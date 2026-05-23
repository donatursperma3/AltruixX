# Main/plugins/userbot/xstories.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.

from Main import Altruix
from pyrogram import Client, filters, enums, raw
from pyrogram.types import (
    Message, MessageEntity, InlineKeyboardMarkup, 
    InlineKeyboardButton, CallbackQuery, InlineQuery,
    InlineQueryResultArticle, InputTextMessageContent
)
from pyrogram.errors import FloodWait, MessageNotModified as BotMessageNotModified, FileReferenceExpired, MessageNotModified
from Main.core.decorators import log_errors
from pyrogram.handlers import InlineQueryHandler, CallbackQueryHandler
import asyncio
import json
import os
import time
import re
import html
import logging
import random
import string
import traceback
# Import task management helpers
from Main.plugins.userbot.xtaskmanager import register_task, unregister_task, generate_task_id

# ============================================================================
# SETTINGS & CONSTANTS
# ============================================================================
PLUGIN_VERSION = "1.0.618"
FLOOD_PROTECTION_DELAY = 1.5  # Jeda antar story download (detik), naik otomatis saat FloodWait
MAX_RETRIES = 2                # Maksimal retry per story jika terkena FloodWait

# Shared state persistence logic
# Dedicated Persistence Logic (Gcast Pattern)
from pathlib import Path
from Main.utils.file_helpers import get_db_path
SESSION_FILE = Path(get_db_path("xstories_sessions.json"))

def _load_all_sessions() -> dict:
    """Load all story sessions from dedicated JSON file."""
    try:
        if SESSION_FILE.exists():
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        Altruix.log(f"xstories: Load Sessions Error: {e}", level=logging.DEBUG)
    return {}

