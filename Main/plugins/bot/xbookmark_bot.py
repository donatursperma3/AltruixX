# kiro_1.5.5.12
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.

import logging
import uuid
import json
import os
import html
from datetime import datetime
from Main import Altruix
from pyrogram import Client, filters, enums, types
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, 
    InlineQuery, InlineQueryResultArticle, InputTextMessageContent,
    ForceReply
)
from pyrogram.errors import MessageNotModified
from Main.core.decorators import log_errors, iuser_check
from Main.utils.essentials import Essentials

# ============================================================================
# SEARCH STATE CACHE (Ephemeral)
# ============================================================================
SEARCH_PROMPTS = {} # uid -> prompt_msg_id
DASHBOARD_MESSAGES = {} # uid -> dashboard_msg_id
PLUGIN_VERSION = "1.1.24"
ITEMS_PER_PAGE = 5

def get_db():
    db_instance = getattr(Altruix, "db", Altruix.local_db)
    return db_instance.make_collection("BOOKMARKS")

def get_user_button_style(user_id):
    """Retrieves the preferred button style for the user."""
    from Main.utils.file_helpers import get_user_button_style as gubs
    return gubs(user_id)

# ============================================================================
# UI BUILDERS (BOT CONTEXT)
# ============================================================================

async def build_main_menu(uid: int):
    user_style = get_user_button_style(uid)
    text = (
        "<blockquote expandable>"
        "<b>📂 GLOBAL BOOKMARK MANAGER</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Selamat datang di pusat kendali pesan Anda. \nSemua data di sini tersinkronisasi\n"
        "ke seluruh aliansi Altroid-X secara native.\n\n"
        "<i>Silakan pilih menu di bawah:</i>"
        "</blockquote>"
    )
    
    buttons = [
        [
            InlineKeyboardButton("All Bookmark", callback_data="bkm_list_0", style=user_style),
            InlineKeyboardButton("Category", callback_data="bkm_cats", style=user_style)
        ],
        [
            InlineKeyboardButton("Search", callback_data="bkm_search", style=user_style),
            InlineKeyboardButton("Alliance Sync", callback_data="bkm_sync", style=user_style)
        ],
        [
            InlineKeyboardButton("Export", callback_data="bkm_export", style=user_style),
            InlineKeyboardButton("Import", callback_data="bkm_import", style=user_style)
        ],
        [
            InlineKeyboardButton("Help", callback_data="bkm_help", style=user_style),
            InlineKeyboardButton("Close", callback_data="bkm_close", style=user_style)
        ]
    ]
    return text, InlineKeyboardMarkup(buttons)

