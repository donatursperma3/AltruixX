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

async def get_sessions_buttons(page=1, user_id=None, filter_type="all") -> tuple:
    """Mendapatkan tombol session dengan layout 9 tombol per halaman (3 baris x 3 kolom)"""
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(user_id) if user_id else enums.ButtonStyle.PRIMARY
    sessions_per_page = 10

    if not hasattr(Altruix, 'clients') or not Altruix.clients:
        return [], False, 1
    
    # 1. Filter clients first
    filtered_clients = []
    for index, client in enumerate(Altruix.clients):
        try:
            me = getattr(client, 'me', None) or getattr(client, 'myself', None)
            if not me:
                me = await client.get_me()
                client.myself = me
            user_id_val = getattr(me, 'id', None)
            is_disabled = Altruix.is_session_disabled(user_id_val) if user_id_val else False
            
            if filter_type == "enabled":
                if not is_disabled:
                    filtered_clients.append((index, client))
            elif filter_type == "disabled":
                if is_disabled:
                    filtered_clients.append((index, client))
            else:
                filtered_clients.append((index, client))
        except Exception as e:
            logger.warning(f"Error filtering client at index {index}: {e}")
            if filter_type == "all":
                filtered_clients.append((index, client))
    
    total_sessions = len(filtered_clients)
    total_pages = (total_sessions + sessions_per_page - 1) // sessions_per_page
    
    if page < 1: page = 1
    elif page > total_pages: page = total_pages if total_pages > 0 else 1
    start_index = (page - 1) * sessions_per_page
    end_index = min(start_index + sessions_per_page, total_sessions)

    # Fetch display mode
    list_mode = await Altruix.config.get_env("SESSION_LIST_MODE", default="name")
    
    buttons = []
    for index, client in filtered_clients[start_index:end_index]:
        try:
            session_num = index + 1
            me = getattr(client, 'me', None) or getattr(client, 'myself', None)
            if not me:
                me = await client.get_me()
                client.myself = me
            
            user_id_val = getattr(me, 'id', None)
            is_disabled = Altruix.is_session_disabled(user_id_val) if user_id_val else False
            status_icon = "🔴" if is_disabled else "🟢"

            if str(list_mode).lower() == "id" and user_id_val:
                display_text = str(user_id_val)
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

