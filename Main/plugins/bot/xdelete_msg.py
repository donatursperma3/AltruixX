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
from Main.utils.access_control import is_authorized_user

PLUGIN_VERSION = "0.0.1"


@Altruix.register_on_cmd(
    ["del", "delete"],
    cmd_help={
        "help": "Delete the replied message and the command itself.",
        "usage": "/del [reply_to_message]",
        "example": "/del",
        "detail": "Menghapus pesan yang dibalas serta pesan perintah ini."
    },
    group_only=False,
    requires_input=False,
)
@log_errors
async def bot_delete_msg_cmd(c: Client, m: Message):
    if not is_authorized_user(m.from_user.id, Altruix.config.OWNER_USERS_ID, Altruix.config.SUDO_USERS_ID):
        return

    if not m.reply_to_message:
        return await m.reply(Altruix.get_string("INVALID_REPLY"))

    try:
        await m.reply_to_message.delete()
        await m.delete()
    except RPCError:
        await m.reply(Altruix.get_string("DEL_SUCCESS_FALSE"))

@Altruix.register_on_cmd(
    ["sdel", "sdelete"],
    cmd_help={
        "help": "Silently delete the replied message and the command.",
        "usage": "/sdel [reply_to_message]",
        "example": "/sdel",
        "detail": "Menghapus pesan yang dibalas dan perintah ini tanpa notifikasi error jika gagal."
    },
    group_only=False,
    requires_input=False,
)
@log_errors
async def bot_silent_delete_msg_cmd(c: Client, m: Message):
    if not is_authorized_user(m.from_user.id, Altruix.config.OWNER_USERS_ID, Altruix.config.SUDO_USERS_ID):
        return

    if not m.reply_to_message:
        return await m.delete()

    try:
        await m.reply_to_message.delete()
    except RPCError:
        pass
    await m.delete()
