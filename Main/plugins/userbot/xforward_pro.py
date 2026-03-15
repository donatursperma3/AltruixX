# xforward_pro.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
# All rights reserved.
#
# Advanced Forwarder Plugin — Forward messages between chats with
# live/batch modes, media filters, bypass protected, and interactive
# inline keyboard dashboard.

import os
import json
import asyncio
import logging
import html
import time
import re
import random
# import aiosqlite  <-- Moved to functions for lazy loading
from pathlib import Path
from datetime import datetime
from pyrogram import Client, filters, enums
from pyrogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    CallbackQuery, Message as RawMessage,
)
from pyrogram.errors import FloodWait, ChatWriteForbidden, ChannelInvalid, ChannelPrivate
from Main import Altruix
from Main.core.types.message import Message as AltruixMessage
from Main.core.decorators import iuser_check, log_errors
from Main.utils.file_helpers import get_db_path, get_user_button_style

# Plugin Metadata
plugin_name = f"{os.path.basename(__file__)}"
__plugin_name__ = plugin_name if plugin_name else "xforward_pro"
PLUGIN_VERSION = "1.0.191"

logger = logging.getLogger("altruix.xforward_pro")
logger.setLevel(logging.INFO)

LOG_CHAT_ID = int(os.getenv("LOG_CHAT_ID", 0))

# ==================== ACTIVE TASK TRACKING ====================

# In-memory live forwarder handlers: {task_id: handler_info}
FWD_LIVE_TASKS = {}

# Batch control states: {task_id: "running"|"paused"|"stopped"}
FWD_BATCH_CONTROL = {}

# ==================== INTERACTIVE STATE ====================
FPRO_ADD_TASK_STATE = {} # {user_id: {"src": id, "tgt": id, "mode": str, "step": int}}
FPRO_WAITING_INPUT = {}  # {user_id: {"action": str, "task_id": int, "mid": int}}


# ==================== DATABASE LAYER (aiosqlite) ====================

DB_PATH = get_db_path("forward_pro.db")
_db_lock = asyncio.Lock()
_db_initialized = False


async def _safe_json_loads(data, default=None):
    """Safely load JSON data with fallback."""
    if default is None: default = {}
    if not data: return default
    try:
        if isinstance(data, (dict, list)): return data
        return json.loads(data)
    except:
        return default


async def init_db():
    """Initialize the SQLite database and create tables if needed."""
    global _db_initialized
    if _db_initialized:
        return
    async with _db_lock:
        if _db_initialized:
            return
        try:
            Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
            import aiosqlite
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS fwd_tasks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        source_id INTEGER NOT NULL,
                        target_id INTEGER NOT NULL,
                        is_active INTEGER DEFAULT 0,
                        mode TEXT DEFAULT 'live',
                        filters TEXT DEFAULT '{}',
                        bypass_protected INTEGER DEFAULT 0,
                        watermark_text TEXT,
                        is_watermark INTEGER DEFAULT 0,
                        is_translate INTEGER DEFAULT 0,
                        ad_keywords TEXT DEFAULT '[]',
                        count_success INTEGER DEFAULT 0,
                        count_failed INTEGER DEFAULT 0,
                        created_at TEXT DEFAULT (datetime('now','localtime')),
                        updated_at TEXT DEFAULT (datetime('now','localtime'))
                    )
                """)
                
                # Schema Migration for Phase 3
                cursor = await db.execute("PRAGMA table_info(fwd_tasks)")
                columns = [row[1] for row in await cursor.fetchall()]
                if "watermark_text" not in columns:
                    await db.execute("ALTER TABLE fwd_tasks ADD COLUMN watermark_text TEXT")
                if "is_watermark" not in columns:
                    await db.execute("ALTER TABLE fwd_tasks ADD COLUMN is_watermark INTEGER DEFAULT 0")
                if "is_translate" not in columns:
                    await db.execute("ALTER TABLE fwd_tasks ADD COLUMN is_translate INTEGER DEFAULT 0")
                if "ad_keywords" not in columns:
                    await db.execute("ALTER TABLE fwd_tasks ADD COLUMN ad_keywords TEXT DEFAULT '[]'")
                if "count_success" not in columns:
                    await db.execute("ALTER TABLE fwd_tasks ADD COLUMN count_success INTEGER DEFAULT 0")
                if "count_failed" not in columns:
                    await db.execute("ALTER TABLE fwd_tasks ADD COLUMN count_failed INTEGER DEFAULT 0")
                if "batch_delay" not in columns:
                    await db.execute("ALTER TABLE fwd_tasks ADD COLUMN batch_delay REAL DEFAULT 1.5")
                if "batch_order" not in columns:
                    await db.execute("ALTER TABLE fwd_tasks ADD COLUMN batch_order TEXT DEFAULT 'oldest'")
                if "clean_links" not in columns:
                    await db.execute("ALTER TABLE fwd_tasks ADD COLUMN clean_links INTEGER DEFAULT 0")
                if "clean_usernames" not in columns:
                    await db.execute("ALTER TABLE fwd_tasks ADD COLUMN clean_usernames INTEGER DEFAULT 0")
                if "is_ads_filter" not in columns:
                    await db.execute("ALTER TABLE fwd_tasks ADD COLUMN is_ads_filter INTEGER DEFAULT 0")
                if "use_regex_pro" not in columns:
                    await db.execute("ALTER TABLE fwd_tasks ADD COLUMN use_regex_pro INTEGER DEFAULT 0")
                if "custom_regex" not in columns:
                    await db.execute("ALTER TABLE fwd_tasks ADD COLUMN custom_regex TEXT DEFAULT '[]'")
                if "tr_lang" not in columns:
                    await db.execute("ALTER TABLE fwd_tasks ADD COLUMN tr_lang TEXT DEFAULT 'id'")
                if "forward_as_copy" not in columns:
                    await db.execute("ALTER TABLE fwd_tasks ADD COLUMN forward_as_copy INTEGER DEFAULT 1")

                await db.execute("""
                    CREATE TABLE IF NOT EXISTS fwd_global_settings (
                        user_id INTEGER PRIMARY KEY,
                        default_delay REAL DEFAULT 1.5,
                        log_channel INTEGER DEFAULT 0,
                        default_is_translate INTEGER DEFAULT 0,
                        default_is_watermark INTEGER DEFAULT 0,
                        default_clean_links INTEGER DEFAULT 0,
                        default_clean_usernames INTEGER DEFAULT 0,
                        default_is_ads_filter INTEGER DEFAULT 0,
                        default_bypass_protected INTEGER DEFAULT 0,
                        default_ad_keywords TEXT DEFAULT '[]',
                        default_watermark_text TEXT DEFAULT 'Altruix',
                        default_filters TEXT DEFAULT '{}',
                        default_batch_order TEXT DEFAULT 'oldest',
                        default_use_regex_pro INTEGER DEFAULT 0,
                        default_custom_regex TEXT DEFAULT '[]',
                        default_tr_lang TEXT DEFAULT 'id',
                        default_forward_as_copy INTEGER DEFAULT 1,
                        updated_at TEXT DEFAULT (datetime('now','localtime'))
                    )
                """)
                
                # Check for new columns in global settings
                cursor = await db.execute("PRAGMA table_info(fwd_global_settings)")
                g_columns = [row[1] for row in await cursor.fetchall()]

                # Migration checks for all global settings columns to ensure backward compatibility
                if "default_tr_lang" not in g_columns:
                    await db.execute("ALTER TABLE fwd_global_settings ADD COLUMN default_tr_lang TEXT DEFAULT 'id'")
                if "default_forward_as_copy" not in g_columns:
                    await db.execute("ALTER TABLE fwd_global_settings ADD COLUMN default_forward_as_copy INTEGER DEFAULT 1")
                if "log_channel" not in g_columns:
                    await db.execute("ALTER TABLE fwd_global_settings ADD COLUMN log_channel INTEGER DEFAULT 0")
                if "default_is_translate" not in g_columns:
                    await db.execute("ALTER TABLE fwd_global_settings ADD COLUMN default_is_translate INTEGER DEFAULT 0")
                if "default_is_watermark" not in g_columns:
                    await db.execute("ALTER TABLE fwd_global_settings ADD COLUMN default_is_watermark INTEGER DEFAULT 0")
                if "default_clean_links" not in g_columns:
                    await db.execute("ALTER TABLE fwd_global_settings ADD COLUMN default_clean_links INTEGER DEFAULT 0")
                if "default_clean_usernames" not in g_columns:
                    await db.execute("ALTER TABLE fwd_global_settings ADD COLUMN default_clean_usernames INTEGER DEFAULT 0")
                if "default_is_ads_filter" not in g_columns:
                    await db.execute("ALTER TABLE fwd_global_settings ADD COLUMN default_is_ads_filter INTEGER DEFAULT 0")
                if "default_bypass_protected" not in g_columns:
                    await db.execute("ALTER TABLE fwd_global_settings ADD COLUMN default_bypass_protected INTEGER DEFAULT 0")
                if "default_ad_keywords" not in g_columns:
                    await db.execute("ALTER TABLE fwd_global_settings ADD COLUMN default_ad_keywords TEXT DEFAULT '[]'")
                if "default_watermark_text" not in g_columns:
                    await db.execute("ALTER TABLE fwd_global_settings ADD COLUMN default_watermark_text TEXT DEFAULT 'Altruix'")
                if "default_filters" not in g_columns:
                    await db.execute("ALTER TABLE fwd_global_settings ADD COLUMN default_filters TEXT DEFAULT '{}'")
                if "default_batch_order" not in g_columns:
                    await db.execute("ALTER TABLE fwd_global_settings ADD COLUMN default_batch_order TEXT DEFAULT 'oldest'")
                if "default_use_regex_pro" not in g_columns:
                    await db.execute("ALTER TABLE fwd_global_settings ADD COLUMN default_use_regex_pro INTEGER DEFAULT 0")
                if "default_custom_regex" not in g_columns:
                    await db.execute("ALTER TABLE fwd_global_settings ADD COLUMN default_custom_regex TEXT DEFAULT '[]'")
                
                await db.commit()
            _db_initialized = True
            logger.info("[ForwardPro] Database initialized successfully")
        except Exception as e:
            logger.error(f"[ForwardPro] Database init failed: {e}")


async def add_task(user_id: int, source_id: int, target_id: int, mode: str = "live") -> int:
    """Add a new forward task inheriting global defaults."""
    await init_db()
    import aiosqlite
    gs = await get_global_settings(user_id)
    
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """
                INSERT INTO fwd_tasks (
                    user_id, source_id, target_id, mode, is_active,
                    is_translate, is_watermark, clean_links, clean_usernames,
                    is_ads_filter, bypass_protected, batch_delay, ad_keywords,
                    filters, batch_order, use_regex_pro, custom_regex
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id, source_id, target_id, mode, 0,
                    gs.get("default_is_translate", 0),
                    gs.get("default_is_watermark", 0),
                    gs.get("default_clean_links", 0),
                    gs.get("default_clean_usernames", 0),
                    gs.get("default_is_ads_filter", 0),
                    gs.get("default_bypass_protected", 0),
                    gs.get("default_delay", 1.5),
                    gs.get("default_ad_keywords", "[]"),
                    gs.get("default_filters", "{}"),
                    gs.get("default_batch_order", "oldest"),
                    gs.get("default_use_regex_pro", 0),
                    gs.get("default_custom_regex", "[]")
                )
            )
            await db.commit()
            return cursor.lastrowid
    except Exception as e:
        logger.error(f"[ForwardPro] add_task failed: {e}")
        return -1


async def get_tasks(user_id: int) -> list:
    """Get all tasks for a user."""
    await init_db()
    import aiosqlite
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM fwd_tasks WHERE user_id = ? ORDER BY id ASC", (user_id,)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"[ForwardPro] get_tasks failed: {e}")
        return []


async def get_task(task_id: int) -> dict:
    """Get a single task by ID."""
    await init_db()
    import aiosqlite
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM fwd_tasks WHERE id = ?", (task_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"[ForwardPro] get_task failed: {e}")
        return None


async def update_task(task_id: int, **kwargs) -> bool:
    """Update specific fields of a task."""
    await init_db()
    import aiosqlite
    if not kwargs:
        return False
    try:
        set_parts = []
        values = []
        for k, v in kwargs.items():
            set_parts.append(f"{k} = ?")
            values.append(v)
        set_parts.append("updated_at = datetime('now','localtime')")
        values.append(task_id)
        query = f"UPDATE fwd_tasks SET {', '.join(set_parts)} WHERE id = ?"
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(query, values)
            await db.commit()
        return True
    except Exception as e:
        logger.error(f"[ForwardPro] update_task failed: {e}")
        return False


async def delete_task(task_id: int) -> bool:
    """Delete a task by ID."""
    await init_db()
    import aiosqlite
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM fwd_tasks WHERE id = ?", (task_id,))
            await db.commit()
        return True
    except Exception as e:
        logger.error(f"[ForwardPro] delete_task failed: {e}")
        return False


async def get_global_settings(user_id: int) -> dict:
    """Get global settings for a user."""
    await init_db()
    import aiosqlite
    defaults = {
        "user_id": user_id, 
        "default_delay": 1.5, 
        "log_channel": 0,
        "default_is_translate": 0,
        "default_is_watermark": 0,
        "default_clean_links": 0,
        "default_clean_usernames": 0,
        "default_is_ads_filter": 0,
        "default_bypass_protected": 0,
        "default_ad_keywords": "[]",
        "default_watermark_text": "Altruix",
        "default_filters": "{}",
        "default_batch_order": "oldest",
        "default_use_regex_pro": 0,
        "default_custom_regex": "[]"
    }
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM fwd_global_settings WHERE user_id = ?", (user_id,)
            )
            row = await cursor.fetchone()
            if row:
                return dict(row)
            # Insert defaults
            await db.execute(
                "INSERT INTO fwd_global_settings (user_id) VALUES (?)", (user_id,)
            )
            await db.commit()
            return defaults
    except Exception as e:
        logger.error(f"[ForwardPro] get_global_settings failed: {e}")
        return defaults


async def update_global_settings(user_id: int, **kwargs) -> bool:
    """Update global settings for a user."""
    await init_db()
    import aiosqlite
    if not kwargs:
        return False
    try:
        # Ensure row exists
        await get_global_settings(user_id)
        set_parts = []
        values = []
        for k, v in kwargs.items():
            set_parts.append(f"{k} = ?")
            values.append(v)
        set_parts.append("updated_at = datetime('now','localtime')")
        values.append(user_id)
        query = f"UPDATE fwd_global_settings SET {', '.join(set_parts)} WHERE user_id = ?"
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(query, values)
            await db.commit()
        return True
    except Exception as e:
        logger.error(f"[ForwardPro] update_global_settings failed: {e}")
        return False


# ==================== HELPER FUNCTIONS ====================

async def send_log(text: str, client=None, reply_markup=None, user_id: int = None):
    """Send a log message to the configured log channel (Global or Task) or LOG_CHAT_ID."""
    try:
        # 1. Resolve target channel
        target_id = LOG_CHAT_ID
        if user_id:
            gs = await get_global_settings(user_id)
            if gs.get("log_channel"):
                target_id = gs["log_channel"]
        
        if not target_id:
            return None

        # 2. Resolve bot assistant
        bot = None
        if client and hasattr(Altruix, 'bot_manager'):
            bot = Altruix.bot_manager.get_bot(client.me.id)
        if not bot:
            bot = Altruix.bot
            
        if bot:
            return await bot.send_message(target_id, text, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"[ForwardPro] send_log failed: {e}")
    return None


async def edit_log(log_msg, text: str, client=None, reply_markup=None):
    """Edit an existing log message. Returns the edited message or None."""
    if not log_msg:
        return None
    try:
        bot = None
        if client and hasattr(Altruix, 'bot_manager'):
            bot = Altruix.bot_manager.get_bot(client.me.id)
        if not bot:
            bot = Altruix.bot
        
        if bot:
            return await bot.edit_message_text(
                log_msg.chat.id, log_msg.id, text, reply_markup=reply_markup
            )
    except Exception as e:
        # MessageNotModified is harmless
        if "MESSAGE_NOT_MODIFIED" not in str(e).upper():
            logger.debug(f"[ForwardPro] edit_log failed: {e}")
    return None


async def safe_cb_answer(cb: CallbackQuery, text: str, show_alert: bool = True):
    """Answer callback query safely."""
    try:
        await cb.answer(text, show_alert=show_alert)
    except Exception:
        pass


