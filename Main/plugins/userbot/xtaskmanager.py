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
import re
import traceback
import hashlib
import sqlite3
from pyrogram import Client, filters, enums
from pyrogram.errors import QueryIdInvalid, MessageNotModified
from pyrogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery,
    InlineQuery, InlineQueryResultArticle, InputTextMessageContent
)
from pyrogram.handlers import InlineQueryHandler, CallbackQueryHandler
from Main import Altruix
from Main.core.types.message import Message
from Main.core.decorators import iuser_check, log_errors
from Main.utils.file_helpers import get_user_button_style

# Plugin Metadata
plugin_name = f"{os.path.basename(__file__)}"
__plugin_name__ = "xtaskmanager"
PLUGIN_VERSION = "1.0.255"

logger = logging.getLogger("altruix.xtaskmanager")
logger.setLevel(logging.INFO)

CALLBACK_ANSWER_TEXT_LIMIT = 180
TASK_LOG_MESSAGE_LIMIT = 3800
TASK_LOG_CHUNK_SIZE = 2500
_HTML_TAG_RE = re.compile(r"<[^>]+>")
TASKMGR_DEBUG = True
_ACTIVE_BULK_USERS = set()

def _tm_debug(message: str):
    try:
        prefix = time.strftime("%H:%M:%S")
        msg = f"[{prefix}] {str(message)}"
        print(msg)
        logger.info(msg)
    except Exception:
        pass

def _tm_error(where: str, err: Exception, **fields):
    try:
        prefix = time.strftime("%H:%M:%S")
        parts = []
        for k, v in (fields or {}).items():
            if v is None:
                continue
            parts.append(f"{k}={v}")
        meta = " ".join(parts)
        msg = f"[{prefix}] [TaskMgr][ERR] where={where} {meta} err={type(err).__name__}: {err}"
        print(msg)
        logger.error(msg, exc_info=True)
    except Exception:
        try:
            logger.error(f"[TaskMgr][ERR] where={where} err={err}", exc_info=True)
        except Exception:
            pass

def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)

def _summarize_task_entry(tid: str, entry: dict) -> str:
    try:
        plugin = entry.get("plugin", "?")
        paused = entry.get("paused", False)
        interrupted = entry.get("is_interrupted", False)
        task_obj = entry.get("task")
        done = task_obj.done() if task_obj else None
        started_at = entry.get("started_at", 0)
        return f"{tid}(plg={plugin}, paused={paused}, intr={interrupted}, has_task={bool(task_obj)}, done={done}, started={started_at})"
    except Exception:
        return f"{tid}(unavailable)"

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

def _strip_html(value: str) -> str:
    """Convert a small HTML fragment into plain text for safe alerts/log fallback."""
    return _HTML_TAG_RE.sub("", html.unescape(str(value or "")))

def _normalize_plain_text(value: str, keep_newlines: bool = False) -> str:
    """Normalize whitespace while optionally preserving line structure."""
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    if keep_newlines:
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
    return " ".join(text.split()).strip()

def _truncate_text(value: str, limit: int, suffix: str = "...") -> str:
    """Trim text to a safe character limit."""
    text = str(value or "")
    if len(text) <= limit:
        return text
    if limit <= len(suffix):
        return suffix[:limit]
    return text[: limit - len(suffix)].rstrip() + suffix

def _chunk_text(value: str, chunk_size: int) -> list:
    """Split long text into fixed-size chunks."""
    text = str(value or "")
    if not text:
        return [""]
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

def _build_task_log_payloads(title: str, text: str, account_name: str, account_id) -> list:
    """Build one or more HTML log payloads that stay within Telegram limits."""
    safe_title = html.escape(str(title or "Task Log"))
    safe_account = html.escape(str(account_name or "Unknown"))
    account_line = f"Account: <b>{safe_account}</b> (<code>{account_id}</code>)"
    rich_body = str(text or "-")
    rich_payload = (
        f"<blockquote expandable>\n"
        f"<b>{safe_title}</b>\n"
        f"{rich_body}\n"
        f"{account_line}\n"
        f"</blockquote>"
    )
    if len(rich_payload) <= TASK_LOG_MESSAGE_LIMIT:
        return [rich_payload]

    plain_body = _normalize_plain_text(_strip_html(rich_body), keep_newlines=True) or "-"
    chunks = _chunk_text(plain_body, TASK_LOG_CHUNK_SIZE)
    payloads = []
    total = len(chunks)
    for index, chunk in enumerate(chunks, start=1):
        suffix = f" (Part {index}/{total})" if total > 1 else ""
        payloads.append(
            f"<blockquote expandable>\n"
            f"<b>{safe_title}{suffix}</b>\n"
            f"<pre>{html.escape(chunk)}</pre>\n"
            f"{account_line}\n"
            f"</blockquote>"
        )
    return payloads

def _inject_status_notice(text: str, notice: str) -> str:
    """Attach a compact status banner to the top of an existing blockquote view."""
    safe_notice = html.escape(
        _truncate_text(
            _normalize_plain_text(_strip_html(notice)),
            500
        )
    )
    if not safe_notice:
        return text

    banner = f"ℹ️ <b>Status:</b> {safe_notice}\n\n"
    marker = "<blockquote expandable>"
    if text.startswith(marker):
        return text.replace(marker, marker + banner, 1)
    return f"<blockquote expandable>{banner}{text}</blockquote>"

def _format_duration(seconds: float) -> str:
    """Format seconds into human readable format: bulan, hari, jam, menit, detik"""
    if seconds < 1:
        return f"{int(seconds * 1000)} milidetik"
    
    seconds = int(seconds)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    months, days = divmod(days, 30) # Pendekatan 1 bulan = 30 hari
    
    parts = []
    if months > 0:
        parts.append(f"{months} bulan")
    if days > 0:
        parts.append(f"{days} hari")
    if hours > 0:
        parts.append(f"{hours} jam")
    if minutes > 0:
        parts.append(f"{minutes} menit")
    if seconds > 0 or not parts:
        parts.append(f"{seconds} detik")
        
    return " ".join(parts)

def _try_parse_datetime(value):
    from datetime import datetime
    if value is None:
        return None
    if hasattr(value, "strftime") and hasattr(value, "timestamp"):
        return value
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value))
        except Exception:
            return None
    s = str(value).strip()
    if not s or s == "-":
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None

def _resolve_finished_account_name(tdata: dict) -> str:
    raw = str(tdata.get("account_name") or tdata.get("account") or "").strip()
    if raw and raw.lower() not in {"unknown", "unknown account", "unknownaccount", "?"}:
        return raw

    try:
        cid = tdata.get("client_id") or tdata.get("user_id") or tdata.get("account_id")
        if cid:
            cid = int(cid)
    except Exception:
        cid = None

    if cid:
        try:
            for c in getattr(Altruix, "clients", []) or []:
                me = getattr(c, "me", None)
                if me and getattr(me, "id", None) == cid:
                    name = f"{me.first_name or ''} {me.last_name or ''}".strip()
                    return name or (me.username or "Unknown")
        except Exception:
            pass

    return raw or "Unknown"

def _resolve_finished_time_str(tdata: dict) -> str:
    from datetime import timedelta

    finish_raw = tdata.get("finish_time") or tdata.get("end_time") or tdata.get("finished_at")
    finish_dt = _try_parse_datetime(finish_raw)
    if not finish_dt:
        start_dt = _try_parse_datetime(tdata.get("start_time"))
        dur = tdata.get("total_duration")
        try:
            dur = float(dur)
        except Exception:
            dur = None
        if start_dt and dur is not None:
            finish_dt = start_dt + timedelta(seconds=max(0.0, dur))

    if not finish_dt:
        return "-"
    return finish_dt.strftime("%Y-%m-%d %H:%M:%S")

