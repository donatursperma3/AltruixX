# Main/plugins/userbot/xgpurgeme_userbot.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.

import asyncio
import time
import logging
import os
import html
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, MessageNotModified
from Main import Altruix
from Main.core.types.message import Message
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from Main.internals.settings import send_log_notification
from Main.core.decorators import iuser_check

# Plugin Metadata
plugin_name = f"{os.path.basename(__file__)}"
__plugin_name__ = plugin_name if plugin_name else "xgpurgeme"
PLUGIN_VERSION = "1.0.12"

# STATE_LOCK is still needed for concurrency within the module
STATE_LOCK = asyncio.Lock()

# Helper to get user info robustly
async def _get_me(client):
    me = getattr(client, "myself", None) or client.me
    if not me:
        try:
            me = await client.get_me()
            client.myself = me
        except: return None
    return me

# Helper to get formatted status message
def get_gp_status_text(state):
    status = state["status"]
    processed_chats = state.get("processed_chats", 0)
    total_chats = state.get("total_chats", 0)
    deleted_count = state.get("deleted_count", 0)
    limit = state["limit"]
    delay = state["delay"]
    target = state["target"]
    ignore_admin = state.get("ignore_admin", False)
    mode = state.get("mode", "newest")
    offset = state.get("offset", 0)
    notify = state.get("notify", True)
    filters_list = state.get("filters", ["all"])
    
    gt = Altruix.get_string
    title = gt("GPURGEME_TITLE") or "🚮 <b>GLOBAL PURGEME DASHBOARD</b>"
    
    # Account Line
    client = state["client"]
    me = client.myself if hasattr(client, "myself") else None
    if me:
        account_name = f"<a href='tg://user?id={me.id}'>{html.escape(me.first_name)}</a>"
        account_str = (gt("GP_ACCOUNT_INFO") or "👤 <b>Account:</b> {}").format(account_name)
    else:
        account_str = ""

    target_str = gt(f"GP_BTN_TARGET_{target.upper()}") or target.capitalize()
    mode_str = gt(f"GP_BTN_MODE_{mode.upper()}") or mode.capitalize()
    filters_str = ", ".join([gt(f"GP_BTN_{f.upper()}") or f.capitalize() for f in filters_list])
    
    header = (
        f"{title}\n\n"
        f"{account_str}\n"
        f"{gt('GP_TARGET').format(target_str)}\n"
        f"{gt('GP_LIMIT').format(limit)} | {gt('GP_DELAY').format(delay)}\n"
        f"{gt('GP_MODE').format(mode_str)} | {gt('GP_OFFSET').format(offset)}\n"
        f"{gt('GP_FILTERS').format(filters_str)}\n"
        f"{gt('GP_IGNORE_ADMIN').format('✅' if ignore_admin else '❌')} | {gt('GP_NOTIF').format('✅' if notify else '❌')}\n\n"
    )

    if status == "idle":
        status_line = gt("GP_STATUS_IDLE") or "💤 <b>Status:</b> <code>Idle / Ready</code>"
    elif status == "listing":
        status_line = "📋 <b>Status:</b> <code>Generating group list...</code>"
    elif status == "running":
        status_line = (gt("GP_STATUS_RUNNING") or "🚀 <b>Status:</b> <code>Running</code>").format(processed_chats + 1, total_chats)
        status_line += f"\n🗑 <b>Deleted:</b> <code>{deleted_count} messages</code>"
        if state.get("current_chat"):
            status_line += f"\n📍 <b>Current Chat:</b> <code>{state['current_chat']}</code>"
    elif status == "paused":
        status_line = gt("GP_STATUS_PAUSED") or "⏸ <b>Status:</b> <code>Paused</code>"
        status_line += f"\n🗑 <b>Deleted:</b> <code>{deleted_count} messages</code>"
    elif status == "completed":
        status_line = gt("GP_STATUS_COMPLETED") or "✅ <b>Status:</b> <code>Completed</code>"
        status_line += f"\n🗑 <b>Total Deleted:</b> <code>{deleted_count} messages</code>"
    else:
        status_line = f"❓ <b>Status:</b> <code>{status}</code>"

    return f"{header}{status_line}"

