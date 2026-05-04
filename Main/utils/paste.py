# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.

import httpx
import random
import contextlib
import json
from json import JSONDecodeError
from typing import Set, List, Union


class Paste:
    def __init__(
        self,
        text: str = None,
        title: str = None,
        author: str = None,
        file_ext: str = None,
        service: str = None,
    ) -> None:
        # Try HTTP/2 first, fallback to HTTP/1.1 if h2 package is not installed
        try:
            self.httpx = httpx.AsyncClient(
                http2=True,
                follow_redirects=True,
                headers={"User-Agent": "AltruixUserbot/0.0.8"}
            )
        except ImportError:
            # h2 package not installed, use HTTP/1.1
            self.httpx = httpx.AsyncClient(
                http2=False,
                follow_redirects=True,
                headers={"User-Agent": "AltruixUserbot/0.0.8"}
            )
        self.text: str = text
        self.title: str = title or "Altruix Paste"
        self.author: str = author or "Altruix"
        self.file_ext: str = file_ext
        self.service: str = service
        # ✅ Ensure text is string for JSON serialization
        if isinstance(self.text, bytes):
            try:
                self.text = self.text.decode("utf-8")
            except UnicodeDecodeError:
                self.text = str(self.text)

    async def to_nekobin(self) -> Set[Union[str, None]]:
        url = "https://nekobin.com/api/documents"
        data = {"content": self.text}
        try:
            resp = await self.httpx.post(url, json=data)
            data = resp.json()
            return "nekobin", f"https://nekobin.com/{data['result']['key']}"
        except Exception:
            return None, None

    async def to_idkmoe(self) -> Set[Union[str, None]]:
        url = "https://bin.idk.moe/documents"
        try:
            r = await self.httpx.post(url, content=self.text)
            data = r.json()
            return "idkmoe", f'https://bin.idk.moe/{data["key"]}'
        except Exception:
            return None, None

    async def to_telegraph(self) -> Set[Union[str, None]]:
        # Telegra.ph is very reliable for Telegram-native pastes
        url = "https://api.telegra.ph/createPage"
        # Content must be in nodes format (JSON)
        content_nodes = [{"tag": "pre", "children": [self.text]}]
        data = {
            "title": self.title,
            "author_name": self.author,
            "content": json.dumps(content_nodes),
            "return_content": False
        }
        try:
            r = await self.httpx.post(url, data=data) 
            data = r.json()
            if data.get("ok"):
                return "telegraph", data["result"]["url"]
            return None, None
        except Exception:
            return None, None

    async def to_pasty(self) -> Set[Union[str, None]]:
        url = "https://pasty.lus.pm/api/v1/pastes"
        data = {"content": self.text}
        try:
            r = await self.httpx.post(url, json=data)
            data = r.json()
            return "pasty", f'https://pasty.lus.pm/{data["id"]}'
        except Exception:
            return None, None

    async def to_pasters(self) -> Set[Union[str, None]]:
        url = "https://paste.rs/"
        try:
            r = await self.httpx.post(url, content=self.text)
            if r.status_code < 400:
                return "pasters", r.text.strip()
            return None, None
        except Exception:
            return None, None

    async def to_dpaste(self) -> Set[Union[str, None]]:
        url = "https://dpaste.org/api/"
        data = {"format": "json", "content": self.text}
        try:
            r = await self.httpx.post(url, data=data)
            data = r.json()
            return "dpaste", data["url"]
        except Exception:
            return None, None

    async def paste(self) -> Set[Union[str, None]]:
        service, paste_url = None, None
        if not self.service:
            available_functions = [
                getattr(self, m)
                for m in dir(self)
                if not m.startswith("__")
                and m.startswith("to")
                and callable(getattr(self, m))
            ]
            while paste_url is None and available_functions:
                _ = random.choice(available_functions)
                available_functions.remove(_)
                service, paste_url = await _()
        elif self.service not in self.all_bins:
            raise ValueError(f'"{self.service}" is not a valid paste service!')
        else:
            service, paste_url = await getattr(self, f"to_{self.service}")()
        with contextlib.suppress(Exception):
            await self.httpx.aclose()
        return service, paste_url

    @property
    def all_bins(self) -> List[str]:
        return [
            m.strip("to_")
            for m in dir(self)
            if not m.startswith("__") and m.startswith("to")
        ]

    def __repr__(self) -> str:
        return f"Paste(text={self.text}, title={self.title}, author={self.author}, file_ext={self.file_ext})"
