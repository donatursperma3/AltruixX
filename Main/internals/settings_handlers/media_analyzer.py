# Main/internals/settings_handlers/media_analyzer.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
# All rights reserved.

import asyncio
import time
from pyrogram import enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from Main import Altruix
from Main.utils.file_helpers import get_user_button_style

# Default constants
DEFAULT_SCOPE = "all"
DEFAULT_TYPE = "all"
DEFAULT_D_CHAT = 0.0
DEFAULT_D_MSG = 0.0
DEFAULT_REPORT_LOG = "split"

# Logic Mapping
SCOPE_LIST = ["all", "groups", "users", "channels", "bots"]
TYPE_LIST = ["all", "photo", "video", "document", "gif", "audio", "voice"]

async def get_ma_settings(user_id):
    """Fetch Media Analyzer settings for a specific user."""
    scope = await Altruix.config.get_env(f"MA_SCOPE_{user_id}") or DEFAULT_SCOPE
    
    mtype_str = await Altruix.config.get_env(f"MA_TYPE_{user_id}") or DEFAULT_TYPE
    mtype_list = mtype_str.split(",") if mtype_str else [DEFAULT_TYPE]
    if not mtype_list: mtype_list = ["all"]
    
    d_chat = float(await Altruix.config.get_env(f"MA_D_CHAT_{user_id}") or DEFAULT_D_CHAT)
    d_msg = float(await Altruix.config.get_env(f"MA_D_MSG_{user_id}") or DEFAULT_D_MSG)
    
    b_size = int(await Altruix.config.get_env(f"MA_B_SIZE_{user_id}") or 50)
    b_delay = float(await Altruix.config.get_env(f"MA_B_DELAY_{user_id}") or 10.0)
    b_msg_size = int(await Altruix.config.get_env(f"MA_B_MSG_SIZE_{user_id}") or 40)
    b_msg_delay = float(await Altruix.config.get_env(f"MA_B_MSG_DELAY_{user_id}") or 60.0)
    
    admin_filter = await Altruix.config.get_env(f"MA_ADMIN_FILTER_{user_id}") or "all"
    
    # Blacklisted chat IDs (CSV format)
    blacklist_str = await Altruix.config.get_env(f"MA_BLACKLIST_{user_id}") or ""
    blacklist = [int(p) for p in blacklist_str.split(",") if p.replace('-', '').isdigit()]
    
    report_log = await Altruix.config.get_env(f"MA_REPORT_LOG_{user_id}") or DEFAULT_REPORT_LOG
    
    return {
        "scope": scope,
        "type": mtype_list,
        "delay_chat": d_chat,
        "delay_msg": d_msg,
        "batch_size": b_size,
        "batch_delay": b_delay,
        "batch_msg_size": b_msg_size,
        "batch_msg_delay": b_msg_delay,
        "admin_filter": admin_filter,
        "blacklist": blacklist,
        "report_log": report_log
    }

async def save_ma_settings(user_id, settings):
    """Save Media Analyzer settings back to the database."""
    await Altruix.config.sync_env_to_db(f"MA_SCOPE_{user_id}", settings["scope"], upsert=True)
    await Altruix.config.sync_env_to_db(f"MA_TYPE_{user_id}", ",".join(settings["type"]), upsert=True)
    await Altruix.config.sync_env_to_db(f"MA_D_CHAT_{user_id}", str(settings["delay_chat"]), upsert=True)
    await Altruix.config.sync_env_to_db(f"MA_D_MSG_{user_id}", str(settings["delay_msg"]), upsert=True)
    await Altruix.config.sync_env_to_db(f"MA_B_SIZE_{user_id}", str(settings["batch_size"]), upsert=True)
    await Altruix.config.sync_env_to_db(f"MA_B_DELAY_{user_id}", str(settings["batch_delay"]), upsert=True)
    await Altruix.config.sync_env_to_db(f"MA_B_MSG_SIZE_{user_id}", str(settings["batch_msg_size"]), upsert=True)
    await Altruix.config.sync_env_to_db(f"MA_B_MSG_DELAY_{user_id}", str(settings["batch_msg_delay"]), upsert=True)
    await Altruix.config.sync_env_to_db(f"MA_ADMIN_FILTER_{user_id}", settings.get("admin_filter", "all"), upsert=True)
    await Altruix.config.sync_env_to_db(f"MA_BLACKLIST_{user_id}", ",".join(map(str, settings.get("blacklist", []))), upsert=True)
    await Altruix.config.sync_env_to_db(f"MA_REPORT_LOG_{user_id}", settings.get("report_log", "split"), upsert=True)

