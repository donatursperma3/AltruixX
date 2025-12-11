# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix/Altruix   >
#
# This file is part of < https://github.com/Altruix/Altruix   > project,
# and is released under "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE   >
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
from pyrogram.enums import ParseMode  # PERBAIKAN: Import ParseMode untuk versi Pyrogram terbaru
import os
import logging
import asyncio
import html
from datetime import datetime
import io

# Dictionary untuk menyimpan state konfirmasi user
user_confirmation_state = {}
user_text_confirmation_state = {}

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


def arrange_buttons(array: list, no=3) -> List:
    """Mengatur tombol dalam baris dengan jumlah tertentu per baris"""
    n = int(no)
    return [array[i * n : (i + 1) * n] for i in range((len(array) + n - 1) // n)]


def get_sessions_buttons(page=1) -> Tuple[List[InlineKeyboardButton], bool, int]:
    """Mendapatkan tombol session dengan layout 6 tombol per halaman (2 baris x 3 kolom)"""
    sessions_per_page = 6  # PERUBAHAN: 6 tombol per halaman (2 baris x 3 kolom)
    
    # PERBAIKAN 1: Pastikan Altruix.clients tersedia dan memiliki properti myself
    if not hasattr(Altruix, 'clients') or not Altruix.clients:
        return [], False, 1
    
    total_sessions = len(Altruix.clients)
    total_pages = (total_sessions + sessions_per_page - 1) // sessions_per_page  # Hitung total halaman
    
    if page < 1:
        page = 1
    elif page > total_pages:
        page = total_pages if total_pages > 0 else 1
    
    # Hitung indeks mulai dan akhir untuk halaman ini
    start_index = (page - 1) * sessions_per_page
    end_index = min(start_index + sessions_per_page, total_sessions)
    
    buttons = []
    for index in range(start_index, end_index):
        client = Altruix.clients[index]
        try:
            # PERBAIKAN 2: Akses first_name dengan aman
            first_name = getattr(getattr(client, 'myself', None), 'first_name', 'Unknown')
            if not first_name or first_name == 'Unknown':
                first_name = f"Session {index + 1}"
            buttons.append(
                InlineKeyboardButton(str(first_name), f"session_info_{index}_{page}")
            )
        except AttributeError:
            buttons.append(
                InlineKeyboardButton(f"Session {index + 1}", f"session_info_{index}_{page}")
            )
    
    # PERBAIKAN 3: Pastikan arrange_buttons menerima list yang valid
    if not buttons:
        return [], False, 1
    
    # Atur tombol dalam baris dengan 3 tombol per baris
    arranged_buttons = arrange_buttons(buttons, 3)
    
    has_next = page < total_pages
    
    # PERBAIKAN 4: Kembalikan arranged_buttons sebagai list of list
    return arranged_buttons, has_next, total_pages


@Altruix.bot.on_message(
    filters.command("settings", "/") & filters.user(Altruix.auth_users)
)
@log_errors
async def settings_command_handler(c: Client, m: Message):
    total_sessions = len(Altruix.clients) if hasattr(Altruix, 'clients') else 0
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
    """Handler untuk menampilkan menu sessions dengan layout baru"""
    await cb.answer()
    try:
        page = int(cb.data.split("_")[-1])
    except (ValueError, IndexError):
        page = 1

    # Dapatkan tombol session untuk halaman ini (sudah dalam format 2 baris x 3 kolom)
    session_buttons, has_next, total_pages = get_sessions_buttons(page)
    
    # Dapatkan LOG_CHAT_ID dengan benar
    LOG_CHAT_ID = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))

    # PERUBAHAN: Susunan tombol sesuai permintaan
    # session_buttons sudah dalam format 2 baris untuk 6 tombol session
    
    # Baris 3: Tombol aksi [test ping all][add a session]
    action_buttons = [
        InlineKeyboardButton("🏓 Test Ping All", "test_ping_all_confirmation"),
        InlineKeyboardButton("➕ Add a session", "add_session")
    ]
    
    # Baris 4: Tombol export [export sessions][export phones]
    export_buttons = [
        InlineKeyboardButton("📤 Export Sessions", "export_all_sessions_confirmation"),
        InlineKeyboardButton("📲 Export Phones", "export_all_phones_confirmation")
    ]
    
    # Baris 5: Tombol navigasi [previous][back][next]
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ Previous", f"sessions_list_{page - 1}"))
    nav_buttons.append(InlineKeyboardButton(f"🔙 Back [{page}/{total_pages or 1}]", "settings_menu"))
    if has_next:
        nav_buttons.append(InlineKeyboardButton("Next ➡️", f"sessions_list_{page + 1}"))
    
    # PERBAIKAN 5: Susun final markup dengan struktur yang benar
    final_markup = []
    
    # Tambahkan session buttons (2 baris pertama)
    for row in session_buttons:
        final_markup.append(row)
    
    # Tambahkan action buttons sebagai baris ketiga
    final_markup.append(action_buttons)
    
    # Tambahkan export buttons sebagai baris keempat
    final_markup.append(export_buttons)
    
    # Tambahkan navigation buttons sebagai baris kelima
    final_markup.append(nav_buttons)
    
    total_sessions = len(Altruix.clients) if hasattr(Altruix, 'clients') else 0
    
    # Hitung range session untuk halaman ini
    sessions_per_page = 6
    start_session = ((page - 1) * sessions_per_page) + 1
    end_session = min(page * sessions_per_page, total_sessions)
    
    try:
        await cb.message.edit(
            text=f"<b>📋 Sessions List</b>\n\n"
                 f"<b>Total Sessions:</b> <code>{total_sessions}</code>\n"
                 f"<b>Showing:</b> <code>{start_session}-{end_session}</code>\n"
                 f"<b>Page:</b> <code>{page}/{total_pages or 1}</code>", 
            reply_markup=InlineKeyboardMarkup(final_markup)
        )
    except Exception as e:
        # Gunakan ParseMode.HTML untuk versi Pyrogram terbaru
        await Altruix.bot.send_message(
            LOG_CHAT_ID,
            f"⚠️ <b>SESSION MENU ERROR</b>\n"
            f"• Error: <code>{html.escape(str(e))}</code>\n"
            f"• Page: {page}\n"
            f"• Total Sessions: {total_sessions}\n"
            f"• Time: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}",
            parse_mode=ParseMode.HTML
        )
        await cb.message.edit("❌ Failed to load menu. Owner has been notified.")


