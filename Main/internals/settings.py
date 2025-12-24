# settings.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix/Altruix >
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.

from Main import Altruix
from typing import List, Tuple, Dict, Any, Union
from pyrogram import Client, filters, raw
from Main.core.decorators import log_errors
from Main.core.types.message import Message
from pyrogram.types import (
    CallbackQuery, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove,
    InlineKeyboardButton, InlineKeyboardMarkup, LinkPreviewOptions, User,
    Chat, MessageEntity
)
import json

# ====================== PERBAIKAN IMPORT ERROR ======================
# Import semua error yang tersedia di Pyrogram
from pyrogram.errors import (
    PeerIdInvalid, UserIsBlocked, ChatWriteForbidden, FloodWait, MessageIdInvalid,
    SlowmodeWait, InviteHashInvalid, InviteHashExpired, UserAlreadyParticipant,
    ChatAdminRequired, UsernameNotOccupied, ChannelPrivate, UsernameInvalid,
    UsernameNotModified, AboutTooLong, PhotoInvalidDimensions,
    PhotoSaveFileInvalid, UsernameOccupied, RPCError
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

from pyrogram.enums import ParseMode, ChatType
import os
import logging
import asyncio
import html
from datetime import datetime
import io
import re
import pyrogram

# ─── LOGGER KHUSUS PLUGIN ───────────────────────────────────────────────
import logging

plugin_name = f"{os.path.basename(__file__)}"
__plugin_name__ = plugin_name if plugin_name else "settings"
PLUGIN_VERSION = "1.0.2"  # ✅ REFACTORED: Integrated session addition

logger = logging.getLogger("altruix.settings")
logger.setLevel(logging.INFO)

# ✅ IMPORT BARU: Untuk integrasi session addition
from Main.internals.get_session import add_session_cb_handler

# 🔥 LOG STARTUP
logger.info(f"🚀 Initializing settings plugin v{PLUGIN_VERSION}")

# Dictionary untuk menyimpan state konfirmasi user
user_confirmation_state = {}
user_text_confirmation_state = {}
user_bulk_join_state = {}  # State untuk bulk join
user_dlphoto_state = {} # ✅ BARU: State untuk download foto profil
user_purge_state = {}   # ✅ BARU: State untuk purge pesan
user_eval_state = {}  # ✅ BARU
user_exec_state = {} # ✅ BARU: State untuk exec terminal
user_sys_ctrl_state = {} # ✅ BARU  # State untuk bulk join
user_profile_edit_state = {}  # State untuk edit profil
user_photo_delete_state = {}  # State untuk hapus foto profil
user_edit_confirmation_state = {}  # State untuk konfirmasi edit profil
user_mentions_state = {}  # ✅ BARU: State untuk cek mention
user_recent_messages_state = {}  # ✅ BARU: State untuk pesan terbaru
user_message_count_state = {}  # ✅ BARU: State untuk jumlah pesan

# ✅ TAMBAHAN STATE UNTUK CEK LIMIT (per session)
user_limit_check_state = {}  # {user_id: {'session_index': int, 'page': int}}
user_dlstory_state = {} # ✅ BARU: State untuk download story
user_purge_state = {}   # ✅ BARU: State untuk purge pesan
user_dlphoto_state = {} # ✅ BARU: State untuk download foto profil
user_privacy_state = {} # ✅ BARU: State untuk privacy settings

# ✅ LOCALIZATION / TRANSLATION SYSTEM
SETTINGS_LANG = getattr(Altruix.config, "UB_LANG", "english").lower()

STRINGS = {
    "indonesia": {
        "sessions": "Sesi",
        "configs": "Konfigurasi",
        "session_info_title": "ℹ️ <b>INFO SESI</b>",
        "refresh_data": "🔄 Refresh data",
        "unlink_session": "🔗 Unlink (Remove)",
        "change_name": "📝 Ganti Nama",
        "change_bio": "✍️ Ganti Bio",
        "change_username": "🆔 Ganti Username",
        "change_profile_photo": "🖼️ Ganti Foto",
        "send_profile_photo": "📷 Kirim Foto Profil",
        "check_limit": "🔍 Check Limit",
        "view_sessions": "📱 Sesi Login",
        "recent_messages": "📨 Pesan Terbaru",
        "view_mentions": "🔔 Lihat Mention",
        "mention_control": "🔔 Mention Control",
        "pm_logger_control": "📟 PM Logger Controls",
        "join_group": "➕ Join Group/Ch",
        "leave_group": "🏃 Leave Group/Ch",
        "send_message": "✉️ Send Message",
        "back": "🔙 Kembali",
        "cancel": "❌ Cancel",
        "yes": "✅ Ya",
        "no": "❌ Tidak",
        "unlink_explain": "Sesi akan dihapus dari konfigurasi dan aplikasi akan direstart.",
        "download_story": "📥 Download Story",
        "pm_logger": "PM Logger",
        "reply_from_all": "Reply From All",
        "mention_auto_log": "Mention Auto-Log",
        "enabled": "AKTIF",
        "disabled": "MATIKAN",
        "status": "Status",
        "export_session": "📤 Ekspor Sesi",
        "export_phone": "📞 Ekspor No. HP",
        "test_ping": "🏓 Tes Ping",
        "join_log_group": "📢 Gabung Log Grup",
        "delete_all_photos": "🗑️ Hapus Foto Profil",
        "first_name": "✏️ Nama Depan",
        "last_name": "✏️ Nama Belakang",
        "purge_my_msg": "🧹 Hapus Pesan Saya",
        "download_user_photo": "🖼️ Unduh Foto User",
        "confirm_purge": "Konfirmasi Hapus",
        "confirm_action": "Konfirmasi Aksi",
        "confirm_msg": "Apakah Anda yakin ingin melakukan aksi ini?",
        "download_content": "📥 Download Konten",
        "download_my_photo": "🖼️ Download My Photo",
        "download_user_photo": "📥 Download User Photo",
    },
    "english": {
        "sessions": "Sessions",
        "configs": "Configs",
        "session_info_title": "ℹ️ <b>SESSION INFO</b>",
        "refresh_data": "🔄 Refresh data",
        "unlink_session": "🔗 Unlink (Remove)",
        "change_name": "📝 Change Name",
        "change_bio": "✍️ Change Bio",
        "change_username": "🆔 Change Username",
        "change_profile_photo": "🖼️ Change Photo",
        "send_profile_photo": "📷 Send Profile Photo",
        "check_limit": "🔍 Check Limit",
        "view_sessions": "📱 Login Sessions",
        "recent_messages": "📨 Recent Messages",
        "view_mentions": "🔔 View Mentions",
        "mention_control": "🔔 Mention Control",
        "pm_logger_control": "📟 PM Logger Controls",
        "join_group": "➕ Join Group/Ch",
        "leave_group": "🏃 Leave Group/Ch",
        "send_message": "✉️ Send Message",
        "back": "🔙 Back",
        "cancel": "❌ Cancel",
        "yes": "✅ Yes",
        "no": "❌ No",
        "unlink_explain": "The session will be removed from config and the application will restart.",
        "download_story": "📥 Download Story",
        "pm_logger": "PM Logger",
        "reply_from_all": "Reply From All",
        "mention_auto_log": "Mention Auto-Log",
        "enabled": "ENABLED",
        "disabled": "DISABLED",
        "status": "Status",
        "export_session": "📤 Export Session",
        "export_phone": "📞 Export Phone",
        "test_ping": "🏓 Test Ping",
        "join_log_group": "📢 Join Log Group",
        "delete_all_photos": "🗑️ Delete Photos",
        "first_name": "✏️ First Name",
        "last_name": "✏️ Last Name",
        "purge_my_msg": "🧹 Purge My Msg",
        "download_user_photo": "🖼️ Download Photo",
        "confirm_purge": "Confirm Purge",
        "confirm_action": "Confirm Action",
        "confirm_msg": "Are you sure you want to perform this action?",
        "download_content": "📥 Download Content",
        "download_my_photo": "🖼️ Download My Photo",
        "download_user_photo": "📥 Download User Photo",
    }
}

def gt(key):
    """Get Translated string"""
    lang = SETTINGS_LANG if SETTINGS_LANG in STRINGS else "english"
    return STRINGS[lang].get(key, STRINGS["english"].get(key, key))

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
            'join_log_group': 'Join Log Group',
            'check_limit': 'Check Limit',
            'recent_messages': 'Pesan Terbaru',  # ✅ BARU
            'view_mentions': 'Lihat Mention',  # ✅ BARU
            'send_profile_photo': 'Kirim Foto Profil'  # ✅ BARU
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
        logger.error(f"Gagal kirim notifikasi ke log: {e}")

# ✅ HANDLER GLOBAL UNTUK KONFIRMASI EDIT (INLINE)
@Altruix.bot.on_callback_query(filters.regex(r"^edit_confirm_(yes|no)_(\d+)"))
@log_errors
async def edit_confirm_cb_handler(c: Client, cb: CallbackQuery):
    """Handler global untuk memproses konfirmasi Yes/No dari Inline Buttons"""
    action_type = cb.matches[0].group(1)
    user_id = int(cb.matches[0].group(2))
    
    if action_type == "no":
        # Bersihkan state dan batalkan
        user_edit_confirmation_state.pop(user_id, None)
        user_profile_edit_state.pop(user_id, None)
        await cb.answer("Dibatalkan.", show_alert=True)
        await cb.message.edit("❌ Aksi dibatalkan oleh pengguna.")
        return

    # Jika PROSES (Yes)
    if user_id not in user_edit_confirmation_state:
        await cb.answer("❌ Data tidak ditemukan atau kadaluarsa.", show_alert=True)
        return
        
    state = user_edit_confirmation_state[user_id]
    session_index = state['session_index']
    action = state['action']
    data = state['data']
    
    # Simpan referensi message karena kita akan butuh reply
    original_msg = cb.message
    
    # Hapus state agar tidak diproses dua kali
    del user_edit_confirmation_state[user_id]
    
    if session_index >= len(Altruix.clients):
        await cb.answer("❌ Session tidak ditemukan.", show_alert=True)
        return
        
    session_client = Altruix.clients[session_index]
    await cb.answer("Memproses...", show_alert=False)
    
    try:
        # Kita akan memanggil user_text_handler versi internal (tanpa listen)
        # Tapi karena kodenya sudah ada di user_text_handler, kita bisa refactor
        # Atau untuk cepat kita buat dummy message object dan panggil function-nya.
        # Strategi: Kita buat "Pesan Bayangan" (Shadow Message) berisi "ya"
        # agar user_text_handler memprosesnya.
        
        class MockMessage:
            def __init__(self, c, u, chat_id, text, reply_to):
                self._c = c
                self.from_user = u
                self.chat = type('obj', (object,), {'id': chat_id})
                self.text = text
                self.id = 0
                self.reply_to_message_id = reply_to
            async def reply(self, *args, **kwargs):
                return await self._c.send_message(self.chat.id, *args, **kwargs)
            async def delete(self): pass
            
        mock_msg = MockMessage(c, cb.from_user, cb.message.chat.id, "ya", cb.message.id)
        
        # Masukkan kembali ke state untuk diproses oleh logic "ya" di user_text_handler
        user_edit_confirmation_state[user_id] = state
        
        # Panggil handler
        await user_text_handler(c, mock_msg)
        
        # Hapus pesan konfirmasi inline
        try:
            await cb.message.delete()
        except:
            pass
            
    except Exception as e:
        logger.error(f"Error in edit_confirm_cb_handler: {e}")
        await cb.message.edit(f"❌ Terjadi kesalahan: {str(e)}")
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

    # Baris 6: Tombol System Control
    system_control_buttons = [
        InlineKeyboardButton("🔄 Force Restart", "sys_ctrl_restart"),
        InlineKeyboardButton("❌ Force Shutdown", "sys_ctrl_shutdown")
    ]
    
    # Baris 7: Tombol navigasi [Previous][Back][Next]
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

    # Tambahkan system control buttons sebagai baris keenam
    final_markup.append(system_control_buttons)
    
    # Tambahkan navigation buttons sebagai baris ketujuh
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
    
    # ✅ NEW: Handle Privacy State (Block/Unblock)
    if user_id in user_privacy_state:
        if text.lower() == "/cancel":
            state = user_privacy_state[user_id]
            del user_privacy_state[user_id]
            await m.reply(
                "❌ Dibatalkan.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menu", callback_data=f"privacy_menu_{state['session_index']}_{state['page']}")]])
            )
            return

        await execute_block_unblock(c, m, user_privacy_state[user_id])
        return

    # ✅ PERUBAHAN: Cek jika user sedang dalam konfirmasi edit profil
    # (Sekarang menggunakan Inline Button, tapi kita handle jika user masih mengetik secara manual)
    if user_id in user_edit_confirmation_state:
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
            except pyrogram.errors.exceptions.flood_420.FloodWait as wait_err:
                error_msg = f"FloodWait {wait_err.value} detik"
                await m.reply(f"⏳ FloodWait: Tunggu {wait_err.value} detik sebelum mencoba lagi.")
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
        
        # Simpan sementara di state konfirmasi
        user_edit_confirmation_state[user_id] = {
            'action': action,
            'session_index': session_index,
            'page': page,
            'data': text
        }
        # Kirim Tombol Konfirmasi
        confirm_buttons = [
            [
                InlineKeyboardButton("✅ Ya, Konfirmasi", f"edit_confirm_yes_{user_id}"),
                InlineKeyboardButton("❌ Tidak", f"edit_confirm_no_{user_id}")
            ]
        ]
        
        await m.reply(
            f"❓ <b>Konfirmasi Perubahan</b>\n\n"
            f"Aksi: <b>{action.replace('_', ' ').title()}</b>\n"
            f"Data Baru: <code>{html.escape(text)}</code>\n\n"
            f"Apakah Anda yakin ingin melanjutkan?",
            reply_markup=InlineKeyboardMarkup(confirm_buttons),
            parse_mode=ParseMode.HTML
        )
        return
    
        return
    
    # ✅ BARU: Cek jika user sedang menunggu input target untuk download foto profil
    elif user_id in user_dlphoto_state and user_dlphoto_state[user_id]['step'] == 'waiting_target':
        if text.lower() == "/cancel":
            del user_dlphoto_state[user_id]
            await m.reply("❌ Download foto dibatalkan.")
            return
        
        state = user_dlphoto_state[user_id]
        state['target'] = text
        state['step'] = 'confirming'
        
        buttons = [
            [
                InlineKeyboardButton("✅ Ya, Download", callback_data=f"dl_uphoto_exec_{user_id}"),
                InlineKeyboardButton("❌ Tidak", callback_data=f"session_info_{state['session_index']}_{state['page']}")
            ]
        ]
        
        await m.reply(
            f"<b>🖼️ Konfirmasi Download Foto</b>\n\n"
            f"Target: <code>{html.escape(text)}</code>\n"
            f"Sesi: <code>{state['session_index'] + 1}</code>\n\n"
            f"Apakah Anda yakin?",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )
        return

    # ✅ BARU: Cek jika user sedang menunggu input chat untuk purge
    elif user_id in user_purge_state and user_purge_state[user_id]['step'] == 'waiting_chat':
        if text.lower() == "/cancel":
            del user_purge_state[user_id]
            await m.reply("❌ Purge dibatalkan.")
            return
        
        state = user_purge_state[user_id]
        state['chat_id'] = text
        state['step'] = 'selecting_amount'
        
        # Tampilkan pilihan jumlah
        buttons = [
            [
                InlineKeyboardButton("1", callback_data=f"purge_amt_{user_id}_1"),
                InlineKeyboardButton("5", callback_data=f"purge_amt_{user_id}_5"),
                InlineKeyboardButton("10", callback_data=f"purge_amt_{user_id}_10"),
            ],
            [
                InlineKeyboardButton("15", callback_data=f"purge_amt_{user_id}_15"),
                InlineKeyboardButton("20", callback_data=f"purge_amt_{user_id}_20"),
                InlineKeyboardButton("25", callback_data=f"purge_amt_{user_id}_25"),
            ],
            [
                InlineKeyboardButton("30", callback_data=f"purge_amt_{user_id}_30"),
                InlineKeyboardButton("Custom", callback_data=f"purge_amt_{user_id}_custom"),
            ],
            [
                InlineKeyboardButton("🔙 Cancel", callback_data=f"session_info_{state['session_index']}_{state['page']}"),
            ]
        ]
        
        await m.reply(
            f"<b>🧹 Purge My Message</b>\n\n"
            f"Target Chat: <code>{html.escape(text)}</code>\n\n"
            f"Pilih jumlah pesan yang ingin dihapus:",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )
        return
    
    # ✅ BARU: Cek jika user sedang menunggu input jumlah custom untuk purge
    elif user_id in user_purge_state and user_purge_state[user_id]['step'] == 'waiting_custom_amount':
        if text.lower() == "/cancel":
            del user_purge_state[user_id]
            await m.reply("❌ Purge dibatalkan.")
            return
        
        try:
            amount = int(text)
            if amount < 1:
                await m.reply("❌ Jumlah harus lebih dari 0.")
                return
        except ValueError:
            await m.reply("❌ Masukkan angka yang valid.")
            return
        
        state = user_purge_state[user_id]
        state['amount'] = amount
        state['step'] = 'selecting_delay'
        
        # Tampilkan pilihan delay
        buttons = [
            [
                InlineKeyboardButton("0.5s", callback_data=f"purge_del_{user_id}_0.5"),
                InlineKeyboardButton("1s", callback_data=f"purge_del_{user_id}_1"),
            ],
            [
                InlineKeyboardButton("3s", callback_data=f"purge_del_{user_id}_3"),
                InlineKeyboardButton("5s", callback_data=f"purge_del_{user_id}_5"),
            ],
            [
                InlineKeyboardButton("🔙 Cancel", callback_data=f"session_info_{state['session_index']}_{state['page']}"),
            ]
        ]
        
        await m.reply(
            f"<b>🧹 Purge My Message</b>\n\n"
            f"Chat: <code>{html.escape(state['chat_id'])}</code>\n"
            f"Jumlah: <code>{amount}</code>\n\n"
            f"Pilih jeda (delay) antar pesan:",
            reply_markup=InlineKeyboardMarkup(buttons),
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
        if user_bulk_join_state[user_id].get('is_single'):
            # Single Join Confirmation
            confirmation_buttons = [
                [
                    InlineKeyboardButton("✅ Yes, Join", callback_data="join_confirm_yes"),
                    InlineKeyboardButton("❌ No, Cancel", callback_data="join_confirm_no")
                ]
            ]
            
            await m.reply(
                text=f"<b>➕ Confirm Join Group</b>\n\n"
                     f"• <b>Sesi:</b> <code>{index + 1}</code>\n"
                     f"• <b>Link:</b> <code>{link}</code>\n\n"
                     f"Pastikan link valid dan grup dapat di-join.",
                reply_markup=InlineKeyboardMarkup(confirmation_buttons),
                parse_mode=ParseMode.HTML
            )
        else:
            # Bulk Join Confirmation (Existing logic)
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
    
    # ✅ BARU: Cek jika user sedang dalam proses lihat mention
    elif user_id in user_mentions_state and user_mentions_state[user_id]['step'] == 'waiting_group':
        if text.lower() == "/cancel":
            del user_mentions_state[user_id]
            await m.reply("❌ Lihat mention dibatalkan.")
            return
        
        # Simpan group dan minta jumlah pesan
        user_mentions_state[user_id]['group'] = text
        user_mentions_state[user_id]['step'] = 'waiting_count'
        
        # Tampilkan pilihan jumlah pesan
        buttons = [
            [
                InlineKeyboardButton("10 pesan", callback_data=f"mention_count_{user_id}_10"),
                InlineKeyboardButton("20 pesan", callback_data=f"mention_count_{user_id}_20"),
            ],
            [
                InlineKeyboardButton("30 pesan", callback_data=f"mention_count_{user_id}_30"),
                InlineKeyboardButton("50 pesan", callback_data=f"mention_count_{user_id}_50"),
            ],
            [
                InlineKeyboardButton("🔙 Cancel", callback_data=f"cancel_mention_{user_id}"),
            ]
        ]
        
        await m.reply(
            text="<b>🔔 Lihat Mention</b>\n\n"
                 f"Group: <code>{html.escape(text)}</code>\n\n"
                 "Pilih jumlah pesan yang akan diperiksa (semakin banyak, semakin lama):",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )
        return
    
    # ✅ BARU: Cek jika user sedang dalam proses pesan terbaru
    elif user_id in user_recent_messages_state and user_recent_messages_state[user_id]['step'] == 'waiting_count':
        if text.lower() == "/cancel":
            del user_recent_messages_state[user_id]
            await m.reply("❌ Pesan terbaru dibatalkan.")
            return
        
        try:
            count = int(text)
            if count < 1 or count > 50:
                await m.reply("❌ Jumlah pesan harus antara 1-50.")
                return
        except ValueError:
            await m.reply("❌ Masukkan angka yang valid.")
            return
        
        # Proses mengambil pesan terbaru
        state = user_recent_messages_state[user_id]
        session_index = state['session_index']
        page = state.get('page', 1)
        
        if session_index >= len(Altruix.clients):
            await m.reply("❌ Session tidak ditemukan.")
            del user_recent_messages_state[user_id]
            return
        
        session_client = Altruix.clients[session_index]
        
        await m.reply(f"🔄 Mengambil {count} pesan terbaru...")
        
        try:
            messages = []
            async for dialog in session_client.get_dialogs(limit=100):
                if dialog.chat.type == ChatType.PRIVATE and dialog.top_message:
                    messages.append({
                        'chat': dialog.chat,
                        'message': dialog.top_message,
                        'date': dialog.top_message.date
                    })
            
            # Urutkan berdasarkan tanggal terbaru
            messages.sort(key=lambda x: x['date'], reverse=True)
            
            if not messages:
                await m.reply("❌ Tidak ada pesan terbaru ditemukan.")
                return
            
            # Ambil jumlah yang diminta
            messages = messages[:count]
            
            # Format hasil
            result_text = f"<b>📨 {len(messages)} Pesan Terbaru</b>\n\n"
            
            for i, msg_data in enumerate(messages, 1):
                chat = msg_data['chat']
                message = msg_data['message']
                
                # Ambil informasi pengirim
                sender_name = "Tidak diketahui"
                if hasattr(message, 'from_user') and message.from_user:
                    sender_name = message.from_user.first_name or "Tidak ada nama"
                
                # Ambil teks pesan
                message_text = message.text or message.caption or "[Media/Tidak ada teks]"
                if len(message_text) > 100:
                    message_text = message_text[:100] + "..."
                
                # Format waktu
                time_str = message.date.strftime('%d-%m-%Y %H:%M')
                
                result_text += (
                    f"<b>{i}. {html.escape(sender_name)}</b>\n"
                    f"   Waktu: {time_str}\n"
                    f"   Pesan: {html.escape(message_text)}\n"
                    f"   Chat ID: <code>{chat.id}</code>\n\n"
                )
            
            await m.reply(result_text, parse_mode=ParseMode.HTML)
            
            # Kirim notifikasi log
            await send_log_notification(
                c, 'recent_messages', session_index, m.from_user,
                True, None, {'Jumlah Pesan': count}
            )
            
        except Exception as e:
            error_msg = f"Gagal mengambil pesan: {str(e)}"
            await m.reply(f"❌ {error_msg}")
            Altruix.log(f"Error recent_messages session {session_index}: {e}", level=logging.ERROR)
            
            # Kirim notifikasi error ke log group
            await send_log_notification(
                c, 'recent_messages', session_index, m.from_user,
                False, str(e), {'Jumlah Pesan': count}
            )
        
        finally:
            # Hapus state
            if user_id in user_recent_messages_state:
                del user_recent_messages_state[user_id]
        
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

    # ✅ BARU: Handle Exec Terminal
    elif user_id in user_exec_state:
        state = user_exec_state[user_id]
        if text.lower() == "/cancel":
            del user_exec_state[user_id]
            await m.reply("❌ Exec canceled.", quote=True)
            return
            
        # Store command and confirm
        user_exec_state[user_id]['command'] = text
        
        # Show confirmation
        buttons = [
            [InlineKeyboardButton("▶️ Run Command", f"exec_term_{user_id}")],
            [InlineKeyboardButton("❌ Cancel", f"session_info_{state['session_index']}_{state['page']}")]
        ]
        
        await m.reply(
            f"🖥️ <b>Confirm Execution?</b>\n\nCommand:\n<pre>{html.escape(text)}</pre>",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )
        return

    # ✅ BARU: Handle System Control (Restart/Shutdown)
    elif user_id in user_sys_ctrl_state:
        state = user_sys_ctrl_state[user_id]
        if text.lower() == "/cancel":
            del user_sys_ctrl_state[user_id]
            await m.reply("❌ System control dibatalkan.", quote=True)
            return
            
        action = state['action']
        required = "11" if action == "shutdown" else "ok"
        
        if text.strip().lower() == required:
            # Execute
            readable = "Restart" if action == "restart" else "Shutdown"
            await m.reply(f"✅ Konfirmasi diterima. Melakukan {readable}...", quote=True)
            
            # Log to group
            log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))
            try:
                await Altruix.bot.send_message(
                    log_chat_id,
                    f"⚠️ <b>SYSTEM ALERT</b>\n"
                    f"• Action: <b>Force {readable}</b>\n"
                    f"• User: {m.from_user.mention}\n"
                    f"• Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    parse_mode=ParseMode.HTML
                )
            except: pass
            
            del user_sys_ctrl_state[user_id]
            
            if action == "restart":
                # Restart logic
                import sys
                os.execl(sys.executable, sys.executable, "-m", "Main")
            else:
                # Shutdown logic
                import sys
                sys.exit(0)
        else:
            await m.reply("❌ Password salah. Silakan coba lagi atau /cancel.", quote=True)
        return

    # ✅ BARU: Handle Eval Session
    elif user_id in user_eval_state:
        state = user_eval_state[user_id]
        if text.lower() == "/cancel":
            del user_eval_state[user_id]
            await m.reply("❌ Eval canceled.", quote=True)
            return
            
        # Store code and confirm
        user_eval_state[user_id]['code'] = text
        
        # Show confirmation
        buttons = [
            [InlineKeyboardButton("▶️ Run Code", f"eval_exec_{user_id}")],
            [InlineKeyboardButton("❌ Cancel", f"session_info_{state['session_index']}_{state['page']}")]
        ]
        
        await m.reply(
            f"🐍 <b>Confirm Execution?</b>\n\nCode:\n<pre>{html.escape(text)}</pre>",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )
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
                    "Gunakan tombol di bawah untuk konfirmasi:",
                    reply_markup=InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("✅ Ya, Ganti Foto", f"edit_confirm_yes_{user_id}"),
                            InlineKeyboardButton("❌ Tidak", f"edit_confirm_no_{user_id}")
                        ]
                    ]),
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
async def sessions_info_cb_handler(c: Client, cb: CallbackQuery, index: int = None, callback_page: int = None):
    try:
        await cb.answer()
    except:
        pass
    
    if index is None or callback_page is None:
        if not cb.matches:
            await cb.message.edit("Invalid callback.")
            return
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
        f"<b>📝 Bio:</b> <code>{html.escape(bio or 'None')}</code>\n"
        f"<b>🌐 DC ID:</b> <code>{dc_id or 'Unknown'}</code>\n"
        f"<b>🔗 Username:</b> @{username or 'None'}\n"
        f"<b>🆔 User ID:</b> <code>{user_id}</code>\n"
        f"<b>⚠️ Is SCAM:</b> <code>{'Yes' if is_scam else 'No'}</code>"
    )
    
    # ✅ PERUBAHAN: Tambahkan tombol-tombol edit profil sesuai permintaan
    buttons = [
        # Baris 1: Refresh dan Unlink
        [
            InlineKeyboardButton("🔄 Refresh data", f"refresh_session_info_{index}"),
            InlineKeyboardButton("🔗 Unlink (Remove)", f"unlink_session_{index}"),
        ]
    ]
    # ✅ REFACTORED BUTTONS WITH LOCALIZATION & CONFIRMATION
    buttons = [
        # Row 1: Refresh and Unlink
        [
            InlineKeyboardButton(gt("refresh_data"), f"gen_conf_refresh_session_info_{index}_{callback_page}"),
            InlineKeyboardButton(gt("unlink_session"), f"unlink_session_{index}"),
        ],
        # Row 2: Profile Management (GROUPED)
        [
             InlineKeyboardButton("✏️ Change Name", f"change_name_menu_{index}_{callback_page}"),
             InlineKeyboardButton(gt("change_bio"), f"gen_conf_change_bio_{index}_{callback_page}"),
        ],
        [
             InlineKeyboardButton(gt("change_username"), f"gen_conf_change_username_{index}_{callback_page}"),
             InlineKeyboardButton(gt("change_profile_photo"), f"gen_conf_change_profile_photo_{index}_{callback_page}"),
        ],
        # Row 2: Media & Downloads
        [
            InlineKeyboardButton(gt("download_story"), f"gen_conf_dlstory_session_input_{index}_{callback_page}"),
            InlineKeyboardButton(gt("download_content"), f"gen_conf_dl_content_input_{index}_{callback_page}"),
        ],
        [
            InlineKeyboardButton(gt("download_user_photo"), f"gen_conf_dl_uphoto_start_{index}_{callback_page}"),
            InlineKeyboardButton(gt("download_my_photo"), f"gen_conf_send_profile_photo_{index}_{callback_page}"),
        ],
        # Row 3: Account Security & Utility
        [
            InlineKeyboardButton(gt("export_session"), f"gen_conf_export_session_{index}_{callback_page}"),
            InlineKeyboardButton(gt("export_phone"), f"gen_conf_export_phone_{index}_{callback_page}"),
        ],
        [
            InlineKeyboardButton(gt("test_ping"), f"gen_conf_test_ping_{index}_{callback_page}"),
            InlineKeyboardButton(gt("check_limit"), f"check_limit_confirm_{index}_{callback_page}"),
        ],
        [
            InlineKeyboardButton(gt("view_sessions"), f"gen_conf_view_all_sessions_{index}_{callback_page}"),
            InlineKeyboardButton(gt("delete_all_photos"), f"delete_all_profile_photos_{index}_{callback_page}"),
        ],
        # Row 4: Group & Message Management
        [
            InlineKeyboardButton(gt("join_group"), f"gen_conf_join_chat_input_{index}_{callback_page}"),
            InlineKeyboardButton(gt("leave_group"), f"gen_conf_leave_chat_input_{index}_{callback_page}"),
        ],
        [
            InlineKeyboardButton(gt("purge_my_msg"), f"gen_conf_purge_msg_start_{index}_{callback_page}"),
            InlineKeyboardButton(gt("send_message"), f"gen_conf_send_message_input_{index}_{callback_page}"),
        ],
        # Row 5: Logs & Controls
        [
            InlineKeyboardButton("🔒 Privacy & Security", f"privacy_menu_{index}_{callback_page}"),
            InlineKeyboardButton("📊 Chat Stats", f"gen_conf_chat_stats_scan_{index}_{callback_page}"),
        ],
        [
            InlineKeyboardButton(gt("pm_logger_control"), f"pml_menu_{index}_{callback_page}"),
            InlineKeyboardButton(gt("mention_control"), f"mnt_menu_{index}_{callback_page}"),
        ],
        [
            InlineKeyboardButton(gt("recent_messages"), f"gen_conf_recent_messages_menu_{index}_{callback_page}"),
            InlineKeyboardButton(gt("view_mentions"), f"gen_conf_view_mentions_menu_{index}_{callback_page}"),
        ],
        # Row 6: Advanced Tools
        [
            InlineKeyboardButton("🐍 Eval Python", f"eval_session_{index}_{callback_page}"),
            InlineKeyboardButton("🖥️ Exec Terminal", f"exec_session_{index}_{callback_page}"),
        ],
        # Back button
        [
            InlineKeyboardButton(gt("back"), f"sessions_list_{callback_page}"),
        ],
    ]

    await cb.message.edit(
        text=f"{gt('session_info_title')}\n\n"
             f"👤 <b>User:</b> <code>{html.escape(session_info.first_name or '')}</code>\n"
             f"🆔 <b>ID:</b> <code>{session_info.id}</code>\n"
             f"📞 <b>Phone:</b> <code>+{session_info.phone_number or 'N/A'}</code>\n"
             f"💠 <b>DC:</b> <code>{session_info.dc_id or 'N/A'}</code>\n"
             f"🏷 <b>Username:</b> @{session_info.username or 'None'}\n\n"
             f"<i>Manage this session using the buttons below:</i>",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )


