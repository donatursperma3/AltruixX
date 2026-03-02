# xcanceltask.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
# All rights reserved.
#
# Universal Task Canceler — Cancel any running asyncio task by its Task ID.
# Works across plugins (gcast, relayspam, eval, bash, etc.)

import os
import asyncio
import time
import logging
from pyrogram import Client, filters
from Main import Altruix
from Main.core.types.message import Message
from Main.core.decorators import iuser_check, log_errors

# Plugin Metadata
plugin_name = f"{os.path.basename(__file__)}"
__plugin_name__ = plugin_name if plugin_name else "xcanceltask"
PLUGIN_VERSION = "1.0.0"

logger = logging.getLogger("altruix.xcanceltask")
logger.setLevel(logging.INFO)

# ==================== GLOBAL TASK REGISTRY ====================
# This registry is stored on the Altruix singleton so ALL plugins can access it.
# Structure: { task_id: { "task": asyncio.Task, "name": str, "plugin": str,
#              "started_at": float, "user_id": int, "details": str } }

def _ensure_registry():
    """Ensure the global task registry exists on Altruix."""
    if not hasattr(Altruix, "_TASK_REGISTRY"):
        Altruix._TASK_REGISTRY = {}
    return Altruix._TASK_REGISTRY

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
                  plugin: str, user_id: int = None, details: str = ""):
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
    """
    registry = _ensure_registry()
    registry[task_id] = {
        "task": asyncio_task,
        "name": name,
        "plugin": plugin,
        "started_at": time.time(),
        "user_id": user_id,
        "details": details
    }
    Altruix.log(f"[TaskRegistry] Registered task {task_id}: {name} ({plugin})", level=20)

def unregister_task(task_id: str):
    """Remove a task from the registry (called when task completes or is cancelled)."""
    registry = _ensure_registry()
    if task_id in registry:
        registry.pop(task_id, None)
        Altruix.log(f"[TaskRegistry] Unregistered task {task_id}", level=20)

def get_all_tasks() -> dict:
    """Return all registered tasks."""
    return _ensure_registry()

def cancel_task_by_id(task_id: str) -> tuple:
    """
    Cancel a task by its ID.
    Returns (success: bool, message: str)
    """
    registry = _ensure_registry()
    if task_id not in registry:
        return False, f"Task `{task_id}` not found in registry."
    
    entry = registry[task_id]
    task_obj = entry.get("task")
    
    if task_obj is None:
        registry.pop(task_id, None)
        return False, f"Task `{task_id}` has no asyncio.Task object."
    
    if task_obj.done():
        registry.pop(task_id, None)
        return False, f"Task `{task_id}` already completed."
    
    # Cancel the asyncio task
    task_obj.cancel()
    task_name = entry.get("name", "Unknown")
    plugin = entry.get("plugin", "Unknown")
    registry.pop(task_id, None)
    
    Altruix.log(f"[TaskRegistry] Cancelled task {task_id}: {task_name} ({plugin})", level=30)
    return True, f"✅ Task `{task_id}` ({task_name}) from `{plugin}` has been cancelled."


# ==================== CLEANUP STALE TASKS ====================
def cleanup_stale_tasks():
    """Remove tasks that have already completed from the registry."""
    registry = _ensure_registry()
    stale = [tid for tid, entry in registry.items() 
             if entry.get("task") and entry["task"].done()]
    for tid in stale:
        registry.pop(tid, None)
    return len(stale)


# ==================== COMMAND: .canceltask ====================
@Altruix.register_on_cmd(
    ["canceltask"],
    cmd_help={
        "help": "Cancel a running background task by its Task ID.",
        "example": ".canceltask #T1a2b",
        "user_args": {
            "task_id": "The unique task ID (e.g. #T1a2b). Get IDs from .tasklist."
        }
    }
)
@iuser_check
@log_errors
async def canceltask_cmd(client: Client, message: Message):
    """
    Cancel a running task by its Task ID.
    Usage: .canceltask <task_id>
    """
    args = message.user_input
    if not args:
        await message.edit(
            "❌ <b>Usage:</b> <code>.canceltask &lt;task_id&gt;</code>\n"
            "💡 Use <code>.tasklist</code> to see active tasks and their IDs."
        )
        return
    
    task_id = args.strip()
    # Normalize: add # if missing
    if not task_id.startswith("#"):
        task_id = f"#{task_id}"
    
    success, result_msg = cancel_task_by_id(task_id)
    
    if success:
        await message.edit(result_msg)
        # Log to LOG_CHAT_ID
        try:
            log_chat = await Altruix.config.get_env("LOG_CHAT_ID")
            if log_chat:
                bot = Altruix.bot_manager.get_bot(client.me.id) if hasattr(Altruix, 'bot_manager') else Altruix.bot
                if bot:
                    await bot.send_message(
                        int(log_chat),
                        f"🛑 <b>Task Cancelled</b>\n"
                        f"Task ID: <code>{task_id}</code>\n"
                        f"By: {client.me.first_name} (ID: {client.me.id})"
                    )
        except Exception:
            pass
    else:
        await message.edit(f"⚠️ {result_msg}")


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
    Display all registered active tasks.
    Shows task ID, name, plugin, duration, and owner.
    """
    # First, clean up completed tasks
    cleaned = cleanup_stale_tasks()
    registry = get_all_tasks()
    
    if not registry:
        await message.edit(
            "📋 <b>Active Tasks</b>\n\n"
            "<i>No active tasks running.</i>"
            + (f"\n🧹 Cleaned {cleaned} stale tasks." if cleaned else "")
        )
        return
    
    lines = []
    now = time.time()
    for tid, entry in registry.items():
        task_obj = entry.get("task")
        name = entry.get("name", "Unknown")
        plugin = entry.get("plugin", "?")
        started = entry.get("started_at", now)
        user_id = entry.get("user_id", "?")
        details = entry.get("details", "")
        
        # Calculate duration
        duration = int(now - started)
        mins, secs = divmod(duration, 60)
        hrs, mins = divmod(mins, 60)
        if hrs > 0:
            dur_str = f"{hrs}h{mins}m{secs}s"
        elif mins > 0:
            dur_str = f"{mins}m{secs}s"
        else:
            dur_str = f"{secs}s"
        
        # Status
        if task_obj and not task_obj.done():
            status = "🟢 Running"
        elif task_obj and task_obj.cancelled():
            status = "🔴 Cancelled"
        elif task_obj and task_obj.done():
            status = "⚫ Done"
        else:
            status = "❓ Unknown"
        
        line = (
            f"<b>{tid}</b> — {name}\n"
            f"   Plugin: <code>{plugin}</code> | {status}\n"
            f"   Duration: {dur_str} | Owner: {user_id}"
        )
        if details:
            line += f"\n   {details}"
        lines.append(line)
    
    text = (
        f"📋 <b>Active Tasks</b> ({len(registry)} total)\n"
        + (f"🧹 Cleaned {cleaned} stale.\n" if cleaned else "")
        + "━" * 30 + "\n"
        + "\n\n".join(lines)
        + "\n━" * 30
        + "\n💡 <code>.canceltask &lt;id&gt;</code> to cancel."
    )
    
    # Truncate if too long
    if len(text) > 4000:
        text = text[:3950] + "\n\n<i>... truncated</i>"
    
    await message.edit(text)
