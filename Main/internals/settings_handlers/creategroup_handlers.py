# Main/internals/settings_handlers/creategroup_handlers.py
import os
import html
import asyncio
import logging
import traceback
import time
from typing import Optional, Dict
from pyrogram import Client, filters
from pyrogram.errors import QueryIdInvalid, MessageNotModified
from pyrogram.types import (
    CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton,
    InlineQuery, InlineQueryResultArticle, InputTextMessageContent,
    ChosenInlineResult, LinkPreviewOptions
)
import re
from Main.core.decorators import log_errors, iuser_check, send_log_message
from Main.core.client import Altruix
from pyrogram.enums import ParseMode
from datetime import datetime


from .states import user_creategroup_state

HANDLER_VERSION = "0.3.231" # ✅ ADDED: Persistent Creation Reports, Log Exports, & Account Batching
logger = logging.getLogger("altruix.creategroup.handlers")
logger.setLevel(logging.INFO)

async def safe_cb_answer(cb: CallbackQuery, text: str = None, show_alert: bool = True):
    """Safely answer callback queries when the query may have expired."""
    try:
        if text is None:
            await cb.answer(show_alert=show_alert)
        else:
            await cb.answer(text, show_alert=show_alert)
    except QueryIdInvalid:
        logger.warning("Ignored invalid callback query while answering.")
    except Exception as e:
        logger.debug(f"Ignored callback answer failure: {e}")

async def safe_edit_message_text(cb: CallbackQuery, text: str, reply_markup=None, parse_mode=ParseMode.HTML, **kwargs):
    """Safely edit message text, ignoring MessageNotModified and QueryIdInvalid."""
    try:
        return await cb.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=parse_mode, **kwargs)
    except (MessageNotModified, QueryIdInvalid):
        return True
    except Exception as e:
        logger.warning(f"Ignored safe_edit failure: {e}")
        return False

# Default Configuration
DEFAULT_CREATEGROUP_CONFIG = {
    "delay": 60, "count": 2, "batch_delay": 10, "batch_size": 2, "action_delay": 3.0,
    "account_delay": 0.5, # ✅ NEW: Staggered start delay for multi-account tasks
    "batch_account": 3, "ba_account_delay": 60, # ✅ NEW: Batch account running settings
    "batch_action": 30, "ba_delay": 30,
    "pattern": "🔰 X(tahun) B(bulan)-T(tanggal)", "username": None, "description": "Powered by @AlphaXProject",
    "bots": "@MissRose_bot @simixbot @Spillgame_bot @truthordaresbot @truthordares_bot @truthordarerp_bot @truthordarerln_bot @truthordares18_bot",
    "invite_bots": True, "anon_mode": True, "copy_messages": True, "msg_img": True, "msg_vid": True,
    "msg_img_album": False, "msg_vid_album": False,
    "photo_source": "source", "custom_photo_id": None,
    "log_destination": "both", "group_type": "a",
    "log_format": "zip", "pin_first_msg": True, "temp_pin": True, "quote_block": True,
    "rand_len": 3, "rand_lower": False, "rand_upper": True, "rand_static": True,
    "interrupted_log": "off", "start_log_mode": "both", "start_photo_log_mode": "both",
    "progress_log_mode": "both", "panel_log_mode": "log_group", "delay_log_mode": "both"
}


# ─── Persistent User Config ───
from Main.utils.file_helpers import get_db_path as _get_db_path
import json as _json
_USER_CG_CONFIG_FILE = _get_db_path("xcreategroup_user_configs.json")

CALLBACK_BUSY: Dict[str, float] = {}

async def _callback_debounce(cb: CallbackQuery, interval: float = 0.5) -> bool:
    """Simple debounce guard for interactive CreateGroup callbacks."""
    try:
        if cb.message and getattr(cb.message, 'message_id', None):
            key = f"cb:{cb.message.chat.id}:{cb.message.message_id}"
        else:
            key = f"user:{cb.from_user.id}"
    except Exception:
        try:
            key = f"user:{cb.from_user.id}"
        except Exception:
            key = "global"

    now = time.monotonic()
    busy_until = CALLBACK_BUSY.get(key, 0)
    if now < busy_until:
        return False
    CALLBACK_BUSY[key] = now + float(interval)
    return True


def save_user_cg_config(user_id: int, config: dict):
    """Save user's CreateGroup config to persistent JSON."""
    try:
        data = {}
        os.makedirs(os.path.dirname(_USER_CG_CONFIG_FILE), exist_ok=True)
        if os.path.exists(_USER_CG_CONFIG_FILE):
            with open(_USER_CG_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = _json.load(f)
        data[str(user_id)] = config
        tmp = f"{_USER_CG_CONFIG_FILE}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            _json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, _USER_CG_CONFIG_FILE)
    except Exception as e:
        logger.error(f"Failed to save user CG config: {e}\n{traceback.format_exc()}")

def load_user_cg_config(user_id: int) -> dict:
    """Load user's saved CreateGroup config, or return defaults."""
    try:
        if os.path.exists(_USER_CG_CONFIG_FILE):
            with open(_USER_CG_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = _json.load(f)
            saved = data.get(str(user_id))
            if saved:
                merged = DEFAULT_CREATEGROUP_CONFIG.copy()
                merged.update(saved)
                return merged
    except Exception as e:
        logger.error(f"Failed to load user CG config: {e}\n{traceback.format_exc()}")
    return DEFAULT_CREATEGROUP_CONFIG.copy()

from datetime import datetime
from Main.utils.file_helpers import get_user_button_style

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_menu_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def creategroup_menu_handler(c: Client, cb: CallbackQuery):
    await cb.answer()
    session_index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2)) if cb.matches[0].group(2) else 1
    
    from Main.internals.settings_handlers.custom_alert_handlers import _get_session_user_id
    session_user_id = _get_session_user_id(session_index)
    user_style = get_user_button_style(session_user_id)
    
    text = (
        f"<blockquote expandable>"
        "<b>🚀 Create Group</b>\n\n"
        "Pilih metode input konfigurasi:\n"
        "• <b>Manual Input:</b> Ketik perintah lengkap\n"
        "• <b>Interactive UI:</b> Gunakan tombol menu"
        f"</blockquote>"
    )
    
    buttons = [
        [InlineKeyboardButton("⌨️ Manual Input", callback_data=f"creategroup_manual_{session_index}_{page}", style=user_style)],
        [InlineKeyboardButton("🎛️ Interactive UI", callback_data=f"creategroup_ui_{session_index}_{page}", style=user_style)],
        [InlineKeyboardButton("🔄 Restore Tasks", callback_data=f"creategroup_cached_{session_index}_{page}", style=user_style)],
        [InlineKeyboardButton("🔙 Back to Session", callback_data=f"session_info_{session_index}_{page}", style=user_style)]
    ]
    
    await safe_edit_message_text(cb, text, reply_markup=InlineKeyboardMarkup(buttons))

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_cached_(\d+)_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def creategroup_cached_handler(c: Client, cb: CallbackQuery):
    await cb.answer()
    
    # Use split instead of cb.matches to be safe for manual calls from other handlers
    data = cb.data.split("_")
    # Format can be creategroup_cached_idx_pg_tpg OR creategroup_pauall_idx_pg etc
    # Both have index 2 as session and index 3 as page
    try:
        session_index = int(data[2])
        page = int(data[3])
        task_page = int(data[4]) if len(data) > 4 and data[4].isdigit() else 1
    except (IndexError, ValueError):
        # Fallback for unexpected data formats
        session_index = 1
        page = 1
        task_page = 1
    
    from Main.plugins.userbot.xcreategroup import CREATEGROUP_TASKS
    from Main.internals.settings_handlers.custom_alert_handlers import _get_session_user_id
    session_user_id = _get_session_user_id(session_index)
    user_style = get_user_button_style(session_user_id)
    
    if not CREATEGROUP_TASKS:
        text = "<blockquote expandable><b>🔄 Restore Tasks (Cache) [0/0 | Total: 0]</b>\n\n<i>Tidak ada task yang terhenti atau tersimpan di cache saat ini.</i></blockquote>"
        buttons = [[InlineKeyboardButton("🔙 Back", callback_data=f"creategroup_menu_{session_index}_{page}", style=user_style)]]
        return await safe_edit_message_text(cb, text, reply_markup=InlineKeyboardMarkup(buttons))
        
    all_tasks = list(CREATEGROUP_TASKS.items())
    total_tasks = len(all_tasks)
    limit = 5
    total_pages = (total_tasks + limit - 1) // limit
    task_page = max(1, min(task_page, total_pages))
    
    start = (task_page - 1) * limit
    end = start + limit
    current_tasks = all_tasks[start:end]
    
    lines = []
    buttons = []
    
    for tid, task in current_tasks:
        current = task.get("current_index", 0)
        total = task.get("params", {}).get("count", 0)
        account = task.get("account_name", "Unknown")
        step = task.get("current_step", "N/A")
        
        # 🔥 SMART STATUS LOGIC
        is_running = task.get("running", False)
        is_paused = task.get("paused", False)
        task_obj = task.get("task_obj")
        
        if is_running:
            # Check if the task is REALLY running (asyncio task is active)
            if task_obj and not task_obj.done():
                if is_paused:
                    status = "⏸️ Paused"
                else:
                    status = "🟢 Running"
            else:
                # Task marked as running but the actual coroutine is gone (likely after restart)
                status = "⚠️ Interrupted"
        else:
            status = "🛑 Stopped"
        
        # Text summary for header
        lines.append(f"• <b>{tid}</b> [{status}] | {account} ({int(current)}/{int(total)})")
        
        # Row 1: Task Label - NOW ACTS AS ENTRY TO SUB-MENU
        # We append session_index, page, and task_page to the callback for "Back" navigation
        buttons.append([
            InlineKeyboardButton(f"⚙️ Manage {tid} — {account[:15]}", callback_data=f"creategroup_task_manage_{tid}_{session_index}_{page}_{task_page}", style=user_style)
        ])
        
    text = f"<blockquote expandable><b>🔄 Restore Tasks (Cache) [{task_page}/{total_pages} | Total: {total_tasks}]</b>\n\n" + "\n".join(lines) + "\n\n<i>Klik tombol aksi di bawah untuk memproses task spesifik.</i></blockquote>"
    
    # ─── BULK CONTROL BUTTONS ───
    buttons.append([
        InlineKeyboardButton("Resume All", callback_data=f"creategroup_resall_{session_index}_{page}", style=user_style),
        InlineKeyboardButton("End All", callback_data=f"creategroup_endall_{session_index}_{page}", style=user_style),
        InlineKeyboardButton("Pause All", callback_data=f"creategroup_pauall_{session_index}_{page}", style=user_style),
    ])
    
    # Navigation row [« prev] [n/n] [next »]
    nav = []
    # Prev button
    if task_page > 1:
        nav.append(InlineKeyboardButton("« Prev", callback_data=f"creategroup_cached_{session_index}_{page}_{task_page-1}", style=user_style))
    else:
        nav.append(InlineKeyboardButton("« Prev", callback_data="creategroup_noop", style=user_style))
        
    # Page indicator
    nav.append(InlineKeyboardButton(f"{task_page}/{total_pages}", callback_data="creategroup_noop", style=user_style))
    
    # Next button
    if task_page < total_pages:
        nav.append(InlineKeyboardButton("Next »", callback_data=f"creategroup_cached_{session_index}_{page}_{task_page+1}", style=user_style))
    else:
        nav.append(InlineKeyboardButton("Next »", callback_data="creategroup_noop", style=user_style))
    
    buttons.append(nav)
    
    # First / Last / Refresh
    nav_extra = []
    nav_extra.append(InlineKeyboardButton("First", callback_data=f"creategroup_cached_{session_index}_{page}_1", style=user_style))
    nav_extra.append(InlineKeyboardButton("Refresh", callback_data=f"creategroup_cached_{session_index}_{page}_{task_page}", style=user_style))
    nav_extra.append(InlineKeyboardButton("Last", callback_data=f"creategroup_cached_{session_index}_{page}_{total_pages}", style=user_style))
    buttons.append(nav_extra)
    
    buttons.append([InlineKeyboardButton("🔙 Back to Menu", callback_data=f"creategroup_menu_{session_index}_{page}", style=user_style)])
    
    await safe_edit_message_text(cb, text, reply_markup=InlineKeyboardMarkup(buttons))


# ─── BULK CONTROL HANDLERS ───
@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_resall_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_resall_handler(c: Client, cb: CallbackQuery):
    from Main.plugins.userbot.xcreategroup import CREATEGROUP_TASKS, creategroup_loop
    
    resumed_count = 0
    tasks_to_start = [] # For interrupted tasks (need new loop)
    
    for tid, task in CREATEGROUP_TASKS.items():
        is_running = task.get("running", False)
        task_obj = task.get("task_obj")
        is_paused = task.get("paused", False)
        
        # 1. Handle Interrupted Tasks (Running but task object is dead)
        if is_running and (not task_obj or task_obj.done()):
            tasks_to_start.append(tid)
            resumed_count += 1
            
        # 2. Handle Paused Tasks (Task object is alive but waiting on event)
        elif is_paused:
            task["paused"] = False
            if "pause_event" in task:
                task["pause_event"].set()
            
            # Sync with global registry
            registry = getattr(Altruix, "_TASK_REGISTRY", {})
            if tid in registry:
                registry[tid]["paused"] = False
                
            resumed_count += 1
            
    if resumed_count == 0:
        return await cb.answer("Tidak ada task terhenti atau ter-pause untuk di-resume.", show_alert=True)
        
    await cb.answer(f"Me-resume {resumed_count} task...")
    
    # Start new loops for interrupted tasks
    for tid in tasks_to_start:
        task_data = CREATEGROUP_TASKS[tid]
        params = task_data.get("params", {})
        client_id = task_data.get("user_id")
        user_client = next((cl for cl in Altruix.clients if cl.me and cl.me.id == client_id), None)
        if not user_client and Altruix.clients: user_client = Altruix.clients[0]
        
        if user_client:
            # Ensure paused state is False for new loop
            task_data["paused"] = False
            if "pause_event" in task_data:
                task_data["pause_event"].set()
                
            # Sync with global registry
            registry = getattr(Altruix, "_TASK_REGISTRY", {})
            if tid in registry:
                registry[tid]["paused"] = False
            
            asyncio.create_task(creategroup_loop(
                user_client=user_client, bot_client=Altruix.bot, initial_message=None,
                delay=params.get("delay"), count=params.get("count"),
                extra_delay_minutes=params.get("extra_delay_minutes"),
                batch_size=params.get("batch_size"), group_type=params.get("group_type"),
                name_pattern=params.get("name_pattern"), username_prefix=params.get("username_prefix"),
                bot_identifiers=params.get("bot_identifiers"), control_message=None,
                action_delay=params.get("action_delay", 3.0), invite_bots=params.get("invite_bots", True),
                anon_mode=params.get("anon_mode", True), copy_messages=params.get("copy_messages", True),
                description=params.get("description", "Powered by @AlphaXproject"),
                photo_source=params.get("photo_source", "source"), custom_photo_id=params.get("custom_photo_id"),
                log_destination=params.get("log_destination", "both"), log_format=params.get("log_format", "zip"),
                pin_first_msg=params.get("pin_first_msg", True), temp_pin=params.get("temp_pin", True),
                quote_block=params.get("quote_block", True), msg_img=params.get("msg_img", True),
                msg_vid=params.get("msg_vid", True),
                msg_img_album=params.get("msg_img_album", False),
                msg_vid_album=params.get("msg_vid_album", False),
                rand_len=params.get("rand_len", 0), rand_lower=params.get("rand_lower", False),
                rand_upper=params.get("rand_upper", False), rand_static=params.get("rand_static", False),
                batch_action=params.get("batch_action", 30), ba_delay=params.get("ba_delay", 30),
                user_id=client_id, task_id=tid, is_resume=True,
                account_idx=params.get("account_idx", 1), total_accs=params.get("total_accs", 1),
                start_log_mode=params.get("start_log_mode", "both"),
                start_photo_log_mode=params.get("start_photo_log_mode", "both"),
                progress_log_mode=params.get("progress_log_mode", "both"),
                panel_log_mode=params.get("panel_log_mode", "log_group"),
                auto_start=params.get("auto_start", False),
                auto_start_count=params.get("auto_start_count", params.get("batch_account", 3)),
            ))

    # Refresh UI with suppression for MessageNotModified
    try:
        await creategroup_cached_handler(c, cb)
    except Exception as e:
        if "MESSAGE_NOT_MODIFIED" not in str(e):
            logger.error(f"Error refreshing cache UI: {e}")


@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_pauall_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_pauall_handler(c: Client, cb: CallbackQuery):
    from Main.plugins.userbot.xcreategroup import CREATEGROUP_TASKS
    registry = getattr(Altruix, "_TASK_REGISTRY", {})
    count = 0
    for tid, task in CREATEGROUP_TASKS.items():
        if task.get("running") and not task.get("paused"):
            task["paused"] = True
            if tid in registry: registry[tid]["paused"] = True
            if "pause_event" in task: task["pause_event"].clear()
            count += 1
            
    await cb.answer(f"{count} task dipause.")
    await creategroup_cached_handler(c, cb)


@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_endall_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_endall_handler(c: Client, cb: CallbackQuery):
    from Main.plugins.userbot.xcreategroup import CREATEGROUP_TASKS, save_creategroup_cache
    registry = getattr(Altruix, "_TASK_REGISTRY", {})
    count = len(CREATEGROUP_TASKS)
    if count == 0: return await cb.answer("Tidak ada task untuk dihapus.", show_alert=True)
    
    # Signal stop to all running tasks first
    for tid, task in CREATEGROUP_TASKS.items():
        task["running"] = False
        if tid in registry: registry[tid]["paused"] = True # Force stop sync
        if task.get("task_obj"): task["task_obj"].cancel()
        
    CREATEGROUP_TASKS.clear()
    await save_creategroup_cache()
    await cb.answer(f"{count} task dihapus.")
    await creategroup_cached_handler(c, cb)


@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_noop$"))
async def creategroup_noop_handler(c: Client, cb: CallbackQuery):
    await cb.answer()


