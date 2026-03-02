# xmention_logger_bot.py
# Bot Assistant Mention Logger - Independent from Userbot Mentions
# Copyright (C) 2021-present by Altruix@Github, <https://github.com/Altruix>.

from Main import Altruix
from Main.utils.essentials import Essentials
from pyrogram import Client, filters, enums
from pyrogram.types import (
    Message as RawMessage, InlineKeyboardButton, InlineKeyboardMarkup, 
    CallbackQuery, ReplyParameters
)
from Main.core.decorators import log_errors, iuser_check
import os
import html
import logging
import json
import asyncio
import time
from pathlib import Path
from datetime import datetime
import aiofiles
from Main.utils.file_helpers import get_db_path

# Logger
plugin_name = f"{os.path.basename(__file__)}"
__plugin_name__ = plugin_name if plugin_name else "xmention_logger_bot"
logger = logging.getLogger("altruix.mention_logger_bot")
logger.setLevel(logging.INFO)


# Global Constants
PLUGIN_NAME = __plugin_name__
PLUGIN_VERSION = "1.0.55"
# ✅ FIX: Match the file name used in logger_handlers.py UI (plural 'mentions')
STORAGE_FILE = Path(get_db_path("mentions_settings.json"))

# Settings Cache - ✅ Default: Disabled/Off
MENTION_LOGGER_BOT_DATA = {"enabled": False}
REPLY_ACCESS_MODE = "sudo"
LAST_LOAD_TIME = 0

async def load_settings():
    global MENTION_LOGGER_BOT_DATA, REPLY_ACCESS_MODE, LAST_LOAD_TIME
    try:
        if STORAGE_FILE.exists():
            # Optimization: Only load if file modified
            current_mtime = STORAGE_FILE.stat().st_mtime
            if current_mtime <= LAST_LOAD_TIME and MENTION_LOGGER_BOT_DATA:
                return
                
            async with aiofiles.open(STORAGE_FILE, 'r', encoding='utf-8') as f:
                content = await f.read()
                if content.strip():
                    data = json.loads(content)
                    # UI writes enabled status in 'settings' -> 'enabled'
                    MENTION_LOGGER_BOT_DATA = data.get("settings", {"enabled": False})
                    # Also check root level for some legacy syncs if needed
                    if "enabled" in data and "enabled" not in MENTION_LOGGER_BOT_DATA:
                        MENTION_LOGGER_BOT_DATA["enabled"] = data["enabled"]
                    
                    REPLY_ACCESS_MODE = data.get("reply_access_mode", "sudo")
                    LAST_LOAD_TIME = current_mtime
        else:
            MENTION_LOGGER_BOT_DATA = {"enabled": False}
    except Exception as e:
        logger.error(f"Failed to load Mention Logger Bot settings: {e}")

async def save_settings():
    # Load current file to preserve other keys
    data = {}
    if STORAGE_FILE.exists():
        try:
            with open(STORAGE_FILE, "r") as f: data = json.load(f)
        except: pass
        
    try:
        data["settings"] = MENTION_LOGGER_BOT_DATA
        data["reply_access_mode"] = REPLY_ACCESS_MODE
        data["version"] = PLUGIN_VERSION
        async with aiofiles.open(STORAGE_FILE, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, indent=2, ensure_ascii=False))
        
        global LAST_LOAD_TIME
        LAST_LOAD_TIME = time.time() # Update cache state
    except Exception as e:
        logger.error(f"Failed to save Mention Logger Bot settings: {e}")

asyncio.create_task(load_settings())

