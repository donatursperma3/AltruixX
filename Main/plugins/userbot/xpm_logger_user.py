# pm_logger_user.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.

from Main import Altruix
from pyrogram import Client, enums, filters
from pyrogram.types import (
    Message as RawMessage,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
    ReplyParameters
)
from Main.core.types.message import Message as AltruixMessage
from Main.core.decorators import log_errors
import os
import html
import logging
import time
import json
import asyncio
from pathlib import Path
import aiofiles
from datetime import datetime
import re
from collections import defaultdict
import psutil
from Main.utils.topic_utils import get_or_create_topic

# ─── LOGGER KHUSUS PLUGIN ───────────────────────────────────────────────


plugin_name = f"{os.path.basename(__file__)}"
__plugin_name__ = plugin_name if plugin_name else "pm_logger_user"

# --- LOGGER ---
logger = logging.getLogger("altruix.pm_logger_user")
logger.setLevel(logging.INFO)

PLUGIN_NAME = __plugin_name__ 
PLUGIN_VERSION = "1.3.0"  # ✅ Added message type filters
STORAGE_FILE = Path("pm_logger_user_settings.json")

# Settings Cache
PM_LOGGER_USER_DATA = {}
PM_LOG_CACHE = {}
REPLY_AS_MENTIONED_WAITING = {}
REPLY_FROM_ALL_ACCESSIBLE = True
USER_REPLY_COUNTS = defaultdict(lambda: defaultdict(int))
USER_REPLY_LIMIT = 5

# Message Type Filters
PM_LOGGER_FILTERS = {
    "from_user": {
        "text": True,
        "photo": True,
        "video": True,
        "document": True,
        "audio": True,
        "voice": True,
        "sticker": True,
        "animation": True,
        "video_note": True,
    },
    "from_bot": {
        "text": False,  # Don't log text from bots by default
        "photo": True,
        "video": True,
        "document": True,
        "audio": True,
        "voice": True,
        "sticker": True,
        "animation": True,
        "video_note": True,
    }
}

DEFAULT_REACTION_EMOJIS = ["👍", "❤️", "🔥", "🥰", "👏", "🎉"]
VALID_REACTION_EMOJIS = {
    "👍", "👎", "❤️", "🔥", "🥰", "👏", "😁", "🤔", "🤯", "😱", 
    "🤬", "😢", "🎉", "🤩", "🤮", "💩", "🙏", "👌", "🕊", "🤡",
    "🥱", "🥴", "😍", "🐳", "❤️‍🔥", "🌚", "🌭", "💯", "🤣", "⚡",
    "🍌", "🏆", "💔", "🤨", "😐", " strawberry", "🍾", "💋", "🖕", "😈",
    "😴", "😭", "🤓", "ghost", "👨‍💻", "👀", "🎃", "🙈", "😇", "😨",
    "🤝", "✍️", "🤗", "🫡", "🎅", "🎄", "☃️", "💅", "🤪", "🗿",
    "🆒", "💘", "🙉", "🦄", "😘", "💊", "🙊", "😎", "👾", "🤷‍♂️",
    "🤷", "🤷‍♀️", "😡"
}

def is_valid_emoji(emoji: str) -> bool:
    return emoji in VALID_REACTION_EMOJIS

async def load_settings():
    global PM_LOGGER_USER_DATA, PM_LOGGER_FILTERS, REPLY_FROM_ALL_ACCESSIBLE
    try:
        if STORAGE_FILE.exists():
            async with aiofiles.open(STORAGE_FILE, 'r', encoding='utf-8') as f:
                content = await f.read()
                if content.strip():
                    data = json.loads(content)
                    PM_LOGGER_USER_DATA = data.get("settings", {})
                    PM_LOGGER_FILTERS = data.get("filters", PM_LOGGER_FILTERS)
                    REPLY_FROM_ALL_ACCESSIBLE = data.get("reply_from_all_accessible", True)
    except Exception as e:
        logger.error(f"Failed to load PM Logger User settings: {e}")

async def save_settings():
    try:
        data = {
            "settings": PM_LOGGER_USER_DATA,
            "filters": PM_LOGGER_FILTERS,
            "reply_from_all_accessible": REPLY_FROM_ALL_ACCESSIBLE,
            "version": PLUGIN_VERSION
        }
        async with aiofiles.open(STORAGE_FILE, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, indent=2))
    except Exception as e:
        logger.error(f"Failed to save PM Logger User settings: {e}")

asyncio.create_task(load_settings())

