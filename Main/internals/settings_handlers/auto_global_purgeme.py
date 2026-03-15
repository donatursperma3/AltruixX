# Main/internals/settings_handlers/auto_global_purgeme.py
# Implementation of Auto Global Purgeme with full feature parity and premium UI.

# 🗃️ GLOBAL REGISTRY
# Track active purge cycles per user to allow cancellation/status checks
ACTIVE_PURGE_TASKS = {} # user_id -> Task object
GLOBAL_USER_LOCKS = {}
CHAT_PURGE_LOCKS = {}

import logging
import html
import re
import time
import random
import asyncio

REGISTRY_LOCK = asyncio.Lock()

from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, MessageNotModified
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
    InlineQuery, InlineQueryResultArticle, InputTextMessageContent, Message
)
from Main import Altruix
from Main.core.decorators import iuser_check, log_errors
from .utils import send_log_notification

# Logger for tracking internal operations and errors
logger = logging.getLogger(__name__)

# State management for temporary UI sessions (if needed for future extensions)
AUTO_GP_DASH_STATE = {}
STATE_LOCK = asyncio.Lock()

# ✅ CRITICAL FIX: Cache untuk settings agar tidak query DB setiap message
# TTL 60 detik untuk balance antara freshness dan performance
from cachetools import TTLCache
import time

AUTO_GP_SETTINGS_CACHE = TTLCache(maxsize=100, ttl=60)  # Cache 60 detik
CACHE_LOCK = asyncio.Lock()

# ✅ NEW: Cache for target chats (Dialog scan is very expensive)
# TTL 1 hour (3600s) as dialogs don't change that frequently for purge targets
AUTO_GP_TARGETS_CACHE = TTLCache(maxsize=50, ttl=3600)
TARGETS_CACHE_TTL = 3600
TARGETS_LOCK = asyncio.Lock()

async def get_auto_gp_settings(user_id):
    """
    Fetch Auto-GP settings for a specific user from the database/environment.
    Provides fallback defaults to ensure stability even if configuration is missing.
    
    ✅ OPTIMIZED: Uses TTL cache to prevent excessive database queries on every message.
    """
    # ✅ Check cache first
    cache_key = f"auto_gp_{user_id}"
    async with CACHE_LOCK:
        if cache_key in AUTO_GP_SETTINGS_CACHE:
            return AUTO_GP_SETTINGS_CACHE[cache_key]
    
    # System Status (ON/OFF)
    is_on = (await Altruix.config.get_env(f"AUTO_GP_STATUS_{user_id}")) == "on"
    
    # Message limits and timing delays
    limit = int(await Altruix.config.get_env(f"AUTO_GP_LIMIT_{user_id}") or 10)
    delay = float(await Altruix.config.get_env(f"AUTO_GP_DELAY_{user_id}") or 1.0)
    delay_msg = float(await Altruix.config.get_env(f"AUTO_GP_DELAY_MSG_{user_id}") or 1.0)
    
    # Targeting and operational modes
    target = await Altruix.config.get_env(f"AUTO_GP_TARGET_{user_id}") or "all"
    mode = await Altruix.config.get_env(f"AUTO_GP_MODE_{user_id}") or "newest"
    offset = int(await Altruix.config.get_env(f"AUTO_GP_OFFSET_{user_id}") or 0)
    notify = (await Altruix.config.get_env(f"AUTO_GP_NOTIFY_{user_id}") or "on") == "on"
    
    # Message type filters (CSV format in DB)
    filters_str = await Altruix.config.get_env(f"AUTO_GP_FILTERS_{user_id}") or "all"
    filters_list = filters_str.split(",") if filters_str else ["all"]
    
    # Administrative restrictions
    admin_filter = await Altruix.config.get_env(f"AUTO_GP_ADMIN_FILTER_{user_id}") or "all"
    
    # Blacklisted chat IDs (CSV format)
    blacklist_str = await Altruix.config.get_env(f"AUTO_GP_BLACKLIST_{user_id}") or ""
    blacklist = [int(p) for p in blacklist_str.split(",") if p.replace('-', '').isdigit()]
    
    # Target Chat scope (Global: All targets / Current: Only active chat)
    cycle = await Altruix.config.get_env(f"AUTO_GP_CYCLE_{user_id}") or "global"
    
    # Advanced Logic settings
    respect_bl = (await Altruix.config.get_env(f"AUTO_GP_RESPECT_BL_{user_id}") or "on") == "on"
    skip_cmds = (await Altruix.config.get_env(f"AUTO_GP_SKIP_CMDS_{user_id}") or "on") == "on"
    keep_recent = int(await Altruix.config.get_env(f"AUTO_GP_KEEP_RECENT_{user_id}") or 6)
    
    # Trigger Mode: "outgoing" (auto on msg send) or "manual" (force start via dashboard only)
    trigger_mode = await Altruix.config.get_env(f"AUTO_GP_TRIGGER_MODE_{user_id}") or "outgoing"

    # Batch per-chat settings
    batch_size = int(await Altruix.config.get_env(f"AUTO_GP_BATCH_SIZE_{user_id}") or 20)
    batch_delay = float(await Altruix.config.get_env(f"AUTO_GP_BATCH_DELAY_{user_id}") or 120.0)

    # Batch per-message settings
    batch_msg_size = int(await Altruix.config.get_env(f"AUTO_GP_BATCH_MSG_SIZE_{user_id}") or 40)
    batch_msg_delay = float(await Altruix.config.get_env(f"AUTO_GP_BATCH_MSG_DELAY_{user_id}") or 600.0)

    settings = {
        "status": is_on,
        "limit": limit,
        "delay": delay,
        "delay_msg": delay_msg,
        "target": target,
        "cycle": cycle,
        "mode": mode,
        "offset": offset,
        "notify": notify,
        "filters": filters_list,
        "admin_filter": admin_filter,
        "blacklist": blacklist,
        "respect_bl": respect_bl,
        "skip_cmds": skip_cmds,
        "keep_recent": keep_recent,
        "trigger_mode": trigger_mode,
        "batch_size": batch_size,
        "batch_delay": batch_delay,
        "batch_msg_size": batch_msg_size,
        "batch_msg_delay": batch_msg_delay
    }
    
    # ✅ Store in cache
    async with CACHE_LOCK:
        AUTO_GP_SETTINGS_CACHE[cache_key] = settings
    
    return settings

async def save_auto_gp_settings(user_id, settings):
    """
    Sync current dictionary of settings back to the database.
    Ensures persistent storage across sessions and restarts.
    
    ✅ OPTIMIZED: Invalidates cache after save to ensure fresh data on next read.
    """
    await Altruix.config.sync_env_to_db(f"AUTO_GP_STATUS_{user_id}", "on" if settings["status"] else "off", upsert=True)
    await Altruix.config.sync_env_to_db(f"AUTO_GP_LIMIT_{user_id}", str(settings["limit"]), upsert=True)
    await Altruix.config.sync_env_to_db(f"AUTO_GP_DELAY_{user_id}", str(settings["delay"]), upsert=True)
    await Altruix.config.sync_env_to_db(f"AUTO_GP_DELAY_MSG_{user_id}", str(settings.get("delay_msg", 1.0)), upsert=True)
    await Altruix.config.sync_env_to_db(f"AUTO_GP_TARGET_{user_id}", settings.get("target", "all"), upsert=True)
    await Altruix.config.sync_env_to_db(f"AUTO_GP_CYCLE_{user_id}", settings.get("cycle", "global"), upsert=True)
    await Altruix.config.sync_env_to_db(f"AUTO_GP_MODE_{user_id}", settings.get("mode", "newest"), upsert=True)
    await Altruix.config.sync_env_to_db(f"AUTO_GP_OFFSET_{user_id}", str(settings.get("offset", 0)), upsert=True)
    await Altruix.config.sync_env_to_db(f"AUTO_GP_NOTIFY_{user_id}", "on" if settings.get("notify", True) else "off", upsert=True)
    await Altruix.config.sync_env_to_db(f"AUTO_GP_FILTERS_{user_id}", ",".join(settings["filters"]), upsert=True)
    await Altruix.config.sync_env_to_db(f"AUTO_GP_ADMIN_FILTER_{user_id}", settings["admin_filter"], upsert=True)
    await Altruix.config.sync_env_to_db(f"AUTO_GP_BLACKLIST_{user_id}", ",".join(map(str, settings["blacklist"])), upsert=True)
    await Altruix.config.sync_env_to_db(f"AUTO_GP_RESPECT_BL_{user_id}", "on" if settings.get("respect_bl", True) else "off", upsert=True)
    await Altruix.config.sync_env_to_db(f"AUTO_GP_SKIP_CMDS_{user_id}", "on" if settings.get("skip_cmds", True) else "off", upsert=True)
    await Altruix.config.sync_env_to_db(f"AUTO_GP_KEEP_RECENT_{user_id}", str(settings.get("keep_recent", 6)), upsert=True)
    await Altruix.config.sync_env_to_db(f"AUTO_GP_TRIGGER_MODE_{user_id}", settings.get("trigger_mode", "outgoing"), upsert=True)
    await Altruix.config.sync_env_to_db(f"AUTO_GP_BATCH_SIZE_{user_id}", str(settings.get("batch_size", 20)), upsert=True)
    await Altruix.config.sync_env_to_db(f"AUTO_GP_BATCH_DELAY_{user_id}", str(settings.get("batch_delay", 120.0)), upsert=True)
    await Altruix.config.sync_env_to_db(f"AUTO_GP_BATCH_MSG_SIZE_{user_id}", str(settings.get("batch_msg_size", 40)), upsert=True)
    await Altruix.config.sync_env_to_db(f"AUTO_GP_BATCH_MSG_DELAY_{user_id}", str(settings.get("batch_msg_delay", 600.0)), upsert=True)
    
    # ✅ Invalidate cache after save
    cache_key = f"auto_gp_{user_id}"
    async with CACHE_LOCK:
        AUTO_GP_SETTINGS_CACHE.pop(cache_key, None)

def loc(key, *args):
    """
    Helper for multi-language support.
    Fetches the translated string and formats it if arguments are provided.
    """
    string = Altruix.get_string(key)
    if not string: return key
    if args:
        try: return string.format(*args)
        except: return string
    return string

async def get_auto_gp_status_text(user_id, current_chat_id=None):
    """
    Compiles the descriptive text for the Dashboard UI.
    Includes account stats, active filters, and current chat status.
    """
    settings = await get_auto_gp_settings(user_id)
    is_on = settings["status"]
    status_text = "ENABLED" if is_on else "DISABLED"
    
    target_str = loc(f"GP_BTN_TARGET_{settings['target'].upper()}")
    
    cycle_map = {
        "global": "Global (All Targets)",
        "current_force": "Current (Force Purge)",
        "current_smart": "Current (Smart/Safe)"
    }
    cycle_str = cycle_map.get(settings["cycle"], "Global")
    if not current_chat_id and settings["cycle"] != "global":
        cycle_str += " <b>(⚠️ Not available in Assistant Bot)</b>"
    
    mode_str = settings["mode"].capitalize()
    filters_display = ", ".join([loc(f"GP_BTN_{f.upper()}") for f in settings["filters"]])
    admin_filter_text = loc(f"GP_BTN_ADMIN_FILTER_{settings['admin_filter'].upper()}")
    respect_bl_str = "ON" if settings.get("respect_bl", True) else "OFF"
    skip_cmds_str = "ON" if settings.get("skip_cmds", True) else "OFF"
    notify_str = "ON" if settings.get("notify", True) else "OFF"
    keep_recent = settings.get("keep_recent", 6)
    trigger_mode = settings.get("trigger_mode", "outgoing")
    trigger_label = "Outgoing (Auto)" if trigger_mode == "outgoing" else "Manual (Force Start)"
    
    blacklist_status = ""
    if current_chat_id:
        is_bl = current_chat_id in settings["blacklist"]
        bl_label = "Blacklisted (Protected)" if is_bl else "Active"
        blacklist_status = f"\n<b>Current Chat:</b> {bl_label}"
        if is_bl and settings["cycle"] == "current_force":
             blacklist_status += " <b>(BYPASSED by Force Mode)</b>"

    # ... (Account name logic same) ...
    account_name = str(user_id)
    for cl in Altruix.clients:
        if cl.me and cl.me.id == user_id:
            first = cl.me.first_name or ""
            last = cl.me.last_name or ""
            account_name = f"{first} {last}".strip() or str(user_id)
            break

    text = (
        f"<b>AUTO GLOBAL PURGEME</b>\n"
        f"<blockquote expandable>"
        f"<b>Account:</b> <code>{account_name}</code>\n"
        f"<b>Status:</b> <code>{status_text}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Target:</b> <code>{target_str}</code>\n"
        f"<b>Cycle:</b> <code>{cycle_str}</code>\n"
        f"<b>Trigger:</b> <code>{trigger_label}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Limit:</b> <code>{settings['limit']} msg</code> | <b>Delay/Chat:</b> <code>{settings['delay']}s</code>\n"
        f"<b>Delay/Msg:</b> <code>{settings['delay_msg']}s</code> | <b>Mode:</b> <code>{mode_str}</code>\n"
        f"<b>Offset:</b> <code>{settings['offset']}</code> | <b>Keep Recent:</b> <code>{keep_recent} msg</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Filters:</b> <code>{filters_display}</code>\n"
        f"<b>Admin Filter:</b> <code>{admin_filter_text}</code>\n"
        f"<b>Notification:</b> <code>{notify_str}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Respect Blacklist:</b> <code>{respect_bl_str}</code>\n"
        f"<b>Skip Commands:</b> <code>{skip_cmds_str}</code>\n"
        f"<b>Batch/Chat:</b> <code>{settings.get('batch_size', 20)}ch</code> | <b>B-Delay:</b> <code>{int(settings.get('batch_delay', 120)/60)}m</code>\n"
        f"<b>Batch/Msg:</b> <code>{settings.get('batch_msg_size', 40)}ms</code> | <b>BM-Delay:</b> <code>{int(settings.get('batch_msg_delay', 600)/60)}m</code>\n"
        f"<b>Blacklisted:</b> <code>{len(settings['blacklist'])} chats</code>{blacklist_status}\n"
        f"</blockquote>"
    )
    return text

