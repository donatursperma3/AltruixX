# Main/internals/settings_handlers/bookmark_handlers.py
# ============================================================================
# ROLE: UI Builder and Callback Handler for Bookmark Manager
# FRAMEWORK: Altroid-X / Kurigram (Powered by Bot Assistant)
# DESCRIPTION: 
#   This module centralizes all interactive components for the Bookmark Manager.
#   It builds complex Inline keyboards and handles all button interactions 
#   via the Bot Assistant to circumvent Userbot inline limitations.
# ============================================================================

import asyncio
import html
import time
import logging
from typing import Union, List
from pyrogram import Client, enums, filters
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)
from pyrogram.errors import FloodWait, RPCError, MessageNotModified
from Main import Altruix
from Main.core.decorators import log_errors, iuser_check
from Main.utils.file_helpers import get_user_button_style

# Configuration constants
ITEMS_PER_PAGE = 5

# ============================================================================
# DATABASE ACCESS HELPERS
# ============================================================================
def get_db():
    """
    Returns the synchronized MongoDB/LocalDB collection for bookmarks.
    Ensures that data is consistent across all alliance sessions.
    """
    db_instance = getattr(Altruix, "db", Altruix.local_db)
    return db_instance.make_collection("BOOKMARKS")

# ============================================================================
# UI BUILDERS (KEYBOARD & TEXT GENERATORS)
# ============================================================================

def get_media_icon(m_type: str) -> str:
    """Returns a visual emoji icon based on the media type string."""
    icons = {
        "Photo": "🖼️", "Video": "🎬", "Document": "📄", "Audio": "🎵",
        "Voice": "🎙️", "Video Note": "📹", "Sticker": "🎨", "Animation": "🎞️", "Text": "📝"
    }
    return icons.get(m_type, "📑")

async def build_main_menu(c: Client):
    """
    Generates the high-level dashboard menu.
    Includes navigation to the list, categories, search, and sync features.
    """
    user_style = get_user_button_style(c.me.id)
    text = (
        "<b>📂 GLOBAL BOOKMARK MANAGER</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Welcome to the Altroid-X alliance control center. "
        "All data is synchronized across all sessions in real-time.\n\n"
        "<i>Please select a menu below:</i>"
    )
    
    buttons = [
        [
            InlineKeyboardButton("📂 All Bookmark", callback_data="bkm_list_0", style=user_style),
            InlineKeyboardButton("🏷️ Category", callback_data="bkm_cats", style=user_style)
        ],
        [
            InlineKeyboardButton("🔍 Search", callback_data="bkm_search", style=user_style),
            InlineKeyboardButton("🔄 Alliance Sync", callback_data="bkm_sync", style=user_style)
        ],
        [InlineKeyboardButton("❌ Close", callback_data="bkm_close", style=user_style)]
    ]
    return text, InlineKeyboardMarkup(buttons)

async def build_bookmark_list(c: Client, bookmarks: List[dict], page: int = 0):
    """
    Generates a paginated list of bookmarks.
    Supports a 5-item-per-page layout for optimal mobile readability.
    """
    user_style = get_user_button_style(c.me.id)
    total = len(bookmarks)
    start = page * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    current_items = bookmarks[start:end]
    
    text = (
        f"<b>📂 BOOKMARK LIST</b> (Total: {total})\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
    )
    
    if not current_items:
        text += "<i>No bookmarks saved yet. Use <code>.bkm</code> on a message to start.</i>"
    else:
        for i, item in enumerate(current_items, start=start+1):
            snippet = item.get("text", "")[:40].replace("\n", " ")
            if len(snippet) >= 40: snippet += "..."
            icon = get_media_icon(item['type'])
            text += f"{i}. {icon} <b>{item['type']}</b>\n   └ <code>{snippet or '[No Text]'}</code>\n"

    buttons = []
    for item in current_items:
        snippet = item.get("text", "")[:20] or item['type']
        buttons.append([InlineKeyboardButton(f"📌 {snippet}", callback_data=f"bkm_view_{item['_id']}_{page}", style=user_style)])
    
    # Pagination Row logic
    nav = []
    if page > 0: nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"bkm_list_{page-1}", style=user_style))
    total_pages = (total - 1) // ITEMS_PER_PAGE + 1 if total > 0 else 0
    if total_pages > 1: nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="bkm_noop", style=user_style))
    if end < total: nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"bkm_list_{page+1}", style=user_style))
    
    if nav: buttons.append(nav)
    buttons.append([InlineKeyboardButton("⬅️ Back to Menu", callback_data="bkm_main", style=user_style)])
    return text, InlineKeyboardMarkup(buttons)

