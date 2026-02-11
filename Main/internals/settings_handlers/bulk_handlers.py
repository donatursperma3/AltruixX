# Main/internals/settings_handlers/bulk_handlers.py
import html
import os
import asyncio
import logging
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton, LinkPreviewOptions
from pyrogram.enums import ParseMode
from pyrogram.errors import (
    FloodWait, InviteHashInvalid, InviteHashExpired, UserAlreadyParticipant,
    ChatAdminRequired, UsernameNotOccupied, ChannelPrivate, UsernameInvalid
)

from Main.core.decorators import log_errors, iuser_check
from Main.core.client import Altruix

# Utils & States
from .utils import edit_cb, check_authorization, send_log_notification, gt
from .states import user_bulk_join_state, user_bulk_leave_state, user_bulk_report_state

# Logger
logger = logging.getLogger(__name__)

# ====================== BULK JOIN FEATURE ======================
@Altruix.bot.on_callback_query(filters.regex("bulk_join_menu"))
@iuser_check
@log_errors
async def bulk_join_menu_handler(c: Client, cb: CallbackQuery):
    """Handler untuk menu bulk join"""
    if not await check_authorization(cb): return
    await cb.answer()
    
    # Tampilkan pilihan delay
    delay_buttons = [
        [
            InlineKeyboardButton("2 detik", callback_data="bulk_join_delay_2"),
            InlineKeyboardButton("4 detik", callback_data="bulk_join_delay_4"),
            InlineKeyboardButton("6 detik", callback_data="bulk_join_delay_6"),
        ],
        [
            InlineKeyboardButton("8 detik", callback_data="bulk_join_delay_8"),
            InlineKeyboardButton("10 detik", callback_data="bulk_join_delay_10"),
            InlineKeyboardButton("15 detik", callback_data="bulk_join_delay_15"),
        ],
        [
            InlineKeyboardButton("20 detik", callback_data="bulk_join_delay_20"),
            InlineKeyboardButton("30 detik", callback_data="bulk_join_delay_30"),
            InlineKeyboardButton("60 detik", callback_data="bulk_join_delay_60"),
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="sessions_list_1"),
        ]
    ]
    
    await edit_cb(cb, 
        text="<b>👥 Bulk Join Settings</b>\n\n"
             "Pilih jeda waktu antara join (untuk menghindari flood wait):\n\n"
             "⚠️ <b>Note:</b>\n"
             "• Delay yang lebih besar mengurangi risiko flood wait\n"
             "• Delay yang lebih kecil lebih cepat tapi berisiko",
        reply_markup=InlineKeyboardMarkup(delay_buttons)
    )

@Altruix.bot.on_callback_query(filters.regex("bulk_join_delay_(\\d+)"))
@iuser_check
@log_errors
async def bulk_join_delay_handler(c: Client, cb: CallbackQuery):
    """Handler untuk memilih delay bulk join"""
    if not await check_authorization(cb): return
    await cb.answer()
    
    try:
        delay = int(cb.matches[0].group(1))
    except (ValueError, IndexError):
        delay = 5
    
    user_id = cb.from_user.id
    user_bulk_join_state[user_id] = {
        'delay': delay,
        'link': None,
        'step': 'waiting_link'
    }
    
    await edit_cb(cb, 
        text=f"<b>👥 Bulk Join - Delay {delay} detik</b>\n\n"
             "Silakan kirim link grup yang akan di-join:\n\n"
             "🔗 <b>Format Link:</b>\n"
             "• https://t.me/username (public group/channel)\n"
             "• https://t.me/+invitehash (private group)\n"
             "• @username (tanpa https://)\n\n"
             "❌ <b>Cancel:</b> Ketik /cancel",
        parse_mode=ParseMode.HTML
    )

@Altruix.bot.on_callback_query(filters.regex("bulk_join_confirm_(yes|no)"))
@iuser_check
@log_errors
async def bulk_join_confirm_handler(c: Client, cb: CallbackQuery):
    """Handler untuk konfirmasi bulk join"""
    if not await check_authorization(cb): return
    await cb.answer()
    choice = cb.matches[0].group(1)
    user_id = cb.from_user.id
    
    if choice == "no":
        if user_id in user_bulk_join_state:
            del user_bulk_join_state[user_id]
        await edit_cb(cb, "❌ Bulk join dibatalkan.", 
                             reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="sessions_list_1")]]))
        return
    
    if user_id not in user_bulk_join_state:
        await edit_cb(cb, "❌ Data tidak ditemukan. Silakan ulangi.")
        return
    
    state = user_bulk_join_state[user_id]
    delay, link = state['delay'], state['link']
    del user_bulk_join_state[user_id]
    
    await execute_bulk_join(c, cb, delay, link)

