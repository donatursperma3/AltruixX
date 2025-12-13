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
from datetime import datetime
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
from typing import Optional, Union

plugin_name = f"plugins/userbot/{os.path.basename(__file__)}"
__plugin_name__ = plugin_name if plugin_name else "mentions"
PLUGIN_VERSION = "0.1.4.0"  # 🔥 PERBAIKAN: Versi dengan fix semua error
logger = logging.getLogger(f"{__plugin_name__}")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - [SET PLUGIN] - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# 🔥 PERBAIKAN: Helper functions dengan timeout handling
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
    except Exception:
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
        logger.warning(f"[MENTIONS] Timeout sending message to {chat_id}")
        return None
    except Exception as e:
        logger.error(f"[MENTIONS] Send message failed: {e}")
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
        logger.warning(f"[MENTIONS] Timeout editing message {message_id}")
        return False
    except Exception as e:
        logger.error(f"[MENTIONS] Edit message failed: {e}")
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
AUTO_REPLY_ENABLED = False  # Default: OFF

# 🔥 PERBAIKAN: Flag untuk track database status
DATABASE_CORRUPTION_DETECTED = False

# 🔥 PERBAIKAN: Cache untuk userbot clients untuk menghindari timeout
USERBOT_CLIENTS = {}

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
                    logger.info(f"[MENTIONS] Loaded {len(MENTIONS_DATA)} settings, auto_reply: {AUTO_REPLY_ENABLED}")
                else:
                    MENTIONS_DATA = {}
                    AUTO_REPLY_ENABLED = False
        else:
            MENTIONS_DATA = {}
            AUTO_REPLY_ENABLED = False
            logger.info("[MENTIONS] Local storage file not found, creating new")
    except Exception as e:
        logger.error(f"[MENTIONS] Failed to load local storage: {e}")
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
            "version": PLUGIN_VERSION
        }
        async with aiofiles.open(LOCAL_STORAGE_FILE, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, indent=2, ensure_ascii=False))
        logger.debug(f"[MENTIONS] Saved {len(MENTIONS_DATA)} settings to local storage")
    except Exception as e:
        logger.error(f"[MENTIONS] Failed to save local storage: {e}")

async def backup_to_telegram(userbot_client: Client):
    """Upload backup ke Telegram menggunakan USERBOT, bukan bot."""
    try:
        if not LOCAL_STORAGE_FILE.exists() or LOCAL_STORAGE_FILE.stat().st_size == 0:
            logger.warning("[MENTIONS] No data to backup")
            return False
        
        # 🔥 PERBAIKAN: Gunakan userbot client, bukan bot
        try:
            await userbot_client.send_document(
                "me",  # Kirim ke saved messages userbot
                str(LOCAL_STORAGE_FILE),
                caption=(
                    f"📂 **Mention Settings Backup**\n\n"
                    f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"📊 Settings: {len(MENTIONS_DATA)}\n"
                    f"🔔 Auto-Reply: {'✅ ON' if AUTO_REPLY_ENABLED else '❌ OFF'}\n"
                    f"🔄 Version: {PLUGIN_VERSION}"
                )
            )
            logger.info("[MENTIONS] Backup sent to userbot saved messages")
            return True
        except Exception as userbot_err:
            logger.error(f"[MENTIONS] Userbot backup failed: {userbot_err}")
            
            # Fallback: Coba simpan ke LOG_CHAT jika userbot gagal
            try:
                backup_text = (
                    f"📂 **Mention Settings Backup**\n\n"
                    f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"📊 Settings: {len(MENTIONS_DATA)}\n"
                    f"🔔 Auto-Reply: {'✅ ON' if AUTO_REPLY_ENABLED else '❌ OFF'}\n\n"
                    f"*Local file:* `{LOCAL_STORAGE_FILE.name}`"
                )
                
                await safe_send_message(
                    Altruix.bot,
                    Altruix.log_chat,
                    backup_text,
                    parse_mode=enums.ParseMode.MARKDOWN
                )
                logger.info("[MENTIONS] Backup info sent to LOG_CHAT")
                return True
            except Exception as bot_err:
                logger.error(f"[MENTIONS] Bot backup also failed: {bot_err}")
                return False
                
    except Exception as e:
        logger.error(f"[MENTIONS] Backup failed: {e}")
        return False

