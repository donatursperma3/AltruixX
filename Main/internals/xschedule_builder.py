# Main/internals/xschedule_builder.py
# ============================================================================
# ROLE: UI Builder and Callback Handler for Scheduler
# FRAMEWORK: Altroid-X / Kurigram (Powered by Bot Assistant)
# DESCRIPTION: 
#   Central module for interactive components of the Auto Repeat Scheduler.
#   Handles Inline Queries and Callback Queries via Bot Assistant.
# ============================================================================

import asyncio
import time
import html
import logging
from typing import List, Union
from pyrogram import Client, enums, filters
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, 
    InlineQuery, InlineQueryResultArticle, InputTextMessageContent
)
from pyrogram.errors import FloodWait, RPCError, MessageNotModified

from Main import Altruix
from Main.core.decorators import log_errors, iuser_check
from Main.utils.file_helpers import get_user_button_style
from pyrogram.raw import functions
from datetime import datetime, timedelta, timezone

# Configuration
ITEMS_PER_PAGE = 5
logger = logging.getLogger("altruix.xschedule.builder")

# ============================================================================
# DATABASE ACCESS HELPERS
# ============================================================================
def get_db():
    """Returns the database collection for scheduled messages (Synchronized)."""
    db_instance = getattr(Altruix, "db", Altruix.local_db)
    return db_instance.make_collection("SCHEDULED_MESSAGES")

def get_readable_interval(seconds: int) -> str:
    """Converts seconds into a user-friendly Indonesian string (Menit, Jam, Hari)."""
    if seconds >= 86400: return f"{seconds // 86400} Hari"
    if seconds >= 3600: return f"{seconds // 3600} Jam"
    if seconds >= 60: return f"{seconds // 60} Menit"
    return f"{seconds} Detik"

# ============================================================================
# UI BUILDERS
# ============================================================================

async def build_main_dashboard(owner_id: int):
    """Generates the main entry point dashboard for the Scheduler."""
    DB = get_db()
    user_style = get_user_button_style(owner_id)
    
    # Get Stats
    total_active = await DB.count_documents({"owner_id": owner_id, "is_active": True})
    total_history = await DB.count_documents({"owner_id": owner_id})
    
    text = (
        f"<blockquote expandable>"
        "<b>🚀 SCHEDULER DASHBOARD</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Owner ID:</b> <code>{owner_id}</code>\n"
        f"📊 <b>Total Jadwal Aktif:</b> <code>{total_active}</code>\n"
        f"📜 <b>Total Riwayat:</b> <code>{total_history}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Gunakan menu di bawah untuk mengelola pengulangan pesan Anda.</i>"
        f"</blockquote>"
    )
    
    buttons = [
        [InlineKeyboardButton("📋 List Scheduled Message", callback_data=f"sched_list_0_{owner_id}", style=user_style)],
        [InlineKeyboardButton("☁️ Scheduled Messages (Official)", callback_data=f"sched_cl_cat_{owner_id}", style=user_style)],
        [
            InlineKeyboardButton("📖 Help", callback_data=f"sched_help_{owner_id}", style=user_style),
            InlineKeyboardButton("🔄 Refresh", callback_data=f"sched_main_{owner_id}", style=user_style)
        ],
        [InlineKeyboardButton("❌ Close Dashboard", callback_data="sched_close", style=user_style)]
    ]
    
    return text, InlineKeyboardMarkup(buttons)

async def build_schedule_list(owner_id: int, page: int = 0):
    """Generates a paginated list of scheduled messages for the owner."""
    DB = get_db()
    user_style = get_user_button_style(owner_id)
    
    # Find all active schedules for this owner
    cursor = DB.find({"owner_id": owner_id, "is_active": True})
    all_items = await cursor.to_list(length=100)
    all_items.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
    
    total = len(all_items)
    start = page * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    current_items = all_items[start:end]
    
    text = (
        "<b>📋 DAFTAR JADWAL PESAN</b>\n"
        f"<i>Halaman {page + 1} | Total: {total}</i>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
    )
    
    if not all_items:
        text += "<i>Tidak ada jadwal aktif ditemukan.</i>"
    else:
        for i, res in enumerate(current_items, start=start+1):
            chat = res.get('chat_id')
            interval = res.get('interval_raw')
            max_repeats = res.get('max_repeats', 0)
            current = res.get('current_repeats', 0)
            lim_text = f"{current}/{max_repeats}" if max_repeats > 0 else "♾️"
            msg_snippet = html.escape(res.get('text', '')[:30]).replace("\n", " ")
            text += f"{i}. <b>Chat:</b> <code>{chat}</code>\n   └ <b>Interval:</b> <code>{interval}</code> | <b>Limit:</b> {lim_text} | <i>{msg_snippet}...</i>\n"

    buttons = []
    # Add buttons for each item in the current page
    for res in current_items:
        chat_id = res.get('chat_id')
        max_repeats = res.get('max_repeats', 0)
        current = res.get('current_repeats', 0)
        lim_text = f"{current}/{max_repeats}" if max_repeats > 0 else "♾️"
        snippet = res.get('text', '')[:20] or str(chat_id)
        # Callback: sched_confirm_cancel_<chat_id>_<owner_id>_<page>
        buttons.append([
            InlineKeyboardButton(f"🗑️ Matikan: {snippet}... [{lim_text}]", callback_data=f"sched_confirm_cancel_{chat_id}_{owner_id}_{page}", style=user_style)
        ])
    
    # Pagination Row
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"sched_list_{page-1}_{owner_id}", style=user_style))
    
    total_pages = (total - 1) // ITEMS_PER_PAGE + 1 if total > 0 else 0
    if total_pages > 1:
        nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="sched_noop", style=user_style))
    
    if end < total:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"sched_list_{page+1}_{owner_id}", style=user_style))
    
    if nav:
        buttons.append(nav)
    
    buttons.append([
        InlineKeyboardButton("🔙 Back", callback_data=f"sched_main_{owner_id}", style=user_style),
        InlineKeyboardButton("🔄 Refresh", callback_data=f"sched_list_{page}_{owner_id}", style=user_style)
    ])
    buttons.append([InlineKeyboardButton("❌ Close Menu", callback_data="sched_close", style=user_style)])
    
    return text, InlineKeyboardMarkup(buttons)

