# settings.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix/Altruix >
# All rights reserved.

from Main import Altruix
from Main.core.config import BaseConfig
from typing import List, Tuple, Dict, Any, Union, Optional
from pyrogram import Client, filters, raw
from Main.core.decorators import log_errors, iuser_check
from Main.core.types.message import Message
from pyrogram.types import (
    CallbackQuery, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove,
    InlineKeyboardButton, InlineKeyboardMarkup, LinkPreviewOptions, User,
    Chat, MessageEntity, InlineQuery, InlineQueryResultArticle, InputTextMessageContent
)
import json
import os
import logging
import asyncio
import html
from datetime import datetime
import io
import re

# ====================== ERROR HANDLING & IMPORTS ======================
from pyrogram.errors import (
    PeerIdInvalid, UserIsBlocked, ChatWriteForbidden, FloodWait, MessageIdInvalid,
    SlowmodeWait, InviteHashInvalid, InviteHashExpired, UserAlreadyParticipant,
    ChatAdminRequired, UsernameNotOccupied, ChannelPrivate, UsernameInvalid,
    UsernameNotModified, AboutTooLong, PhotoInvalidDimensions,
    PhotoSaveFileInvalid, UsernameOccupied, RPCError, QueryIdInvalid
)

try:
    from pyrogram.errors import FirstNameInvalid
except ImportError:
    class FirstNameInvalid(Exception): pass

from pyrogram.errors import UserIsBlocked as BotBlocked
from pyromod.exceptions import ListenerTimeout
from pyrogram.enums import ParseMode, ChatType

# Utils & Helpers
from Main.internals.get_session import add_session_cb_handler
from Main.utils.file_helpers import get_db_path

# ====================== AUTHORIZATION HELPER ======================
def is_authorized(user_id: int) -> bool:
    return user_id == Altruix.config.OWNER_ID or user_id in Altruix.config.SUDO_USERS

async def check_authorization(cb: CallbackQuery) -> bool:
    from .settings_handlers.utils import check_authorization as modular_check
    return await modular_check(cb)

async def check_authorization_message(m: Message) -> bool:
    from .settings_handlers.utils import check_authorization_message as modular_check_msg
    return await modular_check_msg(m)

async def edit_cb(cb: CallbackQuery, text: str, **kwargs):
    return await Altruix.edit_cb(cb, text, **kwargs)

async def delete_cb(cb: CallbackQuery):
    return await Altruix.delete_cb(cb)

# ====================== PLUGIN METADATA ======================
PLUGIN_VERSION = "1.5.5.9b"
logger = logging.getLogger("altruix.settings")

# ====================== SHARED STATES ======================
# Re-exported or used by sub-handlers
user_confirmation_state = {}
user_text_confirmation_state = {}
user_bulk_join_state = {}
user_dlphoto_state = {}
user_purge_state = {}
user_eval_state = {}
user_exec_state = {}
user_sys_ctrl_state = {}
user_profile_edit_state = {}
user_photo_delete_state = {}
user_edit_confirmation_state = {}
user_mentions_state = {}
user_recent_messages_state = {}
user_message_count_state = {}
user_limit_check_state = {}
user_dlstory_state = {}

# ====================== MODULAR IMPORTS ======================
# Note: Handlers are registered in the sub-modules
import Main.internals.settings_handlers.session_info
import Main.internals.settings_handlers.profile_handlers
import Main.internals.settings_handlers.bulk_handlers
import Main.internals.settings_handlers.system_handlers
import Main.internals.settings_handlers.security_handlers
import Main.internals.settings_handlers.privacy_handlers
import Main.internals.settings_handlers.stats_handlers
import Main.internals.settings_handlers.media_handlers
import Main.internals.settings_handlers.startup_handlers
import Main.internals.settings_handlers.logger_handlers
import Main.internals.settings_handlers.env_handlers
import Main.internals.settings_handlers.toggle_session_handlers
import Main.internals.settings_handlers.sessions_list
import Main.internals.settings_handlers.export_handlers
import Main.internals.settings_handlers.cmd_settings_handlers
import Main.internals.settings_handlers.global_purgeme

# ====================== LOCALIZATION ======================
SETTINGS_LANG = getattr(Altruix.config, "UB_LANG", "english").lower()

def gt(key):
    val = Altruix.get_string(key)
    if val and val != key: return val
    # Fallback strings for hardcoded UI elements if needed
    return key

# ====================== UI HELPERS ======================
CUSTOM_LINK_FILE = get_db_path("custom_button_settings.json")

def get_custom_link_data():
    if not os.path.exists(CUSTOM_LINK_FILE):
        return {"global": {"text": "Repo", "link": "https://t.me/AlphaXProject"}, "sessions": {}, "apply_types": {}}
    with open(CUSTOM_LINK_FILE, "r") as f:
        try: return json.load(f)
        except: return {"global": {"text": "Repo", "link": "https://t.me/AlphaXProject"}, "sessions": {}, "apply_types": {}}

def save_custom_link_data(data):
    with open(CUSTOM_LINK_FILE, "w") as f: json.dump(data, f, indent=4)

def get_user_custom_link(user_id):
    data = get_custom_link_data()
    apply_type = data.get("apply_types", {}).get(str(user_id), "global")
    if apply_type == "per_account" and str(user_id) in data.get("sessions", {}):
        return data["sessions"][str(user_id)]
    return data["global"]

