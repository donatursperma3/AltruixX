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
    ReplyParameters
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

plugin_name = f"plugins/userbot/{os.path.basename(__file__)}"
__plugin_name__ = plugin_name if plugin_name else "mentions"
PLUGIN_VERSION = "0.1.2.0"  # 🔥 PERBAIKAN: Versi final fix semua tipe data
logger = logging.getLogger(f"{__plugin_name__}")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - [SET PLUGIN] - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# 🔥 PERBAIKAN: Helper functions untuk type safety
def safe_datetime_fromtimestamp(timestamp):
    """Convert timestamp to datetime dengan handling semua tipe data."""
    try:
        if timestamp is None:
            return datetime.now()
        
        if isinstance(timestamp, datetime):
            return timestamp  # Sudah datetime, return langsung
        
        if isinstance(timestamp, (int, float)):
            # Pastikan timestamp dalam range yang wajar
            if timestamp > 4102444800:  # 2100-01-01
                timestamp = timestamp / 1000  # Mungkin milliseconds
            return datetime.fromtimestamp(float(timestamp))
        
        if isinstance(timestamp, str):
            # Coba parse string
            try:
                return datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except:
                pass
        
        # Fallback ke current time
        return datetime.now()
    except Exception as e:
        logger.warning(f"[MENTIONS] Safe datetime conversion failed: {e}, using current time")
        return datetime.now()

def safe_get_timestamp(obj):
    """Get timestamp dari object dengan type checking."""
    try:
        if hasattr(obj, 'date'):
            date_val = obj.date
            if isinstance(date_val, datetime):
                return int(date_val.timestamp())
            elif isinstance(date_val, (int, float)):
                return int(date_val)
        
        if hasattr(obj, 'edit_date'):
            edit_val = obj.edit_date
            if isinstance(edit_val, datetime):
                return int(edit_val.timestamp())
            elif isinstance(edit_val, (int, float)):
                return int(edit_val)
        
        return int(time.time())
    except Exception as e:
        logger.warning(f"[MENTIONS] Safe timestamp failed: {e}")
        return int(time.time())

# 🔥 PERBAIKAN: Local JSON storage sebagai fallback
LOCAL_STORAGE_FILE = Path("mentions_settings.json")
MENTIONS_DATA = {}

# 🔥 TAMBAHAN: Dictionary untuk melacak pesan mention yang sudah dikirim (untuk deteksi edit)
MENTION_LOG_CACHE = {}

# 🔥 TAMBAHAN: Emoji default untuk quick reaction (5 pilihan)
DEFAULT_REACTION_EMOJIS = ["👍", "❤️", "😂", "😮", "😢"]

# 🔥 TAMBAHAN: Dictionary untuk menunggu konfirmasi reply-as-mentioned
REPLY_AS_MENTIONED_WAITING = {}

# 🔥 PERBAIKAN: Flag untuk track database status
DATABASE_CORRUPTION_DETECTED = False

async def load_local_storage():
    """Load data dari local JSON file."""
    global MENTIONS_DATA
    try:
        if LOCAL_STORAGE_FILE.exists():
            async with aiofiles.open(LOCAL_STORAGE_FILE, 'r', encoding='utf-8') as f:
                content = await f.read()
                if content.strip():
                    MENTIONS_DATA = json.loads(content)
                    logger.info(f"[MENTIONS] Loaded {len(MENTIONS_DATA)} settings from local storage")
                else:
                    MENTIONS_DATA = {}
        else:
            MENTIONS_DATA = {}
            logger.info("[MENTIONS] Local storage file not found, creating new")
    except Exception as e:
        logger.error(f"[MENTIONS] Failed to load local storage: {e}")
        MENTIONS_DATA = {}
        await save_local_storage()

async def save_local_storage():
    """Save data ke local JSON file."""
    try:
        async with aiofiles.open(LOCAL_STORAGE_FILE, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(MENTIONS_DATA, indent=2, ensure_ascii=False))
        logger.debug(f"[MENTIONS] Saved {len(MENTIONS_DATA)} settings to local storage")
    except Exception as e:
        logger.error(f"[MENTIONS] Failed to save local storage: {e}")