async def get_mention_setting_safe(client_id: int, client_name: str = "Unknown") -> bool:
    """Safe method untuk membaca setting."""
    # Cek local storage dulu
    client_id_str = str(client_id)
    if client_id_str in MENTIONS_DATA:
        setting_data = MENTIONS_DATA[client_id_str]
        if isinstance(setting_data, dict) and "value" in setting_data:
            return bool(setting_data["value"])
        else:
            return bool(setting_data) if isinstance(setting_data, (bool, int)) else False
    
    # Cek config cache
    if hasattr(Altruix.config, "mention_settings") and client_id in Altruix.config.mention_settings:
        value = bool(Altruix.config.mention_settings[client_id])
        
        # Simpan ke local storage
        MENTIONS_DATA[client_id_str] = {
            "value": value,
            "source": "config_cache",
            "timestamp_int": int(time.time()),
            "client_name": client_name
        }
        await save_local_storage()
        
        return value
    
    # Default value
    default_value = False
    MENTIONS_DATA[client_id_str] = {
        "value": default_value,
        "source": "default",
        "timestamp_int": int(time.time()),
        "client_name": client_name
    }
    await save_local_storage()
    
    return default_value

async def save_mention_setting(client_id: int, value: bool, client_name: str = "Unknown") -> bool:
    """Safe method untuk menyimpan setting."""
    client_id_str = str(client_id)
    bool_value = bool(value)
    
    # Simpan ke local storage
    MENTIONS_DATA[client_id_str] = {
        "value": bool_value,
        "source": "manual_save",
        "timestamp_int": int(time.time()),
        "client_name": client_name,
        "saved_at_int": int(time.time())
    }
    await save_local_storage()
    
    # Simpan ke config cache
    if not hasattr(Altruix.config, "mention_settings"):
        Altruix.config.mention_settings = {}
    Altruix.config.mention_settings[client_id] = bool_value
    
    logger.info(f"[MENTIONS] Saved setting for {client_id}: {bool_value}")
    return True

async def get_userbot_client(client_id: int) -> Optional[Client]:
    """Get userbot client dari cache atau cari."""
    if client_id in USERBOT_CLIENTS:
        return USERBOT_CLIENTS[client_id]
    return None

