# xauto_pro_gcast.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
# All rights reserved.
#
# Auto Pro Global BroadCast — Send messages automatically to all chats
# with an advanced interactive dashboard, CRUD text list, blacklist manager,
# and full task lifecycle (start/stop/pause/resume/recurring).

import os
import json
import asyncio
import time
import random
import logging
import html
from datetime import datetime, timedelta
from pathlib import Path
from pyrogram import Client, filters, enums
from pyrogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    CallbackQuery, Message as PyroMessage,
    InlineQuery, InlineQueryResultArticle, InputTextMessageContent
)
from pyrogram.errors.exceptions import FloodWait, SlowmodeWait, ChatWriteForbidden
from pyrogram import errors
from Main import Altruix
from Main.core.types.message import Message
from Main.core.decorators import iuser_check, log_errors
from Main.utils.file_helpers import get_user_button_style

# Plugin Metadata
plugin_name = f"{os.path.basename(__file__)}"
__plugin_name__ = plugin_name if plugin_name else "xauto_pro_gcast"
PLUGIN_VERSION = "1.0.518"

logger = logging.getLogger("altruix.xauto_pro_gcast")
logger.setLevel(logging.INFO)

# ==================== PERSISTENT STORAGE ====================
from Main.utils.file_helpers import get_db_path
STORAGE_FILE = Path(get_db_path("auto_pro_gcast_settings.json"))

def _load_all_settings() -> dict:
    """Load all user settings from JSON file."""
    try:
        if STORAGE_FILE.exists():
            with open(STORAGE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        Altruix.log(f"Failed to load settings: {e}", level=40)
    return {}

def _save_all_settings(data: dict):
    """Save all user settings to JSON file."""
    try:
        STORAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STORAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        Altruix.log(f"Failed to save settings: {e}", level=40)

def get_settings(user_id: int) -> dict:
    """Get settings for a specific user, with defaults."""
    all_s = _load_all_settings()
    uid = str(user_id)
    defaults = {
        "chat_filter": "all",       # all / groups / personal
        "admin_filter": "all",      # all / admin / nonadmin
        "delay_per_chat": 6,        # seconds
        "text_list": [],            # list of dicts: {"content": "...", "parse_mode": "html/markdown/none"}
        "media_list": [],           # list of dicts: {"type": "photo/video/etc", "file_id": "...", "caption": "...", "parse_mode": "html/markdown/none"}
        "random_text": True,        # random vs sequential
        "blacklist": [],            # list of chat_ids (int)
        "recurring": False,         # auto-restart after cycle
        "parse_mode": "html",       # default parse mode: html / markdown / none
        # Smart Purgeme settings
        "smart_purge": False,       # enable/disable smart purge before gcast
        "purge_limit": 4,           # number of messages to delete (default 4)
        "purge_delay_msg": 1.0,     # delay between message deletions (default 1s)
        "purge_mode": "oldest",     # oldest / newest
        "purge_offset": 0,          # skip N messages (default 0)
        # Notification settings
        "notify_logs": True,        # enable/disable log notifications to group log
        # Auto React settings
        "auto_react": False,        # enable/disable auto react on sent messages
        "react_emoji": "👍",        # default emoji for reaction
        "react_delay": 4,           # delay before reacting (seconds, default 4s)
        # Self-Destruct settings
        "self_destruct": False,     # enable/disable self-destruct
        "self_destruct_delay": 30,  # delay before deleting sent message (seconds)
        # Auto-Reply settings
        "auto_reply": False,        # enable/disable auto reply
        "reply_delay": 3,           # delay before replying (seconds)
        "random_reply": True,       # random vs sequential for reply
        "reply_text_list": [        # default human-friendly templates
            {"content": "Izin nyimak kak, menarik banget infonya! 😍", "parse_mode": "html"},
            {"content": "Wah boleh juga nih, gas polll! 🚀", "parse_mode": "html"},
            {"content": "Mantap jiwa, info yang sangat berfaedah! 🙏", "parse_mode": "html"},
            {"content": "Lucu banget sih ini, gemeshhh! ✨", "parse_mode": "html"},
            {"content": "Aseekk, makasih infonya ya kak! 🤘", "parse_mode": "html"},
            {"content": "Izin up kak, moga makin rame ya! 🔥", "parse_mode": "html"}
        ],
        # Menu settings
        "menu_mode": "hide",         # full / hide
        "queues": {},               # { "QueueName": [chat_id1, chat_id2, ...] }
        "recurring_mode": "interval", # interval / time
        "recurring_interval_hours": 0,
        "recurring_interval_minutes": 10,
        "recurring_specific_hour": 0,
        "recurring_specific_minute": 0,
    }
    if uid not in all_s:
        all_s[uid] = defaults
        _save_all_settings(all_s)
    else:
        # Merge missing keys and migrate old format
        for k, v in defaults.items():
            if k not in all_s[uid]:
                all_s[uid][k] = v
        
        # Migrate old text_list format (list of strings) to new format (list of dicts)
        if all_s[uid].get("text_list") and isinstance(all_s[uid]["text_list"], list):
            if all_s[uid]["text_list"] and isinstance(all_s[uid]["text_list"][0], str):
                # Old format detected, migrate to new format
                old_texts = all_s[uid]["text_list"]
                all_s[uid]["text_list"] = [
                    {"content": text, "parse_mode": "html"} for text in old_texts
                ]
        
        _save_all_settings(all_s)
    return all_s[uid]

def save_settings(user_id: int, settings: dict):
    """Save settings for a specific user."""
    all_s = _load_all_settings()
    all_s[str(user_id)] = settings
    _save_all_settings(all_s)

# ==================== IN-MEMORY TASK STATE ====================
# { user_id: { task_id, running, pause_event, sent_count, total_chats,
#              current_chat, asyncio_task, started_at, client, errors, text_idx } }
GCAST_TASKS = {}

# Pending confirmation for start
GCAST_PENDING_CONFIRM = {}

# State for text list input (waiting for user reply)
GCAST_TEXT_INPUT_STATE = {}

# State for media input (waiting for user media)
GCAST_MEDIA_INPUT_STATE = {}

# State for Auto-Reply text input
GCAST_REPLY_TEXT_INPUT_STATE = {}
GCAST_REPLY_MEDIA_INPUT_STATE = {}

# State for blacklist add input
GCAST_BL_INPUT_STATE = {}

# ==================== LOG CHAT ====================
try:
    LOG_CHAT_ID = Altruix.config.LOG_CHAT_ID
    if isinstance(LOG_CHAT_ID, str) and LOG_CHAT_ID.lstrip("-").isdigit():
        LOG_CHAT_ID = int(LOG_CHAT_ID)
except Exception:
    LOG_CHAT_ID = "me"

# ==================== HELPER FUNCTIONS ====================

async def send_log(text: str, client=None, reply_markup=None):
    """Send a log message to the LOG_CHAT_ID via bot assistant."""
    try:
        bot = None
        if client and hasattr(Altruix, 'bot_manager'):
            bot = Altruix.bot_manager.get_bot(client.me.id)
        if not bot:
            bot = Altruix.bot
        if bot:
            return await bot.send_message(LOG_CHAT_ID, text, reply_markup=reply_markup)
    except Exception as e:
        Altruix.log(f"send_log failed: {e}", level=40)
    return None

def build_detailed_log_text(status: dict) -> str:
    """Build the detailed log text from a status dictionary.
    
    Status dict keys:
        success, counter, account_name, chat_link, chat_id,
        message_type, content_preview, current_time,
        purge_count, react_emoji, reply_status,
        sd_gcast_status, sd_reply_status, error_reason
    """
    if status.get("success", True):
        status_emoji = "✅"
        status_text = "SUCCESS"
    else:
        status_emoji = "❌"
        status_text = "FAILED"
    
    header = f"{status_emoji} <b>GCast {status_text}</b>"
    if status.get("counter"):
        header += f" [{status['counter']}]"
    
    text = (
        f"<blockquote expandable>{header}\n"
        f"{'━' * 18}\n"
        f"• <b>Account:</b> {html.escape(status.get('account_name', 'Unknown'))}\n"
        f"• <b>Chat:</b> {status.get('chat_link', 'Unknown')}\n"
        f"• <b>Chat ID:</b> <code>{status.get('chat_id', '?')}</code>\n"
        f"• <b>Type:</b> {status.get('message_type', '?')}\n"
        f"• <b>Content:</b> {html.escape(status.get('content_preview', '')[:50])}{'...' if len(status.get('content_preview', '')) > 50 else ''}\n"
    )
    
    # Progressive fields — only shown when available
    if status.get("purge_count") is not None:
        text += f"• <b>Purged:</b> {status['purge_count']} msg\n"
    
    if status.get("react_emoji"):
        text += f"• <b>Reaction:</b> Done ({status['react_emoji']})\n"
    
    if status.get("reply_status"):
        text += f"• <b>Reply:</b> {status['reply_status']}\n"
    
    if status.get("sd_gcast_status"):
        text += f"• <b>Self-Destruct Gcast:</b> {status['sd_gcast_status']}\n"
    
    if status.get("sd_reply_status"):
        text += f"• <b>Self-Destruct Reply:</b> {status['sd_reply_status']}\n"
    
    if not status.get("success", True) and status.get("error_reason"):
        text += f"• <b>Reason:</b> {html.escape(status['error_reason'])}\n"
    
    text += f"• <b>Time:</b> {status.get('current_time', '?')}\n"
    text += f"{'━' * 18}</blockquote>"
    
    return text


def build_chat_link(chat_id: int, chat_title: str, sent_message_id: int = None) -> str:
    """Build a clickable chat link for Telegram."""
    if str(chat_id).startswith("-100"):
        clean_chat_id = str(chat_id)[4:]
        if sent_message_id:
            return f"<a href='https://t.me/c/{clean_chat_id}/{sent_message_id}'>{html.escape(chat_title)}</a>"
        else:
            return f"<a href='https://t.me/c/{clean_chat_id}'>{html.escape(chat_title)}</a>"
    return html.escape(chat_title)


async def edit_log_msg(log_msg, text: str, client=None):
    """Edit an existing log message in the LOG chat. Retries once on FloodWait."""
    try:
        if log_msg:
            bot = None
            if client and hasattr(Altruix, 'bot_manager'):
                bot = Altruix.bot_manager.get_bot(client.me.id)
            if not bot:
                bot = Altruix.bot
            if bot:
                try:
                    await bot.edit_message_text(
                        LOG_CHAT_ID, log_msg.id, text,
                        parse_mode=enums.ParseMode.HTML
                    )
                except FloodWait as fw:
                    await asyncio.sleep(fw.value + 2)
                    await bot.edit_message_text(
                        LOG_CHAT_ID, log_msg.id, text,
                        parse_mode=enums.ParseMode.HTML
                    )
    except Exception as e:
        Altruix.log(f"edit_log_msg failed: {e}", level=10, client=client)


async def pin_log_msg(log_msg, client=None):
    """Pin a log message in the LOG chat."""
    try:
        if log_msg:
            bot = None
            if client and hasattr(Altruix, 'bot_manager'):
                bot = Altruix.bot_manager.get_bot(client.me.id)
            if not bot:
                bot = Altruix.bot
            if bot:
                await bot.pin_chat_message(LOG_CHAT_ID, log_msg.id, disable_notification=True)
    except Exception as e:
        Altruix.log(f"pin_log_msg failed: {e}", level=10, client=client)


async def unpin_log_msg(log_msg, client=None):
    """Unpin a log message in the LOG chat."""
    try:
        if log_msg:
            bot = None
            if client and hasattr(Altruix, 'bot_manager'):
                bot = Altruix.bot_manager.get_bot(client.me.id)
            if not bot:
                bot = Altruix.bot
            if bot:
                await bot.unpin_chat_message(LOG_CHAT_ID, log_msg.id)
    except Exception as e:
        Altruix.log(f"unpin_log_msg failed: {e}", level=10, client=client)


# ========== Persistent Task State for Resume ==========
ACTIVE_TASKS_FILE = Path(get_db_path("gcast_active_tasks.json"))


def save_active_task(user_id: int, task_data: dict):
    """Save active broadcast task state for resume after restart."""
    try:
        all_tasks = {}
        if ACTIVE_TASKS_FILE.exists():
            all_tasks = json.loads(ACTIVE_TASKS_FILE.read_text(encoding="utf-8"))
        all_tasks[str(user_id)] = task_data
        ACTIVE_TASKS_FILE.write_text(json.dumps(all_tasks, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        Altruix.log(f"save_active_task failed: {e}", level=40)


def remove_active_task(user_id: int):
    """Remove completed/stopped task from persistent state."""
    try:
        if ACTIVE_TASKS_FILE.exists():
            all_tasks = json.loads(ACTIVE_TASKS_FILE.read_text(encoding="utf-8"))
            all_tasks.pop(str(user_id), None)
            ACTIVE_TASKS_FILE.write_text(json.dumps(all_tasks, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        Altruix.log(f"remove_active_task failed: {e}", level=40)


def get_active_tasks() -> dict:
    """Load all active broadcast tasks from persistent state."""
    try:
        if ACTIVE_TASKS_FILE.exists():
            return json.loads(ACTIVE_TASKS_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        Altruix.log(f"get_active_tasks failed: {e}", level=40)
    return {}


async def send_detailed_log(
    user_id: int,
    chat_id: int,
    chat_title: str,
    message_type: str,
    content_preview: str,
    success: bool,
    error_reason: str = None,
    purge_count: int = 0,
    react_success: bool = False,
    client=None,
    sent_message_id: int = None,
    counter: str = None,
    react_emoji: str = None,
    reply_status: str = None,
    sd_gcast_status: str = None,
    sd_reply_status: str = None,
):
    """Send detailed log notification (legacy compatibility wrapper)."""
    try:
        from datetime import datetime
        # Get account info
        account_name = "Unknown"
        if client and client.me:
            first = client.me.first_name or ""
            last = client.me.last_name or ""
            account_name = f"{first} {last}".strip() or str(user_id)
        
        chat_link = build_chat_link(chat_id, chat_title, sent_message_id)
        
        status = {
            "success": success,
            "counter": counter,
            "account_name": account_name,
            "chat_link": chat_link,
            "chat_id": chat_id,
            "message_type": message_type,
            "content_preview": content_preview,
            "current_time": datetime.now().strftime("%H:%M:%S"),
            "purge_count": purge_count,
            "react_emoji": react_emoji if react_success else None,
            "reply_status": reply_status,
            "sd_gcast_status": sd_gcast_status,
            "sd_reply_status": sd_reply_status,
            "error_reason": error_reason,
        }
        text = build_detailed_log_text(status)
        await send_log(text, client=client)
    except Exception as e:
        Altruix.log(f"send_detailed_log failed: {e}", level=40, client=client)

async def safe_cb_answer(cb: CallbackQuery, text: str, show_alert: bool = True):
    """Answer callback query safely, ignoring expired queries."""
    try:
        await cb.answer(text, show_alert=show_alert)
    except Exception:
        pass

async def safe_edit_message(cb: CallbackQuery, text: str, reply_markup=None, parse_mode=None, **kwargs):
    """
    Safely edit callback message, handling both regular and inline mode messages.
    Uses cb.edit_message_text() which automatically handles inline messages.
    """
    try:
        # Use cb.edit_message_text() - it automatically handles both regular and inline messages
        # logger.info(f"[safe_edit_message] Editing message for callback: {cb.data}")
        
        await cb.edit_message_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            **kwargs
        )
        # logger.info(f"[safe_edit_message] Successfully edited message")
        return True
                
    except errors.MessageNotModified:
        # Ignore this error as it's not a failure, just means state didn't change
        # logger.info(f"[safe_edit_message] Message was not modified, ignoring.")
        return True
    except Exception as e:
        Altruix.log(f"[safe_edit_message] Error editing message: {e}", level=40)
        Altruix.log(f"[safe_edit_message] Callback data: {cb.data}", level=40)
        await safe_cb_answer(cb, f"❌ Error: {str(e)[:100]}", show_alert=True)
        return False


def _get_q_hash(name: str) -> str:
    """Get short hash of a queue name to stay under 64b callback limit."""
    import hashlib
    return hashlib.sha256(name.encode()).hexdigest()[:8]

def _resolve_q_name(user_id: int, maybe_hash: str) -> str:
    """Resolve a hash (h:hash) or name back to the full queue name."""
    s = get_settings(user_id)
    queues = s.get("queues", {})
    
    if maybe_hash.startswith("h:"):
        target_hash = maybe_hash[2:]
        for q_name in queues.keys():
            if _get_q_hash(q_name) == target_hash:
                return q_name
    return maybe_hash

def _filter_label(val: str) -> str:
    """Convert filter value to display label."""
    if val.startswith("q:"):
        return f"Q: {val[2:]}"
    return {"all": "All", "groups": "Groups", "personal": "Personal",
            "admin": "Admin", "nonadmin": "Non-Admin"}.get(val, val.title())

def _task_status_str(user_id: int) -> str:
    """Get short status string for a user's task."""
    task = GCAST_TASKS.get(user_id)
    if not task:
        return "⬚ IDLE"
    if not task["running"]:
        return "🔴 STOPPED"
    if not task["pause_event"].is_set():
        return "🟡 PAUSED"
    return "🟢 RUNNING"

def _task_progress_str(user_id: int) -> str:
    """Get progress string for a user's task."""
    task = GCAST_TASKS.get(user_id)
    if not task:
        return "N/A"
    sent = task.get("sent_count", 0)
    total = task.get("total_chats", 0)
    if total > 0:
        pct = (sent / total) * 100
        return f"{sent}/{total} ({pct:.1f}%)"
    return f"{sent}/?"

# ==================== DASHBOARD TEXT & KEYBOARD ====================

def build_dashboard_text(user_id: int) -> str:
    """Build the main dashboard status text."""
    s = get_settings(user_id)
    task = GCAST_TASKS.get(user_id)
    
    status = _task_status_str(user_id)
    task_id = task["task_id"] if task else "#N/A"
    progress = _task_progress_str(user_id)
    current = task.get("current_chat", "-") if task else "-"
    errs = task.get("errors", 0) if task else 0
    
    # Count total messages (text + media)
    total_messages = len(s.get('text_list', [])) + len(s.get('media_list', []))
    
    # Smart Purge status
    smart_purge_status = "ON" if s.get('smart_purge', False) else "OFF"
    
    # Get account info with clickable mention
    account_mention = f"<a href='tg://user?id={user_id}'>User</a>"
    account_name = str(user_id)
    
    # Try to get full name from connected clients
    for cl in Altruix.clients:
        if hasattr(cl, 'me') and cl.me and cl.me.id == user_id:
            first = cl.me.first_name or ""
            last = cl.me.last_name or ""
            full_name = f"{first} {last}".strip()
            if full_name:
                account_name = html.escape(full_name)
                account_mention = f"<a href='tg://user?id={user_id}'>{account_name}</a>"
            break
    
    # Recurring detailed info
    rec_val = "OFF"
    if s.get('recurring', False):
        mode = s.get('recurring_mode', 'interval')
        if mode == 'interval':
            h = s.get('recurring_interval_hours', 0)
            m = s.get('recurring_interval_minutes', 10)
            rec_val = f"ON (Every {h}h {m}m)"
        else:
            sh = s.get('recurring_specific_hour', 0)
            sm = s.get('recurring_specific_minute', 0)
            rec_val = f"ON (At {sh:02d}:{sm:02d} Daily)"

    text = (
        f"<blockquote expandable>📡 <b>Auto Pro Global BroadCast</b>\n"
        f"{'━' * 18}\n"
        f"• Account: <b>{account_mention}</b>\n"
        f"• Status: {status} | • Task: <code>{task_id}</code>\n"
        f"• Chat Filter: <b>{_filter_label(s['chat_filter'])}</b> | "
        f"• Admin: <b>{_filter_label(s['admin_filter'])}</b>\n"
        f"• Delay/Chat: <b>{s['delay_per_chat']}s</b> | "
        f"• Messages: <b>{total_messages} items</b>\n"
        f"• Texts: <b>{len(s.get('text_list', []))}</b> | "
        f"• Media: <b>{len(s.get('media_list', []))}</b>\n"
        f"• Random Gcast: <b>{'ON' if s['random_text'] else 'OFF'}</b> | "
        f"• Recurring: <b>{rec_val}</b>\n"
        f"• Auto-Reply: <b>{'ON' if s.get('auto_reply', False) else 'OFF'}</b> (<b>{s.get('reply_delay', 3)}s</b>)\n"
        f"• Random Reply: <b>{'ON' if s.get('random_reply', True) else 'OFF'}</b> | "
        f"• Reply Msgs: <b>{len(s.get('reply_text_list', []))}</b>\n"
        f"• Blacklist: <b>{len(s['blacklist'])} chats</b>\n"
        f"• Smart Purge: <b>{smart_purge_status}</b>\n"
        f"• Self-Destruct: <b>{'ON' if s.get('self_destruct', False) else 'OFF'}</b> (<b>{s.get('self_destruct_delay', 30)}s</b>)\n"
    )
    if task and task["running"]:
        text += (
            f"{'━' * 18}\n"
            f"📊 Progress: {progress}\n"
            f"📍 Current: {html.escape(str(current)[:30])}\n"
            f"❌ Errors: {errs}\n"
        )
    text += f"{'━' * 18}</blockquote>"
    return text

def build_task_control_kb(user_id: int, task_id: str) -> InlineKeyboardMarkup:
    """Build dynamic task control keyboard for log messages."""
    btn_style = get_user_button_style(user_id)
    state = GCAST_TASKS.get(user_id)
    
    is_paused = state and not state["pause_event"].is_set()
    
    pause_resume_btn = (
        InlineKeyboardButton("▶️ Resume", callback_data=f"pgc_resume_{user_id}_{task_id}", style=btn_style)
        if is_paused else
        InlineKeyboardButton("⏸ Pause", callback_data=f"pgc_pause_{user_id}_{task_id}", style=btn_style)
    )
    
    return InlineKeyboardMarkup([
        [pause_resume_btn, InlineKeyboardButton("⏹ Stop", callback_data=f"pgc_stop_{user_id}_{task_id}", style=btn_style)],
        [InlineKeyboardButton("ℹ️ Status", callback_data=f"pgc_status_{user_id}_{task_id}", style=btn_style)]
    ])

def build_dashboard_kb(user_id: int) -> InlineKeyboardMarkup:
    """Build the main dashboard inline keyboard with exact requested layout."""
    s = get_settings(user_id)
    task = GCAST_TASKS.get(user_id)
    is_running = task and task.get("running", False)
    is_paused = is_running and not task["pause_event"].is_set()
    menu_mode = s.get("menu_mode", "full")

    uid = user_id
    rows = []

    # Get user button style
    btn_style = get_user_button_style(user_id)

    if menu_mode == "full":
        # 1. Chat Filter / Admin Filter
        rows.append([
            InlineKeyboardButton(f"📋 Chat: {_filter_label(s['chat_filter'])}", callback_data=f"pgc_chatfilter_{uid}", style=btn_style),
            InlineKeyboardButton(f"👤 Admin: {_filter_label(s['admin_filter'])}", callback_data=f"pgc_adminfilter_{uid}", style=btn_style),
        ])

        # 2. Messages GCast / Random Toggle
        total_messages = len(s.get('text_list', [])) + len(s.get('media_list', []))
        rows.append([
            InlineKeyboardButton(f"📝 Messages GCast ({total_messages})", callback_data=f"pgc_msgmenu_{uid}", style=btn_style),
            InlineKeyboardButton(f"🔀 RandomGcst: {'ON' if s['random_text'] else 'OFF'}", callback_data=f"pgc_randomtoggle_{uid}", style=btn_style),
        ])

        # 3. Messages Reply / Random Toggle
        total_reply_msgs = len(s.get('reply_text_list', []))
        rows.append([
            InlineKeyboardButton(f"📩 Messages Reply ({total_reply_msgs})", callback_data=f"pgc_repmsgmenu_{uid}", style=btn_style),
            InlineKeyboardButton(f"🔄 RandomRep: {'ON' if s.get('random_reply', True) else 'OFF'}", callback_data=f"pgc_reprandomtoggle_{uid}", style=btn_style),
        ])

        # 4. Blacklist / List Chats
        rows.append([
            InlineKeyboardButton(f"🚫 Blacklist ({len(s['blacklist'])})", callback_data=f"pgc_blmenu_{uid}", style=btn_style),
            InlineKeyboardButton(f"📋 List Chats", callback_data=f"pgc_listchats_{uid}", style=btn_style),
        ])

        # 4.5 Queue Manager
        rows.append([
            InlineKeyboardButton(f"📁 Queue Manager ({len(s.get('queues', {}))})", callback_data=f"pgc_queuemgr_{uid}", style=btn_style),
        ])

        # 5. Recurring / Notif
        notif_status = "ON" if s.get('notify_logs', True) else "OFF"
        rows.append([
            InlineKeyboardButton(f"🔁 Recurring Settings", callback_data=f"pgc_rec_menu_{uid}", style=btn_style),
            InlineKeyboardButton(f"🔔 Notif: {notif_status}", callback_data=f"pgc_notiftoggle_{uid}", style=btn_style),
        ])

        # 6. Smart Purge / React
        smart_purge_status = "ON" if s.get('smart_purge', False) else "OFF"
        react_status = "ON" if s.get('auto_react', False) else "OFF"
        rows.append([
            InlineKeyboardButton(f"🧹 Smart Purge: {smart_purge_status}", callback_data=f"pgc_smartpurge_{uid}", style=btn_style),
            InlineKeyboardButton(f"⚡ React: {react_status}", callback_data=f"pgc_reactmenu_{uid}", style=btn_style),
        ])

        # 7. Self-Destruct / Delay Chat
        sd_status = "ON" if s.get('self_destruct', False) else "OFF"
        rows.append([
            InlineKeyboardButton(f"🧨 Self-Destruc: {sd_status}", callback_data=f"pgc_sdmenu_{uid}", style=btn_style),
            InlineKeyboardButton(f"⏱ Delay/Chat: {s['delay_per_chat']}s", callback_data=f"pgc_delaymenu_{uid}", style=btn_style),
        ])

        # 8. Auto-Reply / Delay Reply
        ar_status = "ON" if s.get('auto_reply', False) else "OFF"
        rows.append([
            InlineKeyboardButton(f"🤖 Auto-Reply: {ar_status}", callback_data=f"pgc_autoreply_{uid}", style=btn_style),
            InlineKeyboardButton(f"⏱ Delay/Rep: {s.get('reply_delay', 3)}s", callback_data=f"pgc_repdelaymenu_{uid}", style=btn_style),
        ])

        # 9. Info / Refresh
        rows.append([
            InlineKeyboardButton("📊 Info", callback_data=f"pgc_info_{uid}", style=btn_style),
            InlineKeyboardButton("🔄 Refresh", callback_data=f"pgc_refresh_{uid}", style=btn_style),
        ])

        # 10. Start/Stop / Close
        if not is_running:
            rows.append([
                InlineKeyboardButton("🟢 Start GCast", callback_data=f"pgc_startconf_{uid}", style=btn_style),
                InlineKeyboardButton("❌ Close Menu", callback_data=f"pgc_close_{uid}", style=btn_style),
            ])
        else:
            stop_btn = InlineKeyboardButton("🔴 Stop GCast", callback_data=f"pgc_stop_{uid}", style=btn_style)
            pause_resume_btn = (
                InlineKeyboardButton("▶️ Resume", callback_data=f"pgc_resume_{uid}", style=btn_style) if is_paused 
                else InlineKeyboardButton("⏸ Pause", callback_data=f"pgc_pause_{uid}", style=btn_style)
            )
            rows.append([pause_resume_btn, stop_btn])
            rows.append([InlineKeyboardButton("❌ Close Menu", callback_data=f"pgc_close_{uid}", style=btn_style)])

        # 11. Hide Menu
        rows.append([
            InlineKeyboardButton("🙈 Hide Menu", callback_data=f"pgc_hidemenu_{uid}", style=btn_style),
        ])
    else:
        # Hide Menu Mode
        if not is_running:
            rows.append([
                InlineKeyboardButton("🟢 Start GCast", callback_data=f"pgc_startconf_{uid}", style=btn_style),
                InlineKeyboardButton("❌ Close Menu", callback_data=f"pgc_close_{uid}", style=btn_style),
            ])
        else:
            stop_btn = InlineKeyboardButton("🔴 Stop GCast", callback_data=f"pgc_stop_{uid}", style=btn_style)
            pause_resume_btn = (
                InlineKeyboardButton("▶️ Resume", callback_data=f"pgc_resume_{uid}", style=btn_style) if is_paused 
                else InlineKeyboardButton("⏸ Pause", callback_data=f"pgc_pause_{uid}", style=btn_style)
            )
            rows.append([pause_resume_btn, stop_btn])
            rows.append([InlineKeyboardButton("❌ Close Menu", callback_data=f"pgc_close_{uid}", style=btn_style)])
        
        rows.append([
            InlineKeyboardButton("👀 Show Menu", callback_data=f"pgc_showmenu_{uid}", style=btn_style),
        ])

    return InlineKeyboardMarkup(rows)

def build_queuemgr_kb(user_id: int) -> InlineKeyboardMarkup:
    """Build the Queue Manager list keyboard."""
    s = get_settings(user_id)
    queues = s.get("queues", {})
    btn_style = get_user_button_style(user_id)
    uid = user_id
    rows = []

    rows.append([InlineKeyboardButton("➕ Create New Queue", callback_data=f"pgc_qadd_{uid}", style=btn_style)])

    for q_name in sorted(queues.keys()):
        count = len(queues[q_name])
        q_hash = _get_q_hash(q_name)
        rows.append([
            InlineKeyboardButton(f"📁 {q_name} ({count})", callback_data=f"pgc_qedit_{uid}_h:{q_hash}", style=btn_style),
            InlineKeyboardButton("🗑", callback_data=f"pgc_qdelconf_{uid}_h:{q_hash}", style=btn_style)
        ])

    rows.append([InlineKeyboardButton("⬅️ Back", callback_data=f"pgc_backmain_{uid}", style=btn_style)])
    return InlineKeyboardMarkup(rows)

def build_queue_edit_kb(user_id: int, queue_name: str) -> InlineKeyboardMarkup:
    """Build the keyboard for editing a specific queue."""
    s = get_settings(user_id)
    queue = s.get("queues", {}).get(queue_name, [])
    btn_style = get_user_button_style(user_id)
    uid = user_id
    rows = []

    q_hash = _get_q_hash(queue_name)
    rows.append([
        InlineKeyboardButton(f"📁 Queue: {queue_name}", callback_data=f"pgc_noop_{uid}", style=btn_style)
    ])
    
    rows.append([
        InlineKeyboardButton("✏️ Edit Name", callback_data=f"pgc_qeditname_{uid}_h:{q_hash}", style=btn_style),
        InlineKeyboardButton("➕ Add Chat (Current)", callback_data=f"pgc_qaddchat_{uid}_h:{q_hash}", style=btn_style),
    ])
    rows.append([
        InlineKeyboardButton("➕ Add Chat (by ID)", callback_data=f"pgc_qaddid_{uid}_h:{q_hash}", style=btn_style),
    ])

    # Show items in queue
    for cid in queue[:15]: # Show max 15
        rows.append([
            InlineKeyboardButton(f"Chat ID: {cid}", callback_data=f"pgc_noop_{uid}", style=btn_style),
            InlineKeyboardButton("🗑", callback_data=f"pgc_qremchat_{uid}_h:{q_hash}_{cid}", style=btn_style)
        ])
    
    if len(queue) > 15:
        rows.append([InlineKeyboardButton(f"... and {len(queue)-15} more", callback_data=f"pgc_noop_{uid}", style=btn_style)])

    rows.append([InlineKeyboardButton("⬅️ Back to Queues", callback_data=f"pgc_queuemgr_{uid}", style=btn_style)])
    return InlineKeyboardMarkup(rows)


def build_sd_submenu_kb(user_id: int) -> InlineKeyboardMarkup:
    """Build the Self-Destruct settings submenu keyboard."""
    uid = user_id
    s = get_settings(user_id)
    is_enabled = s.get('self_destruct', False)
    delay = s.get('self_destruct_delay', 30)
    target = s.get('sd_target', 'gcast')
    trigger = s.get('sd_trigger', 'after_gcast')
    btn_style = get_user_button_style(user_id)

    rows = []
    # Row 1: Toggle
    toggle_text = "🔴 Disable Self-Destruct" if is_enabled else "🟢 Enable Self-Destruct"
    rows.append([InlineKeyboardButton(toggle_text, callback_data=f"pgc_sdtoggle_{uid}", style=btn_style)])

    if is_enabled:
        # Row 2: Delay adjustment
        rows.append([
            InlineKeyboardButton("-10s", callback_data=f"pgc_sddelay_dec_{uid}", style=btn_style),
            InlineKeyboardButton(f"⏰ Delay: {delay}s", callback_data=f"pgc_noop_{uid}", style=btn_style),
            InlineKeyboardButton("+10s", callback_data=f"pgc_sddelay_inc_{uid}", style=btn_style),
        ])
        
        # Row 3: Target Selection (GCast / Reply / Both)
        target_labels = {"gcast": "🎯 Target: GCast Only", "reply": "🎯 Target: Reply Only", "both": "🎯 Target: Both"}
        rows.append([InlineKeyboardButton(target_labels.get(target, "🎯 Target: GCast Only"), callback_data=f"pgc_sdtarget_{uid}", style=btn_style)])
        
        # Row 4: Trigger Selection (After GCast / After Reply)
        trigger_labels = {"after_gcast": "⏱ Trigger: After GCast Sent", "after_reply": "⏱ Trigger: After Reply Sent"}
        rows.append([InlineKeyboardButton(trigger_labels.get(trigger, "⏱ Trigger: After GCast Sent"), callback_data=f"pgc_sdtrigger_{uid}", style=btn_style)])

    # Row 5: Back
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data=f"pgc_backmain_{uid}", style=btn_style)])
    return InlineKeyboardMarkup(rows)

def build_delay_submenu_kb(user_id: int) -> InlineKeyboardMarkup:
    """Build the Delay/Chat settings submenu keyboard."""
    uid = user_id
    s = get_settings(user_id)
    delay = s.get('delay_per_chat', 6)
    btn_style = get_user_button_style(user_id)

    rows = []
    # Row 1: Adjustment
    rows.append([
        InlineKeyboardButton("-2s", callback_data=f"pgc_delay_dec_{uid}", style=btn_style),
        InlineKeyboardButton(f"⏱ Delay: {delay}s", callback_data=f"pgc_noop_{uid}", style=btn_style),
        InlineKeyboardButton("+2s", callback_data=f"pgc_delay_inc_{uid}", style=btn_style),
    ])

    # Row 2: Presets (Optional for premium feel)
    rows.append([
        InlineKeyboardButton("5s", callback_data=f"pgc_delayset_5_{uid}", style=btn_style),
        InlineKeyboardButton("10s", callback_data=f"pgc_delayset_10_{uid}", style=btn_style),
        InlineKeyboardButton("30s", callback_data=f"pgc_delayset_30_{uid}", style=btn_style),
    ])

    # Row 3: Back
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data=f"pgc_backmain_{uid}", style=btn_style)])
    return InlineKeyboardMarkup(rows)


