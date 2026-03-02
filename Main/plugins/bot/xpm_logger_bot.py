# pm_logger_bot.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.

from Main import Altruix
from Main.utils.essentials import Essentials
from pyrogram import Client, enums, filters
from pyrogram.types import (
    Message as RawMessage,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyParameters,
    CallbackQuery
)
from Main.core.types.message import Message as AltruixMessage
from Main.core.decorators import log_errors, iuser_check
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
from Main.utils.topic_utils import get_or_create_topic
from Main.utils.file_helpers import get_db_path

# ─── LOGGER KHUSUS PLUGIN ───────────────────────────────────────────────


plugin_name = f"{os.path.basename(__file__)}"
__plugin_name__ = plugin_name if plugin_name else "pm_logger_bot"

# --- LOGGER ---
logger = logging.getLogger("altruix.pm_logger_bot")
logger.setLevel(logging.INFO)

PLUGIN_NAME = __plugin_name__ 
PLUGIN_VERSION = "1.3.25"  # ✅ Improved filtering logic consistency
STORAGE_FILE = Path(get_db_path("pm_logger_bot_settings.json"))

# Settings Cache
PM_LOGGER_BOT_DATA = {}
REPLY_FROM_ALL_ACCESSIBLE = True
REPLY_ACCESS_MODE = "sudo"  # Default: sudo users + owner
USER_REPLY_COUNTS = defaultdict(lambda: defaultdict(int))
USER_REPLY_LIMIT = 5

# Message Type Filters (same as user logger)
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
        "text": False,
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
    "🍌", "🏆", "💔", "🤨", "😐", "🍓", "🍾", "💋", "🖕", "😈",
    "😴", "😭", "🤓", "👻", "👨‍💻", "👀", "🎃", "🙈", "😇", "😨",
    "🤝", "✍️", "🤗", "🫡", "🎅", "🎄", "☃️", "💅", "🤪", "🗿",
    "🆒", "💘", "🙉", "🦄", "😘", "💊", "🙊", "😎", "👾", "🤷‍♂️",
    "🤷", "🤷‍♀️", "😡"
}

def is_valid_emoji(emoji: str) -> bool:
    return emoji in VALID_REACTION_EMOJIS

def get_permission_label(mode: str = "sudo") -> str:
    """Generate permission label for Reply button."""
    if mode == "owner":
        return "Reply (Owner)"
    elif mode == "sudo":
        return "Reply (Sudo + Owner)"
    elif mode == "all":
        return "Reply (All)"
    else:
        return f"Reply ({mode})"

async def load_settings():
    global PM_LOGGER_BOT_DATA, PM_LOGGER_FILTERS, REPLY_FROM_ALL_ACCESSIBLE, REPLY_ACCESS_MODE
    try:
        if STORAGE_FILE.exists():
            async with aiofiles.open(STORAGE_FILE, 'r', encoding='utf-8') as f:
                content = await f.read()
                if content.strip():
                    data = json.loads(content)
                    PM_LOGGER_BOT_DATA = data.get("settings", {})
                    # Migration: enabled -> log_mode
                    if "log_mode" not in PM_LOGGER_BOT_DATA:
                        enabled = PM_LOGGER_BOT_DATA.get("enabled", True)
                        PM_LOGGER_BOT_DATA["log_mode"] = "all" if enabled else "off"
                        
                    PM_LOGGER_FILTERS = data.get("filters", PM_LOGGER_FILTERS)
                    REPLY_FROM_ALL_ACCESSIBLE = data.get("reply_from_all_accessible", True)
                    REPLY_ACCESS_MODE = data.get("reply_access_mode", "sudo")
        else:
            # Default
            PM_LOGGER_BOT_DATA = {"log_mode": "off"}
                    
        # Try to read shared REPLY_ACCESS_MODE from user settings
        shared_file = Path(get_db_path("pm_logger_user_settings.json"))
        if shared_file.exists():
            async with aiofiles.open(shared_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                if content.strip():
                    data = json.loads(content)
                    REPLY_ACCESS_MODE = data.get("reply_access_mode", REPLY_ACCESS_MODE)
    except Exception as e:
        logger.error(f"Failed to load settings: {e}")

async def save_settings():
    try:
        data = {
            "settings": PM_LOGGER_BOT_DATA,
            "filters": PM_LOGGER_FILTERS,
            "reply_from_all_accessible": REPLY_FROM_ALL_ACCESSIBLE,
            "version": PLUGIN_VERSION
        }
        async with aiofiles.open(STORAGE_FILE, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, indent=2))
    except Exception as e:
        logger.error(f"Failed to save PM Logger Bot settings: {e}")

