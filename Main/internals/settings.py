# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix/Altruix >
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.

from Main import Altruix
from typing import List, Tuple
from pyrogram import Client, filters
from Main.core.decorators import log_errors
from Main.core.types.message import Message
from pyrogram.types import (
    CallbackQuery, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove,
    InlineKeyboardButton, InlineKeyboardMarkup, LinkPreviewOptions
)
from pyrogram.errors import (
    PeerIdInvalid, UserIsBlocked, ChatWriteForbidden, FloodWait, MessageIdInvalid,
    SlowmodeWait
)
import os
import logging
import asyncio
import html
from datetime import datetime
import io


settings_menu_buttons = [
    [
        InlineKeyboardButton("Sessions", callback_data="sessions_list_1"),
        InlineKeyboardButton("Configs", callback_data="configs_home"),
    ],
]


@Altruix.bot.on_callback_query(filters.regex("configs_home"))
@log_errors
async def configs_menu_cb_handler(c: Client, cb: CallbackQuery):
    await cb.answer("This feature will be added soon!", show_alert=True)


@Altruix.bot.on_callback_query(filters.regex("settings_menu"))
@log_errors
async def settings_menu_cb_handler(c: Client, cb: CallbackQuery):
    await cb.answer()
    await cb.message.edit(
        text=Altruix.get_string("SETTINGS_TEXT") or "<b>Settings</b>",
        reply_markup=InlineKeyboardMarkup(settings_menu_buttons)
    )


def arrange_buttons(array: list, no=5) -> List:
    n = int(no)
    return [array[i * n : (i + 1) * n] for i in range((len(array) + n - 1) // n)]


def get_sessions_buttons(page=1) -> Tuple[List[InlineKeyboardButton], bool, int]:
    per_page = 9
    buttons = [
        InlineKeyboardButton(str(i.myself.first_name), f"session_info_{index}_{page}")
        for index, i in enumerate(Altruix.clients)
    ] + [InlineKeyboardButton("\u2795 Add a session", "add_session")]
    len_buttons = len(buttons)
    buttons = arrange_buttons(buttons, per_page)
    
    total_pages = len(buttons)
    if page < 1:
        page = 1
    elif page > total_pages:
        page = total_pages if total_pages > 0 else 1

    current_buttons = buttons[page - 1] if total_pages > 0 else []
    has_next = page < total_pages
    return current_buttons, has_next, total_pages


@Altruix.bot.on_message(
    filters.command("settings", "/") & filters.user(Altruix.auth_users)
)
@log_errors
async def settings_command_handler(c: Client, m: Message):
    total_sessions = len(Altruix.clients)
    settings_text = Altruix.get_string("SETTINGS_TEXT") or "<b>🛠️ Settings</b>"
    full_text = f"{settings_text}\n\n<b>Total Sessions:</b> <code>{total_sessions}</code>"
    
    await m.reply(
        full_text,
        reply_markup=InlineKeyboardMarkup(settings_menu_buttons),
        quote=True,
    )


@Altruix.bot.on_callback_query(filters.regex("sessions_list_(\\d+)$"))
@log_errors
async def sessions_menu_cb_handler(c: Client, cb: CallbackQuery):
    await cb.answer()
    try:
        page = int(cb.data.split("_")[-1])
    except (ValueError, IndexError):
        page = 1

    buttons, has_next, total_pages = get_sessions_buttons(page)
    
    # ✅ Dapatkan LOG_CHAT_ID dengan benar
    LOG_CHAT_ID = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))

    # ✅ Tambahkan tombol aksi sebagai LIST TUNGGAL
    action_buttons = [
        InlineKeyboardButton("🏓 Test Ping All", "test_ping_all_confirmation"),
        InlineKeyboardButton("📲 Export All Phones", "export_all_phones")
    ]
    
    # ✅ Tambahkan tombol navigasi sebagai LIST TUNGGAL
    nav_buttons = []
    if not page == 1:
        nav_buttons.append(InlineKeyboardButton("Previous", f"sessions_list_{page - 1}"))
    nav_buttons.append(InlineKeyboardButton(f"🔙 [{page}/{total_pages or 1}]", "settings_menu"))
    if has_next:
        nav_buttons.append(InlineKeyboardButton("Next", f"sessions_list_{page + 1}"))
    
    # ✅ Pastikan SEMUA elemen adalah LIST OF LISTS
    final_markup = buttons + [action_buttons] + [nav_buttons]
    total_sessions = len(Altruix.clients)
    
    try:
        await cb.message.edit(
            text=f"<b>Total Sessions:</b> <code>{total_sessions}</code>", 
            reply_markup=InlineKeyboardMarkup(final_markup)
        )
    except Exception as e:
        # ✅ Gunakan LOG_CHAT_ID yang sudah didefinisikan
        await Altruix.bot.send_message(
            LOG_CHAT_ID,
            f"⚠️ <b>SESSION MENU ERROR</b>\n"
            f"• Error: <code>{str(e)}</code>",
            parse_mode="html"
        )
        await cb.message.edit("❌ Gagal memuat menu. Owner telah diberi tahu.")


