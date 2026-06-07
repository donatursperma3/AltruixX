# Main/plugins/userbot/xbookmark_manager.py
# ============================================================================
# ROLE: Senior Python Developer (Telegram Userbot Specialist)
# FRAMEWORK: Pyrogram / Kurigram (Altroid-X Style)
# TASK: Global Bookmark & Message Manager
# DESCRIPTION: 
#   Modular plugin for Altruix to save, manage, and broadcast messages 
#   via multi-client sync. Adheres to specific multi-session standards.
# ============================================================================

import asyncio
import html
import time
import logging
from typing import List, Union

from Main import Altruix
from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait, RPCError, MessageNotModified

from Main.core.decorators import log_errors, iuser_check
from Main.utils.file_helpers import get_user_button_style

# ============================================================================
# SETTINGS & DATABASE HELPERS
# ============================================================================
PLUGIN_VERSION = "1.1.15"
ITEMS_PER_PAGE = 5

def get_db():
    """
    Returns the synchronized database collection for bookmarks.
    """
    Altruix.log("DEBUG: [get_db] Initializing database access...", level=logging.INFO)
    db_instance = getattr(Altruix, "db", Altruix.local_db)
    col = db_instance.make_collection("BOOKMARKS")
    Altruix.log("DEBUG: [get_db] Database access successful.", level=logging.INFO)
    return col

def get_media_type(m: Message):
    """
    Determines the primary media type of a message.
    """
    if m.photo: return "Photo"
    if m.video: return "Video"
    if m.document: return "Document"
    if m.audio: return "Audio"
    if m.voice: return "Voice"
    if m.video_note: return "Video Note"
    if m.sticker: return "Sticker"
    if m.animation: return "Animation"
    if m.text: return "Text"
    return "Other"

# ============================================================================
# UI FUNCTIONS (DASHBOARD & MENUS)
# ============================================================================

