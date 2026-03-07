# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.

"""
Global Exception Handler for Pyrogram Dispatcher Errors
Catches errors that occur in Pyrogram's internal message parser
"""

import logging
import traceback
import asyncio
import time
from pyrogram.errors import PeerIdInvalid, ChannelInvalid
from pyrogram import Client

logger = logging.getLogger("Altruix")


# Global state to avoid circular imports
_ALTRUIX_INST = None

def get_session_info(client):
    """Extract session information from client"""
    try:
        if hasattr(client, 'me') and client.me:
            client_name = client.me.first_name or "Unknown"
            client_id = client.me.id
            client_username = f"@{client.me.username}" if client.me.username else "No username"
            
            # Get session index
            try:
                if _ALTRUIX_INST:
                    total_sessions = len(_ALTRUIX_INST.clients)
                    current_index = None
                    for idx, c in enumerate(_ALTRUIX_INST.clients, start=1):
                        if hasattr(c, 'me') and c.me and c.me.id == client_id:
                            current_index = idx
                            break
                    if current_index:
                        session_index = f"{current_index}/{total_sessions}"
                    else:
                        session_index = f"?/{total_sessions}"
                else:
                    session_index = "?/?"
            except:
                session_index = "?/?"
            
            return f"[{session_index}] {client_name} (ID: {client_id}, {client_username})"
        elif hasattr(client, 'name'):
            return f"[?/?] {client.name}"
    except:
        pass
    return "[?/?] Unknown Client"


def handle_peer_id_invalid(error, client, context="Unknown"):
    """Handle PEER_ID_INVALID error with compact logging"""
    session_info = get_session_info(client)
    
    # Extract peer ID from error
    peer_id = "Unknown"
    error_str = str(error)
    if "ID not found:" in error_str:
        try:
            peer_id = error_str.split("ID not found:")[1].strip().strip("'\"")
        except:
            pass
    
    # Compact log (one-liner)
    if _ALTRUIX_INST:
        _ALTRUIX_INST.log(
            f"⚠️ [Dispatcher-PeerIdInvalid] Peer: {peer_id} | Context: {context} | "
            f"💡 Solution: Send a message to this chat First with this account to refresh cache.",
            level=logging.WARNING,
            client=client
        )
    else:
        logger.warning(
            f"⚠️ [Dispatcher-PeerIdInvalid] {session_info} | Peer: {peer_id} | Context: {context} | "
            f"💡 Solution: Send a message to this chat First with this account to refresh cache."
        )


def handle_channel_invalid(error, client, context="Unknown"):
    """Handle CHANNEL_INVALID error with compact logging"""
    session_info = get_session_info(client)
    
    # Compact log
    if _ALTRUIX_INST:
        _ALTRUIX_INST.log(
            f"⚠️ [Dispatcher-ChannelInvalid] Context: {context} | "
            f"💡 Solution: Check if Joined or if Channel ID is correct.",
            level=logging.WARNING,
            client=client
        )
    else:
        logger.warning(
            f"⚠️ [Dispatcher-ChannelInvalid] {session_info} | Context: {context} | "
            f"💡 Solution: Check if Joined or if Channel ID is correct."
        )