asyncio.create_task(load_settings())

@Altruix.register_on_cmd(
    ["pmlb"],
    cmd_help={
        "help": "Manage PM Logger Bot settings.",
        "usage": "/pmlb [on/off/replyall]",
        "example": "/pmlb on | /pmlb replyall off",
        "detail": (
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🤖 **BOT ASSIST CONTROL (PM)**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "• `/pmlb` : Buka menu pengaturan interaktif.\n\n"
            "👥 **Interactive Tools:**\n"
            "• `/pmlb replyall on` : Izinkan tombol 'Reply From All'.\n"
            "• `/pmlb replyall off`: Sembunyikan tombol 'Reply From All'.\n\n"
            "📊 **General Status:**\n"
            "• `/pmlstatus`: Lihat detail status seluruh logger (User & Bot)."
        )
    },
    group_only=False,
    requires_input=False,
)
@iuser_check
@log_errors
async def pmlb_settings_handler(c: Client, m: AltruixMessage):
    global REPLY_FROM_ALL_ACCESSIBLE
    user_input = (m.user_input or "").lower().strip()
    
    # Direct to interactive menu if no arg
    if not user_input or user_input == "settings":
        # Simulate button press logic to send menu
        log_mode = PM_LOGGER_BOT_DATA.get("log_mode", "off")
        mode_label = Altruix.get_string(f"pmlb_mode_{log_mode}") or log_mode.capitalize()
        text = (
            "<b>🤖 Bot Assist Dashboard (PM Logger)</b>\n\n"
            f"Manage how the Bot Assistant handles private messages.\n"
            f"Current Status: <b>{mode_label}</b>\n"
        )
        buttons = [
            [
                InlineKeyboardButton(await Essentials.get_user_button_style(m.from_user.id, f"{'✅' if log_mode == 'all' else '⚫️'} {Altruix.get_string('pmlb_mode_all')}"), callback_data="pmlb_set_mode_all"),
                InlineKeyboardButton(await Essentials.get_user_button_style(m.from_user.id, f"{'✅' if log_mode == 'sudo' else '⚫️'} {Altruix.get_string('pmlb_mode_sudo')}"), callback_data="pmlb_set_mode_sudo"),
            ],
            [
                InlineKeyboardButton(await Essentials.get_user_button_style(m.from_user.id, f"{'✅' if log_mode == 'nonsudo' else '⚫️'} {Altruix.get_string('pmlb_mode_nonsudo')}"), callback_data="pmlb_set_mode_nonsudo"),
                InlineKeyboardButton(await Essentials.get_user_button_style(m.from_user.id, f"{'✅' if log_mode == 'off' else '⚫️'} {Altruix.get_string('pmlb_mode_off')}"), callback_data="pmlb_set_mode_off"),
            ],
            [
                InlineKeyboardButton(await Essentials.get_user_button_style(m.from_user.id, f"Reply All: {'✅' if REPLY_FROM_ALL_ACCESSIBLE else '❌'}"), callback_data="pmlb_toggle_replyall")
            ],
            [InlineKeyboardButton(await Essentials.get_user_button_style(m.from_user.id, Altruix.get_string('close') or "Close"), callback_data="create_close")]
        ]
        return await m.reply_msg(text, reply_markup=InlineKeyboardMarkup(buttons))

    if user_input.startswith("replyall"):
        arg = user_input.replace("replyall", "").strip()
        if arg in ["on", "yes"]:
            REPLY_FROM_ALL_ACCESSIBLE = True
            msg_text = "✅ **Reply From All (PM Bot) is now ACCESSIBLE**"
        elif arg in ["off", "no"]:
            REPLY_FROM_ALL_ACCESSIBLE = False
            msg_text = "❌ **Reply From All (PM Bot) is now RESTRICTED**"
        else:
            return await m.reply_msg("Usage: `/pmlb replyall on/off`")
        await save_settings()
        return await m.reply_msg(msg_text)
    
    # Legacy support for on/off args
    if user_input in ["on", "yes", "enable"]:
        PM_LOGGER_BOT_DATA["log_mode"] = "all"
        status = "ALL (Enabled) ✅"
    elif user_input in ["off", "no", "disable"]:
        PM_LOGGER_BOT_DATA["log_mode"] = "off"
        status = "OFF (Disabled) ❌"
    else:
        return await m.reply_msg("INVALID_INPUT")
    
    await save_settings()
    await m.reply_msg(f"**PM Logger Bot Mode set to:** `{status}`")

