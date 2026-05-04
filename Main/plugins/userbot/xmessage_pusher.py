# xmessage_pusher.py
"""
Plugin Message Pusher untuk Altruix Userbot
Inspired by xcreategroup.py logic
Created by Antigravity for Altruix
"""

import os
import asyncio
import logging
import json
import html
import traceback
from datetime import datetime
from typing import List, Dict, Any, Optional

from pyrogram import Client, filters
from pyrogram.errors import FloodWait, RPCError, UserIsBlocked, PeerIdInvalid, ChatWriteForbidden, BadRequest
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode

from Main import Altruix
from Main.core.decorators import log_errors, iuser_check
from Main.core.types.message import Message
from Main.utils.file_helpers import get_db_path
from Main.utils.helpers import ChatPrivileges

# ─── LOGGER ───
logger = logging.getLogger("altruix.xmessage_pusher")
logger.setLevel(logging.INFO)

plugin_name = f"{os.path.basename(__file__)}"
__plugin_name__ = plugin_name if plugin_name else "xmessage_pusher"
PLUGIN_VERSION = "0.1.11"

# ─── CONFIG ───
LOG_CHAT_ID = Altruix.log_chat or Altruix.config.LOG_CHAT_ID or Altruix.config.OWNER_USERS_ID
SRC_CHANNEL = "alphaxbbc"

# Message IDs from xcreategroup.py
LIST_MSG_IDS = [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17]
MSG_IMG_IDS = [25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76]

LOVE_QUOTES = [
    "You are the best thing that ever happened to me.",
    "Every moment with you is like a dream come true.",
    "My heart belongs to you, now and forever."
]

LOVE_QUOTES_2 = [
    "I love you more than words can express.",
    "You are my sunshine on a rainy day.",
    "Life is beautiful because of you."
]

LOVE_QUOTES_3 = [
    "I'm so lucky to have you in my life.",
    "You make my world a better place.",
    "Thinking of you always makes me smile."
]

# Task Storage
MESSAGEPUSHER_TASKS = {}
CACHE_FILE = get_db_path("xmessage_pusher_cache.json")

