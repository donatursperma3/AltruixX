# Main/utils/changelog_helpers.py
# ============================================================================
# ROLE: Changelog Parsing and Formatting Utilities
# DESCRIPTION: 
#   Standalone helpers for processing changelog.md. 
#   Separated from builders to avoid circular imports.
# ============================================================================

import os
import re
import html
import logging
from typing import List, Tuple
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Configuration
# Resolve path absolutely relative to this file's location to prevent execution directory mismatch bugs
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHANGELOG_PATH = os.path.join(ROOT_DIR, "changelog.md")
logger = logging.getLogger("altruix.utils.changelog")

CB_PREFIX = "clog_"

def parse_changelog() -> List[str]:
    """Reads changelog.md and splits it into entries based on version headers.
    Long entries are automatically chunked into multiple parts.
    """
    if not os.path.exists(CHANGELOG_PATH):
        logger.warning(f"Changelog file not found at: {CHANGELOG_PATH}")
        return []
    
    try:
        import traceback
        with open(CHANGELOG_PATH, "r", encoding="utf-8") as f:
            content = f.read()
            
        # Split by version header '## [' at the start of a line
        raw_entries = re.split(r'(?m)^(?=## \[)', content)
        
        final_pages = []
        for entry in raw_entries:
            entry = entry.strip()
            if not entry:
                continue
            
            # Clean up leading '# AltruixX Changelog' block if it doesn't contain a version
            if entry.startswith("# AltruixX Changelog") and not entry.startswith("## ["):
                if not re.search(r'## \[', entry):
                    continue
            
            # Clean up trailing/leading '---' lines from the entry
            entry = re.sub(r'(?m)^---\s*$', '', entry).strip()
            if not entry:
                continue
            
            # Check if entry is too long (Markdown limit ~3000 to be safe after HTML conversion)
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
                
                # Add chunks with "Part" indicator in title
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
        logger.error(f"Error parsing changelog: {e}\n{traceback.format_exc()}")
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

async def build_changelog_page(owner_id: int, page: int = 0) -> Tuple[str, InlineKeyboardMarkup]:
    """Generates a paginated view of changelog entries."""
    from Main.utils.file_helpers import get_user_button_style
    
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
        "📜 <b>Latest Changelog Update</b>\n"
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