@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_task_manage_(?P<tid>.+?)_(?P<session>\d+)_(?P<page>\d+)_(?P<tpage>\d+)$"))
@iuser_check
@log_errors
async def creategroup_task_manage_handler(c: Client, cb: CallbackQuery):
    """Sub-menu to manage a specific cached/active task."""
    m = cb.matches[0]
    tid = m.group("tid")
    session_index = int(m.group("session"))
    page = int(m.group("page"))
    task_page = int(m.group("tpage"))
    
    from Main.plugins.userbot.xcreategroup import CREATEGROUP_TASKS, get_creategroup_dashboard_text
    task = CREATEGROUP_TASKS.get(tid)
    if not task:
        return await cb.answer("❌ Task tidak ditemukan di memori.", show_alert=True)
    
    # Generate clean standardized text
    text = get_creategroup_dashboard_text(tid)
    
    # Check live status for buttons
    task_obj = task.get("task_obj")
    is_paused = task.get("paused", False)
    is_running = task.get("running", False)
    is_actually_alive = task_obj and not task_obj.done()
    
    can_resume = not is_actually_alive or is_paused
    
    # Resolve user_style
    from Main.internals.settings_handlers.custom_alert_handlers import _get_session_user_id
    session_user_id = _get_session_user_id(session_index)
    user_style = get_user_button_style(session_user_id)
    
    # Build Sub-Menu Buttons
    buttons = [
        [
            InlineKeyboardButton("▶️ Resume" if can_resume else "⏸ Pause", 
                                 callback_data=f"recover_creategroup:{tid}", style=user_style),
            InlineKeyboardButton("🛑 End", callback_data=f"delete_task_creategroup:{tid}", style=user_style),
            InlineKeyboardButton("🔄 Refresh", callback_data=cb.data, style=user_style)
        ]
    ]
    
    # Add "View" (External Link) if available
    chat_link = task.get("invite_link")
    if not chat_link and task.get("current_chat_id"):
        c_id = task.get("current_chat_id")
        if str(c_id).startswith("-100"):
            chat_link = f"https://t.me/c/{str(c_id)[4:]}/1"
    
    row_nav = []
    if chat_link:
        row_nav.append(InlineKeyboardButton("🔍 View", url=chat_link, style=user_style))
    
    row_nav.append(InlineKeyboardButton("📋 Back", callback_data=f"creategroup_cached_{session_index}_{page}_{task_page}", style=user_style))
    buttons.append(row_nav)
    
    try:
        await safe_edit_message_text(cb, text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        logger.warning(f"Failed to edit restore task message: {e}")
        await safe_cb_answer(cb, "⚠️ Unable to update menu", show_alert=False)

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_manual_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_manual_handler(c: Client, cb: CallbackQuery):
    await cb.answer()
    session_index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    
    # Resolve user_style
    from Main.internals.settings_handlers.custom_alert_handlers import _get_session_user_id
    session_user_id = _get_session_user_id(session_index)
    user_style = get_user_button_style(session_user_id)
    
    user_creategroup_state[cb.from_user.id] = {
        "step": "input_manual",
        "session_index": session_index,
        "page": page
    }

    text = (
        f"<blockquote expandable>"
        "<b>⌨️ Create Group - Manual Input</b>\n\n"
        "Kirim pesan di chat ini dengan format berikut:\n"
        "<code>[delay] [count] [batch_delay] [batch_size] [type] [pattern]</code>\n\n"
        "<b>Detail Parameter:</b>\n"
        "• <code>delay</code> : Jeda antar grup (detik).\n"
        "• <code>count</code> : Jumlah total grup.\n"
        "• <code>batch_delay</code> : Jeda antar batch (detik).\n"
        "• <code>batch_size</code> : Jumlah grup per batch.\n"
        "• <code>type</code> : Tipe (<code>group</code> / <code>supergroup</code>).\n"
        "• <code>pattern</code> : Nama (gunakan tanda kutip jika ada spasi).\n\n"
        "<b>Contoh Spesifik:</b>\n"
        "<code>60 5 300 2 supergroup \"Project X\"</code>\n"
        "<i>(Membuat 5 supergroup, tiap 2 grup istirahat 300 detik)</i>\n\n"
        "<b>Opsi Custom Username & Bot:</b>\n"
        "<code>... [pattern] ; [username] [bot1] [bot2]</code>\n"
        "Contoh: <code>60 3 0 0 group Test ; x_user bot1 bot2</code>\n\n"
        "<b>Placeholders Pattern:</b>\n"
        "• <code>(index)</code> : Urutan (1, 2, 3...)\n"
        "• <code>(tahun)</code> : 2 digit tahun\n"
        "• <code>(bulan)</code> : Bulan (angka)\n"
        "• <code>(tanggal)</code>: Tanggal\n\n"
        "<i>Ketik /cancel untuk membatalkan.</i>"
        f"</blockquote>"
    )

    
    await safe_edit_message_text(cb, text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"creategroup_menu_{session_index}_{page}", style=user_style)]]))

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_ui_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_ui_handler(c: Client, cb: CallbackQuery):
    """
    Interactive UI configuration for CreateGroup.
    Loads existing configuration or defaults and renders the adjustment menu.
    Handles task state checking to prevent multiple overlapping tasks.
    """
    await cb.answer()
    session_index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    await show_creategroup_ui(c, cb, session_index, page)

async def _find_task_by_session_idx(idx: int):
    if not (1 <= idx <= len(Altruix.clients)):
        return None
    client = Altruix.clients[idx - 1]
    try:
        me_user = client.me or await client.get_me()
        target_session_id = me_user.id
    except Exception:
        return None
        
    from Main.plugins.userbot.xcreategroup import CREATEGROUP_TASKS
    for k, v in CREATEGROUP_TASKS.items():
        if v.get("user_id") == target_session_id and v.get("running"):
            t_obj = v.get("task_obj")
            # ✅ FIX: Also match cache-restored tasks where task_obj is None
            if t_obj is None or not t_obj.done():
                return v
    return None

def _extract_primary_session_user_id_from_ui_text(text: Optional[str]) -> Optional[int]:
    try:
        if not text:
            return None
        m = re.search(r"tg://user\?id=(\d+)", text)
        if not m:
            return None
        return int(m.group(1))
    except Exception:
        return None

async def _find_session_index_by_user_id(target_user_id: int) -> Optional[int]:
    try:
        if not target_user_id:
            return None
        for i, client in enumerate(Altruix.clients or []):
            me = getattr(client, "myself", None) or getattr(client, "me", None)
            if me and getattr(me, "id", None) == target_user_id:
                return i + 1
    except Exception as e:
        logger.warning(f"Failed to map user_id to session index: {e}")
    return None

async def _resolve_cg_session_index_from_cb(cb: CallbackQuery, fallback_idx: int = 1) -> int:
    try:
        user_id = cb.from_user.id if cb and cb.from_user else None
        if user_id in user_creategroup_state:
            idx = user_creategroup_state[user_id].get("session_index")
            if isinstance(idx, int) and 1 <= idx <= len(Altruix.clients):
                return idx

        msg = getattr(cb, "message", None)
        if msg:
            msg_text = getattr(msg, "text", None) or getattr(msg, "caption", None) or ""
            session_user_id = _extract_primary_session_user_id_from_ui_text(msg_text)
            if session_user_id:
                mapped = await _find_session_index_by_user_id(session_user_id)
                if mapped:
                    return mapped
    except Exception as e:
        logger.warning(f"Failed to resolve CG session index from callback: {e}\n{traceback.format_exc()}")

    try:
        if isinstance(fallback_idx, int) and 1 <= fallback_idx <= len(Altruix.clients):
            return fallback_idx
    except Exception:
        pass
    return 1

async def _ensure_creategroup_ui_state(c: Client, cb: CallbackQuery, session_index: int, page: int, session_page: Optional[int] = None):
    user_id = cb.from_user.id
    try:
        if user_id not in user_creategroup_state or not isinstance(user_creategroup_state.get(user_id), dict):
            user_creategroup_state[user_id] = {}

        state = user_creategroup_state[user_id]
        state["step"] = "ui_config"
        state["session_index"] = session_index
        state["page"] = page
        state["input_mode"] = None
        state.setdefault("sub_menu", None)

        if "config" not in state or not isinstance(state.get("config"), dict):
            state["config"] = load_user_cg_config(user_id)

        if "selected_sessions" not in state or not isinstance(state.get("selected_sessions"), list):
            state["selected_sessions"] = [session_index]
        # Removed forced selection of current session when list is empty to allow deselection

        if session_page is not None:
            state["session_page"] = session_page
        else:
            state.setdefault("session_page", 0)

        if cb.message:
            state["ui_msg_id"] = cb.message.id
            state["ui_chat_id"] = cb.message.chat.id if cb.message.chat else None
        else:
            state.setdefault("ui_msg_id", None)
            state.setdefault("ui_chat_id", None)

        state.setdefault("prompt_msg_id", None)
        return state
    except Exception as e:
        logger.error(f"Failed to ensure CreateGroup UI state: {e}\n{traceback.format_exc()}")
        user_creategroup_state[user_id] = {
            "step": "ui_config",
            "session_index": session_index,
            "page": page,
            "config": load_user_cg_config(user_id),
            "selected_sessions": [session_index],
            "input_mode": None,
            "ui_msg_id": cb.message.id if cb.message else None,
            "ui_chat_id": cb.message.chat.id if cb.message and cb.message.chat else None,
            "prompt_msg_id": None,
            "sub_menu": None,
            "launching": False
        }
        return user_creategroup_state[user_id]

async def show_creategroup_ui(c: Client, cb: CallbackQuery, session_index: int, page: int):
    user_id = cb.from_user.id
    
    # Check if task is already running
    task = await _find_task_by_session_idx(session_index)
    if task and task.get("running"):
        await render_creategroup_running_ui(cb, task, session_index, page)
        return

    if user_id not in user_creategroup_state or user_creategroup_state[user_id].get("step") != "ui_config":
        if user_id in user_creategroup_state and user_creategroup_state[user_id].get("prompt_msg_id"):
            try:
                if cb.message:
                    await c.delete_messages(cb.message.chat.id, user_creategroup_state[user_id]["prompt_msg_id"])
            except: pass
            
        user_creategroup_state[user_id] = {
            "step": "ui_config",
            "session_index": session_index,
            "page": page,
            "config": load_user_cg_config(user_id),
            "selected_sessions": [session_index], # ✅ DEFAULT: Current session
            "session_page": 0,
            "input_mode": None,
            "ui_msg_id": cb.message.id if cb.message else None,
            "ui_chat_id": cb.message.chat.id if cb.message else None,
            "prompt_msg_id": None,
            "sub_menu": None,
            "launching": False
        }
    else:
        user_creategroup_state[user_id]["step"] = "ui_config"
        user_creategroup_state[user_id]["input_mode"] = None
        user_creategroup_state[user_id]["launching"] = False
        if user_creategroup_state[user_id].get("prompt_msg_id"):
            try:
                if cb.message:
                    await c.delete_messages(cb.message.chat.id, user_creategroup_state[user_id]["prompt_msg_id"])
            except: pass
            user_creategroup_state[user_id]["prompt_msg_id"] = None
    
    await render_creategroup_ui(cb, user_creategroup_state[user_id])

