# Main/plugins/userbot/xjoin_logger.py
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
SETTINGS_FILE = Path("join_logger_settings.json")

# Default settings
JOIN_LOGGER_DATA = {
    "enabled": True  # ON by default
}

def load_settings():
    """Load join logger settings from file."""
    global JOIN_LOGGER_DATA
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r") as f:
                JOIN_LOGGER_DATA.update(json.load(f))
        except:
            pass

def save_settings():
    """Save join logger settings to file."""
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(JOIN_LOGGER_DATA, f, indent=4)
    except Exception as e:
        print(f"Failed to save join logger settings: {e}")

# Load settings on startup
load_settings()

@Altruix.on_message(filters.new_chat_members, group=-1, bot_mode_unsupported=True)
@log_errors
async def join_logger_handler(c: Client, m: Message):
    """Log when userbot joins or is invited to groups/channels."""
    try:
        if not JOIN_LOGGER_DATA.get("enabled", True):
            return
            
        # Check if this is about the current userbot
        for new_member in m.new_chat_members:
            if new_member.id == c.me.id:
                chat = m.chat
                invited_by = m.from_user
                
                # Determine chat type
                chat_type = "Channel" if chat.type == enums.ChatType.CHANNEL else "Group"
                
                # Build log message
                log_message = (
                    f"🔔 <b>Join Event Detected</b>\n\n"
                    f"👤 <b>Account:</b> {c.me.mention(style=enums.ParseMode.HTML)}\n"
                    f"💬 <b>{chat_type}:</b> {chat.title} (<code>{chat.id}</code>)\n"
                )
                
                if invited_by:
                    log_message += f"👥 <b>Invited By:</b> {invited_by.mention(style=enums.ParseMode.HTML)} (<code>{invited_by.id}</code>)\n"
                else:
                    log_message += f"✅ <b>Action:</b> Joined via link\n"
                    
                log_message += f"🕒 <b>Time:</b> <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>"
                
                # Send to log chat
                await Altruix.bot.send_message(
                    Altruix.log_chat,
                    log_message,
                    parse_mode=enums.ParseMode.HTML
                )
                break  # Only log once per join event
            
    except Exception as e:
        print(f"Join logger error: {e}")

@Altruix.register_on_cmd(
    ["joinlogger", "jlog"],
    cmd_help={
        "help": "Monitor and log when the userbot joins or is invited to chats.",
        "usage": ".joinlogger <on/off/status>",
        "example": ".joinlogger on",
        "user_args": {
            "on": "Enable join logging.",
            "off": "Disable join logging.",
            "status": "Show current configuration status.",
        },
        "detail": "Logs include the chat title, ID, account name, and the user who invited the bot (if applicable) to the designated Log Group."
    },
)
async def join_logger_toggle(c: Client, m: Message):
    """Toggle join logger on/off."""
    arg = m.user_input.lower() if m.user_input else "status"
    
    if arg == "on":
        JOIN_LOGGER_DATA["enabled"] = True
        save_settings()
        await m.handle_message("✅ <b>Join Logger enabled!</b>")
    elif arg == "off":
        JOIN_LOGGER_DATA["enabled"] = False
        save_settings()
        await m.handle_message("❌ <b>Join Logger disabled!</b>")
    else:
        status = "✅ Enabled" if JOIN_LOGGER_DATA.get("enabled", True) else "❌ Disabled"
        await m.handle_message(
            f"<b>Join Logger Status:</b> {status}\n\n"
            f"<i>Use</i> <code>.joinlogger on/off</code> <i>to toggle</i>"
        )
