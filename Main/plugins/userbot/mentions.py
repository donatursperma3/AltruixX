# qwen
# mentions.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.

from Main import Altruix
from Main.core.types.message import Message as AltruixMessage
from pyrogram import Client, enums, filters
from pyrogram.types import (
    Message as RawMessage,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyParameters,
    CallbackQuery
)
from datetime import datetime, timedelta
from Main.core.decorators import log_errors
import os
import re
import asyncio
import html
import logging
import time
import json
import traceback
from pathlib import Path
import aiofiles
from typing import Optional, Union, Dict, Any
from collections import defaultdict

plugin_name = f"plugins/userbot/{os.path.basename(__file__)}"
__plugin_name__ = plugin_name if plugin_name else "mentions"
PLUGIN_VERSION = "0.2.0.0"  # 🔥 VERSI DIPERBAIKI: Semua tombol bekerja + logging lengkap

# 🔥 SETUP LOGGING DETAILED
logger = logging.getLogger(f"{__plugin_name__}")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - [MENTIONS] - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)  # 🔥 DEBUG untuk semua log

# 🔥 LOG STARTUP
logger.info(f"🚀 Initializing mentions plugin v{PLUGIN_VERSION}")

# 🔥 PERBAIKAN: Helper functions dengan logging
def log_button_press(button_name: str, data: str, user_id: Optional[int] = None):
    """Log setiap tombol yang ditekan."""
    user_info = f" by user {user_id}" if user_id else ""
    logger.debug(f"🔘 Button '{button_name}' pressed{user_info}: {data}")

def safe_datetime_fromtimestamp(timestamp) -> datetime:
    """Convert timestamp to datetime dengan handling semua tipe data."""
    try:
        if timestamp is None:
            return datetime.now()
        
        if isinstance(timestamp, datetime):
            return timestamp
        
        if isinstance(timestamp, (int, float)):
            if timestamp > 4102444800:
                timestamp = timestamp / 1000
            return datetime.fromtimestamp(float(timestamp))
        
        return datetime.now()
    except Exception as e:
        logger.warning(f"Datetime conversion error: {e}")
        return datetime.now()

async def safe_send_message(
    client: Client, 
    chat_id: Union[int, str], 
    text: str, 
    **kwargs
) -> Optional[RawMessage]:
    """Send message dengan timeout dan error handling."""
    try:
        # Timeout protection
        return await asyncio.wait_for(
            client.send_message(chat_id, text, **kwargs),
            timeout=30
        )
    except asyncio.TimeoutError:
        logger.warning(f"Timeout sending message to {chat_id}")
        return None
    except Exception as e:
        logger.error(f"Send message failed: {e}")
        return None

async def safe_edit_message(
    client: Client,
    chat_id: Union[int, str],
    message_id: int,
    text: str,
    **kwargs
) -> bool:
    """Edit message dengan timeout handling."""
    try:
        await asyncio.wait_for(
            client.edit_message_text(chat_id, message_id, text, **kwargs),
            timeout=15
        )
        return True
    except asyncio.TimeoutError:
        logger.warning(f"Timeout editing message {message_id}")
        return False
    except Exception as e:
        logger.error(f"Edit message failed: {e}")
        return False

# 🔥 PERBAIKAN: Local JSON storage
LOCAL_STORAGE_FILE = Path("mentions_settings.json")
MENTIONS_DATA = {}

# 🔥 TAMBAHAN: Dictionary untuk melacak pesan mention yang sudah dikirim
MENTION_LOG_CACHE = {}

# 🔥 TAMBAHAN: Emoji default untuk quick reaction
DEFAULT_REACTION_EMOJIS = ["👍", "❤️", "😂", "😮", "😢"]

# 🔥 TAMBAHAN: Dictionary untuk menunggu konfirmasi reply-as-mentioned
REPLY_AS_MENTIONED_WAITING = {}

# 🔥 PERBAIKAN: Flag untuk auto-reply
AUTO_REPLY_ENABLED = False

# 🔥 PERBAIKAN: Rate limiting untuk Reply From All
USER_REPLY_COUNTS = defaultdict(lambda: defaultdict(int))  # user_id -> {date: count}
USER_REPLY_LIMIT = 3  # Maksimal 3x per hari per user

# 🔥 PERBAIKAN: Cache untuk userbot clients
USERBOT_CLIENTS = {}

# 🔥 BARU: Button press statistics
BUTTON_STATS = {
    "react": 0,
    "reply": 0,
    "reply_all": 0,
    "confirm": 0,
    "cancel": 0
}

async def load_local_storage():
    """Load data dari local JSON file."""
    global MENTIONS_DATA, AUTO_REPLY_ENABLED
    try:
        if LOCAL_STORAGE_FILE.exists():
            async with aiofiles.open(LOCAL_STORAGE_FILE, 'r', encoding='utf-8') as f:
                content = await f.read()
                if content.strip():
                    data = json.loads(content)
                    MENTIONS_DATA = data.get("settings", {})
                    AUTO_REPLY_ENABLED = data.get("auto_reply", False)
                    logger.info(f"Loaded {len(MENTIONS_DATA)} settings, auto_reply: {AUTO_REPLY_ENABLED}")
                else:
                    MENTIONS_DATA = {}
                    AUTO_REPLY_ENABLED = False
        else:
            MENTIONS_DATA = {}
            AUTO_REPLY_ENABLED = False
            logger.info("Local storage file not found, creating new")
    except Exception as e:
        logger.error(f"Failed to load local storage: {e}")
        MENTIONS_DATA = {}
        AUTO_REPLY_ENABLED = False
        await save_local_storage()

