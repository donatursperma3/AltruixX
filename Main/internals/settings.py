# settings.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix/Altruix   >
#
# This file is part of < https://github.com/Altruix/Altruix   > project,
# and is released under "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE   >
#
# All rights reserved.

from Main import Altruix
from typing import List, Tuple, Dict, Any
from pyrogram import Client, filters
from Main.core.decorators import log_errors
from Main.core.types.message import Message
from pyrogram.types import (
    CallbackQuery, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove,
    InlineKeyboardButton, InlineKeyboardMarkup, LinkPreviewOptions, User
)

# ====================== PERBAIKAN IMPORT ERROR ======================
# Import semua error yang tersedia di Pyrogram
from pyrogram.errors import (
    PeerIdInvalid, UserIsBlocked, ChatWriteForbidden, FloodWait, MessageIdInvalid,
    SlowmodeWait, InviteHashInvalid, InviteHashExpired, UserAlreadyParticipant,
    ChatAdminRequired, UsernameNotOccupied, ChannelPrivate, UsernameInvalid,
    UsernameNotModified, AboutTooLong, PhotoInvalidDimensions,
    PhotoSaveFileInvalid, UsernameOccupied
)

# Handle FirstNameInvalid yang mungkin tidak ada di beberapa versi Pyrogram
try:
    from pyrogram.errors import FirstNameInvalid
except ImportError:
    # Buat kelas dummy jika FirstNameInvalid tidak ada
    class FirstNameInvalid(Exception):
        pass

# ✅ IMPORT BARU UNTUK CEK LIMIT
from pyrogram.errors import UserIsBlocked as BotBlocked  # Alias agar tidak bentrok

from pyrogram.enums import ParseMode
import os
import logging
import asyncio
import html
from datetime import datetime
import io
import re

plugin_name = f"plugins/userbot/{os.path.basename(__file__)}"
__plugin_name__ = plugin_name if plugin_name else "settings"
PLUGIN_VERSION = "0.1.1.1"  # 🔥 VERSI DIPERBAIKI: Semua error fixed

# 🔥 SETUP LOGGING DETAILED
logger = logging.getLogger(f"{__plugin_name__}")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - [MENTIONS] - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

# 🔥 LOG STARTUP
logger.info(f"🚀 Initializing mentions plugin v{PLUGIN_VERSION}")

# Dictionary untuk menyimpan state konfirmasi user
user_confirmation_state = {}
user_text_confirmation_state = {}
user_bulk_join_state = {}  # State untuk bulk join
user_profile_edit_state = {}  # ✅ BARU: State untuk edit profil
user_photo_delete_state = {}  # ✅ BARU: State untuk hapus foto profil
user_edit_confirmation_state = {}  # ✅ BARU: State untuk konfirmasi edit profil

# ✅ TAMBAHAN STATE UNTUK CEK LIMIT (per session)
user_limit_check_state = {}  # {user_id: {'session_index': int, 'page': int}}

settings_menu_buttons = [
    [
        InlineKeyboardButton("Sessions", callback_data="sessions_list_1"),
        InlineKeyboardButton("Configs", callback_data="configs_home"),
    ],
]

# ✅ FUNGSI BARU: Kirim notifikasi ke log group
async def send_log_notification(
    c: Client, 
    action: str, 
    session_index: int, 
    user: Any, 
    success: bool, 
    error_msg: str = None,
    additional_info: Dict[str, Any] = None
):
    """Mengirim notifikasi ke log group untuk semua aksi"""
    try:
        log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))
        
        if session_index >= len(Altruix.clients):
            return
        
        session_client = Altruix.clients[session_index]
        session_info = getattr(session_client, 'myself', None)
        if not session_info:
            try:
                session_info = await session_client.get_me()
            except:
                session_info = None
        
        # Map action to readable text
        action_map = {
            'change_first_name': 'Ganti Nama Depan',
            'change_last_name': 'Ganti Nama Belakang',
            'change_bio': 'Ganti Bio',
            'change_username': 'Ganti Username',
            'change_profile_photo': 'Ganti Foto Profil',
            'view_all_sessions': 'Lihat Sesi Login',
            'delete_all_profile_photos': 'Hapus Semua Foto Profil',
            'test_ping': 'Test Ping',
            'export_phone': 'Export Phone',
            'export_session': 'Export Session',
            'join_log_group': 'Join Log Group'
        }
        
        action_text = action_map.get(action, action)
        status = "✅ BERHASIL" if success else "❌ GAGAL"
        timestamp = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
        
        # Buat pesan log
        log_message = (
            f"📢 <b>AKSI PROFIL - {action_text}</b>\n"
            f"• Status: <b>{status}</b>\n"
            f"• User: <a href='tg://user?id={user.id}'>{html.escape(user.first_name)}</a>\n"
            f"• User ID: <code>{user.id}</code>\n"
        )
        
        if session_info:
            log_message += (
                f"• Akun: <a href='tg://user?id={session_info.id}'>{html.escape(session_info.first_name or '')}</a>\n"
                f"• Akun ID: <code>{session_info.id}</code>\n"
            )
        
        if additional_info:
            for key, value in additional_info.items():
                if value and str(value).strip():
                    log_message += f"• {key}: <code>{html.escape(str(value))}</code>\n"
        
        if error_msg:
            log_message += f"• Error: <code>{html.escape(error_msg)}</code>\n"
        
        log_message += f"• Waktu: <code>{timestamp}</code>"
        
        # Kirim ke log group
        await Altruix.bot.send_message(
            log_chat_id,
            log_message,
            parse_mode=ParseMode.HTML,
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
        
    except Exception as e:
        Altruix.log(f"Error sending log notification: {e}", level=logging.ERROR)


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
    """Mendapatkan tombol session dengan layout 9 tombol per halaman (3 baris x 3 kolom)"""
    sessions_per_page = 9  # PERUBAHAN: 9 tombol per halaman (3 baris x 3 kolom)
    
    if not hasattr(Altruix, 'clients') or not Altruix.clients:
        return [], False, 1
    
    total_sessions = len(Altruix.clients)
    total_pages = (total_sessions + sessions_per_page - 1) // sessions_per_page
    
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
            # PERBAIKAN: Akses first_name dengan aman
            session_num = index + 1  # Nomor session (dimulai dari 1)
            first_name = getattr(getattr(client, 'myself', None), 'first_name', 'Unknown')
            if not first_name or first_name == 'Unknown':
                first_name = f"Session {session_num}"
            # PERUBAHAN: Format tombol dengan nomor: [[1] Nama Akun]
            button_text = f"[{session_num}] {first_name[:15]}" if len(first_name) > 15 else f"[{session_num}] {first_name}"
            buttons.append(
                InlineKeyboardButton(button_text, f"session_info_{index}_{page}")
            )
        except AttributeError:
            button_text = f"[{index + 1}] Session {index + 1}"
            buttons.append(
                InlineKeyboardButton(button_text, f"session_info_{index}_{page}")
            )
    
    if not buttons:
        return [], False, 1
    
    # Atur tombol dalam baris dengan 3 tombol per baris
    arranged_buttons = arrange_buttons(buttons, 3)
    
    has_next = page < total_pages
    
    return arranged_buttons, has_next, total_pages


@Altruix.bot.on_message(
    filters.command("settings", "/") & filters.user(Altruix.auth_users)
)
@log_errors
async def settings_command_handler(c: Client, m: Message):
    """Handler untuk command /settings"""
    try:
        total_sessions = len(Altruix.clients) if hasattr(Altruix, 'clients') else 0
        settings_text = Altruix.get_string("SETTINGS_TEXT") or "<b>🛠️ Settings</b>"
        full_text = f"{settings_text}\n\n<b>Total Sessions:</b> <code>{total_sessions}</code>"
        
        await m.reply(
            full_text,
            reply_markup=InlineKeyboardMarkup(settings_menu_buttons),
            quote=True,
        )
        logging.info(f"User {m.from_user.id} used /settings command")
    except Exception as e:
        logging.error(f"Error in settings_command_handler: {e}")
        await m.reply("❌ Terjadi error saat memproses command.")


@Altruix.bot.on_callback_query(filters.regex("sessions_list_(\\d+)$"))
@log_errors
async def sessions_menu_cb_handler(c: Client, cb: CallbackQuery):
    """Handler untuk menampilkan menu sessions dengan layout baru"""
    await cb.answer()
    try:
        page = int(cb.data.split("_")[-1])
    except (ValueError, IndexError):
        page = 1

    # Dapatkan tombol session untuk halaman ini (sudah dalam format 3 baris x 3 kolom)
    session_buttons, has_next, total_pages = get_sessions_buttons(page)
    
    # Dapatkan LOG_CHAT_ID dengan benar
    LOG_CHAT_ID = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))

    # PERUBAHAN: Susunan tombol sesuai permintaan baru
    # session_buttons sudah dalam format 3 baris untuk 9 tombol session
    
    # Baris 4: Tombol aksi [Test Ping All][Bulk Join][Add a Session]
    action_buttons = [
        InlineKeyboardButton("🏓 Tes Ping All", "test_ping_all_confirmation"),
        InlineKeyboardButton("👥 Bulk Join", "bulk_join_menu"),
        InlineKeyboardButton("➕ Add a Session", "add_session")
    ]
    
    # Baris 5: Tombol export [Export Sessions][Export Phones]
    export_buttons = [
        InlineKeyboardButton("📤 Export Sessions", "export_all_sessions_confirmation"),
        InlineKeyboardButton("📲 Export Phones", "export_all_phones_confirmation")
    ]
    
    # Baris 6: Tombol navigasi [Previous][Back][Next]
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ Previous", f"sessions_list_{page - 1}"))
    nav_buttons.append(InlineKeyboardButton(f"🔙 Back [{page}/{total_pages or 1}]", "settings_menu"))
    if has_next:
        nav_buttons.append(InlineKeyboardButton("Next ➡️", f"sessions_list_{page + 1}"))
    
    # Susun final markup dengan struktur yang benar
    final_markup = []
    
    # Tambahkan session buttons (3 baris pertama)
    for row in session_buttons:
        final_markup.append(row)
    
    # Tambahkan action buttons sebagai baris keempat
    final_markup.append(action_buttons)
    
    # Tambahkan export buttons sebagai baris kelima
    final_markup.append(export_buttons)
    
    # Tambahkan navigation buttons sebagai baris keenam
    final_markup.append(nav_buttons)
    
    total_sessions = len(Altruix.clients) if hasattr(Altruix, 'clients') else 0
    
    # Hitung range session untuk halaman ini
    sessions_per_page = 9
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


