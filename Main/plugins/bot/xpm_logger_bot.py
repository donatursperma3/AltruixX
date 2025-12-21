# pm_logger_bot.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.

from Main import Altruix
from pyrogram import Client, enums, filters
from pyrogram.types import (
    Message as RawMessage,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyParameters,
    CallbackQuery
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
__plugin_name__ = plugin_name if plugin_name else "pm_logger_bot"

# --- LOGGER ---
logger = logging.getLogger("altruix.pm_logger_bot")
logger.setLevel(logging.INFO)

PLUGIN_NAME = __plugin_name__ 
PLUGIN_VERSION = "1.2.3" # ✅ Added Debug Logs
STORAGE_FILE = Path("pm_logger_bot_settings.json")

# Settings Cache
PM_LOGGER_BOT_DATA = {}
REPLY_FROM_ALL_ACCESSIBLE = True
USER_REPLY_COUNTS = defaultdict(lambda: defaultdict(int))
USER_REPLY_LIMIT = 5

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

async def load_settings():
    global PM_LOGGER_BOT_DATA
    try:
        if STORAGE_FILE.exists():
            async with aiofiles.open(STORAGE_FILE, 'r', encoding='utf-8') as f:
                content = await f.read()
                if content.strip():
                    data = json.loads(content)
                    PM_LOGGER_BOT_DATA = data.get("settings", {})
                    global REPLY_FROM_ALL_ACCESSIBLE
                    REPLY_FROM_ALL_ACCESSIBLE = data.get("reply_from_all_accessible", True)
    except Exception as e:
        logger.error(f"Failed to load PM Logger Bot settings: {e}")

async def save_settings():
    try:
        data = {
            "settings": PM_LOGGER_BOT_DATA,
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
            "🤖 **PM LOGGER BOT COMMANDS**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "• `/pmlb on` : Aktifkan pencatatan PM Bot.\n"
            "• `/pmlb off`: Nonaktifkan pencatatan PM Bot.\n\n"
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
@log_errors
async def pmlb_settings_handler(c: Client, m: AltruixMessage):
    global REPLY_FROM_ALL_ACCESSIBLE
    user_input = (m.user_input or "").lower().strip()
    
    if not user_input:
        is_enabled = PM_LOGGER_BOT_DATA.get("enabled", False)
        status = "ENABLED ✅" if is_enabled else "DISABLED ❌"
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
            f"🤖 **PM Logger Bot Status Detail**\n"
            f"• **Status:** {status}\n"
            f"• **Reply From All:** {ra_status}\n"
            f"• **Log Group ID:** ` {log_chat} `\n"
            f"• **Bot Access:** {bot_access}\n\n"
            f"Use `.pmlb on` or `.pmlb off` to change status.\n"
            f"Use `.pmlb replyall on` or `.pmlb replyall off` to toggle feature."
        )
        return await m.reply_msg(res)

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
    
    if user_input in ["on", "yes"]:
        PM_LOGGER_BOT_DATA["enabled"] = True
        status = "ENABLED ✅"
    elif user_input in ["off", "no"]:
        PM_LOGGER_BOT_DATA["enabled"] = False
        status = "DISABLED ❌"
    else:
        return await m.reply_msg("INVALID_INPUT")
    
    await save_settings()
    await m.reply_msg(f"**PM Logger Bot is now {status}**")

@Altruix.register_on_cmd(
    ["pmlstatus", "pmlbstatus"],
    cmd_help={
        "help": "Check status of PM Logger User and Bot.",
        "example": "/pmlstatus",
    },
    group_only=False,
    requires_input=False,
)
@log_errors
async def pml_status_bot_handler(c: Client, m: AltruixMessage):
    # Bot status
    b_enabled = PM_LOGGER_BOT_DATA.get("enabled", False)
    
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
        if not PM_LOGGER_BOT_DATA.get("enabled", False):
            return

        from Main.plugins.userbot.xpm_logger_user import PM_LOGGER_USER_DATA as U_DATA
        mode = U_DATA.get("mode", "both")
        if mode == "user":
            return
            
        logger.info(f"🤖 Bot Logger triggered for PM from {sender_id if 'sender' in locals() else m.from_user.id}")

        if not Altruix.log_chat:
            logger.warning("🤖 PMLB: log_chat is not configured!")
            return

        sender = m.from_user
        if not sender:
            return

        sender_id = sender.id
        sender_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip() or "Unknown"
        sender_username = f"@{sender.username}" if sender.username else "No Username"
        sender_hyperlink = f'<a href="tg://user?id={sender_id}">{html.escape(sender_name)}</a>'
        
        msg_text = m.text or m.caption or "[No text/media caption]"
        msg_type = m.media.value if m.media else "text"
        
        log_time = m.date.strftime("%Y-%m-%d %H:%M:%S")
        
        log_content = (
            f"👤 <b>New PM Received (Bot)</b>\n\n"
            f"• <b>From:</b> {sender_hyperlink}\n"
            f"• <b>User ID:</b> <code>{sender_id}</code>\n"
            f"• <b>Username:</b> {sender_username}\n"
            f"• <b>To Bot:</b> {c.me.mention}\n"
            f"• <b>Time:</b> <code>{log_time}</code>\n"
            f"• <b>Type:</b> <code>{msg_type}</code>\n"
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
                InlineKeyboardButton("➕ Others", callback_data=f"pmlb_others_{m.chat.id}_{m.id}_{c.me.id}"),
                InlineKeyboardButton("🗑️ Remove React", callback_data=f"pmlb_unreact_{m.chat.id}_{m.id}_{c.me.id}")
            ],
            [
                InlineKeyboardButton("🗨️ Reply", callback_data=f"pmlb_reply_{m.chat.id}_{m.id}_{c.me.id}"),
                InlineKeyboardButton("💾 Save to Log", callback_data=f"pmlb_save_{m.chat.id}_{m.id}_{c.me.id}")
            ],
            [
                InlineKeyboardButton("👥 Reply From All", callback_data=f"pmlb_replyall_{m.chat.id}_{m.id}_{c.me.id}"),
                InlineKeyboardButton("🗑️ Unsend", callback_data=f"pmlb_unsend_{m.chat.id}_{m.id}_{c.me.id}")
            ],
            [InlineKeyboardButton("🔗 Chat with User", url=f"tg://user?id={sender_id}")]
        ]

        if not REPLY_FROM_ALL_ACCESSIBLE:
            keyboard = [r for r in keyboard if not any(b.text == "👥 Reply From All" for b in r)]

        # Forward message to log chat using Bot
        fwd_msg = await Altruix.bot.forward_messages(Altruix.log_chat, m.chat.id, m.id)
        
        # Send Detailed Info as a reply to the forwarded message
        sent_log = await Altruix.bot.send_message(
            Altruix.log_chat,
            log_content,
            parse_mode=enums.ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard),
            reply_to_message_id=fwd_msg.id if fwd_msg else None
        )
        
        # Cache for recovery
        from Main.plugins.userbot.xpm_logger_user import PM_LOG_CACHE as U_CACHE
        U_CACHE[f"{m.chat.id}_{m.id}"] = {
            "client_id": c.me.id,
            "log_msg_id": sent_log.id,
            "chat_id": m.chat.id,
            "msg_id": m.id,
            "last_replies": []
        }
    except Exception as e:
        logger.error(f"Error in PM Logger Bot: {e}")