async def get_creategroup_ui_data(user_id: int, session_index: int, page: int = 1):
    """
    Get the text and markup for the CreateGroup UI dashboard.
    Used for both callback-based and inline-based UI.
    """
    if user_id not in user_creategroup_state:
        user_creategroup_state[user_id] = {
            "step": "ui_config",
            "session_index": session_index,
            "page": page,
            "config": load_user_cg_config(user_id),
            "selected_sessions": [session_index], # ✅ Initialize with 1-based index
            "input_mode": None,
            "ui_msg_id": None,
            "ui_chat_id": None,
            "prompt_msg_id": None,
            "launching": False
        }
    else:
        # 🔥 CRITICAL SYNC: If we are switching accounts, update the primary index and selection
        # This prevents a dashboard opened on Account 2 from using Account 1's state
        state = user_creategroup_state[user_id]
        if state.get("session_index") != session_index:
             state["session_index"] = session_index
             # Only initialize if missing or invalid; allow empty lists
             if "selected_sessions" not in state or not isinstance(state.get("selected_sessions"), list):
                 state["selected_sessions"] = [session_index]
    
    state = user_creategroup_state[user_id]
    state.setdefault("session_page", 0)
    config = state["config"]
    idx = state["session_index"]
    pg = state["page"]
    sub_menu = state.get("sub_menu")

    per_page = 5
    total_sessions = len(Altruix.clients)
    total_pages = (total_sessions + per_page - 1) // per_page if total_sessions else 1
    if state["session_page"] >= total_pages:
        state["session_page"] = max(0, total_pages - 1)
    
    # Resolve user_style
    from Main.internals.settings_handlers.custom_alert_handlers import _get_session_user_id
    session_user_id = _get_session_user_id(idx)
    user_style = get_user_button_style(session_user_id)
    
    # Safety check for Altruix.clients
    if not Altruix.clients or idx < 1 or idx > len(Altruix.clients):
        return f"❌ Session index {idx} invalid (Clients: {len(Altruix.clients)})", None

    session_client = Altruix.clients[idx - 1] # ✅ Convert 1-based to 0-based
    session_user = getattr(session_client, 'me', None)
    if not session_user:
        try: session_user = await session_client.get_me()
        except Exception: session_user = None

    # Display session and selection info
    # Ensure selected_sessions is a clean list of unique integers
    raw_selected = state.get("selected_sessions", [idx])
    if not isinstance(raw_selected, list):
        raw_selected = [idx]
    
    selected = []
    for x in raw_selected:
        try:
            val = int(x)
            if 1 <= val <= len(Altruix.clients) and val not in selected:
                selected.append(val)
        except (ValueError, TypeError):
            continue
            
    selected = sorted(selected)
    state["selected_sessions"] = selected
    sel_count = len(selected)
    
    session_text = ""
    if session_user:
        session_text = f"• <b>Session:</b> ⭐ <a href='tg://user?id={session_user.id}'>{html.escape(session_user.first_name)}</a>\n"
    
    session_text += f"• <b>Selected Acc(s):</b> <code>{sel_count}</code> / <code>{len(Altruix.clients)}</code>\n"

    photo_status = f"Source Account" if config.get('photo_source') == "source" else "Custom Photo"
    if config.get('photo_source') == "custom":
        photo_status += " ✅" if config.get('custom_photo_id') else " ❌ (No photo)"

    num_bots = len(config['bots'].split() if config['bots'] else [])
    is_default_bots = config['bots'] == DEFAULT_CREATEGROUP_CONFIG['bots']
    bot_list_text = f"{num_bots} bots{' (Default)' if is_default_bots else ''}"

    g_type = config.get('group_type', 'a')
    is_channel = g_type == 'c'
    type_label = "Channel" if is_channel else "Group"
    unit_name = "channels" if is_channel else "groups"

    # Generate name preview
    import random
    import string
    
    pattern = config.get('pattern', '')
    rand_len = config.get('rand_len', 3)
    rand_lower = config.get('rand_lower', False)
    rand_upper = config.get('rand_upper', True)
    
    name_preview = pattern
    if rand_len > 0 and (rand_lower or rand_upper):
        chars = ""
        if rand_lower: chars += string.ascii_lowercase
        if rand_upper: chars += string.ascii_uppercase
        # We use a fixed seed or just let it be random for preview
        rand_text = "".join(random.choices(chars, k=rand_len))
        if '(index)' in name_preview:
            name_preview = name_preview.replace('(index)', f"{rand_text} (index)")
        else:
            name_preview = f"{name_preview}{rand_text}"

    log_dest = config.get('log_destination', 'both')
    log_dest_lbl = "Both (Log+Saved)" if log_dest == "both" else ("Log Group" if log_dest == "log_group" else "Saved Messages")
    start_log = config.get('start_log_mode', 'both')
    start_log_lbl = "Both" if start_log == "both" else ("Group Log" if start_log == "log_group" else ("PM Bot" if start_log == "pm_bot" else "Off"))
    photo_log = config.get('start_photo_log_mode', 'both')
    photo_log_lbl = "Both" if photo_log == "both" else ("Group Log" if photo_log == "log_group" else ("PM Bot" if photo_log == "pm_bot" else "Off"))
    prog_log = config.get('progress_log_mode', 'both')
    prog_log_lbl = "Both" if prog_log == "both" else ("Group Log" if prog_log == "log_group" else ("PM Bot" if prog_log == "pm_bot" else "Off"))
    panel_log = config.get('panel_log_mode', 'log_group')
    panel_log_lbl = "Both" if panel_log == "both" else ("Group Log" if panel_log == "log_group" else ("PM Bot" if panel_log == "pm_bot" else "Off"))
    
    text = (
        "<b>🎛️ Auto Create Configuration</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>{session_text}</b>"
        f"• <b>Type:</b> {type_label}\n"
        f"• <b>Count:</b> {config['count']} {unit_name}\n"
        f"• <b>Action Delay:</b> {config['action_delay']}s\n"
        f"• <b>Delay:</b> {config['delay']}s\n"
        f"• <b>Batch Delay:</b> {config['batch_delay']}m | <b>Batch Size:</b> {config['batch_size']} {unit_name}\n"
        f"• <b>Batch Act:</b> {config.get('batch_action', 30)} act | <b>B.Act Delay:</b> {config.get('ba_delay', 30)}s\n"
        f"• <b>Account Delay:</b> {config.get('account_delay', 0.5)}s | <b>B.Acc Size:</b> {config.get('batch_account', 3)} acc\n"
        f"• <b>B.Acc Delay:</b> {config.get('ba_account_delay', 60)}s\n"
        f"• <b>Name:</b> {html.escape(name_preview)}\n"
        f"• <b>Username:</b> {config['username'] or 'None'}\n"
        f"• <b>Description:</b> {html.escape(config['description'])}\n"
        f"• <b>Photo:</b> {photo_status}\n"
        f"• <b>Anon Admin:</b> {'Yes' if config['anon_mode'] else 'No'} | <b>Copy Msg:</b> {'Yes' if config['copy_messages'] else 'No'}\n"
        f"• <b>Invite Bots:</b> {'Yes' if config['invite_bots'] else 'No'}\n"
        f"• <b>Bot List:</b> {bot_list_text}\n"
        f"• <b>Pin First Msg:</b> {'Yes' if config.get('pin_first_msg', True) else 'No'} | <b>Temp Pin:</b> {'Yes' if config.get('temp_pin', True) else 'No'}\n"
        f"• <b>Quote Block:</b> {'Yes' if config.get('quote_block', True) else 'No'} | <b>Msg Img:</b> {'Yes' if config.get('msg_img', True) else 'No'}\n"
        f"• <b>Msg Vid:</b> {'Yes' if config.get('msg_vid', True) else 'No'}\n"
        f"• <b>Album Img:</b> {'On' if config.get('msg_img_album', False) else 'Off'} | <b>Album Vid:</b> {'On' if config.get('msg_vid_album', False) else 'Off'}\n"
        f"• <b>Log To:</b> {log_dest_lbl} | <b>Format:</b> {config.get('log_format', 'zip').upper()}\n"
        f"• <b>Start Log:</b> {start_log_lbl} | <b>Photo Log:</b> {photo_log_lbl}\n"
        f"• <b>Progress Log:</b> {prog_log_lbl} | <b>Panel Log:</b> {panel_log_lbl}"
    )
    
    # ─── SUB-MENUS ───
    if sub_menu in ["action_delay", "account_delay", "delay", "count", "batch_delay", "batch_size", "batch_action", "ba_delay", "batch_account", "ba_account_delay"]:
        # Sub-Menu Keypad
        # steps = {"delay": 10, "count": 1, "batch_delay": 1, "batch_size": 1, "action_delay": 0.5}
        step_map = {"delay": 10, "count": 1, "batch_delay": 1, "batch_size": 1, "action_delay": 0.5, "account_delay": 0.5, "batch_action": 5, "ba_delay": 10, "batch_account": 1, "ba_account_delay": 10}
        step = step_map.get(sub_menu, 1)
        step_str = f"{step}" if step < 1 else f"{int(step)}"
        
        # Label and current value
        labels = {
            "action_delay": "Action Delay", "account_delay": "Account Delay", "delay": "Group Delay", 
            "count": "Total Groups", "batch_delay": "Batch Delay", "batch_size": "Batch Size",
            "batch_action": "Batch Act", "ba_delay": "B.Act Delay",
            "batch_account": "Batch Account", "ba_account_delay": "B.Acc Delay"
        }
        unit_map = {
            "action_delay": "s", 
            "account_delay": "s", 
            "delay": "s", 
            "batch_delay": "m", 
            "count": "c" if config.get('group_type', 'a') == 'c' else "g", 
            "batch_size": "c" if config.get('group_type', 'a') == 'c' else "g",
            "batch_account": " acc", "ba_account_delay": "s",
            "batch_action": " act", "ba_delay": "s"
        }
        
        label = labels.get(sub_menu, sub_menu.capitalize())
        curr_val = config.get(sub_menu)
        unit = unit_map.get(sub_menu, "")
        
        # Generate adjustment rows based on sub_menu
        adj_steps = []
        if sub_menu == "delay":
            adj_steps = [3, 5, 10, 30, 60, 120]
        elif sub_menu == "ba_delay":
            adj_steps = [3, 5, 10, 30, 60, 120]
        elif sub_menu == "batch_action":
            adj_steps = [3, 5, 10, 30, 60, 120]
        elif sub_menu == "action_delay" or sub_menu == "account_delay":
            adj_steps = [0.25, 0.5, 1, 3, 5]
        elif sub_menu == "count":
            adj_steps = [1, 3, 5, 10, 50, 100]
        elif sub_menu == "batch_size":
            adj_steps = [1, 3, 5, 10, 50, 100]
        elif sub_menu == "batch_delay":
            adj_steps = [1, 3, 5, 10, 30, 60]
        elif sub_menu == "batch_account":
            adj_steps = [1, 3, 5, 10, 50, 100]
        elif sub_menu == "ba_account_delay":
            adj_steps = [5, 10, 30, 60, 120, 300]
        
        buttons = [[InlineKeyboardButton(f"━━ {label}: {curr_val}{unit} ━━", callback_data="noop", style=user_style)]]
        
        for s in adj_steps:
            s_str = f"{s}" if s % 1 != 0 else f"{int(s)}"
            # Map standard step (1 for count, 10 for delay, etc.) to generic 'sub'/'add' if it matches the default step in creategroup_adjust_handler
            # Actually, creategroup_adjust_handler handles sub{val} and add{val} correctly.
            # But the default 'sub'/'add' uses steps.get(key, 1).
            # To avoid confusion, I'll use explicit values for all buttons.
            buttons.append([
                InlineKeyboardButton(f"-{s_str}{unit}", callback_data=f"creategroup_adj_{idx}_{pg}_{sub_menu}_sub{s_str}", style=user_style),
                InlineKeyboardButton(f"+{s_str}{unit}", callback_data=f"creategroup_adj_{idx}_{pg}_{sub_menu}_add{s_str}", style=user_style)
            ])
            
        buttons.append([
            InlineKeyboardButton("✏️ Manual Input", callback_data=f"creategroup_in_{idx}_{pg}_{sub_menu}", style=user_style),
            InlineKeyboardButton("🔙 Back", callback_data=f"creategroup_back_submenu_{idx}_{pg}", style=user_style)
        ])
        return text, InlineKeyboardMarkup(buttons)

    elif sub_menu == "group_type":
        curr = config.get("group_type", "a")
        buttons = [
            [InlineKeyboardButton(f"━━ Chat Type: {'Supergroup' if curr == 'a' else 'Channel'} ━━", callback_data="noop", style=user_style)],
            [
                InlineKeyboardButton("👥 Supergroup (Anon)", callback_data=f"creategroup_setv_{idx}_{pg}_group_type_a", style=user_style),
                InlineKeyboardButton("📢 Channel", callback_data=f"creategroup_setv_{idx}_{pg}_group_type_c", style=user_style)
            ],
            [InlineKeyboardButton("🔙 Back", callback_data=f"creategroup_back_submenu_{idx}_{pg}", style=user_style)]
        ]
        return text, InlineKeyboardMarkup(buttons)

    elif sub_menu == "pattern":
        buttons = [
            [InlineKeyboardButton(f"━━ Name Pattern: {config.get('pattern')[:20]}... ━━", callback_data="noop", style=user_style)],
            [InlineKeyboardButton("✏️ Change Name Pattern", callback_data=f"creategroup_in_{idx}_{pg}_pattern", style=user_style)],
            [InlineKeyboardButton("🎲 Random Text", callback_data=f"creategroup_submenu_{idx}_{pg}_random_text", style=user_style)],
            [InlineKeyboardButton("🔙 Back", callback_data=f"creategroup_back_submenu_{idx}_{pg}", style=user_style)]
        ]
        return text, InlineKeyboardMarkup(buttons)
        
    elif sub_menu == "random_text":
        r_len = config.get("rand_len", 3)
        r_low = "on" if config.get("rand_lower", False) else "off"
        r_up = "on" if config.get("rand_upper", True) else "off"
        r_stat = "on" if config.get("rand_static", True) else "off"
        
        buttons = [
            [InlineKeyboardButton(f"━━ Random Text Setting ━━", callback_data="noop", style=user_style)],
            [
                InlineKeyboardButton("-1", callback_data=f"creategroup_adj_{idx}_{pg}_rand_len_sub", style=user_style),
                InlineKeyboardButton(f"Text Length: {r_len}", callback_data="noop", style=user_style),
                InlineKeyboardButton("+1", callback_data=f"creategroup_adj_{idx}_{pg}_rand_len_add", style=user_style)
            ],
            [
                InlineKeyboardButton(f"Alpha Lower: {r_low}", callback_data=f"creategroup_toggle_{idx}_{pg}_rand_lower", style=user_style),
                InlineKeyboardButton(f"Alpha Upper: {r_up}", callback_data=f"creategroup_toggle_{idx}_{pg}_rand_upper", style=user_style)
            ],
            [InlineKeyboardButton(f"Static per Task: {r_stat}", callback_data=f"creategroup_toggle_{idx}_{pg}_rand_static", style=user_style)],
            [InlineKeyboardButton("🔙 Back", callback_data=f"creategroup_submenu_{idx}_{pg}_pattern", style=user_style)]
        ]
        return text, InlineKeyboardMarkup(buttons)

    elif sub_menu == "username":
        curr_us = config.get("username")
        buttons = [
            [InlineKeyboardButton(f"━━ Username Prefix: {curr_us or 'None'} ━━", callback_data="noop", style=user_style)],
            [InlineKeyboardButton("✏️ Set Username Prefix", callback_data=f"creategroup_in_{idx}_{pg}_username", style=user_style)],
            [InlineKeyboardButton("❌ Remove Username (None)", callback_data=f"creategroup_setv_{idx}_{pg}_username_none", style=user_style)],
            [InlineKeyboardButton("🔙 Back", callback_data=f"creategroup_back_submenu_{idx}_{pg}", style=user_style)]
        ]
        return text, InlineKeyboardMarkup(buttons)

    elif sub_menu == "description":
        buttons = [
            [InlineKeyboardButton(f"━━ Description: {config.get('description')[:20]}... ━━", callback_data="noop", style=user_style)],
            [InlineKeyboardButton("✏️ Change Description", callback_data=f"creategroup_in_{idx}_{pg}_description", style=user_style)],
            [InlineKeyboardButton("🔙 Back", callback_data=f"creategroup_back_submenu_{idx}_{pg}", style=user_style)]
        ]
        return text, InlineKeyboardMarkup(buttons)

    elif sub_menu == "photo":
        src = config.get("photo_source", "source")
        src_lbl = "👤 Source Account" if src == "source" else "🖼 Custom Photo"
        buttons = [
            [InlineKeyboardButton(f"━━ Photo Source: {src_lbl} ━━", callback_data="noop", style=user_style)],
            [
                InlineKeyboardButton("👤 Use Source Account", callback_data=f"creategroup_setv_{idx}_{pg}_photo_source_source", style=user_style),
                InlineKeyboardButton("🖼 Use Custom Photo", callback_data=f"creategroup_setv_{idx}_{pg}_photo_source_custom", style=user_style)
            ]
        ]
        if src == "custom":
            lbl = "📤 Re-upload Photo" if config.get("custom_photo_id") else "📤 Upload Photo"
            buttons.append([InlineKeyboardButton(lbl, callback_data=f"creategroup_upload_photo_{idx}_{pg}", style=user_style)])
        
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"creategroup_back_submenu_{idx}_{pg}", style=user_style)])
        return text, InlineKeyboardMarkup(buttons)

    elif sub_menu == "bots":
        curr_bots = config.get("bots") or ""
        num_bots = len(curr_bots.split())
        is_default = curr_bots == DEFAULT_CREATEGROUP_CONFIG['bots']
        
        # Override the text summary to show the full list only in this sub-menu
        text = (
            f"<blockquote expandable>"
            "<b>🤖 Bot Configuration</b>\n\n"
            f"• <b>Total Bots:</b> {num_bots}{' (Default)' if is_default else ''}\n"
            f"• <b>Username List:</b>\n<code>{html.escape(curr_bots or 'None')}</code>\n\n"
            "<i>Klik 'Add Bot List' untuk mengganti atau 'Reset' untuk kembali ke default.</i>"
            f"</blockquote>"
        )
        
        buttons = [
            [InlineKeyboardButton(f"━━ Bots List Configuration ━━", callback_data="noop", style=user_style)],
            [
                InlineKeyboardButton("✏️ Add Bot List", callback_data=f"creategroup_in_{idx}_{pg}_bots", style=user_style),
                InlineKeyboardButton("🔄 Reset to Default", callback_data=f"creategroup_setv_{idx}_{pg}_bots_default", style=user_style)
            ],
            [InlineKeyboardButton("🔙 Back", callback_data=f"creategroup_back_submenu_{idx}_{pg}", style=user_style)]
        ]
        return text, InlineKeyboardMarkup(buttons)

    elif sub_menu == "info":
        text = (
            f"<blockquote expandable>"
            "<b>ℹ️ Create Group/Channel - Comprehensive Guide</b>\n\n"
            "<b>🎛️ Basic Configuration:</b>\n"
            "• <b>Type:</b> <u>Supergroup</u> (mendukung Anon Admin/Topics) atau <u>Channel</u> (broadcast).\n"
            "• <b>Count:</b> Jumlah total grup/channel yang akan dibuat secara otomatis.\n"
            "• <b>Delay/Act:</b> Jeda antar aksi di dalam grup/channel (misal: setting foto, copy pesan, invite bot).\n"
            "• <b>Group/Channel Delay:</b> Jeda istirahat setelah satu grup/channel selesai diproses sebelum lanjut ke grup/channel berikutnya.\n\n"
            "<b>📦 Batch & Pacing:</b>\n"
            "• <b>Batch Size:</b> Jumlah grup/channel yang dibuat dalam satu sesi sebelum istirahat panjang.\n"
            "• <b>Batch Delay:</b> Durasi istirahat (menit) setelah mencapai Batch Size.\n"
            "<i>Tujuan: Menghindari limit Telegram (FloodWait).</i>\n\n"
            "<b>📝 Identity & Links:</b>\n"
            "• <b>Name Pattern:</b> Nama grup/channel. Gunakan <code>(index)</code> untuk angka urut, <code>(tahun)</code>, <code>(bulan)</code>, atau <code>(tanggal)</code>.\n"
            "• <b>Random Text:</b> Opsi injeksi kombinasi huruf acak secara otomatis ke dalam nama grup/channel sebelum urutan index.\n"
            "• <b>Username:</b> Prefix link publik. Contoh: <code>alpha_</code> + Index 1 = <code>@alpha_1</code>.\n"
            "• <b>Description:</b> Teks biografi/info grup/channel yang akan dipasang otomatis.\n"
            "• <b>Photo:</b> Ambil foto profil dari akun utama atau upload foto kustom.\n\n"
            "<b>🛡️ Advanced Features:</b>\n"
            "• <b>Anon Admin:</b> Mengaktifkan mode anonim agar nama akun Anda tidak terlihat oleh member.\n"
            "• <b>Copy Msg:</b> Menyalin template pesan dari channel sumber (alphaxbbc) ke setiap grup/channel baru.\n"
            "• <b>Invite Bots:</b> Otomatis mengundang daftar username bot yang telah Anda tentukan.\n"
            "• <b>Log To:</b> Memilih apakah laporan progres dikirim ke Group Log atau Saved Messages.\n"
            "• <b>Log Format:</b> Ekspor file report akhir dalam format .TXT standar atau terkompresi .ZIP."
            f"</blockquote>"
        )
        buttons = [[InlineKeyboardButton("🔙 Back to Dashboard", callback_data=f"creategroup_back_submenu_{idx}_{pg}", style=user_style)]]
        return text, InlineKeyboardMarkup(buttons)

    elif sub_menu == "select_sessions":
        selected = state.get("selected_sessions", [idx])
        # Pagination logic for sessions
        per_page = 5
        total_sessions = len(Altruix.clients)
        total_pages = (total_sessions + per_page - 1) // per_page if total_sessions else 1
        s_page = min(max(0, state.get("session_page", 0)), total_pages - 1)
        state["session_page"] = s_page

        # Account filter support: 'all' | 'newest' | 'oldest'
        acct_filter = config.get("account_filter", "all") or "all"

        # Build sortable session list (idx, client)
        indexed_clients = [(i + 1, client) for i, client in enumerate(Altruix.clients)]
        try:
            report_data = load_creation_report()
        except Exception:
            report_data = {}

        def _last_created_time_for_idx(idx):
            try:
                me = getattr(Altruix.clients[idx - 1], "me", None) or asyncio.get_event_loop().run_until_complete(Altruix.clients[idx - 1].get_me())
                s_uid = str(getattr(me, "id", None)) if me else None
                if s_uid and s_uid in report_data:
                    groups = report_data[s_uid].get("created_groups", [])
                    if groups:
                        # parse latest time
                        times = []
                        for g in groups:
                            t = g.get("time")
                            if not t: continue
                            try:
                                times.append(datetime.strptime(t, "%Y-%m-%d %H:%M:%S"))
                            except Exception:
                                continue
                        if times:
                            return max(times)
            except Exception:
                pass
            return None

        if acct_filter == "newest":
            indexed_clients.sort(key=lambda it: _last_created_time_for_idx(it[0]) or datetime.fromtimestamp(0), reverse=True)
        elif acct_filter == "oldest":
            indexed_clients.sort(key=lambda it: _last_created_time_for_idx(it[0]) or datetime.fromtimestamp(2**31-1))

        start = s_page * per_page
        end = start + per_page
        paged_slice = indexed_clients[start:end]
        # Keep the original (index, client) pairs so we can show correct session numbers
        paged_clients = paged_slice
        # Record the original session indices displayed on this page so handlers can act on them
        try:
            state["last_paged_indices"] = [orig for orig, _ in paged_slice]
        except Exception:
            state["last_paged_indices"] = []

        # Load creation reports to show counts on buttons (already attempted above)
        # report_data variable is available; fallback to loader
        if 'report_data' not in locals():
            report_data = load_creation_report()
        
        text = (
            f"<blockquote expandable>"
            f"<b>👥 Multi-Session Selection</b> (Page {s_page+1}/{total_pages})\n\n"
            f"Pilih satu atau beberapa akun yang akan menjalankan task ini secara bersamaan.\n"
            f"Total Terpilih: <code>{len(selected)}</code> / <code>{total_sessions}</code>\n\n"
            f"<i>☑️ = selected | ☐ = not selected</i>"
            f"</blockquote>"
        )
        
        # Filter buttons row
        filter_buttons = [
            InlineKeyboardButton(f"{'✅' if acct_filter=='all' else '◻️'} All", callback_data=f"creategroup_filter_all_{idx}_{pg}", style=user_style),
            InlineKeyboardButton(f"{'✅' if acct_filter=='newest' else '◻️'} Newest", callback_data=f"creategroup_filter_newest_{idx}_{pg}", style=user_style),
            InlineKeyboardButton(f"{'✅' if acct_filter=='oldest' else '◻️'} Oldest", callback_data=f"creategroup_filter_oldest_{idx}_{pg}", style=user_style)
        ]
        buttons = [filter_buttons]
        for i, (orig_idx, client) in enumerate(paged_clients):
            actual_idx = orig_idx
            is_sel = actual_idx in selected
            icon = "☑️" if is_sel else "☐"

            # 🔥 INDICATOR: Mark the session that triggered the command (compare against original index)
            current_tag = " ⭐ [ Current ]" if actual_idx == idx else ""

            try:
                me = getattr(client, "me", None) or await client.get_me()
                name = me.first_name
                s_uid = str(me.id)
            except Exception as e:
                logger.warning(f"Failed to resolve session name for idx={actual_idx}: {e}")
                name = f"Session {actual_idx}"
                s_uid = None

            # Count groups created by this session
            count_info = ""
            if s_uid and s_uid in report_data:
                count = len(report_data[s_uid].get("created_groups", []))
                if count > 0:
                    count_info = f" ({count})"

            buttons.append([InlineKeyboardButton(f"{icon} {actual_idx}. {name}{count_info}{current_tag}", callback_data=f"creategroup_tsel_{actual_idx}_{pg}", style=user_style)])
            
        # Select Page / Deselect Page
        buttons.append([
            InlineKeyboardButton("☑️ Select Page", callback_data=f"creategroup_selp_{s_page}_{pg}", style=user_style),
            InlineKeyboardButton("☐ Deselect Page", callback_data=f"creategroup_dselp_{s_page}_{pg}", style=user_style)
        ])

        # Select All / Deselect All
        buttons.append([
            InlineKeyboardButton("✅ Select All", callback_data=f"creategroup_sall_{s_page}_{pg}", style=user_style),
            InlineKeyboardButton("❌ Deselect All", callback_data=f"creategroup_dsall_{s_page}_{pg}", style=user_style)
        ])
        
        # Navigation
        nav = []
        if s_page > 0: nav.append(InlineKeyboardButton("« Prev", callback_data=f"creategroup_spage_{s_page-1}_{pg}", style=user_style))
        if total_pages > 1: nav.append(InlineKeyboardButton(f"{s_page+1}/{total_pages}", callback_data="noop", style=user_style))
        if end < total_sessions: nav.append(InlineKeyboardButton("Next »", callback_data=f"creategroup_spage_{s_page+1}_{pg}", style=user_style))
        if nav: buttons.append(nav)

        # Back 5 / Next 5 Navigation
        if total_pages > 1:
            nav_5 = []
            if s_page > 0:
                back_5_page = max(0, s_page - 5)
                nav_5.append(InlineKeyboardButton("« 5 Prev", callback_data=f"creategroup_spage_{back_5_page}_{pg}", style=user_style))
            if s_page < total_pages - 1:
                next_5_page = min(total_pages - 1, s_page + 5)
                nav_5.append(InlineKeyboardButton("Next 5 »", callback_data=f"creategroup_spage_{next_5_page}_{pg}", style=user_style))
            if nav_5:
                buttons.append(nav_5)

        # First / Last Navigation
        if total_pages > 2:
            buttons.append([
                InlineKeyboardButton("First", callback_data=f"creategroup_spage_0_{pg}", style=user_style),
                InlineKeyboardButton("Last", callback_data=f"creategroup_spage_{total_pages-1}_{pg}", style=user_style)
            ])
        
        buttons.append([InlineKeyboardButton(f"🚀 Run Task ({len(selected)} Acc)", callback_data=f"creategroup_run_{idx}_{pg}", style=user_style)])
        buttons.append([InlineKeyboardButton("🔙 Back to Dashboard", callback_data=f"creategroup_back_submenu_{idx}_{pg}", style=user_style)])
        return text, InlineKeyboardMarkup(buttons)

    elif sub_menu == "log_settings":
        log_dest = config.get("log_destination", "both")
        _il_labels = {'both': 'Both', 'log_group': 'Log Group', 'pm_bot': 'PM Bot', 'off': 'Off'}
        _il_label = _il_labels.get(config.get('interrupted_log', 'off'), 'Off')
        _sl_labels = {'both': 'Both', 'log_group': 'Group Log', 'pm_bot': 'PM Bot', 'off': 'Off'}
        _sl_label = _sl_labels.get(config.get('start_log_mode', 'both'), 'Both')
        _pl_labels = {'both': 'Both', 'log_group': 'Group Log', 'pm_bot': 'PM Bot', 'off': 'Off'}
        _pl_label = _pl_labels.get(config.get('start_photo_log_mode', 'both'), 'Both')
        _pgl_labels = {'both': 'Both', 'log_group': 'Group Log', 'pm_bot': 'PM Bot', 'off': 'Off'}
        _pgl_label = _pgl_labels.get(config.get('progress_log_mode', 'both'), 'Both')
        _pnl_labels = {'both': 'Both', 'log_group': 'Group Log', 'pm_bot': 'PM Bot', 'off': 'Off'}
        _pnl_label = _pnl_labels.get(config.get('panel_log_mode', 'log_group'), 'Group Log')
        _dl_labels = {'both': 'Both', 'log_group': 'Group Log', 'pm_bot': 'PM Bot', 'off': 'Off'}
        _dl_label = _dl_labels.get(config.get('delay_log_mode', 'both'), 'Both')

        text = (
            f"<blockquote expandable>"
            "<b>📂 Log & Notification Settings</b>\n\n"
            "Atur preferensi log untuk meminimalkan spam dan melacak progres.\n"
            f"• <b>Destination:</b> {'Both' if log_dest == 'both' else ('GroupLog' if log_dest == 'log_group' else 'SavedMsg')}\n"
            f"• <b>Format:</b> {config.get('log_format', 'zip').upper()}\n"
            f"</blockquote>"
        )

        buttons = [
            [
                InlineKeyboardButton(f"Start Log: {_sl_label}", callback_data=f"creategroup_toggle_{idx}_{pg}_start_log_mode", style=user_style),
                InlineKeyboardButton(f"Photo Log: {_pl_label}", callback_data=f"creategroup_toggle_{idx}_{pg}_start_photo_log_mode", style=user_style)
            ],
            [
                InlineKeyboardButton(f"Prog Log: {_pgl_label}", callback_data=f"creategroup_toggle_{idx}_{pg}_progress_log_mode", style=user_style),
                InlineKeyboardButton(f"Panel Log: {_pnl_label}", callback_data=f"creategroup_toggle_{idx}_{pg}_panel_log_mode", style=user_style)
            ],
            [
                InlineKeyboardButton(f"Interrupt Log: {_il_label}", callback_data=f"creategroup_toggle_{idx}_{pg}_interrupted_log", style=user_style),
                InlineKeyboardButton(f"Delay Log: {_dl_label}", callback_data=f"creategroup_toggle_{idx}_{pg}_delay_log_mode", style=user_style)
            ],
            [
                InlineKeyboardButton(f"FileLog To: {'Both' if log_dest == 'both' else ('GroupLog' if log_dest == 'log_group' else 'SavedMsg')}", callback_data=f"creategroup_toggle_{idx}_{pg}_log_destination", style=user_style),
                InlineKeyboardButton(f"Log Format: {config.get('log_format', 'zip').upper()}", callback_data=f"creategroup_toggle_{idx}_{pg}_log_format", style=user_style)
            ],
            [InlineKeyboardButton("🔙 Back to Dashboard", callback_data=f"creategroup_back_submenu_{idx}_{pg}", style=user_style)]
        ]
        return text, InlineKeyboardMarkup(buttons)

    # ─── MAIN DASHBOARD ───
    is_channel = config.get('group_type', 'a') == 'c'
    type_indicator = "c" if is_channel else "g"

    # Compute Log Configs indicator: count active log settings out of known log keys
    try:
        log_keys = [
            'start_log_mode', 'start_photo_log_mode', 'progress_log_mode',
            'panel_log_mode', 'interrupted_log', 'delay_log_mode'
        ]
        total_log_keys = len(log_keys)
        active_count = 0
        for k in log_keys:
            v = config.get(k)
            if v is None:
                continue
            # For boolean-like or string modes: consider active if not 'off'
            if isinstance(v, str):
                if v.lower() != 'off':
                    active_count += 1
            elif isinstance(v, bool):
                if v:
                    active_count += 1
            else:
                try:
                    if bool(v):
                        active_count += 1
                except Exception:
                    continue
    except Exception as e:
        logger.error(f"Failed to compute log config indicator: {e}\n{traceback.format_exc()}")
        active_count = 0
        total_log_keys = 6

    buttons = [
        [
            InlineKeyboardButton(f"Acc(s): {sel_count} Sel", callback_data=f"creategroup_submenu_{idx}_{pg}_select_sessions", style=user_style),
            InlineKeyboardButton(f"Delay/Acc: {config.get('account_delay', 0.5)}s", callback_data=f"creategroup_submenu_{idx}_{pg}_account_delay", style=user_style)
        ],
        [
            InlineKeyboardButton(f"B.Acc: {config.get('batch_account', 3)} acc", callback_data=f"creategroup_submenu_{idx}_{pg}_batch_account", style=user_style),
            InlineKeyboardButton(f"B.Acc Delay: {config.get('ba_account_delay', 60)}s", callback_data=f"creategroup_submenu_{idx}_{pg}_ba_account_delay", style=user_style)
        ],
        [
            InlineKeyboardButton(f"Type: {'Group' if not is_channel else 'Channel'}", callback_data=f"creategroup_submenu_{idx}_{pg}_group_type", style=user_style),
            InlineKeyboardButton(f"Count: {config['count']}{type_indicator}", callback_data=f"creategroup_submenu_{idx}_{pg}_count", style=user_style)
        ],
        [
            InlineKeyboardButton(f"Delay/Act: {config['action_delay']}s", callback_data=f"creategroup_submenu_{idx}_{pg}_action_delay", style=user_style),
            InlineKeyboardButton(f"Delay/{'GC' if not is_channel else 'CH'}: {config['delay']}s", callback_data=f"creategroup_submenu_{idx}_{pg}_delay", style=user_style)
        ],
        [
            InlineKeyboardButton(f"B.{'GC' if not is_channel else 'CH'}: {config['batch_size']}{type_indicator}", callback_data=f"creategroup_submenu_{idx}_{pg}_batch_size", style=user_style),
            InlineKeyboardButton(f"B.{'GC' if not is_channel else 'CH'} Delay: {config['batch_delay']}m", callback_data=f"creategroup_submenu_{idx}_{pg}_batch_delay", style=user_style)
        ],
        [
            InlineKeyboardButton(f"B.Act: {config.get('batch_action', 30)} act", callback_data=f"creategroup_submenu_{idx}_{pg}_batch_action", style=user_style),
            InlineKeyboardButton(f"B.Act Delay: {config.get('ba_delay', 30)}s", callback_data=f"creategroup_submenu_{idx}_{pg}_ba_delay", style=user_style)
        ],
        [InlineKeyboardButton(f"Name: {config['pattern'][:25]}...", callback_data=f"creategroup_submenu_{idx}_{pg}_pattern", style=user_style)],
        [InlineKeyboardButton(f"Desc: {config['description'][:25]}...", callback_data=f"creategroup_submenu_{idx}_{pg}_description", style=user_style)],
        [
            InlineKeyboardButton(f"Username: {config['username'] or 'None'}", callback_data=f"creategroup_submenu_{idx}_{pg}_username", style=user_style),
            InlineKeyboardButton(f"Photo: {'Source' if config.get('photo_source') == 'source' else 'Custom'}", callback_data=f"creategroup_submenu_{idx}_{pg}_photo", style=user_style)
        ],
        [
            InlineKeyboardButton(f"Anon Adm: {'Yes' if config['anon_mode'] else 'No'}", callback_data=f"creategroup_toggle_{idx}_{pg}_anon_mode", style=user_style),
            InlineKeyboardButton(f"Copy Msg: {'Yes' if config['copy_messages'] else 'No'}", callback_data=f"creategroup_toggle_{idx}_{pg}_copy_messages", style=user_style)
        ],
        [
            InlineKeyboardButton(f"Invite Bots: {'Yes' if config['invite_bots'] else 'No'}", callback_data=f"creategroup_toggle_{idx}_{pg}_invite_bots", style=user_style),
            InlineKeyboardButton(f"Bots: {len(config['bots'].split() if config['bots'] else [])}", callback_data=f"creategroup_submenu_{idx}_{pg}_bots", style=user_style)
        ],
        [
            InlineKeyboardButton(f"Pin First: {'Yes' if config.get('pin_first_msg', True) else 'No'}", callback_data=f"creategroup_toggle_{idx}_{pg}_pin_first_msg", style=user_style),
            InlineKeyboardButton(f"Temp Pin: {'Yes' if config.get('temp_pin', True) else 'No'}", callback_data=f"creategroup_toggle_{idx}_{pg}_temp_pin", style=user_style)
        ],
        [
            InlineKeyboardButton(f"Quote Block: {'Yes' if config.get('quote_block', True) else 'No'}", callback_data=f"creategroup_toggle_{idx}_{pg}_quote_block", style=user_style),
        ],
        [
            InlineKeyboardButton(f"Msg Img: {'Yes' if config.get('msg_img', True) else 'No'}", callback_data=f"creategroup_toggle_{idx}_{pg}_msg_img", style=user_style),
            InlineKeyboardButton(f"Msg Vid: {'Yes' if config.get('msg_vid', True) else 'No'}", callback_data=f"creategroup_toggle_{idx}_{pg}_msg_vid", style=user_style)
        ],
        [
            InlineKeyboardButton(f"Album Img: {'On' if config.get('msg_img_album', False) else 'Off'}", callback_data=f"creategroup_toggle_{idx}_{pg}_msg_img_album", style=user_style),
            InlineKeyboardButton(f"Album Vid: {'On' if config.get('msg_vid_album', False) else 'Off'}", callback_data=f"creategroup_toggle_{idx}_{pg}_msg_vid_album", style=user_style)
        ],
        [
            InlineKeyboardButton(f"Log Configs: {active_count}/{total_log_keys}", callback_data=f"creategroup_submenu_{idx}_{pg}_log_settings", style=user_style),
            InlineKeyboardButton("All Reports", callback_data=f"creategroup_reports_{idx}_{pg}_1", style=user_style)
        ],
        [
            InlineKeyboardButton("Restore Tasks", callback_data=f"creategroup_cached_{idx}_{pg}", style=user_style),
            InlineKeyboardButton("Info", callback_data=f"creategroup_submenu_{idx}_{pg}_info", style=user_style)
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data=f"creategroup_menu_{idx}_{pg}", style=user_style),
            InlineKeyboardButton("✅ Run Task", callback_data=f"creategroup_run_{idx}_{pg}", style=user_style)
        ]
    ]
    
    return text, InlineKeyboardMarkup(buttons)

