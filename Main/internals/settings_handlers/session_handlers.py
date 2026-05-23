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
import re
import traceback
from pyrogram import enums


# ====================== BYPASS HELPERS ======================

async def handle_bypass_forward(client, msg, target_chat, index, chat_id, chat_name):
    """Helper to handle bypass (download/re-upload) for protected or self-destructing content."""
    Altruix.log(f"📦 [Bypass] Starting bypass for message {msg.id} in {chat_id} ({chat_name})", level=20)
    if msg.media:
        try:
            file_path = await client.download_media(msg)
            if file_path:
                m_type = msg.media.value.upper() if hasattr(msg.media, 'value') else str(msg.media).upper()
                Altruix.log(f"✅ [Bypass] Media downloaded: {file_path} (Type: {m_type})", level=20)
                caption = (
                    f"📤 <b>Bypassed Content</b>\n"
                    f"• From: <code>{html.escape(chat_name)}</code>\n"
                    f"• Type: <code>{m_type}</code>\n"
                    f"• Session: <code>{index + 1}</code>"
                )
                
                # If there's original text, append it
                original_text = msg.text or msg.caption
                if original_text:
                    caption += f"\n\n📝 <b>Original Text:</b>\n{html.escape(original_text[:500])}"
                
                # Handle different media types for better UX
                try:
                    if msg.photo:
                        await client.send_photo(target_chat, file_path, caption=caption)
                    elif msg.video:
                        await client.send_video(target_chat, file_path, caption=caption)
                    elif msg.voice:
                        await client.send_voice(target_chat, file_path, caption=caption)
                    else:
                        await client.send_document(target_chat, file_path, caption=caption)
                    Altruix.log(f"✅ [Bypass] Media sent to {target_chat}", level=20)
                except Exception as e:
                    Altruix.log(f"⚠️ [Bypass] Error sending media: {e}", level=30)
                    # Fallback to document
                    await client.send_document(target_chat, file_path, caption=caption)
                
                if os.path.exists(file_path):
                    os.remove(file_path)
            else:
                Altruix.log(f"❌ [Bypass] Download failed for message {msg.id}", level=40)
                raise Exception("Failed to download protected media.")
        except Exception as e:
            Altruix.log(f"❌ [Bypass] Fatal error during media bypass: {e}", level=40)
            raise e
    else:
        # Protected text message
        text = msg.text or msg.caption or "[Empty Protected Message]"
        Altruix.log(f"📝 [Bypass] Handling protected text message: {text[:30]}...", level=20)
        caption = (
            f"📤 <b>Bypassed Text (Protected)</b>\n"
            f"• From: <code>{html.escape(chat_name)}</code>\n"
            f"• Session: <code>{index + 1}</code>\n\n"
            f"{html.escape(text)}"
        )
        await client.send_message(target_chat, caption)
        Altruix.log(f"✅ [Bypass] Text sent to {target_chat}", level=20)

# ====================== INFO & SECURITY HANDLERS ======================

# Note: gen_conf_export_session and gen_conf_export_phone are handled in security_handlers.py

# Helper to format seconds to readable time
def format_interval(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h}h {m}m" if m else f"{h}h"
    return f"{seconds // 86400}d"

@Altruix.bot.on_callback_query(filters.regex(r"^test_ping_all_confirm(?:ation)?$"))
@iuser_check
@log_errors
async def test_ping_all_dashboard_handler(c: Client, cb: CallbackQuery):
    """Auto Ping All Management Dashboard"""
    await cb.answer()
    
    # Fetch current settings from database
    status = await Altruix.config.get_env("AUTO_PING_ALL") or "off"
    mode = await Altruix.config.get_env("AUTO_PING_MODE") or "test"
    interval = await Altruix.config.get_env("AUTO_PING_INTERVAL") or 300
    try: 
        interval = int(interval)
    except: 
        interval = 300
    
    # UI Setup
    user_id = cb.from_user.id
    user_style = get_user_button_style(user_id)
    
    status_emoji = "🟢 ON" if str(status).lower() == "on" else "🔴 OFF"
    mode_val = str(mode).lower()
    if mode_val == "message":
        mode_text = "📡 Test + Message"
        next_mode_btn = "Test + Online"
    elif mode_val == "online":
        mode_text = "🟢 Test + Online"
        next_mode_btn = "Test Only"
    else:
        mode_text = "🔍 Test Only"
        next_mode_btn = "Test + Msg"
        
    readable_interval = format_interval(interval)
    
    text = (
        "<b>🏓 Auto Ping All Manager</b>\n\n"
        f"• Status Auto Ping: <b>{status_emoji}</b>\n"
        f"• Ping Mode: <b>{mode_text}</b>\n"
        f"• Interval: <code>{readable_interval}</code>\n\n"
        "Gunakan tombol di bawah untuk mengatur auto-ping atau menjalankan tes manual secara massal."
    )

    
    buttons = [
        [
            InlineKeyboardButton(f"Toggle Status: {('TURN OFF' if str(status).lower() == 'on' else 'TURN ON')}", "auto_ping_toggle", style=user_style),
            InlineKeyboardButton(f"Mode: {next_mode_btn}", "auto_ping_mode_toggle", style=user_style)
        ],


        [
            InlineKeyboardButton("-1h", "auto_ping_int_-3600", style=user_style),
            InlineKeyboardButton("-10m", "auto_ping_int_-600", style=user_style),
            InlineKeyboardButton("-1m", "auto_ping_int_-60", style=user_style)
        ],
        [
            InlineKeyboardButton("+1m", "auto_ping_int_60", style=user_style),
            InlineKeyboardButton("+10m", "auto_ping_int_600", style=user_style),
            InlineKeyboardButton("+1h", "auto_ping_int_3600", style=user_style)
        ],
        [InlineKeyboardButton("🚀 Run Ping Test Now", "auto_ping_run_now", style=user_style)],
        [InlineKeyboardButton("🔙 Back", "bulk_controls_menu", style=user_style)]
    ]

    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons))