@Altruix.register_on_cmd(
    ["pmlstatus", "pmlbstatus"],
    cmd_help={
        "help": "Check status of PM Logger User and Bot.",
        "example": "/pmlstatus",
    },
    group_only=False,
    requires_input=False,
)
@iuser_check
@log_errors
async def pml_status_bot_handler(c: Client, m: AltruixMessage):
    # Bot status
    log_mode = PM_LOGGER_BOT_DATA.get("log_mode", "off")
    b_enabled = log_mode != "off"
    
    # Userbot settings (import from the other plugin)
    try:
        from Main.plugins.userbot.xpm_logger_user import PM_LOGGER_USER_DATA as U_DATA, REPLY_FROM_ALL_ACCESSIBLE
        u_enabled = U_DATA.get("enabled", False)
        mode = U_DATA.get("mode", "both")
    except:
        u_enabled = False
        mode = "both"
        REPLY_FROM_ALL_ACCESSIBLE = True

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


@Altruix.bot.on_message(
    filters.private & ~filters.me, group=0
)
@log_errors
async def pm_logger_bot_handler(c: Client, m: RawMessage):
    """Log incoming private messages to the bot."""
    try:
        # ✅ Dynamic Reload: Catch UI updates from settings.py
        await load_settings()

        if not PM_LOGGER_BOT_DATA.get("log_mode", "off") != "off":
            return

        # Filtering Logic
        log_mode = PM_LOGGER_BOT_DATA.get("log_mode", "all")
        
        # Check authorization for Sudo/Non-Sudo modes
        from Main.utils.access_control import is_authorized_user
        sender_is_auth = is_authorized_user(m.from_user.id, Altruix.config.OWNER_USERS_ID, Altruix.config.SUDO_USERS_ID)
        
        if log_mode == "sudo" and not sender_is_auth:
            return # Sudo mode: Only authorized users
        
        if log_mode == "nonsudo" and sender_is_auth:
            return # Non-Sudo mode: Only unauthorized users
            
        # Optional: Check if at least one session has bot logging enabled 
        # (Though usually bot logger is global for the bot assistant anyway)
            
        sender = m.from_user
        if not sender:
            return
            
        # Block Bot PMs if coming from another Bot (optional, if you want only user PMs)
        if sender.is_bot and log_mode == "nonsudo":
           # Logic choice: Are bots considered non-sudo? typically yes. 
           # But let's assume 'nonsudo' implies 'regular human users'.
           pass 

        sender_id = sender.id
        logger.info(f"🤖 Bot Logger triggered for PM from {sender_id} [Mode: {log_mode}]")

        if not Altruix.log_chat:
            logger.warning("🤖 PMLB: log_chat is not configured!")
            return
        sender_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip() or "Unknown"
        sender_username = f"@{sender.username}" if sender.username else "No Username"
        sender_hyperlink = f'<a href="tg://user?id={sender_id}">{html.escape(sender_name)}</a>'
        
        msg_type_str = "text"
        if m.media:
            if msg_type_str == "animation": msg_type_str = "video"
            
        log_time = m.date.strftime("%Y-%m-%d %H:%M:%S")
        msg_text = m.text or m.caption or "[Media]"

        # ✅ Filter Check
        filter_key = "from_bot" if sender.is_bot else "from_user"
        
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
        logger.info(f"🔍 [DEBUG] Filter key: {filter_key}, Message type: {filter_msg_type}")
        logger.info(f"🔍 [DEBUG] PM_LOGGER_FILTERS: {PM_LOGGER_FILTERS.get(filter_key, {})}")
        if filter_msg_type and not PM_LOGGER_FILTERS.get(filter_key, {}).get(filter_msg_type, True):
            logger.warning(f"🤖 PMLB: Message type {filter_msg_type} from {filter_key} is filtered out")
            return  # Skip logging this message type
        
        logger.info("✅ [DEBUG] Passed all checks, preparing to send log...")

        log_content = (
            f"👤 <b>New PM Received (Bot)</b>\n\n"
            f"• <b>From:</b> {sender_hyperlink}\n"
            f"• <b>User ID:</b> <code>{sender_id}</code>\n"
            f"• <b>Username:</b> {sender_username}\n"
            f"• <b>To Bot:</b> {c.me.mention}\n"
            f"• <b>Time:</b> <code>{log_time}</code>\n"
            f"• <b>Type:</b> <code>{msg_type_str}</code>\n"
            f"• <b>Message:</b>\n<blockquote>{html.escape(str(msg_text)[:1000])}</blockquote>"
        )
        
        # ─── BUTTONS ───
        reaction_btns = [
            InlineKeyboardButton(emoji, callback_data=f"pmlb_react_{m.chat.id}_{m.id}_{c.me.id}_{emoji}")
            for emoji in DEFAULT_REACTION_EMOJIS
        ]
        
        row1 = reaction_btns[:3]
        row2 = reaction_btns[3:6]
        
        keyboard = [
            row1,
            row2,
            [
                InlineKeyboardButton(await Essentials.get_user_button_style(c.me.id, "➕ Others"), callback_data=f"pmlb_others_{m.chat.id}_{m.id}_{c.me.id}"),
                InlineKeyboardButton(await Essentials.get_user_button_style(c.me.id, "🗑️ Remove React"), callback_data=f"pmlb_unreact_{m.chat.id}_{m.id}_{c.me.id}")
            ],
            [
                InlineKeyboardButton(await Essentials.get_user_button_style(c.me.id, f"🗨️ {get_permission_label(REPLY_ACCESS_MODE)}"), callback_data=f"pmlb_reply_menu_{m.chat.id}_{m.id}_{c.me.id}"),
                InlineKeyboardButton(await Essentials.get_user_button_style(c.me.id, "💾 Save to Log"), callback_data=f"pmlb_save_{m.chat.id}_{m.id}_{c.me.id}")
            ],
            [
                InlineKeyboardButton(await Essentials.get_user_button_style(c.me.id, "🗑️ Unsend"), callback_data=f"pmlb_unsend_{m.chat.id}_{m.id}_{c.me.id}")
            ],
            [InlineKeyboardButton(await Essentials.get_user_button_style(c.me.id, "🔗 Chat with User"), url=f"tg://user?id={sender_id}")]
        ]

        # Get topic if any (bot will search, but won't create if no permission)
        topic_id = await get_or_create_topic(Altruix.bot, Altruix.log_chat, "pm logger")

        # Forward message to log chat using Bot
        try:
            fwd_msg = await Altruix.bot.forward_messages(Altruix.log_chat, m.chat.id, m.id, message_thread_id=topic_id)
        except Exception as e:
            logger.debug(f"PMLB Forward failed: {e}")
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
        # Cache for recovery - capture ACTUAL thread_id from sent message
        actual_thread_id = getattr(sent_log, "message_thread_id", None)
        from Main.plugins.userbot.xpm_logger_user import PM_LOG_CACHE as U_CACHE
        U_CACHE[f"{m.chat.id}_{m.id}"] = {
            "client_id": c.me.id,
            "log_msg_id": sent_log.id,
            "fwd_msg_id": fwd_msg.id if fwd_msg else None,
            "thread_id": actual_thread_id,
            "chat_id": m.chat.id,
            "msg_id": m.id,
            "last_replies": []
        }
        
        # Save cache
        from Main.plugins.userbot.xpm_logger_user import SessionManager
        SessionManager.save()
    except Exception as e:
        logger.error(f"Error in PM Logger Bot: {e}")