# ✅ HANDLER BARU: Menu Ganti Nama
@Altruix.bot.on_callback_query(filters.regex(r"change_name_menu_(\d+)_(\d+)"))
@log_errors
async def change_name_menu_handler(c: Client, cb: CallbackQuery):
    """Handler untuk menu ganti nama (First/Last)"""
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    
    buttons = [
        [
            InlineKeyboardButton(gt("first_name"), f"gen_conf_change_first_name_{index}_{page}"),
            InlineKeyboardButton(gt("last_name"), f"gen_conf_change_last_name_{index}_{page}"),
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data=f"session_info_{index}_{page}"),
        ]
    ]
    
    await cb.message.edit(
        text="<b>✏️ Ganti Nama</b>\n\n"
             "Pilih bagian nama yang ingin Anda ubah:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )


# ✅ HANDLER BARU: Download Content Input
@Altruix.bot.on_callback_query(filters.regex(r"^dl_content_input_(\d+)_(\d+)$"))
@log_errors
async def dl_content_input_handler(c: Client, cb: CallbackQuery):
    """Menerima input link pesan untuk didownload/forward"""
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    
    if index >= len(Altruix.clients):
        await cb.answer("❌ Session tidak ditemukan.", show_alert=True)
        return

    session_client = Altruix.clients[index]
    session_info = getattr(session_client, 'myself', None) or await session_client.get_me()
    
    await cb.message.edit(
        f"📥 <b>Download Konten</b>\n\n"
        f"Akun pengeksekusi: <b>{html.escape(session_info.first_name)}</b>\n\n"
        f"Silakan kirim <b>Link Pesan</b> (misal: <code>https://t.me/username/123</code>).\n"
        f"Konten akan dikirim ke <b>Altruix Log Group</b>.\n\n"
        f"Ketik <code>cancel</code> untuk membatalkan.",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(gt("cancel"), f"session_info_{index}_{page}")]])
    )
    
    try:
        user_id = cb.from_user.id
        msg = await c.listen(filters.chat(user_id) & filters.text, timeout=120)
        
        if msg.text.lower() == 'cancel':
            await msg.delete()
            await cb.message.edit("❌ Dibatalkan.")
            await asyncio.sleep(2)
            await sessions_info_cb_handler(c, cb)
            return
            
        link = msg.text.strip()
        await msg.delete()
        
        await cb.message.edit("🔄 <b>Sedang memproses...</b>")
        await process_download_content(c, cb, session_client, link, index, page)
        
    except asyncio.TimeoutError:
        await cb.message.edit("⏳ Waktu habis. Silakan coba lagi.")
    except Exception as e:
        await cb.message.edit(f"❌ Error: {str(e)}")


