"""
Monkey-patch untuk Pyrogram agar kompatibel dengan reply_to_message_id dan reply_parameters.
Dengan proteksi FloodWait yang lebih baik.
"""
import inspect
import functools
import asyncio
from typing import Dict, Any, Optional
from pyrogram.types import ReplyParameters
from pyrogram.errors import FloodWait

# Cache untuk mengecek dukungan
_SUPPORTS_REPLY_PARAMETERS = None

def _check_reply_parameters_support():
    """Cek apakah Pyrogram mendukung reply_parameters."""
    global _SUPPORTS_REPLY_PARAMETERS
    if _SUPPORTS_REPLY_PARAMETERS is None:
        from pyrogram import Client
        sig = inspect.signature(Client.send_message)
        _SUPPORTS_REPLY_PARAMETERS = 'reply_parameters' in sig.parameters
    return _SUPPORTS_REPLY_PARAMETERS

def _normalize_reply_params(
    reply_to_message_id: Optional[int] = None,
    reply_parameters: Optional[ReplyParameters] = None,
    chat_id: Optional[int] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Normalisasi parameter reply untuk semua method pengiriman.
    """
    if _check_reply_parameters_support():
        # Versi baru Pyrogram (>2.0) - gunakan reply_parameters
        if reply_parameters is not None:
            return {'reply_parameters': reply_parameters}
        elif reply_to_message_id is not None:
            # Convert reply_to_message_id ke ReplyParameters
            return {
                'reply_parameters': ReplyParameters(
                    message_id=reply_to_message_id,
                    chat_id=chat_id,
                    allow_sending_without_reply=kwargs.get('allow_sending_without_reply', True)
                )
            }
        return {}
    else:
        # Versi lama Pyrogram (<2.0) - gunakan reply_to_message_id
        if reply_to_message_id is not None:
            return {'reply_to_message_id': reply_to_message_id}
        return {}

# Method-method yang perlu di-patch
_METHODS_TO_PATCH = [
    'send_message',
    'send_photo',
    'send_video',
    'send_document',
    'send_audio',
    'send_voice',
    'send_sticker',
    'send_animation',
    'send_location',
    'send_contact',
    'send_poll',
    'send_dice',
    'send_inline_bot_result',
    'send_cached_media',
    'send_chat_action',
    'copy_message',
    'forward_messages',
    'edit_message_text',
    'edit_message_caption',
    'edit_message_media',
    'edit_message_reply_markup'
]

def _create_patched_method(original_method):
    """Buat method yang sudah di-patch dengan handling reply parameters DAN FloodWait."""
    @functools.wraps(original_method)
    async def patched_method(self, *args, **kwargs):
        # EKSTRAK chat_id dari args/kwargs
        chat_id = kwargs.get('chat_id')
        if not chat_id and len(args) > 0:
            chat_id = args[0]
        
        # Ekstrak parameter reply
        reply_to_message_id = kwargs.pop('reply_to_message_id', None)
        reply_parameters = kwargs.pop('reply_parameters', None)
        
        # Normalisasi parameter reply
        reply_params = _normalize_reply_params(
            reply_to_message_id=reply_to_message_id,
            reply_parameters=reply_parameters,
            chat_id=chat_id,
            **kwargs
        )
        
        # Gabungkan semua parameter
        all_kwargs = {**kwargs, **reply_params}
        
        # **TAMBAHAN: Proteksi FloodWait untuk method tertentu**
        # Hanya untuk method yang berpotensi menyebabkan FloodWait
        if original_method.__name__ in [
            'send_message', 'send_photo', 'send_video', 'send_document',
            'send_audio', 'forward_messages', 'copy_message'
        ]:
            try:
                return await original_method(self, *args, **all_kwargs)
            except FloodWait as e:
                # Log FloodWait dan tunggu sesuai yang diminta Telegram
                if hasattr(self, 'log'):
                    self.log(f"FloodWait: Menunggu {e.value} detik", level=30)
                await asyncio.sleep(e.value)
                # Coba lagi setelah menunggu
                return await original_method(self, *args, **all_kwargs)
        else:
            # Untuk method lain, langsung panggil tanpa proteksi khusus
            return await original_method(self, *args, **all_kwargs)
    
    return patched_method

def patch_pyrogram_client(client):
    """
    Patch sebuah instance Client Pyrogram untuk otomatis handle reply parameters.
    
    Args:
        client: Instance Pyrogram Client yang akan di-patch
    
    Returns:
        Client yang sudah di-patch
    """
    for method_name in _METHODS_TO_PATCH:
        if hasattr(client, method_name):
            original_method = getattr(client, method_name)
            patched_method = _create_patched_method(original_method)
            setattr(client, method_name, patched_method)
    
    return client

def patch_client_class():
    """
    Patch class Client Pyrogram secara langsung (lebih agresif).
    **WARNING**: Hanya gunakan jika Anda yakin!
    """
    from pyrogram import Client
    for method_name in _METHODS_TO_PATCH:
        if hasattr(Client, method_name):
            original_method = getattr(Client, method_name)
            patched_method = _create_patched_method(original_method)
            setattr(Client, method_name, patched_method)
    
    return Client
