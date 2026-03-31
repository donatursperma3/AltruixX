# kiro 1.5.5.12
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.



PLUGIN_VERSION = "0.0.42"
import time
from Main import Altruix
from style import ping_format as pf
from pyrogram import Client, filters
from pyrogram.raw.functions import Ping
from Main.utils.essentials import Essentials
from pyrogram.enums import ParseMode, ButtonStyle
from pyrogram import enums, types
from Main.core.decorators import log_errors, iuser_check
from pyrogram.types import (
    Message, InlineQuery, CallbackQuery, InlineKeyboardButton,
    InlineKeyboardMarkup, InputTextMessageContent, InlineQueryResultArticle)


@Altruix.bot.on_message(
    filters.command("ping", Altruix.bot_handler) & Altruix.is_sudo_filter
)
@log_errors
async def ping_command_handler(c: Client, m: Message):
    start = time.perf_counter()
    await c.invoke(Ping(ping_id=9999999))
    uptime = Essentials.get_readable_time(time.time() - Altruix.start_time)
    end = time.perf_counter()
    ms = round((end - start) * 1000, 2)
    await m.reply(
        Altruix.get_string("PING_TEXT").format(
            pf["ping_emoji1"], ms, pf["ping_emoji2"], uptime
        ),
        reply_markup=InlineKeyboardMarkup(
            [[
                InlineKeyboardButton(
                    await Essentials.get_user_button_style(m.from_user.id, f"{pf['ping_emoji1']} Ping"), "ping",
                    style=enums.ButtonStyle.PRIMARY
                    )
                ]]
        ),
    )


@Altruix.bot.on_callback_query(filters.regex("^ping"))
@log_errors
async def ping_cb_handler(c: Client, cb: CallbackQuery):
    # Security: Verify if user is authorized
    from Main.utils.access_control import is_authorized_user
    if not is_authorized_user(cb.from_user.id, Altruix.config.OWNER_ID, Altruix.config.SUDO_USERS):
        # Extract uid if present in callback_data (format: "ping_{uid}")
        parts = cb.data.split("_")
        uid = parts[1] if len(parts) > 1 else None
        
        if uid:
            from Main.utils.file_helpers import get_user_custom_alert
            alert_data = get_user_custom_alert(uid)
            msg = alert_data.get("text") if alert_data.get("mode") == "custom" else (Altruix.get_string("access_denied") or "⛔ Access denied")
        else:
            msg = (Altruix.get_string("access_denied") or "⛔ Access denied")
            
        return await cb.answer(msg, show_alert=True)

    # Resolve session data
    parts = cb.data.split("_")
    uid = parts[1] if len(parts) > 1 else None
    
    target_client = c # Default to bot
    if hasattr(Altruix, "clients") and Altruix.clients:
        for cli in Altruix.clients:
            if hasattr(cli, "me") and cli.me and str(cli.me.id) == uid:
                target_client = cli
                break

    start_time_val = getattr(target_client, "start_time", Altruix.start_time)
    uptime = Essentials.get_readable_time(time.time() - start_time_val)
    
    start = time.perf_counter()
    await target_client.invoke(Ping(ping_id=9999999))
    end = time.perf_counter()
    ms = round((end - start) * 1000, 2)
    
    text = Altruix.get_string("PING_TEXT").format(
        pf["ping_emoji1"], ms, pf["ping_emoji2"], uptime
    )
    await cb.answer(Essentials.clean_html(text), show_alert=True)
    await cb.edit_message_text(
        Altruix.get_string(
            "PING_TEXT", args=(pf["ping_emoji1"], ms, pf["ping_emoji2"], uptime)
        ),
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton(
                await Essentials.get_user_button_style(cb.from_user.id, f"{pf['ping_emoji1']} Ping"), cb.data,
                style=enums.ButtonStyle.PRIMARY
                )]]
        ),
    )


@Altruix.bot.on_inline_query(filters.regex("^ping"))
@log_errors
@iuser_check
async def ping_inline_handler(c: Client, iq: InlineQuery):
    # Extract session uid if provided (format: "ping_{uid}")
    query_parts = iq.query.split("_")
    uid = query_parts[1] if len(query_parts) > 1 else str(iq.from_user.id)
    
    # Resolve session data
    target_client = c # Default to bot
    if hasattr(Altruix, "clients") and Altruix.clients:
        for cli in Altruix.clients:
            if hasattr(cli, "me") and cli.me and str(cli.me.id) == uid:
                target_client = cli
                break

    start_time_val = getattr(target_client, "start_time", Altruix.start_time)
    uptime = Essentials.get_readable_time(time.time() - start_time_val)
    
    start = time.perf_counter()
    await target_client.invoke(Ping(ping_id=9999999))
    end = time.perf_counter()
    ms = round((end - start) * 1000, 2)
    
    await iq.answer(
        [
            InlineQueryResultArticle(
                id=1,
                title=f"{pf['ping_emoji1']} Pong!",
                description=f"{ms} ms\n{uptime}",
                input_message_content=InputTextMessageContent(
                    "<b>{} Pong!</b>\n<code>{} ms</code>\n<b>{} Uptime:</b> <code>{}</code>".format(
                        pf["ping_emoji1"], ms, pf["ping_emoji2"], uptime
                    )
                ),
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton(
                        await Essentials.get_user_button_style(iq.from_user.id, f"{pf['ping_emoji1']} Ping"), f"ping_{uid}",
                        style=enums.ButtonStyle.PRIMARY
                        )]]
                ),
            )
        ],
        cache_time=0,
        is_personal=True,
        switch_pm_text=f"{pf['ping_emoji1']} Ping",
        switch_pm_parameter="ping",
    )

