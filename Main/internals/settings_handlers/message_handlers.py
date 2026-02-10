# Main/internals/settings_handlers/message_handlers.py
import html
import os
import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from Main.core.decorators import log_errors, iuser_check
from Main.core.client import Altruix
from pyrogram.enums import ParseMode, ChatType
from pyrogram.errors import FloodWait

# States & Utils
from .states import user_purge_state, user_recent_messages_state
from .utils import send_log_notification
# from .session_info import sessions_info_cb_handler

# Logger
logger = logging.getLogger(__name__)

@Altruix.bot.on_callback_query(filters.regex(r"purge_msg_start_(\d+)_(\d+)"))
@iuser_check
@log_errors
async def purge_msg_start_handler(c: Client, cb: CallbackQuery):
    """Start purge session message process"""
    await cb.answer()
    index, page = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    user_id = cb.from_user.id
    
    user_purge_state[user_id] = {'session_index': index, 'page': page, 'step': 'waiting_chat'}
    
    await cb.message.edit(
        text="<b>🧹 Purge My Message</b>\n\n"
             "Menghapus pesan Anda sendiri di chat tertentu.\n"
             "Silakan kirim <b>Username</b> atau <b>ID</b> target chat.\n\n"
             "❌ <b>Cancel:</b> /cancel",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}")]]),
        parse_mode=ParseMode.HTML
    )

@Altruix.bot.on_callback_query(filters.regex(r"rpm_conf_(\d+)_(-?\d+)_(\d+)"))
@iuser_check
@log_errors
async def rpm_conf_handler(c: Client, cb: CallbackQuery):
    """Confirmation for replying to a PM mention"""
    await cb.answer()
    index, chat_id, msg_id = int(cb.matches[0].group(1)), int(cb.matches[0].group(2)), int(cb.matches[0].group(3))
    
    buttons = [
        [
            InlineKeyboardButton("✅ Yes, Reply", f"rpm_exec_{index}_{chat_id}_{msg_id}"),
            InlineKeyboardButton("❌ No", f"session_info_{index}_1")
        ]
    ]
    await cb.message.edit(
        "<b>❓ Konfirmasi Reply PM</b>\n\n"
        "Kirim balasan otomatis ke pengirim mention melalui PM?",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )

@Altruix.bot.on_callback_query(filters.regex(r"rpm_exec_(\d+)_(-?\d+)_(\d+)"))
@iuser_check
@log_errors
async def rpm_exec_handler(c: Client, cb: CallbackQuery):
    """Execute PM reply for mention"""
    index, chat_id, msg_id = int(cb.matches[0].group(1)), int(cb.matches[0].group(2)), int(cb.matches[0].group(3))
    await cb.answer("⏳ Memproses balas pesan...", show_alert=False)
    
    if index >= len(Altruix.clients): return
    client = Altruix.clients[index]
    try:
        msg = await client.get_messages(chat_id, msg_id)
        if msg and msg.from_user:
            await client.send_message(msg.from_user.id, "Halo, ada yang bisa saya bantu? (Auto-reply via Mention Logger)")
            await cb.answer("✅ Berhasil membalas via PM.", show_alert=True)
        else: await cb.answer("❌ Pesan tidak ditemukan.", show_alert=True)
    except Exception as e: await cb.answer(f"❌ Error: {e}", show_alert=True)
    from .session_info import sessions_info_cb_handler
    await sessions_info_cb_handler(c, cb, index=index, callback_page=1)