async def render_creategroup_ui(cb: Optional[CallbackQuery], state: dict, message: Optional[Message] = None):
    """
    Renders the configuration menu with inline adjustment buttons.
    Displays current settings including delays, counts, batching, and bot lists.
    """
    user_id = cb.from_user.id if cb else (message.from_user.id if message else None)
    if not user_id and state.get("user_id"): user_id = state["user_id"]
    
    text, reply_markup = await get_creategroup_ui_data(user_id, state["session_index"], state["page"])
    
    full_text = f"<b>🚀 𝗔𝗨𝗧𝗢 𝗖𝗥𝗘𝗔𝗧𝗘 𝗗𝗔𝗦𝗛𝗕𝗢𝗔𝗥𝗗</b>\n\n<blockquote expandable>{text}</blockquote>"
    
    try:
        if cb:
            await safe_edit_message_text(cb, full_text, reply_markup=reply_markup)
        elif message:
            try:
                await message.edit(full_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
            except (MessageNotModified, QueryIdInvalid):
                pass
        elif state.get("ui_msg_id") and isinstance(state["ui_msg_id"], str):
            # Inline message edit via Altruix.bot
            from Main.core.client import Altruix
            try:
                await Altruix.bot.edit_inline_message_text(
                    state["ui_msg_id"], 
                    full_text, 
                    reply_markup=reply_markup, 
                    parse_mode=ParseMode.HTML
                )
            except (MessageNotModified, QueryIdInvalid):
                pass
    except Exception: pass

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_adj_(\d+)_(\d+)_(\w+)_([\w.]+)$"))
@iuser_check
@log_errors
async def creategroup_adjust_handler(c: Client, cb: CallbackQuery):
    if not await _callback_debounce(cb):
        await safe_cb_answer(cb, "Tunggu sebentar...", show_alert=False)
        return

    match = cb.matches[0]
    idx, pg, key, action_raw = int(match.group(1)), int(match.group(2)), match.group(3), match.group(4)
    user_id = cb.from_user.id
    
    if user_id not in user_creategroup_state:
        await _ensure_creategroup_ui_state(c, cb, idx, pg)
         
    conf = user_creategroup_state[user_id]["config"]
    steps = {"delay": 10, "count": 1, "batch_delay": 1, "batch_size": 1, "action_delay": 0.5, "account_delay": 0.5, "rand_len": 1, "batch_action": 5, "ba_delay": 10, "batch_account": 1, "ba_account_delay": 10}
    limits = {"delay": (0, 3600), "count": (1, 1000), "batch_delay": (0, 300), "batch_size": (1, 100), "action_delay": (0, 30.0), "account_delay": (0, 30.0), "rand_len": (0, 64), "batch_action": (0, 500), "ba_delay": (0, 3600), "batch_account": (1, 999), "ba_account_delay": (0, 3600)}
    val = conf.get(key, 0)
    
    # Handle extended step actions (sub10, add60, sub0.5 etc)
    import re
    m = re.match(r"(add|sub)([\d.]+)?", action_raw)
    action = m.group(1)
    custom_step = float(m.group(2)) if m.group(2) else None
    
    step = custom_step if custom_step is not None else steps.get(key, 1)
    val = val + step if action == "add" else val - step
    min_v, max_v = limits.get(key, (0, 100))
    final_val = max(min_v, min(val, max_v))
    
    # 🔥 CRITICAL FIX: Ensure specific keys don't become floats (User requested ONLY 'count')
    int_keys = ["count", "batch_account", "ba_account_delay"]
    if key in int_keys:
        final_val = int(round(final_val))
        
    conf[key] = final_val
    save_user_cg_config(user_id, conf)
    await render_creategroup_ui(cb, user_creategroup_state[user_id])
    await cb.answer()

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_submenu_(\d+)_(\d+)_(\w+)$"))
@iuser_check
@log_errors
async def creategroup_submenu_handler(c: Client, cb: CallbackQuery):
    idx, pg, field = int(cb.matches[0].group(1)), int(cb.matches[0].group(2)), cb.matches[0].group(3)
    user_id = cb.from_user.id
    if user_id not in user_creategroup_state:
        await _ensure_creategroup_ui_state(c, cb, idx, pg)
    user_creategroup_state[user_id]["sub_menu"] = field
    await render_creategroup_ui(cb, user_creategroup_state[user_id])
    await cb.answer()

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_back_submenu_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_back_submenu_handler(c: Client, cb: CallbackQuery):
    idx, pg = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    user_id = cb.from_user.id
    if user_id not in user_creategroup_state:
        await _ensure_creategroup_ui_state(c, cb, idx, pg)
    user_creategroup_state[user_id]["sub_menu"] = None
    await render_creategroup_ui(cb, user_creategroup_state[user_id])
    await cb.answer()

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_tsel_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_session_toggle_handler(c: Client, cb: CallbackQuery):
    if not await _callback_debounce(cb, interval=0.3):
        await safe_cb_answer(cb, "Sabar...", show_alert=False)
        return

    s_idx, pg = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    user_id = cb.from_user.id
    if user_id not in user_creategroup_state:
        idx = await _resolve_cg_session_index_from_cb(cb, fallback_idx=s_idx)
        await _ensure_creategroup_ui_state(c, cb, idx, pg)

    state = user_creategroup_state[user_id]
    state.setdefault("session_page", 0)
    
    # Use a set for efficient and clean toggling
    current_selected = state.get("selected_sessions", [])
    if not isinstance(current_selected, list):
        current_selected = [state.get("session_index", s_idx)]
        
    selected_set = set()
    for x in current_selected:
        try: selected_set.add(int(x))
        except: pass
    
    if s_idx in selected_set:
        selected_set.remove(s_idx)
    else:
        selected_set.add(s_idx)

    state["selected_sessions"] = sorted(list(selected_set))
    await render_creategroup_ui(cb, state)
    await cb.answer()

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_spage_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_session_page_handler(c: Client, cb: CallbackQuery):
    if not await _callback_debounce(cb, interval=0.3):
        await cb.answer()
        return
        
    s_page, pg = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    user_id = cb.from_user.id
    if user_id not in user_creategroup_state:
        idx = await _resolve_cg_session_index_from_cb(cb, fallback_idx=1)
        await _ensure_creategroup_ui_state(c, cb, idx, pg, session_page=s_page)
    user_creategroup_state[user_id]["session_page"] = s_page
    await render_creategroup_ui(cb, user_creategroup_state[user_id])
    await cb.answer()


@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_filter_(\w+)_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_filter_handler(c: Client, cb: CallbackQuery):
    try:
        mode = cb.matches[0].group(1)
        idx = int(cb.matches[0].group(2))
        pg = int(cb.matches[0].group(3))
        user_id = cb.from_user.id
        if user_id not in user_creategroup_state:
            await _ensure_creategroup_ui_state(c, cb, idx, pg)

        state = user_creategroup_state[user_id]
        conf = state.get("config") or load_user_cg_config(user_id)
        if mode not in ("all", "newest", "oldest"):
            await safe_cb_answer(cb, "Unknown filter mode", show_alert=True)
            return

        conf["account_filter"] = mode
        save_user_cg_config(user_id, conf)
        state["config"] = conf
        await render_creategroup_ui(cb, state)
        await cb.answer()
    except Exception as e:
        logger.error(f"Error in creategroup_filter_handler: {e}\n{traceback.format_exc()}")
        await safe_cb_answer(cb, "❌ Error applying filter", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_sall_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_session_select_all_handler(c: Client, cb: CallbackQuery):
    if not await _callback_debounce(cb, interval=0.5):
        await cb.answer()
        return
        
    s_page, pg = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    user_id = cb.from_user.id
    if user_id not in user_creategroup_state:
        idx = await _resolve_cg_session_index_from_cb(cb, fallback_idx=1)
        await _ensure_creategroup_ui_state(c, cb, idx, pg, session_page=s_page)
    state = user_creategroup_state[user_id]
    state.setdefault("session_page", s_page)
    state["selected_sessions"] = list(range(1, len(Altruix.clients) + 1))
    await render_creategroup_ui(cb, state)
    await cb.answer("All sessions selected")

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_selp_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_session_select_page_handler(c: Client, cb: CallbackQuery):
    try:
        s_page, pg = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
        user_id = cb.from_user.id
        if user_id not in user_creategroup_state:
            idx = await _resolve_cg_session_index_from_cb(cb, fallback_idx=1)
            await _ensure_creategroup_ui_state(c, cb, idx, pg, session_page=s_page)

        state = user_creategroup_state[user_id]
        state["session_page"] = s_page

        per_page = 5
        total_sessions = len(Altruix.clients)

        # Prefer using the last rendered paged indices if available (handles filtered ordering)
        last_page_indices = state.get("last_paged_indices") or []
        if last_page_indices and state.get("session_page") == s_page:
            page_indices = list(last_page_indices)
        else:
            start = max(0, s_page) * per_page
            end = min(start + per_page, total_sessions)
            page_indices = list(range(start + 1, end + 1))
        selected = state.get("selected_sessions", []) or []

        merged = set(selected)
        merged.update(page_indices)
        state["selected_sessions"] = sorted(merged)

        await render_creategroup_ui(cb, state)
        await safe_cb_answer(cb, "Page selected", show_alert=False)
    except Exception as e:
        logger.error(f"Error in creategroup_session_select_page_handler: {e}\n{traceback.format_exc()}")
        await safe_cb_answer(cb, "❌ Error select page", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_dsall_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_session_deselect_all_handler(c: Client, cb: CallbackQuery):
    if not await _callback_debounce(cb, interval=0.5):
        await cb.answer()
        return
        
    s_page, pg = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    user_id = cb.from_user.id
    if user_id not in user_creategroup_state:
        idx = await _resolve_cg_session_index_from_cb(cb, fallback_idx=1)
        await _ensure_creategroup_ui_state(c, cb, idx, pg, session_page=s_page)
    state = user_creategroup_state[user_id]
    state.setdefault("session_page", s_page)
    state["selected_sessions"] = []
    await render_creategroup_ui(cb, state)
    await cb.answer("All sessions deselected")

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_dselp_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_session_deselect_page_handler(c: Client, cb: CallbackQuery):
    try:
        s_page, pg = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
        user_id = cb.from_user.id
        if user_id not in user_creategroup_state:
            idx = await _resolve_cg_session_index_from_cb(cb, fallback_idx=1)
            await _ensure_creategroup_ui_state(c, cb, idx, pg, session_page=s_page)

        state = user_creategroup_state[user_id]
        state["session_page"] = s_page

        per_page = 5
        total_sessions = len(Altruix.clients)

        # Prefer using the last rendered paged indices if available (handles filtered ordering)
        last_page_indices = state.get("last_paged_indices") or []
        if last_page_indices and state.get("session_page") == s_page:
            page_indices = set(last_page_indices)
        else:
            start = max(0, s_page) * per_page
            end = min(start + per_page, total_sessions)
            page_indices = set(range(start + 1, end + 1))
        selected = state.get("selected_sessions", []) or []
        state["selected_sessions"] = [x for x in selected if x not in page_indices]

        await render_creategroup_ui(cb, state)
        await cb.answer("Page deselected")
    except Exception as e:
        logger.error(f"Error in creategroup_session_deselect_page_handler: {e}\n{traceback.format_exc()}")
        await safe_cb_answer(cb, "❌ Error deselect page", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_setv_(\d+)_(\d+)_(\w+)_(\w+)$"))
@iuser_check
@log_errors
async def creategroup_set_val_handler(c: Client, cb: CallbackQuery):
    if not await _callback_debounce(cb):
        await safe_cb_answer(cb, "Tunggu sebentar...", show_alert=False)
        return

    idx, pg, key, val_raw = int(cb.matches[0].group(1)), int(cb.matches[0].group(2)), cb.matches[0].group(3), cb.matches[0].group(4)
    user_id = cb.from_user.id
    if user_id not in user_creategroup_state:
        await _ensure_creategroup_ui_state(c, cb, idx, pg)
    
    val = None if val_raw == "none" else val_raw
    if key == "bots" and val_raw == "default":
        val = DEFAULT_CREATEGROUP_CONFIG["bots"]
        
    user_creategroup_state[user_id]["config"][key] = val
    save_user_cg_config(user_id, user_creategroup_state[user_id]["config"])
    await render_creategroup_ui(cb, user_creategroup_state[user_id])
    await cb.answer(f"Updated {key} to {val_raw}")

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_in_(\d+)_(\d+)_(\w+)$"))
@iuser_check
@log_errors
async def creategroup_input_request(c: Client, cb: CallbackQuery):
    if not await _callback_debounce(cb):
        await safe_cb_answer(cb, "Tunggu sebentar...", show_alert=False)
        return

    await cb.answer()
    idx, pg, field = int(cb.matches[0].group(1)), int(cb.matches[0].group(2)), cb.matches[0].group(3)
    user_id = cb.from_user.id
    if user_id not in user_creategroup_state:
        await _ensure_creategroup_ui_state(c, cb, idx, pg)
    
    from Main.internals.settings_handlers.custom_alert_handlers import _get_session_user_id
    session_user_id = _get_session_user_id(idx)
    user_style = get_user_button_style(session_user_id)
    
    # Preserve ui_msg_id if it's already an inline ID (string) and cb.message is missing
    current_ui_msg_id = user_creategroup_state[user_id].get("ui_msg_id")
    new_ui_msg_id = cb.message.id if cb.message else (current_ui_msg_id if isinstance(current_ui_msg_id, str) else None)
    
    user_creategroup_state[user_id].update({
        "input_mode": field, 
        "step": "awaiting_input", 
        "ui_msg_id": new_ui_msg_id, 
        "ui_chat_id": cb.message.chat.id if cb.message else user_creategroup_state[user_id].get("ui_chat_id"),
        "session_index": idx, # Ensure session index is current
        "page": pg # Ensure page is current
    })
    field_name = {"pattern": "Group Name Pattern", "username": "Username Prefix", "bots": "Bot Usernames List", "description": "Group Description"}.get(field, field.replace("_", " ").title())
    text = f"<b>📝 Memproses Input: {field_name}...</b>\n\nSilakan lihat instruksi detail pada pesan baru di bawah ini."
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data=f"creategroup_ui_{idx}_{pg}", style=user_style)]])
    
    await safe_edit_message_text(cb, text, reply_markup=kb)
    chat_id = cb.message.chat.id if cb.message else cb.from_user.id
        
    # Build detailed prompt instructions
    if field == "bots":
        prompt_text = (
            "<b>✏️ Input Bot Usernames List</b>\n\n"
            f"<b>Current Bots:</b>\n<code>{html.escape(user_creategroup_state[user_id]['config']['bots'] or 'None')}</code>\n\n"
            "Kirim daftar username bot yang ingin Anda undang ke grup baru, <b>pisahkan dengan spasi</b>.\n\n"
            "<b>Contoh:</b>\n<code>@MissRose_bot @simixbot @Spillgame_bot @GroupHelpBot</code>\n\n"
            "<i>Ketik /cancel untuk membatalkan.</i>"
        )
    elif field == "pattern":
        prompt_text = (
            "<b>✏️ Input Group Name Pattern</b>\n\n"
            f"<b>Current Pattern:</b> <code>{html.escape(user_creategroup_state[user_id]['config']['pattern'])}</code>\n\n"
            "Kirim pola nama yang akan digunakan untuk grup baru. Gunakan placeholder berikut:\n"
            "• <code>(index)</code> : Urutan angka\n"
            "• <code>(tahun)</code> : 2 digit tahun\n"
            "• <code>(bulan)</code> : Angka bulan\n"
            "• <code>(tanggal)</code>: Angka tanggal\n\n"
            "<b>Contoh:</b> <code>Altruix Project (tanggal)-(bulan) (index)</code>\n\n"
            "<i>Ketik /cancel untuk membatalkan.</i>"
        )
    elif field == "username":
        prompt_text = (
            "<b>✏️ Input Username Prefix</b>\n\n"
            f"<b>Current:</b> <code>{html.escape(user_creategroup_state[user_id]['config']['username'] or 'None')}</code>\n\n"
            "Kirim awalan username (tanpa @) untuk grup publik, atau <b>'none'</b> untuk menjadikannya grup private.\n\n"
            "<b>Contoh:</b> <code>MyXProject</code>\n\n"
            "<i>Ketik /cancel untuk membatalkan.</i>"
        )
    else:
        prompt_text = (
            f"<b>✏️ Input {field_name}</b>\n\n"
            "Silakan kirim teks yang diinginkan.\n\n"
            "<i>Ketik /cancel untuk membatalkan.</i>"
        )

    try:
        prompt_msg = await c.send_message(chat_id, prompt_text, parse_mode=ParseMode.HTML)
        user_creategroup_state[user_id]["prompt_msg_id"] = prompt_msg.id
    except Exception as e:
        logger.error(f"Failed to send prompt in creategroup: {e}")

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_toggle_(\d+)_(\d+)_(\w+)$"))
@iuser_check
@log_errors
async def creategroup_toggle_handler(c: Client, cb: CallbackQuery):
    if not await _callback_debounce(cb):
        await safe_cb_answer(cb, "Tunggu sebentar...", show_alert=False)
        return

    idx, pg, key = int(cb.matches[0].group(1)), int(cb.matches[0].group(2)), cb.matches[0].group(3)
    user_id = cb.from_user.id
    if user_id in user_creategroup_state:
        if user_creategroup_state[user_id].get("prompt_msg_id"):
            try:
                if cb.message:
                    await c.delete_messages(cb.message.chat.id, user_creategroup_state[user_id]["prompt_msg_id"])
            except: pass
            user_creategroup_state[user_id]["prompt_msg_id"] = None
        conf = user_creategroup_state[user_id]["config"]
        if key == "photo_source": conf["photo_source"] = "custom" if conf.get("photo_source") == "source" else "source"
        elif key == "log_destination":
            curr = conf.get("log_destination", "both")
            if curr == "log_group": conf["log_destination"] = "saved_messages"
            elif curr == "saved_messages": conf["log_destination"] = "both"
            else: conf["log_destination"] = "log_group"
        elif key == "interrupted_log":
            curr = conf.get("interrupted_log", "off")
            if curr == "both": conf["interrupted_log"] = "log_group"
            elif curr == "log_group": conf["interrupted_log"] = "pm_bot"
            elif curr == "pm_bot": conf["interrupted_log"] = "off"
            else: conf["interrupted_log"] = "both"
        elif key == "start_log_mode":
            curr = conf.get("start_log_mode", "both")
            if curr == "both": conf["start_log_mode"] = "log_group"
            elif curr == "log_group": conf["start_log_mode"] = "pm_bot"
            elif curr == "pm_bot": conf["start_log_mode"] = "off"
            else: conf["start_log_mode"] = "both"
        elif key == "start_photo_log_mode":
            curr = conf.get("start_photo_log_mode", "both")
            if curr == "both": conf["start_photo_log_mode"] = "log_group"
            elif curr == "log_group": conf["start_photo_log_mode"] = "pm_bot"
            elif curr == "pm_bot": conf["start_photo_log_mode"] = "off"
            else: conf["start_photo_log_mode"] = "both"
        elif key in ["progress_log_mode", "panel_log_mode", "delay_log_mode"]:
            curr = conf.get(key, "both" if key != "panel_log_mode" else "log_group")
            if curr == "both": conf[key] = "log_group"
            elif curr == "log_group": conf[key] = "pm_bot"
            elif curr == "pm_bot": conf[key] = "off"
            else: conf[key] = "both"
        elif key == "log_format": conf["log_format"] = "zip" if conf.get("log_format", "txt") == "txt" else "txt"
        elif key == "msg_img": conf["msg_img"] = not conf.get("msg_img", True)
        elif key == "msg_vid": conf["msg_vid"] = not conf.get("msg_vid", True)
        elif key == "msg_img_album": conf["msg_img_album"] = not conf.get("msg_img_album", False)
        elif key == "msg_vid_album": conf["msg_vid_album"] = not conf.get("msg_vid_album", False)
        elif key in conf: conf[key] = not conf[key]
        save_user_cg_config(user_id, conf)
        await render_creategroup_ui(cb, user_creategroup_state[user_id])
    await cb.answer()

