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

plugin_name = f"plugins/userbot/{os.path.basename(__file__)}"
__plugin_name__ = plugin_name if plugin_name else "mentions"
PLUGIN_VERSION = "0.1.1.8"  # 🔥 PERBAIKAN: Versi lengkap dengan semua fitur
logger = logging.getLogger(f"{__plugin_name__}")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - [SET PLUGIN] - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# 🔥 TAMBAHAN: Dictionary untuk melacak pesan mention yang sudah dikirim (untuk deteksi edit)
MENTION_LOG_CACHE = {}

# 🔥 TAMBAHAN: Emoji default untuk quick reaction (5 pilihan)
DEFAULT_REACTION_EMOJIS = ["👍", "❤️", "😂", "😮", "😢"]

# 🔥 TAMBAHAN: Dictionary untuk menunggu konfirmasi reply-as-mentioned
REPLY_AS_MENTIONED_WAITING = {}

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
    value = False
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
        # 🔥 PERBAIKAN: Gunakan integer timestamp untuk semua operasi database
        setting_key = f"MENTION_LOG_{c.me.id}"
        
        db_success = False
        
        try:
            # 🔥 PERBAIKAN: Pastikan kita hanya menggunakan integer timestamp
            current_timestamp = int(time.time())
            current_datetime_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            if hasattr(Altruix.db, 'settings_col'):
                await Altruix.db.settings_col.update_one(
                    {"_id": setting_key},
                    {"$set": {
                        "value": value, 
                        "client_id": c.me.id, 
                        "client_name": c.me.first_name or c.me.username,
                        "client_username": c.me.username or "No username",
                        "updated_at": current_timestamp,  # 🔥 HANYA INTEGER
                        "updated_at_str": current_datetime_str,  # 🔥 String untuk display
                        "plugin": "mentions",
                        "timestamp_type": "int",
                        "version": PLUGIN_VERSION
                    }},
                    upsert=True
                )
                db_success = True
                logger.info(f"[MENTIONS] Setting saved to database: {setting_key} = {value}")
                
                # 🔥 PERBAIKAN: Hapus data lama jika ada
                try:
                    old_data = await Altruix.db.settings_col.find_one({"_id": "MENTION_LOG"})
                    if old_data:
                        logger.info(f"[MENTIONS] Found old setting MENTION_LOG, migrating...")
                        await Altruix.db.settings_col.delete_one({"_id": "MENTION_LOG"})
                        logger.info(f"[MENTIONS] Deleted old setting MENTION_LOG")
                except Exception as delete_err:
                    logger.debug(f"[MENTIONS] Could not delete old setting: {delete_err}")
                    
            else:
                logger.warning(f"[MENTIONS] Database settings_col not available, using config only")
                db_success = False
                
        except Exception as db_err:
            logger.error(f"[MENTIONS] Database operation error: {str(db_err)}", exc_info=True)
            db_success = False
        
        # 🔥 PERBAIKAN: Selalu simpan di config untuk akses cepat (cache)
        if not hasattr(Altruix.config, "mention_settings"):
            Altruix.config.mention_settings = {}
        Altruix.config.mention_settings[c.me.id] = value
        
        # 🔥 LOGGING DETAIL: Catat status penyimpanan
        if db_success:
            logger.info(f"[MENTIONS] Successfully saved setting to DB and cache: {setting_key} = {value}")
        else:
            logger.warning(f"[MENTIONS] Saved setting to cache only (DB unavailable): {setting_key} = {value}")
        
        # 🔥 PERBAIKAN: Kirim pesan sukses dengan detail
        if db_success:
            success_msg = f"✅ **Mention notifications {'ENABLED' if value else 'DISABLED'}**\n\n"
            success_msg += f"• **Status:** Saved to database ✅\n"
            success_msg += f"• **Client:** {c.me.first_name} (ID: {c.me.id})\n"
            success_msg += f"• **Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        else:
            success_msg = f"⚠️ **Mention notifications {'ENABLED' if value else 'DISABLED'}**\n\n"
            success_msg += f"• **Status:** Saved to cache only (DB unavailable)\n"
            success_msg += f"• **Client:** {c.me.first_name} (ID: {c.me.id})\n"
            success_msg += f"• **Note:** Restart may reset this setting"
        
        await msg.edit_msg(success_msg)
        
    except Exception as e:
        error_detail = str(e)
        Altruix.log(f"[ERROR] Failed to save mention setting: {error_detail}", level=40)
        
        # 🔥 PERBAIKAN: Error handling yang lebih informatif
        error_msg = f"❌ **Failed to save setting**\n\n"
        error_msg += f"• **Error:** {error_detail[:150]}\n"
        error_msg += f"• **Client ID:** {c.me.id if c and c.me else 'Unknown'}\n"
        error_msg += f"• **Time:** {datetime.now().strftime('%H:%M:%S')}"
        
        await msg.edit_msg(error_msg)
        return


