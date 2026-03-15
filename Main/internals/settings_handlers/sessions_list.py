# Main/internals/settings_handlers/sessions_list.py
import html
import os
import logging
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from Main.core.decorators import log_errors, iuser_check
from Main.core.client import Altruix
from pyrogram.enums import ParseMode, ButtonStyle
from pyrogram import enums, types

# Utils
from .utils import edit_cb, check_authorization, gt

# Logger
logger = logging.getLogger(__name__)

def arrange_buttons(array: list, no=3) -> list:
    """Mengatur tombol dalam baris dengan jumlah tertentu per baris"""
    n = int(no)
    return [array[i * n : (i + 1) * n] for i in range((len(array) + n - 1) // n)]

def get_sessions_buttons(page=1, user_id=None) -> tuple:
    """Mendapatkan tombol session dengan layout 9 tombol per halaman (3 baris x 3 kolom)"""
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(user_id) if user_id else enums.ButtonStyle.PRIMARY
    sessions_per_page = 9
    
    if not hasattr(Altruix, 'clients') or not Altruix.clients:
        return [], False, 1
    
    total_sessions = len(Altruix.clients)
    total_pages = (total_sessions + sessions_per_page - 1) // sessions_per_page
    
    if page < 1: page = 1
    elif page > total_pages: page = total_pages if total_pages > 0 else 1
    
    start_index = (page - 1) * sessions_per_page
    end_index = min(start_index + sessions_per_page, total_sessions)
    
    buttons = []
    for index in range(start_index, end_index):
        client = Altruix.clients[index]
        try:
            session_num = index + 1
            me = getattr(client, 'myself', None)
            first_name = getattr(me, 'first_name', 'Unknown')
            if not first_name or first_name == 'Unknown':
                first_name = f"Session {session_num}"
            
            user_id = getattr(me, 'id', None)
            is_disabled = Altruix.is_session_disabled(user_id) if user_id else False
            status_icon = "❌" if is_disabled else "✅"

            button_text = f"{status_icon} [{session_num}] {first_name[:15]}"
            buttons.append(
                InlineKeyboardButton(button_text, f"session_info_{index}_{page}",
                    style=user_style)
            )
        except Exception:
            buttons.append(
                InlineKeyboardButton(f"[{index + 1}] Session {index + 1}", f"session_info_{index}_{page}",
                    style=user_style)
            )
    
    if not buttons: return [], False, 1
    
    arranged_buttons = arrange_buttons(buttons, 3)
    has_next = page < total_pages
    return arranged_buttons, has_next, total_pages

@Altruix.bot.on_callback_query(filters.regex(r"^sessions_list_(\d+)$"))
@log_errors
@iuser_check
async def sessions_menu_cb_handler(c: Client, cb: CallbackQuery):
    """Handler untuk menampilkan menu sessions dengan layout baru"""
    if not await check_authorization(cb): return
    try:
        await cb.answer()
    except Exception:
        pass
    try:
        page = int(cb.data.split("_")[-1])
    except (ValueError, IndexError):
        page = 1

    user_id = cb.from_user.id
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(user_id)

    session_buttons, has_next, total_pages = get_sessions_buttons(page, user_id=user_id)
    LOG_CHAT_ID = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_USERS_ID))

    action_buttons = [
        [
            InlineKeyboardButton("👥 Bulk Join", "bulk_join_menu", style=user_style),
            InlineKeyboardButton("🏃 Bulk Leave", "bulk_leave_menu", style=user_style),
            InlineKeyboardButton("🚩 Bulk Report", "bulk_report_menu", style=user_style)
        ],
        [
            InlineKeyboardButton("🏓 Test Ping All", "test_ping_all_confirmation", style=user_style),
            InlineKeyboardButton(gt("btn_stats"), "sessions_stats", style=user_style),
            InlineKeyboardButton("➕ Add a Session", "add_session", style=user_style)
        ]
    ]
    
    export_buttons = [
        InlineKeyboardButton("📤 Export Sessions", "export_all_sessions_confirmation", style=user_style),
        InlineKeyboardButton("📲 Export Phones", "export_all_phones_confirmation", style=user_style)
    ]

    system_control_buttons = [
        InlineKeyboardButton("🔄 Force Restart", "sys_ctrl_restart", style=user_style),
        InlineKeyboardButton("❌ Force Shutdown", "sys_ctrl_shutdown", style=user_style)
    ]
    
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ Previous", f"sessions_list_{page - 1}", style=user_style))
    nav_buttons.append(InlineKeyboardButton(f"🔙 Back [{page}/{total_pages or 1}]", "settings_menu", style=user_style))
    if has_next:
        nav_buttons.append(InlineKeyboardButton("Next ➡️", f"sessions_list_{page + 1}", style=user_style))
    
    # Construct final markup
    final_markup = []
    for row in session_buttons: final_markup.append(row)
    for row in action_buttons: final_markup.append(row)
    final_markup.append(export_buttons)
    final_markup.append(system_control_buttons)
    final_markup.append(nav_buttons)
    
    total_sessions = len(Altruix.clients)
    start_session = ((page - 1) * 9) + 1
    end_session = min(page * 9, total_sessions)
    
    try:
        await edit_cb(
            cb,
            text=f"<b>📱 Sessions Manager</b>\n\n"
                 f"<b>Total Sessions:</b> <code>{total_sessions}</code>\n"
                 f"<b>Showing:</b> <code>{start_session}-{end_session}</code>\n"
                 f"<b>Page:</b> <code>{page}/{total_pages or 1}</code>\n\n"
                 f"Select a session below to manage it or use the bulk actions.",
            reply_markup=InlineKeyboardMarkup(final_markup)
        )
    except Exception as e:
        await Altruix.bot.send_message(
            LOG_CHAT_ID,
            f"⚠️ <b>SESSION MENU ERROR</b>\n• Error: <code>{html.escape(str(e))}</code>\n• Time: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}",
            parse_mode=ParseMode.HTML
        )
        await edit_cb(cb, "❌ Failed to load menu.")
