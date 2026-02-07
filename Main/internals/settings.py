# settings.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix/Altruix >
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.

from Main import Altruix
from Main.core.config import BaseConfig
from typing import List, Tuple, Dict, Any, Union, Optional
from pyrogram import Client, filters, raw
from Main.core.decorators import log_errors, iuser_check
from Main.core.types.message import Message
from pyrogram.types import (
    CallbackQuery, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove,
    InlineKeyboardButton, InlineKeyboardMarkup, LinkPreviewOptions, User,
    Chat, MessageEntity, InlineQuery, InlineQueryResultArticle, InputTextMessageContent
)
import json

# ====================== PERBAIKAN IMPORT ERROR ======================
# Import semua error yang tersedia di Pyrogram
from pyrogram.errors import (
    PeerIdInvalid, UserIsBlocked, ChatWriteForbidden, FloodWait, MessageIdInvalid,
    SlowmodeWait, InviteHashInvalid, InviteHashExpired, UserAlreadyParticipant,
    ChatAdminRequired, UsernameNotOccupied, ChannelPrivate, UsernameInvalid,
    UsernameNotModified, AboutTooLong, PhotoInvalidDimensions,
    PhotoSaveFileInvalid, UsernameOccupied, RPCError, QueryIdInvalid
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

from pyromod.exceptions import ListenerTimeout
from pyrogram.enums import ParseMode, ChatType
import os
import logging
import asyncio
import html
from datetime import datetime
import io
import re

# ====================== AUTHORIZATION HELPER ======================
def is_authorized(user_id: int) -> bool:
    """Check if user is authorized (owner or sudo user)."""
    return user_id == Altruix.config.OWNER_ID or user_id in Altruix.config.SUDO_USERS

async def check_authorization(cb: CallbackQuery) -> bool:
    """
    Check if callback user is authorized. 
    Returns True if authorized, False otherwise (and sends access denied message).
    """
    if not is_authorized(cb.from_user.id):
        msg = Altruix.get_string("access_denied") or "⛔ Akses Ditolak"
        full_msg = Altruix.get_string("access_denied_desc") or "Anda tidak memiliki izin untuk menggunakan tombol ini."
        await cb.answer(f"{msg} - {full_msg}", show_alert=True)
        return False
    return True

async def edit_cb(cb: CallbackQuery, text: str, **kwargs):
    """Wrapper for Altruix.edit_cb."""
    return await Altruix.edit_cb(cb, text, **kwargs)

async def delete_cb(cb: CallbackQuery):
    """Wrapper for Altruix.delete_cb."""
    return await Altruix.delete_cb(cb)

import pyrogram

# ─── LOGGER KHUSUS PLUGIN ───────────────────────────────────────────────
import logging

plugin_name = f"{os.path.basename(__file__)}"
__plugin_name__ = plugin_name if plugin_name else "settings"
PLUGIN_VERSION = "0.0.6.87"  # ✅ FIXED: Global Audit & Version Sync

logger = logging.getLogger("altruix.settings")
logger.setLevel(logging.INFO)

# ✅ IMPORT BARU: Untuk integrasi session addition
from Main.internals.get_session import add_session_cb_handler

from Main.utils.file_helpers import get_db_path

# Dictionary untuk menyimpan state konfirmasi user
# ✅ SHARED STATES (Using client-instantiated dictionaries)
user_confirmation_state = {}
user_text_confirmation_state = {}
user_bulk_join_state = {}
user_dlphoto_state = {}
user_purge_state = {}
user_eval_state = {}
user_exec_state = {}
user_sys_ctrl_state = {}
user_profile_edit_state = {}
user_photo_delete_state = {}
user_edit_confirmation_state = {}
user_mentions_state = {}
user_recent_messages_state = {}
user_message_count_state = {}
user_limit_check_state = {}
user_dlstory_state = {}
user_privacy_state = Altruix.user_privacy_state
user_bulk_leave_state = {}
user_bulk_report_state = {}
user_laucreate_state = {}
user_env_manager_state = Altruix.user_env_manager_state
user_track_state = Altruix.user_track_state

# ✅ LOCALIZATION / TRANSLATION SYSTEM
SETTINGS_LANG = getattr(Altruix.config, "UB_LANG", "english").lower()

STRINGS = {
    "indonesia": {
        "sessions": "Sesi",
        "configs": "Konfigurasi",
        "session_info_title": "ℹ️ <b>INFO SESI USERBOT</b>",
        "refresh_data": "🔄 Refresh data",
        "unlink_session": "🔗 Unlink (Remove Account)",
        "change_name": "📝 Ganti Nama",
        "change_bio": "✍️ Ganti Bio",
        "change_username": "🆔 Ganti Username",
        "change_profile_photo": "🖼️ Ganti Foto",
        "send_profile_photo": "📷 Kirim Foto Profil",
        "check_limit": "🔍 Check Limit",
        "view_sessions": "📱 Sesi Login",
        "recent_messages": "📨 Pesan Terbaru",
        "view_mentions": "🔔 Lihat Mention",
        "env_edit_file": "📁 Edit via File",
        "mention_control": "🔔 Mention Control",
        "pm_logger_control": "📟 PM Logger Controls",
        "join_group": "➕ Join Group/Ch",
        "leave_group": "🏃 Leave Group/Ch",
        "send_message": "✉️ Send Message",
        "back": "🔙 Kembali",
        "cancel": "❌ Cancel",
        "yes": "✅ Ya",
        "no": "❌ Tidak",
        "unlink_explain": "⚠️ Menghapus sesi akan memutuskan koneksi akun ini secara permanen dari bot sampai Anda menambahkannya kembali.",
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
        "join_logger_control": "🚪 Join Logger",
        "cmd_logger_control": "⌨️ Command Logger",
        "filter_message_control": "🔍 Filter Message",
        "bio": "✍️ Bio",
        "premium": "💠 Premium",
        "session_number": "🔢 Session",
        "bulk_leave": "🏃 Keluar Massal",
        "bulk_report": "🚩 Lapor Massal",
        "export_sessions": "📤 Ekspor Semua Sesi",
        "export_phones": "📲 Ekspor Semua No. HP",
        "refresh_session_info": "🔄 Segarkan Info Sesi",
        "settings_text": "<b>🛠️ Pengaturan Userbot</b>",
        "mention_logic": "Logika Mention",
        "next": "Selanjutnya ➡️",
        "prev": "⬅️ Sebelumnya",
        "apply_type": "Tipe Penerapan",
        "global": "Global 🌐",
        "per_account": "Per-Akun 👤",
        "set_as_global": "Jadikan Global ✨",
        "help_info_msg_updated": "✅ <b>Pesan help info berhasil diperbarui!</b>",
        "custom_delay_prompt": "Silakan kirim <b>angka</b> jeda (delay) dalam detik (contoh: 0.5 atau 2):",
        "purge_progress": "🧹 <b>Purging:</b> <code>{count}/{total}</code>",
        "purge_success_log": "✅ <b>Purge Selesai!</b>\n\n• Chat: {chat}\n• Berhasil: <code>{count}</code>\n• Gagal: <code>{error}</code>",
        "startup_settings_title": "🚀 <b>Pengaturan Startup</b>",
        "help_info_settings_title": "❇️ <b>Pengaturan Help Info</b>",
        "callback_logger": "Callback Logger",
        "custom_bot": "🤖 Custom Bot",
        "cache_log": "🧹 Cache Log",
        "custom_bot_title": "🤖 <b>Custom Assistant Bot</b>",
        "set_bot_token": "🔑 Set Bot Token",
        "remove_bot": "🗑️ Remove Custom Bot",
        "bot_info": "ℹ️ Bot Info",
        "cache_log_title": "🧹 <b>Cache Cleaning Notification</b>",
        "cache_log_desc": "Kirim notifikasi ke log group saat cache dibersihkan",
        "cmd_settings": "Pengaturan Perintah",
        "auto_delete_cmd": "Auto-Delete Input",
        "cmd_settings_text": "<b>🛠️ Pengaturan Perintah</b>",
        "auto_delete_desc": "Hapus otomatis pesan perintah setelah eksekusi.",
        "env_edit_file": "📁 Edit via File"
    },
    "english": {
        "sessions": "Sessions",
        "configs": "Configs",
        "session_info_title": "ℹ️ <b>USERBOT SESSION INFO</b>",
        "refresh_data": "🔄 Refresh data",
        "unlink_session": "🔗 Unlink (Remove Account)",
        "change_name": "📝 Change Name",
        "change_bio": "✍️ Change Bio",
        "change_username": "🆔 Change Username",
        "change_profile_photo": "🖼️ Change Photo",
        "send_profile_photo": "📷 Send Profile Photo",
        "check_limit": "🔍 Check Limit",
        "view_sessions": "📱 Login Sessions",
        "recent_messages": "📨 Recent Messages",
        "view_mentions": "🔔 View Mentions",
        "env_edit_file": "📁 Edit via File",
        "mention_control": "🔔 Mention Control",
        "pm_logger_control": "📟 PM Logger Controls",
        "join_group": "➕ Join Group/Ch",
        "leave_group": "🏃 Leave Group/Ch",
        "send_message": "✉️ Send Message",
        "back": "🔙 Back",
        "cancel": "❌ Cancel",
        "yes": "✅ Yes",
        "no": "❌ No",
        "unlink_explain": "⚠️ Removing the session will permanently disconnect this account from the bot until you add it back.",
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
        "join_logger_control": "🚪 Join Logger",
        "cmd_logger_control": "⌨️ Command Logger",
        "filter_message_control": "🔍 Filter Message",
        "bio": "✍️ Bio",
        "premium": "💠 Premium",
        "session_number": "🔢 Session",
        "bulk_leave": "🏃 Bulk Leave",
        "bulk_report": "🚩 Bulk Report",
        "export_sessions": "📤 Export All Sessions",
        "export_phones": "📲 Export All Phones",
        "refresh_session_info": "🔄 Refresh Session Info",
        "settings_text": "<b>🛠️ Userbot Settings</b>",
        "mention_logic": "Mention Logic",
        "next": "Next ➡️",
        "prev": "⬅️ Prev",
        "apply_type": "Apply Type",
        "global": "Global 🌐",
        "per_account": "Per-Account 👤",
        "set_as_global": "Set as Global ✨",
        "help_info_msg_updated": "✅ <b>Help info message updated!</b>",
        "custom_delay_prompt": "Please send the <b>number</b> of delay in seconds (e.g., 0.5 or 2):",
        "purge_progress": "🧹 <b>Purging:</b> <code>{count}/{total}</code>",
        "purge_success_log": "✅ <b>Purge Complete!</b>\n\n• Chat: {chat}\n• Success: <code>{count}</code>\n• Failed: <code>{error}</code>",
        "startup_settings_title": "🚀 <b>Startup Settings</b>",
        "help_info_settings_title": "❇️ <b>Help Info Settings</b>",
        "callback_logger": "Callback Logger",
        "custom_bot": "🤖 Custom Bot",
        "cache_log": "🧹 Cache Log",
        "custom_bot_title": "🤖 <b>Custom Assistant Bot</b>",
        "set_bot_token": "🔑 Set Bot Token",
        "remove_bot": "🗑️ Remove Custom Bot",
        "bot_info": "ℹ️ Bot Info",
        "cache_log_title": "🧹 <b>Cache Cleaning Notification</b>",
        "cache_log_desc": "Send notification to log group when cache is cleaned",
        "cmd_settings": "🛠️ Command Settings",
        "auto_delete_cmd": "Auto-Delete Input",
        "cmd_settings_text": "<b>🛠️ Command Settings</b>",
        "auto_delete_desc": "Automatically delete command prefix messages after execution."
    }
}

def gt(key):
    """Get Translated string with global YAML support fallback"""
    # 1. Try global Altruix strings (YAML)
    val = Altruix.get_string(key)
    if val and val != key:
        return val
        
    # 2. Fallback to local STRINGS dictionary
    lang = SETTINGS_LANG if SETTINGS_LANG in STRINGS else "english"
    return STRINGS[lang].get(key, STRINGS["english"].get(key, key))

def get_settings_buttons(user_id=None):
    custom_data = get_user_custom_link(user_id) if user_id else get_custom_link_data()["global"]
    return [
        [
            InlineKeyboardButton("📱 Sessions", callback_data="sessions_list_1"),
            InlineKeyboardButton("🤖 Bot Controls", callback_data="bot_controls_menu"),
        ],
        [
            InlineKeyboardButton("⚙️ Configs", callback_data="configs_home"),
            InlineKeyboardButton("❇️ Help Menu", callback_data="re_open"),
        ],
        [
            InlineKeyboardButton(
                custom_data.get("text", "Repo"), 
                url=custom_data.get("link", "https://t.me/AlphaXProject")
            ),
        ],
    ]


# ✅ HELPER: Custom Link Settings
CUSTOM_LINK_FILE = get_db_path("custom_button_settings.json")

def get_custom_link_data():
    if not os.path.exists(CUSTOM_LINK_FILE):
        return {
            "global": {"text": "Repo", "link": "https://t.me/AlphaXProject"},
            "sessions": {},
            "apply_types": {}
        }
    with open(CUSTOM_LINK_FILE, "r") as f:
        try:
            return json.load(f)
        except:
            return {"global": {"text": "Repo", "link": "https://t.me/AlphaXProject"}, "sessions": {}, "apply_types": {}}

def save_custom_link_data(data):
    with open(CUSTOM_LINK_FILE, "w") as f:
        json.dump(data, f, indent=4)

def get_user_custom_link(user_id):
    data = get_custom_link_data()
    apply_type = data.get("apply_types", {}).get(str(user_id), "global")
    
    if apply_type == "per_account" and str(user_id) in data.get("sessions", {}):
        return data["sessions"][str(user_id)]
    return data["global"]


# ✅ FUNGSI BARU: Kirim notifikasi ke log group
async def send_log_notification(
    c: Client, 
    action: str, 
    session_index: int, 
    user: Any, 
    success: bool, 
    error_msg: str = None,
    additional_info: Dict[str, Any] = None,
    reply_markup: InlineKeyboardMarkup = None
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
            'getlinkf': 'Get Invite Link',
            'check_limit': 'Check Limit',
            'recent_messages': 'Pesan Terbaru',  # ✅ BARU
            'view_mentions': 'Lihat Mention',  # ✅ BARU
            'send_profile_photo': 'Kirim Foto Profil',  # ✅ BARU
            'purge_my_message': 'Purge My Message',  # ✅ BARU
            'gpurgeme_completed': 'Global Purgeme'   # ✅ BARU
        }
        
        action_text = action_map.get(action, action)
        status = "✅ BERHASIL" if success else "❌ GAGAL"
        timestamp = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
        
        # Buat pesan log
        user_name = html.escape(user.first_name or "User") if user else "Unknown"
        user_id = user.id if user else "N/A"
        user_link = f"<a href='tg://user?id={user_id}'>{user_name}</a>" if user else "Unknown"

        log_message = (
            f"📢 <b>AKSI PROFIL - {action_text}</b>\n"
            f"• Status: <b>{status}</b>\n"
            f"• User: {user_link}\n"
            f"• User ID: <code>{user_id}</code>\n"
        )
        
        if session_info:
            log_message += (
                f"• Akun: <a href='tg://user?id={session_info.id}'>{html.escape(session_info.first_name or '')}</a>\n"
                f"• Akun ID: <code>{session_info.id}</code>\n"
            )
        
        if additional_info:
            for key, value in additional_info.items():
                if value and str(value).strip():
                    val_str = str(value)
                    # ✅ Cek jika value sudah mengandung tag HTML (a, code, b, i)
                    if any(tag in val_str for tag in ["<a ", "<code>", "<b>", "<i>"]):
                        log_message += f"• {key}: {val_str}\n"
                    else:
                        log_message += f"• {key}: <code>{html.escape(val_str)}</code>\n"
        
        if error_msg:
            log_message += f"• Error: <code>{html.escape(error_msg)}</code>\n"
        
        log_message += f"• Waktu: <code>{timestamp}</code>"
        
        # Kirim ke log group
        try:
            await Altruix.bot.send_message(
                chat_id=log_chat_id,
                text=log_message,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML,
                link_preview_options=LinkPreviewOptions(is_disabled=True)
            )
        except Exception as e:
            from pyrogram.errors import ChannelInvalid, ChatAdminRequired, PeerIdInvalid
            if isinstance(e, (ChannelInvalid, ChatAdminRequired, PeerIdInvalid)):
                Altruix.log(f"Cannot access log chat {log_chat_id}: Telegram says: {e}", level=logging.ERROR)
            else:
                Altruix.log(f"Failed to send log notification: {e}", level=logging.ERROR)
            return # Silent fail on log error
        
    except Exception as e:
        Altruix.log(f"Error sending log notification: {e}", level=logging.ERROR)



@Altruix.bot.on_callback_query(filters.regex(r"^configs_home$"))
@iuser_check
@log_errors
async def configs_menu_cb_handler(c: Client, cb: CallbackQuery):
    await cb.answer()
    
    text = (
        "<b>⚙️ Configuration Manager</b>\n\n"
        "Gunakan menu ini untuk mengelola environment variables dan konfigurasi bot secara langsung.\n"
        "💡 <b>Tip:</b> Perubahan pada beberapa variabel mungkin memerlukan restart bot untuk efek penuh."
    )
    
    buttons = [
        [
            InlineKeyboardButton("🔧 ENV Manager", callback_data="env_manager_list_1"),
        ],
        [
            InlineKeyboardButton("🔙 Back to Settings", callback_data="settings_menu"),
        ]
    ]
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons))


@Altruix.bot.on_callback_query(filters.regex(r"^bot_controls_menu$"))
@iuser_check
@log_errors
async def bot_controls_menu_handler(c: Client, cb: CallbackQuery):
    await cb.answer()
    
    text = (
        "<b>🤖 Bot Controls</b>\n\n"
        "Menu untuk mengatur perilaku Bot Assistant secara global.\n"
        "Pilih menu di bawah ini:"
    )
    
    buttons = [
        [
            InlineKeyboardButton("📟 PM Logger Bot", callback_data="pmlb_menu"),
            InlineKeyboardButton("🔘 Callback Logger", callback_data="cb_logger_settings"),
        ],
        [
            InlineKeyboardButton("🔔 Mention Logger", callback_data="mntlb_menu"),
            InlineKeyboardButton("💬 Reply Manager", callback_data="reply_manager_menu"),
        ],
        [
            InlineKeyboardButton("🚪 Join Logger Global", callback_data="joinl_menu_global"),
            InlineKeyboardButton("🔗 Group Log Link", callback_data="get_log_group_link"),
        ],
        [
            InlineKeyboardButton("👽 Custom Bot Manager", callback_data="custom_bot_manager"),
            InlineKeyboardButton("🔘 Custom Link/Text", callback_data="custom_link_settings"),
        ],
        [
            InlineKeyboardButton("🔙 Back to Settings", callback_data="settings_menu"),
        ]

    ]
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons))


# ✅ HANDLER: Custom Link Settings Menu
@Altruix.bot.on_callback_query(filters.regex(r"^custom_link_settings$"))
@iuser_check
@log_errors
async def custom_link_settings_handler(c: Client, cb: CallbackQuery):
    await cb.answer()
    user_id = cb.from_user.id
    data = get_custom_link_data()
    
    apply_type = data.get("apply_types", {}).get(str(user_id), "global")
    current_link = get_user_custom_link(user_id)
    
    apply_text = gt("custom_link_global") if apply_type == "global" else gt("custom_link_per_account")
    
    msg_body = gt("custom_link_desc").format(
        current_link.get("text", gt("default_text")),
        current_link.get("link", gt("default_link")),
        apply_text
    )
    
    buttons = [
        [
            InlineKeyboardButton(gt("edit_button_text"), callback_data="edit_cl_text"),
            InlineKeyboardButton(gt("edit_button_link"), callback_data="edit_cl_link"),
        ],
        [
            InlineKeyboardButton(gt("apply_type_btn").format(apply_text), callback_data="toggle_cl_apply"),
            InlineKeyboardButton(gt("reset_default"), callback_data="reset_cl_default"),
        ],
        [
            InlineKeyboardButton(gt("back"), callback_data="settings_menu"),
        ]
    ]
    
    await edit_cb(cb, gt("custom_link_title") + "\n\n" + msg_body, reply_markup=InlineKeyboardMarkup(buttons))


@Altruix.bot.on_callback_query(filters.regex(r"^edit_cl_(text|link)$"))
@iuser_check
@log_errors
async def edit_cl_input_handler(c: Client, cb: CallbackQuery):
    await cb.answer()
    target = cb.matches[0].group(1)
    user_id = cb.from_user.id
    
    Altruix.user_track_state[user_id] = {"step": f"edit_cl_{target}", "msg_id": cb.message.id}
    
    prompt = gt("prompt_edit_text") if target == "text" else gt("prompt_edit_link")
    
    await edit_cb(cb, prompt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(gt("cancel"), callback_data="custom_link_settings")]]))


@Altruix.bot.on_callback_query(filters.regex(r"^toggle_cl_apply$"))
@iuser_check
@log_errors
async def toggle_cl_apply_handler(c: Client, cb: CallbackQuery):
    user_id = cb.from_user.id
    data = get_custom_link_data()
    
    current = data.get("apply_types", {}).get(str(user_id), "global")
    new_type = "per_account" if current == "global" else "global"
    
    data.setdefault("apply_types", {})[str(user_id)] = new_type
    save_custom_link_data(data)
    
    await cb.answer(gt("apply_type_changed").format(gt(f"custom_link_{new_type}")), show_alert=True)
    await custom_link_settings_handler(c, cb)


@Altruix.bot.on_callback_query(filters.regex(r"^reset_cl_default$"))
@iuser_check
@log_errors
async def reset_cl_default_handler(c: Client, cb: CallbackQuery):
    user_id = cb.from_user.id
    data = get_custom_link_data()
    
    if str(user_id) in data.get("sessions", {}):
        del data["sessions"][str(user_id)]
    
    if str(user_id) in data.get("apply_types", {}):
        data["apply_types"][str(user_id)] = "global"
        
    save_custom_link_data(data)
    
    await cb.answer(gt("btn_reset"), show_alert=True)
    await custom_link_settings_handler(c, cb)



# ✅ HANDLER: Global Close Button
@Altruix.bot.on_callback_query(filters.regex(r"^create_close$"))
async def create_close_handler(c: Client, cb: CallbackQuery):
    try:
        await cb.message.delete()
    except:
        pass


# ✅ HANDLER: Get Log Group Link
@Altruix.bot.on_callback_query(filters.regex(r"^get_log_group_link$"))
@iuser_check
@log_errors
async def get_log_group_link_handler(c: Client, cb: CallbackQuery):
    log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))
    try:
        chat = await c.get_chat(log_chat_id)
        link = chat.invite_link
        if not link:
             link = await c.export_chat_invite_link(log_chat_id)
        
        await edit_cb(cb, 
            f"🔗 <b>Log Group Link</b>\n\nLink: {link}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="bot_controls_menu")]])
        )
    except Exception as e:
        await cb.answer(f"❌ Error: {e}", show_alert=True)


# ✅ HANDLER: Join Logger Global Menu
@Altruix.bot.on_callback_query(filters.regex(r"^joinl_menu_global$"))
@iuser_check
@log_errors
async def joinl_menu_global_handler(c: Client, cb: CallbackQuery):
    filename = get_db_path("join_logger_settings.json")
    data = {"global": {"enabled": True}, "sessions": {}, "apply_types": {}}
    if os.path.exists(filename):
        with open(filename, "r") as f:
            loaded = json.load(f)
            if "global" in loaded: data = loaded
            else: data["global"]["enabled"] = loaded.get("enabled", True)
            
    active_enabled = data["global"].get("enabled", True)
    
    text = (
        "<b>🚪 Join Logger Global Settings</b>\n\n"
        "Pengaturan ini akan berlaku untuk semua akun yang menggunakan tipe 'Global'.\n\n"
        f"• <b>Status Global:</b> {'✅ ENABLED' if active_enabled else '❌ DISABLED'}"
    )
    
    buttons = [
        [InlineKeyboardButton(f"{'Disable' if active_enabled else 'Enable'} Globally", "joinl_toggle_global")],
        [InlineKeyboardButton("🔙 Back", "bot_controls_menu")]
    ]
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons))


@Altruix.bot.on_callback_query(filters.regex(r"^joinl_toggle_global$"))
@iuser_check
@log_errors
async def joinl_toggle_global_handler(c: Client, cb: CallbackQuery):
    filename = get_db_path("join_logger_settings.json")
    data = {"global": {"enabled": True}, "sessions": {}, "apply_types": {}}
    if os.path.exists(filename):
        with open(filename, "r") as f: data = json.load(f)
        
    data["global"]["enabled"] = not data["global"].get("enabled", True)
    
    with open(filename, "w") as f: json.dump(data, f, indent=4)
    
    await cb.answer(f"Global Join Logger: {'Enabled' if data['global']['enabled'] else 'Disabled'}")
    await joinl_menu_global_handler(c, cb)



@Altruix.bot.on_callback_query(filters.regex(r"^cb_logger_settings$"))
@iuser_check
@log_errors
async def cb_logger_settings_handler(c: Client, cb: CallbackQuery):
    await cb.answer()
    log_type = (await Altruix.config.get_env("CALLBACK_LOGGER_TYPE") or "all").lower()
    
    text = (
        "<b>🔘 Callback Logger Settings</b>\n\n"
        "Pilih siapa yang akan dicatat aktivitas callback-nya:\n"
        f"• Status Saat Ini: <code>{log_type.upper()}</code>\n\n"
        "💡 <b>Deskripsi:</b>\n"
        "• <b>All</b>: Catat semua user.\n"
        "• <b>Sudo</b>: Hanya catat sudo user.\n"
        "• <b>Non-Sudo</b>: Hanya catat user biasa.\n"
        "• <b>Off</b>: Matikan logging callback."
    )
    
    buttons = [
        [
            InlineKeyboardButton("✅ All" if log_type == "all" else "All", callback_data="set_cb_log_all"),
            InlineKeyboardButton("✅ Sudo" if log_type == "sudo" else "Sudo", callback_data="set_cb_log_sudo"),
        ],
        [
            InlineKeyboardButton("✅ Non-Sudo" if log_type == "non_sudo" else "Non-Sudo", callback_data="set_cb_log_non_sudo"),
            InlineKeyboardButton("❌ Off" if log_type == "off" else "Off", callback_data="set_cb_log_off"),
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="bot_controls_menu"),
        ]
    ]
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons))


@Altruix.bot.on_callback_query(filters.regex(r"set_cb_log_(all|sudo|non_sudo|off)"))
@iuser_check
@log_errors
async def set_cb_log_type_handler(c: Client, cb: CallbackQuery):
    new_type = cb.matches[0].group(1)
    # Save to persistent DB
    await Altruix.config.sync_env_to_db("CALLBACK_LOGGER_TYPE", new_type, upsert=True)
    # Update local state for immediate effect
    os.environ["CALLBACK_LOGGER_TYPE"] = new_type
    
    await cb.answer(f"✅ Callback Logger set to: {new_type.upper()}", show_alert=True)
    await cb_logger_settings_handler(c, cb)