@Altruix.bot.on_callback_query(filters.regex(r"^sessions_list_(\d+)(?:_(\w+))?$"))
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
        parts = cb.data.split("_")
        page = int(parts[2])
        filter_type = parts[3] if len(parts) >= 4 else "all"
    except (ValueError, IndexError):
        page = 1
        filter_type = "all"
        
    if filter_type not in ["all", "enabled", "disabled"]:
        filter_type = "all"

    user_id = cb.from_user.id
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(user_id)

    session_buttons, has_next, total_pages = await get_sessions_buttons(page, user_id=user_id, filter_type=filter_type)
    LOG_CHAT_ID = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_USERS_ID))

    # Row 0: Filter buttons
    filter_all_label = "[All]" if filter_type == "all" else "All"
    filter_enabled_label = "[Enabled]" if filter_type == "enabled" else "Enabled"
    filter_disabled_label = "[Disabled]" if filter_type == "disabled" else "Disabled"
    
    filter_row = [
        InlineKeyboardButton(filter_all_label, f"sessions_list_1_all", style=user_style),
        InlineKeyboardButton(filter_enabled_label, f"sessions_list_1_enabled", style=user_style),
        InlineKeyboardButton(filter_disabled_label, f"sessions_list_1_disabled", style=user_style)
    ]

    # Row 1.5: Enable/Disable All
    bulk_action_row = [
        InlineKeyboardButton("Enable All", f"sessions_enable_all_confirm_{page}_{filter_type}", style=user_style),
        InlineKeyboardButton("Disable All", f"sessions_disable_all_confirm_{page}_{filter_type}", style=user_style)
    ]

    # Row 1: Action buttons
    action_buttons = [
        InlineKeyboardButton(gt("btn_stats"), "sessions_stats", style=user_style),
        InlineKeyboardButton("➕ Add Session", "add_session", style=user_style),
        InlineKeyboardButton("📲 Login QR", "login_qr", style=user_style)
    ]
    
    # Row 2: Prev / Page / Next
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("« Prev", f"sessions_list_{page - 1}_{filter_type}", style=user_style))
    else:
        nav_row.append(InlineKeyboardButton("·", "noop", style=user_style))
    nav_row.append(InlineKeyboardButton(f"{page}/{total_pages or 1}", "noop", style=user_style))
    if has_next:
        nav_row.append(InlineKeyboardButton("Next »", f"sessions_list_{page + 1}_{filter_type}", style=user_style))
    else:
        nav_row.append(InlineKeyboardButton("·", "noop", style=user_style))
    
    # Row 3: First / Back / Last
    bottom_row = [
        InlineKeyboardButton("First", f"sessions_list_1_{filter_type}", style=user_style),
        InlineKeyboardButton("« Back »", "settings_menu", style=user_style),
        InlineKeyboardButton("Last", f"sessions_list_{(total_pages or 1)}_{filter_type}", style=user_style)
    ]
    
    # Construct final markup
    final_markup = []
    final_markup.append(filter_row)
    for row in session_buttons: final_markup.append(row)
    final_markup.append(bulk_action_row)
    final_markup.append(action_buttons)
    final_markup.append(nav_row)
    final_markup.append(bottom_row)

    # Filtered and total counts calculation
    total_sessions_all = len(Altruix.clients) if hasattr(Altruix, 'clients') else 0
    filtered_clients_count = 0
    enabled_count = 0
    disabled_count = 0
    
    for client in Altruix.clients:
        try:
            me = getattr(client, 'me', None) or getattr(client, 'myself', None)
            if not me:
                me = await client.get_me()
                client.myself = me
            user_id_val = getattr(me, 'id', None)
            is_disabled = Altruix.is_session_disabled(user_id_val) if user_id_val else False
            
            if is_disabled:
                disabled_count += 1
            else:
                enabled_count += 1
                
            if filter_type == "enabled":
                if not is_disabled:
                    filtered_clients_count += 1
            elif filter_type == "disabled":
                if is_disabled:
                    filtered_clients_count += 1
            else:
                filtered_clients_count += 1
        except:
            if filter_type == "all":
                filtered_clients_count += 1

    start_session = ((page - 1) * 10) + 1 if filtered_clients_count > 0 else 0
    end_session = min(page * 10, filtered_clients_count)

    try:
        await edit_cb(
            cb,
            text=f"<blockquote expandable>"
                 f"<b>📱 Sessions Manager</b>\n\n"
                 f"<b>Total Sessions:</b> <code>{total_sessions_all}</code>\n"
                 f"<b>Enabled:</b> <code>{enabled_count}</code> | <b>Disabled:</b> <code>{disabled_count}</code>\n"
                 f"<b>Filter:</b> <code>{filter_type.upper()}</code> (<code>{filtered_clients_count}</code> sessions)\n"
                 f"<b>Showing:</b> <code>{start_session}-{end_session}</code>\n"
                 f"<b>Page:</b> <code>{page}/{total_pages or 1}</code>\n\n"
                 f"Select a session below to manage it or use the bulk actions."
                 f"</blockquote>",
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

@Altruix.bot.on_callback_query(filters.regex(r"^sessions_enable_all_confirm_(\d+)_(\w+)$"))
@log_errors
@iuser_check
async def sessions_enable_all_confirm_handler(c: Client, cb: CallbackQuery):
    """Konfirmasi mengaktifkan semua sesi"""
    if not await check_authorization(cb): return
    await cb.answer()
    
    match = cb.matches[0]
    page = int(match.group(1))
    filter_type = match.group(2)
    
    user_id = cb.from_user.id
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(user_id)
    
    text = (
        "<blockquote expandable>"
        "<b>✅ Konfirmasi Enable All Session</b>\n\n"
        "Apakah Anda yakin ingin mengaktifkan KEMBALI <b>SELURUH</b> sesi userbot?\n\n"
        "Setelah diaktifkan, semua akun akan kembali merespons perintah secara normal."
        "</blockquote>"
    )
    
    buttons = [
        [
            InlineKeyboardButton("✅ Ya, Aktifkan Semua", f"sessions_enable_all_execute_{page}_{filter_type}", style=user_style),
            InlineKeyboardButton("❌ Batal", f"sessions_list_{page}_{filter_type}", style=user_style)
        ]
    ]
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons))