from Main.utils.file_helpers import get_user_button_style

def get_auto_gp_kb(user_id, settings, current_chat_id=None):
    """
    Constructs the compact multi-row Inline Keyboard using submenus for
    engine configuration to save vertical space.
    """
    kb = []
    target = settings.get("target", "all").capitalize()
    cycle = settings.get("cycle", "global").title().replace("_", " ")
    mode = settings.get("mode", "newest").capitalize()
    trigger_mode = settings.get("trigger_mode", "outgoing").title()
    user_style = get_user_button_style(user_id)
    
    # 🎯 Row 1: Target & Cycle Sub-menus
    kb.append([
        InlineKeyboardButton(f"🎯 Target: {target}", f"autogp_menu_target_{user_id}", style=user_style),
        InlineKeyboardButton(f"🔄 Cycle: {cycle}", f"autogp_menu_cycle_{user_id}", style=user_style)
    ])

    # 🎛 Row 2: Trigger Sub-menu & Force Start
    force_btn_text = "🚀 Force Start"
    force_btn_callback = f"autogp_forceconfirm_prompt_{user_id}"
    if not current_chat_id and settings.get("cycle", "global") != "global":
        force_btn_text = "⚠️ Switch & Start"
        force_btn_callback = f"autogp_forceconfirm_switchglobal_{user_id}"
    
    kb.append([
        InlineKeyboardButton(f"🎛 Trigger: {trigger_mode}", f"autogp_menu_trigger_{user_id}", style=user_style),
        InlineKeyboardButton(force_btn_text, force_btn_callback, style=user_style)
    ])

    # 🛑 Task Control Row: Stop Active Purge (Dynamic)
    active_task = ACTIVE_PURGE_TASKS.get(user_id)
    if active_task and not active_task.done():
        kb.append([
            InlineKeyboardButton("🛑 Stop Active Purge Cycle", f"autogp_stopcycle_{user_id}", style=user_style)
        ])
    
    # 🔢 Row 3: Limit & Mode Sub-menus
    kb.append([
        InlineKeyboardButton(f"📊 Limit: {settings['limit']}", f"autogp_menu_limit_{user_id}", style=user_style),
        InlineKeyboardButton(f"⚙️ Mode: {mode}", f"autogp_menu_mode_{user_id}", style=user_style)
    ])
    
    # ⏱ Row 4: Delay Settings Sub-menus
    kb.append([
        InlineKeyboardButton(f"⏱ Delay/Chat: {settings['delay']}s", f"autogp_menu_delaychat_{user_id}", style=user_style),
        InlineKeyboardButton(f"⏳ Delay/Msg: {settings.get('delay_msg', 1.0)}s", f"autogp_menu_delaymsg_{user_id}", style=user_style)
    ])

    # 📦 Row: Batch Configuration (NEW)
    batch_text = f"📦 Batch: {settings.get('batch_size', 20)}chats / {settings.get('batch_msg_size', 40)}msgs"
    kb.append([
        InlineKeyboardButton(batch_text, f"autogp_menu_batch_{user_id}", style=user_style)
    ])

    # 📏 Row 5: Offset & Keep Recent Sub-menus
    kb.append([
        InlineKeyboardButton(f"📏 Offset: {settings.get('offset', 0)}", f"autogp_menu_offset_{user_id}", style=user_style),
        InlineKeyboardButton(f"🛡 Keep Recent: {settings.get('keep_recent', 6)}msgs", f"autogp_menu_keeprecent_{user_id}", style=user_style)
    ])

    # 🔔 Row: Notification Toggle
    kb.append([
        InlineKeyboardButton(("Notif: ✅ ON" if settings.get("notify", True) else "Notif: ❌ OFF"), f"autogp_notif_{user_id}", style=user_style)
    ])

    # 🧹 Row: Message Filter & Administrative Access Filter
    f_list = settings.get("filters", ["all"])
    active_count = len(f_list)
    filter_preview = "All Types" if "all" in f_list else f"{active_count} selected"
    
    admin_filter_active = loc(f"GP_BTN_ADMIN_FILTER_{settings.get('admin_filter', 'all').upper()}")
    
    kb.append([
        InlineKeyboardButton(f"🧹 Msg Filter: {filter_preview}", f"autogp_filtermenu_{user_id}", style=user_style),
        InlineKeyboardButton(f"👑 Adm Filter: {admin_filter_active}", f"autogp_toggleadmin_{user_id}", style=user_style)
    ])

    # 🧠 Row: Respect Blacklist + Skip Commands
    respect_bl_btn = "🚫 Respect BL: ON" if settings.get("respect_bl", True) else "🚫 Respect BL: OFF"
    skip_cmds_btn = "⌨️ Skip CMD: ON" if settings.get("skip_cmds", True) else "⌨️ Skip CMD: OFF"
    kb.append([
        InlineKeyboardButton(respect_bl_btn, f"autogp_respectbl_{user_id}", style=user_style),
        InlineKeyboardButton(skip_cmds_btn, f"autogp_skipcmds_{user_id}", style=user_style)
    ])
    
    # 🚫 Row: Interactive Blacklist for current chat
    if current_chat_id:
        is_bl = current_chat_id in settings.get("blacklist", [])
        btn_text = "✅ Active (Whitelist)" if is_bl else "🚫 Blacklist This Chat"
        kb.append([InlineKeyboardButton(btn_text, f"autogp_bl_togglecid_{user_id}", style=user_style)])

    # 📋 Row: List Blacklist + List Chats (combined)
    kb.append([
        InlineKeyboardButton(f"🚫 List Blacklist: ({len(settings.get('blacklist', []))})", f"autogp_bl_list_{user_id}", style=user_style),
        InlineKeyboardButton(loc("GP_BTN_LIST_CHATS"), f"autogp_list_target_{user_id}", style=user_style)
    ])
    
    # 🔄 Row: Refresh + Info
    kb.append([
        InlineKeyboardButton("🔄 Refresh", f"autogp_refresh_{user_id}", style=user_style),
        InlineKeyboardButton(loc("GP_BTN_INFO"), f"autogp_info_{user_id}", style=user_style)
    ])
    
    # 🟢/🔴 Row: Enable/Disable + Close Menu
    status_btn = "🔴 Disable Auto-GP" if settings.get("status", True) else "🟢 Enable Auto-GP"
    kb.append([
        InlineKeyboardButton(status_btn, f"autogp_toggle_{user_id}", style=user_style),
        InlineKeyboardButton("❌ Close Menu", f"autogp_close_{user_id}", style=user_style)
    ])
    
    return InlineKeyboardMarkup(kb)

def get_autogp_submenu_text(settings, menu_type):
    """Generates the descriptive text for a specific submenu."""
    titles = {
        "target": "🎯 Target Chat Settings",
        "cycle": "🔄 Cycle Mode Settings",
        "trigger": "🎛 Trigger Mode Settings",
        "limit": "📊 Deletion Limit Settings",
        "delaychat": "⏱ Inter-Chat Delay Settings",
        "delaymsg": "⏳ Inter-Msg Delay Settings",
        "mode": "⚙️ Deletion Search Mode Settings",
        "offset": "📏 Skip Offset Settings",
        "keeprecent": "🛡 Keep Recent Settings",
        "batch": "📦 Dual Batching & Anti-Flood Settings"
    }
    
    title = titles.get(menu_type, "⚙️ Submenu Settings")
    return (
        f"<blockquote expandable><b>{title}</b>\n\n"
        f"<i>Adjust the configuration below.\n"
        f"Changes apply immediately to upcoming processes.</i></blockquote>"
    )

def get_autogp_submenu_kb(user_id, settings, menu_type, current_chat_id=None):
    """Generates the inline keyboard for a specific engine setting submenu."""
    kb = []
    user_style = get_user_button_style(user_id)
    
    if menu_type == "target":
        target = settings.get("target", "all")
        kb.append([
            InlineKeyboardButton(("✅ " if target == "all" else "") + loc("GP_BTN_TARGET_ALL"), f"autogp_target_all_{user_id}", style=user_style),
            InlineKeyboardButton(("✅ " if target == "groups" else "") + loc("GP_BTN_TARGET_GROUPS"), f"autogp_target_groups_{user_id}", style=user_style),
            InlineKeyboardButton(("✅ " if target == "personal" else "") + loc("GP_BTN_TARGET_PERSONAL"), f"autogp_target_personal_{user_id}", style=user_style)
        ])
    elif menu_type == "cycle":
        cycle = settings.get("cycle", "global")
        cycle_row = [
            InlineKeyboardButton(("✅ " if cycle == "global" else "") + "Global", f"autogp_cycle_global_{user_id}", style=user_style),
            InlineKeyboardButton(("✅ " if cycle == "current_smart" else "") + "C-Smart", f"autogp_cycle_current_smart_{user_id}", style=user_style),
            InlineKeyboardButton(("✅ " if cycle == "current_force" else "") + "C-Force", f"autogp_cycle_current_force_{user_id}", style=user_style)
        ]
        kb.append(cycle_row)
    elif menu_type == "trigger":
        trigger_mode = settings.get("trigger_mode", "outgoing")
        kb.append([
            InlineKeyboardButton(("✅ " if trigger_mode == "outgoing" else "") + "📤 Outgoing", f"autogp_trigmode_outgoing_{user_id}", style=user_style),
            InlineKeyboardButton(("✅ " if trigger_mode == "manual" else "") + "🖐 Manual", f"autogp_trigmode_manual_{user_id}", style=user_style)
        ])
    elif menu_type == "limit":
        kb.append([InlineKeyboardButton(f"Limit: {settings['limit']} msg", "autogp_noop", style=user_style)])
        kb.append([
            InlineKeyboardButton("-2 msg", f"autogp_limit_m2_{user_id}", style=user_style),
            InlineKeyboardButton("+2 msg", f"autogp_limit_p2_{user_id}", style=user_style)
        ])
    elif menu_type == "delaychat":
        kb.append([InlineKeyboardButton(f"Delay/Chat: {settings['delay']}s", "autogp_noop", style=user_style)])
        kb.append([
            InlineKeyboardButton("-1s", f"autogp_delay_m1_{user_id}", style=user_style),
            InlineKeyboardButton("+1s", f"autogp_delay_p1_{user_id}", style=user_style)
        ])
    elif menu_type == "delaymsg":
        kb.append([InlineKeyboardButton(f"Delay/Msg: {settings.get('delay_msg', 1.0)}s", "autogp_noop", style=user_style)])
        kb.append([
            InlineKeyboardButton("-0.5s", f"autogp_delaymsg_m05_{user_id}", style=user_style),
            InlineKeyboardButton("+0.5s", f"autogp_delaymsg_p05_{user_id}", style=user_style)
        ])
    elif menu_type == "mode":
        mode = settings.get("mode", "newest")
        kb.append([
            InlineKeyboardButton(("✅ " if mode == "newest" else "") + loc("GP_BTN_MODE_NEWEST"), f"autogp_mode_newest_{user_id}", style=user_style),
            InlineKeyboardButton(("✅ " if mode == "oldest" else "") + loc("GP_BTN_MODE_OLDEST"), f"autogp_mode_oldest_{user_id}", style=user_style)
        ])
    elif menu_type == "offset":
        kb.append([InlineKeyboardButton(f"Offset: {settings.get('offset', 0)}", "autogp_noop", style=user_style)])
        kb.append([
            InlineKeyboardButton("-5", f"autogp_off_m5_{user_id}", style=user_style),
            InlineKeyboardButton(loc("GP_BTN_RESET"), f"autogp_off_reset_{user_id}", style=user_style),
            InlineKeyboardButton("+5", f"autogp_off_p5_{user_id}", style=user_style)
        ])
    elif menu_type == "keeprecent":
        kb.append([InlineKeyboardButton(f"Keep Recent: {settings.get('keep_recent', 6)} msg", "autogp_noop", style=user_style)])
        kb.append([
            InlineKeyboardButton("-2 msg", f"autogp_keep_m2_{user_id}", style=user_style),
            InlineKeyboardButton(f"+2 msg", f"autogp_keep_p2_{user_id}", style=user_style)
        ])
    elif menu_type == "batch":
        kb.append([InlineKeyboardButton(f"📦 Batch/Chat: {settings.get('batch_size', 20)} chats", "autogp_noop", style=user_style)])
        kb.append([
            InlineKeyboardButton("-5 ch", f"autogp_batch_m5_{user_id}", style=user_style),
            InlineKeyboardButton("+5 ch", f"autogp_batch_p5_{user_id}", style=user_style)
        ])
        kb.append([InlineKeyboardButton(f"⏱ Delay/Bchat: {int(settings.get('batch_delay', 120)/60)} min", "autogp_noop", style=user_style)])
        kb.append([
            InlineKeyboardButton("-1 min", f"autogp_bdelay_m60_{user_id}", style=user_style),
            InlineKeyboardButton("+1 min", f"autogp_bdelay_p60_{user_id}", style=user_style)
        ])
        kb.append([InlineKeyboardButton(f"✉️ Batch/Msg: {settings.get('batch_msg_size', 40)} msgs", "autogp_noop", style=user_style)])
        kb.append([
            InlineKeyboardButton("-10 ms", f"autogp_batch_m10_{user_id}", style=user_style),
            InlineKeyboardButton("+10 ms", f"autogp_batch_p10_{user_id}", style=user_style)
        ])
        kb.append([InlineKeyboardButton(f"⏱ Delay/BMsg: {int(settings.get('batch_msg_delay', 600)/60)} min", "autogp_noop", style=user_style)])
        kb.append([
            InlineKeyboardButton("-1 min", f"autogp_bmsgdelay_m60_{user_id}", style=user_style),
            InlineKeyboardButton("+1 min", f"autogp_bmsgdelay_p60_{user_id}", style=user_style)
        ])
        
    kb.append([InlineKeyboardButton("⬅️ Back to Dashboard", f"autogp_refresh_{user_id}", style=user_style)])
    return InlineKeyboardMarkup(kb)

