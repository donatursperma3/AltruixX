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

PLUGIN_VERSION = "0.0.31"
logger = logging.getLogger("altruix.xcmd_logger")

# Settings file
SETTINGS_FILE = Path("cmd_logger_settings.json")

# Default settings (Legacy fallback)
CMD_LOGGER_DATA = {
    "enabled": False
}

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

@Altruix.on_message(filters.me, group=0, allow_commands=True)
@log_errors
async def cmd_logger_handler(c: Client, m: Message):
    """
    Log all commands executed by userbot.
    Optimized to use Altruix.config for real-time status check.
    """
    try:
        # Aggressive DEBUG
        text = m.text or m.caption or ""
        # Altruix.log(f"DEBUG: CmdLogger received message: '{text[:20]}...'", level=logging.INFO)

        # 1. Identify context by ID
        user_id = c.me.id
        index = -1
        for i, client in enumerate(Altruix.clients):
            if client.me and client.me.id == user_id:
                index = i
                break
        
        if index == -1:
            Altruix.log(f"DEBUG: CmdLogger - Index not found for user {user_id}", level=logging.WARNING)
            return

        # 2. Check enablement
        apply_type = await Altruix.config.get_env(f"CMDL_LOGGER_APPLY_TYPE_{index}") or "global"
        if apply_type == "global":
            status = await Altruix.config.get_env("CMDL_LOGGER_GLOBAL") or "off"
        else:
            status = await Altruix.config.get_env(f"CMDL_LOGGER_{index}") or "off"

        if status != "on":
            # Altruix.log(f"DEBUG: CmdLogger - Feature is {status} for index {index}", level=logging.INFO)
            return
            
        # 3. Detect prefix
        prefix_apply_type = await Altruix.config.get_env("PREFIX_APPLY_TYPE") or "global"
        pk = "CMD_HANDLER" if prefix_apply_type == "global" else f"CMD_HANDLER_{user_id}"
        prefix = await Altruix.config.get_env(pk) or "."
        
        if not text.startswith(prefix):
            # Altruix.log(f"DEBUG: CmdLogger - Text '{text[:10]}' doesn't start with prefix '{prefix}'", level=logging.INFO)
            return

        # 4. Filter Specific Noise
        cmd_part = text[len(prefix):].split()[0].lower() if len(text) > len(prefix) else ""
        if cmd_part in ["cmdlogger", "cmdlog"]:
            return
            
        Altruix.log(f"⚡ [CMD_LOGGER] Detected command: '{cmd_part}' from user {user_id}", level=logging.INFO)

        # 5. Build and send log
        log_message = (
            f"⚡ <b>Command Executed</b>\n\n"
            f"👤 <b>Account:</b> {c.me.mention(style=enums.ParseMode.HTML)}\n"
            f"💬 <b>Chat:</b> {m.chat.title or 'Private'} (<code>{m.chat.id}</code>)\n"
            f"📝 <b>Command:</b> <code>{html.escape(text[:500])}</code>\n"
            f"🕒 <b>Time:</b> <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>"
        )
        
        # Consistently use main Bot
        bot = Altruix.bot
        if not bot:
             Altruix.log("DEBUG: CmdLogger - Main Bot NOT FOUND!", level=logging.ERROR)
             return

        # Verify Log Chat
        if not Altruix.log_chat:
            Altruix.log("DEBUG: CmdLogger - Altruix.log_chat is NOT SET!", level=logging.ERROR)
            return

        try:
            await bot.send_message(
                Altruix.log_chat,
                log_message,
                parse_mode=enums.ParseMode.HTML
            )
            Altruix.log(f"✅ [CMD_LOGGER] Log sent successfully to {Altruix.log_chat}", level=logging.INFO)
        except Exception as send_err:
            Altruix.log(f"❌ [CMD_LOGGER] Failed to send message: {send_err}", level=logging.ERROR)
        
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
        if client.me and client.me.id == user_id:
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
