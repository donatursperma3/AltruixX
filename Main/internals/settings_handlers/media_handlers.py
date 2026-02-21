# Main/internals/settings_handlers/media_handlers.py
import html
import os
import asyncio
import logging
import traceback
import sys
import io
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from Main.core.decorators import log_errors, iuser_check
from Main.core.client import Altruix
from pyrogram.enums import ParseMode
from .utils import send_log_notification

# Shared State
from .states import user_profile_edit_state

logger = logging.getLogger(__name__)

@Altruix.bot.on_callback_query(filters.regex(r"^gen_conf_dlstory_session_input_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def dlstory_input_handler(c: Client, cb: CallbackQuery):
    """Start story download process"""
    index, page = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    await cb.answer()
    user_id = cb.from_user.id
    user_profile_edit_state[user_id] = {'action': 'download_story', 'session_index': index, 'page': page}
    await cb.edit_message_text(
        "📥 <b>Download Story</b>\n\n"
        "Silakan kirim <b>Username</b> atau <b>ID</b> user yang ingin didownload story-nya.\n\n"
        "❌ <b>Cancel:</b> /cancel",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}")]])
    )

@Altruix.bot.on_callback_query(filters.regex(r"^gen_conf_dl_content_input_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def dllink_input_handler(c: Client, cb: CallbackQuery):
    """Start content download from link"""
    index, page = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    await cb.answer()
    
    # Correction: page should be group(2)
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    
    user_id = cb.from_user.id
    user_profile_edit_state[user_id] = {'action': 'download_content', 'session_index': index, 'page': page}
    await cb.edit_message_text(
        "💾 <b>Download Content</b>\n\n"
        "Silakan kirim <b>Link Pesan</b> (t.me/...) yang ingin didownload kontennya.\n\n"
        "❌ <b>Cancel:</b> /cancel",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}")]])
    )

async def process_media_input(c: Client, m: Message, state: dict):
    """Router for media-related text inputs"""
    action = state['action']
    index = state['session_index']
    page = state['page']
    text = m.text.strip()
    user_id = m.from_user.id
    
    session_client = Altruix.clients[index]
    
    try:
        if action == 'download_story':
            status_msg = await m.reply("📥 Downloading stories...")
            target = text.lstrip('@')
            user = await session_client.get_users(int(target) if target.isdigit() else target)
            
            stories = []
            async for story in session_client.get_stories(user.id):
                stories.append(story)
            
            if not stories:
                await status_msg.edit("❌ No stories found.")
                del user_profile_edit_state[user_id]
                return
            
            await status_msg.edit(f"📥 Found {len(stories)} stories. Downloading...")
            for story in stories:
                try:
                    file_path = await session_client.download_media(story)
                    await m.reply_document(file_path)
                    if os.path.exists(file_path): os.remove(file_path)
                except: continue
                
            await status_msg.edit(f"✅ Success downloaded {len(stories)} stories.")
            
        elif action == 'download_content':
            status_msg = await m.reply("💾 Downloading content...")
            try:
                msg = await session_client.get_messages_from_link(text)
                if msg.media:
                    file_path = await session_client.download_media(msg)
                    await m.reply_document(file_path)
                    if os.path.exists(file_path): os.remove(file_path)
                    await status_msg.edit("✅ Content downloaded!")
                else:
                    await status_msg.edit("❌ No media found in this link.")
            except Exception as e:
                await status_msg.edit(f"❌ Error: {e}")

    except Exception as e:
        await m.reply(f"❌ <b>Error:</b> {str(e)}")
        
    del user_profile_edit_state[user_id]
    await asyncio.sleep(2)
    await m.reply("🔄 Memuat ulang menu...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Dashboard", f"session_info_{index}_{page}")]]))