def get_autogp_info_text():
    """
    Returns the detailed help/info text for Auto-GP.
    """
    return (
        "<b>🤖 AUTO GLOBAL PURGEME - COMPREHENSIVE GUIDE</b>\n\n"
        "<b>🔄 CYCLE MODES (Trigger Logic):</b>\n"
        "• <b>Global 🌍:</b> Memproses SEMUA chat yang sesuai target. Aman & menyeluruh.\n"
        "• <b>Current Smart 🔆:</b> Hanya proses chat saat ini & <b>Hormati</b> Blacklist/Admin Filter.\n"
        "• <b>Current Force ⚠️:</b> Paksa hapus chat saat ini, <b>ABAIKAN</b> semua batasan (Use with Caution!).\n\n"
        "<b>🎯 TARGETS & ACCESS:</b>\n"
        "• <b>Groups/Personal/All:</b> Jenis chat yang akan diproses pada mode Global.\n"
        "• <b>Admin Filter:</b> Pilih untuk hapus hanya di grup di mana Anda Admin, Non-Admin, atau keduanya.\n"
        "• <b>Blacklist Manager:</b> Daftar chat yang akan dilewati secara otomatis.\n\n"
        "<b>📊 DELETION SETTINGS:</b>\n"
        "• <b>Limit:</b> Jumlah maksimal pesan yang dihapus per chat dalam satu siklus.\n"
        "• <b>Mode Search:</b> <i>Newest</i> (hapus dari terbaru) or <i>Oldest</i> (hapus dari terlama).\n"
        "• <b>Skip Offset:</b> Melewati <code>N</code> pesan teratas dalam pencarian (misal sisakan 5 pesan teratas).\n\n"
        "<b>⏱ DELAY CONTROL:</b>\n"
        f"• <b>Delay/Chat:</b> Jeda waktu antar pemrosesan chat pada mode Global.\n"
        f"• <b>Delay/Msg:</b> Jeda waktu antar penghapusan pesan (mencegah FloodWait).\n\n"
        f"<b>📦 BATCHING (Anti-Flood):</b>\n"
        f"• <b>Batch Chats:</b> Jeda extra setelah memproses <code>N</code> chat.\n"
        f"• <b>Batch Msg:</b> Jeda extra setelah menghapus <code>N</code> total pesan.\n"
        f"• <i>Fitur ini sangat disarankan untuk menjaga akun Anda tetap aman dari limit/floodwait Telegram.</i>\n\n"
        f"<b>🧠 ADVANCED LOGIC:</b>\n"
        "• <b>Respect Blacklist:</b> Jika ON, pesan di chat blacklist tidak akan memicu siklus Auto-GP.\n"
        "• <b>Cmd Bypass:</b> Lewati pesan Command (.ping, dll) & BALASANnya agar tidak terhapus.\n"
        "• <b>Keep Recent:</b> Safety buffer untuk menjaga <code>N</code> pesan terbaru tetap aman.\n\n"
        "<b>🎛 TRIGGER MODE:</b>\n"
        "• <b>Outgoing 📤:</b> Auto-GP otomatis jalan setiap kali Anda mengirim pesan baru (Default).\n"
        "• <b>Manual 🖐:</b> Auto-GP TIDAK jalan otomatis. Hanya bisa dijalankan lewat tombol [🚀 Force Start] di dashboard.\n"
        "• <b>Force Start 🚀:</b> Tombol untuk menjalankan siklus penghapusan SEKARANG JUGA (dengan konfirmasi [Yes]/[No]).\n\n"
        "<b>🔔 OTHER:</b>\n"
        "• <b>Logs/Notif:</b> Kirim notifikasi hasil pembersihan ke log chat.\n"
        "• <b>Master Switch:</b> Aktifkan/Matikan seluruh sistem Auto-GP secara instan."
    )

def get_autogp_filter_submenu_text(settings):
    """
    Generates the text for the filter sub-menu with a live preview
    of currently active message type filters.
    """
    f_list = settings.get("filters", ["all"])
    
    # All 16 filter types with their display info
    ALL_FILTER_TYPES = [
        ("all", "All Types", "📦"),
        ("text", "Text", "📝"), ("photo", "Photo", "🖼"), ("video", "Video", "🎬"),
        ("audio", "Audio", "🎵"), ("voice", "Voice", "🎤"), ("sticker", "Sticker", "🎨"),
        ("animation", "Animation/GIF", "🎞"), ("document", "Document", "📄"), ("video_note", "Video Note", "⏺"),
        ("contact", "Contact", "👤"), ("location", "Location", "📍"), ("venue", "Venue", "🏛"),
        ("game", "Game", "🎮"), ("poll", "Poll", "📊"), ("dice", "Dice", "🎲")
    ]
    
    # Build live preview
    preview_lines = []
    for f_type, f_name, f_icon in ALL_FILTER_TYPES:
        status = "✅" if f_type in f_list else "☑️"
        preview_lines.append(f"{status} {f_icon} {f_name}")
    
    text = (
        "<b>🧹 MESSAGE TYPE FILTERS</b>\n\n"
        "<b>Live Preview:</b>\n"
        + "\n".join(preview_lines) + "\n\n"
        "<i>Tap buttons below to toggle each filter type.\n"
        "Active filters determine which message types are purged.</i>"
    )
    return text

def get_autogp_filter_submenu_kb(user_id, settings):
    """
    Constructs the filter sub-menu keyboard with all 16 message types.
    Organized in a clean grid layout with Back button.
    """
    kb = []
    f_list = settings.get("filters", ["all"])
    user_style = get_user_button_style(user_id)
    
    def get_f_btn(f_type, label_key, def_label):
        label = loc(label_key) or def_label
        active = "✅" if f_type in f_list else "☑️"
        return InlineKeyboardButton(f"{active} {label}", f"autogp_filter_{f_type}_{user_id}", style=user_style)
    
    # Row 1: All
    kb.append([get_f_btn("all", "GP_BTN_ALL", "All Types")])
    # Row 2-3: Common media
    kb.append([get_f_btn("text", "GP_BTN_TEXT", "Text"), get_f_btn("photo", "GP_BTN_PHOTO", "Photo"), get_f_btn("video", "GP_BTN_VIDEO", "Video")])
    kb.append([get_f_btn("audio", "GP_BTN_AUDIO", "Audio"), get_f_btn("sticker", "GP_BTN_STICKER", "Sticker"), get_f_btn("voice", "GP_BTN_VOICE", "Voice")])
    # Row 4-5: Other media
    kb.append([get_f_btn("animation", "GP_BTN_ANIMATION", "Anim"), get_f_btn("document", "GP_BTN_DOCUMENT", "Doc"), get_f_btn("video_note", "GP_BTN_VNOTE", "VNote")])
    kb.append([get_f_btn("contact", "GP_BTN_CONTACT", "Contact"), get_f_btn("location", "GP_BTN_LOCATION", "Loc"), get_f_btn("venue", "GP_BTN_VENUE", "Venue")])
    # Row 6: Misc
    kb.append([get_f_btn("game", "GP_BTN_GAME", "Game"), get_f_btn("poll", "GP_BTN_POLL", "Poll"), get_f_btn("dice", "GP_BTN_DICE", "Dice")])
    # Back button
    kb.append([InlineKeyboardButton("⬅️ Back to Dashboard", f"autogp_back_{user_id}", style=user_style)])
    
    return InlineKeyboardMarkup(kb)

def get_autogp_cmd_help_text(plugin_version="unknown"):
    """
    Returns formatted help text showing all manual commands from
    xauto_gpurgeme_userbot.py with their descriptions.
    """
    return (
        f"<b>📋 AUTO GLOBAL PURGEME - COMMANDS</b>\n"
        f"<code>Plugin v{plugin_version}</code>\n\n"
        "<b>Available Commands:</b>\n\n"
        "• <code>.autogp</code>\n"
        "  ↳ Open Auto-GP Dashboard via Bot Assistant\n\n"
        "• <code>.autogpon</code> / <code>.autogpoff</code>\n"
        "  ↳ Quick toggle Auto-GP ON or OFF\n\n"
        "• <code>.autogpbl [chat_id]</code>\n"
        "  ↳ Toggle blacklist for current/specified chat\n\n"
        "• <code>.autogpdel &lt;chat_id&gt;</code>\n"
        "  ↳ Remove a specific chat from blacklist\n\n"
        "• <code>.autogpblist</code>\n"
        "  ↳ View all blacklisted chats\n\n"
        "• <code>.autogpstatus</code>\n"
        "  ↳ View current Auto-GP status and config\n\n"
        "<i>Use the dashboard for advanced settings like\n"
        "filters, delays, cycle modes, and more.</i>"
    )