# ====================== BULK JOIN FEATURE ======================
@Altruix.bot.on_callback_query(filters.regex("bulk_join_menu"))
@log_errors
async def bulk_join_menu_handler(c: Client, cb: CallbackQuery):
    """Handler untuk menu bulk join"""
    await cb.answer()
    
    # Tampilkan pilihan delay
    delay_buttons = [
        [
            InlineKeyboardButton("2 detik", callback_data="bulk_join_delay_2"),
            InlineKeyboardButton("4 detik", callback_data="bulk_join_delay_4"),
            InlineKeyboardButton("6 detik", callback_data="bulk_join_delay_6"),
        ],
        [
            InlineKeyboardButton("8 detik", callback_data="bulk_join_delay_8"),
            InlineKeyboardButton("10 detik", callback_data="bulk_join_delay_10"),
            InlineKeyboardButton("15 detik", callback_data="bulk_join_delay_15"),
        ],
        [
            InlineKeyboardButton("20 detik", callback_data="bulk_join_delay_20"),
            InlineKeyboardButton("30 detik", callback_data="bulk_join_delay_30"),
            InlineKeyboardButton("60 detik", callback_data="bulk_join_delay_60"),
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="sessions_list_1"),
        ]
    ]
    
    await cb.message.edit(
        text="<b>👥 Bulk Join Settings</b>\n\n"
             "Pilih jeda waktu antara join (untuk menghindari flood wait):\n\n"
             "⚠️ <b>Note:</b>\n"
             "• Delay yang lebih besar mengurangi risiko flood wait\n"
             "• Delay yang lebih kecil lebih cepat tapi berisiko",
        reply_markup=InlineKeyboardMarkup(delay_buttons)
    )


@Altruix.bot.on_callback_query(filters.regex("bulk_join_delay_(\\d+)"))
@log_errors
async def bulk_join_delay_handler(c: Client, cb: CallbackQuery):
    """Handler untuk memilih delay bulk join"""
    await cb.answer()
    
    try:
        delay = int(cb.matches[0].group(1))
    except (ValueError, IndexError):
        delay = 5
    
    user_id = cb.from_user.id
    user_bulk_join_state[user_id] = {
        'delay': delay,
        'link': None,
        'step': 'waiting_link'
    }
    
    await cb.message.edit(
        text=f"<b>👥 Bulk Join - Delay {delay} detik</b>\n\n"
             "Silakan kirim link grup yang akan di-join:\n\n"
             "🔗 <b>Format Link:</b>\n"
             "• https://t.me/username (public group/channel)\n"
             "• https://t.me/+invitehash (private group)\n"
             "• @username (tanpa https://)\n\n"
             "❌ <b>Cancel:</b> Ketik /cancel",
        parse_mode=ParseMode.HTML
    )