# 🔥 Load local storage saat plugin start
asyncio.create_task(load_local_storage())

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
    elif user_input in ["off", "no"]:
        value = False
        status_text = "DISABLED"
    else:
        return await msg.edit_msg("INVALID_INPUT")
    
    try:
        client_id = c.me.id
        client_name = c.me.first_name or c.me.username or "Unknown"
        
        await save_mention_setting(client_id, value, client_name)
        
        # Simpan client ke cache
        USERBOT_CLIENTS[client_id] = c
        
        status_msg = (
            f"✅ **Mention notifications {status_text}**\n\n"
            f"• **Client:** {client_name} (ID: `{client_id}`)\n"
            f"• **Auto-Reply:** {'✅ ON' if AUTO_REPLY_ENABLED else '❌ OFF'}\n"
            f"• **Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"Use `/autoreply on` to enable auto-reply"
        )
        
        await safe_edit_message(
            c,
            m.chat.id,
            msg.id,
            status_msg,
            parse_mode=enums.ParseMode.MARKDOWN
        )
        
    except Exception as e:
        error_detail = str(e)
        Altruix.log(f"[ERROR] Save failed: {error_detail}", level=40)
        await msg.edit_msg(f"❌ Save error: {error_detail[:100]}")

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
        
        status_msg = (
            f"{emoji} **Auto-Reply {status_text}**\n\n"
            f"• **Status:** {status_text}\n"
            f"• **Client:** {c.me.first_name} (ID: `{c.me.id}`)\n"
            f"• **Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )
        
        if AUTO_REPLY_ENABLED:
            status_msg += "Bot akan membalas otomatis saat Anda disebut di grup."
        else:
            status_msg += "Bot tidak akan membalas otomatis saat Anda disebut."
        
        await safe_edit_message(
            c,
            m.chat.id,
            msg.id,
            status_msg,
            parse_mode=enums.ParseMode.MARKDOWN
        )
        
    except Exception as e:
        error_detail = str(e)
        Altruix.log(f"[ERROR] Auto-reply save failed: {error_detail}", level=40)
        await msg.edit_msg(f"❌ Auto-reply error: {error_detail[:100]}")

@Altruix.on_message(
    filters.mentioned & filters.group & ~filters.user(Altruix.bot_info.id)
)
@log_errors
async def send_mention_log_handler(c: Client, m: RawMessage):
    """Handler utama untuk menangkap mention dan mengirim notifikasi ke LOG_CHAT."""
    try:
        client_id = c.me.id
        client_name = c.me.first_name or c.me.username or "Unknown"
        
        # Simpan client ke cache
        USERBOT_CLIENTS[client_id] = c
        
        # Cek apakah mention notifications enabled
        is_enabled = await get_mention_setting_safe(client_id, client_name)
        
        if not is_enabled:
            logger.debug(f"[MENTIONS] Disabled for {client_id}")
            return

        logger.info(f"[MENTIONS] Processing mention for {client_name} ({client_id})")
        
        # Persiapan data mention
        mentioner = m.from_user
        if not mentioner:
            return

        mentioner_name = mentioner.first_name or "Unknown"
        mentioner_id = mentioner.id
        mentioner_link = f"tg://user?id={mentioner_id}"
        mentioner_hyperlink = f'<a href="{mentioner_link}">{html.escape(mentioner_name)}</a>'
        
        # Handle m.date dengan timeout protection
        try:
            if hasattr(m, 'date'):
                date_value = m.date
                if isinstance(date_value, datetime):
                    mention_datetime = date_value
                elif isinstance(date_value, (int, float)):
                    mention_datetime = datetime.fromtimestamp(float(date_value))
                else:
                    mention_datetime = datetime.now()
            else:
                mention_datetime = datetime.now()
            
            mention_time = mention_datetime.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as date_err:
            logger.warning(f"[MENTIONS] Date error: {date_err}")
            mention_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Handle message text
        message_text = m.text or m.caption or "[No text content]"
        if message_text:
            message_text = html.escape(str(message_text))[:1000]
        
        # Deteksi media
        media_info = ""
        if m.media:
            if m.audio: media_info = "🎵 Audio"
            elif m.video: media_info = "🎬 Video" 
            elif m.photo: media_info = "🖼️ Photo"
            elif m.sticker: media_info = "🤡 Sticker"
            elif m.voice: media_info = "🎤 Voice"
            elif m.document: media_info = "📎 Document"
            if media_info:
                message_text = f"{media_info}: {message_text}"
        
        # Handle edit detection
        is_edited_message = False
        edit_info = ""
        
        if hasattr(m, 'edit_date'):
            edit_date_val = m.edit_date
            if edit_date_val is not None:
                is_edited_message = True
                try:
                    if isinstance(edit_date_val, datetime):
                        edit_time_str = edit_date_val.strftime("%Y-%m-%d %H:%M:%S")
                    elif isinstance(edit_date_val, (int, float)):
                        edit_time_str = datetime.fromtimestamp(float(edit_date_val)).strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        edit_time_str = "Unknown"
                    
                    edit_info = f"✏️ <b>Edited Time:</b> <code>{edit_time_str}</code>\n"
                except Exception as edit_err:
                    logger.warning(f"[MENTIONS] Edit time error: {edit_err}")
        
        # Bangun pesan notifikasi
        if is_edited_message:
            title = "✏️ Edited Mention Detected!"
        else:
            title = "🔔 Mention Detected!"
        
        log_message = (
            f"{title}\n\n"
            f"👤 <b>Mentioned By:</b> {mentioner_hyperlink} (<code>{mentioner_id}</code>)\n"
            f"📛 <b>Username:</b> @{mentioner.username if mentioner.username else 'N/A'}\n"
            f"🤖 <b>My Account:</b> {c.me.mention(style=enums.ParseMode.HTML)}\n"
            f"💬 <b>Group:</b> {html.escape(m.chat.title)} (<code>{m.chat.id}</code>)\n"
            f"🕒 <b>Time:</b> <code>{mention_time}</code>\n"
            f"{edit_info}"
            f"📄 <b>Message:</b>\n<blockquote>{message_text}</blockquote>\n\n"
            f"⚡ <b>Auto-Reply:</b> {'✅ ON' if AUTO_REPLY_ENABLED else '❌ OFF'}"
        )
        
        # Tombol dengan callback data yang benar
        reaction_buttons = [
            InlineKeyboardButton(emoji, callback_data=f"mentions_react_{m.chat.id}_{m.id}_{emoji}")
            for emoji in DEFAULT_REACTION_EMOJIS
        ]
        reply_button = [InlineKeyboardButton("🗨️ Reply as Mentioned", callback_data=f"mentions_reply_{m.chat.id}_{m.id}")]
        link_button = [InlineKeyboardButton("🔗 Go to Message", url=m.link)]
        
        msg_key = f"{m.chat.id}_{m.id}"
        
        # Cek cache untuk edit dengan timeout
        if is_edited_message and msg_key in MENTION_LOG_CACHE:
            try:
                old_data = MENTION_LOG_CACHE[msg_key]
                await asyncio.wait_for(
                    Altruix.bot.edit_message_text(
                        chat_id=Altruix.log_chat,
                        message_id=old_data["log_msg_id"],
                        text=log_message,
                        parse_mode=enums.ParseMode.HTML,
                        disable_web_page_preview=True,
                        reply_markup=InlineKeyboardMarkup([reaction_buttons, reply_button, link_button])
                    ),
                    timeout=15
                )
                MENTION_LOG_CACHE[msg_key]["text"] = message_text
                return
            except asyncio.TimeoutError:
                logger.warning(f"[MENTIONS] Timeout editing message {msg_key}")
            except Exception as edit_err:
                logger.warning(f"[MENTIONS] Edit failed: {edit_err}")
        
        # Kirim notifikasi baru dengan timeout protection
        try:
            sent_log_msg = await asyncio.wait_for(
                Altruix.bot.send_message(
                    Altruix.log_chat,
                    log_message,
                    parse_mode=enums.ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=InlineKeyboardMarkup([reaction_buttons, reply_button, link_button])
                ),
                timeout=30
            )
            logger.info(f"[MENTIONS] Sent notification for {msg_key}")
        except asyncio.TimeoutError:
            logger.error(f"[MENTIONS] Timeout sending notification for {msg_key}")
            return
        except Exception as send_err:
            logger.error(f"[MENTIONS] Send failed: {send_err}")
            return
        
        # 🔥 PERBAIKAN: Auto-reply hanya jika enabled dan bukan pesan edit
        if AUTO_REPLY_ENABLED and not is_edited_message:
            try:
                await asyncio.wait_for(
                    c.send_message(
                        Altruix.log_chat,
                        "💬 Saya yang disebut di atas.",
                        reply_parameters=ReplyParameters(
                            message_id=sent_log_msg.id,
                            chat_id=Altruix.log_chat
                        )
                    ),
                    timeout=15
                )
                logger.debug(f"[MENTIONS] Auto-reply sent for {msg_key}")
            except asyncio.TimeoutError:
                logger.warning(f"[MENTIONS] Timeout sending auto-reply for {msg_key}")
            except Exception as reply_err:
                logger.warning(f"[MENTIONS] Auto-reply failed: {reply_err}")
        
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
            except Exception as cache_err:
                logger.warning(f"[MENTIONS] Cache cleanup failed: {cache_err}")
            
    except Exception as e:
        error_msg = str(e)
        Altruix.log(f"[CRITICAL] Error in mention handler: {error_msg}", level=50)
        logger.error(f"[MENTIONS] Handler error: {error_msg}")

# 🔥 PERBAIKAN: Handler untuk quick reaction dengan timeout
@Altruix.bot.on_callback_query(filters.regex(r"^mentions_react_(\d+)_(\d+)_(.+)$"))
@log_errors
async def quick_reaction_handler(c: Client, cb: CallbackQuery):
    """Kirim reaksi ke pesan asli di grup."""
    try:
        logger.info(f"[MENTIONS] Quick reaction callback: {cb.data}")
        
        # Parse callback data
        parts = cb.data.split("_")
        if len(parts) < 5:
            await cb.answer("❌ Invalid callback data", show_alert=True)
            return
        
        chat_id = int(parts[2])
        message_id = int(parts[3])
        emoji = parts[4]
        
        msg_key = f"{chat_id}_{message_id}"
        logger.info(f"[MENTIONS] Processing reaction for {msg_key} with {emoji}")
        
        if msg_key not in MENTION_LOG_CACHE:
            logger.warning(f"[MENTIONS] Mention not in cache: {msg_key}")
            await cb.answer("❌ Mention tidak ditemukan di cache.", show_alert=True)
            return
        
        userbot_client = MENTION_LOG_CACHE[msg_key]["mentioned_client"]
        if not userbot_client:
            logger.warning(f"[MENTIONS] Userbot client not available: {msg_key}")
            await cb.answer("❌ Akun yang disebut tidak tersedia.", show_alert=True)
            return
        
        try:
            # Kirim reaction dengan timeout
            await asyncio.wait_for(
                userbot_client.send_reaction(chat_id, message_id, emoji),
                timeout=15
            )
            logger.info(f"[MENTIONS] Reaction sent: {emoji} to {msg_key}")
            
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
                    
                    await cb.message.edit_reply_markup(
                        InlineKeyboardMarkup(new_buttons)
                    )
            except Exception as edit_err:
                logger.warning(f"[MENTIONS] Could not update button: {edit_err}")
            
            await cb.answer(f"✅ Bereaksi dengan {emoji}", show_alert=False)
            
        except asyncio.TimeoutError:
            logger.error(f"[MENTIONS] Timeout sending reaction to {msg_key}")
            await cb.answer("❌ Timeout: Gagal mengirim reaksi", show_alert=True)
        except Exception as react_err:
            logger.error(f"[MENTIONS] Reaction failed: {react_err}")
            await cb.answer(f"❌ Gagal: {str(react_err)[:50]}", show_alert=True)
            
    except Exception as e:
        logger.error(f"[MENTIONS] Quick reaction error: {e}", exc_info=True)
        await cb.answer("❌ Terjadi kesalahan.", show_alert=True)

# 🔥 PERBAIKAN: Handler untuk reply as mentioned
@Altruix.bot.on_callback_query(filters.regex(r"^mentions_reply_(\d+)_(\d+)$"))
@log_errors
async def start_reply_as_mentioned(c: Client, cb: CallbackQuery):
    """Memulai proses reply-as-mentioned."""
    try:
        logger.info(f"[MENTIONS] Reply callback: {cb.data}")
        
        # Parse callback data
        parts = cb.data.split("_")
        if len(parts) < 4:
            await cb.answer("❌ Invalid callback data", show_alert=True)
            return
        
        chat_id = int(parts[2])
        message_id = int(parts[3])
        msg_key = f"{chat_id}_{message_id}"
        
        logger.info(f"[MENTIONS] Starting reply process for {msg_key}")
        
        if msg_key not in MENTION_LOG_CACHE:
            logger.warning(f"[MENTIONS] Mention not in cache: {msg_key}")
            await cb.answer("❌ Mention tidak ditemukan di cache.", show_alert=True)
            return
        
        mentioned_client = MENTION_LOG_CACHE[msg_key]["mentioned_client"]
        if not mentioned_client:
            logger.warning(f"[MENTIONS] Userbot client not available: {msg_key}")
            await cb.answer("❌ Akun yang disebut tidak tersedia.", show_alert=True)
            return
        
        # Simpan status menunggu input
        REPLY_AS_MENTIONED_WAITING[cb.message.id] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "mentioned_client": mentioned_client,
            "log_msg_id": cb.message.id,
            "user_id": cb.from_user.id if cb.from_user else None,
            "timestamp_int": int(time.time()),
            "callback_message_id": cb.message.id
        }
        
        logger.info(f"[MENTIONS] Waiting for reply input for {msg_key}")
        
        # Kirim instruksi dengan timeout
        try:
            instruction_msg = await asyncio.wait_for(
                cb.message.reply_text(
                    "🗨️ <b>Reply as Mentioned</b>\n\n"
                    "Silakan ketik pesan balasan Anda di bawah ini.\n"
                    "Pesan akan dikirim sebagai akun yang disebut di grup asal.\n\n"
                    "<i>Balas pesan ini dengan teks yang ingin dikirim.</i>",
                    reply_parameters=ReplyParameters(
                        message_id=cb.message.id,
                        chat_id=cb.message.chat.id
                    ),
                    parse_mode=enums.ParseMode.HTML
                ),
                timeout=15
            )
            
            # Simpan ID pesan instruksi
            REPLY_AS_MENTIONED_WAITING[cb.message.id]["instruction_msg_id"] = instruction_msg.id
            
        except asyncio.TimeoutError:
            logger.error(f"[MENTIONS] Timeout sending instruction for {msg_key}")
            await cb.answer("❌ Timeout: Gagal mengirim instruksi", show_alert=True)
            return
        
        await cb.answer("✅ Silakan ketik balasan Anda.", show_alert=False)
        
    except Exception as e:
        logger.error(f"[MENTIONS] Reply start error: {e}", exc_info=True)
        await cb.answer("❌ Terjadi kesalahan.", show_alert=True)

