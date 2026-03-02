PLUGIN_VERSION = "0.0.32"

"""
Purgeme Interactive Plugin for Altruix Userbot
Allows filtering by message type, custom delay, and batch processing with interactive UI.
"""

import asyncio
import time
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, MessageNotModified
from Main import Altruix
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from Main.internals.settings import send_log_notification
from Main.utils.essentials import Essentials

# Initialize shared state storage if not exists
if not hasattr(Altruix, "PURGEME_STATE"):
    Altruix.PURGEME_STATE = {}

STATE_LOCK = asyncio.Lock()

# Helper to get formatted status message
def get_purgeme_status_text(state):
    status = state["status"]
    count = state["count"]
    processed = state.get("processed", 0)
    scanned = state.get("scanned", 0) # Track scanned messages
    delay = state["delay"]
    types = state["types"]
    start_time = state.get("start_time", 0)
    mode = state.get("mode", "latest")
    
    title = Altruix.get_string("purgeme_title") or "🗑 <b>Userbot Purgeme</b>"
    
    def loc(key): return Altruix.get_string(key)
    
    # Dynamic Phase Indicator
    if status == "config":
        menu_title = loc("purgeme_menu_title") or "<b>⚙️ Purgeme Configuration</b>"
        chat_name = state.get("chat_name", "Unknown")
        chat_id = state.get("chat_id", "Unknown")
        chat_link = state.get("chat_link")
        
        display_name = f"<a href='{chat_link}'>{chat_name}</a>" if chat_link else f"<b>{chat_name}</b>"
        
        select_options = loc("purgeme_select_options") or "Please select options:"
        return (
            f"{title}\n\n"
            f"<b>Chat:</b> {display_name}\n"
            f"<b>Chat_ID:</b> <code>{chat_id}</code>\n\n"
            f"{menu_title}\n"
            f"{select_options}"
        )

    chat_name = state.get("chat_name", "Unknown")
    account_name = state.get("account_name", "Unknown")

    # Mapping for special types to YML keys
    TYPE_MAP = {
        "video_note": "VNOTE",
        "animation": "GIF",
        "document": "DOC",
        "location": "LOC",
        "contact": "CONT",
        "venue": "VEN"
    }

    # Common Header for active states
    if not types or "all" in types:
        type_display = loc("GP_BTN_ALL") or "ALL"
    elif len(types) > 1:
        type_display = (loc("purgeme_multiple") or "Multiple ({})").format(len(types))
    else:
        raw_type = types[0].lower()
        suffix = TYPE_MAP.get(raw_type, raw_type.upper())
        type_display = loc(f"GP_BTN_{suffix}") or suffix

    header = f"{title}\n" \
             f"<b>Mode:</b> {mode.capitalize()} | <b>Type:</b> {type_display}\n" \
             f"<b>Target:</b> {count} messages\n" \
             f"<b>Chat:</b> {chat_name}\n" \
             f"<b>Account:</b> {account_name}"

    if status == "collecting":
        status_line = (loc("purgeme_collecting_detailed") or "🔎 <b>Collecting...</b>\nFound: {processed}/{count}\nScanned: {scanned}").format(
            processed=processed, count=count, scanned=scanned
        )
        return f"{header}\n\n{status_line}"

    elif status == "running":
        status_line = (loc("purgeme_deleting_detailed") or "🗑 <b>Deleting...</b>\nDeleted: {processed}/{count}").format(
            processed=processed, count=count
        )
        if delay > 0: status_line += f"\nDelay: {delay}s"
        return f"{header}\n\n{status_line}"

    elif status == "paused":
        status_line = (loc("purgeme_paused_detailed") or "⏸ <b>PAUSED</b>\nDeleted: {processed}/{count}").format(
            processed=processed, count=count
        )
        return f"{header}\n\n{status_line}"

    elif status == "finished":
        start_time = state.get("start_time", 0)
        duration = round(time.time() - start_time, 2) if start_time > 0 else 0
        
        chat_link = state.get("chat_link")
        chat_display = f"<a href='{chat_link}'>{chat_name}</a>" if chat_link else f"<b>{chat_name}</b>"
        
        fin_text = (loc("purgeme_finished_detailed") or "✅ <b>Finished!</b>\nDeleted: {processed} messages\nTime: {duration}s\nChat: {chat}\nAccount: {account}").format(
            processed=processed, duration=duration, chat=chat_display, account=account_name
        )
        return f"{title}\n\n{fin_text}"

    elif status == "cancelled":
        lbl = loc("purgeme_cancelled_short") or "❌ <b>Cancelled</b>"
        return f"{title}\n\n{lbl}"
        
    return title