async def resolve_chat_title(client, chat_id: int) -> str:
    """Resolve a chat ID to its title/name with type icons (👤/🤖/👥/📢)."""
    try:
        chat = await client.get_chat(chat_id)
        icon = "👤" # Private
        if chat.type == enums.ChatType.BOT:
            icon = "🤖"
        elif chat.type in (enums.ChatType.GROUP, enums.ChatType.SUPERGROUP):
            icon = "👥"
        elif chat.type == enums.ChatType.CHANNEL:
            icon = "📢"
        
        name = chat.title or chat.first_name or str(chat_id)
        return f"{icon} {name}"
    except Exception:
        return f"❓ {chat_id}"


async def get_chat_link(client: Client, chat_id: int) -> str:
    """Generate a shared link for a chat (username or private link)."""
    try:
        chat = await client.get_chat(chat_id)
        if chat.username:
            return f"https://t.me/{chat.username}"
        
        # Private chat format: -1001555 -> 1555
        cid_str = str(chat_id)
        if cid_str.startswith("-100"):
            clean_id = cid_str[4:]
            return f"https://t.me/c/{clean_id}/1"
            
        return "https://t.me"
    except Exception:
        return "https://t.me"


def _clean_caption(text: str, ad_keywords: list = None, clean_links: bool = True, clean_usernames: bool = True, use_regex_pro: bool = False, custom_regex: list = None) -> str:
    """Remove links, usernames, and ad keywords from text, plus custom Regex Pro patterns."""
    if not text:
        return ""
    
    # Remove http/https links
    if clean_links:
        text = re.sub(r'https?://\S+', '', text)
        
    # Remove usernames
    if clean_usernames:
        text = re.sub(r'@\w+', '', text)
    
    # Remove Ad Keywords
    if ad_keywords:
        for word in ad_keywords:
            text = re.sub(rf'(?i){re.escape(word)}', '', text)
    
    # ✅ Regex Pro Logic
    if use_regex_pro and custom_regex:
        for entry in custom_regex:
            if isinstance(entry, list) and len(entry) >= 2:
                pattern, replacement = entry[0], entry[1]
                try:
                    text = re.sub(pattern, replacement, text)
                except Exception as e:
                    logger.error(f"[ForwardPro] Regex Pro error for pattern '{pattern}': {e}")
            
    return text.strip()


async def _translate_text(text: str, dest: str = "id") -> str:
    """Translate text using googletrans."""
    if not text:
        return ""
    try:
        from googletrans import Translator
        translator = Translator()
        result = await asyncio.to_thread(translator.translate, text, dest=dest)
        return result.text
    except Exception as e:
        logger.error(f"[ForwardPro] translation failed: {e}")
        return text


async def _handle_fwd(client: Client, msg: RawMessage, target_id: int, bypass: bool = False, filters: dict = None, task_cfg: dict = None):
    """Core forwarding logic with filters, cleaning, bypass, watermark, and translation."""
    # 1. Check Filters
    msg_type = _get_message_type(msg)
    if filters and msg_type and not filters.get(msg_type, True):
        return False, "Filtered"

    # 2. Get Config
    ad_keywords = []
    is_translate = False
    is_watermark = False
    watermark_text = "Altruix"
    use_regex_pro = False
    custom_regex = []
    tid = task_cfg["id"] if task_cfg else None
    
    if task_cfg:
        try:
            ad_keywords = json.loads(task_cfg.get("ad_keywords", "[]"))
        except:
            ad_keywords = []
        is_translate = bool(task_cfg.get("is_translate"))
        is_watermark = bool(task_cfg.get("is_watermark"))
        watermark_text = task_cfg.get("watermark_text") or "Altruix"
        use_regex_pro = bool(task_cfg.get("use_regex_pro", 0))
        try:
            custom_regex = json.loads(task_cfg.get("custom_regex", "[]"))
        except:
            custom_regex = []

    # 3. Prepare Caption (Cleaned & Translated)
    clean_l = bool(task_cfg.get("clean_links", 0)) if task_cfg else True
    clean_u = bool(task_cfg.get("clean_usernames", 0)) if task_cfg else True
    is_ads_f = bool(task_cfg.get("is_ads_filter", 0)) if task_cfg else True
    
    raw_caption = msg.caption or msg.text if msg_type == "text" else msg.caption
    caption = _clean_caption(
        raw_caption, 
        ad_keywords if is_ads_f else None, 
        clean_links=clean_l, 
        clean_usernames=clean_u,
        use_regex_pro=use_regex_pro,
        custom_regex=custom_regex
    )
    
    if is_translate and caption:
        dest_lang = task_cfg.get("tr_lang", "id") if task_cfg else "id"
        caption = await _translate_text(caption, dest=dest_lang)
    
    # 4. Handle Bypass or Standard Forward
    as_copy = bool(task_cfg.get("forward_as_copy", 1)) if task_cfg else True
    
    try:
        # Priority 1: Watermark (always re-upload)
        if is_watermark:
            await _copy_protected_message(client, msg, target_id, clean_caption=caption, watermark=watermark_text)
            if tid: await update_task_stats(tid, success=True)
            return True, "Watermark/Re-upload Success"

        # Priority 2: Bypass ONLY for actually protected content
        if msg.has_protected_content:
            if bypass:
                await _copy_protected_message(client, msg, target_id, clean_caption=caption)
                if tid: await update_task_stats(tid, success=True)
                return True, "Bypass Protected Success"
            else:
                if tid: await update_task_stats(tid, success=False)
                return False, "Restricted content (Bypass OFF)"

        # Priority 3: Forward as Copy (CPY)
        if as_copy:
            result = await msg.copy(target_id, caption=caption if caption is not None else msg.caption)
            if result:
                if tid: await update_task_stats(tid, success=True)
                return True, "Copy Success (Hidden Sender)"
            else:
                if tid: await update_task_stats(tid, success=False)
                return False, "Copy returned empty result"

        # Priority 4: Standard Forward
        result = await msg.forward(target_id)
        if result:
            if tid: await update_task_stats(tid, success=True)
            return True, "Forward Success"
        else:
            if tid: await update_task_stats(tid, success=False)
            return False, "Forward returned empty result"

    except (ChatWriteForbidden, ChannelInvalid, ChannelPrivate) as e:
        if tid: await update_task_stats(tid, success=False)
        return False, f"Permission error: {e}"
    except Exception as e:
        if tid: await update_task_stats(tid, success=False)
        # Final Fallback to bypass if enabled and standard forward failed
        if bypass:
            # Fallback to bypass on error if enabled
            try:
                await _copy_protected_message(client, msg, target_id, clean_caption=caption)
                if tid: await update_task_stats(tid, success=True)
                return True, "Bypass Fallback Success"
            except Exception as e2:
                return False, f"Bypass fallback failed: {e2}"
        return False, str(e)


async def update_task_stats(task_id: int, success: bool = True):
    """Update task success/failed counts."""
    field = "count_success" if success else "count_failed"
    import aiosqlite
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(f"UPDATE fwd_tasks SET {field} = {field} + 1 WHERE id = ?", (task_id,))
            await db.commit()
    except Exception as e:
        logger.error(f"[ForwardPro] update_task_stats failed: {e}")


# ==================== ACTIVE TASK TRACKING ====================

# In-memory live forwarder handlers: {task_id: handler_info}
FWD_LIVE_TASKS = {}


# ==================== UI BUILDERS ====================

def build_main_menu_kb(user_id: int, gsettings: dict = None) -> InlineKeyboardMarkup:
    """Build the main menu keyboard with global toggles grid."""
    btn_style = get_user_button_style(user_id)
    if not gsettings:
        return InlineKeyboardMarkup([[InlineKeyboardButton("Loading...", callback_data="noop")]])
    
    gs = gsettings
    uid = user_id
    
    # Toggle labels
    tr_label = "🌍 TR: ON" if gs.get("default_is_translate") else "🌍 TR: OFF"
    wm_label = "🖼 WM: ON" if gs.get("default_is_watermark") else "🖼 WM: OFF"
    cpy_label = "📂 CPY: ON" if gs.get("default_forward_as_copy", 1) else "📂 CPY: OFF"
    lnk_label = "🔗 LNK: ON" if gs.get("default_clean_links") else "🔗 LNK: OFF"
    usr_label = "👤 USR: ON" if gs.get("default_clean_usernames") else "👤 USR: OFF"
    ads_label = "🚫 ADS: ON" if gs.get("default_is_ads_filter") else "🚫 ADS: OFF"
    bps_label = "🛡 BPS: ON" if gs.get("default_bypass_protected") else "🛡 BPS: OFF"
    
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📡 List Tasks", callback_data=f"fwd_list_{uid}", style=btn_style),
            InlineKeyboardButton("📊 General Stats", callback_data=f"fwd_stats_{uid}", style=btn_style)
        ],
        [
            InlineKeyboardButton("➕ Add Task (Step)", callback_data=f"fwd_add_start_{uid}", style=btn_style),
            InlineKeyboardButton("📖 Help", callback_data=f"fwd_help_0_{uid}", style=btn_style)
        ],
        [
            InlineKeyboardButton("🌍 Global Filter", callback_data=f"fwd_gfilter_{uid}", style=btn_style),
            InlineKeyboardButton("🛡 Global Adv Opts", callback_data=f"fwd_gadvopts_{uid}", style=btn_style)
        ],
        [
            InlineKeyboardButton("🧹 Global Ads", callback_data=f"fwd_gadsset_{uid}", style=btn_style),
            InlineKeyboardButton("🖼 Global WM", callback_data=f"fwd_gwmset_{uid}", style=btn_style)
        ],
        [
            InlineKeyboardButton(tr_label, callback_data=f"fwd_gtoggle_default_is_translate_{uid}", style=btn_style),
            InlineKeyboardButton(wm_label, callback_data=f"fwd_gtoggle_default_is_watermark_{uid}", style=btn_style),
            InlineKeyboardButton(cpy_label, callback_data=f"fwd_gtoggle_default_forward_as_copy_{uid}", style=btn_style)
        ],
        [
            InlineKeyboardButton(lnk_label, callback_data=f"fwd_gtoggle_default_clean_links_{uid}", style=btn_style),
            InlineKeyboardButton(usr_label, callback_data=f"fwd_gtoggle_default_clean_usernames_{uid}", style=btn_style)
        ],
        [
            InlineKeyboardButton(bps_label, callback_data=f"fwd_gtoggle_default_bypass_protected_{uid}", style=btn_style),
            InlineKeyboardButton(ads_label, callback_data=f"fwd_gtoggle_default_is_ads_filter_{uid}", style=btn_style)
        ],
        [
            InlineKeyboardButton("📢 Log Channel", callback_data=f"fwd_glog_{uid}", style=btn_style),
            InlineKeyboardButton("❌ Close Dashboard", callback_data=f"fwd_close_{uid}", style=btn_style)
        ]
    ])


async def build_main_menu_text(user_id: int, client=None) -> str:
    """Build the main dashboard text."""
    tasks = await get_tasks(user_id)
    gsettings = await get_global_settings(user_id)
    
    active_count = sum(1 for t in tasks if t.get("is_active"))
    total_count = len(tasks)
    live_count = sum(1 for t in tasks if t.get("mode") == "live" and t.get("is_active"))
    
    account_name = str(user_id)
    if client and client.me:
        first = client.me.first_name or ""
        last = client.me.last_name or ""
        account_name = f"{first} {last}".strip() or str(user_id)
    
    ads_keywords = gsettings.get("default_ad_keywords", "[]")
    try:
        keywords_list = json.loads(ads_keywords)
    except:
        keywords_list = []
    keywords_display = ", ".join(keywords_list) if keywords_list else "<i>None</i>"

    text = (
        f"<blockquote expandable>"
        f"📡 <b>Forward Pro Dashboard</b>\n"
        f"{'━' * 18}\n"
        f"👤 <b>Account:</b> {html.escape(account_name)}\n"
        f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
        f"{'━' * 18}\n"
        f"📊 <b>Statistics:</b>\n"
        f"  • Total Tasks: <b>{total_count}</b>\n"
        f"  • Active: <b>{active_count}</b> | • Live Listeners: <b>{live_count}</b>\n"
        f"{'━' * 18}\n"
        f"⚙️ <b>Global Default Settings:</b>\n"
        f"  • Delay: <b>{gsettings.get('default_delay', 1.5)}s</b>\n"
        f"  • Translate: <b>{'✅' if gsettings.get('default_is_translate') else '❌'}</b> | "
        f"WM: <b>{'✅' if gsettings.get('default_is_watermark') else '❌'}</b>\n"
        f"  • Clean Links: <b>{'✅' if gsettings.get('default_clean_links') else '❌'}</b> | "
        f"Users: <b>{'✅' if gsettings.get('default_clean_usernames') else '❌'}</b>\n"
        f"  • Ads Filter: <b>{'✅' if gsettings.get('default_is_ads_filter') else '❌'}</b> | "
        f"Bypass: <b>{'✅' if gsettings.get('default_bypass_protected') else '❌'}</b>\n"
        f"  • Global Ads: <code>{html.escape(keywords_display)}</code>\n"
        f"  • Global WM: <code>{html.escape(gsettings.get('default_watermark_text', 'Altruix'))}</code>\n"
        f"  • Regex Pro: <b>{'✅' if gsettings.get('default_use_regex_pro') else '❌'}</b> | "
        f"Order: <b>{gsettings.get('default_batch_order', 'oldest').title()}</b>\n"
        f"  • Log Channel: <b>{'Set' if gsettings.get('log_channel') else 'Not Set'}</b>\n"
        f"{'━' * 18}\n"
        f"🔌 <b>Plugin:</b> <code>v{PLUGIN_VERSION}</code>\n"
        f"{'━' * 18}"
        f"</blockquote>"
    )
    return text


async def build_task_list_text(user_id: int, client=None) -> str:
    """Build the task list text."""
    tasks = await get_tasks(user_id)
    if not tasks:
        return (
            "<blockquote expandable>"
            "📡 <b>Forward Tasks</b>\n"
            f"{'━' * 18}\n"
            "📭 <b>No tasks configured yet.</b>\n\n"
            "Use <code>.fwd add &lt;source_id&gt; &lt;target_id&gt;</code>\n"
            "to add your first forwarding task.\n"
            f"{'━' * 18}"
            "</blockquote>"
        )
    
    text = (
        "<blockquote expandable>"
        "📡 <b>Forward Tasks</b>\n"
        f"{'━' * 18}\n"
    )
    
    for i, t in enumerate(tasks):
        status = "🟢" if t["is_active"] else "🔴"
        mode_icon = "📡" if t["mode"] == "live" else "📦"
        bypass = "🛡" if t.get("bypass_protected") else ""
        
        # Try to get chat titles with icons
        src_title = str(t["source_id"])
        tgt_title = str(t["target_id"])
        if client:
            src_title = await resolve_chat_title(client, t["source_id"])
            tgt_title = await resolve_chat_title(client, t["target_id"])
        
        text += (
            f"\n{status} <b>Task #{t['id']}</b> {mode_icon} {bypass}\n"
            f"  📥 Source: <code>{src_title}</code>\n"
            f"  📤 Target: <code>{tgt_title}</code>\n"
        )
    
    text += f"\n{'━' * 18}</blockquote>"
    return text


def build_task_list_kb(user_id: int, tasks: list) -> InlineKeyboardMarkup:
    """Build keyboard for task list with clickable task buttons."""
    btn_style = get_user_button_style(user_id)
    rows = []
    
    # Task buttons (2 per row)
    task_buttons = []
    for t in tasks:
        status = "🟢" if t["is_active"] else "🔴"
        task_buttons.append(
            InlineKeyboardButton(
                f"{status} Task #{t['id']}",
                callback_data=f"fwd_detail_{t['id']}_{user_id}",
                style=btn_style
            )
        )
    
    for i in range(0, len(task_buttons), 2):
        rows.append(task_buttons[i:i+2])
    
    rows.append([
        InlineKeyboardButton("🔙 Back", callback_data=f"fwd_back_{user_id}", style=btn_style)
    ])
    
    return InlineKeyboardMarkup(rows)


