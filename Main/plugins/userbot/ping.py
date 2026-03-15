# kiro_1.5.5.12
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.


PLUGIN_VERSION = "0.0.16"
import time
from Main import Altruix
from pyrogram import Client
from style import ping_format as pf
from pyrogram.raw.functions import Ping
from Main.core.types.message import Message
from Main.utils.essentials import Essentials
from Main.core.decorators import inline_check
from pyrogram.errors import ChatSendInlineForbidden


@Altruix.register_on_cmd(
    ["ping", "pong"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Ping userbot",
        "example": "ping",
        "user_args": [
            {
                "arg": "c",
                "help": "show the ping output as a regular text edit.",
                "requires_input": False,
            },
        ],
    },
)
@inline_check
async def ping_ub_cmd(c: Client, m: Message):
    # ✅ DEBUG: Log function entry FIRST to verify registration
    Altruix.log(f"🎯 [PING] Function called! User: {c.me.id}, Chat: {m.chat.id}", level=20)
    user_args = m.user_args
    
    if "c" not in user_args:
        # with inline result
        rm = m.reply_to_message
        try:
            bot_username = Altruix.bot_manager.get_bot_username(c.me.id)
            results = await c.get_inline_bot_results(bot_username, "ping")
            await c.send_inline_bot_result(
                chat_id=m.chat.id,
                query_id=results.query_id,
                result_id=results.results[0].id,
                reply_to_message_id=rm.id if rm else m.id,
            )
            await m.delete_if_self()
        except ChatSendInlineForbidden:
            start = time.perf_counter()
            await c.invoke(Ping(ping_id=9999999))
            uptime = Essentials.get_readable_time(time.time() - Altruix.start_time)
            end = time.perf_counter()
            ms = round((end - start) * 1000, 2)
            await m.handle_message(
                "PING_TEXT",
                string_args=(pf["ping_emoji1"], ms, pf["ping_emoji2"], uptime),
            )

    else:
        # without inline result
        start = time.perf_counter()
        await c.invoke(Ping(ping_id=9999999))
        uptime = Essentials.get_readable_time(time.time() - Altruix.start_time)
        end = time.perf_counter()
        ms = round((end - start) * 1000, 2)
        await m.handle_message(
            "PING_TEXT", string_args=(pf["ping_emoji1"], ms, pf["ping_emoji2"], uptime)
        )



import random
import time
from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.raw.functions import Ping
from Main import Altruix
from Main.core.types.message import Message
from Main.utils.essentials import Essentials
from Main.core.decorators import inline_check

from pyrogram.enums import ButtonStyle

@Altruix.register_on_cmd(
    ["pink"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Aesthetic Pink Ping",
        "example": "pink",
    },
)
@inline_check
async def pink_ub_cmd(c: Client, m: Message):
    rm = m.reply_to_message
    try:
        bot_username = Altruix.bot_manager.get_bot_username(c.me.id)
        results = await c.get_inline_bot_results(bot_username, f"pink_{c.me.id}_{m.chat.id}")
        await c.send_inline_bot_result(
            chat_id=m.chat.id,
            query_id=results.query_id,
            result_id=results.results[0].id,
            reply_to_message_id=rm.id if rm else m.id,
        )
        await m.delete_if_self()
    except ChatSendInlineForbidden:
        # Fallback when inline bot results cannot be sent
        start = time.perf_counter()
        await c.invoke(Ping(ping_id=9999999))
        uptime = Essentials.get_readable_time(time.time() - Altruix.start_time)
        end = time.perf_counter()
        ms = round((end - start) * 1000, 2)
        
        text = f"""<blockquote expandable>─────────────────
⚡️ <b>PONG!</b>  [● System OK]
  ├─ • 🕹 <b>Latency:</b> {ms} ms 
  ├─ • 🧟 <b>Uptime:</b> {uptime}  [● Online]
  └─ • 🙊 <b>React:</b> not allowed
  ─────────────────</blockquote>
  
<i>⚠️ Inline buttons / Bot mode disabled in this chat.</i>"""
        await m.reply(text)
    except Exception as e:
        await m.reply(f'Error: {e}')

