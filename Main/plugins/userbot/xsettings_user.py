# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.


PLUGIN_VERSION = "0.0.21"
import asyncio
import html
import base64
from Main import Altruix
from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode

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
        # Encode chat title for query safety
        chat_obj = m.chat
        chat_title = chat_obj.title or chat_obj.first_name or "Chat"
        encoded_title = base64.b64encode(chat_title.encode('utf-8')).decode('utf-8')
        
        # 2. Ambil hasil inline bot untuk query 'settings'
        # Add metadata to query
        results = await c.get_inline_bot_results(bot_username, f"settings cid={chat} ctit={encoded_title}")
        
        if results and results.results:
            # 3. Kirim hasil inline ke chat
            await c.send_inline_bot_result(
                chat_id=chat,
                query_id=results.query_id,
                result_id=results.results[0].id,
                reply_to_message_id=m.id,
            )
            # 4. Hapus pesan perintah
            await m.delete_if_self()
        else:
            await m.edit_msg("❌ Bot Asisten gagal memberikan menu pengaturan.")
            
    except Exception as e:
        Altruix.log(f"Error in .settings userbot handler: {e}")
        await m.edit_msg(f"❌ Error: {str(e)}")


@Altruix.register_on_cmd(
    ["mysess"], 
    cmd_help={"help": "Tampilkan informasi dan pengaturan session ini dengan tombol interaktif", "example": "mysess"},
    bot_mode_unsupported=True
)
async def mysess_handler(c: Client, m):
    """
    Handler untuk command .mysess pada userbot.
    Menampilkan informasi lengkap session dengan semua tombol seperti di dashboard settings.
    """
    try:
        # Get session index
        index = None
        for i, client in enumerate(Altruix.clients):
            if client.me.id == c.me.id:
                index = i
                break
        
        if index is None:
            await m.edit_msg("❌ Session tidak ditemukan dalam daftar clients.")
            return
        
        me = c.me
        chat = m.chat.id
        
        # 1. Ambil username bot asisten (bisa custom bot atau main bot)
        bot_username = Altruix.bot_manager.get_bot_username(me.id)
        
        # 2. Ambil hasil inline bot untuk query 'session_{index}'
        # Encode chat title
        chat_obj = m.chat
        chat_title = chat_obj.title or chat_obj.first_name or "Chat"
        encoded_title = base64.b64encode(chat_title.encode('utf-8')).decode('utf-8')
        
        try:
            query_str = f"session_{index} cid={chat} ctit={encoded_title}"
            results = await c.get_inline_bot_results(bot_username, query_str)
            
            if results and results.results:
                # 3. Kirim hasil inline ke chat
                await c.send_inline_bot_result(
                    chat_id=chat,
                    query_id=results.query_id,
                    result_id=results.results[0].id,
                    reply_to_message_id=m.id,
                )
                # 4. Hapus pesan perintah asli
                await m.delete_if_self()
            else:
                await m.edit_msg(f"❌ {Altruix.get_string('mysess_fetch_error')}")
                
        except Exception as e:
            Altruix.log(f"Error in .mysess inline fetch: {e}")
            await m.edit_msg(f"❌ Error getting inline results: {str(e)}")
            
    except Exception as e:
        Altruix.log(f"Error in .mysess handler: {e}", level=40)
        await m.edit_msg(f"❌ Error: {str(e)}")

