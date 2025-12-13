# mentions.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under theGNU v3.0 License Agreement.
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
PLUGIN_VERSION = "0.1.1.6"  # 🔥 PERBAIKAN: Versi dengan fix datetime error
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
        # 🔥 PERBAIKAN KRITIS: Gunakan metode database Altruix yang benar
        setting_key = f"MENTION_LOG_{c.me.id}"
        
        db_success = False
        
        try:
            # Cek jika settings_col tersedia
            if hasattr(Altruix.db, 'settings_col'):
                # 🔥 PERBAIKAN: Gunakan time.time() untuk timestamp integer
                current_timestamp = int(time.time())
                
                await Altruix.db.settings_col.update_one(
                    {"_id": setting_key},
                    {"$set": {
                        "value": value, 
                        "client_id": c.me.id, 
                        "client_name": c.me.first_name or c.me.username,
                        "updated_at": current_timestamp,  # 🔥 INTEGER timestamp
                        "plugin": "mentions"
                    }},
                    upsert=True
                )
                db_success = True
                logger.info(f"[MENTIONS] Setting saved via settings_col: {setting_key}")
                
            else:
                logger.warning(f"[MENTIONS] settings_col not found, using config-only")
                db_success = False
                
        except Exception as db_err:
            logger.error(f"[MENTIONS] Database error: {db_err}")
            db_success = False
        
        # 🔥 PERBAIKAN: Selalu simpan di config untuk akses cepat
        if not hasattr(Altruix.config, "mention_settings"):
            Altruix.config.mention_settings = {}
        Altruix.config.mention_settings[c.me.id] = value
        
        # 🔥 PERBAIKAN: Hapus data lama untuk menghindari conflict
        try:
            if hasattr(Altruix.db, 'settings_col'):
                # 🔥 PERBAIKAN: Cek dulu sebelum delete
                old_data = await Altruix.db.settings_col.find_one({"_id": "MENTION_LOG"})
                if old_data:
                    # 🔥 PERBAIKAN: Cek tipe data updated_at sebelum migrasi
                    old_updated_at = old_data.get("updated_at")
                    if isinstance(old_updated_at, datetime):
                        # Konversi datetime ke timestamp jika perlu
                        migrate_timestamp = int(old_updated_at.timestamp())
                    elif isinstance(old_updated_at, (int, float)):
                        migrate_timestamp = int(old_updated_at)
                    else:
                        migrate_timestamp = int(time.time())
                    
                    # Migrasi data ke format baru
                    await Altruix.db.settings_col.update_one(
                        {"_id": setting_key},
                        {"$set": {
                            "value": old_data.get("value", False),
                            "client_id": c.me.id,
                            "migrated_from": "MENTION_LOG",
                            "updated_at": migrate_timestamp,
                            "old_data": old_data
                        }},
                        upsert=True
                    )
                    
                    # Hapus data lama
                    await Altruix.db.settings_col.delete_one({"_id": "MENTION_LOG"})
                    logger.info(f"[MENTIONS] Migrated and deleted old setting: MENTION_LOG")
        except Exception as delete_err:
            logger.debug(f"[MENTIONS] Could not migrate old setting: {delete_err}")
        
        logger.info(f"[MENTIONS] Setting {'saved to DB' if db_success else 'saved to config only'}: {setting_key} = {value}")
        
        # 🔥 PERBAIKAN: Kirim pesan sukses
        if db_success:
            success_msg = f"✅ Mention notifications {'ENABLED' if value else 'DISABLED'} for this userbot"
        else:
            success_msg = f"⚠️ Mention notifications {'ENABLED' if value else 'DISABLED'} (config only)"
        
        await msg.edit_msg(success_msg)
        
    except Exception as e:
        error_detail = str(e)
        Altruix.log(f"[ERROR] Gagal menyimpan setting mention: {error_detail}", level=40)
        
        try:
            if not hasattr(Altruix.config, "mention_settings"):
                Altruix.config.mention_settings = {}
            Altruix.config.mention_settings[c.me.id] = value
            
            error_msg = f"⚠️ Setting saved to config only"
        except:
            error_msg = f"❌ Failed to save setting"
        
        await msg.edit_msg(error_msg)
        return