async def process_download_content(c, cb, session_client, link, index, page):
    """Helper untuk memproses download konten dari link"""
    try:
        # Simple link parsing
        if "t.me/" not in link:
            await cb.message.edit("❌ <b>Link tidak valid!</b>")
            return

        parts = link.split("/")
        msg_id = int(parts[-1])
        target = parts[-2]
        if parts[-3] == 'c':
             target = int(f"-100{parts[-2]}")
             msg_id = int(parts[-1])
        
        log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))
        
        # Try to get message
        msg = await session_client.get_messages(target, msg_id)
        if not msg:
            await cb.message.edit("❌ <b>Pesan tidak ditemukan!</b>")
            return

        # Attempt to copy first
        try:
            await msg.copy(log_chat_id)
            await cb.message.edit("✅ <b>Berhasil!</b> Konten telah disalin ke Log Group.")
        except Exception:
            # Fallback for restricted: Download and Upload
            await cb.message.edit("🔄 <b>Copy gagal, mencoba Bypass (Download & Upload)...</b>")
            file_path = await session_client.download_media(msg)
            if file_path:
                try:
                    caption = msg.caption or f"📥 Content from {link}"
                    if msg.photo:
                        await c.send_photo(log_chat_id, file_path, caption=caption)
                    elif msg.video:
                        await c.send_video(log_chat_id, file_path, caption=caption)
                    elif msg.document:
                        await c.send_document(log_chat_id, file_path, caption=caption)
                    elif msg.audio:
                        await c.send_audio(log_chat_id, file_path, caption=caption)
                    elif msg.voice:
                        await c.send_voice(log_chat_id, file_path, caption=caption)
                    elif msg.animation:
                        await c.send_animation(log_chat_id, file_path, caption=caption)
                    
                    await cb.message.edit("✅ <b>Bypass Berhasil!</b> Konten telah diupload ke Log Group.")
                finally:
                    if os.path.exists(file_path):
                        os.remove(file_path)
            else:
                # Text only?
                if msg.text:
                    await c.send_message(log_chat_id, f"📥 <b>Text Content:</b>\n\n{msg.text}")
                    await cb.message.edit("✅ <b>Berhasil!</b> Teks telah disalin ke Log Group.")
                else:
                    await cb.message.edit("❌ <b>Gagal mendownload media.</b>")

        # Log
        await send_log_notification(
            c, 'download_content', index, cb.from_user,
            True, None, {'Link': link}
        )

    except Exception as e:
        await cb.message.edit(f"❌ <b>Gagal:</b> {str(e)}")
        await send_log_notification(
            c, 'download_content', index, cb.from_user,
            False, str(e), {'Link': link}
        )
    
    await asyncio.sleep(3)
    await sessions_info_cb_handler(c, cb)


# ✅ HANDLER BARU: Menu Pesan Terbaru
@Altruix.bot.on_callback_query(filters.regex(r"recent_messages_menu_(\d+)_(\d+)"))
@log_errors
async def recent_messages_menu_handler(c: Client, cb: CallbackQuery):
    """Handler untuk menu pesan terbaru"""
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    
    # Tampilkan pilihan jumlah pesan
    buttons = [
        [
            InlineKeyboardButton("3 pesan", callback_data=f"recent_messages_quick_{index}_{page}_3"),
            InlineKeyboardButton("6 pesan", callback_data=f"recent_messages_quick_{index}_{page}_6"),
        ],
        [
            InlineKeyboardButton("9 pesan", callback_data=f"recent_messages_quick_{index}_{page}_9"),
            InlineKeyboardButton("11 pesan", callback_data=f"recent_messages_quick_{index}_{page}_11"),
        ],
        [
            InlineKeyboardButton("📝 Custom jumlah", callback_data=f"recent_messages_custom_{index}_{page}"),
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data=f"session_info_{index}_{page}"),
        ]
    ]
    
    await cb.message.edit(
        text="<b>📨 Pesan Terbaru</b>\n\n"
             "Pilih jumlah pesan terbaru yang akan ditampilkan (dari chat private):\n\n"
             "⚠️ <b>Note:</b>\n"
             "• Hanya menampilkan pesan dari chat private\n"
             "• Pesan diurutkan berdasarkan waktu terbaru",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )


# ✅ HANDLER BARU: Pesan Terbaru Quick Select
@Altruix.bot.on_callback_query(filters.regex(r"recent_messages_quick_(\d+)_(\d+)_(\d+)"))
@log_errors
async def recent_messages_quick_handler(c: Client, cb: CallbackQuery):
    """Handler untuk pesan terbaru quick select"""
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    count = int(cb.matches[0].group(3))
    
    user_id = cb.from_user.id
    user_recent_messages_state[user_id] = {
        'session_index': index,
        'page': page,
        'step': 'waiting_count',
        'count': count
    }
    
    # Langsung proses
    await cb.message.edit(f"🔄 Mengambil {count} pesan terbaru...")
    
    try:
        if index >= len(Altruix.clients):
            await cb.message.edit("❌ Session tidak ditemukan.")
            if user_id in user_recent_messages_state:
                del user_recent_messages_state[user_id]
            return
        
        session_client = Altruix.clients[index]
        
        messages = []
        async for dialog in session_client.get_dialogs(limit=100):
            if dialog.chat.type == ChatType.PRIVATE and dialog.top_message:
                messages.append({
                    'chat': dialog.chat,
                    'message': dialog.top_message,
                    'date': dialog.top_message.date
                })
        
        # Urutkan berdasarkan tanggal terbaru
        messages.sort(key=lambda x: x['date'], reverse=True)
        
        if not messages:
            await cb.message.edit("❌ Tidak ada pesan terbaru ditemukan.")
            return
        
        # Ambil jumlah yang diminta
        messages = messages[:count]
        
        # Format hasil
        result_text = f"<b>📨 {len(messages)} Pesan Terbaru</b>\n\n"
        
        for i, msg_data in enumerate(messages, 1):
            chat = msg_data['chat']
            message = msg_data['message']
            
            # Ambil informasi pengirim
            sender_name = "Tidak diketahui"
            if hasattr(message, 'from_user') and message.from_user:
                sender_name = message.from_user.first_name or "Tidak ada nama"
            
            # Ambil teks pesan
            message_text = message.text or message.caption or "[Media/Tidak ada teks]"
            if len(message_text) > 100:
                message_text = message_text[:100] + "..."
            
            # Format waktu
            time_str = message.date.strftime('%d-%m-%Y %H:%M')
            
            result_text += (
                f"<b>{i}. {html.escape(sender_name)}</b>\n"
                f"   Waktu: {time_str}\n"
                f"   Pesan: {html.escape(message_text)}\n"
                f"   Chat ID: <code>{chat.id}</code>\n\n"
            )
        
        # Tambahkan tombol kembali
        buttons = [
            [InlineKeyboardButton("🔙 Back", callback_data=f"session_info_{index}_{page}")]
        ]
        
        await cb.message.edit(
            text=result_text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )
        
        # Kirim notifikasi log
        await send_log_notification(
            c, 'recent_messages', index, cb.from_user,
            True, None, {'Jumlah Pesan': count}
        )
        
    except Exception as e:
        error_msg = f"Gagal mengambil pesan: {str(e)}"
        await cb.message.edit(f"❌ {error_msg}")
        Altruix.log(f"Error recent_messages session {index}: {e}", level=logging.ERROR)
        
        # Kirim notifikasi error ke log group
        await send_log_notification(
            c, 'recent_messages', index, cb.from_user,
            False, str(e), {'Jumlah Pesan': count}
        )
    
    finally:
        # Hapus state
        if user_id in user_recent_messages_state:
            del user_recent_messages_state[user_id]


# ✅ HANDLER BARU: Pesan Terbaru Custom
@Altruix.bot.on_callback_query(filters.regex(r"recent_messages_custom_(\d+)_(\d+)"))
@log_errors
async def recent_messages_custom_handler(c: Client, cb: CallbackQuery):
    """Handler untuk pesan terbaru custom jumlah"""
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    
    user_id = cb.from_user.id
    user_recent_messages_state[user_id] = {
        'session_index': index,
        'page': page,
        'step': 'waiting_count'
    }
    
    await cb.message.edit(
        text="<b>📨 Pesan Terbaru (Custom)</b>\n\n"
             "Silakan kirim jumlah pesan yang ingin ditampilkan (1-50):\n\n"
             "❌ <b>Cancel:</b> Ketik /cancel",
        parse_mode=ParseMode.HTML
    )


# ✅ HANDLER BARU: Menu Lihat Mention
@Altruix.bot.on_callback_query(filters.regex(r"view_mentions_menu_(\d+)_(\d+)"))
@log_errors
async def view_mentions_menu_handler(c: Client, cb: CallbackQuery):
    """Handler untuk menu lihat mention"""
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    
    user_id = cb.from_user.id
    user_mentions_state[user_id] = {
        'session_index': index,
        'page': page,
        'step': 'waiting_group'
    }
    
    await cb.message.edit(
        text="<b>🔔 Lihat Mention</b>\n\n"
             "Silakan kirim username atau ID group (contoh: @username atau -1001234567890):\n\n"
             "❌ <b>Cancel:</b> Ketik /cancel",
        parse_mode=ParseMode.HTML
    )


# ✅ HANDLER BARU: Pilihan Jumlah Mention
@Altruix.bot.on_callback_query(filters.regex(r"mention_count_(\d+)_(\d+)"))
@log_errors
async def mention_count_handler(c: Client, cb: CallbackQuery):
    """Handler untuk pilihan jumlah mention"""
    await cb.answer()
    user_id = int(cb.matches[0].group(1))
    count = int(cb.matches[0].group(2))
    
    if user_id not in user_mentions_state:
        await cb.message.edit("❌ Session tidak ditemukan atau state expired.")
        return
    
    state = user_mentions_state[user_id]
    index = state['session_index']
    page = state.get('page', 1)
    group = state.get('group')
    
    if index >= len(Altruix.clients):
        await cb.message.edit("❌ Session tidak ditemukan.")
        if user_id in user_mentions_state:
            del user_mentions_state[user_id]
        return
    
    session_client = Altruix.clients[index]
    session_info = getattr(session_client, 'myself', None) or await session_client.get_me()
    
    await cb.message.edit(f"🔔 Mencari mention di {group}...")
    
    try:
        # Resolve group
        try:
            chat = await session_client.get_chat(group)
        except Exception as e:
            await cb.message.edit(f"❌ Gagal mendapatkan group: {str(e)}")
            if user_id in user_mentions_state:
                del user_mentions_state[user_id]
            return
        
        # Ambil pesan dari group
        messages = []
        async for message in session_client.get_chat_history(chat.id, limit=count):
            # Cek apakah pesan mengandung mention ke akun kita
            if message.entities:
                for entity in message.entities:
                    if entity.type == "mention":
                        # Cek mention username kita
                        mentioned_username = message.text[entity.offset:entity.offset+entity.length]
                        if mentioned_username.lower() == f"@{session_info.username}".lower():
                            messages.append(message)
                            break
                    elif entity.type == "text_mention":
                        if entity.user.id == session_info.id:
                            messages.append(message)
                            break
        
        if not messages:
            await cb.message.edit(f"❌ Tidak ditemukan mention untuk @{session_info.username} di group {chat.title}.")
            if user_id in user_mentions_state:
                del user_mentions_state[user_id]
            return
        
        # Format pesan
        text = f"<b>🔔 Mention di {html.escape(chat.title)}</b>\n\n"
        buttons = []
        for i, msg in enumerate(messages, 1):
            sender = msg.from_user.first_name if msg.from_user else "Unknown"
            m_time = msg.date.strftime('%H:%M')
            preview = msg.text[:50] + "..." if msg.text and len(msg.text) > 50 else (msg.text or "[Media]")
            text += f"<b>{i}. {html.escape(sender)}</b> ({m_time}): {html.escape(preview)}\n\n"
            
            # Button untuk reply ke PM
            if msg.from_user:
                buttons.append([InlineKeyboardButton(f"💬 Reply PM to {sender}", f"rpm_conf_{index}_{chat.id}_{msg.id}")])
        
        # Tambahkan tombol kembali
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"session_info_{index}_{page}")])
        
        await cb.message.edit(
            text=text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )
        
        # Kirim log
        await send_log_notification(
            c, 'view_mentions', index, cb.from_user,
            True, None, {'Group': group, 'Jumlah Pesan': count, 'Mention Ditemukan': len(messages)}
        )
        
    except Exception as e:
        await cb.message.edit(f"❌ Gagal mencari mention: {str(e)}")
        Altruix.log(f"Error view_mentions session {index}: {e}", level=logging.ERROR)
        await send_log_notification(
            c, 'view_mentions', index, cb.from_user,
            False, str(e), {'Group': group, 'Jumlah Pesan': count}
        )
    
    finally:
        # Hapus state
        if user_id in user_mentions_state:
            del user_mentions_state[user_id]


