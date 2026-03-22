# session_handlers.py - All Missing Session Info Button Handlers
# This file contains all missing handlers for session info buttons

from Main import Altruix
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from Main.core.decorators import log_errors, iuser_check
from Main.core.client import Altruix
from pyrogram.enums import ParseMode, ChatType
from Main.internals.settings_handlers.utils import edit_cb, send_log_notification
from .states import user_profile_edit_state
from Main.utils.file_helpers import get_user_button_style
import html
import os
import asyncio

# ====================== INFO & SECURITY HANDLERS ======================

# Note: gen_conf_export_session and gen_conf_export_phone are handled in security_handlers.py

@Altruix.bot.on_callback_query(filters.regex(r"^test_ping_all_confirm(?:ation)?$"))
@iuser_check
@log_errors
async def test_ping_all_handler(c: Client, cb: CallbackQuery):
    """Test ping for all sessions"""
    await cb.answer("🏓 Testing ping for all sessions...")
    target_session_id = Altruix.clients[0].me.id if Altruix.clients and hasattr(Altruix.clients[0], 'me') and Altruix.clients[0].me else cb.from_user.id
    user_style = get_user_button_style(target_session_id)
    
    total = len(Altruix.clients)
    if total == 0:
        return await edit_cb(cb, "❌ No active sessions to test.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", "bulk_controls_menu", style=user_style)]]))

    await edit_cb(cb, f"⏳ Testing ping for {total} sessions...")
    
    results = []
    for i, client in enumerate(Altruix.clients):
        try:
            import time
            start = time.time()
            # Use small dummy request to test latency
            await client.get_me()
            ping = round((time.time() - start) * 1000, 2)
            results.append(f"• Session {i+1}: ✅ {ping}ms")
        except Exception:
            results.append(f"• Session {i+1}: ❌ Offline")
            
    txt = "<b>🏓 Global Ping Test Results</b>\n\n" + "\n".join(results)
    await edit_cb(cb, txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", "bulk_controls_menu", style=user_style)]]))

# ====================== GROUP & MESSAGE HANDLERS ======================

@Altruix.bot.on_callback_query(filters.regex(r"^join_chat_input_(\d+)_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def join_chat_handler(c: Client, cb: CallbackQuery):
    """Join group/channel"""
    await cb.answer()
    index = int(cb.matches[0].group(1))
    callback_page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 2
    
    user_profile_edit_state[cb.from_user.id] = {
        'action': 'join_chat',
        'index': index,
        'callback_page': callback_page,
        'button_page': button_page
    }
    
    session_id = Altruix.clients[index].me.id if index < len(Altruix.clients) and hasattr(Altruix.clients[index], 'me') and Altruix.clients[index].me else cb.from_user.id
    user_style = get_user_button_style(session_id)
    await edit_cb(
        cb,
        f"👥 <b>Join Group/Channel</b>\n\nSend the invite link or username:\n\n<i>Example: https://t.me/channel or @username</i>\n\n❌ Type /cancel to cancel",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", f"session_info_{index}_{callback_page}_{button_page}", style=user_style)]])
    )

@Altruix.bot.on_callback_query(filters.regex(r"^leave_chat_input_(\d+)_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def leave_chat_handler(c: Client, cb: CallbackQuery):
    """Leave group/channel"""
    await cb.answer()
    index = int(cb.matches[0].group(1))
    callback_page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 2
    
    user_profile_edit_state[cb.from_user.id] = {
        'action': 'leave_chat',
        'index': index,
        'callback_page': callback_page,
        'button_page': button_page
    }
    
    session_id = Altruix.clients[index].me.id if index < len(Altruix.clients) and hasattr(Altruix.clients[index], 'me') and Altruix.clients[index].me else cb.from_user.id
    user_style = get_user_button_style(session_id)
    await edit_cb(
        cb,
        f"🚪 <b>Leave Group/Channel</b>\n\nSend the chat ID or username:\n\n<i>Example: -1001234567890 or @username</i>\n\n❌ Type /cancel to cancel",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", f"session_info_{index}_{callback_page}_{button_page}", style=user_style)]])
    )

@Altruix.bot.on_callback_query(filters.regex(r"^send_message_input_(\d+)_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def send_message_handler(c: Client, cb: CallbackQuery):
    """Send message to chat"""
    await cb.answer()
    index = int(cb.matches[0].group(1))
    callback_page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 2
    
    user_profile_edit_state[cb.from_user.id] = {
        'action': 'send_message_step1',
        'index': index,
        'callback_page': callback_page,
        'button_page': button_page
    }
    
    session_id = Altruix.clients[index].me.id if index < len(Altruix.clients) and hasattr(Altruix.clients[index], 'me') and Altruix.clients[index].me else cb.from_user.id
    user_style = get_user_button_style(session_id)
    await edit_cb(
        cb,
        f"💬 <b>Send Message</b>\n\nStep 1: Send the chat ID or username:\n\n<i>Example: -1001234567890 or @username</i>\n\n❌ Type /cancel to cancel",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", f"session_info_{index}_{callback_page}_{button_page}", style=user_style)]])
    )

# ====================== MEDIA & PROFILE HANDLERS ======================

@Altruix.bot.on_callback_query(filters.regex(r"^gen_conf_dl_uphoto_start_(\d+)_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def download_user_photo_handler(c: Client, cb: CallbackQuery):
    """Download user profile photos"""
    await cb.answer()
    index = int(cb.matches[0].group(1))
    callback_page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 2
    
    user_profile_edit_state[cb.from_user.id] = {
        'action': 'download_user_photo',
        'index': index,
        'callback_page': callback_page,
        'button_page': button_page
    }
    
    session_id = Altruix.clients[index].me.id if index < len(Altruix.clients) and hasattr(Altruix.clients[index], 'me') and Altruix.clients[index].me else cb.from_user.id
    user_style = get_user_button_style(session_id)
    await edit_cb(
        cb,
        f"📸 <b>Download User Photos</b>\n\nSend username or user ID:\n\n<i>Example: @username or 123456789</i>\n\n❌ Type /cancel to cancel",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", f"session_info_{index}_{callback_page}_{button_page}", style=user_style)]])
    )

@Altruix.bot.on_callback_query(filters.regex(r"^gen_conf_send_profile_photo_(\d+)_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def send_my_photo_handler(c: Client, cb: CallbackQuery):
    """Send own profile photo to user"""
    await cb.answer("📸 Fetching profile photo...")
    index = int(cb.matches[0].group(1))
    callback_page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    if index >= len(Altruix.clients): return
    client = Altruix.clients[index]
    
    try:
        me = await client.get_me()
        photos = [p async for p in client.get_chat_photos(me.id, limit=1)]
        if photos:
            await c.send_photo(cb.from_user.id, photos[0].file_id, caption="📸 Your Current Profile Photo")
            await cb.answer("✅ Sent to your PM!", show_alert=True)
        else:
            await cb.answer("❌ No profile photo found.", show_alert=True)
    except Exception as e:
        await cb.answer(f"❌ Error: {str(e)}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^gen_conf_delete_all_profile_photos_(\d+)_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def delete_all_photos_handler(c: Client, cb: CallbackQuery):
    """Delete all profile photos confirmation"""
    index = int(cb.matches[0].group(1))
    callback_page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    await cb.answer()
    
    session_id = Altruix.clients[index].me.id if index < len(Altruix.clients) and hasattr(Altruix.clients[index], 'me') and Altruix.clients[index].me else cb.from_user.id
    user_style = get_user_button_style(session_id)
    text = (
        "<b>🗑️ Delete All Profile Photos</b>\n\n"
        "Are you sure you want to delete ALL of your profile photos?\n"
        "This action cannot be undone."
    )
    buttons = [
        [InlineKeyboardButton("✅ Confirm Delete", f"delete_photos_confirm_{index}_{callback_page}_{button_page}", style=user_style)],
        [InlineKeyboardButton("🔙 Back", f"session_info_{index}_{callback_page}_{button_page}", style=user_style)]
    ]
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons))

@Altruix.bot.on_callback_query(filters.regex(r"^delete_photos_confirm_(\d+)_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def delete_photos_confirmed_handler(c: Client, cb: CallbackQuery):
    """Execute deletion of all profile photos"""
    index, page, b_page = int(cb.matches[0].group(1)), int(cb.matches[0].group(2)), int(cb.matches[0].group(3))
    await cb.answer("🗑️ Deleting all photos...")
    
    if index >= len(Altruix.clients): return
    client = Altruix.clients[index]
    
    try:
        me = await client.get_me()
        photos = [p async for p in client.get_chat_photos(me.id)]
        deleted = 0
        for p in photos:
            try:
                await client.delete_profile_photos(p.file_id)
                deleted += 1
            except: pass
            
        await cb.answer(f"✅ Deleted {deleted} photo(s)!", show_alert=True)
        from .settings_handlers.session_info import sessions_info_cb_handler
        # Re-display session info dashboard
        await sessions_info_cb_handler(c, cb, index=index, callback_page=page, button_page=b_page)
    except Exception as e:
        await cb.answer(f"❌ Error: {str(e)}", show_alert=True)

# ====================== RECENT MESSAGES & GLOBAL STATS ======================

@Altruix.bot.on_callback_query(filters.regex(r"^recent_msgs_menu_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def recent_messages_menu_handler(c: Client, cb: CallbackQuery):
    """Menu selection for Recent Messages filter"""
    index, page = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    await cb.answer()
    
    Altruix.log(f"🛠 [Recent Messages] Handler started for session index {index}", level=20, client=c)
    
    if index < len(Altruix.clients):
        client = Altruix.clients[index]
        if not client.is_connected:
            try: 
                Altruix.log(f"🔌 [Recent Messages] Session {index} offline. Reconnecting...", level=20, client=c)
                await asyncio.wait_for(client.start(), timeout=10)
            except asyncio.TimeoutError:
                Altruix.log(f"⏰ [Recent Messages] Connection timeout for session {index}", level=30, client=c)
                return await cb.answer("❌ Connection timeout. Session is too slow to start.", show_alert=True)
            except Exception as e: 
                Altruix.log(f"❌ [Recent Messages] Connection failed: {e}", level=40, client=c)
                pass
                
        if client.me and client.me.is_bot:
            Altruix.log(f"🚫 [Recent Messages] Blocked bot session usage", level=20, client=c)
            return await cb.answer("❌ Feature not available for bot sessions.", show_alert=True)
    
    session_id = Altruix.clients[index].me.id if index < len(Altruix.clients) and hasattr(Altruix.clients[index], 'me') and Altruix.clients[index].me else cb.from_user.id
    user_style = get_user_button_style(session_id)
    
    # Fetch current limit
    limit = await Altruix.config.get_env(f"RECENT_MSGS_LIMIT_{index}") or 200
    
    text = (
        f"<b>📨 Recent Messages (Session {index+1})</b>\n\n"
        f"Scan Limit: <code>{limit}</code> messages\n\n"
        "Pilih kategori pesan yang ingin Anda lihat:"
    )
    buttons = [
        [
            InlineKeyboardButton("👤 All Users", f"recent_msgs_list_{index}_{page}_user", style=user_style),
            InlineKeyboardButton("🤖 All Bots", f"recent_msgs_list_{index}_{page}_bot", style=user_style)
        ],
        [InlineKeyboardButton("🌐 All Messages", f"recent_msgs_list_{index}_{page}_all", style=user_style)],
        [
            InlineKeyboardButton("⚙️ Set Limit", f"set_scan_limit_{index}_{page}_recent", style=user_style),
            InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}_2", style=user_style)
        ]
    ]
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^set_scan_limit_(\d+)_(\d+)_(recent|mnt)$"))
@iuser_check
@log_errors
async def set_scan_limit_handler(c: Client, cb: CallbackQuery):
    """Ask user for the scan limit value"""
    index, page, s_type = int(cb.matches[0].group(1)), int(cb.matches[0].group(2)), cb.matches[0].group(3)
    await cb.answer()
    
    session_id = Altruix.clients[index].me.id if index < len(Altruix.clients) and hasattr(Altruix.clients[index], 'me') and Altruix.clients[index].me else cb.from_user.id
    user_style = get_user_button_style(session_id)
    
    # Store state
    from .states import user_scan_limit_state
    user_scan_limit_state[cb.from_user.id] = {
        'index': index,
        'page': page,
        'type': s_type
    }
    
    target_name = "Recent Messages" if s_type == "recent" else "View Mentions"
    
    await edit_cb(
        cb,
        f"⚙️ <b>Set Scan Limit for {target_name}</b>\n\n"
        "Masukkan jumlah maksimal pesan/dialog yang ingin discan (1-1000):\n\n"
        "<i>Semakin besar limit, semakin lama proses fetching berlangsung.</i>\n\n"
        "❌ Type /cancel to cancel",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", f"session_info_{index}_{page}_2", style=user_style)]])
    )

@Altruix.bot.on_callback_query(filters.regex(r"^recent_msgs_list_(\d+)_(\d+)_(user|bot|all)$"))
@iuser_check
@log_errors
async def recent_messages_list_handler(c: Client, cb: CallbackQuery):
    """Display the list of recent messages based on filter"""
    index, page, f_type = int(cb.matches[0].group(1)), int(cb.matches[0].group(2)), cb.matches[0].group(3)
    await cb.answer("📨 Fetching recent messages...", show_alert=False)
    
    if index >= len(Altruix.clients): 
        Altruix.log(f"❌ [Recent Messages List] Index {index} out of bounds!", level=30, client=c)
        return
    client = Altruix.clients[index]

    Altruix.log(f"🛠 [Recent Messages List] Handler started for session {index} (Filter: {f_type})", level=20, client=client)
    
    Altruix.log(f"DEBUG: Checking clients list (Len: {len(Altruix.clients)})", level=20, client=client)
    
    Altruix.log("DEBUG: Accessing client.me...", level=20, client=client)
    me = getattr(client, "me", None)
    Altruix.log(f"DEBUG: client.me is {'Set' if me else 'None'}", level=20, client=client)
    
    # 🛑 BOT CHECK: Recent messages scanning is a user-only method
    if me and me.is_bot:
        Altruix.log(f"🚫 [Recent Messages List] Blocked bot session {index}", level=20, client=client)
        await cb.answer("❌ This feature is only available for Userbot sessions.", show_alert=True)
        return
    
    Altruix.log("DEBUG: Checking connection status...", level=20, client=client)
    is_connected = getattr(client, "is_connected", False)
    Altruix.log(f"DEBUG: is_connected={is_connected}", level=20, client=client)
    
    # ✅ ACTIVE HEALTH CHECK: Force a ping even if connected=True
    try:
        Altruix.log("📡 [Recent Messages List] Performing Health Ping...", level=20, client=client)
        await asyncio.wait_for(client.get_me(), timeout=3)
        Altruix.log("✅ [Recent Messages List] Health Ping OK.", level=20, client=client)
    except (asyncio.TimeoutError, Exception) as e:
        Altruix.log(f"⚠️ [Recent Messages List] Health Ping FAILED (is_connected was {is_connected}): {e}. Forced Restarting...", level=30, client=client)
        try:
            try: await asyncio.wait_for(client.stop(), timeout=3)
            except: pass
            Altruix.log("🔌 [Recent Messages List] Restarting session...", level=20, client=client)
            await asyncio.wait_for(client.start(), timeout=10)
            Altruix.log("♻️ [Recent Messages List] Forced Restart Successful.", level=20, client=client)
        except Exception as re:
            Altruix.log(f"❌ [Recent Messages List] Forced Restart FAILED: {re}", level=40, client=client)
            return await cb.answer("❌ Session unreachable. Try refreshing session info.", show_alert=True)

    try:
        dialogs = []
        # Get custom limit
        limit_val = await Altruix.config.get_env(f"RECENT_MSGS_LIMIT_{index}") or 200
        limit_val = int(limit_val)
        
        await edit_cb(cb, f"🔍 <b>Scanning up to {limit_val} dialogs...</b>\n<i>Please wait a moment...</i>", parse_mode=ParseMode.HTML)
        
        # 🟢 Progress update helper
        async def update_progress(current, total):
            pct = int((current / total) * 100) if total > 0 else 0
            msg = f"🔍 <b>Scanning dialogs... ({current}/{total})</b>\n<i>Progress: {pct}%</i>"
            await edit_cb(cb, msg, parse_mode=ParseMode.HTML)

        # 1. Phase 1: Quick Scan (Top 20)
        await edit_cb(cb, "🔍 <b>Initializing Quick Scan...</b>", parse_mode=ParseMode.HTML)
        Altruix.log(f"📂 [Recent Messages List] Fetching first batch (Limit: 20)...", level=20, client=client)
        scanned = 0
        
        try:
            async for dialog in client.get_dialogs(limit=20):
                scanned += 1
                await update_progress(scanned, 20)
                
                try:
                    # Apply filter
                    if f_type == "user" and dialog.chat.type != ChatType.PRIVATE: continue
                    if f_type == "bot" and dialog.chat.type != ChatType.BOT: continue
                    dialogs.append(dialog)
                except Exception: continue
                if len(dialogs) >= 15: break
            
            # 2. Phase 2: Deep Scan (if needed and limit allows)
            if len(dialogs) < 15 and limit_val > 20:
                await edit_cb(cb, f"🔍 <b>Performing Deep Scan...</b>\n<i>Found: {len(dialogs)} messages so far</i>", parse_mode=ParseMode.HTML)
                async for dialog in client.get_dialogs(limit=limit_val):
                    scanned += 1
                    if scanned <= 20: continue # Already checked
                    
                    if scanned % 10 == 0:
                        await update_progress(scanned, limit_val)
                    
                    try:
                        if f_type == "user" and dialog.chat.type != ChatType.PRIVATE: continue
                        if f_type == "bot" and dialog.chat.type != ChatType.BOT: continue
                        if dialog.chat.id not in [d.chat.id for d in dialogs]:
                            dialogs.append(dialog)
                    except Exception: continue
                    
                    if len(dialogs) >= 15: break
                    if scanned >= limit_val: break
                    await asyncio.sleep(0.01)

        except Exception as de:
            Altruix.log(f"⚠️ [Recent Messages List] Dialog scan error: {de}", level=30, client=client)
            if not dialogs: raise de

        Altruix.log(f"🏁 [Recent Messages List] Finished scanning. Found {len(dialogs)} dialogs out of {scanned} scanned.", level=20, client=client)

        if not dialogs:
            Altruix.log(f"🔕 [Recent Messages List] No dialogs matched filter {f_type}.", level=20, client=client)
            await cb.answer("❌ No messages found for this filter.", show_alert=True)
            # Restore menu if possible
            from .session_info import get_session_info_data
            text, reply_markup = await get_session_info_data(index, page, 2)
            # Add status info to the top
            status_text = "👤 Users" if f_type == "user" else "🤖 Bots" if f_type == "bot" else "🌐 All"
            text = f"<b>🔕 No recent messages found ({status_text})</b>\n\n" + text
            return await edit_cb(cb, text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

        type_label = "👤 All Users" if f_type == "user" else "🤖 All Bots" if f_type == "bot" else "🌐 All Recent"
        txt = f"<b>📨 Recent Messages ({type_label})</b>\n\n"
        
        for i, d in enumerate(dialogs, 1):
            try:
                # 🛡️ DEFENSIVE NAME RETRIEVAL
                name = (d.chat.title or d.chat.first_name or "Unknown")
                if d.chat.type == ChatType.BOT:
                    name = "🤖 " + name
                
                # 🛡️ DEFENSIVE TEXT RETRIEVAL (Fixes utf-16 decoding error)
                try:
                    last_msg = (d.top_message.text or d.top_message.caption or "[Media]") if d.top_message else "[No Messages]"
                except UnicodeDecodeError:
                    last_msg = "[⚠️ Decoding Error]"
                except Exception:
                    last_msg = "[Message Error]"

                msg_date = d.top_message.date.strftime("%H:%M") if d.top_message and hasattr(d.top_message, 'date') else "--:--"
                
                # Clean text safely
                if len(last_msg) > 40: last_msg = last_msg[:37] + "..."
                last_msg = html.escape(last_msg.replace('\n', ' '))
                
                txt += f"{i}. <b>{html.escape(name)}</b> [<code>{msg_date}</code>]\n   └ <code>{last_msg}</code>\n"
            except Exception as inner_e:
                Altruix.log(f"⚠️ [Recent Messages List] Skipping corrupted dialog entry {i}: {inner_e}", level=10)
                continue
            
        session_id = client.me.id if hasattr(client, 'me') and client.me else cb.from_user.id
        user_style = get_user_button_style(session_id)
        await edit_cb(cb, txt, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", f"recent_msgs_list_{index}_{page}_{f_type}", style=user_style)],
            [InlineKeyboardButton("🔙 Back", f"recent_msgs_menu_{index}_{page}", style=user_style)],
            [InlineKeyboardButton("🔙 Dashboard", f"session_info_{index}_{page}_2", style=user_style)]
        ]))
    except Exception as e:
        Altruix.log(f"❌ [Recent Messages List] Fatal Error: {e}", level=40, client=client)
        await cb.answer(f"❌ Error: {str(e)}", show_alert=True)
        from .session_info import get_session_info_data
        text, reply_markup = await get_session_info_data(index, page, 2)
        text = f"<b>❌ Error scanning messages:</b> <code>{html.escape(str(e))}</code>\n\n" + text
        return await edit_cb(cb, text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

# ====================== INPUT PROCESSING ======================

async def process_scan_limit_input(c: Client, m: Message, state: dict):
    """Process scan limit input from user"""
    user_id = m.from_user.id
    index, page, s_type = state['index'], state['page'], state['type']
    text = m.text.strip()
    
    if not text.isdigit():
        return await m.reply("❌ Limit harus berupa angka (1-1000).")
    
    val = int(text)
    if not (1 <= val <= 1000):
        return await m.reply("❌ Limit harus di antara 1 dan 1000.")
    
    # Save to DB
    key = f"RECENT_MSGS_LIMIT_{index}" if s_type == "recent" else f"MENTIONS_LIMIT_{index}"
    try:
        await Altruix.config.sync_env_to_db(key, val, upsert=True)
        # Update cache if exists
        setattr(Altruix.config, key, val)
    except Exception as e:
        Altruix.log(f"Error saving scan limit: {e}", level=40)
    
    from .states import user_scan_limit_state
    if user_id in user_scan_limit_state:
        del user_scan_limit_state[user_id]
        
    session_id = Altruix.clients[index].me.id if index < len(Altruix.clients) and hasattr(Altruix.clients[index], 'me') and Altruix.clients[index].me else m.from_user.id
    user_style = get_user_button_style(session_id)
    
    target_name = "Recent Messages" if s_type == "recent" else "View Mentions"
    back_cb = f"recent_msgs_menu_{index}_{page}" if s_type == "recent" else f"view_mnt_menu_{index}_{page}"
    
    await m.reply(
        f"✅ <b>Scan Limit Updated!</b>\n\n"
        f"• Feature: <code>{target_name}</code>\n"
        f"• New Limit: <code>{val}</code>\n\n"
        f"Scan Limit berhasil diperbarui.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", back_cb, style=user_style)]])
    )

@Altruix.bot.on_callback_query(filters.regex(r"^gen_conf_global_stats_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def global_stats_handler(c: Client, cb: CallbackQuery):
    """Aggregate statistics across all active sessions"""
    index, page = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    await cb.answer("🌐 Calculating global stats...", show_alert=False)
    
    total_sessions = len(Altruix.clients)
    active_sessions = sum(1 for client in Altruix.clients if getattr(client, 'is_connected', False))
    
    import platform
    import time
    uptime = time.time() - Altruix.start_time
    days, hours, minutes = int(uptime // 86400), int((uptime % 86400) // 3600), int((uptime % 3600) // 60)
    
    txt = (
        f"<b>🌐 Global Statistics</b>\n\n"
        f"• <b>Total Sessions:</b> <code>{total_sessions}</code>\n"
        f"• <b>Active Sessions:</b> <code>{active_sessions}</code>\n"
        f"• <b>System Architecture:</b> <code>{platform.machine()}</code>\n"
        f"• <b>OS:</b> <code>{platform.system()} {platform.release()}</code>\n"
        f"• <b>Uptime:</b> <code>{days}d {hours}h {minutes}m</code>\n"
        f"• <b>Core Modules:</b> <code>{len(Altruix.plugin_categories)}</code>\n"
    )
    
    session_id = Altruix.clients[index].me.id if index < len(Altruix.clients) and hasattr(Altruix.clients[index], 'me') and Altruix.clients[index].me else cb.from_user.id
    user_style = get_user_button_style(session_id)
    await edit_cb(cb, txt, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Dashboard", f"session_info_{index}_{page}_4", style=user_style)],
        [InlineKeyboardButton("🔙 Main Stats", "sessions_stats", style=user_style)]
    ]))

# ====================== PLACEHOLDER HANDLERS ======================

@Altruix.bot.on_callback_query(filters.regex(r"^(gen_conf_view_all_sessions_|laucreate_menu_|eval_session_|exec_session_)"))
@iuser_check
@log_errors
async def improved_placeholder_handler(c: Client, cb: CallbackQuery):
    """Smart redirect for placeholders and legacy patterns."""
    data = cb.data
    
    if "view_all_sessions" in data:
        # Redirect to main sessions list
        from .settings_handlers.sessions_list import sessions_menu_cb_handler
        cb.data = "sessions_list_1"
        return await sessions_menu_cb_handler(c, cb)
        
    if "laucreate_menu" in data:
        # Redirect to creategroup menu
        from .settings_handlers.creategroup_handlers import creategroup_menu_handler
        # Extract index and page if present 
        # Format usually: laucreate_menu_{index}_{page}
        # Result should be: creategroup_menu_{index}_{page}
        new_data = data.replace("laucreate_menu_", "creategroup_menu_")
        cb.data = new_data
        
        # We need to mock matches because the handler uses cb.matches[0]
        # Regex in creategroup_handlers: r"^creategroup_menu_(\d+)(?:_(\d+))?$"
        import re
        cb.matches = [re.search(r"^creategroup_menu_(\d+)(?:_(\d+))?$", new_data)]
        return await creategroup_menu_handler(c, cb)
    
    # Eval/Exec redirection reminder
    if "eval_session" in data or "exec_session" in data:
        return await cb.answer("⚠️ Legacy Eval/Exec is disabled. Please use Page 4 buttons.", show_alert=True)

    await cb.answer("🚧 This feature has been moved or is under development.", show_alert=True)
