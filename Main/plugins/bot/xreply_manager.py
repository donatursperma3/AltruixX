PLUGIN_VERSION = "0.0.24"
# xreply_manager.py
# Separated logic for handling PM Logger replies to prevent conflicts
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.

from Main import Altruix
from pyrogram import Client, enums, filters
from pyrogram.types import (
    Message as RawMessage,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery
)
from Main.core.decorators import log_errors, iuser_check
from Main.utils.access_control import is_authorized_user
from Main.utils.file_helpers import get_db_path
import html
import logging
from datetime import datetime

# Import module directly to ensure we always get the fresh dict after reloads
from Main.plugins.userbot import xpm_logger_user
import json
import os

logger = logging.getLogger("altruix.reply_manager")

def should_log():
    filename = get_db_path("reply_manager_settings.json")
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                data = json.load(f)
                return data.get("enabled", False)
        except:
            pass
    return False

# ✅ Dynamic Filter for Log Chat
async def dynamic_log_chat_filter(_, __, m: RawMessage):
    if not Altruix.log_chat:
        return False
    return m.chat.id == Altruix.log_chat

log_chat_filter = filters.create(dynamic_log_chat_filter)

@Altruix.bot.on_message(log_chat_filter & filters.reply, group=1)
@iuser_check
@log_errors
async def handle_reply_input(c: Client, m: RawMessage):
    """
    Handles replies in the log group.
    Checks if the reply is to an instruction message from the bot.
    If so, initiates the confirmation flow.
    """
    if not m.reply_to_message:
        return
        
    do_log = should_log()
    if do_log:
        logger.info(f"ReplyManager: Detected reply in log chat {m.chat.id} from {m.from_user.id if m.from_user else 'None'}. Altruix.log_chat={Altruix.log_chat}")

    # Access shared state from Altruix object (PERSISTENT across reloads)
    REPLY_AS_MENTIONED_WAITING = Altruix.REPLY_AS_MENTIONED_WAITING
    PM_LOG_CACHE = Altruix.PM_LOG_CACHE
    USER_REPLY_COUNTS = Altruix.USER_REPLY_COUNTS

    # FORCE RELOAD from persistent storage to ensure we have sessions from before restart
    xpm_logger_user.SessionManager.load()
    
    if do_log:
        logger.info(f"ReplyManager: Current items after forced load: {len(REPLY_AS_MENTIONED_WAITING)}")
        if len(REPLY_AS_MENTIONED_WAITING) > 0:
            logger.debug(f"ReplyManager: Current waiting IDs: {list(REPLY_AS_MENTIONED_WAITING.keys())}")

    # Security: Verify if user is authorized to reply (Handled by @iuser_check)
    # is_auth = is_authorized_user(m.from_user.id, Altruix.config.OWNER_ID, Altruix.config.SUDO_USERS)
    # ...
    
    # Check if we are waiting for a reply to this specific message
    waiting_id = None
    reply_to_id = m.reply_to_message.id
    thread_id = getattr(m, "message_thread_id", None)
    
    # Debug: Print full reply info
    r_msg = m.reply_to_message
    if do_log:
        logger.info(
            f"ReplyManager: Checking reply.\n"
            f"  - Current Msg ID: {m.id}\n"
            f"  - Reply To ID: {reply_to_id}\n"
            f"  - Thread ID: {thread_id}\n"
            f"  - Reply From ID: {r_msg.from_user.id if r_msg.from_user else 'None'}\n"
            f"  - Reply Text snippet: {str(r_msg.text or r_msg.caption)[:30]}"
        )
    
    # Force reload if empty
    if not REPLY_AS_MENTIONED_WAITING:
        xpm_logger_user.SessionManager.load()
        logger.info(f"ReplyManager: Reloaded sessions, current count: {len(REPLY_AS_MENTIONED_WAITING)}")

    # Priority Match 1: Direct ID Match (Notification, Instructions, or Forwarded)
    for wid, data in list(REPLY_AS_MENTIONED_WAITING.items()):
        saved_instr_id = str(data.get("instruction_msg_id"))
        saved_log_id = str(data.get("log_msg_id"))
        saved_fwd_id = str(data.get("fwd_msg_id", "None"))
        current_id = str(reply_to_id)
        
        if current_id in [saved_instr_id, saved_log_id, saved_fwd_id]:
            waiting_id = wid
            logger.info(f"ReplyManager: Direct ID Match found: {wid} (matched ID {current_id})")
            break
            
    # Priority Match 2: Thread/Topic ID Match (Fallback for Forum)
    if not waiting_id and thread_id is not None:
        logger.info(f"ReplyManager: Direct match failed, attempting Thread ID fallback for thread {thread_id}")
        candidates = []
        is_topic_head_reply = (str(reply_to_id) == str(thread_id))
        
        for wid, data in list(REPLY_AS_MENTIONED_WAITING.items()):
            saved_thread_id = data.get("thread_id")
            # If it's a topic head reply, we are more lenient with thread matching
            if saved_thread_id is not None and str(saved_thread_id) == str(thread_id):
                candidates.append((wid, data.get("instruction_msg_id", 0) or 0))
        
        if candidates:
            # Sort by instruction_msg_id descending to get the MOST RECENT session in this thread
            candidates.sort(key=lambda x: x[1], reverse=True)
            waiting_id = candidates[0][0]
            logger.info(f"ReplyManager: Fallback Match found (Thread: {thread_id}, Head: {is_topic_head_reply}): {waiting_id}")
        else:
            # No candidates found - try reloading sessions one more time
            # This handles the case where a session was just created
            logger.info(f"ReplyManager: No candidates in current sessions, forcing reload...")
            xpm_logger_user.SessionManager.load()
            
            # Try again after reload
            for wid, data in list(REPLY_AS_MENTIONED_WAITING.items()):
                saved_thread_id = data.get("thread_id")
                if saved_thread_id is not None and str(saved_thread_id) == str(thread_id):
                    candidates.append((wid, data.get("instruction_msg_id", 0) or 0))
            
            if candidates:
                candidates.sort(key=lambda x: x[1], reverse=True)
                waiting_id = candidates[0][0]
                logger.info(f"ReplyManager: Found after reload (Thread: {thread_id}): {waiting_id}")

    if not waiting_id:
        active_ids = []
        for wid, d in list(REPLY_AS_MENTIONED_WAITING.items()):
            active_ids.append(f"{wid} -> instr:{d.get('instruction_msg_id')}|log:{d.get('log_msg_id')}|fwd:{d.get('fwd_msg_id')}|thread:{d.get('thread_id')}")
        
        if do_log:
            logger.warning(
                f"ReplyManager: No active session for message_id {reply_to_id}.\n"
                f"  - Checked {len(REPLY_AS_MENTIONED_WAITING)} sessions: {active_ids}"
            )
        
        # Only reply if it was a direct reply attempt
        await m.reply(
                f"⚠️ <b>Sesi Balasan Tidak Ditemukan</b>\n\n"
                f"Balasan ke ID: <code>{reply_to_id}</code>\n"
                f"Thread ID: <code>{thread_id}</code>\n\n"
                f"Pastikan membalas ke pesan <b>Notifikasi Log</b> atau <b>Instruksi Balasan</b> yang baru.\n"
                f"💡 <i>Jika di Forum, klik 'Reply' pada pesan log, bukan pada judul topik.</i>",
                quote=True
            )
        return
    
    session_user_id = str(REPLY_AS_MENTIONED_WAITING[waiting_id].get("user_id", "None"))
    current_user_id = str(m.from_user.id)
    data = REPLY_AS_MENTIONED_WAITING[waiting_id]
    
    logger.info(f"ReplyManager: Validated session {waiting_id} (Session User: {session_user_id}, Current: {current_user_id}). Preparing confirmation.")
    
    # Store the admin's reply message ID
    REPLY_AS_MENTIONED_WAITING[waiting_id]["admin_reply_msg_id"] = m.id
    xpm_logger_user.SessionManager.save()
    
    # Preview message
    preview_text = m.text or m.caption or "[Media Message]"
    if len(preview_text) > 100:
        preview_text = preview_text[:100] + "..."
        
    is_all = data.get("is_reply_all", False)
    target_chat_id = data.get("chat_id")
    
    confirm_text = (
        f"🤔 <b>Konfirmasi Kirim Balasan?</b>\n\n"
        f"• <b>Target:</b> <code>{target_chat_id}</code>\n"
        f"• <b>Metode:</b> {'SEMUA Akun' if is_all else 'Akun Tunggal'}\n"
        f"• <b>Pesan:</b>\n<blockquote>{html.escape(preview_text)}</blockquote>\n\n"
        f"✅ Klik tombol di bawah untuk mengirim."
    )
    
    btn_prefix = "pmlu"
    if waiting_id.startswith("pmlb_"): btn_prefix = "pmlb"
    elif waiting_id.startswith("mentions_"): btn_prefix = "mentions"
    elif waiting_id.startswith("mntlb_"): btn_prefix = "mntlb" # ✅ Added for bot mentions
    
    buttons = [
        [
            InlineKeyboardButton("✅ Ya, Kirim", callback_data=f"{btn_prefix}_confirm_{waiting_id}"),
            InlineKeyboardButton("❌ Batal", callback_data=f"{btn_prefix}_cancel_{waiting_id}")
        ]
    ]
    
    try:
        await m.reply(
            confirm_text,
            quote=True,
            parse_mode=enums.ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(buttons),
            message_thread_id=m.message_thread_id if hasattr(m, "message_thread_id") else None
        )
    except Exception as e:
        logger.error(f"ReplyManager: Confirm send failed: {e}")
        await m.reply(f"❌ Error: {e}")


