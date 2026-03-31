# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.

PLUGIN_VERSION = "0.1.2"
import logging
from Main import Altruix
from pyrogram import Client, enums
from Main.core.types.message import Message
from Main.core.decorators import log_errors

logger = logging.getLogger("altruix.xblocklist")

@Altruix.register_on_cmd(
    ["block"],
    cmd_help={
        "help": "Block a user from current account.",
        "usage": ".block <reply/username/id>",
        "example": ".block @username",
        "detail": "Blocks a user on Telegram. This prevents them from messaging you or seeing your status."
    },
)
@log_errors
async def block_user_cmd(c: Client, m: Message):
    msg = await m.handle_message("PROCESSING")
    user = None
    if m.reply_to_message:
        user = m.reply_to_message.from_user.id if m.reply_to_message.from_user else None
    elif m.user_input:
        user = m.user_input.split()[0]
    
    if not user:
        return await msg.edit("❌ <b>Gagal:</b> Mohon reply ke pesan user atau input username/ID.")

    try:
        user_obj = await c.get_users(user)
        await c.block_user(user_obj.id)
        await msg.edit(f"✅ <b>Berhasil:</b> <a href='tg://user?id={user_obj.id}'>{user_obj.first_name}</a> [<code>{user_obj.id}</code>] telah diblokir.")
    except Exception as e:
        await msg.edit(f"❌ <b>Error:</b> <code>{str(e)}</code>")

@Altruix.register_on_cmd(
    ["unblock"],
    cmd_help={
        "help": "Unblock a user from current account.",
        "usage": ".unblock <reply/username/id>",
        "example": ".unblock @username",
        "detail": "Removes a user from your Telegram blocklist."
    },
)
@log_errors
async def unblock_user_cmd(c: Client, m: Message):
    msg = await m.handle_message("PROCESSING")
    user = None
    if m.reply_to_message:
        user = m.reply_to_message.from_user.id if m.reply_to_message.from_user else None
    elif m.user_input:
        user = m.user_input.split()[0]
    
    if not user:
        return await msg.edit("❌ <b>Gagal:</b> Mohon reply ke pesan user atau input username/ID.")

    try:
        user_obj = await c.get_users(user)
        await c.unblock_user(user_obj.id)
        await msg.edit(f"✅ <b>Berhasil:</b> <a href='tg://user?id={user_obj.id}'>{user_obj.first_name}</a> [<code>{user_obj.id}</code>] telah dibuka blokirnya.")
    except Exception as e:
        await msg.edit(f"❌ <b>Error:</b> <code>{str(e)}</code>")

@Altruix.register_on_cmd(
    ["blocklist"],
    cmd_help={
        "help": "View list of blocked users for this account.",
        "usage": ".blocklist",
        "example": ".blocklist",
        "detail": "Fetches and displays the list of users you have blocked on this specific account."
    },
)
@log_errors
async def list_blocked_users_cmd(c: Client, m: Message):
    msg = await m.handle_message("PROCESSING")
    try:
        from pyrogram import raw
        blocked_users = []
        offset = 0
        limit = 100
        
        while True:
            r = await c.invoke(raw.functions.contacts.GetBlocked(offset=offset, limit=limit))
            if not r.users:
                break
                
            blocked_users.extend(r.users)
            if isinstance(r, raw.types.contacts.Blocked):
                break # Non-paged result
            
            # For BlockedSlice, we continue paginating
            if len(r.users) < limit:
                break
            offset += limit
        
        if not blocked_users:
            return await msg.edit("📭 <b>Blocklist kosong.</b>")
            
        res = "<b>🚫 Blocklist User:</b>\n\n"
        for i, user in enumerate(blocked_users, 1):
            name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Deleted Account"
            # Mentions are clickable via tg://user?id=
            res += f"{i}. <a href='tg://user?id={user.id}'>{name}</a> | <code>{user.id}</code>\n"
        
        # Split message if it's too long
        if len(res) > 4096:
            # Simple split for now, but we'll try to fit as many as possible
            # Or send as a file if massive
            with open("blocklist.txt", "w", encoding="utf-8") as f:
                f.write(res.replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", "").replace("<a>", "").replace("</a>", ""))
            await msg.delete()
            return await c.send_document(m.chat.id, "blocklist.txt", caption="📋 <b>Blocklist</b> (File format due to length)")

        await msg.edit(res, parse_mode=enums.ParseMode.HTML)
    except Exception as e:
        await msg.edit(f"❌ <b>Error:</b> <code>{str(e)}</code>")