async def build_help_menu(owner_id: int):
    """Shows quick help guide for the scheduler."""
    user_style = get_user_button_style(owner_id)
    text = (
        "<b>📖 PANDUAN SCHEDULER</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Sistem ini menggunakan <b>Cloud Scheduling</b> Telegram.\n\n"
        "<b>Format Perintah:</b>\n"
        "<code>.schedulrepeatmsg [chat] [interval] [teks]</code>\n\n"
        "<b>Contoh Interval:</b>\n"
        "• <code>10m</code> = 10 Menit\n"
        "• <code>2h</code> = 2 Jam\n"
        "• <code>1d</code> = 1 Hari\n\n"
        "Pesan akan otomatis dijadwalkan ulang setelah terkirim."
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"sched_main_{owner_id}", style=user_style)]])
    return text, kb

async def build_cloud_category_menu(owner_id: int):
    """Level 1: Main Category Menu for Cloud Manager."""
    user_style = get_user_button_style(owner_id)
    text = (
        f"<blockquote expandable><b>☁️ CLOUD MANAGER: PILIH KATEGORI</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Silakan pilih kategori chat untuk melihat pesan terjadwal secara realtime dari server Telegram.\n"
        f"</blockquote>"
    )
    buttons = [
        [
            InlineKeyboardButton("👥 Groups", callback_data=f"sched_cl_list_groups_all_0_{owner_id}"),
            InlineKeyboardButton("👤 Users", callback_data=f"sched_cl_list_users_all_0_{owner_id}")
        ],
        [
            InlineKeyboardButton("🤖 Bots", callback_data=f"sched_cl_list_bots_all_0_{owner_id}"),
            InlineKeyboardButton("📢 Channels", callback_data=f"sched_cl_list_channels_all_0_{owner_id}")
        ],
        [
            InlineKeyboardButton("📖 Contacts", callback_data=f"sched_cl_list_contacts_all_0_{owner_id}"),
            InlineKeyboardButton("👤 Non-Contacts", callback_data=f"sched_cl_list_noncontacts_all_0_{owner_id}")
        ],
        [
            InlineKeyboardButton("🌐 All Chats", callback_data=f"sched_cl_list_all_all_0_{owner_id}")
        ],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data=f"sched_main_{owner_id}")],
        [InlineKeyboardButton("❌ Close", callback_data="sched_close")]
    ]
    for row in buttons:
        for btn in row: btn.style = user_style
    return text, InlineKeyboardMarkup(buttons)

async def build_cloud_chat_list(owner_id: int, filter_type: str, admin_filter: str = "all", page: int = 0):
    """Level 2: Paginated List of Chats in a category."""
    user_style = get_user_button_style(owner_id)
    CHATS_PER_PAGE = 10
    
    target_client = next((cl for cl in Altruix.clients if hasattr(cl, 'me') and cl.me and cl.me.id == owner_id), None)
    if not target_client: return "❌ Client tidak ditemukan.", None

    text = (
        f"<blockquote expandable><b>📂 DAFTAR CHAT: {filter_type.upper()}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Memindai dialog... Halaman {page+1}\n"
    )
    
    matched_chats = []
    try:
        # Scan dialogs and filter only those with scheduled messages
        async for dialog in target_client.get_dialogs(limit=250):
            chat = dialog.chat
            ctype_str = str(chat.type).lower()
            
            is_private = "private" in ctype_str
            is_group = "group" in ctype_str or "supergroup" in ctype_str
            is_channel = "channel" in ctype_str
            is_bot = "bot" in ctype_str
            is_contact = getattr(chat, "is_contact", False) or getattr(chat, "contact", False)
            
            should_add = False
            if filter_type == "all": should_add = True
            elif filter_type == "users": should_add = is_private
            elif filter_type == "groups": should_add = is_group
            elif filter_type == "channels": should_add = is_channel
            elif filter_type == "bots": should_add = is_bot
            elif filter_type == "contacts": should_add = is_private and is_contact
            elif filter_type == "noncontacts": should_add = is_private and not is_contact

            if should_add:
                try:
                    # CHECK FOR SCHEDULED MESSAGES
                    schedules = await target_client.get_scheduled_messages(chat.id)
                    if schedules:
                        matched_chats.append((chat, len(schedules)))
                except RPCError:
                    continue
                except Exception:
                    continue
                
            await asyncio.sleep(0.02) # Micro-delay for stability
    except Exception as e:
        logger.error(f"Error listing chats: {e}")

    total = len(matched_chats)
    start = page * CHATS_PER_PAGE
    end = start + CHATS_PER_PAGE
    current_chats = matched_chats[start:end]

    buttons = []
    for chat, count in current_chats:
        title = (chat.title or chat.first_name or str(chat.id))[:20]
        buttons.append([InlineKeyboardButton(f"📁 {title} : {count}msg", callback_data=f"sched_cl_msg_{chat.id}_{filter_type}_{admin_filter}_{page}_{owner_id}")])

    # Navigation
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"sched_cl_list_{filter_type}_{admin_filter}_{page-1}_{owner_id}"))
    if end < total:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"sched_cl_list_{filter_type}_{admin_filter}_{page+1}_{owner_id}"))
    if nav: buttons.append(nav)

    buttons.append([InlineKeyboardButton("🔙 Back to Category", callback_data=f"sched_cl_cat_{owner_id}")])
    
    for row in buttons:
        for btn in row: btn.style = user_style
        
    text += f"Ditemukan: {total} chat berisi pesan terjadwal.</blockquote>"
    return text, InlineKeyboardMarkup(buttons)

