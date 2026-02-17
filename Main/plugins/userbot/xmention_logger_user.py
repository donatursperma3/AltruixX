# Main/plugins/userbot/mentions.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.

from Main import Altruix
from Main.core.types.message import Message as AltruixMessage
from pyrogram import Client, enums, filters
from pyrogram.types import (
    Message as RawMessage,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyParameters,
    CallbackQuery
)
from datetime import datetime, timedelta
from Main.core.decorators import log_errors, iuser_check
import os
import re
import asyncio
import html
import logging
import time
import json
import traceback
from pathlib import Path
import aiofiles
from typing import Optional, Union, Dict, Any, List
from collections import defaultdict
import sys
from Main.utils.topic_utils import get_or_create_topic
# ✅ Import SessionManager for persistence
from Main.plugins.userbot.xpm_logger_user import SessionManager


# ============================================================================
# LOGGER KHUSUS PLUGIN
# ============================================================================
plugin_name = f"{os.path.basename(__file__)}"
__plugin_name__ = plugin_name if plugin_name else "tags"  # Renamed from mentions
PLUGIN_VERSION = "1.7.73-TAG"  # ✅ Improved safe settings & multi-account sync

# Gunakan logger Altruix jika tersedia, atau buat baru yang konsisten
logger = logging.getLogger("altruix.mentions")
logger.setLevel(logging.INFO)

# 🔥 LOG STARTUP
# logger.info(f"🚀 Initializing mentions plugin {PLUGIN_VERSION}")


# ============================================================================
# 🔥 IMPORT CACHE MANAGER DARI Main.utils
# ============================================================================
try:
    from Main.utils.cache_manager import cache_manager, init_cache
    CACHE_MANAGER_AVAILABLE = True
    logger_info = "✅ Cache manager imported successfully from Main.utils"
    # logger.info(f"[DEBUG] {logger_info} to {__plugin_name__}")
except ImportError as e:
    # Coba cara alternatif jika gagal
    try:
        # Tambahkan path ke sys.path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.abspath(os.path.join(current_dir, '../../../'))
        if root_dir not in sys.path:
            sys.path.insert(0, root_dir)
        
        from Main.utils.cache_manager import cache_manager, init_cache
        CACHE_MANAGER_AVAILABLE = True
        logger_info = "✅ Cache manager imported with path adjustment"
        # logger.info(f"[DEBUG] ✅ {logger_info} to {__plugin_name__}")
    except ImportError as e2:
        CACHE_MANAGER_AVAILABLE = False
        logger_info = f"⚠️ Cache manager import failed: {e2}"
        # logger.info(f"[DEBUG] ✅ {logger_info} to {__plugin_name__}")
        
        # Fallback definitions
        cache_manager = None
        
        async def init_cache(config=None):
            return None

logger.info(logger_info)

# ============================================================================
# 🔥 CACHE KEY PREFIXES DAN KONFIGURASI
# ============================================================================
CACHE_PREFIX_MENTION = "mention:"
CACHE_PREFIX_WAITING = "waiting:"
CACHE_PREFIX_USER_COUNT = "user_count:"
CACHE_PREFIX_SETTINGS = "settings:"
CACHE_PREFIX_CLIENT = "client:"

# 🔥 TTL SETTINGS (dalam detik)
TTL_MENTION_CACHE = 7200  # 2 jam untuk mention cache
TTL_WAITING_REPLY = 3600  # 1 jam untuk waiting replies
TTL_USER_COUNTS = 86400   # 24 jam untuk rate limiting
TTL_CLIENT_CACHE = 300    # 5 menit untuk client cache

# Shared state from Altruix object (PERSISTENT across reloads)
REPLY_AS_MENTIONED_WAITING = Altruix.REPLY_AS_MENTIONED_WAITING
MENTION_LOG_CACHE = Altruix.PM_LOG_CACHE
SHARED_BUTTON_STATS = Altruix.BUTTON_STATS

# Default Mode
REPLY_ACCESS_MODE = "sudo"
MENTION_SETTINGS_GLOBAL = {"mention": False, "auto_log": True, "reply_from_all": False, "auto_create_topic": False}
MENTION_APPLY_TYPES = {}

def get_shared_reply_mode():
    """Read reply mode from shared settings file."""
    try:
        from Main.utils.file_helpers import get_db_path
        shared_file = get_db_path("pm_logger_user_settings.json")
        if os.path.exists(shared_file):
            with open(shared_file, "r") as f:
                data = json.load(f)
                return data.get("reply_access_mode", "sudo")
    except Exception as e:
        logger.error(f"Failed to read shared reply mode: {e}")
    return "sudo"


# ============================================================================
# 🔥 PERBAIKAN: Helper functions
# ============================================================================
def log_button_press(button_name: str, data: str, user_id: Optional[int] = None):
    """Log setiap tombol yang ditekan."""
    user_info = f" by user {user_id}" if user_id else ""
    logger.debug(f"🔘 Button '{button_name}' pressed{user_info}: {data}")

def safe_datetime_fromtimestamp(timestamp) -> datetime:
    """Convert timestamp to datetime."""
    try:
        if timestamp is None:
            return datetime.now()
        
        if isinstance(timestamp, datetime):
            return timestamp
        
        if isinstance(timestamp, (int, float)):
            if timestamp > 4102444800:
                timestamp = timestamp / 1000
            return datetime.fromtimestamp(float(timestamp))
        
        return datetime.now()
    except Exception as e:
        logger.warning(f"Datetime conversion error: {e}")
        return datetime.now()

async def safe_send_message(
    client: Client, 
    chat_id: Union[int, str], 
    text: str, 
    **kwargs
) -> Optional[RawMessage]:
    """Send message dengan timeout dan error handling."""
    try:
        return await asyncio.wait_for(
            client.send_message(chat_id, text, **kwargs),
            timeout=30
        )
    except asyncio.TimeoutError:
        logger.warning(f"Timeout sending message to {chat_id}")
        return None
    except Exception as e:
        logger.error(f"Send message failed: {e}")
        return None

async def safe_edit_message(
    client: Client,
    chat_id: Union[int, str],
    message_id: int,
    text: str,
    **kwargs
) -> bool:
    """Edit message dengan timeout handling."""
    try:
        await asyncio.wait_for(
            client.edit_message_text(chat_id, message_id, text, **kwargs),
            timeout=15
        )
        return True
    except asyncio.TimeoutError:
        logger.warning(f"Timeout editing message {message_id}")
        return False
    except Exception as e:
        logger.error(f"Edit message failed: {e}")
        return False

# ============================================================================
# 🔥 CACHE HELPER FUNCTIONS - Interface ke cache_manager
# ============================================================================
async def cache_set(key: str, value: Any, ttl: int = None) -> bool:
    """Set value ke cache dengan TTL."""
    try:
        if CACHE_MANAGER_AVAILABLE and cache_manager:
            return await cache_manager.set(key, value, ttl or TTL_MENTION_CACHE)
        else:
            # Fallback ke in-memory dengan file backup
            return await _fallback_cache_set(key, value, ttl)
    except Exception as e:
        logger.error(f"❌ Cache SET failed for {key}: {e}")
        return False

async def cache_get(key: str, default=None) -> Any:
    """Get value dari cache."""
    try:
        if CACHE_MANAGER_AVAILABLE and cache_manager:
            return await cache_manager.get(key, default)
        else:
            return await _fallback_cache_get(key, default)
    except Exception as e:
        logger.error(f"❌ Cache GET failed for {key}: {e}")
        return default

async def cache_delete(key: str) -> bool:
    """Delete key dari cache."""
    try:
        if CACHE_MANAGER_AVAILABLE and cache_manager:
            return await cache_manager.delete(key)
        else:
            return await _fallback_cache_delete(key)
    except Exception as e:
        logger.error(f"❌ Cache DELETE failed for {key}: {e}")
        return False

async def cache_exists(key: str) -> bool:
    """Check jika key ada di cache."""
    try:
        if CACHE_MANAGER_AVAILABLE and cache_manager:
            return await cache_manager.exists(key)
        else:
            return await _fallback_cache_exists(key)
    except Exception as e:
        logger.error(f"❌ Cache EXISTS failed for {key}: {e}")
        return False

# ============================================================================
# 🔥 FALLBACK CACHE SYSTEM (In-memory dengan JSON backup)
# ============================================================================
# Fallback cache initialization (only if shared state is missing)
if "MENTION_LOG_CACHE" not in globals() or MENTION_LOG_CACHE is None:
    MENTION_LOG_CACHE = {}
USER_REPLY_COUNTS = defaultdict(lambda: defaultdict(int))
MENTIONS_DATA = {}
AUTO_REPLY_ENABLED = False

async def _fallback_cache_set(key: str, value: Any, ttl: int = None) -> bool:
    """Fallback in-memory cache dengan file persistence."""
    try:
        # In-memory storage
        MENTION_LOG_CACHE[key] = {
            "value": value,
            "expires_at": time.time() + (ttl or TTL_MENTION_CACHE),
            "created_at": time.time()
        }
        
        # Backup ke file setiap 10 operasi write
        if hasattr(_fallback_cache_set, 'write_count'):
            _fallback_cache_set.write_count += 1
        else:
            _fallback_cache_set.write_count = 1
            
        if _fallback_cache_set.write_count % 10 == 0:
            await _save_fallback_cache()
            
        return True
    except Exception as e:
        logger.error(f"❌ Fallback cache SET failed: {e}")
        return False

async def _fallback_cache_get(key: str, default=None) -> Any:
    """Get dari fallback cache."""
    try:
        if key in MENTION_LOG_CACHE:
            entry = MENTION_LOG_CACHE[key]
            if entry["expires_at"] > time.time():
                return entry["value"]
            else:
                del MENTION_LOG_CACHE[key]
        return default
    except:
        return default

async def _fallback_cache_delete(key: str) -> bool:
    """Delete dari fallback cache."""
    try:
        if key in MENTION_LOG_CACHE:
            del MENTION_LOG_CACHE[key]
            return True
        return False
    except:
        return False

async def _fallback_cache_exists(key: str) -> bool:
    """Check existence in fallback cache."""
    try:
        if key in MENTION_LOG_CACHE:
            entry = MENTION_LOG_CACHE[key]
            if entry["expires_at"] > time.time():
                return True
            else:
                del MENTION_LOG_CACHE[key]
        return False
    except:
        return False

async def _save_fallback_cache():
    """Save fallback cache to file."""
    try:
        file_path = Path(get_db_path("mentions_cache_fallback.json"))
        data = {
            "cache": MENTION_LOG_CACHE,
            "meta": {
                "saved_at": time.time(),
                "count": len(MENTION_LOG_CACHE)
            }
        }
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception as e:
        logger.error(f"❌ Failed to save fallback cache: {e}")

async def _load_fallback_cache():
    """Load fallback cache from file."""
    try:
        file_path = Path(get_db_path("mentions_cache_fallback.json"))
        if file_path.exists():
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                if content.strip():
                    data = json.loads(content)
                    # Filter expired entries
                    now = time.time()
                    for key, entry in data.get("cache", {}).items():
                        if entry.get("expires_at", 0) > now:
                            MENTION_LOG_CACHE[key] = entry
                    
            logger.info(f"Loaded {len(MENTION_LOG_CACHE)} entries from fallback cache")
    except Exception as e:
        logger.error(f"Failed to load fallback cache: {e}")

# Initialize fallback cache
asyncio.create_task(_load_fallback_cache())

# ============================================================================
# 🔥 SPECIFIC CACHE FUNCTIONS untuk mentions plugin
# ============================================================================
async def get_mention_from_cache(msg_key: str) -> Optional[Dict]:
    """Get mention data from cache."""
    cache_key = f"{CACHE_PREFIX_MENTION}{msg_key}"
    return await cache_get(cache_key)

async def save_mention_to_cache(msg_key: str, data: Dict) -> bool:
    """Save mention data to cache."""
    cache_key = f"{CACHE_PREFIX_MENTION}{msg_key}"
    return await cache_set(cache_key, data, TTL_MENTION_CACHE)

async def delete_mention_from_cache(msg_key: str) -> bool:
    """Delete mention data from cache."""
    cache_key = f"{CACHE_PREFIX_MENTION}{msg_key}"
    return await cache_delete(cache_key)

async def check_mention_in_cache(msg_key: str) -> bool:
    """Check if mention exists in cache."""
    cache_key = f"{CACHE_PREFIX_MENTION}{msg_key}"
    return await cache_exists(cache_key)

async def get_waiting_reply(waiting_id: str) -> Optional[Dict]:
    """Get waiting reply data."""
    cache_key = f"{CACHE_PREFIX_WAITING}{waiting_id}"
    return await cache_get(cache_key)

async def save_waiting_reply(waiting_id: str, data: Dict) -> bool:
    """Save waiting reply data."""
    cache_key = f"{CACHE_PREFIX_WAITING}{waiting_id}"
    return await cache_set(cache_key, data, TTL_WAITING_REPLY)

async def delete_waiting_reply(waiting_id: str) -> bool:
    """Delete waiting reply data."""
    cache_key = f"{CACHE_PREFIX_WAITING}{waiting_id}"
    return await cache_delete(cache_key)

async def get_user_reply_count(user_id: int, date_str: str = None) -> int:
    """Get user's reply count for rate limiting."""
    if not date_str:
        date_str = datetime.now().strftime("%Y%m%d")
    
    cache_key = f"{CACHE_PREFIX_USER_COUNT}{user_id}:{date_str}"
    
    if CACHE_MANAGER_AVAILABLE:
        return await cache_get(cache_key, 0)
    else:
        # Fallback ke in-memory
        return USER_REPLY_COUNTS[user_id][date_str]

async def increment_user_reply_count(user_id: int, date_str: str = None) -> int:
    """Increment user's reply count."""
    if not date_str:
        date_str = datetime.now().strftime("%Y%m%d")
    
    cache_key = f"{CACHE_PREFIX_USER_COUNT}{user_id}:{date_str}"
    
    if CACHE_MANAGER_AVAILABLE:
        current = await get_user_reply_count(user_id, date_str)
        new_count = current + 1
        await cache_set(cache_key, new_count, TTL_USER_COUNTS)
        return new_count
    else:
        # Fallback ke in-memory
        USER_REPLY_COUNTS[user_id][date_str] += 1
        return USER_REPLY_COUNTS[user_id][date_str]

async def decrement_user_reply_count(user_id: int, date_str: str = None) -> int:
    """Decrement user's reply count."""
    if not date_str:
        date_str = datetime.now().strftime("%Y%m%d")
    
    cache_key = f"{CACHE_PREFIX_USER_COUNT}{user_id}:{date_str}"
    
    if CACHE_MANAGER_AVAILABLE:
        current = await get_user_reply_count(user_id, date_str)
        new_count = max(0, current - 1)
        await cache_set(cache_key, new_count, TTL_USER_COUNTS)
        return new_count
    else:
        # Fallback ke in-memory
        USER_REPLY_COUNTS[user_id][date_str] = max(0, USER_REPLY_COUNTS[user_id][date_str] - 1)
        return USER_REPLY_COUNTS[user_id][date_str]

async def get_mention_setting(client_id: int) -> bool:
    """Get mention setting for a client."""
    cache_key = f"{CACHE_PREFIX_SETTINGS}{client_id}"
    return await cache_get(cache_key, False)

async def save_mention_setting(client_id: int, value: bool) -> bool:
    """Save mention setting for a client."""
    cache_key = f"{CACHE_PREFIX_SETTINGS}{client_id}"
    return await cache_set(cache_key, bool(value), 86400 * 30)  # 30 days TTL

# ============================================================================
# 🔥 KONFIGURASI DEFAULT
# ============================================================================
# 🔥 PERBAIKAN CRITICAL: Emoji yang valid untuk Telegram Reaction API
DEFAULT_REACTION_EMOJIS = ["👍", "❤️", "🔥", "🥰", "👏", "🎉"]

REPLY_FROM_ALL_ACCESSIBLE = True  # Global toggle for Reply From All button visibility

# 🔥 BARU: Button press statistics
BUTTON_STATS = {
    "react": 0,
    "reply": 0,
    "reply_all": 0,
    "confirm": 0,
    "cancel": 0,
    "save": 0,
    "unsend": 0
}

USER_REPLY_LIMIT = 9  # Rate limiting untuk Reply From All

# 🔥 BARU: Valid emoji checker
VALID_REACTION_EMOJIS = {
    "👍", "👎", "❤️", "🔥", "🥰", "👏", "😁", "🤔", "🤯", "😱", 
    "🤬", "😢", "🎉", "🤩", "🤮", "💩", "🙏", "👌", "🕊", "🤡",
    "🥱", "🥴", "😍", "🐳", "❤️‍🔥", "🌚", "🌭", "💯", "🤣", "⚡",
    "🍌", "🏆", "💔", "🤨", "😐", "🍓", "🍾", "💋", "🖕", "😈",
    "😴", "😭", "🤓", "👻", "👨‍💻", "👀", "🎃", "🙈", "😇", "😨",
    "🤝", "✍️", "🤗", "🫡", "🎅", "🎄", "☃️", "💅", "🤪", "🗿",
    "🆒", "💘", "🙉", "🦄", "😘", "💊", "🙊", "😎", "👾", "🤷‍♂️",
    "🤷", "🤷‍♀️", "😡"
}