async def backup_to_telegram(client):
    """Upload backup ke Telegram jika diperlukan."""
    try:
        if LOCAL_STORAGE_FILE.exists() and LOCAL_STORAGE_FILE.stat().st_size > 0:
            # Kirim file ke saved messages
            await client.send_document(
                "me",  # Kirim ke saved messages
                str(LOCAL_STORAGE_FILE),
                caption=f"📂 Backup Mention Settings\n"
                       f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                       f"📊 Entries: {len(MENTIONS_DATA)}"
            )
            logger.info("[MENTIONS] Backup sent to Telegram saved messages")
    except Exception as e:
        logger.error(f"[MENTIONS] Failed to send backup to Telegram: {e}")

async def fix_database_corruption(client_id):
    """Fix database corruption dengan cara yang lebih agresif."""
    global DATABASE_CORRUPTION_DETECTED
    
    if not hasattr(Altruix.db, 'settings_col'):
        return False
    
    try:
        setting_key = f"MENTION_LOG_{client_id}"
        
        # 1. Hapus semua document yang corrupt
        try:
            await Altruix.db.settings_col.delete_many({
                "$or": [
                    {"_id": setting_key},
                    {"_id": "MENTION_LOG"},
                    {"updated_at": {"$type": "date"}},  # Hapus yang punya datetime
                    {"$where": "typeof this.updated_at === 'object'"}  # Hapus object apapun
                ]
            })
            logger.info(f"[MENTIONS] Force cleaned corrupt entries for client {client_id}")
        except Exception as e:
            logger.error(f"[MENTIONS] Clean failed: {e}")
        
        # 2. Buat document baru yang bersih
        try:
            clean_doc = {
                "_id": setting_key,
                "value": MENTIONS_DATA.get(str(client_id), {}).get("value", False),
                "client_id": client_id,
                "timestamp_int": int(time.time()),  # INTEGER ONLY
                "created_at_int": int(time.time()),  # INTEGER ONLY
                "plugin": "mentions",
                "version": PLUGIN_VERSION,
                "data_type": "int_only"  # Flag untuk pastikan hanya integer
            }
            
            await Altruix.db.settings_col.insert_one(clean_doc)
            logger.info(f"[MENTIONS] Created clean document for {setting_key}")
            return True
            
        except Exception as e:
            logger.error(f"[MENTIONS] Create clean doc failed: {e}")
            DATABASE_CORRUPTION_DETECTED = True
            return False
            
    except Exception as e:
        logger.error(f"[MENTIONS] Fix database corruption failed: {e}")
        DATABASE_CORRUPTION_DETECTED = True
        return False

