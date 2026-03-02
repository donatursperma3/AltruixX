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
from datetime import datetime
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
PLUGIN_VERSION = "1.0.30"

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
        logger.error(f"Failed to load settings: {e}")
    return {}

def _save_all_settings(data: dict):
    """Save all user settings to JSON file."""
    try:
        STORAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STORAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save settings: {e}")

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
        "self_destruct_delay": 30   # delay before deleting sent message (seconds)
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
        logger.error(f"send_log failed: {e}")
    return None

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
    sent_message_id: int = None
):
    """Send detailed log notification with blockquote expand format."""
    try:
        # Create clickable chat link (works on iOS/Android/Desktop)
        # Always use https://t.me/c/ format for supergroups/channels
        chat_link = None
        
        if str(chat_id).startswith("-100"):
            # Supergroup/Channel: remove -100 prefix
            clean_chat_id = str(chat_id)[4:]
            
            if sent_message_id:
                # Link to specific message
                chat_link = f"<a href='https://t.me/c/{clean_chat_id}/{sent_message_id}'>{html.escape(chat_title)}</a>"
            else:
                # Link to chat only
                chat_link = f"<a href='https://t.me/c/{clean_chat_id}'>{html.escape(chat_title)}</a>"
        else:
            # Regular group or private chat: use plain text (no clickable link for these)
            chat_link = html.escape(chat_title)
        
        # Get current time
        from datetime import datetime
        current_time = datetime.now().strftime("%H:%M:%S")
        
        # Get account info
        account_name = "Unknown"
        if client and client.me:
            first = client.me.first_name or ""
            last = client.me.last_name or ""
            account_name = f"{first} {last}".strip() or str(user_id)
        
        # Build status emoji and text
        if success:
            status_emoji = "✅"
            status_text = "SUCCESS"
        else:
            status_emoji = "❌"
            status_text = "FAILED"
        
        # Build message
        text = (
            f"<blockquote expandable>{status_emoji} <b>GCast {status_text}</b>\n"
            f"{'━' * 18}\n"
            f"👤 <b>Account:</b> {html.escape(account_name)}\n"
            f"💬 <b>Chat:</b> {chat_link}\n"
            f"🆔 <b>Chat ID:</b> <code>{chat_id}</code>\n"
            f"� <b>Type:</b> {message_type}\n"
            f"� <b>Content:</b> {html.escape(content_preview[:50])}{'...' if len(content_preview) > 50 else ''}\n"
            f"� <b>Time:</b> {current_time}\n"
        )
        
        # Always show purge status (even if 0)
        text += f"🧹 <b>Purged:</b> {purge_count} msg\n"
        
        if react_success:
            text += f"⚡ <b>Reaction:</b> Added successfully\n"
        
        if not success and error_reason:
            text += f"❌ <b>Reason:</b> {html.escape(error_reason)}\n"
        
        text += f"{'━' * 18}</blockquote>"
        
        await send_log(text, client=client)
    except Exception as e:
        logger.error(f"send_detailed_log failed: {e}")

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
                
    except Exception as e:
        logger.error(f"[safe_edit_message] Error editing message: {e}")
        logger.error(f"[safe_edit_message] Callback data: {cb.data}")
        # logger.error(f"[safe_edit_message] Message: {cb.message}")
        await safe_cb_answer(cb, f"❌ Error: {str(e)[:100]}", show_alert=True)
        return False


def _filter_label(val: str) -> str:
    """Convert filter value to display label."""
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
    smart_purge_status = "🟢 ON" if s.get('smart_purge', False) else "🔴 OFF"
    
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
    
    text = (
        f"📡 <b>Auto Pro Global BroadCast</b>\n"
        f"{'━' * 18}\n"
        f"Account: {account_mention}\n"
        f"Status: {status} | Task: <code>{task_id}</code>\n"
        f"Chat Filter: <b>{_filter_label(s['chat_filter'])}</b> | "
        f"Admin: <b>{_filter_label(s['admin_filter'])}</b>\n"
        f"Delay/Chat: <b>{s['delay_per_chat']}s</b> | "
        f"Messages: <b>{total_messages} items</b>\n"
        f"📝 Texts: <b>{len(s.get('text_list', []))}</b> | "
        f"🎬 Media: <b>{len(s.get('media_list', []))}</b>\n"
        f"Random: <b>{'ON' if s['random_text'] else 'OFF'}</b> | "
        f"Recurring: <b>{'ON' if s['recurring'] else 'OFF'}</b>\n"
        f"Blacklist: <b>{len(s['blacklist'])} chats</b>\n"
        f"🧹 Smart Purge: {smart_purge_status}\n"
        f"🧨 Self-Destruct: <b>{'🟢 ON' if s.get('self_destruct', False) else '🔴 OFF'}</b> (<b>{s.get('self_destruct_delay', 30)}s</b>)\n"
    )
    if task and task["running"]:
        text += (
            f"{'━' * 18}\n"
            f"📊 Progress: {progress}\n"
            f"📍 Current: {html.escape(str(current)[:30])}\n"
            f"❌ Errors: {errs}\n"
        )
    text += f"{'━' * 18}"
    return text