# ✅ HANDLER BARU: Cancel Mention
@Altruix.bot.on_callback_query(filters.regex(r"cancel_mention_(\d+)"))
@log_errors
async def cancel_mention_handler(c: Client, cb: CallbackQuery):
    """Handler untuk cancel mention"""
    user_id = int(cb.matches[0].group(1))
    if user_id in user_mentions_state:
        del user_mentions_state[user_id]
    await cb.answer("Cancelled.")
    await cb.message.edit("❌ Lihat mention dibatalkan.")


# ✅ HANDLER BARU: Kirim Foto Profil
@Altruix.bot.on_callback_query(filters.regex(r"send_profile_photo_(\d+)_(\d+)"))
@log_errors
async def send_profile_photo_handler(c: Client, cb: CallbackQuery):
    """Handler untuk mengirim foto profil"""
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    
    if index >= len(Altruix.clients):
        await cb.answer("❌ Session tidak ditemukan.", show_alert=True)
        return
    
    session_client = Altruix.clients[index]
    session_info = getattr(session_client, 'myself', None) or await session_client.get_me()
    
    await cb.answer("🖼️ Mengirim foto profil...", show_alert=False)
    
    try:
        # Ambil foto profil
        photos = []
        async for photo in session_client.get_chat_photos("me", limit=1):
            photos.append(photo)
        
        if not photos:
            await cb.message.edit("❌ Akun ini tidak memiliki foto profil.")
            # Kirim log
            await send_log_notification(
                c, 'send_profile_photo', index, cb.from_user,
                False, "Tidak ada foto profil", {'Aksi': 'Kirim foto profil gagal'}
            )
            return
        
        # Download media ke lokal lalu kirim (untuk hindari MEDIA_EMPTY karena Bot beda database file_id)
        photo_path = await session_client.download_media(photos[0])
        
        # Kirim foto ke user
        await c.send_photo(
            chat_id=cb.from_user.id,
            photo=photo_path,
            caption=f"🖼️ Foto profil akun: {html.escape(session_info.first_name or '')}\n"
                   f"ID: <code>{session_info.id}</code>",
            parse_mode=ParseMode.HTML
        )
        
        # Hapus file temp
        if os.path.exists(photo_path):
            os.remove(photo_path)
        
        await cb.message.edit("✅ Foto profil telah dikirim ke pesan pribadi Anda.")
        
        # Kirim log
        await send_log_notification(
            c, 'send_profile_photo', index, cb.from_user,
            True, None, {'Aksi': 'Kirim foto profil berhasil'}
        )
        
    except FloodWait as e:
        await cb.message.edit(f"⏳ FloodWait: Tunggu {e.value} detik.")
        await send_log_notification(
            c, 'send_profile_photo', index, cb.from_user,
            False, f"FloodWait {e.value}s", {'Aksi': 'Kirim foto profil gagal'}
        )
    except Exception as e:
        await cb.message.edit(f"❌ Gagal mengirim foto profil: {str(e)}")
        Altruix.log(f"Error send_profile_photo session {index}: {e}", level=logging.ERROR)
        await send_log_notification(
            c, 'send_profile_photo', index, cb.from_user,
            False, str(e), {'Aksi': 'Kirim foto profil gagal'}
        )

# ✅ HANDLER BARU: Leave Chat (Group/Channel)
@Altruix.bot.on_callback_query(filters.regex(r"leave_chat_input_(\d+)_(\d+)"))
@log_errors
async def leave_chat_input_handler(c: Client, cb: CallbackQuery):
    """Menerima input chat_id atau username untuk leave"""
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    
    if index >= len(Altruix.clients):
        await cb.answer("❌ Session tidak ditemukan.", show_alert=True)
        return

    session_client = Altruix.clients[index]
    session_info = getattr(session_client, 'myself', None) or await session_client.get_me()
    
    prompt = await cb.message.edit(
        f"🏃 <b>Leave Group/Channel</b>\n\n"
        f"Akun: <b>{html.escape(session_info.first_name)}</b>\n\n"
        f"Silakan kirim <b>Username</b> (misal: @groupname) atau <b>Chat ID</b> grup yang ingin ditinggalkan.\n\n"
        f"Ketik <code>cancel</code> untuk membatalkan.",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", f"session_info_{index}_{page}")]])
    )
    
    try:
        user_id = cb.from_user.id
        msg = await c.listen(filters.chat(user_id) & filters.text, timeout=120)
        
        if msg.text.lower() == 'cancel':
            await msg.delete()
            await cb.message.edit("❌ Dibatalkan.")
            await asyncio.sleep(2)
            await sessions_info_cb_handler(c, cb)
            return
            
        target = msg.text.strip()
        await msg.delete()
        
        # Konfirmasi
        confirm_buttons = [
            [
                InlineKeyboardButton("✅ Ya, Keluar Sekarang", f"leave_chat_confirm_{index}_{page}_{target}"),
                InlineKeyboardButton("❌ Tidak", f"session_info_{index}_{page}")
            ]
        ]
        
        await cb.message.edit(
            f"❓ <b>Konfirmasi Keluar</b>\n\n"
            f"Apakah Anda yakin ingin menyuruh akun <b>{html.escape(session_info.first_name)}</b> keluar dari <code>{target}</code>?",
            reply_markup=InlineKeyboardMarkup(confirm_buttons),
            parse_mode=ParseMode.HTML
        )
        
    except asyncio.TimeoutError:
        await cb.message.edit("⏳ Waktu habis. Silakan coba lagi.")
    except Exception as e:
        await cb.message.edit(f"❌ Error: {str(e)}")

@Altruix.bot.on_callback_query(filters.regex(r"leave_chat_confirm_(\d+)_(\d+)_(.+)"))
@log_errors
async def leave_chat_confirm_handler(c: Client, cb: CallbackQuery):
    """Eksekusi leave chat setelah konfirmasi"""
    await cb.answer("Memproses...", show_alert=False)
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    target = cb.matches[0].group(3)
    
    # FIX: Convert to int if target is a chat ID (digits)
    if target.lstrip('-').isdigit():
        target = int(target)
    
    if index >= len(Altruix.clients):
        await cb.answer("❌ Session tidak ditemukan.", show_alert=True)
        return

    session_client = Altruix.clients[index]
    
    try:
        # Coba resolve chat dulu
        chat = await session_client.get_chat(target)
        chat_title = chat.title or chat.first_name or target
        
        await session_client.leave_chat(target)
        
        await cb.message.edit(f"✅ Berhasil keluar dari <b>{html.escape(str(chat_title))}</b>")
        
        # Log
        await send_log_notification(
            c, 'leave_chat', index, cb.from_user,
            True, None, {'Target': target, 'Title': chat_title}
        )
        
        await asyncio.sleep(3)
        await sessions_info_cb_handler(c, cb)
        
    except Exception as e:
        await cb.message.edit(f"❌ Gagal keluar dari {target}: {str(e)}")
        await send_log_notification(
            c, 'leave_chat', index, cb.from_user,
            False, str(e), {'Target': target}
        )

# ✅ HANDLER BARU: Send Message Direct
@Altruix.bot.on_callback_query(filters.regex(r"send_message_input_(\d+)_(\d+)"))
@log_errors
async def send_message_input_handler(c: Client, cb: CallbackQuery):
    """Menerima input target dan teks pesan"""
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    
    if index >= len(Altruix.clients):
        await cb.answer("❌ Session tidak ditemukan.", show_alert=True)
        return

    session_client = Altruix.clients[index]
    session_info = getattr(session_client, 'myself', None) or await session_client.get_me()
    
    await cb.message.edit(
        f"✉️ <b>Send Message Direct</b>\n\n"
        f"Akun pengirim: <b>{html.escape(session_info.first_name)}</b>\n\n"
        f"Silakan kirim <b>Target</b> (Username @... atau ID).\n"
        f"Ketik <code>cancel</code> untuk membatalkan.",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", f"session_info_{index}_{page}")]])
    )
    
    try:
        user_id = cb.from_user.id
        msg_target = await c.listen(filters.chat(user_id) & filters.text, timeout=60)
        
        if msg_target.text.lower() == 'cancel':
            await msg_target.delete()
            await cb.message.edit("❌ Dibatalkan.")
            await asyncio.sleep(2)
            await sessions_info_cb_handler(c, cb)
            return
            
        target = msg_target.text.strip()
        await msg_target.delete()
        
        # Minta isi pesan
        await cb.message.edit(
            f"✉️ <b>Send Message Direct</b>\n\n"
            f"Target: <code>{target}</code>\n\n"
            f"Sekarang kirim <b>Pesan</b> yang ingin dikirim.\n"
            f"Ketik <code>cancel</code> untuk membatalkan.",
            parse_mode=ParseMode.HTML
        )
        
        msg_text = await c.listen(filters.chat(user_id) & filters.text, timeout=120)
        
        if msg_text.text.lower() == 'cancel':
            await msg_text.delete()
            await cb.message.edit("❌ Dibatalkan.")
            return
            
        text_to_send = msg_text.text
        await msg_text.delete()
        
        # Konfirmasi
        confirm_buttons = [
            [
                InlineKeyboardButton("✅ Ya, Kirim Sekarang", f"send_msg_confirm_{index}_{page}"),
                InlineKeyboardButton("❌ Tidak", f"session_info_{index}_{page}")
            ]
        ]
        
        # Simpan pesan sementara di state (atau bisa di callback data jika pendek, tapi mending di state)
        # Untuk simplicity di sini saya pakai temp state
        user_limit_check_state[user_id] = {'target': target, 'text': text_to_send}
        
        await cb.message.edit(
            f"❓ <b>Konfirmasi Kirim Pesan</b>\n\n"
            f"<b>Pengirim:</b> {html.escape(session_info.first_name)}\n"
            f"<b>Target:</b> <code>{target}</code>\n"
            f"<b>Pesan:</b>\n<i>{html.escape(text_to_send[:100])}{'...' if len(text_to_send) > 100 else ''}</i>\n\n"
            f"Apakah Anda yakin?",
            reply_markup=InlineKeyboardMarkup(confirm_buttons),
            parse_mode=ParseMode.HTML
        )
        
    except asyncio.TimeoutError:
        await cb.message.edit("⏳ Waktu habis. Silakan coba lagi.")
    except Exception as e:
        await cb.message.edit(f"❌ Error: {str(e)}")

@Altruix.bot.on_callback_query(filters.regex(r"send_msg_confirm_(\d+)_(\d+)"))
@log_errors
async def send_msg_confirm_handler(c: Client, cb: CallbackQuery):
    """Eksekusi kirim pesan setelah konfirmasi"""
    await cb.answer("Mengirim...", show_alert=False)
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    user_id = cb.from_user.id
    
    state = user_limit_check_state.get(user_id)
    if not state or 'target' not in state:
        await cb.answer("❌ Data tidak ditemukan atau kadaluarsa.", show_alert=True)
        return
        
    target = state['target']
    text = state['text']
    
    # FIX: Convert to int if target is a chat ID (digits)
    if target.lstrip('-').isdigit():
        target = int(target)
    
    if index >= len(Altruix.clients):
        await cb.answer("❌ Session tidak ditemukan.", show_alert=True)
        return

    session_client = Altruix.clients[index]
    
    try:
        await session_client.send_message(target, text)
        await cb.message.edit(f"✅ Pesan berhasil dikirim ke <code>{target}</code>")
        
        # Log
        await send_log_notification(
            c, 'send_direct_message', index, cb.from_user,
            True, None, {'Target': target}
        )
        
        # Bersihkan state
        user_limit_check_state.pop(user_id, None)
        
        await asyncio.sleep(3)
        await sessions_info_cb_handler(c, cb)
        
    except Exception as e:
        await cb.message.edit(f"❌ Gagal mengirim pesan ke {target}: {str(e)}")
        await send_log_notification(
            c, 'send_direct_message', index, cb.from_user,
            False, str(e), {'Target': target}
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
             "Pilih tombol di bawah untuk lanjut:",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Ya, Hapus Semua", f"edit_confirm_yes_{user_id}"),
                InlineKeyboardButton("❌ Tidak", f"session_info_{index}_{page}")
            ]
        ]),
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


@Altruix.bot.on_callback_query(filters.regex(r"^export_session_(\d+)$"))
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


@Altruix.bot.on_callback_query(filters.regex(r"^refresh_session_info_(\d+)$"))
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
    await sessions_info_cb_handler(c, cb, index=index, callback_page=1)


@Altruix.bot.on_callback_query(filters.regex(r"^unlink_session_(\d+)$"))
@log_errors
async def unlink_session_cb_handler(c: Client, cb: CallbackQuery):
    index = int(cb.matches[0].group(1))
    
    if index >= len(Altruix.clients):
        await cb.answer("Session already removed or invalid.", show_alert=True)
        return

    # Gunakan Tombol Konfirmasi Inline sesuai permintaan user
    confirm_buttons = [
        [
            InlineKeyboardButton(gt("yes"), f"unlink_confirm_{index}"),
            InlineKeyboardButton(gt("no"), f"session_info_{index}_1") # Kembali ke info
        ]
    ]

    await cb.message.edit(
        f"❓ <b>{gt('unlink_session')}</b>\n\n"
        f"Apakah Anda yakin ingin menghapus/unlink session index <b>{index + 1}</b>?\n"
        f"<i>{gt('unlink_explain')}</i>\n\n"
        f"<b>Fungsi:</b> Unlink akan menghapus sesi ini dari konfigurasi (.env/Database) dan menghentikan koneksinya. "
        "Akun ini tidak akan lagi digunakan oleh bot ini sampai ditambahkan kembali.",
        reply_markup=InlineKeyboardMarkup(confirm_buttons),
        parse_mode=ParseMode.HTML
    )

@Altruix.bot.on_callback_query(filters.regex(r"^unlink_confirm_(\d+)$"))
@log_errors
async def unlink_confirm_handler(c: Client, cb: CallbackQuery):
    """Eksekusi unlink setelah konfirmasi tombol"""
    index = int(cb.matches[0].group(1))
    await cb.answer("Processing...", show_alert=False)
    
    try:
        await cb.message.edit(f"⏳ {gt('unlink_session')}...")
        await Altruix.remove_session(index)
        await cb.answer("Sesi berhasil dihapus. Restarting...", show_alert=True)
        # ✅ REFINED: Sebaiknya restart agar sesi benar-benar bersih dari list memori di semua plugin
        await Altruix._restart(soft=True)
    except Exception as e:
        await cb.message.edit(f"❌ Gagal menghapus sesi: {e}")


# ✅ HANDLER BARU: Lihat Semua Sesi Login
@Altruix.bot.on_callback_query(filters.regex(r"^view_all_sessions_(\d+)_(\d+)$"))
@log_errors
async def view_all_sessions_handler(c: Client, cb: CallbackQuery):
    await cb.answer("🔍 Mengambil data sesi...", show_alert=False)
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))

    if index >= len(Altruix.clients):
        await cb.message.edit("❌ Session tidak ditemukan.")
        return

    session_client = Altruix.clients[index]
    
    try:
        from pyrogram.raw.functions.account import GetAuthorizations
        auths_obj = await session_client.invoke(GetAuthorizations())
        auths = auths_obj.authorizations
        
        if not auths:
            await cb.message.edit(
                text="ℹ️ Tidak ada sesi aktif selain ini.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}")]
                ])
            )
            return

        out = f"<b>📱 Total Sesi Aktif: {len(auths)}</b>\n\n"
        for i, s in enumerate(auths, 1):
            cur = " ← <b>Sesi ini</b>" if s.current else ""
            out += f"<b>{i}.</b> {html.escape(s.device_model or 'Unknown')} • {html.escape(s.app_name or 'Unknown')} {html.escape(s.app_version or '')}{cur}\n"
            out += f" ├ OS: <code>{html.escape(s.platform or 'Unknown')} {html.escape(s.system_version or '-')}</code>\n"
            out += f" ├ IP: <code>{s.ip or 'Unknown'}</code> • {s.country or 'Unknown'}\n"
            out += f" └ Login: <code>{s.date_created or 'Unknown'}</code>\n\n"

        await cb.message.edit(
            text=out,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}")]
            ]),
            parse_mode=ParseMode.HTML
        )
        
        # Kirim notifikasi log
        await send_log_notification(
            c, 'view_all_sessions', index, cb.from_user, 
            True, None, {'Total Sesi': len(auths)}
        )

    except Exception as e:
        await cb.message.edit(
            text=f"❌ Gagal mengambil data sesi: {html.escape(str(e))}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}")]
            ])
        )
        await send_log_notification(
            c, 'view_all_sessions', index, cb.from_user, 
            False, str(e), {}
        )