async def build_cloud_message_view(owner_id: int, chat_id: int, filter_type: str, admin_filter: str, page: int):
    """Level 3: List of Scheduled Messages as Buttons."""
    user_style = get_user_button_style(owner_id)
    target_client = next((cl for cl in Altruix.clients if hasattr(cl, 'me') and cl.me and cl.me.id == owner_id), None)
    if not target_client: return "❌ Client tidak ditemukan.", None

    try:
        chat = await target_client.get_chat(chat_id)
        chat_title = chat.title or chat.first_name or str(chat_id)
        schedules = await target_client.get_scheduled_messages(chat_id)
    except Exception as e:
        return f"❌ Gagal mengambil data: {str(e)}", None

    text = (
        f"<blockquote expandable><b>🕒 PESAN TERJADWAL: {html.escape(chat_title)}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Klik pada salah satu pesan di bawah untuk mengelola atau melakukan tindakan cepat.\n"
        f"</blockquote>"
    )

    buttons = []
    if not schedules:
        text = "<i>Tidak ada pesan terjadwal di chat ini.</i>"
    else:
        for sm in schedules:
            msg_text = (sm.text or sm.caption or "[Media]").replace("\n", " ")[:20]
            sched_time = sm.date.strftime("%H:%M (%d/%m)")
            # callback: sched_cl_det_<chat_id>_<msg_id>_<type>_<adm>_<pg>_<owner_id>
            buttons.append([InlineKeyboardButton(
                f"🕒 {sched_time} | {msg_text}...",
                callback_data=f"sched_cl_det_{chat_id}_{sm.id}_{filter_type}_{admin_filter}_{page}_{owner_id}"
            )])

    buttons.append([InlineKeyboardButton("🔄 Refresh", callback_data=f"sched_cl_msg_{chat_id}_{filter_type}_{admin_filter}_{page}_{owner_id}")])
    buttons.append([InlineKeyboardButton("🔙 Back to List Chat", callback_data=f"sched_cl_list_{filter_type}_{admin_filter}_{page}_{owner_id}")])
    
    for row in buttons:
        for btn in row: btn.style = user_style
        
    return text, InlineKeyboardMarkup(buttons)

async def build_cloud_message_panel(owner_id: int, chat_id: int, msg_id: int, filter_type: str, admin_filter: str, page: int):
    """Level 4: Control Panel for a specific message."""
    user_style = get_user_button_style(owner_id)
    target_client = next((cl for cl in Altruix.clients if hasattr(cl, 'me') and cl.me and cl.me.id == owner_id), None)
    if not target_client: return "❌ Client tidak ditemukan.", None

    try:
        # We need to find the message among scheduled ones
        schedules = await target_client.get_scheduled_messages(chat_id)
        target_msg = next((m for m in schedules if m.id == msg_id), None)
        if not target_msg: return "❌ Pesan tidak ditemukan atau sudah terkirim.", None
        
        chat = await target_client.get_chat(chat_id)
        chat_title = chat.title or chat.first_name or str(chat_id)
        
        msg_text = target_msg.text or target_msg.caption or "[Media/No Text]"
        sched_time = target_msg.date.strftime("%d %b %Y, %H:%M:%S")
        
        text = (
            f"<blockquote expandable><b>🛠️ KONTROL PESAN TERJADWAL</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 <b>Chat:</b> {html.escape(chat_title)}\n"
            f"🕒 <b>Jadwal:</b> <code>{sched_time}</code>\n\n"
            f"📝 <b>Isi Pesan:</b>\n<i>{html.escape(msg_text[:200])}</i>"
            f"{'...' if len(msg_text) > 200 else ''}\n"
            f"</blockquote>"
        )
        
        # Action Buttons
        # cl_act_<action>_<chat_id>_<msg_id>_<type>_<adm>_<pg>_<owner_id>
        prefix = f"sched_cl_act"
        suffix = f"{chat_id}_{msg_id}_{filter_type}_{admin_filter}_{page}_{owner_id}"
        
        buttons = [
            [
                InlineKeyboardButton("🚀 Send Now", callback_data=f"{prefix}_send_{suffix}"),
                InlineKeyboardButton("🗑️ Delete", callback_data=f"{prefix}_del_{suffix}")
            ],
            [
                InlineKeyboardButton("📅 Reschedule", callback_data=f"sched_cl_res_{suffix}"),
                InlineKeyboardButton("✏️ Edit", callback_data=f"{prefix}_edit_{suffix}")
            ],
            [

                InlineKeyboardButton("📝 Copy to Saved", callback_data=f"{prefix}_copy_{suffix}"),
                InlineKeyboardButton("📁 Copy to LOG", callback_data=f"{prefix}_log_{suffix}")
            ],
            [
                InlineKeyboardButton("🔄 Refresh", callback_data=f"sched_cl_det_{chat_id}_{msg_id}_{filter_type}_{admin_filter}_{page}_{owner_id}"),
                InlineKeyboardButton("🔙 Back", callback_data=f"sched_cl_msg_{chat_id}_{filter_type}_{admin_filter}_{page}_{owner_id}")
            ]
        ]
        
        for row in buttons:
            for btn in row: btn.style = user_style
            
        return text, InlineKeyboardMarkup(buttons)
    except Exception as e:
        return f"❌ Error: {str(e)}", None