# 🔥 PERBAIKAN: Handler untuk menerima input balasan
@Altruix.bot.on_message(filters.chat(Altruix.log_chat) & filters.reply)
@log_errors
async def handle_reply_as_mentioned_input(c: Client, m: RawMessage):
    """Menangani input balasan untuk reply-as-mentioned."""
    try:
        if not m.reply_to_message:
            return
        
        reply_msg_id = m.reply_to_message.id
        logger.info(f"[MENTIONS] Checking reply input for message {reply_msg_id}")
        
        # Cek apakah ini reply ke instruction message
        for waiting_id, data in list(REPLY_AS_MENTIONED_WAITING.items()):
            if data.get("instruction_msg_id") == reply_msg_id:
                reply_msg_id = waiting_id
                break
            elif data.get("callback_message_id") == reply_msg_id:
                # Ini reply langsung ke callback message
                break
        else:
            # Tidak ditemukan
            return
        
        if reply_msg_id not in REPLY_AS_MENTIONED_WAITING:
            return
        
        data = REPLY_AS_MENTIONED_WAITING[reply_msg_id]
        chat_id = data["chat_id"]
        message_id = data["message_id"]
        mentioned_client = data["mentioned_client"]
        
        reply_text = m.text or m.caption or ""
        if not reply_text.strip():
            await safe_send_message(
                c,
                m.chat.id,
                "❌ <b>Pesan kosong</b>\n\nSilakan ketik pesan yang ingin dikirim.",
                reply_to_message_id=m.id,
                parse_mode=enums.ParseMode.HTML
            )
            return
        
        logger.info(f"[MENTIONS] Reply input received for {chat_id}_{message_id}")
        
        # Kirim pesan konfirmasi
        confirm_buttons = [
            [InlineKeyboardButton("✅ Yes, Send", callback_data=f"mentions_confirm_{reply_msg_id}")],
            [InlineKeyboardButton("❌ No, Cancel", callback_data=f"mentions_cancel_{reply_msg_id}")]
        ]
        
        confirm_msg = (
            f"⚠️ <b>Konfirmasi Kirim Balasan</b>\n\n"
            f"<b>Pesan:</b>\n<blockquote>{html.escape(reply_text[:500])}</blockquote>\n\n"
            f"<b>Detail:</b>\n"
            f"• <b>Group:</b> <code>{chat_id}</code>\n"
            f"• <b>To Message:</b> <code>{message_id}</code>\n"
            f"• <b>Send as:</b> {mentioned_client.me.first_name if mentioned_client.me else 'Unknown'}\n\n"
            f"Apakah Anda yakin?"
        )
        
        try:
            confirm_message = await asyncio.wait_for(
                m.reply_text(
                    confirm_msg,
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(confirm_buttons),
                    reply_parameters=ReplyParameters(
                        message_id=m.id,
                        chat_id=m.chat.id
                    )
                ),
                timeout=15
            )
            
            # Simpan data
            REPLY_AS_MENTIONED_WAITING[reply_msg_id]["reply_text"] = reply_text
            REPLY_AS_MENTIONED_WAITING[reply_msg_id]["user_msg_id"] = m.id
            REPLY_AS_MENTIONED_WAITING[reply_msg_id]["confirm_msg_id"] = confirm_message.id
            
        except asyncio.TimeoutError:
            logger.error(f"[MENTIONS] Timeout sending confirmation for {reply_msg_id}")
            await safe_send_message(
                c,
                m.chat.id,
                "❌ Timeout: Gagal mengirim konfirmasi",
                reply_to_message_id=m.id
            )
        
    except Exception as e:
        logger.error(f"[MENTIONS] Reply input error: {e}", exc_info=True)

