import asyncio
import time
import logging
import html
import re
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, MessageNotModified, PeerIdInvalid
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InlineQuery, InlineQueryResultArticle, InputTextMessageContent
from Main import Altruix
from Main.core.decorators import iuser_check, log_errors
from .utils import send_log_notification

# Localizer Helper
def loc(key, *args):
    """Get localized string and format with args if provided."""
    string = Altruix.get_string(key)
    if not string:
        return None
    # Only format if args are provided and string has placeholders
    if args:
        try:
            return string.format(*args)
        except (IndexError, KeyError):
            # If format fails, return the string as-is
            return string
    return string

# Concurrency Lock
STATE_LOCK = asyncio.Lock()

# Helper to get user info robustly
async def _get_me(client):
    me = getattr(client, "myself", None) or client.me
    if not me:
        try:
            me = await client.get_me()
            client.myself = me
        except:
            return None
    return me

# Helper to get formatted status message
def get_gp_status_text(state):
    status = state["status"]
    processed_chats = state.get("processed_chats", 0)
    total_chats = state.get("total_chats", 0)
    deleted_count = state.get("deleted_count", 0)
    limit = state["limit"]
    delay = state["delay"]
    delay_msg = state.get("delay_msg", 1)
    target = state["target"]
    admin_filter = state.get("admin_filter", "non_admin")
    mode = state.get("mode", "newest")
    offset = state.get("offset", 0)
    notify = state.get("notify", True)
    filters_list = state.get("filters", ["all"])
    
    title = loc("GPURGEME_TITLE") or "🚮 <b>GLOBAL PURGEME DASHBOARD</b>"
    
    # Account Line
    client = state["client"]
    me = client.myself if hasattr(client, "myself") else None
    if me:
        account_name = f"<b><a href='tg://user?id={me.id}'>{html.escape(me.first_name)}</a></b>"
        account_str = (loc("GP_ACCOUNT_INFO") or "👤 <b>Account:</b> {}").format(account_name)
    else:
        account_str = ""

    target_str = loc(f"GP_BTN_TARGET_{target.upper()}") or target.capitalize()
    mode_str = loc(f"GP_BTN_MODE_{mode.upper()}") or mode.capitalize()
    filters_str = ", ".join([loc(f"GP_BTN_{f.upper()}") or f.capitalize() for f in filters_list])
    
    admin_filter_str = loc(f"GP_BTN_ADMIN_FILTER_{admin_filter.upper()}") or admin_filter.replace("_", " ").title()
    
    header = (
        f"{title}\n\n"
        f"{account_str}\n"
        f"{loc('GP_TARGET').format(target_str) if loc('GP_TARGET') else f'🎯 Target: {target_str}'}\n"
        f"<b>📊 Settings:</b> [ <code>L:{limit}msg | Dly_Chat:{delay}s | Dly_Msg:{delay_msg}s</code> ]\n"
        f"<b>🛠 Config:</b> [ <code>M:{mode_str} | O:{offset}</code> ]\n"
        f"<b>🧹 Filters:</b> <code>{filters_str}</code>\n"
        f"<b>👑 Admin Filter:</b> {admin_filter_str} | <b>🔔 Notif:</b> {'✅' if notify else '❌'}\n\n"
    )

    if status == "idle":
        status_line = loc("GP_STATUS_IDLE") or "💤 <b>Status:</b> <code>Idle / Ready</code>"
    elif status == "listing":
        status_line = "📋 <b>Status:</b> <code>Generating group list...</code>"
    elif status == "running":
        status_line = (loc("GP_STATUS_RUNNING") or "🚀 <b>Status:</b> <code>Running ({}/{})</code>").format(processed_chats + 1, total_chats)
        status_line += f"\n🗑 <b>Deleted:</b> <code>{deleted_count} messages</code>"
        if state.get("current_chat"):
            status_line += f"\n📍 <b>Current Chat:</b> <code>{state['current_chat']}</code>"
    elif status == "paused":
        status_line = loc("GP_STATUS_PAUSED") or "⏸ <b>Status:</b> <code>Paused</code>"
        status_line += f"\n🗑 <b>Deleted:</b> <code>{deleted_count} messages</code>"
    elif status == "completed":
        status_line = loc("GP_STATUS_COMPLETED") or "✅ <b>Status:</b> <code>Completed</code>"
        status_line += f"\n🗑 <b>Total Deleted:</b> <code>{deleted_count} messages</code>"
    elif status == "completed":
        status_line = loc("GP_STATUS_COMPLETED") or "✅ <b>Status:</b> <code>Completed</code>"
        status_line += f"\n🗑 <b>Total Deleted:</b> <code>{deleted_count} messages</code>"
    elif status == "confirm_start":
        status_line = loc("GP_STATUS_CONFIRM_START") or "⚠️ <b>Confirmation:</b> <code>Are you sure you want to start?</code>"
    else:
        status_line = f"❓ <b>Status:</b> <code>{status}</code>"

    return f"{header}{status_line}"