# Note: Complex multi-step purge handlers (amt, del, mode, exec) are usually triggered via on_message logic
# which we'll implement in session_info.py or a dedicated module.
@Altruix.bot.on_callback_query(filters.regex(r"^gen_conf_join_chat_input_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def join_chat_input_handler(c: Client, cb: CallbackQuery):
    """Start join chat process"""
    index, page = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    await cb.answer()
    from .states import user_join_state
    user_join_state[cb.from_user.id] = {'session_index': index, 'page': page, 'step': 'waiting_link'}
    await cb.message.edit(
        "<b>➕ Join Chat</b>\n\n"
        "Silakan kirim <b>Invite Link</b> atau <b>Username</b> grup/channel yang ingin dimasuki.\n\n"
        "❌ <b>Cancel:</b> /cancel",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}")]])
    )

@Altruix.bot.on_callback_query(filters.regex(r"^gen_conf_leave_chat_input_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def leave_chat_input_handler(c: Client, cb: CallbackQuery):
    """Start leave chat process"""
    index, page = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    await cb.answer()
    from .states import user_leave_state
    user_leave_state[cb.from_user.id] = {'session_index': index, 'page': page, 'step': 'waiting_chat'}
    await cb.message.edit(
        "<b>➖ Leave Chat</b>\n\n"
        "Silakan kirim <b>Username</b> atau <b>ID</b> grup/channel yang ingin ditinggalkan.\n\n"
        "❌ <b>Cancel:</b> /cancel",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}")]])
    )

@Altruix.bot.on_callback_query(filters.regex(r"^gen_conf_send_message_input_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def send_message_input_handler(c: Client, cb: CallbackQuery):
    """Start send message process"""
    index, page = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    await cb.answer()
    from .states import user_send_msg_state
    user_send_msg_state[cb.from_user.id] = {'session_index': index, 'page': page, 'step': 'waiting_target'}
    await cb.message.edit(
        "<b>💬 Send Message</b>\n\n"
        "Silakan kirim <b>Target (Username/ID)</b> tujuan pengiriman pesan.\n\n"
        "❌ <b>Cancel:</b> /cancel",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}")]])
    )
async def process_join_chat(c: Client, m: Message, state: dict):
    """Process join chat input"""
    user_id = m.from_user.id
    index, page = state['session_index'], state['page']
    link = m.text.strip()
    
    await m.reply(f"⏳ <b>Joining...</b>\nTarget: <code>{html.escape(link)}</code>", parse_mode=ParseMode.HTML)
    session_client = Altruix.clients[index]
    try:
        await session_client.join_chat(link)
        await m.reply("✅ <b>Success!</b> Successfully joined chat.")
        await send_log_notification(c, 'join_chat', index, m.from_user, True, additional_info={'Target': link})
    except Exception as e:
        await m.reply(f"❌ <b>Failed:</b> {str(e)}")
        await send_log_notification(c, 'join_chat', index, m.from_user, False, str(e))
    
    from .states import user_join_state
    if user_id in user_join_state: del user_join_state[user_id]
    await asyncio.sleep(2)
    await m.reply("🔄 Memuat ulang menu...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Dashboard", f"session_info_{index}_{page}")]]))

async def process_leave_chat(c: Client, m: Message, state: dict):
    """Process leave chat input"""
    user_id = m.from_user.id
    index, page = state['session_index'], state['page']
    target = m.text.strip()
    
    await m.reply(f"⏳ <b>Leaving...</b>\nTarget: <code>{html.escape(target)}</code>", parse_mode=ParseMode.HTML)
    session_client = Altruix.clients[index]
    try:
        await session_client.leave_chat(target)
        await m.reply("✅ <b>Success!</b> Successfully left chat.")
        await send_log_notification(c, 'leave_chat', index, m.from_user, True, additional_info={'Target': target})
    except Exception as e:
        await m.reply(f"❌ <b>Failed:</b> {str(e)}")
        await send_log_notification(c, 'leave_chat', index, m.from_user, False, str(e))
    
    from .states import user_leave_state
    if user_id in user_leave_state: del user_leave_state[user_id]
    await asyncio.sleep(2)
    await m.reply("🔄 Memuat ulang menu...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Dashboard", f"session_info_{index}_{page}")]]))

async def process_send_message(c: Client, m: Message, state: dict):
    """Process send message target input and move to step 2 (message content)"""
    user_id = m.from_user.id
    index, page = state['session_index'], state['page']
    target = m.text.strip()
    
    from .states import user_send_msg_state
    user_send_msg_state[user_id].update({'target': target, 'step': 'waiting_content'})
    await m.reply(f"🎯 <b>Target set:</b> <code>{html.escape(target)}</code>\n\nSilakan kirim pesan yang ingin dikirim.\n\n❌ <b>Cancel:</b> /cancel", parse_mode=ParseMode.HTML)

async def process_send_message_content(c: Client, m: Message, state: dict):
    """Process actual message sending"""
    user_id = m.from_user.id
    index, page, target = state['session_index'], state['page'], state['target']
    content = m.text
    
    await m.reply(f"⏳ <b>Sending message to...</b>\nTarget: <code>{html.escape(target)}</code>", parse_mode=ParseMode.HTML)
    session_client = Altruix.clients[index]
    try:
        await session_client.send_message(target, content)
        await m.reply("✅ <b>Success!</b> Message sent.")
        await send_log_notification(c, 'send_message', index, m.from_user, True, additional_info={'Target': target})
    except Exception as e:
        await m.reply(f"❌ <b>Failed:</b> {str(e)}")
        await send_log_notification(c, 'send_message', index, m.from_user, False, str(e))
    
    from .states import user_send_msg_state
    if user_id in user_send_msg_state: del user_send_msg_state[user_id]
    await asyncio.sleep(2)
    await m.reply("🔄 Memuat ulang menu...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Dashboard", f"session_info_{index}_{page}")]]))
