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
        "<b>🛠️ Bulk Controls Manager</b>\n\n"
        "Manage multiple sessions or system-wide actions at once:"
    )
    
    buttons = [
        [
            InlineKeyboardButton("👥 Bulk Join", "bulk_join_menu", style=user_style),
            InlineKeyboardButton("🏃 Bulk Leave", "bulk_leave_menu", style=user_style)
        ],
        [
            InlineKeyboardButton("🚩 Bulk Report", "bulk_report_menu", style=user_style),
            InlineKeyboardButton("🏓 Test Ping All", "test_ping_all_confirmation", style=user_style)
        ],
        [
            InlineKeyboardButton("📤 Export Sessions", "export_all_sessions_confirmation", style=user_style),
            InlineKeyboardButton("📲 Export Phones", "export_all_phones_confirmation", style=user_style)
        ],
        [
            InlineKeyboardButton("🔄 Force Restart", "sys_ctrl_restart", style=user_style),
            InlineKeyboardButton("❌ Force Shutdown", "sys_ctrl_shutdown", style=user_style)
        ],
        [
            InlineKeyboardButton("🔙 Back to Settings", "settings_menu", style=user_style)
        ]
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