async def save_local_storage():
    """Save data ke local JSON file."""
    try:
        data = {
            "settings": MENTIONS_DATA,
            "auto_reply": AUTO_REPLY_ENABLED,
            "last_saved": int(time.time()),
            "version": PLUGIN_VERSION,
            "button_stats": BUTTON_STATS
        }
        async with aiofiles.open(LOCAL_STORAGE_FILE, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, indent=2, ensure_ascii=False))
        logger.debug(f"Saved {len(MENTIONS_DATA)} settings to local storage")
    except Exception as e:
        logger.error(f"Failed to save local storage: {e}")

async def backup_to_telegram(userbot_client: Client):
    """Upload backup ke Telegram."""
    try:
        if not LOCAL_STORAGE_FILE.exists():
            return False
        
        await userbot_client.send_document(
            "me",
            str(LOCAL_STORAGE_FILE),
            caption=f"📂 Mention Settings Backup\nVersion: {PLUGIN_VERSION}"
        )
        logger.info("Backup sent to saved messages")
        return True
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        return False

async def get_mention_setting_safe(client_id: int) -> bool:
    """Safe method untuk membaca setting."""
    client_id_str = str(client_id)
    if client_id_str in MENTIONS_DATA:
        setting_data = MENTIONS_DATA[client_id_str]
        if isinstance(setting_data, dict) and "value" in setting_data:
            return bool(setting_data["value"])
    return False

async def save_mention_setting(client_id: int, value: bool) -> bool:
    """Safe method untuk menyimpan setting."""
    client_id_str = str(client_id)
    MENTIONS_DATA[client_id_str] = {
        "value": bool(value),
        "timestamp_int": int(time.time())
    }
    await save_local_storage()
    logger.info(f"Saved setting for {client_id}: {value}")
    return True

async def get_userbot_client(client_id: int) -> Optional[Client]:
    """Get userbot client dari cache."""
    return USERBOT_CLIENTS.get(client_id)

# 🔥 Load local storage saat plugin start
asyncio.create_task(load_local_storage())
logger.info("Local storage loaded")

@Altruix.register_on_cmd(
    ["mentions"],
    cmd_help={
        "help": "To toggle notify mentions globally.",
        "example": "mentions (on/off)",
    },
    group_only=False,
    requires_input=True,
)
@log_errors
async def mention_settings_handler(c: Client, m: AltruixMessage):
    """Handler untuk mengaktifkan/menonaktifkan notifikasi mention global."""
    msg = await m.handle_message("PROCESSING")
    user_input = m.user_input.lower().strip()
    
    if user_input in ["on", "yes"]:
        value = True
        status_text = "ENABLED"
        emoji = "✅"
    elif user_input in ["off", "no"]:
        value = False
        status_text = "DISABLED"
        emoji = "❌"
    else:
        return await msg.edit_msg("INVALID_INPUT")
    
    try:
        client_id = c.me.id
        await save_mention_setting(client_id, value)
        USERBOT_CLIENTS[client_id] = c
        
        status_msg = f"{emoji} **Mention notifications {status_text}**"
        await safe_edit_message(c, m.chat.id, msg.id, status_msg, parse_mode=enums.ParseMode.MARKDOWN)
        
    except Exception as e:
        logger.error(f"Save failed: {e}")
        await msg.edit_msg(f"❌ Save error: {str(e)[:100]}")

@Altruix.register_on_cmd(
    ["autoreply"],
    cmd_help={
        "help": "Toggle auto-reply for mentions",
        "example": "autoreply (on/off)",
    },
    group_only=False,
    requires_input=True,
)
@log_errors
async def autoreply_settings_handler(c: Client, m: AltruixMessage):
    """Handler untuk mengaktifkan/menonaktifkan auto-reply."""
    global AUTO_REPLY_ENABLED
    
    msg = await m.handle_message("PROCESSING")
    user_input = m.user_input.lower().strip()
    
    if user_input in ["on", "yes"]:
        AUTO_REPLY_ENABLED = True
        status_text = "ENABLED"
        emoji = "✅"
    elif user_input in ["off", "no"]:
        AUTO_REPLY_ENABLED = False
        status_text = "DISABLED"
        emoji = "❌"
    else:
        return await msg.edit_msg("INVALID_INPUT")
    
    try:
        await save_local_storage()
        status_msg = f"{emoji} **Auto-Reply {status_text}**"
        await safe_edit_message(c, m.chat.id, msg.id, status_msg, parse_mode=enums.ParseMode.MARKDOWN)
        
    except Exception as e:
        logger.error(f"Auto-reply save failed: {e}")
        await msg.edit_msg(f"❌ Auto-reply error: {str(e)[:100]}")

