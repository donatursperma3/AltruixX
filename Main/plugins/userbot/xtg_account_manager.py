# Copyright (C) 2025-present by @AlphaXproject
# Plugin: xtg_account_manager.py (set / modify) — 100% FIXED, NO __file__ DEPENDENCY
import os
import traceback
import html
import logging
import asyncio  # ✅ IMPORT BARU: Untuk sleep saat FloodWait
from pyrogram import Client
from pyrogram.enums import ParseMode
from pyrogram.errors import (
    UsernameInvalid, UsernameOccupied, UsernameNotModified,
    FloodWait, PhotoCropSizeSmall, BadRequest,
    PeerIdInvalid, UserIsBlocked  # ✅ IMPORT BARU: Error handling untuk SpamBot
)
from pyrogram.raw.functions.account import CheckUsername, GetAuthorizations
from pyrogram.types import LinkPreviewOptions
from Main import Altruix
from Main.core.types.message import Message
from Main.core.decorators import log_errors
# =============================================================================
# LOGGER KHUSUS PLUGIN
# =============================================================================
logger = logging.getLogger("altruix.xtg_account_manager")
logger.setLevel(logging.INFO)

__plugin_name__ = "xtg_account_manager"
PLUGIN_VERSION = "1.2.6"  # ✅ REFACTORED: Unified logging
logger.info(f"{__plugin_name__} v{PLUGIN_VERSION} berhasil dimuat")

# =============================================================================
class CustomMsg:
    PROCESSING = "🔄 Sedang memproses..."
    INPUT_REQUIRED = "❌ Input diperlukan: {}"
    SUCCESS = "✅ {} berhasil diubah: {}"
    USERNAME_TAKEN = "❌ {} sudah dipakai!"
    PHOTO_UPDATED = "✅ Foto profil berhasil diubah!"
    # ✅ PESAN BARU UNTUK LIMIT CHECK
    LIMIT_CHECKING = "🔍 Sedang mengecek status limit akun ke @SpamBot..."
    LIMIT_FREE = "✅ <b>Akun kamu BEBAS!</b>\n\nGood news, no limits are currently applied to your account. You’re free as a bird!"
    LIMIT_RESTRICTED = "⚠️ <b>Akun kamu TERKENA LIMIT!</b>\n\n{}"
    LIMIT_ERROR = "❌ Gagal mendapatkan info limit: {}"
Msg = CustomMsg()
async def safe_edit_or_reply(msg: Message, text: str, **kwargs) -> Message:
    default_kwargs = {
        "link_preview_options": LinkPreviewOptions(is_disabled=True),
        "parse_mode": ParseMode.HTML
    }
    default_kwargs.update(kwargs)
    try:
        if msg.outgoing:
            return await msg.edit_text(text, **default_kwargs)
        else:
            return await msg.reply_text(text, **default_kwargs)
    except Exception:
        try:
            return await msg.reply_text(f"{text}\n\n<i>(Gagal edit pesan)</i>", **default_kwargs)
        except Exception:
            return msg
