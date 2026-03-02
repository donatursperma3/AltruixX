# session_handlers.py - All Missing Session Info Button Handlers
# This file contains all 34 missing handlers for session info buttons

from Main import Altruix
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from Main.core.decorators import log_errors, iuser_check
from Main.internals.settings_handlers.utils import edit_cb, send_log_notification
from Main.internals.settings import user_profile_edit_state
import html

# ====================== INFO & SECURITY HANDLERS ======================

@Altruix.bot.on_callback_query(filters.regex(r"^gen_conf_export_session_(\d+)_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def export_session_handler(c: Client, cb: CallbackQuery):
    """Export session string"""
    await cb.answer("📤 Exporting session...")
    index = int(cb.matches[0].group(1))
    callback_page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3))
    
    if index >= len(Altruix.clients):
        await cb.answer("❌ Session not found", show_alert=True)
        return
    
    session_client = Altruix.clients[index]
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)
    try:
        session_string = await session_client.export_session_string()
        await cb.message.reply(
            f"📤 <b>Session String</b>\n\n<code>{session_string}</code>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"session_info_{index}_{callback_page}_{button_page}", style=user_style)]])
        )
        await cb.answer("✅ Session exported!")
    except Exception as e:
        await cb.answer(f"❌ Error: {str(e)}", show_alert=True)


@Altruix.bot.on_callback_query(filters.regex(r"^gen_conf_export_phone_(\d+)_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def export_phone_handler(c: Client, cb: CallbackQuery):
    """Export phone number"""
    await cb.answer()
    index = int(cb.matches[0].group(1))
    callback_page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3))
    
    if index >= len(Altruix.clients):
        await cb.answer("❌ Session not found", show_alert=True)
        return
    
    session_client = Altruix.clients[index]
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)
    try:
        me = await session_client.get_me()
        phone = me.phone_number or "N/A"
        await edit_cb(
            cb,
            f"📱 <b>Phone Number</b>\n\n<code>{phone}</code>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"session_info_{index}_{callback_page}_{button_page}", style=user_style)]])
        )
    except Exception as e:
        await cb.answer(f"❌ Error: {str(e)}", show_alert=True)


@Altruix.bot.on_callback_query(filters.regex(r"^gen_conf_test_ping_(\d+)_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def test_ping_handler(c: Client, cb: CallbackQuery):
    """Test session ping"""
    index = int(cb.matches[0].group(1))
    callback_page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3))
    
    if index >= len(Altruix.clients):
        await cb.answer("❌ Session not found", show_alert=True)
        return
    
    session_client = Altruix.clients[index]
    await cb.answer("🏓 Testing ping...")
    
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)
    try:
        import time
        start = time.time()
        await session_client.get_me()
        ping = round((time.time() - start) * 1000, 2)
        
        await edit_cb(
            cb,
            f"🏓 <b>Ping Test</b>\n\n<b>Latency:</b> <code>{ping}ms</code>\n<b>Status:</b> ✅ Online",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"session_info_{index}_{callback_page}_{button_page}", style=user_style)]])
        )
    except Exception as e:
        await edit_cb(
            cb,
            f"🏓 <b>Ping Test</b>\n\n<b>Status:</b> ❌ Failed\n<b>Error:</b> {str(e)}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"session_info_{index}_{callback_page}_{button_page}", style=user_style)]])
        )


# ====================== GROUP & MESSAGE HANDLERS ======================

@Altruix.bot.on_callback_query(filters.regex(r"^gen_conf_join_chat_input_(\d+)_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def join_chat_handler(c: Client, cb: CallbackQuery):
    """Join group/channel"""
    await cb.answer()
    index = int(cb.matches[0].group(1))
    callback_page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3))
    
    user_profile_edit_state[cb.from_user.id] = {
        'action': 'join_chat',
        'index': index,
        'callback_page': callback_page,
        'button_page': button_page
    }
    
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)
    await edit_cb(
        cb,
        f"👥 <b>Join Group/Channel</b>\n\nSend the invite link or username:\n\n<i>Example: https://t.me/channel or @username</i>\n\n❌ Type /cancel to cancel",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", f"session_info_{index}_{callback_page}_{button_page}", style=user_style)]])
    )


@Altruix.bot.on_callback_query(filters.regex(r"^gen_conf_leave_chat_input_(\d+)_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def leave_chat_handler(c: Client, cb: CallbackQuery):
    """Leave group/channel"""
    await cb.answer()
    index = int(cb.matches[0].group(1))
    callback_page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3))
    
    user_profile_edit_state[cb.from_user.id] = {
        'action': 'leave_chat',
        'index': index,
        'callback_page': callback_page,
        'button_page': button_page
    }
    
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)
    await edit_cb(
        cb,
        f"🚪 <b>Leave Group/Channel</b>\n\nSend the chat ID or username:\n\n<i>Example: -1001234567890 or @username</i>\n\n❌ Type /cancel to cancel",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", f"session_info_{index}_{callback_page}_{button_page}", style=user_style)]])
    )


