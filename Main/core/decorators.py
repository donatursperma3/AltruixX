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
from Main.utils.essentials import Essentials
from pyromod.exceptions import ListenerTimeout
from Main.internals.set_inline import set_inline_in_botfather
from pyrogram.types import Message, InlineQuery, CallbackQuery
from pyrogram import Client, StopPropagation, ContinuePropagation
from pyrogram.errors import (
    MessageEmpty, MessageIdInvalid, BotInlineDisabled, MessageNotModified,
    UserNotParticipant, MessageTooLong, QueryIdInvalid, 
    PeerIdInvalid, ChannelInvalid # ✅ Added to ignore list
)
from pyrogram.enums import ParseMode
from pyrogram.types import LinkPreviewOptions, ReplyParameters
from Main.utils.file_helpers import make_file_from_text # ✅ Added


# ─── UTIL: DECODE INLINE_MESSAGE_ID → CHAT_ID ───────────────────────────
def _decode_inline_chat_id(inline_message_id: str):
    """
    Decode inline_message_id to extract the real chat_id (peer ID).
    Uses Pyrogram's unpack_inline_message_id which decodes the base64 TL object.
    InputBotInlineMessageID64 contains 'owner_id' = the chat peer ID.
    Returns (chat_id_str, is_channel) or (None, False) on failure.
    """
    try:
        from pyrogram.utils import unpack_inline_message_id
        parsed = unpack_inline_message_id(inline_message_id)
        if hasattr(parsed, 'owner_id') and parsed.owner_id:
            raw_id = parsed.owner_id
            # owner_id for channels/supergroups is the raw channel_id (positive)
            # Pyrogram API uses -100{channel_id} format for supergroups/channels
            # For private chats (users), owner_id IS the user_id (positive)
            # We return both the -100 prefixed version and raw, caller tries both
            return raw_id
    except Exception:
        pass
    return None


async def _resolve_chat_from_owner_id(raw_owner_id, client, clients_list):
    """
    Try to resolve a chat from the decoded owner_id.
    Tries -100{owner_id} first (supergroup/channel), then raw owner_id (user/group).
    Returns (chat_id_str, chat_title, chat_type_prefix) or (None, None, None).
    """
    candidates = []
    # Supergroup/Channel format: -100{raw_id}
    if raw_owner_id > 0:
        candidates.append(int(f"-100{raw_owner_id}"))
    # Raw ID (user or legacy group)
    candidates.append(raw_owner_id)
    # Negative legacy group
    if raw_owner_id > 0:
        candidates.append(-raw_owner_id)
    
    from pyrogram.enums import ChatType
    
    for try_id in candidates:
        # Try with bot client first
        try:
            chat = await client.get_chat(try_id)
            title = chat.title or f"{chat.first_name or ''} {chat.last_name or ''}".strip() or "Chat"
            if chat.type == ChatType.PRIVATE:
                prefix = "👤 Private"
            elif chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                prefix = "👥 Group"
            elif chat.type == ChatType.CHANNEL:
                prefix = "📢 Channel"
            else:
                prefix = "💬 Chat"
            return str(chat.id), title, prefix
        except Exception:
            pass
        # Try with userbot clients
        for ubot in clients_list:
            try:
                chat = await ubot.get_chat(try_id)
                title = chat.title or f"{chat.first_name or ''} {chat.last_name or ''}".strip() or "Chat"
                if chat.type == ChatType.PRIVATE:
                    prefix = "👤 Private"
                elif chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                    prefix = "👥 Group"
                elif chat.type == ChatType.CHANNEL:
                    prefix = "📢 Channel"
                else:
                    prefix = "💬 Chat"
                return str(chat.id), title, prefix
            except Exception:
                continue
    return None, None, None