async def get_ma_status_text(user_id):
    """Compiles the descriptive text for the Media Analyzer Dashboard."""
    settings = await get_ma_settings(user_id)
    
    mode_str = "🐢 Stealth (Slow)" if settings["delay_msg"] > 0 else "🚀 Bulk (Fast)"
    type_str = ", ".join([t.capitalize() for t in settings['type']])
    
    # Account name resolution
    account_name = str(user_id)
    for cl in Altruix.clients:
        if cl.me and cl.me.id == user_id:
            account_name = (cl.me.first_name or "") + (" " + cl.me.last_name if cl.me.last_name else "")
            account_name = account_name.strip() or str(user_id)
            break

    text = (
        f"<blockquote expandable>"
        f"📊 <b>MEDIA ANALYZER DASHBOARD</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Account:</b> <code>{account_name}</code>\n"
        f"<b>Status:</b> 🏷️ <code>Ready to analyze</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Scope:</b> <code>{settings['scope'].capitalize()}</code>\n"
        f"<b>Types:</b> <code>{type_str}</code>\n"
        f"<b>Mode:</b> <code>{mode_str}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Delay Chat:</b> <code>{settings['delay_chat']}s</code>\n"
        f"<b>Delay Msg:</b> <code>{settings['delay_msg']}s</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Batch/Chat:</b> <code>{settings['batch_size']}ch</code> | <b>B-Delay:</b> <code>{int(settings['batch_delay']/60)}m</code>\n"
        f"<b>Batch/Msg:</b> <code>{settings['batch_msg_size']}ms</code> | <b>BM-Delay:</b> <code>{int(settings['batch_msg_delay']/60)}m</code>\n"
        f"<b>Admin Filter:</b> <code>{settings.get('admin_filter', 'all').upper()}</code>\n"
        f"<b>Report Log:</b> <code>{settings.get('report_log', 'split').upper()}</code>\n"
        f"<b>Blacklisted:</b> <code>{len(settings.get('blacklist', []))} chats</code>\n"
        f"</blockquote>\n"
        f"<i>Adjust settings below and tap Start to begin.</i>"
    )
    return text

def get_ma_kb(user_id, settings):
    """Constructs the Media Analyzer Inline Keyboard."""
    kb = []
    user_style = get_user_button_style(user_id)
    
    # Row 1: Scope & Type (Submenu Access)
    kb.append([
        InlineKeyboardButton(f"Scope: {settings['scope'].capitalize()}", f"ma_cycle_scope_{user_id}", style=user_style),
        InlineKeyboardButton(f"Type: {len(settings['type'])} selected", f"ma_filtermenu_{user_id}", style=user_style)
    ])
    
    # Row 2: Delay Configuration Access
    kb.append([
        InlineKeyboardButton(f"Delay/Chat: {settings['delay_chat']}s", f"ma_menu_dchat_{user_id}", style=user_style),
        InlineKeyboardButton(f"Delay/Msg: {settings['delay_msg']}s", f"ma_menu_dmsg_{user_id}", style=user_style)
    ])
    
    # Row: Admin Filter
    adm_f = settings.get("admin_filter", "all").upper()
    kb.append([
        InlineKeyboardButton(f"Adm Filter: {adm_f}", f"ma_toggleadmin_{user_id}", style=user_style)
    ])
    
    # Row: Blacklist Management
    bl_count = len(settings.get("blacklist", []))
    rep_log = settings.get("report_log", "split").upper()
    kb.append([
        InlineKeyboardButton(f"List Blacklist: ({bl_count})", f"ma_bl_list_{user_id}", style=user_style),
        InlineKeyboardButton(f"Log: {rep_log}", f"ma_reportlog_{user_id}", style=user_style)
    ])
    
    # Row 3: Batch Configuration Access
    batch_str = f"Batch: {settings['batch_size']}chats / {settings['batch_msg_size']}msgs"
    kb.append([
        InlineKeyboardButton(batch_str, f"ma_menu_batch_{user_id}", style=user_style)
    ])
    
    # Row 4: Main Action & Close
    kb.append([
        InlineKeyboardButton("START SCAN", f"ma_start_{user_id}", style=user_style)
    ])
    
    kb.append([
        InlineKeyboardButton("Refresh", f"ma_refresh_{user_id}", style=user_style),
        InlineKeyboardButton("Close", f"ma_close_{user_id}", style=user_style)
    ])
    
    return InlineKeyboardMarkup(kb)

