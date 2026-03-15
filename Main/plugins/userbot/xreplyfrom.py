from pyrogram import Client, filters
from Main import Altruix
from Main.core.decorators import iuser_check, log_errors
from Main.core.types.message import Message as RawMessage
import time
import asyncio

# Plugin Metadata
def _get_plugin_name():
    import os
    return os.path.basename(__file__)

plugin_name = _get_plugin_name()
__plugin_name__ = "xreplyfrom"
PLUGIN_VERSION = "0.0.197"

# Database Helpers
async def get_rf_logging_setting(user_id: int):
    """Get RF auto-logging setting for user (default: True)."""
    try:
        col = Altruix.db.make_collection("rf_settings")
        doc = await col.find_one({"_id": user_id})
        return doc.get("logging", True) if doc else True
    except Exception:
        return True

async def set_rf_logging_setting(user_id: int, value: bool):
    """Set RF auto-logging setting for user."""
    try:
        col = Altruix.db.make_collection("rf_settings")
        await col.update_one({"_id": user_id}, {"$set": {"logging": value}}, upsert=True)
        return True
    except Exception:
        return False

def clean_premium_caption(caption, entities, is_premium_session):
    """Remove premium emojis from entities if session is not premium."""
    if is_premium_session or not entities:
        return caption, entities
    from pyrogram import enums
    new_entities = [e for e in entities if e.type != enums.MessageEntityType.CUSTOM_EMOJI]
    return caption, new_entities

PROGRESS_STAGES = [
    (20,  "⏳ <b>Downloading media... please wait. (20s)</b>"),
    (40,  "⏳ <b>Still downloading... this may take a moment. (40s)</b>"),
    (60,  "⏳ <b>The media is quite large, processing in background... (60s)</b>"),
    (80,  "⏳ <b>Hang on, still working on it... (80s)</b>"),
    (100, "⏳ <b>Large file detected, download in progress... (100s)</b>"),
    (120, "⏳ <b>Still processing... large media takes time to bypass securely. (120s)</b>"),
    (140, "⏳ <b>Almost halfway through the download... please be patient. (140s)</b>"),
    (160, "⏳ <b>The server is responding slowly, still downloading... (160s)</b>"),
    (180, "⏳ <b>3 minutes in... this is a very large file. Hang tight! (180s)</b>"),
    (200, "⏳ <b>Download is progressing steadily, please wait... (200s)</b>"),
    (220, "⏳ <b>Still going strong... almost there! (220s)</b>"),
    (240, "⏳ <b>4 minutes elapsed... wrapping up the download soon. (240s)</b>"),
    (260, "⏳ <b>Final stretch... the file is nearly fully downloaded. (260s)</b>"),
    (280, "⏳ <b>Just a little more... preparing to send the media. (280s)</b>"),
    (300, "⏳ <b>Download finishing up... thank you for your patience! (300s)</b>"),
]

def create_progress_task(status_msg):
    """Creates an independent asyncio task for progress notifications."""
    async def _notifier():
        if not status_msg:
            return
        stage = 0
        start = time.time()
        while stage < len(PROGRESS_STAGES):
            await asyncio.sleep(10)
            elapsed = time.time() - start
            while stage < len(PROGRESS_STAGES) and elapsed > PROGRESS_STAGES[stage][0]:
                try:
                    await status_msg.edit(PROGRESS_STAGES[stage][1])
                except:
                    pass
                stage += 1
    return asyncio.create_task(_notifier())