# Helper to get control buttons
def get_gp_control_kb(unique_id, state):
    status = state["status"]
    target = state["target"]
    limit = state["limit"]
    delay = state["delay"]
    delay_msg = state.get("delay_msg", 1)
    admin_filter = state.get("admin_filter", "non_admin")
    mode = state.get("mode", "newest")
    offset = state.get("offset", 0)
    notify = state.get("notify", True)
    filters_list = state.get("filters", ["all"])
    
    # Settings context
    is_settings = state.get("is_settings", False)
    index = state.get("index", 0)
    page = state.get("page", 0)
    
    kb = []
    
    if status == "idle" or status == "completed":
        # Target Toggle Buttons
        kb.append([
            InlineKeyboardButton(("✅ " if target == "all" else "") + (loc("GP_BTN_TARGET_ALL") or "All"), f"gp_target_all_{unique_id}"),
            InlineKeyboardButton(("✅ " if target == "groups" else "") + (loc("GP_BTN_TARGET_GROUPS") or "Groups"), f"gp_target_groups_{unique_id}"),
            InlineKeyboardButton(("✅ " if target == "personal" else "") + (loc("GP_BTN_TARGET_PERSONAL") or "Personal"), f"gp_target_personal_{unique_id}")
        ])
        
        # Limit Adjustment
        kb.append([
            InlineKeyboardButton(f"Limit: {limit}", "gp_noop"),
            InlineKeyboardButton("-2", f"gp_limit_m2_{unique_id}"),
            InlineKeyboardButton("+2", f"gp_limit_p2_{unique_id}")
        ])
        
        # Delay Adjustment (Per Chat)
        kb.append([
            InlineKeyboardButton(f"{loc('GP_BTN_DELAY_CHAT') or 'Delay/Chat'}: {delay}s", "gp_noop"),
            InlineKeyboardButton("-2s", f"gp_delay_m2_{unique_id}"),
            InlineKeyboardButton("+2s", f"gp_delay_p2_{unique_id}")
        ])

        # Delay Adjustment (Per Msg)
        kb.append([
            InlineKeyboardButton(f"{loc('GP_BTN_DELAY_MSG') or 'Delay/Msg'}: {delay_msg}s", "gp_noop"),
            InlineKeyboardButton("-0.5s", f"gp_delaymsg_m05_{unique_id}"),
            InlineKeyboardButton("+0.5s", f"gp_delaymsg_p05_{unique_id}")
        ])

        # Mode Selection
        kb.append([
            InlineKeyboardButton(f"Mode: {mode.capitalize()}", "gp_noop"),
            InlineKeyboardButton(("✅ " if mode == "newest" else "") + (loc("GP_BTN_MODE_NEWEST") or "Newest"), f"gp_mode_newest_{unique_id}"),
            InlineKeyboardButton(("✅ " if mode == "oldest" else "") + (loc("GP_BTN_MODE_OLDEST") or "Oldest"), f"gp_mode_oldest_{unique_id}")
        ])

        # Offset Selection
        kb.append([
            InlineKeyboardButton(f"Offset: {offset}", "gp_noop"),
            InlineKeyboardButton("-5", f"gp_off_m5_{unique_id}"),
            InlineKeyboardButton("+5", f"gp_off_p5_{unique_id}"),
            InlineKeyboardButton(loc("GP_BTN_RESET") or "Reset", f"gp_off_reset_{unique_id}")
        ])

        # Notif Toggle
        kb.append([
            InlineKeyboardButton(loc("GP_BTN_NOTIF_ON" if notify else "GP_BTN_NOTIF_OFF") or f"Notif: {'ON' if notify else 'OFF'}", f"gp_notif_{unique_id}")
        ])

        # Filters Grid (3-column)
        def get_f_btn(f_type, label_key, def_label):
            label = loc(label_key) or def_label
            active = "✅" if f_type in filters_list else "☑️"
            return InlineKeyboardButton(f"{active} {label}", f"gp_filter_{f_type}_{unique_id}")

        # Row 1: Core Media
        kb.append([
            get_f_btn("all", "GP_BTN_ALL", "All"),
            get_f_btn("photo", "GP_BTN_IMG", "Photo"),
            get_f_btn("video", "GP_BTN_VID", "Video")
        ])
        # Row 2: Engagement
        kb.append([
            get_f_btn("text", "GP_BTN_TXT", "Text"),
            get_f_btn("audio", "GP_BTN_AUD", "Audio"),
            get_f_btn("sticker", "GP_BTN_STK", "Sticker")
        ])
        # Row 3: Rich Media
        kb.append([
            get_f_btn("animation", "GP_BTN_GIF", "Anim"),
            get_f_btn("document", "GP_BTN_DOC", "Doc"),
            get_f_btn("video_note", "GP_BTN_VNOTE", "VNote")
        ])
        # Row 4: Specialized
        kb.append([
            get_f_btn("voice", "GP_BTN_VN", "Voice"),
            get_f_btn("contact", "GP_BTN_CONT", "Contact"),
            get_f_btn("location", "GP_BTN_LOC", "Loc")
        ])
        # Row 5: Interaction
        kb.append([
            get_f_btn("venue", "GP_BTN_VENUE", "Venue"),
            get_f_btn("game", "GP_BTN_GAME", "Game"),
            get_f_btn("poll", "GP_BTN_POLL", "Poll")
        ])
        kb.append([
            get_f_btn("dice", "GP_BTN_DICE", "Dice")
        ])

        # Advanced Options
        admin_filter_btn_text = loc(f"GP_BTN_ADMIN_FILTER_{admin_filter.upper()}") or admin_filter.replace("_", " ").title()
        kb.append([
            InlineKeyboardButton(f"👑 {admin_filter_btn_text}", f"gp_toggle_admin_{unique_id}")
        ])
        kb.append([
            InlineKeyboardButton(loc("GP_BTN_LIST_CHATS") or "📋 List Chats", f"gp_list_groups_{unique_id}")
        ])
        
        # New Layout: Refresh/Info then Start/Close
        kb.append([
            InlineKeyboardButton("🔄 Refresh", f"gp_refresh_{unique_id}"),
            InlineKeyboardButton(loc("GP_BTN_INFO") or "ℹ️ Info", f"gp_info_{unique_id}")
        ])
        
        if is_settings:
             kb.append([
                InlineKeyboardButton(loc("GP_BTN_START") or "🚀 Start GPurgeme", f"gp_start_{unique_id}"),
                InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}")
            ])
        else:
            kb.append([
                InlineKeyboardButton(loc("GP_BTN_START") or "🚀 Start GPurgeme", f"gp_start_{unique_id}"),
                InlineKeyboardButton("❌ Close", f"gp_close_{unique_id}")
            ])
            
    elif status == "confirm_start":
        kb.append([
            InlineKeyboardButton(loc("GP_BTN_YES") or "✅ Yes, Start", f"gp_confirm_start_{unique_id}"),
            InlineKeyboardButton(loc("GP_BTN_NO") or "❌ No, Cancel", f"gp_confirm_cancel_{unique_id}")
        ])
            
    elif status == "running":
        kb.append([
            InlineKeyboardButton(loc("GP_BTN_PAUSE") or "⏸ Pause", f"gp_pause_{unique_id}"),
            InlineKeyboardButton(loc("GP_BTN_STOP") or "🛑 Stop", f"gp_stop_{unique_id}")
        ])
    elif status == "paused":
        kb.append([
            InlineKeyboardButton(loc("GP_BTN_RESUME") or "▶️ Resume", f"gp_resume_{unique_id}"),
            InlineKeyboardButton(loc("GP_BTN_STOP") or "🛑 Stop", f"gp_stop_{unique_id}")
        ])
    elif status == "info":
        kb.append([InlineKeyboardButton(loc("GP_BTN_BACK") or "🔙 Back", f"gp_back_{unique_id}")])
    
    # Close/Refresh/Settings Back (Only for running/paused status now, as idle has custom layout)
    if status in ["running", "paused"]:
        bottom_row = [InlineKeyboardButton("🔄 Refresh", f"gp_refresh_{unique_id}")]
        if is_settings:
            bottom_row.append(InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}"))
        else:
            bottom_row.append(InlineKeyboardButton("❌ Close", f"gp_close_{unique_id}"))
        kb.append(bottom_row)
    
    return InlineKeyboardMarkup(kb)