async def show_main_menu(c: Client, m: Union[Message, CallbackQuery]):
    """
    Displays the Main Menu of the Bookmark Manager.
    Redirects through Bot Assistant via Inline Result to ensure buttons are visible.
    """
    Altruix.log(f"DEBUG: [show_main_menu] Called for user ID: {c.me.id}", level=logging.INFO)
    
    Altruix.log("DEBUG: [show_main_menu] Building items and styles...", level=logging.INFO)
    user_style = get_user_button_style(c.me.id)
    text = (
        "<b>📂 GLOBAL BOOKMARK MANAGER</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Selamat datang di pusat kendali pesan Anda. \nSemua data di sini tersinkronisasi "
        "ke seluruh aliansi Altroid-X secara native.\n\n"
        "<i>Silakan pilih menu di bawah:</i>"
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
        [
            InlineKeyboardButton("📤 Export", callback_data="bkm_export", style=user_style),
            InlineKeyboardButton("📥 Import", callback_data="bkm_import", style=user_style)
        ],
        [InlineKeyboardButton("❌ Close", callback_data="bkm_close", style=user_style)]
    ]
    
    kb = InlineKeyboardMarkup(buttons)
    
    # Logic for different context (Message vs CallbackQuery)
    if isinstance(m, Message):
        # NEW PATTERN: Use Inline Results via Bot Assistant (From ping.py pattern)
        try:
            bot_username = Altruix.bot_manager.get_bot_username(c.me.id)
            Altruix.log(f"DEBUG: Triggering inline query for @{bot_username}", level=logging.INFO)
            # Query format: bkm_dash_{uid}
            results = await c.get_inline_bot_results(bot_username, f"bkm_dash_{c.me.id}")
            
            await c.send_inline_bot_result(
                chat_id=m.chat.id,
                query_id=results.query_id,
                result_id=results.results[0].id,
                reply_to_message_id=m.reply_to_message.id if m.reply_to_message else m.id
            )
            Altruix.log("DEBUG: Inline dashboard sent successfully", level=logging.INFO)
        except Exception as e:
            Altruix.log(f"DEBUG: Inline pattern failed ({e}). Falling back to direct bot send (Less reliable)...", level=logging.WARNING)
            bot = Altruix.bot_manager.get_bot(c.me.id)
            if bot:
                try:
                    await bot.send_message(chat_id=m.chat.id, text=text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
                except Exception as b_e:
                    Altruix.log(f"DEBUG: Direct bot send failed: {b_e}", level=logging.ERROR)
                    await m.reply_msg(f"❌ <b>Error:</b> Tidak dapat mengirim dashboard. ({b_e})")
            else:
                await m.reply_msg("❌ <b>Error:</b> Bot Assistant tidak aktif.")
    else:
        # Handling for CallbackQuery (edits existing dashboard)
        try:
            await m.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        except MessageNotModified:
            pass
    Altruix.log("DEBUG: show_main_menu interaction handled", level=logging.INFO)


async def show_bookmark_list(c: Client, cb: CallbackQuery, page: int = 0):
    """
    Lists bookmarks with pagination.
    """
    BK_DB = get_db()
    user_style = get_user_button_style(c.me.id)
    all_bkm = []
    async for item in BK_DB.find({}):
        all_bkm.append(item)
    
    # Sort by timestamp desc
    all_bkm.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
    
    total = len(all_bkm)
    start = page * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    current_items = all_bkm[start:end]
    
    text = (
        f"<b>📂 BOOKMARK LIST</b> (Total: {total})\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
    )
    
    if not current_items:
        text += "<i>No bookmarks saved yet. Type <code>.bkm</code> on a message to start.</i>"
    else:
        for i, item in enumerate(current_items, start=start+1):
            snippet = item.get("text", "")[:40].replace("\n", " ")
            if len(snippet) >= 40: snippet += "..."
            icon = "📄" if item['type'] == "Text" else "🎬"
            text += f"{i}. {icon} <b>{item['type']}</b>\n   └ <code>{snippet or '[No Text Content]'}</code>\n"

    buttons = []
    # Item buttons
    for item in current_items:
        snippet = item.get("text", "")[:20] or item['type']
        buttons.append([InlineKeyboardButton(f"📌 {snippet}", callback_data=f"bkm_view_{item['_id']}_{page}", style=user_style)])
    
    # Pagination Logic
    total_pages = (total - 1) // ITEMS_PER_PAGE + 1 if total > 0 else 0
    
    # Row 1: Prev | N/M | Next
    nav_row1 = []
    if page > 0:
        nav_row1.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"bkm_list_{page-1}", style=user_style))
    
    if total_pages > 0:
        nav_row1.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="bkm_noop", style=user_style))
        
    if end < total:
        nav_row1.append(InlineKeyboardButton("Next ➡️", callback_data=f"bkm_list_{page+1}", style=user_style))
    
    if nav_row1:
        buttons.append(nav_row1)
        
    # Row 2: First | Last
    if total_pages > 1:
        nav_row2 = [
            InlineKeyboardButton("⏪ First", callback_data="bkm_list_0", style=user_style),
            InlineKeyboardButton("Last ⏩", callback_data=f"bkm_list_{total_pages-1}", style=user_style)
        ]
        buttons.append(nav_row2)
        
    buttons.append([InlineKeyboardButton("⬅️ Back to Menu", callback_data="bkm_main", style=user_style)])
    
    try:
        await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)
    except MessageNotModified:
        pass

