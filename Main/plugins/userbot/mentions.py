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
PLUGIN_VERSION = "0.2.6.1"  # 🔥 VERSI DIPERBAIKI: Button Reply Fixed


# 🔥 SETUP LOGGING DETAILED
logger = logging.getLogger(f"{__plugin_name__}")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - [MENTIONS] - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

# 🔥 LOG STARTUP
logger.info(f"🚀 Initializing mentions plugin v{PLUGIN_VERSION}")

# 🔥 PERBAIKAN: Helper functions
def log_button_press(button_name: str, data: str, user_id: Optional[int] = None):
    """Log setiap tombol yang ditekan."""
    user_info = f" by user {user_id}" if user_id else ""
    logger.debug(f"🔘 Button '{button_name}' pressed{user_info}: {data}")

def safe_datetime_fromtimestamp(timestamp) -> datetime:
    """Convert timestamp to datetime."""
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

# 🔥 PERBAIKAN CRITICAL: Emoji yang valid untuk Telegram Reaction API
# Hanya emoji yang didukung oleh Telegram Reaction API
DEFAULT_REACTION_EMOJIS = ["👍", "❤️", "🔥", "🥰", "👏"]

# 🔥 TAMBAHAN: Dictionary untuk menunggu konfirmasi reply-as-mentioned
REPLY_AS_MENTIONED_WAITING = {}

# 🔥 PERBAIKAN: Flag untuk auto-reply
AUTO_REPLY_ENABLED = False

# 🔥 PERBAIKAN: Rate limiting untuk Reply From All
USER_REPLY_COUNTS = defaultdict(lambda: defaultdict(int))
USER_REPLY_LIMIT = 3

# 🔥 BARU: Button press statistics
BUTTON_STATS = {
    "react": 0,
    "reply": 0,
    "reply_all": 0,
    "confirm": 0,
    "cancel": 0
}

# 🔥 BARU: Valid emoji checker
VALID_REACTION_EMOJIS = {
    "👍", "👎", "❤️", "🔥", "🥰", "👏", "😁", "🤔", "🤯", "😱", 
    "🤬", "😢", "🎉", "🤩", "🤮", "💩", "🙏", "👌", "🕊", "🤡",
    "🥱", "🥴", "😍", "🐳", "❤️‍🔥", "🌚", "🌭", "💯", "🤣", "⚡",
    "🍌", "🏆", "💔", "🤨", "😐", "🍓", "🍾", "💋", "🖕", "😈",
    "😴", "😭", "🤓", "👻", "👨‍💻", "👀", "🎃", "🙈", "😇", "😨",
    "🤝", "✍️", "🤗", "🫡", "🎅", "🎄", "☃️", "💅", "🤪", "🗿",
    "🆒", "💘", "🙉", "🦄", "😘", "💊", "🙊", "😎", "👾", "🤷‍♂️",
    "🤷", "🤷‍♀️", "😡"
}

def is_valid_emoji(emoji: str) -> bool:
    """Cek apakah emoji valid untuk Telegram Reaction."""
    return emoji in VALID_REACTION_EMOJIS

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
    except Exception as e:
        logger.error(f"Failed to load local storage: {e}")
        MENTIONS_DATA = {}
        AUTO_REPLY_ENABLED = False

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
    except Exception as e:
        logger.error(f"Failed to save local storage: {e}")

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

# 🔥 BARU: Fungsi untuk mendapatkan client dari client_id - FIXED!
async def get_mention_client(client_id: int) -> Optional[Client]:
    """Get client for mention reply dari session manager Altruix."""
    try:
        logger.info(f"🔍 [get_mention_client] Looking for client with ID: {client_id}")
        
        # 1. Cek jika ini adalah bot client
        if hasattr(Altruix, 'bot') and Altruix.bot and hasattr(Altruix.bot, 'me') and Altruix.bot.me.id == client_id:
            logger.info(f"✅ [get_mention_client] Found bot client for ID {client_id}")
            return Altruix.bot
        
        # 2. Cari di semua userbot clients yang aktif (jika ada)
        if hasattr(Altruix, 'userbot_clients') and Altruix.userbot_clients:
            logger.info(f"🔍 [get_mention_client] Checking {len(Altruix.userbot_clients)} userbot clients")
            for idx, ub in enumerate(Altruix.userbot_clients):
                try:
                    if ub and hasattr(ub, 'me') and ub.me and ub.me.id == client_id:
                        logger.info(f"✅ [get_mention_client] Found userbot client at index {idx}: {ub.me.first_name} ({client_id})")
                        return ub
                except Exception as e:
                    logger.warning(f"⚠️ [get_mention_client] Error checking userbot client at index {idx}: {e}")
                    continue
        
        # 3. Coba cari di ubot utama
        if hasattr(Altruix, 'ubot') and Altruix.ubot:
            try:
                if Altruix.ubot.me and Altruix.ubot.me.id == client_id:
                    logger.info(f"✅ [get_mention_client] Found main ubot: {Altruix.ubot.me.first_name}")
                    return Altruix.ubot
            except Exception as e:
                logger.warning(f"⚠️ [get_mention_client] Error checking main ubot: {e}")
        
        # 4. Cari di semua clients Altruix yang terdaftar - FIXED untuk handle list/dict
        if hasattr(Altruix, 'clients'):
            clients = Altruix.clients
            logger.info(f"🔍 [get_mention_client] Altruix.clients type: {type(clients)}")
            
            if isinstance(clients, dict):
                for client_name, client_obj in clients.items():
                    try:
                        if client_obj and hasattr(client_obj, 'me') and client_obj.me and client_obj.me.id == client_id:
                            logger.info(f"✅ [get_mention_client] Found client in Altruix.clients dict: {client_name}")
                            return client_obj
                    except Exception as e:
                        logger.warning(f"⚠️ [get_mention_client] Error checking client {client_name}: {e}")
                        continue
            elif isinstance(clients, list):
                for idx, client_obj in enumerate(clients):
                    try:
                        if client_obj and hasattr(client_obj, 'me') and client_obj.me and client_obj.me.id == client_id:
                            logger.info(f"✅ [get_mention_client] Found client in Altruix.clients list index {idx}")
                            return client_obj
                    except Exception as e:
                        logger.warning(f"⚠️ [get_mention_client] Error checking client at index {idx}: {e}")
                        continue
            else:
                logger.warning(f"⚠️ [get_mention_client] Altruix.clients is of unknown type: {type(clients)}")
        else:
            logger.warning(f"⚠️ [get_mention_client] Altruix.clients not found")
        
        # 5. Last resort: coba cari di session manager
        try:
            from Main.core.clients.session_manager import session_manager
            sessions = session_manager.get_sessions()
            logger.info(f"🔍 [get_mention_client] Checking {len(sessions)} sessions")
            for session in sessions:
                if session.is_active and session.user_id == client_id:
                    logger.info(f"✅ [get_mention_client] Found active session for user_id: {client_id}")
                    # Get client from session
                    return await session.get_client()
        except Exception as e:
            logger.warning(f"⚠️ [get_mention_client] Session manager check failed: {e}")
        
        # 6. Debug semua userbot clients yang tersedia
        if hasattr(Altruix, 'userbot_clients') and Altruix.userbot_clients:
            logger.info(f"🔍 [get_mention_client] Available userbot client IDs:")
            for idx, ub in enumerate(Altruix.userbot_clients):
                try:
                    if ub and hasattr(ub, 'me') and ub.me:
                        logger.info(f"  {idx}. {ub.me.first_name} ({ub.me.id})")
                    else:
                        logger.info(f"  {idx}. Invalid client object")
                except Exception as e:
                    logger.info(f"  {idx}. Error getting client info: {e}")
        
        logger.warning(f"❌ [get_mention_client] Client {client_id} not found in any active sessions")
        return None
    except Exception as e:
        logger.error(f"❌ [get_mention_client] Error getting client: {e}", exc_info=True)
        return None

