# Main/plugins/userbot/mentions.py
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
)
from datetime import datetime
from Main.core.decorators import log_errors
from Main.utils.compatibility import smart_send
import os
import logging

plugin_name = f"plugins/userbot/{os.path.basename(__file__)}"
__plugin_name__ = plugin_name if plugin_name else "mentions"
PLUGIN_VERSION = "0.1.1.1"  # 🔥 Versi terbaru dengan smart_send dan error handling optimal
logger = logging.getLogger(f"{__plugin_name__}")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - [SET PLUGIN] - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# 🔥 TAMBAHAN: Cache untuk lacak pesan mention yang sudah dikirim → update, bukan kirim baru
MENTION_LOG_CACHE = {}

# 🔥 TAMBAHAN: Emoji default untuk quick reaction
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
        await Altruix.db.settings_col.update_one(
            {"_id": "MENTION_LOG", "client_id": c.me.id},
            {"$set": {"value": value}},
            upsert=True,
        )
    except Exception as e:
        Altruix.log(f"[ERROR] Gagal menyimpan setting mention: {e}", level=40)
        await msg.edit_msg("FAILED_TO_SAVE_SETTING")


@Altruix.on_message(
    filters.mentioned & filters.group & ~filters.user(Altruix.bot_info.id)
)
@log_errors
async def send_mention_log_handler(c: Client, m: RawMessage):
    """Handler utama untuk menangkap mention dan mengirim notifikasi ke LOG_CHAT."""
    try:
        db_res = await Altruix.db.settings_col.find_one(
            {"_id": "MENTION_LOG", "client_id": c.me.id}
        )
        if not (db_res and db_res.get("value", False)):
            return

        mentioner = m.from_user
        if not mentioner:
            return  # Abaikan jika mention dari channel anonim

        # Format hyperlink user yang klikable di semua platform
        mentioner_name = mentioner.first_name or "Unknown"
        mentioner_id = mentioner.id
        mentioner_link = f"tg://user?id={mentioner_id}"
        mentioner_hyperlink = f'<a href="{mentioner_link}">{mentioner_name}</a>'
        
        # Ambil dan amankan isi pesan
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

        # 🔥 TOMBOL: Quick reaction + reply as mentioned + link
        reaction_buttons = [
            InlineKeyboardButton(emoji, callback_data=f"react_mention_{m.chat.id}_{m.id}_{emoji}")
            for emoji in DEFAULT_REACTION_EMOJIS
        ]
        reply_button = [InlineKeyboardButton("🗨️ Reply as Mentioned", callback_data=f"reply_as_mentioned_{m.chat.id}_{m.id}")]
        link_button = [InlineKeyboardButton("🔗 Go to Message", url=m.link)]

        # 🔥 KIRIM ATAU UPDATE NOTIFIKASI
        msg_key = f"{m.chat.id}_{m.id}"
        if msg_key in MENTION_LOG_CACHE:
            try:
                old_log_msg_id = MENTION_LOG_CACHE[msg_key]["log_msg_id"]
                edited_log = log_message.replace(
                    "🔔 <b>Mention Detected!</b>",
                    "✏️ <b>Edited Mention!</b>\n<i>Original mention was modified.</i>"
                )
                await Altruix.bot.edit_message_text(
                    Altruix.log_chat,
                    old_log_msg_id,
                    edited_log,
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup([reaction_buttons, reply_button, link_button]),
                    disable_web_page_preview=True
                )
                MENTION_LOG_CACHE[msg_key]["text"] = message_text
                return
            except Exception as edit_err:
                Altruix.log(f"[DEBUG] Gagal edit notifikasi mention: {edit_err}", level=30)
                pass

        try:
            sent_log_msg = await Altruix.bot.send_message(
                Altruix.log_chat,
                log_message,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=InlineKeyboardMarkup([reaction_buttons, reply_button, link_button])
            )
            MENTION_LOG_CACHE[msg_key] = {
                "text": message_text,
                "log_msg_id": sent_log_msg.id,
                "mentioned_client": c,  # Simpan client yang disebut
                "chat_id": m.chat.id,
                "message_id": m.id
            }
        except Exception as send_err:
            Altruix.log(f"[ERROR] Gagal kirim notifikasi mention: {send_err}", level=40)
            return

        # 🔥 BALAS OTOMATIS DARI USERBOT YANG DI-MENTION
        try:
            await c.send_message(
                Altruix.log_chat,
                "💬 Saya yang disebut di atas.",
                reply_to_message_id=sent_log_msg.id
            )
        except Exception as reply_err:
            Altruix.log(f"[DEBUG] Gagal kirim reply otomatis: {reply_err}", level=30)

    except Exception as e:
        Altruix.log(f"[CRITICAL] Error in mention handler: {e}", level=50)
        try:
            await Altruix.bot.send_message(
                Altruix.log_chat,
                f"⚠️ <b>Error in mention handler:</b>\n<code>{str(e)}</code>",
                parse_mode=enums.ParseMode.HTML
            )
        except:
            pass


# 🔥 BARU: Handler untuk memulai proses reply-as-mentioned
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

        # Simpan status menunggu input
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
            reply_to_message_id=cb.message.id
        )
        await cb.answer("Silakan ketik balasan Anda.", show_alert=False)

    except Exception as e:
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

    # Kirim pesan konfirmasi
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
        reply_markup=InlineKeyboardMarkup(confirm_buttons)
    )

    # Simpan teks balasan
    REPLY_AS_MENTIONED_WAITING[reply_msg_id]["reply_text"] = m.text or m.caption or ""
    REPLY_AS_MENTIONED_WAITING[reply_msg_id]["user_msg_id"] = m.id


# 🔥 BARU: Handler konfirmasi kirim
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

        # Kirim balasan dari akun yang disebut
        await mentioned_client.send_message(
            chat_id,
            reply_text,
            reply_to_message_id=message_id
        )

        await cb.message.edit_text("✅ <b>Balasan berhasil dikirim!</b>", parse_mode=enums.ParseMode.HTML)
        # Hapus input user
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


# 🔥 BARU: Handler pembatalan
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


# 🔥 BARU: Handler untuk quick reaction
@Altruix.bot.on_callback_query(filters.regex(r"react_mention_(\d+)_(\d+)_(.+)"))
@log_errors
async def quick_reaction_handler(c: Client, cb):
    """Kirim reaksi ke pesan asli di grup menggunakan akun userbot yang disebut."""
    try:
        chat_id = int(cb.data.split("_")[2])
        message_id = int(cb.data.split("_")[3])
        emoji = cb.data.split("_")[4]

        # Ambil client yang disebut dari cache
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


# 🔥 BARU: Deteksi edit pesan mention → trigger ulang handler utama
@Altruix.on_edited_message(
    filters.mentioned & filters.group & ~filters.user(Altruix.bot_info.id)
)
@log_errors
async def edited_mention_handler(c: Client, m: RawMessage):
    """Trigger ulang handler utama saat pesan mention diedit."""
    await send_mention_log_handler(c, m)

# Log sukses loading
try:
    Altruix.log(f"[DEBUG] Loaded → {__plugin_name__} {PLUGIN_VERSION}", level=20)
except Exception as e:
    logger.info(f"[DEBUG] Loaded → {__plugin_name__} {PLUGIN_VERSION}")