@Altruix.bot.on_edited_message(
    filters.private & ~filters.me, group=0
)
@log_errors
async def pm_logger_bot_edit_handler(c: Client, m: RawMessage):
    """Update log when a bot message is edited."""
    try:
        if not PM_LOGGER_BOT_DATA.get("enabled", False):
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
        data = cb.data.split("_")
        chat_id, msg_id = int(data[2]), int(data[3])
        await Altruix.bot.forward_messages(Altruix.log_chat, chat_id, msg_id)
        await cb.answer("✅ Message forwarded again to log group!", show_alert=True)
    except Exception as e:
        await cb.answer(f"❌ Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlb_reply_"))
@log_errors
async def pmlb_reply_callback(c: Client, cb: CallbackQuery):
    from Main.plugins.userbot.xpm_logger_user import REPLY_AS_MENTIONED_WAITING as WAIT_CACHE
    try:
        data = cb.data.split("_")
        chat_id, msg_id, client_id = int(data[2]), int(data[3]), int(data[4])
        waiting_id = f"pmlb_r_{int(time.time())}_{cb.id}"
        WAIT_CACHE[waiting_id] = {
            "chat_id": chat_id, "message_id": msg_id, "client_id": client_id,
            "user_id": cb.from_user.id, "instruction_msg_id": None, "is_reply_all": False,
            "msg_key": f"{chat_id}_{msg_id}"
        }
        instr = await cb.message.reply("🗨️ <b>Reply (PM Bot)</b>\n\nSilakan balas pesan ini.", parse_mode=enums.ParseMode.HTML)
        WAIT_CACHE[waiting_id]["instruction_msg_id"] = instr.id
        await cb.answer("Silakan kirim balasan Anda.")
    except Exception as e:
        await cb.answer(f"❌ Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlb_others_"))
