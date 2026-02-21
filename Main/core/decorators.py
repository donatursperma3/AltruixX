# Copyright (C) 2021-present by Altruix@Github, <https://github.com/Altruix>
#
# This file is part of <https://github.com/Altruix/Altruix> project,
# and is released under the "GNU v3.0 License Agreement".
# Please see <https://github.com/Altriux/Altruix/blob/main/LICENSE>
#
# All rights reserved.

import os
import html
import asyncio
import traceback
from datetime import datetime
from .client import Altruix
from typing import Union
from functools import wraps
from pyromod.exceptions import ListenerTimeout
from Main.internals.set_inline import set_inline_in_botfather
from pyrogram.types import Message, InlineQuery, CallbackQuery
from pyrogram import Client, StopPropagation, ContinuePropagation
from pyrogram.errors import (
    MessageEmpty, MessageIdInvalid, BotInlineDisabled, MessageNotModified,
    UserNotParticipant, MessageTooLong, QueryIdInvalid # ✅ Added
)
from pyrogram.enums import ParseMode
from pyrogram.types import LinkPreviewOptions, ReplyParameters
from Main.utils.file_helpers import make_file_from_text # ✅ Added


# ─── UTIL: KIRIM PESAN KE GRUP LOG (AMAN DARI ERROR) ────────────────────
async def send_log_message(text: str, filename: str = "log_error.txt"):
    """
    Kirim pesan ke LOG_CHAT_ID (dari .env) atau fallback ke OWNER_ID.
    Digunakan untuk logging error & aktivitas penting.
    Returns: Message object or None
    """
    log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))
    
    try:
        return await Altruix.bot.send_message(
            log_chat_id,
            text,
            parse_mode=ParseMode.HTML,
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
    except MessageTooLong:
        # ✅ FIX: Handle text that exceeds Telegram limit by sending as file
        try:
            file_path = await make_file_from_text(text, file_name=filename)
            msg = await Altruix.bot.send_document(
                log_chat_id,
                file_path,
                caption=f"📄 <b>Log message too long</b>\nTime: <code>{datetime.now().strftime('%H:%M:%S')}</code>",
                parse_mode=ParseMode.HTML
            )
            if os.path.exists(file_path):
                os.remove(file_path)
            return msg
        except Exception as e:
            Altruix.log(f"Failed to send long log file: {e}", level=40)
    except Exception:
        # Jika gagal ke LOG_CHAT_ID, coba ke OWNER_ID langsung
        try:
            return await Altruix.bot.send_message(
                Altruix.config.OWNER_ID,
                f"⚠️ [FALLBACK LOG]\n{text}",
                parse_mode=ParseMode.HTML,
                link_preview_options=LinkPreviewOptions(is_disabled=True)
            )
        except Exception:
            pass


# ─── DECORATOR: DEBUG SETIAP INTERAKSI CALLBACK/INLINE ──────────────────
def iuser_check(func):
    """
    ✅ DIPERBAIKI:
    - Tambahkan logging aktivitas tombol ke log grup
    - Beri feedback jika terjadi error internal
    - Pastikan selalu ada respons (tidak diam)
    """

    async def wrapper(*args, **kwargs):
        client = None
        update = None
        
        # Identify client and update from args
        for arg in args:
            if isinstance(arg, Client):
                client = arg
            elif hasattr(arg, 'from_user'):
                update = arg
        
        user = update.from_user if update else None
        if not user:
            return

        user_id = user.id
        username = f"@{user.username}" if user.username else "No username"
        full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "No name"
        
        # ✅ CALLBACK LOGGER CONFIGURATION
        # Fetch from centralized config (synced with database)
        # Filter modes: all / sudo / nonsudo / off
        log_type = (await Altruix.config.get_env("CB_LOGGER_GLOBAL") or "all").lower()
        
        # ✅ FIXED: Check authorization using centralized helper
        # This handles dynamic sudo users from database, static list, and per-account settings
        c = args[0] if args and isinstance(args[0], Client) else None
        is_sudo = await Altruix.is_sudo(user_id, client=c)
        
        # ✅ Also authorize all active userbot session IDs for inline queries
        # This ensures .ping, .help, etc. can use inline bot results
        if not is_sudo and isinstance(update, InlineQuery):
            active_session_ids = [client.me.id for client in Altruix.clients if hasattr(client, 'me') and client.me]
            is_sudo = user_id in active_session_ids
        
        # ✅ Determine if callback should be logged based on filter mode
        should_log = False
        if log_type == "all":
            should_log = True
        elif log_type == "sudo" and is_sudo:
            should_log = True
        elif log_type == "nonsudo" and not is_sudo:
            should_log = True
        elif log_type == "off":
            should_log = False

        if is_sudo:
            result_status = "AUTHORIZED"
        else:
            if isinstance(update, CallbackQuery):
                # ✅ FIX: The ID must be the USERBOT session owner's ID, not the bot assistant's ID.
                # The custom alert is saved under the userbot's user ID (from Altruix.clients),
                # while `c.me` here is the bot assistant (@coolkidxbot), NOT the userbot.
                # We fall back to the first active userbot session for global mode.
                owner_id = Altruix.config.OWNER_ID
                if Altruix.clients:
                    first_client = Altruix.clients[0]
                    if hasattr(first_client, 'me') and first_client.me:
                        owner_id = first_client.me.id
                from Main.utils.file_helpers import get_user_custom_alert
                alert_data = get_user_custom_alert(owner_id)
                if alert_data.get("mode") == "custom":
                    result_status = alert_data.get("text", Altruix.get_string("AUTH_BUTTON_DENIED"))
                else:
                    result_status = Altruix.get_string("AUTH_BUTTON_DENIED")
            elif isinstance(update, InlineQuery):
                result_status = "AUTH_FEATURE_DENIED"
            else:
                result_status = "AUTH_FEATURE_DENIED"


        if is_sudo:
            # ✅ PERF: Run handler IMMEDIATELY, then log in background (fire & forget)
            async def _log_and_auth():
                if should_log:
                    chat_info = "N/A"
                    chat_id = "N/A"
                    cb_data = "N/A"
                    msg_text = "N/A"
                    
                    if isinstance(update, CallbackQuery):
                        cb_data = update.data or "No Data"
                        if update.message:
                            chat = update.message.chat
                            
                            from pyrogram.enums import ChatType
                            
                            # Chat Label/Hyperlink
                            if chat.type == ChatType.PRIVATE:
                                chat_type_str = "👤 Private"
                                chat_label = f"{chat.first_name or ''} {chat.last_name or ''}".strip() or "User"
                            elif chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                                chat_type_str = "👥 Group"
                                chat_label = chat.title or "Unknown Group"
                            elif chat.type == ChatType.CHANNEL:
                                chat_type_str = "📢 Channel"
                                chat_label = chat.title or "Unknown Channel"
                            else:
                                chat_type_str = "💬 Chat"
                                chat_label = chat.title or "Unknown"

                            if chat.username:
                                chat_info = f"{chat_type_str}: <a href='https://t.me/{chat.username}'>{html.escape(chat_label)}</a>"
                            elif chat.id:
                                chat_info = f"{chat_type_str}: <b>{html.escape(chat_label)}</b>"
                            else:
                                chat_info = f"{chat_type_str}: <b>{html.escape(chat_label)}</b>"
                            
                            msg_text = update.message.text or update.message.caption or "[No Text/Media]"
                        else:
                            chat_info = "📱 Inline Interface"
                            chat_id = "Inline"
                            
                            if hasattr(update, "inline_message_id") and update.inline_message_id:
                                try:
                                    cache = await Altruix.local_db.inline_col.find_one({"_id": update.inline_message_id})
                                    if cache:
                                        chat_id = cache.get("chat_id", "Inline")
                                        chat_title = cache.get("chat_title", "Inline Chat")
                                        if chat_id != "Inline" and chat_id != "N/A":
                                            chat_info = f"📱 {chat_title} (<code>{chat_id}</code>)"
                                        else:
                                            chat_info = f"📱 {chat_title}"
                                except Exception:
                                    pass

                            import re
                            if chat_id == "Inline" and (cid_match := re.search(r"cid=(-?\d+)", cb_data)):
                                extracted_cid = cid_match.group(1)
                                chat_id = extracted_cid
                                chat_info = f"📱 Inline Chat (ID: <code>{extracted_cid}</code>)"
                            
                            msg_text = "[Inline Callback Result]"
                    elif isinstance(update, InlineQuery):
                        cb_data = f"Inline Query: {update.query}"
                        chat_info = "Inline Query"
                    
                    time_now = datetime.now().strftime("%H:%M:%S")
                    
                    me = getattr(client, "me", None) if 'client' in locals() else None
                    if not me:
                        for arg in args:
                            if isinstance(arg, Client):
                                _c = arg
                                me = getattr(_c, "me", None)
                                break

                    if client and not me:
                        try: me = await client.get_me()
                        except: me = None
                    
                    bot_username = f"@{me.username}" if me and me.username else "Unknown Bot"
                    if me and not getattr(me, "is_bot", False):
                        bot_username = f"Userbot Session ({bot_username})"
                    
                    display_name = full_name.strip()
                    is_blank = not display_name or all(ord(ch) < 33 or ord(ch) == 8203 for ch in display_name)
                    final_name = "blank" if is_blank else html.escape(full_name)
                    username_display = f"{username}" if username and username != "None" else "None"
                    
                    log_message = (
                        f"{Altruix.get_string('LOGGER_CALLBACK_TITLE')}\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"{Altruix.get_string('LOGGER_CALLBACK_BOT').format(html.escape(bot_username))}\n"
                        f"{Altruix.get_string('LOGGER_CALLBACK_USER').format(user_id, final_name)}\n"
                        f"{Altruix.get_string('LOGGER_CALLBACK_USERNAME').format(username_display)}\n"
                        f"{Altruix.get_string('LOGGER_CALLBACK_USER_ID').format(user_id)}\n"
                        f"{Altruix.get_string('LOGGER_CALLBACK_CHAT').format(chat_info)}\n"
                        f"{Altruix.get_string('LOGGER_CALLBACK_CHAT_ID').format(chat_id)}\n"
                        f"{Altruix.get_string('LOGGER_CALLBACK_DATA').format(html.escape(cb_data))}\n"
                        f"{Altruix.get_string('LOGGER_CALLBACK_RESULT').format(html.escape(Altruix.get_string('AUTHORIZED')))}\n"
                        f"{Altruix.get_string('LOGGER_CALLBACK_MSG_HEADER')}\n"
                        f"<blockquote>{html.escape(str(msg_text)[:1000])}</blockquote>\n"
                        f"{Altruix.get_string('LOGGER_CALLBACK_TIME').format(time_now)}\n\n"
                        f"{Altruix.get_string('LOGGER_CALLBACK_PRIVATE_LINK').format(user_id)}"
                    )
                    await send_log_message(log_message)

            try:
                # ✅ Fire handler immediately, log concurrently (non-blocking)
                import asyncio as _asyncio
                result_coro = func(*args, **kwargs)
                _asyncio.create_task(_log_and_auth())
                return await result_coro
            except MessageNotModified:
                if isinstance(update, CallbackQuery):
                    await update.answer("ℹ️ Tidak ada perubahan diperlukan.", show_alert=True)
            except Exception as e:
                error_text = (
                    f"💥 <b>ERROR SAAT MENANGANI CALLBACK</b>\n"
                    f"• User: {full_name} ({user_id})\n"
                    f"• Fungsi: <code>{func.__name__}</code>\n"
                    f"• Error: <code>{str(e)}</code>"
                )
                import asyncio as _asyncio
                _asyncio.create_task(send_log_message(error_text))
                if isinstance(update, CallbackQuery):
                    try:
                        await update.answer("❌ Terjadi kesalahan internal. Owner telah diberi tahu.", show_alert=True)
                    except QueryIdInvalid:
                        pass
        else:
            # ✅ For non-sudo: show the alert popup, then log in background
            if should_log:
                async def _log_denied():
                    chat_id = "Inline"
                    cb_data = update.data or "No Data" if isinstance(update, CallbackQuery) else "N/A"
                    chat_info = "📱 Inline Interface" if isinstance(update, CallbackQuery) and not update.message else "N/A"
                    msg_text = "[Inline Callback Result]"
                    time_now = datetime.now().strftime("%H:%M:%S")
                    
                    if isinstance(update, CallbackQuery) and update.message:
                        chat = update.message.chat
                        from pyrogram.enums import ChatType
                        chat_label = chat.title or f"{chat.first_name or ''} {chat.last_name or ''}".strip() or "User"
                        if chat.type == ChatType.PRIVATE: prefix = "👤 Private"
                        elif chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]: prefix = "👥 Group"
                        elif chat.type == ChatType.CHANNEL: prefix = "📢 Channel"
                        else: prefix = "💬 Chat"
                        chat_info = f"{prefix}: <b>{html.escape(chat_label)}</b>"
                        chat_id = chat.id
                        msg_text = update.message.text or update.message.caption or "[No Text/Media]"
                    
                    me = None
                    for arg in args:
                        if isinstance(arg, Client):
                            me = getattr(arg, "me", None)
                            break
                    bot_username = f"@{me.username}" if me and me.username else "Unknown Bot"
                    if me and not getattr(me, "is_bot", False):
                        bot_username = f"Userbot Session ({bot_username})"
                    
                    display_name = full_name.strip()
                    is_blank = not display_name or all(ord(ch) < 33 or ord(ch) == 8203 for ch in display_name)
                    final_name = "blank" if is_blank else html.escape(full_name)
                    username_display = f"{username}" if username and username != "None" else "None"
                    
                    log_message = (
                        f"{Altruix.get_string('LOGGER_CALLBACK_TITLE')}\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"{Altruix.get_string('LOGGER_CALLBACK_BOT').format(html.escape(bot_username))}\n"
                        f"{Altruix.get_string('LOGGER_CALLBACK_USER').format(user_id, final_name)}\n"
                        f"{Altruix.get_string('LOGGER_CALLBACK_USERNAME').format(username_display)}\n"
                        f"{Altruix.get_string('LOGGER_CALLBACK_USER_ID').format(user_id)}\n"
                        f"{Altruix.get_string('LOGGER_CALLBACK_CHAT').format(chat_info)}\n"
                        f"{Altruix.get_string('LOGGER_CALLBACK_CHAT_ID').format(chat_id)}\n"
                        f"{Altruix.get_string('LOGGER_CALLBACK_DATA').format(html.escape(cb_data))}\n"
                        f"{Altruix.get_string('LOGGER_CALLBACK_RESULT').format(html.escape(result_status))}\n"
                        f"{Altruix.get_string('LOGGER_CALLBACK_MSG_HEADER')}\n"
                        f"<blockquote>{html.escape(str(msg_text)[:1000])}</blockquote>\n"
                        f"{Altruix.get_string('LOGGER_CALLBACK_TIME').format(time_now)}\n\n"
                        f"{Altruix.get_string('LOGGER_CALLBACK_PRIVATE_LINK').format(user_id)}"
                    )
                    await send_log_message(log_message)

                import asyncio as _asyncio
                _asyncio.create_task(_log_denied())

            if isinstance(update, CallbackQuery):
                try:
                    await update.answer(
                        result_status if 'result_status' in locals() else Altruix.get_string("AUTH_BUTTON_DENIED"),
                        show_alert=True,
                        cache_time=5
                    )
                except QueryIdInvalid:
                    pass
            elif isinstance(update, InlineQuery):
                try:
                    await update.answer(
                        [],
                        switch_pm_text=Altruix.get_string("AUTH_FEATURE_DENIED"),
                        switch_pm_parameter="unauthorized",
                        cache_time=5
                    )
                except QueryIdInvalid:
                    pass
            elif isinstance(update, Message):
                await update.reply_msg(Altruix.get_string("AUTH_FEATURE_DENIED"))

    return wrapper