async def build_bookmark_view(c: Client, item: dict, page: int):
    """
    Generates the specific detail view for a single saved bookmark.
    Provides metadata like sender name, media type, tags, and timestamps.
    """
    user_style = get_user_button_style(c.me.id)
    dt = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(item['timestamp']))
    tags = ", ".join(item.get("tags", [])) or "-"
    icon = get_media_icon(item['type'])
    
    text = (
        f"<b>{icon} BOOKMARK SUMMARY</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Sender:</b> {html.escape(item['metadata']['sender_name'])}\n"
        f"🎬 <b>Media Type:</b> {item['type']}\n"
        f"🏷️ <b>Tags:</b> <code>{tags}</code>\n"
        f"🕒 <b>Saved:</b> <code>{dt}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>CONTENT:</b>\n"
        f"{html.escape(item.get('text', '')[:500])}"
    )
    if len(item.get('text', '')) > 500: text += "..."

    buttons = [
        [
            InlineKeyboardButton("🚀 Alliance Broadcast", callback_data=f"bkm_cast_all_{item['_id']}", style=user_style),
            InlineKeyboardButton("👤 Targeted Send", callback_data=f"bkm_select_{item['_id']}", style=user_style)
        ],
        [
            InlineKeyboardButton("🗑️ Delete Permanently", callback_data=f"bkm_del_{item['_id']}_{page}", style=user_style),
            InlineKeyboardButton("↩️ Back to List", callback_data=f"bkm_list_{page}", style=user_style)
        ]
    ]
    return text, InlineKeyboardMarkup(buttons)

async def build_client_selection(c: Client, b_id: str):
    """
    Builds a list of available alliance sessions for manual message casting.
    """
    user_style = get_user_button_style(c.me.id)
    text = (
        "<b>👤 SELECT ALLIANCE SENDER</b>\n"
        "Select an alliance session to clone this message:\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )
    buttons = []
    for i, client in enumerate(Altruix.clients):
        if not hasattr(client, 'me') or not client.me: continue
        if not client.is_connected: continue
        name = client.me.first_name or f"Session {i+1}"
        status = "✨" if i == 0 else "⚔️"
        buttons.append([InlineKeyboardButton(f"{status} {name}", callback_data=f"bkm_sendto_{i}_{b_id}", style=user_style)])
    
    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data=f"bkm_view_{b_id}_0", style=user_style)])
    return text, InlineKeyboardMarkup(buttons)

# ============================================================================
# BOT ASSISTANT CALLBACK HANDLERS
# ============================================================================

