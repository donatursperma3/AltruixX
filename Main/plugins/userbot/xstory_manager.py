# Main/plugins/userbot/xstory_manager.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
# All rights reserved.

"""
PLUGIN: Story Manager
DESCRIPTION: Native story management (Upload, Edit, Delete, Flush).
AUTHOR: Altroid-X Pro
VERSION: 0.0.4
"""

import os
import re
import asyncio
import logging
from pyrogram import Client, filters, enums
from pyrogram.types import Message
from pyrogram.errors import (
    StoryIdInvalid, 
    PeerIdInvalid, 
    FloodWait, 
    MessageIdInvalid,
    RPCError
)
from Main import Altruix
from Main.core.decorators import log_errors, iuser_check

# ============================================================================
# SETTINGS & HELPERS
# ============================================================================
PLUGIN_VERSION = "0.0.4"
BATCH_DELETE_SIZE = 30 
BATCH_DELAY = 6.0 

def parse_story_id(input_str: str) -> int:
    """
    Extracts story_id from a raw ID or a Telegram story link.
    Supported Link Formats:
    - https://t.me/username/s/123
    - https://t.me/c/12345/s/678
    """
    if not input_str:
        return 0
        
    # Extract digit-only ID if provided directly
    if input_str.isdigit():
        return int(input_str)
        
    # Regex for t.me link extraction
    match = re.search(r"/s/(\d+)", input_str)
    if match:
        return int(match.group(1))
        
    return 0

# ============================================================================
# COMMANDS
# ============================================================================

@Altruix.register_on_cmd(
    ["storypost", "spost"],
    cmd_help={
        "help": "Unggah foto atau video sebagai story baru.",
        "usage": ".storypost [teks caption]",
        "detail": (
            "<b>Wajib</b> membalas (reply) ke sebuah foto atau video.\n"
            "Mendownload media tersebut, lalu mengunggahnya ke story akun Anda.\n\n"
            "<b>Parameter:</b>\n"
            "• <code>caption</code>: Teks yang akan muncul di bawah story (opsional).\n\n"
            "<b>Catatan:</b>\n"
            "Story akan aktif selama 24 jam secara default."
        ),
        "example": ".storypost Liburan Seru di Bali!"
    },
)
@iuser_check
@log_errors
async def story_post_cmd(c: Client, m: Message):
    """Upload media as a story via c.send_story."""
    reply = m.reply_to_message
    if not reply or not (reply.photo or reply.video):
        return await m.handle_message("❌ <b>Harap reply ke foto atau video yang ingin dijadikan story!</b>")

    caption = m.user_input or ""
    status_msg = await m.handle_message("📥 <b>Mendownload media...</b>")

    # Temporary file storage
    temp_file = None
    try:
        # Download media
        temp_file = await c.download_media(reply)
        if not temp_file:
             return await status_msg.edit("❌ <b>Gagal mengunduh media. Pastikan bot memiliki akses.</b>")

        await status_msg.edit("📤 <b>Mengunggah story...</b>")
        
        # Native send_story (Specialized for Kurigram)
        # Note: If c.send_story is missing, it will raise an AttributeError handled by log_errors
        # and we would need a raw invoke fallback.
        await c.send_story(
            chat_id="me",
            media=temp_file,
            caption=caption,
            parse_mode=enums.ParseMode.HTML
        )
        
        # Jeda sebentar agar Telegram sinkronisasi backend
        await asyncio.sleep(2.0)
        
        await status_msg.edit("✅ <b>Story berhasil diunggah ke profil Anda!</b>")
        await m.delete_if_self()

    except FloodWait as e:
        await status_msg.edit(f"⏳ <b>FloodWait:</b> Limit Telegram tercapai. Tunggu {e.value} detik.")
    except RPCError as e:
        await status_msg.edit(f"❌ <b>Kesalahan API:</b>\n<code>{str(e)}</code>")
    except Exception as e:
        await status_msg.edit(f"❌ <b>Error Internal:</b>\n<code>{str(e)}</code>")
    finally:
        # Resource cleanup
        if temp_file and os.path.exists(temp_file):
            try: os.remove(temp_file)
            except: pass

