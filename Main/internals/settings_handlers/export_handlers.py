# Main/internals/settings_handlers/export_handlers.py
import html
import os
import traceback
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
@Altruix.bot.on_callback_query(filters.regex(r"^export_all_sessions_confirmation$"))
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
    
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(user_id)

    confirmation_buttons = [
        [
            InlineKeyboardButton("✅ Yes", callback_data="export_all_sessions_confirm_yes", style=user_style),
            InlineKeyboardButton("❌ No", callback_data="export_all_sessions_confirm_no", style=user_style)
        ]
    ]

    text = (
        "<blockquote expandable>"
        "❓ <b>Export All Sessions Confirmation</b>\n\n"
        "Are you sure you want to export ALL session strings?\n\n"
        "⚠️ <b>WARNING:</b>\n"
        "• This will export session strings for ALL your accounts\n"
        "• Session strings can be used to login to your accounts\n"
        "• Keep them secure and DO NOT share with anyone"
        "</blockquote>"
    )
    
    await edit_cb(cb, 
        text=text,
        reply_markup=InlineKeyboardMarkup(confirmation_buttons),
        parse_mode=ParseMode.HTML
    )

@Altruix.bot.on_callback_query(filters.regex(r"^export_all_sessions_confirm_no$"))
@log_errors
@iuser_check
async def export_all_sessions_cancel_handler(c: Client, cb: CallbackQuery):
    """Handler to cancel export all sessions."""
    if not await check_authorization(cb): return
    await cb.answer("Operation cancelled.")
    
    user_id = cb.from_user.id
    if user_id in user_confirmation_state:
        del user_confirmation_state[user_id]
    
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(user_id)
    await edit_cb(cb, "❌ Operation cancelled.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", "bulk_controls_menu", style=user_style)]]))

@Altruix.bot.on_callback_query(filters.regex(r"^export_all_sessions_confirm_yes$"))
@log_errors
@iuser_check
async def export_all_sessions_confirm_yes_handler(c: Client, cb: CallbackQuery):
    """Handler for security verification before exporting all sessions."""
    if not await check_authorization(cb): return
    user_id = cb.from_user.id
    
    if user_id in user_confirmation_state:
        del user_confirmation_state[user_id]
    
    await cb.answer("Exporting sessions...", show_alert=False)
    # We pass the callback query to the execution handler
    await execute_export_all_sessions(c, cb)


# ====================== EXPORT PHONES FEATURE ======================
@Altruix.bot.on_callback_query(filters.regex(r"^export_all_phones_confirmation$"))
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
    
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(user_id)

    confirmation_buttons = [
        [
            InlineKeyboardButton("✅ Yes", callback_data="export_all_phones_confirm_yes", style=user_style),
            InlineKeyboardButton("❌ No", callback_data="export_all_phones_confirm_no", style=user_style)
        ]
    ]

    text = (
        "<blockquote expandable>"
        "❓ <b>Export All Phone Numbers Confirmation</b>\n\n"
        "Are you sure you want to export ALL phone numbers?\n\n"
        "⚠️ <b>NOTE:</b>\n"
        "• This will export phone numbers for ALL your accounts\n"
        "• Phone numbers are sensitive information\n"
        "• Keep them secure and share only with trusted parties"
        "</blockquote>"
    )
    
    await edit_cb(cb, 
        text=text,
        reply_markup=InlineKeyboardMarkup(confirmation_buttons),
        parse_mode=ParseMode.HTML
    )

@Altruix.bot.on_callback_query(filters.regex(r"^export_all_phones_confirm_no$"))
@log_errors
@iuser_check
async def export_all_phones_cancel_handler(c: Client, cb: CallbackQuery):
    """Handler to cancel export all phones."""
    if not await check_authorization(cb): return
    await cb.answer("Operation cancelled.")
    
    user_id = cb.from_user.id
    if user_id in user_confirmation_state:
        del user_confirmation_state[user_id]
    
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(user_id)
    await edit_cb(cb, "❌ Operation cancelled.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", "bulk_controls_menu", style=user_style)]]))