@Altruix.register_on_cmd(
    ["pmlu"],
    cmd_help={
        "help": "Manage PM Logger settings and modes.",
        "usage": ".pmlu [on/off/mode/replyall/filter]",
        "example": ".pmlu on | .pmlu mode bot | .pmlu replyall off",
        "user_args": {
            "on": "Enable PM Logger User",
            "off": "Disable PM Logger User",
            "mode <bot/user/both>": "Set logging mode (bot only, user only, or both)",
            "replyall <on/off>": "Enable/disable reply from all feature",
            "filter": "Show current message type filters",
            "filter <source> <type> <on/off>": "Toggle specific filter (e.g., .pmlu filter bot text off)",
        },
        "detail": (
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "💬 **PM LOGGER USER COMMANDS**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "• `.pmlu on` : Aktifkan pencatatan PM Userbot.\n"
            "• `.pmlu off`: Nonaktifkan pencatatan PM Userbot.\n\n"
            "🛠 **Logger Mode:**\n"
            "• `.pmlu mode user`: Catat PM masuk ke User saja.\n"
            "• `.pmlu mode bot` : Catat PM masuk ke Bot saja.\n"
            "• `.pmlu mode both `: Catat PM dari keduanya (Default).\n\n"
            "👥 **Interactive Tools:**\n"
            "• `.pmlu replyall on` : Izinkan tombol 'Reply From All'.\n"
            "• `.pmlu replyall off`: Sembunyikan tombol 'Reply From All'.\n\n"
            "📊 **Filter Type Pesan:**\n"
            "• `.pmlu filter`: Lihat filter tipe pesan saat ini.\n"
            "• `.pmlu filter <user/bot> <tipe> <on/off>`: Atur filter spesifik.\n\n"
            "📊 **General Status:**\n"
            "• `.pmlstatus`: Lihat detail status seluruh logger (User & Bot)."
        )
    },
    group_only=False,
    requires_input=False,
)
@log_errors
async def pmlu_settings_handler(c: Client, m: AltruixMessage):
    global REPLY_FROM_ALL_ACCESSIBLE
    user_input = (m.user_input or "").lower().strip()
    
    if not user_input:
        is_enabled = PM_LOGGER_USER_DATA.get("enabled", False)
        # PERBAIKAN: Definisikan variabel status berdasarkan is_enabled
        status = "ENABLED ✅" if is_enabled else "DISABLED ❌"
        mode = PM_LOGGER_USER_DATA.get("mode", "both").upper()
        ra_status = "ENABLED ✅" if REPLY_FROM_ALL_ACCESSIBLE else "DISABLED ❌"
        log_chat = Altruix.log_chat or "Not Configured ⚠️"
        
        # Check if bot can actually send to log_chat
        bot_access = "Checking..."
        if Altruix.log_chat:
            try:
                await Altruix.bot.get_chat(Altruix.log_chat)
                bot_access = "OK ✅"
            except Exception as e:
                bot_access = f"FAILED ❌ ({str(e)})"
        else:
            bot_access = "N/A"

        res = (
            f"📊 **PM Logger User Status Detail**\n"
            f"• **Status:** {status}\n"
            f"• **Logger Mode:** `{mode}`\n"
            f"• **Reply From All:** {ra_status}\n"
            f"• **Log Group ID:** ` {log_chat} `\n"
            f"• **Bot Access:** {bot_access}\n\n"
            f"Commands:\n"
            f"• `.pmlu on/off` - Global Toggle\n"
            f"• `.pmlu mode user/bot/both` - Set Mode\n"
            f"• `.pmlu replyall on/off` - Toggle ReplyAll\n"
            f"• `.pmlu filter` - View Filters"
        )
        return await m.reply_msg(res)

    if user_input.startswith("filter"):
        args = user_input.split()
        if len(args) == 1:
            # Show current filters
            res = "📑 **PM Logger Message Type Filters**\n\n"
            for source in ["from_user", "from_bot"]:
                label = "👤 **User Messages**" if source == "from_user" else "🤖 **Bot Messages**"
                res += f"{label}:\n"
                for m_type, allowed in PM_LOGGER_FILTERS[source].items():
                    status_icon = "✅" if allowed else "❌"
                    res += f"  {status_icon} `{m_type}`\n"
                res += "\n"
            res += "Usage: `.pmlu filter <user/bot> <type> <on/off>`"
            return await m.reply_msg(res)
        
        if len(args) == 4:
            source_arg = args[1].lower()
            type_arg = args[2].lower()
            state_arg = args[3].lower()
            
            source_key = "from_user" if source_arg == "user" else "from_bot" if source_arg == "bot" else None
            if not source_key:
                return await m.reply_msg("❌ **Invalid Source!** Use `user` or `bot`.")
                
            if type_arg not in PM_LOGGER_FILTERS[source_key]:
                return await m.reply_msg(f"❌ **Invalid Type!** Valid types: `{', '.join(PM_LOGGER_FILTERS[source_key].keys())}`")
                
            new_state = True if state_arg in ["on", "yes", "true"] else False if state_arg in ["off", "no", "false"] else None
            if new_state is None:
                return await m.reply_msg("❌ **Invalid State!** Use `on` or `off`.")
                
            PM_LOGGER_FILTERS[source_key][type_arg] = new_state
            await save_settings()
            status_icon = "✅" if new_state else "❌"
            return await m.reply_msg(f"{status_icon} **Filter Updated:** `{type_arg}` from `{source_arg}` is now **{'ENABLED' if new_state else 'DISABLED'}**")
            
        return await m.reply_msg("❌ **Invalid Arguments!**\nUsage: `.pmlu filter <user/bot> <type> <on/off>`")

    if user_input.startswith("mode"):
        arg = user_input.replace("mode", "").strip()
        if arg in ["user", "bot", "both"]:
            PM_LOGGER_USER_DATA["mode"] = arg
            await save_settings()
            return await m.reply_msg(f"✅ **PM Logger mode set to: `{arg.upper()}`**")
        else:
            return await m.reply_msg("❌ **Invalid Mode!** Use `user`, `bot`, or `both`.")

    if user_input.startswith("replyall"):
        arg = user_input.replace("replyall", "").strip()
        if arg in ["on", "yes"]:
            REPLY_FROM_ALL_ACCESSIBLE = True
            msg_text = "✅ **Reply From All (PM) is now ACCESSIBLE**"
        elif arg in ["off", "no"]:
            REPLY_FROM_ALL_ACCESSIBLE = False
            msg_text = "❌ **Reply From All (PM) is now RESTRICTED**"
        else:
            return await m.reply_msg("Usage: `.pmlu replyall on/off`")
        await save_settings()
        return await m.reply_msg(msg_text)

    if user_input in ["on", "yes"]:
        PM_LOGGER_USER_DATA["enabled"] = True
        status = "ENABLED ✅"
    elif user_input in ["off", "no"]:
        PM_LOGGER_USER_DATA["enabled"] = False
        status = "DISABLED ❌"
    else:
        return await m.reply_msg("INVALID_INPUT")
    
    await save_settings()
    await m.reply_msg(f"**PM Logger User (All Accounts) is now {status}**")