# ─── CREATION REPORTS SUBMENU [NEW] ───

def load_creation_report() -> dict:
    from Main.utils.file_helpers import get_db_path
    import json
    import os
    
    file_path = get_db_path("xcreategroup_created_report.json")
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load creation report json: {e}")
    return {}

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_reports_(\d+)_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_reports_handler(c: Client, cb: CallbackQuery):
    try:
        try:
            await cb.answer()
        except Exception:
            pass
        
        session_index = int(cb.matches[0].group(1))
        page = int(cb.matches[0].group(2))
        report_page = int(cb.matches[0].group(3))
        
        from Main.internals.settings_handlers.custom_alert_handlers import _get_session_user_id
        session_user_id = _get_session_user_id(session_index)
        user_style = get_user_button_style(session_user_id)
        
        # Sync first in case of new completed tasks in the background
        try:
            from Main.plugins.userbot.xcreategroup import sync_existing_created_groups
            await sync_existing_created_groups()
        except Exception as se:
            logger.warning(f"Failed to sync created groups: {se}")
            
        report_data = load_creation_report()
        
        if not report_data:
            text = "<blockquote expandable><b>📊 Creation Reports</b>\n\n<i>Belum ada data group/channel yang berhasil dibuat oleh akun mana pun.</i></blockquote>"
            buttons = [[InlineKeyboardButton("🔙 Back", callback_data=f"creategroup_ui_{session_index}_{page}", style=user_style)]]
            return await safe_edit_message_text(cb, text, reply_markup=InlineKeyboardMarkup(buttons))
            
        accounts_list = sorted(list(report_data.items()), key=lambda x: len(x[1].get("created_groups", [])), reverse=True)
        total_accounts = len(accounts_list)
        limit = 5
        total_pages = (total_accounts + limit - 1) // limit
        report_page = max(1, min(report_page, total_pages))
        
        start = (report_page - 1) * limit
        end = start + limit
        current_accounts = accounts_list[start:end]
        
        lines = []
        buttons = []
        
        total_all_created = sum(len(acc[1].get("created_groups", [])) for acc in accounts_list)
        lines.append(f"<b>Total Keseluruhan:</b> {total_all_created} group/channel\n")
        lines.append("Pilih akun di bawah untuk melihat detail group/channel yang berhasil dibuat:\n")
        
        for acc_id, acc_info in current_accounts:
            acc_name = acc_info.get("account_name", "Unknown Account")
            grps = acc_info.get("created_groups", [])
            total_created = len(grps)
            
            channels_count = sum(1 for g in grps if g.get("type") == "c")
            groups_count = total_created - channels_count
            
            detail_desc = []
            if groups_count > 0: detail_desc.append(f"{groups_count} grup")
            if channels_count > 0: detail_desc.append(f"{channels_count} channel")
            detail_str = " (" + ", ".join(detail_desc) + ")" if detail_desc else ""
            
            lines.append(f"• <b>{acc_name}</b>: {total_created} dibuat{detail_str}")
            
            buttons.append([
                InlineKeyboardButton(f"👤 {acc_name[:20]} ({total_created})", callback_data=f"creategroup_repdet_{session_index}_{page}_{acc_id}_1", style=user_style)
            ])
            
        text = f"<blockquote expandable><b>📊 Creation Reports [{report_page}/{total_pages}]</b>\n\n" + "\n".join(lines) + "\n\n<i>Klik akun untuk melihat detail lengkap atau mengekspor log.</i></blockquote>"
        
        buttons.append([
            InlineKeyboardButton("📤 Export All Reports", callback_data=f"creategroup_repexp_all_{session_index}_{page}", style=user_style)
        ])
        
        nav = []
        if report_page > 1:
            nav.append(InlineKeyboardButton("« Prev", callback_data=f"creategroup_reports_{session_index}_{page}_{report_page-1}", style=user_style))
        else:
            nav.append(InlineKeyboardButton("« Prev", callback_data="noop", style=user_style))
            
        nav.append(InlineKeyboardButton(f"{report_page}/{total_pages}", callback_data="noop", style=user_style))
        
        if report_page < total_pages:
            nav.append(InlineKeyboardButton("Next »", callback_data=f"creategroup_reports_{session_index}_{page}_{report_page+1}", style=user_style))
        else:
            nav.append(InlineKeyboardButton("Next »", callback_data="noop", style=user_style))
            
        buttons.append(nav)
        
        # First / Last Navigation
        if total_pages > 1:
            buttons.append([
                InlineKeyboardButton("First", callback_data=f"creategroup_reports_{session_index}_{page}_1", style=user_style),
                InlineKeyboardButton("Last", callback_data=f"creategroup_reports_{session_index}_{page}_{total_pages}", style=user_style)
            ])
            
        buttons.append([InlineKeyboardButton("🔙 Back to Dashboard", callback_data=f"creategroup_ui_{session_index}_{page}", style=user_style)])
        
        await safe_edit_message_text(cb, text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        logger.error(f"Error in creategroup_reports_handler: {e}\n{traceback.format_exc()}")
        try:
            await cb.answer(f"❌ Error: {e}", show_alert=True)
        except Exception:
            pass


@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_repdet_(\d+)_(\d+)_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_report_detail_handler(c: Client, cb: CallbackQuery):
    try:
        try:
            await cb.answer()
        except Exception:
            pass
        
        session_index = int(cb.matches[0].group(1))
        page = int(cb.matches[0].group(2))
        target_account_id = cb.matches[0].group(3)
        detail_page = int(cb.matches[0].group(4))
        
        from Main.internals.settings_handlers.custom_alert_handlers import _get_session_user_id
        session_user_id = _get_session_user_id(session_index)
        user_style = get_user_button_style(session_user_id)
        
        report_data = load_creation_report()
        acc_info = report_data.get(target_account_id)
        
        if not acc_info:
            text = "<blockquote expandable><b>❌ Error</b>\n\nData untuk akun ini tidak ditemukan.</blockquote>"
            buttons = [[InlineKeyboardButton("🔙 Back", callback_data=f"creategroup_reports_{session_index}_{page}_1", style=user_style)]]
            return await safe_edit_message_text(cb, text, reply_markup=InlineKeyboardMarkup(buttons))
            
        acc_name = acc_info.get("account_name", "Unknown Account")
        username = acc_info.get("username", "")
        grps = acc_info.get("created_groups", [])
        total_created = len(grps)
        
        limit = 5
        total_pages = (total_created + limit - 1) // limit
        detail_page = max(1, min(detail_page, total_pages))
        
        start = (detail_page - 1) * limit
        end = start + limit
        current_grps = grps[start:end]
        
        lines = []
        lines.append(f"👤 <b>Akun:</b> {acc_name}" + (f" (@{username})" if username else ""))
        lines.append(f"🆔 <b>ID Akun:</b> <code>{target_account_id}</code>")
        lines.append(f"📈 <b>Total Dibuat:</b> {total_created} group/channel\n")
        
        for idx, g in enumerate(current_grps, start + 1):
            g_type = "Channel" if g.get("type") == "c" else "Grup"
            name = g.get("name", "N/A")
            link = g.get("link", "N/A")
            c_id = g.get("id", "N/A")
            time_str = g.get("time", "N/A")
            task_id = g.get("task_id", "N/A")
            
            link_str = f"<a href='{link}'>{link}</a>" if link and link != "N/A" else "N/A"
            lines.append(
                f"{idx}. <b>{name}</b> ({g_type})\n"
                f"   • ID: <code>{c_id}</code> | Task: <code>{task_id}</code>\n"
                f"   • Link: {link_str}\n"
                f"   • Waktu: {time_str}"
            )
            
        text = f"<blockquote expandable><b>📊 Detail Laporan Dibuat [{detail_page}/{total_pages}]</b>\n\n" + "\n".join(lines) + "\n\n<i>Anda dapat mengekspor seluruh log akun ini ke file .txt menggunakan tombol di bawah.</i></blockquote>"
        
        buttons = [
            [
                InlineKeyboardButton("📥 Export This Account Log", callback_data=f"creategroup_repexp_acc_{session_index}_{page}_{target_account_id}", style=user_style)
            ]
        ]
        
        nav = []
        if detail_page > 1:
            nav.append(InlineKeyboardButton("« Prev", callback_data=f"creategroup_repdet_{session_index}_{page}_{target_account_id}_{detail_page-1}", style=user_style))
        else:
            nav.append(InlineKeyboardButton("« Prev", callback_data="noop", style=user_style))
            
        nav.append(InlineKeyboardButton(f"{detail_page}/{total_pages}", callback_data="noop", style=user_style))
        
        if detail_page < total_pages:
            nav.append(InlineKeyboardButton("Next »", callback_data=f"creategroup_repdet_{session_index}_{page}_{target_account_id}_{detail_page+1}", style=user_style))
        else:
            nav.append(InlineKeyboardButton("Next »", callback_data="noop", style=user_style))
            
        buttons.append(nav)
        
        # First / Last Navigation
        if total_pages > 1:
            buttons.append([
                InlineKeyboardButton("First", callback_data=f"creategroup_repdet_{session_index}_{page}_{target_account_id}_1", style=user_style),
                InlineKeyboardButton("Last", callback_data=f"creategroup_repdet_{session_index}_{page}_{target_account_id}_{total_pages}", style=user_style)
            ])
            
        buttons.append([InlineKeyboardButton("🔙 Back to Reports List", callback_data=f"creategroup_reports_{session_index}_{page}_1", style=user_style)])
        
        await safe_edit_message_text(cb, text, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Error in creategroup_report_detail_handler: {e}\n{traceback.format_exc()}")
        try:
            await cb.answer(f"❌ Error: {e}", show_alert=True)
        except Exception:
            pass


@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_repexp_acc_(\d+)_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_report_export_acc_handler(c: Client, cb: CallbackQuery):
    await cb.answer("Generating report...", show_alert=False)
    
    import tempfile
    import os
    from datetime import datetime
    
    session_index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    target_account_id = cb.matches[0].group(3)
    
    report_data = load_creation_report()
    acc_info = report_data.get(target_account_id)
    
    if not acc_info:
        await cb.answer("❌ Data tidak ditemukan!", show_alert=True)
        return
        
    acc_name = acc_info.get("account_name", "Unknown Account")
    username = acc_info.get("username", "")
    grps = acc_info.get("created_groups", [])
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"report_creation_{target_account_id}_{timestamp}.txt"
    temp_path = os.path.join(tempfile.gettempdir(), filename)
    
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(f"AltruixX - LAPORAN DETAIL GROUP/CHANNEL YANG BERHASIL DIBUAT\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"AKUN: {acc_name}" + (f" (@{username})" if username else "") + "\n")
            f.write(f"ID AKUN: {target_account_id}\n")
            f.write(f"TOTAL YANG BERHASIL DIBUAT: {len(grps)} group/channel\n")
            f.write(f"WAKTU EXPORT: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write(f"DAFTAR DETAIL:\n")
            f.write("-" * 60 + "\n\n")
            
            for idx, g in enumerate(grps, 1):
                g_type = "Channel" if g.get("type") == "c" else "Grup"
                f.write(
                    f"{idx}. {g.get('name', 'N/A')} ({g_type})\n"
                    f"   • ID: {g.get('id', 'N/A')}\n"
                    f"   • Link: {g.get('link', 'N/A')}\n"
                    f"   • Task ID: {g.get('task_id', 'N/A')}\n"
                    f"   • Waktu Pembuatan: {g.get('time', 'N/A')}\n\n"
                )
                
            f.write("=" * 60 + "\n")
            f.write("Powered by AltruixX Engine\n")
            
        await c.send_document(
            chat_id=cb.message.chat.id if cb.message else cb.from_user.id,
            document=temp_path,
            caption=f"📊 <b>Laporan Pembuatan Akun: {acc_name}</b>\n\nBerhasil diekspor.",
            parse_mode=ParseMode.HTML
        )
        await cb.answer("✅ Report berhasil dikirim!", show_alert=True)
    except Exception as e:
        logger.error(f"Failed to export account report: {e}\n{traceback.format_exc()}")
        await cb.answer(f"❌ Gagal mengekspor report: {e}", show_alert=True)
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_repexp_all_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_report_export_all_handler(c: Client, cb: CallbackQuery):
    await cb.answer("Generating master report...", show_alert=False)
    
    import tempfile
    import os
    from datetime import datetime
    
    session_index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    
    report_data = load_creation_report()
    
    if not report_data:
        await cb.answer("❌ Tidak ada data untuk diekspor!", show_alert=True)
        return
        
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"report_creation_all_accounts_{timestamp}.txt"
    temp_path = os.path.join(tempfile.gettempdir(), filename)
    
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(f"AltruixX - LAPORAN MASTER PEMBUATAN GROUP/CHANNEL KESELURUHAN\n")
            f.write("=" * 60 + "\n\n")
            
            total_all_created = sum(len(acc_info.get("created_groups", [])) for acc_info in report_data.values())
            f.write(f"TOTAL AKUN TEREPESENTASI: {len(report_data)}\n")
            f.write(f"TOTAL KESELURUHAN GROUP/CHANNEL: {total_all_created}\n")
            f.write(f"WAKTU EXPORT: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("RINGKASAN PER-AKUN:\n")
            f.write("-" * 30 + "\n")
            for acc_id, acc_info in report_data.items():
                acc_name = acc_info.get("account_name", "Unknown Account")
                total = len(acc_info.get("created_groups", []))
                f.write(f"• {acc_name} ({acc_id}): {total} group/channel\n")
            f.write("\n" + "=" * 60 + "\n\n")
            
            for acc_id, acc_info in report_data.items():
                acc_name = acc_info.get("account_name", "Unknown Account")
                username = acc_info.get("username", "")
                grps = acc_info.get("created_groups", [])
                
                f.write(f"👤 AKUN: {acc_name}" + (f" (@{username})" if username else "") + f" | ID: {acc_id}\n")
                f.write(f"TOTAL DIBUAT: {len(grps)} group/channel\n")
                f.write("-" * 60 + "\n")
                
                for idx, g in enumerate(grps, 1):
                    g_type = "Channel" if g.get("type") == "c" else "Grup"
                    f.write(
                        f"   {idx}. {g.get('name', 'N/A')} ({g_type})\n"
                        f"      • ID: {g.get('id', 'N/A')}\n"
                        f"      • Link: {g.get('link', 'N/A')}\n"
                        f"      • Task ID: {g.get('task_id', 'N/A')}\n"
                        f"      • Waktu: {g.get('time', 'N/A')}\n\n"
                    )
                f.write("=" * 60 + "\n\n")
                
            f.write("Powered by AltruixX Engine\n")
            
        await c.send_document(
            chat_id=cb.message.chat.id if cb.message else cb.from_user.id,
            document=temp_path,
            caption=f"📊 <b>Laporan Master Pembuatan Grup/Channel Keseluruhan</b>\n\nTotal {total_all_created} group/channel berhasil diekspor dari {len(report_data)} akun.",
            parse_mode=ParseMode.HTML
        )
        await cb.answer("✅ Master Report berhasil dikirim!", show_alert=True)
    except Exception as e:
        logger.error(f"Failed to export master report: {e}\n{traceback.format_exc()}")
        await cb.answer(f"❌ Gagal mengekspor report: {e}", show_alert=True)
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

    await cb.answer()

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_upload_photo_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_upload_photo_handler(c: Client, cb: CallbackQuery):
    if not await _callback_debounce(cb):
        await safe_cb_answer(cb, "Tunggu sebentar...", show_alert=False)
        return

    idx, pg, user_id = int(cb.matches[0].group(1)), int(cb.matches[0].group(2)), cb.from_user.id
    if user_id not in user_creategroup_state:
        await _ensure_creategroup_ui_state(c, cb, idx, pg)
        
    from Main.internals.settings_handlers.custom_alert_handlers import _get_session_user_id
    session_user_id = _get_session_user_id(idx)
    user_style = get_user_button_style(session_user_id)
    
    user_creategroup_state[user_id].update({"step": "awaiting_photo", "input_mode": "custom_photo", "ui_msg_id": cb.message.id if cb.message else None})
    text = "<b>📸 Awaiting Photo Upload...</b>\n\nSilakan lihat instruksi pada pesan di bawah."
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data=f"creategroup_ui_{idx}_{pg}", style=user_style)]])
    
    if cb.message:
        await cb.message.edit(text, reply_markup=kb)
        chat_id = cb.message.chat.id
    else:
        await cb.edit_message_text(text, reply_markup=kb)
        chat_id = cb.from_user.id
        
    try:
        prompt_msg = await c.send_message(chat_id, "<b>📸 Upload Custom Photo</b>\n\nSilakan kirim atau reply pesan ini dengan foto yang ingin dijadikan profil grup.\nKetik /cancel untuk membatalkan.", parse_mode=ParseMode.HTML)
        user_creategroup_state[user_id]["prompt_msg_id"] = prompt_msg.id
    except Exception as e:
        logger.error(f"Failed to send photo prompt in creategroup: {e}")
    finally:
        await cb.answer()

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_run_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_run_handler(c: Client, cb: CallbackQuery):
    if not await _callback_debounce(cb):
        await safe_cb_answer(cb, "Tunggu sebentar...", show_alert=False)
        return

    idx, pg, user_id = int(cb.matches[0].group(1)), int(cb.matches[0].group(2)), cb.from_user.id
    if user_id not in user_creategroup_state or "config" not in user_creategroup_state[user_id]:
        await _ensure_creategroup_ui_state(c, cb, idx, pg)
        
    from Main.internals.settings_handlers.custom_alert_handlers import _get_session_user_id
    session_user_id = _get_session_user_id(idx)
    user_style = get_user_button_style(session_user_id)
    
    state = user_creategroup_state[user_id]
    selected = state.get("selected_sessions", [])
    if not selected:
        state["sub_menu"] = "select_sessions"
        await render_creategroup_ui(cb, state)
        await safe_cb_answer(cb, "⚠️ Pilih minimal 1 akun dulu.", show_alert=True)
        return

    sel_count = len(selected)
    
    conf = user_creategroup_state[user_id]["config"]
    photo_text = ("👤 Source Account" if conf.get('photo_source') == 'source' else "🖼 Custom Photo") + (" ✅" if conf.get('photo_source') == 'custom' and conf.get('custom_photo_id') else "")
    type_lbl = "Supergroup" if conf.get('group_type', 'a') == 'a' else "Channel"
    _mode_labels = {'both': 'Both', 'log_group': 'Group Log', 'pm_bot': 'PM Bot', 'off': 'Off'}
    prog_lbl = _mode_labels.get(conf.get("progress_log_mode", "both"), "Both")
    pnl_lbl = _mode_labels.get(conf.get("panel_log_mode", "log_group"), "Group Log")
    text = (
        f"<blockquote expandable>"
        f"<b>⚠️ Task Create {type_lbl} Confirmation</b>\n\n"
        f"• <b>Type:</b> {type_lbl}\n"
        f"• <b>Pattern:</b> {html.escape(conf['pattern'])}\n"
        f"• <b>Count:</b> {conf['count']} {type_lbl} / Account\n"
        f"• <b>Accounts:</b> <code>{sel_count}</code> selected\n"
        f"• <b>Anon Admin:</b> {'Yes' if conf['anon_mode'] else 'No'}\n"
        f"• <b>Photo Source:</b> {photo_text}\n"
        f"• <b>Description:</b> {html.escape(conf.get('description', ''))}\n"
        f"• <b>Invite Bots:</b> {'Yes' if conf['invite_bots'] else 'No'} ({len(conf['bots'].split() if conf['bots'] else [])})\n"
        f"• <b>Pin First Msg:</b> {'Yes' if conf.get('pin_first_msg', True) else 'No'}\n"
        f"• <b>Log Destination:</b> {'📡 Both' if conf.get('log_destination', 'both') == 'both' else ('📡 Group Log' if conf.get('log_destination') == 'log_group' else '📥 Saved Messages')}\n\n"
        f"• <b>Progress Log:</b> <code>{prog_lbl}</code> | <b>Panel Log:</b> <code>{pnl_lbl}</code>\n\n"
        f"Apakah Anda yakin ingin menjalankan task ini di <b>{sel_count} akun</b>?"
        f"</blockquote>"
    )
    buttons = [[InlineKeyboardButton("❌ Batal", callback_data=f"creategroup_ui_{idx}_{pg}", style=user_style), InlineKeyboardButton("✅ Ya, Jalankan", callback_data=f"creategroup_confirm_task_{idx}", style=user_style)]]
    await safe_edit_message_text(cb, text, reply_markup=InlineKeyboardMarkup(buttons))
    await cb.answer()

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_confirm_task_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_confirm_task_handler(c: Client, cb: CallbackQuery):
    if not await _callback_debounce(cb):
        await safe_cb_answer(cb, "Tunggu sebentar...", show_alert=False)
        return

    user_id = None  # ✅ FIX: Init before try to prevent NameError in outer except
    try:
        idx, user_id = int(cb.matches[0].group(1)), cb.from_user.id
        if user_id not in user_creategroup_state or "config" not in user_creategroup_state[user_id]:
            await _ensure_creategroup_ui_state(c, cb, idx, user_creategroup_state.get(user_id, {}).get("page", 1))
        state = user_creategroup_state[user_id]
        if state.get("launching"):
            await cb.answer("Sedang memproses... Silakan tunggu.", show_alert=True)
            return
        state["launching"] = True
        
        conf = state["config"]
        selected = state.get("selected_sessions", [])
        selected = [s for s in (selected or []) if 1 <= s <= len(Altruix.clients)]
        if not selected:
            state["launching"] = False
            state["sub_menu"] = "select_sessions"
            await render_creategroup_ui(cb, state)
            await safe_cb_answer(cb, "⚠️ Tidak ada akun yang dipilih. Pilih minimal 1 akun.", show_alert=True)
            return
        
        from Main.plugins.userbot.xtaskmanager import generate_task_id
        from Main.plugins.userbot.xcreategroup import creategroup_loop
        
        # We will launch the loops in a background task so we can return to the dashboard immediately
        async def launch_tasks_bg(selected_sessions, conf_copy, uid, cb_msg):
            try:
                acc_delay = conf_copy.get("account_delay", 0.5)
                batch_account = conf_copy.get("batch_account", 3)
                ba_account_delay = conf_copy.get("ba_account_delay", 60)

                selected_sessions = [s for s in (selected_sessions or []) if 1 <= s <= len(Altruix.clients)]
                total_sessions = len(selected_sessions)
                
                for i, s_idx in enumerate(selected_sessions):
                    acc_preview = f"{i + 1}/{total_sessions}" if total_sessions else f"{i + 1}/?"
                    is_batch_boundary = (i > 0 and i % batch_account == 0)
                    
                    # Stagger startup if not the first account
                    if i > 0:
                        if is_batch_boundary and ba_account_delay > 0:
                            await asyncio.sleep(ba_account_delay)
                        elif acc_delay > 0:
                            await asyncio.sleep(acc_delay)
                        
                    tid = generate_task_id("CG")
                    try:
                        control_msg = None
                        try:
                            # Get session name for better logging
                            executor = Altruix.clients[s_idx - 1]
                            try:
                                me = executor.me or await executor.get_me()
                                s_name = (me.first_name or "") + (f" {me.last_name}" if me.last_name else "")
                            except Exception:
                                s_name = "Unknown"
                                
                            msg_text = f"🔄 Initializing task for Session {s_idx} [<b>{html.escape(s_name)}</b>] ({acc_preview}) [<code>{tid}</code>]..."
                            if i > 0:
                                if is_batch_boundary:
                                    msg_text = f"⏳ Batch Account Delay ({ba_account_delay}s)... {acc_preview}\n{msg_text}"
                                else:
                                    msg_text = f"⏳ Staggered Start ({acc_delay}s)... {acc_preview}\n{msg_text}"
                            
                            if cb_msg:
                                control_msg = await cb_msg.reply(f"<blockquote expandable>{msg_text}</blockquote>")
                            else:
                                control_msg = await Altruix.bot.send_message(uid, f"<blockquote expandable>{msg_text}</blockquote>")
                        except Exception as e:
                            from pyrogram.errors import PeerIdInvalid, UserIsBlocked
                            if isinstance(e, (PeerIdInvalid, UserIsBlocked)):
                                logger.warning(f"Bot failed to send control PM to user {uid} for session {s_idx}")
                            else:
                                logger.error(f"Critical error creating control message for session {s_idx}: {e}\n{traceback.format_exc()}")
                                continue # Don't start task for this session if we hit a critical error
                        
                        bots = conf_copy.get("bots", "").split() if conf_copy.get("bots") else []
                        asyncio.create_task(creategroup_loop(
                            user_client=executor,
                            bot_client=Altruix.bot,
                            initial_message=cb_msg,
                            delay=conf_copy.get("delay", 60),
                            count=conf_copy.get("count", 1),
                            extra_delay_minutes=conf_copy.get("batch_delay", 10),
                            batch_size=conf_copy.get("batch_size", 5),
                            batch_action=conf_copy.get("batch_action", 30),
                            ba_delay=conf_copy.get("ba_delay", 30),
                            group_type=conf_copy.get('group_type', 'a'),
                            name_pattern=conf_copy.get("pattern", "Group (index)"),
                            username_prefix=conf_copy.get("username", ""),
                            bot_identifiers=bots,
                            control_message=control_msg,
                            action_delay=conf_copy.get("action_delay", 3.0),
                            invite_bots=conf_copy.get("invite_bots", False),
                            anon_mode=conf_copy.get("anon_mode", True),
                            copy_messages=conf_copy.get("copy_messages", True),
                            description=conf_copy.get("description", "Powered by @AlphaXProject"),
                            photo_source=conf_copy.get("photo_source", "source"),
                            custom_photo_id=conf_copy.get("custom_photo_id"),
                            log_destination=conf_copy.get("log_destination", "both"),
                            log_format=conf_copy.get("log_format", "zip"),
                            pin_first_msg=conf_copy.get("pin_first_msg", True),
                            msg_img=conf_copy.get("msg_img", True),
                            msg_vid=conf_copy.get("msg_vid", True),
                            msg_img_album=conf_copy.get("msg_img_album", False),
                            msg_vid_album=conf_copy.get("msg_vid_album", False),
                            rand_len=conf_copy.get("rand_len", 3),
                            rand_lower=conf_copy.get("rand_lower", False),
                            rand_upper=conf_copy.get("rand_upper", True),
                            rand_static=conf_copy.get("rand_static", True),
                            temp_pin=conf_copy.get("temp_pin", True),
                            quote_block=conf_copy.get("quote_block", True),
                            user_id=uid,
                            task_id=tid,
                            account_idx=i+1,
                            total_accs=total_sessions,
                            batch_account=conf_copy.get("batch_account", 3),
                            ba_account_delay=conf_copy.get("ba_account_delay", 60),
                            start_log_mode=conf_copy.get("start_log_mode", "both"),
                            start_photo_log_mode=conf_copy.get("start_photo_log_mode", "both"),
                            progress_log_mode=conf_copy.get("progress_log_mode", "both"),
                            panel_log_mode=conf_copy.get("panel_log_mode", "log_group")
                        ))
                    except Exception as e:
                        logger.error(f"Failed to start task for session {s_idx}: {e}\n{traceback.format_exc()}")
                        # ✅ FIX: Notify user about the failed session via Telegram
                        try:
                            err_notify = (
                                f"<blockquote expandable>"
                                f"❌ <b>Gagal memulai task untuk Session {s_idx}</b>\n"
                                f"• Task ID: <code>{tid}</code>\n"
                                f"• Error: <code>{html.escape(str(e))}</code>"
                                f"</blockquote>"
                            )
                            if cb_msg:
                                await cb_msg.reply(err_notify)
                            else:
                                await Altruix.bot.send_message(uid, err_notify)
                        except Exception:
                            pass  # Best-effort notification
            except Exception as e:
                logger.error(f"Unexpected error in launch_tasks_bg: {e}\n{traceback.format_exc()}")
                # ✅ FIX: Notify user about the overall launch failure via Telegram
                try:
                    err_notify = (
                        f"<blockquote expandable>"
                        f"❌ <b>Launch sequence gagal total</b>\n"
                        f"• Error: <code>{html.escape(str(e))}</code>\n"
                        f"• Traceback: <pre>{html.escape(traceback.format_exc()[-500:])}</pre>"
                        f"</blockquote>"
                    )
                    if cb_msg:
                        await cb_msg.reply(err_notify)
                    else:
                        await Altruix.bot.send_message(uid, err_notify)
                except Exception:
                    pass  # Best-effort notification
            finally:
                if uid in user_creategroup_state:
                    user_creategroup_state[uid]["launching"] = False
        
        # Copy the config to freeze it for launch
        conf_copy = conf.copy()
        
        # Start the launch sequence in background
        asyncio.create_task(launch_tasks_bg(selected, conf_copy, user_id, cb.message))
        
        # Update state to go back to main dashboard
        state["sub_menu"] = None
        
        # Render the dashboard UI immediately
        await render_creategroup_ui(cb, state)
        
        # Notify the user with popup alert
        await safe_cb_answer(cb, f"🚀 Memulai CreateGroup Task pada {len(selected)} akun!", show_alert=True)
        
    except Exception as e:
        if user_id and user_id in user_creategroup_state:
            user_creategroup_state[user_id]["launching"] = False
        logger.error(f"Error in creategroup_confirm_task_handler: {e}\n{traceback.format_exc()}")
        err_msg = f"❌ <b>Error starting tasks:</b>\n<code>{e}</code>\n\n#LOG_ERROR"
        await send_log_message(f"{err_msg}\n<pre>{html.escape(traceback.format_exc())}</pre>")
        if cb.message:
            try: await cb.message.reply(f"❌ Error: {e}")
            except: pass
        else:
            try: await c.send_message(cb.from_user.id, f"❌ Error: {e}")
            except: pass

async def render_creategroup_running_ui(cb: CallbackQuery, task: dict, idx: int, pg: int):
    status = "▶️ Running"
    if task.get("paused"): status = "⏸️ Paused"
    
    # Calculate created count
    created_count = len(task.get("created_groups", []))
    total_count = task["params"]["count"]
    
    # Helper for current group name
    from Main.plugins.userbot.xcreategroup import generate_group_name
    current_name = generate_group_name(task["params"]["name_pattern"], task["current_index"])
    
    # Resolve user_style
    from Main.internals.settings_handlers.custom_alert_handlers import _get_session_user_id
    session_user_id = _get_session_user_id(idx)
    user_style = get_user_button_style(session_user_id)
    
    text = (
        f"<blockquote expandable>"
        "<b>📊 Progress Create Group</b>\n\n"
        f"• <b>Created:</b> {created_count}/{total_count}\n"
        f"• <b>Berhasil:</b> {created_count}\n"
        f"• <b>Current:</b> {html.escape(current_name)}\n"
        f"• <b>Account:</b> {html.escape(task.get('account_name', 'Unknown'))}\n"
        f"• <b>Status:</b> {status}"
        f"</blockquote>"
    )
    
    buttons = [
        [
            InlineKeyboardButton("🛑 Stop", callback_data=f"creategroup_control_stop_{idx}_{pg}", style=user_style),
            InlineKeyboardButton("⏸️ Pause", callback_data=f"creategroup_control_pause_{idx}_{pg}", style=user_style),
            InlineKeyboardButton("▶️ Resume", callback_data=f"creategroup_control_resume_{idx}_{pg}", style=user_style)
        ],
        [
            InlineKeyboardButton("📋 Status Detail", callback_data=f"creategroup_status_detail_{idx}_{pg}", style=user_style),
            InlineKeyboardButton("📑 List Group", callback_data=f"creategroup_list_group_{idx}_{pg}", style=user_style)
        ],
        [
            InlineKeyboardButton("🔄 Recurring", callback_data=f"creategroup_recurring_{idx}_{pg}", style=user_style),
            InlineKeyboardButton("✏️ Edit Last", callback_data=f"creategroup_edit_last_{idx}_{pg}", style=user_style)
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data=f"creategroup_menu_{idx}_{pg}", style=user_style)
        ]
    ]
    
    await safe_edit_message_text(cb, text, reply_markup=InlineKeyboardMarkup(buttons))

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_control_(stop|pause|resume)_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_control_handler(c: Client, cb: CallbackQuery):
    action, idx, pg = cb.matches[0].group(1), int(cb.matches[0].group(2)), int(cb.matches[0].group(3))
    task = await _find_task_by_session_idx(idx)
    
    # Redirect to main menu if task finished
    if not task or not task.get("running"):
        await cb.answer("Task not running", show_alert=True)
        await creategroup_ui_handler(c, cb) 
        return

    if action == "stop":
        # We need to signal the task to stop. The task checks CREATEGROUP_TASKS entry.
        task["running"] = False
        # Also wake up if paused
        if task.get("pause_event"): task["pause_event"].set()
        await cb.answer("Stopping task...")
        await asyncio.sleep(1) # Give it a moment
        await show_creategroup_ui(c, cb, idx, pg)
        
    elif action == "pause":
        if not task.get("paused"):
            task["paused"] = True
            if task.get("pause_event"): task["pause_event"].clear()
            await cb.answer("Paused!")
            await render_creategroup_running_ui(cb, task, idx, pg)
        else: await cb.answer("Already paused")
            
    elif action == "resume":
        if task.get("paused"):
            task["paused"] = False
            if task.get("pause_event"): task["pause_event"].set()
            await cb.answer("Resumed!")
            await render_creategroup_running_ui(cb, task, idx, pg)
        else: await cb.answer("Already running")

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_status_detail_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_status_detail_handler(c: Client, cb: CallbackQuery):
    idx, pg = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    task = await _find_task_by_session_idx(idx)
    
    if not task: return await cb.answer("No task running", show_alert=True)
    
    # Detailed status logic
    p = task["params"]
    text = (
        "<b>📝 Status Detail</b>\n\n"
        f"• <b>Start Time:</b> {task['start_time'].strftime('%H:%M:%S')}\n"
        f"• <b>Delay:</b> {p['delay']}s\n"
        f"• <b>Batch:</b> {p['batch_size']} groups (Delay {p['extra_delay_minutes']}m)\n"
        f"• <b>Bots:</b> {len(p['bot_identifiers'])} bots\n"
        f"• <b>Username:</b> {p['username_prefix'] or 'None'}\n"
    )
    # Resolve user_style
    from Main.internals.settings_handlers.custom_alert_handlers import _get_session_user_id
    session_user_id = _get_session_user_id(idx)
    user_style = get_user_button_style(session_user_id)
    
    await cb.answer("Full details shown", show_alert=True)
    buttons = [[InlineKeyboardButton("🔙 Back", callback_data=f"creategroup_ui_{idx}_{pg}", style=user_style)]]
    await safe_edit_message_text(cb, text, reply_markup=InlineKeyboardMarkup(buttons))

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_list_group_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_list_group_handler(c: Client, cb: CallbackQuery):
    idx, pg = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    task = await _find_task_by_session_idx(idx)
    
    if not task: return await cb.answer("No task running", show_alert=True)
    
    groups = task.get("created_groups", [])
    if not groups:
        await cb.answer("No groups created yet", show_alert=True)
        return
        
    text = "<b>📑 List Created Groups</b>\n\n"
    for g in groups[-10:]: # Show last 10
        text += f"• {html.escape(g['name'])} (<code>{g['id']}</code>)\n"
    
    if len(groups) > 10: text += f"\n...and {len(groups)-10} more."
    
    # Resolve user_style
    from Main.internals.settings_handlers.custom_alert_handlers import _get_session_user_id
    session_user_id = _get_session_user_id(idx)
    user_style = get_user_button_style(session_user_id)
    
    buttons = [[InlineKeyboardButton("🔙 Back", callback_data=f"creategroup_ui_{idx}_{pg}", style=user_style)]]
    await safe_edit_message_text(cb, text, reply_markup=InlineKeyboardMarkup(buttons))