# ✅ PERUBAHAN: Handler untuk menerima input teks (dengan konfirmasi)
@Altruix.bot.on_message(filters.text & filters.private & filters.user(Altruix.auth_users))
@log_errors
async def user_text_handler(c: Client, m: Message):
    """Handler untuk menerima input teks dari user (dengan konfirmasi)"""
    user_id = m.from_user.id
    text = m.text.strip()
    
    # ✅ PERUBAHAN: Cek jika user sedang dalam konfirmasi edit profil
    if user_id in user_edit_confirmation_state:
        state = user_edit_confirmation_state[user_id]
        
        if text.lower() == "ya":
            # Proses aksi yang sudah ditentukan
            session_index = state['session_index']
            page = state.get('page', 1)
            action = state['action']
            data = state['data']
            
            # Hapus state
            del user_edit_confirmation_state[user_id]
            
            if session_index >= len(Altruix.clients):
                await m.reply("❌ Session tidak ditemukan.")
                return
            
            session_client = Altruix.clients[session_index]
            
            try:
                old_info = await session_client.get_me()
                success = False
                error_msg = None
                additional_info = {}
                
                if action == 'change_first_name':
                    # Update first name
                    await session_client.update_profile(first_name=data)
                    success = True
                    additional_info = {
                        'Nama Lama': old_info.first_name,
                        'Nama Baru': data
                    }
                    await m.reply(f"✅ Nama depan berhasil diubah menjadi: <code>{html.escape(data)}</code>")
                    
                elif action == 'change_last_name':
                    # Update last name (bisa kosong untuk menghapus)
                    if data.lower() == "kosong" or data == "":
                        await session_client.update_profile(last_name="")
                        success = True
                        additional_info = {
                            'Nama Belakang Lama': old_info.last_name or 'Kosong',
                            'Nama Belakang Baru': 'Dihapus'
                        }
                        await m.reply("✅ Nama belakang berhasil dihapus.")
                    else:
                        await session_client.update_profile(last_name=data)
                        success = True
                        additional_info = {
                            'Nama Belakang Lama': old_info.last_name,
                            'Nama Belakang Baru': data
                        }
                        await m.reply(f"✅ Nama belakang berhasil diubah menjadi: <code>{html.escape(data)}</code>")
                        
                elif action == 'change_bio':
                    # Update bio
                    await session_client.update_profile(bio=data)
                    success = True
                    additional_info = {
                        'Bio Lama': old_info.bio or 'Kosong',
                        'Bio Baru': data
                    }
                    await m.reply(f"✅ Bio berhasil diubah menjadi: <code>{html.escape(data)}</code>")
                    
                elif action == 'change_username':
                    # Update username
                    username = data.replace("@", "")
                    try:
                        await session_client.update_username(username)
                        success = True
                        additional_info = {
                            'Username Lama': old_info.username or 'Kosong',
                            'Username Baru': username
                        }
                        await m.reply(f"✅ Username berhasil diubah menjadi: @{html.escape(username)}")
                    except UsernameOccupied:
                        error_msg = "Username sudah digunakan"
                        await m.reply(f"❌ Username @{html.escape(username)} sudah digunakan.")
                    except UsernameInvalid as e:
                        error_msg = str(e)
                        await m.reply(f"❌ Username tidak valid: {str(e)}")
                    except Exception as e:
                        error_msg = str(e)
                        await m.reply(f"❌ Error: {str(e)}")
                        
            except FirstNameInvalid as e:
                error_msg = f"Nama tidak valid: {str(e)}"
                await m.reply(f"❌ Nama tidak valid: {str(e)}")
            except AboutTooLong as e:
                error_msg = f"Bio terlalu panjang: {str(e)}"
                await m.reply(f"❌ Bio terlalu panjang: {str(e)}")
            except FloodWait as e:
                error_msg = f"FloodWait {e.value} detik"
                await m.reply(f"⏳ FloodWait: Tunggu {e.value} detik sebelum mencoba lagi.")
            except Exception as e:
                error_msg = str(e)
                await m.reply(f"❌ Error: {str(e)}")
                Altruix.log(f"Error updating profile: {e}", level=logging.ERROR)
            finally:
                # Kirim notifikasi ke log group
                await send_log_notification(
                    c, action, session_index, m.from_user, 
                    success, error_msg, additional_info
                )
                
                # Kembali ke info session
                try:
                    await asyncio.sleep(1)
                    cb_obj = CallbackQuery(
                        id="temp",
                        from_user=m.from_user,
                        message=m,
                        chat_instance="temp",
                        data=f"session_info_{session_index}_{page}"
                    )
                    await sessions_info_cb_handler(c, cb_obj)
                except Exception:
                    pass
        
        elif text.lower() == "tidak":
            # Batalkan aksi
            del user_edit_confirmation_state[user_id]
            await m.reply("❌ Aksi dibatalkan.")
            
            # Kembali ke info session
            session_index = state['session_index']
            page = state.get('page', 1)
            try:
                cb_obj = CallbackQuery(
                    id="temp",
                    from_user=m.from_user,
                    message=m,
                    chat_instance="temp",
                    data=f"session_info_{session_index}_{page}"
                )
                await sessions_info_cb_handler(c, cb_obj)
            except Exception:
                pass
        else:
            await m.reply("❌ Silakan jawab 'ya' atau 'tidak'.")
        return
    
    # ✅ PERUBAHAN: Cek jika user sedang menunggu input untuk edit profil (langsung minta konfirmasi)
    elif user_id in user_profile_edit_state:
        state = user_profile_edit_state[user_id]
        action = state['action']
        session_index = state['session_index']
        page = state.get('page', 1)
        
        # Hapus state waiting
        del user_profile_edit_state[user_id]
        
        if text.lower() == "/cancel":
            await m.reply("❌ Aksi dibatalkan.")
            try:
                cb_obj = CallbackQuery(
                    id="temp",
                    from_user=m.from_user,
                    message=m,
                    chat_instance="temp",
                    data=f"session_info_{session_index}_{page}"
                )
                await sessions_info_cb_handler(c, cb_obj)
            except Exception:
                pass
            return
        
        # Simpan data dan minta konfirmasi
        user_edit_confirmation_state[user_id] = {
            'action': action,
            'session_index': session_index,
            'page': page,
            'data': text
        }
        
        action_names = {
            'change_first_name': 'Ganti Nama Depan',
            'change_last_name': 'Ganti Nama Belakang',
            'change_bio': 'Ganti Bio',
            'change_username': 'Ganti Username'
        }
        
        action_text = action_names.get(action, action)
        
        await m.reply(
            f"❓ <b>Konfirmasi {action_text}</b>\n\n"
            f"Data: <code>{html.escape(text)}</code>\n\n"
            f"Apakah Anda yakin ingin melanjutkan?\n"
            f"Ketik <b>ya</b> untuk lanjut atau <b>tidak</b> untuk batalkan.",
            parse_mode=ParseMode.HTML
        )
        return
    
    # ✅ PERUBAHAN: Cek jika user sedang dalam proses bulk join
    elif user_id in user_bulk_join_state and user_bulk_join_state[user_id]['step'] == 'waiting_link':
        if text.lower() == "/cancel":
            del user_bulk_join_state[user_id]
            await m.reply("❌ Bulk join dibatalkan.")
            return
        
        # Validasi link
        link = text
        if not re.match(r'^(https?://t\.me/|@)', link):
            await m.reply("❌ Format link tidak valid!\n\n"
                         "Gunakan format:\n"
                         "• https://t.me/username\n"
                         "• https://t.me/+invitehash\n"
                         "• @username")
            return
        
        # Simpan link
        user_bulk_join_state[user_id]['link'] = link
        user_bulk_join_state[user_id]['step'] = 'confirmation'
        
        delay = user_bulk_join_state[user_id]['delay']
        total_sessions = len(Altruix.clients) if hasattr(Altruix, 'clients') else 0
        
        confirmation_buttons = [
            [
                InlineKeyboardButton("✅ Yes, Join All", callback_data="bulk_join_confirm_yes"),
                InlineKeyboardButton("❌ No, Cancel", callback_data="bulk_join_confirm_no")
            ]
        ]
        
        await m.reply(
            text=f"<b>👥 Confirm Bulk Join</b>\n\n"
                 f"• <b>Delay:</b> <code>{delay} detik</code>\n"
                 f"• <b>Link:</b> <code>{link}</code>\n"
                 f"• <b>Total Sessions:</b> <code>{total_sessions}</code>\n\n"
                 f"⚠️ <b>WARNING:</b>\n"
                 f"• Ini akan join semua session ke grup tersebut\n"
                 f"• Proses mungkin memakan waktu lama\n"
                 f"• Pastikan link valid dan grup dapat di-join",
            reply_markup=InlineKeyboardMarkup(confirmation_buttons),
            parse_mode=ParseMode.HTML
        )
        return
    
    # Handler untuk konfirmasi teks 'ok' dari user (untuk export)
    elif user_id in user_text_confirmation_state and text.lower() == "ok":
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
        return


# ✅ PERUBAHAN: Handler untuk foto profil dengan konfirmasi
@Altruix.bot.on_message(filters.photo & filters.private & filters.user(Altruix.auth_users))
@log_errors
async def profile_photo_handler(c: Client, m: Message):
    """Handler untuk menerima foto profil baru (dengan konfirmasi)"""
    user_id = m.from_user.id
    
    if user_id in user_profile_edit_state:
        state = user_profile_edit_state[user_id]
        action = state['action']
        
        if action == 'change_profile_photo':
            session_index = state['session_index']
            page = state.get('page', 1)
            
            # Hapus state waiting
            del user_profile_edit_state[user_id]
            
            if session_index >= len(Altruix.clients):
                await m.reply("❌ Session tidak ditemukan.")
                return
            
            # Download foto
            try:
                photo_path = await m.download()
                
                # Simpan path di state konfirmasi
                user_edit_confirmation_state[user_id] = {
                    'action': action,
                    'session_index': session_index,
                    'page': page,
                    'data': photo_path,
                    'photo_message': m
                }
                
                await m.reply(
                    "❓ <b>Konfirmasi Ganti Foto Profil</b>\n\n"
                    "Apakah Anda yakin ingin mengganti foto profil dengan foto yang dikirim?\n\n"
                    "⚠️ <b>Note:</b>\n"
                    "• Foto lama akan diganti\n"
                    "• Tidak bisa dikembalikan\n\n"
                    "Ketik <b>ya</b> untuk lanjut atau <b>tidak</b> untuk batalkan.",
                    parse_mode=ParseMode.HTML
                )
                
            except Exception as e:
                await m.reply(f"❌ Error: {str(e)}")
                Altruix.log(f"Error downloading photo: {e}", level=logging.ERROR)