@Altruix.bot.on_callback_query(filters.regex(r"^settings_menu$"))
@log_errors
async def settings_menu_cb_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer()
    
    total_sessions = len(Altruix.clients) if hasattr(Altruix, 'clients') else 0
    default_bots = 1
    custom_bots = len(Altruix.bot_manager.custom_bots) if hasattr(Altruix, 'bot_manager') and hasattr(Altruix.bot_manager, 'custom_bots') else 0
    total_bots = default_bots + custom_bots
        
    # Get Module Stats
    ub_mods = 0
    bot_mods = 0
    xtra_mods = 0
    xtra_features = 0
    
    for plugin, cat in Altruix.plugin_categories.items():
        if cat == "userbot":
            ub_mods += 1
        elif cat == "bot":
            bot_mods += 1
        else:
            xtra_mods += 1
            if plugin in Altruix.cmd_list:
                for cmd_info in Altruix.cmd_list[plugin]:
                    xtra_features += len(cmd_info.get("commands", []))
                    
    total_mods = ub_mods + bot_mods + xtra_mods

    full_text = gt('settings_stats').format(
        total_sessions, total_bots, default_bots, custom_bots, xtra_features, total_mods, ub_mods, bot_mods, xtra_mods, Altruix.total_commands, Altruix.__version__
    ) + f"\n\n<i>{gt('select_category')}</i>"


    await edit_cb(
        cb,
        text=full_text,
        reply_markup=InlineKeyboardMarkup(get_settings_buttons(cb.from_user.id))
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
            
            # ✅ Status Check
            user_id = getattr(getattr(client, 'myself', None), 'id', None)
            is_disabled = Altruix.is_session_disabled(user_id) if user_id else False
            status_icon = "❌" if is_disabled else "✅"

            # PERUBAHAN: Format tombol dengan nomor: [[1] Nama Akun]
            button_text = f"{status_icon} [{session_num}] {first_name[:15]}" if len(first_name) > 15 else f"{status_icon} [{session_num}] {first_name}"
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
        default_bots = 1
        custom_bots = len(Altruix.bot_manager.custom_bots) if hasattr(Altruix, 'bot_manager') and hasattr(Altruix.bot_manager, 'custom_bots') else 0
        total_bots = default_bots + custom_bots
        
        # Get Module Stats
        ub_mods = 0
        bot_mods = 0
        xtra_mods = 0
        xtra_features = 0
        
        for plugin, cat in Altruix.plugin_categories.items():
            if cat == "userbot":
                ub_mods += 1
            elif cat == "bot":
                bot_mods += 1
            else:
                xtra_mods += 1
                if plugin in Altruix.cmd_list:
                    for cmd_info in Altruix.cmd_list[plugin]:
                        xtra_features += len(cmd_info.get("commands", []))
                        
        total_mods = ub_mods + bot_mods + xtra_mods

        full_text = gt('settings_stats').format(
            total_sessions, total_bots, default_bots, custom_bots, xtra_features, total_mods, ub_mods, bot_mods, xtra_mods, Altruix.total_commands, Altruix.__version__
        ) + f"\n\n<i>{gt('select_category')}</i>"

        
        await m.reply(
            full_text,
            reply_markup=InlineKeyboardMarkup(get_settings_buttons(m.from_user.id)),
            quote=True,
        )

        logging.info(f"User {m.from_user.id} used /settings command")
    except Exception as e:
        logger.error(f"Gagal kirim notifikasi ke log: {e}")


        logger.error(f"Gagal kirim notifikasi ke log: {e}")


@Altruix.bot.on_inline_query(filters.regex(r"^settings$"))
@log_errors
async def settings_inline_handler(c: Client, iq: InlineQuery):
    """Handler untuk menyediakan menu settings via inline (untuk userbot)"""
    try:
        # Check authorization (only owner/sudo)
        if iq.from_user.id not in Altruix.auth_users:
            return await iq.answer(
                results=[
                    InlineQueryResultArticle(
                        title="🚫 Akses Ditolak",
                        input_message_content=InputTextMessageContent(
                            "⛔ Anda tidak diizinkan mengakses menu pengaturan ini."
                        )
                    )
                ],
                cache_time=0,
                is_personal=True
            )

        total_sessions = len(Altruix.clients) if hasattr(Altruix, 'clients') else 0
        default_bots = 1
        custom_bots = len(Altruix.bot_manager.custom_bots) if hasattr(Altruix, 'bot_manager') and hasattr(Altruix.bot_manager, 'custom_bots') else 0
        total_bots = default_bots + custom_bots
        
        # Get Module Stats
        ub_mods = 0
        bot_mods = 0
        xtra_mods = 0
        xtra_features = 0
        
        for plugin, cat in Altruix.plugin_categories.items():
            if cat == "userbot":
                ub_mods += 1
            elif cat == "bot":
                bot_mods += 1
            else:
                xtra_mods += 1
                if plugin in Altruix.cmd_list:
                    for cmd_info in Altruix.cmd_list[plugin]:
                        xtra_features += len(cmd_info.get("commands", []))
                        
        total_mods = ub_mods + bot_mods + xtra_mods

        full_text = gt('settings_stats').format(
            total_sessions, total_bots, default_bots, custom_bots, xtra_features, total_mods, ub_mods, bot_mods, xtra_mods, Altruix.total_commands, Altruix.__version__
        ) + f"\n\n<i>{gt('select_category')}</i>"


        await iq.answer(
            results=[
                InlineQueryResultArticle(
                    title="Userbot Settings",
                    input_message_content=InputTextMessageContent(
                        full_text,
                        parse_mode=ParseMode.HTML
                    ),
                    reply_markup=InlineKeyboardMarkup(get_settings_buttons(iq.from_user.id))
                )
            ],
            cache_time=0,
            is_personal=True
        )

    except Exception as e:
        logger.error(f"Error in settings_inline_handler: {e}")

# ✅ HANDLER GLOBAL UNTUK KONFIRMASI EDIT (INLINE)
@Altruix.bot.on_callback_query(filters.regex(r"^edit_confirm_(yes|no)_(\d+)"))
@log_errors
async def edit_confirm_cb_handler(c: Client, cb: CallbackQuery):
    """Handler global untuk memproses konfirmasi Yes/No dari Inline Buttons"""
    if not await check_authorization(cb): return
    action_type = cb.matches[0].group(1)
    user_id = int(cb.matches[0].group(2))
    
    if action_type == "no":
        # Bersihkan state dan batalkan
        user_edit_confirmation_state.pop(user_id, None)
        user_profile_edit_state.pop(user_id, None)
        await cb.answer("Dibatalkan.", show_alert=True)
        await edit_cb(cb, "❌ Aksi dibatalkan oleh pengguna.")
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
            if cb.message:
                if cb.message: await cb.message.delete()
        except:
            pass
            
    except Exception as e:
        logger.error(f"Error in edit_confirm_cb_handler: {e}")
        await edit_cb(cb, f"❌ Terjadi kesalahan: {str(e)}")
        await m.reply("❌ Terjadi error saat memproses command.")


@Altruix.bot.on_callback_query(filters.regex("sessions_list_(\\d+)$"))
@log_errors
async def sessions_menu_cb_handler(c: Client, cb: CallbackQuery):
    """Handler untuk menampilkan menu sessions dengan layout baru"""
    if not await check_authorization(cb): return
    await cb.answer()
    try:
        page = int(cb.data.split("_")[-1])
    except (ValueError, IndexError):
        page = 1

    # Dapatkan tombol session untuk halaman ini (sudah dalam format 3 baris x 3 kolom)
    session_buttons, has_next, total_pages = get_sessions_buttons(page)
    
    # Dapatkan LOG_CHAT_ID dengan benar
    LOG_CHAT_ID = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))

    # Baris 4: Tombol aksi
    action_buttons = [
        [
            InlineKeyboardButton("👥 Bulk Join", "bulk_join_menu"),
            InlineKeyboardButton("🏃 Bulk Leave", "bulk_leave_menu"),
            InlineKeyboardButton("🚩 Bulk Report", "bulk_report_menu")
        ],
        [
            InlineKeyboardButton("🏓 Test Ping All", "test_ping_all_confirmation"),
            InlineKeyboardButton(gt("btn_stats"), "sessions_stats"),
            InlineKeyboardButton("➕ Add a Session", "add_session")
        ]
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
    
    # Tambahkan action buttons sebagai baris keempat dan kelima
    for row in action_buttons:
        final_markup.append(row)
    
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
        await edit_cb(
            cb,
            text=f"<b>📱 Sessions Manager</b>\n\n"
                 f"<b>Total Sessions:</b> <code>{total_sessions}</code>\n"
                 f"<b>Showing:</b> <code>{start_session}-{end_session}</code>\n"
                 f"<b>Page:</b> <code>{page}/{total_pages or 1}</code>\n\n"
                 f"Select a session below to manage it or use the bulk actions.",
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
        await edit_cb(cb, "❌ Failed to load menu. Owner has been notified.")

@Altruix.bot.on_callback_query(filters.regex("^sessions_stats$"))
@log_errors
@iuser_check
async def sessions_stats_cb_handler(c: Client, cb: CallbackQuery):
    """Handler untuk menampilkan statistik sesi secara interaktif"""
    if not await check_authorization(cb): return
    await cb.answer()
    
    total_sessions = len(Altruix.clients) if hasattr(Altruix, 'clients') else 0
    inactive_sessions = 0
    
    if hasattr(Altruix, 'disabled_sessions'):
        for client in Altruix.clients:
            me = getattr(client, 'myself', None)
            if me and Altruix.is_session_disabled(me.id):
                inactive_sessions += 1
                
    active_sessions = total_sessions - inactive_sessions
    total_custom_bots = len(Altruix.bot_manager.custom_bots) if hasattr(Altruix, 'bot_manager') else 0
    
    txt = (
        f"{gt('sessions_stats_title')}\n\n"
        f"{gt('active_sessions').format(active_sessions)}\n"
        f"{gt('inactive_sessions').format(inactive_sessions)}\n"
        f"{gt('total_sessions').format(total_sessions)}\n"
        f"{gt('total_custom_bots').format(total_custom_bots)}\n\n"
        f"<i>💡 This data reflects current in-memory state.</i>"
    )
    
    buttons = [
        [InlineKeyboardButton(gt("refresh_data"), "sessions_stats")],
        [InlineKeyboardButton(gt("back"), "sessions_list_1")]
    ]
    
    await edit_cb(cb, txt, reply_markup=InlineKeyboardMarkup(buttons))


# ====================== BULK JOIN FEATURE ======================
@Altruix.bot.on_callback_query(filters.regex("bulk_join_menu"))
@log_errors
async def bulk_join_menu_handler(c: Client, cb: CallbackQuery):
    """Handler untuk menu bulk join"""
    if not await check_authorization(cb): return
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
    
    await edit_cb(cb, 
        text="<b>👥 Bulk Join Settings</b>\n\n"
             "Pilih jeda waktu antara join (untuk menghindari flood wait):\n\n"
             "⚠️ <b>Note:</b>\n"
             "• Delay yang lebih besar mengurangi risiko flood wait\n"
             "• Delay yang lebih kecil lebih cepat tapi berisiko",
        reply_markup=InlineKeyboardMarkup(delay_buttons)
    )


@Altruix.bot.on_callback_query(filters.regex("bulk_leave_menu"))
@log_errors
async def bulk_leave_menu_handler(c: Client, cb: CallbackQuery):
    """Handler untuk menu bulk leave"""
    if not await check_authorization(cb): return
    await cb.answer()
    
    # Tampilkan pilihan delay
    delay_buttons = [
        [
            InlineKeyboardButton("2 detik", callback_data="bulk_leave_delay_2"),
            InlineKeyboardButton("4 detik", callback_data="bulk_leave_delay_4"),
            InlineKeyboardButton("6 detik", callback_data="bulk_leave_delay_6"),
        ],
        [
            InlineKeyboardButton("8 detik", callback_data="bulk_leave_delay_8"),
            InlineKeyboardButton("10 detik", callback_data="bulk_leave_delay_10"),
            InlineKeyboardButton("15 detik", callback_data="bulk_leave_delay_15"),
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="sessions_list_1"),
        ]
    ]
    
    await edit_cb(cb, 
        text="<b>🏃 Bulk Leave Settings</b>\n\n"
             "Pilih jeda waktu antara keluar dari chat:\n\n"
             "⚠️ <b>Note:</b>\n"
             "• Delay penting untuk menghindari limit Telegram.",
        reply_markup=InlineKeyboardMarkup(delay_buttons)
    )


@Altruix.bot.on_callback_query(filters.regex("bulk_leave_delay_(\\d+)"))
@log_errors
async def bulk_leave_delay_handler(c: Client, cb: CallbackQuery):
    """Handler untuk memilih delay bulk leave"""
    if not await check_authorization(cb): return
    await cb.answer()
    
    try:
        delay = int(cb.matches[0].group(1))
    except (ValueError, IndexError):
        delay = 5
    
    user_id = cb.from_user.id
    user_bulk_leave_state[user_id] = {
        'delay': delay,
        'chat_id': None,
        'step': 'waiting_chat'
    }
    
    await edit_cb(cb, 
        text=f"<b>🏃 Bulk Leave - Delay {delay} detik</b>\n\n"
             "Silakan kirim Chat ID atau Username grup/channel yang akan ditinggalkan:\n\n"
             "❌ <b>Cancel:</b> Ketik /cancel",
        parse_mode=ParseMode.HTML
    )


@Altruix.bot.on_callback_query(filters.regex("bulk_report_menu"))
@log_errors
async def bulk_report_menu_handler(c: Client, cb: CallbackQuery):
    """Handler untuk menu bulk report"""
    if not await check_authorization(cb): return
    await cb.answer()
    
    # Tampilkan pilihan delay
    delay_buttons = [
        [
            InlineKeyboardButton("2 detik", callback_data="bulk_report_delay_2"),
            InlineKeyboardButton("4 detik", callback_data="bulk_report_delay_4"),
            InlineKeyboardButton("6 detik", callback_data="bulk_report_delay_6"),
        ],
        [
            InlineKeyboardButton("8 detik", callback_data="bulk_report_delay_8"),
            InlineKeyboardButton("10 detik", callback_data="bulk_report_delay_10"),
            InlineKeyboardButton("15 detik", callback_data="bulk_report_delay_15"),
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="sessions_list_1"),
        ]
    ]
    
    await edit_cb(cb, 
        text="<b>🚩 Bulk Report Settings</b>\n\n"
             "Pilih jeda waktu antar report:\n\n"
             "⚠️ <b>Note:</b>\n"
             "• Delay membantu akun anda tetap aman.",
        reply_markup=InlineKeyboardMarkup(delay_buttons)
    )


@Altruix.bot.on_callback_query(filters.regex("bulk_report_delay_(\\d+)"))
@log_errors
async def bulk_report_delay_handler(c: Client, cb: CallbackQuery):
    """Handler untuk memilih delay bulk report"""
    if not await check_authorization(cb): return
    await cb.answer()
    
    try:
        delay = int(cb.matches[0].group(1))
    except (ValueError, IndexError):
        delay = 5
    
    user_id = cb.from_user.id
    user_bulk_report_state[user_id] = {
        'delay': delay,
        'target': None,
        'step': 'waiting_target'
    }
    
    await edit_cb(cb, 
        text=f"<b>🚩 Bulk Report - Delay {delay} detik</b>\n\n"
             "Silakan kirim Chat ID atau Username target yang akan di-report:\n\n"
             "❌ <b>Cancel:</b> Ketik /cancel",
        parse_mode=ParseMode.HTML
    )


@Altruix.bot.on_callback_query(filters.regex("bulk_join_delay_(\\d+)"))
@log_errors
async def bulk_join_delay_handler(c: Client, cb: CallbackQuery):
    """Handler untuk memilih delay bulk join"""
    if not await check_authorization(cb): return
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
    
    await edit_cb(cb, 
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
@Altruix.bot.on_message((filters.text | filters.document) & filters.private & filters.user(Altruix.auth_users))
@log_errors
async def user_text_handler(c: Client, m: Message):
    """Handler untuk menerima input teks dari user (dengan konfirmasi)"""
    user_id = m.from_user.id
    text = (m.text or m.caption or "").strip()
    
    # ✅ PERBAIKAN: Izinkan flag/command bot agar tidak di-intersep bila tidak perlu
    # Jika pesan dimulai dengan '/' dan bukan '/cancel', biarkan Handler Command yang memproses.
    if text.startswith("/") and text.lower() != "/cancel":
        m.continue_propagation()
        return
    
    # ✅ NEW: Handle Privacy State (Block/Unblock)
    if user_id in user_privacy_state:
        state = user_privacy_state[user_id]
        if text.lower() == "/cancel":
            del user_privacy_state[user_id]
            await m.reply(
                "❌ Dibatalkan.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menu", callback_data=f"privacy_menu_{state['session_index']}_{state['page']}")]])
            )
            return

    # ✅ Custom Link Settings Input
    if user_id in Altruix.user_track_state:
        state = Altruix.user_track_state[user_id]
        step = state.get("step", "")
        
        if text.lower() == "/cancel":
            del Altruix.user_track_state[user_id]
            await m.reply("❌ Dibatalkan.")
            return

        if step.startswith("edit_cl_"):
            target = step.replace("edit_cl_", "") # "text" or "link"
            data = get_custom_link_data()
            apply_type = data.get("apply_types", {}).get(str(user_id), "global")
            
            if target == "link" and not (text.startswith("http://") or text.startswith("https://")):
                await m.reply(gt("invalid_link"))
                return
            
            if apply_type == "global":
                data["global"][target] = text
            else:
                data.setdefault("sessions", {}).setdefault(str(user_id), {})[target] = text
                if target == "text" and "link" not in data["sessions"][str(user_id)]:
                    data["sessions"][str(user_id)]["link"] = data["global"]["link"]
                elif target == "link" and "text" not in data["sessions"][str(user_id)]:
                    data["sessions"][str(user_id)]["text"] = data["global"]["text"]
            
            save_custom_link_data(data)
            del Altruix.user_track_state[user_id]
            
            await m.reply(gt("btn_updated").format(target.capitalize()))
            try:
                await c.send_message(m.chat.id, gt("custom_link_title"), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(gt("back"), callback_data="custom_link_settings")]]))
            except:
                pass
            return


        # ✅ Handle Custom Startup Message Input
        if state['step'] == 'waiting_startup_custom_msg':
            index = state['session_index']
            page = state['page']
            
            # Save to DB
            apply_type = await Altruix.config.get_env(f"STARTUP_MSG_TYPE_{index}") or "per_account"
            if apply_type == "global":
                key = "STARTUP_CUSTOM_MSG_GLOBAL"
            else:
                key = f"STARTUP_CUSTOM_MSG_{index}"
                
            await Altruix.config.sync_env_to_db(key, text, upsert=True)
            setattr(Altruix.config, key, text)
            
            # Clear state
            del user_privacy_state[user_id]
            
            await m.reply(
                f"✅ <b>Startup message berhasil diupdate!</b>\n\n"
                f"<code>{html.escape(text)}</code>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(gt("cancel"), callback_data=f"startup_custom_menu_{index}_{page}_{button_page}")]])
            )
            return

        # ✅ Handle Custom Help Message Input
        if state['step'] == 'waiting_help_custom_msg':
            index = state['session_index']
            page = state['page']
            
            # Save to DB based on type
            apply_type = await Altruix.config.get_env(f"HELP_INFO_TYPE_{index}") or "per_account"
            if apply_type == "global":
                key = "HELP_INFO_CUSTOM_MSG_GLOBAL"
            else:
                key = f"HELP_INFO_CUSTOM_MSG_{index}"
                
            await Altruix.config.sync_env_to_db(key, text, upsert=True)
            setattr(Altruix.config, key, text)
            
            # Clear state
            del user_privacy_state[user_id]
            
            await m.reply(
                f"{gt('help_info_msg_updated')}\n\n"
                f"<code>{html.escape(text)}</code>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(gt("back"), callback_data=f"help_info_custom_menu_{index}_{page}")]])
            )
            return

        await execute_block_unblock(c, m, state)
        return

    # ✅ NEW: Handle Laucreate Input
    if user_id in user_laucreate_state:
        if text.lower() == "/cancel":
            del user_laucreate_state[user_id]
            await m.reply("❌ Laucreate setup dibatalkan.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Settings", "settings_menu")]]))
            return
        
        await process_laucreate_input(c, m, text)
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

    # ✅ BARU: Cek jika user sedang menunggu input delay custom untuk purge
    elif user_id in user_purge_state and user_purge_state[user_id]['step'] == 'waiting_custom_delay':
        if text.lower() == "/cancel":
            del user_purge_state[user_id]
            await m.reply("❌ Purge dibatalkan.")
            return
        
        try:
            delay = float(text)
            if delay < 0:
                await m.reply("❌ Jeda tidak boleh negatif.")
                return
        except ValueError:
            await m.reply("❌ Masukkan angka (float/int) yang valid.")
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
        
        await m.reply(
            f"<b>🧹 Purge My Message</b>\n\n"
            f"Chat: <code>{html.escape(state['chat_id'])}</code>\n"
            f"Jumlah: <code>{state['amount']}</code>\n"
            f"Jeda: <code>{delay}s</code>\n\n"
            f"Pilih mode urutan penghapusan:",
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
    
    # ✅ BARU: Cek jika user sedang dalam proses bulk leave
    elif user_id in user_bulk_leave_state and user_bulk_leave_state[user_id]['step'] == 'waiting_chat':
        if text.lower() == "/cancel":
            del user_bulk_leave_state[user_id]
            await m.reply("❌ Bulk leave dibatalkan.")
            return
        
        # Simpan chat_id
        user_bulk_leave_state[user_id]['chat_id'] = text
        user_bulk_leave_state[user_id]['step'] = 'confirming'
        
        delay = user_bulk_leave_state[user_id]['delay']
        total_sessions = len(Altruix.clients) if hasattr(Altruix, 'clients') else 0
        
        confirmation_buttons = [
            [
                InlineKeyboardButton("✅ Yes, Leave All", callback_data="bulk_leave_confirm_yes"),
                InlineKeyboardButton("❌ No, Cancel", callback_data="bulk_leave_confirm_no")
            ]
        ]
        
        await m.reply(
            text=f"<b>🏃 Confirm Bulk Leave</b>\n\n"
                 f"• <b>Target Chat:</b> <code>{html.escape(text)}</code>\n"
                 f"• <b>Delay:</b> <code>{delay} detik</code>\n"
                 f"• <b>Total Sessions:</b> <code>{total_sessions}</code>\n\n"
                 f"⚠️ <b>WARNING:</b>\n"
                 f"• Semua session akan keluar dari chat tersebut\n"
                 f"• Aksi ini tidak dapat dibatalkan setelah dimulai",
            reply_markup=InlineKeyboardMarkup(confirmation_buttons),
            parse_mode=ParseMode.HTML
        )
        return

    # ✅ BARU: Cek jika user sedang dalam proses bulk report
    elif user_id in user_bulk_report_state and user_bulk_report_state[user_id]['step'] == 'waiting_target':
        if text.lower() == "/cancel":
            del user_bulk_report_state[user_id]
            await m.reply("❌ Bulk report dibatalkan.")
            return
        
        # Simpan target
        user_bulk_report_state[user_id]['target'] = text
        user_bulk_report_state[user_id]['step'] = 'selecting_reason'
        
        reason_buttons = [
            [
                InlineKeyboardButton("SPAM", callback_data=f"bulk_report_reason_{user_id}_spam"),
                InlineKeyboardButton("VIOLENCE", callback_data=f"bulk_report_reason_{user_id}_violence"),
            ],
            [
                InlineKeyboardButton("PORNOGRAPHY", callback_data=f"bulk_report_reason_{user_id}_pornography"),
                InlineKeyboardButton("CHILD ABUSE", callback_data=f"bulk_report_reason_{user_id}_child_abuse"),
            ],
            [
                InlineKeyboardButton("OTHER", callback_data=f"bulk_report_reason_{user_id}_other"),
                InlineKeyboardButton("Custom Text", callback_data=f"bulk_report_reason_{user_id}_custom"),
            ],
            [
                InlineKeyboardButton("🔙 Cancel", callback_data=f"sessions_list_1"),
            ]
        ]
        
        await m.reply(
            text=f"<b>🚩 Bulk Report</b>\n\n"
                 f"Target: <code>{html.escape(text)}</code>\n\n"
                 f"Pilih alasan report:",
            reply_markup=InlineKeyboardMarkup(reason_buttons),
            parse_mode=ParseMode.HTML
        )
        return
    
    # ✅ BARU: Cek jika user sedang mengetik alasan custom untuk report
    elif user_id in user_bulk_report_state and user_bulk_report_state[user_id]['step'] == 'waiting_custom_reason':
        if text.lower() == "/cancel":
            del user_bulk_report_state[user_id]
            await m.reply("❌ Bulk report dibatalkan.")
            return
        
        user_bulk_report_state[user_id]['reason'] = text
        user_bulk_report_state[user_id]['step'] = 'confirming'
        
        state = user_bulk_report_state[user_id]
        delay = state['delay']
        total_sessions = len(Altruix.clients) if hasattr(Altruix, 'clients') else 0
        
        confirmation_buttons = [
            [
                InlineKeyboardButton("✅ Yes, Report All", callback_data="bulk_report_confirm_yes"),
                InlineKeyboardButton("❌ No, Cancel", callback_data="bulk_report_confirm_no")
            ]
        ]
        
        await m.reply(
            text=f"<b>🚩 Confirm Bulk Report</b>\n\n"
                 f"• <b>Target:</b> <code>{html.escape(state['target'])}</code>\n"
                 f"• <b>Reason:</b> <code>{html.escape(text)}</code>\n"
                 f"• <b>Delay:</b> <code>{delay} detik</code>\n"
                 f"• <b>Total Sessions:</b> <code>{total_sessions}</code>\n\n"
                 f"⚠️ <b>WARNING:</b>\n"
                 f"• Semua session akan melaporkan target tersebut",
            reply_markup=InlineKeyboardMarkup(confirmation_buttons),
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

    # ✅ BARU: Cek jika user sedang dalam proses Track Profile
    elif user_id in Altruix.user_track_state and Altruix.user_track_state[user_id].get('step') == 'waiting_target_id':
        if text.lower() == "/cancel":
            del Altruix.user_track_state[user_id]
            await m.reply("❌ Track Profile dibatalkan.")
            return
            
        target_id = text.strip()
        Altruix.user_track_state[user_id]['target_id'] = target_id
        Altruix.user_track_state[user_id]['step'] = 'confirming'
        
        session_index = Altruix.user_track_state[user_id]['session_index']
        page = Altruix.user_track_state[user_id]['page']
        
        confirm_btns = [
            [
                InlineKeyboardButton("✅ Yes, Track", callback_data=f"track_profile_confirm_yes_{user_id}"),
                InlineKeyboardButton("❌ No, Cancel", callback_data=f"track_profile_confirm_no_{user_id}")
            ]
        ]
        
        await m.reply(
            f"🔍 <b>Confirm Track Profile</b>\n\n"
            f"• <b>Target ID/Username:</b> <code>{html.escape(target_id)}</code>\n"
            f"• <b>Via Account:</b> <code>Session {session_index + 1}</code>\n\n"
            f"Pesan <code>/id {html.escape(target_id)}</code> akan dikirim ke @SangMata_beta_bot.",
            reply_markup=InlineKeyboardMarkup(confirm_btns),
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

    # ✅ BARU: Handle ENV Manager Text Input
    elif user_id in user_env_manager_state:
        state = user_env_manager_state[user_id]
        if text.lower() == "/cancel":
            del user_env_manager_state[user_id]
            await m.reply("❌ ENV Manager dibatalkan.")
            return
            
        action = state['action']
        
        if action == 'add_key':
            # Step 1: Dapatkan key, lalu minta value
            env_key = text.strip().upper()
            
            # Cek jika sudah ada
            existing = await Altruix.config.env_col.find_one({"_id": env_key})
            if existing:
                await m.reply(f"❌ Variabel <code>{env_key}</code> sudah ada di database. Silakan gunakan nama lain atau edit yang sudah ada.", parse_mode=ParseMode.HTML)
                return
                
            user_env_manager_state[user_id]['env_key'] = env_key
            user_env_manager_state[user_id]['action'] = 'add_value'
            
            await m.reply(
                f"<b>➕ Add New ENV (Step 2/2)</b>\n\n"
                f"🔑 <b>Key:</b> <code>{env_key}</code>\n\n"
                f"Sekarang silakan kirimkan <b>NILAI (Value)</b> untuk variabel ini.\n\n"
                f"Ketik <code>/cancel</code> untuk membatalkan.",
                parse_mode=ParseMode.HTML
            )
            return
            
        elif action in ['add_value', 'edit_value', 'edit_value_file']:
            # Final Step: Dapatkan value
            new_val = text
            source_info = ""
            
            if m.document:
                # Handle file upload
                if m.document.file_size > 1024 * 1024: # Limit 1MB for safety
                     await m.reply("❌ File terlalu besar. Maksimal 1MB.")
                     return
                
                download_path = await m.download()
                try:
                    with open(download_path, 'r', encoding='utf-8') as f:
                        new_val = f.read()
                    source_info = f"\n📄 <b>Source:</b> <code>File ({m.document.file_name})</code>"
                except Exception as e:
                    await m.reply(f"❌ Gagal membaca file: {e}")
                    return
                finally:
                    if os.path.exists(download_path):
                        os.remove(download_path)
            
            env_key = state['env_key']
            user_env_manager_state[user_id]['new_value'] = new_val
            
            confirm_btns = [
                [
                    InlineKeyboardButton("✅ Ya, Simpan", callback_data="env_save_confirm_yes"),
                    InlineKeyboardButton("❌ Tidak, Batal", callback_data="env_save_confirm_no")
                ]
            ]
            
            # Preview value
            preview = new_val
            if len(preview) > 1000:
                preview = preview[:1000] + "..."
            
            # Use localized strings for confirmation
            await m.reply(
                Altruix.get_string("env_preview_title") + "\n\n" +
                Altruix.get_string("env_preview_key").format(env_key) + "\n" +
                Altruix.get_string("env_preview_val").format(html.escape(preview)) + "\n" +
                Altruix.get_string("env_preview_info").format(len=len(new_val), name=m.document.file_name if m.document else "Text") +
                "\n\n" + Altruix.get_string("confirm_msg"),
                reply_markup=InlineKeyboardMarkup(confirm_btns),
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
    if not await check_authorization(cb): return
    await cb.answer()
    choice = cb.matches[0].group(1)
    user_id = cb.from_user.id
    
    if choice == "no":
        # Hapus state user
        if user_id in user_bulk_join_state:
            del user_bulk_join_state[user_id]
        
        await edit_cb(cb, 
            text="❌ Bulk join dibatalkan.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Sessions", callback_data="sessions_list_1")]
            ])
        )
        return
    
    # Proses bulk join
    if user_id not in user_bulk_join_state:
        await edit_cb(cb, "❌ Data tidak ditemukan. Silakan ulangi.")
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
        await edit_cb(cb, "❌ No sessions available to join.")
        return
    
    await edit_cb(cb, f"🔄 Starting bulk join for <b>{total_sessions}</b> sessions...\n\n"
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
                await edit_cb(cb, 
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
                    await edit_cb(cb, f"❌ Link invalid/expired. Stopping...")
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
        f"• User: {user_link}\n"
        f"• User ID: <code>{user_id}</code>\n"
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
    
    await edit_cb(cb, 
        text=result_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Sessions", callback_data="sessions_list_1")]
        ]),
        parse_mode=ParseMode.HTML
    )


@Altruix.bot.on_callback_query(filters.regex("bulk_leave_confirm_(yes|no)"))
@log_errors
async def bulk_leave_confirm_handler(c: Client, cb: CallbackQuery):
    """Handler untuk konfirmasi bulk leave"""
    if not await check_authorization(cb): return
    await cb.answer()
    choice = cb.matches[0].group(1)
    user_id = cb.from_user.id
    
    if choice == "no":
        if user_id in user_bulk_leave_state:
            del user_bulk_leave_state[user_id]
        await edit_cb(cb, "❌ Bulk leave dibatalkan.", 
                             reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="sessions_list_1")]]))
        return
    
    if user_id not in user_bulk_leave_state:
        await edit_cb(cb, "❌ Data tidak ditemukan.")
        return
    
    state = user_bulk_leave_state[user_id]
    del user_bulk_leave_state[user_id]
    
    await execute_bulk_leave(c, cb, state['delay'], state['chat_id'])


@Altruix.bot.on_callback_query(filters.regex("bulk_report_reason_(\\d+)_(.*)"))
@log_errors
async def bulk_report_reason_handler(c: Client, cb: CallbackQuery):
    """Handler untuk memilih alasan bulk report"""
    if not await check_authorization(cb): return
    await cb.answer()
    user_id = int(cb.matches[0].group(1))
    reason = cb.matches[0].group(2)
    
    if user_id not in user_bulk_report_state:
        await edit_cb(cb, "❌ Session expired. Silakan ulangi.")
        return
    
    if reason == "custom":
        user_bulk_report_state[user_id]['step'] = 'waiting_custom_reason'
        await edit_cb(cb, "✍️ Silakan ketik alasan report custom Anda:", 
                             reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="sessions_list_1")]]))
        return
    
    user_bulk_report_state[user_id]['reason'] = reason
    user_bulk_report_state[user_id]['step'] = 'confirming'
    
    state = user_bulk_report_state[user_id]
    delay = state['delay']
    total_sessions = len(Altruix.clients)
    
    confirmation_buttons = [
        [
            InlineKeyboardButton("✅ Yes, Report All", callback_data="bulk_report_confirm_yes"),
            InlineKeyboardButton("❌ No, Cancel", callback_data="bulk_report_confirm_no")
        ]
    ]
    
    await edit_cb(cb, 
        text=f"<b>🚩 Confirm Bulk Report</b>\n\n"
             f"• <b>Target:</b> <code>{html.escape(state['target'])}</code>\n"
             f"• <b>Reason:</b> <code>{reason.upper()}</code>\n"
             f"• <b>Delay:</b> <code>{delay} detik</code>\n"
             f"• <b>Total Sessions:</b> <code>{total_sessions}</code>\n\n"
             f"⚠️ <b>WARNING:</b>\n"
             f"• Semua session akan melaporkan target tersebut",
        reply_markup=InlineKeyboardMarkup(confirmation_buttons),
        parse_mode=ParseMode.HTML
    )


@Altruix.bot.on_callback_query(filters.regex("bulk_report_confirm_(yes|no)"))
@log_errors
async def bulk_report_confirm_handler(c: Client, cb: CallbackQuery):
    """Handler untuk konfirmasi bulk report"""
    if not await check_authorization(cb): return
    await cb.answer()
    choice = cb.matches[0].group(1)
    user_id = cb.from_user.id
    
    if choice == "no":
        if user_id in user_bulk_report_state:
            del user_bulk_report_state[user_id]
        await edit_cb(cb, "❌ Bulk report dibatalkan.", 
                             reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="sessions_list_1")]]))
        return
    
    if user_id not in user_bulk_report_state:
        await edit_cb(cb, "❌ Data tidak ditemukan.")
        return
    
    state = user_bulk_report_state[user_id]
    del user_bulk_report_state[user_id]
    
    await execute_bulk_report(c, cb, state['delay'], state['target'], state['reason'])


async def execute_bulk_leave(c: Client, cb: CallbackQuery, delay: float, chat_id: str):
    """Esekusi bulk leave"""
    total = len(Altruix.clients)
    success = 0
    failed = 0
    
    await edit_cb(cb, f"🔄 <b>Bulk Leave in progress...</b>\nTarget: <code>{chat_id}</code>\nTotal: <code>{total}</code> sessions")
    
    for i, client in enumerate(Altruix.clients):
        try:
            await client.leave_chat(chat_id)
            success += 1
        except Exception:
            failed += 1
        
        if i < total - 1:
            await asyncio.sleep(delay)
            await edit_cb(cb, f"🔄 <b>Bulk Leave in progress...</b>\nSuccess: <code>{success}</code>\nFailed: <code>{failed}</code>\nRemaining: <code>{total - (i+1)}</code>")

    await edit_cb(cb, f"✅ <b>Bulk Leave Completed</b>\n\nTarget: <code>{chat_id}</code>\nSuccess: <code>{success}</code>\nFailed: <code>{failed}</code>")


async def execute_bulk_report(c: Client, cb: CallbackQuery, delay: float, target: str, reason: str):
    """Esekusi bulk report"""
    total = len(Altruix.clients)
    success = 0
    failed = 0
    
    await edit_cb(cb, f"🔄 <b>Bulk Report in progress...</b>\nTarget: <code>{target}</code>\nTotal: <code>{total}</code> sessions")
    
    for i, client in enumerate(Altruix.clients):
        try:
            await client.report_peer(target, reason)
            success += 1
        except Exception:
            failed += 1
        
        if i < total - 1:
            await asyncio.sleep(delay)
            await edit_cb(cb, f"🔄 <b>Bulk Report in progress...</b>\nSuccess: <code>{success}</code>\nFailed: <code>{failed}</code>\nRemaining: <code>{total - (i+1)}</code>")

    await edit_cb(cb, f"✅ <b>Bulk Report Completed</b>\n\nTarget: <code>{target}</code>\nSuccess: <code>{success}</code>\nFailed: <code>{failed}</code>")


