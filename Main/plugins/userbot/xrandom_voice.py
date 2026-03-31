# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.

PLUGIN_VERSION = "1.0.10"

import os
import html
import json
import random
import asyncio
import tempfile
from datetime import datetime
from Main import Altruix
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from Main.utils.file_helpers import get_db_path

# ====================== DATA HELPERS ======================
RVOICE_FILE = get_db_path("rvoice_channels.json")
rvoice_tracked_db = Altruix.db.make_collection("rvoice_tracked")

# Default channel (pre-configured fallback)
DEFAULT_CHANNEL = "@desahancworizal"


def _load_rvoice_data() -> dict:
    """Load voice channel data from JSON database with migration support."""
    if not os.path.exists(RVOICE_FILE):
        return {}
    try:
        with open(RVOICE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Migration check: if old format (list), migrate to dict
            migrated = False
            for uid, val in list(data.items()):
                if isinstance(val, list):
                    data[uid] = {"channels": val, "autodel": False}
                    migrated = True
            if migrated:
                _save_rvoice_data(data)
            return data
    except Exception:
        return {}


def _save_rvoice_data(data: dict):
    """Save voice channel data to JSON database."""
    with open(RVOICE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def _get_channels(user_id: int) -> list:
    """Get channel list for a specific session (user_id)."""
    data = _load_rvoice_data()
    user_data = data.get(str(user_id), {})
    if isinstance(user_data, list): # Legacy fallback
        return user_data or [DEFAULT_CHANNEL]
    channels = user_data.get("channels", [])
    if not channels:
        return [DEFAULT_CHANNEL]
    return channels


def _add_channel(user_id: int, channel: str) -> bool:
    """Add a channel for the session. Returns False if already exists."""
    data = _load_rvoice_data()
    uid = str(user_id)
    if uid not in data:
        data[uid] = {"channels": [], "autodel": False}
    elif isinstance(data[uid], list): # Migrate on add
        data[uid] = {"channels": data[uid], "autodel": False}
    
    if channel in data[uid]["channels"]:
        return False
    data[uid]["channels"].append(channel)
    _save_rvoice_data(data)
    return True


def _remove_channel(user_id: int, channel: str) -> bool:
    """Remove a channel from the session. Returns False if not found."""
    data = _load_rvoice_data()
    uid = str(user_id)
    if uid not in data:
        return False
    
    user_data = data[uid]
    channels = user_data if isinstance(user_data, list) else user_data.get("channels", [])
    
    if channel not in channels:
        return False
    
    channels.remove(channel)
    if isinstance(user_data, dict):
        user_data["channels"] = channels
    _save_rvoice_data(data)
    return True


def _get_autodel_status(user_id: int) -> bool:
    """Get auto-delete status for a specific session."""
    data = _load_rvoice_data()
    user_data = data.get(str(user_id), {})
    if isinstance(user_data, list): return False
    return user_data.get("autodel", False)


def _set_autodel_status(user_id: int, status: bool):
    """Set auto-delete status for a specific session."""
    data = _load_rvoice_data()
    uid = str(user_id)
    if uid not in data:
        data[uid] = {"channels": [], "autodel": status}
    elif isinstance(data[uid], list):
        data[uid] = {"channels": data[uid], "autodel": status}
    else:
        data[uid]["autodel"] = status
    _save_rvoice_data(data)


# ====================== COMMAND HELP FOOTER ======================
RVOICE_HELP_TEXT = """
<b>🎙️ Random Voice Note — Help</b>

<b>Cara penggunaan:</b>

<blockquote>
<b>.rvoice</b>
→ Reply ke pesan apapun, bot akan mengirim voice note acak (tanpa caption).

<b>.rvoice [caption]</b>
→ Voice note dikirim dengan caption sesuai teks yang kamu tulis.
→ Contoh: <code>.rvoice wkwkwk takut ga? 😈</code>

<b>.rvoice add &lt;channel&gt;</b>
→ Tambahkan channel sebagai sumber voice note.
→ Contoh: <code>.rvoice add @username</code>
→ Contoh: <code>.rvoice add -1001234567890</code>

<b>.rvoice del &lt;channel&gt;</b>
→ Hapus channel dari daftar sumber.
→ Contoh: <code>.rvoice del @username</code>

<b>.rvoice list</b>
→ Tampilkan status fitur dan daftar channel sumber.

<b>.rvoice autodel &lt;on/off&gt;</b>
→ Aktifkan/Matikan fitur hapus otomatis.
→ Jika ON, voice note akan dihapus setelah user membalas pesan tersebut.

<b>.rvoice help</b>
→ Tampilkan halaman bantuan ini.
</blockquote>

<b>📌 Informasi Fitur:</b>
• <b>Auto-Delete:</b> Berguna agar chat tidak penuh. Bot akan menghapus voice note-nya sendiri segera setelah ada yang membalas (reply) ke pesan tersebut.
• <b>Default:</b> Jika daftar kosong, bot menggunakan <code>{}</code>
• <b>Limit:</b> Voice note dipilih acak dari 100 pesan terbaru di channel sumber.
• <b>Caption:</b> Bersifat opsional — kosongkan jika tidak diperlukan.
""".format(DEFAULT_CHANNEL).strip()


# ====================== UTILITY ======================
async def _fetch_random_voice(c: Client, channel: str, limit: int = 100):
    """
    Iterate channel history, collect voice/audio messages, return a random one.
    Returns the Message object or None if not found.
    """
    voices = []
    try:
        async for msg in c.get_chat_history(channel, limit=limit):
            if msg.voice:
                voices.append(msg)
    except Exception as e:
        return None, str(e)
    if not voices:
        return None, "No voice notes found in this channel."
    return random.choice(voices), None


# ====================== MAIN COMMAND ======================
@Altruix.register_on_cmd(
    "rvoice",
    cmd_help={
        "help": "Send a random voice note to a replied message from configured channels.",
        "usage": ".rvoice [caption]\n.rvoice <add/del/list/autodel/help>",
        "example": ".rvoice\n.rvoice mantap\n.rvoice add @,channel\n.rvoice del @,channel\n.rvoice autodel on\n.rvoice list\n.rvoice help",
        "user_args": {
            "add": "Add a new source channel.",
            "del": "Remove an existing source channel.",
            "list": "View configurations and sources.",
            "autodel": "Toggle auto-delete on reply (on/off).",
            "help": "Show detailed internal help."
        }
    },
)
async def rvoice_cmd(c: Client, m: Message):
    """Main handler for the .rvoice command family."""
    user_id = c.me.id if c.me else m.from_user.id
    user_input = getattr(m, "user_input", "") or ""
    args = user_input.strip().split(maxsplit=1)
    sub = args[0].lower() if args else ""

    # Known subcommands that should NOT be treated as captions
    SUBCOMMANDS = {"help", "add", "del", "delete", "remove", "rm", "list", "autodel"}

    # ── .rvoice help ──────────────────────────────────────────
    if sub == "help":
        await m.edit(RVOICE_HELP_TEXT, parse_mode=ParseMode.HTML)
        return

    # ── .rvoice add <channel> ──────────────────────────────────
    if sub == "add":
        if len(args) < 2:
            await m.edit(
                "⚠️ <b>Format salah!</b>\nGunakan: <code>.rvoice add @channel_username</code>",
                parse_mode=ParseMode.HTML,
            )
            return
        channel = args[1].strip()
        # Normalize channel ID
        if channel.startswith("https://t.me/"):
            channel = "@" + channel.split("https://t.me/")[-1].split("/")[0]
        # Validate channel is accessible
        try:
            chat = await c.get_chat(channel)
            channel_id_str = f"@{chat.username}" if chat.username else str(chat.id)
        except Exception as e:
            await m.edit(
                f"❌ <b>Channel tidak ditemukan atau tidak bisa diakses.</b>\n<code>{e}</code>",
                parse_mode=ParseMode.HTML,
            )
            return
            
        added = _add_channel(user_id, channel_id_str)
        if not added:
            await m.edit(
                f"ℹ️ Channel <code>{channel_id_str}</code> sudah ada di daftar sumber.",
                parse_mode=ParseMode.HTML,
            )
        else:
            await m.edit(
                f"✅ <b>Channel berhasil ditambahkan!</b>\n<code>{channel_id_str}</code> — {chat.title}",
                parse_mode=ParseMode.HTML,
            )
        return

    # ── .rvoice del <channel> ──────────────────────────────────
    if sub in ("del", "delete", "remove", "rm"):
        if len(args) < 2:
            await m.edit(
                "⚠️ <b>Format salah!</b>\nGunakan: <code>.rvoice del @channel_username</code>",
                parse_mode=ParseMode.HTML,
            )
            return
        channel = args[1].strip()
        if channel.startswith("https://t.me/"):
            channel = "@" + channel.split("https://t.me/")[-1].split("/")[0]
            
        # Try to normalize via chat lookup
        try:
            chat = await c.get_chat(channel)
            channel_id_str = f"@{chat.username}" if chat.username else str(chat.id)
        except Exception:
            channel_id_str = channel

        removed = _remove_channel(user_id, channel_id_str)
        if not removed:
            # Try removing raw input if normalized failed
            removed = _remove_channel(user_id, channel)
            channel_id_str = channel

        if not removed:
            await m.edit(
                f"❌ Channel <code>{channel_id_str}</code> tidak ditemukan di daftar sumber.",
                parse_mode=ParseMode.HTML,
            )
        else:
            await m.edit(
                f"🗑️ <b>Channel berhasil dihapus:</b> <code>{channel_id_str}</code>",
                parse_mode=ParseMode.HTML,
            )
        return

    # ── .rvoice autodel <on/off/status> ────────────────────────
    if sub == "autodel":
        status_arg = args[1].lower() if len(args) > 1 else "status"
        if status_arg in ("on", "enable", "true"):
            _set_autodel_status(user_id, True)
            await m.edit("✅ <b>Auto-Delete diaktifkan!</b>\nVoice note akan dihapus jika ada yang membalas.", parse_mode=ParseMode.HTML)
        elif status_arg in ("off", "disable", "false"):
            _set_autodel_status(user_id, False)
            await m.edit("❌ <b>Auto-Delete dimatikan!</b>", parse_mode=ParseMode.HTML)
        else:
            is_on = _get_autodel_status(user_id)
            stat_text = "✅ Aktif" if is_on else "❌ Mati"
            await m.edit(f"<b>Status Auto-Delete:</b> {stat_text}", parse_mode=ParseMode.HTML)
        return

    # ── .rvoice list ───────────────────────────────────────────
    if sub == "list":
        channels = _get_channels(user_id)
        is_on = _get_autodel_status(user_id)
        stat_text = "✅ Aktif" if is_on else "❌ Mati"
        
        if not channels or (len(channels) == 1 and channels[0] == DEFAULT_CHANNEL):
            await m.edit(
                f"📋 <b>Daftar sumber kosong.</b>\nMenggunakan default: <code>{DEFAULT_CHANNEL}</code>\n"
                f"<b>Status Auto-Delete:</b> {stat_text}\n\n"
                f"Tambahkan dengan: <code>.rvoice add @channel</code>",
                parse_mode=ParseMode.HTML,
            )
        else:
            lines = "\n".join(f"  {i+1}. <code>{ch}</code>" for i, ch in enumerate(channels))
            await m.edit(
                f"📋 <b>Konfigurasi Random Voice:</b>\n"
                f"• <b>Auto-Delete:</b> {stat_text}\n"
                f"• <b>Sumber ({len(channels)}):</b>\n{lines}",
                parse_mode=ParseMode.HTML
            )
        return

    # ── .rvoice [caption optional] (send random voice) ────────
    # If sub is not a known subcommand, treat the entire user_input as caption
    caption = user_input.strip() if sub not in SUBCOMMANDS else None
    reply = m.reply_to_message
    if not reply:
        await m.edit(
            "⚠️ <b>Reply ke pesan terlebih dahulu sebelum menggunakan .rvoice</b>\n\n"
            "Gunakan <code>.rvoice help</code> untuk panduan lengkap.",
            parse_mode=ParseMode.HTML,
        )
        return

    # Show loading indicator
    msg = await m.edit("<code>⏳ loading...</code>", parse_mode=ParseMode.HTML)
    
    channels = _get_channels(user_id)
    # Shuffle for extra randomness in channel selection
    random.shuffle(channels)
    
    voice_msg = None
    error_info = ""
    for channel in channels:
        voice_msg, err = await _fetch_random_voice(c, channel)
        if voice_msg: 
            break
        error_info = err or "unknown error"

    if not voice_msg:
        await msg.edit(
            f"😔 <b>Tidak ada voice note yang ditemukan.</b>\n"
            f"Pastikan channel sumber memiliki pesan voice note dan bot sudah join.\n"
            f"<code>{error_info}</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    # Download and re-send as voice (reply to the target message)
    tmp_file = None
    try:
        tmp_file = await voice_msg.download()
        sent = await reply.reply_voice(
            tmp_file, 
            caption=caption or None
        )
        
        # Tracking for auto-delete
        if _get_autodel_status(user_id):
            await rvoice_tracked_db.insert_one({
                "chat_id": m.chat.id,
                "msg_id": sent.id,
                "owner_id": user_id,
                "time": datetime.now()
            })
            
        # Delete the command message
        await msg.delete()
    except Exception as e:
        await msg.edit(
            f"❌ <b>Error Kirim voice note:</b>\n<code>{e}</code>",
            parse_mode=ParseMode.HTML,
        )
    finally:
        if tmp_file and os.path.exists(tmp_file): 
            os.remove(tmp_file)


# ====================== AUTO-DELETE LISTENER ======================
@Altruix.on_message(filters.group & filters.reply & ~filters.me, group=7)
async def rvoice_autodel_listener(c: Client, m: Message):
    """Listen for replies to tracked voice notes and delete them."""
    replied_msg = m.reply_to_message
    if not replied_msg: 
        return
    
    # Check if this message is tracked
    track = await rvoice_tracked_db.find_one({
        "chat_id": m.chat.id,
        "msg_id": replied_msg.id
    })
    
    if track:
        try:
            # Check if the owner of the session has autodel enabled
            if _get_autodel_status(track["owner_id"]):
                await replied_msg.delete()
                # Also delete record from DB
                await rvoice_tracked_db.delete_one({"_id": track["_id"]})
        except Exception:
            pass
