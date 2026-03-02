# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.


import os
import asyncio
import time
import random
from Main import Altruix
from typing import Union
from pyrogram import Client, raw
from pyrogram.types import ChatMember
from ...utils.file_utils import FileHelpers
from ...utils.startup_helpers import monkeypatch
from pyrogram.errors.exceptions import FloodWait, SlowmodeWait


@monkeypatch(Client)
class CustomClientMethods:
    """
    Docstring:
    Menyediakan method kustom untuk Client, termasuk mekanisme anti-hang.
    Fitur utama:
    - Circuit breaker sederhana berbasis cooldown per operasi (mis. GetChannelDifference)
    - Backoff dengan jitter untuk retry agar tidak menyebabkan bottleneck
    - Skipping aman untuk operasi non-kritis saat timeout berulang
    - Sync Serialization: Mencegah Thundering Herd (banyak sync op sekaligus) per client.
    """
    
    # Static/Global registry to serialize sync operations across sessions/invokes
    _SYNC_LOCKS = {}

    def __init__(self) -> None:
        super().__init__()
        # Cooldown global per sesi + operasi: { (client_id, op_name): expires_ts }
        if not hasattr(Altruix, "_TIMEOUT_COOLDOWNS"):
            Altruix._TIMEOUT_COOLDOWNS = {}

    async def get_group(self, *args, **kwargs):
        chat_obj = await self.get_chat(*args, **kwargs)
        if str(chat_obj.type).lower().startswith("chattype."):
            chat_type = str((str(chat_obj.type).lower()).split("chattype.")[1])
            chat_obj.type = chat_type
        return chat_obj

    async def invoke(self, *args, **kwargs):
        """
        Executes API calls with advanced resilience features:
        - Exponential backoff with jitter for transient errors (Timeout, FloodWait).
        - Fast Sync Retry: Prioritizes dispatcher fluidity during update synchronization.
        - Resilient Dummy Results: Prevents plugin crashes by returning empty objects instead of None.
        - Sync Serialization: Prevents the 'Thundering Herd' effect (too many concurrent sync probes).
        - Circuit Breaker: Temporarily silences failing operations to protect system stability.
        """
        op = args[0]
        op_name = type(op).__name__
        
        # 1. Gather client/session context for logging and tracking
        client_id = getattr(self, "me", None).id if getattr(self, "me", None) else None
        
        try:
            if hasattr(self, '_index'):
                current_index = self._index + 1
                total_sessions = len(Altruix.clients)
                session_index = f"{current_index}/{total_sessions}"
            else:
                session_index = "N/A"
            client_info = f"{self.me.first_name} (ID: {client_id})" if client_id else "Unbound"
        except:
            client_info = "Unknown Client"
            session_index = "?/?"
        
        # 2. CIRCUIT BREAKER: If this operation is in a cooldown period for this client, skip it
        # This prevents the bot from repeatedly failing and logging known issues during turbulence.
        if client_id:
            key = (client_id, op_name)
            cooldowns = getattr(Altruix, "_TIMEOUT_COOLDOWNS", None)
            if cooldowns is None:
                Altruix._TIMEOUT_COOLDOWNS = {}
                cooldowns = Altruix._TIMEOUT_COOLDOWNS
            exp = cooldowns.get(key)
            now = time.time()
            if exp and exp > now:
                remain = int(exp - now)
                Altruix.log(f"[Timeout-Cooldown] Session: [{session_index}] {client_info} | {op_name} skipped ({remain}s remaining)", level=30)
                return self._get_dummy_result(op_name)

        # 3. DEFINE NON-CRITICAL OPERATIONS: These can safely return dummy/empty objects if they fail.
        # This prevents one failing plugin from hanging the entire dispatcher or causing AttributeError.
        non_critical_ops = [
            "messages.GetMessages",
            "GetMessages",
            "GetForumTopicsByID",
            "GetChannel",
            "GetFullChannel",
            "GetHistory",
            "channels.GetChannels",
            "GetFullUser",
            "messages.DeleteMessages",
            "messages.EditMessage",
            "messages.EditInlineBotMessage",
            "updates.GetChannelDifference", # ✅ SAFE TO SKIP: Crucial to prevent sync-induced hangs
            "GetChannelDifference",
        ]

        # 4. METADATA INITIALIZATION
        error_str = ""
        is_timeout = False
        is_update_sync = op_name.startswith("updates.") or "GetChannelDifference" in op_name
        is_non_critical = op_name in non_critical_ops
        
        # 5. SYNC SERIALIZATION (Anti-Thundering Herd)
        # We use a per-client lock for sync operations to ensure they don't drown the event loop
        # when multiple sessions experience network lag at the same time.
        sync_lock_ctx = None
        if is_update_sync and client_id:
            lock_key = (client_id, "sync_lock")
            if lock_key not in self._SYNC_LOCKS:
                self._SYNC_LOCKS[lock_key] = asyncio.Lock()
            sync_lock_ctx = self._SYNC_LOCKS[lock_key]

        max_count = 0
        mmax_ = 5 # Maximum number of retry attempts for transient errors
        backoff = 1.0 # Initial backoff delay
        
        # 6. MAIN EXECUTION LOOP
        while True:
            try:
                # Execute with serialization if it's a synchronization operation
                if sync_lock_ctx:
                    async with sync_lock_ctx:
                        result = await self.__send_custom__(*args, **kwargs)
                else:
                    result = await self.__send_custom__(*args, **kwargs)
                
                # ✅ FIX FOR DISPATCHER CRASH (BadMsgNotification)
                # Sometimes Telegram returns a notification instead of requested data.
                # Accessing .users or .messages on such objects crashes the Pyrogram dispatcher.
                if is_update_sync and isinstance(result, (raw.types.BadMsgNotification, raw.types.BadServerSalt)):
                    Altruix.log(f"[Sync-BadResult] Session: [{session_index}] {client_info} | {op_name} returned {type(result).__name__}. Forcing retry...", level=30)
                    raise asyncio.TimeoutError(f"Bad MTProto sync result: {type(result).__name__}")
                
                return result
                
            except (FloodWait, SlowmodeWait) as e:
                # 7. TELEGRAM THROTTLING: Handle FloodWait/SlowmodeWait
                if max_count > mmax_:
                    raise e
                wait_time = e.value + 3 # Add a 3s safety buffer
                Altruix.log(f"[{e.__class__.__name__}] Session: [{session_index}] {client_info} | sleeping for - {wait_time}s.")
                await asyncio.sleep(wait_time)
                max_count += 1
            except Exception as e:
                # 8. GENERAL EXCEPTION HANDLING
                error_str = str(e)
                error_type = type(e).__name__
                
                # Determine error characteristics
                is_timeout = "TimeoutError" in error_type or isinstance(e, asyncio.TimeoutError)
                
                # Check if this operation should be treated as sync or non-critical based on error content
                if not is_update_sync:
                    is_update_sync = any(x in error_str for x in ["updates.GetChannelDifference", "updates.GetDifference"])
                if not is_non_critical:
                    is_non_critical = any(op in error_str for op in non_critical_ops)
                
                # ✅ CHANNEL/PEER ERRORS: Handle gracefully if non-critical
                # These often happen when a peer is deleted or unreachable.
                if "CHANNEL_INVALID" in error_str or "PEER_ID_INVALID" in error_str:
                    if is_non_critical:
                        Altruix.log(f"[NonCritical-Skipped] Session: [{session_index}] {client_info} | {error_type}: {error_str[:150]}", level=30)
                        return self._get_dummy_result(op_name)
                    # For critical ops, we still raise it as it might be a legitimate fatal error for that task
                    raise e
                
                # ✅ TIMEOUT LOGIC: Handle network/latency issues
                if is_timeout:
                    if max_count < mmax_:
                        # Fast sync retry: Small delay for sync ops to keep dispatcher moving
                        if is_update_sync:
                            wait_time = 0.1 + random.uniform(0.05, 0.2) if max_count == 0 else min(backoff, 3)
                        else:
                            # Gradual exponential backoff with jitter for standard operations
                            wait_time = min(backoff * 1.5, 10) + random.uniform(0.1, 1.0)
                            
                        Altruix.log(f"[Timeout-Retry] Session: [{session_index}] {client_info} | {op_name} ({max_count+1}/{mmax_}) | {error_str[:100]}", level=30)
                        await asyncio.sleep(wait_time)
                        max_count += 1
                        backoff = min(backoff * 2, 8)
                        continue
                    else:
                        # RETRIES EXHAUSTED: Protect stability by skipping instead of crashing
                        if is_update_sync:
                            Altruix.log(f"[Critical-Timeout-Failed] Session: [{session_index}] {client_info} | {op_name} aborted after {mmax_} retries. Providing dummy.", level=40)
                            return self._get_dummy_result(op_name)
                        
                        if is_non_critical:
                            Altruix.log(f"[NonCritical-Timeout-Skipped] Session: [{session_index}] {client_info} | {op_name} skipped. Providing dummy.", level=30)
                            # Enable circuit breaker cooldown for this specific operation
                            if client_id:
                                if not hasattr(Altruix, "_TIMEOUT_COOLDOWNS"): Altruix._TIMEOUT_COOLDOWNS = {}
                                Altruix._TIMEOUT_COOLDOWNS[(client_id, op_name)] = time.time() + 30
                            return self._get_dummy_result(op_name)
                        raise e
                
                # ✅ PERMANENT ERRORS: Identify errors that will not resolve with retries
                permanent_errors = [
                    "MessageIdsEmpty", "MessageEmpty", "MessageIdInvalid", 
                    "UserNotParticipant", "ChatWriteForbidden", "UserIsBlocked",
                    "PeerIdInvalid", "ChannelInvalid", "PEER_ID_INVALID", "CHANNEL_INVALID"
                ]
                # KeyError during peer lookup is also permanent
                is_key_error_peer = isinstance(e, KeyError) and "ID not found" in str(e)
                is_permanent = is_key_error_peer or any(x in error_type for x in permanent_errors) or any(x in error_str for x in permanent_errors)
                
                if is_permanent:
                    if is_non_critical:
                        Altruix.log(f"[NonCritical-Permanent-Skipped] Session: [{session_index}] {client_info} | {error_type}: {error_str[:150]}", level=30)
                        return self._get_dummy_result(op_name)
                    raise e
                
                # ✅ FINAL FALLBACK: General retry for unexpected errors
                if max_count < mmax_:
                    Altruix.log(f"[Error-Retry] Session: [{session_index}] {client_info} | {error_type} ({max_count+1}/{mmax_}) | {error_str[:100]}", level=30)
                    await asyncio.sleep(1.5 + random.uniform(0.1, 0.5))
                    max_count += 1
                    continue
                    
                # If everything failed but it's non-critical, stay graceful
                if is_non_critical:
                    Altruix.log(f"[NonCritical-RetryExhausted-Skipped] Session: [{session_index}] {client_info} | {op_name} skipped after {mmax_} retries.", level=30)
                    return self._get_dummy_result(op_name)
                raise e

    def _get_dummy_result(self, op_name: str):
        """
        Returns a dummy empty object for MTProto operations to prevent plugin crashes.
        Each object is initialized with minimal required fields for its respective type.
        """
        # A. MESSAGE LISTS: Returns empty Messages object with topics support for Layer 158+
        if op_name.endswith(".GetMessages") or op_name == "GetMessages":
            try:
                # Newer layouts require 'topics' argument
                return raw.types.messages.Messages(messages=[], users=[], chats=[], topics=[])
            except TypeError:
                # Backward compatibility for older Pyrogram/MTProto versions
                return raw.types.messages.Messages(messages=[], users=[], chats=[])
                
        # B. USER LISTS: Returns an empty list
        if op_name.endswith(".GetUsers") or op_name == "GetUsers":
            return []
            
        # C. USER PROFILES: Returns a minimal UserFull structure
        if op_name.endswith(".GetFullUser") or op_name == "GetFullUser":
            # Very basic dummy for UserFull
            try:
                return raw.types.users.UserFull(
                    full_user=raw.types.UserFull(id=0, about="", settings=raw.types.PeerSettings()),
                    users=[], chats=[]
                )
            except:
                return None

        # D. UPDATE SYNCHRONIZATION: Essential to prevent dispatcher hangs during sync failure
        if "GetChannelDifference" in op_name:
            # final=True indicates there's no more data to fetch, finishing the sync process.
            return raw.types.updates.ChannelDifferenceEmpty(final=True, pts=0, timeout=0)
            
        return None

    async def send_file(
        self: Client,
        entity: Union[str, int],
        file_path: str,
        thumb: str = None,
        *args,
        **kwargs,
    ):
        file_ = FileHelpers(file_path, self)
        if file_.is_photo:
            file_path = await file_._resize_if_req()
            return await self.send_photo(entity, file_path, *args, **kwargs)
        if file_.is_sticker or file_.is_animated_sticker:
            return await self.send_sticker(entity, file_path, *args, **kwargs)
        if file_.is_video:
            dur, width, height = await file_._get_metadata(is_audio=False)
            return await self.send_video(
                entity,
                file_path,
                thumb=thumb,
                duration=dur,
                width=width,
                height=height,
                *args,
                **kwargs,
            )
        if file_.is_audio:
            dur, title = await file_._get_metadata()
            return await self.send_audio(
                entity,
                file_path,
                thumb=thumb,
                duration=dur,
                title=title,
                *args,
                **kwargs,
            )
        if file_.is_audio_note:
            dur, title = await file_._get_metadata()
            return await self.send_voice(
                entity, file_path, duration=dur, *args, **kwargs
            )
        return await self.send_document(entity, file_path, thumb=thumb, *args, **kwargs)

    async def upload_doc(self, file_: str, peer_, force_file=False):
        uploaded_doc = await self.save_file(file_)
        chat_pperr = peer_
        mime_ = self.guess_mime_type(file_)
        media = raw.types.InputMediaUploadedDocument(
            mime_type=mime_,
            file=uploaded_doc,
            force_file=force_file,
            attributes=[
                raw.types.DocumentAttributeFilename(file_name=os.path.basename(file_))
            ],
        )
        uploaded_media_ = await self.invoke(
            raw.functions.messages.UploadMedia(peer=chat_pperr, media=media)
        )
        if os.path.exists(file_):
            os.remove(file_)
        return raw.types.InputDocument(
            id=uploaded_media_.document.id,
            access_hash=uploaded_media_.document.access_hash,
            file_reference=uploaded_media_.document.file_reference,
        )

    async def fetch_chats(self: Client):
        return [
            x
            async for x in self.get_dialogs()
            if (not x.chat.type.PRIVATE or not x.chat.type.BOT)
        ]

    async def check_my_perm(self, msg, perm_type):
        my_id = self.myself.id
        chat = msg.chat
        u_args = msg.user_args
        if (
            ("-no-cache" not in u_args)
            and Altruix.SELF_PERMISSION_CACHE.get(chat.id)
            and Altruix.SELF_PERMISSION_CACHE.get(chat.id).get(my_id)
        ):
            perms_json = Altruix.SELF_PERMISSION_CACHE[chat.id][my_id]
        else:
            try:
                c: Client = msg._client
                ps: ChatMember = await c.get_chat_member(chat.id, my_id)
            except Exception:
                return None, None
            perms_json = {
                "chat": chat.id,
                "can_delete_messages": True
                if ps.status.OWNER
                else ps.privileges.can_delete_messages,
                "can_restrict_members": True
                if ps.status.OWNER
                else ps.privileges.can_restrict_members,
                "can_promote_members": True
                if ps.status.OWNER
                else ps.privileges.can_promote_members,
                "can_change_info": True
                if ps.status.OWNER
                else ps.privileges.can_change_info,
                "can_invite_users": True
                if ps.status.OWNER
                else ps.privileges.can_invite_users,
                "can_pin_messages": True
                if ps.status.OWNER
                else ps.privileges.can_pin_messages,
                "can_manage_voice_chats": True
                if ps.status.OWNER
                else ps.privileges.can_manage_video_chats,
                "is_anonymous": True if ps.status.OWNER else ps.privileges.is_anonymous,
                "can_be_edited": ps.can_be_edited,
            }
            if not Altruix.SELF_PERMISSION_CACHE.get(chat.id):
                Altruix.SELF_PERMISSION_CACHE[chat.id] = {}
            Altruix.SELF_PERMISSION_CACHE[chat.id][my_id] = perms_json
        return perms_json[perm_type], perms_json