async def get_auto_gp_target_chats(client: Client, target_type: str, admin_filter: str, blacklist: list):
    """
    Scans dialogs for target chats that are NOT on the blacklist.
    ✅ OPTIMIZED: Uses TTL cache to prevent frequent expensive dialog scans.
    """
    if client.me.is_bot:
        return [], 0
        
    user_id = client.me.id
    cache_key = f"targets_{user_id}_{target_type}_{admin_filter}"
    
    async with TARGETS_LOCK:
        if cache_key in AUTO_GP_TARGETS_CACHE:
            cached_chats, cached_ignored, timestamp = AUTO_GP_TARGETS_CACHE[cache_key]
            if time.time() - timestamp < TARGETS_CACHE_TTL:
                # Filter out blacklisted ones from cache dynamically
                filtered = [c for c in cached_chats if c["id"] not in blacklist]
                Altruix.log(f"✅ Auto-GP | Cache hit for targets (user {user_id})...", level=20)
                return filtered, cached_ignored
            else:
                del AUTO_GP_TARGETS_CACHE[cache_key] # Cache expired

    chats = []
    ignored_count = 0
    total_scanned = 0
    
    Altruix.log(f"🔍 Auto-GP | Scanning dialogs for user {user_id} (Cache Miss, Deep Scan)...", level=20)
    try:
        async for dialog in client.get_dialogs():
            total_scanned += 1
                
            # Periodic yield to keep UI responsive and log progress
            if total_scanned % 100 == 0: 
                Altruix.log(f"⏳ Auto-GP | Scanned {total_scanned} dialogs so far...", level=10)
                await asyncio.sleep(0.1)
                
            chat_id = dialog.chat.id
            if chat_id in blacklist:
                 ignored_count += 1
                 continue

            is_target = False
            chat_type = dialog.chat.type
            
            if target_type == "all" and chat_type in [enums.ChatType.PRIVATE, enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
                is_target = True
            elif target_type == "groups" and chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
                is_target = True
            elif target_type == "personal" and chat_type == enums.ChatType.PRIVATE:
                is_target = True
            
            if is_target:
                should_ignore = False
                if admin_filter != "all" and chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
                    try:
                        # Pacing API calls to avoid FloodWait from Telegram
                        await asyncio.sleep(0.25)
                        # Fetch member directly to avoid Pyrogram Future cancellation bug (NoneType.set)
                        me = await dialog.chat.get_member("me")
                        is_admin = me.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]
                        if admin_filter == "admin" and not is_admin: should_ignore = True
                        elif admin_filter == "non_admin" and is_admin: should_ignore = True
                    except Exception as e:
                        # Handle FloodWait securely
                        if "FloodWait" in str(type(e).__name__):
                            wait_time = getattr(e, "value", 10)
                            Altruix.log(f"⚠️ Auto-GP | FloodWait di chat {chat_id}, tidur {wait_time}s...", level=30)
                            await asyncio.sleep(wait_time + 1)
                            should_ignore = True # Skip this chat for safety for this cycle
                        else:
                            # If check fails or times out, assume non-admin for safety in 'admin' filter
                            if admin_filter == "admin": should_ignore = True
                
                if should_ignore: ignored_count += 1
                else:
                    chats.append({
                        "id": chat_id,
                        "title": dialog.chat.title or f"{dialog.chat.first_name or ''} {dialog.chat.last_name or ''}".strip() or str(chat_id)
                    })
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        Altruix.log(f"⚠️ Auto-GP | Dialog scan interrupted for user {user_id}: {e}\n<pre>{tb}</pre>", level=30)
        
    # Final Caching
    if chats:
        async with TARGETS_LOCK:
            AUTO_GP_TARGETS_CACHE[cache_key] = (chats, ignored_count, time.time())
            
    return chats, ignored_count

async def get_autogp_bl_text(client, settings, page=0):
    """
    Generate the text for the blacklist manager with clickable chat names.
    Supports hyperlinks for Android/iOS/Desktop.
    Resolves chat names via userbot client for better access (even non-admin groups).
    """
    bl = settings["blacklist"]
    start = page * 10
    end = start + 10
    chunk = bl[start:end]
    
    text = f"<b>🚫 Auto-GP Blacklist Manager</b>\n\n"
    text += f"Page: {page+1}\n"
    text += f"Total: {len(bl)} restricted chats\n\n"
    
    if not chunk:
        text += "<i>Blacklist is empty.</i>"
        return text

    # Determine the best client for resolving chats
    # Prefer userbot client (has broader access than bot client)
    resolve_client = client
    # Extract user_id from settings keys if possible, or check Altruix.clients
    for cl in Altruix.clients:
        if cl.me and cl.is_connected:
            resolve_client = cl
            break

    # 1. Gather pre-resolved names from cache if available to avoid API spam
    cached_titles = {}
    for cl in Altruix.clients:
        if cl.me:
            cache_key = f"auto_gp_targets_{cl.me.id}"
            if cache_key in AUTO_GP_TARGETS_CACHE:
                cached_data, _, _ = AUTO_GP_TARGETS_CACHE[cache_key]
                for c in cached_data:
                    cached_titles[int(c["id"])] = c["title"]
                    
    # Dynamic fetching of chat info for hyperlinks
    for i, cid in enumerate(chunk, start=start + 1):
        name = cached_titles.get(int(cid)) # Try cache first
        link = None
        
        # If not in cache, try API resolution via userbot first, then bot
        if not name:
            try:
                chat = await resolve_client.get_chat(cid)
                name = chat.title or chat.first_name or f"Chat {cid}"
                if chat.username: link = f"https://t.me/{chat.username}"
            except Exception:
                try:
                    chat = await client.get_chat(cid)
                    name = chat.title or chat.first_name or f"Chat {cid}"
                    if chat.username: link = f"https://t.me/{chat.username}"
                except Exception:
                    name = f"Unknown Chat ({cid})"
        
        # Format name securely
        name = html.escape(str(name))
            
        # Ensure a link is present if possible
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

def get_autogp_bl_kb(user_id, settings, page=0):
    """
    Generates a sub-menu for managing blacklisted chats.
    Includes [ID][Remove] layout, [Add Chat] button, and [Back][Page N] navigation.
    """
    kb = []
    bl = settings["blacklist"]
    user_style = get_user_button_style(user_id)
    
    # Paginate (display 10 IDs per view)
    start = page * 10
    end = start + 10
    chunk = bl[start:end]
    
    for cid in chunk:
        kb.append([
            InlineKeyboardButton(f"ID: {cid}", "autogp_noop", style=user_style),
            InlineKeyboardButton("Remove", f"autogp_bl_rem_{cid}_{user_id}", style=user_style)
        ])
    
    # Add Chat to Blacklist button (input-based)
    kb.append([InlineKeyboardButton("Add Chat", f"autogp_bl_addchat_{user_id}", style=user_style)])
    
    # Footer Navigation
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(f"Page {page}", f"autogp_bl_page_{page-1}_{user_id}", style=user_style))
    nav.append(InlineKeyboardButton(loc("GP_BTN_BACK"), f"autogp_refresh_{user_id}", style=user_style))
    if end < len(bl):
        nav.append(InlineKeyboardButton(f"Page {page+2}", f"autogp_bl_page_{page+1}_{user_id}", style=user_style))
         
    kb.append(nav)
    return InlineKeyboardMarkup(kb)