# ─── EXPORT ALL PHONE NUMBERS HANDLER ───────────────────────────────────
@Altruix.bot.on_callback_query(filters.regex("export_all_phones"))
@log_errors
async def export_all_phones_handler(c: Client, cb: CallbackQuery):
    """Ekspor semua nomor telepon ke file teks."""
    user = cb.from_user
    user_id = user.id
    log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))

    if user_id not in Altruix.auth_users:
        return await cb.answer("⛔ Anda tidak diizinkan mengakses fitur ini.", show_alert=True)

    if not Altruix.clients:
        return await cb.answer("❌ Tidak ada session yang tersedia.", show_alert=True)

    await cb.answer("📲 Sedang menyiapkan file nomor...", show_alert=False)
    
    try:
        # ✅ Kumpulkan data semua session
        phone_data = []
        for client in Altruix.clients:
            try:
                user_info = await client.get_me()
                first_name = user_info.first_name or "None"
                last_name = user_info.last_name or "None"
                full_name = f"{first_name} {last_name}".strip()
                username = f"@{user_info.username}" if user_info.username else "None"
                phone = user_info.phone_number or "Not Available"
                user_id = user_info.id
                
                phone_data.append(
                    f"Nama: {full_name}\n"
                    f"Nomor: +{phone}\n"
                    f"ID: {user_id}\n"
                    f"Username: {username}\n"
                    f"{'-' * 40}"
                )
            except Exception as e:
                Altruix.log(f"Error mengambil info session: {e}", level=logging.ERROR)
                phone_data.append(f"Error: {str(e)}\n{'-' * 40}")

        # ✅ Buat file teks
        file_content = "\n".join(phone_data)
        file_stream = io.BytesIO(file_content.encode())
        file_stream.name = "all_phone_numbers.txt"

        # ✅ Kirim file ke user via bot
        await Altruix.bot.send_document(
            chat_id=user.id,
            document=file_stream,
            caption="📲 **All Phone Numbers Exported**\nFile ini berisi data semua session Anda."
        )

        # ✅ Kirim notifikasi ke log
        await Altruix.bot.send_message(
            log_chat_id,
            f"📲 <b>EXPORT ALL PHONES</b>\n"
            f"• User: <a href='tg://user?id={user.id}'>{html.escape(user.first_name)}</a>\n"
            f"• Jumlah Session: <code>{len(Altruix.clients)}</code>\n"
            f"• Waktu: <code>{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</code>",
            parse_mode="html",
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )

        await cb.message.edit("✅ File nomor telepon berhasil dikirim ke pesan pribadi Anda.")

    except FloodWait as e:
        await asyncio.sleep(e.value)
        await cb.message.edit(f"⏳ FloodWait terdeteksi. Tunggu {e.value} detik.")
        Altruix.log(f"FloodWait saat export all phones: {e.value}s")

    except (PeerIdInvalid, UserIsBlocked, ChatWriteForbidden) as e:
        error_msg = "❌ Gagal mengirim file: User tidak dapat dihubungi."
        await cb.message.edit(error_msg)
        Altruix.log(f"Error izin saat export all phones: {e}")

        # ✅ Kirim error ke log
        await Altruix.bot.send_message(
            log_chat_id,
            f"⚠️ <b>ERROR EXPORT ALL PHONES</b>\n"
            f"• User: <a href='tg://user?id={user.id}'>{html.escape(user.first_name)}</a>\n"
            f"• Error: <code>{type(e).__name__}</code>\n"
            f"• Solusi: Pastikan Anda memulai chat dengan bot assistant.",
            parse_mode="html"
        )

    except Exception as e:
        await cb.message.edit("❌ Gagal mengekspor nomor. Owner telah diberi tahu.")
        Altruix.log(f"Error umum saat export all phones: {e}")

        # ✅ Kirim error detail ke log
        await Altruix.bot.send_message(
            log_chat_id,
            f"⚠️ <b>ERROR EXPORT ALL PHONES (CRITICAL)</b>\n"
            f"• User: <a href='tg://user?id={user.id}'>{html.escape(user.first_name)}</a>\n"
            f"• Error: <code>{str(e)}</code>\n"
            f"• Waktu: <code>{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</code>",
            parse_mode="html"
        )