# ✅ PERUBAHAN: Handler untuk konfirmasi ya/tidak khusus foto
@Altruix.bot.on_message(filters.regex(r'^(ya|tidak)$', re.I) & filters.private & filters.user(Altruix.auth_users))
@log_errors
async def confirmation_handler(c: Client, m: Message):
    """Handler khusus untuk konfirmasi ya/tidak"""
    user_id = m.from_user.id
    text = m.text.lower()
    
    if user_id in user_edit_confirmation_state:
        state = user_edit_confirmation_state[user_id]
        action = state['action']
        session_index = state['session_index']
        page = state.get('page', 1)
        
        if text == "ya":
            # Proses aksi
            try:
                session_client = Altruix.clients[session_index]
                success = False
                error_msg = None
                additional_info = {}
                
                if action == 'change_profile_photo':
                    photo_path = state.get('data')
                    
                    if photo_path and os.path.exists(photo_path):
                        try:
                            # Dapatkan info foto lama
                            old_photos = []
                            async for photo in session_client.get_chat_photos("me", limit=1):
                                old_photos.append(photo)
                            
                            # Update foto profil
                            await session_client.set_profile_photo(photo=photo_path)
                            success = True
                            additional_info = {
                                'Aksi': 'Foto profil diganti'
                            }
                            await m.reply("✅ Foto profil berhasil diubah!")
                            
                            # Kirim notifikasi ke log group
                            await send_log_notification(
                                c, action, session_index, m.from_user, 
                                success, error_msg, additional_info
                            )
                            
                            # Hapus file sementara
                            os.remove(photo_path)
                            
                        except PhotoInvalidDimensions as e:
                            error_msg = f"Dimensi foto tidak valid: {str(e)}"
                            await m.reply(f"❌ Dimensi foto tidak valid: {str(e)}")
                        except PhotoSaveFileInvalid as e:
                            error_msg = f"File foto tidak valid: {str(e)}"
                            await m.reply(f"❌ File foto tidak valid: {str(e)}")
                        except FloodWait as e:
                            error_msg = f"FloodWait {e.value} detik"
                            await m.reply(f"⏳ FloodWait: Tunggu {e.value} detik sebelum mencoba lagi.")
                        except Exception as e:
                            error_msg = str(e)
                            await m.reply(f"❌ Error: {str(e)}")
                            Altruix.log(f"Error updating profile photo: {e}", level=logging.ERROR)
                        finally:
                            if not success and photo_path and os.path.exists(photo_path):
                                os.remove(photo_path)
                    else:
                        error_msg = "File foto tidak ditemukan"
                        await m.reply("❌ File foto tidak ditemukan.")
                
                elif action == 'delete_all_profile_photos':
                    # Proses hapus semua foto profil
                    delay = state.get('delay', 2)
                    await m.reply(f"🔄 Memulai penghapusan semua foto profil dengan delay {delay} detik...")
                    
                    # Panggil fungsi penghapusan
                    await delete_all_profile_photos_process(c, m, session_index, page, delay)
                    
                    # Notifikasi log sudah dikirim dari fungsi delete_all_profile_photos_process
                    return
                    
            except Exception as e:
                error_msg = str(e)
                await m.reply(f"❌ Error: {str(e)}")
                Altruix.log(f"Error in confirmation handler: {e}", level=logging.ERROR)
            
            # Hapus state
            del user_edit_confirmation_state[user_id]
            
            # Kembali ke info session
            try:
                await asyncio.sleep(1)
                cb_obj = CallbackQuery(
                    id="temp",
                    from_user=m.from_user,
                    message=m,
                    chat_instance="temp",
                    data=f"session_info_{session_index}_{page}"
                )
                await sessions_info_cb_handler(c, cb_obj)
            except Exception:
                pass
            
        elif text == "tidak":
            # Batalkan aksi
            state = user_edit_confirmation_state[user_id]
            
            # Hapus file foto jika ada
            if state.get('action') == 'change_profile_photo' and state.get('data'):
                photo_path = state['data']
                if os.path.exists(photo_path):
                    os.remove(photo_path)
            
            del user_edit_confirmation_state[user_id]
            await m.reply("❌ Aksi dibatalkan.")
            
            # Kembali ke info session
            try:
                cb_obj = CallbackQuery(
                    id="temp",
                    from_user=m.from_user,
                    message=m,
                    chat_instance="temp",
                    data=f"session_info_{state['session_index']}_{state.get('page', 1)}"
                )
                await sessions_info_cb_handler(c, cb_obj)
            except Exception:
                pass


@Altruix.bot.on_callback_query(filters.regex("bulk_join_confirm_(yes|no)"))
@log_errors
async def bulk_join_confirm_handler(c: Client, cb: CallbackQuery):
    """Handler untuk konfirmasi bulk join"""
    await cb.answer()
    choice = cb.matches[0].group(1)
    user_id = cb.from_user.id
    
    if choice == "no":
        # Hapus state user
        if user_id in user_bulk_join_state:
            del user_bulk_join_state[user_id]
        
        await cb.message.edit(
            text="❌ Bulk join dibatalkan.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Sessions", callback_data="sessions_list_1")]
            ])
        )
        return
    
    # Proses bulk join
    if user_id not in user_bulk_join_state:
        await cb.message.edit("❌ Data tidak ditemukan. Silakan ulangi.")
        return
    
    state = user_bulk_join_state[user_id]
    delay = state['delay']
    link = state['link']
    
    # Hapus state
    del user_bulk_join_state[user_id]
    
    # Mulai proses bulk join
    await execute_bulk_join(c, cb, delay, link)


async def execute_bulk_join(c: Client, cb: CallbackQuery, delay: int, link: str):
    """Fungsi untuk mengeksekusi bulk join"""
    user = cb.from_user
    user_id = user.id
    log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))
    
    total_sessions = len(Altruix.clients) if hasattr(Altruix, 'clients') else 0
    
    if total_sessions == 0:
        await cb.message.edit("❌ No sessions available to join.")
        return
    
    await cb.message.edit(f"🔄 Starting bulk join for <b>{total_sessions}</b> sessions...\n\n"
                         f"• Delay: <code>{delay}</code> seconds\n"
                         f"• Link: <code>{link}</code>")
    
    success_count = 0
    failed_count = 0
    success_list = []
    failed_list = []
    
    # Proses join untuk setiap session
    for index, client in enumerate(Altruix.clients):
        try:
            # Dapatkan info session
            session_user = getattr(client, 'myself', None)
            if not session_user:
                try:
                    session_user = await client.get_me()
                except:
                    session_user = None
            
            session_name = f"Session {index+1}"
            if session_user:
                first_name = getattr(session_user, 'first_name', 'Unknown')
                session_name = f"{first_name} (ID: {getattr(session_user, 'id', 'Unknown')})"
            
            # Coba join
            try:
                await client.join_chat(link)
                success_count += 1
                success_list.append(f"{index+1}. {session_name}")
                
                # Update status
                await cb.message.edit(
                    f"🔄 Bulk join in progress...\n"
                    f"• Success: <code>{success_count}</code>\n"
                    f"• Failed: <code>{failed_count}</code>\n"
                    f"• Total: <code>{total_sessions}</code>\n"
                    f"• Current: Session {index+1}"
                )
                
            except UserAlreadyParticipant:
                success_count += 1
                success_list.append(f"{index+1}. {session_name} (Already in group)")
                
            except FloodWait as e:
                await asyncio.sleep(e.value)
                try:
                    await client.join_chat(link)
                    success_count += 1
                    success_list.append(f"{index+1}. {session_name}")
                except Exception as e:
                    failed_count += 1
                    failed_list.append(f"{index+1}. {session_name} - {type(e).__name__}: {str(e)}")
            
            except (InviteHashInvalid, InviteHashExpired, UsernameNotOccupied, 
                   UsernameInvalid, ChannelPrivate, ChatAdminRequired) as e:
                failed_count += 1
                failed_list.append(f"{index+1}. {session_name} - {type(e).__name__}")
                # Jika error karena link tidak valid, berhenti
                if isinstance(e, (InviteHashInvalid, InviteHashExpired, UsernameNotOccupied)):
                    await cb.message.edit(f"❌ Link invalid/expired. Stopping...")
                    break
            
            except Exception as e:
                failed_count += 1
                failed_list.append(f"{index+1}. {session_name} - {type(e).__name__}: {str(e)}")
            
            # Delay antara session
            if index < total_sessions - 1:
                await asyncio.sleep(delay)
                
        except Exception as e:
            failed_count += 1
            failed_list.append(f"{index+1}. Session {index+1} - {type(e).__name__}: {str(e)}")
    
    # Siapkan laporan
    report_time = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
    
    # Kirim laporan ke log group
    log_report = (
        f"👥 <b>BULK JOIN COMPLETED</b>\n"
        f"• User: <a href='tg://user?id={user.id}'>{html.escape(user.first_name)}</a>\n"
        f"• User ID: <code>{user.id}</code>\n"
        f"• Link: <code>{link}</code>\n"
        f"• Delay: <code>{delay}</code> seconds\n"
        f"• Total Sessions: <code>{total_sessions}</code>\n"
        f"• Success: <code>{success_count}</code>\n"
        f"• Failed: <code>{failed_count}</code>\n"
        f"• Time: <code>{report_time}</code>"
    )
    
    # Tambahkan detail jika ada yang gagal
    if failed_list:
        failed_details = "\n".join(failed_list[:10])  # Batasi 10 item
        if len(failed_list) > 10:
            failed_details += f"\n... and {len(failed_list) - 10} more"
        log_report += f"\n\n<b>Failed Details (first 10):</b>\n{failed_details}"
    
    try:
        await Altruix.bot.send_message(
            log_chat_id,
            log_report,
            parse_mode=ParseMode.HTML,
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
    except Exception as e:
        Altruix.log(f"Failed to send bulk join report to log group: {e}", level=logging.ERROR)
    
    # Update message dengan hasil
    result_text = (
        f"✅ <b>Bulk Join Completed</b>\n\n"
        f"• Total Sessions: <code>{total_sessions}</code>\n"
        f"• Success: <code>{success_count}</code>\n"
        f"• Failed: <code>{failed_count}</code>\n"
        f"• Delay: <code>{delay}</code> seconds\n\n"
    )
    
    if failed_count > 0:
        result_text += f"⚠️ Some sessions failed to join. Check log group for details."
    
    await cb.message.edit(
        text=result_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Sessions", callback_data="sessions_list_1")]
        ]),
        parse_mode=ParseMode.HTML
    )


