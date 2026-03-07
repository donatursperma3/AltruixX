from pyrogram import Client, filters
from Main import Altruix
from Main.core.decorators import iuser_check, log_errors
from Main.core.types.message import Message as RawMessage

# Plugin Metadata
def _get_plugin_name():
    import os
    return os.path.basename(__file__)

plugin_name = _get_plugin_name()
__plugin_name__ = "xreplyfrom"
PLUGIN_VERSION = "0.0.191"

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

@Altruix.register_on_cmd(
    cmd="replyfrom",
    cmd_help={
        "categories": ["Utility"],
        "description": "Balas pesan target menggunakan konten (Text/Media) dari chat atau ID pesan lain (Mendukung link).",
        "usage": ".replyfrom <chat_id/username/link> <message_id>",
        "example": ".replyfrom @username 5397852\n.replyfrom username 5397852\n.replyfrom https://t.me/username/5397852\n.replyfrom t.me/username/5397852",
        "note": "✨ Auto-logs to Log Group. If target send fails, it automatically backups to Log Group."
    },
    requires_input=True
)
@iuser_check
@log_errors
async def reply_from_handler(client: Client, message: RawMessage):
    """
    Fetch content from another message and reply to the target message.
    Usage: .replyfrom <chat_id> <message_id>
    """
    import re
    import asyncio
    from pyrogram import enums
    args = message.command or []
    source_msg = None # Initialize to avoid UnboundLocalError
    
    if not args and message.text:
        # Fallback if .command is None for some reason
        args = message.text.split()
    
    # Logic to handle Link or Space Separated arguments
    target_chat = None
    message_id = None
    
    # 1. Check for Link in any argument
    link_pattern = r"(?:https?://)?(?:t\.me/|telegram\.me/)(?:c/)?([\w.-]+)/(\d+)"
    
    for arg in args[1:]:
        match = re.search(link_pattern, arg)
        if match:
            chat_val = match.group(1)
            msg_id_val = match.group(2)
            
            # If it was /c/ID, prepend -100 to make it a supergroup ID
            if "/c/" in arg or "t.me/c/" in arg:
                target_chat = int(f"-100{chat_val}")
            else:
                target_chat = f"@{chat_val}" if not chat_val.startswith("@") else chat_val
            
            message_id = int(msg_id_val)
            break

    # 2. Fallback to space-separated format if no link found
    if target_chat is None:
        if len(args) < 3:
            await message.edit("❌ <b>Usage:</b> <code>.replyfrom [m] &lt;chat_id/username/link&gt; &lt;message_id&gt;</code>")
            return

        try:
            if args[1].lower() == "m" and len(args) >= 4:
                input_chat = args[2]
                msg_id_str = args[3]
            else:
                input_chat = args[1]
                msg_id_str = args[2]
            
            # chat_id can be int or str (@username)
            if input_chat.startswith("-100") or input_chat.isdigit():
                target_chat = int(input_chat)
            else:
                target_chat = input_chat # string username
                if not target_chat.startswith("@") and not target_chat.startswith("-"):
                    target_chat = f"@{target_chat}"
                
            message_id = int(msg_id_str)
        except (ValueError, IndexError):
            await message.edit("❌ <b>Error:</b> Invalid input format.")
            return

    # Check if this is a reply
    if not message.reply_to_message:
        await message.edit("❌ <b>Error:</b> Use this command as a reply to the message you want to respond to.")
        return

    status_msg = await message.edit(f"🔍 <b>Fetching:</b> <code>{target_chat}/{message_id}</code>...")

    try:
        source_msg = await client.get_messages(target_chat, message_id)
        if not source_msg or source_msg.empty:
            await status_msg.edit("❌ <b>Error:</b> Source message not found or is empty.")
            return

        # Auto Forward to Log Group (if enabled)
        uid = message.from_user.id
        logging_on = await get_rf_logging_setting(uid)
        
        if logging_on:
            await asyncio.sleep(3) # Delay to prevent FloodWait
            if Altruix.log_chat:
                try:
                    # ✅ ROBUST LOGGING: Try copy first (hides sender if possible), fallback to forward
                    try:
                        await source_msg.copy(Altruix.log_chat)
                    except Exception:
                        await source_msg.forward(Altruix.log_chat)
                except Exception as e:
                    Altruix.log(f"RF Auto-forward failed: {e}")

        # Attempt Method 1: standard Copy (Bypass Forward Restriction)
        try:
            await source_msg.copy(
                chat_id=message.chat.id,
                reply_to_message_id=message.reply_to_message.id
            )
            await status_msg.delete()
            return
        except Exception:
            # Method 1 failed, likely strict Protected Content
            try:
                await status_msg.edit("🧨 <b>Copy restricted.</b> Attempting robust bypass (Download & Upload)...")
            except Exception:
                pass

        # Attempt Method 2: Download & Upload Bypass
        if source_msg.media:
            # Handle Media Bypass
            temp_path = await client.download_media(source_msg)
            if not temp_path:
                await status_msg.edit("❌ <b>Bypass Failed:</b> Could not download restricted media.")
                return
            
            caption = source_msg.caption or ""
            reply_id = message.reply_to_message.id
            
            # Identify media type and send accordingly
            if source_msg.photo:
                await client.send_photo(message.chat.id, temp_path, caption=caption, reply_to_message_id=reply_id)
            elif source_msg.video:
                await client.send_video(message.chat.id, temp_path, caption=caption, reply_to_message_id=reply_id)
            elif source_msg.audio:
                await client.send_audio(message.chat.id, temp_path, caption=caption, reply_to_message_id=reply_id)
            elif source_msg.voice:
                await client.send_voice(message.chat.id, temp_path, caption=caption, reply_to_message_id=reply_id)
            elif source_msg.document:
                await client.send_document(message.chat.id, temp_path, caption=caption, reply_to_message_id=reply_id)
            elif source_msg.animation:
                await client.send_animation(message.chat.id, temp_path, caption=caption, reply_to_message_id=reply_id)
            elif source_msg.video_note:
                sent_msg = await client.send_video_note(message.chat.id, temp_path, reply_to_message_id=reply_id)
            elif source_msg.sticker:
                sent_msg = await client.send_sticker(message.chat.id, temp_path, reply_to_message_id=reply_id)
            elif source_msg.media == enums.MessageMediaType.PHOTO: # Fallback for edge cases
                 sent_msg = await client.send_photo(message.chat.id, temp_path, caption=caption, reply_to_message_id=reply_id)
            
            # ✅ ROBUST BACKUP: If bypass succeeded, we have the file. Use it for logging too.
            if logging_on and Altruix.log_chat:
                try:
                    # Reuse temp_path to send to log group
                    caption_log = f"📥 <b>Restricted Content Log</b>\nSource: <code>{target_chat}</code>\nTask ID: <code>{message.id}</code>"
                    if source_msg.photo:
                        await client.send_photo(Altruix.log_chat, temp_path, caption=caption_log)
                    elif source_msg.video:
                        await client.send_video(Altruix.log_chat, temp_path, caption=caption_log)
                    elif source_msg.document:
                        await client.send_document(Altruix.log_chat, temp_path, caption=caption_log)
                    # Add other types if needed
                except Exception as log_err:
                     Altruix.log(f"RF Bypass Log failed: {log_err}")
            
            # Clean up
            import os
            if os.path.exists(temp_path):
                os.remove(temp_path)
        
        elif source_msg.text:
            # Handle Text Bypass (rarely fails copy but for completeness)
            await client.send_message(
                message.chat.id, 
                source_msg.text, 
                reply_to_message_id=message.reply_to_message.id
            )
        
        await status_msg.delete()

    except Exception as e:
        # FAIL-SAFE BACKUP to Log Group
        if Altruix.log_chat and (source_msg and not source_msg.empty):
             try:
                 # Try copy first, then forward
                 try:
                     await source_msg.copy(Altruix.log_chat)
                 except:
                     await source_msg.forward(Altruix.log_chat)
                 backup_info = f" (Backup sent to Log Group)"
             except Exception:
                 backup_info = ""
        else:
             backup_info = ""

        try:
            await status_msg.edit(f"❌ <b>Bypass Critical Error:</b> {str(e)}{backup_info}")
        except Exception:
            await message.reply(f"❌ <b>Bypass Critical Error:</b> {str(e)}{backup_info}")

