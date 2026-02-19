# Main/internals/settings_handlers/auto_global_purgeme.py
# Implementation of Auto Global Purgeme with full feature parity and premium UI.

import asyncio
import logging
import html
import re
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

async def get_auto_gp_settings(user_id):
    """
    Fetch Auto-GP settings for a specific user from the database/environment.
    Provides fallback defaults to ensure stability even if configuration is missing.
    """
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

    return {
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
        "blacklist": blacklist
    }

async def save_auto_gp_settings(user_id, settings):
    """
    Sync current dictionary of settings back to the database.
    Ensures persistent storage across sessions and restarts.
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
    status_emoji = "🟢" if is_on else "🔴"
    status_text = "ENABLED" if is_on else "DISABLED"
    
    target_str = loc(f"GP_BTN_TARGET_{settings['target'].upper()}")
    
    cycle_map = {
        "global": "Global (All Targets)",
        "current_force": "Current (Force Purge ⚠️)",
        "current_smart": "Current (Smart/Safe 🔆)"
    }
    cycle_str = cycle_map.get(settings["cycle"], "Global")
    
    mode_str = settings["mode"].capitalize()
    filters_display = ", ".join([loc(f"GP_BTN_{f.upper()}") for f in settings["filters"]])
    admin_filter_text = loc(f"GP_BTN_ADMIN_FILTER_{settings['admin_filter'].upper()}")
    notify_str = "✅ ON" if settings["notify"] else "❌ OFF"
    
    blacklist_status = ""
    if current_chat_id:
        is_bl = current_chat_id in settings["blacklist"]
        blacklist_status = f"\n📍 <b>Current Chat:</b> {'🚫 Blacklisted (Protected)' if is_bl else '✅ Active'}"
        
        # Add warning if Force mode would bypass blacklist
        if is_bl and settings["cycle"] == "current_force":
             blacklist_status += " ⚠️ <b>(BYPASSED by Force Mode)</b>"

    # ... (Account name logic same) ...
    account_name = str(user_id)
    for cl in Altruix.clients:
        if cl.me and cl.me.id == user_id:
            first = cl.me.first_name or ""
            last = cl.me.last_name or ""
            account_name = f"{first} {last}".strip() or str(user_id)
            break

    text = (
        f"<b>🤖 AUTO GLOBAL PURGEME DASHBOARD</b>\n\n"
        f"👤 <b>Account:</b> {account_name}\n"
        f"🎯 <b>Target:</b> {target_str} | <b>🔄 Cycle:</b> {cycle_str}\n"
        f"<b>📊 Settings:</b> [ <code>Lmt:{settings['limit']}msg | Dly/Chat:{settings['delay']}s | Dly/Msg:{settings['delay_msg']}s</code> ]\n"
        f"<b>🛠 Config:</b> [ <code>Mode:{mode_str} | Offset:{settings['offset']}</code> ]\n"
        f"<b>🧹 Filters:</b> <code>{filters_display}</code>\n"
        f"<b>👑 Admin Filter:</b> {admin_filter_text} | <b>🔔 Notif:</b> {notify_str}\n"
        f"<b>🚫 Blacklisted:</b> <code>{len(settings['blacklist'])} chats</code>{blacklist_status}\n\n"
        f"<b>Status: {status_emoji} {status_text}</b>\n\n"
        f"<i>Automated purging triggers every time you send an outgoing message.</i>"
    )
    return text

def get_auto_gp_kb(user_id, settings, current_chat_id=None):
    """
    Constructs the complex multi-row Inline Keyboard.
    """
    kb = []
    target = settings.get("target", "all")
    cycle = settings.get("cycle", "global")
    mode = settings.get("mode", "newest")
    
    # 🟢 Row: Master Status Toggle
    status_btn = "🔴 Disable Auto-GP Now" if settings["status"] else "🟢 Enable Auto-GP Now"
    kb.append([InlineKeyboardButton(status_btn, f"autogp_toggle_{user_id}")])
    
    # 🎯 Row: Target Type Selection
    kb.append([
        InlineKeyboardButton(("✅ " if target == "all" else "") + loc("GP_BTN_TARGET_ALL"), f"autogp_target_all_{user_id}"),
        InlineKeyboardButton(("✅ " if target == "groups" else "") + loc("GP_BTN_TARGET_GROUPS"), f"autogp_target_groups_{user_id}"),
        InlineKeyboardButton(("✅ " if target == "personal" else "") + loc("GP_BTN_TARGET_PERSONAL"), f"autogp_target_personal_{user_id}")
    ])

    # 🔄 Row: Cycle Target (Global / Smart / Force)
    # [Cycle: Global/Smart/Force]
    # [Global][Smart][Force]
    kb.append([
        InlineKeyboardButton(f"Cycle Mode: {cycle.upper().replace('_', ' ')}", "autogp_noop")
    ])
    kb.append([
        InlineKeyboardButton(("✅ " if cycle == "global" else "") + "Global 🌍", f"autogp_cycle_global_{user_id}"),
        InlineKeyboardButton(("✅ " if cycle == "current_smart" else "") + "Smart 🔆", f"autogp_cycle_current_smart_{user_id}"),
        InlineKeyboardButton(("✅ " if cycle == "current_force" else "") + "Force ⚠️", f"autogp_cycle_current_force_{user_id}")
    ])
    
    # ... (Rest of rows same logic) ...
    # 🔢 Row: Purge Limit Control (-/+ 2)
    kb.append([
        InlineKeyboardButton(f"Limit: {settings['limit']}", "autogp_noop"),
        InlineKeyboardButton("-2", f"autogp_limit_m2_{user_id}"),
        InlineKeyboardButton("+2", f"autogp_limit_p2_{user_id}")
    ])
    
    # ⏱ Row: Inter-Chat Delay (in seconds)
    kb.append([
        InlineKeyboardButton(f"Delay/Chat: {settings['delay']}s", "autogp_noop"),
        InlineKeyboardButton("-1s", f"autogp_delay_m1_{user_id}"),
        InlineKeyboardButton("+1s", f"autogp_delay_p1_{user_id}")
    ])

    # ⏱ Row: Inter-Message Delay (in seconds)
    kb.append([
        InlineKeyboardButton(f"Delay/Msg: {settings['delay_msg']}s", "autogp_noop"),
        InlineKeyboardButton("-0.5s", f"autogp_delaymsg_m05_{user_id}"),
        InlineKeyboardButton("+0.5s", f"autogp_delaymsg_p05_{user_id}")
    ])
    
    # ⚙️ Row: Mode Selection (Newest / Oldest)
    kb.append([
        InlineKeyboardButton(f"Mode: {mode.capitalize()}", "autogp_noop"),
        InlineKeyboardButton(("✅ " if mode == "newest" else "") + loc("GP_BTN_MODE_NEWEST"), f"autogp_mode_newest_{user_id}"),
        InlineKeyboardButton(("✅ " if mode == "oldest" else "") + loc("GP_BTN_MODE_OLDEST"), f"autogp_mode_oldest_{user_id}")
    ])

    # 📏 Row: Skip Offset Control
    kb.append([
        InlineKeyboardButton(f"Offset: {settings['offset']}", "autogp_noop"),
        InlineKeyboardButton("-5", f"autogp_off_m5_{user_id}"),
        InlineKeyboardButton("+5", f"autogp_off_p5_{user_id}"),
        InlineKeyboardButton(loc("GP_BTN_RESET"), f"autogp_off_reset_{user_id}")
    ])

    # 🔔 Row: Notification Toggle
    kb.append([
        InlineKeyboardButton(("✅ Notif ON" if settings["notify"] else "❌ Notif OFF"), f"autogp_notif_{user_id}")
    ])

    # 🧹 Grid: Content Filter Selection (15 types + Dice)
    f_list = settings["filters"]
    def get_f_btn(f_type, label_key, def_label):
        label = loc(label_key) or def_label
        active = "✅" if f_type in f_list else "☑️"
        return InlineKeyboardButton(f"{active} {label}", f"autogp_filter_{f_type}_{user_id}")

    kb.append([get_f_btn("all", "GP_BTN_ALL", "All"), get_f_btn("photo", "GP_BTN_PHOTO", "Photo"), get_f_btn("video", "GP_BTN_VIDEO", "Video")])
    kb.append([get_f_btn("text", "GP_BTN_TEXT", "Text"), get_f_btn("audio", "GP_BTN_AUDIO", "Audio"), get_f_btn("sticker", "GP_BTN_STICKER", "Sticker")])
    kb.append([get_f_btn("animation", "GP_BTN_ANIMATION", "Anim"), get_f_btn("document", "GP_BTN_DOCUMENT", "Doc"), get_f_btn("video_note", "GP_BTN_VNOTE", "VNote")])
    kb.append([get_f_btn("voice", "GP_BTN_VOICE", "Voice"), get_f_btn("contact", "GP_BTN_CONTACT", "Contact"), get_f_btn("location", "GP_BTN_LOCATION", "Loc")])
    kb.append([get_f_btn("venue", "GP_BTN_VENUE", "Venue"), get_f_btn("game", "GP_BTN_GAME", "Game"), get_f_btn("poll", "GP_BTN_POLL", "Poll")])
    kb.append([get_f_btn("dice", "GP_BTN_DICE", "Dice")])

    # 👑 Row: Administrative Access Filter
    admin_filter_active = loc(f"GP_BTN_ADMIN_FILTER_{settings['admin_filter'].upper()}")
    kb.append([InlineKeyboardButton(f"👑 Admin Filter: {admin_filter_active}", f"autogp_toggleadmin_{user_id}")])
    
    # 🚫 Row: Interactive Blacklist Management
    bl_buttons = []
    if current_chat_id: # Show toggle only if we have context of the chat
        is_bl = current_chat_id in settings["blacklist"]
        btn_text = "✅ Active (Whitelist)" if is_bl else "🚫 Blacklist This Chat"
        bl_buttons.append(InlineKeyboardButton(btn_text, f"autogp_bl_togglecid_{user_id}"))
    
    bl_buttons.append(InlineKeyboardButton(loc("autogp_bl_list"), f"autogp_bl_list_{user_id}"))
    kb.append(bl_buttons)

    # 📋 Row: Target Chat Listing
    kb.append([
        InlineKeyboardButton(loc("GP_BTN_LIST_CHATS"), f"autogp_list_target_{user_id}")
    ])
    
    # 🔄 Row: Global Menu Controls
    kb.append([
        InlineKeyboardButton("🔄 Refresh", f"autogp_refresh_{user_id}"),
        InlineKeyboardButton(loc("GP_BTN_INFO"), f"autogp_info_{user_id}")
    ])
    
    # ❌ Row: Close Dashboard
    kb.append([
        InlineKeyboardButton("❌ Close Menu", f"autogp_close_{user_id}")
    ])
    
    return InlineKeyboardMarkup(kb)

def get_autogp_info_text():
    """
    Returns the detailed help/info text for Auto-GP.
    """
    return (
        "<b>🤖 AUTO GLOBAL PURGEME - INFORMATION</b>\n\n"
        "<b>🔄 Cycle Modes:</b>\n"
        "• <b>Global 🌍:</b> Triggers a full scan of ALL target chats (Groups/Private/etc). Safe and thorough.\n"
        "• <b>Current Smart 🔆:</b> Purges ONLY the current chat, but <b>Respects</b> Blacklist and Admin Filters. If the current chat is blacklisted, it does nothing.\n"
        "• <b>Current Force ⚠️:</b> Purges the current chat immediately, <b>IGNORING</b> all safeguards (Blacklist, Admin Filter, Target Type). Use with caution.\n\n"
        "<b>🎯 Targets & Filters:</b>\n"
        "• <b>All/Groups/Personal:</b> Defines which chats are scanned in Global Mode.\n"
        "• <b>Admin Filter:</b> Skips chats where you aren't admin (except in Force Mode).\n"
        "• <b>Blacklist:</b> Chats here are skipped (except in Force Mode).\n\n"
        "<b>⏱ Delays:</b>\n"
        "• <b>Delay/Chat:</b> Wait time between processing chats in Global Mode.\n"
    )

async def get_auto_gp_target_chats(client: Client, target_type: str, admin_filter: str, blacklist: list):
    """
    Scans dialogs for target chats that are NOT on the blacklist.
    """
    chats = []
    ignored_count = 0
    total_scanned = 0
    
    async for dialog in client.get_dialogs():
        total_scanned += 1
        if total_scanned % 20 == 0: await asyncio.sleep(0.5)
            
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
                    me = await dialog.chat.get_member("me")
                    is_admin = me.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]
                    if admin_filter == "admin" and not is_admin: should_ignore = True
                    elif admin_filter == "non_admin" and is_admin: should_ignore = True
                except:
                    if admin_filter == "admin": should_ignore = True
            
            if should_ignore: ignored_count += 1
            else:
                chats.append({
                    "id": chat_id,
                    "title": dialog.chat.title or f"{dialog.chat.first_name or ''} {dialog.chat.last_name or ''}".strip() or str(chat_id)
                })  
    return chats, ignored_count

async def get_autogp_bl_text(client, settings, page=0):
    """
    Generate the text for the blacklist manager with clickable chat names.
    Supports hyperlinks for Android/iOS/Desktop.
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

    # Dynamic fetching of chat info for hyperlinks
    tasks = [client.get_chat(cid) for cid in chunk]
    chats = await asyncio.gather(*tasks, return_exceptions=True)
    
    for i, cid in enumerate(chunk):
        chat = chats[i]
        name = f"Chat {cid}"
        link = None
        
        if not isinstance(chat, Exception):
            name = chat.title or chat.first_name or f"Chat {cid}"
            if chat.username:
                link = f"https://t.me/{chat.username}"
            elif str(cid).startswith("-100"):
                link = f"https://t.me/c/{str(cid)[4:]}/1"
            elif cid > 0:
                link = f"tg://user?id={cid}"
        else:
            # Fallback links if get_chat fails
            if str(cid).startswith("-100"):
                link = f"https://t.me/c/{str(cid)[4:]}/1"
            elif cid > 0:
                link = f"tg://user?id={cid}"
        
        if link:
            text += f"• <a href='{link}'>{name}</a> (<code>{cid}</code>)\n"
        else:
            text += f"• {name} (<code>{cid}</code>)\n"
            
    return text