def _save_all_sessions(data: dict):
    """Save all story sessions to dedicated JSON file synchronously for robustness."""
    try:
        SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            # Pre-processing to convert any remaining SETs to LISTs for safety
            safe_data = {}
            for sid, s_dict in data.items():
                if not isinstance(s_dict, dict): continue
                s_copy = s_dict.copy()
                if "selected" in s_copy and isinstance(s_copy["selected"], set):
                    s_copy["selected"] = list(s_copy["selected"])
                # Remove non-serializable objects
                s_copy.pop("client", None)
                s_copy.pop("bot", None)
                safe_data[sid] = s_copy
            json.dump(safe_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        Altruix.log(f"xstories: Save Sessions Error: {e}", level=40)

# [Gcast Pattern] Global in-memory session cache for instant synchronization across Bot/Userbot
_STORY_SESSIONS_CACHE = _load_all_sessions()

async def get_session(sid):
    """
    Get session from memory cache with disk fallback for cross-process sync.
    [v1.0.613] Added automatic re-sync if session is missing or incomplete (e.g. missing target_id).
    """
    global _STORY_SESSIONS_CACHE
    
    # Proactive Re-Sync: If session is missing OR critical rebuilding fields like target_id are missing,
    # reload from disk to catch updates from the other context (Userbot <-> Bot Assistant sync).
    is_incomplete = False
    if sid in _STORY_SESSIONS_CACHE:
        # Check if it was just a skeleton session without target details
        if "target_id" not in _STORY_SESSIONS_CACHE[sid]:
            is_incomplete = True
            
    if sid not in _STORY_SESSIONS_CACHE or is_incomplete:
        fresh_data = _load_all_sessions()
        if sid in fresh_data:
            _STORY_SESSIONS_CACHE[sid] = fresh_data[sid]
            # Altruix.log(f"xstories: Session {sid} re-synced from disk for cross-client consistency.", level=logging.DEBUG)
        elif is_incomplete:
            # If still incomplete after reload, we just use what we have to avoid infinite loop
            pass
        else:
            return None
            
    # Use a copy to avoid in-memory set/list mutation issues during re-saves
    data = _STORY_SESSIONS_CACHE[sid].copy()
    data["_id"] = sid
    
    # Re-hydrate Userbot Client
    cid = data.get("client_id")
    data["client"] = next((c for c in Altruix.clients if c.me and c.me.id == cid), None)
    
    # Re-hydrate Bot Assistant
    bid = data.get("bot_id")
    if bid:
        if bid == (Altruix.bot.me.id if Altruix.bot and Altruix.bot.me else 0):
            data["bot"] = Altruix.bot
        else:
            data["bot"] = Altruix.bot_manager.get_bot(bid) if hasattr(Altruix, "bot_manager") else Altruix.bot
    else:
        data["bot"] = Altruix.bot
        
    # Convert list back to set for 'selected' stories
    if "selected" in data and isinstance(data["selected"], list):
        data["selected"] = set(data["selected"])
    return data

async def save_session(sid, data=None, update_dict=None):
    """Update memory cache and persist to JSON file (Gcast Pattern)."""
    global _STORY_SESSIONS_CACHE
    
    if update_dict:
        # Granular Update in Memory
        if sid not in _STORY_SESSIONS_CACHE:
            return
        
        # Pre-process update_dict (convert sets to lists)
        if "selected" in update_dict and isinstance(update_dict["selected"], set):
            update_dict["selected"] = list(update_dict["selected"])
        
        # Ensure we don't save non-serializable objects
        update_dict.pop("client", None)
        update_dict.pop("bot", None) 
        _STORY_SESSIONS_CACHE[sid].update(update_dict)
    elif data:
        # Full save to Memory Cache
        save_data = data.copy()
        if "selected" in save_data and isinstance(save_data["selected"], set):
            save_data["selected"] = list(save_data["selected"])
        save_data.pop("client", None)
        save_data.pop("bot", None) 
        _STORY_SESSIONS_CACHE[sid] = save_data
    
    # Synchronously persist to disk for robustness (adopted from Gcast)
    _save_all_sessions(_STORY_SESSIONS_CACHE)

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
        Altruix.log(f"safe_edit error: {e}", level=logging.DEBUG)

def clean_premium_entities(entities, is_premium_session):
    """
    Remove premium emojis from entities if session is not premium.
    """
    if is_premium_session or not entities:
        return entities

    # Filter out CUSTOM_EMOJI entities
    return [e for e in entities if e.type != enums.MessageEntityType.CUSTOM_EMOJI]

def entities_to_html(text, entities):
    """
    Convert caption text and entities to HTML.
    Very basic implementation for stories.
    """
    if not entities:
        return html.escape(text or "")
    
    # Sort entities by offset descending to insert tags without messing up indices
    sorted_entities = sorted(entities, key=lambda e: e.offset, reverse=True)
    html_text = list(text or "")
    
    for e in sorted_entities:
        start = e.offset
        end = e.offset + e.length
        content = html.escape("".join(html_text[start:end]))
        
        tag_start = ""
        tag_end = ""
        
        if e.type == enums.MessageEntityType.BOLD:
            tag_start, tag_end = "<b>", "</b>"
        elif e.type == enums.MessageEntityType.ITALIC:
            tag_start, tag_end = "<i>", "</i>"
        elif e.type == enums.MessageEntityType.CODE:
            tag_start, tag_end = "<code>", "</code>"
        elif e.type == enums.MessageEntityType.PRE:
            tag_start, tag_end = "<pre>", "</pre>"
        elif e.type == enums.MessageEntityType.TEXT_LINK:
            tag_start, tag_end = f'<a href="{e.url}">', "</a>"
        elif e.type == enums.MessageEntityType.MENTION:
            tag_start, tag_end = "<a>", "</a>" # Just to keep style
        elif e.type == enums.MessageEntityType.URL:
            tag_start, tag_end = "<a>", "</a>"
        elif e.type == enums.MessageEntityType.CUSTOM_EMOJI:
            tag_start, tag_end = f'<emoji id="{e.custom_emoji_id}">', "</emoji>"
            
        if tag_start:
            html_text[start:end] = [tag_start + content + tag_end]
            
    return "".join(html_text)

async def process_story(c: Client, target_chat_id: int, target_user: str, story_id: int, status_msg: Message = None, watermark: bool = False, session: dict = None, reply_to_id: int = None, return_media: bool = False, raise_errors: bool = False):
    """
    Helper function to process a single story:
    1. Try copy_story (Fastest) - Skip if watermark required to avoid extra API hits or if return_media is True
    2. If watermark ON or return_media is True: Try send_media with file_id / Create InputMedia
    3. Fallback to download_media + send_photo/video / Create InputMedia (Bypass Restricted)
    
    Returns:
        - If return_media=False: bool (Success/Fail)
        - If return_media=True: tuple (InputMedia object, local_file_path_to_clean) or (None, None)
    """
    is_premium = c.me.is_premium
    retries = 0
    
    while retries < MAX_RETRIES:
        try:
            # Step 0: Get story info to check type & caption
            story = await asyncio.wait_for(c.get_stories(target_user, story_id), timeout=15.0)
            if not story:
                if raise_errors: raise Exception("Story sudah dihapus, kadaluarsa, atau tidak dapat diakses.")
                return False
                
            # Strip tags for metadata
            clean_target_name = re.sub(r'<[^>]+>', '', str(target_user))
            wm_text = ""
            if watermark:
                # [v1.0.615] Resolve target chat for clickable source mention
                target_id = "N/A"
                source_display = clean_target_name
                try:
                    chat = await c.get_chat(target_user)
                    target_id = chat.id
                    
                    # Determine link based on type
                    if chat.type in [enums.ChatType.CHANNEL, enums.ChatType.SUPERGROUP, enums.ChatType.GROUP]:
                        username = getattr(chat, "username", None)
                        if username:
                            link = f"https://t.me/{username}"
                        else:
                            stripped_id = str(target_id).replace("-100", "")
                            link = f"https://t.me/c/{stripped_id}/1"
                    else:
                        link = f"tg://user?id={target_id}"
                    
                    source_name = html.escape(chat.first_name or chat.title or str(target_user))
                    source_display = f'<a href="{link}">{source_name}</a>'
                except:
                    # Fallback to plain if get_chat fails
                    source_display = html.escape(clean_target_name)

                # [v1.0.612] Calculate media size for watermark
                media_size_str = "N/A"
                try:
                    raw_size = None
                    if getattr(story, "video", None):
                        raw_size = getattr(story.video, "file_size", None)
                    elif getattr(story, "photo", None):
                        raw_size = getattr(story.photo, "file_size", None)
                    if raw_size and raw_size > 0:
                        if raw_size >= 1073741824:
                            media_size_str = f"{raw_size / 1073741824:.2f} GB"
                        elif raw_size >= 1048576:
                            media_size_str = f"{raw_size / 1048576:.2f} MB"
                        elif raw_size >= 1024:
                            media_size_str = f"{raw_size / 1024:.2f} KB"
                        else:
                            media_size_str = f"{raw_size} B"
                except: pass
                # Premium watermark style (v1.0.576)
                wm_text = (
                    f"\n\n• ID: <code>{target_id}</code>"
                    f"\n• Source: {source_display}"
                    f"\n• Story ID: <code>{story_id}</code>"
                    f"\n• Size: <code>{media_size_str}</code>"
                    f"\n\n<i>Powered by Altroid-X</i>"
                )

            # ✅ PRIORITAS 0: copy_story (Paling Hemat Bandwidth)
            # Skip if return_media is True (cannot group a copy result into an album easily)
            try:
                if not return_media:
                    # Resolve caption with entities
                    cleaned_entities = clean_premium_entities(story.caption_entities, is_premium)
                    base_html = entities_to_html(story.caption, cleaned_entities)
                    final_caption = base_html + wm_text
                    
                    # Tambahkan label default jika kosong sama sekali
                    if not final_caption.strip():
                        final_caption = f"🎬 <b>Story from</b> @{target_user}{wm_text}" if getattr(story, "video", None) else f"🖼 <b>Story from</b> @{target_user}{wm_text}"

                    # Copy story (server-side)
                    msg = await asyncio.wait_for(c.copy_story(target_chat_id, target_user, story_id, reply_to_message_id=reply_to_id), timeout=20.0)
                    if msg:
                        # Jika watermark ON, edit captionnya
                        if watermark:
                            try:
                                # Gunakan parse_mode=HTML agar tags terbaca
                                await msg.edit_caption(final_caption, parse_mode=enums.ParseMode.HTML)
                            except Exception as edit_e:
                                Altruix.log(f"Watermark edit failed (non-critical): {edit_e}", level=logging.DEBUG)
                        return True
            except Exception as copy_e:
                Altruix.log(f"copy_story failed for story {story_id}, trying send_media: {copy_e}", level=logging.DEBUG)

            # ✅ PRIORITAS 1: Server-Side Send via file_id (Jika restricted atau copy_story gagal)
            try:
                # [Fix for FILE_REFERENCE_X_EXPIRED]: Album mode requires physical downloads
                if return_media:
                    raise Exception("Skipping Priority 1: Album mode requires physical download to avoid FileReferenceExpired")
                
                # Gunakan caption yang sudah diproses tadi
                cleaned_entities = clean_premium_entities(story.caption_entities, is_premium)
                base_html = entities_to_html(story.caption, cleaned_entities)
                final_caption = base_html + wm_text
                if not final_caption.strip():
                    final_caption = f"🎬 <b>Story from</b> @{target_user}{wm_text}" if getattr(story, "video", None) else f"🖼 <b>Story from</b> @{target_user}{wm_text}"

                if getattr(story, "video", None):
                    if return_media:
                        from pyrogram.types import InputMediaVideo
                        return InputMediaVideo(
                            story.video.file_id, 
                            caption=final_caption, 
                            parse_mode=enums.ParseMode.HTML
                        ), None
                        
                    await c.send_video(
                        target_chat_id, 
                        video=story.video.file_id, 
                        caption=final_caption, 
                        parse_mode=enums.ParseMode.HTML,
                        reply_to_message_id=reply_to_id
                    )
                else:
                    if return_media:
                        from pyrogram.types import InputMediaPhoto
                        return InputMediaPhoto(
                            story.photo.file_id, 
                            caption=final_caption, 
                            parse_mode=enums.ParseMode.HTML
                        ), None
                        
                    await c.send_photo(
                        target_chat_id, 
                        photo=story.photo.file_id, 
                        caption=final_caption, 
                        parse_mode=enums.ParseMode.HTML,
                        reply_to_message_id=reply_to_id
                    )
                return True
            except FileReferenceExpired:
                Altruix.log(f"File reference expired for story {story_id}, attempting recovery...", level=logging.WARNING)
                # Re-fetch story to get fresh file_id
                try:
                    await asyncio.sleep(2) # Brief wait for TG cache
                    await c.get_chat(target_user) # Refresh peer metadata
                except: pass
                story = await asyncio.wait_for(c.get_stories(target_user, story_id), timeout=15.0)
                if not story: 
                    Altruix.log(f"Recovery failed: Story {story_id} not found after refresh.", level=logging.WARNING)
                    return False
                # Try bypass directly to be safe
                Altruix.log(f"Recovery successful for story {story_id}, moving to bypass.", level=logging.INFO)
            except Exception as e:
                # Jika masih gagal, lanjut ke download (Priority 3/Bypass)
                Altruix.log(f"Server-side send failed for story {story_id}: {repr(e)}", level=logging.INFO)

            # ✅ PRIORITAS 2: Bypass (Download & Re-upload)
            try:
                # [Stabilization-v1.0.574] Pre-emptive peer refresh & Ultra-fresh fetch
                try:
                    Altruix.log(f"Story {story_id} Stage 0: Refreshing peer & story...", level=logging.DEBUG)
                    await c.get_chat(target_user)
                    fresh_story = await asyncio.wait_for(c.get_stories(target_user, story_id), timeout=15.0)
                    if fresh_story: story = fresh_story
                except: pass

                # Determine what to download
                media_to_dl = None
                if getattr(story, "video", None):
                    media_to_dl = story.video # Gunakan objek langsung (lebih sakti dari file_id sbg string)
                    m_type = "Video"
                    m_size = getattr(story.video, "file_size", "unknown")
                elif getattr(story, "photo", None):
                    media_to_dl = story.photo # Gunakan objek langsung
                    m_type = "Photo"
                    m_size = getattr(story.photo, "file_size", "unknown")
                
                if not media_to_dl:
                    Altruix.log(f"No media found in story {story_id} for bypass.", level=logging.WARNING)
                    if raise_errors: raise Exception("Tidak ada foto/video yang bisa di-bypass (Mungkin teks saja).")
                    return False

                Altruix.log(f"Starting physical bypass for story {story_id} ({m_type}, size: {m_size}, premium: {is_premium})...", level=logging.INFO)
                
                # Progress logger & visual status helper
                last_percent = -1
                first_progress_called = False
                async def progress(current, total, action="Download"):
                    nonlocal last_percent, first_progress_called
                    if not first_progress_called:
                        Altruix.log(f"Story {story_id} {action} progress started: {current}/{total}", level=logging.DEBUG)
                        first_progress_called = True
                    if total <= 0: return
                    percent = int(current * 100 / total)
                    # Log & Update UI every 20%
                    if percent % 20 == 0 and percent != last_percent:
                        Altruix.log(f"Story {story_id} {action}: {percent}% ({current}/{total})", level=logging.INFO)
                        if session:
                            session["status_text"] = f"{action} #{story_id} ({percent}%)"
                        if status_msg:
                            icon = "⏳" if action == "Download" else "📤"
                            await safe_edit(status_msg, f"{icon} <b>{action} Story {story_id}:</b> {percent}%")
                        last_percent = percent
                
                # RF-Style Background Progress (To keep UI alive if bitstream is slow)
                async def _background_status():
                    try:
                        await asyncio.sleep(25) # Wait for bitstream
                        if last_percent <= 0:
                            Altruix.log(f"Story {story_id} background check: No progress after 25s.", level=logging.DEBUG)
                            await safe_edit(status_msg, f"⏳ <b>Download Story {story_id}:</b> Bitstream lambat, mohon tunggu...")
                    except: pass
                
                bg_task = asyncio.create_task(_background_status())

                # Stage 1: Attempt Object-based Download (Preferred)
                file_path = None
                try:
                    Altruix.log(f"Story {story_id} Stage 1: Calling download_media(object)...", level=logging.DEBUG)
                    file_path = await asyncio.wait_for(
                        c.download_media(story, in_memory=False, progress=progress, progress_args=("Download",)), 
                        timeout=300.0 
                    )
                    Altruix.log(f"Story {story_id} c.download_media returned: {file_path}", level=logging.DEBUG)
                except Exception as dl_e:
                    # Stage 2: Fallback to FileID-string (Often triggers different DC relocation)
                    Altruix.log(f"Stage 1 failed for story {story_id}: {repr(dl_e)}. Moving to Stage 2 (FileID)...", level=logging.WARNING)
                    if status_msg: await safe_edit(status_msg, f"⏳ <b>Bypass Story {story_id}:</b> Melakukan re-routing Data Center...")
                    
                    # Reset progress tracker
                    last_percent = -1
                    first_progress_called = False
                    
                    file_path = await asyncio.wait_for(
                        c.download_media(media_to_dl.file_id, in_memory=False, progress=progress, progress_args=("Download",)), 
                        timeout=300.0 
                    )
                
                bg_task.cancel()
                if not file_path: raise Exception("download_media returned None")
                
                Altruix.log(f"Download success: {file_path}. Uploading...", level=logging.INFO)
                
                last_percent = -1 # Reset for upload progress
                thumb_path = None
                try:
                    # Fetch thumbnail if it's a video to prevent blank/black preview
                    if getattr(story, "video", None) and hasattr(story.video, "thumbs") and story.video.thumbs:
                        try:
                            thumb_path = await asyncio.wait_for(c.download_media(story.video.thumbs[0].file_id, in_memory=False), timeout=20.0)
                        except Exception as e:
                            Altruix.log(f"Video story thumb dl failed: {e}", level=logging.DEBUG)
                            
                    # Clean caption if needed
                    cleaned_entities = clean_premium_entities(story.caption_entities, is_premium)
                    base_html = entities_to_html(story.caption, cleaned_entities)
                    final_caption = base_html + wm_text
                    
                    # Tambahkan credit kecil (jika caption kosong)
                    if not final_caption.strip():
                        final_caption = f"🎬 <b>Story from</b> @{target_user}{wm_text}" if getattr(story, "video", None) else f"🖼 <b>Story from</b> @{target_user}{wm_text}"
                    
                    if getattr(story, "video", None):
                        if return_media:
                            from pyrogram.types import InputMediaVideo
                            return InputMediaVideo(
                                file_path, 
                                thumb=thumb_path,
                                caption=final_caption, 
                                parse_mode=enums.ParseMode.HTML
                            ), [f for f in (file_path, thumb_path) if f]  # We return file paths list to let caller handle cleanup

                        await c.send_video(
                            target_chat_id, 
                            video=file_path, 
                            thumb=thumb_path,
                            caption=final_caption, 
                            parse_mode=enums.ParseMode.HTML,
                            progress=progress,
                            progress_args=("Upload",),
                            reply_to_message_id=reply_to_id
                        )
                    else:
                        if return_media:
                            from pyrogram.types import InputMediaPhoto
                            return InputMediaPhoto(
                                file_path, 
                                caption=final_caption, 
                                parse_mode=enums.ParseMode.HTML
                            ), [file_path]

                        await c.send_photo(
                            target_chat_id, 
                            photo=file_path, 
                            caption=final_caption, 
                            parse_mode=enums.ParseMode.HTML,
                            progress=progress,
                            progress_args=("Upload",),
                            reply_to_message_id=reply_to_id
                        )
                finally:
                    # GUARANTEED CLEANUP (If not returning media for delayed sending)
                    if not return_media:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                        if thumb_path and os.path.exists(thumb_path):
                            os.remove(thumb_path)
                    
                return True
                
            except FloodWait as fwe:
                wait_time = fwe.value + 1
                if status_msg: await safe_edit(status_msg, f"⏳ <b>FloodWait (Download):</b> Tunggu {wait_time}s...")
                await asyncio.sleep(wait_time)
                retries += 1
                continue
            except Exception as bypass_e:
                if status_msg: await safe_edit(status_msg, f"❌ <b>Bypass Gagal:</b> {repr(bypass_e)}")
                # Re-raise so it hits the while loop's retry logic
                raise bypass_e
        
        except FloodWait as e:
            wait_time = e.value + 1
            if status_msg: await safe_edit(status_msg, f"⏳ <b>FloodWait:</b> Tunggu {wait_time}s...")
            await asyncio.sleep(wait_time)
            retries += 1
        except Exception as e:
            Altruix.log(f"Process story error: {e}", level=logging.DEBUG)
            if raise_errors and retries >= 2: raise e
            retries += 1
    
    if raise_errors: raise Exception("Max retries exceeded dalam process_story (Timeout/Blocked).")
    return (None, None) if return_media else False

# ============================================================================
# CMD: .dlstory — Download story tunggal dari link
# Flow: Parse link → extract username & story_id → process_story()
# ============================================================================
@Altruix.register_on_cmd(
    ["dlstory"], 
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Download/copy a single Telegram story from a link.",
        "description": (
            "Mengunduh atau menyalin satu story spesifik menggunakan link story Telegram.\n"
            "Sangat berguna jika Anda hanya ingin mengambil satu konten tanpa membuka dashboard.\n\n"
            "<b>Format Link yang Didukung:</b>\n"
            "• <code>https://t.me/username/s/123</code> (Public User/Channel)\n"
            "• <code>https://t.me/c/12345/s/678</code> (Private Channel)\n\n"
            "<b>Fitur Unggulan:</b>\n"
            "1. <b>Smart Copy:</b> Mencoba menyalin langsung (server-side) untuk kecepatan maksimal.\n"
            "2. <b>Bypass Restricted:</b> Jika konten diproteksi, bot akan mendownload dan mengunggah ulang secara otomatis.\n"
            "3. <b>Auto-Watermark:</b> Menyertakan informasi sumber story jika fitur watermark aktif.\n\n"
            "<b>Catatan:</b> Output akan dikirim langsung ke chat tempat Anda menjalankan perintah ini."
        ),
        "usage": ".dlstory [link_story]",
        "example": ".dlstory https://t.me/durov/s/12",
    }
)
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
        success = await process_story(c, m.chat.id, target, story_id, status_msg, reply_to_id=m.id)
        
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


