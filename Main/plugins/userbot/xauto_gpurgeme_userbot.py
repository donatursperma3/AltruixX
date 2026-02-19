# Main/plugins/userbot/xauto_gpurgeme_userbot.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
# All rights reserved.

import os
from pyrogram import Client, filters, StopPropagation
from Main import Altruix
from Main.core.types.message import Message
from Main.core.decorators import iuser_check, log_errors
from Main.internals.settings_handlers.auto_global_purgeme import (
    auto_gp_perform_purge, get_auto_gp_settings, save_auto_gp_settings,
    get_auto_gp_status_text, get_auto_gp_kb, auto_gp_global_cycle
)

# Plugin Metadata
plugin_name = f"{os.path.basename(__file__)}"
__plugin_name__ = plugin_name if plugin_name else "xautogp"
PLUGIN_VERSION = "0.0.36"

# Cooldown/Task tracking is now handled by GLOBAL_PURGE_LOCK in auto_global_purgeme.py

@Altruix.register_on_cmd(
    ["autogp"],
    cmd_help={
        "help": "Open Auto Global Purgeme dashboard via Bot Assistant.",
        "example": ".autogp"
    }
)
@iuser_check
@log_errors
async def autogp_dashboard_cmd(client: Client, message: Message):
    """
    Open the Auto Global Purgeme dashboard.
    Attempts to use the bot assistant's inline mode for a seamless UI.
    """
    user_id = client.me.id
    bot_username = Altruix.bot_manager.get_bot_username(user_id)
    
    if not bot_username:
        await message.edit("❌ <b>Bot assistant not found.</b>")
        return

    # Try Inline first
    try:
        results = await client.get_inline_bot_results(bot_username, f"autogp_menu_uid_{user_id}")
        if results.results:
            sent = await client.send_inline_bot_result(
                message.chat.id,
                results.query_id,
                results.results[0].id,
                reply_to_message_id=message.reply_to_message.id if message.reply_to_message else message.id
            )
            if sent:
                await message.delete_if_self()
                return
    except Exception as e:
        Altruix.log(f"Auto-GP Inline Failed: {e}", level=20)

    # Fallback to direct bot message
    try:
        settings = await get_auto_gp_settings(user_id)
        text = await get_auto_gp_status_text(user_id)
        kb = get_auto_gp_kb(user_id, settings)
        
        bot = Altruix.bot_manager.get_bot(user_id)
        if not bot:
            await message.edit("❌ <b>Could not start bot assistant.</b>")
            return
            
        await bot.send_message(message.chat.id, text, reply_markup=kb)
        await message.delete_if_self()
    except Exception as e:
        await message.edit(f"❌ <b>Error opening Auto-GP:</b> {e}")
    
    raise StopPropagation

@Altruix.register_on_cmd(
    ["autogpon", "autogpoff"],
    cmd_help={"help": "Quick toggle Auto Global Purgeme ON or OFF."}
)
@iuser_check
@log_errors
async def autogp_toggle_cmd(client: Client, message: Message):
    """Quick toggle Auto Global Purgeme."""
    user_id = client.me.id
    settings = await get_auto_gp_settings(user_id)
    
    new_status = message.command[0].lower() == "autogpon"
    settings["status"] = new_status
    await save_auto_gp_settings(user_id, settings)
    
    status_str = "ENABLED" if new_status else "DISABLED"
    await message.edit(f"✅ Auto Global Purgeme has been <b>{status_str}</b>.")
    raise StopPropagation

@Altruix.register_on_cmd(
    ["autogpbl"],
    cmd_help={
        "help": "Blacklist or whitelist a chat for Auto-GP. This prevents Auto-GP from purging messages in that specific chat.",
        "example": ".autogpbl or .autogpbl <chat_id>"
    }
)
@iuser_check
@log_errors
async def autogp_blacklist_cmd(client: Client, message: Message):
    """
    Toggle the blacklist status of a chat for Auto Global Purgeme.
    If no chat ID is provided, the current chat is toggled.
    """
    user_id = client.me.id
    chat_id = message.chat.id
    
    if message.user_input and message.user_input.lstrip('-').isdigit():
        chat_id = int(message.user_input)
        
    settings = await get_auto_gp_settings(user_id)
    
    if chat_id in settings["blacklist"]:
        settings["blacklist"].remove(chat_id)
        action = "REMOVED FROM"
    else:
        settings["blacklist"].append(chat_id)
        action = "ADDED TO"
        
    await save_auto_gp_settings(user_id, settings)
    await message.edit(f"✅ Chat <code>{chat_id}</code> has been <b>{action}</b> Auto-GP Blacklist.")
    raise StopPropagation

@Altruix.register_on_cmd(
    ["autogpstatus"],
    cmd_help={"help": "View current Auto Global Purgeme status, limit, and active filters."}
)
@iuser_check
@log_errors
async def autogp_status_cmd(client: Client, message: Message):
    """
    Display the current configuration and status of the Auto-GP system 
    for the active session.
    """
    user_id = client.me.id
    text = await get_auto_gp_status_text(user_id)
    await message.edit(text)
    raise StopPropagation

@Altruix.on_message(filters.outgoing & ~filters.bot & ~filters.service, group=-1)
@log_errors
async def auto_gp_message_trigger(client: Client, message: Message):
    """
    Automated trigger for purging messages when the user sends a new message.
    Triggered for session owner's outgoing messages.
    Group -1 ensures it runs before command handlers.
    """
    if not message:
        return
    
    # TRACE: Log immediately to confirm entry
    Altruix.log(f"🔍 Auto-GP Handler ENTRY | MsgID: {message.id} | Chat: {message.chat.id}", level=20)

    # Check if message has text or caption to look for prefixes
    msg_text = message.text or message.caption or ""

    # Skip if message starts with a command prefix to avoid interference
    prefixes = [Altruix.prefix_owner_user, Altruix.prefix_sudo_users]
    if msg_text and any(msg_text.startswith(p) for p in prefixes):
        return

    user_id = client.me.id
    chat_id = message.chat.id
    
    # Retrieve settings to determine mode
    settings = await get_auto_gp_settings(user_id)
    cycle_mode = settings.get("cycle", "global")

    if cycle_mode == "global":
        # 🚀 GLOBAL TRIGGER: Fire and forget the global cycle
        import asyncio
        asyncio.create_task(auto_gp_global_cycle(client))
    
    elif cycle_mode == "current_force":
        # ⚠️ FORCE TRIGGER: Force purge on current chat (Bypass guards)
        import asyncio
        Altruix.log(f"📍 Auto-GP Force Mode | Triggering Force Purge for Chat: {chat_id}", level=20)
        asyncio.create_task(auto_gp_perform_purge(client, chat_id, message=message, bypass_guards=True))
    
    elif cycle_mode == "current_smart":
        # ✅ SMART TRIGGER: Purge current chat but RESPECT guards (Blacklist/Admin)
        import asyncio
        Altruix.log(f"📍 Auto-GP Smart Mode | Triggering Safe Purge for Chat: {chat_id}", level=20)
        asyncio.create_task(auto_gp_perform_purge(client, chat_id, message=message, bypass_guards=False))