@Altruix.register_on_cmd(
    cmd=["replyfrom", "replyfromcap", "replyfromcustom", "replyfromcust"],
    cmd_help={
        "categories": ["Utility"],
        "help": "Balas pesan dari chat/ID pesan lain (Teks/Media) dengan proxy/format aesthetic.",
        "description": "Balas pesan target menggunakan konten (Text/Media) dari chat atau ID pesan lain (Mendukung link).\n\n"
                       "**Perbedaan CMD:**\n"
                       "• `.replyfrom` : Mengambil media TANPA caption asli.\n"
                       "• `.replyfromcap` : Mengambil media DENGAN caption asli.\n"
                       "• `.replyfromcustom` : Mengambil media dengan CUSTOM caption.",
        "usage": ".replyfrom <link>\n"
                 ".replyfromcap <link>\n"
                 ".replyfromcustom <link> | <custom_caption>",
        "example": ".replyfrom https://t.me/username/123\n"
                   ".replyfromcap https://t.me/username/123\n"
                   ".replyfromcust https://t.me/username/123 | Ini caption kustom aesthetic!",
        "note": "✨ Auto-logs to Log Group. Bypass method supports thumbnails. Caption otomatis menggunakan format <blockquote expandable>."
    },
    requires_input=True,
    bot_mode_unsupported=True
)
@iuser_check
@log_errors
async def reply_from_handler(client: Client, message: RawMessage):
    """
    Fetch content from another message and reply to the target message.
    Supports no caption, default caption, and custom caption formatting.
    """
    if not client or not client.me or client.me.is_bot:
        return
    import re
    from pyrogram import enums
    import os
    
    cmd_name = message.command[0].lower() if message.command else "replyfrom"
    
    mode_cap = "none"
    if cmd_name == "replyfromcap":
        mode_cap = "default"
    elif cmd_name in ["replyfromcustom", "replyfromcust"]:
        mode_cap = "custom"
        
    custom_text = ""
    raw_text = message.text or ""
    cmd_len = len(message.command[0]) + 1 if message.command else 10
    args_text = raw_text[cmd_len:].strip()
    
    if mode_cap == "custom":
        if "|" in args_text:
            split_parts = args_text.split("|", 1)
            args_text = split_parts[0].strip()
            custom_text = split_parts[1].strip()
            if custom_text:
                custom_text = f"<blockquote expandable>{custom_text}</blockquote>"
        else:
            await message.edit("❌ <b>Usage:</b> <code>.replyfromcustom &lt;link&gt; | &lt;teks caption kustom&gt;</code>")
            return

    target_chat = None
    message_id = None
    
    # 1. Parse Link
    link_pattern = r"(?:https?://)?(?:t\.me/|telegram\.me/)(?:c/)?([\w.-]+)/(?:(\d+)/)?(\d+)"
    match = re.search(link_pattern, args_text)
    
    if match:
        chat_val = match.group(1)
        msg_id_val = match.group(3)
        if "/c/" in args_text or "t.me/c/" in args_text:
            target_chat = int(f"-100{chat_val}")
        else:
            target_chat = f"@{chat_val}" if not chat_val.startswith("@") else chat_val
        message_id = int(msg_id_val)
    else:
        # 2. Parse Space Separated
        parts = args_text.split()
        if len(parts) >= 2:
            input_chat = parts[0]
            msg_id_str = parts[1]
            if parts[0].lower() == "m" and len(parts) >= 3:
                input_chat = parts[1]
                msg_id_str = parts[2]
                
            if input_chat.startswith("-100") or input_chat.isdigit():
                target_chat = int(input_chat)
            else:
                target_chat = input_chat
                if not target_chat.startswith("@") and not target_chat.startswith("-"):
                    target_chat = f"@{target_chat}"
            try:
                message_id = int(msg_id_str)
            except ValueError:
                await message.edit("❌ <b>Error:</b> Invalid Message ID format.")
                return
        else:
            await message.edit(
                "❌ <b>Usage:</b>\n"
                "<code>.replyfrom &lt;link&gt;</code>\n"
                "<code>.replyfromcap &lt;link&gt;</code>\n"
                "<code>.replyfromcustom &lt;link&gt; | &lt;caption&gt;</code>"
            )
            return

    if not message.reply_to_message:
        await message.edit("❌ <b>Error:</b> Gunakan command ini sebagai balasan (reply) ke pesan target.")
        return

    status_msg = await message.edit(f"🔍 <b>Fetching:</b> <code>{target_chat}/{message_id}</code>...")

    try:
        source_msg = await client.get_messages(target_chat, message_id)
        if not source_msg or source_msg.empty:
            await status_msg.edit("❌ <b>Error:</b> Source message not found or is empty.")
            return

        # Auto Forward to Log Group
        uid = message.from_user.id
        logging_on = await get_rf_logging_setting(uid)
        
        if logging_on and Altruix.log_chat:
            await asyncio.sleep(1.0)
            try:
                try:
                    await source_msg.copy(Altruix.log_chat)
                except Exception as log_e:
                    if "CHAT_FORWARDS_RESTRICTED" not in str(log_e):
                        await source_msg.forward(Altruix.log_chat)
            except Exception as e:
                Altruix.log(f"RF Auto-forward failed: {e}")

        # Format Aesthetics (Blockquote)
        final_caption = ""
        final_text = ""
        
        if mode_cap == "custom":
            final_caption = custom_text
            final_text = custom_text
        elif mode_cap == "none":
            final_caption = ""
            if source_msg.text:
                try:
                    final_text = f"<blockquote expandable>{source_msg.text.html}</blockquote>"
                except Exception:
                    final_text = f"<blockquote expandable>{source_msg.text}</blockquote>"
        elif mode_cap == "default":
            if source_msg.media and source_msg.caption:
                try:
                    final_caption = f"<blockquote expandable>{source_msg.caption.html}</blockquote>"
                except Exception:
                    final_caption = f"<blockquote expandable>{source_msg.caption}</blockquote>"
            if source_msg.text:
                try:
                    final_text = f"<blockquote expandable>{source_msg.text.html}</blockquote>"
                except Exception:
                    final_text = f"<blockquote expandable>{source_msg.text}</blockquote>"

        reply_id = message.reply_to_message.id

        # If it's pure text, we can't use .copy() if we want to change its formatting to blockquote.
        # So we MUST send as new message.
        if source_msg.text:
            await client.send_message(
                message.chat.id, 
                final_text, 
                reply_to_message_id=reply_id,
                parse_mode=enums.ParseMode.HTML
            )
            await status_msg.delete()
            return

        # Attempt Method 1: standard Copy (Bypass Forward Restriction)
        try:
            kwargs = {
                "caption": final_caption,
                "parse_mode": enums.ParseMode.HTML
            }
                
            await source_msg.copy(
                chat_id=message.chat.id,
                reply_to_message_id=reply_id,
                **kwargs
            )
            await status_msg.delete()
            return
        except Exception as copy_e:
            error_msg = str(copy_e)
            is_restricted = "CHAT_FORWARDS_RESTRICTED" in error_msg
            status_text = "🧨 <b>Copy restricted (Protected).</b> Attempting robust bypass..." if is_restricted else f"⚠️ <b>Copy failed:</b> {error_msg[:50]}... Attempting bypass..."
            try:
                await status_msg.edit(status_text)
            except Exception:
                pass

        # Attempt Method 2: Download & Upload Bypass (with Thumbnail fix)
        if source_msg.media:
            progress_task = create_progress_task(status_msg)
            temp_path = await client.download_media(source_msg)
            progress_task.cancel()
            if not temp_path:
                await status_msg.edit("❌ <b>Bypass Failed:</b> Could not download restricted media.")
                return

            thumb_path = None
            try:
                if source_msg.video and getattr(source_msg.video, "thumbs", None):
                    thumb_path = await client.download_media(source_msg.video.thumbs[0].file_id)
                elif source_msg.document and getattr(source_msg.document, "thumbs", None):
                    thumb_path = await client.download_media(source_msg.document.thumbs[0].file_id)
            except Exception:
                pass

            # Extract video metadata
            v_duration = getattr(source_msg.video, "duration", 0) if source_msg.video else 0
            v_width = getattr(source_msg.video, "width", 0) if source_msg.video else 0
            v_height = getattr(source_msg.video, "height", 0) if source_msg.video else 0

            try:
                # Identify media type and send accordingly with thumbnails
                if source_msg.photo:
                    await client.send_photo(message.chat.id, temp_path, caption=final_caption, reply_to_message_id=reply_id, parse_mode=enums.ParseMode.HTML)
                elif source_msg.video:
                    await client.send_video(message.chat.id, temp_path, caption=final_caption, reply_to_message_id=reply_id, parse_mode=enums.ParseMode.HTML, thumb=thumb_path, duration=v_duration, width=v_width, height=v_height, supports_streaming=True)
                elif source_msg.audio:
                    await client.send_audio(message.chat.id, temp_path, caption=final_caption, reply_to_message_id=reply_id, parse_mode=enums.ParseMode.HTML, thumb=thumb_path)
                elif source_msg.voice:
                    await client.send_voice(message.chat.id, temp_path, caption=final_caption, reply_to_message_id=reply_id, parse_mode=enums.ParseMode.HTML)
                elif source_msg.document:
                    await client.send_document(message.chat.id, temp_path, caption=final_caption, reply_to_message_id=reply_id, parse_mode=enums.ParseMode.HTML, thumb=thumb_path)
                elif source_msg.animation:
                    await client.send_animation(message.chat.id, temp_path, caption=final_caption, reply_to_message_id=reply_id, parse_mode=enums.ParseMode.HTML, thumb=thumb_path)
                elif source_msg.video_note:
                    await client.send_video_note(message.chat.id, temp_path, reply_to_message_id=reply_id, thumb=thumb_path)
                elif source_msg.sticker:
                    await client.send_sticker(message.chat.id, temp_path, reply_to_message_id=reply_id)
                elif source_msg.media == enums.MessageMediaType.PHOTO:
                    await client.send_photo(message.chat.id, temp_path, caption=final_caption, reply_to_message_id=reply_id, parse_mode=enums.ParseMode.HTML)
                
                # ROBUST BACKUP Log
                if logging_on and Altruix.log_chat:
                    try:
                        caption_log = f"📥 <b>Restricted Content Log</b>\nSource: <code>{target_chat}</code>\nTask ID: <code>{message.id}</code>"
                        if source_msg.photo:
                            await client.send_photo(Altruix.log_chat, temp_path, caption=caption_log)
                        elif source_msg.video:
                            await client.send_video(Altruix.log_chat, temp_path, caption=caption_log, thumb=thumb_path)
                        elif source_msg.document:
                            await client.send_document(Altruix.log_chat, temp_path, caption=caption_log, thumb=thumb_path)
                    except Exception as log_err:
                        Altruix.log(f"RF Bypass Log failed: {log_err}")
                        
            finally:
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)
                if thumb_path and os.path.exists(thumb_path):
                    os.remove(thumb_path)
        
        await status_msg.delete()

    except Exception as e:
        if Altruix.log_chat and ('source_msg' in locals() and source_msg and not source_msg.empty):
             try:
                 try: await source_msg.copy(Altruix.log_chat)
                 except: await source_msg.forward(Altruix.log_chat)
                 backup_info = f" (Backup sent to Log Group)"
             except Exception: backup_info = ""
        else: backup_info = ""

        try: await status_msg.edit(f"❌ <b>Bypass Critical Error:</b> {str(e)}{backup_info}")
        except Exception: await message.reply(f"❌ <b>Bypass Critical Error:</b> {str(e)}{backup_info}")