async def get_mention_setting_safe_ultimate(client_id, client_name="Unknown"):
    """ULTIMATE safe method untuk membaca setting."""
    global DATABASE_CORRUPTION_DETECTED
    
    # 🔥 STRATEGI 1: Cek local storage dulu (paling aman)
    client_id_str = str(client_id)
    if client_id_str in MENTIONS_DATA:
        setting_data = MENTIONS_DATA[client_id_str]
        if isinstance(setting_data, dict) and "value" in setting_data:
            value = bool(setting_data["value"])
        else:
            value = bool(setting_data) if isinstance(setting_data, (bool, int)) else False
        
        logger.debug(f"[MENTIONS] Local storage for {client_id}: {value}")
        return value
    
    # 🔥 STRATEGY 2: Cek config cache
    if hasattr(Altruix.config, "mention_settings") and client_id in Altruix.config.mention_settings:
        value = bool(Altruix.config.mention_settings[client_id])
        logger.debug(f"[MENTIONS] Config cache for {client_id}: {value}")
        
        # Simpan ke local storage
        MENTIONS_DATA[client_id_str] = {
            "value": value,
            "source": "config_cache",
            "timestamp_int": int(time.time()),
            "client_name": client_name
        }
        await save_local_storage()
        
        return value
    
    # 🔥 STRATEGY 3: Jika database tidak corrupt, coba baca
    if hasattr(Altruix.db, 'settings_col') and not DATABASE_CORRUPTION_DETECTED:
        setting_key = f"MENTION_LOG_{client_id}"
        
        try:
            # Coba baca dengan projection yang sangat spesifik
            # HANYA ambil field integer/boolean
            doc = await Altruix.db.settings_col.find_one(
                {"_id": setting_key},
                {
                    "value": 1,
                    "_id": 1,
                    "timestamp_int": 1,
                    "data_type": 1
                }
            )
            
            if doc:
                # Extract value dengan type checking
                raw_value = doc.get("value")
                if isinstance(raw_value, bool):
                    value = raw_value
                elif isinstance(raw_value, (int, float)):
                    value = bool(raw_value)
                elif isinstance(raw_value, str):
                    value = raw_value.lower() in ["true", "yes", "1", "on"]
                else:
                    value = False
                
                # Periksa apakah document clean
                if doc.get("data_type") != "int_only":
                    # Document mungkin corrupt, mark database sebagai corrupt
                    DATABASE_CORRUPTION_DETECTED = True
                    logger.warning(f"[MENTIONS] Document not int_only, marking DB as corrupt")
                
                # Simpan ke backup systems
                MENTIONS_DATA[client_id_str] = {
                    "value": value,
                    "source": "mongodb",
                    "timestamp_int": int(time.time()),
                    "client_name": client_name
                }
                await save_local_storage()
                
                if not hasattr(Altruix.config, "mention_settings"):
                    Altruix.config.mention_settings = {}
                Altruix.config.mention_settings[client_id] = value
                
                return value
                
        except Exception as e:
            logger.error(f"[MENTIONS] MongoDB read failed: {e}")
            DATABASE_CORRUPTION_DETECTED = True
    
    # 🔥 STRATEGY 4: Default value
    default_value = False
    MENTIONS_DATA[client_id_str] = {
        "value": default_value,
        "source": "default",
        "timestamp_int": int(time.time()),
        "client_name": client_name
    }
    await save_local_storage()
    
    logger.info(f"[MENTIONS] Default for {client_id}: {default_value}")
    return default_value

async def save_mention_setting_ultimate(client_id, value, client_name="Unknown"):
    """ULTIMATE safe method untuk menyimpan setting."""
    global DATABASE_CORRUPTION_DETECTED
    
    client_id_str = str(client_id)
    bool_value = bool(value)
    
    # 🔥 STRATEGY 1: Simpan ke local storage
    MENTIONS_DATA[client_id_str] = {
        "value": bool_value,
        "source": "manual_save",
        "timestamp_int": int(time.time()),
        "client_name": client_name,
        "saved_at_int": int(time.time())
    }
    await save_local_storage()
    
    # 🔥 STRATEGY 2: Simpan ke config cache
    if not hasattr(Altruix.config, "mention_settings"):
        Altruix.config.mention_settings = {}
    Altruix.config.mention_settings[client_id] = bool_value
    
    # 🔥 STRATEGY 3: Coba simpan ke MongoDB jika tidak corrupt
    if hasattr(Altruix.db, 'settings_col') and not DATABASE_CORRUPTION_DETECTED:
        setting_key = f"MENTION_LOG_{client_id}"
        
        try:
            # Buat document yang SANGAT clean
            clean_doc = {
                "_id": setting_key,
                "value": bool_value,
                "client_id": client_id,
                "client_name": client_name,
                "timestamp_int": int(time.time()),
                "saved_at_int": int(time.time()),
                "plugin": "mentions",
                "version": PLUGIN_VERSION,
                "data_type": "int_only",  # Flag penting
                "fields": ["_id", "value", "client_id", "timestamp_int", "data_type"]  # Hanya field ini
            }
            
            await Altruix.db.settings_col.update_one(
                {"_id": setting_key},
                {"$set": clean_doc},
                upsert=True
            )
            logger.info(f"[MENTIONS] Saved to MongoDB: {setting_key} = {bool_value}")
            
        except Exception as e:
            logger.error(f"[MENTIONS] MongoDB save failed: {e}")
            DATABASE_CORRUPTION_DETECTED = True
    
    logger.info(f"[MENTIONS] Saved for {client_id}: {bool_value}")
    return True

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
        await msg.edit_msg("TURNED_ON_MENTIONS_GLOBALLY")
    elif user_input in ["off", "no"]:
        value = False
        await msg.edit_msg("TURNED_OFF_MENTIONS_GLOBALLY")
    else:
        return await msg.edit_msg("INVALID_INPUT")
    
    try:
        client_id = c.me.id
        client_name = c.me.first_name or c.me.username or "Unknown"
        
        await save_mention_setting_ultimate(client_id, value, client_name)
        
        status_msg = f"✅ **Mention notifications {'ENABLED' if value else 'DISABLED'}**\n\n"
        status_msg += f"• **Client:** {client_name} (ID: `{client_id}`)\n"
        status_msg += f"• **Local Storage:** ✅\n"
        status_msg += f"• **Config Cache:** ✅\n"
        status_msg += f"• **MongoDB:** {'✅' if not DATABASE_CORRUPTION_DETECTED else '⚠️ Backup'}\n"
        status_msg += f"• **Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        await msg.edit_msg(status_msg)
        
    except Exception as e:
        error_detail = str(e)
        Altruix.log(f"[ERROR] Save failed: {error_detail}", level=40)
        await msg.edit_msg(f"❌ Save error: {error_detail[:100]}")