@Altruix.bot.on_callback_query(filters.regex(r"^export_all_phones_confirm_yes$"))
@log_errors
@iuser_check
async def export_all_phones_confirm_yes_handler(c: Client, cb: CallbackQuery):
    """Handler for security verification before exporting all phone numbers."""
    if not await check_authorization(cb): return
    user_id = cb.from_user.id
    
    if user_id in user_confirmation_state:
        del user_confirmation_state[user_id]
    
    await cb.answer("Exporting phones...", show_alert=False)
    # We pass the callback query to the execution handler
    await execute_export_all_phones(c, cb)

async def execute_export_all_sessions(c: Client, event):
    """Executes the export of all sessions to a file."""
    user = event.from_user
    user_id = user.id
    m = event.message if isinstance(event, CallbackQuery) else event
    
    log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_USERS_ID))
    user_name = html.escape(user.first_name if user.first_name else "User")
    user_link = f"<a href='tg://user?id={user_id}'>{user_name}</a>"
    
    if not await Altruix.is_sudo(user_id):
        if hasattr(event, "answer"):
            await event.answer("⛔ You are not authorized to use this feature.", show_alert=True)
        else:
            await m.reply("⛔ You are not authorized to use this feature.")
        return
    
    if not hasattr(Altruix, 'clients') or not Altruix.clients:
        if hasattr(event, "answer"):
            await event.answer("❌ No sessions available to export.", show_alert=True)
        else:
            await m.reply("❌ No sessions available to export.")
        return
    
    if isinstance(event, CallbackQuery):
        await edit_cb(event, "📤 Preparing to export all sessions...")
        status_msg = event.message
    else:
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
        
        try:
            await c.send_document(
                chat_id=user_id,
                document=file_stream,
                caption="📤 <b>All Sessions Exported</b>",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            Altruix.log(f"❌ [ExportSessions] send_document error: {e}")
        
        try:
            await Altruix.bot.send_message(
                log_chat_id,
                f"<blockquote expandable>"
                f"📤 <b>EXPORT ALL SESSIONS COMPLETED</b>\n"
                f"• User: {user_link}\n• Status: ✅ Success"
                f"</blockquote>",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            Altruix.log(f"❌ [ExportSessions] log_notification error: {e}")
        from Main.utils.file_helpers import get_user_button_style
        user_style = get_user_button_style(user_id)
        await status_msg.edit(
            "✅ All sessions exported and sent to your PM.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", "bulk_controls_menu", style=user_style)]])
        )
        
    except Exception as e:
        logger.error(f"Error in execute_export_all_sessions: {e}")
        try:
            from Main.utils.file_helpers import get_user_button_style
            user_style = get_user_button_style(user_id)
            await status_msg.edit(
                f"❌ Failed to export: {e}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", "bulk_controls_menu", style=user_style)]])
            )
        except:
            try: await m.reply(f"❌ Failed to export: {e}")
            except: pass

async def execute_export_all_phones(c: Client, event):
    """Executes the export of all phone numbers to a file."""
    user = event.from_user
    user_id = user.id
    m = event.message if isinstance(event, CallbackQuery) else event
    
    log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_USERS_ID))
    user_name = html.escape(user.first_name if user.first_name else "User")
    user_link = f"<a href='tg://user?id={user_id}'>{user_name}</a>"
    
    if isinstance(event, CallbackQuery):
        await edit_cb(event, "📲 Preparing to export all phone numbers...")
        status_msg = event.message
    else:
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
        
        try:
            await c.send_document(chat_id=user_id, document=file_stream, caption="📲 **All Phones Exported**")
        except Exception as e:
            Altruix.log(f"❌ [ExportPhones] send_document error: {e}")

        try:
            await Altruix.bot.send_message(
                log_chat_id,
                f"<blockquote expandable>"
                f"📲 <b>EXPORT ALL PHONES COMPLETED</b>\n"
                f"• User: {user_link}\n• Status: ✅ Success"
                f"</blockquote>",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            Altruix.log(f"❌ [ExportPhones] log_notification error: {e}")
        from Main.utils.file_helpers import get_user_button_style
        user_style = get_user_button_style(user_id)
        await status_msg.edit(
            "✅ All phone numbers exported and sent to your PM.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", "bulk_controls_menu", style=user_style)]])
        )
        
    except Exception as e:
        try:
            from Main.utils.file_helpers import get_user_button_style
            user_style = get_user_button_style(user_id)
            await status_msg.edit(
                f"❌ Failed to export: {e}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", "bulk_controls_menu", style=user_style)]])
            )
        except:
            try: await m.reply(f"❌ Failed to export: {e}")
            except: pass

