# xtaskmanager.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
# All rights reserved.
#
# Universal Task Manager — Monitor and Manage running asyncio tasks.
# Works across plugins (gcast, relayspam, eval, bash, etc.)

import os
import json
import html
import asyncio
import time
import logging
import traceback
from pyrogram import Client, filters, enums
from pyrogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery,
    InlineQuery, InlineQueryResultArticle, InputTextMessageContent
)
from Main import Altruix
from Main.core.types.message import Message
from Main.core.decorators import iuser_check, log_errors
from Main.utils.file_helpers import get_user_button_style

# Plugin Metadata
plugin_name = f"{os.path.basename(__file__)}"
__plugin_name__ = "xtaskmanager"
PLUGIN_VERSION = "1.0.249"

logger = logging.getLogger("altruix.xtaskmanager")
logger.setLevel(logging.INFO)

# ==================== GLOBAL TASK REGISTRY ====================
# This registry is stored on the Altruix singleton so ALL plugins can access it.
# Structure: { task_id: { "task": asyncio.Task, "name": str, "plugin": str,
#              "started_at": float, "user_id": int, "details": str, "paused": bool } }

from Main.utils.file_helpers import get_db_path

def _ensure_registry():
    """Ensure the global task registry exists on Altruix."""
    if not hasattr(Altruix, "_TASK_REGISTRY"):
        Altruix._TASK_REGISTRY = {}
    return Altruix._TASK_REGISTRY

def scan_and_merge_caches():
    """Scan plugin caches and merge interrupted tasks into the registry if not present."""
    registry = _ensure_registry()
    
    # 1. Scan CreateGroup Cache
    cg_path = get_db_path("xcreategroup_cache.json")
    logger.info(f"[TaskManager] Scanning CG cache at: {cg_path} (exists={os.path.exists(cg_path)})")
    
    if os.path.exists(cg_path):
        try:
            with open(cg_path, "r", encoding="utf-8") as f:
                raw = f.read()
            
            if not raw.strip():
                logger.warning("[TaskManager] CG cache file is empty.")
                return registry
            
            data = json.loads(raw)
            
            # Structure: {"tasks": {tid: data}, "completed": {...}}
            tasks = {}
            if isinstance(data, dict):
                if "tasks" in data and isinstance(data["tasks"], dict):
                    tasks = data["tasks"]
                elif any(k.startswith("#CG") for k in data.keys()):
                    # Fallback: flat structure where keys are TIDs directly
                    tasks = data
            
            logger.info(f"[TaskManager] Found {len(tasks)} tasks in CG cache.")
            
            merged = 0
            for tid, tdata in tasks.items():
                if tid not in registry:
                    params = tdata.get("params", {})
                    total = int(params.get("count", 0))
                    current = tdata.get("current_index", 0)
                    last_step = tdata.get("last_action", "setup")
                    
                    # Safe conversion for started_at
                    raw_start = tdata.get("start_time", 0)
                    if isinstance(raw_start, str):
                        try:
                            from datetime import datetime
                            # Handle ISO format if present
                            if "T" in raw_start:
                                started_at = datetime.fromisoformat(raw_start).timestamp()
                            else:
                                started_at = float(raw_start)
                        except:
                            started_at = time.time()
                    else:
                        started_at = float(raw_start or time.time())
                    
                    registry[tid] = {
                        "task": None,
                        "name": tdata.get("name", tdata.get("current_group_name", "CreateGroup Task")),
                        "plugin": "xcreategroup",
                        "started_at": started_at,
                        "user_id": tdata.get("user_id"),
                        "user_name": tdata.get("account_name", "Unknown"),
                        "paused": tdata.get("paused", False),
                        "details": f"⚠️ Interrupted (Progress: {current}/{total})",
                        "is_interrupted": True,
                        "extra": {
                            "current": current,
                            "total": total,
                            "attempt": tdata.get("attempt", 1),
                            "last_step": last_step
                        }
                    }
                    merged += 1
            
            logger.info(f"[TaskManager] Merged {merged} interrupted tasks into registry. Total registry: {len(registry)}")
        except Exception as e:
            logger.error(f"[TaskManager] Error merging CG cache: {e}", exc_info=True)
    else:
        logger.info("[TaskManager] No CG cache file found.")
    
    return registry

def get_all_tasks():
    """Get all tasks from the global registry, merging from cache first."""
    return scan_and_merge_caches()

def generate_task_id(prefix="T"):
    """
    Generate a short unique task ID like #T1a2b.
    Uses timestamp + counter for uniqueness.
    """
    import hashlib
    _ensure_registry()
    # Increment a simple counter
    if not hasattr(Altruix, "_TASK_COUNTER"):
        Altruix._TASK_COUNTER = 0
    Altruix._TASK_COUNTER += 1
    raw = f"{time.time()}-{Altruix._TASK_COUNTER}"
    short_hash = hashlib.md5(raw.encode()).hexdigest()[:4]
    return f"#{prefix}{short_hash}"

def register_task(task_id: str, asyncio_task: asyncio.Task, name: str,
    plugin: str, user_id: int = None, details: str = "", user_name: str = None):
    """
    Register a running asyncio.Task in the global registry.
    Called by any plugin that creates background tasks.
    
    Args:
        task_id: Unique ID (e.g. #T1a2b)
        asyncio_task: The asyncio.Task object
        name: Human-readable task name (e.g. "Global BroadCast")
        plugin: Plugin name that owns this task (e.g. "xauto_pro_gcast")
        user_id: Owner user ID
        details: Extra details for display
        user_name: Owner's first name/username
    """
    try:
        registry = _ensure_registry()
        registry[task_id] = {
            "task": asyncio_task,
            "name": name,
            "plugin": plugin,
            "started_at": time.time(),
            "user_id": user_id,
            "user_name": user_name,
            "details": details,
            "paused": False,
            "recurring": False
        }
        Altruix.log(f"[TaskManager] Registered task {task_id}: {name} ({plugin})", level=20)
    except Exception as e:
        logger.error(f"Error in register_task: {e}\n{traceback.format_exc()}")

