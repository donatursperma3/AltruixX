# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.


import re
import glob
import asyncio
import contextlib
from Main import Altruix
from pyrogram import filters, enums
from Main.core.decorators import log_errors
from pyrogram.types import (
    Message, ForceReply, CallbackQuery, KeyboardButton, ReplyKeyboardMarkup,
    ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup)


@Altruix.bot.on_message(filters.command("start", "/") & filters.private)
@log_errors
async def start_command_handler(_, m: Message):
    payload = m.text.replace("/start", "").strip()
    if payload == "debug":
        uid = m.from_user.id
        try:
            is_sudo_result = await Altruix.is_sudo(uid)
        except Exception as e:
            is_sudo_result = f"ERROR: {e}"
        
        in_owner = uid in Altruix.config.OWNER_USERS_ID
        in_db_sudo = uid in Altruix.db_sudo_users
        in_auth_cache = uid in Altruix._auth_users_cache
        owner_count = len(Altruix.config.OWNER_USERS_ID)
        sudo_count = len(Altruix.db_sudo_users)
        auth_count = len(Altruix._auth_users_cache)
        
        # Whitelist Info
        wl_enabled = await Altruix.is_group_wl_enabled()
        wl_groups = await Altruix.get_group_wl_list()
        in_wl_group = await Altruix.is_member_of_whitelisted_group(uid)
        
        # Check env parsing
        from os import getenv
        raw_env = getenv("OWNER_USERS_ID", "NOT SET")
        
        return await m.reply(
            f"**🔍 COMPREHENSIVE DEBUG:**\n\n"
            f"**Your Info:**\n"
            f"• ID: `{uid}`\n"
            f"• is_sudo(): `{is_sudo_result}`\n\n"
            f"**Membership Check:**\n"
            f"• In OWNER_USERS_ID: `{in_owner}`\n"
            f"• In db_sudo_users: `{in_db_sudo}`\n"
            f"• In _auth_users_cache: `{in_auth_cache}`\n\n"
            f"**Whitelist Features:**\n"
            f"• Feature Enabled: `{wl_enabled}`\n"
            f"• Whitelisted Groups: `{len(wl_groups)}` entries\n"
            f"• Member of Whitelist: `{in_wl_group}`\n\n"
            f"**List Sizes:**\n"
            f"• OWNER_USERS_ID: `{owner_count}` entries\n"
            f"• db_sudo_users: `{sudo_count}` entries\n"
            f"• _auth_users_cache: `{auth_count}` entries\n\n"
            f"**Raw .env OWNER_USERS_ID:**\n"
            f"`{raw_env[:200]}`\n\n"
            f"**First 5 OWNER_USERS_ID:**\n"
            f"`{Altruix.config.OWNER_USERS_ID[:5]}`\n\n"
            f"**Bot handlers count:** `{len(Altruix.bot.dispatcher.groups)}`"
        )
    if not payload:
        path_ = "./cache/bot_st_media.*"
        file = (
            glob.glob(path_)[0] if glob.glob(path_) else "./Main/assets/images/logo.jpg"
        )
        from Main.utils.file_helpers import get_user_button_style
        user_style = get_user_button_style(m.from_user.id)
        await m.reply_file(
            file,
            caption=Altruix.get_string("BOT_ST_MSG").format(
                m.from_user.mention, Altruix.config.CUSTOM_BT_START_MSG or ""
            ),
            parse_mode=enums.ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("Altroid", url="https://t.me/AltroidUserbot", style=user_style),
                        InlineKeyboardButton("Alpha-X", url="https://t.me/AlphaXProject", style=user_style)
                    ]
                ]
            ),
            send_msg_if_file_invalid=True,
        )
        if Altruix.training_wheels_protocol and await Altruix.is_sudo(m.from_user.id):
            await m.reply(
                "You'll have to add a user session to disable TWP, would you like to proceed?",
                reply_markup=ReplyKeyboardMarkup(
                    [[KeyboardButton("Yeah sure")]],
                    resize_keyboard=True,
                    one_time_keyboard=True,
                ),
            )
            _ = await m.from_user.listen()
            await m.reply(
                "Alright, let's get started.", reply_markup=ReplyKeyboardRemove()
            )
            await asyncio.sleep(1)
            from Main.utils.file_helpers import get_user_button_style
            user_style = get_user_button_style(m.from_user.id)
            await m.reply(
                "Do you have the string session already generated?.",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton("Yes", callback_data="session_yes", style=user_style),
                            InlineKeyboardButton("No", callback_data="session_no", style=user_style),
                        ]
                    ]
                ),
            )
    elif payload == "add_session":
        await m.reply("Alright, let's get started.", reply_markup=ReplyKeyboardRemove())
        await asyncio.sleep(1)
        from Main.utils.file_helpers import get_user_button_style
        user_style = get_user_button_style(m.from_user.id)
        await m.reply(
            "Do you have the string session already generated?.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("Yes", callback_data="session_yes", style=user_style),
                        InlineKeyboardButton("No", callback_data="session_no", style=user_style),
                    ]
                ]
            ),
        )