# ============================================================================
# CMD: .stories — Download SEMUA story aktif dari user (direct mode)
# Flow: Resolve user → get_chat_stories / RAW fallback → loop process_story()
# ============================================================================
@Altruix.register_on_cmd(
    ["stories"], 
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Interactively download stories from a user/channel.",
        "description": (
            "Membuka <b>Story Picker Dashboard</b> interaktif untuk memilih story apa saja yang ingin didownload dari target.\n\n"
            "<b>Cara Penggunaan:</b>\n"
            "1. Jalankan perintah <code>.stories @username</code> atau <code>.stories ID_TARGET</code>.\n"
            "2. Cek pesan dashboard yang muncul (biasanya dikirim ke Log Group untuk keamanan).\n"
            "3. Klik nomor story untuk memilih (centang ✅).\n"
            "4. Gunakan tombol <b>Download Selected</b> atau <b>Download All</b>.\n\n"
            "<b>Panduan Tombol Dashboard:</b>\n"
            "• <b>[1. 🎬 #ID]:</b> Klik nomor untuk memilih/membatalkan pilihan story.\n"
            "• <b>🔄 Refresh:</b> Scan ulang untuk mencari story terbaru dari target.\n"
            "• <b>⚠️ Reset Status:</b> Gunakan jika dashboard terasa macet atau 'busy' terlalu lama.\n"
            "• <b>☑️ Select All:</b> Pilih semua story yang ditemukan sekaligus.\n"
            "• <b>☐ Deselect All:</b> Batalkan semua pilihan yang sudah dicentang.\n"
            "• <b>Watermark:</b> ON (Sertakan info sumber) | OFF (Tanpa info sumber).\n"
            "• <b>Download Selected:</b> Memulai proses download untuk story yang dicentang.\n"
            "• <b>Download All:</b> Download semua story target (Gunakan dengan bijak).\n"
            "• <b>Cancel:</b> Tutup dashboard dan hapus session penyimpanan."
        ),
        "usage": ".stories [username/ID]",
        "example": ".stories @durov",
    }
)
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
        # Resolve target to get ID for better API compatibility
        try:
            target_peer = await c.get_chat(target)
            target_id = target_peer.id
            
            # [v1.0.601] Resolve name properly for users/channels
            name_raw = target_peer.first_name or target_peer.title or "Unknown"
            clean_name = html.escape(name_raw)
            
            # Build target_display with link based on type
            if target_peer.type in [enums.ChatType.CHANNEL, enums.ChatType.SUPERGROUP, enums.ChatType.GROUP]:
                username = getattr(target_peer, "username", None)
                if username:
                    link = f"https://t.me/{username}"
                else:
                    stripped_id = str(target_id).replace("-100", "")
                    link = f"https://t.me/c/{stripped_id}/1"
            else:
                link = f"tg://user?id={target_id}"
            
            # Format: Clickable name with double-quoted href for inline compatibility
            target_display = f'{clean_name} (<a href="{link}"><code>{target_id}</code></a>)'
            target_username = getattr(target_peer, "username", None) or target_id
            
            # Store raw components for robust rebuilding in Bot Assistant
            session_target_id = target_id
            session_target_name = name_raw
        except Exception as e:
            return await safe_edit(status_msg, f"❌ <b>Gagal mendapatkan info target:</b> <code>{str(e)}</code>")

        story_data = await discover_stories(c, target_id)
        
        if not story_data:
            return await safe_edit(
                status_msg,
                f"❌ <b>Tidak ada story aktif ditemukan untuk {target_display}.</b>\n\n"
                f"Tips: Pastikan user tersebut memiliki story aktif yang bisa Anda lihat."
            )

        # Pass current chat as primary, Log Group as fallback logic inside show_story_menu
        # [v1.0.613] Pass raw target info directly to initial session for perfect link rendering
        sid = await show_story_menu(
            c, m.chat.id, target_username, target_display, story_data, 
            reply_to_id=m.id, target_id=session_target_id, target_name=session_target_name
        )
        
        if sid:
            session = await get_session(sid)
            sent_to_log = session.get("sent_to") == "log" if session else False
            target_cid = session.get("menu_chat_id", m.chat.id) if session else m.chat.id
            
            msg_link = ""
            if session and session.get("menu_msg_id") and str(target_cid).startswith("-100"):
                msg_link = f"https://t.me/c/{str(target_cid).replace("-100", "").lstrip("-")}/{session['menu_msg_id']}"
            
            if sent_to_log:
                success_text = "✅ <b>Story Picker Menu sent to Log Group!</b>\n\n<i>Check your Log Group to choose a story.</i>"
            else:
                success_text = "✅ <b>Menu Story Picker successfully sent!</b>"
                
            if msg_link:
                success_text += f'\n👉 <b><a href="{msg_link}">Open Dashboard Menu</a></b>'
                
            await safe_edit(status_msg, success_text)
            # Auto-delete notification after 3 seconds to keep chat clean
            await asyncio.sleep(3)
            try: await status_msg.delete()
            except: pass
        else:
            await safe_edit(status_msg, "❌ <b>Gagal mengirim menu interaktif ke chat ini atau Log Group.</b>")
            
        # Delete the trigger command
        await m.delete_if_self()

    except Exception as e:
        await safe_edit(status_msg, f"❌ <b>Error:</b> <code>{str(e)}</code>")

# ============================================================================
# INTERACTIVE STORY SELECTION SYSTEM
# 
# Arsitektur:
#   1. User menjalankan .rstories / .rlinkstories
#   2. discover_stories() mencari story aktif (Pyrogram + RAW fallback)
#   3. show_story_menu() mengirim pesan inline buttons via Bot Assistant
#   4. User memilih story via toggle buttons → callback sdl_tog_*
#   5. User klik Download Selected/All → execute_story_download() berjalan
#      di background task (asyncio.create_task)
#   6. Session auto-cleanup setelah 5 menit
#
# Callback data format: sdl_{action}_{session_id}[_{story_id}]
#   Actions: tog, selall, desel, dlsel, dlall, confirmall, back, cancel
# ============================================================================

# Helper to generate unique session ID
def _gen_sid():
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=6))