async def build_task_detail_text(task: dict, client=None) -> str:
    """Build the task detail view text."""
    status = "🟢 Active" if task["is_active"] else "🔴 Inactive"
    mode = "📡 Live" if task["mode"] == "live" else "📦 Batch"
    bypass = "✅ ON" if task.get("bypass_protected") else "❌ OFF"
    watermark = f"✅ ON (<i>{html.escape(task.get('watermark_text') or 'Altruix')}</i>)" if task.get("is_watermark") else "❌ OFF"
    translate = "✅ ON" if task.get("is_translate") else "❌ OFF"
    
    # Parse filters
    try:
        filt = json.loads(task.get("filters", "{}"))
    except (json.JSONDecodeError, TypeError):
        filt = {}
    
    filter_text = "All"
    if filt:
        active_filters = [k for k, v in filt.items() if v]
        filter_text = ", ".join(active_filters) if active_filters else "All"
    
    src_title = str(task["source_id"])
    tgt_title = str(task["target_id"])
    if client:
        try:
            src_title = await resolve_chat_title(client, task["source_id"])
        except Exception:
            pass
        try:
            tgt_title = await resolve_chat_title(client, task["target_id"])
        except Exception:
            pass
    
    text = (
        f"<blockquote expandable>"
        f"🔧 <b>Task #{task['id']} Detail</b>\n"
        f"{'━' * 18}\n"
        f"📥 <b>Source:</b> {html.escape(src_title)} (<code>{task['source_id']}</code>)\n"
        f"📤 <b>Target:</b> {html.escape(tgt_title)} (<code>{task['target_id']}</code>)\n"
        f"{'━' * 18}\n"
        f"📊 <b>Status:</b> {status}\n"
        f"🔀 <b>Mode:</b> {mode}\n"
        f"🛡 <b>Bypass:</b> {bypass}\n"
        f"🖼 <b>Watermark:</b> {watermark}\n"
        f"🌍 <b>Translate:</b> {translate}\n"
        f"🔍 <b>Filters:</b> {filter_text}\n"
        f"📅 <b>Created:</b> {task.get('created_at', '?')}\n"
        f"{'━' * 18}"
        f"</blockquote>"
    )
    return text


def build_task_detail_kb(task: dict, user_id: int) -> InlineKeyboardMarkup:
    """Build task detail action keyboard."""
    btn_style = get_user_button_style(user_id)
    tid = task["id"]
    
    start_stop_text = "⏹ Stop" if task["is_active"] else "▶️ Start"
    start_stop_data = f"fwd_stop_{tid}_{user_id}" if task["is_active"] else f"fwd_start_{tid}_{user_id}"
    
    mode_text = f"🔀 Mode: {task['mode'].title()}"
    bypass_text = f"🛡 Bypass: {'ON' if task.get('bypass_protected') else 'OFF'}"
    wm_text = f"🖼 WM: {'ON' if task.get('is_watermark') else 'OFF'}"
    tr_text = f"🌍 TR: {'ON' if task.get('is_translate') else 'OFF'}"
    
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(start_stop_text, callback_data=start_stop_data, style=btn_style),
            InlineKeyboardButton("🔍 Filter Media", callback_data=f"fwd_filter_{tid}_{user_id}", style=btn_style)
        ],
        [
            InlineKeyboardButton("🛡 Advanced Options", callback_data=f"fwd_advopts_{tid}_{user_id}", style=btn_style)
        ],
        [
            InlineKeyboardButton(bypass_text, callback_data=f"fwd_bypass_{tid}_{user_id}", style=btn_style),
            InlineKeyboardButton(mode_text, callback_data=f"fwd_mode_{tid}_{user_id}", style=btn_style)
        ],
        [
            InlineKeyboardButton(wm_text, callback_data=f"fwd_wmtoggle_{tid}_{user_id}", style=btn_style),
            InlineKeyboardButton(tr_text, callback_data=f"fwd_trtoggle_{tid}_{user_id}", style=btn_style)
        ],
        [
            InlineKeyboardButton("🚀 START BATCH", callback_data=f"fwd_btchrange_{tid}_{user_id}", style=btn_style)
        ],
        [
            InlineKeyboardButton("🖼 Set WM Text", callback_data=f"fwd_wmset_{tid}_{user_id}", style=btn_style),
            InlineKeyboardButton("🚫 Set Ads Filter", callback_data=f"fwd_adsset_{tid}_{user_id}", style=btn_style)
        ],
        [
            InlineKeyboardButton("🗑 Delete", callback_data=f"fwd_delconf_{tid}_{user_id}", style=btn_style),
            InlineKeyboardButton("🔙 Back", callback_data=f"fwd_list_{user_id}", style=btn_style)
        ]
    ])


def build_advanced_options_kb(task: dict, user_id: int) -> InlineKeyboardMarkup:
    """Build keyboard for advanced task settings."""
    btn_style = get_user_button_style(user_id)
    tid = task["id"]
    
    clean_l = "✅ Links" if task.get("clean_links") else "❌ Links"
    clean_u = "✅ Users" if task.get("clean_usernames") else "❌ Users"
    ads_f = "✅ Ads" if task.get("is_ads_filter") else "❌ Ads"
    rex_p = "✅ Regex Pro" if task.get("use_regex_pro") else "❌ Regex Pro"
    cpy_f = "✅ Copy" if task.get("forward_as_copy", 1) else "❌ Copy"
    bps_f = "✅ Bypass" if task.get("bypass_protected") else "❌ Bypass"
    
    order_label = "⬇️ Order: Oldest First" if task.get("batch_order") == "oldest" else "⬆️ Order: Newest First"
    
    tr_text = "🌐 Set Language"
    
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(clean_l, callback_data=f"fwd_atoggle_{tid}_clean_links_{user_id}", style=btn_style),
            InlineKeyboardButton(clean_u, callback_data=f"fwd_atoggle_{tid}_clean_usernames_{user_id}", style=btn_style),
            InlineKeyboardButton(ads_f, callback_data=f"fwd_atoggle_{tid}_is_ads_filter_{user_id}", style=btn_style)
        ],
        [
            InlineKeyboardButton(rex_p, callback_data=f"fwd_atoggle_{tid}_use_regex_pro_{user_id}", style=btn_style),
            InlineKeyboardButton(cpy_f, callback_data=f"fwd_atoggle_{tid}_forward_as_copy_{user_id}", style=btn_style),
            InlineKeyboardButton(bps_f, callback_data=f"fwd_atoggle_{tid}_bypass_protected_{user_id}", style=btn_style)
        ],
        [
            InlineKeyboardButton("📝 Config Regex", callback_data=f"fwd_rexset_{tid}_{user_id}", style=btn_style),
            InlineKeyboardButton(tr_text, callback_data=f"fwd_trlang_{tid}_{user_id}", style=btn_style)
        ],
        [
            InlineKeyboardButton("⏱ Delay -", callback_data=f"fwd_bdel_{tid}_dec_{user_id}", style=btn_style),
            InlineKeyboardButton(f"Delay: {task.get('batch_delay', 1.5)}s", callback_data="noop", style=btn_style),
            InlineKeyboardButton("⏱ Delay +", callback_data=f"fwd_bdel_{tid}_inc_{user_id}", style=btn_style)
        ],
        [
            InlineKeyboardButton(order_label, callback_data=f"fwd_border_{tid}_{user_id}", style=btn_style)
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data=f"fwd_detail_{tid}_{user_id}", style=btn_style)
        ]
    ])


async def build_advanced_options_text(task: dict) -> str:
    """Build text for advanced task settings menu."""
    clean_links = "ON" if task.get("clean_links") else "OFF"
    clean_users = "ON" if task.get("clean_usernames") else "OFF"
    ads_filter = "ON" if task.get("is_ads_filter") else "OFF"
    regex_pro = "ON" if task.get("use_regex_pro") else "OFF"
    as_copy = "ON" if task.get("forward_as_copy", 1) else "OFF"
    bypass = "ON" if task.get("bypass_protected") else "OFF"
    order = "Oldest ➔ Newest" if task.get("batch_order") == "oldest" else "Newest ➔ Oldest"
    
    text = (
        f"<blockquote expandable>"
        f"🛡 <b>Advanced Options — Task #{task['id']}</b>\n"
        f"{'━' * 18}\n"
        f"🧹 <b>Caption Cleaning:</b>\n"
        f"  • Remove Links: <b>{clean_links}</b>\n"
        f"  • Remove Usernames: <b>{clean_users}</b>\n"
        f"  • Ads Word Filter: <b>{ads_filter}</b>\n"
        f"  • Regex Pro: <b>{regex_pro}</b>\n\n"
        f"📦 <b>Batch Controls:</b>\n"
        f"  • Custom Delay: <b>{task.get('batch_delay', 1.5)}s</b>\n"
        f"  • Process Order: <b>{order}</b>\n"
        f"  • Forward as Copy: <b>{as_copy}</b>\n"
        f"  • Bypass Protected: <b>{bypass}</b>\n\n"
        f"📖 <b>Glossary:</b>\n"
        f"  • <b>LNK</b>: Remove web links from caption.\n"
        f"  • <b>USR</b>: Remove @usernames from caption.\n"
        f"  • <b>ADS</b>: Filter out defined advertisement keywords.\n"
        f"  • <b>BPS</b>: Bypass restricted content (re-upload logic).\n"
        f"  • <b>CPY</b>: Forward as Copy (Hide Sender Name).\n"
        f"  • <b>TR</b>: Automatic translation to target language.\n"
        f"{'━' * 18}"
        f"</blockquote>"
    )
    return text


def build_filter_kb(task: dict, user_id: int, is_global: bool = False) -> InlineKeyboardMarkup:
    """Build media filter selection keyboard (Task-specific or Global)."""
    btn_style = get_user_button_style(user_id)
    tid = task.get("id", 0) if task else 0
    
    try:
        if is_global:
            filt = json.loads(task.get("default_filters", "{}"))
        else:
            filt = json.loads(task.get("filters", "{}"))
    except (json.JSONDecodeError, TypeError):
        filt = {}
    
    media_types = [
        ("photo", "🖼 Photo"), ("video", "🎬 Video"),
        ("audio", "🎵 Audio"), ("document", "📄 Document"),
        ("sticker", "🎨 Sticker"), ("voice", "🎤 Voice"),
        ("text", "✏️ Text"),
    ]
    
    rows = []
    for i in range(0, len(media_types), 2):
        row = []
        for key, label in media_types[i:i+2]:
            is_on = filt.get(key, True)
            emoji = "✅" if is_on else "❌"
            cbd = f"fwd_gftoggle_{key}_{user_id}" if is_global else f"fwd_ftoggle_{tid}_{key}_{user_id}"
            row.append(InlineKeyboardButton(f"{emoji} {label}", callback_data=cbd, style=btn_style))
        rows.append(row)
    
    back_cbd = f"fwd_back_{user_id}" if is_global else f"fwd_advopts_{tid}_{user_id}"
    rows.append([InlineKeyboardButton("🔙 Back", callback_data=back_cbd, style=btn_style)])
    
    return InlineKeyboardMarkup(rows)


def build_global_adv_opts_kb(gs: dict, user_id: int) -> InlineKeyboardMarkup:
    """Build keyboard for global advanced defaults."""
    btn_style = get_user_button_style(user_id)
    
    order_label = "⬇️ Order: Oldest First" if gs.get("default_batch_order") == "oldest" else "⬆️ Order: Newest First"
    rex_p = "✅ Regex Pro" if gs.get("default_use_regex_pro") else "❌ Regex Pro"
    
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(rex_p, callback_data=f"fwd_gtoggle_default_use_regex_pro_{user_id}", style=btn_style),
            InlineKeyboardButton("📝 Config Global Regex", callback_data=f"fwd_grexset_{user_id}", style=btn_style)
        ],
        [
            InlineKeyboardButton("-0.5s", callback_data=f"fwd_gdel_dec_{user_id}", style=btn_style),
            InlineKeyboardButton(f"Delay: {gs.get('default_delay', 1.5)}", callback_data="noop", style=btn_style),
            InlineKeyboardButton("+0.5s", callback_data=f"fwd_gdel_inc_{user_id}", style=btn_style)
        ],
        [
            InlineKeyboardButton("-3.0s", callback_data=f"fwd_gdel_dec3_{user_id}", style=btn_style),
            InlineKeyboardButton("+3.0s", callback_data=f"fwd_gdel_inc3_{user_id}", style=btn_style)
        ],
        [
            InlineKeyboardButton(order_label, callback_data=f"fwd_gborder_{user_id}", style=btn_style)
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data=f"fwd_back_{user_id}", style=btn_style)
        ]
    ])




# ==================== COMMAND HANDLERS ====================

@Altruix.register_on_cmd(
    ["fwd", "forward"],
    cmd_help={
        "help": "Advanced Forwarder Dashboard. Manage forwarding tasks between chats.",
        "example": (
            "{i}fwd\n"
            "{i}fwd add -100123456789 -100987654321 live\n"
            "{i}fwd run 1 100 500\n"
            "{i}fwd stop 1\n"
            "{i}fwd status 1\n"
            "{i}fwd rm 1\n"
            "{i}fwd wm 1 @MyWatermark\n"
            "{i}fwd ads 1 promo,iklan\n"
            "{i}fwd glog"
        ),
        "user_args": [
            "add <src> <tgt> [mode] - Add a new task (mode: live or batch)",
            "run <tid> <start> <end> - Execute a batch forward task",
            "stop <tid> - Stop an active automated task",
            "status <tid> - Check the current statistics and mode of a task",
            "rm <tid> - Delete a task from the database",
            "wm <tid> <text> - Set specific watermark text for a task",
            "ads <tid> <words> - Set ad filter keywords for a task",
            "gwm <text> - Set global watermark text (applies to new tasks)",
            "gads <words> - Set global ad keywords (applies to new tasks)",
            "glog - Set current group/channel as the global log receiver",
            "help - Show the detailed inline help menu documentation"
        ]
    },
)
@log_errors
@iuser_check
async def fwd_command_handler(c: Client, m: AltruixMessage):
    """Handle .fwd command — show dashboard or process subcommands."""
    user_id = m.from_user.id if m.from_user else c.me.id
    
    # Parse subcommands
    raw = m.raw_user_input or ""
    parts = raw.strip().split()
    
    if parts:
        subcmd = parts[0].lower()
        
        # .fwd help
        if subcmd == "help":
            help_text = build_info_text(0)
            btn_style = get_user_button_style(user_id)
            kb = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("◀️", callback_data=f"fwd_help_0_{user_id}", style=btn_style),
                    InlineKeyboardButton("▶️", callback_data=f"fwd_help_1_{user_id}", style=btn_style)
                ],
                [InlineKeyboardButton("📋 Show CMD", callback_data=f"fwd_showcmd_{user_id}", style=btn_style)],
                [InlineKeyboardButton("🔙 Back", callback_data=f"fwd_back_{user_id}", style=btn_style)]
            ])
            await m.reply(help_text, reply_markup=kb)
            return

        # .fwd add <source_id> <target_id> [mode]
        if subcmd == "add" and len(parts) >= 3:
            try:
                source_id = int(parts[1])
                target_id = int(parts[2])
                mode = parts[3] if len(parts) > 3 and parts[3] in ("live", "batch") else "live"
            except ValueError:
                return await m.reply(
                    "❌ <b>Invalid format.</b>\n"
                    "Usage: <code>.fwd add &lt;source_id&gt; &lt;target_id&gt; [live|batch]</code>"
                )
            
            task_id = await add_task(user_id, source_id, target_id, mode)
            if task_id > 0:
                src_title = await resolve_chat_title(c, source_id)
                tgt_title = await resolve_chat_title(c, target_id)
                await m.reply(
                    f"✅ <b>Task #{task_id} Created</b>\n"
                    f"📥 Source: {html.escape(src_title)} (<code>{source_id}</code>)\n"
                    f"📤 Target: {html.escape(tgt_title)} (<code>{target_id}</code>)\n"
                    f"🔀 Mode: <b>{mode}</b>\n\n"
                    f"Use <code>.fwd</code> to manage."
                )
            else:
                await m.reply("❌ <b>Failed to create task.</b> Check logs.")
            return

        # .fwd run <task_id> <start_id> <end_id>
        if subcmd == "run" and len(parts) >= 4:
            try:
                tid = int(parts[1])
                start_id = int(parts[2])
                end_id = int(parts[3])
            except ValueError:
                return await m.reply("❌ <b>Invalid ID format.</b> Use: <code>.fwd run <tid> <start> <end></code>")
            
            task = await get_task(tid)
            if not task or task["user_id"] != user_id:
                return await m.reply("❌ <b>Task not found or access denied.</b>")
            
            # Start batch background task
            asyncio.create_task(start_batch_fwd(c, user_id, tid, start_id, end_id))
            await m.reply(f"🚀 <b>Batch Forward Task #{tid} Started!</b>\nRange: <code>{start_id}</code> - <code>{end_id}</code>\nMonitoring progress in Log Group...")
            return
        
        # .fwd wm <task_id> <text>
        if subcmd == "wm" and len(parts) >= 3:
            try:
                tid = int(parts[1])
                wm_text = " ".join(parts[2:])
                await update_task(tid, watermark_text=wm_text)
                await m.reply(f"✅ <b>Watermark for Task #{tid} set:</b> <code>{wm_text}</code>")
            except ValueError:
                await m.reply("❌ <b>Invalid Task ID.</b>")
            return

        # .fwd ads <task_id> <keywords>
        if subcmd == "ads" and len(parts) >= 3:
            try:
                tid = int(parts[1])
                keywords = parts[2].split(",")
                await update_task(tid, ad_keywords=json.dumps(keywords))
                await m.reply(f"✅ <b>Ad Keywords for Task #{tid} set:</b> <code>{keywords}</code>")
            except ValueError:
                await m.reply("❌ <b>Invalid Task ID.</b>")
            return

        # .fwd gads <keywords>
        if subcmd == "gads" and len(parts) >= 2:
            keywords = parts[1].split(",")
            await update_global_settings(user_id, default_ad_keywords=json.dumps(keywords))
            await m.reply(f"✅ <b>Global Ad Keywords set:</b> <code>{keywords}</code>\n<i>This will apply to all new tasks.</i>")
            return

        # .fwd gwm <text>
        if subcmd == "gwm" and len(parts) >= 2:
            wm_text = " ".join(parts[1:])
            await update_global_settings(user_id, default_watermark_text=wm_text)
            await m.reply(f"✅ <b>Global Watermark set:</b> <code>{wm_text}</code>\n<i>This will apply to all new tasks.</i>")
            return

        # .fwd remove <task_id>
        if subcmd in ("remove", "rm", "del", "delete") and len(parts) >= 2:
            try:
                tid = int(parts[1])
            except ValueError:
                return await m.reply("❌ <b>Invalid task ID.</b>")
            
            task = await get_task(tid)
            if not task or task["user_id"] != user_id:
                return await m.reply("❌ <b>Task not found or access denied.</b>")
            
            _unregister_live_listener(tid)
            if await delete_task(tid):
                await m.reply(f"✅ <b>Task #{tid} deleted.</b>")
            else:
                await m.reply("❌ <b>Failed to delete task.</b>")
            return
            
        # .fwd stop <task_id>
        if subcmd == "stop" and len(parts) >= 2:
            try:
                tid = int(parts[1])
            except ValueError:
                return await m.reply("❌ <b>Invalid task ID.</b>")
                
            task = await get_task(tid)
            if not task or task["user_id"] != user_id:
                return await m.reply("❌ <b>Task not found or access denied.</b>")
                
            await update_task(tid, is_active=0)
            task["is_active"] = 0
            _unregister_live_listener(tid)
            
            await m.reply(f"⏹ <b>Task #{tid} has been explicitly stopped.</b>")
            return
            
        # .fwd status <task_id>
        if subcmd == "status" and len(parts) >= 2:
            try:
                tid = int(parts[1])
            except ValueError:
                return await m.reply("❌ <b>Invalid task ID.</b>")
                
            task = await get_task(tid)
            if not task or task["user_id"] != user_id:
                return await m.reply("❌ <b>Task not found or access denied.</b>")
                
            status_text = await build_task_detail_text(task, client=c)
            await m.reply(status_text)
            return

        # .fwd glog
        if subcmd == "glog":
            chat_id = m.chat.id
            if m.chat.type == enums.ChatType.PRIVATE:
                return await m.reply("❌ <b>Command ini hanya bisa digunakan di dalam Group atau Channel untuk dijadikan tempat penerima Log.</b>")
                
            await update_global_settings(user_id, log_channel_id=chat_id)
            await m.reply(
                f"✅ <b>Log Channel Berhasil Diperbarui!</b>\n"
                f"Semua notifikasi Forward Pro sekarang akan dikirimkan ke chat ini (<code>{chat_id}</code>)."
            )
            return
    
    # Default: Show dashboard via Inline Mode (tag @botasisten)
    bot_username = None
    if hasattr(Altruix, 'bot_manager'):
        bot_username = Altruix.bot_manager.get_bot_username(user_id)
    
    if bot_username:
        try:
            # Inline trigger for dashboard
            results = await c.get_inline_bot_results(bot_username, f"fwd_menu_uid_{user_id}")
            if results.results:
                sent = await c.send_inline_bot_result(
                    m.chat.id,
                    results.query_id,
                    results.results[0].id,
                    reply_to_message_id=m.id
                )
                if sent:
                    await m.delete_if_self()
                    return
        except Exception as e:
            logger.warning(f"[ForwardPro] Inline dashboard failed: {e}, falling back to direct")

    # Fallback to direct bot message
    dashboard_text = await build_main_menu_text(user_id, client=c)
    gsettings = await get_global_settings(user_id)
    kb = build_main_menu_kb(user_id, gsettings=gsettings)
    
    # Send via bot for inline buttons
    bot = None
    if hasattr(Altruix, 'bot_manager'):
        bot = Altruix.bot_manager.get_bot(user_id)
    if not bot:
        bot = Altruix.bot
    
    if bot:
        await bot.send_message(
            m.chat.id, dashboard_text, reply_markup=kb,
            parse_mode=enums.ParseMode.HTML, reply_to_message_id=m.id
        )
        await m.delete_if_self()
    else:
        await m.reply(dashboard_text, reply_markup=kb)