async def build_cloud_reschedule_menu(owner_id: int, chat_id: int, msg_id: int, filter_type: str, admin_filter: str, page: int):
    """Level 5: Dedicated Reschedule Menu."""
    user_style = get_user_button_style(owner_id)
    target_client = next((cl for cl in Altruix.clients if hasattr(cl, 'me') and cl.me and cl.me.id == owner_id), None)
    if not target_client: return "❌ Client tidak ditemukan.", None

    try:
        schedules = await target_client.get_scheduled_messages(chat_id)
        target_msg = next((m for m in schedules if m.id == msg_id), None)
        if not target_msg: return "❌ Pesan tidak ditemukan.", None
        
        chat = await target_client.get_chat(chat_id)
        sched_time = target_msg.date.strftime("%d %b %Y, %H:%M:%S")
        
        text = (
            f"<blockquote expandable><b>📅 PENGATURAN ULANG JADWAL</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 <b>Chat:</b> {html.escape(chat.title or chat.first_name)}\n"
            f"🕒 <b>Jadwal Saat Ini:</b> <code>{sched_time}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Silakan pilih penyesuaian waktu di bawah ini.\n"
            f"</blockquote>"
        )
        
        prefix = f"sched_cl_act"
        suffix = f"{chat_id}_{msg_id}_{filter_type}_{admin_filter}_{page}_{owner_id}"
        
        buttons = [
            [
                InlineKeyboardButton("-5 Hari", callback_data=f"{prefix}_res-5d_{suffix}"),
                InlineKeyboardButton("+5 Hari", callback_data=f"{prefix}_res5d_{suffix}")
            ],
            [
                InlineKeyboardButton("-1 Hari", callback_data=f"{prefix}_res-1d_{suffix}"),
                InlineKeyboardButton("+1 Hari", callback_data=f"{prefix}_res1d_{suffix}")
            ],
            [
                InlineKeyboardButton("-5 Jam", callback_data=f"{prefix}_res-5h_{suffix}"),
                InlineKeyboardButton("+5 Jam", callback_data=f"{prefix}_res5h_{suffix}")
            ],
            [
                InlineKeyboardButton("-1 Jam", callback_data=f"{prefix}_res-1h_{suffix}"),
                InlineKeyboardButton("+1 Jam", callback_data=f"{prefix}_res1h_{suffix}")
            ],
            [
                InlineKeyboardButton("-5 Menit", callback_data=f"{prefix}_res-5m_{suffix}"),
                InlineKeyboardButton("+5 Menit", callback_data=f"{prefix}_res5m_{suffix}")
            ],
            [
                InlineKeyboardButton("-1 Menit", callback_data=f"{prefix}_res-1m_{suffix}"),
                InlineKeyboardButton("+1 Menit", callback_data=f"{prefix}_res1m_{suffix}")
            ],
            [InlineKeyboardButton("🔙 Back to Message Control", callback_data=f"sched_cl_det_{chat_id}_{msg_id}_{filter_type}_{admin_filter}_{page}_{owner_id}")]
        ]
        
        for row in buttons:
            for btn in row: btn.style = user_style
            
        return text, InlineKeyboardMarkup(buttons)
    except Exception as e:
        return f"❌ Error: {str(e)}", None