async def show_bookmark_list(cb: CallbackQuery, page: int = 0):
    uid = cb.from_user.id
    user_style = get_user_button_style(uid)
    db = get_db()
    
    bookmarks = [b async for b in db.find({"owner_id": uid})]
    total = len(bookmarks)
    
    if total == 0:
        text = "<blockquote expandable><b>📂 DAFTAR BOOKMARK</b>\n━━━━━━━━━━━━━━━━━━━━\nAnda belum menyimpan pesan apapun.</blockquote>"
        buttons = [[InlineKeyboardButton("⬅️ Back", callback_data="bkm_main", style=user_style)]]
        return await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

    start = page * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    current_page_items = bookmarks[start:end]
    
    text = f"<blockquote expandable><b>📂 DAFTAR BOOKMARK ({total})</b>\n━━━━━━━━━━━━━━━━━━━━\n<i>Halaman {page + 1}</i></blockquote>\n\n"
    buttons = []
    
    for b in current_page_items:
        title = b.get("title") or (b.get("text")[:30] + "..." if b.get("text") else "Media/Pesan")
        buttons.append([InlineKeyboardButton(f"• {title}", callback_data=f"bkm_view_{b['_id']}", style=user_style)])
    
    # Navigation
    total_pages = (total - 1) // ITEMS_PER_PAGE + 1
    
    # Row 1: Prev | N/M | Next
    nav_row1 = []
    if page > 0:
        nav_row1.append(InlineKeyboardButton("Prev", callback_data=f"bkm_list_{page-1}", style=user_style))
    
    nav_row1.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="bkm_noop", style=user_style))
    
    if end < total:
        nav_row1.append(InlineKeyboardButton("Next", callback_data=f"bkm_list_{page+1}", style=user_style))
    
    buttons.append(nav_row1)
    
    # Row 2: First | Last
    if total_pages > 1:
        nav_row2 = [
            InlineKeyboardButton("First", callback_data="bkm_list_0", style=user_style),
            InlineKeyboardButton("Last", callback_data=f"bkm_list_{total_pages-1}", style=user_style)
        ]
        buttons.append(nav_row2)
    
    buttons.append([InlineKeyboardButton("Back to Menu", callback_data="bkm_main", style=user_style)])
    
    await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def show_bookmark_view(cb: CallbackQuery, bookmark_id: str):
    uid = cb.from_user.id
    user_style = get_user_button_style(uid)
    db = get_db()
    
    try:
        bookmark = await db.find_one({"_id": bookmark_id})
    except Exception as e:
        Altruix.log(f"DEBUG: Error finding bookmark: {e}")
        return await cb.answer("❌ Bookmark tidak ditemukan.", show_alert=True)
        
    if not bookmark:
        return await cb.answer("❌ Data korup atau telah dihapus.", show_alert=True)
    
    text = (
        f"<blockquote expandable>"
        f"<b>📄 Rincian Bookmark</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>ID:</b> <code>{bookmark_id}</code>\n"
        f"<b>Tipe:</b> {bookmark.get('type', 'Unknown')}\n"
        f"<b>Kategori:</b> {bookmark.get('category', 'Lainnya')}\n"
        f"<b>Hashtag:</b> {' '.join(bookmark.get('tags', [])) if bookmark.get('tags') else '-'}\n"
        f"<b>Chat Source:</b> {html.escape(bookmark.get('metadata', {}).get('chat_title', 'Unknown'))}\n"
        f"<b>Sender:</b> {html.escape(bookmark.get('metadata', {}).get('sender_name', 'Unknown'))}\n\n"
        f"<i>Silakan pilih aksi:</i>"
        f"</blockquote>"
    )
    
    # Construct Message Link
    chat_id = bookmark.get("chat_id", 0)
    msg_id = bookmark.get("message_id", 0)
    msg_link = f"https://t.me/c/{str(chat_id).replace('-100', '')}/{msg_id}"
    
    # Build Copy ID button using native CopyTextButton (same pattern as xcmd_logger)
    copy_id_text = str(bookmark_id)
    try:
        from pyrogram.types import CopyTextButton
        copy_id_btn = InlineKeyboardButton("Copy ID", copy_text=CopyTextButton(text=copy_id_text), style=user_style)
    except (ImportError, TypeError):
        try:
            copy_id_btn = InlineKeyboardButton("Copy ID", copy_text=copy_id_text, style=user_style)
        except TypeError:
            # Absolute fallback: just show ID in alert popup
            copy_id_btn = InlineKeyboardButton("Copy ID", callback_data=f"bkm_copyalert_{bookmark_id}", style=user_style)
    
    buttons = [
        [
            InlineKeyboardButton("Broadcast", callback_data=f"bkm_brdcf_{bookmark_id}", style=user_style),
            InlineKeyboardButton("Target Send", callback_data=f"bkm_send_{bookmark_id}", style=user_style)
        ],
        [
            InlineKeyboardButton("Set Category", callback_data=f"bkm_catset_{bookmark_id}", style=user_style),
            InlineKeyboardButton("Delete", callback_data=f"bkm_del_{bookmark_id}", style=user_style)
        ],
        [
            InlineKeyboardButton("Goto Msg", url=msg_link, style=user_style),
            copy_id_btn
        ],
        [InlineKeyboardButton("Back to List", callback_data="bkm_list_0", style=user_style)]
    ]
    
    await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def show_category_menu(cb: CallbackQuery):
    """Displays the list of categories and counts."""
    uid = cb.from_user.id
    user_style = get_user_button_style(uid)
    db = get_db()
    
    # Predefined categories for UI consistency
    standard_cats = ["Text", "Photo", "Video", "Document", "Audio", "Voice Note", "Video Note", "Sticker", "Animation", "Others"]
    
    # Get counts for each category
    counts = {}
    for cat in standard_cats:
        # Compatibility fix: LocalCollection doesn't support count_documents
        count = 0
        async for _ in db.find({"owner_id": uid, "category": cat}):
            count += 1
        counts[cat] = count
    
    text = (
        "<blockquote expandable>"
        "<b>🏷️ KATEGORI BOOKMARK</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Pilih kategori untuk melihat konten spesifik:\n"
        "</blockquote>"
    )
    
    buttons = []
    # Grid: 2 per row
    for i in range(0, len(standard_cats), 2):
        row = []
        cat1 = standard_cats[i]
        row.append(InlineKeyboardButton(f"{cat1} ({counts[cat1]})", callback_data=f"bkm_catfilt_0_{cat1}", style=user_style))
        if i+1 < len(standard_cats):
            cat2 = standard_cats[i+1]
            row.append(InlineKeyboardButton(f"{cat2} ({counts[cat2]})", callback_data=f"bkm_catfilt_0_{cat2}", style=user_style))
        buttons.append(row)
        
    buttons.append([InlineKeyboardButton("Back to Menu", callback_data="bkm_main", style=user_style)])
    
    await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def show_category_items(cb: CallbackQuery, page: int, category: str):
    """Shows paginated bookmarks filtered by category."""
    uid = cb.from_user.id
    user_style = get_user_button_style(uid)
    db = get_db()
    
    bookmarks = [b async for b in db.find({"owner_id": uid, "category": category})]
    total = len(bookmarks)
    
    if total == 0:
        text = f"<blockquote expandable><b>🏷️ CATEGORY: {category.upper()}</b>\n━━━━━━━━━━━━━━━━━━━━\nEmpty.</blockquote>"
        buttons = [[InlineKeyboardButton("⬅️ Back", callback_data="bkm_cats", style=user_style)]]
        return await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

    start = page * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    current_page_items = bookmarks[start:end]
    
    text = f"<blockquote expandable><b>🏷️ CATEGORY: {category.upper()} ({total})</b>\n━━━━━━━━━━━━━━━━━━━━\n<i>Page {page + 1}</i></blockquote>\n\n"
    buttons = []
    
    for b in current_page_items:
        title = b.get("title") or (b.get("text")[:30] + "..." if b.get("text") else "Media/Pesan")
        buttons.append([InlineKeyboardButton(f"• {title}", callback_data=f"bkm_view_{b['_id']}", style=user_style)])
    
    # Navigation
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"bkm_catfilt_{page-1}_{category}", style=user_style))
    if end < total:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"bkm_catfilt_{page+1}_{category}", style=user_style))
    
    if nav: buttons.append(nav)
    
    buttons.append([InlineKeyboardButton("⬅️ Back to Category", callback_data="bkm_cats", style=user_style)])
    
    await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def show_category_assign_menu(cb: CallbackQuery, bookmark_id: str):
    """Menu to assign or change a category for a specific bookmark."""
    uid = cb.from_user.id
    user_style = get_user_button_style(uid)
    standard_cats = ["Text", "Photo", "Video", "Document", "Audio", "Voice Note", "Video Note", "Sticker", "Animation", "Others"]
    
    text = (
        "<blockquote expandable>"
        "<b>🏷️ SET CATEGORY</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Select a new category for this bookmark:\n"
        "</blockquote>"
    )
    
    buttons = []
    for i in range(0, len(standard_cats), 2):
        row = []
        cat1 = standard_cats[i]
        row.append(InlineKeyboardButton(cat1, callback_data=f"bkm_docatset_{bookmark_id}_{cat1}", style=user_style))
        if i+1 < len(standard_cats):
            cat2 = standard_cats[i+1]
            row.append(InlineKeyboardButton(cat2, callback_data=f"bkm_docatset_{bookmark_id}_{cat2}", style=user_style))
        buttons.append(row)
        
    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data=f"bkm_view_{bookmark_id}", style=user_style)])
    
    await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def show_client_selection(cb: CallbackQuery, bookmark_id: str):
    """Lists all active alliance accounts for targeted message transmission."""
    uid = cb.from_user.id
    user_style = get_user_button_style(uid)
    text = (
        f"<blockquote expandable>"
        "<b>👤 SELECT ALLIANCE SENDER</b>\n"
        "Send this message via a specific alliance account:\n"
        "━━━━━━━━━━━━━━━━━━━━"
        "</blockquote>"
    )
    
    buttons = []
    for i, client in enumerate(Altruix.clients):
        if not hasattr(client, 'me') or not client.me: continue
        if not client.is_connected: continue
        
        name = client.me.first_name or f"Session {i+1}"
        buttons.append([InlineKeyboardButton(f"⚔️ {name}", callback_data=f"bkm_snto_{i}_{bookmark_id}", style=user_style)])
    
    buttons.append([InlineKeyboardButton("↩️ Cancel & Back", callback_data=f"bkm_view_{bookmark_id}", style=user_style)])
    
    await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)

