# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.


import re
import Main
from pyrogram import filters
from pyrogram.types import Message
from .file_helpers import run_in_exc


async def parse_(client, message: Message, cmd, is_ultroid=False, disable_sudo=False):
    # ✅ REFACTOR: Use HIGH-PERFORMANCE CACHE from Altruix
    # This prevents event loop clogging from thousands of DB lookups for every message
    prefix_cache = Main.Altruix._prefix_cache
    prefix_apply_type = prefix_cache["apply_type"]
    user_id = client.me.id if client and hasattr(client, 'me') and client.me else None
    
    if is_ultroid:
        if prefix_apply_type == "global":
            prefix_owner_user = prefix_cache.get("ultroid_owner", ",")
            prefix_sudo_users = prefix_cache.get("ultroid_sudo", "?")
        else:
            pa = prefix_cache["per_account"].get(user_id, {})
            prefix_owner_user = pa.get("ult_u", prefix_cache.get("ultroid_owner", ","))
            prefix_sudo_users = pa.get("ult_s", prefix_cache.get("ultroid_sudo", "?"))
    else:
        if prefix_apply_type == "global":
            prefix_owner_user = prefix_cache["prefix_owner_user"]
            prefix_sudo_users = prefix_cache["prefix_sudo_users"]
        else:
            pa = prefix_cache["per_account"].get(user_id, {})
            prefix_owner_user = pa.get("u", prefix_cache["prefix_owner_user"])
            prefix_sudo_users = pa.get("s", prefix_cache["prefix_sudo_users"])

    try:
        if not message.text:
            return False
        
        reg = re.search(
            r"^([\!\"\#\$\%\&\'\(\)\*\+\,\-\.\/\:\;\<\>\=\?\@\[\]\{\}\\\\\^\_\`\~])(\w+)(?:(?:.|\n)+)?$",
            message.text,
        )
        if not reg:
            return False

        prefix = reg[1]
        command_name = reg[2]

        # ✅ Determine sender identity
        is_self = (message.from_user and message.from_user.is_self) or message.outgoing
        
        # 1. OWNER LOGIC (User Prefix Only)
        if is_self:
            if prefix == prefix_owner_user and command_name in cmd:
                return True
            return False

        # 2. SUDO LOGIC (Sudo Prefix Only)
        if not disable_sudo and prefix == prefix_sudo_users and command_name in cmd:
            # Check if current user ID is in authorized sudo list
            if message.from_user and await Main.Altruix.is_sudo(message.from_user.id, client=client):
                Main.Altruix.log(f"👑 SUDO_FILTER: Authorized sudo user {message.from_user.id} executing command '{command_name}'", level=20)
                return True
        
        return False
    except Exception:
        return False


def user_filters(cmd, is_ultroid=False, disable_sudo=False):
    async def s_f(f, client, message):
        f_out = await parse_(
            client=client, message=message, cmd=cmd, is_ultroid=is_ultroid, disable_sudo=disable_sudo
        )
        return f_out

    return filters.create(s_f)
