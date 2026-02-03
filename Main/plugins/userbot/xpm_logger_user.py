# pm_logger_user.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.

from Main import Altruix
from pyrogram import Client, filters, enums, filters
from pyrogram.types import (
    Message as RawMessage,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
    ReplyParameters
)
from Main.core.types.message import Message as AltruixMessage
from Main.core.decorators import log_errors
import os
import html
import logging
import time
import json
import asyncio
from pathlib import Path
import aiofiles
from datetime import datetime
import re
from collections import defaultdict
import psutil
from Main.utils.topic_utils import get_or_create_topic

# ─── LOGGER KHUSUS PLUGIN ───────────────────────────────────────────────


plugin_name = f"{os.path.basename(__file__)}"
__plugin_name__ = plugin_name if plugin_name else "pm_logger_user"

# --- LOGGER ---
logger = logging.getLogger("altruix.pm_logger_user")
logger.setLevel(logging.INFO)

PLUGIN_NAME = __plugin_name__ 
PLUGIN_VERSION = "1.3.6"  # ✅ Fixed CHANNEL_INVALID during topic creation
STORAGE_FILE = Path("pm_logger_user_settings.json")

# Settings Cache
PM_LOGGER_USER_DATA = {}
# Shared state from Altruix object (PERSISTENT across reloads)
PM_LOG_CACHE = Altruix.PM_LOG_CACHE
REPLY_AS_MENTIONED_WAITING = Altruix.REPLY_AS_MENTIONED_WAITING
USER_REPLY_COUNTS = Altruix.USER_REPLY_COUNTS
BUTTON_STATS = Altruix.BUTTON_STATS

# --- SESSION PERSISTENCE ---
SESSION_FILE = Path("pm_logger_sessions.json")