async def discover_stories(c: Client, user_id):
    """
    Find active stories using multiple methods.
    Returns: list of (story_id, type_string)
    """
    # Pre-warming peer cache to avoid PEER_ID_INVALID
    try:
        if isinstance(user_id, str) or (isinstance(user_id, int) and user_id > 0):
             await c.resolve_peer(user_id)
             Altruix.log(f"discover_stories: Peer warmed for {user_id}", level=logging.DEBUG)
    except Exception as pw_e:
        Altruix.log(f"discover_stories: Peer warming failed for {user_id}: {pw_e}", level=logging.DEBUG)

    # v1.0.602+: Stagger discovery to avoid thundering herd across multiple accounts
    await asyncio.sleep(random.uniform(0.1, 0.6))
    
    story_data = []
    
    def _get_stype(s):
        """Helper to determine if a story is a Video or Photo (supports Pyrogram Story and Raw StoryItem)."""
        # Case A: Pyrogram Story (Method 1)
        if hasattr(s, "video"):
            return "Video" if s.video else "Photo"
        # Case B: Raw StoryItem (Method 2, 3, 4)
        media = getattr(s, "media", None)
        if media:
            if isinstance(media, raw.types.MessageMediaDocument):
                return "Video"
            return "Photo"
        return "Photo"

    # [Diagnostic] Check Chat Metadata
    try:
        chat = await c.get_chat(user_id)
        has_stories = getattr(chat, "has_visible_stories", "Unknown")
        Altruix.log(f"discover_stories: Chat metadata for {user_id}: has_visible_stories={has_stories}", level=logging.DEBUG)
    except Exception as e:
        Altruix.log(f"discover_stories: Chat metadata check failed: {e}", level=logging.DEBUG)

    # Method 1: Pyrogram
    try:
        Altruix.log(f"discover_stories: Trying Method 1 (Pyrogram) for {user_id}", level=logging.DEBUG)
        async for s in c.get_chat_stories(user_id):
            story_data.append((s.id, _get_stype(s)))
    except Exception as e:
        Altruix.log(f"discover_stories (Method 1) error for {user_id}: {e}", level=logging.DEBUG)
        
    # Method 2: Raw API Fallback (GetPeerStories)
    if not story_data:
        try:
            Altruix.log(f"discover_stories: Trying Method 2 (Raw GetPeerStories) for {user_id}", level=logging.DEBUG)
            peer = await c.resolve_peer(user_id)
            res = await c.invoke(
                raw.functions.stories.GetPeerStories(peer=peer)
            )
            
            # [Fix for v1.0.585] Extract from PeerStories
            stories_list = None
            if res:
                candidate = getattr(res, "stories", None)
                if isinstance(candidate, (list, raw.core.List)):
                    stories_list = candidate
                elif hasattr(candidate, "stories") and isinstance(candidate.stories, (list, raw.core.List)):
                    stories_list = candidate.stories
                elif isinstance(res, (list, raw.core.List)):
                    stories_list = res
                
                if stories_list:
                    count = 0
                    for s in stories_list:
                        if isinstance(s, raw.types.StoryItem):
                            story_data.append((s.id, _get_stype(s)))
                            count += 1
                    Altruix.log(f"discover_stories: Method 2 iterated {count} items.", level=logging.DEBUG)
        except Exception as e:
            Altruix.log(f"discover_stories (Method 2) error for {user_id}: {repr(e)}", level=logging.DEBUG)

    # Method 3: Raw API Fallback (GetFullUser)
    if not story_data:
        try:
            Altruix.log(f"discover_stories: Trying Method 3 (Raw GetFullUser) for {user_id}", level=logging.DEBUG)
            peer = await c.resolve_peer(user_id)
            full_user = await c.invoke(
                raw.functions.users.GetFullUser(id=peer)
            )
            # full_user.full_user: UserFull
            if hasattr(full_user, "full_user") and hasattr(full_user.full_user, "stories"):
                peer_stories = full_user.full_user.stories
                stories_list_raw = getattr(peer_stories, "stories", [])
                if stories_list_raw:
                    count = 0
                    for s in stories_list_raw:
                        if isinstance(s, raw.types.StoryItem):
                            story_data.append((s.id, _get_stype(s)))
                            count += 1
                    Altruix.log(f"discover_stories: Method 3 (FullUser) iterated {count} items.", level=logging.DEBUG)
        except Exception as e:
            Altruix.log(f"discover_stories (Method 3) error for {user_id}: {repr(e)}", level=logging.DEBUG)

    # Method 4 & 5: Fetch Pinned/Archived Stories (Up to 500) to bypass the 100-story limit
    try:
        Altruix.log(f"discover_stories: Fetching Pinned (Archived) Stories for {user_id}", level=logging.DEBUG)
        peer = await c.resolve_peer(user_id)
        offset_id = 0
        pinned_count = 0
        while pinned_count < 500:  # Hard cap at 500 to prevent infinite loops
            res = await c.invoke(
                raw.functions.stories.GetPinnedStories(peer=peer, offset_id=offset_id, limit=100)
            )
            stories_list = getattr(res, "stories", []) if res else []
            if not stories_list:
                break
            
            added_in_batch = 0
            last_id = 0
            for s in stories_list:
                if isinstance(s, raw.types.StoryItem):
                    story_data.append((s.id, _get_stype(s)))
                    added_in_batch += 1
                    last_id = s.id
            
            pinned_count += added_in_batch
            if added_in_batch < 100:
                break  # Last page
                
            offset_id = last_id  # Pagination cursor
            await asyncio.sleep(0.3)
            
        Altruix.log(f"discover_stories: Pinned Loop returned {pinned_count} total archive stories.", level=logging.DEBUG)
    except Exception as e:
        Altruix.log(f"discover_stories (Method 4/Pinned) error for {user_id}: {repr(e)}", level=logging.DEBUG)
            
    # Remove duplicates and sort descending (newest first)
    unique_stories = {sid: stype for sid, stype in story_data}
    sorted_data = sorted(unique_stories.items(), key=lambda x: x[0], reverse=True)
    
    Altruix.log(f"discover_stories: Found {len(sorted_data)} stories for {user_id}", level=logging.DEBUG)
    return sorted_data

# IMPORTANT: Builders are moved to bot/xstories_bot.py
# If Userbot needs them (Tahap 3), we import them.
def get_builders():
    from Main.plugins.bot.xstories_bot import build_story_menu_text, build_story_menu_kb
    return build_story_menu_text, build_story_menu_kb

async def show_story_menu(c: Client, chat_id, target_username, target_display, story_data, reply_to_id=None, target_id=None, target_name=None):
    """
    Main entry point for showing the story picker menu.
    Handles multi-stage sending (Current Chat -> Log Group).
    """
    sid = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    log_chat_id = getattr(Altruix, "log_chat", chat_id)
    
    Altruix.log(f"[show_story_menu] START: sid={sid}, chat_id={chat_id}, log_chat={log_chat_id}, target={target_username}, stories={len(story_data)}", level=logging.DEBUG)
    
    # Store session to DB BEFORE sending to avoid race condition in bot side
    session_data = {
        "_id": sid,
        "client_id": c.me.id,
        "target": target_username,
        "target_display": target_display,
        "target_id": target_id,
        "target_name": target_name,
        "story_data": story_data,
        "selected": set(),
        "page": 0,
        "ts": time.time(),
        "chat_id": chat_id, # Target awal
        "status": "selecting",
        "menu_msg_id": None,
        "menu_chat_id": chat_id,
        "sent_to": "current", # Indicator untuk command handler
        "last_hash": None,    # Untuk cegah MessageNotModified
        "watermark": True,    # New: Watermark toggle
        "send_as_album": False, # ✅ New: Send as album toggle
        "reply_to_id": reply_to_id, # ✅ Simpan ID perintah agar bisa di-reply nanti
    }
    await save_session(sid, session_data)
    
    # Get bot assistant details
    bot_username = None
    target_bot = Altruix.bot # Default
    
    if hasattr(Altruix, 'bot_manager'):
        target_bot = Altruix.bot_manager.get_bot(c.me.id)
        bot_username = Altruix.bot_manager.get_bot_username(c.me.id)
        Altruix.log(f"[show_story_menu] Bot resolved via bot_manager: @{bot_username} (is custom: {target_bot != Altruix.bot})", level=logging.DEBUG)
        
    if not bot_username or bot_username == "Unknown":
        try:
            me_bot = await Altruix.bot.get_me()
            bot_username = me_bot.username
            target_bot = Altruix.bot
            Altruix.log(f"[show_story_menu] Fallback to main bot: @{bot_username}", level=logging.DEBUG)
        except: pass

    # ✅ PROACTIVE REGISTRATION: Pastikan asisten memiliki handler story
    try:
        Altruix.log(f"Registering story handlers for @{bot_username}...", level=logging.DEBUG)
        register_story_bot_handlers(target_bot)
    except Exception as e:
        Altruix.log(f"Failed to register story handlers for {bot_username}: {e}", level=logging.DEBUG)

    # ✅ PRE-EMPTIVE PEER WARMING: Pastikan bot mengenal userbot di peer cache-nya
    # Tanpa ini, bot akan gagal resolve_peer saat menerima inline query dari userbot
    try:
        userbot_id = c.me.id
        # Coba kirim pesan singkat dari bot ke userbot, lalu hapus
        try:
            temp_msg = await target_bot.send_message(userbot_id, "⏳")
            await temp_msg.delete()
            Altruix.log(f"[show_story_menu] Peer warm OK: bot -> userbot ({userbot_id})", level=logging.DEBUG)
        except Exception as pw_e:
            Altruix.log(f"[show_story_menu] Peer warm FAILED: bot -> userbot ({userbot_id}): {pw_e}", level=logging.WARNING)
        # Juga coba warm log_chat_id dan target
        if log_chat_id:
            try:
                await target_bot.resolve_peer(log_chat_id)
                Altruix.log(f"[show_story_menu] Peer warm OK: bot -> log_chat ({log_chat_id})", level=logging.DEBUG)
            except Exception as pw_e2:
                Altruix.log(f"[show_story_menu] Peer warm FAILED: bot -> log_chat ({log_chat_id}): {pw_e2}", level=logging.WARNING)
            
        if target:
            try:
                # If target is ID (int) or username (str)
                await target_bot.resolve_peer(target)
                Altruix.log(f"[show_story_menu] Peer warm OK: bot -> target ({target})", level=logging.DEBUG)
            except: pass
            
        Altruix.log(f"[show_story_menu] Peer warming completed for @{bot_username}", level=logging.DEBUG)
    except Exception as e:
        Altruix.log(f"[show_story_menu] Peer warming FATAL: {e}", level=logging.DEBUG)

    async def try_inline_send(target_cid, b_username, r_id=None):
        try:
            if not b_username or b_username == "Unknown":
                Altruix.log(f"[try_inline_send] Skipped: no bot username.", level=logging.DEBUG)
                return None
            
            Altruix.log(f"[try_inline_send] START: chat={target_cid}, bot=@{b_username}, sid={sid}, reply={r_id}", level=logging.DEBUG)
            
            # Retry loop: Telegram butuh waktu utk propagasi jawaban bot asisten
            # Retry loop: Telegram butuh waktu utk propagasi jawaban bot asisten
            results = None
            for attempt in range(2):
                try:
                    cbust = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
                    query_str = f"sdl_menu_sid_{sid}_{cbust}"
                    Altruix.log(f"[try_inline_send] Attempt {attempt+1}/2: query='{query_str}'", level=logging.DEBUG)
                    results = await asyncio.wait_for(
                        c.get_inline_bot_results(b_username, query_str),
                        timeout=10.0
                    )
                    result_count = len(results.results) if results and results.results else 0
                    Altruix.log(f"[try_inline_send] Attempt {attempt+1} result: {result_count} results", level=logging.DEBUG)
                    if results and results.results:
                        break
                except Exception as attempt_e:
                    Altruix.log(f"[try_inline_send] Attempt {attempt+1} error: {repr(attempt_e)}", level=logging.DEBUG)
                await asyncio.sleep(0.5) 
            
            # Jika semua attempt gagal, kembalikan None
            if not results or not results.results:
                Altruix.log(f"[try_inline_send] FAILED: No results from @{b_username} after 2 retries.", level=logging.WARNING)
                return None
            
            # Kirim hasil inline ke chat tujuan
            Altruix.log(f"[try_inline_send] Got results! Sending to chat {target_cid}...", level=logging.DEBUG)
            sent = await asyncio.wait_for(
                c.send_inline_bot_result(
                    target_cid,
                    results.query_id,
                    results.results[0].id,
                    reply_to_message_id=r_id if target_cid == chat_id else None
                ),
                timeout=15.0
            )
            if sent:
                msg_id = None
                if hasattr(sent, "id"): msg_id = sent.id
                elif hasattr(sent, "updates"):
                    for u in getattr(sent, "updates", []):
                        if hasattr(u, "message") and hasattr(u.message, "id"):
                            msg_id = u.message.id
                            break
                Altruix.log(f"[try_inline_send] SUCCESS: Inline sent to {target_cid}, msg_id={msg_id}", level=logging.INFO)
                return msg_id
        except Exception as e: 
            Altruix.log(f"[try_inline_send] EXCEPTION for {target_cid} via @{b_username}: {repr(e)}", level=logging.WARNING)
        return None

    # TAHAP 1: Coba via Inline Mode di Chat Sekarang (Current Chat)
    if bot_username:
        Altruix.log(f"[show_story_menu] TAHAP 1: Trying inline in current chat {chat_id}...", level=logging.DEBUG)
        msg_id = await try_inline_send(chat_id, bot_username, r_id=reply_to_id)
        
        # Fallback Tahap 1.5: Jika asisten kustom gagal, coba asisten utama
        if not msg_id and target_bot != Altruix.bot:
            try:
                main_bot_me = await Altruix.bot.get_me()
                Altruix.log(f"[show_story_menu] TAHAP 1.5: Custom bot failed, trying main bot @{main_bot_me.username}...", level=logging.DEBUG)
                msg_id = await try_inline_send(chat_id, main_bot_me.username, r_id=reply_to_id)
            except Exception as e15:
                Altruix.log(f"[show_story_menu] TAHAP 1.5 Exception: {e15}", level=logging.DEBUG)

        if msg_id:
            Altruix.log(f"[show_story_menu] TAHAP 1 SUCCESS: msg_id={msg_id} in {chat_id}", level=logging.INFO)
            session_data["menu_msg_id"] = msg_id
            session_data["menu_chat_id"] = chat_id
            session_data["sent_to"] = "current"
            await save_session(sid, session_data)
            return sid

        # TAHAP 2: Coba via Inline Mode di Log Group (Jika berbeda)
        if log_chat_id != chat_id:
            Altruix.log(f"[show_story_menu] TAHAP 2: Trying inline in log chat {log_chat_id}...", level=logging.DEBUG)
            msg_id = await try_inline_send(log_chat_id, bot_username)
            if msg_id:
                Altruix.log(f"[show_story_menu] TAHAP 2 SUCCESS: msg_id={msg_id} in {log_chat_id}", level=logging.INFO)
                session_data["menu_msg_id"] = msg_id
                session_data["menu_chat_id"] = log_chat_id
                session_data["sent_to"] = "log"
                await save_session(sid, session_data)
                return sid
        else:
            Altruix.log(f"[show_story_menu] TAHAP 2 SKIPPED: log_chat is same as current_chat.", level=logging.DEBUG)

    # TAHAP 3: FALLBACK - Direct send via bot assistant (ke Log Group)
    Altruix.log(f"[show_story_menu] TAHAP 3: Falling back to direct send in log chat {log_chat_id}...", level=logging.DEBUG)
    try:
        main_bot_me = await asyncio.wait_for(Altruix.bot.get_me(), timeout=10.0)
        main_bot_id = main_bot_me.id
        
        # Load builders from bot plugin for Tahap 3
        build_story_menu_text_bot, build_story_menu_kb_bot = get_builders()
        
        msg = None
        try:
            Altruix.log(f"[show_story_menu] TAHAP 3: Sending with target_bot...", level=logging.DEBUG)
            msg = await asyncio.wait_for(
                target_bot.send_message(
                    log_chat_id,
                    build_story_menu_text_bot(session_data),
                    reply_markup=build_story_menu_kb_bot(sid, session_data),
                    parse_mode=enums.ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_to_message_id=reply_to_id if log_chat_id == chat_id else None
                ),
                timeout=15.0
            )
        except Exception as e:
            Altruix.log(f"[show_story_menu] TAHAP 3 target_bot send failed: {repr(e)}", level=logging.DEBUG)
            if target_bot != Altruix.bot:
                Altruix.log(f"[show_story_menu] TAHAP 3: Trying main bot fallback...", level=logging.DEBUG)
                msg = await asyncio.wait_for(
                    Altruix.bot.send_message(
                        log_chat_id,
                        build_story_menu_text_bot(session_data),
                        reply_markup=build_story_menu_kb_bot(sid, session_data),
                        parse_mode=enums.ParseMode.HTML,
                        disable_web_page_preview=True,
                        reply_to_message_id=reply_to_id if log_chat_id == chat_id else None
                    ),
                    timeout=15.0
                )
            else:
                raise e
        
        if msg:
            Altruix.log(f"[show_story_menu] TAHAP 3 SUCCESS: msg_id={msg.id} in {log_chat_id}", level=logging.INFO)
            session_data["menu_msg_id"] = msg.id
            session_data["menu_chat_id"] = log_chat_id
            session_data["sent_to"] = "log"
            
            # ✅ RESTORE: Tentukan bot mana yang akhirnya mengirim pesan ini (simpan ID agar serializable)
            msg_from_id = getattr(msg.from_user, "id", 0) if hasattr(msg, "from_user") and msg.from_user else 0
            session_data["bot_id"] = msg_from_id
            
            await save_session(sid, session_data)
            return sid
    except Exception as e:
        Altruix.log(f"[show_story_menu] TAHAP 3 FATAL ERROR: {repr(e)}", level=logging.ERROR)
        if sid in _STORY_SESSIONS_CACHE:
             del _STORY_SESSIONS_CACHE[sid]
             _save_all_sessions(_STORY_SESSIONS_CACHE)
        return None

