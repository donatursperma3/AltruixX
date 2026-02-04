# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.

from Main import Altruix
from pyrogram import Client, filters
from Main.core.decorators import log_errors
from pyrogram.types import Message
from pyrogram.errors import RPCError

PLUGIN_VERSION = "0.0.1"

@Altruix.bot.on_message(
    filters.command(["del", "delete"], Altruix.bot_handler) & filters.user([Altruix.config.OWNER_ID] + Altruix.config.SUDO_USERS)
)
@log_errors
async def bot_delete_msg_cmd(c: Client, m: Message):
    if not m.reply_to_message:
        return await m.reply(Altruix.get_string("INVALID_REPLY"))

    try:
        await m.reply_to_message.delete()
        await m.delete()
    except RPCError:
        await m.reply(Altruix.get_string("DEL_SUCCESS_FALSE"))

@Altruix.bot.on_message(
    filters.command(["sdel", "sdelete"], Altruix.bot_handler) & filters.user([Altruix.config.OWNER_ID] + Altruix.config.SUDO_USERS)
)
@log_errors
async def bot_silent_delete_msg_cmd(c: Client, m: Message):
    if not m.reply_to_message:
        return await m.delete()

    try:
        await m.reply_to_message.delete()
    except RPCError:
        pass
    await m.delete()