# 🔥 PERBAIKAN: Handler konfirmasi kirim dengan timeout
@Altruix.bot.on_callback_query(filters.regex(r"^mentions_confirm_(\d+)$"))
@log_errors
async def confirm_send_reply(c: Client, cb: CallbackQuery):
    """Mengirim balasan setelah konfirmasi."""
    try:
        reply_msg_id = int(cb.data.split("_")[2])
        logger.info(f"[MENTIONS] Confirm send for {reply_msg_id}")
        
        if reply_msg_id not in REPLY_AS_MENTIONED_WAITING:
            logger.warning(f"[MENTIONS] Reply data not found: {reply_msg_id}")
            await cb.answer("❌ Data tidak ditemukan.", show_alert=True)
            return
        
        data = REPLY_AS_MENTIONED_WAITING[reply_msg_id]
        chat_id = data["chat_id"]
        message_id = data["message_id"]
        mentioned_client = data["mentioned_client"]
        reply_text = data["reply_text"]
        user_msg_id = data.get("user_msg_id")
        confirm_msg_id = data.get("confirm_msg_id")
        
        logger.info(f"[MENTIONS] Sending reply to {chat_id}_{message_id}")
        
        try:
            # Kirim balasan dengan timeout
            await asyncio.wait_for(
                mentioned_client.send_message(
                    chat_id,
                    reply_text,
                    reply_to_message_id=message_id
                ),
                timeout=30
            )
            logger.info(f"[MENTIONS] Reply sent successfully")
            
            # Update status
            await safe_edit_message(
                c,
                cb.message.chat.id,
                cb.message.id,
                "✅ <b>Balasan berhasil dikirim!</b>\n\n"
                f"• <b>Group:</b> <code>{chat_id}</code>\n"
                f"• <b>To Message:</b> <code>{message_id}</code>\n"
                f"• <b>Time:</b> {datetime.now().strftime('%H:%M:%S')}",
                parse_mode=enums.ParseMode.HTML
            )
            
            # Hapus pesan terkait
            messages_to_delete = []
            if user_msg_id:
                messages_to_delete.append(user_msg_id)
            if confirm_msg_id:
                messages_to_delete.append(confirm_msg_id)
            
            instruction_msg_id = data.get("instruction_msg_id")
            if instruction_msg_id:
                messages_to_delete.append(instruction_msg_id)
            
            if messages_to_delete:
                try:
                    await asyncio.wait_for(
                        Altruix.bot.delete_messages(cb.message.chat.id, messages_to_delete),
                        timeout=10
                    )
                except Exception as delete_err:
                    logger.warning(f"[MENTIONS] Delete messages failed: {delete_err}")
            
        except asyncio.TimeoutError:
            logger.error(f"[MENTIONS] Timeout sending reply to {chat_id}")
            await cb.message.edit_text(
                "❌ <b>Timeout: Gagal mengirim balasan</b>\n\n"
                "Silakan coba lagi nanti.",
                parse_mode=enums.ParseMode.HTML
            )
            await cb.answer("❌ Timeout: Gagal mengirim", show_alert=True)
            return
        except Exception as send_err:
            logger.error(f"[MENTIONS] Send reply failed: {send_err}")
            await cb.message.edit_text(
                f"❌ <b>Gagal mengirim balasan:</b>\n<code>{html.escape(str(send_err)[:200])}</code>",
                parse_mode=enums.ParseMode.HTML
            )
            await cb.answer("❌ Gagal mengirim.", show_alert=True)
            return
        
        # Bersihkan waiting list
        REPLY_AS_MENTIONED_WAITING.pop(reply_msg_id, None)
        await cb.answer("✅ Balasan terkirim!", show_alert=False)
        
    except Exception as e:
        logger.error(f"[MENTIONS] Confirm send error: {e}", exc_info=True)
        await cb.answer("❌ Terjadi kesalahan.", show_alert=True)