def build_recurring_settings_kb(user_id: int) -> InlineKeyboardMarkup:
    """Build the main Recurring settings submenu keyboard."""
    uid = user_id
    s = get_settings(user_id)
    is_enabled = s.get('recurring', False)
    mode = s.get('recurring_mode', 'interval')
    btn_style = get_user_button_style(user_id)

    rows = []
    # Toggle Master Recurring
    toggle_text = "🔴 Disable Recurring" if is_enabled else "🟢 Enable Recurring"
    rows.append([InlineKeyboardButton(toggle_text, callback_data=f"pgc_rec_toggle_{uid}", style=btn_style)])

    if is_enabled:
        # Mode Selection
        rows.append([
            InlineKeyboardButton(f"{'✅ ' if mode=='interval' else ''}Repetition", callback_data=f"pgc_rec_rep_{uid}", style=btn_style),
            InlineKeyboardButton(f"{'✅ ' if mode=='time' else ''}Specific Time", callback_data=f"pgc_rec_time_{uid}", style=btn_style),
        ])
        
        if mode == "interval":
            h = s.get('recurring_interval_hours', 0)
            m = s.get('recurring_interval_minutes', 10)
            rows.append([InlineKeyboardButton(f"⏱ Every: {h}h {m}m", callback_data=f"pgc_rec_rep_{uid}", style=btn_style)])
        else:
            sh = s.get('recurring_specific_hour', 0)
            sm = s.get('recurring_specific_minute', 0)
            rows.append([InlineKeyboardButton(f"{'✅ ' if mode=='time' else ''}At: {sh:02d}:{sm:02d} Daily", callback_data=f"pgc_rec_time_{uid}", style=btn_style)])

    rows.append([InlineKeyboardButton("⬅️ Back", callback_data=f"pgc_backmain_{uid}", style=btn_style)])
    return InlineKeyboardMarkup(rows)

def build_repetition_menu_kb(user_id: int) -> InlineKeyboardMarkup:
    """Build the interval-based repetition sub-menu with grid layout."""
    btn_style = get_user_button_style(user_id)
    uid = user_id
    rows = []
    
    # Hours Grid
    rows.append([InlineKeyboardButton("─── Set Hours ───", callback_data="pgc_noop", style=btn_style)])
    h_vals = [1, 2, 3, 4, 6, 8, 12, 24]
    for i in range(0, len(h_vals), 4):
        rows.append([InlineKeyboardButton(f"{v}h", callback_data=f"pgc_rec_set_rep_h_{v}_{uid}", style=btn_style) for v in h_vals[i:i+4]])
    
    # Minutes Grid
    rows.append([InlineKeyboardButton("─── Set Minutes ───", callback_data="pgc_noop", style=btn_style)])
    m_vals = [1, 2, 3, 5, 10, 15, 20, 30]
    for i in range(0, len(m_vals), 4):
        rows.append([InlineKeyboardButton(f"{v}m", callback_data=f"pgc_rec_set_rep_m_{v}_{uid}", style=btn_style) for v in m_vals[i:i+4]])
        
    rows.append([InlineKeyboardButton("⬅️ Back to Recurring", callback_data=f"pgc_rec_menu_{uid}", style=btn_style)])
    return InlineKeyboardMarkup(rows)

def build_time_menu_kb(user_id: int) -> InlineKeyboardMarkup:
    """Build the daily specific time sub-menu with 6-column grid layout."""
    btn_style = get_user_button_style(user_id)
    uid = user_id
    rows = []
    
    rows.append([InlineKeyboardButton("─── Select Hour (24h) ───", callback_data="pgc_noop", style=btn_style)])
    # 24 hours in 6 columns = 4 rows
    for r in range(0, 24, 6):
        row = []
        for c in range(6):
            h = r + c
            row.append(InlineKeyboardButton(f"{h:02d}", callback_data=f"pgc_rec_set_spec_h_{h}_{uid}", style=btn_style))
        rows.append(row)
    
    # Minutes Selection
    rows.append([InlineKeyboardButton("─── Select Minute ───", callback_data="pgc_noop", style=btn_style)])
    # 60 minutes in 6 columns = 10 rows
    for r in range(0, 60, 6):
        row = []
        for c in range(6):
            m = r + c
            row.append(InlineKeyboardButton(f"{m:02d}m", callback_data=f"pgc_rec_set_spec_m_{m}_{uid}", style=btn_style))
        rows.append(row)
        
    rows.append([InlineKeyboardButton("⬅️ Back to Recurring", callback_data=f"pgc_rec_menu_{uid}", style=btn_style)])
    return InlineKeyboardMarkup(rows)

def build_reply_msglist_text(user_id: int, page: int = 0) -> str:
    """Build the auto-reply message list sub-menu text (paginated)."""
    s = get_settings(user_id)
    text_list = s.get("reply_text_list", [])
    media_list = s.get("reply_media_list", [])
    random_enabled = s.get("random_reply", True)
    fixed_msg_idx = s.get("reply_fixed_message_index", None)
    
    # Combined list
    combined = []
    for i, item in enumerate(text_list):
        combined.append(("text", i, item))
    for i, item in enumerate(media_list):
        combined.append(("media", i, item))
        
    total = len(combined)
    items_per_page = 6
    total_pages = max(1, (total + items_per_page - 1) // items_per_page)
    
    if page < 0: page = 0
    if page >= total_pages: page = total_pages - 1
    
    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, total)
    page_items = combined[start_idx:end_idx]
    
    lines = []
    if random_enabled:
        lines.append("🎲 <b>Mode:</b> Random - Balasan dikirim acak")
    else:
        if fixed_msg_idx is not None:
            lines.append(f"📌 <b>Mode:</b> Fixed - Selalu balas dengan pesan #{fixed_msg_idx + 1}")
        else:
            lines.append("📋 <b>Mode:</b> Sequential - Balasan dikirim berurutan")
            
    lines.append(f"<i>Page {page+1}/{total_pages}</i>\n")
    
    if not combined:
        lines.append("📭 <i>Belum ada balasan yang ditambahkan.</i>")
    else:
        for i, (mtype, o_idx, item) in enumerate(page_items, start=start_idx + 1):
            fixed_marker = " 📌" if fixed_msg_idx == (i - 1) else ""
            if mtype == "text":
                content = item.get("content", "")
                preview = html.escape(content[:40]) + ("..." if len(content) > 40 else "")
                lines.append(f"{i}. 📝 {preview}{fixed_marker}")
            else:
                media_type = item.get("type", "unknown")
                type_icon = {"photo": "🖼", "video": "🎬"}.get(media_type, "📎")
                lines.append(f"{i}. {type_icon} {media_type.title()}{fixed_marker}")
                
    return (
        f"<blockquote expandable>💬 <b>Reply Message List</b> ({total} items)\n"
        f"{'━' * 18}\n" + "\n".join(lines) + "</blockquote>"
    )

def build_reply_msglist_kb(user_id: int, page: int = 0) -> InlineKeyboardMarkup:
    """Build the auto-reply message list sub-menu keyboard (paginated)."""
    uid = user_id
    s = get_settings(user_id)
    text_list = s.get("reply_text_list", [])
    media_list = s.get("reply_media_list", [])
    btn_style = get_user_button_style(user_id)
    
    combined = []
    for i, item in enumerate(text_list):
        combined.append(("text", i, item))
    for i, item in enumerate(media_list):
        combined.append(("media", i, item))
        
    total = len(combined)
    items_per_page = 6
    total_pages = max(1, (total + items_per_page - 1) // items_per_page)
    
    if page < 0: page = 0
    if page >= total_pages: page = total_pages - 1
    
    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, total)
    page_items = combined[start_idx:end_idx]
    
    rows = []
    rows.append([
        InlineKeyboardButton("➕ Add Text", callback_data=f"pgc_repmsgaddtext_{uid}_p{page}", style=btn_style),
        InlineKeyboardButton("➕ Add Media", callback_data=f"pgc_repmsgaddmedia_{uid}_p{page}", style=btn_style),
    ])
    
    for i, (mtype, o_idx, item) in enumerate(page_items, start=start_idx + 1):
        if mtype == "text":
            content = item.get("content", "")
            preview = content[:20].strip() + (".." if len(content) > 20 else "")
            label = f"📝 #{i}: {preview}"
            pref = "pgc_repmsgsetfixed_text"
            ppref = "pgc_repmsgpreview_text"
            dpref = "pgc_repmsgdelconf_text"
        else:
            mtype_val = item.get("type", "unknown")
            label = f"🎬 #{i}: {mtype_val.title()}"
            pref = "pgc_repmsgsetfixed_media"
            ppref = "pgc_repmsgpreview_media"
            dpref = "pgc_repmsgdelconf_media"
            
        rows.append([
            InlineKeyboardButton(label, callback_data=f"{pref}_{uid}_{o_idx}_p{page}", style=btn_style),
            InlineKeyboardButton("👁", callback_data=f"{ppref}_{uid}_{o_idx}_p{page}", style=btn_style),
            InlineKeyboardButton("🗑", callback_data=f"{dpref}_{uid}_{o_idx}_p{page}", style=btn_style),
        ])
    
    # Nav Row
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ Prev", callback_data=f"pgc_repmsgmenu_{uid}_page_{page-1}", style=btn_style))
    nav.append(InlineKeyboardButton("🔄 Refresh", callback_data=f"pgc_repmsgmenu_{uid}_page_{page}", style=btn_style))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Next ▶️", callback_data=f"pgc_repmsgmenu_{uid}_page_{page+1}", style=btn_style))
    rows.append(nav)
    
    rows.append([
        InlineKeyboardButton("🗑 Clear All", callback_data=f"pgc_repmsgclearconf_{uid}", style=btn_style),
        InlineKeyboardButton("📌 Set Fixed", callback_data=f"pgc_repsetfixed_{uid}", style=btn_style),
    ])
    
    rows.append([
        InlineKeyboardButton("⬅️ Back", callback_data=f"pgc_backmain_{uid}", style=btn_style),
    ])
    
    return InlineKeyboardMarkup(rows)

def build_reply_delay_submenu_kb(user_id: int) -> InlineKeyboardMarkup:
    uid = user_id
    s = get_settings(uid)
    delay = s.get("reply_delay", 3)
    btn_style = get_user_button_style(uid)
    rows = []
    
    # Delay controls
    rows.append([
        InlineKeyboardButton("➖ 1s", callback_data=f"pgc_repdelay_dec_{uid}", style=btn_style),
        InlineKeyboardButton(f"⏱ {delay}s", callback_data=f"pgc_noop_{uid}", style=btn_style),
        InlineKeyboardButton("➕ 1s", callback_data=f"pgc_repdelay_inc_{uid}", style=btn_style),
    ])

    # Presets
    rows.append([
        InlineKeyboardButton("1s", callback_data=f"pgc_repdelay_set_{uid}_1", style=btn_style),
        InlineKeyboardButton("3s", callback_data=f"pgc_repdelay_set_{uid}_3", style=btn_style),
        InlineKeyboardButton("5s", callback_data=f"pgc_repdelay_set_{uid}_5", style=btn_style),
        InlineKeyboardButton("10s", callback_data=f"pgc_repdelay_set_{uid}_10", style=btn_style),
    ])

    rows.append([InlineKeyboardButton("🔙 Back", callback_data=f"pgc_repmsgmenu_{uid}", style=btn_style)])
    return InlineKeyboardMarkup(rows)


# ==================== MESSAGE LIST SUB-MENU ====================

def build_msglist_text(user_id: int, page: int = 0) -> str:
    """Build the message list sub-menu text with selection mode info (paginated)."""
    s = get_settings(user_id)
    text_list = s.get("text_list", [])
    media_list = s.get("media_list", [])
    random_enabled = s.get("random_text", True)
    fixed_msg_idx = s.get("fixed_message_index", None)
    
    # Combined list for pagination: list of (original_type, original_index, item_data)
    combined = []
    for i, item in enumerate(text_list):
        combined.append(("text", i, item))
    for i, item in enumerate(media_list):
        combined.append(("media", i, item))
    
    total = len(combined)
    items_per_page = 6
    total_pages = max(1, (total + items_per_page - 1) // items_per_page)
    
    if page < 0: page = 0
    if page >= total_pages: page = total_pages - 1
    
    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, total)
    page_items = combined[start_idx:end_idx]
    
    lines = []
    if random_enabled:
        lines.append("🎲 <b>Mode:</b> Random - Message sent randomly")
    else:
        if fixed_msg_idx is not None:
            lines.append(f"📌 <b>Mode:</b> Fixed - Always send message #{fixed_msg_idx + 1}")
        else:
            lines.append("📋 <b>Mode:</b> Sequential - Pesan dikirim berurutan")
    
    lines.append(f"<i>Page {page+1}/{total_pages}</i>\n")
    
    if not combined:
        lines.append("📭 <i>Belum ada pesan yang ditambahkan.</i>")
    else:
        for i, (mtype, o_idx, item) in enumerate(page_items, start=start_idx + 1):
            fixed_marker = " 📌" if fixed_msg_idx == (i - 1) else ""
            if mtype == "text":
                content = item.get("content", "") if isinstance(item, dict) else str(item)
                parse_mode = item.get("parse_mode", "html") if isinstance(item, dict) else "html"
                mode_icon = {"html": "🌐", "markdown": "", "none": "📄"}.get(parse_mode, "📄")
                preview = html.escape(content[:40]) + ("..." if len(content) > 40 else "")
                lines.append(f"{i}. 📝 {mode_icon} {preview}{fixed_marker}")
            else:
                media_type = item.get("type", "unknown")
                caption = item.get("caption", "")
                type_icon = {
                    "photo": "🖼", "video": "🎬", "audio": "🎵",
                    "voice": "🎤", "document": "📄", "sticker": "🎨",
                    "animation": "🎞", "video_note": "⏺"
                }.get(media_type, "📎")
                cap_preview = html.escape(caption[:30]) if caption else "<i>no caption</i>"
                lines.append(f"{i}. {type_icon} {media_type.title()}: {cap_preview}{fixed_marker}")
    
    return (
        f"<blockquote expandable>📝 <b>Message List</b> ({total} items)\n"
        f"{'━' * 18}\n" + "\n".join(lines) + "</blockquote>"
    )