# ─── TEST PING ALL CONFIRMATION ─────────────────────────────────────────
@Altruix.bot.on_callback_query(filters.regex("test_ping_all_confirmation"))
@log_errors
async def test_ping_all_confirmation_handler(c: Client, cb: CallbackQuery):
    await cb.answer()
    confirmation_buttons = [
        [
            InlineKeyboardButton("✅ Yes", callback_data="test_ping_all_confirm_yes"),
            InlineKeyboardButton("❌ No", callback_data="test_ping_all_confirm_no")
        ]
    ]
    await cb.message.edit(
        text="❓ Are you sure you want to test ping all sessions?",
        reply_markup=InlineKeyboardMarkup(confirmation_buttons)
    )


# ─── CANCEL TEST PING ALL ───────────────────────────────────────────────
@Altruix.bot.on_callback_query(filters.regex("test_ping_all_confirm_no"))
@log_errors
async def test_ping_all_cancel_handler(c: Client, cb: CallbackQuery):
    await cb.answer("Operation cancelled.")
    await sessions_menu_cb_handler(c, cb)


# ─── EXECUTE TEST PING ALL ──────────────────────────────────────────────
@Altruix.bot.on_callback_query(filters.regex("test_ping_all_confirm_yes"))
@log_errors
async def test_ping_all_execute_handler(c: Client, cb: CallbackQuery):
    await cb.answer("🏓 Testing ping for all sessions...", show_alert=False)
    log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))
    user = cb.from_user
    
    success_count = 0
    failed_count = 0
    total_sessions = len(Altruix.clients)
    
    if total_sessions == 0:
        await cb.message.edit("❌ No sessions available to ping.")
        return

    await cb.message.edit(f"✅ Starting ping test for <b>{total_sessions}</b> sessions...")
    
    for index, client in enumerate(Altruix.clients):
        session_user = client.myself
        try:
            await client.send_message(
                chat_id=log_chat_id,
                text=f"🏓 <b>Pong!</b>\nDari akun: <a href='tg://user?id={session_user.id}'>{html.escape(session_user.first_name or 'Unknown')}</a> | ID: <code>{session_user.id}</code>",
                parse_mode="html",
                link_preview_options=LinkPreviewOptions(is_disabled=True)
            )
            success_count += 1
            
        except FloodWait as e:
            await asyncio.sleep(e.value)
            try:
                await client.send_message(
                    chat_id=log_chat_id,
                    text=f"🏓 <b>Pong!</b>\nDari akun: <a href='tg://user?id={session_user.id}'>{html.escape(session_user.first_name or 'Unknown')}</a> | ID: <code>{session_user.id}</code>",
                    parse_mode="html",
                    link_preview_options=LinkPreviewOptions(is_disabled=True)
                )
                success_count += 1
            except Exception:
                failed_count += 1
                
        except (PeerIdInvalid, UserIsBlocked, ChatWriteForbidden, SlowmodeWait, MessageIdInvalid):
            failed_count += 1
            
        except Exception:
            failed_count += 1

        await cb.message.edit(
            f"✅ Ping test in progress...\n"
            f"• Berhasil: <code>{success_count}</code>\n"
            f"• Gagal: <code>{failed_count}</code>\n"
            f"• Total: <code>{total_sessions}</code>"
        )
        await asyncio.sleep(1)

    final_status = "✅ SEMUA BERHASIL" if failed_count == 0 else "⚠️ ADA YANG GAGAL"
    await Altruix.bot.send_message(
        log_chat_id,
        f"🏓 <b>TEST PING ALL SELESAI</b>\n"
        f"• User: <a href='tg://user?id={user.id}'>{html.escape(user.first_name)}</a>\n"
        f"• Status: <b>{final_status}</b>\n"
        f"• Berhasil: <code>{success_count}</code> akun\n"
        f"• Gagal: <code>{failed_count}</code> akun\n"
        f"• Waktu: <code>{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</code>",
        parse_mode="html",
        link_preview_options=LinkPreviewOptions(is_disabled=True)
    )
    
    await cb.message.edit(
        f"✅ Ping all test completed!\n"
        f"• Berhasil: <code>{success_count}</code>\n"
        f"• Gagal: <code>{failed_count}</code>\n"
        f"Lihat detail di grup log."
    )