async def show_search_results(cb: CallbackQuery, page: int, keyword: str):
    """Displays paginated search results based on a keyword."""
    uid = cb.from_user.id
    user_style = get_user_button_style(uid)
    db = get_db()
    
    # Query: Search in text, tags, and category (Case insensitive)
    query = {
        "owner_id": uid,
        "$or": [
            {"text": {"$regex": keyword, "$options": "i"}},
            {"category": {"$regex": keyword, "$options": "i"}},
            {"tags": {"$regex": keyword, "$options": "i"}}
        ]
    }
    
    bookmarks = [b async for b in db.find(query)]
    total = len(bookmarks)
    
    if total == 0:
        text = (
            f"<blockquote expandable>"
            f"<b>🔍 HASIL PENCARIAN</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Keyword: <code>{keyword}</code>\n\n"
            f"❌ Tidak ada hasil yang relevan."
            f"</blockquote>"
        )
        buttons = [
            [InlineKeyboardButton("🔍 Search Again", callback_data="bkm_search", style=user_style)],
            [InlineKeyboardButton("⬅️ Back", callback_data="bkm_main", style=user_style)]
        ]
        return await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

    start = page * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    current_page_items = bookmarks[start:end]
    
    text = (
        f"<blockquote expandable>"
        f"<b>🔍 HASIL PENCARIAN ({total})</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Keyword: <code>{keyword}</code>\n"
        f"<i>Halaman {page + 1}</i>"
        f"</blockquote>\n\n"
    )
    
    buttons = []
    for b in current_page_items:
        title = b.get("title") or (b.get("text")[:30] + "..." if b.get("text") else "Media/Pesan")
        buttons.append([InlineKeyboardButton(f"• {title}", callback_data=f"bkm_view_{b['_id']}", style=user_style)])
    
    # Navigation
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("Prev", callback_data=f"bkm_srchfilt_{page-1}_{keyword}", style=user_style))
    if end < total:
        nav.append(InlineKeyboardButton("Next", callback_data=f"bkm_srchfilt_{page+1}_{keyword}", style=user_style))
    
    if nav: buttons.append(nav)
    
    buttons.append([InlineKeyboardButton("Search Again", callback_data="bkm_search", style=user_style)])
    buttons.append([InlineKeyboardButton("Back to Menu", callback_data="bkm_main", style=user_style)])
    
    await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def show_help_view(cb: CallbackQuery):
    """Retrieves and displays the help information for the Bookmark Manager plugin."""
    uid = cb.from_user.id
    user_style = get_user_button_style(uid)
    
    plugin_key = "xbookmark_manager"
    help_data = Altruix.cmd_list.get(plugin_key)
    help_msg = Altruix._command_help_message_data.get(plugin_key, "")

    if not help_data:
        text = "<b>❌ Help Error</b>\n━━━━━━━━━━━━━━━━━━━━\nInformasi bantuan tidak ditemukan di sistem."
    else:
        # We assume there is at least one entry for the plugin
        info = help_data[0]
        cmd_info = info.get("cmd_help", {})
        
        cmds = sorted(set(info.get("commands", [])))
        cmd_str = ", ".join([f"<code>{Altruix.prefix_owner_user}{c}</code>" for c in cmds])
        
        version = info.get("version", "1.1.13")
        
        text = (
            f"<blockquote expandable>"
            f"<b>❓ BOOKMARK MANAGER HELP</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>🏷️ Version:</b> <code>v{version}</code>\n"
            f"<b>⌨️ Commands:</b> {cmd_str}\n\n"
            f"<b>📖 Description:</b>\n{cmd_info.get('description', help_msg)}\n\n"
            f"<b>🕹️ Main Dashboard Buttons:</b>\n"
            f"• <b>All Bookmark:</b> Display the list of all saved messages.\n"
            f"• <b>Category:</b> Filter messages by media type.\n"
            f"• <b>Search:</b> Find specific messages via keywords or tags.\n"
            f"• <b>Alliance Sync:</b> Force manual database synchronization.\n\n"
            f"<b>🚀 View / Detail Buttons:</b>\n"
            f"• <b>Broadcast:</b> Ask ALL active bot/userbot accounts in the alliance to simultaneously send the message (For Raiding/Spamming).\n"
            f"• <b>Target Send:</b> Manually select a specific account (Session) to send the message.\n"
            f"• <b>Set Category:</b> Change or put the bookmark into a specific category for easy searching.\n"
            f"• <b>Delete:</b> Permanently remove the bookmark from the global database.\n\n"
            f"<b>💡 Example:</b>\n<code>{cmd_info.get('example', 'N/A')}</code>\n\n"
            f"<i>Use the commands above in any chat for quick interactions.</i>"
            f"</blockquote>"
        )

    buttons = [[InlineKeyboardButton("Back to Menu", callback_data="bkm_main", style=user_style)]]
    await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)