@Altruix.bot.on_edited_message(
    filters.private & ~filters.me, group=0
)
@log_errors
async def pm_logger_bot_edit_handler(c: Client, m: RawMessage):
    """Update log when a bot message is edited."""
    try:
        # ✅ Dynamic Reload
        await load_settings()

        if not PM_LOGGER_BOT_DATA.get("log_mode", "off") != "off":
            return

        from Main.plugins.userbot.xpm_logger_user import PM_LOG_CACHE as U_CACHE
        msg_key = f"{m.chat.id}_{m.id}"
        cache = U_CACHE.get(msg_key)
        if not cache: return

        log_msg_id = cache.get("log_msg_id")
        if not log_msg_id: return

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
            f"👤 <b>New PM Received (Bot) [EDITED]</b>\n\n"
            f"• <b>From:</b> {sender_hyperlink}\n"
            f"• <b>User ID:</b> <code>{sender_id}</code>\n"
            f"• <b>Username:</b> {sender_username}\n"
            f"• <b>To Bot:</b> {c.me.mention}\n"
            f"• <b>Time Original:</b> <code>{log_time}</code>\n"
            f"• <b>Time Edited:</b> <code>{edit_time}</code>\n"
            f"• <b>Type:</b> <code>{msg_type}</code>\n"
            f"• <b>New Message:</b>\n<blockquote>{html.escape(str(msg_text)[:1000])}</blockquote>"
        )

        try:
            old_msg = await Altruix.bot.get_messages(Altruix.log_chat, log_msg_id)
            markup = old_msg.reply_markup if old_msg else None
        except:
            markup = None

        await Altruix.bot.edit_message_text(Altruix.log_chat, log_msg_id, log_content, parse_mode=enums.ParseMode.HTML, reply_markup=markup)
    except Exception as e:
        logger.error(f"Error in PM Logger Bot Edit: {e}")