# Update Dashboard Function
async def update_gp_dashboard(unique_id, custom_text=None, cb=None, state=None):
    if state:
        await _perform_dashboard_update(unique_id, state, custom_text, cb)
    else:
        async with STATE_LOCK:
            state = Altruix.GPURGEME_STATE.get(unique_id)
            if state:
                await _perform_dashboard_update(unique_id, state, custom_text, cb)

async def _perform_dashboard_update(unique_id, state, custom_text, cb):
    if not state.get("dashboard_msg_id") and not state.get("inline_dashboard_id") and not cb:
        return
    
    text = custom_text or get_gp_status_text(state)
    kb = get_gp_control_kb(unique_id, state)
    
    try:
        # Case 0: Direct Callback Edit
        if cb:
             await cb.edit_message_text(text, reply_markup=kb, disable_web_page_preview=True)
             return

        # Case 1: Inline Message Update
        if state.get("inline_dashboard_id"):
             await Altruix.bot.edit_inline_text(state["inline_dashboard_id"], text, reply_markup=kb, disable_web_page_preview=True)

        # Case 2: Regular Message Update
        elif state.get("dashboard_msg_id"):
             # For settings menu, always use assistant bot
             bot = Altruix.bot_manager.get_bot(state["client"].me.id)
             await bot.edit_message_text(
                state["dashboard_chat_id"],
                state["dashboard_msg_id"],
                text,
                reply_markup=kb,
                disable_web_page_preview=True
            )
    except MessageNotModified:
        pass
    except Exception as e:
        Altruix.log(f"GPurgeme UI Update Fail: {e}")