async def show_sync_confirm_view(cb: CallbackQuery):
    """Displays a confirmation menu before triggering Alliance Sync."""
    uid = cb.from_user.id
    user_style = get_user_button_style(uid)
    
    text = (
        "<blockquote expandable>"
        "<b>🔄 KONFIRMASI ALLIANCE SYNC</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Apakah Anda yakin ingin melakukan sinkronisasi modul Bookmark ke seluruh "
        "Aliansi Altroid-X sekarang?\n\n"
        "<i>Tindakan ini akan memastikan seluruh database MongoDB sinkron di semua akun.</i>"
        "</blockquote>"
    )
    
    buttons = [
        [
            InlineKeyboardButton("Yes, Sync", callback_data="bkm_sync_yes", style=user_style),
            InlineKeyboardButton("Cancel", callback_data="bkm_main", style=user_style)
        ]
    ]
    await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)

@Altruix.bot.on_message(filters.reply, group=10)
@iuser_check
@log_errors
async def bookmark_search_input_handler(bot: Client, m: types.Message):
    """Catches user input for bookmark search via ForceReply."""
    if not m.reply_to_message: return
    
    # Identify our special search prompt (check text or caption)
    prompt_content = (m.reply_to_message.text or m.reply_to_message.caption or "")
    if "MASUKKAN KATA KUNCI" in prompt_content:
        Altruix.log(f"🔍 [trace] Search input handler triggered by {m.from_user.id}")
        
        keyword = m.text
        if not keyword:
            Altruix.log(f"⚠️ [trace] No keyword found in message {m.id}")
            return
            
        Altruix.log(f"🔍 [trace] Keyword identified: {keyword}")
        
        # Clean up messages
        try:
            await m.delete()
            await m.reply_to_message.delete()
            Altruix.log(f"🔍 [trace] Cleanup successful.")
        except Exception as ce:
            Altruix.log(f"⚠️ [trace] Cleanup failed (non-critical): {ce}", level=logging.DEBUG)
        
        # 3. Trigger the search results view on the ORIGINAL DASHBOARD
        uid = m.from_user.id
        dash_id = DASHBOARD_MESSAGES.get(uid)
        Altruix.log(f"🔍 [trace] Dashboard ID for {uid}: {dash_id}")
        
        # Simulasikan CallbackQuery untuk memicu show_search_results
        mock_cb = types.CallbackQuery(
            id="0",
            client=bot,
            data=f"bkm_srchfilt_0_{keyword}",
            from_user=m.from_user,
            chat_instance="0",
            message=None
        )
        
        if dash_id:
            try:
                Altruix.log(f"🔍 [trace] Attempting to update dashboard message {dash_id}...")
                # Mock the message object targeting the dashboard
                class MockMessage:
                    def __init__(self, bot, chat_id, msg_id):
                        self.chat = types.Chat(id=chat_id, type=enums.ChatType.PRIVATE)
                        self.id = msg_id
                        self._client = bot
                    async def edit_text(self, *args, **kwargs):
                        return await self._client.edit_message_text(self.chat.id, self.id, *args, **kwargs)
                mock_cb.message = MockMessage(bot, m.chat.id, dash_id)
                await show_search_results(mock_cb, 0, keyword)
                Altruix.log(f"✅ [trace] Dashboard updated successfully with results.")
                
                # Cleanup state
                if uid in DASHBOARD_MESSAGES: del DASHBOARD_MESSAGES[uid]
                return
            except Exception as e:
                Altruix.log(f"❌ [trace] Failed to update original dashboard: {e}", level=logging.ERROR)
        
        # Fallback: Jika dashboard tidak ditemukan, buat pesan baru
        Altruix.log(f"⚠️ [trace] DASHBOARD_ID missing or update failed. Using fallback (new message).")
        text = f"🔍 <b>Hasil Pencarian untuk:</b> <code>{keyword}</code>"
        res_msg = await m.reply(text, parse_mode=enums.ParseMode.HTML)
        mock_cb.message = res_msg
        await show_search_results(mock_cb, 0, keyword)
        Altruix.log(f"✅ [trace] Fallback results message sent.")

