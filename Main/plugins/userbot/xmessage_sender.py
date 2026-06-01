# xmessage_sender.py
# Copyright (C) 2021-present by Altruix@Github, <https://github.com/Altruix>
# All rights reserved.

import os
import json
import asyncio
import logging
import html
import re
from pathlib import Path
from pyrogram import Client, filters, enums
from pyrogram.types import (
    Message as RawMessage, 
    ReplyParameters, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
    CallbackQuery,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent
)
from pyrogram.errors import (
    FloodWait, SlowmodeWait, ChatWriteForbidden, 
    PeerIdInvalid, MessageIdInvalid, ChannelPrivate
)

from Main import Altruix
from Main.core.types.message import Message
from Main.core.decorators import iuser_check, log_errors, send_log_message
from Main.utils.file_helpers import get_db_path, get_user_button_style

# Plugin Metadata
plugin_name = f"{os.path.basename(__file__)}"
__plugin_name__ = plugin_name if plugin_name else "xmessage_sender"
PLUGIN_VERSION = "1.1.130"

logger = logging.getLogger("altruix.xmessage_sender")
logger.setLevel(logging.INFO)

# ==================== PERSISTENT STORAGE ====================
STORAGE_FILE = Path(get_db_path("xmessage_sender_settings.json"))