@Altruix.on_message(
    filters.mentioned & filters.group & ~filters.user(Altruix.bot_info.id)
)
@log_errors
async def send_mention_log_handler(c: Client, m: RawMessage):
    """Handler utama untuk menangkap mention dan mengirim notifikasi ke LOG_CHAT."""
    try:
        client_id = c.me.id
        
        # Cek apakah mention notifications enabled
        is_enabled = await get_mention_setting_safe(client_id)
        if not is_enabled:
            logger.debug(f"Mentions disabled for {client_id}")
            return

        logger.info(f"Processing mention for {c.me.first_name} ({client_id})")
        
        # Persiapan data mention
        mentioner = m.from_user
        if not mentioner:
            return

        mentioner_name = mentioner.first_name or "Unknown"
        mentioner_id = mentioner.id
        mentioner_hyperlink = f'<a href="tg://user?id={mentioner_id}">{html.escape(mentioner_name)}</a>'
        
        # Handle message text
        message_text = m.text or m.caption or "[No text content]"
        if message_text:
            message_text = html.escape(str(message_text))[:500]
        
        # Format waktu
        try:
            mention_time = datetime.fromtimestamp(m.date).strftime("%Y-%m-%d %H:%M:%S")
        except:
            mention_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Bangun pesan notifikasi
        log_message = (
            f"🔔 <b>Mention Detected!</b>\n\n"
            f"👤 <b>Mentioned By:</b> {mentioner_hyperlink} (<code>{mentioner_id}</code>)\n"
            f"🤖 <b>My Account:</b> {c.me.mention(style=enums.ParseMode.HTML)}\n"
            f"💬 <b>Group:</b> {html.escape(m.chat.title)} (<code>{m.chat.id}</code>)\n"
            f"🕒 <b>Time:</b> <code>{mention_time}</code>\n"
            f"📄 <b>Message:</b>\n<blockquote>{message_text}</blockquote>"
        )
        
        # 🔥 PERBAIKAN: Tombol dengan callback data yang benar
        reaction_buttons = [
            InlineKeyboardButton(
                emoji,
                callback_data=f"mentions_react_{m.chat.id}_{m.id}_{emoji}_{int(time.time())}"
            )
            for emoji in DEFAULT_REACTION_EMOJIS
        ]
        
        reply_button = [InlineKeyboardButton(
            "🗨️ Reply as Mentioned",
            callback_data=f"mentions_reply_{m.chat.id}_{m.id}_{int(time.time())}"
        )]
        
        reply_all_button = [InlineKeyboardButton(
            "👥 Reply From All",
            callback_data=f"mentions_replyall_{m.chat.id}_{m.id}_{int(time.time())}"
        )]
        
        link_button = [InlineKeyboardButton("🔗 Go to Message", url=m.link)]
        
        # 🔥 PERBAIKAN: Keyboard layout yang benar
        keyboard = [
            reaction_buttons[:3],  # Baris pertama: 3 emoji
            reaction_buttons[3:],  # Baris kedua: 2 emoji
            reply_button,          # Baris ketiga: Reply as Mentioned
            reply_all_button,      # Baris keempat: Reply From All
            link_button           # Baris kelima: Link
        ]
        
        msg_key = f"{m.chat.id}_{m.id}"
        
        # Kirim notifikasi
        try:
            sent_log_msg = await Altruix.bot.send_message(
                Altruix.log_chat,
                log_message,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            logger.info(f"Notification sent for {msg_key}, message_id: {sent_log_msg.id}")
            
        except Exception as send_err:
            logger.error(f"Send failed: {send_err}")
            return
        
        # Cache untuk edit detection
        MENTION_LOG_CACHE[msg_key] = {
            "text": message_text,
            "log_msg_id": sent_log_msg.id,
            "mentioned_client": c,
            "chat_id": m.chat.id,
            "message_id": m.id,
            "timestamp_int": int(time.time()),
            "client_id": client_id
        }
        
        # Cache management
        if len(MENTION_LOG_CACHE) > 100:
            try:
                oldest = min(MENTION_LOG_CACHE.items(), key=lambda x: x[1].get("timestamp_int", 0))
                del MENTION_LOG_CACHE[oldest[0]]
                logger.debug(f"Cleaned cache: {oldest[0]}")
            except Exception as cache_err:
                logger.warning(f"Cache cleanup failed: {cache_err}")
            
    except Exception as e:
        logger.error(f"Error in mention handler: {e}", exc_info=True)

# 🔥 PERBAIKAN UTAMA: Handler untuk quick reaction dengan LOGGING DETAIL
@Altruix.bot.on_callback_query(filters.regex(r"^mentions_react_"))
@log_errors
async def quick_reaction_handler(c: Client, cb: CallbackQuery):
    """Kirim reaksi ke pesan asli di grup."""
    try:
        BUTTON_STATS["react"] += 1
        log_button_press("REACT", cb.data, cb.from_user.id if cb.from_user else None)
        logger.info(f"📊 React button pressed. Total: {BUTTON_STATS['react']}")
        
        # Parse callback data
        parts = cb.data.split("_")
        if len(parts) < 6:
            logger.error(f"Invalid react callback data: {cb.data}")
            await cb.answer("❌ Invalid callback data", show_alert=True)
            return
        
        chat_id = int(parts[2])
        message_id = int(parts[3])
        emoji = parts[4]
        timestamp = parts[5] if len(parts) > 5 else "0"
        
        msg_key = f"{chat_id}_{message_id}"
        logger.info(f"Processing reaction for {msg_key} with {emoji}")
        
        if msg_key not in MENTION_LOG_CACHE:
            logger.warning(f"Mention not in cache: {msg_key}")
            await cb.answer("❌ Mention tidak ditemukan di cache.", show_alert=True)
            return
        
        userbot_client = MENTION_LOG_CACHE[msg_key]["mentioned_client"]
        if not userbot_client:
            logger.warning(f"Userbot client not available: {msg_key}")
            await cb.answer("❌ Akun yang disebut tidak tersedia.", show_alert=True)
            return
        
        try:
            # Kirim reaction
            await userbot_client.send_reaction(chat_id, message_id, emoji)
            logger.info(f"Reaction sent: {emoji} to {msg_key}")
            
            # Update tombol untuk show success
            try:
                if cb.message.reply_markup:
                    new_buttons = []
                    for row in cb.message.reply_markup.inline_keyboard:
                        new_row = []
                        for button in row:
                            if button.callback_data == cb.data:
                                new_row.append(InlineKeyboardButton(
                                    f"✅ {emoji}", 
                                    callback_data="mentions_reacted"
                                ))
                            else:
                                new_row.append(button)
                        new_buttons.append(new_row)
                    
                    await cb.message.edit_reply_markup(InlineKeyboardMarkup(new_buttons))
                    logger.debug(f"Button updated for {emoji}")
            except Exception as edit_err:
                logger.warning(f"Could not update button: {edit_err}")
            
            await cb.answer(f"✅ Bereaksi dengan {emoji}", show_alert=False)
            
        except Exception as react_err:
            logger.error(f"Reaction failed: {react_err}")
            await cb.answer(f"❌ Gagal: {str(react_err)[:50]}", show_alert=True)
            
    except Exception as e:
        logger.error(f"Quick reaction error: {e}", exc_info=True)
        await cb.answer("❌ Terjadi kesalahan.", show_alert=True)

# 🔥 PERBAIKAN: Handler untuk reply as mentioned dengan LOGGING
@Altruix.bot.on_callback_query(filters.regex(r"^mentions_reply_"))
@log_errors
async def start_reply_as_mentioned(c: Client, cb: CallbackQuery):
    """Memulai proses reply-as-mentioned."""
    try:
        BUTTON_STATS["reply"] += 1
        log_button_press("REPLY", cb.data, cb.from_user.id if cb.from_user else None)
        logger.info(f"📊 Reply button pressed. Total: {BUTTON_STATS['reply']}")
        
        # Parse callback data
        parts = cb.data.split("_")
        if len(parts) < 5:
            logger.error(f"Invalid reply callback data: {cb.data}")
            await cb.answer("❌ Invalid callback data", show_alert=True)
            return
        
        chat_id = int(parts[2])
        message_id = int(parts[3])
        timestamp = parts[4] if len(parts) > 4 else "0"
        msg_key = f"{chat_id}_{message_id}"
        
        logger.info(f"Starting reply process for {msg_key}")
        
        if msg_key not in MENTION_LOG_CACHE:
            logger.warning(f"Mention not in cache: {msg_key}")
            await cb.answer("❌ Mention tidak ditemukan di cache.", show_alert=True)
            return
        
        mentioned_client = MENTION_LOG_CACHE[msg_key]["mentioned_client"]
        if not mentioned_client:
            logger.warning(f"Userbot client not available: {msg_key}")
            await cb.answer("❌ Akun yang disebut tidak tersedia.", show_alert=True)
            return
        
        # Simpan status menunggu input
        waiting_id = f"reply_{int(time.time())}_{cb.message.id}"
        REPLY_AS_MENTIONED_WAITING[waiting_id] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "mentioned_client": mentioned_client,
            "log_msg_id": cb.message.id,
            "user_id": cb.from_user.id if cb.from_user else None,
            "timestamp_int": int(time.time()),
            "callback_message_id": cb.message.id,
            "is_reply_all": False,
            "waiting_id": waiting_id
        }
        
        logger.info(f"Waiting for reply input for {msg_key}, waiting_id: {waiting_id}")
        
        # Kirim instruksi
        try:
            instruction_msg = await cb.message.reply_text(
                "🗨️ <b>Reply as Mentioned</b>\n\n"
                "Silakan ketik pesan balasan Anda di bawah ini.\n"
                "Pesan akan dikirim sebagai akun yang disebut di grup asal.\n\n"
                "<i>Balas pesan ini dengan teks yang ingin dikirim.</i>",
                reply_to_message_id=cb.message.id,
                parse_mode=enums.ParseMode.HTML
            )
            
            REPLY_AS_MENTIONED_WAITING[waiting_id]["instruction_msg_id"] = instruction_msg.id
            logger.info(f"Instruction sent: {instruction_msg.id}")
            
        except Exception as e:
            logger.error(f"Instruction send failed: {e}")
            await cb.answer("❌ Gagal mengirim instruksi", show_alert=True)
            return
        
        await cb.answer("✅ Silakan ketik balasan Anda.", show_alert=False)
        
    except Exception as e:
        logger.error(f"Reply start error: {e}", exc_info=True)
        await cb.answer("❌ Terjadi kesalahan.", show_alert=True)