def unregister_task(task_id: str):
    """
    Remove a task from the registry (called when task completes or is cancelled).
    
    Args:
        task_id: Unique ID of the task to remove.
    """
    try:
        registry = _ensure_registry()
        if task_id in registry:
            registry.pop(task_id, None)
            Altruix.log(f"[TaskManager] Unregistered task {task_id}", level=20)
    except Exception as e:
        logger.error(f"Error in unregister_task: {e}\n{traceback.format_exc()}")


def find_task_by_id(task_id: str) -> tuple:
    """
    Find a task in the registry by its ID.
    Supports case-insensitive matching and optional '#' prefix.
    Returns (normalized_id: str, entry: dict) or (None, None)
    """
    if not task_id:
        return None, None
        
    registry = _ensure_registry()
    
    # 1. Try exact match
    if task_id in registry:
        return task_id, registry[task_id]
        
    # 2. Try case-insensitive match (with normalized '#' prefix)
    target = task_id.lower()
    if not target.startswith("#"):
        target = f"#{target}"
        
    for tid, entry in registry.items():
        if tid.lower() == target:
            return tid, entry
            
    # 3. Try without any '#' prefix
    target_no_hash = task_id.lower().lstrip("#")
    for tid, entry in registry.items():
        if tid.lower().lstrip("#") == target_no_hash:
            return tid, entry
            
    return None, None

def cancel_task_by_id(task_id: str) -> tuple:
    """
    Cancel a task by its ID.
    Supports both active asyncio tasks and interrupted tasks from cache.
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        registry = _ensure_registry()
        if task_id not in registry:
            return False, f"Task `{task_id}` not found in registry."
        
        entry = registry[task_id]
        task_obj = entry.get("task")
        task_name = entry.get("name", "Unknown")
        plugin = entry.get("plugin", "Unknown")
        
        # 1. Sync with plugin cache to remove it permanently if applicable
        if plugin == "xcreategroup":
            try:
                from Main.plugins.userbot.xcreategroup import CREATEGROUP_TASKS, save_creategroup_cache
                if task_id in CREATEGROUP_TASKS:
                    CREATEGROUP_TASKS.pop(task_id, None)
                    asyncio.create_task(save_creategroup_cache())
                    Altruix.log(f"[TaskManager] CG Cache cleared for {task_id}", level=20)
            except Exception as e:
                logger.error(f"Error syncing CG cache on cancel: {e}")

        # 2. Handle the asyncio task object (if it exists and is running)
        if task_obj:
            if not task_obj.done():
                task_obj.cancel()
                Altruix.log(f"[TaskManager] Cancelled active task {task_id}: {task_name}", level=30)
        else:
            # If no task_obj, it's an interrupted/cached placeholder
            Altruix.log(f"[TaskManager] Removed interrupted task {task_id}: {task_name}", level=20)

        # 3. Remove from global registry
        registry.pop(task_id, None)
        return True, f"<blockquote expandable>✅ Task <b>{task_id}</b> ({task_name}) from <b>{plugin}</b> has been ended/cleared.</blockquote>"
    except Exception as e:
        logger.error(f"Error in cancel_task_by_id: {e}\n{traceback.format_exc()}")
        return False, f"❌ Error cancelling task: {str(e)}"


def pause_task_by_id(task_id: str) -> tuple:
    """
    Pause a task by its ID.
    Note: This only sets a flag; the plugin's task runner must check this flag to stop.
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        registry = _ensure_registry()
        if task_id not in registry:
            return False, f"Task `{task_id}` not found in registry."
        
        registry[task_id]["paused"] = True
        task_name = registry[task_id].get("name", "Unknown")
        plugin = registry[task_id].get("plugin")
        
        Altruix.log(f"[TaskManager] Pausing task {task_id}: {task_name} ({plugin})", level=20)
        
        # Sync with plugin-specific cache to ensure persistence across restarts
        if plugin == "xcreategroup":
            try:
                from Main.plugins.userbot.xcreategroup import CREATEGROUP_TASKS, save_creategroup_cache
                if task_id in CREATEGROUP_TASKS:
                    CREATEGROUP_TASKS[task_id]["paused"] = True
                    asyncio.create_task(save_creategroup_cache())
                    Altruix.log(f"[TaskManager] CG Cache synced (Paused) for {task_id}", level=20)
            except Exception as e:
                Altruix.log(f"[TaskManager] CG Sync Error (Pause): {e}", level=40)

        return True, f"<blockquote expandable>⏸ Task <b>{task_id}</b> ({task_name}) has been <b>Paused</b>.</blockquote>"
    except Exception as e:
        logger.error(f"Error in pause_task_by_id: {e}\n{traceback.format_exc()}")
        return False, f"❌ Error pausing task: {str(e)}"