# Helper to get control buttons
def get_gp_control_kb(unique_id, state):
    status = state["status"]
    target = state["target"]
    limit = state["limit"]
    delay = state["delay"]
    ignore_admin = state.get("ignore_admin", False)
    mode = state.get("mode", "newest")
    offset = state.get("offset", 0)
    notify = state.get("notify", True)
    filters_list = state.get("filters", ["all"])
    
    # Settings context
    is_settings = state.get("is_settings", False)
    index = state.get("index", 0)
    page = state.get("page", 0)
    
    gt = Altruix.get_string
    
    Altruix.log(f"DEBUG: Generating GP KB for {unique_id}. Limit: {limit}, Delay: {delay}, Target: {target}", level=20)
    
    kb = []
    
    if status == "idle" or status == "completed":
        # Target Toggle Buttons
        kb.append([
            InlineKeyboardButton(("✅ " if target == "all" else "") + (gt("GP_BTN_TARGET_ALL") or "All"), f"gp_target_all_{unique_id}"),
            InlineKeyboardButton(("✅ " if target == "groups" else "") + (gt("GP_BTN_TARGET_GROUPS") or "Groups"), f"gp_target_groups_{unique_id}"),
            InlineKeyboardButton(("✅ " if target == "personal" else "") + (gt("GP_BTN_TARGET_PERSONAL") or "Personal"), f"gp_target_personal_{unique_id}")
        ])
        
        # Limit Adjustment
        kb.append([
            InlineKeyboardButton(f"Limit: {limit}", "gp_noop"),
            InlineKeyboardButton("-2", f"gp_limit_m2_{unique_id}"),
            InlineKeyboardButton("+2", f"gp_limit_p2_{unique_id}")
        ])
        
        # Delay Adjustment
        kb.append([
            InlineKeyboardButton(f"Delay: {delay}s", "gp_noop"),
            InlineKeyboardButton("-2s", f"gp_delay_m2_{unique_id}"),
            InlineKeyboardButton("+2s", f"gp_delay_p2_{unique_id}")
        ])

        # Mode Selection
        kb.append([
            InlineKeyboardButton(f"Mode: {mode.capitalize()}", "gp_noop"),
            InlineKeyboardButton(("✅ " if mode == "newest" else "") + (gt("GP_BTN_MODE_NEWEST") or "Newest"), f"gp_mode_newest_{unique_id}"),
            InlineKeyboardButton(("✅ " if mode == "oldest" else "") + (gt("GP_BTN_MODE_OLDEST") or "Oldest"), f"gp_mode_oldest_{unique_id}")
        ])

        # Offset Selection
        kb.append([
            InlineKeyboardButton(f"Offset: {offset}", "gp_noop"),
            InlineKeyboardButton("-5", f"gp_off_m5_{unique_id}"),
            InlineKeyboardButton("+5", f"gp_off_p5_{unique_id}"),
            InlineKeyboardButton(gt("GP_BTN_RESET") or "Reset", f"gp_off_reset_{unique_id}")
        ])

        # Notif Toggle
        kb.append([
            InlineKeyboardButton(gt("GP_BTN_NOTIF_ON" if notify else "GP_BTN_NOTIF_OFF") or f"Notif: {'ON' if notify else 'OFF'}", f"gp_notif_{unique_id}")
        ])

        # Filters Grid
        def get_f_btn(f_type, label):
            active = "✅" if f_type in filters_list else "☑️"
            return InlineKeyboardButton(f"{active} {label}", f"gp_filter_{f_type}_{unique_id}")

        kb.append([
            get_f_btn("all", gt("GP_BTN_ALL") or "All"),
            get_f_btn("image", gt("GP_BTN_IMG") or "Img"),
            get_f_btn("video", gt("GP_BTN_VID") or "Vid")
        ])
        kb.append([
            get_f_btn("text", gt("GP_BTN_TXT") or "Txt"),
            get_f_btn("audio", gt("GP_BTN_AUD") or "Aud"),
            get_f_btn("sticker", gt("GP_BTN_STK") or "Stk")
        ])
        kb.append([
            get_f_btn("gif", gt("GP_BTN_GIF") or "Gif"),
            get_f_btn("file", gt("GP_BTN_FILE") or "File"),
            get_f_btn("vnote", gt("GP_BTN_VN") or "VN")
        ])

        # Advanced Options
        kb.append([
            InlineKeyboardButton(("✅ " if ignore_admin else "❌ ") + (gt("GP_BTN_IGNORE_ADMIN") or "Ignore Admin"), f"gp_toggle_admin_{unique_id}")
        ])
        kb.append([
            InlineKeyboardButton(gt("GP_BTN_LIST_CHATS") or "📋 List Chats", f"gp_list_groups_{unique_id}")
        ])
        kb.append([
            InlineKeyboardButton(gt("GP_BTN_START") or "🚀 Start GPurgeme", f"gp_start_{unique_id}"),
            InlineKeyboardButton(gt("GP_BTN_INFO") or "ℹ️ Info", f"gp_info_{unique_id}")
        ])
    elif status == "running":
        kb.append([
            InlineKeyboardButton(gt("GP_BTN_PAUSE") or "⏸ Pause", f"gp_pause_{unique_id}"),
            InlineKeyboardButton(gt("GP_BTN_STOP") or "🛑 Stop", f"gp_stop_{unique_id}")
        ])
    elif status == "paused":
        kb.append([
            InlineKeyboardButton(gt("GP_BTN_RESUME") or "▶️ Resume", f"gp_resume_{unique_id}"),
            InlineKeyboardButton(gt("GP_BTN_STOP") or "🛑 Stop", f"gp_stop_{unique_id}")
        ])
    elif status == "info":
        kb.append([InlineKeyboardButton(gt("GP_BTN_BACK") or "🔙 Back", f"gp_back_{unique_id}")])
    
    # Close/Refresh/Settings Back
    if status != "running":
        if is_settings:
            kb.append([
                InlineKeyboardButton("🔄 Refresh", f"gp_refresh_{unique_id}"), 
                InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}")
            ])
        else:
            kb.append([
                InlineKeyboardButton("🔄 Refresh", f"gp_refresh_{unique_id}"), 
                InlineKeyboardButton("❌ Close", f"gp_close_{unique_id}")
            ])
    
    return InlineKeyboardMarkup(kb)