@Altruix.on_message(
    filters.mentioned & filters.group & ~filters.user(Altruix.bot_info.id)
)
@log_errors
async def send_mention_log_handler(c: Client, m: RawMessage):
    """Handler utama untuk menangkap mention dan mengirim notifikasi ke LOG_CHAT."""
    try:
        # 🔥 PERBAIKAN: Gunakan format key yang sama
        setting_key = f"MENTION_LOG_{c.me.id}"
        
        # 🔥 PERBAIKAN: Cek dulu di config cache
        if hasattr(Altruix.config, "mention_settings") and c.me.id in Altruix.config.mention_settings:
            is_enabled = Altruix.config.mention_settings[c.me.id]
            logger.debug(f"[MENTIONS] Setting from cache: {is_enabled}")
        else:
            # 🔥 PERBAIKAN: Baca dari database dengan handling datetime error
            is_enabled = False
            
            try:
                if hasattr(Altruix.db, 'settings_col'):
                    db_res = await Altruix.db.settings_col.find_one({"_id": setting_key})
                    
                    if db_res:
                        # 🔥 PERBAIKAN UTAMA: Handle datetime conversion error
                        try:
                            # Coba ambil value
                            is_enabled = db_res.get("value", False)
                            
                            # 🔥 PERBAIKAN: Cek dan fix tipe data updated_at jika perlu
                            updated_at = db_res.get("updated_at")
                            if isinstance(updated_at, datetime):
                                # Konversi datetime ke timestamp
                                fixed_timestamp = int(updated_at.timestamp())
                                await Altruix.db.settings_col.update_one(
                                    {"_id": setting_key},
                                    {"$set": {"updated_at": fixed_timestamp}}
                                )
                                logger.info(f"[MENTIONS] Fixed datetime in DB for: {setting_key}")
                                
                        except Exception as fix_err:
                            logger.warning(f"[MENTIONS] Error fixing datetime: {fix_err}")
                            is_enabled = db_res.get("value", False) if 'value' in db_res else False
                        
                        logger.debug(f"[MENTIONS] Found in settings_col: {is_enabled}")
                    else:
                        # Coba cari data lama
                        db_res_old = await Altruix.db.settings_col.find_one({"_id": "MENTION_LOG"})
                        if db_res_old:
                            is_enabled = db_res_old.get("value", False)
                            logger.debug(f"[MENTIONS] Found old setting: {is_enabled}")
                            
                            # 🔥 PERBAIKAN: Migrasi dengan handling datetime
                            try:
                                old_updated_at = db_res_old.get("updated_at")
                                if isinstance(old_updated_at, datetime):
                                    migrate_timestamp = int(old_updated_at.timestamp())
                                elif isinstance(old_updated_at, (int, float)):
                                    migrate_timestamp = int(old_updated_at)
                                else:
                                    migrate_timestamp = int(time.time())
                                
                                await Altruix.db.settings_col.update_one(
                                    {"_id": setting_key},
                                    {"$set": {
                                        "value": is_enabled,
                                        "client_id": c.me.id,
                                        "migrated_from": "MENTION_LOG",
                                        "updated_at": migrate_timestamp
                                    }},
                                    upsert=True
                                )
                                logger.info(f"[MENTIONS] Migrated old setting to: {setting_key}")
                            except Exception as migrate_err:
                                logger.warning(f"[MENTIONS] Migration failed: {migrate_err}")
                
            except Exception as db_err:
                logger.error(f"[MENTIONS] DB read error: {db_err}")
                is_enabled = False
            
            # Update cache
            if not hasattr(Altruix.config, "mention_settings"):
                Altruix.config.mention_settings = {}
            Altruix.config.mention_settings[c.me.id] = is_enabled
        
        # Jika mention log tidak diaktifkan, return
        if not is_enabled:
            logger.debug(f"[MENTIONS] Not enabled for client {c.me.id}")
            return

        logger.debug(f"[MENTIONS] Processing mention for client {c.me.id}")
        
        mentioner = m.from_user
        if not mentioner:
            return

        # Format hyperlink user
        mentioner_name = mentioner.first_name or "Unknown"
        mentioner_id = mentioner.id
        mentioner_link = f"tg://user?id={mentioner_id}"
        mentioner_hyperlink = f'<a href="{mentioner_link}">{mentioner_name}</a>'
        
        # Ambil isi pesan
        message_text = m.text or m.caption or "[No text content]"
        message_text = (
            message_text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

        # Format waktu lokal
        mention_time = datetime.fromtimestamp(m.date).strftime("%Y-%m-%d %H:%M:%S")

        # Bangun pesan notifikasi
        log_message = (
            f"🔔 <b>Mention Detected!</b>\n\n"
            f"👤 <b>Mentioned By:</b> {mentioner_hyperlink} (<code>{mentioner_id}</code>)\n"
            f"🤖 <b>My Account:</b> {c.me.mention(style=enums.ParseMode.HTML)}\n"
            f"💬 <b>Group:</b> {m.chat.title} (<code>{m.chat.id}</code>)\n"
            f"🕒 <b>Time:</b> <code>{mention_time}</code>\n"
            f"📄 <b>Message:</b>\n<blockquote>{message_text}</blockquote>"
        )

        # Tombol Quick Reaction
        reaction_buttons = [
            InlineKeyboardButton(emoji, callback_data=f"react_mention_{m.chat.id}_{m.id}_{emoji}")
            for emoji in DEFAULT_REACTION_EMOJIS
        ]
        reply_button = [InlineKeyboardButton("🗨️ Reply as Mentioned", callback_data=f"reply_as_mentioned_{m.chat.id}_{m.id}")]
        link_button = [InlineKeyboardButton("🔗 Go to Message", url=m.link)]
        
        # Deteksi pesan edit
        msg_key = f"{m.chat.id}_{m.id}"
        
        is_edited_message = hasattr(m, 'edit_date') and m.edit_date is not None
        
        if is_edited_message:
            log_message = (
                f"✏️ <b>Edited Mention Detected!</b>\n\n"
                f"👤 <b>Mentioned By:</b> {mentioner_hyperlink} (<code>{mentioner_id}</code>)\n"
                f"🤖 <b>My Account:</b> {c.me.mention(style=enums.ParseMode.HTML)}\n"
                f"💬 <b>Group:</b> {m.chat.title} (<code>{m.chat.id}</code>)\n"
                f"🕒 <b>Original Time:</b> <code>{mention_time}</code>\n"
                f"🕒 <b>Edited Time:</b> <code>{datetime.fromtimestamp(m.edit_date).strftime('%Y-%m-%d %H:%M:%S')}</code>\n"
                f"📄 <b>Edited Message:</b>\n<blockquote>{message_text}</blockquote>"
            )
            
            if msg_key in MENTION_LOG_CACHE:
                old_data = MENTION_LOG_CACHE[msg_key]
                try:
                    await Altruix.bot.edit_message_text(
                        chat_id=Altruix.log_chat,
                        message_id=old_data["log_msg_id"],
                        text=log_message,
                        parse_mode=enums.ParseMode.HTML,
                        disable_web_page_preview=True,
                        reply_markup=InlineKeyboardMarkup([reaction_buttons, reply_button, link_button])
                    )
                    MENTION_LOG_CACHE[msg_key]["text"] = message_text
                    MENTION_LOG_CACHE[msg_key]["is_edited"] = True
                    logger.debug(f"[MENTIONS] Updated edited mention: {msg_key}")
                    return
                except Exception as edit_err:
                    Altruix.log(f"[DEBUG] Gagal edit pesan log: {edit_err}", level=30)
        
        # Kirim notifikasi
        try:
            sent_log_msg = await Altruix.bot.send_message(
                Altruix.log_chat,
                log_message,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=InlineKeyboardMarkup([reaction_buttons, reply_button, link_button])
            )
            logger.debug(f"[MENTIONS] Sent mention log: {msg_key}")
        except Exception as send_err:
            Altruix.log(f"[ERROR] Gagal kirim notifikasi mention: {send_err}", level=40)
            return

        # Balas otomatis
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
                logger.debug(f"[MENTIONS] Sent auto-reply for: {msg_key}")
            except Exception as reply_err:
                Altruix.log(f"[DEBUG] Gagal kirim reply otomatis: {reply_err}", level=30)

        # Simpan ke cache
        MENTION_LOG_CACHE[msg_key] = {
            "text": message_text,
            "log_msg_id": sent_log_msg.id,
            "mentioned_client": c,
            "chat_id": m.chat.id,
            "message_id": m.id,
            "is_edited": is_edited_message
        }
        logger.debug(f"[MENTIONS] Cached mention: {msg_key}")

    except Exception as e:
        Altruix.log(f"[CRITICAL] Error in mention handler: {str(e)}", level=50)
        try:
            await Altruix.bot.send_message(
                Altruix.log_chat,
                f"⚠️ <b>Error in mention handler:</b>\n<code>{str(e)[:500]}</code>",
                parse_mode=enums.ParseMode.HTML
            )
        except:
            pass


# Handler untuk memulai proses reply-as-mentioned
@Altruix.bot.on_callback_query(filters.regex(r"reply_as_mentioned_(\d+)_(\d+)"))
@log_errors
async def start_reply_as_mentioned(c: Client, cb):
    """Memulai proses reply-as-mentioned dengan meminta input pesan."""
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
            "log_msg_id": cb.message.id
        }

        await cb.message.reply_text(
            "🗨️ <b>Reply as Mentioned</b>\n\n"
            "Ketik pesan balasan Anda di bawah ini.\n"
            "Pesan ini akan dikirim sebagai akun yang disebut di grup asal.",
            reply_parameters=ReplyParameters(
                message_id=cb.message.id,
                chat_id=cb.message.chat.id
            )
        )
        await cb.answer("Silakan ketik balasan Anda.", show_alert=False)

    except Exception as e:
        Altruix.log(f"[ERROR] Error in start_reply_as_mentioned: {e}", level=40)
        await cb.answer("❌ Terjadi kesalahan.", show_alert=True)