# ====================== EXPORT ALL SESSIONS ======================
# TAMBAHAN: Handler untuk konfirmasi export all sessions
@Altruix.bot.on_callback_query(filters.regex("export_all_sessions_confirmation"))
@log_errors
async def export_all_sessions_confirmation_handler(c: Client, cb: CallbackQuery):
    """Handler untuk konfirmasi export all sessions"""
    await cb.answer()
    
    # Simpan state untuk user ini
    user_id = cb.from_user.id
    user_confirmation_state[user_id] = {
        'action': 'export_all_sessions',
        'message_id': cb.message.id,
        'chat_id': cb.message.chat.id
    }
    
    confirmation_buttons = [
        [
            InlineKeyboardButton("✅ Yes", callback_data="export_all_sessions_confirm_yes"),
            InlineKeyboardButton("❌ No", callback_data="export_all_sessions_confirm_no")
        ]
    ]
    
    await cb.message.edit(
        text="❓ <b>Export All Sessions Confirmation</b>\n\n"
             "Are you sure you want to export ALL session strings?\n\n"
             "⚠️ <b>WARNING:</b>\n"
             "• This will export session strings for ALL your accounts\n"
             "• Session strings can be used to login to your accounts\n"
             "• Keep them secure and DO NOT share with anyone",
        reply_markup=InlineKeyboardMarkup(confirmation_buttons),
        parse_mode=ParseMode.HTML
    )


# TAMBAHAN: Handler untuk membatalkan export all sessions
@Altruix.bot.on_callback_query(filters.regex("export_all_sessions_confirm_no"))
@log_errors
async def export_all_sessions_cancel_handler(c: Client, cb: CallbackQuery):
    """Handler untuk membatalkan export all sessions"""
    await cb.answer("Operation cancelled.")
    
    # Hapus state user
    user_id = cb.from_user.id
    if user_id in user_confirmation_state:
        del user_confirmation_state[user_id]
    
    # Kembali ke menu sessions
    await sessions_menu_cb_handler(c, cb)