def build_msglist_kb(user_id: int, page: int = 0) -> InlineKeyboardMarkup:
    """Build the message list sub-menu keyboard with pagination (6 items per page)."""
    uid = user_id
    s = get_settings(user_id)
    text_list = s.get("text_list", [])
    media_list = s.get("media_list", [])
    btn_style = get_user_button_style(user_id)
    
    # Combined list for pagination
    combined = []
    for i, item in enumerate(text_list):
        combined.append(("text", i, item))
    for i, item in enumerate(media_list):
        combined.append(("media", i, item))
    
    total = len(combined)
    items_per_page = 6
    total_pages = max(1, (total + items_per_page - 1) // items_per_page)
    
    if page < 0: page = 0
    if page >= total_pages: page = total_pages - 1
    
    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, total)
    page_items = combined[start_idx:end_idx]
    
    rows = []
    # Row 1: Add buttons
    rows.append([
        InlineKeyboardButton("➕ Add Text", callback_data=f"pgc_addtext_{uid}", style=btn_style),
        InlineKeyboardButton("➕ Add Media", callback_data=f"pgc_addmedia_{uid}", style=btn_style),
    ])
    
    # Paginated Items
    for i, (mtype, o_idx, item) in enumerate(page_items, start=start_idx + 1):
        if mtype == "text":
            content = item.get("content", "") if isinstance(item, dict) else str(item)
            preview = content[:25].strip() + (".." if len(content) > 25 else "")
            label = f"📝 #{i}: {preview}"
            cb_fixed = f"pgc_msgsetfixed_text_{uid}_{o_idx}_p{page}"
            cb_preview = f"pgc_msgpreview_text_{uid}_{o_idx}_p{page}"
            cb_edit = f"pgc_msgeditedit_text_{uid}_{o_idx}_p{page}"
            cb_del = f"pgc_msgdelconf_text_{uid}_{o_idx}_p{page}"
        else:
            media_type = item.get("type", "unknown")
            label = f"🎬 #{i}: {media_type.title()}"
            cb_fixed = f"pgc_msgsetfixed_media_{uid}_{o_idx}_p{page}"
            cb_preview = f"pgc_msgpreview_media_{uid}_{o_idx}_p{page}"
            cb_edit = f"pgc_msgeditedit_media_{uid}_{o_idx}_p{page}"
            cb_del = f"pgc_msgdelconf_media_{uid}_{o_idx}_p{page}"
            
        rows.append([InlineKeyboardButton(label, callback_data=cb_fixed, style=btn_style)])
        rows.append([
            InlineKeyboardButton("👁 Preview", callback_data=cb_preview, style=btn_style),
            InlineKeyboardButton("✏️ Edit", callback_data=cb_edit, style=btn_style),
            InlineKeyboardButton("🗑 Delete", callback_data=cb_del, style=btn_style),
        ])
    
    # Navigation Row
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ Prev", callback_data=f"pgc_msgmenu_{uid}_page_{page-1}", style=btn_style))
    
    nav.append(InlineKeyboardButton("🔄 Refresh", callback_data=f"pgc_msgmenu_{uid}_page_{page}", style=btn_style))
    
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Next ▶️", callback_data=f"pgc_msgmenu_{uid}_page_{page+1}", style=btn_style))
    rows.append(nav)
    
    # Footer Actions
    rows.append([
        InlineKeyboardButton("🗑 Clear All", callback_data=f"pgc_msgclearconf_{uid}", style=btn_style),
        InlineKeyboardButton("📌 Set Fixed", callback_data=f"pgc_setfixed_{uid}", style=btn_style),
    ])
    
    rows.append([
        InlineKeyboardButton("⬅️ Back", callback_data=f"pgc_backmain_{uid}", style=btn_style),
    ])
    
    return InlineKeyboardMarkup(rows)

# ==================== BLACKLIST SUB-MENU ====================

def build_bl_text(user_id: int, page: int = 0) -> str:
    """Build the blacklist sub-menu text (paginated)."""
    s = get_settings(user_id)
    bl = s["blacklist"]
    
    if not bl:
        return "🚫 <b>Blacklist Manager</b>\n\n<i>No chats blacklisted.</i>"
    
    # Pagination: 10 items per page
    items_per_page = 10
    total_pages = (len(bl) + items_per_page - 1) // items_per_page
    
    # Bounds check
    if page < 0:
        page = 0
    elif page >= total_pages:
        page = total_pages - 1
    
    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, len(bl))
    page_bl = bl[start_idx:end_idx]
    
    lines = []
    for i, cid in enumerate(page_bl, start=start_idx + 1):
        lines.append(f"{i}. <code>{cid}</code>")
    
    return (
        f"<blockquote expandable>🚫 <b>Blacklist Manager</b>\n"
        f"<i>Page {page+1}/{total_pages}</i>\n"
        f"{'━' * 18}\n"
        f"Total: <b>{len(bl)}</b> chats\n\n"
        + "\n".join(lines) + "</blockquote>"
    )

def build_bl_kb(user_id: int, page: int = 0) -> InlineKeyboardMarkup:
    """Build the blacklist sub-menu keyboard (paginated)."""
    uid = user_id
    s = get_settings(user_id)
    bl = s["blacklist"]
    
    # Pagination: 10 items per page
    items_per_page = 10
    total_pages = (len(bl) + items_per_page - 1) // items_per_page
    
    # Bounds check
    if page < 0:
        page = 0
    elif page >= total_pages:
        page = total_pages - 1
    
    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, len(bl))
    page_bl = bl[start_idx:end_idx]
    
    # Get user button style
    btn_style = get_user_button_style(user_id)
    
    rows = [
        [
            InlineKeyboardButton("➕ Add Chat", callback_data=f"pgc_bladd_{uid}", style=btn_style),
            InlineKeyboardButton("🗑 Clear All", callback_data=f"pgc_blclearconf_{uid}", style=btn_style),
        ],
    ]
    
    # Show delete buttons for each blacklisted chat on current page
    for i, cid in enumerate(page_bl):
        actual_idx = start_idx + i
        rows.append([
            InlineKeyboardButton(f"Chat: {cid}", callback_data=f"pgc_noop_{uid}", style=btn_style),
            InlineKeyboardButton("🗑", callback_data=f"pgc_bldel_{uid}_{actual_idx}", style=btn_style),
        ])
    
    # Pagination buttons
    if len(bl) > items_per_page:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("◀️ Prev", callback_data=f"pgc_blmenu_{uid}_page_{page-1}", style=btn_style))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"pgc_blmenu_{uid}_page_{page+1}", style=btn_style))
        if nav_buttons:
            rows.append(nav_buttons)
    
    rows.append([
        InlineKeyboardButton("⬅️ Back", callback_data=f"pgc_backmain_{uid}", style=btn_style),
    ])
    return InlineKeyboardMarkup(rows)

# ==================== SMART PURGEME SUB-MENU ====================

def build_smartpurge_text(user_id: int) -> str:
    """Build the smart purgeme sub-menu text."""
    s = get_settings(user_id)
    status = "🟢 ENABLED" if s.get('smart_purge', False) else "🔴 DISABLED"
    
    return (
        f"<blockquote expandable>🧹 <b>Smart Purgeme Settings</b>\n"
        f"{'━' * 18}\n"
        f"Status: {status}\n\n"
        f"<b>Current Settings:</b>\n"
        f"• Limit: <b>{s.get('purge_limit', 4)} messages</b>\n"
        f"• Delay/Msg: <b>{s.get('purge_delay_msg', 1.0)}s</b>\n"
        f"• Mode: <b>{s.get('purge_mode', 'oldest').title()}</b>\n"
        f"• Offset: <b>{s.get('purge_offset', 0)} messages</b>\n\n"
        f"<i>Smart Purge akan menghapus pesan Anda di chat target\n"
        f"sebelum mengirim broadcast GCast.</i></blockquote>"
    )

def build_smartpurge_kb(user_id: int) -> InlineKeyboardMarkup:
    """Build the smart purgeme sub-menu keyboard."""
    uid = user_id
    s = get_settings(user_id)
    is_enabled = s.get('smart_purge', False)
    
    # Get user button style
    btn_style = get_user_button_style(user_id)
    
    rows = []
    
    # Row 1: Enable/Disable Toggle
    toggle_text = "🔴 Disable Smart Purge" if is_enabled else "🟢 Enable Smart Purge"
    rows.append([
        InlineKeyboardButton(toggle_text, callback_data=f"pgc_sp_toggle_{uid}", style=btn_style),
    ])
    
    # Row 2: Limit [-2] [value] [+2]
    limit = s.get('purge_limit', 4)
    rows.append([
        InlineKeyboardButton("-2", callback_data=f"pgc_sp_limit_dec_{uid}", style=btn_style),
        InlineKeyboardButton(f"Limit: {limit} msg", callback_data=f"pgc_noop_{uid}", style=btn_style),
        InlineKeyboardButton("+2", callback_data=f"pgc_sp_limit_inc_{uid}", style=btn_style),
    ])
    
    # Row 3: Delay/Msg [-0.5] [value] [+0.5]
    delay_msg = s.get('purge_delay_msg', 1.0)
    rows.append([
        InlineKeyboardButton("-0.5s", callback_data=f"pgc_sp_delay_dec_{uid}", style=btn_style),
        InlineKeyboardButton(f"Delay/Msg: {delay_msg}s", callback_data=f"pgc_noop_{uid}", style=btn_style),
        InlineKeyboardButton("+0.5s", callback_data=f"pgc_sp_delay_inc_{uid}", style=btn_style),
    ])
    
    # Row 4: Mode [Newest] [Oldest]
    mode = s.get('purge_mode', 'oldest')
    rows.append([
        InlineKeyboardButton(f"Mode: {mode.title()}", callback_data=f"pgc_noop_{uid}", style=btn_style),
        InlineKeyboardButton(("✅ " if mode == "newest" else "") + "Newest", callback_data=f"pgc_sp_mode_newest_{uid}", style=btn_style),
        InlineKeyboardButton(("✅ " if mode == "oldest" else "") + "Oldest", callback_data=f"pgc_sp_mode_oldest_{uid}", style=btn_style),
    ])
    
    # Row 5: Offset [-5] [value] [+5]
    offset = s.get('purge_offset', 0)
    rows.append([
        InlineKeyboardButton("-5", callback_data=f"pgc_sp_offset_dec_{uid}", style=btn_style),
        InlineKeyboardButton(f"Offset: {offset}", callback_data=f"pgc_noop_{uid}", style=btn_style),
        InlineKeyboardButton("+5", callback_data=f"pgc_sp_offset_inc_{uid}", style=btn_style),
    ])
    
    # Row 6: Back
    rows.append([
        InlineKeyboardButton("⬅️ Back", callback_data=f"pgc_backmain_{uid}", style=btn_style),
    ])
    
    return InlineKeyboardMarkup(rows)

# ==================== AUTO REACT SUB-MENU ====================

def build_react_text(user_id: int) -> str:
    """Build the auto react sub-menu text."""
    s = get_settings(user_id)
    status = "🟢 ENABLED" if s.get('auto_react', False) else "🔴 DISABLED"
    
    return (
        f"<blockquote expandable>⚡ <b>Auto React Settings</b>\n"
        f"{'━' * 18}\n"
        f"Status: {status}\n\n"
        f"<b>Current Settings:</b>\n"
        f"• Emoji: {s.get('react_emoji', '👍')}\n"
        f"• Delay: <b>{s.get('react_delay', 4)}s</b>\n\n"
        f"<i>Auto React akan menambahkan reaksi emoji pada pesan\n"
        f"yang berhasil dikirim ke chat target.</i></blockquote>"
    )

def build_react_kb(user_id: int) -> InlineKeyboardMarkup:
    """Build the auto react sub-menu keyboard."""
    uid = user_id
    s = get_settings(user_id)
    is_enabled = s.get('auto_react', False)
    
    # Get user button style
    btn_style = get_user_button_style(user_id)
    
    rows = []
    
    # Row 1: Enable/Disable Toggle
    toggle_text = "🔴 Disable Auto React" if is_enabled else "🟢 Enable Auto React"
    rows.append([
        InlineKeyboardButton(toggle_text, callback_data=f"pgc_react_toggle_{uid}", style=btn_style),
    ])
    
    # Row 2: Delay [-2s] [value] [+2s]
    delay = s.get('react_delay', 4)
    rows.append([
        InlineKeyboardButton("-2s", callback_data=f"pgc_react_delay_dec_{uid}", style=btn_style),
        InlineKeyboardButton(f"Delay: {delay}s", callback_data=f"pgc_noop_{uid}", style=btn_style),
        InlineKeyboardButton("+2s", callback_data=f"pgc_react_delay_inc_{uid}", style=btn_style),
    ])
    
    # Row 3: Common Emojis
    current_emoji = s.get('react_emoji', '👍')
    emojis = ['👍', '❤️', '🔥', '🎉', '😊', '💯']
    emoji_row = []
    for emoji in emojis:
        prefix = "✅ " if emoji == current_emoji else ""
        emoji_row.append(InlineKeyboardButton(f"{prefix}{emoji}", callback_data=f"pgc_react_emoji_{emoji}_{uid}", style=btn_style))
    
    # Split into 2 rows of 3 emojis each
    rows.append(emoji_row[:3])
    rows.append(emoji_row[3:])
    
    # Row 6: Back
    rows.append([
        InlineKeyboardButton("⬅️ Back", callback_data=f"pgc_backmain_{uid}", style=btn_style),
    ])
    
    return InlineKeyboardMarkup(rows)

# ==================== INFO & HELP TEXT ====================

def build_info_text(page: int = 0) -> str:
    """Build the info text with button documentation (paginated)."""
    
    # Split into pages (max ~800 chars per page for readability)
    pages = [
        # Page 0: Dashboard Buttons Part 1
        (
            "<blockquote expandable><b>📊 AUTO PRO GLOBAL BROADCAST - INFO</b>\n"
            "<i>Page 1/4</i>\n\n"
            "<b>🎯 DASHBOARD BUTTONS:</b>\n\n"
            "• <b>🟢 Start GCast</b>\n"
            "  ↳ Mulai broadcast ke semua chat yang sesuai filter\n\n"
            "• <b>🔴 Stop GCast</b>\n"
            "  ↳ Hentikan broadcast yang sedang berjalan\n\n"
            "• <b>⏸ Pause / ▶️ Resume</b>\n"
            "  ↳ Jeda atau lanjutkan broadcast\n\n"
            "• <b>📋 Chat Filter</b>\n"
            "  ↳ Pilih jenis chat: All → Groups → Personal\n\n"
            "• <b>👤 Admin Filter</b>\n"
            "  ↳ Filter berdasarkan status admin: All → Admin → Non-Admin\n\n"
            "• <b>⏱ Delay/Chat</b>\n"
            "  ↳ Atur jeda waktu antar chat (±2s, min 2s)\n\n"
            "• <b>📝 Messages</b>\n"
            "  ↳ Kelola daftar pesan broadcast (text + media)\n"
            "  ↳ Mendukung format HTML & Markdown\n"
            "  ↳ <b>👁 Preview:</b> Lihat isi pesan lengkap di LOG chat\n"
            "  ↳ <b>🗑 Delete:</b> Hapus pesan (dengan konfirmasi)\n"
            "  ↳ <b>📌 Set Fixed:</b> Pilih satu pesan tetap untuk broadcast</blockquote>"
        ),
        # Page 1: Dashboard Buttons Part 2
        (
            "<blockquote expandable><b>📊 AUTO PRO GLOBAL BROADCAST - INFO</b>\n"
            "<i>Page 2/4</i>\n\n"
            "<b>🎯 DASHBOARD BUTTONS (lanjutan):</b>\n\n"
            "• <b>🔀 Random</b>\n"
            "  ↳ Toggle mode pengiriman pesan:\n"
            "  ↳ <b>ON:</b> Pesan dipilih secara acak\n"
            "  ↳ <b>OFF + Fixed:</b> Selalu kirim pesan yang sama (aman dari spam)\n"
            "  ↳ <b>OFF + Sequential:</b> Kirim berurutan 1→2→3...→1\n\n"
            "• <b>🚫 Blacklist</b>\n"
            "  ↳ Kelola daftar chat yang dikecualikan dari broadcast\n\n"
            "• <b>📋 List Chats</b>\n"
            "  ↳ Lihat daftar chat target untuk broadcast\n\n"
            "• <b>🔁 Recurring</b>\n"
            "  ↳ Auto-restart broadcast setelah selesai satu siklus\n\n"
            "• <b>🔔 Notif</b>\n"
            "  ↳ Toggle notifikasi log ke LOG chat\n"
            "  ↳ Menampilkan detail: chat, pesan, waktu, status, error\n\n"
            "• <b>📊 Refresh</b>\n"
            "  ↳ Perbarui tampilan dashboard</blockquote>"
        ),
        # Page 2: Smart Purge & Auto React
        (
            "<blockquote expandable><b>📊 AUTO PRO GLOBAL BROADCAST - INFO</b>\n"
            "<i>Page 3/4</i>\n\n"
            "<b>🎯 FITUR LANJUTAN:</b>\n\n"
            "• <b>🧹 Smart Purge</b>\n"
            "  ↳ Hapus pesan Anda di chat target sebelum broadcast\n"
            "  ↳ <b>Limit:</b> Jumlah pesan yang akan dihapus (±2)\n"
            "  ↳ <b>Delay/Msg:</b> Jeda antar penghapusan (±0.5s)\n"
            "  ↳ <b>Mode:</b> Newest (terbaru) / Oldest (terlama)\n"
            "  ↳ <b>Offset:</b> Lewati N pesan teratas (±1)\n"
            "  ↳ Skip blacklist chat otomatis\n\n"
            "• <b>⚡ React</b>\n"
            "  ↳ Auto react pada pesan yang dikirim\n"
            "  ↳ <b>Toggle:</b> Enable/Disable auto react\n"
            "  ↳ <b>Delay:</b> Jeda sebelum react (±2s, default 4s)\n"
            "  ↳ <b>Emoji:</b> Pilih emoji (👍❤️🔥🎉😊💯)\n"
            "  ↳ React count ditampilkan di completion log</blockquote>"
        ),
        # Page 3: Dynamic Variables
        (
            "<blockquote expandable><b>📊 AUTO PRO GLOBAL BROADCAST - INFO</b>\n"
            "<i>Page 4/5</i>\n\n"
            "<b>✨ DYNAMIC VARIABLES:</b>\n\n"
            "Gunakan variabel ini agar pesan terasa lebih natural:\n\n"
            "• <code>{group_title}</code>\n"
            "  ↳ Nama group atau Nama User (jika private)\n\n"
            "• <code>{chat_name}</code>\n"
            "  ↳ Nama depan User atau Nama Group\n\n"
            "<b>💡 CONTOH PENGGUNAAN:</b>\n"
            "• <code>Halo member group {group_title}!</code>\n"
            "  ↳ <i>Halo member group Altruix Community!</i>\n\n"
            "• <code>Hi {chat_name}, apa kabar?</code>\n"
            "  ↳ <i>Hi Budi, apa kabar?</i>\n\n"
            "<i>Variabel ini bekerja di Pesan GCast & Auto-Reply.</i></blockquote>"
        ),
        # Page 4: Chat Queues
        (
            "<blockquote expandable><b>📊 AUTO PRO GLOBAL BROADCAST - INFO</b>\n"
            "<i>Page 5/6</i>\n\n"
            "<b>📁 CHAT QUEUES:</b>\n"
            "Gunakan Chat Queue untuk membuat daftar target kustom.\n\n"
            "<b>Cara Menggunakan:</b>\n"
            "1. Buka <b>Queue Manager</b> di Dashboard.\n"
            "2. Buat queue baru (misal: 'Promo').\n"
            "3. Tambahkan chat melalui tombol Edit atau perintah manual.\n"
            "4. Klik tombol <code>Chat: ...</code> di menu utama hingga muncul <code>Q: NamaQueue</code>.\n\n"
            "<b>Manual Commands:</b>\n"
            "• <code>.gcastqadd [Nama] [@id]</code>\n"
            "• <code>.gcastqdel [Nama] [id]</code>\n"
            "• <code>.gcastqlist</code></blockquote>"
        ),
        # Page 5: Format Text
        (
            "<blockquote expandable><b>📊 AUTO PRO GLOBAL BROADCAST - INFO</b>\n"
            "<i>Page 6/6</i>\n\n"
            "<b>📝 FORMAT TEXT:</b>\n\n"
            "<b>HTML Format:</b>\n"
            "• <code>&lt;b&gt;Bold&lt;/b&gt;</code> → <b>Bold</b>\n"
            "• <code>&lt;i&gt;Italic&lt;/i&gt;</code> → <i>Italic</i>\n"
            "• <code>&lt;u&gt;Underline&lt;/u&gt;</code> → <u>Underline</u>\n"
            "• <code>&lt;code&gt;Code&lt;/code&gt;</code> → <code>Code</code>\n"
            "• <code>&lt;a href='url'&gt;Link&lt;/a&gt;</code>\n\n"
            "<b>Markdown Format:</b>\n"
            "• <code>**Bold**</code> → <b>Bold</b>\n"
            "• <code>__Italic__</code> → <i>Italic</i>\n"
            "• <code>`Code`</code> → <code>Code</code>\n"
            "• <code>[Link](url)</code>\n\n"
            "<b>💡 TIPS:</b>\n"
            "• Gunakan Fixed Mode untuk menghindari spam detection\n"
            "• Smart Purge + Blacklist = chat penting tetap aman\n"
            "• Preview pesan sebelum broadcast untuk cek format\n\n"
            "<i>Gunakan tombol 'Show CMD' untuk melihat daftar command manual.</i></blockquote>"
        )
    ]
    
    # Return the requested page (with bounds checking)
    if page < 0:
        page = 0
    elif page >= len(pages):
        page = len(pages) - 1
    
    return pages[page]

def build_showcmd_text() -> str:
    """Build the command help text."""
    return (
        f"<blockquote expandable><b>📋 AUTO PRO GLOBAL BROADCAST - COMMANDS</b>\n"
        f"<code>Plugin v{PLUGIN_VERSION}</code>\n\n"
        "<b>Available Commands:</b>\n\n"
        "• <code>.gcast</code>\n"
        "  ↳ Buka dashboard GCast via Bot Assistant\n\n"
        "• <code>.gcaststart</code>\n"
        "  ↳ Quick start broadcast\n\n"
        "• <code>.gcaststop</code>\n"
        "  ↳ Hentikan broadcast yang sedang berjalan\n\n"
        "• <code>.gcastpause</code>\n"
        "  ↳ Jeda broadcast\n\n"
        "• <code>.gcastresume</code>\n"
        "  ↳ Lanjutkan broadcast yang dijeda\n\n"
        "• <code>.gcaststatus</code>\n"
        "  ↳ Lihat status dan progress broadcast\n\n"
        "• <code>.gcastbl [chat_id]</code>\n"
        "  ↳ Toggle blacklist untuk chat tertentu\n"
        "  ↳ Contoh: <code>.gcastbl -1001234567890</code>\n\n"
        "• <code>.gcastbldel &lt;chat_id&gt;</code>\n"
        "  ↳ Hapus chat dari blacklist\n"
        "  ↳ Contoh: <code>.gcastbldel -1001234567800</code>\n\n"
        "• <code>.gcastblist</code>\n"
        "  ↳ Lihat semua chat yang di-blacklist\n\n"
        "<i>Gunakan dashboard untuk pengaturan lanjutan seperti\n"
        "filter, delay, text list, dan lainnya.</i></blockquote>"
    )

# ==================== BROADCAST LOOP ====================


async def get_target_chats(client: Client, settings: dict) -> list:
    """
    Scan dialogs and return list of target chats based on filter settings.
    Returns list of dicts: {"chat_id": int, "group_title": str, "chat_name": str}.
    """
    targets = []
    blacklist = set(settings.get("blacklist", []))
    chat_filter = settings.get("chat_filter", "all")
    admin_filter = settings.get("admin_filter", "all")
    
    if chat_filter.startswith("q:"):
        queue_name = chat_filter[2:]
        queue_ids = settings.get("queues", {}).get(queue_name, [])
        for cid in queue_ids:
            if cid in blacklist: continue
            try:
                chat = await client.get_chat(cid)
                targets.append({
                    "chat_id": chat.id,
                    "group_title": chat.title or chat.first_name or f"Chat {chat.id}",
                    "chat_name": chat.first_name or chat.title or f"User {chat.id}"
                })
            except Exception as e:
                Altruix.log(f"Failed to get chat {cid} for queue {queue_name}: {e}", level=30)
        return targets

    try:
        async for dialog in client.get_dialogs():
            chat = dialog.chat
            cid = chat.id
            
            # Skip blacklisted
            if cid in blacklist:
                continue
            
            # Chat type filter
            chat_type = str(chat.type).lower()
            is_group = "group" in chat_type or "supergroup" in chat_type
            is_personal = "private" in chat_type
            is_channel = "channel" in chat_type
            
            if chat_filter == "groups" and not is_group:
                continue
            if chat_filter == "personal" and not is_personal:
                continue
            # "all" includes groups + personal (skip channels by default)
            if chat_filter == "all" and is_channel:
                continue
            
            # Admin filter (only for groups)
            if is_group and admin_filter != "all":
                try:
                    member = await client.get_chat_member(cid, client.me.id)
                    is_admin = member.status in [
                        enums.ChatMemberStatus.ADMINISTRATOR,
                        enums.ChatMemberStatus.OWNER
                    ]
                    if admin_filter == "admin" and not is_admin:
                        continue
                    if admin_filter == "nonadmin" and is_admin:
                        continue
                except Exception:
                    if admin_filter == "admin":
                        continue
            
            group_title = chat.title or chat.first_name or f"Group {cid}"
            chat_name = chat.first_name or chat.title or f"User {cid}"
            
            targets.append({
                "chat_id": cid,
                "group_title": group_title,
                "chat_name": chat_name
            })
    except Exception as e:
        Altruix.log(f"get_target_chats error: {e}", level=40, client=client)
    
    return targets

