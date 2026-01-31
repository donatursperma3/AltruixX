
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
        desc = loc("purgeme_desc") or "Configure purge settings"
        return f"{title}\n{desc}"

    # Common Header for active states
    header = f"{title}\n" \
             f"<b>Mode:</b> {mode.capitalize()} | <b>Type:</b> {types[0].upper() if types else 'ALL'}\n" \
             f"<b>Target:</b> {count} messages"

    if status == "collecting":
        lbl = loc("purgeme_collecting")
        status_line = f"🔎 <b>Collecting...</b>\nFound: {processed}/{count}\nScanned: {scanned}"
        return f"{header}\n\n{status_line}"

    elif status == "running":
        lbl = loc("purgeme_status_deleting")
        status_line = f"🗑 <b>Deleting...</b>\nDeleted: {processed}/{count}"
        if delay > 0: status_line += f"\nDelay: {delay}s"
        return f"{header}\n\n{status_line}"

    elif status == "paused":
        status_line = f"⏸ <b>PAUSED</b>\nDeleted: {processed}/{count}"
        return f"{header}\n\n{status_line}"

    elif status == "finished":
        lbl = loc("purgeme_finished")
        start_time = state.get("start_time", 0)
        duration = time.time() - start_time if start_time > 0 else 0
        return f"{title}\n\n✅ <b>Finished!</b>\nDeleted: {processed} messages\nTime: {round(duration, 2)}s"

    elif status == "cancelled":
        return f"{title}\n\n❌ <b>Cancelled</b>"
        
    return title

# Helper to get control buttons
def get_purgeme_control_kb(unique_id, status):
    if status == "running":
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⏸ Pause", callback_data=f"pg_pause_{unique_id}"),
                InlineKeyboardButton("⏹ Stop", callback_data=f"pg_stop_{unique_id}"),
            ],
            [InlineKeyboardButton("Status", callback_data=f"pg_refresh_{unique_id}")]
        ])
    elif status == "paused":
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("▶️ Resume", callback_data=f"pg_resume_{unique_id}"),
                InlineKeyboardButton("⏹ Stop", callback_data=f"pg_stop_{unique_id}"),
            ],
             [InlineKeyboardButton("Status", callback_data=f"pg_refresh_{unique_id}")]
        ])
    return None