@Altruix.bot.on_message(
    filters.mentioned & filters.group & ~filters.me, group=1
)
@log_errors
async def mention_logger_bot_handler(c: Client, m: RawMessage):
    """Log when bot is mentioned in groups."""
    try:
        # ✅ Optimized: Only loads if mtime changed
        await load_settings()
        
        # Check enabled status safely
        is_bot_enabled = False
        if isinstance(MENTION_LOGGER_BOT_DATA, dict):
            is_bot_enabled = MENTION_LOGGER_BOT_DATA.get("enabled", False)
        
        if not is_bot_enabled:
            return
        
        if not Altruix.log_chat:
            logger.warning("🤖 Mention Logger Bot: log_chat is not configured!")
            return
        
        sender = m.from_user
        if not sender:
            return
        
        chat = m.chat
        sender_id = sender.id
        sender_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip() or "Unknown"
        sender_username = f"@{sender.username}" if sender.username else "No Username"
        sender_hyperlink = f'<a href="tg://user?id={sender_id}">{html.escape(sender_name)}</a>'
        
        chat_title = html.escape(chat.title or "Unknown Group")
        chat_username = f"@{chat.username}" if chat.username else "Private Group"
        
        log_time = m.date.strftime("%Y-%m-%d %H:%M:%S")
        msg_text = m.text or m.caption or "[Media]"
        
        log_content = (
            f"🔔 <b>Bot Mentioned in Group</b>\n\n"
            f"• <b>From:</b> {sender_hyperlink}\n"
            f"• <b>User ID:</b> <code>{sender_id}</code>\n"
            f"• <b>Username:</b> {sender_username}\n"
            f"• <b>Group:</b> {chat_title}\n"
            f"• <b>Group Username:</b> {chat_username}\n"
            f"• <b>Group ID:</b> <code>{chat.id}</code>\n"
            f"• <b>Time:</b> <code>{log_time}</code>\n"
            f"• <b>Message:</b>\n<blockquote>{html.escape(str(msg_text)[:1000])}</blockquote>"
        )
        
        # Buttons
        # Determine label based on access mode
        reply_label = "Reply (Sudo + Owner)"
        if REPLY_ACCESS_MODE == "owner":
            reply_label = "Reply (Owner)"
        elif REPLY_ACCESS_MODE == "all":
            reply_label = "Reply (All)"
        elif REPLY_ACCESS_MODE != "sudo":
             reply_label = f"Reply ({REPLY_ACCESS_MODE})"

        buttons = [
            [
                InlineKeyboardButton(await Essentials.get_user_button_style(c.me.id, f"💬 {reply_label}"), callback_data=f"mntlb_reply_{chat.id}_{m.id}_{sender_id}"),
                InlineKeyboardButton(await Essentials.get_user_button_style(c.me.id, "🔇 Mute Group"), callback_data=f"mntlb_mute_{chat.id}"),
            ],
            [
                InlineKeyboardButton(await Essentials.get_user_button_style(c.me.id, "🔗 Go to Message"), url=m.link if m.link else f"https://t.me/c/{str(chat.id)[4:]}/{m.id}")
            ]
        ]

        # Check if muted
        if chat.id in MENTION_LOGGER_BOT_DATA.get("muted_chats", []):
            return
        
        await Altruix.bot.send_message(
            chat_id=Altruix.log_chat,
            text=log_content,
            parse_mode=enums.ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(buttons),
            disable_web_page_preview=True
        )
        
        logger.info(f"🔔 Bot mentioned in {chat.title} by {sender_name} (ID: {sender_id})")
        
    except Exception as e:
        logger.error(f"Error in mention_logger_bot_handler: {e}", exc_info=True)


