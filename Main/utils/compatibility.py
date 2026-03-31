# Main/utils/compatibility.py

import inspect
from pyrogram.types import ReplyParameters
import logging

logger = logging.getLogger("smart_send")

def smart_send(client, method_name: str, chat_id, *args, reply_to_message_id=None, **kwargs):
    """
    Kirim pesan/media apapun (message, photo, video, etc.) dengan parameter reply yang kompatibel.

    Args:
        client: Pyrogram Client
        method_name: Nama method, misal: "send_message", "send_photo", "send_video", dll.
        chat_id: ID chat tujuan
        *args: Argumen utama (misalnya: text, photo path, video path)
        reply_to_message_id: ID pesan yang ingin direply (opsional)
        **kwargs: Keyword arguments lainnya (caption, reply_markup, parse_mode, etc.)

    Returns:
        Hasil dari method yang dipanggil (misal: Message)
    """
    # Ambil method dari client
    method = getattr(client, method_name, None)
    if not method:
        raise AttributeError(f"Client tidak memiliki method '{method_name}'")

    # Jika tidak ada reply, panggil method langsung
    if reply_to_message_id is None:
        return method(chat_id=chat_id, *args, **kwargs)

    # Periksa signature method untuk cek apakah menerima 'reply_parameters'
    sig = inspect.signature(method)
    if 'reply_parameters' in sig.parameters:
        # ✅ Gunakan reply_parameters (Pyrogram v2.0.106+)
        reply_params = ReplyParameters(message_id=reply_to_message_id)
        return method(chat_id=chat_id, *args, reply_parameters=reply_params, **kwargs)
    else:
        # ❌ Fallback ke reply_to_message_id (Pyrogram versi lama)
        return method(chat_id=chat_id, *args, reply_to_message_id=reply_to_message_id, **kwargs)