@Altruix.on_message(
    filters.mentioned & filters.group & ~filters.user(Altruix.bot_info.id)
)
@log_errors
async def send_mention_log_handler(c: Client, m: RawMessage):
    """Handler utama untuk menangkap mention dan mengirim notifikasi ke LOG_CHAT."""
    try:
        # 🔥 PERBAIKAN: Gunakan helper function untuk membaca setting dengan aman
        async def get_mention_setting_safe(client_id):
            """Baca setting mention dengan handling datetime error yang aman."""
            
            # 1. Cek cache config dulu (paling aman dan cepat)
            if hasattr(Altruix.config, "mention_settings") and client_id in Altruix.config.mention_settings:
                cached_value = Altruix.config.mention_settings[client_id]
                logger.debug(f"[MENTIONS] Retrieved from cache for client {client_id}: {cached_value}")
                return cached_value
            
            # 2. Jika tidak ada di cache, coba baca dari database dengan cara yang aman
            if not hasattr(Altruix.db, 'settings_col'):
                logger.warning(f"[MENTIONS] Database settings_col not available for client {client_id}, using default (False)")
                return False
                
            setting_key = f"MENTION_LOG_{client_id}"
            
            try:
                # 🔥 PERBAIKAN UTAMA: Baca dengan projection untuk menghindari datetime field
                # Gunakan projection untuk hanya mengambil field yang diperlukan
                db_res = await Altruix.db.settings_col.find_one(
                    {"_id": setting_key},
                    {"value": 1, "_id": 1, "timestamp_type": 1}  # 🔥 HANYA ambil field yang diperlukan
                )
                
                if db_res and "value" in db_res:
                    value = db_res["value"]
                    logger.debug(f"[MENTIONS] Retrieved from database for client {client_id}: {value}")
                    
                    # 🔥 PERBAIKAN: Simpan ke cache untuk akses cepat di masa depan
                    if not hasattr(Altruix.config, "mention_settings"):
                        Altruix.config.mention_settings = {}
                    Altruix.config.mention_settings[client_id] = value
                    
                    return value
                    
                # 3. Jika tidak ditemukan dengan key baru, coba cari data lama (format lama)
                logger.debug(f"[MENTIONS] New key not found, searching for old format for client {client_id}")
                db_res_old = await Altruix.db.settings_col.find_one(
                    {"_id": "MENTION_LOG"},
                    {"value": 1, "_id": 1}  # 🔥 Projection juga untuk data lama
                )
                
                if db_res_old and "value" in db_res_old:
                    old_value = db_res_old["value"]
                    logger.info(f"[MENTIONS] Found old format setting for client {client_id}: {old_value}")
                    
                    # Migrasi ke format baru dengan timestamp integer
                    try:
                        migrate_timestamp = int(time.time())
                        await Altruix.db.settings_col.update_one(
                            {"_id": setting_key},
                            {"$set": {
                                "value": old_value,
                                "client_id": client_id,
                                "client_name": c.me.first_name if c and c.me else "Unknown",
                                "migrated_from": "MENTION_LOG",
                                "updated_at": migrate_timestamp,  # 🔥 INTEGER
                                "timestamp_type": "int",
                                "migration_time": migrate_timestamp
                            }},
                            upsert=True
                        )
                        
                        # Hapus data lama setelah migrasi berhasil
                        await Altruix.db.settings_col.delete_one({"_id": "MENTION_LOG"})
                        logger.info(f"[MENTIONS] Successfully migrated old setting for client {client_id}")
                        
                        # Simpan ke cache
                        if not hasattr(Altruix.config, "mention_settings"):
                            Altruix.config.mention_settings = {}
                        Altruix.config.mention_settings[client_id] = old_value
                        
                        return old_value
                    except Exception as migrate_err:
                        logger.error(f"[MENTIONS] Migration failed for client {client_id}: {migrate_err}")
                        return old_value  # Return nilai lama meski migrasi gagal
                        
            except Exception as e:
                logger.error(f"[MENTIONS] Error reading setting for client {client_id}: {str(e)}", exc_info=True)
                # 🔥 PERBAIKAN: Coba auto-fix jika error terkait datetime
                if "an integer is required" in str(e) and "datetime.datetime" in str(e):
                    logger.warning(f"[MENTIONS] Detected datetime corruption for client {client_id}, attempting fix...")
                    try:
                        # Coba fix dengan membaca tanpa field yang bermasalah
                        db_res_fix = await Altruix.db.settings_col.find_one(
                            {"_id": setting_key},
                            {"value": 1}
                        )
                        if db_res_fix and "value" in db_res_fix:
                            return db_res_fix["value"]
                    except Exception as fix_err:
                        logger.error(f"[MENTIONS] Auto-fix failed: {fix_err}")
            
            logger.debug(f"[MENTIONS] No setting found for client {client_id}, using default (False)")
            return False  # Default jika semua gagal
        
        # 🔥 PERBAIKAN: Gunakan helper function yang aman
        is_enabled = await get_mention_setting_safe(c.me.id)
        
        # Jika mention log tidak diaktifkan, return
        if not is_enabled:
            logger.debug(f"[MENTIONS] Mentions disabled for client {c.me.id}, ignoring mention")
            return

        logger.info(f"[MENTIONS] Processing mention for client {c.me.id} in group {m.chat.title} ({m.chat.id})")
        
        # Persiapan data mention
        mentioner = m.from_user
        if not mentioner:
            logger.debug(f"[MENTIONS] No mentioner info, skipping")
            return

        mentioner_name = mentioner.first_name or "Unknown"
        mentioner_id = mentioner.id
        mentioner_link = f"tg://user?id={mentioner_id}"
        mentioner_hyperlink = f'<a href="{mentioner_link}">{mentioner_name}</a>'
        
        # 🔥 PERBAIKAN: Ambil isi pesan dengan handling yang lebih baik
        message_text = m.text or m.caption or "[No text content]"
        if message_text:
            # Escape HTML characters
            message_text = html.escape(message_text)
        else:
            message_text = "[No text content]"
            
        # Jika ada media/file, tambahkan indicator
        if m.media and not m.text and not m.caption:
            media_type = "Document"
            if m.audio: media_type = "Audio"
            elif m.video: media_type = "Video"
            elif m.photo: media_type = "Photo"
            elif m.sticker: media_type = "Sticker"
            elif m.voice: media_type = "Voice"
            message_text = f"[{media_type}] {message_text}"

        # 🔥 PERBAIKAN: Gunakan datetime hanya untuk display, bukan untuk database
        mention_time = datetime.fromtimestamp(m.date).strftime("%Y-%m-%d %H:%M:%S")
        
        # Deteksi apakah ini pesan edit
        is_edited_message = hasattr(m, 'edit_date') and m.edit_date is not None
        edit_time = ""
        if is_edited_message:
            edit_time = datetime.fromtimestamp(m.edit_date).strftime("%Y-%m-%d %H:%M:%S")

        # Bangun pesan notifikasi lengkap
        if is_edited_message:
            log_message = (
                f"✏️ <b>Edited Mention Detected!</b>\n\n"
                f"👤 <b>Mentioned By:</b> {mentioner_hyperlink} (<code>{mentioner_id}</code>)\n"
                f"📛 <b>Username:</b> @{mentioner.username if mentioner.username else 'N/A'}\n"
                f"🤖 <b>My Account:</b> {c.me.mention(style=enums.ParseMode.HTML)}\n"
                f"💬 <b>Group:</b> {html.escape(m.chat.title)} (<code>{m.chat.id}</code>)\n"
                f"🕒 <b>Original Time:</b> <code>{mention_time}</code>\n"
                f"✏️ <b>Edited Time:</b> <code>{edit_time}</code>\n"
                f"📄 <b>Edited Message:</b>\n<blockquote>{message_text[:1000]}</blockquote>\n"
                f"📊 <b>Message ID:</b> <code>{m.id}</code>"
            )
        else:
            log_message = (
                f"🔔 <b>Mention Detected!</b>\n\n"
                f"👤 <b>Mentioned By:</b> {mentioner_hyperlink} (<code>{mentioner_id}</code>)\n"
                f"📛 <b>Username:</b> @{mentioner.username if mentioner.username else 'N/A'}\n"
                f"🤖 <b>My Account:</b> {c.me.mention(style=enums.ParseMode.HTML)}\n"
                f"💬 <b>Group:</b> {html.escape(m.chat.title)} (<code>{m.chat.id}</code>)\n"
                f"🕒 <b>Time:</b> <code>{mention_time}</code>\n"
                f"📄 <b>Message:</b>\n<blockquote>{message_text[:1000]}</blockquote>\n"
                f"📊 <b>Message ID:</b> <code>{m.id}</code>"
            )

        # 🔥 TOMBOL: Quick Reaction (5 emoji default)
        reaction_buttons = [
            InlineKeyboardButton(emoji, callback_data=f"react_mention_{m.chat.id}_{m.id}_{emoji}")
            for emoji in DEFAULT_REACTION_EMOJIS
        ]
        
        # 🔥 TOMBOL: Link ke pesan asli
        reply_button = [InlineKeyboardButton("🗨️ Reply as Mentioned", callback_data=f"reply_as_mentioned_{m.chat.id}_{m.id}")]
        link_button = [InlineKeyboardButton("🔗 Go to Message", url=m.link)]
        
        msg_key = f"{m.chat.id}_{m.id}"
        
        # 🔥 PERBAIKAN: Cek cache untuk pesan edit
        if is_edited_message and msg_key in MENTION_LOG_CACHE:
            old_data = MENTION_LOG_CACHE[msg_key]
            try:
                logger.info(f"[MENTIONS] Editing existing mention log for message {msg_key}")
                await Altruix.bot.edit_message_text(
                    chat_id=Altruix.log_chat,
                    message_id=old_data["log_msg_id"],
                    text=log_message,
                    parse_mode=enums.ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=InlineKeyboardMarkup([reaction_buttons, reply_button, link_button])
                )
                MENTION_LOG_CACHE[msg_key]["text"] = message_text
                MENTION_LOG_CACHE[msg_key]["last_updated"] = time.time()
                logger.info(f"[MENTIONS] Successfully updated edited mention: {msg_key}")
                return
            except Exception as edit_err:
                logger.warning(f"[MENTIONS] Failed to edit message log: {edit_err}")
                # Jika edit gagal, lanjut untuk kirim pesan baru
        
        # 🔥 KIRIM NOTIFIKASI BARU
        try:
            logger.info(f"[MENTIONS] Sending new mention notification for {msg_key}")
            sent_log_msg = await Altruix.bot.send_message(
                Altruix.log_chat,
                log_message,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=InlineKeyboardMarkup([reaction_buttons, reply_button, link_button])
            )
            logger.info(f"[MENTIONS] Successfully sent mention log: {msg_key}, log_msg_id: {sent_log_msg.id}")
        except Exception as send_err:
            logger.error(f"[MENTIONS] Failed to send mention notification: {send_err}")
            Altruix.log(f"[ERROR] Gagal kirim notifikasi mention: {send_err}", level=40)
            return

        # 🔥 BALAS OTOMATIS DARI USERBOT YANG DI-MENTION (hanya untuk pesan baru)
        if not is_edited_message:
            try:
                logger.debug(f"[MENTIONS] Sending auto-reply for mention {msg_key}")
                await c.send_message(
                    Altruix.log_chat,
                    "💬 Saya yang disebut di atas.",
                    reply_parameters=ReplyParameters(
                        message_id=sent_log_msg.id,
                        chat_id=Altruix.log_chat
                    )
                )
                logger.debug(f"[MENTIONS] Auto-reply sent successfully for {msg_key}")
            except Exception as reply_err:
                logger.warning(f"[MENTIONS] Failed to send auto-reply: {reply_err}")
                # Tidak critical, bisa diabaikan

        # 🔥 SIMPAN KE CACHE untuk deteksi edit
        MENTION_LOG_CACHE[msg_key] = {
            "text": message_text,
            "log_msg_id": sent_log_msg.id,
            "mentioned_client": c,
            "chat_id": m.chat.id,
            "message_id": m.id,
            "is_edited": is_edited_message,
            "timestamp": time.time(),
            "mentioner_id": mentioner_id
        }
        
        # 🔥 PERBAIKAN: Bersihkan cache lama (prevent memory leak)
        if len(MENTION_LOG_CACHE) > 100:  # Keep only last 100 mentions
            oldest_key = min(MENTION_LOG_CACHE.keys(), key=lambda k: MENTION_LOG_CACHE[k].get("timestamp", 0))
            del MENTION_LOG_CACHE[oldest_key]
            logger.debug(f"[MENTIONS] Cleaned old cache entry: {oldest_key}")
            
        logger.debug(f"[MENTIONS] Cached mention: {msg_key}, total cache size: {len(MENTION_LOG_CACHE)}")

    except Exception as e:
        # 🔥 PERBAIKAN: Error handling yang komprehensif
        error_msg = str(e)
        Altruix.log(f"[CRITICAL] Error in mention handler: {error_msg}", level=50)
        
        # 🔥 PERBAIKAN: Deteksi spesifik untuk datetime error dan coba auto-fix
        if "an integer is required" in error_msg and "datetime.datetime" in error_msg:
            logger.error(f"[MENTIONS] Database datetime corruption detected for client {c.me.id if c and c.me else 'unknown'}. Attempting auto-fix...")
            
            try:
                if hasattr(Altruix.db, 'settings_col'):
                    # Cari semua document dengan datetime di updated_at
                    fixed_count = 0
                    async for doc in Altruix.db.settings_col.find({"updated_at": {"$type": "date"}}):
                        try:
                            if isinstance(doc.get("updated_at"), datetime):
                                await Altruix.db.settings_col.update_one(
                                    {"_id": doc["_id"]},
                                    {"$set": {"updated_at": int(time.time()), "fixed_datetime": True}}
                                )
                                fixed_count += 1
                                logger.info(f"[MENTIONS] Fixed datetime in doc: {doc['_id']}")
                        except Exception as doc_err:
                            logger.error(f"[MENTIONS] Failed to fix doc {doc['_id']}: {doc_err}")
                    
                    if fixed_count > 0:
                        logger.info(f"[MENTIONS] Auto-fixed {fixed_count} documents with datetime corruption")
                        
                    # 🔥 PERBAIKAN: Update cache untuk menghindari error berikutnya
                    if c and c.me:
                        setting_key = f"MENTION_LOG_{c.me.id}"
                        # Force read dengan projection aman
                        try:
                            db_res = await Altruix.db.settings_col.find_one(
                                {"_id": setting_key},
                                {"value": 1}
                            )
                            if db_res and "value" in db_res:
                                if not hasattr(Altruix.config, "mention_settings"):
                                    Altruix.config.mention_settings = {}
                                Altruix.config.mention_settings[c.me.id] = db_res["value"]
                        except Exception as cache_err:
                            logger.error(f"[MENTIONS] Failed to update cache after fix: {cache_err}")
                            
            except Exception as fix_err:
                logger.error(f"[MENTIONS] Auto-fix operation failed: {fix_err}")
                
        else:
            # Tampilkan error biasa ke LOG_CHAT
            try:
                await Altruix.bot.send_message(
                    Altruix.log_chat,
                    f"⚠️ <b>Mention Handler Error</b>\n\n"
                    f"<code>{html.escape(error_msg[:500])}</code>\n\n"
                    f"<i>Check logs for details</i>",
                    parse_mode=enums.ParseMode.HTML
                )
            except Exception as send_error:
                logger.error(f"[MENTIONS] Could not send error message: {send_error}")