async def show_bookmark_view(c: Client, cb: CallbackQuery, b_id: str, page: int):
    """
    Displays detailed view of a single bookmark.
    """
    BK_DB = get_db()
    user_style = get_user_button_style(c.me.id)
    item = await BK_DB.find_one({"_id": b_id})
    if not item:
        return await cb.answer("❌ Bookmark tidak ditemukan! Mungkin telah dihapus.", show_alert=True)
    
    dt = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(item['timestamp']))
    tags = ", ".join(item.get("tags", [])) or "-"
    
    text = (
        f"<b>📌 RINGKASAN BOOKMARK</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Pengirim:</b> {html.escape(item['metadata']['sender_name'])}\n"
        f"📍 <b>Asal Chat:</b> {html.escape(item['metadata']['chat_title'])}\n"
        f"🎬 <b>Tipe Media:</b> {item['type']}\n"
        f"🏷️ <b>Kategori Tags:</b> <code>{tags}</code>\n"
        f"🕒 <b>Tgl Simpan:</b> <code>{dt}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>KONTEN:</b>\n"
        f"{html.escape(item.get('text', '')[:500])}"
    )
    if len(item.get('text', '')) > 500: text += "..."

    # Construct Message Link
    chat_id = item.get("chat_id", 0)
    msg_id = item.get("message_id", 0)
    msg_link = f"https://t.me/c/{str(chat_id).replace('-100', '')}/{msg_id}"
    
    buttons = [
        [
            InlineKeyboardButton("🚀 Alliance Broadcast", callback_data=f"bkm_cast_all_{b_id}", style=user_style),
            InlineKeyboardButton("👤 Targeted Send", callback_data=f"bkm_select_{b_id}", style=user_style)
        ],
        [
            InlineKeyboardButton("🔗 Goto Msg", url=msg_link, style=user_style),
            InlineKeyboardButton("📋 Copy ID", copy_text=b_id, style=user_style)
        ],
        [
            InlineKeyboardButton("🗑️ Delete Permanently", callback_data=f"bkm_del_{b_id}_{page}", style=user_style),
            InlineKeyboardButton("↩️ Back to List", callback_data=f"bkm_list_{page}", style=user_style)
        ]
    ]
    
    try:
        await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)
    except MessageNotModified:
        pass

# ============================================================================
# COMMAND: .bkm (Quick Save)
# ============================================================================

@Altruix.register_on_cmd(
    ["bkm"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Save a message/media to global bookmarks.",
        "description": (
            "📌 <b>Bookmark Quick Save</b>\n"
            "Use this command by replying to any message or media to save it to the alliance database.\n\n"
            "<b>Features:</b>\n"
            "• Auto media type detection.\n"
            "• Smart text and caption detection.\n"
            "• Category tag support (Example: <code>.bkm #work #important</code>).\n"
            "• Auto sync across all Altroid-X alliance accounts."
        ),
        "usage": ".bkm [tag1] [tag2]",
        "example": ".bkm #project #info",
    }
)
@log_errors
async def save_bookmark_cmd(c: Client, m: Message):
    if not m.reply_to_message:
        return await m.reply_msg("❌ <b>Please reply to the message you want to save!</b>")

    target = m.reply_to_message
    media_type = get_media_type(target)
    
    tags = []
    if m.user_input:
        tags = [t.strip() for t in m.user_input.split() if t.startswith("#")]
    
    # Determine category based on media_type
    category = "Others"
    if media_type == "Photo": category = "Photo"
    elif media_type == "Video": category = "Video"
    elif media_type == "Document": category = "Document"
    elif media_type == "Text": category = "Text"
    elif media_type == "Audio": category = "Audio"
    elif media_type == "Voice": category = "Voice Note"
    elif media_type == "Video Note": category = "Video Note"
    elif media_type == "Sticker": category = "Sticker"
    elif media_type == "Animation": category = "Animation"

    bookmark_id = f"{target.chat.id}_{target.id}"
    doc = {
        "_id": bookmark_id,
        "owner_id": m.from_user.id,
        "chat_id": target.chat.id,
        "message_id": target.id,
        "type": media_type,
        "category": category, # Added category field
        "text": target.text or target.caption or "",
        "tags": tags,
        "timestamp": int(time.time()),
        "metadata": {
            "chat_title": target.chat.title or "Private Chat",
            "sender_name": (target.from_user.first_name if target.from_user else "Unknown"),
            "sender_id": (target.from_user.id if target.from_user else 0),
        }
    }
    
    BK_DB = get_db()
    try:
        await BK_DB.find_one_and_update({"_id": bookmark_id}, {"$set": doc}, upsert=True)
        status_msg = await m.reply_msg(
            f"✅ <b>Saved in Alliance!</b>\n"
            f"📂 <b>Type:</b> {media_type}\n"
            f"🏷️ <b>Tags:</b> {', '.join(tags) if tags else '-'}",
            parse_mode=enums.ParseMode.HTML
        )
        await asyncio.sleep(2)
        await m.delete_if_self()
    except Exception as e:
        await m.reply_msg(f"❌ <b>DB Sync Error:</b> <code>{str(e)}</code>")

