# Main/plugins/userbot/xstories.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.

from Main import Altruix
from pyrogram import Client, filters, enums, raw
from pyrogram.types import Message, MessageEntity
from pyrogram.errors import FloodWait, MessageNotModified
from Main.core.decorators import log_errors
import asyncio
import os
import time

# ============================================================================
# SETTINGS & CONSTANTS
# ============================================================================
PLUGIN_VERSION = "1.0.4"
FLOOD_PROTECTION_DELAY = 1.5  # Reduced default delay, will increase if hit flood
MAX_RETRIES = 3

async def safe_edit(msg: Message, text: str, parse_mode=enums.ParseMode.HTML):
    """
    Helper to safely edit message, ignoring MessageNotModified error.
    Only edits if text is different (simple check) or just try-except.
    """
    if not msg: return
    try:
        # Simple optimization: check if text is same (if available)
        if msg.text == text: return 
        await msg.edit(text, parse_mode=parse_mode)
    except MessageNotModified:
        pass
    except Exception as e:
        # Fallback log
        pass

def clean_premium_cation(caption, entities, is_premium_session):
    """
    Remove premium emojis from caption/entities if session is not premium.
    Returns: (cleaned_caption, cleaned_entities)
    """
    if is_premium_session:
        return caption, entities
    
    if not entities:
        return caption, None

    # Filter out CUSTOM_EMOJI entities
    new_entities = []
    for entity in entities:
        if entity.type != enums.MessageEntityType.CUSTOM_EMOJI:
            new_entities.append(entity)
            
    # If we just drop the entity for custom emoji, the text remains as the fallback char (usually valid).
    # So we don't need to modify caption text itself, just the metadata.
    
    return caption, new_entities

async def process_story(c: Client, target_chat_id: int, target_user: str, story_id: int, status_msg: Message = None):
    """
    Helper function to process a single story:
    1. Try copy_story (Preferred)
    2. If fails/restricted, fallback to download_media + send_photo/video
    3. Handles premium caption cleaning
    """
    is_premium = c.me.is_premium
    retries = 0
    
    while retries < MAX_RETRIES:
        try:
            # ✅ PRIORITAS 1: Coba Copy Story (Tercepat & Hemat Bandwidth)
            if is_premium:
                 await c.copy_story(target_chat_id, target_user, story_id)
                 return True
            else:
                # Non-premium try copy first
                await c.copy_story(target_chat_id, target_user, story_id)
                return True

        except Exception as e:
            # Check Error Message
            err_str = str(e)
            bypass_needed = "PREMIUM_ACCOUNT_REQUIRED" in err_str or "STORY_NOT_MODIFIED" in err_str or "bad request" in err_str.lower()
            
            if not bypass_needed:
                 # Jika error bukan karena premium/restrict, mungkin floodwait
                 if isinstance(e, FloodWait):
                     wait_time = e.value + 1
                     if status_msg: await safe_edit(status_msg, f"⏳ <b>FloodWait:</b> Tunggu {wait_time}s...")
                     await asyncio.sleep(wait_time)
                     retries += 1
                     continue
                 else:
                     # Unknown error, log debug logic here if needed
                     pass
            
            if status_msg and retries == 0:
                 await safe_edit(status_msg, f"⚠️ <b>Copy gagal ({err_str[:30]}...), switch ke mode download...</b>")
            
            # ✅ PRIORITAS 2: Bypass (Download & Re-upload)
            try:
                story = await c.get_stories(target_user, story_id)
                if not story:
                    if status_msg: await safe_edit(status_msg, f"❌ <b>Story {story_id} tidak ditemukan.</b>")
                    return False
                    
                # Use in_memory=False to save to disk safely
                file_path = await c.download_media(story, in_memory=False)
                
                if not file_path:
                    if status_msg: await safe_edit(status_msg, "❌ <b>Gagal download media story.</b>")
                    return False
                
                try:
                    # Clean caption if needed
                    caption = story.caption or ""
                    caption_entities = story.caption_entities
                    
                    final_caption, final_entities = clean_premium_cation(caption, caption_entities, is_premium)
                    
                    # Tambahkan credit kecil (jika caption kosong)
                    if not final_caption:
                         final_caption = f"📥 <b>Story from</b> @{target_user}"
                    
                    if story.video:
                        await c.send_video(
                            target_chat_id, 
                            video=file_path, 
                            caption=final_caption, 
                            caption_entities=final_entities
                        )
                    else:
                        await c.send_photo(
                            target_chat_id, 
                            photo=file_path, 
                            caption=final_caption, 
                            caption_entities=final_entities
                        )
                finally:
                    # GUARANTEED CLEANUP
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    
                return True
                
            except FloodWait as fwe:
                 wait_time = fwe.value + 1
                 if status_msg: await safe_edit(status_msg, f"⏳ <b>FloodWait (Download):</b> Tunggu {wait_time}s...")
                 await asyncio.sleep(wait_time)
                 retries += 1
                 continue
            except Exception as bypass_e:
                 if status_msg: await safe_edit(status_msg, f"❌ <b>Bypass Gagal:</b> {str(bypass_e)}")
                 return False
    
    return False