class SessionManager:
    @staticmethod
    def save():
        try:
            # We want to be sure everything is string-indexed for JSON
            to_save = {}
            for k, v in Altruix.REPLY_AS_MENTIONED_WAITING.items():
                to_save[str(k)] = v
                
            # Also save PM_LOG_CACHE
            cache_file = Path("pm_logger_cache.json")
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(Altruix.PM_LOG_CACHE, f, indent=4)
                
            logger.debug("SessionManager: Saved successfully.")
        except Exception as e:
            logger.error(f"SessionManager: Failed to save: {e}")

    @staticmethod
    def load():
        if SESSION_FILE.exists():
            try:
                with open(SESSION_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Merge but keep integer types if they exist or just rely on manager casting to str
                    Altruix.REPLY_AS_MENTIONED_WAITING.update(data)
                logger.info(f"SessionManager: Loaded {len(data)} sessions from {SESSION_FILE}")
            except Exception as e:
                logger.error(f"SessionManager: Failed to load sessions: {e}")
                
        cache_file = Path("pm_logger_cache.json")
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    c_data = json.load(f)
                    Altruix.PM_LOG_CACHE.update(c_data)
                logger.info(f"SessionManager: Loaded {len(c_data)} cache items from {cache_file}")
            except Exception as e:
                logger.error(f"SessionManager: Failed to load cache: {e}")
        
        # Cleanup: Remove old sessions with missing thread_id
        # These are from before the thread_id tracking was implemented
        cleaned_count = 0
        for session_id in list(Altruix.REPLY_AS_MENTIONED_WAITING.keys()):
            session_data = Altruix.REPLY_AS_MENTIONED_WAITING[session_id]
            # Remove sessions without thread_id (old sessions before patch)
            if session_data.get("thread_id") is None:
                del Altruix.REPLY_AS_MENTIONED_WAITING[session_id]
                cleaned_count += 1
        
        if cleaned_count > 0:
            logger.info(f"SessionManager: Cleaned {cleaned_count} old sessions (missing thread_id)")

# Load sessions on startup
SessionManager.load()

REPLY_FROM_ALL_ACCESSIBLE = True
REPLY_ACCESS_MODE = "sudo" # Default
USER_REPLY_LIMIT = 5

# Message Type Filters
PM_LOGGER_FILTERS = {
    "from_user": {
        "text": True,
        "photo": True,
        "video": True,
        "document": True,
        "audio": True,
        "voice": True,
        "sticker": True,
        "animation": True,
        "video_note": True,
    },
    "from_bot": {
        "text": True,   # Enabled for tools like SangMata
        "photo": True,
        "video": True,
        "document": True,
        "audio": True,
        "voice": True,
        "sticker": True,
        "animation": True,
        "video_note": True,
    }
}

DEFAULT_REACTION_EMOJIS = ["👍", "❤️", "🔥", "🥰", "👏", "🎉"]
VALID_REACTION_EMOJIS = {
    "👍", "👎", "❤️", "🔥", "🥰", "👏", "😁", "🤔", "🤯", "😱", 
    "🤬", "😢", "🎉", "🤩", "🤮", "💩", "🙏", "👌", "🕊", "🤡",
    "🥱", "🥴", "😍", "🐳", "❤️‍🔥", "🌚", "🌭", "💯", "🤣", "⚡",
    "🍌", "🏆", "💔", "🤨", "😐", " strawberry", "🍾", "💋", "🖕", "😈",
    "😴", "😭", "🤓", "ghost", "👨‍💻", "👀", "🎃", "🙈", "😇", "😨",
    "🤝", "✍️", "🤗", "🫡", "🎅", "🎄", "☃️", "💅", "🤪", "🗿",
    "🆒", "💘", "🙉", "🦄", "😘", "💊", "🙊", "😎", "👾", "🤷‍♂️",
    "🤷", "🤷‍♀️", "😡"
}

def is_valid_emoji(emoji: str) -> bool:
    return emoji in VALID_REACTION_EMOJIS

def get_permission_label(mode: str = "sudo") -> str:
    """Generate permission label for Reply button."""
    # Format: [ reply : (all/as mentioned/sudo user/owner/sudo+owner) ]
    # Default userbot logic usually allows Owner + Sudo
    
    if mode == "owner":
        return "Reply (Owner)"
    elif mode == "sudo":
        return "Reply (Sudo + Owner)"
    elif mode == "all":
        return "Reply (All)"
    else:
        return f"Reply ({mode})"

def get_shared_reply_mode():
    """Read reply mode from shared settings file."""
    try:
        if STORAGE_FILE.exists():
            with open(STORAGE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("reply_access_mode", "sudo")
    except:
        pass
    return REPLY_ACCESS_MODE

async def load_settings():
    global PM_LOGGER_USER_DATA, PM_LOGGER_FILTERS, REPLY_FROM_ALL_ACCESSIBLE, REPLY_ACCESS_MODE
    try:
        if STORAGE_FILE.exists():
            async with aiofiles.open(STORAGE_FILE, 'r', encoding='utf-8') as f:
                content = await f.read()
                if content.strip():
                    data = json.loads(content)
                    
                    # Supports both old and new structure
                    PM_LOGGER_USER_DATA = data.get("settings", {}) or data.get("sessions", {})
                    PM_LOGGER_FILTERS = data.get("filters", PM_LOGGER_FILTERS)
                    PM_LOGGER_FILTERS = data.get("filters", PM_LOGGER_FILTERS)
                    REPLY_FROM_ALL_ACCESSIBLE = data.get("reply_from_all_accessible", True)
                    REPLY_ACCESS_MODE = data.get("reply_access_mode", "sudo")
                    
                    # Ensure auto_create_topic exists
                    if "auto_create_topic" not in PM_LOGGER_USER_DATA:
                         PM_LOGGER_USER_DATA["auto_create_topic"] = False # Default Disable

    except Exception as e:
        logger.error(f"Failed to load PM Logger User settings: {e}")

async def save_settings():
    try:
        data = {
            "sessions": PM_LOGGER_USER_DATA,
            "filters": PM_LOGGER_FILTERS,
            "reply_from_all_accessible": REPLY_FROM_ALL_ACCESSIBLE,
            "reply_access_mode": REPLY_ACCESS_MODE,
            "version": PLUGIN_VERSION
        }
        async with aiofiles.open(STORAGE_FILE, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, indent=2))
    except Exception as e:
        logger.error(f"Failed to save PM Logger User settings: {e}")

# Call load_settings initially
asyncio.run_coroutine_threadsafe(load_settings(), asyncio.get_event_loop())

@Altruix.register_on_cmd(
    ["pmlu"],
    cmd_help={
        "help": "Manage PM Logger User settings.",
        "usage": ".pmlu",
        "example": ".pmlu",
    },
    group_only=False,
    requires_input=False,
)
@log_errors
async def pmlu_settings_handler(c: Client, m: AltruixMessage):
    """Handler for managing PM Logger User settings via interactive menu."""
    msg = await m.handle_message("PROCESSING")
    try:
        text, markup = generate_pmlu_menu(c.me.id)
        if markup:
            await msg.edit_msg(text, reply_markup=markup)
        else:
            await msg.edit_msg("❌ Failed to generate menu.")
    except Exception as e:
        logger.error(f"PMLU Settings Error: {e}")
        await msg.edit_msg(f"❌ Error: {str(e)[:100]}")

@Altruix.register_on_cmd(
    ["pmlstatus", "pmlustatus"],
    cmd_help={
        "help": "Check status of PM Logger User and Bot.",
        "usage": ".pmlstatus",
        "example": ".pmlstatus",
        "detail": "Lihat status aktif/nonaktif dan konfigurasi dari PM Logger User serta PM Logger Bot secara bersamaan."
    },
    group_only=False,
    requires_input=False,
)
@log_errors
async def pml_status_unified_handler(c: Client, m: AltruixMessage):
    await load_settings()
    user_id_str = str(c.me.id)
    session_settings = PM_LOGGER_USER_DATA.get(user_id_str, {})
    
    # User status
    is_globally_on = session_settings.get("enabled", PM_LOGGER_USER_DATA.get("enabled", False))
    log_from_user = session_settings.get("log_from_user", is_globally_on)
    log_from_bot = session_settings.get("log_from_bot", is_globally_on)
    
    # Bot assistant status
    try:
        from Main.plugins.bot.xpm_logger_bot import PM_LOGGER_BOT_DATA as B_DATA
        b_enabled = B_DATA.get("enabled", False)
    except:
        b_enabled = False
    
    u_status = "✅ ACTIVE" if log_from_user else "❌ INACTIVE"
    b_status = "✅ ACTIVE" if log_from_bot else "❌ INACTIVE"
    bot_assist_status = "✅ ACTIVE" if b_enabled else "❌ INACTIVE"
    ra_status = "✅ ACTIVE" if REPLY_FROM_ALL_ACCESSIBLE else "❌ INACTIVE"
    pml_global = "✅ ACTIVE" if (log_from_user or log_from_bot or b_enabled) else "❌ INACTIVE"
    log_chat = Altruix.log_chat or "⚠️ Not Configured"
    
    res = (
        f"🛡️ **PM LOGGER DETAILED STATUS**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Global PM Logger:** {pml_global}\n"
        f"• **Reply From All:** {ra_status}\n\n"
        f"📊 **Userbot Logging (Current):**\n"
        f"• **From Users:** {u_status}\n"
        f"• **From Bots:** {b_status}\n\n"
        f"🤖 **Bot Assistant Logging:**\n"
        f"• **Status:** {bot_assist_status}\n\n"
        f"⚙️ **Configuration:**\n"
        f"• **Log Group:** ` {log_chat} `\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Tip: Gunakan `.pmlu mode` untuk mengubah sumber logger."
    )
    await m.reply_msg(res)


@Altruix.on_message(
    filters.private & ~filters.me, group=0, bot_mode_unsupported=True
)
@log_errors
async def pm_logger_user_handler(c: Client, m: RawMessage):
    """Log incoming private messages."""
    try:
        # ✅ Dynamic Reload: Catch UI updates from settings.py
        await load_settings()
        
        user_id_str = str(c.me.id)
        
        # Resolve settings based on apply_type
        apply_type = PM_LOGGER_USER_DATA.get("apply_types", {}).get(user_id_str, "per_account")
        
        if apply_type == "global":
            session_settings = PM_LOGGER_USER_DATA.get("global_config", {})
        else:
            session_settings = PM_LOGGER_USER_DATA.get("sessions", {}).get(user_id_str)
            
        if session_settings is None:
            # Fallback to legacy global setting
            is_globally_on = PM_LOGGER_USER_DATA.get("enabled", False)
            log_from_user = is_globally_on
            log_from_bot = is_globally_on
            session_filters = {}
        elif isinstance(session_settings, bool):
            is_globally_on = session_settings
            log_from_user = is_globally_on
            log_from_bot = is_globally_on
            session_filters = {}
        else:
            is_globally_on = session_settings.get("enabled", False)
            log_from_user = session_settings.get("log_from_user", is_globally_on)
            log_from_bot = session_settings.get("log_from_bot", is_globally_on)
            log_from_bot = session_settings.get("log_from_bot", is_globally_on)
            session_filters = session_settings.get("filters", {})

        # ✅ Check Auto Create Topic Logic
        auto_create_topic = PM_LOGGER_USER_DATA.get("auto_create_topic", False) # Default Disable

        if not (log_from_user or log_from_bot):
            return

        if not Altruix.log_chat:
            return

        sender = m.from_user
        if not sender or sender.is_self:
            return

        # ✅ CAPTURE SANGMATA RESPONSE
        if sender.username == "SangMata_beta_bot":
            if c.me.id in Altruix.SANGMATA_WAITING:
                future = Altruix.SANGMATA_WAITING[c.me.id]
                if not future.done():
                    future.set_result(m)

        sender_id = sender.id
        sender_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip() or "Unknown"
        sender_username = f"@{sender.username}" if sender.username else "No Username"
        sender_hyperlink = f'<a href="tg://user?id={sender_id}">{html.escape(sender_name)}</a>'
        
        msg_type_str = "text"
        msg_text = ""
        if m.service:
            if m.service == enums.MessageServiceType.PHONE_CALL_ENDED:
                msg_type_str = "phone_call"
                msg_text = "📞 Phone Call Ended"
            else:
                return # Skip other service messages
        elif m.media:
            msg_type_str = m.media.value
            if msg_type_str == "animation": msg_type_str = "video"
            
        log_time = m.date.strftime("%Y-%m-%d %H:%M:%S")
        msg_text = m.text or m.caption or msg_text or "[Media]"

        # ✅ NEW: Message Type Filter Check (Bot vs User)
        is_bot = m.from_user.is_bot if m.from_user else False
        
        # ✅ Master Category Check
        if is_bot:
            if not log_from_bot: return
        else:
            if not log_from_user: return

        filter_key = "from_bot" if is_bot else "from_user"
        
        # Determine message type for filtering
        filter_msg_type = None
        if not m.media and m.text:
            filter_msg_type = "text"
        elif m.photo:
            filter_msg_type = "photo"
        elif m.video:
            filter_msg_type = "video"
        elif m.document:
            filter_msg_type = "document"
        elif m.audio:
            filter_msg_type = "audio"
        elif m.voice:
            filter_msg_type = "voice"
        elif m.sticker:
            filter_msg_type = "sticker"
        elif m.animation:
            filter_msg_type = "animation"
        elif m.video_note:
            filter_msg_type = "video_note"
        
        # ✅ Filter Check (Use pre-initialized session_filters)
        category_filters = session_filters.get(filter_key, PM_LOGGER_FILTERS.get(filter_key, {}))
        
        if filter_msg_type and not category_filters.get(filter_msg_type, True):
            return  # Skip logging this message type

        is_restricted = getattr(m, "has_protected_content", False)
        
        # Get file size if restricted
        size_str = ""
        if is_restricted:
            size = 0
            if m.document: size = m.document.file_size
            elif m.photo: size = m.photo.file_size
            elif m.video: size = m.video.file_size
            elif m.audio: size = m.audio.file_size
            elif m.voice: size = m.voice.file_size
            elif m.video_note: size = m.video_note.file_size
            elif m.animation: size = m.animation.file_size
            
            if size > 0:
                if size < 1024: size_str = f" ({size} B)"
                elif size < 1024*1024: size_str = f" ({size/1024:.2f} KB)"
                else: size_str = f" ({size/(1024*1024):.2f} MB)"

        log_content = (
            f"👤 <b>New PM Received (User)</b>\n"
        )
        if is_restricted:
            log_content += f"⚠️ <b>ini adalah restrict content dengan ukuran{size_str}</b>\n\n"
        else:
            log_content += "\n"

        log_content += (
            f"• <b>From:</b> {sender_hyperlink}\n"
            f"• <b>User ID:</b> <code>{sender_id}</code>\n"
            f"• <b>Username:</b> {sender_username}\n"
            f"• <b>To Account:</b> {c.me.mention}\n"
            f"• <b>Time:</b> <code>{log_time}</code>\n"
            f"• <b>Type:</b> <code>{msg_type_str.upper()}</code>\n"
            f"• <b>Message:</b>\n<blockquote>{html.escape(str(msg_text)[:1000])}</blockquote>"
        )

        # Get topic: "pm logger"
        topic_id = None
        if auto_create_topic:
            try:
                # Validate channel first to prevent CHANNEL_INVALID spam
                try:
                    chat_info = await Altruix.bot.get_chat(Altruix.log_chat)
                    # Only create topic if it's a forum
                    if getattr(chat_info, "is_forum", False):
                         topic_id = await get_or_create_topic(Altruix.bot, Altruix.log_chat, "pm logger", userbot_client=c)
                    else:
                         topic_id = None # Not a forum
                except Exception as e:
                     logger.warning(f"PMLU: Invalid Log Channel {Altruix.log_chat}: {e}")
                     return # Stop logging if channel invalid

            except Exception as e:
                logger.debug(f"PMLU Topic creation failed: {e}")
                topic_id = None
        else:
             # If auto create is disabled, check if standard topics exist or just send as normal message
             # For now, we set topic_id to None to send to General/Default
             topic_id = None

        # ─── BUTTONS ───
        # Main consolidated button using direct callback (skipping menu)
        p_label = get_permission_label(get_shared_reply_mode())
        keyboard = [
            [
                InlineKeyboardButton(f"💬 Reply ({p_label})", callback_data=f"pmlu_reply_{m.chat.id}_{m.id}_{c.me.id}"),
                InlineKeyboardButton("⚙️ Menu", callback_data=f"pmlu_toggle_full_{m.chat.id}_{m.id}_{c.me.id}")
            ],
            [
                InlineKeyboardButton("👤 User", url=f"tg://user?id={sender_id}"),
                InlineKeyboardButton("📂 Save", callback_data=f"pmlu_save_{m.chat.id}_{m.id}_{c.me.id}")
            ]
        ]
        
        if is_restricted:
            keyboard[1].append(InlineKeyboardButton("🚀 Bypass/Force Forward", callback_data=f"pmlu_force_fwd_{m.chat.id}_{m.id}_{c.me.id}"))

        # Forward message to topic
        fwd_msg = None
        if Altruix.log_chat:
            try:
                fwd_msg = await c.forward_messages(Altruix.log_chat, m.chat.id, m.id, message_thread_id=topic_id)
            except Exception as e:
                logger.debug(f"PMLU Forward failed: {e}")
        
        if not fwd_msg and not Altruix.log_chat:
            return

        # Send Detailed Info as a reply to the forwarded message in topic
        try:
            bot = Altruix.bot_manager.get_bot(c.me.id)
            sent_log = await bot.send_message(
                Altruix.log_chat,
                log_content,
                parse_mode=enums.ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard),
                reply_to_message_id=fwd_msg.id if fwd_msg else None,
                message_thread_id=topic_id
            )
            
            # Cache for recovery - capture ACTUAL thread_id from sent message
            actual_thread_id = getattr(sent_log, "message_thread_id", None)
            PM_LOG_CACHE[f"{m.chat.id}_{m.id}"] = {
                "client_id": c.me.id,
                "log_msg_id": sent_log.id,
                "fwd_msg_id": fwd_msg.id if fwd_msg else None,
                "thread_id": actual_thread_id,
                "chat_id": m.chat.id,
                "msg_id": m.id,
                "last_reply_id": None
            }
        except Exception as e:
            if "CHANNEL_INVALID" in str(e) or "PEER_ID_INVALID" in str(e):
                logger.warning(f"PMLU Error: Invalid Log Channel {Altruix.log_chat}. Disabling Logger.")
                # Auto-disable to prevent spam
                PM_LOGGER_USER_DATA["enabled"] = False
                await save_settings()
                try:
                    await c.send_message(
                        "me", 
                        f"⚠️ **PMLU DISABLED**\n\nLog Channel (`{Altruix.log_chat}`) tidak valid/tidak dapat diakses.\nLogger dimatikan otomatis untuk mencegah error berulang."
                    )
                except:
                    pass
            else:
                logger.error(f"PMLU Log send failed: {e}")

        # Save both sessions and cache
        SessionManager.save()

    except Exception as e:
        if "CHANNEL_INVALID" in str(e):
             # Silently catch CHANNEL_INVALID to prevent spamming logs
             logger.warning(f"PM Logger User: Target channel/topic is invalid: {e}")
        else:
             logger.error(f"Error in PM Logger User: {e}")

