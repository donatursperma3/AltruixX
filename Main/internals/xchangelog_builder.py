# Main/internals/xchangelog_builder.py
# ============================================================================
# ROLE: UI Builder and Callback Handler for Paginated Changelog
# FRAMEWORK: Altruix / Kurigram (Powered by Bot Assistant)
# DESCRIPTION: 
#   Central module for interactive changelog components.
#   Handles Inline Queries and Callback Queries via Bot Assistant.
# ============================================================================

import os
import re
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
CHANGELOG_PATH = "changelog.md"
QUERY_PREFIX = "clog_view"
CB_PREFIX = "clog_"
logger = logging.getLogger("altruix.xchangelog.builder")

# ============================================================================
# DATA PARSER
# ============================================================================

def parse_changelog() -> List[str]:
    """Reads changelog.md and splits it into entries.
    Long entries are automatically chunked into multiple parts.
    """
    if not os.path.exists(CHANGELOG_PATH):
        return []
    
    try:
        with open(CHANGELOG_PATH, "r", encoding="utf-8") as f:
            content = f.read()
            
        # 1. Split by horizontal rule separator (Primary split: by Version)
        raw_entries = content.split("---")
        
        final_pages = []
        for entry in raw_entries:
            entry = entry.strip()
            if not entry or entry.startswith("# AltruixX Changelog"):
                continue
            
            # 2. Check if entry is too long (Markdown limit ~3000 to be safe after HTML conversion)
            if len(entry) > 3000:
                # Split entry into chunks of ~2800 characters, trying to split at newlines
                chunks = []
                remaining = entry
                while remaining:
                    if len(remaining) <= 2800:
                        chunks.append(remaining)
                        break
                    
                    # Try to find a good split point (newline)
                    split_idx = remaining.rfind("\n", 0, 2800)
                    if split_idx == -1: # No newline found, hard split
                        split_idx = 2800
                    
                    chunks.append(remaining[:split_idx].strip())
                    remaining = remaining[split_idx:].strip()
                
                # Add chunks with "Part" indicator in title (we'll handle title in build_page)
                # For now, we just add them to the list.
                for i, chunk in enumerate(chunks):
                    prefix = ""
                    if i > 0:
                        # Find the version header to repeat it
                        version_match = re.search(r'## \[(.*?)\]', chunks[0])
                        v_str = version_match.group(1) if version_match else "Update"
                        prefix = f"## [{v_str}] (Part {i+1})\n\n"
                    final_pages.append(prefix + chunk)
            else:
                final_pages.append(entry)
                
        return final_pages
    except Exception as e:
        logger.error(f"Error parsing changelog: {e}")
        return []

def format_entry_to_html(entry: str) -> str:
    """Converts a single changelog entry from Markdown to aesthetic HTML."""
    # Escape HTML but keep our specific formatting
    entry_html = html.escape(entry)
    
    # Format Headers: ## [Version] -> 📦 <b>Version: Version</b>
    entry_html = re.sub(r'## \[(.*?)\]', r'📦 <b>Version: \1</b>', entry_html)
    
    # Format Subheaders: ### Category -> <u>Category</u>
    entry_html = re.sub(r'### (.*)', r'<u>\1</u>', entry_html)
    
    # Format Bullet points for better look
    entry_html = entry_html.replace("- ", "• ")
    
    # Bold patterns like **Text** -> <b>Text</b>
    entry_html = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', entry_html)
    
    return entry_html

# ============================================================================
# UI BUILDERS
# ============================================================================

