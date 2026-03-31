# Main/internals/settings_handlers/stats_handlers.py
import html
import os
import asyncio
import logging
from pyrogram import Client, filters, enums
from pyrogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from Main.core.decorators import log_errors, iuser_check
from Main.core.client import Altruix
from pyrogram.enums import ParseMode, ChatType
from .utils import send_log_notification, gt, edit_cb, check_authorization

# Logger
logger = logging.getLogger(__name__)

@Altruix.bot.on_callback_query(filters.regex(r"^chat_stats_scan_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def chat_stats_scan_handler(c: Client, cb: CallbackQuery):
    """Scan account for chat statistics (Admin/Owner in Groups & Channels)"""
    index, page = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    await cb.answer("📊 Scanning admin/owner status...", show_alert=False)
    
    if index >= len(Altruix.clients): return
    client = Altruix.clients[index]
    
    try:
        await cb.edit_message_text("🔄 <b>Scanning Dialogs... (Checking Permissions)</b>", parse_mode=ParseMode.HTML)
        
        owned_groups = 0
        admin_groups = 0
        owned_channels = 0
        admin_channels = 0
        
        # Get my ID to check status
        me = await client.get_me()
        
        async for dialog in client.get_dialogs():
            chat = dialog.chat
            if chat.type in [ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL]:
                try:
                    member = await chat.get_member(me.id)
                    is_owner = member.status == enums.ChatMemberStatus.OWNER
                    is_admin = member.status == enums.ChatMemberStatus.ADMINISTRATOR
                    
                    if chat.type == ChatType.CHANNEL:
                        if is_owner: owned_channels += 1
                        elif is_admin: admin_channels += 1
                    else:
                        if is_owner: owned_groups += 1
                        elif is_admin: admin_groups += 1
                except:
                    # Likely no permission to get member info or not an admin
                    pass
        
        txt = (
            f"<b>📊 Detailed Statistics (Session {index+1})</b>\n\n"
            f"👤 <b>Groups:</b>\n"
            f"• Owned: <code>{owned_groups}</code>\n"
            f"• Admin: <code>{admin_groups}</code>\n\n"
            f"📢 <b>Channels:</b>\n"
            f"• Owned: <code>{owned_channels}</code>\n"
            f"• Admin: <code>{admin_channels}</code>\n\n"
            f"<i>💡 Total Managed: {owned_groups + admin_groups + owned_channels + admin_channels}</i>"
        )
        
        from Main.utils.file_helpers import get_user_button_style
        if index < len(Altruix.clients):
            user_style = get_user_button_style(Altruix.clients[index].me.id)
        else:
            user_style = get_user_button_style(cb.from_user.id)
        
        await cb.edit_message_text(
            txt,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}", style=user_style)]]),
            parse_mode=ParseMode.HTML
        )
        await send_log_notification(c, 'chat_stats_scan', index, cb.from_user, True)
    except Exception as e:
        from Main.utils.file_helpers import get_user_button_style
        if index < len(Altruix.clients):
            user_style = get_user_button_style(Altruix.clients[index].me.id)
        else:
            user_style = get_user_button_style(cb.from_user.id)
        await cb.edit_message_text(f"❌ Error scanning stats: {str(e)}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}", style=user_style)]]))
        await send_log_notification(c, 'chat_stats_scan', index, cb.from_user, False, str(e))

@Altruix.bot.on_callback_query(filters.regex(r"^sessions_stats(?:_(\d+))?$"))
@log_errors
@iuser_check
async def sessions_stats_cb_handler(c: Client, cb: CallbackQuery):
    """Handler untuk menampilkan statistik sesi secara interaktif"""
    if not await check_authorization(cb): return
    await cb.answer()
    
    total_sessions = len(Altruix.clients) if hasattr(Altruix, 'clients') else 0
    inactive_sessions = 0
    
    # Simple check for active clients
    active_sessions = 0
    for client in Altruix.clients:
        if getattr(client, 'is_connected', False):
            active_sessions += 1
    
    inactive_sessions = total_sessions - active_sessions
    total_custom_bots = len(Altruix.bot_manager.custom_bots) if hasattr(Altruix, 'bot_manager') else 0
    
    txt = (
        f"<b>📊 In-Memory Session Statistics</b>\n\n"
        f"• Active Sessions: <code>{active_sessions}</code>\n"
        f"• Inactive Sessions: <code>{inactive_sessions}</code>\n"
        f"• Total Sessions: <code>{total_sessions}</code>\n"
        f"• Total Custom Bots: <code>{total_custom_bots}</code>\n\n"
        f"<i>💡 This data reflects current in-memory state.</i>"
    )
    
    index = int(cb.matches[0].group(1)) if cb.matches and len(cb.matches[0].groups()) >= 1 and cb.matches[0].group(1) else None
    
    from Main.utils.file_helpers import get_user_button_style
    if index is not None and index < len(Altruix.clients):
        user_style = get_user_button_style(Altruix.clients[index].me.id)
    else:
        user_style = get_user_button_style(cb.from_user.id)
    
    buttons = [
        [InlineKeyboardButton("🔄 Refresh Data", f"sessions_stats{'_' + str(index) if index is not None else ''}", style=user_style)],
        [InlineKeyboardButton("🔙 Back", f"session_info_{index}_1_5" if index is not None else "sessions_list_1", style=user_style)]
    ]
    
    await edit_cb(cb, txt, reply_markup=InlineKeyboardMarkup(buttons))