async def execute_bulk_join(c: Client, cb: CallbackQuery, delay: int, link: str):
    """Esekusi bulk join"""
    user = cb.from_user
    total_sessions = len(Altruix.clients)
    if total_sessions == 0:
        await edit_cb(cb, "❌ No sessions available.")
        return
    
    await edit_cb(cb, f"🔄 Starting bulk join for <b>{total_sessions}</b> sessions...\nDelay: {delay}s\nLink: {link}")
    
    success_count, failed_count = 0, 0
    
    for index, client in enumerate(Altruix.clients):
        try:
            await client.join_chat(link)
            success_count += 1
        except UserAlreadyParticipant:
            success_count += 1
        except Exception as e:
            failed_count += 1
        
        await edit_cb(cb, f"🔄 Progress: {index+1}/{total_sessions}\nSuccess: {success_count}\nFailed: {failed_count}")
        if index < total_sessions - 1:
            await asyncio.sleep(delay)
            
    await edit_cb(cb, f"✅ <b>Bulk Join Completed</b>\nSuccess: {success_count}\nFailed: {failed_count}",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="sessions_list_1")]]))
    
    await send_log_notification(c, 'bulk_join', 0, user, True, additional_info={'Link': link, 'Success': success_count, 'Failed': failed_count})

# ====================== BULK LEAVE FEATURE ======================
@Altruix.bot.on_callback_query(filters.regex("bulk_leave_menu"))
@iuser_check
@log_errors
async def bulk_leave_menu_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer()
    
    delay_buttons = [
        [InlineKeyboardButton(f"{d} detik", callback_data=f"bulk_leave_delay_{d}") for d in [2, 4, 6]],
        [InlineKeyboardButton(f"{d} detik", callback_data=f"bulk_leave_delay_{d}") for d in [8, 10, 15]],
        [InlineKeyboardButton("🔙 Back", callback_data="sessions_list_1")]
    ]
    
    await edit_cb(cb, text="<b>🏃 Bulk Leave Settings</b>\nPilih jeda waktu antara keluar dari chat:", 
                        reply_markup=InlineKeyboardMarkup(delay_buttons))

@Altruix.bot.on_callback_query(filters.regex("bulk_leave_delay_(\\d+)"))
@iuser_check
@log_errors
async def bulk_leave_delay_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer()
    delay = int(cb.matches[0].group(1))
    user_bulk_leave_state[cb.from_user.id] = {'delay': delay, 'chat_id': None, 'step': 'waiting_chat'}
    await edit_cb(cb, text=f"<b>🏃 Bulk Leave - Delay {delay}s</b>\nKirim Chat ID/Username target:\n/cancel untuk batal")

@Altruix.bot.on_callback_query(filters.regex("bulk_leave_confirm_(yes|no)"))
@iuser_check
@log_errors
async def bulk_leave_confirm_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer()
    choice, user_id = cb.matches[0].group(1), cb.from_user.id
    if choice == "no":
        if user_id in user_bulk_leave_state: del user_bulk_leave_state[user_id]
        await edit_cb(cb, "❌ Batal.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="sessions_list_1")]]))
        return
    if user_id not in user_bulk_leave_state: return
    state = user_bulk_leave_state[user_id]
    del user_bulk_leave_state[user_id]
    await execute_bulk_leave(c, cb, state['delay'], state['chat_id'])

async def execute_bulk_leave(c: Client, cb: CallbackQuery, delay: int, chat_id: str):
    total, success, failed = len(Altruix.clients), 0, 0
    await edit_cb(cb, f"🔄 Leaving {chat_id}...")
    for i, client in enumerate(Altruix.clients):
        try:
            await client.leave_chat(chat_id)
            success += 1
        except: failed += 1
        if i < total - 1: await asyncio.sleep(delay)
    await edit_cb(cb, f"✅ Done\nSuccess: {success}\nFailed: {failed}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="sessions_list_1")]]))

# ====================== BULK REPORT FEATURE ======================
@Altruix.bot.on_callback_query(filters.regex("bulk_report_menu"))
@iuser_check
@log_errors
async def bulk_report_menu_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer()
    delay_buttons = [
        [InlineKeyboardButton(f"{d} detik", callback_data=f"bulk_report_delay_{d}") for d in [2, 4, 6]],
        [InlineKeyboardButton(f"{d} detik", callback_data=f"bulk_report_delay_{d}") for d in [8, 10, 15]],
        [InlineKeyboardButton("🔙 Back", callback_data="sessions_list_1")]
    ]
    await edit_cb(cb, text="<b>🚩 Bulk Report Settings</b>\nPilih jeda waktu antar report:", 
                        reply_markup=InlineKeyboardMarkup(delay_buttons))

@Altruix.bot.on_callback_query(filters.regex("bulk_report_delay_(\\d+)"))
@iuser_check
@log_errors
async def bulk_report_delay_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer()
    delay = int(cb.matches[0].group(1))
    user_bulk_report_state[cb.from_user.id] = {'delay': delay, 'target': None, 'step': 'waiting_target'}
    await edit_cb(cb, text=f"<b>🚩 Bulk Report - Delay {delay}s</b>\nKirim Target ID/Username:\n/cancel untuk batal")

@Altruix.bot.on_callback_query(filters.regex("bulk_report_reason_(\\d+)_(.*)"))
@iuser_check
@log_errors
async def bulk_report_reason_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer()
    user_id, reason = int(cb.matches[0].group(1)), cb.matches[0].group(2)
    if user_id not in user_bulk_report_state: return
    user_bulk_report_state[user_id].update({'reason': reason, 'step': 'confirming'})
    target, delay = user_bulk_report_state[user_id]['target'], user_bulk_report_state[user_id]['delay']
    
    await edit_cb(cb, text=f"<b>🚩 Confirm Bulk Report</b>\nTarget: {target}\nReason: {reason.upper()}\nDelay: {delay}s",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("✅ Yes", callback_data="bulk_report_confirm_yes"),
                             InlineKeyboardButton("❌ No", callback_data="bulk_report_confirm_no")]
                        ]))