@Altruix.bot.on_callback_query(filters.regex(r"^(pmlu|mentions|pmlb)_confirm_"))
@iuser_check
@log_errors
async def pmlu_confirm_send_callback(c: Client, cb: CallbackQuery):
    """Confirm and send the reply using the appropriate client(s)."""
    # Access shared state from Altruix object (PERSISTENT across reloads)
    REPLY_AS_MENTIONED_WAITING = Altruix.REPLY_AS_MENTIONED_WAITING
    PM_LOG_CACHE = Altruix.PM_LOG_CACHE
    USER_REPLY_COUNTS = Altruix.USER_REPLY_COUNTS

    # Ensure we have latest from disk
    xpm_logger_user.SessionManager.load()

    try:
        # Security (Handled by @iuser_check)
        

        # Extract waiting_id based on prefix
        if cb.data.startswith("pmlu_confirm_"):
            waiting_id = cb.data.replace("pmlu_confirm_", "")
        elif cb.data.startswith("pmlb_confirm_"):
            waiting_id = cb.data.replace("pmlb_confirm_", "")
        elif cb.data.startswith("mentions_confirm_"):
            waiting_id = cb.data.replace("mentions_confirm_", "")
        else: # mntlb
            waiting_id = cb.data.replace("mntlb_confirm_", "")
        
        if waiting_id not in REPLY_AS_MENTIONED_WAITING:
            # Try numeric waiting_id if it's stored as int (legacy)
            if waiting_id.isdigit() and int(waiting_id) in REPLY_AS_MENTIONED_WAITING:
                waiting_id = int(waiting_id)
            else:
                return await cb.answer("❌ Session expired or invalid.", show_alert=True)
        
        # Security: Allow any authorized sudo user to confirm
        # Skip strict user_id check because cb.from_user.id returns bot ID
        # Just verify that SUDO_USERS exist (means system is authorized)
        if not Altruix.config.SUDO_USERS and not Altruix.config.OWNER_ID:
            return await cb.answer("⛔ Sistem tidak dikonfigurasi!", show_alert=True)
            
        data = REPLY_AS_MENTIONED_WAITING.pop(waiting_id)
        xpm_logger_user.SessionManager.save()
        
        chat_id = int(data["chat_id"])
        msg_id = int(data["message_id"])
        msg_key = data["msg_key"]
        client_id = int(data.get("client_id", 0)) if data.get("client_id") else 0
        admin_reply_id = data.get("admin_reply_msg_id")
        
        do_log = should_log()
        if do_log:
            logger.info(f"ReplyManager: Starting delivery for session {waiting_id}. Target User: {chat_id}, ReplyMsg ID: {msg_id}, AdminReply ID: {admin_reply_id}, ClientID: {client_id}")

        if not admin_reply_id:
            return await cb.answer("❌ Admin reply message not found.", show_alert=True)
            
        sent_count = 0
        errors = []
        today = datetime.now().strftime("%Y%m%d")
        
        # Ensure cache entry exists
        if msg_key not in PM_LOG_CACHE:
            PM_LOG_CACHE[msg_key] = {"last_replies": []}
        elif not isinstance(PM_LOG_CACHE[msg_key], dict):
             PM_LOG_CACHE[msg_key] = {"last_replies": []}
        elif "last_replies" not in PM_LOG_CACHE[msg_key]:
            PM_LOG_CACHE[msg_key]["last_replies"] = []

        if data.get("is_reply_all"):
            # Send from all userbots
            logger.info(f"ReplyManager: Attempting Reply-All from {len(Altruix.clients)} clients.")
            for client in Altruix.clients:
                if client.is_connected:
                    try:
                        # Copy from LOG GROUP (where admin replied) to TARGET CHAT
                        sent = await client.copy_message(
                            chat_id=chat_id, 
                            from_chat_id=Altruix.log_chat, 
                            message_id=admin_reply_id,
                            reply_to_message_id=msg_id
                        )
                        sent_count += 1
                        PM_LOG_CACHE[msg_key]["last_replies"].append((client.me.id, sent.id))
                        logger.info(f"ReplyManager: Reply-All Successful for client {client.me.id}")
                    except Exception as e:
                        logger.error(f"ReplyManager: Reply-All Failed for client {client.me.id if client.me else 'unknown'}: {e}")
                        errors.append(f"{client.me.first_name if client.me else 'Client'}: {str(e)}")
            
            if "user_id" in data:
                USER_REPLY_COUNTS[data["user_id"]][today] += 1
        else:
            # Send from specific account
            target_client = None
            if Altruix.bot and Altruix.bot.me and Altruix.bot.me.id == client_id:
                target_client = Altruix.bot
            else:
                for client in Altruix.clients:
                    if client.me and client.me.id == client_id:
                        target_client = client
                        break
            
            if target_client:
                if do_log:
                    logger.info(f"ReplyManager: Sending via target client {target_client.me.id if target_client.me else 'Bot'}")
                try:
                    sent = await target_client.copy_message(
                        chat_id=chat_id, 
                        from_chat_id=Altruix.log_chat, 
                        message_id=admin_reply_id,
                        reply_to_message_id=msg_id
                    )
                    if do_log:
                        logger.info(f"ReplyManager: Copy successful. Sent ID {sent.id} to user {chat_id}")
                    sent_count = 1
                    PM_LOG_CACHE[msg_key]["last_replies"].append((target_client.me.id, sent.id))
                except Exception as e:
                     logger.warning(f"ReplyManager: copy_message failed ({e}). Trying fallback.")
                     try:
                        # Fallback: Get message from bot and send via target client
                        msg = await Altruix.bot.get_messages(Altruix.log_chat, admin_reply_id)
                        sent = None
                        if msg.text:
                            sent = await target_client.send_message(chat_id, msg.text, reply_to_message_id=msg_id)
                        elif msg.media:
                            sent = await msg.copy(chat_id, reply_to_message_id=msg_id) # Using pyrogram msg.copy
                        
                        if sent:
                            sent_count = 1
                            PM_LOG_CACHE[msg_key]["last_replies"].append((target_client.me.id, getattr(sent, "id", 0)))
                            logger.info(f"ReplyManager: Fallback successful. Sent ID {getattr(sent, 'id', 0)}")
                        else:
                             errors.append(f"Fallback failed: No return message")
                     except Exception as fallback_err:
                        logger.error(f"ReplyManager: Both primary and fallback failed. Error: {fallback_err}")
                        errors.append(f"Primary error: {e}. Fallback error: {fallback_err}")
            else:
                logger.error(f"ReplyManager: Target client {client_id} not found or offline.")
                errors.append("Account not found or offline.")
            
            # Update counts for single replies too
            if "user_id" in data:
                USER_REPLY_COUNTS[data["user_id"]][today] += 1
        
        # ✅ Detailed Success Notification
        if sent_count > 0:
            # 1. Reply Via (Account used)
            if data.get("is_reply_all"):
                via_text = f"Multiple Accounts ({sent_count})"
            else:
                if target_client and target_client.me:
                    via_text = f"<a href='tg://user?id={target_client.me.id}'>{html.escape(target_client.me.first_name)}</a>"
                else:
                    via_text = "Unknown Client"

            # 2. Reply By (User who clicked)
            by_user = cb.from_user
            if by_user:
                by_text = f"<a href='tg://user?id={by_user.id}'>{html.escape(by_user.first_name)}</a>"
            else:
                by_text = "Unknown User"

            # 3. Target Chat & Info
            # Try to get chat title from cache if available, or just use ID
            chat_title = str(chat_id)
            chat_link = f"tg://user?id={chat_id}" # Default to user link for PM
            chat_type = "User/Bot" if chat_id > 0 else "Group"
            
            # Check cached name
            if msg_key in PM_LOG_CACHE and isinstance(PM_LOG_CACHE[msg_key], dict):
                cached_name = PM_LOG_CACHE[msg_key].get("name") or PM_LOG_CACHE[msg_key].get("group_name")
                if cached_name:
                    chat_title = html.escape(cached_name)
                    
                # Determining link type based on ID
                # If negative, it's a group/channel
                if chat_id < 0:
                     # Remove -100 prefix if present for public links, but for protected links use c/
                     chat_link_id = str(chat_id).replace("-100", "") if str(chat_id).startswith("-100") else str(chat_id).replace("-", "")
                     chat_link = f"https://t.me/c/{chat_link_id}/{msg_id}"
                else:
                     chat_link = f"tg://user?id={chat_id}"

            target_text = f"<a href='{chat_link}'>{chat_title}</a>"

            # 4. Sent Message Link (Button)
            # We use the LAST sent message ID for the button
            sent_msg_id = 0
            if PM_LOG_CACHE[msg_key]["last_replies"]:
                _, sent_msg_id = PM_LOG_CACHE[msg_key]["last_replies"][-1]
            
            # Construct Button
            success_kb = None
            if sent_msg_id:
                if chat_id < 0:
                    chat_link_id = str(chat_id).replace("-100", "") if str(chat_id).startswith("-100") else str(chat_id).replace("-", "")
                    btn_url = f"https://t.me/c/{chat_link_id}/{sent_msg_id}"
                    success_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Go to Message", url=btn_url)]])

            time_str = datetime.now().strftime("%H:%M:%S")

            res_msg = (
                f"✅ <b>Berhasil mengirim dari {sent_count} akun</b>\n"
                f"• <b>Reply via:</b> {via_text} (userbot)\n"
                f"• <b>Replied by:</b> {by_text}\n"
                f"• <b>Chat Target:</b> {target_text} (source)\n"
                f"• <b>Chat Type:</b> {chat_type}\n"
                f"• <b>Chat ID:</b> <code>{chat_id}</code>\n"
                f"• <b>Time:</b> {time_str}"
            )
            
            if errors:
                res_msg += f"\n\n❌ <b>Gagal:</b> {len(errors)} akun\n" + "\n".join([f"- {e}" for e in errors[:5]])
            
            await cb.message.edit_text(res_msg, parse_mode=enums.ParseMode.HTML, reply_markup=success_kb, disable_web_page_preview=True)
            
        else:
             await cb.message.edit_text(f"❌ <b>Gagal Mengirim</b>\n" + "\n".join(errors), parse_mode=enums.ParseMode.HTML)

    except Exception as e:
        logger.error(f"ReplyManager Error: {e}")
        await cb.answer(f"❌ Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^(pmlu|mentions|pmlb|mntlb)_cancel_"))
