# Copyright (C) 2021-present by Altruix@Github, <https://github.com/Altruix>
#
# This file is part of <https://github.com/Altruix/Altruix> project,
# and is released under the "GNU v3.0 License Agreement".
# Please see <https://github.com/Altriux/Altruix/blob/main/LICENSE>
#
# All rights reserved.

import asyncio
import logging
import os
import html
import contextlib
from Main import Altruix
from pyrogram.enums import ParseMode
from pyrogram import enums
from pyrogram import Client, filters
from Main.core.decorators import log_errors
from pyrogram.types import (
    Message, ForceReply, CallbackQuery, KeyboardButton, ReplyKeyboardMarkup,
    ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton, LinkPreviewOptions
)
from pyrogram.errors import (
    FloodWait, ApiIdInvalid, UsernameInvalid, PhoneCodeExpired,
    PhoneCodeInvalid, UsernameOccupied, PhoneNumberInvalid,
    UsernameNotModified, SessionPasswordNeeded, UserIsBlocked, PeerIdInvalid
)


# 🔒 TRACK PROSES AKTIF PER USER — CEGAH DUPLIKASI
_ACTIVE_ADD_SESSION = set()


async def client_session(api_id, api_hash):
    """Buat klien sementara untuk generate session string."""
    return Client("new_session", api_id=int(api_id), api_hash=str(api_hash), in_memory=True)


# ─── UTIL: Kirim log ke grup (dengan fallback ke OWNER_ID) ─────────────
async def log_to_group(text: str):
    """Kirim notifikasi ke LOG_CHAT_ID atau OWNER_ID jika gagal."""
    log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_USERS_ID))
    try:
        await Altruix.bot.send_message(
            log_chat_id,
            text,
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
    except Exception:
        pass  # Gagal log? abaikan


# ─── HANDLER UTAMA: Tekan "No" di menu /add ─────────────────────────────
@Altruix.bot.on_callback_query(filters.regex("^session_no$"))
@log_errors
async def add_session_cb_handler(_, cb: CallbackQuery):
    user = cb.from_user
    user_id = user.id

    # ✅ PERIKSA IZIN: menggunakan helper is_sudo yang mendukung DB
    if not await Altruix.is_sudo(user_id):
        return await cb.answer("⛔ Anda tidak diizinkan menambah session.", show_alert=True)

    # ✅ PERBAIKAN UTAMA: JANGAN GUNAKAN ReplyKeyboardMarkup DI GRUP!
    if cb.message.chat.type in ["group", "supergroup"]:
        await cb.answer()
        # Beri tahu di grup untuk lanjut di PM
        await cb.message.reply(
            "🔐 Proses pembuatan session hanya bisa di **chat pribadi** dengan bot.\n"
            "Silakan kirim /start ke bot, lalu tekan **Add Session** di sana.",
            quote=True
        )
        # Kirim tombol ke PM user
        try:
            await Altruix.bot.send_message(
                user_id,
                "Anda memulai proses dari grup.\nKlik tombol di bawah untuk memulai:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("✅ Mulai Buat Session", callback_data="make_session_start")
                ]])
            )
            await cb.message.reply("💬 Pesan dikirim ke chat pribadi Anda.", quote=True)
        except (UserIsBlocked, PeerIdInvalid):
            await cb.message.reply(
                f"❌ Gagal kirim ke PM. Pastikan Anda sudah chat dengan bot (@{Altruix.bot.me.username}).",
                quote=True
            )
        return  # ← PENTING: JANGAN LANJUTKAN DI GRUP!

    # Jika di PM, langsung mulai proses
    await _start_add_session_process(cb)


# ─── HANDLER DI PM: Mulai proses setelah redirect dari grup ────────────
@Altruix.bot.on_callback_query(filters.regex("^make_session_start$"))
@log_errors
async def make_session_start_handler(_, cb: CallbackQuery):
    if not await Altruix.is_sudo(cb.from_user.id):
        return await cb.answer("⛔ Tidak diizinkan.", show_alert=True)
    await cb.answer()
    await _start_add_session_process(cb)