def is_valid_emoji(emoji: str) -> bool:
    """Cek apakah emoji valid untuk Telegram Reaction."""
    return emoji in VALID_REACTION_EMOJIS

def get_permission_label(mode: str = "sudo") -> str:
    """Generate permission label for Reply button."""
    if mode == "owner":
        return Altruix.get_string("PERM_LABEL_OWNER") or "Reply (Owner)"
    elif mode == "sudo":
        return Altruix.get_string("PERM_LABEL_SUDO") or "Reply (Sudo + Owner)"
    elif mode == "all":
        return Altruix.get_string("PERM_LABEL_ALL") or "Reply (All)"
    else:
        return f"{Altruix.get_string('PERM_LABEL_CUSTOM') or 'Reply'} ({mode})"

# ============================================================================
# 🔥 PERBAIKAN: get_mention_client dengan CACHING
# ============================================================================
async def get_mention_client(user_id: int) -> Optional[Client]:
    """Dapatkan client yang sesuai berdasarkan user_id dengan caching."""
    try:
        user_id = int(user_id)
        logger.info(f"🔄 get_mention_client called for user_id: {user_id}")
        
        # Cache key untuk client lookup
        cache_key = f"{CACHE_PREFIX_CLIENT}{user_id}"
        cached_client = await cache_get(cache_key)
        
        # Jika cache mengembalikan "NOT_FOUND", langsung return None
        if cached_client == "NOT_FOUND":
            logger.debug(f"⚠️ Client {user_id} marked as NOT_FOUND in cache")
            return None
        
        # 1. Cek di daftar userbot clients
        if hasattr(Altruix, 'clients') and Altruix.clients:
            logger.info(f"📋 Found {len(Altruix.clients)} clients")
            for i, client in enumerate(Altruix.clients):
                try:
                    # Gunakan cache myself jika ada, atau get_me
                    me = getattr(client, "myself", None)
                    if not me and client.is_connected:
                        me = await client.get_me()
                        client.myself = me  # Cache it

                    if me:
                        logger.info(f"  Client {i}: ID={me.id}, Name={me.first_name}")
                        if me.id == user_id:
                            logger.info(f"✅ Found matching client: {me.first_name} ({user_id})")
                            # Cache the client reference sebagai "FOUND"
                            await cache_set(cache_key, "FOUND", TTL_CLIENT_CACHE)
                            return client
                    else:
                        logger.warning(f"  Client {i}: Could not get 'me' info")
                except Exception as e:
                    logger.warning(f"  Error checking client {i}: {e}")
                    continue
        else:
            logger.warning("⚠️ No 'clients' attribute found in Altruix or it's empty")
        
        # 🔥 **PERBAIKAN**: Cek atribut lain dengan logging yang lebih detail
        for attr_name in ['userbot_clients', 'ubot', 'client']:
            if hasattr(Altruix, attr_name):
                attr = getattr(Altruix, attr_name)
                logger.info(f"🔍 Checking attribute '{attr_name}': {type(attr)}")
                
                if isinstance(attr, (list, tuple)):
                    for i, item in enumerate(attr):
                        if isinstance(item, Client):
                            try:
                                me = getattr(item, "myself", None)
                                if not me and item.is_connected:
                                    me = await item.get_me()
                                    item.myself = me
                                
                                if me and me.id == user_id:
                                    logger.info(f"✅ Found client {me.first_name} in {attr_name}[{i}]")
                                    await cache_set(cache_key, "FOUND", TTL_CLIENT_CACHE)
                                    return item
                            except Exception as e:
                                logger.warning(f"  Error checking {attr_name}[{i}]: {e}")
                                continue
                elif isinstance(attr, Client):
                    try:
                        me = getattr(attr, "myself", None)
                        if not me and attr.is_connected:
                            me = await attr.get_me()
                            attr.myself = me
                        
                        if me and me.id == user_id:
                            logger.info(f"✅ Found client {me.first_name} in {attr_name}")
                            await cache_set(cache_key, "FOUND", TTL_CLIENT_CACHE)
                            return attr
                    except Exception as e:
                        logger.warning(f"  Error checking {attr_name}: {e}")
                        continue

        # 4. Jika tidak ditemukan, cache "NOT_FOUND" untuk 1 menit
        logger.warning(f"❌ Client {user_id} not found in any active sessions")
        await cache_set(cache_key, "NOT_FOUND", 60)
        return None
        
    except Exception as e:
        logger.error(f"❌ [get_mention_client] Error getting client: {e}", exc_info=True)
        return None


# ============================================================================
# 🔥 Initialize cache manager pada startup
# ============================================================================
async def init_mentions_cache():
    """Initialize cache manager for mentions plugin."""
    try:
        if not CACHE_MANAGER_AVAILABLE:
            logger.warning("⚠️ Cache manager not available, using in-memory cache only")
            return
        
        # Determine which backend to use from environment
        cache_config = {
            "cache_backend": "json",  # Default
            "json_cache_path": "mentions_cache.json"
        }
        
        # Cek environment variables
        if os.environ.get("REDIS_URL"):
            cache_config["cache_backend"] = "redis"
            cache_config["redis_url"] = os.environ.get("REDIS_URL")
            logger.info("Using Redis cache backend")
        elif os.environ.get("MONGO_URI"):
            cache_config["cache_backend"] = "mongodb"
            cache_config["mongo_uri"] = os.environ.get("MONGO_URI")
            cache_config["mongo_db"] = os.environ.get("MONGO_DB", "altruix")
            cache_config["mongo_collection"] = os.environ.get("MONGO_COLLECTION", "mentions_cache")
            logger.info("Using MongoDB cache backend")
        
        # Initialize cache manager
        await init_cache(cache_config)
        logger.info(f"✅ Mentions cache initialized with {cache_config['cache_backend']} backend")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize cache: {e}")
        logger.warning("⚠️ Using fallback memory cache only")

# Start cache initialization
asyncio.create_task(init_mentions_cache())

from Main.utils.file_helpers import get_db_path

# ============================================================================
# 🔥 LOAD SETTINGS DARI CACHE PADA STARTUP
# ============================================================================
async def load_settings_on_startup():
    """Load settings from cache on startup."""
    try:
        global REPLY_FROM_ALL_ACCESSIBLE, MENTIONS_DATA, AUTO_REPLY_ENABLED
        
        # Load REPLY_FROM_ALL_ACCESSIBLE dari cache
        cached_value = await cache_get("reply_from_all_accessible")
        if cached_value is not None:
            REPLY_FROM_ALL_ACCESSIBLE = bool(cached_value)
            logger.info(f"Loaded REPLY_FROM_ALL_ACCESSIBLE from cache: {REPLY_FROM_ALL_ACCESSIBLE}")
        
        # Load MENTIONS_DATA dari local JSON (fallback)
        await load_local_storage()
    except Exception as e:
        logger.error(f"Failed to load settings from cache: {e}")

# Track last load time to avoid unnecessary disk I/O
LAST_LOAD_TIME_MENTION = 0

async def load_local_storage():
    """
    Loads Mention Logger settings from the local JSON storage file.
    Uses mtime check to avoid redundant loads from disk.
    Ensures per-account settings, global configurations, and apply types are correctly restored.
    """
    global MENTION_SETTINGS_GLOBAL, MENTIONS_DATA, MENTION_APPLY_TYPES, AUTO_REPLY_ENABLED, LAST_LOAD_TIME_MENTION
    try:
        if LOCAL_STORAGE_FILE.exists():
            # Optimization: Only load if file modified since last load
            current_mtime = LOCAL_STORAGE_FILE.stat().st_mtime
            if current_mtime <= LAST_LOAD_TIME_MENTION and MENTIONS_DATA:
                return
                
            async with aiofiles.open(LOCAL_STORAGE_FILE, 'r', encoding='utf-8') as f:
                content = await f.read()
                if content.strip():
                    data = json.loads(content)
                    # Support both new and old format
                    if "global" in data:
                        MENTION_SETTINGS_GLOBAL = data.get("global", {})
                        MENTIONS_DATA = data.get("settings", {})
                        MENTION_APPLY_TYPES = data.get("apply_types", {})
                    else:
                        # Old format migration
                        MENTIONS_DATA = data.get("settings", data)
                        MENTION_SETTINGS_GLOBAL = {
                            "mention": data.get("mention", True),
                            "auto_log": data.get("auto_log", True),
                            "reply_from_all": data.get("reply_from_all", False)
                        }
                    AUTO_REPLY_ENABLED = data.get("auto_reply", False)
                    LAST_LOAD_TIME_MENTION = current_mtime
                    logger.debug(f"Mention settings reloaded (mtime: {current_mtime})")
    except Exception as e:
        logger.error(f"Failed to load mention local storage: {e}")

asyncio.create_task(load_settings_on_startup())

# ============================================================================
# 🔥 LOCAL JSON STORAGE (untuk backward compatibility)
# ============================================================================
LOCAL_STORAGE_FILE = Path(get_db_path("mentions_settings.json"))