@Altruix.register_on_cmd(["dlstory"], bot_mode_unsupported=True)
@log_errors
async def download_story_cmd(c: Client, m: Message):
    """
    Download/Copy a story from a given link using Kurigram copy_story.
    Support Bypass for Non-Premium Userbots.
    Usage: !dlstory <story_link>
    """
    input_ = m.user_input or m.raw_user_input
    if not input_:
        return await m.handle_message(
            "❌ <b>Silakan berikan link story aktif!</b>\n\n"
            "<b>Cara pakai:</b>\n"
            "<code>!dlstory https://t.me/username/s/ID</code>\n\n"
            "<b>Output:</b> Pesan akan dikirim ke chat ini."
        )

    link = input_.split()[0]
    status_msg = await m.handle_message("🔄 <b>Mencoba memproses story link...</b>")

    try:
        if "t.me/" not in link or "/s/" not in link:
            return await safe_edit(status_msg, "❌ <b>Format link tidak valid!</b> Gunakan format: <code>https://t.me/username/s/ID</code>")

        parts = link.split("/")
        # Trik parsing lazy: ambil integer terakhir sbg ID, dan part sebelum /s/ sebagai username/chatid
        if parts[-2] == 's':
             story_id = int(parts[-1])
             target_raw = parts[-3]
        elif parts[-2].isdigit(): # Case https://t.me/c/xxx/ID
             story_id = int(parts[-1])
             target_raw = parts[-3] # kemungkinan 'c' lalu ID
             if parts[-4] == 'c':
                 target_raw = f"-100{parts[-3]}"
        else:
             # Fallback parsing standar
             story_id = int(parts[-1])
             target_raw = parts[-3] if "t.me/c/" not in link else f"-100{parts[-3]}"

        # Fix target type (int/str)
        if target_raw.lstrip('-').isdigit():
             target = int(target_raw) # Chat ID
        else:
             target = target_raw # Username

        await safe_edit(status_msg, f"⏬ <b>Mengambil story no {story_id} dari {target}...</b>")
        
        # PROCESS
        success = await process_story(c, m.chat.id, target, story_id, status_msg)
        
        if success:
              await status_msg.delete()
              await m.delete_if_self()
        else:
              # Error message sudah dihandle di dalam func atau status_msg terakhir
              pass

    except FloodWait as e:
        await safe_edit(status_msg, f"⏳ <b>FloodWait Detected:</b> Tunggu {e.value} detik.")
    except Exception as e:
        await safe_edit(status_msg, f"❌ <b>Terjadi kesalahan:</b>\n<code>{str(e)}</code>")