# ✅ HANDLER BARU: Join Group/Channel Input
@Altruix.bot.on_callback_query(filters.regex(r"^join_chat_input_(\d+)_(\d+)$"))
@log_errors
async def join_chat_input_handler(c: Client, cb: CallbackQuery):
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    user_id = cb.from_user.id
    
    # Simpan state
    user_bulk_join_state[user_id] = {
        'session_index': index,
        'page': page,
        'step': 'waiting_link',
        'delay': 0, # Not bulk, but we reuse the state dict for simplicity
        'is_single': True
    }
    
    await cb.message.edit(
        text="<b>➕ Join Group/Channel</b>\n\n"
             "Silakan kirimkan link group/channel atau username.\n\n"
             "Contoh:\n"
             "• <code>@username</code>\n"
             "• <code>https://t.me/joinchat/xxxxx</code>\n"
             "• <code>https://t.me/+xxxxx</code>\n\n"
             "Kirim <code>/cancel</code> untuk membatalkan.",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Batal", callback_data=f"session_info_{index}_{page}")]
        ])
    )


# ✅ HANDLER BARU: Join Chat Confirm (Di panggil dari handle_reply)
@Altruix.bot.on_callback_query(filters.regex(r"^join_confirm_(yes|no)$"))
@log_errors
async def join_chat_confirm_handler(c: Client, cb: CallbackQuery):
    user_id = cb.from_user.id
    action = cb.matches[0].group(1)
    
    if user_id not in user_bulk_join_state:
        await cb.answer("❌ State tidak ditemukan.", show_alert=True)
        return
        
    state = user_bulk_join_state[user_id]
    index = state['session_index']
    page = state['page']
    link = state['link']
    
    if action == "no":
        del user_bulk_join_state[user_id]
        await cb.answer("Dibatalkan")
        await cb.message.delete()
        return
        
    await cb.answer("⏳ Mencoba join...", show_alert=False)
    await cb.message.edit(f"🔄 Sesi {index+1} sedang mencoba join ke <code>{link}</code>...", parse_mode=ParseMode.HTML)
    
    session_client = Altruix.clients[index]
    success = False
    error_msg = None
    
    try:
        if "/+" in link or "joinchat/" in link:
            # Private link
            hash = link.split("/")[-1].replace("+", "")
            await session_client.join_chat(hash)
        else:
            # Public link / username
            await session_client.join_chat(link)
        
        success = True
        await cb.message.edit(
            text=f"✅ <b>Berhasil Join!</b>\n\nSesi {index+1} telah bergabung ke <code>{link}</code>.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}")]
            ]),
            parse_mode=ParseMode.HTML
        )
    except UserAlreadyParticipant:
        success = True # Already in
        await cb.message.edit(
            text=f"ℹ️ <b>Sudah Bergabung</b>\n\nSesi {index+1} sudah menjadi anggota di <code>{link}</code>.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}")]
            ]),
            parse_mode=ParseMode.HTML
        )
    except (InviteHashInvalid, InviteHashExpired):
        error_msg = "Link kadaluarsa atau tidak valid"
        await cb.message.edit(f"❌ <b>Gagal!</b>\n\nLink tidak valid atau kadaluarsa.", parse_mode=ParseMode.HTML)
    except FloodWait as e:
        error_msg = f"FloodWait {e.value}s"
        await cb.message.edit(f"⏳ <b>FloodWait!</b>\n\nHarus menunggu {e.value} detik.", parse_mode=ParseMode.HTML)
    except Exception as e:
        error_msg = str(e)
        await cb.message.edit(f"❌ <b>Error:</b>\n\n<code>{html.escape(str(e))}</code>", parse_mode=ParseMode.HTML)
    
    # Kirim notifikasi log
    await send_log_notification(
        c, 'join_chat', index, cb.from_user, 
        success, error_msg, {'Link': link}
    )
    
    # Cleanup state
    del user_bulk_join_state[user_id]


# ✅ HANDLER BARU: PM Logger Filters Menu
@Altruix.bot.on_callback_query(filters.regex(r"^pml_filters_menu_(\d+)_(\d+)$"))
@log_errors
async def pml_filters_menu_handler(c: Client, cb: CallbackQuery, index: int = None, page: int = None):
    if index is None:
        index = int(cb.matches[0].group(1))
    if page is None:
        page = int(cb.matches[0].group(2))
    
    # Load filter settings
    filters_file = "pml_filters.json"
    default_filters = {
        "text": True,
        "photo": True,
        "video": True,
        "voice": True,
        "audio": True,
        "sticker": False,
        "document": True,
        "others": True
    }
    
    current_filters = default_filters.copy()
    if os.path.exists(filters_file):
        try:
            with open(filters_file, "r") as f:
                saved_filters = json.load(f)
                current_filters.update(saved_filters)
        except: pass
        
    def get_status(key):
        return "✅" if current_filters.get(key, False) else "❌"
        
    text = (
        "<b>⚙️ Logger Message Filters</b>\n\n"
        "Pilih tipe pesan yang ingin dicatat (Logged) ke Log Group.\n"
        "Klik tombol untuk mengubah status (ON/OFF).\n\n"
        "<i>Setting ini berlaku untuk semua akun.</i>"
    )
    
    buttons = [
        [
            InlineKeyboardButton(f"{get_status('text')} Text", f"pml_filter_toggle_text_{index}_{page}"),
            InlineKeyboardButton(f"{get_status('photo')} Photo", f"pml_filter_toggle_photo_{index}_{page}")
        ],
        [
            InlineKeyboardButton(f"{get_status('video')} Video", f"pml_filter_toggle_video_{index}_{page}"),
            InlineKeyboardButton(f"{get_status('voice')} Voice", f"pml_filter_toggle_voice_{index}_{page}")
        ],
        [
            InlineKeyboardButton(f"{get_status('audio')} Audio", f"pml_filter_toggle_audio_{index}_{page}"),
            InlineKeyboardButton(f"{get_status('sticker')} Sticker", f"pml_filter_toggle_sticker_{index}_{page}")
        ],
        [
            InlineKeyboardButton(f"{get_status('document')} Docs", f"pml_filter_toggle_document_{index}_{page}"),
            InlineKeyboardButton(f"{get_status('others')} Others", f"pml_filter_toggle_others_{index}_{page}")
        ],
        [InlineKeyboardButton("🔙 Back to Logger Controls", f"pml_menu_{index}_{page}")]
    ]
    
    await cb.message.edit(text=text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)


# ✅ HANDLER BARU: Toggle Filter Item
@Altruix.bot.on_callback_query(filters.regex(r"^pml_filter_toggle_([a-z]+)_(\d+)_(\d+)$"))
@log_errors
async def pml_filter_toggle_handler(c: Client, cb: CallbackQuery):
    filter_type = cb.matches[0].group(1)
    index = int(cb.matches[0].group(2))
    page = int(cb.matches[0].group(3))
    
    filters_file = "pml_filters.json"
    default_filters = {
        "text": True, "photo": True, "video": True, "voice": True,
        "audio": True, "sticker": False, "document": True, "others": True
    }
    
    current_filters = default_filters.copy()
    if os.path.exists(filters_file):
        try:
            with open(filters_file, "r") as f:
                saved_filters = json.load(f)
                current_filters.update(saved_filters)
        except: pass
        
    # Toggle
    new_state = not current_filters.get(filter_type, False)
    current_filters[filter_type] = new_state
    
    try:
        with open(filters_file, "w") as f:
            json.dump(current_filters, f, indent=2)
    except Exception as e:
        await cb.answer(f"❌ Save failed: {e}", show_alert=True)
        return
        
    # Refresh menu
    await pml_filters_menu_handler(c, cb, index=index, page=page)
    
    # Kirim notifikasi log
    await send_log_notification(
        c, 'pml_toggle', index, cb.from_user,
        True, None, {'Target': filter_type, 'Status': new_state}
    )


# ✅ HANDLER BARU: PM Logger Menu
@Altruix.bot.on_callback_query(filters.regex(r"^pml_menu_(\d+)_(\d+)$"))
@log_errors
async def pml_menu_handler(c: Client, cb: CallbackQuery, index: int = None, page: int = None):
    try:
        await cb.answer()
    except: pass
    
    if index is None:
        index = int(cb.matches[0].group(1))
    if page is None:
        page = int(cb.matches[0].group(2))
    
    # Load settings (dari file JSON plugins)
    try:
        if os.path.exists("pm_logger_user_settings.json"):
            with open("pm_logger_user_settings.json", "r") as f:
                pmlu_data = json.load(f)
        else:
            pmlu_data = {"settings": {}, "reply_from_all_accessible": True}
            
        if os.path.exists("pm_logger_bot_settings.json"):
            with open("pm_logger_bot_settings.json", "r") as f:
                pmlb_data = json.load(f)
        else:
            pmlb_data = {"settings": {}, "reply_from_all_accessible": True}
    except Exception as e:
        logger.error(f"Error loading PML settings: {e}")
        pmlu_data = {"settings": {}, "reply_from_all_accessible": True}
        pmlb_data = {"settings": {}, "reply_from_all_accessible": True}

    # Cek status untuk session ini (index -> userbot id)
    session_client = Altruix.clients[index]
    userbot_id = str(session_client.me.id) if session_client.me else "Unknown"
    
    pmlu_enabled = pmlu_data["settings"].get(userbot_id, False)
    pmlb_enabled = pmlb_data["settings"].get("enabled", False)
    replyall_accessible = pmlu_data.get("reply_from_all_accessible", True)
    
    text = (
        "<b>📟 PM Logger Controls</b>\n\n"
        f"• <b>Userbot Logger:</b> {'✅ ON' if pmlu_enabled else '❌ OFF'}\n"
        f"• <b>Bot Logger:</b> {'✅ ON' if pmlb_enabled else '❌ OFF'}\n"
        f"• <b>Reply All Accessible:</b> {'✅ YES' if replyall_accessible else '❌ NO'}\n\n"
        "Gunakan tombol di bawah untuk toggle settings."
    )
    
    buttons = [
        [
            InlineKeyboardButton(f"Userbot Logger: {'OFF' if pmlu_enabled else 'ON'}", f"pml_toggle_user_{index}_{page}"),
            InlineKeyboardButton(f"Bot Logger: {'OFF' if pmlb_enabled else 'ON'}", f"pml_toggle_bot_{index}_{page}"),
        ],
        [
            InlineKeyboardButton(f"Reply All: {'DISABLE' if replyall_accessible else 'ENABLE'}", f"pml_toggle_replyall_{index}_{page}"),
        ],
        [
            InlineKeyboardButton("⚙️ Message Type Filters", f"pml_filters_menu_{index}_{page}")
        ],
        [InlineKeyboardButton("🔙 Back to Session Info", f"session_info_{index}_{page}")]
    ]
    
    await cb.message.edit(text=text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)


# ✅ HANDLER BARU: Toggle PM Logger Settings
@Altruix.bot.on_callback_query(filters.regex(r"^pml_toggle_(user|bot|replyall)_(\d+)_(\d+)$"))
@log_errors
async def pml_toggle_handler(c: Client, cb: CallbackQuery):
    target = cb.matches[0].group(1)
    index = int(cb.matches[0].group(2))
    page = int(cb.matches[0].group(3))
    
    file_map = {
        "user": "pm_logger_user_settings.json",
        "bot": "pm_logger_bot_settings.json",
        "replyall": "pm_logger_user_settings.json" # ReplyAll is stored in PMLU settings
    }
    
    filename = file_map[target]
    
    try:
        if os.path.exists(filename):
            with open(filename, "r") as f:
                data = json.load(f)
        else:
            data = {"settings": {}, "reply_from_all_accessible": True}
            
        success = False
        if target == "user":
            userbot_id = str(Altruix.clients[index].me.id)
            current = data["settings"].get(userbot_id, False)
            data["settings"][userbot_id] = not current
            success = True
        elif target == "bot":
            current = data["settings"].get("enabled", False)
            data["settings"]["enabled"] = not current
            success = True
        elif target == "replyall":
            current = data.get("reply_from_all_accessible", True)
            data["reply_from_all_accessible"] = not current
            success = True
            
        if success:
            with open(filename, "w") as f:
                json.dump(data, f, indent=2)
            await cb.answer("Settings updated!")
            await pml_menu_handler(c, cb, index=index, page=page)
            
            # Notifikasi log
            await send_log_notification(
                c, f'pml_toggle_{target}', index, cb.from_user, 
                True, None, {'New State': not current}
            )
        else:
            await cb.answer("Gagal mengupdate settings", show_alert=True)
            
    except Exception as e:
        await cb.answer(f"Error: {e}", show_alert=True)
        logger.error(f"Error toggling PML settings: {e}")


# ✅ HANDLER UNTUK ADD SESSION (PLACEHOLDER)
@Altruix.bot.on_callback_query(filters.regex(r"^add_session$"))
@log_errors
async def add_session_handler(c: Client, cb: CallbackQuery):
    """Handler untuk tombol Add a Session"""
    # Triggel handler dari get_session.py
    await add_session_cb_handler(c, cb)


# ✅ HANDLER BARU: Mention Control Menu
@Altruix.bot.on_callback_query(filters.regex(r"^mnt_menu_(\d+)_(\d+)$"))
@log_errors
async def mnt_menu_handler(c: Client, cb: CallbackQuery, index: int = None, page: int = None):
    """Mention Control Menu with toggles"""
    try:
        await cb.answer()
    except: pass
    
    if index is None:
        index = int(cb.matches[0].group(1))
    if page is None:
        page = int(cb.matches[0].group(2))
    
    # Check current states (mock logic - ideally stored in a shared settings file)
    from Main.plugins.userbot.mentions import MENTION_LOG_CACHE # Assuming it exists or use common settings
    # We'll use a local json check as backup
    settings_file = "mentions_settings.json"
    if os.path.exists(settings_file):
        with open(settings_file, "r") as f:
            m_settings = json.load(f)
    else:
        m_settings = {"reply_from_all": False, "mention": True, "auto_log": True}

    rfa_status = "✅ ON" if m_settings.get("reply_from_all") else "❌ OFF"
    mnt_status = "✅ ON" if m_settings.get("mention") else "❌ OFF"
    alog_status = "✅ ON" if m_settings.get("auto_log") else "❌ OFF"

    buttons = [
        [
            InlineKeyboardButton(f"{gt('reply_from_all')}: {rfa_status}", f"mnt_toggle_rfa_{index}_{page}"),
        ],
        [
            InlineKeyboardButton(f"{gt('pm_logger')}: {mnt_status}", f"mnt_toggle_mnt_{index}_{page}"),
        ],
        [
            InlineKeyboardButton(f"{gt('mention_auto_log')}: {alog_status}", f"mnt_toggle_alog_{index}_{page}"),
        ],
        [
            InlineKeyboardButton(gt("view_mentions"), f"view_mentions_menu_{index}_{page}"),
        ],
        [
            InlineKeyboardButton(gt("back"), f"session_info_{index}_{page}"),
        ]
    ]

    await cb.message.edit(
        f"<b>{gt('mention_control')}</b>\n\n"
        f"• <b>{gt('status')}:</b>\n"
        f"  ├ {gt('reply_from_all')}: {rfa_status}\n"
        f"  ├ {gt('pm_logger')}: {mnt_status}\n"
        f"  └ {gt('mention_auto_log')}: {alog_status}\n\n"
        f"<i>Configure mention behavior for all sessions.</i>",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )


