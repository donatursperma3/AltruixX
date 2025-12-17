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

import logging

plugin_name = f"plugins/userbot/{os.path.basename(__file__)}"
__plugin_name__ = plugin_name if plugin_name else "sudo_manager"
PLUGIN_VERSION = "0.0.4"  # 🔥 VERSI DIPERBAIKI: Semua error fixed dan fitur ditambahkan

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



# ← PERUBAHAN BARU: Fungsi bulletify diganti total dengan format box terpisah aktif/deleted
def format_sudo_list(active_users: list[User], deleted_users: list[User]) -> str:
    total = len(active_users) + len(deleted_users)
    out = f"<b>Sudo Users (Total: {total})</b>:\n\n"

    # === Bagian Aktif Users ===
    if active_users:
        out += f"<b>Aktif Users ({len(active_users)})</b>:\n"
        for i, user in enumerate(active_users):
            # Escape karakter HTML
            first_name = user.first_name or ""
            last_name = f" {user.last_name}" if user.last_name else ""
            display_name = (first_name + last_name).strip()
            display_name = display_name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

            hyperlink = f"<a href=\"tg://user?id={user.id}\">{display_name}</a>"

            if i == 0:
                out += f"┏◈ {hyperlink}\n"
            elif i == len(active_users) - 1:
                out += f"┗◈ {hyperlink}\n"
            else:
                out += f"┣◈ {hyperlink}\n"
        out += "\n"
    else:
        out += "<b>Aktif Users (0)</b>:\n<i>Tidak ada user aktif.</i>\n\n"

    # === Bagian Deleted Users ===
    if deleted_users:
        out += f"<b>Deleted Users ({len(deleted_users)})</b>:\n"
        for i, user in enumerate(deleted_users):
            hyperlink = f"<a href=\"tg://user?id={user.id}\">Deleted Account</a>"

            if i == 0:
                out += f"┏◈ {hyperlink}\n"
            elif i == len(deleted_users) - 1:
                out += f"┗◈ {hyperlink}\n"
            else:
                out += f"┣◈ {hyperlink}\n"
    else:
        out += "<b>Deleted Users (0)</b>:\n<i>Tidak ada akun terhapus.</i>"

    return out


@Altruix.register_on_cmd(
    "dpfs",
    cmd_help={"help": "Disabled cmds for sudo users!", "example": "dpfs eval"},
    requires_input=True,
)
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
    cmd_help={"help": "List all sudo users (separated active & deleted)", "example": "listsudo"}
)
# ← PERUBAHAN BARU: Pisah aktif vs deleted, format box rapi, hyperlink tetap jalan
async def list_sudo_func(c: Client, m: Message):
    msg = await m.handle_message("PROCESSING")
    sudo_ids = await Altruix.config.get_sudo()

    if not sudo_ids:
        return await msg.edit_msg(
            "<b>Sudo Users (Total: 0)</b>\n\n"
            "<b>Aktif Users (0)</b>:\n<i>Tidak ada user aktif.</i>\n\n"
            "<b>Deleted Users (0)</b>:\n<i>Tidak ada akun terhapus.</i>"
        )

    active_users = []
    deleted_users = []

    for user_id in sudo_ids:
        try:
            user = await c.get_users(int(user_id))
            if user.is_deleted:
                deleted_users.append(user)
            else:
                active_users.append(user)
        except Exception:
            # Jika gagal fetch (banned, blocked, dll) → anggap deleted
            dummy_user = User(
                id=int(user_id),
                is_deleted=True,
                first_name=None,
                last_name=None,
                username=None,
                dc_id=None,
                is_bot=False
            )
            deleted_users.append(dummy_user)

    await msg.edit_msg(format_sudo_list(active_users, deleted_users))

# Log sukses loading
try:
    Altruix.log(f"[DEBUG] ✅ Loaded → {__plugin_name__} {PLUGIN_VERSION}", level=20)
except Exception as e:
    logger.info(f"[DEBUG] ✅ Loaded → {__plugin_name__} {PLUGIN_VERSION}")