async def safe_cb_answer(cb: CallbackQuery, text: str = "", show_alert: bool = False, cache_time: int = 0) -> bool:
    """Answer callback queries safely without crashing on expired query IDs."""
    safe_text = _truncate_text(
        _normalize_plain_text(_strip_html(text)),
        CALLBACK_ANSWER_TEXT_LIMIT
    ) if text else ""
    try:
        kwargs = {"show_alert": show_alert}
        if safe_text:
            kwargs["text"] = safe_text
        if cache_time:
            kwargs["cache_time"] = cache_time
        await cb.answer(**kwargs)
        return True
    except QueryIdInvalid:
        logger.debug(f"Expired callback query ignored: {getattr(cb, 'data', 'unknown')}")
    except Exception as e:
        logger.debug(f"Failed to answer callback query safely: {e}")
    return False

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
                params = tdata.get("params", {})
                total = int(params.get("count", 0))
                current = tdata.get("current_index", 0)
                last_step = tdata.get("current_step", tdata.get("last_action", "setup"))

                if tid not in registry:
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
                        # Persist recurring flag from CreateGroup cache so TaskManager
                        # knows whether this interrupted task should be considered recurring
                        # after a restart.
                        "recurring": tdata.get("recurring", False),
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
                else:
                    # Sync extra info for existing tasks (running or paused)
                    if registry[tid].get("plugin") == "xcreategroup":
                        if "extra" not in registry[tid] or not isinstance(registry[tid]["extra"], dict):
                            registry[tid]["extra"] = {}
                        
                        registry[tid]["extra"].update({
                            "current": current,
                            "total": total,
                            "attempt": tdata.get("attempt", 1),
                            "last_step": last_step
                        })
            
            logger.info(f"[TaskManager] Merged {merged} interrupted tasks into registry. Total registry: {len(registry)}")
        except Exception as e:
            _tm_error("scan_and_merge_caches.cg", e, cg_path=cg_path)
    else:
        logger.info("[TaskManager] No CG cache file found.")
    
    # 2. Merge YTDL State (In-Memory)
    try:
        if hasattr(Altruix, "YTDL_STATE") and isinstance(Altruix.YTDL_STATE, dict):
            for tid, tdata in Altruix.YTDL_STATE.items():
                if tid not in registry:
                    registry[tid] = {
                        "task": None,
                        "name": f"🎬 {tdata.get('title', 'YouTube Tool')}",
                        "plugin": "xyt_tools",
                        "started_at": time.time(), # Fallback
                        "user_id": tdata.get("user_id"),
                        "details": f"Processing: {tdata.get('url', '-')}",
                        "is_interrupted": True
                    }
    except Exception as e:
        _tm_error("scan_and_merge_caches.ytdl", e)

    # 3. Merge YTCUT State (In-Memory)
    try:
        if hasattr(Altruix, "YTCUT_STATE") and isinstance(Altruix.YTCUT_STATE, dict):
            for tid, tdata in Altruix.YTCUT_STATE.items():
                if tid not in registry:
                    registry[tid] = {
                        "task": None,
                        "name": f"✂️ {tdata.get('title', 'YT Multi-Cut')}",
                        "plugin": "xytcut_tools",
                        "started_at": time.time(), # Fallback
                        "user_id": tdata.get("user_id"),
                        "details": f"Mode: {tdata.get('mode', 'keep').upper()}",
                        "is_interrupted": True
                    }
    except Exception as e:
        _tm_error("scan_and_merge_caches.ytcut", e)

    # 4. Merge Forward Pro Tasks (JSON & SQLite)
    # Prefer JSON for consistency with other plugins
    fwd_json = get_db_path("forward_pro_db.json")
    fwd_db = get_db_path("forward_pro.db")
    
    merged_fwd = 0
    
    # 4a. Check JSON first
    if os.path.exists(fwd_json):
        try:
            with open(fwd_json, "r", encoding="utf-8") as f:
                fwd_data = json.load(f)
                tasks = fwd_data.get("tasks", [])
                for task in tasks:
                    if task.get("is_active") == 1:
                        mode = str(task.get("mode") or "live").lower()
                        prefix = "FPL" if mode == "live" else "FPB"
                        tid = f"#{prefix}{task['id']}"
                        
                        if tid not in registry:
                            registry[tid] = {
                                "task": None,
                                "name": "Forward Pro Live" if mode == "live" else "Forward Pro Batch",
                                "plugin": "xforward_pro",
                                "started_at": time.time(),
                                "user_id": task["user_id"],
                                "details": f"Task #{task['id']}: {task['source_id']} -> {task['target_id']}",
                                "is_interrupted": True
                            }
                            merged_fwd += 1
        except Exception as e:
            _tm_error("scan_and_merge_caches.fwd_json", e, path=fwd_json)

    # 4b. Fallback to SQLite if no tasks merged from JSON
    if merged_fwd == 0 and os.path.exists(fwd_db):
        try:
            conn = sqlite3.connect(fwd_db)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM fwd_tasks WHERE is_active = 1")
            active_fwd = cursor.fetchall()
            
            for row in active_fwd:
                mode = str(row["mode"] or "live").lower()
                prefix = "FPL" if mode == "live" else "FPB"
                tid = f"#{prefix}{row['id']}"
                
                if tid not in registry:
                    registry[tid] = {
                        "task": None,
                        "name": "Forward Pro Live" if mode == "live" else "Forward Pro Batch",
                        "plugin": "xforward_pro",
                        "started_at": time.time(),
                        "user_id": row["user_id"],
                        "details": f"Task #{row['id']}: {row['source_id']} -> {row['target_id']}",
                        "is_interrupted": True
                    }
                    merged_fwd += 1
            conn.close()
        except Exception as e:
            _tm_error("scan_and_merge_caches.fwd_sqlite", e, path=fwd_db)

    if merged_fwd > 0:
        logger.info(f"[TaskManager] Merged {merged_fwd} interrupted Forward Pro tasks.")

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

def update_task_info(task_id: str, **kwargs):
    """
    Update specific fields of a task in the registry.
    Usage: update_task_info("#T1a2b", details="Processing...", extra={"current": 5})
    """
    try:
        registry = _ensure_registry()
        if task_id in registry:
            # If "extra" is in kwargs, merge it with existing extra instead of overwriting
            if "extra" in kwargs and isinstance(kwargs["extra"], dict):
                current_extra = registry[task_id].get("extra", {})
                if not isinstance(current_extra, dict):
                    current_extra = {}
                current_extra.update(kwargs["extra"])
                kwargs["extra"] = current_extra
            
            registry[task_id].update(kwargs)
            return True
    except Exception as e:
        _tm_error("update_task_info", e, task_id=task_id, keys=",".join(list(kwargs.keys())[:25]))
    return False

def register_task(task_id: str, asyncio_task: asyncio.Task, name: str,
    plugin: str, user_id: int = None, details: str = "", user_name: str = None,
    extra: dict = None):
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
        extra: Optional dictionary for plugin-specific progress info
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
            "recurring": False,
            "extra": extra or {}
        }
        Altruix.log(f"[TaskManager] Registered task {task_id}: {name} ({plugin})", level=20)
    except Exception as e:
        _tm_error("register_task", e, task_id=task_id, plugin=plugin, name=name, user_id=user_id)

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
        _tm_error("unregister_task", e, task_id=task_id)


def find_task_by_id(task_id: str) -> tuple:
    """
    Find a task in the registry by its ID.
    Supports case-insensitive matching and optional '#' prefix.
    Returns (normalized_id: str, entry: dict) or (None, None)
    """
    if not task_id:
        return None, None
        
    registry = get_all_tasks()
    
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
        if TASKMGR_DEBUG:
            _tm_debug(f"[TaskMgr][CANCEL] tid={task_id} plugin={plugin} name={task_name} has_task={bool(task_obj)} done={(task_obj.done() if task_obj else None)}")
        
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
        _tm_error("cancel_task_by_id", e, task_id=task_id)
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
        if TASKMGR_DEBUG:
            _tm_debug(f"[TaskMgr][PAUSE] tid={task_id} plugin={plugin} name={task_name}")
        
        Altruix.log(f"[TaskManager] Pausing task {task_id}: {task_name} ({plugin})", level=20)
        
        # Sync with plugin-specific cache to ensure persistence across restarts
        if plugin == "xcreategroup":
            try:
                from Main.plugins.userbot.xcreategroup import CREATEGROUP_TASKS, save_creategroup_cache
                if task_id in CREATEGROUP_TASKS:
                    CREATEGROUP_TASKS[task_id]["paused"] = True
                    pe = CREATEGROUP_TASKS[task_id].get("pause_event")
                    if pe:
                        try:
                            pe.clear()
                        except Exception:
                            pass
                    asyncio.create_task(save_creategroup_cache())
                    Altruix.log(f"[TaskManager] CG Cache synced (Paused) for {task_id}", level=20)
            except Exception as e:
                Altruix.log(f"[TaskManager] CG Sync Error (Pause): {e}", level=40)

        return True, f"<blockquote expandable>⏸ Task <b>{task_id}</b> ({task_name}) has been <b>Paused</b>.</blockquote>"
    except Exception as e:
        _tm_error("pause_task_by_id", e, task_id=task_id)
        return False, f"❌ Error pausing task: {str(e)}"