# ✅ HANDLER BARU: Download Story session-targeted
@Altruix.bot.on_callback_query(filters.regex(r"^dlstory_session_input_(\d+)_(\d+)$"))
@log_errors
async def dlstory_session_input_handler(c: Client, cb: CallbackQuery):
    """Menerima input link story untuk didownload sesi tertentu"""
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    
    if index >= len(Altruix.clients):
        await cb.answer("❌ Session tidak ditemukan.", show_alert=True)
        return

    session_client = Altruix.clients[index]
    session_info = getattr(session_client, 'myself', None) or await session_client.get_me()
    
    await cb.message.edit(
        f"📥 <b>{gt('download_story')}</b>\n\n"
        f"Akun pengeksekusi: <b>{html.escape(session_info.first_name)}</b>\n\n"
        f"Silakan kirim <b>Link Story Aktif</b> (misal: <code>https://t.me/username/s/1</code>).\n"
        f"Hasil akan dikirim ke <b>Altruix Log Group</b>.\n\n"
        f"Ketik <code>cancel</code> untuk membatalkan.",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(gt("cancel"), f"session_info_{index}_{page}")]])
    )
    
    try:
        user_id = cb.from_user.id
        msg = await c.listen(filters.chat(user_id) & filters.text, timeout=120)
        
        if msg.text.lower() == 'cancel':
            await msg.delete()
            await cb.message.edit("❌ Dibatalkan.")
            await asyncio.sleep(2)
            await sessions_info_cb_handler(c, cb, index=index, callback_page=page)
            return
            
        link = msg.text.strip()
        await msg.delete()
        
        await cb.message.edit("🔄 <b>Sedang memproses...</b>")
        
        # Parse link
        if "t.me/" not in link or "/s/" not in link:
            await cb.message.edit("❌ <b>Format link tidak valid!</b>")
            await asyncio.sleep(3)
            await sessions_info_cb_handler(c, cb, index=index, callback_page=page)
            return

        parts = link.split("/")
        story_id = int(parts[-1])
        target = parts[-3] if "t.me/c/" not in link else f"-100{parts[-3]}"
        
        log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))
        
        try:
            # ✅ TRY COPY STORY FIRST
            is_premium = session_client.me.is_premium if session_client.me else False
            
            try:
                # Prioritas 1: Copy jika Premium atau Non-Restricted
                await session_client.copy_story(log_chat_id, target, story_id)
                await cb.message.edit(f"✅ <b>Berhasil!</b> Story telah disalin ke Log Group.")
            except Exception as e:
                err_str = str(e)
                # Check Bypass condition
                bypass = "PREMIUM_ACCOUNT_REQUIRED" in err_str or "STORY_NOT_MODIFIED" in err_str or "bad request" in err_str.lower()
                
                if not bypass and isinstance(e, FloodWait):
                     raise e
                
                await cb.message.edit(f"🔄 <b>Copy gagal ({err_str[:20]}...), mencoba Bypass (Download & Re-upload)...</b>")
                
                # ✅ BYPASS: Download and Re-upload
                story = await session_client.get_stories(target, story_id)
                if not story:
                    await cb.message.edit("❌ <b>Story tidak ditemukan atau sudah kadaluarsa.</b>")
                    return
                
                file_path = await session_client.download_media(story)
                if file_path:
                    try:
                        # Clean Caption Logic
                        from pyrogram import enums
                        caption = story.caption or ""
                        entities = story.caption_entities
                        
                        final_entities = []
                        if is_premium:
                            final_entities = entities
                        elif entities:
                            for ent in entities:
                                if ent.type != enums.MessageEntityType.CUSTOM_EMOJI:
                                    final_entities.append(ent)
                                    
                        final_caption = caption
                        if not final_caption:
                             final_caption = f"📥 <b>Story from</b> @{target}" + (f" ({target})" if str(target).lstrip('-').isdigit() else "")
                             final_entities = None

                        if story.video:
                            await session_client.send_video(log_chat_id, file_path, caption=final_caption, caption_entities=final_entities)
                        else:
                            await session_client.send_photo(log_chat_id, file_path, caption=final_caption, caption_entities=final_entities)
                        
                        await cb.message.edit("✅ <b>Bypass Berhasil!</b> Story telah diupload ke Log Group.")
                    finally:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                else:
                    await cb.message.edit("❌ <b>Gagal mendownload media story untuk bypass.</b>")
            
            # Notifikasi Log
            await send_log_notification(
                c, 'dlstory_session', index, cb.from_user,
                True, None, {'Target': target, 'StoryID': story_id, 'Method': 'Copy/Bypass'}
            )
            
        except Exception as e:
            await cb.message.edit(f"❌ <b>Gagal:</b> {str(e)}")
            await send_log_notification(
                c, 'dlstory_session', index, cb.from_user,
                False, str(e), {'Target': target, 'StoryID': story_id, 'Aksi': 'Download story gagal'}
            )
            
        await asyncio.sleep(3)
        await sessions_info_cb_handler(c, cb, index=index, callback_page=page)
        
    except asyncio.TimeoutError:
        await cb.message.edit("⏳ Waktu habis. Silakan coba lagi.")
    except Exception as e:
        await cb.message.edit(f"❌ Error: {str(e)}")


# ✅ HANDLER BARU: Toggle Mention Settings (RFA, MNT, ALOG)
@Altruix.bot.on_callback_query(filters.regex(r"^mnt_toggle_(rfa|mnt|alog)_(\d+)_(\d+)$"))
@log_errors
async def mnt_toggle_handler(c: Client, cb: CallbackQuery):
    """Toggle mention settings (RFA, MNT, ALOG)"""
    action = cb.matches[0].group(1)
    index = int(cb.matches[0].group(2))
    page = int(cb.matches[0].group(3))
    
    settings_file = "mentions_settings.json"
    if os.path.exists(settings_file):
        try:
            with open(settings_file, "r") as f:
                m_settings = json.load(f)
        except:
             m_settings = {"reply_from_all": False, "mention": True, "auto_log": True}
    else:
        m_settings = {"reply_from_all": False, "mention": True, "auto_log": True}

    # Map action to setting key
    key_map = {
        "rfa": "reply_from_all",
        "mnt": "mention",
        "alog": "auto_log"
    }
    
    key = key_map.get(action)
    if key:
        m_settings[key] = not m_settings.get(key, False)
        with open(settings_file, "w") as f:
            json.dump(m_settings, f, indent=4)
        
        readable_name = key.replace('_', ' ').title()
        status_text = "ON" if m_settings[key] else "OFF"
        await cb.answer(f"✅ {readable_name} turned {status_text}", show_alert=False)
        await mnt_menu_handler(c, cb, index=index, page=page)
    else:
        await cb.answer("❌ Invalid action", show_alert=True)


# ✅ HANDLER BARU: Generic Confirmation Handler
@Altruix.bot.on_callback_query(filters.regex(r"^gen_conf_(.+)$"))
@log_errors
async def gen_confirm_handler(c: Client, cb: CallbackQuery):
    await cb.answer()
    # Format: gen_conf_{real_callback_data}
    real_data = cb.matches[0].group(1)
    
    # Extract index and page if available for the 'No' button
    # Most data ends with _{index} or _{index}_{page}
    parts = real_data.split("_")
    index = "0"
    page = "1"
    if len(parts) >= 2:
        index = parts[-2] if len(parts) >= 2 else "0"
        page = parts[-1] if len(parts) >= 2 else "1"
        # If the last part is not a page (some data only has index), adjust
        if not index.isdigit() and parts[-1].isdigit():
             index = parts[-1]
             page = "1"
    
    confirm_buttons = [
        [
            InlineKeyboardButton(gt("yes"), real_data),
            InlineKeyboardButton(gt("no"), f"session_info_{index}_{page}")
        ]
    ]
    
    await cb.message.edit(
        text=f"<b>❓ {gt('confirm_action')}</b>\n\n{gt('confirm_msg')}\n\nAksi: <code>{real_data.replace('_', ' ').title()}</code>",
        reply_markup=InlineKeyboardMarkup(confirm_buttons),
        parse_mode=ParseMode.HTML
    )


# ✅ HANDLER BARU: Download User Photo Start
@Altruix.bot.on_callback_query(filters.regex(r"^dl_uphoto_start_(\d+)_(\d+)$"))
@log_errors
async def dl_uphoto_start_handler(c: Client, cb: CallbackQuery):
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    user_id = cb.from_user.id
    
    user_dlphoto_state[user_id] = {
        'session_index': index,
        'page': page,
        'step': 'waiting_target'
    }
    
    await cb.message.edit(
        text="<b>🖼️ Download Photo Profil</b>\n\n"
             "Silakan kirim <b>Username</b> atau <b>Chat ID</b> user yang ingin didownload fotonya.\n\n"
             "Ketik /cancel untuk membatalkan.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(gt("cancel"), f"session_info_{index}_{page}")]
        ]),
        parse_mode=ParseMode.HTML
    )

# ✅ HANDLER BARU: Purge Amount Handler
@Altruix.bot.on_callback_query(filters.regex(r"^purge_amt_(\d+)_(.+)$"))
@log_errors
async def purge_amt_handler(c: Client, cb: CallbackQuery):
    await cb.answer()
    user_id = int(cb.matches[0].group(1))
    amt_choice = cb.matches[0].group(2)
    
    if user_id not in user_purge_state:
        await cb.answer("❌ State tidak ditemukan. Silakan mulai ulang.", show_alert=True)
        return
        
    state = user_purge_state[user_id]
    
    if amt_choice == "custom":
        state['step'] = 'waiting_custom_amount'
        await cb.message.edit(
            f"<b>🧹 Purge My Message</b>\n\n"
            f"Chat: <code>{html.escape(state['chat_id'])}</code>\n\n"
            f"Silakan kirim <b>angka</b> jumlah pesan yang ingin dihapus.\n\n"
            f"Ketik /cancel untuk membatalkan.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(gt("cancel"), f"session_info_{state['session_index']}_{state['page']}")]
            ])
        )
        return
        
    state['amount'] = int(amt_choice)
    state['step'] = 'selecting_delay'
    
    # Tampilkan pilihan delay
    buttons = [
        [
            InlineKeyboardButton("0.5s", callback_data=f"purge_del_{user_id}_0.5"),
            InlineKeyboardButton("1s", callback_data=f"purge_del_{user_id}_1"),
        ],
        [
            InlineKeyboardButton("3s", callback_data=f"purge_del_{user_id}_3"),
            InlineKeyboardButton("5s", callback_data=f"purge_del_{user_id}_5"),
        ],
        [
            InlineKeyboardButton("🔙 Cancel", callback_data=f"session_info_{state['session_index']}_{state['page']}"),
        ]
    ]
    
    await cb.message.edit(
        f"<b>🧹 Purge My Message</b>\n\n"
        f"Chat: <code>{html.escape(state['chat_id'])}</code>\n"
        f"Jumlah: <code>{state['amount']}</code>\n\n"
        f"Pilih jeda (delay) antar setiap penghapusan pesan:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ✅ HANDLER BARU: Purge Delay Handler
@Altruix.bot.on_callback_query(filters.regex(r"^purge_del_(\d+)_(.+)$"))
@log_errors
async def purge_del_handler(c: Client, cb: CallbackQuery):
    await cb.answer()
    user_id = int(cb.matches[0].group(1))
    delay = float(cb.matches[0].group(2))
    
    if user_id not in user_purge_state:
        await cb.answer("❌ State tidak ditemukan.", show_alert=True)
        return
        
    state = user_purge_state[user_id]
    state['delay'] = delay
    state['step'] = 'selecting_mode'
    
    # Tampilkan pilihan mode (Reverse)
    buttons = [
        [
            InlineKeyboardButton("🆕 Terbaru (Latest)", callback_data=f"purge_mode_{user_id}_latest"),
            InlineKeyboardButton("⌛ Terlama (Oldest)", callback_data=f"purge_mode_{user_id}_oldest"),
        ],
        [
            InlineKeyboardButton("🔙 Cancel", callback_data=f"session_info_{state['session_index']}_{state['page']}"),
        ]
    ]
    
    await cb.message.edit(
        f"<b>🧹 Purge My Message</b>\n\n"
        f"Chat: <code>{html.escape(state['chat_id'])}</code>\n"
        f"Jumlah: <code>{state['amount']}</code>\n"
        f"Jeda: <code>{delay}s</code>\n\n"
        f"Pilih mode urutan penghapusan:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ✅ HANDLER BARU: Purge Mode Handler
@Altruix.bot.on_callback_query(filters.regex(r"^purge_mode_(\d+)_(.+)$"))
@log_errors
async def purge_mode_handler(c: Client, cb: CallbackQuery):
    await cb.answer()
    user_id = int(cb.matches[0].group(1))
    mode = cb.matches[0].group(2)
    
    if user_id not in user_purge_state:
        await cb.answer("❌ State tidak ditemukan.", show_alert=True)
        return
        
    state = user_purge_state[user_id]
    state['mode'] = mode
    state['step'] = 'confirming'
    
    # Final confirmation
    buttons = [
        [
            InlineKeyboardButton("✅ Ya, Mulai Purge", callback_data=f"purge_exec_{user_id}"),
            InlineKeyboardButton("❌ Tidak, Batalkan", f"session_info_{state['session_index']}_{state['page']}")
        ]
    ]
    
    await cb.message.edit(
        f"<b>🧹 Konfirmasi Purge</b>\n\n"
        f"• <b>Sesi:</b> <code>{state['session_index'] + 1}</code>\n"
        f"• <b>Chat:</b> <code>{html.escape(state['chat_id'])}</code>\n"
        f"• <b>Jumlah:</b> <code>{state['amount']}</code>\n"
        f"• <b>Jeda:</b> <code>{state['delay']}s</code>\n"
        f"• <b>Mode:</b> <code>{mode.upper()}</code>\n\n"
        f"⚠️ Penghapusan pesan tidak dapat dibatalkan. Lanjutkan?",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ✅ HANDLER BARU: Purge Execution
@Altruix.bot.on_callback_query(filters.regex(r"purge_exec_(\d+)"))
@log_errors
async def purge_exec_handler(c: Client, cb: CallbackQuery):
    user_id = int(cb.matches[0].group(1))
    if user_id not in user_purge_state:
        await cb.answer("❌ State tidak ditemukan.", show_alert=True)
        return
        
    state = user_purge_state.pop(user_id)
    session_index = state['session_index']
    chat_id = state['chat_id']
    amount = state['amount']
    delay = state['delay']
    mode = state['mode']
    
    if session_index >= len(Altruix.clients):
        await cb.answer("❌ Session tidak ditemukan.", show_alert=True)
        return
        
    session_client = Altruix.clients[session_index]
    
    await cb.message.edit(f"⏳ <b>Memulai Purge pada {html.escape(chat_id)}...</b>", parse_mode=ParseMode.HTML)
    
    try:
        # Resolve chat properly (handle numerical strings)
        chat_to_resolve = chat_id
        if isinstance(chat_id, str) and chat_id.lstrip('-').isdigit():
            chat_to_resolve = int(chat_id)
            
        target = await session_client.get_chat(chat_to_resolve)
        me = await session_client.get_me()
        
        count = 0
        error_count = 0
        
        # Determine reverse mode
        # get_chat_history limit=amount
        # If mode oldest, we might need a different approach or just reverse the list
        
        msgs_to_delete = []
        async for msg in session_client.get_chat_history(target.id):
            if msg.from_user and msg.from_user.id == me.id:
                msgs_to_delete.append(msg.id)
            if len(msgs_to_delete) >= amount:
                break
                
        if mode == "oldest":
            msgs_to_delete.reverse()
            
        if not msgs_to_delete:
            await cb.message.edit("❌ <b>Tidak ada pesan Anda yang ditemukan untuk dihapus.</b>")
            return

        await cb.message.edit(f"🧹 <b>Menghapus {len(msgs_to_delete)} pesan...</b>")
        
        for mid in msgs_to_delete:
            try:
                await session_client.delete_messages(target.id, mid)
                count += 1
                await asyncio.sleep(delay)
            except FloodWait as e:
                await asyncio.sleep(e.value)
                await session_client.delete_messages(target.id, mid)
                count += 1
            except Exception:
                error_count += 1
                
        final_text = f"✅ <b>Purge Selesai!</b>\n\n• Berhasil dihapus: <code>{count}</code>\n• Gagal: <code>{error_count}</code>"
        await cb.message.edit(final_text)
        
        # Log to Altruix Log Group
        await send_log_notification(
            c, 'purge_my_message', session_index, cb.from_user,
            True, None, {
                'Chat': f"{target.title or target.first_name} ({target.id})",
                'Jumlah': count,
                'Delay': delay,
                'Mode': mode
            }
        )
        
    except Exception as e:
        await cb.message.edit(f"❌ <b>Error saat Purge:</b> <code>{str(e)}</code>")
        await send_log_notification(
            c, 'purge_my_message', session_index, cb.from_user,
            False, str(e), {'Target': chat_id}
        )

# ✅ HANDLER BARU: Download Photo Execution
@Altruix.bot.on_callback_query(filters.regex(r"dl_uphoto_exec_(\d+)"))
@log_errors
async def dl_uphoto_exec_handler(c: Client, cb: CallbackQuery):
    user_id = int(cb.matches[0].group(1))
    if user_id not in user_dlphoto_state:
        await cb.answer("❌ State tidak ditemukan.", show_alert=True)
        return
        
    state = user_dlphoto_state.pop(user_id)
    session_index = state['session_index']
    target = state['target']
    
    if session_index >= len(Altruix.clients):
        await cb.answer("❌ Session tidak ditemukan.", show_alert=True)
        return
        
    session_client = Altruix.clients[session_index]
    await cb.message.edit(f"⏳ <b>Mendownload foto profil {html.escape(str(target))}...</b>")
    
    try:
        # FIX: Convert to int if target is a chat ID (digits)
        if str(target).lstrip('-').isdigit():
             target = int(target)

        user = await session_client.get_chat(target)
        photo = await session_client.download_media(user.photo.big_file_id) if user.photo else None
        
        if photo:
            log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))
            caption = (
                f"🖼️ <b>User Profile Photo</b>\n\n"
                f"• <b>User:</b> {user.first_name}\n"
                f"• <b>ID:</b> <code>{user.id}</code>\n"
                f"• <b>Source Session:</b> <code>{session_index + 1}</code>"
            )
            await c.send_photo(log_chat_id, photo, caption=caption)
            if os.path.exists(photo):
                os.remove(photo)
            
            page = state.get('page', 1)
            await cb.message.edit(
                f"✅ <b>Foto profil {html.escape(user.first_name)} telah dikirim ke Log Group!</b>",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(gt("back"), f"session_info_{session_index}_{page}")]
                ]),
                parse_mode=ParseMode.HTML
            )
            
            await send_log_notification(
                c, 'download_user_photo', session_index, cb.from_user,
                True, None, {'Target': f"{user.first_name} ({user.id})"}
            )
        else:
            await cb.message.edit("❌ <b>User tidak memiliki foto profil.</b>")
            
    except Exception as e:
        await cb.message.edit(f"❌ <b>Gagal mendownload foto:</b> <code>{str(e)}</code>")
        await send_log_notification(
            c, 'download_user_photo', session_index, cb.from_user,
            False, str(e), {'Target': target}
        )

