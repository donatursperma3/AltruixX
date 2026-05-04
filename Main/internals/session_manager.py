# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.


from Main import Altruix
from pyrogram import filters
from Main.core.decorators import log_errors
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup


@Altruix.bot.on_message(filters.command("add", "/") & Altruix.is_sudo_filter)
@log_errors
async def add_session_command_handler(_, m: Message):
    # ✅ AUTHORIZATION CHECK (Centralized)
    if not await Altruix.is_sudo(m.from_user.id):
        return await m.reply_text("Hey, I'm just a bot. Powered by @AltruixUB.")
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(m.from_user.id)
    await m.reply(
        "Do you have the string session already generated?.",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Yes", callback_data="session_yes", style=user_style),
                    InlineKeyboardButton("No", callback_data="session_no", style=user_style),
                ]
            ]
        ),
    )