async def save_cache():
    try:
        data = {}
        for tid, task in MESSAGEPUSHER_TASKS.items():
            task_copy = task.copy()
            # Remove non-serializable objects
            for key in ["pause_event", "task_obj"]:
                if key in task_copy: del task_copy[key]
            if "start_time" in task_copy:
                task_copy["start_time"] = task_copy["start_time"].isoformat()
            data[tid] = task_copy
        
        with open(CACHE_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save cache: {e}")

async def send_log_notification(client, text, user_id, reply_to=None):
    try:
        await client.send_message(
            LOG_CHAT_ID,
            text,
            parse_mode=ParseMode.HTML,
            reply_to_message_id=reply_to
        )
    except Exception as e:
        logger.error(f"Failed to send log: {e}")

async def messagepusher_loop(
    user_client: Client,
    bot_client: Client,
    target_chats: List[Any],
    delay_act: float,
    batch_act: int,
    ba_delay: int,
    options: Dict[str, bool],
    control_message: Message,
    user_id: int
):
    from Main.plugins.userbot.xtaskmanager import register_task, unregister_task, generate_task_id
    tid = generate_task_id("MP")
    
    try:
        user_info = await user_client.get_me()
        userbot_id = user_info.id
        task_id = f"messagepusher_{userbot_id}"
        account_name = f"{user_info.first_name or ''} {user_info.last_name or ''}".strip()
        
        MESSAGEPUSHER_TASKS[task_id] = {
            "running": True,
            "paused": False,
            "pause_event": asyncio.Event(),
            "current_index": 0,
            "start_time": datetime.now(),
            "user_id": user_id,
            "account_name": account_name,
            "task_obj": asyncio.current_task()
        }
        MESSAGEPUSHER_TASKS[task_id]["pause_event"].set()
        await save_cache()
        
        register_task(tid, asyncio.current_task(), "Message Pusher", "xmessage_pusher", user_id, f"Chats: {len(target_chats)}", user_name=account_name)
        
        await send_log_notification(
            bot_client,
            f"<blockquote expandable>🚀 <b>Task Message Pusher Started</b>\n"
            f"• Task ID: <code>{tid}</code>\n"
            f"• Account: <b>{html.escape(account_name)}</b>\n"
            f"• Targets: <code>{len(target_chats)}</code> chats\n"
            f"• Act Delay: <code>{delay_act}</code>s\n"
            f"• Batch Act: <code>{batch_act}</code> | Delay: <code>{ba_delay}</code>s\n"
            f"</blockquote>",
            user_id
        )

        action_count = 0
        async def handle_delay():
            nonlocal action_count
            await asyncio.sleep(delay_act)
            action_count += 1
            if action_count >= batch_act:
                action_count = 0
                await asyncio.sleep(ba_delay)

        for idx, chat_id in enumerate(target_chats, 1):
            if not MESSAGEPUSHER_TASKS.get(task_id, {}).get("running"): break
            
            # Convert to int if numeric string to avoid Pyrogram interpreting it as a phone number
            try:
                if str(chat_id).replace("-", "").isdigit():
                    chat_id = int(chat_id)
            except: pass
            
            try:
                # 0. Handle Anon Adm if enabled
                if options.get("anon_adm"):
                    try:
                        await user_client.promote_chat_member(
                            chat_id, user_info.id,
                            privileges=ChatPrivileges(
                                can_manage_chat=True,
                                can_delete_messages=True,
                                can_manage_video_chats=True,
                                can_restrict_members=True,
                                can_promote_members=True,
                                can_change_info=True,
                                can_post_messages=True,
                                can_edit_messages=True,
                                can_invite_users=True,
                                can_pin_messages=True,
                                can_manage_topics=True,
                                can_post_stories=True,
                                can_edit_stories=True,
                                can_delete_stories=True,
                                is_anonymous=True
                            )
                        )
                        await handle_delay()
                    except Exception as e:
                        logger.warning(f"Failed to set anon adm for {chat_id}: {e}")

                # 1. LIST_MSG_IDS
                for msg_id in LIST_MSG_IDS:
                    await user_client.copy_message(chat_id, SRC_CHANNEL, msg_id)
                    await handle_delay()
                
                # 2. LOVE_QUOTES
                if options.get("quote1"):
                    for quote in LOVE_QUOTES:
                        await user_client.send_message(chat_id, f"<i>💙 {quote}</i>", parse_mode=ParseMode.HTML)
                        await handle_delay()
                
                # 3. LOVE_QUOTES_2
                if options.get("quote2"):
                    for quote in LOVE_QUOTES_2:
                        await user_client.send_message(chat_id, f"<i>💖 {quote}</i>", parse_mode=ParseMode.HTML)
                        await handle_delay()
                
                # 4. MSG_IMG_IDS
                if options.get("msg_img"):
                    for img_id in MSG_IMG_IDS:
                        await user_client.copy_message(chat_id, SRC_CHANNEL, img_id)
                        await handle_delay()
                
                # 5. LOVE_QUOTES_3
                if options.get("quote3"):
                    for quote in LOVE_QUOTES_3:
                        await bot_client.send_message(chat_id, f"<i>💗 {quote}</i>", parse_mode=ParseMode.HTML)
                        await handle_delay()

                await send_log_notification(
                    bot_client,
                    f"✅ <b>Pushed to chat {idx}/{len(target_chats)}</b>: <code>{chat_id}</code>",
                    user_id
                )
            except Exception as e:
                logger.error(f"Error pushing to {chat_id}: {e}")
                await send_log_notification(bot_client, f"❌ <b>Error on {chat_id}</b>: {str(e)}", user_id)

        await send_log_notification(bot_client, f"🏁 <b>Message Pusher Task Completed!</b>\n• Task ID: <code>{tid}</code>", user_id)

    except Exception as e:
        logger.error(f"Critical error in pusher_loop: {e}")
    finally:
        unregister_task(tid)
        MESSAGEPUSHER_TASKS.pop(task_id, None)
        await save_cache()

# ─── COMMANDS ───
@Altruix.register_on_cmd(
    ["pushmsg"], 
    cmd_help={
        "help": "Open Message Pusher dashboard.", 
        "usage": ".pushmsg [chat_id/current chat]",
        "example": ".pushmsg -100123456789"
    }
)
@iuser_check
@log_errors
async def pushmsg_cmd(c: Client, m: Message):
    user_id = m.from_user.id if m.from_user else c.me.id
    logger.info(f"Received .pushmsg command from {user_id} (Anon: {m.from_user is None})")
    
    # Handle optional target argument
    target_arg = m.user_input
    
    try:
        from Main.internals.settings_handlers.message_pusher_handlers import show_pusher_ui, user_messagepusher_state, DEFAULT_PUSHER_CONFIG
        
        # Resolve 'current' keyword
        if target_arg and target_arg.lower() == "current":
            target_arg = str(m.chat.id)

        # Find session index first (needed for composite state key)
        session_index = -1
        for i, client in enumerate(Altruix.clients):
            if client.me and client.me.id == user_id:
                session_index = i
                break
        
        if session_index == -1:
            return await m.reply_msg("❌ Session not found.")

        # Use composite state key matching all dashboard handlers
        state_key = f"{user_id}_{session_index}"

        # Initialize or update state with targets if provided
        if target_arg:
            if state_key not in user_messagepusher_state:
                user_messagepusher_state[state_key] = {
                    "step": "idle",
                    "config": DEFAULT_PUSHER_CONFIG.copy(),
                    "session_index": session_index,
                    "sub_menu": None
                }
            user_messagepusher_state[state_key]["config"]["targets"] = target_arg
            logger.info(f"Set targets to: {target_arg}")

            
        # Trigger the dashboard through inline query
        bot_username = Altruix.bot_manager.get_bot_username(c.me.id)
        logger.info(f"Triggering inline query to @{bot_username} with query: pushmsg_{session_index}")
        
        try:
            results = await c.get_inline_bot_results(bot_username, f"pushmsg_{session_index}")
            logger.info(f"Received {len(results.results)} inline results. Query ID: {results.query_id}")
            
            await c.send_inline_bot_result(
                chat_id=m.chat.id,
                query_id=results.query_id,
                result_id=results.results[0].id,
                reply_to_message_id=m.reply_to_message.id if m.reply_to_message else m.id
            )
            logger.info("Successfully sent inline bot result.")
        except Exception as inline_err:
            logger.error(f"Failed to get or send inline result: {inline_err}")
            # Fallback to direct edit if possible (though unlikely to work if inline failed)
            raise inline_err

        await m.delete_if_self()
    except Exception as e:
        error_tb = traceback.format_exc()
        logger.error(f"Error in pushmsg_cmd: {e}\n{error_tb}")
        await m.reply_msg(f"❌ <b>Error Loading Dashboard:</b>\n<code>{html.escape(str(e))}</code>\n\n<blockquote expandable><code>{html.escape(error_tb)}</code></blockquote>", parse_mode=ParseMode.HTML)

Altruix.log(f"[DEBUG] Loaded → {__plugin_name__} {PLUGIN_VERSION}", level=20)