@Altruix.bot.on_callback_query(filters.regex(r"^autogp_(?P<action>menu|target|cycle|limit|delay|delaymsg|mode|off|notif|filter|filtermenu|toggleadmin|bl|refresh|close|toggle|list|info|showcmd|back|noop|respectbl|skipcmds|keep|trigmode|forceconfirm|batch|bdelay|bmsgdelay|stopcycle)_(?P<tail>.*)$"))
# NOTE: 'bl' action handles sub_actions: togglecid, addchat, list, page_N, rem_ID
@iuser_check
@log_errors
async def auto_gp_callback_handler(c: Client, cb: CallbackQuery):
    """
    Primary handler for logic adjustments from Dashboard buttons.
    Uses Regex capture groups to parse the intent (action, subaction, account_id).
    """
    # 🕵️ CRITICAL DEBUG: Verify entry
    Altruix.log(f"📍 Auto-GP Callback | RAW ENTRY | Data: {cb.data}", level=20)
    
    m = cb.matches[0]
    action = m.group("action")
    tail = m.group("tail")
    
    # Unified tail parsing: [subaction_]user_id
    parts = tail.split("_")
    user_id = int(parts[-1])
    sub_action = "_".join(parts[:-1]) if len(parts) > 1 else None
    
    # 🔍 TRACE: Callback Entry
    Altruix.log(f"📍 Auto-GP Callback | Action: {action} | Sub: {sub_action} | TargetID: {user_id}", level=20)
    
    # Access Security Check
    from Main.utils.access_control import is_authorized_user
    if not is_authorized_user(cb.from_user.id, Altruix.config.OWNER_USERS_ID, Altruix.config.SUDO_USERS_ID):
        await cb.answer("⛔ Access Denied: Authorized accounts only.", show_alert=True)
        return

    settings = await get_auto_gp_settings(user_id)
    chat_id = cb.message.chat.id if cb.message else None
    
    # 🧩 LOGIC: No-Operation (for info buttons)
    if action == "noop": return await cb.answer()

    # 📋 LOGIC: Engine Submenu Navigator
    elif action == "menu":
        menu_type = sub_action
        text = get_autogp_submenu_text(settings, menu_type)
        kb = get_autogp_submenu_kb(user_id, settings, menu_type, chat_id)
        try:
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
        except MessageNotModified:
            pass
        return
    
    # ⚙️ LOGIC: Master Killswitch (with alert)
    elif action == "toggle":
        settings["status"] = not settings["status"]
        status_str = " ✅ ENABLED" if settings["status"] else "🔴 DISABLED "
        await cb.answer(
            f"AUTO GLOBAL PURGEME: {status_str}\n\n"
            f"{'Automated purging is ACTIVE. Messages will be purged on every outgoing message.' if settings['status'] else 'Automated purging is STOPPED. No messages will be purged.'}",
            show_alert=True
        )
    
    # 🎯 LOGIC: Target Chat Filtering
    elif action == "target":
        settings["target"] = sub_action
        await cb.answer(f"🎯 Target Filter set to: {sub_action.capitalize()}")

    # 🔄 LOGIC: Cycle Selection (NEW)
    elif action == "cycle":
        settings["cycle"] = sub_action
        await cb.answer(f"🔄 Cycle Mode set to: {sub_action.capitalize()}")
    
    # 🔢 LOGIC: Limit Adjustment
    elif action == "limit":
        if sub_action == "m2": settings["limit"] = max(1, settings["limit"] - 2)
        elif sub_action == "p2": settings["limit"] += 2
        await cb.answer(f"📊 Deletion Limit: {settings['limit']}")
        
    # ⏱ LOGIC: Timing Control
    elif action == "delay":
        if sub_action == "m1": settings["delay"] = max(0, settings["delay"] - 1.0)
        elif sub_action == "p1": settings["delay"] += 1.0
        await cb.answer(f"⌛ Inter-Chat Delay: {settings['delay']}s")

    elif action == "delaymsg":
        if sub_action == "m05": settings["delay_msg"] = max(0, settings.get("delay_msg", 1.0) - 0.5)
        elif sub_action == "p05": settings["delay_msg"] = settings.get("delay_msg", 1.0) + 0.5
        await cb.answer(f"⏳ Inter-Msg Delay: {settings['delay_msg']}s")

    # 📦 LOGIC: Dual Batch Configuration
    elif action == "batch":
        if sub_action == "m5": settings["batch_size"] = max(1, settings.get("batch_size", 20) - 5)
        elif sub_action == "p5": settings["batch_size"] += 5
        elif sub_action == "m10": settings["batch_msg_size"] = max(1, settings.get("batch_msg_size", 40) - 10)
        elif sub_action == "p10": settings["batch_msg_size"] += 10
        await cb.answer(f"📦 Batch thresholds updated.")

    elif action == "bdelay":
        delta = int(sub_action.replace("m", "-").replace("p", ""))
        settings["batch_delay"] = max(0, settings.get("batch_delay", 120.0) + delta)
        await cb.answer(f"⏱ Batch Chat Delay: {int(settings['batch_delay']/60)}m")

    elif action == "bmsgdelay":
        delta = int(sub_action.replace("m", "-").replace("p", ""))
        settings["batch_msg_delay"] = max(0, settings.get("batch_msg_delay", 600.0) + delta)
        await cb.answer(f"⏱ Batch Msg Delay: {int(settings['batch_msg_delay']/60)}m")

    # ⚙️ LOGIC: Search Strategy (Newest vs Oldest)
    elif action == "mode":
        settings["mode"] = sub_action
        await cb.answer(f"🧹 Mode: {sub_action.capitalize()}")

    # 📏 LOGIC: Offset (Skip) Configuration
    elif action == "off":
        if sub_action == "m5": settings["offset"] = max(0, settings.get("offset", 0) - 5)
        elif sub_action == "p5": settings["offset"] += 5
        elif sub_action == "reset": settings["offset"] = 0
        await cb.answer(f"📏 Skip Offset: {settings['offset']}")

    # 🔔 LOGIC: Notification Preferences
    elif action == "notif":
        settings["notify"] = not settings.get("notify", True)
        await cb.answer(f"🔔 Logs: {'ON' if settings['notify'] else 'OFF'}")

    # 🧠 LOGIC: Advanced Logic Toggles
    elif action == "respectbl":
        settings["respect_bl"] = not settings.get("respect_bl", True)
        await cb.answer(f"🚫 Respect Blacklist: {'ON' if settings['respect_bl'] else 'OFF'}")

    elif action == "skipcmds":
        settings["skip_cmds"] = not settings.get("skip_cmds", True)
        await cb.answer(f"⌨️ Skip Commands: {'ON' if settings['skip_cmds'] else 'OFF'}")

    elif action == "keep":
        if sub_action == "m2": settings["keep_recent"] = max(0, settings.get("keep_recent", 6) - 2)
        elif sub_action == "p2": settings["keep_recent"] = settings.get("keep_recent", 6) + 2
        await cb.answer(f"Keep Recent: {settings['keep_recent']} messages")
        
    # 🧹 LOGIC: Media Content Filters (Smart Toggle) — stays in sub-menu
    elif action == "filter":
        f_type = sub_action
        f_list = settings.get("filters", ["all"])
        if f_type == "all": f_list = ["all"] # Reset to All if All clicked
        else:
            if "all" in f_list: f_list.remove("all")
            if f_type in f_list:
                f_list.remove(f_type)
                if not f_list: f_list = ["all"]
            else: f_list.append(f_type)
        settings["filters"] = f_list
        await save_auto_gp_settings(user_id, settings)
        await cb.answer("🧹 Filter Updated")
        # Re-render filter sub-menu with live preview
        text = get_autogp_filter_submenu_text(settings)
        kb = get_autogp_filter_submenu_kb(user_id, settings)
        try:
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        except MessageNotModified: pass
        return
    
    # 👑 LOGIC: Admin Rights Strategy
    elif action == "toggleadmin":
        curr = settings["admin_filter"]
        if curr == "all": settings["admin_filter"] = "admin"
        elif curr == "admin": settings["admin_filter"] = "non_admin"
        else: settings["admin_filter"] = "all"
        await cb.answer(f"👑 Admin Filter: {settings['admin_filter']}")
    
    # 🚫 LOGIC: Interactive Blacklist Management
    elif action == "bl":
        if sub_action == "togglecid": # Immediate toggle for current chat
            if not chat_id:
                await cb.answer("❌ This feature is only available for direct dashboard messages, not via Inline Mode.", show_alert=True)
                return
            if chat_id in settings["blacklist"]:
                settings["blacklist"].remove(chat_id)
                await cb.answer("✅ Whitelisted: Auto-GP will now track this chat.")
            else:
                settings["blacklist"].append(chat_id)
                await cb.answer("🚫 Blacklisted: Auto-GP will now skip this chat.")
        elif sub_action == "addchat": # Prompt user for chat_id or @username input
            # Send prompt to LOG chat instead of requiring direct message context
            # Get LOG_CHAT_ID
            try:
                log_chat_id = Altruix.config.LOG_CHAT_ID
                if isinstance(log_chat_id, str) and log_chat_id.lstrip("-").isdigit():
                    log_chat_id = int(log_chat_id)
            except Exception:
                log_chat_id = "me"
            
            # Get bot client
            bot = Altruix.bot_manager.get_bot(user_id) if hasattr(Altruix, 'bot_manager') else Altruix.bot
            
            try:
                prompt_msg = await bot.send_message(
                    log_chat_id,
                    "<b>➕ Add Chat to Auto-GP Blacklist</b>\n\n"
                    "Reply to this message with:\n"
                    "• <b>Chat ID</b> (e.g., <code>-1001234567890</code>)\n"
                    "• <b>@username</b> (e.g., <code>@groupname</code>)\n\n"
                    "<i>Or use command: <code>.autogpbl &lt;chat_id&gt;</code></i>",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("Cancel", f"autogp_bl_canceladd_{user_id}", style=get_user_button_style(user_id))]
                    ])
                )
                
                # Store waiting state
                dash_msg_id = cb.message.id if cb.message else None
                async with STATE_LOCK:
                    AUTO_GP_DASH_STATE[f"bl_add_{user_id}"] = {
                        "user_id": user_id,
                        "prompt_msg_id": prompt_msg.id,
                        "dash_msg_id": dash_msg_id,
                        "from_user_id": cb.from_user.id,
                        "log_chat_id": log_chat_id,
                    }
                
                # Show alert with clear instruction
                await cb.answer(
                    "📝 Check your LOG chat!\n\n"
                    "Reply to the message there with:\n"
                    "• Chat ID (e.g., -1001234567890)\n"
                    "• @username (e.g., @groupname)",
                    show_alert=True
                )
            except Exception as e:
                logger.error(f"Failed to send addchat prompt: {e}")
                await cb.answer(
                    "❌ Failed to send prompt to LOG chat.\n\n"
                    "Use command instead:\n"
                    ".autogpbl <chat_id>",
                    show_alert=True
                )
            return
        elif sub_action == "canceladd": # Cancel add-chat input
            # Clean up state
            async with STATE_LOCK:
                state = AUTO_GP_DASH_STATE.pop(f"bl_add_{user_id}", None)
            
            await cb.answer("❌ Add chat cancelled.")
            
            # Try to delete the prompt message
            if state:
                try:
                    bot = Altruix.bot_manager.get_bot(user_id) if hasattr(Altruix, 'bot_manager') else Altruix.bot
                    log_chat_id = state.get("log_chat_id", "me")
                    prompt_msg_id = state.get("prompt_msg_id")
                    if prompt_msg_id:
                        await bot.delete_messages(log_chat_id, prompt_msg_id)
                except Exception:
                    pass
            return
        elif sub_action == "list" or sub_action.startswith("page"): # Open sub-menu list
            await cb.answer("🔍 Memuat blacklist...") # Add feedback while resolving names
            page = 0
            if sub_action.startswith("page"): page = int(sub_action.split("_")[1])
            kb = get_autogp_bl_kb(user_id, settings, page)
            text = await get_autogp_bl_text(c, settings, page)
            try:
                await cb.edit_message_text(text, reply_markup=kb, disable_web_page_preview=True)
            except MessageNotModified: pass
            return
        elif sub_action.startswith("rem_"): # Individual item removal from list
            target_id = int(sub_action.split("_")[1])
            if target_id in settings["blacklist"]:
                settings["blacklist"].remove(target_id)
                await cb.answer(f"🗑 ID {target_id} has been removed.")
            await save_auto_gp_settings(user_id, settings)
            kb = get_autogp_bl_kb(user_id, settings, 0)
            text = await get_autogp_bl_text(c, settings, 0)
            await cb.edit_message_text(text, reply_markup=kb, disable_web_page_preview=True)
            return

    # 📋 LOGIC: Target Chat Listing (Paginated)
    elif action == "list" and sub_action.startswith("target"):
        await cb.answer("🔍 Scanning for target chats...")
        
        # Determine client to scan dialogs
        target_client = next((cl for cl in Altruix.clients if cl.me and cl.me.id == user_id), None)
        if not target_client:
            return await cb.answer("❌ Error: Active session not found.", show_alert=True)
            
        chats, ignored = await get_auto_gp_target_chats(
            target_client, settings["target"], settings["admin_filter"], settings["blacklist"]
        )
        
        # Parse Page
        page = 0
        if "_" in sub_action:
            try: page = int(sub_action.split("_")[1])
            except ValueError: pass
            
        per_page = 30
        start_idx = page * per_page
        end_idx = start_idx + per_page
        chunk = chats[start_idx:end_idx]
        
        chat_list = "\n".join([f"• {start_idx + i + 1}. {c['title']} (<code>{c['id']}</code>)" for i, c in enumerate(chunk)])
        
        header_fmt = "<b>Daftar Target (Halaman {}):</b>\n<i>(Total: {} | Diabaikan: {})</i>\n\n{}"
        text = header_fmt.format(page + 1, len(chats), ignored, chat_list or "Kosong")
        
        # Build Navigation Keyboard
        nav_buttons = []
        user_style = get_user_button_style(user_id)
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(f"⬅️ Prev", f"autogp_list_target_{page-1}_{user_id}", style=user_style))
        nav_buttons.append(InlineKeyboardButton(loc("GP_BTN_BACK") or "🔙 Back", f"autogp_back_{user_id}", style=user_style))
        if end_idx < len(chats):
            nav_buttons.append(InlineKeyboardButton(f"Next ➡️", f"autogp_list_target_{page+1}_{user_id}", style=user_style))
            
        kb = InlineKeyboardMarkup([nav_buttons])
        try:
            await cb.edit_message_text(text, reply_markup=kb, disable_web_page_preview=True)
        except MessageNotModified: pass
        return
    
    # 🛑 LOGIC: Stop Active Purge Cycle
    elif action == "stopcycle":
        task = ACTIVE_PURGE_TASKS.get(user_id)
        if task and not task.done():
            task.cancel()
            ACTIVE_PURGE_TASKS.pop(user_id, None)
            await cb.answer("🛑 Purge cycle cancelled successfully.", show_alert=True)
            Altruix.log(f"🛑 Auto-GP | Purge cycle STOPPED via Dashboard by {cb.from_user.id}", level=20)
        else:
            await cb.answer("ℹ️ No active purge cycle found.", show_alert=False)
        
        # Re-render dashboard
        settings = await get_auto_gp_settings(user_id)
        text = await get_auto_gp_status_text(user_id, chat_id)
        kb = get_auto_gp_kb(user_id, settings, chat_id)
        try:
            await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
        except MessageNotModified:
            pass
        return

    # 🧹 LOGIC: Filter Sub-Menu
    elif action == "filtermenu":
        text = get_autogp_filter_submenu_text(settings)
        kb = get_autogp_filter_submenu_kb(user_id, settings)
        await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        return

    # ℹ️ LOGIC: Info Menu (with Show CMD button)
    elif action == "info":
        text = get_autogp_info_text()
        user_style = get_user_button_style(user_id)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Show CMD", f"autogp_showcmd_{user_id}", style=user_style)],
            [InlineKeyboardButton(loc("GP_BTN_BACK"), f"autogp_back_{user_id}", style=user_style)]
        ])
        await cb.edit_message_text(text, reply_markup=kb)
        return

    # 📋 LOGIC: Show CMD Help
    elif action == "showcmd":
        # Try to get plugin version from the userbot module
        try:
            from Main.plugins.userbot.xauto_gpurgeme_userbot import PLUGIN_VERSION
        except ImportError:
            PLUGIN_VERSION = "unknown"
        text = get_autogp_cmd_help_text(PLUGIN_VERSION)
        user_style = get_user_button_style(user_id)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(loc("GP_BTN_BACK"), f"autogp_info_{user_id}", style=user_style)]
        ])
        await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        return

    # 🎛 LOGIC: Trigger Mode Selection
    elif action == "trigmode":
        new_mode = sub_action  # "outgoing" or "manual"
        settings["trigger_mode"] = new_mode
        mode_label = "📤 Outgoing (Auto)" if new_mode == "outgoing" else "🖐 Manual (Force Start)"
        await cb.answer(f"🎛 Trigger Mode: {mode_label}")

    # 🚀 LOGIC: Force Start Confirmation
    elif action == "forceconfirm":
        # Define cycle_mode early to avoid UnboundLocalError
        current_cycle = settings.get("cycle", "global")
        
        if sub_action == "switchglobal":
            settings["cycle"] = "global"
            await save_auto_gp_settings(user_id, settings)
            await cb.answer("🔄 Settings updated: Cycle switched to GLOBAL.", show_alert=False)
            # Re-read to ensure consistency for the next block
            current_cycle = "global"
            sub_action = "prompt" # Proceed to prompt logic below

        if sub_action == "prompt":
            if current_cycle != "global" and not cb.message:
                await cb.answer(
                    "❌ Error: 'Current' mode requires opening dashboard in a chat.\n\n"
                    "💡 Suggestion: Click the [⚠️ Switch to Global & Start] button or use .autogp in a group.", 
                    show_alert=True
                )
                return
            
            cycle_map = {
                "global": "Global (All Targets)",
                "current_force": "Current (Force Purge ⚠️)",
                "current_smart": "Current (Smart/Safe 🔆)"
            }
            cycle_str = cycle_map.get(current_cycle, "Global")

            confirm_text = (
                f"<b>🚀 FORCE START — Konfirmasi</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"⚠️ <b>Apakah Anda yakin ingin menjalankan siklus penghapusan SEKARANG?</b>\n\n"
                f"<blockquote expandable>"
                f"<b>Cycle:</b> <code>{cycle_str}</code>\n"
                f"<b>Target:</b> <code>{settings.get('target', 'all').capitalize()}</code>\n"
                f"<b>Limit:</b> <code>{settings['limit']} msg/chat</code>\n"
                f"<b>Mode:</b> <code>{settings.get('mode', 'newest').capitalize()}</code>\n"
                f"<b>Delay/Chat:</b> <code>{settings['delay']}s</code>\n"
                f"<b>Delay/Msg:</b> <code>{settings.get('delay_msg', 1.0)}s</code>\n"
                f"<b>Blacklisted:</b> <code>{len(settings['blacklist'])} chats</code>\n"
                f"</blockquote>\n\n"
                f"<i>Tekan [✅ Yes] untuk memulai atau [❌ No] untuk kembali ke dashboard.</i>"
            )
            user_style = get_user_button_style(user_id)
            confirm_kb = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Yes, Start Now!", f"autogp_forceconfirm_yes_{user_id}", style=user_style),
                    InlineKeyboardButton("❌ No, Go Back", f"autogp_back_{user_id}", style=user_style)
                ]
            ])
            try:
                await cb.edit_message_text(confirm_text, reply_markup=confirm_kb, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
            except MessageNotModified:
                pass
            return
        
        elif sub_action == "yes":
            # Execute Force Start
            # Provide IMMEDIATE feedback by editing the message to show start progress
            try:
                confirm_txt = "🚀 <b>Siklus Manual Dimulai!</b>\n━━━━━━━━━━━━━━━━━━━━\n<i>Memulai pemindaian target... Harap cek grup log untuk detail progres.</i>"
                await cb.edit_message_text(confirm_txt, parse_mode=enums.ParseMode.HTML)
            except: pass
            
            # Answer only ONCE
            await cb.answer("🚀 Auto-GP: Siklus manual telah dipicu!", show_alert=False)
            
            # Find the userbot client for this user_id
            target_client = next((cl for cl in Altruix.clients if cl.me and cl.me.id == user_id), None)
            
            Altruix.log(f"🔎 Auto-GP | Target Client Lookup: {'FOUND' if target_client else 'NOT FOUND'} for ID {user_id}", level=20)
            
            if not target_client:
                # Log current clients to help debug mismatch
                client_ids = [c.me.id for c in Altruix.clients if c.me]
                Altruix.log(f"❌ Auto-GP | Session mismatch. Available IDs: {client_ids}", level=30)
                await cb.answer("❌ Error: Active session not found for this account.", show_alert=True)
                return
            
            cycle_label = settings.get("cycle", "global").capitalize()
            cycle_mode = settings.get("cycle", "global")
            
            # --- START EXECUTION ---
            success = False
            if cycle_mode == "global":
                Altruix.log(f"🚀 Auto-GP | Force Start Triggered by {cb.from_user.id} for target {target_client.me.id} (Global Cycle)", level=20)
                task = asyncio.create_task(auto_gp_global_cycle(target_client, force=True))
                ACTIVE_PURGE_TASKS[user_id] = task
                success = True
            elif cycle_mode == "current_force":
                force_chat_id = cb.message.chat.id if cb.message else None
                if force_chat_id:
                    Altruix.log(f"🚀 Auto-GP | Force Start Triggered by {cb.from_user.id} for target {target_client.me.id} in chat {force_chat_id} (Force Purge)", level=20)
                    task = asyncio.create_task(auto_gp_perform_purge(target_client, force_chat_id, bypass_guards=True, force=True))
                    ACTIVE_PURGE_TASKS[user_id] = task
                    success = True
                else:
                    Altruix.log(f"⚠️ Auto-GP | Force Start FAILED: Context missing (Inline Mode) for 'Current Force' mode.", level=30)
                    await cb.answer("❌ Error: 'Current' mode requires opening dashboard in a chat, NOT via @bot Assistant.", show_alert=True)
                    return
            elif cycle_mode == "current_smart":
                force_chat_id = cb.message.chat.id if cb.message else None
                if force_chat_id:
                    Altruix.log(f"🚀 Auto-GP | Force Start Triggered by {cb.from_user.id} for target {target_client.me.id} in chat {force_chat_id} (Smart Purge)", level=20)
                    task = asyncio.create_task(auto_gp_perform_purge(target_client, force_chat_id, bypass_guards=False, force=True))
                    ACTIVE_PURGE_TASKS[user_id] = task
                    success = True
                else:
                    Altruix.log(f"⚠️ Auto-GP | Force Start FAILED: Context missing (Inline Mode) for 'Current Smart' mode.", level=30)
                    await cb.answer("❌ Error: 'Current' mode requires opening dashboard in a chat, NOT via @bot Assistant.", show_alert=True)
                    return

            if not success: return

            # --- ONLY UPON SUCCESS: Notify & Feedback ---
            # (Answer already called above)
            
            try:
                import os
                bot_sender = Altruix.bot_manager.get_bot(user_id) or Altruix.bot
                log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID or 0))
                
                log_text = (
                    f"<blockquote expandable>⚠️ <b>AUTO GLOBAL PURGEME - MANUAL START</b>\n\n"
                    f"👤 <b>Account:</b> <a href='tg://user?id={target_client.me.id}'>{html.escape(target_client.me.first_name)}</a>\n"
                    f"🔄 <b>Cycle:</b> <code>{cycle_label}</code>\n"
                    f"🚀 <b>Status:</b> Force Start Triggered via Dashboard confirmation.</blockquote>"
                )
                
                await bot_sender.send_message(
                    log_chat_id,
                    log_text,
                    disable_web_page_preview=True,
                    parse_mode=enums.ParseMode.HTML
                )
            except Exception as e: 
                Altruix.log(f"⚠️ Auto-GP Force Log Failed: {e}", level=30)
            
            Altruix.log(f"Auto-GP Force Log Status: {'SENT' if success else 'FAILED'}", level=20)
            
            # RE-RENDER DASHBOARD to show updated status
            # Force settings reload to ensure UI reflects the latest
            settings = await get_auto_gp_settings(user_id)
            text = await get_auto_gp_status_text(user_id, chat_id)
            kb = get_auto_gp_kb(user_id, settings, chat_id)
            try:
                await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
            except MessageNotModified: pass
            return

            
            # Fall through to re-render dashboard with updated status

    # 🔙 LOGIC: Return to Dashboard
    elif action == "back":
        await cb.answer()
        # Fall through to re-render main dashboard

    # 🔄 LOGIC: Force UI Update
    elif action == "refresh":
        await cb.answer("🔄 Refreshing dashboard data...")

    # ❌ LOGIC: Session Termination
    elif action == "close":
        await cb.answer("Dashboard session closed.")
        try:
            if cb.message:
                await cb.message.delete()
            else:
                # Handle Inline Mode (sent via @bot assistant)
                await cb.edit_message_text(
                    "<b>❌ Dashboard Closed</b>\n<i>This session has been terminated.</i>", 
                    parse_mode=enums.ParseMode.HTML
                )
        except Exception:
            # Fallback for permission errors or old messages
            try:
                await cb.edit_message_text(
                    "<b>❌ Dashboard Closed</b>", 
                    parse_mode=enums.ParseMode.HTML
                )
            except: pass
        return

    # FINAL: Commit changes to DB and repopulate UI
    await save_auto_gp_settings(user_id, settings)
    
    # Check if we should re-render a sub-menu instead of main dashboard
    submenu_actions = ["target", "cycle", "trigmode", "limit", "delay", "delaymsg", "mode", "off", "keep", "batch", "bdelay", "bmsgdelay"]
    if action in submenu_actions:
        menu_type = action
        if action == "off": menu_type = "offset"
        elif action == "trigmode": menu_type = "trigger"
        elif action == "keep": menu_type = "keeprecent"
        elif action == "delay": menu_type = "delaychat"
        elif action in ["batch", "bdelay", "bmsgdelay"]: menu_type = "batch"
        
        text = get_autogp_submenu_text(settings, menu_type)
        kb = get_autogp_submenu_kb(user_id, settings, menu_type, chat_id)
    else:
        text = await get_auto_gp_status_text(user_id, chat_id)
        kb = get_auto_gp_kb(user_id, settings, chat_id)
    
    try:
        await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
    except MessageNotModified: pass