# 🔥 BARU: Handler untuk memulai proses reply-as-mentioned
@Altruix.bot.on_callback_query(filters.regex(r"reply_as_mentioned_(\d+)_(\d+)"))
@log_errors
async def start_reply_as_mentioned(c: Client, cb):
    """Memulai proses reply-as-mentioned dengan meminta input pesan."""
    try:
        logger.info(f"[MENTIONS] Starting reply-as-mentioned process, callback data: {cb.data}")
        
        chat_id = int(cb.data.split("_")[3])
        message_id = int(cb.data.split("_")[4])
        msg_key = f"{chat_id}_{message_id}"

        if msg_key not in MENTION_LOG_CACHE:
            logger.warning(f"[MENTIONS] Mention not found in cache for reply: {msg_key}")
            await cb.answer("❌ Mention tidak ditemukan.", show_alert=True)
            return

        mentioned_client = MENTION_LOG_CACHE[msg_key]["mentioned_client"]
        if not mentioned_client:
            logger.warning(f"[MENTIONS] Mentioned client not available for reply: {msg_key}")
            await cb.answer("❌ Akun yang disebut tidak tersedia.", show_alert=True)
            return

        # Simpan status menunggu input
        REPLY_AS_MENTIONED_WAITING[cb.message.id] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "mentioned_client": mentioned_client,
            "log_msg_id": cb.message.id,
            "user_id": cb.from_user.id if cb.from_user else None,
            "timestamp": time.time()
        }

        logger.info(f"[MENTIONS] Waiting for reply input for message {msg_key}, user: {cb.from_user.id if cb.from_user else 'unknown'}")

        await cb.message.reply_text(
            "🗨️ <b>Reply as Mentioned</b>\n\n"
            "Ketik pesan balasan Anda di bawah ini.\n"
            "Pesan ini akan dikirim sebagai akun yang disebut di grup asal.\n\n"
            "<i>Note: Balas pesan ini dengan teks yang ingin dikirim.</i>",
            reply_parameters=ReplyParameters(
                message_id=cb.message.id,
                chat_id=cb.message.chat.id
            )
        )
        await cb.answer("Silakan ketik balasan Anda.", show_alert=False)

    except Exception as e:
        logger.error(f"[MENTIONS] Error in start_reply_as_mentioned: {e}", exc_info=True)
        Altruix.log(f"[ERROR] Error in start_reply_as_mentioned: {e}", level=40)
        await cb.answer("❌ Terjadi kesalahan.", show_alert=True)