@iuser_check
@log_errors
async def pmlu_cancel_send_callback(c: Client, cb: CallbackQuery):
    """Cancel the reply session."""
    REPLY_AS_MENTIONED_WAITING = Altruix.REPLY_AS_MENTIONED_WAITING
    # Force read from persistent
    xpm_logger_user.SessionManager.load()
    try:
        # Security (Handled by @iuser_check)
        

        if cb.data.startswith("pmlu_cancel_"):
            waiting_id = cb.data.replace("pmlu_cancel_", "")
        elif cb.data.startswith("pmlb_cancel_"):
            waiting_id = cb.data.replace("pmlb_cancel_", "")
        elif cb.data.startswith("mentions_cancel_"):
            waiting_id = cb.data.replace("mentions_cancel_", "")
        else: # mntlb
            waiting_id = cb.data.replace("mntlb_cancel_", "")

        if waiting_id not in REPLY_AS_MENTIONED_WAITING:
            if waiting_id.isdigit() and int(waiting_id) in REPLY_AS_MENTIONED_WAITING:
                waiting_id = int(waiting_id)
            else:
                return await cb.answer("❌ Sesi tidak ditemukan.", show_alert=True)
         
        if waiting_id in REPLY_AS_MENTIONED_WAITING:
            # Security: Allow any authorized sudo user to cancel
            # Skip strict user_id check because cb.from_user.id returns bot ID
            if not Altruix.config.SUDO_USERS and not Altruix.config.OWNER_ID:
                return await cb.answer("⛔ Sistem tidak dikonfigurasi!", show_alert=True)
            
            REPLY_AS_MENTIONED_WAITING.pop(waiting_id)
            xpm_logger_user.SessionManager.save()
            
        await cb.message.edit_text("❌ Pengiriman pesan dibatalkan.")
    except Exception as e:
        await cb.answer(f"❌ Error: {e}", show_alert=True)