# ============================================================================
# COMMAND: .bmmanager (Open Dashboard)
# ============================================================================

@Altruix.register_on_cmd(
    ["bmmanager"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Open Global Bookmark Manager Dashboard.",
        "description": (
            "🚀 <b>Global Bookmark & Alliance Message Manager</b>\n\n"
            "Dashboard interaktif untuk mengelola pesan dan media yang telah disimpan. "
            "Dirancang khusus untuk ekosistem multi-client Altroid-X dengan dukungan sinkronisasi aliansi.\n\n"
            "<b>Cara Kerja (Ping-Pink Pattern):</b>\n"
            "Sistem menggunakan <i>Inline Bot Results</i> untuk mengirim tombol. Ini menjamin tombol muncul di grup mana pun bahkan jika bot asisten tidak ada di sana.\n\n"
            "<b>Fitur Utama:</b>\n"
            "• <b>Multi-Sync:</b> Data tersimpan global di MongoDB/LocalDB.\n"
            "• <b>Alliance Broadcast:</b> Kirim konten via seluruh akun aliansi sekaligus.\n"
            "• <b>Stealth Copy:</b> Menggunakan method copy_message (tanpa label 'forwarded').\n"
            "• <b>Pagination:</b> Penampilan data rapi dengan batas 5 item per halaman.\n\n"
            "<b>Cara Penggunaan:</b>\n"
            "1. Simpan pesan dengan membalas pesan tersebut menggunakan <code>.bkm</code>.\n"
            "2. Buka panel ini dengan <code>.bmmanager</code>.\n"
            "3. Kelola, hapus, atau broadcast konten sesuai kebutuhan."
        ),
        "usage": ".bmmanager",
        "example": ".bmmanager",
    }
)
@log_errors
async def bookmark_manager_cmd(c: Client, m: Message):
    Altruix.log(f"DEBUG: [bmmanager] Triggered by {c.me.id}", level=logging.INFO)
    status_msg = await m.reply_msg("⏳ <i>Menghubungkan ke Aliansi...</i>")
    
    try:
        bot_username = Altruix.bot_manager.get_bot_username(c.me.id)
        # The bot handler is now in Main/plugins/bot/xbookmark_bot.py
        results = await c.get_inline_bot_results(bot_username, f"bkm_dash_{c.me.id}")
        
        await c.send_inline_bot_result(
            chat_id=m.chat.id,
            query_id=results.query_id,
            result_id=results.results[0].id,
            reply_to_message_id=m.reply_to_message.id if m.reply_to_message else m.id
        )
        # Auto-delete loading status after success
        try:
            await status_msg.delete()
        except:
            pass
    except Exception as e:
        Altruix.log(f"ERROR: [bmmanager] {e}", level=logging.ERROR)
        await status_msg.edit(f"❌ <b>Error:</b> Gagal memuat dashboard. ({e})")
        
    await m.delete_if_self()

# ============================================================================
# COMMAND: .bmsearch / .bms (Manual Search)
# ============================================================================

@Altruix.register_on_cmd(
    ["bmsearch"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Manual search for bookmarks via keyword.",
        "description": (
            "🔍 <b>Manual Bookmark Search</b>\n"
            "Mencari pesan tersimpan menggunakan kata kunci, tag, atau kategori secara langsung.\n\n"
            "<b>Cara Penggunaan:</b>\n"
            "<code>.bmsearch [keyword]</code>\n"
            "Contoh: <code>.bmsearch project</code>"
        ),
        "usage": ".bmsearch <keyword>",
        "example": ".bmsearch foto",
    }
)
@log_errors
async def bookmark_search_cmd(c: Client, m: Message):
    if not m.user_input:
        return await m.reply_msg("❓ <b>Gunakan:</b> <code>.bmsearch [keyword]</code>")

    keyword = m.user_input
    status_msg = await m.reply_msg(f"⏳ <i>Mencari '{keyword}' di Aliansi...</i>")
    
    try:
        bot_username = Altruix.bot_manager.get_bot_username(c.me.id)
        # Inline pattern: bkm_search_{uid}_{keyword}
        results = await c.get_inline_bot_results(bot_username, f"bkm_search_{c.me.id}_{keyword}")
        
        await c.send_inline_bot_result(
            chat_id=m.chat.id,
            query_id=results.query_id,
            result_id=results.results[0].id,
            reply_to_message_id=m.reply_to_message.id if m.reply_to_message else m.id
        )
        await status_msg.delete()
    except Exception as e:
        await status_msg.edit(f"❌ <b>Error:</b> Pencarian gagal. ({e})")
    await m.delete_if_self()