# Core Logic: Process Chat
async def gp_process_chat(client: Client, chat_id: int, limit: int, delay: int, delay_msg: float, state: dict):
    deleted_in_chat = 0
    try:
        if state["stop_event"].is_set():
            return 0
        if not state["pause_event"].is_set(): await state["pause_event"].wait()

        mode = state.get("mode", "newest")
        offset = state.get("offset", 0)
        target_filters = state.get("filters", ["all"])

        collected_ids = []
        async for msg in client.search_messages(chat_id, from_user="me", limit=limit + offset):
            should_include = False
            if "all" in target_filters: should_include = True
            else:
                try:
                    # Map Pyrogram message attributes to our filter types
                    if msg.text and "text" in target_filters:
                        should_include = True
                    elif msg.photo and ("photo" in target_filters or "image" in target_filters):
                        should_include = True
                    elif msg.video and "video" in target_filters:
                        should_include = True
                    elif (msg.voice or msg.audio) and "audio" in target_filters:
                        should_include = True
                    elif msg.sticker and "sticker" in target_filters:
                        should_include = True
                    elif msg.animation and ("animation" in target_filters or "gif" in target_filters):
                        should_include = True
                    elif msg.document and ("document" in target_filters or "file" in target_filters):
                        should_include = True
                    elif msg.video_note and ("video_note" in target_filters or "vnote" in target_filters):
                        should_include = True
                    elif msg.voice and "voice" in target_filters:
                        should_include = True
                    elif msg.contact and "contact" in target_filters:
                        should_include = True
                    elif msg.location and "location" in target_filters:
                        should_include = True
                    elif msg.venue and "venue" in target_filters:
                        should_include = True
                    elif msg.game and "game" in target_filters:
                        should_include = True
                    elif msg.poll and "poll" in target_filters:
                        should_include = True
                    elif msg.dice and "dice" in target_filters:
                        should_include = True
                except Exception as e:
                    Altruix.log(f"GPurgeme: Type identification error: {e}", level=10)
            
            if should_include: collected_ids.append(msg.id)
            if len(collected_ids) >= limit + offset: break
            if state["stop_event"].is_set(): break
            
        if not collected_ids:
            return 0
        if mode == "oldest": collected_ids.reverse()
        if offset > 0: collected_ids = collected_ids[offset:]
        collected_ids = collected_ids[:limit]
        if not collected_ids:
            return 0
            
        for i in range(0, len(collected_ids), 100):
            if state["stop_event"].is_set(): break
            batch = collected_ids[i:i+100]
            try:
                await client.delete_messages(chat_id, batch)
                deleted_in_chat += len(batch)
                state["deleted_count"] += len(batch)
                if deleted_in_chat % 10 == 0:
                    asyncio.create_task(update_gp_dashboard(state["unique_id"]))
                # Message Throttle (apply after each batch)
                if delay_msg > 0: await asyncio.sleep(delay_msg)
            except FloodWait as e:
                await asyncio.sleep(e.value)
            except Exception: pass
        
        if delay > 0 and not state["stop_event"].is_set(): await asyncio.sleep(delay)
            
    except Exception: pass
    return deleted_in_chat