def get_ma_submenu_kb(user_id, settings, menu_type):
    """Generates the inline keyboard for a specific setting submenu (Delays)."""
    kb = []
    user_style = get_user_button_style(user_id)
    
    if menu_type == "dchat":
        val = settings["delay_chat"]
        kb.append([InlineKeyboardButton(f"Delay/Chat: {val}s", "ma_noop", style=user_style)])
        kb.append([
            InlineKeyboardButton("-1s", f"ma_set_dchat_m1_{user_id}", style=user_style),
            InlineKeyboardButton("+1s", f"ma_set_dchat_p1_{user_id}", style=user_style)
        ])
    elif menu_type == "dmsg":
        val = settings["delay_msg"]
        kb.append([InlineKeyboardButton(f"Delay/Msg: {val}s", "ma_noop", style=user_style)])
        kb.append([
            InlineKeyboardButton("-0.5s", f"ma_set_dmsg_m05_{user_id}", style=user_style),
            InlineKeyboardButton("+0.5s", f"ma_set_dmsg_p05_{user_id}", style=user_style)
        ])
    
    kb.append([InlineKeyboardButton("Back", f"ma_refresh_{user_id}", style=user_style)])
    return InlineKeyboardMarkup(kb)

def get_ma_filter_submenu_text(settings):
    """Generates text for the multi-select filter sub-menu."""
    f_list = settings.get("type", ["all"])
    preview = ", ".join([t.capitalize() for t in f_list])
    
    return (
        "<b>🔍 MEDIA TYPE FILTERS</b>\n\n"
        f"<b>Active:</b> <code>{preview}</code>\n\n"
        "<i>Tap buttons below to toggle each filter type. \n"
        "Selecting 'All' will clear specific filters.</i>"
    )

def get_ma_filter_submenu_kb(user_id, settings):
    """Constructs the multi-select filter keyboard."""
    kb = []
    f_list = settings.get("type", ["all"])
    user_style = get_user_button_style(user_id)
    
    def get_f_btn(f_type, label):
        active = "✅" if f_type in f_list else "☑️"
        return InlineKeyboardButton(f"{active} {label}", f"ma_filter_{f_type}_{user_id}", style=user_style)
    
    # Grid layout
    kb.append([get_f_btn("all", "All Media")])
    kb.append([get_f_btn("photo", "Photo"), get_f_btn("video", "Video")])
    kb.append([get_f_btn("gif", "GIF"), get_f_btn("document", "Doc")])
    kb.append([get_f_btn("audio", "Audio"), get_f_btn("voice", "Voice")])
    
    kb.append([InlineKeyboardButton("Back", f"ma_refresh_{user_id}", style=user_style)])
    return InlineKeyboardMarkup(kb)

def get_ma_batch_submenu_text():
    return (
        "<blockquote expandable><b>📦 Dual Batching & Anti-Flood Settings</b>\n\n"
        "<i>Adjust the configuration below to prevent hitting rate limits during deep scans.\n"
        "Changes apply immediately.</i></blockquote>"
    )