# Helper to get control buttons
async def get_purgeme_control_kb(unique_id, status, client_id):
    def loc(key): return Altruix.get_string(key)
    if status == "running":
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(await Essentials.get_user_button_style(client_id, loc("purgeme_pause") or "⏸ Pause"), callback_data=f"pg_pause_{unique_id}"),
                InlineKeyboardButton(await Essentials.get_user_button_style(client_id, loc("purgeme_stop") or "⏹ Stop"), callback_data=f"pg_stop_{unique_id}"),
            ],
            [InlineKeyboardButton(await Essentials.get_user_button_style(client_id, loc("status") or loc("purgeme_refresh") or "Status"), callback_data=f"pg_refresh_{unique_id}")]
        ])
    elif status == "paused":
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(await Essentials.get_user_button_style(client_id, loc("purgeme_resume") or "▶️ Resume"), callback_data=f"pg_resume_{unique_id}"),
                InlineKeyboardButton(await Essentials.get_user_button_style(client_id, loc("purgeme_stop") or "⏹ Stop"), callback_data=f"pg_stop_{unique_id}"),
            ],
             [InlineKeyboardButton(await Essentials.get_user_button_style(client_id, loc("status") or loc("purgeme_refresh") or "Status"), callback_data=f"pg_refresh_{unique_id}")]
        ])
    return None

async def collect_user_messages_optimized(client: Client, chat_id: int, user_id: int, target_types: list, limit: int = 100, offset: int = 0, state_callback=None):
    """
    OPTIMIZED: Collect user's message IDs using search_messages (async generator).
    state_callback: function to call for UI updates (passed with state dict)
    """
    collected_ids = []
    scanned_total = 0
    
    try:
        # METHOD 1: search_messages (The most efficient way)
        Altruix.log(f"Purgeme: Starting collection via search_messages for user {user_id}")
        
        try:
            # search_messages in Pyrogram is an async generator
            async for msg in client.search_messages(
                chat_id=chat_id,
                from_user=user_id,
                limit=limit,
                offset=offset
            ):
                scanned_total += 1
                
                # Identify message type and check if it should be included
                should_include = False
                if "all" in target_types:
                    should_include = True
                else:
                    try:
                        # Map Pyrogram message attributes to our filter types
                        if msg.text and "text" in target_types:
                            should_include = True
                        elif msg.photo and ("photo" in target_types or "image" in target_types):
                            should_include = True
                        elif msg.video and "video" in target_types:
                            should_include = True
                        elif (msg.voice or msg.audio) and "audio" in target_types:
                            should_include = True
                        elif msg.sticker and "sticker" in target_types:
                            should_include = True
                        elif msg.animation and ("animation" in target_types or "gif" in target_types):
                            should_include = True
                        elif msg.document and ("document" in target_types or "file" in target_types):
                            should_include = True
                        elif msg.video_note and ("video_note" in target_types or "vnote" in target_types):
                            should_include = True
                        elif msg.voice and "voice" in target_types:
                            should_include = True
                        elif msg.contact and "contact" in target_types:
                            should_include = True
                        elif msg.location and "location" in target_types:
                            should_include = True
                        elif msg.venue and "venue" in target_types:
                            should_include = True
                        elif msg.game and "game" in target_types:
                            should_include = True
                        elif msg.poll and "poll" in target_types:
                            should_include = True
                        elif msg.dice and "dice" in target_types:
                            should_include = True
                    except Exception as e:
                        Altruix.log(f"Purgeme: Type identification error: {e}", level=10)
                
                if should_include:
                    collected_ids.append(msg.id)
                
                # Update UI periodically (Every 10 messages found OR every 50 scanned)
                if state_callback and (scanned_total % 50 == 0 or len(collected_ids) % 10 == 0):
                    await state_callback(len(collected_ids), scanned_total)
                
                if len(collected_ids) >= limit:
                    break
                    
            if collected_ids:
                Altruix.log(f"Purgeme: search_messages SUCCESS - Found {len(collected_ids)} messages")
                return collected_ids
            else:
                Altruix.log(f"Purgeme: search_messages returned 0 results, forcing fallback to get_chat_history")
                
        except Exception as search_err:
            Altruix.log(f"Purgeme: search_messages FAILED ({search_err}), falling back to get_chat_history")
        
        # METHOD 2: Fallback to get_chat_history
        Altruix.log(f"Purgeme: Using get_chat_history fallback for user {user_id}")
        collected_ids = [] # Reset
        scanned_total = 0
        
        # Scan deeper - up to 5000 messages or 50x the limit
        max_scan = max(5000, limit * 50)
        
        try:
            async for msg in client.get_chat_history(chat_id, offset=offset):
                scanned_total += 1
                
                if scanned_total >= max_scan:
                    Altruix.log(f"Purgeme: Reached max scan limit ({max_scan}), stopping fallback collection")
                    break
                
                if not (msg.from_user and msg.from_user.id == user_id):
                    # Still update counter for "scanned" to show progress
                    if state_callback and scanned_total % 100 == 0:
                        await state_callback(len(collected_ids), scanned_total)
                    continue
                
                # Identify message type and check if it should be included
                should_include = False
                if "all" in target_types:
                    should_include = True
                else:
                    try:
                        # Map Pyrogram message attributes to our filter types
                        if msg.text and "text" in target_types:
                            should_include = True
                        elif msg.photo and ("photo" in target_types or "image" in target_types):
                            should_include = True
                        elif msg.video and "video" in target_types:
                            should_include = True
                        elif (msg.voice or msg.audio) and "audio" in target_types:
                            should_include = True
                        elif msg.sticker and "sticker" in target_types:
                            should_include = True
                        elif msg.animation and ("animation" in target_types or "gif" in target_types):
                            should_include = True
                        elif msg.document and ("document" in target_types or "file" in target_types):
                            should_include = True
                        elif msg.video_note and ("video_note" in target_types or "vnote" in target_types):
                            should_include = True
                        elif msg.voice and "voice" in target_types:
                            should_include = True
                        elif msg.contact and "contact" in target_types:
                            should_include = True
                        elif msg.location and "location" in target_types:
                            should_include = True
                        elif msg.venue and "venue" in target_types:
                            should_include = True
                        elif msg.game and "game" in target_types:
                            should_include = True
                        elif msg.poll and "poll" in target_types:
                            should_include = True
                        elif msg.dice and "dice" in target_types:
                            should_include = True
                    except Exception as e:
                        Altruix.log(f"Purgeme Fallback: Type identification error: {e}", level=10)
                
                if should_include:
                    collected_ids.append(msg.id)
                    
                    if state_callback and (len(collected_ids) % 10 == 0 or scanned_total % 100 == 0):
                        await state_callback(len(collected_ids), scanned_total)
                    
                    if len(collected_ids) >= limit:
                        break
        except Exception as iter_err:
             Altruix.log(f"Purgeme: Error during history iteration: {iter_err}")
        
        Altruix.log(f"Purgeme: get_chat_history complete - Found {len(collected_ids)} messages")
        return collected_ids
        
    except Exception as e:
        Altruix.log(f"Purgeme: Fatal collection error: {e}")
        return collected_ids