@Altruix.on_edited_message(
    filters.private & ~filters.me, group=0, bot_mode_unsupported=True
)
@log_errors
async def pm_logger_user_edit_handler(c: Client, m: RawMessage):
    """Update log when a message is edited."""
    try:
        if not PM_LOGGER_USER_DATA.get("enabled", False):
            return

        msg_key = f"{m.chat.id}_{m.id}"
        cache = PM_LOG_CACHE.get(msg_key)
        if not cache:
            return

        log_msg_id = cache.get("log_msg_id")
        if not log_msg_id:
            return

        sender = m.from_user
        sender_id = sender.id
        sender_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip() or "Unknown"
        sender_username = f"@{sender.username}" if sender.username else "No Username"
        sender_hyperlink = f'<a href="tg://user?id={sender_id}">{html.escape(sender_name)}</a>'
        
        msg_text = m.text or m.caption or "[No text/media caption]"
        msg_type = m.media.value if m.media else "text"
        
        log_time = m.date.strftime("%Y-%m-%d %H:%M:%S")
        edit_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        log_content = (
            f"👤 <b>New PM Received (User) [EDITED]</b>\n\n"
            f"• <b>From:</b> {sender_hyperlink}\n"
            f"• <b>User ID:</b> <code>{sender_id}</code>\n"
            f"• <b>Username:</b> {sender_username}\n"
            f"• <b>To Account:</b> {c.me.mention}\n"
            f"• <b>Time Original:</b> <code>{log_time}</code>\n"
            f"• <b>Time Edited:</b> <code>{edit_time}</code>\n"
            f"• <b>Type:</b> <code>{msg_type}</code>\n"
            f"• <b>New Message:</b>\n<blockquote>{html.escape(str(msg_text)[:1000])}</blockquote>"
        )

        # Preserve the reply_markup by fetching it
        bot = Altruix.bot_manager.get_bot(c.me.id)
        try:
            old_msg = await bot.get_messages(Altruix.log_chat, log_msg_id)
            markup = old_msg.reply_markup if old_msg else None
        except:
            markup = None

        await bot.edit_message_text(
            Altruix.log_chat,
            log_msg_id,
            log_content,
            parse_mode=enums.ParseMode.HTML,
            reply_markup=markup
        )
        # Actually we need to keep the original reply_markup
        # But we can't easily get it without fetching the message again
        # Let's just edit text first or try to re-fetch if needed.
        # Most of the time we can just assume the buttons are the same.
        
    except Exception as e:
        logger.error(f"Error in PM Logger User Edit: {e}")