async def build_cloud_dashboard(owner_id: int, filter_type: str = "all", admin_filter: str = "all", page: int = 0):
    """
    Generates an interactive dashboard to view cloud-scheduled messages with pagination.
    """
    user_style = get_user_button_style(owner_id)
    CHATS_PER_PAGE_CLOUD = 5
    
    # Resolve Account Name
    account_name = str(owner_id)
    target_client = None
    for cl in Altruix.clients:
        if hasattr(cl, 'me') and cl.me and cl.me.id == owner_id:
            target_client = cl
            first = cl.me.first_name or ""
            last = cl.me.last_name or ""
            account_name = f"{first} {last}".strip() or str(owner_id)
            break
    
    filter_labels = {
        "all": "🌐 All",
        "users": "👤 Users",
        "contacts": "📖 Contacts",
        "noncontacts": "👤 Non-Contacts",
        "groups": "👥 Groups",
        "channels": "📢 Channels",
        "bots": "🤖 Bots"
    }
    
    admin_labels = {
        "all": "All",
        "admin": "Admin Only",
        "nonadmin": "Non-Admin"
    }
    
    text = (
        f"<blockquote expandable><b>☁️ CLOUD SCHEDULE MANAGER</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Account:</b> {html.escape(account_name)}\n"
        f"🔍 <b>Filter:</b> <b>{filter_labels.get(filter_type, filter_type.title())}</b>\n"
        f"🛠️ <b>Admin:</b> <b>{admin_labels.get(admin_filter, 'All')}</b>\n"
        f"📄 <b>Halaman:</b> <code>{page + 1}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
    )
    
    found_schedules = []
    scanned_count = 0
    if target_client:
        try:
            # Increased scan limit to 250 for better coverage
            async for dialog in target_client.get_dialogs(limit=250):
                scanned_count += 1
                chat = dialog.chat
                chat_type = chat.type
                ctype_str = str(chat_type).lower()
                
                # Jeda mikro agar tidak dianggap spam oleh Telegram (FloodWait Prevention)
                await asyncio.sleep(0.05)
                
                # Cooling period setiap 20 chat
                if scanned_count % 20 == 0:
                    await asyncio.sleep(0.5)

                # Robust type identification
                is_private = "private" in ctype_str
                is_group = "group" in ctype_str or "supergroup" in ctype_str
                is_channel = "channel" in ctype_str
                is_bot = "bot" in ctype_str
                is_contact = getattr(chat, "is_contact", False) or getattr(chat, "contact", False)
                
                # Filtering Logic
                should_check = False
                if filter_type == "all": 
                    should_check = True
                elif filter_type == "users": 
                    should_check = is_private
                elif filter_type == "groups": 
                    should_check = is_group
                elif filter_type == "channels": 
                    should_check = is_channel
                elif filter_type == "bots": 
                    should_check = is_bot
                elif filter_type == "contacts":
                    should_check = is_private and is_contact
                elif filter_type == "noncontacts":
                    should_check = is_private and not is_contact

                # Additional Admin Filter for Groups
                if should_check and is_group and admin_filter != "all":
                    try:
                        # SUPER FAST: Check cached privileges first
                        if chat.privileges:
                            is_admin = True
                        else:
                            # Fallback if cache is empty or it's a basic group
                            member = await target_client.get_chat_member(chat.id, owner_id)
                            is_admin = member.status in (enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER)
                        
                        if admin_filter == "admin" and not is_admin: should_check = False
                        elif admin_filter == "nonadmin" and is_admin: should_check = False
                    except Exception:
                        if admin_filter == "admin": should_check = False

                if should_check:
                    try:
                        schedules = await target_client.get_scheduled_messages(chat.id)
                        if schedules:
                            found_schedules.append((chat, schedules))
                    except FloodWait as fw:
                        await asyncio.sleep(fw.value + 1)
                        # Retry once after wait
                        schedules = await target_client.get_scheduled_messages(chat.id)
                        if schedules: found_schedules.append((chat, schedules))
                    except RPCError as re:
                        # Silently skip if admin rights are required to view history
                        if "CHAT_ADMIN_REQUIRED" in str(re):
                            continue
                        logger.debug(f"RPCError checking cloud for {chat.id}: {re}")
                        continue
        except Exception as e:
            logger.error(f"Error scanning cloud for user {owner_id}: {e}", exc_info=True)
            text += f"⚠️ <b>Error Scanning:</b> <code>{str(e)}</code>\n"

    total_found = len(found_schedules)
    start = page * CHATS_PER_PAGE_CLOUD
    end = start + CHATS_PER_PAGE_CLOUD
    current_page_chats = found_schedules[start:end]

    if not found_schedules:
        text += "<i>Tidak ada pesan terjadwal ditemukan di Cloud.</i>"
    else:
        text += f"<i>Menampilkan {start+1}-{min(end, total_found)} dari {total_found} chat ditemukan.</i>\n\n"
        for chat, msgs in current_page_chats:
            chat_title = chat.title or f"{chat.first_name} {chat.last_name or ''}".strip()
            text += f"📍 <b>{html.escape(chat_title[:20])}</b> (<code>{chat.id}</code>)\n"
            for i, sm in enumerate(msgs, 1):
                msg_text = html.escape((sm.text or sm.caption or "[Media]").replace("\n", " ")[:30])
                sched_time = sm.date.strftime("%d/%m %H:%M")
                text += f"  {i}. 🕒 <code>{sched_time}</code> | <i>{msg_text}...</i>\n"
            text += "\n"
    
    text += f"━━━━━━━━━━━━━━━━━━━━\n"
    text += f"📊 <b>Scanned:</b> <code>{scanned_count} chats</code>\n"
    text += "</blockquote>"
    
    # Admin Cycle Logic
    next_admin = {"all": "admin", "admin": "nonadmin", "nonadmin": "all"}[admin_filter]
    
    # Build Keyboard
    buttons = [
        [
            InlineKeyboardButton(f"{'✅ ' if filter_type == 'all' else ''}All", callback_data=f"sched_cloud_all_{admin_filter}_0_{owner_id}"),
            InlineKeyboardButton(f"{'✅ ' if filter_type == 'users' else ''}Users", callback_data=f"sched_cloud_users_{admin_filter}_0_{owner_id}")
        ],
        [
            InlineKeyboardButton(f"{'✅ ' if filter_type == 'groups' else ''}Groups", callback_data=f"sched_cloud_groups_{admin_filter}_0_{owner_id}"),
            InlineKeyboardButton(f"{'✅ ' if filter_type == 'channels' else ''}Channels", callback_data=f"sched_cloud_channels_{admin_filter}_0_{owner_id}")
        ],
        [
            InlineKeyboardButton(f"{'✅ ' if filter_type == 'bots' else ''}Bots", callback_data=f"sched_cloud_bots_{admin_filter}_0_{owner_id}"),
            InlineKeyboardButton(f"{'✅ ' if filter_type == 'contacts' else ''}Contacts", callback_data=f"sched_cloud_contacts_{admin_filter}_0_{owner_id}")
        ],
        [
            InlineKeyboardButton(f"{'✅ ' if filter_type == 'noncontacts' else ''}Non-Contacts", callback_data=f"sched_cloud_noncontacts_{admin_filter}_0_{owner_id}"),
            InlineKeyboardButton(f"🛠️ Admin: {admin_labels[admin_filter]}", callback_data=f"sched_cloud_{filter_type}_{next_admin}_0_{owner_id}")
        ]
    ]
    
    # Navigation Row for Cloud
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"sched_cloud_{filter_type}_{admin_filter}_{page-1}_{owner_id}"))
    
    if end < total_found:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"sched_cloud_{filter_type}_{admin_filter}_{page+1}_{owner_id}"))
    
    if nav:
        buttons.append(nav)

    buttons.append([
        InlineKeyboardButton("🔄 Refresh Scan", callback_data=f"sched_cloud_{filter_type}_{admin_filter}_{page}_{owner_id}"),
        InlineKeyboardButton("🔙 Back", callback_data=f"sched_main_{owner_id}")
    ])
    buttons.append([InlineKeyboardButton("❌ Close Dashboard", callback_data="sched_close")])
    
    # Apply user style
    for row in buttons:
        for btn in row:
            btn.style = user_style
            
    return text, InlineKeyboardMarkup(buttons)