def _apply_dynamic_vars(text: str, chat_info: dict) -> str:
    """Replace dynamic variables in text with chat-specific metadata."""
    if not text or not isinstance(text, str):
        return text
    
    # {group_title} and {chat_name} replacement
    # Fallback to chat_name if group_title is missing/generic in personal chats
    group_title = chat_info.get("group_title", "")
    chat_name = chat_info.get("chat_name", "")
    
    # Basic replacements
    text = text.replace("{group_title}", group_title)
    text = text.replace("{chat_name}", chat_name)
    
    return text

async def smart_purge_chat(client: Client, chat_id: int, title: str, settings: dict, user_id: int) -> dict:
    """
    Perform Smart Purge: delete user's own messages in a chat before sending GCast.
    Returns dict with purge statistics: {"deleted": int, "errors": int}
    """
    purge_limit = settings.get("purge_limit", 4)
    purge_delay_msg = settings.get("purge_delay_msg", 1.0)
    purge_mode = settings.get("purge_mode", "oldest")
    purge_offset = settings.get("purge_offset", 0)

    stats = {"deleted": 0, "errors": 0}

    try:
        # Collect message IDs to delete
        collected_ids = []
        fetch_limit = purge_limit + purge_offset + 10

        Altruix.log(f"[Smart Purge] Scanning chat {chat_id} ({title}) - Limit: {purge_limit}, Offset: {purge_offset}, Mode: {purge_mode}", level=20, client=client)

        async for msg in client.search_messages(chat_id, from_user="me", limit=fetch_limit):
            collected_ids.append(msg.id)
            if len(collected_ids) >= fetch_limit:
                break

        if not collected_ids:
            Altruix.log(f"[Smart Purge] No messages found in chat {chat_id}", level=20, client=client)
            return stats

        # Apply mode and offset
        if purge_mode == "oldest":
            collected_ids.reverse()
        if purge_offset > 0:
            collected_ids = collected_ids[purge_offset:]
        collected_ids = collected_ids[:purge_limit]

        if not collected_ids:
            Altruix.log(f"[Smart Purge] No messages to delete after applying offset in chat {chat_id}", level=20, client=client)
            return stats

        # Delete messages with delay
        Altruix.log(f"[Smart Purge] Deleting {len(collected_ids)} messages in chat {chat_id}", level=20, client=client)
        for i in range(0, len(collected_ids), 100):
            batch = collected_ids[i:i+100]
            try:
                await client.delete_messages(chat_id, batch)
                stats["deleted"] += len(batch)
                if purge_delay_msg > 0:
                    await asyncio.sleep(purge_delay_msg)
            except FloodWait as fw:
                wait = fw.value + 3
                Altruix.log(f"[Smart Purge] FloodWait {wait}s in chat {chat_id}", level=30, client=client)
                await asyncio.sleep(wait)
                # Retry this batch
                try:
                    await client.delete_messages(chat_id, batch)
                    stats["deleted"] += len(batch)
                except Exception as e:
                    Altruix.log(f"[Smart Purge] Retry failed for chat {chat_id}: {e}", level=40, client=client)
                    stats["errors"] += len(batch)
            except ChatWriteForbidden:
                Altruix.log(f"[Smart Purge] ChatWriteForbidden in chat {chat_id}", level=30, client=client)
                stats["errors"] += len(batch)
                break
            except Exception as e:
                Altruix.log(f"[Smart Purge] Error deleting batch in chat {chat_id}: {e}", level=40, client=client)
                stats["errors"] += len(batch)

        Altruix.log(f"[Smart Purge] Completed for chat {chat_id} - Deleted: {stats['deleted']}, Errors: {stats['errors']}", level=20, client=client)
        return stats

    except Exception as e:
        Altruix.log(f"[Smart Purge] Critical error in chat {chat_id}: {e}", level=40, client=client)
        return stats


async def broadcast_loop(client: Client, user_id: int, start_index: int = 0):
    """
    Main broadcast loop. Sends messages to all target chats.
    Respects pause/stop signals and logs every action.
    If start_index > 0, resumes from that chat index (used after restart).
    """
    # Import task registry functions
    try:
        from Main.plugins.userbot.xcanceltask import register_task, unregister_task, generate_task_id
    except ImportError:
        # Fallback if xcanceltask not loaded yet
        def generate_task_id(prefix="G"): 
            import hashlib
            raw = f"{time.time()}-{random.randint(0,9999)}"
            return f"#{prefix}{hashlib.md5(raw.encode()).hexdigest()[:4]}"
        register_task = None
        unregister_task = None
    
    settings = get_settings(user_id)
    text_list = settings.get("text_list", [])
    media_list = settings.get("media_list", [])
    
    # Combine text and media into one message list
    all_messages = []
    for item in text_list:
        if isinstance(item, dict):
            all_messages.append({"type": "text", **item})
        else:
            # Old format compatibility
            all_messages.append({"type": "text", "content": str(item), "parse_mode": "html"})
    
    for item in media_list:
        # Store media_type separately to avoid conflict with type="media"
        media_item = {"type": "media", "media_type": item.get("type", "photo"), **{k: v for k, v in item.items() if k != "type"}}
        all_messages.append(media_item)
    
    if not all_messages:
        Altruix.log("❌ GCast Error: Message list is empty. Add texts or media first.", level=40, client=client)
        await send_log("❌ <b>GCast Error:</b> Message list is empty. Add texts or media first.", client=client)
        return
    
    # Generate task ID
    task_id = generate_task_id("G")
    
    # Get target chats
    await send_log(f"<blockquote expandable>📡 <b>GCast</b> <code>{task_id}</code>\n🔍 Scanning target chats...</blockquote>", client=client)
    targets = await get_target_chats(client, settings)
    
    if not targets:
        await send_log("❌ <b>GCast Error:</b> No target chats found.", client=client)
        return
    
    # Initialize task state
    pause_event = asyncio.Event()
    pause_event.set()  # Start in running state
    
    task_state = {
        "task_id": task_id,
        "running": True,
        "pause_event": pause_event,
        "sent_count": 0,
        "total_chats": len(targets),
        "current_chat": "-",
        "asyncio_task": None,  # Will be set after creating the task
        "started_at": time.time(),
        "client": client,
        "errors": 0,
        "text_idx": 0,
        "failed_chats": [],  # Track failed chats with details
        "react_count": 0,  # Track successful reactions
        "reply_idx": 0, # For sequential auto-reply
    }
    GCAST_TASKS[user_id] = task_state
    
    # Register in global task registry
    current_task = asyncio.current_task()
    task_state["asyncio_task"] = current_task
    if register_task:
        register_task(task_id, current_task, "Global BroadCast", 
                      __plugin_name__, user_id, f"Targets: {len(targets)} chats")
    
    # Get account name
    account_name = "Unknown"
    try:
        if client.me:
            first = client.me.first_name or ""
            last = client.me.last_name or ""
            account_name = f"{first} {last}".strip() or str(user_id)
    except Exception:
        account_name = str(user_id)
    
    from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    btn_style = get_user_button_style(user_id)
    kb = build_task_control_kb(user_id, task_id)
    
    started_msg = await send_log(
        f"<blockquote expandable>📡 <b>GCast Started</b> <code>{task_id}</code>\n"
        f"{'━' * 18}\n"
        f"  • <b>Account:</b> {account_name}\n"
        f"  • <b>Targets:</b> {len(targets)} chats\n"
        f"  • <b>Messages:</b> {len(all_messages)} items ({len(text_list)} text, {len(media_list)} media)\n"
        f"  • <b>Delay/Chat:</b> {settings['delay_per_chat']}s\n"
        f"  • <b>Random:</b> {'ON' if settings['random_text'] else 'OFF'}\n"
        f"  • <b>Recurring:</b> {'ON' if settings['recurring'] else 'OFF'}\n"
        f"  • <b>Chat Filter:</b> {_filter_label(settings['chat_filter'])}\n"
        f"  • <b>Admin Filter:</b> {_filter_label(settings['admin_filter'])}\n"
        f"{'━' * 18}</blockquote>",
        client=client,
        reply_markup=kb
    )
    
    # Auto-pin the GCast Started message
    await pin_log_msg(started_msg, client=client)
    task_state["log_start_msg"] = started_msg
    
    # Save persistent broadcast state for resume after restart
    save_active_task(user_id, {
        "task_id": task_id,
        "targets": targets,
        "sent_index": 0,
        "msg_idx": 0,
        "started_at": task_state["started_at"],
        "settings_snapshot": {k: v for k, v in settings.items() if k not in ("text_list", "media_list", "reply_text_list")},
    })
    
    try:
        msg_idx = 0
        for i, chat_info in enumerate(targets):
            cid = chat_info["chat_id"]
            title = chat_info["group_title"]
            # Skip already-sent chats on resume
            if i < start_index:
                task_state["sent_count"] += 1
                continue
            
            # Check if stopped
            if not task_state["running"]:
                break
            
            # Wait if paused
            await task_state["pause_event"].wait()
            
            # Double check after unpause
            if not task_state["running"]:
                break
            
            task_state["current_chat"] = title
            
            # Reset per-chat flags
            purge_count = 0
            
            # Smart Purge: Delete messages before sending GCast (if enabled)
            if settings.get("smart_purge", False):
                try:
                    purge_stats = await smart_purge_chat(client, cid, title, settings, user_id)
                    purge_count = purge_stats.get("deleted", 0)
                    if purge_count > 0:
                        Altruix.log(f"[GCast] Smart Purge completed for {title}: {purge_count} deleted", level=20, client=client)
                        # Log purge activity to group log
                        await send_log(
                            f"<blockquote expandable>"
                            f"🧹 <b>Smart Purge</b> <code>{task_id}</code>\n"
                            f"Chat: {html.escape(title[:30])}\n"
                            f"Deleted: {purge_stats['deleted']} messages\n"
                            f"Errors: {purge_stats['errors']}"
                            f"</blockquote>",
                            client=client
                        )
                except Exception as e:
                    Altruix.log(f"[GCast] Smart Purge error for {title}: {e}", level=40, client=client)
                    await send_log(
                        f"<blockquote expandable>"
                        f"⚠️ <b>Smart Purge Error</b> <code>{task_id}</code>\n"
                        f"Chat: {html.escape(title[:30])}\n"
                        f"Error: {str(e)[:100]}"
                        f"</blockquote>",
                        client=client
                    )
            
            # Pick message (text or media)
            if settings.get("random_text", True):
                # Random mode
                message = random.choice(all_messages)
            else:
                # Check if fixed message is set
                fixed_idx = settings.get("fixed_message_index", None)
                if fixed_idx is not None and 0 <= fixed_idx < len(all_messages):
                    # Fixed message mode
                    message = all_messages[fixed_idx]
                else:
                    # Sequential mode
                    message = all_messages[msg_idx % len(all_messages)]
                    msg_idx += 1
            task_state["text_idx"] = msg_idx
            
            # Initialize tracking variables
            sent_msg = None
            message_type = "Unknown"
            content_preview = ""
            
            # Send message based on type
            try:
                if message["type"] == "text":
                    # Send text message with format
                    content = message.get("content", "")
                    # Apply dynamic variables
                    content = _apply_dynamic_vars(content, chat_info)
                    
                    content_preview = content
                    message_type = "Text"
                    parse_mode_str = message.get("parse_mode", "html")
                    
                    # Convert parse_mode string to enum
                    parse_mode_enum = None
                    if parse_mode_str == "html":
                        parse_mode_enum = enums.ParseMode.HTML
                    elif parse_mode_str == "markdown":
                        parse_mode_enum = enums.ParseMode.MARKDOWN
                    
                    sent_msg = await client.send_message(cid, content, parse_mode=parse_mode_enum)
                
                elif message["type"] == "media":
                    # Send media message
                    media_subtype = message.get("media_type", message.get("type", "photo"))
                    message_type = media_subtype.title()
                    file_id = message.get("file_id")
                    caption = message.get("caption", "")
                    # Apply dynamic variables to caption
                    caption = _apply_dynamic_vars(caption, chat_info)
                    
                    content_preview = caption if caption else f"[{media_subtype}]"
                    caption_parse_mode_str = message.get("parse_mode", "html")
                    
                    # Convert parse_mode string to enum
                    caption_parse_mode = None
                    if caption_parse_mode_str == "html":
                        caption_parse_mode = enums.ParseMode.HTML
                    elif caption_parse_mode_str == "markdown":
                        caption_parse_mode = enums.ParseMode.MARKDOWN
                    
                    # Send based on media type
                    if media_subtype == "photo":
                        sent_msg = await client.send_photo(cid, file_id, caption=caption, parse_mode=caption_parse_mode)
                    elif media_subtype == "video":
                        sent_msg = await client.send_video(cid, file_id, caption=caption, parse_mode=caption_parse_mode)
                    elif media_subtype == "audio":
                        sent_msg = await client.send_audio(cid, file_id, caption=caption, parse_mode=caption_parse_mode)
                    elif media_subtype == "voice":
                        sent_msg = await client.send_voice(cid, file_id, caption=caption, parse_mode=caption_parse_mode)
                    elif media_subtype == "document":
                        sent_msg = await client.send_document(cid, file_id, caption=caption, parse_mode=caption_parse_mode)
                    elif media_subtype == "sticker":
                        sent_msg = await client.send_sticker(cid, file_id)
                    elif media_subtype == "animation":
                        sent_msg = await client.send_animation(cid, file_id, caption=caption, parse_mode=caption_parse_mode)
                    elif media_subtype == "video_note":
                        sent_msg = await client.send_video_note(cid, file_id)
                
                task_state["sent_count"] += 1
                
                # ========== PROGRESSIVE LOG: Phase 1 — Initial send ==========
                from datetime import datetime
                account_name = "Unknown"
                try:
                    if client.me:
                        first = client.me.first_name or ""
                        last = client.me.last_name or ""
                        account_name = f"{first} {last}".strip() or str(user_id)
                except Exception:
                    account_name = str(user_id)
                
                log_status = {
                    "success": True,
                    "counter": f"{task_state['sent_count']}/{task_state['total_chats']}",
                    "account_name": account_name,
                    "chat_link": build_chat_link(cid, title, sent_msg.id if sent_msg else None),
                    "chat_id": cid,
                    "message_type": message_type,
                    "content_preview": content_preview,
                    "current_time": datetime.now().strftime("%H:%M:%S"),
                }
                
                detail_log_msg = None
                if settings.get('notify_logs', True):
                    text = build_detailed_log_text(log_status)
                    detail_log_msg = await send_log(text, client=client)
                
                # ========== Auto React (with FloodWait retry) ==========
                react_success = False
                if settings.get('auto_react', False) and sent_msg:
                    try:
                        react_delay = settings.get('react_delay', 4)
                        if react_delay > 0:
                            await asyncio.sleep(react_delay)
                        
                        react_emoji = settings.get('react_emoji', '👍')
                        try:
                            await client.send_reaction(cid, sent_msg.id, react_emoji)
                        except FloodWait as fw:
                            await asyncio.sleep(fw.value + 2)
                            await client.send_reaction(cid, sent_msg.id, react_emoji)
                        task_state["react_count"] += 1
                        react_success = True
                        Altruix.log(f"[GCast] Reacted to message in {title} with {react_emoji}", level=20, client=client)
                    except Exception as e:
                        Altruix.log(f"[GCast] React error in {cid}: {e}", level=40, client=client)
                        react_success = False
                
                # ========== PROGRESSIVE LOG: Phase 2 — After purge/react ==========
                if react_success:
                    log_status["react_emoji"] = settings.get('react_emoji', '👍')
                log_status["purge_count"] = purge_count
                
                if settings.get('notify_logs', True) and detail_log_msg:
                    text = build_detailed_log_text(log_status)
                    await edit_log_msg(detail_log_msg, text, client=client)
                
                # ========== Advanced Self-Destruct & Auto-Reply Logic ==========
                sd_enabled = settings.get("self_destruct", False)
                has_reply = settings.get("auto_reply", False) and (settings.get("reply_text_list") or settings.get("reply_media_list"))
                
                if sent_msg and (sd_enabled or has_reply):
                    async def handle_post_send(c, cid, gcast_mid, s, t_state, _log_status, _log_msg, chat_info):
                        replied_msg = None
                        reply_delay_time = s.get("reply_delay", 3)
                        
                        # 1. Handle Auto-Reply
                        if has_reply:
                            await asyncio.sleep(reply_delay_time)
                            try:
                                replies_text = s.get("reply_text_list", [])
                                replies_media = s.get("reply_media_list", [])
                                all_replies = []
                                for ri, r in enumerate(replies_text): all_replies.append(("text", ri, r))
                                for ri, r in enumerate(replies_media): all_replies.append(("media", ri, r))
                                
                                if all_replies:
                                    if s.get("random_reply", True):
                                        r_type, r_o_idx, r_item = random.choice(all_replies)
                                    else:
                                        fixed_idx = s.get("reply_fixed_message_index")
                                        if fixed_idx is not None and 0 <= fixed_idx < len(all_replies):
                                            r_type, r_o_idx, r_item = all_replies[fixed_idx]
                                        else:
                                            r_idx = t_state.get("reply_idx", 0)
                                            r_type, r_o_idx, r_item = all_replies[r_idx % len(all_replies)]
                                            t_state["reply_idx"] = r_idx + 1
                                    
                                    pm_str = r_item.get("parse_mode", "html").lower()
                                    pm = enums.ParseMode.HTML if pm_str == "html" else enums.ParseMode.MARKDOWN if pm_str == "markdown" else None
                                    
                                    try:
                                        if r_type == "text":
                                            r_content = r_item["content"]
                                            # Apply dynamic variables to auto-reply
                                            r_content = _apply_dynamic_vars(r_content, chat_info)
                                            replied_msg = await c.send_message(chat_id=cid, text=r_content, reply_to_message_id=gcast_mid, parse_mode=pm)
                                        else:
                                            m_subtype = r_item.get("media_type", r_item.get("type", "photo"))
                                            f_id = r_item.get("file_id")
                                            cap = r_item.get("caption", "")
                                            # Apply dynamic variables to auto-reply media caption
                                            cap = _apply_dynamic_vars(cap, chat_info)
                                            
                                            if m_subtype == "photo": replied_msg = await c.send_photo(cid, f_id, caption=cap, reply_to_message_id=gcast_mid, parse_mode=pm)
                                            elif m_subtype == "video": replied_msg = await c.send_video(cid, f_id, caption=cap, reply_to_message_id=gcast_mid, parse_mode=pm)
                                            elif m_subtype == "audio": replied_msg = await c.send_audio(cid, f_id, caption=cap, reply_to_message_id=gcast_mid, parse_mode=pm)
                                            elif m_subtype == "voice": replied_msg = await c.send_voice(cid, f_id, caption=cap, reply_to_message_id=gcast_mid, parse_mode=pm)
                                            elif m_subtype == "document": replied_msg = await c.send_document(cid, f_id, caption=cap, reply_to_message_id=gcast_mid, parse_mode=pm)
                                            elif m_subtype == "sticker": replied_msg = await c.send_sticker(cid, f_id, reply_to_message_id=gcast_mid)
                                            elif m_subtype == "animation": replied_msg = await c.send_animation(cid, f_id, caption=cap, reply_to_message_id=gcast_mid, parse_mode=pm)
                                            elif m_subtype == "video_note": replied_msg = await c.send_video_note(cid, f_id, reply_to_message_id=gcast_mid)
                                        _log_status["reply_status"] = "Done"
                                    except Exception as reply_err:
                                        # Auto-skip if message not found / deleted
                                        Altruix.log(f"[GCast] Auto-Reply skipped in {cid}: {reply_err}", level=30, client=client)
                                        _log_status["reply_status"] = f"Skipped ({type(reply_err).__name__})"
                                        replied_msg = None
                            except FloodWait as fw:
                                Altruix.log(f"[GCast] Auto-Reply FloodWait in {cid}: {fw.value + 3}s", level=40, client=client)
                                await asyncio.sleep(fw.value + 3)
                            except Exception as e:
                                if "MESSAGE_ID_INVALID" not in str(e):
                                    Altruix.log(f"[GCast] Auto-Reply error in {cid}: {e}", level=40, client=client)
                                    _log_status["reply_status"] = f"Error ({type(e).__name__})"
                        
                        # ===== PROGRESSIVE LOG: Phase 3 — After reply =====
                        if _log_msg and s.get('notify_logs', True) and _log_status.get("reply_status"):
                            text = build_detailed_log_text(_log_status)
                            await edit_log_msg(_log_msg, text, client=c)
                        
                        # 2. Handle Advanced Self-Destruct
                        if sd_enabled:
                            sd_delay_time = s.get("self_destruct_delay", 30)
                            sd_target = s.get("sd_target", "gcast")
                            sd_trigger = s.get("sd_trigger", "after_gcast")
                            
                            # Calculate exact remaining delay
                            remaining_delay = sd_delay_time
                            if has_reply and sd_trigger == "after_gcast":
                                remaining_delay = max(0, sd_delay_time - reply_delay_time)
                            
                            if remaining_delay > 0:
                                await asyncio.sleep(remaining_delay)
                                
                            msg_ids_to_del = []
                            if sd_target in ["gcast", "both"]:
                                msg_ids_to_del.append(gcast_mid)
                            if sd_target in ["reply", "both"] and replied_msg:
                                msg_ids_to_del.append(replied_msg.id)
                                
                            if msg_ids_to_del:
                                try:
                                    await c.delete_messages(cid, msg_ids_to_del)
                                    if sd_target in ["gcast", "both"]:
                                        _log_status["sd_gcast_status"] = "Done"
                                    if sd_target in ["reply", "both"]:
                                        _log_status["sd_reply_status"] = "Done" if replied_msg else "Skipped (no reply)"
                                except Exception:
                                    if sd_target in ["gcast", "both"]:
                                        _log_status["sd_gcast_status"] = "Failed"
                                    if sd_target in ["reply", "both"]:
                                        _log_status["sd_reply_status"] = "Failed"
                            else:
                                if sd_target in ["gcast", "both"]:
                                    _log_status["sd_gcast_status"] = "Pending"
                                if sd_target in ["reply", "both"]:
                                    _log_status["sd_reply_status"] = "Skipped (no reply)" if not replied_msg else "Pending"
                            
                            # ===== PROGRESSIVE LOG: Phase 4 — After self-destruct =====
                            if _log_msg and s.get('notify_logs', True):
                                text = build_detailed_log_text(_log_status)
                                await edit_log_msg(_log_msg, text, client=c)
                    
                    asyncio.create_task(handle_post_send(client, cid, sent_msg.id, settings, task_state, log_status, detail_log_msg, chat_info))
                
                # Log every 10 chats or last chat
                if (i + 1) % 10 == 0 or (i + 1) == len(targets):
                    pct = ((i + 1) / len(targets)) * 100
                    await send_log(
                        f"📡 <b>GCast</b> <code>{task_id}</code>\n"
                        f"Progress: {i+1}/{len(targets)} ({pct:.1f}%)\n"
                        f"Last: {html.escape(title[:30])}",
                        client=client
                    )
            except FloodWait as fw:
                wait = fw.value + 3
                Altruix.log(f"[GCast] FloodWait {wait}s at chat {cid}", level=30)
                task_state["errors"] += 1
                
                # Track failed chat
                from datetime import datetime
                task_state["failed_chats"].append({
                    "chat_id": cid,
                    "chat_title": title,
                    "error": f"FloodWait: {wait}s",
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                })
                
                # Detailed notification for failure
                if settings.get('notify_logs', True):
                    await send_detailed_log(
                        user_id=user_id,
                        chat_id=cid,
                        chat_title=title,
                        message_type=message_type,
                        content_preview=content_preview,
                        success=False,
                        error_reason=f"FloodWait: {wait}s",
                        purge_count=0,
                        react_success=False,
                        client=client,
                        sent_message_id=None
                    )
                
                await send_log(
                    f"⚠️ <b>GCast FloodWait</b> <code>{task_id}</code>\n"
                    f"Waiting {wait}s...", client=client
                )
                await asyncio.sleep(wait)
                
            except ChatWriteForbidden:
                task_state["errors"] += 1
                Altruix.log(f"[GCast] ChatWriteForbidden: {cid}", level=30)
                
                # Track failed chat
                from datetime import datetime
                task_state["failed_chats"].append({
                    "chat_id": cid,
                    "chat_title": title,
                    "error": "ChatWriteForbidden",
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                })
                
                # Detailed notification for failure
                if settings.get('notify_logs', True):
                    await send_detailed_log(
                        user_id=user_id,
                        chat_id=cid,
                        chat_title=title,
                        message_type=message_type,
                        content_preview=content_preview,
                        success=False,
                        error_reason="ChatWriteForbidden - No permission to send messages",
                        purge_count=0,
                        react_success=False,
                        client=client,
                        sent_message_id=None
                    )
                
            except (errors.ChannelInvalid, errors.ChannelPrivate, errors.PeerIdInvalid):
                task_state["errors"] += 1
                Altruix.log(f"[GCast] Invalid chat: {cid}", level=30)
                
                # Track failed chat
                from datetime import datetime
                task_state["failed_chats"].append({
                    "chat_id": cid,
                    "chat_title": title,
                    "error": "Invalid/Private Channel",
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                })
                
                # Detailed notification for failure
                if settings.get('notify_logs', True):
                    await send_detailed_log(
                        user_id=user_id,
                        chat_id=cid,
                        chat_title=title,
                        message_type=message_type,
                        content_preview=content_preview,
                        success=False,
                        error_reason="Invalid or Private Channel",
                        purge_count=0,
                        react_success=False,
                        client=client,
                        sent_message_id=None
                    )
                
            except Exception as e:
                task_state["errors"] += 1
                Altruix.log(f"[GCast] Error sending to {cid}: {e}", level=40)
                
                # Track failed chat
                from datetime import datetime
                task_state["failed_chats"].append({
                    "chat_id": cid,
                    "chat_title": title,
                    "error": str(e),
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                })
                
                # Detailed notification for failure
                if settings.get('notify_logs', True):
                    await send_detailed_log(
                        user_id=user_id,
                        chat_id=cid,
                        chat_title=title,
                        message_type=message_type,
                        content_preview=content_preview,
                        success=False,
                        error_reason=str(e),
                        purge_count=0,
                        react_success=False,
                        client=client,
                        sent_message_id=None
                    )
            
            # Delay between chats (re-read from settings in case updated)
            current_settings = get_settings(user_id)
            delay = current_settings.get("delay_per_chat", 6)
            await asyncio.sleep(delay)
            
            # Debounced persistent state save (every 5 chats)
            if (i + 1) % 5 == 0 or (i + 1) == len(targets):
                save_active_task(user_id, {
                    "task_id": task_id,
                    "targets": targets,
                    "sent_index": i + 1,
                    "msg_idx": msg_idx,
                    "started_at": task_state["started_at"],
                    "settings_snapshot": {k: v for k, v in settings.items() if k not in ("text_list", "media_list", "reply_text_list")},
                })
        
        # Broadcast completed
        task_state["running"] = False
        remove_active_task(user_id)
        await unpin_log_msg(task_state.get("log_start_msg"), client=client)
        
        sent = task_state["sent_count"]
        errs = task_state["errors"]
        elapsed = int(time.time() - task_state["started_at"])
        mins, secs = divmod(elapsed, 60)
        
        # Calculate success rate
        success_rate = (sent / len(targets) * 100) if len(targets) > 0 else 0
        
        await send_log(
            f"<blockquote expandable>✅ <b>GCast Completed</b> <code>{task_id}</code>\n"
            f"{'━' * 18}\n"
            f"  • <b>Account:</b> <b>{account_name}</b>\n"
            f"  • <b>Statistics:</b>\n"
            f"  • <b>Sent:</b> <code>{sent}/{len(targets)}</code> ({success_rate:.1f}%)\n"
            f"  • <b>Failed:</b> <code>{errs}</code> chats\n"
            f"  • <b>Reacted:</b> <code>{task_state.get('react_count', 0)}</code> messages\n"
            f"  • <b>Duration:</b> <code>{mins}</code>m <code>{secs}</code>s\n"
            f"  • <b>Delay/Chat:</b> <code>{settings['delay_per_chat']}</code>s\n"
            f"  • <b>Messages Used:</b> <code>{len(all_messages)}</code> items (<code>{len(text_list)}</code> text, <code>{len(media_list)}</code> media)\n"
            f"{'━' * 18}</blockquote>",
            client=client
        )
        
        # Send failed chats summary if any
        if task_state.get("failed_chats") and len(task_state["failed_chats"]) > 0 and settings.get('notify_logs', True):
            from datetime import datetime
            failed_text = "<blockquote expandable>❌ <b>Failed Chats Summary</b>\n"
            failed_text += f"{'━' * 18}\n"
            failed_text += f"Total Failed: <b>{len(task_state['failed_chats'])}</b> chats\n\n"
            
            # Show max 20 failed chats
            for fc in task_state["failed_chats"][:20]:
                chat_link = f"<a href='tg://openmessage?chat_id={fc['chat_id']}'>{html.escape(fc['chat_title'][:30])}</a>"
                failed_text += f"• {chat_link}\n"
                failed_text += f"  ⚠️ {html.escape(fc['error'][:60])}\n"
                failed_text += f"  🕒 {fc['timestamp']}\n\n"
            
            if len(task_state["failed_chats"]) > 20:
                failed_text += f"<i>... and {len(task_state['failed_chats']) - 20} more</i>\n\n"
            
            failed_text += f"{'━' * 18}</blockquote>"
            await send_log(failed_text, client=client)
        
        # Check recurring
        current_settings = get_settings(user_id)
        if current_settings.get("recurring", False):
            mode = current_settings.get("recurring_mode", "interval")
            wait_seconds = 10 # Default fallback
            
            if mode == "interval":
                h = current_settings.get("recurring_interval_hours", 0)
                m = current_settings.get("recurring_interval_minutes", 10)
                wait_seconds = (h * 3600) + (m * 60)
                if wait_seconds < 10: wait_seconds = 10
                
                next_run_dt = datetime.now() + timedelta(seconds=wait_seconds)
                next_run_str = next_run_dt.strftime("%H:%M:%S")
                await send_log(
                    f"🔁 <b>GCast Recurring (Interval)</b> <code>{task_id}</code>\n"
                    f"Next run: <b>{next_run_str}</b> (In {h}h {m}m)", client=client
                )
            else: # mode == "time"
                sh = current_settings.get("recurring_specific_hour", 0)
                sm = current_settings.get("recurring_specific_minute", 0)
                now = datetime.now()
                target_time = now.replace(hour=sh, minute=sm, second=0, microsecond=0)
                if target_time <= now:
                    target_time += timedelta(days=1)
                
                wait_seconds = int((target_time - now).total_seconds())
                next_run_str = target_time.strftime("%d/%m %H:%M:%S")
                
                await send_log(
                    f"🕒 <b>GCast Recurring (Specific Time)</b> <code>{task_id}</code>\n"
                    f"Target Time: <b>{sh:02d}:{sm:02d}</b>\n"
                    f"Next run: <b>{next_run_str}</b>", client=client
                )

            await asyncio.sleep(wait_seconds)
            # Create new task for the next cycle
            new_task = asyncio.create_task(broadcast_loop(client, user_id))
            GCAST_TASKS[user_id] = {**task_state, "asyncio_task": new_task, "running": True}
    
    except asyncio.CancelledError:
        remove_active_task(user_id)
        await unpin_log_msg(task_state.get("log_start_msg"), client=client)
        await send_log(
            f"🛑 <b>GCast Cancelled</b> <code>{task_id}</code>\n"
            f"Sent: {task_state['sent_count']}/{len(targets)}",
            client=client
        )
    except Exception as e:
        remove_active_task(user_id)
        await unpin_log_msg(task_state.get("log_start_msg"), client=client)
        Altruix.log(f"[GCast] Critical error: {e}", level=50)
        await send_log(f"❌ <b>GCast Error</b> <code>{task_id}</code>\n{e}", client=client)
    finally:
        # Cleanup
        if user_id in GCAST_TASKS and GCAST_TASKS[user_id].get("task_id") == task_id:
            GCAST_TASKS[user_id]["running"] = False
        if unregister_task:
            unregister_task(task_id)


