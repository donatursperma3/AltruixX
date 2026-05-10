# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.

PLUGIN_VERSION = "1.0.125"

import hashlib
import time
import traceback
from pyrogram import Client
from pyrogram.types import Message
from Main import Altruix
from Main.core.decorators import log_errors
from Main.internals.ytdl_core import extract_yt_info

@Altruix.register_on_cmd(
    ["ytdl", "yt"],
    bot_mode_unsupported=True,
    requires_input=True,
    cmd_help={
        "help": "Advanced Manager & Downloader Media YouTube Interaktif.",
        "example": (
             ".ytdl https://www.youtube.com/watch?v=xxxx\n"
             ".yt https://youtu.be/xxxx\n\n"
             "📊 <b>Fitur Interaktif Dashboard:</b>\n"
             "• <b>Format/Quality:</b> Download Video (hingga resolusi Max) atau Audio (MP3 320kbps).\n"
             "• <b>Playlist Handling:</b> Mendukung Batch (seluruh playlist) atau Single Select.\n"
             "• <b>✂️ Precise Trimmer:</b> Memotong durasi awal dan akhir secara spesifik.\n"
             "• <b>👤 Sender:</b> Opsi fallback untuk upload via bot jika file terlalu besar untuk Userbot.\n"
             "• <b>🏷 Audio Edit:</b> Modifikasi Meta Tag ID3 Artist & penyusunan judul file suara.\n"
             "  └─ <b>Channel:</b> Menggunakan nama akun YouTube pengunggah.\n"
             "  └─ <b>Meta:</b> Menggunakan Metadata asli (YouTube Music Official).\n"
             "  └─ <b>None:</b> Mengosongkan data artist agar tampilan minimalis."
             "• <b>💧 Watermark:</b> Stamp visual 'Altroid-X' di atas frame video.\n"
             "• <b>📥 Auto-Backup:</b> Teruskan hasil download langsung ke Grup Log (via Bot/Ubot).\n"
             "• <b>🔗 Source Link:</b> Tempelkan URL video asli ke dalam caption file."
        ),
    }
)
@log_errors
async def ytdl_cmd(c: Client, m: Message):
    url = m.user_input
    if not url.startswith("http"):
        return await m.reply("❌ Silakan masukkan URL YouTube yang valid.")
        
    status = await m.reply("<b>🔍 Menganalisis video...</b>")
    
    try:
        # 1. Extract Video Info
        info = await extract_yt_info(url)
        
        # 2. Generate Task ID with Fallback
        try:
            from Main.plugins.userbot.xtaskmanager import generate_task_id
            task_id = generate_task_id("YT")
        except Exception:
            import hashlib
            task_id = f"#YT{hashlib.md5(f'{url}{time.time()}'.encode()).hexdigest()[:4]}"
        
        # 3. Save to shared state
        is_playlist = info.get("type") == "playlist"
        
        reply_to = m.reply_to_message.id if m.reply_to_message else m.id
        
        Altruix.YTDL_STATE[task_id] = {
            "type": info["type"],
            "title": info["title"],
            "url": url,
            "duration": info.get("duration", 0),
            "thumb": info["thumbnail"],
            "uploader": info.get("uploader"),
            "subscribers": info.get("subscribers"),
            "views": info.get("views"),
            "upload_date": info.get("upload_date"),
            "start": 0,
            "end": info.get("duration", 0),
            "format": "video",
            "quality": "720",
            "client_idx": -1, # Default: Bot (-1)
            "sender_name": "Assistant Bot",
            "user_id": c.me.id,
            "chat_id": m.chat.id,
            "reply_to": reply_to,
            "show_link": True,
            "auto_backup": True,
            "backup_mode": "bot",
            "languages": info.get("languages", []),
            "audio_lang": "Default"
        }
        
        if not is_playlist:
             Altruix.YTDL_STATE[task_id].update({
                 "resolutions": info.get("resolutions", []),
                 "res_sizes": info.get("res_sizes", {}),
                 "end": info.get("duration", 0)
             })
        else:
             Altruix.YTDL_STATE[task_id].update({
                 "entries": info.get("entries", []),
                 "count": info.get("count", 0)
             })
        
        # Determine Runner Index (Who initiated the command)
        runner_idx = 0
        for idx, client in enumerate(Altruix.clients):
             if client == c:
                 runner_idx = idx
                 break
        Altruix.YTDL_STATE[task_id]["runner_idx"] = runner_idx

        # Determine Default Sender based on Chat Context
        log_chat_id = getattr(Altruix, "log_chat", None)
        if m.chat.id == log_chat_id:
             # Default to Assistant Bot in Log Group
             Altruix.YTDL_STATE[task_id]["client_idx"] = -1
             Altruix.YTDL_STATE[task_id]["sender_name"] = "Assistant Bot"
             Altruix.YTDL_STATE[task_id]["auto_backup"] = False # Disable backup in Log Group
        else:
             # Default to the current Userbot session in any other chat
             Altruix.YTDL_STATE[task_id]["client_idx"] = runner_idx
             Altruix.YTDL_STATE[task_id]["sender_name"] = c.me.first_name or f"Userbot #{runner_idx+1}"
        
        bot_username = Altruix.bot_manager.get_bot_username(c.me.id)
        if not bot_username or bot_username == "Unknown":
            return await status.edit("❌ Bot asisten tidak terkonfigurasi.")
            
        from Main.internals.ytdl_core import sync_ytdl_task
        await sync_ytdl_task(task_id)
            
        results = await c.get_inline_bot_results(bot_username, f"ytdl_menu#{task_id}")
        await c.send_inline_bot_result(
            chat_id=m.chat.id,
            query_id=results.query_id,
            result_id=results.results[0].id,
            reply_to_message_id=m.reply_to_message.id if m.reply_to_message else m.id
        )
        await status.delete()
        await m.delete_if_self()
        
    except Exception:
        err_msg = traceback.format_exc()
        Altruix.log(f"YTDL Command Error:\n{err_msg}", level=40)
        
        # Cleaner error message for users
        clean_err = err_msg.splitlines()[-1]
        if "truncated" in clean_err.lower() or "incomplete youtube id" in clean_err.lower():
            clean_err = "URL YouTube tidak lengkap atau terpotong. Pastikan Anda menyalin URL dengan benar."
        elif "yt-dlp error" in clean_err.lower():
            clean_err = clean_err.split("YT-DLP Error: ")[-1]
            
        await status.edit(f"❌ <b>Error:</b> <code>{clean_err}</code>")