# ====================== JOIN LOG GROUP FEATURE ======================
@Altruix.bot.on_callback_query(filters.regex("join_log_group_(\\d+)$"))
@log_errors
async def join_log_group_handler(c: Client, cb: CallbackQuery):
    """Handler untuk join log group per session (dengan notifikasi log)"""
    if not await check_authorization(cb): return
    await cb.answer()
    index = int(cb.matches[0].group(1))
    
    if index >= len(Altruix.clients):
        await edit_cb(cb, "Session not found.")
        return
    
    session_client = Altruix.clients[index]
    session_info = getattr(session_client, 'myself', None)
    
    if not session_info:
        try:
            session_info = await session_client.get_me()
        except Exception as e:
            await edit_cb(cb, f"Error getting session info: {str(e)}")
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
                await edit_cb(cb, "❌ Cannot get invite link for log group. Make sure bot is admin.")
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
            
            await edit_cb(cb, "✅ Successfully joined log group!")
            
            # ✅ BARU: Kirim notifikasi ke log group via fungsi
            await send_log_notification(
                c, 'join_log_group', index, cb.from_user, 
                True, None, {'Aksi': 'Join log group berhasil'}
            )
            
        except UserAlreadyParticipant:
            await edit_cb(cb, "ℹ️ This session is already in the log group.")
            # ✅ BARU: Kirim notifikasi ke log group
            await send_log_notification(
                c, 'join_log_group', index, cb.from_user, 
                True, None, {'Aksi': 'Join log group (sudah bergabung)'}
            )
            
        except Exception as e:
            await edit_cb(cb, f"❌ Failed to join log group: {str(e)}")
            
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
        await edit_cb(cb, f"❌ Error: {str(e)}")
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
    if not await check_authorization(cb): return
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
    
    await edit_cb(cb, 
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
    if not await check_authorization(cb): return
    await cb.answer("Operation cancelled.")
    
    user_id = cb.from_user.id
    if user_id in user_confirmation_state:
        del user_confirmation_state[user_id]
    
    await sessions_menu_cb_handler(c, cb)


@Altruix.bot.on_callback_query(filters.regex("export_all_sessions_confirm_yes"))
@log_errors
async def export_all_sessions_confirm_yes_handler(c: Client, cb: CallbackQuery):
    """Handler untuk konfirmasi Yes export all sessions"""
    if not await check_authorization(cb): return
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
    
    await edit_cb(cb, 
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
    if not await check_authorization(cb): return
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
    
    await edit_cb(cb, 
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
    if not await check_authorization(cb): return
    await cb.answer("Operation cancelled.")
    
    user_id = cb.from_user.id
    if user_id in user_confirmation_state:
        del user_confirmation_state[user_id]
    
    await sessions_menu_cb_handler(c, cb)


@Altruix.bot.on_callback_query(filters.regex("export_all_phones_confirm_yes"))
@log_errors
async def export_all_phones_confirm_yes_handler(c: Client, cb: CallbackQuery):
    """Handler untuk konfirmasi Yes export all phones"""
    if not await check_authorization(cb): return
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
    
    await edit_cb(cb, 
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
            f"• User: {user_link}\n"
            f"• User ID: <code>{user_id}</code>\n"
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
            f"• User: {user_link}\n"
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
            f"• User: {user_link}\n"
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
            f"• User: {user_link}\n"
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
            f"• User: {user_link}\n"
            f"• User ID: <code>{user_id}</code>\n"
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
            f"• User: {user_link}\n"
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
            f"• User: {user_link}\n"
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
            f"• User: {user_link}\n"
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
    if not await check_authorization(cb): return
    await cb.answer()
    confirmation_buttons = [
        [
            InlineKeyboardButton("✅ Yes", callback_data="test_ping_all_confirm_yes"),
            InlineKeyboardButton("❌ No", callback_data="test_ping_all_confirm_no")
        ]
    ]
    await edit_cb(cb, 
        text="❓ Are you sure you want to test ping all sessions?",
        reply_markup=InlineKeyboardMarkup(confirmation_buttons)
    )


@Altruix.bot.on_callback_query(filters.regex("test_ping_all_confirm_no"))
@log_errors
async def test_ping_all_cancel_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer("Operation cancelled.")
    await sessions_menu_cb_handler(c, cb)


@Altruix.bot.on_callback_query(filters.regex("test_ping_all_confirm_yes"))
@log_errors
async def test_ping_all_execute_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer("🏓 Testing ping for all sessions...", show_alert=False)
    log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))
    user = cb.from_user
    
    success_count = 0
    failed_count = 0
    total_sessions = len(Altruix.clients) if hasattr(Altruix, 'clients') else 0
    
    if total_sessions == 0:
        await edit_cb(cb, "❌ No sessions available to ping.")
        return

    await edit_cb(cb, f"✅ Starting ping test for <b>{total_sessions}</b> sessions...")
    
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

        await edit_cb(cb, 
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
        f"• User: {user_link}\n"
        f"• Status: <b>{final_status}</b>\n"
        f"• Berhasil: <code>{success_count}</code> akun\n"
        f"• Gagal: <code>{failed_count}</code> akun\n"
        f"• Waktu: <code>{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</code>",
        parse_mode=ParseMode.HTML,
        link_preview_options=LinkPreviewOptions(is_disabled=True)
    )
    
    await edit_cb(cb, 
        f"✅ Ping all test completed!\n"
        f"• Berhasil: <code>{success_count}</code>\n"
        f"• Gagal: <code>{failed_count}</code>\n"
        f"Lihat detail di grup log."
    )


@Altruix.bot.on_callback_query(filters.regex(r"^session_info_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
@iuser_check
async def sessions_info_cb_handler(c: Client, cb: CallbackQuery, index: int = None, callback_page: int = None, button_page: int = 1):
    try:
        await cb.answer()
    except:
        pass
    
    gt = Altruix.get_string
    
    data = cb.matches[0]
    num_groups = len(data.groups())
    
    if index is None:
        index = int(data.group(1))
    if callback_page is None:
        callback_page = int(data.group(2))
    
    # 🕵️ Safe group access for optional button_page
    if button_page == 1 and num_groups >= 3 and data.group(3):
        button_page = int(data.group(3))

    if index >= len(Altruix.clients):
        await edit_cb(cb, "Session not found.")
        return

    session_client = Altruix.clients[index]
    session_info = getattr(session_client, 'myself', None)
    
    if not session_info:
        try:
            session_info = await session_client.get_me()
        except Exception as e:
            await edit_cb(cb, f"Error getting session info: {str(e)}")
            return

    is_premium = getattr(session_info, 'is_premium', False)
    bio = getattr(session_info, 'bio', 'None')
    
    startup_state = await Altruix.config.get_env(f"STARTUP_MSG_{index}")
    if startup_state is None:
        startup_state = "default"
    
    status_map = {
        "off": "❌ OFF",
        "default": "✅ DEFAULT",
        "custom": "✨ CUSTOM"
    }
    startup_status = status_map.get(str(startup_state).lower(), "✅ DEFAULT")

    # ✅ Toggle Disable Button
    is_session_disabled_ = Altruix.is_session_disabled(session_info.id)
    toggle_text = gt("enable_session") if is_session_disabled_ else gt("disable_session")
    toggle_cb = f"toggle_sess_stat_{index}_{callback_page}"

    # All available buttons
    all_buttons = [
        # Account Actions
        InlineKeyboardButton(toggle_text, f"{toggle_cb}_{button_page}"),
        InlineKeyboardButton(gt("refresh_data"), f"gen_conf_refresh_session_info_{index}_{callback_page}_{button_page}"),
        InlineKeyboardButton(gt("unlink_session"), f"unlink_session_{index}_{callback_page}_{button_page}"),
        InlineKeyboardButton(gt("change_name"), f"change_name_menu_{index}_{callback_page}_{button_page}"),
        InlineKeyboardButton(gt("change_bio"), f"gen_conf_change_bio_{index}_{callback_page}_{button_page}"),
        InlineKeyboardButton(gt("change_username"), f"gen_conf_change_username_{index}_{callback_page}_{button_page}"),
        InlineKeyboardButton(gt("change_profile_photo"), f"gen_conf_change_profile_photo_{index}_{callback_page}_{button_page}"),
        InlineKeyboardButton(gt("delete_all_photos"), f"gen_conf_delete_all_profile_photos_{index}_{callback_page}_{button_page}"),
        InlineKeyboardButton(gt("change_login_email"), f"change_login_email_{index}_{callback_page}_{button_page}"),
        
        # Tools & Downloads
        InlineKeyboardButton(gt("download_story"), f"gen_conf_dlstory_session_input_{index}_{callback_page}_{button_page}"),
        InlineKeyboardButton(gt("download_content"), f"gen_conf_dl_content_input_{index}_{callback_page}_{button_page}"),
        InlineKeyboardButton(gt("download_user_photo"), f"gen_conf_dl_uphoto_start_{index}_{callback_page}_{button_page}"),
        InlineKeyboardButton(gt("download_my_photo"), f"gen_conf_send_profile_photo_{index}_{callback_page}_{button_page}"),
        
        # Info & Security
        InlineKeyboardButton(gt("export_session"), f"gen_conf_export_session_{index}_{callback_page}_{button_page}"),
        InlineKeyboardButton(gt("export_phone"), f"gen_conf_export_phone_{index}_{callback_page}_{button_page}"),
        InlineKeyboardButton(gt("test_ping"), f"gen_conf_test_ping_{index}_{callback_page}_{button_page}"),
        InlineKeyboardButton(gt("track_profile"), f"track_profile_start_{index}_{callback_page}_{button_page}"),
        InlineKeyboardButton(gt("check_limit"), f"check_limit_confirm_{index}_{callback_page}_{button_page}"),
        InlineKeyboardButton(gt("view_sessions"), f"gen_conf_view_all_sessions_{index}_{callback_page}_{button_page}"),
        
        # Group & Msg
        InlineKeyboardButton(gt("join_group"), f"gen_conf_join_chat_input_{index}_{callback_page}_{button_page}"),
        InlineKeyboardButton(gt("leave_group"), f"gen_conf_leave_chat_input_{index}_{callback_page}_{button_page}"),
        InlineKeyboardButton(gt("purge_my_msg"), f"gen_conf_purge_msg_start_{index}_{callback_page}_{button_page}"),
        InlineKeyboardButton(gt("global_purgeme"), f"gpurgeme_menu_{index}_{callback_page}_{button_page}"),
        InlineKeyboardButton(gt("send_message"), f"gen_conf_send_message_input_{index}_{callback_page}_{button_page}"),
        InlineKeyboardButton(gt("chat_stats"), f"gen_conf_chat_stats_scan_{index}_{callback_page}_{button_page}"),
        
        # Logs & Monitoring
        InlineKeyboardButton(gt("pm_logger_control"), f"pml_menu_{index}_{callback_page}_{button_page}"),
        InlineKeyboardButton(gt("mention_control"), f"mnt_menu_{index}_{callback_page}_{button_page}"),
        InlineKeyboardButton(gt("join_logger_control"), f"joinl_menu_{index}_{callback_page}_{button_page}"),
        InlineKeyboardButton(gt("cmd_logger_control"), f"cmdl_menu_{index}_{callback_page}_{button_page}"),
        InlineKeyboardButton(gt("cmd_settings"), f"cmd_settings_menu_{index}_{callback_page}_{button_page}"),
        InlineKeyboardButton(gt("recent_messages"), f"gen_conf_recent_messages_menu_{index}_{callback_page}_{button_page}"),
        InlineKeyboardButton(gt("view_mentions"), f"gen_conf_view_mentions_menu_{index}_{callback_page}_{button_page}"),
        InlineKeyboardButton(gt("join_log_group"), f"join_log_group_{index}_{callback_page}_{button_page}"),
        
        # Advanced & Settings
        InlineKeyboardButton(f"🚀 Startup: {startup_status}", f"startup_menu_{index}_{callback_page}_{button_page}"),
        InlineKeyboardButton(gt("laucreate_menu"), f"laucreate_menu_{index}_{callback_page}_{button_page}"),
        # Removed Edit Startup Msg
        InlineKeyboardButton(gt("privacy_security"), f"privacy_menu_{index}_{callback_page}_{button_page}"),
        InlineKeyboardButton(f"🚀 Help Info: {await Altruix.config.get_env(f'HELP_INFO_{index}') or 'default'}", f"help_info_menu_{index}_{callback_page}_{button_page}"),
        # Removed Edit Help Msg
        InlineKeyboardButton(gt("eval_python"), f"eval_session_{index}_{callback_page}_{button_page}"),
        InlineKeyboardButton(gt("exec_terminal"), f"exec_session_{index}_{callback_page}_{button_page}"),
        InlineKeyboardButton(gt("custom_bot"), f"custom_bot_menu_{index}_{callback_page}_{button_page}"),
        InlineKeyboardButton(gt("cache_log_menu"), f"cache_log_menu_{index}_{callback_page}_{button_page}"),
        InlineKeyboardButton(gt("sudo_settings"), f"sudo_settings_menu_{index}_{callback_page}_{button_page}"),
        InlineKeyboardButton(gt("prefix_settings"), f"prefix_settings_menu_{index}_{callback_page}_{button_page}"),
    ]

    # Pagination Logic
    buttons_per_page = 10
    total_pages = (len(all_buttons) + buttons_per_page - 1) // buttons_per_page

    custom_bot_username = Altruix.bot_manager.get_bot_username(session_info.id)
    custom_bot_info = f"🤖 <b>Custom Bot:</b> <spoiler>@{custom_bot_username}</spoiler>\n" if custom_bot_username else ""

    # Count plugins by category
    ub_count = sum(1 for cat in Altruix.plugin_categories.values() if cat == "userbot")
    bot_count = sum(1 for cat in Altruix.plugin_categories.values() if cat == "bot")
    xtra_count = sum(1 for cat in Altruix.plugin_categories.values() if cat == "other")
    total_modules = ub_count + bot_count + xtra_count
    
    # Count Xtra-Features (inline buttons)
    xtra_features_count = len(all_buttons)

    txt = (
        f"{gt('session_info_title')}\n\n"
        f"👤 <b>User:</b> <a href='tg://user?id={session_info.id}'>{html.escape((session_info.first_name or '') + ' ' + (session_info.last_name or '')).strip() or 'No name'}</a>\n"
        f"🆔 <b>ID:</b> <spoiler>{session_info.id}</spoiler>\n"
        f"✍️ <b>Bio:</b> <code>{html.escape(bio or 'None')}</code>\n"
        f"💠 <b>DC:</b> <code>{session_info.dc_id or 'N/A'}</code>\n"
        f"❤️‍🔥 <b>Premium:</b> <code>{'Yes' if is_premium else 'No'}</code>\n"
        f"📊 <b>Session Index:</b> <code>{index + 1}</code>\n"
        f"🏷 <b>Username:</b> <spoiler>@{session_info.username or 'None'}</spoiler>\n"
        f"{custom_bot_info}"
        f"⚙️ <b>Xtra-Features:</b> <code>{xtra_features_count}</code>\n"
        f"🔘 <b>Total Modul:</b> <code>{total_modules}</code> <i>(UB mod {ub_count}, Bot mod {bot_count}, Xtra mod {xtra_count})</i>\n\n"
        f"<i>Manage this session ({button_page}/{total_pages}):</i>"
    )
    
    start = (button_page - 1) * buttons_per_page
    end = start + buttons_per_page
    current_page_buttons = all_buttons[start:end]
    
    # Render buttons in 2 columns
    kb_buttons = []
    for i in range(0, len(current_page_buttons), 2):
        kb_buttons.append(current_page_buttons[i:i+2])
        
    # Navigation Buttons
    nav_row = []
    if button_page > 1:
        nav_row.append(InlineKeyboardButton(gt("prev"), f"session_info_{index}_{callback_page}_{button_page-1}"))
    
    if button_page < total_pages:
        nav_row.append(InlineKeyboardButton(gt("next"), f"session_info_{index}_{callback_page}_{button_page+1}"))
        
    if nav_row:
        kb_buttons.append(nav_row)
        
    # Final row: Back
    kb_buttons.append([InlineKeyboardButton(f"{gt('back')} [{callback_page}]", f"sessions_list_{callback_page}")])

    await edit_cb(cb, 
        text=txt,
        reply_markup=InlineKeyboardMarkup(kb_buttons),
        parse_mode=ParseMode.HTML
    )


@Altruix.bot.on_callback_query(filters.regex(r"change_login_email_(\d+)_(\d+)(?:_(\d+))?"))
@iuser_check
@log_errors
async def change_login_email_handler(c: Client, cb: CallbackQuery):
    """Handler awal untuk ganti login email (Review email saat ini)"""
    gt = Altruix.get_string
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    if index >= len(Altruix.clients):
        await edit_cb(cb, "❌ Session tidak ditemukan.")
        return

    session_client = Altruix.clients[index]
    
    await edit_cb(cb, gt("fetching_security_info"))
    
    try:
        # Ambil pattern email saat ini
        pwd_info = await session_client.invoke(raw.functions.account.GetPassword())
        email_pattern = getattr(pwd_info, "login_email_pattern", None)
        has_password = getattr(pwd_info, "has_password", False)
        
        email_display = f"<code>{html.escape(email_pattern)}</code>" if email_pattern else f"<i>{gt('inactive')}</i>"
        
        text = (
            f"{gt('change_login_email_title')}\n\n"
            f"{gt('current_email').format(email_display)}\n"
            f"{gt('2fa_password').format(gt('active') if has_password else gt('inactive'))}\n\n"
            f"{gt('security_note_email')}\n\n"
            f"{gt('confirm_continue')}"
        )
        
        buttons = [
            [
                InlineKeyboardButton(gt("yes_continue"), f"change_email_start_{index}_{page}_{button_page}"),
                InlineKeyboardButton(gt("cancel"), f"session_info_{index}_{page}_{button_page}")
            ]
        ]
        
        await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
        
    except FloodWait as e:
        await edit_cb(cb, f"⏳ FloodWait: {e.value}s")
    except Exception as e:
        await edit_cb(cb, f"❌ {str(e)}")
        Altruix.log(f"Error in change_login_email_handler: {e}", level=logging.ERROR)


@Altruix.bot.on_callback_query(filters.regex(r"change_email_start_(\d+)_(\d+)(?:_(\d+))?"))
@iuser_check
@log_errors
async def change_email_start_handler(c: Client, cb: CallbackQuery):
    """Handler untuk memulai input email baru"""
    gt = Altruix.get_string
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    user_id = cb.from_user.id
    
    if index >= len(Altruix.clients): return
    session_client = Altruix.clients[index]
    
    # Prompt email baru
    await edit_cb(cb, 
        gt("change_email_step_1"),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(gt("back"), f"session_info_{index}_{page}_{button_page}")]])
    )
    
    try:
        # Tunggu input email
        msg_email = await c.listen(filters.chat(user_id) & filters.text, timeout=120)
        new_email = msg_email.text.strip().lower()
        
        if new_email == "cancel":
            await msg_email.delete()
            await edit_cb(cb, gt("operation_cancelled"))
            await asyncio.sleep(2)
            await sessions_info_cb_handler(c, cb)
            return

        # Validasi format email sederhana
        if "@" not in new_email or "." not in new_email:
            await msg_email.reply(f"❌ {gt('email_invalid')}")
            return

        await msg_email.delete()
        await edit_cb(cb, gt("sending_code_to").format(html.escape(new_email)))
        
        # Kirim kode verifikasi
        try:
            # Menggunakan SendVerifyEmailCode karena SetLoginEmailAddress tidak tersedia di versi ini
            # EmailVerifyPurposeLoginChange tidak mengambil argumen di Kurigram 2.2.18
            purpose = raw.types.EmailVerifyPurposeLoginChange()
            await session_client.invoke(
                raw.functions.account.SendVerifyEmailCode(
                    email=new_email,
                    purpose=purpose
                )
            )
            
            # Step 2: Minta kode
            await edit_cb(cb, 
                gt("code_sent_step_2").format(html.escape(new_email)),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(gt("back"), f"session_info_{index}_{page}_{button_page}")]])
            )
            
            msg_code = await c.listen(filters.chat(user_id) & filters.text, timeout=180)
            verify_code = msg_code.text.strip().replace("-", "")
            
            if verify_code.lower() == "cancel":
                await msg_code.delete()
                await edit_cb(cb, gt("operation_cancelled"))
                return

            await msg_code.delete()
            await edit_cb(cb, gt("verifying_code"))
            
            # Verifikasi email
            # Kurigram 2.2.18 requires verification as EmailVerification object
            verification = raw.types.EmailVerificationCode(code=verify_code)
            await session_client.invoke(
                raw.functions.account.VerifyEmail(
                    purpose=purpose,
                    verification=verification
                )
            )
            
            await edit_cb(cb, 
                gt("change_email_success").format(html.escape(new_email)),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(gt("back"), f"session_info_{index}_{page}_{button_page}")]])
            )
            
            # Log Notification
            await send_log_notification(
                c, 'change_login_email', index, cb.from_user,
                True, None, {'Email Baru': new_email}
            )
            
        except RPCError as e:
            error_text = str(e)
            if "EMAIL_INVALID" in error_text:
                error_text = gt("email_invalid")
            elif "EMAIL_ID_INVALID" in error_text:
                error_text = gt("verification_code_invalid")
            
            await edit_cb(cb, f"❌ <b>Gagal:</b> {error_text}")
            await send_log_notification(
                c, 'change_login_email', index, cb.from_user,
                False, str(e), {'Email Baru': new_email}
            )
            
    except (asyncio.TimeoutError, ListenerTimeout):
        await edit_cb(cb, gt("timeout_retry"))
    except Exception as e:
        await edit_cb(cb, f"❌ <b>Error:</b> {str(e)}")
        Altruix.log(f"Error in change_email_start_handler: {e}", level=logging.ERROR)


# ✅ HANDLER BARU: Menu Ganti Nama
@Altruix.bot.on_callback_query(filters.regex(r"change_name_menu_(\d+)_(\d+)(?:_(\d+))?"))
@iuser_check
@log_errors
async def change_name_menu_handler(c: Client, cb: CallbackQuery):
    """Handler untuk menu ganti nama (First/Last)"""
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    buttons = [
        [
            InlineKeyboardButton(gt("first_name"), f"gen_conf_change_first_name_{index}_{page}_{button_page}"),
            InlineKeyboardButton(gt("last_name"), f"gen_conf_change_last_name_{index}_{page}_{button_page}"),
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data=f"session_info_{index}_{page}_{button_page}"),
        ]
    ]
    
    await edit_cb(cb, 
        text="<b>✏️ Ganti Nama</b>\n\n"
             "Pilih bagian nama yang ingin Anda ubah:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )


# ✅ HANDLER BARU: Download Content Input
@Altruix.bot.on_callback_query(filters.regex(r"^dl_content_input_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def dl_content_input_handler(c: Client, cb: CallbackQuery):
    """Menerima input link pesan untuk didownload/forward"""
    if not await check_authorization(cb): return
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    if index >= len(Altruix.clients):
        await cb.answer("❌ Session tidak ditemukan.", show_alert=True)
        return

    session_client = Altruix.clients[index]
    session_info = getattr(session_client, 'myself', None) or await session_client.get_me()
    
    await edit_cb(cb, 
        f"📥 <b>Download Konten</b>\n\n"
        f"Akun pengeksekusi: <b>{html.escape(session_info.first_name)}</b>\n\n"
        f"Silakan kirim <b>Link Pesan</b> (misal: <code>https://t.me/username/123</code>).\n"
        f"Konten akan dikirim ke <b>Altruix Log Group</b>.\n\n"
        f"Ketik <code>cancel</code> untuk membatalkan.",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(gt("cancel"), f"session_info_{index}_{page}_{button_page}")]])
    )
    
    try:
        user_id = cb.from_user.id
        msg = await c.listen(filters.chat(user_id) & filters.text, timeout=120)
        
        if msg.text.lower() == 'cancel':
            await msg.delete()
            await edit_cb(cb, "❌ Dibatalkan.")
            await asyncio.sleep(2)
            await sessions_info_cb_handler(c, cb)
            return
            
        link = msg.text.strip()
        await msg.delete()
        
        await edit_cb(cb, "🔄 <b>Sedang memproses...</b>")
        await process_download_content(c, cb, session_client, link, index, page)
        
    except (asyncio.TimeoutError, ListenerTimeout):
        await edit_cb(cb, "⏳ Waktu habis. Silakan coba lagi.")
    except Exception as e:
        await edit_cb(cb, f"❌ Error: {str(e)}")


async def process_download_content(c, cb, session_client, link, index, page):
    """Helper untuk memproses download konten dari link"""
    try:
        # Simple link parsing
        if "t.me/" not in link:
            await edit_cb(cb, "❌ <b>Link tidak valid!</b>")
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
            await edit_cb(cb, "❌ <b>Pesan tidak ditemukan!</b>")
            return

        # Attempt to copy first
        try:
            await msg.copy(log_chat_id)
            await edit_cb(cb, "✅ <b>Berhasil!</b> Konten telah disalin ke Log Group.")
        except Exception:
            # Fallback for restricted: Download and Upload
            await edit_cb(cb, "🔄 <b>Copy gagal, mencoba Bypass (Download & Upload)...</b>")
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
                    
                    await edit_cb(cb, "✅ <b>Bypass Berhasil!</b> Konten telah diupload ke Log Group.")
                finally:
                    if os.path.exists(file_path):
                        os.remove(file_path)
            else:
                # Text only?
                if msg.text:
                    await c.send_message(log_chat_id, f"📥 <b>Text Content:</b>\n\n{msg.text}")
                    await edit_cb(cb, "✅ <b>Berhasil!</b> Teks telah disalin ke Log Group.")
                else:
                    await edit_cb(cb, "❌ <b>Gagal mendownload media.</b>")

        # Log
        await send_log_notification(
            c, 'download_content', index, cb.from_user,
            True, None, {'Link': link}
        )

    except Exception as e:
        await edit_cb(cb, f"❌ <b>Gagal:</b> {str(e)}")
        await send_log_notification(
            c, 'download_content', index, cb.from_user,
            False, str(e), {'Link': link}
        )
    
    await asyncio.sleep(3)
    await sessions_info_cb_handler(c, cb)


# ✅ HANDLER BARU: Menu Pesan Terbaru
@Altruix.bot.on_callback_query(filters.regex(r"recent_messages_menu_(\d+)_(\d+)(?:_(\d+))?"))
@iuser_check
@log_errors
async def recent_messages_menu_handler(c: Client, cb: CallbackQuery):
    """Handler untuk menu pesan terbaru"""
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    # Tampilkan pilihan jumlah pesan
    buttons = [
        [
            InlineKeyboardButton("3 pesan", callback_data=f"recent_messages_quick_{index}_{page}_3_{button_page}"),
            InlineKeyboardButton("6 pesan", callback_data=f"recent_messages_quick_{index}_{page}_6_{button_page}"),
        ],
        [
            InlineKeyboardButton("9 pesan", callback_data=f"recent_messages_quick_{index}_{page}_9_{button_page}"),
            InlineKeyboardButton("11 pesan", callback_data=f"recent_messages_quick_{index}_{page}_11_{button_page}"),
        ],
        [
            InlineKeyboardButton("📝 Custom jumlah", callback_data=f"recent_messages_custom_{index}_{page}_{button_page}"),
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data=f"session_info_{index}_{page}_{button_page}"),
        ]
    ]
    
    await edit_cb(cb, 
        text="<b>📨 Pesan Terbaru</b>\n\n"
             "Pilih jumlah pesan terbaru yang akan ditampilkan (dari chat private):\n\n"
             "⚠️ <b>Note:</b>\n"
             "• Hanya menampilkan pesan dari chat private\n"
             "• Pesan diurutkan berdasarkan waktu terbaru",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )


# ✅ HANDLER BARU: Pesan Terbaru Quick Select
@Altruix.bot.on_callback_query(filters.regex(r"recent_messages_quick_(\d+)_(\d+)_(\d+)(?:_(\d+))?"))
@log_errors
async def recent_messages_quick_handler(c: Client, cb: CallbackQuery):
    """Handler untuk pesan terbaru quick select"""
    if not await check_authorization(cb): return
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    count = int(cb.matches[0].group(3))
    button_page = int(cb.matches[0].group(4)) if len(cb.matches[0].groups()) >= 4 and cb.matches[0].group(4) else 1
    
    user_id = cb.from_user.id
    user_recent_messages_state[user_id] = {
        'session_index': index,
        'page': page,
        'button_page': button_page,
        'step': 'waiting_count',
        'count': count
    }
    
    # Langsung proses
    await edit_cb(cb, f"🔄 Mengambil {count} pesan terbaru...")
    
    try:
        if index >= len(Altruix.clients):
            await edit_cb(cb, "❌ Session tidak ditemukan.")
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
            await edit_cb(cb, "❌ Tidak ada pesan terbaru ditemukan.")
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
            [InlineKeyboardButton("🔙 Back", callback_data=f"session_info_{index}_{page}_{button_page}")]
        ]
        
        await edit_cb(cb, 
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
        await edit_cb(cb, f"❌ {error_msg}")
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
@Altruix.bot.on_callback_query(filters.regex(r"recent_messages_custom_(\d+)_(\d+)(?:_(\d+))?"))
@log_errors
async def recent_messages_custom_handler(c: Client, cb: CallbackQuery):
    """Handler untuk pesan terbaru custom jumlah"""
    if not await check_authorization(cb): return
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    user_id = cb.from_user.id
    user_recent_messages_state[user_id] = {
        'session_index': index,
        'page': page,
        'button_page': button_page,
        'step': 'waiting_count'
    }
    
    await edit_cb(cb, 
        text="<b>📨 Pesan Terbaru (Custom)</b>\n\n"
             "Silakan kirim jumlah pesan yang ingin ditampilkan (1-50):\n\n"
             "❌ <b>Cancel:</b> Ketik /cancel",
        parse_mode=ParseMode.HTML
    )


# ✅ HANDLER BARU: Menu Lihat Mention
@Altruix.bot.on_callback_query(filters.regex(r"view_mentions_menu_(\d+)_(\d+)(?:_(\d+))?"))
@iuser_check
@log_errors
async def view_mentions_menu_handler(c: Client, cb: CallbackQuery):
    """Handler untuk menu lihat mention"""
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    user_id = cb.from_user.id
    user_mentions_state[user_id] = {
        'session_index': index,
        'page': page,
        'button_page': button_page,
        'step': 'waiting_group'
    }
    
    await edit_cb(cb, 
        text="<b>🔔 Lihat Mention</b>\n\n"
             "Silakan kirim username atau ID group (contoh: @username atau -1001234567890):\n\n"
             "❌ <b>Cancel:</b> Ketik /cancel",
        parse_mode=ParseMode.HTML
    )


# ✅ HANDLER BARU: Pilihan Jumlah Mention
@Altruix.bot.on_callback_query(filters.regex(r"mention_count_(\d+)_(\d+)(?:_(\d+))?"))
@log_errors
async def mention_count_handler(c: Client, cb: CallbackQuery):
    """Handler untuk pilihan jumlah mention"""
    if not await check_authorization(cb): return
    await cb.answer()
    user_id = int(cb.matches[0].group(1))
    count = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    if user_id not in user_mentions_state:
        await edit_cb(cb, "❌ Session tidak ditemukan atau state expired.")
        return
    
    state = user_mentions_state[user_id]
    index = state['session_index']
    page = state.get('page', 1)
    group = state.get('group')
    
    if index >= len(Altruix.clients):
        await edit_cb(cb, "❌ Session tidak ditemukan.")
        if user_id in user_mentions_state:
            del user_mentions_state[user_id]
        return
    
    session_client = Altruix.clients[index]
    session_info = getattr(session_client, 'myself', None) or await session_client.get_me()
    
    await edit_cb(cb, f"🔔 Mencari mention di {group}...")
    
    try:
        # Resolve group
        try:
            chat = await session_client.get_chat(group)
        except Exception as e:
            await edit_cb(cb, f"❌ Gagal mendapatkan group: {str(e)}")
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
            await edit_cb(cb, f"❌ Tidak ditemukan mention untuk @{session_info.username} di group {chat.title}.")
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
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"session_info_{index}_{page}_{button_page}")])
        
        await edit_cb(cb, 
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
        await edit_cb(cb, f"❌ Gagal mencari mention: {str(e)}")
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
    if not await check_authorization(cb): return
    user_id = int(cb.matches[0].group(1))
    if user_id in user_mentions_state:
        del user_mentions_state[user_id]
    await cb.answer("Cancelled.")
    await edit_cb(cb, "❌ Lihat mention dibatalkan.")


# ✅ HANDLER BARU: Kirim Foto Profil
@Altruix.bot.on_callback_query(filters.regex(r"send_profile_photo_(\d+)_(\d+)(?:_(\d+))?"))
@log_errors
async def send_profile_photo_handler(c: Client, cb: CallbackQuery):
    """Handler untuk mengirim foto profil"""
    if not await check_authorization(cb): return
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
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
            await edit_cb(cb, "❌ Akun ini tidak memiliki foto profil.")
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
        
        await edit_cb(cb, 
            f"✅ Foto profil telah dikirim ke pesan pribadi Anda.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}")]])
        )
        
        # Kirim log
        await send_log_notification(
            c, 'send_profile_photo', index, cb.from_user,
            True, None, {'Aksi': 'Kirim foto profil berhasil'}
        )
        
    except FloodWait as e:
        await edit_cb(cb, f"⏳ FloodWait: Tunggu {e.value} detik.")
        await send_log_notification(
            c, 'send_profile_photo', index, cb.from_user,
            False, f"FloodWait {e.value}s", {'Aksi': 'Kirim foto profil gagal'}
        )
    except Exception as e:
        await edit_cb(cb, f"❌ Gagal mengirim foto profil: {str(e)}")
        Altruix.log(f"Error send_profile_photo session {index}: {e}", level=logging.ERROR)
        await send_log_notification(
            c, 'send_profile_photo', index, cb.from_user,
            False, str(e), {'Aksi': 'Kirim foto profil gagal'}
        )

# ✅ HANDLER BARU: Leave Chat (Group/Channel)
@Altruix.bot.on_callback_query(filters.regex(r"leave_chat_input_(\d+)_(\d+)(?:_(\d+))?"))
@log_errors
async def leave_chat_input_handler(c: Client, cb: CallbackQuery):
    """Menerima input chat_id atau username untuk leave"""
    if not await check_authorization(cb): return
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    if index >= len(Altruix.clients):
        await cb.answer("❌ Session tidak ditemukan.", show_alert=True)
        return

    session_client = Altruix.clients[index]
    session_info = getattr(session_client, 'myself', None) or await session_client.get_me()
    
    prompt = await edit_cb(cb, 
        f"🏃 <b>Leave Group/Channel</b>\n\n"
        f"Akun: <b>{html.escape(session_info.first_name)}</b>\n\n"
        f"Silakan kirim <b>Username</b> (misal: @groupname) atau <b>Chat ID</b> grup yang ingin ditinggalkan.\n\n"
        f"Ketik <code>cancel</code> untuk membatalkan.",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", f"session_info_{index}_{page}_{button_page}")]])
    )
    
    try:
        user_id = cb.from_user.id
        msg = await c.listen(filters.chat(user_id) & filters.text, timeout=120)
        
        if msg.text.lower() == 'cancel':
            await msg.delete()
            await edit_cb(cb, "❌ Dibatalkan.")
            await asyncio.sleep(2)
            await sessions_info_cb_handler(c, cb)
            return
            
        target = msg.text.strip()
        await msg.delete()
        
        # Konfirmasi
        confirm_buttons = [
            [
                InlineKeyboardButton("✅ Ya, Keluar Sekarang", f"leave_chat_confirm_{index}_{page}_{button_page}_{target}"),
                InlineKeyboardButton("❌ Tidak", f"session_info_{index}_{page}_{button_page}")
            ]
        ]
        
        await edit_cb(cb, 
            f"❓ <b>Konfirmasi Keluar</b>\n\n"
            f"Apakah Anda yakin ingin menyuruh akun <b>{html.escape(session_info.first_name)}</b> keluar dari <code>{target}</code>?",
            reply_markup=InlineKeyboardMarkup(confirm_buttons),
            parse_mode=ParseMode.HTML
        )
        
    except (asyncio.TimeoutError, ListenerTimeout):
        await edit_cb(cb, "⏳ Waktu habis. Silakan coba lagi.")
    except Exception as e:
        await edit_cb(cb, f"❌ Error: {str(e)}")