@Altruix.register_on_cmd(
    ["purgeme"],
    cmd_help={
        "help": "Purge messages with interactive UI configuration.",
        "example": ".purgeme or .purgeme <chat id/username>",
        "detail": """
<b>Interactive Purgeme Tool</b>

Use this command to delete your own messages with advanced filtering and controls.
The command triggers an interactive UI via your Assistant Bot.

<b>Usage:</b>
• <code>.purgeme</code> - Open UI for current chat.
• <code>.purgeme [chat_id/username]</code> - Open UI for a specific target chat.

<b>Features:</b>
• <b>Count</b>: Set exact number of messages to check/delete.
• <b>Delay</b>: Add delay between deletions to safe-guard against rate limits.
• <b>Types</b>: Filter by message content (Text, Image, Video, Audio, Sticker).
• <b>Controls</b>: Pause, Resume, and Stop the process at any time.

<b>Manual Commands:</b>
• <code>.purgemepause</code> - Pause current purge
• <code>.purgemeresume</code> - Resume purge
• <code>.purgemestop</code> - Stop purge
• <code>.purgemestatus</code> - Check status
"""
    }
)
async def purgeme_cmd(client: Client, message: Message):
    """
    Purge messages with interactive UI configuration.
    Supports filtering by 15 specialized message types.
    """
    # ✅ SAFETY CHECK: Basic message validity
    if not message or not hasattr(message, 'chat') or not message.chat:
        return

    # Sudo & Owner Check
    from Main.utils.access_control import is_authorized_user
    if not is_authorized_user(message.from_user.id, Altruix.config.OWNER_USERS_ID, Altruix.config.SUDO_USERS_ID):
        return

    # Check for target chat input
    input_chat = message.user_input
    chat_id = message.chat.id
    
    # Define local helper for localization strings
    def loc(key): return Altruix.get_string(key)
    
    if input_chat:
        try:
            # Handle username or ID (including negative IDs)
            if input_chat.lstrip('-').isdigit():
                resolved_chat = await client.get_chat(int(input_chat))
            else:
                resolved_chat = await client.get_chat(input_chat)
            chat_id = resolved_chat.id
        except Exception as e:
            return await message.handle_message(f"❌ **Invalid Chat Target:** `{input_chat}`\nError: {e}")

    user_id = client.me.id
    unique_id = f"{chat_id}_{user_id}"
    
    # Resolve Chat and Account info
    chat_link = None
    try:
        chat = await client.get_chat(chat_id)
        if chat.type == enums.ChatType.PRIVATE:
            chat_name = f"{chat.first_name} {chat.last_name}" if chat.last_name else chat.first_name
        else:
            chat_name = chat.title if chat.title else "Unknown Chat"
        
        # Generate Chat Link
        if chat.username:
            chat_link = f"https://t.me/{chat.username}"
        elif chat.type == enums.ChatType.PRIVATE:
            chat_link = f"tg://user?id={chat.id}"
        elif hasattr(chat, "invite_link") and chat.invite_link:
            chat_link = chat.invite_link
    except:
        chat_name = f"Chat {chat_id}"
        
    account_name = f"{client.me.first_name or ''} {client.me.last_name or ''}".strip() or f"User {client.me.id}"

    # Initialize State
    async with STATE_LOCK:
        Altruix.PURGEME_STATE[unique_id] = {
            "count": 20, # Default changed to 20
            "delay": 1.0, # Default changed to 1.0s
            "types": ["all"],
            "mode": "oldest",
            "batch_size": 30,
            "batch_delay": 0, # Default 0 (only active if toggled)
            "offset": 0,
            "status": "config",
            "event": asyncio.Event(),
            "stop_event": asyncio.Event(),
            "pause_event": asyncio.Event(),
            "client": client,
            "chat_id": chat_id,
            "chat_name": chat_name,
            "chat_link": chat_link,
            "account_name": account_name,
            "processed": 0,
            "start_time": 0,
            "dashboard_msg_id": None, 
            "dashboard_chat_id": None,
            "notify": True
        }
        # Pause event is set to True initially (not paused)
        Altruix.PURGEME_STATE[unique_id]["pause_event"].set()

    # Trigger Assistant UI
    try:
        bot_username = Altruix.bot_manager.get_bot_username(client.me.id)
        
        # 1. PM Logic: Use direct message via Bot assistant (Deletable)
        if message.chat.type == enums.ChatType.PRIVATE:
            from Main.plugins.bot.xpurgeme_bot import get_purgeme_text, get_purgeme_keyboard
            menu_text = get_purgeme_text(Altruix.PURGEME_STATE[unique_id])
            kb = await get_purgeme_keyboard(chat_id, user_id, unique_id)
            
            bot = Altruix.bot_manager.get_bot(client.me.id)
            sent_invite = await bot.send_message(
                message.chat.id,
                menu_text,
                reply_markup=kb,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )
            
            if sent_invite:
                state = Altruix.PURGEME_STATE.get(unique_id)
                if state:
                    state["dashboard_msg_id"] = sent_invite.id
                    state["dashboard_chat_id"] = sent_invite.chat.id
            
            await message.delete_if_self()
            
        # 2. Group Logic: Use Inline Query (Bypass membership)
        else:
            try:
                results = await client.get_inline_bot_results(bot_username, f"purgeme_menu_{unique_id}")
                if results.results:
                    sent_invite = await client.send_inline_bot_result(
                        message.chat.id,
                        results.query_id,
                        results.results[0].id,
                        reply_to_message_id=message.reply_to_message.id if message.reply_to_message else message.id
                    )
                    
                    if sent_invite:
                        state = Altruix.PURGEME_STATE.get(unique_id)
                        if state:
                            state["dashboard_msg_id"] = sent_invite.id
                            state["dashboard_chat_id"] = sent_invite.chat.id

                    await message.delete_if_self()
                else:
                    raise Exception("Empty inline results")
            except Exception as inline_e:
                raise inline_e

    except Exception as inner_e:
        Altruix.log(f"Purgeme Inline Fail: {inner_e} - Triggering Log & PM Fallback")
        
        # Send /start ONLY on failure to ensure bot is active for the user
        try:
            await client.send_message(bot_username, "/start")
        except Exception as start_err:
            Altruix.log(f"Purgeme: Auto-start bot failed: {start_err}")
        
        # 1. Notify Log Group
        try:
            await send_log_notification(
                client, "purgeme_inline_restricted", 0, client.me, False,
                error_msg=f"Inline Restricted in {chat_name} ({chat_id})",
                additional_info={"Reason": str(inner_e)}
            )
        except: pass

        # 2. Prepare Fallback Menu for PM
        from Main.plugins.bot.xpurgeme_bot import get_purgeme_text, get_purgeme_keyboard
        
        menu_text = get_purgeme_text(Altruix.PURGEME_STATE[unique_id])
        kb = await get_purgeme_keyboard(chat_id, client.me.id, unique_id)
        
        # 3. Send Direct PM via Bot Assistant
        try:
            pm_sent_msg = loc("purgeme_pm_sent") or "Configuration menu has been sent to your bot assistant's <b>Private Message (PM)</b>."
            await Altruix.bot.send_message(
                client.me.id,
                f"⚠️ <b>Inline Mode Restricted</b> in {chat_name}\n\n"
                f"Direct Menu:\n{menu_text}",
                reply_markup=kb,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )
            
            # Notify in group that menu was sent to PM
            msg_notif = await message.reply(
                f"⚠️ <b>Inline Mode Restricted</b>\n"
                f"{pm_sent_msg}",
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )
            await message.delete_if_self()
            # Auto delete notification after 9 seconds
            await asyncio.sleep(9)
            await msg_notif.delete()
        except Exception as pm_err:
            Altruix.log(f"Purgeme: Failed to send direct PM: {pm_err}")
            # FALLBACK URL if PM also fails or bot not started
            url = f"https://t.me/{bot_username}?start=purgeme_{unique_id}"
            click_here_msg = (loc("purgeme_pm_click_here") or "Please <a href='{url}'>Klik Disini</a> untuk konfigurasi via PM.").format(url=url)
            msg_notif = await message.reply(
                f"⚠️ <b>Inline Mode Restricted</b>\n"
                f"{click_here_msg}",
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )
            # Auto delete notification after 9 seconds
            await asyncio.sleep(9)
            await msg_notif.delete()

    except Exception as e:
        await message.edit(f"❌ Error initiating Purgeme: {e}")
        return

    # Wait for 'Start' signal from UI
    state = Altruix.PURGEME_STATE.get(unique_id)
    if not state:
        Altruix.log(f"Purgeme: State lost for {unique_id} before start execution")
        # cleanup if it was somehow deleted
        return
        
    try:
        # Wait up to 10 minutes (600s) for configuration to prevent "Session not found" too early
        await asyncio.wait_for(state["event"].wait(), timeout=600)
    except asyncio.TimeoutError:
        if unique_id in Altruix.PURGEME_STATE:
            del Altruix.PURGEME_STATE[unique_id]
        return

    # Check if cancelled
    if state["status"] == "cancelled":
        del Altruix.PURGEME_STATE[unique_id]
        return

    # Start Purging
    state["status"] = "running"
    state["start_time"] = time.time()
    count = state["count"]
    delay = state["delay"] 
    batch_size = state.get("batch_size", 30)
    batch_delay = state.get("batch_delay", 0)
    offset = state.get("offset", 0)
    target_types = state["types"]
    mode = state.get("mode", "latest")
    
    # ---------------------------------------------------------
    # DASHBOARD CREATION - MOVED TO TARGET CHAT
    # ---------------------------------------------------------
    
    dashboard_chat = chat_id # ALWAYS TARGET CHAT
    
    # Check if we already have a dashboard message in the target chat (e.g. from Inline menu)
    if state.get("dashboard_msg_id") and state.get("dashboard_chat_id") == dashboard_chat:
        Altruix.log(f"Purgeme: Reusing existing dashboard message {state['dashboard_msg_id']} in {dashboard_chat}")
        # Message already exists and is tracked, just proceed to updates
    else:
        try:
            dash_text = get_purgeme_status_text(state)
            dash_kb = await get_purgeme_control_kb(unique_id, "running", client.me.id)
            
            # Try to send via appropriate bot (custom if available, fallback to main Altruix.bot)
            bot = Altruix.bot_manager.get_bot(client.me.id)
            try:
                dash_msg = await bot.send_message(
                    dashboard_chat,
                    dash_text,
                    reply_markup=dash_kb,
                    disable_web_page_preview=True
                )
            except Exception as bot_err:
                Altruix.log(f"Purgeme Dashboard Primary Bot Fail: {bot_err}. Trying fallback to main bot.")
                try:
                    # Fallback to main Altruix.bot if custom bot failed
                    dash_msg = await Altruix.bot.send_message(
                        dashboard_chat,
                        dash_text,
                        reply_markup=dash_kb,
                        disable_web_page_preview=True
                    )
                except Exception as main_err:
                    Altruix.log(f"Purgeme Dashboard Main Bot Fail: {main_err}. Trying fallback to PM.")
                    # FALLBACK TO PM (Send to userbot account via bot)
                    dashboard_chat = client.me.id
                    dash_msg = await bot.send_message(
                        dashboard_chat,
                        dash_text,
                        reply_markup=dash_kb,
                        disable_web_page_preview=True
                    )
                
            state["dashboard_msg_id"] = dash_msg.id
            state["dashboard_chat_id"] = dashboard_chat
        except Exception as e:
            Altruix.log(f"Purgeme Dashboard Critical Error: {e}")
            # If all fail to send, try log_chat using main bot
            if Altruix.log_chat:
                dashboard_chat = Altruix.log_chat
                try:
                    dash_msg = await Altruix.bot.send_message(
                        dashboard_chat,
                        dash_text,
                        reply_markup=dash_kb,
                        disable_web_page_preview=True
                    )
                    state["dashboard_msg_id"] = dash_msg.id
                    state["dashboard_chat_id"] = dashboard_chat
                except Exception as final_e:
                     Altruix.log(f"Purgeme Dashboard Final Fallback Fail: {final_e}")

    # Execution Loop
    deleted_count = 0
    state["scanned"] = 0
    
    Altruix.log(f"Purgeme {mode.capitalize()}: Starting OPTIMIZED deletion process for {count} messages")
    
    try:
        # Collection Phase
        state["status"] = "collecting"
        asyncio.create_task(update_dashboard(state))
        
        # Callback wrapper to update state and dashboard
        async def collection_callback(collected, scanned):
            state["processed"] = collected
            state["scanned"] = scanned
            # Rate limit updates to avoid flood
            if scanned % 20 == 0 or collected == state["count"]:
                asyncio.create_task(update_dashboard(state))

        collected_ids = await collect_user_messages_optimized(
            client, 
            chat_id, 
            user_id, 
            target_types, 
            limit=count,
            offset=offset,
            state_callback=collection_callback
        )
        
        if not collected_ids:
            Altruix.log("Purgeme Optimized: No messages found matching criteria")
            state["status"] = "finished"
            state["processed"] = 0
            asyncio.create_task(update_dashboard(state))
        else:
            # Handle mode selection
            if mode == "oldest":
                # Reverse to get oldest first (search_messages returns newest first)
                collected_ids.reverse()
                Altruix.log(f"Purgeme Optimized: Reversed to oldest-first order ({len(collected_ids)} messages)")
            else:
                Altruix.log(f"Purgeme Optimized: Using newest-first order ({len(collected_ids)} messages)")
            
            # Update state
            state["status"] = "running"
            state["processed"] = 0
            asyncio.create_task(update_dashboard(state))
            
            # ---------------------------------------------------------
            # DELETION PHASE (BATCH SUPPORTED)
            # ---------------------------------------------------------
            
            # Outer loop for Batches
            for b_idx in range(0, len(collected_ids), batch_size):
                if state["stop_event"].is_set():
                    break
                    
                # Get current batch
                batch_ids = collected_ids[b_idx : b_idx + batch_size]
                
                # Check Pause
                if not state["pause_event"].is_set():
                    last_status = state["status"]
                    state["status"] = "paused"
                    asyncio.create_task(update_dashboard(state))
                    await state["pause_event"].wait()
                    state["status"] = last_status # Restore running
                    asyncio.create_task(update_dashboard(state))

                # Process the batch (sub-chunking if delay is present)
                inner_chunk_size = 1 if delay > 0 else 100
                
                for i in range(0, len(batch_ids), inner_chunk_size):
                    chunk = batch_ids[i:i+inner_chunk_size]
                    
                    retry_count = 0
                    max_retries = 3
                    delete_success = False

                    while not delete_success and retry_count < max_retries:
                        try:
                            await client.delete_messages(chat_id, chunk)
                            deleted_count += len(chunk)
                            state["processed"] = deleted_count
                            delete_success = True
                            
                            # UI Update (Throttle)
                            if deleted_count % 10 == 0 or delay > 0:
                                asyncio.create_task(update_dashboard(state))
                                
                            if delay > 0: 
                                await asyncio.sleep(delay)
                                
                        except FloodWait as fw:
                            retry_count += 1
                            Altruix.log(f"Purgeme FloodWait: {fw.value}s")
                            await asyncio.sleep(fw.value)
                        except Exception as e:
                            retry_count += 1
                            Altruix.log(f"Purgeme Delete Error: {e}")
                            await asyncio.sleep(1)
                
                # End of Batch Delay
                if (b_idx + batch_size < len(collected_ids)) and batch_delay > 0:
                    Altruix.log(f"Purgeme: Batch delay {batch_delay}s...")
                    # Optional: Update status to show Waiting???
                    # For now just sleep
                    await asyncio.sleep(batch_delay)


    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception as e:
        Altruix.log(f"Purgeme Error: {e}")

    # Finish
    if state.get("status") == "cancelled":
        Altruix.log(f"Purgeme: Task {unique_id} aborted by user.")
        # Cleanup state and exit
        if unique_id in Altruix.PURGEME_STATE:
            del Altruix.PURGEME_STATE[unique_id]
        return

    state["status"] = "finished"
    await update_dashboard(state)
    
    # CALCULATE FINAL STATS
    duration = time.time() - state.get("start_time", 0)
    duration_str = f"{round(duration, 2)}s"
    
    # Wait 3 seconds before deleting the dashboard
    await asyncio.sleep(3)

    # CLEANUP DASHBOARD (Delete it from group to make space for success message)
    try:
        if state.get("dashboard_msg_id") and state.get("dashboard_chat_id"):
            # Use Userbot to delete its own inline result message
            # This ensures deletion works even if the bot assistant is not in the chat
            try:
                await state["client"].delete_messages(state["dashboard_chat_id"], state["dashboard_msg_id"])
            except:
                pass
    except: 
        pass

    # Send detailed completion log to LOG_CHAT_ID
    try:
        if Altruix.log_chat:
            # Get chat info
            try:
                chat = await client.get_chat(chat_id)
                chat_title = chat.title if hasattr(chat, 'title') and chat.title else f"Private Chat"
                chat_type = "Group" if chat_id < 0 else "PM"
            except:
                chat_title = "Unknown Chat"
                chat_type = "Unknown"
            
            # Get user info
            user_name = client.me.first_name or "Unknown"
            user_mention = f'<a href="tg://user?id={user_id}">{user_name}</a>'
            
            # Create chat hyperlink
            chat_link = chat_title
            try:
                if chat_id < 0:
                    # Check if we have a username (Public Group/Channel)
                    if 'chat' in locals() and chat and getattr(chat, 'username', None):
                        chat_link = f'<a href="https://t.me/{chat.username}">{chat_title}</a>'
                    # Private Group/Channel
                    elif str(chat_id).startswith("-100"):
                        clean_chat_id = str(chat_id)[4:]
                        chat_link = f'<a href="https://t.me/c/{clean_chat_id}/1">{chat_title}</a>'
            except Exception as link_err:
                Altruix.log(f"Purgeme: Error creating chat link: {link_err}")
                chat_link = chat_title
            
            # Calculate duration
            duration = time.time() - state.get("start_time", 0)
            duration_str = f"{round(duration, 2)}s"
            
            # Determine final status emoji and text
            status_emoji = "✅"
            final_status = "Finished!"
            if state.get("stop_event") and state["stop_event"].is_set():
                status_emoji = "⏹"
                final_status = "Stopped"
            elif deleted_count == 0:
                status_emoji = "⚠️"
                final_status = "No matches found"
            elif deleted_count < count:
                final_status = "Partially Deleted"

            # requested format:
            # 🗑 Userbot Purgeme
            # Mode: Oldest | Type: TEXT
            # Target: 60 messages | Offset: 0
            # Batch: 30 | DelayBc: 4m
            # Chat: Sharing Bot Telegram
            # Account: CoolKid 369

            # 🗑 Deleting... (or Finished!)
            # Deleted: 30/60
            # Delay: 1.0s
            
            # Use current status text directly for the bottom part or reconstruct
            log_msg = (
                f"🗑 <b>Userbot Purgeme</b>\n"
                f"• <b>Mode:</b> {mode.capitalize()} | <b>Type:</b> <code>{type_display}</code>\n"
                f"• <b>Target:</b> <code>{count}</code> messages | <b>Offset:</b> <code>{offset}</code>\n"
                f"• <b>Batch:</b> <code>{batch_size}</code> | <b>DelayBc:</b> <code>{int(batch_delay/60)}m</code>\n"
                f"• <b>Chat:</b> {chat_link}\n"
                f"• <b>Account:</b> <code>{account_name}</code>\n\n"
                f"{status_emoji} <b>{final_status}</b>\n"
                f"• <b>Deleted:</b> <code>{deleted_count}/{count}</code>\n"
                f"• <b>Delay:</b> <code>{delay}s</code>"
            )

            # Always use main bot for log chat to ensure member access
            await Altruix.bot.send_message(
                Altruix.log_chat,
                log_msg,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )
            
            # Send completion notification to target chat (auto-delete after 9s)
            if state.get("notify", True):
                try:
                    title = Altruix.get_string("purgeme_title") or "🗑 <b>Userbot Purgeme</b>"
                    completion_msg = (loc("purgeme_task_completed_short") or "✅ <b>The task has been completed in execution!</b>\nDeleted: <b>{count}</b> messages | Mode: <b>{mode}</b> | Duration: <b>{duration}</b>").format(
                        count=deleted_count, mode=mode.capitalize(), duration=duration_str
                    )
                    
                    # Determine which bot to use for the notification
                    target_bot = Altruix.bot_manager.get_bot(client.me.id)
                    try:
                        target_notif = await target_bot.send_message(
                            chat_id,
                            completion_msg,
                            parse_mode=enums.ParseMode.HTML,
                            disable_web_page_preview=True
                        )
                    except:
                        # Fallback to main bot or Userbot (Client) if custom bot fails
                        try:
                            target_notif = await Altruix.bot.send_message(
                                chat_id,
                                completion_msg,
                                parse_mode=enums.ParseMode.HTML,
                                disable_web_page_preview=True
                            )
                        except:
                            # Final Fallback: Use Userbot itself as it's guaranteed to be in the chat
                            target_notif = await client.send_message(
                                chat_id,
                                completion_msg,
                                parse_mode=enums.ParseMode.HTML,
                                disable_web_page_preview=True
                            )
                    
                    
                    # Auto-delete after 9 seconds as requested
                    await asyncio.sleep(9)
                    await target_notif.delete()
                except Exception as notif_err:
                    Altruix.log(f"Failed to send target chat notification: {notif_err}")
                    # Try one last time with Userbot client to log chat if target chat failed
                    try:
                        if Altruix.log_chat:
                             await client.send_message(Altruix.log_chat, f"⚠️ Purgeme Notification Fail: {notif_err}")
                    except: pass
    except Exception as log_err:
        Altruix.log(f"Failed to send Purgeme completion log: {log_err}")
    
    # Wait a bit then clean up
    # EXTENDED CLEANUP DELAY to allow user to see result/click Close (300s = 5 mins)
    await asyncio.sleep(300)
    if unique_id in Altruix.PURGEME_STATE:
        del Altruix.PURGEME_STATE[unique_id]

