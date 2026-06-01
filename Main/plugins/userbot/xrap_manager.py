# xrap_manager.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.

"""
🎤 RAP MANAGER PLUGIN FOR ALTRUIX
================================

Features:
- JSON-based lyric database (rap_db.json).
- Multi-client synchronization (sync across all sessions).
- Automated Rhyme Formatting (Bold + Spoiler for the last word of each line).
- Task ID system to track and stop lyric delivery.
- Comprehensive Management Dashboard (.dm) with full CRUD support.
- Response Modes: Reply (new message) or Edit (overwrite previous line).
- Customizable rhyme emoji suffixes.

Command List:
.rap <slug> [delay] - Start sending lyrics by song slug.
.rapstop [id|all]   - Stop ongoing lyric tasks.
.raplist           - List all songs in the collection.
.rapfind <query>   - Search for songs by title or slug.
.raprand           - Send a random lyric line (Quick Diss).
.rapmanage   - Open the interactive management dashboard.
.raprefresh        - Reload the database from the JSON file.
.rapexport         - Export and backup the database as a file.
.rapimport         - Import/Merge database from a replied JSON file.

Reply Rules:
- If the command is a reply to a message, the response will reply to THAT target message.
- If the command is NOT a reply, the response will reply to the command message itself.
"""

from Main import Altruix
from pyrogram import Client, filters, enums
from pyrogram.types import (
    Message as RawMessage,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
    ReplyParameters,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    ChosenInlineResult
)
from Main.core.types.message import Message as AltruixMessage
from Main.core.decorators import log_errors, iuser_check
from Main.utils.essentials import Essentials
from Main.utils.file_helpers import get_db_path, make_file_from_text, get_user_button_style
from pyrogram.errors import (
    FloodWait, MessageNotModified, ChatWriteForbidden, 
    UserIsBlocked, PeerIdInvalid, ChannelInvalid, ChatAdminRequired
)
import os
import json
import asyncio
import random
import time
import html
import re
import hashlib
import traceback
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

# --- TASK REGISTRY HELPERS ---
def _x_gen_id(prefix="RP"):
    try:
        from Main.plugins.userbot.xtaskmanager import generate_task_id
        return generate_task_id(prefix)
    except:
        import random
        import string
        return f"#{prefix}" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))

def _x_register(tid, task, name, plugin, uid=None, details=""):
    try:
        from Main.plugins.userbot.xtaskmanager import register_task
        register_task(tid, task, name, plugin, uid, details)
    except: pass

def _x_unregister(tid):
    try:
        from Main.plugins.userbot.xtaskmanager import unregister_task
        unregister_task(tid)
    except: pass

def _get_bot(client_id):
    """Get custom bot for session or fallback to main bot."""
    if hasattr(Altruix, "bot_manager"):
        try:
            bot = Altruix.bot_manager.get_bot(client_id)
            if bot and getattr(bot, "is_connected", False):
                return bot
        except: pass
    return Altruix.bot

# --- CONFIG & PATHS ---
PLUGIN_NAME = "Rap Manager"
PLUGIN_VERSION = "1.2.48.34"
RAP_DB_PATH = Path(get_db_path("rap_db.json"))
logger = logging.getLogger("altruix.rap_manager")

# block global registry
# Global Registry for Active Rap Tasks
# Structure: {task_id: {"task": Task, "client_id": int, "chat_id": int, "slug": str, "start_time": float}}
RAP_TASKS: Dict[str, Dict[str, Any]] = {}

