# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.


import asyncio
import traceback
import sys
import subprocess
import os
from Main import Altruix
from style import ping_format as pf
from pyrogram import Client, filters
from Main.core.types.message import Message
from Main.utils.file_helpers import get_user_button_style
from Main.core.decorators import log_errors, iuser_check, inline_check
from pyrogram.types import (
    InlineQuery, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    InputTextMessageContent, InlineQueryResultArticle)


@Altruix.bot.on_callback_query(filters.regex("^(restart|reload)_confirm(_hard|_soft)?$"))
@log_errors
@iuser_check
async def restart_cb_handler(_, cb: CallbackQuery):
    await cb.answer("Hang on..", show_alert=True)
    _type = cb.matches[0].group(1)
    _mode = cb.matches[0].group(2) or ""
    
    Altruix.log(f"🔄 Power Controls | Callback Received: type={_type}, mode={_mode}", level=20)

    if _type == "reload":
        await cb.edit_message_text("<b>♻️ Reloading Plugins...</b>\nUpdating command registry. Please wait.")
        await Altruix.reboot(soft=True, last_msg=cb)
    elif _mode == "_hard":
        Altruix.log("⚠️ Power Controls | Hard Restart (Process Swap) Initiated...", level=20)
        await cb.edit_message_text("<b>⚙️ Hard Restart Initiated...</b>\nReplacing process. Please wait.")
        args = [sys.executable, "-m", "Main"]
        if os.name == 'nt':
            Altruix.log(f"💻 Power Controls | Spawning new console on Windows: {' '.join(args)}", level=20)
            subprocess.Popen(args, creationflags=subprocess.CREATE_NEW_CONSOLE)
            Altruix.log("👋 Power Controls | Exiting parent process.", level=20)
            os._exit(0)
        else:
            Altruix.log(f"🐧 Power Controls | Executing replace on Linux: {' '.join(args)}", level=20)
            os.execv(sys.executable, args)
    else:
        # Default to Soft Restart (Optimized)
        Altruix.log("🚀 Power Controls | Soft Restart (Optimized) Initiated...", level=20)
        await cb.edit_message_text("<b>🚀 Soft Restart Initiated...</b>\nRestarting sessions in parallel. Please wait.")
        await Altruix.reboot(soft=False, last_msg=cb)


@Altruix.bot.on_callback_query(filters.regex("^(restart|reload)_cancel"))
@log_errors
@iuser_check
async def cancel_restart_cb_handler(c: Client, cb: CallbackQuery):
    Altruix.log(f"🔘 Callback Received: {cb.data} (Cancel) from {cb.from_user.id}", level=20)
    await cb.answer("Alright", show_alert=True)
    _type = cb.matches[0].group(1)
    soft = _type != "restart"
    await cb.edit_message_text(
        f"<i>Aborted {'reload' if soft else 'restart'}.</i>",
    )


