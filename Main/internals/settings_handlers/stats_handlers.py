# Main/internals/settings_handlers/stats_handlers.py
import html
import os
import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from Main.core.decorators import log_errors, iuser_check
from Main.core.client import Altruix
from pyrogram.enums import ParseMode, ChatType
from .utils import send_log_notification, gt, edit_cb, check_authorization

# Logger
logger = logging.getLogger(__name__)

@Altruix.bot.on_callback_query(filters.regex(r"^gen_conf_chat_stats_scan_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def chat_stats_scan_handler(c: Client, cb: CallbackQuery):
    """Scan account for chat statistics (Dialogs, Groups, Channels)"""
    index, page = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    await cb.answer("📊 Scanning account stats...", show_alert=False)
    
    if index >= len(Altruix.clients): return
    client = Altruix.clients[index]
    
    try:
        status_msg = await cb.message.edit("🔄 <b>Scanning Dialogs...</b>", parse_mode=ParseMode.HTML)
        
        dialogs_count = 0
        groups_count = 0
        channels_count = 0
        bots_count = 0
        users_count = 0
        
        async for dialog in client.get_dialogs():
            dialogs_count += 1
            chat = dialog.chat
            if chat.type == ChatType.PRIVATE:
                if chat.is_bot: bots_count += 1
                else: users_count += 1
            elif chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                groups_count += 1
            elif chat.type == ChatType.CHANNEL:
                channels_count += 1
        
        txt = (
            f"<b>📊 Account Statistics (Session {index+1})</b>\n\n"
            f"• <b>Total Dialogs:</b> <code>{dialogs_count}</code>\n"
            f"• <b>Groups:</b> <code>{groups_count}</code>\n"
            f"• <b>Channels:</b> <code>{channels_count}</code>\n"
            f"• <b>Users:</b> <code>{users_count}</code>\n"
            f"• <b>Bots:</b> <code>{bots_count}</code>\n"
        )
        
        await status_msg.edit(
            txt,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}")]]),
            parse_mode=ParseMode.HTML
        )
        await send_log_notification(c, 'chat_stats_scan', index, cb.from_user, True)
    except Exception as e:
        await cb.message.edit(f"❌ Error scanning stats: {str(e)}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}")]]))
        await send_log_notification(c, 'chat_stats_scan', index, cb.from_user, False, str(e))

@Altruix.bot.on_callback_query(filters.regex("^sessions_stats$"))
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
    
    buttons = [
        [InlineKeyboardButton("🔄 Refresh Data", "sessions_stats")],
        [InlineKeyboardButton("🔙 Back", "sessions_list_1")]
    ]
    
    await edit_cb(cb, txt, reply_markup=InlineKeyboardMarkup(buttons))