# ==================== INFO & HELP TEXT ====================

def build_info_text(page: int = 0) -> str:
    """Build paginated help text for Forward Pro."""
    pages = [
        # Page 0: Dashboard & Basics (What each button does)
        (
            "<blockquote expandable><b>📡 FORWARD PRO - INFO (1/4)</b>\n\n"
            "<b>🎯 MAIN BUTTON FUNCTIONS:</b>\n\n"
            "• <b>➕ Add Task (Step)</b>: Start the interactive task creation process.\n"
            "  ↳ <i>You will be prompted to enter the Source chat ID and the Target chat ID.</i>\n\n"
            "• <b>📡 List Tasks</b>: Open the dashboard listing all your forwarding tasks.\n"
            "  ↳ <i>From this list, you can click on any task to view its details and modify its settings.</i>\n\n"
            "• <b>📊 General Stats</b>: View the total number of successfully/failed forwarded messages.\n\n"
            "• <b>🧹 Global Ads & 🖼 Global WM</b>: Open a prompt to input a list of ad keywords or Watermark text to be used as default settings for every new task.</blockquote>"
        ),
        # Page 1: Task Options
        (
            "<blockquote expandable><b>📡 FORWARD PRO - INFO (2/4)</b>\n\n"
            "<b>🔧 IN-TASK SETTINGS (Task Detail):</b>\n\n"
            "• <b>▶️ Start / ⏹ Stop</b>: Toggle the forwarding automation on or off.\n\n"
            "• <b>🔍 Filter Media</b>: Select which types of messages you want to forward.\n\n"
            "• <b>🖼 WM & 🌍 TR Toggle</b>: Enable Watermark or automatic Translation.\n\n"
            "• <b>⚙️ GLOSSARY:</b>\n"
            "  - <b>LNK (Links)</b>: Strip all URLs.\n"
            "  - <b>USR (Users)</b>: Strip all user mentions.\n"
            "  - <b>ADS (Ads)</b>: Remove specified keywords.\n"
            "  - <b>BPS (Bypass)</b>: Handle protected content.\n"
            "  - <b>TR (Translate)</b>: Convert text to your chosen language.</blockquote>"
        ),
        # Page 2: Advanced Tools & Bypass
        (
            "<blockquote expandable><b>📡 FORWARD PRO - INFO (3/4)</b>\n\n"
            "<b>✨ ADVANCED FEATURES (Bypass & Clean):</b>\n\n"
            "• <b>🧹 Caption Cleaner (LNK/USR/ADS)</b>: \n"
            "  ↳ If enabled, the bot will automatically strip `http://..` links, `@someone` usernames, and ad keywords from message captions before forwarding.\n\n"
            "• <b>🛡 BYPASS FEATURE (Crucial!):</b>\n"
            "  ↳ If the source channel has <i>Restrict Saving Content</i> enabled, standard forwarding will fail.\n"
            "  ↳ With Bypass enabled, the bot silently downloads the media and <b>re-uploads</b> it to the target chat as a completely new message.\n"
            "  ↳ <i>Note: If you enable the Watermark (WM) feature, the Bypass system activates automatically to imprint the image.</i></blockquote>"
        ),
        # Page 3: Command Examples
        (
            "<blockquote expandable><b>📡 FORWARD PRO - INFO (4/4)</b>\n\n"
            "<b>📦 LIVE vs BATCH MODE:</b>\n"
            "• <b>📡 Live Mode</b>: Bot continuously monitors. Any new message in Source is sent to Target.\n"
            "• <b>📦 Batch Mode</b>: Bot fetches history in a range.\n\n"
            "<b>CONCRETE MANUAL COMMANDS:</b>\n"
            "  1. <i>Start/Add Task (Live):</i>\n"
            "     <code>.fwd add -1001234 -1005678 live</code>\n"
            "  2. <i>Cek Status Task #1:</i>\n"
            "     <code>.fwd status 1</code>\n"
            "  3. <i>Hentikan Automasi Task #1:</i>\n"
            "     <code>.fwd stop 1</code>\n"
            "  4. <i>Run Batch (Task #1, ID 1-500):</i>\n"
            "     <code>.fwd run 1 1 500</code>\n"
            "  5. <i>Set Log Receiver (Ketik di Group Log):</i>\n"
            "     <code>.fwd glog</code></blockquote>"
        )
    ]
    if page < 0: page = 0
    if page >= len(pages): page = len(pages) - 1
    return pages[page]

def build_showcmd_text() -> str:
    """Build manual command guide text."""
    return (
        "<blockquote expandable><b>📋 FORWARD PRO - MANUAL COMMANDS</b>\n\n"
        "In addition to using the interactive Dashboard buttons, you can manually type commands:\n\n"
        "• <code>.fwd</code>\n"
        "  ↳ Open the Main Dashboard interface.\n\n"
        "• <code>.fwd add &lt;src_id&gt; &lt;tgt_id&gt; [mode]</code>\n"
        "  ↳ EXAMPLE: <code>.fwd add -100123.. -100456.. live</code>\n"
        "  ↳ EXAMPLE: <code>.fwd add -100123.. -100456.. batch</code>\n\n"
        "• <code>.fwd run &lt;task_id&gt; &lt;start_msg_id&gt; &lt;end_msg_id&gt;</code>\n"
        "  ↳ Execute a Batch transfer. You can find the Task ID in the 'List Tasks' menu.\n"
        "  ↳ EXAMPLE: <code>.fwd run 1 100 500</code> (Run Task #1 from msg ID 100 to 500)\n\n"
        "• <code>.fwd remove &lt;task_id&gt;</code>\n"
        "  ↳ Force remove a task: <code>.fwd remove 1</code>\n\n"
        "• <code>.fwd wm &lt;task_id&gt; &lt;text&gt;</code>\n"
        "  ↳ Set Watermark string: <code>.fwd wm 1 By @Altruix</code>\n\n"
        "• <code>.fwd ads &lt;task_id&gt; &lt;word1,word2&gt;</code>\n"
        "  ↳ Set Ad Filters: <code>.fwd ads 1 promo,iklan,join</code>\n\n"
        "• <code>.fwd glog</code>\n"
        "  ↳ Type this command inside your secret log group/channel to redirect all bot notifications there.</blockquote>"
    )

# ==================== INLINE HANDLER ====================

from pyrogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent

@Altruix.bot.on_inline_query(filters.regex(r"^fwd_menu_uid_(?P<uid>\d+)"))
@iuser_check
@log_errors
async def fwd_inline_handler(client: Client, query: InlineQuery):
    """Handle inline query for Forward Pro dashboard."""
    try:
        user_id = int(query.matches[0].group("uid"))
        
        # Get userbot client for resolution (optional here but good for consistency)
        ub_client = None
        if hasattr(Altruix, 'clients'):
            for cl in Altruix.clients:
                try:
                    if cl.me and cl.me.id == user_id:
                        ub_client = cl
                        break
                except: continue

        text = await build_main_menu_text(user_id, client=ub_client)
        gs = await get_global_settings(user_id)
        kb = build_main_menu_kb(user_id, gsettings=gs)
        
        await query.answer(
            results=[
                InlineQueryResultArticle(
                    title="📡 Forward Pro Dashboard",
                    description=f"Manage forwarding tasks for account {user_id}",
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
        logger.error(f"ForwardPro Inline Handler Error: {e}")


# ==================== INTERACTIVE INPUT HANDLER ====================

@Altruix.bot.on_message(filters.private & ~filters.me)
@iuser_check
@log_errors
async def fwd_input_handler(client: Client, message: RawMessage):
    """Handle interactive inputs (task creation, setting text)."""
    user_id = message.from_user.id
    
    # ── Handle WAITING_FOR_INPUT (Settings) ──
    if user_id in FPRO_WAITING_INPUT:
        state = FPRO_WAITING_INPUT.pop(user_id)
        action = state["action"]
        text = message.text
        
        # Determine client for UI refresh
        ub_client = None
        if hasattr(Altruix, "clients"):
            for cl in Altruix.clients:
                if cl.me and cl.me.id == user_id:
                    ub_client = cl
                    break
                    
        mid = state.get("mid")
        inl_id = state.get("inline_message_id")
        
        async def _update_ui(new_text, new_kb):
            try:
                if inl_id:
                    await Altruix.bot.edit_inline_text(inline_message_id=inl_id, text=new_text, reply_markup=new_kb, parse_mode=enums.ParseMode.HTML)
                elif mid:
                    await client.edit_message_text(chat_id=user_id, message_id=mid, text=new_text, reply_markup=new_kb, parse_mode=enums.ParseMode.HTML)
            except Exception as e:
                logger.error(f"[ForwardPro] update UI error: {e}")

        if action == "wm_set_text":
            tid = state.get("task_id") or state.get("tid")
            if tid:
                await update_task(tid, watermark_text=text)
                await message.reply(f"✅ <b>Watermark text for Task #{tid} updated!</b>")
                task = await get_task(tid)
                if task:
                    await _update_ui(await build_task_detail_text(task, client=ub_client), build_task_detail_kb(task, user_id))
            else:
                # Global
                await update_global_settings(user_id, default_watermark_text=text)
                await message.reply(f"✅ <b>Global watermark text updated!</b>")
                gs = await get_global_settings(user_id)
                await _update_ui(await build_main_menu_text(user_id, client=ub_client), build_main_menu_kb(user_id, gsettings=gs))
        
        elif action in ("ads_set_keywords", "gads_set"):
            tid = state.get("task_id") or state.get("tid")
            keywords = [k.strip() for k in text.split(",")]
            if tid:
                await update_task(tid, ad_keywords=json.dumps(keywords))
                await message.reply(f"✅ <b>Ad keywords for Task #{tid} updated!</b>")
                task = await get_task(tid)
                if task:
                    await _update_ui(await build_task_detail_text(task, client=ub_client), build_task_detail_kb(task, user_id))
            else:
                # Global
                await update_global_settings(user_id, default_ad_keywords=json.dumps(keywords))
                await message.reply(f"✅ <b>Global ad keywords updated!</b>")
                gs = await get_global_settings(user_id)
                await _update_ui(await build_main_menu_text(user_id, client=ub_client), build_main_menu_kb(user_id, gsettings=gs))
        
        elif action in ("rex_set_patterns", "grex_set_patterns"):
            is_global = (action == "grex_set_patterns")
            tid = state.get("tid") or state.get("task_id", 0)
            
            # Parse patterns: pattern|replacement
            patterns = []
            lines = text.split("\n")
            for line in lines:
                if "|" in line:
                    parts = line.split("|", 1)
                    patterns.append([parts[0].strip(), parts[1].strip()])
            
            json_patterns = json.dumps(patterns)
            if is_global:
                await update_global_settings(user_id, default_custom_regex=json_patterns)
                await message.reply(f"✅ <b>Global Regex Pro patterns updated ({len(patterns)} patterns)!</b>")
                gs = await get_global_settings(user_id)
                
                # Stay in Global Adv Opts
                adv_text = (
                    "<blockquote expandable>"
                    "🛡 <b>Global Advanced Options</b>\n"
                    f"{'━' * 18}\n"
                    "Atur default untuk pengaturan lanjutan (berlaku untuk task baru).\n\n"
                    "• <b>Regex Pro</b>: Gunakan pola regex kustom.\n"
                    "• <b>Batch Order</b>: Urutan proses pesan dalam mode batch.\n"
                    "• <b>Default Delay</b>: Jeda antar pesan.\n"
                    f"{'━' * 18}"
                    "</blockquote>"
                )
                await _update_ui(adv_text, build_global_adv_opts_kb(gs, user_id))
            else:
                await update_task(tid, custom_regex=json_patterns)
                await message.reply(f"✅ <b>Regex Pro patterns for Task #{tid} updated ({len(patterns)} patterns)!</b>")
                task = await get_task(tid)
                if task:
                    await _update_ui(await build_advanced_options_text(task), build_advanced_options_kb(task, user_id))
            
        elif action == "glog_set":
            try:
                chat_id = int(text)
                await update_global_settings(user_id, log_channel=chat_id)
                
                title = "Unknown Chat"
                if ub_client:
                    title = await resolve_chat_title(ub_client, chat_id)
                
                await message.reply(f"✅ <b>Log channel set to:</b> {html.escape(title)} (<code>{chat_id}</code>)")
                
                gs = await get_global_settings(user_id)
                await _update_ui(await build_main_menu_text(user_id, client=ub_client), build_main_menu_kb(user_id, gsettings=gs))
            except ValueError:
                await message.reply("❌ <b>Mohon masukkan angka ID yang valid.</b>")
                # re-put state to allow retry
                FPRO_WAITING_INPUT[user_id] = state 
            except Exception as e:
                logger.error(f"[ForwardPro] glog_set error: {e}")
                await message.reply(f"❌ <b>Error:</b> {e}")

        return

    # ── Handle ADD_TASK_STATE (Interactive Creation) ──
    if user_id in FPRO_ADD_TASK_STATE:
        state = FPRO_ADD_TASK_STATE[user_id]
        step = state["step"]
        
        try:
            val = int(message.text)
        except ValueError:
            return await message.reply("❌ <b>Mohon masukkan angka ID yang valid.</b>")
        
        if step == 1: # Got Source
            state["src"] = val
            state["step"] = 2
            
            # Proactive Title Resolution
            title_info = ""
            if hasattr(Altruix, "clients") and Altruix.clients:
                for cl in Altruix.clients:
                    if cl.me and cl.me.id == user_id:
                        title_info = f" ({await resolve_chat_title(cl, val)})"
                        break
            
            await message.reply(
                f"📥 <b>Source set to:</b> <code>{val}</code>{html.escape(title_info)}\n"
                f"👤 <b>Sekarang kirim Target Chat ID:</b>"
            )
        elif step == 2: # Got Target
            state["tgt"] = val
            state["step"] = 3
            
            # Proactive Title Resolution
            title_info = ""
            if hasattr(Altruix, "clients") and Altruix.clients:
                for cl in Altruix.clients:
                    if cl.me and cl.me.id == user_id:
                        title_info = f" ({await resolve_chat_title(cl, val)})"
                        break
            
            btn_style = get_user_button_style(user_id)
            kb = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📡 Live", callback_data=f"fwd_add_done_live_{user_id}", style=btn_style),
                    InlineKeyboardButton("📦 Batch", callback_data=f"fwd_add_done_batch_{user_id}", style=btn_style)
                ],
                [InlineKeyboardButton("❌ Cancel", callback_data=f"fwd_add_cancel_{user_id}", style=btn_style)]
            ])
            await message.reply(
                f"📤 <b>Target set to:</b> <code>{val}</code>{html.escape(title_info)}\n\n"
                f"⚙️ <b>Pilih Mode forwarding:</b>",
                reply_markup=kb
            )
        return


