# Main/internals/xlist_builder.py
# ============================================================================
# ROLE: UI Builder and Callback Handler for Command List
# FRAMEWORK: Altruix / Kurigram (Powered by Bot Assistant)
# DESCRIPTION: 
#   Central module for interactive components of the Command List.
#   Handles Inline Queries and Callback Queries via Bot Assistant.
# ============================================================================

import html
import logging
from typing import List, Tuple
from pyrogram import Client, enums, filters
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, 
    InlineQuery, InlineQueryResultArticle, InputTextMessageContent
)
from pyrogram.errors import MessageNotModified

from Main import Altruix
from Main.core.decorators import log_errors, iuser_check
from Main.utils.file_helpers import get_user_button_style

# Configuration
PLUGINS_PER_PAGE = 6
QUERY_CONFIRM = "listcmds_confirm"
QUERY_LIST = "listcmds_list"
logger = logging.getLogger("altruix.xlist.builder")

# ============================================================================
# UI BUILDERS
# ============================================================================

async def build_cmds_confirmation(owner_id: int):
    """Generates the confirmation dashboard before listing commands."""
    user_style = get_user_button_style(owner_id)
    
    text = (
        f"<blockquote expandable>"
        "<b>📜 COMMAND LIST CONFIRMATION</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Apakah Anda yakin ingin melihat daftar seluruh perintah?</i>\n"
        "Pesan ini akan diupdate menjadi daftar perintah yang terpaginasi.\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "</blockquote>"
    )
    
    buttons = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"listcmds_approve_{owner_id}", style=user_style),
            InlineKeyboardButton("❌ Reject", callback_data="listcmds_reject", style=user_style)
        ]
    ]
    
    return text, InlineKeyboardMarkup(buttons)

async def build_cmds_list(owner_id: int, page: int = 0) -> Tuple[str, InlineKeyboardMarkup]:
    """Generates a paginated list of all command triggers."""
    user_style = get_user_button_style(owner_id)
    
    # Filter and sort plugins that actually have commands
    all_plugins = sorted(Altruix.cmd_list.keys())
    valid_plugins = []
    for plugin in all_plugins:
        has_cmds = False
        for cmd_info in Altruix.cmd_list[plugin]:
            if cmd_info.get("commands"):
                has_cmds = True
                break
        if has_cmds:
            valid_plugins.append(plugin)
            
    total_plugins_count = len(valid_plugins)
    
    # Calculate pagination
    start = page * PLUGINS_PER_PAGE
    end = start + PLUGINS_PER_PAGE
    current_plugins = valid_plugins[start:end]
    
    text = (
        "<blockquote expandable>"
        "<b>📜 List of All Command Triggers</b>\n"
        f"<i>Halaman {page + 1} | Total Plugin: {total_plugins_count}</i>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    
    total_cmds_on_page = 0
    for plugin in current_plugins:
        cmds = []
        for cmd_info in Altruix.cmd_list[plugin]:
            cmds.extend(cmd_info.get("commands", []))
        
        if cmds:
            unique_cmds = sorted(set(cmds))
            total_cmds_on_page += len(unique_cmds)
            cmd_str = ", ".join([f"<code>{c}</code>" for c in unique_cmds])
            text += f"<b>Plugin:</b> <code>{plugin}</code>\n<b>Cmds:</b> {cmd_str}\n\n"
    
    if not current_plugins:
        text += "<i>Tidak ada plugin ditemukan.</i>\n\n"

    text += "━━━━━━━━━━━━━━━━━━━━\n"
    text += f"<i>Gunakan {Altruix.prefix_owner_user}help &lt;plugin&gt; untuk detail!</i>"
    text += "</blockquote>"

    buttons = []
    # Row 1: Navigation [Prev] [N/N] [Next]
    nav = []
    total_pages = (total_plugins_count - 1) // PLUGINS_PER_PAGE + 1 if total_plugins_count > 0 else 0
    
    # Prev button
    if page > 0:
        nav.append(InlineKeyboardButton("«", callback_data=f"listcmds_page_{page-1}_{owner_id}", style=user_style))
    else:
        nav.append(InlineKeyboardButton(" ", callback_data="listcmds_noop", style=user_style))
        
    # N/N button
    nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="listcmds_noop", style=user_style))
    
    # Next button
    if end < total_plugins_count:
        nav.append(InlineKeyboardButton("»", callback_data=f"listcmds_page_{page+1}_{owner_id}", style=user_style))
    else:
        nav.append(InlineKeyboardButton(" ", callback_data="listcmds_noop", style=user_style))
    
    buttons.append(nav)
    
    # Row 2: [First] [Last]
    jump_row = [
        InlineKeyboardButton("First", callback_data=f"listcmds_page_0_{owner_id}", style=user_style),
        InlineKeyboardButton("Last", callback_data=f"listcmds_page_{total_pages-1}_{owner_id}", style=user_style)
    ]
    buttons.append(jump_row)
    
    # Row 3: [Refresh] [Tutup]
    buttons.append([
        InlineKeyboardButton("🔄 Refresh", callback_data=f"listcmds_page_{page}_{owner_id}", style=user_style),
        InlineKeyboardButton("❌ Close", callback_data="listcmds_close", style=user_style)
    ])
    
    return text, InlineKeyboardMarkup(buttons)

