# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.

"""
Bot assistant command for listing sudo users
"""

from Main import Altruix
from pyrogram import Client, filters
from pyrogram.types import Message, User
from Main.core.decorators import log_errors
import logging
import asyncio

PLUGIN_VERSION = "0.0.1"

logger = logging.getLogger("altruix.sudo_bot")
logger.setLevel(logging.INFO)


def format_sudo_list(active_users: list[User], unfetchable_users: list[User], deleted_users: list[User]) -> str:
    """Format sudo user list for display"""
    total = len(active_users) + len(unfetchable_users) + len(deleted_users)
    out = f"<b>Sudo Users (Total: {total})</b>:\n\n"

    # Active Users
    if active_users:
        out += f"<b>Active Users ({len(active_users)})</b>:\n"
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
        out += "<b>Active Users (0)</b>:\n<i>No active users.</i>\n\n"

    # Unfetchable Users
    if unfetchable_users:
        out += f"<b>Unfetchable Users ({len(unfetchable_users)})</b> <i>(May be active but failed to fetch, check manually)</i>:\n"
        for i, user in enumerate(unfetchable_users):
            hyperlink = f"<a href=\"tg://user?id={user.id}\">Unfetchable Account (ID: {user.id})</a>"
            if i == 0:
                out += f"┏◈ {hyperlink}\n"
            elif i == len(unfetchable_users) - 1:
                out += f"┗◈ {hyperlink}\n"
            else:
                out += f"┣◈ {hyperlink}\n"
        out += "\n"
    else:
        out += "<b>Unfetchable Users (0)</b>:\n<i>No unfetchable users.</i>\n\n"

    # Deleted Users
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
        out += "<b>Deleted Users (0)</b>:\n<i>No deleted accounts.</i>"

    return out


@Altruix.bot.on_message(filters.command("listsudo", prefixes="/") & filters.private & Altruix.is_sudo_filter)
@log_errors
async def listsudo_bot_handler(c: Client, m: Message):
    """
    Bot command to list all sudo users.
    Only accessible by owner and sudo users.
    """
    user_id = m.from_user.id
    
    # ✅ AUTHORIZATION CHECK (Centralized)
    if not await Altruix.is_sudo(user_id):
        await m.reply("⛔ You are not authorized to use this command.")
        return
    
    processing_msg = await m.reply("<code>Processing sudo user list...</code>")
    
    # ✅ GET ALL SUDO USERS (Global + DB Cache)
    static_sudo = Altruix.config.SUDO_USERS_ID or []
    if isinstance(static_sudo, str):
        static_sudo = [int(x.strip()) for x in static_sudo.split(',') if x.strip().isdigit()]
    
    # Combine static and cached DB users
    sudo_ids = list(set(static_sudo + list(Altruix.db_sudo_users)))
    
    if not sudo_ids:
        await processing_msg.edit(
            "<b>Sudo Users (Total: 0)</b>\n\n"
            "<b>Active Users (0)</b>:\n<i>No active users found in listing.</i>\n\n"
            "<b>Unfetchable Users (0)</b>:\n<i>No unfetchable users.</i>\n\n"
            "<b>Deleted Users (0)</b>:\n<i>No deleted accounts.</i>"
        )
        return
    
    active_users = []
    unfetchable_users = []
    deleted_users = []
    
    # Use first available client to fetch user info
    if not hasattr(Altruix, 'clients') or not Altruix.clients:
        await processing_msg.edit("❌ No userbot sessions available to fetch user information.")
        return
    
    client = Altruix.clients[0]
    
    for uid in sudo_ids:
        try:
            user = await client.get_users(int(uid))
            if user.is_deleted:
                deleted_users.append(user)
            else:
                active_users.append(user)
        except Exception:
            # If failed to fetch, create dummy user for unfetchable category
            dummy_user = User(
                id=int(uid),
                is_deleted=False,
                first_name=None,
                last_name=None,
                username=None,
                dc_id=None,
                is_bot=False
            )
            unfetchable_users.append(dummy_user)
    
    formatted_list = format_sudo_list(active_users, unfetchable_users, deleted_users)
    await processing_msg.edit(formatted_list)