async def save_local_storage():
    """Save data ke local JSON file."""
    try:
        data = {
            "global": MENTION_SETTINGS_GLOBAL,
            "settings": MENTIONS_DATA,
            "apply_types": MENTION_APPLY_TYPES,
            "auto_reply": AUTO_REPLY_ENABLED,
            "last_saved": int(time.time()),
            "version": PLUGIN_VERSION
        }
        async with aiofiles.open(LOCAL_STORAGE_FILE, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception as e:
        logger.error(f"Failed to save local storage: {e}")

async def get_mention_setting_safe(client_id: int, key: str = "mention") -> bool:
    """
    ✅ ENHANCED: Primary source for Mention Logger status.
    Prioritizes Altruix.config (Database) for 'enabled' status (mention key) 
    to ensure synchronization with the UI dashboard.
    Falls back to mentions_settings.json for advanced filters.
    """
    # Ensure fresh settings from disk (for advanced filters)
    await load_local_storage()
    
    client_id_str = str(client_id)
    
    # --- 1. RESOLVE ENABLED STATUS FROM DATABASE (Altruix.config) ---
    # This is critical to fix the desync with the UI dashboard.
    if key == "mention":
        try:
            # Find session index for this client_id
            idx = -1
            if hasattr(Altruix, "clients"):
                for i, client in enumerate(Altruix.clients):
                    if client.me and client.me.id == client_id:
                        idx = i
                        break
            
            if idx != -1:
                # Resolve Apply Type (Global vs Per-Account) from Config
                apply_type = await Altruix.config.get_env(f"MNT_LOGGER_APPLY_TYPE_{idx}") or "per_account"
                
                if apply_type == "global":
                    status = await Altruix.config.get_env("MNT_LOGGER_GLOBAL") or "off"
                else:
                    status = await Altruix.config.get_env(f"MNT_LOGGER_{idx}") or "off"
                
                return status == "on"
        except Exception as e:
            logger.error(f"❌ Failed to fetch mention status from config for {client_id}: {e}")

    # --- 2. FALLBACK TO JSON FOR ADVANCED FILTERS OR IF CONFIG FAILS ---
    # Resolve apply_type from JSON (fallback)
    apply_type_json = MENTION_APPLY_TYPES.get(client_id_str, "per_account")
    
    if apply_type_json == "global":
        return bool(MENTION_SETTINGS_GLOBAL.get(key, False)) # Default False (OFF)

    # Check local storage (settings per client)
    if client_id_str in MENTIONS_DATA:
        setting_data = MENTIONS_DATA[client_id_str]
        if isinstance(setting_data, dict):
            # Check nested filters if the key is a message type
            if key not in ["mention", "auto_log", "reply_from_all", "auto_create_topic"]:
                 p_filters = setting_data.get("filters", {})
                 return bool(p_filters.get(key, True))
            return bool(setting_data.get(key, False))
        elif isinstance(setting_data, bool) and key == "mention":
            return setting_data

    # Final fallback to Global JSON
    return bool(MENTION_SETTINGS_GLOBAL.get(key, False))

async def save_mention_setting_safe(client_id: int, value: bool) -> bool:
    """Safe method untuk menyimpan setting - simpan ke cache DAN local."""
    # Simpan ke cache
    cache_success = await save_mention_setting(client_id, value)
    
    # Simpan ke local storage untuk backward compatibility
    client_id_str = str(client_id)
    MENTIONS_DATA[client_id_str] = {
        "value": bool(value),
        "timestamp_int": int(time.time())
    }
    await save_local_storage()
    
    logger.info(f"Saved setting for {client_id}: {value} (cache: {cache_success})")
    return cache_success

# Load local storage
# asyncio.create_task(load_local_storage()) # REMOVED: Redundant, already called in load_settings_on_startup


@Altruix.register_on_cmd(
    ["mentions_debug_waiting"],
    cmd_help={
        "help": "Debug waiting entries in memory",
        "example": "mentions_debug_waiting",
    },
    group_only=False,
    requires_input=False,
)
@log_errors
async def debug_waiting_handler(c: Client, m: AltruixMessage):
    """Debug waiting entries untuk troubleshooting."""
    msg = await m.handle_message("PROCESSING")
    
    try:
        if not REPLY_AS_MENTIONED_WAITING:
            await msg.edit_msg(Altruix.get_string("MENTION_NO_WAITING"))
            return
        
        response = f"{Altruix.get_string('MENTION_WAITING_HEADER').format(count=len(REPLY_AS_MENTIONED_WAITING))}\n\n"
        
        for waiting_id, data in list(REPLY_AS_MENTIONED_WAITING.items()):
            response += f"• **{waiting_id}**\n"
            response += f"  Chat: `{data.get('chat_id', 'N/A')}`\n"
            response += f"  Message: `{data.get('message_id', 'N/A')}`\n"
            response += f"  Client ID: `{data.get('client_id', 'N/A')}`\n"
            response += f"  Instruction Msg ID: `{data.get('instruction_msg_id', 'Not set')}`\n"
            response += f"  User ID: `{data.get('user_id', 'N/A')}`\n"
            response += f"  Is Reply All: `{data.get('is_reply_all', False)}`\n"
            response += f"  Reply Text: {data.get('reply_text', 'Not set')[:30]}\n\n"
        
        # Potong jika terlalu panjang
        if len(response) > 4000:
            response = response[:3900] + "\n\n... (truncated)"
        
        await safe_edit_message(
            c,
            m.chat.id,
            msg.id,
            response,
            parse_mode=enums.ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"❌ Debug waiting failed: {e}")
        await msg.edit_msg(f"❌ Error: {str(e)[:100]}")


# ============================================================================
# 🔥 MAIN MENTION HANDLER - DIUPDATE DENGAN CACHE
# ============================================================================
@Altruix.register_on_cmd(
    ["mentions"],
    cmd_help={
        "help": "To toggle notify mentions globally or toggle reply-from-all access.",
        "example": "mentions (on/off) | mentions replyall (on/off)",
    },
    group_only=False,
    requires_input=True,
)
@log_errors
async def mention_settings_handler(c: Client, m: AltruixMessage):
    """Handler untuk mengaktifkan/menonaktifkan notifikasi mention global."""
    msg = await m.handle_message("PROCESSING")
    try:
        text, markup = await generate_mnt_menu_async(c.me.id)
        if markup:
            await msg.edit_msg(text, reply_markup=markup)
        else:
            await msg.edit_msg("❌ Failed to generate menu.")
    except Exception as e:
        logger.error(f"Mention Settings Error: {e}")
        await msg.edit_msg(f"❌ Error: {str(e)[:100]}")
# ✅ NEW: Helper to generate Mention Logger Menu

async def generate_mnt_menu_async(client_id):
    """Generates the Mention Logger configuration menu for a specific client ID (Async)."""
    try:
        settings_file = "mentions_settings.json"
        if os.path.exists(settings_file):
            with open(settings_file, "r") as f:
                data = json.load(f)
        else:
            data = {"settings": {}, "global": {}}
            
        m_global = data.get("global", {})
        user_id_str = str(client_id)
        
        # Load Apply Type
        apply_type = MENTION_APPLY_TYPES.get(user_id_str, "per_account")
        
        # Load Status
        is_enabled = await get_mention_setting_safe(client_id)
        status_text = "ENABLED ✅" if is_enabled else "DISABLED ❌"
        
        # Load auto_topic
        auto_topic = m_global.get("auto_create_topic", False) # Default False
        
        # Get Bot Assist status from its own settings file
        from Main.plugins.bot.xmention_logger_bot import STORAGE_FILE as BOT_STORAGE
        bot_assist_enabled = False
        if BOT_STORAGE.exists():
            with open(BOT_STORAGE, "r") as f:
                b_data = json.load(f)
                bot_assist_enabled = b_data.get("settings", {}).get("enabled", False)
        
        bot_assist_label = "ENABLED ✅" if bot_assist_enabled else "DISABLED ❌"
        bot_assist_btn = "ON" if bot_assist_enabled else "OFF"

        ra_status = "ENABLED ✅" if REPLY_FROM_ALL_ACCESSIBLE else "DISABLED ❌"
        log_chat_id = Altruix.log_chat or "Not Configured ⚠️"

        buttons = [
             [
                 InlineKeyboardButton(f"Status: {status_text}", callback_data=f"mnt_cfg_toggle_enable_{client_id}"),
                 InlineKeyboardButton(f"Auto Topic: {'ON' if auto_topic else 'OFF'}", callback_data=f"mnt_cfg_toggle_autotopic_{client_id}")
             ],
             [
                 InlineKeyboardButton(f"Apply Type: {apply_type.upper().replace('_', ' ')}", callback_data=f"mnt_cfg_toggle_apply_{client_id}"),
                 InlineKeyboardButton(f"Bot Assist: {bot_assist_btn}", callback_data=f"mnt_cfg_toggle_botassist_{client_id}")
             ],
             [
                 InlineKeyboardButton(f"ReplyAll: {ra_status}", callback_data=f"mnt_cfg_toggle_replyall_{client_id}"),
                 InlineKeyboardButton("🔍 Filters", callback_data=f"mntf_menu_{client_id}_0")
             ],
             [
                 InlineKeyboardButton("❌ Close", callback_data="bot_controls_menu")
             ]
        ]
        
        res = (
            f"📊 **Mention Logger Configuration (ID: {client_id})**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• **Status:** {status_text}\n"
            f"• **Apply Type:** `{apply_type}`\n"
            f"• **Auto Topic:** {'ENABLED' if auto_topic else 'DISABLED'}\n"
            f"• **Reply From All:** {ra_status}\n"
            f"• **Bot Assist:** {bot_assist_label}\n"
            f"• **Log Group:** ` {log_chat_id} `\n\n"
            f"<i>Click buttons below to change settings.</i>"
        )
        return res, InlineKeyboardMarkup(buttons)
    except Exception as e:
        logger.error(f"Mention Menu Gen Error: {e}")
        return f"Error: {e}", None

@Altruix.bot.on_callback_query(filters.regex(r"^open_mentions_settings_owner$"))
@log_errors
async def open_mentions_settings_owner_handler(c: Client, cb: CallbackQuery):
    try:
        from Main.utils.access_control import is_authorized_user
        if not is_authorized_user(cb.from_user.id, Altruix.config.OWNER_USERS_ID, Altruix.config.SUDO_USERS_ID):
            return await cb.answer(Altruix.get_string("ACCESS_DENIED"), show_alert=True)
            
        await cb.answer()
        owner_id = Altruix.config.OWNER_USERS_ID
        text, markup = await generate_mnt_menu_async(owner_id)
        if markup:
            await Altruix.edit_cb(cb, text, reply_markup=markup, parse_mode=enums.ParseMode.HTML)
    except Exception as e:
        logger.error(f"Open Mentions Error: {e}")
        await cb.answer(f"Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^mnt_cfg_(toggle_enable|toggle_replyall|toggle_autotopic|toggle_apply|toggle_botassist)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def mnt_config_callback(c: Client, cb: CallbackQuery):
    try:
        action = cb.matches[0].group(1)
        client_id = int(cb.matches[0].group(2)) if cb.matches[0].group(2) else Altruix.config.OWNER_USERS_ID
        
        settings_file = "mentions_settings.json"
        if os.path.exists(settings_file):
             with open(settings_file, "r") as f: data = json.load(f)
        else: data = {"settings": {}, "global": {}}
        
        if "global" not in data: data["global"] = {}
        
        text = "Setting Updated"
        
        if action == "toggle_enable":
            curr = await get_mention_setting_safe(client_id)
            await save_mention_setting_safe(client_id, not curr)
            text = f"✅ Mentions {'ENABLED' if not curr else 'DISABLED'}"
            
        elif action == "toggle_replyall":
            global REPLY_FROM_ALL_ACCESSIBLE
            REPLY_FROM_ALL_ACCESSIBLE = not REPLY_FROM_ALL_ACCESSIBLE
            await cache_set("reply_from_all_accessible", REPLY_FROM_ALL_ACCESSIBLE, 86400 * 30)
            text = f"🔄 Reply From All: {'ACCESSIBLE' if REPLY_FROM_ALL_ACCESSIBLE else 'RESTRICTED'}"
            
        elif action == "toggle_botassist":
            from Main.plugins.bot.xmention_logger_bot import STORAGE_FILE as BOT_STORAGE
            if BOT_STORAGE.exists():
                async with aiofiles.open(BOT_STORAGE, "r") as f:
                    content = await f.read()
                    b_data = json.loads(content)
                
                current = b_data.get("settings", {}).get("enabled", False)
                new_status = not current
                
                if "settings" not in b_data: b_data["settings"] = {}
                b_data["settings"]["enabled"] = new_status
                
                async with aiofiles.open(BOT_STORAGE, "w") as f:
                    await f.write(json.dumps(b_data, indent=2))
                
                text = f"🔄 Bot Assist: {'ENABLED' if new_status else 'DISABLED'}"
            else:
                text = "❌ Bot Assist settings not found"

        elif action == "toggle_autotopic":
            curr = data["global"].get("auto_create_topic", False) # Default False
            data["global"]["auto_create_topic"] = not curr
            text = f"🔄 Auto Topic: {'ENABLED' if not curr else 'DISABLED'}"
            
        elif action == "toggle_apply":
            curr = MENTION_APPLY_TYPES.get(str(client_id), "per_account")
            new_type = "global" if curr == "per_account" else "per_account"
            MENTION_APPLY_TYPES[str(client_id)] = new_type
            data["apply_types"] = MENTION_APPLY_TYPES
            text = f"🔄 Apply Type for {client_id}: {new_type.upper().replace('_', ' ')}"
            
        # Save JSON
        with open(settings_file, "w") as f:
            json.dump(data, f, indent=2)
            
        await save_local_storage() # Sync
        await cb.answer(text)
        
        # Refresh Menu
        res_text, markup = await generate_mnt_menu_async(client_id)
        if markup:
            await Altruix.edit_cb(cb, res_text, reply_markup=markup, parse_mode=enums.ParseMode.HTML)
        
    except Exception as e:
        await cb.answer(f"Cfg Error: {e}", show_alert=True)
        logger.error(f"MNT Config Callback Error: {e}")

# ============================================================================
# 🔥 MENTION DETECTION HANDLER - DIUPDATE DENGAN CACHE
# ============================================================================
@Altruix.on_message(
    filters.mentioned & filters.group
)
@log_errors
async def send_mention_log_handler(c: Client, m: RawMessage):
    """
    Core handler for processing and logging new mentions found in groups.
    Handles media forwarding, topic creation, and sends detailed notifications.
    Stores mention data in both persistent and memory cache for later reply processing.
    """
    try:
        # ✅ SAFETY CHECK: Basic message validity
        if not m or not hasattr(m, 'chat') or not m.chat:
            return

        # ✅ FIX: Ignore mentions in log group to prevent auto-reply loop
        if Altruix.log_chat and m.chat.id == Altruix.log_chat:
            logger.debug(f"⚠️ Ignoring mention in log group {m.chat.id}")
            return
        
        msg_key = f"{m.chat.id}_{m.id}"
        
        # ✅ NEW: Handle Bot Assistant Specific Filtering
        # If the sender is our own bot assistant, check if 'Bot Assist' is disabled
        sender = m.from_user
        is_bot_assistant = (sender and sender.id == Altruix.bot_info.id)
        if is_bot_assistant:
            from Main.plugins.bot.xmention_logger_bot import STORAGE_FILE as BOT_STORAGE
            bot_assist_enabled = False
            if BOT_STORAGE.exists():
                try:
                    with open(BOT_STORAGE, "r") as f:
                        b_data = json.load(f)
                        bot_assist_enabled = b_data.get("settings", {}).get("enabled", False)
                except:
                    pass
            
            if not bot_assist_enabled:
                logger.debug(f"Mention: Skipping mention from Bot Assistant (Bot Assist is DISABLED)")
                return
        
        # Cek apakah sudah ada di cache PERSISTEN
        if await check_mention_in_cache(msg_key):
            cache_data = await get_mention_from_cache(msg_key)
            if cache_data and cache_data.get("log_msg_id"):
                logger.debug(f"⚠️ Mention {msg_key} already processed (from persistent cache)")
                return
        
        # Juga cek di in-memory cache (backward compatibility)
        if msg_key in MENTION_LOG_CACHE and MENTION_LOG_CACHE[msg_key].get("log_msg_id"):
            logger.debug(f"⚠️ Mention {msg_key} already processed (from memory cache)")
            return
            
        # Cek apakah log_chat dikonfigurasi
        if not Altruix.log_chat:
            # Attempt fallback: read from environment again
            fallback_chat = await Altruix.config.get_env("LOG_CHAT_ID")
            if fallback_chat:
                Altruix.log_chat = Altruix.config.digit_wrap(fallback_chat)
                logger.info(f"Fallback LOG_CHAT_ID set to {Altruix.log_chat} from environment")
            else:
                logger.error("LOG_CHAT not configured, cannot send mention notifications. Please set LOG_CHAT_ID.")
                return
            
        # REMOVED: Unnecessary assistant bot check that blocks the entire logger
        # bot = Altruix.bot_manager.get_bot(c.me.id)
        # try:
        #     await bot.get_chat(Altruix.log_chat)
        # except Exception as chat_err:
        #     logger.error(f"Cannot access log chat {Altruix.log_chat}: {chat_err}")
        #     return
            
        client_id = c.me.id
        
        # Cek apakah mention notifications enabled
        is_enabled = await get_mention_setting_safe(client_id)
        if not is_enabled:
            logger.debug(f"Mention logic disabled for {client_id}")
            return

        # Check auto_log and filters from mentions_settings.json
        try:
            settings_file = get_db_path("mentions_settings.json")
            if os.path.exists(settings_file):
                with open(settings_file, "r") as f:
                    m_settings = json.load(f)
                
                # Check global settings first
                m_global = m_settings.get("global", {})
                if not m_global.get("auto_log", True):
                    logger.debug(f"Mention auto-log disabled globally")
                    return
                
                # Identify message type for filtering
                m_type = "text"
                if m.photo: m_type = "photo"
                elif m.video: m_type = "video"
                elif m.document: m_type = "document"
                elif m.audio: m_type = "audio"
                elif m.voice: m_type = "voice"
                elif m.sticker: m_type = "sticker"
                elif m.animation: m_type = "animation"
                elif m.video_note: m_type = "video_note"
                elif m.contact: m_type = "contact"
                elif m.location: m_type = "location"
                elif m.venue: m_type = "venue"
                elif m.game: m_type = "game"
                elif m.poll: m_type = "poll"
                elif m.dice: m_type = "dice"

                # ✅ NEW: Check per-account source-specific filters (User vs Bot)
                is_bot = (m.from_user.is_bot if m.from_user else False)
                source_key = "from_bot" if is_bot else "from_user"
                
                user_settings = m_settings.get("settings", {}).get(str(client_id), {})
                p_filters = user_settings.get("filters", {})
                
                # Case 1: New nested structure exists (filters -> from_user/from_bot -> type)
                if isinstance(p_filters, dict) and source_key in p_filters:
                    if not p_filters[source_key].get(m_type, True):
                        logger.debug(f"Mention filter BLOCKED {source_key} message type: {m_type}")
                        return
                        
                # Case 2: Old flat structure exists (filters -> type)
                elif isinstance(p_filters, dict) and p_filters:
                    if not p_filters.get(m_type, True):
                        logger.debug(f"Mention filter BLOCKED message type (flat structure): {m_type}")
                        return
                        
                # Case 3: Fallback to legacy global filters
                else:
                    legacy_filters = m_settings.get("filters", {})
                    if isinstance(legacy_filters, dict):
                        # Check global source-specific
                        if source_key in legacy_filters and isinstance(legacy_filters[source_key], dict):
                            if not legacy_filters[source_key].get(m_type, True):
                                logger.debug(f"Mention filter BLOCKED by global {source_key} settings")
                                return
                        # Check global flat
                        elif not legacy_filters.get(m_type, True):
                            logger.debug(f"Mention filter BLOCKED by global flat settings: {m_type}")
                            return
        except Exception as e:
            logger.error(f"Error checking mention filters: {e}")

        logger.info(f"📩 Processing mention for {c.me.first_name} ({client_id})")
        
        # Persiapan data mention
        mentioner = m.from_user
        if not mentioner:
            return

        # Custom Formatting as requested
        mentioner_id = mentioner.id
        
        # Name handling: First Last or "Blank User"
        f_name = mentioner.first_name or ""
        l_name = mentioner.last_name or ""
        full_name = f"{f_name} {l_name}".strip()
        if not full_name:
            full_name = "Blank User"
        
        # Hyperlink the name
        mentioner_hyperlink = f'<a href="tg://user?id={mentioner_id}">{html.escape(full_name)}</a>'
        
        # Username handling
        username_display = f"@{mentioner.username}" if mentioner.username else "None"
        
        # Handle message text
        message_text = m.text or m.caption or "[No text content]"
        if message_text:
            message_text = html.escape(str(message_text))[:500]
        
        # Format waktu
        try:
            if isinstance(m.date, datetime):
                mention_time = m.date.strftime("%Y-%m-%d %H:%M:%S")
            else:
                mention_time = datetime.fromtimestamp(m.date).strftime("%Y-%m-%d %H:%M:%S")
        except:
            mention_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Check for media and restricted content
        has_media = bool(m.media)
        is_restricted = getattr(m, "has_protected_content", False)
        media_size = 0
        size_str = ""
        
        if has_media:
            if m.document: media_size = m.document.file_size
            elif m.photo: media_size = m.photo.file_size
            elif m.video: media_size = m.video.file_size
            elif m.audio: media_size = m.audio.file_size
            elif m.voice: media_size = m.voice.file_size
            elif m.video_note: media_size = m.video_note.file_size
            elif m.animation: media_size = m.animation.file_size
            
            if media_size > 0:
                if media_size < 1024: size_str = f"{media_size} B"
                elif media_size < 1024*1024: size_str = f"{media_size/1024:.2f} KB"
                else: size_str = f"{media_size/(1024*1024):.2f} MB"
        
        # My Account Name (First Name only as per request example "CoolKid 369")
        my_name = c.me.first_name if c.me else "Unknown"

        # Hyperlink the my name
        my_name_hyperlink = f'<a href="tg://user?id={c.me.id}">{html.escape(my_name)}</a>'
        
        # Group handling: Title as clickable hyperlink + (ID)
        group_title_raw = m.chat.title or "Unknown Group"
        group_title = html.escape(group_title_raw)
        if m.chat.username:
            group_link = f"https://t.me/{m.chat.username}"
        else:
            # Private group: use https://t.me/c/{stripped_id}/{msg_id}
            stripped_id = str(m.chat.id).replace("-100", "", 1)
            group_link = f"https://t.me/c/{stripped_id}/{m.id}"
        group_hyperlink = f'<a href="{group_link}">{group_title}</a>'

        # Format: Group: Title(hyperlink) (ID)
        group_display = f"{group_hyperlink} ({m.chat.id})"

        log_message = (
            f"🔔 <b>Tag Detected!</b>\n\n"
            f"👤 <b>Tagged By:</b> {mentioner_hyperlink} (<code>{mentioner_id}</code>)\n"
            f"ℹ️ <b>Username:</b> {username_display}\n"
            f"🤖 <b>My Account:</b> {my_name_hyperlink} (<code>{c.me.id}</code>)\n"
            f"💬 <b>Group:</b> {group_display}\n"
            f"🕒 <b>Time:</b> {mention_time}\n"
        )
        
        if has_media:
            media_type = str(m.media.value) if m.media else "Unknown"
            log_message += f"{Altruix.get_string('LOGGER_TAG_MEDIA').format(media_type)}\n"
            if media_size > 0:
                log_message += f"{Altruix.get_string('LOGGER_TAG_SIZE').format(size_str)}\n"
            if is_restricted:
                log_message += f"{Altruix.get_string('LOGGER_TAG_RESTRICTED')}\n"
            
            # Auto-forward media to log group
            try:
                await m.forward(Altruix.log_chat)
                log_message += f"{Altruix.get_string('LOGGER_TAG_FORWARDED')}\n"
            except Exception as forward_err:
                logger.debug(f"Media forward failed: {forward_err}")

        log_message += f"{Altruix.get_string('LOGGER_TAG_MSG_HEADER')}\n<blockquote>{message_text}</blockquote>"
        
        # Buttons
        keyboard = [
            [
                InlineKeyboardButton("⚙️ Menu", callback_data=f"tags_toggle_full_{m.chat.id}_{m.id}"),
                InlineKeyboardButton(Altruix.get_string('BUTTON_GO_TO_MSG') or "🔗 Go to Message", url=m.link)
            ],
            [
                InlineKeyboardButton("💬 Chat with User", url=f"tg://user?id={mentioner_id}")
            ]
        ]
        
        # Get topic if any (use userbot to create if needed)
        # Check auto_create_topic setting
        topic_id = None
        try:
             settings_file = get_db_path("mentions_settings.json")
             if os.path.exists(settings_file):
                 with open(settings_file, "r") as f:
                     m_settings = json.load(f)
                 auto_create = m_settings.get("global", {}).get("auto_create_topic", False) # Default False
             else:
                 auto_create = False
                 
             if auto_create:
                 topic_id = await get_or_create_topic(Altruix.bot, Altruix.log_chat, "tag logger", userbot_client=c)
        except Exception as e:
             logger.debug(f"Topic creation check failed: {e}")
             topic_id = None

        # Kirim notifikasi menggunakan Main Bot (Altruix.bot) agar lebih robust
        try:
            sent_log_msg = await Altruix.bot.send_message(
                Altruix.log_chat,
                log_message,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=InlineKeyboardMarkup(keyboard),
                message_thread_id=topic_id
            )
            logger.info(f"📤 Notification sent for {msg_key}, message_id: {sent_log_msg.id}")
            
        except Exception as send_err:
            logger.error(f"Send failed to LOG_CHAT ({Altruix.log_chat}), falling back to OWNER: {send_err}")
            try:
                # Fallback to Owner if log chat fails (e.g., CHANNEL_INVALID)
                sent_log_msg = await Altruix.bot.send_message(
                    int(Altruix.config.OWNER_USERS_ID),
                    f"⚠️ <b>LOG FALLBACK</b> (Chat {Altruix.log_chat} invalid)\n\n" + log_message,
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except Exception as owner_err:
                logger.error(f"Fallback to OWNER also failed: {owner_err}")
                return
        
        # SIMPAN KE CACHE PERSISTEN (priority)
        cache_data = {
            "text": message_text,
            "log_msg_id": sent_log_msg.id,
            "client_id": client_id,
            "chat_id": m.chat.id,
            "message_id": m.id,
            "thread_id": topic_id,
            "timestamp_int": int(time.time()),
            "mentioned_by": mentioner_id,
            "name": m.chat.title or full_name,
            "group_name": m.chat.title,
            "client_name": c.me.first_name if c.me else "Unknown",
            "last_reply_id": None,
            "last_reply_chat": None
        }
        
        await save_mention_to_cache(msg_key, cache_data)
        
        # JUGA SIMPAN KE IN-MEMORY CACHE (backward compatibility)
        MENTION_LOG_CACHE[msg_key] = {
            "text": message_text,
            "log_msg_id": sent_log_msg.id,
            "client_id": client_id,
            "chat_id": m.chat.id,
            "message_id": m.id,
            "thread_id": topic_id,
            "timestamp_int": int(time.time()),
            "mentioned_by": mentioner_id,
            "name": m.chat.title or full_name,
            "group_name": m.chat.title,
            "client_name": c.me.first_name if c.me else "Unknown",
            "last_reply_id": None,
            "last_reply_chat": None
        }
        
        logger.info(f"✅ Cached mention: {msg_key} for client {client_id} ({c.me.first_name})")
        
    except Exception as e:
        logger.error(f"❌ Error in mention handler: {e}", exc_info=True)

# ============================================================================
# 🔥 EDITED MESSAGE HANDLER - DIUPDATE DENGAN CACHE
# ============================================================================
@Altruix.on_edited_message(
    filters.group & ~filters.me, group=0
)
@log_errors
async def send_mention_edit_handler(c: Client, m: RawMessage):
    """
    Updates existing mention logs when the original message is edited.
    If a message becomes a mention after editing, it initiates a new log entry.
    Ensures that only the client that originally logged the mention can update it.
    """
    try:
        # ✅ SAFETY CHECK: Basic message validity
        if not m or not hasattr(m, 'chat') or not m.chat:
            return

        if not Altruix.log_chat:
            return
            
        # ✅ FIX: Check if mention notifications enabled for this account
        if not await get_mention_setting_safe(c.me.id):
            return
            
        msg_key = f"{m.chat.id}_{m.id}"
        
        # ✅ NEW: Handle Bot Assistant Specific Filtering
        # If the sender is our own bot assistant, check if 'Bot Assist' is disabled
        sender = m.from_user
        is_bot_assistant = (sender and sender.id == Altruix.bot_info.id)
        if is_bot_assistant:
            from Main.plugins.bot.xmention_logger_bot import STORAGE_FILE as BOT_STORAGE
            bot_assist_enabled = False
            if BOT_STORAGE.exists():
                try:
                    with open(BOT_STORAGE, "r") as f:
                        b_data = json.load(f)
                        bot_assist_enabled = b_data.get("settings", {}).get("enabled", False)
                except: pass
            
            if not bot_assist_enabled:
                logger.debug(f"Mention Edit: Skipping edit from Bot Assistant (Bot Assist is DISABLED)")
                # If it was already in cache, we might want to keep it, but skip updating the log message
                return
        
        # Cek di cache PERSISTEN terlebih dahulu
        cache_data = await get_mention_from_cache(msg_key)
        
        if cache_data:
            # Only the client that originally logged it should handle the update
            if c.me.id != cache_data.get("client_id"):
                return
            log_msg_id = cache_data.get("log_msg_id")
        else:
            # Fallback ke in-memory cache
            cache = MENTION_LOG_CACHE.get(msg_key)
            if cache:
                if c.me.id != cache.get("client_id"):
                    return
                log_msg_id = cache.get("log_msg_id")
            else:
                # If not in cache, check if it's now mentioned (new mention via edit)
                if m.mentioned:
                    # Prevent multiple clients from logging the same new mention
                    if msg_key in MENTION_LOG_CACHE:
                        return
                    MENTION_LOG_CACHE[msg_key] = {"status": "logging"}
                    try:
                        return await send_mention_log_handler(c, m)
                    except:
                        MENTION_LOG_CACHE.pop(msg_key, None)
                        raise
                return

        if not log_msg_id or log_msg_id == "logging":
            return

        logger.info(f"✏️ Mention edited in {m.chat.title} ({msg_key})")

        # Re-format text (limit to 500)
        message_text = m.text or m.caption or "[No text content]"
        message_text = html.escape(str(message_text))[:500]

        # Use formatted HTML for updated content
        # Format for Edited Message (Consistent with new request)
        mentioner = m.from_user
        mentioner_id = mentioner.id if mentioner else 0
        
        # Name handling
        f_name_edit = (mentioner.first_name if mentioner else "") or ""
        l_name_edit = (mentioner.last_name if mentioner else "") or ""
        full_name_edit = f"{f_name_edit} {l_name_edit}".strip() or "Blank User"
        
        mentioner_hyperlink = f'<a href="tg://user?id={mentioner_id}">{html.escape(full_name_edit)}</a>'
        username_display_edit = f"@{mentioner.username}" if mentioner and mentioner.username else "None"
        
        my_name_edit = c.me.first_name if c.me else "Unknown"
        
        # Time handling
        try:
             mention_time = m.date.strftime("%Y-%m-%d %H:%M:%S")
        except:
             mention_time = "Unknown"
        edit_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Group handling: Title as clickable hyperlink + (ID)
        group_title_edit_raw = m.chat.title or "Unknown Group"
        group_title_edit = html.escape(group_title_edit_raw)
        if m.chat.username:
            group_link_edit = f"https://t.me/{m.chat.username}"
        else:
            # Private group: use https://t.me/c/{stripped_id}/{msg_id}
            stripped_id_edit = str(m.chat.id).replace("-100", "", 1)
            group_link_edit = f"https://t.me/c/{stripped_id_edit}/{m.id}"
        group_hyperlink_edit = f'<a href="{group_link_edit}">{group_title_edit}</a>'
        group_display_edit = f"{group_hyperlink_edit} ({m.chat.id})"

        log_content = (
            f"🔔 <b>Tag Detected! [EDITED]</b>\n\n"
            f"👤 <b>Tagged By:</b> {mentioner_hyperlink} (<code>{mentioner_id}</code>)\n"
            f"ℹ️ <b>Username:</b> {username_display_edit}\n"
            f"🤖 <b>My Account:</b> <a href='tg://user?id={c.me.id}'>{html.escape(my_name_edit)}</a> (<code>{c.me.id}</code>)\n"
            f"💬 <b>Group:</b> {group_display_edit}\n"
            f"🕒 <b>Original:</b> <code>{mention_time}</code>\n"
            f"🕒 <b>Edited:</b> <code>{edit_time}</code>\n"
            f"📄 <b>New Message:</b>\n<blockquote>{message_text}</blockquote>"
        )

        # Preserve markup by fetching original msg
        # Use Altruix.bot (Main Bot) for all operations in log chat to avoid identity mismatch
        # Fix for error 403 MESSAGE_AUTHOR_REQUIRED
        bot = Altruix.bot
        try:
            old_msg = await bot.get_messages(Altruix.log_chat, log_msg_id)
            markup = old_msg.reply_markup if old_msg else None
        except:
            markup = None

        await bot.edit_message_text(
            Altruix.log_chat,
            log_msg_id,
            log_content,
            parse_mode=enums.ParseMode.HTML,
            reply_markup=markup,
            disable_web_page_preview=True
        )
        
        # Update cache text (PERSISTEN)
        if cache_data:
            cache_data["text"] = message_text
            await save_mention_to_cache(msg_key, cache_data)
        
        # Update in-memory cache juga
        if msg_key in MENTION_LOG_CACHE:
            MENTION_LOG_CACHE[msg_key]["text"] = message_text
        
    except Exception as e:
        logger.error(f"Error in mention edit handler: {e}")

# ============================================================================
# 🔥 QUICK REACTION HANDLER - DIUPDATE DENGAN CACHE
# ============================================================================
@Altruix.bot.on_callback_query(filters.regex(r"^mentions_react_"))
@iuser_check
@log_errors
async def quick_reaction_handler(c: Client, cb: CallbackQuery):
    """Handle quick reactions from buttons."""
    try:
        # Format: mentions_react_{chat_id}_{message_id}_{emoji}
        BUTTON_STATS["react"] += 1
        log_button_press("REACT", cb.data, cb.from_user.id if cb.from_user else None)
        logger.info(f"📊 React button pressed. Total: {BUTTON_STATS['react']}")
        
        # PERBAIKAN: Parse callback data dengan benar
        # Format: mentions_react_{chat_id}_{message_id}_{emoji}
        pattern = r"mentions_react_(-?\d+)_(\d+)_(.+)"
        match = re.match(pattern, cb.data)
        
        if not match:
            logger.error(f"Invalid react callback data: {cb.data}")
            await cb.answer("❌ Invalid callback data", show_alert=True)
            return
        
        chat_id = int(match.group(1))
        message_id = int(match.group(2))
        emoji = match.group(3)
        
        # PERBAIKAN KRITIS: Validasi emoji sebelum dikirim
        if not is_valid_emoji(emoji):
            logger.error(f"Invalid emoji for reaction: {emoji}")
            await cb.answer(f"❌ Emoji '{emoji}' tidak didukung untuk reaction", show_alert=True)
            return
        
        msg_key = f"{chat_id}_{message_id}"
        logger.info(f"🔄 Processing reaction for {msg_key} with {emoji}")
        
        # CEK DI CACHE PERSISTEN TERLEBIH DAHULU
        cache_data = await get_mention_from_cache(msg_key)
        
        if not cache_data:
            # Fallback ke in-memory cache
            if msg_key not in MENTION_LOG_CACHE:
                logger.warning(f"❌ Mention not in cache: {msg_key}")
                await cb.answer(f"❌ Mention tidak ditemukan di cache ({msg_key}).", show_alert=True)
                return
            cache_data = MENTION_LOG_CACHE[msg_key]
        
        # DAPATKAN CLIENT DARI CLIENT_ID
        client_id = cache_data["client_id"]
        logger.info(f"🔍 Looking for client with ID: {client_id}")
        
        userbot_client = await get_mention_client(client_id)
        
        if not userbot_client:
            logger.warning(f"❌ Userbot client not available for ID: {client_id}")
            await cb.answer("❌ Akun yang disebut tidak tersedia atau tidak aktif.", show_alert=True)
            return
        
        try:
            # PERBAIKAN: Kirim reaction dengan error handling
            logger.info(f"⚡ Sending reaction {emoji} to {chat_id}:{message_id}")
            await userbot_client.send_reaction(chat_id, message_id, emoji)
            logger.info(f"✅ Reaction sent: {emoji} to {msg_key}")
            
            # Update tombol untuk show success
            try:
                # Cari tombol yang sesuai untuk diupdate
                if cb.message.reply_markup:
                    new_keyboard = []
                    for row in cb.message.reply_markup.inline_keyboard:
                        new_row = []
                        for button in row:
                            # Cek apakah ini tombol reaction dengan emoji yang sama
                            if button.callback_data and button.callback_data == cb.data:
                                # Buat tombol baru yang sudah direaksi
                                new_row.append(InlineKeyboardButton(
                                    f"✅ {emoji}", 
                                    callback_data="mentions_reacted"
                                ))
                            else:
                                new_row.append(button)
                        new_keyboard.append(new_row)
                    
                    # Edit hanya reply_markup saja
                    await cb.message.edit_reply_markup(
                        InlineKeyboardMarkup(new_keyboard)
                    )
                    logger.debug(f"✅ Button updated for {emoji}")
            except Exception as edit_err:
                logger.warning(f"⚠️ Could not update button: {edit_err}")
                # Tidak fatal, lanjutkan saja
            
            await cb.answer(f"✅ Bereaksi dengan {emoji}", show_alert=False)
            
        except Exception as react_err:
            error_msg = str(react_err)
            logger.error(f"❌ Reaction failed: {error_msg}")
            
            # Handle specific errors
            if "REACTION_INVALID" in error_msg:
                await cb.answer(f"❌ Emoji '{emoji}' tidak valid untuk reaction", show_alert=True)
            elif "MESSAGE_NOT_MODIFIED" in error_msg:
                await cb.answer(f"✅ Sudah direaksi dengan {emoji}", show_alert=False)
            elif "MESSAGE_ID_INVALID" in error_msg or "msg_id" in error_msg.lower():
                await cb.answer(f"❌ Pesan tidak ditemukan atau sudah dihapus", show_alert=True)
            elif "CHAT_ADMIN_REQUIRED" in error_msg:
                await cb.answer(f"❌ Tidak punya akses admin di grup tersebut", show_alert=True)
            else:
                await cb.answer(f"❌ Gagal: {error_msg[:50]}", show_alert=True)
            
    except Exception as e:
        logger.error(f"❌ Quick reaction error: {e}", exc_info=True)
        await cb.answer("❌ Terjadi kesalahan.", show_alert=True)

# ============================================================================
# 🔥 REPLY FROM ALL HANDLER - DIUPDATE DENGAN CACHE
# ============================================================================
@Altruix.bot.on_callback_query(filters.regex(r"^mentions_replyall_"))
@iuser_check
@log_errors
async def start_reply_from_all(c: Client, cb: CallbackQuery):
    """Memulai proses reply-from-all for all user."""
    try:
        # 1. Log Aktivitas
        BUTTON_STATS["reply_all"] += 1
        log_button_press("REPLY_ALL", cb.data, cb.from_user.id if cb.from_user else None)
        
        if not REPLY_FROM_ALL_ACCESSIBLE:
            await cb.answer("❌ Fitur Reply From All sedang dinonaktifkan oleh Owner.", show_alert=True)
            return

        logger.info(f"📊 Reply All button pressed. Total: {BUTTON_STATS['reply_all']}")
        
        # 2. Parse Data dengan Aman
        # Format: mentions_replyall_{chat_id}_{message_id}
        pattern = r"mentions_replyall_(-?\d+)_(\d+)"
        match = re.match(pattern, cb.data)
        
        if not match:
            logger.error(f"❌ Invalid replyall callback data: {cb.data}")
            await cb.answer("❌ Data tombol tidak valid", show_alert=True)
            return
        
        chat_id = int(match.group(1))
        message_id = int(match.group(2))
        msg_key = f"{chat_id}_{message_id}"
        
        # 3. Validasi User
        user_id = cb.from_user.id if cb.from_user else None
        if not user_id:
            await cb.answer("❌ User tidak dikenal", show_alert=True)
            return
        
        # 4. Cek Rate Limit (Anti-Spam) - GUNAKAN CACHE
        today = datetime.now().strftime("%Y%m%d")
        user_count = await get_user_reply_count(user_id, today)
        
        if user_count >= USER_REPLY_LIMIT:
            logger.warning(f"⚠️ User {user_id} hit rate limit for today")
            await cb.answer(
                f"❌ Batas reply tercapai ({USER_REPLY_LIMIT}x per hari). Coba lagi besok.",
                show_alert=True
            )
            return
        
        # 5. Cek Ketersediaan Cache - PERSISTEN CACHE DULU
        cache_data = await get_mention_from_cache(msg_key)
        
        if not cache_data:
            # Fallback ke in-memory cache
            if msg_key not in MENTION_LOG_CACHE:
                logger.warning(f"❌ Mention not in cache: {msg_key}")
                await cb.answer(f"❌ Data mention kadaluarsa atau hilang ({msg_key}).", show_alert=True)
                return
            cache_data = MENTION_LOG_CACHE[msg_key]
        
        # 6. Dapatkan Client Userbot
        client_id = cache_data["client_id"]
        logger.info(f"🔍 Looking for client with ID: {client_id}")
        
        mentioned_client = await get_mention_client(client_id)
        
        if not mentioned_client:
            logger.warning(f"❌ Userbot client not available for ID: {client_id}")
            await cb.answer("❌ Akun userbot tidak aktif/offline.", show_alert=True)
            return
        
        # 7. Generate Waiting ID unik
        waiting_id = f"replyall_{int(time.time())}_{cb.id}"
        waiting_data = {
            "chat_id": chat_id,
            "message_id": message_id,
            "client_id": client_id,
            "log_msg_id": cb.message.id,
            "user_id": user_id,
            "timestamp_int": int(time.time()),
            "callback_message_id": cb.message.id,
            "is_reply_all": True,
            "waiting_id": waiting_id,
            "msg_key": msg_key
        }
        
        # SIMPAN KE CACHE PERSISTEN
        await save_waiting_reply(waiting_id, waiting_data)
        
        # SIMPAN JUGA KE IN-MEMORY (backward compatibility)
        REPLY_AS_MENTIONED_WAITING[waiting_id] = waiting_data
        
        logger.info(f"⏳ Reply From All waiting for {msg_key}, user: {user_id}, waiting_id: {waiting_id}")
        
        # 8. Kirim Instruksi ke User
        try:
            user_mention = cb.from_user.mention(style=enums.ParseMode.HTML) if cb.from_user else "User"
            client_name = mentioned_client.me.first_name if mentioned_client.me else "Unknown"
            
            instruction_msg = await cb.message.reply(
                f"✉️ <b>Kirim Balasan untuk Semua Session</b>\n\n"
                f"Halo <b>{user_mention}</b>!\n"
                f"Pesan Anda akan dikirim dari <b>SEMUA</b> akun userbot yang aktif.\n"
                f"Silakan balas pesan ini dengan teks balasan Anda.",
                parse_mode=enums.ParseMode.HTML
            )
            # Simpan instruction_msg_id agar bisa direply langsung
            waiting_data["instruction_msg_id"] = instruction_msg.id
            await save_waiting_reply(waiting_id, waiting_data)
            REPLY_AS_MENTIONED_WAITING[waiting_id] = waiting_data
            SessionManager.save() # ✅ Save to persistent storage
            
            await cb.answer("Silakan kirimkan balasan Anda.", show_alert=False)
            
        except Exception as e:
            logger.error(f"❌ Reply All instruction failed: {e}")
            # Hapus dari cache jika gagal
            await delete_waiting_reply(waiting_id)
            if waiting_id in REPLY_AS_MENTIONED_WAITING:
                del REPLY_AS_MENTIONED_WAITING[waiting_id]
            await cb.answer("❌ Gagal mengirim pesan instruksi.", show_alert=True)
            return

    except Exception as e:
        logger.error(f"❌ Reply From All logic error: {e}", exc_info=True)
        await cb.answer(f"❌ Terjadi kesalahan sistem: {str(e)[:50]}", show_alert=True)

# ============================================================================
# 🔥 REPLY AS MENTIONED HANDLER - DIUPDATE DENGAN CACHE
# ============================================================================
@Altruix.bot.on_callback_query(filters.regex(r"^mentions_reply_(-?\d+)_(\d+)"))
@iuser_check
@log_errors
async def mentions_direct_reply_callback(c: Client, cb: CallbackQuery):
    """Langsung memulai proses reply untuk mention tanpa menu perantara."""
    try:
        from Main.utils.access_control import check_reply_access
        has_access, reason = check_reply_access(
                cb.from_user, get_shared_reply_mode(), Altruix.config.OWNER_USERS_ID, Altruix.config.SUDO_USERS_ID
            )
        if not has_access:
            return await cb.answer(reason, show_alert=True)
            
        data = cb.data.split("_")
        chat_id, msg_id = int(data[2]), int(data[3])
        msg_key = f"{chat_id}_{msg_id}"
        waiting_id = f"mentions_r_{cb.id}"
        
        # 1. Dapatkan Data Mention dari Cache
        cache_data = await get_mention_from_cache(msg_key)
        if not cache_data:
            # Fallback ke memory cache
            cache_data = MENTION_LOG_CACHE.get(msg_key)
            
        if not cache_data:
             return await cb.answer("❌ Data mention tidak ditemukan di cache.", show_alert=True)
             
        client_id = cache_data.get("client_id")
        mentioned_client = await get_mention_client(client_id)
        if not mentioned_client:
             return await cb.answer("❌ Akun userbot tidak aktif.", show_alert=True)
             
        # 2. Persiapkan data waiting
        log_msg_id = cache_data.get("log_msg_id") or cb.message.id
        thread_id = cache_data.get("thread_id") or getattr(cb.message, "message_thread_id", None)
        waiting_data = {
            "chat_id": chat_id,
            "message_id": msg_id,
            "client_id": client_id,
            "log_msg_id": log_msg_id,
            "thread_id": thread_id,
            "user_id": cb.from_user.id,
            "is_reply_all": False,
            "msg_key": msg_key
        }
        REPLY_AS_MENTIONED_WAITING[waiting_id] = waiting_data
        await save_waiting_reply(waiting_id, waiting_data)
        
        # 3. Kirim Instruksi (Direct)
        client_name = mentioned_client.me.first_name if mentioned_client.me else "Unknown"
        user_mention = cb.from_user.mention(style=enums.ParseMode.HTML) if cb.from_user else "User"
        
        bot = Altruix.bot
        instr = await bot.send_message(
            Altruix.log_chat,
            f"✉️ <b>Input Balasan Mention</b> (via {client_name})\n\n"
            f"Halo <b>{user_mention}</b>!\n"
            f"Silakan balas pesan ini dengan teks balasan Anda.\n"
            f"Pesan akan dikirim ke chat ID <code>{chat_id}</code>.",
            reply_to_message_id=log_msg_id,
            parse_mode=enums.ParseMode.HTML
        )
        
        # Simpan instruction_msg_id agar bisa direply langsung
        waiting_data["instruction_msg_id"] = instr.id
        await save_waiting_reply(waiting_id, waiting_data)
        REPLY_AS_MENTIONED_WAITING[waiting_id] = waiting_data
        await cb.answer("Silakan kirim balasan Anda.")
    except Exception as e:
        logger.error(f"Mentions direct reply error: {e}")
        await cb.answer(f"❌ Error: {e}", show_alert=True)


# Note: Reply input handling, confirmation, and cancellation are now centralizing in xreply_manager.py
# to avoid conflicts and ensure a robust experience across all log topics.

# Note: Buttons logic for react, others, and mention save are kept below as they are logger-specific.

# ============================================================================
# 🔥 ALREADY REACTED HANDLER
# ============================================================================
@Altruix.bot.on_callback_query(filters.regex(r"^mentions_reacted$"))
@iuser_check
@log_errors
async def already_reacted_handler(c: Client, cb: CallbackQuery):
    """Handler untuk tombol yang sudah direaksi."""
    log_button_press("ALREADY_REACTED", cb.data, cb.from_user.id if cb.from_user else None)
    await cb.answer("✅ Sudah direaksi sebelumnya", show_alert=False)

# ============================================================================
# 🔥 TEST BUTTONS HANDLER
# ============================================================================
@Altruix.bot.on_callback_query(filters.regex(r"^test_mentions_"))
@iuser_check
@log_errors
async def test_buttons_handler_bot(c: Client, cb: CallbackQuery):
    """Handler untuk tombol test dari bot."""
    try:
        pattern = r"test_mentions_(.+)_(-?\d+)_(\d+)"
        match = re.match(pattern, cb.data)
        
        if not match:
            await cb.answer("❌ Invalid test button", show_alert=True)
            return
        
        action = match.group(1)
        chat_id = int(match.group(2))
        message_id = int(match.group(3))
        
        if action == "reply":
            # Simulasikan tombol reply
            await mentions_direct_reply_callback(c, cb)
        elif action == "replyall":
            # Simulasikan tombol reply all
            await start_reply_from_all(c, cb)
        elif action == "react":
            # Simulasikan tombol react
            fake_cb_data = f"mentions_react_{chat_id}_{message_id}_👍"
            cb.data = fake_cb_data
            await quick_reaction_handler(c, cb)
            await cb.answer("✅ Reaction sent!", show_alert=False)
        elif action == "unreact": # New action for unreact
            fake_cb_data = f"mentions_unreact_{chat_id}_{message_id}"
            cb.data = fake_cb_data
            await quick_unreact_handler(c, cb)
        else:
            await cb.answer(f"❌ Unknown test action: {action}", show_alert=True)
            
    except Exception as e:
        logger.error(f"❌ Test button handler failed: {e}")
        await cb.answer("❌ Test failed", show_alert=True)

# ============================================================================
# 🔥 UNREACT HANDLER - DIUPDATE DENGAN CACHE
# ============================================================================
@Altruix.bot.on_callback_query(filters.regex(r"^mentions_unreact_(-?\d+)_(\d+)"))
@iuser_check
@log_errors
async def quick_unreact_handler(c: Client, cb: CallbackQuery):
    """Hapus reaksi (unreact) pada pesan asli."""
    try:
        chat_id = int(cb.matches[0].group(1))
        message_id = int(cb.matches[0].group(2))
        msg_key = f"{chat_id}_{message_id}"
        
        # CEK DI CACHE PERSISTEN
        cache_data = await get_mention_from_cache(msg_key)
        
        if not cache_data:
            # Fallback ke in-memory
            if msg_key not in MENTION_LOG_CACHE:
                await cb.answer("❌ Mention tidak ditemukan di cache.", show_alert=True)
                return
            cache_data = MENTION_LOG_CACHE[msg_key]
            
        client_id = cache_data["client_id"]
        userbot_client = await get_mention_client(client_id)
        
        if not userbot_client:
            await cb.answer("❌ Akun tidak tersedia.", show_alert=True)
            return
            
        # Hapus reaction dengan mengirim list kosong atau send_reaction tanpa emoji
        await userbot_client.send_reaction(chat_id, message_id, "")
        
        await cb.answer("✅ Reaction dihapus!", show_alert=False)
        logger.info(f"🗑️ Reaction removed for {msg_key}")
        
    except Exception as e:
        logger.error(f"❌ Unreact failed: {e}")
        await cb.answer(f"❌ Gagal: {str(e)[:50]}", show_alert=True)

# ============================================================================
# 🔥 OTHERS EMOJI HANDLER
# ============================================================================
@Altruix.bot.on_callback_query(filters.regex(r"^mentions_others_(-?\d+)_(\d+)"))
@iuser_check
@log_errors
async def others_emoji_handler(c: Client, cb: CallbackQuery):
    """Tampilkan menu pilihan emoji lainnya."""
    try:
        chat_id = int(cb.matches[0].group(1))
        message_id = int(cb.matches[0].group(2))
        
        # Daftar emoji tambahan yang populer
        extra_emojis = ["👎", "👏", "😁", "🤔", "🤯", "😱", "🤬", "😢", "🤩", "🤮", "💩", "🙏"]
        
        keyboard = []
        row = []
        for i, emoji in enumerate(extra_emojis):
            row.append(InlineKeyboardButton(emoji, callback_data=f"mentions_react_{chat_id}_{message_id}_{emoji}"))
            if len(row) == 4:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
            
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=f"mentions_back_{chat_id}_{message_id}")])
        
        await cb.message.edit_reply_markup(InlineKeyboardMarkup(keyboard))
        await cb.answer("Silakan pilih emoji lainnya")
        
    except Exception as e:
        logger.error(f"❌ Others emoji handler failed: {e}")
        await cb.answer("❌ Gagal memuat emoji", show_alert=True)

