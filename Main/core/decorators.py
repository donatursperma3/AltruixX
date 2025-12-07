# Copyright (C) 2021-present by Altruix@Github, <https://github.com/Altruix>
#
# This file is part of <https://github.com/Altruix/Altruix> project,
# and is released under the "GNU v3.0 License Agreement".
# Please see <https://github.com/Altriux/Altruix/blob/main/LICENSE>
#
# All rights reserved.

import os
import traceback
from Main import Altruix
from typing import Union
from functools import wraps
from Main.internals.set_inline import set_inline_in_botfather
from pyrogram.types import Message, InlineQuery, CallbackQuery
from pyrogram import Client, StopPropagation, ContinuePropagation
from pyrogram.errors import (
    MessageEmpty, MessageIdInvalid, BotInlineDisabled, MessageNotModified,
    UserNotParticipant
)
from pyrogram.types import LinkPreviewOptions


# ─── UTIL: KIRIM PESAN KE GRUP LOG (AMAN DARI ERROR) ────────────────────
async def send_log_message(text: str):
    """
    Kirim pesan ke LOG_CHAT_ID (dari .env) atau fallback ke OWNER_ID.
    Digunakan untuk logging error & aktivitas penting.
    """
    # ✅ PERBAIKAN: Gunakan LOG_CHAT_ID dari .env, bukan Altruix.log_chat (yg bisa None)
    log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))
    try:
        await Altruix.bot.send_message(
            log_chat_id,
            text,
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
    except Exception:
        # Jika gagal ke LOG_CHAT_ID, coba ke OWNER_ID langsung
        try:
            await Altruix.bot.send_message(
                Altruix.config.OWNER_ID,
                f"⚠️ [FALLBACK LOG]\n{text}",
                link_preview_options=LinkPreviewOptions(is_disabled=True)
            )
        except Exception:
            pass  # gagal total? abaikan


# ─── DECORATOR: DEBUG SETIAP INTERAKSI CALLBACK/INLINE ──────────────────
def iuser_check(func):
    """
    ✅ DIPERBAIKI:
    - Tambahkan logging aktivitas tombol ke log grup
    - Beri feedback jika terjadi error internal
    - Pastikan selalu ada respons (tidak diam)
    """

    async def wrapper(client: Client, update: Union[CallbackQuery, InlineQuery]):
        user = update.from_user
        if not user:
            return

        user_id = user.id
        username = f"@{user.username}" if user.username else "No username"
        full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "No name"

        # ✅ KIRIM NOTIFIKASI AKTIVITAS KE LOG (opsional, bisa dinonaktifkan)
        await send_log_message(
            f"🔘 <b>Callback Ditekan</b>\n"
            f"• User: {full_name} ({username})\n"
            f"• ID: <code>{user_id}</code>\n"
            f"• Fungsi: <code>{func.__name__}</code>"
        )

        if user_id in Altruix.auth_users:
            try:
                return await func(client, update)
            except MessageNotModified:
                # ✅ Jangan diam — beri feedback halus
                await update.answer("ℹ️ Tidak ada perubahan diperlukan.", show_alert=True)
            except Exception as e:
                # ✅ TANGANI ERROR INTERNAL & KIRIM KE LOG
                error_text = (
                    f"💥 <b>ERROR SAAT MENANGANI CALLBACK</b>\n"
                    f"• User: {full_name} ({user_id})\n"
                    f"• Fungsi: <code>{func.__name__}</code>\n"
                    f"• Error: <code>{str(e)}</code>"
                )
                await send_log_message(error_text)
                # ✅ Beri feedback ke user
                await update.answer("❌ Terjadi kesalahan internal. Owner telah diberi tahu.", show_alert=True)
        else:
            # ✅ Respon jelas untuk user tidak terotorisasi
            if isinstance(update, CallbackQuery):
                await update.answer(
                    "⛔ Anda tidak diizinkan menggunakan tombol ini.",
                    show_alert=True,
                    cache_time=5
                )
            else:
                await update.answer(
                    [],
                    switch_pm_text="⛔ Anda tidak diizinkan menggunakan fitur ini.",
                    switch_pm_parameter="unauthorized",
                    cache_time=5
                )

    return wrapper


# ─── DECORATOR: LOG ERROR SECARA LUAS DAN AMAN ──────────────────────────
def log_errors(func):
    """✅ DIPERBAIKI: Gunakan send_log_message & tangani semua edge case"""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except StopPropagation as e:
            raise StopPropagation from e
        except (
            MessageNotModified,
            MessageIdInvalid,
            UserNotParticipant,
            MessageEmpty,
        ):
            pass  # error yang bisa diabaikan
        except ContinuePropagation as e:
            raise ContinuePropagation from e
        except Exception as _be:
            # ✅ KIRIM ERROR LENGKAP KE LOG
            error_detail = (
                f"<b>AN ERROR OCCURRED:</b>\n"
                f"Exception: <i>{_be}</i>\n"
                f"Occurred in: <code>{func.__name__}</code>\n\n"
                f"<pre>{traceback.format_exc()}</pre>"
            )
            await send_log_message(error_detail)
            # Jangan lempar ulang kecuali dalam dev mode
            # raise _be  # optional

    return wrapper


# ─── DECORATOR: CEK IZIN INLINE (TANPA PERUBAHAN BESAR) ─────────────────
def inline_check(func):
    @wraps(func)
    async def check_inline(c: Client, m: Message, *args, **kwargs):
        try:
            return await func(c, m)
        except BotInlineDisabled:
            status = await m.handle_message("INLINE_DISABLED")
            await set_inline_in_botfather(c)
            await status.delete()
            return await func(c, m)
    return check_inline


# ─── DECORATOR: CEK IZIN ADMIN (TANPA PERUBAHAN BESAR) ──────────────────
def check_perm(perm_type, return_perm=False):
    def check_perm_s(func):
        async def perm_check(client, m):
            if m.chat.type in ["bot", "private"]:
                return await func(client, m)
            if isinstance(perm_type, list):
                s = {}
                for i in perm_type:
                    s[i] = await client.check_my_perm(m, i)[0]  # ✅ PERBAIKAN: sebelumnya s[perm_type] → salah
                if all(element is False for element in s.values()):
                    return await func(client, m)
                not_true_ = [str(v) for v in s.keys() if s[v] is False]
                not_true_m = ", ".join(not_true_)
                return await m.handle_message(
                    "ADMIN_ACTION_FAILED", string_args=(not_true_m,)
                )
            else:
                perm_result = await client.check_my_perm(m, perm_type)
                if return_perm:
                    return (
                        await func(client, m, perm_result[1])
                        if perm_result[0]
                        else await m.handle_message(
                            "ADMIN_ACTION_FAILED", string_args=(perm_type,)
                        )
                    )
                return (
                    await func(client, m)
                    if perm_result[0]
                    else await m.handle_message(
                        "ADMIN_ACTION_FAILED", string_args=(perm_type,)
                    )
                )
        return perm_check
    return check_perm_s