async def resume_task_by_id(task_id: str) -> tuple:
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
        if TASKMGR_DEBUG:
            _tm_debug(f"[TaskMgr][RESUME] tid={task_id} plugin={plugin} name={task_name} interrupted={is_interrupted}")
        
        # Check if the task is interrupted (no active process)
        if is_interrupted:
            Altruix.log(f"[TaskManager] Cannot resume interrupted task {task_id} via simple resume. Using RESTORE logic.", level=20)
            s, restore_msg = await handle_restore_action(Altruix.bot, None, plugin, task_id, silent=True)
            return s, restore_msg

        registry[task_id]["paused"] = False
        Altruix.log(f"[TaskManager] Resuming task {task_id}: {task_name} ({plugin})", level=20)
        
        # Sync with plugin-specific cache
        if plugin == "xcreategroup":
            try:
                from Main.plugins.userbot.xcreategroup import CREATEGROUP_TASKS, save_creategroup_cache
                if task_id in CREATEGROUP_TASKS:
                    CREATEGROUP_TASKS[task_id]["paused"] = False
                    pe = CREATEGROUP_TASKS[task_id].get("pause_event")
                    if pe:
                        try:
                            pe.set()
                        except Exception:
                            pass
                    asyncio.create_task(save_creategroup_cache())
                    Altruix.log(f"[TaskManager] CG Cache synced (Resumed) for {task_id}", level=20)
            except Exception as e:
                Altruix.log(f"[TaskManager] CG Sync Error (Resume): {e}", level=40)

        return True, f"<blockquote expandable>▶️ Task <b>{task_id}</b> ({task_name}) has been <b>Resumed</b>.</blockquote>"
    except Exception as e:
        _tm_error("resume_task_by_id", e, task_id=task_id)
        return False, f"❌ Error resuming task: {str(e)}"


async def send_task_log(client: Client, title: str, text: str):
    """Send a task-related log message to the LOG_CHAT_ID."""
    try:
        log_chat = Altruix.log_chat or Altruix.config.LOG_CHAT_ID
        if not log_chat:
            try:
                log_chat = await Altruix.config.get_env("LOG_CHAT_ID")
            except Exception as e:
                logger.debug(f"Failed to get LOG_CHAT_ID from config: {e}")
                pass
        
        if log_chat:
            # Use bot assistant or fallback to main bot
            bot = Altruix.bot_manager.get_bot(client.me.id) if hasattr(Altruix, 'bot_manager') else Altruix.bot
            if bot:
                # Ensure log_chat is int if it's a numeric string
                chat_id = int(log_chat) if str(log_chat).lstrip('-').isdigit() else log_chat
                account_name = getattr(client.me, "first_name", "Unknown")
                payloads = _build_task_log_payloads(title, text, account_name, client.me.id)
                for payload in payloads:
                    await bot.send_message(chat_id, payload, parse_mode=enums.ParseMode.HTML)
    except Exception as e:
        _tm_error("send_task_log", e, title=title)

# ==================== MENU GENERATORS ====================

def get_filtered_tasks(task_filter: str = None) -> list:
    """Get all tasks matching the specified filter, returned as a sorted list of (tid, entry)."""
    registry = get_all_tasks()
    if task_filter is None:
        task_filter = get_task_filter()
        
    filtered = []
    for tid, entry in registry.items():
        is_paused = entry.get("paused", False)
        is_interrupted = entry.get("is_interrupted", False)
        
        if task_filter == "all":
            filtered.append((tid, entry))
        elif task_filter == "running":
            if not is_paused and not is_interrupted:
                filtered.append((tid, entry))
        elif task_filter == "interrupted":
            if is_interrupted:
                filtered.append((tid, entry))
        elif task_filter == "pause":
            if is_paused and not is_interrupted:
                filtered.append((tid, entry))
    
    # Sort by started_at descending (newest first) to ensure stable ordering
    filtered.sort(key=lambda x: (_safe_float(x[1].get("started_at", 0.0), 0.0), str(x[0])), reverse=True)
    return filtered

def gen_task_list_data(user_id: int, page: int = 1, page_size: int = 5, task_filter: str = None):
    """Generate text and keyboard for the task list."""
    try:
        cleanup_stale_tasks()
        user_style = get_user_button_style(user_id)
        from datetime import datetime
        last_update_str = datetime.now().strftime("%H:%M:%S")
        
        if task_filter is None:
            task_filter = get_task_filter()
        
        # Define filter labels
        filter_labels = {
            "all": "All",
            "running": "Running",
            "interrupted": "Intrrupted",
            "pause": "Paused"
        }
        
        # Apply filtering (returns a sorted list of tuples)
        tasks_list = get_filtered_tasks(task_filter)
        total_tasks_count = len(get_all_tasks())

        # Filter Buttons Row
        filter_buttons = []
        for f_key, f_label in filter_labels.items():
            # Add brackets to the active filter
            display_label = f"[{f_label}]" if task_filter == f_key else f_label
            filter_buttons.append(InlineKeyboardButton(display_label, callback_data=f"taskmgr_filter_{f_key}", style=user_style))
        
        if not tasks_list:
            text = (
                "<blockquote expandable>"
                f"📋 <b>Active Tasks ({filter_labels.get(task_filter)})</b>\n\n"
                "<i>No tasks found matching this filter.</i>"
                f"\n\n• Last Update: <code>{last_update_str}</code>"
                "</blockquote>"
            )
            # Still show filter buttons even if empty
            return text, InlineKeyboardMarkup([
                filter_buttons, 
                [InlineKeyboardButton("View Finished Task", callback_data="taskmgr_finished_1", style=user_style)],
                [InlineKeyboardButton("Refresh", callback_data=f"taskmgr_page_1", style=user_style)], 
                [InlineKeyboardButton("Close", callback_data="taskmgr_close", style=user_style)]
            ])

        total_pages = (len(tasks_list) + page_size - 1) // page_size
        page = max(1, min(page, total_pages))
        
        start_idx = (page - 1) * page_size
        current_batch = tasks_list[start_idx:start_idx + page_size]
        
        now = time.time()
        lines = []
        buttons = []
        
        # Add filter buttons as the first row
        buttons.append(filter_buttons)
        
        # Finished Tasks Button Row
        buttons.append([
            InlineKeyboardButton("View Finished Task", callback_data="taskmgr_finished_1", style=user_style)
        ])
        
        for tid, entry in current_batch:
            task_obj = entry.get("task")
            name = str(entry.get("name") or "Unknown")
            plugin = str(entry.get("plugin") or "?")
            started = entry.get("started_at", now)
            try: started = float(started)
            except (ValueError, TypeError): started = now
            u_name = str(entry.get("user_name") or "Unknown")
            is_paused = entry.get("paused", False)
            is_recur = entry.get("recurring", False)
            is_interrupted = entry.get("is_interrupted", False)
            
            duration = int(now - started)
            dur_str = _format_duration(duration)
            
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
                f"   Duration: {dur_str} | Owner: <spoiler><b>{html.escape(str(u_name))}</b></spoiler>"
            )
            
            row = [
                InlineKeyboardButton(f"⚙️ Manage {tid} — {name[:20]}", callback_data=f"taskmgr_status_{tid}", style=user_style)
            ]
            buttons.append(row)
            
        # Delay Per-Resume Button Row
        current_delay = get_delay_per_resume()
        buttons.append([
            InlineKeyboardButton(f"⏳ Delay/Resume: {current_delay}s", callback_data="taskmgr_delaymenu", style=user_style)
        ])
        
        # Bulk Actions Row
        buttons.append([
            InlineKeyboardButton("Resume All", callback_data="taskmgr_ask_resumeall_all", style=user_style),
            InlineKeyboardButton("End All", callback_data="taskmgr_ask_endall_all", style=user_style),
            InlineKeyboardButton("Pause All", callback_data="taskmgr_ask_pauseall_all", style=user_style)
        ])
        
        # Page Actions Row
        buttons.append([
            InlineKeyboardButton("Resume Page", callback_data=f"taskmgr_ask_resumepage_{page}", style=user_style),
            InlineKeyboardButton("End Page", callback_data=f"taskmgr_ask_endpage_{page}", style=user_style),
            InlineKeyboardButton("Pause Page", callback_data=f"taskmgr_ask_pausepage_{page}", style=user_style)
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

        jump_row = []
        if page > 1:
            jump_back = max(1, page - 5)
            jump_row.append(InlineKeyboardButton("« 5 Prev ", callback_data=f"taskmgr_page_{jump_back}", style=user_style))
        else:
            jump_row.append(InlineKeyboardButton("« 5 Prev ", callback_data="taskmgr_noop", style=user_style))

        if page < total_pages:
            jump_next = min(total_pages, page + 5)
            jump_row.append(InlineKeyboardButton("Next 5 »", callback_data=f"taskmgr_page_{jump_next}", style=user_style))
        else:
            jump_row.append(InlineKeyboardButton("Next 5 »", callback_data="taskmgr_noop", style=user_style))

        buttons.append(jump_row)
        
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
            
        header = f"📋 <b>Active Tasks ({filter_labels.get(task_filter, 'All')})</b> ({len(tasks_list)} filtered / {total_tasks_count} total)\n" + "━" * 18 + "\n"
        body = "\n\n".join(lines)
        footer = "\n" + "━" * 18 + "\n💡 Click buttons below to manage.\n• Last Update: <code>" + last_update_str + "</code>"
        text = f"<blockquote expandable>{header}{body}{footer}</blockquote>"
        
        return text, InlineKeyboardMarkup(buttons)
    except Exception as e:
        _tm_error("gen_task_list_data", e, user_id=user_id, page=page, page_size=page_size, task_filter=task_filter)
        return "❌ <b>Internal error generating task list.</b>", None

def gen_task_status_data(user_id: int, tid: str):
    """Generate text and keyboard for a specific task's status."""
    try:
        # Refresh registry from caches to ensure 'Last Step' and progress are up-to-date
        get_all_tasks()
        
        actual_tid, entry = find_task_by_id(tid)
        user_style = get_user_button_style(user_id)
        
        if not actual_tid:
            text = (
                f"<blockquote expandable>"
                f"❌ <b>Task not found.</b>\n"
                f"━━━━━━━━━━━━━━━\n"
                f"Task: <code>{html.escape(str(tid))}</code>\n"
                f"━━━━━━━━━━━━━━━\n"
                f"<i>Task mungkin sudah selesai / terhapus dari registry. Coba Refresh list.</i>"
                f"</blockquote>"
            )
            kb = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📋 Back", callback_data="taskmgr_page_1", style=user_style),
                    InlineKeyboardButton("🔄 Refresh", callback_data="taskmgr_page_1", style=user_style)
                ]
            ])
            return text, kb
            
        task_obj = entry.get("task")
        name = str(entry.get("name") or "Unknown")
        plugin = str(entry.get("plugin") or "?")
        started = entry.get("started_at", time.time())
        try: started = float(started)
        except (ValueError, TypeError): started = time.time()
        u_id = entry.get("user_id", "?")
        u_name = str(entry.get("user_name") or "Unknown")
        details = str(entry.get("details", ""))
        is_paused = entry.get("paused", False)
        is_recur = entry.get("recurring", False)
        
        is_interrupted = entry.get("is_interrupted", False)
        if is_interrupted:
            status = "⚠️ Interrupted"
        elif is_paused:
            status = "🟡 Paused"
        else:
            status = "🟢 Running" if task_obj and not task_obj.done() else "⚫ Done"
        
        # Uptime in human readable format
        uptime_total_sec = int(time.time() - started)
        uptime_str = _format_duration(uptime_total_sec)
        
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
        _tm_error("gen_task_status_data", e, user_id=user_id, tid=tid)
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
        # If this task belongs to CreateGroup, mirror the recurring flag into
        # the plugin's in-memory cache and persist it so the flag survives restarts.
        try:
            if registry[task_id].get("plugin") == "xcreategroup":
                from Main.plugins.userbot.xcreategroup import CREATEGROUP_TASKS, save_creategroup_cache
                if task_id in CREATEGROUP_TASKS:
                    CREATEGROUP_TASKS[task_id]["recurring"] = registry[task_id]["recurring"]
                    # Persist asynchronously
                    try:
                        import asyncio as _asyncio
                        _asyncio.create_task(save_creategroup_cache())
                        Altruix.log(f"[TaskManager] Synced recurring flag to CG cache for {task_id}", level=20)
                    except Exception:
                        # Best-effort: if async create_task fails, call save synchronously
                        try:
                            save_creategroup_cache()
                        except Exception:
                            pass
        except Exception as _e:
            _tm_error("toggle_recurring_by_id.sync", _e, task_id=task_id)
        return True, f"<blockquote expandable>🔁 Recurring <b>{state}</b> for task <b>{task_id}</b> ({task_name}).</blockquote>"
    except Exception as e:
        _tm_error("toggle_recurring_by_id", e, task_id=task_id)
        return False, f"❌ Error toggling recurring: {str(e)}"