# ====================== EXPORT BOT TOKENS FEATURE ======================
@Altruix.bot.on_callback_query(filters.regex(r"^export_all_bot_tokens_confirmation$"))
@log_errors
@iuser_check
async def export_all_bot_tokens_confirmation_handler(c: Client, cb: CallbackQuery):
    """Handler for export all bot tokens confirmation prompt."""
    if not await check_authorization(cb): return
    await cb.answer()
    
    try:
        user_id = cb.from_user.id
        user_confirmation_state[user_id] = {
            'action': 'export_all_bot_tokens',
            'message_id': cb.message.id if cb.message else 0,
            'chat_id': cb.message.chat.id if cb.message else 0
        }
        
        from Main.utils.file_helpers import get_user_button_style
        user_style = get_user_button_style(user_id)

        confirmation_buttons = [
            [
                InlineKeyboardButton("✅ Yes", callback_data="export_all_bot_tokens_confirm_yes", style=user_style),
                InlineKeyboardButton("❌ No", callback_data="export_all_bot_tokens_confirm_no", style=user_style)
            ]
        ]

        text = (
            "<blockquote expandable>"
            "❓ <b>Export All Bot Tokens Confirmation</b>\n\n"
            "Are you sure you want to export ALL Custom Bot Tokens?\n\n"
            "⚠️ <b>WARNING:</b>\n"
            "• This will export bot tokens for ALL your custom bots\n"
            "• Anyone with access to these tokens can control your bots\n"
            "• Keep them secure and DO NOT share with anyone"
            "</blockquote>"
        )
        
        await edit_cb(cb, 
            text=text,
            reply_markup=InlineKeyboardMarkup(confirmation_buttons),
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        Altruix.log(f"❌ [ExportBotTokens] confirmation_handler error: {e}\n{traceback.format_exc()}", level=logging.ERROR)
        try: await cb.answer(f"❌ Error: {str(e)[:100]}", show_alert=True)
        except: pass

@Altruix.bot.on_callback_query(filters.regex(r"^export_all_bot_tokens_confirm_no$"))
@log_errors
@iuser_check
async def export_all_bot_tokens_cancel_handler(c: Client, cb: CallbackQuery):
    """Handler to cancel export all bot tokens."""
    if not await check_authorization(cb): return
    await cb.answer("Operation cancelled.")
    
    try:
        user_id = cb.from_user.id
        if user_id in user_confirmation_state:
            del user_confirmation_state[user_id]
        
        from Main.utils.file_helpers import get_user_button_style
        user_style = get_user_button_style(user_id)
        await edit_cb(cb, "❌ Operation cancelled.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", "bulk_controls_menu", style=user_style)]]))
    except Exception as e:
        Altruix.log(f"❌ [ExportBotTokens] cancel_handler error: {e}\n{traceback.format_exc()}", level=logging.ERROR)
        try: await cb.answer(f"❌ Error: {str(e)[:100]}", show_alert=True)
        except: pass

@Altruix.bot.on_callback_query(filters.regex(r"^export_all_bot_tokens_confirm_yes$"))
@log_errors
@iuser_check
async def export_all_bot_tokens_confirm_yes_handler(c: Client, cb: CallbackQuery):
    """Handler for security verification before exporting all bot tokens."""
    if not await check_authorization(cb): return
    user_id = cb.from_user.id
    
    try:
        if user_id in user_confirmation_state:
            del user_confirmation_state[user_id]
        
        await cb.answer("Exporting bot tokens...", show_alert=False)
        await execute_export_all_bot_tokens(c, cb)
    except Exception as e:
        Altruix.log(f"❌ [ExportBotTokens] confirm_yes error: {e}\n{traceback.format_exc()}", level=logging.ERROR)
        try: await cb.answer(f"❌ Error: {str(e)[:100]}", show_alert=True)
        except: pass