# logger.info("xreply_manager loaded successfully.")

# ✅ HANDLER: Reply Manager Settings Menu
@Altruix.bot.on_callback_query(filters.regex(r"^reply_manager_menu$"))
@iuser_check
@log_errors
async def reply_manager_menu_handler(c: Client, cb: CallbackQuery):
    try:
        # Security (Handled by @iuser_check)
        

        enabled = should_log()
        
        text = (
            "<b>💬 Reply Manager Settings</b>\n\n"
            "Kontrol apakah Bot Assistant memproses balasan di Log Group untuk diteruskan ke user.\n\n"
            f"• <b>Status:</b> {'✅ ENABLED' if enabled else '❌ DISABLED'}"
        )
        
        buttons = [
            [
                InlineKeyboardButton(f"{'Disable' if enabled else 'Enable'} Manager", callback_data="reply_manager_toggle_enabled")
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data="bot_controls_menu")
            ]
        ]
        await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)
    except Exception as e:
        await cb.answer(f"❌ Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^reply_manager_toggle_enabled$"))
@iuser_check
@log_errors
async def reply_manager_toggle_enabled_handler(c: Client, cb: CallbackQuery):
    filename = get_db_path("reply_manager_settings.json")
    data = {"enabled": False}
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f: data = json.load(f)
        except: pass
        
    data["enabled"] = not data.get("enabled", False)
    
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)
        
    await reply_manager_menu_handler(c, cb)