@Altruix.register_on_cmd(
    cmd="replyfromcap",
    cmd_help={
        "categories": ["Utility"],
        "description": "Mirip .replyfrom, namun memastikan caption media tetap terlampir (Mendukung link).",
        "usage": ".replyfromcap <chat_id/username/link> <message_id>",
        "example": ".replyfromcap @username 123",
        "note": "✨ Auto-logs to Log Group. If target send fails, it automatically backups to Log Group."
    },
    requires_input=True
)
@iuser_check
@log_errors
async def reply_from_cap_handler(client: Client, message: RawMessage):
    """
    Fetch content from another message and reply to the target message (same as copy logic).
    Usage: .replyfromcap <chat_id> <message_id>
    """
    # .copy() already handles captions, so the logic is identical to .replyfrom
    # but we keep the separate command as requested.
    await reply_from_handler(client, message)

@Altruix.register_on_cmd(
    cmd="replyfroms",
    cmd_help={
        "categories": ["Utility"],
        "description": "Balas pesan target menggunakan konten dari Story Telegram (Mendukung link story).",
        "usage": ".replyfroms [noc] <story_link>",
        "example": ".replyfroms https://t.me/username/s/123\n.replyfroms noc https://t.me/username/s/123",
        "note": "✨ Auto-logs to Log Group. If target send fails, it automatically backups to Log Group."
    },
    requires_input=True
)
@iuser_check
@log_errors
async def reply_from_story_handler(client: Client, message: RawMessage):
    """Fetch content from a story link and reply to the target msg."""
    import asyncio
    story = None # Initialize to avoid UnboundLocalError
    
    args = message.command or []
    if not args and message.text:
        args = message.text.split()
    
    if len(args) < 2:
        await message.edit("❌ <b>Usage:</b> <code>.replyfroms [noc] &lt;story_link&gt;</code>")
        return

    # Handle nocredit flag
    no_credit = False
    link = None
    
    if args[1].lower() in ["noc", "nocredit"] and len(args) >= 3:
        no_credit = True
        link = args[2]
    else:
        link = args[1]

    if "t.me/" not in link or "/s/" not in link:
        await message.edit("❌ <b>Invalid Story Link!</b> format: <code>https://t.me/user/s/ID</code>")
        return

    if not message.reply_to_message:
        await message.edit("❌ <b>Error:</b> Reply to the target message first.")
        return

    status_msg = await message.edit("🔄 <b>Processing story...</b>")
    
    try:
        # Parse link: https://t.me/username/s/123
        parts = link.split("/")
        story_id = int(parts[-1])
        target_raw = parts[-3]
        
        if "t.me/c/" in link:
            target = int(f"-100{target_raw}")
        else:
            target = target_raw
            
        is_premium = client.me.is_premium
        reply_id = message.reply_to_message.id

        # Bypass Logic (Direct download/upload to ensure Reply context and Control over caption)
        story = await client.get_stories(target, story_id)
        if not story:
            await status_msg.edit("❌ <b>Story not found/expired.</b>")
            return
        
        file_path = await client.download_media(story)
        if not file_path:
            await status_msg.edit("❌ <b>Download failed.</b>")
            return

        # Auto Logging to Log Group
        uid = message.from_user.id
        logging_on = await get_rf_logging_setting(uid)
        if logging_on:
            await asyncio.sleep(3) # Delay to prevent FloodWait
            if Altruix.log_chat:
                try:
                    # Forward story directly if supported or send downloaded file
                    await client.forward_messages(Altruix.log_chat, target, story_id)
                except Exception:
                    # Fallback to sending file to log chat
                    try:
                        caption_log = f"📥 <b>Story Backup</b> from @{target_raw}"
                        if story.video:
                            await client.send_video(Altruix.log_chat, file_path, caption=caption_log)
                        else:
                            await client.send_photo(Altruix.log_chat, file_path, caption=caption_log)
                    except Exception as e:
                        # Final Attempt: Direct copy/forward of ID
                        try:
                            await client.copy_media_group(Altruix.log_chat, target, [story_id])
                        except:
                            Altruix.log(f"RF Story auto-forward failed: {e}")
        
        caption, entities = clean_premium_caption(story.caption or "", story.caption_entities, is_premium)
        
        # If no caption and no_credit is False, add credit
        if not caption and not no_credit:
            caption = f"📥 <b>Story from</b> @{target_raw}"
        
        try:
            if story.video:
                await client.send_video(message.chat.id, file_path, caption=caption, caption_entities=entities, reply_to_message_id=reply_id)
            else:
                await client.send_photo(message.chat.id, file_path, caption=caption, caption_entities=entities, reply_to_message_id=reply_id)
        except Exception as e:
             # FAIL-SAFE BACKUP on send failure
             if Altruix.log_chat:
                 try:
                     caption_err = f"⚠️ <b>RF Error Backup</b> from @{target_raw}\nError: {e}"
                     if story.video:
                         await client.send_video(Altruix.log_chat, file_path, caption=caption_err)
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
            if os.path.exists(file_path): os.remove(file_path)

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
        "description": "Aktifkan/Matikan auto-logging ke Group Log untuk XReplyFrom.",
        "usage": ".rflogging <on/off>",
        "example": ".rflogging on\n.rflogging off"
    },
    requires_input=True
)
@iuser_check
@log_errors
async def rf_logging_toggle_handler(client: Client, message: RawMessage):
    """Toggle RF auto-logging."""
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
        "description": "Cek status pengaturan XReplyFrom.",
        "usage": ".rfstatus",
        "example": ".rfstatus"
    }
)
@iuser_check
@log_errors
async def rf_status_handler(client: Client, message: RawMessage):
    """Show RF settings status."""
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
