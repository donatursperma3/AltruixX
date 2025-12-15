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
from pyrogram.handlers import MessageHandler
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
from pyrogram.errors import FloodWait

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
        self.__version__ = "0.0.4.1"
        self.selected_lang = "english"
        self.local_lang_file = "./Main/localization"
        self.cmd_list = {}
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
        self.local_db = LocalDatabase()
        self.loop = asyncio.get_event_loop()
        self.loop.run_until_complete(self._db_setup())
        self.executor = ThreadPoolExecutor(max_workers=multiprocessing.cpu_count() * 5)
        self.config = Config(self.db.env_col, loop=self.loop, executor=self.executor)
        self.log_chat = None
        self._command_help_message_data = {}
        
        # ✅ PERBAIKAN: Setup signal handlers untuk graceful shutdown
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
        
        self.loop.run_until_complete(self._setup(restart=False, *args, **kwargs))

    async def update_cache(self):
        cache = Cache(self.config, self.db, self.clients)
        await cache.update_auto_post_cache()

    @property
    def banner(self):
        return f"""
     * _ _ _
    / \ | | |* _ __ _ *(*)* __
   / _ \ | | **| '**| | | | \ \/ /
  / ___ \| | |*| | | |*| | |> <
 //*/ \*\*|\**|_| \**,**/*/\*\
 (C) Project-Altruix 2021-{datetime.today().year}
        """

    @property
    def ax(self) -> Optional[Client]:
        return random.choice(self.clients) if self.clients else None

    @property
    def auth_users(self):
        return list(
            set(
                self.config.SUDO_USERS
                + [int(acc.id) for acc in self.ourselves]
                + [self.config.OWNER_ID]
            )
        )

    @staticmethod
    def log(
        message: Optional[str] = None,
        level=logging.DEBUG,
        logger: logging.Logger = logging.getLogger(__name__),
    ) -> Optional[str]:
        logger.log(level, message or traceback.format_exc())
        return message or traceback.format_exc()

    def _init_logger(self) -> None:
        logging.getLogger("pyrogram").setLevel(logging.INFO)
        logging.basicConfig(
            level=logging.DEBUG,
            datefmt="[%d/%m/%Y %H:%M:%S]",
            format="%(asctime)s - [Altruix] >> %(levelname)s << %(message)s",
            handlers=[logging.FileHandler("/app/altruix.log"), logging.StreamHandler()],
        )
        self.log("Initialized Logger successfully!")

    async def resolve_dns(self):
        import dns.resolver
        try:
            dns.resolver.resolve("www.google.com")
        except Exception:
            self.log("Resolving DNS. Setting to : 8.8.8.8")
            dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
            dns.resolver.default_resolver.nameservers = ["8.8.8.8"]

    async def _db_setup(self):
        with contextlib.suppress(Exception):
            await self.update_on_startup()
        await self.resolve_dns()
        self.db = MongoDB(self.config.DB_URI)
        self.log("Initialized Mongo successfully!")
        await self.db.ping()
        self.log("Pinged Mongo successfully!")
        self.app_url_ = await prepare_heroku_url()

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

    def get_string(self, keyword: str, args: tuple = None):
        selected_lang = self.selected_lang
        if self.all_lang_strings.get(selected_lang) and self.all_lang_strings.get(
            selected_lang
        ).get(keyword):
            str_ing = self.all_lang_strings.get(selected_lang).get(keyword)
            return (
                (
                    str_ing.format(*args)
                    if isinstance(args, tuple)
                    else str_ing.format(args)
                )
                if args
                else str_ing
            )

    def on_message(self, custom_filters, group=1, bot_mode_unsupported=False):
        custom_filters &= ~filters.command(
            self.cmd_list_s, [self.user_command_handler, self.sudo_cmd_handler]
        )
        def decorator(func):
            async def wrapper(client, message: Message):
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
                bot_mode_unsupported=bot_mode_unsupported,
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
        packages_ = await mc.find_one({"*id": "APM"})
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
        file_name = os.path.basename(previous_stack_frame.filename.replace(".py", ""))
        self.add_help_to_command_list(
            commands=cmd,
            file_name=file_name,
            help_map=cmd_help,
            requires_input=requires_input,
            requires_reply=requires_reply,
            group_only=group_only,
            channel_only=channel_only,
            private_only=pm_only,
        )
        def decorator(func):
            async def wrapper(client, message: Message):
                if str(message.chat.type).lower().startswith("chattype."):
                    chat_type = str(
                        (str(message.chat.type).lower()).split("chattype.")[1]
                    )
                    message.chat.type = chat_type
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
    ):
        example = html.escape(help_map.get("example", "No example available"))
        help_text = html.escape(
            help_map.get("help", "Sorry, No help available for this command")
        )
        user_args = help_map.get("user_args")
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
                }
            )

    def custom_add_handler(
        self,
        cmd=None,
        func_=None,
        filter_s=None,
        disable_sudo=False,
        group=0,
        bot_mode_unsupported=False,
    ):
        if not self.training_wheels_protocol:
            self.config.CMD_HANDLER
            basic_filters = (
                filter_s
                or user_filters(list(cmd), disable_sudo=disable_sudo)
                & ~filters.via_bot
                & ~filters.forwarded
            )
            for client in self.clients:
                client.add_handler(
                    MessageHandler(func_, filters=basic_filters), group=group
                )
        if self.bot_mode and not bot_mode_unsupported and not self.loaded_bot_cmds:
            bot_f = filter_s or filters.user(self.auth_users) & filters.command(
                list(cmd), ["!", "/", "|"]
            )
            self.bot.add_handler(MessageHandler(func_, filters=bot_f), group=group)

    async def _setup(self, restart=False, *args, **kwargs):
        if not os.path.isdir("cache"):
            os.mkdir("cache")
        await self.setup_localization()
        self.sudo_cmd_handler = await self.config.get_env("SUDO_CMD_HANDLER") or "!"
        self.user_command_handler = await self.config.get_env("CMD_HANDLER") or "."
        self.disabled_sudo_plugin_list = await self.config.get_env(
            "DISABLED_SUDO_CMD_LIST", []
        )
        self.log_chat = self.config.digit_wrap(await self.config.get_env("LOG_CHAT_ID"))
        self.bot_mode = (str(await self.config.get_env("BOT_MODE"))).lower() in {
            "yes",
            "true",
            "enable",
        }
        if not restart:
            await self.initialize_telegram_sessions(*args, **kwargs)
        await self.update_cache()

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
                print(self.banner)
                branch_info = get_current_git_branch()
                self.log(f"🌿 Branch: {branch_info}")
                self.log(f"🚀 Altruix v{self.__version__} berjalan!")
                
                if self.training_wheels_protocol:
                    self.log("⚠️ Altruix is in [TWP] mode - userbot features disabled!", level=30)
                
                # ✅ HEALTH CHECK SEBELUM IDLE
                await self._health_check()
                
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
                self.log("User session was found locally, syncing in progress...")
                await self.config.sync_env_to_db("SESSIONS", string_sessions)
            else:
                self.log("Searching in DB for a user session...")
                string_sessions = await self.config.get_env_from_db("SESSIONS")
            if not string_sessions:
                self.training_wheels_protocol = True
                self.log(
                    "No User Session found, all the userbot features will be disabled!",
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
                self.log("User Session found, using it!")
                total_sessions = len(string_sessions)
                unloaded_sessions = []
                for count, each in enumerate(string_sessions):
                    try:
                        client = await Client(
                            f"{count}_instance_Altruix",
                            api_id=self.config.API_ID,
                            api_hash=self.config.API_HASH,
                            session_string=each,
                            workdir="cache",
                        ).start()
                        me = await client.get_me()
                        client.myself = me
                        OWNER_ID = BaseConfig.OWNER_ID
                        first = (me.first_name or "").strip()
                        last = (me.last_name or "").strip()
                        full_name = f"{first} {last}".strip() or "(No Name)"
                        username = f" @{me.username}" if me.username else ""
                        is_owner = " [OWNER]" if me.id == OWNER_ID else ""
                        user_id = me.id
                        self.log(
                            f"[{count + 1}/{total_sessions}] Session Loaded → "
                            f"ID: {user_id} | {full_name} {username} {is_owner}"
                        )
                        self.clients.append(client)
                        if me.id != self.config.OWNER_ID:
                            self.ourselves.append(me)
                    except Exception as err:
                        self.log(f"[{count + 1}/{total_sessions}] Session Unloaded: {err}", level=50)
                        self.log("became unusable, please re-add the session using the assistant bot.")
                        unloaded_sessions.append(each)
                for bad_session in unloaded_sessions:
                    await self.config.pop_element_from_list("SESSIONS", bad_session)
                if not self.clients:
                    await self.config.del_env_from_db("SESSIONS")
                    self.training_wheels_protocol = True
            # =============================================
            # SEMUA CLIENT (BOT + USER SESSION) KIRIM PESAN STARTUP KE LOG_CHAT_ID
            # =============================================
            if BaseConfig.LOG_CHAT_ID:
                # ✅ PERBAIKAN 3: Validasi LOG_CHAT_ID sebelum digunakan
                try:
                    log_chat_id = int(BaseConfig.LOG_CHAT_ID)
                    await self.bot.get_chat(log_chat_id) # Pastikan bot bisa akses
                except (PeerIdInvalid, UserNotParticipant, ValueError) as ve:
                    self.log(f"LOG_CHAT_ID tidak valid atau bot tidak bisa akses: {ve}", level=40)
                    log_chat_id = None
                else:
                    from datetime import datetime
                    startup_time = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
                    all_clients = [self.bot] + self.clients
                    success_count = 0
                    failed_clients = []
                    self.log(f"Mencoba kirim startup log dari {len(all_clients)} client ke LOG_CHAT_ID...")
                    for client in all_clients:
                        try:
                            me = client.myself if hasattr(client, "myself") else await client.get_me()
                            name = f"{me.first_name or ''} {me.last_name or ''}".strip() or "Unknown"
                            username = f" @{me.username}" if me.username else ""
                            user_id = me.id
                            client_type = "🤖 Bot" if client == self.bot else "🦸🏼 Ubot"
                            mention_user = f'<a href="tg://user?id={user_id}">{name}</a>'
                            total_user_sessions = len(self.clients)
                            if client == self.bot:
                                base_text = f"<b>✅ Altruix Bot Assistant is alive!</b>"
                            else:
                                user_index = self.clients.index(client) + 1
                                base_text = f"<b>✅ Altruix Userbot [{user_index}/{total_user_sessions}] is alive!</b>"
                            personal_message = (
                                f"{base_text}\n"
                                f"<b>{client_type}: {mention_user}</b> [ <code>{user_id}</code> ]\n"
                            )
                            await client.send_message(
                                chat_id=log_chat_id,
                                text=personal_message,
                                link_preview_options=LinkPreviewOptions(is_disabled=True)
                            )
                            await asyncio.sleep(3)
                            success_count += 1
                            self.log(f"BERHASIL: [{client_type}] {name} mengirim startup log")
                        except FloodWait as e:
                            self.log(f"FloodWait terdeteksi. Menunggu {e.value} detik...")
                            await asyncio.sleep(e.value + 6)
                        except Exception as e:
                            error_type = type(e).__name__
                            error_msg = str(e)
                            me = client.myself if hasattr(client, "myself") else None
                            name = me.first_name if me else "Unknown"
                            username = f" @{me.username}" if me and me.username else ""
                            client_type = "Bot" if client == self.bot else "User"
                            failed_clients.append(f"• <b>{name}{username}</b> → {error_type}")
                            self.log(f"GAGAL: [{client_type}] {name}{username} → {error_type}: {error_msg}")
                    self.log("=== RINGKASAN PENGIRIMAN STARTUP LOG ===")
                    self.log(f"Berhasil kirim: {success_count}/{len(all_clients)} client")
                    if failed_clients:
                        self.log("Client yang gagal:")
                        for fail in failed_clients:
                            self.log(f" {fail}")
                    else:
                        self.log(f"SEMUA client berhasil mengirim pesan ke LOG_CHAT_ID: {log_chat_id}")
                    if success_count > 0:
                        try:
                            branch = get_current_git_branch()
                            altruix_version = getattr(self, "__version__", "unknown")
                            summary = (
                                "Semua client selesai mengirim startup log!\n"
                                f"Total Session: <code>{len(self.clients)}</code> user + <code>1</code> bot\n"
                                f"Berhasil: <code>{success_count}</code> client\n"
                                f"Gagal: <code>{len(failed_clients)}</code> client\n"
                                f"Owner ID: <code>{BaseConfig.OWNER_ID}</code>\n"
                                f"Branch: <code>{branch}</code>\n"
                                f"Versi: <code>{altruix_version}</code>\n"
                                f"Waktu: <code>{startup_time}</code>"
                            )
                            await self.bot.send_message(log_chat_id, summary)
                            self.log(f"Ringkasan akhir berhasil dikirim. Branch: {branch}, Versi: {altruix_version}")
                        except Exception as e:
                            self.log(f"Gagal kirim ringkasan startup log: {e}", level=logging.ERROR)
        except Exception as e:
            self.log(f"CRITICAL: Session initialization failed: {e}", level=50)
            raise

    async def add_session(self, session: str, status: Message = None) -> Client:
        await self.config.add_element_to_list("SESSIONS", session)
        self.config.append_session(session)
        self.config.SESSIONS.append(session)
        self.log("User session added successfully!")
        if self.training_wheels_protocol:
            self.log("[TWP] has been disabled!")
        app = Client(
            "main_instance",
            api_id=self.config.API_ID,
            api_hash=self.config.API_HASH,
            session_string=session,
            workdir="cache",
        )
        self.clients.append(app)
        await app.start()
        session_user_info = await app.get_me()
        app.myself = session_user_info
        if not app.myself.id == self.config.OWNER_ID:
            self.ourselves.append(session_user_info)
        self.training_wheels_protocol = False
        await self.load_all_modules()
        self.log("Userbot plugins have been loaded.")
        if status:
            await status.edit(
                "<b>Account Successfully added!</b>",
            )
        return app

    async def remove_session(self, index: int) -> User:
        session = self.config.pop_session(index)
        await self.config.pop_element_from_list("SESSIONS", session)
        removed_session_info = self.ourselves.pop(index)
        await self.clients.pop(index).stop()
        if not self.ourselves:
            self.training_wheels_protocol = True
            self.log("[TWP] has been enabled!")
        self.log("User session removed successfully!")
        self.loop.create_task(self.load_all_modules())
        return removed_session_info

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
                args = [sys.executable, "-m", "Main"]
                os.execle(sys.executable, *args, os.environ)
            if not self.training_wheels_protocol and not self.clients:
                for each in self.clients:
                    await each.restart()
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
                        sys.modules[import_path + plugin_name] = load
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