# =============================================================================
@Altruix.register_on_cmd(
    ["set", "modify"],
    bot_mode_unsupported=True,
    requires_reply=False,
    cmd_help={
        "help": "Ubah pengaturan akun Telegram dengan aman!",
        "example": ".set -f AltruixBot",
        "user_args": {
            "-f <nama>": "Ganti nama depan",
            "-l <nama>": "Ganti nama belakang (kosong = hapus)",
            "-b <bio>": "Ganti bio",
            "-u <username>": "Ganti username (tanpa @)",
            "-p": "Ganti foto profil (reply ke foto)",
            "-s": "Lihat semua sesi login",
            "-delp": "Hapus semua foto profil",
            "-limit": "Cek status limit/spam akun (via @SpamBot)",  # ✅ ARG BARU DI HELP
        },
    },
)
@log_errors
async def advanced_set_command(c: Client, m: Message):
    # ─── PARSE ARGUMEN SECARA MANUAL ─────────────────────────────────────
    raw_text = (m.text or m.caption or "").strip()
    if not raw_text:
        proc = await m.handle_message(Msg.PROCESSING)
        return await safe_edit_or_reply(proc, "❌ Tidak ada input.")
    parts = raw_text.split()
    if len(parts) < 2:
        proc = await m.handle_message(Msg.PROCESSING)
        help_text = (
            "<b>🔧 Perintah Set / Modify</b>\n\n"
            "• <code>-f &lt;nama&gt;</code> → Ganti nama depan\n"
            "• <code>-l &lt;nama&gt;</code> → Ganti nama belakang (kosong = hapus)\n"
            "• <code>-b &lt;bio&gt;</code> → Ganti bio\n"
            "• <code>-u &lt;username&gt;</code> → Ganti username (tanpa @)\n"
            "• <code>-p</code> → Ganti foto profil (reply ke foto)\n"
            "• <code>-delp</code> → Hapus semua foto profil\n"
            "• <code>-s</code> → Lihat semua sesi aktif\n"
            "• <code>-limit</code> → Cek status limit akun (via @SpamBot)"  # ✅ TAMBAHAN DI HELP
        )
        return await safe_edit_or_reply(proc, help_text)
    args = []
    text_parts = []
    for part in parts[1:]:
        if part.startswith("-") and len(part) > 1 and part[1:].replace("_", "").isalnum():
            args.append(part)
        else:
            text_parts.append(part)
    text = " ".join(text_parts)
    reply = m.reply_to_message
    proc = await m.handle_message(Msg.PROCESSING)
    try:
        # ✅ PERUBAHAN BARU: Tambahkan handling -limit
        if "-limit" in args:
            await safe_edit_or_reply(proc, Msg.LIMIT_CHECKING)
            try:
                # Kirim pesan ke @SpamBot untuk memicu respons otomatis
                await c.send_message("spambot", "/start")
                # Tunggu sebentar agar respons masuk
                await asyncio.sleep(5)
                # Ambil history chat dengan SpamBot
                messages = [msg async for msg in c.get_chat_history("spambot", limit=10)]
                # Cari pesan terbaru dari SpamBot
                bot_responses = [msg.text for msg in messages if msg.from_user and msg.from_user.is_self == False]
                if bot_responses:
                    latest = bot_responses[0].strip()
                    if "Good news, no limits" in latest or "You’re free as a bird" in latest:
                        return await safe_edit_or_reply(proc, Msg.LIMIT_FREE)
                    else:
                        # Bersihkan respons untuk tampilan
                        cleaned = html.escape(latest)
                        return await safe_edit_or_reply(proc, Msg.LIMIT_RESTRICTED.format(cleaned))
                else:
                    return await safe_edit_or_reply(proc, Msg.LIMIT_ERROR.format("Tidak ada respons dari @SpamBot"))
            except UserIsBlocked:
                return await safe_edit_or_reply(proc, Msg.LIMIT_ERROR.format("Akun kamu diblokir oleh @SpamBot (mungkin limit permanen)"))
            except PeerIdInvalid:
                return await safe_edit_or_reply(proc, Msg.LIMIT_ERROR.format("Tidak dapat menemukan @SpamBot"))
            except FloodWait as e:
                return await safe_edit_or_reply(proc, f"⏳ FloodWait! Tunggu {e.value} detik.")
            except Exception as e:
                return await safe_edit_or_reply(proc, Msg.LIMIT_ERROR.format(html.escape(str(e))))

        if "-f" in args:
            if not text:
                return await safe_edit_or_reply(proc, Msg.INPUT_REQUIRED.format("nama depan"))
            await c.update_profile(first_name=text[:70])
            return await safe_edit_or_reply(proc, Msg.SUCCESS.format("Nama Depan", f"<code>{html.escape(text)}</code>"))
        # ... (kode lain tetap sama)
        # (seluruh bagian elif lainnya tidak diubah)

        elif "-l" in args:
            await c.update_profile(last_name=text or None)
            action = "dihapus" if not text else f"diubah menjadi <code>{html.escape(text)}</code>"
            return await safe_edit_or_reply(proc, Msg.SUCCESS.format("Nama Belakang", action))

        elif "-b" in args:
            if not text:
                return await safe_edit_or_reply(proc, Msg.INPUT_REQUIRED.format("bio"))
            await c.update_profile(bio=text[:170])
            return await safe_edit_or_reply(proc, Msg.SUCCESS.format("Bio", f"<code>{html.escape(text)}</code>"))

        elif "-u" in args:
            if not text:
                return await safe_edit_or_reply(proc, Msg.INPUT_REQUIRED.format("username"))
            uname = text.lstrip("@")
            if len(uname) < 5:
                return await safe_edit_or_reply(proc, "❌ Username minimal 5 karakter!")
            try:
                check = await c.invoke(CheckUsername(username=uname))
                if not check:
                    return await safe_edit_or_reply(proc, Msg.USERNAME_TAKEN.format(f"@{uname}"))
                await c.set_username(uname)
                return await safe_edit_or_reply(proc, Msg.SUCCESS.format("Username", f"@{uname}"))
            except UsernameOccupied:
                return await safe_edit_or_reply(proc, f"❌ @{uname} sudah dipakai!")
            except UsernameInvalid:
                return await safe_edit_or_reply(proc, "❌ Username tidak valid!")
            except UsernameNotModified:
                return await safe_edit_or_reply(proc, "ℹ️ Username sudah sama seperti sekarang.")

        elif "-p" in args:
            if not reply or not reply.photo:
                return await safe_edit_or_reply(proc, "❌ Reply ke foto yang ingin dijadikan profil!")
            photo_path = await reply.download(in_memory=False)
            try:
                await c.set_profile_photo(photo=photo_path)
                await safe_edit_or_reply(proc, Msg.PHOTO_UPDATED)
            except (PhotoCropSizeSmall, BadRequest) as e:
                await safe_edit_or_reply(proc, f"❌ Gagal set foto: {str(e) or 'Ukuran terlalu kecil / tidak cocok.'}")
            finally:
                if photo_path and os.path.exists(photo_path):
                    try:
                        os.remove(photo_path)
                    except OSError:
                        pass
            return

        elif "-delp" in args:
            try:
                photos = [p async for p in c.get_chat_photos("me")]
                if not photos:
                    return await safe_edit_or_reply(proc, "ℹ️ Kamu belum punya foto profil.")
                await c.delete_profile_photos([p.file_id for p in photos])
                return await safe_edit_or_reply(proc, "✅ Semua foto profil berhasil dihapus!")
            except Exception as e:
                return await safe_edit_or_reply(proc, f"❌ Gagal hapus foto: {str(e)}")

        elif "-s" in args:
            try:
                auths = (await c.invoke(GetAuthorizations())).authorizations
                if not auths:
                    return await safe_edit_or_reply(proc, "ℹ️ Tidak ada sesi aktif selain ini.")
                out = f"<b>📱 Total Sesi Aktif: {len(auths)}</b>\n\n"
                for i, s in enumerate(auths, 1):
                    curr = " ← <b>Sesi ini</b>" if s.current else ""
                    out += f"<b>{i}.</b> {html.escape(s.device_model or 'Unknown')} • {html.escape(s.app_name or 'Unknown')} {html.escape(s.app_version or '')}{curr}\n"
                    out += f" ├ OS: <code>{html.escape(s.platform or 'Unknown')} {html.escape(s.system_version or '-')}</code>\n"
                    out += f" ├ IP: <code>{s.ip or 'Unknown'}</code> • {s.country or 'Unknown'}\n"
                    out += f" └ Login: <code>{s.date_created or 'Unknown'}</code>\n\n"
                return await safe_edit_or_reply(proc, out)
            except FloodWait as e:
                return await safe_edit_or_reply(proc, f"⏳ FloodWait! Tunggu {e.value} detik.")
            except Exception as e:
                return await safe_edit_or_reply(proc, f"❌ Gagal mengambil data sesi: {str(e)}")

        else:
            help_text = (
                "<b>🔧 Perintah Set / Modify</b>\n\n"
                "• <code>-f &lt;nama&gt;</code> → Ganti nama depan\n"
                "• <code>-l &lt;nama&gt;</code> → Ganti nama belakang (kosong = hapus)\n"
                "• <code>-b &lt;bio&gt;</code> → Ganti bio\n"
                "• <code>-u &lt;username&gt;</code> → Ganti username (tanpa @)\n"
                "• <code>-p</code> → Ganti foto profil (reply ke foto)\n"
                "• <code>-delp</code> → Hapus semua foto profil\n"
                "• <code>-s</code> → Lihat semua sesi aktif\n"
                "• <code>-limit</code> → Cek status limit akun (via @SpamBot)"
            )
            return await safe_edit_or_reply(proc, help_text)
    except FloodWait as e:
        await safe_edit_or_reply(proc, f"⏳ Terlalu cepat! Tunggu {e.value} detik.")
    except Exception as e:
        error_detail = traceback.format_exc()
        logger.error(f"[SET PLUGIN ERROR]\n{error_detail}")
        print(f"[SET PLUGIN ERROR] {str(e)}")
        await safe_edit_or_reply(proc, f"❌ Terjadi kesalahan:\n<code>{html.escape(str(e))}</code>")

# Log sukses loading
logger.info(f"✅ Loaded → {__plugin_name__} v{PLUGIN_VERSION}")