# ==================== CALLBACK HANDLERS ====================

@Altruix.bot.on_callback_query(filters.regex(r"^pgc_(.+)$"))
@iuser_check
@log_errors
async def pgc_callback_handler(c: Client, cb: CallbackQuery):
    """Master callback handler for all pgc_ prefixed callbacks.
    Protected by @iuser_check for auth verification and group log logging."""
    data = cb.data
    # Parse: pgc_action_uid or pgc_action_uid_extra
    parts = data.split("_")
    # Minimum: pgc_action_uid
    if len(parts) < 3:
        await safe_cb_answer(cb, "Invalid callback data.", show_alert=True)
        return
    
    action = parts[1]
    
    # ✅ FIXED: Extract user_id with proper handling for different formats
    uid = None
    try:
        # Format detection based on action
        if action in ["msgpreview", "msgdelconf", "msgdel", "msgsetfixed", "repmsgpreview", "repmsgdelconf", "repmsgdel", "repmsgsetfixed"]:
            # Format: pgc_action_type_uid_index[_pPAGE]
            if len(parts) >= 4:
                uid = int(parts[3])
                
        elif action in ["pause", "resume", "stop", "status"]:
            if len(parts) >= 3:
                uid = int(parts[2])

        elif action in ["bldel", "rec", "rec_set_rep_h", "rec_set_rep_m", "rec_set_spec"]:
            # Example: pgc_rec_menu_7844837037 or pgc_rec_set_rep_h_1_7844837037
            # UID is frequently the last part
            uid = int(parts[-1])
            
        elif len(parts) >= 5 and parts[-2] == "page":
            uid = int(parts[2])
        else:
            # Standard: pgc_action_uid
            for i in range(len(parts) - 1, 1, -1):
                try:
                    uid = int(parts[i])
                    break
                except ValueError:
                    continue
        
        if uid is None:
            raise ValueError("No valid user ID found")
    except (ValueError, IndexError):
        await safe_cb_answer(cb, "Invalid user ID.", show_alert=True)
        return
    
    s = get_settings(uid)
    btn_style = get_user_button_style(uid)
    
    # ========== TASK CONTROLS ==========
    
    if action in ["pause", "resume", "stop", "status"]:
        state = GCAST_TASKS.get(uid)
        
        # If task_id is provided in callback (from log msg), use it to check
        if len(parts) >= 4:
            task_id = "_".join(parts[3:])
            if not state or state.get("task_id") != task_id:
                await safe_cb_answer(cb, "❌ Task not found or already finished.", show_alert=True)
                return
        else:
            # If no task_id provided (from dashboard), just act on the user's active task
            if not state or not state.get("running"):
                await safe_cb_answer(cb, "⚫ No active broadcast.", show_alert=True)
                return
            task_id = state.get("task_id")

        if action == "pause":
            if state.get("pause_event"):
                state["pause_event"].clear()
            await safe_cb_answer(cb, "⏸ GCast paused.", show_alert=True)
        elif action == "resume":
            if state.get("pause_event"):
                state["pause_event"].set()
            await safe_cb_answer(cb, "▶️ GCast resumed.", show_alert=True)
        elif action == "stop":
            state["running"] = False
            if state.get("pause_event"):
                state["pause_event"].set()
            await safe_cb_answer(cb, "⏹ GCast stopped.", show_alert=True)
        elif action == "status":
            pct = (state["sent_count"] / state["total_chats"]) * 100 if state["total_chats"] > 0 else 0
            is_running = state.get("pause_event") and state["pause_event"].is_set()
            status_text = f"Status: {'Running' if is_running else 'Paused'}\n"
            status_text += f"Progress: {state['sent_count']}/{state['total_chats']} ({pct:.1f}%)\n"
            status_text += f"Errors: {state['errors']}"
            await safe_cb_answer(cb, status_text, show_alert=True)
            return

        # UI Refresh
        if len(parts) >= 4:
            # From Log Message: Update specific control buttons
            kb = build_task_control_kb(uid, task_id)
            await safe_edit_message(cb, cb.message.text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        else:
            # From Dashboard: Refresh full dashboard
            text = build_dashboard_text(uid)
            kb = build_dashboard_kb(uid)
            await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        return

    # ========== MAIN MENU ACTIONS ==========
    
    if action == "noop":
        await safe_cb_answer(cb, "ℹ️ This is a display-only button.", show_alert=False)
        return
    
    elif action == "close":
        try:
            await cb.message.delete()
        except Exception:
            pass
        await safe_cb_answer(cb, "Menu closed.", show_alert=False)
        return
    
    elif action == "backmain":
        # Return to main dashboard
        text = build_dashboard_text(uid)
        kb = build_dashboard_kb(uid)
        success = await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        if success:
            await safe_cb_answer(cb, "Main menu.", show_alert=False)
        return
    
    elif action == "chatfilter":
        # Cycle: all → groups → personal → [queues] → all
        options = ["all", "groups", "personal"]
        queues = list(s.get("queues", {}).keys())
        for q in queues:
            options.append(f"q:{q}")
        
        current = s.get("chat_filter", "all")
        try:
            next_idx = (options.index(current) + 1) % len(options)
        except ValueError:
            next_idx = 0
            
        s["chat_filter"] = options[next_idx]
        save_settings(uid, s)
        text = build_dashboard_text(uid)
        kb = build_dashboard_kb(uid)
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        await safe_cb_answer(cb, f"Chat filter: {_filter_label(s['chat_filter'])}", show_alert=False)
        return
    
    elif action == "adminfilter":
        # Cycle: all → admin → nonadmin → all
        cycle = {"all": "admin", "admin": "nonadmin", "nonadmin": "all"}
        s["admin_filter"] = cycle.get(s["admin_filter"], "all")
        save_settings(uid, s)
        text = build_dashboard_text(uid)
        kb = build_dashboard_kb(uid)
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        await safe_cb_answer(cb, f"Admin filter: {_filter_label(s['admin_filter'])}", show_alert=False)
        return
    
    elif action == "delay":
        # parts: pgc_delay_dec/inc_uid
        if len(parts) < 4:
            return
        direction = parts[2]
        
        if direction == "dec":
            s["delay_per_chat"] = max(2, s["delay_per_chat"] - 2)
        elif direction == "inc":
            s["delay_per_chat"] = s["delay_per_chat"] + 2
        
        save_settings(uid, s)
        text = build_dashboard_text(uid)
        kb = build_delay_submenu_kb(uid) # Return to Delay SubMenu
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        await safe_cb_answer(cb, f"Delay: {s['delay_per_chat']}s", show_alert=False)
        return

    elif action == "delayset":
        # parts: pgc_delayset_VAL_uid
        if len(parts) < 4:
            return
        try:
            val = int(parts[2])
            s["delay_per_chat"] = val
            save_settings(uid, s)
            text = build_dashboard_text(uid)
            kb = build_delay_submenu_kb(uid)
            await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            await safe_cb_answer(cb, f"Delay set to {val}s", show_alert=False)
        except Exception:
            pass
        return

    elif action == "delaymenu":
        text = build_dashboard_text(uid)
        kb = build_delay_submenu_kb(uid)
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        await safe_cb_answer(cb, "Delay settings.", show_alert=False)
        return
    
    elif action == "randomtoggle":
        s["random_text"] = not s["random_text"]
        save_settings(uid, s)
        text = build_dashboard_text(uid)
        kb = build_dashboard_kb(uid)
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        await safe_cb_answer(cb, f"Random: {'ON' if s['random_text'] else 'OFF'}", show_alert=False)
        return
    
    elif action == "recurring":
        # Legacy toggle, redirect to menu or keep simple?
        # User requested sub-menus, so let's redirect pgc_recurring to menu
        text = build_dashboard_text(uid)
        kb = build_recurring_settings_kb(uid)
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        await safe_cb_answer(cb, "Recurring Settings.", show_alert=False)
        return

    # Granular Recurring Handlers
    elif action == "rec":
        # pgc_rec_SUB_uid or pgc_rec_set_rep_h_VAL_uid
        sub = parts[2]
        if sub == "menu":
            kb = build_recurring_settings_kb(uid)
            await safe_edit_message(cb, build_dashboard_text(uid), reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            await safe_cb_answer(cb, "Recurring settings.")
        elif sub == "toggle":
            s["recurring"] = not s.get("recurring", False)
            save_settings(uid, s)
            kb = build_recurring_settings_kb(uid)
            await safe_edit_message(cb, build_dashboard_text(uid), reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            await safe_cb_answer(cb, f"Recurring: {'ENABLED' if s['recurring'] else 'DISABLED'}")
        elif sub == "rep":
            s["recurring_mode"] = "interval"
            save_settings(uid, s)
            kb = build_repetition_menu_kb(uid)
            await safe_edit_message(cb, build_dashboard_text(uid), reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            await safe_cb_answer(cb, "Interval Repetition settings.")
        elif sub == "time":
            s["recurring_mode"] = "time"
            save_settings(uid, s)
            kb = build_time_menu_kb(uid)
            await safe_edit_message(cb, build_dashboard_text(uid), reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            await safe_cb_answer(cb, "Specific Time settings.")
        
        # Handling for: pgc_rec_set_rep_h_VAL_uid
        elif sub == "set" and len(parts) >= 6:
            action_type = parts[3] # rep
            sub_type = parts[4] # h or m or spec
            
            if action_type == "rep":
                if sub_type == "h":
                    try:
                        val = int(parts[5])
                        s["recurring_interval_hours"] = val
                        save_settings(uid, s)
                        kb = build_repetition_menu_kb(uid)
                        await safe_edit_message(cb, build_dashboard_text(uid), reply_markup=kb, parse_mode=enums.ParseMode.HTML)
                        await safe_cb_answer(cb, f"Interval Hours set to {val}h")
                    except Exception as e:
                        await safe_cb_answer(cb, f"❌ Error: {e}", show_alert=True)
                elif sub_type == "m":
                    try:
                        val = int(parts[5])
                        s["recurring_interval_minutes"] = val
                        save_settings(uid, s)
                        kb = build_repetition_menu_kb(uid)
                        await safe_edit_message(cb, build_dashboard_text(uid), reply_markup=kb, parse_mode=enums.ParseMode.HTML)
                        await safe_cb_answer(cb, f"Interval Minutes set to {val}m")
                    except Exception as e:
                        await safe_cb_answer(cb, f"❌ Error: {e}", show_alert=True)
            elif action_type == "spec":
                sub_type = parts[4] # h or m
                try:
                    val = int(parts[5])
                    if sub_type == "h":
                        s["recurring_specific_hour"] = val
                        msg = f"Specific Hour set to {val:02d}"
                    else: # m
                        s["recurring_specific_minute"] = val
                        msg = f"Specific Minute set to {val:02d}"
                        
                    save_settings(uid, s)
                    kb = build_time_menu_kb(uid)
                    await safe_edit_message(cb, build_dashboard_text(uid), reply_markup=kb, parse_mode=enums.ParseMode.HTML)
                    await safe_cb_answer(cb, msg)
                except Exception as e:
                    await safe_cb_answer(cb, f"❌ Error: {e}", show_alert=True)
        else:
            # Prevent stuck spinner if unknown sub-action
            await safe_cb_answer(cb, "Unknown recurring sub-action.")
        return
    
    elif action == "notiftoggle":
        s["notify_logs"] = not s.get("notify_logs", True)
        save_settings(uid, s)
        text = build_dashboard_text(uid)
        kb = build_dashboard_kb(uid)
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        await safe_cb_answer(cb, f"Notif Logs: {'ON' if s['notify_logs'] else 'OFF'}", show_alert=False)
        return
    
    # ========== QUEUE MANAGER ACTIONS ==========

    elif action == "queuemgr":
        text = (
            f"<blockquote expandable>📁 <b>Chat Queue Manager</b>\n"
            f"{'━' * 18}\n"
            f"Kelola daftar target chat kustom Anda.\n"
            f"Pilih queue untuk filter gcast yang lebih spesifik.</blockquote>"
        )
        kb = build_queuemgr_kb(uid)
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        await safe_cb_answer(cb, "Queue Manager.", show_alert=False)
        return

    elif action == "qadd":
        # Request new queue name
        GCAST_TEXT_INPUT_STATE[uid] = {"action": "qadd"}
        text = (
            f"<blockquote expandable>➕ <b>Create New Queue</b>\n"
            f"{'━' * 18}\n"
            f"Silahkan balas (reply) pesan ini dengan <b>Nama Queue</b> baru yang ingin Anda buat.\n\n"
            f"Contoh: <code>Queue1</code> atau <code>Target Promosi</code></blockquote>"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data=f"pgc_queuemgr_{uid}", style=btn_style)]])
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        await safe_cb_answer(cb, "📝 Silahkan balas (reply) pesan di LOG/Bot dengan Nama Queue baru.", show_alert=True)
        return

    elif action == "qeditname":
        if len(parts) < 4: return
        q_name = _resolve_q_name(uid, parts[3])
        GCAST_TEXT_INPUT_STATE[uid] = {"action": "qeditname", "old_name": q_name}
        text = (
            f"<blockquote expandable>✏️ <b>Edit Queue Name</b>\n"
            f"{'━' * 18}\n"
            f"Queue saat ini: <code>{q_name}</code>\n\n"
            f"Silahkan balas (reply) pesan ini dengan <b>Nama Baru</b> untuk queue ini.</blockquote>"
        )
        q_hash = _get_q_hash(q_name)
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data=f"pgc_qedit_{uid}_h:{q_hash}", style=btn_style)]])
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        await safe_cb_answer(cb, "📝 Silahkan balas (reply) pesan ini dengan Nama Baru.", show_alert=True)
        return

    elif action == "qedit":
        if len(parts) < 4: return
        # Might be hashed: h:hash
        raw_q = parts[3]
        q_name = _resolve_q_name(uid, raw_q)
        
        text = (
            f"<blockquote expandable>📁 <b>Edit Queue: {q_name}</b>\n"
            f"{'━' * 18}\n"
            f"Gunakan tombol di bawah untuk menambah atau menghapus chat dari queue ini.</blockquote>"
        )
        kb = build_queue_edit_kb(uid, q_name)
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        await safe_cb_answer(cb, f"Editing queue: {q_name}", show_alert=False)
        return

    elif action == "qdelconf":
        if len(parts) < 4: return
        q_name = _resolve_q_name(uid, parts[3])
        q_hash = _get_q_hash(q_name)
        text = (
            f"<blockquote expandable>⚠️ <b>Delete Queue: {q_name}</b>\n"
            f"{'━' * 18}\n"
            f"Apakah Anda yakin ingin menghapus queue ini?\n"
            f"Tindakan ini tidak dapat dibatalkan.</blockquote>"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Yes, Delete", callback_data=f"pgc_qdel_{uid}_h:{q_hash}", style=btn_style)],
            [InlineKeyboardButton("⬅️ Cancel", callback_data=f"pgc_queuemgr_{uid}", style=btn_style)]
        ])
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        return

    elif action == "qdel":
        if len(parts) < 4: return
        q_name = _resolve_q_name(uid, parts[3])
        queues = s.get("queues", {})
        if q_name in queues:
            del queues[q_name]
            s["queues"] = queues
            if s["chat_filter"] == f"q:{q_name}":
                s["chat_filter"] = "all"
            save_settings(uid, s)
            await safe_cb_answer(cb, f"Queue '{q_name}' deleted.", show_alert=True)
        
        # Back to mgr
        text = (
            f"<blockquote expandable>📁 <b>Chat Queue Manager</b>\n"
            f"{'━' * 18}\n"
            f"Kelola daftar target chat kustom Anda.\n"
            f"Pilih queue untuk filter gcast yang lebih spesifik.</blockquote>"
        )
        kb = build_queuemgr_kb(uid)
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        return

    elif action == "qaddchat":
        if len(parts) < 4: return
        q_name = _resolve_q_name(uid, parts[3])
        cid = cb.message.chat.id
        title = cb.message.chat.title or cb.message.chat.first_name or "Unknown"
        
        queues = s.get("queues", {})
        if q_name not in queues: queues[q_name] = []
        if cid not in queues[q_name]:
            queues[q_name].append(cid)
            s["queues"] = queues
            save_settings(uid, s)
            await safe_cb_answer(cb, f"Added {title} ({cid}) to {q_name}.", show_alert=True)
        else:
            await safe_cb_answer(cb, f"Chat already in queue {q_name}.", show_alert=True)
            
        kb = build_queue_edit_kb(uid, q_name)
        await safe_edit_message(cb, cb.message.text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        return

    elif action == "qaddid":
        if len(parts) < 4: return
        q_name = _resolve_q_name(uid, parts[3])
        GCAST_TEXT_INPUT_STATE[uid] = {"action": "qaddid", "qname": q_name}
        text = (
            f"<blockquote expandable>➕ <b>Add Chat to Queue: {q_name}</b>\n"
            f"{'━' * 18}\n"
            f"Silahkan balas (reply) pesan ini dengan <b>Chat ID</b> atau <b>Username</b> grup/user yang ingin Anda tambahkan ke queue.</blockquote>"
        )
        q_hash = _get_q_hash(q_name)
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data=f"pgc_qedit_{uid}_h:{q_hash}", style=btn_style)]])
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        await safe_cb_answer(cb, "📝 Silahkan balas (reply) pesan di LOG/Bot dengan Chat ID/Username.", show_alert=True)
        return

    elif action == "qremchat":
        # pgc_qremchat_uid_hash_cid
        if len(parts) < 5: return
        # CID is the last part
        cid_str = parts[-1]
        try:
            cid = int(cid_str)
            raw_q = parts[3]
            q_name = _resolve_q_name(uid, raw_q)
            queues = s.get("queues", {})
            if q_name in queues and cid in queues[q_name]:
                queues[q_name].remove(cid)
                s["queues"] = queues
                save_settings(uid, s)
                await safe_cb_answer(cb, f"Removed {cid} from {q_name}.", show_alert=True)
        except Exception:
            await safe_cb_answer(cb, "Failed to remove chat.", show_alert=True)
            
        # Refresh
        kb = build_queue_edit_kb(uid, q_name)
        await safe_edit_message(cb, cb.message.text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        return

    elif action == "smartpurge":
        # Open smart purge sub-menu
        text = build_smartpurge_text(uid)
        kb = build_smartpurge_kb(uid)
        success = await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        if success:
            await safe_cb_answer(cb, "Smart Purge settings.", show_alert=False)
        return
    
    elif action == "reactmenu":
        # Open auto react sub-menu
        text = build_react_text(uid)
        kb = build_react_kb(uid)
        success = await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        if success:
            await safe_cb_answer(cb, "Auto React settings.", show_alert=False)
        return
    
    elif action == "react":
        # Auto React sub-actions: toggle, delay, emoji
        if len(parts) < 3:
            return
        sub_action = parts[2]
        
        if sub_action == "toggle":
            s["auto_react"] = not s.get("auto_react", False)
            save_settings(uid, s)
            text = build_react_text(uid)
            kb = build_react_kb(uid)
            await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            await safe_cb_answer(cb, f"Auto React: {'ON' if s['auto_react'] else 'OFF'}", show_alert=False)
        elif sub_action == "delay":
            direction = parts[3] if len(parts) > 3 else None
            if direction == "dec":
                s["react_delay"] = max(0, s.get("react_delay", 4) - 2)
            elif direction == "inc":
                s["react_delay"] = s.get("react_delay", 4) + 2
            save_settings(uid, s)
            text = build_react_text(uid)
            kb = build_react_kb(uid)
            await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            await safe_cb_answer(cb, f"React Delay: {s['react_delay']}s", show_alert=False)
        elif sub_action == "emoji":
            # parts: pgc_react_emoji_{emoji}_{uid}
            if len(parts) >= 4:
                emoji = parts[3]
                s["react_emoji"] = emoji
                save_settings(uid, s)
                text = build_react_text(uid)
                kb = build_react_kb(uid)
                await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
                await safe_cb_answer(cb, f"Emoji set to: {emoji}", show_alert=False)
        return
    
    elif action == "sp":
        # Smart Purge sub-actions: toggle, limit, delay, mode, offset
        if len(parts) < 4:
            return
        sub_action = parts[2]
        
        if sub_action == "toggle":
            s["smart_purge"] = not s.get("smart_purge", False)
            save_settings(uid, s)
            text = build_smartpurge_text(uid)
            kb = build_smartpurge_kb(uid)
            await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        elif sub_action == "limit":
            direction = parts[3] if len(parts) > 3 else None
            if direction == "dec":
                s["purge_limit"] = max(1, s.get("purge_limit", 4) - 2)
            elif direction == "inc":
                s["purge_limit"] = s.get("purge_limit", 4) + 2
            save_settings(uid, s)
            text = build_smartpurge_text(uid)
            kb = build_smartpurge_kb(uid)
            await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        elif sub_action == "delay":
            direction = parts[3] if len(parts) > 3 else None
            if direction == "dec":
                s["purge_delay_msg"] = max(0.5, s.get("purge_delay_msg", 1.0) - 0.5)
            elif direction == "inc":
                s["purge_delay_msg"] = s.get("purge_delay_msg", 1.0) + 0.5
            save_settings(uid, s)
            text = build_smartpurge_text(uid)
            kb = build_smartpurge_kb(uid)
            await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        elif sub_action == "mode":
            mode_val = parts[3] if len(parts) > 3 else "oldest"
            s["purge_mode"] = mode_val
            save_settings(uid, s)
            text = build_smartpurge_text(uid)
            kb = build_smartpurge_kb(uid)
            await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        elif sub_action == "offset":
            direction = parts[3] if len(parts) > 3 else None
            if direction == "dec":
                s["purge_offset"] = max(0, s.get("purge_offset", 0) - 5)
            elif direction == "inc":
                s["purge_offset"] = s.get("purge_offset", 0) + 5
            save_settings(uid, s)
            text = build_smartpurge_text(uid)
            kb = build_smartpurge_kb(uid)
            await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)

    elif action == "sdtoggle":
        s["self_destruct"] = not s.get("self_destruct", False)
        save_settings(uid, s)
        text = build_dashboard_text(uid)
        kb = build_sd_submenu_kb(uid) # Return to SD SubMenu
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        await safe_cb_answer(cb, f"Self-Destruct: {'ON' if s['self_destruct'] else 'OFF'}", show_alert=False)
        return

    elif action == "sddelay":
        # parts: pgc_sddelay_dec/inc_uid
        if len(parts) < 4:
            return
        direction = parts[2]
        s["self_destruct_delay"] = s.get("self_destruct_delay", 30)
        if direction == "dec":
            s["self_destruct_delay"] = max(5, s["self_destruct_delay"] - 10)
        elif direction == "inc":
            s["self_destruct_delay"] = s["self_destruct_delay"] + 10
        save_settings(uid, s)
        text = build_dashboard_text(uid)
        kb = build_sd_submenu_kb(uid) # Return to SD SubMenu
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        await safe_cb_answer(cb, f"SD Delay: {s['self_destruct_delay']}s", show_alert=False)
        return

    elif action == "sdmenu":
        text = build_dashboard_text(uid)
        kb = build_sd_submenu_kb(uid)
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        await safe_cb_answer(cb, "Self-Destruct settings.", show_alert=False)
        return

    elif action == "sdtarget":
        cycle = {"gcast": "reply", "reply": "both", "both": "gcast"}
        s["sd_target"] = cycle.get(s.get("sd_target", "gcast"), "both")
        save_settings(uid, s)
        text = build_dashboard_text(uid)
        kb = build_sd_submenu_kb(uid)
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        target_labels = {"gcast": "GCast Only", "reply": "Reply Only", "both": "Both"}
        await safe_cb_answer(cb, f"Target: {target_labels.get(s['sd_target'], 'Unknown')}", show_alert=False)
        return

    elif action == "sdtrigger":
        cycle = {"after_gcast": "after_reply", "after_reply": "after_gcast"}
        s["sd_trigger"] = cycle.get(s.get("sd_trigger", "after_gcast"), "after_reply")
        save_settings(uid, s)
        text = build_dashboard_text(uid)
        kb = build_sd_submenu_kb(uid)
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        trigger_labels = {"after_gcast": "After GCast", "after_reply": "After Reply"}
        await safe_cb_answer(cb, f"Trigger: {trigger_labels.get(s['sd_trigger'], 'Unknown')}", show_alert=False)
        return

    # ========== AUTO-REPLY ACTIONS ==========

    elif action == "autoreply":
        s["auto_reply"] = not s.get("auto_reply", False)
        save_settings(uid, s)
        text = build_dashboard_text(uid)
        kb = build_dashboard_kb(uid)
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        await safe_cb_answer(cb, f"Auto-Reply: {'ON' if s['auto_reply'] else 'OFF'}", show_alert=False)
        return

    elif action == "reprandomtoggle":
        s["random_reply"] = not s.get("random_reply", True)
        save_settings(uid, s)
        text = build_reply_msglist_text(uid)
        kb = build_reply_msglist_kb(uid)
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        await safe_cb_answer(cb, f"Random Reply: {'ON' if s.get('random_reply', True) else 'OFF'}", show_alert=False)
        return

    elif action == "repdelaymenu":
        text = build_dashboard_text(uid)
        kb = build_reply_delay_submenu_kb(uid)
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        await safe_cb_answer(cb, "Reply delay settings.", show_alert=False)
        return

    elif action == "repdelay":
        # pgc_repdelay_dec/inc_uid
        if len(parts) < 4: return
        dir_ = parts[2]
        cur = s.get("reply_delay", 3)
        if dir_ == "dec": s["reply_delay"] = max(1, cur - 1)
        elif dir_ == "inc": s["reply_delay"] = cur + 1
        save_settings(uid, s)
        text = build_dashboard_text(uid)
        kb = build_reply_delay_submenu_kb(uid)
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        await safe_cb_answer(cb, f"Delay: {s['reply_delay']}s", show_alert=False)
        return

    elif action == "repdelayset":
        # pgc_repdelay_set_uid_VAL
        if len(parts) < 5: return
        try:
            val = int(parts[4])
            s["reply_delay"] = val
            save_settings(uid, s)
            text = build_dashboard_text(uid)
            kb = build_reply_delay_submenu_kb(uid)
            await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            await safe_cb_answer(cb, f"Delay set to {val}s", show_alert=False)
        except: pass
        return

    elif action == "repsetfixed":
        await safe_cb_answer(cb, "👆 Klik pada pesan di atas untuk menjadikannya pesan tetap (Fixed).", show_alert=True)
        return

    elif action == "repmsgmenu":
        # parts: pgc_repmsgmenu_uid[_page_N]
        page = 0
        if len(parts) >= 5 and parts[3] == "page":
            try: page = int(parts[4])
            except: page = 0
        text = build_reply_msglist_text(uid, page=page)
        kb = build_reply_msglist_kb(uid, page=page)
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        await safe_cb_answer(cb, f"Auto-Reply list - Page {page+1}", show_alert=False)
        return

    elif action in ["repmsgpreview", "repmsgdelconf", "repmsgdel", "repmsgsetfixed"]:
        # parts: pgc_repmsg{action}_{mtype}_{uid}_{idx}[_p{page}]
        if len(parts) < 5: return
        mtype = parts[2]
        try:
            o_idx = int(parts[4])
            page = 0
            if len(parts) >= 6 and parts[5].startswith("p"):
                try: page = int(parts[5][1:])
                except: page = 0
            
            target_list = s["reply_text_list"] if mtype == "text" else s["reply_media_list"]
            if o_idx < 0 or o_idx >= len(target_list):
                await safe_cb_answer(cb, "❌ Message not found.", show_alert=True)
                return

            if action == "repmsgpreview":
                item = target_list[o_idx]
                if mtype == "text":
                    content = item.get("content", "")
                    preview_text = f"<b>Preview Auto-Reply Text #{o_idx+1}</b>\n{'━' * 18}\n{html.escape(content)}"
                else:
                    subtype = item.get("type", "photo")
                    cap = item.get("caption", "")
                    preview_text = f"<b>Preview Auto-Reply Media #{o_idx+1}</b>\n{'━' * 18}\nType: <b>{subtype.upper()}</b>\nCaption: {html.escape(cap) or '<i>none</i>'}"
                
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🗑 Delete", callback_data=f"pgc_repmsgdelconf_{mtype}_{uid}_{o_idx}_p{page}", style=btn_style)],
                    [InlineKeyboardButton("🔙 Back", callback_data=f"pgc_repmsgmenu_{uid}_page_{page}", style=btn_style)]
                ])
                await safe_edit_message(cb, preview_text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)

            elif action == "repmsgdelconf":
                confirm_text = f"❓ <b>Hapus auto-reply {mtype} #{o_idx+1}?</b>"
                kb = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Ya, Hapus", callback_data=f"pgc_repmsgdel_{mtype}_{uid}_{o_idx}_p{page}", style=btn_style),
                        InlineKeyboardButton("❌ Batal", callback_data=f"pgc_repmsgmenu_{uid}_page_{page}", style=btn_style)
                    ]
                ])
                await safe_edit_message(cb, confirm_text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)

            elif action == "repmsgdel":
                target_list.pop(o_idx)
                if mtype == "text": s["reply_text_list"] = target_list
                else: s["reply_media_list"] = target_list
                if s.get("reply_fixed_message_index") is not None: s["reply_fixed_message_index"] = None
                save_settings(uid, s)
                await safe_cb_answer(cb, "✅ Balasan dihapus.", show_alert=True)
                # Refresh
                text = build_reply_msglist_text(uid, page=page)
                kb = build_reply_msglist_kb(uid, page=page)
                await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)

            elif action == "repmsgsetfixed":
                actual_idx = o_idx if mtype == "text" else len(s["reply_text_list"]) + o_idx
                s["random_reply"] = False
                s["reply_fixed_message_index"] = actual_idx
                save_settings(uid, s)
                await safe_cb_answer(cb, f"📌 Set fixed ke balasan #{actual_idx+1}", show_alert=False)
                # Refresh
                text = build_reply_msglist_text(uid, page=page)
                kb = build_reply_msglist_kb(uid, page=page)
                await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)

        except Exception as e:
            Altruix.log(f"Error in Auto-Reply msg action {action}: {e}", level=40, client=client)
            await safe_cb_answer(cb, "❌ Gagal memproses balasan.", show_alert=True)
        return

    elif action == "repmsgaddtext":
        # parts: pgc_repmsgaddtext_uid[_p{page}]
        page = 0
        if len(parts) >= 4 and parts[3].startswith("p"):
            try: page = int(parts[3][1:])
            except: page = 0
            
        chat_id = cb.message.chat.id if cb.message and cb.message.chat else uid
        msg_id = cb.message.id if cb.message else 0
        
        GCAST_REPLY_TEXT_INPUT_STATE[uid] = {"chat_id": chat_id, "msg_id": msg_id, "page": page, "action": "add"}
        log_msg = await send_log(f"📝 <b>Add Auto-Reply Text</b>\n<i>Return to Page {page+1} after adding</i>\n\nReply with your text.", client=None)
        
        if log_msg:
            await safe_cb_answer(cb, "📝 Silahkan balas (reply) pesan di LOG/Bot dengan Teks balasan baru.", show_alert=True)
        else:
            await safe_cb_answer(cb, "❌ Gagal mengirim perintah input. Silahkan coba lagi.", show_alert=True)
        return

    elif action == "repmsgaddmedia":
        # parts: pgc_repmsgaddmedia_uid[_p{page}]
        page = 0
        if len(parts) >= 4 and parts[3].startswith("p"):
            try: page = int(parts[3][1:])
            except: page = 0
            
        chat_id = cb.message.chat.id if cb.message and cb.message.chat else uid
        msg_id = cb.message.id if cb.message else 0
        
        # Re-use media state with a flag or separate dic? I'll use separate for clarity if I can.
        # But I'll modify pgc_input_handler accordingly.
        GCAST_REPLY_MEDIA_INPUT_STATE[uid] = {"chat_id": chat_id, "msg_id": msg_id, "page": page, "action": "add"}
        log_msg = await send_log(f"🎬 <b>Add Auto-Reply Media</b>\n<i>Return to Page {page+1} after adding</i>\n\nReply with your media.", client=None)
        
        if log_msg:
            await safe_cb_answer(cb, "🎬 Silahkan balas (reply) pesan di LOG/Bot dengan Media baru.", show_alert=True)
        else:
            await safe_cb_answer(cb, "❌ Gagal mengirim perintah input. Silahkan coba lagi.", show_alert=True)
        return

    elif action == "repeditedit":
        # pgc_repeditedit_{type}_{uid}_{idx}_p{page}
        if len(parts) < 6: return
        mtype = parts[2]
        try:
            idx = int(parts[4])
            page = int(parts[5][1:]) if parts[5].startswith("p") else 0
        except: return
        
        msg_id = cb.message.id if cb.message else None
        if mtype == "text":
            GCAST_REPLY_TEXT_INPUT_STATE[uid] = {"action": "edit", "idx": idx, "msg_id": msg_id, "page": page}
            prompt = "Silahkan balas (reply) pesan ini dengan Teks balasan baru."
        else:
            GCAST_REPLY_MEDIA_INPUT_STATE[uid] = {"action": "edit", "idx": idx, "msg_id": msg_id, "page": page}
            prompt = "Silahkan balas (reply) pesan ini dengan Caption balasan baru."
            
        log_msg = await send_log(
            f"✏️ <b>Edit Auto-Reply {mtype.title()} #{idx+1}</b>\n"
            f"{'━' * 18}\n{prompt}",
            client=None
        )
        
        if log_msg:
            await safe_cb_answer(cb, f"✏️ {prompt}", show_alert=True)
        else:
            await safe_cb_answer(cb, "❌ Gagal mengirim perintah input. Silahkan coba lagi.", show_alert=True)
        return

    elif action == "repmsgclearconf":
        confirm_text = "⚠️ <b>Hapus semua balasan otomatis?</b>"
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Ya, Hapus Semua", callback_data=f"pgc_repmsgclear_{uid}", style=btn_style),
                InlineKeyboardButton("❌ Batal", callback_data=f"pgc_repmsgmenu_{uid}", style=btn_style)
            ]
        ])
        await safe_edit_message(cb, confirm_text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        return

    elif action == "repmsgclear":
        s["reply_text_list"] = []
        s["reply_media_list"] = []
        s["reply_fixed_message_index"] = None
        save_settings(uid, s)
        text = build_reply_msglist_text(uid)
        kb = build_reply_msglist_kb(uid)
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        await safe_cb_answer(cb, "Reply list cleared.", show_alert=True)
        return

    elif action == "hidemenu":
        s["menu_mode"] = "hide"
        save_settings(uid, s)
        text = build_dashboard_text(uid)
        kb = build_dashboard_kb(uid)
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        await safe_cb_answer(cb, "Menu hidden.", show_alert=False)
        return

    elif action == "showmenu":
        s["menu_mode"] = "full"
        save_settings(uid, s)
        text = build_dashboard_text(uid)
        kb = build_dashboard_kb(uid)
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        await safe_cb_answer(cb, "Menu shown.", show_alert=False)
        return

    elif action == "refresh":
        text = build_dashboard_text(uid)
        kb = build_dashboard_kb(uid)
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        await safe_cb_answer(cb, "Refreshed!", show_alert=False)
        return
    
    elif action == "info":
        # Show info sub-menu with button documentation (paginated)
        # Parse page number: pgc_info_uid or pgc_info_uid_page_N
        page = 0
        if len(parts) >= 5 and parts[3] == "page":
            try:
                page = int(parts[4])
            except (ValueError, IndexError):
                page = 0
        
        text = build_info_text(page)
        
        # Build keyboard with pagination
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("◀️ Prev", callback_data=f"pgc_info_{uid}_page_{page-1}", style=btn_style))
        if page < 3:  # ✅ FIX: We have 4 pages (0, 1, 2, 3)
            nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"pgc_info_{uid}_page_{page+1}", style=btn_style))
        
        kb_rows = []
        if nav_buttons:
            kb_rows.append(nav_buttons)
        kb_rows.append([InlineKeyboardButton("📋 Show CMD", callback_data=f"pgc_showcmd_{uid}", style=btn_style)])
        kb_rows.append([InlineKeyboardButton("⬅️ Back", callback_data=f"pgc_backmain_{uid}", style=btn_style)])
        
        kb = InlineKeyboardMarkup(kb_rows)
        success = await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        if success:
            await safe_cb_answer(cb, f"Info menu (Page {page+1}/4).", show_alert=False)
        return
    
    elif action == "showcmd":
        # Show command list
        text = build_showcmd_text()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data=f"pgc_info_{uid}", style=btn_style)],
        ])
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        await safe_cb_answer(cb, "Command list.", show_alert=False)
        return
    
    elif action == "help":
        # Deprecated - redirect to info
        text = build_info_text()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(" Show CMD", callback_data=f"pgc_showcmd_{uid}", style=btn_style)],
            [InlineKeyboardButton("⬅️ Back", callback_data=f"pgc_backmain_{uid}", style=btn_style)],
        ])
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        await safe_cb_answer(cb, "Info menu.", show_alert=False)
        return
    
    # ========== START / STOP / PAUSE / RESUME ==========
    
    elif action == "startconf":
        # Show confirmation
        if uid in GCAST_TASKS and GCAST_TASKS[uid].get("running"):
            await safe_cb_answer(cb, "⚠️ A broadcast is already running!", show_alert=True)
            return
        if not s["text_list"] and not s.get("media_list"):
            await safe_cb_answer(cb, "❌ Message list is empty! Add texts or media first.", show_alert=True)
            return
        
        # Count total messages
        total_messages = len(s.get('text_list', [])) + len(s.get('media_list', []))
        
        # Smart Purge status
        smart_purge_text = ""
        if s.get('smart_purge', False):
            smart_purge_text = (
                f"\n🧹 Smart Purge: ON\n"
                f"  • Limit: {s.get('purge_limit', 4)} msg\n"
                f"  • Mode: {s.get('purge_mode', 'oldest').title()}\n"
                f"  • Delay: {s.get('purge_delay_msg', 1.0)}s/msg"
            )
        else:
            smart_purge_text = "\n🧹 Smart Purge: OFF"
        
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Yes, Start!", callback_data=f"pgc_startyes_{uid}", style=btn_style),
                InlineKeyboardButton("❌ Cancel", callback_data=f"pgc_backmain_{uid}", style=btn_style),
            ]
        ])
        text = (
            f"<blockquote expandable>⚠️ <b>Confirm Start GCast?</b>\n"
            f"{'━' * 18}\n"
            f"Chat Filter: <b>{_filter_label(s['chat_filter'])}</b>\n"
            f"Admin Filter: <b>{_filter_label(s['admin_filter'])}</b>\n"
            f"Messages: <b>{total_messages} items</b> ({len(s.get('text_list', []))} text, {len(s.get('media_list', []))} media)\n"
            f"Delay: <b>{s['delay_per_chat']}s/chat</b>\n"
            f"Random: <b>{'ON' if s['random_text'] else 'OFF'}</b>\n"
            f"Recurring: <b>{'ON' if s['recurring'] else 'OFF'}</b>"
            f"{smart_purge_text}</blockquote>"
        )
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        await safe_cb_answer(cb, "Confirm to start.", show_alert=False)
        return
    
    elif action == "startyes":
        # Actually start the broadcast
        if uid in GCAST_TASKS and GCAST_TASKS[uid].get("running"):
            await safe_cb_answer(cb, "⚠️ Already running!", show_alert=True)
            return
        # Find the userbot client for this user
        broadcast_client = None
        for cl in Altruix.clients:
            if hasattr(cl, 'me') and cl.me and cl.me.id == uid:
                broadcast_client = cl
                break
                
        if not broadcast_client:
            await safe_cb_answer(cb, "❌ Session Client Userbot not found or not available.", show_alert=True)
            return
        
        # Start broadcast in background
        task = asyncio.create_task(broadcast_loop(broadcast_client, uid))
        
        await safe_cb_answer(cb, "🟢 Broadcast started!", show_alert=True)
        # Refresh dashboard
        await asyncio.sleep(1)
        text = build_dashboard_text(uid)
        kb = build_dashboard_kb(uid)
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        return
    
    elif action == "stop":
        task = GCAST_TASKS.get(uid)
        if not task or not task.get("running"):
            await safe_cb_answer(cb, "⚫ No active broadcast.", show_alert=True)
            return
        task["running"] = False
        task["pause_event"].set()  # Unpause so loop can exit
        atask = task.get("asyncio_task")
        if atask and not atask.done():
            atask.cancel()
        await safe_cb_answer(cb, "🔴 Broadcast stopped.", show_alert=True)
        await send_log(f"🔴 <b>GCast Stopped</b> <code>{task.get('task_id', '?')}</code> by user.", client=task.get("client"))
        # Refresh
        await asyncio.sleep(0.5)
        text = build_dashboard_text(uid)
        kb = build_dashboard_kb(uid)
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        return
    
    elif action == "pause":
        task = GCAST_TASKS.get(uid)
        if not task or not task.get("running"):
            await safe_cb_answer(cb, "⚫ No active broadcast.", show_alert=True)
            return
        task["pause_event"].clear()
        await safe_cb_answer(cb, "⏸ Broadcast paused.", show_alert=True)
        await send_log(f"⏸ <b>GCast Paused</b> <code>{task.get('task_id', '?')}</code>", client=task.get("client"))
        text = build_dashboard_text(uid)
        kb = build_dashboard_kb(uid)
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        return
    
    elif action == "resume":
        task = GCAST_TASKS.get(uid)
        if not task or not task.get("running"):
            await safe_cb_answer(cb, "⚫ No active broadcast.", show_alert=True)
            return
        task["pause_event"].set()
        await safe_cb_answer(cb, "▶️ Broadcast resumed.", show_alert=True)
        await send_log(f"▶️ <b>GCast Resumed</b> <code>{task.get('task_id', '?')}</code>", client=task.get("client"))
        text = build_dashboard_text(uid)
        kb = build_dashboard_kb(uid)
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        return
    
    # ========== MESSAGE LIST SUB-MENU ==========
    
    elif action == "msgmenu":
        # parts: pgc_msgmenu_uid or pgc_msgmenu_uid_page_N
        page = 0
        if len(parts) >= 5 and parts[3] == "page":
            try:
                page = int(parts[4])
            except: page = 0
            
        text = build_msglist_text(uid, page=page)
        kb = build_msglist_kb(uid, page=page)
        success = await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        if success:
            await safe_cb_answer(cb, f"Message list - Page {page+1}", show_alert=False)
        return
    
    elif action == "addtext":
        # parts: pgc_addtext_uid[_p{page}]
        page = 0
        if len(parts) >= 3:
            # Check if last part is page
            if parts[-1].startswith("p"):
                try: page = int(parts[-1][1:])
                except: page = 0
        
        # Set state to wait for user text input
        msg_id = cb.message.id if cb.message else None
        GCAST_TEXT_INPUT_STATE[uid] = {"action": "add", "msg_id": msg_id, "page": page}
        
        # Send log message for user to reply to
        log_msg = await send_log(
            f"📝 <b>Add Text to GCast</b>\n"
            f"<i>Return to Page {page+1} after adding</i>\n\n"
            f"Reply to this message with the text you want to add.\n\n"
            f"<b>Supported Formats:</b>\n"
            f"• HTML: <code>&lt;b&gt;Bold&lt;/b&gt;</code>, <code>&lt;i&gt;Italic&lt;/i&gt;</code>\n"
            f"• Markdown: <code>**Bold**</code>, <code>__Italic__</code>\n\n"
            f"<b>Format Detection:</b>\n"
            f"• Starts with <code>&lt;</code> → HTML\n"
            f"• Contains <code>**</code> or <code>__</code> → Markdown\n"
            f"• Otherwise → Plain text",
            client=None
        )
        
        if log_msg:
            await safe_cb_answer(cb, "📝 Silahkan balas (reply) pesan di LOG/Bot dengan Teks baru.", show_alert=True)
        else:
            await safe_cb_answer(cb, "❌ Gagal mengirim perintah input. Silahkan coba lagi.", show_alert=True)
        return

    elif action == "msgeditedit":
        # pgc_msgeditedit_{type}_{uid}_{idx}_p{page}
        if len(parts) < 6: return
        mtype = parts[2]
        try:
            idx = int(parts[4])
            page = int(parts[5][1:]) if parts[5].startswith("p") else 0
        except: return
        
        msg_id = cb.message.id if cb.message else None
        if mtype == "text":
            GCAST_TEXT_INPUT_STATE[uid] = {"action": "edit", "idx": idx, "msg_id": msg_id, "page": page}
            prompt = "Silahkan balas (reply) pesan ini dengan Teks baru."
        else:
            GCAST_MEDIA_INPUT_STATE[uid] = {"action": "edit", "idx": idx, "msg_id": msg_id, "page": page}
            prompt = "Silahkan balas (reply) pesan ini dengan Caption baru."
            
        log_msg = await send_log(
            f"✏️ <b>Edit GCast {mtype.title()} #{idx+1}</b>\n"
            f"{'━' * 18}\n{prompt}",
            client=None
        )
        
        if log_msg:
            await safe_cb_answer(cb, f"✏️ {prompt}", show_alert=True)
        else:
            await safe_cb_answer(cb, "❌ Gagal mengirim perintah input. Silahkan coba lagi.", show_alert=True)
        return
    
    # Combined handlers for GCast message actions (preview, del, setfixed)
    elif action in ["msgpreview", "msgdelconf", "msgdel", "msgsetfixed"]:
        # Parts: pgc_{action}_{type}_{uid}_{idx}[_p{page}]
        if len(parts) < 5: return
        mtype = parts[2]
        try:
            o_idx = int(parts[4])
            page = 0
            # Check for page suffix (usually parts[5] like 'p1')
            if len(parts) >= 6 and parts[5].startswith("p"):
                try: page = int(parts[5][1:])
                except: page = 0
            
            target_list = s["text_list"] if mtype == "text" else s["media_list"]
            if o_idx < 0 or o_idx >= len(target_list):
                await safe_cb_answer(cb, "❌ Message not found.", show_alert=True)
                return

            if action == "msgpreview":
                item = target_list[o_idx]
                if mtype == "text":
                    content = item.get("content", "") if isinstance(item, dict) else str(item)
                    pm = item.get("parse_mode", "html") if isinstance(item, dict) else "html"
                    preview_text = (
                        f"<b>Preview GCast Text #{o_idx+1}</b>\n"
                        f"{'━' * 18}\n"
                        f"{html.escape(content)}\n"
                        f"{'━' * 18}\n"
                        f"Format: <code>{pm.upper()}</code>"
                    )
                else:
                    subtype = item.get("type", "photo")
                    cap = item.get("caption", "")
                    preview_text = (
                        f"<b>Preview GCast Media #{o_idx+1}</b>\n"
                        f"{'━' * 18}\n"
                        f"Type: <b>{subtype.upper()}</b>\n"
                        f"Caption: {html.escape(cap) if cap else '<i>none</i>'}"
                    )
                
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🗑 Delete", callback_data=f"pgc_msgdelconf_{mtype}_{uid}_{o_idx}_p{page}", style=btn_style)],
                    [InlineKeyboardButton("🔙 Back", callback_data=f"pgc_msgmenu_{uid}_page_{page}", style=btn_style)]
                ])
                await safe_edit_message(cb, preview_text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
                await safe_cb_answer(cb, "Previewing message.", show_alert=False)

            elif action == "msgdelconf":
                confirm_text = f"❓ <b>Hapus pesan {mtype} #{o_idx+1}?</b>"
                kb = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Ya, Hapus", callback_data=f"pgc_msgdel_{mtype}_{uid}_{o_idx}_p{page}", style=btn_style),
                        InlineKeyboardButton("❌ Batal", callback_data=f"pgc_msgmenu_{uid}_page_{page}", style=btn_style)
                    ]
                ])
                await safe_edit_message(cb, confirm_text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)

            elif action == "msgdel":
                target_list.pop(o_idx)
                if mtype == "text": s["text_list"] = target_list
                else: s["media_list"] = target_list
                
                # If deleted fixed message, reset it
                if not s["random_text"] and s.get("fixed_message_index") is not None:
                    s["fixed_message_index"] = None
                
                save_settings(uid, s)
                await safe_cb_answer(cb, "✅ Pesan dihapus.", show_alert=True)
                
                # Refresh list (return to same page)
                text = build_msglist_text(uid, page=page)
                kb = build_msglist_kb(uid, page=page)
                await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)

            elif action == "msgsetfixed":
                # Calculate global index
                actual_fixed_idx = o_idx if mtype == "text" else len(s["text_list"]) + o_idx
                s["random_text"] = False
                s["fixed_message_index"] = actual_fixed_idx
                save_settings(uid, s)
                await safe_cb_answer(cb, f"📌 Set fixed ke pesan #{actual_fixed_idx+1}", show_alert=False)
                
                # Refresh list
                text = build_msglist_text(uid, page=page)
                kb = build_msglist_kb(uid, page=page)
                await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)

        except Exception as e:
            Altruix.log(f"Error in GCast msg action {action}: {e}", level=40, client=client)
            await safe_cb_answer(cb, "❌ Gagal memproses pesan.", show_alert=True)
        return
    
    elif action == "addmedia":
        # parts: pgc_addmedia_uid[_p{page}]
        page = 0
        if len(parts) >= 3:
            if parts[-1].startswith("p"):
                try: page = int(parts[-1][1:])
                except: page = 0
                
        # Send log message for user to reply to
        msg_id = cb.message.id if cb.message else None
        GCAST_MEDIA_INPUT_STATE[uid] = {"action": "add", "msg_id": msg_id, "page": page}
        
        log_msg = await send_log(
            f"🎬 <b>Add Media to GCast</b>\n"
            f"<i>Return to Page {page+1} after adding</i>\n\n"
            f"Reply to this message with the media you want to add.\n"
            f"Supported: Photo, Video, Animation, Audio, etc.",
            client=None
        )
        
        if log_msg:
            await safe_cb_answer(cb, "🎬 Silahkan balas (reply) pesan di LOG/Bot dengan Media baru.", show_alert=True)
        else:
            await safe_cb_answer(cb, "❌ Gagal mengirim perintah input. Silahkan coba lagi.", show_alert=True)
        return
    
    elif action == "msgclearconf":
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Yes, Clear All", callback_data=f"pgc_msgclearyes_{uid}", style=btn_style),
                InlineKeyboardButton("❌ Cancel", callback_data=f"pgc_msgmenu_{uid}", style=btn_style),
            ]
        ])
        await safe_edit_message(cb, "⚠️ <b>Clear ALL messages (text + media)?</b>\nThis cannot be undone.", reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        await safe_cb_answer(cb, "Confirm clear.", show_alert=False)
        return
    
    elif action == "msgclearyes":
        s["text_list"] = []
        s["media_list"] = []
        save_settings(uid, s)
        await safe_cb_answer(cb, "🗑 All messages cleared.", show_alert=True)
        await send_log("🗑 <b>GCast Message List Cleared</b>", client=None)
        text = build_msglist_text(uid)
        kb = build_msglist_kb(uid)
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        return
    
    # ========== OLD TEXT MENU (for backward compatibility) ==========
    
    elif action == "textmenu":
        # Redirect to new message menu
        text = build_msglist_text(uid)
        kb = build_msglist_kb(uid)
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        await safe_cb_answer(cb, "Message list menu.", show_alert=False)
        return
    
    elif action == "textadd":
        # Redirect to addtext
        GCAST_TEXT_INPUT_STATE[uid] = {"action": "add", "msg_id": cb.message.id}
        await safe_cb_answer(cb, "📝 Send your broadcast text now.\nReply to any message in LOG chat.", show_alert=True)
        await send_log(
            f"📝 <b>Add Text to GCast</b>\n"
            f"Reply to this message with the text you want to add to the broadcast list.",
            client=None
        )
        return
    
    elif action == "textdel":
        # pgc_textdel_uid_index
        if len(parts) < 4:
            return
        try:
            idx = int(parts[3])
        except (ValueError, IndexError):
            return
        s = get_settings(uid)
        if 0 <= idx < len(s["text_list"]):
            removed = s["text_list"].pop(idx)
            save_settings(uid, s)
            content = removed.get("content", "") if isinstance(removed, dict) else str(removed)
            await safe_cb_answer(cb, f"🗑 Removed text #{idx+1}.", show_alert=True)
            await send_log(f"🗑 <b>GCast Text Removed</b> #{idx+1}: {html.escape(content[:50])}", client=None)
        else:
            await safe_cb_answer(cb, "Invalid index.", show_alert=True)
        text = build_msglist_text(uid)
        kb = build_msglist_kb(uid)
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        return
    
    elif action == "textclearconf":
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Yes, Clear All", callback_data=f"pgc_textclearyes_{uid}", style=btn_style),
                InlineKeyboardButton("❌ Cancel", callback_data=f"pgc_textmenu_{uid}", style=btn_style),
            ]
        ])
        await safe_edit_message(cb, "⚠️ <b>Clear ALL texts?</b>\nThis cannot be undone.", reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        await safe_cb_answer(cb, "Confirm clear.", show_alert=False)
        return
    
    elif action == "textclearyes":
        s["text_list"] = []
        save_settings(uid, s)
        await safe_cb_answer(cb, "🗑 All texts cleared.", show_alert=True)
        await send_log("🗑 <b>GCast Text List Cleared</b>", client=None)
        text = build_msglist_text(uid)
        kb = build_msglist_kb(uid)
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        return
    
    # ========== BLACKLIST SUB-MENU ==========
    
    elif action == "blmenu":
        # Parse page number: pgc_blmenu_uid or pgc_blmenu_uid_page_N
        page = 0
        if len(parts) >= 5 and parts[3] == "page":
            try:
                page = int(parts[4])
            except (ValueError, IndexError):
                page = 0
        
        text = build_bl_text(uid, page)
        kb = build_bl_kb(uid, page)
        success = await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        if success:
            await safe_cb_answer(cb, "Blacklist menu.", show_alert=False)
        return
    
    elif action == "bladd":
        # Store state and send prompt message
        msg_id = cb.message.id if cb.message else None
        GCAST_BL_INPUT_STATE[uid] = {"action": "add", "msg_id": msg_id}
        
        # Send log message for user to reply to
        log_msg = await send_log(
            f"🚫 <b>Add to GCast Blacklist</b>\n\n"
            f"Reply to this message with:\n"
            f"• Chat ID (e.g., <code>-100123456789</code>)\n"
            f"• Username (e.g., <code>@groupname</code>)\n\n"
            f"<i>Or use command: <code>.gcastbl &lt;chat_id&gt;</code></i>",
            client=None
        )
        
        if log_msg:
            await safe_cb_answer(cb, "📝 Reply to the message in LOG chat to add chat to blacklist.", show_alert=True)
        else:
            await safe_cb_answer(cb, "❌ Failed to send prompt. Use command: .gcastbl <chat_id>", show_alert=True)
        return
    
    elif action == "bldel":
        # pgc_bldel_uid_index
        if len(parts) < 4:
            return
        try:
            idx = int(parts[3])
        except (ValueError, IndexError):
            return
        s = get_settings(uid)
        if 0 <= idx < len(s["blacklist"]):
            removed = s["blacklist"].pop(idx)
            save_settings(uid, s)
            await safe_cb_answer(cb, f"🗑 Removed chat {removed} from blacklist.", show_alert=True)
            await send_log(f"🗑 <b>GCast Blacklist Removed</b> Chat: {removed}", client=None)
        else:
            await safe_cb_answer(cb, "Invalid index.", show_alert=True)
        
        # Calculate which page to show after deletion
        items_per_page = 10
        total_items = len(s["blacklist"])
        if total_items > 0:
            page = min(idx // items_per_page, (total_items - 1) // items_per_page)
        else:
            page = 0
        
        text = build_bl_text(uid, page)
        kb = build_bl_kb(uid, page)
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        return
    
    elif action == "blclearconf":
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Yes, Clear All", callback_data=f"pgc_blclearyes_{uid}", style=btn_style),
                InlineKeyboardButton("❌ Cancel", callback_data=f"pgc_blmenu_{uid}", style=btn_style),
            ]
        ])
        await safe_edit_message(cb, "⚠️ <b>Clear ALL blacklist?</b>\nThis cannot be undone.", reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        await safe_cb_answer(cb, "Confirm clear.", show_alert=False)
        return
    
    elif action == "blclearyes":
        s["blacklist"] = []
        save_settings(uid, s)
        await safe_cb_answer(cb, "🗑 Blacklist cleared.", show_alert=True)
        await send_log("🗑 <b>GCast Blacklist Cleared</b>", client=None)
        text = build_bl_text(uid)
        kb = build_bl_kb(uid)
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        return
    
    elif action == "listchats":
        # Show list of target chats (scan dialogs) with pagination
        # Parse page number: pgc_listchats_uid or pgc_listchats_uid_page_N
        page = 0
        if len(parts) >= 5 and parts[3] == "page":
            try:
                page = int(parts[4])
            except (ValueError, IndexError):
                page = 0
        
        await safe_cb_answer(cb, "🔍 Scanning target chats...", show_alert=False)
        
        # Find the userbot client for this user
        target_client = None
        for cl in Altruix.clients:
            if hasattr(cl, 'me') and cl.me and cl.me.id == uid:
                target_client = cl
                break
        
        if not target_client:
            await safe_cb_answer(cb, "❌ No userbot client found.", show_alert=True)
            return
        
        # Get target chats
        targets = await get_target_chats(target_client, s)
        
        if not targets:
            text = (
                f"📋 <b>Target Chats</b>\n"
                f"{'━' * 18}\n"
                f"<i>No target chats found.</i>\n\n"
                f"Current filters:\n"
                f"• Chat Filter: {_filter_label(s['chat_filter'])}\n"
                f"• Admin Filter: {_filter_label(s['admin_filter'])}\n"
                f"• Blacklist: {len(s['blacklist'])} chats"
            )
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data=f"pgc_backmain_{uid}", style=btn_style)],
            ])
        else:
            # Pagination: 10 items per page
            items_per_page = 10
            total_pages = (len(targets) + items_per_page - 1) // items_per_page
            
            # Bounds check
            if page < 0:
                page = 0
            elif page >= total_pages:
                page = total_pages - 1
            
            start_idx = page * items_per_page
            end_idx = min(start_idx + items_per_page, len(targets))
            page_targets = targets[start_idx:end_idx]
            
            # Build chat list for current page
            chat_list = []
            for i, target in enumerate(page_targets, start=start_idx + 1):
                cid = target["chat_id"]
                title = target["group_title"]
                chat_list.append(f"{i}. {html.escape(title[:40])} (<code>{cid}</code>)")
            
            text = (
                f"📋 <b>Target Chats</b>\n"
                f"<i>Page {page+1}/{total_pages}</i>\n"
                f"{'━' * 18}\n"
                f"Total: <b>{len(targets)}</b> chats\n"
                f"Blacklist: <b>{len(s['blacklist'])}</b> chats excluded\n\n"
                f"<b>Filters:</b>\n"
                f"• Chat: {_filter_label(s['chat_filter'])}\n"
                f"• Admin: {_filter_label(s['admin_filter'])}\n\n"
                + "\n".join(chat_list)
            )
            
            # Build keyboard with pagination
            nav_buttons = []
            if page > 0:
                nav_buttons.append(InlineKeyboardButton("◀️ Prev", callback_data=f"pgc_listchats_{uid}_page_{page-1}", style=btn_style))
            if page < total_pages - 1:
                nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"pgc_listchats_{uid}_page_{page+1}", style=btn_style))
            
            kb_rows = []
            if nav_buttons:
                kb_rows.append(nav_buttons)
            kb_rows.append([InlineKeyboardButton("⬅️ Back", callback_data=f"pgc_backmain_{uid}", style=btn_style)])
            kb = InlineKeyboardMarkup(kb_rows)
        
        await safe_edit_message(cb, text, reply_markup=kb, disable_web_page_preview=True, parse_mode=enums.ParseMode.HTML)
        return
    
    else:
        await safe_cb_answer(cb, f"Unknown action: {action}", show_alert=True)