# ✅ NEW: Interactive Config Handlers with Client ID Support

def generate_pmlu_menu(client_id):
    """Generates the PM Logger configuration menu for a specific client ID."""
    try:
        user_id = str(client_id)
        
        is_enabled = PM_LOGGER_USER_DATA.get("enabled", False)
        status = "ENABLED ✅" if is_enabled else "DISABLED ❌"
        mode = PM_LOGGER_USER_DATA.get("mode", "both").upper()
        ra_status = "ENABLED ✅" if REPLY_FROM_ALL_ACCESSIBLE else "DISABLED ❌"
        log_chat = Altruix.log_chat or "Not Configured ⚠️"
        
        apply_val = PM_LOGGER_USER_DATA.get("apply_types", {}).get(user_id, "per_account").upper().replace('_', ' ')
        auto_topic = PM_LOGGER_USER_DATA.get("auto_create_topic", False) # Default False
        auto_topic_val = "ENABLED" if auto_topic else "DISABLED"
        auto_topic_btn = "ON" if auto_topic else "OFF"
        
        # Check if bot can actually send to log_chat (Basic Check)
        bot_access = "OK ✅" if Altruix.log_chat else "N/A"

        buttons = [
             [
                 InlineKeyboardButton(f"Status: {status}", callback_data=f"pmlu_cfg_toggle_enable_{client_id}"),
                 InlineKeyboardButton(f"Mode: {mode}", callback_data=f"pmlu_cfg_toggle_mode_{client_id}")
             ],
             [
                 InlineKeyboardButton(f"Apply Type: {apply_val}", callback_data=f"pmlu_cfg_toggle_apply_{client_id}"),
                 InlineKeyboardButton(f"Auto Topic: {auto_topic_btn}", callback_data=f"pmlu_cfg_toggle_autotopic_{client_id}")
             ],
             [
                 InlineKeyboardButton(f"ReplyAll: {ra_status}", callback_data=f"pmlu_cfg_toggle_replyall_{client_id}"),
             ],
             [
                 InlineKeyboardButton("❌ Close", callback_data="bot_controls_menu") # Back to Bot Controls if opened from there
             ]
        ]
        
        res = (
            f"📊 **PM Logger Configuration (Client {client_id})**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• **Status:** {status}\n"
            f"• **Logger Mode:** `{mode}`\n"
            f"• **Apply Type:** `{PM_LOGGER_USER_DATA.get('apply_types', {}).get(user_id, 'per_account')}`\n"
            f"• **Auto Topic:** {auto_topic_val}\n"
            f"• **Reply From All:** {ra_status}\n"
            f"• **Log Group:** ` {log_chat} `\n"
            f"• **Bot Access:** {bot_access}\n\n"
            f"<i>Click buttons below to change settings.</i>"
        )
        return res, InlineKeyboardMarkup(buttons)
    except Exception as e:
        logger.error(f"Menu gen error: {e}")
        return f"Error: {e}", None

@Altruix.bot.on_callback_query(filters.regex(r"^open_pmlu_settings_owner$"))
@log_errors
async def open_pmlu_settings_owner_handler(c: Client, cb: CallbackQuery):
    try:
        from Main.utils.access_control import is_authorized_user
        if not is_authorized_user(cb.from_user.id, Altruix.config.OWNER_ID, Altruix.config.SUDO_USERS):
            return await cb.answer("⛔ Akses Ditolak!", show_alert=True)
            
        await cb.answer()
        owner_id = Altruix.config.OWNER_ID
        text, markup = generate_pmlu_menu(owner_id)
        if markup:
            await Altruix.edit_cb(cb, text, reply_markup=markup, parse_mode=enums.ParseMode.HTML)
        else:
            await cb.answer("Failed to generate menu", show_alert=True)
            
    except Exception as e:
        logger.error(f"Failed to open PMLU settings: {e}")
        await cb.answer(f"Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlu_cfg_(toggle_enable|toggle_mode|toggle_replyall|toggle_autotopic|toggle_apply)(?:_(\d+))?$"))