@Altruix.bot.on_callback_query(filters.regex(r"^auto_ping_toggle$"))
@iuser_check
@log_errors
async def auto_ping_toggle_handler(c: Client, cb: CallbackQuery):
    """Toggle Auto Ping status"""
    current = await Altruix.config.get_env("AUTO_PING_ALL") or "off"
    new_status = "off" if str(current).lower() == "on" else "on"
    
    await Altruix.config.set_env("AUTO_PING_ALL", new_status)
    await cb.answer(f"✅ Auto Ping turned {new_status.upper()}")
    await test_ping_all_dashboard_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^get_otp_exec_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def get_otp_exec_handler(c: Client, cb: CallbackQuery):
    """Retrieve Telegram OTP from session and format it with dashes and spaces."""
    index, page = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    await cb.answer("⏳ Fetching latest OTP...", show_alert=False)
    
    if index >= len(Altruix.clients):
        return await cb.answer("❌ Session not found.", show_alert=True)
    
    client = Altruix.clients[index]
    try:
        # Search for messages from 777000 (Telegram Official)
        async for msg in client.get_chat_history(777000, limit=1):
            if msg.text:
                # Regex to find 5-digit code or similar common OTP formats
                otp_match = re.search(r"(\d{5})", msg.text)
                if otp_match:
                    otp_code = otp_match.group(1)
                    # Format as requested: 2 - 2 - 6 - 4 - 4
                    formatted_otp = " - ".join(list(otp_code))
                    
                    me = client.me or await client.get_me()
                    full_name = f"{me.first_name} {me.last_name or ''}".strip()
                    phone = f"+{me.phone_number}" if me.phone_number else "N/A"
                    
                    full_text = (
                        "<b>🗝️ TELEGRAM OTP RECOVERY</b>\n\n"
                        f"• <b>Account Name:</b> <code>{html.escape(full_name)}</code>\n"
                        f"• <b>ID:</b> <code>{me.id}</code>\n"
                        f"• <b>Phone Number:</b> <code>{phone}</code>\n"
                        f"• <b>Login Code:</b> <code>{formatted_otp}</code>\n\n"
                        f"<b>Last Received:</b> <i>{msg.date.strftime('%Y-%m-%d %H:%M:%S')}</i>\n\n"
                        "⚠️ <i>Kode ini telah diformat agar aman dari sistem deteksi auto-expired Telegram.</i>"
                    )

                    
                    user_style = get_user_button_style(cb.from_user.id)
                    buttons = [
                        [InlineKeyboardButton("🔄 Refresh", f"get_otp_exec_{index}_{page}", style=user_style)],
                        [InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}", style=user_style)]
                    ]
                    
                    return await edit_cb(cb, full_text, reply_markup=InlineKeyboardMarkup(buttons))
        
        await cb.answer("❌ Tidak ditemukan kode OTP terbaru dari Telegram (777000).", show_alert=True)
    except Exception as e:
        await cb.answer(f"❌ Error: {str(e)}", show_alert=True)



@Altruix.bot.on_callback_query(filters.regex(r"^auto_ping_mode_toggle$"))
@iuser_check
@log_errors
async def auto_ping_mode_toggle_handler(c: Client, cb: CallbackQuery):
    """Toggle Auto Ping mode (test vs message vs online)"""
    current = await Altruix.config.get_env("AUTO_PING_MODE") or "test"
    mode_val = str(current).lower()
    if mode_val == "test":
        new_mode = "message"
        label = "Test + Message"
    elif mode_val == "message":
        new_mode = "online"
        label = "Test + Online"
    else:
        new_mode = "test"
        label = "Test Only"
    
    await Altruix.config.set_env("AUTO_PING_MODE", new_mode)
    await cb.answer(f"✅ Mode changed to: {label}")
    await test_ping_all_dashboard_handler(c, cb)


