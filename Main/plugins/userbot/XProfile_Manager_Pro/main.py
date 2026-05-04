# Main/plugins/userbot/XProfile_Manager_Pro/main.py
import asyncio
import random
import logging
import io
import aiohttp
from datetime import datetime
from PIL import Image
from pyrogram import Client, filters, enums
from pyrogram.types import (
    CallbackQuery, InlineQuery, InlineQueryResultArticle, 
    InputTextMessageContent
)
from Main.core.client import Altruix
from Main.core.types.message import Message as AltruixMessage
from Main.core.decorators import log_errors, iuser_check

# Modular Imports
from .db_handler import db_handler
from .identity_gen import generate_identity, get_avatar_url
from .ui_builder import build_main_dashboard, build_session_list, build_edit_menu, build_confirmation_menu

logger = logging.getLogger("altruix.xprofile")

# Background Task Queue
UPDATE_QUEUE = asyncio.Queue()
STATE = {"is_processing": False}
PLUGIN_VERSION = "1.0.0"

async def get_profile_preview_text(client, me, db_data):
    """Helper to generate the profile preview text."""
    try:
        full_me = await client.get_me()
        curr_name = f"{full_me.first_name} {full_me.last_name or ''}".strip()
        curr_bio = full_me.bio or "Tidak ada bio"
        curr_username = f"@{full_me.username}" if full_me.username else "Tidak ada"
    except Exception:
        curr_name = me.first_name or "Unknown"
        curr_bio = "Gagal memuat bio"
        curr_username = "Unknown"
        
    return (
        f"<blockquote expandable>"
        f"<b>👤 Manage Session:</b>\n"
        f"• Account:  {me.first_name or ''} {me.last_name or ''}\n"
        f"• ID: <code>{me.id}</code>\n"
        f"• Username: {curr_username}\n\n"
        f"<b>📝 Profile Preview:</b>\n"
        f"• <b>Name:</b> <code>{curr_name}</code>\n"
        f"• <b>Bio:</b> <i>{curr_bio}</i>\n\n"
        f"<b>⚙️ Status:</b>\n"
        f"• <b>Lock:</b> {'🔒 LOCKED' if db_data.get('is_locked') else '🔓 UNLOCKED'}\n"
        f"• <b>Pref Gender:</b> <code>{db_data.get('gender', 'random').upper()}</code>"
        f"</blockquote>"
    )