# 🔥 PERBAIKAN: Handler pembatalan
@Altruix.bot.on_callback_query(filters.regex(r"^mentions_cancel_(\d+)$"))
@log_errors
async def cancel_send_reply(c: Client, cb: CallbackQuery):
    """Membatalkan pengiriman balasan."""
    try:
        reply_msg_id = int(cb.data.split("_")[2])
        logger.info(f"[MENTIONS] Cancel reply for {reply_msg_id}")
        
        if reply_msg_id in REPLY_AS_MENTIONED_WAITING:
            data = REPLY_AS_MENTIONED_WAITING[reply_msg_id]
            
            # Hapus pesan terkait
            messages_to_delete = []
            if data.get("user_msg_id"):
                messages_to_delete.append(data["user_msg_id"])
            if data.get("confirm_msg_id"):
                messages_to_delete.append(data["confirm_msg_id"])
            if data.get("instruction_msg_id"):
                messages_to_delete.append(data["instruction_msg_id"])
            
            if messages_to_delete:
                try:
                    await asyncio.wait_for(
                        Altruix.bot.delete_messages(cb.message.chat.id, messages_to_delete),
                        timeout=10
                    )
                except Exception as delete_err:
                    logger.warning(f"[MENTIONS] Delete messages failed: {delete_err}")
            
            REPLY_AS_MENTIONED_WAITING.pop(reply_msg_id, None)
            
            await safe_edit_message(
                c,
                cb.message.chat.id,
                cb.message.id,
                "❌ <b>Pengiriman dibatalkan.</b>",
                parse_mode=enums.ParseMode.HTML
            )
            await cb.answer("❌ Dibatalkan.", show_alert=True)
        else:
            await cb.answer("❌ Tidak ada proses yang berjalan.", show_alert=True)
            
    except Exception as e:
        logger.error(f"[MENTIONS] Cancel error: {e}")
        await cb.answer("❌ Terjadi kesalahan.", show_alert=True)