# TAMBAHAN: Handler untuk konfirmasi Yes export all sessions
@Altruix.bot.on_callback_query(filters.regex("export_all_sessions_confirm_yes"))
@log_errors
async def export_all_sessions_confirm_yes_handler(c: Client, cb: CallbackQuery):
    """Handler untuk konfirmasi Yes export all sessions"""
    user = cb.from_user
    user_id = user.id
    
    # Update state untuk meminta konfirmasi teks "ok"
    if user_id in user_confirmation_state:
        user_confirmation_state[user_id]['step'] = 'waiting_text_confirmation'
        user_text_confirmation_state[user_id] = {
            'action': 'export_all_sessions',
            'message_id': cb.message.id,
            'chat_id': cb.message.chat.id,
            'timestamp': datetime.now()
        }
    
    await cb.answer()
    
    await cb.message.edit(
        text="🔐 <b>Security Verification Required</b>\n\n"
             "Please type <code>ok</code> in this chat to confirm export all sessions.\n\n"
             "⚠️ This is an additional security step to prevent accidental exports.\n"
             "⏳ You have 60 seconds to type <code>ok</code>",
        parse_mode=ParseMode.HTML
    )
    
    # Set timer untuk menghapus state setelah 60 detik
    asyncio.create_task(clear_user_state_after_timeout(user_id, 60))


# TAMBAHAN: Handler untuk menjalankan export all sessions setelah konfirmasi teks
@Altruix.bot.on_message(filters.text & filters.private & filters.user(Altruix.auth_users))
@log_errors
async def text_confirmation_handler(c: Client, m: Message):
    """Handler untuk konfirmasi teks 'ok' dari user"""
    user_id = m.from_user.id
    text = m.text.strip().lower()
    
    # Cek apakah user sedang menunggu konfirmasi teks
    if user_id in user_text_confirmation_state and text == "ok":
        action_data = user_text_confirmation_state[user_id]
        action = action_data['action']
        
        # Hapus state
        del user_text_confirmation_state[user_id]
        if user_id in user_confirmation_state:
            del user_confirmation_state[user_id]
        
        # Jalankan aksi sesuai jenis
        if action == 'export_all_sessions':
            await execute_export_all_sessions(c, m)
        elif action == 'export_all_phones':
            await execute_export_all_phones(c, m)
        else:
            await m.reply("❌ Unknown action. Please try again.")
    elif user_id in user_text_confirmation_state:
        # User mengirim teks selain "ok"
        await m.reply("❌ Invalid confirmation. Please type exactly <code>ok</code> to proceed.", 
                     parse_mode=ParseMode.HTML)