def resume_task_by_id(task_id: str) -> tuple:
    """
    Resume a task by its ID.
    Note: Interrupted tasks must be handled via the Restore menu first.
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        registry = _ensure_registry()
        if task_id not in registry:
            return False, f"Task `{task_id}` not found in registry."
        
        entry = registry[task_id]
        task_name = entry.get("name", "Unknown")
        plugin = entry.get("plugin")
        is_interrupted = entry.get("is_interrupted", False)
        
        # Check if the task is interrupted (no active process)
        if is_interrupted:
            Altruix.log(f"[TaskManager] Cannot resume interrupted task {task_id} via simple resume. Use RESTORE menu.", level=30)
            return False, f"⚠️ Task <b>{task_id}</b> is interrupted and needs to be <b>Restored</b> first."

        registry[task_id]["paused"] = False
        Altruix.log(f"[TaskManager] Resuming task {task_id}: {task_name} ({plugin})", level=20)
        
        # Sync with plugin-specific cache
        if plugin == "xcreategroup":
            try:
                from Main.plugins.userbot.xcreategroup import CREATEGROUP_TASKS, save_creategroup_cache
                if task_id in CREATEGROUP_TASKS:
                    CREATEGROUP_TASKS[task_id]["paused"] = False
                    asyncio.create_task(save_creategroup_cache())
                    Altruix.log(f"[TaskManager] CG Cache synced (Resumed) for {task_id}", level=20)
            except Exception as e:
                Altruix.log(f"[TaskManager] CG Sync Error (Resume): {e}", level=40)

        return True, f"<blockquote expandable>▶️ Task <b>{task_id}</b> ({task_name}) has been <b>Resumed</b>.</blockquote>"
    except Exception as e:
        logger.error(f"Error in resume_task_by_id: {e}\n{traceback.format_exc()}")
        return False, f"❌ Error resuming task: {str(e)}"


async def send_task_log(client: Client, title: str, text: str):
    """Send a task-related log message to the LOG_CHAT_ID."""
    try:
        log_chat = Altruix.log_chat or Altruix.config.LOG_CHAT_ID
        if not log_chat:
            try: log_chat = await Altruix.config.get_env("LOG_CHAT_ID")
            except: pass
        
        if log_chat:
            # Use bot assistant or fallback to main bot
            bot = Altruix.bot_manager.get_bot(client.me.id) if hasattr(Altruix, 'bot_manager') else Altruix.bot
            if bot:
                # Ensure log_chat is int if it's a numeric string
                chat_id = int(log_chat) if str(log_chat).lstrip('-').isdigit() else log_chat
                full_text = (
                    f"<blockquote expandable>\n"
                    f"<b>{title}</b>\n"
                    f"{text}\n"
                    f"Account: <b>{html.escape(client.me.first_name)}</b> (<code>{client.me.id}</code>)\n"
                    f"</blockquote>"
                )
                await bot.send_message(chat_id, full_text, parse_mode=enums.ParseMode.HTML)
    except Exception as e:
        logger.error(f"Failed to send task log: {e}")

# ==================== MENU GENERATORS ====================

def gen_task_list_data(user_id: int, page: int = 1, page_size: int = 5):
    """Generate text and keyboard for the task list."""
    try:
        cleanup_stale_tasks()
        registry = get_all_tasks()
        user_style = get_user_button_style(user_id)
        
        if not registry:
            text = (
                "<blockquote expandable>"
                "📋 <b>Active Tasks</b>\n\n"
                "<i>No active tasks running.</i>"
                "</blockquote>"
            )
            return text, None

        tasks_list = list(registry.items())
        total_pages = (len(tasks_list) + page_size - 1) // page_size
        page = max(1, min(page, total_pages))
        
        start_idx = (page - 1) * page_size
        current_batch = tasks_list[start_idx:start_idx + page_size]
        
        now = time.time()
        lines = []
        buttons = []
        
        for tid, entry in current_batch:
            task_obj = entry.get("task")
            name = entry.get("name", "Unknown")
            plugin = entry.get("plugin", "?")
            started = entry.get("started_at", now)
            try: started = float(started)
            except (ValueError, TypeError): started = now
            u_name = entry.get("user_name", "Unknown")
            is_paused = entry.get("paused", False)
            is_recur = entry.get("recurring", False)
            is_interrupted = entry.get("is_interrupted", False)
            
            duration = int(now - started)
            mins, secs = divmod(duration, 60)
            hrs, mins = divmod(mins, 60)
            dur_str = f"{hrs}h{mins}m{secs}s" if hrs > 0 else (f"{mins}m{secs}s" if mins > 0 else f"{secs}s")
            
            # Determine status text and icon
            if is_interrupted:
                status_icon = "⚠️ Interrupted"
            elif is_paused:
                status_icon = "⏸️ Paused"
            else:
                status_icon = "🟢 Running"

            recur_icon = " 🔁" if is_recur else ""
            
            lines.append(
                f"<b>{tid}</b> — {name}{recur_icon}\n"
                f"   Plugin: <code>{plugin}</code> | {status_icon}\n"
                f"   Duration: {dur_str} | Owner: <b>{html.escape(str(u_name))}</b>"
            )
            
            row = [
                InlineKeyboardButton(f"⚙️ Manage {tid} — {name[:20]}", callback_data=f"taskmgr_status_{tid}", style=user_style)
            ]
            buttons.append(row)
            
        # Bulk Actions Row
        buttons.append([
            InlineKeyboardButton("Resume All", callback_data="taskmgr_ask_resumeall_all", style=user_style),
            InlineKeyboardButton("End All", callback_data="taskmgr_ask_endall_all", style=user_style),
            InlineKeyboardButton("Pause All", callback_data="taskmgr_ask_pauseall_all", style=user_style)
        ])
        
        nav_row = []
        # Prev button (Always visible)
        if page > 1:
            nav_row.append(InlineKeyboardButton("« Prev", callback_data=f"taskmgr_page_{page-1}", style=user_style))
        else:
            nav_row.append(InlineKeyboardButton("« Prev", callback_data="taskmgr_noop", style=user_style))
            
        # Page indicator
        nav_row.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="taskmgr_noop", style=user_style))
        
        # Next button (Always visible)
        if page < total_pages:
            nav_row.append(InlineKeyboardButton("Next »", callback_data=f"taskmgr_page_{page+1}", style=user_style))
        else:
            nav_row.append(InlineKeyboardButton("Next »", callback_data="taskmgr_noop", style=user_style))
            
        buttons.append(nav_row)
        
        # First and Last navigation
        buttons.append([
            InlineKeyboardButton("First", callback_data="taskmgr_page_1", style=user_style),
            InlineKeyboardButton("Last", callback_data=f"taskmgr_page_{total_pages}", style=user_style)
        ])
        
        # Refresh and Restore buttons
        buttons.append([
            InlineKeyboardButton("Refresh", callback_data=f"taskmgr_page_{page}", style=user_style),
            InlineKeyboardButton("Restore", callback_data="taskmgr_restore_1", style=user_style)
        ])

        # Close button (Single row at bottom)
        buttons.append([
            InlineKeyboardButton("Close", callback_data="taskmgr_close", style=user_style)
        ])
            
        header = f"📋 <b>Active Tasks</b> ({len(registry)} total)\n" + "━" * 18 + "\n"
        body = "\n\n".join(lines)
        footer = "\n" + "━" * 18 + "\n💡 Click buttons below to manage."
        text = f"<blockquote expandable>{header}{body}{footer}</blockquote>"
        
        return text, InlineKeyboardMarkup(buttons)
    except Exception as e:
        logger.exception(f"Error in gen_task_list_data: {e}")
        return "❌ <b>Internal error generating task list.</b>", None

def gen_task_status_data(user_id: int, tid: str):
    """Generate text and keyboard for a specific task's status."""
    try:
        actual_tid, entry = find_task_by_id(tid)
        user_style = get_user_button_style(user_id)
        
        if not actual_tid:
            return f"⚠️ Task <code>{tid}</code> not found.", None
            
        task_obj = entry.get("task")
        name = entry.get("name", "Unknown")
        plugin = entry.get("plugin", "?")
        started = entry.get("started_at", time.time())
        try: started = float(started)
        except (ValueError, TypeError): started = time.time()
        u_id = entry.get("user_id", "?")
        u_name = entry.get("user_name")
        details = entry.get("details", "")
        is_paused = entry.get("paused", False)
        is_recur = entry.get("recurring", False)
        
        duration = int(time.time() - started)
        mins, secs = divmod(duration, 60)
        hrs, mins = divmod(mins, 60)
        dur_str = f"{hrs}h{mins}m{secs}s" if hrs > 0 else (f"{mins}m{secs}s" if mins > 0 else f"{secs}s")
        
        is_interrupted = entry.get("is_interrupted", False)
        if is_interrupted:
            status = "⚠️ Interrupted"
        elif is_paused:
            status = "🟡 Paused"
        else:
            status = "🟢 Running" if task_obj and not task_obj.done() else "⚫ Done"
        
        # Uptime in minutes and seconds
        uptime_total_sec = int(time.time() - started)
        up_mins, up_secs = divmod(uptime_total_sec, 60)
        uptime_str = f"{up_mins} menit {up_secs} detik"
        
        from datetime import datetime
        start_str = datetime.fromtimestamp(started).strftime("%Y-%m-%d %H:%M:%S")

        # Plugin specific progress info
        extra = entry.get("extra", {})
        current = extra.get("current", 0)
        total = extra.get("total", 0)
        attempt = extra.get("attempt", 1)
        last_step = extra.get("last_step", "setup")

        text = (
            f"⚙️ <b>Manage Task: {actual_tid}</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"• <b>Name:</b> <code>{name}</code>\n"
            f"• <b>Plugin:</b> <code>{plugin}</code>\n"
            f"• <b>Account:</b> <b>{html.escape(str(u_name or 'Unknown'))}</b>\n"
            f"• <b>Owner ID:</b> <code>{u_id}</code>\n"
            f"• <b>Status:</b> {status}\n"
            f"• <b>Created:</b> {current} / <b>Attempt:</b> {attempt} / <b>Total:</b> {total}\n"
            f"• <b>Started:</b> <code>{start_str}</code>\n"
            f"• <b>Uptime:</b> {uptime_str}\n"
            f"• <b>Last Step:</b> <code>{last_step}</code>\n"
            f"• <b>Recurring:</b> {'✅ Enabled' if is_recur else '❌ Disabled'}\n"
        )
        text += "━━━━━━━━━━━━━━━"
        
        # Action Buttons
        row1 = []
        if is_interrupted:
            # Special button for interrupted tasks to restore directly
            row1.append(InlineKeyboardButton("♻️ Restore", callback_data=f"taskmgr_ask_dorestore_{actual_tid}", style=user_style))
        else:
            row1.append(InlineKeyboardButton("▶️ Resume" if is_paused else "⏸ Pause", 
                                             callback_data=f"taskmgr_{'pause' if not is_paused else 'resume'}_{actual_tid}", style=user_style))
        row1.append(InlineKeyboardButton("🛑 End", callback_data=f"taskmgr_ask_stop_{actual_tid}", style=user_style))

        buttons = [
            row1,
            [
                InlineKeyboardButton("🔍 View Info", callback_data=f"taskmgr_info_{actual_tid}", style=user_style),
                InlineKeyboardButton("🔁 Recur: " + ("ON" if is_recur else "OFF"), callback_data=f"taskmgr_recur_{actual_tid}", style=user_style),
            ],
            [
                InlineKeyboardButton("📋 Back", callback_data="taskmgr_page_1", style=user_style),
                InlineKeyboardButton("🔄 Refresh", callback_data=f"taskmgr_status_{actual_tid}", style=user_style)
            ]
        ]
        
        return f"<blockquote expandable>{text}</blockquote>", InlineKeyboardMarkup(buttons)
    except Exception as e:
        logger.exception(f"Error in gen_task_status_data: {e}")
        return f"❌ <b>Internal error fetching status for {tid}.</b>", None