async def execute_export_all_bot_tokens(c: Client, event):
    """Executes the export of all custom bot tokens to a file."""
    user = event.from_user
    user_id = user.id
    m = event.message if isinstance(event, CallbackQuery) else event
    
    log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_USERS_ID))
    user_name = html.escape(user.first_name if user.first_name else "User")
    user_link = f"<a href='tg://user?id={user_id}'>{user_name}</a>"
    
    if not await Altruix.is_sudo(user_id):
        if hasattr(event, "answer"):
            await event.answer("⛔ You are not authorized to use this feature.", show_alert=True)
        else:
            await m.reply("⛔ You are not authorized to use this feature.")
        return
    
    if isinstance(event, CallbackQuery):
        await edit_cb(event, "🤖 Preparing to export all custom bot tokens...")
        status_msg = event.message
    else:
        status_msg = await m.reply("🤖 Preparing to export all custom bot tokens...")
    
    try:
        # Query bot tokens from the custom_bots database collection
        tokens_data = []
        if hasattr(Altruix, 'db') and hasattr(Altruix.db, 'make_collection'):
            col = Altruix.db.make_collection("custom_bots")
            async for doc in col.find({}):
                bot_id = doc.get("_id")
                token = doc.get("token")
                if bot_id and token:
                    # Find matching session index if possible
                    session_index = -1
                    session_phone = "Unknown"
                    for idx, client in enumerate(Altruix.clients):
                        if getattr(client, "me", None) and client.me.id == bot_id:
                            session_index = idx
                            session_phone = f"+{client.me.phone_number}" if client.me.phone_number else "Unknown"
                            break
                            
                    tokens_data.append(
                        f"=== BOT TOKEN ===\n"
                        f"Session Index: {session_index + 1 if session_index != -1 else 'Standalone'}\n"
                        f"Owner ID: {bot_id}\n"
                        f"Owner Phone: {session_phone}\n"
                        f"Bot Token:\n{token}\n"
                        f"{'=' * 40}\n"
                    )
        
        if not tokens_data:
            await status_msg.edit("❌ No custom bot tokens found to export.")
            return
            
        file_content = "⚠️ WARNING: KEEP THIS FILE SECURE! ⚠️\n" + ("=" * 50) + "\n\n" + "".join(tokens_data)
        file_stream = io.BytesIO(file_content.encode())
        file_stream.name = f"bot_tokens_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        try:
            await c.send_document(
                chat_id=user_id,
                document=file_stream,
                caption="🤖 <b>All Custom Bot Tokens Exported</b>",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            Altruix.log(f"❌ [ExportBotTokens] send_document error: {e}")
        
        try:
            await Altruix.bot.send_message(
                log_chat_id,
                f"<blockquote expandable>"
                f"🤖 <b>EXPORT ALL BOT TOKENS COMPLETED</b>\n"
                f"• User: {user_link}\n• Status: ✅ Success"
                f"</blockquote>",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            Altruix.log(f"❌ [ExportBotTokens] log_notification error: {e}")
        from Main.utils.file_helpers import get_user_button_style
        user_style = get_user_button_style(user_id)
        await status_msg.edit(
            "✅ All custom bot tokens exported and sent to your PM.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", "bulk_controls_menu", style=user_style)]])
        )
        
    except Exception as e:
        Altruix.log(f"❌ [ExportBotTokens] execute error: {e}\n{traceback.format_exc()}", level=logging.ERROR)
        try:
            from Main.utils.file_helpers import get_user_button_style
            user_style = get_user_button_style(user_id)
            await status_msg.edit(
                f"❌ Failed to export bot tokens: {e}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", "bulk_controls_menu", style=user_style)]])
            )
        except: 
            try: await m.reply(f"❌ Failed to export bot tokens: {e}")
            except: pass

async def clear_user_state_after_timeout(user_id: int, timeout: int):
    """Clears user state after a specified timeout period."""
    await asyncio.sleep(timeout)
    if user_id in user_text_confirmation_state:
        del user_text_confirmation_state[user_id]
        if user_id in user_confirmation_state:
            del user_confirmation_state[user_id]
