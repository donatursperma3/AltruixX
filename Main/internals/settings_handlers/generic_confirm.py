# Main/internals/settings_handlers/generic_confirm.py
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from Main.core.decorators import log_errors, iuser_check
from Main.core.client import Altruix
from pyrogram.enums import ParseMode

@Altruix.bot.on_callback_query(filters.regex(r"^gen_conf_(.+)$"))
@iuser_check
@log_errors
async def gen_confirm_handler(c: Client, cb: CallbackQuery):
    """Generic confirmation bridge for session info buttons."""
    gt = Altruix.get_string
    await cb.answer()
    
    # Format: gen_conf_{real_callback_data}
    real_data = cb.matches[0].group(1)
    
    # Extract index and page if available for the 'No' button
    # Pattern: action_name_index_page
    parts = real_data.split("_")
    index = "0"
    page = "1"
    
    # Heuristic to find index and page from the end of the string
    if len(parts) >= 2:
        if parts[-1].isdigit() and parts[-2].isdigit():
            index = parts[-2]
            page = parts[-1]
        elif parts[-1].isdigit():
            index = parts[-1]
            page = "1"
            
    confirm_buttons = [
        [
            InlineKeyboardButton(gt("yes"), callback_data=real_data),
            InlineKeyboardButton(gt("no"), callback_data=f"session_info_{index}_{page}")
        ]
    ]
    
    # Format action name for display
    display_action = real_data.replace('_', ' ').title()
    
    confirm_text = gt("confirm_action_template").format(display_action) if Altruix.get_string("confirm_action_template") else f"<b>❓ Confirm Action</b>\n\nAre you sure you want to proceed?\n\nAction: <code>{display_action}</code>"
    
    await cb.message.edit(
        text=confirm_text,
        reply_markup=InlineKeyboardMarkup(confirm_buttons),
        parse_mode=ParseMode.HTML
    )
