# xpeer_manager.py
# Interactive peer cleanup and leave chat management
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.

from Main import Altruix
from pyrogram import Client, filters, enums
from pyrogram.errors import PeerIdInvalid
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from Main.core.decorators import log_errors, iuser_check
from Main.utils.file_helpers import get_user_button_style
import logging
import html

logger = logging.getLogger("altruix.peer_manager")

@Altruix.bot.on_callback_query(filters.regex(r"^p_leave_req_(\d+)_(-?\d+)"))
@iuser_check
@log_errors
async def leave_request_callback(c: Client, cb: CallbackQuery):
    """Show confirmation for leaving a chat."""
    user_id = int(cb.matches[0].group(1))
    peer_id = int(cb.matches[0].group(2))
    
    # Resolve account name
    acc_name = "Unknown"
    for client in Altruix.clients:
        if client.me and client.me.id == user_id:
            acc_name = client.me.first_name
            break
            
    text = (
        "<blockquote expandable>"
        f"❓ <b>Konfirmasi Keluar Chat?</b>\n\n"
        f"• <b>Akun:</b> {acc_name} (<code>{user_id}</code>)\n"
        f"• <b>Chat ID:</b> <code>{peer_id}</code>\n\n"
        f"Apakah Anda yakin ingin memerintahkan akun ini keluar dari chat tersebut?"
        "</blockquote>"
    )
    
    # ✅ Resolve Button Style for this session
    user_style = get_user_button_style(user_id)
    
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Ya, Keluar", callback_data=f"p_leave_yes_{user_id}_{peer_id}", style=user_style),
            InlineKeyboardButton("❌ Batal", callback_data=f"p_leave_no_{user_id}_{peer_id}", style=user_style)
        ]
    ])
    
    await cb.edit_message_text(text, reply_markup=kb)

@Altruix.bot.on_callback_query(filters.regex(r"^p_leave_yes_(\d+)_(-?\d+)"))
@iuser_check
@log_errors
async def leave_execute_callback(c: Client, cb: CallbackQuery):
    """Execute leave chat command."""
    user_id = int(cb.matches[0].group(1))
    peer_id = int(cb.matches[0].group(2))
    
    # Find client
    target_client = None
    for client in Altruix.clients:
        if client.me and client.me.id == user_id:
            target_client = client
            break
            
    if not target_client:
        return await cb.answer("❌ Akun (Userbot) tidak ditemukan atau offline.", show_alert=True)
        
    await cb.edit_message_text(f"⏳ Sedang memerintahkan {target_client.me.first_name} keluar dari <code>{peer_id}</code>...")
    
    try:
        await target_client.leave_chat(peer_id)
        await cb.edit_message_text(
            "<blockquote expandable>"
            f"✅ <b>Successfully Exited</b>\n\n"
            f"• <b>Account:</b> {target_client.me.first_name}\n"
            f"• <b>Chat ID:</b> <code>{peer_id}</code>\n"
            f"• <b>Status:</b> Session cleared."
            "</blockquote>"
        )
    except PeerIdInvalid:
        logger.warning(f"Leave chat failed (PeerIdInvalid): {peer_id} for user {user_id}")
        msg = (
            "<blockquote expandable>"
            f"❌ <b>Logout Failed (Unknown ID)</b>\n\n"
            f"Account <b>{target_client.me.first_name}</b> doesn't recognize Chat ID <code>{peer_id}</code>.\n\n"
            f"💡 <b>Solution:</b>\n"
            f"1. Send any message to the chat from that account directly to refresh the cache.\n"
            f"2. If you can't access it, just ignore it because your account most likely doesn't exist."
            "</blockquote>"
        )
        await cb.edit_message_text(msg)
    except Exception as e:
        logger.error(f"Leave chat failed: {e}")
        await cb.edit_message_text(f"❌ <b>Leave Failed</b>\n\nError: <code>{html.escape(str(e))}</code>")

@Altruix.bot.on_callback_query(filters.regex(r"^p_leave_no_(\d+)_(-?\d+)"))
@iuser_check
@log_errors
async def leave_cancel_callback(c: Client, cb: CallbackQuery):
    """Cancel leave request and restore original message."""
    user_id = int(cb.matches[0].group(1))
    peer_id = int(cb.matches[0].group(2))
    
    # Resolve account name
    acc_name = "Unknown"
    for client in Altruix.clients:
        if client.me and client.me.id == user_id:
            acc_name = client.me.first_name
            break
            
    # Try to get chat title from cache
    chat_title = "Unknown Chat"
    if hasattr(Altruix, "PM_LOG_CACHE"):
        msg_key = f"{user_id}_{peer_id}"
        cached = Altruix.PM_LOG_CACHE.get(msg_key)
        if cached and isinstance(cached, dict):
            chat_title = cached.get("name") or cached.get("group_name") or "Unknown Chat"
            
    # Reconstruct chat link
    chat_link = None
    pid = str(peer_id)
    if pid.startswith("-100"):
        stripped_id = pid.replace("-100", "")
        chat_link = f"https://t.me/c/{stripped_id}/1"
    elif pid.isdigit() and not pid.startswith("-"):
        chat_link = f"tg://user?id={pid}"
    elif not pid.startswith("-") and not pid.isdigit() and not pid.isnumeric():
        chat_link = f"https://t.me/{pid.replace('@', '')}"
        
    text = (
        "<blockquote expandable>"
        f"⚠️ <b>[Invalid Peer Detected]</b>\n\n"
        f"• <b>Account:</b> {acc_name} (<code>{user_id}</code>)\n"
        f"• <b>Chat:</b> {chat_title} (<code>{peer_id}</code>)\n"
        f"• <b>Context:</b> <code>resolve_peer</code>\n\n"
        f"💡 This account doesn't recognize the Chat ID above. If the account has been kicked or is no longer relevant, you can order it to leave (Leave Chat)."
        "</blockquote>"
    )
    
    user_style = get_user_button_style(user_id)
    buttons = []
    if chat_link:
        buttons.append(InlineKeyboardButton("🔗 Open Chat", url=chat_link))
    buttons.append(InlineKeyboardButton("🗑 Leave Chat", callback_data=f"p_leave_req_{user_id}_{peer_id}"))
    
    for btn in buttons:
        btn.style = user_style
        
    kb = InlineKeyboardMarkup([buttons])
    await cb.edit_message_text(text, reply_markup=kb)