async def build_changelog_page(owner_id: int, page: int = 0) -> Tuple[str, InlineKeyboardMarkup]:
    """Generates a paginated view of changelog entries."""
    user_style = get_user_button_style(owner_id)
    entries = parse_changelog()
    total_entries = len(entries)
    
    if not entries:
        text = (
            "<blockquote expandable>"
            "<b>📜 AltruixX Changelog</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "❌ <i>Changelog data not found or empty.</i>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "</blockquote>"
        )
        buttons = [[InlineKeyboardButton("❌ Close", callback_data=f"{CB_PREFIX}close")]]
        return text, InlineKeyboardMarkup(buttons)

    # Ensure page is within bounds
    if page < 0: page = 0
    if page >= total_entries: page = total_entries - 1
    
    current_entry = entries[page]
    entry_html = format_entry_to_html(current_entry)
    
    text = (
        "<blockquote expandable>"
        "<b>📜 AltruixX Changelog</b>\n"
        f"<i>Page {page + 1} of {total_entries}</i>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{entry_html}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Gunakan navigasi di bawah untuk melihat riwayat.</i>"
        "</blockquote>"
    )
    
    buttons = []
    # Row 1: [Prev] [N/N] [Next]
    nav = []
    
    # Prev button
    if page > 0:
        nav.append(InlineKeyboardButton("«", callback_data=f"{CB_PREFIX}page_{page-1}_{owner_id}", style=user_style))
    else:
        nav.append(InlineKeyboardButton(" ", callback_data=f"{CB_PREFIX}noop", style=user_style))
        
    # N/N indicator
    nav.append(InlineKeyboardButton(f"{page+1}/{total_entries}", callback_data=f"{CB_PREFIX}noop", style=user_style))
    
    # Next button
    if page < total_entries - 1:
        nav.append(InlineKeyboardButton("»", callback_data=f"{CB_PREFIX}page_{page+1}_{owner_id}", style=user_style))
    else:
        nav.append(InlineKeyboardButton(" ", callback_data=f"{CB_PREFIX}noop", style=user_style))
    
    buttons.append(nav)
    
    # Row 2: [First] [Last]
    jump_row = [
        InlineKeyboardButton("First", callback_data=f"{CB_PREFIX}page_0_{owner_id}", style=user_style),
        InlineKeyboardButton("Last", callback_data=f"{CB_PREFIX}page_{total_entries-1}_{owner_id}", style=user_style)
    ]
    buttons.append(jump_row)
    
    # Row 3: [Refresh] [Close]
    buttons.append([
        InlineKeyboardButton("🔄 Refresh", callback_data=f"{CB_PREFIX}page_{page}_{owner_id}", style=user_style),
        InlineKeyboardButton("❌ Close", callback_data=f"{CB_PREFIX}close", style=user_style)
    ])
    
    return text, InlineKeyboardMarkup(buttons)

# ============================================================================
# BOT ASSISTANT HANDLERS
# ============================================================================

@Altruix.bot.on_inline_query(filters.regex(r"^clog_view_(\d+)_(\d+)"))
@iuser_check
@log_errors
async def changelog_inline_handler(c: Client, iq: InlineQuery):
    """Handles inline queries to display the paginated changelog."""
    page = int(iq.matches[0].group(1))
    owner_id = int(iq.matches[0].group(2))
    
    text, kb = await build_changelog_page(owner_id, page=page)
    
    results = [
        InlineQueryResultArticle(
            id=f"{QUERY_PREFIX}_{page}_{owner_id}",
            title=f"AltruixX Changelog - Entry {page + 1}",
            description=f"Klik untuk mengirim changelog (Halaman {page + 1}).",
            input_message_content=InputTextMessageContent(
                text, parse_mode=enums.ParseMode.HTML
            ),
            reply_markup=kb,
            thumb_url="https://telegra.ph/file/0c6f5a3e1445790c9b0e2.jpg"
        )
    ]
    await iq.answer(results, cache_time=0, is_personal=True)

@Altruix.bot.on_callback_query(filters.regex(r"^clog_"))
@iuser_check
@log_errors
async def changelog_callback_handler(c: Client, cb: CallbackQuery):
    """Processes all interactions with the changelog inline menu."""
    data = cb.data.split("_")
    action = data[1] # page, close, noop
    
    try:
        if action == "page":
            page = int(data[2])
            owner_id = int(data[3])
            text, kb = await build_changelog_page(owner_id, page)
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            
        elif action == "close":
            await cb.message.delete()
            
        elif action == "noop":
            await cb.answer()
            
    except MessageNotModified:
        pass
    except Exception as e:
        logger.error(f"Changelog Callback Error: {e}", exc_info=True)
        await cb.answer(f"❌ Error: {str(e)}", show_alert=True)