# 🔥 Load local storage
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
        
        status_msg = f"{emoji} **Mention notifications {status_text}**"
        await safe_edit_message(c, m.chat.id, msg.id, status_msg, parse_mode=enums.ParseMode.MARKDOWN)
        
    except Exception as e:
        logger.error(f"Save failed: {e}")
        await msg.edit_msg(f"❌ Save error: {str(e)[:100]}")

@Altruix.on_message(
    filters.mentioned & filters.group & ~filters.user(Altruix.bot_info.id)
)
@log_errors
async def send_mention_log_handler(c: Client, m: RawMessage):
    """Handler utama untuk menangkap mention dan mengirim notifikasi ke LOG_CHAT."""
    try:
        # Cek apakah log_chat dikonfigurasi
        if not Altruix.log_chat:
            logger.error("LOG_CHAT not configured, cannot send mention notifications")
            return
            
        # Cek apakah bot bisa mengirim pesan ke log_chat
        try:
            await Altruix.bot.get_chat(Altruix.log_chat)
        except Exception as chat_err:
            logger.error(f"Cannot access log chat {Altruix.log_chat}: {chat_err}")
            return
            
        client_id = c.me.id
        
        # Cek apakah mention notifications enabled
        is_enabled = await get_mention_setting_safe(client_id)
        if not is_enabled:
            logger.debug(f"Mentions disabled for {client_id}")
            return

        logger.info(f"📩 Processing mention for {c.me.first_name} ({client_id})")
        
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
            mention_time = datetime.now().strftime("%Y-%m-d %H:%M:%S")
        
        # Bangun pesan notifikasi
        log_message = (
            f"🔔 <b>Mention Detected!</b>\n\n"
            f"👤 <b>Mentioned By:</b> {mentioner_hyperlink} (<code>{mentioner_id}</code>)\n"
            f"🤖 <b>My Account:</b> {c.me.mention(style=enums.ParseMode.HTML)}\n"
            f"💬 <b>Group:</b> {html.escape(m.chat.title)} (<code>{m.chat.id}</code>)\n"
            f"🕒 <b>Time:</b> <code>{mention_time}</code>\n"
            f"📄 <b>Message:</b>\n<blockquote>{message_text}</blockquote>"
        )
        
        # PERBAIKAN: Tombol dengan callback data yang benar
        reaction_buttons = [
            InlineKeyboardButton(
                emoji,
                callback_data=f"mentions_react_{m.chat.id}_{m.id}_{emoji}"
            )
            for emoji in DEFAULT_REACTION_EMOJIS
        ]
        
        reply_button = [InlineKeyboardButton(
            "🗨️ Reply as Mentioned",
            callback_data=f"mentions_reply_{m.chat.id}_{m.id}"
        )]
        
        reply_all_button = [InlineKeyboardButton(
            "👥 Reply From All",
            callback_data=f"mentions_replyall_{m.chat.id}_{m.id}"
        )]
        
        link_button = [InlineKeyboardButton("🔗 Go to Message", url=m.link)]
        
        # PERBAIKAN: Keyboard layout yang benar
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
            logger.info(f"📤 Notification sent for {msg_key}, message_id: {sent_log_msg.id}")
            
        except Exception as send_err:
            logger.error(f"Send failed: {send_err}")
            return
        
        # Cache untuk edit detection - SIMPAN client_id BUKAN objek Client
        MENTION_LOG_CACHE[msg_key] = {
            "text": message_text,
            "log_msg_id": sent_log_msg.id,
            "client_id": client_id,  # Simpan ID saja
            "chat_id": m.chat.id,
            "message_id": m.id,
            "timestamp_int": int(time.time()),
            "mentioned_by": mentioner_id,
            "group_name": m.chat.title,
            "client_name": c.me.first_name if c.me else "Unknown"
        }
        
        logger.info(f"✅ Cached mention: {msg_key} for client {client_id} ({c.me.first_name})")
        
    except Exception as e:
        logger.error(f"❌ Error in mention handler: {e}", exc_info=True)