# ============================================================================
# BOT ASSISTANT HANDLERS
# ============================================================================

@Altruix.bot.on_inline_query(filters.regex(r"^sched_(main|list)(?:_(\d+))?"))
@iuser_check
@log_errors
async def scheduler_inline_handler(c: Client, iq: InlineQuery):
    """
    Handles inline queries from userbots to display the scheduler dashboard.
    Query pattern: sched_main_<owner_id> or sched_list_<owner_id>
    """
    mode = iq.matches[0].group(1)
    owner_id = int(iq.matches[0].group(2)) if iq.matches[0].group(2) else iq.from_user.id
    
    if mode == "main":
        text, kb = await build_main_dashboard(owner_id)
        title = "Scheduler Main Menu"
        desc = "Kelola pengaturan pusat pengulangan pesan."
    else:
        text, kb = await build_schedule_list(owner_id, page=0)
        title = "Scheduler List Manager"
        desc = "Lihat dan matikan jadwal aktif."
    
    results = [
        InlineQueryResultArticle(
            id=f"sched_{mode}_{owner_id}",
            title=title,
            description=desc,
            input_message_content=InputTextMessageContent(
                text, parse_mode=enums.ParseMode.HTML
            ),
            reply_markup=kb,
            thumb_url="https://telegra.ph/file/0c6f5a3e1445790c9b0e2.jpg"
        )
    ]
    await iq.answer(results, cache_time=0, is_personal=True)

