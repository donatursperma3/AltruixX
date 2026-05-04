from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from Main.core.client import Altruix

PLUGIN_VERSION = "1.0.10"

def get_status_icon(client):
    """Return a status icon for the client."""
    if hasattr(client, "is_connected") and client.is_connected:
        return "🟢"
    return "🔴"

def build_dashboard(user_id, stories, page, total_pages, filter_type="all", acc_page=1):
    """Build the main story feed dashboard."""
    buttons = []
    
    # --- Account List Section ---
    buttons.append([InlineKeyboardButton("📂 Account List", callback_data="xstory_noop")])
    
    # 📱 Account Indicators (Chunked by 2)
    acc_limit = 8
    total_accs = len(Altruix.clients)
    acc_total_pages = (total_accs + acc_limit - 1) // acc_limit or 1
    acc_start = (acc_page - 1) * acc_limit
    acc_end = acc_start + acc_limit
    
    acc_buttons = []
    for i, client in enumerate(Altruix.clients[acc_start:acc_end], start=acc_start):
        icon = get_status_icon(client)
        name = getattr(client, "me", None)
        name_str = name.first_name[:8] if name else f"Acc{i+1}"
        acc_buttons.append(InlineKeyboardButton(f"{icon} {name_str}", callback_data=f"xstory_acc_{i}_{acc_page}"))
        
    for i in range(0, len(acc_buttons), 2):
        buttons.append(acc_buttons[i:i+2])
        
    # Account Pagination
    acc_nav = []
    if acc_page > 1:
        acc_nav.append(InlineKeyboardButton("« Prev", callback_data=f"xstory_accpage_{acc_page-1}_{page}_{filter_type}"))
    
    acc_nav.append(InlineKeyboardButton(f"Page {acc_page}/{acc_total_pages}", callback_data="xstory_noop"))
    
    if acc_page < acc_total_pages:
        acc_nav.append(InlineKeyboardButton("Next »", callback_data=f"xstory_accpage_{acc_page+1}_{page}_{filter_type}"))
        
    buttons.append(acc_nav)
        
    # --- Story List Section ---
    buttons.append([InlineKeyboardButton("📜 Story List", callback_data="xstory_noop")])

    # 📂 Filter Tabs
    filter_row = [
        InlineKeyboardButton(f"{'• ' if filter_type == 'all' else ''}All", callback_data=f"xstory_filter_all_{acc_page}"),
        InlineKeyboardButton(f"{'• ' if filter_type == 'unread' else ''}Unread", callback_data=f"xstory_filter_unread_{acc_page}"),
        InlineKeyboardButton(f"{'• ' if filter_type == 'archived' else ''}Archived", callback_data=f"xstory_filter_archived_{acc_page}")
    ]
    buttons.append(filter_row)

    # 📜 Story List
    story_buttons = []
    for story in stories:
        peer_id = story["peer_id"]
        story_id = story["story_id"]
        media_icon = "🖼" if story["media_type"] == "photo" else "🎬"
        viewed_icon = "👁" if story.get("is_viewed") else "🆕"
        
        # Display name could be retrieved from cache or just ID if not available
        display_name = str(peer_id)[:8] 
        
        story_buttons.append(
            InlineKeyboardButton(
                f"{viewed_icon} {media_icon} {display_name} (#{story_id})",
                callback_data=f"xstory_view_{peer_id}_{story_id}_{page}_{acc_page}"
            )
        )
        
    for i in range(0, len(story_buttons), 2):
        buttons.append(story_buttons[i:i+2])

    # 📑 Pagination
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("« Prev", callback_data=f"xstory_page_{page-1}_{filter_type}_{acc_page}"))
    
    nav_row.append(InlineKeyboardButton(f"Page {page}/{total_pages}", callback_data="xstory_noop"))
    
    if page < total_pages:
        nav_row.append(InlineKeyboardButton("Next »", callback_data=f"xstory_page_{page+1}_{filter_type}_{acc_page}"))
    
    if nav_row:
        buttons.append(nav_row)

    # 🛠 Global Actions
    buttons.append([
        InlineKeyboardButton("🔄 Refresh Feed", callback_data="xstory_refresh"),
        InlineKeyboardButton("⚙️ Settings", callback_data="xstory_settings")
    ])
    
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="xstory_close")])
    
    return InlineKeyboardMarkup(buttons)

def build_story_menu(peer_id, story_id, page, is_archived=False, is_whitelisted=False, acc_page=1):
    """Build the menu for a specific story."""
    buttons = [
        [
            InlineKeyboardButton("👁 Ghost View", callback_data=f"xstory_ghost_{peer_id}_{story_id}"),
            InlineKeyboardButton("📥 Download", callback_data=f"xstory_dl_{peer_id}_{story_id}")
        ],
        [
            InlineKeyboardButton("❤️ React", callback_data=f"xstory_react_{peer_id}_{story_id}"),
            InlineKeyboardButton("💬 Reply", callback_data=f"xstory_reply_{peer_id}_{story_id}")
        ],
        [
            InlineKeyboardButton(
                "⭐ Un-Whitelist" if is_whitelisted else "⭐ Whitelist", 
                callback_data=f"xstory_wl_{peer_id}_{story_id}_{page}_{acc_page}"
            ),
            InlineKeyboardButton(
                "📂 Un-Archive" if is_archived else "📂 Archive", 
                callback_data=f"xstory_arc_{peer_id}_{story_id}_{page}_{acc_page}"
            )
        ],
        [InlineKeyboardButton("🔙 Back to Feed", callback_data=f"xstory_page_{page}_all_{acc_page}")]
    ]
    return InlineKeyboardMarkup(buttons)

def build_settings_menu():
    """Build the settings menu."""
    buttons = [
        [InlineKeyboardButton("🔔 Auto-Archive: ON", callback_data="xstory_set_auto_off")], # Toggle logic needed
        [InlineKeyboardButton("🔍 OCR Filtering: OFF", callback_data="xstory_set_ocr_on")],
        [InlineKeyboardButton("🗑 Flush Cache", callback_data="xstory_flush_conf")],
        [InlineKeyboardButton("🔙 Back", callback_data="xstory_refresh")]
    ]
    return InlineKeyboardMarkup(buttons)