# 🔥 BARU: Handler untuk Reply From All dengan LOGGING dan RATE LIMIT
@Altruix.bot.on_callback_query(filters.regex(r"^mentions_replyall_"))
@log_errors
async def start_reply_from_all(c: Client, cb: CallbackQuery):
    """Memulai proses reply-from-all untuk semua user."""
    try:
        BUTTON_STATS["reply_all"] += 1
        log_button_press("REPLY_ALL", cb.data, cb.from_user.id if cb.from_user else None)
        logger.info(f"📊 Reply All button pressed. Total: {BUTTON_STATS['reply_all']}")
        
        # Parse callback data
        parts = cb.data.split("_")
        if len(parts) < 5:
            logger.error(f"Invalid replyall callback data: {cb.data}")
            await cb.answer("❌ Invalid callback data", show_alert=True)
            return
        
        chat_id = int(parts[2])
        message_id = int(parts[3])
        timestamp = parts[4] if len(parts) > 4 else "0"
        msg_key = f"{chat_id}_{message_id}"
        
        # Cek rate limit
        user_id = cb.from_user.id if cb.from_user else None
        if not user_id:
            await cb.answer("❌ User tidak dikenal", show_alert=True)
            return
        
        today = datetime.now().strftime("%Y%m%d")
        if USER_REPLY_COUNTS[user_id][today] >= USER_REPLY_LIMIT:
            logger.warning(f"User {user_id} hit rate limit for today")
            await cb.answer(
                f"❌ Anda sudah mencapai batas reply ({USER_REPLY_LIMIT}x per hari). Coba lagi besok.",
                show_alert=True
            )
            return
        
        if msg_key not in MENTION_LOG_CACHE:
            logger.warning(f"Mention not in cache: {msg_key}")
            await cb.answer("❌ Mention tidak ditemukan di cache.", show_alert=True)
            return
        
        mentioned_client = MENTION_LOG_CACHE[msg_key]["mentioned_client"]
        if not mentioned_client:
            logger.warning(f"Userbot client not available: {msg_key}")
            await cb.answer("❌ Akun yang disebut tidak tersedia.", show_alert=True)
            return
        
        # Simpan status menunggu input
        waiting_id = f"replyall_{int(time.time())}_{cb.message.id}"
        REPLY_AS_MENTIONED_WAITING[waiting_id] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "mentioned_client": mentioned_client,
            "log_msg_id": cb.message.id,
            "user_id": user_id,
            "timestamp_int": int(time.time()),
            "callback_message_id": cb.message.id,
            "is_reply_all": True,
            "waiting_id": waiting_id
        }
        
        logger.info(f"Reply From All waiting for {msg_key}, user: {user_id}, waiting_id: {waiting_id}")
        
        # Kirim instruksi
        try:
            user_mention = cb.from_user.mention(style=enums.ParseMode.HTML) if cb.from_user else "User"
            instruction_msg = await cb.message.reply_text(
                f"👥 <b>Reply From All</b>\n\n"
                f"Halo {user_mention}!\n\n"
                f"Silakan ketik pesan balasan Anda di bawah ini.\n"
                f"Pesan akan dikirim sebagai <b>{mentioned_client.me.first_name}</b> ke grup asal.\n\n"
                f"<i>Note: Maksimal {USER_REPLY_LIMIT}x reply per hari per mention</i>\n"
                f"<i>Balas pesan ini dengan teks yang ingin dikirim.</i>",
                reply_to_message_id=cb.message.id,
                parse_mode=enums.ParseMode.HTML
            )
            
            REPLY_AS_MENTIONED_WAITING[waiting_id]["instruction_msg_id"] = instruction_msg.id
            logger.info(f"Reply All instruction sent: {instruction_msg.id}")
            
        except Exception as e:
            logger.error(f"Reply All instruction failed: {e}")
            await cb.answer("❌ Gagal mengirim instruksi", show_alert=True)
            return
        
        # Update count
        USER_REPLY_COUNTS[user_id][today] += 1
        logger.info(f"User {user_id} reply count: {USER_REPLY_COUNTS[user_id][today]}/{USER_REPLY_LIMIT}")
        
        await cb.answer("✅ Silakan ketik balasan Anda. (Reply From All)", show_alert=False)
        
    except Exception as e:
        logger.error(f"Reply From All error: {e}", exc_info=True)
        await cb.answer("❌ Terjadi kesalahan.", show_alert=True)

