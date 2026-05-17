# Main/internals/settings_handlers/bulk_handlers.py
import html
import os
import asyncio
import traceback
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
from .states import user_bulk_join_state, user_bulk_leave_state, user_bulk_report_state, user_bulk_append_session_state, user_bulk_append_bot_tokens_state

# Logger
logger = logging.getLogger(__name__)

# Version
BULK_VERSION = "1.0.420H" # ✅ Added TXT list support

# ====================== BULK CONTROLS MENU ======================

@Altruix.bot.on_callback_query(filters.regex(r"^bulk_controls_menu$"))
@iuser_check
@log_errors
async def bulk_controls_menu_handler(c: Client, cb: CallbackQuery):
    """Global Bulk Controls Menu."""
    if not await check_authorization(cb): return
    await cb.answer()
    
    user_id = cb.from_user.id
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(user_id)
    
    text = (
        "<b>🛠️ Bulk Controls Manager</b>\n"
        f"🏷️ <b>Version:</b> <code>{BULK_VERSION}</code>\n\n"
        "Manage multiple sessions or system-wide actions at once:"
    )

    
    buttons = [
        [
            InlineKeyboardButton("👥 Bulk Join", "bulk_join_menu", style=user_style),
            InlineKeyboardButton("🏃 Bulk Leave", "bulk_leave_menu", style=user_style)
        ],
        [
            InlineKeyboardButton("🚩 Bulk Report", "bulk_report_menu", style=user_style),
            InlineKeyboardButton("🏓 Bulk Ping", "test_ping_all_confirmation", style=user_style)
        ],
        [
            InlineKeyboardButton("📤 Export Sessions", "export_all_sessions_confirmation", style=user_style),
            InlineKeyboardButton("➕ Append Session", "bulk_append_session_menu", style=user_style)
        ],
        [
            InlineKeyboardButton("🤖 Export Bot Tokens", "export_all_bot_tokens_confirmation", style=user_style),
            InlineKeyboardButton("➕ Append Bot Tokens", "bulk_append_bot_tokens_menu", style=user_style)
        ],
        [
            InlineKeyboardButton("📲 Export Phones", "export_all_phones_confirmation", style=user_style),
        ],
        [
            InlineKeyboardButton("🔄 Force Restart", "sys_ctrl_restart", style=user_style),
            InlineKeyboardButton("❌ Force Shutdown", "sys_ctrl_shutdown", style=user_style)
        ],
        [
            InlineKeyboardButton("🔙 Back to Settings", "settings_menu", style=user_style)
        ],
    ]
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons))

# ====================== BULK JOIN FEATURE ======================
@Altruix.bot.on_callback_query(filters.regex(r"^bulk_join_menu(?:_(\d+))?$"))
@iuser_check
@log_errors
async def bulk_join_menu_handler(c: Client, cb: CallbackQuery):
    """Handler untuk menu bulk join"""
    if not await check_authorization(cb): return
    from Main.utils.file_helpers import get_user_button_style
    
    index = int(cb.matches[0].group(1)) if (cb.matches and len(cb.matches[0].groups()) >= 1 and cb.matches[0].group(1)) else None
    
    if index is not None and index < len(Altruix.clients):
        client = Altruix.clients[index]
        me = getattr(client, "myself", None) or await client.get_me()
        user_style = get_user_button_style(me.id)
    else:
        user_style = get_user_button_style(cb.from_user.id)
        
    await cb.answer()
    
    # Tampilkan pilihan delay
    back_cb = f"session_info_{index}_1_5" if index is not None else "bulk_controls_menu"
    
    delay_buttons = [
        [
            InlineKeyboardButton("2 detik", callback_data=f"bulk_join_delay_2{'_' + str(index) if index is not None else ''}", style=user_style),
            InlineKeyboardButton("4 detik", callback_data=f"bulk_join_delay_4{'_' + str(index) if index is not None else ''}", style=user_style),
            InlineKeyboardButton("6 detik", callback_data=f"bulk_join_delay_6{'_' + str(index) if index is not None else ''}", style=user_style),
        ],
        [
            InlineKeyboardButton("8 detik", callback_data=f"bulk_join_delay_8{'_' + str(index) if index is not None else ''}", style=user_style),
            InlineKeyboardButton("10 detik", callback_data=f"bulk_join_delay_10{'_' + str(index) if index is not None else ''}", style=user_style),
            InlineKeyboardButton("15 detik", callback_data=f"bulk_join_delay_15{'_' + str(index) if index is not None else ''}", style=user_style),
        ],
        [
            InlineKeyboardButton("20 detik", callback_data=f"bulk_join_delay_20{'_' + str(index) if index is not None else ''}", style=user_style),
            InlineKeyboardButton("30 detik", callback_data=f"bulk_join_delay_30{'_' + str(index) if index is not None else ''}", style=user_style),
            InlineKeyboardButton("60 detik", callback_data=f"bulk_join_delay_60{'_' + str(index) if index is not None else ''}", style=user_style),
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data=back_cb, style=user_style),
        ]
    ]
    
    total_sessions = len(Altruix.clients)
    await edit_cb(cb, 
        text=f"<b>👥 Bulk Join Settings ({total_sessions} Sesi)</b>\n\n"
             "Pilih jeda waktu antara join (untuk menghindari flood wait):\n\n"
             "⚠️ <b>Note:</b>\n"
             "• Delay yang lebih besar mengurangi risiko flood wait\n"
             "• Delay yang lebih kecil lebih cepat tapi berisiko",
        reply_markup=InlineKeyboardMarkup(delay_buttons)
    )

