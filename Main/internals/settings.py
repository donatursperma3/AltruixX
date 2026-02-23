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
    Chat, MessageEntity, InlineQuery, InlineQueryResultArticle, InputTextMessageContent,
    ChosenInlineResult
)
import json
import os
import logging
import asyncio
import html
import glob
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
from pyrogram.enums import ParseMode, ButtonStyle
from pyrogram import enums, types

# Utils & Helpers
from Main.internals.get_session import add_session_cb_handler
from Main.utils.file_helpers import get_db_path

# ====================== AUTHORIZATION HELPER ======================
async def is_authorized(user_id: int) -> bool:
    """✅ Check if user is authorized using centralized database-aware helper."""
    return await Altruix.is_sudo(user_id)

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
PLUGIN_VERSION = "1.5.5.10b"
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
import Main.internals.settings_handlers.backup_handlers
import Main.internals.settings_handlers.custom_alert_handlers
import Main.internals.session_handlers

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

# ====================== STATS HELPERS ======================

async def get_settings_home_text():
    """
    Generates the standardized settings home/dashboard text with detailed stats (v1.5.5.9b style).
    """
    total_sessions = len(Altruix.clients)
    
    # Bots Calculation
    custom_bots_count = len(Altruix.bot_manager.custom_bots) if hasattr(Altruix, 'bot_manager') else 0
    total_bots = 1 + custom_bots_count # Default Bot + Custom Bots
    
    # Module Breakdown
    ub_mod = len([x for x in Altruix.plugin_categories.values() if x == 'userbot'])
    bot_mod = len([x for x in Altruix.plugin_categories.values() if x == 'bot'])
    xtra_mod = len([x for x in Altruix.plugin_categories.values() if x == 'other'])
    # Count Addons Mod (plugins/addons/*.py)
    addons_mod = len(glob.glob("Main/plugins/addons/**/*.py", recursive=True))
    total_mod = ub_mod + bot_mod + xtra_mod + addons_mod
    
    # Commands Count
    total_cmds = sum(len(cmds) for cmds in Altruix.cmd_list.values())
    
    # Xtra-Features (Core set of 18 management functions)
    xtra_features_count = 18
    
    # Localization support if available
    template = Altruix.get_string("settings_stats")
    if not template or template == "settings_stats":
        # Fallback to hardcoded template if string missing
        template = (
            "<b>🛠️ Userbot Settings</b>\n\n"
            "• Total Sessions: <code>{}</code>\n"
            "• Total Bots: <code>{}</code> (Default: 1, Custom: {})\n"
            "• Xtra-Module: <code>{}</code>\n"
            "• Modules: <code>{}</code> (UB {}, Bot {}, Xtra {}, Addons {})\n"
            "• Commands: <code>{}</code>\n"
            "• Version: <code>{}</code>"
        )
        return template.format(
            total_sessions, total_bots, custom_bots_count, xtra_features_count,
            total_mod, ub_mod, bot_mod, xtra_mod, addons_mod, total_cmds, Altruix.__version__
        ) + "\n\nSelect a category below to configure your userbot."

    return template.format(
        total_sessions, total_bots, custom_bots_count, xtra_features_count,
        total_mod, ub_mod, bot_mod, xtra_mod, addons_mod, total_cmds, Altruix.__version__
    ) + "\n\nSelect a category below to configure your userbot."

def get_settings_buttons(user_id=None):
    custom_data = get_user_custom_link(user_id) if user_id else get_custom_link_data()["global"]
    return [
        [
            InlineKeyboardButton("📱 Sessions", callback_data="sessions_list_1", style=enums.ButtonStyle.PRIMARY),
            InlineKeyboardButton("🤖 Bot Controls", callback_data="bot_controls_menu", style=enums.ButtonStyle.PRIMARY),
        ],
        [
            InlineKeyboardButton("⚙️ Configs", callback_data="configs_home", style=enums.ButtonStyle.PRIMARY),
            InlineKeyboardButton("⌨️ Cmd Settings", callback_data="cmd_settings_menu", style=enums.ButtonStyle.PRIMARY),
        ],
        [
            InlineKeyboardButton("❇️ Help Menu", callback_data="re_open", style=enums.ButtonStyle.DANGER),
            InlineKeyboardButton(custom_data.get("text", "Repo"), url=custom_data.get("link", "https://t.me/AlphaXProject"), style=enums.ButtonStyle.DANGER),
        ],
    ]