def gen_task_info_data(user_id: int, tid: str, page: int = 1):
    """Generate detailed task info with log pagination."""
    try:
        registry = get_all_tasks()
        if tid not in registry:
            user_style = get_user_button_style(user_id)
            text = (
                f"<blockquote expandable>"
                f"❌ <b>Task not found.</b>\n"
                f"━━━━━━━━━━━━━━━\n"
                f"Task: <code>{html.escape(str(tid))}</code>\n"
                f"━━━━━━━━━━━━━━━\n"
                f"<i>Task mungkin sudah selesai / terhapus dari registry.</i>"
                f"</blockquote>"
            )
            kb = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🔙 Back", callback_data=f"taskmgr_status_{tid}", style=user_style),
                    InlineKeyboardButton("📋 Task List", callback_data="taskmgr_page_1", style=user_style)
                ]
            ])
            return text, kb

        entry = registry[tid]
        name = str(entry.get("name") or "Unknown")
        plugin = str(entry.get("plugin") or "?")
        details = str(entry.get("details") or "-")
        u_id = entry.get("user_id", "?")
        u_name = str(entry.get("user_name") or "?")
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
        _tm_error("gen_task_info_data", e, user_id=user_id, tid=tid, page=page)
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
                            "name": str(tdata.get("name") or "CreateGroup Task"),
                            "plugin": "xcreategroup",
                            "progress": f"{tdata.get('current_index', 0)}/{tdata.get('params', {}).get('count', 0)}",
                            "data": tdata
                        })
            except Exception as e:
                logger.warning(f"Error parsing CG cache tasks: {e}")
                pass

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
        _tm_error("gen_restore_menu_data", e, user_id=user_id, page=page)
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
            "pauseall": "Pause ALL Running Tasks",
            "resumepage": f"Resume Tasks on Page {target}",
            "endpage": f"End Tasks on Page {target}",
            "pausepage": f"Pause Tasks on Page {target}",
            "cache": "Clear Cache Database"
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
        
        back_callback = "taskmgr_page_1"
        if action == "cache":
            back_callback = "taskmgr_cachemgr"
        elif "all" in action:
            back_callback = "taskmgr_page_1"
        elif "page" in action:
            back_callback = f"taskmgr_page_{target}"
        else:
            back_callback = f"taskmgr_status_{target}"
            
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Yes, Proceed", callback_data=f"taskmgr_confirm_{action}_{target}", style=user_style),
                InlineKeyboardButton("❌ No, Cancel", callback_data=back_callback, style=user_style)
            ]
        ])
        
        return text, kb
    except Exception as e:
        _tm_error("gen_confirmation_data", e, user_id=user_id, action=action, target=target)
        return "❌ <b>Error generating confirmation screen.</b>", None


async def _background_bulk_action(cb: CallbackQuery, targets: list, action_fn, action_name: str, user_id: int, target_page: int):
    """
    Jalankan bulk action (pause/end) di background agar callback query tidak nge-freeze/timeout.
    """
    if user_id in _ACTIVE_BULK_USERS:
        if TASKMGR_DEBUG:
            _tm_debug(f"[TaskMgr][BULK_ACTION_SKIP] User {user_id} already has a bulk action in progress.")
        return
    
    _ACTIVE_BULK_USERS.add(user_id)
    count = 0
    total = len(targets or [])
    failures = []
    if TASKMGR_DEBUG:
        sample = ", ".join([str(x) for x in (targets or [])[:10]])
        _tm_debug(f"[TaskMgr][BULK_START] {action_name} total={total} page={target_page} sample=[{sample}]")
    try:
        for tid in targets:
            try:
                # Periksa apakah tid valid di registry sebelum eksekusi
                _, entry = find_task_by_id(tid)
                if not entry:
                    if TASKMGR_DEBUG:
                        failures.append(f"{tid}:not_found")
                    continue
                    
                s, _ = action_fn(tid)
                if s:
                    count += 1
                else:
                    if TASKMGR_DEBUG:
                        failures.append(f"{tid}:false")
            except Exception as e:
                logger.debug(f"Bulk action failed for {tid}: {e}")
                if TASKMGR_DEBUG:
                    failures.append(f"{tid}:{type(e).__name__}")
                continue

        try:
            msg = f"✅ {action_name} selesai: {count} task diproses."
            text, kb = gen_task_list_data(user_id, page=target_page)
            text = _inject_status_notice(text, msg)
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        except Exception:
            pass
    except Exception as e:
        _tm_error("_background_bulk_action", e, action_name=action_name, user_id=user_id, target_page=target_page)
    finally:
        _ACTIVE_BULK_USERS.discard(user_id)
        if TASKMGR_DEBUG:
            fail_preview = ", ".join(failures[:10])
            _tm_debug(f"[TaskMgr][BULK_DONE] {action_name} ok={count}/{total} fail_count={len(failures)} fail_sample=[{fail_preview}]")