async def execute_story_download(session, story_ids_to_dl, resume=False):
    """
    Background task: download story-story yang dipilih user.
    Dipanggil via asyncio.create_task() dari callback handler agar tidak memblokir event loop.
    Mengupdate pesan bot dengan progress (Success/Failed counter) secara real-time.
    Menggunakan process_story() untuk setiap story dengan flood delay protection.
    """
    sid = session.get("_id", "unknown")
    Altruix.log(f"[execute_story_download] START: sid={sid}, count={len(story_ids_to_dl)}", level=logging.INFO)
    
    # Generate Task ID for Monitoring (.tasklist / .taskcancel)
    tid = generate_task_id("RES") if resume else generate_task_id("ST")
    
    # Initialize counters at function scope
    stories_count = 0
    failed_count = 0
    total = len(story_ids_to_dl)

    # Hydration check
    c = session.get("client")
    if not c:
        cid = session.get("client_id")
        c = next((cl for cl in Altruix.clients if cl.me and cl.me.id == cid), None)
        
    if not c:
        Altruix.log(f"[execute_story_download] FAILED: Userbot client not found for {sid}", level=logging.ERROR)
        return

    chat_id = session["chat_id"]
    target = session["target"]
    target_display = session["target_display"]
    target_id = session.get("target_id")
    target_name = session.get("target_name")
    
    # 🆕 Build a "Source Name Only" display for separated log style
    if target_name and target_id:
        target_name_esc = html.escape(target_name)
        # Using a generic tg:// link or reconstruct based on type if possible. 
        # For simplicity in logs, we use the name with the preserved session link if it's there,
        # but the userbot previously built target_display with name + (ID).
        # We can extract the name part by splitting at ' (' if it follows the pattern.
        source_name_only = target_display.split(" (<a")[0] if " (<a" in target_display else target_display
    else:
        source_name_only = target_display
    
    source_id_display = f"{target_id}" if target_id else "-"
    
    # [v1.0.612] Final stabilization: Only edit if sent via Direct/Log mode (Tahap 3)
    # Inline results (Tahap 1/2) cannot be reliably edited via chat/msg_id.
    # We will ONLY background-edit if was sent directly from a Bot to a Log Group.
    sent_to = session.get("sent_to", "current")
    bot_id = session.get("bot_id", 0)
    can_bg_edit = (sent_to == "log" and bot_id > 0)
    
    # 🆕 Define bot_client for reliable log group notifications
    bot_client = session.get("bot")
    if not bot_client:
        if bot_id and bot_id != (Altruix.bot.me.id if Altruix.bot and Altruix.bot.me else 0):
            bot_client = getattr(Altruix, "bot_manager", Altruix).get_bot(bot_id) if hasattr(Altruix, "bot_manager") else Altruix.bot
        else:
            bot_client = Altruix.bot

    # 🆕 Send start notification to Log Group (Requested by User)
    log_chat_id = getattr(Altruix, "log_chat", chat_id)
    progress_msg = None
    try:
        alb_text = " (Album Mode)" if session.get("send_as_album") else ""
        alb_status = "ON" if session.get("send_as_album") else "OFF"
        notif_text = (
            f"<blockquote expandable>"
            f"⏳ <b>Memulai Download Story{alb_text}...</b>\n"
            f"• Target: {source_name_only}\n"
            f"• Target ID: <code>{source_id_display}</code>\n"
            f"• Total Story: {total}\n"
            f"• Album: <b>{alb_status}</b>\n"
            f"• Task ID: <code>{tid}</code>\n"
            f"• Sistem: Background Task"
            f"</blockquote>"
        )
        progress_msg = await bot_client.send_message(log_chat_id, notif_text, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
        Altruix.log(f"[execute_story_download] {tid} | Sent start notification to {log_chat_id}", level=logging.DEBUG)
    except Exception as e:
        Altruix.log(f"Failed to send start notification to log group: {e}", level=logging.DEBUG)
    
    if can_bg_edit:
        # Direct Mode (Bot is the owner and can edit dashboard directly)
        edit_client = bot_client
        Altruix.log(f"[execute_story_download] {tid} | Using BOT client for UI edits (Direct Mode).", level=logging.DEBUG)
    else:
        # Inline Mode: We skip background edits to dashboard to avoid 403 INLINE_BOT_REQUIRED flood.
        # User will rely on the progress_msg in the log group instead.
        edit_client = None
        Altruix.log(f"[execute_story_download] {tid} | Skipping background dashboard edits (Inline Mode). Progress routed to log group.", level=logging.DEBUG)
    
    # Master execution block to handle cancellation and cleanup
    # [v1.0.613] Shared mutable state for background heartbeat
    _hb_state = {
        "stories_count": 0, "failed_count": 0, "total": total,
        "current_story": None, "current_p": 0, "active": True,
        "status_text": session.get("status_text", ""),
    }
    
    # [v1.0.617] Start timer for duration tracking
    start_time_val = time.time()
    
    # [v1.0.613] Background heartbeat: updates progress_msg every 10s so it doesn't look stuck
    async def _progress_heartbeat():
        """Periodically update progress_msg to show the download is still alive."""
        last_text = ""
        while _hb_state["active"]:
            await asyncio.sleep(10)
            if not _hb_state["active"] or not progress_msg:
                break
            try:
                sc = _hb_state["stories_count"]
                fc = _hb_state["failed_count"]
                cp = _hb_state["current_p"]
                tt = _hb_state["total"]
                cs = _hb_state["current_story"]
                st = _hb_state.get("status_text", "")
                alb_txt = " (Album)" if session.get("send_as_album") else ""
                alb_status = "ON" if session.get("send_as_album") else "OFF"
                
                # Calculate elapsed time
                elapsed = int(time.time() - start_time_val)
                mins, secs = divmod(elapsed, 60)
                hours, mins = divmod(mins, 60)
                duration_str = f"{hours:02d}:{mins:02d}:{secs:02d}" if hours > 0 else f"{mins:02d}:{secs:02d}"
                
                new_text = (
                    f"<blockquote expandable>"
                    f"🔄 <b>Download Story{alb_txt} In Progress...</b>\n"
                    f"• Target: {source_name_only}\n"
                    f"• Target ID: <code>{source_id_display}</code>\n"
                    f"• Progress: {cp}/{tt} (✅ {sc} | ❌ {fc})\n"
                    f"• Album: <b>{alb_status}</b>\n"
                    f"• Durasi: <code>{duration_str}</code>\n"
                    f"• Task ID: <code>{tid}</code>"
                    f"</blockquote>"
                )
                if st:
                    new_text += f"\n⚡ {st}"
                    
                if new_text != last_text:
                    await progress_msg.edit_text(new_text, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
                    last_text = new_text
            except BotMessageNotModified:
                pass
            except Exception:
                pass
    
    heartbeat_task = asyncio.create_task(_progress_heartbeat()) if progress_msg else None
    
    # [v1.0.618] Initialize placeholders for status reporting
    duration_str = "00:00"
    
    try:
        # [v1.0.618] Pull session specific settings early for persistence
        watermark = session.get("watermark", True)
        send_as_album = session.get("send_as_album", False)
        reply_to_id = session.get("reply_to_id")
        
        # [v1.0.616] Persistence: Store initial context for potential resume
        session_id = session.get("_id")
        if session_id:
            await save_session(session_id, update_dict={
                "status": "downloading",
                "chat_id": chat_id,
                "target": target,
                "target_display": target_display,
                "story_ids_to_dl": story_ids_to_dl,
                "watermark": watermark,
                "send_as_album": send_as_album,
                "reply_to_id": reply_to_id,
                "bot_id": bot_id,
                "task_id_saved": tid
            })

        # Register the task in global registry
        details = f"Target: {target} | Total: {len(story_ids_to_dl)}"
        if tid.startswith("#RES"):
            details = f"[RESUME] {details}"
        register_task(tid, asyncio.current_task(), "Story Downloader", "xstories", c.me.id, details)
        
        # Update menu only for Direct-mode sessions [Stop 403 Flood]
        if edit_client:
            try:
                from Main.plugins.bot.xstories_bot import build_story_menu_kb, build_story_menu_text
                text = build_story_menu_text(session)
                await edit_client.edit_message_text(
                    chat_id=session["menu_chat_id"],
                    message_id=session["menu_msg_id"],
                    text=text,
                    parse_mode=enums.ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=build_story_menu_kb(sid, session)
                )
            except Exception as e:
                Altruix.log(f"Story DL progress init edit error: {e}", level=logging.DEBUG)
        else:
            # Inline mode: Only log and update cache. User can manual 'Refresh'.
            Altruix.log(f"[execute_story_download] {tid} | Progress update via background edit SKIPPED for Inline Mode.", level=logging.DEBUG)
        
        # Use username if available for process_story
        story_target = target
        if isinstance(target, int):
            try:
                user = await asyncio.wait_for(c.get_users(target), timeout=15.0)
                if user.username:
                    story_target = user.username
            except Exception as e:
                Altruix.log(f"Username resolve error: {e}", level=logging.DEBUG)
        
        media_group = []
        files_to_clean = []
        
        # [v1.0.616] Work with a copy of the list to allow incremental updates to the original
        remaining_ids = list(story_ids_to_dl)
        
        for story_id in list(remaining_ids):
            try:
                current_p = stories_count + failed_count + 1
                sid_val = session.get("_id")
                
                # ✅ RE-FETCH FROM CACHE: Instant synchronization (Prevents toggle bouncing)
                # Re-reading from the shared memory cache ensures Userbot
                # always sees the FRESH toggle states (Album, Watermark, etc.) instantly.
                db_session = await get_session(sid_val) if sid_val else None
                if db_session:
                    # Updates toggles from cache for 100% UI visual consistency
                    watermark = db_session.get("watermark", watermark)
                    send_as_album = db_session.get("send_as_album", send_as_album)
                
                # Update status text
                prep_text = "Menyiapkan" if send_as_album else "Mendownload"
                session["status_text"] = f"{prep_text} #{story_id} ({current_p}/{total})...."
                if sid_val: await save_session(sid_val, update_dict={"status_text": session["status_text"]})
                Altruix.log(f"[execute_story_download] {tid} | {prep_text} story {story_id} ({current_p}/{total})...", level=logging.DEBUG)
                
                # [v1.0.613] Sync heartbeat state for background progress updates
                _hb_state.update({"current_p": current_p, "current_story": story_id, "status_text": session["status_text"], "stories_count": stories_count, "failed_count": failed_count})
                
                try:
                    # process_story handles retries and floodwaits internally
                    if send_as_album:
                        # return_media=True returns (InputMedia, file_path)
                        res = await asyncio.wait_for(
                            process_story(c, chat_id, story_target, story_id, None, watermark=watermark, session=session, reply_to_id=reply_to_id, return_media=True),
                            timeout=600.0  # [v1.0.619] Raised from 300s: process_story has multi-stage pipeline overhead
                        )
                        if res and isinstance(res, tuple) and res[0]:
                            media_group.append(res[0])
                            if res[1]: 
                                if isinstance(res[1], list): files_to_clean.extend(res[1])
                                else: files_to_clean.append(res[1])
                            success = True
                        else:
                            success = False
                            
                        # Send frequently (chunk = 5) to prevent FILE_REFERENCE_EXPIRED
                        if len(media_group) == 5:
                            try:
                                await c.send_media_group(chat_id, media_group, reply_to_message_id=reply_to_id)
                                stories_count += len(media_group)
                                # [v1.0.616] Persistence: Update remaining stories after successful chunk
                                for s_id in story_ids_to_dl[current_p-5:current_p]:
                                    if s_id in remaining_ids: 
                                        try: remaining_ids.remove(s_id)
                                        except: pass
                                if sid_val: await save_session(sid_val, update_dict={"story_ids_to_dl": list(remaining_ids)})
                            except Exception as album_e:
                                Altruix.log(f"Failed to send media group chunk: {album_e}", level=logging.ERROR)
                                # In case of album failure, we still remove them to avoid infinite loop on resume
                                for s_id in story_ids_to_dl[current_p-5:current_p]:
                                    if s_id in remaining_ids: 
                                        try: remaining_ids.remove(s_id)
                                        except: pass
                                if sid_val: await save_session(sid_val, update_dict={"story_ids_to_dl": list(remaining_ids)})
                            finally:
                                # Cleanup local files immediately after sending
                                for f in files_to_clean:
                                    if os.path.exists(f): 
                                        try: os.remove(f)
                                        except: pass
                                media_group = []
                                files_to_clean = []
                    else:
                        success = await asyncio.wait_for(
                            process_story(c, chat_id, story_target, story_id, None, watermark=watermark, session=session, reply_to_id=reply_to_id, raise_errors=True),
                            timeout=600.0  # [v1.0.619] Raised from 300s: process_story has multi-stage pipeline overhead
                        )
                except asyncio.TimeoutError:
                    Altruix.log(f"Story {story_id} TIMEOUT after 600s.", level=logging.WARNING)
                    success = False
                    dl_err_msg = "Waktu pemrosesan API habis (Timeout 600 detik)."
                    if story_id in remaining_ids: 
                        try: remaining_ids.remove(story_id)
                        except: pass
                    if sid_val: await save_session(sid_val, update_dict={"story_ids_to_dl": list(remaining_ids)})
                except Exception as dl_e:
                    Altruix.log(f"Story {story_id} FAILED: {repr(dl_e)}", level=logging.WARNING)
                    success = False
                    dl_err_msg = str(dl_e) or repr(dl_e)
                    if story_id in remaining_ids: 
                        try: remaining_ids.remove(story_id)
                        except: pass
                    if sid_val: await save_session(sid_val, update_dict={"story_ids_to_dl": list(remaining_ids)})
                
                if success:
                    stories_count += 1
                    Altruix.log(f"[execute_story_download] {tid} | Story {story_id} {'PREPPED' if send_as_album else 'SUCCESS'}.", level=logging.DEBUG)
                    if not send_as_album:
                        if story_id in remaining_ids:
                            try: remaining_ids.remove(story_id)
                            except: pass
                        if sid_val: await save_session(sid_val, update_dict={"story_ids_to_dl": list(remaining_ids)})
                else:
                    failed_count += 1
                    Altruix.log(f"[execute_story_download] {tid} | Story {story_id} FAILED.", level=logging.DEBUG)
                    if not send_as_album:
                        if story_id in remaining_ids:
                            try: remaining_ids.remove(story_id)
                            except: pass
                        if sid_val: await save_session(sid_val, update_dict={"story_ids_to_dl": list(remaining_ids)})
                    
                    # 🆕 NOTIFY BOT ASSISTANT ON SINGLE STORY FAILURE
                    if bot_client and log_chat_id and hasattr(bot_client, "send_message"):
                        try:
                            # Tunda sejenak agar tidak flood Telegram jika banyak yang error
                            await asyncio.sleep(0.5)
                            await bot_client.send_message(
                                log_chat_id,
                                f"❌ <b>Download Error (Story #{story_id})</b>\n"
                                f"• <b>User:</b> {target_display}\n"
                                f"• <b>Task ID:</b> <code>{tid}</code>\n"
                                f"• <b>Penyebab:</b>\n"
                                f"<code>{dl_err_msg}</code>",
                                parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True
                            )
                        except Exception as log_e:
                            Altruix.log(f"Failed to send failure log to group: {log_e}", level=logging.DEBUG)
                
                # [v1.0.613] Sync counters to heartbeat after each story completes
                _hb_state.update({"stories_count": stories_count, "failed_count": failed_count})
                
                # Update progress with correct client/keyboard to avoid 403 & bouncing
                if edit_client:
                    try:
                        from Main.plugins.bot.xstories_bot import build_story_menu_kb, build_story_menu_text
                        # Use central text builder during progress to keep naming and links consistent
                        text = build_story_menu_text(db_session or session)
                        await edit_client.edit_message_text(
                            chat_id=session["menu_chat_id"],
                            message_id=session["menu_msg_id"],
                            text=text,
                            parse_mode=enums.ParseMode.HTML,
                            disable_web_page_preview=True,
                            reply_markup=build_story_menu_kb(sid_val, db_session or session)
                        )
                    except BotMessageNotModified:
                        pass
                    except Exception as e:
                        Altruix.log(f"Story DL progress edit error: {e}", level=logging.DEBUG)
                
                # 🆕 Always update the standalone progress notification in Log Group
                if progress_msg:
                    try:
                        alb_txt = " (Menyiapkan Album)" if send_as_album else ""
                        await progress_msg.edit_text(
                            f"🔄 <b>Progres Download Story{alb_txt}</b>\n"
                            f"• Target: {target_display}\n"
                            f"• Progress: {current_p}/{total} (Sukses: {stories_count}, Gagal: {failed_count})",
                            parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True
                        )
                    except: pass
                
                if not send_as_album:
                    await asyncio.sleep(FLOOD_PROTECTION_DELAY)
                    
            except FloodWait as e:
                await asyncio.sleep(e.value)
        
        # Send remaining items in media group
        if send_as_album and media_group:
            try:
                await c.send_media_group(chat_id, media_group, reply_to_message_id=reply_to_id)
            except Exception as album_e:
                Altruix.log(f"Failed to send final media group: {album_e}", level=logging.ERROR)
            finally:
                for f in files_to_clean:
                    if os.path.exists(f): 
                        try: os.remove(f)
                        except: pass
        
        # Final Update
        try:
            alb_status = " (Album Mode)" if send_as_album else ""
            # Calculate final duration
            elapsed = int(time.time() - start_time_val)
            mins, secs = divmod(elapsed, 60)
            hours, mins = divmod(mins, 60)
            duration_str = f"{hours:02d}:{mins:02d}:{secs:02d}" if hours > 0 else f"{mins:02d}:{secs:02d}"
            
            final_text_html = (
                f"<blockquote expandable>\n"
                f"<b>✅ Story Downloader {alb_status} Selesai!</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"• <b>Target:</b> {source_name_only}\n"
                f"• <b>Target ID:</b> <code>{source_id_display}</code>\n"
                f"• <b>Task ID:</b> <code>{tid}</code>\n"
                f"• <b>Durasi:</b> <code>{duration_str}</code>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"📊 <b>Hasil:</b>\n"
                f"✅ Sukses: {stories_count}\n"
                f"❌ Gagal: {failed_count}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"<i>Sistem kembali ke status idle.</i>\n"
                f"</blockquote>"
            )
            
            # Final update Dashboard
            if can_bg_edit:
                await edit_client.edit_message_text(
                    chat_id=session["menu_chat_id"],
                    message_id=session["menu_msg_id"],
                    text=final_text_html,
                    parse_mode=enums.ParseMode.HTML,
                )
            
            # Final update Log Group standalone message
            if progress_msg:
                await progress_msg.edit_text(final_text_html, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
        except Exception:
            pass
            
        session["status"] = "idle"
        session["status_text"] = None
        await save_session(session["_id"], update_dict={"status": "idle", "status_text": None})
    except asyncio.CancelledError:
        Altruix.log(f"[execute_story_download] Task {tid} was CANCELLED by user.", level=logging.WARNING)
        try:
            # Calculate duration at cancellation
            elapsed = int(time.time() - start_time_val)
            mins, secs = divmod(elapsed, 60)
            hours, mins = divmod(mins, 60)
            duration_str = f"{hours:02d}:{mins:02d}:{secs:02d}" if hours > 0 else f"{mins:02d}:{secs:02d}"
            
            cancel_html = (
                f"<blockquote expandable>\n"
                f"🛑 <b>Task Cancelled</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"Task ID: <code>{tid}</code>\n"
                f"Status: Download dihentikan paksa.\n"
                f"Durasi: <code>{duration_str}</code>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"</blockquote>"
            )
            
            # Cancellation update Dashboard
            if can_bg_edit:
                await edit_client.edit_message_text(
                    chat_id=session["menu_chat_id"],
                    message_id=session["menu_msg_id"],
                    text=cancel_html,
                    parse_mode=enums.ParseMode.HTML,
                )
                
            # Cancellation update standalone Log message
            if progress_msg:
                await progress_msg.edit_text(cancel_html, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
        except Exception:
            pass
        raise

    except Exception as e:
        Altruix.log(f"[execute_story_download] FATAL ERROR: {repr(e)}", level=logging.ERROR)
        traceback.print_exc()
    finally:
        # [v1.0.613] Stop heartbeat background task
        _hb_state["active"] = False
        if heartbeat_task and not heartbeat_task.done():
            heartbeat_task.cancel()
        unregister_task(tid)
        sid_final = session.get("_id")
        if sid_final:
            await save_session(sid_final, update_dict={"status": "idle", "busy_until": 0, "status_text": None})
    session["status_text"] = f"Done! {stories_count} success, {failed_count} failed."
    if sid: await save_session(sid, update_dict={"status_text": session["status_text"]})
    # Final formatted text for direct/inline fallback
    final_text = (
        f"<blockquote expandable>"
        f"<b>📖 Story Download Complete</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"• <b>Target:</b> {source_name_only}\n"
        f"• <b>Target ID:</b> <code>{source_id_display}</code>\n"
        f"• <b>Durasi:</b> <code>{duration_str}</code>\n"
        f"• <b>Success:</b> {stories_count}\n"
        f"• <b>Failed:</b> {failed_count}\n"
        f"━━━━━━━━━━━━━━━━━━"
        f"</blockquote>"
    )
    
    try:
        if edit_client:
            await edit_client.edit_message_text(
                chat_id=session["menu_chat_id"],
                message_id=session["menu_msg_id"],
                text=final_text,
                reply_markup=None, # Only remove keyboard at the very end
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True,
            )
        else:
            # Inline Mode notification: Send new msg since we can't background-edit
            await c.send_message(chat_id, final_text, parse_mode=enums.ParseMode.HTML)
    except Exception as e:
        Altruix.log(f"Story DL final result reporting error: {e}", level=logging.DEBUG)

# Bot Handlers registration is now managed via xstories_bot.py
# and triggered via register_story_bot_handlers(target_bot) in show_story_menu.
# This ensures cross-plugin compatibility and correct loading by the Bot Assistant.

def register_story_bot_handlers(bot_client):
    """
    Proxy function to call registration in the bot plugin.
    This ensures that custom bots also get the handlers when they are needed.
    """
    from Main.plugins.bot.xstories_bot import register_story_bot_handlers as bot_reg
    return bot_reg(bot_client)

# ============================================================================
# CMD: .rstories — Menu interaktif Story Picker (reply ke pesan user)
# Flow: Detect replied user → discover_stories() → show_story_menu()
# ============================================================================

@Altruix.register_on_cmd(
    ["rstories"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Interactively download stories from the replied user.",
        "description": (
            "Cara tercepat untuk mendownload story seseorang tanpa perlu mengetik username mereka.\n\n"
            "<b>Langkah-langkah:</b>\n"
            "1. Cari pesan dari target di grup atau chat mana saja.\n"
            "2. <b>Reply</b> (balas) pesan tersebut dengan mengetik <code>.rstories</code>.\n"
            "3. Dashboard interaktif akan muncul membawa daftar story orang tersebut.\n\n"
            "<b>Detail:</b>\n"
            "• Bot otomatis mendeteksi User ID dari pengirim pesan yang Anda balas.\n"
            "• Klik link nama di dashboard untuk memverifikasi profil target."
        ),
        "usage": ".rstories (reply to user message)",
        "example": "Balas pesan target -> .rstories",
    },
)
@log_errors
async def reply_stories_cmd(c: Client, m: Message):
    """Interactive story download from the replied user."""
    rm = m.reply_to_message
    if not rm or not rm.from_user:
        return await m.handle_message(
            "❌ <b>Reply Required!</b>\n\n"
            "<i>Reply to user message that you want to download stories from.</i>\n\n"
            "<b>Example:</b>\n"
            "• Reply message → <code>.rstories</code>"
        )

    target_user = rm.from_user
    target = target_user.id
    target_display = f'<a href="tg://user?id={target_user.id}">{html.escape(target_user.first_name)}</a> (<code>{target_user.id}</code>)'

    status_msg = await m.handle_message(f"🔍 <b>Searching for active stories from {target_display}...</b>")

    try:
        story_data = await discover_stories(c, target)
        
        if not story_data:
            return await safe_edit(
                status_msg,
                f"❌ <b>No active stories found for {target_display}.</b>\n\n"
                f"Tips: Make sure the user has active stories that you can see."
            )
        
        # Show interactive menu in current chat (fallback to log hidden in show_story_menu)
        # [v1.0.615] Pass raw target info for perfect link rendering
        sid = await show_story_menu(
            c, m.chat.id, target_user.username or target, target_display, story_data, 
            reply_to_id=m.id, target_id=target_user.id, target_name=target_user.first_name
        )
        
        if sid:
            session = await get_session(sid)
            sent_to_log = (session.get("sent_to") == "log") if session else False
            target_cid = session.get("menu_chat_id", m.chat.id) if session else m.chat.id
            
            msg_link = ""
            if session and session.get("menu_msg_id") and str(target_cid).startswith("-100"):
                msg_link = f"https://t.me/c/{str(target_cid).replace("-100", "").lstrip("-")}/{session['menu_msg_id']}"
            
            if sent_to_log:
                success_text = "✅ <b>Story Picker Menu sent to Log Group!</b>\n\n<i>Check your Log Group to choose a story.</i>"
            else:
                success_text = "✅ <b>Story Picker Menu successfully sent!</b>"
                
            if msg_link:
                success_text += f'\n👉 <b><a href="{msg_link}">Open Dashboard Menu</a></b>'
                
            await safe_edit(status_msg, success_text)
            # Auto-delete notification after 3 seconds to keep chat clean
            await asyncio.sleep(3)
            try: await status_msg.delete()
            except: pass
        else:
            await safe_edit(status_msg, "❌ <b>Failed to send interactive menu to this chat or Log Group.</b>")
            
        # Delete the trigger command
        await m.delete_if_self()

    except Exception as e:
        await safe_edit(status_msg, f"❌ <b>Error:</b> <code>{str(e)}</code>")


# ============================================================================
# CMD: .rlinkstories — Menu interaktif Story Picker via message link
# Flow: Parse link → get_messages() → detect sender → discover_stories() → show_story_menu()
# ============================================================================

@Altruix.register_on_cmd(
    ["rlinkstories"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Interactively download stories from a user by message link.",
        "description": (
            "Gunakan link pesan (message link) untuk mendapatkan dashboard story dari pengirim pesan tersebut.\n"
            "Sangat berguna jika Anda menemukan link pesan menarik dari grup lain.\n\n"
            "<b>Contoh Link:</b>\n"
            "• <code>https://t.me/c/145678/123</code> (Link Private)\n"
            "• <code>https://t.me/username/456</code> (Link Publik)\n\n"
            "<b>Alur Kerja:</b>\n"
            "1. Masukkan link pesan setelah perintah <code>.rlinkstories</code>.\n"
            "2. Bot akan 'mengintip' siapa pengirimnya dan mencari story aktif mereka.\n"
            "3. Dashboard story picker akan muncul untuk Anda gunakan."
        ),
        "usage": ".rlinkstories [link_pesan]",
        "example": ".rlinkstories https://t.me/durov/1234\n.rlinkstories https://t.me/c/1234567890/42",
    },
)
@log_errors
async def link_stories_cmd(c: Client, m: Message):
    """Interactive story download from a message link sender."""
    input_ = m.user_input or m.raw_user_input
    if not input_:
        return await m.handle_message(
            "❌ <b>Please provide a message link!</b>\n\n"
            "<b>How to use:</b>\n"
            "<code>.rlinkstories https://t.me/c/CHAT_ID/MSG_ID</code>\n"
            "<code>.rlinkstories https://t.me/username/MSG_ID</code>\n\n"
            "<b>The system will:</b>\n"
            "1. Mengambil pesan dari link.\n"
            "2. Mendeteksi pengirimnya.\n"
            "3. Menampilkan menu story interaktif."
        )

    link = input_.split()[0]
    status_msg = await m.handle_message("🔄 <b>Processing message link...</b>")

    try:
        if "t.me/" not in link:
            return await safe_edit(status_msg, "❌ <b>Invalid message link format!</b> Use Telegram message link.")

        parts = link.rstrip("/").split("/")

        if "t.me/c/" in link:
            try:
                chat_id = int(f"-100{parts[-2]}")
                msg_id = int(parts[-1])
            except (ValueError, IndexError):
                return await safe_edit(status_msg, "❌ <b>Failed to parse message link private group.</b>")
        else:
            try:
                chat_identifier = parts[-2]
                msg_id = int(parts[-1])
                try:
                    chat = await c.get_chat(chat_identifier)
                    chat_id = chat.id
                except Exception as e:
                    return await safe_edit(status_msg, f"❌ <b>Failed to resolve chat:</b> <code>{chat_identifier}</code>\n<code>{e}</code>")
            except (ValueError, IndexError):
                return await safe_edit(status_msg, "❌ <b>Failed to parse message link.</b>")

        await safe_edit(status_msg, f"🔍 <b>Retrieving messages from chat <code>{chat_id}</code>...</b>")

        try:
            messages = await c.get_messages(chat_id, msg_id)
            if not messages:
                return await safe_edit(status_msg, "❌ <b>Message not found.</b>")
            
            msg = messages if not isinstance(messages, list) else messages[0]

            if not msg.from_user:
                return await safe_edit(
                    status_msg,
                    "❌ <b>This message has no identified sender.</b>\n\n"
                    "<i>Possibly an anonymous channel or a deleted message.</i>"
                )

            target_user = msg.from_user

        except Exception as e:
            return await safe_edit(status_msg, f"❌ <b>Failed to retrieve message:</b>\n<code>{str(e)}</code>")

        target = target_user.id
        target_display = f'<a href="tg://user?id={target_user.id}">{html.escape(target_user.first_name)}</a> (<code>{target_user.id}</code>)'

        await safe_edit(status_msg, f"🔍 <b>User detected: {target_display}</b>\n<b>Searching for active stories...</b>")

        story_data = await discover_stories(c, target)

        if not story_data:
            return await safe_edit(
                status_msg,
                f"❌ <b>No active stories found for {target_display}.</b>\n\n"
                f"Tips: Make sure the user has active stories that you can view."
            )

        # Show interactive menu in current chat (fallback to log hidden in show_story_menu)
        # [v1.0.615] Pass raw target info for perfect link rendering
        sid = await show_story_menu(
            c, m.chat.id, target_user.username or target, target_display, story_data, 
            reply_to_id=m.id, target_id=target_user.id, target_name=target_user.first_name
        )
        
        if sid:
            session = await get_session(sid)
            sent_to_log = (session.get("sent_to") == "log") if session else False
            target_cid = session.get("menu_chat_id", m.chat.id) if session else m.chat.id
            
            msg_link = ""
            if session and session.get("menu_msg_id") and str(target_cid).startswith("-100"):
                msg_link = f"https://t.me/c/{str(target_cid).replace("-100", "").lstrip("-")}/{session['menu_msg_id']}"
            
            if sent_to_log:
                success_text = "✅ <b>Story Picker Menu sent to Log Group!</b>\n\n<i>Check your Log Group to choose a story.</i>"
            else:
                success_text = "✅ <b>Menu Story Picker successfully sent!</b>"
                
            if msg_link:
                success_text += f'\n👉 <b><a href="{msg_link}">Open Dashboard Menu</a></b>'
                
            await safe_edit(status_msg, success_text)
            # Auto-delete notification after 3 seconds to keep chat clean
            await asyncio.sleep(3)
            try: await status_msg.delete()
            except: pass
        else:
            await safe_edit(status_msg, "❌ <b>Failed to send interactive menu to this chat or Log Group.</b>")
            
        # Delete the trigger command
        await m.delete_if_self()

    except Exception as e:
        await safe_edit(status_msg, f"❌ <b>Error:</b> <code>{str(e)}</code>")


# ============================================================================
# STARTUP RECOVERY LOGIC
# [v1.0.616] Auto-resumes unfinished story downloads after restart.
# ============================================================================

async def recover_story_tasks():
    """
    Scans for unfinished download sessions and restarts them.
    Called at plugin initialization via a delayed background task.
    """
    Altruix.log("📖 [Recovery] Scanning for unfinished Story downloads...", level=logging.INFO)
    sessions = _load_all_sessions()
    recovered_count = 0
    
    # Wait for clients to be ready (Altruix.clients are populated during startup)
    retries = 0
    while not Altruix.clients and retries < 10:
        await asyncio.sleep(5)
        retries += 1
        
    if not Altruix.clients:
        Altruix.log("📖 [Recovery] FAILED: No active userbot sessions found. Skipping recovery.", level=logging.WARNING)
        return

    for sid, session in list(sessions.items()):
        if session.get("status") == "downloading":
            try:
                remaining_ids = session.get("story_ids_to_dl", [])
                if not remaining_ids:
                    # Mark as clean if nothing left
                    session["status"] = "done"
                    session["status_text"] = "Selesai (Auto-Recovered)"
                    sessions[sid] = session
                    continue
                
                cid = session.get("client_id")
                client = next((cl for cl in Altruix.clients if cl.me and cl.me.id == cid), Altruix.clients[0])
                
                # Restart the background task
                Altruix.log(f"📖 [Recovery] Resuming Story download for session {sid} ({len(remaining_ids)} stories)...", level=logging.INFO)
                
                # Hydrate session for executor
                full_session = session.copy()
                full_session["_id"] = sid
                full_session["client"] = client
                
                # Re-hydrate Bot
                bid = session.get("bot_id")
                if bid:
                    if bid == (Altruix.bot.me.id if Altruix.bot and Altruix.bot.me else 0):
                        full_session["bot"] = Altruix.bot
                    else:
                        full_session["bot"] = Altruix.bot_manager.get_bot(bid) if hasattr(Altruix, "bot_manager") else Altruix.bot
                else:
                    full_session["bot"] = Altruix.bot
                
                # Run the task with a Resume prefix for tracking
                asyncio.create_task(
                    execute_story_download(full_session, remaining_ids, resume=True)
                )
                recovered_count += 1
            except Exception as e:
                Altruix.log(f"📖 [Recovery] Failed to resume session {sid}: {e}", level=logging.ERROR)

    if recovered_count > 0:
        # Save any cleaned statuses
        _save_all_sessions(sessions)
        Altruix.log(f"📖 [Recovery] Successfully resumed {recovered_count} story download tasks.", level=logging.INFO)
    else:
        Altruix.log("📖 [Recovery] No tasks needed recovery.", level=logging.DEBUG)

# Helper to automatically trigger recovery on startup
async def _startup_hook():
    """Waits for Altruix to be fully initialized before triggering recovery."""
    try:
        # Delay to ensure bot assistant and userbots are connected
        await asyncio.sleep(15)
        await recover_story_tasks()
    except Exception as e:
        Altruix.log(f"XStories Startup Hook Error: {e}", level=logging.ERROR)

# Schedule recovery task immediately upon module load
asyncio.create_task(_startup_hook())

# Add help info
Altruix._command_help_message_data["xstories"] = (
    "<b>✨ Story Downloader (Smart Bypass v4 + Advanced Engine)</b>\n\n"
    "Plugin ini adalah solusi lengkap untuk mengunduh story Telegram dari <b>User, Group, maupun Channel</b> secara aman dan interaktif.\n\n"
    "<b>📚 Panduan Perintah:</b>\n"
    "• <code>!dlstory [link]</code>\n"
    "  Download story spesifik via link (Publik & Private).\n"
    "• <code>!stories [username/ID]</code>\n"
    "  Open dashboard via Username atau Chat ID.\n"
    "  Ex: <code>.stories @durov</code> atau <code>.stories -100123456</code>\n"
    "• <code>!rstories</code> (reply ke pesan)\n"
    "  Buka dashboard dari pengirim pesan yang di-reply.\n"
    "• <code>!rlinkstories [link_pesan]</code>\n"
    "  Buka dashboard dari pengirim pesan via link pesan.\n\n"
    "<b>🛠 Fungsi Tombol Dashboard:</b>\n"
    "• <b>[#1. 🎬 #ID]:</b> Klik nomor story untuk memilih/membatalkan.\n"
    "• <b>Refresh:</b> Scan ulang story terbaru dari target.\n"
    "• <b>Reset Status:</b> Paksa reset jika dashboard terasa stuck atau busy.\n"
    "• <b>Select/Deselect All:</b> Pilih semua story dalam satu klik.\n"
    "• <b>Watermark Toggle:</b> Sertakan link & ID sumber di caption media.\n"
    "• <b>Download Selected:</b> Ambil story yang sudah dicentang (Anti-Flood).\n"
    "• <b>Download All:</b> Ambil semua story target sekaligus.\n"
    "• <b>Cancel:</b> Tutup menu secara aman."
)
