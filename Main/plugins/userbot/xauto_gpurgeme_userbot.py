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
PLUGIN_VERSION = "0.0.41"

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
        # Fallback to direct edit if no bot found (still better than nothing)
        text = await get_auto_gp_status_text(user_id, current_chat_id=message.chat.id)
        await message.edit(f"❌ <b>Bot assistant not found.</b>\n\n{text}")
        raise StopPropagation

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
    ["autogpdel"],
    cmd_help={
        "help": "Remove a specific chat from Auto-GP blacklist by its chat ID.",
        "example": ".autogpdel -100123456789"
    }
)
@iuser_check
@log_errors
async def autogp_del_blacklist_cmd(client: Client, message: Message):
    """
    Remove a specific chat_id from the Auto-GP blacklist.
    Usage: .autogpdel <chat_id>
    """
    user_id = client.me.id

    if not message.user_input or not message.user_input.lstrip('-').isdigit():
        await message.edit("❌ <b>Usage:</b> <code>.autogpdel &lt;chat_id&gt;</code>")
        raise StopPropagation

    chat_id = int(message.user_input)
    settings = await get_auto_gp_settings(user_id)

    if chat_id not in settings["blacklist"]:
        await message.edit(
            f"⚠️ Chat <code>{chat_id}</code> is <b>NOT</b> in the Auto-GP Blacklist."
        )
        raise StopPropagation

    settings["blacklist"].remove(chat_id)
    await save_auto_gp_settings(user_id, settings)
    await message.edit(
        f"✅ Chat <code>{chat_id}</code> has been <b>REMOVED</b> from Auto-GP Blacklist.\n"
        f"📋 Remaining blacklisted: <code>{len(settings['blacklist'])} chats</code>"
    )
    raise StopPropagation

@Altruix.register_on_cmd(
    ["autogpblist"],
    cmd_help={
        "help": "View all blacklisted chats for Auto Global Purgeme.",
        "example": ".autogpblist"
    }
)
@iuser_check
@log_errors
async def autogp_view_blacklist_cmd(client: Client, message: Message):
    """
    Display all chat IDs currently on the Auto-GP blacklist,
    with resolved chat names where possible.
    """
    user_id = client.me.id
    settings = await get_auto_gp_settings(user_id)
    bl = settings["blacklist"]

    if not bl:
        await message.edit(
            "📋 <b>Auto-GP Blacklist</b>\n\n"
            "<i>Blacklist is empty. No chats are excluded.</i>"
        )
        raise StopPropagation

    lines = []
    for cid in bl:
        try:
            chat = await client.get_chat(cid)
            name = chat.title or chat.first_name or f"Chat {cid}"
        except Exception:
            name = f"Chat {cid}"
        lines.append(f"• <code>{cid}</code> — {name}")

    text = (
        f"📋 <b>Auto-GP Blacklist</b>\n"
        f"Total: <code>{len(bl)}</code> chats\n\n"
        + "\n".join(lines)
    )
    await message.edit(text)
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

    # Check if message has text or caption to look for prefixes
    msg_text = message.text or message.caption or ""

    user_id = client.me.id
    chat_id = message.chat.id
    
    # Retrieve settings to determine behavior
    settings = await get_auto_gp_settings(user_id)
    
    # Check if Auto-GP is ON
    if not settings.get("status", False):
        return

    # TRACE: Log entry after confirming it's enabled
    Altruix.log(f"🔍 Auto-GP Handler ENTRY | MsgID: {message.id} | Chat: {chat_id}", level=20)

    # 🚫 Feature 1: Respect Blacklist for Triggering
    if settings.get("respect_bl", True) and chat_id in settings.get("blacklist", []):
        Altruix.log(f"🕵️ Auto-GP | Trigger Chat {chat_id} is blacklisted. Skipping cycle.", level=20)
        return

    # ⌨️ Feature 2: Command Response Bypass (Skip CMDs)
    if settings.get("skip_cmds", True):
        # Skip if message starts with a command prefix
        prefixes = [Altruix.config.PREFIX_OWNER_USER or ".", Altruix.config.PREFIX_SUDO_USERS or "!"]
        if msg_text and any(msg_text.startswith(p) for p in prefixes):
            Altruix.log(f"⌨️ Auto-GP | Trigger is a command. Skipping cycle.", level=20)
            return
        # Skip if trigger message is an edit
        if getattr(message, "edit_date", None):
             Altruix.log(f"⌨️ Auto-GP | Trigger is an EDIT. Skipping cycle.", level=20)
             return
        # Skip if trigger message is via bot (e.g. inline results, dashboard)
        if getattr(message, "via_bot", None):
             Altruix.log(f"⌨️ Auto-GP | Trigger is VIA BOT. Skipping cycle.", level=20)
             return
        # Skip if trigger message is a reply to a command (e.g. non-inline pong!)
        if message.reply_to_message:
            rep = message.reply_to_message
            rep_text = rep.text or rep.caption or ""
            if rep_text and any(rep_text.startswith(p) for p in prefixes):
                Altruix.log(f"⌨️ Auto-GP | Trigger is a REPLY to a command. Skipping cycle.", level=20)
                return

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