# ====================== JOIN LOG GROUP FEATURE ======================
@Altruix.bot.on_callback_query(filters.regex("join_log_group_(\\d+)$"))
@log_errors
async def join_log_group_handler(c: Client, cb: CallbackQuery):
    """Handler untuk join log group per session (dengan notifikasi log)"""
    await cb.answer()
    index = int(cb.matches[0].group(1))
    
    if index >= len(Altruix.clients):
        await cb.message.edit("Session not found.")
        return
    
    session_client = Altruix.clients[index]
    session_info = getattr(session_client, 'myself', None)
    
    if not session_info:
        try:
            session_info = await session_client.get_me()
        except Exception as e:
            await cb.message.edit(f"Error getting session info: {str(e)}")
            # Kirim notifikasi error ke log group
            await send_log_notification(
                c, 'join_log_group', index, cb.from_user, 
                False, str(e), {'Aksi': 'Join log group gagal'}
            )
            return
    
    # Dapatkan LOG_CHAT_ID
    log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))
    
    # Coba buat invite link atau dapatkan link yang ada
    try:
        # Coba buat invite link baru
        try:
            invite_link = await Altruix.bot.create_chat_invite_link(
                chat_id=log_chat_id,
                member_limit=1,
                name=f"Join for {session_info.first_name or 'Session'}"
            )
            link = invite_link.invite_link
        except Exception:
            # Jika gagal, coba dapatkan link yang ada
            try:
                chat = await Altruix.bot.get_chat(log_chat_id)
                link = chat.invite_link
                if not link:
                    raise Exception("No invite link available")
            except Exception:
                await cb.message.edit("❌ Cannot get invite link for log group. Make sure bot is admin.")
                # Kirim notifikasi error ke log group
                await send_log_notification(
                    c, 'join_log_group', index, cb.from_user, 
                    False, "Tidak dapat mendapatkan invite link", 
                    {'Aksi': 'Join log group gagal'}
                )
                return
        
        # Coba join dengan session
        try:
            await session_client.join_chat(link)
            
            # Kirim notifikasi ke log group
            await Altruix.bot.send_message(
                log_chat_id,
                f"📢 <b>JOIN LOG GROUP SUCCESS</b>\n"
                f"• Session: <a href='tg://user?id={session_info.id}'>{html.escape(session_info.first_name or '')}</a>\n"
                f"• User ID: <code>{session_info.id}</code>\n"
                f"• Time: <code>{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</code>\n"
                f"• Status: ✅ Successfully joined",
                parse_mode=ParseMode.HTML,
                link_preview_options=LinkPreviewOptions(is_disabled=True)
            )
            
            await cb.message.edit("✅ Successfully joined log group!")
            
            # ✅ BARU: Kirim notifikasi ke log group via fungsi
            await send_log_notification(
                c, 'join_log_group', index, cb.from_user, 
                True, None, {'Aksi': 'Join log group berhasil'}
            )
            
        except UserAlreadyParticipant:
            await cb.message.edit("ℹ️ This session is already in the log group.")
            # ✅ BARU: Kirim notifikasi ke log group
            await send_log_notification(
                c, 'join_log_group', index, cb.from_user, 
                True, None, {'Aksi': 'Join log group (sudah bergabung)'}
            )
            
        except Exception as e:
            await cb.message.edit(f"❌ Failed to join log group: {str(e)}")
            
            # Log error
            await Altruix.bot.send_message(
                log_chat_id,
                f"⚠️ <b>JOIN LOG GROUP FAILED</b>\n"
                f"• Session: <a href='tg://user?id={session_info.id}'>{html.escape(session_info.first_name or '')}</a>\n"
                f"• Error: <code>{html.escape(str(e))}</code>\n"
                f"• Time: <code>{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</code>",
                parse_mode=ParseMode.HTML
            )
            
            # ✅ BARU: Kirim notifikasi error ke log group
            await send_log_notification(
                c, 'join_log_group', index, cb.from_user, 
                False, str(e), {'Aksi': 'Join log group gagal'}
            )
    
    except Exception as e:
        await cb.message.edit(f"❌ Error: {str(e)}")
        # ✅ BARU: Kirim notifikasi error ke log group
        await send_log_notification(
            c, 'join_log_group', index, cb.from_user, 
            False, str(e), {'Aksi': 'Join log group gagal'}
        )


# ====================== EXPORT ALL SESSIONS ======================
@Altruix.bot.on_callback_query(filters.regex("export_all_sessions_confirmation"))
@log_errors
async def export_all_sessions_confirmation_handler(c: Client, cb: CallbackQuery):
    """Handler untuk konfirmasi export all sessions"""
    await cb.answer()
    
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


@Altruix.bot.on_callback_query(filters.regex("export_all_sessions_confirm_no"))
@log_errors
async def export_all_sessions_cancel_handler(c: Client, cb: CallbackQuery):
    """Handler untuk membatalkan export all sessions"""
    await cb.answer("Operation cancelled.")
    
    user_id = cb.from_user.id
    if user_id in user_confirmation_state:
        del user_confirmation_state[user_id]
    
    await sessions_menu_cb_handler(c, cb)


@Altruix.bot.on_callback_query(filters.regex("export_all_sessions_confirm_yes"))
@log_errors
async def export_all_sessions_confirm_yes_handler(c: Client, cb: CallbackQuery):
    """Handler untuk konfirmasi Yes export all sessions"""
    user = cb.from_user
    user_id = user.id
    
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
    
    asyncio.create_task(clear_user_state_after_timeout(user_id, 60))


# ====================== EXPORT ALL PHONES ======================
@Altruix.bot.on_callback_query(filters.regex("export_all_phones_confirmation"))
@log_errors
async def export_all_phones_confirmation_handler(c: Client, cb: CallbackQuery):
    """Handler untuk konfirmasi export all phones"""
    await cb.answer()
    
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


@Altruix.bot.on_callback_query(filters.regex("export_all_phones_confirm_no"))
@log_errors
async def export_all_phones_cancel_handler(c: Client, cb: CallbackQuery):
    """Handler untuk membatalkan export all phones"""
    await cb.answer("Operation cancelled.")
    
    user_id = cb.from_user.id
    if user_id in user_confirmation_state:
        del user_confirmation_state[user_id]
    
    await sessions_menu_cb_handler(c, cb)


@Altruix.bot.on_callback_query(filters.regex("export_all_phones_confirm_yes"))
@log_errors
async def export_all_phones_confirm_yes_handler(c: Client, cb: CallbackQuery):
    """Handler untuk konfirmasi Yes export all phones"""
    user = cb.from_user
    user_id = user.id
    
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
    
    asyncio.create_task(clear_user_state_after_timeout(user_id, 60))


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
        session_data = []
        for index, client in enumerate(Altruix.clients):
            try:
                user_info = getattr(client, 'myself', None)
                if not user_info:
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
        
        file_content = "⚠️ WARNING: KEEP THIS FILE SECURE! ⚠️\n"
        file_content += "These session strings can be used to login to your accounts.\n"
        file_content += "DO NOT share with anyone!\n"
        file_content += "=" * 50 + "\n\n"
        file_content += "".join(session_data)
        
        file_stream = io.BytesIO(file_content.encode())
        file_stream.name = f"all_sessions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
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
        
        await Altruix.bot.send_message(
            log_chat_id,
            f"⚠️ <b>EXPORT ALL SESSIONS CRITICAL ERROR</b>\n"
            f"• User: <a href='tg://user?id={user.id}'>{html.escape(user.first_name)}</a>\n"
            f"• Error: <code>{html.escape(str(e))}</code>\n"
            f"• Time: <code>{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</code>",
            parse_mode=ParseMode.HTML
        )


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
        phone_data = []
        for index, client in enumerate(Altruix.clients):
            try:
                user_info = getattr(client, 'myself', None)
                if not user_info:
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
        
        file_content = "⚠️ Phone numbers are sensitive information. Keep secure!\n"
        file_content += "=" * 50 + "\n\n"
        file_content += "".join(phone_data)
        
        file_stream = io.BytesIO(file_content.encode())
        file_stream.name = f"all_phone_numbers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        await c.send_document(
            chat_id=user_id,
            document=file_stream,
            caption="📲 **All Phone Numbers Exported**\n\n"
                   "⚠️ Keep this information secure.",
            parse_mode=ParseMode.HTML
        )
        
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
        state_data = user_text_confirmation_state[user_id]
        time_elapsed = (datetime.now() - state_data['timestamp']).total_seconds()
        
        if time_elapsed >= timeout:
            del user_text_confirmation_state[user_id]
            if user_id in user_confirmation_state:
                del user_confirmation_state[user_id]
            
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