@log_errors
async def pmlu_config_callback(c: Client, cb: CallbackQuery):
    try:
        from Main.utils.access_control import is_authorized_user
        if not is_authorized_user(cb.from_user.id, Altruix.config.OWNER_ID, Altruix.config.SUDO_USERS):
            return await cb.answer("⛔ Akses Ditolak!", show_alert=True)
            
        action = cb.matches[0].group(1)
        # Get Client ID from callback data or default to Bot ID
        client_id = int(cb.matches[0].group(2)) if cb.matches[0].group(2) else c.me.id
        
        await load_settings() # Refresh data
        
        text = "Updated"
        
        if action == "toggle_enable":
            current = PM_LOGGER_USER_DATA.get("enabled", False)
            PM_LOGGER_USER_DATA["enabled"] = not current
            text = "✅ PM Logger Enabled" if not current else "❌ PM Logger Disabled"
            
        elif action == "toggle_mode":
            modes = ["user", "bot", "both"]
            current = PM_LOGGER_USER_DATA.get("mode", "both")
            try:
                idx = modes.index(current)
            except: idx = 2
            new_mode = modes[(idx + 1) % len(modes)]
            PM_LOGGER_USER_DATA["mode"] = new_mode
            text = f"🔄 Mode set to: {new_mode.upper()}"
            
        elif action == "toggle_replyall":
            global REPLY_FROM_ALL_ACCESSIBLE
            REPLY_FROM_ALL_ACCESSIBLE = not REPLY_FROM_ALL_ACCESSIBLE
            text = f"🔄 Reply From All: {'ACCESSIBLE' if REPLY_FROM_ALL_ACCESSIBLE else 'RESTRICTED'}"
            
        elif action == "toggle_autotopic":
            current = PM_LOGGER_USER_DATA.get("auto_create_topic", False) # Default to False if missing
            PM_LOGGER_USER_DATA["auto_create_topic"] = not current
            text = f"🔄 Auto Topic: {'ENABLED' if not current else 'DISABLED'}"
            
        elif action == "toggle_apply":
            # Toggle global/per_account for SPECIFIC client
            user_id = str(client_id)
            if "apply_types" not in PM_LOGGER_USER_DATA:
                PM_LOGGER_USER_DATA["apply_types"] = {}
                
            current = PM_LOGGER_USER_DATA["apply_types"].get(user_id, "per_account")
            new_type = "global" if current == "per_account" else "per_account"
            PM_LOGGER_USER_DATA["apply_types"][user_id] = new_type
            text = f"🔄 Apply Type for {client_id}: {new_type.upper().replace('_', ' ')}"

        await save_settings()
        await cb.answer(text)
        
        # Refresh menu
        text, markup = generate_pmlu_menu(client_id)
        if markup:
            await Altruix.edit_cb(cb, text, reply_markup=markup, parse_mode=enums.ParseMode.HTML)
                
    except Exception as e:
        logger.error(f"PMLU Config Error: {e}")
        await cb.answer(f"Error: {str(e)[:50]}", show_alert=True)

# Callback Handlers for PMLU
@Altruix.bot.on_callback_query(filters.regex(r"^pmlu_react_"))
@log_errors
async def pmlu_react_callback(c: Client, cb: CallbackQuery):
    try:
        from Main.utils.access_control import is_authorized_user
        if not is_authorized_user(cb.from_user.id, Altruix.config.OWNER_ID, Altruix.config.SUDO_USERS):
            return await cb.answer("⛔ Akses Ditolak!", show_alert=True)

        data = cb.data.split("_")
        chat_id, msg_id, client_id, emoji = int(data[2]), int(data[3]), int(data[4]), data[5]
        
        target_client = None
        for client in Altruix.clients:
            if client.me and client.me.id == client_id:
                target_client = client
                break
        
        if not target_client:
            await cb.answer("❌ Client session not found.", show_alert=True)
            return
            
        await target_client.send_reaction(chat_id, msg_id, emoji)
        await cb.answer(f"✅ Reacted with {emoji}")
    except Exception as e:
        await cb.answer(f"❌ Error: {str(e)}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlu_unreact_"))
@log_errors
async def pmlu_unreact_callback(c: Client, cb: CallbackQuery):
    try:
        from Main.utils.access_control import is_authorized_user
        if not is_authorized_user(cb.from_user.id, Altruix.config.OWNER_ID, Altruix.config.SUDO_USERS):
            return await cb.answer("⛔ Akses Ditolak!", show_alert=True)

        data = cb.data.split("_")
        chat_id, msg_id, client_id = int(data[2]), int(data[3]), int(data[4])
        
        target_client = None
        for client in Altruix.clients:
            if client.me and client.me.id == client_id:
                target_client = client
                break
        
        if not target_client:
            await cb.answer("❌ Client session not found.", show_alert=True)
            return
            
        await target_client.send_reaction(chat_id, msg_id, None)
        await cb.answer("✅ Reaction removed")
    except Exception as e:
        await cb.answer(f"❌ Error: {str(e)}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlu_save_"))
@log_errors
async def pmlu_save_callback(c: Client, cb: CallbackQuery):
    try:
        from Main.utils.access_control import is_authorized_user
        if not is_authorized_user(cb.from_user.id, Altruix.config.OWNER_ID, Altruix.config.SUDO_USERS):
            return await cb.answer("⛔ Akses Ditolak!", show_alert=True)

        data = cb.data.split("_")
        chat_id, msg_id, client_id = int(data[2]), int(data[3]), int(data[4])
        
        target_client = None
        for client in Altruix.clients:
            if client.me and client.me.id == client_id:
                target_client = client
                break
        
        if not target_client or not target_client.is_connected:
            return await cb.answer("❌ Account not connected/found.", show_alert=True)
            
        # Forward message again to log group
        await target_client.forward_messages(Altruix.log_chat, chat_id, msg_id)
        await cb.answer("✅ Message forwarded again to log group!", show_alert=True)
    except Exception as e:
        logger.error(f"PMLU Save callback error: {e}")

