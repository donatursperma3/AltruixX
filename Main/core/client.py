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
from pyrogram.types import User, Message, CallbackQuery
from ..utils.multi_lang_helpers import get_all_files_in_path
from pyrogram import (
    Client, StopPropagation, ContinuePropagation, idle, filters,
    __version__ as pyrogram_version)
from pyrogram.errors.exceptions.bad_request_400 import (
    MessageEmpty, PeerIdInvalid, MessageTooLong, MessageIdInvalid,
    MessageNotModified, UserNotParticipant)
from pyrogram.types import LinkPreviewOptions
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait
import psutil
import platform
import threading

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

class AltruixClient:
    def __init__(self, *args, **kwargs) -> None:
        self.ourselves: List[Dict[Any, Any]] = []
        self.bot_info = None
        self.clients: List[Client] = []
        self.cmd_list = {}
        self.all_lang_strings = {}
        self.__version__ = "0.0.9.734"
        self.selected_lang = "english"
        self.local_lang_file = "./Main/localization"
        self.cmd_list = {} # {plugin_name: [cmd_data, ...]}
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
        self._init_logger()
        self.config = BaseConfig

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
        
        # ✅ Shared States for Plugins
        self.PURGEME_STATE = {}
        self.user_env_manager_state = {}
        self.user_privacy_state = {}
        self.user_track_state = {}
        self.SANGMATA_WAITING = {}
        
        # ✅ Loop setup: Get or create the optimized loop
        try:
            self.loop = asyncio.get_event_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
        
        if hasattr(asyncio, 'get_event_loop_policy'):
            policy = asyncio.get_event_loop_policy()
            if sys.platform == "win32":
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
        try:
            await cb.message.delete()
        except Exception as e:
            self.log(f"delete_cb failed: {e}", level=logging.ERROR)
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
        return f"""
     _    _ _              _
    / \\  | | |_ _ __ _   _(_)_  __
   / _ \\ | | __| '__| | | | \\ \\/ /
  / ___ \\| | |_| |  | |_| | |>  <
 /_/   \\_\\_|\\__|_|   \\__,_|_/_/\\_\\

 (C) Project-Altruix Reborn 2021-{datetime.today().year}
 Version: {self.__version__} - [ Altruix Assistant ]
        """

    @property
    def ax(self) -> Optional[Client]:
        return random.choice(self.clients) if self.clients else None

    @property
    def auth_users(self):
        # Convert SUDO_USERS to list if it's a string
        sudo_users = self.config.SUDO_USERS
        if isinstance(sudo_users, str):
            # Parse comma-separated string to list of ints
            sudo_users = [int(x.strip()) for x in sudo_users.split(',') if x.strip().isdigit()]
        elif not isinstance(sudo_users, list):
            sudo_users = []
        
        return list(
            set(
                sudo_users
                + [int(acc.id) for acc in self.ourselves]
                + [self.config.OWNER_ID]
            )
        )

    def log(
        self,
        message: Optional[str] = None,
        level=logging.DEBUG,
        logger: logging.Logger = logging.getLogger(__name__),
    ) -> Optional[str]:
        msg = message or traceback.format_exc()
        # Suppress DEBUG: logs unless config.DEBUG is True
        if msg and msg.startswith("DEBUG:") and not getattr(self.config, "DEBUG", False):
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
        logging.basicConfig(
            level=logging.INFO,
            datefmt="[%d/%m/%Y %H:%M:%S]",
            format="%(asctime)s - [Altruix] >> %(levelname)s << %(message)s",
            handlers=[
                logging.FileHandler("altruix.log", encoding="utf-8"),
                logging.StreamHandler()
            ],
        )
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
    def on_message(self, custom_filters, group=1, bot_mode_unsupported=False):
        custom_filters &= ~filters.command(
            self.cmd_list_s, [self.user_command_handler, self.sudo_cmd_handler]
        )
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
                handler_type=MessageHandler,
                bot_mode_unsupported=bot_mode_unsupported,
            )
            return wrapper
        return decorator

    def on_edited_message(self, custom_filters, group=1, bot_mode_unsupported=False):
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
    ):
        if isinstance(cmd, str):
            cmd = [cmd]
        self.cmd_list_s.extend(cmd)
        previous_stack_frame = inspect.stack()[1]
        full_path = previous_stack_frame.filename
        file_name = os.path.basename(full_path.replace(".py", ""))
        
        # ✅ Detect Category based on directory
        category = "other"
        if "plugins/userbot" in full_path.replace("\\", "/"):
            category = "userbot"
        elif "plugins/bot" in full_path.replace("\\", "/"):
            category = "bot"
        
        self.plugin_categories[file_name.lower()] = category

        # ✅ Detect Plugin Version
        plugin_version = "0.0.1"
        try:
            # Check if PLUGIN_VERSION exists in the caller's globals (reliable for decorators)
            caller_globals = previous_stack_frame.frame.f_globals
            plugin_version = caller_globals.get("PLUGIN_VERSION", "0.0.1")
            
            if plugin_version == "0.0.1":
                # Fallback: check caller's module if globals didn't work
                module = inspect.getmodule(previous_stack_frame.frame)
                if module:
                    plugin_version = getattr(module, "PLUGIN_VERSION", "0.0.1")
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
                
                # ✅ MULTI-CLIENT CROSS-EXECUTION PREVENTION
                # Prevent Client B from executing commands sent by Client A
                # when both are active in the same instance.
                if message.from_user:
                    sender_id = message.from_user.id
                    current_client_id = client.me.id
                    
                    # If sender is NOT the current client
                    if sender_id != current_client_id:
                        # Check if sender is another active client in this instance
                        other_client_ids = [c.me.id for c in self.clients if hasattr(c, 'me')]
                        if sender_id in other_client_ids:
                            # Sender is another active client, IGNORE to prevent double response
                            return
                
                # ✅ DEDUPLICATION for Multi-Session
                # If message is incoming but from self (sent from other session/phone),
                # only the FIRST active session handles it to avoid double responses.
                if not message.outgoing and message.from_user and message.from_user.is_self:
                    if self.clients and client != self.clients[0]:
                        return

                if str(message.chat.type).lower().startswith("chattype."):
                    chat_type = str(
                        (str(message.chat.type).lower()).split("chattype.")[1]
                    )
                    message.chat.type = chat_type
                
                # ✅ CRITICAL SAFETY CHECK: Ensure it's actually a command
                if message.text:
                    apply_type_p = await self.config.get_env("PREFIX_APPLY_TYPE") or "global"
                    if apply_type_p == "global":
                        valid_prefixes = [self.user_command_handler, self.sudo_cmd_handler]
                    else:
                        u_pref = await self.config.get_env(f"CMD_HANDLER_{client.me.id}") or self.user_command_handler
                        s_pref = await self.config.get_env(f"SUDO_CMD_HANDLER_{client.me.id}") or self.sudo_cmd_handler
                        valid_prefixes = [u_pref, s_pref]
                    
                    # [DEBUG] Log wrapper safety check
                    # logger.info(f"[WRAPPER DEBUG] Client: {client.me.id if client.me else 'None'}, Valid Prefixes: {valid_prefixes}, Msg: {message.text[:20] if message.text else 'None'}")
                    
                    if not any(message.text.startswith(p) for p in valid_prefixes):
                        return

                chat_type = message.chat.type
                input_ = message.user_input
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
                            await message.edit(f"❌ Error: {type(_be).__name__}")
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
        user_args = help_map.get("user_args")
        detail = help_map.get("detail")
        if isinstance(commands, str):
            commands = [commands]
        if file_name not in self.cmd_list:
            self.cmd_list[file_name] = [
                {
                    "commands": commands,
                    "help": help_text,
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
        group=0,
        handler_type=MessageHandler,
        bot_mode_unsupported=False,
    ):
        if not self.training_wheels_protocol:
            self.config.CMD_HANDLER
            basic_filters = (
                filter_s
                or user_filters(list(cmd) if cmd else [], disable_sudo=disable_sudo)
                & ~filters.via_bot
                & ~filters.forwarded
            )
            for client in self.clients:
                # ✅ DEDUPLICATION Logic for Sessions
                if cmd:
                    if isinstance(cmd, (list, tuple)): cmd_key = tuple(sorted(list(cmd)))
                    else: cmd_key = (cmd,)
                    
                    registry_key = (f"session_{client.me.id if hasattr(client, 'me') else client.name}", cmd_key, handler_type.__name__)
                    if registry_key in self.handler_registry:
                        continue
                    
                    self.handler_registry.add(registry_key)

                client.add_handler(
                    handler_type(func_, filters=basic_filters), group=group
                )
                
        if self.bot_mode and not bot_mode_unsupported and not self.loaded_bot_cmds:
            # ✅ DEDUPLICATION Logic for Bot Assistant
            if cmd:
                if isinstance(cmd, (list, tuple)): cmd_key = tuple(sorted(list(cmd)))
                else: cmd_key = (cmd,)
                
                bot_registry_key = ("bot_assistant", cmd_key, handler_type.__name__)
                if bot_registry_key in self.handler_registry:
                    return # Already registered to bot
                
                self.handler_registry.add(bot_registry_key)

            bot_f = filter_s or filters.user(self.auth_users) & filters.command(
                list(cmd) if cmd else [], ["/", "|"] # removed "!" to avoid conflict with userbot sudo handler
            )
            self.bot.add_handler(handler_type(func_, filters=bot_f), group=group)

            # ✅ Register to Custom Bots
            if hasattr(self, 'bot_manager') and self.bot_manager.custom_bots:
                for custom_bot in self.bot_manager.custom_bots.values():
                    try:
                        # Deduplication for custom bots
                        cb_reg_key = (f"custom_bot_{custom_bot.me.id if hasattr(custom_bot, 'me') else 'pending'}", cmd_key, handler_type.__name__)
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
                            "⚠️ <b>ALTRUIX RESOURCE WARNING</b>\n\n"
                            f"{usage_info}\n"
                            "‼️ <b>Tindakan diperlukan:</b>\n"
                            "Server Anda hampir mencapai kapasitas maksimal. Mohon periksa proses yang berjalan untuk menghindari crash atau restart tak terduga."
                        )
                        
                        # Kirim ke log group menggunakan bot client
                        if hasattr(self, 'bot') and self.bot.is_connected and self.log_chat:
                            try:
                                from pyrogram import enums
                                await self.bot.send_message(
                                    chat_id=self.log_chat,
                                    text=alert_msg,
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
        self.sudo_cmd_handler = await self.config.get_env("SUDO_CMD_HANDLER") or "!"
        self.user_command_handler = await self.config.get_env("CMD_HANDLER") or "."
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
        await self.update_cache()

    #
    def get_system_stats(self) -> dict:
        """
        Dapatkan statistik sistem dengan fallback yang aman untuk lingkungan terbatas (Sevalla).
        """
        try:
            import psutil
            # Gunakan psutil jika tersedia
            cpu_percent = round(psutil.cpu_percent(interval=0.5), 1)
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
            }
        }

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

                system_info = (
                    f"📊 <b>SISTEM STATISTIK</b>\n"
                    f"• <b>CPU:</b> {cpu_percent}% "
                    f"({cpu_cores} core/{cpu_threads} thread)\n"
                    f"• <b>RAM:</b> {ram_used}GB/{ram_total}GB "
                    f"({ram_percent}%)\n"
                    f"• <b>Proses:</b> {proc_memory}MB "
                    f"({proc_threads} thread)\n"
                    f"• <b>Uptime:</b> {uptime}\n"
                    f"• <b>Platform:</b> {platform_name} | "
                    f"Python {python_version} | Pyrogram {pyrogram_version_safe}"
                )
               
                # Kirim ke log chat
                if hasattr(self, 'bot') and self.bot.is_connected and self.log_chat:
                    try:
                        await self.bot.send_message(
                            self.log_chat,
                            system_info,
                            link_preview_options=LinkPreviewOptions(is_disabled=True)
                        )
                    except Exception as e:
                        self.log(f"Gagal kirim stats ke log chat: {e}", level=logging.WARNING)

                # Tampilkan di console
                print("\n" + "="*60)
                print("📊 SISTEM STATISTIK".center(60))
                print("="*60)
                print(f"CPU     : {cpu_percent}% ({cpu_cores} core / {cpu_threads} thread)")
                print(f"RAM     : {ram_used}GB / {ram_total}GB ({ram_percent}%)")
                print(f"Proses  : {proc_memory}MB | {proc_threads} thread")
                print(f"Uptime  : {uptime}")
                print(f"System  : {platform_name} | Python {python_version}")
                print(f"Pyrogram: {pyrogram_version_safe}")
                print("="*60 + "\n")

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
        
        # Cek database
        try:
            await self.db.ping()
            self.log("✅ Database connection: OK")
            checks_passed += 1
        except Exception as e:
            self.log(f"❌ Database connection: FAILED - {e}", level=logging.ERROR)
        total_checks += 1
        
        # Cek bot connection
        try:
            if hasattr(self, 'bot') and self.bot.is_connected:
                await self.bot.get_me()
                self.log("✅ Bot connection: OK")
                checks_passed += 1
        except Exception as e:
            self.log(f"❌ Bot connection: FAILED - {e}", level=logging.ERROR)
        total_checks += 1

        # Di _health_check(), tambahkan:
        try:
            mem_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
            if mem_mb > 7000:  # 7GB dari 8GB
                self.log("MemoryWarning: Memori hampir penuh! Pertimbangkan restart manual.", level=logging.WARNING)
        except Exception:
            pass
                
        # Cek user sessions
        for idx, client in enumerate(self.clients):
            try:
                if client.is_connected:
                    await client.get_me()
                    self.log(f"✅ User session {idx}: OK")
                    checks_passed += 1
            except Exception as e:
                self.log(f"❌ User session {idx}: FAILED - {e}", level=logging.WARNING)
            total_checks += 1
        
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
                except PeerIdInvalid:
                    self.log(
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
                            mention_user = f'<a href="tg://user?id={user_id}">{name}</a>'
                            total_user_sessions = len(self.clients)
                            final_message = ""
                            parse_mode = ParseMode.HTML
                            
                            if client == self.bot:
                                base_text = f"<b>✅ Altruix Bot Assistant is alive!</b>"
                                final_message = (
                                    f"{base_text}\n"
                                    f"<b>{client_type}: {mention_user}</b> [ <code>{user_id}</code> ]\n"
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
                                    base_text = f"<b>✅ Altruix Userbot [{user_display_index}/{total_user_sessions}] is alive!</b>"
                                    final_message = (
                                        f"{base_text}\n"
                                        f"<b>{client_type}: {mention_user}</b> [ <code>{user_id}</code> ]\n"
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
                                log_msg = f"BERHASIL: [1/1] 🤖 Bot: {name} -» mengirim startup msg"
                            else:
                                # Userbot logic: [current/total_userbots]
                                userbot_index = self.clients.index(client) + 1
                                total_userbots = len(self.clients)
                                log_msg = f"BERHASIL: [{userbot_index}/{total_userbots}] 🦸🏼 Ubot: {name} -» mengirim startup msg"
                            
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
                    self.log(f"Berhasil kirim: {success_count}/{len(all_clients)} client", level=20)
                    if failed_clients:
                        self.log("Client yang gagal:", level=30)
                        for fail in failed_clients:
                            self.log(f" {fail}", level=30)
                    else:
                        self.log(self.get_string("startup_summary_success").format(log_chat_id), level=20)
                    if success_count > 0:
                        try:
                            branch = get_current_git_branch()
                            altruix_version = getattr(self, "__version__", "unknown")
                            db_type = "MongoDB" if self.config.DB_URI else "LocalDB"
                            summary = (
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
                            await self.bot.send_message(log_chat_id, summary)
                            self.log(f"Ringkasan akhir berhasil dikirim. Branch: {branch}, Versi: {altruix_version}, level=20")
                        except Exception as e:
                            self.log(self.get_string("startup_summary_fail").format(e), level=logging.ERROR)
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

            # Jika ini session pertama, matikan TWP
            if self.training_wheels_protocol:
                self.training_wheels_protocol = False
                self.log("[TWP] Support mode disabled - features unlocked!")

            # Tambahkan ke ourselves list jika bukan owner (untuk sudo checks)
            if user_id != self.config.OWNER_ID:
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
            me = client.myself if hasattr(client, "myself") else await client.get_me()
            
        ub_plugins = len(glob.glob("Main/plugins/userbot/*.py"))
        bot_plugins = len(glob.glob("Main/plugins/bot/*.py"))
        total_sessions = len(self.clients)
        
        # Detect ParseMode
        parse_mode = ParseMode.HTML
        if "(md2)" in text:
            parse_mode = ParseMode.MARKDOWN
            text = text.replace("(md2)", "")
        elif "(markdown2)" in text:
            parse_mode = ParseMode.MARKDOWN
            text = text.replace("(markdown2)", "")
        
        replacements = {
            # Standard placeholders
            "ub_version": self.__version__,
            "pyrogram_version": pyrogram.__version__,
            "python_version": platform.python_version(),
            "ub_plugins": ub_plugins,
            "bot_plugins": bot_plugins,
            "index": (index + 1) if index is not None and index >= 0 else "N/A",
            "total_sessions": total_sessions,
            "total_commands": self.total_commands,

            
            # Legacy/Requested (userbot version) style
            "(userbot version)": self.__version__,
            "(pyrogram version)": pyrogram.__version__,
            "(python version)": platform.python_version(),
            "(userbot plugins)": ub_plugins,
            "(bot plugins)": bot_plugins,
            "(session index)": (index + 1) if index is not None and index >= 0 else "N/A",
            "(total sessions)": total_sessions,
            "(total commands)": self.total_commands,

        }
        
        if me:
            first = me.first_name or ""
            last = me.last_name or ""
            # Escape only for HTML mode
            m_first = html.escape(first) if parse_mode == ParseMode.HTML else first
            mention = f'<a href="tg://user?id={me.id}">{m_first}</a>' if parse_mode == ParseMode.HTML else f"[{first}](tg://user?id={me.id})"
            username = f"@{me.username}" if me.username else ""
            
            replacements.update({
                "first_name": first,
                "last_name": last,
                "mention": mention,
                "mention_first_name": mention, # Backward compatibility
                "user_name": username,
                "user_id": me.id,
                
                "(first name)": first,
                "(last name)": last,
                "(mention)": mention,
                "(mention session)": mention,
                "(mention session/userbot client)": mention,
                "(user name)": username,
                "(user id)": me.id,
            })
            
        # Perform replacement for {} style
        try:
            # We use a safer way than .format() to avoid KeyError on unknown braces
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
        **args,
    ):
        chat_id = self.log_chat
        cmd_handler = self.config.CMD_HANDLER
        headers = self.get_string("ERROR*")
        if isinstance(cmd, list):
            cmd = cmd[0]
        if not chat_id:
            return
        txt_ = self.get_string(
            "ERROR_REPORT", args=(cmd_handler, cmd, error, cmd_handler, file_name)
        )
        try:
            m = await client.send_message(chat_id, txt_, **args)
        except MessageTooLong:
            text = Essentials.md_to_text(txt_)
            service, paste_link = await Paste(text).paste()
            txt = headers.format(service.title(), paste_link)
            m = await client.send_message(chat_id, txt, **args)
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

    async def load_from_directory(self, path: str, log=True, msg=None):
        helper_scripts = glob.glob(path)
        if not helper_scripts:
            return await self.custom_log(
                f"No plugins loaded from {path}", level=logging.INFO, p_msg=msg
            )
        plugin_count = str(len(helper_scripts))
        loaded_pc = 0
        for name in helper_scripts:
            loaded_pc += 1
            start_time = time.time()
            try:
                with open(name, encoding="utf-8") as a:
                    path_ = Path(a.name)
                    plugin_name = path_.stem
                    plugins_dir = Path(path.replace("*", plugin_name))
                    import_path = path.replace("/", ".")[:-4] + plugin_name
                    import_type = import_path.split(".")[-2]
                    spec = importlib.util.spec_from_file_location(import_path, plugins_dir)
                    load = importlib.util.module_from_spec(spec)
                    load.Altruix = self
                    load.bot = self.bot
                    load.asyncio = asyncio
                    if import_type == "userbot":
                        import_type = "U"
                    elif import_type == "bot":
                        import_type = "A"
                    else:
                        import_type = "M"
                    try:
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
            await self.load_from_directory("Main/utils/*.py", log=False)
            await self.load_from_directory("Main/internals/*.py", log=False)
            self.log("All internal modules have been loaded.")
            self.log("Preparing to load all plugins.\n")
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
                if os.path.lexists("Main/plugins/external"):
                    await self.load_from_directory("Main/plugins/externals/*.py", log=True)
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
                self._command_help_message_data[plugin_name] = ""
                for each_command_data in commands_data:
                    commands_: List[str] = each_command_data.get("commands", ["???"])
                    help_text = each_command_data.get("help")
                    example_text = each_command_data.get("example")
                    user_args = each_command_data.get("user_args")
                    self._command_help_message_data[plugin_name] += "\n<b>Command :</b>"
                    for _cmd_str in commands_:
                        self._command_help_message_data[
                            plugin_name
                        ] += f"<code>{self.user_command_handler}{_cmd_str}</code>/"
                    self._command_help_message_data[plugin_name] = (
                        self._command_help_message_data[plugin_name][:-1] + "\n"
                    )
                    self._command_help_message_data[
                        plugin_name
                    ] += f"<b>Help :</b> <i>{help_text}</i>\n"
                    self._command_help_message_data[
                        plugin_name
                    ] += f"<b>Example :</b> <code>{self.user_command_handler}{example_text}</code>\n"
                    
                    # ✅ Support for 'detail' key
                    if detail_text := each_command_data.get("detail"):
                        self._command_help_message_data[
                            plugin_name
                        ] += f"\n{detail_text}\n"
                    if user_args:
                        self._command_help_message_data[plugin_name] += "<b>Arguments:</b>\n"
                        if isinstance(user_args, list):
                            for arg_data in user_args:
                                if isinstance(arg_data, dict):
                                    arg_name = arg_data.get("arg", "")
                                    help_txt = arg_data.get("help", "")
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
                                self._command_help_message_data[
                                    plugin_name
                                ] += f" <code>{arg_flag}</code> - {arg_help}\n"
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