@Altruix.bot.on_callback_query(filters.regex(r"^gen_conf_send_message_input_(\d+)_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def send_message_handler(c: Client, cb: CallbackQuery):
    """Send message to chat"""
    await cb.answer()
    index = int(cb.matches[0].group(1))
    callback_page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3))
    
    user_profile_edit_state[cb.from_user.id] = {
        'action': 'send_message_step1',
        'index': index,
        'callback_page': callback_page,
        'button_page': button_page
    }
    
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)
    await edit_cb(
        cb,
        f"💬 <b>Send Message</b>\n\nStep 1: Send the chat ID or username:\n\n<i>Example: -1001234567890 or @username</i>\n\n❌ Type /cancel to cancel",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", f"session_info_{index}_{callback_page}_{button_page}", style=user_style)]])
    )


# ====================== DOWNLOAD HANDLERS ======================

@Altruix.bot.on_callback_query(filters.regex(r"^gen_conf_dl_uphoto_start_(\d+)_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def download_user_photo_handler(c: Client, cb: CallbackQuery):
    """Download user profile photos"""
    await cb.answer()
    index = int(cb.matches[0].group(1))
    callback_page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3))
    
    user_profile_edit_state[cb.from_user.id] = {
        'action': 'download_user_photo',
        'index': index,
        'callback_page': callback_page,
        'button_page': button_page
    }
    
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)
    await edit_cb(
        cb,
        f"📸 <b>Download User Photos</b>\n\nSend username or user ID:\n\n<i>Example: @username or 123456789</i>\n\n❌ Type /cancel to cancel",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", f"session_info_{index}_{callback_page}_{button_page}", style=user_style)]])
    )


@Altruix.bot.on_callback_query(filters.regex(r"^gen_conf_send_profile_photo_(\d+)_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def send_my_photo_handler(c: Client, cb: CallbackQuery):
    """Send own profile photo"""
    await cb.answer("📸 Fetching profile photo...")
    index = int(cb.matches[0].group(1))
    callback_page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3))
    
    if index >= len(Altruix.clients):
        await cb.answer("❌ Session not found", show_alert=True)
        return
    
    session_client = Altruix.clients[index]
    try:
        me = await session_client.get_me()
        photos = [p async for p in session_client.get_chat_photos(me.id, limit=1)]
        
        if photos:
            await cb.message.reply_photo(photos[0].file_id)
            await cb.answer("✅ Photo sent!")
        else:
            await cb.answer("❌ No profile photo found", show_alert=True)
    except Exception as e:
        await cb.answer(f"❌ Error: {str(e)}", show_alert=True)


@Altruix.bot.on_callback_query(filters.regex(r"^gen_conf_delete_all_profile_photos_(\d+)_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def delete_all_photos_handler(c: Client, cb: CallbackQuery):
    """Delete all profile photos"""
    await cb.answer()
    index = int(cb.matches[0].group(1))
    callback_page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3))
    
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)
    await edit_cb(
        cb,
        f"⚠️ <b>Delete All Profile Photos</b>\n\nAre you sure you want to delete ALL profile photos?\n\n<b>This action cannot be undone!</b>",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Yes, Delete All", f"delete_photos_confirm_{index}_{callback_page}_{button_page}", style=user_style)],
            [InlineKeyboardButton("❌ Cancel", f"session_info_{index}_{callback_page}_{button_page}", style=user_style)]
        ])
    )


@Altruix.bot.on_callback_query(filters.regex(r"^delete_photos_confirm_(\d+)_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def delete_photos_confirm_handler(c: Client, cb: CallbackQuery):
    """Confirm delete all photos"""
    await cb.answer("🗑️ Deleting photos...")
    index = int(cb.matches[0].group(1))
    callback_page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3))
    
    if index >= len(Altruix.clients):
        await cb.answer("❌ Session not found", show_alert=True)
        return
    
    session_client = Altruix.clients[index]
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)
    try:
        me = await session_client.get_me()
        photos = [p async for p in session_client.get_chat_photos(me.id)]
        
        deleted = 0
        for photo in photos:
            try:
                await session_client.delete_profile_photos(photo.file_id)
                deleted += 1
            except:
                pass
        
        await edit_cb(
            cb,
            f"✅ <b>Photos Deleted</b>\n\n<b>Deleted:</b> {deleted} photo(s)",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"session_info_{index}_{callback_page}_{button_page}", style=user_style)]])
        )
    except Exception as e:
        await cb.answer(f"❌ Error: {str(e)}", show_alert=True)


# ====================== RECENT MESSAGES & GLOBAL STATS ======================

