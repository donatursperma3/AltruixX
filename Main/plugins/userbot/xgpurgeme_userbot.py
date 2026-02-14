# Main/plugins/userbot/xgpurgeme_userbot.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
# All rights reserved.

import asyncio
import os
from pyrogram import Client, filters
from pyrogram.errors import PeerIdInvalid
from Main import Altruix
from Main.core.types.message import Message
from Main.core.decorators import iuser_check, log_errors

# Import consolidated logic
from Main.internals.settings_handlers.global_purgeme import (
    STATE_LOCK, get_gp_status_text, get_gp_control_kb, 
    gp_global_purgeme_task, update_gp_dashboard, _get_me
)

# Plugin Metadata
plugin_name = f"{os.path.basename(__file__)}"
__plugin_name__ = plugin_name if plugin_name else "xgpurgeme"
PLUGIN_VERSION = "0.0.30"

@Altruix.register_on_cmd(
    ["gpurgeme"],
    cmd_help={
        "help": "Mass-delete your messages globally across chats.",
        "example": ".gpurgeme",
        "detail": """
<b>Global Purgeme (GPurgeme)</b>
Mass-delete your own messages across multiple chats with interactive UI.

<b>Options:</b>
• <b>Target:</b> All Chats, Groups Only, or Personal Chats only.
• <b>Limit:</b> Number of messages to delete per each chat.
• <b>Delay:</b> Sleep time between processing each chat to avoid floods.
• <b>Ignore Admin:</b> Exclude groups where you are an admin.

<b>Controls:</b>
Interactive dashboard allows Pausing, Resuming, and Stopping the process.
"""
    }
)
@iuser_check
@log_errors
async def gpurgeme_cmd(client: Client, message: Message):
    """
    Mass-delete your messages globally across chats.
    Now supports 15 granular message filters.
    """
    # ✅ SAFETY CHECK: Basic message validity
    if not message or not hasattr(message, 'chat') or not message.chat:
        return

    # Authorization Check
    from Main.utils.access_control import is_authorized_user
    if not is_authorized_user(message.from_user.id, Altruix.config.OWNER_ID, Altruix.config.SUDO_USERS):
        return

    me = await _get_me(client)
    if not me:
        return await message.edit("❌ Failed to fetch session info.")
            
    unique_id = f"gp_{me.id}"
    
    async with STATE_LOCK:
        if not hasattr(Altruix, "GPURGEME_STATE"):
            Altruix.GPURGEME_STATE = {}
            
        if unique_id not in Altruix.GPURGEME_STATE:
            Altruix.GPURGEME_STATE[unique_id] = {
                "unique_id": unique_id,
                "client": client,
                "status": "idle",
                "target": "all",
                "limit": 6,
                "delay": 6,
                "ignore_admin": True,
                "mode": "newest",
                "offset": 0,
                "notify": True,
                "filters": ["all"],
                "deleted_count": 0,
                "processed_chats": 0,
                "total_chats": 0,
                "processed_list": [],
                "stop_event": asyncio.Event(),
                "pause_event": asyncio.Event(),
                "dashboard_msg_id": None,
                "dashboard_chat_id": None,
                "start_time": 0
            }
        state = Altruix.GPURGEME_STATE[unique_id]
        state["pause_event"].set()

    bot_username = Altruix.bot_manager.get_bot_username(me.id)
    text = get_gp_status_text(state)
    kb = get_gp_control_kb(unique_id, state)

    try:
        # Try Inline first with FIXED unique_id format
        try:
            results = await client.get_inline_bot_results(bot_username, f"gp_menu_{unique_id}")
            if results.results:
                sent = await client.send_inline_bot_result(
                    message.chat.id,
                    results.query_id,
                    results.results[0].id,
                    reply_to_message_id=message.id
                )
                if sent:
                    state["dashboard_msg_id"] = sent.id
                    state["dashboard_chat_id"] = sent.chat.id
                # Only delete message if successfully sent
                await message.delete_if_self()
                return
        except Exception as inline_e:
            Altruix.log(f"DEBUG: Inline query failed for {unique_id}: {inline_e}", level=20)

        # Fallback to direct bot message
        bot = Altruix.bot_manager.get_bot(me.id)
        
        # Security check: Bots cannot send messages to themselves
        if message.chat.id == bot.me.id:
            await message.edit("❌ <b>Cannot show dashboard in Bot PM.</b>\nPlease use this command in your <b>Saved Messages</b> or enable Inline Mode in @BotFather.")
            return

        sent = await bot.send_message(
            message.chat.id, 
            text, 
            reply_markup=kb,
            reply_to_message_id=message.id
        )
        state["dashboard_msg_id"] = sent.id
        state["dashboard_chat_id"] = sent.chat.id
        await message.delete_if_self()
        
    except PeerIdInvalid:
        await message.edit(
            "❌ <b>Error: Peer ID Invalid.</b>\n\n"
            "The Bot Assistant (@" + bot_username + ") doesn't know this chat yet.\n"
            "Please <b>start the bot</b> first or send a message to it, then try again."
        )
    except Exception as e:
        await message.edit(f"❌ Error initiating GPurgeme: {e}")