# ============================================================================
# BOT ASSISTANT HANDLERS
# ============================================================================

@Altruix.bot.on_inline_query(filters.regex(r"^listcmds_confirm_(\d+)"))
@iuser_check
@log_errors
async def listcmds_inline_handler(c: Client, iq: InlineQuery):
    """Handles inline queries to display the command list confirmation."""
    owner_id = int(iq.matches[0].group(1))
    
    text, kb = await build_cmds_confirmation(owner_id)
    
    results = [
        InlineQueryResultArticle(
            id=f"listcmds_confirm_{owner_id}",
            title="Command List Confirmation",
            description="Klik untuk mengirim konfirmasi daftar perintah.",
            input_message_content=InputTextMessageContent(
                text, parse_mode=enums.ParseMode.HTML
            ),
            reply_markup=kb,
            thumb_url="https://telegra.ph/file/0c6f5a3e1445790c9b0e2.jpg" # Example icon
        )
    ]
    await iq.answer(results, cache_time=0, is_personal=True)

@Altruix.bot.on_inline_query(filters.regex(r"^listcmds_list_(\d+)_(\d+)"))
@iuser_check
@log_errors
async def listcmds_list_inline_handler(c: Client, iq: InlineQuery):
    """Handles inline queries to display a specific page of the command list directly."""
    page = int(iq.matches[0].group(1))
    owner_id = int(iq.matches[0].group(2))
    
    text, kb = await build_cmds_list(owner_id, page=page)
    
    results = [
        InlineQueryResultArticle(
            id=f"listcmds_page_{page}_{owner_id}",
            title=f"Command List - Page {page + 1}",
            description=f"Klik untuk melihat daftar perintah halaman {page + 1}.",
            input_message_content=InputTextMessageContent(
                text, parse_mode=enums.ParseMode.HTML
            ),
            reply_markup=kb,
            thumb_url="https://telegra.ph/file/0c6f5a3e1445790c9b0e2.jpg"
        )
    ]
    await iq.answer(results, cache_time=0, is_personal=True)

@Altruix.bot.on_callback_query(filters.regex(r"^listcmds_"))
@iuser_check
@log_errors
async def listcmds_callback_handler(c: Client, cb: CallbackQuery):
    """Processes all interactions with the command list inline menus."""
    data = cb.data.split("_")
    action = data[1] # approve, reject, page, close, noop
    
    try:
        if action == "approve":
            owner_id = int(data[2])
            text, kb = await build_cmds_list(owner_id, page=0)
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            await cb.answer("✅ Approved! Memuat daftar perintah...", show_alert=False)
            
        elif action == "reject":
            await cb.answer("❌ Dibatalkan.", show_alert=True)
            await cb.edit_message_text("<b>❌ Operasi Dibatalkan</b>\n<i>Daftar perintah tidak akan ditampilkan.</i>", parse_mode=enums.ParseMode.HTML)
            
        elif action == "page":
            page = int(data[2])
            owner_id = int(data[3])
            text, kb = await build_cmds_list(owner_id, page)
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            
        elif action == "close":
            await cb.message.delete()
            
        elif action == "noop":
            await cb.answer()
            
    except MessageNotModified:
        pass
    except Exception as e:
        logger.error(f"Command List Callback Error: {e}", exc_info=True)
        await cb.answer(f"❌ Error: {str(e)}", show_alert=True)