@Altruix.bot.on_callback_query(filters.regex("session_info_(\\d+)_(\\d+)$"))
@log_errors
async def sessions_info_cb_handler(c: Client, cb: CallbackQuery):
    await cb.answer()
    index = int(cb.matches[0].group(1))
    callback_page = int(cb.matches[0].group(2))

    if index >= len(Altruix.clients):
        await cb.message.edit("Session not found.")
        return

    session_info = Altruix.clients[index].myself

    is_scam = getattr(
        getattr(session_info, 'verification_status', session_info),
        'is_scam',
        False
    )

    txt = (
        "<b>Session info</b>\n\n"
        "<b>First name:</b> {}\n"
        "<b>Last name:</b> {}\n"
        "<b>DC ID:</b> <code>{}</code>\n"
        "<b>Username:</b> @{}\n"
        "<b>User ID:</b> <code>{}</code>\n"
        "<b>Is SCAM:</b> <code>{}</code>"
    ).format(
        session_info.first_name or "None",
        session_info.last_name or "None",
        session_info.dc_id or "Unknown",
        session_info.username or "None",
        session_info.id,
        "Yes" if is_scam else "No",
    )
    
    await cb.message.edit(
        text=txt,
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("🔄 Refresh data", f"refresh_session_info_{index}"),
                    InlineKeyboardButton("🔗 Unlink (Remove)", f"unlink_session_{index}"),
                ],
                [
                    InlineKeyboardButton("📤 Export Session", f"export_session_{index}"),
                ],
                [
                    InlineKeyboardButton("📞 Export Phone Number", f"export_phone_{index}"),
                ],
                [
                    InlineKeyboardButton("🏓 Test Ping", f"test_ping_{index}"),
                ],
                [
                    InlineKeyboardButton("🔙 Back", f"sessions_list_{callback_page}"),
                ],
            ]
        ),
    )


