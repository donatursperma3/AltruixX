# Main/plugins/userbot/xcmd_logger.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.

import html
import json
import logging
from datetime import datetime
from pathlib import Path

from pyrogram import Client, enums, filters
from pyrogram.types import Message

from Main import Altruix
from Main.core.decorators import log_errors

PLUGIN_VERSION = "0.0.381"
logger = logging.getLogger("altruix.xcmd_logger")

# Settings file
SETTINGS_FILE = Path("cmd_logger_settings.json")

# Default settings (Legacy fallback)
CMD_LOGGER_DATA = {
    "enabled": False
}

# ✅ CRITICAL FIX: Cache untuk settings agar tidak query DB setiap command
from cachetools import TTLCache
import asyncio

CMD_LOGGER_SETTINGS_CACHE = TTLCache(maxsize=100, ttl=60)  # Cache 60 detik
CMD_CACHE_LOCK = asyncio.Lock()

def load_settings():
    """Load cmd logger settings from file for legacy/initial states."""
    global CMD_LOGGER_DATA
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r") as f:
                data = json.load(f)
                if "global" in data:
                    CMD_LOGGER_DATA = data
                else:
                    # Migration
                    CMD_LOGGER_DATA = {"global": {"enabled": data.get("enabled", False)}, "sessions": {}, "apply_types": {}}
        except:
            pass

# Load settings on startup
load_settings()

async def get_cmd_logger_settings(user_id, index):
    """
    Get cmd logger settings with caching to prevent excessive DB queries.
    
    ✅ OPTIMIZED: Uses TTL cache to prevent DB query on every command.
    """
    cache_key = f"cmdl_{user_id}_{index}"
    
    # Check cache first
    async with CMD_CACHE_LOCK:
        if cache_key in CMD_LOGGER_SETTINGS_CACHE:
            return CMD_LOGGER_SETTINGS_CACHE[cache_key]
    
    # Fetch from DB
    apply_type = await Altruix.config.get_env(f"CMDL_LOGGER_APPLY_TYPE_{index}") or "global"
    if apply_type == "global":
        status = await Altruix.config.get_env("CMDL_LOGGER_GLOBAL") or "off"
    else:
        status = await Altruix.config.get_env(f"CMDL_LOGGER_{index}") or "off"
    
    prefix_apply_type = await Altruix.config.get_env("PREFIX_APPLY_TYPE") or "global"
    pk = "PREFIX_OWNER_USER" if prefix_apply_type == "global" else f"PREFIX_OWNER_USER_{user_id}"
    prefix = await Altruix.config.get_env(pk) or "."
    
    autodel_type = await Altruix.config.get_env(f"AUTO_DELETE_CMD_TYPE_{index}") or "per_account"
    if autodel_type == "global":
        autodel_status = await Altruix.config.get_env("AUTO_DELETE_CMD_GLOBAL")
    else:
        autodel_status = await Altruix.config.get_env(f"AUTO_DELETE_CMD_STATUS_{index}")
    
    settings = {
        "status": status,
        "prefix": prefix,
        "autodel_status": autodel_status
    }
    
    # Store in cache
    async with CMD_CACHE_LOCK:
        CMD_LOGGER_SETTINGS_CACHE[cache_key] = settings
    
    return settings

