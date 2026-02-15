# Main/internals/settings_handlers/utils.py
import html
import os
import logging
from datetime import datetime
from typing import Any, Dict
from pyrogram import Client
from pyrogram.types import CallbackQuery
from Main.core.client import Altruix
from pyrogram.enums import ParseMode

# Logger
logger = logging.getLogger(__name__)

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
            'recent_messages': 'Pesan Terbaru',
            'view_mentions': 'Lihat Mention',
            'send_profile_photo': 'Kirim Foto Profil',
            'purge_my_message': 'Purge Message',
            'dlstory_session': 'Download Story',
            'dl_content_session': 'Download Content'
        }
        
        action_text = action_map.get(action, action)
        status = "✅ BERHASIL" if success else "❌ GAGAL"
        
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
        
        if error_msg:
            log_message += f"• Error: <code>{html.escape(str(error_msg))}</code>\n"
            
        if additional_info:
            for key, value in additional_info.items():
                if value and str(value).strip():
                    log_message += f"• {key}: <code>{html.escape(str(value))}</code>\n"
        
        log_message += f"• Waktu: <code>{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</code>"
        
        await Altruix.bot.send_message(
            log_chat_id, 
            log_message, 
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        
    except Exception as e:
        logger.error(f"Error sending log notification: {e}")

async def edit_cb(cb: CallbackQuery, text: str, **kwargs):
    """Wrapper for Altruix.edit_cb."""
    return await Altruix.edit_cb(cb, text, **kwargs)

async def delete_cb(cb: CallbackQuery):
    """Wrapper for Altruix.delete_cb."""
    return await Altruix.delete_cb(cb)

def gt(key):
    """Wrapper for Altruix.get_string."""
    return Altruix.get_string(key)

async def is_authorized(user_id: int, client: Client = None) -> bool:
    """✅ Check if user is authorized using centralized database-aware helper."""
    return await Altruix.is_sudo(user_id, client=client)

async def check_authorization(cb: CallbackQuery) -> bool:
    """
    Check if callback user is authorized. 
    Returns True if authorized, False otherwise (and sends access denied message).
    """
    if not await is_authorized(cb.from_user.id):
        msg = Altruix.get_string("ACCESS_DENIED")
        full_msg = Altruix.get_string("AUTH_NO_PERMISSION")
        await cb.answer(f"{msg} - {full_msg}", show_alert=True)
        return False
    return True

async def check_authorization_message(m: Any) -> bool:
    """
    Check if message user is authorized. 
    Returns True if authorized, False otherwise (and sends ❌ access denied reply).
    """
    if not await is_authorized(m.from_user.id):
        msg = Altruix.get_string("ACCESS_DENIED")
        full_msg = Altruix.get_string("AUTH_NO_PERMISSION")
        await m.reply(f"❌ {msg} - {full_msg}")
        return False
    return True