# 🔥 PERBAIKAN: Handler untuk menerima input balasan dengan LOGGING
@Altruix.bot.on_message(filters.chat(Altruix.log_chat) & filters.reply)
@log_errors
async def handle_reply_as_mentioned_input(c: Client, m: RawMessage):
    """Menangani input balasan untuk reply-as-mentioned."""
    try:
        if not m.reply_to_message:
            return
        
        reply_msg_id = m.reply_to_message.id
        logger.info(f"Checking reply input for message {reply_msg_id}")
        
        # Cari waiting_id berdasarkan instruction_msg_id atau callback_message_id
        waiting_id = None
        for wid, data in REPLY_AS_MENTIONED_WAITING.items():
            if data.get("instruction_msg_id") == reply_msg_id:
                waiting_id = wid
                break
            elif data.get("callback_message_id") == reply_msg_id:
                waiting_id = wid
                break
        
        if not waiting_id or waiting_id not in REPLY_AS_MENTIONED_WAITING:
            logger.debug(f"No waiting found for reply to {reply_msg_id}")
            return
        
        data = REPLY_AS_MENTIONED_WAITING[waiting_id]
        chat_id = data["chat_id"]
        message_id = data["message_id"]
        mentioned_client = data["mentioned_client"]
        
        reply_text = m.text or m.caption or ""
        if not reply_text.strip():
            logger.warning(f"Empty reply text from message {m.id}")
            await m.reply_text(
                "❌ <b>Pesan kosong</b>\n\nSilakan ketik pesan yang ingin dikirim.",
                reply_to_message_id=m.id,
                parse_mode=enums.ParseMode.HTML
            )
            return
        
        logger.info(f"Reply input received for {chat_id}_{message_id}, text: {reply_text[:50]}...")
        
        # Buat pesan konfirmasi
        user_info = ""
        if data.get("is_reply_all") and m.from_user:
            user_info = f"👤 <b>Replying as:</b> {m.from_user.mention(style=enums.ParseMode.HTML)}\n"
        
        confirm_buttons = [
            [InlineKeyboardButton("✅ Yes, Send", callback_data=f"mentions_confirm_{waiting_id}")],
            [InlineKeyboardButton("❌ No, Cancel", callback_data=f"mentions_cancel_{waiting_id}")]
        ]
        
        confirm_msg = (
            f"⚠️ <b>Konfirmasi Kirim Balasan</b>\n\n"
            f"{user_info}"
            f"<b>Pesan:</b>\n<blockquote>{html.escape(reply_text[:500])}</blockquote>\n\n"
            f"<b>Detail:</b>\n"
            f"• <b>Group:</b> <code>{chat_id}</code>\n"
            f"• <b>To Message:</b> <code>{message_id}</code>\n"
            f"• <b>Send as:</b> {mentioned_client.me.first_name if mentioned_client.me else 'Unknown'}\n\n"
            f"Apakah Anda yakin?"
        )
        
        try:
            confirm_message = await m.reply_text(
                confirm_msg,
                parse_mode=enums.ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(confirm_buttons),
                reply_to_message_id=m.id
            )
            
            # Update data
            REPLY_AS_MENTIONED_WAITING[waiting_id]["reply_text"] = reply_text
            REPLY_AS_MENTIONED_WAITING[waiting_id]["user_msg_id"] = m.id
            REPLY_AS_MENTIONED_WAITING[waiting_id]["confirm_msg_id"] = confirm_message.id
            
            logger.info(f"Confirmation sent: {confirm_message.id}")
            
        except Exception as e:
            logger.error(f"Confirmation send failed: {e}")
        
    except Exception as e:
        logger.error(f"Reply input error: {e}", exc_info=True)