def install_exception_handler(altruix_instance=None):
    """
    Docstring:
    Memasang handler global untuk error dispatcher Pyrogram.
    - Monkey-patch resolve_peer agar log mencakup informasi sesi
    - Debounce refresh dialogs di background saat PeerIdInvalid terdeteksi,
      untuk membantu membangun cache peer tanpa memblokir jalur eksekusi
    """
    global _ALTRUIX_INST
    if altruix_instance:
        _ALTRUIX_INST = altruix_instance

    from pyrogram.methods.advanced.resolve_peer import ResolvePeer
    
    # Store original resolve_peer from the Mixin class itself
    original_resolve_peer = ResolvePeer.resolve_peer
    _LAST_REFRESH = {}
    
    async def _refresh_dialogs_debounced(client):
        """
        Docstring:
        Memicu refresh dialogs secara terkontrol (debounced) untuk memperbarui
        storage peer. Jika baru saja dilakukan, akan di-skip.
        """
        try:
            me_id = client.me.id if hasattr(client, "me") and client.me else None
            now = time.time()
            last = _LAST_REFRESH.get(me_id, 0)
            # Minimal interval 120 detik antar refresh
            if now - last < 120:
                return
            _LAST_REFRESH[me_id] = now
            # Jalankan tanpa memblokir resolve_peer
            async def _do():
                try:
                    async for _ in client.get_dialogs():
                        break
                except Exception:
                    pass
            asyncio.create_task(_do())
        except Exception:
            pass
    
    async def wrapped_resolve_peer(self, peer_id):
        """Docstring: Bungkus resolve_peer dengan logging sesi + refresh dialogs debounce"""
        try:
            return await original_resolve_peer(self, peer_id)
        except PeerIdInvalid as e:
            # Log with session info
            handle_peer_id_invalid(e, self, context="resolve_peer")
            # Jadwalkan refresh dialogs untuk membantu cache peer
            try:
                await _refresh_dialogs_debounced(self)
            except Exception:
                pass
            # Re-raise to maintain original behavior
            raise
        except ChannelInvalid as e:
            # Log with session info
            handle_channel_invalid(e, self, context="resolve_peer")
            # Re-raise to maintain original behavior
            raise
        except Exception as e:
            # Log other errors with session info (Compact)
            if _ALTRUIX_INST:
                _ALTRUIX_INST.log(f"⚠️ [Dispatcher-Error] resolve_peer failed: {e}", level=logging.WARNING, client=self)
            else:
                session_info = get_session_info(self)
                logger.warning(f"⚠️ [Dispatcher-Error] Session: {session_info} | resolve_peer failed: {e}")
            # Re-raise to maintain original behavior
            raise
    
    # ✅ DEEP PATCH: Replace on the Mixin class directly. 
    # This affects pyrogram.Client because it inherits from ResolvePeer.
    ResolvePeer.resolve_peer = wrapped_resolve_peer
    
    # Also ensure Client's own reference is updated if it was already bound/copied
    from pyrogram import Client
    Client.resolve_peer = wrapped_resolve_peer
    
    # ✅ DEEP PATCH 2: Intercept Pyrogram's internal Dispatcher exception logging
    import pyrogram.dispatcher
    import inspect
    orig_log = pyrogram.dispatcher.log

    class PyrogramLogProxy:
        def getattr(self, name):
            return getattr(orig_log, name)
            
        def _get_context_client(self):
            try:
                for frame_record in inspect.stack():
                    locals_dict = frame_record.frame.f_locals
                    if 'self' in locals_dict:
                        obj = locals_dict['self']
                        if type(obj).__name__ == "Dispatcher" and hasattr(obj, 'client'):
                            return obj.client
            except Exception:
                pass
            return None

        def exception(self, msg, *args, **kwargs):
            self.error(msg, *args, exc_info=True, **kwargs)

        def error(self, msg, *args, **kwargs):
            try:
                client = self._get_context_client()
                
                if _ALTRUIX_INST and client:
                    exc_info = kwargs.get('exc_info')
                    if exc_info:
                        if isinstance(exc_info, tuple) and len(exc_info) >= 2:
                            exc = exc_info[1]
                        elif isinstance(exc_info, Exception):
                            exc = exc_info
                        else:
                            # fallback fetch from sys.exc_info if strictly True
                            import sys
                            exc = sys.exc_info()[1]
                            
                        if exc:
                            # Pass to Altruix logger which formats properly with session context
                            _ALTRUIX_INST.log(exc, level=logging.ERROR, client=client)
                            return
                            
                    _ALTRUIX_INST.log(f"⚠️ [Dispatcher-Unhandled] {msg}", level=logging.ERROR, client=client)
                    return
            except Exception:
                pass
            orig_log.error(msg, *args, **kwargs)
            
        def __getattr__(self, name):
            return getattr(orig_log, name)

    pyrogram.dispatcher.log = PyrogramLogProxy()

    logger.info("✅ Global exception handler installed for Pyrogram dispatcher (Deep Patch)")