# ─── DECORATOR: LOG ERROR SECARA LUAS DAN AMAN ──────────────────────────
def log_errors(func):
    """✅ DIPERBAIKI: Gunakan send_log_message & tangani semua edge case"""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except StopPropagation as e:
            raise StopPropagation from e
        except (
            MessageNotModified,
            MessageIdInvalid,
            UserNotParticipant,
            MessageEmpty,
            ListenerTimeout,   # ✅ Added: Ignore listener timeout as crash
            asyncio.TimeoutError, # ✅ Added: Also ignore standard timeout
            QueryIdInvalid      # ✅ Added: Ignore expired queries
        ):
            pass  # error yang bisa diabaikan
        except ContinuePropagation as e:
            raise ContinuePropagation from e
        except Exception as _be:
            # ✅ KIRIM ERROR LENGKAP KE LOG DENGAN METADATA DETAIL
            c = None
            u = None
            
            # Extract client and update from args
            for arg in args:
                if isinstance(arg, Client):
                    c = arg
                elif isinstance(arg, (Message, CallbackQuery)):
                    u = arg
            
            if not c and Altruix.clients:
                c = Altruix.clients[0]
            
            # Common Info
            time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            plugin_ver = "Unknown"
            module_name = func.__module__
            
            # Try to get plugin version from the function's module
            try:
                import sys
                module = sys.modules.get(module_name)
                if module:
                    plugin_ver = getattr(module, "PLUGIN_VERSION", "Unknown")
            except: pass

            msg_info = "N/A"
            chat_info = "N/A"
            user_info = "N/A"
            acc_info = "N/A"
            reply_info = "" # ✅ NEW: Reply info container
            
            if u:
                # Chat ID/Link
                chat = getattr(u, "chat", None)
                if not chat and getattr(u, "message", None): # CallbackQuery
                    chat = u.message.chat
                
                if chat:
                    chat_id = chat.id
                    chat_title = chat.title or chat.first_name or "Chat"
                    if chat.username:
                        chat_info = f"<a href='https://t.me/{chat.username}'>{html.escape(str(chat_title))}</a> (<code>{chat_id}</code>)"
                    else:
                        chat_info = f"<b>{html.escape(str(chat_title))}</b> (<code>{chat_id}</code>)"
                
                # Executed By
                user = u.from_user
                if user:
                    user_id = user.id
                    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "User"
                    status = "Owner (Self)" if user_id in Altruix.config.OWNER_USERS_ID else ("Sudo" if user_id in Altruix.auth_users else "User")
                    user_info = f"<a href='tg://user?id={user_id}'>{html.escape(full_name)}</a> [<code>{user_id}</code>] (<b>{status}</b>)"
                
                # Command
                if isinstance(u, Message):
                    msg_info = u.text or u.caption or "[Media/No Text]"
                    
                    # ✅ CHECK REPLY
                    if u.reply_to_message:
                        rm_id = u.reply_to_message.id
                        rm_user = u.reply_to_message.from_user
                        rm_user_info = "False"
                        if rm_user:
                            rm_full_name = f"{rm_user.first_name or ''} {rm_user.last_name or ''}".strip()
                            rm_user_info = f"<a href='tg://user?id={rm_user.id}'>{html.escape(rm_full_name)}</a>"
                        
                        reply_info = (
                            f"↩️ <b>Reply to msg ID:</b> <code>{rm_id}</code>\n"
                            f"👤 <b>Reply to user:</b> {rm_user_info}\n"
                        )
                    else:
                        reply_info = "↩️ <b>Reply to msg ID:</b> False\n👤 <b>Reply to user:</b> False\n"

                elif isinstance(u, CallbackQuery):
                    msg_info = f"Callback: <code>{u.data}</code>"

            if c:
                # Account
                me = c.me
                me_name = f"{me.first_name or ''} {me.last_name or ''}".strip() or "Userbot"
                idx = "N/A"
                for i, client in enumerate(Altruix.clients):
                    if client == c:
                        idx = i + 1
                        break
                acc_info = f"<b>{html.escape(me_name)}</b> [<code>{me.id}</code>] Account #{idx}"

            error_detail = (
                f"#LOG_ERROR\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🎯 <b>CMD:</b> <code>{html.escape(str(msg_info)[:500])}</code>\n"
                f"👤 <b>CMD BY:</b> {user_info}\n"
                f"🤖 <b>ACCOUNT:</b> {acc_info}\n"
                f"💬 <b>CHAT:</b> {chat_info}\n"
                f"{reply_info}" # ✅ Inject reply info
                f"🕒 <b>TIME:</b> <code>{time_now}</code>\n"
                f"🔌 <b>PLUGIN VER:</b> <code>{plugin_ver}</code>\n"
                f"🛰 <b>USERBOT VER:</b> <code>{Altruix.__version__}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"💥 <b>ERROR:</b> <code>{_be}</code>\n"
                f"📍 <b>IN:</b> <code>{module_name}.{func.__name__}</code>\n\n"
                f"📑 <b>TRACEBACK:</b>\n"
                f"<pre>{html.escape(traceback.format_exc())}</pre>"
            )
            
            sent_log = await send_log_message(error_detail, filename=f"error_{func.__name__}.txt")
            
            # ✅ Notify user if possible (Edit "Processing..." message)
            # Check if there is a tracked "wait_msg" (Processing...) attached to the input message
            target_msg = getattr(u, "wait_msg", None)
            
            # Fallback to editing the command itself if no wait_msg, ONLY if it's self-authored
            if not target_msg and isinstance(u, Message) and u.from_user and u.from_user.is_self:
                target_msg = u

            if target_msg and isinstance(target_msg, Message):
                try:
                    # Construct Log Link
                    log_link = "Check Log Group"
                    if sent_log and sent_log.chat and sent_log.chat.username:
                        log_link = f"<a href='https://t.me/{sent_log.chat.username}/{sent_log.id}'>Check Log Message</a>"
                    elif sent_log and sent_log.chat:
                         # Private/Private Group link format
                        log_link = f"<a href='https://t.me/c/{str(sent_log.chat.id)[4:]}/{sent_log.id}'>Check Log Message</a>"

                    await target_msg.edit(
                        f"<b>💥 Error Occurred!</b>\n"
                        f"Command failed during execution.\n"
                        f"👉 {log_link}",
                        disable_web_page_preview=True
                    )
                except Exception:
                    pass

    return wrapper