@Altruix.bot.on_callback_query(filters.regex(r"leave_chat_confirm_(\d+)_(\d+)_(\d+)_(.+)"))
@log_errors
async def leave_chat_confirm_handler(c: Client, cb: CallbackQuery):
    """Eksekusi leave chat setelah konfirmasi"""
    if not await check_authorization(cb): return
    await cb.answer("Memproses...", show_alert=False)
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3))
    target = cb.matches[0].group(4)
    
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
        
        await edit_cb(cb, f"✅ Berhasil keluar dari <b>{html.escape(str(chat_title))}</b>")
        
        # Log
        await send_log_notification(
            c, 'leave_chat', index, cb.from_user,
            True, None, {'Target': target, 'Title': chat_title}
        )
        
        await asyncio.sleep(3)
        await sessions_info_cb_handler(c, cb)
        
    except Exception as e:
        await edit_cb(cb, f"❌ Gagal keluar dari {target}: {str(e)}")
        await send_log_notification(
            c, 'leave_chat', index, cb.from_user,
            False, str(e), {'Target': target}
        )

# ✅ HANDLER BARU: Send Message Direct
@Altruix.bot.on_callback_query(filters.regex(r"send_message_input_(\d+)_(\d+)(?:_(\d+))?"))
@log_errors
async def send_message_input_handler(c: Client, cb: CallbackQuery):
    """Menerima input target dan teks pesan"""
    if not await check_authorization(cb): return
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    if index >= len(Altruix.clients):
        await cb.answer("❌ Session tidak ditemukan.", show_alert=True)
        return

    session_client = Altruix.clients[index]
    session_info = getattr(session_client, 'myself', None) or await session_client.get_me()
    
    await edit_cb(cb, 
        f"✉️ <b>Send Message Direct</b>\n\n"
        f"Akun pengirim: <b>{html.escape(session_info.first_name)}</b>\n\n"
        f"Silakan kirim <b>Target</b> (Username @... atau ID).\n"
        f"Ketik <code>cancel</code> untuk membatalkan.",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", f"session_info_{index}_{page}_{button_page}")]])
    )
    
    try:
        user_id = cb.from_user.id
        msg_target = await c.listen(filters.chat(user_id) & filters.text, timeout=60)
        
        if msg_target.text.lower() == 'cancel':
            await msg_target.delete()
            await edit_cb(cb, "❌ Dibatalkan.")
            await asyncio.sleep(2)
            await sessions_info_cb_handler(c, cb)
            return
            
        target = msg_target.text.strip()
        await msg_target.delete()
        
        # Minta isi pesan
        await edit_cb(cb, 
            f"✉️ <b>Send Message Direct</b>\n\n"
            f"Target: <code>{target}</code>\n\n"
            f"Sekarang kirim <b>Pesan</b> yang ingin dikirim.\n"
            f"Ketik <code>cancel</code> untuk membatalkan.",
            parse_mode=ParseMode.HTML
        )
        
        msg_text = await c.listen(filters.chat(user_id) & filters.text, timeout=120)
        
        if msg_text.text.lower() == 'cancel':
            await msg_text.delete()
            await edit_cb(cb, "❌ Dibatalkan.")
            return
            
        text_to_send = msg_text.text
        await msg_text.delete()
        
        # Konfirmasi
        confirm_buttons = [
            [
                InlineKeyboardButton("✅ Ya, Kirim Sekarang", f"send_msg_confirm_{index}_{page}"),
                InlineKeyboardButton("❌ Tidak", f"session_info_{index}_{page}_{button_page}")
            ]
        ]
        
        # Simpan pesan sementara di state (atau bisa di callback data jika pendek, tapi mending di state)
        # Untuk simplicity di sini saya pakai temp state
        user_limit_check_state[user_id] = {'target': target, 'text': text_to_send}
        
        await edit_cb(
            cb,
            text=f"❓ <b>Konfirmasi Kirim Pesan</b>\n\n"
            f"<b>Pengirim:</b> {html.escape(session_info.first_name)}\n"
            f"<b>Target:</b> <code>{target}</code>\n"
            f"<b>Pesan:</b>\n<i>{html.escape(text_to_send[:100])}{'...' if len(text_to_send) > 100 else ''}</i>\n\n"
            f"Apakah Anda yakin?",
            reply_markup=InlineKeyboardMarkup(confirm_buttons)
        )
        
    except (asyncio.TimeoutError, ListenerTimeout):
        await edit_cb(cb, "⏳ Waktu habis. Silakan coba lagi.")
    except Exception as e:
        await edit_cb(cb, f"❌ Error: {str(e)}")

@Altruix.bot.on_callback_query(filters.regex(r"send_msg_confirm_(\d+)_(\d+)"))
@log_errors
async def send_msg_confirm_handler(c: Client, cb: CallbackQuery):
    """Eksekusi kirim pesan setelah konfirmasi"""
    if not await check_authorization(cb): return
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
        await edit_cb(cb, f"✅ Pesan berhasil dikirim ke <code>{target}</code>")
        
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
        await edit_cb(cb, f"❌ Gagal mengirim pesan ke {target}: {str(e)}")
        await send_log_notification(
            c, 'send_direct_message', index, cb.from_user,
            False, str(e), {'Target': target}
        )


# ✅ HANDLER BARU: Ganti Nama Depan dengan konfirmasi
@Altruix.bot.on_callback_query(filters.regex(r"change_first_name_(\d+)_(\d+)"))
@iuser_check
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
    
    await edit_cb(
        cb,
        text="✏️ <b>Ganti Nama Depan</b>\n\n"
             "Silakan kirim nama depan baru untuk akun ini.\n\n"
             "⚠️ <b>Note:</b>\n"
             "• Nama depan maksimal 64 karakter\n"
             "• Tidak boleh mengandung karakter khusus\n\n"
             "❌ <b>Cancel:</b> Kirim /cancel"
    )


# ✅ HANDLER BARU: Ganti Nama Belakang dengan konfirmasi
@Altruix.bot.on_callback_query(filters.regex(r"change_last_name_(\d+)_(\d+)"))
@log_errors
async def change_last_name_handler(c: Client, cb: CallbackQuery):
    """Handler untuk mengganti nama belakang (dengan konfirmasi)"""
    if not await check_authorization(cb): return
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    
    user_id = cb.from_user.id
    user_profile_edit_state[user_id] = {
        'action': 'change_last_name',
        'session_index': index,
        'page': page
    }
    
    await edit_cb(
        cb,
        text="✏️ <b>Ganti Nama Belakang</b>\n\n"
             "Silakan kirim nama belakang baru untuk akun ini.\n"
             "Kirim 'kosong' atau string kosong untuk menghapus nama belakang.\n\n"
             "⚠️ <b>Note:</b>\n"
             "• Nama belakang maksimal 64 karakter\n"
             "• Kosongkan untuk menghapus nama belakang\n\n"
             "❌ <b>Cancel:</b> Kirim /cancel"
    )


# ✅ HANDLER BARU: Ganti Bio dengan konfirmasi
@Altruix.bot.on_callback_query(filters.regex(r"change_bio_(\d+)_(\d+)(?:_(\d+))?"))
@log_errors
async def change_bio_handler(c: Client, cb: CallbackQuery):
    """Handler untuk mengganti bio (dengan konfirmasi)"""
    if not await check_authorization(cb): return
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    user_id = cb.from_user.id
    user_profile_edit_state[user_id] = {
        'action': 'change_bio',
        'session_index': index,
        'page': page,
        'button_page': button_page
    }
    
    await edit_cb(
        cb,
        text="📝 <b>Ganti Bio</b>\n\n"
             "Silakan kirim bio baru untuk akun ini.\n"
             "Maksimal 70 karakter.\n\n"
             "⚠️ <b>Note:</b>\n"
             "• Bio akan tampil di profil\n"
             "• Bisa berisi emoji dan link\n\n"
             "❌ <b>Cancel:</b> Kirim /cancel"
    )