def get_ma_batch_submenu_kb(user_id, settings):
    """Generates the inline keyboard for batch settings submenu."""
    kb = []
    user_style = get_user_button_style(user_id)
    
    def fmt_time(sec):
        m, s = divmod(int(sec), 60)
        return f"{m}m {s}s" if m and s else (f"{m}m" if m else f"{s}s")
    
    b_size = settings['batch_size']
    kb.append([InlineKeyboardButton(f"Batch/Chat: {b_size} chats", "ma_noop", style=user_style)])
    kb.append([
        InlineKeyboardButton("-5 chat", f"ma_set_batch_m5_{user_id}", style=user_style),
        InlineKeyboardButton("+5 chat", f"ma_set_batch_p5_{user_id}", style=user_style)
    ])
    
    b_delay = fmt_time(settings['batch_delay'])
    kb.append([InlineKeyboardButton(f"Delay/Bchat: {b_delay}", "ma_noop", style=user_style)])
    kb.append([
        InlineKeyboardButton("-1m", f"ma_set_bdelay_m60_{user_id}", style=user_style),
        InlineKeyboardButton("-5s", f"ma_set_bdelay_m5_{user_id}", style=user_style),
        InlineKeyboardButton("+5s", f"ma_set_bdelay_p5_{user_id}", style=user_style),
        InlineKeyboardButton("+1m", f"ma_set_bdelay_p60_{user_id}", style=user_style)
    ])
    
    b_msg_size = settings['batch_msg_size']
    kb.append([InlineKeyboardButton(f"Batch/Msg: {b_msg_size} msgs", "ma_noop", style=user_style)])
    kb.append([
        InlineKeyboardButton("-10 msg", f"ma_set_bmsg_m10_{user_id}", style=user_style),
        InlineKeyboardButton("+10 msg", f"ma_set_bmsg_p10_{user_id}", style=user_style)
    ])
    
    b_msg_delay = fmt_time(settings['batch_msg_delay'])
    kb.append([InlineKeyboardButton(f"Delay/BMsg: {b_msg_delay}", "ma_noop", style=user_style)])
    kb.append([
        InlineKeyboardButton("-1m", f"ma_set_bmdelay_m60_{user_id}", style=user_style),
        InlineKeyboardButton("-5s", f"ma_set_bmdelay_m5_{user_id}", style=user_style),
        InlineKeyboardButton("+5s", f"ma_set_bmdelay_p5_{user_id}", style=user_style),
        InlineKeyboardButton("+1m", f"ma_set_bmdelay_p60_{user_id}", style=user_style)
    ])
        
    kb.append([InlineKeyboardButton("Back", f"ma_refresh_{user_id}", style=user_style)])
    return InlineKeyboardMarkup(kb)

MA_CACHE_FILE = "cache/ma_reports.json"

def get_ma_report_data(user_id, task_id):
    import json, os
    from Main import Altruix
    
    cache_file = f"cache/ma_reports_{user_id}.json"
    
    if not hasattr(Altruix, "_MA_REPORTS"):
        Altruix._MA_REPORTS = {}
        
    if user_id not in Altruix._MA_REPORTS:
        Altruix._MA_REPORTS[user_id] = {}
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    Altruix._MA_REPORTS[user_id] = json.load(f)
            except Exception:
                pass
                
    return Altruix._MA_REPORTS[user_id].get(task_id)