def toggle_recurring_by_id(task_id: str) -> tuple:
    """Toggle the recurring flag for a task."""
    try:
        registry = _ensure_registry()
        if task_id not in registry:
            return False, f"Task `{task_id}` not found in registry."
        
        current = registry[task_id].get("recurring", False)
        registry[task_id]["recurring"] = not current
        state = "Enabled" if not current else "Disabled"
        task_name = registry[task_id].get("name", "Unknown")
        
        Altruix.log(f"[TaskManager] Recurring {state} for task {task_id}: {task_name}", level=20)
        return True, f"<blockquote expandable>🔁 Recurring <b>{state}</b> for task <b>{task_id}</b> ({task_name}).</blockquote>"
    except Exception as e:
        logger.error(f"Error in toggle_recurring_by_id: {e}\n{traceback.format_exc()}")
        return False, f"❌ Error toggling recurring: {str(e)}"


def gen_task_info_data(user_id: int, tid: str, page: int = 1):
    """Generate detailed task info with log pagination."""
    try:
        registry = get_all_tasks()
        if tid not in registry:
            return "❌ Task not found.", None

        entry = registry[tid]
        name = entry.get("name", "Unknown")
        plugin = entry.get("plugin", "?")
        details = str(entry.get("details", "-"))
        u_id = entry.get("user_id", "?")
        u_name = entry.get("user_name", "?")
        started = entry.get("started_at", time.time())
        
        from datetime import datetime
        start_str = datetime.fromtimestamp(started).strftime("%Y-%m-%d %H:%M:%S")
        user_style = get_user_button_style(user_id)

        # Log Pagination logic
        max_chars = 1500
        chunks = [details[i:i+max_chars] for i in range(0, len(details), max_chars)]
        total_pages = len(chunks) or 1
        if page > total_pages: page = total_pages
        if page < 1: page = 1
        
        current_log = chunks[page-1] if chunks else "-"
        
        text = (
            f"<b>📄 Task Detailed Info: {tid}</b>\n" +
            "━" * 15 + "\n" +
            f"• <b>Name:</b> <code>{name}</code>\n" +
            f"• <b>Plugin:</b> <code>{plugin}</code>\n" +
            f"• <b>Owner:</b> <code>{u_name}</code> (<code>{u_id}</code>)\n" +
            f"• <b>Started:</b> <code>{start_str}</code>\n" +
            "━" * 15 + "\n" +
            f"<b>📝 Logs/Status (Page {page}/{total_pages}):</b>\n" +
            f"<blockquote expandable>\n{html.escape(current_log)}\n</blockquote>"
        )

        buttons = []
        if total_pages > 1:
            nav = []
            if page > 1:
                nav.append(InlineKeyboardButton("⬅️ Log", callback_data=f"taskmgr_info_{tid}_{page-1}", style=user_style))
            else:
                nav.append(InlineKeyboardButton("⬅️ Log", callback_data="taskmgr_noop", style=user_style))
                
            nav.append(InlineKeyboardButton(f"📖 {page}/{total_pages}", callback_data="taskmgr_noop", style=user_style))
            
            if page < total_pages:
                nav.append(InlineKeyboardButton("Log ➡️", callback_data=f"taskmgr_info_{tid}_{page+1}", style=user_style))
            else:
                nav.append(InlineKeyboardButton("Log ➡️", callback_data="taskmgr_noop", style=user_style))
            buttons.append(nav)

        buttons.append([
            InlineKeyboardButton("🔙 Back to Status", callback_data=f"taskmgr_status_{tid}", style=user_style),
            InlineKeyboardButton("🔄 Refresh Info", callback_data=f"taskmgr_info_{tid}_{page}", style=user_style)
        ])
        
        return text, InlineKeyboardMarkup(buttons)
    except Exception as e:
        logger.error(f"Error in gen_task_info_data: {e}\n{traceback.format_exc()}")
        return f"❌ <b>Error fetching info for {tid}.</b>", None