@Altruix.bot.on_message(filters.reply & filters.document, group=11)
@iuser_check
@log_errors
async def bookmark_import_file_handler(bot: Client, m: types.Message):
    """Catches JSON file replies for bookmark import."""
    if not m.reply_to_message: return
    
    prompt_content = (m.reply_to_message.text or m.reply_to_message.caption or "")
    if "KIRIM FILE JSON" not in prompt_content:
        return
    
    uid = m.from_user.id
    Altruix.log(f"📥 [trace] Import handler triggered by {uid}")
    
    # Validate file type
    if not m.document.file_name or not m.document.file_name.endswith(".json"):
        return await m.reply("❌ <b>File harus berformat .json</b>", parse_mode=enums.ParseMode.HTML)
    
    # Download file
    status_msg = await m.reply("⏳ <i>Mengunduh dan memproses file...</i>", parse_mode=enums.ParseMode.HTML)
    
    try:
        file_path = await bot.download_media(m, file_name=f"bkm_import_{uid}.json")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            import_data = json.load(f)
        
        os.remove(file_path)
        
        # Validate structure
        bookmarks = import_data.get("bookmarks", [])
        if not bookmarks:
            return await status_msg.edit("❌ <b>File tidak mengandung data bookmark.</b>", parse_mode=enums.ParseMode.HTML)
        
        # Import bookmarks
        db = get_db()
        imported = 0
        skipped = 0
        
        for bk in bookmarks:
            try:
                # Ensure owner_id matches current user
                bk["owner_id"] = uid
                bk_id = bk.get("_id")
                if not bk_id:
                    skipped += 1
                    continue
                
                await db.find_one_and_update({"_id": bk_id}, {"$set": bk}, upsert=True)
                imported += 1
            except Exception as e:
                skipped += 1
                Altruix.log(f"⚠️ [import] Skip bookmark {bk.get('_id', '?')}: {e}", level=logging.WARNING)
        
        # Cleanup messages
        try:
            await m.delete()
            await m.reply_to_message.delete()
        except: pass
        
        # Update dashboard
        dash_id = DASHBOARD_MESSAGES.get(uid)
        if dash_id:
            try:
                text, kb = await build_main_menu(uid)
                await bot.edit_message_text(
                    m.chat.id, dash_id,
                    text + f"\n\n✅ <i>Import selesai: {imported} berhasil, {skipped} dilewati.</i>",
                    reply_markup=kb,
                    parse_mode=enums.ParseMode.HTML
                )
                if uid in DASHBOARD_MESSAGES: del DASHBOARD_MESSAGES[uid]
            except: pass
        
        await status_msg.edit(
            f"✅ <b>Import Selesai!</b>\n"
            f"• Berhasil: <code>{imported}</code>\n"
            f"• Dilewati: <code>{skipped}</code>",
            parse_mode=enums.ParseMode.HTML
        )
        
        # Cleanup state
        if uid in SEARCH_PROMPTS: del SEARCH_PROMPTS[uid]
        
    except json.JSONDecodeError:
        await status_msg.edit("❌ <b>File JSON tidak valid / rusak.</b>", parse_mode=enums.ParseMode.HTML)
    except Exception as e:
        await status_msg.edit(f"❌ <b>Import gagal:</b> <code>{str(e)[:100]}</code>", parse_mode=enums.ParseMode.HTML)
        Altruix.log(f"ERROR: [bkm_import_handler] {e}", level=logging.ERROR)