# ====================== HANDLER YANG SUDAH ADA ======================
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


@Altruix.bot.on_callback_query(filters.regex("test_ping_all_confirm_no"))
@log_errors
async def test_ping_all_cancel_handler(c: Client, cb: CallbackQuery):
    await cb.answer("Operation cancelled.")
    await sessions_menu_cb_handler(c, cb)


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

    session_client = Altruix.clients[index]
    session_info = getattr(session_client, 'myself', None)
    
    if not session_info:
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
    bio = getattr(session_info, 'bio', 'None')

    txt = (
        "<b>📋 Session Info</b>\n\n"
        f"<b>👤 First name:</b> <code>{html.escape(first_name or 'None')}</code>\n"
        f"<b>👤 Last name:</b> <code>{html.escape(last_name or 'None')}</code>\n"
        f"<b>📝 Bio:</b> <code>{html.escape(bio[:50] + '...' if bio and len(bio) > 50 else bio or 'None')}</code>\n"
        f"<b>🌐 DC ID:</b> <code>{dc_id or 'Unknown'}</code>\n"
        f"<b>🔗 Username:</b> @{username or 'None'}\n"
        f"<b>🆔 User ID:</b> <code>{user_id}</code>\n"
        f"<b>⚠️ Is SCAM:</b> <code>{'Yes' if is_scam else 'No'}</code>"
    )
    
    # ✅ PERUBAHAN: Tambahkan tombol-tombol edit profil sesuai permintaan
    await cb.message.edit(
        text=txt,
        reply_markup=InlineKeyboardMarkup(
            [
                # Baris 1: Refresh dan Unlink
                [
                    InlineKeyboardButton("🔄 Refresh data", f"refresh_session_info_{index}"),
                    InlineKeyboardButton("🔗 Unlink (Remove)", f"unlink_session_{index}"),
                ],
                # Baris 2: Export Session dan Phone
                [
                    InlineKeyboardButton("📤 Export Session", f"export_session_{index}"),
                    InlineKeyboardButton("📞 Export Phone Number", f"export_phone_{index}"),
                ],
                # Baris 3: Test Ping dan Join Log Group
                [
                    InlineKeyboardButton("🏓 Test Ping", f"test_ping_{index}"),
                    InlineKeyboardButton("📢 Join Log Group", f"join_log_group_{index}"),
                ],
                # Baris 4: Check Limit
                [
                    InlineKeyboardButton("🔍 Check Limit", f"check_limit_confirm_{index}_{callback_page}"),
                ],
                # ✅ BARU: Baris 5-9 untuk fitur edit profil
                # Baris 5: Ganti Nama Depan dan Belakang
                [
                    InlineKeyboardButton("✏️ Ganti nama depan", f"change_first_name_{index}_{callback_page}"),
                    InlineKeyboardButton("✏️ Ganti nama belakang", f"change_last_name_{index}_{callback_page}"),
                ],
                # Baris 6: Ganti Bio dan Username
                [
                    InlineKeyboardButton("📝 Ganti bio", f"change_bio_{index}_{callback_page}"),
                    InlineKeyboardButton("👤 Ganti username", f"change_username_{index}_{callback_page}"),
                ],
                # Baris 7: Ganti Foto Profil dan Lihat Sesi Login
                [
                    InlineKeyboardButton("🖼️ Ganti foto profil", f"change_profile_photo_{index}_{callback_page}"),
                    InlineKeyboardButton("👁️ Lihat semua sesi", f"view_all_sessions_{index}_{callback_page}"),
                ],
                # Baris 8: Hapus Semua Foto Profil
                [
                    InlineKeyboardButton("🗑️ Hapus semua foto profil", f"delete_all_profile_photos_{index}_{callback_page}"),
                ],
                # Baris 9: Tombol Back
                [
                    InlineKeyboardButton("🔙 Back", f"sessions_list_{callback_page}"),
                ],
            ]
        ),
        parse_mode=ParseMode.HTML
    )


# ✅ HANDLER BARU: Ganti Nama Depan dengan konfirmasi
@Altruix.bot.on_callback_query(filters.regex(r"change_first_name_(\d+)_(\d+)"))
@log_errors
async def change_first_name_handler(c: Client, cb: CallbackQuery):
    """Handler untuk mengganti nama depan (dengan konfirmasi)"""
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    
    user_id = cb.from_user.id
    user_profile_edit_state[user_id] = {
        'action': 'change_first_name',
        'session_index': index,
        'page': page
    }
    
    await cb.message.edit(
        text="✏️ <b>Ganti Nama Depan</b>\n\n"
             "Silakan kirim nama depan baru untuk akun ini.\n\n"
             "⚠️ <b>Note:</b>\n"
             "• Nama depan maksimal 64 karakter\n"
             "• Tidak boleh mengandung karakter khusus\n\n"
             "❌ <b>Cancel:</b> Kirim /cancel",
        parse_mode=ParseMode.HTML
    )


# ✅ HANDLER BARU: Ganti Nama Belakang dengan konfirmasi
@Altruix.bot.on_callback_query(filters.regex(r"change_last_name_(\d+)_(\d+)"))
@log_errors
async def change_last_name_handler(c: Client, cb: CallbackQuery):
    """Handler untuk mengganti nama belakang (dengan konfirmasi)"""
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    
    user_id = cb.from_user.id
    user_profile_edit_state[user_id] = {
        'action': 'change_last_name',
        'session_index': index,
        'page': page
    }
    
    await cb.message.edit(
        text="✏️ <b>Ganti Nama Belakang</b>\n\n"
             "Silakan kirim nama belakang baru untuk akun ini.\n"
             "Kirim 'kosong' atau string kosong untuk menghapus nama belakang.\n\n"
             "⚠️ <b>Note:</b>\n"
             "• Nama belakang maksimal 64 karakter\n"
             "• Kosongkan untuk menghapus nama belakang\n\n"
             "❌ <b>Cancel:</b> Kirim /cancel",
        parse_mode=ParseMode.HTML
    )


# ✅ HANDLER BARU: Ganti Bio dengan konfirmasi
@Altruix.bot.on_callback_query(filters.regex(r"change_bio_(\d+)_(\d+)"))
@log_errors
async def change_bio_handler(c: Client, cb: CallbackQuery):
    """Handler untuk mengganti bio (dengan konfirmasi)"""
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    
    user_id = cb.from_user.id
    user_profile_edit_state[user_id] = {
        'action': 'change_bio',
        'session_index': index,
        'page': page
    }
    
    await cb.message.edit(
        text="📝 <b>Ganti Bio</b>\n\n"
             "Silakan kirim bio baru untuk akun ini.\n"
             "Maksimal 70 karakter.\n\n"
             "⚠️ <b>Note:</b>\n"
             "• Bio akan tampil di profil\n"
             "• Bisa berisi emoji dan link\n\n"
             "❌ <b>Cancel:</b> Kirim /cancel",
        parse_mode=ParseMode.HTML
    )


# ✅ HANDLER BARU: Ganti Username dengan konfirmasi
@Altruix.bot.on_callback_query(filters.regex(r"change_username_(\d+)_(\d+)"))
@log_errors
async def change_username_handler(c: Client, cb: CallbackQuery):
    """Handler untuk mengganti username (dengan konfirmasi)"""
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    
    user_id = cb.from_user.id
    user_profile_edit_state[user_id] = {
        'action': 'change_username',
        'session_index': index,
        'page': page
    }
    
    await cb.message.edit(
        text="👤 <b>Ganti Username</b>\n\n"
             "Silakan kirim username baru (tanpa @).\n"
             "Contoh: username_baru\n\n"
             "⚠️ <b>Note:</b>\n"
             "• Username harus unik dan tersedia\n"
             "• Minimal 5 karakter\n"
             "• Hanya boleh mengandung huruf, angka, dan underscore\n"
             "• Tidak boleh mengandung kata kasar\n\n"
             "❌ <b>Cancel:</b> Kirim /cancel",
        parse_mode=ParseMode.HTML
    )