# Callback Handlers for PMLB
@Altruix.bot.on_callback_query(filters.regex(r"^pmlb_save_"))
@log_errors
async def pmlb_save_callback(c: Client, cb: CallbackQuery):
    try:
        from Main.utils.access_control import is_authorized_user
        if not is_authorized_user(cb.from_user.id, Altruix.config.OWNER_USERS_ID, Altruix.config.SUDO_USERS_ID):
            return await cb.answer(Altruix.get_string("ACCESS_DENIED"), show_alert=True)
            
        data = cb.data.split("_")
        chat_id, msg_id = int(data[2]), int(data[3])
        await Altruix.bot.forward_messages(Altruix.log_chat, chat_id, msg_id)
        await cb.answer("✅ Message forwarded again to log group!", show_alert=True)
    except Exception as e:
        await cb.answer(f"❌ Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlb_reply_(\d+)"))
@log_errors
async def pmlb_reply_callback(c: Client, cb: CallbackQuery):
    from Main.plugins.userbot.xpm_logger_user import REPLY_AS_MENTIONED_WAITING as WAIT_CACHE
    try:
        from Main.utils.access_control import check_reply_access
        has_access, reason = check_reply_access(cb.from_user, REPLY_ACCESS_MODE, Altruix.config.OWNER_USERS_ID, Altruix.config.SUDO_USERS_ID)
        if not has_access:
            return await cb.answer(reason, show_alert=True)
            
        data = cb.data.split("_")
        chat_id, msg_id, client_id = int(data[2]), int(data[3]), int(data[4])
        waiting_id = f"pmlb_r_{int(time.time())}_{cb.id}"
        msg_key = f"{chat_id}_{msg_id}"
        
        # Access cache to get log_msg_id and fwd_msg_id
        from Main.plugins.userbot.xpm_logger_user import PM_LOG_CACHE
        cache = PM_LOG_CACHE.get(msg_key, {})
        log_msg_id = cache.get("log_msg_id") or cb.message.id
        fwd_msg_id = cache.get("fwd_msg_id")
        current_msg_thread = getattr(cb.message, "message_thread_id", None)
        thread_id = cache.get("thread_id") or current_msg_thread
        
        logger.info(f"PMLB Reply: msg_key={msg_key}, log_msg_id={log_msg_id}, thread_id={thread_id}")
        
        WAIT_CACHE[waiting_id] = {
            "chat_id": chat_id, "message_id": msg_id, "client_id": client_id,
            "user_id": cb.from_user.id, "instruction_msg_id": None, "is_reply_all": False,
            "log_msg_id": log_msg_id, "fwd_msg_id": fwd_msg_id, "thread_id": thread_id,
            "msg_key": msg_key
        }
        instr = await cb.message.reply("🗨️ <b>Reply (PM Bot)</b>\n\nSilakan balas pesan ini.", parse_mode=enums.ParseMode.HTML)
        WAIT_CACHE[waiting_id]["instruction_msg_id"] = instr.id
        # Save session
        from Main.plugins.userbot.xpm_logger_user import SessionManager
        SessionManager.save()
        await cb.answer("Silakan kirim balasan Anda.")
    except Exception as e:
        logger.error(f"PMLB Reply Error: {e}")
        try:
            await cb.answer(f"❌ Error: {str(e)[:40]}", show_alert=True)
        except Exception:
            pass

@Altruix.bot.on_callback_query(filters.regex(r"^pmlb_others_"))
@log_errors
async def pmlb_others_callback(c: Client, cb: CallbackQuery):
    try:
        from Main.utils.access_control import is_authorized_user
        if not is_authorized_user(cb.from_user.id, Altruix.config.OWNER_USERS_ID, Altruix.config.SUDO_USERS_ID):
            return await cb.answer(Altruix.get_string("ACCESS_DENIED"), show_alert=True)
            
        data = cb.data.split("_")
        chat_id, msg_id, client_id = int(data[2]), int(data[3]), int(data[4])
        keyboard = []
        emojis = list(VALID_REACTION_EMOJIS)
        for i in range(0, len(emojis), 8):
            row = [InlineKeyboardButton(await Essentials.get_user_button_style(cb.from_user.id, e), callback_data=f"pmlb_react_{chat_id}_{msg_id}_{client_id}_{e}") for e in emojis[i:i+8]]
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton(await Essentials.get_user_button_style(cb.from_user.id, "🔙 Back"), callback_data=f"pmlb_back_{chat_id}_{msg_id}_{client_id}")])
        await cb.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        await cb.answer("Select a reaction emoji")
    except Exception as e:
        await cb.answer(f"❌ Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlb_back_"))