# 🔥 Handler untuk reacted button
@Altruix.bot.on_callback_query(filters.regex(r"^mentions_reacted$"))
@log_errors
async def already_reacted_handler(c: Client, cb: CallbackQuery):
    """Handler untuk tombol yang sudah direaksi."""
    await cb.answer("✅ Sudah direaksi sebelumnya", show_alert=False)

# 🔥 PERBAIKAN: Command untuk status
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
    
    status_msg = (
        f"📊 **Mention Plugin Status**\n\n"
        f"• **Version:** {PLUGIN_VERSION}\n"
        f"• **Mention Notifications:** {'✅ ENABLED' if user_setting else '❌ DISABLED'}\n"
        f"• **Auto-Reply:** {'✅ ON' if AUTO_REPLY_ENABLED else '❌ OFF'}\n"
        f"• **Cache Size:** {len(MENTION_LOG_CACHE)} mentions\n"
        f"• **Waiting Replies:** {len(REPLY_AS_MENTIONED_WAITING)}\n"
        f"• **Client:** {c.me.first_name} (ID: `{c.me.id}`)\n"
        f"• **Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"**Commands:**\n"
        f"• `/mentions on/off` - Toggle notifications\n"
        f"• `/autoreply on/off` - Toggle auto-reply\n"
        f"• `/mentions_backup` - Backup settings"
    )
    
    await safe_edit_message(
        c,
        m.chat.id,
        msg.id,
        status_msg,
        parse_mode=enums.ParseMode.MARKDOWN
    )