@Altruix.register_on_cmd(
    ["storyedit", "sedit"],
    cmd_help={
        "help": "Ubah caption pada story yang sudah aktif.",
        "usage": ".storyedit [ID/Link] [Caption Baru]",
        "detail": (
            "Mengganti caption teks story yang sedang tayang.\n\n"
            "<b>Input:</b>\n"
            "• <code>ID Story</code>: Angka ID saja (misal: 123).\n"
            "• <code>Link Story</code>: Link t.me story (misal: <code>https://t.me/durov/s/12</code>).\n\n"
            "<b>Contoh:</b> <code>.storyedit 12 Caption yang Lebih Bagus!</code>"
        ),
        "example": ".storyedit https://t.me/durov/s/12 Caption Keren!"
    },
)
@iuser_check
@log_errors
async def story_edit_cmd(c: Client, m: Message):
    """Edit story caption."""
    raw_input = m.user_input
    if not raw_input:
        return await m.handle_message("❌ <b>Harap berikan link/ID story dan teks caption baru!</b>")

    parts = raw_input.split(None, 1)
    story_id = parse_story_id(parts[0])
    new_caption = parts[1] if len(parts) > 1 else ""

    if not story_id:
        return await m.handle_message("❌ <b>Format ID atau Link Story tidak valid!</b>")

    status_msg = await m.handle_message(f"🔄 <b>Memperbarui caption story #{story_id}...</b>")

    try:
        # Native edit_story
        await c.edit_story(
            chat_id="me",
            story_id=story_id,
            caption=new_caption,
            parse_mode=enums.ParseMode.HTML
        )
        await status_msg.edit(f"✅ <b>Story #{story_id} berhasil diperbarui!</b>")
        await m.delete_if_self()

    except StoryIdInvalid:
        await status_msg.edit("❌ <b>Story ini sudah tidak ada atau kadaluarsa.</b>")
    except FloodWait as e:
        await status_msg.edit(f"⏳ <b>FloodWait:</b> Tunggu {e.value} detik.")
    except Exception as e:
        await status_msg.edit(f"❌ <b>Gagal memperbarui story:</b>\n<code>{str(e)}</code>")

@Altruix.register_on_cmd(
    ["storydel", "sdel"],
    cmd_help={
        "help": "Hapus story tertentu dari akun Anda.",
        "usage": ".storydel [ID/Link]",
        "detail": "Menghapus secara permanen story yang dipilih menggunakan ID atau link t.me.",
        "example": ".storydel 123"
    },
)
@iuser_check
@log_errors
async def story_del_cmd(c: Client, m: Message):
    """Delete one active story."""
    story_id = parse_story_id(m.user_input)
    if not story_id:
        return await m.handle_message("❌ <b>Berikan ID Story atau Link yang benar!</b>")

    status_msg = await m.handle_message(f"🗑 <b>Menghapus story #{story_id}...</b>")

    try:
        # Native delete_stories (takes a list of IDs)
        await c.delete_stories(chat_id="me", story_ids=[story_id])
        await status_msg.edit(f"✅ <b>Story #{story_id} berhasil dihapus!</b>")
        await m.delete_if_self()

    except StoryIdInvalid:
        await status_msg.edit("❌ <b>Story sudah tidak aktif atau ID salah.</b>")
    except FloodWait as e:
        await status_msg.edit(f"⏳ <b>FloodWait:</b> Tunggu {e.value} detik.")
    except Exception as e:
        await status_msg.edit(f"❌ <b>Gagal menghapus:</b>\n<code>{str(e)}</code>")

@Altruix.register_on_cmd(
    ["storyflush", "sflush"],
    cmd_help={
        "help": "Hapus SEMUA story aktif dari akun ini.",
        "usage": ".storyflush",
        "detail": "Melacak semua story aktif dan menghapusnya secara massal (batch deleting) untuk efisiensi limit."
    },
)
@iuser_check
@log_errors
async def story_flush_cmd(c: Client, m: Message):
    """Remove all active stories from current account."""
    status_msg = await m.handle_message("🧹 <b>Mencari story aktif...</b>")

    try:
        active_ids = []
        # Fetch stories via Kurigram native list method if available
        async for s in c.get_chat_stories("me"):
            active_ids.append(s.id)

        if not active_ids:
            return await status_msg.edit("ℹ️ <b>Tidak ditemukan story aktif untuk dihapus.</b>")

        total = len(active_ids)
        await status_msg.edit(f"🗑 <b>Ditemukan {total} story. Memulai penghapusan massal...</b>")
        
        # Batch deletion loop for safety
        deleted_count = 0
        for i in range(0, total, BATCH_DELETE_SIZE):
            batch = active_ids[i:i + BATCH_DELETE_SIZE]
            try:
                await c.delete_stories(chat_id="me", story_ids=batch)
                deleted_count += len(batch)
                await status_msg.edit(f"🗑 <b>Menghapus batch: {deleted_count}/{total}...</b>")
                if deleted_count < total:
                    await asyncio.sleep(BATCH_DELAY)
            except FloodWait as e:
                await status_msg.edit(f"⏳ <b>FloodWait:</b> Tunggu {e.value}s untuk batch berikutnya.")
                await asyncio.sleep(e.value + 1)
                # Retry deletion for the current batch
                await c.delete_stories(chat_id="me", story_ids=batch)
                deleted_count += len(batch)

        await status_msg.edit(f"✅ <b>Berhasil membersihkan {deleted_count} story aktif!</b>")
        await m.delete_if_self()

    except Exception as e:
        await status_msg.edit(f"❌ <b>Gagal pembersihan:</b>\n<code>{str(e)}</code>")
