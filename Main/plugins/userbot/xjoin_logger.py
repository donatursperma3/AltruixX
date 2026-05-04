# Main/plugins/userbot/xjoin_logger.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.


PLUGIN_VERSION = "0.0.3"
from Main import Altruix
from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
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
                data = json.load(f)
                if "global" in data:
                    JOIN_LOGGER_DATA = data
                else:
                    # Migration
                    JOIN_LOGGER_DATA = {"global": {"enabled": data.get("enabled", True)}, "sessions": {}, "apply_types": {}}
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

@Altruix.on_chat_member_updated(group=-1, bot_mode_unsupported=True)
@log_errors
async def join_logger_handler(c: Client, u):
    """Log when userbot joins or is invited to groups/channels."""
    try:
        # Dynamic Reload
        load_settings()
        
        user_id_str = str(c.me.id)
        apply_type = JOIN_LOGGER_DATA.get("apply_types", {}).get(user_id_str, "per_account")
        
        if apply_type == "global":
            is_enabled = JOIN_LOGGER_DATA.get("global", {}).get("enabled", True)
        else:
            session_config = JOIN_LOGGER_DATA.get("sessions", {}).get(user_id_str, JOIN_LOGGER_DATA.get("global", {}))
            if isinstance(session_config, bool):
                 is_enabled = session_config
            else:
                 is_enabled = session_config.get("enabled", True)

        if not is_enabled:
            return

        # Check if new_chat_member exists
        if getattr(u, "new_chat_member", None) is None: return

        # 🛑 Ensure it only logs events involving the current userbot session
        new_user_id = getattr(u.new_chat_member.user, "id", None)
        if new_user_id != c.me.id:
            return

        # ✅ Refresh 'me' to ensure nickname is up-to-date
        me = await c.get_me()
            
        new_status = getattr(u.new_chat_member, "status", None)
        
        old_status = enums.ChatMemberStatus.LEFT
        if getattr(u, "old_chat_member", None):
            old_status = getattr(u.old_chat_member, "status", enums.ChatMemberStatus.LEFT)
        
        joined_statuses = [
            enums.ChatMemberStatus.MEMBER,
            enums.ChatMemberStatus.ADMINISTRATOR,
            enums.ChatMemberStatus.RESTRICTED
        ]
        left_statuses = [
            enums.ChatMemberStatus.LEFT,
            enums.ChatMemberStatus.BANNED
        ]
        
        if new_status in joined_statuses and old_status in left_statuses:
            chat = u.chat
            invited_by = u.from_user
            
            # Determine chat type
            chat_type = "Channel" if chat.type == enums.ChatType.CHANNEL else "Group"
            
            # Generate Chat Link
            if chat.username:
                chat_link = f"https://t.me/{chat.username}"
                group_link = chat_link
            else:
                # Private chat: t.me/c/123456789/999999999
                # Strip -100 prefix if present
                chat_id_str = str(chat.id)
                if chat_id_str.startswith("-100"):
                    real_id = chat_id_str[4:]
                else:
                    real_id = chat_id_str.replace("-", "")
                
                chat_link = f"https://t.me/c/{real_id}/999999999"
                # Cannot link to private group title easily without invite link
                group_link = chat_link 

            # Build log message
            log_message = (
                f"🔔 <b>Join Event Detected</b>\n\n"
                f"👤 <b>Account:</b> {me.mention(style=enums.ParseMode.HTML)} (<code>{me.id}</code>)\n"
                f"💬 <b>{chat_type}:</b> <a href='{group_link}'>{chat.title}</a> (<code>{chat.id}</code>)\n"
            )
            
            if invited_by and invited_by.id != me.id:
                log_message += f"👥 <b>Invited By:</b> {invited_by.mention(style=enums.ParseMode.HTML)} (<code>{invited_by.id}</code>)\n"
            else:
                log_message += f"✅ <b>Action:</b> Joined via link or naturally\n"
                
            log_message += f"🕒 <b>Time:</b> <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>"
            
            # Send to log chat
            bot = Altruix.bot_manager.get_bot(c.me.id)
            from Main.utils.essentials import Essentials
            await bot.send_message(
                Altruix.log_chat,
                log_message,
                parse_mode=enums.ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(await Essentials.get_user_button_style(c.me.id, "Go to Chat ↗️"), url=chat_link)]
                ])
            )
            
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
        if "global" not in JOIN_LOGGER_DATA: JOIN_LOGGER_DATA["global"] = {}
        JOIN_LOGGER_DATA["global"]["enabled"] = True
        JOIN_LOGGER_DATA["enabled"] = True  # Legacy sync
        save_settings()
        await m.handle_message("✅ <b>Join Logger enabled (Global)!</b>")
    elif arg == "off":
        if "global" not in JOIN_LOGGER_DATA: JOIN_LOGGER_DATA["global"] = {}
        JOIN_LOGGER_DATA["global"]["enabled"] = False
        JOIN_LOGGER_DATA["enabled"] = False # Legacy sync
        save_settings()
        await m.handle_message("❌ <b>Join Logger disabled (Global)!</b>")
    else:
        is_on = JOIN_LOGGER_DATA.get("global", {}).get("enabled", JOIN_LOGGER_DATA.get("enabled", True))
        status = "✅ Enabled" if is_on else "❌ Disabled"
        await m.handle_message(
            f"<b>Join Logger Status (Global):</b> {status}\n\n"
            f"<i>Use</i> <code>.joinlogger on/off</code> <i>to toggle global status.</i>"
        )