# ✅ HANDLER BARU: Purge My Msg Start
@Altruix.bot.on_callback_query(filters.regex(r"purge_msg_start_(\d+)_(\d+)"))
@log_errors
async def purge_msg_start_handler(c: Client, cb: CallbackQuery):
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    user_id = cb.from_user.id
    
    user_purge_state[user_id] = {
        'session_index': index,
        'page': page,
        'step': 'waiting_chat'
    }
    
    await cb.message.edit(
        text="<b>🧹 Purge My Message</b>\n\n"
             "Fitur ini akan menghapus pesan yang dikirim oleh session ini pada chat tertentu.\n\n"
             "Silakan kirim <b>Username</b> atau <b>Chat ID</b> target chat.\n\n"
             "Ketik /cancel untuk membatalkan.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(gt("cancel"), f"session_info_{index}_{page}")]
        ]),
        parse_mode=ParseMode.HTML
    )


# ✅ HANDLER BARU: Reply PM Mention Confirmation
@Altruix.bot.on_callback_query(filters.regex(r"rpm_conf_(\d+)_(-?\d+)_(\d+)"))
@log_errors
async def rpm_conf_handler(c: Client, cb: CallbackQuery):
    await cb.answer()
    index = int(cb.matches[0].group(1))
    chat_id = int(cb.matches[0].group(2))
    msg_id = int(cb.matches[0].group(3))
    
    confirm_buttons = [
        [
            InlineKeyboardButton("✅ Yes, Reply Now", f"rpm_exec_{index}_{chat_id}_{msg_id}"),
            InlineKeyboardButton("❌ No, Cancel", f"session_info_{index}_1") # Fallback to session info
        ]
    ]
    
    await cb.message.edit(
        text="<b>❓ Konfirmasi Reply ke PM</b>\n\n"
             "Apakah Anda yakin ingin membalas mention ini melalui Personal Chat (PM) "
             "dengan menyertakan tag quote dari pesan asli?\n\n"
             "⚠️ User akan menerima pesan dari userbot Anda.",
        reply_markup=InlineKeyboardMarkup(confirm_buttons),
        parse_mode=ParseMode.HTML
    )


# ✅ HANDLER BARU: Reply PM Mention Execute
@Altruix.bot.on_callback_query(filters.regex(r"rpm_exec_(\d+)_(-?\d+)_(\d+)"))
@log_errors
async def rpm_exec_handler(c: Client, cb: CallbackQuery):
    index = int(cb.matches[0].group(1))
    chat_id = int(cb.matches[0].group(2))
    msg_id = int(cb.matches[0].group(3))
    
    if index >= len(Altruix.clients):
        await cb.answer("❌ Session tidak ditemukan.", show_alert=True)
        return
        
    session_client = Altruix.clients[index]
    
    try:
        # Ambil pesan asli
        msg = await session_client.get_messages(chat_id, msg_id)
        if not msg or not msg.from_user:
            await cb.answer("❌ Pesan atau pengirim tidak ditemukan.", show_alert=True)
            return
            
        target_user = msg.from_user
        chat_title = msg.chat.title or "Group"
        original_text = msg.text or msg.caption or "[Media]"
        
        # Format pesan balasan (Tag Quote)
        quote_reply = (
            f"Halo {target_user.mention},\n\n"
            f"Anda mention saya di <b>{html.escape(chat_title)}</b>:\n"
            f"<blockquote>{html.escape(original_text[:200])}</blockquote>\n\n"
            f"Ada yang bisa saya bantu?"
        )
        
        # Kirim PM
        await session_client.send_message(target_user.id, quote_reply, parse_mode=ParseMode.HTML)
        
        await cb.message.edit(f"✅ Berhasil mengirim reply PM ke {html.escape(target_user.first_name)}.")
        
        # Kirim log
        await send_log_notification(
            c, 'reply_mention_to_pm', index, cb.from_user,
            True, None, {
                'Target': f"{target_user.first_name} ({target_user.id})",
                'Group': chat_title,
                'Status': 'Berhasil'
            }
        )
        
    except Exception as e:
        await cb.message.edit(f"❌ Gagal mengirim reply PM: {str(e)}")
        await send_log_notification(
            c, 'reply_mention_to_pm', index, cb.from_user,
            False, str(e), {'Chat_ID': chat_id, 'Msg_ID': msg_id}
        )

# ✅ HANDLER BARU: System Control Callback Handler (Restart/Shutdown)
@Altruix.bot.on_callback_query(filters.regex(r"^sys_ctrl_(restart|shutdown)$"))
@log_errors
async def sys_ctrl_cb_handler(c: Client, cb: CallbackQuery):
    action = cb.matches[0].group(1)
    user_id = cb.from_user.id
    
    if user_id not in Altruix.auth_users and user_id != Altruix.config.OWNER_ID:
        await cb.answer("⛔ Access Denied!", show_alert=True)
        return

    readable_action = "Restart" if action == "restart" else "Shutdown"
    
    await cb.message.edit(
        f"⚠️ <b>Force {readable_action}</b>\n\n"
        f"Anda yakin ingin melakukan paksa {readable_action.lower()} pada bot?\n"
        f"Aksi ini akan menghentikan proses bot saat ini.\n\n"
        f"<i>Pilih 'Ya' untuk lanjut ke konfirmasi keamanan.</i>",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"✅ Ya, {readable_action}", callback_data=f"sys_ctrl_confirm_{action}_1"),
                InlineKeyboardButton("❌ Batal", callback_data="close_settings")
            ]
        ]),
        parse_mode=ParseMode.HTML
    )

@Altruix.bot.on_callback_query(filters.regex(r"^sys_ctrl_confirm_(restart|shutdown)_1$"))
@log_errors
async def sys_ctrl_1_handler(c: Client, cb: CallbackQuery):
    action = cb.matches[0].group(1)
    user_id = cb.from_user.id
    readable_action = "Restart" if action == "restart" else "Shutdown"
    required_code = "11" if action == "shutdown" else "ok"
    
    # Save state
    user_sys_ctrl_state[user_id] = {
        "action": action,
        "step": "waiting_code"
    }
    
    await cb.message.edit(
        f"🔒 <b>Keamanan Tingkat Lanjut</b>\n\n"
        f"Untuk konfirmasi akhir <b>{readable_action}</b>, silakan ketik password berikut:\n\n"
        f"👉 <code>{required_code}</code>\n\n"
        f"Ketik /cancel untuk membatalkan.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Batal", callback_data="close_settings")]
        ]),
        parse_mode=ParseMode.HTML
    )




# ✅ HANDLER BARU: Eval Session Input
@Altruix.bot.on_callback_query(filters.regex(r"^eval_session_(\d+)_(\d+)$"))
@log_errors
async def eval_session_start_handler(c: Client, cb: CallbackQuery):
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    user_id = cb.from_user.id
    
    user_eval_state[user_id] = {
        "session_index": index,
        "page": page,
        "step": "waiting_code"
    }
    
    await cb.message.edit(
        f"🐍 <b>Eval Python (Session {index + 1})</b>\n\n"
        f"Silakan kirim kode Python yang ingin dieksekusi.\n"
        f"Kode akan dijalankan di dalam context session tersebut.\n\n"
        f"⚠️ <b>Hati-hati!</b> Kode berbahaya dapat merusak sesi.\n\n"
        f"Ketik /cancel untuk membatalkan.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Cancel", callback_data=f"session_info_{index}_{page}")]
        ]),
        parse_mode=ParseMode.HTML
    )

@Altruix.bot.on_callback_query(filters.regex(r"^eval_exec_(\d+)$"))
@log_errors
async def eval_exec_confirm_handler(c: Client, cb: CallbackQuery):
    user_id = int(cb.matches[0].group(1))
    
    if user_id not in user_eval_state:
         await cb.answer("Session expired.", show_alert=True)
         return
         
    state = user_eval_state[user_id]
    code = state.get("code")
    index = state["session_index"]
    
    if not code:
        await cb.answer("No code found.", show_alert=True)
        return
        
    await cb.message.edit("⏳ <b>Executing...</b>")
    
    session_client = Altruix.clients[index]
    
    # Redirect output
    import io
    import sys
    import traceback
    
    old_stdout = sys.stdout
    redirected_output = io.StringIO()
    sys.stdout = redirected_output
    
    result = None
    status = "Success"
    
    try:
        # Create context
        # Handle async/await properly
        reply_msg = getattr(cb.message, 'reply_to_message', None)
        
        exec_locals = {
            "c": session_client,
            "client": session_client,
            "Altruix": Altruix,
            "print": print,
            "m": cb.message,
            "message": cb.message,
            "reply": reply_msg,
            "chat": cb.message.chat,
            "user": cb.message.from_user
        }
        
        # Async exec wrapper if needed, but standard exec is blocking.
        # Ideally we wrap in async function
        exec(
            f"async def __ex():\n" + "".join(f"    {l}\n" for l in code.split("\n")),
            exec_locals
        )
        result = await exec_locals["__ex"]()
        
    except Exception as e:
        traceback.print_exc(file=redirected_output)
        status = "Error"
        result = str(e)
    finally:
        sys.stdout = old_stdout
        
    output = redirected_output.getvalue()
    
    final_output = f"<b>Output:</b>\n<pre>{html.escape(str(output) or 'No output')}</pre>\n"
    if result is not None:
        final_output += f"<b>Result:</b>\n<pre>{html.escape(str(result))}</pre>"
        
    if len(final_output) > 4000:
        final_output = final_output[:4000] + "... (truncated)"
        
    log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))
    try:
         await Altruix.bot.send_message(
             log_chat_id,
             f"🐍 <b>Eval Execution Log</b>\n"
             f"• User: {cb.from_user.mention}\n"
             f"• Status: {status}\n\n"
             f"<b>Code:</b>\n<pre>{html.escape(code)}</pre>\n\n"
             f"{final_output}",
             parse_mode=ParseMode.HTML
         )
    except: pass
    
    await cb.message.edit(
        f"🐍 <b>Eval Result</b>\n\n{final_output}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data=f"session_info_{index}_{state['page']}")]
        ]),
        parse_mode=ParseMode.HTML
    )
    
    del user_eval_state[user_id]


# ✅ HANDLER BARU: Exec Session Input
@Altruix.bot.on_callback_query(filters.regex(r"^exec_session_(\d+)_(\d+)$"))
@log_errors
async def exec_session_start_handler(c: Client, cb: CallbackQuery):
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    user_id = cb.from_user.id
    
    user_exec_state[user_id] = {
        "session_index": index,
        "page": page,
        "step": "waiting_command"
    }
    
    await cb.message.edit(
        f"🖥️ <b>Exec Terminal (Session {index + 1})</b>\n\n"
        f"Silakan kirim perintah terminal (shell) yang ingin dieksekusi.\n"
        f"Perintah akan dijalankan di server host bot ini.\n\n"
        f"⚠️ <b>WARNING:</b> Fitur ini sangat <b>BERBAHAYA</b>. Gunakan dengan bijak!\n\n"
        f"Ketik /cancel untuk membatalkan.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Cancel", callback_data=f"session_info_{index}_{page}")]
        ]),
        parse_mode=ParseMode.HTML
    )

@Altruix.bot.on_callback_query(filters.regex(r"^exec_term_(\d+)$"))
@log_errors
async def exec_term_handler(c: Client, cb: CallbackQuery):
    user_id = int(cb.matches[0].group(1))
    
    if user_id not in user_exec_state:
         await cb.answer("Session expired.", show_alert=True)
         return
         
    state = user_exec_state[user_id]
    command = state.get("command")
    index = state["session_index"]
    
    if not command:
        await cb.answer("No command found.", show_alert=True)
        return
        
    await cb.message.edit("⏳ <b>Executing...</b>")
    
    status = "Success"
    output = ""
    
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        
        output = (stdout.decode() if stdout else "") + (stderr.decode() if stderr else "")
        if not output:
             output = "No output."
             
    except Exception as e:
        status = "Error"
        output = str(e)
        
    final_output = f"<b>Output:</b>\n<pre>{html.escape(str(output))}</pre>"
        
    if len(final_output) > 4000:
        final_output = final_output[:4000] + "... (truncated)"
        
    log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))
    try:
         await Altruix.bot.send_message(
             log_chat_id,
             f"🖥️ <b>Exec Terminal Log</b>\n"
             f"• User: {cb.from_user.mention}\n"
             f"• Status: {status}\n\n"
             f"<b>Command:</b>\n<pre>{html.escape(command)}</pre>\n\n"
             f"{final_output}",
             parse_mode=ParseMode.HTML
         )
    except: pass
    
    await cb.message.edit(
        f"🖥️ <b>Exec Result</b>\n\n{final_output}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data=f"session_info_{index}_{state['page']}")]
        ]),
        parse_mode=ParseMode.HTML
    )
    
    del user_exec_state[user_id]


