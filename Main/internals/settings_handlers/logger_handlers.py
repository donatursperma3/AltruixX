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
from pyrogram.enums import ParseMode
from pyrogram.errors import UserAlreadyParticipant, FloodWait

# States & Helpers
# from .session_info import sessions_info_cb_handler

# Logger
logger = logging.getLogger(__name__)

@Altruix.bot.on_callback_query(filters.regex(r"^(pml|mnt|joinl|cmdl)_menu_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def logger_menu_handler(c: Client, cb: CallbackQuery):
    """General logger status menu with filter buttons if applicable."""
    log_type, index, page = cb.matches[0].group(1), int(cb.matches[0].group(2)), int(cb.matches[0].group(3))
    await cb.answer()
    
    type_map = {"pml": "PM Logger", "mnt": "Mention Logger", "joinl": "Join Logger", "cmdl": "Command Logger"}
    key = f"{log_type.upper()}_LOGGER_{index}"
    current = await Altruix.config.get_env(key) or "off"
    status_emoji = "✅ ON" if current == "on" else "❌ OFF"
    
    buttons = [
        [InlineKeyboardButton(f"Toggle {type_map[log_type]}: {status_emoji}", f"{log_type}_toggle_{index}_{page}")],
    ]
    
    # Add advanced filter buttons for PM Logger and Mention Logger
    if log_type == "pml":
        buttons.append([InlineKeyboardButton("🔍 PM Logger Filters", f"pmlf_menu_user_{index}_{page}")])
    elif log_type == "mnt":
        buttons.append([InlineKeyboardButton("🔍 Mention Filters", f"mntf_menu_{index}_{page}")])
        buttons.append([InlineKeyboardButton("🔔 View Mentions", f"view_mentions_menu_{index}_{page}")])
        
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"session_info_{index}_{page}_3")]) # Fixed page return to 3 (Logs Page)
    
    await cb.message.edit(
        f"<b>📊 {type_map[log_type]} Control</b>\n\n"
        f"Status saat ini: {status_emoji}\n\n"
        f"<i>Gunakan tombol di bawah untuk toggle status atau mengatur filter lebih lanjut.</i>",
        reply_markup=InlineKeyboardMarkup(buttons), 
        parse_mode=ParseMode.HTML
    )

@Altruix.bot.on_callback_query(filters.regex(r"^(pml|mnt|joinl|cmdl)_toggle_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def logger_toggle_handler(c: Client, cb: CallbackQuery):
    """Toggle logger status (on/off)"""
    log_type, index, page = cb.matches[0].group(1), int(cb.matches[0].group(2)), int(cb.matches[0].group(3))
    key = f"{log_type.upper()}_LOGGER_{index}"
    current = await Altruix.config.get_env(key) or "off"
    new_val = "off" if current == "on" else "on"
    
    await Altruix.config.sync_env_to_db(key, new_val, upsert=True)
    setattr(Altruix.config, key, new_val)
    await cb.answer(f"{log_type.upper()} Logger: {new_val.upper()}")
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
    
    text = (
        f"<b>🔍 PM Logger Filters ({'Userbot Session'})</b>\n\n"
        "Pilih kategori di bawah untuk mengatur jenis pesan yang akan dicatat:\n\n"
        "👤 <b>User Filters:</b> Filter pesan dari pengguna (Text, Photo, Video, dll).\n"
        "🤖 <b>Bot Filters:</b> Filter pesan dari Bot (Menjaga kebersihan log group)."
    )
    buttons = [
        [
            InlineKeyboardButton("👤 From User", f"pmlfl_user_user_{index}_{page}"),
            InlineKeyboardButton("🤖 From Bot", f"pmlfl_user_bot_{index}_{page}"),
        ],
        [InlineKeyboardButton("🔙 Back to PM Logger", f"pml_menu_{index}_{page}")]
    ]
    await cb.message.edit(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlfl_(user|bot)_(user|bot)_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def pmlf_list_handler(c: Client, cb: CallbackQuery):
    """List of toggles for specific message types in PM Logger"""
    logger_type = cb.matches[0].group(1)
    source = cb.matches[0].group(2)
    index = int(cb.matches[0].group(3))
    page = int(cb.matches[0].group(4))
    await cb.answer()
    
    filename = "pm_logger_user_settings.json"
    user_id_str = str(Altruix.clients[index].me.id)
    source_key = f"from_{source}"
    
    filters_data = {}
    if os.path.exists(filename):
        with open(filename, "r") as f: data = json.load(f)
        sessions = data.get("sessions", {}) or data.get("settings", {})
        session_data = sessions.get(user_id_str, {})
        if isinstance(session_data, dict):
            filters_data = session_data.get("filters", {}).get(source_key, {})
    
    text = f"<b>🔍 {source.capitalize()} Filter ({'Session ' + str(index+1)})</b>\n\nKlik untuk toggle (✅ = Log, ❌ = Ignore):"
    buttons = []
    row = []
    m_types = ["text", "photo", "video", "document", "audio", "voice", "sticker", "animation", "video_note"]
    for m_type in m_types:
        default_val = False if (source == "bot" and m_type == "text") else True
        val = filters_data.get(m_type, default_val)
        status = "✅" if val else "❌"
        row.append(InlineKeyboardButton(f"{status} {m_type.capitalize()}", f"pmlft_{logger_type}_{source}_{m_type}_{index}_{page}"))
        if len(row) == 2:
            buttons.append(row); row = []
    if row: buttons.append(row)
    buttons.append([InlineKeyboardButton("🔙 Back", f"pmlf_menu_{logger_type}_{index}_{page}")])
    await cb.message.edit(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlft_(user|bot)_(user|bot)_(.+)_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def pmlf_toggle_handler(c: Client, cb: CallbackQuery):
    """Toggle a specific filter in PM Logger"""
    logger_type, source, m_type, index, page = cb.matches[0].groups()
    index, page = int(index), int(page)
    user_id_str = str(Altruix.clients[index].me.id)
    source_key = f"from_{source}"
    filename = "pm_logger_user_settings.json"
    
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
    
    with open(filename, "w") as f: json.dump(data, f, indent=2)
    await cb.answer(f"{m_type.capitalize()} {source}: {'ON' if not current else 'OFF'}")
    await pmlf_list_handler(c, cb)

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
    log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))
    
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
