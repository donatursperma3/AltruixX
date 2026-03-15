# qwen client.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
# 
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
# 
# All rights reserved.
import os
import sys
import subprocess
import glob
import html
import time
import yaml
import shlex
import random
import shutil
import asyncio
import inspect
import logging
import aiofiles
import importlib
import traceback

import contextlib
import multiprocessing
from pathlib import Path
from collections import defaultdict
from functools import wraps
from Main.core.apm import APM
from Main.core.ext.upm import UPM
from datetime import datetime
from cachetools import TTLCache
from traceback import format_exc
from Main.core.cache import Cache
from Main.utils.paste import Paste
from ..utils._updater import Updater
from pyrogram.session import Session
from .config import Config, BaseConfig
from ..utils.essentials import Essentials
from .database import MongoDB, LocalDatabase
from pyrogram.handlers import MessageHandler, EditedMessageHandler, DeletedMessagesHandler, CallbackQueryHandler
from ..utils.custom_filters import user_filters
from ..utils.startup_helpers import concatenate
from Main.utils.heroku_ import prepare_heroku_url
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Union, Optional
# --------------------

from ..utils.multi_lang_helpers import get_all_files_in_path
from pyrogram import (
    Client, StopPropagation, ContinuePropagation, idle, filters,
    __version__ as pyrogram_version)
from pyrogram.errors.exceptions.bad_request_400 import (
    MessageEmpty, PeerIdInvalid, MessageTooLong, MessageIdInvalid,
    MessageNotModified, UserNotParticipant)

# --------------------
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, User, ChatPrivileges, ChatMember, BotCommand, ChatInviteLink, MenuButton, ChatPhoto, Sticker, MessageReactions, Chat, LinkPreviewOptions
from pyrogram.errors import (
    RPCError,
    FloodWait,
    ChatSendPhotosForbidden,
    ChatSendMediaForbidden,
    # ChatSendRoundVideoForbidden,
    # ChatSendVideosForbidden,
    # ChatSendAudiosForbidden,
    # ChatSendVoicesForbidden,
    # ChatSendDocumentsForbidden,
    # ChatSendStickersForbidden,
    # ChatSendGifsForbidden,
    # ChatSendGameForbidden,
    # ChatSendInlineForbidden,
    # ChatWriteForbidden,
    # UserIsBlocked,
    PeerIdInvalid,
    MessageNotModified
)

# Monkey-patch Message.edit to ignore MessageNotModified
_old_edit = Message.edit
async def _new_edit(self, *args, **kwargs):
    try:
        return await _old_edit(self, *args, **kwargs)
    except MessageNotModified:
        return self
Message.edit = _new_edit
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait
import psutil
import platform
import threading
from Main.utils.essentials import Essentials
from pyrogram import Client, idle, enums

logger = logging.getLogger("Altruix")