# TAMBAHAN: Fungsi untuk menjalankan export all sessions
async def execute_export_all_sessions(c: Client, m: Message):
    """Fungsi untuk mengeksekusi export all sessions"""
    user = m.from_user
    user_id = user.id
    log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))
    
    if user_id not in Altruix.auth_users:
        await m.reply("⛔ You are not authorized to use this feature.")
        return
    
    if not hasattr(Altruix, 'clients') or not Altruix.clients:
        await m.reply("❌ No sessions available to export.")
        return
    
    await m.reply("📤 Preparing to export all sessions...")
    
    try:
        # Kumpulkan data semua session
        session_data = []
        for index, client in enumerate(Altruix.clients):
            try:
                # PERBAIKAN: Gunakan try-except untuk menghindari error
                user_info = getattr(client, 'myself', None)
                if not user_info:
                    # Coba ambil info dengan get_me
                    try:
                        user_info = await client.get_me()
                    except:
                        user_info = None
                
                if user_info:
                    first_name = getattr(user_info, 'first_name', 'None')
                    last_name = getattr(user_info, 'last_name', 'None')
                    full_name = f"{first_name} {last_name}".strip()
                    username = f"@{user_info.username}" if hasattr(user_info, 'username') and user_info.username else "None"
                    phone = getattr(user_info, 'phone_number', 'Not Available')
                    
                    # Export session string
                    try:
                        session_string = await client.export_session_string()
                    except Exception as e:
                        session_string = f"Error exporting session: {str(e)}"
                    
                    session_data.append(
                        f"=== SESSION {index + 1} ===\n"
                        f"Name: {full_name}\n"
                        f"Phone: +{phone}\n"
                        f"ID: {getattr(user_info, 'id', 'Unknown')}\n"
                        f"Username: {username}\n"
                        f"DC ID: {getattr(user_info, 'dc_id', 'Unknown')}\n"
                        f"Session String:\n{session_string}\n"
                        f"{'=' * 40}\n"
                    )
                else:
                    session_data.append(
                        f"=== SESSION {index + 1} ERROR ===\n"
                        f"Error: Cannot get user info\n"
                        f"{'=' * 40}\n"
                    )
            except Exception as e:
                Altruix.log(f"Error exporting session {index}: {e}", level=logging.ERROR)
                session_data.append(
                    f"=== SESSION {index + 1} ERROR ===\n"
                    f"Error: {str(e)}\n"
                    f"{'=' * 40}\n"
                )
        
        # Buat file teks
        file_content = "⚠️ WARNING: KEEP THIS FILE SECURE! ⚠️\n"
        file_content += "These session strings can be used to login to your accounts.\n"
        file_content += "DO NOT share with anyone!\n"
        file_content += "=" * 50 + "\n\n"
        file_content += "".join(session_data)
        
        file_stream = io.BytesIO(file_content.encode())
        file_stream.name = f"all_sessions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        # Kirim file ke user
        await c.send_document(
            chat_id=user_id,
            document=file_stream,
            caption="📤 **All Sessions Exported**\n\n"
                   "⚠️ **SECURITY WARNING:**\n"
                   "• Keep this file secure\n"
                   "• Do not share with anyone\n"
                   "• Store in a safe location",
            parse_mode=ParseMode.HTML
        )
        
        # Kirim notifikasi ke log group
        await Altruix.bot.send_message(
            log_chat_id,
            f"📤 <b>EXPORT ALL SESSIONS COMPLETED</b>\n"
            f"• User: <a href='tg://user?id={user.id}'>{html.escape(user.first_name)}</a>\n"
            f"• User ID: <code>{user.id}</code>\n"
            f"• Total Sessions: <code>{len(Altruix.clients)}</code>\n"
            f"• Time: <code>{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</code>\n"
            f"• Status: ✅ Success",
            parse_mode=ParseMode.HTML,
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
        
        await m.reply("✅ All session files have been sent to your private messages.")
        
    except FloodWait as e:
        await asyncio.sleep(e.value)
        await m.reply(f"⏳ FloodWait detected. Please wait {e.value} seconds and try again.")
        
        # Log error
        await Altruix.bot.send_message(
            log_chat_id,
            f"⚠️ <b>EXPORT ALL SESSIONS FLOODWAIT</b>\n"
            f"• User: <a href='tg://user?id={user.id}'>{html.escape(user.first_name)}</a>\n"
            f"• FloodWait: {e.value} seconds\n"
            f"• Time: <code>{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</code>",
            parse_mode=ParseMode.HTML
        )
        
    except (PeerIdInvalid, UserIsBlocked, ChatWriteForbidden) as e:
        error_msg = "❌ Failed to send file: Cannot send message to user."
        await m.reply(error_msg)
        
        # Log error
        await Altruix.bot.send_message(
            log_chat_id,
            f"⚠️ <b>EXPORT ALL SESSIONS PERMISSION ERROR</b>\n"
            f"• User: <a href='tg://user?id={user.id}'>{html.escape(user.first_name)}</a>\n"
            f"• Error: <code>{type(e).__name__}</code>\n"
            f"• Solution: User must start chat with bot assistant.",
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        await m.reply("❌ Failed to export sessions. Owner has been notified.")
        Altruix.log(f"General error exporting all sessions: {e}", level=logging.ERROR)
        
        # Log detailed error
        await Altruix.bot.send_message(
            log_chat_id,
            f"⚠️ <b>EXPORT ALL SESSIONS CRITICAL ERROR</b>\n"
            f"• User: <a href='tg://user?id={user.id}'>{html.escape(user.first_name)}</a>\n"
            f"• Error: <code>{html.escape(str(e))}</code>\n"
            f"• Time: <code>{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</code>",
            parse_mode=ParseMode.HTML
        )


# ====================== EXPORT ALL PHONES (DIPERBARUI) ======================
# PERUBAHAN: Ubah handler export all phones menjadi konfirmasi
@Altruix.bot.on_callback_query(filters.regex("export_all_phones_confirmation"))
@log_errors
async def export_all_phones_confirmation_handler(c: Client, cb: CallbackQuery):
    """Handler untuk konfirmasi export all phones"""
    await cb.answer()
    
    # Simpan state untuk user ini
    user_id = cb.from_user.id
    user_confirmation_state[user_id] = {
        'action': 'export_all_phones',
        'message_id': cb.message.id,
        'chat_id': cb.message.chat.id
    }
    
    confirmation_buttons = [
        [
            InlineKeyboardButton("✅ Yes", callback_data="export_all_phones_confirm_yes"),
            InlineKeyboardButton("❌ No", callback_data="export_all_phones_confirm_no")
        ]
    ]
    
    await cb.message.edit(
        text="❓ <b>Export All Phone Numbers Confirmation</b>\n\n"
             "Are you sure you want to export ALL phone numbers?\n\n"
             "⚠️ <b>NOTE:</b>\n"
             "• This will export phone numbers for ALL your accounts\n"
             "• Phone numbers are sensitive information\n"
             "• Keep them secure and share only with trusted parties",
        reply_markup=InlineKeyboardMarkup(confirmation_buttons),
        parse_mode=ParseMode.HTML
    )


# PERUBAHAN: Handler untuk membatalkan export all phones
@Altruix.bot.on_callback_query(filters.regex("export_all_phones_confirm_no"))
@log_errors
async def export_all_phones_cancel_handler(c: Client, cb: CallbackQuery):
    """Handler untuk membatalkan export all phones"""
    await cb.answer("Operation cancelled.")
    
    # Hapus state user
    user_id = cb.from_user.id
    if user_id in user_confirmation_state:
        del user_confirmation_state[user_id]
    
    # Kembali ke menu sessions
    await sessions_menu_cb_handler(c, cb)


# PERUBAHAN: Handler untuk konfirmasi Yes export all phones
@Altruix.bot.on_callback_query(filters.regex("export_all_phones_confirm_yes"))
@log_errors
async def export_all_phones_confirm_yes_handler(c: Client, cb: CallbackQuery):
    """Handler untuk konfirmasi Yes export all phones"""
    user = cb.from_user
    user_id = user.id
    
    # Update state untuk meminta konfirmasi teks "ok"
    if user_id in user_confirmation_state:
        user_confirmation_state[user_id]['step'] = 'waiting_text_confirmation'
        user_text_confirmation_state[user_id] = {
            'action': 'export_all_phones',
            'message_id': cb.message.id,
            'chat_id': cb.message.chat.id,
            'timestamp': datetime.now()
        }
    
    await cb.answer()
    
    await cb.message.edit(
        text="🔐 <b>Security Verification Required</b>\n\n"
             "Please type <code>ok</code> in this chat to confirm export all phone numbers.\n\n"
             "⚠️ This is an additional security step to prevent accidental exports.\n"
             "⏳ You have 60 seconds to type <code>ok</code>",
        parse_mode=ParseMode.HTML
    )
    
    # Set timer untuk menghapus state setelah 60 detik
    asyncio.create_task(clear_user_state_after_timeout(user_id, 60))


# PERUBAHAN: Fungsi untuk menjalankan export all phones
async def execute_export_all_phones(c: Client, m: Message):
    """Fungsi untuk mengeksekusi export all phones"""
    user = m.from_user
    user_id = user.id
    log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))
    
    if user_id not in Altruix.auth_users:
        await m.reply("⛔ You are not authorized to use this feature.")
        return
    
    if not hasattr(Altruix, 'clients') or not Altruix.clients:
        await m.reply("❌ No sessions available to export.")
        return
    
    await m.reply("📲 Preparing to export all phone numbers...")
    
    try:
        # Kumpulkan data semua session
        phone_data = []
        for index, client in enumerate(Altruix.clients):
            try:
                # PERBAIKAN: Gunakan getattr untuk menghindari error
                user_info = getattr(client, 'myself', None)
                if not user_info:
                    # Coba ambil info dengan get_me
                    try:
                        user_info = await client.get_me()
                    except:
                        user_info = None
                
                if user_info:
                    first_name = getattr(user_info, 'first_name', 'None')
                    last_name = getattr(user_info, 'last_name', 'None')
                    full_name = f"{first_name} {last_name}".strip()
                    username = f"@{user_info.username}" if hasattr(user_info, 'username') and user_info.username else "None"
                    phone = getattr(user_info, 'phone_number', 'Not Available')
                    user_id_info = getattr(user_info, 'id', 'Unknown')
                    
                    phone_data.append(
                        f"=== ACCOUNT {index + 1} ===\n"
                        f"Name: {full_name}\n"
                        f"Phone: +{phone}\n"
                        f"ID: {user_id_info}\n"
                        f"Username: {username}\n"
                        f"DC ID: {getattr(user_info, 'dc_id', 'Unknown')}\n"
                        f"{'=' * 40}\n"
                    )
                else:
                    phone_data.append(f"=== ACCOUNT {index + 1} ERROR ===\nCannot get user info\n{'=' * 40}\n")
            except Exception as e:
                Altruix.log(f"Error getting session info {index}: {e}", level=logging.ERROR)
                phone_data.append(f"=== ACCOUNT {index + 1} ERROR ===\nError: {str(e)}\n{'=' * 40}\n")
        
        # Buat file teks
        file_content = "⚠️ Phone numbers are sensitive information. Keep secure!\n"
        file_content += "=" * 50 + "\n\n"
        file_content += "".join(phone_data)
        
        file_stream = io.BytesIO(file_content.encode())
        file_stream.name = f"all_phone_numbers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        # Kirim file ke user
        await c.send_document(
            chat_id=user_id,
            document=file_stream,
            caption="📲 **All Phone Numbers Exported**\n\n"
                   "⚠️ Keep this information secure.",
            parse_mode=ParseMode.HTML
        )
        
        # Kirim notifikasi ke log group
        await Altruix.bot.send_message(
            log_chat_id,
            f"📲 <b>EXPORT ALL PHONES COMPLETED</b>\n"
            f"• User: <a href='tg://user?id={user.id}'>{html.escape(user.first_name)}</a>\n"
            f"• User ID: <code>{user.id}</code>\n"
            f"• Total Sessions: <code>{len(Altruix.clients)}</code>\n"
            f"• Time: <code>{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</code>\n"
            f"• Status: ✅ Success",
            parse_mode=ParseMode.HTML,
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
        
        await m.reply("✅ All phone number files have been sent to your private messages.")
        
    except FloodWait as e:
        await asyncio.sleep(e.value)
        await m.reply(f"⏳ FloodWait detected. Please wait {e.value} seconds and try again.")
        
        # Log error
        await Altruix.bot.send_message(
            log_chat_id,
            f"⚠️ <b>EXPORT ALL PHONES FLOODWAIT</b>\n"
            f"• User: <a href='tg://user?id={user.id}'>{html.escape(user.first_name)}</a>\n"
            f"• FloodWait: {e.value} seconds\n"
            f"• Time: <code>{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</code>",
            parse_mode=ParseMode.HTML
        )
        
    except (PeerIdInvalid, UserIsBlocked, ChatWriteForbidden) as e:
        error_msg = "❌ Failed to send file: Cannot send message to user."
        await m.reply(error_msg)
        
        # Log error
        await Altruix.bot.send_message(
            log_chat_id,
            f"⚠️ <b>EXPORT ALL PHONES PERMISSION ERROR</b>\n"
            f"• User: <a href='tg://user?id={user.id}'>{html.escape(user.first_name)}</a>\n"
            f"• Error: <code>{type(e).__name__}</code>\n"
            f"• Solution: User must start chat with bot assistant.",
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        await m.reply("❌ Failed to export phone numbers. Owner has been notified.")
        Altruix.log(f"General error exporting all phones: {e}", level=logging.ERROR)
        
        # Log detailed error
        await Altruix.bot.send_message(
            log_chat_id,
            f"⚠️ <b>EXPORT ALL PHONES CRITICAL ERROR</b>\n"
            f"• User: <a href='tg://user?id={user.id}'>{html.escape(user.first_name)}</a>\n"
            f"• Error: <code>{html.escape(str(e))}</code>\n"
            f"• Time: <code>{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</code>",
            parse_mode=ParseMode.HTML
        )


# ====================== FUNGSI BANTUAN ======================
async def clear_user_state_after_timeout(user_id: int, timeout: int):
    """Menghapus state user setelah timeout"""
    await asyncio.sleep(timeout)
    
    if user_id in user_text_confirmation_state:
        # Cek jika sudah lewat timeout
        state_data = user_text_confirmation_state[user_id]
        time_elapsed = (datetime.now() - state_data['timestamp']).total_seconds()
        
        if time_elapsed >= timeout:
            del user_text_confirmation_state[user_id]
            if user_id in user_confirmation_state:
                del user_confirmation_state[user_id]
            
            # Coba kirim notifikasi timeout ke user
            try:
                chat_id = state_data.get('chat_id')
                message_id = state_data.get('message_id')
                
                if chat_id and message_id:
                    await Altruix.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text="⏰ <b>Confirmation Timeout</b>\n\n"
                             "The confirmation period has expired. Please try again if you still want to proceed.",
                        parse_mode=ParseMode.HTML
                    )
            except Exception:
                pass


# ====================== HANDLER YANG SUDAH ADA (DIPERTAHANKAN) ======================
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
    total_sessions = len(Altruix.clients) if hasattr(Altruix, 'clients') else 0
    
    if total_sessions == 0:
        await cb.message.edit("❌ No sessions available to ping.")
        return

    await cb.message.edit(f"✅ Starting ping test for <b>{total_sessions}</b> sessions...")
    
    for index, client in enumerate(Altruix.clients):
        try:
            session_user = getattr(client, 'myself', None)
            if not session_user:
                # Coba ambil info dengan get_me
                try:
                    session_user = await client.get_me()
                except:
                    session_user = None
            
            if session_user:
                first_name = getattr(session_user, 'first_name', 'Unknown')
                user_id = getattr(session_user, 'id', 'Unknown')
                
                await client.send_message(
                    chat_id=log_chat_id,
                    text=f"🏓 <b>Pong!</b>\nDari akun: <a href='tg://user?id={user_id}'>{html.escape(first_name)}</a> | ID: <code>{user_id}</code>",
                    parse_mode=ParseMode.HTML,
                    link_preview_options=LinkPreviewOptions(is_disabled=True)
                )
                success_count += 1
            else:
                failed_count += 1
                
        except FloodWait as e:
            await asyncio.sleep(e.value)
            try:
                if session_user:
                    await client.send_message(
                        chat_id=log_chat_id,
                        text=f"🏓 <b>Pong!</b>\nDari akun: <a href='tg://user?id={session_user.id}'>{html.escape(session_user.first_name or 'Unknown')}</a> | ID: <code>{session_user.id}</code>",
                        parse_mode=ParseMode.HTML,
                        link_preview_options=LinkPreviewOptions(is_disabled=True)
                    )
                    success_count += 1
                else:
                    failed_count += 1
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
        parse_mode=ParseMode.HTML,
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

    # PERBAIKAN: Gunakan getattr untuk menghindari error
    session_client = Altruix.clients[index]
    session_info = getattr(session_client, 'myself', None)
    
    if not session_info:
        # Coba ambil info dengan get_me
        try:
            session_info = await session_client.get_me()
        except Exception as e:
            await cb.message.edit(f"Error getting session info: {str(e)}")
            return

    is_scam = getattr(
        getattr(session_info, 'verification_status', session_info),
        'is_scam',
        False
    )

    first_name = getattr(session_info, 'first_name', 'None')
    last_name = getattr(session_info, 'last_name', 'None')
    dc_id = getattr(session_info, 'dc_id', 'Unknown')
    username = getattr(session_info, 'username', 'None')
    user_id = getattr(session_info, 'id', 'Unknown')

    txt = (
        "<b>Session info</b>\n\n"
        "<b>First name:</b> {}\n"
        "<b>Last name:</b> {}\n"
        "<b>DC ID:</b> <code>{}</code>\n"
        "<b>Username:</b> @{}\n"
        "<b>User ID:</b> <code>{}</code>\n"
        "<b>Is SCAM:</b> <code>{}</code>"
    ).format(
        first_name or "None",
        last_name or "None",
        dc_id or "Unknown",
        username or "None",
        user_id,
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
    session_user = getattr(session_client, 'myself', None)
    
    if not session_user:
        # Coba ambil info dengan get_me
        try:
            session_user = await session_client.get_me()
        except Exception as e:
            await cb.answer(f"Error getting session info: {str(e)}", show_alert=True)
            return

    try:
        await session_client.send_message(
            chat_id=log_chat_id,
            text=(
                f"🏓 <b>Pong!</b>\n"
                f"• User: <a href='tg://user?id={user.id}'>{html.escape(user.first_name)}</a> melakukan test ping pada akun: "
                f"<a href='tg://user?id={session_user.id}'>{html.escape(session_user.first_name or '')} {html.escape(session_user.last_name or '')}</a>\n"
                f"• Tanggal: <code>{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</code>"
            ),
            parse_mode=ParseMode.HTML,
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
        
        await cb.message.edit(
            f"✅ Ping berhasil! Pesan dikirim ke grup log.\n"
            f"Akun: <a href='tg://user?id={session_user.id}'>{html.escape(session_user.first_name or '')} {html.escape(session_user.last_name or '')}</a>",
            parse_mode=ParseMode.HTML
        )
        
        Altruix.log(f"Test ping sukses untuk session {index} ({getattr(session_user, 'id', 'Unknown')})")

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
                f"• Session: <a href='tg://user?id={session_user.id}'>{html.escape(session_user.first_name or '')} {html.escape(session_user.last_name or '')}</a> (<code>{getattr(session_user, 'id', 'Unknown')}</code>)\n"
                f"• Error: <code>{type(e).__name__}</code>\n"
                f"• Solusi: Pastikan bot assistant dan userbot berada di group dan bisa mengirim pesan ke grup log.",
                parse_mode=ParseMode.HTML
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
                parse_mode=ParseMode.HTML
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
                f"• Session: <a href='tg://user?id={session_user.id}'>{html.escape(session_user.first_name or '')} {html.escape(session_user.last_name or '')}</a> (<code>{getattr(session_user, 'id', 'Unknown')}</code>)\n"
                f"• Error: <code>{html.escape(str(e))}</code>\n"
                f"• Waktu: <code>{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</code>",
                parse_mode=ParseMode.HTML
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
        await Altruix.bot.send_message(log_chat_id, log_msg, parse_mode=ParseMode.HTML)
        await cb.message.edit("✅ Nomor telepon dikirim ke pesan pribadi Anda.")
        
    except Exception as e:
        error_text = (
            "⚠️ <b>ERROR SAAT EKSPOR NOMOR TELEPON</b>\n\n"
            f"• User ID: <code>{user_id}</code>\n"
            f"• Session Index: <code>{index}</code>\n"
            f"• Error: <code>{html.escape(str(e))}</code>"
        )
        log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))
        try:
            await Altruix.bot.send_message(log_chat_id, error_text, parse_mode=ParseMode.HTML)
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
        await Altruix.bot.send_message(log_chat_id, log_msg, parse_mode=ParseMode.HTML)
        await cb.message.edit("✅ Session dikirim ke pesan pribadi Anda.")
        
    except Exception as e:
        error_text = (
            "⚠️ <b>ERROR SAAT EKSPOR SESSION</b>\n\n"
            f"• User ID: <code>{user_id}</code>\n"
            f"• Session Index: <code>{index}</code>\n"
            f"• Error: <code>{html.escape(str(e))}</code>"
        )
        log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))
        try:
            await Altruix.bot.send_message(log_chat_id, error_text, parse_mode=ParseMode.HTML)
        except Exception:
            pass

        await cb.message.edit("❌ Gagal mengekspor session. Owner telah diberi tahu.")
        Altruix.log(f"Error mengekspor session: {e}", level=logging.ERROR)


@Altruix.bot.on_callback_query(filters.regex("refresh_session_info_(\\d+)$"))
@log_errors
async def refresh_session_info_cb_handler(c: Client, cb: CallbackQuery):
    index = int(cb.matches[0].group(1))
    
    # PERBAIKAN: Pastikan Altruix.ourselves ada dan cukup panjang
    if not hasattr(Altruix, 'ourselves'):
        Altruix.ourselves = []
    
    while len(Altruix.ourselves) <= index:
        Altruix.ourselves.append(None)

    try:
        user = await Altruix.clients[index].get_me()
        Altruix.ourselves[index] = user
        Altruix.clients[index].myself = user
    except Exception as e:
        await cb.answer(f"Error refreshing data: {str(e)}", show_alert=True)
        return

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