# 🔥 PERBAIKAN UTAMA: Handler untuk quick reaction - FIX EMOJI VALIDATION
@Altruix.bot.on_callback_query(filters.regex(r"^mentions_react_"))
@log_errors
async def quick_reaction_handler(c: Client, cb: CallbackQuery):
    """Kirim reaksi ke pesan asli di grup."""
    try:
        BUTTON_STATS["react"] += 1
        log_button_press("REACT", cb.data, cb.from_user.id if cb.from_user else None)
        logger.info(f"📊 React button pressed. Total: {BUTTON_STATS['react']}")
        
        # PERBAIKAN: Parse callback data dengan benar
        # Format: mentions_react_{chat_id}_{message_id}_{emoji}
        pattern = r"mentions_react_(-?\d+)_(\d+)_(.+)"
        match = re.match(pattern, cb.data)
        
        if not match:
            logger.error(f"Invalid react callback data: {cb.data}")
            await cb.answer("❌ Invalid callback data", show_alert=True)
            return
        
        chat_id = int(match.group(1))
        message_id = int(match.group(2))
        emoji = match.group(3)
        
        # PERBAIKAN KRITIS: Validasi emoji sebelum dikirim
        if not is_valid_emoji(emoji):
            logger.error(f"Invalid emoji for reaction: {emoji}")
            await cb.answer(f"❌ Emoji '{emoji}' tidak didukung untuk reaction", show_alert=True)
            return
        
        msg_key = f"{chat_id}_{message_id}"
        logger.info(f"🔄 Processing reaction for {msg_key} with {emoji}")
        
        if msg_key not in MENTION_LOG_CACHE:
            logger.warning(f"❌ Mention not in cache: {msg_key}")
            await cb.answer("❌ Mention tidak ditemukan di cache.", show_alert=True)
            return
        
        # DAPATKAN CLIENT DARI CLIENT_ID
        cache_data = MENTION_LOG_CACHE[msg_key]
        client_id = cache_data["client_id"]
        logger.info(f"🔍 Looking for client with ID: {client_id}")
        
        userbot_client = await get_mention_client(client_id)
        
        if not userbot_client:
            logger.warning(f"❌ Userbot client not available for ID: {client_id}")
            # Coba tampilkan info cache untuk debug
            logger.info(f"Cache data: {cache_data}")
            await cb.answer("❌ Akun yang disebut tidak tersedia atau tidak aktif.", show_alert=True)
            return
        
        try:
            # PERBAIKAN: Kirim reaction dengan error handling
            logger.info(f"⚡ Sending reaction {emoji} to {chat_id}:{message_id}")
            await userbot_client.send_reaction(chat_id, message_id, emoji)
            logger.info(f"✅ Reaction sent: {emoji} to {msg_key}")
            
            # Update tombol untuk show success
            try:
                # Cari tombol yang sesuai untuk diupdate
                if cb.message.reply_markup:
                    new_keyboard = []
                    for row in cb.message.reply_markup.inline_keyboard:
                        new_row = []
                        for button in row:
                            # Cek apakah ini tombol reaction dengan emoji yang sama
                            if button.callback_data and button.callback_data == cb.data:
                                # Buat tombol baru yang sudah direaksi
                                new_row.append(InlineKeyboardButton(
                                    f"✅ {emoji}", 
                                    callback_data="mentions_reacted"
                                ))
                            else:
                                new_row.append(button)
                        new_keyboard.append(new_row)
                    
                    # Edit hanya reply_markup saja
                    await cb.message.edit_reply_markup(
                        InlineKeyboardMarkup(new_keyboard)
                    )
                    logger.debug(f"✅ Button updated for {emoji}")
            except Exception as edit_err:
                logger.warning(f"⚠️ Could not update button: {edit_err}")
                # Tidak fatal, lanjutkan saja
            
            await cb.answer(f"✅ Bereaksi dengan {emoji}", show_alert=False)
            
        except Exception as react_err:
            error_msg = str(react_err)
            logger.error(f"❌ Reaction failed: {error_msg}")
            
            # Handle specific errors
            if "REACTION_INVALID" in error_msg:
                await cb.answer(f"❌ Emoji '{emoji}' tidak valid untuk reaction", show_alert=True)
            elif "MESSAGE_NOT_MODIFIED" in error_msg:
                await cb.answer(f"✅ Sudah direaksi dengan {emoji}", show_alert=False)
            elif "MESSAGE_ID_INVALID" in error_msg or "msg_id" in error_msg.lower():
                await cb.answer(f"❌ Pesan tidak ditemukan atau sudah dihapus", show_alert=True)
            elif "CHAT_ADMIN_REQUIRED" in error_msg:
                await cb.answer(f"❌ Tidak punya akses admin di grup tersebut", show_alert=True)
            else:
                await cb.answer(f"❌ Gagal: {error_msg[:50]}", show_alert=True)
            
    except Exception as e:
        logger.error(f"❌ Quick reaction error: {e}", exc_info=True)
        await cb.answer("❌ Terjadi kesalahan.", show_alert=True)