@Altruix.register_on_cmd(
    ["pmlstatus", "pmlustatus"],
    cmd_help={
        "help": "Check status of PM Logger User and Bot.",
        "usage": ".pmlstatus",
        "example": ".pmlstatus",
        "detail": "Lihat status aktif/nonaktif dan konfigurasi dari PM Logger User serta PM Logger Bot secara bersamaan."
    },
    group_only=False,
    requires_input=False,
)
@log_errors
async def pml_status_unified_handler(c: Client, m: AltruixMessage):
    u_enabled = PM_LOGGER_USER_DATA.get("enabled", False)
    mode = PM_LOGGER_USER_DATA.get("mode", "both")
    
    # Bot status (import from the other plugin)
    try:
        from Main.plugins.bot.pm_logger_bot import PM_LOGGER_BOT_DATA as B_DATA
        b_enabled = B_DATA.get("enabled", False)
    except:
        b_enabled = False
    
    # Calculate effective status
    user_active = u_enabled and mode in ["user", "both"]
    bot_active = b_enabled and mode in ["bot", "both"]
    
    u_status = "✅ ACTIVE" if user_active else "❌ INACTIVE"
    b_status = "✅ ACTIVE" if bot_active else "❌ INACTIVE"
    pml_global = "✅ ACTIVE" if (user_active or bot_active) else "❌ INACTIVE"
    ra_status = "✅ ACTIVE" if REPLY_FROM_ALL_ACCESSIBLE else "❌ INACTIVE"

    log_chat = Altruix.log_chat or "⚠️ Not Configured"
    
    res = (
        f"🛡️ **PM LOGGER DETAILED STATUS**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Global PM Logger:** {pml_global}\n"
        f"• **Reply From All:** {ra_status}\n\n"
        f"📊 **Sub-Logger Status:**\n"
        f"• **Logger From User:** {u_status}\n"
        f"• **Logger From Bot:** {b_status}\n\n"
        f"⚙️ **Configuration:**\n"
        f"• **Current Mode:** `{mode.upper()}`\n"
        f"• **Log Group:** ` {log_chat} `\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Tip: Gunakan `.pmlu mode` untuk mengubah sumber logger."
    )
    await m.reply_msg(res)