async def collect_user_messages_optimized(client: Client, chat_id: int, user_id: int, target_types: list, limit: int = 100, state_callback=None):
    """
    OPTIMIZED: Collect user's message IDs with hybrid approach.
    state_callback: function to call for UI updates (passed with state dict)
    """
    collected_ids = []
    scanned_total = 0
    
    try:
        # METHOD 1: Try search_messages first
        Altruix.log(f"Purgeme: Attempting search_messages for user {user_id}")
        
        try:
            offset = 0
            batch_size = 100
            search_attempts = 0
            max_search_attempts = 50 # Increased significantly for reliability
            
            while len(collected_ids) < limit and search_attempts < max_search_attempts:
                # Always request batch_size to maximize throughput, rely on 'limit' check in loop
                request_limit = batch_size 
                messages = await client.search_messages(
                    chat_id=chat_id,
                    from_user=user_id,
                    limit=request_limit,
                    offset=offset
                )
                
                if not messages:
                    Altruix.log(f"Purgeme: search_messages returned no results (offset: {offset})")
                    break
                
                # Filter by type
                for msg in messages:
                    scanned_total += 1
                    if len(collected_ids) >= limit:
                        break
                        
                    should_include = False
                    if "all" in target_types:
                        should_include = True
                    else:
                        try:
                            if msg.text and "text" in target_types: should_include = True
                            elif msg.photo and "image" in target_types: should_include = True
                            elif msg.video and "video" in target_types: should_include = True
                            elif (msg.voice or msg.audio) and "audio" in target_types: should_include = True
                            elif msg.sticker and "sticker" in target_types: should_include = True
                            elif msg.animation and "gif" in target_types: should_include = True
                            elif msg.document and "file" in target_types: should_include = True
                            elif msg.video_note and "vnote" in target_types: should_include = True
                        except:
                            pass
                    
                    if should_include:
                        collected_ids.append(msg.id)
                
                # Update UI periodically
                if state_callback:
                    await state_callback(len(collected_ids), scanned_total)
                
                Altruix.log(f"Purgeme: search_messages collected {len(collected_ids)}/{limit}")
                
                if len(messages) < request_limit:
                    if len(messages) == 0: break # End of stream
                    break
                    
                offset += len(messages)
                search_attempts += 1
            
            # If search_messages worked, return results
            if collected_ids:
                Altruix.log(f"Purgeme: search_messages SUCCESS - Found {len(collected_ids)} messages")
                return collected_ids
            else:
                Altruix.log(f"Purgeme: search_messages returned 0 results, falling back to get_chat_history")
                
        except Exception as search_err:
            Altruix.log(f"Purgeme: search_messages FAILED ({search_err}), falling back to get_chat_history")
        
        # METHOD 2: Fallback to optimized get_chat_history
        Altruix.log(f"Purgeme: Using get_chat_history fallback for user {user_id}")
        collected_ids = [] # Reset if previous method failed partially
        scanned_total = 0
        
        # Scan much deeper - up to 5000 messages or 50x the limit
        max_scan = max(5000, limit * 50)
        
        try:
            async for msg in client.get_chat_history(chat_id):
                scanned_total += 1
                
                if scanned_total >= max_scan:
                    Altruix.log(f"Purgeme: Reached max scan limit ({max_scan}), stopping fallback collection")
                    break
                
                if not (msg.from_user and msg.from_user.id == user_id):
                    continue
                
                # Filter by type
                should_include = False
                if "all" in target_types:
                    should_include = True
                else:
                    try:
                        if msg.text and "text" in target_types: should_include = True
                        elif msg.photo and "image" in target_types: should_include = True
                        elif msg.video and "video" in target_types: should_include = True
                        elif (msg.voice or msg.audio) and "audio" in target_types: should_include = True
                        elif msg.sticker and "sticker" in target_types: should_include = True
                        elif msg.animation and "gif" in target_types: should_include = True
                        elif msg.document and "file" in target_types: should_include = True
                        elif msg.video_note and "vnote" in target_types: should_include = True
                    except:
                        pass
                
                if should_include:
                    collected_ids.append(msg.id)
                    
                    if state_callback and (len(collected_ids) % 10 == 0):
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
        "example": ".purgeme",
        "detail": """
<b>Interactive Purgeme Tool</b>

Use this command to delete your own messages with advanced filtering and controls.
The command triggers an interactive UI via your Assistant Bot.

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
    chat_id = message.chat.id
    user_id = client.me.id
    unique_id = f"{chat_id}_{user_id}"
    
    # Initialize State
    async with STATE_LOCK:
        Altruix.PURGEME_STATE[unique_id] = {
            "count": 10,
            "delay": 0,
            "types": ["all"],
            "mode": "latest",
            "status": "config",
            "event": asyncio.Event(),
            "stop_event": asyncio.Event(),
            "pause_event": asyncio.Event(),
            "client": client,
            "chat_id": chat_id,
            "processed": 0,
            "start_time": 0,
            "dashboard_msg_id": None, 
            "dashboard_chat_id": None
        }
        # Pause event is set to True initially (not paused)
        Altruix.PURGEME_STATE[unique_id]["pause_event"].set()

    # Trigger Assistant UI
    try:
        bot_username = Altruix.bot_manager.get_bot_username(client.me.id)
        # Inline query trigger to get the menu
        try:
            results = await client.get_inline_bot_results(bot_username, f"purgeme_menu_{unique_id}")
            
            if results.results:
                # Send the inline result to the chat (Self-destructing menu prompt)
                sent_invite = await client.send_inline_bot_result(
                    message.chat.id,
                    results.query_id,
                    results.results[0].id,
                    reply_to_message_id=message.reply_to_message.id if message.reply_to_message else message.id
                )
                # Delete the command message to keep chat clean
                await message.delete()
            else:
                 raise Exception("Empty inline results")

        except Exception as inner_e:
            Altruix.log(f"Purgeme Inline Fail: {inner_e} - Trying Fallback")
            # FALLBACK
            start_param = f"purgeme_{unique_id}"
            
            kb = enums.ParseMode.HTML
            from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            url = f"https://t.me/{bot_username}?start={start_param}"
            
            fallback_msg = (
                "⚠️ <b>Inline Mode Restricted</b>\n"
                "I cannot open the menu here directly.\n"
                f"👉 <a href='{url}'>Click Here to Configure via PM</a>"
            )
            
            await message.reply(
                fallback_msg,
                parse_mode=kb,
                disable_web_page_preview=True
            )

    except Exception as e:
        await message.edit(f"❌ Error initiating Purgeme: {e}")
        return

    # Wait for 'Start' signal from UI
    state = Altruix.PURGEME_STATE[unique_id]
    try:
        # Wait up to 5 minutes for configuration
        await asyncio.wait_for(state["event"].wait(), timeout=300)
    except asyncio.TimeoutError:
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
    target_types = state["types"]
    mode = state.get("mode", "latest")
    
    # ---------------------------------------------------------
    # DASHBOARD CREATION - MOVED TO TARGET CHAT
    # ---------------------------------------------------------
    
    dashboard_chat = chat_id # ALWAYS TARGET CHAT
    
    try:
        dash_text = get_purgeme_status_text(state)
        dash_kb = get_purgeme_control_kb(unique_id, "running")
        
        # Send via BOT to allow buttons
        bot = Altruix.bot_manager.get_bot(client.me.id)
        dash_msg = await bot.send_message(
            dashboard_chat,
            dash_text,
            reply_markup=dash_kb,
            disable_web_page_preview=True
        )
        state["dashboard_msg_id"] = dash_msg.id
        state["dashboard_chat_id"] = dashboard_chat
    except Exception as e:
        Altruix.log(f"Purgeme Dashboard Error: {e}")
        # If bot fails to send to chat_id (e.g. privacy), try log_chat?
        if Altruix.log_chat:
            dashboard_chat = Altruix.log_chat
            try:
                bot = Altruix.bot_manager.get_bot(client.me.id)
                dash_msg = await bot.send_message(
                    dashboard_chat,
                    dash_text,
                    reply_markup=dash_kb,
                    disable_web_page_preview=True
                )
                state["dashboard_msg_id"] = dash_msg.id
                state["dashboard_chat_id"] = dashboard_chat
            except: pass

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
            # DELETION PHASE
            # ---------------------------------------------------------
            chunk_size = 1 if delay > 0 else 100
            
            for i in range(0, len(collected_ids), chunk_size):
                if state["stop_event"].is_set():
                    Altruix.log("Purgeme Optimized: Stop event triggered")
                    break
                
                # Check Pause
                if not state["pause_event"].is_set():
                    state["status"] = "paused"
                    asyncio.create_task(update_dashboard(state))
                    await state["pause_event"].wait()
                    state["status"] = "running"
                    asyncio.create_task(update_dashboard(state))

                chunk = collected_ids[i:i+chunk_size]
                
                # Retry logic for each chunk
                delete_success = False
                retry_count = 0
                max_retries = 3
                
                while not delete_success and retry_count < max_retries:
                    try:
                        await client.delete_messages(chat_id, chunk)
                        deleted_count += len(chunk)
                        state["processed"] = deleted_count
                        delete_success = True
                        
                        Altruix.log(f"Purgeme Optimized: Deleted chunk of {len(chunk)}, total: {deleted_count}/{len(collected_ids)}")
                        
                        if deleted_count % 10 == 0 or delay > 0:
                            asyncio.create_task(update_dashboard(state))
                            
                        if delay > 0: 
                            await asyncio.sleep(delay)
                            
                    except FloodWait as fw:
                        retry_count += 1
                        wait_time = fw.value
                        Altruix.log(f"Purgeme Optimized: FloodWait {wait_time}s (attempt {retry_count}/{max_retries})")
                        await asyncio.sleep(wait_time)
                    except Exception as e:
                        retry_count += 1
                        Altruix.log(f"Purgeme Optimized: Delete error (attempt {retry_count}/{max_retries}): {e}")
                        if retry_count >= max_retries:
                            Altruix.log(f"Purgeme Optimized: Max retries reached for chunk, skipping")
                            delete_success = True
                        else:
                            await asyncio.sleep(2)


    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception as e:
        Altruix.log(f"Purgeme Error: {e}")

    # Finish
    state["status"] = "finished"
    await update_dashboard(state)
    
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
            
            # Determine final status
            if state.get("stop_event") and state["stop_event"].is_set():
                final_status = "⏹ Stopped"
                status_emoji = "⚠️"
            elif deleted_count == 0:
                final_status = "❌ No messages deleted"
                status_emoji = "⚠️"
            else:
                final_status = "✅ Success"
                status_emoji = "✅"
            
            log_msg = (
                f"{status_emoji} <b>Purgeme Completed</b>\n\n"
                f"• <b>Status:</b> {final_status}\n"
                f"• <b>Deleted:</b> {deleted_count} messages\n"
                f"• <b>Mode:</b> {mode.capitalize()}\n"
                f"• <b>Duration:</b> {duration_str}\n"
                f"• <b>Chat:</b> {chat_link} (<code>{chat_id}</code>)\n"
                f"• <b>Type:</b> {chat_type}\n"
                f"• <b>User:</b> {user_mention} (<code>{user_id}</code>)"
            )

            
            bot = Altruix.bot_manager.get_bot(client.me.id)
            await bot.send_message(
                Altruix.log_chat,
                log_msg,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )
            
            # Send completion notification to target chat (auto-delete after 5s)
            try:
                completion_msg = (
                    f"{status_emoji} <b>Purgeme Selesai!</b>\n"
                    f"Dihapus: <b>{deleted_count}</b> pesan | "
                    f"Mode: <b>{mode.capitalize()}</b> | "
                    f"Durasi: <b>{duration_str}</b>"
                )
                
                target_notif = await client.send_message(
                    chat_id,
                    completion_msg,
                    parse_mode=enums.ParseMode.HTML,
                    disable_web_page_preview=True
                )
                
                # Auto-delete after 6 seconds
                await asyncio.sleep(6)
                await target_notif.delete()
            except Exception as notif_err:
                Altruix.log(f"Failed to send target chat notification: {notif_err}")
    except Exception as log_err:
        Altruix.log(f"Failed to send Purgeme completion log: {log_err}")
    
    # Wait a bit then clean up
    await asyncio.sleep(5)
    if unique_id in Altruix.PURGEME_STATE:
        del Altruix.PURGEME_STATE[unique_id]

async def update_dashboard(state):
    """Updates the dashboard message with current state"""
    try:
        if state["dashboard_chat_id"] and state["dashboard_msg_id"]:
            text = get_purgeme_status_text(state)
            # Simpler: Store unique_id in state
            uid = f"{state['chat_id']}_{state['client'].me.id}"
            kb = get_purgeme_control_kb(uid, state["status"])

            try:
                # If chat is different from bot's chat (userbot logging to PM?), 
                # we must ensure bot can edit it.
                bot = Altruix.bot_manager.get_bot(state["client"].me.id)
                await bot.edit_message_text(
                    chat_id=state["dashboard_chat_id"],
                    message_id=state["dashboard_msg_id"],
                    text=text,
                    reply_markup=kb
                )
            except FloodWait as f:
                Altruix.log(f"Purgeme UI FloodWait: {f.value}s - Skipping frame")
            except MessageNotModified:
                pass
            except Exception as e:
                Altruix.log(f"Failed to update Purgeme Dashboard: {e}")
    except Exception as e:
        Altruix.log(f"Purgeme Dashboard Critical: {e}")

# ---------------------------------------------------------
# MANUAL COMMANDS
# ---------------------------------------------------------

@Altruix.register_on_cmd(["purgemepause", "ppaause"], cmd_help={"help": "Pause running purge"})
async def purgeme_pause_cmd(client: Client, message: Message):
    uid = f"{message.chat.id}_{client.me.id}"
    state = Altruix.PURGEME_STATE.get(uid)
    if state and state["status"] == "running":
        state["pause_event"].clear()
        state["status"] = "paused"
        await update_dashboard(state)
        await message.edit("⏸ <b>Purgeme Paused</b>")
    else:
        await message.edit("❌ No running purge found here.")

@Altruix.register_on_cmd(["purgemeresume", "presume"], cmd_help={"help": "Resume paused purge"})
async def purgeme_resume_cmd(client: Client, message: Message):
    uid = f"{message.chat.id}_{client.me.id}"
    state = Altruix.PURGEME_STATE.get(uid)
    if state and state["status"] == "paused":
        state["pause_event"].set()
        state["status"] = "running"
        await update_dashboard(state)
        await message.edit("▶️ <b>Purgeme Resumed</b>")
    else:
        await message.edit("❌ No paused purge found here.")

@Altruix.register_on_cmd(["purgemestop", "pstop"], cmd_help={"help": "Stop running purge"})
async def purgeme_stop_cmd(client: Client, message: Message):
    uid = f"{message.chat.id}_{client.me.id}"
    state = Altruix.PURGEME_STATE.get(uid)
    if state:
        state["stop_event"].set()
        await message.edit("⏹ <b>Purgeme Stopping...</b>")
    else:
        await message.edit("❌ No active purge found here.")

@Altruix.register_on_cmd(["purgemestatus", "pstatus"], cmd_help={"help": "Check purge status"})
async def purgeme_status_cmd(client: Client, message: Message):
    uid = f"{message.chat.id}_{client.me.id}"
    state = Altruix.PURGEME_STATE.get(uid)
    if state:
        text = get_purgeme_status_text(state)
        await message.edit(text)
    else:
        await message.edit("❌ No active purge session.")