# Handle Inline Dashboard Requests (via @bot)
@Altruix.bot.on_inline_query(filters.regex(r"^autogp_menu_uid_(?P<uid>\d+)"))
@log_errors
async def autogp_inline_handler(client: Client, query: InlineQuery):
    """
    Responds to inline query (triggered by @bot assistant).
    Allows opening the dashboard anywhere with a premium UI.
    """
    try:
        user_id = int(query.matches[0].group("uid"))
        
        # Security: Only owner/sudo can trigger their own menu
        from Main.utils.access_control import is_authorized_user
        if not is_authorized_user(query.from_user.id, Altruix.config.OWNER_USERS_ID, Altruix.config.SUDO_USERS_ID):
             return await query.answer([], cache_time=0)
        
        # Build Dashboard View
        text = await get_auto_gp_status_text(user_id)
        settings = await get_auto_gp_settings(user_id)
        kb = get_auto_gp_kb(user_id, settings)
        
        await query.answer(
            results=[
                InlineQueryResultArticle(
                    title="🤖 Auto Global Purgeme Dashboard",
                    description=f"Configure automated purging for account {user_id}",
                    input_message_content=InputTextMessageContent(
                        text,
                        parse_mode=enums.ParseMode.HTML,
                        disable_web_page_preview=True
                    ),
                    reply_markup=kb
                )
            ],
            cache_time=0
        )
    except Exception as e:
        logger.error(f"Auto-GP Inline Handler Critical Error: {e}")