async def update_dashboard(state):
    """Updates the dashboard message with current state"""
    try:
        if state.get("dashboard_chat_id") and state.get("dashboard_msg_id"):
            text = get_purgeme_status_text(state)
            current_client = state["client"]
            client_id = current_client.me.id if current_client.me else None
            uid = f"{state['chat_id']}_{client_id}"
            kb = await get_purgeme_control_kb(uid, state["status"], client_id)

            target_bot = Altruix.bot if state["dashboard_chat_id"] == Altruix.log_chat else Altruix.bot_manager.get_bot(state["client"].me.id)
            
            try:
                await target_bot.edit_message_text(
                    chat_id=state["dashboard_chat_id"],
                    message_id=state["dashboard_msg_id"],
                    text=text,
                    reply_markup=kb,
                    disable_web_page_preview=True
                )
            except MessageNotModified:
                pass
            except Exception as e:
                # Retry with main bot if primary bot failed
                if target_bot != Altruix.bot:
                    try:
                        await Altruix.bot.edit_message_text(
                            chat_id=state["dashboard_chat_id"],
                            message_id=state["dashboard_msg_id"],
                            text=text,
                            reply_markup=kb,
                            disable_web_page_preview=True
                        )
                    except Exception as e2:
                        Altruix.log(f"Purgeme Dashboard Update Fail (Both Bots): {e2}")
                else:
                    Altruix.log(f"Purgeme Dashboard Update Fail: {e}")
    except Exception as e:
        Altruix.log(f"Purgeme Dashboard Critical: {e}")