def _load_settings() -> dict:
    try:
        if STORAGE_FILE.exists():
            with open(STORAGE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        Altruix.log(f"Failed to load xmessage_sender settings: {e}", level=40)
    return {}

def _save_settings(data: dict):
    try:
        STORAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STORAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        Altruix.log(f"Failed to save xmessage_sender settings: {e}", level=40)

def get_user_settings(user_id: int) -> dict:
    all_s = _load_settings()
    uid = str(user_id)
    defaults = {
        "notify_logs": True
    }
    if uid not in all_s:
        all_s[uid] = defaults
        _save_settings(all_s)
    return all_s[uid]

def save_user_settings(user_id: int, settings: dict):
    all_s = _load_settings()
    all_s[str(user_id)] = settings
    _save_settings(all_s)

# ==================== HELPERS ====================

def get_message_link(message: RawMessage) -> str:
    """Gets a clickable link for a message, even if it's in a private group."""
    if not message:
        return None
    if getattr(message, "link", None):
        return message.link
    
    # Manual construction for private chats/groups
    chat_id = getattr(message.chat, "id", None) if hasattr(message, "chat") else None
    msg_id = getattr(message, "id", None)
    
    if not chat_id or not msg_id:
        return None
        
    chat_id_str = str(chat_id)
    if chat_id_str.startswith("-100"):
        clean_id = chat_id_str[4:]
        return f"https://t.me/c/{clean_id}/{msg_id}"
    elif chat_id_str.startswith("-"):
        clean_id = chat_id_str[1:]
        return f"https://t.me/c/{clean_id}/{msg_id}"
        
    return None

def parse_tg_link(input_str: str) -> tuple:
    """
    Parses a Telegram link or raw ID/username.
    Returns: (chat_id_or_username, first_id, second_id)
    """
    if not input_str:
        return None, None, None
        
    # Private Link: https://t.me/c/2819883800/45463 or https://t.me/c/2819883800/45463/45465
    private_match = re.search(r"t\.me/c/(\d+)/(\d+)(?:/(\d+))?", input_str)
    if private_match:
        chat_id = int(f"-100{private_match.group(1)}")
        first_id = int(private_match.group(2))
        second_id = int(private_match.group(3)) if private_match.group(3) else None
        return chat_id, first_id, second_id
        
    # Public Link: t.me/username/123 or t.me/username/123/125
    public_match = re.search(r"t\.me/([a-zA-Z0-9_]+)/(\d+)(?:/(\d+))?", input_str)
    if public_match:
        chat = public_match.group(1)
        try: chat = int(chat)
        except: pass
        first_id = int(public_match.group(2))
        second_id = int(public_match.group(3)) if public_match.group(3) else None
        return chat, first_id, second_id

    # Raw ID or Username
    try:
        return int(input_str), None, None
    except ValueError:
        return input_str, None, None

def parse_story_link(input_str: str) -> tuple:
    """
    Parses a Telegram story link.
    Returns: (username_or_chat_id, story_id)
    """
    if not input_str:
        return None, None
        
    match = re.search(r"t\.me/([^/]+)/s/(\d+)", input_str)
    if match:
        chat = match.group(1)
        if chat == "c" and "t.me/c/" in input_str:
            cc_match = re.search(r"t\.me/c/(\d+)/s/(\d+)", input_str)
            if cc_match:
                return int(f"-100{cc_match.group(1)}"), int(cc_match.group(2))
        try: chat = int(chat)
        except: pass
        return chat, int(match.group(2))
        
    return None, None

async def resolve_chat_info(client: Client, chat_id):
    """
    Resolves chat info safely. Returns dict with type, title, username, id, is_forum.
    """
    info = {"type": "Unknown", "title": str(chat_id), "username": "none", "id": chat_id, "is_forum": False}
    try:
        chat = await client.get_chat(chat_id)
        if chat:
            info["id"] = chat.id
            info["username"] = f"@{chat.username}" if chat.username else "none"
            info["is_forum"] = getattr(chat, "is_forum", False)
            if chat.type == enums.ChatType.CHANNEL:
                info["type"] = "Channel"
                info["title"] = chat.title or str(chat.id)
            elif chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
                info["type"] = "Group"
                info["title"] = chat.title or str(chat.id)
            elif chat.type == enums.ChatType.PRIVATE:
                info["type"] = "User"
                info["title"] = chat.first_name or str(chat.id)
            elif chat.type == enums.ChatType.BOT:
                info["type"] = "Bot"
                info["title"] = chat.first_name or str(chat.id)
    except:
        pass
    return info

def make_clickable_name(chat_info: dict) -> str:
    """Creates a clickable HTML link for a chat/user."""
    name = html.escape(chat_info["title"])
    cid = chat_info["id"]
    uname = chat_info["username"]
    if chat_info["type"] in ["User", "Bot"]:
        return f"<a href='tg://user?id={cid}'>{name}</a>"
    elif uname != "none":
        return f"<a href='https://t.me/{uname.lstrip('@')}'>{name}</a>"
    return f"<code>{name}</code>"

async def send_action_log(client: Client, user_id: int, text: str, sent_msg: RawMessage = None, source_link: str = None, target_link: str = None):
    """Sends a log message with inline buttons. Optional auto-forward."""
    s = get_user_settings(user_id)
    if not s.get("notify_logs", True):
        return

    log_chat = Altruix.config.LOG_CHAT_ID
    if isinstance(log_chat, str) and log_chat.lstrip("-").isdigit():
        log_chat = int(log_chat)

    # Auto Forwarding Logic
    if s.get("auto_forward", False) and sent_msg and log_chat != "me":
        try:
            # We use the userbot client to forward its own sent message
            await sent_msg.forward(log_chat)
        except Exception as e:
            logger.debug(f"Sender auto-forward failed: {e}")

    # Build inline keyboard
    kb = []
    if source_link or target_link:
        row = []
        btn_style = get_user_button_style(user_id)
        if source_link:
            row.append(InlineKeyboardButton("From msg_id", url=source_link, style=btn_style))
        if target_link:
            row.append(InlineKeyboardButton("To msg_id", url=target_link, style=btn_style))
        kb.append(row)
    
    markup = InlineKeyboardMarkup(kb) if kb else None
    
    try:
        bot = None
        if hasattr(Altruix, 'bot_manager'):
            bot = Altruix.bot_manager.get_bot(user_id)
        if not bot:
            bot = Altruix.bot
            
        if bot and markup and log_chat != "me":
            await bot.send_message(
                log_chat, 
                f"<blockquote expandable>{text}</blockquote>", 
                reply_markup=markup,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )
            return
    except Exception as e:
        logger.debug(f"Failed to send log with buttons via bot: {e}")
        
    # Fallback
    await send_log_message(f"<blockquote expandable>{text}</blockquote>", reply_markup=markup)

def clean_premium_entities(text: str, entities: list, is_premium: bool):
    """
    Remove premium emojis from entities if session is not premium.
    Returns: (cleaned_text, cleaned_entities)
    """
    if is_premium:
        return text, entities
        
    if not entities:
        return text, None

    new_entities = []
    for entity in entities:
        if getattr(entity, "type", None) != enums.MessageEntityType.CUSTOM_EMOJI:
            new_entities.append(entity)
            
    return text, new_entities

import time

async def bypass_protected_send(client: Client, target_chat: int, source_msg, reply_to: int = None, message_thread_id: int = None, custom_text: str = None, wait_msg: Message = None):
    """
    Handles sending/cloning a message or story. 
    If content is protected, it downloads and re-uploads media.
    Returns: (sent_msg, is_bypassed)
    """
    reply_params = ReplyParameters(message_id=reply_to) if reply_to else None
    
    # Safely extract text/caption and entities
    original_text = getattr(source_msg, "text", None) or getattr(source_msg, "caption", "")
    caption = custom_text if custom_text is not None else getattr(source_msg, "caption", "")
    text = custom_text if custom_text is not None else original_text
    
    # Extract entities. Determine if we are keeping original entities or if custom_text overrides them.
    # If custom_text is present, we drop the original entities (as they would misalign).
    entities = None
    if custom_text is None:
        if getattr(source_msg, "entities", None):
            entities = source_msg.entities
        elif getattr(source_msg, "caption_entities", None):
            entities = source_msg.caption_entities
        else:
            # Fallback for stories
            story_obj = getattr(source_msg, "story", None)
            if story_obj and getattr(story_obj, "caption_entities", None):
                entities = story_obj.caption_entities
                
    # Clean up premium emojis if the userbot doesn't have premium
    is_premium = getattr(client.me, "is_premium", False)
    if not is_premium and entities:
         _, entities = clean_premium_entities("", entities, is_premium)
    
    # Check for media presence
    has_media = any(getattr(source_msg, attr, None) is not None for attr in ["media", "animation", "photo", "video", "document", "audio", "voice", "sticker", "story"])
    
    # Text-only
    if not has_media:
        res = await client.send_message(
            target_chat, 
            text, 
            entities=entities,
            reply_parameters=reply_params,
            message_thread_id=message_thread_id,
            parse_mode=enums.ParseMode.HTML if not entities else None
        )
        return res, False

    # Detect protected content
    is_protected = getattr(source_msg, "has_protected_content", False)
    if not is_protected:
        story_obj = getattr(source_msg, "story", None)
        if story_obj:
            is_protected = getattr(story_obj, "has_protected_content", False)

    # Optimization: Use copy_message for non-protected media/messages (excluding stories)
    if not is_protected and isinstance(source_msg, RawMessage) and not getattr(source_msg, "story", None):
        try:
            if wait_msg:
                try: await wait_msg.edit("⏳ <b>Cloning via copy...</b>")
                except: pass
            
            # If custom_text is None, copy_message keeps original caption and entities.
            # If custom_text is provided, we replace the caption/text.
            res = await client.copy_message(
                chat_id=target_chat,
                from_chat_id=source_msg.chat.id,
                message_id=source_msg.id,
                caption=custom_text if custom_text is not None else getattr(source_msg, "caption", None),
                reply_to_message_id=reply_to,
                message_thread_id=message_thread_id
            )
            return res, False
        except Exception as e:
            Altruix.log(f"copy_message failed, falling back to bypass: {e}", level=30)
            # Fall through to download/upload bypass logic

    if is_protected and wait_msg:
         try:
             await wait_msg.edit("⏳ <b>Media protected, trying to bypass...</b>")
         except: pass

    # Independent progress notifier task (not dependent on download chunks)
    progress_stages = [
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
    
    async def _progress_notifier():
        """Runs independently every 10s to update wait_msg based on elapsed time."""
        if not wait_msg:
            return
        stage = 0
        start = time.time()
        while stage < len(progress_stages):
            await asyncio.sleep(10)
            elapsed = time.time() - start
            while stage < len(progress_stages) and elapsed > progress_stages[stage][0]:
                try:
                    await wait_msg.edit(progress_stages[stage][1])
                except:
                    pass
                stage += 1
    
    progress_task = asyncio.create_task(_progress_notifier())
             
    # Media with protection check
    # We force re-upload for all media to ensure success against content protection
    temp_file = None
    try:
        Altruix.log(f"Starting download_media for source_msg type {type(source_msg)}")
        temp_file = await client.download_media(source_msg, in_memory=False)
        Altruix.log(f"download_media completed: {temp_file}")
        progress_task.cancel()
    except Exception as e:
        progress_task.cancel()
        Altruix.log(f"download_media exception: {e}")
        raise e
        
    thumb_file = None
    sent_res = None
    try:
        # Determine media type for re-upload
        # If it's a forwarded story inside a normal message, extract its true media type
        is_photo = getattr(source_msg, "photo", None) is not None
        is_video = getattr(source_msg, "video", None) is not None
        
        story_obj = getattr(source_msg, "story", None)
        if story_obj:
             is_photo = is_photo or (getattr(story_obj, "photo", None) is not None)
             is_video = is_video or (getattr(story_obj, "video", None) is not None)

        # Extract video/animation/audio metadata from the appropriate object
        media_obj = None
        if is_video:
            media_obj = getattr(source_msg, "video", None) or (getattr(story_obj, "video", None) if story_obj else None)
        elif getattr(source_msg, "animation", None):
            media_obj = source_msg.animation
        elif getattr(source_msg, "audio", None):
            media_obj = source_msg.audio
            
        v_duration = getattr(media_obj, "duration", 0) if media_obj else 0
        v_width = getattr(media_obj, "width", 0) if media_obj else 0
        v_height = getattr(media_obj, "height", 0) if media_obj else 0
        
        # Try to get thumbnail
        thumbs = getattr(media_obj, "thumbs", None) if media_obj else None
        if thumbs and len(thumbs) > 0:
            try:
                thumb_file = await client.download_media(source_msg, file_name="thumb_", in_memory=False)
                # Pyrogram doesn't have a direct "download thumb only" for re-upload,
                # so we skip thumb_file if it's the same as temp_file
                if thumb_file == temp_file:
                    thumb_file = None
            except:
                thumb_file = None
             
        if is_photo:
            sent_res = await client.send_photo(target_chat, temp_file, caption=caption, caption_entities=entities, reply_parameters=reply_params, message_thread_id=message_thread_id)
        elif is_video:
            sent_res = await client.send_video(
                target_chat, temp_file,
                caption=caption, caption_entities=entities,
                duration=v_duration, width=v_width, height=v_height,
                thumb=thumb_file,
                supports_streaming=True,
                reply_parameters=reply_params,
                message_thread_id=message_thread_id
            )
        elif getattr(source_msg, "document", None):
            sent_res = await client.send_document(target_chat, temp_file, caption=caption, caption_entities=entities, thumb=thumb_file, reply_parameters=reply_params, message_thread_id=message_thread_id)
        elif getattr(source_msg, "audio", None):
            sent_res = await client.send_audio(
                target_chat, temp_file,
                caption=caption, caption_entities=entities,
                duration=v_duration, thumb=thumb_file,
                reply_parameters=reply_params,
                message_thread_id=message_thread_id
            )
        elif getattr(source_msg, "voice", None):
            sent_res = await client.send_voice(target_chat, temp_file, caption=caption, caption_entities=entities, duration=v_duration, reply_parameters=reply_params, message_thread_id=message_thread_id)
        elif getattr(source_msg, "animation", None):
            sent_res = await client.send_animation(
                target_chat, temp_file,
                caption=caption, caption_entities=entities,
                duration=v_duration, width=v_width, height=v_height,
                thumb=thumb_file,
                reply_parameters=reply_params,
                message_thread_id=message_thread_id
            )
        elif getattr(source_msg, "sticker", None):
            sent_res = await client.send_sticker(target_chat, temp_file, reply_parameters=reply_params, message_thread_id=message_thread_id)
        else:
            sent_res = await client.send_document(target_chat, temp_file, caption=caption, caption_entities=entities, reply_parameters=reply_params, message_thread_id=message_thread_id)
            
        return sent_res, True
    finally:
        if temp_file and os.path.exists(temp_file):
            os.remove(temp_file)
        if thumb_file and os.path.exists(thumb_file):
            os.remove(thumb_file)

# ==================== COMMANDS ====================

@Altruix.register_on_cmd(
    ["sendto"],
    cmd_help={
        "help": "Send a direct text message to a target chat or thread.",
        "usage": ".sendto <target/link> <reply_id/none> <message>",
        "arguments": (
            "target/link: Chat ID, username, or t.me link (public/private).\n"
            "reply_id/none: Message ID to reply to, or use 'none'. If target is a link, its message ID is used by default.\n"
            "message: The text content to send.\n"
            "Note: Sent messages are logged and can be auto-forwarded to your log group (toggle via .sender_settings)."
        ),
        "example": (
            ".sendto @username none Hello there!\n"
            ".sendto -100123456789 42 How are you?\n"
            ".sendto https://t.me/c/123/456 none This uses link reply_id by default."
        ),
    },
)
@iuser_check
@log_errors
async def sendto_cmd(c: Client, m: Message):
    args = m.text.split()[1:] if m.text else []
    if not args or len(args) < 2:
        await m.reply_msg("❌ <b>Usage:</b> <code>.sendto &lt;target/link&gt; &lt;reply_id/none&gt; &lt;message&gt;</code>")
        return

    # Parse Target
    target_input = args[0]
    target_chat, first_id, second_id = parse_tg_link(target_input)
    
    # Check if target is a forum
    chat_info = await resolve_chat_info(c, target_chat)
    is_forum = chat_info.get("is_forum", False)
    
    message_thread_id = None
    link_reply_id = None
    if is_forum:
        message_thread_id = first_id
        link_reply_id = second_id
    else:
        link_reply_id = first_id
        
    # Logic for reply_id
    # If link_reply_id exists from target link, it overrides the second argument if second arg is 'none'
    reply_arg = args[1] if len(args) > 1 else "none"
    reply_id = None
    
    if reply_arg.lower() != "none" and reply_arg.isdigit():
        reply_id = int(reply_arg)
    elif link_reply_id:
        reply_id = link_reply_id
        
    # Message text
    text = " ".join(args[2:]) if len(args) > 2 else ""
    if not text:
        return await m.reply_msg("❌ <b>Please provide a message.</b>")

    wait = await m.handle_message("⏳ <b>Sending...</b>")
    
    try:
        sent_msg = await c.send_message(
            target_chat, 
            text, 
            message_thread_id=message_thread_id,
            reply_parameters=ReplyParameters(message_id=reply_id) if reply_id else None
        )
        await wait.edit_msg("✅ <b>Message sent successfully!</b>")
        t_link = get_message_link(sent_msg)
        
        # Build detailed log
        target_clickable = make_clickable_name(chat_info)
        log_text = (
            f"✅ <b>[Sender] Direct Message</b>\n"
            f"• To: {chat_info['type']}\n"
            f"• Chat/User ID: <code>{chat_info['id']}</code>\n"
            f"• Username: <code>{chat_info['username']}</code>\n"
            f"• Account: {c.me.mention}\n"
            f"• Target: {target_clickable}\n"
            f"• Reply to msg ID: <code>{reply_id or 'None'}</code>\n"
            f"• Thread ID: <code>{message_thread_id or 'None'}</code>\n"
            f"• ByPass: <code>False</code>"
        )
        await send_action_log(c, c.me.id, log_text, sent_msg=sent_msg, target_link=t_link)
        await asyncio.sleep(2)
        await wait.delete()
        await m.delete_if_self()
    except Exception as e:
        await wait.edit_msg(f"❌ <b>Failed:</b> <code>{str(e)}</code>")


@Altruix.register_on_cmd(
    ["sendfromto"],
    cmd_help={
        "help": "Clone a message (text/media) from a source chat to a target chat.",
        "usage": ".sendfromto <target/link> [reply_id/none] <source/link> [source_id]",
        "arguments": (
            "target/link: Destination chat or t.me link.\n"
            "reply_id/none: (Optional) ID to reply to in target.\n"
            "source/link: Source chat or specific t.me link to the message.\n"
            "source_id: (Optional) Message ID if source is just a chat ID/username.\n"
            "Note: Cloned messages are logged and can be auto-forwarded to your log group (toggle via .sender_settings)."
        ),
        "example": (
            ".sendfromto @target_group none @source_channel 100\n"
            ".sendfromto https://t.me/c/target/1 https://t.me/c/source/99\n"
            ".sendfromto -100111 none https://t.me/username/44"
        ),
    },
)
@iuser_check
@log_errors
async def sendfromto_cmd(c: Client, m: Message):
    args = m.text.split()[1:] if m.text else []
    if len(args) < 2:
        await m.reply_msg("❌ <b>Usage:</b> <code>.sendfromto &lt;target/link&gt; [reply_id/none] &lt;source/link&gt; [source_id]</code>")
        return

    # Flexible arg parsing
    # 1. Parse Target
    tg_chat, tg_first_id, tg_second_id = parse_tg_link(args[0])
    curr_idx = 1
    
    # Check if target is a forum
    chat_info = await resolve_chat_info(c, tg_chat)
    is_forum = chat_info.get("is_forum", False)
    
    message_thread_id = None
    link_reply_id = None
    if is_forum:
        message_thread_id = tg_first_id
        link_reply_id = tg_second_id
    else:
        link_reply_id = tg_first_id

    # Check if next arg is reply_id
    reply_id = link_reply_id
    if curr_idx < len(args) and args[curr_idx].isdigit():
        reply_id = int(args[curr_idx])
        curr_idx += 1
    elif curr_idx < len(args) and args[curr_idx].lower() == "none":
        reply_id = None
        curr_idx += 1

    # 2. Parse Source
    if curr_idx >= len(args):
        return await m.reply_msg("❌ <b>Missing source chat/link.</b>")
        
    src_chat, src_first_id, src_second_id = parse_tg_link(args[curr_idx])
    curr_idx += 1
    
    src_msg_id = src_second_id if src_second_id else src_first_id
    
    if not src_msg_id:
        if curr_idx < len(args) and args[curr_idx].isdigit():
            src_msg_id = int(args[curr_idx])
            curr_idx += 1
        else:
            return await m.reply_msg("❌ <b>Missing Source Message ID.</b>")

    wait = await m.handle_message("⏳ <b>Cloning message...</b>")

    try:
        source_msg = await c.get_messages(src_chat, src_msg_id)
        if not source_msg or source_msg.empty:
            return await wait.edit_msg("❌ <b>Source message not found.</b>")
            
        sent_msg, is_bypassed = await bypass_protected_send(c, tg_chat, source_msg, reply_id, message_thread_id=message_thread_id, wait_msg=wait)
        await wait.edit_msg("✅ <b>Message cloned successfully!</b>")
        s_link = get_message_link(source_msg)
        t_link = get_message_link(sent_msg)
        
        src_info = await resolve_chat_info(c, src_chat)
        target_clickable = make_clickable_name(chat_info)
        log_text = (
            f"✅ <b>[Sender] Message Cloned</b>\n"
            f"• From: {src_info['type']}\n"
            f"• Chat/User ID: <code>{src_info['id']}</code>\n"
            f"• Username: <code>{src_info['username']}</code>\n"
            f"• Msg ID: <code>{src_msg_id}</code>\n"
            f"• To: <code>{tg_chat}</code>\n"
            f"• Account: {c.me.mention}\n"
            f"• Target: {target_clickable}\n"
            f"• Reply to msg ID: <code>{reply_id or 'None'}</code>\n"
            f"• Thread ID: <code>{message_thread_id or 'None'}</code>\n"
            f"• ByPass: <code>{is_bypassed}</code>"
        )
        await send_action_log(c, c.me.id, log_text, sent_msg=sent_msg, source_link=s_link, target_link=t_link)
        await asyncio.sleep(2)
        await wait.delete()
        await m.delete_if_self()
    except Exception as e:
        await wait.edit_msg(f"❌ <b>Error:</b> <code>{str(e)}</code>")


@Altruix.register_on_cmd(
    ["sendfromtocus"],
    cmd_help={
        "help": "Clone a message with custom text (replaces or appends text/caption).",
        "usage": ".sendfromtocus <target/link> [reply_id/none] <source/link> [source_id] <custom_text>",
        "arguments": (
            "target/link: Destination chat or link.\n"
            "source/link: Source chat or message link.\n"
            "custom_text: The new message or caption to use for the clone.\n"
            "Note: Cloned messages with custom text are logged and can be auto-forwarded to your log group (toggle via .sender_settings)."
        ),
        "example": (
            ".sendfromtocus @group none @chan 100 New Caption Here\n"
            ".sendfromtocus link_target link_source Check this out!"
        ),
    },
)
@iuser_check
@log_errors
async def sendfromtocus_cmd(c: Client, m: Message):
    args = m.text.split()[1:] if m.text else []
    if len(args) < 3:
        await m.reply_msg("❌ <b>Usage:</b> <code>.sendfromtocus &lt;target/link&gt; [reply_id/none] &lt;source/link&gt; [source_id] &lt;custom_text&gt;</code>")
        return

    # 1. Target
    tg_chat, tg_first_id, tg_second_id = parse_tg_link(args[0])
    curr_idx = 1
    
    # Check if target is a forum
    chat_info = await resolve_chat_info(c, tg_chat)
    is_forum = chat_info.get("is_forum", False)
    
    message_thread_id = None
    link_reply_id = None
    if is_forum:
        message_thread_id = tg_first_id
        link_reply_id = tg_second_id
    else:
        link_reply_id = tg_first_id

    reply_id = link_reply_id
    if curr_idx < len(args) and args[curr_idx].isdigit():
        reply_id = int(args[curr_idx])
        curr_idx += 1
    elif curr_idx < len(args) and args[curr_idx].lower() == "none":
        reply_id = None
        curr_idx += 1

    # 2. Source
    src_chat, src_first_id, src_second_id = parse_tg_link(args[curr_idx])
    curr_idx += 1
    
    src_msg_id = src_second_id if src_second_id else src_first_id
    if not src_msg_id:
        if curr_idx < len(args) and args[curr_idx].isdigit():
            src_msg_id = int(args[curr_idx])
            curr_idx += 1
        else:
            return await m.reply_msg("❌ <b>Missing Source Message ID.</b>")

    # 3. Custom Text (All remaining args)
    custom_text = " ".join(args[curr_idx:])
    if not custom_text:
        return await m.reply_msg("❌ <b>Please provide custom text.</b>")

    wait = await m.handle_message("⏳ <b>Cloning with custom text...</b>")

    try:
        source_msg = await c.get_messages(src_chat, src_msg_id)
        if not source_msg or source_msg.empty:
            return await wait.edit_msg("❌ <b>Source message not found.</b>")
            
        sent_msg, is_bypassed = await bypass_protected_send(c, tg_chat, source_msg, reply_id, message_thread_id=message_thread_id, custom_text=custom_text, wait_msg=wait)
        await wait.edit_msg("✅ <b>Message cloned with custom text!</b>")
        s_link = get_message_link(source_msg)
        t_link = get_message_link(sent_msg)
        
        src_info = await resolve_chat_info(c, src_chat)
        target_clickable = make_clickable_name(chat_info)
        log_text = (
            f"✅ <b>[Sender] Custom Clone</b>\n"
            f"• From: {src_info['type']}\n"
            f"• Chat/User ID: <code>{src_info['id']}</code>\n"
            f"• Username: <code>{src_info['username']}</code>\n"
            f"• Msg ID: <code>{src_msg_id}</code>\n"
            f"• To: <code>{tg_chat}</code>\n"
            f"• Account: {c.me.mention}\n"
            f"• Target: {target_clickable}\n"
            f"• Reply to msg ID: <code>{reply_id or 'None'}</code>\n"
            f"• Thread ID: <code>{message_thread_id or 'None'}</code>\n"
            f"• ByPass: <code>{is_bypassed}</code>"
        )
        await send_action_log(c, c.me.id, log_text, sent_msg=sent_msg, source_link=s_link, target_link=t_link)
        await asyncio.sleep(2)
        await wait.delete()
        await m.delete_if_self()
    except Exception as e:
        await wait.edit_msg(f"❌ <b>Error:</b> <code>{str(e)}</code>")


@Altruix.register_on_cmd(
    ["sendfromtos"],
    cmd_help={
        "help": "Clone a Telegram story to a target chat.",
        "usage": ".sendfromtos <target/link> [reply_id/none] <story_link>",
        "arguments": (
            "target/link: Destination chat or t.me link.\n"
            "reply_id/none: (Optional) ID to reply to in target.\n"
            "story_link: Link to the story (e.g., t.me/username/s/123).\n"
            "Note: Cloned stories are logged and can be auto-forwarded to your log group (toggle via .sender_settings)."
        ),
        "example": (
            ".sendfromtos @target_group none https://t.me/username/s/42\n"
            ".sendfromtos -10012345 99 https://t.me/c/123/s/4"
        ),
    },
)
@iuser_check
@log_errors
async def sendfromtos_cmd(c: Client, m: Message):
    args = m.text.split()[1:] if m.text else []
    if len(args) < 2:
        await m.reply_msg("❌ <b>Usage:</b> <code>.sendfromtos &lt;target/link&gt; [reply_id/none] &lt;story_link&gt;</code>")
        return

    # 1. Target Extract
    tg_chat, tg_first_id, tg_second_id = parse_tg_link(args[0])
    curr_idx = 1
    
    # Check if target is a forum
    chat_info = await resolve_chat_info(c, tg_chat)
    is_forum = chat_info.get("is_forum", False)
    
    message_thread_id = None
    link_reply_id = None
    if is_forum:
        message_thread_id = tg_first_id
        link_reply_id = tg_second_id
    else:
        link_reply_id = tg_first_id

    reply_id = link_reply_id
    if curr_idx < len(args) and args[curr_idx].isdigit():
        reply_id = int(args[curr_idx])
        curr_idx += 1
    elif curr_idx < len(args) and args[curr_idx].lower() == "none":
        reply_id = None
        curr_idx += 1

    # 2. Source Story Extract
    if curr_idx >= len(args):
        return await m.reply_msg("❌ <b>Missing Story Link.</b>")
        
    src_chat, src_story_id = parse_story_link(args[curr_idx])
    
    if not src_story_id:
         return await m.reply_msg("❌ <b>Invalid Story Link. Please use format like https://t.me/username/s/123</b>")

    wait = await m.handle_message("⏳ <b>Cloning story...</b>")

    try:
        Altruix.log(f"Fetching story {src_story_id} from {src_chat}")
        story = await c.get_stories(src_chat, src_story_id)
        if not story:
            return await wait.edit_msg("❌ <b>Story not found or expired.</b>")
            
        if isinstance(story, list):
            story = story[0] if len(story) > 0 else None
            if not story:
                return await wait.edit_msg("❌ <b>Story not found (empty list).</b>")
                
        Altruix.log("Calling bypass_protected_send")
        sent_msg, is_bypassed = await bypass_protected_send(c, tg_chat, story, reply_id, message_thread_id=message_thread_id, wait_msg=wait)
        Altruix.log("bypass_protected_send completed")
        await wait.edit_msg("✅ <b>Story cloned successfully!</b>")
        
        # Link not always available easily for stories. Use arg link.
        s_link = args[curr_idx] 
        t_link = get_message_link(sent_msg)
        
        src_info = await resolve_chat_info(c, src_chat)
        target_clickable = make_clickable_name(chat_info)
        log_text = (
            f"✅ <b>[Sender] Story Cloned</b>\n"
            f"• From: {src_info['type']} (story)\n"
            f"• Chat/User ID: <code>{src_info['id']}</code>\n"
            f"• Username: <code>{src_info['username']}</code>\n"
            f"• Story ID: <code>{src_story_id}</code>\n"
            f"• To: <code>{tg_chat}</code>\n"
            f"• Account: {c.me.mention}\n"
            f"• Target: {target_clickable}\n"
            f"• Reply to msg ID: <code>{reply_id or 'None'}</code>\n"
            f"• Thread ID: <code>{message_thread_id or 'None'}</code>\n"
            f"• ByPass: <code>{is_bypassed}</code>"
        )
        await send_action_log(c, c.me.id, log_text, sent_msg=sent_msg, source_link=s_link, target_link=t_link)
        await asyncio.sleep(2)
        await wait.delete()
        await m.delete_if_self()
    except Exception as e:
        await wait.edit_msg(f"❌ <b>Error:</b> <code>{str(e)}</code>")


@Altruix.register_on_cmd(
    ["sendfromtoscus"],
    cmd_help={
        "help": "Clone a Telegram story with a custom caption.",
        "usage": ".sendfromtoscus <target/link> [reply_id/none] <story_link> <custom_text>",
        "arguments": (
            "target/link: Destination chat or link.\n"
            "story_link: Link to the story.\n"
            "custom_text: New caption for the cloned story.\n"
            "Note: Cloned stories with custom text are logged and can be auto-forwarded to your log group (toggle via .sender_settings)."
        ),
        "example": (
            ".sendfromtoscus @target_group none https://t.me/username/s/42 Look at this!\n"
        ),
    },
)
@iuser_check
@log_errors
async def sendfromtoscus_cmd(c: Client, m: Message):
    args = m.text.split()[1:] if m.text else []
    if len(args) < 3:
        await m.reply_msg("❌ <b>Usage:</b> <code>.sendfromtoscus &lt;target/link&gt; [reply_id/none] &lt;story_link&gt; &lt;custom_text&gt;</code>")
        return

    # 1. Target
    tg_chat, tg_first_id, tg_second_id = parse_tg_link(args[0])
    curr_idx = 1
    
    # Check if target is a forum
    chat_info = await resolve_chat_info(c, tg_chat)
    is_forum = chat_info.get("is_forum", False)
    
    message_thread_id = None
    link_reply_id = None
    if is_forum:
        message_thread_id = tg_first_id
        link_reply_id = tg_second_id
    else:
        link_reply_id = tg_first_id

    reply_id = link_reply_id
    if curr_idx < len(args) and args[curr_idx].isdigit():
        reply_id = int(args[curr_idx])
        curr_idx += 1
    elif curr_idx < len(args) and args[curr_idx].lower() == "none":
        reply_id = None
        curr_idx += 1

    # 2. Source Story Extract
    if curr_idx >= len(args):
        return await m.reply_msg("❌ <b>Missing Story Link.</b>")
        
    src_chat, src_story_id = parse_story_link(args[curr_idx])
    story_link_str = args[curr_idx]
    curr_idx += 1
    
    if not src_story_id:
         return await m.reply_msg("❌ <b>Invalid Story Link. Please use format like https://t.me/username/s/123</b>")

    # 3. Custom Text (All remaining args)
    custom_text = " ".join(args[curr_idx:])
    if not custom_text:
        return await m.reply_msg("❌ <b>Please provide custom text.</b>")

    wait = await m.handle_message("⏳ <b>Cloning story with custom text...</b>")

    try:
        Altruix.log(f"Fetching story {src_story_id} from {src_chat}")
        story = await c.get_stories(src_chat, src_story_id)
        if not story:
            Altruix.log("Story not found")
            return await wait.edit_msg("❌ <b>Story not found or expired.</b>")
            
        Altruix.log(f"Story retrieved! Type: {type(story)}")
        # Quick check if it's a list:
        if isinstance(story, list):
            # In some Pyrogram versions get_stories returns a list even for a single ID
            story = story[0] if len(story) > 0 else None
            if not story:
                return await wait.edit_msg("❌ <b>Story not found (empty list).</b>")
                
        Altruix.log("Calling bypass_protected_send")
        sent_msg, is_bypassed = await bypass_protected_send(c, tg_chat, story, reply_id, message_thread_id=message_thread_id, custom_text=custom_text, wait_msg=wait)
        Altruix.log("bypass_protected_send completed")
        await wait.edit_msg("✅ <b>Story cloned with custom text!</b>")
        
        t_link = get_message_link(sent_msg)
        
        src_info = await resolve_chat_info(c, src_chat)
        target_clickable = make_clickable_name(chat_info)
        log_text = (
            f"✅ <b>[Sender] Custom Story Clone</b>\n"
            f"• From: {src_info['type']} (story)\n"
            f"• Chat/User ID: <code>{src_info['id']}</code>\n"
            f"• Username: <code>{src_info['username']}</code>\n"
            f"• Story ID: <code>{src_story_id}</code>\n"
            f"• To: <code>{tg_chat}</code>\n"
            f"• Account: {c.me.mention}\n"
            f"• Target: {target_clickable}\n"
            f"• Reply to msg ID: <code>{reply_id or 'None'}</code>\n"
            f"• Thread ID: <code>{message_thread_id or 'None'}</code>\n"
            f"• ByPass: <code>{is_bypassed}</code>"
        )
        await send_action_log(c, c.me.id, log_text, sent_msg=sent_msg, source_link=story_link_str, target_link=t_link)
        await asyncio.sleep(2)
        await wait.delete()
        await m.delete_if_self()
    except Exception as e:
        await wait.edit_msg(f"❌ <b>Error:</b> <code>{str(e)}</code>")

@Altruix.register_on_cmd(
    ["sender_settings"],
    cmd_help={
        "help": "Display the Message Sender configuration dashboard.",
        "usage": ".sender_settings",
        "description": "Allows you to toggle group log notifications and auto-forwarding of sent/cloned messages to the group log."
    },
)
@iuser_check
@log_errors
async def sender_settings_cmd(client: Client, message: Message):
    user_id = client.me.id
    
    bot_username = None
    if hasattr(Altruix, 'bot_manager'):
        bot_username = Altruix.bot_manager.get_bot_username(user_id)
    if not bot_username and Altruix.bot and Altruix.bot.me:
        bot_username = Altruix.bot.me.username
        
    if bot_username:
        try:
            results = await client.get_inline_bot_results(bot_username, f"sender_set_{user_id}")
            if results.results:
                await client.send_inline_bot_result(
                    message.chat.id,
                    results.query_id,
                    results.results[0].id,
                    reply_to_message_id=message.id
                )
                return
        except Exception as e:
            Altruix.log(f"Sender settings inline bot fetch failed: {e}")
            
    # Fallback to normal reply if inline fails or bot is missing
    s = get_user_settings(user_id)
    notify = s.get("notify_logs", True)
    autofwd = s.get("auto_forward", False)
    text = (
        "📨 <b>Message Sender Settings</b>\n"
        f"<blockquote expandable>"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"• <b>Account:</b> {html.escape(client.me.first_name)}\n"
        f"• <b>Notify Logs:</b> {'✅ ON' if notify else '❌ OFF'}\n"
        f"• <b>Auto-Forward:</b> {'✅ ON' if autofwd else '❌ OFF'}\n\n"
        "<i>(Inline buttons require the Bot Assistant to be active)</i>\n"
        f"</blockquote>"
    )
    await message.reply_msg(text)

# ==================== INLINE QUERY & CALLBACKS ====================

@Altruix.bot.on_inline_query(filters.regex(r"^sender_set_(\d+)"))
async def sender_inline_menu(c: Client, inline_query: InlineQuery):
    user_id = int(inline_query.matches[0].group(1))
    s = get_user_settings(user_id)
    notify = s.get("notify_logs", True)
    autofwd = s.get("auto_forward", False)
    
    text = (
        "📨 <b>Message Sender Settings</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"• <b>Account ID:</b> <code>{user_id}</code>\n"
        f"• <b>Notify Logs:</b> {'✅ ON' if notify else '❌ OFF'}\n"
        f"• <b>Auto-Forward:</b> {'✅ ON' if autofwd else '❌ OFF'}\n"
    )
    
    kb = [
        [
            InlineKeyboardButton(
                f"{'🟢' if notify else '🔴'} Logs", 
                callback_data=f"sendset_notif_{user_id}"
            ),
            InlineKeyboardButton(
                f"{'🟢' if autofwd else '🔴'} Auto-Fwd", 
                callback_data=f"sendset_fwd_{user_id}"
            )
        ]
    ]
    
    await inline_query.answer(
        results=[
            InlineQueryResultArticle(
                title="Message Sender Settings",
                input_message_content=InputTextMessageContent(text, parse_mode=enums.ParseMode.HTML),
                reply_markup=InlineKeyboardMarkup(kb)
            )
        ],
        cache_time=0
    )

@Altruix.bot.on_callback_query(filters.regex(r"^sendset_(notif|fwd)_(\d+)"))
@iuser_check
async def sender_settings_cb(c: Client, cb: CallbackQuery):
    action = cb.matches[0].group(1)
    user_id = int(cb.matches[0].group(2))
    s = get_user_settings(user_id)
    
    if action == "notif":
        s["notify_logs"] = not s.get("notify_logs", True)
    elif action == "fwd":
        s["auto_forward"] = not s.get("auto_forward", False)
        
    save_user_settings(user_id, s)
    
    notify = s.get("notify_logs", True)
    autofwd = s.get("auto_forward", False)
    
    text = (
        "📨 <b>Message Sender Settings</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"• <b>Account ID:</b> <code>{user_id}</code>\n"
        f"• <b>Notify Logs:</b> {'✅ ON' if notify else '❌ OFF'}\n"
        f"• <b>Auto-Forward:</b> {'✅ ON' if autofwd else '❌ OFF'}\n"
    )
    
    kb = [
        [
            InlineKeyboardButton(
                f"{'🟢' if notify else '🔴'} Logs", 
                callback_data=f"sendset_notif_{user_id}"
            ),
            InlineKeyboardButton(
                f"{'🟢' if autofwd else '🔴'} Auto-Fwd", 
                callback_data=f"sendset_fwd_{user_id}"
            )
        ]
    ]
    
    await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=enums.ParseMode.HTML)
    await cb.answer("Settings Updated", show_alert=False)