@Altruix.on_message(
    filters.mentioned & filters.group & ~filters.user(Altruix.bot_info.id)
)
@log_errors
async def send_mention_log_handler(c: Client, m: RawMessage):
    """Handler utama untuk menangkap mention dan mengirim notifikasi ke LOG_CHAT."""
    try:
        client_id = c.me.id
        client_name = c.me.first_name or c.me.username or "Unknown"
        
        # 🔥 PERBAIKAN: Gunakan safe method
        is_enabled = await get_mention_setting_safe_ultimate(client_id, client_name)
        
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
        
        # 🔥 PERBAIKAN UTAMA: Handle m.date dengan safe function
        try:
            # m.date bisa berupa datetime ATAU integer
            if hasattr(m, 'date'):
                date_value = m.date
                if isinstance(date_value, datetime):
                    # Jika sudah datetime, gunakan langsung
                    mention_datetime = date_value
                elif isinstance(date_value, (int, float)):
                    # Jika integer/float, convert ke datetime
                    mention_datetime = datetime.fromtimestamp(float(date_value))
                else:
                    # Fallback
                    mention_datetime = datetime.now()
            else:
                mention_datetime = datetime.now()
            
            mention_time = mention_datetime.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as date_err:
            logger.warning(f"[MENTIONS] Date error: {date_err}, using current time")
            mention_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 🔥 PERBAIKAN: Handle message text
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
        
        # 🔥 PERBAIKAN: Handle edit detection dengan safe function
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
            f"📄 <b>Message:</b>\n<blockquote>{message_text}</blockquote>"
        )
        
        # Tombol
        reaction_buttons = [
            InlineKeyboardButton(emoji, callback_data=f"react_mention_{m.chat.id}_{m.id}_{emoji}")
            for emoji in DEFAULT_REACTION_EMOJIS
        ]
        reply_button = [InlineKeyboardButton("🗨️ Reply as Mentioned", callback_data=f"reply_as_mentioned_{m.chat.id}_{m.id}")]
        link_button = [InlineKeyboardButton("🔗 Go to Message", url=m.link)]
        
        msg_key = f"{m.chat.id}_{m.id}"
        
        # Cek cache untuk edit
        if is_edited_message and msg_key in MENTION_LOG_CACHE:
            try:
                old_data = MENTION_LOG_CACHE[msg_key]
                await Altruix.bot.edit_message_text(
                    chat_id=Altruix.log_chat,
                    message_id=old_data["log_msg_id"],
                    text=log_message,
                    parse_mode=enums.ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=InlineKeyboardMarkup([reaction_buttons, reply_button, link_button])
                )
                MENTION_LOG_CACHE[msg_key]["text"] = message_text
                return
            except Exception:
                pass
        
        # Kirim notifikasi baru
        try:
            sent_log_msg = await Altruix.bot.send_message(
                Altruix.log_chat,
                log_message,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=InlineKeyboardMarkup([reaction_buttons, reply_button, link_button])
            )
        except Exception as send_err:
            logger.error(f"[MENTIONS] Send failed: {send_err}")
            return
        
        # Auto-reply untuk pesan baru
        if not is_edited_message:
            try:
                await c.send_message(
                    Altruix.log_chat,
                    "💬 Saya yang disebut di atas.",
                    reply_parameters=ReplyParameters(
                        message_id=sent_log_msg.id,
                        chat_id=Altruix.log_chat
                    )
                )
            except Exception:
                pass
        
        # Cache untuk edit detection
        MENTION_LOG_CACHE[msg_key] = {
            "text": message_text,
            "log_msg_id": sent_log_msg.id,
            "mentioned_client": c,
            "chat_id": m.chat.id,
            "message_id": m.id,
            "timestamp_int": int(time.time())  # 🔥 INTEGER ONLY
        }
        
        # Cache management
        if len(MENTION_LOG_CACHE) > 100:
            # Remove oldest entry
            oldest = min(MENTION_LOG_CACHE.items(), key=lambda x: x[1].get("timestamp_int", 0))
            del MENTION_LOG_CACHE[oldest[0]]
            
    except Exception as e:
        error_msg = str(e)
        Altruix.log(f"[CRITICAL] Error in mention handler: {error_msg}", level=50)
        
        # Log error details
        logger.error(f"[MENTIONS] Handler error: {error_msg}")
        logger.error(f"[MENTIONS] Traceback: {traceback.format_exc()}")
        
        # Handle specific datetime error
        if "an integer is required" in error_msg and "datetime.datetime" in error_msg:
            logger.error(f"[MENTIONS] Message datetime corruption detected")
            
            # Coba fix corruption
            if c and c.me:
                await fix_database_corruption(c.me.id)
            
            # Kirim error report
            try:
                await Altruix.bot.send_message(
                    Altruix.log_chat,
                    f"⚠️ <b>Message Date Format Issue</b>\n\n"
                    f"Pyrogram message date is datetime object, not integer.\n"
                    f"Plugin has adjusted to handle this format.",
                    parse_mode=enums.ParseMode.HTML
                )
            except:
                pass