# ─── DECORATOR: CEK IZIN INLINE (TANPA PERUBAHAN BESAR) ─────────────────
def inline_check(func):
    """
    ✅ FIXED: Decorator to handle BotInlineDisabled errors and auto-enable inline mode.
    
    This decorator wraps userbot command handlers that use inline bot results (via @bot).
    If inline mode is disabled, it automatically enables it via BotFather and retries.
    
    CRITICAL FIX: Now properly passes *args and **kwargs to the wrapped function.
    Previous version was dropping these arguments, causing inline responses to fail.
    """
    @wraps(func)
    async def check_inline(c: Client, m: Message, *args, **kwargs):
        try:
            # ✅ DEBUG: Log entry to inline_check decorator
            log_msg = f"🔍 <b>[inline_check] Entering decorator</b>\n• Function: <code>{func.__name__}</code>\n• User: {c.me.id if c.me else 'Unknown'}\n• Chat: {m.chat.id}"
            Altruix.log(f"🔍 [inline_check] Entering decorator for {func.__name__}", level=20)
            await send_log_message(log_msg)
            
            # ✅ FIX: Pass all arguments to the wrapped function
            result = await func(c, m, *args, **kwargs)
            
            # ✅ DEBUG: Log successful completion
            success_msg = f"✅ <b>[inline_check] Completed successfully</b>\n• Function: <code>{func.__name__}</code>"
            Altruix.log(f"✅ [inline_check] {func.__name__} completed successfully", level=20)
            await send_log_message(success_msg)
            return result
            
        except BotInlineDisabled as e:
            # Auto-enable inline mode and retry
            error_msg = f"⚠️ <b>[inline_check] BotInlineDisabled</b>\n• Function: <code>{func.__name__}</code>\n• Action: Auto-enabling inline mode"
            Altruix.log(f"⚠️ [inline_check] BotInlineDisabled caught, auto-enabling inline mode", level=30)
            await send_log_message(error_msg)
            
            status = await m.handle_message("INLINE_DISABLED")
            await set_inline_in_botfather(c)
            await status.delete()
            # ✅ FIX: Pass all arguments on retry as well
            return await func(c, m, *args, **kwargs)
            
        except Exception as e:
            # ✅ DEBUG: Log any other exceptions that might be silently caught
            exception_msg = (
                f"❌ <b>[inline_check] Exception Caught</b>\n"
                f"• Function: <code>{func.__name__}</code>\n"
                f"• Exception: <code>{type(e).__name__}</code>\n"
                f"• Message: <code>{str(e)[:200]}</code>"
            )
            Altruix.log(f"❌ [inline_check] Exception in {func.__name__}: {type(e).__name__}: {e}", level=40)
            await send_log_message(exception_msg)
            raise  # Re-raise to let the function's own exception handling deal with it
    return check_inline