def get_settings_buttons(user_id=None):
    custom_data = get_user_custom_link(user_id) if user_id else get_custom_link_data()["global"]
    return [
        [
            InlineKeyboardButton("📱 Sessions", callback_data="sessions_list_1"),
            InlineKeyboardButton("🤖 Bot Controls", callback_data="bot_controls_menu"),
        ],
        [
            InlineKeyboardButton("⚙️ Configs", callback_data="configs_home"),
            InlineKeyboardButton("⌨️ Cmd Settings", callback_data="cmd_settings_menu"),
        ],
        [
            InlineKeyboardButton("❇️ Help Menu", callback_data="re_open"),
            InlineKeyboardButton(custom_data.get("text", "Repo"), url=custom_data.get("link", "https://t.me/AlphaXProject")),
        ],
    ]

# ====================== CORE SETTINGS HANDLERS ======================

@Altruix.bot.on_message(filters.command("settings", "/") & filters.user(Altruix.auth_users))
@iuser_check
@log_errors
async def settings_command_handler(c: Client, m: Message):
    """Entry point for /settings command."""
    from Main.internals.settings_handlers.stats_handlers import sessions_stats_cb_handler
    # Forwarding stats logic is usually better but for simplicity we keep basic info
    total_sessions = len(Altruix.clients)
    total_bots = 1 + (len(Altruix.bot_manager.custom_bots) if hasattr(Altruix, 'bot_manager') else 0)
    
    text = (
        f"<b>🛠️ Userbot Settings</b>\n\n"
        f"• Sessions: <code>{total_sessions}</code>\n"
        f"• Active Bots: <code>{total_bots}</code>\n"
        f"• Version: <code>{Altruix.__version__}</code>\n\n"
        f"Select a category below to configure your userbot."
    )
    await m.reply(text, reply_markup=InlineKeyboardMarkup(get_settings_buttons(m.from_user.id)), quote=True)

@Altruix.bot.on_inline_query(filters.regex(r"^settings$"))
@iuser_check
@log_errors
async def settings_inline_handler(c: Client, iq: InlineQuery):
    """Inline entry point for settings."""
    if iq.from_user.id not in Altruix.auth_users: return
    
    total_sessions = len(Altruix.clients)
    text = f"<b>🛠️ Userbot Settings</b>\n\nTotal Sessions: <code>{total_sessions}</code>"
    
    await iq.answer(
        results=[
            InlineQueryResultArticle(
                title="Userbot Settings",
                input_message_content=InputTextMessageContent(text, parse_mode=ParseMode.HTML),
                reply_markup=InlineKeyboardMarkup(get_settings_buttons(iq.from_user.id))
            )
        ],
        cache_time=0, is_personal=True
    )

@Altruix.bot.on_callback_query(filters.regex(r"^settings_menu$"))
@iuser_check
@log_errors
async def settings_menu_cb_handler(c: Client, cb: CallbackQuery):
    """Main settings menu return point."""
    await cb.answer()
    total_sessions = len(Altruix.clients)
    text = f"<b>🛠️ Userbot Settings Dashboard</b>\n\nTotal Sessions: <code>{total_sessions}</code>"
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(get_settings_buttons(cb.from_user.id)))

@Altruix.bot.on_callback_query(filters.regex(r"^configs_home$"))
@iuser_check
@log_errors
async def configs_menu_cb_handler(c: Client, cb: CallbackQuery):
    await cb.answer()
    text = "<b>⚙️ Configuration Manager</b>\n\nManage environment variables and bot configs."
    buttons = [
        [InlineKeyboardButton("🔧 ENV Manager", callback_data="env_manager_list_1")],
        [InlineKeyboardButton("🔙 Back to Settings", callback_data="settings_menu")]
    ]
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons))

@Altruix.bot.on_callback_query(filters.regex(r"^bot_controls_menu$"))
@iuser_check
@log_errors
async def bot_controls_menu_handler(c: Client, cb: CallbackQuery):
    await cb.answer()
    text = "<b>🤖 Bot Controls</b>\n\nManage Bot Assistant behaviors globally."
    buttons = [
        [
            InlineKeyboardButton("📟 PM Logger Bot", callback_data="pmlb_menu"),
            InlineKeyboardButton("🔘 Callback Logger", callback_data="cb_logger_settings"),
        ],
        [
            InlineKeyboardButton("🔔 Mention Logger", callback_data="mntlb_menu"),
            InlineKeyboardButton("💬 Reply Manager", callback_data="reply_manager_menu"),
        ],
        [
            InlineKeyboardButton("🚪 Join Logger Global", callback_data="joinl_menu_global"),
            InlineKeyboardButton("🔗 Group Log Link", callback_data="get_log_group_link"),
        ],
        [
            InlineKeyboardButton("👽 Custom Bot Manager", callback_data="custom_bot_manager"),
            InlineKeyboardButton("🔘 Custom Link/Text", callback_data="custom_link_settings"),
        ],
        [InlineKeyboardButton("🔙 Back to Settings", callback_data="settings_menu")]
    ]
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons))

# ====================== SHARED UTILS ======================
async def send_log_notification(*args, **kwargs):
    # This is a bridge to the modular version if needed, 
    # but sub-handlers should import it directly from their own utils.
    from .settings_handlers.utils import send_log_notification as modular_sln
    return await modular_sln(*args, **kwargs)

# Handle Global Close
@Altruix.bot.on_callback_query(filters.regex(r"^create_close$"))
@iuser_check
@log_errors
async def create_close_handler(c: Client, cb: CallbackQuery):
    try: await cb.message.delete()
    except: pass

# End of modular settings.py