# ✅ PERUBAHAN 1: Prioritaskan env vars Sevalla untuk deteksi branch/commit yang akurat
def get_current_git_branch() -> str:
    """Deteksi branch Git secara akurat + commit hash pendek, prioritas env vars Sevalla."""
    branch_name = "unknown"
    commit_hash = "unknown"
    
    # ✅ PRIORITAS 1: Cek env vars Sevalla (runtime deployment info)
    sevalla_branch = os.getenv("SVL_DEPLOYMENT_BRANCH")
    sevalla_commit = os.getenv("SVL_DEPLOYMENT_COMMIT_SHA")
    
    if sevalla_branch:
        branch_name = sevalla_branch
    if sevalla_commit:
        commit_hash = sevalla_commit[:7] # Short commit: 7 char
    
    # ✅ PRIORITAS 2: Jika env vars Sevalla tidak ada, fallback ke deteksi Git
    if branch_name == "unknown" or commit_hash == "unknown":
        try:
            # Ambil short commit dari Git (selalu tersedia)
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                commit_hash = result.stdout.strip()[:7]
            
            # Deteksi branch name
            if branch_name == "unknown":
                result = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0 and result.stdout.strip() not in ("HEAD", ""):
                    branch_name = result.stdout.strip()
                else:
                    # Alternatif: git branch --show-current
                    result = subprocess.run(
                        ["git", "branch", "--show-current"],
                        capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        branch_name = result.stdout.strip()
                    else:
                        # Baca .git/HEAD
                        try:
                            with open(".git/HEAD", "r") as f:
                                head_content = f.read().strip()
                                if head_content.startswith("ref: refs/heads/"):
                                    branch_name = head_content.replace("ref: refs/heads/", "")
                        except (FileNotFoundError, OSError):
                            pass
        except (FileNotFoundError, subprocess.SubprocessError, OSError, subprocess.TimeoutExpired):
            pass # Biarkan tetap "unknown"
    
    # Format akhir: branch (commit)
    return f"{branch_name} [{commit_hash}]"

class TruncatedFormatter(logging.Formatter):
    """Custom formatter to truncate extremely long messages/tracebacks unless in DEBUG mode"""
    def __init__(self, fmt=None, datefmt=None, max_length=222, config=None):
        super().__init__(fmt, datefmt)
        self.max_length = max_length
        self.config = config

    def format(self, record):
        formatted = super().format(record)
        # Bypassing truncation if DEBUG is True
        if self.config and getattr(self.config, "DEBUG", False):
            return formatted
            
        if len(formatted) > self.max_length:
            return formatted[:self.max_length] + "... [TRUNCATED]"
        return formatted

class AltruixClient:
    def __init__(self, *args, **kwargs) -> None:
        self.ourselves: List[Dict[Any, Any]] = []
        self.bot_info = None
        self.clients: List[Client] = []
        self.cmd_list = {}
        self.all_lang_strings = {}
        self.__version__ = "0.0.10.0891H" # ✅ Global Inline Fix & Reg Fix
        self.upm = UPM(self)
        self.selected_lang = "english"
        self.local_lang_file = "./Main/localization"
        self.cmd_list = {} # {plugin_name: [cmd_data, ...]}
        self._module_helps = {} # {plugin_name: docstring}
        self.plugin_categories = {} # {plugin_name: 'userbot'|'bot'|'other'}
        self.start_time = time.time()
        self.app_url_ = None
        self.disabled_sudo_plugin_list = []
        self.SELF_PERMISSION_CACHE = TTLCache(
            99999, ttl=60 * 60, timer=time.perf_counter
        )
        self.loaded_bot_cmds = False
        Session.notice_displayed = True
        self.cmd_list_s = []
        self.training_wheels_protocol = False
        self.config = BaseConfig
        self._init_logger()
        self.db_sudo_users = set() # ✅ Dynamic Cache for Sudo Users from DB
        self.db_sudo_sync_lock = asyncio.Lock()
        self._sudo_membership_cache = TTLCache(maxsize=2000, ttl=600) # 10 minutes cache
        self._membership_lock = asyncio.Lock()
        self._membership_locks = {} # {user_id: Lock} to avoid global lock for network probes
        self._group_wl_cache = None
        self._group_wl_cache_exp = 0
        self._auth_users_cache = set() # ✅ Optimized set for fast lookup
        
        # ✅ HIGH-PERFORMANCE SETTINGS CACHE
        self._prefix_cache = {
            "apply_type": "global",
            "prefix_owner_user": ".",
            "prefix_sudo_users": "!",
            "ultroid_owner": ",", # Default for Ultroid Addons
            "ultroid_sudo": "?",  # Default for Ultroid Sudo
            "per_account": {} # {user_id: {"u": ".", "s": "!", "ult_u": ",", "ult_s": "?"}}
        }
        self._sudo_settings_cache = {
            "apply_type": "global",
            "enabled_global": True,
            "per_account_enabled": {} # {user_id: bool}
        }

        # ✅ Migrate JSON databases BEFORE initializing LocalDatabase
        try:
            from Main.utils.file_helpers import migrate_db_files
            json_to_migrate = [
                "altruix_local_db.json", "callback_logger_settings.json", 
                "chat_stats_cache.json", "custom_button_settings.json", 
                "db.json", "join_logger_settings.json", "mentions_cache.json", 
                "mentions_cache_fallback.json", "mentions_settings.json", 
                "mention_logger_bot_settings.json", "pml_filters.json", 
                "pm_logger_bot_settings.json", "pm_logger_cache.json", 
                "pm_logger_sessions.json", "pm_logger_user_settings.json", 
                "reply_manager_settings.json", "topic_cache.json", 
                "xchatsanomlau_cache.json", "cmd_logger_settings.json", 
                "topics_cache.json"
            ]
            migrate_db_files(json_to_migrate)
        except Exception as e:
            print(f"Migration failed: {e}")

        self.local_db = LocalDatabase()
        
        # ✅ Loop setup: Get or create the optimized loop
        try:
            self.loop = asyncio.get_event_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        # ✅ Install global exception handler for Pyrogram dispatcher
        try:
            from Main.core.exception_handler import install_exception_handler
            install_exception_handler(self)
            
            # ✅ INSTALL GLOBAL LOOP EXCEPTION HANDLER
            # This catches "Task exception was never retrieved" errors and logs them with context.
            def _loop_exception_handler(loop, context):
                msg = context.get("exception", context.get("message"))
                try:
                    self.log(f"💥 [GlobalLoopError] {msg}", level=30)
                except:
                    logger.warning(f"💥 [GlobalLoopError] {msg}")
            
            self.loop.set_exception_handler(_loop_exception_handler)
            
        except Exception as e:
            logger.warning(f"Failed to install exception handler: {e}")
        
        # ✅ Shared States for Plugins
        self.PURGEME_STATE = {}
        self.user_env_manager_state = {}
        self.user_privacy_state = {}
        self.user_track_state = {}
        self.SANGMATA_WAITING = {}
        
        if hasattr(asyncio, 'get_event_loop_policy'):
            policy = asyncio.get_event_loop_policy()
            if sys.platform == "win32":
                # winloop can sometimes cause deadlocks with Pyrogram, disabling temporarily for stability
                # pass
                try:
                    import winloop
                    asyncio.set_event_loop_policy(winloop.EventLoopPolicy())
                    logger.info("🚀 Using event loop policy: winloop.EventLoopPolicy")
                except ImportError:
                    logger.info(f"🚀 Using event loop policy: {type(policy).__name__}")
            else:
                try:
                    import uvloop
                    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
                    logger.info("🚀 Using event loop policy: uvloop.EventLoopPolicy")
                except ImportError:
                    logger.info(f"🚀 Using event loop policy: {type(policy).__name__}")

        self.loop.run_until_complete(self._db_setup())
        self.executor = ThreadPoolExecutor(max_workers=multiprocessing.cpu_count() * 5)
        self.config = Config(self.db.env_col, loop=self.loop, executor=self.executor)
        self.log_chat = None
        self._command_help_message_data = {}
        
        # Shared state for PM and Mention Loggers
        self.PM_LOG_CACHE = {}
        self.SANGMATA_WAITING = {}
        self.REPLY_AS_MENTIONED_WAITING = {}
        # Daily limit tracking: user_id -> date_str -> count
        self.USER_REPLY_COUNTS = defaultdict(lambda: defaultdict(int))
        self.BUTTON_STATS = {"react": 0, "reply": 0, "reply_all": 0, "confirm": 0, "cancel": 0, "save": 0, "unsend": 0}
        
        # State mapping for different plugins
        self.user_track_state = {} # {user_id: {'session_index': int, 'step': str, ...}}
        self.GPURGEME_STATE = {} # {unique_id: state_dict}
        
        if sys.platform != "win32":
            try:
                import signal
                self.loop.add_signal_handler(
                    signal.SIGINT, 
                    lambda: asyncio.create_task(self.graceful_shutdown("SIGINT"))
                )
                self.loop.add_signal_handler(
                    signal.SIGTERM,
                    lambda: asyncio.create_task(self.graceful_shutdown("SIGTERM"))
                )
            except (NotImplementedError, ImportError):
                pass
        
        # Registry to track added handlers (prevent duplication)
        self.handler_registry = set()
        
        # ✅ Disabled Sessions Management
        self.disabled_sessions = set()
        self.load_disabled_sessions()
        
        # Initialize BotManager BEFORE _setup()
        from Main.core.bot_manager import BotManager
        self.bot_manager = BotManager(self)
        
        self.loop.run_until_complete(self._setup(restart=False, *args, **kwargs))


    async def edit_cb(self, cb: CallbackQuery, text: str, **kwargs):
        try:
            await cb.edit_message_text(text, **kwargs)
        except MessageNotModified:
            pass
        except Exception as e:
            self.log(f"edit_cb failed: {e}", level=logging.ERROR)

    async def delete_cb(self, cb: CallbackQuery):
        """ ✅ Hardened delete utility that handles both regular and inline modes safely. """
        try:
            if cb.message:
                await cb.message.delete()
            else:
                # Handle Inline Mode (results sent via bot)
                await cb.edit_message_text(
                    "<b>❌ Menu Closed</b>\n<i>The session has been terminated safely.</i>", 
                    parse_mode=ParseMode.HTML
                )
        except Exception as e:
            # Fallback if deletion is not allowed or message is too old
            try:
                await cb.edit_message_text(
                    "<b>❌ Closed</b>", 
                    parse_mode=ParseMode.HTML
                )
            except: pass
            self.log(f"delete_cb failed (fallback applied): {e}", level=logging.ERROR)
    def load_disabled_sessions(self):
        """Load list of disabled user_ids from file."""
        try:
            if not os.path.exists("DATABASE"):
                os.makedirs("DATABASE")
            path = os.path.join("DATABASE", "disabled_sessions.json")
            if os.path.exists(path):
                import json
                with open(path, "r") as f:
                    data = json.load(f)
                    self.disabled_sessions = set(int(x) for x in data)
            else:
                self.disabled_sessions = set()
        except Exception as e:
            self.log(f"Failed to load disabled sessions: {e}", level=logging.ERROR)
            self.disabled_sessions = set()

    def save_disabled_sessions(self):
        """Save list of disabled user_ids to file."""
        try:
            if not os.path.exists("DATABASE"):
                os.makedirs("DATABASE")
            path = os.path.join("DATABASE", "disabled_sessions.json")
            import json
            with open(path, "w") as f:
                json.dump(list(self.disabled_sessions), f)
        except Exception as e:
            self.log(f"Failed to save disabled sessions: {e}", level=logging.ERROR)

    def is_session_disabled(self, user_id: int) -> bool:
        """Check if a session (user_id) is disabled."""
        return user_id in self.disabled_sessions

    def toggle_session_status(self, user_id: int, enable: bool = None) -> bool:
        """Toggle or set session enabled/disabled status.
        
        Args:
            user_id: The user ID to toggle
            enable: If None, toggle. If True, enable. If False, disable.
            
        Returns:
            bool: True if session is now enabled, False if disabled
        """
        if enable is None:
            # Toggle
            if user_id in self.disabled_sessions:
                self.disabled_sessions.discard(user_id)
            else:
                self.disabled_sessions.add(user_id)
        elif enable:
            # Enable
            self.disabled_sessions.discard(user_id)
        else:
            # Disable
            self.disabled_sessions.add(user_id)
        self.save_disabled_sessions()
        return user_id not in self.disabled_sessions  # Return new status (True = enabled)

    def toggle_session_disable(self, user_id: int, disable: bool):
        """Enable or disable a session."""
        if disable:
            self.disabled_sessions.add(user_id)
        else:
            self.disabled_sessions.discard(user_id)
        self.save_disabled_sessions()

    @property
    def total_commands(self) -> int:
        """Calculate total number of registered command triggers."""
        total = 0
        for plugin in self.cmd_list:
            for cmd_info in self.cmd_list[plugin]:
                total += len(cmd_info.get("commands", []))
        return total


    async def update_cache(self):
        cache = Cache(self.config, self.db, self.clients)
        await cache.update_auto_post_cache()

    @property
    def banner(self):
        return fr"""
   _____  .__   __                .__    .___        ____  ___
  /  _  \ |  |_/  |________  ____ |__| __| _/        \   \/  /
 /  /_\  \|  |\   __\_  __ \/  _ \|  |/ __ |  ______  \     / 
/    |    \  |_|  |  |  | \(  <_> )  / /_/ | /_____/  /     \ 
\____|__  /____/__|  |__|   \____/|__\____ |         /___/\  \.
        \/                                \/               \_/
                                                    
                                                    
 (C) Project Altruix + Ultroid + Alpha-X 2021-{datetime.today().year}
 Version: {self.__version__} - [ Altroid-X Assistant ]
        """

    @property
    def ax(self) -> Optional[Client]:
        return random.choice(self.clients) if self.clients else None

    @property
    def auth_users(self):
        """
        Synchronous property for basic authorization checks (e.g. Bot filters).
        Uses the optimized cache set.
        """
        return list(self._auth_users_cache)

    async def get_prefix(self, user_id: int, message: Message = None, is_ultroid: bool = False) -> str:
        """Centralized helper to get the prefix for a specific user session."""
        is_global = self._prefix_cache["apply_type"] == "global"
        
        if is_ultroid:
            if is_global:
                u_p = self._prefix_cache.get("ultroid_owner", ",")
                s_p = self._prefix_cache.get("ultroid_sudo", "?")
            else:
                pa = self._prefix_cache["per_account"].get(user_id, {})
                u_p = pa.get("ult_u", self._prefix_cache.get("ultroid_owner", ","))
                s_p = pa.get("ult_s", self._prefix_cache.get("ultroid_sudo", "?"))
        else:
            if is_global:
                u_p = self._prefix_cache["prefix_owner_user"]
                s_p = self._prefix_cache["prefix_sudo_users"]
            else:
                pa = self._prefix_cache["per_account"].get(user_id, {})
                u_p = pa.get("u", self._prefix_cache["prefix_owner_user"])
                s_p = pa.get("s", self._prefix_cache["prefix_sudo_users"])
        
        if message and message.text:
            if message.text.startswith(u_p): return u_p
            if message.text.startswith(s_p): return s_p
        return u_p

    async def is_sudo(self, user_id: int, client: Client = None) -> bool:
        """
        ✅ Centralized helper to check if a user is authorized as Sudo.
        Handles both Global and Per-Account sudo settings from DB and .env.
        Inclue Sudo Enabled/Disabled check.
        """
        # logger.debug(f"🔍 is_sudo(user_id={user_id}, ...)") # Too slow for tight loops
        
        if user_id in self._auth_users_cache:
            return True
            
        if user_id in self.config.OWNER_USERS_ID:
            self._auth_users_cache.add(user_id) # Cache it
            return True
        
        # Sudo list check follows...

        # ====================== ENABLEMENT CHECK ======================
        # ✅ OPTIMIZED: Use cache if available
        apply_type = self._sudo_settings_cache["apply_type"]
        
        if apply_type == "global":
            sudo_enabled = self._sudo_settings_cache["enabled_global"]
        else:
            # Per-Account Sudo
            if client and client in self.clients:
                target_id = client.me.id
                sudo_enabled = self._sudo_settings_cache["per_account_enabled"].get(target_id, True)
            else:
                # Default for Bot Assistant or unknown context
                sudo_enabled = True
        
        if not sudo_enabled:
            self.log(f"❌ is_sudo: Sudo is DISABLED ({apply_type}).", level=logging.DEBUG)
            return False

        # ====================== USER LIST CHECK ======================
        # Check optimized cache set (Comprehensive)
        if user_id in self._auth_users_cache:
            self.log(f"✅ is_sudo: User {user_id} found in optimized auth_users cache.", level=logging.DEBUG)
            return True

        # Check database sudo users based on application mode (Dynamic Cache)
        if apply_type == "global":
            # In global mode, if user is in ANY session's sudo list, they are authorized.
            if user_id in self.db_sudo_users:
                self.log(f"✅ is_sudo: User {user_id} found in global db_sudo_users cache.", level=logging.DEBUG)
                return True
        else:
            # In per-account mode, check if user is in the specific session's sudo list.
            if client and client in self.clients:
                try:
                    target_id = client.me.id
                    sudo_data = await self.config.get_env(f"SUDO_USERS_{target_id}")
                    if sudo_data:
                        uids = []
                        if isinstance(sudo_data, str):
                            uids = [int(x) for x in sudo_data.split() if x.isdigit()]
                        elif isinstance(sudo_data, list):
                            uids = [int(x) for x in sudo_data]
                        if user_id in uids:
                            self.log(f"✅ is_sudo: User {user_id} found in per-account DB list ({target_id}).", level=logging.DEBUG)
                            return True
                except Exception as e:
                    self.log(f"Error checking per-account sudo list: {e}", level=logging.DEBUG)
            else:
                # Fallback: check cache if no specific client context (e.g. for general bot commands)
                if user_id in self.db_sudo_users:
                    self.log(f"✅ is_sudo: User {user_id} found in fallback db_sudo_users cache.", level=logging.DEBUG)
                    return True
        
        if await self.is_member_of_whitelisted_group(user_id):
            self.log(f"✅ is_sudo: User {user_id} is a member of a whitelisted group.", level=logging.DEBUG)
            return True
        
        self.log(f"❌ is_sudo: User {user_id} NOT AUTHORIZED.", level=logging.DEBUG)
        return False

    async def is_member_of_whitelisted_group(self, user_id: int) -> bool:
        """Check if a user is a member of any whitelisted group with TTL caching."""
        if not await self.is_group_wl_enabled():
            return False
            
        # 1. Immediate cache check (Fast Path)
        if user_id in self._sudo_membership_cache:
            return self._sudo_membership_cache[user_id]
            
        # 2. Get user-specific lock to avoid redundant concurrent probes
        if user_id not in self._membership_locks:
            self._membership_locks[user_id] = asyncio.Lock()
        
        async with self._membership_locks[user_id]:
            # Double check cache after acquiring lock
            if user_id in self._sudo_membership_cache:
                return self._sudo_membership_cache[user_id]
                
            try:
                group_list = await asyncio.wait_for(self.get_group_wl_list(), timeout=5)
            except asyncio.TimeoutError:
                self.log("⏰ get_group_wl_list TIMEOUT. Defaulting to empty list.", level=30)
                group_list = []
                
            if not group_list:
                self._sudo_membership_cache[user_id] = False
                return False
                
            is_member = False
            # Try checking membership via connected clients
            # Priority: Bot Assistant -> First 2 userbots (Limit to avoid loop lag)
            clients_to_try = ([self.bot] if self.bot and self.bot.is_connected else []) + self.clients[:2]
            
            for client in clients_to_try:
                if not client or not client.is_connected:
                    continue
                    
                for group in group_list:
                    chat_id = group["_id"]
                    try:
                        # ✅ Check chat member status with timeout
                        member = await asyncio.wait_for(client.get_chat_member(int(chat_id), user_id), timeout=3)
                        from pyrogram.enums import ChatMemberStatus
                        if member.status in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.MEMBER]:
                            is_member = True
                            break
                    except (asyncio.TimeoutError, RPCError, Exception):
                        continue
                if is_member:
                    break
            
            # ✅ Update TTL cache (Including False results for negative caching)
            self._sudo_membership_cache[user_id] = is_member
            return is_member

    @property
    def is_sudo_filter(self):
        """
        ✅ Dynamic Filter for Bot Assistant and other Pyrogram handlers.
        Always evaluates the LATEST sudo status instead of using a static list.
        """
        async def func(_, __, update):
            user = getattr(update, "from_user", None)
            if not user:
                return False
            # We don't have client context in a general filter easily, 
            # so it defaults to global cache check in is_sudo.
            return await self.is_sudo(user.id)
        return filters.create(func)

    async def refresh_sudo_cache(self):
        """
        ✅ FIXED: Dynamically refresh the sudo users list from database for all sessions.
        This allows sudo users added via UI to be recognized immediately.
        """
        async with self.db_sudo_sync_lock:
            # ✅ REFACTOR: Use the robust config method that aggregates everything
            all_sudo = await self.config.get_sudo()
            new_sudo_set = set(all_sudo)
            
            # 2. Include Per-Account Sudo Users (for per-account logic)
            for client in self.clients:
                try:
                    if not client.me: continue
                    target_id = client.me.id
                    db_sudo_raw = await self.config.get_env(f"SUDO_USERS_{target_id}")
                    if db_sudo_raw:
                        if isinstance(db_sudo_raw, str):
                            uids = [int(x) for x in db_sudo_raw.split() if x.isdigit()]
                        elif isinstance(db_sudo_raw, list):
                            uids = [int(x) for x in db_sudo_raw]
                        new_sudo_set.update(uids)
                except Exception as e:
                    self.log(f"Error fetching sudo from session: {e}", level=logging.DEBUG)
            
            self.db_sudo_users = new_sudo_set
            
            # ✅ REFRESH SETTINGS CACHE (Prefix & Sudo Settings)
            self._sudo_settings_cache["apply_type"] = await self.config.get_env("SUDO_APPLY_TYPE") or "global"
            self._prefix_cache["apply_type"] = await self.config.get_env("PREFIX_APPLY_TYPE") or "global"
            
            # Global Settings
            enabled_raw = await self.config.get_env("SUDO_ENABLED_GLOBAL")
            self._sudo_settings_cache["enabled_global"] = (enabled_raw != "false") if enabled_raw else True
            self._prefix_cache["prefix_owner_user"] = await self.config.get_env("PREFIX_OWNER_USER") or self.prefix_owner_user
            self._prefix_cache["prefix_sudo_users"] = await self.config.get_env("PREFIX_SUDO_USERS") or self.prefix_sudo_users
            self._prefix_cache["ultroid_owner"] = await self.config.get_env("ULTROID_PREFIX_OWNER") or ","
            self._prefix_cache["ultroid_sudo"] = await self.config.get_env("ULTROID_PREFIX_SUDO") or "?"
            
            # ✅ UPDATE OPTIMIZED CACHE
            self._auth_users_cache = new_sudo_set.copy()
            self._auth_users_cache.update(self.config.OWNER_USERS_ID)
            for acc in self.ourselves:
                try: self._auth_users_cache.add(int(acc.id))
                except: pass
            
            # Per-Account Refresh
            for client in self.clients:
                try:
                    tid = client.me.id
                    # Sudo Enablement
                    en_raw = await self.config.get_env(f"SUDO_ENABLED_{tid}")
                    self._sudo_settings_cache["per_account_enabled"][tid] = (en_raw != "false") if en_raw else True
                    # Prefix
                    up = await self.config.get_env(f"PREFIX_OWNER_USER_{tid}") or self.prefix_owner_user
                    sp = await self.config.get_env(f"PREFIX_SUDO_USERS_{tid}") or self.prefix_sudo_users
                    ulp = await self.config.get_env(f"ULTROID_PREFIX_OWNER_{tid}") or ","
                    usp = await self.config.get_env(f"ULTROID_PREFIX_SUDO_{tid}") or "?"
                    self._prefix_cache["per_account"][tid] = {"u": up, "s": sp, "ult_u": ulp, "ult_s": usp}
                except: pass
                
            self.log(f"✅ Sudo & Prefix cache refreshed: {len(self.db_sudo_users)} sudo users.", level=logging.INFO)


    # ✅ GROUP WHITELIST MANAGEMENT
    _group_wl_enabled = None

    async def is_group_wl_enabled(self) -> bool:
        """Check if group whitelist feature is enabled globaly."""
        if self._group_wl_enabled is not None:
            return self._group_wl_enabled
        status = await self.config.get_env("GROUP_WL_STATUS")
        self._group_wl_enabled = (status == "on")
        return self._group_wl_enabled

    async def toggle_group_wl(self, status: bool = None) -> bool:
        """Toggle group whitelist feature status."""
        current = await self.is_group_wl_enabled()
        new_status = status if status is not None else not current
        val = "on" if new_status else "off"
        await self.config.add_env_to_db("GROUP_WL_STATUS", val)
        self._group_wl_enabled = new_status
        return new_status

    async def is_group_whitelisted(self, chat_id: Union[int, str]) -> bool:
        """Check if a group is whitelisted."""
        if not await self.is_group_wl_enabled():
            return False
        res = await self.db.group_wl_col.find_one({"_id": str(chat_id)})
        return bool(res)

    async def add_group_wl(self, chat_id: Union[int, str], title: str = "Unknown Group") -> bool:
        """Add a group to the whitelist."""
        await self.db.group_wl_col.find_one_and_update(
            {"_id": str(chat_id)},
            {"$set": {"_id": str(chat_id), "title": title, "added_at": time.time()}},
            upsert=True
        )
        self._group_wl_cache = None # Invalidate cache
        return True

    async def del_group_wl(self, chat_id: Union[int, str]) -> bool:
        """Remove a group from the whitelist."""
        res = await self.db.group_wl_col.find_one_and_delete({"_id": str(chat_id)})
        self._group_wl_cache = None # Invalidate cache
        return bool(res)

    async def get_group_wl_list(self) -> List[Dict[str, Any]]:
        """Get list of all whitelisted groups with 1-minute TTL caching."""
        now = time.time()
        if self._group_wl_cache is not None and self._group_wl_cache_exp > now:
            return self._group_wl_cache
            
        groups = []
        async for group in self.db.group_wl_col.find({}):
            groups.append(group)
            
        self._group_wl_cache = groups
        self._group_wl_cache_exp = now + 60 # 1 minute cache
        return groups

    def log(
        self,
        message: Optional[Any] = None,
        level=logging.DEBUG,
        logger: logging.Logger = logging.getLogger(__name__),
        client: Client = None,
        user_id: Union[int, str] = None
    ) -> Optional[str]:
        if message is None:
            msg = traceback.format_exc()
        elif isinstance(message, Exception):
            # Compact formatting for RPC errors or standard exceptions
            error_name = type(message).__name__
            full_str = str(message)
            
            # ✅ IMPROVED: Aggressively remove "Telegram says:" and any leading/trailing boilerplate
            if "Telegram says:" in full_str:
                try:
                    # Capture everything AFTER "Telegram says:"
                    error_msg = full_str.split("Telegram says:")[1].strip()
                except IndexError:
                    error_msg = full_str
            else:
                error_msg = full_str
                
            msg = f"[{error_name}] {error_msg}"
        else:
            msg = str(message)
            
        # ✅ ENHANCEMENT: Add Caller Info (Module & Function)
        # Identify Caller (Plugin/Function) - Highly Optimized using sys._getframe
        debug_mode = getattr(self.config, "DEBUG", False)
        caller_info = ""
        
        # Only extract caller info if DEBUG mode is ON, or if it's an ERROR/CRITICAL log (level >= 40)
        if debug_mode or level >= 40:
            try:
                import sys as _sys
                # Traverse frames to find the first non-core frame
                f = _sys._getframe(1)
                depth = 0
                while f and depth < 10:
                    module_name = f.f_globals.get('__name__', 'unknown')
                    
                    # Exclude logging machinery itself, but allow decorators
                    if module_name in ["logging", "importlib", "asyncio.events", "threading", "Main.core.client", "Main.utils.essentials"]:
                         f = f.f_back
                         depth += 1
                         continue
                         
                    func_name = f.f_code.co_name
                    
                    # Ignore wrapper functions inside decorators
                    if func_name in ["wrapper", "check_inline"]:
                        f = f.f_back
                        depth += 1
                        continue
    
                    parts = module_name.split(".")
                    mod_display = ".".join(parts[-2:]) if len(parts) > 1 else module_name
                    caller_info = f" [📍 {mod_display}.{func_name}]"
                    break
                    
            except Exception:
                pass
                
        if caller_info:
            msg += caller_info


        # ✅ ENHANCEMENT: Add Session/Account Information to terminal logs
        session_info = ""
        target_client = client
        target_uid = user_id
        
        if not target_client and target_uid:
            # Try to find client by ID
            for c in self.clients:
                if hasattr(c, "me") and c.me and c.me.id == int(target_uid):
                    target_client = c; break
        
        if target_client:
            try:
                from Main.core.exception_handler import get_session_info
                session_info = f"{get_session_info(target_client)} | "
            except: pass
        elif target_uid:
            session_info = f"[ID: {target_uid}] | "

        if session_info:
            msg = f"{session_info}{msg}"

        # ✅ FINAL: Apply DEBUG prefix at the VERY start if mode is True
        if debug_mode:
            if not msg.startswith("[DEBUG]: »"):
                msg = f"[DEBUG]: » {msg}"

        # Suppress DEBUG level logs unless config.DEBUG is True
        if level <= logging.DEBUG and not debug_mode:
            return msg
            
        logger.log(level, msg)
        return msg

    def _init_logger(self) -> None:
        if sys.platform == "win32":
            # Force UTF-8 for Windows console to handle emojis
            if sys.stdout.encoding.lower() != "utf-8":
                sys.stdout.reconfigure(encoding="utf-8")
            if sys.stderr.encoding.lower() != "utf-8":
                sys.stderr.reconfigure(encoding="utf-8")

        logging.getLogger("pyrogram").setLevel(logging.ERROR)
        
        # Define format
        log_format = "%(asctime)s - [Altroid-X] >> %(levelname)s << %(message)s"
        date_format = "[%d/%m/%Y %H:%M:%S]"
        
        # Setup handlers
        file_handler = logging.FileHandler("altruix.log", encoding="utf-8", mode="w")
        stream_handler = logging.StreamHandler()
        
        # Apply Truncated Formatter (aware of DEBUG mode)
        formatter = TruncatedFormatter(
            fmt=log_format, 
            datefmt=date_format, 
            max_length=1500,
            config=self.config
        )
        file_handler.setFormatter(formatter)
        stream_handler.setFormatter(formatter)
        
        # Get root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        
        # Remove existing handlers if any
        for h in root_logger.handlers[:]:
            root_logger.removeHandler(h)
            
        root_logger.addHandler(file_handler)
        root_logger.addHandler(stream_handler)
        
        # ✅ Windows Terminal Color Support (Colorama)
        try:
            import colorama
            colorama.init(autoreset=True)
            self.log("Colorama initialized successfully (Windows Color Support)")
        except ImportError:
            pass

        self.log("Initialized Logger successfully!")

    async def resolve_dns(self):
        import dns.resolver
        self.log("DNS resolution check...", level=logging.INFO)
        try:
            # Run DNS resolution in executor to avoid blocking the event loop
            await asyncio.wait_for(
                self.loop.run_in_executor(None, lambda: dns.resolver.resolve("www.google.com")),
                timeout=5.0
            )
            self.log("DNS resolution: OK", level=logging.INFO)
        except asyncio.TimeoutError:
            self.log("DNS resolution timeout. Setting to: 8.8.8.8", level=logging.WARNING)
            dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
            dns.resolver.default_resolver.nameservers = ["8.8.8.8"]
        except Exception as e:
            self.log(f"DNS resolution error ({type(e).__name__}). Setting to: 8.8.8.8", level=logging.WARNING)
            dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
            dns.resolver.default_resolver.nameservers = ["8.8.8.8"]

    async def _db_setup(self):
        self.log("Initializing Database Setup...", level=logging.INFO)
        with contextlib.suppress(Exception):
            await self.update_on_startup()
        
        await self.resolve_dns()
        
        if self.config.DB_URI:
            self.log("Connecting to MongoDB...", level=logging.INFO)
            self.db = MongoDB(self.config.DB_URI)
            self.log("Initialized Mongo successfully!", level=logging.INFO)
        else:
            self.log("DB_URI not found. Using LocalDatabase.", level=logging.INFO)
            self.db = LocalDatabase()
            self.log("Initialized LocalDatabase successfully!", level=logging.INFO)
            # Start background saver for debounced writing
            self.loop.create_task(self.db.start_background_saver())
            self.log("Started LocalDatabase background saver.", level=logging.INFO)
            
        self.log("Pinging Database...", level=logging.INFO)
        try:
            await asyncio.wait_for(self.db.ping(), timeout=10.0)
            self.log("Pinged Database successfully!", level=logging.INFO)
        except asyncio.TimeoutError:
            self.log("Database ping timeout! Check your connection.", level=logging.ERROR)
        except Exception as e:
            self.log(f"Database ping failed: {e}", level=logging.ERROR)
            
        self.log("Preparing App URL...", level=logging.INFO)
        self.app_url_ = await prepare_heroku_url()
        self.log("Database Setup Complete.", level=logging.INFO)

    def run_in_exc(self, func_):
        @wraps(func_)
        async def wrapper(*args, **kwargs):
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                self.executor, lambda: func_(*args, **kwargs)
            )
        return wrapper

    async def setup_localization(self):
        lang = await self.config.get_env("UB_LANG")
        selected_lang = lang.lower() if lang else "english"
        all_files = get_all_files_in_path(self.local_lang_file)
        for filepath in all_files:
            with open(filepath, encoding="utf-8") as f:
                try:
                    data = yaml.safe_load(f)
                except Exception:
                    self.log()
                    continue
                language_to_load = data.get("language")
                if language_to_load == "template":
                    continue
                self.log(f"Loading : {language_to_load}", level=10)
                self.all_lang_strings[language_to_load] = data
        self.selected_lang = (
            selected_lang if selected_lang in self.all_lang_strings else "english"
        )
        if selected_lang not in self.all_lang_strings:
            self.log(
                f"{selected_lang} Not Found! Using The Default Language - English."
            )
        self.log("Localization setup complete!")

    def get_string(self, keyword: str, args: tuple = None) -> str:
        try:
            # ✅ Robust fallback for Bot Assistant
            lang_code = self.selected_lang or "id"
            if self.bot and not self.clients: # Independent Bot Mode
                lang_code = "id"
            
            # Corrected attribute name: all_lang_strings
            lang = self.all_lang_strings.get(lang_code) or self.all_lang_strings.get("english") or self.all_lang_strings.get("id") or self.all_lang_strings.get("en")
            if not lang:
                return keyword
            
            format_string = lang.get(keyword, keyword)
            if args:
                 return format_string.format(*args) if isinstance(args, tuple) else format_string.format(args)
            return format_string
        except Exception:
            return keyword
    def on_message(self, custom_filters, group=1, bot_mode_unsupported=False, allow_commands=False):
        if not allow_commands:
            custom_filters &= ~filters.command(
                self.cmd_list_s, [self.prefix_owner_user, self.prefix_sudo_users]
            )
        def decorator(func):
            async def wrapper(client, message: Message):
                # ✅ Check if session is disabled
                if client.me.id in self.disabled_sessions:
                    self.log(f"🚫 Session {client.me.id} is disabled. Dropping message {message.id}.", level=logging.DEBUG)
                    return

                if str(message.chat.type).lower().startswith("chattype."):
                    chat_type = str(
                        (str(message.chat.type).lower()).split("chattype.")[1]
                    )
                    message.chat.type = chat_type
                try:
                    await func(client, message)
                except StopPropagation as e:
                    raise StopPropagation from e
                except ContinuePropagation as e:
                    raise ContinuePropagation from e
            self.custom_add_handler(
                cmd=None,
                func_=wrapper,
                filter_s=custom_filters,
                group=group,
                handler_type=MessageHandler,
                bot_mode_unsupported=bot_mode_unsupported,
            )
            return wrapper
        return decorator

    def on_edited_message(self, custom_filters, group=1, bot_mode_unsupported=False, allow_commands=False):
        def decorator(func):
            async def wrapper(client, message: Message):
                # ✅ Check if session is disabled
                if client.me.id in self.disabled_sessions:
                    return

                if str(message.chat.type).lower().startswith("chattype."):
                    chat_type = str(
                        (str(message.chat.type).lower()).split("chattype.")[1]
                    )
                    message.chat.type = chat_type
                try:
                    await func(client, message)
                except StopPropagation as e:
                    raise StopPropagation from e
                except ContinuePropagation as e:
                    raise ContinuePropagation from e
            self.custom_add_handler(
                cmd=None,
                func_=wrapper,
                filter_s=custom_filters,
                group=group,
                handler_type=EditedMessageHandler,
                bot_mode_unsupported=bot_mode_unsupported,
            )
            return wrapper
        return decorator

    def on_callback_query(self, custom_filters, group=1):
        def decorator(func):
            async def wrapper(client, cb: CallbackQuery):
                # ✅ Check if session is disabled
                if client.me and client.me.id in self.disabled_sessions:
                    return
                try:
                    await func(client, cb)
                except StopPropagation as e:
                    raise StopPropagation from e
                except ContinuePropagation as e:
                    raise ContinuePropagation from e
            self.custom_add_handler(
                cmd=None,
                func_=wrapper,
                filter_s=custom_filters,
                group=group,
                handler_type=CallbackQueryHandler,
            )
            return wrapper
        return decorator

    def on_deleted_messages(self, custom_filters, group=1):
        def decorator(func):
            async def wrapper(client, messages: List[Message]):
                # ✅ Check if session is disabled
                if client.me.id in self.disabled_sessions:
                    return
                try:
                    await func(client, messages)
                except StopPropagation as e:
                    raise StopPropagation from e
                except ContinuePropagation as e:
                    raise ContinuePropagation from e
            self.custom_add_handler(
                cmd=None,
                func_=wrapper,
                filter_s=custom_filters,
                group=group,
                handler_type=DeletedMessagesHandler,
            )
            return wrapper
        return decorator

    async def update_on_startup(self):
        if self.config.UPDATE_ON_STARTUP:
            updater_ = Updater(
                repo=self.config.REPO, branch="main", app_url=self.app_url_
            )
            repo = await updater_.init_repo()
            up_rem = await updater_.create_remote_and_fetch(repo)
            await updater_.update_locally(up_rem, repo, None, self, True)

    async def install_apm_from_file(self):
        if os.path.exists("apm_req.txt"):
            async with aiofiles.open("apm_req.txt", "r") as f:
                apm_ = await f.readlines()
                APM_ = APM(self)
                for i in apm_:
                    try:
                        await APM_.install_package(i)
                    except Exception:
                        logging.error(
                            f"Failed to install {i} :: {traceback.format_exc()}"
                        )
                        continue
            return logging.info("Installed all Packages from [apm.txt]")

    async def install_all_apm_packages(self):
        custom_path = "./Main/plugins/custom_app/"
        if os.path.exists(custom_path):
            for it in os.scandir(custom_path):
                if it.is_dir():
                    await self.load_from_directory(f"{it.path}/*.py")
        await self.install_apm_from_file()
        mc = self.db.make_collection("packages")
        APM_ = APM(self)
        packages_ = await mc.find_one({"_id": "APM"})
        if (packages_) and packages_.get("installed_packages"):
            list_of_packages = packages_["installed_packages"]
            for package in list_of_packages:
                try:
                    await APM_.install_package(package)
                except Exception:
                    logging.error(
                        f"Failed to install {package} :: {traceback.format_exc()}"
                    )
                    continue
            if os.path.exists("./Main/plugins/temp_app/"):
                shutil.rmtree("./Main/plugins/temp_app/")
            return logging.info("Installed all Packages.")

    def register_on_cmd(
        self,
        cmd: Union[str, List[str]],
        cmd_help: dict = {},
        pm_only: bool = False,
        group_only: bool = False,
        channel_only: bool = False,
        just_exc: bool = False,
        requires_input: bool = False,
        requires_reply: bool = False,
        bot_mode_unsupported: bool = False,
        group=1,
        disallow_if_sender_is_channel=False,
        is_ultroid: bool = None,
    ):
        if isinstance(cmd, str):
            cmd = [cmd]
        self.cmd_list_s.extend(cmd)
        # ✅ Detect Category based on stack (robust for bridge layers)
        category = "other"
        full_path = inspect.stack()[1].filename
        
        # Search stack for first plugin directory
        for frame in inspect.stack():
            fname = frame.filename.replace("\\", "/")
            if "plugins/userbot" in fname:
                category = "userbot"
                full_path = fname
                frame_to_use = frame.frame
                break
            elif "plugins/bot" in fname:
                category = "bot"
                full_path = fname
                frame_to_use = frame.frame
                break
            elif "plugins/addons" in fname:
                category = "ultroid"
                full_path = fname
                frame_to_use = frame.frame
                break
        
        file_name = os.path.basename(full_path.replace(".py", ""))
        self.plugin_categories[file_name.lower()] = category
        if is_ultroid is None:
            is_ultroid = category == "ultroid"

        # ✅ Detect Module Docstring (for Addon Help)
        if category == "ultroid" and file_name.lower() not in self._module_helps:
            try:
                # Use the module from the frame we found in the loop above
                if 'frame_to_use' in locals():
                    module = inspect.getmodule(frame_to_use)
                    if module and module.__doc__:
                        self._module_helps[file_name.lower()] = module.__doc__.strip()
            except Exception:
                pass

        # ✅ Detect Plugin Version
        plugin_version = "0.0.1"
        try:
            # Check frames for PLUGIN_VERSION
            for frame in inspect.stack():
                caller_globals = frame.frame.f_globals
                if "PLUGIN_VERSION" in caller_globals:
                    plugin_version = caller_globals["PLUGIN_VERSION"]
                    break
                module = inspect.getmodule(frame.frame)
                if module and hasattr(module, "PLUGIN_VERSION"):
                    plugin_version = getattr(module, "PLUGIN_VERSION")
                    break
        except Exception:
            pass

        self.add_help_to_command_list(
            commands=cmd,
            file_name=file_name,
            help_map=cmd_help,
            requires_input=requires_input,
            requires_reply=requires_reply,
            group_only=group_only,
            channel_only=channel_only,
            private_only=pm_only,
            version=plugin_version,
        )
        def decorator(func):
            async def wrapper(client, message: Message):
                # ✅ Check if session is disabled
                if client.me and client.me.id in self.disabled_sessions:
                    return

                # ✅ Initialize defaults at scope start to avoid UnboundLocalError
                is_user_cmd = False
                is_sudo_cmd = False
                is_bot_plugin = False
                is_bot_command = False
                
                # ✅ MULTI-CLIENT CROSS-EXECUTION PREVENTION
                # Prevent Client B from executing commands sent by Client A
                # when both are active in the same instance.
                if message.from_user:
                    sender_id = message.from_user.id
                    current_client_id = client.me.id
                    
                    # ✅ Determine role and prefixes (Optimized cache usage)
                    is_self = sender_id == current_client_id or message.outgoing
                    is_sudo_user = await self.is_sudo(sender_id, client=client) if not is_self else False
                    
                    if self._prefix_cache["apply_type"] == "global":
                        if is_ultroid:
                            u_p = self._prefix_cache.get("ultroid_owner", ",")
                            s_p = self._prefix_cache.get("ultroid_sudo", "?")
                        else:
                            u_p = self._prefix_cache["prefix_owner_user"]
                            s_p = self._prefix_cache["prefix_sudo_users"]
                    else:
                        pa = self._prefix_cache["per_account"].get(current_client_id, {})
                        if is_ultroid:
                            u_p = pa.get("ult_u", self._prefix_cache.get("ultroid_owner", ","))
                            s_p = pa.get("ult_s", self._prefix_cache.get("ultroid_sudo", "?"))
                        else:
                            u_p = pa.get("u", self._prefix_cache["prefix_owner_user"])
                            s_p = pa.get("s", self._prefix_cache["prefix_sudo_users"])

                    is_user_cmd = message.text and message.text.startswith(u_p)
                    is_sudo_cmd = message.text and message.text.startswith(s_p)

                    # ✅ Bot mode check bypass for bot handlers (Check early)
                    is_bot_plugin = self.plugin_categories.get(file_name.lower()) == "bot"
                    is_bot_command = message.text and message.text.startswith("/")

                    # ✅ ENFORCE STRICT PREFIX SEPARATION (Requirement 1.A) - Bypass for Bot Commands
                    if not (is_bot_plugin and is_bot_command):
                        if is_self:
                            # Owner session ONLY responds to User Prefix
                            if not is_user_cmd:
                                return
                        else:
                            # Sudo user ONLY responds to Sudo Prefix
                            if not is_sudo_cmd:
                                return

                    # ✅ FIXED: SMART SUDO HANDLING for Multi-Client Setup
                    if is_sudo_cmd and is_sudo_user:
                        # Check if sudo is enabled for THIS specific client
                        sudo_apply_type = self._sudo_settings_cache["apply_type"]
                        
                        if sudo_apply_type == "per_account":
                            # Per-account mode: Each client handles sudo independently based on their own settings
                            sudo_enabled_for_this_client = self._sudo_settings_cache["per_account_enabled"].get(current_client_id, True)
                            if not sudo_enabled_for_this_client:
                                # This client has sudo disabled, skip
                                return
                            # ✅ Allow this client to handle sudo command
                        else:
                            # Global mode: ALL clients with global sudo enabled will respond
                            # Check if global sudo is enabled
                            if not self._sudo_settings_cache["enabled_global"]:
                                # Global sudo is disabled, skip
                                return
                            # ✅ Allow ALL clients to handle sudo command (no deduplication in global mode)

                    # ✅ CROSS-EXECUTION PREVENTION for multiple userbot sessions
                    if sender_id != current_client_id and not is_sudo_cmd:
                        # If sender is another active client in this instance, ignore
                        other_client_ids = [c.me.id for c in self.clients if hasattr(c, 'me')]
                        if sender_id in other_client_ids:
                            return
                elif message.outgoing:
                    # ✅ CHANNEL POST HANDLING: from_user is None but message is outgoing.
                    # message.outgoing is ONLY True for messages sent by THIS userbot session.
                    # This is safe — it cannot be spoofed by other channels or users.
                    # NOTE: We intentionally do NOT check message.sender_chat here,
                    # because sender_chat could match ANY channel (including ones we don't own),
                    # which would be a critical security hole.
                    current_client_id = client.me.id
                    if self._prefix_cache["apply_type"] == "global":
                        if is_ultroid:
                            u_p = self._prefix_cache.get("ultroid_owner", ",")
                        else:
                            u_p = self._prefix_cache["prefix_owner_user"]
                    else:
                        pa = self._prefix_cache["per_account"].get(current_client_id, {})
                        if is_ultroid:
                            u_p = pa.get("ult_u", self._prefix_cache.get("ultroid_owner", ","))
                        else:
                            u_p = pa.get("u", self._prefix_cache["prefix_owner_user"])
                    
                    is_user_cmd = message.text and message.text.startswith(u_p)
                    if not is_user_cmd:
                        return
                
                # ✅ DEDUPLICATION for Self-Messages (Distant execution from phone)
                if not message.outgoing and message.from_user and message.from_user.is_self:
                    if self.clients and client != self.clients[0]:
                        return

                if str(message.chat.type).lower().startswith("chattype."):
                    chat_type = str(
                        (str(message.chat.type).lower()).split("chattype.")[1]
                    )
                    message.chat.type = chat_type
                
                # ✅ Bot mode check bypass for bot handlers
                is_bot_plugin = self.plugin_categories.get(file_name.lower()) == "bot"
                is_bot_command = message.text and message.text.startswith("/")
                
                if message.text:
                    if not (is_bot_plugin and is_bot_command):
                        # Final prefix validation (already gated by role logic above, but kept for safety)
                        if not (is_user_cmd or is_sudo_cmd):
                            return

                chat_type = message.chat.type
                input_ = message.user_input
                
                # ✅ Validation checks (bot commands already allowed above)
                if requires_input and input_ in ["", " ", None]:
                    return await message.handle_message("INPUT_REQUIRED")
                if requires_reply and not message.reply_to_message:
                    return await message.handle_message("REPLY_REQUIRED")
                if group_only and chat_type not in ["supergroup", "group"]:
                    return await message.handle_message("GROUP_ONLY")
                if channel_only and chat_type != "channel":
                    return await message.handle_message("CHANNEL_ONLY")
                if pm_only and chat_type != "private":
                    return await message.handle_message("PM_ONLY")
                if (
                    message.reply_to_message
                    and disallow_if_sender_is_channel
                    and message.reply_to_message.sender_chat
                    and message.reply_to_message.sender_chat.id
                ):
                    return await message.handle_message("DISALLOW_SENDER_CHAT")
                if just_exc:
                    await func(client, message)
                else:
                    try:
                        # Re-verify filters with correct context if needed
                        from Main.utils.custom_filters import parse_
                        if not await parse_(client, message, cmd, is_ultroid=is_ultroid, disable_sudo=disabled_sudo):
                            return
                        await func(client, message)
                    except StopPropagation as e:
                        raise StopPropagation from e
                    except (
                        MessageNotModified,
                        MessageIdInvalid,
                        UserNotParticipant,
                        MessageEmpty,
                    ):
                        pass
                    except ContinuePropagation as e:
                        raise ContinuePropagation from e
                    except FloodWait as e:
                        self.log(f"FloodWait: {e.value}s untuk command {cmd}")
                        await asyncio.sleep(e.value)
                    except Exception as _be:
                        # ✅ LOG ERROR TAPI JANGAN CRASH
                        error_msg = f"Command '{cmd}' error: {type(_be).__name__}: {str(_be)[:100]}"
                        self.log(error_msg, level=logging.ERROR)
                        
                        # Coba kirim error ke user
                        try:
                            await message.edit(f"❌ Error: {str(_be)[:100]}")
                        except:
                            pass
                        
                        # Coba kirim error log
                        try:
                            await self.send_error(client, cmd, str(_be)[:500], file_name)
                        except Exception as send_err:
                            self.log(f"Failed to send error report: {send_err}", level=logging.DEBUG)
            disabled_sudo = False
            if not self.training_wheels_protocol:
                if disabled_sudo := (
                    all(
                        (
                            item in list(cmd)
                            for item in list(self.disabled_sudo_plugin_list)
                        )
                    )
                    if self.disabled_sudo_plugin_list
                    else False
                ):
                    self.log(f"Not Loading - Disabled : {cmd[0]} For sudo!")
            self.custom_add_handler(
                cmd,
                wrapper,
                disable_sudo=disabled_sudo,
                is_ultroid=is_ultroid,
                group=group,
                bot_mode_unsupported=bot_mode_unsupported,
            )
            return wrapper
        return decorator

    def add_help_to_command_list(
        self,
        commands: Union[List[str], str],
        file_name: str,
        help_map: dict,
        requires_input: bool,
        requires_reply: bool,
        group_only: bool,
        channel_only: bool,
        private_only: bool,
        version: str = "unknown",
    ):
        example = html.escape(help_map.get("example", "No example available"))
        help_text = html.escape(
            help_map.get("help", "Sorry, No help available for this command")
        )
        usage = help_map.get("usage")
        if usage:
            usage = html.escape(usage)
        user_args = help_map.get("user_args")
        detail = help_map.get("detail")
        if isinstance(commands, str):
            commands = [commands]
        if file_name not in self.cmd_list:
            self.cmd_list[file_name] = [
                {
                    "commands": commands,
                    "help": help_text,
                    "usage": usage,
                    "example": example,
                    "user_args": user_args,
                    "requires_input": requires_input,
                    "requires_reply": requires_reply,
                    "group_only": group_only,
                    "channel_only": channel_only,
                    "private_only": private_only,
                    "detail": detail,
                    "version": version,
                }
            ]
        elif commands[0] not in [
            x.get("commands", [""])[0] for x in self.cmd_list[file_name]
        ]:
            self.cmd_list[file_name].append(
                {
                    "commands": commands,
                    "help": help_text,
                    "usage": usage,
                    "example": example,
                    "user_args": user_args,
                    "requires_input": requires_input,
                    "requires_reply": requires_reply,
                    "group_only": group_only,
                    "channel_only": channel_only,
                    "private_only": private_only,
                    "detail": detail,
                    "version": version,
                }
            )

    def custom_add_handler(
        self,
        cmd=None,
        func_=None,
        filter_s=None,
        disable_sudo=False,
        is_ultroid=False,
        group=0,
        handler_type=MessageHandler,
        bot_mode_unsupported=False,
    ):
        if not self.training_wheels_protocol:
            self.config.PREFIX_OWNER_USER
            basic_filters = (
                filter_s
                or user_filters(list(cmd) if cmd else [], is_ultroid=is_ultroid, disable_sudo=disable_sudo)
                & ~filters.via_bot
                & ~filters.forwarded
            )
            for client in self.clients:
                # ✅ DEDUPLICATION Logic for Sessions
                img_key_val = None
                if cmd:
                    if isinstance(cmd, (list, tuple)): img_key_val = tuple(sorted(list(cmd)))
                    else: img_key_val = (cmd,)
                    
                    registry_key = (f"session_{client.me.id if hasattr(client, 'me') else client.name}", img_key_val, handler_type.__name__)
                    if registry_key in self.handler_registry:
                        continue
                    
                    self.handler_registry.add(registry_key)

                client.add_handler(
                    handler_type(func_, filters=basic_filters), group=group
                )
                
        if self.bot_mode and not bot_mode_unsupported and not self.loaded_bot_cmds:
            # ✅ DEDUPLICATION Logic for Bot Assistant
            bot_cmd_key = None
            if cmd:
                if isinstance(cmd, (list, tuple)): bot_cmd_key = tuple(sorted(list(cmd)))
                else: bot_cmd_key = (cmd,)
                
                bot_registry_key = ("bot_assistant", bot_cmd_key, handler_type.__name__)
                if bot_registry_key in self.handler_registry:
                    return # Already registered to bot
                
                self.handler_registry.add(bot_registry_key)

            # ✅ FIXED: Use dynamic is_sudo_filter instead of static filters.user(self.auth_users)
            # This ensures users added via UI are authorized immediately.
            bot_f = filter_s or self.is_sudo_filter & filters.command(
                list(cmd) if cmd else [], ["/", "|"] # removed "!" to avoid conflict with userbot sudo handler
            )
            self.bot.add_handler(handler_type(func_, filters=bot_f), group=group)

            # ✅ Register to Custom Bots
            if hasattr(self, 'bot_manager') and self.bot_manager.custom_bots:
                for custom_bot in self.bot_manager.custom_bots.values():
                    try:
                        # Deduplication for custom bots
                        cb_cmd_key = None
                        if cmd:
                            if isinstance(cmd, (list, tuple)): cb_cmd_key = tuple(sorted(list(cmd)))
                            else: cb_cmd_key = (cmd,)
                        cb_reg_key = (f"custom_bot_{custom_bot.me.id if hasattr(custom_bot, 'me') else 'pending'}", cb_cmd_key, handler_type.__name__)
                        if cb_reg_key not in self.handler_registry:
                            custom_bot.add_handler(handler_type(func_, filters=bot_f), group=group)
                            self.handler_registry.add(cb_reg_key)
                    except Exception as e:
                        self.log(f"⚠️ Failed to add handler to custom bot: {e}", level=logging.WARNING)

    async def _resource_monitor_loop(self):
        """Background loop to monitor system resources (CPU/RAM) and alert if > 90%."""
        self.log("🚀 Resource monitor loop started.", level=logging.INFO)
        alert_sent = False
        while True:
            try:
                stats = self.get_system_stats()
                cpu = stats.get("cpu", {}).get("percent", 0)
                ram = stats.get("ram", {}).get("percent", 0)
                
                # Check thresholds
                is_high_cpu = isinstance(cpu, (int, float)) and cpu > 90
                is_high_ram = isinstance(ram, (int, float)) and ram > 90
                
                if is_high_cpu or is_high_ram:
                    if not alert_sent:
                        usage_info = ""
                        if is_high_cpu: usage_info += f"🖥 <b>CPU Usage:</b> <code>{cpu}%</code>\n"
                        if is_high_ram: usage_info += f"💾 <b>RAM Usage:</b> <code>{ram}%</code>\n"
                        
                        alert_msg = (
                            "⚠️ <b>USERBOT RESOURCE WARNING</b>\n\n"
                            f"{usage_info}\n"
                            "‼️ <b>Tindakan diperlukan:</b>\n"
                            "Server Anda hampir mencapai kapasitas maksimal. Mohon periksa proses yang berjalan untuk menghindari crash atau restart tak terduga."
                        )
                        
                        # Kirim ke log group menggunakan bot client
                        if hasattr(self, 'bot') and self.bot.is_connected and self.log_chat:
                            try:
                                await self.bot.send_message(
                                    chat_id=self.log_chat,
                                    text=f"<blockquote expandable>{alert_msg}</blockquote>",
                                    parse_mode=enums.ParseMode.HTML
                                )
                                alert_sent = True
                                self.log("‼️ High resource usage alert sent to log group.", level=logging.WARNING)
                            except Exception as e:
                                self.log(f"Failed to send resource alert: {e}", level=logging.ERROR)
                else:
                    # Reset alert status if usage drops below 85% for stability
                    if alert_sent:
                        cpu_safe = not isinstance(cpu, (int, float)) or cpu < 85
                        ram_safe = not isinstance(ram, (int, float)) or ram < 85
                        if cpu_safe and ram_safe:
                            alert_sent = False
                            self.log("✅ Resource levels normalized.", level=logging.INFO)
                
            except Exception as e:
                self.log(f"Error in resource monitor: {e}", level=logging.ERROR)
            
            await asyncio.sleep(60) # Cek setiap 1 menit

    async def _setup(self, restart=False, *args, **kwargs):
        if not os.path.isdir("cache"):
            os.mkdir("cache")
        await self.setup_localization()
        self.prefix_sudo_users = await self.config.get_env("PREFIX_SUDO_USERS") or "!"
        self.prefix_owner_user = await self.config.get_env("PREFIX_OWNER_USER") or "."
        self.bot_handler = await self.config.get_env("BOT_HANDLER") or "/"
        self.disabled_sudo_plugin_list = await self.config.get_env(
            "DISABLED_SUDO_CMD_LIST", []
        )
        self.log_chat = self.config.digit_wrap(await self.config.get_env("LOG_CHAT_ID"))
        if self.log_chat is None:
            logger.warning("LOG_CHAT_ID not set. Mention notifications will not be sent. Please set LOG_CHAT_ID in .env or config.")
        self.bot_mode = (str(await self.config.get_env("BOT_MODE"))).lower() in {
            "yes",
            "true",
            "enable",
        }
        if not restart:
            await self.initialize_telegram_sessions(*args, **kwargs)
        
        # ✅ Load sudo users from DB into cache
        await self.refresh_sudo_cache()
        
        await self.update_cache()

    #
    def get_system_stats(self) -> dict:
        """
        Dapatkan statistik sistem dengan fallback yang aman untuk lingkungan terbatas (Sevalla).
        """
        try:
            import psutil
            # Gunakan psutil jika tersedia
            # ✅ PERFORMANCE: interval=0 untuk instant read (non-blocking)
            cpu_percent = round(psutil.cpu_percent(interval=0), 1)
            cpu_cores = psutil.cpu_count(logical=False) or os.cpu_count() or "N/A"
            cpu_threads = psutil.cpu_count(logical=True) or os.cpu_count() or "N/A"
            
            ram = psutil.virtual_memory()
            ram_total_gb = round(ram.total / (1024**3), 2)
            ram_used_gb = round(ram.used / (1024**3), 2)
            ram_percent = ram.percent
            
            swap_used_gb = round(psutil.swap_memory().used / (1024**3), 2) if hasattr(psutil, 'swap_memory') else 0.0
            
        except (ImportError, Exception) as e:
            # Fallback tanpa psutil
            self.log(f"psutil tidak tersedia atau error: {e}. Menggunakan fallback.", level=logging.WARNING)
            
            cpu_percent = "N/A"
            cpu_cores = os.cpu_count() or "N/A"
            cpu_threads = os.cpu_count() or "N/A"
            
            # Gunakan resource untuk estimasi RAM (dalam KB → konversi ke MB/GB dengan benar)
            try:
                ram_used_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                # Di Linux: ru_maxrss dalam KB → konversi ke GB
                ram_used_gb = round(ram_used_kb / (1024**2), 2)  # KB → GB
                ram_total_gb = "N/A"
                ram_percent = "N/A"
            except Exception:
                ram_used_gb = "N/A"
                ram_total_gb = "N/A"
                ram_percent = "N/A"
            
            swap_used_gb = "N/A"

        # Proses info (selalu bisa diakses)
        try:
            process_memory_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            process_memory_mb = round(process_memory_kb / 1024, 2)  # KB → MB
            process_threads = threading.active_count()
        except Exception:
            process_memory_mb = "N/A"
            process_threads = "N/A"

        # Component Statistics
        plugin_paths = [
            "Main/plugins/bot/*.py",
            "Main/plugins/userbot/*.py",
            "Main/plugins/addons/**/*.py"
        ]
        total_plugins = 0
        for p in plugin_paths:
            total_plugins += len([f for f in glob.glob(p, recursive=True) if os.path.isfile(f)])

        total_sessions = len(self.clients)
        assistant_bot = 1 if hasattr(self, 'bot') and self.bot.is_connected else 0
        custom_bots = len(self.bot_manager.custom_bots) if hasattr(self, 'bot_manager') else 0

        return {
            "cpu": {
                "percent": cpu_percent,
                "cores": cpu_cores,
                "threads": cpu_threads,
                "freq": round(psutil.cpu_freq().current, 1) if hasattr(psutil, "cpu_freq") else 0
            },
            "ram": {
                "total": ram_total_gb,
                "used": ram_used_gb,
                "percent": ram_percent,
                "swap_used": swap_used_gb
            },
            "process": {
                "memory_mb": process_memory_mb,
                "threads": process_threads,
                "uptime": Essentials.get_readable_time(time.time() - self.start_time)
            },
            "system": {
                "platform": platform.system(),
                "python": platform.python_version(),
                "pyrogram": pyrogram_version
            },
            "components": {
                "plugins": total_plugins,
                "sessions": total_sessions,
                "bot": assistant_bot,
                "custom_bots": custom_bots
            }
        }

    def format_startup_log_blockquote(
        self,
        total_sessions: int,
        success_count: int,
        failed_count: int,
        owner_id: int,
        branch: str,
        db_type: str,
        version: str,
        startup_time: str,
        system_stats: dict = None,
        warnings: dict = None
    ) -> str:
        """
        Format startup log dengan blockquote expandable untuk tampilan yang lebih rapi.
        """
        import html as html_module
        
        # Header (di luar blockquote)
        message = "<b>✅ All clients finished sending startup logs!</b>\n\n"
        
        # Mulai blockquote expandable
        message += "<blockquote expandable>\n"
        
        # Section 1: Client Statistics
        message += "<b>📊 Client Statistics</b>\n"
        message += f"• Total Session: {total_sessions} user + 1 bot\n"
        message += f"• Success: {success_count} clients\n"
        message += f"• Failed: {failed_count} clients\n"
        message += f"{'━' * 20}\n"
        
        # Section 2: System Information
        message += "<b>ℹ️ System Information</b>\n"
        message += f"• Owner ID: <code>{html_module.escape(str(owner_id))}</code>\n"
        message += f"• Branch: {html_module.escape(branch)}\n"
        message += f"• Database: {html_module.escape(db_type)}\n"
        message += f"• Version: {html_module.escape(version)}\n"
        message += f"• Time: {html_module.escape(startup_time)}\n"
        message += f"{'━' * 20}\n"
        
        # Section 3: System Statistics (jika ada)
        if system_stats:
            cpu_data = system_stats.get('cpu', {})
            ram_data = system_stats.get('ram', {})
            proc_data = system_stats.get('process', {})
            sys_data = system_stats.get('system', {})
            
            cpu_percent = cpu_data.get('percent', 'N/A')
            cpu_cores = cpu_data.get('cores', 'N/A')
            cpu_threads = cpu_data.get('threads', 'N/A')
            ram_used = ram_data.get('used', 'N/A')
            ram_total = ram_data.get('total', 'N/A')
            ram_percent = ram_data.get('percent', 'N/A')
            proc_memory = proc_data.get('memory_mb', 'N/A')
            proc_threads = proc_data.get('threads', 'N/A')
            uptime = proc_data.get('uptime', 'N/A')
            platform_name = sys_data.get('platform', 'Unknown')
            python_version = sys_data.get('python', 'Unknown')
            pyrogram_version_val = sys_data.get('pyrogram', 'Unknown')
            
            message += "<b>📊 System Statistics</b>\n"
            message += f"• CPU: {cpu_percent}% ({cpu_cores} core/{cpu_threads} thread)\n"
            message += f"• RAM: {ram_used}GB/{ram_total}GB ({ram_percent}%)\n"
            message += f"• Proses: {proc_memory}MB ({proc_threads} thread)\n"
            message += f"• Uptime: {uptime}\n"
            message += f"• Platform: {platform_name} | Python {python_version} | Pyrogram {pyrogram_version_val}\n"
        
        # Section 4: Resource Warning (conditional)
        if warnings:
            cpu_warning = warnings.get('cpu')
            ram_warning = warnings.get('ram')
            
            if cpu_warning or ram_warning:
                message += f"{'━' * 20}\n"
                message += "<b>⚠️ Resource Warning</b>\n"
                if cpu_warning:
                    message += f"• CPU Usage: {cpu_warning}%\n"
                if ram_warning:
                    message += f"• RAM Usage: {ram_warning}%\n"
                message += "‼️ Tindakan diperlukan:\n"
                message += "Server Anda hampir mencapai kapasitas maksimal. Mohon periksa proses yang berjalan untuk menghindari crash atau restart tak terduga.\n"
        
        # Tutup blockquote
        message += "</blockquote>"
        
        return message

    async def _run(self):
        """Main loop dengan state management dan restart terkontrol"""
        restart_count = 0
        last_restart_time = 0
        MAX_RESTARTS_PER_HOUR = 5
        
        while True:
            try:
                current_time = time.time()
                
                # ✅ CEK RESTART BERLEBIHAN
                if current_time - last_restart_time < 3600:
                    restart_count += 1
                    if restart_count >= MAX_RESTARTS_PER_HOUR:
                        self.log("❌ RESTART BERLEBIHAN! Menunggu 10 menit...", level=logging.CRITICAL)
                        await asyncio.sleep(600)
                        restart_count = 0
                else:
                    restart_count = 0
                    
                last_restart_time = current_time
                
                # ✅ LOAD MODUL
                await self.load_all_modules()

                system_stats = self.get_system_stats()

                # ✅ TAMPILKAN STATISTIK SISTEM SETELAH SEMUA MODUL DILOAD
                # ✅ PERBAIKAN: Aman terhadap fallback tanpa psutil
                                # ✅ PERBAIKAN FINAL: Akses semua key dengan .get() + fallback default
                cpu_percent = system_stats.get('cpu', {}).get('percent', 'N/A')
                cpu_cores = system_stats.get('cpu', {}).get('cores', 'N/A')
                cpu_threads = system_stats.get('cpu', {}).get('threads', 'N/A')
                ram_used = system_stats.get('ram', {}).get('used', 'N/A')
                ram_total = system_stats.get('ram', {}).get('total', 'N/A')
                ram_percent = system_stats.get('ram', {}).get('percent', 'N/A')
                proc_memory = system_stats.get('process', {}).get('memory_mb', 'N/A')
                proc_threads = system_stats.get('process', {}).get('threads', 'N/A')
                uptime = system_stats.get('process', {}).get('uptime', 'N/A')
                platform_name = system_stats.get('system', {}).get('platform', 'Unknown')
                python_version = system_stats.get('system', {}).get('python', 'Unknown')
                pyrogram_version_safe = system_stats.get('system', {}).get('pyrogram', pyrogram_version)  # fallback ke global

                comp_data = system_stats.get('components', {})
                total_plugins = comp_data.get('plugins', 0)
                total_sessions = comp_data.get('sessions', 0)
                total_bots = comp_data.get('bot', 0)
                custom_bots = comp_data.get('custom_bots', 0)

                system_info = (
                    f"📊 <b>SISTEM STATISTIK</b>\n"
                    f"{'━' * 20}\n"
                    f"<b>🖥 RESOURCES</b>\n"
                    f"• CPU: <code>{cpu_percent}%</code> "
                    f"({cpu_cores}C/{cpu_threads}T)\n"
                    f"• RAM: <code>{ram_used}GB/{ram_total}GB</code> "
                    f"({ram_percent}%)\n"
                    f"• Proses: <code>{proc_memory}MB</code> "
                    f"({proc_threads} thread)\n"
                    f"• Uptime: <code>{uptime}</code>\n\n"
                    f"<b>⚙️ COMPONENTS</b>\n"
                    f"• Plugins: <code>{total_plugins}</code>\n"
                    f"• Sessions: <code>{total_sessions}</code>\n"
                    f"• Bots: <code>{total_bots} bot + {custom_bots} custom</code>\n\n"
                    f"<b>🌐 PLATFORM</b>\n"
                    f"• {platform_name} | "
                    f"Python {python_version} | Pyrogram {pyrogram_version_safe}"
                )
               
                # Kirim ke log chat
                if hasattr(self, 'bot') and self.bot.is_connected and self.log_chat:
                    try:
                        await self.bot.send_message(
                            self.log_chat,
                            f"<blockquote expandable>{system_info}</blockquote>",
                            link_preview_options=LinkPreviewOptions(is_disabled=True),
                            parse_mode=enums.ParseMode.HTML
                        )
                    except Exception as e:
                        self.log(f"Gagal kirim stats ke log chat: {e}", level=logging.WARNING)

                # Tampilkan di console
                border = "═" * 50
                print(f"\n{border}")
                print("📊 SISTEM STATISTIK".center(50))
                print(border)
                print(f" [🖥] CPU     : {cpu_percent}% ({cpu_cores}C/{cpu_threads}T)")
                print(f" [💾] RAM     : {ram_used}GB / {ram_total}GB ({ram_percent}%)")
                print(f" [🚀] Proses  : {proc_memory}MB | {proc_threads} thread")
                print(f" [⏱] Uptime  : {uptime}")
                print("-" * 50)
                print(f" [⚙️] Plugins : {total_plugins}")
                print(f" [👤] Sessions: {total_sessions}")
                print(f" [🤖] Bots    : {total_bots} assistant + {custom_bots} custom")
                print("-" * 50)
                print(f" [🌐] System  : {platform_name} | Python {python_version}")
                print(f" [📦] Pyrogram: {pyrogram_version_safe}")
                print(f"{border}\n")

                print(self.banner)
                branch_info = get_current_git_branch()
                self.log(f"🌿 Branch: {branch_info}")
                self.log(f"🚀 Altruix v{self.__version__} berjalan!")
                
                if self.training_wheels_protocol:
                    self.log("⚠️ Altruix is in [TWP] mode - userbot features disabled!", level=30)
                
                # ✅ HEALTH CHECK SEBELUM IDLE
                await self._health_check()

                try:
                    # ✅ Gunakan psutil (cross-platform) sebagai ganti resource module
                    process = psutil.Process(os.getpid())
                    process_memory_mb = round(process.memory_info().rss / (1024 * 1024), 2)
                    self.log(f"MemoryWarning: Memori proses = {process_memory_mb} MB")
                except Exception as e:
                    self.log(f"Gagal cek penggunaan memori: {e}", level=logging.WARNING)

                
                # ✅ JALANKAN IDLE DENGAN MONITORING
                await self._safe_idle()
                
                # Jika idle berhenti tanpa error, keluar dari loop
                self.log("🛑 Idle stopped, shutting down...")
                break
                
            except KeyboardInterrupt:
                self.log("👋 Received keyboard interrupt. Shutting down gracefully...")
                break
            except Exception as e:
                error_msg = f"🔥 CRITICAL ERROR: {type(e).__name__}: {str(e)[:200]}"
                self.log(error_msg, level=logging.CRITICAL)
                self.log(f"📋 Traceback: {traceback.format_exc()}", level=logging.DEBUG)
                
                try:
                    # Kirim notifikasi error
                    if hasattr(self, 'bot') and self.bot.is_connected:
                        await self.bot.send_message(
                            self.config.OWNER_ID,
                            f"⚠️ <b>Altruix Runtime Error</b>\n"
                            f"• Error: <code>{type(e).__name__}</code>\n"
                            f"• Pesan: {str(e)[:100]}\n"
                            f"• Waktu: {datetime.now().strftime('%H:%M:%S')}\n"
                            f"• Restart ke: {restart_count}",
                            link_preview_options=LinkPreviewOptions(is_disabled=True)
                        )
                except Exception:
                    pass
                
                # ✅ DELAY ANTAR RESTART (exponential backoff)
                delay = min(300, 10 * (2 ** restart_count))
                self.log(f"⏳ Restart dalam {delay} detik... (Restart #{restart_count})", level=logging.WARNING)
                await asyncio.sleep(delay)

    async def _safe_idle(self):
        """Idle dengan heartbeat dan monitoring"""
        try:
            # Buat task untuk monitoring
            monitor_task = asyncio.create_task(self._monitor_connections())
            health_task = asyncio.create_task(self._heartbeat_monitor())
            res_monitor_task = asyncio.create_task(self._resource_monitor_loop())
            backup_task = asyncio.create_task(self._auto_backup_loop())
            
            # Jalankan idle
            await idle()
            
            # Bersihkan task
            monitor_task.cancel()
            health_task.cancel()
            
            try:
                await asyncio.gather(monitor_task, health_task, return_exceptions=True)
            except asyncio.CancelledError:
                pass
                
        except asyncio.CancelledError:
            self.log("Monitoring tasks cancelled")
        except Exception as e:
            raise e

    async def _monitor_connections(self):
        """Monitor koneksi client secara berkala"""
        while True:
            try:
                await asyncio.sleep(60)
                
                # Cek koneksi bot
                if hasattr(self, 'bot') and not self.bot.is_connected:
                    self.log("🤖 Bot disconnected, attempting reconnect...")
                    try:
                        await self.bot.start()
                    except Exception as e:
                        self.log(f"Failed to reconnect bot: {e}")
                
                # Cek koneksi user sessions
                for idx, client in enumerate(self.clients):
                    if not client.is_connected:
                        self.log(f"👤 User session {idx} disconnected")
                        # Bisa coba reconnect di sini jika perlu
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.log(f"Monitor error: {e}", level=logging.DEBUG)

    async def _heartbeat_monitor(self):
        """Kirim heartbeat untuk memastikan bot hidup"""
        while True:
            try:
                await asyncio.sleep(300)
                
                uptime = Essentials.get_readable_time(time.time() - self.start_time)
                self.log(f"💓 Heartbeat - Uptime: {uptime}")
                
                # 🔍 Tambahkan pemantauan memori di heartbeat
                try:
                    # ✅ Gunakan psutil (cross-platform) sebagai ganti resource module
                    process = psutil.Process(os.getpid())
                    mem_mb = round(process.memory_info().rss / (1024 * 1024), 2)
                    self.log(f"📊 Heartbeat - Memori: {mem_mb} MB")
                except Exception:
                    pass  # Abaikan jika gagal
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.log(f"Heartbeat error: {e}", level=logging.DEBUG)

    async def _health_check(self):
        """Cek kesehatan semua komponen sebelum idle"""
        checks_passed = 0
        total_checks = 0
        
        # ✅ PERFORMANCE: Jalankan semua checks secara parallel dengan timeout
        async def check_database():
            try:
                await asyncio.wait_for(self.db.ping(), timeout=3.0)
                self.log("✅ Database connection: OK")
                return True
            except asyncio.TimeoutError:
                self.log("❌ Database connection: TIMEOUT", level=logging.ERROR)
                return False
            except Exception as e:
                self.log(f"❌ Database connection: FAILED - {e}", level=logging.ERROR)
                return False
        
        async def check_bot():
            try:
                if hasattr(self, 'bot') and self.bot.is_connected:
                    await asyncio.wait_for(self.bot.get_me(), timeout=3.0)
                    self.log("✅ Bot connection: OK")
                    return True
                return False
            except asyncio.TimeoutError:
                self.log("❌ Bot connection: TIMEOUT", level=logging.ERROR)
                return False
            except Exception as e:
                self.log(f"❌ Bot connection: FAILED - {e}", level=logging.ERROR)
                return False
        
        async def check_user_session(idx, client):
            try:
                if client.is_connected:
                    await asyncio.wait_for(client.get_me(), timeout=3.0)
                    self.log(f"✅ User session {idx}: OK")
                    return True
                return False
            except asyncio.TimeoutError:
                self.log(f"❌ User session {idx}: TIMEOUT", level=logging.WARNING)
                return False
            except Exception as e:
                self.log(f"❌ User session {idx}: FAILED - {e}", level=logging.WARNING)
                return False
        
        # ✅ PERFORMANCE: Run all checks in parallel
        tasks = [check_database(), check_bot()]
        tasks.extend([check_user_session(idx, client) for idx, client in enumerate(self.clients)])
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        checks_passed = sum(1 for r in results if r is True)
        total_checks = len(results)

        # Memory check (non-blocking)
        try:
            mem_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
            if mem_mb > 7000:  # 7GB dari 8GB
                self.log("MemoryWarning: Memori hampir penuh! Pertimbangkan restart manual.", level=logging.WARNING)
        except Exception:
            pass
        
        success_rate = (checks_passed / total_checks * 100) if total_checks > 0 else 0
        self.log(f"📊 Health Check: {checks_passed}/{total_checks} passed ({success_rate:.1f}%)")
        
        if success_rate < 50:
            self.log("⚠️ Health check warning: Beberapa komponen bermasalah", level=logging.WARNING)
            return False
        return True

    async def graceful_shutdown(self, signal=None):
        """Shutdown yang aman"""
        self.log(f"🚦 Received shutdown signal: {signal}")
        
        try:
            # Stop semua clients
            for client in self.clients:
                try:
                    await client.stop()
                except:
                    pass
            
            # Stop bot
            if hasattr(self, 'bot') and self.bot.is_connected:
                await self.bot.stop()
                
            # Stop executor
            self.executor.shutdown(wait=True)
            
            self.log("✅ Shutdown completed gracefully")
            
        except Exception as e:
            self.log(f"❌ Error during shutdown: {e}", level=logging.ERROR)
        
        # Keluar dari program
        sys.exit(0)

    async def _auto_backup_loop(self):
        """Background loop for automatic database backups."""
        self.log("🚀 Auto-backup loop started.", level=logging.INFO)
        while True:
            try:
                # Get settings
                is_enabled = await self.config.get_env("AUTO_BACKUP_ENABLED") == "true"
                interval_str = await self.config.get_env("AUTO_BACKUP_INTERVAL") or "24h"
                
                if not is_enabled:
                    await asyncio.sleep(600) # Check every 10 mins if it got enabled
                    continue
                
                # Convert interval to seconds
                # 1h, 3h, 6h, 12h, 24h, 1w
                try:
                    unit = interval_str[-1].lower()
                    amount = int(interval_str[:-1])
                    if unit == 'h': seconds = amount * 3600
                    elif unit == 'w': seconds = amount * 7 * 24 * 3600
                    else: seconds = 24 * 3600 # Fallback 24h
                except (ValueError, IndexError):
                    seconds = 24 * 3600
                
                # Wait for the interval
                await asyncio.sleep(seconds)
                
                # Perform backup
                if self.log_chat and self.bot and self.bot.is_connected:
                    from Main.utils.backup_helpers import upload_db_backup
                    success = await upload_db_backup(self.bot, self.log_chat)
                    if success:
                        self.log("📦 Auto-backup completed successfully.", level=logging.INFO)
                        # Save last backup time
                        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        # ✅ Fixed: Use upsert=True to ensure key is created if missing
                        await self.config.add_env_to_db("LAST_BACKUP_TIME", now_str, upsert=True)
                    else:
                        self.log("❌ Auto-backup failed.", level=logging.ERROR)
                else:
                    self.log("⚠️ Auto-backup skipped: Log chat or Bot not ready.", level=logging.WARNING)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.log(f"Auto-backup loop error: {e}", level=logging.DEBUG)
                await asyncio.sleep(60)

    async def _test(self):
        dev_chat_id = -1002653859864
        try:
            await self.load_all_modules()
            mess = None
            if self.training_wheels_protocol:
                self.log("No user session found, Running in [TWP] mode.", level=50)
            else:
                self.log("Testing User session.", level=30)
                for each in self.clients:
                    mess = await each.send_message(
                        dev_chat_id,
                        f"""commit: <a href='https://github.com/Altruix/Altruix/commit/{os.getenv("COMMIT_SHA")}'>{os.getenv('COMMIT_NAME')}</a> was successfully tested!""",
                    )
                    await each.stop()
            self.log("Testing bot.", level=30)
            await self.bot.send_message(
                dev_chat_id,
                "Test completed.",
                reply_to_message_id=mess.id if mess else None,
            )
            self.log("Test completed.", level=30)
        except Exception:
            self.log(f"Test failed: {(await Paste(format_exc()).paste())[1]}", level=40)
            quit(1)

    async def initialize_telegram_sessions(self, *args, **kwargs) -> None:
        try:
            self.bot = Client(
                name="Altruix[bot]",
                api_id=self.config.API_ID,
                api_hash=self.config.API_HASH,
                bot_token=self.config.BOT_TOKEN,
                workdir="cache",
                loop=self.loop,
                *args,
                **kwargs,
            )
            await self.bot.start()
            self.bot_info = await self.bot.get_me()
            self.bot.myself = self.bot_info
            self.log(f"Assistant : Logged in as @{self.bot_info.username}")
        except Exception as e:
            self.log(f"CRITICAL: Failed to start bot assistant: {e}", level=50)
            raise
        try:
            if string_sessions := self.config.SESSIONS:
                self.log(self.get_string("reading_session"))
                await self.config.sync_env_to_db("SESSIONS", string_sessions)
            else:
                self.log(self.get_string("search_session_db"))
                string_sessions = await self.config.get_env_from_db("SESSIONS")
            if not string_sessions:
                self.training_wheels_protocol = True
                self.log(
                    self.get_string("no_session_found"),
                    level=30,
                )
                try:
                    self.ourselves.append(await self.bot.get_users(self.config.OWNER_ID))
                except Exception:
                    Altruix.log(
                        "Please start the bot with the account where it's ID is where you've added in the OWNER_ID field.",
                        level=40,
                    )
                    quit()
                except Exception as e:
                    self.log(
                        f"[{e}] - Please add another session using your assistant bot [@{self.bot_info.username}]",
                        level=logging.CRITICAL,
                    )
            else:
                self.log(self.get_string("session_found"))
                # ✅ FIX: Ensure string_sessions is always a list. 
                # If retrieved as string from DB, split it by spaces.
                if isinstance(string_sessions, str):
                    string_sessions = [i for i in string_sessions.split(" ") if i.strip()]
                
                total_sessions = len(string_sessions)
                unloaded_sessions = []
                loaded_user_ids = set() # Track IDs to prevent dupes
                self.config.SESSION_NAMES = [] # ✅ Reset session names

                for count, each in enumerate(string_sessions):
                    try:
                        # ✅ STAGGER START: Avoid network burst by staggering connection starts
                        if count > 0:
                            wait_stagger = min(5, count * 0.5) 
                            await asyncio.sleep(wait_stagger)

                        client = await Client(
                            f"{count}_instance_Altruix",
                            api_id=self.config.API_ID,
                            api_hash=self.config.API_HASH,
                            session_string=each,
                            workdir="cache",
                            loop=self.loop,
                        ).start()
                        
                        me = await client.get_me()
                        
                        # ✅ DEDUPLICATE SESSIONS
                        if me.id in loaded_user_ids:
                            self.log(f"Skipping duplicate session for user {me.id}")
                            await client.stop()
                            continue
                            
                        loaded_user_ids.add(me.id)
                        
                        client.myself = me
                        OWNER_ID = BaseConfig.OWNER_ID
                        first = (me.first_name or "").strip()
                        last = (me.last_name or "").strip()
                        full_name = f"{first} {last}".strip() or "(No Name)"
                        username = f" @{me.username}" if me.username else ""
                        is_owner = " [OWNER]" if me.id == OWNER_ID else ""
                        user_id = me.id
                        self.log(
                            self.get_string("session_loaded").format(count + 1, total_sessions, user_id, full_name, username, is_owner)
                        )
                        # ✅ Store session string for easier removal later
                        client.session_string = each
                        self.clients.append(client)
                        self.config.SESSION_NAMES.append(client.name) # ✅ Synchronize name
                        # ✅ ALWAYS add to ourselves to keep indices in sync with clients
                        self.ourselves.append(me)
                    except Exception as err:
                        self.log(self.get_string("session_unloaded").format(count + 1, total_sessions, err), level=50)
                        self.log(self.get_string("session_invalid"))
                        unloaded_sessions.append(each)
                for bad_session in unloaded_sessions:
                    await self.config.pop_element_from_list("SESSIONS", bad_session)
                if not self.clients:
                    await self.config.del_env_from_db("SESSIONS")
                    self.training_wheels_protocol = True
            # =============================================
            # SEMUA CLIENT (BOT + USER SESSION) KIRIM PESAN STARTUP KE LOG_CHAT_ID
            # =============================================
            if self.log_chat:
                # ✅ PERBAIKAN 3: Validasi log_chat sebelum digunakan
                try:
                    log_chat_id = int(self.log_chat)
                    await self.bot.get_chat(log_chat_id) # Pastikan bot bisa akses
                except (PeerIdInvalid, UserNotParticipant, ValueError, RPCError) as ve:
                    self.log(f"log_chat tidak valid atau bot tidak bisa akses: {ve}", level=40)
                    log_chat_id = None
                else:
                    from datetime import datetime
                    startup_time = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
                    all_clients = [self.bot] + self.clients
                    success_count = 0
                    failed_clients = []
                    self.log(self.get_string("sending_startup").format(len(all_clients)))
                    for client in all_clients:
                        try:
                            me = client.myself if hasattr(client, "myself") else await client.get_me()
                            name = f"{me.first_name or ''} {me.last_name or ''}".strip() or "Unknown"
                            username = f" @{me.username}" if me.username else ""
                            user_id = me.id
                            client_type = "🤖 Bot" if client == self.bot else "🦸🏼 Ubot"
                            mention_user = f'<a href="tg://user?id={user_id}">{html.escape(name)}</a>'
                            total_user_sessions = len(self.clients)
                            final_message = ""
                            parse_mode = ParseMode.HTML
                            
                            if client == self.bot:
                                base_text = f"<b>✅ Altroid-X Bot Assistant is alive!</b>"
                                final_message = (
                                    f"<blockquote expandable>{base_text}\n"
                                    f"<b>{client_type}: {mention_user}</b> [ <code>{user_id}</code> ]</blockquote>\n"
                                )
                            else:
                                user_index = self.clients.index(client)
                                user_display_index = user_index + 1
                                
                                # ✅ CHECK STARTUP STATE (OFF/DEFAULT/CUSTOM)
                                startup_key = f"STARTUP_MSG_{user_index}"
                                state = await self.config.get_env(startup_key)
                                state = str(state).lower() if state else "default"
                                
                                if state in ["off", "false", "no", "0"]:
                                    self.log(f"SKIP: [{client_type}] {name} startup log (OFF)")
                                    continue
                                
                                if state == "custom":
                                    custom_msg = await self.config.get_env(f"STARTUP_CUSTOM_MSG_{user_index}")
                                    if custom_msg:
                                        final_message, parse_mode = await self.resolve_placeholders(custom_msg, index=user_index, client=client)
                                    else:
                                        state = "default" # Fallback
                                
                                if state == "default":
                                    base_text = f"<b>✅ Altroid-X Userbot [{user_display_index}/{total_user_sessions}] is alive!</b>"
                                    final_message = (
                                        f"<blockquote expandable>{base_text}\n"
                                        f"<b>{client_type}: {mention_user}</b> [ <code>{user_id}</code> ]</blockquote>\n"
                                    )
                                    parse_mode = ParseMode.HTML

                            await client.send_message(
                                log_chat_id,
                                final_message,
                                parse_mode=parse_mode,
                                link_preview_options=LinkPreviewOptions(is_disabled=True)
                            )
                            await asyncio.sleep(3)
                            success_count += 1
                            if client == self.bot:
                                # Bot logic: [1/1]
                                log_msg = f"✔ SL_MSG BY: [1/1] 🤖 Bot: {name}"
                            else:
                                # Userbot logic: [current/total_userbots]
                                userbot_index = self.clients.index(client) + 1
                                total_userbots = len(self.clients)
                                log_msg = f"✔ SL_MSG BY: [{userbot_index}/{total_userbots}] 🦸🏼 Ubot: {name}"
                            
                            self.log(log_msg, level=20)
                        except FloodWait as e:
                            self.log(f"FloodWait terdeteksi. Menunggu {e.value} detik...", level=30)
                            await asyncio.sleep(e.value + 6)
                        except Exception as e:
                            error_type = type(e).__name__
                            error_msg = str(e)
                            me = client.myself if hasattr(client, "myself") else None
                            name = me.first_name if me else "Unknown"
                            username = f" @{me.username}" if me and me.username else ""
                            client_type = "Bot" if client == self.bot else "User"
                            failed_clients.append(f"• <b>{name}{username}</b> → {error_type}")
                            self.log(f"GAGAL: [{client_type}] {name}{username} → {error_type}: {error_msg}", level=30)
                    self.log("=== RINGKASAN PENGIRIMAN STARTUP LOG ===")
                    self.log(f"✔ Successfully sent: {success_count}/{len(all_clients)} client", level=20)
                    if failed_clients:
                        self.log("✖ Failed client:", level=30)
                        for fail in failed_clients:
                            self.log(f" {fail}", level=30)
                    else:
                        self.log(self.get_string("startup_summary_success").format(log_chat_id), level=20)
                    if success_count > 0:
                        try:
                            branch = get_current_git_branch()
                            altruix_version = getattr(self, "__version__", "unknown")
                            db_type = "MongoDB" if self.config.DB_URI else "LocalDB"
                            
                            # Get system stats untuk ditampilkan di startup log
                            system_stats = self.get_system_stats()
                            
                            # Check untuk resource warnings (CPU/RAM > 80%)
                            warnings = {}
                            cpu_percent = system_stats.get('cpu', {}).get('percent')
                            ram_percent = system_stats.get('ram', {}).get('percent')
                            
                            if isinstance(cpu_percent, (int, float)) and cpu_percent > 80:
                                warnings['cpu'] = cpu_percent
                            if isinstance(ram_percent, (int, float)) and ram_percent > 80:
                                warnings['ram'] = ram_percent
                            
                            # Format pesan dengan blockquote expandable
                            summary = self.format_startup_log_blockquote(
                                total_sessions=len(self.clients),
                                success_count=success_count,
                                failed_count=len(failed_clients),
                                owner_id=self.config.OWNER_ID,
                                branch=branch,
                                db_type=db_type,
                                version=altruix_version,
                                startup_time=startup_time,
                                system_stats=system_stats,
                                warnings=warnings if warnings else None
                            )
                            
                            # Kirim dengan parse_mode HTML
                            await self.bot.send_message(
                                log_chat_id, 
                                summary,
                                parse_mode=ParseMode.HTML
                            )
                            self.log(f"Ringkasan akhir berhasil dikirim. Branch: {branch}, Versi: {altruix_version}", level=20)
                        except Exception as e:
                            # Fallback ke format plain text jika HTML error
                            self.log(f"Error sending HTML format, trying plain text: {e}", level=logging.WARNING)
                            try:
                                summary_plain = (
                                    self.get_string("startup_complete_title") +
                                    self.get_string("startup_total_session").format(len(self.clients)) +
                                    self.get_string("startup_success_count").format(success_count) +
                                    self.get_string("startup_failed_count").format(len(failed_clients)) +
                                    self.get_string("startup_owner_id").format(BaseConfig.OWNER_ID) +
                                    self.get_string("startup_branch").format(branch) +
                                    self.get_string("startup_db").format(db_type) +
                                    self.get_string("startup_ver").format(altruix_version) +
                                    self.get_string("startup_time").format(startup_time)
                                )
                                await self.bot.send_message(log_chat_id, summary_plain)
                            except Exception as e2:
                                self.log(self.get_string("startup_summary_fail").format(e2), level=logging.ERROR)
        except Exception as e:
            self.log(f"CRITICAL: Session initialization failed: {e}", level=50)
            raise

    async def add_session(self, session: str, status: Message = None, user: User = None) -> Client:
        """
        Validates and adds a new user session.
        Checks for duplicates and connection validity BEFORE saving.
        """
        from pyrogram.errors import (
            AuthKeyDuplicated,
            SessionPasswordNeeded,
            UserDeactivated,
            PeerIdInvalid
        )

        # 1. Gunakan nama unik untuk client baru untuk mencegah konflik internal Pyrogram
        import time
        temp_client_name = f"temp_session_{int(time.time()*1000)}"
        
        self.log(f"Attempting to add new session with temp name: {temp_client_name}", level=20)

        app = Client(
            temp_client_name,
            api_id=self.config.API_ID,
            api_hash=self.config.API_HASH,
            session_string=session,
            workdir="cache",
            loop=self.loop,
        )

        try:
            # 2. Coba connect dulu
            await app.start()
            
            # 3. Validasi User
            me = await app.get_me()
            user_id = me.id
            
            # 4. Cek apakah user ini SUDAH ada di daftar client yang aktif
            for existing_client in self.clients:
                existing_me = existing_client.myself if hasattr(existing_client, "myself") else await existing_client.get_me()
                if existing_me.id == user_id:
                    try:
                        await app.stop()
                    except Exception:
                        pass
                    msg = f"User {me.first_name} (ID: {user_id}) sudah aktif! Tidak bisa menambahkan akun yang sama dua kali."
                    self.log(msg, level=logging.WARNING)
                    if status:
                        await status.edit(msg)
                    return None

            # 5. Jika lolos validasi, simpan session secara permanen
            app.myself = me # Simpan info user di object client
            
            # -- Add to DB/Config --
            await self.config.add_element_to_list("SESSIONS", session)
            self.config.append_session(session)
            
            # ✅ Fix: Force save to LocalDB to ensure persistence
            try:
                if hasattr(self.db, "save_now"):
                    await self.db.save_now()
                    self.log("Forced save to LocalDB after adding session.", level=20)
            except Exception as e:
                self.log(f"Failed to force save LocalDB: {e}", level=logging.ERROR)

            # Pastikan tidak double add di list memori jika append_session sudah handle
            if session not in self.config.SESSIONS:
                self.config.SESSIONS.append(session)
            
            self.log(f"User session added successfully: {me.first_name} ({user_id})", level=20)
            
            # Add to active clients list
            self.clients.append(app)
            self.config.SESSION_NAMES.append(app.name) # ✅ Synchronize name

            # Jika ini session pertama, matikan TWP
            if self.training_wheels_protocol:
                self.training_wheels_protocol = False
                self.log("[TWP] Support mode disabled - features unlocked!")

            # Tambahkan ke ourselves list jika bukan owner (untuk sudo checks)
            if user_id not in self.config.OWNER_USERS_ID:
                self.ourselves.append(me)

            # ✅ Load modules for this new session
            await self.load_all_modules()
            self.log("Userbot plugins have been loaded for new session.")

            if status:
                await status.edit("<b>Account Successfully added!</b>")

            # ✅ LOG NOTIFICATION: SESI BERHASIL DITAMBAHKAN
            try:
                log_chat_id = int(os.getenv("LOG_CHAT_ID", self.config.OWNER_ID))
                log_msg = (
                    "✅ <b>SESSION BERHASIL DITAMBAHKAN</b>\n\n"
                    f"• <b>User Admin:</b> <a href='tg://user?id={user.id}'>{html.escape(user.first_name)}</a> (<code>{user.id}</code>)\n"
                    f"• <b>Akun Baru:</b> <a href='tg://user?id={me.id}'>{html.escape(me.first_name or 'None')}</a> (<code>{me.id}</code>)\n"
                    f"• <b>Username:</b> @{me.username or 'None'}\n"
                    f"• <b>Waktu:</b> <code>{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</code>"
                ) if user else (
                    "✅ <b>SESSION BERHASIL DITAMBAHKAN (System)</b>\n\n"
                    f"• <b>Akun ID:</b> <code>{me.id}</code>\n"
                    f"• <b>Waktu:</b> <code>{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</code>"
                )
                await self.bot.send_message(log_chat_id, log_msg, parse_mode=ParseMode.HTML)
            except Exception as le:
                self.log(f"Failed to send success add_session log: {le}", level=logging.DEBUG)

            return app

        except (AuthKeyDuplicated, UserDeactivated, SessionPasswordNeeded) as e:
            try:
                await app.stop()
            except Exception:
                pass # Abaikan jika client sudah terminated (sering terjadi pada AuthKeyDuplicated)
            error_msg = f"Session Invalid/Expired/2FA Required: {type(e).__name__} - {e}"
            self.log(error_msg, level=logging.ERROR)
            if status:
                await status.edit(f"❌ Gagal menambahkan akun:\n`{error_msg}`")
            
            # ✅ LOG NOTIFICATION: GAGAL TAMBAH (Auth Error)
            try:
                log_chat_id = int(os.getenv("LOG_CHAT_ID", self.config.OWNER_ID))
                log_msg = (
                    "❌ <b>GAGAL MENAMBAH SESSION</b>\n\n"
                    f"• <b>User Admin:</b> <a href='tg://user?id={user.id}'>{html.escape(user.first_name)}</a> (<code>{user.id}</code>)\n"
                    f"• <b>Error:</b> <code>{type(e).__name__}</code>\n"
                    f"• <b>Pesan:</b> <code>{html.escape(str(e))}</code>\n"
                    f"• <b>Waktu:</b> <code>{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</code>"
                ) if user else f"❌ <b>GAGAL MENAMBAH SESSION (System)</b>\n\n• Error: <code>{type(e).__name__}</code>"
                await self.bot.send_message(log_chat_id, log_msg, parse_mode=ParseMode.HTML)
            except Exception: pass
            
            raise e # Lempar ulang agar caller tau gagal
            
        except Exception as e:
            try:
                await app.stop()
            except Exception:
                pass
            error_msg = f"Unknown Error adding session: {e}"
            self.log(error_msg, level=logging.ERROR)
            self.log(traceback.format_exc())
            if status:
                await status.edit(f"❌ Error tidak dikenal:\n`{str(e)[:100]}`")
            raise e

    async def remove_session(self, index: int, user: User = None) -> User:
        # ✅ SAFER REMOVAL: Check indices before popping
        if index >= len(self.clients):
            raise IndexError("Client index out of range")
        
        client_to_remove = self.clients[index]
        session_str = getattr(client_to_remove, "session_string", None)
        
        # Remove from SESSIONS list (config/database)
        if session_str:
            try:
                # First try removing from local list and .env
                self.config.remove_session_by_value(session_str)
                # Then remove from database
                await self.config.pop_element_from_list("SESSIONS", session_str)
            except Exception as e:
                self.log(f"Failed to remove session string from config/db: {e}", level=logging.WARNING)

        # Remove from memory lists
        removed_session_info = self.ourselves.pop(index) if index < len(self.ourselves) else None
        if not removed_session_info:
            removed_session_info = getattr(client_to_remove, "me", None) or getattr(client_to_remove, "myself", None)

        try:
            removed_client = self.clients.pop(index)
            await removed_client.stop()
        except Exception as e:
            self.log(f"Error stopping removed client: {e}")

        if not self.ourselves:
            self.training_wheels_protocol = True
            self.log("[TWP] has been enabled!")
        self.log("User session removed successfully!")
        
        # ✅ LOG NOTIFICATION: SESI BERHASIL DIHAPUS (UNLINK)
        try:
            log_chat_id = int(os.getenv("LOG_CHAT_ID", self.config.OWNER_ID))
            log_msg = (
                "🗑 <b>SESSION BERHASIL DIHAPUS (UNLINK)</b>\n\n"
                f"• <b>User Admin:</b> <a href='tg://user?id={user.id}'>{html.escape(user.first_name)}</a> (<code>{user.id}</code>)\n"
                f"• <b>Akun Dihapus:</b> <a href='tg://user?id={removed_session_info.id}'>{html.escape(removed_session_info.first_name or 'None')}</a> (<code>{removed_session_info.id}</code>)\n"
                f"• <b>Username:</b> @{removed_session_info.username or 'None'}\n"
                f"• <b>Index Sesi:</b> <code>{index + 1}</code>\n"
                f"• <b>Waktu:</b> <code>{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</code>"
            ) if user else (
                "🗑 <b>SESSION BERHASIL DIHAPUS (System)</b>\n\n"
                f"• <b>Akun ID:</b> <code>{removed_session_info.id}</code>\n"
                f"• <b>Waktu:</b> <code>{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</code>"
            )
            await self.bot.send_message(log_chat_id, log_msg, parse_mode=ParseMode.HTML)
        except Exception as le:
            self.log(f"Failed to send remove_session log: {le}", level=logging.DEBUG)

        self.loop.create_task(self.load_all_modules())
        return removed_session_info

    def find_plugin_file(self, plugin_name: str) -> Optional[str]:
        """Find the file path for a given plugin name."""
        import os
        # Check standard locations
        search_paths = [
            f"Main/plugins/userbot/{plugin_name}.py",
            f"Main/plugins/bot/{plugin_name}.py",
            # Also check underscore version if name has spaces
            f"Main/plugins/userbot/{plugin_name.replace(' ', '_')}.py",
            f"Main/plugins/bot/{plugin_name.replace(' ', '_')}.py",
        ]
        
        for path in search_paths:
            if os.path.exists(path):
                return path
        
        # If not found, try a broader search in the plugins directory
        import glob
        all_plugins = glob.glob("Main/plugins/**/*.py", recursive=True)
        for p in all_plugins:
            if os.path.basename(p).lower() == f"{plugin_name.lower()}.py" or \
               os.path.basename(p).lower() == f"{plugin_name.replace(' ', '_').lower()}.py":
                return p
                
        return None

    async def resolve_placeholders(self, text: str, index: int = None, client: Client = None) -> Union[str, tuple[str, Any]]:
        """Resolve placeholders in custom messages. Returns (text, parse_mode) if detection is requested."""
        if not text:
            return "", ParseMode.HTML
            
        import pyrogram
        import platform
        import glob
        import html
        from pyrogram.enums import ParseMode
        
        # Determine client and index if not provided
        if client is None and index is not None and index < len(self.clients):
            client = self.clients[index]
        elif client is not None and index is None:
            try:
                index = self.clients.index(client)
            except ValueError:
                index = -1 # Probably the bot client
                
        me = None
        if client:
            # ✅ OPTIMIZATION: Use cached info if available to avoid network call in high-freq tasks
            if hasattr(client, "myself") and client.myself:
                me = client.myself
            elif hasattr(client, "me") and client.me:
                me = client.me
            elif index is not None and 0 <= index < len(self.ourselves):
                me = self.ourselves[index]
            else:
                # Fallback only if absolutely necessary, but try to avoid it
                try:
                    me = await client.get_me()
                    client.myself = me
                except:
                    pass
            
        ub_plugins = len(glob.glob("Main/plugins/userbot/*.py"))
        bot_plugins = len(glob.glob("Main/plugins/bot/*.py"))
        total_sessions = len(self.clients)
        
        # Detect ParseMode
        parse_mode = ParseMode.HTML
        if "(md2)" in text or "(markdown2)" in text:
            parse_mode = ParseMode.MARKDOWN
            text = text.replace("(md2)", "").replace("(markdown2)", "")
        elif "(html)" in text:
            parse_mode = ParseMode.HTML
            text = text.replace("(html)", "")
        
        replacements = {
            # Standard placeholders
            "ub_version": self.__version__,
            "kurigram_version": pyrogram.__version__,
            "pyrogram_version": pyrogram.__version__,
            "python_version": platform.python_version().split()[0],
            "ub_plugins": ub_plugins,
            "bot_plugins": bot_plugins,
            "index": (index + 1) if index is not None and index >= 0 else "N/A",
            "total_sessions": total_sessions,
            "total_commands": self.total_commands,
            "prefix": self._prefix_cache["prefix_owner_user"],
            "sudo_prefix": self._prefix_cache["prefix_sudo_users"],
            "ultroid_prefix": self._prefix_cache.get("ultroid_owner", ","),
            "ultroid_sudo_prefix": self._prefix_cache.get("ultroid_sudo", "?"),

            
            # Legacy/Requested (userbot version) style
            "(userbot version)": self.__version__,
            "(kurigram version)": pyrogram.__version__,
            "(pyrogram version)": pyrogram.__version__,
            "(python version)": platform.python_version().split()[0],
            "(total userbot plugins)": ub_plugins,
            "(total bot plugins)": bot_plugins,
            "(session index)": (index + 1) if index is not None and index >= 0 else "N/A",
            "(total sessions)": total_sessions,
            "(total commands)": self.total_commands,
            "(userbot plugins)": ub_plugins,
            "(bot plugins)": bot_plugins,
            "total_addons": len([p for p, cat in self.plugin_categories.items() if cat == "ultroid"]),
            "(total addons)": len([p for p, cat in self.plugin_categories.items() if cat == "ultroid"]),
        }
        
        if me:
            first = me.first_name or ""
            last = me.last_name or ""
            full = f"{first} {last}".strip()
            
            first = Essentials.clean_user_name(first)
            full = Essentials.clean_user_name(full)
            
            # Escape only for HTML mode
            m_first = html.escape(first) if parse_mode == ParseMode.HTML else first
            m_full = html.escape(full) if parse_mode == ParseMode.HTML else full
            
            mention = f'<a href="tg://user?id={me.id}">{m_first}</a>' if parse_mode == ParseMode.HTML else f"[{first}](tg://user?id={me.id})"
            mention_full = f'<a href="tg://user?id={me.id}">{m_full}</a>' if parse_mode == ParseMode.HTML else f"[{full}](tg://user?id={me.id})"
            username = f"@{me.username}" if me.username else ""
            
            # Determine prefixes for this specific session
            is_global = self._prefix_cache["apply_type"] == "global"
            if is_global:
                up = self._prefix_cache["prefix_owner_user"]
                sp = self._prefix_cache["prefix_sudo_users"]
                ulp = self._prefix_cache.get("ultroid_owner", ",")
                usp = self._prefix_cache.get("ultroid_sudo", "?")
            else:
                pa = self._prefix_cache["per_account"].get(me.id, {})
                up = pa.get("u", self._prefix_cache["prefix_owner_user"])
                sp = pa.get("s", self._prefix_cache["prefix_sudo_users"])
                ulp = pa.get("ult_u", self._prefix_cache.get("ultroid_owner", ","))
                usp = pa.get("ult_s", self._prefix_cache.get("ultroid_sudo", "?"))

            replacements.update({
                "prefix": up,
                "sudo_prefix": sp,
                "ultroid_prefix": ulp,
                "ultroid_sudo_prefix": usp,
                "first_name": first,
                "last_name": last,
                "full_name": full,
                "mention": mention,
                "mention_name": mention,
                "mention_first_name": mention,
                "mention_full_name": mention_full,
                "user_name": username,
                "user_id": me.id,
                "session_name": first,
                
                "(first name)": first,
                "(last name)": last,
                "(full name)": full,
                "(mention)": mention,
                "(mention name)": mention,
                "(mention userbot)": mention,
                "(mention session)": mention,
                "(mention session/userbot client)": mention,
                "(mention full name)": mention_full,
                "(user name)": username,
                "(user id)": me.id,
                "(session name)": first,
            })
            
        # Perform replacement for {} style
        try:
            # We use a safer way than .format() to avoid KeyError on unknown braces
            # Add Aliases for compatibility
            replacements["i"] = replacements.get("prefix", ".")
            replacements["HNDLR"] = replacements.get("ultroid_prefix", ",")

            for k, v in replacements.items():
                if not k.startswith("("):
                    text = text.replace(f"{{{k}}}", str(v))
        except Exception as e:
            self.log(f"Error resolving {{}} placeholders: {e}")
            
        # Perform replacement for () style
        for k, v in replacements.items():
            if k.startswith("("):
                text = text.replace(k, str(v))
                
        return text, parse_mode

    async def _restart(
        self,
        soft=False,
        last_msg: Union[Message, CallbackQuery, None] = None,
        power_hard=False,
    ):
        self.loaded_bot_cmds = False
        _start = time.perf_counter()
        await self._setup(restart=True)
        if not soft:
            if power_hard:
                import subprocess
                self.log("Hard restart initiated...", level=30)
                args = [sys.executable, "-m", "Main"]
                if os.name == 'nt':
                     subprocess.Popen(args, creationflags=subprocess.CREATE_NEW_CONSOLE)
                     sys.exit(0)
                else:
                     os.execv(sys.executable, args)
                     
            if not self.training_wheels_protocol and self.clients:
                for each in self.clients:
                    try:
                        await each.restart()
                    except: pass
            await self.bot.restart()
            self.start_time = time.time()
        await self.load_all_modules()
        time_took = Essentials.get_readable_time(time.perf_counter() - _start)
        msg = f"<b>Altruix has been {'reloaded' if soft else 'restarted'}!</b>\nTook {time_took}."
        await self.bot.send_message(self.config.OWNER_ID, msg)
        if isinstance(last_msg, Message):
            await last_msg.edit(msg)
        elif isinstance(last_msg, CallbackQuery):
            await last_msg.edit_message_text(msg)
        self.log(
            f"Altruix have been {'reloaded' if soft else 'restarted'} successfully!"
        )

    async def send_error(
        self,
        client: Client,
        cmd: Union[str, List[str]],
        error: str,
        file_name: str,
        use_bot: bool = False,
        **args,
    ):
        chat_id = self.log_chat
        cmd_handler = self.config.PREFIX_OWNER_USER
        headers = self.get_string("ERROR*")
        if isinstance(cmd, list):
            cmd = cmd[0]
        if not chat_id:
            return
        txt_ = self.get_string(
            "ERROR_REPORT", args=(cmd_handler, cmd, error, cmd_handler, file_name)
        )
        target_client = self.bot if use_bot else client
        try:
            m = await target_client.send_message(chat_id, txt_, **args)
        except MessageTooLong:
            text = Essentials.md_to_text(txt_)
            service, paste_link = await Paste(text).paste()
            txt = headers.format(service.title(), paste_link)
            m = await target_client.send_message(chat_id, txt, **args)
        return m

    async def reboot(
        self, soft=False, last_msg: Union[Message, CallbackQuery, None] = None
    ):
        self.log(f"Received signal for {'Reload' if soft else'Restart'}!", level=30)
        await asyncio.sleep(2)
        self.loop.create_task(self._restart(soft=soft, last_msg=last_msg))

    async def custom_log(self, msg, level=logging.INFO, p_msg: Message = None):
        self.log(msg, level)
        if p_msg:
            return await p_msg.edit_msg(msg.strip())

    async def load_from_directory(self, path: str, log=True, msg=None, recursive=False):
        helper_scripts = glob.glob(path, recursive=recursive)
        if not helper_scripts:
            return await self.custom_log(
                f"No plugins loaded from {path}", level=logging.INFO, p_msg=msg
            )
        # Filter out directories if any (though glob *.py usually doesn't return dirs)
        helper_scripts = [f for f in helper_scripts if os.path.isfile(f)]
        
        plugin_count = str(len(helper_scripts))
        loaded_pc = 0
        for name in helper_scripts:
            loaded_pc += 1
            start_time = time.time()
            try:
                with open(name, encoding="utf-8") as a:
                    path_ = Path(a.name)
                    plugin_name = path_.stem
                    
                    # Robust import path calculation
                    # Convert 'Main/plugins/addons/inline/imdb.py' -> 'Main.plugins.addons.inline.imdb'
                    rel_path = os.path.relpath(name, os.getcwd())
                    import_path = rel_path.replace(os.sep, ".").replace("/", ".")
                    if import_path.endswith(".py"):
                        import_path = import_path[:-3]
                    
                    # Identify category based on the directory structure
                    if "userbot" in import_path:
                        import_type = "userbot"
                    elif "addons" in import_path:
                        import_type = "addons"
                    elif ".bot" in import_path or "Main.plugins.bot" in import_path:
                        import_type = "bot"
                    else:
                        import_type = "other"

                    spec = importlib.util.spec_from_file_location(import_path, name)
                    load = importlib.util.module_from_spec(spec)
                    load.Altruix = self
                    load.bot = self.bot
                    load.asyncio = asyncio
                    if import_type == "userbot":
                        import_type = "U"
                    elif import_type == "bot":
                        import_type = "A"
                    elif import_type == "addons":
                        import_type = "X"
                        # ✅ PERFORMANCE FIX: Use cached value instead of querying DB
                        if not getattr(self, '_ultroid_addons_enabled', False):
                            # Skip loading if disabled
                            continue
                        
                        # Inject Ultroid Bridge Symbols
                        try:
                            from Main.core.ext.ultroid_bridge import (
                                ultroid_cmd, UltroidEvent, eor, eod, udB, as_commas, get_string
                            )
                            load.ultroid_cmd = ultroid_cmd
                            load.UltroidEvent = UltroidEvent
                            load.get_string = get_string
                            load.eor = eor
                            load.eod = eod
                            load.udB = udB
                            load.as_commas = as_commas
                            # Also inject common names
                            load.event = UltroidEvent
                        except Exception as bridge_err:
                            self.log(f"Failed to inject Ultroid bridge: {bridge_err}", level=logging.ERROR)
                    else:
                        import_type = "M"
                    try:
                        # ✅ Trigger Dynamic Altruix Injection for Ultroid Addons
                        is_ultroid = import_type == "X"
                        if is_ultroid and hasattr(sys, '_altruix_inject_addon'):
                            sys._altruix_inject_addon(load)
                        
                        # ✅ Recursive injection for sub-packages
                        # If this module has a __path__ (is a package), we might need to inject symbols 
                        # into its children as well when they are loaded, but for now injecting into the 
                        # main module handles the 'from . import ...' cases effectively.
                            
                        spec.loader.exec_module(load)
                        sys.modules[import_path] = load
                        end_time = round(time.time() - start_time, 2)
                        if log:
                            string_load = (
                                f"[{import_type}] - ["
                                + concatenate(str(loaded_pc), "99", "0", False)
                                + "/"
                                + concatenate(plugin_count, "99", "0", False)
                                + "] Loaded "
                                + concatenate(plugin_name, " " * 30, " ")
                                + "["
                                + concatenate(str(end_time), " ", "0")
                                + "s]"
                            )
                            if msg:
                                string_load = f"[{import_type}] - Loaded {plugin_name} in <i>{end_time}s</i>"
                            await self.custom_log(
                                string_load,
                                p_msg=msg,
                            )
                    except Exception as err:
                        import traceback
                        full_trace = traceback.format_exc()
                        error_summary = f"[{import_type}] CRITICAL << Failed To Load Plugin: {plugin_name}"
                        full_error_log = f"{error_summary}\n{'─' * 50}\n{full_trace}\n{'─' * 50}"
                        await self.custom_log(
                            full_error_log,
                            level=50,
                            p_msg=msg,
                        )
                        # ✅ Suppress massive tracebacks for Ultroid Addons missing third-party dependencies
                        if import_type == "X":
                            err_msg = full_trace.strip().split("\n")[-1]
                            print(f"\n[X] CRITICAL << Failed To Load Addon: {plugin_name} | Reason: {err_msg}\n", flush=True)
                        else:
                            print(f"\n{full_error_log}\n", flush=True)
                        continue
            except (OSError, UnicodeDecodeError) as e:
                error_msg = f"Failed to read plugin file '{name}': {e}"
                await self.custom_log(error_msg, level=50, p_msg=msg)
                print(f"\n❌ {error_msg}\n", flush=True)
                continue

    async def run_cmd_async(self, cmd):
        _cmd_args = shlex.split(cmd)
        process = await asyncio.create_subprocess_exec(
            *_cmd_args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        return (
            stdout.decode("utf-8").strip(),
            stderr.decode("utf-8").strip(),
            process.returncode,
            process.pid,
        )


    async def load_all_modules(self):
        self.log("Starting to load all modules...", level=logging.INFO)
        try:
            # ✅ PERFORMANCE FIX: Cache LOAD_ULTROID_ADDONS check once
            ultroid_addons_enabled = await self.config.get_env("LOAD_ULTROID_ADDONS", default="off")
            self._ultroid_addons_enabled = str(ultroid_addons_enabled).lower() in ("on", "true", "1", "yes")
            
            await self.load_from_directory("Main/utils/*.py", log=False)
            await self.load_from_directory("Main/internals/*.py", log=False)
            self.log("All internal modules have been loaded.")
            self.log("Preparing to load all plugins.\n")
            # Setup Ultroid Shims *only if* addons enabled
            if self._ultroid_addons_enabled:
                try:
                    from Main.core.ext.ultroid_shims import setup_shims
                    setup_shims(self)
                except Exception as e:
                    self.log(f"Failed to setup Ultroid shims: {e}", level=logging.ERROR)

            await self.load_from_directory("Main/plugins/bot/*.py", log=True)
            if self.training_wheels_protocol:
                self.log("Userbot Plugins will be disabled due to [TWP]!")
                if self.bot_mode:
                    await self.load_from_directory("Main/plugins/userbot/*.py", log=False)
                    self.log("BOT_MODE: ON - Loaded all possible Modules as BOT.")
                    self.loaded_bot_cmds = True
            else:
                await self.load_from_directory("Main/plugins/userbot/*.py", log=True)
                if self.bot_mode:
                    self.log("BOT_MODE: ON - Loaded all possible Modules as BOT.")
                    self.loaded_bot_cmds = True
                await self.install_all_apm_packages()
                
                # ✅ NEW: Sync Ultroid Addons before loading
                if self._ultroid_addons_enabled:
                    await self.upm.sync_addons()

                if os.path.lexists("Main/plugins/addons"):
                    # ✅ Silent Injection: Populate package namespace for relative imports ('from . import ...')
                    try:
                        import Main.plugins.addons as addon_pkg
                        import sys as _sys
                        # ✅ Alias: some addons do `from addons.xxx import yyy` expecting a top-level package
                        if 'addons' not in _sys.modules:
                            _sys.modules['addons'] = addon_pkg
                        from Main.core.ext.ultroid_bridge import get_string, ultroid_cmd, as_commas
                        import requests
                        import asyncio
                        addon_pkg.get_string = get_string
                        addon_pkg.ultroid_cmd = ultroid_cmd
                        addon_pkg.as_commas = as_commas
                        addon_pkg.HNDLR = await self.get_prefix(self.clients[0].me.id, None, is_ultroid=True)
                        addon_pkg.requests = requests
                        addon_pkg.asyncio = asyncio
                        class UltroidBotShim:
                            def __init__(self, real_bot):
                                self._real_bot = real_bot
                            @property
                            def uid(self):
                                # Telethon-style user ID
                                return getattr(self._real_bot.me, 'id', None) if self._real_bot.me else None
                            def on(self, *args, **kwargs):
                                return lambda f: f
                            def add_handler(self, *args, **kwargs):
                                pass
                            def add_event_handler(self, *args, **kwargs):
                                pass
                            def remove_event_handler(self, *args, **kwargs):
                                pass
                            def __getattr__(self, name):
                                return getattr(self._real_bot, name, None) or _OptDummy()
                        
                        addon_pkg.ultroid_bot = UltroidBotShim(self.bot)
                        # ULTConfig shim for legacy plugins
                        addon_pkg.ULTConfig = self.config
                        
                        # ✅ Universal __getattr__ Interceptor (PEP 562)
                        # This silently satisfies ANY missing import like 'bash', 'downloader', 'async_searcher'
                        # returning a safe dummy object that can be called or accessed without crashing.
                        if not hasattr(addon_pkg, '__getattr__'):
                            class UltroidDummy:
                                def __call__(self, *args, **kwargs):
                                    # Act as pass-through decorator if first arg is callable
                                    if args and callable(args[0]): return args[0]
                                    return self
                                def __getattr__(self, item): return self
                                def __bool__(self): return False
                                def __iter__(self): return iter([self, self])
                                def __await__(self):
                                    async def dummy_coro(): return self
                                    return dummy_coro().__await__()
                                def __str__(self): return ""
                                def __repr__(self): return "<UltroidDummy>"

                            def universal_getattr(name):
                                if name == '__all__': return []
                                return UltroidDummy()
                                
                            addon_pkg.__getattr__ = universal_getattr
                        addon_pkg.__all__ = []
                        
                        # ✅ Broaden injection to subpackages (e.g. 'addons.inline')
                        # Some addons do `from .. import LOGS` in `addons/inline/imdb.py`
                        for m_name, m_obj in _sys.modules.items():
                            if m_name.startswith("Main.plugins.addons.") or m_name.startswith("addons."):
                                for key in ["LOGS", "get_string", "ultroid_cmd", "as_commas", "HNDLR", "requests", "asyncio", "ultroid_bot", "ULTConfig", "in_pattern", "callback", "asst", "InlinePlugin", "async_searcher", "Button"]:
                                    if not hasattr(m_obj, key):
                                        val = getattr(addon_pkg, key, None)
                                        if val: setattr(m_obj, key, val)
                    except Exception as e:
                        self.log(f"Silent injection error: {traceback.format_exc()}")

                    if not hasattr(self.bot, 'on'):
                        self.bot.on = lambda *args, **kwargs: lambda f: f
                    for cli in self.clients:
                        if not hasattr(cli, 'on'):
                            cli.on = lambda *args, **kwargs: lambda f: f
                    await self.load_from_directory("Main/plugins/addons/**/*.py", log=True, recursive=True)
                
                await self.load_from_directory("User/userbot/*.py", log=True)
                
                self.log("All plugins have been loaded.")
                self.prepare_help()
            
            # ✅ Initialize Custom Bots after all modules are loaded
            await self.bot_manager.initialize()
            
            print("\n")
        except Exception as e:
            error_msg = f"CRITICAL: load_all_modules crashed: {traceback.format_exc()}"
            self.log(error_msg, level=50)
            try:
                log_chat = int(os.getenv("LOG_CHAT_ID", self.config.OWNER_ID))
                await self.bot.send_message(
                    log_chat,
                    f"🚨 <b>BOT CRASHED ON STARTUP</b>\n<code>{str(e)}</code>",
                    link_preview_options=LinkPreviewOptions(is_disabled=True)
                )
            except Exception:
                pass

    def run(self):
        self.loop.run_until_complete(self._run())

    def test_run(self):
        self.loop.run_until_complete(self._test())

    def prepare_help(self):
        self._command_help_message_data.clear()
        for plugin_name, commands_data in self.cmd_list.items():
            try:
                plugin_name = plugin_name.lower()
                category = self.plugin_categories.get(plugin_name, "other")
                is_ultroid = category == "ultroid"
                display_pfx = "{ultroid_prefix}" if is_ultroid else "{prefix}"
                
                self._command_help_message_data[plugin_name] = ""
                
                # ✅ Add Module Docstring if exists
                if mod_help := self._module_helps.get(plugin_name):
                    # Basic cleanup and placeholder preparation
                    import html
                    e_mod_help = html.escape(mod_help)
                    self._command_help_message_data[plugin_name] += f"<i>{e_mod_help}</i>\n\n"

                for each_command_data in commands_data:
                    commands_: List[str] = each_command_data.get("commands", ["???"])
                    help_text = each_command_data.get("help")
                    usage_text = each_command_data.get("usage")
                    example_text = each_command_data.get("example")
                    user_args = each_command_data.get("user_args")
                    if usage_text:
                        usage_text = usage_text.replace("{i}", display_pfx).replace("{prefix}", display_pfx).replace("{ultroid_prefix}", display_pfx)
                    if example_text:
                        example_text = example_text.replace("{i}", display_pfx).replace("{prefix}", display_pfx).replace("{ultroid_prefix}", display_pfx)
                    self._command_help_message_data[plugin_name] += "\n<b>➤ Command :</b> "
                    for _cmd_str in commands_:
                        self._command_help_message_data[
                            plugin_name
                        ] += f"<code>{display_pfx}{_cmd_str}</code> / "
                    # Remove trailing " / " and add newline
                    self._command_help_message_data[plugin_name] = (
                        self._command_help_message_data[plugin_name][:-3] + "\n"
                    )
                    import html
                    e_help = html.escape(str(help_text))
                    self._command_help_message_data[
                        plugin_name
                    ] += f"\n<b>➥ Help :</b>  <i>{e_help}</i>\n"
                    if usage_text:
                        import html
                        e_usage = html.escape(str(usage_text))
                        self._command_help_message_data[
                            plugin_name
                        ] += f"\n<b>➥ Usage :</b>  <code>{e_usage}</code>\n"
                    if example_text:
                        # ✅ Auto-repair prefix: strip existing prefixes from example/usage to avoid double prefix
                        punctuation = ".!/? "
                        example_render = example_text.lstrip(punctuation)
                        
                        # Add the correct placeholder prefix
                        example_render = f"{display_pfx}{example_render}"
                        import html
                        e_example = html.escape(str(example_render))
                        self._command_help_message_data[
                            plugin_name
                        ] += f"\n<b>➥ Example :</b>  <code>{e_example}</code>\n"
                    
                    # ✅ Support for 'detail' key
                    if detail_text := each_command_data.get("detail"):
                        # detail might contain pre-formatted HTML, but for safety with user input 
                        # we should ensure it doesn't break the parent tags. 
                        # However, since most plugins expect HTML to work here, we'll keep it as-is 
                        # but ensure 'usage' and 'user_args' are safe.
                        self._command_help_message_data[
                            plugin_name
                        ] += f"\n{detail_text}\n"
                    if user_args:
                        self._command_help_message_data[plugin_name] += "\n<b>➥ Arguments:</b>\n"
                        if isinstance(user_args, list):
                            for arg_data in user_args:
                                if isinstance(arg_data, dict):
                                    import html
                                    arg_name = html.escape(str(arg_data.get("arg", "")))
                                    help_txt = html.escape(str(arg_data.get("help", "")))
                                    requires_input = arg_data.get("requires_input", False)
                                    self._command_help_message_data[
                                        plugin_name
                                    ] += f" <code>-{arg_name}</code> - {help_txt}{' [need input]' if requires_input else ''}\n"
                                else:
                                    self._command_help_message_data[
                                        plugin_name
                                    ] += f" <code>{arg_data}</code>\n"
                        elif isinstance(user_args, dict):
                            for arg_flag, arg_help in user_args.items():
                                # Escape arg_flag and arg_help for safety
                                e_flag = html.escape(str(arg_flag))
                                e_help = html.escape(str(arg_help))
                                self._command_help_message_data[
                                    plugin_name
                                ] += f" <code>{e_flag}</code> - {e_help}\n"
                        else:
                            self._command_help_message_data[
                                plugin_name
                            ] += f" <i>{str(user_args)}</i>\n"
                
            except Exception as e:
                self.log(
                    f"Failed to prepare help for plugin '{plugin_name}': {e}",
                    level=logging.ERROR
                )
                self._command_help_message_data[plugin_name] = (
                    f"<b>⚠️ Error loading help for '{plugin_name}'</b>\n"
                    f"<code>{str(e)}</code>"
        )


Altruix = AltruixClient()