# 🔥 PERBAIKAN: Command untuk backup - FIX bot cannot send to bot
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
        
        # 🔥 PERBAIKAN: Coba backup dengan userbot
        backup_success = await backup_to_telegram(c)
        
        if backup_success:
            backup_msg = (
                f"📂 **Mention Settings Backup**\n\n"
                f"• **Settings:** {len(MENTIONS_DATA)} entries\n"
                f"• **Auto-Reply:** {'ON' if AUTO_REPLY_ENABLED else 'OFF'}\n"
                f"• **Backup Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"• **File:** `{LOCAL_STORAGE_FILE.name}`\n\n"
                f"✅ Backup berhasil."
            )
        else:
            backup_msg = (
                f"📂 **Mention Settings Backup**\n\n"
                f"• **Settings:** {len(MENTIONS_DATA)} entries\n"
                f"• **Auto-Reply:** {'ON' if AUTO_REPLY_ENABLED else 'OFF'}\n"
                f"• **Backup Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"• **Status:** ✅ Local backup saved\n\n"
                f"⚠️ Could not send to Telegram, but local backup is safe."
            )
        
        await safe_edit_message(
            c,
            m.chat.id,
            msg.id,
            backup_msg,
            parse_mode=enums.ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"[MENTIONS] Backup failed: {e}")
        await msg.edit_msg(f"❌ Backup error: {str(e)[:100]}")

# 🔥 PERBAIKAN: Command untuk clear cache
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
        global MENTION_LOG_CACHE, REPLY_AS_MENTIONED_WAITING
        
        cache_count = len(MENTION_LOG_CACHE)
        waiting_count = len(REPLY_AS_MENTIONED_WAITING)
        
        MENTION_LOG_CACHE.clear()
        REPLY_AS_MENTIONED_WAITING.clear()
        
        clear_msg = (
            f"🧹 **Cache Cleared**\n\n"
            f"• **Mention Cache:** {cache_count} entries cleared\n"
            f"• **Waiting Replies:** {waiting_count} entries cleared\n"
            f"• **Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"✅ Cache telah dibersihkan."
        )
        
        await safe_edit_message(
            c,
            m.chat.id,
            msg.id,
            clear_msg,
            parse_mode=enums.ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"[MENTIONS] Clear cache failed: {e}")
        await msg.edit_msg(f"❌ Clear error: {str(e)[:100]}")

# 🔥 Cleanup task dengan error handling
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
            
            for key in expired_cache[:50]:  # Batasi per cleanup
                try:
                    del MENTION_LOG_CACHE[key]
                except:
                    pass
            
            if expired_cache:
                logger.debug(f"[MENTIONS] Cleaned {len(expired_cache[:50])} cache entries")
            
            # Clean old waiting (1 hour)
            expired_waiting = []
            for key, data in REPLY_AS_MENTIONED_WAITING.items():
                if current_time - data.get("timestamp_int", 0) > 3600:
                    expired_waiting.append(key)
            
            for key in expired_waiting[:20]:  # Batasi per cleanup
                try:
                    del REPLY_AS_MENTIONED_WAITING[key]
                except:
                    pass
            
            if expired_waiting:
                logger.debug(f"[MENTIONS] Cleaned {len(expired_waiting[:20])} waiting entries")
                
        except Exception as e:
            logger.error(f"[MENTIONS] Cleanup error: {e}")
        
        await asyncio.sleep(600)  # Run every 10 minutes

# Start cleanup task
asyncio.create_task(cleanup_old_entries())

# Log sukses loading
try:
    Altruix.log(f"[DEBUG] Loaded → {__plugin_name__} {PLUGIN_VERSION}", level=20)
    logger.info(f"[MENTIONS] Plugin loaded with timeout protection!")
    logger.info(f"[MENTIONS] Features: Mentions, Auto-Reply, Quick reactions, Reply-as-mentioned")
except Exception as e:
    logger.info(f"[DEBUG] Loaded → {__plugin_name__} {PLUGIN_VERSION}")