@log_errors
async def pmlb_back_callback(c: Client, cb: CallbackQuery):
    try:
        from Main.utils.access_control import is_authorized_user
        if not is_authorized_user(cb.from_user.id, Altruix.config.OWNER_USERS_ID, Altruix.config.SUDO_USERS_ID):
            return await cb.answer(Altruix.get_string("ACCESS_DENIED"), show_alert=True)
            
        data = cb.data.split("_")
        chat_id, msg_id, client_id = int(data[2]), int(data[3]), int(data[4])
        reaction_btns = [InlineKeyboardButton(await Essentials.get_user_button_style(cb.from_user.id, e), callback_data=f"pmlb_react_{chat_id}_{msg_id}_{client_id}_{e}") for e in DEFAULT_REACTION_EMOJIS]
        keyboard = [
            reaction_btns[:3], reaction_btns[3:6],
            [InlineKeyboardButton(await Essentials.get_user_button_style(cb.from_user.id, "➕ Others"), callback_data=f"pmlb_others_{chat_id}_{msg_id}_{client_id}"), InlineKeyboardButton(await Essentials.get_user_button_style(cb.from_user.id, "🗑️ Remove React"), callback_data=f"pmlb_unreact_{chat_id}_{msg_id}_{client_id}")],
            [InlineKeyboardButton(await Essentials.get_user_button_style(cb.from_user.id, f"🗨️ {get_permission_label(REPLY_ACCESS_MODE)}"), callback_data=f"pmlb_reply_menu_{chat_id}_{msg_id}_{client_id}"), InlineKeyboardButton(await Essentials.get_user_button_style(cb.from_user.id, "💾 Save to Log"), callback_data=f"pmlb_save_{chat_id}_{msg_id}_{client_id}")],
            [InlineKeyboardButton(await Essentials.get_user_button_style(cb.from_user.id, "🗑️ Unsend"), callback_data=f"pmlb_unsend_{chat_id}_{msg_id}_{client_id}")],
            [InlineKeyboardButton(await Essentials.get_user_button_style(cb.from_user.id, "🔗 Chat with User"), url=f"tg://user?id={chat_id}")]
        ]
        await cb.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        await cb.answer(f"❌ Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlb_react_"))
@log_errors
async def pmlb_react_callback(c: Client, cb: CallbackQuery):
    try:
        from Main.utils.access_control import is_authorized_user
        if not is_authorized_user(cb.from_user.id, Altruix.config.OWNER_USERS_ID, Altruix.config.SUDO_USERS_ID):
            return await cb.answer(Altruix.get_string("ACCESS_DENIED"), show_alert=True)
            
        data = cb.data.split("_")
        chat_id, msg_id, client_id, emoji = int(data[2]), int(data[3]), int(data[4]), data[5]
        await Altruix.bot.send_reaction(chat_id, msg_id, emoji)
        await cb.answer(f"✅ Reacted with {emoji}")
    except Exception as e:
        await cb.answer(f"❌ Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlb_unreact_"))
@log_errors
async def pmlb_unreact_callback(c: Client, cb: CallbackQuery):
    try:
        from Main.utils.access_control import is_authorized_user
        if not is_authorized_user(cb.from_user.id, Altruix.config.OWNER_USERS_ID, Altruix.config.SUDO_USERS_ID):
            return await cb.answer(Altruix.get_string("ACCESS_DENIED"), show_alert=True)
            
        data = cb.data.split("_")
        chat_id, msg_id, client_id = int(data[2]), int(data[3]), int(data[4])
        await Altruix.bot.send_reaction(chat_id, msg_id, None)
        await cb.answer("✅ Reaction removed")
    except Exception as e:
        await cb.answer(f"❌ Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlb_replyall_"))