@log_errors
async def pmlb_others_callback(c: Client, cb: CallbackQuery):
    try:
        data = cb.data.split("_")
        chat_id, msg_id, client_id = int(data[2]), int(data[3]), int(data[4])
        keyboard = []
        emojis = list(VALID_REACTION_EMOJIS)
        for i in range(0, len(emojis), 8):
            row = [InlineKeyboardButton(e, callback_data=f"pmlb_react_{chat_id}_{msg_id}_{client_id}_{e}") for e in emojis[i:i+8]]
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=f"pmlb_back_{chat_id}_{msg_id}_{client_id}")])
        await cb.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        await cb.answer("Select a reaction emoji")
    except Exception as e:
        await cb.answer(f"❌ Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlb_back_"))
@log_errors
async def pmlb_back_callback(c: Client, cb: CallbackQuery):
    try:
        data = cb.data.split("_")
        chat_id, msg_id, client_id = int(data[2]), int(data[3]), int(data[4])
        reaction_btns = [InlineKeyboardButton(e, callback_data=f"pmlb_react_{chat_id}_{msg_id}_{client_id}_{e}") for e in DEFAULT_REACTION_EMOJIS]
        keyboard = [
            reaction_btns[:3], reaction_btns[3:6],
            [InlineKeyboardButton("➕ Others", callback_data=f"pmlb_others_{chat_id}_{msg_id}_{client_id}"), InlineKeyboardButton("🗑️ Remove React", callback_data=f"pmlb_unreact_{chat_id}_{msg_id}_{client_id}")],
            [InlineKeyboardButton("🗨️ Reply", callback_data=f"pmlb_reply_{chat_id}_{msg_id}_{client_id}"), InlineKeyboardButton("💾 Save to Log", callback_data=f"pmlb_save_{chat_id}_{msg_id}_{client_id}")],
            [InlineKeyboardButton("👥 Reply From All", callback_data=f"pmlb_replyall_{chat_id}_{msg_id}_{client_id}"), InlineKeyboardButton("🗑️ Unsend", callback_data=f"pmlb_unsend_{chat_id}_{msg_id}_{client_id}")],
            [InlineKeyboardButton("🔗 Chat with User", url=f"tg://user?id={chat_id}")]
        ]
        if not REPLY_FROM_ALL_ACCESSIBLE:
             keyboard = [r for r in keyboard if not any(b.text == "👥 Reply From All" for b in r)]
        await cb.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        await cb.answer(f"❌ Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlb_react_"))
@log_errors
async def pmlb_react_callback(c: Client, cb: CallbackQuery):
    try:
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
        if not REPLY_FROM_ALL_ACCESSIBLE:
            return await cb.answer("❌ Fitur ini sedang dinonaktifkan.", show_alert=True)
        data = cb.data.split("_")
        chat_id, msg_id, client_id = int(data[2]), int(data[3]), int(data[4])
        user_id = cb.from_user.id
        today = datetime.now().strftime("%Y%m%d")
        if USER_REPLY_COUNTS[user_id][today] >= USER_REPLY_LIMIT:
             return await cb.answer(f"❌ Limit harian tercapai.", show_alert=True)
        
        waiting_id = f"pmlb_ra_{int(time.time())}_{cb.id}"
        WAIT_CACHE[waiting_id] = {
            "chat_id": chat_id, "message_id": msg_id, "client_id": client_id,
            "user_id": user_id, "instruction_msg_id": None, "is_reply_all": True,
            "msg_key": f"{chat_id}_{msg_id}"
        }
        instr = await cb.message.reply("👥 <b>Reply From All (PM Bot)</b>\n\nSilakan balas pesan ini.", parse_mode=enums.ParseMode.HTML)
        WAIT_CACHE[waiting_id]["instruction_msg_id"] = instr.id
        await cb.answer("Silakan kirim balasan Anda.")
    except Exception as e:
        await cb.answer(f"❌ Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlb_unsend_"))
@log_errors
async def pmlb_unsend_callback(c: Client, cb: CallbackQuery):
    from Main.plugins.userbot.xpm_logger_user import PM_LOG_CACHE as U_CACHE
    try:
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

# ==================== LOG SUKSES LOADING ====================
try:
    Altruix.log(f"[DEBUG] Loaded → {__plugin_name__} {PLUGIN_VERSION}", level=20)
except Exception as e:
    logger.info(f"[DEBUG] Loaded → {__plugin_name__} {PLUGIN_VERSION}")