@Altruix.on_message(
    filters.private & ~filters.me, group=0, bot_mode_unsupported=True
)
@log_errors
async def pm_logger_user_handler(c: Client, m: RawMessage):
    """Log incoming private messages."""
    try:
        # Debug Log
        # logger.debug(f"PMLU triggered for msg {m.id} in chat {m.chat.id}")
        
        if not PM_LOGGER_USER_DATA.get("enabled", False):
            return

        mode = PM_LOGGER_USER_DATA.get("mode", "both")
        if mode == "bot":
            return

        if not Altruix.log_chat:
            # logger.warning("PMLU: Altruix.log_chat is not set!")
            return

        sender = m.from_user
        if not sender or sender.is_self:
            return

        sender_id = sender.id
        sender_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip() or "Unknown"
        sender_username = f"@{sender.username}" if sender.username else "No Username"
        sender_hyperlink = f'<a href="tg://user?id={sender_id}">{html.escape(sender_name)}</a>'
        
        msg_type_str = "text"
        if m.service:
            if m.service == enums.MessageServiceType.PHONE_CALL_ENDED:
                msg_type_str = "phone_call"
                msg_text = "📞 Phone Call Ended"
            else:
                return # Skip other service messages
        elif m.media:
            msg_type_str = m.media.value
            if msg_type_str == "animation": msg_type_str = "video"
            
        log_time = m.date.strftime("%Y-%m-%d %H:%M:%S")
        msg_text = m.text or m.caption or msg_text or "[Media]"

        # ✅ NEW: Message Type Filter Check (Bot vs User)
        is_bot = m.from_user.is_bot if m.from_user else False
        filter_key = "from_bot" if is_bot else "from_user"
        
        # Determine message type for filtering
        filter_msg_type = None
        if not m.media and m.text:
            filter_msg_type = "text"
        elif m.photo:
            filter_msg_type = "photo"
        elif m.video:
            filter_msg_type = "video"
        elif m.document:
            filter_msg_type = "document"
        elif m.audio:
            filter_msg_type = "audio"
        elif m.voice:
            filter_msg_type = "voice"
        elif m.sticker:
            filter_msg_type = "sticker"
        elif m.animation:
            filter_msg_type = "animation"
        elif m.video_note:
            filter_msg_type = "video_note"
        
        # Check if this message type is allowed
        if filter_msg_type and not PM_LOGGER_FILTERS.get(filter_key, {}).get(filter_msg_type, True):
            return  # Skip logging this message type

        is_restricted = getattr(m, "has_protected_content", False)
        
        # Get file size if restricted
        size_str = ""
        if is_restricted:
            size = 0
            if m.document: size = m.document.file_size
            elif m.photo: size = m.photo.file_size
            elif m.video: size = m.video.file_size
            elif m.audio: size = m.audio.file_size
            elif m.voice: size = m.voice.file_size
            elif m.video_note: size = m.video_note.file_size
            elif m.animation: size = m.animation.file_size
            
            if size > 0:
                if size < 1024: size_str = f" ({size} B)"
                elif size < 1024*1024: size_str = f" ({size/1024:.2f} KB)"
                else: size_str = f" ({size/(1024*1024):.2f} MB)"

        log_content = (
            f"👤 <b>New PM Received (User)</b>\n"
        )
        if is_restricted:
            log_content += f"⚠️ <b>ini adalah restrict content dengan ukuran{size_str}</b>\n\n"
        else:
            log_content += "\n"

        log_content += (
            f"• <b>From:</b> {sender_hyperlink}\n"
            f"• <b>User ID:</b> <code>{sender_id}</code>\n"
            f"• <b>Username:</b> {sender_username}\n"
            f"• <b>To Account:</b> {c.me.mention}\n"
            f"• <b>Time:</b> <code>{log_time}</code>\n"
            f"• <b>Type:</b> <code>{msg_type_str.upper()}</code>\n"
            f"• <b>Message:</b>\n<blockquote>{html.escape(str(msg_text)[:1000])}</blockquote>"
        )

        # ─── BUTTONS ───
        # Menu Ringkas/Kompak secara default
        keyboard = [
            [
                InlineKeyboardButton("⚙️ Show Settings Menu", callback_data=f"pmlu_toggle_full_{m.chat.id}_{m.id}_{c.me.id}"),
                InlineKeyboardButton("🔗 Chat with User", url=f"tg://user?id={sender_id}")
            ]
        ]
        
        if is_restricted:
            keyboard[0].insert(0, InlineKeyboardButton("🚀 Force/Bypass Forward", callback_data=f"pmlu_force_fwd_{m.chat.id}_{m.id}_{c.me.id}"))

        if not REPLY_FROM_ALL_ACCESSIBLE:
            # Remove Reply From All button row or just that button
            keyboard = [r for r in keyboard if not any(b.text == "👥 Reply From All" for b in r)]

        # Get topic if any (use userbot to create if needed)
        topic_id = await get_or_create_topic(Altruix.bot, Altruix.log_chat, "pm logger", userbot_client=c)

        # Forward message
        try:
            fwd_msg = await c.forward_messages(Altruix.log_chat, m.chat.id, m.id, message_thread_id=topic_id)
        except Exception as e:
            logger.debug(f"PMLU Forward failed: {e}")
            fwd_msg = None
        
        # Send Detailed Info as a reply to the forwarded message
        sent_log = await Altruix.bot.send_message(
            Altruix.log_chat,
            log_content,
            parse_mode=enums.ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard),
            reply_to_message_id=fwd_msg.id if fwd_msg else None,
            message_thread_id=topic_id
        )
        
        # Cache for recovery
        PM_LOG_CACHE[f"{m.chat.id}_{m.id}"] = {
            "client_id": c.me.id,
            "log_msg_id": sent_log.id,
            "chat_id": m.chat.id,
            "msg_id": m.id,
            "last_reply_id": None
        }

    except Exception as e:
        logger.error(f"Error in PM Logger User: {e}")