async def update_gp_dashboard(unique_id, custom_text=None, cb=None, state=None):
    # If state is provided, assume caller holds lock or doesn't need it.
    if state:
        await _perform_dashboard_update(unique_id, state, custom_text, cb)
    else:
        # Otherwise, acquire lock and fetch state
        async with STATE_LOCK:
            state = Altruix.GPURGEME_STATE.get(unique_id)
            if state:
                await _perform_dashboard_update(unique_id, state, custom_text, cb)

async def _perform_dashboard_update(unique_id, state, custom_text, cb):
    # Check if we have EITHER a regular msg_id OR an inline_msg_id OR a valid callback
    if not state.get("dashboard_msg_id") and not state.get("inline_dashboard_id") and not cb:
        Altruix.log(f"DEBUG: update_gp_dashboard skipped. No Msg ID or Callback found for {unique_id}", level=20)
        return
    
    text = custom_text or get_gp_status_text(state)
    kb = get_gp_control_kb(unique_id, state)
    
    try:
        # Case 0: Direct Callback Edit (Most Robust for Buttons)
        if cb:
             Altruix.log(f"DEBUG: Updating GP Dashboard via Callback for {unique_id}", level=20)
             await cb.edit_message_text(
                 text,
                 reply_markup=kb,
                 disable_web_page_preview=True
             )
             return

        # Case 1: Inline Message Update
        if state.get("inline_dashboard_id"):
             Altruix.log(f"DEBUG: Updating GP Dashboard (Inline) for {unique_id}", level=20)
             await Altruix.bot.edit_inline_text(
                 state["inline_dashboard_id"],
                 text,
                 reply_markup=kb,
                 disable_web_page_preview=True
             )

        # Case 2: Regular Message Update (Settings or Direct)
        elif state.get("dashboard_msg_id"):
            # If in settings, ALWAYS use the main bot to update
            if state.get("is_settings"):
                bot = Altruix.bot
                Altruix.log(f"DEBUG: Updating Settings GP Dashboard for {unique_id} via main bot", level=20)
            else:
                me = await _get_me(state["client"])
                if not me: 
                    Altruix.log(f"DEBUG: Update failed - Could not fetch 'me' for {unique_id}", level=20)
                    return
                bot = Altruix.bot_manager.get_bot(me.id)
                Altruix.log(f"DEBUG: Updating GP Dashboard for {unique_id} via bot @{bot.me.username if bot.me else 'unknown'}", level=20)
                
            await bot.edit_message_text(
                state["dashboard_chat_id"],
                state["dashboard_msg_id"],
                text,
                reply_markup=kb,
                disable_web_page_preview=True
            )
        
        Altruix.log(f"DEBUG: GP Dashboard update SUCCESS for {unique_id}", level=20)
    except MessageNotModified:
        pass
    except Exception as e:
        Altruix.log(f"GPurgeme UI Update Fail: {e}", level=40)

