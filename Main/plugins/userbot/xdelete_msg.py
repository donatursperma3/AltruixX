# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.

import time
from Main import Altruix
from pyrogram import Client
from Main.core.types.message import Message
from Main.core.decorators import inline_check
from pyrogram.errors import RPCError

PLUGIN_VERSION = "0.0.1"

@Altruix.register_on_cmd(
    ["del", "delete"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Delete a message by replying to it. If in a group, requires admin permission if deleting others' messages.",
        "example": ".del (replying to a message)",
    },
)
@inline_check
async def delete_msg_cmd(c: Client, m: Message):
    if not m.reply_to_message:
        return await m.handle_message("INVALID_REPLY")

    reply = m.reply_to_message
    
    try:
        await reply.delete()
        await m.delete_if_self()
    except RPCError:
        await m.handle_message("DEL_SUCCESS_FALSE")

@Altruix.register_on_cmd(
    ["sdel", "sdelete"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Silent delete a message by replying to it. No success/fail message, and the command is always deleted.",
        "example": ".sdel (replying to a message)",
    },
)
@inline_check
async def silent_delete_msg_cmd(c: Client, m: Message):
    if not m.reply_to_message:
        return await m.delete_if_self()

    reply = m.reply_to_message
    try:
        await reply.delete()
    except RPCError:
        pass
    await m.delete_if_self()