# ============================================================================
# 🔥 BACK TO MAIN HANDLER
# ============================================================================
@Altruix.bot.on_callback_query(filters.regex(r"^mentions_back_(-?\d+)_(\d+)"))
@iuser_check
@log_errors
async def back_to_main_handler(c: Client, cb: CallbackQuery):
    """Kembali ke menu utama mention log."""
    try:
        chat_id = int(cb.matches[0].group(1))
        message_id = int(cb.matches[0].group(2))
        
        # Ambil link asli jika mungkin, atau biarkan kosong
        # Kita bisa coba cari url di keyboard lama
        original_link = ""
        if cb.message.reply_markup:
            for row in cb.message.reply_markup.inline_keyboard:
                for btn in row:
                    if btn.url:
                        original_link = btn.url
                        break

        reaction_buttons = [
            InlineKeyboardButton(emoji, callback_data=f"mentions_react_{chat_id}_{message_id}_{emoji}")
            for emoji in DEFAULT_REACTION_EMOJIS
        ]
        
        log_button_press = [
            InlineKeyboardButton("💾 Save to Log", callback_data=f"mentions_save_{chat_id}_{message_id}"),
            InlineKeyboardButton("🗑️ Unsend Reply", callback_data=f"mentions_unsend_{chat_id}_{message_id}")
        ]
        
        keyboard = [
            reaction_buttons[:3],
            reaction_buttons[3:6],
            [InlineKeyboardButton("➕ Choose Others", callback_data=f"mentions_others_{chat_id}_{message_id}")],
            log_button_press,
            [InlineKeyboardButton(f"🗨️ {get_permission_label(get_shared_reply_mode())}", callback_data=f"mentions_reply_menu_{chat_id}_{message_id}")],
            [InlineKeyboardButton("🗑️ Remove Reaction", callback_data=f"mentions_unreact_{chat_id}_{message_id}")]
        ]
        
        if original_link:
            keyboard.append([InlineKeyboardButton("🔗 Go to Message", url=original_link)])
        
        await cb.message.edit_reply_markup(InlineKeyboardMarkup(keyboard))
        await cb.answer()
        
    except Exception as e:
        logger.error(f"❌ Back to main handler failed: {e}")