@log_errors
async def auto_gp_perform_purge(client: Client, chat_id: int, trigger_msg_id: int = None, message: Message = None, bypass_guards: bool = False, force: bool = False, suppress_log: bool = False):
    """
    The background engine that performs the deletions.
    Triggered for every outgoing message when Auto-GP is ON.
    Locked PER CHAT to prevent redundant background tasks for the same chat.
    If force=True, bypasses the master status check.
    """
    user_id = client.me.id
    chat_lock = await get_chat_lock(user_id, chat_id)
    
    if chat_lock.locked():
        Altruix.log(f"🕵️ Auto-GP | Purge already in progress for chat {chat_id}. Skipping redundant call.", level=20)
        return 0

    async with chat_lock:
        settings = await get_auto_gp_settings(user_id)
        
        # 🛑 Master Switch Check (Bypassed if force=True)
        if not force and not settings["status"]:
            Altruix.log(f"💤 Auto-GP | Status is OFF for user {user_id}. Skipping.", level=20)
            return 0
        
        # 🛑 Blacklist & Trigger Guard (Feature 1: Respect Blacklist)
        if not bypass_guards:
            respect_bl = settings.get("respect_bl", True)
            if respect_bl and chat_id in settings["blacklist"]:
                Altruix.log(f"🕵️ Auto-GP | Respecting Blacklist for chat {chat_id}. Trigger Skipped.", level=20)
                return 0
            elif chat_id in settings["blacklist"] and not respect_bl:
                Altruix.log(f"⚠️ Auto-GP | Chat {chat_id} is blacklisted but 'Respect Blacklist' is OFF. Proceeding.", level=20)
                # We don't return here if respect_bl is OFF, allowing it to proceed (useful for specific configs)
                pass
            elif chat_id in settings["blacklist"]: 
                Altruix.log(f"🕵️ Auto-GP | Chat {chat_id} is blacklisted. Skipping.", level=20)
                return 0

        # ⌨️ Feature 2: Command Response Bypass (Skip CMDs)
        if not bypass_guards and settings.get("skip_cmds", True):
            # 1. Skip if the trigger message itself is a command
            if message and message.text:
                prefixes = [Altruix.config.PREFIX_OWNER_USER or ".", Altruix.config.PREFIX_SUDO_USERS or "!", "/"]
                if any(message.text.startswith(p) for p in prefixes):
                    Altruix.log(f"⌨️ Auto-GP | Trigger message is a command. Skipping cycle.", level=20)
                    return 0
            # 2. Skip if the trigger message is an edited message (often a command response update)
            if message and message.edit_date:
                 Altruix.log(f"⌨️ Auto-GP | Trigger message is an EDIT. Skipping cycle.", level=20)
                 return 0
            # 3. Skip if the trigger message is sent via a bot (Feature: via_bot bypass)
            if message and message.via_bot:
                 Altruix.log(f"⌨️ Auto-GP | Trigger message is sent VIA BOT (@{message.via_bot.username}). Skipping cycle.", level=20)
                 return 0
        
        # 🎯 Get Chat context (avoid redundant API call if message is provided)
        chat = None
        if message and message.chat:
            chat = message.chat
        else:
            try:
                # Set a timeout for get_chat to prevent hanging
                chat = await asyncio.wait_for(client.get_chat(chat_id), timeout=5.0)
            except Exception as e:
                Altruix.log(f"💥 Auto-GP | Failed to get chat {chat_id} (Timeout/Error): {e}", level=30)
                return 0

        if not chat:
            return 0

        # Use message.id as trigger if provided
        current_trigger_id = trigger_msg_id or (message.id if message else None)

        # 🔧 Configuration extraction (Moved up for logging)
        limit = settings["limit"]
        target_filters = settings["filters"]
        mode = settings.get("mode", "newest")
        offset = settings.get("offset", 0)
        delay_msg = settings.get("delay_msg", 1.0)
        delay_chat = settings.get("delay", 1.0)

        # 🔗 Construct Chat Hyperlink
        chat_title = chat.title or "Private"
        chat_hyperlink = html.escape(chat_title)
        if message and message.link:
            chat_hyperlink = f"<a href='{message.link}'>{html.escape(chat_title)}</a>"
        elif chat.username:
            chat_hyperlink = f"<a href='https://t.me/{chat.username}'>{html.escape(chat_title)}</a>"
        elif str(chat_id).startswith("-100"):
            stripped_id = str(chat_id)[4:]
            chat_hyperlink = f"<a href='https://t.me/c/{stripped_id}/999999999'>{html.escape(chat_title)}</a>"
        else:
            chat_hyperlink = f"<a href='tg://user?id={chat_id}'>{html.escape(chat_title)}</a>"

        # 🎯 Target Type Check (Bypassed in Current Mode)
        if not bypass_guards:
            target = settings.get("target", "all")
            # Normalize chat type to string for consistent comparison
            c_type = str(chat.type).lower()
            if c_type.startswith("chattype."): c_type = c_type.split("chattype.")[1]
            
            if target == "groups" and c_type not in ["group", "supergroup"]:
                Altruix.log(f"🕵️ Auto-GP | Chat {chat_id} type {c_type} mismatch (Target: groups). Skipping.", level=20, client=client)
                return 0
            if target == "personal" and c_type != "private":
                Altruix.log(f"🕵️ Auto-GP | Chat {chat_id} type {c_type} mismatch (Target: personal). Skipping.", level=20, client=client)
                return 0

        # 👑 GUARD: Admin Rights Filter (Bypassed in Current Mode)
        if not bypass_guards:
            if settings["admin_filter"] != "all":
                try:
                    if c_type in ["group", "supergroup"]:
                        me = await chat.get_member("me")
                        is_admin = me.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]
                        if settings["admin_filter"] == "admin" and not is_admin: return 0
                        if settings["admin_filter"] == "non_admin" and is_admin: return 0
                except Exception as e:
                    logger.debug(f"Admin Check Failed for {chat_id}: {e}")
                    if settings["admin_filter"] == "admin": return 0

        # 📢 STEP 0: Initial Progress Notification (Sent ONLY if all guards pass)
        log_msg = None
        if settings.get("notify", True):
            try:
                target_idx = -1
                for i, c in enumerate(Altruix.clients):
                    if c.me.id == user_id:
                        target_idx = i; break
                
                if target_idx != -1:
                    Altruix.log(f"📡 Auto-GP | Sending 'Processing' log for chat {chat_id}...", level=20, client=client)
                    log_msg = await send_log_notification(
                        client, "auto_global_purgeme", target_idx, client.me, True, 
                        additional_info={
                            "Type": "🤖 Auto-GP Processing...",
                            "Chat": chat_hyperlink,
                            "ChatID": f"{chat_id}",
                            "Status": "🔍 Scanning/Cleaning...",
                            "Delay/Msg": f"{delay_msg}s",
                            "Delay/Chat": f"{delay_chat}s"
                        }
                    )
            except Exception as e:
                Altruix.log(f"⚠️ Auto-GP Initial Log Error: {e}", level=30, client=client)
        
        # 🔍 STEP 1: Search and Match messages
        collected_ids = []
        keep_recent = settings.get("keep_recent", 6)
        skip_cmds = settings.get("skip_cmds", True)
        prefixes = [Altruix.config.PREFIX_OWNER_USER or ".", Altruix.config.PREFIX_SUDO_USERS or "!"]
        
        Altruix.log(f"🔎 Auto-GP | Scanning chat {chat_id} (Limit: {limit}, Offset: {offset}, Keep: {keep_recent})...", level=20, client=client)
        
        # Fetch Logic: Scan deep enough to find filtered messages buried under noise.
        max_scan = max(limit * 4 + offset + keep_recent, 100) 
        match_count = 0 # Sequential count of 'me' messages for keep_recent logic
        scanned_count = 0 # Total messages processed from search
        
        try:
            log_depth = f"(Target: {limit}, Max Depth: {max_scan})"
            Altruix.log(f"🔎 Auto-GP | Scanning {chat_id} {log_depth}...", level=20, client=client)
            
            async for msg in client.search_messages(chat_id, from_user="me"):
                scanned_count += 1
                if scanned_count > max_scan:
                    Altruix.log(f"⏹ Auto-GP | Depth reached ({max_scan}). Stopping search for {chat_id}.", level=20, client=client)
                    break
                    
                if current_trigger_id and msg.id == current_trigger_id: continue 
                    
                # ⏳ Feature 3: Keep Recent Messages Buffer
                match_count += 1
                if (not force) and match_count <= keep_recent:
                    continue

                # ⌨️ Feature 2: Skip Commands in scan
                if skip_cmds:
                    if msg.text and any(msg.text.startswith(p) for p in prefixes):
                        continue
                    if msg.via_bot:
                        continue
                should_include = False
                if "all" in target_filters: should_include = True
                else:
                    try:
                    # Media Type Validation Logic
                        if msg.text and "text" in target_filters: should_include = True
                        elif msg.photo and ("photo" in target_filters or "image" in target_filters): should_include = True
                        elif msg.video and "video" in target_filters: should_include = True
                        elif (msg.voice or msg.audio) and "audio" in target_filters: should_include = True
                        elif msg.sticker and "sticker" in target_filters: should_include = True
                        elif msg.animation and ("animation" in target_filters or "gif" in target_filters): should_include = True
                        elif msg.document and ("document" in target_filters or "file" in target_filters): should_include = True
                        elif msg.video_note and ("video_note" in target_filters or "vnote" in target_filters): should_include = True
                        elif msg.voice and "voice" in target_filters: should_include = True
                        elif msg.contact and "contact" in target_filters: should_include = True
                        elif msg.location and "location" in target_filters: should_include = True
                        elif msg.venue and "venue" in target_filters: should_include = True
                        elif msg.game and "game" in target_filters: should_include = True
                        elif msg.poll and "poll" in target_filters: should_include = True
                        elif msg.dice and "dice" in target_filters: should_include = True
                    except: pass
                if should_include:
                    collected_ids.append(msg.id)
                    Altruix.log(f"✅ Auto-GP | Collected message {msg.id} ({len(collected_ids)}/{limit+offset})", level=20, client=client)
        except FloodWait as e:
            wait_time = getattr(e, "value", 10)
            Altruix.log(f"⚠️ Auto-GP | FloodWait during message scan in {chat_id}, tidur {wait_time}s...", level=30, client=client)
            await asyncio.sleep(wait_time + 1)
            return 0
        except Exception as e:
            Altruix.log(f"💥 Auto-GP | Error during message scan in chat {chat_id}: {e}", level=30, client=client)
            return 0

        Altruix.log(f"📊 Auto-GP | Scan complete. Collected: {len(collected_ids)} items.", level=20, client=client)
        if not collected_ids:
            Altruix.log(f"💤 Auto-GP | No messages collected after scanning {scanned_count} messages.", level=20, client=client)
            return 0
            
        # 📏 STEP 2: Application of Search Mode & Offset
        if mode == "oldest": collected_ids.reverse() 
        if offset > 0: collected_ids = collected_ids[offset:] 
        collected_ids = collected_ids[:limit] 
        
        if not collected_ids: return 0

        # 🗑 STEP 3: Execution of Batched Deletions
        deleted_count = 0
        total_matched = len(collected_ids)
        Altruix.log(f"🗑 Auto-GP | Deleting {total_matched} matched messages in chat {chat_id}...", level=20, client=client)
        for i in range(0, total_matched, 100): 
            batch = collected_ids[i:i+100]
            try:
                deleted = await client.delete_messages(chat_id, batch, revoke=True)
                deleted_count += deleted
                if delay_msg > 0: await asyncio.sleep(delay_msg) 
            except FloodWait as e: 
                await asyncio.sleep(e.value + 3)
            except Exception as e: 
                Altruix.log(f"Purge Logic Batch Error (Chat {chat_id}): {e}", level=30, client=client)
        
        # 🔔 STEP 4: Reporting to Telegram Log Group
        if settings.get("notify", True) and deleted_count > 0:
            try:
            # Resolve account index if not already present
                idx = -1
                for i, c in enumerate(Altruix.clients):
                    if c.me.id == user_id:
                        idx = i; break
                
                if idx != -1:
                    final_info = {
                        "Type": "✅ Auto-GP Cycle Complete",
                        "Chat": chat_hyperlink,
                        "ChatID": f"{chat_id}",
                        "Deleted": f"{deleted_count} messages purged",
                        "Limit": f"{limit} items configured",
                        "Filters": f"{', '.join(target_filters)} active",
                        "Delay/Msg": f"{delay_msg}s",
                        "Delay/Chat": f"{delay_chat}s"
                    }
                    
                    Altruix.log(f"✅ Auto-GP | Cycle Complete for {chat_id}. Deleted: {deleted_count}", level=20, client=client)
                    if not suppress_log:
                        await send_log_notification(
                            client, "auto_global_purgeme", idx, client.me, True, 
                            additional_info=final_info,
                            edit_message=log_msg
                        )
            except Exception as e:
                Altruix.log(f"Auto-GP Log Dispatch Error: {e}", level=30, client=client)
        
        return deleted_count

# 🌍 LOCK MANAGEMENT REGISTRY
# Handled at top of file

async def get_user_lock(user_id):
    async with REGISTRY_LOCK:
        if user_id not in GLOBAL_USER_LOCKS:
            GLOBAL_USER_LOCKS[user_id] = asyncio.Lock()
        return GLOBAL_USER_LOCKS[user_id]

async def get_chat_lock(user_id, chat_id):
    async with REGISTRY_LOCK:
        key = (user_id, chat_id)
        if key not in CHAT_PURGE_LOCKS:
            CHAT_PURGE_LOCKS[key] = asyncio.Lock()
        return CHAT_PURGE_LOCKS[key]