def gen_restore_menu_data(user_id: int, page: int = 1):
    """Scan for cached tasks from known plugins and generate a restore menu."""
    try:
        all_cached = []
        user_style = get_user_button_style(user_id)
        
        # 1. Check CreateGroup Cache
        cg_cache_path = get_db_path("xcreategroup_cache.json")
        if os.path.exists(cg_cache_path):
            try:
                with open(cg_cache_path, "r") as f:
                    data = json.load(f)
                    tasks = data.get("tasks", data) if isinstance(data, dict) else {}
                    for tid, tdata in tasks.items():
                        all_cached.append({
                            "tid": tid,
                            "name": tdata.get("name", "CreateGroup Task"),
                            "plugin": "xcreategroup",
                            "progress": f"{tdata.get('current_index', 0)}/{tdata.get('params', {}).get('count', 0)}",
                            "data": tdata
                        })
            except: pass

        registry = _ensure_registry()
        all_cached = [t for t in all_cached if t["tid"] not in registry]

        if not all_cached:
            return "<blockquote expandable>📭 <b>No cached tasks found.</b>\nAll tasks are either running or cleared.</blockquote>", \
                   InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="taskmgr_page_1", style=user_style)]])

        page_size = 5
        total_pages = (len(all_cached) + page_size - 1) // page_size
        if page > total_pages: page = total_pages
        start = (page - 1) * page_size
        end = start + page_size
        current_page = all_cached[start:end]

        text = f"🔄 <b>Restore Tasks (Cache)</b>\n" + "━" * 18 + "\n"
        buttons = []
        for t in current_page:
            text += f"• <code>{t['tid']}</code> | {t['name']} ({t['progress']})\n"
            buttons.append([InlineKeyboardButton(f"♻️ Restore {t['tid']}", callback_data=f"taskmgr_ask_dorestore_{t['tid']}", style=user_style)])

        nav = []
        nav.append(InlineKeyboardButton("« Prev", callback_data=f"taskmgr_restore_{page-1}" if page > 1 else "taskmgr_noop", style=user_style))
        nav.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="taskmgr_noop", style=user_style))
        nav.append(InlineKeyboardButton("Next »", callback_data=f"taskmgr_restore_{page+1}" if page < total_pages else "taskmgr_noop", style=user_style))
        buttons.append(nav)

        buttons.append([InlineKeyboardButton("🔙 Back", callback_data="taskmgr_page_1", style=user_style)])
        
        return text, InlineKeyboardMarkup(buttons)
    except Exception as e:
        logger.error(f"Error in gen_restore_menu_data: {e}\n{traceback.format_exc()}")
        return f"❌ <b>Error scanning cache.</b>", None