# ==================== CALLBACK HANDLER ====================

@Altruix.bot.on_callback_query(filters.regex(r"^fwd_(.+)$"))
@iuser_check
@log_errors
async def fwd_callback_handler(client: Client, cb: CallbackQuery):
    """Handle all Forward Pro callback queries."""
    data = cb.data
    parts = data.split("_")
    
    # fwd_action_...
    if len(parts) < 2:
        return
    
    action = parts[1]
    
    # Extract user_id (always last part for auth)
    try:
        uid = int(parts[-1])
    except (ValueError, IndexError):
        uid = cb.from_user.id
    
    # Auth check: only the task owner can interact
    if cb.from_user.id != uid:
        # Check if sudo
        is_sudo = await Altruix.is_sudo(cb.from_user.id)
        if not is_sudo:
            return await safe_cb_answer(cb, "❌ Not authorized.", show_alert=True)
    
    # Get a userbot client for this user
    ub_client = None
    if hasattr(Altruix, 'clients') and Altruix.clients:
        for cl in Altruix.clients:
            try:
                if cl.me and cl.me.id == uid:
                    ub_client = cl
                    break
            except Exception:
                continue
    if not ub_client and Altruix.clients:
        ub_client = Altruix.clients[0]
    
    # ── CLOSE ──
    if action == "close":
        try:
            await cb.message.delete()
        except Exception:
            try:
                await cb.edit_message_text("🚪 <b>Menu Closed.</b>", parse_mode=enums.ParseMode.HTML)
            except:
                pass
        return
        
    # ── NOOP ──
    if action == "noop":
        return await safe_cb_answer(cb, "ℹ️ Sudah di batas halaman.", show_alert=False)
    
    # ── BACK (Main Menu) ──
    if action == "back":
        text = await build_main_menu_text(uid, client=ub_client)
        gs = await get_global_settings(uid)
        kb = build_main_menu_kb(uid, gsettings=gs)
        try:
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        except Exception:
            pass
        return
    
    # ── GLOBAL TOGGLES ──
    if action == "gtoggle":
        # fwd_gtoggle_{field}_{uid}
        # field might contain underscores, so we join everything between parts[2] and the last part (uid)
        field = "_".join(parts[2:-1])
        gs = await get_global_settings(uid)
        
        valid_fields = (
            "default_is_translate", "default_is_watermark", 
            "default_clean_links", "default_clean_usernames",
            "default_is_ads_filter", "default_bypass_protected",
            "default_use_regex_pro", "default_forward_as_copy"
        )
        
        if field in valid_fields:
            new_val = 0 if gs.get(field) else 1
            await update_global_settings(uid, **{field: new_val})
            gs[field] = new_val
            
            await safe_cb_answer(cb, f"🔘 {field.replace('default_', '').replace('_', ' ').title()}: {'ON' if new_val else 'OFF'}", show_alert=False)
            
            # Hot reload based on menu context
            if field == "default_use_regex_pro":
                text = (
                    "<blockquote expandable>"
                    "🛡 <b>Global Advanced Options</b>\n"
                    f"{'━' * 18}\n"
                    "Atur default untuk pengaturan lanjutan (berlaku untuk task baru).\n\n"
                    "• <b>Regex Pro</b>: Gunakan pola regex kustom.\n"
                    "• <b>Batch Order</b>: Urutan proses pesan dalam mode batch.\n"
                    "• <b>Default Delay</b>: Jeda antar pesan.\n"
                    f"{'━' * 18}"
                    "</blockquote>"
                )
                kb = build_global_adv_opts_kb(gs, uid)
            else:
                text = await build_main_menu_text(uid, client=ub_client)
                kb = build_main_menu_kb(uid, gsettings=gs)
            
            try:
                await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            except Exception:
                pass
        return

    # ── LIST TASKS ──
    if action == "list":
        tasks = await get_tasks(uid)
        text = await build_task_list_text(uid, client=ub_client)
        kb = build_task_list_kb(uid, tasks)
        try:
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        except Exception:
            pass
        return

    # ── GLOBAL STATS ──
    if action == "stats":
        tasks = await get_tasks(uid)
        total_success = sum(t.get("count_success", 0) for t in tasks)
        total_failed = sum(t.get("count_failed", 0) for t in tasks)
        
        text = (
            "<blockquote expandable>"
            "📊 <b>Detailed Forward Statistics</b>\n"
            f"{'━' * 18}\n"
            f"✅ Total Success: <b>{total_success}</b>\n"
            f"❌ Total Failed: <b>{total_failed}</b>\n"
            f"📝 Total Tasks: <b>{len(tasks)}</b>\n"
            f"{'━' * 18}\n"
            "<i>Stats are accumulated across all active and inactive tasks.</i>\n"
            f"{'━' * 18}"
            "</blockquote>"
        )
        btn_style = get_user_button_style(uid)
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"fwd_back_{uid}", style=btn_style)]])
        try:
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        except Exception:
            pass
        return

    # ── GLOBAL ADS SET ──
    if action in ("gadsset", "gads"):
        is_inline = bool(cb.inline_message_id)
        mid = cb.message.id if cb.message else None
        inl_id = cb.inline_message_id if is_inline else None
        FPRO_WAITING_INPUT[uid] = {"action": "gads_set", "mid": mid, "inline_message_id": inl_id}
        text = (
            "<blockquote expandable>"
            "🧹 <b>Set Global Ad Keywords</b>\n"
            f"{'━' * 18}\n"
            "Kirim daftar kata kunci iklan yang ingin difilter (pisahkan dengan koma) <b>ke PM Bot ini</b>.\n\n"
            "<b>Contoh:</b> <code>promo,iklan,join</code>\n"
            f"{'━' * 18}"
            "</blockquote>"
        )
        btn_style = get_user_button_style(uid)
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data=f"fwd_back_{uid}", style=btn_style)]])
        try:
            if is_inline:
                await Altruix.bot.edit_inline_text(inline_message_id=inl_id, text=text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            else:
                await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        except Exception:
            pass
        return

    # ── GLOBAL WM SET ──
    if action in ("gwmset", "gwm"):
        is_inline = bool(cb.inline_message_id)
        mid = cb.message.id if cb.message else None
        inl_id = cb.inline_message_id if is_inline else None
        FPRO_WAITING_INPUT[uid] = {"action": "wm_set_text", "mid": mid, "inline_message_id": inl_id}
        text = (
            "<blockquote expandable>"
            "🖼 <b>Set Global Watermark</b>\n"
            f"{'━' * 18}\n"
            "Kirim teks watermark default (untuk semua task baru).\n\n"
            "<b>Contoh:</b> <code>@Altruix_Channel</code>\n"
            f"{'━' * 18}"
            "</blockquote>"
        )
        btn_style = get_user_button_style(uid)
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data=f"fwd_back_{uid}", style=btn_style)]])
        try:
            if is_inline:
                await Altruix.bot.edit_inline_text(inline_message_id=inl_id, text=text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            else:
                await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        except Exception:
            pass
        return
    
    # ── ADD TASK (STEP-BY-STEP) ──
    if action == "add":
        subaction = parts[2] if len(parts) > 2 else ""
        if subaction == "start":
            FPRO_ADD_TASK_STATE[uid] = {"step": 1}
            await cb.edit_message_text(
                "<blockquote expandable>➕ <b>Interactive Add Task</b>\n"
                f"{'━' * 18}\n"
                "Sistem akan memandu Anda secara bertahap.\n\n"
                "👤 <b>Langkah 1:</b> Silakan kirim <b>Source Chat ID</b>\n"
                "(Contoh: <code>-100123456789</code> atau forward pesan ke sini lalu ketik <code>.id</code>)</blockquote>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=f"fwd_add_cancel_{uid}")]])
            )
            return
        
        if subaction == "cancel":
            FPRO_ADD_TASK_STATE.pop(uid, None)
            await safe_cb_answer(cb, "❌ Add Task cancelled.", show_alert=True)
            text = await build_main_menu_text(uid, client=ub_client)
            gs = await get_global_settings(uid)
            kb = build_main_menu_kb(uid, gsettings=gs)
            await cb.edit_message_text(text, reply_markup=kb)
            return

        if subaction == "done":
            mode = parts[3] if len(parts) > 3 else "live"
            state = FPRO_ADD_TASK_STATE.pop(uid, None)
            if not state or "src" not in state or "tgt" not in state:
                return await safe_cb_answer(cb, "❌ Session expired or invalid.", show_alert=True)
            
            tid = await add_task(uid, state["src"], state["tgt"], mode=mode)
            if tid:
                await safe_cb_answer(cb, f"✅ Task #{tid} Created!", show_alert=True)
                task = await get_task(tid)
                text = await build_task_detail_text(task, client=ub_client)
                kb = build_task_detail_kb(task, uid)
                await cb.edit_message_text(text, reply_markup=kb)
            else:
                await cb.edit_message_text("❌ Failed to create task.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"fwd_back_{uid}")]]))
            return

    # ── ADD INFO ──
    if action == "addinfo":
        text = (
            "<blockquote expandable>"
            "➕ <b>Add Forward Task</b>\n"
            f"{'━' * 18}\n"
            "Gunakan format command berikut untuk menambah task:\n\n"
            "<code>.fwd add &lt;source&gt; &lt;target&gt; [mode]</code>\n\n"
            "<b>💡 TIPS DAPAT ID:</b>\n"
            "• Ketik <code>.id</code> di chat mana saja.\n"
            "• Forward pesan ke Userbot ini lalu ketik <code>.id</code>.\n"
            "• ID Channel biasanya diawali <code>-100...</code>\n\n"
            "<b>🔀 MODE:</b>\n"
            "• <code>live</code>: Forward real-time (default).\n"
            "• <code>batch</code>: Forward pesan lama (massal).\n\n"
            "<b>📝 CONTOH:</b>\n"
            "<code>.fwd add -100123 -100456 live</code>\n"
            f"{'━' * 18}"
            "</blockquote>"
        )
        btn_style = get_user_button_style(uid)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data=f"fwd_back_{uid}", style=btn_style)]
        ])
        try:
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        except Exception:
            pass
        return
    
    # ── GLOBAL FILTER MENU ──
    if action == "gfilter":
        gs = await get_global_settings(uid)
        text = (
            "<blockquote expandable>"
            "🌍 <b>Global Media Filter</b>\n"
            f"{'━' * 18}\n"
            "Atur jenis pesan yang diizinkan untuk diteruskan secara default (berlaku untuk task baru).\n\n"
            "🟢 = <b>Diizinkan</b>\n"
            "🔴 = <b>Diskip</b>\n"
            f"{'━' * 18}"
            "</blockquote>"
        )
        kb = build_filter_kb(gs, uid, is_global=True)
        try:
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        except Exception:
            pass
        return

    # ── GLOBAL ADV OPTS MENU ──
    if action == "gadvopts":
        gs = await get_global_settings(uid)
        text = (
            "<blockquote expandable>"
            "🛡 <b>Global Advanced Options</b>\n"
            f"{'━' * 18}\n"
            "Atur default untuk pengaturan lanjutan (berlaku untuk task baru).\n\n"
            "• <b>Regex Pro</b>: Gunakan pola regex kustom.\n"
            "• <b>Batch Order</b>: Urutan proses pesan dalam mode batch.\n"
            "• <b>Default Delay</b>: Jeda antar pesan.\n"
            f"{'━' * 18}"
            "</blockquote>"
        )
        kb = build_global_adv_opts_kb(gs, uid)
        
        # Add TR Language button to global
        kb.inline_keyboard.insert(-2, [InlineKeyboardButton("🌐 Set Global TR Lang", callback_data=f"fwd_gtrlang_{uid}", style=get_user_button_style(uid))])
        
        try:
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        except Exception:
            pass
        return

    # ── GLOBAL FILTER TOGGLE ──
    if action == "gftoggle":
        # fwd_gftoggle_{key}_{uid}
        key = parts[2]
        gs = await get_global_settings(uid)
        try:
            filt = json.loads(gs.get("default_filters", "{}"))
        except:
            filt = {}
        
        filt[key] = not filt.get(key, True)
        await update_global_settings(uid, default_filters=json.dumps(filt))
        
        await safe_cb_answer(cb, f"🔘 {key.title()}: {'ON' if filt[key] else 'OFF'}", show_alert=False)
        gs["default_filters"] = json.dumps(filt)
        
        # HOT RELOAD TEXT
        text = (
            "<blockquote expandable>"
            "🌍 <b>Global Media Filter</b>\n"
            f"{'━' * 18}\n"
            "Atur jenis pesan yang diizinkan untuk diteruskan secara default (berlaku untuk task baru).\n\n"
            "🟢 = <b>Diizinkan</b>\n"
            "🔴 = <b>Diskip</b>\n"
            f"{'━' * 18}"
            "</blockquote>"
        )
        kb = build_filter_kb(gs, uid, is_global=True)
        try:
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        except:
            pass
        return

    # ── GLOBAL BATCH ORDER TOGGLE ──
    if action == "gborder":
        gs = await get_global_settings(uid)
        cur = gs.get("default_batch_order", "oldest")
        new_val = "newest" if cur == "oldest" else "oldest"
        await update_global_settings(uid, default_batch_order=new_val)
        gs["default_batch_order"] = new_val
        
        await safe_cb_answer(cb, f"🔀 Global Order: {new_val.title()}", show_alert=False)
        
        # FIX: Stay in Global Adv Opts menu
        text = (
            "<blockquote expandable>"
            "🛡 <b>Global Advanced Options</b>\n"
            f"{'━' * 18}\n"
            "Atur default untuk pengaturan lanjutan (berlaku untuk task baru).\n\n"
            "• <b>Regex Pro</b>: Gunakan pola regex kustom.\n"
            "• <b>Batch Order</b>: Urutan proses pesan dalam mode batch.\n"
            "• <b>Default Delay</b>: Jeda antar pesan.\n"
            f"{'━' * 18}"
            "</blockquote>"
        )
        kb = build_global_adv_opts_kb(gs, uid)
        await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        return

    # ── REGEX SET (TASK / GLOBAL) ──
    if action in ("rexset", "grexset"):
        await safe_cb_answer(cb, "Loading...", show_alert=False)
        is_global = (action == "grexset")
        tid = int(parts[2]) if not is_global else 0
        
        is_inline = bool(cb.inline_message_id)
        mid = cb.message.id if cb.message else None
        inl_id = cb.inline_message_id if is_inline else None
        
        input_action = "grex_set_patterns" if is_global else "rex_set_patterns"
        FPRO_WAITING_INPUT[uid] = {"action": input_action, "tid": tid, "mid": mid, "inline_message_id": inl_id}
        
        scope = "Global" if is_global else f"Task #{tid}"
        text = (
            "<blockquote expandable>"
            f"📝 <b>Set {scope} Regex Patterns</b>\n"
            f"{'━' * 18}\n"
            f"Kirim pola regex dan penggantinya <b>ke PM Bot ini</b> dengan format:\n"
            f"<code>pattern|replacement</code>\n\n"
            f"Setiap baris adalah satu pola baru.\n"
            f"<b>Contoh:</b>\n"
            f"<code>Join us|Hapus yuk</code>\n"
            f"<code>@\\w+|[HIDDEN]</code>\n"
            f"{'━' * 18}"
            "</blockquote>"
        )
        
        try:
            btn_style = get_user_button_style(uid)
            back_cbd = f"fwd_back_{uid}" if is_global else f"fwd_advopts_{tid}_{uid}"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data=back_cbd, style=btn_style)]])
            
            if is_inline:
                await Altruix.bot.edit_inline_text(inline_message_id=inl_id, text=text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            else:
                await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        except Exception as e:
            logger.error(f"[Regex Config UI Error]: {e}")
            await safe_cb_answer(cb, f"Error displaying prompt: {str(e)[:30]}", show_alert=True)
        return
    
    # ── GLOBAL DELAY INC/DEC ──
    if action == "gdel":
        direction = parts[2] if len(parts) > 2 else ""
        gs = await get_global_settings(uid)
        delay = gs.get("default_delay", 1.5)
        if direction == "inc":
            delay = min(delay + 0.5, 30.0)
        elif direction == "dec":
            delay = max(delay - 0.5, 0.0)
        elif direction == "inc3":
            delay = min(delay + 3.0, 30.0)
        elif direction == "dec3":
            delay = max(delay - 3.0, 0.0)
            
        await update_global_settings(uid, default_delay=delay)
        gs["default_delay"] = delay
        
        # FIX: Stay in Global Adv Opts menu
        text = (
            "<blockquote expandable>"
            "🛡 <b>Global Advanced Options</b>\n"
            f"{'━' * 18}\n"
            "Atur default untuk pengaturan lanjutan (berlaku untuk task baru).\n\n"
            "• <b>Regex Pro</b>: Gunakan pola regex kustom.\n"
            "• <b>Batch Order</b>: Urutan proses pesan dalam mode batch.\n"
            "• <b>Default Delay</b>: Jeda antar pesan.\n"
            f"{'━' * 18}"
            "</blockquote>"
        )
        kb = build_global_adv_opts_kb(gs, uid)
        try:
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        except Exception:
            pass
        await safe_cb_answer(cb, f"⏱ Global Delay: {delay}s", show_alert=False)
        return
    
    # ── SET LOG CHANNEL ──
    if action == "glog":
        is_inline = bool(cb.inline_message_id)
        mid = cb.message.id if cb.message else None
        inl_id = cb.inline_message_id if is_inline else None
        
        FPRO_WAITING_INPUT[uid] = {"action": "glog_set", "mid": mid, "inline_message_id": inl_id}
        
        text = (
            "<blockquote expandable>"
            "📢 <b>Set Log Channel</b>\n"
            f"{'━' * 18}\n"
            "Kirim <b>Chat ID</b> untuk channel log ke PM Bot ini.\n\n"
            "Channel ini akan menerima laporan proses forwarding.\n"
            "<b>Contoh:</b> <code>-100123456789</code>\n"
            f"{'━' * 18}"
            "</blockquote>"
        )
        btn_style = get_user_button_style(uid)
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data=f"fwd_back_{uid}", style=btn_style)]])
        
        try:
            if is_inline:
                await Altruix.bot.edit_inline_text(inline_message_id=inl_id, text=text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            else:
                await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        except:
            pass
        return
    
    # ── TASK DETAIL ──
    if action == "detail":
        tid = int(parts[2]) if len(parts) > 2 else 0
        task = await get_task(tid)
        if not task or task["user_id"] != uid:
            return await safe_cb_answer(cb, "❌ Task not found.", show_alert=True)
        
        text = await build_task_detail_text(task, client=ub_client)
        kb = build_task_detail_kb(task, uid)
        try:
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        except Exception:
            pass
        return
    
    # ── START TASK ──
    if action == "start":
        tid = int(parts[2]) if len(parts) > 2 else 0
        task = await get_task(tid)
        if not task or task["user_id"] != uid:
            return await safe_cb_answer(cb, "❌ Task not found.", show_alert=True)
        
        await update_task(tid, is_active=1)
        task["is_active"] = 1
        
        # If live mode, register the listener
        if task["mode"] == "live" and ub_client:
            asyncio.create_task(_register_live_listener(ub_client, task, uid))
        
        await safe_cb_answer(cb, f"▶️ Task #{tid} started!", show_alert=True)
        
        text = await build_task_detail_text(task, client=ub_client)
        kb = build_task_detail_kb(task, uid)
        try:
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        except Exception:
            pass
        return
    
    # ── STOP TASK ──
    if action == "stop":
        tid = int(parts[2]) if len(parts) > 2 else 0
        task = await get_task(tid)
        if not task or task["user_id"] != uid:
            return await safe_cb_answer(cb, "❌ Task not found.", show_alert=True)
        
        await update_task(tid, is_active=0)
        task["is_active"] = 0
        
        # Remove live listener if exists
        _unregister_live_listener(tid)
        
        await safe_cb_answer(cb, f"⏹ Task #{tid} stopped!", show_alert=True)
        
        text = await build_task_detail_text(task, client=ub_client)
        kb = build_task_detail_kb(task, uid)
        try:
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        except Exception:
            pass
        return

    # ── BATCH RANGE PROMPT ──
    if action == "btchrange":
        tid = int(parts[2]) if len(parts) > 2 else 0
        task = await get_task(tid)
        if not task:
            return await safe_cb_answer(cb, "❌ Task not found.", show_alert=True)
            
        text = (
            "<blockquote expandable>"
            f"🚀 <b>Batch Forward — Task #{tid}</b>\n"
            f"{'━' * 18}\n"
            "Silakan balas pesan ini atau kirim command berikut untuk memulai batch:\n\n"
            f"<code>.fwd run {tid} &lt;start_id&gt; &lt;end_id&gt;</code>\n\n"
            "<b>Contoh:</b>\n"
            f"<code>.fwd run {tid} 100 200</code>\n"
            f"{'━' * 18}"
            "</blockquote>"
        )
        btn_style = get_user_button_style(uid)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data=f"fwd_detail_{tid}_{uid}", style=btn_style)]
        ])
        try:
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        except Exception:
            pass
        return
    
    # ── TOGGLE BYPASS ──
    if action == "bypass":
        tid = int(parts[2]) if len(parts) > 2 else 0
        task = await get_task(tid)
        if not task or task["user_id"] != uid:
            return await safe_cb_answer(cb, "❌ Task not found.", show_alert=True)
        
        new_val = 0 if task.get("bypass_protected") else 1
        await update_task(tid, bypass_protected=new_val)
        task["bypass_protected"] = new_val
        
        status = "ON" if new_val else "OFF"
        await safe_cb_answer(cb, f"🛡 Bypass Protected: {status}", show_alert=False)
        
        text = await build_task_detail_text(task, client=ub_client)
        kb = build_task_detail_kb(task, uid)
        try:
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        except Exception:
            pass
        return
    
    # ── TOGGLE MODE ──
    if action == "mode":
        tid = int(parts[2]) if len(parts) > 2 else 0
        task = await get_task(tid)
        if not task or task["user_id"] != uid:
            return await safe_cb_answer(cb, "❌ Task not found.", show_alert=True)
        
        new_mode = "batch" if task["mode"] == "live" else "live"
        await update_task(tid, mode=new_mode)
        task["mode"] = new_mode
        
        # If task was active and mode changed, we need to re-register
        if task["is_active"]:
            _unregister_live_listener(tid)
            if new_mode == "live" and ub_client:
                asyncio.create_task(_register_live_listener(ub_client, task, uid))
        
        mode_icon = "📡 Live" if new_mode == "live" else "📦 Batch"
        await safe_cb_answer(cb, f"🔀 Mode: {mode_icon}", show_alert=False)
        
        text = await build_task_detail_text(task, client=ub_client)
        kb = build_task_detail_kb(task, uid)
        try:
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        except Exception:
            pass
        return
    
    # ── DELETE CONFIRMATION ──
    if action == "delconf":
        tid = int(parts[2]) if len(parts) > 2 else 0
        btn_style = get_user_button_style(uid)
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Yes, Delete", callback_data=f"fwd_delyes_{tid}_{uid}", style=btn_style),
                InlineKeyboardButton("❌ No", callback_data=f"fwd_detail_{tid}_{uid}", style=btn_style)
            ]
        ])
        try:
            await cb.edit_message_text(
                f"⚠️ <b>Are you sure you want to delete Task #{tid}?</b>\n\n"
                f"This action cannot be undone.",
                reply_markup=kb, parse_mode=enums.ParseMode.HTML
            )
        except Exception:
            pass
        return
    
    # ── DELETE YES ──
    if action == "delyes":
        tid = int(parts[2]) if len(parts) > 2 else 0
        task = await get_task(tid)
        if not task or task["user_id"] != uid:
            return await safe_cb_answer(cb, "❌ Task not found.", show_alert=True)
        
        _unregister_live_listener(tid)
        if await delete_task(tid):
            await safe_cb_answer(cb, f"🗑 Task #{tid} deleted!", show_alert=True)
        else:
            await safe_cb_answer(cb, "❌ Failed to delete.", show_alert=True)
        
        # Go back to list
        tasks = await get_tasks(uid)
        text = await build_task_list_text(uid, client=ub_client)
        kb = build_task_list_kb(uid, tasks)
        try:
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        except Exception:
            pass
        return
    
    # ── WM / TR TOGGLE ──
    if action in ("wmtoggle", "trtoggle"):
        tid = int(parts[2]) if len(parts) > 2 else 0
        task = await get_task(tid)
        if not task or task["user_id"] != uid:
            return await safe_cb_answer(cb, "❌ Task not found.", show_alert=True)

        field = "is_watermark" if action == "wmtoggle" else "is_translate"
        new_val = 0 if task.get(field) else 1
        await update_task(tid, **{field: new_val})
        task[field] = new_val
        
        label = "Watermark" if action == "wmtoggle" else "Translation"
        status = "ON" if new_val else "OFF"
        await safe_cb_answer(cb, f"🔘 {label}: {status}", show_alert=False)
        
        text = await build_task_detail_text(task, client=ub_client)
        kb = build_task_detail_kb(task, uid)
        try:
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        except Exception:
            pass
        return

    # ── TR LANGUAGE MENU (TASK / GLOBAL) ──
    if action in ("trlang", "gtrlang"):
        is_global = (action == "gtrlang")
        tid = int(parts[2]) if not is_global else 0
        
        langs = [
            ("id", "🇮🇩 Indonesian"), ("en", "🇺🇸 English"),
            ("ja", "🇯🇵 Japanese"), ("ko", "🇰🇷 Korean"),
            ("ar", "🇸🇦 Arabic"), ("ru", "🇷🇺 Russian"),
            ("de", "🇩🇪 German"), ("fr", "🇫🇷 French")
        ]
        
        scope = "Global" if is_global else f"Task #{tid}"
        text = f"<blockquote expandable>🌐 <b>Set {scope} Target Language</b>\n\nSilakan pilih bahasa target untuk fitur Auto-Translation:</blockquote>"
        
        btn_style = get_user_button_style(uid)
        rows = []
        for i in range(0, len(langs), 2):
            batch = langs[i:i+2]
            row = []
            for code, name in batch:
                cb_data = f"fwd_gtrset_{code}_{uid}" if is_global else f"fwd_trset_{tid}_{code}_{uid}"
                row.append(InlineKeyboardButton(name, callback_data=cb_data, style=btn_style))
            rows.append(row)
            
        back_cbd = f"fwd_gadvopts_{uid}" if is_global else f"fwd_advopts_{tid}_{uid}"
        rows.append([InlineKeyboardButton("🔙 Back", callback_data=back_cbd, style=btn_style)])
        
        await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows), parse_mode=enums.ParseMode.HTML)
        return

    # ── TR LANGUAGE SET (TASK / GLOBAL) ──
    if action in ("trset", "gtrset"):
        is_global = (action == "gtrset")
        if is_global:
            code = parts[2]
            await update_global_settings(uid, default_tr_lang=code)
            await safe_cb_answer(cb, f"✅ Global Language set to: {code.upper()}", show_alert=True)
            # Re-show Global Adv Opts
            gs = await get_global_settings(uid)
            text = (
                "<blockquote expandable>"
                "🛡 <b>Global Advanced Options</b>\n"
                f"{'━' * 18}\n"
                "Atur default untuk pengaturan lanjutan (berlaku untuk task baru).\n\n"
                "• <b>Regex Pro</b>: Gunakan pola regex kustom.\n"
                "• <b>Batch Order</b>: Urutan proses pesan dalam mode batch.\n"
                "• <b>Default Delay</b>: Jeda antar pesan.\n"
                f"{'━' * 18}"
                "</blockquote>"
            )
            kb = build_global_adv_opts_kb(gs, uid)
            kb.inline_keyboard.insert(-2, [InlineKeyboardButton("🌐 Set Global TR Lang", callback_data=f"fwd_gtrlang_{uid}", style=get_user_button_style(uid))])
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        else:
            tid = int(parts[2])
            code = parts[3]
            await update_task(tid, tr_lang=code)
            await safe_cb_answer(cb, f"✅ Task Language set to: {code.upper()}", show_alert=True)
            # Re-show Task Adv Opts
            task = await get_task(tid)
            text = await build_advanced_options_text(task)
            kb = build_advanced_options_kb(task, uid)
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        return

    # ── HELP PAGE ──
    if action == "help":
        # fwd_help_{page}_{uid}
        page = int(parts[2]) if len(parts) > 2 else 0
        text = build_info_text(page)
        btn_style = get_user_button_style(uid)
        
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("◀️", callback_data=f"fwd_help_{page-1}_{uid}" if page > 0 else f"fwd_noop_{uid}", style=btn_style),
                InlineKeyboardButton("▶️", callback_data=f"fwd_help_{page+1}_{uid}" if page < 3 else f"fwd_noop_{uid}", style=btn_style)
            ],
            [InlineKeyboardButton("📋 Show CMD", callback_data=f"fwd_showcmd_{uid}", style=btn_style)],
            [InlineKeyboardButton("🔙 Back", callback_data=f"fwd_back_{uid}", style=btn_style)]
        ])
        try:
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        except Exception:
            pass
        return

    # ── SHOW CMD ──
    if action == "showcmd":
        text = build_showcmd_text()
        btn_style = get_user_button_style(uid)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data=f"fwd_help_0_{uid}", style=btn_style)]
        ])
        try:
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        except Exception:
            pass
        return

    # ── ADS SET KEYWORDS ──
    if action == "adsset":
        tid = int(parts[2]) if len(parts) > 2 else 0
        task = await get_task(tid)
        if not task:
            return await safe_cb_answer(cb, "❌ Task not found.", show_alert=True)
        
        is_inline = bool(cb.inline_message_id)
        mid = cb.message.id if cb.message else None
        inl_id = cb.inline_message_id if is_inline else None
        
        FPRO_WAITING_INPUT[uid] = {"action": "ads_set_keywords", "task_id": tid, "mid": mid, "inline_message_id": inl_id}
        text = (
            "<blockquote expandable>"
            f"🚫 <b>Set Ad Keywords — Task #{tid}</b>\n"
            f"{'━' * 18}\n"
            "Kirim daftar kata kunci iklan untuk task ini (pisahkan dengan koma).\n\n"
            "<b>Contoh:</b> <code>promo,iklan,join</code>\n"
            f"{'━' * 18}"
            "</blockquote>"
        )
        btn_style = get_user_button_style(uid)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Cancel", callback_data=f"fwd_detail_{tid}_{uid}", style=btn_style)]
        ])
        try:
            if is_inline:
                await Altruix.bot.edit_inline_text(inline_message_id=inl_id, text=text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            else:
                await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        except Exception:
            pass
        return

    # ── WM SET TEXT ──
    if action == "wmset":
        tid = int(parts[2]) if len(parts) > 2 else 0
        task = await get_task(tid)
        if not task:
            return await safe_cb_answer(cb, "❌ Task not found.", show_alert=True)
            
        is_inline = bool(cb.inline_message_id)
        mid = cb.message.id if cb.message else None
        inl_id = cb.inline_message_id if is_inline else None
        
        FPRO_WAITING_INPUT[uid] = {"action": "wm_set_text", "task_id": tid, "mid": mid, "inline_message_id": inl_id}
        text = (
            "<blockquote expandable>"
            f"🖼 <b>Set Watermark — Task #{tid}</b>\n"
            f"{'━' * 18}\n"
            "Kirim teks watermark yang ingin digunakan untuk task ini.\n\n"
            "<b>Contoh:</b> <code>@My_Channel</code>\n"
            f"{'━' * 18}"
            "</blockquote>"
        )
        btn_style = get_user_button_style(uid)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Cancel", callback_data=f"fwd_detail_{tid}_{uid}", style=btn_style)]
        ])
        try:
            if is_inline:
                await Altruix.bot.edit_inline_text(inline_message_id=inl_id, text=text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            else:
                await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        except Exception:
            pass
        return
    
    # ── ADVANCED OPTIONS MENU ──
    if action == "advopts":
        tid = int(parts[2]) if len(parts) > 2 else 0
        task = await get_task(tid)
        if not task or task["user_id"] != uid:
            return await safe_cb_answer(cb, "❌ Task not found.", show_alert=True)
        
        text = await build_advanced_options_text(task)
        kb = build_advanced_options_kb(task, uid)
        try:
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        except Exception:
            pass
        return

    # ── ADVANCED TOGGLES (Links/Users/Ads) ──
    if action == "atoggle":
        # fwd_atoggle_{tid}_{field}_{uid}
        tid = int(parts[2]) if len(parts) > 2 else 0
        field = "_".join(parts[3:-1])
        task = await get_task(tid)
        
        valid_fields = ("clean_links", "clean_usernames", "is_ads_filter", "use_regex_pro", "forward_as_copy", "bypass_protected")
        if not task or task["user_id"] != uid or field not in valid_fields:
            return await safe_cb_answer(cb, "❌ Invalid action.", show_alert=True)
        
        new_val = 0 if task.get(field) else 1
        await update_task(tid, **{field: new_val})
        task[field] = new_val
        
        await safe_cb_answer(cb, f"🔘 {field.replace('_', ' ').title()}: {'ON' if new_val else 'OFF'}", show_alert=False)
        
        # Refresh view
        text = await build_advanced_options_text(task)
        kb = build_advanced_options_kb(task, uid)
        try:
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        except Exception:
            pass
        return

    # ── BATCH ORDER TOGGLE (TASK) ──
    if action == "border":
        tid = int(parts[2]) if len(parts) > 2 else 0
        task = await get_task(tid)
        if not task or task["user_id"] != uid:
            return await safe_cb_answer(cb, "❌ Task not found.", show_alert=True)
        
        cur = task.get("batch_order", "oldest")
        new_val = "newest" if cur == "oldest" else "oldest"
        await update_task(tid, batch_order=new_val)
        task["batch_order"] = new_val
        
        await safe_cb_answer(cb, f"🔀 Order: {new_val.title()}", show_alert=False)
        text = await build_advanced_options_text(task)
        kb = build_advanced_options_kb(task, uid)
        await cb.edit_message_text(text, reply_markup=kb)
        return

    # ── MEDIA FILTER TOGGLE (TASK) ──
    if action == "ftoggle":
        # fwd_ftoggle_{tid}_{key}_{uid}
        tid = int(parts[2])
        key = parts[3]
        task = await get_task(tid)
        if not task:
            return await safe_cb_answer(cb, "❌ Task not found.", show_alert=True)
            
        try:
            filt = json.loads(task.get("filters", "{}"))
        except:
            filt = {}
        
        filt[key] = not filt.get(key, True)
        await update_task(tid, filters=json.dumps(filt))
        task["filters"] = json.dumps(filt)
        
        await safe_cb_answer(cb, f"🔘 {key.title()}: {'ON' if filt[key] else 'OFF'}", show_alert=False)
        
        text = (
            "<blockquote expandable>"
            f"🔍 <b>Media Filter — Task #{tid}</b>\n"
            f"{'━' * 18}\n"
            "Atur jenis pesan yang diizinkan untuk diteruskan dalam task ini.\n\n"
            "🟢 = <b>Diizinkan</b>\n"
            "🔴 = <b>Diskip</b>\n"
            f"{'━' * 18}"
            "</blockquote>"
        )
        kb = build_filter_kb(task, uid)
        try:
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        except:
            pass
        return

    # ── MEDIA FILTER MENU (TASK) ──
    if action == "filter":
        tid = int(parts[2])
        task = await get_task(tid)
        if not task:
            return await safe_cb_answer(cb, "❌ Task not found.", show_alert=True)
        
        text = (
            "<blockquote expandable>"
            f"🔍 <b>Media Filter — Task #{tid}</b>\n"
            f"{'━' * 18}\n"
            "Atur jenis pesan yang diizinkan untuk diteruskan dalam task ini.\n\n"
            "🟢 = <b>Diizinkan</b>\n"
            "🔴 = <b>Diskip</b>\n"
            f"{'━' * 18}"
            "</blockquote>"
        )
        kb = build_filter_kb(task, uid)
        await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        return

    # ── BATCH DELAY ADJUST ──
    if action == "bdel":
        # fwd_bdel_{tid}_{dir}_{uid}
        tid = int(parts[2]) if len(parts) > 2 else 0
        direction = parts[3] if len(parts) > 3 else ""
        task = await get_task(tid)
        if not task:
            return await safe_cb_answer(cb, "❌ Task not found.", show_alert=True)
        
        delay = task.get("batch_delay", 1.5)
        if direction == "inc":
            delay = min(delay + 0.5, 30.0)
        elif direction == "dec":
            delay = max(delay - 0.5, 0.0)
        
        await update_task(tid, batch_delay=delay)
        task["batch_delay"] = delay
        
        text = await build_advanced_options_text(task)
        kb = build_advanced_options_kb(task, uid)
        try:
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        except Exception:
            pass
        await safe_cb_answer(cb, f"⏱ Batch Delay: {delay}s", show_alert=False)
        return

    # Pause / Resume / Stop Batch Control
    elif cb.data.startswith(("fwd_bpause_", "fwd_bresume_", "fwd_bstop_")):
        parts = cb.data.split("_")
        action = parts[1]
        try:
            tid = int(parts[2])
            cb_user_id = int(parts[-1])
        except:
            await cb.answer("Invalid callback format.", show_alert=True)
            return

        # Ensure user authorization
        if client.me.id != cb_user_id and cb.from_user.id != cb_user_id and cb.from_user.id not in SUDO_USERS and cb.from_user.id != OWNER_ID:
            await cb.answer("Not authorized to control this task.", show_alert=True)
            return

        if tid not in FWD_BATCH_CONTROL and action != "bstop":
            await cb.answer("Task not found or already finished.", show_alert=True)
            return
        
        if action == "bpause":
            FWD_BATCH_CONTROL[tid] = "paused"
            await cb.answer("Task paused.")
        elif action == "bresume":
            FWD_BATCH_CONTROL[tid] = "running"
            await cb.answer("Task resumed.")
        elif action == "bstop":
            FWD_BATCH_CONTROL[tid] = "stopped"
            await cb.answer("Task stopped.")
            
    # Confirm Bypass Forward_alert=False)
        return

    # ── CHAT INFO (LOGS) ──
    if action == "chatinfo":
        tid = int(parts[2])
        ctype = parts[3] # src or tgt
        task = await get_task(tid)
        if not task:
            return await safe_cb_answer(cb, "❌ Task not found.", show_alert=True)
        
        chat_id = task["source_id"] if ctype == "src" else task["target_id"]
        title = await resolve_chat_title(client, chat_id)
        
        msg = f"ℹ️ <b>Chat Info</b>\nID: <code>{chat_id}</code>\nTitle: {title}"
        await safe_cb_answer(cb, f"ID: {chat_id}\n{title}", show_alert=True)
        return

    # ── BPS CONFIRM & RESUME ──
    if action == "bpsconfirm":
        # fwd_bpsconfirm_{tid}_{start}_{end}_{uid}
        tid = int(parts[2])
        start = int(parts[3])
        end = int(parts[4])
        
        await update_task(tid, bypass_protected=1)
        FWD_BATCH_CONTROL[tid] = "running"
        
        await safe_cb_answer(cb, "🛡 Bypass Enabled! Resuming batch...", show_alert=True)
        try:
            await cb.message.delete()
        except:
            pass
        return



# ==================== LIVE FORWARDING ENGINE ====================

@log_errors
async def start_batch_fwd(client: Client, user_id: int, task_id: int, start_id: int, end_id: int):
    """Process a batch of messages for forwarding."""
    # Re-check session ownership
    if client.me.id != user_id:
        return

    task = await get_task(task_id)
    if not task:
        return
    
    source_id = task["source_id"]
    target_id = task["target_id"]
    bypass = bool(task.get("bypass_protected", False))
    
    filters = await _safe_json_loads(task.get("filters"))

    # Use task-specific delay or global default
    gs = await get_global_settings(user_id)
    base_delay = task.get("batch_delay") if task.get("batch_delay") is not None else gs.get("default_delay", 1.5)

    stats = {"success": 0, "failed": 0, "skipped": 0, "total": 0}
    
    # Determine order and message list
    msg_ids = list(range(start_id, end_id + 1))
    if task.get("batch_order") == "newest":
        msg_ids.reverse()
    stats["total"] = len(msg_ids)
    
    # Initialize control state
    FWD_BATCH_CONTROL[task_id] = "running"
    
    processed = 0
    media_found = set()
    btn_style = get_user_button_style(user_id)
    
    # 🔗 Generate URL Links
    src_link = await get_chat_link(client, source_id)
    tgt_link = await get_chat_link(client, target_id)

    # 🛡 Proactive Content Protection Check
    if not bypass:
        try:
            # Check chat object directly for protection setting
            chat_info = await client.get_chat(source_id)
            if chat_info and chat_info.has_protected_content:
                confirm_kb = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("🛡 Yes, Bypass", callback_data=f"fwd_bpsconfirm_{task_id}_{start_id}_{end_id}_{user_id}", style=btn_style),
                        InlineKeyboardButton("❌ Cancel", callback_data=f"fwd_bstop_{task_id}_{user_id}", style=btn_style)
                    ]
                ])
                await send_log(
                    f"⚠️ <b>Content Protection Detected — Task #{task_id}</b>\n"
                    f"This chat (<code>{source_id}</code>) has content protection enabled.\n"
                    f"Messages cannot be forwarded normally. Do you want to use **Bypass Forward**?",
                    client=client,
                    reply_markup=confirm_kb,
                    user_id=user_id
                )
                # Halt batch until confirmed
                FWD_BATCH_CONTROL[task_id] = "paused"
                # Fallthrough to start log, but loop will wait
        except Exception as e:
            logger.error(f"[ForwardPro] Protection check error: {e}")

    ctrl_kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📥 Source", url=src_link, style=btn_style),
            InlineKeyboardButton("📤 Target", url=tgt_link, style=btn_style)
        ],
        [
            InlineKeyboardButton("⏸ Pause", callback_data=f"fwd_bpause_{task_id}_{user_id}", style=btn_style),
            InlineKeyboardButton("▶️ Resume", callback_data=f"fwd_bresume_{task_id}_{user_id}", style=btn_style),
            InlineKeyboardButton("⏹ Stop", callback_data=f"fwd_bstop_{task_id}_{user_id}", style=btn_style)
        ]
    ])

    # Build clickable message links for range
    src_cid = str(source_id)[4:] if str(source_id).startswith("-100") else str(source_id)
    start_msg_link = f"https://t.me/c/{src_cid}/{start_id}"
    end_msg_link = f"https://t.me/c/{src_cid}/{end_id}"

    # Resolve chat titles for started log
    _src_title = await resolve_chat_title(client, source_id)
    _tgt_title = await resolve_chat_title(client, target_id)

    await send_log(
        f"<blockquote expandable>"
        f"📦 <b>Batch Started — Task #{task_id}</b>\n"
        f"{'━' * 18}\n"
        f"📥 Source: <code>{source_id}</code>\n"
        f"    ├ Chat: <b>{_src_title}</b>\n"
        f"📤 Target: <code>{target_id}</code>\n"
        f"    ├ Chat: <b>{_tgt_title}</b>\n"
        f"📊 Range: <a href='{start_msg_link}'>{start_id}</a> to <a href='{end_msg_link}'>{end_id}</a>\n"
        f"{'━' * 18}"
        f"</blockquote>",
        client=client,
        reply_markup=ctrl_kb,
        user_id=user_id
    )

    # ── Live Log State ──
    log_entries = []       # List of (icon, mid, m_type, reason_short)
    live_log_msg = None    # Current editable log message
    log_part = 1           # Current part number
    MAX_LOG_CHARS = 3800   # Leave room for header/footer within 4096 limit
    UPDATE_EVERY = 3       # Edit log every N messages to avoid flood

    def _build_live_log_text(entries, part, stats, total, ctrl_active=True):
        """Render the live updating batch log report."""
        header = (
            f"<blockquote expandable>"
            f"📋 <b>Batch Log — Task #{task_id}</b>"
        )
        if part > 1:
            header += f" <code>(Part {part})</code>"
        header += (
            f"\n{'━' * 18}\n"
            f"📊 <b>{stats['success'] + stats['failed'] + stats['skipped']}</b>/{total} "
            f"│ ✅ {stats['success']} │ ❌ {stats['failed']} │ ⏭ {stats['skipped']}\n"
            f"{'━' * 18}\n"
        )
        
        # Compact table of entries
        lines = ""
        for icon, eid, etype, ereason in entries:
            _link = f"https://t.me/c/{src_cid}/{eid}"
            short_reason = (ereason[:25] + "…") if len(ereason) > 26 else ereason
            lines += f"{icon} <a href='{_link}'>{eid}</a> │ {etype or '?'} │ <code>{short_reason}</code>\n"
        
        status_line = "🔄 <i>Processing...</i>" if ctrl_active else "🏁 <i>Completed</i>"
        footer = f"{'━' * 18}\n{status_line}</blockquote>"
        
        return header + lines + footer

    for mid in msg_ids:
        # Check control state
        while FWD_BATCH_CONTROL.get(task_id) == "paused":
            await asyncio.sleep(2)
        
        if FWD_BATCH_CONTROL.get(task_id) == "stopped":
            break

        # Re-fetch task config to catch 'Bypass Confirmation' or user setting changes
        task = await get_task(task_id)
        if not task: break
        bypass = bool(task.get("bypass_protected", False))
        filters = await _safe_json_loads(task.get("filters"))

        m_type = None  # Reset per iteration

        try:
            msg = await client.get_messages(source_id, mid)
            if not msg or msg.empty:
                stats["skipped"] += 1
                log_entries.append(("⏭", mid, "empty", "Deleted/Empty"))
            else:
                m_type = _get_message_type(msg)
                # Execute the forward logic
                success, reason = await _handle_fwd(client, msg, target_id, bypass, filters, task_cfg=task)
                
                if success:
                    stats["success"] += 1
                    if m_type:
                        media_found.add(m_type)
                    log_entries.append(("✅", mid, m_type or "?", reason))
                elif reason == "Filtered":
                    stats["skipped"] += 1
                    log_entries.append(("⏭", mid, m_type or "?", reason))
                elif reason == "Restricted content (Bypass OFF)":
                    stats["failed"] += 1
                    log_entries.append(("🛡", mid, m_type or "?", "Protected (BPS OFF)"))
                    # Reactive prompt for individual protected messages
                    if FWD_BATCH_CONTROL.get(task_id) != "paused":
                        FWD_BATCH_CONTROL[task_id] = "paused"
                        confirm_kb = InlineKeyboardMarkup([
                            [
                                InlineKeyboardButton("🛡 Yes, Bypass", callback_data=f"fwd_bpsconfirm_{task_id}_{start_id}_{end_id}_{user_id}", style=btn_style),
                                InlineKeyboardButton("❌ Cancel", callback_data=f"fwd_bstop_{task_id}_{user_id}", style=btn_style)
                            ]
                        ])
                        await send_log(
                            f"⚠️ <b>Content Protection Detected — Task #{task_id}</b>\n"
                            f"Msg <code>{mid}</code> in <code>{source_id}</code> is protected.\n"
                            f"Enable Bypass to resume?",
                            client=client,
                            reply_markup=confirm_kb,
                            user_id=user_id
                        )
                else:
                    stats["failed"] += 1
                    log_entries.append(("❌", mid, m_type or "?", reason))
            
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
            try:
                msg = await client.get_messages(source_id, mid)
                success, reason = await _handle_fwd(client, msg, target_id, bypass, filters, task_cfg=task)
                if success: 
                    stats["success"] += 1
                    log_entries.append(("✅", mid, m_type or "?", reason or "Retry OK"))
                else: 
                    stats["failed"] += 1
                    log_entries.append(("❌", mid, m_type or "?", reason or "Retry Fail"))
            except Exception as retry_err:
                stats["failed"] += 1
                log_entries.append(("❌", mid, "?", f"Retry: {str(retry_err)[:20]}"))
        except Exception as e:
            logger.error(f"[ForwardPro] Batch task #{task_id} msg {mid} err: {e}")
            stats["failed"] += 1
            log_entries.append(("❌", mid, "?", str(e)[:25]))

        # ── Update Live Log ──
        processed += 1
        if processed % UPDATE_EVERY == 0 or processed >= stats["total"]:
            log_text = _build_live_log_text(log_entries, log_part, stats, stats["total"])
            
            # Check if text is too long → start new part
            if len(log_text) > MAX_LOG_CHARS:
                # Finalize current part
                if live_log_msg:
                    final_text = _build_live_log_text(log_entries[:-1], log_part, stats, stats["total"], ctrl_active=False)
                    await edit_log(live_log_msg, final_text, client=client, reply_markup=ctrl_kb)
                
                # Start new part
                log_part += 1
                log_entries = log_entries[-1:]  # Keep only the latest entry
                live_log_msg = None
            
            log_text = _build_live_log_text(log_entries, log_part, stats, stats["total"])
            
            if live_log_msg:
                await edit_log(live_log_msg, log_text, client=client, reply_markup=ctrl_kb)
            else:
                live_log_msg = await send_log(log_text, client=client, reply_markup=ctrl_kb, user_id=user_id)

        # Batch Delay: user-configured delay + small jitter to avoid flood
        await asyncio.sleep(base_delay + random.uniform(0.5, 1.5))

    # ── Final update of live log ──
    if log_entries and live_log_msg:
        final_text = _build_live_log_text(log_entries, log_part, stats, stats["total"], ctrl_active=False)
        await edit_log(live_log_msg, final_text, client=client, reply_markup=ctrl_kb)
    elif log_entries and not live_log_msg:
        final_text = _build_live_log_text(log_entries, log_part, stats, stats["total"], ctrl_active=False)
        await send_log(final_text, client=client, reply_markup=ctrl_kb, user_id=user_id)

    # Cleanup control state
    FWD_BATCH_CONTROL.pop(task_id, None)

    # Resolve Titles for enhanced summary
    source_title = await resolve_chat_title(client, source_id)
    target_title = await resolve_chat_title(client, target_id)
    media_str = ", ".join(sorted(list(media_found))) if media_found else "none"
    
    end_kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📥 Source", url=src_link, style=btn_style),
            InlineKeyboardButton("📤 Target", url=tgt_link, style=btn_style)
        ]
    ])

    # Build clickable message links for end summary
    _src_cid = str(source_id)[4:] if str(source_id).startswith("-100") else str(source_id)
    _start_link = f"https://t.me/c/{_src_cid}/{start_id}"
    _end_link = f"https://t.me/c/{_src_cid}/{end_id}"

    # End summary
    status_icon = "🏁" if stats["success"] + stats["skipped"] + stats["failed"] >= stats["total"] else "⏹"
    summary = (
        f"<blockquote expandable>"
        f"{status_icon} <b>Batch {'Completed' if status_icon == '🏁' else 'Stopped'} — Task #{task_id}</b>\n"
        f"{'━' * 18}\n"
        f"📥 Source: <code>{source_id}</code>\n"
        f"    ├ Chat: <b>{source_title}</b>\n"
        f"📤 Target: <code>{target_id}</code>\n"
        f"    ├ Chat: <b>{target_title}</b>\n"
        f"📊 Range: <a href='{_start_link}'>{start_id}</a> to <a href='{_end_link}'>{end_id}</a>\n"
        f"🏷 msg: <code>{media_str}</code>\n"
        f"⏱ delay permsg: <b>{base_delay}s</b>\n"
        f"✅ Success: <b>{stats['success']}</b>\n"
        f"❌ Failed: <b>{stats['failed']}</b>\n"
        f"⏭️ Skipped: <b>{stats['skipped']}</b>\n"
        f"📊 Total: <b>{stats['total']}</b>\n"
        f"{'━' * 18}"
        f"</blockquote>"
    )
    await send_log(summary, client=client, reply_markup=end_kb, user_id=user_id)


