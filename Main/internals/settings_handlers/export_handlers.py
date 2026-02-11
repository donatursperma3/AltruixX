# Main/internals/settings_handlers/export_handlers.py
import html
import os
import asyncio
import io
import logging
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait, PeerIdInvalid, UserIsBlocked, ChatWriteForbidden

from Main.core.decorators import log_errors, iuser_check
from Main.core.client import Altruix

# Utils & States
from .utils import edit_cb, check_authorization, gt
from .states import user_confirmation_state, user_text_confirmation_state

# Logger
logger = logging.getLogger(__name__)

# ====================== EXPORT SESSIONS FEATURE ======================
@Altruix.bot.on_callback_query(filters.regex("export_all_sessions_confirmation"))
@log_errors
@iuser_check
async def export_all_sessions_confirmation_handler(c: Client, cb: CallbackQuery):
    """Handler for export all sessions confirmation prompt."""
    if not await check_authorization(cb): return
    await cb.answer()
    
    user_id = cb.from_user.id
    user_confirmation_state[user_id] = {
        'action': 'export_all_sessions',
        'message_id': cb.message.id if cb.message else 0,
        'chat_id': cb.message.chat.id if cb.message else 0
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
@iuser_check
async def export_all_sessions_cancel_handler(c: Client, cb: CallbackQuery):
    """Handler to cancel export all sessions."""
    if not await check_authorization(cb): return
    await cb.answer("Operation cancelled.")
    
    user_id = cb.from_user.id
    if user_id in user_confirmation_state:
        del user_confirmation_state[user_id]
    
    from .sessions_list import sessions_menu_cb_handler
    await sessions_menu_cb_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex("export_all_sessions_confirm_yes"))
@log_errors
@iuser_check
async def export_all_sessions_confirm_yes_handler(c: Client, cb: CallbackQuery):
    """Handler for security verification before exporting all sessions."""
    if not await check_authorization(cb): return
    user_id = cb.from_user.id
    
    if user_id in user_confirmation_state:
        user_confirmation_state[user_id]['step'] = 'waiting_text_confirmation'
        user_text_confirmation_state[user_id] = {
            'action': 'export_all_sessions',
            'message_id': cb.message.id if cb.message else 0,
            'chat_id': cb.message.chat.id if cb.message else 0,
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

# ====================== EXPORT PHONES FEATURE ======================
@Altruix.bot.on_callback_query(filters.regex("export_all_phones_confirmation"))
@log_errors
@iuser_check
async def export_all_phones_confirmation_handler(c: Client, cb: CallbackQuery):
    """Handler for export all phones confirmation prompt."""
    if not await check_authorization(cb): return
    await cb.answer()
    
    user_id = cb.from_user.id
    user_confirmation_state[user_id] = {
        'action': 'export_all_phones',
        'message_id': cb.message.id if cb.message else 0,
        'chat_id': cb.message.chat.id if cb.message else 0
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
@iuser_check
async def export_all_phones_cancel_handler(c: Client, cb: CallbackQuery):
    """Handler to cancel export all phones."""
    if not await check_authorization(cb): return
    await cb.answer("Operation cancelled.")
    
    user_id = cb.from_user.id
    if user_id in user_confirmation_state:
        del user_confirmation_state[user_id]
    
    from .sessions_list import sessions_menu_cb_handler
    await sessions_menu_cb_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex("export_all_phones_confirm_yes"))
@log_errors
@iuser_check
async def export_all_phones_confirm_yes_handler(c: Client, cb: CallbackQuery):
    """Handler for security verification before exporting all phone numbers."""
    if not await check_authorization(cb): return
    user_id = cb.from_user.id
    
    if user_id in user_confirmation_state:
        user_confirmation_state[user_id]['step'] = 'waiting_text_confirmation'
        user_text_confirmation_state[user_id] = {
            'action': 'export_all_phones',
            'message_id': cb.message.id if cb.message else 0,
            'chat_id': cb.message.chat.id if cb.message else 0,
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

# ====================== EXECUTION LOGIC ======================
async def execute_export_all_sessions(c: Client, m: Message):
    """Executes the export of all sessions to a file."""
    user = m.from_user
    user_id = user.id
    log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))
    user_name = html.escape(user.first_name if user.first_name else "User")
    user_link = f"<a href='tg://user?id={user_id}'>{user_name}</a>"
    
    if user_id not in Altruix.auth_users:
        await m.reply("⛔ You are not authorized to use this feature.")
        return
    
    if not hasattr(Altruix, 'clients') or not Altruix.clients:
        await m.reply("❌ No sessions available to export.")
        return
    
    status_msg = await m.reply("📤 Preparing to export all sessions...")
    
    try:
        session_data = []
        for index, client in enumerate(Altruix.clients):
            try:
                user_info = getattr(client, 'myself', None)
                if not user_info:
                    try: user_info = await client.get_me()
                    except: user_info = None
                
                if user_info:
                    full_name = html.escape(f"{user_info.first_name or ''} {user_info.last_name or ''}".strip())
                    username = f"@{user_info.username}" if user_info.username else "None"
                    phone = getattr(user_info, 'phone_number', 'Unknown')
                    
                    try: session_string = await client.export_session_string()
                    except Exception as e: session_string = f"Error: {e}"
                    
                    session_data.append(
                        f"=== SESSION {index + 1} ===\n"
                        f"Name: {full_name}\n"
                        f"Phone: +{phone}\n"
                        f"ID: {user_info.id}\n"
                        f"Username: {username}\n"
                        f"DC ID: {getattr(user_info, 'dc_id', 'Unknown')}\n"
                        f"Session String:\n{session_string}\n"
                        f"{'=' * 40}\n"
                    )
            except Exception as e:
                session_data.append(f"=== SESSION {index + 1} ERROR ===\n{e}\n{'=' * 40}\n")
        
        file_content = "⚠️ WARNING: KEEP THIS FILE SECURE! ⚠️\n" + ("=" * 50) + "\n\n" + "".join(session_data)
        file_stream = io.BytesIO(file_content.encode())
        file_stream.name = f"all_sessions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        await c.send_document(
            chat_id=user_id,
            document=file_stream,
            caption="📤 **All Sessions Exported**",
            parse_mode=ParseMode.HTML
        )
        
        await Altruix.bot.send_message(
            log_chat_id,
            f"📤 <b>EXPORT ALL SESSIONS COMPLETED</b>\n"
            f"• User: {user_link}\n• Status: ✅ Success",
            parse_mode=ParseMode.HTML
        )
        await status_msg.edit("✅ All sessions exported and sent to your PM.")
        
    except Exception as e:
        await m.reply(f"❌ Failed to export: {e}")
        logger.error(f"Error in execute_export_all_sessions: {e}")

