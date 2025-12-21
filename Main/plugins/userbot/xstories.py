# Main/plugins/userbot/xstories.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.

from Main import Altruix
from pyrogram import Client, filters, enums
from pyrogram.types import Message
from Main.core.decorators import log_errors
import asyncio
import os
import time

# ============================================================================
# SETTINGS & CONSTANTS
# ============================================================================
PLUGIN_VERSION = "1.0.1"
FLOOD_PROTECTION_DELAY = 3  # Detik antar download/copy

@Altruix.register_on_cmd(["dlstory"], bot_mode_unsupported=True)
@log_errors
async def download_story_cmd(c: Client, m: Message):
    """
    Download/Copy a story from a given link using Kurigram copy_story.
    Usage: !dlstory <story_link>
    Example: !dlstory https://t.me/username/s/1
    """
    input_ = m.user_input or m.raw_user_input
    if not input_:
        return await m.handle_message(
            "❌ <b>Silakan berikan link story aktif!</b>\n\n"
            "<b>Cara pakai:</b>\n"
            "<code>!dlstory https://t.me/username/s/ID</code>\n\n"
            "<b>Contoh:</b>\n"
            "<code>!dlstory https://t.me/durov/s/12</code>"
        )

    link = input_.split()[0]
    await m.handle_message("🔄 <b>Mencoba memproses story link...</b>")

    try:
        # Regex to extract username and story_id
        # Format: https://t.me/username/s/1 or https://t.me/c/ID/s/1
        if "t.me/" not in link or "/s/" not in link:
            return await m.handle_message("❌ <b>Format link tidak valid!</b> Gunakan format: <code>https://t.me/username/s/ID</code>")

        parts = link.split("/")
        # link format usually ends with /s/ID
        story_id = int(parts[-1])
        target = parts[-3] if "t.me/c/" not in link else f"-100{parts[-3]}"

        await m.handle_message(f"⏬ <b>Menyalin story {story_id} dari {target}...</b>")
        
        # ✅ USE Kurigram copy_story method
        # await client.copy_story(chat_id, from_chat_id, story_id)
        try:
            await c.copy_story(m.chat.id, target, story_id)
            await m.delete_if_self()
        except Exception as e:
            # Fallback to download if copy fails
            await m.handle_message(f"⚠️ <b>Copy gagal, mencoba download manual...</b>\n<i>Error: {str(e)}</i>")
            story = await c.get_stories(target, story_id)
            if not story:
                return await m.handle_message("❌ <b>Story tidak ditemukan atau sudah kadaluarsa.</b>")
            
            file_path = await c.download_media(story)
            if file_path:
                if story.video:
                    await c.send_video(m.chat.id, file_path, caption=f"🎬 <b>Story from @{target}</b>")
                else:
                    await c.send_photo(m.chat.id, file_path, caption=f"🖼️ <b>Story from @{target}</b>")
                if os.path.exists(file_path):
                    os.remove(file_path)
                await m.delete_if_self()
            else:
                await m.handle_message("❌ <b>Gagal mendownload media story secara manual.</b>")

    except Exception as e:
        await m.handle_message(f"❌ <b>Terjadi kesalahan:</b>\n<code>{str(e)}</code>")


@Altruix.register_on_cmd(["stories"], bot_mode_unsupported=True)
@log_errors
async def list_stories_cmd(c: Client, m: Message):
    """
    Download all active stories from a user.
    Usage: !stories <username/ID>
    """
    input_ = m.user_input or m.raw_user_input
    if not input_:
        return await m.handle_message(
            "❌ <b>Silakan berikan username atau user ID!</b>\n\n"
            "<b>Cara pakai:</b>\n"
            "<code>!stories @username</code> atau <code>!stories 12345678</code>"
        )

    target = input_.split()[0]
    await m.handle_message(f"🔍 <b>Mencari stories aktif dari {target}...</b>")

    try:
        # Get active stories using get_chat_stories generator
        stories_count = 0
        async for story in c.get_chat_stories(target):
            try:
                # Copy directly to current chat
                await c.copy_story(m.chat.id, target, story.id)
                stories_count += 1
                await asyncio.sleep(FLOOD_PROTECTION_DELAY)
            except Exception:
                # Fallback to download
                file_path = await c.download_media(story)
                if file_path:
                    if story.video:
                        await c.send_video(m.chat.id, file_path, caption=f"🎬 Story {story.id} from {target}")
                    else:
                        await c.send_photo(m.chat.id, file_path, caption=f"🖼️ Story {story.id} from {target}")
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    stories_count += 1
                    await asyncio.sleep(FLOOD_PROTECTION_DELAY)

        if stories_count == 0:
            return await m.handle_message(f"❌ <b>Tidak ada story aktif ditemukan untuk {target}.</b>")

        await m.handle_message(f"✅ <b>Berhasil menyalin {stories_count} stories dari {target}.</b>")
        await asyncio.sleep(3)
        await m.delete_if_self()

    except Exception as e:
        await m.handle_message(f"❌ <b>Error:</b> <code>{str(e)}</code>")

# Add help info
Altruix._command_help_message_data["xstories"] = (
    "<b>✨ Story Downloader (Kurigram Powered)</b>\n\n"
    "Plugin ini memudahkan Anda mendownload atau menyalin story Telegram dari link atau username.\n\n"
    "<b>Perintah Tersedia:</b>\n"
    "• <code>!dlstory &lt;link&gt;</code>\n"
    "  Menyalin story spesifik dari link t.me.\n"
    "  Contoh: <code>!dlstory https://t.me/durov/s/12</code>\n\n"
    "• <code>!stories &lt;username/ID&gt;</code>\n"
    "  Mengambil SEMUA story aktif dari user tersebut.\n"
    "  Contoh: <code>!stories @username</code>\n\n"
    "<i>Fitur ini mendukung proteksi Anti-Flood otomatis.</i>"
)