@Altruix.on_edited_message(
    filters.private & ~filters.me, group=0, bot_mode_unsupported=True
)
@log_errors
async def pm_logger_user_edit_handler(c: Client, m: RawMessage):
    """Update log when a message is edited."""
    try:
        if not PM_LOGGER_USER_DATA.get("enabled", False):
            return

        msg_key = f"{m.chat.id}_{m.id}"
        cache = PM_LOG_CACHE.get(msg_key)
        if not cache:
            return

        log_msg_id = cache.get("log_msg_id")
        if not log_msg_id:
            return

        sender = m.from_user
        sender_id = sender.id
        sender_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip() or "Unknown"
        sender_username = f"@{sender.username}" if sender.username else "No Username"
        sender_hyperlink = f'<a href="tg://user?id={sender_id}">{html.escape(sender_name)}</a>'
        
        msg_text = m.text or m.caption or "[No text/media caption]"
        msg_type = m.media.value if m.media else "text"
        
        log_time = m.date.strftime("%Y-%m-%d %H:%M:%S")
        edit_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        log_content = (
            f"👤 <b>New PM Received (User) [EDITED]</b>\n\n"
            f"• <b>From:</b> {sender_hyperlink}\n"
            f"• <b>User ID:</b> <code>{sender_id}</code>\n"
            f"• <b>Username:</b> {sender_username}\n"
            f"• <b>To Account:</b> {c.me.mention}\n"
            f"• <b>Time Original:</b> <code>{log_time}</code>\n"
            f"• <b>Time Edited:</b> <code>{edit_time}</code>\n"
            f"• <b>Type:</b> <code>{msg_type}</code>\n"
            f"• <b>New Message:</b>\n<blockquote>{html.escape(str(msg_text)[:1000])}</blockquote>"
        )

        # Preserve the reply_markup by fetching it
        try:
            old_msg = await Altruix.bot.get_messages(Altruix.log_chat, log_msg_id)
            markup = old_msg.reply_markup if old_msg else None
        except:
            markup = None

        await Altruix.bot.edit_message_text(
            Altruix.log_chat,
            log_msg_id,
            log_content,
            parse_mode=enums.ParseMode.HTML,
            reply_markup=markup
        )
        # Actually we need to keep the original reply_markup
        # But we can't easily get it without fetching the message again
        # Let's just edit text first or try to re-fetch if needed.
        # Most of the time we can just assume the buttons are the same.
        
    except Exception as e:
        logger.error(f"Error in PM Logger User Edit: {e}")

# Callback Handlers for PMLU
@Altruix.bot.on_callback_query(filters.regex(r"^pmlu_react_"))
@log_errors
async def pmlu_react_callback(c: Client, cb: CallbackQuery):
    try:
        data = cb.data.split("_")
        chat_id, msg_id, client_id, emoji = int(data[2]), int(data[3]), int(data[4]), data[5]
        
        target_client = None
        for client in Altruix.clients:
            if client.me and client.me.id == client_id:
                target_client = client
                break
        
        if not target_client:
            await cb.answer("❌ Client session not found.", show_alert=True)
            return
            
        await target_client.send_reaction(chat_id, msg_id, emoji)
        await cb.answer(f"✅ Reacted with {emoji}")
    except Exception as e:
        await cb.answer(f"❌ Error: {str(e)}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlu_unreact_"))
@log_errors
async def pmlu_unreact_callback(c: Client, cb: CallbackQuery):
    try:
        data = cb.data.split("_")
        chat_id, msg_id, client_id = int(data[2]), int(data[3]), int(data[4])
        
        target_client = None
        for client in Altruix.clients:
            if client.me and client.me.id == client_id:
                target_client = client
                break
        
        if not target_client:
            await cb.answer("❌ Client session not found.", show_alert=True)
            return
            
        await target_client.send_reaction(chat_id, msg_id, None)
        await cb.answer("✅ Reaction removed")
    except Exception as e:
        await cb.answer(f"❌ Error: {str(e)}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlu_save_"))
@log_errors
async def pmlu_save_callback(c: Client, cb: CallbackQuery):
    try:
        data = cb.data.split("_")
        chat_id, msg_id, client_id = int(data[2]), int(data[3]), int(data[4])
        
        target_client = None
        for client in Altruix.clients:
            if client.me and client.me.id == client_id:
                target_client = client
                break
        
        if not target_client or not target_client.is_connected:
            return await cb.answer("❌ Account not connected/found.", show_alert=True)
            
        # Forward message again to log group
        await target_client.forward_messages(Altruix.log_chat, chat_id, msg_id)
        await cb.answer("✅ Message forwarded again to log group!", show_alert=True)
    except Exception as e:
        logger.error(f"PMLU Save callback error: {e}")

@Altruix.bot.on_callback_query(filters.regex(r"^pmlu_force_fwd_"))
@log_errors
async def pmlu_force_fwd_callback(c: Client, cb: CallbackQuery):
    try:
        data = cb.data.split("_")
        # pmlu_force_fwd_{chat_id}_{msg_id}_{client_id}
        chat_id, msg_id, client_id = int(data[3]), int(data[4]), int(data[5])
        
        target_client = None
        for client in Altruix.clients:
            if client.me and client.me.id == client_id:
                target_client = client
                break
        
        if not target_client:
            return await cb.answer("❌ Account not connected/found.", show_alert=True)
            
        await cb.answer("📥 Mendownload content...", show_alert=False)
        
        # Download using the specific account that received it
        # Restricted content often requires the specific account to download
        try:
            msg = await target_client.get_messages(chat_id, msg_id)
            if not msg or not msg.media:
                return await cb.answer("❌ Media tidak ditemukan.", show_alert=True)
            
            file_path = await target_client.download_media(msg)
        except Exception as e:
            logger.error(f"PMLU Download failed: {e}")
            return await cb.answer(f"❌ Gagal download: {str(e)[:50]}", show_alert=True)

        if not file_path:
            return await cb.answer("❌ Gagal mendownload content (file_path empty).", show_alert=True)
            
        # Update text to show uploading
        try:
            old_text = cb.message.text.html
            await cb.edit_message_text(f"{old_text}\n\n📤 **Uploading bypassed content...**", parse_mode=enums.ParseMode.HTML)
        except: pass
        
        # Get topic
        topic_id = await get_or_create_topic(Altruix.bot, Altruix.log_chat, "pm logger", userbot_client=target_client)
        
        # Upload using the userbot to the log group
        await target_client.send_document(
            Altruix.log_chat, 
            file_path, 
            caption=f"✅ **Bypassed Restrict Content**\nFrom account: {target_client.me.mention}",
            message_thread_id=topic_id
        )
        
        # Cleanup
        if os.path.exists(file_path):
            os.remove(file_path)
            
        await cb.answer("✅ Berhasil mendownload dan mengupload ulang ke group log!", show_alert=True)
    except Exception as e:
        logger.error(f"PMLU Force Forward error: {e}")
        await cb.answer(f"❌ Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlu_others_"))