# ─── FUNGSI UTAMA: Alur pembuatan session ──────────────────────────────
async def _start_add_session_process(cb: CallbackQuery):
    user = cb.from_user
    user_id = user.id
    bot = Altruix.bot  # ✅ Gunakan bot sebagai client
    is_sudo = user_id != Altruix.config.OWNER_USERS_ID

    # ✅ Log ke grup jika sudo user memulai proses
    if is_sudo:
        await log_to_group(
            f"<blockquote expandable>"
            f"👮‍♂️ <b>Sudo User Memulai Generate Session</b>\n"
            f"• Nama: {user.first_name} {user.last_name or ''}\n"
            f"• ID: <code>{user_id}</code>"
            f"</blockquote>"
        )

    if user_id in _ACTIVE_ADD_SESSION:
        return await cb.answer("❗ Proses sudah berjalan. Tunggu atau batalkan yang sebelumnya.", show_alert=True)

    _ACTIVE_ADD_SESSION.add(user_id)

    # ✅ KIRIM PESAN VIA BOT (BUKAN VIA USER) — AMAN DI PM!
    try:
        temp_msg = await bot.send_message(
            chat_id=user_id,
            text="📲 Kirim kontak Anda untuk ambil nomor telepon.\n"
                 "<i>Data tidak disimpan — hanya untuk buat session.</i>\n\n"
                 "Ketik /cancel untuk batalkan.",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("Share Contact", request_contact=True)]],
                resize_keyboard=True,
                one_time_keyboard=True,
            ),
        )
    except Exception as e:
        Altruix.log(f"Gagal kirim pesan ke {user_id}: {e}", level=logging.ERROR)
        _ACTIVE_ADD_SESSION.discard(user_id)
        await cb.message.edit("❌ Gagal memulai proses.")
        return

    phone_number = None
    try:
        # ✅ DENGARKAN RESPON VIA BOT — DENGAN FILTER YANG BENAR
        # Pyromod: listen(filters=..., timeout=...)
        while True:
            response: Message = await bot.listen(
                filters=filters.user(user_id),
                timeout=120
            )
            if response.contact:
                phone_number = response.contact.phone_number
                break
            elif response.text and response.text.strip().lower() == "/cancel":
                await temp_msg.delete()
                await bot.send_message(user_id, "❌ Dibatalkan.", reply_markup=ReplyKeyboardRemove())
                _ACTIVE_ADD_SESSION.discard(user_id)
                return
            else:
                await bot.send_message(user_id, "❌ Harap kirim kontak atau ketik /cancel.")
    except asyncio.TimeoutError:
        await temp_msg.delete()
        await bot.send_message(user_id, "⏰ Waktu habis.", reply_markup=ReplyKeyboardRemove())
        _ACTIVE_ADD_SESSION.discard(user_id)
        return
    except Exception as e:
        Altruix.log(f"Error tunggu input: {e}", level=logging.ERROR)
        await log_to_group(
            f"<blockquote expandable>"
            f"⚠️ <b>ERROR SAAT TUNGGU INPUT</b>\n"
            f"• User ID: <code>{user_id}</code>\n"
            f"• Error: <code>{str(e)}</code>"
            f"</blockquote>"
        )
        _ACTIVE_ADD_SESSION.discard(user_id)
        await bot.send_message(user_id, "❌ Kesalahan internal.")
        return

    await bot.send_message(user_id, "📞 Nomor diterima. Membuat session...", reply_markup=ReplyKeyboardRemove())
    process_msg = await bot.send_message(user_id, "<i>Mohon tunggu...</i>")

    # Buat klien sementara
    try:
        app = await client_session(Altruix.config.API_ID, Altruix.config.API_HASH)
        await app.connect()
        sent_code = await app.send_code(phone_number)
    except FloodWait as e:
        await process_msg.edit(f"⏳ FloodWait! Tunggu {e.value} detik.")
        await app.disconnect()
        _ACTIVE_ADD_SESSION.discard(user_id)
        return
    except PhoneNumberInvalid:
        await process_msg.edit("❌ Nomor telepon tidak valid.")
        await app.disconnect()
        _ACTIVE_ADD_SESSION.discard(user_id)
        return
    except ApiIdInvalid:
        await process_msg.edit("❌ API ID/Hash tidak valid.")
        await app.disconnect()
        _ACTIVE_ADD_SESSION.discard(user_id)
        return
    except Exception as e:
        await process_msg.edit("❌ Gagal kirim kode OTP.")
        Altruix.log(f"Kirim kode error: {e}", level=logging.ERROR)
        await log_to_group(
            f"<blockquote expandable>"
            f"⚠️ <b>ERROR SAAT KIRIM KODE OTP</b>\n"
            f"• User ID: <code>{user_id}</code>\n"
            f"• Error: <code>{str(e)}</code>"
            f"</blockquote>"
        )
        await app.disconnect()
        _ACTIVE_ADD_SESSION.discard(user_id)
        return

    # Minta kode OTP
    try:
        ans = await bot.ask(
            chat_id=user_id,
            text="🔑 Kirim kode OTP format <code>1-2-3-4-5</code>",
            reply_markup=ForceReply(selective=True),
            timeout=300,
            filters=filters.user(user_id)
        )
        if ans.text and ans.text.strip().lower() == "/cancel":
            await process_msg.edit("❌ Dibatalkan oleh user.")
            await app.disconnect()
            _ACTIVE_ADD_SESSION.discard(user_id)
            return
        code = ans.text.replace("-", "").replace(" ", "")
        await app.sign_in(phone_number, sent_code.phone_code_hash, code)
    except SessionPasswordNeeded:
        try:
            ans2 = await bot.ask(
                chat_id=user_id,
                text="🔐 Masukkan password 2FA:",
                reply_markup=ForceReply(selective=True),
                timeout=300,
                filters=filters.user(user_id)
            )
            if ans2.text.strip().lower() == "/cancel":
                await process_msg.edit("❌ Dibatalkan.")
                await app.disconnect()
                _ACTIVE_ADD_SESSION.discard(user_id)
                return
            await app.check_password(ans2.text)
        except Exception as e:
            await process_msg.edit("❌ Password salah atau error.")
            Altruix.log(f"2FA error: {e}", level=logging.ERROR)
            await log_to_group(
                f"<blockquote expandable>"
                f"⚠️ <b>ERROR 2FA</b>\n"
                f"• User ID: <code>{user_id}</code>\n"
                f"• Error: <code>{str(e)}</code>"
                f"</blockquote>"
            )
            await app.disconnect()
            _ACTIVE_ADD_SESSION.discard(user_id)
            return
    except (PhoneCodeInvalid, PhoneCodeExpired):
        await process_msg.edit("❌ Kode OTP salah/kadaluarsa.")
        await app.disconnect()
        _ACTIVE_ADD_SESSION.discard(user_id)
        return
    except Exception as e:
        await process_msg.edit("❌ Gagal login.")
        Altruix.log(f"Sign-in error: {e}", level=logging.ERROR)
        await log_to_group(
            f"<blockquote expandable>"
            f"⚠️ <b>ERROR LOGIN</b>\n"
            f"• User ID: <code>{user_id}</code>\n"
            f"• Error: <code>{str(e)}</code>"
            f"</blockquote>"
        )
        await app.disconnect()
        _ACTIVE_ADD_SESSION.discard(user_id)
        return

    # Ekspor dan simpan session
    try:
        app_session = await app.export_session_string()
        await app.send_message(
            "me", 
            f"✅ <b>Session Berhasil!</b>\n\n<code>{app_session}</code>\n\n• String: Pyrogram\n• Powered by: Altroid-X\n\n⚠️ <b>JANGAN DIBAGIKAN!</b>"
        )
        await app.disconnect()
        await Altruix.add_session(app_session, process_msg, user=cb.from_user, skip_reload=True)
        await log_to_group(
            f"<blockquote expandable>"
            f"✅ <b>BERHASIL ADD SESSION</b>\n"
            f"• User ID: <code>{user_id}</code>\n"
            f"</blockquote>"
        )
        
        from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from Main.utils.file_helpers import get_user_button_style
        user_style = get_user_button_style(cb.from_user.id)
        await cb.message.reply(
            "✅ **Session added successfully!**\n\n"
            "Do you want to reload the system modules now to apply changes?\n"
            "*(Choose 'No' if you want to add more sessions first to save time)*",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Yes, Reload Now", callback_data="reload_sys_yes", style=user_style),
                    InlineKeyboardButton("No, Later", callback_data="reload_sys_no", style=user_style)
                ]
            ])
        )
    except Exception as e:
        await process_msg.edit("❌ Gagal tambahkan session ke bot.")
        Altruix.log(f"Add session error: {e}", level=logging.ERROR)
        await log_to_group(
            f"<blockquote expandable>"
            f"⚠️ <b>ERROR TAMBAH SESSION</b>\n"
            f"• User ID: <code>{user_id}</code>\n"
            f"• Error: <code>{str(e)}</code>"
            f"</blockquote>"
        )
        _ACTIVE_ADD_SESSION.discard(user_id)
        return

    _ACTIVE_ADD_SESSION.discard(user_id)