# ─── DECORATOR: CEK IZIN ADMIN (TANPA PERUBAHAN BESAR) ──────────────────
def check_perm(perm_type, return_perm=False):
    def check_perm_s(func):
        async def perm_check(client, m):
            if m.chat.type in ["bot", "private"]:
                return await func(client, m)
            if isinstance(perm_type, list):
                s = {}
                for i in perm_type:
                    s[i] = await client.check_my_perm(m, i)[0]  # ✅ PERBAIKAN: sebelumnya s[perm_type] → salah
                if all(element is False for element in s.values()):
                    return await func(client, m)
                not_true_ = [str(v) for v in s.keys() if s[v] is False]
                not_true_m = ", ".join(not_true_)
                return await m.handle_message(
                    "ADMIN_ACTION_FAILED", string_args=(not_true_m,)
                )
            else:
                perm_result = await client.check_my_perm(m, perm_type)
                if return_perm:
                    return (
                        await func(client, m, perm_result[1])
                        if perm_result[0]
                        else await m.handle_message(
                            "ADMIN_ACTION_FAILED", string_args=(perm_type,)
                        )
                    )
                return (
                    await func(client, m)
                    if perm_result[0]
                    else await m.handle_message(
                        "ADMIN_ACTION_FAILED", string_args=(perm_type,)
                    )
                )
        return perm_check
    return check_perm_s
