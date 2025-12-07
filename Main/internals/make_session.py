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
import contextlib
from Main import Altruix
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


async def client_session(api_id, api_hash):
    """Buat klien sementara untuk generate session string."""
    return Client("new_session", api_id=int(api_id), api_hash=str(api_hash), in_memory=True)


# ─── UTIL: Kirim log ke grup (dengan fallback ke OWNER_ID) ─────────────
async def log_to_group(text: str):
    """Kirim notifikasi ke LOG_CHAT_ID atau OWNER_ID jika gagal."""
    log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))
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

    # ✅ PERIKSA IZIN: hanya auth_users yang boleh akses
    if user_id not in Altruix.auth_users:
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
    if cb.from_user.id not in Altruix.auth_users:
        return await cb.answer("⛔ Tidak diizinkan.", show_alert=True)
    await cb.answer()
    await _start_add_session_process(cb)


# ─── FUNGSI UTAMA: Alur pembuatan session ──────────────────────────────
async def _start_add_session_process(cb: CallbackQuery):
    user = cb.from_user
    user_id = user.id
    is_sudo = user_id != Altruix.config.OWNER_ID

    # ✅ Log ke grup jika sudo user memulai proses
    if is_sudo:
        await log_to_group(
            f"👮‍♂️ <b>Sudo User Memulai Generate Session</b>\n"
            f"• Nama: {user.first_name} {user.last_name or ''}\n"
            f"• ID: <code>{user_id}</code>"
        )

    # ✅ KIRIM PESAN VIA BOT (BUKAN VIA USER) — AMAN DI PM!
    try:
        temp_msg = await Altruix.bot.send_message(
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
        await cb.message.edit("❌ Gagal memulai proses.")
        return

    phone_number = None
    try:
        # ✅ DENGARKAN RESPON VIA BOT (BUKAN VIA USER)
        while True:
            response: Message = await Altruix.bot.listen(user_id, filters=filters.user(user_id), timeout=120)
            if response.contact:
                phone_number = response.contact.phone_number
                break
            elif response.text and response.text.strip().lower() == "/cancel":
                await temp_msg.delete()
                await Altruix.bot.send_message(user_id, "❌ Dibatalkan.", reply_markup=ReplyKeyboardRemove())
                return
            else:
                await Altruix.bot.send_message(user_id, "❌ Kirim kontak atau /cancel.")
    except asyncio.TimeoutError:
        await temp_msg.delete()
        await Altruix.bot.send_message(user_id, "⏰ Waktu habis.", reply_markup=ReplyKeyboardRemove())
        return
    except Exception as e:
        Altruix.log(f"Error tunggu input: {e}", level=logging.ERROR)
        await Altruix.bot.send_message(user_id, "❌ Kesalahan internal.")
        return

    await Altruix.bot.send_message(user_id, "📞 Nomor diterima. Membuat session...", reply_markup=ReplyKeyboardRemove())
    process_msg = await Altruix.bot.send_message(user_id, "<i>Mohon tunggu...</i>")

    # Buat klien sementara
    try:
        app = await client_session(Altruix.config.API_ID, Altruix.config.API_HASH)
        await app.connect()
        sent_code = await app.send_code(phone_number)
    except FloodWait as e:
        await process_msg.edit(f"⏳ FloodWait! Tunggu {e.value} detik.")
        await app.disconnect()
        return
    except PhoneNumberInvalid:
        await process_msg.edit("❌ Nomor telepon tidak valid.")
        await app.disconnect()
        return
    except ApiIdInvalid:
        await process_msg.edit("❌ API ID/Hash tidak valid.")
        await app.disconnect()
        return
    except Exception as e:
        await process_msg.edit("❌ Gagal kirim kode OTP.")
        Altruix.log(f"Kirim kode error: {e}", level=logging.ERROR)
        await app.disconnect()
        return

    # Minta kode OTP
    try:
        # ✅ TANYA KODE VIA BOT
        ans = await Altruix.bot.ask(
            user_id,
            "🔑 Kirim kode OTP format <code>1-2-3-4-5</code>",
            reply_markup=ForceReply(selective=True),
            timeout=300,
            filters=filters.user(user_id)
        )
        if ans.text and ans.text.strip().lower() == "/cancel":
            await process_msg.edit("❌ Dibatalkan oleh user.")
            await app.disconnect()
            return
        code = ans.text.replace("-", "").replace(" ", "")
        await app.sign_in(phone_number, sent_code.phone_code_hash, code)
    except SessionPasswordNeeded:
        try:
            ans2 = await Altruix.bot.ask(
                user_id,
                "🔐 Masukkan password 2FA:",
                reply_markup=ForceReply(selective=True),
                timeout=300,
                filters=filters.user(user_id)
            )
            if ans2.text.strip().lower() == "/cancel":
                await process_msg.edit("❌ Dibatalkan.")
                await app.disconnect()
                return
            await app.check_password(ans2.text)
        except Exception as e:
            await process_msg.edit("❌ Password salah atau error.")
            Altruix.log(f"2FA error: {e}", level=logging.ERROR)
            await app.disconnect()
            return
    except (PhoneCodeInvalid, PhoneCodeExpired):
        await process_msg.edit("❌ Kode OTP salah/kadaluarsa.")
        await app.disconnect()
        return
    except Exception as e:
        await process_msg.edit("❌ Gagal login.")
        Altruix.log(f"Sign-in error: {e}", level=logging.ERROR)
        await app.disconnect()
        return

    # Ekspor dan simpan session
    try:
        app_session = await app.export_session_string()
        await app.send_message("me", f"✅ **Session Berhasil!**\n\n`{app_session}`\n\n⚠️ **JANGAN DIBAGIKAN!**")
        await app.disconnect()
        await Altruix.add_session(app_session, process_msg)
    except Exception as e:
        await process_msg.edit("❌ Gagal tambahkan session ke bot.")
        Altruix.log(f"Add session error: {e}", level=logging.ERROR)
        return