# ==================== BOT MESSAGE HANDLER: Text/Media/BL Input ====================

@Altruix.bot.on_message(filters.chat(LOG_CHAT_ID) & filters.incoming & filters.reply)
@log_errors
async def pgc_input_handler(c: Client, m: PyroMessage):
    """
    Catches user replies in LOG chat for:
    - Adding texts to the text list (with format detection)
    - Adding media to the media list
    - Adding chats to the blacklist
    Manual auth check to prevent noise for unauthorized users.
    """
    if not m.reply_to_message:
        return
    
    # ✅ Auth Check: Only Owner/Sudo can interact with Gcast setup
    from Main.utils.access_control import is_authorized_user
    is_auth = is_authorized_user(m.from_user.id, Altruix.config.OWNER_USERS_ID, Altruix.config.SUDO_USERS_ID)
    
    # We only care if the user is in an active input state OR if they are unauthorized but trying to trigger something.
    # To prevent noise, unauthorized users who just "talk" (reply) in the log group should be SILENTLY ignored.
    user_in_state = (
        m.from_user.id in GCAST_TEXT_INPUT_STATE or 
        m.from_user.id in GCAST_MEDIA_INPUT_STATE or 
        m.from_user.id in GCAST_BL_INPUT_STATE or
        m.from_user.id in GCAST_REPLY_TEXT_INPUT_STATE or
        m.from_user.id in GCAST_REPLY_MEDIA_INPUT_STATE
    )
    
    if not is_auth:
        if user_in_state:
            # If they are in state but somehow no longer auth (revoked sudo?), tell them.
            await m.reply(Altruix.get_string("ACCESS_DENIED"))
        return # SILENT for everyone else

    # Check Auto-Reply text input state
    for uid, state in list(GCAST_REPLY_TEXT_INPUT_STATE.items()):
        if m.from_user.id == uid and m.text:
            new_text = m.text.strip()
            if not new_text:
                await m.reply("❌ Text cannot be empty.")
                return
            
            # Auto-detect format
            parse_mode = "none"
            if new_text.startswith("<"):
                parse_mode = "html"
            elif "**" in new_text or "__" in new_text or "`" in new_text:
                parse_mode = "markdown"
            
            s = get_settings(uid)
            if "reply_text_list" not in s:
                s["reply_text_list"] = []
                
            s["reply_text_list"].append({
                "content": new_text,
                "parse_mode": parse_mode
            })
            save_settings(uid, s)
            GCAST_REPLY_TEXT_INPUT_STATE.pop(uid, None)
            
            page = state.get("page", 0)
            mode_label = {"html": "HTML", "markdown": "Markdown", "none": "Plain Text"}.get(parse_mode, "Plain")
            await m.reply(
                f"✅ <b>Auto-Reply Added</b>\n"
                f"Format: <b>{mode_label}</b>\n"
                f"<i>Added to Page {page+1}</i>\n"
                f"Total replies: {len(s['reply_text_list']) + len(s.get('reply_media_list', []))}\n"
                f"Preview: {html.escape(new_text[:80])}"
            )
            return
        
        elif m.from_user.id == uid and state.get("action") == "edit" and m.text:
            idx = state["idx"]
            new_text = m.text.strip()
            s = get_settings(uid)
            if idx < len(s.get("reply_text_list", [])):
                s["reply_text_list"][idx]["content"] = new_text
                save_settings(uid, s)
                GCAST_REPLY_TEXT_INPUT_STATE.pop(uid, None)
                await m.reply(f"✅ <b>Auto-Reply Text #{idx+1} Updated!</b>")
            return
    
    # Check Auto-Reply media input state
    for uid, state in list(GCAST_REPLY_MEDIA_INPUT_STATE.items()):
        if m.from_user.id == uid:
            media_type = None
            file_id = None
            caption = m.caption or ""
            
            if m.photo:
                media_type = "photo"; file_id = m.photo.file_id
            elif m.video:
                media_type = "video"; file_id = m.video.file_id
            elif m.audio:
                media_type = "audio"; file_id = m.audio.file_id
            elif m.voice:
                media_type = "voice"; file_id = m.voice.file_id
            elif m.document:
                media_type = "document"; file_id = m.document.file_id
            elif m.sticker:
                media_type = "sticker"; file_id = m.sticker.file_id
            elif m.animation:
                media_type = "animation"; file_id = m.animation.file_id
            elif m.video_note:
                media_type = "video_note"; file_id = m.video_note.file_id
            
            if not media_type:
                await m.reply("❌ No media found.")
                return
            
            caption_parse_mode = "none"
            if caption:
                if caption.startswith("<"): caption_parse_mode = "html"
                elif "**" in caption or "__" in caption: caption_parse_mode = "markdown"

            s = get_settings(uid)
            if "reply_media_list" not in s: s["reply_media_list"] = []
            s["reply_media_list"].append({
                "type": media_type,
                "file_id": file_id,
                "caption": caption,
                "parse_mode": caption_parse_mode
            })
            save_settings(uid, s)
            GCAST_REPLY_MEDIA_INPUT_STATE.pop(uid, None)
            
            page = state.get("page", 0)
            await m.reply(
                f"✅ <b>Auto-Reply Media Added</b>\n"
                f"Type: <b>{media_type.upper()}</b>\n"
                f"<i>Added to Page {page+1}</i>\n"
                f"Total replies: {len(s.get('reply_text_list', [])) + len(s['reply_media_list'])}\n"
                f"Caption: {html.escape(caption[:50]) or '<i>none</i>'}"
            )
            return
        
        elif m.from_user.id == uid and state.get("action") == "edit":
            idx = state["idx"]
            cap = m.caption or ""
            s = get_settings(uid)
            if idx < len(s.get("reply_media_list", [])):
                s["reply_media_list"][idx]["caption"] = cap
                save_settings(uid, s)
                GCAST_REPLY_MEDIA_INPUT_STATE.pop(uid, None)
                await m.reply(f"✅ <b>Auto-Reply Media #{idx+1} Caption Updated!</b>")
            return
    
    # Check text input state
    for uid, state in list(GCAST_TEXT_INPUT_STATE.items()):
        if state["action"] == "add" and m.text:
            new_text = m.text.strip()
            if not new_text:
                await m.reply("❌ Text cannot be empty.")
                return
            
            # Auto-detect format
            parse_mode = "none"
            if new_text.startswith("<"):
                parse_mode = "html"
            elif "**" in new_text or "__" in new_text or "`" in new_text:
                parse_mode = "markdown"
            
            s = get_settings(uid)
            s["text_list"].append({
                "content": new_text,
                "parse_mode": parse_mode
            })
            save_settings(uid, s)
            GCAST_TEXT_INPUT_STATE.pop(uid, None)
            
            mode_label = {"html": "HTML", "markdown": "Markdown", "none": "Plain Text"}.get(parse_mode, "Plain")
            await m.reply(
                f"✅ <b>Text Added to GCast</b>\n"
                f"Format: <b>{mode_label}</b>\n"
                f"Total texts: {len(s['text_list'])}\n"
                f"Preview: {html.escape(new_text[:80])}"
            )
            return

        elif m.from_user.id == uid and state.get("action") == "edit" and m.text:
            idx = state["idx"]
            new_text = m.text.strip()
            s = get_settings(uid)
            if idx < len(s.get("text_list", [])):
                s["text_list"][idx]["content"] = new_text
                save_settings(uid, s)
                GCAST_TEXT_INPUT_STATE.pop(uid, None)
                await m.reply(f"✅ <b>GCast Text #{idx+1} Updated!</b>")
            return
    
    # Check media input state
    for uid, state in list(GCAST_MEDIA_INPUT_STATE.items()):
        if state["action"] == "add":
            media_data = None
            media_type = None
            file_id = None
            caption = m.caption or ""
            
            # Detect media type and extract file_id
            if m.photo:
                media_type = "photo"
                file_id = m.photo.file_id
            elif m.video:
                media_type = "video"
                file_id = m.video.file_id
            elif m.audio:
                media_type = "audio"
                file_id = m.audio.file_id
            elif m.voice:
                media_type = "voice"
                file_id = m.voice.file_id
            elif m.document:
                media_type = "document"
                file_id = m.document.file_id
            elif m.sticker:
                media_type = "sticker"
                file_id = m.sticker.file_id
            elif m.animation:
                media_type = "animation"
                file_id = m.animation.file_id
            elif m.video_note:
                media_type = "video_note"
                file_id = m.video_note.file_id
            else:
                await m.reply("❌ No media found. Please send a photo, video, sticker, or other supported media.")
                return
            
            # Auto-detect caption format
            caption_parse_mode = "none"
            if caption:
                if caption.startswith("<"):
                    caption_parse_mode = "html"
                elif "**" in caption or "__" in caption:
                    caption_parse_mode = "markdown"
            
            s = get_settings(uid)
            s["media_list"].append({
                "type": media_type,
                "file_id": file_id,
                "caption": caption,
                "parse_mode": caption_parse_mode
            })
            save_settings(uid, s)
            GCAST_MEDIA_INPUT_STATE.pop(uid, None)
            
            type_icon = {
                "photo": "🖼", "video": "🎬", "audio": "🎵",
                "voice": "🎤", "document": "📄", "sticker": "🎨",
                "animation": "🎞", "video_note": "⏺"
            }.get(media_type, "📎")
            
            await m.reply(
                f"✅ <b>Media Added to GCast</b>\n"
                f"Type: {type_icon} <b>{media_type.title()}</b>\n"
                f"Total media: {len(s['media_list'])}\n"
                f"Caption: {html.escape(caption[:50]) if caption else '<i>no caption</i>'}"
            )
            return

        elif m.from_user.id == uid and state.get("action") == "edit":
            idx = state["idx"]
            cap = m.caption or ""
            s = get_settings(uid)
            if idx < len(s.get("media_list", [])):
                s["media_list"][idx]["caption"] = cap
                save_settings(uid, s)
                GCAST_MEDIA_INPUT_STATE.pop(uid, None)
                await m.reply(f"✅ <b>GCast Media #{idx+1} Caption Updated!</b>")
            return
    
    # Check blacklist input state
    for uid, state in list(GCAST_BL_INPUT_STATE.items()):
        if state["action"] == "add" and m.text:
            input_val = m.text.strip()
            chat_id = None
            
            try:
                if input_val.lstrip("-").isdigit():
                    chat_id = int(input_val)
                elif input_val.startswith("@"):
                    # Resolve username
                    uc = None
                    # Try to find the correct userbot client for this user
                    for cl in Altruix.clients:
                        if hasattr(cl, 'me') and cl.me and cl.me.id == uid:
                            uc = cl
                            break
                    
                    if uc:
                        try:
                            chat = await uc.get_chat(input_val)
                            chat_id = chat.id
                            await m.reply(f"✅ Resolved <code>{input_val}</code> → <code>{chat_id}</code>")
                        except Exception as e:
                            await m.reply(f"❌ Could not resolve: {input_val}\nError: {str(e)[:100]}")
                            GCAST_BL_INPUT_STATE.pop(uid, None)
                            return
                    else:
                        await m.reply("❌ No userbot client available.")
                        GCAST_BL_INPUT_STATE.pop(uid, None)
                        return
                else:
                    await m.reply("❌ Invalid format. Send:\n• Chat ID (e.g., <code>-100123456789</code>)\n• Username (e.g., <code>@groupname</code>)")
                    GCAST_BL_INPUT_STATE.pop(uid, None)
                    return
            except Exception as e:
                await m.reply(f"❌ Invalid input: {str(e)[:100]}")
                GCAST_BL_INPUT_STATE.pop(uid, None)
                return
            
            if chat_id:
                s = get_settings(uid)
                if chat_id in s["blacklist"]:
                    await m.reply(f"⚠️ Chat <code>{chat_id}</code> is already blacklisted.")
                else:
                    s["blacklist"].append(chat_id)
                    save_settings(uid, s)
                    await m.reply(f"✅ Chat <code>{chat_id}</code> added to blacklist.\n\n<i>Use <code>.gcastblist</code> to view all blacklisted chats.</i>")
                GCAST_BL_INPUT_STATE.pop(uid, None)
            return

    # Check GCAST_TEXT_INPUT_STATE for Queue Actions
    for uid, state in list(GCAST_TEXT_INPUT_STATE.items()):
        if state["action"] == "qadd" and m.text:
            q_name = m.text.strip()
            if not q_name:
                await m.reply("❌ Queue name cannot be empty.")
                return
            
            s = get_settings(uid)
            if "queues" not in s: s["queues"] = {}
            if q_name in s["queues"]:
                await m.reply(f"⚠️ Queue '{q_name}' already exists.")
            else:
                s["queues"][q_name] = []
                save_settings(uid, s)
                await m.reply(f"✅ <b>Queue Created:</b> <code>{q_name}</code>")
            
            GCAST_TEXT_INPUT_STATE.pop(uid, None)
            return

        elif state["action"] == "qeditname" and m.text:
            new_name = m.text.strip()
            old_name = state["old_name"]
            s = get_settings(uid)
            if "queues" in s and old_name in s["queues"]:
                if new_name in s["queues"]:
                    await m.reply("⚠️ Name already exists.")
                else:
                    # Rename key
                    s["queues"][new_name] = s["queues"].pop(old_name)
                    # Check if filters need update
                    if s["chat_filter"] == f"q:{old_name}":
                        s["chat_filter"] = f"q:{new_name}"
                    save_settings(uid, s)
                    await m.reply(f"✅ Queue <b>{old_name}</b> renamed to <b>{new_name}</b>")
            GCAST_TEXT_INPUT_STATE.pop(uid, None)
            return

        elif state["action"] == "qaddid" and m.text:
            input_val = m.text.strip()
            q_name = state["qname"]
            chat_id = None
            
            try:
                if input_val.lstrip("-").isdigit():
                    chat_id = int(input_val)
                elif input_val.startswith("@"):
                    # Resolve username
                    uc = None
                    for cl in Altruix.clients:
                        if hasattr(cl, 'me') and cl.me and cl.me.id == uid:
                            uc = cl; break
                    
                    if uc:
                        try:
                            chat = await uc.get_chat(input_val)
                            chat_id = chat.id
                            await m.reply(f"✅ Resolved <code>{input_val}</code> → <code>{chat_id}</code>")
                        except Exception as e:
                            await m.reply(f"❌ Could not resolve: {input_val}\n{e}")
                
                if chat_id:
                    s = get_settings(uid)
                    if q_name not in s["queues"]: s["queues"][q_name] = []
                    if chat_id not in s["queues"][q_name]:
                        s["queues"][q_name].append(chat_id)
                        save_settings(uid, s)
                        await m.reply(f"✅ Added <code>{chat_id}</code> to queue <b>{q_name}</b>")
                    else:
                        await m.reply(f"⚠️ Chat <code>{chat_id}</code> is already in queue <b>{q_name}</b>")
            except Exception as e:
                await m.reply(f"❌ Error: {e}")
            
            GCAST_TEXT_INPUT_STATE.pop(uid, None)
            return