@Altruix.bot.on_callback_query(filters.regex(r"^pmlu_force_fwd_"))
@log_errors
async def pmlu_force_fwd_callback(c: Client, cb: CallbackQuery):
    try:
        from Main.utils.access_control import is_authorized_user
        if not is_authorized_user(cb.from_user.id, Altruix.config.OWNER_ID, Altruix.config.SUDO_USERS):
            return await cb.answer("⛔ Akses Ditolak!", show_alert=True)

        data = cb.data.split("_")
        # pmlu_force_fwd_{chat_id}_{msg_id}_{client_id}
        chat_id, msg_id, client_id = int(data[3]), int(data[4]), int(data[5])
        
        target_client = None
        for client in Altruix.clients:
            if client.me and client.me.id == client_id:
                target_client = client
                break
        
        if not target_client:
            return await cb.answer("❌ Account not connected/found.", show_alert=True)
            
        await cb.answer("📥 Mendownload content...", show_alert=False)
        
        # Download using the specific account that received it
        # Restricted content often requires the specific account to download
        try:
            msg = await target_client.get_messages(chat_id, msg_id)
            if not msg or not msg.media:
                return await cb.answer("❌ Media tidak ditemukan.", show_alert=True)
            
            file_path = await target_client.download_media(msg)
        except Exception as e:
            logger.error(f"PMLU Download failed: {e}")
            return await cb.answer(f"❌ Gagal download: {str(e)[:50]}", show_alert=True)

        if not file_path:
            return await cb.answer("❌ Gagal mendownload content (file_path empty).", show_alert=True)
            
        # Update text to show uploading
        try:
            old_text = cb.message.text.html
            await cb.edit_message_text(f"{old_text}\n\n📤 <b>Uploading bypassed content...</b>", parse_mode=enums.ParseMode.HTML)
        except: pass
        
        # Get topic
        topic_id = await get_or_create_topic(Altruix.bot, Altruix.log_chat, "pm logger", userbot_client=target_client)
        
        # Upload using the userbot to the log group
        await target_client.send_document(
            Altruix.log_chat, 
            file_path, 
            caption=f"✅ <b>Bypassed Restrict Content</b>\nFrom account: {target_client.me.mention}",
            message_thread_id=topic_id
        )
        
        # Cleanup
        if os.path.exists(file_path):
            os.remove(file_path)
            
        await cb.answer("✅ Berhasil mendownload dan mengupload ulang ke group log!", show_alert=True)
    except Exception as e:
        logger.error(f"PMLU Force Forward error: {e}")
        await cb.answer(f"❌ Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlu_others_"))
@log_errors
async def pmlu_others_callback(c: Client, cb: CallbackQuery):
    try:
        from Main.utils.access_control import is_authorized_user
        if not is_authorized_user(cb.from_user.id, Altruix.config.OWNER_ID, Altruix.config.SUDO_USERS):
            msg = Altruix.get_string("access_denied") or "⛔ Akses Ditolak"
            return await cb.answer(msg, show_alert=True)
            
        data = cb.data.split("_")
        chat_id, msg_id, client_id = int(data[2]), int(data[3]), int(data[4])
        
        # Build emoji keyboard (8 per row)
        keyboard = []
        emojis = list(VALID_REACTION_EMOJIS)
        for i in range(0, len(emojis), 8):
            row = [
                InlineKeyboardButton(e, callback_data=f"pmlu_react_{chat_id}_{msg_id}_{client_id}_{e}")
                for e in emojis[i:i+8]
            ]
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=f"pmlu_back_{chat_id}_{msg_id}_{client_id}")])
        
        await cb.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        await cb.answer("Select a reaction emoji")
    except Exception as e:
        await cb.answer(f"❌ Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlu_back_"))
@log_errors
async def pmlu_back_callback(c: Client, cb: CallbackQuery):
    try:
        from Main.utils.access_control import is_authorized_user
        if not is_authorized_user(cb.from_user.id, Altruix.config.OWNER_ID, Altruix.config.SUDO_USERS):
            msg = Altruix.get_string("access_denied") or "⛔ Akses Ditolak"
            return await cb.answer(msg, show_alert=True)
            
        data = cb.data.split("_")
        chat_id, msg_id, client_id = int(data[2]), int(data[3]), int(data[4])
        
        # Re-build original keyboard
        reaction_btns = [
            InlineKeyboardButton(emoji, callback_data=f"pmlu_react_{chat_id}_{msg_id}_{client_id}_{emoji}")
            for emoji in DEFAULT_REACTION_EMOJIS
        ]
        
        keyboard = [
            reaction_btns[:3],
            reaction_btns[3:6],
            [
                InlineKeyboardButton("➕ Others", callback_data=f"pmlu_others_{chat_id}_{msg_id}_{client_id}"),
                InlineKeyboardButton("🗑️ Remove React", callback_data=f"pmlu_unreact_{chat_id}_{msg_id}_{client_id}")
            ],
            [
                InlineKeyboardButton(f"🗨️ {get_permission_label(REPLY_ACCESS_MODE)}", callback_data=f"pmlu_reply_{chat_id}_{msg_id}_{client_id}"),
                InlineKeyboardButton("💾 Save to Log", callback_data=f"pmlu_save_{chat_id}_{msg_id}_{client_id}")
            ],
            [
                InlineKeyboardButton("🗑️ Unsend", callback_data=f"pmlu_unsend_{chat_id}_{msg_id}_{client_id}")
            ],
            [InlineKeyboardButton("🔗 Chat with User", url=f"tg://user?id={chat_id}")] 
        ]

        await cb.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        await cb.answer(f"❌ Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlu_replyall_"))
@log_errors
async def pmlu_replyall_callback(c: Client, cb: CallbackQuery):
    try:
        from Main.utils.access_control import is_authorized_user
        if not is_authorized_user(cb.from_user.id, Altruix.config.OWNER_ID, Altruix.config.SUDO_USERS):
            return await cb.answer("⛔ Akses Ditolak!", show_alert=True)
            
        if not REPLY_FROM_ALL_ACCESSIBLE:
            return await cb.answer("❌ Fitur ini sedang dinonaktifkan.", show_alert=True)

        data = cb.data.split("_")
        chat_id, msg_id, client_id = int(data[2]), int(data[3]), int(data[4])
        msg_key = f"{chat_id}_{msg_id}"
        
        # Get bot ID dynamically
        bot_id = Altruix.bot.me.id if Altruix.bot and Altruix.bot.me else None
        
        # Find first sudo user that is NOT the bot assistant
        # Allow: userbot owner (client_id), PM sender if sudo (chat_id), any other sudo
        user_id = None
        if Altruix.config.SUDO_USERS:
            for sudo_id in Altruix.config.SUDO_USERS:
                if sudo_id != bot_id:  # Only exclude bot assistant
                    user_id = sudo_id
                    break
        
        if not user_id:
            user_id = Altruix.config.OWNER_ID
        today = datetime.now().strftime("%Y%m%d")
        if USER_REPLY_COUNTS[user_id][today] >= USER_REPLY_LIMIT:
             return await cb.answer(f"❌ Limit harian tercapai ({USER_REPLY_LIMIT}x).", show_alert=True)

        # Get thread_id from cache if possible
        cache = PM_LOG_CACHE.get(msg_key, {})
        thread_id = cache.get("thread_id") or getattr(cb.message, "message_thread_id", None)

        waiting_id = f"pmlu_ra_{cb.id}"
        REPLY_AS_MENTIONED_WAITING[waiting_id] = {
            "chat_id": chat_id,
            "message_id": msg_id,
            "client_id": client_id,
            "user_id": user_id,
            "log_msg_id": cb.message.id, # Store original log message ID
            "thread_id": thread_id,
            "instruction_msg_id": None,
            "is_reply_all": True,
            "msg_key": msg_key
        }
        SessionManager.save()
        
        instr = await cb.message.reply(
            "👥 <b>Reply From All (PM)</b>\n\n"
            "Silakan balas pesan ini dengan teks atau media.\n"
            "Pesan akan dikirim dari <b>SEMUA</b> akun Anda ke user ini.",
            parse_mode=enums.ParseMode.HTML,
            reply_parameters=ReplyParameters(message_id=cb.message.id),
            message_thread_id=cb.message.message_thread_id if hasattr(cb.message, "message_thread_id") else None
        )
        REPLY_AS_MENTIONED_WAITING[waiting_id]["instruction_msg_id"] = instr.id
        await cb.answer("Silakan kirim balasan Anda.")
        
        # Debug log
        logger.info(f"PMLU: Waiting for reply on msg {instr.id} for waiting_id {waiting_id}")
    except Exception as e:
        await cb.answer(f"❌ Error: {e}", show_alert=True)


