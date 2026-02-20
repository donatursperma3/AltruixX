# Main/internals/settings_handlers/profile_handlers.py
from typing import Optional
import html
import os
import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from Main.core.decorators import log_errors, iuser_check
from Main.core.client import Altruix
from pyrogram.enums import ParseMode
from pyrogram.errors import (
    UsernameNotModified, AboutTooLong, 
    PhotoInvalidDimensions, PhotoSaveFileInvalid, UsernameOccupied, FloodWait
)

# Handle FirstNameInvalid yang mungkin tidak ada di beberapa versi Pyrogram
try:
    from pyrogram.errors import FirstNameInvalid
except ImportError:
    # Buat kelas dummy jika FirstNameInvalid tidak ada
    class FirstNameInvalid(Exception):
        pass

# Shared State (Centralized)
from .states import (
    user_profile_edit_state, 
    user_edit_confirmation_state
)

# Logger
logger = logging.getLogger(__name__)

@Altruix.bot.on_callback_query(filters.regex(r"change_name_menu_(\d+)_(\d+)"))
@iuser_check
@log_errors
async def change_name_menu_handler(c: Client, cb: CallbackQuery):
    """Handler for name change menu (First/Last)"""
    await cb.answer()
    index, page = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    buttons = [
        [
            InlineKeyboardButton(Altruix.get_string("first_name"), f"change_first_name_{index}_{page}"), 
            InlineKeyboardButton(Altruix.get_string("last_name"), f"change_last_name_{index}_{page}")
        ],
        [InlineKeyboardButton("🔙 Back", callback_data=f"session_info_{index}_{page}")]
    ]
    args = {
        "text": "<b>✏️ Ganti Nama</b>\n\nPilih bagian nama yang ingin Anda ubah:", 
        "reply_markup": InlineKeyboardMarkup(buttons), 
        "parse_mode": ParseMode.HTML
    }
    if cb.message:
        await cb.message.edit(**args)
    else:
        await cb.edit_message_text(**args)

@Altruix.bot.on_callback_query(filters.regex(r"change_(first|last)_name_(\d+)_(\d+)"))
@iuser_check
@log_errors
async def change_name_handler(c: Client, cb: CallbackQuery):
    """Entry point for changing first or last name"""
    await cb.answer()
    name_type = cb.matches[0].group(1) # 'first' or 'last'
    index, page = int(cb.matches[0].group(2)), int(cb.matches[0].group(3))
    user_id = cb.from_user.id
    
    action = f"change_{name_type}_name"
    user_profile_edit_state[user_id] = {
        'action': action,
        'session_index': index,
        'page': page
    }
    
    label = "Depan" if name_type == "first" else "Belakang"
    note = "Nama depan maksimal 64 karakter" if name_type == "first" else "Kirim 'kosong' untuk menghapus nama belakang"
    
    args = {
        "text": f"✏️ <b>Ganti Nama {label}</b>\n\n"
              f"Silakan kirim nama {label.lower()} baru untuk akun ini.\n\n"
              f"⚠️ <b>Note:</b>\n"
              f"• {note}\n"
              f"• Tidak boleh mengandung karakter khusus\n\n"
              f"❌ <b>Cancel:</b> Kirim /cancel",
        "parse_mode": ParseMode.HTML
    }
    if cb.message:
        await cb.message.edit(**args)
    else:
        await cb.edit_message_text(**args)