@log_errors
async def pmlu_others_callback(c: Client, cb: CallbackQuery):
    try:
        data = cb.data.split("_")
        chat_id, msg_id, client_id = int(data[2]), int(data[3]), int(data[4])
        
        # Build emoji keyboard (8 per row)
        keyboard = []
        emojis = list(VALID_REACTION_EMOJIS)
        for i in range(0, len(emojis), 8):
            row = [
                InlineKeyboardButton(e, callback_data=f"pmlu_react_{chat_id}_{msg_id}_{client_id}_{e}")
                for e in emojis[i:i+8]
            ]
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=f"pmlu_back_{chat_id}_{msg_id}_{client_id}")])
        
        await cb.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        await cb.answer("Select a reaction emoji")
    except Exception as e:
        await cb.answer(f"❌ Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlu_back_"))
@log_errors
async def pmlu_back_callback(c: Client, cb: CallbackQuery):
    try:
        data = cb.data.split("_")
        chat_id, msg_id, client_id = int(data[2]), int(data[3]), int(data[4])
        
        # Re-build original keyboard
        reaction_btns = [
            InlineKeyboardButton(emoji, callback_data=f"pmlu_react_{chat_id}_{msg_id}_{client_id}_{emoji}")
            for emoji in DEFAULT_REACTION_EMOJIS
        ]
        
        keyboard = [
            reaction_btns[:3],
            reaction_btns[3:6],
            [
                InlineKeyboardButton("➕ Others", callback_data=f"pmlu_others_{chat_id}_{msg_id}_{client_id}"),
                InlineKeyboardButton("🗑️ Remove React", callback_data=f"pmlu_unreact_{chat_id}_{msg_id}_{client_id}")
            ],
            [
                InlineKeyboardButton("🗨️ Reply", callback_data=f"pmlu_reply_{chat_id}_{msg_id}_{client_id}"),
                InlineKeyboardButton("💾 Save to Log", callback_data=f"pmlu_save_{chat_id}_{msg_id}_{client_id}")
            ],
            [
                InlineKeyboardButton("👥 Reply From All", callback_data=f"pmlu_replyall_{chat_id}_{msg_id}_{client_id}"),
                InlineKeyboardButton("🗑️ Unsend", callback_data=f"pmlu_unsend_{chat_id}_{msg_id}_{client_id}")
            ],
            [InlineKeyboardButton("🔗 Chat with User", url=f"tg://user?id={chat_id}")] 
        ]
        
        if not REPLY_FROM_ALL_ACCESSIBLE:
             keyboard = [r for r in keyboard if not any(b.text == "👥 Reply From All" for b in r)]

        await cb.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        await cb.answer(f"❌ Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlu_replyall_"))
@log_errors
async def pmlu_replyall_callback(c: Client, cb: CallbackQuery):
    try:
        if not REPLY_FROM_ALL_ACCESSIBLE:
            return await cb.answer("❌ Fitur ini sedang dinonaktifkan.", show_alert=True)

        data = cb.data.split("_")
        chat_id, msg_id, client_id = int(data[2]), int(data[3]), int(data[4])
        msg_key = f"{chat_id}_{msg_id}"
        
        user_id = cb.from_user.id
        today = datetime.now().strftime("%Y%m%d")
        if USER_REPLY_COUNTS[user_id][today] >= USER_REPLY_LIMIT:
             return await cb.answer(f"❌ Limit harian tercapai ({USER_REPLY_LIMIT}x).", show_alert=True)

        waiting_id = f"pmlu_ra_{int(time.time())}_{cb.id}"
        REPLY_AS_MENTIONED_WAITING[waiting_id] = {
            "chat_id": chat_id,
            "message_id": msg_id,
            "client_id": client_id,
            "user_id": user_id,
            "instruction_msg_id": None,
            "is_reply_all": True,
            "msg_key": msg_key
        }
        
        instr = await cb.message.reply(
            "👥 <b>Reply From All (PM)</b>\n\n"
            "Silakan balas pesan ini dengan teks atau media.\n"
            "Pesan akan dikirim dari <b>SEMUA</b> akun Anda ke user ini.",
            parse_mode=enums.ParseMode.HTML,
            reply_parameters=ReplyParameters(message_id=cb.message.id)
        )
        REPLY_AS_MENTIONED_WAITING[waiting_id]["instruction_msg_id"] = instr.id
        await cb.answer("Silakan kirim balasan Anda.")
        
        # Debug log
        logger.info(f"PMLU: Waiting for reply on msg {instr.id} for waiting_id {waiting_id}")
    except Exception as e:
        await cb.answer(f"❌ Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlu_reply_"))