async def _find_completed_task_by_session_idx(idx: int):
    if not (1 <= idx <= len(Altruix.clients)):
        return None
    client = Altruix.clients[idx - 1]
    try:
        me_user = client.me or await client.get_me()
        target_session_id = me_user.id
    except Exception:
        return None
        
    from Main.plugins.userbot.xcreategroup import COMPLETED_CREATEGROUP_TASKS
    matching_tasks = []
    for k, v in COMPLETED_CREATEGROUP_TASKS.items():
        if v.get("user_id") == target_session_id:
            matching_tasks.append(v)
            
    if matching_tasks:
        matching_tasks.sort(key=lambda x: x.get("start_time", datetime.min) if isinstance(x.get("start_time"), datetime) else datetime.min, reverse=True)
        return matching_tasks[0]
    return None

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_recurring_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_recurring_handler(c: Client, cb: CallbackQuery):
    idx, pg = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    
    # Check if a task is already running for this session
    task = await _find_task_by_session_idx(idx)
    if task and task.get("running"):
        await cb.answer("⚠️ Task masih berjalan, hentikan dulu sebelum recurring.", show_alert=True)
        return
        
    conf = await _find_completed_task_by_session_idx(idx)
    if not conf:
        await cb.answer("❌ Tidak ada task selesai untuk diulang.", show_alert=True)
        return
        
    # Show confirmation UI
    text = (
        f"🔁 <b>Konfirmasi Recurring</b>\n\n"
        f"Apakah Anda yakin ingin mengulang task ini?\n"
        f"• Account: <b>Session {idx}</b>\n"
        f"• Total: <code>{conf['count']}</code> grup\n"
        f"• Tipe: <code>{conf['group_type']}</code>\n"
        f"• Delay/Act: <code>{conf.get('action_delay', 3.0)}</code>s\n"
        f"• Delay/GC: <code>{conf['delay']}</code>s\n"
        f"• Batch: <code>{conf['batch_size']}</code> | <code>{conf['extra_delay_minutes']}</code>m\n"
        f"• Pattern: <code>{html.escape(conf['name_pattern'][:25])}...</code>\n"
        f"• Bots: <code>{'Yes' if conf.get('invite_bots', True) else 'No'}</code>\n\n"
        f"<i>Task akan menggunakan konfigurasi yang sama.</i>"
    )
    
    from Main.internals.settings_handlers.custom_alert_handlers import _get_session_user_id
    session_user_id = _get_session_user_id(idx)
    user_style = get_user_button_style(session_user_id)
    
    buttons = [
        [
            InlineKeyboardButton("✅ Ya, Ulangi", callback_data=f"creategroup_confirm_recur_{idx}_{pg}", style=user_style),
            InlineKeyboardButton("❌ Tidak", callback_data=f"creategroup_ui_{idx}_{pg}", style=user_style)
        ]
    ]
    
    if cb.message:
        await cb.message.edit(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
    else:
        await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_confirm_recur_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_confirm_recur_handler(c: Client, cb: CallbackQuery):
    idx, pg = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    
    task = await _find_task_by_session_idx(idx)
    if task and task.get("running"):
        await cb.answer("⚠️ Task masih berjalan, hentikan dulu sebelum recurring.", show_alert=True)
        return
        
    conf = await _find_completed_task_by_session_idx(idx)
    if not conf:
        await cb.answer("❌ Tidak ada task selesai untuk diulang.", show_alert=True)
        return
        
    await cb.answer("🔁 Mengulang task...")
    
    from Main.plugins.userbot.xcreategroup import creategroup_loop
    from Main.plugins.userbot.xtaskmanager import generate_task_id
    
    tid = generate_task_id("CG")
    executor = Altruix.clients[idx - 1]
    
    try:
        control_msg = await Altruix.bot.send_message(cb.from_user.id, f"<blockquote expandable>🔄 Re-initializing recurring task for Session {idx} [<code>{tid}</code>]...</blockquote>")
    except Exception:
        control_msg = None
        
    asyncio.create_task(creategroup_loop(
        user_client=executor,
        bot_client=Altruix.bot,
        initial_message=cb.message,
        delay=conf["delay"],
        count=conf["count"],
        extra_delay_minutes=conf["extra_delay_minutes"],
        batch_size=conf["batch_size"],
        batch_action=conf.get("batch_action", 30),
        ba_delay=conf.get("ba_delay", 30),
        group_type=conf["group_type"],
        name_pattern=conf["name_pattern"],
        username_prefix=conf["username_prefix"],
        bot_identifiers=conf["bot_identifiers"],
        control_message=control_msg,
        action_delay=conf.get("action_delay", 3.0),
        invite_bots=conf.get("invite_bots", True),
        anon_mode=conf.get("anon_mode", True),
        copy_messages=conf.get("copy_messages", True),
        description=conf.get("description", "Powered by @AlphaXproject"),
        photo_source=conf.get("photo_source", "source"),
        custom_photo_id=conf.get("custom_photo_id"),
        log_destination=conf.get("log_destination", "both"),
        log_format=conf.get("log_format", "zip"),
        pin_first_msg=conf.get("pin_first_msg", True),
        msg_img=conf.get("msg_img", True),
        msg_vid=conf.get("msg_vid", True),
        msg_img_album=conf.get("msg_img_album", False),
        msg_vid_album=conf.get("msg_vid_album", False),
        rand_len=conf.get("rand_len", 0),
        rand_lower=conf.get("rand_lower", False),
        rand_upper=conf.get("rand_upper", False),
        rand_static=conf.get("rand_static", False),
        temp_pin=conf.get("temp_pin", True),
        user_id=cb.from_user.id,
        task_id=tid,
        account_idx=1,
        total_accs=1
    ))
    
    # Back to running dashboard or menu
    await asyncio.sleep(1)
    await show_creategroup_ui(c, cb, idx, pg)

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_edit_last_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_edit_last_handler(c: Client, cb: CallbackQuery):
    idx, pg = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    user_id = cb.from_user.id
    
    task = await _find_task_by_session_idx(idx) or await _find_completed_task_by_session_idx(idx)
    if not task:
        await cb.answer("❌ Tidak ada task aktif atau selesai untuk sesi ini.", show_alert=True)
        return
        
    created_groups = task.get("created_groups", [])
    if not created_groups:
        await cb.answer("❌ Belum ada grup yang dibuat.", show_alert=True)
        return
        
    last_group = created_groups[-1]
    chat_id = last_group["id"]
    old_name = last_group["name"]
    
    user_creategroup_state[user_id] = {
        "step": "awaiting_edit_last_name",
        "session_index": idx,
        "page": pg,
        "chat_id": chat_id,
        "old_name": old_name,
        "ui_msg_id": cb.message.id if cb.message else None,
        "ui_chat_id": cb.message.chat.id if cb.message else user_id
    }
    
    text = (
        f"✏️ <b>Edit Last Group Name</b>\n\n"
        f"• Group ID: <code>{chat_id}</code>\n"
        f"• Current Name: <b>{html.escape(old_name)}</b>\n\n"
        f"Silakan balas/kirimkan nama baru untuk grup tersebut.\n"
        f"Ketik <code>/cancel</code> untuk membatalkan."
    )
    
    from Main.internals.settings_handlers.custom_alert_handlers import _get_session_user_id
    session_user_id = _get_session_user_id(idx)
    user_style = get_user_button_style(session_user_id)
    
    buttons = [[InlineKeyboardButton("❌ Cancel", callback_data=f"creategroup_cancel_edit_last_{idx}_{pg}", style=user_style)]]
    
    if cb.message:
        await cb.message.edit(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
    else:
        await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_cancel_edit_last_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_cancel_edit_last_handler(c: Client, cb: CallbackQuery):
    idx, pg = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    user_id = cb.from_user.id
    
    if user_id in user_creategroup_state:
        user_creategroup_state[user_id]["step"] = "ui_config"
        
    await cb.answer("Edit last dibatalkan")
    await show_creategroup_ui(c, cb, idx, pg)

async def process_creategroup_input(c: Client, m: Message, text: str = None):
    user_id = m.from_user.id
    state = user_creategroup_state.get(user_id)
    import logging
    dl = logging.getLogger("altruix.CG_DEBUG")
    dl.info(f"[DEBUG-CG] Enter process_CG. user: {user_id}. step: {state.get('step') if state else 'NONE'}, field: {state.get('input_mode') if state else 'NONE'}")
    if not state: return
    if state["step"] == "awaiting_photo":
        if state.get("prompt_msg_id"):
            try: await c.delete_messages(m.chat.id, state["prompt_msg_id"])
            except: pass
            state["prompt_msg_id"] = None
        if m.photo:
            state["config"]["custom_photo_id"] = m.photo.file_id
            state["step"], state["input_mode"] = "ui_config", None
            if state.get("ui_msg_id"):
                try: 
                    target_chat = state.get("ui_chat_id", m.chat.id)
                    target_msg = await c.get_messages(target_chat, state["ui_msg_id"])
                    await render_creategroup_ui(None, state, message=target_msg)
                    if target_chat != m.chat.id:
                        await m.reply("✅ Foto berhasil diperbarui pada menu terkait.")
                except Exception as e:
                    new_msg = await m.reply(f"✅ Foto Tersimpan! (Fallback memuat UI baru...)")
                    state["ui_msg_id"] = new_msg.id
                    state["ui_chat_id"] = m.chat.id
                    await render_creategroup_ui(None, state, message=new_msg)
            else:
                new_msg = await m.reply("✅ Foto Tersimpan! Memuat UI baru...")
                state["ui_msg_id"] = new_msg.id
                state["ui_chat_id"] = m.chat.id
                await render_creategroup_ui(None, state, message=new_msg)
            return
        elif text and text.lower() == "/cancel":
            state["step"], state["input_mode"] = "ui_config", None
            if state.get("ui_msg_id"):
                try:
                    target_chat = state.get("ui_chat_id", m.chat.id)
                    target_msg = await c.get_messages(target_chat, state["ui_msg_id"])
                    await render_creategroup_ui(None, state, message=target_msg)
                except: pass
            else:
                new_msg = await m.reply("Memperbarui UI...")
                state["ui_msg_id"] = new_msg.id
                state["ui_chat_id"] = m.chat.id
                await render_creategroup_ui(None, state, message=new_msg)
            return
        else: return
    elif state["step"] == "awaiting_edit_last_name":
        new_name = text or m.text
        if not new_name:
            return
            
        idx = state["session_index"]
        pg = state["page"]
        
        if new_name.strip().lower() == "/cancel":
            state["step"] = "ui_config"
            await m.reply("✏️ Edit nama grup dibatalkan.")
            task = await _find_task_by_session_idx(idx)
            user_style = get_user_button_style(m.from_user.id)
            if task:
                await m.reply(
                    "Kembali ke progress menu.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📊 Lihat Progress", callback_data=f"creategroup_ui_{idx}_{pg}", style=user_style)]])
                )
            else:
                await m.reply(
                    "Kembali ke menu utama.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menu Utama", callback_data=f"creategroup_ui_{idx}_{pg}", style=user_style)]])
                )
            return

        chat_id = state["chat_id"]
        old_name = state["old_name"]
        
        try:
            client = Altruix.clients[idx - 1]
            await client.set_chat_title(int(chat_id), new_name)
            
            # Update memory in tasks
            from Main.plugins.userbot.xcreategroup import CREATEGROUP_TASKS, COMPLETED_CREATEGROUP_TASKS
            task_info = CREATEGROUP_TASKS.get(idx) or await _find_task_by_session_idx(idx) or await _find_completed_task_by_session_idx(idx)
            if task_info:
                for g in task_info.get("created_groups", []):
                    if g["id"] == chat_id:
                        g["name"] = new_name
                        break
            
            await m.reply(
                f"✅ <b>Nama Grup Berhasil Diubah!</b>\n\n"
                f"• Sebelum: <code>{html.escape(old_name)}</code>\n"
                f"• Sesudah: <code>{html.escape(new_name)}</code>",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Error in process_creategroup_input awaiting_edit_last_name: {e}\n{traceback.format_exc()}")
            await m.reply(f"❌ <b>Gagal mengubah nama grup:</b>\n<code>{html.escape(str(e))}</code>", parse_mode=ParseMode.HTML)
            
        state["step"] = "ui_config"
        task = await _find_task_by_session_idx(idx)
        user_style = get_user_button_style(m.from_user.id)
        if task:
            await m.reply(
                "Grup telah diperbarui. Silakan muat ulang progress menu.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📊 Lihat Progress", callback_data=f"creategroup_ui_{idx}_{pg}", style=user_style)]])
            )
        else:
            await m.reply(
                "Grup telah diperbarui. Kembali ke menu utama.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menu Utama", callback_data=f"creategroup_ui_{idx}_{pg}", style=user_style)]])
            )
        return
    elif state["step"] == "input_manual":
        # Process manual command-like input string
        try:
            args = text.split()
            if len(args) < 6:
                await m.reply("❌ Format salah! Minimal 6 parameter.")
                return
            config = {"delay": int(args[0]), "count": int(args[1]), "batch_delay": int(args[2]), "batch_size": int(args[3]), "type": args[4].lower(), "bots": [], "username": None, "pattern": ""}
            full_args = " ".join(args[5:])
            if " ; " in full_args:
                p, e = full_args.split(" ; ", 1)
                config["pattern"] = p.strip('"\'')
                ex = e.strip().split()
                if ex:
                    if not (ex[0].startswith('@') or ex[0].isdigit()):
                         config["username"] = ex[0]
                         config["bots"] = ex[1:]
                    else: config["bots"] = ex
            else: config["pattern"] = full_args.strip('"\'')
            state["config"], state["step"] = config, "confirm_manual"
            buttons = [[InlineKeyboardButton("✅ Run", f"creategroup_run_{state['session_index']}_{state['page']}")]]
            await m.reply(f"Confirm Manual Run?\n{config}", reply_markup=InlineKeyboardMarkup(buttons))
        except Exception as e: await m.reply(f"Error: {e}")
    elif state["step"] == "awaiting_input":
        field = state["input_mode"]
        dl.info(f"[DEBUG-CG] Processing input for field '{field}'. Provided text: '{text}'")
        
        if field == "pattern": 
            state["config"]["pattern"] = text
            dl.info(f"[DEBUG-CG] Field 'pattern' successfully updated in config.")
        elif field == "username": 
            state["config"]["username"] = text
            dl.info(f"[DEBUG-CG] Field 'username' successfully updated in config.")
        elif field == "description": 
            state["config"]["description"] = text
            dl.info(f"[DEBUG-CG] Field 'description' successfully updated in config.")
        elif field == "bots":
             bots = text.replace(",", " ").split()
             clean_bots = []
             for b in bots: clean_bots.append(b if (b.startswith("@") or b.isdigit()) else f"@{b}")
             state["config"]["bots"] = " ".join(clean_bots)
             dl.info(f"[DEBUG-CG] Field 'bots' successfully updated {len(clean_bots)} bots.")
        elif field in ["delay", "count", "batch_delay", "batch_size", "action_delay", "account_delay", "batch_action", "ba_delay", "batch_account", "ba_account_delay"]:
            is_float_field = field in ["action_delay", "account_delay"]
            if text.isdigit() or (is_float_field and text.replace(".", "", 1).isdigit()):
                 val = float(text) if is_float_field else int(text)
                 state["config"][field] = val
                 dl.info(f"[DEBUG-CG] Field '{field}' successfully updated to integer/float {val}.")
            else:
                 dl.warning(f"[DEBUG-CG] Input for '{field}' was rejected due to non-digit: '{text}'")
                 await m.reply("❌ Input harus angka!")
                 return
        else:
             dl.error(f"[DEBUG-CG] WARNING: Unrecognized field mode: '{field}'")
             
        dl.info(f"[DEBUG-CG] Changing step back to 'ui_config' and dispatching UI update.")
        state["step"], state["input_mode"] = "ui_config", None
        save_user_cg_config(m.from_user.id, state["config"])
        if state.get("prompt_msg_id"):
            try: await c.delete_messages(m.chat.id, state["prompt_msg_id"])
            except: pass
            state["prompt_msg_id"] = None
        
        ui_id = state.get("ui_msg_id")
        if ui_id:
            try:
                if isinstance(ui_id, str):
                    # Inline message
                    dl.info(f"[DEBUG-CG] Editing inline msg {ui_id}")
                    await render_creategroup_ui(None, state)
                    await m.reply("✅ Pengaturan berhasil diperbarui.")
                else:
                    chat_id_to_edit = state.get("ui_chat_id", m.chat.id)
                    dl.info(f"[DEBUG-CG] Editing msg {ui_id} in chat {chat_id_to_edit}")
                    target_msg = await c.get_messages(chat_id_to_edit, ui_id)
                    await render_creategroup_ui(None, state, message=target_msg)
                    if chat_id_to_edit != m.chat.id:
                         await m.reply("✅ Pengaturan berhasil diperbarui pada menu terkait.")
            except Exception as e:
                # Fallback if editing the original message fails for any reason
                dl.error(f"[DEBUG-CG] Edit failed: {e}. Falling back to new msg")
                new_msg = await m.reply(f"✅ Tersimpan! (Fallback memuat UI baru...)")
                state["ui_msg_id"] = new_msg.id
                state["ui_chat_id"] = m.chat.id
                await render_creategroup_ui(None, state, message=new_msg)
        else:
            dl.info(f"[DEBUG-CG] No ui_msg_id, creating new msg")
            new_msg = await m.reply("✅ Tersimpan! Memuat UI baru...")
            state["ui_msg_id"] = new_msg.id
            state["ui_chat_id"] = m.chat.id
            await render_creategroup_ui(None, state, message=new_msg)
            
        return