@Altruix.on_message(filters.me, group=0, allow_commands=True)
@log_errors
async def cmd_logger_handler(c: Client, m: Message):
    """
    Log all commands executed by userbot.
    Optimized to use cached settings for real-time status check.
    
    ✅ OPTIMIZED: Uses cached settings to prevent DB queries on every command.
    """
    try:
        # Aggressive DEBUG
        text = m.text or m.caption or ""
        # Altruix.log(f"DEBUG: CmdLogger received message: '{text[:20]}...'", level=logging.INFO)

        # 1. Identify context by ID
        user_id = c.me.id
        index = -1
        for i, client in enumerate(Altruix.clients):
            if hasattr(client, 'me') and client.me and client.me.id == user_id:
                index = i
                break
        
        if index == -1:
            Altruix.log(f"DEBUG: CmdLogger - Index not found for user {user_id}", level=logging.WARNING)
            return

        # 2. Get cached settings (prevents multiple DB queries)
        settings = await get_cmd_logger_settings(user_id, index)
        
        if settings["status"] != "on":
            return
        
        # 3. Check prefix
        if not text.startswith(settings["prefix"]):
            return

        # 4. Get autodel status from cached settings
        autodel_status = settings["autodel_status"]
        
        autodel_enabled = str(autodel_status).lower() in ("on", "true", "1", "yes")

        # 5. Filter Specific Noise
        cmd_part = text[len(settings["prefix"]):].split()[0].lower() if len(text) > len(settings["prefix"]) else ""
        if cmd_part in ["cmdlogger", "cmdlog"]:
            return
            
        Altruix.log(f"⚡ [CMD_LOGGER] Detected command: '{cmd_part}' from user {user_id}", level=logging.INFO)
            
        # 6. Build and send log
        chat = m.chat
        chat_title = chat.title or f"{chat.first_name or ''} {chat.last_name or ''}".strip() or "Private Chat"
        
        # Clickable Link Logic
        chat_link = None
        msg_link = None
        if chat.username:
            chat_link = f"https://t.me/{chat.username}"
            msg_link = f"https://t.me/{chat.username}/{m.id}"
        elif chat.type == enums.ChatType.PRIVATE:
            chat_link = f"tg://user?id={chat.id}"
            # No universal web link for PMs, using tg:// for deep link if possible,
            # but usually for self-audit we just use nothing or chat link
        elif str(chat.id).startswith("-100"):
            stripped_id = str(chat.id).replace("-100", "")
            chat_link = f"https://t.me/c/{stripped_id}/{m.id}" # This link works better as a joiner in Pyrogram logs
            msg_link = f"https://t.me/c/{stripped_id}/{m.id}"
            
        chat_display = f"<a href='{chat_link}'>{html.escape(chat_title)}</a>" if chat_link else f"<b>{html.escape(chat_title)}</b>"
        
        msg_link_display = f"[ <a href='{msg_link}'>here</a> ]" if msg_link else " N/A"

        log_message = (
            f"⚡️ <b>Command Executed</b>\n"
            f"<blockquote expandable>\n"
            f"👤 <b>Account:</b> <b>{c.me.mention(style=enums.ParseMode.HTML)}</b>\n"
            f"💬 <b>Chat:</b> {chat_display}\n"
            f"🆔 <b>ChatID:</b> <code>{chat.id}</code>\n"
            f"♻️ <b>Auto del:</b> <code>{autodel_enabled}</code>\n"
            f"➡️ <b>Goto Msg:</b> {msg_link_display}\n"
        )
        
        # ✅ Add Active Task IDs from global registry
        try:
            if hasattr(Altruix, '_TASK_REGISTRY') and Altruix._TASK_REGISTRY:
                active_tasks = [
                    (tid, t) for tid, t in Altruix._TASK_REGISTRY.items()
                    if t.get("task") and not t["task"].done()
                ]
                if active_tasks:
                    parts_list = []
                    for tid, t in active_tasks:
                        name = t.get("name", "?")[:15]
                        parts_list.append(f"<code>{tid}</code> ({name})")
                    log_message += f"🏷 <b>Active Tasks:</b> {', '.join(parts_list)}\n"
        except Exception:
            pass
        
        # ✅ Add Reply Info if applicable
        if m.reply_to_message:
            reply_user = m.reply_to_message.from_user
            if reply_user:
                r_mention = reply_user.mention(style=enums.ParseMode.HTML)
                r_id = reply_user.id
                r_username = f"@{reply_user.username}" if reply_user.username else "N/A"
                
                log_message += (
                    f"↩️ <b>Reply to user:</b> {r_mention}\n"
                    f"🆔 <b>UserID :</b> <code>{r_id}</code>\n"
                    f"*️⃣ <b>Username:</b> {r_username}\n"
                )
        
        log_message += f"🕒 <b>Time:</b> <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code></blockquote>"
        
        # 📝 Command at the bottom in a separate blockquote
        log_message += f"\n\n📝 <b>Command:</b>\n<pre language='python'>{html.escape(text[:2000])}</pre>"
        
        # Consistently use main Bot
        bot = Altruix.bot
        if not bot:
             Altruix.log("DEBUG: CmdLogger - Main Bot NOT FOUND!", level=logging.ERROR)
             return

        # Verify Log Chat
        if not Altruix.log_chat:
            Altruix.log("DEBUG: CmdLogger - Altruix.log_chat is NOT SET!", level=logging.ERROR)
            return

        async def _log_task():
            try:
                await bot.send_message(
                    Altruix.log_chat,
                    log_message,
                    parse_mode=enums.ParseMode.HTML,
                    disable_web_page_preview=True
                )
                Altruix.log(f"✅ [CMD_LOGGER] Log sent successfully to {Altruix.log_chat}", level=logging.INFO)
            except Exception as send_err:
                Altruix.log(f"❌ [CMD_LOGGER] Failed to send message: {send_err}", level=logging.ERROR)
        
        asyncio.create_task(_log_task())
        
    except Exception as e:
        Altruix.log(f"Cmd logger fatal error: {e}", level=40)