def get_autogp_bl_kb(user_id, settings, page=0):
    """
    Generates a sub-menu for managing blacklisted chats.
    Includes [ID][Remove] layout and [Back][Page N] navigation.
    """
    kb = []
    bl = settings["blacklist"]
    
    # Paginate (display 10 IDs per view)
    start = page * 10
    end = start + 10
    chunk = bl[start:end]
    
    for cid in chunk:
        kb.append([
            InlineKeyboardButton(f"ID: {cid}", "autogp_noop"),
            InlineKeyboardButton("🗑 Remove", f"autogp_bl_rem_{cid}_{user_id}")
        ])
    
    # Footer Navigation as per mockup
    nav = []
    nav.append(InlineKeyboardButton(loc("GP_BTN_BACK"), f"autogp_refresh_{user_id}"))
    
    if end < len(bl):
         nav.append(InlineKeyboardButton(f"Page {page+2} ▶️", f"autogp_bl_page_{page+1}_{user_id}"))
    elif page > 0:
         nav.insert(0, InlineKeyboardButton(f"◀️ Page {page}", f"autogp_bl_page_{page-1}_{user_id}"))
         
    kb.append(nav)
    return InlineKeyboardMarkup(kb)

@Altruix.bot.on_callback_query(filters.regex(r"^autogp_(?P<action>target|cycle|limit|delay|delaymsg|mode|off|notif|filter|toggleadmin|bl|refresh|close|toggle|list|info|back|noop)_(?P<tail>.*)$"))
@iuser_check
@log_errors
async def auto_gp_callback_handler(c: Client, cb: CallbackQuery):
    """
    Primary handler for logic adjustments from Dashboard buttons.
    Uses Regex capture groups to parse the intent (action, subaction, account_id).
    """
    m = cb.matches[0]
    action = m.group("action")
    tail = m.group("tail")
    
    # Unified tail parsing: [subaction_]user_id
    parts = tail.split("_")
    user_id = int(parts[-1])
    sub_action = "_".join(parts[:-1]) if len(parts) > 1 else None
    
    # Access Security Check
    from Main.utils.access_control import is_authorized_user
    if not is_authorized_user(cb.from_user.id, Altruix.config.OWNER_USERS_ID, Altruix.config.SUDO_USERS_ID):
        await cb.answer("⛔ Access Denied: Authorized accounts only.", show_alert=True)
        return

    settings = await get_auto_gp_settings(user_id)
    chat_id = cb.message.chat.id if cb.message else None
    
    # 🧩 LOGIC: No-Operation (for info buttons)
    if action == "noop": return await cb.answer()
    
    # ⚙️ LOGIC: Master Killswitch
    elif action == "toggle":
        settings["status"] = not settings["status"]
        await cb.answer(f"✅ Auto-GP marked as {'ENABLED' if settings['status'] else 'DISABLED'}")
    
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
        await cb.answer(f"⌛ Inter-Msg Delay: {settings['delay_msg']}s")

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
        
    # 🧹 LOGIC: Media Content Filters (Smart Toggle)
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
        await cb.answer("🧹 Filter Grid Synchronized")
    
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
        elif sub_action == "list" or sub_action.startswith("page"): # Open sub-menu list
            page = 0
            if sub_action.startswith("page"): page = int(sub_action.split("_")[1])
            kb = get_autogp_bl_kb(user_id, settings, page)
            text = await get_autogp_bl_text(c, settings, page)
            await cb.edit_message_text(text, reply_markup=kb)
            return
        elif sub_action.startswith("rem_"): # Individual item removal from list
            target_id = int(sub_action.split("_")[1])
            if target_id in settings["blacklist"]:
                settings["blacklist"].remove(target_id)
                await cb.answer(f"🗑 ID {target_id} has been removed.")
            await save_auto_gp_settings(user_id, settings)
            kb = get_autogp_bl_kb(user_id, settings, 0)
            text = await get_autogp_bl_text(c, settings, 0)
            await cb.edit_message_text(text, reply_markup=kb)
            return

    # 📋 LOGIC: Target Chat Listing
    elif action == "list" and sub_action == "target":
        await cb.answer("🔍 Scanning for target chats...")
        
        # Determine client to scan dialogs
        target_client = next((cl for cl in Altruix.clients if cl.me and cl.me.id == user_id), None)
        if not target_client:
            return await cb.answer("❌ Error: Active session not found.", show_alert=True)
            
        chats, ignored = await get_auto_gp_target_chats(
            target_client, settings["target"], settings["admin_filter"], settings["blacklist"]
        )
        
        chat_list = "\n".join([f"• {c['title']} (<code>{c['id']}</code>)" for c in chats[:50]])
        if len(chats) > 50: chat_list += f"\n...and {len(chats) - 50} more"
        
        header_fmt = loc("GP_LIST_CHATS_HEADER") or "<b>Target Chats:</b>\n<i>(Total: {} | Ignored: {})</i>\n\n{}"
        text = header_fmt.format(len(chats), ignored, chat_list or "None")
        
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(loc("GP_BTN_BACK"), f"autogp_back_{user_id}")]])
        await cb.edit_message_text(text, reply_markup=kb, disable_web_page_preview=True)
        return

    # ℹ️ LOGIC: Info Menu
    elif action == "info":
        text = get_autogp_info_text()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(loc("GP_BTN_BACK"), f"autogp_back_{user_id}")]])
        await cb.edit_message_text(text, reply_markup=kb)
        return

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
        if cb.message: await cb.message.delete()
        return

    # FINAL: Commit changes to DB and repopulate UI
    await save_auto_gp_settings(user_id, settings)
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