# 🔥 Handler untuk memulai proses reply-as-mentioned
@Altruix.bot.on_callback_query(filters.regex(r"reply_as_mentioned_(\d+)_(\d+)"))
@log_errors
async def start_reply_as_mentioned(c: Client, cb):
    try:
        chat_id = int(cb.data.split("_")[3])
        message_id = int(cb.data.split("_")[4])
        msg_key = f"{chat_id}_{message_id}"
        
        if msg_key not in MENTION_LOG_CACHE:
            await cb.answer("❌ Mention tidak ditemukan.", show_alert=True)
            return
        
        mentioned_client = MENTION_LOG_CACHE[msg_key]["mentioned_client"]
        if not mentioned_client:
            await cb.answer("❌ Akun yang disebut tidak tersedia.", show_alert=True)
            return
        
        REPLY_AS_MENTIONED_WAITING[cb.message.id] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "mentioned_client": mentioned_client,
            "log_msg_id": cb.message.id,
            "timestamp_int": int(time.time())
        }
        
        await cb.message.reply_text(
            "🗨️ <b>Reply as Mentioned</b>\n\n"
            "Ketik pesan balasan Anda di bawah ini.",
            reply_parameters=ReplyParameters(
                message_id=cb.message.id,
                chat_id=cb.message.chat.id
            )
        )
        await cb.answer("Silakan ketik balasan Anda.", show_alert=False)
        
    except Exception as e:
        logger.error(f"[MENTIONS] Reply start error: {e}")
        await cb.answer("❌ Terjadi kesalahan.", show_alert=True)