def build_dashboard_kb(user_id: int) -> InlineKeyboardMarkup:
    """Build the main dashboard inline keyboard."""
    s = get_settings(user_id)
    task = GCAST_TASKS.get(user_id)
    is_running = task and task.get("running", False)
    is_paused = is_running and not task["pause_event"].is_set()

    uid = user_id
    rows = []

    # Get user button style
    btn_style = get_user_button_style(user_id)

    # Row 1: Pause / Resume / Refresh (only if running)
    if is_running:
        if is_paused:
            rows.append([
                InlineKeyboardButton("▶️ Resume", callback_data=f"pgc_resume_{uid}", style=btn_style),
                InlineKeyboardButton("📊 Refresh", callback_data=f"pgc_refresh_{uid}", style=btn_style),
            ])
        else:
            rows.append([
                InlineKeyboardButton("⏸ Pause", callback_data=f"pgc_pause_{uid}", style=btn_style),
                InlineKeyboardButton("📊 Refresh", callback_data=f"pgc_refresh_{uid}", style=btn_style),
            ])
        # Row 2: Stop (only if running)
        rows.append([
            InlineKeyboardButton("🔴 Stop GCast", callback_data=f"pgc_stop_{uid}", style=btn_style),
        ])

    # Row 3: Chat Filter / Admin Filter
    rows.append([
        InlineKeyboardButton(f"📋 Chat: {_filter_label(s['chat_filter'])}", callback_data=f"pgc_chatfilter_{uid}", style=btn_style),
        InlineKeyboardButton(f"👤 Admin: {_filter_label(s['admin_filter'])}", callback_data=f"pgc_adminfilter_{uid}", style=btn_style),
    ])

    # Row 4: Delay/Chat [-2] [value] [+2]
    rows.append([
        InlineKeyboardButton("-2", callback_data=f"pgc_delay_dec_{uid}", style=btn_style),
        InlineKeyboardButton(f"⏱ Delay/Chat: {s['delay_per_chat']}s", callback_data=f"pgc_noop_{uid}", style=btn_style),
        InlineKeyboardButton("+2", callback_data=f"pgc_delay_inc_{uid}", style=btn_style),
    ])

    # Row 5: Message List / Random Toggle
    total_messages = len(s.get('text_list', [])) + len(s.get('media_list', []))
    rows.append([
        InlineKeyboardButton(f"📝 Messages ({total_messages})", callback_data=f"pgc_msgmenu_{uid}", style=btn_style),
        InlineKeyboardButton(f"🔀 Random: {'ON' if s['random_text'] else 'OFF'}", callback_data=f"pgc_randomtoggle_{uid}", style=btn_style),
    ])

    # Row 6: Blacklist / List Chats
    rows.append([
        InlineKeyboardButton(f"🚫 Blacklist ({len(s['blacklist'])})", callback_data=f"pgc_blmenu_{uid}", style=btn_style),
        InlineKeyboardButton(f"📋 List Chats", callback_data=f"pgc_listchats_{uid}", style=btn_style),
    ])

    # Row 7: Recurring / Notif Logs
    notif_status = "ON" if s.get('notify_logs', True) else "OFF"
    rows.append([
        InlineKeyboardButton(f"🔁 Recurring: {'ON' if s['recurring'] else 'OFF'}", callback_data=f"pgc_recurring_{uid}", style=btn_style),
        InlineKeyboardButton(f"🔔 Notif: {notif_status}", callback_data=f"pgc_notiftoggle_{uid}", style=btn_style),
    ])

    # Row 8: Smart Purge / Auto React
    smart_purge_status = "ON" if s.get('smart_purge', False) else "OFF"
    react_status = "ON" if s.get('auto_react', False) else "OFF"
    rows.append([
        InlineKeyboardButton(f"🧹 Smart Purge: {smart_purge_status}", callback_data=f"pgc_smartpurge_{uid}", style=btn_style),
        InlineKeyboardButton(f"⚡ React: {react_status}", callback_data=f"pgc_reactmenu_{uid}", style=btn_style),
    ])

    # Row 9: Self-Destruct Toggle / Delay
    sd_status = "ON" if s.get('self_destruct', False) else "OFF"
    rows.append([
        InlineKeyboardButton(f"🧨 Self-Destruct: {sd_status}", callback_data=f"pgc_sdtoggle_{uid}", style=btn_style),
        InlineKeyboardButton("-10s", callback_data=f"pgc_sddelay_dec_{uid}", style=btn_style),
        InlineKeyboardButton("+10s", callback_data=f"pgc_sddelay_inc_{uid}", style=btn_style),
    ])

    # Row 10: Info / Refresh
    rows.append([
        InlineKeyboardButton("📊 Info", callback_data=f"pgc_info_{uid}", style=btn_style),
        InlineKeyboardButton("🔄 Refresh", callback_data=f"pgc_refresh_{uid}", style=btn_style),
    ])

    # Row 10: Start / Close (bottom row)
    if not is_running:
        rows.append([
            InlineKeyboardButton("🟢 Start GCast", callback_data=f"pgc_startconf_{uid}", style=btn_style),
            InlineKeyboardButton("❌ Close Menu", callback_data=f"pgc_close_{uid}", style=btn_style),
        ])
    else:
        rows.append([
            InlineKeyboardButton("❌ Close Menu", callback_data=f"pgc_close_{uid}", style=btn_style),
        ])

    return InlineKeyboardMarkup(rows)


# ==================== MESSAGE LIST SUB-MENU ====================

def build_msglist_text(user_id: int) -> str:
    """Build the message list sub-menu text with selection mode info."""
    s = get_settings(user_id)
    text_list = s.get("text_list", [])
    media_list = s.get("media_list", [])
    random_enabled = s.get("random_text", True)
    fixed_msg_idx = s.get("fixed_message_index", None)
    
    lines = []
    
    # ✅ NEW: Explain message selection logic with fixed message mode
    if random_enabled:
        lines.append("🎲 <b>Mode:</b> Random - Messages sent randomly")
    else:
        if fixed_msg_idx is not None:
            lines.append(f"📌 <b>Mode:</b> Fixed - Always send message #{fixed_msg_idx + 1}")
        else:
            lines.append("📋 <b>Mode:</b> Sequential - Messages sent in order (1→2→3...→1)")
            lines.append("⚠️ <i>Sequential mode may look spammy. Consider using Fixed mode.</i>")
    lines.append("")
    
    if not text_list and not media_list:
        lines.append("📭 <i>No messages added yet.</i>")
        total = 0
        return (
            f"📝 <b>Message List</b> ({total} items)\n"
            f"{'━' * 18}\n" + "\n".join(lines)
        )
    
    # Show text messages
    if text_list:
        lines.append("<b>📝 Text Messages:</b>")
        for i, item in enumerate(text_list[:10], 1):
            if isinstance(item, dict):
                content = item.get("content", "")
                parse_mode = item.get("parse_mode", "html")
            else:
                # Old format compatibility
                content = str(item)
                parse_mode = "html"
            
            preview = html.escape(content[:50]) + ("..." if len(content) > 50 else "")
            mode_icon = {"html": "🌐", "markdown": "�", "none": "📄"}.get(parse_mode, "📄")
            lines.append(f"{i}. {mode_icon} {preview} <i>({len(content)} chars)</i>")
    
    # Show media messages
    if media_list:
        lines.append("\n<b>🎬 Media Messages:</b>")
        for i, item in enumerate(media_list[:10], 1):
            media_type = item.get("type", "unknown")
            caption = item.get("caption", "")
            type_icon = {
                "photo": "🖼", "video": "🎬", "audio": "🎵",
                "voice": "🎤", "document": "📄", "sticker": "🎨",
                "animation": "🎞", "video_note": "⏺"
            }.get(media_type, "📎")
            
            cap_preview = html.escape(caption[:30]) if caption else "<i>no caption</i>"
            
            # ✅ Mark fixed message with 📌
            actual_idx = len(text_list) + i - 1
            fixed_marker = " 📌" if fixed_msg_idx == actual_idx else ""
            lines.append(f"{len(text_list) + i}. {type_icon} {media_type.title()} - {cap_preview}{fixed_marker}")
    
    total = len(text_list) + len(media_list)
    return (
        f"📝 <b>Message List</b> ({total} items)\n"
        f"{'━' * 18}\n" + "\n".join(lines)
    )