@Altruix.register_on_cmd(
    cmd=["replyfroms", "replyfromscap", "replyfromscustom", "replyfromscust"],
    cmd_help={
        "categories": ["Utility"],
        "help": "Balas pesan menggunakan konten dari Story Telegram via proxy.",
        "description": "Balas pesan target menggunakan konten dari Story Telegram (Mendukung link story).\n\n"
                       "**Perbedaan CMD:**\n"
                       "• `.replyfroms` : Mengambil story TANPA caption asli (opsional noc/nocredit).\n"
                       "• `.replyfromscap` : Mengambil story DENGAN caption asli.\n"
                       "• `.replyfromscustom` : Mengambil story dengan CUSTOM caption.",
        "usage": ".replyfroms [noc] <story_link>\n"
                 ".replyfromscap <story_link>\n"
                 ".replyfromscustom <story_link> | <custom_caption>",
        "example": ".replyfroms https://t.me/username/s/123\n"
                   ".replyfroms noc https://t.me/username/s/123\n"
                   ".replyfromscap https://t.me/username/s/123\n"
                   ".replyfromscust https://t.me/username/s/123 | Ini caption story aesthetic!",
        "note": "✨ Auto-logs to Log Group. Bypass method supports thumbnails. Caption otomatis menggunakan format <blockquote expandable>."
    },
    requires_input=True,
    bot_mode_unsupported=True
)
@iuser_check
@log_errors
async def reply_from_story_handler(client: Client, message: RawMessage):
    """Fetch content from a story link and reply to the target msg with advanced caption & thumbnail support."""
    if not client or not client.me or client.me.is_bot:
        return
    from pyrogram import enums
    import os
    story = None 
    
    cmd_name = message.command[0].lower() if message.command else "replyfroms"
    
    mode_cap = "none"
    if cmd_name == "replyfromscap":
        mode_cap = "default"
    elif cmd_name in ["replyfromscustom", "replyfromscust"]:
        mode_cap = "custom"
        
    custom_text = ""
    raw_text = message.text or ""
    cmd_len = len(message.command[0]) + 1 if message.command else 11
    args_text = raw_text[cmd_len:].strip()
    
    if mode_cap == "custom":
        if "|" in args_text:
            split_parts = args_text.split("|", 1)
            args_text = split_parts[0].strip()
            custom_text = split_parts[1].strip()
        else:
            await message.edit("❌ <b>Usage:</b> <code>.replyfromscustom &lt;link&gt; | &lt;teks caption kustom&gt;</code>")
            return
            
    no_credit = False
    parts = args_text.split()
    
    if len(parts) >= 2 and parts[0].lower() in ["noc", "nocredit"]:
        no_credit = True
        link = parts[1]
    else:
        link = parts[0] if parts else ""

    if "t.me/" not in link or "/s/" not in link:
        await message.edit("❌ <b>Invalid Story Link!</b> format: <code>https://t.me/user/s/ID</code>")
        return

    if not message.reply_to_message:
        await message.edit("❌ <b>Error:</b> Reply to the target message first.")
        return

    status_msg = await message.edit("🔄 <b>Processing story...</b>")
    
    try:
        parts = link.rstrip("/").split("/")
        story_id = int(parts[-1])
        target_raw = parts[-3]
        
        if "t.me/c/" in link:
            target = int(f"-100{target_raw}")
        else:
            target = target_raw
            
        is_premium = client.me.is_premium
        reply_id = message.reply_to_message.id

        story = await client.get_stories(target, story_id)
        if not story:
            await status_msg.edit("❌ <b>Story not found/expired.</b>")
            return
        
        progress_task = create_progress_task(status_msg)
        file_path = await client.download_media(story)
        progress_task.cancel()
        if not file_path:
            await status_msg.edit("❌ <b>Download failed.</b>")
            return
            
        thumb_path = None
        if story.video and getattr(story.video, "thumbs", None):
            try:
                thumb_path = await client.download_media(story.video.thumbs[0].file_id)
            except Exception:
                pass

        # Auto Logging to Log Group
        uid = message.from_user.id
        logging_on = await get_rf_logging_setting(uid)
        if logging_on:
            await asyncio.sleep(1.0) 
            if Altruix.log_chat:
                try:
                    await client.forward_messages(Altruix.log_chat, target, story_id)
                except Exception:
                    try:
                        caption_log = f"📥 <b>Story Backup</b> from @{target_raw}"
                        if story.video:
                            await client.send_video(Altruix.log_chat, file_path, caption=caption_log, thumb=thumb_path)
                        else:
                            await client.send_photo(Altruix.log_chat, file_path, caption=caption_log)
                    except Exception as e:
                        try:
                            await client.copy_media_group(Altruix.log_chat, target, [story_id])
                        except:
                            Altruix.log(f"RF Story auto-forward failed: {e}")
        
        final_caption = ""
        
        if mode_cap == "custom":
            final_caption = custom_text
        elif mode_cap == "default":
            cap, _ = clean_premium_caption(story.caption or "", story.caption_entities, is_premium)
            final_caption = cap
            if not final_caption and not no_credit:
                 final_caption = f"📥 <b>Story from</b> @{target_raw}"
        elif mode_cap == "none":
            if not no_credit:
                 final_caption = f"📥 <b>Story from</b> @{target_raw}"

        if final_caption:
            final_caption = f"<blockquote expandable>{final_caption}</blockquote>"
        
        try:
            if story.video:
                v_dur = getattr(story.video, "duration", 0)
                v_w = getattr(story.video, "width", 0)
                v_h = getattr(story.video, "height", 0)
                await client.send_video(message.chat.id, file_path, caption=final_caption, parse_mode=enums.ParseMode.HTML, reply_to_message_id=reply_id, thumb=thumb_path, duration=v_dur, width=v_w, height=v_h, supports_streaming=True)
            else:
                await client.send_photo(message.chat.id, file_path, caption=final_caption, parse_mode=enums.ParseMode.HTML, reply_to_message_id=reply_id)
        except Exception as e:
             if Altruix.log_chat:
                 try:
                     caption_err = f"⚠️ <b>RF Error Backup</b> from @{target_raw}\nError: {e}"
                     if story.video:
                         await client.send_video(Altruix.log_chat, file_path, caption=caption_err, thumb=thumb_path)
                     else:
                         await client.send_photo(Altruix.log_chat, file_path, caption=caption_err)
                     backup_info = " (Backup sent to Log Group)"
                 except Exception:
                     backup_info = ""
             else:
                 backup_info = ""
             await status_msg.edit(f"❌ <b>Send Failed:</b> {e}{backup_info}")
             return
        finally:
            import os
            if file_path and os.path.exists(file_path): os.remove(file_path)
            if thumb_path and os.path.exists(thumb_path): os.remove(thumb_path)

        await status_msg.delete()

    except Exception as e:
        try:
            await status_msg.edit(f"❌ <b>Error:</b> {e}")
        except Exception:
            await message.reply(f"❌ <b>Error:</b> {e}")