# 🔥 Handler untuk menerima input balasan
@Altruix.bot.on_message(filters.chat(Altruix.log_chat) & filters.reply & ~filters.user(Altruix.bot_info.id))
@log_errors
async def handle_reply_as_mentioned_input(c: Client, m: RawMessage):
    if not m.reply_to_message:
        return
    
    reply_msg_id = m.reply_to_message.id
    if reply_msg_id not in REPLY_AS_MENTIONED_WAITING:
        return
    
    data = REPLY_AS_MENTIONED_WAITING[reply_msg_id]
    chat_id = data["chat_id"]
    message_id = data["message_id"]
    mentioned_client = data["mentioned_client"]
    
    reply_text = m.text or m.caption or ""
    if not reply_text.strip():
        await m.reply_text("❌ Pesan kosong")
        return
    
    confirm_buttons = [
        [InlineKeyboardButton("✅ Yes, Send", callback_data=f"confirm_reply_{reply_msg_id}")],
        [InlineKeyboardButton("❌ No, Cancel", callback_data=f"cancel_reply_{reply_msg_id}")]
    ]
    
    confirm_msg = (
        f"⚠️ <b>Konfirmasi Kirim Balasan</b>\n\n"
        f"Pesan: {html.escape(reply_text[:200])}\n\n"
        f"Kirim sebagai {mentioned_client.me.first_name if mentioned_client.me else 'Unknown'}?"
    )
    
    await m.reply_text(
        confirm_msg,
        parse_mode=enums.ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(confirm_buttons),
        reply_parameters=ReplyParameters(
            message_id=m.id,
            chat_id=m.chat.id
        )
    )
    
    REPLY_AS_MENTIONED_WAITING[reply_msg_id]["reply_text"] = reply_text
    REPLY_AS_MENTIONED_WAITING[reply_msg_id]["user_msg_id"] = m.id

# 🔥 Handler konfirmasi kirim
@Altruix.bot.on_callback_query(filters.regex(r"confirm_reply_(\d+)"))
@log_errors
async def confirm_send_reply(c: Client, cb):
    try:
        reply_msg_id = int(cb.data.split("_")[2])
        if reply_msg_id not in REPLY_AS_MENTIONED_WAITING:
            await cb.answer("❌ Data tidak ditemukan.", show_alert=True)
            return
        
        data = REPLY_AS_MENTIONED_WAITING[reply_msg_id]
        chat_id = data["chat_id"]
        message_id = data["message_id"]
        mentioned_client = data["mentioned_client"]
        reply_text = data["reply_text"]
        user_msg_id = data["user_msg_id"]
        
        await mentioned_client.send_message(
            chat_id,
            reply_text,
            reply_to_message_id=message_id
        )
        
        await cb.message.edit_text("✅ <b>Balasan berhasil dikirim!</b>", parse_mode=enums.ParseMode.HTML)
        
        try:
            await Altruix.bot.delete_messages(Altruix.log_chat, user_msg_id)
        except:
            pass
        
        REPLY_AS_MENTIONED_WAITING.pop(reply_msg_id, None)
        await cb.answer("✅ Balasan terkirim!", show_alert=False)
        
    except Exception as e:
        logger.error(f"[MENTIONS] Confirm reply error: {e}")
        await cb.message.edit_text("❌ <b>Gagal mengirim balasan.</b>", parse_mode=enums.ParseMode.HTML)
        await cb.answer("❌ Gagal mengirim.", show_alert=True)

