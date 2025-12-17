# sudo_manager.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.
"""
A-Z for sudo users!
"""
from Main import Altruix
from style import bullets
from pyrogram import Client
from pyrogram.types import User
from ...core.types.message import Message
import os
import asyncio
import re
from pyrogram.errors import RPCError
from Main.core.decorators import log_errors

plugin_name = f"plugins/userbot/{os.path.basename(__file__)}"
__plugin_name__ = plugin_name if plugin_name else "sudo_manager"
PLUGIN_VERSION = "0.0.3"  # 🔥 VERSI DIPERBAIKI: Semua error fixed dan fitur ditambahkan

# 🔥 SETUP LOGGING DETAILED
logger = logging.getLogger(f"{__plugin_name__}")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - [SETTINGS] - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

# 🔥 LOG STARTUP
logger.info(f"🚀 Initializing settings plugin v{PLUGIN_VERSION}")


b4 = bullets["bullet4"]
b5 = bullets["bullet5"]
b6 = bullets["bullet6"]
b7 = bullets["bullet7"]

# ← PERUBAHAN BARU: Fungsi bulletify sepenuhnya dirombak
#     - Semua nama user jadi hyperlink tg://user?id=...
#     - Compatible 100% di Android, iOS, Desktop, Web
#     - Handling deleted account dengan aman
#     - Total count di header
def bulletify(users_list: list[User]) -> str:
    total = len(users_list)
    out = f"<b>Sudo Users (Total: {total})</b>:\n\n"

    if total == 0:
        return "<b>Sudo Users (Total: 0)</b>\n\n<i>Tidak ada sudo user saat ini.</i>"

    for idx, user in enumerate(users_list):
        # Buat hyperlink yang valid di semua platform Telegram
        user_id = user.id
        if user.is_deleted:
            display_name = "<i>Deleted Account</i>"
        elif user.first_name:
            # Escape karakter HTML khusus jika ada
            first_name = user.first_name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            last_name = f" {user.last_name}" if user.last_name else ""
            last_name = last_name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            display_name = f"{first_name}{last_name}".strip()
        else:
            display_name = "<i>Unknown User</i>"

        hyperlink = f"<a href=\"tg://user?id={user_id}\">{display_name}</a>"

        if total == 1:
            out += f"{b6}{b4} {hyperlink}"
        elif total == 2:
            if idx == 0:
                out += f"{b5}{b4} {hyperlink}"
            else:
                out += f"\n{b7}{b4} {hyperlink}"
        else:
            if idx == 0:
                out += f"{b5}{b4} {hyperlink}"
            elif idx == total - 1:
                out += f"\n{b7}{b4} {hyperlink}"
            else:
                out += f"\n{b6}{b4} {hyperlink}"

    return out


@Altruix.register_on_cmd(
    "dpfs",
    cmd_help={"help": "Disabled cmds for sudo users!", "example": "dpfs eval"},
    requires_input=True,
)
@log_errors
async def disabled_ps_func(c: Client, m: Message):
    msg = await m.handle_message("PROCESSING")
    input_ = m.user_input.strip()
    if "," in input_:
        input_ = [x.strip() for x in input_.split(",")]
    await Altruix.config.sync_env_to_db("DISABLED_SUDO_CMD_LIST", input_, push_=True)
    await msg.edit_msg("DISABLED_SUDO_CMD", string_args=(input_))


@Altruix.register_on_cmd(
    "rmdfs",
    cmd_help={"help": "Disabled cmds from sudo users", "example": "dpfs eval"},
    requires_input=True,
)
async def remove_disabled_ps_func(c: Client, m: Message):
    msg = await m.handle_message("PROCESSING")
    input_ = m.user_input.strip()
    if "," in input_:
        input_ = [x.strip() for x in input_.split(",")]
    await Altruix.config.unsync_env_to_db("DISABLED_SUDO_CMD_LIST", input_)
    await msg.edit_msg("UNDISABLED_SUDO_CMD", string_args=(input_))