async def execute_export_all_phones(c: Client, m: Message):
    """Executes the export of all phone numbers to a file."""
    user = m.from_user
    user_id = user.id
    log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))
    user_name = html.escape(user.first_name if user.first_name else "User")
    user_link = f"<a href='tg://user?id={user_id}'>{user_name}</a>"
    
    status_msg = await m.reply("📲 Preparing to export all phone numbers...")
    
    try:
        phone_data = []
        for index, client in enumerate(Altruix.clients):
            try:
                user_info = getattr(client, 'myself', None)
                if not user_info:
                    try: user_info = await client.get_me()
                    except: user_info = None
                
                if user_info:
                    full_name = html.escape(f"{user_info.first_name or ''} {user_info.last_name or ''}".strip())
                    phone = getattr(user_info, 'phone_number', 'Unknown')
                    phone_data.append(f"{index+1}. {full_name}: +{phone}\n")
            except Exception as e:
                phone_data.append(f"{index+1}. Error: {e}\n")
        
        file_content = "📲 Account Phone Numbers\n" + ("=" * 40) + "\n\n" + "".join(phone_data)
        file_stream = io.BytesIO(file_content.encode())
        file_stream.name = f"all_phones_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        await c.send_document(chat_id=user_id, document=file_stream, caption="📲 **All Phones Exported**")
        await Altruix.bot.send_message(
            log_chat_id,
            f"📲 <b>EXPORT ALL PHONES COMPLETED</b>\n"
            f"• User: {user_link}\n• Status: ✅ Success",
            parse_mode=ParseMode.HTML
        )
        await status_msg.edit("✅ All phone numbers exported and sent to your PM.")
        
    except Exception as e:
        await m.reply(f"❌ Failed to export: {e}")

async def clear_user_state_after_timeout(user_id: int, timeout: int):
    """Clears user state after a specified timeout period."""
    await asyncio.sleep(timeout)
    if user_id in user_text_confirmation_state:
        del user_text_confirmation_state[user_id]
        if user_id in user_confirmation_state:
            del user_confirmation_state[user_id]