# ==================== INLINE HANDLER (for dashboard in any chat) ====================

@Altruix.bot.on_inline_query(filters.regex(r"^gcast_menu_uid_(?P<uid>\d+)"))
@iuser_check
@log_errors
async def gcast_inline_handler(client: Client, query: InlineQuery):
    """
    Responds to inline query (triggered by @bot assistant).
    Allows opening the GCast dashboard in ANY chat via inline mode.
    Protected by @iuser_check for auth verification and group log logging.
    """
    try:
        user_id = int(query.matches[0].group("uid"))
        
        # Build Dashboard View
        text = build_dashboard_text(user_id)
        kb = build_dashboard_kb(user_id)
        
        await query.answer(
            results=[
                InlineQueryResultArticle(
                    title="📡 Auto Pro Global BroadCast Dashboard",
                    description=f"Configure global broadcast for account {user_id}",
                    input_message_content=InputTextMessageContent(
                        text,
                        parse_mode=enums.ParseMode.HTML,
                        disable_web_page_preview=True
                    ),
                    reply_markup=kb
                )
            ],
            cache_time=0
        )
    except Exception as e:
        Altruix.log(f"GCast Inline Handler Error: {e}", level=40, client=client)


# ==================== USERBOT COMMANDS ====================

@Altruix.register_on_cmd(
    ["gcast"],
    cmd_help={
        "help": "Open Auto Pro Global BroadCast dashboard via Bot Assistant.",
        "example": ".gcast"
    }
)
@iuser_check
@log_errors
async def gcast_dashboard_cmd(client: Client, message: Message):
    """
    Open the GCast dashboard via Bot Assistant.
    Tries inline mode first (works in any chat), falls back to direct message.
    Note: Inline mode buttons will delete and re-send message on click.
    """
    user_id = client.me.id
    
    # Get bot assistant
    bot = None
    bot_username = None
    if hasattr(Altruix, 'bot_manager'):
        bot = Altruix.bot_manager.get_bot(user_id)
        bot_username = Altruix.bot_manager.get_bot_username(user_id)
    if not bot:
        bot = Altruix.bot
    
    if not bot:
        # No bot assistant found
        text = build_dashboard_text(user_id)
        await message.edit(f"❌ <b>Bot assistant not found.</b>\n\n{text}")
        return
    
    # Try Inline mode first (works in ANY chat, even without bot present)
    if bot_username:
        try:
            results = await client.get_inline_bot_results(bot_username, f"gcast_menu_uid_{user_id}")
            if results.results:
                sent = await client.send_inline_bot_result(
                    message.chat.id,
                    results.query_id,
                    results.results[0].id,
                    reply_to_message_id=message.id # ✅ REPLY TO COMMAND
                )
                if sent:
                    await message.delete_if_self()
                    Altruix.log(f"[gcast_dashboard_cmd] Dashboard opened via inline mode", level=20, client=client)
                    return
        except Exception as e:
            Altruix.log(f"[gcast_dashboard_cmd] Inline mode failed: {e}, falling back to direct message", level=30, client=client)
    
    # Fallback to direct bot message (only works if bot is in the chat)
    try:
        text = build_dashboard_text(user_id)
        kb = build_dashboard_kb(user_id)
        # ✅ REPLY TO COMMAND
        await bot.send_message(message.chat.id, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML, reply_to_message_id=message.id)
        await message.delete_if_self()
        Altruix.log(f"[gcast_dashboard_cmd] Dashboard opened via direct message", level=20, client=client)
    except Exception as e:
        Altruix.log(f"[gcast_dashboard_cmd] Error sending dashboard: {e}", level=40, client=client)
        await message.edit(f"❌ Error: {e}")