# 🔥 PERBAIKAN: Handler untuk Reply From All - DIPINDAHKAN KE ATAS & FIXED
# Menggunakan regex yang lebih spesifik dan urutan yang benar
@Altruix.bot.on_callback_query(filters.regex(r"^mentions_replyall_"))
@log_errors
async def start_reply_from_all(c: Client, cb: CallbackQuery):
    """Memulai proses reply-from-all untuk semua user."""
    try:
        # 1. Log Aktivitas
        BUTTON_STATS["reply_all"] += 1
        log_button_press("REPLY_ALL", cb.data, cb.from_user.id if cb.from_user else None)
        logger.info(f"📊 Reply All button pressed. Total: {BUTTON_STATS['reply_all']}")
        
        # 2. Parse Data dengan Aman
        # Format: mentions_replyall_{chat_id}_{message_id}
        pattern = r"mentions_replyall_(-?\d+)_(\d+)"
        match = re.match(pattern, cb.data)
        
        if not match:
            logger.error(f"❌ Invalid replyall callback data: {cb.data}")
            await cb.answer("❌ Data tombol tidak valid", show_alert=True)
            return
        
        chat_id = int(match.group(1))
        message_id = int(match.group(2))
        msg_key = f"{chat_id}_{message_id}"
        
        # 3. Validasi User
        user_id = cb.from_user.id if cb.from_user else None
        if not user_id:
            await cb.answer("❌ User tidak dikenal", show_alert=True)
            return
        
        # 4. Cek Rate Limit (Anti-Spam)
        today = datetime.now().strftime("%Y%m%d")
        if USER_REPLY_COUNTS[user_id][today] >= USER_REPLY_LIMIT:
            logger.warning(f"⚠️ User {user_id} hit rate limit for today")
            await cb.answer(
                f"❌ Batas reply tercapai ({USER_REPLY_LIMIT}x per hari). Coba lagi besok.",
                show_alert=True
            )
            return
        
        # 5. Cek Ketersediaan Cache
        if msg_key not in MENTION_LOG_CACHE:
            logger.warning(f"❌ Mention not in cache: {msg_key}")
            await cb.answer("❌ Data mention kadaluarsa atau hilang (restarted).", show_alert=True)
            return
        
        # 6. Dapatkan Client Userbot
        cache_data = MENTION_LOG_CACHE[msg_key]
        client_id = cache_data["client_id"]
        logger.info(f"🔍 Looking for client with ID: {client_id}")
        
        mentioned_client = await get_mention_client(client_id)
        
        if not mentioned_client:
            logger.warning(f"❌ Userbot client not available for ID: {client_id}")
            await cb.answer("❌ Akun userbot tidak aktif/offline.", show_alert=True)
            return
        
        # 7. Generate Waiting ID unik
        waiting_id = f"replyall_{int(time.time())}_{cb.id}"
        REPLY_AS_MENTIONED_WAITING[waiting_id] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "client_id": client_id,
            "log_msg_id": cb.message.id,
            "user_id": user_id,
            "timestamp_int": int(time.time()),
            "callback_message_id": cb.message.id,
            "is_reply_all": True,
            "waiting_id": waiting_id,
            "msg_key": msg_key
        }
        
        logger.info(f"⏳ Reply From All waiting for {msg_key}, user: {user_id}, waiting_id: {waiting_id}")
        
        # 8. Kirim Instruksi ke User
        try:
            user_mention = cb.from_user.mention(style=enums.ParseMode.HTML) if cb.from_user else "User"
            client_name = mentioned_client.me.first_name if mentioned_client.me else "Unknown"
            
            instruction_msg = await cb.message.reply(
                f"� <b>Reply From All</b>\n\n"
                f"Halo {user_mention}!\n\n"
                f"Silakan ketik pesan balasan Anda di bawah ini.\n"
                f"Pesan akan dikirim sebagai <b>{client_name}</b> ke grup asal.\n\n"
                f"<i>Note: Maksimal {USER_REPLY_LIMIT}x reply per hari per mention</i>\n"
                f"<i>Balas pesan ini dengan teks yang ingin dikirim.</i>",
                parse_mode=enums.ParseMode.HTML,
                reply_parameters=ReplyParameters(
                    message_id=cb.message.id,
                    chat_id=cb.message.chat.id
                )
            )
            
            REPLY_AS_MENTIONED_WAITING[waiting_id]["instruction_msg_id"] = instruction_msg.id
            logger.info(f"📤 Reply All instruction sent: {instruction_msg.id}")
            
            # Update counter hanya jika instruksi berhasil dikirim
            USER_REPLY_COUNTS[user_id][today] += 1
            
            # FEEDBACK SUKSES KE USER
            await cb.answer("✅ Silakan ketik balasan Anda (Lihat pesan baru).", show_alert=False)
            
        except Exception as e:
            logger.error(f"❌ Reply All instruction failed: {e}")
            REPLY_AS_MENTIONED_WAITING.pop(waiting_id, None) # Hapus jika gagal
            await cb.answer("❌ Gagal mengirim pesan instruksi.", show_alert=True)
            return

    except Exception as e:
        logger.error(f"❌ Reply From All logic error: {e}", exc_info=True)
        await cb.answer(f"❌ Terjadi kesalahan sistem: {str(e)[:50]}", show_alert=True)


# 🔥 PERBAIKAN: Handler untuk Reply as Mentioned - UPDATED REGEX
# Regex updated matched ^mentions_reply_ followed by digits specifically
@Altruix.bot.on_callback_query(filters.regex(r"^mentions_reply_(-?\d+)_"))
@log_errors
async def start_reply_as_mentioned(c: Client, cb: CallbackQuery):
    """Memulai proses reply-as-mentioned."""
    try:
        # 1. Log Aktivitas
        BUTTON_STATS["reply"] += 1
        log_button_press("REPLY", cb.data, cb.from_user.id if cb.from_user else None)
        logger.info(f"📊 Reply button pressed. Total: {BUTTON_STATS['reply']}")
        
        # 2. Parse regex aman
        # Pattern disesuaikan agar tidak false match
        pattern = r"mentions_reply_(-?\d+)_(\d+)"
        match = re.match(pattern, cb.data)
        
        if not match:
            logger.error(f"❌ Invalid reply callback data: {cb.data}")
            await cb.answer("❌ Data tombol validasi gagal", show_alert=True)
            return
        
        chat_id = int(match.group(1))
        message_id = int(match.group(2))
        msg_key = f"{chat_id}_{message_id}"
        
        logger.info(f"🔄 Starting reply process for {msg_key}")
        
        # 3. Cek Cache
        if msg_key not in MENTION_LOG_CACHE:
            logger.warning(f"❌ Mention not in cache: {msg_key}")
            await cb.answer("❌ Data mention kadaluarsa/hilang. (Bot restart?)", show_alert=True)
            return
        
        cache_data = MENTION_LOG_CACHE[msg_key]
        
        # 4. Validasi Client
        client_id = cache_data["client_id"]
        logger.info(f"🔍 Looking for client with ID: {client_id}")
        
        mentioned_client = await get_mention_client(client_id)
        
        if not mentioned_client:
            logger.warning(f"❌ Userbot client not available for ID: {client_id}")
            await cb.answer("❌ Akun userbot tidak aktif saat ini.", show_alert=True)
            return
        
        # 5. Generate Waiting ID
        waiting_id = f"reply_{int(time.time())}_{cb.id}"
        REPLY_AS_MENTIONED_WAITING[waiting_id] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "client_id": client_id,
            "log_msg_id": cb.message.id,
            "user_id": cb.from_user.id if cb.from_user else None,
            "timestamp_int": int(time.time()),
            "callback_message_id": cb.message.id,
            "is_reply_all": False,
            "waiting_id": waiting_id,
            "msg_key": msg_key
        }
        
        logger.info(f"⏳ Waiting for reply input for {msg_key}, waiting_id: {waiting_id}")
        
        # 6. Kirim Instruksi
        try:
            instruction_msg = await cb.message.reply(
                "�️ <b>Reply as Mentioned</b>\n\n"
                "Silakan ketik pesan balasan Anda di bawah ini.\n"
                "Pesan akan dikirim sebagai akun yang disebut di grup asal.\n\n"
                "<i>Balas pesan ini dengan teks yang ingin dikirim.</i>",
                parse_mode=enums.ParseMode.HTML,
                reply_parameters=ReplyParameters(
                    message_id=cb.message.id,
                    chat_id=cb.message.chat.id
                )
            )
            
            REPLY_AS_MENTIONED_WAITING[waiting_id]["instruction_msg_id"] = instruction_msg.id
            logger.info(f"📤 Instruction sent: {instruction_msg.id}")
            
            # FEEDBACK SUKSES
            await cb.answer("✅ Silakan ketik balasan Anda.", show_alert=False)
            
        except Exception as e:
            logger.error(f"❌ Instruction send failed: {e}")
            REPLY_AS_MENTIONED_WAITING.pop(waiting_id, None) # Cleanup
            await cb.answer("❌ Gagal mengirim instruksi reply.", show_alert=True)
            return
        
    except Exception as e:
        logger.error(f"❌ Reply start error: {e}", exc_info=True)
        await cb.answer(f"❌ Error: {str(e)[:50]}", show_alert=True)