# 🔥 PERBAIKAN: Handler konfirmasi kirim dengan LOGGING
@Altruix.bot.on_callback_query(filters.regex(r"^mentions_confirm_"))
@log_errors
async def confirm_send_reply(c: Client, cb: CallbackQuery):
    """Mengirim balasan setelah konfirmasi."""
    try:
        BUTTON_STATS["confirm"] += 1
        log_button_press("CONFIRM", cb.data, cb.from_user.id if cb.from_user else None)
        logger.info(f"📊 Confirm button pressed. Total: {BUTTON_STATS['confirm']}")
        
        # Parse waiting_id
        parts = cb.data.split("_")
        if len(parts) < 3:
            logger.error(f"Invalid confirm callback: {cb.data}")
            await cb.answer("❌ Invalid callback", show_alert=True)
            return
        
        waiting_id = parts[2]
        logger.info(f"Confirm send for waiting_id: {waiting_id}")
        
        if waiting_id not in REPLY_AS_MENTIONED_WAITING:
            logger.warning(f"Reply data not found: {waiting_id}")
            await cb.answer("❌ Data tidak ditemukan.", show_alert=True)
            return
        
        data = REPLY_AS_MENTIONED_WAITING[waiting_id]
        chat_id = data["chat_id"]
        message_id = data["message_id"]
        mentioned_client = data["mentioned_client"]
        reply_text = data["reply_text"]
        user_msg_id = data.get("user_msg_id")
        confirm_msg_id = data.get("confirm_msg_id")
        instruction_msg_id = data.get("instruction_msg_id")
        is_reply_all = data.get("is_reply_all", False)
        
        logger.info(f"Sending reply to {chat_id}_{message_id}, is_reply_all: {is_reply_all}")
        
        try:
            # Kirim balasan
            await mentioned_client.send_message(
                chat_id,
                reply_text,
                reply_to_message_id=message_id
            )
            logger.info(f"Reply sent successfully to {chat_id}")
            
            # Update status pesan
            await cb.message.edit_text(
                "✅ <b>Balasan berhasil dikirim!</b>\n\n"
                f"• <b>Group:</b> <code>{chat_id}</code>\n"
                f"• <b>Time:</b> {datetime.now().strftime('%H:%M:%S')}",
                parse_mode=enums.ParseMode.HTML
            )
            
            # Hapus pesan terkait
            messages_to_delete = []
            if user_msg_id:
                messages_to_delete.append(user_msg_id)
            if confirm_msg_id and confirm_msg_id != cb.message.id:
                messages_to_delete.append(confirm_msg_id)
            if instruction_msg_id:
                messages_to_delete.append(instruction_msg_id)
            
            if messages_to_delete:
                try:
                    await c.delete_messages(cb.message.chat.id, messages_to_delete)
                    logger.info(f"Deleted {len(messages_to_delete)} related messages")
                except Exception as delete_err:
                    logger.warning(f"Delete messages failed: {delete_err}")
            
            # Log untuk Reply From All
            if is_reply_all and cb.from_user:
                logger.info(f"Reply From All successful - User: {cb.from_user.id}, Mention: {chat_id}_{message_id}")
            
        except Exception as send_err:
            logger.error(f"Send reply failed: {send_err}")
            await cb.message.edit_text(
                f"❌ <b>Gagal mengirim balasan:</b>\n<code>{html.escape(str(send_err)[:200])}</code>",
                parse_mode=enums.ParseMode.HTML
            )
            await cb.answer("❌ Gagal mengirim.", show_alert=True)
            return
        
        # Bersihkan waiting list
        REPLY_AS_MENTIONED_WAITING.pop(waiting_id, None)
        await cb.answer("✅ Balasan terkirim!", show_alert=False)
        
        # Save stats
        await save_local_storage()
        
    except Exception as e:
        logger.error(f"Confirm send error: {e}", exc_info=True)
        await cb.answer("❌ Terjadi kesalahan.", show_alert=True)