async def auto_gp_perform_purge(client: Client, chat_id: int, trigger_msg_id: int = None, message: Message = None, bypass_guards: bool = False):
    """
    The background engine that performs the deletions.
    Triggered for every outgoing message when Auto-GP is ON.
    """
    user_id = client.me.id
    settings = await get_auto_gp_settings(user_id)
    
    # 🛑 Master Switch Check (Always Respected)
    if not settings["status"]:
        Altruix.log(f"💤 Auto-GP | Status is OFF for user {user_id}. Skipping.", level=20)
        return
    
    # 🛑 Blacklist Check (Bypassed in Current Mode)
    if not bypass_guards:
        if chat_id in settings["blacklist"]:
            Altruix.log(f"🕵️ Auto-GP | Chat {chat_id} is blacklisted. Skipping.", level=20)
            return
    
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
            return

    if not chat:
        return

    # Use message.id as trigger if provided
    current_trigger_id = trigger_msg_id or (message.id if message else None)

    # 🎯 Target Type Check (Bypassed in Current Mode)
    if not bypass_guards:
        target = settings.get("target", "all")
        # Normalize chat type to string for consistent comparison
        c_type = str(chat.type).lower()
        if c_type.startswith("chattype."): c_type = c_type.split("chattype.")[1]
        
        if target == "groups" and c_type not in ["group", "supergroup"]:
            Altruix.log(f"🕵️ Auto-GP | Chat {chat_id} type {c_type} mismatch (Target: groups). Skipping.", level=20)
            return
        if target == "personal" and c_type != "private":
            Altruix.log(f"🕵️ Auto-GP | Chat {chat_id} type {c_type} mismatch (Target: personal). Skipping.", level=20)
            return

    # 👑 GUARD: Admin Rights Filter (Bypassed in Current Mode)
    if not bypass_guards:
        if settings["admin_filter"] != "all":
            try:
                if c_type in ["group", "supergroup"]:
                    me = await chat.get_member("me")
                    is_admin = me.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]
                    if settings["admin_filter"] == "admin" and not is_admin: return
                    if settings["admin_filter"] == "non_admin" and is_admin: return
            except Exception as e:
                logger.debug(f"Admin Check Failed for {chat_id}: {e}")
                if settings["admin_filter"] == "admin": return

    # 📢 STEP 0: Initial Progress Notification (Sent ONLY if all guards pass)
    log_msg = None
    if settings.get("notify", True):
        try:
            target_idx = -1
            for i, c in enumerate(Altruix.clients):
                if c.me.id == user_id:
                    target_idx = i; break
            
            if target_idx != -1:
                Altruix.log(f"📡 Auto-GP | Sending 'Processing' log for chat {chat_id}...", level=20)
                log_msg = await send_log_notification(
                    client, "auto_global_purgeme", target_idx, client.me, True, 
                    additional_info={
                        "Type": "🤖 Auto-GP Processing...",
                        "Chat": f"{chat_id} ({chat.title or 'Private'})",
                        "Status": "🔍 Scanning/Cleaning..."
                    }
                )
        except Exception as e:
            Altruix.log(f"⚠️ Auto-GP Initial Log Error: {e}", level=30)
    
    # Configuration extraction
    limit = settings["limit"]
    target_filters = settings["filters"]
    mode = settings.get("mode", "newest")
    offset = settings.get("offset", 0)
    
    # 🔍 STEP 1: Search and Match messages
    collected_ids = []
    Altruix.log(f"🔎 Auto-GP | Scanning chat {chat_id} (Limit: {limit}, Offset: {offset})...", level=20)
    # Fetch slightly more than needed to account for offset and the message that triggered this
    async for msg in client.search_messages(chat_id, from_user="me", limit=limit + offset + 5):
        if current_trigger_id and msg.id == current_trigger_id: continue # Don't delete the command itself if it matches
            
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
            if len(collected_ids) >= limit + offset: break
    
    if not collected_ids: return
        
    # 📏 STEP 2: Application of Search Mode & Offset
    if mode == "oldest": collected_ids.reverse() # Invert if oldest first
    if offset > 0: collected_ids = collected_ids[offset:] # Skip first N
    collected_ids = collected_ids[:limit] # Truncate to limit
    
    if not collected_ids: return

    # 🗑 STEP 3: Execution of Batched Deletions
    deleted_count = 0
    delay_msg = settings.get("delay_msg", 1.0)
    Altruix.log(f"🗑 Auto-GP | Deleting {len(collected_ids)} matched messages in chat {chat_id}...", level=20)
    for i in range(0, len(collected_ids), 100): # Telegram allows max 100 per delete call
        batch = collected_ids[i:i+100]
        try:
            await client.delete_messages(chat_id, batch)
            deleted_count += len(batch)
            if delay_msg > 0: await asyncio.sleep(delay_msg) # Safety delay to avoid flooding
        except FloodWait as e: await asyncio.sleep(e.value)
        except Exception as e: Altruix.log(f"Purge Logic Batch Error: {e}", level=30)
            
    # 🔔 STEP 4: Reporting to Telegram Log Group
    if settings.get("notify", True) and deleted_count > 0:
        try:
            # Resolve account index if not already present
            idx = -1
            for i, c in enumerate(Altruix.clients):
                if c.me.id == user_id:
                    idx = i; break
            
            if idx != -1:
                # 📢 USER REQUESTED FORMAT
                # • Type: ✅ Auto-GP Cycle Complete
                # • Chat: -100... (Title)
                # • Deleted: 1 messages purged
                # • Limit: 2 items configured
                # • Filters: all active
                # • Waktu: ...
                
                final_info = {
                    "Type": "✅ Auto-GP Cycle Complete",
                    "Chat": f"{chat_id} ({chat.title or 'Private'})",
                    "Deleted": f"{deleted_count} messages purged",
                    "Limit": f"{limit} items configured",
                    "Filters": f"{', '.join(target_filters)} active"
                }
                
                # If we have an initial log message, try to update it; otherwise send a new one
                if log_msg:
                    try:
                        await log_msg.delete()
                    except: pass
                
                Altruix.log(f"✅ Auto-GP | Cycle Complete for {chat_id}. Deleted: {deleted_count}", level=20)
                await send_log_notification(
                    client, "auto_global_purgeme", idx, client.me, True, 
                    additional_info=final_info
                )
        except Exception as e:
            Altruix.log(f"Auto-GP Log Dispatch Error: {e}", level=30)