@Altruix.bot.on_callback_query(filters.regex(r"^mntlb_reply_(-?\d+)_(\d+)_(\d+)$"))
@log_errors
async def mention_reply_handler(c: Client, cb: CallbackQuery):
    """Handle reply button for bot mentions."""
    # Import shared cache
    from Main.plugins.userbot.xpm_logger_user import REPLY_AS_MENTIONED_WAITING
    try:
        from Main.utils.access_control import check_reply_access
        
        chat_id = int(cb.matches[0].group(1))
        msg_id = int(cb.matches[0].group(2))
        original_sender_id = int(cb.matches[0].group(3))
        
        # Check access
        has_access, reason = check_reply_access(
            user=cb.from_user,
            mode=REPLY_ACCESS_MODE,
            owner_id=Altruix.config.OWNER_ID,
            sudo_users=Altruix.config.SUDO_USERS,
            mentioned_userbot_id=None  # Not applicable for bot mentions
        )
        
        if not has_access:
            await cb.answer(reason, show_alert=True)
            return
        
        # Use simple timestamp based ID
        waiting_id = f"mntlb_r_{int(datetime.now().timestamp())}_{cb.id}"
        REPLY_AS_MENTIONED_WAITING[waiting_id] = {
            "chat_id": chat_id,
            "message_id": msg_id,
            "client_id": c.me.id, # Bot ID
            "user_id": cb.from_user.id,
            "instruction_msg_id": None,
            "is_reply_all": False,
            "msg_key": f"{chat_id}_{msg_id}"
        }
        
        instr = await cb.message.reply(
            "💬 <b>Reply to Mention (Bot)</b>\n\n"
            "Silakan balas pesan ini.\n"
            "Pesan akan dikirim dari Bot ke Group tersebut.",
            parse_mode=enums.ParseMode.HTML,
            reply_parameters=ReplyParameters(message_id=cb.message.id)
        )
        REPLY_AS_MENTIONED_WAITING[waiting_id]["instruction_msg_id"] = instr.id
        await cb.answer("Silakan kirim balasan Anda.")
        
    except Exception as e:
        logger.error(f"Error in mention_reply_handler: {e}")
        await cb.answer(f"❌ Error: {e}", show_alert=True)


@Altruix.bot.on_callback_query(filters.regex(r"^mntlb_mute_(-?\d+)$"))
@iuser_check
@log_errors
async def mention_mute_handler(c: Client, cb: CallbackQuery):
    """Handle mute group button."""
    try:
        
        chat_id = int(cb.matches[0].group(1))
        
        muted = MENTION_LOGGER_BOT_DATA.get("muted_chats", [])
        if chat_id not in muted:
            muted.append(chat_id)
            MENTION_LOGGER_BOT_DATA["muted_chats"] = muted
            
            # Save settings
            asyncio.create_task(save_settings())
            
            await cb.answer(f"✅ Group {chat_id} telah di-mute.", show_alert=True)
        else:
            await cb.answer(f"⚠️ Group {chat_id} sudah di-mute sebelumnya.", show_alert=True)
        
    except Exception as e:
        logger.error(f"Error in mention_mute_handler: {e}")
        await cb.answer(f"❌ Error: {e}", show_alert=True)




