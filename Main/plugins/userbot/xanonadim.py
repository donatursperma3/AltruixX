# xanonadim.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
#
# Adapted from Ultroid for Altruix ecosystem.

from Main import Altruix
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.types import ChatAdministratorRights, ChatPermissions
from Main.utils.helpers import ChatPrivileges
from Main.core.decorators import log_errors
import html

@Altruix.register_on_cmd(
    ["setowneranon"],
    cmd_help={
        "help": "Set the chat owner to be anonymous.",
        "usage": ".setowneranon",
        "example": ".setowneranon",
        "detail": "Make the creator (owner) of the group appear as 'Anonymous' when they send messages. This will enable 'is_anonymous' privilege for the owner account."
    },
    group_only=True
)
@log_errors
async def set_owner_anon_handler(c: Client, m: Message):
    chat_id = m.chat.id
    try:
        # Get current me as creator/admin
        me = await c.get_chat_member(chat_id, "me")
        if not me.status.value == "owner":
            return await m.reply_msg("❌ **Anda harus menjadi OWNER (Creator) grup ini untuk menggunakan command ini.**")

        await c.promote_chat_member(
            chat_id, 
            me.user.id,
            ChatPrivileges(
                can_manage_chat=True,
                can_delete_messages=True,
                can_manage_video_chats=True,
                can_restrict_members=True,
                can_promote_members=True,
                can_change_info=True,
                can_invite_users=True,
                can_pin_messages=True,
                is_anonymous=True
            )
        )
        await m.reply_msg("✅ **Owner sekarang Anonymous!**")
    except Exception as e:
        await m.reply_msg(f"❌ **Error:** `{str(e)}`")

@Altruix.register_on_cmd(
    ["unsetowneranon"],
    cmd_help={
        "help": "Set the chat owner to NOT be anonymous.",
        "usage": ".unsetowneranon",
        "example": ".unsetowneranon",
        "detail": "Disables the 'is_anonymous' privilege for the group owner, revealing their identity in group messages."
    },
    group_only=True
)
@log_errors
async def unset_owner_anon_handler(c: Client, m: Message):
    chat_id = m.chat.id
    try:
        me = await c.get_chat_member(chat_id, "me")
        if not me.status.value == "owner":
            return await m.reply_msg("❌ **Anda harus menjadi OWNER (Creator) grup ini.**")

        await c.promote_chat_member(
            chat_id, 
            me.user.id,
            ChatPrivileges(
                can_manage_chat=True,
                can_delete_messages=True,
                can_manage_video_chats=True,
                can_restrict_members=True,
                can_promote_members=True,
                can_change_info=True,
                can_invite_users=True,
                can_pin_messages=True,
                is_anonymous=False
            )
        )
        await m.reply_msg("✅ **Owner sekarang TIDAK Anonymous.**")
    except Exception as e:
        await m.reply_msg(f"❌ **Error:** `{str(e)}`")

@Altruix.register_on_cmd(
    ["setadminanon"],
    cmd_help={
        "help": "Set an administrator to be anonymous.",
        "usage": ".setadminanon [reply/user_id/username]",
        "example": ".setadminanon @username",
        "user_args": {
            "reply": "Reply to an administrator's message to make them anonymous.",
            "user_id": "Target administrator's numerical user ID.",
            "username": "Target administrator's @username."
        },
        "detail": "Enables 'is_anonymous' privilege for the specified administrator. You must be the group owner to perform this action."
    },
    group_only=True
)
@log_errors
async def set_admin_anon_handler(c: Client, m: Message):
    chat_id = m.chat.id
    user_id = m.reply_to_message.from_user.id if m.reply_to_message else m.user_input
    
    if not user_id:
        return await m.reply_msg("❌ **Reply to a message or provide User ID/Username.**")
    
    try:
        # Check if caller is owner
        me = await c.get_chat_member(chat_id, "me")
        if not me.status.value == "owner":
            return await m.reply_msg("❌ **Anda harus menjadi OWNER untuk mengubah status anonim admin lain.**")

        target = await c.get_chat_member(chat_id, user_id)
        if target.status.value != "administrator":
            return await m.reply_msg("❌ **Target bukan merupakan Administrator.**")

        # Copy existing privileges and set is_anonymous=True
        await c.promote_chat_member(
            chat_id,
            target.user.id,
            ChatPrivileges(
                can_manage_chat=target.privileges.can_manage_chat,
                can_delete_messages=target.privileges.can_delete_messages,
                can_manage_video_chats=target.privileges.can_manage_video_chats,
                can_restrict_members=target.privileges.can_restrict_members,
                can_promote_members=target.privileges.can_promote_members,
                can_change_info=target.privileges.can_change_info,
                can_invite_users=target.privileges.can_invite_users,
                can_pin_messages=target.privileges.can_pin_messages,
                can_post_messages=target.privileges.can_post_messages,
                can_edit_messages=target.privileges.can_edit_messages,
                is_anonymous=True
            )
        )
        await m.reply_msg(f"✅ **Admin {target.user.mention} sekarang Anonymous!**")
    except Exception as e:
        await m.reply_msg(f"❌ **Error:** `{str(e)}`")

@Altruix.register_on_cmd(
    ["unsetadminanon"],
    cmd_help={
        "help": "Set an administrator to NOT be anonymous.",
        "usage": ".unsetadminanon [reply/user_id/username]",
        "example": ".unsetadminanon @username",
        "user_args": {
            "reply": "Reply to an administrator's message to reveal their identity.",
            "user_id": "Target administrator's numerical user ID.",
            "username": "Target administrator's @username."
        },
        "detail": "Disables 'is_anonymous' privilege for the specified administrator. You must be the group owner to perform this action."
    },
    group_only=True
)
@log_errors
async def unset_admin_anon_handler(c: Client, m: Message):
    chat_id = m.chat.id
    user_id = m.reply_to_message.from_user.id if m.reply_to_message else m.user_input
    
    if not user_id:
        return await m.reply_msg("❌ **Reply to a message or provide User ID/Username.**")
    
    try:
        me = await c.get_chat_member(chat_id, "me")
        if not me.status.value == "owner":
            return await m.reply_msg("❌ **Anda harus menjadi OWNER.**")

        target = await c.get_chat_member(chat_id, user_id)
        if target.status.value != "administrator":
            return await m.reply_msg("❌ **Target bukan merupakan Administrator.**")

        await c.promote_chat_member(
            chat_id,
            target.user.id,
            ChatPrivileges(
                can_manage_chat=target.privileges.can_manage_chat,
                can_delete_messages=target.privileges.can_delete_messages,
                can_manage_video_chats=target.privileges.can_manage_video_chats,
                can_restrict_members=target.privileges.can_restrict_members,
                can_promote_members=target.privileges.can_promote_members,
                can_change_info=target.privileges.can_change_info,
                can_invite_users=target.privileges.can_invite_users,
                can_pin_messages=target.privileges.can_pin_messages,
                can_post_messages=target.privileges.can_post_messages,
                can_edit_messages=target.privileges.can_edit_messages,
                is_anonymous=False
            )
        )
        await m.reply_msg(f"✅ **Admin {target.user.mention} sekarang TIDAK Anonymous.**")
    except Exception as e:
        await m.reply_msg(f"❌ **Error:** `{str(e)}`")