SETTINGS_FILE = get_db_path("taskmanager_settings.json")

def get_task_filter() -> str:
    """Get the current task filter from settings cache."""
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("task_filter", "all")
    except Exception as e:
        _tm_error("get_task_filter", e)
    return "all"

def save_task_filter(task_filter: str):
    """Save the task filter to settings cache."""
    try:
        data = {}
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                logger.debug(f"Could not load existing settings file, creating new: {e}")
        data["task_filter"] = task_filter
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        _tm_error("save_task_filter", e, task_filter=task_filter)

def get_delay_per_resume() -> float:
    """Get the delay per resume value in seconds from settings cache."""
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return float(data.get("delay_per_resume", 3.0)) # Default to 3.0 seconds
    except Exception as e:
        _tm_error("get_delay_per_resume", e)
    return 3.0 # Default fallback

def save_delay_per_resume(delay: float):
    """Save the delay per resume value in seconds to settings cache."""
    try:
        data = {}
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                logger.debug(f"Could not load existing settings file, creating new: {e}")
        data["delay_per_resume"] = delay
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        _tm_error("save_delay_per_resume", e, delay=delay)

def gen_delay_menu_data(user_id: int):
    """Generate text and keyboard for configuring delay per-resume settings."""
    try:
        user_style = get_user_button_style(user_id)
        current_delay = get_delay_per_resume()
        
        text = (
            f"<blockquote expandable>"
            f"⏳ <b>Configure Delay Per-Resume</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"• Current Delay: <b>{current_delay}s</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Configure the time delay applied between resuming successive tasks when clicking 'Resume All'.\n"
            f"This acts as a safety cooldown to prevent flood waits or CPU spikes.\n"
            f"</blockquote>"
        )
        
        buttons = [
            [
                InlineKeyboardButton("-5s", callback_data="taskmgr_setdelay_-5.0", style=user_style),
                InlineKeyboardButton("-1s", callback_data="taskmgr_setdelay_-1.0", style=user_style),
                InlineKeyboardButton("+1s", callback_data="taskmgr_setdelay_+1.0", style=user_style),
                InlineKeyboardButton("+5s", callback_data="taskmgr_setdelay_+5.0", style=user_style)
            ],
            [
                InlineKeyboardButton("0s (Instant)", callback_data="taskmgr_setdelay_0.0", style=user_style),
                InlineKeyboardButton("3s (Default)", callback_data="taskmgr_setdelay_3.0", style=user_style),
                InlineKeyboardButton("5s", callback_data="taskmgr_setdelay_5.0", style=user_style),
                InlineKeyboardButton("10s", callback_data="taskmgr_setdelay_10.0", style=user_style)
            ],
            [
                InlineKeyboardButton("📋 Back to Task List", callback_data="taskmgr_page_1", style=user_style)
            ]
        ]
        
        return text, InlineKeyboardMarkup(buttons)
    except Exception as e:
        _tm_error("gen_delay_menu_data", e, user_id=user_id)
        return "❌ <b>Error generating delay menu.</b>", None


def gen_finished_tasks_data(user_id: int, page: int = 1):
    """Scan for finished tasks from known plugins and generate a finished tasks menu."""
    try:
        all_finished = []
        user_style = get_user_button_style(user_id)
        
        # 1. Check CreateGroup Cache for completed tasks
        cg_cache_path = get_db_path("xcreategroup_cache.json")
        if os.path.exists(cg_cache_path):
            try:
                with open(cg_cache_path, "r") as f:
                    data = json.load(f)
                    completed = data.get("completed", {})
                    for tid, tdata in completed.items():
                        all_finished.append({
                            "tid": tid,
                            "name": str(tdata.get("name") or "CreateGroup Task"),
                            "plugin": "xcreategroup",
                            "status": tdata.get("status", "completed"),
                            "progress": f"{len(tdata.get('created_groups', []))}/{tdata.get('count', 0)}",
                            "time": tdata.get("start_time", "-"),
                            "finish_time": _resolve_finished_time_str(tdata),
                            "account": _resolve_finished_account_name(tdata)
                        })
            except Exception as e:
                logger.warning(f"Error reading finished tasks from CG cache: {e}")

        # 2. Check in-memory COMPLETED_CREATEGROUP_TASKS
        try:
            from Main.plugins.userbot.xcreategroup import COMPLETED_CREATEGROUP_TASKS
            for tid, tdata in COMPLETED_CREATEGROUP_TASKS.items():
                if not any(f["tid"] == tid for f in all_finished):
                    all_finished.append({
                        "tid": tid,
                        "name": str(tdata.get("name") or "CreateGroup Task"),
                        "plugin": "xcreategroup",
                        "status": tdata.get("status", "completed"),
                        "progress": f"{len(tdata.get('created_groups', []))}/{tdata.get('count', 0)}",
                        "time": tdata.get("start_time").strftime('%Y-%m-%d %H:%M:%S') if hasattr(tdata.get("start_time"), "strftime") else str(tdata.get("start_time") or "-"),
                        "finish_time": _resolve_finished_time_str(tdata),
                        "account": _resolve_finished_account_name(tdata)
                    })
        except Exception as e:
            logger.debug(f"Failed to read in-memory COMPLETED_CREATEGROUP_TASKS: {e}")

        if not all_finished:
            return "<blockquote expandable>📭 <b>No finished tasks found.</b></blockquote>", \
                   InlineKeyboardMarkup([
                       [InlineKeyboardButton("🔙 Back", callback_data="taskmgr_page_1", style=user_style)],
                       [InlineKeyboardButton("⚙️ Manage Cache", callback_data="taskmgr_cachemgr", style=user_style)]
                   ])

        # Sort by time if possible (descending)
        all_finished.reverse() 

        page_size = 5
        total_pages = (len(all_finished) + page_size - 1) // page_size
        if page > total_pages: page = total_pages
        start = (page - 1) * page_size
        end = start + page_size
        current_page = all_finished[start:end]

        text = f"✅ <b>Finished Tasks History</b>\n" + "━" * 18 + "\n"
        buttons = []
        for t in current_page:
            status_icon = "✅" if t['status'] == "completed" else "❌"
            text += f"{status_icon} <code>{t['tid']}</code> | {t['name']} ({t['progress']}) | Owner: <b>{html.escape(t['account'])}</b> | Selesai: <code>{html.escape(str(t.get('finish_time') or '-'))}</code>\n"
            # Since these are finished, we might not have specific management for them here,
            # but we could add a "Re-run" or "View Log" if supported.
            # For now, just listing.
        
        nav = []
        nav.append(InlineKeyboardButton("« Prev", callback_data=f"taskmgr_finished_{page-1}" if page > 1 else "taskmgr_noop", style=user_style))
        nav.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="taskmgr_noop", style=user_style))
        nav.append(InlineKeyboardButton("Next »", callback_data=f"taskmgr_finished_{page+1}" if page < total_pages else "taskmgr_noop", style=user_style))
        buttons.append(nav)

        # First and Last navigation
        buttons.append([
            InlineKeyboardButton("First", callback_data="taskmgr_finished_1", style=user_style),
            InlineKeyboardButton("Last", callback_data=f"taskmgr_finished_{total_pages}", style=user_style)
        ])

        buttons.append([
            InlineKeyboardButton("🔙 Back", callback_data="taskmgr_page_1", style=user_style),
            InlineKeyboardButton("⚙️ Manage Cache", callback_data="taskmgr_cachemgr", style=user_style)
        ])
        
        return text, InlineKeyboardMarkup(buttons)
    except Exception as e:
        _tm_error("gen_finished_tasks_data", e, user_id=user_id, page=page)
        return f"❌ <b>Error scanning finished tasks.</b>", None