# ============================================================================
# 🔥 SAVE TO LOG HANDLER - DIUPDATE DENGAN CACHE
# ============================================================================
@Altruix.bot.on_callback_query(filters.regex(r"^mentions_save_(-?\d+)_(\d+)"))
@iuser_check
@log_errors
async def save_mention_to_log(c: Client, cb: CallbackQuery):
    """Simpan (forward) pesan mention ke log group."""
    try:
        BUTTON_STATS["save"] += 1
        chat_id = int(cb.matches[0].group(1))
        message_id = int(cb.matches[0].group(2))
        msg_key = f"{chat_id}_{message_id}"
        
        # CEK DI CACHE PERSISTEN
        cache_data = await get_mention_from_cache(msg_key)
        
        if not cache_data:
            # Fallback ke in-memory
            if msg_key not in MENTION_LOG_CACHE:
                await cb.answer("❌ Data mention tidak ditemukan di cache.", show_alert=True)
                return
            cache_data = MENTION_LOG_CACHE[msg_key]
            
        client_id = cache_data["client_id"]
        userbot_client = await get_mention_client(client_id)
        
        if not userbot_client:
            await cb.answer("❌ Akun tidak tersedia.", show_alert=True)
            return
            
        # Get topic for tag logger
        topic_id = await get_or_create_topic(Altruix.bot, Altruix.log_chat, "tag logger", userbot_client=userbot_client)
        
        # Forward pesan ke log chat dengan topic
        await userbot_client.forward_messages(
            Altruix.log_chat, 
            chat_id, 
            message_id,
            message_thread_id=topic_id
        )
        
        await cb.answer("✅ Pesan berhasil disimpan ke Tag Logger topic!", show_alert=True)
        logger.info(f"💾 Message {msg_key} saved to log by user {cb.from_user.id}")
        
    except Exception as e:
        logger.error(f"❌ Save to log failed: {e}")
        await cb.answer(f"❌ Gagal menyimpan: {str(e)[:50]}", show_alert=True)

