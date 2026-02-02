# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.

import asyncio
from Main import Altruix
from pyrogram import Client

@Altruix.register_on_cmd(
    ["settings"], 
    cmd_help={"help": "Buka menu pengaturan interactive (full buttons)", "example": "settings"},
    bot_mode_unsupported=True
)
async def ub_settings_handler(c: Client, m):
    """
    Handler untuk command .settings pada userbot.
    Mengambil hasil inline dari Bot Asisten untuk menampilkan menu dengan tombol interaktif.
    """
    chat = m.chat.id
    rm = m.reply_to_message
    
    # 1. Ambil username bot asisten (bisa custom bot atau main bot)
    bot_username = Altruix.bot_manager.get_bot_username(c.me.id)
    
    try:
        # 2. Ambil hasil inline bot untuk query 'settings'
        results = await c.get_inline_bot_results(bot_username, "settings")
        
        if results and results.results:
            # 3. Kirim hasil inline ke chat
            await c.send_inline_bot_result(
                chat_id=chat,
                query_id=results.query_id,
                result_id=results.results[0].id,
                reply_to_message_id=rm.id if rm else None,
            )
            # 4. Hapus pesan perintah
            await m.delete_if_self()
        else:
            await m.edit_msg("❌ Bot Asisten gagal memberikan menu pengaturan.")
            
    except Exception as e:
        Altruix.log(f"Error in .settings userbot handler: {e}")
        await m.edit_msg(f"❌ Error: {str(e)}")
