# Main/plugins/userbot/xdlcontent.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under "GNU v3.0 License Agreement".

import os
import re
import html
import logging
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.types import Message
from pyrogram.errors import FloodWait, RPCError, PeerIdInvalid, ChannelInvalid, UserNotParticipant

# Import metadata from client
from Main import Altruix
from Main.core.decorators import log_errors

plugin_name = f"{os.path.basename(__file__)}"
__plugin_name__ = plugin_name if plugin_name else "xdlcontent"
PLUGIN_VERSION = "0.0.2"

logger = logging.getLogger("altruix.xdlcontent")

__usage__ = """
<b>📥 Download Content Plugin</b>

Gunakan perintah ini untuk mengunduh konten dari link pesan (public/private).
Konten akan dikirimkan ke Log Group Anda.
"""

@Altruix.register_on_cmd(
    ["dlcontent"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Download content from telegram message link (public/private).",
        "example": "!dlcontent https://t.me/c/12345/678",
        "user_args": {
            "link": "The telegram message link to download content from."
        }
    }
)
@log_errors
async def dl_content_cmd_handler(c: Client, m: Message):
    input_ = m.user_input or m.raw_user_input
    if not input_:
        return await m.handle_message(__usage__)

    link = input_.split()[0].strip()
    status_msg = await m.handle_message("⏳ <b>Memproses download konten...</b>")
    
    try:
        await process_dl_content_logic(c, m, link, status_msg)
        if status_msg:
            try:
                await status_msg.delete()
            except:
                pass
        await m.delete_if_self()
    except Exception as e:
        await status_msg.edit(f"❌ <b>Error:</b> <code>{html.escape(str(e))}</code>")

async def process_dl_content_logic(c, m, link, status_msg):
    log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_USERS_ID))
    
    # Parse link
    pattern = r"t\.me/(c/)?([^/]+)/(\d+)"
    match = re.search(pattern, link)
    if not match:
        return await status_msg.edit("❌ <b>Format link tidak valid!</b>\nGunakan link pesan Telegram yang benar.")
        
    is_private = match.group(1) == "c/"
    chat_identifier = match.group(2)
    message_id = int(match.group(3))
    
    if is_private:
        chat_id = int("-100" + chat_identifier)
    else:
        chat_id = chat_identifier
        
    # Multi-client attempt to handle private chats
    msg = None
    exec_client = None
    
    # Prioritaskan client yang menerima command jika dia userbot
    clients_to_try = [c] + [client for client in Altruix.clients if client != c]
    
    await status_msg.edit("🔍 <b>Mencari akses ke chat...</b>")
    
    for client in clients_to_try:
        if client.is_bot: # Skip official bot if it somehow got here
            continue
        try:
            msg = await client.get_messages(chat_id, message_ids=message_id)
            if msg and not msg.empty:
                exec_client = client
                break
        except (PeerIdInvalid, ChannelInvalid, UserNotParticipant, RPCError):
            continue
        except FloodWait as e:
            await status_msg.edit(f"⏳ <b>FloodWait:</b> Tunggu {e.value}s...")
            await asyncio.sleep(e.value)
            # Retry with same client
            try:
                msg = await client.get_messages(chat_id, message_ids=message_id)
                if msg and not msg.empty:
                    exec_client = client
                    break
            except: continue
    
    if not exec_client or not msg or msg.empty:
        return await status_msg.edit("❌ <b>Konten tidak dapat diakses atau pesan tidak ditemukan.</b>\nPastikan salah satu session userbot Anda ada di dalam chat tersebut.")
            
    await status_msg.edit(f"📥 <b>Konten ditemukan via Sesi {Altruix.clients.index(exec_client) + 1}. Mencoba mengunduh...</b>")
    
    # 1. Try to copy first (fastest)
    try:
        # Gunakan bot utama untuk copy jika mungkin, atau userbot ini sendiri
        # Kita copy ke Log Group
        await msg.copy(log_chat_id)
        return
    except RPCError:
        pass
            
    # 2. Bypass Mechanism (Download then Upload)
    await status_msg.edit("🔄 <b>Copy dibatasi, mencoba bypass (download & re-upload)...</b>")
    
    if msg.media:
        try:
            media_path = await exec_client.download_media(msg)
            if not media_path:
                return await status_msg.edit("❌ <b>Gagal mengunduh media.</b>")
                
            # Upload using the main bot (or this client if bot is not available)
            uploader = Altruix.bot if Altruix.bot.is_connected else exec_client
            caption = (msg.caption or "") + f"\n\n🔗 <b>Source:</b> {link}"
            
            if msg.photo:
                await uploader.send_photo(log_chat_id, media_path, caption=caption)
            elif msg.video:
                await uploader.send_video(log_chat_id, media_path, caption=caption)
            elif msg.document:
                await uploader.send_document(log_chat_id, media_path, caption=caption)
            elif msg.audio:
                await uploader.send_audio(log_chat_id, media_path, caption=caption)
            elif msg.voice:
                await uploader.send_voice(log_chat_id, media_path, caption=caption)
            elif msg.animation:
                await uploader.send_animation(log_chat_id, media_path, caption=caption)
            else:
                # Generic file fallback
                await uploader.send_document(log_chat_id, media_path, caption=caption)
            
            if os.path.exists(media_path):
                os.remove(media_path)
        except FloodWait as e:
            return await status_msg.edit(f"⏳ <b>Bypass Gagal:</b> FloodWait {e.value} detik.")
        except Exception as e:
            return await status_msg.edit(f"❌ <b>Bypass Gagal:</b> <code>{str(e)}</code>")
    else:
        # Just text
        text = (msg.text or "") + f"\n\n🔗 <b>Source:</b> {link}"
        bot = Altruix.bot_manager.get_bot(c.me.id)
        await bot.send_message(log_chat_id, text)
