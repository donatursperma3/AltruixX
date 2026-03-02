# Main/internals/settings_handlers/logger_handlers.py
import html
import os
import json
import asyncio
import logging
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton, LinkPreviewOptions
from Main.core.decorators import log_errors, iuser_check
from Main.core.client import Altruix
from Main.utils.file_helpers import get_db_path
from pyrogram.enums import ParseMode
from pyrogram.errors import UserAlreadyParticipant, FloodWait

# States & Helpers
from .utils import edit_cb
# from .session_info import sessions_info_cb_handler

# Logger
logger = logging.getLogger(__name__)

from Main.utils.file_helpers import get_user_button_style
from .custom_alert_handlers import _get_session_user_id

@Altruix.bot.on_callback_query(filters.regex(r"^(pml|mnt|joinl|cmdl)_menu_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def logger_menu_handler(c: Client, cb: CallbackQuery):
    """General logger status menu with filter buttons if applicable."""
    log_type, index, page = cb.matches[0].group(1), int(cb.matches[0].group(2)), int(cb.matches[0].group(3))
    await cb.answer()
    
    # Resolve user_style
    user_id_key = _get_session_user_id(index)
    user_style = get_user_button_style(user_id_key)
    
    type_map = {"pml": "PM Logger", "mnt": "Mention Logger", "joinl": "Join Logger", "cmdl": "Command Logger"}
    base_key = log_type.upper()
    
    # 1. APPLY TYPE
    apply_type = await Altruix.config.get_env(f"{base_key}_LOGGER_APPLY_TYPE_{index}") or "global"
    apply_label = "Global" if apply_type == "global" else "Per-Account"
    
    # 2. STATUS
    if apply_type == "global":
        current = await Altruix.config.get_env(f"{base_key}_LOGGER_GLOBAL") or "off"
    else:
        current = await Altruix.config.get_env(f"{base_key}_LOGGER_{index}") or "off"
    status_emoji = "✅ ON" if current == "on" else "❌ OFF"
    
    # 3. REPLY BY (Only for PML and MNT)
    reply_by_txt = ""
    reply_buttons = []
    if log_type in ["pml", "mnt"]:
        if apply_type == "global":
            reply_by = await Altruix.config.get_env(f"{base_key}_REPLY_BY_GLOBAL") or "all"
        else:
            reply_by = await Altruix.config.get_env(f"{base_key}_REPLY_BY_{index}") or "all"
        
        reply_by_txt = f"• 🗣️ <b>Reply By:</b> <code>{reply_by.upper()}</code>\n"
        reply_buttons = [InlineKeyboardButton(await Essentials().get_user_button_style(user_id_key, f"🗣️ Reply: {reply_by.upper()}"), f"{log_type}_reply_{index}_{page}")]

    buttons = [
        [InlineKeyboardButton(await Essentials().get_user_button_style(user_id_key, f"Toggle {type_map[log_type]}: {status_emoji}"), f"{log_type}_toggle_{index}_{page}")],
    ]
    
    # Mode & Reply Buttons
    config_row = [InlineKeyboardButton(await Essentials().get_user_button_style(user_id_key, f"⚙️ Type: {apply_label}"), f"{log_type}_mode_{index}_{page}")]
    if reply_buttons:
        config_row.extend(reply_buttons)
    buttons.append(config_row)
    
    # Add advanced filter buttons for PM Logger and Mention Logger
    if log_type == "pml":
        buttons.append([InlineKeyboardButton(await Essentials().get_user_button_style(user_id_key, "🔍 PM Logger Filters"), f"pmlf_menu_user_{index}_{page}")])
    elif log_type == "mnt":
        buttons.append([
            InlineKeyboardButton(await Essentials().get_user_button_style(user_id_key, "🔍 Mention Filters"), f"mntf_menu_{index}_{page}"),
            InlineKeyboardButton(await Essentials().get_user_button_style(user_id_key, "🔔 View Mentions"), f"view_mentions_menu_{index}_{page}")
        ])
        
        c_id = index
        buttons.append([InlineKeyboardButton(await Essentials().get_user_button_style(user_id_key, "🚫 Haters Detector Dashboard"), f"haters_menu_{c_id}")])
    
    # Add Bot Assist toggle for PML and MNT
    if log_type in ["pml", "mnt"]:
        bot_assist_enabled = False
        storage_file = get_db_path("pm_logger_bot_settings.json" if log_type == "pml" else "mentions_settings.json")
        if os.path.exists(storage_file):
            with open(storage_file, "r") as f:
                try:
                    b_data = json.load(f)
                    if log_type == "pml":
                        bot_assist_enabled = b_data.get("settings", {}).get("log_mode", "off") != "off"
                    else:
                        bot_assist_enabled = b_data.get("settings", {}).get("enabled", False)
                except: pass
        
        bot_assist_btn = "ON" if bot_assist_enabled else "OFF"
        buttons.append([InlineKeyboardButton(await Essentials().get_user_button_style(user_id_key, f"🤖 Bot Assist: {bot_assist_btn}"), f"{log_type}_botassist_{index}_{page}")])
        
    buttons.append([InlineKeyboardButton(await Essentials().get_user_button_style(user_id_key, "🔙 Back"), callback_data=f"session_info_{index}_{page}_3")]) # Fixed page return to 3 (Logs Page)
    
    await edit_cb(
        cb,
        f"<b>📊 {type_map[log_type]} Control</b>\n\n"
        f"• 🔌 <b>Status:</b> {status_emoji}\n"
        f"• ⚙️ <b>Apply Type:</b> <code>{apply_label}</code>\n"
        f"{reply_by_txt}\n"
        f"<i>Gunakan tombol di bawah untuk mengubah pengaturan.</i>",
        reply_markup=InlineKeyboardMarkup(buttons), 
        parse_mode=ParseMode.HTML
    )

@Altruix.bot.on_callback_query(filters.regex(r"^(pml|mnt|joinl|cmdl)_toggle_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def logger_toggle_handler(c: Client, cb: CallbackQuery):
    """Toggle logger status (on/off) respecting apply type"""
    log_type, index, page = cb.matches[0].group(1), int(cb.matches[0].group(2)), int(cb.matches[0].group(3))
    base_key = log_type.upper()
    
    apply_type = await Altruix.config.get_env(f"{base_key}_LOGGER_APPLY_TYPE_{index}") or "global"
    
    if apply_type == "global":
        key = f"{base_key}_LOGGER_GLOBAL"
    else:
        key = f"{base_key}_LOGGER_{index}"
        
    current = await Altruix.config.get_env(key) or "off"
    new_val = "off" if current == "on" else "on"
    
    await Altruix.config.sync_env_to_db(key, new_val, upsert=True)
    setattr(Altruix.config, key, new_val) 
    
    # ✅ SYNC TO JSON (For Userbot Loggers)
    if log_type in ["pml", "mnt", "cmdl"]:
        if log_type == "pml":
            filename = get_db_path('pm_logger_user_settings.json')
        elif log_type == "mnt":
            filename = get_db_path('mentions_settings.json')
        else:
            filename = get_db_path('cmd_logger_settings.json')

        if os.path.exists(filename):
            try:
                with open(filename, "r") as f: data = json.load(f)
                
                # PM Logger Sync
                if log_type == "pml":
                    sessions = data.get("settings", {}) or data.get("sessions", {})
                    # If global mode, sync root 'enabled'
                    if apply_type == "global":
                        data["enabled"] = (new_val == "on")
                        if "global_config" not in data: data["global_config"] = {}
                        data["global_config"]["enabled"] = (new_val == "on")
                    else:
                        me_id_str = str(Altruix.clients[index].me.id)
                        if me_id_str not in sessions: sessions[me_id_str] = {}
                        sessions[me_id_str]["enabled"] = (new_val == "on")
                        data["settings"] = sessions # Ensure back-sync
                
                # Mention Logger Sync
                elif log_type == "mnt": 
                    me_id_str = str(Altruix.clients[index].me.id)
                    if apply_type == "global":
                        if "global" not in data: data["global"] = {}
                        data["global"]["mention"] = (new_val == "on")
                    else:
                        if "settings" not in data: data["settings"] = {}
                        if me_id_str not in data["settings"]: data["settings"][me_id_str] = {}
                        # If it was a bool, convert to dict
                        if not isinstance(data["settings"][me_id_str], dict):
                             data["settings"][me_id_str] = {"mention": data["settings"][me_id_str]}
                        data["settings"][me_id_str]["mention"] = (new_val == "on")
                
                # Command Logger Sync
                elif log_type == "cmdl":
                    me_id_str = str(Altruix.clients[index].me.id)
                    if apply_type == "global":
                        if "global" not in data: data["global"] = {}
                        data["global"]["enabled"] = (new_val == "on")
                        data["enabled"] = (new_val == "on") # Legacy
                    else:
                        if "sessions" not in data: data["sessions"] = {}
                        if me_id_str not in data["sessions"]: data["sessions"][me_id_str] = {}
                        data["sessions"][me_id_str]["enabled"] = (new_val == "on")

                with open(filename, "w") as f: json.dump(data, f, indent=2)
            except Exception as e:
                logger.error(f"Failed to sync {log_type} toggle to JSON: {e}")

    await cb.answer(f"{log_type.upper()} Logger: {new_val.upper()}")
    await logger_menu_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^(pml|mnt|joinl|cmdl)_mode_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def logger_mode_handler(c: Client, cb: CallbackQuery):
    """Toggle Apply Type (Per-Account <-> Global)"""
    log_type, index, page = cb.matches[0].group(1), int(cb.matches[0].group(2)), int(cb.matches[0].group(3))
    base_key = log_type.upper()
    key = f"{base_key}_LOGGER_APPLY_TYPE_{index}"
    
    current = await Altruix.config.get_env(key) or "global"
    new_val = "global" if current == "per_account" else "per_account"
    
    await Altruix.config.sync_env_to_db(key, new_val, upsert=True)
    
    # ✅ SYNC APPLY TYPE TO JSON
    if log_type in ["pml", "mnt", "cmdl"]:
        if log_type == "pml":
            filename = get_db_path('pm_logger_user_settings.json')
        elif log_type == "mnt":
            filename = get_db_path('mentions_settings.json')
        else:
            filename = get_db_path('cmd_logger_settings.json')

        if os.path.exists(filename):
            try:
                with open(filename, "r") as f: data = json.load(f)
                if "apply_types" not in data: data["apply_types"] = {}
                me_id_str = str(Altruix.clients[index].me.id)
                data["apply_types"][me_id_str] = new_val
                with open(filename, "w") as f: json.dump(data, f, indent=2)
            except Exception as e:
                logger.error(f"Failed to sync {log_type} mode to JSON: {e}")

    await cb.answer(f"Apply Type: {new_val.upper()}")
    await logger_menu_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^(pml|mnt)_reply_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def logger_reply_handler(c: Client, cb: CallbackQuery):
    """Cycle Reply By modes: All -> Sudo -> User -> Owner"""
    log_type, index, page = cb.matches[0].group(1), int(cb.matches[0].group(2)), int(cb.matches[0].group(3))
    base_key = log_type.upper()
    
    apply_type = await Altruix.config.get_env(f"{base_key}_LOGGER_APPLY_TYPE_{index}") or "per_account"
    
    if apply_type == "global":
        key = f"{base_key}_REPLY_BY_GLOBAL"
    else:
        key = f"{base_key}_REPLY_BY_{index}"
        
    modes = ["all", "sudo", "user", "owner"]
    current = await Altruix.config.get_env(key) or "all"
    
    try:
        current_idx = modes.index(current)
        next_idx = (current_idx + 1) % len(modes)
        new_val = modes[next_idx]
    except ValueError:
        new_val = "all"
        
    await Altruix.config.sync_env_to_db(key, new_val, upsert=True)
    
    # ✅ SYNC REPLY MODE TO JSON
    if log_type in ["pml", "mnt"]:
        filename = get_db_path('pm_logger_user_settings.json' if log_type == 'pml' else 'mentions_settings.json')
        if os.path.exists(filename):
            try:
                with open(filename, "r") as f: data = json.load(f)
                # Both use 'reply_access_mode' key in root or settings
                data["reply_access_mode"] = new_val
                with open(filename, "w") as f: json.dump(data, f, indent=2)
            except Exception as e:
                logger.error(f"Failed to sync {log_type} reply mode to JSON: {e}")

    await cb.answer(f"Reply By: {new_val.upper()}")
    await logger_menu_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^(pml|mnt)_botassist_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def logger_botassist_handler(c: Client, cb: CallbackQuery):
    """Toggle Bot Assist globally from session menu"""
    log_type, index, page = cb.matches[0].group(1), int(cb.matches[0].group(2)), int(cb.matches[0].group(3))
    
    if log_type == "pml":
        bot_assist_enabled = False
        if os.path.exists(get_db_path("pm_logger_bot_settings.json")):
            with open(get_db_path("pm_logger_bot_settings.json"), "r") as f:
                b_data = json.load(f)
                bot_assist_enabled = b_data.get("settings", {}).get("log_mode", "off") != "off"
        
        new_val = "off" if bot_assist_enabled else "all"
        storage_path = get_db_path("pm_logger_bot_settings.json")
        if not os.path.exists(storage_path):
            data = {"settings": {"log_mode": new_val}}
        else:
            with open(storage_path, "r") as f: data = json.load(f)
            if "settings" not in data: data["settings"] = {}
            data["settings"]["log_mode"] = new_val
            
        with open(storage_path, "w") as f: json.dump(data, f, indent=2)
        status = "DISABLED" if new_val == "off" else "ENABLED"
    else:
        # mnt
        bot_assist_enabled = False
        storage_path = get_db_path("mentions_settings.json")
        if os.path.exists(storage_path):
            with open(storage_path, "r") as f:
                b_data = json.load(f)
                bot_assist_enabled = b_data.get("settings", {}).get("enabled", False)
        
        new_val = not bot_assist_enabled
        with open(storage_path, "r") as f: data = json.load(f)
        if "settings" not in data: data["settings"] = {}
        data["settings"]["enabled"] = new_val
        with open(storage_path, "w") as f: json.dump(data, f, indent=2)
        status = "ENABLED" if new_val else "DISABLED"
        
    await cb.answer(f"🤖 Bot Assist: {status}")
    await logger_menu_handler(c, cb)

# --- PM Logger Advanced Filters ---

@Altruix.bot.on_callback_query(filters.regex(r"^pmlf_menu_(user|bot)_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def pmlf_menu_handler(c: Client, cb: CallbackQuery):
    """PM Logger Filters Category Selection"""
    logger_type = cb.matches[0].group(1) # 'user' or 'bot'
    index = int(cb.matches[0].group(2))
    page = int(cb.matches[0].group(3))
    await cb.answer()
    
    # Resolve user_style
    user_id_key = _get_session_user_id(index)
    user_style = get_user_button_style(user_id_key)
    
    text = (
        f"<b>🔍 PM Logger Filters ({'Userbot Session'})</b>\n\n"
        "Pilih kategori di bawah untuk mengatur jenis pesan yang akan dicatat:\n\n"
        "👤 <b>User Filters:</b> Filter pesan dari pengguna (Text, Photo, Video, dll).\n"
        "🤖 <b>Bot Filters:</b> Filter pesan dari Bot (Menjaga kebersihan log group)."
    )
    buttons = [
        [
            InlineKeyboardButton(await Essentials().get_user_button_style(user_id_key, "👤 From User"), f"pmlfl_user_user_{index}_{page}"),
            InlineKeyboardButton(await Essentials().get_user_button_style(user_id_key, "🤖 From Bot"), f"pmlfl_user_bot_{index}_{page}"),
        ],
        [InlineKeyboardButton(await Essentials().get_user_button_style(user_id_key, "🔙 Back to PM Logger"), f"pml_menu_{index}_{page}")]
    ]
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

async def show_pmlf_list(c: Client, cb: CallbackQuery, logger_type: str, source: str, index: int, page: int):
    """
    Helper function to generate and display the message type filter list for PM Logger.
    Avoids ValueError by centralizing parameter handling.
    """
    filename = get_db_path("pm_logger_user_settings.json")
    user_id_str = str(Altruix.clients[index].me.id)
    source_key = f"from_{source}"
    
    filters_data = {}
    if os.path.exists(filename):
        with open(filename, "r") as f: 
            data = json.load(f)
        sessions = data.get("sessions", {}) or data.get("settings", {})
        session_data = sessions.get(user_id_str, {})
        if isinstance(session_data, dict):
            filters_data = session_data.get("filters", {}).get(source_key, {})
    
    text = f"<b>🔍 {source.capitalize()} Filter (Session {index+1})</b>\n\nKlik untuk toggle (✅ = Log, ❌ = Ignore):"
    buttons = []
    row = []
    m_types = [
        "text", "photo", "video", "document", "audio", "voice", "sticker", "animation", 
        "video_note", "contact", "location", "venue", "game", "poll", "dice"
    ]
    # Mapping for localized keys
    type_map = {
        "text": "GP_BTN_TXT", "photo": "GP_BTN_IMG", "video": "GP_BTN_VID",
        "document": "GP_BTN_DOC", "audio": "GP_BTN_AUD", "voice": "GP_BTN_VN",
        "sticker": "GP_BTN_STK", "animation": "GP_BTN_GIF", "video_note": "GP_BTN_VNOTE",
        "contact": "GP_BTN_CONT", "location": "GP_BTN_LOC", "venue": "GP_BTN_VEN",
        "game": "GP_BTN_GAME", "poll": "GP_BTN_POLL", "dice": "GP_BTN_DICE"
    }

    # Resolve user_style
    from Main.utils.file_helpers import get_user_button_style
    user_id_key = str(Altruix.clients[index].me.id)
    user_style = get_user_button_style(int(user_id_key))

    for m_type in m_types:
        # Defaults: log everything except bot text (to avoid spam)
        default_val = False if (source == "bot" and m_type == "text") else True
        val = filters_data.get(m_type, default_val)
        status = "✅" if val else "❌"
        
        lbl_key = type_map.get(m_type)
        lbl = Altruix.get_string(lbl_key) or m_type.capitalize()
        
        row.append(InlineKeyboardButton(f"{status} {lbl}", f"pmlft_{logger_type}_{source}_{m_type}_{index}_{page}", style=user_style))
        if len(row) == 2:
            buttons.append(row)
            row = []
    
    if row: 
        buttons.append(row)
        
    buttons.append([InlineKeyboardButton(await Essentials().get_user_button_style(int(user_id_key), "🔙 Back"), f"pmlf_menu_{logger_type}_{index}_{page}")])
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlfl_(user|bot)_(user|bot)_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def pmlf_list_handler(c: Client, cb: CallbackQuery):
    """Handler for displaying the specific message type filters list."""
    logger_type = cb.matches[0].group(1)
    source = cb.matches[0].group(2)
    index = int(cb.matches[0].group(3))
    page = int(cb.matches[0].group(4))
    await cb.answer()
    await show_pmlf_list(c, cb, logger_type, source, index, page)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlft_(user|bot)_(user|bot)_(.+)_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def pmlf_toggle_handler(c: Client, cb: CallbackQuery):
    """Toggle a specific filter in PM Logger"""
    logger_type, source, m_type, index, page = cb.matches[0].groups()
    index, page = int(index), int(page)
    user_id_str = str(Altruix.clients[index].me.id)
    source_key = f"from_{source}"
    filename = get_db_path("pm_logger_user_settings.json")
    
    data = {"sessions": {}}
    if os.path.exists(filename):
        with open(filename, "r") as f: data = json.load(f)
    
    if "sessions" not in data: data["sessions"] = data.pop("settings", {})
    if user_id_str not in data["sessions"]: data["sessions"][user_id_str] = {"filters": {}}
    if "filters" not in data["sessions"][user_id_str]: data["sessions"][user_id_str]["filters"] = {}
    if source_key not in data["sessions"][user_id_str]["filters"]:
        # Fallback to empty dict if defaults import fails
        data["sessions"][user_id_str]["filters"][source_key] = {}
        
    current = data["sessions"][user_id_str]["filters"][source_key].get(m_type, True)
    data["sessions"][user_id_str]["filters"][source_key][m_type] = not current
    
    with open(filename, "w") as f: 
        json.dump(data, f, indent=2)
        
    await cb.answer(f"{m_type.capitalize()} {source}: {'ON' if not current else 'OFF'}")
    # Refresh menu using helper to avoid regex/indexing errors
    await show_pmlf_list(c, cb, logger_type, source, index, page)

# --- Mention Logger Advanced Filters ---

@Altruix.bot.on_callback_query(filters.regex(r"^mntf_menu_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def mntf_menu_handler(c: Client, cb: CallbackQuery):
    """Mention Logger Filters Category Selection"""
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    await cb.answer()
    
    # Resolve user_style
    user_id_key = _get_session_user_id(index)
    user_style = get_user_button_style(user_id_key)
    
    text = (
        f"<b>🔍 Mention Logger Filters (Sesi {index+1})</b>\n\n"
        "Pilih kategori di bawah untuk mengatur jenis pesan yang akan dicatat:\n\n"
        "👤 <b>User Filters:</b> Filter mention dari pengguna biasa.\n"
        "🤖 <b>Bot Filters:</b> Filter mention dari Bot/Robot."
    )
    buttons = [
        [
            InlineKeyboardButton(await Essentials().get_user_button_style(user_id_key, "👤 From User"), f"mntfl_user_{index}_{page}"),
            InlineKeyboardButton(await Essentials().get_user_button_style(user_id_key, "🤖 From Bot"), f"mntfl_bot_{index}_{page}"),
        ],
        [InlineKeyboardButton(await Essentials().get_user_button_style(user_id_key, "🔙 Back to Mention Logger"), f"mnt_menu_{index}_{page}")]
    ]
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

async def show_mntf_list(c: Client, cb: CallbackQuery, source: str, index: int, page: int):
    """Helper to show mention filter list for a specific source (user/bot)"""
    filename = get_db_path("mentions_settings.json")
    user_id_str = str(Altruix.clients[index].me.id)
    source_key = f"from_{source}"
    
    filters_data = {}
    if os.path.exists(filename):
        with open(filename, "r") as f: data = json.load(f)
        sessions = data.get("settings", {})
        session_data = sessions.get(user_id_str, {})
        filters_data = session_data.get("filters", {}).get(source_key, {})
    
    text = f"<b>🔍 Mention {source.capitalize()} Filter (Sesi {index+1})</b>\n\nKlik untuk toggle (✅ = Log, ❌ = Ignore):"
    buttons = []
    row = []
    m_types = [
        "text", "photo", "video", "document", "audio", "voice", "sticker", "animation", 
        "video_note", "contact", "location", "venue", "game", "poll", "dice"
    ]
    # Mapping for localized keys
    type_map = {
        "text": "GP_BTN_TXT", "photo": "GP_BTN_IMG", "video": "GP_BTN_VID",
        "document": "GP_BTN_DOC", "audio": "GP_BTN_AUD", "voice": "GP_BTN_VN",
        "sticker": "GP_BTN_STK", "animation": "GP_BTN_GIF", "video_note": "GP_BTN_VNOTE",
        "contact": "GP_BTN_CONT", "location": "GP_BTN_LOC", "venue": "GP_BTN_VEN",
        "game": "GP_BTN_GAME", "poll": "GP_BTN_POLL", "dice": "GP_BTN_DICE"
    }

    # Resolve user_style
    user_id_key = str(Altruix.clients[index].me.id)
    user_style = get_user_button_style(int(user_id_key))

    for m_type in m_types:
        # Default: log everything
        val = filters_data.get(m_type, True)
        status = "✅" if val else "❌"
        
        lbl_key = type_map.get(m_type)
        lbl = Altruix.get_string(lbl_key) or m_type.capitalize()
        
        row.append(InlineKeyboardButton(f"{status} {lbl}", f"mntft_{source}_{m_type}_{index}_{page}", style=user_style))
        if len(row) == 2:
            buttons.append(row); row = []
    if row: buttons.append(row)
    
    buttons.append([InlineKeyboardButton("🔙 Back", f"mntf_menu_{index}_{page}", style=user_style)])
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^mntfl_(user|bot)_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def mntfl_list_handler(c: Client, cb: CallbackQuery):
    """Handler for displaying the specific message type filters list for Mentions."""
    source, index, page = cb.matches[0].groups()
    await cb.answer()
    await show_mntf_list(c, cb, source, int(index), int(page))

@Altruix.bot.on_callback_query(filters.regex(r"^mntft_(user|bot)_(.+)_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def mntf_toggle_handler(c: Client, cb: CallbackQuery):
    """Toggle a specific filter in Mention Logger"""
    source, m_type, index, page = cb.matches[0].groups()
    index, page = int(index), int(page)
    user_id_str = str(Altruix.clients[index].me.id)
    source_key = f"from_{source}"
    filename = get_db_path("mentions_settings.json")
    
    data = {"settings": {}, "global": {}}
    if os.path.exists(filename):
        with open(filename, "r") as f: data = json.load(f)
    
    if "settings" not in data: data["settings"] = {}
    if user_id_str not in data["settings"]: data["settings"][user_id_str] = {}
    if "filters" not in data["settings"][user_id_str]: data["settings"][user_id_str]["filters"] = {}
    if source_key not in data["settings"][user_id_str]["filters"]:
        data["settings"][user_id_str]["filters"][source_key] = {}
        
    current = data["settings"][user_id_str]["filters"][source_key].get(m_type, True)
    data["settings"][user_id_str]["filters"][source_key][m_type] = not current
    
    with open(filename, "w") as f: json.dump(data, f, indent=2)
    await cb.answer(f"MNT {source} {m_type.capitalize()} toggled")
    await show_mntf_list(c, cb, source, index, page)

# --- Join Log Group ---

@Altruix.bot.on_callback_query(filters.regex("join_log_group_(\\d+)(?:_(\\d+))?$"))
@iuser_check
@log_errors
async def join_log_group_handler(c: Client, cb: CallbackQuery):
    """Invite session to log group and join"""
    index = int(cb.matches[0].group(1))
    # page = int(cb.matches[0].group(2)) if cb.matches[0].group(2) else 1 # Not strictly needed for logic but good for completeness if we add back button here
    await cb.answer("🔄 Processing join...", show_alert=False)
    
    if index >= len(Altruix.clients): return
    session_client = Altruix.clients[index]
    log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_USERS_ID))
    
    try:
        chat = await Altruix.bot.get_chat(log_chat_id)
        link = chat.invite_link
        if not link:
            invite = await Altruix.bot.create_chat_invite_link(log_chat_id, member_limit=1)
            link = invite.invite_link
            
        await session_client.join_chat(link)
        await cb.answer("✅ Successfully joined Log Group!", show_alert=True)
    except UserAlreadyParticipant:
        await cb.answer("ℹ️ Already in Log Group.", show_alert=True)
    except Exception as e:
        await cb.answer(f"❌ Join failed: {str(e)}", show_alert=True)

# --- Global Logger Menus (Bot Controls) ---

@Altruix.bot.on_callback_query(filters.regex(r"^(pmlb|mntlb|joinl|cbl)_menu$"))
@iuser_check
@log_errors
async def global_logger_menu_handler(c: Client, cb: CallbackQuery):
    """Global control menu for loggers from Bot Controls."""
    log_type = cb.matches[0].group(1).replace("lb", "").replace("l", "")
    await cb.answer()
    
    type_map = {"pm": "PM Logger", "mnt": "Mention Logger", "join": "Join Logger", "cb": "Callback Logger"}
    base_key = log_type.upper()
    
    key = f"{base_key}_LOGGER_GLOBAL"
    current = await Altruix.config.get_env(key) or "off"
    
    # Resolve user_style (Global menu uses OWNER style)
    user_style = get_user_button_style(Altruix.config.OWNER_ID)
    
    # Special handling for Callback Logger (cb)
    if log_type == "cb":
        # Map old "on" to "all" for compatibility
        if current == "on": current = "all"
        
        status_text = {
            "all": "✅ ALL Users",
            "sudo": "🛡️ SUDO Only",
            "nonsudo": "👤 NON-SUDO Only",
            "off": "❌ OFF"
        }.get(current, "❌ OFF")
        
        buttons = [
            [
                InlineKeyboardButton(await Essentials().get_user_button_style(Altruix.config.OWNER_ID, f"{'✅ ' if current == 'all' else ''}All"), "global_cb_filter_all"),
                InlineKeyboardButton(await Essentials().get_user_button_style(Altruix.config.OWNER_ID, f"{'✅ ' if current == 'off' else ''}Off"), "global_cb_filter_off")
            ],
            [
                InlineKeyboardButton(await Essentials().get_user_button_style(Altruix.config.OWNER_ID, f"{'✅ ' if current == 'sudo' else ''}Sudo"), "global_cb_filter_sudo"),
                InlineKeyboardButton(await Essentials().get_user_button_style(Altruix.config.OWNER_ID, f"{'✅ ' if current == 'nonsudo' else ''}Non-Sudo"), "global_cb_filter_nonsudo")
            ],
            [InlineKeyboardButton(await Essentials().get_user_button_style(Altruix.config.OWNER_ID, "🔙 Back"), "bot_controls_menu")]
        ]
        
        await edit_cb(cb, 
            f"<b>📊 Global {type_map[log_type]} Control</b>\n\n"
            f"• 🔌 <b>Status Saat Ini:</b> {status_text}\n\n"
            f"💡 <b>Deskripsi:</b>\n"
            f"• <b>All:</b> Catat semua user.\n"
            f"• <b>Sudo:</b> Hanya catat sudo user.\n"
            f"• <b>Non-Sudo:</b> Hanya catat user biasa.\n"
            f"• <b>Off:</b> Matikan logging callback.\n",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )
        return

    status_emoji = "✅ ON" if current == "on" else "❌ OFF"
    
    buttons = [
        [InlineKeyboardButton(await Essentials().get_user_button_style(Altruix.config.OWNER_ID, f"Toggle Global {type_map[log_type]}: {status_emoji}"), f"global_{log_type}_toggle")],
        [InlineKeyboardButton(await Essentials().get_user_button_style(Altruix.config.OWNER_ID, "🔙 Back"), "bot_controls_menu")]
    ]
    
    await edit_cb(cb, 
        f"<b>📊 Global {type_map[log_type]} Control</b>\n\n"
        f"• 🔌 <b>Global Status:</b> {status_emoji}\n\n"
        f"<i>Aksi ini akan mempengaruhi semua sesi yang menggunakan mode Global.</i>",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )

@Altruix.bot.on_callback_query(filters.regex(r"^global_(pm|mnt|join|cb)_toggle$"))
@iuser_check
@log_errors
async def global_logger_toggle_handler(c: Client, cb: CallbackQuery):
    """Toggle global status for loggers."""
    log_type = cb.matches[0].group(1)
    key = f"{log_type.upper()}_LOGGER_GLOBAL"
    
    current = await Altruix.config.get_env(key) or "off"
    new_val = "off" if current == "on" else "on"
    
    await Altruix.config.sync_env_to_db(key, new_val, upsert=True)
    setattr(Altruix.config, key, new_val)
    
    await cb.answer(f"Global {log_type.upper()} Logger: {new_val.upper()}")
    # Re-use the menu but we need a mock regex match or call it directly with adjustments
    # For simplicity, let's just create a mock with a manual type
    # ✅ FIX: Use *args in lambda to ignore implicit 'self' when called as a method
    cb.matches = [type('Mock', (object,), {'group': lambda *args: f"{log_type}l_menu"})()] 
    await global_logger_menu_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^get_log_group_link$"))
@iuser_check
@log_errors
async def get_log_group_link_handler(c: Client, cb: CallbackQuery):
    """Get or generate log group invite link."""
    await cb.answer("Generating link...")
    log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_USERS_ID))
    
    try:
        chat = await Altruix.bot.get_chat(log_chat_id)
        link = chat.invite_link
        if not link:
            invite = await Altruix.bot.create_chat_invite_link(log_chat_id)
            link = invite.invite_link
            
        user_style = get_user_button_style(Altruix.config.OWNER_ID)
        await edit_cb(cb, 
            f"<b>🔗 Log Group Link</b>\n\n<code>{link}</code>\n\n"
            f"<i>Gunakan link ini untuk memasukkan sesi lain ke Log Group secara manual atau bagikan ke Sudo user.</i>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(await Essentials().get_user_button_style(Altruix.config.OWNER_ID, "🔙 Back"), "bot_controls_menu")]]),
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        await cb.answer(f"❌ Error: {str(e)}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^global_cb_filter_(all|sudo|nonsudo|off)$"))
@iuser_check
@log_errors
async def callback_logger_filter_handler(c: Client, cb: CallbackQuery):
    """Handle filter selection for Callback Logger."""
    new_val = cb.matches[0].group(1)
    key = "CB_LOGGER_GLOBAL"
    
    await Altruix.config.sync_env_to_db(key, new_val, upsert=True)
    setattr(Altruix.config, key, new_val)
    
    await cb.answer(f"Callback Logger Filter: {new_val.upper()}")
    
    # Return to menu to update UI
    # Explicitly calling global_logger_menu_handler with mocked 'cb' match
    # Group 1 match should be "cb" as expected by global_logger_menu_handler regex (pmlb|mntlb|joinl|cbl) -> "cb"
    cb.matches = [type('Mock', (object,), {'group': lambda *args: "cbl"})()]
    await global_logger_menu_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^cb_logger_settings$"))
@iuser_check
@log_errors
async def cb_logger_settings_handler(c: Client, cb: CallbackQuery):
    """Special menu for Callback Logger."""
    # This is a bridge, for now just toggle like others
    # ✅ FIX: Use *args in lambda to ignore implicit 'self'
    cb.matches = [type('Mock', (object,), {'group': lambda *args: "cbl"})()]
    await global_logger_menu_handler(c, cb)