# ✅ HANDLER BARU: Ganti Foto Profil dengan konfirmasi
@Altruix.bot.on_callback_query(filters.regex(r"change_profile_photo_(\d+)_(\d+)"))
@log_errors
async def change_profile_photo_handler(c: Client, cb: CallbackQuery):
    """Handler untuk mengganti foto profil (dengan konfirmasi)"""
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    
    user_id = cb.from_user.id
    user_profile_edit_state[user_id] = {
        'action': 'change_profile_photo',
        'session_index': index,
        'page': page
    }
    
    await cb.message.edit(
        text="🖼️ <b>Ganti Foto Profil</b>\n\n"
             "Silakan kirim foto baru untuk profil akun ini.\n\n"
             "⚠️ <b>Note:</b>\n"
             "• Foto harus dalam format JPEG/PNG\n"
             "• Ukuran maksimal 10MB\n"
             "• Rasio disarankan 1:1 (persegi)\n"
             "• Foto lama akan diganti\n\n"
             "❌ <b>Cancel:</b> Kirim /cancel",
        parse_mode=ParseMode.HTML
    )


# ✅ HANDLER BARU: Lihat semua sesi login dengan notifikasi log
@Altruix.bot.on_callback_query(filters.regex(r"view_all_sessions_(\d+)_(\d+)"))
@log_errors
async def view_all_sessions_handler(c: Client, cb: CallbackQuery):
    """Handler untuk melihat semua sesi login (dengan notifikasi log)"""
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    
    if index >= len(Altruix.clients):
        await cb.message.edit("❌ Session tidak ditemukan.")
        return
    
    session_client = Altruix.clients[index]
    session_info = getattr(session_client, 'myself', None) or await session_client.get_me()
    
    try:
        # Coba dapatkan informasi sesi aktif
        authorized = await session_client.get_me() is not None
        
        # Kirim notifikasi ke log group
        await send_log_notification(
            c, 'view_all_sessions', index, cb.from_user, 
            True, None, {'Aksi': 'Melihat sesi login'}
        )
        
        session_text = (
            f"<b>👁️ Informasi Sesi Login</b>\n\n"
            f"<b>Akun:</b> {html.escape(session_info.first_name or 'Unknown')}\n"
            f"<b>ID:</b> <code>{session_info.id}</code>\n"
            f"<b>Status:</b> {'✅ Authorized' if authorized else '❌ Not Authorized'}\n"
            f"<b>Username:</b> @{session_info.username or 'tidak ada'}\n"
            f"<b>DC ID:</b> <code>{session_info.dc_id or 'Unknown'}</code>\n\n"
            f"<b>⚠️ Catatan:</b>\n"
            f"Pyrogram tidak menyediakan API untuk melihat semua sesi login.\n"
            f"Informasi ini hanya menunjukkan status autorisasi saat ini."
        )
        
        await cb.message.edit(
            text=session_text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}")]
            ]),
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        await cb.message.edit(f"❌ Error: {html.escape(str(e))}")
        # Kirim notifikasi error ke log group
        await send_log_notification(
            c, 'view_all_sessions', index, cb.from_user, 
            False, str(e), {'Aksi': 'Melihat sesi login'}
        )


# ✅ HANDLER BARU: Hapus semua foto profil dengan konfirmasi
@Altruix.bot.on_callback_query(filters.regex(r"delete_all_profile_photos_(\d+)_(\d+)"))
@log_errors
async def delete_all_profile_photos_handler(c: Client, cb: CallbackQuery):
    """Handler untuk menghapus semua foto profil (dengan konfirmasi)"""
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    
    user_id = cb.from_user.id
    user_edit_confirmation_state[user_id] = {
        'action': 'delete_all_profile_photos',
        'session_index': index,
        'page': page,
        'delay': 2  # Default delay 2 detik
    }
    
    # Tampilkan konfirmasi
    await cb.message.edit(
        text="🗑️ <b>Konfirmasi Hapus Semua Foto Profil</b>\n\n"
             "Apakah Anda yakin ingin menghapus SEMUA foto profil akun ini?\n\n"
             "⚠️ <b>PERINGATAN TINGGI:</b>\n"
             "• Tindakan ini TIDAK DAPAT DIBATALKAN\n"
             "• Semua foto profil akan dihapus permanen\n"
             "• Risiko flood wait/limit jika terlalu banyak foto\n\n"
             "Ketik <b>ya</b> untuk lanjut atau <b>tidak</b> untuk batalkan.\n\n"
             "Setelah konfirmasi, Anda bisa pilih delay:",
        parse_mode=ParseMode.HTML
    )


# ✅ FUNGSI BARU: Hapus semua foto profil dengan notifikasi log
async def delete_all_profile_photos_process(c: Client, m: Message, session_index: int, page: int, delay: int):
    """Fungsi untuk menghapus semua foto profil dengan delay dan notifikasi log"""
    if session_index >= len(Altruix.clients):
        await m.reply("❌ Session tidak ditemukan.")
        return
    
    session_client = Altruix.clients[session_index]
    session_info = getattr(session_client, 'myself', None) or await session_client.get_me()
    
    try:
        # Dapatkan semua foto profil
        photos = []
        async for photo in session_client.get_chat_photos("me"):
            photos.append(photo)
        
        total_photos = len(photos)
        
        if total_photos == 0:
            await m.reply("ℹ️ Akun ini tidak memiliki foto profil.")
            # Kirim notifikasi ke log group
            await send_log_notification(
                c, 'delete_all_profile_photos', session_index, m.from_user, 
                True, None, {
                    'Aksi': 'Hapus semua foto profil',
                    'Total Foto': '0',
                    'Status': 'Tidak ada foto'
                }
            )
            return
        
        # Kirim notifikasi mulai ke log group
        await send_log_notification(
            c, 'delete_all_profile_photos', session_index, m.from_user, 
            True, None, {
                'Aksi': 'Mulai hapus semua foto profil',
                'Total Foto': str(total_photos),
                'Delay': f'{delay} detik'
            }
        )
        
        await m.reply(f"🔄 Menghapus {total_photos} foto profil dengan delay {delay} detik...")
        
        deleted_count = 0
        failed_count = 0
        errors = []
        
        for i, photo in enumerate(photos, 1):
            try:
                await session_client.delete_profile_photos(photo.file_id)
                deleted_count += 1
                
                # Update progress
                if i % 5 == 0 or i == total_photos:
                    progress_msg = (
                        f"🔄 Progress: {i}/{total_photos} foto\n"
                        f"✅ Berhasil: {deleted_count}\n"
                        f"❌ Gagal: {failed_count}"
                    )
                    await m.reply(progress_msg, quote=False)
                
                # Delay antara penghapusan
                if i < total_photos:
                    await asyncio.sleep(delay)
                    
            except FloodWait as e:
                await m.reply(f"⏳ FloodWait {e.value} detik, menunggu...")
                await asyncio.sleep(e.value)
                try:
                    await session_client.delete_profile_photos(photo.file_id)
                    deleted_count += 1
                except Exception as e:
                    failed_count += 1
                    errors.append(f"Foto {i}: {type(e).__name__}: {str(e)}")
                    
            except Exception as e:
                failed_count += 1
                errors.append(f"Foto {i}: {type(e).__name__}: {str(e)}")
                Altruix.log(f"Error deleting photo {i}: {e}", level=logging.ERROR)
        
        # Hasil akhir
        result_text = (
            f"✅ <b>Penghapusan Foto Profil Selesai</b>\n\n"
            f"<b>Akun:</b> {html.escape(session_info.first_name or 'Unknown')}\n"
            f"<b>Total Foto:</b> {total_photos}\n"
            f"<b>Berhasil Dihapus:</b> {deleted_count}\n"
            f"<b>Gagal:</b> {failed_count}\n"
            f"<b>Delay:</b> {delay} detik"
        )
        
        await m.reply(result_text, parse_mode=ParseMode.HTML)
        
        # Kirim notifikasi selesai ke log group
        error_info = "; ".join(errors[:5]) if errors else "Tidak ada error"
        if len(errors) > 5:
            error_info += f"... dan {len(errors) - 5} error lainnya"
            
        await send_log_notification(
            c, 'delete_all_profile_photos', session_index, m.from_user, 
            True if failed_count == 0 else False, 
            error_info if errors else None,
            {
                'Aksi': 'Selesai hapus foto profil',
                'Total Foto': str(total_photos),
                'Berhasil': str(deleted_count),
                'Gagal': str(failed_count),
                'Delay': f'{delay} detik'
            }
        )
        
        # Kembali ke info session
        try:
            cb_obj = CallbackQuery(
                id="temp",
                from_user=m.from_user,
                message=m,
                chat_instance="temp",
                data=f"session_info_{session_index}_{page}"
            )
            await sessions_info_cb_handler(c, cb_obj)
        except Exception:
            pass
            
    except Exception as e:
        await m.reply(f"❌ Error: {str(e)}")
        Altruix.log(f"Error in delete_all_profile_photos_process: {e}", level=logging.ERROR)
        # Kirim notifikasi error ke log group
        await send_log_notification(
            c, 'delete_all_profile_photos', session_index, m.from_user, 
            False, str(e), {'Aksi': 'Error hapus foto profil'}
        )


