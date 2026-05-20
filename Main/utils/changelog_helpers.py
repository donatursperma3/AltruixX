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
from typing import List

# Configuration
CHANGELOG_PATH = "changelog.md"
logger = logging.getLogger("altruix.utils.changelog")

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
        for i, entry in enumerate(raw_entries):
            entry = entry.strip()
            if not entry:
                continue
            
            # If first entry contains the header, strip it instead of skipping the whole entry
            if i == 0 and entry.startswith("# AltruixX Changelog"):
                # Find the first version header (## [x.x.x])
                match = re.search(r'(## \[.*)', entry, re.DOTALL)
                if match:
                    entry = match.group(1).strip()
                else:
                    # No version header found, probably just a pure header page
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