@Altruix.bot.on_callback_query(filters.regex(r"^auto_ping_int_(-?\d+)$"))
@iuser_check
@log_errors
async def auto_ping_interval_handler(c: Client, cb: CallbackQuery):
    """Adjust Auto Ping interval"""
    adjustment = int(cb.matches[0].group(1))
    current = await Altruix.config.get_env("AUTO_PING_INTERVAL") or 300
    try: 
        current = int(current)
    except: 
        current = 300
    
    new_interval = current + adjustment
    if new_interval < 60:
        new_interval = 60
        await cb.answer("⚠️ Min interval is 1 minute.", show_alert=True)
    else:
        await cb.answer(f"✅ Interval adjusted by {format_interval(abs(adjustment))}")
        
    await Altruix.config.set_env("AUTO_PING_INTERVAL", new_interval)
    await test_ping_all_dashboard_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^auto_ping_run_now$"))
@iuser_check
@log_errors
async def auto_ping_run_now_handler(c: Client, cb: CallbackQuery):
    """Execute manual ping test across all sessions and send split report."""
    await cb.answer("🚀 Starting manual Auto Ping cycle...")
    user_style = get_user_button_style(cb.from_user.id)
    total = len(Altruix.clients)
    
    if total == 0:
        return await edit_cb(cb, "❌ No active sessions to test.", 
                           reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", "test_ping_all_confirm", style=user_style)]]))

    status_msg = await edit_cb(cb, f"⏳ Testing latency for <b>{total}</b> sessions...\n<i>Reports will be sent to log group.</i>")
    
    try:
        # Fetch current mode for manual run
        mode = await Altruix.config.get_env("AUTO_PING_MODE") or "test"
        
        # Manually trigger a ping cycle through the manager (sends split report to log group)
        await Altruix.auto_ping._execute_ping_cycle(mode=mode, title="MANUAL - PING ALL")

        # ✅ Also do a quick local ping for the inline dashboard summary
        import time as _time
        online = 0
        offline = 0
        total_ms = 0.0
        
        for i, client in enumerate(Altruix.clients):
            try:
                start = _time.time()
                await client.get_me()
                ping = round((_time.time() - start) * 1000, 2)
                online += 1
                total_ms += ping
            except Exception:
                offline += 1
        
        avg_ms = round(total_ms / online, 2) if online > 0 else 0
        
        # ✅ Show compact summary in the inline message (safe for any session count)
        summary_txt = (
            "<b>✅ Manual Ping Test Completed</b>\n\n"
            f"• <b>Total:</b> <code>{total}</code>\n"
            f"• <b>Online:</b> <code>{online}</code>\n"
            f"• <b>Offline:</b> <code>{offline}</code>\n"
            f"• <b>Avg Latency:</b> <code>{avg_ms}ms</code>\n\n"
            "<i>📋 Detailed report has been sent to Log Group.</i>"
        )
        await edit_cb(cb, summary_txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", "test_ping_all_confirm", style=user_style)]]))
    except Exception as e:
        await cb.answer(f"❌ Error: {str(e)}", show_alert=True)
        await edit_cb(cb, f"❌ <b>Error running manual ping:</b>\n<code>{str(e)}</code>", 
                           reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", "test_ping_all_confirm", style=user_style)]]))



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
    chat_limit = await Altruix.config.get_env(f"RECENT_CHATS_LIMIT_{index}") or 200
    
    # Fetch delays
    delay_chat = await Altruix.config.get_env(f"RECENT_MSGS_DELAY_CHAT_{index}") or 1.0
    delay_msg = await Altruix.config.get_env(f"RECENT_MSGS_DELAY_MSG_{index}") or 0.5
    
    text = (
        f"<b>📨 Recent Messages (Session {index+1})</b>\n\n"
        f"• Limit (Messages): <code>{limit}</code> messages\n"
        f"• Scan Limit (Chat): <code>{chat_limit}</code> chats\n"
        f"• Delay/Chat: <code>{delay_chat}</code>s\n"
        f"• Delay/Msg: <code>{delay_msg}</code>s\n\n"
        "Pilih kategori pesan yang ingin Anda lihat:"
    )
    buttons = [
        [
            InlineKeyboardButton("👤 All Users", f"recent_msgs_list_{index}_{page}_user", style=user_style),
            InlineKeyboardButton("🤖 All Bots", f"recent_msgs_list_{index}_{page}_bot", style=user_style)
        ],
        [
            InlineKeyboardButton("🌐 All Messages", f"recent_msgs_list_{index}_{page}_all", style=user_style),
            InlineKeyboardButton("🎯 Select Chat", f"recent_msgs_select_chat_{index}_{page}", style=user_style)
        ],
        [
            InlineKeyboardButton(f"⏳ Chat: {delay_chat}s", f"recent_msgs_delay_chat_{index}_{page}", style=user_style),
            InlineKeyboardButton(f"⏳ Msg: {delay_msg}s", f"recent_msgs_delay_msg_{index}_{page}", style=user_style)
        ],
        [InlineKeyboardButton("⚙️ Set Limit (Msg)", f"set_scan_limit_{index}_{page}_recent", style=user_style)],
        [InlineKeyboardButton("⚙️ Set Limit (Chat)", f"set_scan_limit_{index}_{page}_chats", style=user_style)],
        [InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}_2", style=user_style)]
    ]
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^recent_msgs_delay_(chat|msg)_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def recent_messages_delay_menu_handler(c: Client, cb: CallbackQuery):
    """Sub-menu for setting delay per chat or per message"""
    d_type, index, page = cb.matches[0].group(1), int(cb.matches[0].group(2)), int(cb.matches[0].group(3))
    await cb.answer()
    
    session_id = Altruix.clients[index].me.id if index < len(Altruix.clients) and hasattr(Altruix.clients[index], 'me') and Altruix.clients[index].me else cb.from_user.id
    user_style = get_user_button_style(session_id)
    
    key = f"RECENT_MSGS_DELAY_{d_type.upper()}_{index}"
    current = await Altruix.config.get_env(key) or (1.0 if d_type == "chat" else 0.5)
    current = float(current)
    
    text = (
        f"<b>⏳ Set Delay Per {d_type.capitalize()}</b>\n\n"
        f"Current Delay: <code>{current}</code> seconds\n\n"
        "Gunakan tombol di bawah untuk menambah atau mengurangi delay.\n"
        "Delay yang tepat membantu menghindari FloodWait."
    )
    
    values = [0.25, 0.5, 1.0, 3.0]
    kb = []
    
    # Value rows with - and +
    for val in values:
        kb.append([
            InlineKeyboardButton(f"- {val}s", f"set_recent_delay_{d_type}_{index}_{page}_minus_{val}", style=user_style),
            InlineKeyboardButton(f"Value: {val}s", "ignore", style=user_style),
            InlineKeyboardButton(f"+ {val}s", f"set_recent_delay_{d_type}_{index}_{page}_plus_{val}", style=user_style)
        ])
        
    kb.append([InlineKeyboardButton("🔙 Back", f"recent_msgs_menu_{index}_{page}", style=user_style)])
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^set_recent_delay_(chat|msg)_(\d+)_(\d+)_(plus|minus)_([\d\.]+)$"))
@iuser_check
@log_errors
async def set_recent_delay_handler(c: Client, cb: CallbackQuery):
    """Adjust delay value and save to DB"""
    d_type, index, page, action, val = cb.matches[0].group(1), int(cb.matches[0].group(2)), int(cb.matches[0].group(3)), cb.matches[0].group(4), float(cb.matches[0].group(5))
    
    key = f"RECENT_MSGS_DELAY_{d_type.upper()}_{index}"
    current = await Altruix.config.get_env(key) or (1.0 if d_type == "chat" else 0.5)
    current = float(current)
    
    if action == "plus":
        new_val = current + val
    else:
        new_val = max(0.0, current - val)
    
    new_val = round(new_val, 2)
    
    try:
        await Altruix.config.sync_env_to_db(key, new_val, upsert=True)
        # Update cache
        setattr(Altruix.config, key, new_val)
    except Exception as e:
        Altruix.log(f"Error saving delay: {e}", level=40)
        
    await cb.answer(f"✅ Delay updated: {new_val}s")
    await recent_messages_delay_menu_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^recent_msgs_select_chat_(\d+)_(\d+)(?:_p(\d+))?$"))
@iuser_check
@log_errors
async def recent_messages_select_chat_handler(c: Client, cb: CallbackQuery):
    """Menu to select a specific chat for recent messages"""
    index, page = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    sub_page = int(cb.matches[0].group(3) or 1)
    await cb.answer("📂 Fetching chats...", show_alert=False)
    
    client = Altruix.clients[index]
    user_id = cb.from_user.id
    user_style = get_user_button_style(client.me.id if client.me else user_id)
    
    try:
        dialogs = []
        # Use a smaller limit for chat selection list
        async for dialog in client.get_dialogs(limit=50):
            dialogs.append(dialog)
            
        if not dialogs:
            return await cb.answer("❌ No chats found.", show_alert=True)
            
        # Pagination for dialogs (10 per page)
        per_page = 10
        total_pages = (len(dialogs) + per_page - 1) // per_page
        start = (sub_page - 1) * per_page
        end = start + per_page
        current_dialogs = dialogs[start:end]
        
        text = (
            f"<b>🎯 Select Target Chat (Session {index+1})</b>\n\n"
            f"Page: <code>{sub_page}/{total_pages}</code>\n"
            "Pilih chat di bawah untuk melihat pesan terbaru dari chat tersebut:"
        )
        
        kb = []
        for d in current_dialogs:
            name = (d.chat.title or d.chat.first_name or "Unknown")
            if len(name) > 25: name = name[:22] + "..."
            kb.append([InlineKeyboardButton(name, f"recent_msgs_view_chat_{index}_{page}_{d.chat.id}_select")])
            
        # Nav buttons
        nav = []
        if sub_page > 1:
            nav.append(InlineKeyboardButton("⬅️ Prev", f"recent_msgs_select_chat_{index}_{page}_p{sub_page-1}", style=user_style))
        if sub_page < total_pages:
            nav.append(InlineKeyboardButton("Next ➡️", f"recent_msgs_select_chat_{index}_{page}_p{sub_page+1}", style=user_style))
        if nav: kb.append(nav)
        
        kb.append([InlineKeyboardButton("🔙 Back", f"recent_msgs_menu_{index}_{page}", style=user_style)])
        
        await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)
    except Exception as e:
        Altruix.log(f"Error fetching dialogs for selection: {e}", level=40)
        await cb.answer(f"❌ Error: {str(e)}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^recent_msgs_view_chat_(\d+)_(\d+)_(-?\d+)_([a-z]+)$"))
@iuser_check
@log_errors
async def recent_messages_view_chat_handler(c: Client, cb: CallbackQuery):
    """View recent messages from a specific selected chat"""
    index, page, chat_id, f_type = int(cb.matches[0].group(1)), int(cb.matches[0].group(2)), int(cb.matches[0].group(3)), cb.matches[0].group(4)
    await cb.answer("📨 Fetching messages...", show_alert=False)
    
    client = Altruix.clients[index]
    user_id = cb.from_user.id
    user_style = get_user_button_style(client.me.id if client.me else user_id)
    
    try:
        chat = await client.get_chat(chat_id)
        chat_name = chat.title or chat.first_name or "Unknown"
        
        # Fetch msg limit
        msg_limit = await Altruix.config.get_env(f"RECENT_MSGS_LIMIT_{index}") or 200
        msg_limit = int(msg_limit)
        
        messages = []
        async for msg in client.get_chat_history(chat_id, limit=min(msg_limit, 50)): # UI display limit
            messages.append(msg)
            
        if not messages:
            return await cb.answer("❌ No messages found in this chat.", show_alert=True)
            
        txt = f"<b>📨 Recent Messages: {html.escape(chat_name)}</b>\n\n"
        for i, m in enumerate(messages, 1):
            try:
                text = (m.text or m.caption or "[Media]")
                if len(text) > 40: text = text[:37] + "..."
                text = html.escape(text.replace('\n', ' '))
                date = m.date.strftime("%H:%M")
                txt += f"{i}. [<code>{date}</code>] <code>{text}</code>\n"
            except: continue
            
        # Determine back callback
        if f_type in ["user", "bot", "all"]:
            back_cb = f"recent_msgs_list_{index}_{page}_{f_type}"
        else:
            back_cb = f"recent_msgs_select_chat_{index}_{page}"
            
        kb = [
            [
                InlineKeyboardButton("📤 Forward Log", f"fwd_chat_recent_{index}_{page}_{chat_id}_{f_type}_log", style=user_style),
                InlineKeyboardButton("🤖 Forward PM", f"fwd_chat_recent_{index}_{page}_{chat_id}_{f_type}_bot", style=user_style)
            ],
            [InlineKeyboardButton("🔄 Refresh", f"recent_msgs_view_chat_{index}_{page}_{chat_id}_{f_type}", style=user_style)],
            [InlineKeyboardButton("🔙 Back", back_cb, style=user_style)],
            [InlineKeyboardButton("🔙 Dashboard", f"session_info_{index}_{page}_2", style=user_style)]
        ]
        
        await edit_cb(cb, txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)
    except Exception as e:
        Altruix.log(f"Error fetching chat history: {e}", level=40)
        await cb.answer(f"❌ Error: {str(e)}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^fwd_chat_recent_(\d+)_(\d+)_(-?\d+)_([a-z]+)_(log|bot)$"))