@Altruix.register_on_cmd(["stories"], bot_mode_unsupported=True)
@log_errors
async def list_stories_cmd(c: Client, m: Message):
    """
    Download all active stories from a user.
    Usage: !stories <username/ID>
    Safe for floodwait & tries RAW method if standard fails.
    """
    input_ = m.user_input or m.raw_user_input
    if not input_:
        return await m.handle_message(
            "❌ <b>Silakan berikan username atau user ID!</b>\n\n"
            "<b>Cara pakai:</b>\n"
            "<code>!stories @username</code>"
        )

    target_input = input_.split()[0]
    
    if target_input.lstrip('-').isdigit():
             target = int(target_input)
    else:
             target = target_input

    status_msg = await m.handle_message(f"🔍 <b>Mencari stories aktif dari {target}...</b>")

    try:
        stories_count = 0
        failed_count = 0
        found_stories_ids = []
        
        # Resolve target to get ID for better API compatibility
        try:
            target_peer = await c.get_chat(target)
            target_id = target_peer.id
        except Exception as e:
            return await safe_edit(status_msg, f"❌ <b>Gagal mendapatkan info target:</b> {str(e)}")

        # 🟢 METODE 1: Standard Pyrogram get_chat_stories
        try:
            async for story in c.get_chat_stories(target_id):
                if story.id not in found_stories_ids:
                    found_stories_ids.append(story.id)
        except Exception as e:
            Altruix.log(f"Metode 1 Stories failed: {e}", level=logging.WARNING)

        # 🟢 METODE 2: RAW Fallback (Jika Metode 1 gagal/kosong)
        if not found_stories_ids:
             try:
                 await safe_edit(status_msg, f"🔍 <b>Mencari via RAW method...</b>")
                 peer = await c.resolve_peer(target_id)
                 raw_result = await c.invoke(raw.functions.stories.GetPeerStories(peer=peer))
                 
                 if hasattr(raw_result, "stories"):
                      for s in raw_result.stories:
                           if hasattr(s, "id") and s.id not in found_stories_ids:
                                found_stories_ids.append(s.id)
             except Exception as e:
                 Altruix.log(f"Metode 2 Stories failed: {e}", level=logging.ERROR)
        
        # 🟢 HASIL PENCARIAN
        if not found_stories_ids:
            # Last resort: Try common range of IDs if it's a known active user (Experimental)
            # But let's stick to the current methods for now and maybe just improve error reporting
            return await safe_edit(status_msg, f"❌ <b>Tidak ada story aktif ditemukan untuk {target}.</b>\n\nTips: Pastikan user tersebut memiliki story aktif yang bisa Anda lihat.")

        await safe_edit(status_msg, f"⬇️ <b>Ditemukan {len(found_stories_ids)} stories. Mulai proses download...</b>")
        
        # 🟢 PROSES DOWNLOAD
        for story_id in found_stories_ids:
            try:
                # Process sequentially 
                success = await process_story(c, m.chat.id, target, story_id, status_msg)
                
                if success:
                    stories_count += 1
                else:
                    failed_count += 1
                
                # Smart delay update
                await safe_edit(status_msg, f"⏳ <b>Proses:</b> {stories_count + failed_count}/{len(found_stories_ids)} (Success: {stories_count})")
                await asyncio.sleep(FLOOD_PROTECTION_DELAY)
                
            except FloodWait as e:
                await safe_edit(status_msg, f"⏳ <b>FloodWait Global:</b> Tidur {e.value}s...")
                await asyncio.sleep(e.value)
                # Retry once logic already in process_story, here we just continue loop
            except Exception:
                failed_count += 1

        await safe_edit(status_msg, f"✅ <b>Selesai!</b>\nBerhasil: {stories_count}\nGagal: {failed_count}")
        await asyncio.sleep(5)
        await status_msg.delete()
        await m.delete_if_self()

    except Exception as e:
        await safe_edit(status_msg, f"❌ <b>Error:</b> <code>{str(e)}</code>")


# Add help info
Altruix._command_help_message_data["xstories"] = (
    "<b>✨ Story Downloader (Smart Bypass v2 + Raw)</b>\n\n"
    "Plugin ini memudahkan Anda mendownload atau menyalin story Telegram.\n"
    "Bot akan <b>otomatis bypass restriction</b> jika akun Anda non-premium atau story diproteksi.\n\n"
    "<b>Perintah Tersedia:</b>\n"
    "• <code>!dlstory &lt;link&gt;</code>\n"
    "  Menyalin story spesifik ke chat ini.\n"
    "  Contoh: <code>!dlstory https://t.me/username/s/12</code>\n\n"
    "• <code>!stories &lt;username/ID&gt;</code>\n"
    "  Mengambil SEMUA story aktif dari target.\n"
    "  Contoh: <code>!stories @username</code>\n\n"
    "⚠️ <b>Catatan:</b>\n"
    "• System otomatis retry & aman dari FloodWait.\n"
    "• Output dikirim ke chat tempat perintah dijalankan."
)