@Altruix.bot.on_callback_query(filters.regex(r"^sched_"))
@iuser_check
@log_errors
async def scheduler_callback_handler(c: Client, cb: CallbackQuery):
    """Processes all interactions with the scheduler inline menus."""
    data = cb.data.split("_")
    action = data[1] # main, list, help, confirm, cancel, close
    
    DB = get_db()
    
    try:
        if action == "main":
            owner_id = int(data[2])
            text, kb = await build_main_dashboard(owner_id)
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            
        elif action == "list":
            # sched_list_<page>_<owner_id>
            page = int(data[2])
            owner_id = int(data[3])
            text, kb = await build_schedule_list(owner_id, page)
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            
        elif action == "help":
            owner_id = int(data[2])
            text, kb = await build_help_menu(owner_id)
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            
        elif action == "confirm":
            # sched_confirm_cancel_<chat_id>_<owner_id>_<page>
            chat_id = int(data[3])
            owner_id = int(data[4])
            page = int(data[5])
            user_style = get_user_button_style(owner_id)
            
            text = f"❓ <b>Konfirmasi Pembatalan</b>\nApakah Anda yakin ingin mematikan pengulangan untuk Chat ID <code>{chat_id}</code>?"
            kb = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Ya, Matikan", callback_data=f"sched_cancel_{chat_id}_{owner_id}_{page}", style=user_style),
                    InlineKeyboardButton("❌ Tidak", callback_data=f"sched_list_{page}_{owner_id}", style=user_style)
                ]
            ])
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)

        elif action == "cancel":
            # sched_cancel_<chat_id>_<owner_id>_<page>
            chat_id = int(data[2])
            owner_id = int(data[3])
            page = int(data[4])
            
            await DB.update_one(
                {"owner_id": owner_id, "chat_id": chat_id},
                {"$set": {"is_active": False}}
            )
            
            target_client = None
            for client in Altruix.clients:
                if client.me and client.me.id == owner_id:
                    target_client = client
                    break
            
            if target_client:
                try:
                    scheduled_msgs = await target_client.get_scheduled_messages(chat_id)
                    if scheduled_msgs:
                        await target_client.delete_scheduled_messages(chat_id, [m.id for m in scheduled_msgs])
                except Exception as e:
                    logger.warning(f"Could not delete scheduled messages for {owner_id} in {chat_id}: {e}")
            
            await cb.answer("✅ Pengulangan Berhasil Dimatikan!", show_alert=True)
            text, kb = await build_schedule_list(owner_id, page)
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)

        elif action == "close":
            await cb.message.delete()
            
        elif action == "cl":
            # Correctly handle cl_cat, cl_list, cl_msg
            # data structure: ['sched', 'cl', 'cat/list/msg', ...]
            sub_action = data[2]
            text, kb = "❌ Error: Konten tidak ditemukan.", None
            await cb.answer("🔍 Memproses...", show_alert=False)
            
            if sub_action == "cat":
                owner_id = int(data[3])
                text, kb = await build_cloud_category_menu(owner_id)
            elif sub_action == "list":
                # cl_list_<type>_<admin>_<page>_<owner_id>
                filter_type, admin_filter, page, owner_id = data[3], data[4], int(data[5]), int(data[6])
                text, kb = await build_cloud_chat_list(owner_id, filter_type, admin_filter, page)
            elif sub_action == "msg":
                # cl_msg_<chat_id>_<type>_<admin>_<page>_<owner_id>
                chat_id, filter_type, admin_filter, page, owner_id = int(data[3]), data[4], data[5], int(data[6]), int(data[7])
                text, kb = await build_cloud_message_view(owner_id, chat_id, filter_type, admin_filter, page)
            elif sub_action == "det":
                # cl_det_<chat_id>_<msg_id>_<type>_<adm>_<pg>_<owner_id>
                chat_id, msg_id, filter_type, admin_filter, page, owner_id = int(data[3]), int(data[4]), data[5], data[6], int(data[7]), int(data[8])
                text, kb = await build_cloud_message_panel(owner_id, chat_id, msg_id, filter_type, admin_filter, page)
            elif sub_action == "res":
                # cl_res_<chat_id>_<msg_id>_<type>_<adm>_<pg>_<owner_id>
                chat_id, msg_id, filter_type, admin_filter, page, owner_id = int(data[3]), int(data[4]), data[5], data[6], int(data[7]), int(data[8])
                text, kb = await build_cloud_reschedule_menu(owner_id, chat_id, msg_id, filter_type, admin_filter, page)
            elif sub_action == "act":
                # cl_act_<sub_act>_<chat_id>_<msg_id>_<type>_<adm>_<pg>_<owner_id>
                sub_act, chat_id, msg_id, filter_type, admin_filter, page, owner_id = data[3], int(data[4]), int(data[5]), data[6], data[7], int(data[8]), int(data[9])
                
                target_client = next((cl for cl in Altruix.clients if cl.me and cl.me.id == owner_id), None)
                if not target_client:
                    await cb.answer("❌ Client tidak ditemukan.", show_alert=True)
                    return

                try:
                    if sub_act == "send":
                        await target_client.send_scheduled_messages(chat_id, [msg_id])
                        await cb.answer("🚀 Pesan segera dikirim!", show_alert=True)
                        # Go back to message list
                        text, kb = await build_cloud_message_view(owner_id, chat_id, filter_type, admin_filter, page)
                    elif sub_act == "del":
                        await target_client.delete_scheduled_messages(chat_id, [msg_id])
                        await cb.answer("🗑️ Pesan berhasil dihapus!", show_alert=True)
                        # Go back to message list
                        text, kb = await build_cloud_message_view(owner_id, chat_id, filter_type, admin_filter, page)
                    elif sub_act == "copy":
                        # Copy content to saved messages
                        schedules = await target_client.get_scheduled_messages(chat_id)
                        target_msg = next((m for m in schedules if m.id == msg_id), None)
                        if target_msg:
                            await target_msg.copy("me")
                            await cb.answer("📝 Salinan dikirim ke Saved Messages!", show_alert=True)
                        else:
                            await cb.answer("❌ Gagal menyalin pesan.", show_alert=True)
                        text, kb = await build_cloud_message_panel(owner_id, chat_id, msg_id, filter_type, admin_filter, page)
                    elif sub_act == "edit":
                        # For now, "Edit" means providing the content to the user to resend
                        schedules = await target_client.get_scheduled_messages(chat_id)
                        target_msg = next((m for m in schedules if m.id == msg_id), None)
                        if target_msg:
                            content = target_msg.text or target_msg.caption or ""
                            await target_client.send_message(
                                "me", 
                                f"🛠️ <b>MODE EDIT PESAN</b>\n\n"
                                f"Silakan salin teks di bawah ini, edit sesuai keinginan, lalu jadwalkan ulang:\n\n"
                                f"<code>{html.escape(content)}</code>"
                            )
                            await cb.answer("✏️ Teks dikirim ke Saved Messages untuk diedit!", show_alert=True)
                        else:
                            await cb.answer("❌ Gagal mengambil konten.", show_alert=True)
                        text, kb = await build_cloud_message_panel(owner_id, chat_id, msg_id, filter_type, admin_filter, page)
                    elif sub_act == "log":
                        # Send to Log Group
                        schedules = await target_client.get_scheduled_messages(chat_id)
                        target_msg = next((m for m in schedules if m.id == msg_id), None)
                        if target_msg:
                            # Try to find Log Group ID from Altruix config or user DB
                            log_group = getattr(Altruix, "LOG_ID", None) or getattr(Altruix, "LOG_GROUP", None)
                            if not log_group:
                                # Fallback to search in user settings if available
                                await cb.answer("⚠️ Grup Log tidak ditemukan di konfigurasi!", show_alert=True)
                            else:
                                await target_msg.copy(log_group)
                                await cb.answer(f"📁 Berhasil dikirim ke Log Group!", show_alert=True)
                        else:
                            await cb.answer("❌ Gagal mengambil pesan.", show_alert=True)
                        text, kb = await build_cloud_message_panel(owner_id, chat_id, msg_id, filter_type, admin_filter, page)
                    elif sub_act.startswith("res"):
                        # Reschedule with flexible values (STABLE TELEGRAM METHOD)
                        schedules = await target_client.get_scheduled_messages(chat_id)
                        target_msg = next((m for m in schedules if m.id == msg_id), None)
                        if target_msg:
                            # Use UTC for all calculations to sync with Telegram
                            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
                            current_sched = target_msg.date.replace(tzinfo=None)
                            
                            new_date = current_sched
                            if sub_act == "res1h": new_date += timedelta(hours=1)
                            elif sub_act == "res-1h": new_date -= timedelta(hours=1)
                            elif sub_act == "res5h": new_date += timedelta(hours=5)
                            elif sub_act == "res-5h": new_date -= timedelta(hours=5)
                            elif sub_act == "res1d": new_date += timedelta(days=1)
                            elif sub_act == "res-1d": new_date -= timedelta(days=1)
                            elif sub_act == "res5d": new_date += timedelta(days=5)
                            elif sub_act == "res-5d": new_date -= timedelta(days=5)
                            elif sub_act == "res1m": new_date += timedelta(minutes=1)
                            elif sub_act == "res-1m": new_date -= timedelta(minutes=1)
                            elif sub_act == "res5m": new_date += timedelta(minutes=5)
                            elif sub_act == "res-5m": new_date -= timedelta(minutes=5)
                            
                            # Safety: Telegram requires scheduled messages to be at least 10-30s in future
                            if new_date <= now_utc + timedelta(seconds=15):
                                await cb.answer("⚠️ Waktu baru terlalu dekat atau di masa lalu!", show_alert=True)
                                return
                            
                            try:
                                # PROFESSIONAL METHOD: Edit the schedule_date directly
                                # This keeps the same message ID and is much faster
                                peer = await target_client.resolve_peer(chat_id)
                                await target_client.invoke(
                                    functions.messages.EditMessage(
                                        peer=peer,
                                        id=msg_id,
                                        schedule_date=int(new_date.timestamp())
                                    )
                                )
                                await cb.answer(f"📅 Jadwal diperbarui ke: {new_date.strftime('%H:%M (%d/%b)')}", show_alert=True)
                            except Exception as e:
                                # Fallback to copy+delete if edit fails (e.g. peer issues)
                                logger.warning(f"EditMessage failed, falling back to copy+delete: {e}")
                                await target_msg.copy(chat_id, schedule_date=new_date)
                                await target_client.delete_scheduled_messages(chat_id, [msg_id])
                                await cb.answer("📅 Jadwal diperbarui (Method: Re-sent)!", show_alert=True)
                            
                            # Refresh message list
                            text, kb = await build_cloud_message_view(owner_id, chat_id, filter_type, admin_filter, page)
                        else:
                            await cb.answer("❌ Gagal mengatur ulang jadwal.", show_alert=True)
                except Exception as e:
                    await cb.answer(f"❌ Error: {str(e)}", show_alert=True)
                    return
            
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)

        elif action == "cloud":
            # For backward compatibility, redirect to Level 1
            owner_id = int(data[-1])
            text, kb = await build_cloud_category_menu(owner_id)
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)

        elif action == "noop":
            await cb.answer()
            
    except MessageNotModified:
        pass
    except Exception as e:
        logger.error(f"Scheduler Callback Error: {e}", exc_info=True)
        await cb.answer(f"❌ Error: {str(e)}", show_alert=True)