def gen_confirmation_data(user_id: int, action: str, target: str):
    """Generate a confirmation (Yes/No) screen for critical actions."""
    try:
        user_style = get_user_button_style(user_id)
        
        # Mapping for display
        action_map = {
            "stop": "End/Stop Task",
            "dorestore": "Restore Task from Cache",
            "endall": "End/Clear ALL Tasks",
            "resumeall": "Resume ALL Paused Tasks",
            "pauseall": "Pause ALL Running Tasks"
        }
        display_action = action_map.get(action, action.upper())
        
        text = (
            f"<blockquote expandable>"
            f"⚠️ <b>Security Confirmation</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Are you sure you want to perform:\n"
            f"👉 <b>{display_action}</b>\n"
            f"Target: <code>{target}</code>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"<i>Action cannot be undone.</i>"
            f"</blockquote>"
        )
        
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Yes, Proceed", callback_data=f"taskmgr_confirm_{action}_{target}", style=user_style),
                InlineKeyboardButton("❌ No, Cancel", callback_data="taskmgr_page_1" if "all" in action else f"taskmgr_status_{target}", style=user_style)
            ]
        ])
        
        return text, kb
    except Exception as e:
        logger.error(f"Error in gen_confirmation_data: {e}\n{traceback.format_exc()}")
        return "❌ <b>Error generating confirmation screen.</b>", None


# ==================== CLEANUP STALE TASKS ====================
def cleanup_stale_tasks():
    """Remove tasks that have already completed from the registry."""
    try:
        registry = _ensure_registry()
        stale = [tid for tid, entry in registry.items() 
                 if entry.get("task") and entry["task"].done()]
        for tid in stale:
            registry.pop(tid, None)
        return len(stale)
    except Exception as e:
        logger.error(f"Error in cleanup_stale_tasks: {e}\n{traceback.format_exc()}")
        return 0


# ==================== COMMAND: .taskcancel ====================
@Altruix.register_on_cmd(
    ["taskcancel", "canceltask"],
    cmd_help={
        "help": "Cancel a running background task by its Task ID.",
        "example": ".taskcancel #T1a2b",
        "user_args": {
            "task_id": "The unique task ID (e.g. #T1a2b). Get IDs from .tasklist."
        }
    }
)
@iuser_check
@log_errors
async def taskcancel_cmd(client: Client, message: Message):
    """
    Cancel a running task by its Task ID.
    Usage: .taskcancel <task_id>
    """
    args = message.user_input
    if not args:
        await message.reply_msg(
            "❌ <b>Usage:</b> <code>.taskcancel &lt;task_id&gt;</code>\n"
            "💡 Use <code>.tasklist</code> to see active tasks and their IDs."
        )
        return
    
    task_id = args.strip()
    
    # Find task robustly
    actual_tid, entry = find_task_by_id(task_id)
    
    if not actual_tid:
        await message.reply_msg(f"⚠️ Task <code>{task_id}</code> not found in registry.")
        return

    success, result_msg = cancel_task_by_id(actual_tid)
    
    if success:
        await message.reply_msg(result_msg)
        # Log to Group Log
        await send_task_log(
            client, 
            "🛑 Task Cancelled (Command)", 
            f"Task ID: <code>{actual_tid}</code>"
        )
    else:
        await message.reply_msg(f"⚠️ {result_msg}")


# ==================== COMMAND: .taskpause ====================
@Altruix.register_on_cmd(
    ["taskpause"],
    cmd_help={
        "help": "Pause a running background task by its Task ID.",
        "example": ".taskpause #T1a2b",
        "user_args": {
            "task_id": "The unique task ID."
        }
    }
)
@iuser_check
@log_errors
async def taskpause_cmd(client: Client, message: Message):
    """Pause a running task by its Task ID."""
    args = message.user_input
    if not args:
        return await message.reply_msg("❌ <b>Usage:</b> <code>.taskpause &lt;task_id&gt;</code>")
    
    task_id = args.strip()
    actual_tid, _ = find_task_by_id(task_id)
    
    if not actual_tid:
        return await message.reply_msg(f"⚠️ Task <code>{task_id}</code> not found.")
    
    success, result_msg = pause_task_by_id(actual_tid)
    await (message.reply_msg(result_msg) if success else message.reply_msg(f"⚠️ {result_msg}"))


# ==================== COMMAND: .taskresume ====================
@Altruix.register_on_cmd(
    ["taskresume"],
    cmd_help={
        "help": "Resume a paused background task by its Task ID.",
        "example": ".taskresume #T1a2b",
        "user_args": {
            "task_id": "The unique task ID."
        }
    }
)
@iuser_check
@log_errors
async def taskresume_cmd(client: Client, message: Message):
    """Resume a paused task by its Task ID."""
    args = message.user_input
    if not args:
        return await message.reply_msg("❌ <b>Usage:</b> <code>.taskresume &lt;task_id&gt;</code>")
    
    task_id = args.strip()
    actual_tid, _ = find_task_by_id(task_id)
    
    if not actual_tid:
        return await message.reply_msg(f"⚠️ Task <code>{task_id}</code> not found.")
    
    success, result_msg = resume_task_by_id(actual_tid)
    await (message.reply_msg(result_msg) if success else message.reply_msg(f"⚠️ {result_msg}"))