# ============================================================================
# 🔥 UNSEND REPLY HANDLER - DIUPDATE DENGAN CACHE
# ============================================================================
@Altruix.bot.on_callback_query(filters.regex(r"^mentions_unsend_(-?\d+)_(\d+)"))
@iuser_check
@log_errors
async def unsend_reply_handler(c: Client, cb: CallbackQuery):
    """Hapus balasan yang sebelumnya dikirim."""
    try:
        BUTTON_STATS["unsend"] += 1
        chat_id = int(cb.matches[0].group(1))
        message_id = int(cb.matches[0].group(2))
        msg_key = f"{chat_id}_{message_id}"
        
        # CEK DI CACHE PERSISTEN
        cache_data = await get_mention_from_cache(msg_key)
        
        if not cache_data:
            # Fallback ke in-memory
            if msg_key not in MENTION_LOG_CACHE:
                await cb.answer("❌ Data mention tidak ditemukan di cache.", show_alert=True)
                return
            cache_data = MENTION_LOG_CACHE[msg_key]
            
        last_reply_id = cache_data.get("last_reply_id")
        last_reply_chat = cache_data.get("last_reply_chat")
        
        if not last_reply_id:
            await cb.answer("❌ Tidak ada balasan yang terekam untuk di-unsend.", show_alert=True)
            return
            
        client_id = cache_data["client_id"]
        userbot_client = await get_mention_client(client_id)
        
        if not userbot_client:
            await cb.answer("❌ Akun tidak tersedia.", show_alert=True)
            return
            
        # Hapus balasan
        await userbot_client.delete_messages(last_reply_chat or chat_id, last_reply_id)
        
        # Update cache - PERSISTEN
        cache_data.pop("last_reply_id", None)
        cache_data.pop("last_reply_chat", None)
        await save_mention_to_cache(msg_key, cache_data)
        
        # Update in-memory juga
        if msg_key in MENTION_LOG_CACHE:
            MENTION_LOG_CACHE[msg_key].pop("last_reply_id", None)
            MENTION_LOG_CACHE[msg_key].pop("last_reply_chat", None)
        
        await cb.answer("🗑️ Balasan berhasil dihapus (unsend)!", show_alert=True)
        logger.info(f"🗑️ Reply {last_reply_id} unsend for {msg_key}")
        
    except Exception as e:
        logger.error(f"❌ Unsend failed: {e}")
        await cb.answer(f"❌ Gagal unsend: {str(e)[:50]}", show_alert=True)

# ============================================================================
# 🔥 CACHE MANAGEMENT COMMAND - BARU
# ============================================================================
@Altruix.register_on_cmd(
    ["mentions_cache"],
    cmd_help={
        "help": "Manage mention cache system",
        "example": "mentions_cache stats | mentions_cache clear | mentions_cache backend redis",
    },
    group_only=False,
    requires_input=True,
)
@iuser_check
@log_errors
async def cache_management_handler(c: Client, m: AltruixMessage):
    """Manage mention cache system."""
    msg = await m.handle_message("PROCESSING")
    user_input = m.user_input.lower().strip()
    
    try:
        if user_input == "stats":
            # Get cache statistics
            if CACHE_MANAGER_AVAILABLE and cache_manager:
                stats = await cache_manager.get_stats()
                
                stats_msg = (
                    f"📊 <b>Cache Statistics v{PLUGIN_VERSION}</b>\n\n"
                    f"<b>Backend:</b> {stats.get('backend', 'Unknown')}\n"
                    f"<b>Memory Items:</b> {stats.get('memory_items', 0)}\n"
                )
                
                if stats.get('redis_keys') is not None:
                    stats_msg += f"<b>Redis Keys:</b> {stats['redis_keys']}\n"
                elif stats.get('mongodb_count') is not None:
                    stats_msg += f"<b>MongoDB Count:</b> {stats['mongodb_count']}\n"
                elif stats.get('json_items') is not None:
                    stats_msg += f"<b>JSON Items:</b> {stats['json_items']}\n"
                    if stats.get('last_updated'):
                        stats_msg += f"<b>Last Updated:</b> {stats['last_updated']}\n"
                
                stats_msg += f"\n<b>Cache Types:</b>\n"
                stats_msg += f"• Mention Cache: {len(MENTION_LOG_CACHE)} (memory)\n"
                stats_msg += f"• Waiting Replies: {len(REPLY_AS_MENTIONED_WAITING)} (memory)\n"
                
                await safe_edit_message(
                    c,
                    m.chat.id,
                    msg.id,
                    stats_msg,
                    parse_mode=enums.ParseMode.HTML
                )
            else:
                await msg.edit_msg("❌ Cache manager not available")
                
        elif user_input == "clear":
            # Clear all cache
            if CACHE_MANAGER_AVAILABLE and cache_manager:
                await cache_manager.clear()
                await msg.edit_msg("✅ All persistent cache cleared")
            else:
                # Clear fallback cache
                MENTION_LOG_CACHE.clear()
                REPLY_AS_MENTIONED_WAITING.clear()
                await msg.edit_msg("✅ Fallback cache cleared")
                
        elif user_input.startswith("backend"):
            # Change cache backend
            backend = user_input.replace("backend", "").strip()
            await msg.edit_msg(
                f"⚠️ To change cache backend to {backend}, set environment variable:\n\n"
                f"For Redis: <code>REDIS_URL=redis://your-redis-url</code>\n"
                f"For MongoDB: <code>MONGO_URI=mongodb://your-mongo-url</code>\n\n"
                f"Then restart Altruix.",
                parse_mode=enums.ParseMode.HTML
            )
                
        elif user_input == "cleanup":
            # Cleanup expired entries
            if CACHE_MANAGER_AVAILABLE and cache_manager:
                cleaned = await cache_manager.cleanup_expired()
                await msg.edit_msg(f"✅ Cleaned {cleaned} expired cache entries")
            else:
                await msg.edit_msg("❌ Cache cleanup not available for this backend")
                
        elif user_input == "fix":
            # Fix cache issues
            await fix_cache_command(c, m)
            return
                
        else:
            await msg.edit_msg(
                "📚 <b>Cache Management Commands:</b>\n\n"
                "• <code>mentions_cache stats</code> - Show cache statistics\n"
                "• <code>mentions_cache clear</code> - Clear all cache\n"
                "• <code>mentions_cache cleanup</code> - Cleanup expired entries\n"
                "• <code>mentions_cache fix</code> - Fix missing cache entries\n"
                "• <code>mentions_cache backend [name]</code> - Change backend\n\n"
                "<b>Available Backends:</b>\n"
                "• memory - In-memory (volatile)\n"
                "• json - JSON file storage\n"
                "• redis - Redis database\n"
                "• mongodb - MongoDB database\n\n"
                f"<b>Current:</b> {'Cache manager available' if CACHE_MANAGER_AVAILABLE else 'Using fallback memory cache'}",
                parse_mode=enums.ParseMode.HTML
            )
            
    except Exception as e:
        logger.error(f"❌ Cache management error: {e}")
        await msg.edit_msg(f"❌ Error: {str(e)[:100]}")

# ============================================================================
# 🔥 FIX CACHE COMMAND - BARU
# ============================================================================
@Altruix.register_on_cmd(
    ["mentions_fix_cache"],
    cmd_help={
        "help": "Fix missing cache entries by reloading from log chat",
        "example": "mentions_fix_cache",
    },
    group_only=False,
    requires_input=False,
)
@iuser_check
@log_errors
async def fix_cache_command(c: Client, m: AltruixMessage):
    """Fix missing cache entries by scanning log chat."""
    msg = await m.handle_message("⏳ Scanning log chat for mentions...")
    
    try:
        if not Altruix.log_chat:
            await msg.edit_msg("❌ LOG_CHAT not configured")
            return
        
        # Scan recent messages in log chat
        found = 0
        fixed = 0
        
        async for message in Altruix.bot.search_messages(
            Altruix.log_chat,
            query="Mention Detected",
            limit=50
        ):
            try:
                if message.text and "Mention Detected" in message.text:
                    # Extract chat_id and message_id from buttons
                    if message.reply_markup:
                        for row in message.reply_markup.inline_keyboard:
                            for button in row:
                                if button.callback_data:
                                    # Parse callback data
                                    if button.callback_data.startswith("mentions_"):
                                        parts = button.callback_data.split("_")
                                        if len(parts) >= 3:
                                            try:
                                                chat_id = int(parts[1])
                                                message_id = int(parts[2])
                                                msg_key = f"{chat_id}_{message_id}"
                                                
                                                # Check if exists in cache
                                                if not await check_mention_in_cache(msg_key):
                                                    # Create cache entry
                                                    cache_data = {
                                                        "text": "Recovered from log",
                                                        "log_msg_id": message.id,
                                                        "client_id": c.me.id if c.me else 0,
                                                        "chat_id": chat_id,
                                                        "message_id": message_id,
                                                        "timestamp_int": int(time.time()),
                                                        "mentioned_by": 0,
                                                        "group_name": "Unknown",
                                                        "client_name": "Recovered"
                                                    }
                                                    
                                                    await save_mention_to_cache(msg_key, cache_data)
                                                    fixed += 1
                                                    logger.info(f"✅ Fixed cache for {msg_key}")
                                                
                                                found += 1
                                            except ValueError:
                                                continue
            except Exception as e:
                logger.error(f"Error processing message {message.id}: {e}")
        
        await msg.edit_msg(
            f"✅ <b>Cache Fix Complete</b>\n\n"
            f"• Scanned messages: {found}\n"
            f"• Fixed cache entries: {fixed}\n\n"
            f"<i>Restart mentions plugin if issues persist.</i>",
            parse_mode=enums.ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"❌ Fix cache error: {e}")
        await msg.edit_msg(f"❌ Error: {str(e)[:100]}")

# ============================================================================
# 🔥 STATUS COMMAND - DIUPDATE DENGAN INFO CACHE
# ============================================================================
@Altruix.register_on_cmd(
    ["mentions_status"],
    cmd_help={
        "help": "Check mention plugin status",
        "example": "mentions_status",
    },
    group_only=False,
    requires_input=False,
)
@iuser_check
@log_errors
async def status_command_handler(c: Client, m: AltruixMessage):
    """Check plugin status with cache info."""
    msg = await m.handle_message("PROCESSING")
    
    client_id_str = str(c.me.id)
    user_setting = await get_mention_setting_safe(c.me.id)
    
    # Hitung statistik user
    today = datetime.now().strftime("%Y%m%d")
    total_users_today = 0
    total_replies_today = 0
    
    # Get cache stats
    cache_info = "Unknown"
    if CACHE_MANAGER_AVAILABLE and cache_manager:
        stats = await cache_manager.get_stats()
        cache_info = f"{stats.get('backend', 'Unknown')}"
        if stats.get('redis_keys'):
            cache_info += f" ({stats['redis_keys']} keys)"
        elif stats.get('mongodb_count'):
            cache_info += f" ({stats['mongodb_count']} docs)"
        elif stats.get('json_items'):
            cache_info += f" ({stats['json_items']} items)"
    
    status_msg = (
        f"📊 <b>Mention Plugin Status v{PLUGIN_VERSION}</b>\n\n"
        f"<b>Settings:</b>\n"
        f"• Mentions: {'✅ ENABLED' if user_setting else '❌ DISABLED'}\n"
        f"• Reply Limit: {USER_REPLY_LIMIT}/user/day\n"
        f"• Reply From All: {'✅ ENABLED' if REPLY_FROM_ALL_ACCESSIBLE else '❌ DISABLED'}\n\n"
        f"<b>Cache System:</b>\n"
        f"• Backend: {cache_info}\n"
        f"• Memory Cache: {len(MENTION_LOG_CACHE)} items\n"
        f"• Waiting Replies: {len(REPLY_AS_MENTIONED_WAITING)} items\n\n"
        f"<b>Statistics:</b>\n"
        f"• Button React: {BUTTON_STATS['react']}\n"
        f"• Button Reply: {BUTTON_STATS['reply']}\n"
        f"• Button Reply All: {BUTTON_STATS['reply_all']}\n"
        f"• Button Confirm: {BUTTON_STATS['confirm']}\n"
        f"• Button Cancel: {BUTTON_STATS['cancel']}\n"
        f"• Button Save: {BUTTON_STATS['save']}\n"
        f"• Button Unsend: {BUTTON_STATS['unsend']}\n\n"
        f"<b>Commands:</b>\n"
        f"• <code>/mentions_cache stats</code> - Cache statistics\n"
        f"• <code>/mentions_fix_cache</code> - Fix missing cache\n"
        f"• <code>/mentions_test</code> - Test buttons\n\n"
        f"<i>Last update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"
    )
    
    await safe_edit_message(
        c,
        m.chat.id,
        msg.id,
        status_msg,
        parse_mode=enums.ParseMode.HTML
    )

# ============================================================================
# 🔥 DEBUG COMMAND
# ============================================================================
@Altruix.register_on_cmd(
    ["mentions_debug"],
    cmd_help={
        "help": "Debug button issues",
        "example": "mentions_debug",
    },
    group_only=False,
    requires_input=False,
)
@iuser_check
@log_errors
async def debug_command_handler(c: Client, m: AltruixMessage):
    """Debug button issues."""
    msg = await m.handle_message("PROCESSING")
    
    try:
        # Test semua callback pattern
        test_patterns = [
            r"^mentions_react_",
            r"^mentions_reply_",
            r"^mentions_replyall_",
            r"^mentions_confirm_",
            r"^mentions_cancel_",
            r"^mentions_reacted$",
            r"^test_mentions_"
        ]
        
        # Cek state current
        debug_msg = (
            f"🔧 <b>Button Debug Report v{PLUGIN_VERSION}</b>\n\n"
            f"<b>Registered Patterns:</b>\n"
        )
        
        for i, pattern in enumerate(test_patterns, 1):
            debug_msg += f"{i}. <code>{pattern}</code>\n"
        
        debug_msg += f"\n<b>Current State:</b>\n"
        debug_msg += f"• LOG_CHAT: <code>{Altruix.log_chat}</code>\n"
        debug_msg += f"• Bot ID: <code>{Altruix.bot_info.id if Altruix.bot_info else 'None'}</code>\n"
        debug_msg += f"• Plugin: v{PLUGIN_VERSION}\n"
        debug_msg += f"• Cache Manager: {'✅ Available' if CACHE_MANAGER_AVAILABLE else '❌ Not Available'}\n"
        debug_msg += f"• Cache Backend: {cache_info if 'cache_info' in locals() else 'Unknown'}\n"
        debug_msg += f"• Memory Cache Size: {len(MENTION_LOG_CACHE)}\n"
        debug_msg += f"• Waiting Size: {len(REPLY_AS_MENTIONED_WAITING)}\n\n"
        
        debug_msg += f"<b>Recent Cache Keys:</b>\n"
        cache_keys = list(MENTION_LOG_CACHE.keys())[:5]
        for i, key in enumerate(cache_keys, 1):
            cache_data = MENTION_LOG_CACHE[key]
            debug_msg += f"{i}. {key} (client: {cache_data.get('client_id', 'unknown')})\n"
        
        debug_msg += f"\n<b>Common Issues:</b>\n"
        debug_msg += f"1. REACTION_INVALID: Emoji tidak didukung Telegram\n"
        debug_msg += f"2. Tombol tidak merespon: Cek log untuk 'Button pressed'\n"
        debug_msg += f"3. Timeout errors: Network issue\n"
        debug_msg += f"4. Cache missing: Gunakan /mentions_fix_cache\n\n"
        
        debug_msg += f"<b>Test Commands:</b>\n"
        debug_msg += f"• <code>/mentions_test</code> - Test semua tombol\n"
        debug_msg += f"• <code>/mentions_status</code> - Status lengkap\n"
        debug_msg += f"• <code>/mentions_clear</code> - Clear cache\n"
        debug_msg += f"• <code>/mentions_cache stats</code> - Cache status\n\n"
        
        debug_msg += f"<i>Cek log file untuk detail error.</i>"
        
        await safe_edit_message(
            c,
            m.chat.id,
            msg.id,
            debug_msg,
            parse_mode=enums.ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"❌ Debug command failed: {e}")
        await msg.edit_msg(f"❌ Debug error: {str(e)[:100]}")

# ============================================================================
# 🔥 TEST BUTTONS COMMAND
# ============================================================================
# Direct flow enabled: menu skipped