def save_ma_report_data(user_id, task_id, data):
    import json, os
    from Main import Altruix
    
    cache_file = f"cache/ma_reports_{user_id}.json"
    
    if not hasattr(Altruix, "_MA_REPORTS"):
        Altruix._MA_REPORTS = {}
        
    if user_id not in Altruix._MA_REPORTS:
        Altruix._MA_REPORTS[user_id] = {}
        
    Altruix._MA_REPORTS[user_id][task_id] = data
    
    try:
        os.makedirs("cache", exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(Altruix._MA_REPORTS[user_id], f)
    except Exception:
        pass

def generate_ma_report_page(user_id, task_id: str, page: int = 1):
    """Generates the text and keyboard for a specific page of the Media Analyzer report."""
    report_data = get_ma_report_data(user_id, task_id)
        
    if not report_data:
        return "❌ <b>Error:</b> Report data expired or not found.", None
        
    results = report_data.get("results", [])
    total_chats = len(results)
    
    per_page = 10
    max_pages = max(1, (total_chats + per_page - 1) // per_page)
    
    if page < 1: page = 1
    elif page > max_pages: page = max_pages
    
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    current_chunk = results[start_idx:end_idx]
    
    # Account name resolution
    account_name = str(user_id)
    for cl in Altruix.clients:
        if cl.me and cl.me.id == user_id:
            account_name = (cl.me.first_name or "") + (" " + cl.me.last_name if cl.me.last_name else "")
            account_name = account_name.strip() or str(user_id)
            break

    text = (
        f"📋 <b>Target Chats</b>\n"
        f"Page {page}/{max_pages}\n"
        f"<b>Account:</b> {account_name}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<b>Total:</b> {total_chats} chats\n\n"
        f"<b>Filters:</b>\n"
        f"• <b>Chat:</b> {report_data.get('scope_str', 'All')}\n"
        f"• <b>Media:</b> {report_data.get('types_str', 'All')}\n\n"
    )
    
    for i, res in enumerate(current_chunk, start=start_idx + 1):
        title = str(res.get("title", "Unknown"))
        chat_id = res.get("chat_id", 0)
        link = res.get("link", "#")
        is_prot = res.get("is_protected", False)
        
        # 15 char truncation
        if len(title) > 15:
            title = title[:15] + "..."
            
        # Link escaping
        safe_title = title.replace("<", "&lt;").replace(">", "&gt;")
        if safe_title.strip() == "": safe_title = "Unknown Chat"
        text += f"{i}. <a href='{link}'>{safe_title}</a> (<code>{chat_id}</code>)\n"
        
        details = res.get("details", {})
        parts = []
        for d_name, d_count in details.items():
            if d_count > 0:
                parts.append(f"{d_count} {d_name}")
                
        prot_str = f"Protect: {is_prot}"
        if not parts:
            text += f" └─ 0 files, {prot_str}\n"
        else:
            text += " └─ " + ", ".join(parts) + f", {prot_str}\n"
            
    # Keyboard Setup
    user_style = get_user_button_style(user_id)
    buttons = []
    
    if page > 1:
        buttons.append(InlineKeyboardButton("«", f"ma_page_{task_id}_{page-1}_{user_id}", style=user_style))
    if total_chats > 0:
        buttons.append(InlineKeyboardButton(f"{page}/{max_pages}", f"ma_noop", style=user_style))
    if page < max_pages:
        buttons.append(InlineKeyboardButton("»", f"ma_page_{task_id}_{page+1}_{user_id}", style=user_style))
        
    kb = []
    if buttons:
        kb.append(buttons)
        
    return text, InlineKeyboardMarkup(kb) if kb else None

import html

async def get_ma_bl_text(client, settings, page=0):
    """Generate the text for the Media Analyzer blacklist manager."""
    bl = settings.get("blacklist", [])
    start = page * 10
    end = start + 10
    chunk = bl[start:end]
    
    text = f"<b>🚫 Media Analyzer Blacklist</b>\n\n"
    text += f"Page: {page+1}\n"
    text += f"Total: {len(bl)} chats\n\n"
    
    if not chunk:
        text += "Blacklist is empty."
        return text

    # Try to resolve names dynamically
    for i, cid in enumerate(chunk, start=start + 1):
        name = f"Chat {cid}"
        link = None
        
        try:
            chat = await client.get_chat(cid)
            name = chat.title or chat.first_name or f"Chat {cid}"
            if chat.username: link = f"https://t.me/{chat.username}"
        except Exception:
            pass
            
        name = html.escape(str(name))
        if not link:
            if str(cid).startswith("-100"):
                link = f"https://t.me/c/{str(cid)[4:]}/1"
            elif cid > 0:
                link = f"tg://user?id={cid}"
        
        if link:
            text += f"• {i}. (<code>{cid}</code>) : <a href='{link}'>{name}</a>\n"
        else:
            text += f"• {i}. (<code>{cid}</code>) : {name}\n"
            
    return text

def get_ma_bl_kb(user_id, settings, page=0):
    """Generates the inline keyboard for managing the blacklist."""
    kb = []
    bl = settings.get("blacklist", [])
    user_style = get_user_button_style(user_id)
    
    start = page * 10
    end = start + 10
    chunk = bl[start:end]
    
    for cid in chunk:
        kb.append([
            InlineKeyboardButton(f"ID: {cid}", "ma_noop", style=user_style),
            InlineKeyboardButton("Remove", f"ma_bl_rem_{cid}_{user_id}", style=user_style)
        ])
    
    kb.append([InlineKeyboardButton("Add Chat", f"ma_bl_addchat_{user_id}", style=user_style)])
    
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("« Prev", f"ma_bl_page_{page-1}_{user_id}", style=user_style))
    nav.append(InlineKeyboardButton("Back", f"ma_refresh_{user_id}", style=user_style))
    if end < len(bl):
        nav.append(InlineKeyboardButton("Next »", f"ma_bl_page_{page+1}_{user_id}", style=user_style))
         
    kb.append(nav)
    return InlineKeyboardMarkup(kb)