# 🔥 PERBAIKAN: Handler untuk menerima input balasan
@Altruix.bot.on_message(filters.chat(Altruix.log_chat) & filters.reply)
@log_errors
async def handle_reply_as_mentioned_input(c: Client, m: RawMessage):
    """Menangani input balasan untuk reply-as-mentioned."""
    try:
        if not m.reply_to_message:
            return
        
        reply_msg_id = m.reply_to_message.id
        logger.info(f"🔍 Checking reply input for message {reply_msg_id}")
        
        # Cari waiting_id berdasarkan instruction_msg_id
        waiting_id = None
        for wid, data in REPLY_AS_MENTIONED_WAITING.items():
            if data.get("instruction_msg_id") == reply_msg_id:
                waiting_id = wid
                break
        
        if not waiting_id or waiting_id not in REPLY_AS_MENTIONED_WAITING:
            logger.debug(f"⚠️ No waiting found for reply to {reply_msg_id}")
            return
        
        data = REPLY_AS_MENTIONED_WAITING[waiting_id]
        chat_id = data["chat_id"]
        message_id = data["message_id"]
        client_id = data["client_id"]
        
        # DAPATKAN CLIENT DARI CLIENT_ID
        logger.info(f"🔍 Looking for client with ID: {client_id}")
        mentioned_client = await get_mention_client(client_id)
        if not mentioned_client:
            logger.error(f"❌ Cannot find client {client_id} for reply")
            await m.reply(
                "❌ <b>Akun tidak ditemukan</b>\n\n"
                "Akun yang disebut tidak tersedia atau session sudah berakhir.",
                parse_mode=enums.ParseMode.HTML
            )
            return
        
        reply_text = m.text or m.caption or ""
        if not reply_text.strip():
            logger.warning(f"⚠️ Empty reply text from message {m.id}")
            await m.reply(
                "❌ <b>Pesan kosong</b>\n\nSilakan ketik pesan yang ingin dikirim.",
                parse_mode=enums.ParseMode.HTML,
                reply_parameters=ReplyParameters(
                    message_id=m.id,
                    chat_id=m.chat.id
                )
            )
            return
        
        logger.info(f"📩 Reply input received for {chat_id}_{message_id}, text: {reply_text[:50]}...")
        
        # Buat pesan konfirmasi
        user_info = ""
        if data.get("is_reply_all") and m.from_user:
            user_info = f"👤 <b>Replying as:</b> {m.from_user.mention(style=enums.ParseMode.HTML)}\n"
        
        client_name = mentioned_client.me.first_name if mentioned_client.me else "Unknown"
        
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
            f"• <b>Send as:</b> {client_name}\n\n"
            f"Apakah Anda yakin?"
        )
        
        try:
            confirm_message = await m.reply(
                confirm_msg,
                parse_mode=enums.ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(confirm_buttons),
                reply_parameters=ReplyParameters(
                    message_id=m.id,
                    chat_id=m.chat.id
                )
            )
            
            # Update data
            REPLY_AS_MENTIONED_WAITING[waiting_id]["reply_text"] = reply_text
            REPLY_AS_MENTIONED_WAITING[waiting_id]["user_msg_id"] = m.id
            REPLY_AS_MENTIONED_WAITING[waiting_id]["confirm_msg_id"] = confirm_message.id
            
            logger.info(f"📤 Confirmation sent: {confirm_message.id}")
            
        except Exception as e:
            logger.error(f"❌ Confirmation send failed: {e}")
        
    except Exception as e:
        logger.error(f"❌ Reply input error: {e}", exc_info=True)

# 🔥 PERBAIKAN: Handler konfirmasi kirim
@Altruix.bot.on_callback_query(filters.regex(r"^mentions_confirm_"))
@log_errors
async def confirm_send_reply(c: Client, cb: CallbackQuery):
    """Mengirim balasan setelah konfirmasi."""
    try:
        BUTTON_STATS["confirm"] += 1
        log_button_press("CONFIRM", cb.data, cb.from_user.id if cb.from_user else None)
        logger.info(f"📊 Confirm button pressed. Total: {BUTTON_STATS['confirm']}")
        
        # Parse waiting_id
        pattern = r"mentions_confirm_(.+)"
        match = re.match(pattern, cb.data)
        
        if not match:
            logger.error(f"❌ Invalid confirm callback: {cb.data}")
            await cb.answer("❌ Invalid callback", show_alert=True)
            return
        
        waiting_id = match.group(1)
        logger.info(f"🔄 Confirm send for waiting_id: {waiting_id}")
        
        if waiting_id not in REPLY_AS_MENTIONED_WAITING:
            logger.warning(f"❌ Reply data not found: {waiting_id}")
            await cb.answer("❌ Data tidak ditemukan.", show_alert=True)
            return
        
        data = REPLY_AS_MENTIONED_WAITING[waiting_id]
        chat_id = data["chat_id"]
        message_id = data["message_id"]
        client_id = data["client_id"]
        reply_text = data["reply_text"]
        user_msg_id = data.get("user_msg_id")
        confirm_msg_id = data.get("confirm_msg_id")
        instruction_msg_id = data.get("instruction_msg_id")
        is_reply_all = data.get("is_reply_all", False)
        
        logger.info(f"⚡ Sending reply to {chat_id}_{message_id}, is_reply_all: {is_reply_all}")
        
        # DAPATKAN CLIENT DARI CLIENT_ID
        logger.info(f"🔍 Looking for client with ID: {client_id}")
        mentioned_client = await get_mention_client(client_id)
        if not mentioned_client:
            logger.error(f"❌ Cannot find client {client_id} for sending reply")
            await cb.message.edit_text(
                "❌ <b>Gagal mengirim balasan:</b>\nAkun yang disebut tidak tersedia.",
                parse_mode=enums.ParseMode.HTML
            )
            await cb.answer("❌ Akun tidak tersedia", show_alert=True)
            return
        
        try:
            # Kirim balasan
            logger.info(f"📤 Sending message to {chat_id}...")
            await mentioned_client.send_message(
                chat_id,
                reply_text,
                reply_to_message_id=message_id
            )
            logger.info(f"✅ Reply sent successfully to {chat_id}")
            
            # Update status pesan
            client_name = mentioned_client.me.first_name if mentioned_client.me else "Unknown"
            await cb.message.edit_text(
                f"✅ <b>Balasan berhasil dikirim!</b>\n\n"
                f"• <b>Group:</b> <code>{chat_id}</code>\n"
                f"• <b>Send as:</b> {client_name}\n"
                f"• <b>Time:</b> {datetime.now().strftime('%H:%M:%S')}",
                parse_mode=enums.ParseMode.HTML
            )
            
            # Hapus pesan terkait
            messages_to_delete = []
            if user_msg_id and user_msg_id != cb.message.id:
                messages_to_delete.append(user_msg_id)
            if confirm_msg_id and confirm_msg_id != cb.message.id:
                messages_to_delete.append(confirm_msg_id)
            if instruction_msg_id:
                messages_to_delete.append(instruction_msg_id)
            
            if messages_to_delete:
                try:
                    await c.delete_messages(cb.message.chat.id, messages_to_delete)
                    logger.info(f"🗑️ Deleted {len(messages_to_delete)} related messages")
                except Exception as delete_err:
                    logger.warning(f"⚠️ Delete messages failed: {delete_err}")
            
            # Log untuk Reply From All
            if is_reply_all and cb.from_user:
                logger.info(f"✅ Reply From All successful - User: {cb.from_user.id}, Mention: {chat_id}_{message_id}")
            
        except Exception as send_err:
            logger.error(f"❌ Send reply failed: {send_err}")
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
        logger.error(f"❌ Confirm send error: {e}", exc_info=True)
        await cb.answer("❌ Terjadi kesalahan.", show_alert=True)