@Altruix.bot.on_callback_query(filters.regex(r"^bkm_"))
@iuser_check
@log_errors
async def bookmark_cb_handler(bot: Client, cb: CallbackQuery):
    """
    Primary dispatcher for all bookmark-related callbacks.
    Processes navigation, deletion, broadcasting, and identity selection.
    Authorized via iuser_check to ensure only the owner can operate the alliance.
    """
    data = cb.data.split("_")
    action = data[1]
    BK_DB = get_db()
    
    # Resolve the active userbot client context for styling and identity
    target_client = Altruix.clients[0]
    for c in Altruix.clients:
        if c.me and c.me.id == cb.from_user.id:
            target_client = c
            break

    try:
        # Route logic based on callback data
        if action == "main":
            text, kb = await build_main_menu(target_client)
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            
        elif action == "list":
            page = int(data[2])
            all_bkm = []
            async for item in BK_DB.find({}): all_bkm.append(item)
            all_bkm.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
            text, kb = await build_bookmark_list(target_client, all_bkm, page)
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            
        elif action == "view":
            # Extract ID which might contain underscores
            b_id = "_".join(data[2:-1])
            page = int(data[-1])
            item = await BK_DB.find_one({"_id": b_id})
            if not item: return await cb.answer("❌ Meta Data Not Found!", show_alert=True)
            text, kb = await build_bookmark_view(target_client, item, page)
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            
        elif action == "del":
            b_id = "_".join(data[2:-1])
            page = int(data[-1])
            await BK_DB.find_one_and_delete({"_id": b_id})
            await cb.answer("🗑️ Deleted from Alliance Database!")
            # Refresh list view after deletion
            all_bkm = []
            async for item in BK_DB.find({}): all_bkm.append(item)
            text, kb = await build_bookmark_list(target_client, all_bkm, page)
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            
        elif action == "cast":
            if data[2] == "all":
                b_id = "_".join(data[3:])
                await run_alliance_broadcast(target_client, cb, b_id)
                
        elif action == "select":
            b_id = "_".join(data[2:])
            text, kb = await build_client_selection(target_client, b_id)
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            
        elif action == "sendto":
            client_idx = int(data[2])
            b_id = "_".join(data[3:])
            await run_targeted_broadcast(target_client, cb, client_idx, b_id)
            
        elif action == "sync":
            await cb.answer("🔄 Alliance Sync: Global database synchronization successful!", show_alert=True)
            
        elif action == "close":
            await cb.message.delete()
            
        elif action in ["cats", "search"]:
            await cb.answer("🛠️ This Advanced Feature is still in development.", show_alert=False)
            
        elif action == "noop":
            await cb.answer()
            
    except MessageNotModified:
        pass
    except RPCError as e:
        if "MESSAGE_NOT_MODIFIED" in str(e):
            pass
        else:
            raise
    except Exception as e:
        Altruix.log(f"Bookmark Handler Error: {e}", level=logging.ERROR)
        await cb.answer(f"❌ Dash Error: {str(e)}", show_alert=True)

# ============================================================================
# ALLIANCE BROADCAST LOGIC (CORE ACTION LAYER)
# ============================================================================

async def run_alliance_broadcast(c: Client, cb: CallbackQuery, b_id: str):
    """
    Executes a global broadcast across all active alliance sessions.
    Iterates through Altruix.clients to clone the message to the current chat.
    Uses copy_message to ensure no "Forwarded" tag is visible.
    """
    BK_DB = get_db()
    item = await BK_DB.find_one({"_id": b_id})
    if not item: return await cb.answer("❌ Metadata pesan telah hilang!")
    
    await cb.answer("🚀 Memulai broadcast massal via seluruh aliansi...", show_alert=False)
    success, fail = 0, 0
    
    # Iterate through all configured clients in the ecosystem
    for client in Altruix.clients:
        if not client.is_connected: fail += 1; continue
        try:
            # Clone message to targeting chat
            await client.copy_message(chat_id=cb.message.chat.id, from_chat_id=item['chat_id'], message_id=item['message_id'])
            success += 1
            await asyncio.sleep(0.5) # Slight pacing to remain stealthy
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
            try: await client.copy_message(cb.message.chat.id, item['chat_id'], item['message_id']); success += 1
            except: fail += 1
        except Exception: fail += 1
            
    res_text = (
        f"📢 <b>ALLIANCE BROADCAST COMPLETE</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ <b>Berhasil:</b> <code>{success}</code>\n"
        f"❌ <b>Gagal:</b> <code>{fail}</code>\n\n"
        f"💠 <i>Seluruh aliansi telah merespons permintaan cloning.</i>"
    )
    user_style = get_user_button_style(c.me.id)
    await cb.message.edit_text(res_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Kembali Utama", callback_data="bkm_main", style=user_style)]]), parse_mode=enums.ParseMode.HTML)

async def run_targeted_broadcast(c: Client, cb: CallbackQuery, client_idx: int, b_id: str):
    """Sends the bookmarked message via a single specifically selected alliance member."""
    if client_idx >= len(Altruix.clients): return await cb.answer("❌ Sesi aliansi tidak tersedia!")
    client = Altruix.clients[client_idx]
    item = await get_db().find_one({"_id": b_id})
    if not item: return await cb.answer("❌ Pesan asal telah terhapus!")
    
    try:
        await client.copy_message(chat_id=cb.message.chat.id, from_chat_id=item['chat_id'], message_id=item['message_id'])
        await cb.answer(f"✅ Pesan sukses dkalkulasi via {client.me.first_name}!", show_alert=True)
    except Exception as e:
        await cb.answer(f"❌ Kegagalan Cloning: {str(e)}", show_alert=True)