# Handler untuk menerima input balasan
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

    confirm_buttons = [
        [InlineKeyboardButton("✅ Yes, Send", callback_data=f"confirm_reply_{reply_msg_id}")],
        [InlineKeyboardButton("❌ No, Cancel", callback_data=f"cancel_reply_{reply_msg_id}")]
    ]
    confirm_msg = (
        f"⚠️ <b>Konfirmasi Kirim Balasan</b>\n\n"
        f"Anda akan mengirim pesan berikut sebagai akun yang disebut:\n\n"
        f"<blockquote>{m.text or m.caption or ''}</blockquote>\n\n"
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

    REPLY_AS_MENTIONED_WAITING[reply_msg_id]["reply_text"] = m.text or m.caption or ""
    REPLY_AS_MENTIONED_WAITING[reply_msg_id]["user_msg_id"] = m.id


# Handler konfirmasi kirim
@Altruix.bot.on_callback_query(filters.regex(r"confirm_reply_(\d+)"))
@log_errors
async def confirm_send_reply(c: Client, cb):
    """Mengirim balasan setelah konfirmasi."""
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
        Altruix.log(f"[ERROR] Gagal kirim reply-as-mentioned: {e}", level=40)
        await cb.message.edit_text("❌ <b>Gagal mengirim balasan.</b>", parse_mode=enums.ParseMode.HTML)
        await cb.answer("❌ Gagal mengirim.", show_alert=True)


# Handler pembatalan
@Altruix.bot.on_callback_query(filters.regex(r"cancel_reply_(\d+)"))
@log_errors
async def cancel_send_reply(c: Client, cb):
    """Membatalkan pengiriman balasan."""
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


# Handler untuk quick reaction
@Altruix.bot.on_callback_query(filters.regex(r"react_mention_(\d+)_(\d+)_(.+)"))
@log_errors
async def quick_reaction_handler(c: Client, cb):
    """Kirim reaksi ke pesan asli di grup menggunakan akun userbot yang disebut."""
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
            Altruix.log(f"[ERROR] Gagal kirim reaksi: {react_err}", level=40)
            await cb.answer("❌ Gagal mengirim reaksi.", show_alert=True)

    except Exception as e:
        Altruix.log(f"[ERROR] Error in quick_reaction_handler: {e}", level=40)
        await cb.answer("❌ Terjadi kesalahan.", show_alert=True)

# Log sukses loading
try:
    Altruix.log(f"[DEBUG] Loaded → {__plugin_name__} {PLUGIN_VERSION}", level=20)
except Exception as e:
    logger.info(f"[DEBUG] Loaded → {__plugin_name__} {PLUGIN_VERSION}")