# ─── TEST PING HANDLER ──────────────────────────────────────────────────
@Altruix.bot.on_callback_query(filters.regex("test_ping_(\\d+)$"))
@log_errors
async def test_ping_cb_handler(c: Client, cb: CallbackQuery):
    user = cb.from_user
    user_id = user.id
    index = int(cb.matches[0].group(1))

    if index >= len(Altruix.clients):
        return await cb.answer("Session tidak ditemukan.", show_alert=True)

    if user_id not in Altruix.auth_users:
        return await cb.answer("⛔ Anda tidak diizinkan menguji ping.", show_alert=True)

    await cb.answer("🏓 Mengirim ping...", show_alert=False)
    log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))
    session_client = Altruix.clients[index]
    session_user = session_client.myself

    try:
        await session_client.send_message(
            chat_id=log_chat_id,
            text=(
                f"🏓 <b>Pong!</b>\n"
                f"• User: <a href='tg://user?id={user.id}'>{html.escape(user.first_name)}</a> melakukan test ping pada akun: "
                f"<a href='tg://user?id={session_user.id}'>{html.escape(session_user.first_name or '')} {html.escape(session_user.last_name or '')}</a>\n"
                f"• Tanggal: <code>{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</code>"
            ),
            parse_mode="html",
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
        
        await cb.message.edit(
            f"✅ Ping berhasil! Pesan dikirim ke grup log.\n"
            f"Akun: <a href='tg://user?id={session_user.id}'>{html.escape(session_user.first_name or '')} {html.escape(session_user.last_name or '')}</a>",
            parse_mode="html"
        )
        
        Altruix.log(f"Test ping sukses untuk session {index} ({session_user.id})")

    except FloodWait as e:
        await asyncio.sleep(e.value)
        await cb.message.edit(f"⏳ FloodWait terdeteksi. Tunggu {e.value} detik.")
        Altruix.log(f"FloodWait saat test ping session {index}: {e.value}s")

    except (PeerIdInvalid, UserIsBlocked, ChatWriteForbidden) as e:
        error_msg = "❌ Gagal mengirim ping: Bot tidak bisa mengirim pesan ke grup log."
        await cb.message.edit(error_msg)
        Altruix.log(f"Error izin saat test ping session {index}: {e}")

        try:
            await Altruix.bot.send_message(
                log_chat_id,
                f"⚠️ <b>ERROR TEST PING</b>\n"
                f"• User: <a href='tg://user?id={user.id}'>{html.escape(user.first_name)}</a>\n"
                f"• Session: <a href='tg://user?id={session_user.id}'>{html.escape(session_user.first_name or '')} {html.escape(session_user.last_name or '')}</a> (<code>{session_user.id}</code>)\n"
                f"• Error: <code>{type(e).__name__}</code>\n"
                f"• Solusi: Pastikan bot assistant dan userbot berada di group dan bisa mengirim pesan ke grup log.",
                parse_mode="html"
            )
        except Exception as log_err:
            Altruix.log(f"Gagal kirim log error test ping: {log_err}")

    except SlowmodeWait as e:
        error_msg = f"❌ Slowmode aktif. Tunggu {e.value} detik."
        await cb.message.edit(error_msg)
        Altruix.log(f"SlowmodeWait saat test ping session {index}: {e.value}s")
        try:
            await Altruix.bot.send_message(
                log_chat_id,
                f"⚠️ <b>ERROR TEST PING (SlowmodeWait)</b>\n"
                f"• User: <a href='tg://user?id={user.id}'>{html.escape(user.first_name)}</a>\n"
                f"• Session: <a href='tg://user?id={session_user.id}'>{html.escape(session_user.first_name or '')} {html.escape(session_user.last_name or '')}</a>\n"
                f"• Error: <code>SlowmodeWait({e.value}s)</code>",
                parse_mode="html"
            )
        except Exception as log_err:
            Altruix.log(f"Gagal kirim log error Slowmode: {log_err}")

    except Exception as e:
        await cb.message.edit("❌ Gagal menguji ping. Owner telah diberi tahu.")
        Altruix.log(f"Error umum saat test ping session {index}: {e}")

        try:
            await Altruix.bot.send_message(
                log_chat_id,
                f"⚠️ <b>ERROR TEST PING (CRITICAL)</b>\n"
                f"• User: <a href='tg://user?id={user.id}'>{html.escape(user.first_name)}</a>\n"
                f"• Session: <a href='tg://user?id={session_user.id}'>{html.escape(session_user.first_name or '')} {html.escape(session_user.last_name or '')}</a> (<code>{session_user.id}</code>)\n"
                f"• Error: <code>{str(e)}</code>\n"
                f"• Waktu: <code>{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</code>",
                parse_mode="html"
            )
        except Exception as log_err:
            Altruix.log(f"Gagal kirim log error kritis test ping: {log_err}")


# ─── EXPORT PHONE NUMBER HANDLER ───────────────────────────────────────
@Altruix.bot.on_callback_query(filters.regex("export_phone_(\\d+)$"))
@log_errors
async def export_phone_cb_handler(c: Client, cb: CallbackQuery):
    user = cb.from_user
    user_id = user.id
    index = int(cb.matches[0].group(1))

    if index >= len(Altruix.clients):
        return await cb.answer("Session tidak ditemukan.", show_alert=True)

    if user_id not in Altruix.auth_users:
        return await cb.answer("⛔ Tidak diizinkan mengekspor nomor.", show_alert=True)

    await cb.answer("📞 Mengambil nomor telepon...", show_alert=False)

    try:
        session_client = Altruix.clients[index]
        user_info = await session_client.get_me()

        if not user_info.phone_number:
            await cb.message.edit("❌ Akun ini tidak memiliki nomor telepon yang terdaftar.")
            return

        await c.send_message(
            chat_id=user_id,
            text=f"📞 **Nomor telepon untuk akun `{user_info.first_name}`:**\n\n`+{user_info.phone_number}`"
        )

        log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))
        log_msg = (
            "📞 <b>NOMOR TELEPON DIEKSPOR</b>\n\n"
            f"• <b>User:</b> <a href='tg://user?id={user_id}'>{html.escape(user.first_name)}</a> (<code>{user_id}</code>)\n"
            f"• <b>Akun:</b> <a href='tg://user?id={user_info.id}'>{html.escape(user_info.first_name)}</a> | <code>+{user_info.phone_number}</code>\n"
            f"• <b>Waktu:</b> <code>{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</code>"
        )
        await Altruix.bot.send_message(log_chat_id, log_msg, parse_mode="html")
        await cb.message.edit("✅ Nomor telepon dikirim ke pesan pribadi Anda.")
        
    except Exception as e:
        error_text = (
            "⚠️ <b>ERROR SAAT EKSPOR NOMOR TELEPON</b>\n\n"
            f"• User ID: <code>{user_id}</code>\n"
            f"• Session Index: <code>{index}</code>\n"
            f"• Error: <code>{str(e)}</code>"
        )
        log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))
        try:
            await Altruix.bot.send_message(log_chat_id, error_text, parse_mode="html")
        except Exception:
            pass

        await cb.message.edit("❌ Gagal mengekspor nomor telepon. Owner telah diberi tahu.")
        Altruix.log(f"Error mengekspor nomor telepon: {e}", level=logging.ERROR)