# ============================================================================
# 🔥 RF LOGGING COMMANDS
# ============================================================================
@Altruix.register_on_cmd(
    cmd="rflogging",
    cmd_help={
        "categories": ["Utility"],
        "help": "Aktifkan/Matikan auto-logging ke Group Log untuk XReplyFrom.",
        "description": "Aktifkan/Matikan auto-logging ke Group Log untuk XReplyFrom.",
        "usage": ".rflogging <on/off>",
        "example": ".rflogging on\n.rflogging off"
    },
    requires_input=True,
    bot_mode_unsupported=True
)
@iuser_check
@log_errors
async def rf_logging_toggle_handler(client: Client, message: RawMessage):
    """Toggle RF auto-logging."""
    if not client or not client.me or client.me.is_bot:
        return
    uid = message.from_user.id
    input_val = message.user_input.lower().strip()
    
    if input_val in ["on", "true", "yes", "1"]:
        await set_rf_logging_setting(uid, True)
        await message.edit("✅ <b>RF Logging:</b> <code>ENABLED</code>")
    elif input_val in ["off", "false", "no", "0"]:
        await set_rf_logging_setting(uid, False)
        await message.edit("❌ <b>RF Logging:</b> <code>DISABLED</code>")
    else:
        await message.edit("❓ <b>Usage:</b> <code>.rflogging &lt;on/off&gt;</code>")

@Altruix.register_on_cmd(
    cmd="rfstatus",
    cmd_help={
        "categories": ["Utility"],
        "help": "Cek status pengaturan auto-logging XReplyFrom.",
        "description": "Cek status pengaturan XReplyFrom.",
        "usage": ".rfstatus",
        "example": ".rfstatus"
    },
    bot_mode_unsupported=True
)
@iuser_check
@log_errors
async def rf_status_handler(client: Client, message: RawMessage):
    """Show RF settings status."""
    if not client or not client.me or client.me.is_bot:
        return
    uid = message.from_user.id
    logging_on = await get_rf_logging_setting(uid)
    
    text = (
        "⚙️ <b>XReplyFrom Settings</b>\n"
        f"{'━' * 20}\n"
        f"• Auto Logging: {'✅ ENABLED' if logging_on else '❌ DISABLED'}\n"
        "• Fail-safe Backup: ✅ ALWAYS ACTIVE\n"
        f"{'━' * 20}\n"
        "<i>Gunakan .rflogging <on/off> untuk mengubah.</i>"
    )
    await message.edit(text)
