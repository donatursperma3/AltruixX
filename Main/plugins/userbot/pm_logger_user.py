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

# ─── LOGGER KHUSUS PLUGIN ───────────────────────────────────────────────


plugin_name = f"{os.path.basename(__file__)}"
__plugin_name__ = plugin_name if plugin_name else "pm_logger_user"

# --- LOGGER ---
logger = logging.getLogger("altruix.pm_logger_user")
logger.setLevel(logging.INFO)

PLUGIN_NAME = __plugin_name__ 
PLUGIN_VERSION = "1.2.2"  # ✅ Isolated from Bot Mode
STORAGE_FILE = Path("pm_logger_user_settings.json")

# Settings Cache
PM_LOGGER_USER_DATA = {}
PM_LOG_CACHE = {}
REPLY_AS_MENTIONED_WAITING = {}
REPLY_FROM_ALL_ACCESSIBLE = True
USER_REPLY_COUNTS = defaultdict(lambda: defaultdict(int))
USER_REPLY_LIMIT = 5

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

from collections import defaultdict

async def load_settings():
    global PM_LOGGER_USER_DATA
    try:
        if STORAGE_FILE.exists():
            async with aiofiles.open(STORAGE_FILE, 'r', encoding='utf-8') as f:
                content = await f.read()
                if content.strip():
                    data = json.loads(content)
                    PM_LOGGER_USER_DATA = data.get("settings", {})
                    global REPLY_FROM_ALL_ACCESSIBLE
                    REPLY_FROM_ALL_ACCESSIBLE = data.get("reply_from_all_accessible", True)
    except Exception as e:
        logger.error(f"Failed to load PM Logger User settings: {e}")

async def save_settings():
    try:
        data = {
            "settings": PM_LOGGER_USER_DATA,
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
        "usage": ".pmlu [on/off/mode/replyall]",
        "example": ".pmlu on | .pmlu mode bot | .pmlu replyall off",
        "detail": (
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "💬 **PM LOGGER USER COMMANDS**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "• `.pmlu on` : Aktifkan pencatatan PM Userbot.\n"
            "• `.pmlu off`: Nonaktifkan pencatatan PM Userbot.\n\n"
            "🛠 **Logger Mode:**\n"
            "• `.pmlu mode user`: Catat PM masuk ke User saja.\n"
            "• `.pmlu mode bot` : Catat PM masuk ke Bot saja.\n"
            "• `.pmlu mode both`: Catat PM dari keduanya (Default).\n\n"
            "👥 **Interactive Tools:**\n"
            "• `.pmlu replyall on` : Izinkan tombol 'Reply From All'.\n"
            "• `.pmlu replyall off`: Sembunyikan tombol 'Reply From All'.\n\n"
            "📊 **General Status:**\n"
            "• `.pmlstatus`: Lihat detail status seluruh logger."
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
            f"• `.pmlu replyall on/off` - Toggle ReplyAll"
        )
        return await m.reply_msg(res)

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
        "example": "pmlstatus",
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
        
        msg_text = m.text or m.caption or "[No text/media caption]"
        msg_type = m.media.value if m.media else "text"
        
        log_time = m.date.strftime("%Y-%m-%d %H:%M:%S")
        
        log_content = (
            f"👤 <b>New PM Received (User)</b>\n\n"
            f"• <b>From:</b> {sender_hyperlink}\n"
            f"• <b>User ID:</b> <code>{sender_id}</code>\n"
            f"• <b>Username:</b> {sender_username}\n"
            f"• <b>To Account:</b> {c.me.mention}\n"
            f"• <b>Time:</b> <code>{log_time}</code>\n"
            f"• <b>Type:</b> <code>{msg_type}</code>\n"
            f"• <b>Message:</b>\n<blockquote>{html.escape(str(msg_text)[:1000])}</blockquote>"
        )

        # ─── BUTTONS ───
        reaction_btns = [
            InlineKeyboardButton(emoji, callback_data=f"pmlu_react_{m.chat.id}_{m.id}_{c.me.id}_{emoji}")
            for emoji in DEFAULT_REACTION_EMOJIS
        ]
        
        row1 = reaction_btns[:3]
        row2 = reaction_btns[3:6]
        
        keyboard = [
            row1,
            row2,
            [
                InlineKeyboardButton("➕ Others", callback_data=f"pmlu_others_{m.chat.id}_{m.id}_{c.me.id}"),
                InlineKeyboardButton("🗑️ Remove React", callback_data=f"pmlu_unreact_{m.chat.id}_{m.id}_{c.me.id}")
            ],
            [
                InlineKeyboardButton("🗨️ Reply", callback_data=f"pmlu_reply_{m.chat.id}_{m.id}_{c.me.id}"),
                InlineKeyboardButton("💾 Save to Log", callback_data=f"pmlu_save_{m.chat.id}_{m.id}_{c.me.id}")
            ],
            [
                InlineKeyboardButton("👥 Reply From All", callback_data=f"pmlu_replyall_{m.chat.id}_{m.id}_{c.me.id}"),
                InlineKeyboardButton("🗑️ Unsend", callback_data=f"pmlu_unsend_{m.chat.id}_{m.id}_{c.me.id}")
            ],
            [InlineKeyboardButton("🔗 Chat with User", url=f"tg://user?id={sender_id}")]
        ]

        if not REPLY_FROM_ALL_ACCESSIBLE:
            # Remove Reply From All button row or just that button
            keyboard = [r for r in keyboard if not any(b.text == "👥 Reply From All" for b in r)]

        # Forward message
        fwd_msg = await c.forward_messages(Altruix.log_chat, m.chat.id, m.id)
        
        # Send Detailed Info as a reply to the forwarded message
        sent_log = await Altruix.bot.send_message(
            Altruix.log_chat,
            log_content,
            parse_mode=enums.ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard),
            reply_to_message_id=fwd_msg.id if fwd_msg else None
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

# ==================== LOG SUKSES LOADING ====================
try:
    Altruix.log(f"[DEBUG] Loaded → {__plugin_name__} {PLUGIN_VERSION}", level=20)
except Exception as e:
    logger.info(f"[DEBUG] Loaded → {__plugin_name__} {PLUGIN_VERSION}")