# ====================== CORE SETTINGS HANDLERS ======================

@Altruix.bot.on_message(filters.command("settings", "/") & Altruix.is_sudo_filter)
@iuser_check
@log_errors
async def settings_command_handler(c: Client, m: Message):
    """Entry point for /settings command with full statistics."""
    text = await get_settings_home_text()
    await m.reply_msg(text, reply_markup=InlineKeyboardMarkup(get_settings_buttons(m.from_user.id)), quote=True)

@Altruix.bot.on_inline_query(filters.regex(r"^settings(?:\s|$)"))
@iuser_check
@log_errors
async def settings_inline_handler(c: Client, iq: InlineQuery):
    """Inline entry point for settings with full statistics."""
    # ✅ AUTHORIZATION CHECK (Supports DB Users)
    if not await Altruix.is_sudo(iq.from_user.id):
        return
    
    # Extract metadata if present
    query = iq.query
    chat_id = "N/A"
    chat_title = "N/A"
    
    if "cid=" in query:
        if m := re.search(r"cid=(-?\d+)", query):
            chat_id = m.group(1)
            
    if "ctit=" in query:
        import base64
        try:
            if m := re.search(r"ctit=([^&\s]+)", query):
                chat_title = base64.b64decode(m.group(1)).decode('utf-8')
        except: pass

    text = await get_settings_home_text()
    result_identity = f"settings_{chat_id if chat_id != 'N/A' else 'Inline'}"
    
    await iq.answer(
        results=[
            InlineQueryResultArticle(
                id=result_identity,
                title="Userbot Settings",
                description=f"Manage dashboard for {chat_title if chat_title != 'N/A' else 'General'}",
                input_message_content=InputTextMessageContent(text, parse_mode=ParseMode.HTML),
                reply_markup=InlineKeyboardMarkup(get_settings_buttons(iq.from_user.id))
            )
        ],
        cache_time=0, is_personal=True
    )

@Altruix.bot.on_chosen_inline_result(filters.regex(r"^settings(?:\s|$)", flags=re.IGNORECASE))
@iuser_check
@log_errors
async def settings_chosen_handler(c: Client, cir: ChosenInlineResult):
    """Capture inline metadata for general settings dashboard."""
    inline_msg_id = cir.inline_message_id
    if not inline_msg_id: return
    
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[SETTINGS CHOSEN] inline_msg_id: {inline_msg_id} | query: {cir.query} | result_id: {cir.result_id}")
    
    try:
        # Extract chat_id from the result_id we assigned (e.g. settings_-100123)
        chat_id = "N/A"
        if cir.result_id and cir.result_id.startswith("settings_"):
            chat_id = cir.result_id.replace("settings_", "")

        await Altruix.local_db.inline_col.find_one_and_update(
            {"_id": inline_msg_id},
            {"$set": {
                "_id": inline_msg_id,
                "chat_id": chat_id,
                "timestamp": datetime.now().timestamp()
            }},
            upsert=True
        )
        logger.info(f"[SETTINGS CACHED] chat_id: {chat_id} mapped to msg_id: {inline_msg_id}")
    except Exception as e:
        logger.error(f"Error in settings_chosen_handler: {e}")

@Altruix.bot.on_callback_query(filters.regex(r"^settings_menu$"))
@iuser_check
@log_errors
async def settings_menu_cb_handler(c: Client, cb: CallbackQuery):
    """Main settings menu return point with consistent full statistics."""
    await cb.answer()
    text = await get_settings_home_text()
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(get_settings_buttons(cb.from_user.id)))

@Altruix.bot.on_callback_query(filters.regex(r"^configs_home$"))
@iuser_check
@log_errors
async def configs_menu_cb_handler(c: Client, cb: CallbackQuery):
    await cb.answer()
    text = "<b>⚙️ Configuration Manager</b>\n\nManage environment variables and bot configs."
    buttons = [
        [InlineKeyboardButton("🔧 ENV Manager", callback_data="env_manager_list_1")],
        [InlineKeyboardButton("📦 Database Manager", callback_data="backup_manager")],
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