@Altruix.bot.on_callback_query(filters.regex("bulk_report_confirm_(yes|no)"))
@iuser_check
@log_errors
async def bulk_report_confirm_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer()
    choice, user_id = cb.matches[0].group(1), cb.from_user.id
    if choice == "no":
        if user_id in user_bulk_report_state: del user_bulk_report_state[user_id]
        await edit_cb(cb, "❌ Batal.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="sessions_list_1")]]))
        return
    if user_id not in user_bulk_report_state: return
    state = user_bulk_report_state[user_id]
    del user_bulk_report_state[user_id]
    await execute_bulk_report(c, cb, state['delay'], state['target'], state['reason'])

async def execute_bulk_report(c: Client, cb: CallbackQuery, delay: int, target: str, reason: str):
    total, success, failed = len(Altruix.clients), 0, 0
    await edit_cb(cb, f"🔄 Reporting {target}...")
    for i, client in enumerate(Altruix.clients):
        try:
            await client.report_peer(target, reason)
            success += 1
        except: failed += 1
        if i < total - 1: await asyncio.sleep(delay)
    await edit_cb(cb, f"✅ Done\nSuccess: {success}\nFailed: {failed}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="sessions_list_1")]]))

# ====================== INPUT PROCESSING HANDLERS ======================

async def process_bulk_join_input(c: Client, m: Message, state: dict):
    """Process target link for bulk join"""
    link = m.text.strip()
    if not link.startswith(("http", "@")):
        await m.reply("❌ Format link tidak valid! Gunakan https://t.me/ atau @username.")
        return
    
    state['link'] = link
    state['step'] = 'confirming'
    
    buttons = [
        [
            InlineKeyboardButton("✅ Yes, Join All", callback_data="bulk_join_confirm_yes"),
            InlineKeyboardButton("❌ No, Cancel", callback_data="bulk_join_confirm_no")
        ]
    ]
    await m.reply(
        f"<b>👥 Confirm Bulk Join</b>\n\n• Delay: {state['delay']}s\n• Target: {link}\n\nLanjutkan join ke semua session?",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )

async def process_bulk_leave_input(c: Client, m: Message, state: dict):
    """Process target chat for bulk leave"""
    chat_id = m.text.strip()
    state['chat_id'] = chat_id
    state['step'] = 'confirming'
    
    buttons = [
        [
            InlineKeyboardButton("✅ Yes, Leave All", callback_data="bulk_leave_confirm_yes"),
            InlineKeyboardButton("❌ No, Cancel", callback_data="bulk_leave_confirm_no")
        ]
    ]
    await m.reply(
        f"<b>🏃 Confirm Bulk Leave</b>\n\n• Delay: {state['delay']}s\n• Target: {chat_id}\n\nKeluar dari chat ini di semua session?",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )

async def process_bulk_report_input(c: Client, m: Message, state: dict):
    """Process target for bulk report and show reason selection"""
    user_id = m.from_user.id
    target = m.text.strip()
    state['target'] = target
    state['step'] = 'selecting_reason'
    
    reasons = ["spam", "violence", "pornography", "child_abuse", "other"]
    buttons = []
    for i in range(0, len(reasons), 2):
        row = [InlineKeyboardButton(reasons[i].upper(), callback_data=f"bulk_report_reason_{user_id}_{reasons[i]}")]
        if i+1 < len(reasons):
            row.append(InlineKeyboardButton(reasons[i+1].upper(), callback_data=f"bulk_report_reason_{user_id}_{reasons[i+1]}"))
        buttons.append(row)
    buttons.append([InlineKeyboardButton("✍️ Custom Reason", callback_data=f"bulk_report_reason_{user_id}_custom")])
    
    await m.reply(
        f"<b>🚩 Bulk Report</b>\nTarget: {target}\n\nPilih alasan report:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )

# ====================== GCAST USER FEATURE ======================
@Altruix.bot.on_callback_query(filters.regex(r"^gcast_user_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def gcast_user_handler(c: Client, cb: CallbackQuery):
    """Handler for Global Broadcast to Users"""
    if not await check_authorization(cb): return
    await cb.answer()
    
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    
    # Store state
    user_id = cb.from_user.id
    from .states import user_privacy_state
    
    user_privacy_state[user_id] = {
        'type': 'gcast_user',
        'index': index,
        'page': page,
        'step': 'waiting_gcast_msg'
    }
    
    await edit_cb(cb, 
        "<b>📢 Global Broadcast (Users)</b>\n\n"
        "Silakan kirim pesan yang ingin dibroadcast ke semua **Private Chat** yang tersimpan di dialogs.\n"
        "⚠️ <b>Warning:</b> Gunakan dengan bijak agar tidak terkena FloodWait/Ban.\n\n"
        "❌ <b>Cancel:</b> Ketik /cancel",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}")]])
    )

async def process_gcast_input(c: Client, m: Message, state: dict):
    """Initiate gcast execution from message input"""
    user_id = m.from_user.id
    index = state['index']
    text = m.text or m.caption
    
    await m.reply("🔄 <b>Starting Broadcast...</b>\n\nProcess started in background.")
    
    # Simple async broadcast
    asyncio.create_task(execute_gcast(c, index, text, m))
    
    from .states import user_privacy_state
    if user_id in user_privacy_state:
        del user_privacy_state[user_id]

async def execute_gcast(c, index, text, m):
    """Logic for broadcasting messages to private dialogs"""
    from pyrogram.enums import ChatType
    try:
        if index >= len(Altruix.clients): return
        client = Altruix.clients[index]
        
        count = 0
        failed = 0
        
        async for dialog in client.get_dialogs():
            if dialog.chat.type == ChatType.PRIVATE:
                try:
                    await client.send_message(dialog.chat.id, text)
                    count += 1
                    await asyncio.sleep(2) # FloodWait prevention
                except:
                    failed += 1
                    
        await m.reply(f"✅ <b>GCAST COMPLETED</b>\n\nSent: {count}\nFailed: {failed}")
    except Exception as e:
        logger.error(f"Error in execute_gcast: {e}")

async def process_gpurgeme_custom(c: Client, m: Message, state: dict):
    """Process custom global purge input"""
    user_id = m.from_user.id
    index = state['session_index']
    text = m.text.strip()
    
    if not text.isdigit():
        await m.reply("❌ Masukkan angka valid.")
        return
        
    limit = int(text)
    await m.reply(f"🗑️ <b>Starting global purge ({limit} msgs)...</b>", parse_mode=ParseMode.HTML)
    
    session_client = Altruix.clients[index]
    try:
        count = 0
        async for dialog in session_client.get_dialogs():
            try:
                my_msgs = []
                async for msg in session_client.get_chat_history(dialog.chat.id, limit=limit):
                    if msg.from_user and msg.from_user.is_self:
                        my_msgs.append(msg.id)
                if my_msgs:
                    await session_client.delete_messages(dialog.chat.id, my_msgs)
                    count += 1
                    await asyncio.sleep(0.5)
            except: continue
        await m.reply(f"✅ <b>Global Purgeme Completed</b>\n\nDeleted from {count} dialogs.")
        await send_log_notification(c, 'gpurgeme_custom', index, m.from_user, True, additional_info={'Limit': limit})
    except Exception as e:
        await m.reply(f"❌ Error: {str(e)}")
        
    from .states import user_privacy_state
    if user_id in user_privacy_state: del user_privacy_state[user_id]
    await asyncio.sleep(2)
    await m.reply("🔄 Kembali ke dashboard...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"session_info_{index}_{state.get('page', 1)}")]]) )