# ============================================================================
# ⌨️ INLINE QUERY HANDLER FOR CREATEGROUP
# ============================================================================

@Altruix.bot.on_inline_query(filters.regex(r"^(creategroup_(\d+)(?:_(\d+))?|creategroup_panel_(#CG[a-f0-9]+)).*"))
@iuser_check
@log_errors
async def creategroup_inline_handler(c: Client, iq: InlineQuery):
    """Inline-based creategroup Dashboard and Panel handlers."""
    # AUTHORIZATION CHECK
    if not await Altruix.is_sudo(iq.from_user.id):
        return
    
    match_str = iq.matches[0].group(1)
    
    # ─── CASE 1: Task Control Panel (creategroup_panel_#TID) ───
    if "creategroup_panel_" in match_str:
        try:
            tid = iq.matches[0].group(4)
            from Main.plugins.userbot.xcreategroup import CREATEGROUP_TASKS
            
            if tid not in CREATEGROUP_TASKS:
                # Fallback if task not found
                results = [InlineQueryResultArticle(
                    id=f"cg_err_{tid}",
                    title="Task Not Found",
                    input_message_content=InputTextMessageContent(f"❌ Task <code>{tid}</code> tidak ditemukan atau sudah selesai.", parse_mode=ParseMode.HTML)
                )]
                return await iq.answer(results=results, cache_time=0, is_personal=True)
                
            task_data = CREATEGROUP_TASKS[tid]
            account_name = task_data.get("account_name", "Unknown")
            params = task_data.get("params", {})
            count = params.get("count", 0)
            group_type = params.get("group_type", "a")
            unit_label = "channel" if group_type == "c" else "grup"
            
            # Resolve user_style
            from Main.utils.file_helpers import get_user_button_style
            user_style = get_user_button_style(iq.from_user.id)
            from Main.utils.essentials import Essentials
            
            control_buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(await Essentials.get_user_button_style(iq.from_user.id, "🛑 Stop"), callback_data=f"stop_creategroup:{tid}", style=user_style),
                    InlineKeyboardButton(await Essentials.get_user_button_style(iq.from_user.id, "⏸️ Pause"), callback_data=f"pause_creategroup:{tid}", style=user_style),
                    InlineKeyboardButton(await Essentials.get_user_button_style(iq.from_user.id, "▶️ Resume"), callback_data=f"resume_creategroup:{tid}", style=user_style)
                ],
                [
                    InlineKeyboardButton(await Essentials.get_user_button_style(iq.from_user.id, "📊 Status"), callback_data=f"status_creategroup:{tid}", style=user_style),
                    InlineKeyboardButton(await Essentials.get_user_button_style(iq.from_user.id, "📋 List"), callback_data=f"list_creategroup:{tid}", style=user_style),
                    InlineKeyboardButton(await Essentials.get_user_button_style(iq.from_user.id, "🔁 Recurring"), callback_data=f"recurring_creategroup:{tid}", style=user_style)
                ],
                [
                     InlineKeyboardButton(await Essentials.get_user_button_style(iq.from_user.id, "✏️ Edit Name"), callback_data=f"edit_last_creategroup:{tid}", style=user_style), 
                     InlineKeyboardButton(await Essentials.get_user_button_style(iq.from_user.id, "✅ Check Created"), callback_data=f"list_groups_creategroup:{tid}", style=user_style)
                ]
            ])
            
            results = [InlineQueryResultArticle(
                id=f"cg_pnl_{tid}",
                title=f"Task Control Panel: {tid}",
                description=f"Manage task for {account_name}",
                input_message_content=InputTextMessageContent(
                    f"<blockquote expandable>"
                    f"🚀 <b>Task Control Panel</b>\n"
                    f"• TID: <code>{tid}</code>\n"
                    f"• Account: <b>{html.escape(account_name)}</b>\n"
                    f"• Target: <code>{count}</code> {unit_label}\n\n"
                    f"<i>Linear Log threading aktif di bawah pesan ini.</i>"
                    f"</blockquote>",
                    parse_mode=ParseMode.HTML
                ),
                reply_markup=control_buttons,
                thumb_url="https://telegra.ph/file/0c6f5a3e1445790c9b0e2.jpg"
            )]
            return await iq.answer(results=results, cache_time=0, is_personal=True)
        except Exception as e:
            logger.error(f"Error in creategroup_inline_handler (Panel): {e}\n{traceback.format_exc()}")
            results = [InlineQueryResultArticle(
                id=f"cg_err_panel",
                title="Internal Error",
                input_message_content=InputTextMessageContent(f"❌ Terjadi kesalahan internal saat memuat panel kontrol.", parse_mode=ParseMode.HTML)
            )]
            return await iq.answer(results=results, cache_time=0, is_personal=True)

    # ─── CASE 2: Configuration Dashboard (creategroup_index_page) ───
    try:
        index = int(iq.matches[0].group(2))
        page = int(iq.matches[0].group(3)) if iq.matches[0].group(3) else 1
        
        # Extract extra metadata from query string if present
        query = iq.query
        chat_id = "N/A"
        chat_title = "N/A"
        
        if "cid=" in query:
            import re
            if m := re.search(r"cid=(-?\d+)", query):
                chat_id = m.group(1)
                
        if "ctit=" in query:
            import base64
            try:
                if m := re.search(r"ctit=([^&\s]+)", query):
                    encoded_title = m.group(1)
                    chat_title = base64.b64decode(encoded_title).decode('utf-8')
            except: pass
            
        # Generate data
        text, reply_markup = await get_creategroup_ui_data(iq.from_user.id, index, page)
        
        result_identity = f"cg_{index}_{chat_id}"
        
        # Answer inline query
        results = [
            InlineQueryResultArticle(
                id=result_identity,
                title=f"Create Group Dashboard #{index}",
                description=f"Manage group creation for {chat_title if chat_title != 'N/A' else 'this session'}",
                input_message_content=InputTextMessageContent(
                    message_text=f"<b>🚀 𝐂𝐑𝐄𝐀𝐓𝐄 𝐆𝐑𝐎𝐔𝐏 𝐃𝐀𝐒𝐇𝐁𝐎𝐀𝐑𝐃</b>\n\n<blockquote expandable>{text}</blockquote>",
                    parse_mode=ParseMode.HTML,
                    link_preview_options=LinkPreviewOptions(is_disabled=True)
                ),
                reply_markup=reply_markup,
                thumb_url="https://telegra.ph/file/0c6f5a3e1445790c9b0e2.jpg"
            )
        ]
        await iq.answer(results=results, cache_time=0, is_personal=True)
    except Exception as e:
        logger.error(f"Error in creategroup_inline_handler (Dashboard): {e}\n{traceback.format_exc()}")
        err_msg = f"❌ <b>Error in Dashboard:</b>\n<code>{e}</code>\n\n#LOG_ERROR"
        await send_log_message(f"{err_msg}\n<pre>{html.escape(traceback.format_exc())}</pre>")
        results = [InlineQueryResultArticle(
            id=f"cg_err_dash",
            title="Internal Error",
            input_message_content=InputTextMessageContent(f"❌ Terjadi kesalahan internal saat memuat dashboard.", parse_mode=ParseMode.HTML)
        )]
        return await iq.answer(results=results, cache_time=0, is_personal=True)