@Altruix.bot.on_callback_query(filters.regex(r"^bulk_join_delay_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def bulk_join_delay_handler(c: Client, cb: CallbackQuery):
    """Handler untuk memilih delay bulk join"""
    if not await check_authorization(cb): return
    await cb.answer()
    
    try:
        delay = int(cb.matches[0].group(1))
        index = int(cb.matches[0].group(2)) if cb.matches[0].group(2) else None
    except (ValueError, IndexError):
        delay = 5
        index = None
    
    user_id = cb.from_user.id
    user_bulk_join_state[user_id] = {
        'delay': delay,
        'link': None,
        'step': 'waiting_link',
        'session_index': index
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

@Altruix.bot.on_callback_query(filters.regex(r"^bulk_join_confirm_(yes|no)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def bulk_join_confirm_handler(c: Client, cb: CallbackQuery):
    """Handler untuk konfirmasi bulk join"""
    if not await check_authorization(cb): return
    await cb.answer()
    choice = cb.matches[0].group(1)
    index = int(cb.matches[0].group(2)) if cb.matches[0].group(2) else None
    user_id = cb.from_user.id
    
    if choice == "no":
        if user_id in user_bulk_join_state:
            del user_bulk_join_state[user_id]
        from Main.utils.file_helpers import get_user_button_style
        
        if index is not None and index < len(Altruix.clients):
            user_style = get_user_button_style(Altruix.clients[index].me.id)
        else:
            user_style = get_user_button_style(user_id)
            
        back_cb = f"session_info_{index}_1_5" if index is not None else "bulk_controls_menu"
        await edit_cb(cb, "❌ Bulk join dibatalkan.", 
                             reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=back_cb, style=user_style)]]))
        return
    
    if user_id not in user_bulk_join_state:
        await edit_cb(cb, "❌ Data tidak ditemukan. Silakan ulangi.")
        return
    
    state = user_bulk_join_state[user_id]
    delay, link = state['delay'], state['link']
    index = state.get('session_index')
    del user_bulk_join_state[user_id]
    
    await execute_bulk_join(c, cb, delay, link, index)

async def execute_bulk_join(c: Client, cb: CallbackQuery, delay: int, link: str, index: int = None):
    """Esekusi bulk join"""
    user = cb.from_user
    total_sessions = len(Altruix.clients)
    if total_sessions == 0:
        await edit_cb(cb, "❌ No sessions available.")
        return
    
    await edit_cb(cb, f"🔄 Starting bulk join for <b>{total_sessions}</b> sessions...\nDelay: {delay}s\nLink: {link}")
    
    success_count, failed_count = 0, 0
    
    for i, client in enumerate(Altruix.clients):
        try:
            await client.join_chat(link)
            success_count += 1
        except UserAlreadyParticipant:
            success_count += 1
        except Exception:
            failed_count += 1
        
        await edit_cb(cb, f"🔄 Progress: {i+1}/{total_sessions}\nSuccess: {success_count}\nFailed: {failed_count}")
        if i < total_sessions - 1:
            await asyncio.sleep(delay)
            
    from Main.utils.file_helpers import get_user_button_style
    if index is not None and index < len(Altruix.clients):
        user_style = get_user_button_style(Altruix.clients[index].me.id)
    else:
        user_style = get_user_button_style(user.id)
        
    back_cb = f"session_info_{index}_1_5" if index is not None else "bulk_controls_menu"
    await edit_cb(cb, f"✅ <b>Bulk Join Completed</b>\nSuccess: {success_count}\nFailed: {failed_count}",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=back_cb, style=user_style)]]))
    
    await send_log_notification(c, 'bulk_join', 0, user, True, additional_info={'Link': link, 'Success': success_count, 'Failed': failed_count})

# ====================== BULK LEAVE FEATURE ======================
@Altruix.bot.on_callback_query(filters.regex(r"^bulk_leave_menu(?:_(\d+))?$"))
@iuser_check
@log_errors
async def bulk_leave_menu_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    from Main.utils.file_helpers import get_user_button_style
    
    index = int(cb.matches[0].group(1)) if (cb.matches and len(cb.matches[0].groups()) >= 1 and cb.matches[0].group(1)) else None
    
    if index is not None and index < len(Altruix.clients):
        user_style = get_user_button_style(Altruix.clients[index].me.id)
    else:
        user_style = get_user_button_style(cb.from_user.id)
        
    await cb.answer()
    
    back_cb = f"session_info_{index}_1_5" if index is not None else "bulk_controls_menu"
    
    delay_buttons = [
        [InlineKeyboardButton(f"{d} detik", callback_data=f"bulk_leave_delay_{d}{'_' + str(index) if index is not None else ''}", style=user_style) for d in [2, 4, 6]],
        [InlineKeyboardButton(f"{d} detik", callback_data=f"bulk_leave_delay_{d}{'_' + str(index) if index is not None else ''}", style=user_style) for d in [8, 10, 15]],
        [InlineKeyboardButton("🔙 Back", callback_data=back_cb, style=user_style)]
    ]
    
    await edit_cb(cb, text="<b>🏃 Bulk Leave Settings</b>\nPilih jeda waktu antara keluar dari chat:", 
                        reply_markup=InlineKeyboardMarkup(delay_buttons))