# ✅ HANDLER BARU: Ganti Username dengan konfirmasi
@Altruix.bot.on_callback_query(filters.regex(r"change_username_(\d+)_(\d+)(?:_(\d+))?"))
@log_errors
async def change_username_handler(c: Client, cb: CallbackQuery):
    """Handler untuk mengganti username (dengan konfirmasi)"""
    if not await check_authorization(cb): return
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    user_id = cb.from_user.id
    user_profile_edit_state[user_id] = {
        'action': 'change_username',
        'session_index': index,
        'page': page,
        'button_page': button_page
    }
    
    await edit_cb(cb, 
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
@Altruix.bot.on_callback_query(filters.regex(r"change_profile_photo_(\d+)_(\d+)(?:_(\d+))?"))
@log_errors
async def change_profile_photo_handler(c: Client, cb: CallbackQuery):
    """Handler untuk mengganti foto profil (dengan konfirmasi)"""
    if not await check_authorization(cb): return
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    user_id = cb.from_user.id
    user_profile_edit_state[user_id] = {
        'action': 'change_profile_photo',
        'session_index': index,
        'page': page,
        'button_page': button_page
    }
    
    await edit_cb(cb, 
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
@Altruix.bot.on_callback_query(filters.regex(r"delete_all_profile_photos_(\d+)_(\d+)(?:_(\d+))?"))
@log_errors
async def delete_all_profile_photos_handler(c: Client, cb: CallbackQuery):
    """Handler untuk menghapus semua foto profil (dengan konfirmasi)"""
    if not await check_authorization(cb): return
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    user_id = cb.from_user.id
    user_edit_confirmation_state[user_id] = {
        'action': 'delete_all_profile_photos',
        'session_index': index,
        'page': page,
        'button_page': button_page,
        'delay': 2  # Default delay 2 detik
    }
    
    # Tampilkan konfirmasi
    await edit_cb(cb, 
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
                InlineKeyboardButton("❌ Tidak", f"session_info_{index}_{page}_{button_page}")
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
@Altruix.bot.on_callback_query(filters.regex(r"check_limit_confirm_(\d+)_(\d+)(?:_(\d+))?"))
@log_errors
async def check_limit_confirmation_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1

    confirmation_buttons = [
        [
            InlineKeyboardButton("✅ Yes, Check Limit", f"check_limit_execute_{index}_{page}"),
            InlineKeyboardButton("❌ Cancel", f"session_info_{index}_{page}_{button_page}")
        ]
    ]

    await edit_cb(cb, 
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
    if not await check_authorization(cb): return
    await cb.answer("🔍 Sedang mengecek limit...", show_alert=True)
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))

    if index >= len(Altruix.clients):
        await edit_cb(cb, "❌ Session tidak ditemukan.")
        return

    session_client = Altruix.clients[index]
    session_info = getattr(session_client, 'myself', None) or await session_client.get_me()

    await edit_cb(cb, "🔄 Mengirim /start ke @SpamBot...")

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

        await edit_cb(cb, 
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
        await edit_cb(cb, "❌ Akun ini diblokir oleh @SpamBot (kemungkinan limit permanen atau sebelumnya terkena spam berat).")

    except FloodWait as e:
        await edit_cb(cb, f"⏳ FloodWait! Akun ini harus menunggu {e.value} detik sebelum bisa mengirim pesan lagi.")

    except Exception as e:
        await edit_cb(cb, f"❌ Gagal mengecek limit: {html.escape(str(e))}")
        Altruix.log(f"Error check limit session {index}: {e}", level=logging.ERROR)


@Altruix.bot.on_callback_query(filters.regex(r"^test_ping_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def test_ping_cb_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    user = cb.from_user
    user_id = user.id
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1

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
        
        await edit_cb(cb, 
            f"✅ Ping berhasil! Pesan dikirim ke grup log.\n"
            f"Akun: <a href='tg://user?id={session_user.id}'>{html.escape(session_user.first_name or '')} {html.escape(session_user.last_name or '')}</a>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(gt("back"), f"session_info_{index}_{page}_{button_page}")]]) ,
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
        await edit_cb(cb, f"⏳ FloodWait terdeteksi. Tunggu {e.value} detik.")
        Altruix.log(f"FloodWait saat test ping session {index}: {e.value}s")
        
        # ✅ BARU: Kirim notifikasi error ke log group
        await send_log_notification(
            c, 'test_ping', index, cb.from_user, 
            False, f"FloodWait {e.value}s", {'Aksi': 'Test ping gagal'}
        )

    except (PeerIdInvalid, UserIsBlocked, ChatWriteForbidden) as e:
        error_msg = "❌ Gagal mengirim ping: Bot tidak bisa mengirim pesan ke grup log."
        await edit_cb(cb, error_msg)
        Altruix.log(f"Error izin saat test ping session {index}: {e}")

        try:
            await Altruix.bot.send_message(
                log_chat_id,
                f"⚠️ <b>ERROR TEST PING</b>\n"
                f"• User: {user_link}\n"
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
        await edit_cb(cb, error_msg)
        Altruix.log(f"SlowmodeWait saat test ping session {index}: {e.value}s")
        try:
            await Altruix.bot.send_message(
                log_chat_id,
                f"⚠️ <b>ERROR TEST PING (SlowmodeWait)</b>\n"
                f"• User: {user_link}\n"
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
        await edit_cb(cb, "❌ Gagal menguji ping. Owner telah diberi tahu.")
        Altruix.log(f"Error umum saat test ping session {index}: {e}")

        try:
            await Altruix.bot.send_message(
                log_chat_id,
                f"⚠️ <b>ERROR TEST PING (CRITICAL)</b>\n"
                f"• User: {user_link}\n"
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


@Altruix.bot.on_callback_query(filters.regex(r"^export_phone_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def export_phone_cb_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    user = cb.from_user
    user_id = user.id
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1

    if index >= len(Altruix.clients):
        return await cb.answer("Session tidak ditemukan.", show_alert=True)

    if user_id not in Altruix.auth_users:
        return await cb.answer("⛔ Tidak diizinkan mengekspor nomor.", show_alert=True)

    await cb.answer("📞 Mengambil nomor telepon...", show_alert=False)

    try:
        session_client = Altruix.clients[index]
        user_info = await session_client.get_me()

        if not user_info.phone_number:
            await edit_cb(cb, "❌ Akun ini tidak memiliki nomor telepon yang terdaftar.")
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
        
        await edit_cb(cb, 
            f"✅ Nomor HP untuk sesi {index + 1} telah dikirim ke pesan pribadi Anda.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(gt("back"), f"session_info_{index}_{page}_{button_page}")]])
        )
        
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

        await edit_cb(cb, "❌ Gagal mengekspor nomor telepon. Owner telah diberi tahu.")
        Altruix.log(f"Error mengekspor nomor telepon: {e}", level=logging.ERROR)
        
        # ✅ BARU: Kirim notifikasi error ke log group
        await send_log_notification(
            c, 'export_phone', index, cb.from_user, 
            False, str(e), {'Aksi': 'Export phone gagal'}
        )


@Altruix.bot.on_callback_query(filters.regex(r"^export_session_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def export_session_cb_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    user = cb.from_user
    user_id = user.id
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1

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
        
        await edit_cb(cb, 
            "✅ Session dikirim ke pesan pribadi Anda.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(gt("back"), f"session_info_{index}_{page}_{button_page}")]])
        )
        
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

        await edit_cb(cb, "❌ Gagal mengekspor session. Owner telah diberi tahu.")
        Altruix.log(f"Error mengekspor session: {e}", level=logging.ERROR)
        
        # ✅ BARU: Kirim notifikasi error ke log group
        await send_log_notification(
            c, 'export_session', index, cb.from_user, 
            False, str(e), {'Aksi': 'Export session gagal'}
        )


@Altruix.bot.on_callback_query(filters.regex(r"^refresh_session_info_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def refresh_session_info_cb_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
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
    await sessions_info_cb_handler(c, cb, index=index, callback_page=page, button_page=button_page)


@Altruix.bot.on_callback_query(filters.regex(r"^unlink_session_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def unlink_session_cb_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    if index >= len(Altruix.clients):
        await cb.answer("Session already removed or invalid.", show_alert=True)
        return

    # Gunakan Tombol Konfirmasi Inline sesuai permintaan user
    confirm_buttons = [
        [
            InlineKeyboardButton(gt("yes"), f"unlink_confirm_{index}"),
            InlineKeyboardButton(gt("no"), f"session_info_{index}_{page}_{button_page}")
        ]
    ]

    await edit_cb(cb, 
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
    if not await check_authorization(cb): return
    index = int(cb.matches[0].group(1))
    
    try:
        await edit_cb(cb, f"⏳ {gt('unlink_session')}...")
        await Altruix.remove_session(index, user=cb.from_user)
        
        # Answer only once at the end with the success alert
        # This avoiding "QUERY_ID_INVALID" error from double answer
        await cb.answer("Sesi berhasil dihapus. Restarting...", show_alert=True)
        
        # ✅ REFINED: Sebaiknya restart agar sesi benar-benar bersih dari list memori di semua plugin
        await Altruix._restart(soft=True)
    except Exception as e:
        # If edit fails, the query might still be valid, try to answer with error
        try:
            await cb.answer(f"❌ Error: {e}", show_alert=True)
        except:
            pass
        await edit_cb(cb, f"❌ Gagal menghapus sesi: {e}")


# ✅ HANDLER BARU: Lihat Semua Sesi Login
@Altruix.bot.on_callback_query(filters.regex(r"^view_all_sessions_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def view_all_sessions_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer("🔍 Mengambil data sesi...", show_alert=False)
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1

    if index >= len(Altruix.clients):
        await edit_cb(cb, "❌ Session tidak ditemukan.")
        return

    session_client = Altruix.clients[index]
    
    try:
        from pyrogram.raw.functions.account import GetAuthorizations
        auths_obj = await session_client.invoke(GetAuthorizations())
        auths = auths_obj.authorizations
        
        if not auths:
            await edit_cb(cb, 
                text="ℹ️ Tidak ada sesi aktif selain ini.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}_{button_page}")]
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

        await edit_cb(cb, 
            text=out,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}_{button_page}")]
            ]),
            parse_mode=ParseMode.HTML
        )
        
        # Kirim notifikasi log
        await send_log_notification(
            c, 'view_all_sessions', index, cb.from_user, 
            True, None, {'Total Sesi': len(auths)}
        )

    except Exception as e:
        await edit_cb(cb, 
            text=f"❌ Gagal mengambil data sesi: {html.escape(str(e))}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}_{button_page}")]
            ])
        )
        await send_log_notification(
            c, 'view_all_sessions', index, cb.from_user, 
            False, str(e), {}
        )


# ✅ HANDLER BARU: Join Group/Channel Input
@Altruix.bot.on_callback_query(filters.regex(r"^join_chat_input_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def join_chat_input_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    user_id = cb.from_user.id
    
    # Simpan state
    user_bulk_join_state[user_id] = {
        'session_index': index,
        'page': page,
        'button_page': button_page,
        'step': 'waiting_link',
        'delay': 0, # Not bulk, but we reuse the state dict for simplicity
        'is_single': True
    }
    
    await edit_cb(cb, 
        text="<b>➕ Join Group/Channel</b>\n\n"
             "Silakan kirimkan link group/channel atau username.\n\n"
             "Contoh:\n"
             "• <code>@username</code>\n"
             "• <code>https://t.me/joinchat/xxxxx</code>\n"
             "• <code>https://t.me/+xxxxx</code>\n\n"
             "Kirim <code>/cancel</code> untuk membatalkan.",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Batal", callback_data=f"session_info_{index}_{page}_{button_page}")]
        ])
    )


# ✅ HANDLER BARU: Join Chat Confirm (Di panggil dari handle_reply)
@Altruix.bot.on_callback_query(filters.regex(r"^join_confirm_(yes|no)$"))
@log_errors
async def join_chat_confirm_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    user_id = cb.from_user.id
    action = cb.matches[0].group(1)
    
    if user_id not in user_bulk_join_state:
        await cb.answer("❌ State tidak ditemukan.", show_alert=True)
        return
        
    state = user_bulk_join_state[user_id]
    index = state['session_index']
    page = state['page']
    button_page = state['button_page']
    link = state['link']
    
    if action == "no":
        del user_bulk_join_state[user_id]
        await cb.answer("Dibatalkan")
        if cb.message: await cb.message.delete()
        return
        
    await cb.answer("⏳ Mencoba join...", show_alert=False)
    await edit_cb(cb, f"🔄 Sesi {index+1} sedang mencoba join ke <code>{link}</code>...", parse_mode=ParseMode.HTML)
    
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
        await edit_cb(cb, 
            text=f"✅ <b>Berhasil Join!</b>\n\nSesi {index+1} telah bergabung ke <code>{link}</code>.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}_{button_page}")]
            ]),
            parse_mode=ParseMode.HTML
        )
    except UserAlreadyParticipant:
        success = True # Already in
        await edit_cb(cb, 
            text=f"ℹ️ <b>Sudah Bergabung</b>\n\nSesi {index+1} sudah menjadi anggota di <code>{link}</code>.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}_{button_page}")]
            ]),
            parse_mode=ParseMode.HTML
        )
    except (InviteHashInvalid, InviteHashExpired):
        error_msg = "Link kadaluarsa atau tidak valid"
        await edit_cb(cb, f"❌ <b>Gagal!</b>\n\nLink tidak valid atau kadaluarsa.", parse_mode=ParseMode.HTML)
    except FloodWait as e:
        error_msg = f"FloodWait {e.value}s"
        await edit_cb(cb, f"⏳ <b>FloodWait!</b>\n\nHarus menunggu {e.value} detik.", parse_mode=ParseMode.HTML)
    except Exception as e:
        error_msg = str(e)
        await edit_cb(cb, f"❌ <b>Error:</b>\n\n<code>{html.escape(str(e))}</code>", parse_mode=ParseMode.HTML)
    
    # Kirim notifikasi log
    await send_log_notification(
        c, 'join_chat', index, cb.from_user, 
        success, error_msg, {'Link': link}
    )
    
    # Cleanup state
    del user_bulk_join_state[user_id]




# ✅ HANDLER BARU: PM Logger Menu
@Altruix.bot.on_callback_query(filters.regex(r"^pml_menu_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def pml_menu_handler(c: Client, cb: CallbackQuery, index: int = None, page: int = None, button_page: int = None):
    if not await check_authorization(cb): return
    try:
        await cb.answer()
    except: pass
    
    if index is None:
        index = int(cb.matches[0].group(1))
    if page is None:
        page = int(cb.matches[0].group(2))
    if button_page is None:
        button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    # Load settings
    try:
        f_path = get_db_path("pm_logger_user_settings.json")
        if os.path.exists(f_path):
            with open(f_path, "r") as f:
                data = json.load(f)
                sessions_data = data.get("sessions", {}) or data.get("settings", {})
                reply_access_mode = data.get("reply_access_mode", "sudo") # Default to sudo
        else:
            sessions_data = {}
            reply_access_mode = "sudo"
    except Exception as e:
        logger.error(f"Error loading PML settings: {e}")
        sessions_data = {}
        reply_access_mode = "sudo"

    # Per-session settings
    session_client = Altruix.clients[index]
    user_id_str = str(session_client.me.id) if session_client.me else "Unknown"
    
    session_config = sessions_data.get(user_id_str, {})
    if isinstance(session_config, bool):
        # Normalize legacy boolean to dict for UI
        session_config = {"enabled": session_config}
    
    # Defaults: use 'enabled' if migrating, else True/False based on common logic
    is_globally_on = session_config.get("enabled", False)
    log_from_user = session_config.get("log_from_user", is_globally_on)
    log_from_bot = session_config.get("log_from_bot", is_globally_on)
    
    # Apply Type logic
    apply_type = data.get("apply_types", {}).get(user_id_str, "per_account")
    type_label = gt("global") if apply_type == "global" else gt("per_account")
    
    text = (
        "<b>📟 PM Logger (Userbot)</b>\n\n"
        "Atur bagaimana akun ini mencatat pesan PM masuk ke Log Group.\n\n"
        f"• 👤 <b>Log User:</b> {'✅ ON' if log_from_user else '❌ OFF'}\n"
        f"• 🤖 <b>Log Bot:</b> {'✅ ON' if log_from_bot else '❌ OFF'}\n"
        f"• 👥 <b>Reply Mode:</b> {reply_access_mode.upper()}\n"
        f"• ⚙️ <b>{gt('apply_type')}:</b> <code>{type_label}</code>\n\n"
        "Pilih kategori di bawah untuk mengatur filter tipe pesan."
    )
    
    buttons = [
        [
            InlineKeyboardButton(f"👤 Log User: {'OFF' if log_from_user else 'ON'}", f"pml_toggle_log_user_{index}_{page}_{button_page}"),
            InlineKeyboardButton(f"🤖 Log Bot: {'OFF' if log_from_bot else 'ON'}", f"pml_toggle_log_bot_{index}_{page}_{button_page}"),
        ],
        [
            InlineKeyboardButton(f"⚙️ {gt('apply_type')}: {type_label}", f"pml_toggle_type_{index}_{page}_{button_page}"),
            InlineKeyboardButton(gt("set_as_global"), f"pml_set_global_{index}_{page}_{button_page}"),
        ],
        [
            InlineKeyboardButton(f"👥 Reply Mode: {reply_access_mode.upper()}", f"pml_toggle_log_mode_{index}_{page}_{button_page}"),
        ],
        [
            InlineKeyboardButton("👤 User Filters", f"pmlf_menu_user_{index}_{page}_{button_page}"),
            InlineKeyboardButton("🤖 Bot Filters", f"pmlf_menu_bot_{index}_{page}_{button_page}")
        ],
        [InlineKeyboardButton("🔙 Back to Session Info", f"session_info_{index}_{page}_{button_page}")]
    ]
    
    await edit_cb(cb, text=text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)


# ✅ HANDLER BARU: Toggle PM Logger Settings
@Altruix.bot.on_callback_query(filters.regex(r"^pml_toggle_type_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def pml_toggle_type_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    user_id_str = str(Altruix.clients[index].me.id)
    filename = get_db_path("pm_logger_user_settings.json")
    
    try:
        if os.path.exists(filename):
            with open(filename, "r") as f: data = json.load(f)
        else:
            data = {"sessions": {}, "reply_access_mode": "sudo", "apply_types": {}}
            
        if "apply_types" not in data: data["apply_types"] = {}
        
        current = data["apply_types"].get(user_id_str, "per_account")
        new_val = "global" if current == "per_account" else "per_account"
        data["apply_types"][user_id_str] = new_val
        
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)
        
        await cb.answer(f"Apply Type: {new_val.upper()}")
        await pml_menu_handler(c, cb, index=index, page=page, button_page=button_page)
    except Exception as e:
        await cb.answer(f"Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^pml_set_global_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def pml_set_global_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    user_id_str = str(Altruix.clients[index].me.id)
    filename = get_db_path("pm_logger_user_settings.json")
    
    try:
        if os.path.exists(filename):
            with open(filename, "r") as f: data = json.load(f)
        else:
            return await cb.answer("❌ Error: Settings file missing", show_alert=True)
            
        current_config = data.get("sessions", {}).get(user_id_str)
        if not current_config:
             return await cb.answer("❌ Current session has no config to set as global", show_alert=True)
             
        data["global_config"] = current_config
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)
            
        await cb.answer("✅ Successfully set as GLOBAL!", show_alert=True)
        await pml_menu_handler(c, cb, index=index, page=page, button_page=button_page)
    except Exception as e:
        await cb.answer(f"Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^pml_toggle_log_(user|bot|mode)_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def pml_toggle_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    target = cb.matches[0].group(1)
    index = int(cb.matches[0].group(2))
    page = int(cb.matches[0].group(3))
    button_page = int(cb.matches[0].group(4)) if len(cb.matches[0].groups()) >= 4 and cb.matches[0].group(4) else 1
    
    filename = get_db_path("pm_logger_user_settings.json")
    
    try:
        if os.path.exists(filename):
            with open(filename, "r") as f:
                data = json.load(f)
        else:
            data = {"sessions": {}, "reply_access_mode": "sudo", "apply_types": {}, "global_config": {"log_from_user": False, "log_from_bot": False}}
            
        if "apply_types" not in data: data["apply_types"] = {}
        if "global_config" not in data: data["global_config"] = {"log_from_user": False, "log_from_bot": False}
            
        if "sessions" not in data:
            data["sessions"] = data.pop("settings", {})

        success = False
        user_id_str = str(Altruix.clients[index].me.id)
        if user_id_str not in data["sessions"]:
            data["sessions"][user_id_str] = {}
        elif isinstance(data["sessions"][user_id_str], bool):
            # Migrate boolean to dict
            data["sessions"][user_id_str] = {"enabled": data["sessions"][user_id_str]}

        current_val = False
        if target == "user":
            current_val = data["sessions"][user_id_str].get("log_from_user", False)
            data["sessions"][user_id_str]["log_from_user"] = not current_val
            success = True
        elif target == "bot":
            current_val = data["sessions"][user_id_str].get("log_from_bot", False)
            data["sessions"][user_id_str]["log_from_bot"] = not current_val
            success = True
        elif target == "mode":
            current_mode = data.get("reply_access_mode", "sudo")
            # Cycle: owner -> sudo -> all
            if current_mode == "owner":
                new_mode = "sudo"
            elif current_mode == "sudo":
                new_mode = "all"
            else:
                new_mode = "owner"
                
            data["reply_access_mode"] = new_mode
            success = True
            current_val = new_mode # For logging
            
        if success:
            with open(filename, "w") as f:
                json.dump(data, f, indent=2)
            await cb.answer("✅ Updated!")
            await pml_menu_handler(c, cb, index=index, page=page, button_page=button_page)
            
            # Log
            await send_log_notification(
                c, f'pml_toggle_{target}', index, cb.from_user, 
                True, None, {'Target': target, 'New State': not current_val}
            )
        else:
            await cb.answer("Failed to update.", show_alert=True)
            
    except Exception as e:
        await cb.answer(f"Error: {e}", show_alert=True)
        logger.error(f"Error toggling PML settings: {e}")


# ✅ HANDLER BARU: Join Logger Menu
@Altruix.bot.on_callback_query(filters.regex(r"^joinl_menu_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def joinl_menu_handler(c: Client, cb: CallbackQuery, index: int = None, page: int = None, button_page: int = None):
    if not await check_authorization(cb): return
    try: await cb.answer()
    except: pass
    if index is None: index = int(cb.matches[0].group(1))
    if page is None: page = int(cb.matches[0].group(2))
    if button_page is None:
        button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    filename = get_db_path("join_logger_settings.json")
    data = {"global": {"enabled": True}, "sessions": {}, "apply_types": {}}
    if os.path.exists(filename):
        with open(filename, "r") as f:
            loaded = json.load(f)
            if "global" in loaded: data = loaded
            else: data["global"]["enabled"] = loaded.get("enabled", True)

    if "sessions" not in data: data["sessions"] = {}
    if "apply_types" not in data: data["apply_types"] = {}
    
    user_id_str = str(Altruix.clients[index].me.id)
    apply_type = data["apply_types"].get(user_id_str, "per_account")
    type_label = gt("global") if apply_type == "global" else gt("per_account")

    if apply_type == "global":
        active_enabled = data["global"].get("enabled", True)
    else:
        active_enabled = data["sessions"].get(user_id_str, data["global"]).get("enabled", True) if isinstance(data["sessions"].get(user_id_str), dict) else data["sessions"].get(user_id_str, data["global"].get("enabled", True))

    text = (
        "<b>🚪 Join Logger Settings</b>\n\n"
        f"Mendeteksi saat akun Anda join atau diundang ke group/channel.\n\n"
        f"• <b>Status:</b> {'✅ ENABLED' if active_enabled else '❌ DISABLED'}\n"
        f"• ⚙️ <b>{gt('apply_type')}:</b> <code>{type_label}</code>"
    )
    buttons = [
        [InlineKeyboardButton(f"{'Disable' if active_enabled else 'Enable'} Join Logger", f"joinl_toggle_{index}_{page}_{button_page}")],
        [
            InlineKeyboardButton(f"⚙️ {gt('apply_type')}: {type_label}", f"joinl_toggle_type_{index}_{page}_{button_page}"),
            InlineKeyboardButton(gt("set_as_global"), f"joinl_set_global_{index}_{page}_{button_page}"),
        ],
        [InlineKeyboardButton("🔙 Back to Session Info", f"session_info_{index}_{page}_{button_page}")]
    ]
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons))

@Altruix.bot.on_callback_query(filters.regex(r"^joinl_toggle_type_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def joinl_toggle_type_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    user_id_str = str(Altruix.clients[index].me.id)
    filename = get_db_path("join_logger_settings.json")
    try:
        if os.path.exists(filename):
            with open(filename, "r") as f: data = json.load(f)
        else:
            data = {"global": {"enabled": True}, "sessions": {}, "apply_types": {}}
        if "apply_types" not in data: data["apply_types"] = {}
        current = data["apply_types"].get(user_id_str, "per_account")
        new_val = "global" if current == "per_account" else "per_account"
        data["apply_types"][user_id_str] = new_val
        with open(filename, "w") as f: json.dump(data, f, indent=4)
        await cb.answer(f"Apply Type: {new_val.upper()}")
        await joinl_menu_handler(c, cb, index=index, page=page, button_page=button_page)
    except Exception as e: await cb.answer(f"Error: {e}", show_alert=True)


# ✅ HANDLER BARU: Command Settings Menu
@Altruix.bot.on_callback_query(filters.regex(r"^cmd_settings_menu_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def cmd_settings_menu_handler(c: Client, cb: CallbackQuery, index: int = None, page: int = None, button_page: int = None):
    if not await check_authorization(cb): return
    if index is None: index = int(cb.matches[0].group(1))
    if page is None: page = int(cb.matches[0].group(2))
    if button_page is None:
        button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    try:
        await cb.answer()
    except: pass
    
    # Get session info
    session_client = Altruix.clients[index]
    user_id_str = str((getattr(session_client, 'myself', None) or session_client.me).id)
    
    # Load settings
    apply_type = await Altruix.config.get_env(f"AUTO_DELETE_CMD_TYPE_{index}") or "per_account"
    if apply_type == "global":
        status = await Altruix.config.get_env("AUTO_DELETE_CMD_GLOBAL")
    else:
        status = await Altruix.config.get_env(f"AUTO_DELETE_CMD_STATUS_{index}")
    
    # Default is True (matches current userbot behavior)
    if status is None: status = True
    
    type_label = gt("global") if apply_type == "global" else gt("per_account")
    status_label = "✅ ON" if status else "❌ OFF"
    
    text = (
        f"{gt('cmd_settings_text')}\n\n"
        f"• 🗑️ <b>{gt('auto_delete_cmd')}:</b> {status_label}\n"
        f"• ⚙️ <b>{gt('apply_type')}:</b> <code>{type_label}</code>\n\n"
        f"<i>{gt('auto_delete_desc')}</i>"
    )
    
    buttons = [
        [
            InlineKeyboardButton(f"🗑️ {gt('auto_delete_cmd')}: {'OFF' if status else 'ON'}", f"cmd_toggle_{index}_{page}_{button_page}"),
        ],
        [
            InlineKeyboardButton(f"⚙️ {gt('apply_type')}: {type_label}", f"cmd_toggle_type_{index}_{page}_{button_page}"),
            InlineKeyboardButton(gt("set_as_global"), f"cmd_set_global_{index}_{page}_{button_page}"),
        ],
        [InlineKeyboardButton("🔙 Back to Session Info", f"session_info_{index}_{page}_{button_page}")]
    ]
    
    await edit_cb(cb, text=text, reply_markup=InlineKeyboardMarkup(buttons))


@Altruix.bot.on_callback_query(filters.regex(r"^cmd_toggle_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def cmd_toggle_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    apply_type = await Altruix.config.get_env(f"AUTO_DELETE_CMD_TYPE_{index}") or "per_account"
    
    if apply_type == "global":
        current = await Altruix.config.get_env("AUTO_DELETE_CMD_GLOBAL")
        if current is None: current = True
        new_val = not current
        await Altruix.config.sync_env_to_db("AUTO_DELETE_CMD_GLOBAL", new_val, upsert=True)
    else:
        current = await Altruix.config.get_env(f"AUTO_DELETE_CMD_STATUS_{index}")
        if current is None: current = True
        new_val = not current
        await Altruix.config.sync_env_to_db(f"AUTO_DELETE_CMD_STATUS_{index}", new_val, upsert=True)
    
    await cb.answer(f"{gt('auto_delete_cmd')}: {'ON' if new_val else 'OFF'}")
    await cmd_settings_menu_handler(c, cb, index=index, page=page, button_page=button_page)


@Altruix.bot.on_callback_query(filters.regex(r"^cmd_toggle_type_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def cmd_toggle_type_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    current = await Altruix.config.get_env(f"AUTO_DELETE_CMD_TYPE_{index}") or "per_account"
    new_val = "global" if current == "per_account" else "per_account"
    
    await Altruix.config.sync_env_to_db(f"AUTO_DELETE_CMD_TYPE_{index}", new_val, upsert=True)
    await cb.answer(f"Apply Type: {new_val.upper()}")
    await cmd_settings_menu_handler(c, cb, index=index, page=page, button_page=button_page)


@Altruix.bot.on_callback_query(filters.regex(r"^cmd_set_global_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def cmd_set_global_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    current = await Altruix.config.get_env(f"AUTO_DELETE_CMD_STATUS_{index}")
    if current is None: current = True
    
    await Altruix.config.sync_env_to_db("AUTO_DELETE_CMD_GLOBAL", current, upsert=True)
    await cb.answer("✅ Successfully set as GLOBAL!", show_alert=True)
    await cmd_settings_menu_handler(c, cb, index=index, page=page, button_page=button_page)

@Altruix.bot.on_callback_query(filters.regex(r"^joinl_set_global_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def joinl_set_global_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    user_id_str = str(Altruix.clients[index].me.id)
    filename = get_db_path("join_logger_settings.json")
    try:
        if os.path.exists(filename):
            with open(filename, "r") as f: data = json.load(f)
        else: return await cb.answer("❌ Error: Settings file missing", show_alert=True)
        current = data.get("sessions", {}).get(user_id_str)
        if current is None: return await cb.answer("❌ Current session has no config to set as global", show_alert=True)
        if not isinstance(current, dict): current = {"enabled": bool(current)}
        data["global"] = current
        with open(filename, "w") as f: json.dump(data, f, indent=4)
        await cb.answer("✅ Successfully set as GLOBAL!", show_alert=True)
        await joinl_menu_handler(c, cb, index=index, page=page, button_page=button_page)
    except Exception as e: await cb.answer(f"Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^joinl_toggle_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def joinl_toggle_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    user_id_str = str(Altruix.clients[index].me.id)
    filename = get_db_path("join_logger_settings.json")
    if os.path.exists(filename):
        with open(filename, "r") as f: data = json.load(f)
    else: data = {"global": {"enabled": True}, "sessions": {}, "apply_types": {}}
    
    if "global" not in data: 
        # Migration from old flat format
        data = {"global": {"enabled": data.get("enabled", True)}, "sessions": {}, "apply_types": {}}
    
    if "sessions" not in data: data["sessions"] = {}
    if "apply_types" not in data: data["apply_types"] = {}

    apply_type = data["apply_types"].get(user_id_str, "per_account")
    if apply_type == "per_account":
        if user_id_str not in data["sessions"]: data["sessions"][user_id_str] = data["global"].copy()
        if not isinstance(data["sessions"][user_id_str], dict): data["sessions"][user_id_str] = {"enabled": bool(data["sessions"][user_id_str])}
        data["sessions"][user_id_str]["enabled"] = not data["sessions"][user_id_str].get("enabled", True)
        new_val = data["sessions"][user_id_str]["enabled"]
    else:
        data["global"]["enabled"] = not data["global"].get("enabled", True)
        new_val = data["global"]["enabled"]

    with open(filename, "w") as f: json.dump(data, f, indent=4)
    await cb.answer(f"Join Logger: {'Enabled' if new_val else 'Disabled'}")
    await joinl_menu_handler(c, cb, index=index, page=page, button_page=button_page)

# ✅ HANDLER BARU: Command Logger Menu
@Altruix.bot.on_callback_query(filters.regex(r"^cmdl_menu_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def cmdl_menu_handler(c: Client, cb: CallbackQuery, index: int = None, page: int = None, button_page: int = None):
    if not await check_authorization(cb): return
    try: await cb.answer()
    except: pass
    if index is None: index = int(cb.matches[0].group(1))
    if page is None: page = int(cb.matches[0].group(2))
    if button_page is None:
        button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    filename = get_db_path("cmd_logger_settings.json")
    data = {"global": {"enabled": False}, "sessions": {}, "apply_types": {}}
    if os.path.exists(filename):
        with open(filename, "r") as f:
            loaded = json.load(f)
            if "global" in loaded: data = loaded
            else: data["global"]["enabled"] = loaded.get("enabled", False)

    if "sessions" not in data: data["sessions"] = {}
    if "apply_types" not in data: data["apply_types"] = {}
    
    user_id_str = str(Altruix.clients[index].me.id)
    apply_type = data["apply_types"].get(user_id_str, "per_account")
    type_label = gt("global") if apply_type == "global" else gt("per_account")

    if apply_type == "global":
        active_enabled = data["global"].get("enabled", False)
    else:
        active_enabled = data["sessions"].get(user_id_str, data["global"]).get("enabled", False) if isinstance(data["sessions"].get(user_id_str), dict) else data["sessions"].get(user_id_str, data["global"].get("enabled", False))

    text = (
        "<b>⌨️ Command Logger Settings</b>\n\n"
        f"Mencatat seluruh perintah yang Anda jalankan.\n\n"
        f"• <b>Status:</b> {'✅ ENABLED' if active_enabled else '❌ DISABLED'}\n"
        f"• ⚙️ <b>{gt('apply_type')}:</b> <code>{type_label}</code>"
    )
    buttons = [
        [InlineKeyboardButton(f"{'Disable' if active_enabled else 'Enable'} Cmd Logger", f"cmdl_toggle_{index}_{page}_{button_page}")],
        [
            InlineKeyboardButton(f"⚙️ {gt('apply_type')}: {type_label}", f"cmdl_toggle_type_{index}_{page}_{button_page}"),
            InlineKeyboardButton(gt("set_as_global"), f"cmdl_set_global_{index}_{page}_{button_page}"),
        ],
        [InlineKeyboardButton("🔙 Back to Session Info", f"session_info_{index}_{page}_{button_page}")]
    ]
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons))

@Altruix.bot.on_callback_query(filters.regex(r"^cmdl_toggle_type_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def cmdl_toggle_type_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    user_id_str = str(Altruix.clients[index].me.id)
    filename = get_db_path("cmd_logger_settings.json")
    try:
        if os.path.exists(filename):
            with open(filename, "r") as f: data = json.load(f)
        else:
            data = {"global": {"enabled": False}, "sessions": {}, "apply_types": {}}
        if "apply_types" not in data: data["apply_types"] = {}
        current = data["apply_types"].get(user_id_str, "per_account")
        new_val = "global" if current == "per_account" else "per_account"
        data["apply_types"][user_id_str] = new_val
        with open(filename, "w") as f: json.dump(data, f, indent=4)
        await cb.answer(f"Apply Type: {new_val.upper()}")
        await cmdl_menu_handler(c, cb, index=index, page=page, button_page=button_page)
    except Exception as e: await cb.answer(f"Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^cmdl_set_global_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def cmdl_set_global_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    user_id_str = str(Altruix.clients[index].me.id)
    filename = get_db_path("cmd_logger_settings.json")
    try:
        if os.path.exists(filename):
            with open(filename, "r") as f: data = json.load(f)
        else: return await cb.answer("❌ Error: Settings file missing", show_alert=True)
        current = data.get("sessions", {}).get(user_id_str)
        if current is None: return await cb.answer("❌ Current session has no config to set as global", show_alert=True)
        if not isinstance(current, dict): current = {"enabled": bool(current)}
        data["global"] = current
        with open(filename, "w") as f: json.dump(data, f, indent=4)
        await cb.answer("✅ Successfully set as GLOBAL!", show_alert=True)
        await cmdl_menu_handler(c, cb, index=index, page=page, button_page=button_page)
    except Exception as e: await cb.answer(f"Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^cmdl_toggle_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def cmdl_toggle_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    user_id_str = str(Altruix.clients[index].me.id)
    filename = get_db_path("cmd_logger_settings.json")
    if os.path.exists(filename):
        with open(filename, "r") as f: data = json.load(f)
    else: data = {"global": {"enabled": False}, "sessions": {}, "apply_types": {}}
    
    if "global" not in data:
        data = {"global": {"enabled": data.get("enabled", False)}, "sessions": {}, "apply_types": {}}
    
    if "sessions" not in data: data["sessions"] = {}
    if "apply_types" not in data: data["apply_types"] = {}

    apply_type = data["apply_types"].get(user_id_str, "per_account")
    if apply_type == "per_account":
        if user_id_str not in data["sessions"]: data["sessions"][user_id_str] = data["global"].copy()
        if not isinstance(data["sessions"][user_id_str], dict): data["sessions"][user_id_str] = {"enabled": bool(data["sessions"][user_id_str])}
        data["sessions"][user_id_str]["enabled"] = not data["sessions"][user_id_str].get("enabled", False)
        new_val = data["sessions"][user_id_str]["enabled"]
    else:
        data["global"]["enabled"] = not data["global"].get("enabled", False)
        new_val = data["global"]["enabled"]

    with open(filename, "w") as f: json.dump(data, f, indent=4)
    await cb.answer(f"Command Logger: {'Enabled' if new_val else 'Disabled'}")
    await cmdl_menu_handler(c, cb, index=index, page=page, button_page=button_page)

# ✅ HANDLER BARU: PM Filters Menu
@Altruix.bot.on_callback_query(filters.regex(r"^pmlf_menu_(user|bot)_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def pml_filters_menu_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    try: await cb.answer()
    except: pass
    logger_type = cb.matches[0].group(1) # 'user' only for now in session info
    index = int(cb.matches[0].group(2))
    page = int(cb.matches[0].group(3))
    button_page = int(cb.matches[0].group(4)) if len(cb.matches[0].groups()) >= 4 and cb.matches[0].group(4) else 1
    
    text = (
        f"<b>🔍 {'Userbot' if logger_type == 'user' else 'Bot'} Logger Message Filters</b>\n\n"
        "Pilih kategori di bawah untuk mengatur jenis pesan yang akan dicatat:\n\n"
        "👤 <b>User Filters:</b> Filter pesan dari pengguna (Text, Photo, Video, Sticker, dll).\n"
        "🤖 <b>Bot Filters:</b> Filter pesan dari Bot (Sangat berguna untuk menghindari spam log dari bot)."
    )
    buttons = [
        [
            InlineKeyboardButton("👤 From User", f"pmlfl_{logger_type}_user_{index}_{page}_{button_page}"),
            InlineKeyboardButton("🤖 From Bot", f"pmlfl_{logger_type}_bot_{index}_{page}_{button_page}"),
        ],
        [InlineKeyboardButton("🔙 Back to PM Logger", f"pml_menu_{index}_{page}_{button_page}")]
    ]
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlfl_(user|bot)_(user|bot)_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def pmlf_list_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    logger_type = cb.matches[0].group(1) # 'user' only for now in session info
    source = cb.matches[0].group(2) # 'user' or 'bot'
    index = int(cb.matches[0].group(3))
    page = int(cb.matches[0].group(4))
    button_page = int(cb.matches[0].group(5)) if len(cb.matches[0].groups()) >= 5 and cb.matches[0].group(5) else 1
    source_key = f"from_{source}"
    
    filename = get_db_path("pm_logger_user_settings.json")
    user_id_str = str(Altruix.clients[index].me.id)
    
    if os.path.exists(filename):
        with open(filename, "r") as f: data = json.load(f)
        sessions = data.get("sessions", {}) or data.get("settings", {})
        session_data = sessions.get(user_id_str, {})
        if isinstance(session_data, bool):
            session_data = {"enabled": session_data}
        filters = session_data.get("filters", {}).get(source_key, {})
    else: filters = {}
    
    text = f"<b>🔍 {source.capitalize()} Filter ({'Userbot Session'})</b>\n\nKlik untuk toggle (✅ = Log, ❌ = Ignore):"
    buttons = []
    row = []
    for m_type in ["text", "photo", "video", "document", "audio", "voice", "sticker", "animation", "video_note"]:
        # Default value
        default_val = True
        if source == "bot" and m_type == "text": default_val = False
        
        val = filters.get(m_type, default_val)
        status = "✅" if val else "❌"
        row.append(InlineKeyboardButton(f"{status} {m_type.capitalize()}", f"pmlft_{logger_type}_{source}_{m_type}_{index}_{page}_{button_page}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row: buttons.append(row)
    buttons.append([InlineKeyboardButton("🔙 Back to Filters Menu", f"pmlf_menu_{logger_type}_{index}_{page}_{button_page}")])
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlft_(user|bot)_(user|bot)_(.+)_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def pmlf_toggle_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    logger_type = cb.matches[0].group(1)
    source = cb.matches[0].group(2)
    m_type = cb.matches[0].group(3)
    index = int(cb.matches[0].group(4))
    page = int(cb.matches[0].group(5))
    button_page = int(cb.matches[0].group(6)) if len(cb.matches[0].groups()) >= 6 and cb.matches[0].group(6) else 1
    source_key = f"from_{source}"
    user_id_str = str(Altruix.clients[index].me.id)
    
    filename = get_db_path("pm_logger_user_settings.json")
    
    if os.path.exists(filename):
        with open(filename, "r") as f: data = json.load(f)
        
        if "sessions" not in data:
            data["sessions"] = data.pop("settings", {})
        
        if user_id_str not in data["sessions"]:
            data["sessions"][user_id_str] = {}
        elif isinstance(data["sessions"][user_id_str], bool):
            # Migrate legacy boolean to dict
            data["sessions"][user_id_str] = {"enabled": data["sessions"][user_id_str]}
        
        if "filters" not in data["sessions"][user_id_str]:
            data["sessions"][user_id_str]["filters"] = {}
            
        if source_key not in data["sessions"][user_id_str]["filters"]: 
            from Main.plugins.userbot.xpm_logger_user import PM_LOGGER_FILTERS as DEFAULTS
            data["sessions"][user_id_str]["filters"][source_key] = DEFAULTS.get(source_key, {}).copy()
        
        current = data["sessions"][user_id_str]["filters"][source_key].get(m_type, True)
        data["sessions"][user_id_str]["filters"][source_key][m_type] = not current
            
        with open(filename, "w") as f: json.dump(data, f, indent=2)
        await cb.answer(f"Filter {m_type} {source}: {'Enabled' if not current else 'Disabled'}")
    
    # Refresh list
    class MockMatch:
        def group(self, i):
            if i == 1: return logger_type
            if i == 2: return source
            if i == 3: return index
            if i == 4: return page
            if i == 5: return button_page
            return None
    cb.matches = [MockMatch()]
    await pmlf_list_handler(c, cb)


# ✅ HANDLER UNTUK ADD SESSION (PLACEHOLDER)
@Altruix.bot.on_callback_query(filters.regex(r"^add_session$"))
@log_errors
async def add_session_handler(c: Client, cb: CallbackQuery):
    """Handler untuk tombol Add a Session"""
    if not await check_authorization(cb): return
    # Triggel handler dari get_session.py
    await add_session_cb_handler(c, cb)


# ✅ HANDLER BARU: Mention Control Menu
@Altruix.bot.on_callback_query(filters.regex(r"^mnt_menu_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def mnt_menu_handler(c: Client, cb: CallbackQuery, index: int = None, page: int = None, button_page: int = None):
    """Mention Control Menu with toggles"""
    if not await check_authorization(cb): return
    try:
        await cb.answer()
    except: pass
    
    if index is None:
        index = int(cb.matches[0].group(1))
    if page is None:
        page = int(cb.matches[0].group(2))
    if button_page is None:
        button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    # Load Mention Settings with support for structured format
    settings_file = get_db_path("mentions_settings.json")
    m_settings = {"global": {"mention": True, "auto_log": True, "reply_from_all": False}, "settings": {}}
    
    if os.path.exists(settings_file):
        try:
            with open(settings_file, "r") as f:
                loaded_data = json.load(f)
                if "global" in loaded_data:
                    m_settings = loaded_data
                else:
                    # Migrate legacy flat format
                    m_settings["global"]["mention"] = loaded_data.get("mention", True)
                    m_settings["global"]["auto_log"] = loaded_data.get("auto_log", True)
                    m_settings["global"]["reply_from_all"] = loaded_data.get("reply_from_all", False)
        except Exception as e:
            logger.error(f"Error loading mentions_settings: {e}")

    # Structured format support
    if "settings" not in m_settings: m_settings["settings"] = {}
    if "apply_types" not in m_settings: m_settings["apply_types"] = {}
    
    user_id_str = str(Altruix.clients[index].me.id)
    apply_type = m_settings["apply_types"].get(user_id_str, "per_account")
    type_label = gt("global") if apply_type == "global" else gt("per_account")

    if apply_type == "global":
        active_settings = m_settings.get("global", {})
    else:
        # Resolve per-session settings
        session_data = m_settings["settings"].get(user_id_str, {})
        if isinstance(session_data, bool):
             # Migrate old boolean value
             active_settings = {"mention": session_data, "auto_log": True, "reply_from_all": False}
        elif isinstance(session_data, dict) and "value" in session_data:
             # Another old format
             active_settings = {"mention": session_data["value"], "auto_log": True, "reply_from_all": False}
        else:
             active_settings = session_data

    rfa_status = "✅ ON" if active_settings.get("reply_from_all", m_settings["global"].get("reply_from_all")) else "❌ OFF"
    mnt_status = "✅ ON" if active_settings.get("mention", m_settings["global"].get("mention")) else "❌ OFF"
    alog_status = "✅ ON" if active_settings.get("auto_log", m_settings["global"].get("auto_log")) else "❌ OFF"

    desc_text = (
        f"<b>{gt('mention_control')}</b>\n\n"
        f"• <b>{gt('reply_from_all')}:</b> {rfa_status}\n"
        f"• <b>{gt('mention_logic')}:</b> {mnt_status}\n"
        f"• <b>{gt('mention_auto_log')}:</b> {alog_status}\n"
        f"• ⚙️ <b>{gt('apply_type')}:</b> <code>{type_label}</code>\n\n"
        f"<i>Gunakan tombol di bawah untuk konfigurasi.</i>"
    )

    buttons = [
        [
            InlineKeyboardButton(f"{gt('reply_from_all')}: {rfa_status}", f"mnt_toggle_rfa_{index}_{page}_{button_page}"),
        ],
        [
            InlineKeyboardButton(f"⚙️ {gt('apply_type')}: {type_label}", f"mnt_toggle_type_{index}_{page}_{button_page}"),
            InlineKeyboardButton(gt("set_as_global"), f"mnt_set_global_{index}_{page}_{button_page}"),
        ],
        [
            InlineKeyboardButton(f"{gt('mention_logic')}: {mnt_status}", f"mnt_toggle_mnt_{index}_{page}_{button_page}"),
            InlineKeyboardButton(f"{gt('mention_auto_log')}: {alog_status}", f"mnt_toggle_alog_{index}_{page}_{button_page}"),
        ],
        [
            InlineKeyboardButton("🔍 Message Type Filters", f"mntf_menu_{index}_{page}_{button_page}"),
            InlineKeyboardButton(gt("view_mentions"), f"view_mentions_menu_{index}_{page}_{button_page}"),
        ],
        [
            InlineKeyboardButton(gt("back"), f"session_info_{index}_{page}_{button_page}"),
        ]
    ]

    await edit_cb(cb, 
        desc_text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )


# ✅ HANDLER BARU: Download Story session-targeted
@Altruix.bot.on_callback_query(filters.regex(r"^dlstory_session_input_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def dlstory_session_input_handler(c: Client, cb: CallbackQuery):
    """Menerima input link story untuk didownload sesi tertentu"""
    if not await check_authorization(cb): return
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    if index >= len(Altruix.clients):
        await cb.answer("❌ Session tidak ditemukan.", show_alert=True)
        return

    session_client = Altruix.clients[index]
    session_info = getattr(session_client, 'myself', None) or await session_client.get_me()
    
    await edit_cb(cb, 
        f"📥 <b>{gt('download_story')}</b>\n\n"
        f"Akun pengeksekusi: <b>{html.escape(session_info.first_name)}</b>\n\n"
        f"Silakan kirim <b>Link Story Aktif</b> (misal: <code>https://t.me/username/s/1</code>).\n"
        f"Hasil akan dikirim ke <b>Altruix Log Group</b>.\n\n"
        f"Ketik <code>cancel</code> untuk membatalkan.",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(gt("cancel"), f"session_info_{index}_{page}_{button_page}")]])
    )
    
    try:
        user_id = cb.from_user.id
        msg = await c.listen(filters.chat(user_id) & filters.text, timeout=120)
        
        link = msg.text.strip()
        
        await edit_cb(cb, "🔄 <b>Sedang memproses...</b>")
        
        # Parse link
        if "t.me/" not in link or "/s/" not in link:
            await edit_cb(cb, "❌ <b>Format link tidak valid!</b>")
            await asyncio.sleep(3)
            await sessions_info_cb_handler(c, cb, index=index, callback_page=page, button_page=button_page)
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
                msg_copied = await session_client.copy_story(log_chat_id, target, story_id)
                # Edit log group message to add details if it was a copy
                try:
                    meta_info = f"\n\n🆔 <b>Story ID:</b> <code>{story_id}</code>\n👤 <b>Author ID:</b> <code>{target}</code>"
                    new_caption = (msg_copied.caption or "") + meta_info
                    await Altruix.bot.edit_message_caption(log_chat_id, msg_copied.id, caption=new_caption, parse_mode=enums.ParseMode.HTML)
                except Exception:
                    pass
                    
                await edit_cb(cb, f"✅ <b>Berhasil!</b> Story telah disalin ke Log Group.")
                await cb.answer("✅ Success!", show_alert=False)
            except Exception as e:
                err_str = str(e)
                # Check Bypass condition
                bypass = "PREMIUM_ACCOUNT_REQUIRED" in err_str or "STORY_NOT_MODIFIED" in err_str or "bad request" in err_str.lower()
                
                if not bypass and isinstance(e, FloodWait):
                     raise e
                
                await edit_cb(cb, f"🔄 <b>Copy gagal, mencoba Bypass (Download & Re-upload)...</b>")
                
                # ✅ BYPASS: Download and Re-upload
                story = await session_client.get_stories(target, story_id)
                if not story:
                    await edit_cb(cb, "❌ <b>Story tidak ditemukan atau sudah kadaluarsa.</b>")
                    try:
                        await cb.answer("❌ Story Not Found", show_alert=True)
                    except Exception:
                        pass
                    return
                
                # Fetch Author details
                try:
                    ent = await session_client.get_chat(target)
                    author_name = getattr(ent, 'title', None) or f"{getattr(ent, 'first_name', '')} {getattr(ent, 'last_name', '')}".strip()
                    author_mention = f"@{ent.username}" if getattr(ent, 'username', None) else f'<a href="tg://user?id={ent.id}">{html.escape(author_name)}</a>'
                    author_id = ent.id
                except:
                    author_mention = f"@{target}" if str(target).isalpha() else f"<code>{target}</code>"
                    author_id = target

                # Use progress callback for "speed" and feedback appearance
                async def progress(current, total):
                    try:
                        percent = (current / total) * 100
                        await edit_cb(cb, f"🔄 <b>Downloading Media... {percent:.1f}%</b>")
                    except Exception:
                        pass

                file_path = await session_client.download_media(story, progress=progress)
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
                        author_info = f"👤 <b>Author:</b> {author_mention}\n🆔 <b>Author ID:</b> <code>{author_id}</code>\n🆔 <b>Story ID:</b> <code>{story_id}</code>"
                        
                        if not final_caption:
                             final_caption = f"📥 <b>Story Downloaded</b>\n\n{author_info}"
                             final_entities = None
                        else:
                             final_caption = f"📥 <b>Story Downloaded</b>\n\n{final_caption}\n\n{author_info}"

                        if story.video:
                            await session_client.send_video(log_chat_id, file_path, caption=final_caption, caption_entities=final_entities)
                        else:
                            await session_client.send_photo(log_chat_id, file_path, caption=final_caption, caption_entities=final_entities)
                        
                        await edit_cb(cb, "✅ <b>Bypass Berhasil!</b> Story telah diupload ke Log Group.")
                        try:
                            await cb.answer("✅ Bypass Success!", show_alert=False)
                        except Exception:
                            pass
                    finally:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                else:
                    await edit_cb(cb, "❌ <b>Gagal mendownload media story untuk bypass.</b>")
                    try:
                        await cb.answer("❌ Download Media Failed", show_alert=True)
                    except Exception:
                        pass
            
            # Notifikasi Log
            await send_log_notification(
                c, 'dlstory_session', index, cb.from_user,
                True, None, {'Target': target, 'StoryID': story_id, 'Method': 'Copy/Bypass'}
            )
            
        except Exception as e:
            err_msg = str(e)
            await edit_cb(cb, f"❌ <b>Gagal:</b> {err_msg}")
            await cb.answer(f"❌ Failed: {err_msg[:30]}", show_alert=True)
            await send_log_notification(
                c, 'dlstory_session', index, cb.from_user,
                False, err_msg, {'Target': target, 'StoryID': story_id, 'Aksi': 'Download story gagal'}
            )
            
        await asyncio.sleep(3)
        await sessions_info_cb_handler(c, cb, index=index, callback_page=page, button_page=button_page)
        
    except (asyncio.TimeoutError, ListenerTimeout):
        await edit_cb(cb, "⏳ Waktu habis. Silakan coba lagi.")
    except Exception as e:
        await edit_cb(cb, f"❌ Error: {str(e)}")


@Altruix.bot.on_callback_query(filters.regex(r"^mnt_toggle_type_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def mnt_toggle_type_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    user_id_str = str(Altruix.clients[index].me.id)
    settings_file = get_db_path("mentions_settings.json")
    
    try:
        if os.path.exists(settings_file):
            with open(settings_file, "r") as f: data = json.load(f)
        else:
            data = {"global": {"mention": True, "auto_log": True, "reply_from_all": False}, "settings": {}, "apply_types": {}}
            
        if "apply_types" not in data: data["apply_types"] = {}
        
        current = data["apply_types"].get(user_id_str, "per_account")
        new_val = "global" if current == "per_account" else "per_account"
        data["apply_types"][user_id_str] = new_val
        
        with open(settings_file, "w") as f:
            json.dump(data, f, indent=4)
        
        await cb.answer(f"Apply Type: {new_val.upper()}")
        await mnt_menu_handler(c, cb, index=index, page=page, button_page=button_page)
    except Exception as e:
        await cb.answer(f"Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^mnt_set_global_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def mnt_set_global_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    user_id_str = str(Altruix.clients[index].me.id)
    settings_file = get_db_path("mentions_settings.json")
    
    try:
        if os.path.exists(settings_file):
            with open(settings_file, "r") as f: data = json.load(f)
        else:
            return await cb.answer("❌ Error: Settings file missing", show_alert=True)
            
        current_config = data.get("settings", {}).get(user_id_str)
        if not current_config:
             return await cb.answer("❌ Current session has no config to set as global", show_alert=True)
        
        if isinstance(current_config, bool):
             current_config = {"mention": current_config, "auto_log": True, "reply_from_all": False}
        elif isinstance(current_config, dict) and "value" in current_config:
             current_config = {"mention": current_config["value"], "auto_log": True, "reply_from_all": False}

        data["global"] = current_config
        with open(settings_file, "w") as f:
            json.dump(data, f, indent=4)
            
        await cb.answer("✅ Successfully set as GLOBAL!", show_alert=True)
        await mnt_menu_handler(c, cb, index=index, page=page, button_page=button_page)
    except Exception as e:
        await cb.answer(f"Error: {e}", show_alert=True)

# ✅ HANDLER BARU: Toggle Mention Settings (RFA, MNT, ALOG)
@Altruix.bot.on_callback_query(filters.regex(r"^mnt_toggle_(rfa|mnt|alog)_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def mnt_toggle_handler(c: Client, cb: CallbackQuery):
    """Toggle mention settings (RFA, MNT, ALOG)"""
    if not await check_authorization(cb): return
    action = cb.matches[0].group(1)
    index = int(cb.matches[0].group(2))
    page = int(cb.matches[0].group(3))
    button_page = int(cb.matches[0].group(4)) if len(cb.matches[0].groups()) >= 4 and cb.matches[0].group(4) else 1
    user_id_str = str(Altruix.clients[index].me.id)
    
    settings_file = get_db_path("mentions_settings.json")
    m_settings = {"global": {"mention": True, "auto_log": True, "reply_from_all": False}, "settings": {}, "apply_types": {}}
    
    if os.path.exists(settings_file):
        try:
            with open(settings_file, "r") as f:
                loaded_data = json.load(f)
                if "global" in loaded_data:
                    m_settings = loaded_data
                else:
                    # Legacy migration logic
                    m_settings["global"]["mention"] = loaded_data.get("mention", True)
                    m_settings["global"]["auto_log"] = loaded_data.get("auto_log", True)
                    m_settings["global"]["reply_from_all"] = loaded_data.get("reply_from_all", False)
        except: pass
    
    if "settings" not in m_settings: m_settings["settings"] = {}
    if "apply_types" not in m_settings: m_settings["apply_types"] = {}

    # Map action to setting key
    key_map = {
        "rfa": "reply_from_all",
        "mnt": "mention",
        "alog": "auto_log"
    }
    
    key = key_map.get(action)
    if key:
        apply_type = m_settings["apply_types"].get(user_id_str, "per_account")
        
        if apply_type == "per_account":
            if user_id_str not in m_settings["settings"]:
                m_settings["settings"][user_id_str] = m_settings["global"].copy()
            
            # Ensure it's a dict
            if not isinstance(m_settings["settings"][user_id_str], dict):
                 m_settings["settings"][user_id_str] = {"mention": bool(m_settings["settings"][user_id_str]), "auto_log": True, "reply_from_all": False}

            m_settings["settings"][user_id_str][key] = not m_settings["settings"][user_id_str].get(key, False)
        else:
            m_settings["global"][key] = not m_settings["global"].get(key, False)

        with open(settings_file, "w") as f:
            json.dump(m_settings, f, indent=4)
        
        readable_name = key.replace('_', ' ').title()
        await cb.answer(f"✅ {readable_name} updated", show_alert=False)
        await mnt_menu_handler(c, cb, index=index, page=page, button_page=button_page)
    else:
        await cb.answer("❌ Invalid action", show_alert=True)


# ✅ HANDLER BARU: Generic Confirmation Handler
@Altruix.bot.on_callback_query(filters.regex(r"^gen_conf_(.+)$"))
@log_errors
async def gen_confirm_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer()
    # Format: gen_conf_{real_callback_data}
    real_data = cb.matches[0].group(1)
    
    # Extract index, callback_page, and optional button_page
    # Format typically: action_{index}_{callback_page} or action_{index}_{callback_page}_{button_page}
    parts = real_data.split("_")
    index = "0"
    callback_page = "1"
    button_page = "1"
    
    # Try to find numeric parts at the end
    numeric_parts = []
    for p in reversed(parts):
        if p.isdigit():
            numeric_parts.insert(0, p)
        else:
            break
            
    if len(numeric_parts) >= 3:
        index = numeric_parts[0]
        callback_page = numeric_parts[1]
        button_page = numeric_parts[2]
    elif len(numeric_parts) == 2:
        index = numeric_parts[0]
        callback_page = numeric_parts[1]
    elif len(numeric_parts) == 1:
        index = numeric_parts[0]
    
    confirm_buttons = [
        [
            InlineKeyboardButton(gt("yes"), real_data),
            InlineKeyboardButton(gt("no"), f"session_info_{index}_{callback_page}_{button_page}")
        ]
    ]
    
    await edit_cb(
        cb,
        text=f"<b>❓ {gt('confirm_action')}</b>\n\n{gt('confirm_msg')}\n\nAksi: <code>{real_data.replace('_', ' ').title()}</code>",
        reply_markup=InlineKeyboardMarkup(confirm_buttons)
    )


# ✅ HANDLER BARU: Download User Photo Start
@Altruix.bot.on_callback_query(filters.regex(r"^dl_uphoto_start_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def dl_uphoto_start_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    user_id = cb.from_user.id
    
    user_dlphoto_state[user_id] = {
        'session_index': index,
        'page': page,
        'button_page': button_page,
        'step': 'waiting_target'
    }
    
    await edit_cb(
        cb,
        text="<b>🖼️ Download Photo Profil</b>\n\n"
             "Silakan kirim <b>Username</b> atau <b>Chat ID</b> user yang ingin didownload fotonya.\n\n"
             "Ketik /cancel untuk membatalkan.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(gt("cancel"), f"session_info_{index}_{page}_{button_page}")]
        ])
    )

# ✅ HANDLER BARU: Purge Amount Handler
@Altruix.bot.on_callback_query(filters.regex(r"^purge_amt_(\d+)_(.+)$"))
@log_errors
async def purge_amt_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    try:
        await cb.answer()
    except Exception:
        pass
    user_id = int(cb.matches[0].group(1))
    amt_choice = cb.matches[0].group(2)
    
    if user_id not in user_purge_state:
        await cb.answer("❌ State tidak ditemukan. Silakan mulai ulang.", show_alert=True)
        return
        
    state = user_purge_state[user_id]
    
    if amt_choice == "custom":
        state['step'] = 'waiting_custom_amount'
        await edit_cb(
            cb,
            text=f"<b>🧹 Purge My Message</b>\n\n"
            f"Chat: <code>{html.escape(state['chat_id'])}</code>\n\n"
            f"Silakan kirim <b>angka</b> jumlah pesan yang ingin dihapus.\n\n"
            f"Ketik /cancel untuk membatalkan.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(gt("cancel"), f"session_info_{state['session_index']}_{state['page']}_{state['button_page']}")]
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
            InlineKeyboardButton("Custom", callback_data=f"purge_del_{user_id}_custom"),
        ],
        [
            InlineKeyboardButton("🔙 Cancel", callback_data=f"session_info_{state['session_index']}_{state['page']}_{state['button_page']}"),
        ]
    ]
    
    await edit_cb(
        cb,
        text=f"<b>🧹 Purge My Message</b>\n\n"
        f"Chat: <code>{html.escape(state['chat_id'])}</code>\n"
        f"Jumlah: <code>{state['amount']}</code>\n\n"
        f"Pilih jeda (delay) antar setiap penghapusan pesan:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ✅ HANDLER BARU: Purge Delay Handler
@Altruix.bot.on_callback_query(filters.regex(r"^purge_del_(\d+)_(.+)$"))
@log_errors
async def purge_del_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer()
    user_id = int(cb.matches[0].group(1))
    delay_val = cb.matches[0].group(2)
    
    if user_id not in user_purge_state:
        await cb.answer("❌ State tidak ditemukan.", show_alert=True)
        return
        
    state = user_purge_state[user_id]
    
    if delay_val == "custom":
        state['step'] = 'waiting_custom_delay'
        await edit_cb(
            cb,
            text=f"<b>🧹 Purge My Message</b>\n\n"
            f"Chat: <code>{html.escape(state['chat_id'])}</code>\n"
            f"Jumlah: <code>{state['amount']}</code>\n\n"
            f"{gt('custom_delay_prompt')}\n\n"
            f"Ketik /cancel untuk membatalkan.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(gt("cancel"), f"session_info_{state['session_index']}_{state['page']}_{state['button_page']}")]
            ])
        )
        return

    delay = float(delay_val)
    state['delay'] = delay
    state['step'] = 'selecting_mode'
    
    # Tampilkan pilihan mode (Reverse)
    buttons = [
        [
            InlineKeyboardButton("🆕 Terbaru (Latest)", callback_data=f"purge_mode_{user_id}_latest"),
            InlineKeyboardButton("⌛ Terlama (Oldest)", callback_data=f"purge_mode_{user_id}_oldest"),
        ],
        [
            InlineKeyboardButton("🔙 Cancel", callback_data=f"session_info_{state['session_index']}_{state['page']}_{state['button_page']}"),
        ]
    ]
    
    await edit_cb(
        cb,
        text=f"<b>🧹 Purge My Message</b>\n\n"
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
    if not await check_authorization(cb): return
    try:
        await cb.answer()
    except Exception:
        pass
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
            InlineKeyboardButton("❌ Tidak, Batalkan", f"session_info_{state['session_index']}_{state['page']}_{state['button_page']}")
        ]
    ]
    
    await edit_cb(
        cb,
        text=f"<b>🧹 Konfirmasi Purge</b>\n\n"
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
    if not await check_authorization(cb): return
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
    
    await edit_cb(cb, f"⏳ <b>Memulai Purge pada {html.escape(chat_id)}...</b>")
    
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
            await edit_cb(cb, "❌ <b>Tidak ada pesan Anda yang ditemukan untuk dihapus.</b>")
            return

        await edit_cb(cb, f"🧹 <b>Menghapus {len(msgs_to_delete)} pesan...</b>")
        
        total_to_purge = len(msgs_to_delete)
        for mid in msgs_to_delete:
            try:
                await session_client.delete_messages(target.id, mid)
                count += 1
                if count % 5 == 0 or count == total_to_purge:
                    try:
                        await edit_cb(cb, gt("purge_progress").format(count=count, total=total_to_purge))
                    except:
                        pass
                await asyncio.sleep(delay)
            except FloodWait as e:
                await asyncio.sleep(e.value)
                await session_client.delete_messages(target.id, mid)
                count += 1
            except Exception:
                error_count += 1
                
        final_text = gt("purge_success_log").format(
            chat=html.escape(target.title or target.first_name),
            count=count,
            error=error_count
        )
        await edit_cb(cb, final_text)
        
        # Generate Chat Link if possible
        chat_link = f"https://t.me/{target.username}" if target.username else None
        chat_display = f"<a href='{chat_link}'>{html.escape(target.title or target.first_name)}</a>" if chat_link else f"<b>{html.escape(target.title or target.first_name)}</b>"

        # Log to Altruix Log Group
        log_buttons = None
        if chat_link:
            log_buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("🌐 Visit Group", url=chat_link)]
            ])

        await send_log_notification(
            c, 'purge_my_message', session_index, cb.from_user,
            True, None, {
                'Chat': f"{chat_display} (<code>{target.id}</code>)",
                'Jumlah': count,
                'Delay': f"{delay}s",
                'Mode': mode.upper(),
                'Account': f"<a href='tg://user?id={me.id}'>{html.escape(me.first_name)}</a>"
            },
            reply_markup=log_buttons
        )
        
    except Exception as e:
        await edit_cb(cb, f"❌ <b>Error saat Purge:</b> <code>{str(e)}</code>")
        await send_log_notification(
            c, 'purge_my_message', session_index, cb.from_user,
            False, str(e), {'Target': chat_id}
        )

# ✅ HANDLER BARU: Download Photo Execution
@Altruix.bot.on_callback_query(filters.regex(r"dl_uphoto_exec_(\d+)"))
@log_errors
async def dl_uphoto_exec_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
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
    await edit_cb(cb, f"⏳ <b>Mendownload foto profil {html.escape(str(target))}...</b>")
    
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
            button_page = state.get('button_page', 1)
            await edit_cb(cb, 
                f"✅ <b>Foto profil {html.escape(user.first_name)} telah dikirim ke Log Group!</b>",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(gt("back"), f"session_info_{session_index}_{page}_{button_page}")]
                ]),
                parse_mode=ParseMode.HTML
            )
            
            await send_log_notification(
                c, 'download_user_photo', session_index, cb.from_user,
                True, None, {'Target': f"{user.first_name} ({user.id})"}
            )
        else:
            await edit_cb(cb, "❌ <b>User tidak memiliki foto profil.</b>")
            
    except Exception as e:
        await edit_cb(cb, f"❌ <b>Gagal mendownload foto:</b> <code>{str(e)}</code>")
        await send_log_notification(
            c, 'download_user_photo', session_index, cb.from_user,
            False, str(e), {'Target': target}
        )

# ✅ HANDLER BARU: Purge My Msg Start
@Altruix.bot.on_callback_query(filters.regex(r"purge_msg_start_(\d+)_(\d+)(?:_(\d+))?"))
@log_errors
async def purge_msg_start_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    user_id = cb.from_user.id
    
    user_purge_state[user_id] = {
        'session_index': index,
        'page': page,
        'button_page': button_page,
        'step': 'waiting_chat'
    }
    
    await edit_cb(cb, 
        text="<b>🧹 Purge My Message</b>\n\n"
             "Fitur ini akan menghapus pesan yang dikirim oleh session ini pada chat tertentu.\n\n"
             "Silakan kirim <b>Username</b> atau <b>Chat ID</b> target chat.\n\n"
             "Ketik /cancel untuk membatalkan.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(gt("cancel"), f"session_info_{index}_{page}_{button_page}")]
        ]),
        parse_mode=ParseMode.HTML
    )


# ✅ HANDLER BARU: Reply PM Mention Confirmation
@Altruix.bot.on_callback_query(filters.regex(r"rpm_conf_(\d+)_(-?\d+)_(\d+)"))
@log_errors
async def rpm_conf_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
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
    
    await edit_cb(cb, 
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
    if not await check_authorization(cb): return
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
        
        await edit_cb(cb, f"✅ Berhasil mengirim reply PM ke {html.escape(target_user.first_name)}.")
        
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
        await edit_cb(cb, f"❌ Gagal mengirim reply PM: {str(e)}")
        await send_log_notification(
            c, 'reply_mention_to_pm', index, cb.from_user,
            False, str(e), {'Chat_ID': chat_id, 'Msg_ID': msg_id}
        )

# ✅ HANDLER BARU: System Control Callback Handler (Restart/Shutdown)
@Altruix.bot.on_callback_query(filters.regex(r"^sys_ctrl_(restart|shutdown)$"))
@log_errors
async def sys_ctrl_cb_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    action = cb.matches[0].group(1)
    user_id = cb.from_user.id
    
    if user_id not in Altruix.auth_users and user_id != Altruix.config.OWNER_ID:
        await cb.answer("⛔ Access Denied!", show_alert=True)
        return

    readable_action = "Restart" if action == "restart" else "Shutdown"
    
    await edit_cb(cb, 
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
    if not await check_authorization(cb): return
    action = cb.matches[0].group(1)
    user_id = cb.from_user.id
    readable_action = "Restart" if action == "restart" else "Shutdown"
    required_code = "11" if action == "shutdown" else "ok"
    
    # Save state
    user_sys_ctrl_state[user_id] = {
        "action": action,
        "step": "waiting_code"
    }
    
    await edit_cb(cb, 
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
@Altruix.bot.on_callback_query(filters.regex(r"^eval_session_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def eval_session_start_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    user_id = cb.from_user.id
    
    user_eval_state[user_id] = {
        "session_index": index,
        "page": page,
        "button_page": button_page,
        "step": "waiting_code"
    }
    
    await edit_cb(cb, 
        f"🐍 <b>Eval Python (Session {index + 1})</b>\n\n"
        f"Silakan kirim kode Python yang ingin dieksekusi.\n"
        f"Kode akan dijalankan di dalam context session tersebut.\n\n"
        f"⚠️ <b>Hati-hati!</b> Kode berbahaya dapat merusak sesi.\n\n"
        f"Ketik /cancel untuk membatalkan.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Cancel", callback_data=f"session_info_{index}_{page}_{button_page}")]
        ]),
        parse_mode=ParseMode.HTML
    )

@Altruix.bot.on_callback_query(filters.regex(r"^eval_exec_(\d+)$"))
@log_errors
async def eval_exec_confirm_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
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
        
    await edit_cb(cb, "⏳ <b>Executing...</b>")
    
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
    
    await edit_cb(cb, 
        f"🐍 <b>Eval Result</b>\n\n{final_output}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data=f"session_info_{index}_{state['page']}_{state.get('button_page', 1)}")]
        ]),
        parse_mode=ParseMode.HTML
    )
    
    del user_eval_state[user_id]


# ✅ HANDLER BARU: Exec Session Input
@Altruix.bot.on_callback_query(filters.regex(r"^exec_session_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def exec_session_start_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    user_id = cb.from_user.id
    
    user_exec_state[user_id] = {
        "session_index": index,
        "page": page,
        "step": "waiting_command"
    }
    
    await edit_cb(cb, 
        f"🖥️ <b>Exec Terminal (Session {index + 1})</b>\n\n"
        f"Silakan kirim perintah terminal (shell) yang ingin dieksekusi.\n"
        f"Perintah akan dijalankan di server host bot ini.\n\n"
        f"⚠️ <b>WARNING:</b> Fitur ini sangat <b>BERBAHAYA</b>. Gunakan dengan bijak!\n\n"
        f"Ketik /cancel untuk membatalkan.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Cancel", callback_data=f"session_info_{index}_{page}_{button_page}")]
        ]),
        parse_mode=ParseMode.HTML
    )

@Altruix.bot.on_callback_query(filters.regex(r"^exec_term_(\d+)$"))
@log_errors
async def exec_term_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
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
        
    await edit_cb(cb, "⏳ <b>Executing...</b>")
    
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
    
    await edit_cb(cb, 
        f"🖥️ <b>Exec Result</b>\n\n{final_output}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data=f"session_info_{index}_{state['page']}_{state.get('button_page', 1)}")]
        ]),
        parse_mode=ParseMode.HTML
    )
    
    del user_exec_state[user_id]



# ============================================================================
# PRIVACY & SECURITY HANDLERS
# ============================================================================

@Altruix.bot.on_callback_query(filters.regex(r"^privacy_menu_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def privacy_menu_cb_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    buttons = [
        [
            InlineKeyboardButton("🚫 Block User", callback_data=f"block_user_input_{index}_{page}_{button_page}"),
            InlineKeyboardButton("✅ Unblock User", callback_data=f"unblock_user_input_{index}_{page}_{button_page}"),
        ],
        [
            InlineKeyboardButton("📞 Phone Privacy", callback_data=f"phone_privacy_menu_{index}_{page}_{button_page}"),
        ],
        [
            InlineKeyboardButton("👥 Group/Channel Privacy", callback_data=f"group_privacy_menu_{index}_{page}_{button_page}"),
        ],
        [
            InlineKeyboardButton("🔙 Back to Session Info", callback_data=f"session_info_{index}_{page}_{button_page}"),
        ]
    ]
    
    await edit_cb(cb, 
        text="<b>🔒 Privacy & Security Settings</b>\n\n"
             "Kelola privasi dan keamanan akun Anda dari sini.\n"
             "• <b>Block/Unblock:</b> Blokir atau buka blokir pengguna.\n"
             "• <b>Phone Privacy:</b> Siapa yang bisa melihat/mencari nomor Anda.\n"
             "• <b>Group Privacy:</b> Siapa yang bisa menambahkan Anda ke grup.",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )

@Altruix.bot.on_callback_query(filters.regex(r"^(block|unblock)_user_input_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def block_unblock_input_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer()
    action = cb.matches[0].group(1) # block / unblock
    index = int(cb.matches[0].group(2))
    page = int(cb.matches[0].group(3))
    button_page = int(cb.matches[0].group(4)) if len(cb.matches[0].groups()) >= 4 and cb.matches[0].group(4) else 1
    user_id = cb.from_user.id
    
    user_privacy_state[user_id] = {
        'action': f"{action}_user",
        'session_index': index,
        'page': page,
        'button_page': button_page,
        'step': 'waiting_target'
    }
    
    readable_action = "Blokir (Block)" if action == "block" else "Buka Blokir (Unblock)"
    
    await edit_cb(cb, 
        text=f"<b>🚫 {readable_action} User</b>\n\n"
             "Silakan kirim <b>Username</b> atau <b>User ID</b> target.\n\n"
             "Contoh: <code>@username</code> atau <code>123456789</code>\n\n"
             "Kirim <code>/cancel</code> untuk membatalkan.",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
             [InlineKeyboardButton("🔙 Cancel", callback_data=f"privacy_menu_{index}_{page}_{button_page}")]
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
@Altruix.bot.on_callback_query(filters.regex(r"^phone_privacy_menu_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def phone_privacy_menu_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    buttons = [
        [
            InlineKeyboardButton("👀 Who can SEE my number?", callback_data="ignore"),
        ],
        [
            InlineKeyboardButton("Everybody", callback_data=f"set_pp_see_{index}_{page}_{button_page}_all"),
            InlineKeyboardButton("Contacts", callback_data=f"set_pp_see_{index}_{page}_{button_page}_contacts"),
            InlineKeyboardButton("Nobody", callback_data=f"set_pp_see_{index}_{page}_{button_page}_nobody"),
        ],
        [
            InlineKeyboardButton("🔍 Who can FIND by number?", callback_data="ignore"),
        ],
        [
            InlineKeyboardButton("Everybody", callback_data=f"set_pp_find_{index}_{page}_{button_page}_all"),
            InlineKeyboardButton("Contacts", callback_data=f"set_pp_find_{index}_{page}_{button_page}_contacts"),
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data=f"privacy_menu_{index}_{page}_{button_page}"),
        ]
    ]
    
    await edit_cb(cb, 
        text="<b>📞 Phone Number Privacy</b>\n\n"
             "Atur siapa yang bisa melihat nomor telepon Anda dan siapa yang bisa menemukan Anda via nomor telepon.\n\n"
             "⚠️ <i>Perubahan akan langsung diterapkan ke Telegram.</i>",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )

@Altruix.bot.on_callback_query(filters.regex(r"^set_pp_(see|find)_(\d+)_(\d+)_(\d+)_(.+)$"))
@log_errors
async def set_phone_privacy_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    type_ = cb.matches[0].group(1) # see / find
    index = int(cb.matches[0].group(2))
    page = int(cb.matches[0].group(3))
    button_page = int(cb.matches[0].group(4)) 
    value = cb.matches[0].group(5) # all / contacts / nobody
    
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
@Altruix.bot.on_callback_query(filters.regex(r"^group_privacy_menu_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def group_privacy_menu_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    buttons = [
        [
            InlineKeyboardButton("Everyone", callback_data=f"set_gp_{index}_{page}_{button_page}_all"),
            InlineKeyboardButton("Contacts", callback_data=f"set_gp_{index}_{page}_{button_page}_contacts"),
            InlineKeyboardButton("Nobody", callback_data=f"set_gp_{index}_{page}_{button_page}_nobody"),
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data=f"privacy_menu_{index}_{page}_{button_page}"),
        ]
    ]
    
    await edit_cb(cb, 
        text="<b>👥 Group & Channel Privacy</b>\n\n"
             "<b>Who can add me to group chats?</b>\n"
             "Atur siapa yang bisa menambahkan Anda ke grup dan channel secara otomatis.",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )

@Altruix.bot.on_callback_query(filters.regex(r"^set_gp_(\d+)_(\d+)_(\d+)_(.+)$"))
@log_errors
async def set_group_privacy_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3))
    value = cb.matches[0].group(4)
    
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

@Altruix.bot.on_callback_query(filters.regex(r"^chat_stats_scan_(\d+)_(\d+)_(\d+)(?:_(force))?$"))
@log_errors
async def chat_stats_scan_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3))
    force = cb.matches[0].group(4) == "force"
    user_id = cb.from_user.id
    
    if index >= len(Altruix.clients):
        await cb.answer("Session unavailable", show_alert=True)
        return
        
    session = Altruix.clients[index]
    session_info = getattr(session, 'myself', None) or await session.get_me()
    
    # Caching Logic
    cache_file = get_db_path("chat_stats_cache.json")
    cache_data = {}
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r") as f:
                cache_data = json.load(f)
        except: pass
    
    session_id_str = str(session_info.id)
    now = datetime.now().timestamp()
    
    # Check if cache exists and is fresh (e.g., 1 hour)
    if not force and session_id_str in cache_data:
        entry = cache_data[session_id_str]
        if now - entry.get("timestamp", 0) < 3600: # 1 hour cache
            stats = entry.get("stats")
            await cb.answer("📊 Loading from cache...")
            await display_chat_stats(c, cb, session_info, stats, index, page, button_page, cached=True)
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
         scanning_msg = await edit_cb(cb, f"🔍 <b>Scanning chats... (0 found)</b>")
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
                
            # Check Admin (Non-Creator) - improved detection
            else:
                # Method 1: Check is_admin attribute
                is_admin = getattr(chat, "is_admin", False)
                
                # Method 2: Check privileges
                has_privileges = False
                privileges = getattr(chat, "privileges", None)
                if privileges:
                    # Check if has any admin privilege
                    has_privileges = (
                        getattr(privileges, "can_manage_chat", False) or
                        getattr(privileges, "can_delete_messages", False) or
                        getattr(privileges, "can_manage_video_chats", False) or
                        getattr(privileges, "can_restrict_members", False) or
                        getattr(privileges, "can_promote_members", False) or
                        getattr(privileges, "can_change_info", False) or
                        getattr(privileges, "can_invite_users", False) or
                        getattr(privileges, "can_pin_messages", False)
                    )
                
                if is_admin or has_privileges:
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

    await display_chat_stats(c, cb, session_info, stats, index, page, button_page)

async def display_chat_stats(c, cb, session_info, stats, index, page, button_page, cached=False):
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
    
    buttons = [
        [
            InlineKeyboardButton("🔄 Update from Server", callback_data=f"chat_stats_scan_{index}_{page}_{button_page}_force"),
            InlineKeyboardButton("🔙 Back to Session Info", callback_data=f"session_info_{index}_{page}_{button_page}")
        ]
    ]
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)


# ============================================================================
# SYSTEM CONTROL HANDLERS
# ============================================================================

@Altruix.bot.on_callback_query(filters.regex("^sys_ctrl_restart$"))
@log_errors
async def sys_restart_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer("Restarting...", show_alert=True)
    try:
        import sys
        import subprocess
        args = [sys.executable, "-m", "Main"]
        if os.name == 'nt':
            subprocess.Popen(args, creationflags=subprocess.CREATE_NEW_CONSOLE)
            sys.exit(0)
        else:
            os.execv(sys.executable, args)
    except Exception as e:
        await cb.answer(f"Failed to restart: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex("^sys_ctrl_shutdown$"))
@log_errors
async def sys_shutdown_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer("Shutting down...", show_alert=True)
    try:
        import sys
        sys.exit(0)
    except:
        pass

# ============================================================================
# LAUCREATE INTEGRATION
# ============================================================================

# ============================================================================
# LAUCREATE INTEGRATION (Interactive UI)
# ============================================================================

# Default Configuration
# ✅ NEW: Startup Message Menu
@Altruix.bot.on_callback_query(filters.regex(r"^startup_menu_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def startup_menu_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    mode = await Altruix.config.get_env(f"STARTUP_MSG_{index}") or "default"
    apply_type = await Altruix.config.get_env(f"STARTUP_MSG_TYPE_{index}") or "per_account"
    
    status_map = {"off": "❌ OFF", "default": "✅ DEFAULT", "custom": "✨ CUSTOM"}
    mode_label = status_map.get(str(mode).lower(), "✅ DEFAULT")
    type_label = gt("global") if apply_type == "global" else gt("per_account")
    
    text = (
        f"{gt('startup_settings_title')}\n\n"
        f"• <b>Status:</b> <code>{mode_label}</code>\n"
        f"• <b>{gt('apply_type')}:</b> <code>{type_label}</code>\n\n"
        f"Pilih opsi di bawah untuk mengatur pesan pembuka otomatis."
    )
    
    buttons = [
        [
            InlineKeyboardButton(f"🔄 Mode: {mode_label}", f"startup_set_val_{index}_{page}_{button_page}"),
        ],
        [
            InlineKeyboardButton(f"⚙️ {gt('apply_type')}: {type_label}", f"startup_toggle_type_{index}_{page}_{button_page}"),
        ],
        [
            InlineKeyboardButton("📝 Edit Custom Msg", f"startup_custom_menu_{index}_{page}_{button_page}"),
            InlineKeyboardButton(gt("set_as_global"), f"startup_set_global_{index}_{page}_{button_page}"),
        ],
        [
            InlineKeyboardButton(gt("back"), f"session_info_{index}_{page}_{button_page}"),
        ]
    ]
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^startup_set_val_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def startup_set_val_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    key = f"STARTUP_MSG_{index}"
    
    current = await Altruix.config.get_env(key) or "default"
    states = ["off", "default", "custom"]
    try:
        new_idx = (states.index(str(current).lower()) + 1) % len(states)
    except:
        new_idx = 1
        
    new_val = states[new_idx]
    await Altruix.config.sync_env_to_db(key, new_val, upsert=True)
    setattr(Altruix.config, key, new_val)
    
    await cb.answer(f"Startup: {new_val.upper()}")
    cb.matches = [re.match(r"^startup_menu_(\d+)_(\d+)_(\d+)$", f"startup_menu_{index}_{page}_{button_page}")]
    await startup_menu_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^startup_toggle_type_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def startup_toggle_type_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    key = f"STARTUP_MSG_TYPE_{index}"
    
    current = await Altruix.config.get_env(key) or "per_account"
    new_val = "global" if current == "per_account" else "per_account"
    
    await Altruix.config.sync_env_to_db(key, new_val, upsert=True)
    setattr(Altruix.config, key, new_val)
    
    await cb.answer(f"Apply Type: {new_val.upper()}")
    cb.matches = [re.match(r"^startup_menu_(\d+)_(\d+)_(\d+)$", f"startup_menu_{index}_{page}_{button_page}")]
    await startup_menu_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^startup_set_global_(\d+)_(\d+)$"))
@log_errors
async def startup_set_global_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    index = int(cb.matches[0].group(1))
    
    current_custom = await Altruix.config.get_env(f"STARTUP_CUSTOM_MSG_{index}")
    if not current_custom:
        await cb.answer("❌ Pesan kustom belum diatur untuk akun ini.", show_alert=True)
        return
        
    await Altruix.config.sync_env_to_db("STARTUP_CUSTOM_MSG_GLOBAL", current_custom, upsert=True)
    setattr(Altruix.config, "STARTUP_CUSTOM_MSG_GLOBAL", current_custom)
    
    await cb.answer("✅ Berhasil dijadikan pesan GLOBAL!", show_alert=True)

# ✅ NEW: Help Info Menu
@Altruix.bot.on_callback_query(filters.regex(r"^help_info_menu_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def help_info_menu_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    mode = await Altruix.config.get_env(f"HELP_INFO_{index}") or "default"
    apply_type = await Altruix.config.get_env(f"HELP_INFO_TYPE_{index}") or "per_account"
    
    status_map = {"default": "✅ DEFAULT", "custom": "✨ CUSTOM"}
    mode_label = status_map.get(str(mode).lower(), "✅ DEFAULT")
    type_label = gt("global") if apply_type == "global" else gt("per_account")
    
    text = (
        f"{gt('help_info_settings_title')}\n\n"
        f"• <b>Status:</b> <code>{mode_label}</code>\n"
        f"• <b>{gt('apply_type')}:</b> <code>{type_label}</code>\n\n"
        f"Pilih opsi di bawah untuk mengatur pesan bantuan kustom."
    )
    
    buttons = [
        [
            InlineKeyboardButton(f"🔄 Mode: {mode_label}", f"help_info_set_val_{index}_{page}_{button_page}"),
        ],
        [
            InlineKeyboardButton(f"⚙️ {gt('apply_type')}: {type_label}", f"help_info_toggle_type_{index}_{page}_{button_page}"),
        ],
        [
            InlineKeyboardButton("📝 Edit Custom Msg", f"help_info_custom_menu_{index}_{page}_{button_page}"),
            InlineKeyboardButton(gt("set_as_global"), f"help_info_set_global_{index}_{page}_{button_page}"),
        ],
        [
            InlineKeyboardButton(gt("back"), f"session_info_{index}_{page}_{button_page}"),
        ]
    ]
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^help_info_set_val_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def help_info_set_val_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    key = f"HELP_INFO_{index}"
    
    current = await Altruix.config.get_env(key) or "default"
    states = ["default", "custom"]
    try:
        new_idx = (states.index(str(current).lower()) + 1) % len(states)
    except:
        new_idx = 0
        
    new_val = states[new_idx]
    await Altruix.config.sync_env_to_db(key, new_val, upsert=True)
    setattr(Altruix.config, key, new_val)
    
    await cb.answer(f"Help Info: {new_val.upper()}")
    cb.matches = [re.match(r"^help_info_menu_(\d+)_(\d+)_(\d+)$", f"help_info_menu_{index}_{page}_{button_page}")]
    await help_info_menu_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^help_info_toggle_type_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def help_info_toggle_type_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    key = f"HELP_INFO_TYPE_{index}"
    
    current = await Altruix.config.get_env(key) or "per_account"
    new_val = "global" if current == "per_account" else "per_account"
    
    await Altruix.config.sync_env_to_db(key, new_val, upsert=True)
    setattr(Altruix.config, key, new_val)
    
    await cb.answer(f"Apply Type: {new_val.upper()}")
    cb.matches = [re.match(r"^help_info_menu_(\d+)_(\d+)_(\d+)$", f"help_info_menu_{index}_{page}_{button_page}")]
    await help_info_menu_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^help_info_set_global_(\d+)_(\d+)$"))
@log_errors
async def help_info_set_global_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    index = int(cb.matches[0].group(1))
    
    current_custom = await Altruix.config.get_env(f"HELP_INFO_CUSTOM_MSG_{index}")
    if not current_custom:
        await cb.answer("❌ Pesan kustom belum diatur untuk akun ini.", show_alert=True)
        return
        
    await Altruix.config.sync_env_to_db("HELP_INFO_CUSTOM_MSG_GLOBAL", current_custom, upsert=True)
    setattr(Altruix.config, "HELP_INFO_CUSTOM_MSG_GLOBAL", current_custom)
    
    await cb.answer("✅ Berhasil dijadikan pesan GLOBAL!", show_alert=True)


@Altruix.bot.on_callback_query(filters.regex(r"^startup_custom_menu_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def startup_custom_menu_handler(c: Client, cb: CallbackQuery):
    """Handler untuk menu kustomisasi startup message"""
    if not await check_authorization(cb): return
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    current_msg = await Altruix.config.get_env(f"STARTUP_CUSTOM_MSG_{index}") or "(Belum diatur)"
    
    text = (
        f"<b>🚀 Custom Startup Message Info</b>\n\n"
        f"Anda dapat mengatur pesan pembuka kustom untuk sesi ini.\n\n"
        f"<b>Placeholders yang didukung:</b>\n"
        f"• <code>{{first_name}}</code> / <code>(first name)</code>\n"
        f"• <code>{{last_name}}</code> / <code>(last name)</code>\n"
        f"• <code>{{mention}}</code> / <code>(mention)</code>\n"
        f"• <code>{{user_name}}</code> / <code>(user name)</code>\n"
        f"• <code>{{user_id}}</code> / <code>(user id)</code>\n"
        f"• <code>{{ub_version}}</code> / <code>(userbot version)</code>\n"
        f"• <code>{{pyrogram_version}}</code> / <code>(pyrogram version)</code>\n"
        f"• <code>{{python_version}}</code> / <code>(python version)</code>\n"
        f"• <code>{{ub_plugins}}</code> / <code>(userbot plugins)</code>\n"
        f"• <code>{{bot_plugins}}</code> / <code>(bot plugins)</code>\n"
        f"• <code>{{index}}</code> / <code>(session index)</code>\n\n"
        f"<b>Pesan Saat Ini:</b>\n<code>{html.escape(str(current_msg))}</code>\n\n"
        f"<i>Gunakan tombol di bawah untuk mengubah pesan atau kembali.</i>"
    )
    
    buttons = [
        [
            InlineKeyboardButton("📝 Edit Startup Message", f"startup_custom_input_{index}_{page}_{button_page}"),
        ],
        [
            InlineKeyboardButton("🔙 Back", f"startup_menu_{index}_{page}_{button_page}"),
        ]
    ]
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)


@Altruix.bot.on_callback_query(filters.regex(r"^help_info_custom_menu_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def help_info_custom_menu_handler(c: Client, cb: CallbackQuery):
    """Handler untuk menu kustomisasi help info message"""
    if not await check_authorization(cb): return
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    # 🕵️ Get Current Logic Type
    apply_type = await Altruix.config.get_env(f"HELP_INFO_TYPE_{index}") or "per_account"
    
    # 🕵️ Get Message based on type for preview
    if apply_type == "global":
        current_msg = await Altruix.config.get_env("HELP_INFO_CUSTOM_MSG_GLOBAL") or "(Global belum diatur)"
    else:
        current_msg = await Altruix.config.get_env(f"HELP_INFO_CUSTOM_MSG_{index}") or "(Belum diatur)"
    
    type_label = gt("global") if apply_type == "global" else gt("per_account")
    
    text = (
        f"<b>❇️ Custom Help Info Message Info</b>\n\n"
        f"Anda dapat mengatur pesan help menu kustom untuk sesi ini.\n\n"
        f"• <b>{gt('apply_type')}:</b> <code>{type_label}</code>\n\n"
        f"<b>Placeholders yang didukung:</b>\n"
        f"• <code>{{ub_version}}</code> / <code>(userbot version)</code>\n"
        f"• <code>{{pyrogram_version}}</code> / <code>(pyrogram version)</code>\n"
        f"• <code>{{python_version}}</code> / <code>(python version)</code>\n"
        f"• <code>{{ub_plugins}}</code> / <code>(userbot plugins)</code>\n"
        f"• <code>{{bot_plugins}}</code> / <code>(bot plugins)</code>\n"
        f"• <code>{{mention}}</code> / <code>(mention session)</code>\n"
        f"• <code>{{index}}</code> / <code>(session index)</code>\n\n"
        f"<b>Pesan Saat Ini ({type_label}):</b>\n<code>{html.escape(str(current_msg))}</code>\n\n"
        f"<i>Gunakan tombol di bawah untuk mengubah pesan atau kembali.</i>"
    )
    
    buttons = [
        [
            InlineKeyboardButton(f"🔄 {gt('apply_type')}: {type_label}", f"help_info_toggle_type_{index}_{page}_{button_page}"),
        ],
        [
            InlineKeyboardButton("📝 Edit Help Msg", f"help_info_custom_input_{index}_{page}_{button_page}"),
            InlineKeyboardButton(gt("set_as_global"), f"help_info_set_global_{index}_{page}_{button_page}"),
        ],
        [
            InlineKeyboardButton("🔙 Back", f"help_info_menu_{index}_{page}_{button_page}"),
        ]
    ]
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)


@Altruix.bot.on_callback_query(filters.regex(r"^help_info_custom_input_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def help_info_custom_input_handler(c: Client, cb: CallbackQuery):
    """Memulai proses input pesan help kustom"""
    if not await check_authorization(cb): return
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    user_id = cb.from_user.id
    
    user_privacy_state[user_id] = {
        'session_index': index,
        'page': page,
        'button_page': button_page,
        'step': 'waiting_help_custom_msg'
    }
    
    await edit_cb(cb, 
        f"⌨️ <b>Input Custom Help Message</b>\n\n"
        f"Silakan kirim pesan help menu kustom Anda sekarang.\n"
        f"Gunakan placeholders seperti <code>(userbot version)</code>, <code>{{ub_version}}</code> dll.\n\n"
        f"<i>Kirim /cancel untuk membatalkan.</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(gt("cancel"), callback_data=f"help_info_custom_menu_{index}_{page}_{button_page}")]])
    )


@Altruix.bot.on_callback_query(filters.regex(r"^help_info_toggle_type_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def help_info_toggle_type_callback(c: Client, cb: CallbackQuery):
    """Toggle antara mode Per-Akun dan Global"""
    if not await check_authorization(cb): return
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    current_type = await Altruix.config.get_env(f"HELP_INFO_TYPE_{index}") or "per_account"
    new_type = "global" if current_type == "per_account" else "per_account"
    
    await Altruix.config.add_env_to_db(f"HELP_INFO_TYPE_{index}", new_type, upsert=True)
    await cb.answer(f"✅ Mode diubah ke: {new_type.upper()}")
    cb.matches = [re.match(r"^help_info_custom_menu_(\d+)_(\d+)_(\d+)$", f"help_info_custom_menu_{index}_{page}_{button_page}")]
    await help_info_custom_menu_handler(c, cb)


@Altruix.bot.on_callback_query(filters.regex(r"^help_info_set_global_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def help_info_set_global_callback(c: Client, cb: CallbackQuery):
    """Menjadikan pesan kustom akun ini sebagai pesan Global"""
    if not await check_authorization(cb): return
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    current_msg = await Altruix.config.get_env(f"HELP_INFO_CUSTOM_MSG_{index}")
    if not current_msg:
        return await cb.answer("❌ Akun ini belum memiliki pesan kustom untuk dibagikan.", show_alert=True)
        
    await Altruix.config.add_env_to_db("HELP_INFO_CUSTOM_MSG_GLOBAL", current_msg, upsert=True)
    await cb.answer("✅ Berhasil! Pesan kustom akun ini sekarang menjadi pesan GLOBAL.", show_alert=True)
    cb.matches = [re.match(r"^help_info_custom_menu_(\d+)_(\d+)_(\d+)$", f"help_info_custom_menu_{index}_{page}_{button_page}")]
    await help_info_custom_menu_handler(c, cb)


@Altruix.bot.on_callback_query(filters.regex(r"^startup_custom_input_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def startup_custom_input_handler(c: Client, cb: CallbackQuery):
    """Memulai proses input pesan startup kustom"""
    if not await check_authorization(cb): return
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    user_id = cb.from_user.id
    
    # Simpan state ke global (atau local state dictionary)
    user_privacy_state[user_id] = {
        'session_index': index,
        'page': page,
        'button_page': button_page,
        'step': 'waiting_startup_custom_msg'
    }
    
    await edit_cb(
        cb,
        text=f"⌨️ <b>Input Custom Startup Message</b>\n\n"
        f"Silakan kirim pesan kustom Anda sekarang.\n"
        f"Gunakan placeholders seperti <code>{{mention_first_name}}</code> dll.\n\n"
        f"Ketik <code>/cancel</code> untuk membatalkan.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(gt("cancel"), f"startup_custom_menu_{index}_{page}")]])
    )


@Altruix.bot.on_callback_query(filters.regex(r"^bot_controls_menu$"))
@log_errors
async def bot_controls_menu_handler(c: Client, cb: CallbackQuery):
    """Handler untuk HUB menu kontrol Bot (Default vs Custom)"""
    if not await check_authorization(cb): return
    await cb.answer()
    
    txt = (
        f"{Altruix.get_string('bot_controls_title')}\n\n"
        f"Please select the type of bot you want to manage:"
    )
    
    buttons = [
        [
            InlineKeyboardButton(Altruix.get_string("default_bot_settings"), "default_bot_settings"),
        ],
        [
            InlineKeyboardButton(Altruix.get_string("pm_logger_control"), "open_pmlu_settings_owner"),
            InlineKeyboardButton(Altruix.get_string("mention_control"), "open_mentions_settings_owner"),
        ],
        [
            InlineKeyboardButton(Altruix.get_string("custom_bot_manager"), "custom_bot_manager"),
            InlineKeyboardButton("🔘 Callback Logger", callback_data="cb_logger_settings"),
        ],
        [
            InlineKeyboardButton(Altruix.get_string("back"), "settings_menu"),
        ]
    ]
    
    await edit_cb(cb, txt, reply_markup=InlineKeyboardMarkup(buttons))


@Altruix.bot.on_callback_query(filters.regex(r"^default_bot_settings$"))
@log_errors
async def default_bot_settings_handler(c: Client, cb: CallbackQuery):
    """Handler untuk menu kontrol Bot Assistant (PM, Mention, Join Logs)"""
    if not await check_authorization(cb): return
    await cb.answer()
    
    # Load statuses from files
    def get_status(filename, key="enabled", nested=False):
        f_path = get_db_path(filename)
        if not os.path.exists(f_path):
            return "OFF ❌"
        try:
            with open(f_path, "r") as f:
                data = json.load(f)
                if nested:
                    val = any(v.get(key, False) for v in (data.get("sessions", {}) or data.get("settings", {})).values() if isinstance(v, dict))
                else:
                    val = data.get(key, False)
                return "ON ✅" if val else "OFF ❌"
        except:
            return "OFF ❌"

    pm_status = get_status("pm_logger_bot_settings.json", nested=True)
    mnt_status = get_status("mention_logger_bot_settings.json", nested=True)  # Bot mention logger
    join_status = get_status("join_logger_settings.json")
    cb_status = get_status("callback_logger_settings.json", nested=True)
    rml_status = get_status("reply_manager_settings.json")
    
    # Generate timestamp to avoid MESSAGE_NOT_MODIFIED
    ts = datetime.now().strftime("%H:%M:%S")
    
    text = (
        f"<b>🤖 Bot Assistant Controls</b>\n\n"
        f"Gunakan tombol di bawah untuk mengatur log yang dikelola oleh Bot Assistant.\n\n"
        f"• <b>PM Log:</b> {pm_status}\n"
        f"• <b>Mention Log:</b> {mnt_status}\n"
        f"• <b>Join Log:</b> {join_status}\n"
        f"• <b>Reply Manager Log:</b> {rml_status}\n\n"
        f"<i>Last Update: {ts}</i>"
    )
    
    buttons = [
        [
            InlineKeyboardButton(f"🤖 PM Log: {pm_status}", "bot_log_pml_toggle"),
        ],
        [
            InlineKeyboardButton(f"🤖 Mention Log: {mnt_status}", "bot_log_mnt_toggle"),
        ],
        [
            InlineKeyboardButton(f"🤖 Join Log: {join_status}", "bot_log_joinl_toggle"),
            InlineKeyboardButton(f"🤖 Reply Log: {rml_status}", "bot_log_rml_toggle"),
        ],
        [
            InlineKeyboardButton("📤 Export Log Group Link", "export_log_link_confirmation"),
        ],
        [
            InlineKeyboardButton("🔙 Back to Hub", "bot_controls_menu"),
        ]
    ]
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons))

@Altruix.bot.on_callback_query(filters.regex(r"^bot_log_(pml|mnt|joinl|cbl|rml)_toggle$"))
@log_errors
async def bot_logger_toggle_handler(c: Client, cb: CallbackQuery):
    # Authorization check
    if not await check_authorization(cb):
        return
    
    target = cb.matches[0].group(1)
    
    file_map = {
        "pml": get_db_path("pm_logger_bot_settings.json"),
        "mnt": get_db_path("mention_logger_bot_settings.json"),  # Bot mention logger (independent from userbot)
        "joinl": get_db_path("join_logger_settings.json"),
        "cbl": get_db_path("callback_logger_settings.json"),
        "rml": get_db_path("reply_manager_settings.json")
    }
    
    filename = file_map.get(target)
    if not filename:
        await cb.answer("Invalid target", show_alert=True)
        return
        
    try:
        if os.path.exists(filename):
            with open(filename, "r") as f: data = json.load(f)
        else:
            data = {"settings": {"enabled": False}}
            
        if target == "mnt":
            # Bot Mention Logger expects nested "settings" key (same as PM logger)
            if "settings" not in data:
                data["settings"] = {}
            data["settings"]["enabled"] = not data["settings"].get("enabled", False)
            status = data["settings"]["enabled"]
        elif target == "pml" or target == "cbl":
            # PM Logger Bot and Callback Logger expect nested "settings" key
            if "settings" not in data:
                data["settings"] = {}
            
            # Default to ON for CBL if just created
            if target == "cbl" and not os.path.exists(filename):
                data["settings"]["enabled"] = True
            else:
                data["settings"]["enabled"] = not data["settings"].get("enabled", False)
            
            status = data["settings"]["enabled"]
        else:
            data["enabled"] = not data.get("enabled", False)
            status = data["enabled"]
            
        with open(filename, "w") as f: json.dump(data, f, indent=2)
        
        await cb.answer(f"Bot Admin {target.upper()} Log: {'ON' if status else 'OFF'}")
        await default_bot_settings_handler(c, cb)
    except Exception as e:
        await cb.answer(f"Error: {e}", show_alert=True)


@Altruix.bot.on_callback_query(filters.regex(r"^export_log_link_confirmation$"))
@log_errors
async def export_log_link_confirmation_handler(c: Client, cb: CallbackQuery):
    """Handler untuk konfirmasi export log link"""
    if not await check_authorization(cb): return
    await cb.answer()
    
    confirmation_buttons = [
        [
            InlineKeyboardButton("✅ Ya, Export", "export_log_link_execute"),
            InlineKeyboardButton("❌ Batal", "bot_controls_menu")
        ]
    ]
    
    await edit_cb(
        cb,
        text="<b>📤 Konfirmasi Export Log Link</b>\n\n"
             "Apakah Anda yakin ingin mengekspor link invite Log Group?\n\n"
             "⚠️ <b>Catatan:</b>\n"
             "• Link ini akan dikirim ke chat ini\n"
             "• Aksi ini akan dicatat di log group",
        reply_markup=InlineKeyboardMarkup(confirmation_buttons)
    )


@Altruix.bot.on_callback_query(filters.regex(r"^export_log_link_execute$"))
@log_errors
async def export_log_link_execute_handler(c: Client, cb: CallbackQuery):
    """Handler untuk eksekusi export log link"""
    if not await check_authorization(cb): return
    await cb.answer("⏳ Memproses...", show_alert=False)
    
    # Dapatkan LOG_CHAT_ID
    log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))
    
    try:
        # Coba ekspor link baru
        try:
            invite_link = await Altruix.bot.export_chat_invite_link(log_chat_id)
            link = invite_link
        except Exception:
            # Fallback jika export gagal, coba get_chat
            chat = await Altruix.bot.get_chat(log_chat_id)
            link = chat.invite_link
            if not link:
                # Jika masih tidak ada, coba create link baru (membutuhkan admin rights lebih spesifik)
                new_link = await Altruix.bot.create_chat_invite_link(log_chat_id)
                link = new_link.invite_link

        if not link:
            raise Exception("Tidak dapat mendapatkan link invite. Pastikan bot adalah admin di log group.")

        await edit_cb(
            cb,
            text=f"<b>✅ Log Group Invite Link</b>\n\n"
                 f"Link: <code>{link}</code>\n\n"
                 f"⚠️ Harap simpan link ini dengan aman.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", "bot_controls_menu")]])
        )
        
        # Kirim notifikasi log
        await send_log_notification(
            c, 'export_log_link', 0, cb.from_user, 
            True, None, {'Link': 'Successfully exported'}
        )
        
    except Exception as e:
        error_msg = str(e)
        await edit_cb(
            cb,
            text=f"❌ <b>Gagal Export Link:</b>\n<code>{html.escape(error_msg)}</code>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", "bot_controls_menu")]])
        )
        
        # Kirim notifikasi error ke log group
        await send_log_notification(
            c, 'export_log_link', 0, cb.from_user, 
            False, error_msg, {}
        )

@Altruix.bot.on_callback_query(filters.regex(r"^mntf_menu_(\d+)_(\d+)$"))
@log_errors
async def mnt_filters_menu_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    
    text = (
        "<b>🔍 Mention Logger Message Filters</b>\n\n"
        "Pilih kategori di bawah untuk mengatur jenis pesan yang akan dicatat saat Anda dimention.\n"
        "Hal ini membantu mengurangi spam di Log Group Anda."
    )
    buttons = [
        [
            InlineKeyboardButton("Filter Settings", f"mntfl_list_{index}_{page}"),
        ],
        [InlineKeyboardButton("🔙 Back to Mention Menu", f"mnt_menu_{index}_{page}")]
    ]
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^mntfl_list_(\d+)_(\d+)$"))
@log_errors
async def mntf_list_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    
    filename = get_db_path("mentions_settings.json")
    if os.path.exists(filename):
        with open(filename, "r") as f: data = json.load(f)
        filters = data.get("filters", {})
    else: filters = {}
    
    text = f"<b>🔍 Mention Message Filters</b>\n\nKlik untuk toggle filter (✅ = Log, ❌ = Ignore):"
    buttons = []
    row = []
    # Same types as PM Logger for consistency
    for m_type in ["text", "photo", "video", "document", "audio", "voice", "sticker", "animation", "video_note"]:
        val = filters.get(m_type, True)
        status = "✅" if val else "❌"
        row.append(InlineKeyboardButton(f"{status} {m_type.capitalize()}", f"mntft_toggle_{m_type}_{index}_{page}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row: buttons.append(row)
    buttons.append([InlineKeyboardButton("🔙 Back to Filters Menu", f"mntf_menu_{index}_{page}")])
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^mntft_toggle_(.+)_(\d+)_(\d+)$"))
@log_errors
async def mntf_toggle_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    m_type = cb.matches[0].group(1)
    index = int(cb.matches[0].group(2))
    page = int(cb.matches[0].group(3))
    
    filename = get_db_path("mentions_settings.json")
    if os.path.exists(filename):
        with open(filename, "r") as f: data = json.load(f)
    else: data = {}
    
    if "filters" not in data: data["filters"] = {}
    
    current = data["filters"].get(m_type, True)
    data["filters"][m_type] = not current
    
    with open(filename, "w") as f: json.dump(data, f, indent=2)
    await cb.answer(f"Mention Filter {m_type}: {'Enabled' if not current else 'Disabled'}")
    await mntf_list_handler(c, cb)

# ============================================================================
# 🔍 TRACK PROFILE (SANGMATA) HANDLERS
# ============================================================================

@Altruix.bot.on_callback_query(filters.regex(r"^track_profile_start_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def track_profile_start_cb_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    user_id = cb.from_user.id
    
    Altruix.user_track_state[user_id] = {
        "session_index": index,
        "page": page,
        "button_page": button_page,
        "step": "waiting_target_id"
    }
    
    await cb.answer()
    await edit_cb(
        cb,
        text=f"🔍 <b>Track Profile (Session {index + 1})</b>\n\n"
        f"Silakan kirimkan <b>User ID</b> atau <b>Username</b> user yang ingin dilacak.\n"
        f"Userbot akan mengirimkan perintah <code>/id</code> ke @SangMata_beta_bot.\n\n"
        f"Ketik /cancel untuk membatalkan.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data=f"session_info_{index}_{page}_{button_page}")]
        ])
    )

@Altruix.bot.on_callback_query(filters.regex(r"^track_profile_confirm_(yes|no)_(\d+)$"))
@log_errors
async def track_profile_confirm_cb_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    action = cb.matches[0].group(1)
    user_id = int(cb.matches[0].group(2))
    
    if user_id not in Altruix.user_track_state:
        await cb.answer("❌ Sesi telah kadaluarsa.", show_alert=True)
        return
        
    state = Altruix.user_track_state[user_id]
    index = state['session_index']
    page = state['page']
    target_id = state.get('target_id')
    
    if action == "no":
        del Altruix.user_track_state[user_id]
        await cb.answer("Dibatalkan.")
        await sessions_info_cb_handler(c, cb, index, page)
        return
        
    await cb.answer("Memproses pelacakan...", show_alert=False)
    await edit_cb(cb, f"⏳ Mengirim perintah track for <code>{html.escape(target_id)}</code>...")
    
    try:
        session_client = Altruix.clients[index]
        # Kirim perintah ke SangMata @SangMata_beta_bot
        await session_client.send_message("SangMata_beta_bot", f"{target_id}")
        
        # ✅ TUNGGU RESPON DARI SANGMATA
        Altruix.SANGMATA_WAITING[session_client.me.id] = asyncio.Future()
        
        try:
            # Tunggu maksimal 15 detik
            response_msg = await asyncio.wait_for(Altruix.SANGMATA_WAITING[session_client.me.id], timeout=15)
            # Dapatkan teks respon
            sangmata_text = response_msg.text or response_msg.caption or "[No text response]"
            status_summary = f"✅ <b>Respon sangmata diterima!</b>\n\n<blockquote>{html.escape(sangmata_text)}</blockquote>"
        except asyncio.TimeoutExpired:
            status_summary = "⚠️ <b>Timeout:</b> SangMata tidak merespon dalam 15 detik. Silakan cek chat secara manual."
        finally:
            if session_client.me.id in Altruix.SANGMATA_WAITING:
                del Altruix.SANGMATA_WAITING[session_client.me.id]

        await edit_cb(cb, 
            f"🔍 <b>Track Profile Result</b>\n\n"
            f"{status_summary}\n\n"
            f"<i>Perintah dikirim via Session {index + 1}.</i>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Menu Sesi", callback_data=f"session_info_{index}_{page}_{state.get('button_page', 1)}")]
            ]),
            parse_mode=ParseMode.HTML
        )
        
        # Log to private/log chat
        log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))
        await Altruix.bot.send_message(
            log_chat_id,
            f"🔍 <b>TRACK PROFILE LOG</b>\n"
            f"• User: {cb.from_user.mention}\n"
            f"• Target: <code>{html.escape(target_id)}</code>\n"
            f"• Via Session: <code>{index + 1}</code>\n"
            f"• Status: ✅ Selesai (lihat detail di Bot Assistant)"
        )
        
    except Exception as e:
        logger.error(f"Track Profile error: {e}")
        await edit_cb(cb, f"❌ <b>Gagal melacak:</b> {str(e)}")
        
    del Altruix.user_track_state[user_id]


# ============================================================================
# 🔧 ENV MANAGER (CRUD) HANDLERS
# ============================================================================

@Altruix.bot.on_callback_query(filters.regex(r"^env_manager_list_(\d+)$"))
@log_errors
async def env_manager_list_handler(c: Client, cb: CallbackQuery):
    """Handler untuk menampilkan daftar environment variables dari database"""
    if not await check_authorization(cb): return
    page = int(cb.matches[0].group(1))
    gt = Altruix.get_string
    await cb.answer(gt("CMD_RUNNING"), show_alert=False)
    
    # Ambil semua data dari env_col
    all_envs = set()
    async for var in Altruix.config.env_col.find({}):
        all_envs.add(var.get("_id"))
    
    # Tambahkan kunci dari BaseConfig (yang uppercase dan relevan)
    for key in dir(BaseConfig):
        if key.isupper() and not key.startswith("_") and key not in ["AUTOPOST_CACHE", "SESSIONS"]:
            all_envs.add(key)
    
    all_envs = sorted(list(all_envs))
    
    if not all_envs:
        await edit_cb(cb, 
            "ℹ️ <b>ENV Manager</b>\n\nDatabase environment variables kosong.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Add New ENV", callback_data="env_manager_add")],
                [InlineKeyboardButton("🔙 Back", callback_data="configs_home")]
            ]),
            parse_mode=ParseMode.HTML
        )
        return

    # Pagination
    limit = 10
    total_pages = (len(all_envs) + limit - 1) // limit
    start = (page - 1) * limit
    end = start + limit
    current_page_envs = all_envs[start:end]
    
    text = (
        f"<b>🔧 ENV Manager (Page {page}/{total_pages})</b>\n\n"
        f"Daftar variabel yang tersimpan di database:\n"
        f"Total: <code>{len(all_envs)}</code> variabel"
    )
    
    buttons = []
    for env_key in current_page_envs:
        buttons.append([InlineKeyboardButton(f"📄 {env_key}", callback_data=f"env_view_{env_key}_{page}")])
    
    # Kontrol Navigasi
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"env_manager_list_{page-1}"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"env_manager_list_{page+1}"))
    if nav_row:
        buttons.append(nav_row)
    
    buttons.append([
        InlineKeyboardButton(gt("refresh"), callback_data=f"env_manager_refresh_{page}"),
        InlineKeyboardButton("➕ Add New ENV", callback_data="env_manager_add")
    ])
    buttons.append([InlineKeyboardButton("🔙 Back to Configs", callback_data="configs_home")])
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons))


@Altruix.bot.on_callback_query(filters.regex(r"^env_manager_refresh_(\d+)$"))
@log_errors
async def env_manager_refresh_handler(c: Client, cb: CallbackQuery):
    """Handler to reload ENV from DB and refresh list"""
    if not await check_authorization(cb): return
    page = int(cb.matches[0].group(1))
    gt = Altruix.get_string
    
    await cb.answer(gt("CMD_RUNNING"))
    
    # Reload cache/vars from DB
    await Altruix.config.load_vars_from_db()
    
    await cb.answer(gt("env_reloaded"), show_alert=True)
    
    # Update the list
    new_match = re.match(r"^env_manager_list_(\d+)$", f"env_manager_list_{page}")
    cb.matches = [new_match]
    await env_manager_list_handler(c, cb)



@Altruix.bot.on_callback_query(filters.regex(r"^env_view_(.+)_(\d+)$"))
@log_errors
async def env_view_handler(c: Client, cb: CallbackQuery):
    """Handler untuk melihat detail satu environment variable"""
    if not await check_authorization(cb): return
    env_key = cb.matches[0].group(1)
    page = int(cb.matches[0].group(2))
    await cb.answer()
    
    # Ambil nilai (cek DB dulu, baru default/ENV)
    value = await Altruix.config.get_env(env_key)
    
    # Cek apakah ada di DB (untuk tombol Delete)
    is_in_db = await Altruix.config.env_col.find_one({"_id": env_key}) is not None
    
    # Format value agar tidak terlalu panjang di UI
    val_str = str(value)
    is_long = len(val_str) > 500
    display_value = val_str[:500] + "..." if is_long else val_str
    
    text = (
        f"<b>📄 ENV Detail</b>\n\n"
        f"🔑 <b>Key:</b> <code>{env_key}</code>\n"
        f"📝 <b>Value:</b>\n<pre>{html.escape(display_value)}</pre>\n\n"
        f"💡 <b>Tipe Data:</b> <code>{type(value).__name__}</code>\n"
        f"☁️ <b>Source:</b> <code>{'Database' if is_in_db else 'Default/ENV'}</code>"
    )
    
    buttons = [
        [
            InlineKeyboardButton(gt("env_edit_file"), callback_data=f"env_edit_file_{env_key}_{page}"),
            InlineKeyboardButton("✏️ Edit Value", callback_data=f"env_edit_{env_key}_{page}")
        ],
        [InlineKeyboardButton("🔙 Back to List", callback_data=f"env_manager_list_{page}")]
    ]
    
    # Tambahkan tombol Download jika panjang
    if is_long:
        buttons[0].insert(0, InlineKeyboardButton("📥 Get Full Value", callback_data=f"env_download_{env_key}"))
    
    # Hanya tampilkan tombol Delete jika variabel ada di database
    if is_in_db:
        buttons[0].append(InlineKeyboardButton("🗑️ Delete", callback_data=f"env_delete_confirm_{env_key}_{page}"))
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons))


@Altruix.bot.on_callback_query(filters.regex(r"^env_download_(.+)$"))
@log_errors
async def env_download_handler(c: Client, cb: CallbackQuery):
    """Handler untuk mendownload nilai ENV sebagai file"""
    if not await check_authorization(cb): return
    env_key = cb.matches[0].group(1)
    await cb.answer(f"📥 Preparing {env_key}.txt...")
    
    value = await Altruix.config.get_env(env_key)
    file_content = str(value)
    
    # Buat file in-memory
    file_io = io.BytesIO(file_content.encode('utf-8'))
    file_io.name = f"{env_key}.txt"
    
    await c.send_document(
        chat_id=cb.message.chat.id if cb.message else cb.from_user.id,
        document=file_io,
        caption=f"📄 <b>Full Value of ENV:</b> <code>{env_key}</code>\n"
                f"💡 <b>Size:</b> <code>{len(file_content)}</code> characters",
        parse_mode=ParseMode.HTML
    )


@Altruix.bot.on_callback_query(filters.regex(r"^env_manager_add$"))
@log_errors
async def env_manager_add_handler(c: Client, cb: CallbackQuery):
    """Handler untuk memulai proses penambahan ENV baru"""
    if not await check_authorization(cb): return
    await cb.answer()
    
    user_id = cb.from_user.id
    user_env_manager_state[user_id] = {
        'action': 'add_key',
        'timestamp': datetime.now()
    }
    
    await edit_cb(cb, 
        "<b>➕ Add New ENV (Step 1/2)</b>\n\n"
        "Silakan kirimkan <b>NAMA (Key)</b> untuk environment variable baru.\n"
        "Contoh: <code>CUSTOM_API_KEY</code>\n\n"
        "Ketik <code>/cancel</code> untuk membatalkan.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Batal", callback_data="env_manager_list_1")]]),
        parse_mode=ParseMode.HTML
    )


@Altruix.bot.on_callback_query(filters.regex(r"^env_edit_file_(.+)_(\d+)$"))
@log_errors
async def env_edit_file_handler(c: Client, cb: CallbackQuery):
    """Handler untuk memulai proses pengeditan nilai ENV via file"""
    if not await check_authorization(cb): return
    env_key = cb.matches[0].group(1)
    page = int(cb.matches[0].group(2))
    await cb.answer()
    
    user_id = cb.from_user.id
    user_env_manager_state[user_id] = {
        'action': 'edit_value_file',
        'env_key': env_key,
        'page': page,
        'timestamp': datetime.now()
    }
    
    await edit_cb(cb, 
        Altruix.get_string("env_upload_prompt").format(key=env_key),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(gt("cancel"), callback_data=f"env_view_{env_key}_{page}")]]) ,
        parse_mode=ParseMode.HTML
    )


@Altruix.bot.on_callback_query(filters.regex(r"^env_edit_(.+)_(\d+)$"))
@log_errors
async def env_edit_handler(c: Client, cb: CallbackQuery):
    """Handler untuk memulai proses pengeditan nilai ENV"""
    if not await check_authorization(cb): return
    env_key = cb.matches[0].group(1)
    page = int(cb.matches[0].group(2))
    await cb.answer()
    
    user_id = cb.from_user.id
    user_env_manager_state[user_id] = {
        'action': 'edit_value',
        'env_key': env_key,
        'page': page,
        'timestamp': datetime.now()
    }
    
    await edit_cb(cb, 
        f"<b>✏️ Edit ENV Value:</b> <code>{env_key}</code>\n\n"
        f"Silakan kirimkan <b>NILAI (Value)</b> baru untuk variabel ini.\n\n"
        f"Ketik <code>/cancel</code> untuk membatalkan.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Batal", callback_data=f"env_view_{env_key}_{page}")]]) ,
        parse_mode=ParseMode.HTML
    )