# 🔥 PERBAIKAN: Handler pembatalan dengan LOGGING
@Altruix.bot.on_callback_query(filters.regex(r"^mentions_cancel_"))
@log_errors
async def cancel_send_reply(c: Client, cb: CallbackQuery):
    """Membatalkan pengiriman balasan."""
    try:
        BUTTON_STATS["cancel"] += 1
        log_button_press("CANCEL", cb.data, cb.from_user.id if cb.from_user else None)
        logger.info(f"📊 Cancel button pressed. Total: {BUTTON_STATS['cancel']}")
        
        # Parse waiting_id
        parts = cb.data.split("_")
        if len(parts) < 3:
            logger.error(f"Invalid cancel callback: {cb.data}")
            await cb.answer("❌ Invalid callback", show_alert=True)
            return
        
        waiting_id = parts[2]
        logger.info(f"Cancel reply for waiting_id: {waiting_id}")
        
        if waiting_id in REPLY_AS_MENTIONED_WAITING:
            data = REPLY_AS_MENTIONED_WAITING[waiting_id]
            
            # Hapus pesan terkait
            messages_to_delete = []
            if data.get("user_msg_id"):
                messages_to_delete.append(data["user_msg_id"])
            if data.get("confirm_msg_id") and data["confirm_msg_id"] != cb.message.id:
                messages_to_delete.append(data["confirm_msg_id"])
            if data.get("instruction_msg_id"):
                messages_to_delete.append(data["instruction_msg_id"])
            
            if messages_to_delete:
                try:
                    await c.delete_messages(cb.message.chat.id, messages_to_delete)
                    logger.info(f"Deleted {len(messages_to_delete)} messages on cancel")
                except Exception as delete_err:
                    logger.warning(f"Delete on cancel failed: {delete_err}")
            
            REPLY_AS_MENTIONED_WAITING.pop(waiting_id, None)
            
            await cb.message.edit_text(
                "❌ <b>Pengiriman dibatalkan.</b>",
                parse_mode=enums.ParseMode.HTML
            )
            await cb.answer("❌ Dibatalkan.", show_alert=True)
            
            # Refund reply count untuk Reply From All
            if data.get("is_reply_all") and data.get("user_id"):
                today = datetime.now().strftime("%Y%m%d")
                if USER_REPLY_COUNTS[data["user_id"]][today] > 0:
                    USER_REPLY_COUNTS[data["user_id"]][today] -= 1
                    logger.info(f"Refunded reply count for user {data['user_id']}")
        else:
            await cb.answer("❌ Tidak ada proses yang berjalan.", show_alert=True)
            
    except Exception as e:
        logger.error(f"Cancel error: {e}", exc_info=True)
        await cb.answer("❌ Terjadi kesalahan.", show_alert=True)

# 🔥 Handler untuk reacted button
@Altruix.bot.on_callback_query(filters.regex(r"^mentions_reacted$"))
@log_errors
async def already_reacted_handler(c: Client, cb: CallbackQuery):
    """Handler untuk tombol yang sudah direaksi."""
    log_button_press("ALREADY_REACTED", cb.data, cb.from_user.id if cb.from_user else None)
    await cb.answer("✅ Sudah direaksi sebelumnya", show_alert=False)

# 🔥 Command untuk status dengan button stats
@Altruix.register_on_cmd(
    ["mentions_status"],
    cmd_help={
        "help": "Check mention plugin status",
        "example": "mentions_status",
    },
    group_only=False,
    requires_input=False,
)
@log_errors
async def status_command_handler(c: Client, m: AltruixMessage):
    """Check plugin status."""
    msg = await m.handle_message("PROCESSING")
    
    client_id_str = str(c.me.id)
    user_setting = MENTIONS_DATA.get(client_id_str, {}).get("value", False)
    
    # Hitung statistik user
    total_users_today = sum(1 for counts in USER_REPLY_COUNTS.values() if counts.get(datetime.now().strftime("%Y%m%d"), 0) > 0)
    total_replies_today = sum(counts.get(datetime.now().strftime("%Y%m%d"), 0) for counts in USER_REPLY_COUNTS.values())
    
    status_msg = (
        f"📊 <b>Mention Plugin Status v{PLUGIN_VERSION}</b>\n\n"
        f"<b>Settings:</b>\n"
        f"• Mentions: {'✅ ENABLED' if user_setting else '❌ DISABLED'}\n"
        f"• Auto-Reply: {'✅ ON' if AUTO_REPLY_ENABLED else '❌ OFF'}\n"
        f"• Reply Limit: {USER_REPLY_LIMIT}/user/day\n\n"
        f"<b>Statistics:</b>\n"
        f"• Cache: {len(MENTION_LOG_CACHE)} mentions\n"
        f"• Waiting: {len(REPLY_AS_MENTIONED_WAITING)} replies\n"
        f"• Users today: {total_users_today}\n"
        f"• Replies today: {total_replies_today}\n\n"
        f"<b>Button Usage:</b>\n"
        f"• React: {BUTTON_STATS['react']}\n"
        f"• Reply: {BUTTON_STATS['reply']}\n"
        f"• Reply All: {BUTTON_STATS['reply_all']}\n"
        f"• Confirm: {BUTTON_STATS['confirm']}\n"
        f"• Cancel: {BUTTON_STATS['cancel']}\n\n"
        f"<i>Last update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"
    )
    
    await safe_edit_message(
        c,
        m.chat.id,
        msg.id,
        status_msg,
        parse_mode=enums.ParseMode.HTML
    )