# ============================================================================
# COMMAND: .bmlist / .bmcats / .bm (Shortcuts)
# ============================================================================

@Altruix.register_on_cmd(
    ["bmlist"],
    bot_mode_unsupported=True,
    cmd_help={"help": "Directly open bookmark list."}
)
async def bookmark_list_direct_cmd(c: Client, m: Message):
    bot_username = Altruix.bot_manager.get_bot_username(c.me.id)
    results = await c.get_inline_bot_results(bot_username, f"bkm_list_{c.me.id}")
    await c.send_inline_bot_result(m.chat.id, results.query_id, results.results[0].id)
    await m.delete_if_self()

@Altruix.register_on_cmd(
    ["bmcats"],
    bot_mode_unsupported=True,
    cmd_help={"help": "Directly open category menu."}
)
async def bookmark_cats_direct_cmd(c: Client, m: Message):
    bot_username = Altruix.bot_manager.get_bot_username(c.me.id)
    results = await c.get_inline_bot_results(bot_username, f"bkm_cats_{c.me.id}")
    await c.send_inline_bot_result(m.chat.id, results.query_id, results.results[0].id)
    await m.delete_if_self()

@Altruix.register_on_cmd(
    ["bm"],
    bot_mode_unsupported=True,
    cmd_help={"help": "Quick alias for bookmark manager."}
)
async def bookmark_manager_alias_cmd(c: Client, m: Message):
    await bookmark_manager_cmd(c, m)


@Altruix.register_on_cmd(
    ["bmsend"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Send a bookmarked message directly via its ID.",
        "description": (
            "🚀 <b>Manual Targeted Send</b>\n"
            "Mengirim/menduplikasi pesan tersimpan secara instan menggunakan ID Bookmark.\n\n"
            "Berguna untuk mengirim snippet panjang atau integrasi filter dengan cepat tanpa harus membuka dashboard.\n"
            "<b>Cara Penggunaan:</b>\n"
            "<code>.bmsend [bookmark_id]</code>"
        ),
        "usage": ".bmsend <bookmark_id>",
        "example": ".bmsend -10012345678_45",
    }
)
@log_errors
async def bookmark_manual_send_cmd(c: Client, m: Message):
    if not m.user_input:
        return await m.reply_msg("❓ <b>Use:</b> <code>.bmsend [bookmark_id]</code>")

    b_id = m.user_input.strip()
    status_msg = await m.reply_msg(f"⏳ <i>get content...</i>")
    
    BK_DB = get_db()
    item = await BK_DB.find_one({"_id": b_id})
    
    if not item:
        return await status_msg.edit(f"❌ <b>Error:</b> Bookmark with ID <code>{b_id}</code> not found.")
    
    try:
        await c.copy_message(
            chat_id=m.chat.id,
            from_chat_id=item['chat_id'],
            message_id=item['message_id'],
            reply_to_message_id=m.reply_to_message.id if m.reply_to_message else None
        )
        await status_msg.delete()
        await m.delete_if_self()
    except Exception as e:
        await status_msg.edit(f"❌ <b>Failed:</b> <code>{str(e)[:50]}</code>")