@iuser_check
@log_errors
async def forward_specific_chat_recent_handler(c: Client, cb: CallbackQuery):
    """Handle forwarding from a specific chat with delay settings"""
    index, page, chat_id, f_type, target_type = int(cb.matches[0].group(1)), int(cb.matches[0].group(2)), int(cb.matches[0].group(3)), cb.matches[0].group(4), cb.matches[0].group(5)
    await cb.answer("📤 Starting forward...", show_alert=False)
    
    client = Altruix.clients[index]
    user_id = cb.from_user.id
    user_style = get_user_button_style(client.me.id if client.me else user_id)
    
    # Target
    if target_type == "log":
        target_chat = Altruix.log_chat
        target_name = "Log Group"
    else:
        target_chat = user_id
        target_name = "PM Bot"
        
    if not target_chat:
        return await cb.answer(f"❌ {target_name} is not configured.", show_alert=True)
        
    # Delays
    delay_msg = await Altruix.config.get_env(f"RECENT_MSGS_DELAY_MSG_{index}") or 0.5
    delay_msg = float(delay_msg)
    
    # Fetch msg limit
    msg_limit = await Altruix.config.get_env(f"RECENT_MSGS_LIMIT_{index}") or 200
    msg_limit = int(msg_limit)
    
    try:
        messages = []
        async for msg in client.get_chat_history(chat_id, limit=msg_limit):
            messages.append(msg)
            
        if not messages:
            return await cb.answer("❌ No messages to forward.", show_alert=True)
            
        success, failed = 0, 0
        total = len(messages)
        
        for i, msg in enumerate(messages, 1):
            try:
                await edit_cb(cb, f"⏳ <b>Forwarding Messages ({i}/{total})</b>\nTarget: <code>{target_name}</code>\nDelay: <code>{delay_msg}</code>s", parse_mode=ParseMode.HTML)
                
                is_protected = getattr(msg, "has_protected_content", False)
                is_self_destruct = False
                if msg.media:
                    # Check for self-destruct in different media types
                    for attr in ['photo', 'video', 'video_note', 'voice']:
                        media_obj = getattr(msg, attr, None)
                        if media_obj and (getattr(media_obj, 'ttl_seconds', None) or getattr(msg, 'ttl_period', None)):
                            is_self_destruct = True
                            break

                if is_protected or is_self_destruct:
                    # Bypass logic (Download/Manual Send)
                    await handle_bypass_forward(client, msg, target_chat, index, chat_id, chat_name)
                    success += 1
                else:
                    try:
                        # Normal forward
                        await client.forward_messages(target_chat, chat_id, msg.id)
                        success += 1
                    except Exception as fwd_err:
                        # If forward is restricted by the chat, try bypass
                        if "CHAT_FORWARDS_RESTRICTED" in str(fwd_err):
                            Altruix.log(f"� [Fwd Specific] Forward restricted for {chat_id}. Falling back to bypass...", level=20)
                            await handle_bypass_forward(client, msg, target_chat, index, chat_id, chat_name)
                            success += 1
                        else:
                            raise fwd_err
                
                if i < total:
                    await asyncio.sleep(delay_msg)
                    
            except Exception as e:
                Altruix.log(f"Forward error in specific chat: {e}", level=30)
                failed += 1
                
        final_text = (
            f"✅ <b>Forward Complete!</b>\n\n"
            f"• Target: <code>{target_name}</code>\n"
            f"• Success: <code>{success}</code>\n"
            f"• Failed: <code>{failed}</code>"
        )
        await edit_cb(cb, final_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"recent_msgs_view_chat_{index}_{page}_{chat_id}_{f_type}", style=user_style)]]))
        
    except Exception as e:
        Altruix.log(f"Fatal error in specific forward: {e}", level=40)
        await cb.answer(f"❌ Error: {str(e)}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^set_scan_limit_(\d+)_(\d+)_(recent|mnt|chats)$"))
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
    
    if s_type == "recent":
        target_name = "Recent Messages (Messages)"
    elif s_type == "chats":
        target_name = "Recent Messages (Scan Limit Chat)"
    else:
        target_name = "View Mentions"
    
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
        limit_val = await Altruix.config.get_env(f"RECENT_CHATS_LIMIT_{index}") or 200
        limit_val = int(limit_val)
        
        await edit_cb(cb, f"🔍 <b>Scanning up to {limit_val} chats...</b>\n<i>Please wait a moment...</i>", parse_mode=ParseMode.HTML)
        
        # 🟢 Progress update helper
        async def update_progress(current, total):
            pct = int((current / total) * 100) if total > 0 else 0
            msg = f"🔍 <b>Scanning chats... ({current}/{total})</b>\n<i>Progress: {pct}%</i>"
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
        
        session_id = client.me.id if hasattr(client, 'me') and client.me else cb.from_user.id
        user_style = get_user_button_style(session_id)
        
        kb = []
        for i, d in enumerate(dialogs, 1):
            try:
                # 🛡️ DEFENSIVE NAME RETRIEVAL
                raw_name = (d.chat.title or d.chat.first_name or "Unknown")
                name = raw_name
                if d.chat.type == ChatType.BOT:
                    name = "🤖 " + name
                
                # 🛡️ DEFENSIVE TEXT RETRIEVAL
                try:
                    last_msg = (d.top_message.text or d.top_message.caption or "[Media]") if d.top_message else "[No Messages]"
                except:
                    last_msg = "[Message Error]"

                msg_date = d.top_message.date.strftime("%H:%M") if d.top_message and hasattr(d.top_message, 'date') else "--:--"
                
                # Clean text safely for the message body
                display_msg = last_msg
                if len(display_msg) > 40: display_msg = display_msg[:37] + "..."
                display_msg = html.escape(display_msg.replace('\n', ' '))
                
                txt += f"{i}. <b>{html.escape(name)}</b> [<code>{msg_date}</code>]\n   └ <code>{display_msg}</code>\n"
                
                # 🔘 ADD BUTTON FOR EACH CHAT
                btn_label = f"{i}. {raw_name} [{msg_date}]"
                if len(btn_label) > 30: btn_label = btn_label[:27] + "..."
                kb.append([InlineKeyboardButton(btn_label, f"recent_msgs_view_chat_{index}_{page}_{d.chat.id}_{f_type}")])
                
            except Exception as inner_e:
                Altruix.log(f"⚠️ [Recent Messages List] Skipping corrupted dialog entry {i}: {inner_e}", level=10)
                continue
            
        # Global Action Buttons
        kb.append([
            InlineKeyboardButton("📤 Fwd All Log", f"fwd_recent_{index}_{page}_{f_type}_log", style=user_style),
            InlineKeyboardButton("🤖 Fwd All PM", f"fwd_recent_{index}_{page}_{f_type}_bot", style=user_style)
        ])
        kb.append([
            InlineKeyboardButton("🔄 Refresh", f"recent_msgs_list_{index}_{page}_{f_type}", style=user_style),
            InlineKeyboardButton("🔙 Back", f"recent_msgs_menu_{index}_{page}", style=user_style)
        ])
        kb.append([InlineKeyboardButton("🔙 Dashboard", f"session_info_{index}_{page}_2", style=user_style)])

        await edit_cb(cb, txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)
    except Exception as e:
        Altruix.log(f"❌ [Recent Messages List] Fatal Error: {e}", level=40, client=client)
        await cb.answer(f"❌ Error: {str(e)}", show_alert=True)
        from .session_info import get_session_info_data
        text, reply_markup = await get_session_info_data(index, page, 2)
        text = f"<b>❌ Error scanning messages:</b> <code>{html.escape(str(e))}</code>\n\n" + text
        return await edit_cb(cb, text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^fwd_recent_(\d+)_(\d+)_(user|bot|all)_(log|bot)$"))
@iuser_check
@log_errors
async def forward_recent_messages_handler(c: Client, cb: CallbackQuery):
    """Handle forwarding of recent messages to Log Group or PM Bot"""
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    f_type = cb.matches[0].group(3)
    target_type = cb.matches[0].group(4)
    
    await cb.answer("📤 Processing forward request...", show_alert=False)
    
    if index >= len(Altruix.clients):
        return await cb.answer("❌ Session not found.", show_alert=True)
    
    client = Altruix.clients[index]
    user_id = cb.from_user.id
    user_style = get_user_button_style(client.me.id if client.me else user_id)
    
    # Resolve target chat ID
    if target_type == "log":
        target_chat = Altruix.log_chat
        target_name = "Log Group"
    else:
        target_chat = user_id
        target_name = "PM Bot"
        
    if not target_chat:
        return await cb.answer(f"❌ {target_name} is not configured.", show_alert=True)

    # Delays
    delay_chat = await Altruix.config.get_env(f"RECENT_MSGS_DELAY_CHAT_{index}") or 1.0
    delay_chat = float(delay_chat)

    # Logging start
    Altruix.log(f"📤 [Forward Recent] Starting forward for session {index} to {target_name} (Delay Chat: {delay_chat}s)", level=20, client=client)
    
    status_msg = await edit_cb(cb, f"⏳ <b>Forwarding Recent Messages...</b>\nTarget: <code>{target_name}</code>\n<i>Fetching dialogs...</i>", parse_mode=ParseMode.HTML)

    try:
        # Fetch dialogs (same logic as list handler)
        dialogs = []
        limit_val = await Altruix.config.get_env(f"RECENT_CHATS_LIMIT_{index}") or 200
        limit_val = int(limit_val)
        
        scanned = 0
        async for dialog in client.get_dialogs(limit=limit_val):
            scanned += 1
            if f_type == "user" and dialog.chat.type != ChatType.PRIVATE: continue
            if f_type == "bot" and dialog.chat.type != ChatType.BOT: continue
            dialogs.append(dialog)
            if len(dialogs) >= 15: break
            
        if not dialogs:
            return await cb.answer("❌ No messages found to forward.", show_alert=True)

        success = 0
        failed = 0
        total_dialogs = len(dialogs)
        
        for i, d in enumerate(dialogs, 1):
            msg = d.top_message
            if not msg: continue
            
            try:
                await edit_cb(cb, f"⏳ <b>Forwarding Recent Messages ({i}/{total_dialogs})</b>\nProcessing: <code>{html.escape(d.chat.title or d.chat.first_name or 'Unknown')}</code>\nDelay: <code>{delay_chat}</code>s", parse_mode=ParseMode.HTML)
                
                is_protected = getattr(msg, "has_protected_content", False)
                is_self_destruct = False
                if msg.media:
                    # Check for self-destruct in different media types
                    for attr in ['photo', 'video', 'video_note', 'voice']:
                        media_obj = getattr(msg, attr, None)
                        if media_obj and (getattr(media_obj, 'ttl_seconds', None) or getattr(msg, 'ttl_period', None)):
                            is_self_destruct = True
                            break

                if is_protected or is_self_destruct:
                    # Bypass logic (Download/Manual Send)
                    await handle_bypass_forward(client, msg, target_chat, index, chat_id, d.chat.title or d.chat.first_name or 'Unknown')
                    success += 1
                else:
                    try:
                        # Normal forward
                        await client.forward_messages(target_chat, d.chat.id, msg.id)
                        success += 1
                    except Exception as fwd_err:
                        # If forward is restricted by the chat, try bypass
                        if "CHAT_FORWARDS_RESTRICTED" in str(fwd_err):
                            Altruix.log(f"🔄 [Fwd Bulk] Forward restricted for {d.chat.id}. Falling back to bypass...", level=20)
                            await handle_bypass_forward(client, msg, target_chat, index, d.chat.id, d.chat.title or d.chat.first_name or 'Unknown')
                            success += 1
                        else:
                            raise fwd_err
                
                # Apply delay per chat
                if i < total_dialogs:
                    await asyncio.sleep(delay_chat)
                
            except Exception as inner_e:
                Altruix.log(f"⚠️ [Forward Recent] Error forwarding msg from {d.chat.id}: {inner_e}\n{traceback.format_exc()}", level=30, client=client)
                failed += 1

        # Final status
        final_text = (
            f"✅ <b>Forward Complete!</b>\n\n"
            f"• Target: <code>{target_name}</code>\n"
            f"• Success: <code>{success}</code>\n"
            f"• Failed: <code>{failed}</code>\n\n"
            f"Messages have been forwarded to {target_name}."
        )
        
        # Save last forward stats to DB
        await Altruix.config.sync_env_to_db(f"LAST_FWD_STATS_{index}", f"{success}s_{failed}f_{target_type}", upsert=True)
        
        await edit_cb(cb, final_text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to List", f"recent_msgs_list_{index}_{page}_{f_type}", style=user_style)],
            [InlineKeyboardButton("🔙 Dashboard", f"session_info_{index}_{page}_2", style=user_style)]
        ]))
        
    except Exception as e:
        Altruix.log(f"❌ [Forward Recent] Fatal Error: {e}\n{traceback.format_exc()}", level=40, client=client)
        await cb.answer(f"❌ Error: {str(e)}", show_alert=True)
        return await edit_cb(cb, f"❌ <b>Forward Failed!</b>\n\n<code>{html.escape(str(e))}</code>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"recent_msgs_list_{index}_{page}_{f_type}", style=user_style)]]))

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
    if s_type == "recent":
        key = f"RECENT_MSGS_LIMIT_{index}"
    elif s_type == "chats":
        key = f"RECENT_CHATS_LIMIT_{index}"
    else:
        key = f"MENTIONS_LIMIT_{index}"
        
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
    
    if s_type == "recent":
        target_name = "Recent Messages (Messages)"
    elif s_type == "chats":
        target_name = "Recent Messages (Scan Limit Chat)"
    else:
        target_name = "View Mentions"
        
    back_cb = f"recent_msgs_menu_{index}_{page}" if s_type in ["recent", "chats"] else f"view_mnt_menu_{index}_{page}"
    
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

# ====================== SESSION UNLINK HANDLER ======================

@Altruix.bot.on_callback_query(filters.regex(r"^unlink_session_exec_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def unlink_session_exec_handler(c: Client, cb: CallbackQuery):
    """Execution handler for unlinking a session."""
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    
    # ✅ Immediate answer to remove button loading state
    await cb.answer("⏳ Processing unlinking...", show_alert=False)
    
    try:
        # Get info before removing for the alert
        if index < len(Altruix.clients):
            client_to_remove = Altruix.clients[index]
            me = getattr(client_to_remove, "me", None) or getattr(client_to_remove, "myself", None)
            name = me.first_name if me else f"Session {index + 1}"
            
            # ✅ Visual feedback: Edit message to show processing state
            await cb.edit_message_text(f"<b>🗑 Unlinking Session...</b>\n\nRemoving <code>{html.escape(name)}</code> from manager. Please wait.", parse_mode=ParseMode.HTML)
        else:
            return await cb.answer("❌ Session already removed or index invalid.", show_alert=True)
            
        # Execute Core Removal logic
        await Altruix.remove_session(index, cb.from_user)
        
        await cb.answer(f"✅ Session '{name}' has been unlinked successfully!", show_alert=True)
        
        # Redirect to Main Sessions List (Page 1 as fallback)
        from .sessions_list import sessions_menu_cb_handler
        cb.data = f"sessions_list_{page}"
        await sessions_menu_cb_handler(c, cb)
        
    except Exception as e:
        import traceback
        logger.error(f"Unlink Session Error: {e}\n{traceback.format_exc()}")
        await cb.answer(f"❌ Error unlinking session: {str(e)}", show_alert=True)