@Altruix.register_on_cmd(
    ["gpurgemestatus", "gpstatus"],
    cmd_help={"help": "Check current Global Purgeme status."}
)
@iuser_check
@log_errors
async def gp_status_cmd(client: Client, message: Message):
    me = await _get_me(client)
    if not me: return
            
    unique_id = f"gp_{me.id}"
    state = Altruix.GPURGEME_STATE.get(unique_id) if hasattr(Altruix, "GPURGEME_STATE") else None
    if not state:
        return await message.edit("❌ <b>No active Global Purgeme session.</b> Use <code>.gpurgeme</code> to start.")
    
    text = get_gp_status_text(state)
    await message.edit(text)

@Altruix.register_on_cmd(
    ["gpurgemestop", "gpstop"],
    cmd_help={"help": "Stop a running Global Purgeme process."}
)
@iuser_check
@log_errors
async def gp_stop_cmd(client: Client, message: Message):
    me = await _get_me(client)
    if not me: return
            
    unique_id = f"gp_{me.id}"
    state = Altruix.GPURGEME_STATE.get(unique_id) if hasattr(Altruix, "GPURGEME_STATE") else None
    if not state:
        return await message.edit("❌ <b>No active Global Purgeme session.</b>")
    
    state["stop_event"].set()
    state["pause_event"].set()
    state["status"] = "idle"
    await message.edit("⏹ <b>Global Purgeme stopped manually.</b>")
    asyncio.create_task(update_gp_dashboard(unique_id))

@Altruix.register_on_cmd(
    ["gpurgemepause", "gppause"],
    cmd_help={"help": "Pause a running Global Purgeme process."}
)
@iuser_check
@log_errors
async def gp_pause_cmd(client: Client, message: Message):
    me = await _get_me(client)
    if not me: return
            
    unique_id = f"gp_{me.id}"
    state = Altruix.GPURGEME_STATE.get(unique_id) if hasattr(Altruix, "GPURGEME_STATE") else None
    if not state or state["status"] != "running":
        return await message.edit("❌ <b>Global Purgeme is not running.</b>")
    
    state["pause_event"].clear()
    state["status"] = "paused"
    await message.edit("⏸ <b>Global Purgeme paused manually.</b>")
    asyncio.create_task(update_gp_dashboard(unique_id))

@Altruix.register_on_cmd(
    ["gpurgemeresume", "gpresume"],
    cmd_help={"help": "Resume a paused Global Purgeme process."}
)
@iuser_check
@log_errors
async def gp_resume_cmd(client: Client, message: Message):
    me = await _get_me(client)
    if not me: return
            
    unique_id = f"gp_{me.id}"
    state = Altruix.GPURGEME_STATE.get(unique_id) if hasattr(Altruix, "GPURGEME_STATE") else None
    if not state or state["status"] != "paused":
        return await message.edit("❌ <b>Global Purgeme is not paused.</b>")
    
    state["pause_event"].set()
    state["status"] = "running"
    await message.edit("▶️ <b>Global Purgeme resumed manually.</b>")
    asyncio.create_task(update_gp_dashboard(unique_id))
