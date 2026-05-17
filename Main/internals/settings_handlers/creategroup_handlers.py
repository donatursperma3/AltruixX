# Main/internals/settings_handlers/creategroup_handlers.py
import os
import html
import asyncio
import logging
import traceback
from typing import Optional
from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton,
    InlineQuery, InlineQueryResultArticle, InputTextMessageContent,
    ChosenInlineResult, LinkPreviewOptions
)
from Main.core.decorators import log_errors, iuser_check, send_log_message
from Main.core.client import Altruix
from pyrogram.enums import ParseMode


from .states import user_creategroup_state

HANDLER_VERSION = "0.3.222" # ✅ FIXED: Resume All for Paused Tasks & UI Stability
logger = logging.getLogger("altruix.creategroup.handlers")
logger.setLevel(logging.INFO)

# Default Configuration
DEFAULT_CREATEGROUP_CONFIG = {
    "delay": 60, "count": 2, "batch_delay": 10, "batch_size": 2, "action_delay": 3.0,
    "account_delay": 0.5, # ✅ NEW: Staggered start delay for multi-account tasks
    "batch_action": 30, "ba_delay": 30,
    "pattern": "🔰 X(tahun) B(bulan)-T(tanggal)", "username": None, "description": "Powered by @AlphaXProject",
    "bots": "@MissRose_bot @simixbot @Spillgame_bot @truthordaresbot @truthordares_bot @truthordarerp_bot @truthordarerln_bot @truthordares18_bot",
    "invite_bots": True, "anon_mode": True, "copy_messages": True, "msg_img": True,
    "photo_source": "source", "custom_photo_id": None,
    "log_destination": "both", "group_type": "a",
    "log_format": "zip", "pin_first_msg": True, "temp_pin": True, "quote_block": True,
    "rand_len": 3, "rand_lower": False, "rand_upper": True, "rand_static": True
}


# ─── Persistent User Config ───
from Main.utils.file_helpers import get_db_path as _get_db_path
import json as _json
_USER_CG_CONFIG_FILE = _get_db_path("xcreategroup_user_configs.json")

def save_user_cg_config(user_id: int, config: dict):
    """Save user's CreateGroup config to persistent JSON."""
    try:
        data = {}
        if os.path.exists(_USER_CG_CONFIG_FILE):
            with open(_USER_CG_CONFIG_FILE, "r") as f:
                data = _json.load(f)
        data[str(user_id)] = config
        tmp = f"{_USER_CG_CONFIG_FILE}.tmp"
        with open(tmp, "w") as f:
            _json.dump(data, f, indent=2)
        os.replace(tmp, _USER_CG_CONFIG_FILE)
    except Exception as e:
        logger.error(f"Failed to save user CG config: {e}\n{traceback.format_exc()}")

def load_user_cg_config(user_id: int) -> dict:
    """Load user's saved CreateGroup config, or return defaults."""
    try:
        if os.path.exists(_USER_CG_CONFIG_FILE):
            with open(_USER_CG_CONFIG_FILE, "r") as f:
                data = _json.load(f)
            saved = data.get(str(user_id))
            if saved:
                merged = DEFAULT_CREATEGROUP_CONFIG.copy()
                merged.update(saved)
                return merged
    except Exception as e:
        logger.error(f"Failed to load user CG config: {e}\n{traceback.format_exc()}")
    return DEFAULT_CREATEGROUP_CONFIG.copy()

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
    
    if cb.message:
        await cb.message.edit(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
    else:
        await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

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
        text = "<blockquote expandable><b>🔄 Restore Tasks</b>\n\n<i>Tidak ada task yang terhenti atau tersimpan di cache saat ini.</i></blockquote>"
        buttons = [[InlineKeyboardButton("🔙 Back", callback_data=f"creategroup_menu_{session_index}_{page}", style=user_style)]]
        return await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
        
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
        
    text = f"<blockquote expandable><b>🔄 Restore Tasks (Cache) [{task_page}/{total_pages}]</b>\n\n" + "\n".join(lines) + "\n\n<i>Klik tombol aksi di bawah untuk memproses task spesifik.</i></blockquote>"
    
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
    
    await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)


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
                rand_len=params.get("rand_len", 0), rand_lower=params.get("rand_lower", False),
                rand_upper=params.get("rand_upper", False), rand_static=params.get("rand_static", False),
                batch_action=params.get("batch_action", 30), ba_delay=params.get("ba_delay", 30),
                user_id=client_id, task_id=tid, is_resume=True,
                account_idx=params.get("account_idx", 1), total_accs=params.get("total_accs", 1)
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
        await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
    except Exception:
        await cb.answer()

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

    
    if cb.message:
        await cb.message.edit(text, parse_mode=ParseMode.HTML, 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"creategroup_menu_{session_index}_{page}", style=user_style)]]))
    else:
        await cb.edit_message_text(text, parse_mode=ParseMode.HTML, 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"creategroup_menu_{session_index}_{page}", style=user_style)]]))

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