# block database manager
# --- DATABASE MANAGER ---
class RapManager:
    """
    Manager class for the Rap Lyric Database (JSON).
    Handles loading, saving, and CRUD operations for song data.
    """
    # block init registry
    def __init__(self):
        """Initialize the manager with default data structure."""
        self.data = {
            "lyrics": {}, 
            "global_config": {
                "default_delay": 6, 
                "default_emoji": "🔥", 
                "mode": "reply", 
                "inline_mode": False,
                "lines_per_msg": 2,
                "markdown_type": "None", # None, Italic, Underline, Italic+Underline
                "send_limit_enabled": True,
                "send_limit_max": 4,
                "send_limit_alert_enabled": True
            }
        }
        self.load()

    # block load database
    def load(self):
        """Load the database from rap_db.json if it exists."""
        if RAP_DB_PATH.exists():
            try:
                with open(RAP_DB_PATH, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load rap_db.json: {e}")
        else:
            self.save()

    # block save database
    def save(self):
        """Save the current database state to rap_db.json."""
        try:
            RAP_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(RAP_DB_PATH, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save rap_db.json: {e}")

    # block get song
    def get_song(self, slug: str) -> Optional[Dict[str, Any]]:
        """Retrieve a song dictionary by its unique slug."""
        return self.data["lyrics"].get(slug)

    # block add song
    def add_song(self, slug: str, title: str, lyrics: List[str], config: Dict[str, Any] = None):
        """Add or update a song in the database."""
        self.data["lyrics"][slug] = {
            "title": title,
            "lyrics": lyrics,
            "config": config or {}
        }
        self.save()

    # block delete song
    def delete_song(self, slug: str) -> bool:
        """Remove a song from the database by its slug."""
        if slug in self.data["lyrics"]:
            del self.data["lyrics"][slug]
            self.save()
            return True
        return False

    # block rename slug
    def rename_slug(self, old_slug: str, new_slug: str) -> bool:
        """Rename a song's slug by moving its data to a new key."""
        if old_slug in self.data["lyrics"] and new_slug not in self.data["lyrics"]:
            self.data["lyrics"][new_slug] = self.data["lyrics"].pop(old_slug)
            self.save()
            return True
        return False

    # block get all songs
    def get_all_songs(self) -> Dict[str, Dict[str, Any]]:
        """Return the dictionary containing all songs."""
        return self.data["lyrics"]

rap_db = RapManager()

# --- HELPERS ---
# block generate task id
def generate_task_id():
    return _x_gen_id("RAP")

# block get target id
def get_target_id(m: AltruixMessage) -> int:
    """
    Determine the message ID that should be replied to.
    If the command is a reply, returns the replied message ID.
    Otherwise, returns the command's own message ID.
    """
    return m.reply_to_message.id if m.reply_to_message else m.id

# block rhyme formatter
def rhyme_formatter(text: str) -> str:
    """
    Apply automated formatting to the last word of a line.
    Wraps the last word in bold and spoiler tags (e.g., ||**word**||).
    """
    if not text: return ""
    words = text.split()
    if not words: return text
    
    last_word = words[-1]
    # Match word part and trailing punctuation
    match = re.search(r"(\w+)([^\w]*)$", last_word)
    if match:
        word_part = match.group(1)
        punct_part = match.group(2)
        # Wrap in bold and spoiler using HTML tags
        formatted_last = f"<spoiler><b>{word_part}</b></spoiler>{punct_part}"
        words[-1] = formatted_last
    else:
        words[-1] = f"<spoiler><b>{last_word}</b></spoiler>"
        
    return " ".join(words)

# block markdown formatter
def markdown_formatter(text: str, mtype: str) -> str:
    """Apply selected HTML markdown formatting to the text."""
    if not text or mtype == "None":
        return text
    
    if mtype == "Italic":
        return f"<i>{text}</i>"
    elif mtype == "Underline":
        return f"<u>{text}</u>"
    elif mtype == "Italic+Underline":
        return f"<i><u>{text}</u></i>"
    return text

# block send log
async def send_log(text: str, userbot_name: str = "Unknown", chat_title: str = "Unknown", chat_link: str = "", chat_id: str = ""):
    """Send a formatted notification to the configured Group Log chat."""
    try:
        if Altruix.log_chat:
            chat_str = f"<a href='{chat_link}'>{html.escape(chat_title)}</a>" if chat_link else html.escape(chat_title)
            full_text = (
                f"🎤 <b>[RAP MANAGER]</b>\n"
                f"<blockquote expandable>{text}\n"
                f"Userbot: <code>{userbot_name}</code>\n"
                f"Chat: {chat_str}\n"
                f"ChatID: <code>{chat_id}</code></blockquote>"
            )
            await Altruix.bot.send_message(
                Altruix.log_chat,
                full_text,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )
    except Exception as e:
        logger.error(f"Failed to send rap log: {e}")

# --- CORE EXECUTION ENGINE ---
# block core execution engine
# Main executor for automated line-by-line lyric delivery.
# Compatible with direct commands (.rap) and dashboard interactions (.rapmanage).
# block rap executor
# Core of the plugin: handles the asynchronous lyric delivery loop.
async def rap_executor(c: Client, chat_id: int, slug: str, custom_delay: int = None, reply_to_id: int = None, task_id: str = None):
    """
    Background worker that handles line-by-line lyric delivery.
    Standardized to work with both direct commands and dashboard triggers.
    Includes 'Loopback' method for authorized inline edits.
    """
    if not task_id: task_id = generate_task_id()
    
    # Check for duplicate tasks
    if task_id in RAP_TASKS: return
    
    song = rap_db.get_song(slug)
    if not song: return
    
    lyrics = song["lyrics"]
    title = song["title"]
    config = song["config"]
    
    # block config hierarchy
    # Configuration fallback hierarchy
    delay = custom_delay or config.get("delay") or rap_db.data["global_config"].get("default_delay", 6)
    mode = config.get("mode") or rap_db.data["global_config"].get("mode", "reply")
    emoji = config.get("emoji") or rap_db.data["global_config"].get("default_emoji", "🔥")
    lines_per_msg = max(1, config.get("lines_per_msg") or rap_db.data["global_config"].get("lines_per_msg", 2))
    mtype = config.get("markdown_type") or rap_db.data["global_config"].get("markdown_type", "None")
    inline_mode = rap_db.data["global_config"].get("inline_mode", False)
    clean_reply = rap_db.data["global_config"].get("clean_reply", False)
    bot_username = Altruix.bot_manager.get_bot_username(c.me.id)
    user_id = c.me.id
    
    # Fetch Userbot and Chat info for Advanced Logging
    userbot_name = "Unknown"
    try:
        if hasattr(c, "me") and c.me:
            userbot_name = f"{c.me.first_name} {c.me.last_name or ''}".strip()
    except Exception: pass

    chat_title = str(chat_id)
    chat_link = ""
    try:
        chat_obj = await c.get_chat(chat_id)
        chat_title = chat_obj.title or chat_obj.first_name or str(chat_id)
        if chat_obj.username:
            chat_link = f"https://t.me/{chat_obj.username}"
        elif chat_obj.invite_link:
            chat_link = chat_obj.invite_link
    except Exception: pass
    
    # block register task
    # Register active task
    RAP_TASKS[task_id] = {
        "task": asyncio.current_task(),
        "client_id": c.me.id,
        "chat_id": chat_id,
        "slug": slug,
        "start_time": time.time(),
        "title": title,
        "total_blocks": 0, # assigned below
        "limit": 4 # default
    }
    
    # Register with global task registry for .taskcancel support
    _x_register(task_id, asyncio.current_task(), f"🎤 Rap: {title}", "xrap_manager", uid=c.me.id, details=f"Chat: {chat_id}")
    
    # block start log
    total_blocks = len(lyrics) // lines_per_msg + (1 if len(lyrics) % lines_per_msg > 0 else 0)
    RAP_TASKS[task_id]["total_blocks"] = total_blocks
    RAP_TASKS[task_id]["title"] = title
    RAP_TASKS[task_id]["limit"] = rap_db.data["global_config"].get("send_limit_max", 4)
    await send_log(
        f"🚀 <b>Started:</b> {html.escape(title)}\n"
        f"• <b>Task ID:</b> <code>{task_id}</code>\n"
        f"• <b>Delay:</b> {delay}s | <b>Mode:</b> {mode.upper()}",
        userbot_name=userbot_name, chat_title=chat_title, chat_link=chat_link, chat_id=str(chat_id)
    )
    
    last_msg = None
    bars_sent = 0  # Counter for send limit feature (resets each cycle)
    total_bars_sent = 0  # Cumulative counter (never resets)
    send_limit_on = rap_db.data["global_config"].get("send_limit_enabled", True)
    send_limit_max = max(1, rap_db.data["global_config"].get("send_limit_max", 4))
    
    # Pre-store some task info for the inline alert handler
    # limit and title are already handled by registration or will be updated below if needed
    # block process lyrics
    try:
        for i in range(0, len(lyrics), lines_per_msg):
            chunk = lyrics[i : i + lines_per_msg]
            
            # block rhyme/markdown formatting
            # Apply formatting
            formatted_lines = []
            for line in chunk:
                f_line = rhyme_formatter(html.escape(line))
                if emoji: f_line = f"{f_line} {emoji}"
                # Apply global markdown formatting
                f_line = markdown_formatter(f_line, mtype)
                formatted_lines.append(f_line)
            
            formatted_text = "\n".join(formatted_lines)
            # Wrap in expandable blockquote for aesthetics
            formatted_text = f"<blockquote expandable>{formatted_text}</blockquote>"
            
            # block typing action
            # Typing simulation
            try: await c.send_chat_action(chat_id, enums.ChatAction.TYPING)
            except: pass
            
            # block delivery logic
            # Message Delivery
            try:
                if mode == "edit" and last_msg:
                    # block edit mode delivery
                    # ─── EDIT MODE ───
                    if inline_mode and bot_username and last_msg.via_bot:
                        # ✅ AUTHORIZED LOOPBACK: Telegram's official method for editing inline messages (via @bot)
                        # fungsi untuk menekan tombol callback otomatis agar pesan inline bisa di edit
                        # Otomatis bypass batasan Telegram dengan memicu tombol callback agar pesan inline bisa di edit
                        # ini adalah satu-satunya metode yang diizinkan oleh telegram untuk mengedit pesan inline mode (tag via@bot)
                        try:
                            # Re-instating local variable 'data' for callback with full context
                            ctx = f"_uid{user_id}_cid{chat_id}"
                            target_data = f"rapmgr_le_{slug}_{i}_{lines_per_msg}{ctx}"
                            
                            # ✅ CORE BYPASS: Trigger the bot assistant's callback automatically.
                            # Since userbots cannot edit bot messages, we trigger the bot's own callback
                            # which then performs the edit on our behalf.
                            await c.request_callback_answer(
                                chat_id, 
                                last_msg.id, 
                                callback_data=target_data
                            )
                        except Exception as loop_e:
                            if "DATA_INVALID" in str(loop_e):
                                logger.warning(f"Inline Edit Loopback failed (DATA_INVALID): falls back to Direct Edit")
                            else:
                                logger.warning(f"Inline Edit Loopback failed: {loop_e}, falling back to Direct Edit")
                                
                            try:
                                # Try one more wait if double response is suspected
                                await asyncio.sleep(0.5)
                                await last_msg.edit(formatted_text, parse_mode=enums.ParseMode.HTML)
                            except Exception as edit_fallback_e:
                                logger.debug(f"Direct edit fallback failed: {edit_fallback_e}")
                                try:
                                    last_msg = await c.send_message(chat_id, formatted_text, reply_to_message_id=reply_to_id, parse_mode=enums.ParseMode.HTML)
                                except: pass
                    else:
                        # Standard Direct Edit
                        try:
                            await last_msg.edit(formatted_text, parse_mode=enums.ParseMode.HTML)
                        except FloodWait as flood_e:
                            await asyncio.sleep(flood_e.value + 1)
                            try:
                                await last_msg.edit(formatted_text, parse_mode=enums.ParseMode.HTML)
                            except:
                                last_msg = await c.send_message(chat_id, formatted_text, reply_to_message_id=reply_to_id, parse_mode=enums.ParseMode.HTML)
                        except Exception as direct_e:
                            logger.debug(f"Standard edit failed: {direct_e}")
                            try:
                                last_msg = await c.send_message(chat_id, formatted_text, reply_to_message_id=reply_to_id, parse_mode=enums.ParseMode.HTML)
                            except: pass
                else:
                    # block reply mode delivery
                    # ─── REPLY/NEW MODE ───
                    try:
                        # Clean reply feature: Delete previous bot message before sending next
                        if clean_reply and last_msg:
                            try: await last_msg.delete()
                            except: pass
                            
                        delivered = False
                        if inline_mode and bot_username:
                            try:
                                # Re-instating character-perfect bypass logic trigger with full context
                                if mode == "edit":
                                    # Suffix _e is mandatory to trigger the callback loopback for future edits
                                    # Minified to fit within 64 byte limit
                                    inline_query = f"line_{slug}_{i}_s{lines_per_msg}_e_u{user_id}_c{chat_id}"
                                else:
                                    inline_query = f"line_{slug}_{i}_s{lines_per_msg}_u{user_id}_c{chat_id}"
                                    
                                results = await c.get_inline_bot_results(bot_username, inline_query)
                                last_msg = await c.send_inline_bot_result(
                                    chat_id, results.query_id, results.results[0].id, 
                                    reply_to_message_id=reply_to_id
                                )
                                delivered = True
                            except Exception as inline_sub_e:
                                logger.debug(f"Inline dispatch sub-error: {inline_sub_e}")
                                # Automatic fallback to direct
                        
                        if not delivered:
                            try:
                                last_msg = await c.send_message(
                                    chat_id, 
                                    formatted_text, 
                                    reply_to_message_id=reply_to_id,
                                    parse_mode=enums.ParseMode.HTML
                                )
                            except Exception as last_try_e:
                                logger.error(f"Final delivery attempt failed: {last_try_e}")
                    except Exception as fatal_delivery_e:
                        logger.error(f"Critical delivery failure: {fatal_delivery_e}")
            except FloodWait as fw_e:
                # block delivery flood wait
                logger.warning(f"FloodWait detected during delivery: {fw_e.value}s")
                await asyncio.sleep(fw_e.value + 1)
            except (ChatWriteForbidden, UserIsBlocked, PeerIdInvalid, ChannelInvalid) as fatal_e:
                # Catch critical access errors (Mute/Ban/Block)
                reason = "Muted/Restricted" if isinstance(fatal_e, ChatWriteForbidden) else "Banned/Blocked/Chat Deleted"
                await send_log(
                    f"🔴 <b>[AUTO-STOP] Access Denied:</b> {html.escape(title)}\n"
                    f"• <b>Reason:</b> <code>{reason}</code>\n"
                    f"• <b>Error:</b> <code>{type(fatal_e).__name__}</code>\n"
                    f"• <b>Status:</b> Task terminated immediately.",
                    userbot_name=userbot_name, chat_title=chat_title, chat_link=chat_link, chat_id=str(chat_id)
                )
                logger.error(f"Lyric task auto-stopped due to access denial: {fatal_e}")
                break # Exit the loop and stop the task
            except ChatAdminRequired as admin_e:
                logger.warning(f"Admin permissions missing for some actions: {admin_e}")
                # Don't break here, maybe it's just a reaction failure
            except Exception as outer_e:
                logger.error(f"Lyric processing error at line {i}: {outer_e}")

            # block reaction
            # Reaction (with error handling for disabled reactions)
            try:
                if last_msg: await last_msg.react("🔥")
            except: pass
            
            # block send limit check
            # Send Limit Confirmation
            bars_sent += 1
            total_bars_sent += 1
            if send_limit_on and bars_sent >= send_limit_max and (i + lines_per_msg < len(lyrics)):
                if not rap_db.data["global_config"].get("send_limit_alert_enabled", True):
                    # If alert is disabled, just reset and continue
                    bars_sent = 0
                else:
                    # Pause and ask for confirmation via bot assistant inline
                    try:
                        confirm_id = f"raplim_{task_id}"
                        RAP_TASKS[task_id]["waiting_confirm"] = True
                        RAP_TASKS[task_id]["confirm_event"] = asyncio.Event()
                        RAP_TASKS[task_id]["bars_sent"] = total_bars_sent
                        
                        confirm_text = (
                            "<blockquote expandable>"
                            f"⚠️ <b>Send Limit Reached</b>\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"Song: <b>{html.escape(title)}</b>\n"
                            f"Bars Sent: <code>{total_bars_sent}/{total_blocks}</code>\n"
                            f"Limit: <code>{send_limit_max}</code>\n\n"
                            f"Continue sending the next bars?"
                            "</blockquote>"
                        )
                        _user_style = get_user_button_style(c.me.id)
                        confirm_kb = InlineKeyboardMarkup([
                            [
                                InlineKeyboardButton("🛑 Stop", callback_data=f"rapmgr_lim_stop_{task_id}", style=_user_style),
                                InlineKeyboardButton("▶️ Continue", callback_data=f"rapmgr_lim_cont_{task_id}", style=_user_style)
                            ]
                        ])
                        
                        alert_sent = False
                        target_bot = _get_bot(c.me.id)
                        bot_username = None
                        try: bot_username = Altruix.bot_manager.get_bot_username(c.me.id)
                        except: pass
                        
                        if not bot_username and Altruix.bot_info:
                            bot_username = Altruix.bot_info.username

                        # 1. Inline Check (Priority: "Userbot via @Bot")
                        if bot_username:
                            try:
                                inline_query = f"rap_alert_{task_id}"
                                logger.debug(f"[RAP ALERT] Requesting inline results for {bot_username} with query: {inline_query}")
                                results = await c.get_inline_bot_results(bot_username, inline_query)
                                if results and results.results:
                                    logger.debug(f"[RAP ALERT] Inline results found, sending via userbot.")
                                    await c.send_inline_bot_result(chat_id, results.query_id, results.results[0].id, reply_to_message_id=reply_to_id)
                                    alert_sent = True
                                else:
                                    logger.warning(f"[RAP ALERT] Inline query returned 0 results for task {task_id}.")
                            except Exception as e:
                                logger.warning(f"[RAP ALERT] Inline alert dispatch failed: {e}")

                        # 2. Custom Bot (Fallback 1: Direct Message)
                        if not alert_sent and target_bot and target_bot != Altruix.bot:
                            try:
                                logger.debug(f"[RAP ALERT] Falling back to Custom Bot direct message.")
                                await target_bot.send_message(chat_id, confirm_text, reply_markup=confirm_kb, parse_mode=enums.ParseMode.HTML)
                                alert_sent = True
                            except Exception as e:
                                logger.warning(f"Custom bot alert failed: {e}")

                        # 3. Main Bot (Fallback 2: Direct Message)
                        if not alert_sent:
                            try:
                                logger.debug(f"[RAP ALERT] Falling back to Main Bot direct message.")
                                await Altruix.bot.send_message(chat_id, confirm_text, reply_markup=confirm_kb, parse_mode=enums.ParseMode.HTML)
                                alert_sent = True
                            except Exception as e:
                                logger.warning(f"Main bot direct alert failed: {e}")

                        # 4. Userbot (Final Fallback: Text Only)
                        if not alert_sent:
                            logger.info("[RAP ALERT] Final fallback to userbot (No Buttons).")
                            try:
                                await c.send_message(chat_id, confirm_text, parse_mode=enums.ParseMode.HTML)
                            except: pass
                        
                        try:
                            await asyncio.wait_for(RAP_TASKS[task_id]["confirm_event"].wait(), timeout=120)
                        except asyncio.TimeoutError:
                            await send_log(f"⏰ <b>Timeout:</b> {html.escape(title)}\nNo response within 120s. Auto-stopped.", userbot_name=userbot_name, chat_title=chat_title, chat_link=chat_link, chat_id=str(chat_id))
                            break
                        
                        # Check if user chose Stop
                        if RAP_TASKS.get(task_id, {}).get("user_stopped", False):
                            break
                        
                        # User chose Continue - reset counter
                        bars_sent = 0
                        RAP_TASKS[task_id].pop("waiting_confirm", None)
                        RAP_TASKS[task_id].pop("confirm_event", None)
                    except Exception as lim_e:
                        logger.warning(f"Limit check error: {lim_e}")

            # block loop/sleep execution
            # Wait for next line
            if i + lines_per_msg < len(lyrics):
                await asyncio.sleep(delay)
                
        # block finish log
        await send_log(f"✅ <b>Finished:</b> {html.escape(title)}\nID: <code>{task_id}</code>", userbot_name=userbot_name, chat_title=chat_title, chat_link=chat_link, chat_id=str(chat_id))
    except asyncio.CancelledError:
        # block stopped log
        await send_log(f"🛑 <b>Stopped:</b> {html.escape(title)}\nID: <code>{task_id}</code>", userbot_name=userbot_name, chat_title=chat_title, chat_link=chat_link, chat_id=str(chat_id))
    except Exception as e:
        # block error log
        await send_log(f"💥 <b>Error:</b> {html.escape(title)}\nID: <code>{task_id}</code>\nDetail: {e}", userbot_name=userbot_name, chat_title=chat_title, chat_link=chat_link, chat_id=str(chat_id))
    finally:
        # block cleanup task
        RAP_TASKS.pop(task_id, None)
        _x_unregister(task_id)

# --- COMMAND HANDLERS ---

@Altruix.register_on_cmd(
    ["rap"],
    cmd_help={
        "help": "Send rap lyrics line by line. Automatically formats rhymes with bold and spoilers.",
        "usage": ".rap <slug> [delay]",
        "example": ".rap em-god 5",
        "detail": "Slug is the unique ID for the song. Delay is optional (default is 6 seconds). Supports automated reply logic: replies to target message if command is a reply."
    },
)
# block rap command handler
# Command handler for .rap executed via standard text messages.
@iuser_check
@log_errors
async def rap_cmd_handler(c: Client, m: AltruixMessage):
    """Initiates lyric delivery from the .rap command."""
    args = m.text.split()
    target_id = get_target_id(m)
    
    if len(args) < 2:
        return await m.reply_msg(
            "❌ <b>Usage:</b> <code>.rap &lt;slug&gt; [delay]</code>\nHint: Use <code>.raplist</code> to see available slugs.",
            reply_to_message_id=target_id
        )
    
    slug = args[1].lower()
    song = rap_db.get_song(slug)
    if not song:
        return await m.reply_msg(
            f"❌ <b>Song not found:</b> <code>{slug}</code>",
            reply_to_message_id=target_id
        )
    
    delay = None
    if len(args) >= 3 and args[2].isdigit():
        delay = int(args[2])
    
    # Clean up command if it's a target-focused reply
    if m.reply_to_message:
        await m.delete()
        
    asyncio.create_task(rap_executor(c, m.chat.id, slug, delay, target_id))

@Altruix.register_on_cmd(
    ["rapstop"],
    cmd_help={
        "help": "Stop currently active rap lyric sessions.",
        "usage": ".rapstop [task_id | all]",
        "example": ".rapstop ABCDEF",
        "detail": "Use 'all' to stop every session across all accounts. If no ID is provided, it stops all sessions in the current chat for the current account."
    },
)
# block rap stop handler
@iuser_check
@log_errors
async def rap_stop_handler(c: Client, m: AltruixMessage):
    """Handles the .rapstop command to cancel ongoing lyric delivery tasks."""
    args = m.text.split()
    target_id = get_target_id(m)
    
    if len(args) < 2:
        # Default: stop sessions in current chat for current client
        stopped = 0
        for tid, data in list(RAP_TASKS.items()):
            if data["chat_id"] == m.chat.id and data["client_id"] == c.me.id:
                data["task"].cancel()
                stopped += 1
        return await m.reply_msg(f"🛑 Stopped {stopped} rap task(s) in this chat.", reply_to_message_id=target_id)
    
    target = args[1].upper()
    if target == "ALL":
        count = len(RAP_TASKS)
        for tid, data in list(RAP_TASKS.items()):
            data["task"].cancel()
        return await m.reply_msg(f"🛑 Stopped all {count} rap task(s).", reply_to_message_id=target_id)
    
    if target in RAP_TASKS:
        RAP_TASKS[target]["task"].cancel()
        return await m.reply_msg(f"🛑 Stopped task <code>{target}</code>.", reply_to_message_id=target_id)
        
    await m.reply_msg(f"❌ Task ID <code>{target}</code> not found.", reply_to_message_id=target_id)

@Altruix.register_on_cmd(
    ["raplist"],
    cmd_help={
        "help": "List all available song slugs and titles in the database.",
        "usage": ".raplist",
        "example": ".raplist"
    },
)
# block raplist handler
@iuser_check
@log_errors
async def rap_list_handler(c: Client, m: AltruixMessage):
    """Displays the list of all songs stored in the database."""
    songs = rap_db.get_all_songs()
    target_id = get_target_id(m)
    
    if not songs:
        return await m.reply_msg("📂 <b>Database is empty.</b>", reply_to_message_id=target_id)
    
    res = "📂 <b>Rap Collection:</b>\n\n"
    for i, (slug, data) in enumerate(songs.items(), 1):
        res += f"{i}. <b>{html.escape(data['title'])}</b> (<code>{slug}</code>) - {len(data['lyrics'])} lines\n"
    
    await m.reply_msg(res, reply_to_message_id=target_id)

@Altruix.register_on_cmd(
    ["rapfind"],
    cmd_help={
        "help": "Search for a song by title or slug fragments.",
        "usage": ".rapfind <query>",
        "example": ".rapfind bangkit"
    },
)
# block rapfind handler
@iuser_check
@log_errors
async def rap_find_handler(c: Client, m: AltruixMessage):
    """Searches for songs within the database using a query string."""
    target_id = get_target_id(m)
    if len(m.text.split()) < 2:
        return await m.reply_msg("❌ <b>Query required.</b>", reply_to_message_id=target_id)
    
    query = m.text.split(None, 1)[1].lower()
    songs = rap_db.get_all_songs()
    found = []
    
    for slug, data in songs.items():
        if query in slug or query in data["title"].lower():
            found.append((slug, data))
            
    if not found:
        return await m.reply_msg(f"🔍 <b>No results for:</b> <code>{query}</code>", reply_to_message_id=target_id)
        
    res = f"🔍 <b>Found {len(found)} result(s):</b>\n"
    for slug, data in found:
        res += f"• <b>{html.escape(data['title'])}</b> (<code>{slug}</code>)\n"
    await m.reply_msg(res, reply_to_message_id=target_id)

@Altruix.register_on_cmd(
    ["raprand"],
    cmd_help={
        "help": "Send a random lyric line from the collection as a quick reply.",
        "usage": ".raprand",
        "example": ".raprand",
        "detail": "Includes automated rhyme formatting and the default emoji suffix."
    },
)
# block raprand handler
@iuser_check
@log_errors
async def rap_rand_handler(c: Client, m: AltruixMessage):
    """Picks a random line from any song in the database and sends it."""
    songs = list(rap_db.get_all_songs().values())
    target_id = get_target_id(m)
    if not songs: return
    
    song = random.choice(songs)
    line = random.choice(song["lyrics"])
    
    res = rhyme_formatter(html.escape(line))
    emoji = rap_db.data["global_config"].get("default_emoji", "🔥")
    if emoji: res = f"{res} {emoji}"
    
    inline_mode = rap_db.data["global_config"].get("inline_mode", False)
    bot_username = Altruix.bot_manager.get_bot_username(c.me.id)
    
    if inline_mode and bot_username:
        try:
            # Find slug and index for the chosen line
            slug = None
            for s, d in rap_db.get_all_songs().items():
                if d["title"] == song["title"] and d["lyrics"] == song["lyrics"]:
                    slug = s
                    break
            
            if slug:
                idx = song["lyrics"].index(line)
                results = await c.get_inline_bot_results(bot_username, f"line_{slug}_{idx}")
                if results.results:
                    return await c.send_inline_bot_result(
                        m.chat.id, 
                        results.query_id, 
                        results.results[0].id, 
                        reply_to_message_id=target_id
                    )
        except Exception as e:
            logger.warning(f"Random inline delivery failed: {e}")

    await m.reply_msg(res, reply_to_message_id=target_id, parse_mode=enums.ParseMode.HTML)

@Altruix.register_on_cmd(
    ["raprefresh"],
    cmd_help={
        "help": "Force reload the lyric database from the JSON file.",
        "usage": ".raprefresh",
        "example": ".raprefresh",
        "detail": "Useful if you manually edited the JSON file and want the changes to take effect immediately."
    },
)
# block raprefresh handler
@iuser_check
@log_errors
async def rap_refresh_handler(c: Client, m: AltruixMessage):
    """Reloads the rap_db.json file into memory."""
    target_id = get_target_id(m)
    rap_db.load()
    await m.reply_msg("🔄 <b>Database reloaded from disk.</b>", reply_to_message_id=target_id)

@Altruix.register_on_cmd(
    ["rapexport"],
    cmd_help={
        "help": "Export the entire rap lyric database as a JSON file.",
        "usage": ".rapexport",
        "example": ".rapexport"
    },
)
# block rapexport handler
@iuser_check
@log_errors
async def rap_export_handler(c: Client, m: AltruixMessage):
    """Sends the rap_db.json file to the chat for backup or sharing."""
    target_id = get_target_id(m)
    if not RAP_DB_PATH.exists():
        return await m.reply_msg("❌ Database file not found.", reply_to_message_id=target_id)
    
    await m.reply_document(str(RAP_DB_PATH), caption="📂 <b>Rap Database Export</b>")

@Altruix.register_on_cmd(
    ["rapimport"],
    cmd_help={
        "help": "Import songs from a JSON file by replying to it.",
        "usage": ".rapimport (as reply)",
        "example": ".rapimport",
        "detail": "This will merge the songs from the file into your current database. Slugs that already exist will be updated."
    },
)
# block rapimport handler
@iuser_check
@log_errors
async def rap_import_handler(c: Client, m: AltruixMessage):
    """Imports or merges song data from a JSON file replied to."""
    target_id = get_target_id(m)
    if not m.reply_to_message or not m.reply_to_message.document:
        return await m.reply_msg("❌ <b>Reply to a JSON file to import.</b>", reply_to_message_id=target_id)
    
    path = await m.reply_to_message.download("DATABASE/rap_import_tmp.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            new_data = json.load(f)
            
        if "lyrics" not in new_data:
             raise ValueError("Invalid format: 'lyrics' key missing.")
             
        # Merge or overwrite? Let's overwrite as requested "menimpa/menggabungkan"
        # I'll implement merge to be safer
        rap_db.data["lyrics"].update(new_data.get("lyrics", {}))
        if "global_config" in new_data:
            rap_db.data["global_config"].update(new_data["global_config"])
            
        rap_db.save()
        await m.reply_msg(f"✅ <b>Imported {len(new_data.get('lyrics', {}))} songs.</b> Database merged successfully.", reply_to_message_id=target_id)
    except Exception as e:
        await m.reply_msg(f"❌ <b>Import failed:</b> <code>{e}</code>", reply_to_message_id=target_id)
    finally:
        if os.path.exists(path): os.remove(path)

# --- DASHBOARD & UI (.rapmanage) ---

# block generate keyboard
def generate_pagination_keyboard(items: List[Any], page: int, page_size: int, prefix: str, style = None, chat_id: int = None, user_id: int = None) -> InlineKeyboardMarkup:
    """Helper to generate a paginated inline keyboard for the dashboard lists."""
    total_pages = (len(items) + page_size - 1) // page_size
    if page < 1: page = 1
    if page > total_pages: page = total_pages
    
    start = (page - 1) * page_size
    end = start + page_size
    current_items = items[start:end]
    
    # block context encoding
    # Encode context (UID and CID) for robust callback handling across different chats.
    encoded_ctx = ""
    if user_id: encoded_ctx += f"_uid{user_id}"
    if chat_id: encoded_ctx += f"_cid{chat_id}"
    
    buttons = []
    for item in current_items:
        # Expected item: (slug, title)
        slug, title = item
        # 🔘 Triple-fallback for Copy Button (Native -> String -> Callback)
        copy_btn = None
        # ✅ FIX: Telegram has a 256 character limit for keyboardButtonCopy.copy_text
        if len(slug) <= 256:
            try:
                # 1. Native CopyTextButton (Pyrogram 2.4+)
                from pyrogram.types import CopyTextButton
                copy_btn = InlineKeyboardButton("Copy", copy_text=CopyTextButton(text=slug), style=style)
            except (ImportError, TypeError):
                try:
                    # 2. String-based copy_text (Older Pyrogram/Kurigram)
                    copy_btn = InlineKeyboardButton("Copy", copy_text=slug, style=style)
                except Exception:
                    # 3. Last resort: internal callback for manual copy
                    copy_btn = InlineKeyboardButton("Copy", callback_data=f"{prefix}_copyslug_{slug}{encoded_ctx}", style=style)
        else:
             # Fallback to last resort for long slugs
             copy_btn = InlineKeyboardButton("Copy", callback_data=f"{prefix}_copyslug_{slug}{encoded_ctx}", style=style)


        buttons.append([
            InlineKeyboardButton(f"🎵 {title[:16]} ({slug[:10]})", callback_data=f"{prefix}_edit_{slug}{encoded_ctx}", style=style),
            copy_btn
        ])
    
    # Navigation controls
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("«", callback_data=f"{prefix}_page_{page-1}{encoded_ctx}", style=style))
    nav.append(InlineKeyboardButton(f"{page}/{max(1, total_pages)}", callback_data="noop", style=style))
    if page < total_pages:
        nav.append(InlineKeyboardButton("»", callback_data=f"{prefix}_page_{page+1}{encoded_ctx}", style=style))
    
    buttons.append(nav)
    buttons.append([
        InlineKeyboardButton("➕ Add New", callback_data=f"{prefix}_add{encoded_ctx}", style=style),
        InlineKeyboardButton("📂 Export", callback_data=f"{prefix}_export{encoded_ctx}", style=style),
        InlineKeyboardButton("📥 Import", callback_data=f"{prefix}_import{encoded_ctx}", style=style)
    ])
    buttons.append([
        InlineKeyboardButton("⚙️ Settings", callback_data=f"{prefix}_settings{encoded_ctx}", style=style),
        InlineKeyboardButton("🔄 Refresh", callback_data=f"{prefix}_refresh{encoded_ctx}", style=style),
        InlineKeyboardButton("❌ Close", callback_data=f"{prefix}_close", style=style)
    ])
    return InlineKeyboardMarkup(buttons)

@Altruix.register_on_cmd(
    ["rapmanage"],
    cmd_help={
        "help": "Open the interactive Rap Manager Dashboard for full CRUD operations.",
        "usage": "rapmanage",
        "example": "rapmanage"
    },
)
# block manage entry command
@iuser_check
@log_errors
async def rap_manage_cmd_handler(c: Client, m: AltruixMessage):
    """Command entry point for launching the dashboard."""
    return await rap_manage_handler(c, m=m)

# block dashboard UI handler
async def rap_manage_handler(c: Client, m: Optional[AltruixMessage] = None, user_id: int = None, chat_id: int = None):
    """Internal logic for launching/refreshing the dashboard UI."""
    # Resolve identities safely
    user_id = user_id or (getattr(m.from_user, 'id', None) if m else c.me.id)
    chat_id = chat_id or (getattr(m.chat, 'id', None) if m else user_id)
    
    # block identify userbot
    # ✅ CRITICAL: Identify the Userbot (Owner) session. 
    # Dashboard must be sent by Userbot via Assistant Bot as an inline builder.
    userbot = None
    for cli in Altruix.clients:
        if cli.me.id == user_id:
            userbot = cli
            break
    
    # Fallback to current client or bot manager
    userbot = userbot or Altruix.bot_manager.get_bot(user_id) or c
    bot_assistant = Altruix.bot_manager.get_bot(user_id)
    bot_username = Altruix.bot_manager.get_bot_username(user_id)
    
    # ─── 0. Generate Song List Early ───
    songs = rap_db.get_all_songs()
    items = [(slug, data["title"]) for slug, data in songs.items()]
    target_id = get_target_id(m) if m else None
    user_style = get_user_button_style(user_id)

    # ─── 1. Determine Target Chat ───
    target_chat = chat_id
    if m and bot_assistant and (m.chat.type == enums.ChatType.BOT or m.chat.id == bot_assistant.me.id):
        target_chat = user_id
    
    # block try inline dashboard
    # ─── 2. Try Inline Mode First (Works in ANY chat) ───
    try:
        if bot_username:
            # ✅ FIX: Encode context. We use userbot (Owner) to fetch results.
            cur_chat = m.chat.id if m else chat_id
            query_str = f"rap_manage_uid_{user_id}_pg1_sz6_cid_{cur_chat}"
            results = await userbot.get_inline_bot_results(bot_username, query_str)
            
            if results.results:
                # Userbot sends the result, appearing as "via @bot"
                await userbot.send_inline_bot_result(
                    chat_id,
                    results.query_id,
                    results.results[0].id,
                    reply_to_message_id=target_id
                )
                if m: await m.delete_if_self()
                return
    except Exception as e:
        logger.warning(f"Rap Manager inline dashboard failed: {e}, falling back to direct message")

    # block fallback direct dashboard
    # ─── 3. Fallback to Direct Bot Message ───
    
    text = (
        f"<blockquote expandable>"
        f"🎤 <b>Userbot Rap Manager</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Total Songs: <b>{len(items)}</b>\n"
        f"Storage Mode: <code>{rap_db.data['global_config'].get('mode', 'reply').upper()}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Select a song to edit or tap 'Add New' to create one:"
        f"</blockquote>"
    )
    # ✅ REUSE generate_pagination_keyboard with page_size=6 and explicit chat_id
    kb = generate_pagination_keyboard(items, 1, 6, "rapmgr", style=user_style, chat_id=chat_id, user_id=user_id)
    
    try:
        # We send to 'target_chat' to avoid USER_IS_BOT error in bot-PMs
        # Use Bot Assistant session for fallback UI messages
        await bot_assistant.send_message(
            target_chat, 
            text, 
            reply_markup=kb,
            reply_to_message_id=target_id if m and m.chat.type != enums.ChatType.PRIVATE and target_chat == m.chat.id else None
        )
    except Exception as e:
        if m: await m.edit(f"❌ <b>Bot Assistant Error:</b> {e}\n\nHint: Use `@bot` inline search if the bot is not in this chat.")
        return

    if m: await m.delete_if_self()

# block callback query handler
# Primary handler for processing all dashboard callback buttons.
# ✅ CRITICAL FIX: The dashboard is sent via Bot Assistant, so we MUST listen on Altruix.bot
@Altruix.bot.on_callback_query(filters.regex(r"^rapmgr_"))
@iuser_check
@log_errors
async def rapmgr_cb_handler(c: Client, cb: CallbackQuery):
    """
    Processes all callback queries originating from the Rap Manager dashboard.
    Manages state persistence and UI updates for both regular and inline modes.
    """
    # block extract callback data
    # ─── EXTRACT DATA ───
    # Format: rapmgr_{action}[_uid{uid}][_cid{cid}]
    full_data = cb.data
    clicker_id = cb.from_user.id
    owner_id = clicker_id # Default
    
    # ─── EXTRACT CONTEXT (UID & CID) ───
    uid_match = re.search(r"_uid(\d+)", full_data)
    cid_match = re.search(r"_cid(-?\d+)", full_data)
    
    if uid_match:
        owner_id = int(uid_match.group(1))
    
    chat_id = int(cid_match.group(1)) if cid_match else (cb.message.chat.id if cb.message else owner_id)
    
    # Cleanup data for main action branches
    data = full_data.replace("rapmgr_", "")
    data = re.sub(r"_uid\d+", "", data)
    data = re.sub(r"_cid-?\d+", "", data)
    
    # Use owner_id for all database and session-specific logic
    user_id = owner_id
    
    # ✅ FIX: Use userbot (bot assistant) for UI/Interactive flows
    userbot = Altruix.bot_manager.get_bot(user_id) or c
    
    # ✅ REAL USERBOT (Client session) for file sending and userbot-only actions
    real_userbot = None
    for cli in Altruix.clients:
        if cli.me.id == user_id:
            real_userbot = cli
            break
    
    # ✅ HELPERS FOR SESSION-AWARE NOTIFICATIONS
    bot_username = getattr(c.me, 'username', 'Bot')
    bot_mention = f"@{bot_username}"
    user_pm_id = user_id # Always use user_id for PM prompts

    # ✅ CORE REFINEMENT: Ensure session context is preserved in all buttons
    def inject_context(kb):
        if not kb: return kb
        ctx = f"_uid{user_id}_cid{chat_id}"
        for row in kb.inline_keyboard:
            for btn in row:
                if btn.callback_data and btn.callback_data.startswith("rapmgr_"):
                    # Remove existing context if any to avoid duplication/limit issues
                    c_data = re.sub(r"_uid\d+", "", btn.callback_data)
                    c_data = re.sub(r"_cid-?\d+", "", c_data)
                    # Limit check: Telegram callback data limit is 64 bytes
                    new_data = c_data + ctx
                    if len(new_data) > 64:
                        # If too long, we might need to use a shorter indicator or fallback
                        # For now, we trust slugs are reasonable
                        btn.callback_data = new_data
                    else:
                        btn.callback_data = new_data
        return kb

    # Helper for navigation or return
    # block edit_or_send utility
    # ✅ DEFINITIVE FIX: Use cb.edit_message_text() directly — identical to gcast's safe_edit_message.
    # Pyrogram's CallbackQuery.edit_message_text() automatically routes to inline or regular editing
    # based on whether cb.inline_message_id is set. No manual routing needed.
    async def edit_or_send(text, kb=None):
        kb = inject_context(kb)
        try:
            # ✅ KEY: cb.edit_message_text() works for BOTH regular and inline mode messages.
            # When the dashboard is sent via @bot in a group (inline mode),
            # cb.message is None but cb.inline_message_id is set.
            # Pyrogram handles this transparently when calling cb.edit_message_text().
            return await cb.edit_message_text(
                text,
                reply_markup=kb,
                parse_mode=enums.ParseMode.HTML
            )
        except MessageNotModified:
            pass  # Content unchanged — no action needed
        except Exception as e:
            logger.warning(f"edit_or_send failed [{type(e).__name__}]: {e}")
            # Fallback: send a new message to the chat (only valid in non-inline context)
            if cb.message:
                try:
                    await c.send_message(chat_id, text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
                except Exception as send_e:
                    logger.debug(f"Fallback send_message also failed: {send_e}")

    # ✅ ANSWER CALLBACK EARLY to stop spinner
    # Exceptions for actions that send their own custom callback answers (notifs/alerts)
    if data not in ["set_mode", "set_inline", "refresh", "export"] and not data.startswith(("lim_stop_", "lim_cont_", "stop_")):
        try: await cb.answer()
        except: pass
    
    # ✅ REFRESH STYLE FOR SESSION-SPECIFIC OR GLOBAL
    # We use a helper to get consistent style across interactions
    user_style = get_user_button_style(user_id)
    
    # Dashboard from Session Info Entry
    if data.startswith("dashboard_"):
        parts = data.split("_")
        idx, pg = int(parts[1]), int(parts[2])
        # Force session-specific style if accessed from session info
        if idx < len(Altruix.clients):
             s_me = Altruix.clients[idx].me
             if s_me: user_style = get_user_button_style(s_me.id)
             
        songs = rap_db.get_all_songs()
        items = [(slug, data["title"]) for slug, data in songs.items()]
        text = (
            f"<blockquote expandable>"
            f"🎤 <b>Userbot Rap Manager</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Total Songs: <b>{len(items)}</b>\n"
            f"Storage Mode: <code>{rap_db.data['global_config'].get('mode', 'reply').upper()}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Select a song to edit or tap 'Add New' to create one:"
            f"</blockquote>"
        )
        kb = generate_pagination_keyboard(items, 1, 6, "rapmgr", style=user_style, chat_id=chat_id, user_id=user_id)
        
        # Add a back button to return to session info
        buttons = kb.inline_keyboard
        buttons.append([InlineKeyboardButton("« Back to Session Info", callback_data=f"session_info_{idx}_{pg}_5", style=user_style)])
        
        await edit_or_send(text, InlineKeyboardMarkup(buttons))
        return

    # block dashboard page handler
    # Pagination Handling (Song List)
    if data.startswith("page_"):
        page = int(data.split("_")[1])
        songs = rap_db.get_all_songs()
        items = [(slug, data["title"]) for slug, data in songs.items()]
        
        # ✅ FIX: Ensure text is reset when returning to main list
        text = (
            f"<blockquote expandable>"
            f"🎤 <b>Userbot Rap Manager</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Total Songs: <b>{len(items)}</b>\n"
            f"Storage Mode: <code>{rap_db.data['global_config'].get('mode', 'reply').upper()}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Select a song to edit or tap 'Add New' to create one:"
            f"</blockquote>"
        )
        kb = generate_pagination_keyboard(items, page, 6, "rapmgr", style=user_style, chat_id=chat_id, user_id=user_id)
        await edit_or_send(text, kb)
        return
        
    # block refresh callback
    # Refresh Logic
    elif data == "refresh":
        if not cb.message:
            await cb.answer("🔄 [REFRESH]\nDatabase items refreshed in this menu.", show_alert=True)
            
        rap_db.load()
        songs = rap_db.get_all_songs()
        items = [(slug, data["title"]) for slug, data in songs.items()]
        kb = generate_pagination_keyboard(items, 1, 6, "rapmgr", style=user_style, chat_id=chat_id, user_id=user_id)
        await cb.edit_message_reply_markup(inject_context(kb))
        if cb.message: await cb.answer("🔄 Database refreshed.")
        
    # block close dashboard
    # Close Menu
    elif data == "close":
        try:
            if cb.message: 
                await cb.message.delete()
            elif cb.inline_message_id:
                if hasattr(c, "edit_inline_text"):
                    await c.edit_inline_text(inline_message_id=cb.inline_message_id, text="👋 Dashboard Closed.")
                else:
                    try:
                        await c.edit_message_text(None, None, "👋 Dashboard Closed.", cb.inline_message_id)
                    except:
                        await c.edit_message_text(inline_message_id=cb.inline_message_id, text="👋 Dashboard Closed.")
        except:
            pass
        
    # block add song flow
    # Create Song Flow (Interactive Conversation)
    elif data == "add":
        await cb.answer(f"✅ Add New List Song (check your PM bot assistant)", show_alert=True)
        # Conversation mode for adding a song
        if not cb.message:
            await cb.answer(f"✨ [CREATE MODE]\nPlease check your PM with {bot_mention} to continue.", show_alert=True)
        
        if cb.message: await cb.message.delete()
        try:
            # 1. Ask for slug - ALWAYS in PM
            prompt1 = await userbot.send_message(user_pm_id, f"✨ [<b>CREATE MODE</b>]\n\nType the <b>Slug</b> for the new song (e.g. <code>em-god</code>):\n(Type <code>/cancel</code> to stop)\n\n<i>This prompt is from {bot_mention}</i>")
            res1 = await userbot.listen(chat_id=user_pm_id, filters=filters.text & filters.user(user_id), timeout=60)
            if res1.text.lower() == "/cancel":
                await res1.delete()
                await prompt1.edit("🛑 <b>Creation cancelled.</b>")
                return await rap_manage_handler(c, user_id=user_id, chat_id=chat_id)
            slug = res1.text.lower().strip().replace(" ", "-")
            # ✅ Keep user input as requested
            
            # 2. Ask for title
            await prompt1.edit("✨ [<b>CREATE MODE</b>]\n\nType the <b>Title</b> for the lyrics:\n(Type <code>/cancel</code> to stop)")
            res2 = await userbot.listen(chat_id=chat_id, filters=filters.text & filters.user(user_id), timeout=60)
            if res2.text.lower() == "/cancel":
                await res2.delete()
                await prompt1.edit("🛑 <b>Creation cancelled.</b>")
                return await rap_manage_handler(c, user_id=user_id, chat_id=chat_id)
            title = res2.text.strip()
            # ✅ Keep user input as requested
            
            # 3. Ask for lyrics
            await prompt1.edit("✨ [<b>CREATE MODE</b>]\n\nPaste the <b>Lyrics</b> (Split each line by newline):\n(Type <code>/cancel</code> to stop)")
            res3 = await userbot.listen(chat_id=chat_id, filters=filters.text & filters.user(user_id), timeout=300)
            if res3.text.lower() == "/cancel":
                await res3.delete()
                await prompt1.edit("🛑 <b>Creation cancelled.</b>")
                return await rap_manage_handler(c, user_id=user_id, chat_id=chat_id)
            lyrics = [line.strip() for line in res3.text.split("\n") if line.strip()]
            # ✅ Keep user input as requested
            
            if not lyrics:
                return await prompt1.edit("❌ <b>Creation failed:</b> No lyrics provided.")
            
            rap_db.add_song(slug, title, lyrics)
            await prompt1.edit(f"✅ <b>Song added!</b>\nSlug: <code>{slug}</code>\nTitle: <b>{title}</b>\nLines: {len(lyrics)}")
            # Show dashboard again via bot
            await rap_manage_handler(c, user_id=user_id, chat_id=chat_id)
        except Exception as e:
            await c.send_message(chat_id, f"❌ <b>Process Interrupted:</b> {e}")

    # block edit song menu
    # Song Detail/Edit Menu
    elif data.startswith("edit_"):
        slug = data.replace("edit_", "")
        song = rap_db.get_song(slug)
        if not song: return await cb.answer("Song not found.", show_alert=True)
        
        text = (
            f"<blockquote expandable>"
            f"🎵 <b>Editing</b>\n"
            f"Title: <code>{song['title']}</code>\n"
            f"Slug: <code>{slug}</code>\n"
            f"Lines: {len(song['lyrics'])}\n\n"
            f"Select an operation for this song:"
            f"</blockquote>"
        )
        
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"📄 View Full Lyrics", callback_data=f"rapmgr_view_{slug}_0", style=user_style)],
            [InlineKeyboardButton("📝 Edit Title", callback_data=f"rapmgr_etitle_{slug}", style=user_style),
             InlineKeyboardButton("📝 Edit Lyrics", callback_data=f"rapmgr_elyrics_{slug}", style=user_style)],
            [InlineKeyboardButton("📝 Edit Slug", callback_data=f"rapmgr_slugedit_{slug}", style=user_style)],
            [InlineKeyboardButton("🗑 Delete", callback_data=f"rapmgr_delconf_{slug}", style=user_style)],
            [InlineKeyboardButton("⬅️ Back", callback_data="rapmgr_page_1", style=user_style)]
        ])
        await edit_or_send(text, kb)

    # block edit title flow
    elif data.startswith("etitle_"):
        slug = data.replace("etitle_", "")
        song = rap_db.get_song(slug)
        if not song: return
        
        if not cb.message:
            await cb.answer(f"📝 [EDIT TITLE]\nPlease check your PM with {bot_mention} to enter the new title.", show_alert=True)
            
        if cb.message: await cb.message.delete()
        try:
            prompt = await userbot.send_message(user_pm_id, f"📝 [<b>EDIT TITLE</b>]\nSong: <code>{slug}</code>\n\nEnter the new title:\n(Type <code>/cancel</code> to stop)\n\n<i>Check {bot_mention} for input</i>")
            res = await userbot.listen(chat_id=user_pm_id, filters=filters.text & filters.user(user_id), timeout=60)
            if res.text.lower() == "/cancel":
                await res.delete()
                await prompt.edit("🛑 <b>Edit cancelled.</b>")
                try: return await rap_manage_handler(c, user_id=user_id, chat_id=chat_id)
                except: pass
            new_title = res.text.strip()
            # ✅ Keep user input as requested
            
            song["title"] = new_title
            rap_db.save()
            await prompt.edit(f"✅ Title updated to: <b>{new_title}</b>")
            await asyncio.sleep(2)
            try: return await rap_manage_handler(c, user_id=user_id, chat_id=chat_id)
            except: pass
        except Exception as e:
            await edit_or_send(f"❌ Error: {e}")

    # block edit lyrics flow
    elif data.startswith("elyrics_"):
        slug = data.replace("elyrics_", "")
        song = rap_db.get_song(slug)
        if not song: return
        
        if not cb.message:
            await cb.answer(f"📜 [EDIT LYRICS]\nPlease check your PM with {bot_mention} to paste new lyrics.", show_alert=True)
        
        if cb.message: await cb.message.delete()
        try:
            prompt = await userbot.send_message(user_pm_id, f"📝 [<b>EDIT LYRICS</b>]\nSong: <b>{song['title']}</b>\n\nPaste the new lyrics (newline separated):\n(Type <code>/cancel</code> to stop)\n\n<i>Check {bot_mention} for input</i>")
            res = await userbot.listen(chat_id=user_pm_id, filters=filters.text & filters.user(user_id), timeout=300)
            if res.text.lower() == "/cancel":
                await res.delete()
                await prompt.edit("🛑 <b>Edit cancelled.</b>")
                try: return await rap_manage_handler(c, user_id=user_id, chat_id=chat_id)
                except: pass
            new_lyrics = [line.strip() for line in res.text.split("\n") if line.strip()]
            # ✅ Keep user input as requested
            
            if not new_lyrics:
                return await prompt.edit("❌ No lyrics provided.")
                
            song["lyrics"] = new_lyrics
            rap_db.save()
            await prompt.edit(f"✅ Lyrics updated! ({len(new_lyrics)} lines)")
            await asyncio.sleep(2)
            try: return await rap_manage_handler(c, user_id=user_id, chat_id=chat_id)
            except: pass
        except Exception as e:
            await edit_or_send(f"❌ Error: {e}")

    # block copy slug helper
    elif data.startswith("copyslug_"):
        slug = data.replace("copyslug_", "").strip()
        # Remove context if present
        if "_cid" in slug: slug = slug.split("_cid")[0]
        if "_uid" in slug: slug = slug.split("_uid")[0]
        
        # 🟢 Priority 1: Answer with the slug in an alert (fastest)
        await cb.answer(f"📋 Slug: {slug}", show_alert=True)
        
        # 🟢 Priority 2: Send a copyable message
        try:
            # We use a clear blockquote and code tag for easy mobile copying
            copy_msg = (
                f"📋 <b>Slug ready to copy:</b>\n"
                f"<code>{slug}</code>\n\n"
                f"<i>Tap the text above to copy it quickly.</i>"
            )
            # Send to the current interaction chat (PM or Group)
            await c.send_message(chat_id, copy_msg)
        except: 
            pass


    # block view lyrics flow
    # Paginated Lyric Viewer
    elif data.startswith("view_"):
        # Format: view_{slug}_{page}
        parts = data.split("_")
        slug = parts[1]
        page = int(parts[2]) if len(parts) > 2 else 0
        
        song = rap_db.get_song(slug)
        if not song: return await cb.answer("Song not found.", show_alert=True)
        
        full_lyrics = "\n".join(song["lyrics"])
        page_size = 400
        total_pages = (len(full_lyrics) + page_size - 1) // page_size
        
        start_idx = page * page_size
        end_idx = start_idx + page_size
        page_text = full_lyrics[start_idx:end_idx]
        
        text = (
            f"📖 <b>Lyric Viewer:</b> {song['title']}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Page: <b>{page + 1} / {max(1, total_pages)}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<blockquote expandable>{html.escape(page_text)}</blockquote>"
        )
        
        # Navigation buttons
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("«", callback_data=f"rapmgr_view_{slug}_{page-1}", style=user_style))
        if end_idx < len(full_lyrics):
            nav_buttons.append(InlineKeyboardButton("»", callback_data=f"rapmgr_view_{slug}_{page+1}", style=user_style))
            
        kb_list = [nav_buttons] if nav_buttons else []
        kb_list.append([InlineKeyboardButton("« Back to Song", callback_data=f"rapmgr_edit_{slug}", style=user_style)])
        
        await edit_or_send(text, InlineKeyboardMarkup(kb_list))

    # block delete confirmation
    # Delete Confirmation
    elif data.startswith("delconf_"):
        slug = data.replace("delconf_", "")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Yes, Delete", callback_data=f"rapmgr_delyes_{slug}", style=user_style)],
            [InlineKeyboardButton("❌ No, Cancel", callback_data=f"rapmgr_edit_{slug}", style=user_style)]
        ])
        await edit_or_send(f"⚠️ <b>Are you sure you want to delete</b> <code>{slug}</code>?", kb)

    # block delete execution
    # Delete Execution
    elif data.startswith("delyes_"):
        slug = data.replace("delyes_", "")
        rap_db.delete_song(slug)
        await cb.answer(f"🗑 Deleted {slug}", show_alert=True)
        # Back to main list
        songs = rap_db.get_all_songs()
        items = [(slug, data["title"]) for slug, data in songs.items()]
        kb = generate_pagination_keyboard(items, 1, 6, "rapmgr", style=user_style, chat_id=chat_id, user_id=user_id)
        await edit_or_send("📂 <b>Rap Collection:</b>", kb)

    # block export execution
    # Interactive Export
    elif data == "export":
        try:
            if not RAP_DB_PATH.exists():
                logger.error(f"Export failed: Database file not found at {RAP_DB_PATH}")
                return await cb.answer("❌ Database file not found.", show_alert=True)
            
            await cb.answer("📂 Exporting database...", show_alert=False)
            
            # Use Absolute Path for reliable sending
            abs_path = str(RAP_DB_PATH.absolute())
            export_caption = f"📂 <b>Rap Database Export</b> (v{PLUGIN_VERSION})\n👤 Admin: <code>{user_id}</code>"
            
            # 1) Figure out Target Chat (Help.py Pattern: chat tempat tombol ditekan)
            target_chat = None
            # Prioritas 1: Chat tempat message inline berada (group/channel/personal)
            if cb.message and cb.message.chat:
                target_chat = cb.message.chat.id
            # Prioritas 2: cid dari callback data (jika ada)
            elif chat_id and str(chat_id) != "None":
                target_chat = chat_id
            # Fallback: PM user yang menekan tombol
            else:
                target_chat = cb.from_user.id
            
            logger.info(f"Export: Preparing to send database to {target_chat} (uid: {user_id})")
                
            # 2) Figure out Sender Client (Strict Session Isolation)
            sender_client = None
            
            # ✅ STRICT: Hanya gunakan userbot yang TEPAT match dengan user_id
            # TIDAK BOLEH fallback ke Altruix.clients[0] agar tidak bocor ke session lain
            for cl in Altruix.clients:
                me = getattr(cl, "me", None) or getattr(cl, "myself", None)
                if me and me.id == user_id:
                    sender_client = cl
                    logger.debug(f"Export: Using userbot matched by user_id {user_id}")
                    break
            
            if not sender_client:
                logger.warning(f"Export: Userbot session {user_id} not found, using Bot Assistant")
                sender_client = Altruix.bot
            
            # ✅ FIX: Jika userbot mengirim ke dirinya sendiri (Saved Messages),
            # gunakan "me" agar Pyrogram tidak hang saat resolve peer numeric ID self.
            send_target = target_chat
            if sender_client != Altruix.bot:
                sender_me = getattr(sender_client, "me", None)
                if sender_me and sender_me.id == target_chat:
                    send_target = "me"
                    logger.debug(f"Export: Sending to self, using 'me' instead of numeric ID")
            
            # 3) Execute Send Fallback Chain (Help.py Pattern)
            try:
                await sender_client.send_document(
                    chat_id=send_target,
                    document=abs_path,
                    caption=f"<blockquote expandable>{export_caption}</blockquote>"
                )
                await cb.answer("✅ Database berhasil diexport!", show_alert=True)
            except Exception as send_err:
                logger.warning(f"Primary export via {type(sender_client).__name__} failed: {send_err}")
                # Fallback to Bot Assistant if Userbot fails (e.g., PeerIdInvalid)
                if sender_client != Altruix.bot:
                    try:
                        await Altruix.bot.send_document(
                            chat_id=target_chat,
                            document=abs_path,
                            caption=f"<blockquote expandable>{export_caption}</blockquote>\n\n<blockquote expandable><i>(Sent via Bot Fallback)</i></blockquote>"
                        )
                        await cb.answer("✅ Export dikirim via Bot Assistant!", show_alert=True)
                    except Exception as bot_err:
                        logger.error(f"Bot fallback export also failed: {bot_err}")
                        await cb.answer(f"❌ Export failed: {str(bot_err)[:50]}", show_alert=True)
                else:
                    logger.error(f"Primary bot export failed: {send_err}")
                    await cb.answer(f"❌ Export failed: {str(send_err)[:50]}", show_alert=True)
                    
        except Exception as outer_exp_e:
             logger.error(f"Export logic fatal error: {outer_exp_e}")
             await cb.answer(f"❌ Critical error during export.", show_alert=True)

    # block slug edit flow
    # Slug Editing Flow
    elif data.startswith("slugedit_"):
        slug = data.replace("slugedit_", "")
        song = rap_db.get_song(slug)
        if not song: return
        
        await edit_or_send(
            f"📝 [<b>SLUG EDIT</b>]\n\n"
            f"Song: <b>{song['title']}</b>\n"
            f"Current Slug: <code>{slug}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Type the <b>New Slug</b> (no spaces, e.g., <code>song-new</code>):\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Type <code>/cancel</code> to stop.",
            InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=f"rapmgr_edit_{slug}", style=user_style)]])
        )
        try:
            # ✅ PM Redirection
            if not cb.message:
                await cb.answer(f"📝 [SLUG EDIT]\nPlease check your PM with {bot_mention} to enter the new slug.", show_alert=True)
            if cb.message: await cb.message.delete()

            prompt = await userbot.send_message(user_pm_id, f"📝 [<b>SLUG EDIT</b>]\nSong: <b>{song['title']}</b>\n\nEnter new slug:\n(Type <code>/cancel</code> to stop)\n\n<i>Check {bot_mention} for input</i>")
            res = await userbot.listen(chat_id=user_pm_id, filters=filters.text & filters.user(user_id), timeout=60)
            
            # If the userbot session catches the message:
            if res.text.lower() == "/cancel":
                await res.delete()
                try: return await rap_manage_handler(c, user_id=user_id, chat_id=chat_id)
                except: pass
            
            new_slug = res.text.lower().strip().replace(" ", "-")
            if rap_db.get_song(new_slug):
                 return await userbot.send_message(user_pm_id, f"❌ <b>Slug '{new_slug}' already exists.</b>")
            
            if rap_db.rename_slug(slug, new_slug):
                 await userbot.send_message(user_pm_id, f"✅ <b>Slug renamed:</b> <code>{slug}</code> ➡️ <code>{new_slug}</code>")
                 try: return await rap_manage_handler(c, user_id=user_id, chat_id=chat_id)
                 except: pass
            else:
                 await userbot.send_message(user_pm_id, f"❌ Failed to rename slug.")
        except Exception as e:
            await userbot.send_message(user_pm_id, f"🛑 <b>Slug edit failed:</b> {e}")

    # block import file request
    # Interactive Import (Step 1: Request File)
    elif data == "import":
        await edit_or_send(
            "📥 [<b>IMPORT MODE</b>]\n\n"
            "Please <b>Reply</b> to a Rap Manager JSON file to import.\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ <i>This will merge the new songs into your existing list.</i>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Type <code>/cancel</code> to stop.",
            InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="rapmgr_page_1", style=user_style)]])
        )
        # ✅ PM Redirection Alert
        if not cb.message:
             await cb.answer(f"📥 [IMPORT]\nPlease check your PM with {bot_mention} to upload the file.", show_alert=True)

        try:
            res = await userbot.listen(chat_id=user_pm_id, filters=filters.document & filters.user(user_id), timeout=300)
            if not res or not res.document: 
                return await edit_or_send("❌ <b>Import failed:</b> No document found.")
            
            # Temporary path
            path = await res.download(f"DATABASE/imp_{generate_task_id()}.json")
            
            # Show confirmation
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Yes, Import", callback_data=f"rapmgr_impyes_{os.path.basename(path)}", style=user_style)],
                [InlineKeyboardButton("❌ No, Cancel", callback_data="rapmgr_page_1", style=user_style)]
            ])
            await edit_or_send(
                f"📂 <b>File Received:</b> <code>{res.document.file_name}</code>\n"
                f"Size: <code>{res.document.file_size} bytes</code>\n\n"
                f"<b>Are you sure you want to import/merge these songs?</b>",
                kb
            )
        except Exception as e:
            await edit_or_send(f"🛑 <b>Import cancelled or failed:</b> {e}")

    # block import execution
    # Interactive Import (Step 2: Execution)
    elif data.startswith("impyes_"):
        filename = data.replace("impyes_", "")
        path = os.path.join("DATABASE", filename)
        
        if not os.path.exists(path):
            return await cb.answer("❌ Import file lost. Please try again.", show_alert=True)
            
        try:
            with open(path, "r", encoding="utf-8") as f:
                new_data = json.load(f)
            
            if "lyrics" not in new_data:
                raise ValueError("Invalid format: 'lyrics' key missing.")
                
            count = len(new_data.get("lyrics", {}))
            rap_db.data["lyrics"].update(new_data.get("lyrics", {}))
            if "global_config" in new_data:
                rap_db.data["global_config"].update(new_data["global_config"])
            
            rap_db.save()
            await edit_or_send(f"✅ <b>Successfully imported {count} songs!</b>")
            await asyncio.sleep(2)
            try: return await rap_manage_handler(c, user_id=user_id, chat_id=chat_id)
            except: pass
        except Exception as e:
            await edit_or_send(f"❌ <b>Import failed:</b> <code>{e}</code>")
        finally:
            if os.path.exists(path): os.remove(path)

    # block global settings menu
    # Global Settings Menu
    elif data == "settings":
        g_cfg = rap_db.data["global_config"]
        text = (
            f"⚙️ <b>Global Rap Settings</b>\n"
            f"<blockquote expandable>━━━━━━━━━━━━━━━━━━━━\n"
            f"Default Delay: <b>{g_cfg.get('default_delay', 6)}s</b>\n"
            f"Default Emoji: <b>{g_cfg.get('default_emoji', '🔥')}</b>\n"
            f"Lines per Message: <b>{g_cfg.get('lines_per_msg', 2)}</b>\n"
            f"Markdown Type: <b>{g_cfg.get('markdown_type', 'None')}</b>\n"
            f"Response Mode: <b>{g_cfg.get('mode', 'reply').upper()}</b>\n"
            f"Inline Support: <b>{'ON' if g_cfg.get('inline_mode', False) else 'OFF'}</b>\n"
            f"Clean Reply: <b>{'ON' if g_cfg.get('clean_reply', False) else 'OFF'}</b>\n"
            f"Send Bars Limit: <b>{'ON' if g_cfg.get('send_limit_enabled', True) else 'OFF'}</b> (Max: <b>{g_cfg.get('send_limit_max', 4)}</b> bars)\n"
            f"Limit Alert: <b>{'ON' if g_cfg.get('send_limit_alert_enabled', True) else 'OFF'}</b></blockquote>"
        )
        
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"⏱ Delay: {g_cfg.get('default_delay', 6)}s", callback_data="rapmgr_set_delay", style=user_style),
             InlineKeyboardButton(f"🎭 Mode: {g_cfg.get('mode', 'reply').upper()}", callback_data="rapmgr_set_mode", style=user_style)],
            [InlineKeyboardButton(f"✨ Emoji: {g_cfg.get('default_emoji', '🔥') or 'None'}", callback_data="rapmgr_set_emoji", style=user_style),
             InlineKeyboardButton(f"🎨 Style: {g_cfg.get('markdown_type', 'None')}", callback_data="rapmgr_set_markdown", style=user_style)],
            [InlineKeyboardButton(f"📜 Lines: {g_cfg.get('lines_per_msg', 2)}", callback_data="rapmgr_set_lines", style=user_style),
             InlineKeyboardButton(f"🤖 Inline: {'ON' if g_cfg.get('inline_mode', False) else 'OFF'}", callback_data="rapmgr_set_inline", style=user_style)],
            [InlineKeyboardButton(f"🧹 Clean Reply: {'ON' if g_cfg.get('clean_reply', False) else 'OFF'}", callback_data="rapmgr_set_clean", style=user_style),
             InlineKeyboardButton(f"🔔 Alert: {'ON' if g_cfg.get('send_limit_alert_enabled', True) else 'OFF'}", callback_data="rapmgr_set_slimit_alert", style=user_style)],
            [InlineKeyboardButton(f"🚦 Send Limit: {'ON' if g_cfg.get('send_limit_enabled', True) else 'OFF'}", callback_data="rapmgr_set_slimit_toggle", style=user_style)],
            [InlineKeyboardButton("-1", callback_data="rapmgr_set_slimit_m", style=user_style),
             InlineKeyboardButton(f"Max Bars: {g_cfg.get('send_limit_max', 4)}", callback_data="noop", style=user_style),
             InlineKeyboardButton("+1", callback_data="rapmgr_set_slimit_p", style=user_style)],
            [InlineKeyboardButton("⬅️ Back", callback_data="rapmgr_page_1", style=user_style)]
        ])
        await edit_or_send(text, kb)

    # block set delay flow
    elif data == "set_delay":
        current = rap_db.data["global_config"].get("default_delay", 6)
        text = (
            f"⏱ <b>Delay Settings</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Current Delay: <b>{current}s</b>\n"
            f"Default: <b>6s</b>\n\n"
            f"Adjust delay by ±3s or type a custom value in PM."
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➖ 3s", callback_data="rapmgr_delay_minus", style=user_style),
             InlineKeyboardButton(f"⏱ {current}s", callback_data="rapmgr_set_delay_prompt", style=user_style),
             InlineKeyboardButton("➕ 3s", callback_data="rapmgr_delay_plus", style=user_style)],
            [InlineKeyboardButton("⬅️ Back", callback_data="rapmgr_settings", style=user_style)]
        ])
        await edit_or_send(text, kb)

    elif data == "set_delay_prompt":
        if not cb.message:
            try: await cb.answer(f"⏱ [SETTINGS]\nPlease check your PM with {bot_mention} to set the custom delay.", show_alert=True)
            except: pass
            
        try:
            if cb.message: await cb.message.delete()
        except: pass
        try:
            prompt = await userbot.send_message(user_pm_id, f"⏱ [<b>SETTINGS</b>]\nEnter default delay in seconds (integer):\n(Type <code>/cancel</code> to stop)\n\n<i>Check {bot_mention} for input</i>")
            res = await userbot.listen(chat_id=user_pm_id, filters=filters.text & filters.user(user_id), timeout=60)
            if res.text.lower() == "/cancel":
                await res.delete()
                await prompt.edit("🛑 <b>Cancelled.</b>")
                return await rap_manage_handler(c, user_id=user_id, chat_id=user_pm_id)

            if res.text.isdigit():
                rap_db.data["global_config"]["default_delay"] = int(res.text)
                rap_db.save()
                await prompt.edit(f"✅ Default delay set to <b>{res.text}s</b>")
            else:
                await prompt.edit("❌ Invalid input. Must be a number.")
            await res.delete()
        except Exception as e:
            await c.send_message(chat_id, f"❌ Error: {e}")

    elif data in ["delay_minus", "delay_plus"]:
        current = rap_db.data["global_config"].get("default_delay", 6)
        new_val = current - 3 if data == "delay_minus" else current + 3
        if new_val < 1: new_val = 1
        rap_db.data["global_config"]["default_delay"] = new_val
        rap_db.save()
        cb.data = "rapmgr_set_delay"
        await rapmgr_cb_handler(c, cb)

    # block set emoji flow
    elif data == "set_emoji":
        if not cb.message:
            await cb.answer(f"✨ [SETTINGS]\nPlease check your PM with {bot_mention} to set the emoji.", show_alert=True)
            
        if cb.message: await cb.message.delete()
        try:
            prompt = await userbot.send_message(user_pm_id, f"✨ [<b>SETTINGS</b>]\nEnter default rhyme emoji suffix (or 'none'):\n(Type <code>/cancel</code> to stop)\n\n<i>Check {bot_mention} for input</i>")
            res = await userbot.listen(chat_id=user_pm_id, filters=filters.text & filters.user(user_id), timeout=60)
            if res.text.lower() == "/cancel":
                await res.delete()
                await prompt.edit("🛑 <b>Cancelled.</b>")
                return await rap_manage_handler(c, user_id=user_id, chat_id=user_pm_id)

            emoji = res.text.strip()
            if emoji.lower() == "none": emoji = ""
            rap_db.data["global_config"]["default_emoji"] = emoji
            rap_db.save()
            await prompt.edit(f"✅ Default emoji set to: {emoji or 'None'}")
            await res.delete()
        except Exception as e:
            await c.send_message(chat_id, f"❌ Error: {e}")

    # block set clean toggle
    # Toggle Clean Reply Mode
    elif data == "set_clean":
        current = rap_db.data["global_config"].get("clean_reply", False)
        rap_db.data["global_config"]["clean_reply"] = not current
        rap_db.save()
        cb.data = "rapmgr_settings"
        await rapmgr_cb_handler(c, cb)

    # block set mode toggle
    # Toggle Mode (Reply/Edit)
    elif data == "set_mode":
        current = rap_db.data["global_config"].get("mode", "reply")
        new_mode = "edit" if current == "reply" else "reply"
        rap_db.data["global_config"]["mode"] = new_mode
        rap_db.save()
        try: await cb.answer(f"✅ Response Mode: {new_mode.upper()}")
        except: pass
        # Refresh current settings view
        cb.data = "rapmgr_settings"
        await rapmgr_cb_handler(c, cb)

    # block send limit toggle
    elif data == "set_slimit_toggle":
        current = rap_db.data["global_config"].get("send_limit_enabled", True)
        rap_db.data["global_config"]["send_limit_enabled"] = not current
        rap_db.save()
        try: await cb.answer(f"🚦 Send Limit: {'ON' if not current else 'OFF'}")
        except: pass
        cb.data = "rapmgr_settings"
        await rapmgr_cb_handler(c, cb)

    # block send limit alert toggle
    elif data == "set_slimit_alert":
        current = rap_db.data["global_config"].get("send_limit_alert_enabled", True)
        rap_db.data["global_config"]["send_limit_alert_enabled"] = not current
        rap_db.save()
        try: await cb.answer(f"🔔 Limit Alert: {'ON' if not current else 'OFF'}")
        except: pass
        cb.data = "rapmgr_settings"
        await rapmgr_cb_handler(c, cb)

    # block send limit adjustment
    elif data in ["set_slimit_m", "set_slimit_p"]:
        current = rap_db.data["global_config"].get("send_limit_max", 4)
        new_val = current - 1 if data == "set_slimit_m" else current + 1
        new_val = max(1, min(50, new_val))  # Clamp 1-50
        rap_db.data["global_config"]["send_limit_max"] = new_val
        rap_db.save()
        try: await cb.answer(f"Max Bars: {new_val}")
        except: pass
        cb.data = "rapmgr_settings"
        await rapmgr_cb_handler(c, cb)

    # block send limit confirmation callbacks
    elif data.startswith("lim_stop_"):
        task_id = data.replace("lim_stop_", "")
        if task_id in RAP_TASKS:
            RAP_TASKS[task_id]["user_stopped"] = True
            evt = RAP_TASKS[task_id].get("confirm_event")
            if evt: evt.set()
        try:
            if cb.message: await cb.message.edit("🛑 <b>Stopped by user.</b>", parse_mode=enums.ParseMode.HTML)
        except: pass
        await cb.answer("🛑 Task stopped.", show_alert=False)

    elif data.startswith("lim_cont_"):
        task_id = data.replace("lim_cont_", "")
        if task_id in RAP_TASKS:
            RAP_TASKS[task_id]["user_stopped"] = False
            evt = RAP_TASKS[task_id].get("confirm_event")
            if evt: evt.set()
        try:
            if cb.message: await cb.message.edit("▶️ <b>Continuing...</b>", parse_mode=enums.ParseMode.HTML)
        except: pass
        await cb.answer("▶️ Continuing!", show_alert=False)

    # block set lines flow
    elif data == "set_lines":
        current = rap_db.data["global_config"].get("lines_per_msg", 2)
        text = (
            f"📜 <b>Line Density Settings</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Lines per Message: <b>{current}</b>\n"
            f"Default: <b>2</b>\n\n"
            f"Adjust the number of lines sent in each message."
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➖ 1", callback_data="rapmgr_lines_minus", style=user_style),
             InlineKeyboardButton(f"line: {current}", callback_data="rapmgr_settings", style=user_style),
             InlineKeyboardButton("➕ 2", callback_data="rapmgr_lines_plus", style=user_style)],
            [InlineKeyboardButton("⬅️ Back", callback_data="rapmgr_settings", style=user_style)]
        ])
        await edit_or_send(text, kb)

    elif data in ["lines_minus", "lines_plus"]:
        current = rap_db.data["global_config"].get("lines_per_msg", 2)
        new_val = current - 1 if data == "lines_minus" else current + 2
        if new_val < 1: new_val = 1
        rap_db.data["global_config"]["lines_per_msg"] = new_val
        rap_db.save()
        cb.data = "rapmgr_set_lines"
        await rapmgr_cb_handler(c, cb)

    # block set markdown toggle
    elif data == "set_markdown":
        options = ["None", "Italic", "Underline", "Italic+Underline"]
        current = rap_db.data["global_config"].get("markdown_type", "None")
        try:
            next_idx = (options.index(current) + 1) % len(options)
        except ValueError:
            next_idx = 0
        new_val = options[next_idx]
        rap_db.data["global_config"]["markdown_type"] = new_val
        rap_db.save()
        await cb.answer(f"🎨 Markdown: {new_val}")
        cb.data = "rapmgr_settings"
        await rapmgr_cb_handler(c, cb)

    # block inline edit loopback
    elif data.startswith("le_"):
        # ─── INLINE EDIT HANDLER (LOOPBACK) ───
        # Note: user_id is already set to owner_id from context extraction above.
        user_style = get_user_button_style(user_id)
        try:
            parts = data.split("_")
            slug = parts[1]
            idx = int(parts[2])
            size = int(parts[3])
            
            song = rap_db.get_song(slug)
            if song and idx < len(song["lyrics"]):
                chunk = song["lyrics"][idx : idx + size]
                formatted_lines = []
                for line in chunk:
                    f_line = rhyme_formatter(html.escape(line))
                    emoji = rap_db.data["global_config"].get("default_emoji", "🔥")
                    if emoji: f_line = f"{f_line} {emoji}"
                    # Apply markdown formatting
                    mtype = rap_db.data["global_config"].get("markdown_type", "None")
                    f_line = markdown_formatter(f_line, mtype)
                    formatted_lines.append(f_line)
                
                text = "\n".join(formatted_lines)
                text = f"<blockquote expandable>{text}</blockquote>"
                
                # Update button for the NEXT chunk — encode context for the next loopback trigger
                next_idx = idx + size
                kb = None
                if next_idx < len(song["lyrics"]):
                    ctx = f"_uid{user_id}_cid{chat_id}"
                    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🎤", callback_data=f"rapmgr_le_{slug}_{next_idx}_{size}{ctx}", style=user_style)]])
                
                await edit_or_send(text, kb)
        except Exception as e:
            logger.error(f"Inline loopback edit failed: {e}")
            await cb.answer("Edit failed.")
 
    # block set inline toggle
    # Toggle Inline Mode
    elif data == "set_inline":
        current = rap_db.data["global_config"].get("inline_mode", False)
        new_state = not current
        rap_db.data["global_config"]["inline_mode"] = new_state
        rap_db.save()
        try: await cb.answer(f"🤖 Inline Mode: {'ON' if new_state else 'OFF'}")
        except: pass
        cb.data = "rapmgr_settings"
        await rapmgr_cb_handler(c, cb)

    # block start rap from ui
    # Trigger Rap from Bot Assistant Result
    elif data.startswith("start_"):
        slug = data.replace("start_", "")
        # Restore explicit Userbot resolving via FOR LOOP if preferred for transparency
        userbot = None
        for cli in Altruix.clients:
            if cli.me.id == user_id:
                userbot = cli
                break
                
        if not userbot:
            # Fallback to bot manager if list iteration fails
            try:
                userbot = Altruix.bot_manager.get_bot(user_id)
            except: pass
            
        if not userbot:
            try: await cb.answer("❌ Userbot session not found for your account.", show_alert=True)
            except: pass
            return
            
        song = rap_db.get_song(slug)
        if not song:
            try: await cb.answer("❌ Song not found.")
            except: pass
            return
        
        # Userbot sends lyrics in THIS chat
        # ✅ Generate Task ID BEFORE starting to avoid race condition
        task_id = generate_task_id()
        asyncio.create_task(rap_executor(userbot, chat_id, slug, reply_to_id=None, task_id=task_id))
        
        await edit_or_send(
            f"🎬 <b>Lyrics Started:</b> <i>{song['title']}</i>\n"
            f"• <b>Task ID:</b> <code>{task_id}</code>", 
            kb=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛑 Stop", callback_data=f"rapmgr_stop_{task_id}", style=user_style)],
                [InlineKeyboardButton("« Back to List", callback_data="rapmgr_page_1", style=user_style)]
            ])
        )

    # block stop rap from ui
    # Stop Rap from Bot Assistant UI
    elif data.startswith("stop_"):
        task_id = data.replace("stop_", "")
        if task_id in RAP_TASKS:
            RAP_TASKS[task_id]["task"].cancel()
            try: await cb.answer("🛑 Task stopping...")
            except: pass
            await edit_or_send(f"🛑 <b>Task Stopped:</b> <code>{task_id}</code>")
        else:
            try: await cb.answer("❌ Task not found or already finished.", show_alert=True)
            except: pass
            try:
                if cb.message:
                    await cb.message.delete()
                else:
                    await edit_or_send("❌ Task Expired.")
            except: pass