@Altruix.bot.on_callback_query(filters.regex(r"^sessions_enable_all_execute_(\d+)_(\w+)$"))
@log_errors
@iuser_check
async def sessions_enable_all_execute_handler(c: Client, cb: CallbackQuery):
    """Eksekusi mengaktifkan semua sesi"""
    if not await check_authorization(cb): return
    
    match = cb.matches[0]
    page = int(match.group(1))
    filter_type = match.group(2)
    
    try:
        Altruix.disabled_sessions.clear()
        Altruix.save_disabled_sessions()
        await cb.answer("✅ Seluruh sesi telah diaktifkan kembali!", show_alert=True)
    except Exception as e:
        logger.error(f"Error in sessions_enable_all_execute_handler: {e}", exc_info=True)
        await cb.answer(f"❌ Error: {str(e)}", show_alert=True)
        
    # Return to sessions list
    cb.data = f"sessions_list_{page}_{filter_type}"
    await sessions_menu_cb_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^sessions_disable_all_confirm_(\d+)_(\w+)$"))
@log_errors
@iuser_check
async def sessions_disable_all_confirm_handler(c: Client, cb: CallbackQuery):
    """Konfirmasi menonaktifkan semua sesi"""
    if not await check_authorization(cb): return
    await cb.answer()
    
    match = cb.matches[0]
    page = int(match.group(1))
    filter_type = match.group(2)
    
    user_id = cb.from_user.id
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(user_id)
    
    text = (
        "<blockquote expandable>"
        "<b>⚠️ Konfirmasi Disable All Session</b>\n\n"
        "Apakah Anda yakin ingin menonaktifkan <b>SELURUH</b> sesi userbot?\n\n"
        "Setelah dinonaktifkan, semua akun tidak akan merespons perintah apapun sampai Anda mengaktifkannya kembali secara manual."
        "</blockquote>"
    )
    
    buttons = [
        [
            InlineKeyboardButton("✅ Ya, Nonaktifkan Semua", f"sessions_disable_all_execute_{page}_{filter_type}", style=user_style),
            InlineKeyboardButton("❌ Batal", f"sessions_list_{page}_{filter_type}", style=user_style)
        ]
    ]
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons))

@Altruix.bot.on_callback_query(filters.regex(r"^sessions_disable_all_execute_(\d+)_(\w+)$"))
@log_errors
@iuser_check
async def sessions_disable_all_execute_handler(c: Client, cb: CallbackQuery):
    """Eksekusi menonaktifkan semua sesi"""
    if not await check_authorization(cb): return
    
    match = cb.matches[0]
    page = int(match.group(1))
    filter_type = match.group(2)
    
    try:
        count = 0
        for client in Altruix.clients:
            try:
                me = getattr(client, 'me', None) or getattr(client, 'myself', None)
                if not me:
                    me = await client.get_me()
                    client.myself = me
                if me:
                    Altruix.disabled_sessions.add(me.id)
                    count += 1
            except Exception as e:
                logger.warning(f"Failed to get client identity for disable all: {e}")
                continue
                
        Altruix.save_disabled_sessions()
        await cb.answer(f"✅ {count} Sesi telah dinonaktifkan!", show_alert=True)
    except Exception as e:
        logger.error(f"Error in sessions_disable_all_execute_handler: {e}", exc_info=True)
        await cb.answer(f"❌ Error: {str(e)}", show_alert=True)
        
    # Return to sessions list
    cb.data = f"sessions_list_{page}_{filter_type}"
    await sessions_menu_cb_handler(c, cb)