async def show_creategroup_ui(c: Client, cb: CallbackQuery, session_index: int, page: int):
    user_id = cb.from_user.id
    
    # Check if task is already running
    from Main.plugins.userbot.xcreategroup import CREATEGROUP_TASKS
    task = CREATEGROUP_TASKS.get(f"creategroup_{user_id}")
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
            "input_mode": None,
            "ui_msg_id": cb.message.id if cb.message else None,
            "ui_chat_id": cb.message.chat.id if cb.message else None,
            "prompt_msg_id": None,
            "sub_menu": None
        }
    else:
        user_creategroup_state[user_id]["step"] = "ui_config"
        user_creategroup_state[user_id]["input_mode"] = None
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
            "prompt_msg_id": None
        }
    else:
        # 🔥 CRITICAL SYNC: If we are switching accounts, update the primary index and selection
        # This prevents a dashboard opened on Account 2 from using Account 1's state
        state = user_creategroup_state[user_id]
        if state.get("session_index") != session_index:
             state["session_index"] = session_index
             # Optionally reset selection to the new triggering session to avoid confusion
             state["selected_sessions"] = [session_index]
    
    state = user_creategroup_state[user_id]
    config = state["config"]
    idx = state["session_index"]
    pg = state["page"]
    sub_menu = state.get("sub_menu")
    
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
    selected = state.get("selected_sessions", [idx])
    sel_count = len(selected)
    
    session_text = ""
    if session_user:
        session_text = f"<b>• Session:</b> ⭐ <a href='tg://user?id={session_user.id}'>{html.escape(session_user.first_name)}</a>\n"
    
    session_text += f"<b>• Selected Acc(s):</b> <code>{sel_count}</code> / <code>{len(Altruix.clients)}</code>\n"

    photo_status = f"Source Account" if config.get('photo_source') == "source" else "Custom Photo"
    if config.get('photo_source') == "custom":
        photo_status += " ✅" if config.get('custom_photo_id') else " ❌ (No photo)"

    num_bots = len(config['bots'].split() if config['bots'] else [])
    is_default_bots = config['bots'] == DEFAULT_CREATEGROUP_CONFIG['bots']
    bot_list_text = f"{num_bots} bots{' (Default)' if is_default_bots else ''}"

    g_type = config.get('group_type', 'a')
    type_label = "Group" if g_type == 'a' else "Channel"
    unit_name = "groups" if g_type == 'a' else "channels"

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
        f"• <b>Action Delay:</b> {config['action_delay']}s | <b>Account Delay:</b> {config.get('account_delay', 0.5)}s\n"
        f"• <b>Name:</b> {html.escape(name_preview)}\n"
        f"• <b>Username:</b> {config['username'] or 'None'}\n"
        f"• <b>Description:</b> {html.escape(config['description'])}\n"
        f"• <b>Photo:</b> {photo_status}\n"
        f"• <b>Anon Admin:</b> {'Yes' if config['anon_mode'] else 'No'} | <b>Copy Msg:</b> {'Yes' if config['copy_messages'] else 'No'}\n"
        f"• <b>Invite Bots:</b> {'Yes' if config['invite_bots'] else 'No'}\n"
        f"• <b>Bot List:</b> {bot_list_text}\n"
        f"• <b>Pin First Msg:</b> {'Yes' if config.get('pin_first_msg', True) else 'No'} | <b>Temp Pin:</b> {'Yes' if config.get('temp_pin', True) else 'No'}\n"
        f"• <b>Quote Block:</b> {'Yes' if config.get('quote_block', True) else 'No'}\n"
        f"• <b>Log To:</b> {log_dest_lbl} | <b>Format:</b> {config.get('log_format', 'zip').upper()}"
    )
    
    # ─── SUB-MENUS ───
    if sub_menu in ["action_delay", "account_delay", "delay", "count", "batch_delay", "batch_size", "batch_action", "ba_delay"]:
        # Sub-Menu Keypad
        # steps = {"delay": 10, "count": 1, "batch_delay": 1, "batch_size": 1, "action_delay": 0.5}
        step_map = {"delay": 10, "count": 1, "batch_delay": 1, "batch_size": 1, "action_delay": 0.5, "account_delay": 0.5, "batch_action": 5, "ba_delay": 10}
        step = step_map.get(sub_menu, 1)
        step_str = f"{step}" if step < 1 else f"{int(step)}"
        
        # Label and current value
        labels = {
            "action_delay": "Action Delay", "account_delay": "Account Delay", "delay": "Group Delay", 
            "count": "Total Groups", "batch_delay": "Batch Delay", "batch_size": "Batch Size",
            "batch_action": "Batch Act", "ba_delay": "B.Act Delay"
        }
        unit_map = {
            "action_delay": "s", 
            "account_delay": "s", 
            "delay": "s", 
            "batch_delay": "m", 
            "count": "c" if config.get('group_type', 'a') == 'c' else "g", 
            "batch_size": "c" if config.get('group_type', 'a') == 'c' else "g"
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
            adj_steps = [1, 3, 5, 10]
        elif sub_menu == "batch_size":
            adj_steps = [1, 3, 5, 10]
        elif sub_menu == "batch_delay":
            adj_steps = [1, 3, 5, 10]
        
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
        per_page = 8
        s_page = state.get("session_page", 0)
        total_sessions = len(Altruix.clients)
        total_pages = (total_sessions + per_page - 1) // per_page
        
        start = s_page * per_page
        end = start + per_page
        paged_clients = Altruix.clients[start:end]
        
        text = (
            f"<blockquote expandable>"
            f"<b>👥 Multi-Session Selection</b> (Page {s_page+1}/{total_pages})\n\n"
            f"Pilih satu atau beberapa akun yang akan menjalankan task ini secara bersamaan.\n"
            f"Total Terpilih: <code>{len(selected)}</code> / <code>{total_sessions}</code>\n\n"
            f"<i>☑️ = selected | ☐ = not selected</i>"
            f"</blockquote>"
        )
        
        buttons = []
        for i, client in enumerate(paged_clients):
            actual_idx = start + i + 1
            is_sel = actual_idx in selected
            icon = "☑️" if is_sel else "☐"
            
            # 🔥 INDICATOR: Mark the session that triggered the command
            current_tag = " ⭐ [ Current ]" if actual_idx == idx else ""
            
            try:
                me = getattr(client, "me", None) or await client.get_me()
                name = me.first_name
            except: name = f"Session {actual_idx}"
            
            buttons.append([InlineKeyboardButton(f"{icon} {actual_idx}. {name}{current_tag}", callback_data=f"creategroup_tsel_{actual_idx}_{pg}", style=user_style)])
            
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

        # First / Last Navigation
        if total_pages > 2:
            buttons.append([
                InlineKeyboardButton("First", callback_data=f"creategroup_spage_0_{pg}", style=user_style),
                InlineKeyboardButton("Last", callback_data=f"creategroup_spage_{total_pages-1}_{pg}", style=user_style)
            ])
        
        buttons.append([InlineKeyboardButton("🔙 Back to Dashboard", callback_data=f"creategroup_back_submenu_{idx}_{pg}", style=user_style)])
        return text, InlineKeyboardMarkup(buttons)

    # ─── MAIN DASHBOARD ───
    is_channel = config.get('group_type', 'a') == 'c'
    type_indicator = "c" if is_channel else "g"

    buttons = [
        [
            InlineKeyboardButton(f"Acc(s): {sel_count} Sel", callback_data=f"creategroup_submenu_{idx}_{pg}_select_sessions", style=user_style),
            InlineKeyboardButton(f"Delay/Acc: {config.get('account_delay', 0.5)}s", callback_data=f"creategroup_submenu_{idx}_{pg}_account_delay", style=user_style)
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
            InlineKeyboardButton(f"B.Size: {config['batch_size']}{type_indicator}", callback_data=f"creategroup_submenu_{idx}_{pg}_batch_size", style=user_style),
            InlineKeyboardButton(f"B.Delay: {config['batch_delay']}m", callback_data=f"creategroup_submenu_{idx}_{pg}_batch_delay", style=user_style)
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
            InlineKeyboardButton(f"Log To: {'Both' if log_dest == 'both' else ('GroupLog' if log_dest == 'log_group' else 'SavedMsg')}", callback_data=f"creategroup_toggle_{idx}_{pg}_log_destination", style=user_style),
            InlineKeyboardButton(f"Log Format: {config.get('log_format', 'zip').upper()}", callback_data=f"creategroup_toggle_{idx}_{pg}_log_format", style=user_style)
        ],
        [
            InlineKeyboardButton(f"Pin First: {'Yes' if config.get('pin_first_msg', True) else 'No'}", callback_data=f"creategroup_toggle_{idx}_{pg}_pin_first_msg", style=user_style),
            InlineKeyboardButton(f"Temp Pin: {'Yes' if config.get('temp_pin', True) else 'No'}", callback_data=f"creategroup_toggle_{idx}_{pg}_temp_pin", style=user_style)
        ],
        [
            InlineKeyboardButton(f"Quote Block: {'Yes' if config.get('quote_block', True) else 'No'}", callback_data=f"creategroup_toggle_{idx}_{pg}_quote_block", style=user_style),
            InlineKeyboardButton(f"Msg Img: {'Yes' if config.get('msg_img', True) else 'No'}", callback_data=f"creategroup_toggle_{idx}_{pg}_msg_img", style=user_style)
        ],
        [
            InlineKeyboardButton("View Tasks", callback_data=f"creategroup_cached_{idx}_{pg}", style=user_style),
            InlineKeyboardButton("Info", callback_data=f"creategroup_submenu_{idx}_{pg}_info", style=user_style)
        ],
        [
            InlineKeyboardButton("✅ Run Task", callback_data=f"creategroup_run_{idx}_{pg}", style=user_style),
            InlineKeyboardButton("🔙 Back", callback_data=f"creategroup_menu_{idx}_{pg}", style=user_style)
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
            if cb.message:
                await cb.message.edit(full_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
            else:
                await cb.edit_message_text(full_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        elif message:
            await message.edit(full_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        elif state.get("ui_msg_id") and isinstance(state["ui_msg_id"], str):
            # Inline message edit via Altruix.bot
            from Main.core.client import Altruix
            await Altruix.bot.edit_inline_message_text(
                state["ui_msg_id"], 
                full_text, 
                reply_markup=reply_markup, 
                parse_mode=ParseMode.HTML
            )
    except Exception: pass

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_adj_(\d+)_(\d+)_(\w+)_([\w.]+)$"))
@iuser_check
@log_errors
async def creategroup_adjust_handler(c: Client, cb: CallbackQuery):
    match = cb.matches[0]
    idx, pg, key, action_raw = int(match.group(1)), int(match.group(2)), match.group(3), match.group(4)
    user_id = cb.from_user.id
    
    if user_id not in user_creategroup_state:
         await cb.answer("Session expired", show_alert=True)
         return
         
    conf = user_creategroup_state[user_id]["config"]
    steps = {"delay": 10, "count": 1, "batch_delay": 1, "batch_size": 1, "action_delay": 0.5, "account_delay": 0.5, "rand_len": 1, "batch_action": 5, "ba_delay": 10}
    limits = {"delay": (1, 3600), "count": (1, 1000), "batch_delay": (0, 300), "batch_size": (1, 100), "action_delay": (0.1, 30.0), "account_delay": (0.1, 30.0), "rand_len": (0, 64), "batch_action": (1, 500), "ba_delay": (10, 3600)}
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
    int_keys = ["count"]
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
        await cb.answer("Session expired", show_alert=True)
        return
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
        await cb.answer("Session expired", show_alert=True)
        return
    user_creategroup_state[user_id]["sub_menu"] = None
    await render_creategroup_ui(cb, user_creategroup_state[user_id])
    await cb.answer()

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_tsel_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_session_toggle_handler(c: Client, cb: CallbackQuery):
    s_idx, pg = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    user_id = cb.from_user.id
    if user_id not in user_creategroup_state: return await cb.answer("Session expired", show_alert=True)
    
    selected = user_creategroup_state[user_id].get("selected_sessions", [])
    if s_idx in selected:
        selected.remove(s_idx)
    else:
        selected.append(s_idx)
    
    user_creategroup_state[user_id]["selected_sessions"] = selected
    await render_creategroup_ui(cb, user_creategroup_state[user_id])
    await cb.answer()

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_spage_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_session_page_handler(c: Client, cb: CallbackQuery):
    s_page, pg = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    user_id = cb.from_user.id
    if user_id not in user_creategroup_state: return await cb.answer("Session expired", show_alert=True)
    user_creategroup_state[user_id]["session_page"] = s_page
    await render_creategroup_ui(cb, user_creategroup_state[user_id])
    await cb.answer()

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_sall_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_session_select_all_handler(c: Client, cb: CallbackQuery):
    user_id = cb.from_user.id
    if user_id not in user_creategroup_state: return await cb.answer("Session expired", show_alert=True)
    user_creategroup_state[user_id]["selected_sessions"] = list(range(1, len(Altruix.clients) + 1))
    await render_creategroup_ui(cb, user_creategroup_state[user_id])
    await cb.answer("All sessions selected")

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_dsall_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_session_deselect_all_handler(c: Client, cb: CallbackQuery):
    user_id = cb.from_user.id
    if user_id not in user_creategroup_state: return await cb.answer("Session expired", show_alert=True)
    user_creategroup_state[user_id]["selected_sessions"] = []
    await render_creategroup_ui(cb, user_creategroup_state[user_id])
    await cb.answer("All sessions deselected")

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_setv_(\d+)_(\d+)_(\w+)_(\w+)$"))
@iuser_check
@log_errors
async def creategroup_set_val_handler(c: Client, cb: CallbackQuery):
    idx, pg, key, val_raw = int(cb.matches[0].group(1)), int(cb.matches[0].group(2)), cb.matches[0].group(3), cb.matches[0].group(4)
    user_id = cb.from_user.id
    if user_id not in user_creategroup_state:
        await cb.answer("Session expired", show_alert=True)
        return
    
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
    await cb.answer()
    idx, pg, field = int(cb.matches[0].group(1)), int(cb.matches[0].group(2)), cb.matches[0].group(3)
    user_id = cb.from_user.id
    if user_id not in user_creategroup_state: return
    
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
        "ui_chat_id": cb.message.chat.id if cb.message else user_creategroup_state[user_id].get("ui_chat_id")
    })
    field_name = {"pattern": "Group Name Pattern", "username": "Username Prefix", "bots": "Bot Usernames List", "description": "Group Description"}.get(field, field.replace("_", " ").title())
    text = f"<b>📝 Memproses Input: {field_name}...</b>\n\nSilakan lihat instruksi detail pada pesan baru di bawah ini."
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data=f"creategroup_ui_{idx}_{pg}", style=user_style)]])
    
    if cb.message:
        await cb.message.edit(text, reply_markup=kb)
        chat_id = cb.message.chat.id
    else:
        await cb.edit_message_text(text, reply_markup=kb)
        chat_id = cb.from_user.id
        
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
        elif key == "log_format": conf["log_format"] = "zip" if conf.get("log_format", "txt") == "txt" else "txt"
        elif key in conf: conf[key] = not conf[key]
        elif key == "msg_img": conf["msg_img"] = not conf.get("msg_img", True)
        save_user_cg_config(user_id, conf)
        await render_creategroup_ui(cb, user_creategroup_state[user_id])
    await cb.answer()

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_upload_photo_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_upload_photo_handler(c: Client, cb: CallbackQuery):
    idx, pg, user_id = int(cb.matches[0].group(1)), int(cb.matches[0].group(2)), cb.from_user.id
    if user_id not in user_creategroup_state:
        await cb.answer("State expired", show_alert=True)
        return
        
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

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_run_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_run_handler(c: Client, cb: CallbackQuery):
    idx, pg, user_id = int(cb.matches[0].group(1)), int(cb.matches[0].group(2)), cb.from_user.id
    if user_id not in user_creategroup_state or "config" not in user_creategroup_state[user_id]:
        await cb.answer("Error: Invalid state", show_alert=True)
        return
        
    from Main.internals.settings_handlers.custom_alert_handlers import _get_session_user_id
    session_user_id = _get_session_user_id(idx)
    user_style = get_user_button_style(session_user_id)
    
    selected = user_creategroup_state[user_id].get("selected_sessions", [idx])
    sel_count = len(selected)
    
    conf = user_creategroup_state[user_id]["config"]
    photo_text = ("👤 Source Account" if conf.get('photo_source') == 'source' else "🖼 Custom Photo") + (" ✅" if conf.get('photo_source') == 'custom' and conf.get('custom_photo_id') else "")
    type_lbl = "Supergroup" if conf.get('group_type', 'a') == 'a' else "Channel"
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
        f"Apakah Anda yakin ingin menjalankan task ini di <b>{sel_count} akun</b>?"
        f"</blockquote>"
    )
    buttons = [[InlineKeyboardButton("❌ Batal", callback_data=f"creategroup_ui_{idx}_{pg}", style=user_style), InlineKeyboardButton("✅ Ya, Jalankan", callback_data=f"creategroup_confirm_task_{idx}", style=user_style)]]
    if cb.message:
        await cb.message.edit(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
    else:
        await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_confirm_task_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_confirm_task_handler(c: Client, cb: CallbackQuery):
    try:
        idx, user_id = int(cb.matches[0].group(1)), cb.from_user.id
        if user_id not in user_creategroup_state or "config" not in user_creategroup_state[user_id]:
            await cb.answer("Error: Invalid state", show_alert=True)
            return
        conf = user_creategroup_state[user_id]["config"]
        selected = user_creategroup_state[user_id].get("selected_sessions", [idx])
        if not selected: selected = [idx]
        
        # ✅ Ensure we only count valid sessions for the indicator accuracy
        selected = [s for s in selected if 1 <= s <= len(Altruix.clients)]
        if not selected: selected = [idx] # Fallback to current if all filtered out
        
        del user_creategroup_state[user_id]
        from Main.plugins.userbot.xtaskmanager import generate_task_id
        from Main.plugins.userbot.xcreategroup import creategroup_loop
        
        start_msg = f"🚀 Memulai CreateGroup Task pada <b>{len(selected)} akun</b>..."
        if cb.message:
            await cb.message.edit(start_msg, parse_mode=ParseMode.HTML)
        else:
            await cb.edit_message_text(start_msg, parse_mode=ParseMode.HTML)
            
        acc_delay = conf.get("account_delay", 0.5)
        for i, s_idx in enumerate(selected):
            if s_idx < 1 or s_idx > len(Altruix.clients): continue
            
            # Stagger startup if not the first account
            if i > 0 and acc_delay > 0:
                await asyncio.sleep(acc_delay)
                
            tid = generate_task_id("CG")
            try:
                control_msg = None
                try:
                    msg_text = f"🔄 Initializing task for Session {s_idx} [<code>{tid}</code>]..."
                    if i > 0: msg_text = f"⏳ Staggered Start ({acc_delay}s)...\n{msg_text}"
                    
                    if cb.message:
                        control_msg = await cb.message.reply(msg_text)
                    else:
                        control_msg = await c.send_message(cb.from_user.id, msg_text)
                except Exception as e:
                    from pyrogram.errors import PeerIdInvalid, UserIsBlocked
                    if isinstance(e, (PeerIdInvalid, UserIsBlocked)):
                        # Fallback: Bot fails to send PM, allow task to continue (loop will create log entry)
                        await cb.answer(f"⚠️ Session {s_idx}: Bot gagal kirim PM (silakan /start bot). Task dilanjutkan.", show_alert=True)
                    else:
                        logger.error(f"Critical error creating control message for session {s_idx}: {e}")
                        await cb.answer(f"❌ Session {s_idx}: Error kritis. Melewati session ini.", show_alert=True)
                        continue # Don't start task for this session if we hit a critical error
                
                executor = Altruix.clients[s_idx - 1] # ✅ Convert 1-based to 0-based
                bots = conf["bots"].split() if conf["bots"] else []
                asyncio.create_task(creategroup_loop(
                    user_client=executor,
                    bot_client=Altruix.bot,
                    initial_message=cb.message,
                    delay=conf["delay"],
                    count=conf["count"],
                    extra_delay_minutes=conf["batch_delay"],
                    batch_size=conf["batch_size"],
                    batch_action=conf.get("batch_action", 30),
                    ba_delay=conf.get("ba_delay", 30),
                    group_type=conf.get('group_type', 'a'),
                    name_pattern=conf["pattern"],
                    username_prefix=conf["username"],
                    bot_identifiers=bots,
                    control_message=control_msg,
                    action_delay=conf.get("action_delay", 3.0),
                    invite_bots=conf.get("invite_bots", False),
                    anon_mode=conf.get("anon_mode", True),
                    copy_messages=conf.get("copy_messages", True),
                    description=conf.get("description", "Powered by @AlphaXProject"),
                    photo_source=conf.get("photo_source", "source"),
                    custom_photo_id=conf.get("custom_photo_id"),
                    log_destination=conf.get("log_destination", "both"),
                    log_format=conf.get("log_format", "zip"),
                    pin_first_msg=conf.get("pin_first_msg", True),
                    msg_img=conf.get("msg_img", True),
                    rand_len=conf.get("rand_len", 3),
                    rand_lower=conf.get("rand_lower", False),
                    rand_upper=conf.get("rand_upper", True),
                    rand_static=conf.get("rand_static", True),
                    temp_pin=conf.get("temp_pin", True),
                    quote_block=conf.get("quote_block", True),
                    user_id=user_id,
                    task_id=tid,
                    account_idx=i+1,
                    total_accs=len(selected)
                ))
            except Exception as e:
                logger.error(f"Failed to start task for session {s_idx}: {e}")
                
        await cb.answer(f"Successfully started {len(selected)} tasks!", show_alert=True)
    except Exception as e:
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
            InlineKeyboardButton("🔄 Recurring", callback_data="noop", style=user_style), # Placeholder
            InlineKeyboardButton("✏️ Edit Last", callback_data="noop", style=user_style) # Placeholder
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data=f"creategroup_menu_{idx}_{pg}", style=user_style)
        ]
    ]
    
    if cb.message:
        await cb.message.edit(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
    else:
        await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_control_(stop|pause|resume)_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_control_handler(c: Client, cb: CallbackQuery):
    action, idx, pg = cb.matches[0].group(1), int(cb.matches[0].group(2)), int(cb.matches[0].group(3))
    from Main.plugins.userbot.xcreategroup import CREATEGROUP_TASKS
    task = CREATEGROUP_TASKS.get(f"creategroup_{cb.from_user.id}")
    
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
    from Main.plugins.userbot.xcreategroup import CREATEGROUP_TASKS
    task = CREATEGROUP_TASKS.get(f"creategroup_{cb.from_user.id}")
    
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
    if cb.message:
        await cb.message.edit(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
    else:
        await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_list_group_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_list_group_handler(c: Client, cb: CallbackQuery):
    idx, pg = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    from Main.plugins.userbot.xcreategroup import CREATEGROUP_TASKS
    task = CREATEGROUP_TASKS.get(f"creategroup_{cb.from_user.id}")
    
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
    if cb.message:
        await cb.message.edit(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
    else:
        await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

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
        elif field in ["delay", "count", "batch_delay", "batch_size", "action_delay", "account_delay"]:
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
        if user_id in user_creategroup_state:
            user_creategroup_state[user_id].update({
                "ui_msg_id": inline_msg_id,
                "ui_chat_id": chat_id if chat_id != "N/A" else None,
                "session_index": index
            })
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error in creategroup_chosen_handler: {e}")