async def gp_process_chat(client: Client, chat_id: int, limit: int, delay: int, state: dict):
    """Processes message deletion in a single chat."""
    deleted_in_chat = 0
    try:
        # Stop event check
        if state["stop_event"].is_set():
            return 0
            
        # Pause logic
        if not state["pause_event"].is_set():
            await state["pause_event"].wait()

        mode = state.get("mode", "newest")
        offset = state.get("offset", 0)
        target_filters = state.get("filters", ["all"])

        # Find messages sent by the userbot
        collected_ids = []
        
        # We fetch extra messages if offset is set to ensure we satisfy the limit after skipping
        # Pyrogram doesn't have a direct skip/offset in search_messages easily like get_chat_history
        # but we can fetch them all and then slice.
        # However, for global search across many chats, we should be careful.
        # For simplicity, we fetch up to limit + offset.
        
        async for msg in client.search_messages(chat_id, from_user="me", limit=limit + offset):
            # Apply media filters
            should_include = False
            if "all" in target_filters:
                should_include = True
            else:
                try:
                    if msg.text and "text" in target_filters: should_include = True
                    elif msg.photo and "image" in target_filters: should_include = True
                    elif msg.video and "video" in target_filters: should_include = True
                    elif (msg.voice or msg.audio) and "audio" in target_filters: should_include = True
                    elif msg.sticker and "sticker" in target_filters: should_include = True
                    elif msg.animation and "gif" in target_filters: should_include = True
                    elif msg.document and "file" in target_filters: should_include = True
                    elif msg.video_note and "vnote" in target_filters: should_include = True
                except: pass
            
            if should_include:
                collected_ids.append(msg.id)
            
            if len(collected_ids) >= limit + offset:
                break
            
            if state["stop_event"].is_set(): break
            
        if not collected_ids:
            return 0
            
        # Handle Mode: Newest returns newest first. Oldest needs reverse.
        if mode == "oldest":
            collected_ids.reverse()
            
        # Handle Offset: Skip N messages
        if offset > 0:
            collected_ids = collected_ids[offset:]
            
        # Satisy limit
        collected_ids = collected_ids[:limit]

        if not collected_ids:
            return 0
            
        # Delete messages in batches of 100 (Pyrogram limit)
        for i in range(0, len(collected_ids), 100):
            if state["stop_event"].is_set(): break
            batch = collected_ids[i:i+100]
            try:
                await client.delete_messages(chat_id, batch)
                deleted_in_chat += len(batch)
                state["deleted_count"] += len(batch)
                # Update UI periodically within chat
                if deleted_in_chat % 10 == 0:
                    asyncio.create_task(update_gp_dashboard(state["unique_id"]))
            except FloodWait as e:
                await asyncio.sleep(e.value)
            except Exception as e:
                Altruix.log(f"GPurgeme: Error deleting in {chat_id}: {e}")
        
        # Delay after finishing a chat
        if delay > 0 and not state["stop_event"].is_set():
            await asyncio.sleep(delay)
            
    except Exception as e:
        Altruix.log(f"GPurgeme: Error processing chat {chat_id}: {e}")
        
    return deleted_in_chat