# ✅ HANDLER: Mention Logger Bot Commands
@Altruix.register_on_cmd(
    ["menlb"],
    cmd_help={
        "help": "Manage Mention Logger Bot settings.",
        "usage": "/menlb [on/off/status]",
        "example": "/menlb on",
        "detail": (
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🤖 **BOT ASSIST CONTROL (Mention)**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "• `/menlb` : Buka menu interaktif.\n\n"
            "Usage Examples:\n"
            "• `/menlb on` : Aktifkan logger bot mention.\n"
            "• `/menlb off` : Matikan logger bot mention.\n"
        )
    },
    group_only=False,
    requires_input=False,
)
@iuser_check
@log_errors
async def menlb_settings_handler(c: Client, m: RawMessage):
    """Handle /menlb command."""
    user_input = (m.command[1] if len(m.command) > 1 else "").lower().strip()
    
    if not user_input or user_input == "menu":
         # Show Menu
         await load_settings()
         enabled = MENTION_LOGGER_BOT_DATA.get("enabled", False)
         
         text = (
            "<b>🤖 Bot Assist Dashboard (Mention Logger)</b>\n\n"
            "Log mentions received by the Bot Assistant in groups.\n\n"
            f"• <b>Status:</b> {'✅ ENABLED' if enabled else '❌ DISABLED'}\n"
            f"• <b>Reply Mode:</b> {REPLY_ACCESS_MODE.upper()}"
        )
         
         buttons = [
            [
                InlineKeyboardButton(await Essentials.get_user_button_style(m.from_user.id, f"{'Disable' if enabled else 'Enable'} Bot Assist"), callback_data="mntlb_toggle_enabled")
            ],
            [
                InlineKeyboardButton(await Essentials.get_user_button_style(m.from_user.id, f"Mode: {REPLY_ACCESS_MODE.upper()}"), callback_data="mntlb_toggle_mode")
            ],
            [
                InlineKeyboardButton(await Essentials.get_user_button_style(m.from_user.id, "🔙 Back"), callback_data="bot_controls_menu")
            ]
        ]
         await m.reply_msg(text, reply_markup=InlineKeyboardMarkup(buttons))
         return

    if user_input in ["on", "enable", "yes"]:
        MENTION_LOGGER_BOT_DATA["enabled"] = True
        status = "ENABLED ✅"
    elif user_input in ["off", "disable", "no"]:
        MENTION_LOGGER_BOT_DATA["enabled"] = False
        status = "DISABLED ❌"
    elif user_input == "status":
        await load_settings()
        enabled = MENTION_LOGGER_BOT_DATA.get("enabled", False)
        status = "ENABLED ✅" if enabled else "DISABLED ❌"
        return await m.reply_msg(
            f"🤖 **Mention Logger Bot Status**\n"
            f"• Status: {status}\n"
            f"• Reply Mode: {REPLY_ACCESS_MODE}"
        )
    else:
        return await m.reply_msg("Invalid argument. Use: `on`, `off`, `status` or just `/menlb` for menu.")

    await save_settings()
    await m.reply_msg(f"✅ Mention Logger Bot is now **{status}**")


# ✅ HANDLER: Mention Logger Bot Settings Menu
@Altruix.bot.on_callback_query(filters.regex(r"^mntlb_menu$"))
@iuser_check
@log_errors
async def mntlb_menu_handler(c: Client, cb: CallbackQuery):
    try:

        await load_settings()
        enabled = MENTION_LOGGER_BOT_DATA.get("enabled", False)
        
        text = (
            "<b>🤖 Bot Assist Dashboard (Mention Logger)</b>\n\n"
            "Log mentions received by the Bot Assistant in groups.\n\n"
            f"• <b>Status:</b> {'✅ ENABLED' if enabled else '❌ DISABLED'}\n"
            f"• <b>Reply Mode:</b> {REPLY_ACCESS_MODE.upper()}"
        )
        
        buttons = [
            [
                InlineKeyboardButton(await Essentials.get_user_button_style(cb.from_user.id, f"{'Disable' if enabled else 'Enable'} Bot Assist"), callback_data="mntlb_toggle_enabled")
            ],
            [
                InlineKeyboardButton(await Essentials.get_user_button_style(cb.from_user.id, f"Mode: {REPLY_ACCESS_MODE.upper()}"), callback_data="mntlb_toggle_mode")
            ],
            [
                InlineKeyboardButton(await Essentials.get_user_button_style(cb.from_user.id, "🔙 Back"), callback_data="bot_controls_menu")
            ]
        ]
        await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)
    except Exception as e:
        await cb.answer(f"❌ Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^mntlb_toggle_enabled$"))
@log_errors
async def mntlb_toggle_enabled_handler(c: Client, cb: CallbackQuery):
    MENTION_LOGGER_BOT_DATA["enabled"] = not MENTION_LOGGER_BOT_DATA.get("enabled", False)
    await save_settings()
    await mntlb_menu_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^mntlb_toggle_mode$"))
@log_errors
async def mntlb_toggle_mode_handler(c: Client, cb: CallbackQuery):
    global REPLY_ACCESS_MODE
    modes = ["sudo", "owner", "all"]
    try:
        current_index = modes.index(REPLY_ACCESS_MODE)
        REPLY_ACCESS_MODE = modes[(current_index + 1) % len(modes)]
    except:
        REPLY_ACCESS_MODE = "sudo"
    
    await save_settings()
    await mntlb_menu_handler(c, cb)