@Altruix.register_on_cmd(
    ["mentions_test"],
    cmd_help={
        "help": "Test button functionality",
        "example": "mentions_test",
    },
    group_only=False,
    requires_input=False,
)
@iuser_check
@log_errors
async def test_buttons_command(c: Client, m: AltruixMessage):
    """Test semua tombol - HANYA BISA DIJALANKAN OLEH BOT!"""
    msg = await m.handle_message("PROCESSING")
    
    try:
        # Hanya bot yang bisa membuat tombol
        if c != Altruix.bot:
            await msg.edit_msg("❌ Perintah ini hanya bisa dijalankan oleh bot!")
            return
        
        # Buat tombol test dengan valid emojis
        test_chat_id = m.chat.id
        test_message_id = m.id
        
        # Tombol untuk test - menggunakan pola khusus untuk bot
        reaction_buttons = [
            InlineKeyboardButton(emoji, callback_data=f"test_mentions_react_{test_chat_id}_{test_message_id}")
            for emoji in DEFAULT_REACTION_EMOJIS[:3]  # Hanya 3 untuk test
        ]
        
        reply_button = [InlineKeyboardButton(
            "🗨️ Test Reply", 
            callback_data=f"test_mentions_reply_{test_chat_id}_{test_message_id}"
        )]
        
        reply_all_button = [InlineKeyboardButton(
            "👥 Test Reply All", 
            callback_data=f"test_mentions_replyall_{test_chat_id}_{test_message_id}"
        )]
        
        keyboard = [
            reaction_buttons,
            reply_button,
            reply_all_button,
        ]
        
        test_msg = (
            f"🔧 <b>Button Test Panel v{PLUGIN_VERSION}</b>\n\n"
            f"<b>Test semua tombol:</b>\n"
            f"1. Reaction buttons (👍, ❤️, 🔥)\n"
            f"2. Reply as Mentioned\n"
            f"3. Reply From All\n\n"
            f"<b>Status:</b>\n"
            f"• Plugin: v{PLUGIN_VERSION}\n"
            f"• Cache: {len(MENTION_LOG_CACHE)} entries\n"
            f"• Cache Manager: {'✅ Available' if CACHE_MANAGER_AVAILABLE else '❌ Not Available'}\n"
            f"• Bot: {c.me.first_name if c.me else 'Unknown'}\n\n"
            f"<i>Tekan tombol di bawah untuk testing.</i>\n"
            f"<i>Cek log untuk debugging.</i>"
        )
        
        test_message = await c.send_message(
            m.chat.id,
            test_msg,
            parse_mode=enums.ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        await msg.delete()
        
        # Tambahkan ke cache untuk testing
        test_key = f"{test_chat_id}_{test_message_id}"
        cache_data = {
            "text": "Test message",
            "log_msg_id": test_message.id,
            "client_id": c.me.id,  # Bot client ID
            "chat_id": test_chat_id,
            "message_id": test_message_id,
            "timestamp_int": int(time.time()),
            "mentioned_by": m.from_user.id if m.from_user else 0,
            "group_name": m.chat.title if m.chat else "Test",
            "client_name": c.me.first_name if c.me else "Bot"
        }
        
        # Simpan ke cache persisten
        await save_mention_to_cache(test_key, cache_data)
        
        # Simpan ke in-memory juga
        MENTION_LOG_CACHE[test_key] = cache_data
        
        logger.info(f"✅ Test panel created with message ID: {test_message.id}")
        
    except Exception as e:
        logger.error(f"❌ Test command failed: {e}")
        await msg.edit_msg(f"❌ Test error: {str(e)[:100]}")

# ============================================================================
# 🔥 CLEAR CACHE COMMAND
# ============================================================================
@Altruix.register_on_cmd(
    ["mentions_clear"],
    cmd_help={
        "help": "Clear mention plugin cache",
        "example": "mentions_clear",
    },
    group_only=False,
    requires_input=False,
)
@iuser_check
@log_errors
async def clear_cache_handler(c: Client, m: AltruixMessage):
    """Clear plugin cache."""
    msg = await m.handle_message("PROCESSING")
    
    try:
        global MENTION_LOG_CACHE, REPLY_AS_MENTIONED_WAITING, USER_REPLY_COUNTS
        
        cache_count = len(MENTION_LOG_CACHE)
        waiting_count = len(REPLY_AS_MENTIONED_WAITING)
        user_count = len(USER_REPLY_COUNTS)
        
        MENTION_LOG_CACHE.clear()
        REPLY_AS_MENTIONED_WAITING.clear()
        USER_REPLY_COUNTS.clear()
        
        # Clear persistent cache juga jika available
        if CACHE_MANAGER_AVAILABLE and cache_manager:
            await cache_manager.clear()
        
        clear_msg = (
            f"🧹 <b>Cache Cleared</b>\n\n"
            f"• Mention Cache: {cache_count} entries\n"
            f"• Waiting Replies: {waiting_count} entries\n"
            f"• User Counts: {user_count} users\n"
            f"• Persistent Cache: {'✅ Cleared' if CACHE_MANAGER_AVAILABLE else '❌ Not Available'}\n\n"
            f"✅ Semua cache telah dibersihkan."
        )
        
        await safe_edit_message(
            c,
            m.chat.id,
            msg.id,
            clear_msg,
            parse_mode=enums.ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"❌ Clear cache failed: {e}")
        await msg.edit_msg(f"❌ Clear error: {str(e)[:100]}")

# ============================================================================
# 🔥 TEST MENTION SYSTEM COMMAND
# ============================================================================
@Altruix.register_on_cmd(
    ["test_mention"],
    cmd_help={"help": "Test mention system", "example": "test_mention"},
)
@iuser_check
@log_errors
async def test_mention_system(c: Client, m: AltruixMessage):
    """Test mention system."""
    msg = await m.handle_message("PROCESSING")
    
    try:
        # Hanya bot yang bisa membuat tombol
        if c != Altruix.bot:
            await msg.edit_msg("❌ Perintah ini hanya bisa dijalankan oleh bot!")
            return
        
        # Buat tombol test
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🗨️ Test Reply", callback_data=f"test_mentions_reply_{m.chat.id}_{m.id}")],
            [InlineKeyboardButton("👥 Test Reply All", callback_data=f"test_mentions_replyall_{m.chat.id}_{m.id}")],
            [InlineKeyboardButton("👍 Test React", callback_data=f"test_mentions_react_{m.chat.id}_{m.id}")],
        ])
        
        await safe_edit_message(
            c,
            m.chat.id,
            msg.id,
            "🔧 **Test Mention System v{PLUGIN_VERSION}**\n\nTekan tombol di bawah untuk testing:",
            reply_markup=keyboard,
            parse_mode=enums.ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"❌ Test mention failed: {e}")
        await msg.edit_msg(f"❌ Test error: {str(e)[:100]}")

# ============================================================================
# 🔥 DEBUG STRUCTURE COMMAND
# ============================================================================
@Altruix.register_on_cmd(
    ["mentions_debug_structure"],
    cmd_help={
        "help": "Debug Altruix structure",
        "example": "mentions_debug_structure",
    },
    group_only=False,
    requires_input=False,
)
@iuser_check
@log_errors
async def debug_structure_handler(c: Client, m: AltruixMessage):
    """Debug Altruix structure untuk menemukan client."""
    msg = await m.handle_message("PROCESSING")
    
    try:
        debug_info = f"🔍 <b>Altruix Structure Debug v{PLUGIN_VERSION}</b>\n\n"
        
        # Cek atribut yang ada
        debug_info += "<b>Available Attributes:</b>\n"
        
        attrs = []
        for attr_name in dir(Altruix):
            if not attr_name.startswith('_'):
                attrs.append(attr_name)
        
        debug_info += f"• Total attributes: {len(attrs)}\n"
        debug_info += f"• First 20: {', '.join(attrs[:20])}\n\n"
        
        # Cek spesifik atribut
        debug_info += "<b>Specific Attributes:</b>\n"
        
        if hasattr(Altruix, 'bot'):
            debug_info += f"• bot: {type(Altruix.bot)} "
            if Altruix.bot and hasattr(Altruix.bot, 'me'):
                debug_info += f"(ID: {Altruix.bot.me.id}, Name: {Altruix.bot.me.first_name})\n"
            else:
                debug_info += "(no me attribute)\n"
        else:
            debug_info += "• bot: NOT FOUND\n"
        
        if hasattr(Altruix, 'userbot_clients'):
            debug_info += f"• userbot_clients: {type(Altruix.userbot_clients)} "
            if Altruix.userbot_clients:
                debug_info += f"(length: {len(Altruix.userbot_clients)})\n"
                # Tampilkan 3 pertama
                for i, ub in enumerate(Altruix.userbot_clients[:3]):
                    try:
                        if ub and hasattr(ub, 'me') and ub.me:
                            debug_info += f"  {i}. {ub.me.first_name} (ID: {ub.me.id})\n"
                        else:
                            debug_info += f"  {i}. Invalid or no me attribute\n"
                    except:
                        debug_info += f"  {i}. Error accessing\n"
            else:
                debug_info += "(empty)\n"
        else:
            debug_info += "• userbot_clients: NOT FOUND\n"
        
        if hasattr(Altruix, 'ubot'):
            debug_info += f"• ubot: {type(Altruix.ubot)} "
            if Altruix.ubot and hasattr(Altruix.ubot, 'me'):
                debug_info += f"(ID: {Altruix.ubot.me.id}, Name: {Altruix.ubot.me.first_name})\n"
            else:
                debug_info += "(no me attribute)\n"
        else:
            debug_info += "• ubot: NOT FOUND\n"
        
        if hasattr(Altruix, 'clients'):
            debug_info += f"• clients: {type(Altruix.clients)} "
            if Altruix.clients:
                if isinstance(Altruix.clients, dict):
                    debug_info += f"(dict, keys: {len(Altruix.clients)})\n"
                    # Tampilkan 3 keys pertama
                    for i, key in enumerate(list(Altruix.clients.keys())[:3]):
                        debug_info += f"  {i}. key: {key}\n"
                elif isinstance(Altruix.clients, list):
                    debug_info += f"(list, length: {len(Altruix.clients)})\n"
            else:
                debug_info += "(empty)\n"
        else:
            debug_info += "• clients: NOT FOUND\n"
        
        debug_info += f"\n<b>Cache Manager Status:</b>\n"
        debug_info += f"• Available: {'✅ Yes' if CACHE_MANAGER_AVAILABLE else '❌ No'}\n"
        debug_info += f"• Manager: {cache_manager}\n"
        
        debug_info += f"\n<b>Current Client:</b>\n"
        debug_info += f"• ID: {c.me.id if c.me else 'N/A'}\n"
        debug_info += f"• Name: {c.me.first_name if c.me else 'N/A'}\n"
        debug_info += f"• Type: {type(c)}\n"
        
        debug_info += f"\n<b>Cache Info:</b>\n"
        debug_info += f"• MENTION_LOG_CACHE: {len(MENTION_LOG_CACHE)} entries\n"
        debug_info += f"• REPLY_AS_MENTIONED_WAITING: {len(REPLY_AS_MENTIONED_WAITING)} entries\n"
        
        await safe_edit_message(
            c,
            m.chat.id,
            msg.id,
            debug_info,
            parse_mode=enums.ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"❌ Debug structure failed: {e}")
        await msg.edit_msg(f"❌ Debug error: {str(e)[:100]}")

# ============================================================================
# 🔥 MENTION TEST HANDLER COMMAND
# ============================================================================
@Altruix.register_on_cmd(
    ["mentions_test_handler"],
    cmd_help={
        "help": "Test reply handler functionality",
        "example": "mentions_test_handler",
    },
    group_only=False,
    requires_input=False,
)
@iuser_check
@log_errors
async def test_handler_command(c: Client, m: AltruixMessage):
    """Test handler functionality."""
    msg = await m.handle_message("PROCESSING")
    
    try:
        # Hanya bot yang bisa testing
        if c != Altruix.bot:
            await msg.edit_msg("❌ Perintah ini hanya bisa dijalankan oleh bot!")
            return
        
        # Buat pesan test
        test_msg = await c.send_message(
            m.chat.id,
            "📝 **Test Handler**\n\n"
            "1. Balas pesan ini dengan teks apapun\n"
            "2. Cek log untuk melihat apakah handler terpicu\n"
            "3. Handler seharusnya merespon dengan pesan ini",
            parse_mode=enums.ParseMode.MARKDOWN
        )
        
        # Buat waiting entry dummy untuk testing
        waiting_id = f"test_handler_{int(time.time())}_{test_msg.id}"
        waiting_data = {
            "chat_id": m.chat.id,
            "message_id": test_msg.id,
            "client_id": c.me.id,
            "log_msg_id": test_msg.id,
            "user_id": m.from_user.id if m.from_user else None,
            "timestamp_int": int(time.time()),
            "callback_message_id": test_msg.id,
            "is_reply_all": False,
            "waiting_id": waiting_id,
            "msg_key": f"{m.chat.id}_{test_msg.id}",
            "instruction_msg_id": test_msg.id  # 🔥 INI PENTING: instruction_msg_id harus sama dengan ID pesan ini
        }
        
        # Simpan ke memory
        REPLY_AS_MENTIONED_WAITING[waiting_id] = waiting_data
        
        await msg.edit_msg(
            f"✅ **Test Handler Created**\n\n"
            f"• Test Message ID: `{test_msg.id}`\n"
            f"• Waiting ID: `{waiting_id}`\n"
            f"• Instruction Msg ID: `{test_msg.id}`\n\n"
            f"**Silakan balas pesan test dengan teks apapun!**",
            parse_mode=enums.ParseMode.MARKDOWN
        )
        
        logger.info(f"✅ [TEST] Handler test created: waiting_id={waiting_id}, instruction_msg_id={test_msg.id}")
        
    except Exception as e:
        logger.error(f"❌ [TEST] Handler test failed: {e}")
        await msg.edit_msg(f"❌ Test error: {str(e)[:100]}")


# ============================================================================
# 🔥 CLEANUP TASK untuk cache
# ============================================================================
async def cleanup_old_entries():
    """Bersihkan cache dan waiting list yang sudah lama."""
    while True:
        try:
            current_time = time.time()
            
            # Clean old in-memory cache (2 hours)
            expired_cache = []
            for key, data in MENTION_LOG_CACHE.items():
                if current_time - data.get("timestamp_int", 0) > 7200:
                    expired_cache.append(key)
            
            for key in expired_cache[:50]:
                try:
                    del MENTION_LOG_CACHE[key]
                except:
                    pass
            
            # Clean old waiting (1 hour)
            expired_waiting = []
            for key, data in REPLY_AS_MENTIONED_WAITING.items():
                if current_time - data.get("timestamp_int", 0) > 3600:
                    expired_waiting.append(key)
            
            for key in expired_waiting[:20]:
                try:
                    del REPLY_AS_MENTIONED_WAITING[key]
                except:
                    pass
                
            if expired_cache or expired_waiting:
                logger.info(f"🧹 Cleaned {len(expired_cache)} cache and {len(expired_waiting)} waiting entries")
                
                # ✅ NOTIF LOG
                try:
                    if getattr(Altruix.config, "CACHE_LOG_ENABLED", False) and Altruix.log_chat:
                        await Altruix.bot.send_message(
                            chat_id=Altruix.log_chat,
                            text=f"🧹 <b>Cache Cleaner Triggered</b>\n\n• Cleaned: <code>{len(expired_cache)}</code> cache entries\n• Waiting: <code>{len(expired_waiting)}</code> entries",
                            parse_mode=enums.ParseMode.HTML
                        )
                except Exception:
                    pass
                
        except Exception as e:
            logger.error(f"❌ Cleanup error: {e}")
        
        await asyncio.sleep(600)

# Start cleanup task
asyncio.create_task(cleanup_old_entries())
logger.info("Cleanup task started")

# ============================================================================
# 🔥 CACHE CLEANUP TASK
# ============================================================================
async def cache_cleanup_task():
    """Regular cache cleanup task."""
    logger.info("♻️ Starting cache cleanup task loop...")
    while True:
        try:
            # Cleanup expired waiting replies di cache persisten
            if CACHE_MANAGER_AVAILABLE and cache_manager:
                try:
                    # Check if method exists before calling (backward compatibility/safety)
                    if hasattr(cache_manager, 'cleanup_expired'):
                        cleaned = await cache_manager.cleanup_expired()
                        if cleaned > 0:
                            logger.info(f"🧹 CacheManager cleaned {cleaned} expired entries")
                    else:
                        logger.warning("⚠️ CacheManager missing cleanup_expired method")
                except Exception as e:
                    logger.error(f"❌ Error calling cache_manager.cleanup_expired: {e}")
            
            # Juga cleanup fallback cache
            now = time.time()
            expired_keys = []
            
            # Use list(keys) to avoid dictionary changed size during iteration
            for key, entry in list(MENTION_LOG_CACHE.items()):
                try:
                    # Parse expires_at if it's string
                    expires_at = entry.get("expires_at", 0)
                    if isinstance(expires_at, str):
                        # Simple check, assumes isoformat or similar if string
                        # For simplicity in fallback, maybe skip string parsing if complex
                        pass 
                    elif isinstance(expires_at, (int, float)):
                        if expires_at < now and expires_at > 0:
                            expired_keys.append(key)
                except: continue
            
            for key in expired_keys[:100]:  # Limit per cycle
                MENTION_LOG_CACHE.pop(key, None)
            
            if expired_keys:
                logger.info(f"🧹 Cleaned {len(expired_keys)} expired fallback cache entries")
                await _save_fallback_cache()
                
        except Exception as e:
            logger.error(f"❌ Cache cleanup task error: {e}")
        
        await asyncio.sleep(300)  # Run every 5 minutes