@Altruix.bot.on_message(
    filters.command(["restart", "reload"], "/") & filters.user(Altruix.config.OWNER_USERS_ID)
)
@log_errors
async def restart_command_handler(_, m: Message):
    reload_only = m.command[0] == "reload"
    Altruix.log(f"🛠 Power Controls | Command Triggered: {m.command[0]} by {m.from_user.id}", level=20)
    user_style = get_user_button_style(m.from_user.id)
    
    if reload_only:
        text = "<blockquote expandable><b>♻️ Are you sure about reloading Altroid-X?</b>\n\n<i>This will only refresh the plugin files without disconnecting.</i></blockquote>"

        buttons = [
            [InlineKeyboardButton("Yes, Reload", "reload_confirm", style=user_style)],
            [InlineKeyboardButton("No, Cancel", "reload_cancel", style=user_style)]
        ]
    else:
        text = (
            f"<blockquote expandable>"
            "<b>🔄 AltruixX Restart Controls</b>\n\n"
            "Pilih metode restart yang diinginkan:\n\n"
            "🚀 <b>Soft Restart (Optimized):</b> Restart koneksi semua session secara paralel. Sangat cepat.\n"
            "⚙️ <b>Full Restart (Hard):</b> Mengganti proses sistem secara keseluruhan (process swap)."
            f"</blockquote>"
        )
        buttons = [
            [InlineKeyboardButton("🚀 Soft Restart (Fast)", "restart_confirm_soft", style=user_style)],
            [InlineKeyboardButton("⚙️ Full Restart (Hard)", "restart_confirm_hard", style=user_style)],
            [InlineKeyboardButton("❌ Cancel", "restart_cancel", style=user_style)]
        ]
        
    await m.reply(
        text,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


@Altruix.bot.on_inline_query(filters.regex("^(restart|reload)"))
@log_errors
@iuser_check
async def ping_inline_handler(_, iq: InlineQuery):
    Altruix.log(f"📥 Inline Query Received: {iq.query} from {iq.from_user.id}", level=20)
    soft = iq.query.lower() == "reload"
    user_style = get_user_button_style(iq.from_user.id)
    if soft:
        text = "<blockquote expandable><b>♻️ Are you sure about reloading Altroid-X?</b>\n\n<i>This will only refresh the plugin files without disconnecting.</i></blockquote>"
        buttons = [
            [InlineKeyboardButton("Yes, Reload", "reload_confirm", style=user_style)],
            [InlineKeyboardButton("No, Cancel", "reload_cancel", style=user_style)]
        ]
    else:
        text = (
            f"<blockquote expandable>"
            "<b>🔄 AltruixX Restart Controls</b>\n\n"
            "Pilih metode restart yang diinginkan:\n\n"
            "🚀 <b>Soft Restart (Optimized):</b> Restart koneksi secara paralel.\n"
            "⚙️ <b>Full Restart (Hard):</b> Mengganti proses sistem."
            f"</blockquote>"
        )
        buttons = [
            [InlineKeyboardButton("🚀 Soft Restart", "restart_confirm_soft", style=user_style)],
            [InlineKeyboardButton("⚙️ Full Restart", "restart_confirm_hard", style=user_style)],
            [InlineKeyboardButton("❌ Cancel", "restart_cancel", style=user_style)]
        ]

    Altruix.log("✅ Sending Inline Query results", level=20)
    await iq.answer(
        [
            InlineQueryResultArticle(
                id=1,
                title=f"{'Reload' if soft else 'Restart'} confirmation message",
                description=Altruix.get_string("INTERNAL_FUNCTION", args=pf["ping_emoji2"]),
                input_message_content=InputTextMessageContent(text),
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        ],
        cache_time=0,
        is_personal=True,
    )


@Altruix.register_on_cmd(
    ["restart", "reload"],
    cmd_help={"help": "Restart or reload the bot."},
    bot_mode_unsupported=True,
)
async def restart_ub_cmd(c: Client, m: Message):
    reload = "reload" in m.text.lower()
    user_id = m.from_user.id if m.from_user else c.me.id
    Altruix.log(f"🚀 UB Command Triggered: {'.reload' if reload else '.restart'} by {user_id}", level=20)
    
    bot_username = Altruix.bot_manager.get_bot_username(c.me.id)
    Altruix.log(f"🔍 Using Bot Username: @{bot_username} for inline query", level=20)
    
    try:
        results = await c.get_inline_bot_results(
            bot_username, "reload" if reload else "restart"
        )
        Altruix.log(f"✅ Inline results fetched, sending to chat...", level=20)
        await c.send_inline_bot_result(
            m.chat.id, results.query_id, results.results[0].id
        )
    except Exception as e:
        Altruix.log(f"❌ Failed to trigger inline restart: {e}", level=40)
        try:
            await m.edit(f"❌ <b>Error:</b> <code>{e}</code>")
        except Exception:
            pass
    
    try:
        await m.delete()
    except Exception:
        pass