# 🔥 PERBAIKAN: Handler pembatalan
@Altruix.bot.on_callback_query(filters.regex(r"^mentions_cancel_"))
@log_errors
async def cancel_send_reply(c: Client, cb: CallbackQuery):
    """Membatalkan pengiriman balasan."""
    try:
        BUTTON_STATS["cancel"] += 1
        log_button_press("CANCEL", cb.data, cb.from_user.id if cb.from_user else None)
        logger.info(f"📊 Cancel button pressed. Total: {BUTTON_STATS['cancel']}")
        
        # Parse waiting_id
        pattern = r"mentions_cancel_(.+)"
        match = re.match(pattern, cb.data)
        
        if not match:
            logger.error(f"❌ Invalid cancel callback: {cb.data}")
            await cb.answer("❌ Invalid callback", show_alert=True)
            return
        
        waiting_id = match.group(1)
        logger.info(f"🔄 Cancel reply for waiting_id: {waiting_id}")
        
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
                    logger.info(f"🗑️ Deleted {len(messages_to_delete)} messages on cancel")
                except Exception as delete_err:
                    logger.warning(f"⚠️ Delete on cancel failed: {delete_err}")
            
            # Refund reply count untuk Reply From All
            if data.get("is_reply_all") and data.get("user_id"):
                today = datetime.now().strftime("%Y%m%d")
                if USER_REPLY_COUNTS[data["user_id"]][today] > 0:
                    USER_REPLY_COUNTS[data["user_id"]][today] -= 1
                    logger.info(f"↩️ Refunded reply count for user {data['user_id']}")
            
            REPLY_AS_MENTIONED_WAITING.pop(waiting_id, None)
            
            await cb.message.edit_text(
                "❌ <b>Pengiriman dibatalkan.</b>",
                parse_mode=enums.ParseMode.HTML
            )
            await cb.answer("❌ Dibatalkan.", show_alert=True)
        else:
            await cb.answer("❌ Tidak ada proses yang berjalan.", show_alert=True)
            
    except Exception as e:
        logger.error(f"❌ Cancel error: {e}", exc_info=True)
        await cb.answer("❌ Terjadi kesalahan.", show_alert=True)

# 🔥 Handler untuk reacted button
@Altruix.bot.on_callback_query(filters.regex(r"^mentions_reacted$"))
@log_errors
async def already_reacted_handler(c: Client, cb: CallbackQuery):
    """Handler untuk tombol yang sudah direaksi."""
    log_button_press("ALREADY_REACTED", cb.data, cb.from_user.id if cb.from_user else None)
    await cb.answer("✅ Sudah direaksi sebelumnya", show_alert=False)

# 🔥 Handler untuk tombol test (dari perintah /mentions_test atau /test_mention)
@Altruix.bot.on_callback_query(filters.regex(r"^test_mentions_"))
@log_errors
async def test_buttons_handler_bot(c: Client, cb: CallbackQuery):
    """Handler untuk tombol test dari bot."""
    try:
        pattern = r"test_mentions_(.+)_(-?\d+)_(\d+)"
        match = re.match(pattern, cb.data)
        
        if not match:
            await cb.answer("❌ Invalid test button", show_alert=True)
            return
        
        action = match.group(1)
        chat_id = int(match.group(2))
        message_id = int(match.group(3))
        
        if action == "reply":
            # Simulasikan tombol reply
            await start_reply_as_mentioned(c, cb)
        elif action == "replyall":
            # Simulasikan tombol reply all
            await start_reply_from_all(c, cb)
        elif action == "react":
            # Simulasikan tombol react
            fake_cb_data = f"mentions_react_{chat_id}_{message_id}_👍"
            cb.data = fake_cb_data
            await quick_reaction_handler(c, cb)
        else:
            await cb.answer(f"❌ Unknown test action: {action}", show_alert=True)
            
    except Exception as e:
        logger.error(f"❌ Test button handler failed: {e}")
        await cb.answer("❌ Test failed", show_alert=True)

# 🔥 Command untuk status
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
    today = datetime.now().strftime("%Y%m%d")
    total_users_today = sum(1 for counts in USER_REPLY_COUNTS.values() if counts.get(today, 0) > 0)
    total_replies_today = sum(counts.get(today, 0) for counts in USER_REPLY_COUNTS.values())
    
    status_msg = (
        f"📊 <b>Mention Plugin Status v{PLUGIN_VERSION}</b>\n\n"
        f"<b>Settings:</b>\n"
        f"• Mentions: {'✅ ENABLED' if user_setting else '❌ DISABLED'}\n"
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
        f"<b>Valid Emojis:</b> 👍 ❤️ 🔥 🥰 👏\n\n"
        f"<i>Last update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"
    )
    
    await safe_edit_message(
        c,
        m.chat.id,
        msg.id,
        status_msg,
        parse_mode=enums.ParseMode.HTML
    )