async def _register_live_listener(client: Client, task: dict, user_id: int):
    """Register a live message handler for a forwarding task."""
    tid = task["id"]
    source_id = task["source_id"]
    
    # Remove existing listener if any
    _unregister_live_listener(tid)
    
    async def _live_forwarder(c: Client, msg: RawMessage):
        """Handle incoming messages from source chat and forward via central logic."""
        # Re-check session ownership
        if c.me.id != user_id:
            return

        # Re-check task configuration
        current_task = await get_task(tid)
        if not current_task or not current_task.get("is_active"):
            return
        
        # Apply delay (Custom task delay or Global default)
        gs = await get_global_settings(user_id)
        delay = current_task.get("batch_delay") if current_task.get("batch_delay") is not None else gs.get("default_delay", 1.5)
        
        if delay > 0:
            await asyncio.sleep(delay)
            
        # Tracker for protection notifications to avoid spam
        # FWD_LIVE_TASKS[tid]["last_bps_notif"] = timestamp
        
        try:
            # Use centralized forwarding logic (handles filters, cleaning, bypass, WM, Translate)
            success, reason = await _handle_fwd(
                c, msg, current_task["target_id"],
                bypass=bool(current_task.get("bypass_protected")),
                filters=await _safe_json_loads(current_task.get("filters")),
                task_cfg=current_task
            )
            
            if success:
                logger.info(f"[ForwardPro] Task #{tid}: Forwarded msg {msg.id} via {reason}")
                await send_log(
                    f"🟢 <b>Message Forwarded — Task #{tid}</b>\n"
                    f"📤 From: <code>{source_id}</code>\n"
                    f"📥 To: <code>{current_task['target_id']}</code>\n"
                    f"📄 Msg ID: <code>{msg.id}</code>\n"
                    f"⚡ Reason: <code>{reason}</code>",
                    client=c,
                    user_id=user_id
                )
            elif reason == "Restricted content (Bypass OFF)":
                # Detect protected content in live mode
                last_notif = FWD_LIVE_TASKS.get(tid, {}).get("last_bps_notif", 0)
                import time
                if time.time() - last_notif > 300: # Notify once every 5 minutes per task
                    FWD_LIVE_TASKS.setdefault(tid, {})["last_bps_notif"] = time.time()
                    btn_style = get_user_button_style(user_id)
                    confirm_kb = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("🛡 Yes, Bypass", callback_data=f"fwd_bpsconfirm_{tid}_0_0_{user_id}", style=btn_style),
                            InlineKeyboardButton("❌ Cancel", callback_data=f"fwd_stop_{tid}_{user_id}", style=btn_style)
                        ]
                    ])
                    await send_log(
                        f"🛡 <b>Protected Content Detected — Task #{tid}</b>\n"
                        f"Target chat (<code>{source_id}</code>) restricts content saving.\n"
                        f"Diteruskan live gagal because Bypass OFF. Aktifkan Bypass?",
                        client=c,
                        reply_markup=confirm_kb,
                        user_id=user_id
                    )

        except FloodWait as fw:
            await asyncio.sleep(fw.value + 2)
            await _handle_fwd(
                c, msg, current_task["target_id"], 
                bypass=bool(current_task.get("bypass_protected")),
                filters=await _safe_json_loads(current_task.get("filters")),
                task_cfg=current_task
            )
        except Exception as e:
            logger.error(f"[ForwardPro] Live forwarder #{tid} failed: {e}")
    
    # Create handler group to avoid conflicts
    handler_group = 100 + tid
    
    try:
        handler = client.on_message(
            filters.chat(source_id) & ~filters.service,
            group=handler_group
        )(_live_forwarder)
        
        FWD_LIVE_TASKS[tid] = {
            "client": client,
            "handler": _live_forwarder,
            "group": handler_group,
            "task": task,
        }
        logger.info(f"[ForwardPro] Live listener registered for task #{tid} (source: {source_id})")
    except Exception as e:
        logger.error(f"[ForwardPro] Failed to register live listener for task #{tid}: {e}")


