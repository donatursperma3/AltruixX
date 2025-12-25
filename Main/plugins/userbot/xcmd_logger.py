# Main/plugins/userbot/xcmd_logger.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.

from Main import Altruix
from pyrogram import Client, filters, enums
from pyrogram.types import Message
from Main.core.decorators import log_errors
from datetime import datetime
import json
from pathlib import Path

# Settings file
SETTINGS_FILE = Path("cmd_logger_settings.json")

# Default settings
CMD_LOGGER_DATA = {
    "enabled": False  # OFF by default
}

def load_settings():
    """Load cmd logger settings from file."""
    global CMD_LOGGER_DATA
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r") as f:
                CMD_LOGGER_DATA.update(json.load(f))
        except:
            pass

def save_settings():
    """Save cmd logger settings to file."""
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(CMD_LOGGER_DATA, f, indent=4)
    except Exception as e:
        print(f"Failed to save cmd logger settings: {e}")

# Load settings on startup
load_settings()

@Altruix.on_message(filters.me & filters.command([], prefixes=Altruix.user_command_handler), group=99)
@log_errors
async def cmd_logger_handler(c: Client, m: Message):
    """Log all commands executed by userbot."""
    try:
        if not CMD_LOGGER_DATA.get("enabled", False):
            return
            
        # Don't log the cmdlogger command itself
        if m.text and any(m.text.startswith(f"{Altruix.user_command_handler}{cmd}") for cmd in ["cmdlogger", "cmdlog"]):
            return
            
        # Extract command
        cmd_text = m.text or m.caption or ""
        
        # Build log message
        log_message = (
            f"⚡ <b>Command Executed</b>\n\n"
            f"👤 <b>Account:</b> {c.me.mention(style=enums.ParseMode.HTML)}\n"
            f"💬 <b>Chat:</b> {m.chat.title or 'Private'} (<code>{m.chat.id}</code>)\n"
            f"📝 <b>Command:</b> <code>{cmd_text[:100]}</code>\n"
            f"🕒 <b>Time:</b> <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>"
        )
        
        # Send to log chat
        await Altruix.bot.send_message(
            Altruix.log_chat,
            log_message,
            parse_mode=enums.ParseMode.HTML
        )
        
    except Exception as e:
        print(f"Cmd logger error: {e}")

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
    """Toggle command logger on/off."""
    arg = m.user_input.lower() if m.user_input else "status"
    
    if arg == "on":
        CMD_LOGGER_DATA["enabled"] = True
        save_settings()
        await m.handle_message("✅ <b>Command Logger enabled!</b>")
    elif arg == "off":
        CMD_LOGGER_DATA["enabled"] = False
        save_settings()
        await m.handle_message("❌ <b>Command Logger disabled!</b>")
    else:
        status = "✅ Enabled" if CMD_LOGGER_DATA.get("enabled", False) else "❌ Disabled"
        await m.handle_message(
            f"<b>Command Logger Status:</b> {status}\n\n"
            f"<i>Use</i> <code>.cmdlogger on/off</code> <i>to toggle</i>"
        )