# 🌍 GLOBAL ITERATION LOGIC
GLOBAL_PURGE_LOCK = asyncio.Lock()

async def auto_gp_global_cycle(client: Client):
    """
    Orchestrates the global purge cycle across ALL target chats.
    Locked to prevent overlapping cycles.
    """
    user_id = client.me.id
    
    # 🔒 LOCK GUARD
    if GLOBAL_PURGE_LOCK.locked():
        Altruix.log(f"⚠️ Auto-GP Global Cycle Skipped (Already Running) | User: {user_id}", level=20)
        return

    async with GLOBAL_PURGE_LOCK:
        try:
            settings = await get_auto_gp_settings(user_id)
            if not settings["status"]: return

            Altruix.log(f"🚀 Auto-GP Global Cycle Started | User: {user_id}", level=20)
            
            # 1. Get Targets
            chats, ignored = await get_auto_gp_target_chats(
                client, settings["target"], settings["admin_filter"], settings["blacklist"]
            )
            
            if not chats:
                Altruix.log(f"💤 Auto-GP Global Cycle: No target chats found.", level=20)
                return

            # 2. Iterate & Purge
            delay_chat = settings.get("delay", 1.0)
            
            for i, chat_info in enumerate(chats):
                chat_id = chat_info["id"]
                try:
                    # Perform purge on this chat
                    # We pass message=None to force a fresh search
                    await auto_gp_perform_purge(client, chat_id, message=None)
                    
                    # Delay between chats
                    if i < len(chats) - 1 and delay_chat > 0:
                        await asyncio.sleep(delay_chat)
                        
                except Exception as e:
                    Altruix.log(f"⚠️ Auto-GP Global Cycle Error on Chat {chat_id}: {e}", level=30)
                    
            Altruix.log(f"✅ Auto-GP Global Cycle Finished | User: {user_id}", level=20)
            
        except Exception as e:
            Altruix.log(f"💥 Auto-GP Global Cycle Critical Error: {e}", level=40)