# 🔥 PERBAIKAN: Command untuk debug tombol
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
            r"^mentions_reacted$",
            r"^test_mentions_"
        ]
        
        # Cek state current
        debug_msg = (
            f"🔧 <b>Button Debug Report v{PLUGIN_VERSION}</b>\n\n"
            f"<b>Registered Patterns:</b>\n"
        )
        
        for i, pattern in enumerate(test_patterns, 1):
            debug_msg += f"{i}. <code>{pattern}</code>\n"
        
        debug_msg += f"\n<b>Current State:</b>\n"
        debug_msg += f"• LOG_CHAT: <code>{Altruix.log_chat}</code>\n"
        debug_msg += f"• Bot ID: <code>{Altruix.bot_info.id if Altruix.bot_info else 'None'}</code>\n"
        debug_msg += f"• Plugin: v{PLUGIN_VERSION}\n"
        debug_msg += f"• Log Level: {logger.level} ({logging.getLevelName(logger.level)})\n"
        debug_msg += f"• Cache Size: {len(MENTION_LOG_CACHE)}\n"
        debug_msg += f"• Waiting Size: {len(REPLY_AS_MENTIONED_WAITING)}\n\n"
        
        debug_msg += f"<b>Recent Cache Keys:</b>\n"
        cache_keys = list(MENTION_LOG_CACHE.keys())[:5]
        for i, key in enumerate(cache_keys, 1):
            cache_data = MENTION_LOG_CACHE[key]
            debug_msg += f"{i}. {key} (client: {cache_data.get('client_id', 'unknown')})\n"
        
        debug_msg += f"\n<b>Common Issues:</b>\n"
        debug_msg += f"1. REACTION_INVALID: Emoji tidak didukung Telegram\n"
        debug_msg += f"2. Tombol tidak merespon: Cek log untuk 'Button pressed'\n"
        debug_msg += f"3. Timeout errors: Network issue\n\n"
        
        debug_msg += f"<b>Test Commands:</b>\n"
        debug_msg += f"• <code>/mentions_test</code> - Test semua tombol\n"
        debug_msg += f"• <code>/mentions_status</code> - Status lengkap\n"
        debug_msg += f"• <code>/mentions_clear</code> - Clear cache\n\n"
        
        debug_msg += f"<i>Cek log file untuk detail error.</i>"
        
        await safe_edit_message(
            c,
            m.chat.id,
            msg.id,
            debug_msg,
            parse_mode=enums.ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"❌ Debug command failed: {e}")
        await msg.edit_msg(f"❌ Debug error: {str(e)[:100]}")

# 🔥 PERBAIKAN: Command untuk test tombol - DIPERBAIKI!
@Altruix.register_on_cmd(
    ["mentions_test"],
    cmd_help={
        "help": "Test button functionality",
        "example": "mentions_test",
    },
    group_only=False,
    requires_input=False,
)
@log_errors
async def test_buttons_command(c: Client, m: AltruixMessage):
    """Test semua tombol - HANYA BISA DIJALANKAN OLEH BOT!"""
    msg = await m.handle_message("PROCESSING")
    
    try:
        # Hanya bot yang bisa membuat tombol
        if c != Altruix.bot:
            await msg.edit_msg("❌ Perintah ini hanya bisa dijalankan oleh bot!")
            return
        
        # Buat tombol test dengan valid emojis
        test_chat_id = m.chat.id
        test_message_id = m.id
        
        # Tombol untuk test - menggunakan pola khusus untuk bot
        reaction_buttons = [
            InlineKeyboardButton(emoji, callback_data=f"test_mentions_react_{test_chat_id}_{test_message_id}")
            for emoji in DEFAULT_REACTION_EMOJIS[:3]  # Hanya 3 untuk test
        ]
        
        reply_button = [InlineKeyboardButton(
            "🗨️ Test Reply", 
            callback_data=f"test_mentions_reply_{test_chat_id}_{test_message_id}"
        )]
        
        reply_all_button = [InlineKeyboardButton(
            "👥 Test Reply All", 
            callback_data=f"test_mentions_replyall_{test_chat_id}_{test_message_id}"
        )]
        
        keyboard = [
            reaction_buttons,
            reply_button,
            reply_all_button,
        ]
        
        test_msg = (
            f"🔧 <b>Button Test Panel v{PLUGIN_VERSION}</b>\n\n"
            f"<b>Test semua tombol:</b>\n"
            f"1. Reaction buttons (👍, ❤️, 🔥)\n"
            f"2. Reply as Mentioned\n"
            f"3. Reply From All\n\n"
            f"<b>Status:</b>\n"
            f"• Plugin: v{PLUGIN_VERSION}\n"
            f"• Cache: {len(MENTION_LOG_CACHE)} entries\n"
            f"• Bot: {c.me.first_name if c.me else 'Unknown'}\n\n"
            f"<i>Tekan tombol di bawah untuk testing.</i>\n"
            f"<i>Cek log untuk debugging.</i>"
        )
        
        test_message = await c.send_message(
            m.chat.id,
            test_msg,
            parse_mode=enums.ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        await msg.delete()
        
        # Tambahkan ke cache untuk testing
        test_key = f"{test_chat_id}_{test_message_id}"
        MENTION_LOG_CACHE[test_key] = {
            "text": "Test message",
            "log_msg_id": test_message.id,
            "client_id": c.me.id,  # Bot client ID
            "chat_id": test_chat_id,
            "message_id": test_message_id,
            "timestamp_int": int(time.time()),
            "mentioned_by": m.from_user.id if m.from_user else 0,
            "group_name": m.chat.title if m.chat else "Test",
            "client_name": c.me.first_name if c.me else "Bot"
        }
        
        logger.info(f"✅ Test panel created with message ID: {test_message.id}")
        
    except Exception as e:
        logger.error(f"❌ Test command failed: {e}")
        await msg.edit_msg(f"❌ Test error: {str(e)[:100]}")

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
        logger.error(f"❌ Clear cache failed: {e}")
        await msg.edit_msg(f"❌ Clear error: {str(e)[:100]}")

# 🔥 BARU: Command untuk test mention system - DIPERBAKI
@Altruix.register_on_cmd(
    ["test_mention"],
    cmd_help={"help": "Test mention system", "example": "test_mention"},
)
@log_errors
async def test_mention_system(c: Client, m: AltruixMessage):
    """Test mention system."""
    msg = await m.handle_message("PROCESSING")
    
    try:
        # Hanya bot yang bisa membuat tombol
        if c != Altruix.bot:
            await msg.edit_msg("❌ Perintah ini hanya bisa dijalankan oleh bot!")
            return
        
        # Buat tombol test
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🗨️ Test Reply", callback_data=f"test_mentions_reply_{m.chat.id}_{m.id}")],
            [InlineKeyboardButton("👥 Test Reply All", callback_data=f"test_mentions_replyall_{m.chat.id}_{m.id}")],
            [InlineKeyboardButton("👍 Test React", callback_data=f"test_mentions_react_{m.chat.id}_{m.id}")],
        ])
        
        await safe_edit_message(
            c,
            m.chat.id,
            msg.id,
            "🔧 **Test Mention System**\n\nTekan tombol di bawah untuk testing:",
            reply_markup=keyboard,
            parse_mode=enums.ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"❌ Test mention failed: {e}")
        await msg.edit_msg(f"❌ Test error: {str(e)[:100]}")

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
                
            if expired_cache or expired_waiting:
                logger.info(f"🧹 Cleaned {len(expired_cache)} cache and {len(expired_waiting)} waiting entries")
                
        except Exception as e:
            logger.error(f"❌ Cleanup error: {e}")
        
        await asyncio.sleep(600)