async def strip_metadata(image_bytes: bytes) -> bytes:
    """Remove metadata from image using Pillow."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        # Create a new image without metadata
        data = list(img.getdata())
        new_img = Image.new(img.mode, img.size)
        new_img.putdata(data)
        
        out = io.BytesIO()
        new_img.save(out, format="JPEG", quality=95)
        return out.getvalue()
    except Exception as e:
        logger.error(f"Failed to strip metadata: {e}")
        return image_bytes

async def profile_update_task():
    """Background task to process profile updates with anti-flood."""
    if STATE["is_processing"]:
        return
    STATE["is_processing"] = True
    while not UPDATE_QUEUE.empty():
        client_idx, action_type, requester_id = await UPDATE_QUEUE.get()
        try:
            if client_idx >= len(Altruix.clients):
                continue
                
            client = Altruix.clients[client_idx]
            me = getattr(client, 'myself', None)
            if not me:
                continue
                
            # Check Lock
            if await db_handler.is_locked(me.id):
                logger.info(f"Skipping locked session: {me.id}")
                continue
            
            if action_type == "undo":
                backup = await db_handler.get_backup(me.id)
                if backup:
                    try:
                        await client.update_profile(
                            first_name=backup.get('first_name', ''),
                            last_name=backup.get('last_name', ''),
                            bio=backup.get('bio', '')
                        )
                        logger.info(f"Successfully undid profile for {me.id}")
                    except Exception as e:
                        logger.error(f"Error undoing profile for {me.id}: {e}")
                continue # Skip avatar and username generation

            # Generate Identity
            name, bio, username = generate_identity(action_type)
            
            # Save Backup before changes
            try:
                full_me = await client.get_me()
                await db_handler.save_backup(
                    me.id, 
                    full_me.first_name, 
                    full_me.last_name or "", 
                    full_me.bio or ""
                )
            except Exception as eb:
                logger.warning(f"Failed to save backup for {me.id}: {eb}")

            # Update Telegram Profile
            try:
                # 1. Name
                names = name.split(" ", 1)
                first = names[0]
                last = names[1] if len(names) > 1 else ""
                await client.update_profile(first_name=first, last_name=last, bio=bio)
                
                # 2. Username (Optional, may fail if occupied)
                try:
                    await client.set_username(username)
                except Exception:
                    pass # Silently fail for username
                
                # 3. Avatar
                db_data = await db_handler.get_profile_data(me.id)
                avatar_src = db_data.get("avatar_src", "xsgames")
                pin_keyword = db_data.get("pinterest_keyword")
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(await get_avatar_url(action_type, avatar_src, keyword=pin_keyword)) as resp:
                            if resp.status == 200:
                                img_data = await resp.read()
                                clean_img = await strip_metadata(img_data)
                                
                                # Save to temp file because pyrogram prefers files
                                temp_path = f"cache/avatar_{me.id}.jpg"
                                with open(temp_path, "wb") as f:
                                    f.write(clean_img)
                                
                                await client.set_profile_photo(photo=temp_path)
                            else:
                                logger.error(f"API Error {avatar_src} status {resp.status} for {me.id}")
                except Exception as api_err:
                    logger.error(f"Failed to fetch avatar from {avatar_src}: {api_err}")
                
                logger.info(f"Successfully updated profile for {me.id}")
                
            except Exception as e:
                logger.error(f"Error updating profile for {me.id}: {e}")
                
            # Anti-Flood Delay
            await asyncio.sleep(random.uniform(5, 15))
            
        finally:
            UPDATE_QUEUE.task_done()
    STATE["is_processing"] = False

# --- COMMAND HANDLERS ---

@Altruix.register_on_cmd(
    ["xprofile", "prof"],
    cmd_help={
        "help": "Membuka Dashboard Profile Manager Pro.",
        "usage": ".xprofile",
        "example": ".xprofile",
        "detail": (
            "Fitur ini memungkinkan Anda untuk mengelola profil (Nama, Bio, Username) "
            "dan Foto Profil secara massal untuk semua sesi yang terhubung.\n\n"
            "<b>Fitur Utama:</b>\n"
            "• <b>Bulk Set (Boy/Girl/Random):</b> Update semua sesi sekaligus.\n"
            "• <b>Persona Lock:</b> Kunci sesi tertentu agar tidak terkena update massal.\n"
            "• <b>AI Avatar:</b> Update foto profil otomatis menggunakan gambar hasil AI.\n"
            "• <b>Privacy:</b> Membersihkan metadata (EXIF) pada setiap foto yang diunggah."
        ),
        "note": "Update massal memiliki delay 5-15 detik per sesi untuk menghindari limitasi API Telegram (FloodWait).",
        "utility": "Identity & Profile Management",
    },
)
@log_errors
@iuser_check
async def xprofile_cmd_handler(c: Client, m: AltruixMessage):
    """Command to open the main dashboard."""
    user_id = m.from_user.id
    try:
        bot_username = Altruix.bot_manager.get_bot_username(c.me.id)
        results = await c.get_inline_bot_results(bot_username, f"xprof_main_{c.me.id}")
        await c.send_inline_bot_result(
            chat_id=m.chat.id,
            query_id=results.query_id,
            result_id=results.results[0].id,
            reply_to_message_id=m.reply_to_message.id if m.reply_to_message else m.id,
        )
        await m.delete_if_self()
    except Exception as e:
        logger.error(f"Failed to send inline dashboard: {e}")
        # Fallback to normal reply if inline fails
        text = (
            f"<blockquote expandable>"
            "<b>💎 Profile Manager Pro</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Kelola identitas semua sesi Anda dengan mudah.\n"
            "Gunakan fitur bulk untuk update massal atau edit per sesi.\n\n"
            "<i>Pilih menu di bawah ini:</i>"
            f"</blockquote>"
        )
        await m.reply_msg(text, reply_markup=build_main_dashboard(user_id))

# --- BOT ASSISTANT HANDLERS MOVED TO Main/plugins/bot/XProfile_Manager_Pro/bot_handlers.py ---