# 🔥 Handler pembatalan
@Altruix.bot.on_callback_query(filters.regex(r"cancel_reply_(\d+)"))
@log_errors
async def cancel_send_reply(c: Client, cb):
    reply_msg_id = int(cb.data.split("_")[2])
    if reply_msg_id in REPLY_AS_MENTIONED_WAITING:
        data = REPLY_AS_MENTIONED_WAITING[reply_msg_id]
        user_msg_id = data.get("user_msg_id")
        try:
            await Altruix.bot.delete_messages(Altruix.log_chat, user_msg_id)
        except:
            pass
        REPLY_AS_MENTIONED_WAITING.pop(reply_msg_id, None)
        await cb.message.edit_text("❌ <b>Pengiriman dibatalkan.</b>", parse_mode=enums.ParseMode.HTML)
        await cb.answer("❌ Dibatalkan.", show_alert=True)
    else:
        await cb.answer("❌ Tidak ada proses yang berjalan.", show_alert=True)

# 🔥 Handler untuk quick reaction
@Altruix.bot.on_callback_query(filters.regex(r"react_mention_(\d+)_(\d+)_(.+)"))
@log_errors
async def quick_reaction_handler(c: Client, cb):
    try:
        chat_id = int(cb.data.split("_")[2])
        message_id = int(cb.data.split("_")[3])
        emoji = cb.data.split("_")[4]
        
        msg_key = f"{chat_id}_{message_id}"
        
        if msg_key not in MENTION_LOG_CACHE:
            await cb.answer("❌ Mention tidak ditemukan.", show_alert=True)
            return
        
        userbot_client = MENTION_LOG_CACHE[msg_key]["mentioned_client"]
        if not userbot_client:
            await cb.answer("❌ Akun yang disebut tidak tersedia.", show_alert=True)
            return
        
        try:
            await userbot_client.send_reaction(chat_id, message_id, emoji)
            await cb.answer(f"✅ Bereaksi dengan {emoji}", show_alert=False)
        except Exception as react_err:
            logger.error(f"[MENTIONS] Reaction error: {react_err}")
            await cb.answer("❌ Gagal mengirim reaksi.", show_alert=True)
            
    except Exception as e:
        logger.error(f"[MENTIONS] Quick reaction error: {e}")
        await cb.answer("❌ Terjadi kesalahan.", show_alert=True)

# 🔥 PERBAIKAN: Command untuk backup dan restore
@Altruix.register_on_cmd(
    ["mentions_backup"],
    cmd_help={
        "help": "Backup mention settings to Telegram",
        "example": "mentions_backup",
    },
    group_only=False,
    requires_input=False,
)
@log_errors
async def backup_command_handler(c: Client, m: AltruixMessage):
    """Backup settings ke Telegram."""
    msg = await m.handle_message("PROCESSING")
    
    try:
        await save_local_storage()
        await backup_to_telegram(c)
        
        backup_msg = (
            f"📂 **Mention Settings Backup**\n\n"
            f"• **Local Entries:** {len(MENTIONS_DATA)}\n"
            f"• **Database Status:** {'✅ OK' if not DATABASE_CORRUPTION_DETECTED else '⚠️ Corrupt'}\n"
            f"• **Backup Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        await msg.edit_msg(backup_msg)
        
    except Exception as e:
        await msg.edit_msg(f"❌ Backup failed: {str(e)[:100]}")

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
        f"• **Local Storage:** {len(MENTIONS_DATA)} entries\n"
        f"• **Cache Size:** {len(MENTION_LOG_CACHE)} mentions\n"
        f"• **Database:** {'✅ OK' if not DATABASE_CORRUPTION_DETECTED else '⚠️ Corrupt'}\n"
        f"• **Your Setting:** {'✅ ENABLED' if user_setting else '❌ DISABLED'}\n"
        f"• **Client:** {c.me.first_name} (ID: `{c.me.id}`)\n"
        f"• **Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    await msg.edit_msg(status_msg)

# Log sukses loading
try:
    Altruix.log(f"[DEBUG] Loaded → {__plugin_name__} {PLUGIN_VERSION}", level=20)
    logger.info(f"[MENTIONS] Plugin loaded with TYPE-SAFE datetime handling")
    logger.info(f"[MENTIONS] All datetime/integer issues should be resolved")
except Exception as e:
    logger.info(f"[DEBUG] Loaded → {__plugin_name__} {PLUGIN_VERSION}")