# Start cleanup task
asyncio.create_task(cleanup_old_entries())
logger.info("Cleanup task started")

# 🔥 BARU: Debug command untuk melihat struktur Altruix
@Altruix.register_on_cmd(
    ["mentions_debug_structure"],
    cmd_help={
        "help": "Debug Altruix structure",
        "example": "mentions_debug_structure",
    },
    group_only=False,
    requires_input=False,
)
@log_errors
async def debug_structure_handler(c: Client, m: AltruixMessage):
    """Debug Altruix structure untuk menemukan client."""
    msg = await m.handle_message("PROCESSING")
    
    try:
        debug_info = f"🔍 <b>Altruix Structure Debug v{PLUGIN_VERSION}</b>\n\n"
        
        # Cek atribut yang ada
        debug_info += "<b>Available Attributes:</b>\n"
        
        attrs = []
        for attr_name in dir(Altruix):
            if not attr_name.startswith('_'):
                attrs.append(attr_name)
        
        debug_info += f"• Total attributes: {len(attrs)}\n"
        debug_info += f"• First 20: {', '.join(attrs[:20])}\n\n"
        
        # Cek spesifik atribut
        debug_info += "<b>Specific Attributes:</b>\n"
        
        if hasattr(Altruix, 'bot'):
            debug_info += f"• bot: {type(Altruix.bot)} "
            if Altruix.bot and hasattr(Altruix.bot, 'me'):
                debug_info += f"(ID: {Altruix.bot.me.id}, Name: {Altruix.bot.me.first_name})\n"
            else:
                debug_info += "(no me attribute)\n"
        else:
            debug_info += "• bot: NOT FOUND\n"
        
        if hasattr(Altruix, 'userbot_clients'):
            debug_info += f"• userbot_clients: {type(Altruix.userbot_clients)} "
            if Altruix.userbot_clients:
                debug_info += f"(length: {len(Altruix.userbot_clients)})\n"
                # Tampilkan 3 pertama
                for i, ub in enumerate(Altruix.userbot_clients[:3]):
                    try:
                        if ub and hasattr(ub, 'me') and ub.me:
                            debug_info += f"  {i}. {ub.me.first_name} (ID: {ub.me.id})\n"
                        else:
                            debug_info += f"  {i}. Invalid or no me attribute\n"
                    except:
                        debug_info += f"  {i}. Error accessing\n"
            else:
                debug_info += "(empty)\n"
        else:
            debug_info += "• userbot_clients: NOT FOUND\n"
        
        if hasattr(Altruix, 'ubot'):
            debug_info += f"• ubot: {type(Altruix.ubot)} "
            if Altruix.ubot and hasattr(Altruix.ubot, 'me'):
                debug_info += f"(ID: {Altruix.ubot.me.id}, Name: {Altruix.ubot.me.first_name})\n"
            else:
                debug_info += "(no me attribute)\n"
        else:
            debug_info += "• ubot: NOT FOUND\n"
        
        if hasattr(Altruix, 'clients'):
            debug_info += f"• clients: {type(Altruix.clients)} "
            if Altruix.clients:
                if isinstance(Altruix.clients, dict):
                    debug_info += f"(dict, keys: {len(Altruix.clients)})\n"
                    # Tampilkan 3 keys pertama
                    for i, key in enumerate(list(Altruix.clients.keys())[:3]):
                        debug_info += f"  {i}. key: {key}\n"
                elif isinstance(Altruix.clients, list):
                    debug_info += f"(list, length: {len(Altruix.clients)})\n"
            else:
                debug_info += "(empty)\n"
        else:
            debug_info += "• clients: NOT FOUND\n"
        
        debug_info += f"\n<b>Current Client:</b>\n"
        debug_info += f"• ID: {c.me.id if c.me else 'N/A'}\n"
        debug_info += f"• Name: {c.me.first_name if c.me else 'N/A'}\n"
        debug_info += f"• Type: {type(c)}\n"
        
        debug_info += f"\n<b>Cache Info:</b>\n"
        debug_info += f"• MENTION_LOG_CACHE: {len(MENTION_LOG_CACHE)} entries\n"
        debug_info += f"• REPLY_AS_MENTIONED_WAITING: {len(REPLY_AS_MENTIONED_WAITING)} entries\n"
        
        await safe_edit_message(
            c,
            m.chat.id,
            msg.id,
            debug_info,
            parse_mode=enums.ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"❌ Debug structure failed: {e}")
        await msg.edit_msg(f"❌ Debug error: {str(e)[:100]}")

# Log sukses loading
try:
    Altruix.log(f"[DEBUG] ✅ Loaded → {__plugin_name__} {PLUGIN_VERSION}", level=20)
except Exception as e:
    logger.info(f"[DEBUG] ✅ Loaded → {__plugin_name__} {PLUGIN_VERSION}")

# logger.info(f"📋 All issues fixed:")
# logger.info(f"  1. Enhanced get_mention_client() with detailed logging")
# logger.info(f"  2. Added cache data logging in reply handlers")
# logger.info(f"  3. Added debug structure command (/mentions_debug_structure)")
# logger.info(f"  4. Improved error handling and logging")
# logger.info(f"🔧 Use /mentions_debug_structure to see Altruix structure")
# logger.info(f"🔧 Use /mentions_test (via bot) to test all buttons")
# logger.info(f"🔧 Use /test_mention (via bot) for quick testing")
# logger.info(f"⚠️  Note: Userbots cannot send inline buttons, only bot can!")