@Altruix.bot.on_callback_query(filters.regex("^add_session"))
@log_errors
async def add_session_menu_cb_handler(_, cb: CallbackQuery):
    # CRITICAL: Authorization check - using is_sudo which supports DB users
    user_id = cb.from_user.id
    if not await Altruix.is_sudo(user_id):
        # Additional Log for debugging Group Whitelist
        wl_enabled = await Altruix.is_group_wl_enabled()
        print(f"DEBUG: /add blocked for {user_id}. WL Enabled: {wl_enabled}")
        return await cb.answer(Altruix.get_string("AUTH_SESSION_ADD_DENIED"), show_alert=True)
    
    if cb.message:
        await cb.edit_message_text(
            "Alright, let's get started.", reply_markup=None
        )
    else:
        await cb.answer("Alright, let's get started.", show_alert=True)
    await asyncio.sleep(1)
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)
    
    sender = cb.message.reply if cb.message else cb.answer
    if cb.message:
        await cb.message.reply(
            "Do you have the string session already generated?.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("Yes", callback_data="session_yes", style=user_style),
                        InlineKeyboardButton("No", callback_data="session_no", style=user_style),
                    ]
                ]
            ),
        )
    else:
        await Altruix.bot.send_message(
            cb.from_user.id,
            "Do you have the string session already generated?.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("Yes", callback_data="session_yes", style=user_style),
                        InlineKeyboardButton("No", callback_data="session_no", style=user_style),
                    ]
                ]
            ),
        )