def build_msglist_kb(user_id: int) -> InlineKeyboardMarkup:
    """Build the message list sub-menu keyboard with preview and delete confirmation."""
    uid = user_id
    s = get_settings(user_id)
    text_list = s.get("text_list", [])
    media_list = s.get("media_list", [])
    
    # Get user button style
    btn_style = get_user_button_style(user_id)
    
    rows = [
        [
            InlineKeyboardButton("➕ Add Text", callback_data=f"pgc_addtext_{uid}", style=btn_style),
            InlineKeyboardButton("➕ Add Media", callback_data=f"pgc_addmedia_{uid}", style=btn_style),
        ],
        [
            InlineKeyboardButton("🗑 Clear All", callback_data=f"pgc_msgclearconf_{uid}", style=btn_style),
            InlineKeyboardButton("📌 Set Fixed", callback_data=f"pgc_setfixed_{uid}", style=btn_style),
        ],
    ]
    
    # ✅ NEW: Show preview + delete buttons for texts (max 5)
    for actual_idx in range(min(5, len(text_list))):
        item = text_list[actual_idx]
        if isinstance(item, dict):
            content = item.get("content", "")
        else:
            content = str(item)
        preview = content[:20] + ("..." if len(content) > 20 else "")
        rows.append([
            InlineKeyboardButton(f"📝 #{actual_idx+1}: {preview}", callback_data=f"pgc_msgsetfixed_text_{uid}_{actual_idx}", style=btn_style),
            InlineKeyboardButton("👁", callback_data=f"pgc_msgpreview_text_{uid}_{actual_idx}", style=btn_style),
            InlineKeyboardButton("🗑", callback_data=f"pgc_msgdelconf_text_{uid}_{actual_idx}", style=btn_style),
        ])
    
    # ✅ NEW: Show preview + delete buttons for media (max 5)
    for actual_idx in range(min(5, len(media_list))):
        item = media_list[actual_idx]
        media_type = item.get("type", "unknown")
        type_icon = {
            "photo": "🖼", "video": "🎬", "audio": "🎵",
            "voice": "🎤", "document": "📄", "sticker": "🎨",
            "animation": "🎞", "video_note": "⏺"
        }.get(media_type, "📎")
        rows.append([
            InlineKeyboardButton(f"{type_icon} #{len(text_list)+actual_idx+1}: {media_type}", callback_data=f"pgc_msgsetfixed_media_{uid}_{actual_idx}", style=btn_style),
            InlineKeyboardButton("👁", callback_data=f"pgc_msgpreview_media_{uid}_{actual_idx}", style=btn_style),
            InlineKeyboardButton("🗑", callback_data=f"pgc_msgdelconf_media_{uid}_{actual_idx}", style=btn_style),
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
        f"🚫 <b>Blacklist Manager</b>\n"
        f"<i>Page {page+1}/{total_pages}</i>\n"
        f"{'━' * 18}\n"
        f"Total: <b>{len(bl)}</b> chats\n\n"
        + "\n".join(lines)
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
        f"🧹 <b>Smart Purgeme Settings</b>\n"
        f"{'━' * 18}\n"
        f"Status: {status}\n\n"
        f"<b>Current Settings:</b>\n"
        f"• Limit: <b>{s.get('purge_limit', 4)} messages</b>\n"
        f"• Delay/Msg: <b>{s.get('purge_delay_msg', 1.0)}s</b>\n"
        f"• Mode: <b>{s.get('purge_mode', 'oldest').title()}</b>\n"
        f"• Offset: <b>{s.get('purge_offset', 0)} messages</b>\n\n"
        f"<i>Smart Purge akan menghapus pesan Anda di chat target\n"
        f"sebelum mengirim broadcast GCast.</i>"
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
        f"⚡ <b>Auto React Settings</b>\n"
        f"{'━' * 18}\n"
        f"Status: {status}\n\n"
        f"<b>Current Settings:</b>\n"
        f"• Emoji: {s.get('react_emoji', '👍')}\n"
        f"• Delay: <b>{s.get('react_delay', 4)}s</b>\n\n"
        f"<i>Auto React akan menambahkan reaksi emoji pada pesan\n"
        f"yang berhasil dikirim ke chat target.</i>"
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
            "<b>📊 AUTO PRO GLOBAL BROADCAST - INFO</b>\n"
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
            "  ↳ <b>📌 Set Fixed:</b> Pilih satu pesan tetap untuk broadcast"
        ),
        # Page 1: Dashboard Buttons Part 2
        (
            "<b>📊 AUTO PRO GLOBAL BROADCAST - INFO</b>\n"
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
            "  ↳ Perbarui tampilan dashboard"
        ),
        # Page 2: Smart Purge & Auto React
        (
            "<b>📊 AUTO PRO GLOBAL BROADCAST - INFO</b>\n"
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
            "  ↳ React count ditampilkan di completion log"
        ),
        # Page 3: Format Text
        (
            "<b>📊 AUTO PRO GLOBAL BROADCAST - INFO</b>\n"
            "<i>Page 4/4</i>\n\n"
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
            "<i>Gunakan tombol 'Show CMD' untuk melihat daftar command manual.</i>"
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
        f"<b>📋 AUTO PRO GLOBAL BROADCAST - COMMANDS</b>\n"
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
        "  ↳ Contoh: <code>.gcastbldel -1001234567890</code>\n\n"
        "• <code>.gcastblist</code>\n"
        "  ↳ Lihat semua chat yang di-blacklist\n\n"
        "<i>Gunakan dashboard untuk pengaturan lanjutan seperti\n"
        "filter, delay, text list, dan lainnya.</i>"
    )

# ==================== BROADCAST LOOP ====================

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
        
        logger.info(f"[Smart Purge] Scanning chat {chat_id} ({title}) - Limit: {purge_limit}, Offset: {purge_offset}, Mode: {purge_mode}")
        
        async for msg in client.search_messages(chat_id, from_user="me", limit=fetch_limit):
            collected_ids.append(msg.id)
            if len(collected_ids) >= fetch_limit:
                break
        
        if not collected_ids:
            logger.info(f"[Smart Purge] No messages found in chat {chat_id}")
            return stats
        
        # Apply mode and offset
        if purge_mode == "oldest":
            collected_ids.reverse()
        if purge_mode == "newest":
            # Already in newest order from search_messages
            pass
        if purge_offset > 0:
            collected_ids = collected_ids[purge_offset:]
        collected_ids = collected_ids[:purge_limit]
        
        if not collected_ids:
            logger.info(f"[Smart Purge] No messages to delete after applying offset in chat {chat_id}")
            return stats
        
        # Delete messages with delay
        logger.info(f"[Smart Purge] Deleting {len(collected_ids)} messages in chat {chat_id}")
        for i in range(0, len(collected_ids), 100):
            batch = collected_ids[i:i+100]
            try:
                await client.delete_messages(chat_id, batch)
                stats["deleted"] += len(batch)
                if purge_delay_msg > 0:
                    await asyncio.sleep(purge_delay_msg)
            except FloodWait as fw:
                wait = fw.value + 3
                logger.warning(f"[Smart Purge] FloodWait {wait}s in chat {chat_id}")
                await asyncio.sleep(wait)
                # Retry this batch
                try:
                    await client.delete_messages(chat_id, batch)
                    stats["deleted"] += len(batch)
                except Exception as e:
                    logger.error(f"[Smart Purge] Retry failed for chat {chat_id}: {e}")
                    stats["errors"] += len(batch)
            except ChatWriteForbidden:
                logger.warning(f"[Smart Purge] ChatWriteForbidden in chat {chat_id}")
                stats["errors"] += len(batch)
                break
            except Exception as e:
                logger.error(f"[Smart Purge] Error deleting batch in chat {chat_id}: {e}")
                stats["errors"] += len(batch)
        
        logger.info(f"[Smart Purge] Completed for chat {chat_id} - Deleted: {stats['deleted']}, Errors: {stats['errors']}")
        return stats
    
    except Exception as e:
        logger.error(f"[Smart Purge] Critical error in chat {chat_id}: {e}")
        return stats

async def get_target_chats(client: Client, settings: dict) -> list:
    """
    Scan dialogs and return list of target chats based on filter settings.
    Returns list of (chat_id, chat_title).
    """
    targets = []
    blacklist = set(settings.get("blacklist", []))
    chat_filter = settings.get("chat_filter", "all")
    admin_filter = settings.get("admin_filter", "all")
    
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
            
            title = chat.title or chat.first_name or f"Chat {cid}"
            targets.append((cid, title))
    except Exception as e:
        logger.error(f"get_target_chats error: {e}")
    
    return targets

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

        logger.info(f"[Smart Purge] Scanning chat {chat_id} ({title}) - Limit: {purge_limit}, Offset: {purge_offset}, Mode: {purge_mode}")

        async for msg in client.search_messages(chat_id, from_user="me", limit=fetch_limit):
            collected_ids.append(msg.id)
            if len(collected_ids) >= fetch_limit:
                break

        if not collected_ids:
            logger.info(f"[Smart Purge] No messages found in chat {chat_id}")
            return stats

        # Apply mode and offset
        if purge_mode == "oldest":
            collected_ids.reverse()
        if purge_offset > 0:
            collected_ids = collected_ids[purge_offset:]
        collected_ids = collected_ids[:purge_limit]

        if not collected_ids:
            logger.info(f"[Smart Purge] No messages to delete after applying offset in chat {chat_id}")
            return stats

        # Delete messages with delay
        logger.info(f"[Smart Purge] Deleting {len(collected_ids)} messages in chat {chat_id}")
        for i in range(0, len(collected_ids), 100):
            batch = collected_ids[i:i+100]
            try:
                await client.delete_messages(chat_id, batch)
                stats["deleted"] += len(batch)
                if purge_delay_msg > 0:
                    await asyncio.sleep(purge_delay_msg)
            except FloodWait as fw:
                wait = fw.value + 3
                logger.warning(f"[Smart Purge] FloodWait {wait}s in chat {chat_id}")
                await asyncio.sleep(wait)
                # Retry this batch
                try:
                    await client.delete_messages(chat_id, batch)
                    stats["deleted"] += len(batch)
                except Exception as e:
                    logger.error(f"[Smart Purge] Retry failed for chat {chat_id}: {e}")
                    stats["errors"] += len(batch)
            except ChatWriteForbidden:
                logger.warning(f"[Smart Purge] ChatWriteForbidden in chat {chat_id}")
                stats["errors"] += len(batch)
                break
            except Exception as e:
                logger.error(f"[Smart Purge] Error deleting batch in chat {chat_id}: {e}")
                stats["errors"] += len(batch)

        logger.info(f"[Smart Purge] Completed for chat {chat_id} - Deleted: {stats['deleted']}, Errors: {stats['errors']}")
        return stats

    except Exception as e:
        logger.error(f"[Smart Purge] Critical error in chat {chat_id}: {e}")
        return stats


async def broadcast_loop(client: Client, user_id: int):
    """
    Main broadcast loop. Sends messages to all target chats.
    Respects pause/stop signals and logs every action.
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
        await send_log("❌ <b>GCast Error:</b> Message list is empty. Add texts or media first.", client=client)
        return
    
    # Generate task ID
    task_id = generate_task_id("G")
    
    # Get target chats
    await send_log(f"📡 <b>GCast</b> <code>{task_id}</code>\n🔍 Scanning target chats...", client=client)
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
    
    await send_log(
        f"📡 <b>GCast Started</b> <code>{task_id}</code>\n"
        f"{'━' * 18}\n"
        f"👤 <b>Account:</b> {account_name}\n"
        f"🎯 <b>Targets:</b> {len(targets)} chats\n"
        f"📝 <b>Messages:</b> {len(all_messages)} items ({len(text_list)} text, {len(media_list)} media)\n"
        f"⏱ <b>Delay/Chat:</b> {settings['delay_per_chat']}s\n"
        f"🔀 <b>Random:</b> {'ON' if settings['random_text'] else 'OFF'}\n"
        f"🔁 <b>Recurring:</b> {'ON' if settings['recurring'] else 'OFF'}\n"
        f"📋 <b>Chat Filter:</b> {_filter_label(settings['chat_filter'])}\n"
        f"👑 <b>Admin Filter:</b> {_filter_label(settings['admin_filter'])}\n"
        f"{'━' * 18}",
        client=client
    )
    
    try:
        msg_idx = 0
        for i, (cid, title) in enumerate(targets):
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
                        logger.info(f"[GCast] Smart Purge completed for {title}: {purge_count} deleted")
                        # Log purge activity to group log
                        await send_log(
                            f"🧹 <b>Smart Purge</b> <code>{task_id}</code>\n"
                            f"Chat: {html.escape(title[:30])}\n"
                            f"Deleted: {purge_stats['deleted']} messages\n"
                            f"Errors: {purge_stats['errors']}",
                            client=client
                        )
                except Exception as e:
                    logger.error(f"[GCast] Smart Purge error for {title}: {e}")
                    await send_log(
                        f"⚠️ <b>Smart Purge Error</b> <code>{task_id}</code>\n"
                        f"Chat: {html.escape(title[:30])}\n"
                        f"Error: {str(e)[:100]}",
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
                
                # Auto React (if enabled)
                react_success = False
                if settings.get('auto_react', False) and sent_msg:
                    try:
                        react_delay = settings.get('react_delay', 4)
                        if react_delay > 0:
                            await asyncio.sleep(react_delay)
                        
                        react_emoji = settings.get('react_emoji', '👍')
                        await client.send_reaction(cid, sent_msg.id, react_emoji)
                        task_state["react_count"] += 1
                        react_success = True
                        logger.info(f"[GCast] Reacted to message in {title} with {react_emoji}")
                    except Exception as e:
                        logger.error(f"[GCast] React error in {cid}: {e}")
                        react_success = False
                
                # Detailed Notification (if enabled)
                if settings.get('notify_logs', True):
                    await send_detailed_log(
                        user_id=user_id,
                        chat_id=cid,
                        chat_title=title,
                        message_type=message_type,
                        content_preview=content_preview,
                        success=True,
                        error_reason=None,
                        purge_count=purge_count,
                        react_success=react_success,
                        client=client,
                        sent_message_id=sent_msg.id if sent_msg else None
                    )
                
                # Self-Destruct (if enabled)
                if settings.get("self_destruct", False) and sent_msg:
                    async def delayed_delete(c: Client, cid: int, mid: int, delay: int):
                        await asyncio.sleep(delay)
                        try:
                            await c.delete_messages(cid, mid)
                        except Exception:
                            pass
                    
                    asyncio.create_task(delayed_delete(
                        client, cid, sent_msg.id, settings.get("self_destruct_delay", 30)
                    ))
                
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
        
        # Broadcast completed
        task_state["running"] = False
        sent = task_state["sent_count"]
        errs = task_state["errors"]
        elapsed = int(time.time() - task_state["started_at"])
        mins, secs = divmod(elapsed, 60)
        
        # Calculate success rate
        success_rate = (sent / len(targets) * 100) if len(targets) > 0 else 0
        
        await send_log(
            f"✅ <b>GCast Completed</b> <code>{task_id}</code>\n"
            f"{'━' * 18}\n"
            f"👤 <b>Account:</b> {account_name}\n"
            f"📊 <b>Statistics:</b>\n"
            f"  • Sent: <b>{sent}/{len(targets)}</b> ({success_rate:.1f}%)\n"
            f"  • Failed: <b>{errs}</b> chats\n"
            f"  • Reacted: <b>{task_state.get('react_count', 0)}</b> messages\n"
            f"  • Duration: <b>{mins}m {secs}s</b>\n"
            f"⏱ <b>Delay/Chat:</b> {settings['delay_per_chat']}s\n"
            f"📝 <b>Messages Used:</b> {len(all_messages)} items ({len(text_list)} text, {len(media_list)} media)\n"
            f"{'━' * 18}",
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
            await send_log(
                f"🔁 <b>GCast Recurring</b> <code>{task_id}</code>\n"
                f"Restarting in 10 seconds...", client=client
            )
            await asyncio.sleep(10)
            # Create new task for the next cycle
            new_task = asyncio.create_task(broadcast_loop(client, user_id))
            GCAST_TASKS[user_id] = {**task_state, "asyncio_task": new_task, "running": True}
    
    except asyncio.CancelledError:
        await send_log(
            f"🛑 <b>GCast Cancelled</b> <code>{task_id}</code>\n"
            f"Sent: {task_state['sent_count']}/{len(targets)}",
            client=client
        )
    except Exception as e:
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
        if action in ["msgpreview", "msgdelconf", "msgdel", "msgsetfixed"]:
            # Format: pgc_action_type_uid_index
            # Example: pgc_msgpreview_text_7844837037_0
            if len(parts) >= 5:
                uid = int(parts[3])  # UID is always at parts[3] for these actions
        elif action in ["bldel"]:
            # Format: pgc_bldel_uid_index
            # Example: pgc_bldel_7844837037_0
            if len(parts) >= 4:
                uid = int(parts[2])  # UID is at parts[2]
        elif len(parts) >= 5 and parts[-2] == "page":
            # Format: pgc_action_uid_page_N
            # Example: pgc_info_7844837037_page_2
            uid = int(parts[2])  # UID is always at parts[2] for pagination
        else:
            # Standard format: pgc_action_uid or pgc_action_subaction_uid
            # Example: pgc_backmain_7844837037 or pgc_sp_toggle_7844837037
            # UID is always the last numeric part
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
        # Cycle: all → groups → personal → all
        cycle = {"all": "groups", "groups": "personal", "personal": "all"}
        s["chat_filter"] = cycle.get(s["chat_filter"], "all")
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
        try:
            uid = int(parts[3])
        except (ValueError, IndexError):
            return
        s = get_settings(uid)
        if direction == "dec":
            s["delay_per_chat"] = max(2, s["delay_per_chat"] - 2)
        elif direction == "inc":
            s["delay_per_chat"] = s["delay_per_chat"] + 2
        save_settings(uid, s)
        text = build_dashboard_text(uid)
        kb = build_dashboard_kb(uid)
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        await safe_cb_answer(cb, f"Delay: {s['delay_per_chat']}s", show_alert=False)
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
        s["recurring"] = not s["recurring"]
        save_settings(uid, s)
        text = build_dashboard_text(uid)
        kb = build_dashboard_kb(uid)
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        await safe_cb_answer(cb, f"Recurring: {'ON' if s['recurring'] else 'OFF'}", show_alert=False)
        return
    
    elif action == "notiftoggle":
        s["notify_logs"] = not s.get("notify_logs", True)
        save_settings(uid, s)
        text = build_dashboard_text(uid)
        kb = build_dashboard_kb(uid)
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        await safe_cb_answer(cb, f"Notif Logs: {'ON' if s['notify_logs'] else 'OFF'}", show_alert=False)
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
        kb = build_dashboard_kb(uid)
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
        kb = build_dashboard_kb(uid)
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        await safe_cb_answer(cb, f"SD Delay: {s['self_destruct_delay']}s", show_alert=False)
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
            nav_buttons.append(InlineKeyboardButton("◀️ Prev", callback_data=f"pgc_info_{uid}_page_{page-1}"))
        if page < 3:  # ✅ FIX: We have 4 pages (0, 1, 2, 3)
            nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"pgc_info_{uid}_page_{page+1}"))
        
        kb_rows = []
        if nav_buttons:
            kb_rows.append(nav_buttons)
        kb_rows.append([InlineKeyboardButton("📋 Show CMD", callback_data=f"pgc_showcmd_{uid}")])
        kb_rows.append([InlineKeyboardButton("⬅️ Back", callback_data=f"pgc_backmain_{uid}")])
        
        kb = InlineKeyboardMarkup(kb_rows)
        success = await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        if success:
            await safe_cb_answer(cb, f"Info menu (Page {page+1}/4).", show_alert=False)
        return
    
    elif action == "showcmd":
        # Show command list
        text = build_showcmd_text()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data=f"pgc_info_{uid}")],
        ])
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        await safe_cb_answer(cb, "Command list.", show_alert=False)
        return
    
    elif action == "help":
        # Deprecated - redirect to info
        text = build_info_text()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("� Show CMD", callback_data=f"pgc_showcmd_{uid}")],
            [InlineKeyboardButton("⬅️ Back", callback_data=f"pgc_backmain_{uid}")],
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
                InlineKeyboardButton("✅ Yes, Start!", callback_data=f"pgc_startyes_{uid}"),
                InlineKeyboardButton("❌ Cancel", callback_data=f"pgc_backmain_{uid}"),
            ]
        ])
        text = (
            f"⚠️ <b>Confirm Start GCast?</b>\n"
            f"{'━' * 18}\n"
            f"Chat Filter: {_filter_label(s['chat_filter'])}\n"
            f"Admin Filter: {_filter_label(s['admin_filter'])}\n"
            f"Messages: {total_messages} items ({len(s.get('text_list', []))} text, {len(s.get('media_list', []))} media)\n"
            f"Delay: {s['delay_per_chat']}s/chat\n"
            f"Random: {'ON' if s['random_text'] else 'OFF'}\n"
            f"Recurring: {'ON' if s['recurring'] else 'OFF'}"
            f"{smart_purge_text}"
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
        if not broadcast_client and Altruix.clients:
            broadcast_client = Altruix.clients[0]
        if not broadcast_client:
            await safe_cb_answer(cb, "❌ No userbot client available.", show_alert=True)
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
        text = build_msglist_text(uid)
        kb = build_msglist_kb(uid)
        success = await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        if success:
            await safe_cb_answer(cb, "Message list menu.", show_alert=False)
        return
    
    elif action == "addtext":
        # Set state to wait for user text input
        msg_id = cb.message.id if cb.message else None
        GCAST_TEXT_INPUT_STATE[uid] = {"action": "add", "msg_id": msg_id}
        
        # Send log message for user to reply to
        log_msg = await send_log(
            f"📝 <b>Add Text to GCast</b>\n\n"
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
            await safe_cb_answer(cb, "📝 Reply to the message in LOG chat with your broadcast text.", show_alert=True)
        else:
            await safe_cb_answer(cb, "❌ Failed to send prompt. Please try again.", show_alert=True)
        return
    
    elif action == "addmedia":
        # Set state to wait for user media input
        msg_id = cb.message.id if cb.message else None
        GCAST_MEDIA_INPUT_STATE[uid] = {"action": "add", "msg_id": msg_id}
        
        # Send log message for user to reply to
        log_msg = await send_log(
            f"🎬 <b>Add Media to GCast</b>\n\n"
            f"Reply to this message with media you want to add.\n\n"
            f"<b>Supported Media Types:</b>\n"
            f"• 🖼 Photo\n"
            f"• 🎬 Video\n"
            f"• 🎵 Audio\n"
            f"• 🎤 Voice\n"
            f"• 📄 Document\n"
            f"• 🎨 Sticker\n"
            f"• 🎞 Animation/GIF\n"
            f"• ⏺ Video Note\n\n"
            f"<i>You can add a caption with HTML/Markdown format.</i>",
            client=None
        )
        
        if log_msg:
            await safe_cb_answer(cb, "🎬 Reply to the message in LOG chat with your media.", show_alert=True)
        else:
            await safe_cb_answer(cb, "❌ Failed to send prompt. Please try again.", show_alert=True)
        return
    
    elif action == "msgdel":
        # pgc_msgdel_text/media_uid_index
        if len(parts) < 5:
            return
        msg_type = parts[2]  # "text" or "media"
        try:
            idx = int(parts[4])
        except (ValueError, IndexError):
            return
        
        s = get_settings(uid)
        if msg_type == "text":
            if 0 <= idx < len(s.get("text_list", [])):
                removed = s["text_list"].pop(idx)
                save_settings(uid, s)
                content = removed.get("content", "") if isinstance(removed, dict) else str(removed)
                await safe_cb_answer(cb, f"🗑 Removed text #{idx+1}.", show_alert=True)
                await send_log(f"🗑 <b>GCast Text Removed</b> #{idx+1}: {html.escape(content[:50])}", client=None)
            else:
                await safe_cb_answer(cb, "Invalid index.", show_alert=True)
        elif msg_type == "media":
            if 0 <= idx < len(s.get("media_list", [])):
                removed = s["media_list"].pop(idx)
                save_settings(uid, s)
                media_type = removed.get("type", "unknown")
                await safe_cb_answer(cb, f"🗑 Removed media #{idx+1}.", show_alert=True)
                await send_log(f"🗑 <b>GCast Media Removed</b> #{idx+1}: {media_type}", client=None)
            else:
                await safe_cb_answer(cb, "Invalid index.", show_alert=True)
        
        text = build_msglist_text(uid)
        kb = build_msglist_kb(uid)
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        return
    
    elif action == "msgdelconf":
        # ✅ NEW: Confirmation before delete individual message
        # pgc_msgdelconf_text/media_uid_index
        if len(parts) < 5:
            return
        msg_type = parts[2]  # "text" or "media"
        try:
            idx = int(parts[4])
        except (ValueError, IndexError):
            return
        
        s = get_settings(uid)
        if msg_type == "text":
            if 0 <= idx < len(s.get("text_list", [])):
                item = s["text_list"][idx]
                content = item.get("content", "") if isinstance(item, dict) else str(item)
                preview = html.escape(content[:100]) + ("..." if len(content) > 100 else "")
                kb = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Yes, Delete", callback_data=f"pgc_msgdel_text_{uid}_{idx}"),
                        InlineKeyboardButton("❌ Cancel", callback_data=f"pgc_msgmenu_{uid}"),
                    ]
                ])
                await safe_edit_message(cb, f"⚠️ <b>Delete Text Message #{idx+1}?</b>\n\n{preview}", reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            else:
                await safe_cb_answer(cb, "Invalid index.", show_alert=True)
        elif msg_type == "media":
            if 0 <= idx < len(s.get("media_list", [])):
                item = s["media_list"][idx]
                media_type = item.get("type", "unknown")
                caption = item.get("caption", "")
                cap_preview = html.escape(caption[:100]) if caption else "<i>no caption</i>"
                kb = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Yes, Delete", callback_data=f"pgc_msgdel_media_{uid}_{idx}"),
                        InlineKeyboardButton("❌ Cancel", callback_data=f"pgc_msgmenu_{uid}"),
                    ]
                ])
                await safe_edit_message(cb, f"⚠️ <b>Delete Media Message #{idx+1}?</b>\n\nType: {media_type}\nCaption: {cap_preview}", reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            else:
                await safe_cb_answer(cb, "Invalid index.", show_alert=True)
        await safe_cb_answer(cb, "Confirm delete.", show_alert=False)
        return
    
    elif action == "msgpreview":
        # ✅ NEW: Preview message content
        # pgc_msgpreview_text/media_uid_index
        if len(parts) < 5:
            return
        msg_type = parts[2]  # "text" or "media"
        try:
            idx = int(parts[4])
        except (ValueError, IndexError):
            return
        
        s = get_settings(uid)
        if msg_type == "text":
            if 0 <= idx < len(s.get("text_list", [])):
                item = s["text_list"][idx]
                content = item.get("content", "") if isinstance(item, dict) else str(item)
                parse_mode_str = item.get("parse_mode", "html") if isinstance(item, dict) else "html"
                
                # Send preview to LOG chat
                await send_log(
                    f"👁 <b>Preview Text Message #{idx+1}</b>\n"
                    f"Parse Mode: {parse_mode_str}\n"
                    f"Length: {len(content)} chars\n"
                    f"{'━' * 20}\n\n{content}",
                    client=None
                )
                await safe_cb_answer(cb, f"✅ Preview sent to LOG chat.", show_alert=True)
            else:
                await safe_cb_answer(cb, "Invalid index.", show_alert=True)
        elif msg_type == "media":
            if 0 <= idx < len(s.get("media_list", [])):
                item = s["media_list"][idx]
                media_type = item.get("type", "unknown")
                file_id = item.get("file_id", "")
                caption = item.get("caption", "")
                
                # Send media preview to LOG chat using userbot client (not bot)
                # because file_id from userbot cannot be used by bot assistant
                try:
                    # Find the userbot client for this user
                    userbot_client = None
                    for cl in Altruix.clients:
                        if hasattr(cl, 'me') and cl.me and cl.me.id == uid:
                            userbot_client = cl
                            break
                    
                    if not userbot_client:
                        await safe_cb_answer(cb, "❌ Userbot client not found.", show_alert=True)
                        return
                    
                    preview_caption = f"👁 <b>Preview Media #{idx+1}</b>\nType: {media_type}\n{'━' * 20}\n\n{caption}"
                    
                    # Use userbot client to send media (file_id is from userbot)
                    if media_type == "photo":
                        await userbot_client.send_photo(LOG_CHAT_ID, file_id, caption=preview_caption, parse_mode=enums.ParseMode.HTML)
                    elif media_type == "video":
                        await userbot_client.send_video(LOG_CHAT_ID, file_id, caption=preview_caption, parse_mode=enums.ParseMode.HTML)
                    elif media_type == "audio":
                        await userbot_client.send_audio(LOG_CHAT_ID, file_id, caption=preview_caption, parse_mode=enums.ParseMode.HTML)
                    elif media_type == "voice":
                        await userbot_client.send_voice(LOG_CHAT_ID, file_id, caption=preview_caption, parse_mode=enums.ParseMode.HTML)
                    elif media_type == "document":
                        await userbot_client.send_document(LOG_CHAT_ID, file_id, caption=preview_caption, parse_mode=enums.ParseMode.HTML)
                    elif media_type == "sticker":
                        await userbot_client.send_sticker(LOG_CHAT_ID, file_id)
                        await send_log(preview_caption, client=userbot_client)
                    elif media_type == "animation":
                        await userbot_client.send_animation(LOG_CHAT_ID, file_id, caption=preview_caption, parse_mode=enums.ParseMode.HTML)
                    elif media_type == "video_note":
                        await userbot_client.send_video_note(LOG_CHAT_ID, file_id)
                        await send_log(preview_caption, client=userbot_client)
                    else:
                        await send_log(f"👁 <b>Preview Media #{idx+1}</b>\nType: {media_type}\nCaption: {caption}", client=userbot_client)
                    
                    await safe_cb_answer(cb, f"✅ Preview sent to LOG chat.", show_alert=True)
                except Exception as e:
                    logger.error(f"Preview media error: {e}")
                    await safe_cb_answer(cb, f"❌ Preview failed: {str(e)[:50]}", show_alert=True)
            else:
                await safe_cb_answer(cb, "Invalid index.", show_alert=True)
        return
    
    elif action == "msgsetfixed" or action == "setfixed":
        # ✅ NEW: Set fixed message mode
        # pgc_msgsetfixed_text/media_uid_index OR pgc_setfixed_uid
        if action == "setfixed":
            # Show menu to select which message to fix
            s = get_settings(uid)
            text_list = s.get("text_list", [])
            media_list = s.get("media_list", [])
            
            if not text_list and not media_list:
                await safe_cb_answer(cb, "❌ No messages to set as fixed.", show_alert=True)
                return
            
            await safe_cb_answer(cb, "👆 Click on a message to set it as fixed.", show_alert=True)
            return
        
        # Set specific message as fixed
        if len(parts) < 5:
            return
        msg_type = parts[2]  # "text" or "media"
        try:
            idx = int(parts[4])
        except (ValueError, IndexError):
            return
        
        s = get_settings(uid)
        text_list = s.get("text_list", [])
        media_list = s.get("media_list", [])
        
        # Calculate absolute index
        if msg_type == "text":
            if 0 <= idx < len(text_list):
                absolute_idx = idx
            else:
                await safe_cb_answer(cb, "Invalid index.", show_alert=True)
                return
        elif msg_type == "media":
            if 0 <= idx < len(media_list):
                absolute_idx = len(text_list) + idx
            else:
                await safe_cb_answer(cb, "Invalid index.", show_alert=True)
                return
        
        # Check if already fixed
        current_fixed = s.get("fixed_message_index", None)
        if current_fixed == absolute_idx:
            # Unset fixed
            s["fixed_message_index"] = None
            save_settings(uid, s)
            await safe_cb_answer(cb, f"📌 Unfixed message #{absolute_idx+1}. Back to Sequential mode.", show_alert=True)
            await send_log(f"📌 <b>GCast Fixed Message Unset</b>\nBack to Sequential mode", client=None)
        else:
            # Set as fixed
            s["fixed_message_index"] = absolute_idx
            save_settings(uid, s)
            await safe_cb_answer(cb, f"📌 Set message #{absolute_idx+1} as fixed!", show_alert=True)
            await send_log(f"📌 <b>GCast Fixed Message Set</b>\nMessage #{absolute_idx+1} will always be sent", client=None)
        
        text = build_msglist_text(uid)
        kb = build_msglist_kb(uid)
        await safe_edit_message(cb, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        return
    
    elif action == "msgclearconf":
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Yes, Clear All", callback_data=f"pgc_msgclearyes_{uid}"),
                InlineKeyboardButton("❌ Cancel", callback_data=f"pgc_msgmenu_{uid}"),
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
                InlineKeyboardButton("✅ Yes, Clear All", callback_data=f"pgc_textclearyes_{uid}"),
                InlineKeyboardButton("❌ Cancel", callback_data=f"pgc_textmenu_{uid}"),
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
                InlineKeyboardButton("✅ Yes, Clear All", callback_data=f"pgc_blclearyes_{uid}"),
                InlineKeyboardButton("❌ Cancel", callback_data=f"pgc_blmenu_{uid}"),
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
                [InlineKeyboardButton("⬅️ Back", callback_data=f"pgc_backmain_{uid}")],
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
            for i, (cid, title) in enumerate(page_targets, start=start_idx + 1):
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
                nav_buttons.append(InlineKeyboardButton("◀️ Prev", callback_data=f"pgc_listchats_{uid}_page_{page-1}"))
            if page < total_pages - 1:
                nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"pgc_listchats_{uid}_page_{page+1}"))
            
            kb_rows = []
            if nav_buttons:
                kb_rows.append(nav_buttons)
            kb_rows.append([InlineKeyboardButton("⬅️ Back", callback_data=f"pgc_backmain_{uid}")])
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
    user_in_state = m.from_user.id in GCAST_TEXT_INPUT_STATE or m.from_user.id in GCAST_MEDIA_INPUT_STATE or m.from_user.id in GCAST_BL_INPUT_STATE
    
    if not is_auth:
        if user_in_state:
            # If they are in state but somehow no longer auth (revoked sudo?), tell them.
            await m.reply(Altruix.get_string("ACCESS_DENIED"))
        return # SILENT for everyone else
    
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
                    if not uc and Altruix.clients:
                        uc = Altruix.clients[0]
                    
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
        logger.error(f"GCast Inline Handler Error: {e}")


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
                    reply_to_message_id=message.reply_to_message.id if message.reply_to_message else None
                )
                if sent:
                    await message.delete_if_self()
                    logger.info(f"[gcast_dashboard_cmd] Dashboard opened via inline mode")
                    return
        except Exception as e:
            logger.warning(f"[gcast_dashboard_cmd] Inline mode failed: {e}, falling back to direct message")
    
    # Fallback to direct bot message (only works if bot is in the chat)
    try:
        text = build_dashboard_text(user_id)
        kb = build_dashboard_kb(user_id)
        await bot.send_message(message.chat.id, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        await message.delete_if_self()
        logger.info(f"[gcast_dashboard_cmd] Dashboard opened via direct message")
    except Exception as e:
        logger.error(f"[gcast_dashboard_cmd] Error sending dashboard: {e}")
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
        await message.edit("⚠️ A broadcast is already running. Use <code>.gcaststop</code> first.")
        return
    s = get_settings(user_id)
    if not s["text_list"]:
        await message.edit("❌ Text list is empty. Add texts via <code>.gcast</code> dashboard first.")
        return
    await message.edit("🟢 Starting Global BroadCast...")
    asyncio.create_task(broadcast_loop(client, user_id))

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
        await message.edit("⚫ No active broadcast.")
        return
    task["running"] = False
    task["pause_event"].set()
    atask = task.get("asyncio_task")
    if atask and not atask.done():
        atask.cancel()
    await message.edit(f"🔴 GCast <code>{task.get('task_id', '?')}</code> stopped.")

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
        await message.edit("⚫ No active broadcast.")
        return
    task["pause_event"].clear()
    await message.edit(f"⏸ GCast <code>{task.get('task_id', '?')}</code> paused.")

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
        await message.edit("⚫ No active broadcast.")
        return
    task["pause_event"].set()
    await message.edit(f"▶️ GCast <code>{task.get('task_id', '?')}</code> resumed.")

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
    await message.edit(text)

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
    await message.edit(f"✅ Chat <code>{chat_id}</code> has been <b>{action}</b> GCast Blacklist.")

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
        await message.edit("📋 <b>GCast Blacklist</b>\n\n<i>Blacklist is empty.</i>")
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
    await message.edit(text)

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
        await message.edit("❌ <b>Usage:</b> <code>.gcastbldel &lt;chat_id&gt;</code>\n\nExample: <code>.gcastbldel -100123456789</code>")
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
                await message.edit(f"❌ Could not resolve: {input_val}\nError: {e}")
                return
        else:
            await message.edit("❌ Send a chat ID (number) or @username.\n\nExample: <code>.gcastbldel -100123456789</code>")
            return
    except Exception as e:
        await message.edit(f"❌ Invalid input: {e}")
        return
    
    if chat_id:
        s = get_settings(user_id)
        if chat_id in s["blacklist"]:
            s["blacklist"].remove(chat_id)
            save_settings(user_id, s)
            await message.edit(f"✅ Chat <code>{chat_id}</code> has been <b>REMOVED FROM</b> GCast Blacklist.")
        else:
            await message.edit(f"⚠️ Chat <code>{chat_id}</code> is not in the blacklist.")