@Altruix.bot.on_callback_query(filters.regex(r"^env_delete_confirm_(.+)_(\d+)$"))
@log_errors
async def env_delete_confirm_handler(c: Client, cb: CallbackQuery):
    """Handler untuk konfirmasi penghapusan ENV"""
    if not await check_authorization(cb): return
    env_key = cb.matches[0].group(1)
    page = int(cb.matches[0].group(2))
    await cb.answer()
    
    buttons = [
        [
            InlineKeyboardButton("✅ Ya, Hapus", callback_data=f"env_delete_exec_{env_key}_{page}"),
            InlineKeyboardButton("❌ Tidak", callback_data=f"env_view_{env_key}_{page}")
        ]
    ]
    
    await edit_cb(cb, 
        f"<b>⚠️ Konfirmasi Hapus ENV</b>\n\n"
        f"Apakah Anda yakin ingin menghapus variabel <code>{env_key}</code> dari database?\n\n"
        f"🔥 <b>PERINGATAN:</b> Aksi ini tidak dapat dibatalkan.",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )


@Altruix.bot.on_callback_query(filters.regex(r"^env_delete_exec_(.+)_(\d+)$"))
@log_errors
async def env_delete_exec_handler(c: Client, cb: CallbackQuery):
    """Handler untuk mengeksekusi penghapusan ENV"""
    if not await check_authorization(cb): return
    env_key = cb.matches[0].group(1)
    page = int(cb.matches[0].group(2))
    await cb.answer("🗑️ Menghapus...", show_alert=False)
    
    try:
        success = await Altruix.config.del_env_from_db(env_key)
        if success:
            # Sync dengan in-memory config jika ada
            if hasattr(Altruix.config, env_key):
                delattr(Altruix.config, env_key)
            
            await edit_cb(cb, 
                f"✅ Variabel <code>{env_key}</code> berhasil dihapus dari database.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to List", callback_data=f"env_manager_list_{page}")]]),
                parse_mode=ParseMode.HTML
            )
            
            # Log notification
            await send_log_notification(
                c, 'del_env', 0, cb.from_user, 
                True, None, {'Key': env_key}
            )
        else:
            await edit_cb(cb, 
                f"❌ Gagal menghapus <code>{env_key}</code>. Mungkin sudah dihapus.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"env_manager_list_{page}")]]),
                parse_mode=ParseMode.HTML
            )
    except Exception as e:
        await edit_cb(cb, f"❌ <b>Error:</b> {str(e)}")
        await send_log_notification(
            c, 'del_env', 0, cb.from_user, 
            False, str(e), {'Key': env_key}
        )