@Altruix.bot.on_callback_query(filters.regex(r"change_bio_(\d+)_(\d+)"))
@Altruix.bot.on_callback_query(filters.regex(r"^gen_conf_change_bio_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def change_bio_handler(c: Client, cb: CallbackQuery):
    """Entry point for changing bio"""
    await cb.answer()
    index, page = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    user_id = cb.from_user.id
    
    user_profile_edit_state[user_id] = {
        'action': 'change_bio',
        'session_index': index,
        'page': page
    }
    
    args = {
        "text": "📝 <b>Ganti Bio</b>\n\n"
              "Silakan kirim bio baru untuk akun ini.\n"
              "Maksimal 70 karakter.\n\n"
              "⚠️ <b>Note:</b>\n"
              "• Bio akan tampil di profil\n"
              "• Bisa berisi emoji dan link\n\n"
              "❌ <b>Cancel:</b> Kirim /cancel",
        "parse_mode": ParseMode.HTML
    }
    if cb.message:
        await cb.message.edit(**args)
    else:
        await cb.edit_message_text(**args)

@Altruix.bot.on_callback_query(filters.regex(r"change_username_(\d+)_(\d+)"))
@Altruix.bot.on_callback_query(filters.regex(r"^gen_conf_change_username_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def change_username_handler(c: Client, cb: CallbackQuery):
    """Entry point for changing username"""
    await cb.answer()
    index, page = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    user_id = cb.from_user.id
    
    user_profile_edit_state[user_id] = {
        'action': 'change_username',
        'session_index': index,
        'page': page
    }
    
    args = {
        "text": "👤 <b>Ganti Username</b>\n\n"
              "Silakan kirim username baru (tanpa @).\n"
              "Contoh: username_baru\n\n"
              "⚠️ <b>Note:</b>\n"
              "• Username harus unik dan tersedia\n"
              "• Minimal 5 karakter\n"
              "• Hanya boleh mengandung huruf, angka, dan underscore\n\n"
              "❌ <b>Cancel:</b> Kirim /cancel",
        "parse_mode": ParseMode.HTML
    }
    if cb.message:
        await cb.message.edit(**args)
    else:
        await cb.edit_message_text(**args)

@Altruix.bot.on_callback_query(filters.regex(r"change_profile_photo_(\d+)_(\d+)"))
@Altruix.bot.on_callback_query(filters.regex(r"^gen_conf_change_profile_photo_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def change_profile_photo_handler(c: Client, cb: CallbackQuery):
    """Entry point for changing profile photo"""
    await cb.answer()
    index, page = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    user_id = cb.from_user.id
    
    user_profile_edit_state[user_id] = {
        'action': 'change_profile_photo',
        'session_index': index,
        'page': page
    }
    
    args = {
        "text": "🖼️ <b>Ganti Foto Profil</b>\n\n"
              "Silakan kirim foto baru untuk profil akun ini.\n\n"
              "⚠️ <b>Note:</b>\n"
              "• Foto harus dalam format JPEG/PNG\n"
              "• Ukuran maksimal 10MB\n"
              "• Foto lama akan diganti\n\n"
              "❌ <b>Cancel:</b> Kirim /cancel",
        "parse_mode": ParseMode.HTML
    }
    if cb.message:
        await cb.message.edit(**args)
    else:
        await cb.edit_message_text(**args)

@Altruix.bot.on_callback_query(filters.regex(r"delete_all_profile_photos_(\d+)_(\d+)"))
@Altruix.bot.on_callback_query(filters.regex(r"^gen_conf_delete_all_profile_photos_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def delete_all_profile_photos_handler(c: Client, cb: CallbackQuery):
    """Confirmation for deleting all profile photos"""
    await cb.answer()
    index, page = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    user_id = cb.from_user.id
    
    user_edit_confirmation_state[user_id] = {
        'action': 'delete_all_profile_photos',
        'session_index': index,
        'page': page,
        'delay': 2
    }
    
    args = {
        "text": "🗑️ <b>Konfirmasi Hapus Semua Foto Profil</b>\n\n"
              "Apakah Anda yakin ingin menghapus SEMUA foto profil akun ini?\n\n"
              "⚠️ <b>PERINGATAN:</b>\n"
              "• Tindakan ini tidak dapat dibatalkan\n"
              "• Semua foto profil akan dihapus permanen\n\n"
              "Lanjutkan?",
        "reply_markup": InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Ya, Hapus Semua", f"edit_confirm_yes_{user_id}"),
                InlineKeyboardButton("❌ Tidak", f"session_info_{index}_{page}")
            ]
        ]),
        "parse_mode": ParseMode.HTML
    }
    if cb.message:
        await cb.message.edit(**args)
    else:
        await cb.edit_message_text(**args)

async def delete_all_profile_photos_process(c: Client, m: Optional[Message], session_index: int, page: int, delay: int, user_id: int = None):
    """Actual process of deleting all profile photos with delay and logging"""
    if session_index >= len(Altruix.clients):
        if m: await m.reply("❌ Session tidak ditemukan.")
        elif user_id: await c.send_message(user_id, "❌ Session tidak ditemukan.")
        return
    
    session_client = Altruix.clients[session_index]
    
    try:
        photos = []
        async for photo in session_client.get_chat_photos("me"):
            photos.append(photo)
        
        total = len(photos)
        if total == 0:
            if m: await m.reply("ℹ️ Akun ini tidak memiliki foto profil.")
            elif user_id: await c.send_message(user_id, "ℹ️ Akun ini tidak memiliki foto profil.")
            return
        
        status_text = f"🔄 Menghapus {total} foto profil dengan delay {delay}s..."
        status_msg = None
        if m: status_msg = await m.reply(status_text)
        elif user_id: status_msg = await c.send_message(user_id, status_text)
        
        deleted = 0
        for i, photo in enumerate(photos, 1):
            try:
                await session_client.delete_profile_photos(photo.file_id)
                deleted += 1
                if status_msg and (i % 5 == 0 or i == total):
                    try: await status_msg.edit(f"🔄 Progress: {i}/{total} foto dihapus.")
                    except: pass
                if i < total:
                    await asyncio.sleep(delay)
            except FloodWait as e:
                if status_msg:
                    try: await status_msg.edit(f"⏳ FloodWait: Menunggu {e.value}s...")
                    except: pass
                await asyncio.sleep(e.value)
                await session_client.delete_profile_photos(photo.file_id)
                deleted += 1
            except Exception as e:
                logger.error(f"Error delete photo {i}: {e}")
        
        final_msg = f"✅ Selesai! {deleted}/{total} foto profil berhasil dihapus."
        if m: await m.reply(final_msg)
        elif user_id: await c.send_message(user_id, final_msg)
        
    except Exception as e:
        err_msg = f"❌ Error: {str(e)}"
        if m: await m.reply(err_msg)
        elif user_id: await c.send_message(user_id, err_msg)
        logger.error(f"Error in delete_all_profile_photos_process: {e}")

# Note: The Yes/No confirmation logic for edits is handled in session_info.py's text handler or dedicated callback.

async def process_profile_edit_input(c: Client, m: Message):
    """Captures and processes text inputs for profile changes."""
    user_id = m.from_user.id
    state = user_profile_edit_state.get(user_id)
    if not state: return

    action = state['action']
    index = state['session_index']
    page = state['page']
    text = m.text.strip()
    
    if text.lower() == '/cancel' or text.lower() == 'cancel':
        del user_profile_edit_state[user_id]
        await m.reply("❌ Perubahan profil dibatalkan.")
        return

    await m.reply("⏳ <b>Sedang memproses perubahan...</b>", parse_mode=ParseMode.HTML)
    
    session_client = Altruix.clients[index]
    success = False
    error_msg = None
    
    try:
        if action == 'change_first_name':
            await session_client.update_profile(first_name=text)
            success = True
        elif action == 'change_last_name':
            await session_client.update_profile(last_name=text)
            success = True
        elif action == 'change_bio':
            await session_client.update_profile(bio=text)
            success = True
        elif action == 'change_username':
            await session_client.update_username(text)
            success = True
            
        if success:
            from .utils import send_log_notification
            await m.reply(f"✅ <b>Berhasil!</b> Profil telah diperbarui.", parse_mode=ParseMode.HTML)
            await send_log_notification(c, action, index, m.from_user, True, additional_info={'New Value': text})
        
    except Exception as e:
        error_msg = str(e)
        await m.reply(f"❌ <b>Gagal:</b> {error_msg}", parse_mode=ParseMode.HTML)
        from .utils import send_log_notification
        await send_log_notification(c, action, index, m.from_user, False, error_msg)
    
    del user_profile_edit_state[user_id]
    await asyncio.sleep(2)
    await m.reply("🔄 Memuat ulang menu...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Dashboard", f"session_info_{index}_{page}")]]))