@Altruix.bot.on_callback_query(filters.regex("^session_yes"))
@log_errors
async def add_session_cb_handler(_, cb: CallbackQuery):
    # CRITICAL: Authorization check - using is_sudo
    if not await Altruix.is_sudo(cb.from_user.id):
        return await cb.answer(Altruix.get_string("AUTH_SESSION_ADD_DENIED"), show_alert=True)
    
    if cb.message:
        with contextlib.suppress(Exception):
            await cb.message.delete()
        await cb.message.reply(
            "Alright... send me your string session.\nUse /cancel to cancel the current operation.",
            reply_markup=ForceReply(),
        )
    else:
        await Altruix.bot.send_message(
            cb.from_user.id,
            "Alright... send me your string session.\nUse /cancel to cancel the current operation.",
            reply_markup=ForceReply(),
        )
    # session = await cb.from_user.listen(filters.regex(r"(\S{300,400})",
    # timeout=600))
    while True:
        session: Message = await cb.from_user.listen(filters.text, timeout=600)
        if session.text.startswith("/"):
            await cb.message.reply("The current process was cancelled.")
            return
        if match := re.search(r"(\S{300,400})", session.text):
            session = match[1]
            break
        else:
            await session.reply("Please send me a valid string session.", quote=True)
    status = await cb.message.reply(
        "<code>Processing the given string session...</code>"
    )
    new_session = await Altruix.add_session(session, status, user=cb.from_user, skip_reload=True)
    if not new_session:
        return # add_session already handled the error message/logging

    me = await new_session.get_me()
    full_name = f"{me.first_name or ''} {me.last_name or ''}".strip() or "N/A"
    username = f"@{me.username}" if me.username else "N/A"
    dc_id = getattr(me, "dc_id", "N/A")
    session_idx = len(Altruix.clients)
    
    await new_session.send_message(
        Altruix.bot.me.id,
        "<b>🎉 Account Successfully added!</b>\n\n"
        "<blockquote expandable>"
        f"•  <b>Name:</b> {full_name}\n"
        f"•  <b>User ID:</b> <code>{me.id}</code>\n"
        f"•  <b>Username:</b> {username}\n"
        f"•  <b>DC ID:</b> <code>{dc_id}</code>\n"
        f"•  <b>Session:</b> #{session_idx}\n"
        f"{'🤖' if me.is_bot else '👤'} <b>Type:</b> {'Bot' if me.is_bot else 'User'}\n\n"
        "Your account has been successfully linked to <b>AltruixX</b>. "
        "You can now manage your sessions and use enhanced features via the bot settings.\n\n"
        "Support: @AltroidUserbot"
        "</blockquote>\n",
    )
    
    from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)
    await cb.message.reply(
        "✅ **Session added successfully!**\n\n"
        "Do you want to reload the system modules now to apply changes?\n"
        "*(Choose 'No' if you want to add more sessions first to save time)*",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Yes, Reload Now", callback_data="reload_sys_yes", style=user_style),
                InlineKeyboardButton("No, Later", callback_data="reload_sys_no", style=user_style)
            ]
        ])
    )

@Altruix.bot.on_callback_query(filters.regex(r"^reload_sys_(yes|no)$"))
@log_errors
async def reload_sys_cb_handler(_, cb: CallbackQuery):
    if not await Altruix.is_sudo(cb.from_user.id):
        return await cb.answer(Altruix.get_string("AUTH_BUTTON_DENIED"), show_alert=True)
    
    choice = cb.matches[0].group(1)
    if choice == "yes":
        await cb.message.edit("🔄 Reloading system modules... (Please wait)")
        await Altruix.load_all_modules()
        await cb.message.edit("✅ **System modules reloaded successfully!** All sessions are ready.")
    else:
        await cb.message.edit("⏩ **Reload skipped.** You can add more sessions now.")


# # ============================================================================
# # 🔧 TEMPORARY DEBUG: Fallback handler for /add and /settings
# # This catches commands when is_sudo_filter blocks them (group=99 = lowest priority)
# # REMOVE THIS AFTER DEBUGGING
# # ============================================================================
# @Altruix.bot.on_message(filters.command(["add", "settings"], "/") & filters.private, group=99)
# @log_errors
# async def debug_fallback_handler(_, m: Message):
#     """Temporary: Catches /add and /settings when is_sudo_filter returns False."""
#     uid = m.from_user.id
#     try:
#         is_sudo_result = await Altruix.is_sudo(uid)
#     except Exception as e:
#         is_sudo_result = f"EXCEPTION: {type(e).__name__}: {e}"
    
#     in_owner = uid in Altruix.config.OWNER_USERS_ID
#     in_db_sudo = uid in Altruix.db_sudo_users
#     in_auth_cache = uid in Altruix._auth_users_cache
    
#     await m.reply(
#         f"⚠️ **FILTER BLOCKED YOUR COMMAND**\n\n"
#         f"Command `{m.text}` was blocked by `is_sudo_filter`.\n\n"
#         f"**Your ID:** `{uid}`\n"
#         f"**is_sudo():** `{is_sudo_result}`\n"
#         f"**In OWNER_USERS_ID:** `{in_owner}`\n"
#         f"**In db_sudo_users:** `{in_db_sudo}`\n"
#         f"**In _auth_users_cache:** `{in_auth_cache}`\n"
#         f"**OWNER_USERS_ID[:3]:** `{Altruix.config.OWNER_USERS_ID[:3]}`\n"
#         f"**OWNER_USERS_ID type:** `{type(Altruix.config.OWNER_USERS_ID)}`"
#     )

# end of file