import random

@Altruix.bot.on_inline_query(filters.regex("^pink"))
@log_errors
@iuser_check
async def pink_inline_handler(c: Client, iq: InlineQuery):
    # Extract session uid and chat_id from query text (format: "pink_{uid}_{chat_id}")
    query_parts = iq.query.split("_")
    uid = query_parts[1] if len(query_parts) > 1 else str(iq.from_user.id)
    chat_id = query_parts[2] if len(query_parts) > 2 else "0"
    
    # Resolve session data
    target_client = c # Default to bot
    if hasattr(Altruix, "clients") and Altruix.clients:
        for cli in Altruix.clients:
            if hasattr(cli, "me") and cli.me and str(cli.me.id) == uid:
                target_client = cli
                break

    start_time_val = getattr(target_client, "start_time", Altruix.start_time)
    uptime = Essentials.get_readable_time(time.time() - start_time_val)
    
    start = time.perf_counter()
    await target_client.invoke(Ping(ping_id=9999999))
    end = time.perf_counter()
    ms = round((end - start) * 1000, 2)
    
    styles = [ButtonStyle.PRIMARY, ButtonStyle.SUCCESS, ButtonStyle.DANGER, ButtonStyle.DEFAULT]
    btn_style = random.choice(styles)
    
    text = f"""<blockquote expandable>─────────────────
⚡️ <b>PONG!</b>  [● System OK]
  ├─ • <b>Latency:</b> {ms} ms 
  ├─ • <b>Uptime:</b> {uptime}  [● Online]
  └─ • <b>React:</b> —
  ─────────────────</blockquote>"""

    # callback_data format: "pkrep_{uid}_{chat_id}" and "pkreac_{uid}_{chat_id}"
    # (shortened to stay within 64-byte Telegram limit)
    await iq.answer(
        [
            InlineQueryResultArticle(
                id=1,
                title=f"🌸 Pink Ping!",
                description=f"{ms} ms\n{uptime}",
                input_message_content=InputTextMessageContent(text),
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🚀 Pink", callback_data=f"pkrep_{uid}_{chat_id}", style=btn_style),
                      InlineKeyboardButton("🙈 React", callback_data=f"pkreac_{uid}_{chat_id}", style=btn_style)]]
                ),
            )
        ],
        cache_time=0,
        is_personal=True,
    )

@Altruix.bot.on_callback_query(filters.regex("^pkrep_"))
@log_errors
async def pink_reping_bot_cb(c: Client, cb: CallbackQuery):
    from Main.utils.access_control import is_authorized_user
    if not is_authorized_user(cb.from_user.id, Altruix.config.OWNER_ID, Altruix.config.SUDO_USERS):
        # Extract uid (target session ID) from callback_data (format: "pkrep_{uid}_{chat_id}")
        parts = cb.data.split("_")
        uid = parts[1] if len(parts) > 1 else None
        
        if uid:
            from Main.utils.file_helpers import get_user_custom_alert
            alert_data = get_user_custom_alert(uid)
            msg = alert_data.get("text") if alert_data.get("mode") == "custom" else (Altruix.get_string("access_denied") or "⛔ Access denied")
        else:
            msg = (Altruix.get_string("access_denied") or "⛔ Access denied")
            
        return await cb.answer(msg, show_alert=True)
    
    # Extract from callback_data (format: "pkrep_{uid}_{chat_id}")
    parts = cb.data.split("_")
    uid = parts[1] if len(parts) > 1 else "0"
    chat_id = parts[2] if len(parts) > 2 else "0"
    
    # Resolve session data
    target_client = c # Default to bot
    if hasattr(Altruix, "clients") and Altruix.clients:
        for cli in Altruix.clients:
            if hasattr(cli, "me") and cli.me and str(cli.me.id) == uid:
                target_client = cli
                break

    start_time_val = getattr(target_client, "start_time", Altruix.start_time)
    uptime = Essentials.get_readable_time(time.time() - start_time_val)
    
    start = time.perf_counter()
    await target_client.invoke(Ping(ping_id=9999999))
    end = time.perf_counter()
    ms = round((end - start) * 1000, 2)
    
    styles = [ButtonStyle.PRIMARY, ButtonStyle.SUCCESS, ButtonStyle.DANGER, ButtonStyle.DEFAULT]
    btn_style = random.choice(styles)
    
    text = f"""<blockquote expandable>─────────────────
⚡️ <b>PONG!</b>  [● System OK]
  ├─ • <b>Latency:</b> {ms} ms 
  ├─ • <b>Uptime:</b> {uptime}  [● Online]
  └─ • <b>React:</b> —
  ─────────────────</blockquote>"""

    try:
        await cb.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🚀 Pink", callback_data=f"pkrep_{uid}_{chat_id}", style=btn_style),
                  InlineKeyboardButton("🙈 React", callback_data=f"pkreac_{uid}_{chat_id}", style=btn_style)]]
            ),
        )
        await cb.answer("Pink Pinged!", show_alert=False)
    except Exception as e:
        await cb.answer("Already latest state or too fast!", show_alert=False)

