# Main/utils/cache_manager.py
"""
Cache Manager untuk sistem mentions AltruixX.
Mendukung multiple backends: memory, json, redis, mongodb.
"""

import json
import logging
import asyncio
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union
from datetime import datetime, timedelta
import aiofiles
import time

# Try imports for external databases
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

try:
    from pymongo import MongoClient
    from motor.motor_asyncio import AsyncIOMotorClient
    MONGO_AVAILABLE = True
except ImportError:
    MONGO_AVAILABLE = False

logger = logging.getLogger("altruix.cache_manager")

class CacheManager:
    """Flexible cache manager with multiple backends."""
    
    def __init__(self, config=None):
        self.config = config or {}
        self.backend = self.config.get("cache_backend", "json")
        self.redis_client = None
        self.mongo_client = None
        self.mongo_db = None
        self.mongo_collection = None
        
        # Path untuk JSON cache
        self.json_file = Path(self.config.get("json_cache_path", "mentions_cache.json"))
        
        # In-memory fallback
        self.memory_cache = {}
        self.memory_ttl = {}
        
        logger.info(f"Cache manager initialized with backend: {self.backend}")
    
    async def initialize(self):
        """Initialize the selected backend."""
        try:
            if self.backend == "redis" and REDIS_AVAILABLE:
                redis_url = self.config.get("redis_url", "redis://localhost:6379/0")
                self.redis_client = redis.from_url(redis_url, decode_responses=True)
                await self.redis_client.ping()
                logger.info("✅ Redis cache connected")
                
            elif self.backend == "mongodb" and MONGO_AVAILABLE:
                mongo_uri = self.config.get("mongo_uri", "mongodb://localhost:27017")
                db_name = self.config.get("mongo_db", "altruix")
                collection_name = self.config.get("mongo_collection", "mentions_cache")
                
                self.mongo_client = AsyncIOMotorClient(mongo_uri)
                self.mongo_db = self.mongo_client[db_name]
                self.mongo_collection = self.mongo_db[collection_name]
                
                # Create TTL index
                await self.mongo_collection.create_index("expires_at", expireAfterSeconds=0)
                logger.info(f"✅ MongoDB cache connected to {db_name}.{collection_name}")
                
            elif self.backend == "json":
                # Ensure JSON file exists
                if not self.json_file.exists():
                    async with aiofiles.open(self.json_file, 'w', encoding='utf-8') as f:
                        await f.write('{"cache": {}, "meta": {"created": "' + datetime.now().isoformat() + '"}}')
                logger.info(f"✅ JSON cache ready: {self.json_file}")
                
            else:
                logger.info("✅ Using in-memory cache (no persistence)")
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize {self.backend} cache: {e}")
            logger.warning("⚠️ Falling back to in-memory cache")
            self.backend = "memory"
    
    async def set(self, key: str, value: Any, ttl: int = 7200) -> bool:
        """Set a cache value with TTL (seconds)."""
        try:
            expires_at = datetime.now() + timedelta(seconds=ttl)
            cache_data = {
                "value": value,
                "expires_at": expires_at.isoformat(),
                "created_at": datetime.now().isoformat()
            }
            
            if self.backend == "redis" and self.redis_client:
                await self.redis_client.setex(
                    key, 
                    ttl, 
                    json.dumps(cache_data, ensure_ascii=False)
                )
                
            elif self.backend == "mongodb" and self.mongo_collection:
                cache_data["_id"] = key
                await self.mongo_collection.update_one(
                    {"_id": key},
                    {"$set": cache_data},
                    upsert=True
                )
                
            elif self.backend == "json":
                async with aiofiles.open(self.json_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    data = json.loads(content) if content.strip() else {"cache": {}}
                
                data["cache"][key] = cache_data
                data["meta"]["last_updated"] = datetime.now().isoformat()
                
                async with aiofiles.open(self.json_file, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(data, indent=2, ensure_ascii=False))
                    
            else:  # memory fallback
                self.memory_cache[key] = cache_data
                self.memory_ttl[key] = expires_at.timestamp()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Cache SET failed for {key}: {e}")
            # Fallback to memory
            self.memory_cache[key] = {"value": value, "expires_at": None}
            return False
    
    async def get(self, key: str, default=None) -> Any:
        """Get a cache value."""
        try:
            cache_data = None
            
            if self.backend == "redis" and self.redis_client:
                data = await self.redis_client.get(key)
                if data:
                    cache_data = json.loads(data)
                    
            elif self.backend == "mongodb" and self.mongo_collection:
                doc = await self.mongo_collection.find_one({"_id": key})
                if doc:
                    cache_data = doc
                    
            elif self.backend == "json":
                async with aiofiles.open(self.json_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    if content.strip():
                        data = json.loads(content)
                        cache_data = data.get("cache", {}).get(key)
                        
            else:  # memory
                cache_data = self.memory_cache.get(key)
                if cache_data and key in self.memory_ttl:
                    if datetime.now().timestamp() > self.memory_ttl[key]:
                        del self.memory_cache[key]
                        del self.memory_ttl[key]
                        return default
            
            # Check expiration
            if cache_data:
                expires_at = cache_data.get("expires_at")
                if expires_at:
                    try:
                        if isinstance(expires_at, str):
                            expires_dt = datetime.fromisoformat(expires_at)
                        else:
                            expires_dt = expires_at
                            
                        if datetime.now() > expires_dt:
                            await self.delete(key)
                            return default
                    except:
                        pass
                
                return cache_data.get("value", default)
            
            return default
            
        except Exception as e:
            logger.error(f"❌ Cache GET failed for {key}: {e}")
            return self.memory_cache.get(key, {}).get("value", default)
    
    async def delete(self, key: str) -> bool:
        """Delete a cache key."""
        try:
            if self.backend == "redis" and self.redis_client:
                await self.redis_client.delete(key)
                
            elif self.backend == "mongodb" and self.mongo_collection:
                await self.mongo_collection.delete_one({"_id": key})
                
            elif self.backend == "json":
                async with aiofiles.open(self.json_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    if content.strip():
                        data = json.loads(content)
                        if key in data.get("cache", {}):
                            del data["cache"][key]
                            data["meta"]["last_updated"] = datetime.now().isoformat()
                            
                            async with aiofiles.open(self.json_file, 'w', encoding='utf-8') as f:
                                await f.write(json.dumps(data, indent=2, ensure_ascii=False))
            
            # Always clean memory cache
            self.memory_cache.pop(key, None)
            self.memory_ttl.pop(key, None)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Cache DELETE failed for {key}: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if a key exists in cache."""
        try:
            value = await self.get(key)
            return value is not None
        except:
            return False
    
    async def cleanup_expired(self) -> int:
        """Cleanup expired entries from all backends."""
        count = 0
        try:
            now = datetime.now()
            
            # 1. Cleanup Memory Cache
            expired_keys = [
                k for k, t in self.memory_ttl.items() 
                if now.timestamp() > t
            ]
            for k in expired_keys:
                self.memory_cache.pop(k, None)
                self.memory_ttl.pop(k, None)
                count += 1
            
            # 2. Cleanup JSON Cache
            if self.backend == "json" and self.json_file.exists():
                async with aiofiles.open(self.json_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    data = json.loads(content) if content.strip() else {"cache": {}}
                
                initial_len = len(data.get("cache", {}))
                
                # Filter expired
                new_cache = {}
                for k, v in data.get("cache", {}).items():
                    try:
                        expires_at = v.get("expires_at")
                        if expires_at:
                            if isinstance(expires_at, str):
                                expires_dt = datetime.fromisoformat(expires_at)
                            else:
                                expires_dt = expires_at
                            
                            if now <= expires_dt:
                                new_cache[k] = v
                        else:
                            new_cache[k] = v
                    except:
                        pass
                
                if len(new_cache) < initial_len:
                    data["cache"] = new_cache
                    data["meta"]["last_cleanup"] = now.isoformat()
                    async with aiofiles.open(self.json_file, 'w', encoding='utf-8') as f:
                        await f.write(json.dumps(data, indent=2, ensure_ascii=False))
                    count += (initial_len - len(new_cache))

            # 3. Redis & Mongo usually handle their own TTL, but we can verify if needed
            # For this implementation, we rely on their native TTL mechanisms.
            
            return count
            
        except Exception as e:
            logger.error(f"❌ Cache cleanup failed: {e}")
            return 0

    async def clear(self) -> bool:
        """Clear all cache."""
        try:
            if self.backend == "redis" and self.redis_client:
                await self.redis_client.flushdb()
                
            elif self.backend == "mongodb" and self.mongo_collection:
                await self.mongo_collection.delete_many({})
                
            elif self.backend == "json":
                async with aiofiles.open(self.json_file, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps({
                        "cache": {},
                        "meta": {
                            "created": datetime.now().isoformat(),
                            "cleared": datetime.now().isoformat()
                        }
                    }, indent=2, ensure_ascii=False))
            
            # Clear memory
            self.memory_cache.clear()
            self.memory_ttl.clear()
            
            logger.info("🧹 Cache CLEARED")
            return True
            
        except Exception as e:
            logger.error(f"❌ Cache CLEAR failed: {e}")
            return False
    
    async def get_stats(self) -> Dict:
        """Get cache statistics."""
        try:
            stats = {
                "backend": self.backend,
                "memory_items": len(self.memory_cache),
                "timestamp": datetime.now().isoformat()
            }
            
            if self.backend == "redis" and self.redis_client:
                stats["redis_keys"] = await self.redis_client.dbsize()
                
            elif self.backend == "mongodb" and self.mongo_collection:
                stats["mongodb_count"] = await self.mongo_collection.count_documents({})
                
            elif self.backend == "json":
                if self.json_file.exists():
                    async with aiofiles.open(self.json_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        if content.strip():
                            data = json.loads(content)
                            stats["json_items"] = len(data.get("cache", {}))
                            stats["last_updated"] = data.get("meta", {}).get("last_updated")
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Cache stats failed: {e}")
            return {"error": str(e)}

# Global cache instance
cache_manager = None

async def init_cache(config=None):
    """Initialize cache manager globally."""
    global cache_manager
    if cache_manager is None:
        cache_manager = CacheManager(config)
        await cache_manager.initialize()
    return cache_manager

# Export functions for convenience
__all__ = ['cache_manager', 'init_cache', 'CacheManager']