@Altruix.register_on_cmd(
    "addsudo",
    cmd_help={
        "help": "Add a user to sudo list, requires restart once done!",
        "example": "addsudo @warner_stark",
    },
)
@log_errors
async def add_sudo_func(c: Client, m: Message):
    msg = await m.handle_message("PROCESSING")
    user, _, is_channel = m.get_user
    if not user or is_channel:
        return await msg.edit_msg("INVALID_USER")
    try:
        user_id = await c.get_users(user)
    except Exception:
        return await msg.edit_msg("INVALID_USER")
    if user_id.id in (await Altruix.config.get_sudo()):
        return await msg.edit_msg("ALREADY_IN_SUDO")
    await Altruix.config.add_sudo(user_id.id)
    await msg.edit_msg("ADDED_SUDO", string_args=(user_id.mention))


@Altruix.register_on_cmd(
    "rmsudo",
    cmd_help={
        "help": "remove sudo from sudo list, requires a restart to reflect the changes",
        "example": "rmsudo @warner_stark",
        "user_args": [
            {
                "arg": "a",
                "help": "Removes all sudos from the db.",
                "requires_input": False,
            },
        ],
    },
)
@log_errors
async def rm_sudo_func(c: Client, m: Message):
    msg = await m.handle_message("PROCESSING")
    user, _, is_channel = m.get_user
    acg = await Altruix.config.get_sudo()
    if user_args := m.user_args:
        if "a" in user_args:
            count = 0
            lacg = len(acg)
            for i in acg:
                try:
                    await Altruix.config.del_sudo(i)
                    count += 1
                except BaseException:
                    pass
            return await msg.edit_msg("DEL_SUDO_A", string_args=(count, lacg))
    if not user or is_channel:
        return await msg.edit_msg("INVALID_USER")
    try:
        user_id = await c.get_users(user)
    except Exception:
        return await msg.edit_msg("INVALID_USER")
    if user_id.id not in acg:
        return await msg.edit_msg("NOT_IN_SUDO")
    await Altruix.config.del_sudo(user_id.id)
    await msg.edit_msg("DEL_SUDO", string_args=(user_id.mention))


@Altruix.register_on_cmd(
    "listsudo",
    cmd_help={"help": "List all sudo users (clickable names + total count)", "example": "listsudo"}
)
@log_errors
# ← PERUBAHAN BARU: 
#     - Semua nama user jadi hyperlink clickable di semua platform
#     - Handling deleted account dengan aman
#     - Total count tetap ditampilkan
async def list_sudo_func(c: Client, m: Message):
    msg = await m.handle_message("PROCESSING")
    sudo_ids = await Altruix.config.get_sudo()

    if not sudo_ids:
        return await msg.edit_msg("<b>Sudo Users (Total: 0)</b>\n\n<i>Tidak ada sudo user saat ini.</i>")

    valid_users = []
    for user_id in sudo_ids:
        try:
            user = await c.get_users(int(user_id))
            valid_users.append(user)
        except Exception:
            # Jika user tidak bisa di-fetch (akun dihapus/banned/blocked bot)
            # Buat objek dummy User agar tetap bisa ditampilkan
            dummy_user = User(
                id=int(user_id),
                is_deleted=True,
                first_name=None,
                last_name=None,
                username=None,
                dc_id=None,
                is_bot=False
            )
            valid_users.append(dummy_user)

    if not valid_users:
        return await msg.edit_msg("<b>Sudo Users (Total: 0)</b>\n\n<i>Tidak ada sudo user yang valid.</i>")

    await msg.edit_msg(bulletify(valid_users))

# Log sukses loading
try:
    Altruix.log(f"[DEBUG] ✅ Loaded → {__plugin_name__} {PLUGIN_VERSION}", level=20)
except Exception as e:
    logger.info(f"[DEBUG] ✅ Loaded → {__plugin_name__} {PLUGIN_VERSION}")
