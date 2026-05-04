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

async def get_sessions_buttons(page=1, user_id=None) -> tuple:
    """Mendapatkan tombol session dengan layout 9 tombol per halaman (3 baris x 3 kolom)"""
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(user_id) if user_id else enums.ButtonStyle.PRIMARY
    sessions_per_page = 10

    
    if not hasattr(Altruix, 'clients') or not Altruix.clients:
        return [], False, 1
    
    total_sessions = len(Altruix.clients)
    total_pages = (total_sessions + sessions_per_page - 1) // sessions_per_page
    
    if page < 1: page = 1
    elif page > total_pages: page = total_pages if total_pages > 0 else 1
    start_index = (page - 1) * sessions_per_page
    end_index = min(start_index + sessions_per_page, total_sessions)

    # Fetch display mode
    list_mode = await Altruix.config.get_env("SESSION_LIST_MODE", default="name")
    
    buttons = []
    for index in range(start_index, end_index):
        client = Altruix.clients[index]
        try:
            session_num = index + 1
            me = getattr(client, 'myself', None)
            
            user_id = getattr(me, 'id', None)
            is_disabled = Altruix.is_session_disabled(user_id) if user_id else False
            status_icon = "🔴" if is_disabled else "🟢"

            if str(list_mode).lower() == "id" and user_id:
                display_text = str(user_id)
            else:
                first_name = getattr(me, 'first_name', 'Unknown')
                if not first_name or first_name == 'Unknown':
                    first_name = f"Session {session_num}"
                display_text = first_name[:15]

            button_text = f"{status_icon} [{session_num}] {display_text}"
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
    
    arranged_buttons = arrange_buttons(buttons, 2)

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

    session_buttons, has_next, total_pages = await get_sessions_buttons(page, user_id=user_id)
    LOG_CHAT_ID = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_USERS_ID))

    # Row 1: Action buttons
    action_buttons = [
        InlineKeyboardButton(gt("btn_stats"), "sessions_stats", style=user_style),
        InlineKeyboardButton("➕ Add Session", "add_session", style=user_style),
        InlineKeyboardButton("📲 Login QR", "login_qr", style=user_style)
    ]
    
    # Row 2: Prev / Page / Next
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("« Prev", f"sessions_list_{page - 1}", style=user_style))
    else:
        nav_row.append(InlineKeyboardButton("·", "noop", style=user_style))
    nav_row.append(InlineKeyboardButton(f"{page}/{total_pages or 1}", "noop", style=user_style))
    if has_next:
        nav_row.append(InlineKeyboardButton("Next »", f"sessions_list_{page + 1}", style=user_style))
    else:
        nav_row.append(InlineKeyboardButton("·", "noop", style=user_style))
    
    # Row 3: First / Back / Last
    bottom_row = [
        InlineKeyboardButton("« First", f"sessions_list_1", style=user_style),
        InlineKeyboardButton("« Back »", "settings_menu", style=user_style),
        InlineKeyboardButton("Last »", f"sessions_list_{total_pages or 1}", style=user_style)
    ]
    
    # Construct final markup
    final_markup = []
    for row in session_buttons: final_markup.append(row)
    final_markup.append(action_buttons)
    final_markup.append(nav_row)
    final_markup.append(bottom_row)

    
    total_sessions = len(Altruix.clients)
    start_session = ((page - 1) * 10) + 1
    end_session = min(page * 10, total_sessions)

    # Calculate enabled/disabled counts
    enabled_count = 0
    disabled_count = 0
    for client in Altruix.clients:
        try:
            if client.me:
                if client.me.id in Altruix.disabled_sessions:
                    disabled_count += 1
                else:
                    enabled_count += 1
        except: continue

    try:
        await edit_cb(
            cb,
            text=f"<b>📱 Sessions Manager</b>\n\n"
                 f"<b>Total Sessions:</b> <code>{total_sessions}</code>\n"
                 f"<b>Enabled:</b> <code>{enabled_count}</code> | <b>Disabled:</b> <code>{disabled_count}</code>\n"
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

@Altruix.bot.on_callback_query(filters.regex(r"^noop$"))
@log_errors
async def noop_handler(c: Client, cb: CallbackQuery):
    """No-op handler for placeholder/info-only buttons."""
    await cb.answer()