def gen_cache_manager_data(user_id: int):
    """Generate text and keyboard for cache management."""
    try:
        user_style = get_user_button_style(user_id)
        cg_cache_path = get_db_path("xcreategroup_cache.json")
        
        cache_info = "📁 <b>Cache Management</b>\n" + "━" * 18 + "\n"
        
        total_size = 0
        file_stats = []
        
        if os.path.exists(cg_cache_path):
            size = os.path.getsize(cg_cache_path)
            total_size += size
            file_stats.append(f"• <code>xcreategroup_cache.json</code>: <b>{size / 1024:.2f} KB</b>")
        
        # Add other potential cache files here
        settings_size = os.path.getsize(SETTINGS_FILE) if os.path.exists(SETTINGS_FILE) else 0
        total_size += settings_size
        file_stats.append(f"• <code>taskmanager_settings.json</code>: <b>{settings_size / 1024:.2f} KB</b>")
        
        cache_info += "\n".join(file_stats)
        cache_info += f"\n\n📊 Total Cache Size: <b>{total_size / 1024:.2f} KB</b>\n"
        cache_info += "━━━━━━━━━━━━━━━\n"
        cache_info += "💡 Membersihkan cache akan menghapus riwayat task yang sudah selesai dan task yang terinterupsi."
        
        buttons = [
            [
                InlineKeyboardButton("🔄 Update/Sync Cache", callback_data="taskmgr_cache_update", style=user_style),
                InlineKeyboardButton("🗑 Clear Cache", callback_data="taskmgr_ask_cache_clear", style=user_style)
            ],
            [
                InlineKeyboardButton("🔙 Back to Finished Tasks", callback_data="taskmgr_finished_1", style=user_style)
            ]
        ]
        
        return f"<blockquote expandable>{cache_info}</blockquote>", InlineKeyboardMarkup(buttons)
    except Exception as e:
        _tm_error("gen_cache_manager_data", e, user_id=user_id)
        return "❌ <b>Error generating cache manager.</b>", None

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
        _tm_error("cleanup_stale_tasks", e)
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
    
    success, result_msg = await resume_task_by_id(actual_tid)
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
            # Pass saved filter to inline handler
            current_filter = get_task_filter()
            text, kb = gen_task_list_data(uid, task_filter=current_filter)
            results.append(
                InlineQueryResultArticle(
                    title=f"Task List ({current_filter.capitalize()})",
                    input_message_content=InputTextMessageContent(text, parse_mode=enums.ParseMode.HTML),
                    reply_markup=kb,
                    description=f"View and manage active tasks (Filter: {current_filter})"
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
        _tm_error("taskmgr_inline_handler", e, query=getattr(iq, "query", None))
        # Send a generic error result
        try:
            await iq.answer([
                InlineQueryResultArticle(
                    title="❌ Error",
                    input_message_content=InputTextMessageContent(f"❌ <b>Internal Handler Error:</b> <code>{html.escape(str(e))}</code>"),
                    description="Check logs for traceback"
                )
            ], cache_time=0)
        except Exception as err:
            _tm_error("taskmgr_inline_handler.reply", err)


async def handle_restore_action(client: Client, cb: CallbackQuery, plugin: str, tid: str, silent: bool = False) -> tuple:
    """Helper to route restore actions to the correct plugin handler."""
    try:
        if plugin == "xcreategroup":
            from Main.plugins.userbot.xcreategroup import (
                creategroup_control_handler,
                recover_creategroup_task,
                load_creategroup_cache,
                CREATEGROUP_TASKS,
            )
            if silent:
                if tid not in CREATEGROUP_TASKS:
                    try:
                        await load_creategroup_cache()
                    except Exception as e:
                        _tm_error("handle_restore_action.load_creategroup_cache", e, tid=tid)
                return await recover_creategroup_task(tid)
                
            # We temporarily modify cb.data to match what the handler expects
            original_data = cb.data
            cb.data = f"recover_creategroup:{tid}"
            await creategroup_control_handler(client, cb)
            cb.data = original_data # restore original data
            return True, f"♻️ Restore request sent for {tid}."
        elif plugin == "xforward_pro":
            from Main.plugins.userbot.xforward_pro import _restore_active_tasks
            # Restore all active tasks from DB (it will skip those already running)
            asyncio.create_task(_restore_active_tasks())
            return True, f"♻️ Forward Pro restoration started for {tid}."
        else:
            return False, f"❌ Plugin {plugin} does not support global restore."
    except Exception as e:
        _tm_error("handle_restore_action", e, plugin=plugin, tid=tid, silent=silent)
        return False, f"❌ Restore failed: {str(e)}"


async def _background_bulk_resume(client, cb, targets, delay, action_name, user_id, target_page):
    """Background task to handle bulk resumes without blocking the main callback handler."""
    if user_id in _ACTIVE_BULK_USERS:
        if TASKMGR_DEBUG:
            _tm_debug(f"[TaskMgr][BULK_RESUME_SKIP] User {user_id} already has a bulk action in progress.")
        return
    
    _ACTIVE_BULK_USERS.add(user_id)
    count = 0
    total_targets = len(targets)
    failures = []
    if TASKMGR_DEBUG:
        sample = ", ".join([str(t[0]) for t in (targets or [])[:10]])
        _tm_debug(f"[TaskMgr][BULK_RESUME_START] {action_name} total={total_targets} delay={delay} page={target_page} sample=[{sample}]")
    try:
        for idx, (tid, entry) in enumerate(targets):
            try:
                is_int = entry.get("is_interrupted", False)
                plugin = entry.get("plugin", "xcreategroup")
                if TASKMGR_DEBUG:
                    _tm_debug(f"[TaskMgr][BULK_RESUME_ITEM] action={action_name} idx={idx+1}/{total_targets} tid={tid} plugin={plugin} intr={is_int} paused={entry.get('paused', False)}")
                if is_int:
                    s, restore_msg = await handle_restore_action(client, cb, plugin, tid, silent=True)
                else:
                    s, restore_msg = await resume_task_by_id(tid)
                
                if s:
                    count += 1
                    if TASKMGR_DEBUG:
                        _tm_debug(f"[TaskMgr][BULK_RESUME_ITEM_OK] tid={tid}")
                    if delay > 0 and idx < total_targets - 1:
                        await asyncio.sleep(delay)
                else:
                    if TASKMGR_DEBUG:
                        reason = _truncate_text(_normalize_plain_text(_strip_html(restore_msg or "false")), 120)
                        _tm_debug(f"[TaskMgr][BULK_RESUME_ITEM_FAIL] tid={tid} reason={reason}")
                        failures.append(f"{tid}:{reason}")
            except Exception as e:
                logger.debug(f"Bulk resume failed for {tid}: {e}")
                if TASKMGR_DEBUG:
                    _tm_debug(f"[TaskMgr][BULK_RESUME_ITEM_ERR] tid={tid} err={type(e).__name__} msg={e}")
                    failures.append(f"{tid}:{type(e).__name__}")
                continue
        
        # Final notification update in the dashboard if message still exists
        try:
            msg = f"✅ {action_name} selesai: {count} task diproses."
            text, kb = gen_task_list_data(user_id, page=target_page)
            text = _inject_status_notice(text, msg)
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        except Exception:
            pass # Message might have been deleted or expired
            
    except Exception as e:
        _tm_error("_background_bulk_resume", e, action_name=action_name, user_id=user_id, target_page=target_page, delay=delay)
    finally:
        _ACTIVE_BULK_USERS.discard(user_id)
        if TASKMGR_DEBUG:
            fail_preview = ", ".join(failures[:10])
            _tm_debug(f"[TaskMgr][BULK_RESUME_DONE] {action_name} ok={count}/{total_targets} fail_count={len(failures)} fail_sample=[{fail_preview}]")

_registered_taskmgr_bots = set()

def register_taskmgr_bot_handlers(bot_client: Client):
    if not bot_client:
        return
    if bot_client is getattr(Altruix, "bot", None):
        return
    try:
        if bot_client.me and bot_client.me.id in _registered_taskmgr_bots:
            return
        bot_client.add_handler(
            InlineQueryHandler(
                taskmgr_inline_handler,
                filters.regex(r"^taskmgr_(?P<type>list|status)_(?P<uid>\d+)(?:_(?P<extra>.*))?")
            ),
            group=-1
        )
        bot_client.add_handler(
            CallbackQueryHandler(
                taskmgr_callback_handler,
                filters.regex("^taskmgr_")
            ),
            group=-1
        )
        if bot_client.me:
            _registered_taskmgr_bots.add(bot_client.me.id)
        if TASKMGR_DEBUG:
            _tm_debug(f"[TaskMgr][BOT_REGISTER] ok bot=@{bot_client.me.username if bot_client.me else 'Bot'}")
    except Exception as e:
        if TASKMGR_DEBUG:
            _tm_debug(f"[TaskMgr][BOT_REGISTER] fail err={type(e).__name__} msg={e}")

# ==================== CALLBACK HANDLER ====================
@Altruix.bot.on_callback_query(filters.regex("^taskmgr_"))
@iuser_check
@log_errors
async def taskmgr_callback_handler(client: Client, cb: CallbackQuery):
    """Handle callback queries for task management interactions."""
    try:
        data = cb.data.split("_")
        action = data[1]
        logger.debug(f"Taskmgr callback received: {cb.data}")
        
        # We need user_id to resolve style. 
        # In this dashboard, we can try to get it from context or message.
        user_id = cb.from_user.id # Default to current user
        style = get_user_button_style(user_id)
        if TASKMGR_DEBUG:
            inline_id = getattr(cb, "inline_message_id", None)
            has_msg = bool(getattr(cb, "message", None))
            msg_id = getattr(getattr(cb, "message", None), "id", None)
            chat_id = getattr(getattr(getattr(cb, "message", None), "chat", None), "id", None)
            _tm_debug(f"[TaskMgr][CB] from={user_id} action={action} has_msg={has_msg} chat_id={chat_id} msg_id={msg_id} inline_id={inline_id} data={cb.data}")
        
        if action == "noop":
            return await safe_cb_answer(cb)
            
        if action == "close":
            await safe_cb_answer(cb, "Dashboard closed")
            if cb.message:
                return await cb.message.delete()
            else:
                return await cb.edit_message_text("🗑 <b>Dashboard Closed</b>", parse_mode=enums.ParseMode.HTML)
            
        if action == "page":
            await safe_cb_answer(cb, "Refreshing list...", show_alert=False)
            page = int(data[2])
            text, kb = gen_task_list_data(user_id, page=page)
            try:
                await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            except Exception:
                pass
            return

        if action == "filter":
            try:
                new_filter = data[2]
                save_task_filter(new_filter)
                await safe_cb_answer(cb, f"Filter: {new_filter.capitalize()}", show_alert=False)
                
                # Regenerate list with page 1
                text, kb = gen_task_list_data(user_id, page=1, task_filter=new_filter)
                try:
                    await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
                except MessageNotModified:
                    pass
            except Exception as e:
                logger.error(f"Error in filter callback: {e}\n{traceback.format_exc()}")
                await safe_cb_answer(cb, f"❌ Error: {str(e)}", show_alert=True)
            return

        if action == "restore":
            await safe_cb_answer(cb, show_alert=False)
            page = int(data[2]) if len(data) > 2 else 1
            text, kb = gen_restore_menu_data(user_id, page=page)
            try:
                await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            except Exception:
                pass
            return

        if action == "finished":
            await safe_cb_answer(cb, "Loading history...", show_alert=False)
            page = int(data[2]) if len(data) > 2 else 1
            text, kb = gen_finished_tasks_data(user_id, page=page)
            try:
                await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            except Exception as e:
                if "MESSAGE_NOT_MODIFIED" not in str(e):
                    logger.error(f"Error displaying finished tasks callback: {e}\n{traceback.format_exc()}")
            return

        if action == "cachemgr":
            await safe_cb_answer(cb, "Opening Cache Manager...", show_alert=False)
            text, kb = gen_cache_manager_data(user_id)
            try:
                await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            except Exception:
                pass
            return

        if action == "cache":
            if len(data) > 2 and data[2] == "update":
                await safe_cb_answer(cb, "Syncing cache...", show_alert=False)
                # Call scan and merge to sync
                scan_and_merge_caches()
                # Refresh manager view
                text, kb = gen_cache_manager_data(user_id)
                text = _inject_status_notice(text, "✅ Cache synced successfully.")
                try:
                    await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
                except Exception:
                    pass
                return

        if action == "delaymenu":
            await safe_cb_answer(cb, "Opening Delay Settings...", show_alert=False)
            text, kb = gen_delay_menu_data(user_id)
            try:
                await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            except Exception as e:
                logger.error(f"Error in delaymenu handler: {e}\n{traceback.format_exc()}")
            return

        if action == "setdelay":
            try:
                val_str = data[2]
                current = get_delay_per_resume()
                if val_str.startswith("+") or val_str.startswith("-"):
                    new_val = current + float(val_str)
                else:
                    new_val = float(val_str)
                
                # Minimum delay is 0s
                new_val = max(0.0, new_val)
                save_delay_per_resume(new_val)
                
                await safe_cb_answer(cb, f"⏳ Delay set to {new_val}s", show_alert=False)
                
                # Regenerate menu
                text, kb = gen_delay_menu_data(user_id)
                await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            except Exception as e:
                logger.error(f"Error in setdelay callback: {e}\n{traceback.format_exc()}")
                await safe_cb_answer(cb, f"❌ Error: {str(e)}", show_alert=True)
            return

        # --- Security Confirmation Flow ---
        if action == "ask":
            # format: taskmgr_ask_{real_action}_{target}
            if len(data) < 4:
                logger.warning(f"Malformed taskmgr ask callback: {cb.data}")
                await safe_cb_answer(cb, "⚠️ Invalid action payload. Coba tekan Refresh.", show_alert=True)
                return
            real_action = data[2]
            target = "_".join(data[3:])
            if TASKMGR_DEBUG and real_action in {"resumeall", "endall", "pauseall", "resumepage", "endpage", "pausepage"}:
                _tm_debug(f"[TaskMgr][ASK] from={user_id} action={real_action} target={target} raw={cb.data}")
            await safe_cb_answer(cb, show_alert=False)
            text, kb = gen_confirmation_data(user_id, real_action, target)
            try:
                await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            except MessageNotModified:
                pass
            return

        if action == "confirm":
            # format: taskmgr_confirm_{real_action}_{target}
            try:
                if len(data) < 4:
                    logger.warning(f"Malformed taskmgr confirm callback: {cb.data}")
                    await safe_cb_answer(cb, "⚠️ Invalid action payload. Coba tekan Refresh.", show_alert=True)
                    return
                real_action = data[2]
                target = "_".join(data[3:])
                if TASKMGR_DEBUG and real_action in {"resumeall", "endall", "pauseall", "resumepage", "endpage", "pausepage"}:
                    _tm_debug(f"[TaskMgr][CONFIRM] from={user_id} action={real_action} target={target} raw={cb.data} filter={get_task_filter()}")
                await safe_cb_answer(cb, "Processing request...", show_alert=False)
                
                if real_action == "stop":
                    success, msg = cancel_task_by_id(target)
                elif real_action == "dorestore":
                    registry = get_all_tasks()
                    plugin = registry.get(target, {}).get("plugin", "xcreategroup")
                    success, msg = await handle_restore_action(client, cb, plugin, target)
                elif real_action == "pauseall":
                    # For global actions, we generally act on 'all' unless specified otherwise.
                    # But if the user clicks 'Pause All', they usually want to pause everything currently running.
                    tasks_list = get_filtered_tasks("all")
                    targets = [tid for tid, entry in tasks_list if not entry.get("paused", False) and not entry.get("is_interrupted", False)]
                    
                    if not targets:
                        success, msg = True, "ℹ️ Tidak ada task yang sedang berjalan untuk di-pause."
                    else:
                        if TASKMGR_DEBUG:
                            _tm_debug(f"[TaskMgr][PAUSEALL] targets={len(targets)}")
                        asyncio.create_task(_background_bulk_action(cb, targets, pause_task_by_id, "Pause All", user_id, 1))
                        success, msg = True, f"⏳ Memproses pause {len(targets)} task di background..."
                elif real_action == "resumeall":
                    # Resume All should act on all paused/interrupted tasks regardless of current filter
                    tasks_list = get_filtered_tasks("all")
                    delay = get_delay_per_resume()
                    targets = []
                    for tid, entry in tasks_list:
                        if entry.get("paused", False) or entry.get("is_interrupted", False):
                            targets.append((tid, entry))
                    
                    total_targets = len(targets)
                    if total_targets == 0:
                        success, msg = True, "ℹ️ Tidak ada task yang perlu di-resume."
                    else:
                        if TASKMGR_DEBUG:
                            _tm_debug(f"[TaskMgr][RESUMEALL] targets={total_targets} delay={delay}")
                        # Jalankan di background agar tidak timeout
                        asyncio.create_task(_background_bulk_resume(client, cb, targets, delay, "Resume All", user_id, 1))
                        success, msg = True, f"⏳ Memproses resume {total_targets} task di background (Delay: {delay}s)..."
                elif real_action == "endall":
                    # End All should clear everything
                    tasks_list = get_filtered_tasks("all")
                    targets = [tid for tid, _ in tasks_list]
                    
                    if not targets:
                        success, msg = True, "ℹ️ Tidak ada task untuk di-hentikan."
                    else:
                        if TASKMGR_DEBUG:
                            _tm_debug(f"[TaskMgr][ENDALL] targets={len(targets)}")
                        asyncio.create_task(_background_bulk_action(cb, targets, cancel_task_by_id, "End All", user_id, 1))
                        success, msg = True, f"⏳ Memproses end {len(targets)} task di background..."
                elif real_action == "resumepage":
                    try:
                        page_num = int(target)
                    except:
                        page_num = 1
                    # Page actions MUST respect the current filter shown in UI
                    tasks_list = get_filtered_tasks() 
                    page_size = 5
                    total_pages = (len(tasks_list) + page_size - 1) // page_size
                    page_num = max(1, min(page_num, total_pages))
                    start_idx = (page_num - 1) * page_size
                    visible_tasks = tasks_list[start_idx:start_idx + page_size]
                    
                    delay = get_delay_per_resume()
                    if TASKMGR_DEBUG:
                        vf = get_task_filter()
                        visible_summary = ", ".join([_summarize_task_entry(t, e) for t, e in visible_tasks])
                        _tm_debug(f"[TaskMgr][RESUMEPAGE_VIEW] page={page_num}/{total_pages} filter={vf} visible_count={len(visible_tasks)} visible=[{visible_summary}]")
                    
                    targets = []
                    for tid, entry in visible_tasks:
                        if entry.get("paused", False) or entry.get("is_interrupted", False):
                            targets.append((tid, entry))
                            
                    total_targets = len(targets)
                    if total_targets == 0:
                        success, msg = True, f"ℹ️ Tidak ada task di halaman {page_num} yang perlu di-resume."
                    else:
                        if TASKMGR_DEBUG:
                            target_summary = ", ".join([_summarize_task_entry(t, e) for t, e in targets])
                            _tm_debug(f"[TaskMgr][RESUMEPAGE] page={page_num} targets={total_targets} delay={delay} filter={get_task_filter()} targets=[{target_summary}]")
                        # Jalankan di background
                        asyncio.create_task(_background_bulk_resume(client, cb, targets, delay, f"Resume Page {page_num}", user_id, page_num))
                        success, msg = True, f"⏳ Memproses resume {total_targets} task (Hal {page_num}) di background..."
                elif real_action == "pausepage":
                    try:
                        page_num = int(target)
                    except:
                        page_num = 1
                    tasks_list = get_filtered_tasks()
                    page_size = 5
                    total_pages = (len(tasks_list) + page_size - 1) // page_size
                    page_num = max(1, min(page_num, total_pages))
                    start_idx = (page_num - 1) * page_size
                    visible_tasks = tasks_list[start_idx:start_idx + page_size]
                    
                    targets = [tid for tid, entry in visible_tasks if not entry.get("paused", False) and not entry.get("is_interrupted", False)]
                    
                    if not targets:
                        success, msg = True, f"ℹ️ Tidak ada task berjalan di halaman {page_num} untuk di-pause."
                    else:
                        if TASKMGR_DEBUG:
                            _tm_debug(f"[TaskMgr][PAUSEPAGE] page={page_num} targets={len(targets)} filter={get_task_filter()}")
                        asyncio.create_task(_background_bulk_action(cb, targets, pause_task_by_id, f"Pause Page {page_num}", user_id, page_num))
                        success, msg = True, f"⏳ Memproses pause {len(targets)} task (Hal {page_num}) di background..."
                elif real_action == "endpage":
                    try:
                        page_num = int(target)
                    except:
                        page_num = 1
                    tasks_list = get_filtered_tasks()
                    page_size = 5
                    total_pages = (len(tasks_list) + page_size - 1) // page_size
                    page_num = max(1, min(page_num, total_pages))
                    start_idx = (page_num - 1) * page_size
                    visible_tasks = tasks_list[start_idx:start_idx + page_size]
                    
                    targets = [tid for tid, _ in visible_tasks]
                    
                    if not targets:
                        success, msg = True, f"ℹ️ Tidak ada task di halaman {page_num}."
                    else:
                        if TASKMGR_DEBUG:
                            _tm_debug(f"[TaskMgr][ENDPAGE] page={page_num} targets={len(targets)} filter={get_task_filter()}")
                        asyncio.create_task(_background_bulk_action(cb, targets, cancel_task_by_id, f"End Page {page_num}", user_id, page_num))
                        success, msg = True, f"⏳ Memproses end {len(targets)} task (Hal {page_num}) di background..."
                elif real_action == "cache":
                    # Clear Cache Action
                    cg_cache_path = get_db_path("xcreategroup_cache.json")
                    cleared_files = []
                    if os.path.exists(cg_cache_path):
                        try:
                            # Also clear memory if possible
                            try:
                                from Main.plugins.userbot.xcreategroup import CREATEGROUP_TASKS, COMPLETED_CREATEGROUP_TASKS
                                CREATEGROUP_TASKS.clear()
                                COMPLETED_CREATEGROUP_TASKS.clear()
                                Altruix.log("[TaskManager] Memory cache for CreateGroup cleared.", level=20)
                            except Exception as mem_err:
                                logger.warning(f"Failed to clear CG memory cache: {mem_err}")

                            # Reset file content to empty structure instead of deleting
                            with open(cg_cache_path, "w") as f:
                                json.dump({"tasks": {}, "completed": {}}, f, indent=2)
                            cleared_files.append("xcreategroup_cache.json")
                        except Exception as e:
                            logger.error(f"Failed to clear CG cache: {e}")
                    
                    if cleared_files:
                        success, msg = True, f"✅ Cache cleared: {', '.join(cleared_files)}"
                    else:
                        success, msg = False, "⚠️ No cache files found to clear."
                    
                    # Redirect to cache manager
                    text, kb = gen_cache_manager_data(user_id)
                    text = _inject_status_notice(text, msg)
                    try:
                        await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
                    except MessageNotModified:
                        pass
                    return
                else:
                    success, msg = False, "Unknown action."

                # Back to the exact same page
                try:
                    target_page = int(target) if "page" in real_action else 1
                except:
                    target_page = 1

                text, kb = gen_task_list_data(user_id, page=target_page)
                text = _inject_status_notice(text, msg)
                try:
                    await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
                except MessageNotModified:
                    pass
                return
            except Exception as e:
                logger.error(f"Error in confirm action: {e}\n{traceback.format_exc()}")
                await safe_cb_answer(cb, f"❌ Error: {str(e)}", show_alert=True)
                return

        # --- Single Task Actions ---
        tid = data[2]
        if not tid.startswith("#"): tid = f"#{tid}"
        
        if action == "status":
            await safe_cb_answer(cb, "Updating status...", show_alert=False)
            text, kb = gen_task_status_data(user_id, tid)
            try:
                await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            except MessageNotModified:
                pass
            except Exception as e:
                logger.error(f"Error updating status view: {e}", exc_info=True)
            return

        if action == "info":
            await safe_cb_answer(cb, "Refreshing info...", show_alert=False)
            page = int(data[3]) if len(data) > 3 else 1
            text, kb = gen_task_info_data(user_id, tid, page=page)
            try:
                await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            except MessageNotModified:
                pass
            except Exception as e:
                logger.error(f"Error updating info view: {e}", exc_info=True)
            return

        if action == "pause":
            success, msg = pause_task_by_id(tid)
            await safe_cb_answer(cb, msg, show_alert=True)
            text, kb = gen_task_status_data(user_id, tid)
            try:
                await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            except MessageNotModified:
                pass
            except Exception as e:
                logger.error(f"Error refreshing status after pause: {e}", exc_info=True)
            return

        if action == "resume":
            success, msg = await resume_task_by_id(tid)
            await safe_cb_answer(cb, msg, show_alert=True)
            text, kb = gen_task_status_data(user_id, tid)
            try:
                await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            except MessageNotModified:
                pass
            except Exception as e:
                logger.error(f"Error refreshing status after resume: {e}", exc_info=True)
            return

        if action == "recur":
            success, msg = toggle_recurring_by_id(tid)
            await safe_cb_answer(cb, msg, show_alert=True)
            text, kb = gen_task_status_data(user_id, tid)
            try:
                await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            except MessageNotModified:
                pass
            except Exception as e:
                logger.error(f"Error refreshing status after recur toggle: {e}", exc_info=True)
            return

        if action == "view":
            # Redirect to detailed info view instead of popup to avoid MESSAGE_TOO_LONG
            text, kb = gen_task_info_data(user_id, tid)
            try:
                await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            except MessageNotModified:
                pass
            except Exception as e:
                logger.error(f"Error rendering info view: {e}", exc_info=True)
                await safe_cb_answer(cb, f"❌ Error rendering info: {str(e)[:50]}", show_alert=True)
            return
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
        await safe_cb_answer(cb, f"❌ Callback Error: {str(e)}", show_alert=True)

try:
    bm = getattr(Altruix, "bot_manager", None)
    bots = getattr(bm, "custom_bots", None) if bm else None
    if isinstance(bots, dict):
        for _bot in list(bots.values()):
            register_taskmgr_bot_handlers(_bot)
except Exception as erb:
    _tm_error("register_taskmgr_bot_handlers.bootstrap", erb)
    pass