# ---------------------------------------------------------
# MANUAL COMMANDS
# ---------------------------------------------------------

@Altruix.register_on_cmd(["purgemepause", "ppaause"], cmd_help={"help": "Pause running purge", "example": ".purgemepause [chat_id/username]"})
async def purgeme_pause_cmd(client: Client, message: Message):
    input_chat = message.user_input
    chat_id = message.chat.id
    if input_chat:
        try:
            res = await client.get_chat(int(input_chat) if input_chat.lstrip('-').isdigit() else input_chat)
            chat_id = res.id
        except: pass

    def loc(key): return Altruix.get_string(key)
    uid = f"{chat_id}_{client.me.id}"
    state = Altruix.PURGEME_STATE.get(uid)
    if state and state["status"] == "running":
        state["pause_event"].clear()
        state["status"] = "paused"
        await update_dashboard(state)
        msg = (loc("purgeme_manual_paused") or "⏸ <b>Purgeme Paused</b> (Chat: {chat})").format(chat=chat_id)
        await message.edit(msg)
    else:
        msg = (loc("purgeme_no_running") or "❌ No running purge found for chat: {chat}").format(chat=chat_id)
        await message.edit(msg)

@Altruix.register_on_cmd(["purgemeresume", "presume"], cmd_help={"help": "Resume paused purge", "example": ".purgemeresume [chat_id/username]"})
async def purgeme_resume_cmd(client: Client, message: Message):
    input_chat = message.user_input
    chat_id = message.chat.id
    if input_chat:
        try:
            res = await client.get_chat(int(input_chat) if input_chat.lstrip('-').isdigit() else input_chat)
            chat_id = res.id
        except: pass

    def loc(key): return Altruix.get_string(key)
    uid = f"{chat_id}_{client.me.id}"
    state = Altruix.PURGEME_STATE.get(uid)
    if state and state["status"] == "paused":
        state["pause_event"].set()
        state["status"] = "running"
        await update_dashboard(state)
        msg = (loc("purgeme_manual_resumed") or "▶️ <b>Purgeme Resumed</b> (Chat: {chat})").format(chat=chat_id)
        await message.edit(msg)
    else:
        msg = (loc("purgeme_no_paused") or "❌ No paused purge found for chat: {chat}").format(chat=chat_id)
        await message.edit(msg)

