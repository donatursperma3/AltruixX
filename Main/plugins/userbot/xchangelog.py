# Main/plugins/userbot/xchangelog.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
# All rights reserved.

import logging
from pyrogram import Client
from Main import Altruix
from Main.core.decorators import log_errors
from Main.internals.xchangelog_builder import QUERY_PREFIX

PLUGIN_VERSION = "1.1.0"
logger = logging.getLogger(__name__)

@Altruix.register_on_cmd(
    ["changelog", "clog"], 
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Read and display the interactive paginated changelog.",
        "description": (
            "📜 <b>Changelog Viewer (Interactive)</b>\n\n"
            "View the latest updates and changes using an interactive menu.\n\n"
            "• <code>.changelog</code> - Open the changelog dashboard.\n"
            "• <code>.changelog [n]</code> - Jump to a specific version update index.\n"
            "• <code>.clog</code> - Alias for .changelog"
        ),
        "usage": ".changelog [page]",
        "example": ".changelog 2",
    }
)
@log_errors
async def changelog_handler(c: Client, m):
    """
    Open the interactive changelog dashboard.
    """
    bot_username = Altruix.bot_manager.get_bot_username(c.me.id)
    if not bot_username:
        return await m.reply_msg("❌ Assistant Bot is not configured!")

    args = m.user_input
    page = 0
    if args and args.isdigit():
        page = int(args) - 1 # 1-indexed to 0-indexed
        if page < 0: page = 0
    
    # Trigger the inline bot
    query_str = f"{QUERY_PREFIX}_{page}_{m.from_user.id}"
    
    try:
        results = await c.get_inline_bot_results(
            bot_username, query_str
        )
        
        if not results or not results.results:
            return await m.reply_msg("❌ Failed to fetch changelog menu!")

        await c.send_inline_bot_result(
            chat_id=m.chat.id,
            query_id=results.query_id,
            result_id=results.results[0].id,
            reply_to_message_id=m.reply_to_message.id if m.reply_to_message else None,
        )
        await m.delete_if_self()
        
    except Exception as e:
        logger.error(f"Changelog Handler Error: {e}")
        return await m.reply_msg(f"❌ Error: <code>{str(e)}</code>")