@Altruix.bot.on_chosen_inline_result(filters.regex(r"^cg_(\d+)_(-?\d+|N/A)"))
async def creategroup_chosen_handler(c: Client, cir: ChosenInlineResult):
    """Capture the inline_message_id and chat metadata when a result is chosen."""
    result_id = cir.result_id
    inline_msg_id = cir.inline_message_id
    
    if not inline_msg_id:
        return

    try:
        # cg_{index}_{chat_id}
        parts = result_id.split("_")
        index = int(parts[1])
        chat_id = parts[2]
        
        user_id = cir.from_user.id
        if user_id not in user_creategroup_state:
            user_creategroup_state[user_id] = {
                "step": "ui_config",
                "session_index": index,
                "page": 1,
                "config": load_user_cg_config(user_id),
                "selected_sessions": [index],
                "session_page": 0,
                "input_mode": None,
                "ui_msg_id": inline_msg_id,
                "ui_chat_id": chat_id if chat_id != "N/A" else None,
                "prompt_msg_id": None,
                "sub_menu": None,
                "launching": False
            }
        else:
            user_creategroup_state[user_id].update({
                "ui_msg_id": inline_msg_id,
                "ui_chat_id": chat_id if chat_id != "N/A" else None,
                "session_index": index,
                "launching": False
            })
            user_creategroup_state[user_id].setdefault("selected_sessions", [index])
            if not user_creategroup_state[user_id]["selected_sessions"]:
                user_creategroup_state[user_id]["selected_sessions"] = [index]
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error in creategroup_chosen_handler: {e}")