# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.
"""
Owner Management Plugin for Altruix.
Allows adding, removing, and listing authorized owners.
"""

from Main import Altruix
from pyrogram import Client
from pyrogram.types import User
from ...core.types.message import Message
import os
from Main.core.decorators import log_errors

plugin_name = f"{os.path.basename(__file__)}"
__plugin_name__ = plugin_name if plugin_name else "xowner_manager"
PLUGIN_VERSION = "0.0.1"

def format_owner_list(active_users: list[User], unfetchable_users: list[User], deleted_users: list[User]) -> str:
    total = len(active_users) + len(unfetchable_users) + len(deleted_users)
    out = f"<b>Owner Users (Total: {total})</b>:\n\n"

    # === Active Users ===
    if active_users:
        out += f"<b>Active Owners ({len(active_users)})</b>:\n"
        for i, user in enumerate(active_users):
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
        out += "<b>Active Owners (0)</b>:\n<i>No active owners.</i>\n\n"

    # === Unfetchable Users ===
    if unfetchable_users:
        out += f"<b>Unfetchable Owners ({len(unfetchable_users)})</b>:\n"
        for i, user in enumerate(unfetchable_users):
            hyperlink = f"<a href=\"tg://user?id={user.id}\">Unfetchable Account (ID: {user.id})</a>"
            if i == 0:
                out += f"┏◈ {hyperlink}\n"
            elif i == len(unfetchable_users) - 1:
                out += f"┗◈ {hyperlink}\n"
            else:
                out += f"┣◈ {hyperlink}\n"
        out += "\n"

    # === Deleted Users ===
    if deleted_users:
        out += f"<b>Deleted Owners ({len(deleted_users)})</b>:\n"
        for i, user in enumerate(deleted_users):
            hyperlink = f"<a href=\"tg://user?id={user.id}\">Deleted Account</a>"
            if i == 0:
                out += f"┏◈ {hyperlink}\n"
            elif i == len(deleted_users) - 1:
                out += f"┗◈ {hyperlink}\n"
            else:
                out += f"┣◈ {hyperlink}\n"
    
    return out

@Altruix.register_on_cmd(
    "addowner",
    cmd_help={
        "help": "Add a user to owners list. Use with caution!",
        "example": "addowner @username",
    },
)
@log_errors
async def add_owner_func(c: Client, m: Message):
    msg = await m.handle_message("PROCESSING")
    user, _, is_channel = m.get_user
    if not user or is_channel:
        await msg.edit_msg("INVALID_USER")
        return

    try:
        user_obj = await c.get_users(user)
    except Exception:
        await msg.edit_msg("INVALID_USER")
        return

    owners = await Altruix.config.get_owners()
    if user_obj.id in owners:
        await msg.edit_msg("ALREADY_IN_OWNER")
        return

    await Altruix.config.add_owner(user_obj.id)
    await Altruix.refresh_sudo_cache() # Owners are also sudo
    await msg.edit_msg("ADDED_OWNER", string_args=(user_obj.mention))
    if msg.id != m.id:
        await m.delete_if_self()

@Altruix.register_on_cmd(
    "rmowner",
    cmd_help={
        "help": "Remove a user from owners list.",
        "example": "rmowner @username",
    },
)
@log_errors
async def rm_owner_func(c: Client, m: Message):
    msg = await m.handle_message("PROCESSING")
    user, _, is_channel = m.get_user
    if not user or is_channel:
        await msg.edit_msg("INVALID_USER")
        return

    try:
        user_obj = await c.get_users(user)
    except Exception:
        await msg.edit_msg("INVALID_USER")
        return

    owners = await Altruix.config.get_owners()
    if user_obj.id not in owners:
        await msg.edit_msg("NOT_IN_OWNER")
        return
    
    # Protect against removing the last owner if possible, 
    # but here we just follow instructions.
    await Altruix.config.del_owner(user_obj.id)
    await Altruix.refresh_sudo_cache()
    await msg.edit_msg("DEL_OWNER", string_args=(user_obj.mention))
    if msg.id != m.id:
        await m.delete_if_self()

@Altruix.register_on_cmd(
    "listowner",
    cmd_help={
        "help": "List all authorized owners.",
        "example": "listowner",
    }
)
@log_errors
async def list_owner_func(c: Client, m: Message):
    msg = await m.handle_message("PROCESSING")
    owner_ids = await Altruix.config.get_owners()

    if not owner_ids:
        await msg.edit_msg("<b>No Owners Found.</b>")
        return

    active_owners = []
    unfetchable_owners = []
    deleted_owners = []

    for user_id in owner_ids:
        try:
            user = await c.get_users(int(user_id))
            if user.is_deleted:
                deleted_owners.append(user)
            else:
                active_owners.append(user)
        except Exception:
            dummy_user = User(
                id=int(user_id),
                is_deleted=False,
                first_name=None,
                last_name=None,
                username=None,
                dc_id=None,
                is_bot=False
            )
            unfetchable_owners.append(dummy_user)

    await msg.edit_msg(format_owner_list(active_owners, unfetchable_owners, deleted_owners))
    if msg.id != m.id:
        await m.delete_if_self()