@Altruix.bot.on_callback_query(filters.regex(r"^env_save_confirm_(yes|no)$"))
@log_errors
async def env_save_confirm_handler(c: Client, cb: CallbackQuery):
    """Handler untuk konfirmasi simpan (Ya/Tidak)"""
    if not await check_authorization(cb): return
    user_id = cb.from_user.id
    action = cb.matches[0].group(1)
    
    if user_id not in user_env_manager_state:
        await cb.answer("❌ State tidak ditemukan.", show_alert=True)
        return
        
    state = user_env_manager_state[user_id]
    
    if action == "no":
        del user_env_manager_state[user_id]
        await cb.answer("Dibatalkan")
        await edit_cb(cb, "❌ Aksi dibatalkan.", 
                             reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="env_manager_list_1")]]))
        return
        
    await cb.answer("💾 Menyimpan...", show_alert=False)
    
    try:
        env_key = state['env_key']
        new_value = state['new_value']
        
        # Simpan ke database
        await Altruix.config.sync_env_to_db(env_key, new_value, upsert=True)
        
        # Sync dengan in-memory config
        processed_val = Altruix.config.digit_wrap(new_value)
        setattr(Altruix.config, env_key, processed_val)
        
        await edit_cb(cb, 
            f"✅ <b>Berhasil Disimpan!</b>\n\n"
            f"🔑 <b>Key:</b> <code>{env_key}</code>\n"
            f"📝 <b>Value:</b> <code>{html.escape(str(new_value))}</code>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="env_manager_list_1")]]),
            parse_mode=ParseMode.HTML
        )
        
        # Log notification
        await send_log_notification(
            c, 'save_env', 0, cb.from_user, 
            True, None, {'Key': env_key, 'Action': state.get('action')}
        )
        
    except Exception as e:
        await edit_cb(cb, f"❌ <b>Error Simpan:</b> {str(e)}")
        await send_log_notification(
            c, 'save_env', 0, cb.from_user, 
            False, str(e), {'Key': state.get('env_key')}
        )
        
    # Cleanup state
    del user_env_manager_state[user_id]