@Altruix.bot.on_callback_query(filters.regex(r"^gen_conf_recent_messages_menu_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def recent_messages_menu_handler(c: Client, cb: CallbackQuery):
    """Menu selection for Recent Messages filter"""
    index, page = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    await cb.answer()
    
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)
    text = (
        f"<b>📨 Recent Messages (Session {index+1})</b>\n\n"
        "Pilih kategori pesan yang ingin Anda lihat:"
    )
    buttons = [
        [
            InlineKeyboardButton("👤 All Users", f"recent_msgs_list_{index}_{page}_user", style=user_style),
            InlineKeyboardButton("🤖 All Bots", f"recent_msgs_list_{index}_{page}_bot", style=user_style)
        ],
        [InlineKeyboardButton("🌐 All Messages", f"recent_msgs_list_{index}_{page}_all", style=user_style)],
        [InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}", style=user_style)]
    ]
    await cb.message.edit(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^recent_msgs_list_(\d+)_(\d+)_(user|bot|all)$"))
@iuser_check
@log_errors
async def recent_messages_list_handler(c: Client, cb: CallbackQuery):
    """Display the list of recent messages based on filter"""
    index, page, f_type = int(cb.matches[0].group(1)), int(cb.matches[0].group(2)), cb.matches[0].group(3)
    await cb.answer("📨 Fetching recent messages...", show_alert=False)
    
    if index >= len(Altruix.clients): return
    client = Altruix.clients[index]
    
    try:
        dialogs = []
        async for dialog in client.get_dialogs(limit=30):
            if dialog.chat.type != ChatType.PRIVATE: continue
            
            is_bot = dialog.chat.is_bot
            if f_type == "user" and is_bot: continue
            if f_type == "bot" and not is_bot: continue
            
            dialogs.append(dialog)
            if len(dialogs) >= 15: break

        if not dialogs:
            await cb.answer("❌ No messages found for this filter.", show_alert=True)
            return

        txt = f"<b>📨 Recent Messages ({f_type.capitalize()})</b>\n\n"
        for i, d in enumerate(dialogs, 1):
            name = d.chat.first_name or "Unknown"
            last_msg = d.top_message.text or d.top_message.caption or "[Media]"
            # Truncate
            if len(last_msg) > 35: last_msg = last_msg[:32] + "..."
            txt += f"{i}. <b>{html.escape(name)}</b>: <code>{html.escape(last_msg)}</code>\n"
            
        from Main.utils.file_helpers import get_user_button_style
        user_style = get_user_button_style(cb.from_user.id)
        await cb.message.edit(
            txt,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", f"recent_messages_menu_{index}_{page}", style=user_style)],
                [InlineKeyboardButton("🔙 Dashboard", f"session_info_{index}_{page}", style=user_style)]
            ]),
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        await cb.answer(f"❌ Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^gen_conf_global_stats_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def global_stats_handler(c: Client, cb: CallbackQuery):
    """Aggregate statistics across all active sessions"""
    index, page = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    await cb.answer("🌐 Calculating global stats...", show_alert=False)
    
    total_sessions = len(Altruix.clients)
    active_sessions = sum(1 for c in Altruix.clients if getattr(c, 'is_connected', False))
    
    # We could scan all, but that's heavy. Let's just use what we have in memory or quick sums if available.
    # For now, a summary of sessions and system info.
    import platform
    import time
    uptime = time.time() - Altruix.start_time
    # Format uptime
    days = int(uptime // (24 * 3600))
    hours = int((uptime % (24 * 3600)) // 3600)
    minutes = int((uptime % 3600) // 60)
    
    txt = (
        f"<b>🌐 Global Statistics</b>\n\n"
        f"• <b>Total Sessions:</b> <code>{total_sessions}</code>\n"
        f"• <b>Active Sessions:</b> <code>{active_sessions}</code>\n"
        f"• <b>System Architecture:</b> <code>{platform.machine()}</code>\n"
        f"• <b>OS:</b> <code>{platform.system()} {platform.release()}</code>\n"
        f"• <b>Uptime:</b> <code>{days}d {hours}h {minutes}m</code>\n"
        f"• <b>Core Modules:</b> <code>{len(Altruix.plugin_categories)}</code>\n"
    )
    
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)
    await cb.message.edit(
        txt,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Dashboard", f"session_info_{index}_{page}", style=user_style)],
            [InlineKeyboardButton("🔙 Main Stats", "sessions_stats", style=user_style)]
        ]),
        parse_mode=ParseMode.HTML
    )

# ====================== PLACEHOLDER HANDLERS FOR REMAINING BUTTONS ======================
# These show "Feature coming soon" instead of failing silently

PLACEHOLDER_PATTERNS = [
    r"^track_profile_start_", r"^check_limit_confirm_", r"^gen_conf_view_all_sessions_",
    r"^gen_conf_purge_msg_start_", r"^gpurgeme_menu_",
    r"^pml_menu_", r"^mnt_menu_", r"^joinl_menu_", r"^cmdl_menu_",
    r"^cmd_settings_menu_", r"^gen_conf_view_mentions_menu_",
    r"^join_log_group_", r"^startup_menu_", r"^laucreate_menu_", r"^privacy_menu_",
    r"^help_info_menu_", r"^eval_session_", r"^exec_session_", r"^custom_bot_menu_",
    r"^cache_log_menu_", r"^sudo_settings_menu_", r"^prefix_settings_menu_"
]

for pattern in PLACEHOLDER_PATTERNS:
    @Altruix.bot.on_callback_query(filters.regex(pattern))
    @iuser_check
    @log_errors
    async def placeholder_handler(c: Client, cb: CallbackQuery):
        """Placeholder for features under development"""
        await cb.answer("🚧 This feature is under development and will be available soon!", show_alert=True)