# ✅ HANDLER BARU: Konfirmasi Check Limit
@Altruix.bot.on_callback_query(filters.regex(r"check_limit_confirm_(\d+)_(\d+)"))
@log_errors
async def check_limit_confirmation_handler(c: Client, cb: CallbackQuery):
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))

    confirmation_buttons = [
        [
            InlineKeyboardButton("✅ Yes, Check Limit", f"check_limit_execute_{index}_{page}"),
            InlineKeyboardButton("❌ Cancel", f"session_info_{index}_{page}")
        ]
    ]

    await cb.message.edit(
        text="🔍 <b>Konfirmasi Check Limit</b>\n\n"
             "Akun ini akan mengirim pesan ke @SpamBot untuk mengecek status limit.\n\n"
             "⚠️ <b>Catatan:</b>\n"
             "• Proses ini aman dan resmi dari Telegram\n"
             "• Hanya memicu respons otomatis dari @SpamBot\n"
             "• Hasil akan ditampilkan di sini",
        reply_markup=InlineKeyboardMarkup(confirmation_buttons),
        parse_mode=ParseMode.HTML
    )


# ✅ HANDLER BARU: Eksekusi Check Limit
@Altruix.bot.on_callback_query(filters.regex(r"check_limit_execute_(\d+)_(\d+)"))
@log_errors
async def check_limit_execute_handler(c: Client, cb: CallbackQuery):
    await cb.answer("🔍 Sedang mengecek limit...", show_alert=True)
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))

    if index >= len(Altruix.clients):
        await cb.message.edit("❌ Session tidak ditemukan.")
        return

    session_client = Altruix.clients[index]
    session_info = getattr(session_client, 'myself', None) or await session_client.get_me()

    await cb.message.edit("🔄 Mengirim /start ke @SpamBot...")

    try:
        # Kirim /start ke SpamBot untuk memicu respons
        await session_client.send_message("spambot", "/start")
        await asyncio.sleep(6)  # Tunggu respons masuk

        # Ambil history chat dengan SpamBot
        messages = [msg async for msg in session_client.get_chat_history("spambot", limit=15)]
        bot_responses = [msg.text for msg in messages if msg.from_user and not msg.outgoing]

        if bot_responses:
            latest_response = bot_responses[0].strip()
            if "Good news" in latest_response and "no limits" in latest_response:
                result_text = "✅ <b>Akun BEBAS dari limit!</b>\n\n" + html.escape(latest_response)
            else:
                result_text = "⚠️ <b>Akun TERKENA LIMIT!</b>\n\n" + html.escape(latest_response)
        else:
            result_text = "❌ Tidak ada respons dari @SpamBot (mungkin belum pernah di-start)."

        await cb.message.edit(
            text=f"<b>🔍 Hasil Check Limit</b>\n\n"
                 f"<b>Akun:</b> {html.escape(session_info.first_name or 'Unknown')}\n"
                 f"<b>ID:</b> <code>{session_info.id}</code>\n\n"
                 f"{result_text}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Session Info", f"session_info_{index}_{page}")]
            ]),
            parse_mode=ParseMode.HTML
        )

    except BotBlocked:
        await cb.message.edit("❌ Akun ini diblokir oleh @SpamBot (kemungkinan limit permanen atau sebelumnya terkena spam berat).")

    except FloodWait as e:
        await cb.message.edit(f"⏳ FloodWait! Akun ini harus menunggu {e.value} detik sebelum bisa mengirim pesan lagi.")

    except Exception as e:
        await cb.message.edit(f"❌ Gagal mengecek limit: {html.escape(str(e))}")
        Altruix.log(f"Error check limit session {index}: {e}", level=logging.ERROR)


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
        
        # ✅ BARU: Kirim notifikasi ke log group melalui fungsi
        await send_log_notification(
            c, 'test_ping', index, cb.from_user, 
            True, None, {'Aksi': 'Test ping berhasil'}
        )
        
        Altruix.log(f"Test ping sukses untuk session {index} ({getattr(session_user, 'id', 'Unknown')})")

    except FloodWait as e:
        await asyncio.sleep(e.value)
        await cb.message.edit(f"⏳ FloodWait terdeteksi. Tunggu {e.value} detik.")
        Altruix.log(f"FloodWait saat test ping session {index}: {e.value}s")
        
        # ✅ BARU: Kirim notifikasi error ke log group
        await send_log_notification(
            c, 'test_ping', index, cb.from_user, 
            False, f"FloodWait {e.value}s", {'Aksi': 'Test ping gagal'}
        )

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
            
        # ✅ BARU: Kirim notifikasi error ke log group
        await send_log_notification(
            c, 'test_ping', index, cb.from_user, 
            False, f"{type(e).__name__}: {str(e)}", {'Aksi': 'Test ping gagal'}
        )

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
            
        # ✅ BARU: Kirim notifikasi error ke log group
        await send_log_notification(
            c, 'test_ping', index, cb.from_user, 
            False, f"SlowmodeWait {e.value}s", {'Aksi': 'Test ping gagal'}
        )

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
            
        # ✅ BARU: Kirim notifikasi error ke log group
        await send_log_notification(
            c, 'test_ping', index, cb.from_user, 
            False, str(e), {'Aksi': 'Test ping gagal'}
        )


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
            # ✅ BARU: Kirim notifikasi ke log group
            await send_log_notification(
                c, 'export_phone', index, cb.from_user, 
                False, "Tidak ada nomor telepon", {'Aksi': 'Export phone gagal'}
            )
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
        
        # ✅ BARU: Kirim notifikasi ke log group
        await send_log_notification(
            c, 'export_phone', index, cb.from_user, 
            True, None, {
                'Aksi': 'Export phone berhasil',
                'Nomor': user_info.phone_number
            }
        )
        
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
        
        # ✅ BARU: Kirim notifikasi error ke log group
        await send_log_notification(
            c, 'export_phone', index, cb.from_user, 
            False, str(e), {'Aksi': 'Export phone gagal'}
        )


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
        
        # ✅ BARU: Kirim notifikasi ke log group
        await send_log_notification(
            c, 'export_session', index, cb.from_user, 
            True, None, {'Aksi': 'Export session berhasil'}
        )
        
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
        
        # ✅ BARU: Kirim notifikasi error ke log group
        await send_log_notification(
            c, 'export_session', index, cb.from_user, 
            False, str(e), {'Aksi': 'Export session gagal'}
        )


@Altruix.bot.on_callback_query(filters.regex("refresh_session_info_(\\d+)$"))
@log_errors
async def refresh_session_info_cb_handler(c: Client, cb: CallbackQuery):
    index = int(cb.matches[0].group(1))
    
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


# ✅ HANDLER UNTUK ADD SESSION (PLACEHOLDER)
@Altruix.bot.on_callback_query(filters.regex("add_session"))
@log_errors
async def add_session_handler(c: Client, cb: CallbackQuery):
    """Handler untuk tombol Add a Session"""
    await cb.answer("Fitur ini akan segera ditambahkan!", show_alert=True)

# Log sukses loading
try:
    Altruix.log(f"[DEBUG] ✅ Loaded → {__plugin_name__} {PLUGIN_VERSION}", level=20)
except Exception as e:
    logger.info(f"[DEBUG] ✅ Loaded → {__plugin_name__} {PLUGIN_VERSION}")