@log_errors
async def pmlu_reply_callback(c: Client, cb: CallbackQuery):
    try:
        data = cb.data.split("_")
        chat_id, msg_id, client_id = int(data[2]), int(data[3]), int(data[4])
        msg_key = f"{chat_id}_{msg_id}"
        
        waiting_id = f"pmlu_r_{int(time.time())}_{cb.id}"
        REPLY_AS_MENTIONED_WAITING[waiting_id] = {
            "chat_id": chat_id,
            "message_id": msg_id,
            "client_id": client_id,
            "user_id": cb.from_user.id,
            "instruction_msg_id": None,
            "is_reply_all": False,
            "msg_key": msg_key
        }
        
        instr = await cb.message.reply(
            "🗨️ <b>Reply (PM)</b>\n\n"
            "Silakan balas pesan ini dengan teks atau media.\n"
            "Pesan akan dikirim dari akun yang bersangkutan ke user ini.",
            parse_mode=enums.ParseMode.HTML,
            reply_parameters=ReplyParameters(message_id=cb.message.id)
        )
        REPLY_AS_MENTIONED_WAITING[waiting_id]["instruction_msg_id"] = instr.id
        await cb.answer("Silakan kirim balasan Anda.")
    except Exception as e:
        await cb.answer(f"❌ Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlu_unsend_"))
@log_errors
async def pmlu_unsend_callback(c: Client, cb: CallbackQuery):
    try:
        data = cb.data.split("_")
        chat_id, msg_id, client_id = int(data[2]), int(data[3]), int(data[4])
        msg_key = f"{chat_id}_{msg_id}"
        
        cache = PM_LOG_CACHE.get(msg_key, {})
        last_replies = cache.get("last_replies", []) # List of (client_id, msg_id)
        
        if not last_replies:
            return await cb.answer("❌ Tidak ada balasan yang terekam untuk di-unsend.", show_alert=True)
            
        unsend_count = 0
        for cid, mid in last_replies:
            target_client = None
            for client in Altruix.clients:
                if client.me and client.me.id == cid:
                    target_client = client
                    break
            if target_client:
                try:
                    await target_client.delete_messages(chat_id, mid)
                    unsend_count += 1
                except:
                    pass
        
        # Clear replies from cache
        PM_LOG_CACHE[msg_key]["last_replies"] = []
        
        await cb.answer(f"✅ Berhasil unsend {unsend_count} pesan.", show_alert=True)
    except Exception as e:
        await cb.answer(f"❌ Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlu_toggle_(full|compact)_"))
@log_errors
async def pmlu_toggle_callback(c: Client, cb: CallbackQuery):
    try:
        data = cb.data.split("_")
        mode, chat_id, msg_id, client_id = data[2], int(data[3]), int(data[4]), int(data[5])
        
        if mode == "full":
            reaction_btns = [
                InlineKeyboardButton(emoji, callback_data=f"pmlu_react_{chat_id}_{msg_id}_{client_id}_{emoji}")
                for emoji in DEFAULT_REACTION_EMOJIS
            ]
            keyboard = [
                reaction_btns[:3],
                reaction_btns[3:6],
                [
                    InlineKeyboardButton("➕ Others", callback_data=f"pmlu_others_{chat_id}_{msg_id}_{client_id}"),
                    InlineKeyboardButton("🗑️ Remove React", callback_data=f"pmlu_unreact_{chat_id}_{msg_id}_{client_id}")
                ],
                [
                    InlineKeyboardButton("🗨️ Reply", callback_data=f"pmlu_reply_{chat_id}_{msg_id}_{client_id}"),
                    InlineKeyboardButton("💾 Save", callback_data=f"pmlu_save_{chat_id}_{msg_id}_{client_id}")
                ],
                [
                    InlineKeyboardButton("🚫 Block", callback_data=f"pmlu_block_{chat_id}_{client_id}"),
                    InlineKeyboardButton("✅ Unblock", callback_data=f"pmlu_unblock_{chat_id}_{client_id}")
                ],
                [
                    InlineKeyboardButton("👥 Reply All", callback_data=f"pmlu_replyall_{chat_id}_{msg_id}_{client_id}"),
                    InlineKeyboardButton("🗑️ Unsend", callback_data=f"pmlu_unsend_{chat_id}_{msg_id}_{client_id}")
                ],
                [
                    InlineKeyboardButton("⚙️ Hide Settings Menu", callback_data=f"pmlu_toggle_compact_{chat_id}_{msg_id}_{client_id}"),
                    InlineKeyboardButton("🔗 Chat", url=f"tg://user?id={chat_id}")
                ]
            ]
            if not REPLY_FROM_ALL_ACCESSIBLE:
                keyboard = [r for r in keyboard if not any(b.text == "👥 Reply All" for b in r)]
        else:
            keyboard = [[
                InlineKeyboardButton("⚙️ Show Settings Menu", callback_data=f"pmlu_toggle_full_{chat_id}_{msg_id}_{client_id}"),
                InlineKeyboardButton("🔗 Chat with User", url=f"tg://user?id={chat_id}")
            ]]
            
        await cb.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        await cb.answer()
    except Exception as e:
        await cb.answer(f"❌ Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlu_(block|unblock)_"))