@Altruix.bot.on_callback_query(filters.regex("^pkreac_"))
@log_errors
async def pink_react_bot_cb(c: Client, cb: CallbackQuery):
    from Main.utils.access_control import is_authorized_user
    if not is_authorized_user(cb.from_user.id, Altruix.config.OWNER_ID, Altruix.config.SUDO_USERS):
        # Extract uid (target session ID) from callback_data (format: "pkreac_{uid}_{chat_id}")
        parts = cb.data.split("_")
        uid = parts[1] if len(parts) > 1 else None
        
        if uid:
            from Main.utils.file_helpers import get_user_custom_alert
            alert_data = get_user_custom_alert(uid)
            msg = alert_data.get("text") if alert_data.get("mode") == "custom" else (Altruix.get_string("access_denied") or "⛔ Access denied")
        else:
            msg = (Altruix.get_string("access_denied") or "⛔ Access denied")
            
        return await cb.answer(msg, show_alert=True)
    
    # Extract from callback_data (format: "pkreac_{uid}_{chat_id}")
    parts = cb.data.split("_")
    uid = parts[1] if len(parts) > 1 else "0"
    chat_id_str = parts[2] if len(parts) > 2 else "0"
    
    # Find the exact userbot client that ran the .pink command
    userbot_client = None
    if hasattr(Altruix, "clients") and Altruix.clients:
        for cli in Altruix.clients:
            if hasattr(cli, "me") and cli.me and str(cli.me.id) == uid:
                userbot_client = cli
                break
    
    if not userbot_client:
        return await cb.answer("⚠️ Session userbot tidak ditemukan!", show_alert=True)
    
    try:
        target_chat_id = int(chat_id_str)
    except (ValueError, TypeError):
        return await cb.answer("⚠️ Chat ID tidak valid!", show_alert=True)
    
    emojis = ['👍', '❤', '🔥', '🎉', '🤩', '⚡', '🙈', '💯']
    rand_emoji = random.choice(emojis)
    try:
        # cb.message is None for inline messages (bot not in group)
        # Use chat_id from callback_data and search for the via_bot message
        if cb.message and cb.message.chat:
            msg_chat_id = cb.message.chat.id
            msg_id = cb.message.id
        else:
            # Find the latest via_bot message from the bot in the target chat
            msg_chat_id = target_chat_id
            msg_id = None
            bot_username = Altruix.bot_manager.get_bot_username(int(uid))
            async for msg in userbot_client.search_messages(target_chat_id, limit=5, from_user="me"):
                if msg.via_bot and msg.via_bot.username == bot_username:
                    msg_id = msg.id
                    break
            if not msg_id:
                return await cb.answer("⚠️ Pesan inline tidak ditemukan di chat!", show_alert=True)
        
        await userbot_client.send_reaction(chat_id=msg_chat_id, message_id=msg_id, emoji=rand_emoji)
        react_status = rand_emoji
        await cb.answer(f"Reacted with {rand_emoji}", show_alert=False)
    except Exception as e:
        react_status = "not allowed"
        await cb.answer(f"⚠️ Reaction failed!\nError: {str(e)[:50]}", show_alert=True)
    
    # Update the message text to show the react status
    # Resolve session data
    target_client = c # Default to bot
    if hasattr(Altruix, "clients") and Altruix.clients:
        for cli in Altruix.clients:
            if hasattr(cli, "me") and cli.me and str(cli.me.id) == uid:
                target_client = cli
                break

    start_time_val = getattr(target_client, "start_time", Altruix.start_time)
    uptime = Essentials.get_readable_time(time.time() - start_time_val)
    
    start = time.perf_counter()
    await target_client.invoke(Ping(ping_id=9999999))
    end = time.perf_counter()
    ms = round((end - start) * 1000, 2)
    
    styles = [ButtonStyle.PRIMARY, ButtonStyle.SUCCESS, ButtonStyle.DANGER, ButtonStyle.DEFAULT]
    btn_style = random.choice(styles)
    
    updated_text = f"""<blockquote expandable>─────────────────
⚡️ <b>PONG!</b>  [● System OK]
  ├─ • <b>Latency:</b> {ms} ms 
  ├─ • <b>Uptime:</b> {uptime}  [● Online]
  └─ • <b>React:</b> {react_status}
  ─────────────────</blockquote>"""
    
    try:
        await cb.edit_message_text(
            updated_text,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🚀 Pink", callback_data=f"pkrep_{uid}_{chat_id_str}", style=btn_style),
                  InlineKeyboardButton("🙈 React", callback_data=f"pkreac_{uid}_{chat_id_str}", style=btn_style)]]
            ),
        )
    except Exception:
        pass