# 🔥 BARU: Handler untuk menerima input balasan
@Altruix.bot.on_message(filters.chat(Altruix.log_chat) & filters.reply & ~filters.user(Altruix.bot_info.id))
@log_errors
async def handle_reply_as_mentioned_input(c: Client, m: RawMessage):
    """Menangani input balasan untuk reply-as-mentioned."""
    if not m.reply_to_message:
        return

    reply_msg_id = m.reply_to_message.id
    if reply_msg_id not in REPLY_AS_MENTIONED_WAITING:
        return

    data = REPLY_AS_MENTIONED_WAITING[reply_msg_id]
    chat_id = data["chat_id"]
    message_id = data["message_id"]
    mentioned_client = data["mentioned_client"]
    
    logger.info(f"[MENTIONS] Received reply input for message {chat_id}_{message_id}, user: {m.from_user.id if m.from_user else 'unknown'}")

    # Kirim pesan konfirmasi
    confirm_buttons = [
        [InlineKeyboardButton("✅ Yes, Send", callback_data=f"confirm_reply_{reply_msg_id}")],
        [InlineKeyboardButton("❌ No, Cancel", callback_data=f"cancel_reply_{reply_msg_id}")]
    ]
    
    reply_text = m.text or m.caption or ""
    if not reply_text.strip():
        await m.reply_text(
            "❌ <b>Pesan kosong</b>\n\n"
            "Silakan ketik pesan yang ingin dikirim.",
            reply_parameters=ReplyParameters(
                message_id=m.id,
                chat_id=m.chat.id
            )
        )
        return
    
    confirm_msg = (
        f"⚠️ <b>Konfirmasi Kirim Balasan</b>\n\n"
        f"Anda akan mengirim pesan berikut sebagai akun yang disebut:\n\n"
        f"<blockquote>{html.escape(reply_text[:500])}</blockquote>\n\n"
        f"<b>Detail:</b>\n"
        f"• <b>Group ID:</b> <code>{chat_id}</code>\n"
        f"• <b>Message ID:</b> <code>{message_id}</code>\n"
        f"• <b>Akun Pengirim:</b> {mentioned_client.me.first_name if mentioned_client.me else 'Unknown'}\n\n"
        f"Apakah Anda yakin?"
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

    # Simpan teks balasan
    REPLY_AS_MENTIONED_WAITING[reply_msg_id]["reply_text"] = reply_text
    REPLY_AS_MENTIONED_WAITING[reply_msg_id]["user_msg_id"] = m.id
    REPLY_AS_MENTIONED_WAITING[reply_msg_id]["input_time"] = time.time()
    
    logger.info(f"[MENTIONS] Waiting for confirmation for reply to {chat_id}_{message_id}")


# 🔥 BARU: Handler konfirmasi kirim
@Altruix.bot.on_callback_query(filters.regex(r"confirm_reply_(\d+)"))
@log_errors
async def confirm_send_reply(c: Client, cb):
    """Mengirim balasan setelah konfirmasi."""
    try:
        reply_msg_id = int(cb.data.split("_")[2])
        if reply_msg_id not in REPLY_AS_MENTIONED_WAITING:
            logger.warning(f"[MENTIONS] Reply data not found for confirmation: {reply_msg_id}")
            await cb.answer("❌ Data tidak ditemukan.", show_alert=True)
            return

        data = REPLY_AS_MENTIONED_WAITING[reply_msg_id]
        chat_id = data["chat_id"]
        message_id = data["message_id"]
        mentioned_client = data["mentioned_client"]
        reply_text = data["reply_text"]
        user_msg_id = data["user_msg_id"]
        
        logger.info(f"[MENTIONS] Sending reply to {chat_id}_{message_id}, text length: {len(reply_text)}")

        # Kirim balasan dari akun yang disebut
        try:
            await mentioned_client.send_message(
                chat_id,
                reply_text,
                reply_to_message_id=message_id
            )
            logger.info(f"[MENTIONS] Successfully sent reply to {chat_id}_{message_id}")
        except Exception as send_err:
            logger.error(f"[MENTIONS] Failed to send reply: {send_err}")
            await cb.message.edit_text(
                f"❌ <b>Gagal mengirim balasan:</b>\n<code>{html.escape(str(send_err)[:200])}</code>",
                parse_mode=enums.ParseMode.HTML
            )
            await cb.answer("❌ Gagal mengirim.", show_alert=True)
            return

        await cb.message.edit_text("✅ <b>Balasan berhasil dikirim!</b>", parse_mode=enums.ParseMode.HTML)
        
        # Hapus input user
        try:
            await Altruix.bot.delete_messages(Altruix.log_chat, user_msg_id)
            logger.debug(f"[MENTIONS] Deleted user input message: {user_msg_id}")
        except Exception as delete_err:
            logger.warning(f"[MENTIONS] Could not delete user message: {delete_err}")

        # Bersihkan waiting list
        REPLY_AS_MENTIONED_WAITING.pop(reply_msg_id, None)
        logger.info(f"[MENTIONS] Completed reply process for {chat_id}_{message_id}")
        
        await cb.answer("✅ Balasan terkirim!", show_alert=False)

    except Exception as e:
        logger.error(f"[MENTIONS] Error in confirm_send_reply: {e}", exc_info=True)
        Altruix.log(f"[ERROR] Gagal kirim reply-as-mentioned: {e}", level=40)
        await cb.message.edit_text("❌ <b>Gagal mengirim balasan.</b>", parse_mode=enums.ParseMode.HTML)
        await cb.answer("❌ Gagal mengirim.", show_alert=True)


# 🔥 BARU: Handler pembatalan
@Altruix.bot.on_callback_query(filters.regex(r"cancel_reply_(\d+)"))
@log_errors
async def cancel_send_reply(c: Client, cb):
    """Membatalkan pengiriman balasan."""
    try:
        reply_msg_id = int(cb.data.split("_")[2])
        if reply_msg_id in REPLY_AS_MENTIONED_WAITING:
            data = REPLY_AS_MENTIONED_WAITING[reply_msg_id]
            user_msg_id = data.get("user_msg_id")
            
            logger.info(f"[MENTIONS] Cancelling reply process for {reply_msg_id}")
            
            try:
                await Altruix.bot.delete_messages(Altruix.log_chat, user_msg_id)
                logger.debug(f"[MENTIONS] Deleted user input on cancel: {user_msg_id}")
            except Exception as delete_err:
                logger.warning(f"[MENTIONS] Could not delete user message on cancel: {delete_err}")
            
            REPLY_AS_MENTIONED_WAITING.pop(reply_msg_id, None)
            await cb.message.edit_text("❌ <b>Pengiriman dibatalkan.</b>", parse_mode=enums.ParseMode.HTML)
            await cb.answer("❌ Dibatalkan.", show_alert=True)
        else:
            logger.warning(f"[MENTIONS] No reply process found to cancel: {reply_msg_id}")
            await cb.answer("❌ Tidak ada proses yang berjalan.", show_alert=True)
    except Exception as e:
        logger.error(f"[MENTIONS] Error in cancel_send_reply: {e}")
        await cb.answer("❌ Terjadi kesalahan.", show_alert=True)


# 🔥 BARU: Handler untuk quick reaction
@Altruix.bot.on_callback_query(filters.regex(r"react_mention_(\d+)_(\d+)_(.+)"))
@log_errors
async def quick_reaction_handler(c: Client, cb):
    """Kirim reaksi ke pesan asli di grup menggunakan akun userbot yang disebut."""
    try:
        chat_id = int(cb.data.split("_")[2])
        message_id = int(cb.data.split("_")[3])
        emoji = cb.data.split("_")[4]
        
        msg_key = f"{chat_id}_{message_id}"
        
        logger.info(f"[MENTIONS] Quick reaction requested: {msg_key} with emoji {emoji}")

        # Ambil client yang disebut dari cache
        if msg_key not in MENTION_LOG_CACHE:
            logger.warning(f"[MENTIONS] Mention not in cache for reaction: {msg_key}")
            await cb.answer("❌ Mention tidak ditemukan.", show_alert=True)
            return

        userbot_client = MENTION_LOG_CACHE[msg_key]["mentioned_client"]
        if not userbot_client:
            logger.warning(f"[MENTIONS] Mentioned client not available for reaction: {msg_key}")
            await cb.answer("❌ Akun yang disebut tidak tersedia.", show_alert=True)
            return

        try:
            await userbot_client.send_reaction(chat_id, message_id, emoji)
            logger.info(f"[MENTIONS] Successfully sent reaction {emoji} to {msg_key}")
            await cb.answer(f"✅ Bereaksi dengan {emoji}", show_alert=False)
        except Exception as react_err:
            logger.error(f"[MENTIONS] Failed to send reaction: {react_err}")
            Altruix.log(f"[ERROR] Gagal kirim reaksi: {react_err}", level=40)
            await cb.answer("❌ Gagal mengirim reaksi.", show_alert=True)

    except Exception as e:
        logger.error(f"[MENTIONS] Error in quick_reaction_handler: {e}", exc_info=True)
        Altruix.log(f"[ERROR] Error in quick_reaction_handler: {e}", level=40)
        await cb.answer("❌ Terjadi kesalahan.", show_alert=True)


# 🔥 PERBAIKAN: Cleanup task untuk bersihkan cache dan waiting list lama
async def cleanup_old_entries():
    """Bersihkan cache dan waiting list yang sudah lama."""
    while True:
        try:
            current_time = time.time()
            
            # Bersihkan MENTION_LOG_CACHE yang lebih dari 1 jam
            expired_keys = []
            for key, data in MENTION_LOG_CACHE.items():
                if current_time - data.get("timestamp", 0) > 3600:  # 1 jam
                    expired_keys.append(key)
            
            for key in expired_keys:
                del MENTION_LOG_CACHE[key]
            
            if expired_keys:
                logger.debug(f"[MENTIONS] Cleaned {len(expired_keys)} expired cache entries")
            
            # Bersihkan REPLY_AS_MENTIONED_WAITING yang lebih dari 30 menit
            expired_waiting = []
            for key, data in REPLY_AS_MENTIONED_WAITING.items():
                if current_time - data.get("timestamp", 0) > 1800:  # 30 menit
                    expired_waiting.append(key)
            
            for key in expired_waiting:
                del REPLY_AS_MENTIONED_WAITING[key]
            
            if expired_waiting:
                logger.debug(f"[MENTIONS] Cleaned {len(expired_waiting)} expired waiting entries")
                
        except Exception as e:
            logger.error(f"[MENTIONS] Error in cleanup task: {e}")
        
        await asyncio.sleep(300)  # Run every 5 minutes

# 🔥 PERBAIKAN: Start cleanup task ketika plugin load
try:
    asyncio.create_task(cleanup_old_entries())
    logger.info(f"[MENTIONS] Started cleanup task for cache management")
except Exception as e:
    logger.warning(f"[MENTIONS] Could not start cleanup task: {e}")

# Log sukses loading
try:
    Altruix.log(f"[DEBUG] Loaded → {__plugin_name__} {PLUGIN_VERSION}", level=20)
    logger.info(f"[MENTIONS] Plugin loaded successfully! Version: {PLUGIN_VERSION}")
    logger.info(f"[MENTIONS] Features: Mention detection, Edit detection, Quick reaction, Reply-as-mentioned")
except Exception as e:
    logger.info(f"[DEBUG] Loaded → {__plugin_name__} {PLUGIN_VERSION}")