@log_errors
async def pmlb_replyall_callback(c: Client, cb: CallbackQuery):
    from Main.plugins.userbot.xpm_logger_user import REPLY_AS_MENTIONED_WAITING as WAIT_CACHE, USER_REPLY_COUNTS, USER_REPLY_LIMIT
    try:
        from Main.utils.access_control import is_authorized_user
        if not is_authorized_user(cb.from_user.id, Altruix.config.OWNER_USERS_ID, Altruix.config.SUDO_USERS_ID):
            return await cb.answer(Altruix.get_string("ACCESS_DENIED"), show_alert=True)
            
        data = cb.data.split("_")
        chat_id, msg_id, client_id = int(data[2]), int(data[3]), int(data[4])
        user_id = cb.from_user.id
        today = datetime.now().strftime("%Y%m%d")
        if USER_REPLY_COUNTS[user_id][today] >= USER_REPLY_LIMIT:
             return await cb.answer(f"❌ Limit harian tercapai.", show_alert=True)
        
        msg_key = f"{chat_id}_{msg_id}"
        
        # Access cache
        from Main.plugins.userbot.xpm_logger_user import PM_LOG_CACHE
        cache = PM_LOG_CACHE.get(msg_key, {})
        log_msg_id = cache.get("log_msg_id") or cb.message.id
        fwd_msg_id = cache.get("fwd_msg_id")
        thread_id = cache.get("thread_id") or getattr(cb.message, "message_thread_id", None)

        waiting_id = f"pmlb_ra_{int(time.time())}_{cb.id}"
        WAIT_CACHE[waiting_id] = {
            "chat_id": chat_id, "message_id": msg_id, "client_id": client_id,
            "user_id": user_id, "instruction_msg_id": None, "is_reply_all": True,
            "log_msg_id": log_msg_id, "fwd_msg_id": fwd_msg_id, "thread_id": thread_id,
            "msg_key": msg_key
        }
        instr = await cb.message.reply("👥 <b>Reply From All (PM Bot)</b>\n\nSilakan balas pesan ini.", parse_mode=enums.ParseMode.HTML)
        WAIT_CACHE[waiting_id]["instruction_msg_id"] = instr.id
        # Save session
        from Main.plugins.userbot.xpm_logger_user import SessionManager
        SessionManager.save()
        await cb.answer("Silakan kirim balasan Anda.")
    except Exception as e:
        await cb.answer(f"❌ Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlb_unsend_"))
@log_errors
async def pmlb_unsend_callback(c: Client, cb: CallbackQuery):
    from Main.plugins.userbot.xpm_logger_user import PM_LOG_CACHE as U_CACHE
    try:
        from Main.utils.access_control import is_authorized_user
        if not is_authorized_user(cb.from_user.id, Altruix.config.OWNER_USERS_ID, Altruix.config.SUDO_USERS_ID):
            return await cb.answer(Altruix.get_string("ACCESS_DENIED"), show_alert=True)
            
        data = cb.data.split("_")
        chat_id, msg_id, client_id = int(data[2]), int(data[3]), int(data[4])
        msg_key = f"{chat_id}_{msg_id}"
        if msg_key in U_CACHE and U_CACHE[msg_key].get("last_replies"):
            unsend_count = 0
            for cid, mid in U_CACHE[msg_key]["last_replies"]:
                target = Altruix.bot if cid == Altruix.bot.me.id else next((cl for cl in Altruix.clients if cl.me.id == cid), None)
                if target:
                    try:
                        await target.delete_messages(chat_id, mid)
                        unsend_count += 1
                    except: pass
            U_CACHE[msg_key]["last_replies"] = []
            return await cb.answer(f"✅ Unsent {unsend_count} messages!")
        await cb.answer("❌ No recent reply found.", show_alert=True)
    except Exception as e:
        await cb.answer(f"❌ Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlb_reply_menu_"))
@log_errors
async def pmlb_reply_menu_callback(c: Client, cb: CallbackQuery):
    try:
        data = cb.data.split("_")
        chat_id, msg_id, client_id = int(data[3]), int(data[4]), int(data[5])
        
        # Check Access
        from Main.utils.access_control import check_reply_access
        has_access, reason = check_reply_access(cb.from_user, REPLY_ACCESS_MODE, Altruix.config.OWNER_USERS_ID, Altruix.config.SUDO_USERS_ID)
        if not has_access:
            return await cb.answer(reason, show_alert=True)
            
        reply_btns = [
             InlineKeyboardButton(await Essentials.get_user_button_style(cb.from_user.id, "👤 Reply as User"), callback_data=f"pmlb_reply_{chat_id}_{msg_id}_{client_id}")
        ]
        
        if REPLY_FROM_ALL_ACCESSIBLE:
             reply_btns.append(InlineKeyboardButton(await Essentials.get_user_button_style(cb.from_user.id, "👥 Reply From All"), callback_data=f"pmlb_replyall_{chat_id}_{msg_id}_{client_id}"))
             
        menu_markup = InlineKeyboardMarkup([
            reply_btns,
            [InlineKeyboardButton(await Essentials.get_user_button_style(cb.from_user.id, "🔙 Back"), callback_data=f"pmlb_back_{chat_id}_{msg_id}_{client_id}")]
        ])
        
        await cb.edit_message_reply_markup(reply_markup=menu_markup)
        await cb.answer()
    except Exception as e:
        await cb.answer(f"❌ Error: {e}", show_alert=True)