# Core Logic: Get Target Chats
async def get_target_chats(client: Client, target_type: str, admin_filter: str):
    chats = []
    ignored_count = 0
    total_scanned = 0
    
    async for dialog in client.get_dialogs():
        total_scanned += 1
        if total_scanned % 20 == 0: await asyncio.sleep(0.5)
            
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
            
            # 3-Way Admin Filter Logic
            # 'all': Keep all (no filter)
            # 'admin': Keep ONLY if admin/owner
            # 'non_admin': Keep ONLY if NOT admin/owner
            
            if admin_filter != "all" and chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
                try:
                    me = await dialog.chat.get_member("me")
                    is_admin = me.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]
                    
                    if admin_filter == "admin":
                        if not is_admin: should_ignore = True
                    elif admin_filter == "non_admin":
                        if is_admin: should_ignore = True
                except:
                    # If can't get member status, assume non-admin for safety or skip?
                    # Let's assume non-admin to be safe against accidental deletion in admin chats,
                    # but if filter is 'admin', we might skip it.
                    if admin_filter == "admin": should_ignore = True
            
            if should_ignore: ignored_count += 1
            else:
                chats.append({
                    "id": dialog.chat.id,
                    "title": dialog.chat.title or f"{dialog.chat.first_name or ''} {dialog.chat.last_name or ''}".strip() or str(dialog.chat.id)
                })  
    return chats, ignored_count