@Altruix.bot.on_callback_query(filters.regex(r"^bulk_leave_delay_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def bulk_leave_delay_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer()
    delay = int(cb.matches[0].group(1))
    index = int(cb.matches[0].group(2)) if cb.matches[0].group(2) else None
    user_bulk_leave_state[cb.from_user.id] = {'delay': delay, 'chat_id': None, 'step': 'waiting_chat', 'session_index': index}
    await edit_cb(cb, text=f"<b>🏃 Bulk Leave - Delay {delay}s</b>\nKirim Chat ID/Username target:\n/cancel untuk batal")

@Altruix.bot.on_callback_query(filters.regex(r"^bulk_leave_confirm_(yes|no)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def bulk_leave_confirm_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer()
    choice = cb.matches[0].group(1)
    index = int(cb.matches[0].group(2)) if cb.matches[0].group(2) else None
    user_id = cb.from_user.id
    
    if choice == "no":
        if user_id in user_bulk_leave_state: del user_bulk_leave_state[user_id]
        from Main.utils.file_helpers import get_user_button_style
        if index is not None and index < len(Altruix.clients):
            user_style = get_user_button_style(Altruix.clients[index].me.id)
        else:
            user_style = get_user_button_style(user_id)
        back_cb = f"session_info_{index}_1_5" if index is not None else "bulk_controls_menu"
        await edit_cb(cb, "❌ Batal.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=back_cb, style=user_style)]]))
        return
    if user_id not in user_bulk_leave_state: return
    state = user_bulk_leave_state[user_id]
    index = state.get('session_index')
    del user_bulk_leave_state[user_id]
    await execute_bulk_leave(c, cb, state['delay'], state['chat_id'], index)

async def execute_bulk_leave(c: Client, cb: CallbackQuery, delay: int, chat_id: str, index: int = None):
    total, success, failed = len(Altruix.clients), 0, 0
    await edit_cb(cb, f"🔄 Leaving {chat_id}...")
    for i, client in enumerate(Altruix.clients):
        try:
            await client.leave_chat(chat_id)
            success += 1
        except Exception: failed += 1
        if i < total - 1: await asyncio.sleep(delay)
    from Main.utils.file_helpers import get_user_button_style
    if index is not None and index < len(Altruix.clients):
        user_style = get_user_button_style(Altruix.clients[index].me.id)
    else:
        user_style = get_user_button_style(cb.from_user.id)
    back_cb = f"session_info_{index}_1_5" if index is not None else "bulk_controls_menu"
    await edit_cb(cb, f"✅ Done\nSuccess: {success}\nFailed: {failed}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=back_cb, style=user_style)]]))

# ====================== BULK REPORT FEATURE ======================
@Altruix.bot.on_callback_query(filters.regex(r"^bulk_report_menu(?:_(\d+))?$"))
@iuser_check
@log_errors
async def bulk_report_menu_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    from Main.utils.file_helpers import get_user_button_style
    
    index = int(cb.matches[0].group(1)) if (cb.matches and len(cb.matches[0].groups()) >= 1 and cb.matches[0].group(1)) else None
    
    if index is not None and index < len(Altruix.clients):
        user_style = get_user_button_style(Altruix.clients[index].me.id)
    else:
        user_style = get_user_button_style(cb.from_user.id)
        
    await cb.answer()
    
    back_cb = f"session_info_{index}_1_5" if index is not None else "bulk_controls_menu"
    
    delay_buttons = [
        [InlineKeyboardButton(f"{d} detik", callback_data=f"bulk_report_delay_{d}{'_' + str(index) if index is not None else ''}", style=user_style) for d in [2, 4, 6]],
        [InlineKeyboardButton(f"{d} detik", callback_data=f"bulk_report_delay_{d}{'_' + str(index) if index is not None else ''}", style=user_style) for d in [8, 10, 15]],
        [InlineKeyboardButton("🔙 Back", callback_data=back_cb, style=user_style)]
    ]
    await edit_cb(cb, text="<b>🚩 Bulk Report Settings</b>\nPilih jeda waktu antar report:", 
                        reply_markup=InlineKeyboardMarkup(delay_buttons))

@Altruix.bot.on_callback_query(filters.regex(r"^bulk_report_delay_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def bulk_report_delay_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer()
    delay = int(cb.matches[0].group(1))
    index = int(cb.matches[0].group(2)) if cb.matches[0].group(2) else None
    user_bulk_report_state[cb.from_user.id] = {'delay': delay, 'target': None, 'step': 'waiting_target', 'session_index': index}
    await edit_cb(cb, text=f"<b>🚩 Bulk Report - Delay {delay}s</b>\nKirim Target ID/Username:\n/cancel untuk batal")

@Altruix.bot.on_callback_query(filters.regex(r"^bulk_report_reason_(\d+)_([^_]+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def bulk_report_reason_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer()
    user_id, reason = int(cb.matches[0].group(1)), cb.matches[0].group(2)
    index = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else None
    
    if user_id not in user_bulk_report_state: return
    user_bulk_report_state[user_id].update({'reason': reason, 'step': 'confirming'})
    target, delay = user_bulk_report_state[user_id]['target'], user_bulk_report_state[user_id]['delay']
    
    from Main.utils.file_helpers import get_user_button_style
    if index is not None and index < len(Altruix.clients):
        user_style = get_user_button_style(Altruix.clients[index].me.id)
    else:
        user_style = get_user_button_style(cb.from_user.id)
    
    await edit_cb(cb, text=f"<b>🚩 Confirm Bulk Report</b>\nTarget: {target}\nReason: {reason.upper()}\nDelay: {delay}s",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("✅ Yes", callback_data=f"bulk_report_confirm_yes{'_' + str(index) if index is not None else ''}", style=user_style),
                             InlineKeyboardButton("❌ No", callback_data=f"bulk_report_confirm_no{'_' + str(index) if index is not None else ''}", style=user_style)]
                        ]))

@Altruix.bot.on_callback_query(filters.regex(r"^bulk_report_confirm_(yes|no)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def bulk_report_confirm_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer()
    choice = cb.matches[0].group(1)
    index = int(cb.matches[0].group(2)) if cb.matches[0].group(2) else None
    user_id = cb.from_user.id
    
    if choice == "no":
        if user_id in user_bulk_report_state: del user_bulk_report_state[user_id]
        from Main.utils.file_helpers import get_user_button_style
        if index is not None and index < len(Altruix.clients):
            user_style = get_user_button_style(Altruix.clients[index].me.id)
        else:
            user_style = get_user_button_style(user_id)
        back_cb = f"session_info_{index}_1_5" if index is not None else "bulk_controls_menu"
        await edit_cb(cb, "❌ Batal.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=back_cb, style=user_style)]]))
        return
    if user_id not in user_bulk_report_state: return
    state = user_bulk_report_state[user_id]
    index = state.get('session_index')
    del user_bulk_report_state[user_id]
    await execute_bulk_report(c, cb, state['delay'], state['target'], state['reason'], index)

async def execute_bulk_report(c: Client, cb: CallbackQuery, delay: int, target: str, reason: str, index: int = None):
    total, success, failed = len(Altruix.clients), 0, 0
    await edit_cb(cb, f"🔄 Reporting {target}...")
    for i, client in enumerate(Altruix.clients):
        try:
            await client.report_peer(target, reason)
            success += 1
        except Exception: failed += 1
        if i < total - 1: await asyncio.sleep(delay)
    from Main.utils.file_helpers import get_user_button_style
    if index is not None and index < len(Altruix.clients):
        user_style = get_user_button_style(Altruix.clients[index].me.id)
    else:
        user_style = get_user_button_style(cb.from_user.id)
    back_cb = f"session_info_{index}_1_5" if index is not None else "bulk_controls_menu"
    await edit_cb(cb, f"✅ Done\nSuccess: {success}\nFailed: {failed}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=back_cb, style=user_style)]]))

# ====================== INPUT PROCESSING HANDLERS ======================

async def process_bulk_join_input(c: Client, m: Message, state: dict):
    """Process target link for bulk join"""
    link = m.text.strip()
    if not link.startswith(("http", "@")):
        await m.reply("❌ Format link tidak valid! Gunakan https://t.me/ atau @username.")
        return
    
    state['link'] = link
    state['step'] = 'confirming'
    index = state.get('session_index')
    
    from Main.utils.file_helpers import get_user_button_style
    if index is not None and index < len(Altruix.clients):
        user_style = get_user_button_style(Altruix.clients[index].me.id)
    else:
        user_style = get_user_button_style(m.from_user.id)
        
    idx_str = f"_{index}" if index is not None else ""
    buttons = [
        [
            InlineKeyboardButton("✅ Yes, Join All", callback_data=f"bulk_join_confirm_yes{idx_str}", style=user_style),
            InlineKeyboardButton("❌ No, Cancel", callback_data=f"bulk_join_confirm_no{idx_str}", style=user_style)
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
    index = state.get('session_index')
    
    from Main.utils.file_helpers import get_user_button_style
    if index is not None and index < len(Altruix.clients):
        user_style = get_user_button_style(Altruix.clients[index].me.id)
    else:
        user_style = get_user_button_style(m.from_user.id)
        
    idx_str = f"_{index}" if index is not None else ""
    buttons = [
        [
            InlineKeyboardButton("✅ Yes, Leave All", callback_data=f"bulk_leave_confirm_yes{idx_str}", style=user_style),
            InlineKeyboardButton("❌ No, Cancel", callback_data=f"bulk_leave_confirm_no{idx_str}", style=user_style)
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
    index = state.get('session_index')
    
    reasons = ["spam", "violence", "pornography", "child_abuse", "other"]
    buttons = []
    from Main.utils.file_helpers import get_user_button_style
    if index is not None and index < len(Altruix.clients):
        user_style = get_user_button_style(Altruix.clients[index].me.id)
    else:
        user_style = get_user_button_style(user_id)
        
    idx_str = f"_{index}" if index is not None else ""
    for i in range(0, len(reasons), 2):
        row = [InlineKeyboardButton(reasons[i].upper(), callback_data=f"bulk_report_reason_{user_id}_{reasons[i]}{idx_str}", style=user_style)]
        if i+1 < len(reasons):
            row.append(InlineKeyboardButton(reasons[i+1].upper(), callback_data=f"bulk_report_reason_{user_id}_{reasons[i+1]}{idx_str}", style=user_style))
        buttons.append(row)
    buttons.append([InlineKeyboardButton("✍️ Custom Reason", callback_data=f"bulk_report_reason_{user_id}_custom{idx_str}", style=user_style)])
    
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
    
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(user_id)
    await edit_cb(cb, 
        "<b>📢 Global Broadcast (Users)</b>\n\n"
        "Silakan kirim pesan yang ingin dibroadcast ke semua **Private Chat** yang tersimpan di dialogs.\n"
        "⚠️ <b>Warning:</b> Gunakan dengan bijak agar tidak terkena FloodWait/Ban.\n\n"
        "❌ <b>Cancel:</b> Ketik /cancel",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}", style=user_style)]])
    )

async def process_gcast_input(c: Client, m: Message, state: dict):
    """Store gcast message and show confirmation before executing."""
    user_id = m.from_user.id
    index = state['index']
    page = state.get('page', 1)
    text = m.text or m.caption
    
    if not text:
        await m.reply("❌ <b>Error:</b> Pesan kosong. Silakan kirim ulang.", parse_mode=ParseMode.HTML)
        return

    # Store the message in state for later confirmation
    from .states import user_privacy_state
    user_privacy_state[user_id] = {
        'type': 'gcast_user',
        'index': index,
        'page': page,
        'step': 'confirming_gcast',
        'gcast_text': text
    }
    
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(user_id)
    
    # Preview first 200 chars of the message
    preview = html.escape(text[:200]) + ("..." if len(text) > 200 else "")
    
    confirm_buttons = [
        [
            InlineKeyboardButton("✅ Yes, Broadcast!", callback_data=f"gcast_confirm_yes_{index}_{page}", style=user_style),
            InlineKeyboardButton("❌ No, Cancel", callback_data=f"gcast_confirm_no_{index}_{page}", style=user_style)
        ]
    ]
    
    await m.reply(
        f"<b>⚠️ CONFIRM BROADCAST</b>\n\n"
        f"<b>Session:</b> #{index}\n"
        f"<b>Target:</b> All Private Chats\n\n"
        f"<b>Message Preview:</b>\n<blockquote expandable>{preview}</blockquote>\n\n"
        f"⚠️ <b>Are you absolutely sure you want to broadcast this message to ALL private chats?</b>",
        reply_markup=InlineKeyboardMarkup(confirm_buttons),
        parse_mode=ParseMode.HTML
    )

@Altruix.bot.on_callback_query(filters.regex(r"^gcast_confirm_(yes|no)_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def gcast_confirm_handler(c: Client, cb: CallbackQuery):
    """Handle gcast confirmation — only execute on explicit 'yes'."""
    if not await check_authorization(cb): return
    await cb.answer()
    
    choice = cb.matches[0].group(1)
    index = int(cb.matches[0].group(2))
    page = int(cb.matches[0].group(3))
    user_id = cb.from_user.id
    
    from .states import user_privacy_state
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(user_id)
    
    if choice == "no":
        if user_id in user_privacy_state:
            del user_privacy_state[user_id]
        await edit_cb(cb, "❌ <b>Broadcast dibatalkan.</b>",
                     reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}", style=user_style)]]))
        return
    
    # choice == "yes"
    state = user_privacy_state.get(user_id)
    if not state or state.get('step') != 'confirming_gcast':
        await edit_cb(cb, "❌ <b>Session expired.</b> Silakan ulangi dari awal.",
                     reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}", style=user_style)]]))
        return
    
    gcast_text = state.get('gcast_text', '')
    del user_privacy_state[user_id]
    
    await edit_cb(cb, "🔄 <b>Starting Broadcast...</b>\n\nProcess started in background.")
    asyncio.create_task(execute_gcast(c, index, gcast_text, cb))

async def execute_gcast(c, index, text, source):
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
        
        # Try to notify completion                    
        try:
            if hasattr(source, 'reply'):
                await source.reply(f"✅ <b>GCAST COMPLETED</b>\n\nSent: {count}\nFailed: {failed}", parse_mode=ParseMode.HTML)
            elif hasattr(source, 'edit_message_text'):
                await edit_cb(source, f"✅ <b>GCAST COMPLETED</b>\n\nSent: {count}\nFailed: {failed}")
        except:
            pass
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
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(user_id)
    if user_id in user_privacy_state: del user_privacy_state[user_id]
    await asyncio.sleep(2)
    await m.reply("🔄 Kembali ke dashboard...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"session_info_{index}_{state.get('page', 1)}", style=user_style)]]) )

# ====================== BULK APPEND SESSION FEATURE ======================
@Altruix.bot.on_callback_query(filters.regex(r"^bulk_append_session_menu$"))
@iuser_check
@log_errors
async def bulk_append_session_menu_handler(c: Client, cb: CallbackQuery):
    """Handler untuk menu bulk append session"""
    if not await check_authorization(cb): return
    await cb.answer()
    
    user_id = cb.from_user.id
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(user_id)
    
    text = (
        "<b>➕ Bulk Append Session</b>\n\n"
        "Fitur ini memungkinkan Anda untuk menambahkan banyak sesi sekaligus ke dalam sistem.\n\n"
        "📂 <b>Metode yang Didukung:</b>\n"
        "1. <b>ZIP File:</b> Kirim file ZIP berisi file <code>.session</code>.\n"
        "2. <b>String Session:</b> Kirim satu atau beberapa baris string session.\n\n"
        "⚠️ <b>Note:</b> Sesi yang sudah ada akan diabaikan (duplikasi dicegah otomatis)."
    )
    
    buttons = [
        [InlineKeyboardButton("🚀 Start Appending", callback_data="bulk_append_session_start", style=user_style)],
        [InlineKeyboardButton("🔙 Back", callback_data="bulk_controls_menu", style=user_style)]
    ]
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons))

@Altruix.bot.on_callback_query(filters.regex(r"^bulk_append_session_start$"))
@iuser_check
@log_errors
async def bulk_append_session_start_handler(c: Client, cb: CallbackQuery):
    """Handler untuk memulai proses input append session"""
    if not await check_authorization(cb): return
    await cb.answer()
    
    user_id = cb.from_user.id
    user_bulk_append_session_state[user_id] = {'step': 'waiting_input'}
    
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(user_id)
    
    await edit_cb(cb, 
        text="<b>➕ Bulk Append Session - Ready</b>\n\n"
             "Silakan kirim salah satu dari berikut ini:\n"
             "• File <b>.zip</b> berisi file session\n"
             "• File <b>.txt</b> berisi daftar session string\n"
             "• String session langsung (Pyrogram v2 format)\n\n"
             "❌ <b>Cancel:</b> Klik tombol di bawah atau ketik /cancel",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", "bulk_append_session_cancel", style=user_style)]])
    )



@Altruix.bot.on_callback_query(filters.regex(r"^bulk_append_session_cancel$"))
@iuser_check
@log_errors
async def bulk_append_session_cancel_handler(c: Client, cb: CallbackQuery):
    """Handler untuk membatalkan proses append session melalui tombol"""
    user_id = cb.from_user.id
    if user_id in user_bulk_append_session_state:
        del user_bulk_append_session_state[user_id]
    
    await cb.answer("❌ Input dibatalkan.")
    from .bulk_handlers import bulk_append_session_menu_handler
    await bulk_append_session_menu_handler(c, cb)


async def process_bulk_append_session_input(c: Client, m: Message, state: dict):
    """Memproses input (file atau teks) untuk bulk append session"""
    user_id = m.from_user.id
    
    if m.document:
        file_name = m.document.file_name.lower()
        if not (file_name.endswith(".zip") or file_name.endswith(".txt")):
            await m.reply("❌ <b>Error:</b> Mohon kirim file format <b>.zip</b> atau <b>.txt</b>.")
            return
        
        file_path = await m.download()
        
        if file_name.endswith(".zip"):
            proc_msg = await m.reply("⏳ <b>Memproses file ZIP...</b>", parse_mode=ParseMode.HTML)
            # Logic for ZIP extraction and session adding
            import zipfile
            import shutil
            extract_path = f"Main/cache/append_{user_id}"
            if os.path.exists(extract_path): shutil.rmtree(extract_path)
            os.makedirs(extract_path, exist_ok=True)
            
            try:
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_path)
                
                sessions_found = []
                for root, dirs, files in os.walk(extract_path):
                    for f in files:
                        if f.endswith(".session"):
                            sessions_found.append(os.path.join(root, f))
                
                if not sessions_found:
                    await proc_msg.edit("❌ <b>Error:</b> Tidak ditemukan file <code>.session</code> di dalam ZIP.")
                    return

                await proc_msg.edit(f"✅ Ditemukan <b>{len(sessions_found)}</b> file sesi. Memulai proses append...")
                await execute_bulk_append_sessions(c, m, sessions_found, is_file=True)
                
            except Exception as e:
                await proc_msg.edit(f"❌ <b>Error:</b> {str(e)}")
            finally:
                if os.path.exists(file_path): os.remove(file_path)
                if os.path.exists(extract_path): shutil.rmtree(extract_path)
                if user_id in user_bulk_append_session_state: del user_bulk_append_session_state[user_id]
        
        elif file_name.endswith(".txt"):
            proc_msg = await m.reply("⏳ <b>Membaca file TXT...</b>", parse_mode=ParseMode.HTML)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                
                valid_sessions = []
                
                # Check for Python list format: ['session1', 'session2']
                if content.startswith("[") and content.endswith("]"):
                    import re
                    # Extract everything inside quotes
                    found = re.findall(r"['\"]([^'\"]+)['\"]", content)
                    valid_sessions = [s.strip() for s in found if len(s.strip()) > 50]
                
                # Fallback to newline-separated format if no sessions found via list parsing
                if not valid_sessions:
                    lines = content.split("\n")
                    valid_sessions = [l.strip() for l in lines if len(l.strip()) > 50]
                
                if not valid_sessions:
                    await proc_msg.edit("❌ <b>Error:</b> Tidak ditemukan session string yang valid di dalam file TXT.")
                    return
                
                await proc_msg.edit(f"✅ Ditemukan <b>{len(valid_sessions)}</b> session string. Memulai proses append...")
                await execute_bulk_append_sessions(c, m, valid_sessions, is_file=False)

            except Exception as e:
                await proc_msg.edit(f"❌ <b>Error:</b> {str(e)}")
            finally:
                if os.path.exists(file_path): os.remove(file_path)
                if user_id in user_bulk_append_session_state: del user_bulk_append_session_state[user_id]


    elif m.text:
        text = m.text.strip()
        lines = text.split("\n")
        valid_sessions = [l.strip() for l in lines if len(l.strip()) > 50] # basic length check for Pyrogram strings
        
        if not valid_sessions:
            await m.reply("❌ <b>Error:</b> Tidak ditemukan session string yang valid.")
            return
            
        await m.reply(f"⏳ Memproses <b>{len(valid_sessions)}</b> session string...")
        await execute_bulk_append_sessions(c, m, valid_sessions, is_file=False)
        if user_id in user_bulk_append_session_state: del user_bulk_append_session_state[user_id]
    else:
        await m.reply("❌ Mohon kirim file ZIP atau teks session string.")

async def execute_bulk_append_sessions(c: Client, m: Message, sessions: list, is_file: bool = False):
    """Esekusi penambahan sesi secara massal"""
    success, failed, skipped = 0, 0, 0
    total = len(sessions)
    error_log = []  # Collect per-session reasons
    
    report_msg = await m.reply(f"🔄 Progress: 0/{total}")
    
    for i, sess_data in enumerate(sessions):
        session_label = f"Session #{i+1}"
        try:
            if is_file:
                file_name = os.path.basename(sess_data)
                dest = os.path.join("Main/sessions", file_name)
                if not os.path.exists(dest):
                    shutil.copy(sess_data, dest)
                    success += 1
                else:
                    skipped += 1
                    error_log.append(f"⚠️ {session_label}: File sudah ada ({file_name})")
            else:
                # String based — skip_reload=True to avoid per-session module reload
                sess_preview = f"{sess_data[:15]}...{sess_data[-10:]}" if len(sess_data) > 30 else sess_data
                res = await Altruix.add_session(sess_data, status=None, user=m.from_user, skip_reload=True)
                if res:
                    me = getattr(res, 'myself', None) or getattr(res, 'me', None)
                    name = getattr(me, 'first_name', 'Unknown') if me else 'Unknown'
                    success += 1
                else:
                    skipped += 1
                    error_log.append(f"⚠️ {session_label}: Duplikat (akun sudah aktif)")

        except Exception as e:
            logger.error(f"Failed to append session #{i+1}: {e}")
            failed += 1
            error_reason = str(e)[:120]
            error_log.append(f"❌ {session_label}: {error_reason}")
            
        if (i + 1) % 5 == 0 or (i + 1) == total:
            try: await report_msg.edit(f"🔄 Progress: {i+1}/{total}\n✅ Success: {success}\n⚠️ Skipped: {skipped}\n❌ Failed: {failed}")
            except: pass
            
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(m.from_user.id)

    await report_msg.edit(
        f"🏁 <b>Bulk Append Completed</b>\n\n"
        f"📊 <b>Summary:</b>\n"
        f"• Total: {total}\n"
        f"• Berhasil: {success}\n"
        f"• Dilewati: {skipped}\n"
        f"• Gagal: {failed}\n\n"
        f"<b>Apakah Anda ingin me-restart sistem sekarang agar sesi baru terdeteksi?</b>",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Yes, Restart Now", "sys_ctrl_restart", style=user_style),
                InlineKeyboardButton("❌ No, Later", "bulk_controls_menu", style=user_style)
            ]
        ])
    )

    # Send detailed error/skip log to log group via bot assistant (auto-split)
    if error_log:
        try:
            log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))
            
            # Header for every chunk
            header = (
                f"📋 <b>BULK APPEND SESSION - DETAILED LOG</b>\n"
                f"{'━' * 25}\n"
                f"• Total: <code>{total}</code>\n"
                f"• ✅ Success: <code>{success}</code>\n"
                f"• ⚠️ Skipped: <code>{skipped}</code>\n"
                f"• ❌ Failed: <code>{failed}</code>\n\n"
                f"<b>Detail Reason:</b>\n"
            )
            footer = (
                f"\n• Waktu: <code>{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</code>\n"
                f"{'━' * 25}"
            )
            
            # Split error_log into chunks that fit within 4096 char limit
            MAX_LEN = 3800  # Safe margin (4096 - header/footer/blockquote overhead)
            chunks = []
            current_chunk = []
            current_len = 0
            
            for entry in error_log:
                entry_len = len(entry) + 1  # +1 for newline
                if current_len + entry_len > MAX_LEN and current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = []
                    current_len = 0
                current_chunk.append(entry)
                current_len += entry_len
            
            if current_chunk:
                chunks.append(current_chunk)
            
            # Send each chunk as a separate message
            for idx, chunk in enumerate(chunks):
                chunk_text = "\n".join(chunk)
                part_label = f" (Part {idx+1}/{len(chunks)})" if len(chunks) > 1 else ""
                log_message = (
                    f"<blockquote expandable>"
                    f"{header}"
                    f"{chunk_text}"
                    f"{footer}{part_label}"
                    f"</blockquote>"
                )
                await c.send_message(log_chat_id, log_message, parse_mode=ParseMode.HTML)
                
        except Exception as le:
            logger.error(f"Failed to send bulk append log: {le}")

    
    # Notify logging channel (general notification)
    await send_log_notification(c, 'bulk_append_session', 0, m.from_user, True, additional_info={'Total': total, 'Success': success})


# ====================== BULK APPEND BOT TOKENS FEATURE ======================
def extract_tokens_from_text(content: str):
    try:
        found = []
        lines = content.splitlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("==="):
                continue
            
            # Check colons count
            colon_count = line.count(":")
            if colon_count >= 2:
                # owner:bot_id:token_hash
                parts = line.split(":", 1)
                prefix = parts[0].strip()
                token = parts[1].strip()
            else:
                prefix = None
                token = line
                
            if ":" in token and len(token) >= 20:
                found.append({'prefix': prefix, 'token': token})
        return found
    except Exception as e:
        logger.error(f"Error in extract_tokens_from_text: {e}\n{traceback.format_exc()}")
        return []

async def execute_bulk_append_bot_tokens(c: Client, m: Message, parsed_entries: list):
    try:
        status_msg = await m.reply(f"⏳ <b>Memulai bulk append bot tokens ({len(parsed_entries)} ditemukan)...</b>", parse_mode=ParseMode.HTML)
        
        success = 0
        failed = 0
        errors = []
        
        # We will map each entry to a client
        used_clients = set()
        
        for idx, entry in enumerate(parsed_entries):
            prefix = entry.get('prefix')
            token = entry.get('token')
            
            # Find matching client
            target_client = None
            
            # 1. Try matching by prefix
            if prefix:
                if prefix.isdigit() and int(prefix) <= len(Altruix.clients):
                    client = Altruix.clients[int(prefix) - 1]
                    if client not in used_clients:
                        target_client = client
                else:
                    clean_prefix = prefix.replace("+", "").strip()
                    for client in Altruix.clients:
                        if client in used_clients:
                            continue
                        if not getattr(client, "me", None):
                            try: client.me = await client.get_me()
                            except: pass
                        if getattr(client, "me", None):
                            if str(client.me.id) == prefix or client.me.phone_number == clean_prefix:
                                target_client = client
                                break
                                
            # 2. Match to next available client without a custom bot active and not already used in this bulk run
            if not target_client:
                for client in Altruix.clients:
                    if client in used_clients:
                        continue
                    if not getattr(client, "me", None):
                        try: client.me = await client.get_me()
                        except: pass
                    if getattr(client, "me", None):
                        session_user_id = client.me.id
                        has_bot = False
                        if hasattr(Altruix, 'bot_manager'):
                            if session_user_id in Altruix.bot_manager.custom_bots:
                                has_bot = True
                        if not has_bot:
                            target_client = client
                            break
                            
            if not target_client:
                failed += 1
                errors.append(f"• Token {token[:15]}...: ❌ No matching available session client found.")
                continue
                
            used_clients.add(target_client)
            session_user_id = target_client.me.id
            session_index = Altruix.clients.index(target_client)
            
            try:
                # Start custom bot and save token
                if hasattr(Altruix, 'bot_manager'):
                    started = await Altruix.bot_manager.start_custom_bot(session_user_id, token)
                    if started:
                        await Altruix.bot_manager.save_token(session_user_id, token)
                        success += 1
                    else:
                        failed += 1
                        errors.append(f"• Session {session_index + 1}: ❌ Bot client failed to start (invalid token or connection error).")
                else:
                    failed += 1
                    errors.append(f"• Session {session_index + 1}: ❌ BotManager not initialized.")
            except Exception as e:
                failed += 1
                errors.append(f"• Session {session_index + 1}: ❌ Error: {str(e)[:100]}")
                
        # Format final summary report
        summary_text = (
            "<b>🤖 Bulk Append Bot Tokens Completed</b>\n\n"
            f"• <b>Total:</b> <code>{len(parsed_entries)}</code>\n"
            f"• <b>Success:</b> <code>{success}</code>\n"
            f"• <b>Failed:</b> <code>{failed}</code>\n\n"
        )
        if errors:
            summary_text += "⚠️ <b>Error Details:</b>\n" + "\n".join(errors[:20])
            if len(errors) > 20:
                summary_text += f"\n<i>...dan {len(errors) - 20} error lainnya.</i>"
                
        await status_msg.edit(summary_text, parse_mode=ParseMode.HTML)
        
        # Notify logging channel
        try:
            log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_USERS_ID))
            user_name = html.escape(m.from_user.first_name if m.from_user.first_name else "User")
            user_link = f"<a href='tg://user?id={m.from_user.id}'>{user_name}</a>"
            await Altruix.bot.send_message(
                log_chat_id,
                f"🤖 <b>BULK APPEND BOT TOKENS</b>\n"
                f"• User: {user_link}\n"
                f"• Total: <code>{len(parsed_entries)}</code>\n"
                f"• Success: <code>{success}</code>\n"
                f"• Failed: <code>{failed}</code>",
                parse_mode=ParseMode.HTML
            )
        except Exception as le:
            logger.error(f"Failed to log bulk append bot tokens: {le}")
    except Exception as e:
        logger.error(f"Error in execute_bulk_append_bot_tokens: {e}\n{traceback.format_exc()}")
        try: await m.reply(f"❌ Error during bulk bot token execution: {e}")
        except: pass

@Altruix.bot.on_callback_query(filters.regex(r"^bulk_append_bot_tokens_menu$"))
@iuser_check
@log_errors
async def bulk_append_bot_tokens_menu_handler(c: Client, cb: CallbackQuery):
    """Handler untuk menu bulk append bot tokens"""
    if not await check_authorization(cb): return
    await cb.answer()
    
    try:
        user_id = cb.from_user.id
        from Main.utils.file_helpers import get_user_button_style
        user_style = get_user_button_style(user_id)
        
        text = (
            "<b>🤖 Bulk Append Bot Tokens</b>\n\n"
            "Fitur ini memungkinkan Anda untuk menambahkan banyak Custom Bot Token sekaligus ke dalam sistem.\n\n"
            "📂 <b>Metode yang Didukung:</b>\n"
            "1. <b>ZIP/TXT File:</b> Kirim file ZIP berisi file teks atau file TXT berisi daftar token.\n"
            "2. <b>Teks Langsung:</b> Kirim satu atau beberapa baris token langsung.\n\n"
            "📝 <b>Format Daftar Token:</b>\n"
            "• <code>bot_id:token_hash</code> (Mencari session kosong berikutnya secara otomatis)\n"
            "• <code>session_index:bot_id:token_hash</code> (Menargetkan session index tertentu, e.g. <code>1:123456789:ABC...</code>)\n"
            "• <code>phone:bot_id:token_hash</code> (Menargetkan session dengan nomor HP tertentu, e.g. <code>+628xxx:123456789:ABC...</code>)"
        )
        
        buttons = [
            [InlineKeyboardButton("🚀 Start Appending", callback_data="bulk_append_bot_tokens_start", style=user_style)],
            [InlineKeyboardButton("🔙 Back", callback_data="bulk_controls_menu", style=user_style)]
        ]
        
        await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        logger.error(f"Error in bulk_append_bot_tokens_menu_handler: {e}\n{traceback.format_exc()}")
        try: await cb.answer(f"❌ Error: {str(e)[:100]}", show_alert=True)
        except: pass

@Altruix.bot.on_callback_query(filters.regex(r"^bulk_append_bot_tokens_start$"))
@iuser_check
@log_errors
async def bulk_append_bot_tokens_start_handler(c: Client, cb: CallbackQuery):
    """Handler untuk memulai proses input append bot tokens"""
    if not await check_authorization(cb): return
    await cb.answer()
    
    try:
        user_id = cb.from_user.id
        user_bulk_append_bot_tokens_state[user_id] = {'step': 'waiting_input'}
        
        from Main.utils.file_helpers import get_user_button_style
        user_style = get_user_button_style(user_id)
        
        await edit_cb(cb, 
            text="<b>🤖 Bulk Append Bot Tokens - Ready</b>\n\n"
                 "Silakan kirim salah satu dari berikut ini:\n"
                 "• File <b>.zip</b> berisi file teks token\n"
                 "• File <b>.txt</b> berisi daftar bot token\n"
                 "• Daftar bot token langsung melalui pesan teks\n\n"
                 "❌ <b>Cancel:</b> Klik tombol di bawah atau ketik /cancel",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", "bulk_append_bot_tokens_cancel", style=user_style)]])
        )
    except Exception as e:
        logger.error(f"Error in bulk_append_bot_tokens_start_handler: {e}\n{traceback.format_exc()}")
        try: await cb.answer(f"❌ Error: {str(e)[:100]}", show_alert=True)
        except: pass

@Altruix.bot.on_callback_query(filters.regex(r"^bulk_append_bot_tokens_cancel$"))
@iuser_check
@log_errors
async def bulk_append_bot_tokens_cancel_handler(c: Client, cb: CallbackQuery):
    """Handler untuk membatalkan proses append bot tokens melalui tombol"""
    try:
        user_id = cb.from_user.id
        if user_id in user_bulk_append_bot_tokens_state:
            del user_bulk_append_bot_tokens_state[user_id]
        
        await cb.answer("❌ Input dibatalkan.")
        await bulk_append_bot_tokens_menu_handler(c, cb)
    except Exception as e:
        logger.error(f"Error in bulk_append_bot_tokens_cancel_handler: {e}\n{traceback.format_exc()}")
        try: await cb.answer(f"❌ Error: {str(e)[:100]}", show_alert=True)
        except: pass

async def process_bulk_append_bot_tokens_input(c: Client, m: Message, state: dict):
    """Memproses input (file atau teks) untuk bulk append bot tokens"""
    try:
        user_id = m.from_user.id
        
        if m.document:
            file_name = m.document.file_name.lower()
            if not (file_name.endswith(".zip") or file_name.endswith(".txt")):
                await m.reply("❌ <b>Error:</b> Mohon kirim file format <b>.zip</b> atau <b>.txt</b>.")
                return
            
            file_path = await m.download()
            parsed_entries = []
            
            if file_name.endswith(".zip"):
                proc_msg = await m.reply("⏳ <b>Memproses file ZIP...</b>", parse_mode=ParseMode.HTML)
                import zipfile
                import shutil
                extract_path = f"Main/cache/append_bots_{user_id}"
                if os.path.exists(extract_path): shutil.rmtree(extract_path)
                os.makedirs(extract_path, exist_ok=True)
                
                try:
                    with zipfile.ZipFile(file_path, 'r') as zip_ref:
                        zip_ref.extractall(extract_path)
                    
                    for root, dirs, files in os.walk(extract_path):
                        for f in files:
                            if f.endswith(".txt") or f.endswith(".json"):
                                with open(os.path.join(root, f), 'r', encoding='utf-8', errors='ignore') as fh:
                                    parsed_entries.extend(extract_tokens_from_text(fh.read()))
                                    
                    if os.path.exists(extract_path):
                        shutil.rmtree(extract_path)
                        
                    if not parsed_entries:
                        await proc_msg.edit("❌ <b>Error:</b> Tidak ditemukan token valid di dalam ZIP.")
                        return
                    await proc_msg.delete()
                except Exception as e:
                    if os.path.exists(extract_path): shutil.rmtree(extract_path)
                    await proc_msg.edit(f"❌ <b>Error memproses ZIP:</b> {e}")
                    return
            else:
                # Single TXT file
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as fh:
                        parsed_entries = extract_tokens_from_text(fh.read())
                    if not parsed_entries:
                        await m.reply("❌ <b>Error:</b> Tidak ditemukan token valid di dalam file TXT.")
                        return
                except Exception as e:
                    await m.reply(f"❌ <b>Error memproses TXT:</b> {e}")
                    return
                finally:
                    if os.path.exists(file_path): os.remove(file_path)
                    
            # Execute appending
            if user_id in user_bulk_append_bot_tokens_state:
                del user_bulk_append_bot_tokens_state[user_id]
            await execute_bulk_append_bot_tokens(c, m, parsed_entries)
            
        else:
            # Raw text message input
            input_text = (m.text or m.caption or "").strip()
            if input_text.lower() in ["/cancel", "cancel", "batal"]:
                if user_id in user_bulk_append_bot_tokens_state:
                    del user_bulk_append_bot_tokens_state[user_id]
                await m.reply("❌ Input dibatalkan.")
                return
                
            parsed_entries = extract_tokens_from_text(input_text)
            if not parsed_entries:
                await m.reply("❌ <b>Error:</b> Tidak ada token valid yang ditemukan dalam teks Anda.")
                return
                
            if user_id in user_bulk_append_bot_tokens_state:
                del user_bulk_append_bot_tokens_state[user_id]
            await execute_bulk_append_bot_tokens(c, m, parsed_entries)
    except Exception as e:
        logger.error(f"Error in process_bulk_append_bot_tokens_input: {e}\n{traceback.format_exc()}")
        try: await m.reply(f"❌ Error processing input: {e}")
        except: pass