@log_errors
async def auto_gp_global_cycle(client: Client, force=False):
    """
    Background engine that scans ALL target chats for deletions.
    """
    if not client or not hasattr(client, 'me') or not client.me:
        Altruix.log("⚠️ Auto-GP Cycle aborted: Client or Client.me is unavailable.", level=30)
        return
        
    user_id = client.me.id
    user_lock = await get_user_lock(user_id)
    
    # 🔒 LOCK GUARD
    if user_lock.locked():
        Altruix.log(f"⚠️ Auto-GP Global Cycle Skipped (Already Running for this user)", level=20, client=client)
        return

    async with user_lock:
        try:
            # 🔄 STEP 1: Settings Retrieval
            Altruix.log(f"🔄 Auto-GP Global Cycle [User: {user_id}] | Fetching settings...", level=20, client=client)
            settings = await get_auto_gp_settings(user_id)
            if not force and not settings["status"]: 
                Altruix.log(f"💤 Auto-GP Global Cycle [User: {user_id}] | Status is OFF. Aborting.", level=20, client=client)
                return

            Altruix.log(f"🚀 Auto-GP Global Cycle Started", level=20, client=client)
            
            # 1. Get Targets
            Altruix.log(f"🔎 Auto-GP Global Cycle [User: {user_id}] | Identifying target chats...", level=20, client=client)
            chats, ignored = await get_auto_gp_target_chats(
                client, settings["target"], settings["admin_filter"], settings["blacklist"]
            )
            
            Altruix.log(f"📊 Auto-GP Global Cycle [User: {user_id}] | Found {len(chats)} target chats ({ignored} ignored).", level=20, client=client)
            
            if not chats:
                Altruix.log(f"💤 Auto-GP Global Cycle [User: {user_id}] | No target chats found. Cycle finished.", level=20, client=client)
                return

            # 2. Iterate & Purge
            delay_chat = settings.get("delay", 1.0)
            
            # Batch Tracking
            batch_size = settings.get("batch_size", 20)
            batch_delay = settings.get("batch_delay", 120.0)
            batch_msg_size = settings.get("batch_msg_size", 40)
            batch_msg_delay = settings.get("batch_msg_delay", 600.0)
            
            chat_count = 0
            msg_count = 0
            total_deleted = 0
            processed_chats = 0
            
            # --- LIVE LOG STATE ---
            log_entries = [] # List of strings: "• (chat_id) : Chat Name | {Count} msgs"
            live_log_msgs = {} # part_number -> Message object
            
            # Use random task id visually link parts
            import random
            task_id = random.randint(100, 999)
            
            # Determine Bot (Custom Bot Priority)
            bot = Altruix.bot_manager.get_bot(user_id) or Altruix.bot
            log_chat_id = Altruix.log_chat
            
            # Determine pagination
            chats_per_part = 30 # Safe chunk size for HTML characters to prevent link breaks
            
            async def _update_batch_log(is_final=False):
                if not log_chat_id: return
                
                # Determine how many parts we need
                total_parts = max(1, (len(log_entries) + chats_per_part - 1) // chats_per_part)
                # Ensure we always report at least Part 1 even if 0 processed yet
                if len(log_entries) == 0: total_parts = 1

                for part in range(1, total_parts + 1):
                    # Calculate indices for this part
                    start_idx = (part - 1) * chats_per_part
                    end_idx = start_idx + chats_per_part
                    chunk_entries = log_entries[start_idx:end_idx]
                    
                    is_last_part = (part == total_parts)
                    
                    # Formatting Header
                    part_label = f" (Part {part})" if total_parts > 1 else ""
                    header = (
                        f"📋 <b>Batch Log — Task #{task_id}{part_label}</b>\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"📊 <b>{processed_chats}</b>/{len(chats)} │ ✅ <b>{total_deleted}</b> msgs\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                    )
                    
                    # Formatting Body
                    body = ""
                    for entry in chunk_entries:
                        body += f"{entry}\n"

                    # Formatting Footer statuses based on part position
                    if is_last_part:
                         status_line = "🏁 <b>Completed</b>" if is_final else "🔄 <i>Processing...</i>"
                    else:
                         status_line = "⏭ <i>Continued below...</i>"
                         
                    footer = f"━━━━━━━━━━━━━━━━━━\n{status_line}"
                    
                    full_text = f"<blockquote expandable>{header}{body}{footer}</blockquote>"
                    
                    # --- SMART EDIT LOGIC ---
                    # Only edit a part if:
                    #   - It's the LATEST (last) part (active editing)
                    # This prevents old parts (e.g. Part 1) from having their headers
                    # updated with total stats from Part 2/3, which is confusing.
                    
                    try:
                        if part in live_log_msgs and part == total_parts:
                            # Edit existing message in-place
                            try:
                                await live_log_msgs[part].edit_text(full_text, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
                            except MessageNotModified:
                                pass
                            except Exception as edit_err:
                                Altruix.log(f"Auto-GP Live Log Edit Error (Part {part}): {edit_err}", level=30, client=client)
                        elif part not in live_log_msgs:
                            # Send a brand new message for this part
                            msg = await bot.send_message(log_chat_id, full_text, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
                            live_log_msgs[part] = msg
                    except Exception as e:
                        Altruix.log(f"Auto-GP Live Log Error (Part {part}): {e}", level=30, client=client)

            # --- PROCESS CHATS ---
            for i, chat_info in enumerate(chats):
                chat_id = chat_info["id"]
                try:
                    # Perform purge on this chat (suppress individual log if global cycle is reporting)
                    deleted_in_this_chat = await auto_gp_perform_purge(client, chat_id, message=None, force=force, suppress_log=True)
                    deleted_in_this_chat = deleted_in_this_chat or 0 # Fallback safety guard
                    
                    chat_name = "Unknown Chat"
                    c_type_str = "group" # fallback default
                    is_bot = False
                    
                    try:
                        c_info = await client.get_chat(chat_id)
                        chat_name = c_info.title or c_info.first_name or f"Chat {chat_id}"
                        c_type_str = str(c_info.type).lower()
                        if hasattr(c_info, "username") and c_info.username and c_info.username.lower().endswith("bot"):
                            is_bot = True
                    except: pass
                    
                    # 🎭 Determine Chat Emoji 
                    type_emoji = "👥"
                    if "channel" in c_type_str: type_emoji = "📢"
                    elif "private" in c_type_str or "bot" in c_type_str:
                         type_emoji = "🤖" if is_bot else "👩🏻\u200d🦳"
                    
                    # ✂️ Truncate Chat Name to 15 chars
                    safe_chat_name = chat_name
                    if len(chat_name) > 15: 
                        safe_chat_name = chat_name[:15] + "..."
                        
                    # Track result (Adding sequence number i+1)
                    icon = "✅" if deleted_in_this_chat > 0 else "⏭️"
                    chat_link = f"https://t.me/c/{str(chat_id)[4:] if str(chat_id).startswith('-100') else chat_id}/1"
                    log_entries.append(f"{icon} {i+1}. (<code>{chat_id}</code>) : {type_emoji} <a href='{chat_link}'>{html.escape(safe_chat_name)}</a> | <code>{deleted_in_this_chat}</code> msgs")
                    
                    if deleted_in_this_chat:
                        total_deleted += deleted_in_this_chat
                        msg_count += deleted_in_this_chat
                        processed_chats += 1
                    else:
                        # Even if 0 deleted, we count it as processed for the progress bar
                        processed_chats += 1
                    
                    chat_count += 1
                    
                    # Update Log After Each Chat
                    await _update_batch_log()

                    # ✅ Feature: Batch per-message delay
                    if msg_count >= batch_msg_size:
                        Altruix.log(f"⏳ Auto-GP | Batch Message Limit Reached ({msg_count}). Resting for {int(batch_msg_delay/60)}m...", level=20, client=client)
                        await asyncio.sleep(batch_msg_delay)
                        msg_count = 0 

                    # ✅ Feature: Batch per-chat delay
                    elif chat_count >= batch_size:
                        Altruix.log(f"⏳ Auto-GP | Batch Chat Limit Reached ({chat_count}). Resting for {int(batch_delay/60)}m...", level=20, client=client)
                        await asyncio.sleep(batch_delay)
                        chat_count = 0 
                    
                    # Normal delay between chats
                    elif i < len(chats) - 1 and delay_chat > 0:
                        await asyncio.sleep(delay_chat)
                        
                except Exception as e:
                    Altruix.log(f"⚠️ Auto-GP Global Cycle Error on Chat {chat_id}: {e}", level=30, client=client)
            
            # Final Update
            await _update_batch_log(is_final=True)
            
            Altruix.log(f"✅ Auto-GP Global Cycle Finished | User: {user_id} | Deleted: {total_deleted}", level=20, client=client)
            
            # --- SEND CYCLE COMPLETED NOTIFICATION ---
            if settings.get("notify", True) and log_chat_id:
                try:
                    c_mode = "Global" if not force else "Global (Forced)"
                    end_log = (
                        f"<blockquote expandable>✅ <b>AUTO GLOBAL PURGEME - CYCLE COMPLETED</b>\n\n"
                        f"👤 <b>Account:</b> <a href='tg://user?id={client.me.id}'>{html.escape(client.me.first_name)}</a>\n"
                        f"🔄 <b>Cycle:</b> <code>{c_mode}</code>\n"
                        f"🎯 <b>Targets:</b> {processed_chats}/{len(chats)} chats processed\n"
                        f"🗑 <b>Purged:</b> <code>{total_deleted}</code> total messages deleted.</blockquote>"
                    )
                    await bot.send_message(
                        log_chat_id,
                        end_log,
                        disable_web_page_preview=True,
                        parse_mode=enums.ParseMode.HTML
                    )
                except Exception as e:
                    Altruix.log(f"Auto-GP End Log Error: {e}", level=30, client=client)
            
        except Exception as e:
            # Enhanced error logging with traceback insight
            tb = traceback.format_exc()
            Altruix.log(f"💥 Auto-GP Global Cycle Critical Error: {e}\n📍 Traceback context:\n{tb}", level=40, client=client)

# 🆕 BOT MESSAGE HANDLER: Catch user input for blacklist add-chat flow
# Works in both private and group chats; strictly validates sender authorization.
@Altruix.bot.on_message(~filters.bot & ~filters.channel, group=50)
@log_errors
async def autogp_bl_add_input_handler(client: Client, message: Message):
    """
    Catches user input when in 'add chat to blacklist' state.
    Expects a chat_id (numeric) or @username.
    
    Security:
    - Only processes messages from the EXACT user who pressed '➕ Add Chat'
    - Validates via from_user_id stored in AUTO_GP_DASH_STATE
    - All other messages in the same chat are silently ignored
    """
    # Must have a sender (no anonymous/channel messages)
    if not message.from_user:
        return
    
    # Check if this user has an active add-chat state
    user_id_key = f"bl_add_{message.from_user.id}"
    
    async with STATE_LOCK:
        state = AUTO_GP_DASH_STATE.get(user_id_key)
    
    if not state:
        return  # Not in add-chat state for this user, ignore
    
    # 🔒 STRICT AUTH: Only accept input from the exact user who pressed the button
    if message.from_user.id != state["from_user_id"]:
        return  # Silently ignore messages from anyone else
    
    user_input = (message.text or "").strip()
    user_id = state["user_id"]
    log_chat_id = state.get("log_chat_id", "me")
    
    # Handle /cancel command
    if user_input.lower() == "/cancel":
        async with STATE_LOCK:
            AUTO_GP_DASH_STATE.pop(user_id_key, None)
        try:
            await client.delete_messages(log_chat_id, [state["prompt_msg_id"], message.id])
        except: pass
        return
    
    # Validate input: must be numeric chat_id or @username
    if not user_input:
        return
    
    resolved_chat_id = None
    resolved_name = "Unknown"
    
    try:
        # Try to resolve via the userbot client (has more access)
        target_client = next((cl for cl in Altruix.clients if cl.me and cl.me.id == user_id), None)
        resolve_client = target_client or client
        
        if user_input.lstrip('-').isdigit():
            # Numeric chat_id
            target_id = int(user_input)
            try:
                chat_info = await resolve_client.get_chat(target_id)
                resolved_chat_id = chat_info.id
                resolved_name = chat_info.title or chat_info.first_name or str(resolved_chat_id)
            except Exception:
                resolved_chat_id = target_id
                resolved_name = f"Chat {target_id}"
        elif user_input.startswith("@"):
            # @username
            chat_info = await resolve_client.get_chat(user_input)
            resolved_chat_id = chat_info.id
            resolved_name = chat_info.title or chat_info.first_name or user_input
        else:
            # Try as-is (could be username without @)
            chat_info = await resolve_client.get_chat(user_input)
            resolved_chat_id = chat_info.id
            resolved_name = chat_info.title or chat_info.first_name or user_input
    except Exception as e:
        await client.send_message(
            log_chat_id,
            f"❌ <b>Could not resolve:</b> <code>{html.escape(user_input)}</code>\n"
            f"<i>Error: {html.escape(str(e))}</i>\n\n"
            "Please try again with a valid chat ID or @username.",
        )
        try:
            await message.delete()
        except: pass
        return
    
    if resolved_chat_id is None:
        await client.send_message(
            log_chat_id,
            "❌ <b>Invalid input.</b> Send a numeric Chat ID or @username."
        )
        try:
            await message.delete()
        except: pass
        return
    
    # Check if already blacklisted
    settings = await get_auto_gp_settings(user_id)
    if resolved_chat_id in settings["blacklist"]:
        # Edit the prompt message with "already in blacklist" text
        try:
            await client.edit_message_text(
                log_chat_id, state["prompt_msg_id"],
                f"<blockquote expandable>⚠️ {html.escape(resolved_name)} ({resolved_chat_id}) is already in the blacklist.</blockquote>"
            )
        except Exception as e:
            logger.error(f"Failed to edit prompt with already-in-blacklist text: {e}")

        # Clean up state (STOP deleting input message)
        async with STATE_LOCK:
            AUTO_GP_DASH_STATE.pop(user_id_key, None)
        return
    
    # Add to blacklist
    settings["blacklist"].append(resolved_chat_id)
    await save_auto_gp_settings(user_id, settings)
    
    # Edit the prompt message with success text
    try:
        await client.edit_message_text(
            log_chat_id, state["prompt_msg_id"],
            f"<blockquote expandable>✅ {html.escape(resolved_name)} ({resolved_chat_id}) has been ADDED to Auto-GP Blacklist.\n"
            f"📋 Total blacklisted: <code>{len(settings['blacklist'])}</code> chats\n\n"
            f"Use .autogpblist to view all blacklisted chats.</blockquote>"
        )
    except Exception as e:
        logger.error(f"Failed to edit prompt with success text: {e}")

    # Clean up state (STOP deleting input message)
    async with STATE_LOCK:
        AUTO_GP_DASH_STATE.pop(user_id_key, None)
    
    # Refresh the dashboard blacklist view if we have the dashboard message
    try:
        kb = get_autogp_bl_kb(user_id, settings, 0)
        text = await get_autogp_bl_text(client, settings, 0)
        await client.edit_message_text(
            message.chat.id, state["dash_msg_id"],
            text, reply_markup=kb, disable_web_page_preview=True
        )
    except Exception as e:
        logger.debug(f"Auto-GP BL Dashboard refresh error: {e}")
