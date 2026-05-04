# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.


PLUGIN_VERSION = "0.0.12"
from Main import Altruix
from pyrogram import Client
import asyncio
from Main.core.decorators import log_errors, inline_check
from Main.internals.xlist_builder import QUERY_CONFIRM, build_cmds_list

@Altruix.register_on_cmd(
    ["listcmds", "allcmds"], 
    bot_mode_unsupported=True,
    cmd_help={
        "help": "List all commands across all plugins using an interactive menu.",
        "usage": ".listcmds [page]",
        "example": ".listcmds 2",
    }
)
@log_errors
@inline_check
async def list_all_cmds_handler(c: Client, m):
    """Handler to list all commands across all plugins using an interactive menu."""
    bot_username = Altruix.bot_manager.get_bot_username(c.me.id)
    if not bot_username:
        return await m.handle_message("❌ Assistant Bot is not configured!")

    rm = m.reply_to_message
    args = m.user_input
    
    # Check if user provided a page number
    page = 0
    query_str = f"{QUERY_CONFIRM}_{m.from_user.id}"
    
    if args and args.isdigit():
        page = int(args) - 1 # 1-indexed to 0-indexed
        if page < 0: page = 0
        query_str = f"listcmds_list_{page}_{m.from_user.id}"
    
    # Call the inline query
    results = await c.get_inline_bot_results(
        bot_username, query_str
    )
    
    if not results or not results.results:
        err_msg = "❌ Failed to fetch command list menu!"
        if args and args.isdigit():
            err_msg = f"❌ Page {args} not found or error occurred!"
        return await m.handle_message(err_msg)

    try:
        await c.send_inline_bot_result(
            chat_id=m.chat.id,
            query_id=results.query_id,
            result_id=results.results[0].id,
            reply_to_message_id=rm.id if rm else m.id,
        )
        await m.delete_if_self()
    except Exception as e:
        # Handle cases where the chat restricts inline bots
        if "CHAT_SEND_INLINE_FORBIDDEN" in str(e) or "FORBIDDEN" in str(e).upper():
            text, _ = await build_cmds_list(m.from_user.id, page=page)
            warning = (
                "⚠️ <b>Inline Bots Restricted</b>\n"
                "<i>This chat does not allow sending inline results.</i>\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
            )
            await m.reply_msg(warning + text)
            return await m.delete_if_self()
        raise