def _unregister_live_listener(task_id: int):
    """Remove a live listener for a task."""
    info = FWD_LIVE_TASKS.pop(task_id, None)
    if info:
        try:
            client = info["client"]
            group = info["group"]
            handler = info["handler"]
            client.remove_handler(handler, group)
        except Exception as e:
            logger.debug(f"[ForwardPro] Unregister handler warning: {e}")
        logger.info(f"[ForwardPro] Live listener removed for task #{task_id}")


def _get_message_type(msg: RawMessage) -> str:
    """Detect the media type of a message."""
    if msg.photo:
        return "photo"
    elif msg.video:
        return "video"
    elif msg.audio:
        return "audio"
    elif msg.document:
        return "document"
    elif msg.sticker:
        return "sticker"
    elif msg.voice:
        return "voice"
    elif msg.animation:
        return "animation"
    elif msg.video_note:
        return "video_note"
    elif msg.text:
        return "text"
    return None


async def _copy_protected_message(client: Client, msg: RawMessage, target_id: int, clean_caption: str = None, watermark: str = None):
    """Copy a protected message by re-sending its content."""
    os.makedirs("./temp/", exist_ok=True)
    caption = clean_caption if clean_caption is not None else _clean_caption(msg.caption)
    
    try:
        path = None
        if msg.text:
            await client.send_message(target_id, caption or msg.text)
        elif msg.photo:
            path = await msg.download(file_name="./temp/")
            if watermark:
                path = await asyncio.to_thread(add_watermark_photo, path, watermark)
            await client.send_photo(target_id, path, caption=caption)
        elif msg.video:
            path = await msg.download(file_name="./temp/")
            if watermark:
                path = await asyncio.to_thread(add_watermark_video, path, watermark)
            await client.send_video(target_id, path, caption=caption)
        elif msg.animation:
            path = await msg.download(file_name="./temp/")
            await client.send_animation(target_id, path, caption=caption)
        elif msg.video_note:
            path = await msg.download(file_name="./temp/")
            await client.send_video_note(target_id, path)
        elif msg.audio:
            path = await msg.download(file_name="./temp/")
            await client.send_audio(target_id, path, caption=caption)
        elif msg.document:
            path = await msg.download(file_name="./temp/")
            await client.send_document(target_id, path, caption=caption)
        elif msg.voice:
            path = await msg.download(file_name="./temp/")
            await client.send_voice(target_id, path, caption=caption)
        elif msg.sticker:
            path = await msg.download(file_name="./temp/")
            await client.send_sticker(target_id, path)
        else:
            # Fallback: try copy_message (might still fail on restricted)
            await client.copy_message(target_id, msg.chat.id, msg.id)
        
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except:
                pass
                
    except Exception as e:
        logger.error(f"[ForwardPro] Copy processing failed: {e}")
        raise