# ==================== COMMAND: .taskstatus ====================
@Altruix.register_on_cmd(
    ["taskstatus"],
    cmd_help={
        "help": "View detailed status of a background task by its Task ID.",
        "example": ".taskstatus #T1a2b",
        "user_args": {
            "task_id": "The unique task ID."
        }
    }
)
@iuser_check
@log_errors
async def taskstatus_cmd(client: Client, message: Message):
    """View detailed status of a task by its Task ID via Inline Bot Result."""
    args = message.user_input
    if not args:
        return await message.reply_msg("❌ <b>Usage:</b> <code>.taskstatus &lt;task_id&gt;</code>")
    
    task_id = args.strip()
    actual_tid, _ = find_task_by_id(task_id)
    
    if not actual_tid:
        return await message.reply_msg(f"⚠️ Task <code>{task_id}</code> not found.")
    
    # Build query and send via Inline Bot Results
    bot_usr = Altruix.bot_manager.get_bot_username(client.me.id)
    query_str = f"taskmgr_status_{client.me.id}_{actual_tid}"
    
    try:
        res = await client.get_inline_bot_results(bot_usr, query_str)
        if res.results:
            await client.send_inline_bot_result(
                chat_id=message.chat.id,
                query_id=res.query_id,
                result_id=res.results[0].id,
                reply_to_message_id=message.id
            )
        else:
            await message.reply_msg(f"❌ Failed to get status for {actual_tid}")
    except Exception as e:
        logger.error(f"Error in taskstatus_cmd: {e}")
        await message.reply_msg(f"❌ Error: {str(e)}")


# ==================== COMMAND: .tasklist ====================
@Altruix.register_on_cmd(
    ["tasklist"],
    cmd_help={
        "help": "List all active background tasks with their IDs.",
        "example": ".tasklist"
    }
)
@iuser_check
@log_errors
async def tasklist_cmd(client: Client, message: Message):
    """
    Display all registered active tasks with pagination and inline buttons via Inline Bot Result.
    """
    bot_usr = Altruix.bot_manager.get_bot_username(client.me.id)
    query_str = f"taskmgr_list_{client.me.id}"
    
    try:
        res = await client.get_inline_bot_results(bot_usr, query_str)
        if res.results:
            await client.send_inline_bot_result(
                chat_id=message.chat.id,
                query_id=res.query_id,
                result_id=res.results[0].id,
                reply_to_message_id=message.id
            )
        else:
            await message.reply_msg("❌ Failed to get task list results.")
    except Exception as e:
        logger.error(f"Error in tasklist_cmd: {e}")
        await message.reply_msg(f"❌ Error: {str(e)}")


# ==================== INLINE HANDLER ====================

@Altruix.bot.on_inline_query(filters.regex(r"^taskmgr_(?P<type>list|status)_(?P<uid>\d+)(?:_(?P<extra>.*))?"))
async def taskmgr_inline_handler(client: Client, iq: InlineQuery):
    """Handle inline queries for task list and status menus."""
    try:
        m = iq.matches[0]
        qtype = m.group("type")
        uid = int(m.group("uid"))
        extra = m.group("extra")
        
        results = []
        if qtype == "list":
            text, kb = gen_task_list_data(uid)
            results.append(
                InlineQueryResultArticle(
                    title="Task List",
                    input_message_content=InputTextMessageContent(text, parse_mode=enums.ParseMode.HTML),
                    reply_markup=kb,
                    description="View and manage active tasks"
                )
            )
        elif qtype == "status":
            text, kb = gen_task_status_data(uid, extra)
            results.append(
                InlineQueryResultArticle(
                    title=f"Status: {extra}",
                    input_message_content=InputTextMessageContent(text, parse_mode=enums.ParseMode.HTML),
                    reply_markup=kb,
                    description=f"Detailed status for task {extra}"
                )
            )
        
        await iq.answer(results, cache_time=0, is_personal=True)
    except Exception as e:
        logger.exception(f"Error in taskmgr_inline_handler: {e}")
        # Send a generic error result
        try:
            await iq.answer([
                InlineQueryResultArticle(
                    title="❌ Error",
                    input_message_content=InputTextMessageContent(f"❌ <b>Internal Handler Error:</b> <code>{html.escape(str(e))}</code>"),
                    description="Check logs for traceback"
                )
            ], cache_time=0)
        except: pass


async def handle_restore_action(client: Client, cb: CallbackQuery, plugin: str, tid: str) -> tuple:
    """Helper to route restore actions to the correct plugin handler."""
    try:
        if plugin == "xcreategroup":
            from Main.internals.settings_handlers.creategroup_handlers import creategroup_resume_cached_handler
            # We temporarily modify cb.data to match what the handler expects
            original_data = cb.data
            cb.data = f"creategroup_restore_{tid}"
            await creategroup_resume_cached_handler(client, cb)
            cb.data = original_data # restore original data
            return True, f"♻️ Restore request sent for {tid}."
        else:
            return False, f"❌ Plugin {plugin} does not support global restore."
    except Exception as e:
        logger.error(f"Error in handle_restore_action: {e}\n{traceback.format_exc()}")
        return False, f"❌ Restore failed: {str(e)}"