# Core Logic: Main Task
async def gp_global_purgeme_task(unique_id):
    async with STATE_LOCK:
        state = Altruix.GPURGEME_STATE.get(unique_id)
        if not state:
            return

    client = state["client"]
    target_type = state["target"]
    limit_per_chat = state["limit"]
    delay_per_chat = state["delay"]
    delay_per_msg = state.get("delay_msg", 1)
    
    state["status"] = "running"
    state["start_time"] = time.time()
    state["deleted_count"] = 0
    state["processed_chats"] = 0
    state["processed_list"] = []
    state["stop_event"].clear()
    state["pause_event"].set()
    
    asyncio.create_task(update_gp_dashboard(unique_id))
    
    try:
        chats_to_process, ignored_count = await get_target_chats(client, target_type, state.get("admin_filter", "non_admin"))
        state["total_chats"] = len(chats_to_process)
        asyncio.create_task(update_gp_dashboard(unique_id))
        
        if not chats_to_process:
            state["status"] = "completed"
            asyncio.create_task(update_gp_dashboard(unique_id))
            return

        for chat_data in chats_to_process:
            if state["stop_event"].is_set(): break
            
            state["current_chat"] = chat_data["title"]
            asyncio.create_task(update_gp_dashboard(unique_id))
            
            deleted = await gp_process_chat(client, chat_data["id"], limit_per_chat, delay_per_chat, delay_per_msg, state)
            
            if deleted > 0:
                state["processed_list"].append(f"• {chat_data['title']} (<code>{deleted}</code>)")
            state["processed_chats"] += 1
            
        state["status"] = "completed"
        state["current_chat"] = None
        asyncio.create_task(update_gp_dashboard(unique_id))
        
        # Log Notification
        if state.get("notify", True):
            duration = round(time.time() - state["start_time"], 2)
            processed_str = "\n".join(state["processed_list"][:30])
            if len(state["processed_list"]) > 30: processed_str += f"\n...and {len(state['processed_list']) - 30} more"
            if not processed_str: processed_str = "None"
            
            msg = (Altruix.get_string("GP_COMPLETED_MSG") or "✅ <b>Global Purgeme Completed!</b>").format(
                state["processed_chats"], state["deleted_count"], duration, processed_str
            )
            
            try:
                s_idx = Altruix.clients.index(client)
            except: s_idx = 0
            
            await send_log_notification(client, "gpurgeme_completed", s_idx, client.me, True, error_msg=msg)
            
            # Send to PM Bot Assistant
            me = await _get_me(client)
            if me:
                bot = Altruix.bot_manager.get_bot(me.id)
                await bot.send_message(me.id, msg, disable_web_page_preview=True)

    except Exception as e:
        Altruix.log(f"GPurgeme Global Task Error: {e}")
        state["status"] = "idle"
        asyncio.create_task(update_gp_dashboard(unique_id))