async def run_broadcast(c: Client, cb: CallbackQuery, b_id: str):
    """
    Mass broadcasting mechanism via all active sessions.
    Handles disconnected clients and rate limits gracefully.
    """
    BK_DB = get_db()
    item = await BK_DB.find_one({"_id": b_id})
    if not item: 
        return await cb.answer("❌ Error: Meta message not found.")
    
    await cb.answer("🚀 Memulai broadcast via seluruh session Aliansi...", show_alert=False)
    
    success = 0
    fail = 0
    logs = []
    
    # Logic: iterate through all active clients
    for i, client in enumerate(Altruix.clients):
        # Validation checks for Altroid-X ecosystem
        if not hasattr(client, 'me') or not client.me:
            fail += 1
            logs.append(f"Session {i+1}: Not initialized")
            continue
        if not client.is_connected:
            fail += 1
            logs.append(f"Session {i+1}: Disconnected")
            continue
            
        try:
            # Use copy_message (Stealth mode - no forward tag)
            await client.copy_message(
                chat_id=cb.message.chat.id,
                from_chat_id=item['chat_id'],
                message_id=item['message_id']
            )
            success += 1
            await asyncio.sleep(0.5) # Protection delay between clients
        except FloodWait as e:
            # Attempting one-time recovery for short waits
            if e.value < 10:
                await asyncio.sleep(e.value + 1)
                try:
                    await client.copy_message(cb.message.chat.id, item['chat_id'], item['message_id'])
                    success += 1
                except: fail += 1
            else:
                fail += 1
        except Exception as e:
            fail += 1
            Altruix.log(f"Broadcast Failed for {client.me.id}: {e}", level=logging.WARNING)
            
    result_text = (
        f"📢 <b>ALLIANCE BROADCAST COMPLETE</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ <b>Berhasil:</b> <code>{success}</code>\n"
        f"❌ <b>Gagal:</b> <code>{fail}</code>\n"
        f"💠 <b>Status:</b> Operasi Selesai"
    )
    user_style = get_user_button_style(c.me.id)
    try:
        await cb.edit_message_text(
            result_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Kembali ke Utama", callback_data="bkm_main", style=user_style)]]),
            parse_mode=enums.ParseMode.HTML
        )
    except MessageNotModified:
        pass
    except RPCError as e:
        if "MESSAGE_NOT_MODIFIED" in str(e):
            pass
        else:
            raise

async def show_client_selection(c: Client, cb: CallbackQuery, b_id: str):
    """Lists all active alliance accounts for targeted message transmission."""
    user_style = get_user_button_style(c.me.id)
    text = (
        "<b>👤 PILIH PENGIRIM ALIANSI</b>\n"
        "Hubungkan pesan Anda melalui identitas spesifik:\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )
    
    buttons = []
    for i, client in enumerate(Altruix.clients):
        # Check authorization and connection status
        if not hasattr(client, 'me') or not client.me: continue
        if not client.is_connected: continue
        
        name = client.me.first_name or f"Session {i+1}"
        status = "✨" if i == 0 else "⚔️" # Master vs Slave indicator
        buttons.append([InlineKeyboardButton(f"{status} {name}", callback_data=f"bkm_sendto_{i}_{b_id}", style=user_style)])
    
    buttons.append([InlineKeyboardButton("↩️ Batal & Kembali", callback_data=f"bkm_view_{b_id}_0", style=user_style)])
    
    try:
        await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)
    except MessageNotModified:
        pass

async def run_targeted_send(c: Client, cb: CallbackQuery, client_idx: int, b_id: str):
    """Sends a bookmarked message via one specific chosen client."""
    if client_idx >= len(Altruix.clients):
        return await cb.answer("❌ Sesi aliansi tidak tersedia!", show_alert=True)
    
    client = Altruix.clients[client_idx]
    BK_DB = get_db()
    item = await BK_DB.find_one({"_id": b_id})
    if not item: return await cb.answer("❌ Pesan telah terhapus dari sinkronisasi database.", show_alert=True)
    
    try:
        await client.copy_message(
            chat_id=cb.message.chat.id,
            from_chat_id=item['chat_id'],
            message_id=item['message_id']
        )
        await cb.answer(f"✅ Pesan sukses dikirim via {client.me.first_name}!", show_alert=True)
    except RPCError as e:
        await cb.answer(f"❌ Telegram Error: {e.MESSAGE}", show_alert=True)
    except Exception as e:
        await cb.answer(f"❌ Kegagalan Internal: {str(e)}", show_alert=True)

# ============================================================================
# INITIALIZATION LOGGING
# ============================================================================
# Altruix.log(f"Global Bookmark Manager v{PLUGIN_VERSION} initialized successfully.", level=logging.INFO)