def add_watermark_photo(file_path: str, text: str) -> str:
    """Add text watermark to a photo using Pillow (Blocking, use in to_thread)."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.open(file_path).convert("RGB")
        draw = ImageDraw.Draw(img)
        # Basic font selection
        try:
            font = ImageFont.truetype("arial.ttf", 36)
        except:
            font = ImageFont.load_default()
        
        # Position: bottom right
        w, h = img.size
        draw.text((w - 200, h - 50), text, fill=(255, 255, 255), font=font)
        
        out_path = str(Path(file_path).with_suffix(f".wm{Path(file_path).suffix}"))
        img.save(out_path, quality=95)
        img.close()
        if os.path.exists(file_path): os.remove(file_path)
        return out_path
    except Exception as e:
        logger.error(f"[ForwardPro] add_watermark_photo err: {e}")
        return file_path


def add_watermark_video(file_path: str, text: str) -> str:
    """Add text watermark to a video via PNG overlay (No ImageMagick needed)."""
    try:
        from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip
        from PIL import Image, ImageDraw, ImageFont
        
        video = VideoFileClip(file_path)
        vw, vh = video.size
        
        # 1. Create a transparent PNG overlay with PIL
        overlay_img = Image.new('RGBA', (vw, vh), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay_img)
        try:
            font = ImageFont.truetype("arial.ttf", int(vh * 0.05)) # Scale with resolution
        except:
            font = ImageFont.load_default()
            
        # Draw text at bottom right with shadow for visibility
        tw, th = draw.textsize(text, font=font) if hasattr(draw, 'textsize') else (200, 50)
        pos = (vw - tw - 20, vh - th - 20)
        draw.text((pos[0]+2, pos[1]+2), text, fill=(0,0,0,128), font=font) # Shadow
        draw.text(pos, text, fill=(255, 255, 255, 200), font=font)
        
        overlay_path = file_path + ".overlay.png"
        overlay_img.save(overlay_path)
        
        # 2. Use ImageClip to overlay
        txt_clip = ImageClip(overlay_path).set_duration(video.duration).set_position('center')
        
        # 3. Composite and Write
        result = CompositeVideoClip([video, txt_clip])
        out_path = str(Path(file_path).with_suffix(f".wm{Path(file_path).suffix}"))
        
        # Preset 'ultrafast' for bot speed
        result.write_videofile(out_path, codec='libx264', audio_codec='aac', logger=None, preset='ultrafast', threads=4)
        
        # Cleanup
        video.close()
        if os.path.exists(overlay_path): os.remove(overlay_path)
        if os.path.exists(file_path): os.remove(file_path)
        return out_path
    except Exception as e:
        logger.error(f"[ForwardPro] add_watermark_video err: {e}")
        return file_path
        
        video.close()
        if os.path.exists(file_path): os.remove(file_path)
        return out_path
    except Exception as e:
        logger.error(f"[ForwardPro] add_watermark_video err: {e}")
        return file_path


# ==================== STARTUP: RESTORE ACTIVE TASKS ====================

async def _restore_active_tasks():
    """On startup, re-register live listeners for all active tasks."""
    try:
        await auto_clear_temp()
        await asyncio.sleep(5)  # Reduced from 20s to prevent 'stuck' feeling
        await init_db()
        
        if not hasattr(Altruix, 'clients') or not Altruix.clients:
            logger.warning("[ForwardPro] No clients available for task restore")
            return
        
        # Get all active live tasks across all users
        import aiosqlite
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM fwd_tasks WHERE is_active = 1 AND mode = 'live'"
            )
            tasks = [dict(r) for r in await cursor.fetchall()]
        
        if not tasks:
            return
        
        logger.info(f"[ForwardPro] Restoring {len(tasks)} active task(s)...")
        
        for task in tasks:
            uid = task["user_id"]
            # Find matching client
            ub_client = None
            for cl in Altruix.clients:
                try:
                    if cl.me and cl.me.id == uid:
                        ub_client = cl
                        break
                except Exception:
                    continue
            
            if not ub_client:
                logger.warning(f"[ForwardPro] No client for uid {uid}, skipping task #{task['id']}")
                continue
            
            await _register_live_listener(ub_client, task, uid)
        
        logger.info(f"[ForwardPro] Task restoration complete")
        
        if LOG_CHAT_ID:
            bot = Altruix.bot
            if bot:
                try:
                    await bot.send_message(
                        LOG_CHAT_ID,
                        f"🔄 <b>Forward Pro:</b> Restored {len(tasks)} active task(s)"
                    )
                except Exception:
                    pass
    except Exception as e:
        logger.error(f"[ForwardPro] _restore_active_tasks failed: {e}")


async def auto_clear_temp():
    """Clear the ./temp/ folder on startup."""
    temp_dir = "./temp/"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir, exist_ok=True)
        return
    try:
        for f in os.listdir(temp_dir):
            path = os.path.join(temp_dir, f)
            if os.path.isfile(path):
                os.remove(path)
        logger.info("[ForwardPro] Temp folder cleared.")
    except Exception as e:
        logger.error(f"[ForwardPro] auto_clear_temp failed: {e}")


def _schedule_restore():
    """Schedule task restoration on plugin load."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(_restore_active_tasks())
        else:
            loop.call_soon(lambda: asyncio.create_task(_restore_active_tasks()))
    except Exception as e:
        logger.error(f"[ForwardPro] _schedule_restore failed: {e}")


# Auto-restore on plugin load
_schedule_restore()