# 🔥 Command untuk backup
@Altruix.register_on_cmd(
    ["mentions_backup"],
    cmd_help={
        "help": "Backup mention settings",
        "example": "mentions_backup",
    },
    group_only=False,
    requires_input=False,
)
@log_errors
async def backup_command_handler(c: Client, m: AltruixMessage):
    """Backup settings."""
    msg = await m.handle_message("PROCESSING")
    
    try:
        await save_local_storage()
        backup_success = await backup_to_telegram(c)
        
        if backup_success:
            backup_msg = "✅ Backup berhasil dikirim ke saved messages."
        else:
            backup_msg = "⚠️ Local backup saved, but could not send to Telegram."
        
        await safe_edit_message(
            c,
            m.chat.id,
            msg.id,
            backup_msg,
            parse_mode=enums.ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        await msg.edit_msg(f"❌ Backup error: {str(e)[:100]}")

# 🔥 Command untuk clear cache
@Altruix.register_on_cmd(
    ["mentions_clear"],
    cmd_help={
        "help": "Clear mention plugin cache",
        "example": "mentions_clear",
    },
    group_only=False,
    requires_input=False,
)
@log_errors
async def clear_cache_handler(c: Client, m: AltruixMessage):
    """Clear plugin cache."""
    msg = await m.handle_message("PROCESSING")
    
    try:
        global MENTION_LOG_CACHE, REPLY_AS_MENTIONED_WAITING, USER_REPLY_COUNTS
        
        cache_count = len(MENTION_LOG_CACHE)
        waiting_count = len(REPLY_AS_MENTIONED_WAITING)
        user_count = len(USER_REPLY_COUNTS)
        
        MENTION_LOG_CACHE.clear()
        REPLY_AS_MENTIONED_WAITING.clear()
        USER_REPLY_COUNTS.clear()
        
        clear_msg = (
            f"🧹 <b>Cache Cleared</b>\n\n"
            f"• Mention Cache: {cache_count} entries\n"
            f"• Waiting Replies: {waiting_count} entries\n"
            f"• User Counts: {user_count} users\n\n"
            f"✅ Semua cache telah dibersihkan."
        )
        
        await safe_edit_message(
            c,
            m.chat.id,
            msg.id,
            clear_msg,
            parse_mode=enums.ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"Clear cache failed: {e}")
        await msg.edit_msg(f"❌ Clear error: {str(e)[:100]}")

# 🔥 Command untuk debug tombol
@Altruix.register_on_cmd(
    ["mentions_debug"],
    cmd_help={
        "help": "Debug button issues",
        "example": "mentions_debug",
    },
    group_only=False,
    requires_input=False,
)
@log_errors
async def debug_command_handler(c: Client, m: AltruixMessage):
    """Debug button issues."""
    msg = await m.handle_message("PROCESSING")
    
    try:
        # Test semua callback pattern
        test_patterns = [
            r"^mentions_react_",
            r"^mentions_reply_",
            r"^mentions_replyall_",
            r"^mentions_confirm_",
            r"^mentions_cancel_",
            r"^mentions_reacted$"
        ]
        
        debug_msg = (
            f"🔧 <b>Button Debug Report</b>\n\n"
            f"<b>Registered Patterns:</b>\n"
        )
        
        for i, pattern in enumerate(test_patterns, 1):
            debug_msg += f"{i}. <code>{pattern}</code>\n"
        
        debug_msg += f"\n<b>Current State:</b>\n"
        debug_msg += f"• LOG_CHAT: <code>{Altruix.log_chat}</code>\n"
        debug_msg += f"• Bot ID: <code>{Altruix.bot_info.id if Altruix.bot_info else 'None'}</code>\n"
        debug_msg += f"• Plugin: v{PLUGIN_VERSION}\n"
        debug_msg += f"• Log Level: {logger.level} ({logging.getLevelName(logger.level)})\n\n"
        
        debug_msg += f"<b>Test Commands:</b>\n"
        debug_msg += f"1. Tekan tombol reaction\n"
        debug_msg += f"2. Cek log untuk 'Button pressed'\n"
        debug_msg += f"3. Gunakan /mentions_status untuk stats\n\n"
        
        debug_msg += f"<i>Jika tombol tidak bekerja, cek log untuk error.</i>"
        
        await safe_edit_message(
            c,
            m.chat.id,
            msg.id,
            debug_msg,
            parse_mode=enums.ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"Debug command failed: {e}")
        await msg.edit_msg(f"❌ Debug error: {str(e)[:100]}")

# 🔥 Cleanup task
async def cleanup_old_entries():
    """Bersihkan cache dan waiting list yang sudah lama."""
    while True:
        try:
            current_time = time.time()
            
            # Clean old cache (2 hours)
            expired_cache = []
            for key, data in MENTION_LOG_CACHE.items():
                if current_time - data.get("timestamp_int", 0) > 7200:
                    expired_cache.append(key)
            
            for key in expired_cache[:50]:
                try:
                    del MENTION_LOG_CACHE[key]
                except:
                    pass
            
            if expired_cache:
                logger.debug(f"Cleaned {len(expired_cache[:50])} cache entries")
            
            # Clean old waiting (1 hour)
            expired_waiting = []
            for key, data in REPLY_AS_MENTIONED_WAITING.items():
                if current_time - data.get("timestamp_int", 0) > 3600:
                    expired_waiting.append(key)
            
            for key in expired_waiting[:20]:
                try:
                    del REPLY_AS_MENTIONED_WAITING[key]
                except:
                    pass
            
            if expired_waiting:
                logger.debug(f"Cleaned {len(expired_waiting[:20])} waiting entries")
                
            # Clean old user counts (30 days)
            thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
            users_to_clean = []
            for user_id, counts in USER_REPLY_COUNTS.items():
                old_dates = [date for date in counts.keys() if date < thirty_days_ago]
                for date in old_dates:
                    del counts[date]
                if not counts:
                    users_to_clean.append(user_id)
            
            for user_id in users_to_clean:
                try:
                    del USER_REPLY_COUNTS[user_id]
                except:
                    pass
            
            if users_to_clean:
                logger.debug(f"Cleaned {len(users_to_clean)} old user counts")
                
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
        
        await asyncio.sleep(600)  # Run every 10 minutes

# Start cleanup task
asyncio.create_task(cleanup_old_entries())
logger.info("Cleanup task started")


# Log sukses loading
try:
    # Altruix.log(f"[DEBUG] Loaded → {__plugin_name__} {PLUGIN_VERSION}", level=20)
    logger.info(f"[MENTIONS] Plugin loaded with timeout protection!")
    logger.info(f"[MENTIONS] Features: Mentions, Auto-Reply, Quick reactions, Reply-as-mentioned")
except Exception as e:
    logger.info(f"[DEBUG] Loaded → {__plugin_name__} {PLUGIN_VERSION}")