# ✅ HANDLER: Bot PM Logger Menu Callback (Main Menu)
@Altruix.bot.on_callback_query(filters.regex(r"^pmlb_menu$"))
@log_errors
async def pmlb_menu_callback_handler(c: Client, cb: CallbackQuery):
    try:
        from Main.utils.access_control import is_authorized_user
        if not is_authorized_user(cb.from_user.id, Altruix.config.OWNER_USERS_ID, Altruix.config.SUDO_USERS_ID):
             return await cb.answer(Altruix.get_string("ACCESS_DENIED"), show_alert=True)
             
        await pmlb_menu_refresh(c, cb)
    except Exception as e:
        await cb.answer(f"❌ Error: {e}", show_alert=True)

# ✅ HANDLER: Bot PM Logger Menu Callback
@Altruix.bot.on_callback_query(filters.regex(r"^pmlb_set_mode_"))
@log_errors
async def pmlb_set_mode_callback(c: Client, cb: CallbackQuery):
    try:
        from Main.utils.access_control import is_authorized_user
        if not is_authorized_user(cb.from_user.id, Altruix.config.OWNER_USERS_ID, Altruix.config.SUDO_USERS_ID):
             return await cb.answer(Altruix.get_string("ACCESS_DENIED"), show_alert=True)
             
        new_mode = cb.data.replace("pmlb_set_mode_", "").strip()
        if new_mode not in ["all", "sudo", "nonsudo", "off"]:
             return await cb.answer("Invalid Mode", show_alert=True)
             
        PM_LOGGER_BOT_DATA["log_mode"] = new_mode
        await save_settings()
        
        mode_label = Altruix.get_string(f"pmlb_mode_{new_mode}") or new_mode.capitalize()
        await cb.answer(Altruix.get_string("pmlb_mode_changed").format(mode_label), show_alert=True)
        
        # Refresh Menu
        await pmlb_menu_refresh(c, cb)
        
    except Exception as e:
        await cb.answer(f"❌ Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlb_toggle_replyall$"))
@log_errors
async def pmlb_toggle_replyall_callback(c: Client, cb: CallbackQuery):
    try:
        from Main.utils.access_control import is_authorized_user
        if not is_authorized_user(cb.from_user.id, Altruix.config.OWNER_USERS_ID, Altruix.config.SUDO_USERS_ID):
             return await cb.answer(Altruix.get_string("ACCESS_DENIED"), show_alert=True)
             
        global REPLY_FROM_ALL_ACCESSIBLE
        REPLY_FROM_ALL_ACCESSIBLE = not REPLY_FROM_ALL_ACCESSIBLE
        await save_settings()
        
        state = "Enabled" if REPLY_FROM_ALL_ACCESSIBLE else "Disabled"
        await cb.answer(f"Reply From All: {state}")
        
        # Refresh Menu
        await pmlb_menu_refresh(c, cb)
    except Exception as e:
        await cb.answer(f"❌ Error: {e}", show_alert=True)

async def pmlb_menu_refresh(c: Client, cb: CallbackQuery):
    log_mode = PM_LOGGER_BOT_DATA.get("log_mode", "off")
    mode_label = Altruix.get_string(f"pmlb_mode_{log_mode}") or log_mode.capitalize()
    
    text = (
        f"{Altruix.get_string('pmlb_menu_title')}\n\n"
        f"{Altruix.get_string('pmlb_menu_desc').format(mode_label)}\n"
    )
    buttons = [
        [
            InlineKeyboardButton(f"{'✅' if log_mode == 'all' else '⚫️'} {Altruix.get_string('pmlb_mode_all')}", callback_data="pmlb_set_mode_all"),
            InlineKeyboardButton(f"{'✅' if log_mode == 'sudo' else '⚫️'} {Altruix.get_string('pmlb_mode_sudo')}", callback_data="pmlb_set_mode_sudo"),
        ],
        [
            InlineKeyboardButton(f"{'✅' if log_mode == 'nonsudo' else '⚫️'} {Altruix.get_string('pmlb_mode_nonsudo')}", callback_data="pmlb_set_mode_nonsudo"),
            InlineKeyboardButton(f"{'✅' if log_mode == 'off' else '⚫️'} {Altruix.get_string('pmlb_mode_off')}", callback_data="pmlb_set_mode_off"),
        ],
        [
            InlineKeyboardButton(f"Reply All: {'✅' if REPLY_FROM_ALL_ACCESSIBLE else '❌'}", callback_data="pmlb_toggle_replyall")
        ],
        [InlineKeyboardButton("🔙 Back", callback_data="bot_controls_menu")]
    ]
    await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)


# ==================== LOG SUKSES LOADING ====================
# try:
#     Altruix.log(f"[DEBUG] Loaded → {__plugin_name__} {PLUGIN_VERSION}", level=20)
# except Exception as e:
#     logger.info(f"[DEBUG] Loaded → {__plugin_name__} {PLUGIN_VERSION}")