async def get_target_chats(client: Client, target_type: str, ignore_admin: bool):
    """Collects list of target chats based on settings with safety delay."""
    chats = []
    ignored_count = 0
    total_scanned = 0
    
    async for dialog in client.get_dialogs():
        # Safety: Small delay every 20 dialogs to prevent floodwait during heavy scanning
        total_scanned += 1
        if total_scanned % 20 == 0:
            await asyncio.sleep(0.5)
            
        is_target = False
        chat_type = dialog.chat.type
        
        if target_type == "all":
            if chat_type in [enums.ChatType.PRIVATE, enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
                is_target = True
        elif target_type == "groups":
            if chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
                is_target = True
        elif target_type == "personal":
            if chat_type == enums.ChatType.PRIVATE:
                is_target = True
        
        if is_target:
            # Respect Ignore Admin/Owner
            should_ignore = False
            if ignore_admin and chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
                try:
                    me = await dialog.chat.get_member("me")
                    if me.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
                        should_ignore = True
                except:
                    pass
            
            if should_ignore:
                ignored_count += 1
            else:
                chats.append({
                    "id": dialog.chat.id,
                    "title": dialog.chat.title or f"{dialog.chat.first_name or ''} {dialog.chat.last_name or ''}".strip() or str(dialog.chat.id)
                })
                
    return chats, ignored_count

async def gp_global_purgeme_task(unique_id):
    """Main task that iterates through all chats."""
    async with STATE_LOCK:
        state = Altruix.GPURGEME_STATE.get(unique_id)
        if not state: return

    client = state["client"]
    target_type = state["target"]
    limit_per_chat = state["limit"]
    delay_per_chat = state["delay"]
    ignore_admin = state.get("ignore_admin", False)
    
    state["status"] = "running"
    state["start_time"] = time.time()
    state["deleted_count"] = 0
    state["processed_chats"] = 0
    state["processed_list"] = []
    state["stop_event"].clear()
    state["pause_event"].set()
    
    asyncio.create_task(update_gp_dashboard(unique_id))
    
    try:
        # Collect target chats
        chats_to_process = await get_target_chats(client, target_type, ignore_admin)
        state["total_chats"] = len(chats_to_process)
        asyncio.create_task(update_gp_dashboard(unique_id))
        
        if not chats_to_process:
            state["status"] = "completed"
            asyncio.create_task(update_gp_dashboard(unique_id))
            return

        # Process chats
        for chat_data in chats_to_process:
            if state["stop_event"].is_set(): break
            
            state["current_chat"] = chat_data["title"]
            asyncio.create_task(update_gp_dashboard(unique_id))
            
            deleted = await gp_process_chat(client, chat_data["id"], limit_per_chat, delay_per_chat, state)
            
            if deleted > 0:
                state["processed_list"].append(f"• {chat_data['title']} (<code>{deleted}</code>)")
            
            state["processed_chats"] += 1
            
        state["status"] = "completed"
        state["current_chat"] = None
        asyncio.create_task(update_gp_dashboard(unique_id))
        
        # Log Notification
        if not state.get("notify", True):
            return

        try:
            duration = round(time.time() - state["start_time"], 2)
            gt = Altruix.get_string
            processed_str = "\n".join(state["processed_list"][:30]) # Limit to 30 for UI
            if len(state["processed_list"]) > 30:
                processed_str += f"\n...and {len(state['processed_list']) - 30} more"
            
            if not processed_str: processed_str = "None"

            msg = (gt("GP_COMPLETED_MSG") or "✅ <b>Global Purgeme Completed!</b>").format(
                state["processed_chats"], state["deleted_count"], duration, processed_str
            )
            
            # Send to Log Group
            # Get actual session index
            try:
                s_idx = Altruix.clients.index(client)
            except:
                s_idx = 0
                
            await send_log_notification(
                client, "gpurgeme_completed", s_idx, client.me, True,
                error_msg=msg
            )
            
            # Also send to PM Bot Assistant as requested
            me = await _get_me(client)
            if me:
                bot = Altruix.bot_manager.get_bot(me.id)
                await bot.send_message(me.id, msg, disable_web_page_preview=True)

        except: pass

    except Exception as e:
        Altruix.log(f"GPurgeme Global Task Error: {e}")
        state["status"] = "idle"
        asyncio.create_task(update_gp_dashboard(unique_id))

# ---------------------------------------------------------
# COMMAND HANDLER
# ---------------------------------------------------------

@Altruix.register_on_cmd(
    ["gpurgeme"],
    cmd_help={
        "help": "Mass-delete your messages globally across chats.",
        "example": ".gpurgeme",
        "detail": """
<b>Global Purgeme (GPurgeme)</b>
Mass-delete your own messages across multiple chats with interactive UI.

<b>Options:</b>
• <b>Target:</b> All Chats, Groups Only, or Personal Chats only.
• <b>Limit:</b> Number of messages to delete per each chat.
• <b>Delay:</b> Sleep time between processing each chat to avoid floods.
• <b>Ignore Admin:</b> Exclude groups where you are an admin.

<b>Controls:</b>
Interactive dashboard allows Pausing, Resuming, and Stopping the process.
"""
    }
)
async def gpurgeme_cmd(client: Client, message: Message):
    # Sudo & Owner Check
    from Main.utils.access_control import is_authorized_user
    if not is_authorized_user(message.from_user.id, Altruix.config.OWNER_ID, Altruix.config.SUDO_USERS):
        return

    me = getattr(client, "myself", None) or client.me
    if not me:
        try:
            me = await client.get_me()
            client.myself = me
        except:
            return await message.edit("❌ Failed to fetch session info.")
            
    unique_id = f"gp_{me.id}"
    
    async with STATE_LOCK:
        if unique_id not in Altruix.GPURGEME_STATE:
            Altruix.GPURGEME_STATE[unique_id] = {
                "unique_id": unique_id,
                "client": client,
                "status": "idle",
                "target": "all",
                "limit": 6,
                "delay": 6,
                "ignore_admin": True,
                "mode": "newest",
                "offset": 0,
                "notify": True,
                "filters": ["all"],
                "deleted_count": 0,
                "processed_chats": 0,
                "total_chats": 0,
                "processed_list": [],
                "stop_event": asyncio.Event(),
                "pause_event": asyncio.Event(),
                "dashboard_msg_id": None,
                "dashboard_chat_id": None,
                "start_time": 0
            }
        state = Altruix.GPURGEME_STATE[unique_id]
        state["pause_event"].set()

    # Dashboard logic
    me = await _get_me(client)
    if not me: return
    bot_username = Altruix.bot_manager.get_bot_username(me.id)
    text = get_gp_status_text(state)
    kb = get_gp_control_kb(unique_id, state)

    try:
        # Try Inline first
        try:
            results = await client.get_inline_bot_results(bot_username, f"gp_menu_{unique_id}")
            if results.results:
                sent = await client.send_inline_bot_result(
                    message.chat.id,
                    results.query_id,
                    results.results[0].id,
                    reply_to_message_id=message.id
                )
                if sent:
                    state["dashboard_msg_id"] = sent.id
                    state["dashboard_chat_id"] = sent.chat.id
                # await message.delete_if_self()
                return
        except Exception as inline_e:
            Altruix.log(f"DEBUG: Inline query failed for {unique_id}: {inline_e}", level=20)
            pass

        # Fallback to direct bot message
        me = await _get_me(client)
        if not me: return
        bot = Altruix.bot_manager.get_bot(me.id)
        
        # PREVENT CRASH: If fallback tries to message the bot's own chat (e.g. user sends .gpurgeme in bot PM)
        # Bots cannot send messages to other bots or THEMSELVES via API initiation
        if message.chat.id == bot.me.id:
            await message.edit("❌ <b>Cannot show dashboard in Bot PM.</b>\nPlease use this command in your <b>Saved Messages</b> or enable Inline Mode in @BotFather.")
            return

        sent = await bot.send_message(
            message.chat.id, 
            text, 
            reply_markup=kb,
            reply_to_message_id=message.id
        )
        state["dashboard_msg_id"] = sent.id
        state["dashboard_chat_id"] = sent.chat.id
        # await message.delete_if_self()
    except Exception as e:
        await message.edit(f"❌ Error initiating GPurgeme: {e}")

@Altruix.register_on_cmd(
    ["gpurgemestatus", "gpstatus"],
    cmd_help={"help": "Check current Global Purgeme status."}
)
async def gp_status_cmd(client: Client, message: Message):
    me = getattr(client, "myself", None) or client.me
    if not me:
        try:
            me = await client.get_me()
            client.myself = me
        except: return
            
    unique_id = f"gp_{me.id}"
    state = Altruix.GPURGEME_STATE.get(unique_id)
    if not state:
        return await message.edit("❌ <b>No active Global Purgeme session.</b> Use <code>.gpurgeme</code> to start.")
    
    text = get_gp_status_text(state)
    await message.edit(text)

@Altruix.register_on_cmd(
    ["gpurgemestop", "gpstop"],
    cmd_help={"help": "Stop a running Global Purgeme process."}
)
async def gp_stop_cmd(client: Client, message: Message):
    me = getattr(client, "myself", None) or client.me
    if not me:
        try:
            me = await client.get_me()
            client.myself = me
        except: return
            
    unique_id = f"gp_{me.id}"
    state = Altruix.GPURGEME_STATE.get(unique_id)
    if not state:
        return await message.edit("❌ <b>No active Global Purgeme session.</b>")
    
    state["stop_event"].set()
    state["pause_event"].set()
    state["status"] = "idle"
    await message.edit("⏹ <b>Global Purgeme stopped manually.</b>")
    asyncio.create_task(update_gp_dashboard(unique_id))

@Altruix.register_on_cmd(
    ["gpurgemepause", "gppause"],
    cmd_help={"help": "Pause a running Global Purgeme process."}
)
async def gp_pause_cmd(client: Client, message: Message):
    me = getattr(client, "myself", None) or client.me
    if not me:
        try:
            me = await client.get_me()
            client.myself = me
        except: return
            
    unique_id = f"gp_{me.id}"
    state = Altruix.GPURGEME_STATE.get(unique_id)
    if not state or state["status"] != "running":
        return await message.edit("❌ <b>Global Purgeme is not running.</b>")
    
    state["pause_event"].clear()
    state["status"] = "paused"
    await message.edit("⏸ <b>Global Purgeme paused manually.</b>")
    asyncio.create_task(update_gp_dashboard(unique_id))

@Altruix.register_on_cmd(
    ["gpurgemeresume", "gpresume"],
    cmd_help={"help": "Resume a paused Global Purgeme process."}
)
async def gp_resume_cmd(client: Client, message: Message):
    me = getattr(client, "myself", None) or client.me
    if not me:
        try:
            me = await client.get_me()
            client.myself = me
        except: return
            
    unique_id = f"gp_{me.id}"
    state = Altruix.GPURGEME_STATE.get(unique_id)
    if not state or state["status"] != "paused":
        return await message.edit("❌ <b>Global Purgeme is not paused.</b>")
    
    state["pause_event"].set()
    state["status"] = "running"
    await message.edit("▶️ <b>Global Purgeme resumed manually.</b>")
    asyncio.create_task(update_gp_dashboard(unique_id))

# ---------------------------------------------------------
# CALLBACK HANDLERS
# ---------------------------------------------------------

@Altruix.bot.on_callback_query(filters.regex(r"^gp_(?P<action>target|limit|delay|pause|resume|stop|start|refresh|close|toggle|list|mode|off|notif|filter|info|back)_(?P<tail>.*)$"))
@iuser_check
async def gpurgeme_callback_handler(c: Client, cb: CallbackQuery):
    # Security: Allow only authorized users
    from Main.utils.access_control import is_authorized_user
    if not is_authorized_user(cb.from_user.id, Altruix.config.OWNER_ID, Altruix.config.SUDO_USERS):
        return await cb.answer("⛔ Access Denied", show_alert=True)

    try:
        action = cb.matches[0].group("action")
        tail = cb.matches[0].group("tail")
        
        Altruix.log(f"DEBUG: GP Callback action: {action}, tail: {tail}", level=20)
        
        # unique_id always starts with gp_ and is at the end
        # We need to find where gp_ starts in the tail
        import re
        match = re.search(r"(?P<sub_action>.*)_?(?P<uid>gp_\d+)$", tail)
        
        if match:
            sub_action = match.group("sub_action").rstrip("_")
            unique_id = match.group("uid")
        else:
            # Fallback for simple actions without sub_action
            unique_id = tail
            sub_action = None

        Altruix.log(f"DEBUG: GP Parsed sub_action: {sub_action}, unique_id: {unique_id}", level=20)

        async with STATE_LOCK:
            state = Altruix.GPURGEME_STATE.get(unique_id)
            if not state:
                Altruix.log(f"DEBUG: GP State not found for {unique_id}. Keys: {list(Altruix.GPURGEME_STATE.keys())}", level=20)
                # One more try: Maybe tail IS the unique_id (if sub_action check failed)
                state = Altruix.GPURGEME_STATE.get(tail)
                if state: 
                    unique_id = tail
                    Altruix.log(f"DEBUG: GP State found on second attempt for {unique_id}", level=20)
            
            if not state:
                await cb.answer("Session not found or expired.", show_alert=True)
                return

            # Self-healing: Capture inline_message_id if available (for inline dashboard)
            if cb.inline_message_id:
                 state["inline_dashboard_id"] = cb.inline_message_id
                 Altruix.log(f"DEBUG: Captured inline_dashboard_id for {unique_id}", level=20)
            
            # Helper: Capture dashboard_msg_id if missing (for Settings/Direct)
            if cb.message and not state.get("dashboard_msg_id"):
                 state["dashboard_msg_id"] = cb.message.id
                 state["dashboard_chat_id"] = cb.message.chat.id
                 Altruix.log(f"DEBUG: Captured dashboard_msg_id for {unique_id}", level=20)

            Altruix.log(f"DEBUG: Processing GP action '{action}' for {unique_id}. Current target: {state.get('target')}", level=20)

            if action == "target":
                state["target"] = sub_action
                await cb.answer(f"Target set to {state['target']}")
            elif action == "limit":
                if sub_action == "m2": state["limit"] = max(1, state["limit"] - 2)
                elif sub_action == "p2": state["limit"] += 2
                Altruix.log(f"DEBUG: Limit updated to {state['limit']} for {unique_id}", level=20)
                await cb.answer(f"Limit: {state['limit']} per chat")
            elif action == "delay":
                if sub_action == "m2": state["delay"] = max(0, state["delay"] - 2)
                elif sub_action == "p2": state["delay"] += 2
                Altruix.log(f"DEBUG: Delay updated to {state['delay']} for {unique_id}", level=20)
                await cb.answer(f"Delay: {state['delay']}s per chat")
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
                if sub_action == "all":
                    if "all" in f_list: f_list = []
                    else: f_list = ["all"]
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
                state["ignore_admin"] = not state.get("ignore_admin", False)
                await cb.answer(f"Ignore Admin: {'ON' if state['ignore_admin'] else 'OFF'}")
            elif action == "list" and sub_action == "groups":
                await cb.answer("Generating list...")
                old_status = state["status"]
                state["status"] = "listing"
                await update_gp_dashboard(unique_id, cb=cb, state=state)
                
                chats, ignored_count = await get_target_chats(state["client"], state["target"], state.get("ignore_admin", False))
                chat_list = "\n".join([f"• {c['title']} (<code>{c['id']}</code>)" for c in chats[:50]])
                if len(chats) > 50: chat_list += f"\n...and {len(chats) - 50} more"
                
                state["status"] = old_status
                header_fmt = Altruix.get_string("GP_LIST_CHATS_HEADER") or "<b>Target Chats:</b>\n<i>(Total: {} | Ignored: {})</i>\n\n{}"
                custom_text = header_fmt.format(len(chats), ignored_count, chat_list or "None")
                await update_gp_dashboard(unique_id, custom_text=custom_text, cb=cb, state=state)
                return
            elif action == "start":
                if state["status"] == "running":
                    await cb.answer("GPurgeme is already running!")
                    return
                state["status"] = "running"
                asyncio.create_task(gp_global_purgeme_task(unique_id))
                await cb.answer("Global Purgeme Started!")
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
                del Altruix.GPURGEME_STATE[unique_id]
                await cb.message.delete()
                return

        await update_gp_dashboard(unique_id, cb=cb, state=state)
    except Exception as e:
        Altruix.log(f"GPurgeme Callback Error: {e}")
        await cb.answer(f"Error: {e}", show_alert=True)