@Altruix.register_on_cmd(
    ["gcaststart"],
    cmd_help={"help": "Quick start Global BroadCast.", "example": ".gcaststart"}
)
@iuser_check
@log_errors
async def gcast_start_cmd(client: Client, message: Message):
    """Quick start broadcast."""
    user_id = client.me.id
    if user_id in GCAST_TASKS and GCAST_TASKS[user_id].get("running"):
        await message.reply("⚠️ A broadcast is already running. Use <code>.gcaststop</code> first.")
        return
    s = get_settings(user_id)
    if not s["text_list"] and not s.get("media_list"):
        await message.reply("❌ Message list is empty. Add texts or media via <code>.gcast</code> dashboard first.")
        return
    await message.reply("🟢 Starting Global BroadCast...")
    asyncio.create_task(broadcast_loop(client, user_id))

@Altruix.register_on_cmd(
    ["gcastqadd"],
    cmd_help={"help": "Add chat to a specific queue.", "example": ".gcastqadd Queue1 [-100... or @user]"}
)
@iuser_check
@log_errors
async def gcast_qadd_cmd(client: Client, message: Message):
    """Add chat to a queue via command."""
    user_id = client.me.id
    parts = message.text.split(maxsplit=2)
    if len(parts) < 2:
        await message.reply("❌ Usage: <code>.gcastqadd [queue_name] [chat_id/@username]</code>")
        return
    
    q_name = parts[1]
    input_val = parts[2] if len(parts) > 2 else str(message.chat.id)
    chat_id = None
    
    try:
        if input_val.lstrip("-").isdigit():
            chat_id = int(input_val)
        else:
            chat = await client.get_chat(input_val)
            chat_id = chat.id
            
        s = get_settings(user_id)
        if "queues" not in s: s["queues"] = {}
        if q_name not in s["queues"]: s["queues"][q_name] = []
        
        if chat_id not in s["queues"][q_name]:
            s["queues"][q_name].append(chat_id)
            save_settings(user_id, s)
            await message.reply(f"✅ Added <code>{chat_id}</code> to queue <b>{q_name}</b>")
        else:
            await message.reply(f"⚠️ Chat already in queue <b>{q_name}</b>")
    except Exception as e:
        await message.reply(f"❌ Error: {e}")

@Altruix.register_on_cmd(
    ["gcastqdel"],
    cmd_help={"help": "Remove chat from a specific queue.", "example": ".gcastqdel Queue1 [-100...]"}
)
@iuser_check
@log_errors
async def gcast_qdel_cmd(client: Client, message: Message):
    """Remove chat from a queue via command."""
    user_id = client.me.id
    parts = message.text.split(maxsplit=2)
    if len(parts) < 2:
        await message.reply("❌ Usage: <code>.gcastqdel [queue_name] [chat_id]</code>")
        return
    
    q_name = parts[1]
    input_val = parts[2] if len(parts) > 2 else str(message.chat.id)
    
    try:
        cid = int(input_val) if input_val.lstrip("-").isdigit() else (await client.get_chat(input_val)).id
        s = get_settings(user_id)
        if q_name in s.get("queues", {}) and cid in s["queues"][q_name]:
            s["queues"][q_name].remove(cid)
            save_settings(user_id, s)
            await message.reply(f"✅ Removed <code>{cid}</code> from queue <b>{q_name}</b>")
        else:
            await message.reply(f"⚠️ Chat not found in queue <b>{q_name}</b>")
    except Exception as e:
        await message.reply(f"❌ Error: {e}")

@Altruix.register_on_cmd(
    ["gcastqlist"],
    cmd_help={"help": "List all chat queues.", "example": ".gcastqlist"}
)
@iuser_check
@log_errors
async def gcast_qlist_cmd(client: Client, message: Message):
    """List all queues."""
    user_id = client.me.id
    s = get_settings(user_id)
    queues = s.get("queues", {})
    if not queues:
        await message.reply("🚙 No queues found.")
        return
    
    text = "📁 <b>Chat Queues:</b>\n\n"
    for qname, chats in queues.items():
        text += f"• <b>{qname}</b>: {len(chats)} chats\n"
    
    await message.reply(text)

@Altruix.register_on_cmd(
    ["gcaststop"],
    cmd_help={"help": "Stop active Global BroadCast.", "example": ".gcaststop"}
)
@iuser_check
@log_errors
async def gcast_stop_cmd(client: Client, message: Message):
    """Stop broadcast."""
    user_id = client.me.id
    task = GCAST_TASKS.get(user_id)
    if not task or not task.get("running"):
        await message.reply("⚫ No active broadcast.")
        return
    task["running"] = False
    task["pause_event"].set()
    atask = task.get("asyncio_task")
    if atask and not atask.done():
        atask.cancel()
    await message.reply(f"🔴 GCast <code>{task.get('task_id', '?')}</code> stopped.")

@Altruix.register_on_cmd(
    ["gcastpause"],
    cmd_help={"help": "Pause active Global BroadCast.", "example": ".gcastpause"}
)
@iuser_check
@log_errors
async def gcast_pause_cmd(client: Client, message: Message):
    """Pause broadcast."""
    user_id = client.me.id
    task = GCAST_TASKS.get(user_id)
    if not task or not task.get("running"):
        await message.reply("⚫ No active broadcast.")
        return
    task["pause_event"].clear()
    await message.reply(f"⏸ GCast <code>{task.get('task_id', '?')}</code> paused.")

@Altruix.register_on_cmd(
    ["gcastresume"],
    cmd_help={"help": "Resume paused Global BroadCast.", "example": ".gcastresume"}
)
@iuser_check
@log_errors
async def gcast_resume_cmd(client: Client, message: Message):
    """Resume broadcast."""
    user_id = client.me.id
    task = GCAST_TASKS.get(user_id)
    if not task or not task.get("running"):
        await message.reply("⚫ No active broadcast.")
        return
    task["pause_event"].set()
    await message.reply(f"▶️ GCast <code>{task.get('task_id', '?')}</code> resumed.")

@Altruix.register_on_cmd(
    ["gcaststatus"],
    cmd_help={"help": "Show Global BroadCast status.", "example": ".gcaststatus"}
)
@iuser_check
@log_errors
async def gcast_status_cmd(client: Client, message: Message):
    """Show broadcast status."""
    user_id = client.me.id
    text = build_dashboard_text(user_id)
    await message.reply(text)

@Altruix.register_on_cmd(
    ["gcastbl"],
    cmd_help={
        "help": "Toggle a chat in the GCast blacklist.",
        "example": ".gcastbl -100123456789"
    }
)
@iuser_check
@log_errors
async def gcast_bl_cmd(client: Client, message: Message):
    """Toggle a chat in the blacklist."""
    user_id = client.me.id
    chat_id = message.chat.id
    
    if message.user_input and message.user_input.lstrip('-').isdigit():
        chat_id = int(message.user_input)
    
    s = get_settings(user_id)
    if chat_id in s["blacklist"]:
        s["blacklist"].remove(chat_id)
        action = "REMOVED FROM"
    else:
        s["blacklist"].append(chat_id)
        action = "ADDED TO"
    save_settings(user_id, s)
    await message.reply(f"✅ Chat <code>{chat_id}</code> has been <b>{action}</b> GCast Blacklist.")

@Altruix.register_on_cmd(
    ["gcastblist"],
    cmd_help={"help": "View all blacklisted chats for GCast.", "example": ".gcastblist"}
)
@iuser_check
@log_errors
async def gcast_blist_cmd(client: Client, message: Message):
    """View all blacklisted chats."""
    user_id = client.me.id
    s = get_settings(user_id)
    bl = s["blacklist"]
    
    if not bl:
        await message.reply("📋 <b>GCast Blacklist</b>\n\n<i>Blacklist is empty.</i>")
        return
    
    lines = []
    for cid in bl:
        try:
            chat = await client.get_chat(cid)
            name = chat.title or chat.first_name or f"Chat {cid}"
        except Exception:
            name = f"Chat {cid}"
        lines.append(f"• <code>{cid}</code> — {html.escape(name)}")
    
    text = (
        f"📋 <b>GCast Blacklist</b>\n"
        f"Total: <code>{len(bl)}</code> chats\n\n"
        + "\n".join(lines)
    )
    await message.reply(text)

@Altruix.register_on_cmd(
    ["gcastbldel", "gcastblremove"],
    cmd_help={
        "help": "Remove a chat from GCast blacklist.",
        "example": ".gcastbldel -100123456789"
    }
)
@iuser_check
@log_errors
async def gcast_bl_del_cmd(client: Client, message: Message):
    """Remove a chat from the blacklist."""
    user_id = client.me.id
    
    if not message.user_input:
        await message.reply("❌ <b>Usage:</b> <code>.gcastbldel &lt;chat_id&gt;</code>\n\nExample: <code>.gcastbldel -100123456789</code>")
        return
    
    input_val = message.user_input.strip()
    chat_id = None
    
    try:
        if input_val.lstrip('-').isdigit():
            chat_id = int(input_val)
        elif input_val.startswith("@"):
            # Resolve username
            try:
                chat = await client.get_chat(input_val)
                chat_id = chat.id
            except Exception as e:
                await message.reply(f"❌ Could not resolve: {input_val}\nError: {e}")
                return
        else:
            await message.reply("❌ Send a chat ID (number) or @username.\n\nExample: <code>.gcastbldel -100123456789</code>")
            return
    except Exception as e:
        await message.reply(f"❌ Invalid input: {e}")
        return
    
    if chat_id:
        s = get_settings(user_id)
        if chat_id in s["blacklist"]:
            s["blacklist"].remove(chat_id)
            save_settings(user_id, s)
            await message.reply(f"✅ Chat <code>{chat_id}</code> has been <b>REMOVED FROM</b> GCast Blacklist.")
        else:
            await message.reply(f"⚠️ Chat <code>{chat_id}</code> is not in the blacklist.")

@Altruix.register_on_cmd(
    ["gcastadd"],
    cmd_help={
        "help": "Add message to GCast list by replying to it.",
        "example": ".gcastadd (replying to a message)"
    }
)
@iuser_check
@log_errors
async def gcast_add_cmd(client: Client, message: Message):
    """Add a message to the GCast lists by replying."""
    user_id = client.me.id
    if not message.reply_to_message:
        await message.reply("❌ <b>Error:</b> You must reply to a message to add it to GCast.")
        return

    rep = message.reply_to_message
    s = get_settings(user_id)
    
    # Handle Text
    if rep.text:
        text = rep.text
        # Auto-detect format
        parse_mode = "none"
        if text.startswith("<"):
            parse_mode = "html"
        elif "**" in text or "__" in text or "`" in text:
            parse_mode = "markdown"
            
        s["text_list"].append({
            "content": text,
            "parse_mode": parse_mode
        })
        save_settings(user_id, s)
        
        mode_label = {"html": "HTML", "markdown": "Markdown", "none": "Plain Text"}.get(parse_mode, "Plain")
        await message.reply(
            f"✅ <b>Text Added to GCast</b>\n"
            f"Format: <b>{mode_label}</b>\n"
            f"Total texts: {len(s['text_list'])}\n"
            f"Preview: {html.escape(text[:80])}"
        )

    # Handle Media
    else:
        media_type = None
        file_id = None
        caption = rep.caption or ""
        
        if rep.photo:
            media_type = "photo"
            file_id = rep.photo.file_id
        elif rep.video:
            media_type = "video"
            file_id = rep.video.file_id
        elif rep.audio:
            media_type = "audio"
            file_id = rep.audio.file_id
        elif rep.voice:
            media_type = "voice"
            file_id = rep.voice.file_id
        elif rep.document:
            media_type = "document"
            file_id = rep.document.file_id
        elif rep.sticker:
            media_type = "sticker"
            file_id = rep.sticker.file_id
        elif rep.animation:
            media_type = "animation"
            file_id = rep.animation.file_id
        elif rep.video_note:
            media_type = "video_note"
            file_id = rep.video_note.file_id
            
        if media_type:
            # Auto-detect caption format
            caption_parse_mode = "none"
            if caption:
                if caption.startswith("<"):
                    caption_parse_mode = "html"
                elif "**" in caption or "__" in caption:
                    caption_parse_mode = "markdown"

            s["media_list"].append({
                "type": media_type,
                "file_id": file_id,
                "caption": caption,
                "parse_mode": caption_parse_mode
            })
            save_settings(user_id, s)
            
            type_icon = {
                "photo": "🖼", "video": "🎬", "audio": "🎵",
                "voice": "🎤", "document": "📄", "sticker": "🎨",
                "animation": "🎞", "video_note": "⏺"
            }.get(media_type, "📎")
            
            await message.reply(
                f"✅ <b>Media Added to GCast</b>\n"
                f"Type: {type_icon} <b>{media_type.title()}</b>\n"
                f"Total media: {len(s['media_list'])}\n"
                f"Caption: {html.escape(caption[:50]) if caption else '<i>no caption</i>'}"
            )
        else:
            await message.reply("❌ <b>Error:</b> Unsupported message type. Please reply to text or media.")


# ==================== RESUME AFTER RESTART ====================

async def resume_pending_broadcasts():
    """Check for interrupted broadcasts and resume them after startup."""
    try:
        await asyncio.sleep(15)  # Wait for all clients to fully initialize
        
        active_tasks = get_active_tasks()
        if not active_tasks:
            return
        
        Altruix.log(f"[GCast] Found {len(active_tasks)} pending broadcast(s) to resume", level=20)
        
        for uid_str, task_data in active_tasks.items():
            uid = int(uid_str)
            task_id = task_data.get("task_id", "?")
            sent_index = task_data.get("sent_index", 0)
            targets = task_data.get("targets", [])
            total = len(targets)
            
            if sent_index >= total:
                # Already completed, clean up stale entry
                remove_active_task(uid)
                continue
            
            # Find the matching client
            resume_client = None
            if hasattr(Altruix, 'clients') and Altruix.clients:
                for cl in Altruix.clients:
                    try:
                        if cl.me and cl.me.id == uid:
                            resume_client = cl
                            break
                    except Exception:
                        continue
            
            if not resume_client:
                Altruix.log(f"[GCast] No client found for uid {uid}, skipping resume of {task_id}", level=30)
                remove_active_task(uid)
                continue
            
            # Check if there's already an active task for this user
            if uid in GCAST_TASKS and GCAST_TASKS[uid].get("running"):
                Altruix.log(f"[GCast] Task already running for uid {uid}, skipping resume", level=20, client=resume_client)
                continue
            
            await send_log(
                f"🔄 <b>GCast Resuming</b> <code>{task_id}</code>\n"
                f"{'━' * 18}\n"
                f"📊 <b>Progress:</b> {sent_index}/{total} chats already sent\n"
                f"▶️ Resuming from chat #{sent_index + 1}...\n"
                f"{'━' * 18}",
                client=resume_client
            )
            
            # Start the broadcast loop with resume index
            asyncio.create_task(broadcast_loop(resume_client, uid, start_index=sent_index))
            Altruix.log(f"[GCast] Resumed broadcast {task_id} for uid {uid} from index {sent_index}/{total}", level=20, client=resume_client)
    except Exception as e:
        Altruix.log(f"[GCast] resume_pending_broadcasts failed: {e}", level=40)


def schedule_resume():
    """Schedule the resume check after event loop is running."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(resume_pending_broadcasts())
        else:
            loop.call_soon(lambda: asyncio.create_task(resume_pending_broadcasts()))
    except Exception as e:
        Altruix.log(f"[GCast] schedule_resume failed: {e}", level=40)


# Auto-schedule resume on plugin load
schedule_resume()