# ==================== CALLBACK HANDLER ====================
@Altruix.bot.on_callback_query(filters.regex("^taskmgr_"))
async def taskmgr_callback_handler(client: Client, cb: CallbackQuery):
    """Handle callback queries for task management interactions."""
    try:
        data = cb.data.split("_")
        action = data[1]
        
        # We need user_id to resolve style. 
        # In this dashboard, we can try to get it from context or message.
        user_id = cb.from_user.id # Default to current user
        style = get_user_button_style(user_id)
        
        if action == "noop":
            return await cb.answer()
            
        if action == "close":
            await cb.answer("Dashboard closed")
            if cb.message:
                return await cb.message.delete()
            else:
                return await cb.edit_message_text("🗑 <b>Dashboard Closed</b>", parse_mode=enums.ParseMode.HTML)
            
        if action == "page":
            await cb.answer("Refreshing list...", show_alert=False)
            page = int(data[2])
            text, kb = gen_task_list_data(user_id, page=page)
            try:
                await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            except Exception:
                pass
            return

        if action == "restore":
            page = int(data[2]) if len(data) > 2 else 1
            text, kb = gen_restore_menu_data(user_id, page=page)
            try:
                await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            except Exception:
                pass
            return

        # --- Security Confirmation Flow ---
        if action == "ask":
            # format: taskmgr_ask_{real_action}_{target}
            real_action = data[2]
            target = data[3]
            text, kb = gen_confirmation_data(user_id, real_action, target)
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            return

        if action == "confirm":
            # format: taskmgr_confirm_{real_action}_{target}
            try:
                real_action = data[2]
                target = data[3]
                
                if real_action == "stop":
                    success, msg = cancel_task_by_id(target)
                elif real_action == "dorestore":
                    registry = get_all_tasks()
                    plugin = registry.get(target, {}).get("plugin", "xcreategroup")
                    success, msg = await handle_restore_action(client, cb, plugin, target)
                elif real_action == "pauseall":
                    registry = get_all_tasks()
                    count = 0
                    for tid in list(registry.keys()):
                        s, _ = pause_task_by_id(tid)
                        if s: count += 1
                    success, msg = True, f"✅ Paused {count} tasks."
                elif real_action == "resumeall":
                    registry = get_all_tasks()
                    count = 0
                    for tid in list(registry.keys()):
                        s, _ = resume_task_by_id(tid)
                        if s: count += 1
                    success, msg = True, f"✅ Resumed {count} tasks."
                elif real_action == "endall":
                    registry = get_all_tasks()
                    count = 0
                    for tid in list(registry.keys()):
                        s, _ = cancel_task_by_id(tid)
                        if s: count += 1
                    success, msg = True, f"✅ Ended {count} tasks."
                else:
                    success, msg = False, "Unknown action."

                await cb.answer(msg.replace("<b>", "").replace("</b>", "").replace("<blockquote expandable>", "").replace("</blockquote>", ""), show_alert=True)
                text, kb = gen_task_list_data(user_id)
                await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
                return
            except Exception as e:
                logger.error(f"Error in confirm action: {e}\n{traceback.format_exc()}")
                await cb.answer(f"❌ Error: {str(e)}", show_alert=True)
                return

        # --- Single Task Actions ---
        tid = data[2]
        if not tid.startswith("#"): tid = f"#{tid}"
        
        if action == "status":
            await cb.answer("Updating status...", show_alert=False)
            text, kb = gen_task_status_data(user_id, tid)
            try: await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            except: pass
            return

        if action == "info":
            await cb.answer("Refreshing info...", show_alert=False)
            page = int(data[3]) if len(data) > 3 else 1
            text, kb = gen_task_info_data(user_id, tid, page=page)
            try: await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            except: pass
            return

        if action == "pause":
            success, msg = pause_task_by_id(tid)
            await cb.answer(msg.replace("<b>", "").replace("</b>", "").replace("<blockquote expandable>", "").replace("</blockquote>", ""), show_alert=True)
            text, kb = gen_task_status_data(user_id, tid)
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            return

        if action == "resume":
            success, msg = resume_task_by_id(tid)
            await cb.answer(msg.replace("<b>", "").replace("</b>", "").replace("<blockquote expandable>", "").replace("</blockquote>", ""), show_alert=True)
            text, kb = gen_task_status_data(user_id, tid)
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            return

        if action == "recur":
            success, msg = toggle_recurring_by_id(tid)
            await cb.answer(msg.replace("<b>", "").replace("</b>", "").replace("<blockquote expandable>", "").replace("</blockquote>", ""), show_alert=True)
            text, kb = gen_task_status_data(user_id, tid)
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            return

        if action == "status":
            text, kb = gen_task_status_data(user_id, tid)
            try:
                await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            except Exception:
                pass
            return

        if action == "view":
            # Redirect to detailed info view instead of popup to avoid MESSAGE_TOO_LONG
            text, kb = gen_task_info_data(user_id, tid)
            try:
                await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            except Exception as e:
                await cb.answer(f"❌ Error rendering info: {str(e)[:50]}", show_alert=True)
            return

        if action == "pause":
            success, msg = pause_task_by_id(tid)
            await cb.answer(msg.replace("<blockquote expandable>", "").replace("</blockquote>", ""), show_alert=True)
        elif action == "resume":
            success, msg = resume_task_by_id(tid)
            await cb.answer(msg.replace("<blockquote expandable>", "").replace("</blockquote>", ""), show_alert=True)
        elif action == "stop":
            success, msg = cancel_task_by_id(tid)
            await cb.answer(msg.replace("<blockquote expandable>", "").replace("</blockquote>", ""), show_alert=True)
        elif action == "recur":
            success, msg = toggle_recurring_by_id(tid)
            await cb.answer(msg.replace("<blockquote expandable>", "").replace("</blockquote>", ""), show_alert=True)

        # Refresh current view
        msg_text = cb.message.text if cb.message else ""
        if "Task Details" in msg_text:
            text, kb = gen_task_status_data(user_id, tid)
        else:
            text, kb = gen_task_list_data(user_id)
            
        try:
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        except Exception:
            pass
    except Exception as e:
        err_trace = traceback.format_exc()
        logger.exception(f"Error in taskmgr_callback_handler: {e}")
        # Log error with full traceback to Group Log
        await send_task_log(
            client,
            "❌ Task Manager Callback Error",
            f"Error: <code>{html.escape(str(e))}</code>\n"
            f"Data: <code>{cb.data}</code>\n\n"
            f"<b>Traceback:</b>\n<pre>{html.escape(err_trace)}</pre>"
        )
        await cb.answer(f"❌ Callback Error: {str(e)}", show_alert=True)