@Altruix.register_on_cmd(
    ["cmdlogger", "cmdlog"],
    cmd_help={
        "help": "Log all commands executed by the userbot for auditing.",
        "usage": ".cmdlogger <on/off/status>",
        "example": ".cmdlogger on",
        "user_args": {
            "on": "Enable command logging.",
            "off": "Disable command logging.",
            "status": "Show current configuration status.",
        },
        "detail": "Logs the command text, chat info, and execution time to the Log Group."
    },
)
async def cmd_logger_toggle(c: Client, m: Message):
    """
    Toggle command logger on/off.
    This UI command still syncs to JSON for backward/external compatibility.
    """
    arg = m.user_input.lower() if m.user_input else "status"
    
    # Identify index for DB update
    user_id = c.me.id
    index = -1
    for i, client in enumerate(Altruix.clients):
        if hasattr(client, 'me') and client.me and client.me.id == user_id:
            index = i
            break
            
    if index == -1: return

    if arg in ["on", "off"]:
        new_val = "on" if arg == "on" else "off"
        # 1. Update DB (Primary)
        key = "CMDL_LOGGER_GLOBAL" # Default to global for .cmdlogger command
        await Altruix.config.sync_env_to_db(key, new_val, upsert=True)
        setattr(Altruix.config, key, new_val)
        
        # 2. Sync to JSON (Secondary)
        if "global" not in CMD_LOGGER_DATA: CMD_LOGGER_DATA["global"] = {}
        CMD_LOGGER_DATA["global"]["enabled"] = (new_val == "on")
        CMD_LOGGER_DATA["enabled"] = (new_val == "on")
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(CMD_LOGGER_DATA, f, indent=4)
        except: pass
        
        status_msg = f"✅ <b>Command Logger enabled (Global)!</b>" if arg == "on" else f"❌ <b>Command Logger disabled (Global)!</b>"
        await m.handle_message(status_msg)
    else:
        is_on = (await Altruix.config.get_env("CMDL_LOGGER_GLOBAL")) == "on"
        status = "✅ Enabled" if is_on else "❌ Disabled"
        await m.handle_message(
            f"<b>Command Logger Status (Global):</b> {status}\n\n"
            f"<i>Use</i> <code>.cmdlogger on/off</code> <i>to toggle global status.</i>"
        )