# Log sukses loading
logger.info(f"✅ Loaded → {__plugin_name__} v{PLUGIN_VERSION}")

# ============================================================================
# PRIVACY & SECURITY HANDLERS
# ============================================================================

@Altruix.bot.on_callback_query(filters.regex(r"^privacy_menu_(\d+)_(\d+)$"))
@log_errors
async def privacy_menu_handler(c: Client, cb: CallbackQuery):
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    
    buttons = [
        [
            InlineKeyboardButton("🚫 Block User", callback_data=f"block_user_input_{index}_{page}"),
            InlineKeyboardButton("✅ Unblock User", callback_data=f"unblock_user_input_{index}_{page}"),
        ],
        [
            InlineKeyboardButton("📞 Phone Privacy", callback_data=f"phone_privacy_menu_{index}_{page}"),
        ],
        [
            InlineKeyboardButton("👥 Group/Channel Privacy", callback_data=f"group_privacy_menu_{index}_{page}"),
        ],
        [
            InlineKeyboardButton("🔙 Back to Session Info", callback_data=f"session_info_{index}_{page}"),
        ]
    ]
    
    await cb.message.edit(
        text="<b>🔒 Privacy & Security Settings</b>\n\n"
             "Kelola privasi dan keamanan akun Anda dari sini.\n"
             "• <b>Block/Unblock:</b> Blokir atau buka blokir pengguna.\n"
             "• <b>Phone Privacy:</b> Siapa yang bisa melihat/mencari nomor Anda.\n"
             "• <b>Group Privacy:</b> Siapa yang bisa menambahkan Anda ke grup.",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )

@Altruix.bot.on_callback_query(filters.regex(r"^(block|unblock)_user_input_(\d+)_(\d+)$"))
@log_errors
async def block_unblock_input_handler(c: Client, cb: CallbackQuery):
    await cb.answer()
    action = cb.matches[0].group(1) # block / unblock
    index = int(cb.matches[0].group(2))
    page = int(cb.matches[0].group(3))
    user_id = cb.from_user.id
    
    user_privacy_state[user_id] = {
        'action': f"{action}_user",
        'session_index': index,
        'page': page,
        'step': 'waiting_target'
    }
    
    readable_action = "Blokir (Block)" if action == "block" else "Buka Blokir (Unblock)"
    
    await cb.message.edit(
        text=f"<b>🚫 {readable_action} User</b>\n\n"
             "Silakan kirim <b>Username</b> atau <b>User ID</b> target.\n\n"
             "Contoh: <code>@username</code> atau <code>123456789</code>\n\n"
             "Kirim <code>/cancel</code> untuk membatalkan.",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
             [InlineKeyboardButton("🔙 Cancel", callback_data=f"privacy_menu_{index}_{page}")]
        ])
    )

async def execute_block_unblock(c: Client, m: Message, state: dict):
    """Eksekusi block/unblock dari text handler"""
    user_id = m.from_user.id
    target_input = m.text.strip()
    session_index = state['session_index']
    action = state['action'] # block_user / unblock_user
    page = state['page']
    
    if session_index >= len(Altruix.clients):
        await m.reply("❌ Session tidak ditemukan.")
        return

    session_client = Altruix.clients[session_index]
    
    status_msg = await m.reply(f"🔄 Processing {action.replace('_', ' ')}...")
    
    try:
        # Resolve target
        if target_input.lstrip('-').isdigit():
             target = int(target_input)
        else:
             target = target_input
             
        target_user = await session_client.get_users(target)
        
        if action == "block_user":
            await session_client.block_user(target_user.id)
            log_text = f"🚫 <b>User Blocked</b>\nTarget: {target_user.mention} (`{target_user.id}`)"
            reply_text = f"✅ Berhasil memblokir <b>{html.escape(target_user.first_name)}</b>."
        else:
            await session_client.unblock_user(target_user.id)
            log_text = f"✅ <b>User Unblocked</b>\nTarget: {target_user.mention} (`{target_user.id}`)"
            reply_text = f"✅ Berhasil membuka blokir <b>{html.escape(target_user.first_name)}</b>."

        await status_msg.edit(reply_text, parse_mode=ParseMode.HTML)
        
        # Log Notification
        await send_log_notification(
            c, 'privacy_action', session_index, m.from_user,
            True, None, {'Action': action, 'Target': f"{target_user.first_name} ({target_user.id})"}
        )
        
        # Back to menu logic
        if user_id in user_privacy_state:
             del user_privacy_state[user_id]
             
    except Exception as e:
        err_msg = str(e)
        await status_msg.edit(f"❌ <b>Gagal:</b> {html.escape(err_msg)}")
        await send_log_notification(
            c, 'privacy_action', session_index, m.from_user,
            False, err_msg, {'Action': action, 'Target input': target_input}
        )

# PHONE PRIVACY MENUS
@Altruix.bot.on_callback_query(filters.regex(r"^phone_privacy_menu_(\d+)_(\d+)$"))
@log_errors
async def phone_privacy_menu_handler(c: Client, cb: CallbackQuery):
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    
    buttons = [
        [
            InlineKeyboardButton("👀 Who can SEE my number?", callback_data="ignore"),
        ],
        [
            InlineKeyboardButton("Everybody", callback_data=f"set_pp_see_{index}_{page}_all"),
            InlineKeyboardButton("Contacts", callback_data=f"set_pp_see_{index}_{page}_contacts"),
            InlineKeyboardButton("Nobody", callback_data=f"set_pp_see_{index}_{page}_nobody"),
        ],
        [
            InlineKeyboardButton("🔍 Who can FIND by number?", callback_data="ignore"),
        ],
        [
            InlineKeyboardButton("Everybody", callback_data=f"set_pp_find_{index}_{page}_all"),
            InlineKeyboardButton("Contacts", callback_data=f"set_pp_find_{index}_{page}_contacts"),
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data=f"privacy_menu_{index}_{page}"),
        ]
    ]
    
    await cb.message.edit(
        text="<b>📞 Phone Number Privacy</b>\n\n"
             "Atur siapa yang bisa melihat nomor telepon Anda dan siapa yang bisa menemukan Anda via nomor telepon.\n\n"
             "⚠️ <i>Perubahan akan langsung diterapkan ke Telegram.</i>",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )

@Altruix.bot.on_callback_query(filters.regex(r"^set_pp_(see|find)_(\d+)_(\d+)_(.+)$"))
@log_errors
async def set_phone_privacy_handler(c: Client, cb: CallbackQuery):
    type_ = cb.matches[0].group(1) # see / find
    index = int(cb.matches[0].group(2))
    page = int(cb.matches[0].group(3))
    value = cb.matches[0].group(4) # all / contacts / nobody
    
    if index >= len(Altruix.clients):
        await cb.answer("Session unavailable", show_alert=True)
        return
        
    session = Altruix.clients[index]
    
    try:
        from pyrogram import raw
        
        # Mapping Value
        rule = None
        if value == "all":
            rule = [raw.types.InputPrivacyValueAllowAll()]
        elif value == "contacts":
            rule = [raw.types.InputPrivacyValueAllowContacts()]
        elif value == "nobody":
             rule = [raw.types.InputPrivacyValueDisallowAll()]
        
        # Mapping Key
        key = None
        if type_ == "see":
            key = raw.types.InputPrivacyKeyPhoneNumber()
        elif type_ == "find":
            key = raw.types.InputPrivacyKeyAddedByPhone()
            # Find by phone doesn't support 'Nobody', mostly All or Contacts
            if value == "nobody":
                 await cb.answer("Option 'Nobody' not supported for 'Find by Number'", show_alert=True)
                 return

        await session.invoke(raw.functions.account.SetPrivacy(key=key, rules=rule))
        
        readable_type = "See Phone Number" if type_ == 'see' else "Find by Phone Number"
        await cb.answer(f"✅ Privacy Updated: {readable_type} -> {value.title()}", show_alert=True)
        
        # Log
        await send_log_notification(
            c, 'privacy_setting', index, cb.from_user,
            True, None, {'Setting': readable_type, 'Value': value.title()}
        )
        
    except Exception as e:
        await cb.answer(f"❌ Failed: {str(e)}", show_alert=True)
        await send_log_notification(
            c, 'privacy_setting', index, cb.from_user,
            False, str(e), {'Setting': f"Phone {type_}", 'Value': value}
        )

# GROUP PRIVACY MENUS
@Altruix.bot.on_callback_query(filters.regex(r"^group_privacy_menu_(\d+)_(\d+)$"))
@log_errors
async def group_privacy_menu_handler(c: Client, cb: CallbackQuery):
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    
    buttons = [
        [
            InlineKeyboardButton("Everyone", callback_data=f"set_gp_{index}_{page}_all"),
            InlineKeyboardButton("Contacts", callback_data=f"set_gp_{index}_{page}_contacts"),
            InlineKeyboardButton("Nobody", callback_data=f"set_gp_{index}_{page}_nobody"),
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data=f"privacy_menu_{index}_{page}"),
        ]
    ]
    
    await cb.message.edit(
        text="<b>👥 Group & Channel Privacy</b>\n\n"
             "<b>Who can add me to group chats?</b>\n"
             "Atur siapa yang bisa menambahkan Anda ke grup dan channel secara otomatis.",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )

@Altruix.bot.on_callback_query(filters.regex(r"^set_gp_(\d+)_(\d+)_(.+)$"))
@log_errors
async def set_group_privacy_handler(c: Client, cb: CallbackQuery):
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    value = cb.matches[0].group(3)
    
    if index >= len(Altruix.clients):
        await cb.answer("Session unavailable", show_alert=True)
        return
        
    session = Altruix.clients[index]
    
    try:
        from pyrogram import raw
        
        rule = None
        if value == "all":
            rule = [raw.types.InputPrivacyValueAllowAll()]
        elif value == "contacts":
            rule = [raw.types.InputPrivacyValueAllowContacts()]
        elif value == "nobody":
             rule = [raw.types.InputPrivacyValueDisallowAll()]
             
        key = raw.types.InputPrivacyKeyChatInvite()
        
        await session.invoke(raw.functions.account.SetPrivacy(key=key, rules=rule))
        
        await cb.answer(f"✅ Group Privacy Updated: {value.title()}", show_alert=True)
        
        # Log
        await send_log_notification(
            c, 'privacy_setting', index, cb.from_user,
            True, None, {'Setting': 'Who can add to group', 'Value': value.title()}
        )
        
    except Exception as e:
        await cb.answer(f"❌ Failed: {str(e)}", show_alert=True)
        await send_log_notification(
            c, 'privacy_setting', index, cb.from_user,
            False, str(e), {'Setting': 'Group Add', 'Value': value}
        )

# ============================================================================
# CHAT STATISTICS HANDLER
# ============================================================================

@Altruix.bot.on_callback_query(filters.regex(r"^chat_stats_scan_(\d+)_(\d+)$"))
@log_errors
async def chat_stats_scan_handler(c: Client, cb: CallbackQuery):
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    user_id = cb.from_user.id
    
    if index >= len(Altruix.clients):
        await cb.answer("Session unavailable", show_alert=True)
        return
        
    session = Altruix.clients[index]
    session_info = getattr(session, 'myself', None) or await session.get_me()
    
    # Caching Logic
    cache_file = "chat_stats_cache.json"
    cache_data = {}
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r") as f:
                cache_data = json.load(f)
        except: pass
    
    session_id_str = str(session_info.id)
    now = datetime.now().timestamp()
    
    # Check if cache exists and is fresh (e.g., 1 hour)
    if session_id_str in cache_data:
        entry = cache_data[session_id_str]
        if now - entry.get("timestamp", 0) < 3600: # 1 hour cache
            stats = entry.get("stats")
            await cb.answer("📊 Loading from cache...")
            await display_chat_stats(c, cb, session_info, stats, index, page, cached=True)
            return

    await cb.answer("🔍 Scanning chat statistics... This may take a moment.", show_alert=False)
    
    # Initialize Counters
    stats = {
        "created": {"group": 0, "supergroup": 0, "channel": 0},
        "admin": {"group": 0, "supergroup": 0, "channel": 0},
        "total": {"group": 0, "supergroup": 0, "channel": 0},
        "private_chat": 0,
        "bot": 0
    }
    
    scanning_msg = None
    try:
         scanning_msg = await cb.message.edit(f"🔍 <b>Scanning chats... (0 found)</b>")
    except: pass

    count = 0
    try:
        async for dialog in session.get_dialogs():
            chat = dialog.chat
            chat_type = chat.type
            
            # Simple Category Mapping
            cat_key = None
            if chat_type == ChatType.GROUP: cat_key = "group"
            elif chat_type == ChatType.SUPERGROUP: cat_key = "supergroup"
            elif chat_type == ChatType.CHANNEL: cat_key = "channel"
            elif chat_type == ChatType.BOT:
                 stats["bot"] += 1
                 continue
            elif chat_type == ChatType.PRIVATE:
                 stats["private_chat"] += 1
                 continue
            
            if not cat_key: continue
            
            # Total Increment
            stats["total"][cat_key] += 1
            
            # Check Creator
            if getattr(chat, "is_creator", False):
                stats["created"][cat_key] += 1
                
            # Check Admin (Non-Creator)
            elif (getattr(chat, "privileges", None) and chat.privileges.can_manage_chat):
                 stats["admin"][cat_key] += 1
            
            count += 1
            if count % 100 == 0 and scanning_msg:
                 try: await scanning_msg.edit(f"🔍 <b>Scanning chats... ({count} scanned)</b>")
                 except: pass

    except FloodWait as e:
        await asyncio.sleep(e.value)
        if scanning_msg: await scanning_msg.edit(f"⏳ <b>FloodWait {e.value}s</b> during scan. Please try again later.")
        return
    except Exception as e:
        if scanning_msg: await scanning_msg.edit(f"❌ <b>Error:</b> {str(e)}")
        return

    # Update Cache
    cache_data[session_id_str] = {
        "timestamp": now,
        "stats": stats
    }
    try:
        with open(cache_file, "w") as f:
            json.dump(cache_data, f, indent=4)
    except: pass

    await display_chat_stats(c, cb, session_info, stats, index, page)

async def display_chat_stats(c, cb, session_info, stats, index, page, cached=False):
    # Formatting Output
    text = (
        f"📊 <b>Chat Statistics</b> {'(CACHED)' if cached else ''}\n"
        f"👤 <b>Account:</b> {html.escape(session_info.first_name or '')}\n"
        f"🆔 <b>ID:</b> <code>{session_info.id}</code>\n\n"
        
        f"👑 <b>Created (Owner):</b>\n"
        f"• Group: <code>{stats['created']['group']}</code>\n"
        f"• Supergroup: <code>{stats['created']['supergroup']}</code>\n"
        f"• Channel: <code>{stats['created']['channel']}</code>\n"
        f"<b>Total Created:</b> {sum(stats['created'].values())}\n\n"
        
        f"👮 <b>Admin (Excl. Creator):</b>\n"
        f"• Group: <code>{stats['admin']['group']}</code>\n"
        f"• Supergroup: <code>{stats['admin']['supergroup']}</code>\n"
        f"• Channel: <code>{stats['admin']['channel']}</code>\n"
        f"<b>Total Admin:</b> {sum(stats['admin'].values())}\n\n"
        
        f"📈 <b>Total Joined:</b>\n"
        f"• Group: <code>{stats['total']['group']}</code>\n"
        f"• Supergroup: <code>{stats['total']['supergroup']}</code>\n"
        f"• Channel: <code>{stats['total']['channel']}</code>\n"
        f"<b>Grand Total Groups:</b> {sum(stats['total'].values())}\n\n"
        
        f"👤 <b>Other Chats:</b>\n"
        f"• Private User Chats: <code>{stats['private_chat']}</code>\n"
        f"• Bot Chats: <code>{stats['bot']}</code>\n"
    )
    
    buttons = [[InlineKeyboardButton("🔙 Back to Session Info", callback_data=f"session_info_{index}_{page}")]]
    
    await cb.message.edit(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