# pmlu_reply_callback removed as it is now handled by pmlu_direct_reply_callback

@Altruix.bot.on_callback_query(filters.regex(r"^pmlu_unsend_"))
@log_errors
async def pmlu_unsend_callback(c: Client, cb: CallbackQuery):
    try:
        from Main.utils.access_control import is_authorized_user
        if not is_authorized_user(cb.from_user.id, Altruix.config.OWNER_ID, Altruix.config.SUDO_USERS):
            return await cb.answer("⛔ Akses Ditolak!", show_alert=True)

        data = cb.data.split("_")
        chat_id, msg_id, client_id = int(data[2]), int(data[3]), int(data[4])
        msg_key = f"{chat_id}_{msg_id}"
        
        cache = PM_LOG_CACHE.get(msg_key, {})
        last_replies = cache.get("last_replies", []) # List of (client_id, msg_id)
        
        if not last_replies:
            return await cb.answer("❌ Tidak ada balasan yang terekam untuk di-unsend.", show_alert=True)
            
        unsend_count = 0
        for cid, mid in last_replies:
            target_client = None
            for client in Altruix.clients:
                if client.me and client.me.id == cid:
                    target_client = client
                    break
            if target_client:
                try:
                    await target_client.delete_messages(chat_id, mid)
                    unsend_count += 1
                except:
                    pass
        
        # Clear replies from cache
        PM_LOG_CACHE[msg_key]["last_replies"] = []
        
        await cb.answer(f"✅ Berhasil unsend {unsend_count} pesan.", show_alert=True)
    except Exception as e:
        await cb.answer(f"❌ Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlu_toggle_(full|compact)_"))
@log_errors
async def pmlu_toggle_callback(c: Client, cb: CallbackQuery):
    try:
        from Main.utils.access_control import is_authorized_user
        if not is_authorized_user(cb.from_user.id, Altruix.config.OWNER_ID, Altruix.config.SUDO_USERS):
            msg = Altruix.get_string("access_denied") or "⛔ Akses Ditolak"
            return await cb.answer(msg, show_alert=True)
            
        data = cb.data.split("_")
        mode, chat_id, msg_id, client_id = data[2], int(data[3]), int(data[4]), int(data[5])
        
        if mode == "full":
            reaction_btns = [
                InlineKeyboardButton(emoji, callback_data=f"pmlu_react_{chat_id}_{msg_id}_{client_id}_{emoji}")
                for emoji in DEFAULT_REACTION_EMOJIS
            ]
            keyboard = [
                reaction_btns[:3],
                reaction_btns[3:6],
                [
                    InlineKeyboardButton("➕ Others", callback_data=f"pmlu_others_{chat_id}_{msg_id}_{client_id}"),
                    InlineKeyboardButton("🗑️ Remove React", callback_data=f"pmlu_unreact_{chat_id}_{msg_id}_{client_id}")
                ],
                [
                    InlineKeyboardButton(f"🗨️ {get_permission_label('sudo')}", callback_data=f"pmlu_reply_{chat_id}_{msg_id}_{client_id}"),
                    InlineKeyboardButton("💾 Save", callback_data=f"pmlu_save_{chat_id}_{msg_id}_{client_id}")
                ],
                [
                    InlineKeyboardButton("🚫 Block", callback_data=f"pmlu_block_{chat_id}_{client_id}"),
                    InlineKeyboardButton("✅ Unblock", callback_data=f"pmlu_unblock_{chat_id}_{client_id}")
                ],
                [
                    InlineKeyboardButton("🗑️ Unsend", callback_data=f"pmlu_unsend_{chat_id}_{msg_id}_{client_id}")
                ],
                [
                    InlineKeyboardButton("⚙️ Hide Settings Menu", callback_data=f"pmlu_toggle_compact_{chat_id}_{msg_id}_{client_id}"),
                    InlineKeyboardButton("🔗 Chat", url=f"tg://user?id={chat_id}")
                ]
            ]
            if not REPLY_FROM_ALL_ACCESSIBLE:
                keyboard = [r for r in keyboard if not any(b.text == "👥 Reply All" for b in r)]
        else:
            keyboard = [[
                InlineKeyboardButton("⚙️ Show Settings Menu", callback_data=f"pmlu_toggle_full_{chat_id}_{msg_id}_{client_id}"),
                InlineKeyboardButton("🔗 Chat with User", url=f"tg://user?id={chat_id}")
            ]]
            
        await cb.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        await cb.answer()
    except Exception as e:
        await cb.answer(f"❌ Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlu_(block|unblock)_"))
@log_errors
async def pmlu_block_unblock_callback(c: Client, cb: CallbackQuery):
    try:
        from Main.utils.access_control import is_authorized_user
        if not is_authorized_user(cb.from_user.id, Altruix.config.OWNER_ID, Altruix.config.SUDO_USERS):
            return await cb.answer("⛔ Akses Ditolak!", show_alert=True)

        data = cb.data.split("_")
        action, chat_id, client_id = data[1], int(data[2]), int(data[3])
        
        target_client = None
        for client in Altruix.clients:
            if client.me and client.me.id == client_id:
                target_client = client
                break
        
        if not target_client:
            return await cb.answer("❌ Client session not found.", show_alert=True)
            
        if action == "block":
            await target_client.block_user(chat_id)
            await cb.answer("🚫 User blocked successfully.", show_alert=True)
        else:
            await target_client.unblock_user(chat_id)
            await cb.answer("✅ User unblocked successfully.", show_alert=True)
    except Exception as e:
        await cb.answer(f"❌ Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlu_reply_(-?\d+)_(\d+)_(\d+)"))