@Altruix.register_on_cmd(["purgemestop", "pstop"], cmd_help={"help": "Stop running purge", "example": ".purgemestop [chat_id/username]"})
async def purgeme_stop_cmd(client: Client, message: Message):
    input_chat = message.user_input
    chat_id = message.chat.id
    if input_chat:
        try:
            res = await client.get_chat(int(input_chat) if input_chat.lstrip('-').isdigit() else input_chat)
            chat_id = res.id
        except: pass

    def loc(key): return Altruix.get_string(key)
    uid = f"{chat_id}_{client.me.id}"
    state = Altruix.PURGEME_STATE.get(uid)
    if state:
        state["stop_event"].set()
        msg = (loc("purgeme_manual_stopping") or "⏹ <b>Purgeme Stopping...</b> (Chat: {chat})").format(chat=chat_id)
        await message.edit(msg)
    else:
        msg = (loc("purgeme_no_active") or "❌ No active purge found for chat: {chat}").format(chat=chat_id)
        await message.edit(msg)

@Altruix.register_on_cmd(["purgemestatus", "pstatus"], cmd_help={"help": "Check purge status", "example": ".purgemestatus [chat_id/username]"})
async def purgeme_status_cmd(client: Client, message: Message):
    input_chat = message.user_input
    chat_id = message.chat.id
    if input_chat:
        try:
            res = await client.get_chat(int(input_chat) if input_chat.lstrip('-').isdigit() else input_chat)
            chat_id = res.id
        except: pass

    def loc(key): return Altruix.get_string(key)
    uid = f"{chat_id}_{client.me.id}"
    state = Altruix.PURGEME_STATE.get(uid)
    if state:
        text = get_purgeme_status_text(state)
        await message.edit(text, disable_web_page_preview=True)
    else:
        msg = (loc("purgeme_no_active") or "❌ No active purge session for chat: {chat}").format(chat=chat_id)
        await message.edit(msg)

