# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.

import os
import certifi
import ujson as json
from os import path
from typing import Any, Dict, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from motor.core import AgnosticDatabase, AgnosticCollection


class MongoDB:
    def __init__(self, uri):
        self.tlsca_ = certifi.where()
        self._client = AsyncIOMotorClient(uri, tlsCAFile=self.tlsca_)
        self._db_name: AgnosticDatabase = self._client["Altruix"]
        self.settings_col: AgnosticCollection = self._db_name["SETTINGS"]
        self.data_col: AgnosticCollection = self._db_name["DATA"]
        self.user_col: AgnosticCollection = self._db_name["USERS"]
        self.env_col: AgnosticCollection = self._db_name["ENV"]
        self.stickers_col: AgnosticCollection = self._db_name["STICKERS"]
        self.inline_col: AgnosticCollection = self._db_name["INLINE_METADATA"]
        self.callback_col: AgnosticCollection = self._db_name["CALLBACK_CACHE"]
        self.group_wl_col: AgnosticCollection = self._db_name["GROUP_WHITELIST"]

    async def ping(self):
        return await self._db_name.command("ping")

    def make_collection(self, name: str) -> AgnosticCollection:
        return self._db_name[name]



class LocalCollection:
    def __init__(self, db: "LocalDatabase", name: str):
        self.db = db
        self.name = name

    async def find_one(self, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        data = self.db.get_collection_data(self.name)
        for item in data.values():
            if all(item.get(k) == v for k, v in query.items()):
                return item
        return None

    class _Cursor:
        def __init__(self, async_gen):
            self.async_gen = async_gen
            
        async def to_list(self, length=None):
            result = []
            count = 0
            async for item in self.async_gen:
                if length is not None and count >= length:
                    break
                result.append(item)
                count += 1
            return result
            
        def __aiter__(self):
            return self.async_gen.__aiter__()

    def find(self, query: Dict[str, Any]):
        async def _generator():
            data = self.db.get_collection_data(self.name)
            for item in data.values():
                if not query or all(item.get(k) == v for k, v in query.items()):
                    yield item
        return self._Cursor(_generator())

    async def count_documents(self, query: Dict[str, Any]) -> int:
        data = self.db.get_collection_data(self.name)
        count = 0
        for item in data.values():
            if not query or all(item.get(k) == v for k, v in query.items()):
                count += 1
        return count

    async def insert_one(self, document: Dict[str, Any]):
        if "_id" not in document:
            raise ValueError("Document must have an _id")
        self.db.update_collection(self.name, document["_id"], document)
        return document

    async def find_one_and_delete(self, query: Dict[str, Any]):
        item = await self.find_one(query)
        if item:
            self.db.delete_from_collection(self.name, item["_id"])
        return item

    class _UpdateResult:
        def __init__(self, modified_count):
            self.modified_count = modified_count

    async def update_one(self, query: Dict[str, Any], update: Dict[str, Any], upsert: bool = False):
        item = await self.find_one_and_update(query, update, upsert=upsert)
        return self._UpdateResult(1 if item else 0)

    async def find_one_and_update(
        self, query: Dict[str, Any], update: Dict[str, Any], upsert: bool = False
    ):
        item = await self.find_one(query)
        if not item:
            if upsert:
                # Create new document based on query
                item = query.copy()
                if "_id" not in item:
                    # Try to infer _id from query if possible, mostly used like {_id: 'NAME'}
                    if "_id" in query:
                        item["_id"] = query["_id"]
                    else:
                        raise ValueError("Upsert requires _id in query for LocalDB")
            else:
                return None

        # Apply updates
        if "$set" in update:
            item.update(update["$set"])
        
        if "$push" in update:
            for k, v in update["$push"].items():
                if k not in item:
                    item[k] = []
                if not isinstance(item[k], list):
                    item[k] = [item[k]]
                
                if isinstance(v, dict) and "$each" in v:
                    item[k].extend(v["$each"])
                else:
                    item[k].append(v)

        if "$addToSet" in update:
            for k, v in update["$addToSet"].items():
                if k not in item:
                    item[k] = []
                if not isinstance(item[k], list):
                    item[k] = [item[k]]
                if v not in item[k]:
                    item[k].append(v)

        if "$pull" in update:
            for k, v in update["$pull"].items():
                if k in item and isinstance(item[k], list):
                    if v in item[k]:
                        item[k].remove(v)

        # Save back to DB
        self.db.update_collection(self.name, item["_id"], item)
        return item


import asyncio
import aiofiles

from Main.utils.file_helpers import get_db_path

class LocalDatabase:
    def __init__(self, file_path="altruix_local_db.json"):
        self.path = get_db_path(file_path)
        self.data = {}
        self._dirty = False
        self._lock = asyncio.Lock()
        self._param_lock = asyncio.Lock() # For protecting data access during save
        self._load()
        
        # Initialize collections
        self.settings_col = LocalCollection(self, "SETTINGS")
        self.data_col = LocalCollection(self, "DATA")
        self.user_col = LocalCollection(self, "USERS")
        self.env_col = LocalCollection(self, "ENV")
        self.stickers_col = LocalCollection(self, "STICKERS")
        self.inline_col = LocalCollection(self, "INLINE_METADATA")
        self.callback_col = LocalCollection(self, "CALLBACK_CACHE")
        self.group_wl_col = LocalCollection(self, "GROUP_WHITELIST")
    
    @property
    def lock(self):
        return self._lock

    def _load(self):
        if not path.exists(self.path):
            self.data = {}
            self._sync_save()
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
            self._dirty = False
        except (ValueError, FileNotFoundError):
            self.data = {}
            self._sync_save()

    async def reload(self):
        """Reload database from disk safely."""
        async with self._lock:
            self._load()
            self._dirty = False

    async def safe_extract_and_reload(self, zip_path: str, extract_path: str):
        """Safely extract a ZIP into the DB directory and reload data."""
        import shutil
        async with self._lock:
            # Run extraction in thread
            await asyncio.to_thread(shutil.unpack_archive, zip_path, extract_path, 'zip')
            self._load()
            self._dirty = False

    def _sync_save(self) -> None:
        """Synchronous save for initialization only."""
        with open(self.path, "w+", encoding="utf-8") as _file:
            json.dump(self.data, _file, indent=4)

    async def save_now(self) -> None:
        """Asynchronous save using aiofiles."""
        if not self._dirty:
            return

        async with self._lock:
            try:
                # Create a copy or dump string while holding param lock if needed?
                # For simplicity, we assume dict operations are atomic enough for json dump in CPython
                # But to be safe against concurrent modification during dump:
                
                # Use a custom default to handle non-serializable objects (like Pyrogram Clients)
                def _json_serial(obj):
                    """JSON serializer for objects not serializable by default json code"""
                    return f"<{type(obj).__name__} non-serializable>"
                
                data_to_save = json.dumps(self.data, indent=4, default=_json_serial)
                
                async with aiofiles.open(self.path, "w+", encoding="utf-8") as _file:
                    await _file.write(data_to_save)
                
                self._dirty = False
            except Exception as e:
                # Log the error but don't crash. Now that we have a default handler, 
                # this block should only be reached on disk/file system errors.
                print(f"[LocalDatabase] Save Error: {e}")

    async def start_background_saver(self):
        """Background task to save DB periodically if dirty."""
        while True:
            await asyncio.sleep(2) # Check every 2 seconds
            if self._dirty:
                await self.save_now()

    def get_collection_data(self, col_name: str) -> Dict[str, Any]:
        if col_name not in self.data:
            self.data[col_name] = {}
        return self.data[col_name]

    def update_collection(self, col_name: str, doc_id: str, document: Dict[str, Any]):
        if col_name not in self.data:
            self.data[col_name] = {}
        self.data[col_name][str(doc_id)] = document
        self._dirty = True
        # REMOVED synchronous self.save()

    def delete_from_collection(self, col_name: str, doc_id: str):
        if col_name in self.data and str(doc_id) in self.data[col_name]:
            del self.data[col_name][str(doc_id)]
            self._dirty = True
            # REMOVED synchronous self.save()

    # Compatibility methods needed by existing code if any
    async def ping(self):
        return "pong"
    
    def make_collection(self, name: str):
        return LocalCollection(self, name)