@log_errors
async def pmlu_block_unblock_callback(c: Client, cb: CallbackQuery):
    try:
        data = cb.data.split("_")
        action, chat_id, client_id = data[1], int(data[2]), int(data[3])
        
        target_client = None
        for client in Altruix.clients:
            if client.me and client.me.id == client_id:
                target_client = client
                break
        
        if not target_client:
            return await cb.answer("❌ Client session not found.", show_alert=True)
            
        if action == "block":
            await target_client.block_user(chat_id)
            await cb.answer("🚫 User blocked successfully.", show_alert=True)
        else:
            await target_client.unblock_user(chat_id)
            await cb.answer("✅ User unblocked successfully.", show_alert=True)
    except Exception as e:
        await cb.answer(f"❌ Error: {e}", show_alert=True)

@Altruix.bot.on_message(filters.chat(Altruix.log_chat) & filters.reply, group=3)
@log_errors
async def handle_pmlu_input(c: Client, m: RawMessage):
    if not m.reply_to_message: return
    
    waiting_id = None
    for wid, data in REPLY_AS_MENTIONED_WAITING.items():
        if data.get("instruction_msg_id") == m.reply_to_message.id:
            waiting_id = wid
            break
            
    if not waiting_id:
        # Check if it was a reply to any bot message in log chat? No, better be specific.
        return
    
    # Process the input
    logger.info(f"PMLU: Processing input for waiting_id {waiting_id}")
    
    data = REPLY_AS_MENTIONED_WAITING.pop(waiting_id)
    chat_id = data["chat_id"]
    msg_id = data["message_id"]
    msg_key = data["msg_key"]
    
    sent_count = 0
    errors = []
    
    if msg_key not in PM_LOG_CACHE:
        PM_LOG_CACHE[msg_key] = {"last_replies": []}
    elif "last_replies" not in PM_LOG_CACHE[msg_key]:
        PM_LOG_CACHE[msg_key]["last_replies"] = []

    if data["is_reply_all"]:
        # Send from all userbots
        for client in Altruix.clients:
            if client.is_connected:
                try:
                    # Use client.copy_message to ensure it's sent from the userbot
                    sent = await client.copy_message(chat_id, m.chat.id, m.id, reply_to_message_id=msg_id)
                    sent_count += 1
                    PM_LOG_CACHE[msg_key]["last_replies"].append((client.me.id, sent.id))
                except Exception as e:
                    errors.append(str(e))
        
        today = datetime.now().strftime("%Y%m%d")
        USER_REPLY_COUNTS[data["user_id"]][today] += 1
    else:
        # Send from specific account
        target_client = None
        if Altruix.bot and Altruix.bot.me and Altruix.bot.me.id == data["client_id"]:
            target_client = Altruix.bot
        else:
            for client in Altruix.clients:
                if client.me and client.me.id == data["client_id"]:
                    target_client = client
                    break
        
        if target_client:
            try:
                # Use target_client.copy_message
                sent = await target_client.copy_message(chat_id, m.chat.id, m.id, reply_to_message_id=msg_id)
                sent_count = 1
                PM_LOG_CACHE[msg_key]["last_replies"].append((target_client.me.id, sent.id))
            except Exception as e:
                errors.append(str(e))
        else:
            errors.append("Account not found or offline.")
    
    res_msg = f"✅ Berhasil mengirim dari {sent_count} akun."
    if errors:
        res_msg += f"\n❌ Gagal: {len(errors)} akun."
    
    await m.reply(res_msg)

# Cleanup task for cache
async def cleanup_pmlu_cache():
    while True:
        if len(PM_LOG_CACHE) > 1000:
            # Simple cleanup: remove oldest 200
            keys = list(PM_LOG_CACHE.keys())[:200]
            for k in keys:
                PM_LOG_CACHE.pop(k, None)
        await asyncio.sleep(3600)

asyncio.create_task(cleanup_pmlu_cache())

# ==================== RESOURCE MONITOR ====================
async def resource_monitor():
    """Monitor system resources and alert if usage exceeds 90%."""
    alert_triggered = False
    while True:
        try:
            cpu_usage = psutil.cpu_percent(interval=1)
            ram_usage = psutil.virtual_memory().percent
            
            if (cpu_usage > 90 or ram_usage > 90) and not alert_triggered:
                log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))
                alert_text = (
                    "🚨 <b>SYSTEM OVERLOAD ALERT</b> 🚨\n\n"
                    f"⚠️ <b>CPU Usage:</b> <code>{cpu_usage}%</code>\n"
                    f"⚠️ <b>RAM Usage:</b> <code>{ram_usage}%</code>\n\n"
                    "Please check your server immediately to prevent crashes."
                )
                try:
                    await Altruix.bot.send_message(log_chat_id, alert_text)
                    alert_triggered = True
                except: pass
            elif cpu_usage < 80 and ram_usage < 80:
                alert_triggered = False
                
        except Exception as e:
            logger.error(f"Resource monitor error: {e}")
            
        await asyncio.sleep(60)

asyncio.create_task(resource_monitor())

# ==================== LOG SUKSES LOADING ====================
try:
    Altruix.log(f"[DEBUG] Loaded → {__plugin_name__} {PLUGIN_VERSION}", level=20)
except Exception as e:
    logger.info(f"[DEBUG] Loaded → {__plugin_name__} {PLUGIN_VERSION}")