# --- INLINE BOT SUPPORT (@bot) ---

# block inline query handler
# Handler for lyric searching and dashboard initiation via @bot inline queries.
@Altruix.bot.on_inline_query(filters.regex(r"^(rap_manage_uid_|.*)"))
@iuser_check
@log_errors
async def rap_inline_query_handler(c: Client, q: InlineQuery):
    """
    Handles inline queries via the bot assistant.
    Returns the dashboard or song results based on the query.
    """
    query = q.query.lower().strip()
    
    # block inline dashboard response
    # ─── DASHBOARD REQUEST (System Triggered) ───
    # We bypass the 'inline_mode' toggle check for dashboard requests
    # because it's required for the .rapmanage command to function.
    # ─── DASHBOARD REQUEST (System Triggered) ───
    # Dashboard query: rap_manage_uid_{uid}_pg{pg}_sz{sz}[_cid{cid}]
    if query.startswith("rap_manage_uid_"):
        try:
            # Parse query parameters using regex for robustness
            uid_match = re.search(r"uid_(\d+)", query)
            pg_match = re.search(r"pg(\d+)", query)
            sz_match = re.search(r"sz(\d+)", query)
            cid_match = re.search(r"cid(-?\d+)", query)
            
            user_id = int(uid_match.group(1)) if uid_match else q.from_user.id
            page = int(pg_match.group(1)) if pg_match else 1
            page_size = int(sz_match.group(1)) if sz_match else 6 # Now default to 6
            chat_id = int(cid_match.group(1)) if cid_match else None
            
            songs = rap_db.get_all_songs()
            items = [(slug, data["title"]) for slug, data in songs.items()]
            text = (
                f"<blockquote expandable>"
                f"🎤 <b>Userbot Rap Manager</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"Total Songs: <b>{len(items)}</b>\n"
                f"Storage Mode: <code>{rap_db.data['global_config'].get('mode', 'reply').upper()}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"Select a song to edit or tap 'Add New' to create one:"
                f"</blockquote>"
            )
            
            # Use generate_pagination_keyboard which now handles context encoding automatically
            kb = generate_pagination_keyboard(items, page, page_size, "rapmgr", style=get_user_button_style(user_id), chat_id=chat_id, user_id=user_id)
            
            return await q.answer(
                results=[
                    InlineQueryResultArticle(
                        title="🎤 Rap Manager Dashboard",
                        description=f"Manage {len(items)} songs (Page {page})",
                        input_message_content=InputTextMessageContent(text),
                        reply_markup=kb
                    )
                ],
                cache_time=1,
                is_personal=True
            )
        except Exception as e:
            logger.error(f"Dashboard inline answer failed: {e}")
            return await q.answer([], switch_pm_text="❌ Error building dashboard", switch_pm_parameter="error")
 
    # block inline line dispatch
    # ─── LINE DISPATCH (Triggered by userbot for lyrics delivery) ───
    if query.startswith("line_"):
        try:
            # Robust parsing of parameters
            slug_match = re.search(r"line_([^_]+)_(\d+)", query)
            if not slug_match: raise ValueError("Invalid line query")
            
            slug = slug_match.group(1)
            idx = int(slug_match.group(2))
            
            size_match = re.search(r"_s(\d+)", query)
            size = int(size_match.group(1)) if size_match else 1
            is_edit = "_e" in query
            
            # Extract owner and chat context (minified format: _u123_c-100)
            uid_match = re.search(r"u(\d+)", query)
            cid_match = re.search(r"c(-?\d+)", query)
            owner_id = int(uid_match.group(1)) if uid_match else q.from_user.id
            chat_id = int(cid_match.group(1)) if cid_match else None
            
            user_style = get_user_button_style(owner_id)
            
            song = rap_db.get_song(slug)
            if song and idx < len(song["lyrics"]):
                chunk = song["lyrics"][idx : idx + size]
                formatted_lines = []
                for line in chunk:
                    f_line = rhyme_formatter(html.escape(line))
                    emoji = rap_db.data["global_config"].get("default_emoji", "🔥")
                    if emoji: f_line = f"{f_line} {emoji}"
                    # Apply markdown formatting
                    mtype = rap_db.data["global_config"].get("markdown_type", "None")
                    f_line = markdown_formatter(f_line, mtype)
                    formatted_lines.append(f_line)
                
                text = "\n".join(formatted_lines)
                # Wrap in expandable blockquote
                text = f"<blockquote expandable>{text}</blockquote>"
                
                # If Edit Mode is enabled, add the hidden trigger button
                # The button points to the NEXT chunk for the loopback mechanism.
                kb = None
                if is_edit:
                    next_idx = idx + size
                    if next_idx < len(song["lyrics"]):
                        # Encode full context in the loopback trigger callback
                        # Callback buttons use _uid and _cid internally, we minify only inline queries
                        ctx = f"_uid{owner_id}"
                        if chat_id: ctx += f"_cid{chat_id}"
                        
                        target_data = f"rapmgr_le_{slug}_{next_idx}_{size}{ctx}"
                        if len(target_data) > 64:
                            # Edge case compression if still too long (highly unlikely now)
                            target_data = target_data[:64]
                            
                        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🎤", callback_data=target_data, style=user_style)]])
                
                import hashlib
                result_id = hashlib.md5(query.encode()).hexdigest()
                
                return await q.answer(
                    results=[
                        InlineQueryResultArticle(
                            id=result_id,
                            title="🎤 Sending Lyrics...",
                            input_message_content=InputTextMessageContent(
                                text,
                                parse_mode=enums.ParseMode.HTML
                            ),
                            reply_markup=kb
                        )
                    ],
                    cache_time=1,
                    is_personal=True
                )
        except Exception as e:
            logger.error(f"Inline line dispatch failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return await q.answer([])

    # block inline alert response
    # ─── LIMIT ALERT (Triggered by userbot when send limit is reached) ───
    if query.startswith("rap_alert_"):
        try:
            # Extract original task_id from q.query to avoid case mismatch
            raw_query = q.query.strip()
            task_id = raw_query.split("_", 2)[-1] if "_" in raw_query else ""
            
            logger.debug(f"[RAP INLINE ALERT] Received query for task: {task_id}. Current tasks: {list(RAP_TASKS.keys())}")
            
            # Robust Case-Insensitive Lookup
            task_info = None
            if task_id in RAP_TASKS:
                task_info = RAP_TASKS[task_id]
            else:
                # Fallback: search case-insensitively
                for tid, info in RAP_TASKS.items():
                    if tid.lower() == task_id.lower():
                        task_info = info
                        task_id = tid # Re-assign the correct key for consistency
                        break
            
            if not task_info:
                logger.warning(f"[RAP INLINE ALERT] Task {task_id} not found in RAP_TASKS.")
                return await q.answer([], switch_pm_text="❌ Task Expired", switch_pm_parameter="help")
            
            title = task_info.get("title", "Unknown Song")
            # For progress, we need to know how many bars were sent vs total
            bars_sent = task_info.get("bars_sent", 0)
            limit = task_info.get("limit", 0)
            total_blocks = task_info.get("total_blocks", 0)
            
            text = (
                "<blockquote expandable>"
                f"⚠️ <b>Send Limit Reached</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"Song: <b>{html.escape(title)}</b>\n"
                f"Bars Sent: <code>{bars_sent}/{total_blocks}</code>\n"
                f"Limit: <code>{limit}</code>\n\n"
                f"Continue sending the next bars?"
                "</blockquote>"
            )
            
            _alert_uid = task_info.get("client_id", 0)
            _alert_style = get_user_button_style(_alert_uid) if _alert_uid else None
            
            kb = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🛑 Stop", callback_data=f"rapmgr_lim_stop_{task_id}", style=_alert_style),
                    InlineKeyboardButton("▶️ Continue", callback_data=f"rapmgr_lim_cont_{task_id}", style=_alert_style)
                ]
            ])
            
            import hashlib
            result_id = hashlib.md5(query.encode()).hexdigest()
            
            return await q.answer(
                results=[
                    InlineQueryResultArticle(
                        id=result_id,
                        title="⚠️ Send Limit Reached",
                        description=f"Song: {title} | Progress: {bars_sent}/{total_blocks}",
                        input_message_content=InputTextMessageContent(
                            text,
                            parse_mode=enums.ParseMode.HTML
                        ),
                        reply_markup=kb
                    )
                ],
                cache_time=1,
                is_personal=True
            )
        except Exception as e:
            logger.error(f"Inline alert dispatch failed: {e}")
            return await q.answer([], cache_time=1)

    # block inline search response
    # ─── SEARCH REQUEST (@bot query) ───
    # For public searching, we honor the 'inline_mode' toggle.
    if not rap_db.data["global_config"].get("inline_mode", False):
        return await q.answer([], switch_pm_text="❌ Inline Mode is OFF", switch_pm_parameter="help")

    songs = rap_db.get_all_songs()
    results = []

    # 1. Filering logic
    matches = []
    for slug, data in songs.items():
        if not query or query in slug or query in data["title"].lower():
            matches.append((slug, data))

    # 2. Limit to 50 results (TG limit)
    for slug, data in matches[:50]:
        results.append(
            InlineQueryResultArticle(
                id=f"rap_{slug}_{int(time.time())}", # Ensure unique result ID
                title=f"🎤 {data['title']}",
                description=f"Slug: {slug} | Lines: {len(data['lyrics'])}",
                input_message_content=InputTextMessageContent(
                    f"🚀 <b>Ready to send:</b> <i>{data['title']}</i>\nSlug: <code>{slug}</code>"
                ),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🚀 Start Lyrics", callback_data=f"rapmgr_start_{slug}", style=get_user_button_style(q.from_user.id))]
                ])
            )
        )

    await q.answer(
        results,
        cache_time=1,
        is_personal=True,
        switch_pm_text="➕ Add New Lyrics",
        switch_pm_parameter="add_song"
    )

# block chosen inline handler
@Altruix.bot.on_chosen_inline_result()
@iuser_check
@log_errors
async def rap_chosen_inline_handler(c: Client, q: ChosenInlineResult):
    """
    Triggers the rap_executor once a user selects a song from the inline results.
    """
    try:
        if not q.result_id.startswith("rap_"):
            return

        # Results format: rap_{slug}_{timestamp}
        parts = q.result_id.split("_")
        
        # If result_id is malformed, raise/handle properly
        if len(parts) < 2: 
            logger.warning(f"Malformed Result ID: {q.result_id}")
            return
            
        slug = parts[1]
        
        # Check if song exists before logging
        song = rap_db.get_song(slug)
        if not song:
            logger.debug(f"Chosen song {slug} not found in DB")
            return

        if q.inline_message_id:
            logger.info(f"Chosen Inline Result: {song['title']} (Slug: {slug}) | InlineID: {q.inline_message_id}")
            # The actual delivery starts via callback button 'Start Lyrics' in the result message.
    except Exception as e:
        logger.error(f"Critical error in chosen inline handler: {e}")