# Handle Inline Dashboard Requests
@Altruix.bot.on_inline_query(filters.regex(r"^gp_menu_gp_(?P<uid>\d+)"))
@iuser_check
@log_errors
async def gpurgeme_inline_handler(client: Client, query: InlineQuery):
    try:
        user_id = int(query.matches[0].group("uid"))
        # Security: Only owner/sudo can trigger their own GP menu
        from Main.utils.access_control import is_authorized_user
        if not is_authorized_user(query.from_user.id, Altruix.config.OWNER_USERS_ID, Altruix.config.SUDO_USERS_ID):
             return await query.answer([], cache_time=0)
        
        unique_id = f"gp_{user_id}"
        
        async with STATE_LOCK:
            if not hasattr(Altruix, "GPURGEME_STATE"):
                Altruix.GPURGEME_STATE = {}
                
            state = Altruix.GPURGEME_STATE.get(unique_id)
            if not state:
                # Find the client for this ID
                target_client = next((c for c in Altruix.clients if c.me and c.me.id == user_id), None)
                if not target_client:
                     return await query.answer([], cache_time=0)
                
                Altruix.GPURGEME_STATE[unique_id] = {
                    "unique_id": unique_id, "client": target_client, "status": "idle",
                    "target": "all", "limit": 6, "delay": 6, "delay_msg": 1, "admin_filter": "non_admin",
                    "mode": "newest", "offset": 0, "notify": True, "filters": ["all"],
                    "deleted_count": 0, "processed_chats": 0, "total_chats": 0,
                    "processed_list": [], "stop_event": asyncio.Event(), "pause_event": asyncio.Event(),
                    "dashboard_msg_id": None, "dashboard_chat_id": None, "start_time": 0
                }
            state = Altruix.GPURGEME_STATE[unique_id]

        text = get_gp_status_text(state)
        kb = get_gp_control_kb(unique_id, state)
        
        await query.answer(
            results=[
                InlineQueryResultArticle(
                    title="Global Purgeme Dashboard",
                    description=f"Control mass deletion for account {user_id}",
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
        Altruix.log(f"GPurgeme Inline Error: {e}")

# Entry Point from Session Info
@iuser_check
@log_errors
async def open_global_purgeme_ui(c: Client, cb: CallbackQuery, index: int, page: int):
    # 1. Get User Client
    if not (0 <= index < len(Altruix.clients)):
        return await cb.answer("Client not found", show_alert=True)
    client = Altruix.clients[index]
    me = await client.get_me() if not getattr(client, "myself", None) else getattr(client, "myself")
    client.myself = me
    
    unique_id = f"gp_{me.id}"
    
    # 2. Init State
    if not hasattr(Altruix, "GPURGEME_STATE"):
        Altruix.GPURGEME_STATE = {}
    
    if unique_id not in Altruix.GPURGEME_STATE:
        Altruix.GPURGEME_STATE[unique_id] = {
            "unique_id": unique_id, "client": client, "status": "idle",
            "target": "all", "limit": 6, "delay": 6, "delay_msg": 1, "admin_filter": "non_admin",
            "mode": "newest", "offset": 0, "notify": True, "filters": ["all"],
            "deleted_count": 0, "processed_chats": 0, "total_chats": 0,
            "processed_list": [], "stop_event": asyncio.Event(), "pause_event": asyncio.Event(),
            "dashboard_msg_id": None, "dashboard_chat_id": None, "start_time": 0
        }
    
    state = Altruix.GPURGEME_STATE[unique_id]
    state["is_settings"] = True
    state["index"] = index
    state["page"] = page
    if not cb.message:
        await cb.answer("❌ Message expired or not found.", show_alert=True)
        return

    state["dashboard_msg_id"] = cb.message.id
    state["dashboard_chat_id"] = cb.message.chat.id
    state["pause_event"].set()

    text = get_gp_status_text(state)
    kb = get_gp_control_kb(unique_id, state)
    
    await cb.message.edit_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)

# Callback Handler
@Altruix.bot.on_callback_query(filters.regex(r"^gp_(?P<action>target|limit|delay|delaymsg|pause|resume|stop|start|confirm|refresh|close|toggle|list|mode|off|notif|filter|info|back)_(?P<tail>.*)$"))
@iuser_check
@log_errors
async def gpurgeme_callback_handler(c: Client, cb: CallbackQuery):
    from Main.utils.access_control import is_authorized_user
    if not is_authorized_user(cb.from_user.id, Altruix.config.OWNER_USERS_ID, Altruix.config.SUDO_USERS_ID):
        return await cb.answer("⛔ Access Denied", show_alert=True)

    try:
        action = cb.matches[0].group("action")
        tail = cb.matches[0].group("tail")
        
        match = re.search(r"(?P<sub_action>.*)_?(?P<uid>gp_\d+)$", tail)
        if match:
            sub_action = match.group("sub_action").rstrip("_")
            unique_id = match.group("uid")
        else:
            unique_id = tail
            sub_action = None

        async with STATE_LOCK:
            state = Altruix.GPURGEME_STATE.get(unique_id)
            if not state: state = Altruix.GPURGEME_STATE.get(tail) # Retry fallback
            if not state: return await cb.answer("Session not found or expired.", show_alert=True)

            if cb.inline_message_id: state["inline_dashboard_id"] = cb.inline_message_id
            if cb.message and not state.get("dashboard_msg_id"):
                 state["dashboard_msg_id"] = cb.message.id
                 state["dashboard_chat_id"] = cb.message.chat.id

            if action == "target":
                state["target"] = sub_action
                await cb.answer(f"Target set to {state['target']}")
            elif action == "limit":
                if sub_action == "m2": state["limit"] = max(1, state["limit"] - 2)
                elif sub_action == "p2": state["limit"] += 2
                await cb.answer(f"Limit: {state['limit']} per chat")
            elif action == "delay":
                if sub_action == "m2": state["delay"] = max(0, state["delay"] - 2)
                elif sub_action == "p2": state["delay"] += 2
                await cb.answer(f"Delay/Chat: {state['delay']}s")
            elif action == "delaymsg":
                if sub_action == "m05": state["delay_msg"] = max(0, state.get("delay_msg", 1) - 0.5)
                elif sub_action == "p05": state["delay_msg"] = state.get("delay_msg", 1) + 0.5
                await cb.answer(f"Delay/Msg: {state['delay_msg']}s")
            elif action == "mode":
                state["mode"] = sub_action
                await cb.answer(f"Mode: {sub_action.capitalize()}")
            elif action == "off":
                if sub_action == "m5": state["offset"] = max(0, state["offset"] - 5)
                elif sub_action == "p5": state["offset"] += 5
                elif sub_action == "reset": state["offset"] = 0
                await cb.answer(f"Offset: {state['offset']}")
            elif action == "notif":
                state["notify"] = not state.get("notify", True)
                await cb.answer(f"Notify: {'ON' if state['notify'] else 'OFF'}")
            elif action == "filter":
                f_list = state.get("filters", ["all"])
                if sub_action == "all": f_list = ["all"] if "all" not in f_list else []
                else:
                    if "all" in f_list: f_list.remove("all")
                    if sub_action in f_list: f_list.remove(sub_action)
                    else: f_list.append(sub_action)
                    if not f_list: f_list = ["all"]
                state["filters"] = f_list
                await cb.answer("Filter updated")
            elif action == "info":
                state["status"] = "info"
                info_text = Altruix.get_string("GP_INFO_TEXT") or "GP Info"
                await update_gp_dashboard(unique_id, custom_text=info_text, cb=cb, state=state)
                return
            elif action == "back":
                state["status"] = "idle"
                await cb.answer()
            elif action == "toggle" and sub_action == "admin":
                # Cycle: non_admin -> all -> admin -> non_admin
                current = state.get("admin_filter", "non_admin")
                if current == "non_admin": new_state = "all"
                elif current == "all": new_state = "admin"
                else: new_state = "non_admin"
                
                state["admin_filter"] = new_state
                # Localize feedback
                feedback_key = f"GP_BTN_ADMIN_FILTER_{new_state.upper()}"
                feedback = loc(feedback_key) or new_state
                await cb.answer(f"Admin Filter: {feedback}")
            elif action == "list" and sub_action == "groups":
                await cb.answer("Generating list...")
                old_status = state["status"]
                state["status"] = "listing"
                await update_gp_dashboard(unique_id, cb=cb, state=state)
                
                chats, ignored_count = await get_target_chats(state["client"], state["target"], state.get("admin_filter", "non_admin"))
                chat_list = "\n".join([f"• {c['title']} (<code>{c['id']}</code>)" for c in chats[:50]])
                if len(chats) > 50: chat_list += f"\n...and {len(chats) - 50} more"
                
                state["status"] = old_status
                header_fmt = Altruix.get_string("GP_LIST_CHATS_HEADER") or "<b>Target Chats:</b>\n<i>(Total: {} | Ignored: {})</i>\n\n{}"
                custom_text = header_fmt.format(len(chats), ignored_count, chat_list or "None")
                await update_gp_dashboard(unique_id, custom_text=custom_text, cb=cb, state=state)
                return
            elif action == "start":
                if state["status"] == "running":
                    return await cb.answer("GPurgeme is already running!")
                # Request Confirmation
                state["status"] = "confirm_start"
                await update_gp_dashboard(unique_id, cb=cb, state=state)
                return
            elif action == "confirm":
                if sub_action == "start":
                    state["status"] = "running"
                    asyncio.create_task(gp_global_purgeme_task(unique_id))
                    await cb.answer("Global Purgeme Started!")
                elif sub_action == "cancel":
                    state["status"] = "idle"
                    await cb.answer("Cancelled.")
                    await update_gp_dashboard(unique_id, cb=cb, state=state)
                    return
            elif action == "pause":
                state["pause_event"].clear()
                state["status"] = "paused"
                await cb.answer("Paused.")
            elif action == "resume":
                state["pause_event"].set()
                state["status"] = "running"
                await cb.answer("Resumed.")
            elif action == "stop":
                state["stop_event"].set()
                state["pause_event"].set()
                state["status"] = "idle"
                await cb.answer("Stopping...")
            elif action == "refresh":
                await cb.answer("Refreshing...")
            elif action == "close":
                state["stop_event"].set()
                state["pause_event"].set()
                if unique_id in Altruix.GPURGEME_STATE: del Altruix.GPURGEME_STATE[unique_id]
                if cb.message:
                    await cb.message.delete()
                return

        await update_gp_dashboard(unique_id, cb=cb, state=state)
    except Exception as e:
        Altruix.log(f"GPurgeme Callback Error: {e}")
        await cb.answer(f"Error: {e}", show_alert=True)