@log_errors
async def pmlu_direct_reply_callback(c: Client, cb: CallbackQuery):
    """Langsung memulai proses reply ke user tertentu."""
    try:
        from Main.utils.access_control import check_reply_access
        has_access, reason = check_reply_access(
            cb.from_user, get_shared_reply_mode(), Altruix.config.OWNER_ID, Altruix.config.SUDO_USERS
        )
        if not has_access:
            return await cb.answer(reason, show_alert=True)
            
        data = cb.data.split("_")
        chat_id, msg_id, client_id = int(data[2]), int(data[3]), int(data[4])
        msg_key = f"{chat_id}_{msg_id}"
        
        # DEBUG: Check OWNER_ID and SUDO_USERS
        logger.info(f"DEBUG OWNER_ID: {Altruix.config.OWNER_ID}, SUDO count: {len(Altruix.config.SUDO_USERS) if Altruix.config.SUDO_USERS else 0}")
        
        # FIXED: Allow ANY sudo user to reply
        # Only exclude: actual bot (5240721396), PM sender (chat_id), userbot accounts (client_id)
        # Get bot ID dynamically
        bot_id = Altruix.bot.me.id if Altruix.bot and Altruix.bot.me else None
        
        # Find first sudo user that is NOT the bot assistant
        # Allow: userbot owner (client_id), PM sender if sudo (chat_id), any other sudo
        admin_user_id = None
        if Altruix.config.SUDO_USERS:
            for sudo_id in Altruix.config.SUDO_USERS:
                if sudo_id != bot_id:  # Only exclude bot assistant
                    admin_user_id = sudo_id
                    logger.info(f"Using SUDO user as admin: {admin_user_id}")
                    break
        
        if not admin_user_id:
            admin_user_id = Altruix.config.OWNER_ID
            logger.info(f"No valid SUDO found, using OWNER_ID: {admin_user_id}")
        logger.info(
            f"PMLU Reply Callback Debug:\n"
            f"  - Callback from user: {cb.from_user.id} ({cb.from_user.first_name})\n"
            f"  - Callback data: {cb.data}\n"
            f"  - Parsed: chat_id={chat_id}, msg_id={msg_id}, client_id={client_id}\n"
            f"  - msg_key={msg_key}"
        )
        
        # Get extra info from cache if available
        cache = PM_LOG_CACHE.get(msg_key, {})
        log_msg_id = cache.get("log_msg_id") or cb.message.id
        fwd_msg_id = cache.get("fwd_msg_id")
        # Try to get thread_id from cache, then from the current callback message
        current_msg_thread = getattr(cb.message, "message_thread_id", None)
        thread_id = cache.get("thread_id") or current_msg_thread
        
        logger.info(f"PMLU Reply: msg_key={msg_key}, log_msg_id={log_msg_id}, thread_id={thread_id}, admin={admin_user_id}")
        
        waiting_id = f"pmlu_r_{cb.id}"
        
        # Find current client name
        client_name = "Unknown"
        for client in Altruix.clients:
            if client.me and client.me.id == client_id:
                client_name = client.me.first_name
                break
        
        waiting_data = {
            "chat_id": chat_id,
            "message_id": msg_id,
            "client_id": client_id,
            "user_id": admin_user_id,  # Use the explicitly captured admin ID
            "log_msg_id": log_msg_id,
            "fwd_msg_id": fwd_msg_id,
            "thread_id": thread_id,
            "is_reply_all": False,
            "msg_key": msg_key
        }
        logger.info(f"DirectReply: Created session {waiting_id} with user_id={waiting_data['user_id']} (admin: {admin_user_id})")
        REPLY_AS_MENTIONED_WAITING[waiting_id] = waiting_data
        SessionManager.save()

        instr = await Altruix.bot.send_message(
            Altruix.log_chat,
            f"✉️ <b>Input Balasan</b> (via {client_name})\n\n"
            f"⚠️ <b>PENTING</b>: Balas pesan INI, bukan judul topik!\n"
            f"Pesan akan dikirim ke User ID <code>{chat_id}</code>.\n\n"
            f"💡 Tip: Klik 'Reply' pada pesan ini untuk memastikan balasan terdeteksi.",
            parse_mode=enums.ParseMode.HTML,
            reply_parameters=ReplyParameters(message_id=cb.message.id),
            message_thread_id=cb.message.message_thread_id if hasattr(cb.message, "message_thread_id") else None
        )
        REPLY_AS_MENTIONED_WAITING[waiting_id]["instruction_msg_id"] = instr.id
        SessionManager.save()
        logger.info(f"DirectReply: Session {waiting_id} updated with instruction_msg_id={instr.id}")
        await cb.answer("Silakan kirim balasan Anda.")
    except Exception as e:
        logger.error(f"Direct reply error: {e}")
        await cb.answer(f"❌ Error: {e}", show_alert=True)



# Cleanup task for cache
async def cleanup_pmlu_cache():
    while True:
        if len(PM_LOG_CACHE) > 1000:
            # Simple cleanup: remove oldest 200
            keys = list(PM_LOG_CACHE.keys())[:200]
            for k in keys:
                PM_LOG_CACHE.pop(k, None)
        await asyncio.sleep(3600)

asyncio.create_task(cleanup_pmlu_cache())

# ==================== RESOURCE MONITOR ====================
async def resource_monitor():
    """Monitor system resources and alert if usage exceeds 90%."""
    alert_triggered = False
    while True:
        try:
            cpu_usage = psutil.cpu_percent(interval=1)
            ram_usage = psutil.virtual_memory().percent
            
            if (cpu_usage > 90 or ram_usage > 90) and not alert_triggered:
                log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))
                alert_text = (
                    "🚨 <b>SYSTEM OVERLOAD ALERT</b> 🚨\n\n"
                    f"⚠️ <b>CPU Usage:</b> <code>{cpu_usage}%</code>\n"
                    f"⚠️ <b>RAM Usage:</b> <code>{ram_usage}%</code>\n\n"
                    "Please check your server immediately to prevent crashes."
                )
                try:
                    await Altruix.bot.send_message(log_chat_id, alert_text)
                    alert_triggered = True
                except: pass
            elif cpu_usage < 80 and ram_usage < 80:
                alert_triggered = False
                
        except Exception as e:
            logger.error(f"Resource monitor error: {e}")
            
        await asyncio.sleep(60)

asyncio.create_task(resource_monitor())

# ==================== LOG SUKSES LOADING ====================
# try:
#     Altruix.log(f"[DEBUG] Loaded → {__plugin_name__} {PLUGIN_VERSION}", level=20)
# except Exception as e:
#     logger.info(f"[DEBUG] Loaded → {__plugin_name__} {PLUGIN_VERSION}")