@Altruix.bot.on_inline_query(filters.regex(r"^bkm_"))
@iuser_check
@log_errors
async def bookmark_assistant_inline(bot: Client, iq: InlineQuery):
    """Handles various bookmark dashboard states via inline query patterns."""
    query = iq.query
    uid = iq.from_user.id
    user_style = get_user_button_style(uid)
    
    Altruix.log(f"DEBUG: [assistant] Inline Query: {query} (from {uid})", level=logging.INFO)
    
    # Check authorization (Simple bypass if iq.from_user.id is authorized elsewhere)
    # 1. Main Dashboard Pattern: bkm_dash_{uid}
    if query.startswith("bkm_dash"):
        text, kb = await build_main_menu(uid)
        title, desc = "📂 Global Bookmark Manager", "Pusat kendali bookmark aliansi Altroid-X."

    # 2. List Pattern: bkm_list_{uid}
    elif query.startswith("bkm_list"):
        db = get_db()
        bookmarks = [b async for b in db.find({"owner_id": uid})]
        total = len(bookmarks)
        if total == 0:
            text = "<blockquote expandable><b>📂 DAFTAR BOOKMARK</b>\n━━━━━━━━━━━━━━━━━━━━\nAnda belum menyimpan pesan apapun.</blockquote>"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="bkm_main", style=user_style)]])
        else:
            text = f"<blockquote expandable><b>📂 DAFTAR BOOKMARK ({total})</b>\n━━━━━━━━━━━━━━━━━━━━\n<i>Halaman 1</i></blockquote>\n\n"
            buttons = []
            for b in bookmarks[:ITEMS_PER_PAGE]:
                tit = b.get("title") or (b.get("text")[:30] + "..." if b.get("text") else "Media/Pesan")
                buttons.append([InlineKeyboardButton(f"• {tit}", callback_data=f"bkm_view_{b['_id']}", style=user_style)])
            if total > ITEMS_PER_PAGE:
                buttons.append([InlineKeyboardButton("Next", callback_data="bkm_list_1", style=user_style)])
            buttons.append([InlineKeyboardButton("Back to Menu", callback_data="bkm_main", style=user_style)])
            kb = InlineKeyboardMarkup(buttons)
        title, desc = "📂 Daftar Bookmark", f"Lihat semua bookmark tersimpan ({total} item)."

    # 3. Category Pattern: bkm_cats_{uid}
    elif query.startswith("bkm_cats"):
        standard_cats = ["Teks", "Foto", "Video", "Dokumen", "Audio", "Pesan Suara", "Pesan Video", "Stiker", "Animasi", "Lainnya"]
        db = get_db()
        counts = {}
        for cat in standard_cats:
            count = 0
            async for _ in db.find({"owner_id": uid, "category": cat}): count += 1
            counts[cat] = count
        text = "<blockquote expandable><b>🏷️ KATEGORI BOOKMARK</b>\n━━━━━━━━━━━━━━━━━━━━\nPilih kategori untuk melihat konten spesifik:\n</blockquote>"
        buttons = []
        for i in range(0, len(standard_cats), 2):
            row = [InlineKeyboardButton(f"{standard_cats[i]} ({counts[standard_cats[i]]})", callback_data=f"bkm_catfilt_0_{standard_cats[i]}", style=user_style)]
            if i+1 < len(standard_cats):
                row.append(InlineKeyboardButton(f"{standard_cats[i+1]} ({counts[standard_cats[i+1]]})", callback_data=f"bkm_catfilt_0_{standard_cats[i+1]}", style=user_style))
            buttons.append(row)
        buttons.append([InlineKeyboardButton("Back to Menu", callback_data="bkm_main", style=user_style)])
        kb = InlineKeyboardMarkup(buttons)
        title, desc = "🏷️ Kategori Bookmark", "Lihat bookmark berdasarkan tipe media."

    # 4. Search Pattern: bkm_search_{uid}_{keyword}
    elif query.startswith("bkm_search"):
        parts = query.split("_")
        keyword = "_".join(parts[3:]) if len(parts) > 3 else "N/A"
        db = get_db()
        import re
        reg = re.compile(keyword, re.IGNORECASE)
        bookmarks = [b async for b in db.find({"owner_id": uid, "$or": [{"text": reg}, {"tags": reg}, {"category": reg}]})]
        total = len(bookmarks)
        if total == 0:
            text = f"<blockquote expandable><b>🔍 SEARCH RESULTS</b>\n━━━━━━━━━━━━━━━━━━━━\nKeyword: <code>{keyword}</code>\n\n❌ No results found.</blockquote>"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("Search Again", callback_data="bkm_search", style=user_style)], [InlineKeyboardButton("Back", callback_data="bkm_main", style=user_style)]])
        else:
            text = f"<blockquote expandable><b>🔍 SEARCH RESULTS ({total})</b>\n━━━━━━━━━━━━━━━━━━━━\nKeyword: <code>{keyword}</code>\n<i>Page 1</i></blockquote>"
            buttons = []
            for b in bookmarks[:ITEMS_PER_PAGE]:
                tit = b.get("title") or (b.get("text")[:30] + "..." if b.get("text") else "Media/Message")
                buttons.append([InlineKeyboardButton(f"• {tit}", callback_data=f"bkm_view_{b['_id']}", style=user_style)])
            if total > ITEMS_PER_PAGE:
                buttons.append([InlineKeyboardButton("Next", callback_data=f"bkm_srchfilt_1_{keyword}", style=user_style)])
            buttons.append([InlineKeyboardButton("Search Again", callback_data="bkm_search", style=user_style)])
            buttons.append([InlineKeyboardButton("Back to Menu", callback_data="bkm_main", style=user_style)])
            kb = InlineKeyboardMarkup(buttons)
        title, desc = f"🔍 Search: {keyword}", f"Filter bookmarks with keyword '{keyword}'."
    else:
        text, kb = await build_main_menu(uid)
        title, desc = "📂 Global Bookmark Manager", "Control Center."

    await iq.answer([InlineQueryResultArticle(id=f"bkm_{uid}_{uuid.uuid4().hex[:8]}", title=title, description=desc, input_message_content=InputTextMessageContent(text, parse_mode=enums.ParseMode.HTML), reply_markup=kb)], cache_time=0, is_personal=True)