# ─── EXPORT SESSION HANDLER ───────────────────────────────────────────
@Altruix.bot.on_callback_query(filters.regex("export_session_(\\d+)$"))
@log_errors
async def export_session_cb_handler(c: Client, cb: CallbackQuery):
    user = cb.from_user
    user_id = user.id
    index = int(cb.matches[0].group(1))

    if index >= len(Altruix.clients):
        return await cb.answer("Session tidak ditemukan.", show_alert=True)

    if user_id not in Altruix.auth_users:
        return await cb.answer("⛔ Tidak diizinkan mengekspor session.", show_alert=True)

    await cb.answer("📤 Mengekspor session...", show_alert=False)

    try:
        session_string = await Altruix.clients[index].export_session_string()
        await c.send_message(
            chat_id=user_id,
            text=f"🔒 **Session String untuk akun `{Altruix.clients[index].myself.first_name}`:**\n\n"
                 f"`{session_string}`\n\n"
                 "⚠️ **JANGAN DIBAGIKAN!**"
        )
        
        log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))
        session_user = Altruix.clients[index].myself
        log_msg = (
            "📤 <b>SESSION DIEKSPOR</b>\n\n"
            f"• <b>User:</b> <a href='tg://user?id={user_id}'>{html.escape(user.first_name)}</a> (<code>{user_id}</code>)\n"
            f"• <b>Akun:</b> <a href='tg://user?id={session_user.id}'>{html.escape(session_user.first_name or 'Unknown')}</a> "
            f"(@{session_user.username if session_user.username else 'None'}) | <code>{session_user.id}</code>\n"
            f"• <b>Waktu:</b> <code>{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</code>"
        )
        await Altruix.bot.send_message(log_chat_id, log_msg, parse_mode="html")
        await cb.message.edit("✅ Session dikirim ke pesan pribadi Anda.")
        
    except Exception as e:
        error_text = (
            "⚠️ <b>ERROR SAAT EKSPOR SESSION</b>\n\n"
            f"• User ID: <code>{user_id}</code>\n"
            f"• Session Index: <code>{index}</code>\n"
            f"• Error: <code>{str(e)}</code>"
        )
        log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))
        try:
            await Altruix.bot.send_message(log_chat_id, error_text, parse_mode="html")
        except Exception:
            pass

        await cb.message.edit("❌ Gagal mengekspor session. Owner telah diberi tahu.")
        Altruix.log(f"Error mengekspor session: {e}", level=logging.ERROR)


@Altruix.bot.on_callback_query(filters.regex("refresh_session_info_(\\d+)$"))
@log_errors
async def refresh_session_info_cb_handler(c: Client, cb: CallbackQuery):
    index = int(cb.matches[0].group(1))
    
    while len(Altruix.ourselves) <= index:
        Altruix.ourselves.append(None)

    user = await Altruix.clients[index].get_me()
    Altruix.ourselves[index] = user
    Altruix.clients[index].myself = user

    await cb.answer("Data refreshed!")
    await sessions_info_cb_handler(c, cb)


@Altruix.bot.on_callback_query(filters.regex("unlink_session_(\\d+)$"))
@log_errors
async def unlink_session_cb_handler(c: Client, cb: CallbackQuery):
    index = int(cb.matches[0].group(1))
    
    if index >= len(Altruix.clients):
        await cb.answer("Session already removed or invalid.", show_alert=True)
        return

    temp = await cb.message.reply(
        "Are you sure you want to unlink this session?",
        quote=True,
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("Yeah sure")]],
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )
    confirmation = await cb.from_user.listen(filters.text, timeout=600)
    await Altruix.bot.delete_messages(temp.chat.id, (temp.id, confirmation.id))
    temp = await temp.reply("Processing..", ReplyKeyboardRemove())
    await cb.answer("The session will be removed and restarted soon.", show_alert=True)
    await temp.delete()
    await Altruix.remove_session(index)
    cb.data = "sessions_list_1"
    await sessions_menu_cb_handler(c, cb)