# ============================================================================
# CUSTOM BOT MANAGER HANDLERS
# ============================================================================

# ✅ HANDLER BARU: Custom Bot Manager
@Altruix.bot.on_callback_query(filters.regex(r"^custom_bot_manager$"))
@log_errors
async def custom_bot_manager_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer()
    
    # List Custom Bots
    custom_bots = Altruix.bot_manager.custom_bots if hasattr(Altruix, 'bot_manager') else {}
    
    text = (
        f"{Altruix.get_string('custom_bot_list_title')}\n\n"
        f"{Altruix.get_string('custom_bot_count').format(len(custom_bots))}\n\n"
        f"Select a bot to manage:"
    )
    
    buttons = []
    if custom_bots:
        for bot_id, bot_client in custom_bots.items():
            # Get Session Name or ID
            name = f"Bot {bot_id}"
            try:
                me = bot_client.myself if hasattr(bot_client, "myself") else None
                if me:
                    name = f"{me.first_name} (@{me.username})"
            except: pass
            
            buttons.append([InlineKeyboardButton(name, f"manage_custom_bot_{bot_id}")])
    else:
        text += f"\n\n{Altruix.get_string('no_custom_bots')}"

    buttons.append([InlineKeyboardButton(Altruix.get_string("back"), "bot_controls_menu")])
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons))


# ✅ HANDLER BARU: Manage Custom Bot
@Altruix.bot.on_callback_query(filters.regex(r"^manage_custom_bot_(\d+)$"))
@log_errors
async def manage_custom_bot_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer()
    bot_id = int(cb.matches[0].group(1))
    
    custom_bots = Altruix.bot_manager.custom_bots if hasattr(Altruix, 'bot_manager') else {}
    bot_client = custom_bots.get(bot_id)
    
    if not bot_client:
        await cb.answer("Bot not found!", show_alert=True)
        return await custom_bot_manager_handler(c, cb)
        
    me = bot_client.myself if hasattr(bot_client, "myself") else None
    
    # Try fetch if missing and connected
    is_connected = getattr(bot_client, 'is_connected', False)
    if not me and is_connected:
        try:
             me = await bot_client.get_me()
        except: pass

    name = me.first_name if me else f"Bot {bot_id}"
    username = f"@{me.username}" if me and me.username else "No Username"
    dc_id = getattr(me, 'dc_id', "N/A") if me else "N/A"
    status_text = Altruix.get_string("bot_status_running") if is_connected else Altruix.get_string("bot_status_stopped")
    
    # Find Linked Session
    linked_session = "None"
    if hasattr(Altruix, 'bot_manager'):
        for session_client in Altruix.clients:
             try:
                 session_user_id = session_client.me.id
                 # Check if this session owns this bot
                 # Assuming bot_manager has a way to map, or we reverse check config
                 # Checking Env: CUSTOM_BOT_{session_id} == bot_token -> we'd need to know token to match id?
                 # Or check bot_manager internal map.
                 # Simplified: Iterate calls to get_bot_username
                 mapped_username = Altruix.bot_manager.get_bot_username(session_user_id)
                 if mapped_username and me and mapped_username.lower() == me.username.lower():
                     linked_session = f"{session_client.me.first_name} ({session_user_id})"
                     break
             except: continue

    text = (
        f"{Altruix.get_string('manage_custom_bot_title')}\n\n"
        f"• <b>Name:</b> {html.escape(name)}\n"
        f"• <b>Username:</b> {username}\n"
        f"• <b>ID:</b> <code>{bot_id}</code>\n"
        f"• <b>DC:</b> <code>{dc_id}</code>\n"
        f"• <b>Status:</b> {status_text}\n"
        f"• <b>Linked Session:</b> {html.escape(linked_session)}\n"
    )
    
    # Actions
    buttons = [
        [
            InlineKeyboardButton(Altruix.get_string("stop_bot"), f"action_custom_bot_stop_{bot_id}"),
            # InlineKeyboardButton(Altruix.get_string("delete_bot"), f"action_custom_bot_delete_{bot_id}"),
        ],
        [
             InlineKeyboardButton(Altruix.get_string("back"), "custom_bot_manager")
        ]
    ]
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

# ✅ HANDLER BARU: Custom Bot Actions (Stop/Delete)
@Altruix.bot.on_callback_query(filters.regex(r"^action_custom_bot_(stop|delete)_(\d+)$"))
@log_errors
async def custom_bot_action_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    action = cb.matches[0].group(1)
    bot_id = int(cb.matches[0].group(2))
    
    if action == "stop":
        # await cb.answer("Stopping bot...", show_alert=False)
        # Logic to stop bot (Altruix.bot_manager.stop_bot?)
        await cb.answer("Fitur Stop belum diimplementasikan sepenuhnya.", show_alert=True)
        
    elif action == "delete":
        # confirm
        pass
        
    # Refresh
    # await manage_custom_bot_handler(c, cb)



# ─── END SESSION INFO HANDLERS ───────────────────────────────────────────


# Helper function for message authorization check
async def check_authorization_message(m: Message) -> bool:
    """Check if user is authorized (owner or sudo)"""
    user_id = m.from_user.id
    owner_id = Altruix.config.OWNER_ID
    sudo_users = getattr(Altruix.config, 'SUDO_USERS', [])
    
    return user_id == owner_id or user_id in sudo_users


# Log sukses loading
logger.info(f"✅ Loaded → {__plugin_name__} v{PLUGIN_VERSION}")
# ====================== SUDO SETTINGS HANDLERS ======================

@Altruix.bot.on_callback_query(filters.regex(r"^sudo_settings_menu_(\d+)_(\d+)$"))
@iuser_check
@log_errors
@Altruix.bot.on_callback_query(filters.regex(r"^sudo_settings_menu_(\d+)_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def sudo_settings_menu_handler(c: Client, cb: CallbackQuery):
    """Handler for sudo settings menu"""
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    # Get current sudo status
    apply_type = await Altruix.config.get_env("SUDO_APPLY_TYPE") or "global"
    
    if apply_type == "global":
        sudo_enabled = await Altruix.config.get_env("SUDO_ENABLED_GLOBAL")
        sudo_enabled = sudo_enabled != "false" if sudo_enabled else True
    else:
        sudo_enabled = await Altruix.config.get_env(f"SUDO_ENABLED_{index}")
        sudo_enabled = sudo_enabled != "false" if sudo_enabled else True
    
    # Get sudo prefix
    sudo_prefix = await Altruix.config.get_env("SUDO_CMD_HANDLER") or "!"
    
    status_text = gt("sudo_enabled_status") if sudo_enabled else gt("sudo_disabled_status")
    apply_type_text = gt("global") if apply_type == "global" else gt("per_account")
    
    text = gt("sudo_settings_desc").format(status_text, apply_type_text, sudo_prefix)
    
    buttons = [
        [
            InlineKeyboardButton(
                gt("sudo_toggle_off") if sudo_enabled else gt("sudo_toggle_on"),
                f"sudo_toggle_{index}_{page}_{button_page}"
            )
        ],
        [
            InlineKeyboardButton(
                f"{gt('apply_type')}: {apply_type_text}",
                f"sudo_apply_type_{index}_{page}_{button_page}"
            )
        ],
        [
            InlineKeyboardButton(gt("change_sudo_prefix"), f"change_sudo_prefix_{index}_{page}_{button_page}")
        ],
        [
            InlineKeyboardButton(gt("back"), f"session_info_{index}_{page}_{button_page}")
        ]
    ]
    
    await edit_cb(cb, 
        text=gt("sudo_settings_title") + "\n\n" + text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )


@Altruix.bot.on_callback_query(filters.regex(r"^sudo_toggle_(\d+)_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def sudo_toggle_handler(c: Client, cb: CallbackQuery):
    """Toggle sudo on/off"""
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    apply_type = await Altruix.config.get_env("SUDO_APPLY_TYPE") or "global"
    
    if apply_type == "global":
        current_status = await Altruix.config.get_env("SUDO_ENABLED_GLOBAL")
        current_status = current_status != "false" if current_status else True
        new_status = not current_status
        await Altruix.config.sync_env_to_db("SUDO_ENABLED_GLOBAL", "true" if new_status else "false", upsert=True)
    else:
        current_status = await Altruix.config.get_env(f"SUDO_ENABLED_{index}")
        current_status = current_status != "false" if current_status else True
        new_status = not current_status
        await Altruix.config.sync_env_to_db(f"SUDO_ENABLED_{index}", "true" if new_status else "false", upsert=True)
    
    # Send log notification
    log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))
    await Altruix.bot.send_message(
        log_chat_id,
        f"🔐 <b>Sudo Settings Changed</b>\n\n"
        f"• User: <a href='tg://user?id={cb.from_user.id}'>{html.escape(cb.from_user.first_name)}</a>\n"
        f"• Session Index: <code>{index + 1}</code>\n"
        f"• Apply Type: <code>{apply_type}</code>\n"
        f"• New Status: <code>{'ENABLED' if new_status else 'DISABLED'}</code>\n"
        f"• Time: <code>{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</code>",
        parse_mode=ParseMode.HTML
    )
    
    await cb.answer(gt("sudo_enabled_msg") if new_status else gt("sudo_disabled_msg"), show_alert=True)
    cb.matches = [re.match(r"^sudo_settings_menu_(\d+)_(\d+)_(\d+)$", f"sudo_settings_menu_{index}_{page}_{button_page}")]
    await sudo_settings_menu_handler(c, cb)


@Altruix.bot.on_callback_query(filters.regex(r"^sudo_apply_type_(\d+)_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def sudo_apply_type_handler(c: Client, cb: CallbackQuery):
    """Toggle between global and per-account apply type"""
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    current_type = await Altruix.config.get_env("SUDO_APPLY_TYPE") or "global"
    new_type = "per_account" if current_type == "global" else "global"
    
    await Altruix.config.sync_env_to_db("SUDO_APPLY_TYPE", new_type, upsert=True)
    
    type_text = gt("global") if new_type == "global" else gt("per_account")
    await cb.answer(gt("sudo_apply_type_changed").format(type_text), show_alert=True)
    await sudo_settings_menu_handler(c, cb)


# ====================== PREFIX SETTINGS HANDLERS ======================

@Altruix.bot.on_callback_query(filters.regex(r"^prefix_settings_menu_(\d+)_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def prefix_settings_menu_handler(c: Client, cb: CallbackQuery):
    """Handler for prefix settings menu"""
    try:
        await cb.answer()
    except QueryIdInvalid:
        pass
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    # Get current prefixes and apply type
    apply_type = await Altruix.config.get_env("PREFIX_APPLY_TYPE") or "global"
    userbot_prefix = await Altruix.config.get_env("CMD_HANDLER") or "."
    sudo_prefix = await Altruix.config.get_env("SUDO_CMD_HANDLER") or "!"
    
    text = gt("prefix_settings_desc").format(userbot_prefix, sudo_prefix)
    
    apply_type_text = gt("prefix_apply_type_global") if apply_type == "global" else gt("prefix_apply_type_account")
    
    buttons = [
        [
            InlineKeyboardButton(f"{gt('prefix_apply_type')}: {apply_type_text}", f"prefix_apply_type_{index}_{page}_{button_page}")
        ],
        [
            InlineKeyboardButton(gt("change_userbot_prefix"), f"change_userbot_prefix_{index}_{page}_{button_page}")
        ],
        [
            InlineKeyboardButton(gt("change_sudo_prefix_menu"), f"change_sudo_prefix_{index}_{page}_{button_page}")
        ],
        [
            InlineKeyboardButton(gt("back"), f"session_info_{index}_{page}_{button_page}")
        ]
    ]
    
    await edit_cb(cb,
        text=gt("prefix_settings_title") + "\n\n" + text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )


@Altruix.bot.on_callback_query(filters.regex(r"^prefix_apply_type_(\d+)_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def prefix_apply_type_handler(c: Client, cb: CallbackQuery):
    """Toggle prefix apply type between global and per-account"""
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    current_type = await Altruix.config.get_env("PREFIX_APPLY_TYPE") or "global"
    new_type = "per-account" if current_type == "global" else "global"
    
    await Altruix.config.sync_env_to_db("PREFIX_APPLY_TYPE", new_type, upsert=True)
    
    type_display = gt("prefix_apply_type_global") if new_type == "global" else gt("prefix_apply_type_account")
    await cb.answer(gt("prefix_apply_type_msg").format(type_display), show_alert=True)
    
    # Send mock cb matches to reuse same handler logic with button_page
    cb.matches = [re.match(r"^prefix_settings_menu_(\d+)_(\d+)_(\d+)$", f"prefix_settings_menu_{index}_{page}_{button_page}")]
    await prefix_settings_menu_handler(c, cb)


@Altruix.bot.on_callback_query(filters.regex(r"^change_userbot_prefix_(\d+)_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def change_userbot_prefix_handler(c: Client, cb: CallbackQuery):
    """Change userbot command prefix"""
    try:
        await cb.answer()
    except QueryIdInvalid:
        pass
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    user_id = cb.from_user.id
    
    apply_type = await Altruix.config.get_env("PREFIX_APPLY_TYPE") or "global"
    
    if apply_type == "global":
        current_prefix = await Altruix.config.get_env("CMD_HANDLER") or "."
    else:
        current_prefix = await Altruix.config.get_env(f"CMD_HANDLER_{user_id}") or await Altruix.config.get_env("CMD_HANDLER") or "."
    
    await edit_cb(cb,
        f"<b>📝 {gt('change_userbot_prefix')}</b>\n\n"
        f"• <b>{gt('current_prefix')}:</b> <code>{current_prefix}</code>\n\n"
        f"{gt('prefix_prompt')}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(gt("back"), f"prefix_settings_menu_{index}_{page}_{button_page}")]]),
        parse_mode=ParseMode.HTML
    )
    
    try:
        msg = await c.listen(filters.chat(user_id) & filters.text, timeout=60)
        new_prefix = msg.text.strip()
        
        if new_prefix.lower() == "cancel":
            await msg.delete()
            await edit_cb(cb, gt("operation_cancelled"))
            await asyncio.sleep(2)
            cb.matches = [re.match(r"^prefix_settings_menu_(\d+)_(\d+)_(\d+)$", f"prefix_settings_menu_{index}_{page}_{button_page}")]
            await prefix_settings_menu_handler(c, cb)
            return
        
        # Validate prefix
        if len(new_prefix) != 1 or new_prefix.isalnum():
            await msg.delete()
            await edit_cb(cb, gt("prefix_invalid"))
            await asyncio.sleep(2)
            cb.matches = [re.match(r"^prefix_settings_menu_(\d+)_(\d+)_(\d+)$", f"prefix_settings_menu_{index}_{page}_{button_page}")]
            await prefix_settings_menu_handler(c, cb)
            return
        
        # Check if same as sudo prefix
        sudo_prefix = await Altruix.config.get_env("SUDO_CMD_HANDLER") or "!"
        if new_prefix == sudo_prefix:
            await msg.delete()
            await edit_cb(cb, gt("prefix_same_as_other").format(gt("prefix_sudo")))
            await asyncio.sleep(2)
            cb.matches = [re.match(r"^prefix_settings_menu_(\d+)_(\d+)_(\d+)$", f"prefix_settings_menu_{index}_{page}_{button_page}")]
            await prefix_settings_menu_handler(c, cb)
            return
        
        await msg.delete()
        
        # Update prefix in DB
        apply_type = await Altruix.config.get_env("PREFIX_APPLY_TYPE") or "global"
        
        if apply_type == "global":
            await Altruix.config.sync_env_to_db("CMD_HANDLER", new_prefix, upsert=True)
            Altruix.user_command_handler = new_prefix
        else:
            await Altruix.config.sync_env_to_db(f"CMD_HANDLER_{user_id}", new_prefix, upsert=True)
            # If current cb handler is the one we changed, update it in memory too
            if c.me and c.me.id == user_id:
                Altruix.user_command_handler = new_prefix
        
        await Altruix.config.load_vars_from_db()
        
        # Send log notification
        log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))
        await Altruix.bot.send_message(
            log_chat_id,
            f"📝 <b>Userbot Prefix Changed</b>\n\n"
            f"• User: <a href='tg://user?id={cb.from_user.id}'>{html.escape(cb.from_user.first_name)}</a>\n"
            f"• Old Prefix: <code>{current_prefix}</code>\n"
            f"• New Prefix: <code>{new_prefix}</code>\n"
            f"• Time: <code>{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</code>",
            parse_mode=ParseMode.HTML
        )
        
        await edit_cb(cb, gt("prefix_updated").format(new_prefix), parse_mode=ParseMode.HTML)
        await asyncio.sleep(3)
        cb.matches = [re.match(r"^prefix_settings_menu_(\d+)_(\d+)_(\d+)$", f"prefix_settings_menu_{index}_{page}_{button_page}")]
        await prefix_settings_menu_handler(c, cb)
        
    except (asyncio.TimeoutError, ListenerTimeout):
        await edit_cb(cb, gt("timeout_retry"))
        await asyncio.sleep(2)
        cb.matches = [re.match(r"^prefix_settings_menu_(\d+)_(\d+)_(\d+)$", f"prefix_settings_menu_{index}_{page}_{button_page}")]
        await prefix_settings_menu_handler(c, cb)


@Altruix.bot.on_callback_query(filters.regex(r"^change_sudo_prefix_(\d+)_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
@Altruix.bot.on_callback_query(filters.regex(r"^change_sudo_prefix_(\d+)_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def change_sudo_prefix_handler(c: Client, cb: CallbackQuery):
    """Change sudo command prefix"""
    try:
        await cb.answer()
    except QueryIdInvalid:
        pass
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    user_id = cb.from_user.id
    
    apply_type = await Altruix.config.get_env("PREFIX_APPLY_TYPE") or "global"
    
    if apply_type == "global":
        current_prefix = await Altruix.config.get_env("SUDO_CMD_HANDLER") or "!"
    else:
        current_prefix = await Altruix.config.get_env(f"SUDO_CMD_HANDLER_{user_id}") or await Altruix.config.get_env("SUDO_CMD_HANDLER") or "!"
    
    await edit_cb(cb,
        f"<b>🔧 {gt('change_sudo_prefix_menu')}</b>\n\n"
        f"• <b>{gt('current_prefix')}:</b> <code>{current_prefix}</code>\n\n"
        f"{gt('prefix_prompt')}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(gt("back"), f"prefix_settings_menu_{index}_{page}_{button_page}")]]),
        parse_mode=ParseMode.HTML
    )
    
    try:
        msg = await c.listen(filters.chat(user_id) & filters.text, timeout=60)
        new_prefix = msg.text.strip()
        
        if new_prefix.lower() == "cancel":
            await msg.delete()
            await edit_cb(cb, gt("operation_cancelled"))
            await asyncio.sleep(2)
            cb.matches = [re.match(r"^prefix_settings_menu_(\d+)_(\d+)_(\d+)$", f"prefix_settings_menu_{index}_{page}_{button_page}")]
            await prefix_settings_menu_handler(c, cb)
            return
        
        # Validate prefix
        if len(new_prefix) != 1 or new_prefix.isalnum():
            await msg.delete()
            await edit_cb(cb, gt("prefix_invalid"))
            await asyncio.sleep(2)
            cb.matches = [re.match(r"^prefix_settings_menu_(\d+)_(\d+)_(\d+)$", f"prefix_settings_menu_{index}_{page}_{button_page}")]
            await prefix_settings_menu_handler(c, cb)
            return
        
        # Check if same as userbot prefix
        userbot_prefix = await Altruix.config.get_env("CMD_HANDLER") or "."
        if new_prefix == userbot_prefix:
            await msg.delete()
            await edit_cb(cb, gt("prefix_same_as_other").format(gt("prefix_userbot")))
            await asyncio.sleep(2)
            cb.matches = [re.match(r"^prefix_settings_menu_(\d+)_(\d+)_(\d+)$", f"prefix_settings_menu_{index}_{page}_{button_page}")]
            await prefix_settings_menu_handler(c, cb)
            return
        
        await msg.delete()
        
        # Update prefix in DB
        apply_type = await Altruix.config.get_env("PREFIX_APPLY_TYPE") or "global"
        
        if apply_type == "global":
            await Altruix.config.sync_env_to_db("SUDO_CMD_HANDLER", new_prefix, upsert=True)
            Altruix.sudo_cmd_handler = new_prefix
        else:
            await Altruix.config.sync_env_to_db(f"SUDO_CMD_HANDLER_{user_id}", new_prefix, upsert=True)
            if c.me and c.me.id == user_id:
                Altruix.sudo_cmd_handler = new_prefix
        
        await Altruix.config.load_vars_from_db()
        
        # Send log notification
        log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))
        await Altruix.bot.send_message(
            log_chat_id,
            f"🔧 <b>Sudo Prefix Changed</b>\n\n"
            f"• User: <a href='tg://user?id={cb.from_user.id}'>{html.escape(cb.from_user.first_name)}</a>\n"
            f"• Old Prefix: <code>{current_prefix}</code>\n"
            f"• New Prefix: <code>{new_prefix}</code>\n"
            f"• Time: <code>{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</code>",
            parse_mode=ParseMode.HTML
        )
        
        await edit_cb(cb, gt("prefix_updated").format(new_prefix), parse_mode=ParseMode.HTML)
        await asyncio.sleep(3)
        cb.matches = [re.match(r"^prefix_settings_menu_(\d+)_(\d+)_(\d+)$", f"prefix_settings_menu_{index}_{page}_{button_page}")]
        await prefix_settings_menu_handler(c, cb)
        
    except (asyncio.TimeoutError, ListenerTimeout):
        await edit_cb(cb, gt("timeout_retry"))
        await asyncio.sleep(2)
        cb.matches = [re.match(r"^prefix_settings_menu_(\d+)_(\d+)_(\d+)$", f"prefix_settings_menu_{index}_{page}_{button_page}")]
        await prefix_settings_menu_handler(c, cb)
# ─── GLOBAL PURGEME HANDLERS ──────────────────────────────────────────

@Altruix.bot.on_callback_query(filters.regex(r"^gpurgeme_menu_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
@iuser_check
async def gpurgeme_menu_handler(c: Client, cb: CallbackQuery):
    try:
        await cb.answer()
    except: pass
    
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    if index >= len(Altruix.clients):
        await edit_cb(cb, "Session not found.")
        return

    client = Altruix.clients[index]
    
    # Fully robust session retrieval
    me = getattr(client, "myself", None) or client.me
    if not me:
        try:
            me = await client.get_me()
            client.myself = me
        except Exception as e:
            await cb.answer(f"Session Error: {e}", show_alert=True)
            return
            
    if not me: # Still None?
        await cb.answer("Could not retrieve user info.", show_alert=True)
        return

    unique_id = f"gp_{me.id}"
    
    # Safe message/chat ID extraction
    msg_id = cb.message.id if cb.message else 0
    chat_id = cb.message.chat.id if cb.message else cb.from_user.id
    
    # Initialize state if not exists
    from Main.plugins.userbot import xgpurgeme_userbot
    async with xgpurgeme_userbot.STATE_LOCK:
        if unique_id not in Altruix.GPURGEME_STATE:
            Altruix.GPURGEME_STATE[unique_id] = {
                "unique_id": unique_id,
                "client": client,
                "status": "idle",
                "target": "all",
                "limit": 10,
                "delay": 6,
                "ignore_admin": True,
                "mode": "newest",
                "offset": 0,
                "notify": True,
                "filters": ["all"],
                "deleted_count": 0,
                "processed_chats": 0,
                "total_chats": 0,
                "stop_event": asyncio.Event(),
                "pause_event": asyncio.Event(),
                "dashboard_msg_id": msg_id,
                "dashboard_chat_id": chat_id,
                "start_time": 0
            }
        state = Altruix.GPURGEME_STATE[unique_id]
        state["dashboard_msg_id"] = msg_id
        state["dashboard_chat_id"] = chat_id
        state["pause_event"].set()
        
        # ✅ SET SETTINGS CONTEXT
        state["is_settings"] = True
        state["index"] = index
        state["page"] = page
        state["button_page"] = button_page
        # Capture the message ID so the dashboard updater knows what to target
        if cb.message:
            state["dashboard_chat_id"] = cb.message.chat.id
            state["dashboard_msg_id"] = cb.message.id
        Altruix.log(f"DEBUG: Initialized GP State in Settings for {unique_id}. index={index}, page={page}, msg_id={state.get('dashboard_msg_id')}", level=20)

    text = xgpurgeme_userbot.get_gp_status_text(state)
    kb = xgpurgeme_userbot.get_gp_control_kb(unique_id, state)
    
    Altruix.log(f"DEBUG: Sending GP Menu via edit_cb for {unique_id}. msg_id={msg_id}", level=20)
    await edit_cb(cb, text, reply_markup=kb)

# ---------------------------------------------------------
# GLOBAL PURGEME INLINE HANDLER
# ---------------------------------------------------------

@Altruix.bot.on_inline_query(filters.regex(r"^gp_menu_(?P<uid>gp_\d+)$"))
@log_errors
@iuser_check
async def gp_inline_handler(c: Client, q: InlineQuery):
    unique_id = q.matches[0].group("uid")
    
    from Main.plugins.userbot import xgpurgeme_userbot
    
    async with xgpurgeme_userbot.STATE_LOCK:
        # Check if state exists, if not try to initialize default
        if unique_id not in Altruix.GPURGEME_STATE:
             # Extract user_id from unique_id (gp_12345)
            try:
                user_id = int(unique_id.split("_")[1])
                # Find the client for this user
                client = None
                for cl in Altruix.clients:
                    me = getattr(cl, "myself", None) or cl.me
                    if me and me.id == user_id:
                        client = cl
                        break
                
                if client:
                    Altruix.GPURGEME_STATE[unique_id] = {
                        "unique_id": unique_id,
                        "client": client,
                        "status": "idle",
                        "target": "all",
                        "limit": 10,
                        "delay": 6,
                        "ignore_admin": True,
                        "mode": "newest",
                        "offset": 0,
                        "notify": True,
                        "filters": ["all"],
                        "deleted_count": 0,
                        "processed_chats": 0,
                        "total_chats": 0,
                        "stop_event": asyncio.Event(),
                        "pause_event": asyncio.Event(),
                        "dashboard_msg_id": None,
                        "dashboard_chat_id": None,
                        "start_time": 0
                    }
                    Altruix.GPURGEME_STATE[unique_id]["pause_event"].set()
            except:
                pass

        state = Altruix.GPURGEME_STATE.get(unique_id)
        
    if not state:
        await q.answer(
            results=[],
            switch_pm_text="❌ Session expired or invalid",
            switch_pm_parameter="help",
            cache_time=0
        )
        return

    text = xgpurgeme_userbot.get_gp_status_text(state)
    kb = xgpurgeme_userbot.get_gp_control_kb(unique_id, state)
    
    await q.answer(
        results=[
            InlineQueryResultArticle(
                title="Global Purgeme Dashboard",
                description=f"Status: {state['status']} | Target: {state['target']}",
                thumb_url="https://telegra.ph/file/0c9aaff87572791838520.png",
                input_message_content=InputTextMessageContent(
                    text,
                    disable_web_page_preview=True
                ),
                reply_markup=kb
            )
        ],
        cache_time=0,
        is_personal=True
    )


@Altruix.bot.on_callback_query(filters.regex(r"^toggle_sess_stat_(\d+)_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def toggle_session_status_handler(c: Client, cb: CallbackQuery):
    """Handler to confirm session disable/enable."""
    gt = Altruix.get_string
    await cb.answer()
    
    index = int(cb.matches[0].group(1))
    callback_page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    if index >= len(Altruix.clients):
        await edit_cb(cb, "Session not found.")
        return

    client = Altruix.clients[index]
    user_id = getattr(getattr(client, 'myself', None), 'id', None)
    
    if not user_id:
        await edit_cb(cb, "Failed to get user ID.")
        return
        
    is_disabled = Altruix.is_session_disabled(user_id)
    
    action = "enable" if is_disabled else "disable"
    confirm_text = gt("confirm_enable") if is_disabled else gt("confirm_disable")
    
    buttons = [
        [
            InlineKeyboardButton(gt("yes"), f"confirm_toggle_sess_stat_{index}_{callback_page}_{button_page}_{action}"),
            InlineKeyboardButton(gt("no"), f"session_info_{index}_{callback_page}_{button_page}")
        ]
    ]
    
    await edit_cb(cb, text=confirm_text, reply_markup=InlineKeyboardMarkup(buttons))


@Altruix.bot.on_callback_query(filters.regex(r"^confirm_toggle_sess_stat_(\d+)_(\d+)_(\d+)_(enable|disable)$"))
@iuser_check
@log_errors
async def toggle_session_status_confirm_handler(c: Client, cb: CallbackQuery):
    """Handler to execute session disable/enable."""
    gt = Altruix.get_string
    await cb.answer()
    
    index = int(cb.matches[0].group(1))
    callback_page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3))
    action = cb.matches[0].group(4)
    
    if index >= len(Altruix.clients):
        await edit_cb(cb, "Session not found.")
        return

    client = Altruix.clients[index]
    user_id = getattr(getattr(client, 'myself', None), 'id', None)
    
    if not user_id:
        await edit_cb(cb, "Failed to get user ID.")
        return
        
    disable = (action == "disable")
    Altruix.toggle_session_disable(user_id, disable)
    
    status_text = gt("inactive_caps") if disable else gt("active_caps")
    await edit_cb(cb, gt("session_status_changed").format(status_text))
    
    # Log to Log Group
    if Altruix.log_chat:
        try:
            log_msg = (
                f"📝 <b>Session Status Changed</b>\n\n"
                f"👤 <b>User:</b> {getattr(client.myself, 'first_name', 'Unknown')} (`{user_id}`)\n"
                f"📊 <b>New Status:</b> {status_text}\n"
                f"👮 <b>By:</b> {cb.from_user.mention}"
            )
            await Altruix.bot.send_message(Altruix.log_chat, log_msg)
        except Exception as e:
            logger.error(f"Failed to log session status change: {e}")
            
    # Redirect back to session info after short delay
    await asyncio.sleep(1.5)
    
    # We need to manually construct the callback implementation to redirect
    # Or just call the exist handler logic? Easier to simulate callback
    # For now, let's just trigger the session_info handler via recursion logic or just edit message again
    
    # Re-use the session info logic
    from pyrogram.types import CallbackQuery as CQ
    new_cb = cb
    # Update matches to match session_info regex structure
    import re
    new_cb.matches = [re.match(r"^session_info_(\d+)_(\d+)_(\d+)$", f"session_info_{index}_{callback_page}_{button_page}")]
    
    await sessions_info_cb_handler(c, new_cb, index, callback_page, button_page)