# ============================================================================
# 🔥 TOGGLE MENU HANDLER - NEW
# ============================================================================
@Altruix.bot.on_callback_query(filters.regex(r"^tags_toggle_(full|compact)_"))
@iuser_check
@log_errors
async def tags_toggle_menu_callback(c: Client, cb: CallbackQuery):
    """Toggle between compact and full menu for tag notifications."""
    try:
        data = cb.data.split("_")
        mode, chat_id, msg_id = data[2], int(data[3]), int(data[4])
        
        # Get cache to retrieve user_id and check for media
        msg_key = f"{chat_id}_{msg_id}"
        cache_data = await get_mention_from_cache(msg_key)
        
        if mode == "full":
            # Get user_id from cache - Fix NoneType error
            mentioner_id = 0
            if cache_data and cache_data.get("mentioner_id"):
                try:
                    mentioner_id = int(cache_data.get("mentioner_id"))
                except:
                   mentioner_id = 0
            
            # Build full menu with all buttons
            reaction_buttons = [
                InlineKeyboardButton(emoji, callback_data=f"mentions_react_{chat_id}_{msg_id}_{emoji}")
                for emoji in DEFAULT_REACTION_EMOJIS
            ]
            
            keyboard = [
                reaction_buttons[:3],
                reaction_buttons[3:6],
                [
                    InlineKeyboardButton("➕ Others", callback_data=f"mentions_others_{chat_id}_{msg_id}"),
                    InlineKeyboardButton("🗑️ Remove React", callback_data=f"mentions_unreact_{chat_id}_{msg_id}")
                ],
                [
                    InlineKeyboardButton(f"🗨️ {get_permission_label(get_shared_reply_mode())}", callback_data=f"mentions_reply_{chat_id}_{msg_id}"),
                    InlineKeyboardButton("💾 Save", callback_data=f"mentions_save_{chat_id}_{msg_id}")
                ],
                [
                    InlineKeyboardButton("🗑️ Unsend", callback_data=f"mentions_unsend_{chat_id}_{msg_id}")
                ],
                [
                    InlineKeyboardButton("💬 Chat with User", url=f"tg://user?id={mentioner_id}"),
                ],
                [
                    InlineKeyboardButton("📤 Send Message", callback_data=f"tags_send_msg_{chat_id}_{msg_id}_{mentioner_id}"),
                    InlineKeyboardButton("🚫 Block User", callback_data=f"tags_block_{chat_id}_{msg_id}_{mentioner_id}")
                ],
                [
                    InlineKeyboardButton("⚙️ Hide Full Menu", callback_data=f"tags_toggle_compact_{chat_id}_{msg_id}"),
                    InlineKeyboardButton("🔗 Go to Message", url=f"https://t.me/c/{str(chat_id)[4:]}/{msg_id}")
                ]
            ]
        else:
            # Compact menu
            keyboard = [
                [
                    InlineKeyboardButton("⚙️ Show Full Menu", callback_data=f"tags_toggle_full_{chat_id}_{msg_id}"),
                    InlineKeyboardButton("🔗 Go to Message", url=f"https://t.me/c/{str(chat_id)[4:]}/{msg_id}")
                ]
            ]
            
        await cb.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        await cb.answer()
    except Exception as e:
        logger.error(f"❌ Toggle menu error: {e}")
        await cb.answer(f"❌ Error: {e}", show_alert=True)

# ============================================================================
# 🔥 MEDIA FORWARD CONFIRMATION HANDLER - NEW
# ============================================================================
@Altruix.bot.on_callback_query(filters.regex(r"^tags_fwd_confirm_"))
@iuser_check
@log_errors
async def tags_forward_confirm_callback(c: Client, cb: CallbackQuery):
    """Show confirmation before forwarding large/restricted media."""
    try:
        data = cb.data.split("_")
        chat_id, msg_id = int(data[3]), int(data[4])
        
        # Show confirmation
        await cb.answer("⚠️ This will download and re-upload the media. Continue?", show_alert=True)
        
        # Update button to execute
        keyboard = [
            [InlineKeyboardButton("✅ Yes, Forward", callback_data=f"tags_fwd_media_{chat_id}_{msg_id}")],
            [InlineKeyboardButton("❌ Cancel", callback_data=f"tags_fwd_cancel_{chat_id}_{msg_id}")]
        ]
        
        await cb.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"❌ Forward confirm error: {e}")
        await cb.answer(f"❌ Error: {e}", show_alert=True)

# ============================================================================
# 🔥 MEDIA FORWARD HANDLER - NEW
# ============================================================================
@Altruix.bot.on_callback_query(filters.regex(r"^tags_fwd_media_"))
@iuser_check
@log_errors
async def tags_forward_media_callback(c: Client, cb: CallbackQuery):
    """Download and forward media to tag logger topic."""
    try:
        data = cb.data.split("_")
        chat_id, msg_id = int(data[3]), int(data[4])
        
        # Get client
        msg_key = f"{chat_id}_{msg_id}"
        cache_data = await get_mention_from_cache(msg_key)
        
        if not cache_data:
            return await cb.answer("❌ Cache not found", show_alert=True)
            
        client_id = cache_data["client_id"]
        userbot_client = await get_mention_client(client_id)
        
        if not userbot_client:
            return await cb.answer("❌ Client not found", show_alert=True)
            
        await cb.answer("📥 Downloading media...", show_alert=False)
        
        # Download
        msg = await userbot_client.get_messages(chat_id, msg_id)
        if not msg or not msg.media:
            return await cb.answer("❌ Media not found", show_alert=True)
            
        file_path = await userbot_client.download_media(msg)
        
        if not file_path:
            return await cb.answer("❌ Download failed", show_alert=True)
            
        # Get topic
        topic_id = await get_or_create_topic(Altruix.bot, Altruix.log_chat, "tag logger", userbot_client=userbot_client)
        
        # Upload
        caption = f"✅ **Forwarded Tag Media**\nFrom: {userbot_client.me.mention}"
        if msg.caption:
            caption += f"\n\n**Original Caption:**\n{msg.caption}"
            
        await userbot_client.send_document(
            Altruix.log_chat,
            file_path,
            caption=caption,
            message_thread_id=topic_id
        )
        
        # Cleanup
        if os.path.exists(file_path):
            os.remove(file_path)
            
        await cb.answer("✅ Media forwarded!", show_alert=True)
    except Exception as e:
        logger.error(f"❌ Forward media error: {e}")
        await cb.answer(f"❌ Error: {e}", show_alert=True)

# ============================================================================
# 🔥 MEDIA FORWARD CANCEL HANDLER - NEW
# ============================================================================
@Altruix.bot.on_callback_query(filters.regex(r"^tags_fwd_cancel_"))
@iuser_check
@log_errors
async def tags_forward_cancel_callback(c: Client, cb: CallbackQuery):
    """Cancel media forward and restore original buttons."""
    try:
        data = cb.data.split("_")
        chat_id, msg_id = int(data[3]), int(data[4])
        
        # Restore compact menu
        keyboard = [
            [
                InlineKeyboardButton("⚙️ Show Full Menu", callback_data=f"tags_toggle_full_{chat_id}_{msg_id}"),
                InlineKeyboardButton("🔗 Go to Message", url=f"https://t.me/c/{str(chat_id)[4:]}/{msg_id}")
            ]
        ]
        
        await cb.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        await cb.answer("❌ Cancelled", show_alert=False)
    except Exception as e:
        logger.error(f"❌ Cancel forward error: {e}")
        await cb.answer(f"❌ Error: {e}", show_alert=True)

# ============================================================================
# 🔥 BLOCK USER HANDLER - NEW
# ============================================================================
@Altruix.bot.on_callback_query(filters.regex(r"^tags_block_"))
@iuser_check
@log_errors
async def tags_block_user_callback(c: Client, cb: CallbackQuery):
    """Block user who tagged."""
    try:
        # from Main.utils.access_control import is_authorized_user (Cleaned)
        # Parse: tags_block_CHATID_MSGID_USERID
        parts = cb.data.split("_")
        chat_id, msg_id, user_id = int(parts[2]), int(parts[3]), int(parts[4])
        
        # Get client
        msg_key = f"{chat_id}_{msg_id}"
        cache_data = await get_mention_from_cache(msg_key)
        
        if not cache_data:
            return await cb.answer("❌ Cache not found", show_alert=True)
            
        client_id = cache_data["client_id"]
        userbot_client = await get_mention_client(client_id)
        
        if not userbot_client:
            return await cb.answer("❌ Client not found", show_alert=True)
            
        # Block user
        await userbot_client.block_user(user_id)
        
        # Update button to unblock
        keyboard = cb.message.reply_markup.inline_keyboard
        for row in keyboard:
            for button in row:
                if button.callback_data and "tags_block_" in button.callback_data:
                    button.text = "✅ Unblock User"
                    button.callback_data = f"tags_unblock_{chat_id}_{msg_id}_{user_id}"
        
        await cb.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        await cb.answer("🚫 User blocked!", show_alert=True)
    except Exception as e:
        logger.error(f"❌ Block user error: {e}")
        await cb.answer(f"❌ Error: {e}", show_alert=True)

# ============================================================================
# 🔥 UNBLOCK USER HANDLER - NEW
# ============================================================================
@Altruix.bot.on_callback_query(filters.regex(r"^tags_unblock_"))
@iuser_check
@log_errors
async def tags_unblock_user_callback(c: Client, cb: CallbackQuery):
    """Unblock user who tagged."""
    try:
        # Parse: tags_unblock_CHATID_MSGID_USERID
        parts = cb.data.split("_")
        chat_id, msg_id, user_id = int(parts[2]), int(parts[3]), int(parts[4])
        
        # Get client
        msg_key = f"{chat_id}_{msg_id}"
        cache_data = await get_mention_from_cache(msg_key)
        
        if not cache_data:
            return await cb.answer("❌ Cache not found", show_alert=True)
            
        client_id = cache_data["client_id"]
        userbot_client = await get_mention_client(client_id)
        
        if not userbot_client:
            return await cb.answer("❌ Client not found", show_alert=True)
            
        # Unblock user
        await userbot_client.unblock_user(user_id)
        
        # Update button to block
        keyboard = cb.message.reply_markup.inline_keyboard
        for row in keyboard:
            for button in row:
                if button.callback_data and "tags_unblock_" in button.callback_data:
                    button.text = "🚫 Block User"
                    button.callback_data = f"tags_block_{chat_id}_{msg_id}_{user_id}"
        
        await cb.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        await cb.answer("✅ User unblocked!", show_alert=True)
    except Exception as e:
        logger.error(f"❌ Unblock user error: {e}")
        await cb.answer(f"❌ Error: {e}", show_alert=True)

# ============================================================================
# 🔥 SEND MESSAGE TO USER HANDLER - NEW
# ============================================================================
@Altruix.bot.on_callback_query(filters.regex(r"^tags_send_msg_"))
@iuser_check
@log_errors
async def tags_send_message_callback(c: Client, cb: CallbackQuery):
    """Start process to send message to user who tagged."""
    try:
        # Parse: tags_send_msg_CHATID_MSGID_USERID
        parts = cb.data.split("_")
        chat_id, msg_id, user_id = int(parts[3]), int(parts[4]), int(parts[5])
        
        # Get client
        msg_key = f"{chat_id}_{msg_id}"
        cache_data = await get_mention_from_cache(msg_key)
        
        if not cache_data:
            return await cb.answer("❌ Cache not found", show_alert=True)
            
        client_id = cache_data["client_id"]
        userbot_client = await get_mention_client(client_id)
        
        if not userbot_client:
            return await cb.answer("❌ Client not found", show_alert=True)
        
        # Create waiting entry
        waiting_id = f"tags_send_{cb.from_user.id}_{int(time.time())}"
        waiting_data = {
            "user_id": user_id,
            "client_id": client_id,
            "log_msg_id": cb.message.id,
            "timestamp": int(time.time())
        }
        
        await save_waiting_reply(waiting_id, waiting_data)
        REPLY_AS_MENTIONED_WAITING[waiting_id] = waiting_data
        
        # Send instruction
        instruction_msg = await Altruix.bot.send_message(
            Altruix.log_chat,
            f"📤 **Send Message to User**\n\n"
            f"Reply to this message with the text you want to send to user <code>{user_id}</code>\n\n"
            f"⏱️ Waiting for your message...",
            parse_mode=enums.ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data=f"tags_send_cancel_{waiting_id}")
            ]])
        )
        
        # Update waiting data with instruction message
        waiting_data["instruction_msg_id"] = instruction_msg.id
        await save_waiting_reply(waiting_id, waiting_data)
        REPLY_AS_MENTIONED_WAITING[waiting_id] = waiting_data
        
        await cb.answer("✅ Reply to the instruction message", show_alert=False)
    except Exception as e:
        logger.error(f"❌ Send message init error: {e}")
        await cb.answer(f"❌ Error: {e}", show_alert=True)

# ============================================================================
# 🔥 HANDLE SEND MESSAGE INPUT - NEW
# ============================================================================
@Altruix.bot.on_message(
    filters.chat(Altruix.log_chat) & filters.reply & ~filters.bot
)
@log_errors
async def handle_tags_send_message_input(c: Client, m: RawMessage):
    """Handle user input for sending message to tagger."""
    try:
        if not m.reply_to_message or not m.reply_to_message.text:
            return
            
        # Check if this is a reply to send message instruction
        if "Send Message to User" not in m.reply_to_message.text:
            return
            
        # Find matching waiting entry
        waiting_entry = None
        waiting_id_match = None
        
        for waiting_id, data in list(REPLY_AS_MENTIONED_WAITING.items()):
            if data.get("instruction_msg_id") == m.reply_to_message.id:
                waiting_entry = data
                waiting_id_match = waiting_id
                break
        
        if not waiting_entry:
            return
            
        user_id = waiting_entry["user_id"]
        client_id = waiting_entry["client_id"]
        
        # Get client
        userbot_client = await get_mention_client(client_id)
        if not userbot_client:
            await m.reply("❌ Client not found")
            return
            
        # Send message to user
        if m.media:
            sent = await userbot_client.copy_message(user_id, m.chat.id, m.id)
        else:
            sent = await userbot_client.send_message(user_id, m.text or m.caption)
        
        # Confirmation
        await m.reply(
            f"✅ **Message sent successfully!**\n\n"
            f"• To: <code>{user_id}</code>\n"
            f"• Via: {userbot_client.me.mention}\n"
            f"• Time: {datetime.now().strftime('%H:%M:%S')}",
            parse_mode=enums.ParseMode.HTML
        )
        
        # Cleanup
        await delete_waiting_reply(waiting_id_match)
        REPLY_AS_MENTIONED_WAITING.pop(waiting_id_match, None)
        
        # Delete instruction message
        try:
            await m.reply_to_message.delete()
        except: pass
        
    except Exception as e:
        logger.error(f"❌ Send message input error: {e}")
        await m.reply(f"❌ Error: {str(e)[:100]}")


# Start cache cleanup task
asyncio.create_task(cache_cleanup_task())
logger.info("Cache cleanup task started")



# # Di akhir file, sebelum FINAL LOG
# logger.info(f"🔧 [DEBUG] Registering handle_reply_as_mentioned_input handler")
# logger.info(f"🔧 [DEBUG] Filter: filters.chat({Altruix.log_chat}) & filters.reply & ~filters.bot")
# logger.info(f"🔧 [DEBUG] Total waiting entries at startup: {len(REPLY_AS_MENTIONED_WAITING)}")

# @Altruix.bot.on_message(filters.chat(Altruix.log_chat))
# @log_errors
# async def debug_all_messages(c: Client, m: RawMessage):
#     """Debug semua pesan di log chat."""
#     logger.info(f"🔍 [DEBUG_ALL] Message in log_chat: ID={m.id}, "
#                f"Reply to={m.reply_to_message.id if m.reply_to_message else None}, "
#                f"Text={m.text[:50] if m.text else 'No text'}")

# ============================================================================
# 🔥 FINAL LOG
# ============================================================================
# Log sukses loading
# try:
#     Altruix.log(f"[DEBUG] ✅ Loaded → {__plugin_name__} {PLUGIN_VERSION}", level=20)
# except Exception as e:
#     logger.info(f"[DEBUG] ✅ Loaded → {__plugin_name__} {PLUGIN_VERSION}")

# logger.info(f"📋 Mentions plugin v{PLUGIN_VERSION} successfully loaded")
# logger.info(f"🔧 Cache system: {'Enabled with flexible backend' if CACHE_MANAGER_AVAILABLE else 'Fallback to in-memory cache'}")
# logger.info(f"🔧 Use /mentions_cache stats to check cache status")
# logger.info(f"🔧 Use /mentions_fix_cache to recover missing cache entries")
# logger.info(f"🔧 Use /mentions_test (via bot) to test all buttons")
# logger.info(f"⚠️  Note: Userbots cannot send inline buttons, only bot can!")