@Altruix.bot.on_callback_query(filters.regex(r"^bkm_"))
@iuser_check
@log_errors
async def bookmark_assistant_callbacks(bot: Client, cb: CallbackQuery):
    data = cb.data
    uid = cb.from_user.id
    
    # Identify Userbot Session
    c = next((cl for cl in Altruix.clients if hasattr(cl, "me") and cl.me and cl.me.id == uid), None)
    
    if not c:
        return await cb.answer("❌ Session userbot tidak aktif untuk akun ini.", show_alert=True)

    try:
        if data == "bkm_main":
            text, kb = await build_main_menu(uid)
            await cb.edit_message_text(text, reply_markup=kb)
            
        elif data.startswith("bkm_list_"):
            page = int(data.split("_")[2])
            await show_bookmark_list(cb, page)
            
        elif data.startswith("bkm_view_"):
            parts = data[9:].split("_")
            bid = f"{parts[0]}_{parts[1]}"
            await show_bookmark_view(cb, bid)
            
        elif data == "bkm_close":
            if cb.message:
                await cb.message.delete()
            else:
                await cb.edit_message_text("❌ <b>Dashboard Ditutup</b>")
            
        elif data.startswith("bkm_del_"):
            parts = data[8:].split("_")
            bid = f"{parts[0]}_{parts[1]}"
            db = get_db()
            await db.delete_one({"_id": bid})
            await cb.answer("✅ Bookmark dihapus.", show_alert=True)
            await show_bookmark_list(cb, 0)
            
        elif data == "bkm_sync":
            await show_sync_confirm_view(cb)
            
        elif data == "bkm_export":
            # Export all bookmarks to JSON file
            await cb.answer("📤 Exporting bookmarks...", show_alert=False)
            db = get_db()
            bookmarks = [b async for b in db.find({"owner_id": uid})]
            
            if not bookmarks:
                return await cb.answer("❌ No bookmarks to export.", show_alert=True)
            
            # Serialize to JSON
            export_data = {
                "version": PLUGIN_VERSION,
                "exported_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "owner_id": uid,
                "count": len(bookmarks),
                "bookmarks": bookmarks
            }
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"bookmarks_export_{timestamp}.json"
            
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)
                
                user_style = get_user_button_style(uid)
                await bot.send_document(
                    cb.message.chat.id if cb.message else uid,
                    document=filename,
                    caption=(
                        f"<blockquote expandable>"
                        f"📤 <b>Bookmark Export</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"• Total: <code>{len(bookmarks)}</code> bookmarks\n"
                        f"• Date: <code>{export_data['exported_at']}</code>\n\n"
                        f"<i>Reply this file with the Import button to restore.</i>"
                        f"</blockquote>"
                    ),
                    parse_mode=enums.ParseMode.HTML
                )
                
                os.remove(filename)
                
                # Return to main menu
                text, kb = await build_main_menu(uid)
                await cb.edit_message_text(text + "\n\n✅ <i>Export berhasil dikirim.</i>", reply_markup=kb)
            except Exception as e:
                if os.path.exists(filename):
                    os.remove(filename)
                await cb.answer(f"❌ Export failed: {str(e)[:50]}", show_alert=True)
        
        elif data == "bkm_import":
            # Show import instructions with ForceReply
            user_style = get_user_button_style(uid)
            
            dash_text = (
                "<blockquote expandable>"
                "<b>📥 IMPORT MODE ACTIVE</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "Reply pesan ini dengan file <b>JSON export</b> (.json) yang sebelumnya telah Anda export.\n\n"
                "<i>Dashboard akan kembali normal setelah import selesai atau dibatalkan.</i>"
                "</blockquote>"
            )
            dash_kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel Import", callback_data="bkm_import_cancel", style=user_style)]])
            await cb.edit_message_text(dash_text, reply_markup=dash_kb)
            
            # Record dashboard for state handling
            if cb.message:
                DASHBOARD_MESSAGES[uid] = cb.message.id
            
            # Send ForceReply prompt
            prompt_text = (
                "📥 <b>KIRIM FILE JSON</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "Balas pesan ini dengan file <code>.json</code> hasil export bookmark."
            )
            try:
                if cb.message:
                    prompt_msg = await cb.message.reply_text(prompt_text, reply_markup=ForceReply(selective=True), parse_mode=enums.ParseMode.HTML)
                else:
                    prompt_msg = await bot.send_message(uid, prompt_text, reply_markup=ForceReply(selective=True), parse_mode=enums.ParseMode.HTML)
                
                if prompt_msg:
                    SEARCH_PROMPTS[uid] = prompt_msg.id  # Reuse search state for cleanup
            except Exception as e:
                Altruix.log(f"ERROR: [bkm_import] {e}", level=logging.ERROR)
            
            await cb.answer("📥 Silakan kirim file JSON...", show_alert=False)
        
        elif data == "bkm_import_cancel":
            # Cleanup the ForceReply prompt if it exists
            if uid in SEARCH_PROMPTS:
                try:
                    await bot.delete_messages(uid, SEARCH_PROMPTS[uid])
                    del SEARCH_PROMPTS[uid]
                except: pass
            
            # Return Dashboard to Main Menu
            text, kb = await build_main_menu(uid)
            await cb.edit_message_text(text, reply_markup=kb)
            await cb.answer("✅ Import cancelled.", show_alert=True)
            
        elif data == "bkm_sync_yes":
            # Native Sync logic - just providing user feedback since it's already global
            await cb.answer("🔥 Memulai sinkronisasi Aliansi (Native Local/Global DB)...", show_alert=True)
            text, kb = await build_main_menu(uid)
            # Re-display main menu with updated status if needed
            await cb.edit_message_text(
                text + "\n\n✅ <i>Database berhasil disinkronisasi ke seluruh Aliansi.</i>",
                reply_markup=kb
            )
            
        elif data == "bkm_cats":
            await show_category_menu(cb)
            
        elif data.startswith("bkm_catfilt_"):
            parts = data.split("_")
            page = int(parts[2])
            cat = parts[3]
            await show_category_items(cb, page, cat)
            
        elif data.startswith("bkm_catset_"):
            parts = data[11:].split("_")
            bid = f"{parts[0]}_{parts[1]}"
            await show_category_assign_menu(cb, bid)
            
        elif data.startswith("bkm_docatset_"):
            parts = data[13:].split("_")
            bid = f"{parts[0]}_{parts[1]}"
            cat = "_".join(parts[2:])
            db = get_db()
            await db.update_one({"_id": bid}, {"$set": {"category": cat}})
            await cb.answer(f"✅ Kategori diubah ke: {cat}", show_alert=True)
            await show_bookmark_view(cb, bid)
            
        elif data == "bkm_search":
            # 1. Update Dashboard to 'Search Mode' with Cancel Button
            uid = cb.from_user.id
            user_style = get_user_button_style(uid)
            
            dash_text = (
                "<blockquote expandable>"
                "<b>🔍 MODE PENCARIAN AKTIF</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "Silakan masukkan kata kunci atau tag pada kolom input (Balasan) yang baru saja muncul.\n\n"
                "<i>Dashboard ini akan kembali normal setelah pencarian selesai atau dibatalkan.</i>"
                "</blockquote>"
            )
            dash_kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel Search", callback_data="bkm_search_cancel", style=user_style)]])
            await cb.edit_message_text(dash_text, reply_markup=dash_kb)
            
            # Record dashboard for state handling (safety check for NoneType)
            if cb.message:
                DASHBOARD_MESSAGES[uid] = cb.message.id
            
            # 2. Send the single ForceReply prompt
            prompt_text = (
                "🔎 <b>MASUKKAN KATA KUNCI</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "Balas pesan ini dengan: <i>keyword, tag, atau kategori.</i>"
            )
            try:
                prompt_msg = None
                if cb.message:
                    prompt_msg = await cb.message.reply_text(prompt_text, reply_markup=ForceReply(selective=True), parse_mode=enums.ParseMode.HTML)
                else:
                    prompt_msg = await bot.send_message(cb.from_user.id, prompt_text, reply_markup=ForceReply(selective=True), parse_mode=enums.ParseMode.HTML)
                
                if prompt_msg:
                    SEARCH_PROMPTS[uid] = prompt_msg.id
            except Exception as e:
                Altruix.log(f"ERROR: [bkm_search] {e}", level=logging.ERROR)
            
            await cb.answer("🔎 Silakan ketik kata kunci...", show_alert=False)

        elif data == "bkm_search_cancel":
            # 1. Cleanup the ForceReply prompt if it exists
            uid = cb.from_user.id
            if uid in SEARCH_PROMPTS:
                try:
                    await bot.delete_messages(cb.from_user.id, SEARCH_PROMPTS[uid])
                    del SEARCH_PROMPTS[uid]
                except:
                    pass
            
            # 2. Return Dashboard to Main Menu
            text, kb = await build_main_menu(uid)
            await cb.edit_message_text(text, reply_markup=kb)
            await cb.answer("✅ Search cancelled.", show_alert=True)

        elif data.startswith("bkm_srchfilt_"):
            parts = data.split("_")
            page = int(parts[2])
            keyword = parts[3]
            await show_search_results(cb, page, keyword)
            
        elif data == "bkm_search_noop":
            await cb.answer("🛠️ Fitur pencarian segera hadir.", show_alert=True)
            
        elif data == "bkm_help":
            await show_help_view(cb)
            
        elif data.startswith("bkm_brdcf_"):
            parts = data[10:].split("_")
            bid = f"{parts[0]}_{parts[1]}"
            uid = cb.from_user.id
            
            text = (
                "<blockquote expandable>"
                "<b>⚠️ BROADCAST CONFIRMATION</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "This action will broadcast the message using <b>all active alliance accounts</b>.\n\n"
                "📍 <b>Delivery Destination:</b> The message will be sent simultaneously to your current chat.\n\n"
                "<i>Proceed with alliance broadcast?</i>"
                "</blockquote>"
            )
            buttons = [
                [InlineKeyboardButton("✅ Yes, BCast Now", callback_data=f"bkm_brdrun_{bid}", style=get_user_button_style(uid))],
                [InlineKeyboardButton("❌ Cancel", callback_data=f"bkm_view_{bid}", style=get_user_button_style(uid))]
            ]
            await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
            
        elif data.startswith("bkm_brdrun_"):
            parts = data[11:].split("_")
            bid = f"{parts[0]}_{parts[1]}"
            await cb.answer("🚀 Starting Alliance Broadcast...", show_alert=False)
            
            db = get_db()
            bookmark = await db.find_one({"_id": bid})
            
            if not bookmark:
                return await cb.answer("❌ Bookmark tidak ditemukan.", show_alert=True)
            
            success = 0
            failed = 0
            for client in Altruix.clients:
                try:
                    if not client.is_connected: continue
                    await client.copy_message(
                        chat_id=cb.message.chat.id if cb.message else "me",
                        from_chat_id=bookmark["chat_id"],
                        message_id=bookmark["message_id"]
                    )
                    success += 1
                except:
                    failed += 1
            await cb.answer(f"✅ Alliance Broadcast Selesai!\nBerhasil: {success}\nGagal: {failed}", show_alert=True)
            
        elif data.startswith("bkm_send_"):
            parts = data[9:].split("_")
            bid = f"{parts[0]}_{parts[1]}"
            await show_client_selection(cb, bid)

        elif data.startswith("bkm_snto_"):
            suffix = data[9:]
            parts = suffix.split("_")
            c_idx = int(parts[0])
            bid = f"{parts[1]}_{parts[2]}"
            
            if c_idx >= len(Altruix.clients):
                return await cb.answer("❌ Sesi tidak tersedia.", show_alert=True)
                
            client = Altruix.clients[c_idx]
            db = get_db()
            bookmark = await db.find_one({"_id": bid})
            
            try:
                await client.copy_message(
                    chat_id=cb.message.chat.id if cb.message else "me",
                    from_chat_id=bookmark["chat_id"],
                    message_id=bookmark["message_id"]
                )
                await cb.answer(f"✅ Pesan dikirim via {client.me.first_name}!", show_alert=True)
            except Exception as e:
                await cb.answer(f"❌ Gagal: {str(e)[:50]}", show_alert=True)
            
        elif data.startswith("bkm_copyalert_") or data.startswith("bkm_copy_"):
            # Fallback: show ID in alert popup for manual copy
            prefix = "bkm_copyalert_" if data.startswith("bkm_copyalert_") else "bkm_copy_"
            parts = data[len(prefix):].split("_")
            bid = f"{parts[0]}_{parts[1]}" if len(parts) >= 2 else parts[0]
            await cb.answer(f"📋 Bookmark ID:\n{bid}", show_alert=True)
            
    except Exception as e:
        Altruix.log(f"ERROR: [assistant_cb] {e}", level=logging.ERROR)
        await cb.answer(f"❌ Error: {str(e)[:50]}", show_alert=True)