# ─── UTIL: KIRIM PESAN KE GRUP LOG (AMAN DARI ERROR) ────────────────────
async def send_log_message(text: str, filename: str = "log_error.txt", reply_markup=None):
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
            link_preview_options=LinkPreviewOptions(is_disabled=True),
            reply_markup=reply_markup
        )
    except MessageTooLong:
        # ✅ FIX: Handle text that exceeds Telegram limit by sending as file
        try:
            file_path = await make_file_from_text(text, file_name=filename)
            msg = await Altruix.bot.send_document(
                log_chat_id,
                file_path,
                caption=f"📄 <b>Log message too long</b>\nTime: <code>{datetime.now().strftime('%H:%M:%S')}</code>",
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
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
                link_preview_options=LinkPreviewOptions(is_disabled=True),
                reply_markup=reply_markup
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
            # Anonymous Admin: from_user is None for Messages sent as anonymous admin
            # SECURITY: Only fall back for outgoing messages (sent by THIS userbot client)
            # This prevents other anonymous admins in the same group from triggering commands
            if isinstance(update, Message) and getattr(update, 'outgoing', False) and client and hasattr(client, 'me') and client.me:
                user = client.me
            else:
                return

        user_id = user.id
        username = f"@{user.username}" if user.username else "No username"
        full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "No name"
        full_name = Essentials.clean_user_name(full_name)
        
        # ✅ CALLBACK LOGGER CONFIGURATION
        # Fetch from centralized config (synced with database)
        # Filter modes: all / sudo / nonsudo / off
        log_type = (await Altruix.config.get_env("CB_LOGGER_GLOBAL") or "all").lower()
        
        # ✅ FIXED: Check authorization using centralized helper
        # This handles dynamic sudo users from database, static list, and per-account settings
        c = args[0] if args and isinstance(args[0], Client) else None
        
        # ✅ DEBUG STALLING: Log every callback intercept
        if hasattr(update, 'data') and update.data:
            Altruix.log(f"🔘 [iuser_check] Intercepted Callback: {update.data} (User: {user_id})", level=20, client=c)
            
        try:
            Altruix.log(f"🔍 [iuser_check] Entering is_sudo for {user_id}...", level=20, client=c)
            # Add a safety timeout for the authorization check itself
            is_sudo = await asyncio.wait_for(Altruix.is_sudo(user_id, client=c), timeout=5)
            Altruix.log(f"📬 [iuser_check] Leaving is_sudo for {user_id}. Result: {is_sudo}", level=20, client=c)
        except asyncio.TimeoutError:
            Altruix.log(f"⏰ [iuser_check] Authorization TIMEOUT for {user_id}. Defaulting to False.", level=30, client=c)
            is_sudo = False
        except Exception as e:
            Altruix.log(f"💥 [iuser_check] Authorization ERR for {user_id}: {e}", level=40, client=c)
            is_sudo = False
        
        # ✅ Also authorize all active userbot session IDs for inline queries
        # This ensures .ping, .help, etc. can use inline bot results
        if not is_sudo and isinstance(update, InlineQuery):
            active_session_ids = [client.me.id for client in Altruix.clients if hasattr(client, 'me') and client.me]
            is_sudo = user_id in active_session_ids
        
        # ✅ Determine if callback should be logged based on filter mode
        # Normalized log_type fallback
        if log_type not in ["all", "sudo", "nonsudo", "off"]:
            log_type = "all"
            
        should_log = False
        # Only log Callbacks and Inlines to avoid message spam
        if isinstance(update, (CallbackQuery, InlineQuery)):
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
            if isinstance(update, (CallbackQuery, InlineQuery, Message)):
                # ✅ FIX: Fetch custom alert for the account owner
                owner_id = Altruix.config.OWNER_ID
                if Altruix.clients:
                    first_client = Altruix.clients[0]
                    if hasattr(first_client, 'me') and first_client.me:
                        owner_id = first_client.me.id
                
                from Main.utils.file_helpers import get_user_custom_alert
                alert_data = get_user_custom_alert(owner_id)
                result_status = alert_data.get("text", Altruix.get_string("AUTH_BUTTON_DENIED"))
                alert_mode = alert_data.get("mode", "default")
            else:
                result_status = "AUTH_FEATURE_DENIED"
                alert_mode = "default"


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
                            chat_id = chat.id  # ✅ FIX: Set chat_id for regular message callbacks
                            
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
                            
                            # ✅ PRIMARY: Decode inline_message_id to get real chat_id
                            if hasattr(update, "inline_message_id") and update.inline_message_id:
                                _raw_owner = _decode_inline_chat_id(update.inline_message_id)
                                if _raw_owner:
                                    try:
                                        _cid_str, _ctitle, _cprefix = await _resolve_chat_from_owner_id(_raw_owner, client, Altruix.clients)
                                        if _cid_str:
                                            chat_id = _cid_str
                                            chat_info = f"{_cprefix}: <b>{html.escape(_ctitle)}</b>"
                                            Altruix.log(f"[CB LOGGER] Decoded inline_message_id → chat_id={chat_id}, title={_ctitle}", level=20)
                                    except Exception as _e:
                                        Altruix.log(f"[CB LOGGER] Decode resolve err: {_e}", level=30)
                            
                            resolved_chat_id = None
                            chat_title = None
                            
                            # FALLBACK: DB cache lookup (only if primary decode didn't resolve)
                            if chat_id == "Inline" and hasattr(update, "inline_message_id") and update.inline_message_id:
                                Altruix.log(f"[CB LOGGER] Found inline_message_id: {update.inline_message_id} in CallbackQuery", level=20)
                                try:
                                    cache = await Altruix.local_db.inline_col.find_one({"_id": update.inline_message_id})
                                    if cache:
                                        Altruix.log(f"[CB LOGGER] Cache HIT for {update.inline_message_id}: {cache}", level=20)
                                        if "chat_title" in cache:
                                            chat_title = cache["chat_title"]
                                        raw_chat_id = cache.get("chat_id", "Inline")
                                        if raw_chat_id not in ["Inline", "N/A", "None", None]:
                                            resolved_chat_id = raw_chat_id
                                    else:
                                        Altruix.log(f"[CB LOGGER] Cache MISS for {update.inline_message_id}", level=30)
                                except Exception as e:
                                    Altruix.log(f"[CB LOGGER] Cache fetch err: {e}", level=40)

                            import re
                            from Main.core.ext.callback_helpers import get_callback_data
                            
                            actual_data = cb_data
                            if "#" in cb_data:
                                parts = cb_data.split("#")
                                if len(parts) > 1 and len(parts[1]) == 12: # Potential hash
                                    try:
                                        unhashed = await get_callback_data(parts[1])
                                        if unhashed:
                                            actual_data = unhashed
                                            Altruix.log(f"[CB LOGGER] Unhashed data: {actual_data}", level=20)
                                    except Exception: pass
                                    
                            # Extract Session Index for Userbot Info
                            session_idx = -1
                            si_match = re.search(r"[\?&]si=(-?\d+)", actual_data)
                            if si_match:
                                session_idx = int(si_match.group(1))
                                
                            # Fallback: Extraction from callback_data (e.g. cid=... or _cid...)
                            if not resolved_chat_id:
                                # Check cid=... (query param format)
                                if cid_match := re.search(r"cid=(-?\d+)", actual_data):
                                    resolved_chat_id = cid_match.group(1)
                                    Altruix.log(f"[CB LOGGER] Extracted cid from data: {resolved_chat_id}", level=20)
                                # Check _cid... (embedded format, e.g. rapmgr_export_uid123_cid-456)
                                elif cid_match := re.search(r"_cid(-?\d+)", actual_data):
                                    resolved_chat_id = cid_match.group(1)
                                    Altruix.log(f"[CB LOGGER] Extracted _cid from data: {resolved_chat_id}", level=20)
                                elif actual_data.startswith("settings_"):
                                    potential_cid = actual_data.replace("settings_", "")
                                    if potential_cid.lstrip('-').isdigit():
                                        resolved_chat_id = potential_cid
                                        Altruix.log(f"[CB LOGGER] Extracted settings cid: {resolved_chat_id}", level=20)

                            # Real-time Title Resolution
                            if resolved_chat_id:
                                chat_id = str(resolved_chat_id)
                                chat_title = chat_title or "Group/Chat"
                                
                                if chat_title == "Group/Chat":
                                    try:
                                        chat = await client.get_chat(int(chat_id))
                                        chat_title = chat.title or chat.first_name or "Chat"
                                    except Exception:
                                        for ubot in Altruix.clients:
                                            try:
                                                chat = await ubot.get_chat(int(chat_id))
                                                chat_title = chat.title or chat.first_name or "Chat"
                                                break
                                            except Exception: continue
                                            
                                    # ✅ Save to DB on first successful fetch to prevent future network spam
                                    if chat_title and chat_title != "Group/Chat" and hasattr(update, "inline_message_id") and update.inline_message_id:
                                        try:
                                            from Main import Altruix as Ax
                                            await Ax.local_db.inline_col.find_one_and_update(
                                                {"_id": update.inline_message_id},
                                                {"$set": {"_id": update.inline_message_id, "chat_title": chat_title, "chat_id": chat_id}},
                                                upsert=True
                                            )
                                        except Exception: pass
                                
                                chat_info = f"📱 {html.escape(chat_title)}"
                            else:
                                chat_info = "📱 Inline Interface"
                                chat_id = "Inline"
                            
                            msg_text = "[Inline Callback Result]"
                    elif isinstance(update, InlineQuery):
                        cb_data = f"Inline Query: {update.query}"
                        chat_info = "Inline Query"
                    
                    try:
                        # ─── UNIVERSAL: Derivation of Session Metadata ───
                        ubot_session_name = "Unknown Session"
                        
                        # Use session_idx from earlier extraction (lines 250-253)
                        if 'session_idx' in locals() and session_idx != -1 and 0 <= session_idx < len(Altruix.clients):
                            _c = Altruix.clients[session_idx]
                            if hasattr(_c, 'me') and _c.me:
                                ubot_session_name = _c.me.first_name or _c.me.username or str(_c.me.id)
                        elif len(Altruix.clients) > 0:
                            # Fallback to primary session
                            if client:
                                for idx, sc in enumerate(Altruix.clients):
                                    if sc == client:
                                        ubot_session_name = sc.me.first_name or sc.me.username or str(sc.me.id) if sc.me else f"Session #{idx+1}"
                                        break
                                        
                        # Common Info
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
                        display_name = Essentials.clean_user_name(display_name)
                        is_blank = not display_name or display_name == "No name" or all(ord(ch) < 33 or ord(ch) == 8203 or ord(ch) == 12644 for ch in display_name)
                        final_name = "blank" if is_blank else html.escape(display_name)
                        username_display = f"@{username.lstrip('@')}" if username and username != "None" else "None"
                        if username_display != "None":
                            username_display = html.escape(username_display)
                        
                        # ── TASK ID LOOKUP ──
                        task_id_line = ""
                        if hasattr(Altruix, '_TASK_REGISTRY') and Altruix._TASK_REGISTRY:
                            active_tasks = [
                                (tid, t) for tid, t in Altruix._TASK_REGISTRY.items()
                                if t.get("task") and not t["task"].done()
                            ]
                            if active_tasks:
                                parts_list = []
                                for tid, t in active_tasks:
                                    name = t.get("name", "?")[:15]
                                    parts_list.append(f"<code>{tid}</code> ({name})")
                                task_id_line = f"🏷 <b>Active Tasks:</b> {', '.join(parts_list)}\n"
                        
                        result_text = Altruix.get_string('AUTHORIZED')
                        if len(result_text) > 11:
                            result_text = result_text[:11] + "..."

                        log_message = (
                            f"{Altruix.get_string('LOGGER_CALLBACK_TITLE')}\n"
                            f"<blockquote expandable>"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"{Altruix.get_string('LOGGER_CALLBACK_BOT').format(html.escape(me.username) if me and me.username else 'bot', html.escape(bot_username))}\n"
                            f"{Altruix.get_string('LOGGER_CALLBACK_USERBOT').format(html.escape(ubot_session_name))}\n"
                            f"{Altruix.get_string('LOGGER_CALLBACK_USER').format(user_id, final_name)}\n"
                            f"{Altruix.get_string('LOGGER_CALLBACK_USERNAME').format(username_display)}\n"
                            f"{Altruix.get_string('LOGGER_CALLBACK_USER_ID').format(user_id)}\n"
                            f"{Altruix.get_string('LOGGER_CALLBACK_CHAT').format(chat_info)}\n"
                            f"{Altruix.get_string('LOGGER_CALLBACK_CHAT_ID').format(chat_id)}\n"
                            f"{Altruix.get_string('LOGGER_CALLBACK_DATA').format(html.escape(cb_data))}\n"
                            f"{Altruix.get_string('LOGGER_CALLBACK_RESULT').format(html.escape(result_text))}\n"
                            f"{Altruix.get_string('LOGGER_CALLBACK_TIME').format(time_now)}\n"
                            f"{task_id_line}"
                            f"{Altruix.get_string('LOGGER_CALLBACK_MSG_HEADER')}\n"
                            f"{html.escape(str(msg_text)[:1000])}"
                            f"</blockquote>"
                        )
                        
                        link_url = ""
                        if hasattr(update, "message") and update.message and update.message.link:
                            link_url = update.message.link
                        elif chat_id and str(chat_id) not in ["Inline", "N/A", "None", None, ""]:
                            c_id_str = str(chat_id)
                            if c_id_str.startswith("-100"):
                                link_url = f"https://t.me/c/{c_id_str[4:]}/999999999"
                            elif not c_id_str.startswith("-"):
                                link_url = f"tg://openmessage?user_id={c_id_str}"
                                
                        from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                        from Main.utils.file_helpers import get_user_button_style as _gubs
                        
                        # Resolve userbot user ID for button style
                        _style_uid = 0
                        if 'session_idx' in locals() and session_idx != -1 and 0 <= session_idx < len(Altruix.clients):
                            _sc = Altruix.clients[session_idx]
                            if hasattr(_sc, 'me') and _sc.me:
                                _style_uid = _sc.me.id
                        _btn_style = _gubs(_style_uid) if _style_uid else None
                        
                        buttons = [InlineKeyboardButton("👤 Chat to User", url=f"tg://user?id={user_id}")]
                        if link_url:
                            buttons.append(InlineKeyboardButton("➡️ Goto Msg", url=link_url))
                        
                        if _btn_style:
                            for _b in buttons:
                                _b.style = _btn_style
                            
                        kbd = InlineKeyboardMarkup([buttons])
                        await send_log_message(log_message, reply_markup=kbd)
                    except Exception:
                        import traceback
                        _err_txt = f"❌ <b>Error in _log_and_auth:</b>\n\n<pre>{html.escape(traceback.format_exc())}</pre>\n\n#LOG_ERROR"
                        await send_log_message(_err_txt)

            try:
                # ✅ Fire handler immediately, log concurrently (non-blocking)
                import asyncio as _asyncio
                result_coro = func(*args, **kwargs)
                _asyncio.create_task(_log_and_auth())
                res = await result_coro
                
                # ✅ INLINE STATE TRACKING: Save new state for authorized users
                if isinstance(update, CallbackQuery) and not update.message and update.inline_message_id and update.data:
                    cb_d = update.data
                    if cb_d.startswith("help") or cb_d.startswith("h#") or cb_d.startswith("ht#"):
                        from Main import Altruix as Ax
                        _asyncio.create_task(Ax.local_db.inline_col.find_one_and_update(
                            {"_id": update.inline_message_id},
                            {"$set": {"help_state": cb_d}},
                            upsert=True
                        ))
                        
                return res
            except (StopPropagation, ContinuePropagation):
                raise
            except (
                MessageNotModified,
                MessageIdInvalid,
                QueryIdInvalid,
                asyncio.TimeoutError,
                ListenerTimeout,
                PeerIdInvalid,
                ChannelInvalid
            ) as e:
                if isinstance(update, CallbackQuery) and not isinstance(e, (QueryIdInvalid, asyncio.TimeoutError, ListenerTimeout)):
                    try:
                        await update.answer("ℹ️ Tidak ada perubahan diperlukan.", show_alert=True)
                    except QueryIdInvalid:
                        pass
                return # Silence these non-critical errors
            except Exception as e:
                # ✅ Terminal Log (with account context)
                Altruix.log(f"💥 [iuser_check] Error in callback {func.__name__}: {e}", level=40, client=client)
                
                error_text = (
                    f"💥 <b>ERROR SAAT MENANGANI CALLBACK</b>\n"
                    f"<blockquote expandable>"
                    f"• User: {full_name} ({user_id})\n"
                    f"• Fungsi: <code>{func.__name__}</code>\n"
                    f"• Error: <code>{html.escape(str(e))}</code>"
                    f"</blockquote>"
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
                    # Default values
                    chat_id = "N/A"
                    cb_data = "N/A"
                    chat_info = "N/A"
                    msg_text = "N/A"
                    time_now = datetime.now().strftime("%H:%M:%S")
                    
                    if isinstance(update, CallbackQuery):
                        chat_id = "Inline"
                        cb_data = update.data or "No Data" 
                        chat_info = "📱 Inline Interface" if not update.message else "N/A"
                        msg_text = "[Inline Callback Result]"
                    elif isinstance(update, InlineQuery):
                        cb_data = f"Inline Query: {update.query}"
                        chat_info = "Inline Query"
                    elif isinstance(update, Message):
                        chat_id = update.chat.id
                        from pyrogram.enums import ChatType
                        chat_label = update.chat.title or update.chat.first_name or "Chat"
                        prefix = "💬"
                        if update.chat.type == ChatType.PRIVATE: prefix = "👤 Private"
                        elif update.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]: prefix = "👥 Group"
                        elif update.chat.type == ChatType.CHANNEL: prefix = "📢 Channel"
                        chat_info = f"{prefix}: <b>{html.escape(chat_label)}</b>"
                        msg_text = update.text or update.caption or "[No Text/Media]"
                    
                    # ✅ UNIVERSAL: Always decompress callback data (for both inline AND regular messages)
                    actual_data = cb_data
                    if isinstance(update, CallbackQuery) and cb_data and "#" in cb_data:
                        import re
                        from Main.core.ext.callback_helpers import get_callback_data
                        parts = cb_data.split("#")
                        if len(parts) > 1 and len(parts[1]) == 12:
                            try:
                                unhashed = await get_callback_data(parts[1])
                                if unhashed:
                                    actual_data = unhashed
                            except Exception: pass
                    
                    # ✅ UNIVERSAL: Extract session index from decompressed data
                    session_idx = -1
                    if isinstance(update, CallbackQuery):
                        import re as _re
                        _si_match = _re.search(r"si=(-?\d+)", actual_data)
                        if _si_match:
                            session_idx = int(_si_match.group(1))
                    
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
                    elif isinstance(update, CallbackQuery) and not update.message:
                        # ✅ Inline mode: decode inline_message_id first, then cache, then callback data
                        chat_title = None
                        resolved_chat_id = None
                        
                        # ✅ PRIMARY: Decode inline_message_id to get real chat_id
                        if hasattr(update, "inline_message_id") and update.inline_message_id:
                            _raw_owner = _decode_inline_chat_id(update.inline_message_id)
                            if _raw_owner:
                                try:
                                    _c = args[0] if args and isinstance(args[0], Client) else None
                                    _cid_str, _ctitle, _cprefix = await _resolve_chat_from_owner_id(_raw_owner, _c or Altruix.bot, Altruix.clients)
                                    if _cid_str:
                                        resolved_chat_id = _cid_str
                                        chat_title = _ctitle
                                        chat_id = _cid_str
                                        chat_info = f"{_cprefix}: <b>{html.escape(_ctitle)}</b>"
                                except Exception: pass
                        
                        # FALLBACK: DB cache lookup
                        if not resolved_chat_id:
                            try:
                                if hasattr(update, "inline_message_id") and update.inline_message_id:
                                    from Main import Altruix as Ax
                                    cached_doc = await Ax.local_db.inline_col.find_one({"_id": update.inline_message_id})
                                    if cached_doc:
                                        if "chat_title" in cached_doc:
                                            chat_title = cached_doc["chat_title"]
                                        if "chat_id" in cached_doc and cached_doc["chat_id"] not in ["Inline", "N/A", "None", None]:
                                            resolved_chat_id = cached_doc["chat_id"]
                            except Exception: pass
                        
                        import re
                        from Main.core.ext.callback_helpers import get_callback_data
                        actual_data = cb_data
                        
                        # ✅ Unhash compressed callback data globally
                        if "#" in cb_data:
                            parts = cb_data.split("#")
                            if len(parts) > 1 and len(parts[1]) == 12:
                                try:
                                    unhashed = await get_callback_data(parts[1])
                                    if unhashed:
                                        actual_data = unhashed
                                except Exception: pass
                                
                        # Extract Session Index for Userbot Info
                        session_idx = -1
                        si_match = re.search(r"[\?&]si=(-?\d+)", actual_data)
                        if si_match:
                            session_idx = int(si_match.group(1))
                        
                        if not resolved_chat_id:
                            # Check cid=... (query param format)
                            if cid_match := re.search(r"cid=(-?\d+)", actual_data):
                                resolved_chat_id = cid_match.group(1)
                            # Check _cid... (embedded format)
                            elif cid_match := re.search(r"_cid(-?\d+)", actual_data):
                                resolved_chat_id = cid_match.group(1)
                        
                        if resolved_chat_id:
                            chat_id = str(resolved_chat_id)
                            chat_title = chat_title or "Group/Chat"
                            
                            if chat_title == "Group/Chat":
                                try:
                                    _c = args[0] if args and isinstance(args[0], Client) else None
                                    if _c:
                                        chat_obj = await _c.get_chat(int(chat_id))
                                        chat_title = chat_obj.title or chat_obj.first_name or "Chat"
                                except Exception:
                                    for ubot in Altruix.clients:
                                        try:
                                            chat_obj = await ubot.get_chat(int(chat_id))
                                            chat_title = chat_obj.title or chat_obj.first_name or "Chat"
                                            break
                                        except Exception: continue
                                        
                                # ✅ Save to DB on first successful fetch to prevent future network spam
                                if chat_title and chat_title != "Group/Chat" and hasattr(update, "inline_message_id") and update.inline_message_id:
                                    try:
                                        from Main import Altruix as Ax
                                        await Ax.local_db.inline_col.find_one_and_update(
                                            {"_id": update.inline_message_id},
                                            {"$set": {"_id": update.inline_message_id, "chat_title": chat_title, "chat_id": chat_id}},
                                            upsert=True
                                        )
                                    except Exception: pass
                                        
                            chat_info = f"📱 {html.escape(chat_title)}"
                    
                    ubot_session_name = "Unknown Session"
                    if 'session_idx' in locals() and session_idx != -1 and 0 <= session_idx < len(Altruix.clients):
                        _c = Altruix.clients[session_idx]
                        if hasattr(_c, 'me') and _c.me:
                            ubot_session_name = _c.me.first_name or _c.me.username or str(_c.me.id)
                    elif len(Altruix.clients) > 0:
                        _c = Altruix.clients[0]
                        if hasattr(_c, 'me') and _c.me:
                            ubot_session_name = _c.me.first_name or _c.me.username or str(_c.me.id)
                            
                    me = None
                    for arg in args:
                        if isinstance(arg, Client):
                            me = getattr(arg, "me", None)
                            break
                    bot_username = f"@{me.username}" if me and me.username else "Unknown Bot"
                    if me and not getattr(me, "is_bot", False):
                        bot_username = f"Userbot Session ({bot_username})"
                    
                    display_name = full_name.strip()
                    display_name = Essentials.clean_user_name(display_name)
                    is_blank = not display_name or display_name == "No name" or all(ord(ch) < 33 or ord(ch) == 8203 or ord(ch) == 12644 for ch in display_name)
                    final_name = "blank" if is_blank else html.escape(display_name)
                    username_display = f"@{username.lstrip('@')}" if username and username != "None" else "None"
                    if username_display != "None":
                        username_display = html.escape(username_display)
                    
                    try:
                        title = Altruix.get_string('LOGGER_CALLBACK_TITLE')
                        if isinstance(update, Message):
                            title = "🎯 <b>Message Access Denied</b>"
                        elif isinstance(update, InlineQuery):
                            title = "🎯 <b>Inline Access Denied</b>"
                            
                        disp_result = result_status
                        if len(disp_result) > 11:
                            disp_result = disp_result[:11] + "..."
                            
                        log_message = (
                            f"{title}\n"
                            f"<blockquote expandable>"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"{Altruix.get_string('LOGGER_CALLBACK_BOT').format(html.escape(me.username) if me and me.username else 'bot', html.escape(bot_username))}\n"
                            f"{Altruix.get_string('LOGGER_CALLBACK_USERBOT').format(html.escape(ubot_session_name)) if 'ubot_session_name' in locals() else ''}\n"
                            f"{Altruix.get_string('LOGGER_CALLBACK_USER').format(user_id, final_name)}\n"
                            f"{Altruix.get_string('LOGGER_CALLBACK_USERNAME').format(username_display)}\n"
                            f"{Altruix.get_string('LOGGER_CALLBACK_USER_ID').format(user_id)}\n"
                            f"{Altruix.get_string('LOGGER_CALLBACK_CHAT').format(chat_info)}\n"
                            f"{Altruix.get_string('LOGGER_CALLBACK_CHAT_ID').format(chat_id)}\n"
                            f"{Altruix.get_string('LOGGER_CALLBACK_DATA').format(html.escape(cb_data))}\n"
                            f"{Altruix.get_string('LOGGER_CALLBACK_RESULT').format(html.escape(disp_result))}\n"
                            f"{Altruix.get_string('LOGGER_CALLBACK_TIME').format(time_now)}\n"
                            f"{Altruix.get_string('LOGGER_CALLBACK_MSG_HEADER')}\n"
                            f"{html.escape(str(msg_text)[:1000])}"
                            f"</blockquote>"
                        )
                        link_url = ""
                        if hasattr(update, "message") and update.message and update.message.link:
                            link_url = update.message.link
                        elif chat_id and str(chat_id) not in ["Inline", "N/A", "None", None, ""]:
                            c_id_str = str(chat_id)
                            if c_id_str.startswith("-100"):
                                link_url = f"https://t.me/c/{c_id_str[4:]}/999999999"
                            elif not c_id_str.startswith("-"):
                                link_url = f"tg://openmessage?user_id={c_id_str}"
                                
                        from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                        from Main.utils.file_helpers import get_user_button_style as _gubs
                        
                        # Resolve userbot user ID for button style
                        _style_uid = 0
                        if 'session_idx' in locals() and session_idx != -1 and 0 <= session_idx < len(Altruix.clients):
                            _sc = Altruix.clients[session_idx]
                            if hasattr(_sc, 'me') and _sc.me:
                                _style_uid = _sc.me.id
                        _btn_style = _gubs(_style_uid) if _style_uid else None
                        
                        buttons = [InlineKeyboardButton("👤 Chat to User", url=f"tg://user?id={user_id}")]
                        if link_url:
                            buttons.append(InlineKeyboardButton("➡️ Goto Msg", url=link_url))
                        
                        if _btn_style:
                            for _b in buttons:
                                _b.style = _btn_style
                            
                        kbd = InlineKeyboardMarkup([buttons])
                        await send_log_message(log_message, reply_markup=kbd)
                    except Exception:
                        import traceback
                        _err_txt = f"❌ <b>Error in _log_denied:</b>\n\n<pre>{html.escape(traceback.format_exc())}</pre>\n\n#LOG_ERROR"
                        await send_log_message(_err_txt)
                        
                    # ✅ SECURE TAPPED BY UPDATE (ZERO-LEAK: NO RE-RENDER)
                    # Instead of re-rendering the menu (which caused leaks), 
                    # we ONLY swap the "Tapped By" name in the existing message text
                    # and REUSE the exact same reply_markup. No buttons regenerated = no leak.
                    if isinstance(update, CallbackQuery) and 'actual_data' in locals() and actual_data:
                        if actual_data.startswith("help") or actual_data.startswith("h#") or actual_data.startswith("ht#"):
                            try:
                                import re
                                msg = update.message
                                
                                if msg and (msg.text or msg.caption):
                                    # ═══ PATH A: REGULAR BOT MESSAGE (Zero-Leak Regex) ═══
                                    current_text = msg.text or msg.caption or ""
                                    current_markup = msg.reply_markup  # EXACT same buttons
                                    
                                    # Build tapper name
                                    t_name = f"{update.from_user.first_name} {update.from_user.last_name or ''}".strip()
                                    escaped_name = html.escape(t_name)
                                    
                                    # Reconstruct HTML from text + entities
                                    entities = msg.entities or msg.caption_entities or []
                                    if entities:
                                        # Use Pyrogram's built-in unparser
                                        try:
                                            from pyrogram.parser.html import HTML
                                            html_text = HTML.unparse(current_text, entities)
                                        except Exception:
                                            html_text = html.escape(current_text)
                                    else:
                                        html_text = html.escape(current_text)
                                    
                                    # Regex: replace only the clickable name after "•  Tapped by:" 
                                    t_name_raw = f"{update.from_user.first_name} {update.from_user.last_name or ''}".strip()
                                    if len(t_name_raw) > 11:
                                        t_name_raw = t_name_raw[:15] + "…"
                                    
                                    t_link = f"<a href='tg://user?id={update.from_user.id}'>{html.escape(t_name_raw)}</a>"
                                    
                                    # Match both Pyrogram unparsed HTML (<a href="...") and raw text
                                    new_text = re.sub(
                                        r'(•\s+Tapped by:</b>\s*)<a href=[\'"]tg://user\?id=\d+[\'"]>.*?</a\>(\s*«—)',
                                        rf'\g<1>{t_link}\g<2>',
                                        html_text,
                                        flags=re.IGNORECASE
                                    )
                                    
                                    # Fallback if tags got escaped or stripped
                                    if new_text == html_text:
                                        new_text = re.sub(
                                            r'(•\s+Tapped by:.*?)(?:<.*?>)*([^<]+)(?:<.*?>)*(\s*«—)',
                                            rf'\g<1>{html.escape(t_name_raw)}\g<3>',
                                            html_text,
                                            flags=re.IGNORECASE
                                        )
                                    
                                    if new_text != html_text:
                                        await update.edit_message_text(
                                            new_text,
                                            reply_markup=current_markup,  # ✅ SAME BUTTONS!
                                            parse_mode=ParseMode.HTML,
                                            disable_web_page_preview=True
                                        )
                                
                                elif not msg and update.inline_message_id:
                                    # ═══ PATH B: INLINE MESSAGE (DB-Backed Zero-Leak Re-render) ═══
                                    from Main import Altruix as Ax
                                    cached_state = await Ax.local_db.inline_col.find_one({"_id": update.inline_message_id})
                                    state_data = "help#_page?page=0&mode=userbot" # Default fallback
                                    if cached_state and "help_state" in cached_state:
                                        state_data = cached_state["help_state"]
                                        
                                    # Extracted cached state (the exact page the user is currently looking at)
                                    render_data = state_data
                                    if "#" in state_data:
                                        parts = state_data.split("#")
                                        if len(parts) > 1 and len(parts[1]) == 12:
                                            try:
                                                from Main.core.ext.callback_helpers import get_callback_data
                                                u = await get_callback_data(parts[1])
                                                if u: render_data = u
                                            except Exception: pass
                                            
                                    from Main.plugins.bot.help import get_help_menu, get_plugin_data
                                    
                                    # Extract page and mode from CURRENT VIEW STATE (render_data)
                                    _mode = "userbot"
                                    _mode_m = re.search(r"mode=(\w+)", render_data)
                                    if _mode_m: _mode = _mode_m.group(1)
                                    elif render_data.startswith("help_tab#"):
                                        _tab_m = re.search(r"^help_tab#([a-zA-Z0-9_]+)", render_data)
                                        if _tab_m: _mode = _tab_m.group(1)
                                        
                                    _page = 0
                                    _pg_m = re.search(r"page=(\d+)", render_data)
                                    if _pg_m: _page = int(_pg_m.group(1))
                                    
                                    _sub = 0
                                    _sub_m = re.search(r"sub=(\d+)", render_data)
                                    if _sub_m: _sub = int(_sub_m.group(1))
                                    
                                    _plugin = None
                                    if render_data.startswith("help#"):
                                        _p_m = re.search(r"^help#([a-zA-Z0-9_]+)", render_data)
                                        if _p_m and _p_m.group(1) != "_page":
                                            _plugin = _p_m.group(1)
                                            
                                    # Extract session index and chat ID from the button they ACTUALLY clicked (actual_data)
                                    # This ensures button styling matching their specific session index is correct
                                    _si = -1
                                    _si_m = re.search(r"si=(-?\d+)", actual_data)
                                    if _si_m: _si = int(_si_m.group(1))
                                    
                                    _cid = None
                                    _cid_m = re.search(r"cid=(-?\d+)", actual_data)
                                    if _cid_m: _cid = int(_cid_m.group(1))
                                    
                                    # Resolve owner from session index
                                    _owner = None
                                    if _si != -1 and 0 <= _si < len(Ax.clients):
                                        cl = Ax.clients[_si]
                                        if hasattr(cl, 'me') and cl.me: _owner = cl.me.id
                                        
                                    if _plugin:
                                        # Plugin detail view
                                        res = await get_plugin_data(
                                            _plugin, _page, sub_page=_sub, user_id=_owner, 
                                            chat_id=_cid, mode=_mode, 
                                            tapped_by=update.from_user
                                        )
                                        _text, _rm = res
                                        await update.edit_message_text(
                                            _text, reply_markup=_rm,
                                            parse_mode=ParseMode.HTML,
                                            disable_web_page_preview=True
                                        )
                                    else:
                                        # Main menu / category list
                                        _text, _btns, _pm = await get_help_menu(
                                            return_all=True, user_id=_owner, 
                                            chat_id=_cid, mode=_mode,
                                            tapped_by=update.from_user
                                        )
                                        # Pick the correct page
                                        if isinstance(_btns, list) and _btns and isinstance(_btns[0], list):
                                            if _btns[0] and isinstance(_btns[0][0], list):
                                                _rm = InlineKeyboardMarkup(_btns[_page] if _page < len(_btns) else _btns[0])
                                            else:
                                                _rm = InlineKeyboardMarkup(_btns)
                                        else:
                                            _rm = _btns if isinstance(_btns, InlineKeyboardMarkup) else InlineKeyboardMarkup(_btns)
                                            
                                        await update.edit_message_text(
                                            _text, reply_markup=_rm,
                                            parse_mode=_pm,
                                            disable_web_page_preview=True
                                        )
                                        
                            except MessageNotModified:
                                pass  # Text unchanged, ignore
                            except Exception as e:
                                Altruix.log(f"Failed to update tapped_by: {e}", level=30)
                        
                import asyncio as _asyncio
                _asyncio.create_task(_log_denied())

            if isinstance(update, CallbackQuery):
                try:
                    # ✅ FIX: Always use show_alert=True for unauthorized access popups
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
                # ✅ Only reply if it looks like a command to prevent spamming normal chat
                if getattr(update, "text", None) and update.text.startswith((".", "!", "/", "?")):
                    # Prevent DOUBLE responses if multiple groups trigger iuser_check
                    if not getattr(update, "_auth_denied_sent", False):
                        await update.reply_msg(Altruix.get_string("AUTH_FEATURE_DENIED"))
                        update._auth_denied_sent = True

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
            QueryIdInvalid,      # ✅ Added: Ignore expired queries
            PeerIdInvalid,       # ✅ Ignore: Handled compactly by resolve_peer/invoke
            ChannelInvalid       # ✅ Ignore: Handled compactly by resolve_peer/invoke
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
                    status = "Owner (Self)" if user_id in Altruix.config.OWNER_USERS_ID else ("Sudo" if user_id in Altruix._auth_users_cache else "User")
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
                            f"• <b>Reply to msg ID:</b> <code>{rm_id}</code>\n"
                            f"• <b>Reply to user:</b> {rm_user_info}\n"
                        )
                    else:
                        reply_info = "• <b>Reply to msg ID:</b> False\n• <b>Reply to user:</b> False\n"

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
                f"<b>⚠️ #LOG_ERROR</b>\n"
                f"<blockquote expandable>"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"• <b>CMD:</b> <code>{html.escape(str(msg_info)[:500])}</code>\n"
                f"• <b>CMD BY:</b> {user_info}\n"
                f"• <b>ACCOUNT:</b> {acc_info}\n"
                f"• <b>CHAT:</b> {chat_info}\n"
                f"{reply_info}" # ✅ Inject reply info
                f"• <b>TIME:</b> <code>{time_now}</code>\n"
                f"• <b>PLUGIN VER:</b> <code>{plugin_ver}</code>\n"
                f"• <b>USERBOT VER:</b> <code>{Altruix.__version__}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"</blockquote>\n"
                f"📍 <b>METHOD:</b>\n"
                f"<blockquote expandable>"
                f"• <b>Error:</b> <code>{_be}</code>\n"
                f"• <b>In:</b> <code>{module_name}.{func.__name__}</code>\n"
                f"</blockquote>\n"
                f"📑 <b>TRACEBACK:</b>\n"
                f"<pre>{html.escape(traceback.format_exc())}</pre>"
            )
            
            import asyncio as _asyncio

            # ✅ Notify user if possible (Edit "Processing..." message)
            # Check if there is a tracked "wait_msg" (Processing...) attached to the input message
            target_msg = getattr(u, "wait_msg", None)
            # Fallback to editing the command itself if no wait_msg, ONLY if it's self-authored
            if not target_msg and isinstance(u, Message) and u.from_user and u.from_user.is_self:
                target_msg = u

            # Capture `_be` in closure scope explicitly
            async def _log_and_notify(captured_err=_be):
                try:
                    # ✅ 0. Terminal Log (with account context)
                    Altruix.log(f"💥 [log_errors] Error in {module_name}.{func.__name__}: {captured_err}", level=40, client=c)
                    
                    # 1. Send Log to Group
                    sent_log = await send_log_message(error_detail, filename=f"error_{func.__name__}.txt")
                    
                    # 2. If we have a message to update, construct specific link and Edit
                    if target_msg and isinstance(target_msg, Message):
                        log_link = "Check Log Group"
                        if sent_log and sent_log.chat:
                            if sent_log.chat.username:
                                log_link = f"<a href='https://t.me/{sent_log.chat.username}/{sent_log.id}'>Check Log Message</a>"
                            else:
                                # Private/Private Group link format
                                log_link = f"<a href='https://t.me/c/{str(sent_log.chat.id)[4:]}/{sent_log.id}'>Check Log Message</a>"

                        try:
                            # ✅ FIX: Use reply_msg instead of edit if target_msg is the original command (u)
                            # to prevent conflict with auto-delete-cmd feature.
                            if target_msg == u:
                                await target_msg.reply_msg(
                                    f"<blockquote expandable>"
                                    f"<b>[ERROR] - Error Occurred!</b>\n"
                                    f"<i>•  Command failed during execution.</i>\n"
                                    f"» {log_link} «"
                                    f"</blockquote>",
                                    disable_web_page_preview=True
                                )
                            else:
                                await target_msg.edit(
                                    f"<blockquote expandable>"
                                    f"<b>[ERROR] - Error Occurred!</b>\n"
                                    f"<i>•  Command failed during execution.</i>\n"
                                    f"» {log_link} «"
                                    f"</blockquote>",
                                    disable_web_page_preview=True
                                )
                        except Exception:
                            pass
                except Exception as e:
                    Altruix.log(f"Error in _log_and_notify background task: {e}", level=40)

            _asyncio.create_task(_log_and_notify())

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
            log_msg = f"<blockquote expandable>🔍 <b>[inline_check] Entering decorator</b>\n• Function: <code>{func.__name__}</code>\n• User: {c.me.id if c.me else 'Unknown'}\n• Chat: {m.chat.id}</blockquote>"
            Altruix.log(f"🔍 [inline_check] Entering decorator for {func.__name__}", level=20)
            await send_log_message(log_msg)
            
            # ✅ FIX: Pass all arguments to the wrapped function
            result = await func(c, m, *args, **kwargs)
            
            # ✅ DEBUG: Log successful completion
            success_msg = f"<blockquote expandable>✅ <b>[inline_check] Completed successfully</b>\n• Function: <code>{func.__name__}</code></blockquote>"
            Altruix.log(f"✅ [inline_check] {func.__name__} completed successfully", level=20)
            await send_log_message(success_msg)
            return result
            
        except BotInlineDisabled as e:
            # Auto-enable inline mode and retry
            error_msg = f"<blockquote expandable>⚠️ <b>[inline_check] BotInlineDisabled</b>\n• Function: <code>{func.__name__}</code>\n• Action: Auto-enabling inline mode</blockquote>"
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
                f"<blockquote expandable>"
                f"❌ <b>[inline_check] Exception Caught</b>\n"
                f"• Function: <code>{func.__name__}</code>\n"
                f"• Exception: <code>{type(e).__name__}</code>\n"
                f"• Message: <code>{str(e)[:200]}</code>"
                f"</blockquote>"
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
