# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.

import re
import os
import asyncio
import random
import shlex
import ast
import time

from Main import Altruix
from pyrogram import Client, filters
from pyrogram.raw.functions import Ping
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram import errors
from pyrogram.errors import FloodWait, ChatWriteForbidden

from Main.core.types.message import Message
from Main.utils.essentials import Essentials
from Main.core.decorators import inline_check
from pyrogram.errors import RPCError
from Main.core.decorators import log_errors

# ─── LOGGER KHUSUS PLUGIN ───────────────────────────────────────────────
import logging 

plugin_name = f"plugins/userbot/{os.path.basename(__file__)}"
__plugin_name__ = plugin_name if plugin_name else "xspamxr"
PLUGIN_VERSION = "0.3.0.0:"

logger = logging.getLogger(f"{__plugin_name__}")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - [SET PLUGIN] - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


f"""
✘ Commands Available -

• `.relayspam <chat/destination> <start_delay> <stop_delay> <step> <count> <delete/purge> <emot_react/optional> ["msg_1", "msg_2", ...]` 
   Atau `[("msg_1", batch_count1), ("msg_2", batch_count2), ...]`
   Spam ke chat tujuan dengan delay acak berinterval dan pesan acak dari list.

• `.srelayspam <chat/destination>` - Stop task
• `.prelayspam <chat/destination>` - Pause task  
• `.rrelayspam <chat/destination>` - Resume task
• `.relayspamcek <chat/destination>` - Check status
• `.relayspamcekall` - Check all tasks

**CHANGELOG v{PLUGIN_VERSION}:**
- FIXED: Masalah recurring dan recurring all mengirim pesan dari bot bukan userbot
- ADDED: Tombol toggle untuk enable/disable reaction secara real-time
- ADDED: Opsi tombol untuk memilih emoji reaction default dari daftar emoji Telegram resmi
- ADDED: Fungsi cancel untuk edit last msg dan edit list msg
- ADDED: Tombol untuk menambah/mengurangi jumlah purge dengan kelipatan 5 (+5, +10, +15, +20, +25, -5, -10, -15, -20, -25)
- IMPROVED: Semua fungsi sekarang menggunakan client userbot untuk mengirim spam dan menghapus pesan
- IMPROVED: Sistem callback query yang lebih robust dengan sub-menu purge
"""

# Dictionary global untuk menyimpan status task relayspam per chat
TELAYSPAM_TASKS = {}

# Dictionary untuk konfigurasi task yang telah selesai (untuk recurring)
COMPLETED_TASKS = {}

# Dictionary untuk menyimpan status edit msg_list yang sedang menunggu input pengguna
EDIT_MSGLIST_WAITING = {}

# Dictionary untuk menyimpan status edit last msg yang sedang menunggu input pengguna
EDIT_LASTMSG_WAITING = {}

# Dictionary untuk menyimpan status pemilihan emoji
EMOJI_SELECTION_WAITING = {}

# Dictionary untuk menyimpan status pemilihan adjust purge
ADJUST_PURGE_WAITING = {}

# Daftar emoji reaction yang valid sesuai API Telegram
# Emoji yang umum digunakan dan didukung oleh Telegram
VALID_EMOJIS = [
    "👍", "👎", "❤️", "🔥", "🥰", "👏", "😁", "🤔", "🤯", "😱",
    "🤬", "😢", "🎉", "🤩", "🤮", "💩", "🙏", "👌", "🕊", "🤡",
    "🥱", "🥴", "😍", "🐳", "❤️‍🔥", "🌚", "🌭", "💯", "🤣", "⚡",
    "🍌", "🏆", "💔", "🤨", "😐", "🍓", "🍾", "💋", "🖕", "😈",
    "😴", "😭", "🤓", "👻", "👨‍💻", "👀", "🎃", "🙈", "😇", "😨",
    "🤝", "✍️", "🤗", "🫡", "🎅", "🎄", "☃️", "💅", "🤪", "🗿",
    "🆒", "💘", "🙉", "🦄", "😘", "💊", "🙊", "😎", "👾", "🤷‍♂️",
    "🤷", "🤷‍♀️", "😡"
]

# Referensi ke client utama Altruix
# PERBAIKAN: Pastikan selalu menggunakan userbot untuk mengirim spam dan menghapus pesan
try:
    USER_CLIENT = Altruix.userbot
    BOT_CLIENT = Altruix.bot if hasattr(Altruix, 'bot') else None
except AttributeError:
    USER_CLIENT = Altruix
    BOT_CLIENT = None

# ============= PERBAIKAN: Handler diambil dari config =============
try:
    HANDLER = Altruix.config.HANDLERS
    if isinstance(HANDLER, list):
        HANDLER = HANDLER[0]
except AttributeError:
    HANDLER = "."

# ============= PERBAIKAN: Mengambil LOG_CHAT_ID dengan benar =============
try:
    LOG_CHAT_ID = Altruix.config.LOG_CHAT_ID
except AttributeError:
    try:
        LOG_CHAT_ID = Altruix.config.OWNER_ID
    except AttributeError:
        LOG_CHAT_ID = None

if not LOG_CHAT_ID:
    LOG_CHAT_ID = "me"  # Kirim ke Saved Messages

# --- Fungsi untuk update tombol purge secara dinamis ---
async def update_purge_button(message: Message, chat_id: str, purge_value: int):
    """
    Update tombol purge di pesan notifikasi dengan nilai yang baru
    """
    try:
        purge_text = f"Purge: {purge_value}" if purge_value > 0 else "Purge: OFF"
        purge_data = f"toggle_purge_{chat_id}"

        keyboard = message.reply_markup.inline_keyboard if message.reply_markup else []
        new_keyboard = []
        
        for row in keyboard:
            new_row = []
            for btn in row:
                if btn.callback_data and "toggle_purge" in btn.callback_data:
                    new_row.append(InlineKeyboardButton(purge_text, callback_data=purge_data))
                else:
                    new_row.append(btn)
            new_keyboard.append(new_row)

        await message.edit_reply_markup(InlineKeyboardMarkup(new_keyboard))
    except Exception as e:
        Altruix.log(f"Gagal update tombol purge: {e}", level=40)

# --- Fungsi untuk update tombol reaction secara dinamis ---
async def update_reaction_button(message: Message, chat_id: str, reaction_enabled: bool, emoji: str = None):
    """
    Update tombol reaction di pesan notifikasi
    """
    try:
        react_text = f"React: {'ON' if reaction_enabled else 'OFF'}"
        if reaction_enabled and emoji:
            react_text = f"React: {emoji} ON"
        react_data = f"toggle_react_{chat_id}"

        keyboard = message.reply_markup.inline_keyboard if message.reply_markup else []
        new_keyboard = []
        
        for row in keyboard:
            new_row = []
            for btn in row:
                if btn.callback_data and "toggle_react" in btn.callback_data:
                    new_row.append(InlineKeyboardButton(react_text, callback_data=react_data))
                else:
                    new_row.append(btn)
            new_keyboard.append(new_row)

        await message.edit_reply_markup(InlineKeyboardMarkup(new_keyboard))
    except Exception as e:
        Altruix.log(f"Gagal update tombol reaction: {e}", level=40)

async def spam_loop(client: Client, target_chat, chat_id: str, msg_list, delays_possible, 
                    count: int, start_delay: float, stop_delay: float, step: float, 
                    x_msg: Message, emot_react: str, is_batch: bool, react_enabled: bool = True):
    """
    Loop utama untuk mengirim spam messages
    PERBAIKAN: Pastikan penghapusan pesan dilakukan oleh userbot
    """
    try:
        sent_count = 0
        total_del_suk = 0
        total_del_ggl = 0
        
        # PERBAIKAN: Pastikan selalu menggunakan client userbot untuk mengirim pesan
        spam_client = client
        
        if is_batch:
            for msg, b_count in msg_list:
                for _ in range(b_count):
                    if not TELAYSPAM_TASKS.get(chat_id, {}).get("running", False):
                        Altruix.log(f"Task dihentikan untuk chat {chat_id}", level=30)
                        if USER_CLIENT:
                            await USER_CLIENT.send_message(
                                LOG_CHAT_ID, 
                                f"__Task dihentikan untuk chat {chat_id}__"
                            )
                        break
                    await TELAYSPAM_TASKS[chat_id]["pause_event"].wait()

                    # Gunakan config real-time untuk old_purge
                    old_purge_val = TELAYSPAM_TASKS[chat_id]["config"]["old_purge"]
                    del_suk, del_ggl = 0, 0
                    
                    # PERBAIKAN: Pastikan hanya userbot yang menghapus pesan
                    if old_purge_val > 0:
                        try:
                            messages = []
                            # Gunakan spam_client (userbot) untuk mendapatkan history
                            async for message in spam_client.get_chat_history(target_chat.id, limit=old_purge_val * 2):
                                messages.append(message)
                            
                            if messages:
                                # Hanya hapus pesan yang dikirim oleh userbot ini
                                my_messages = [msg for msg in messages if msg.from_user and msg.from_user.id == spam_client.me.id][:old_purge_val]
                                message_ids = [msg.id for msg in my_messages]
                                
                                if message_ids:
                                    # PERBAIKAN: Gunakan spam_client (userbot) untuk menghapus pesan
                                    await spam_client.delete_messages(target_chat.id, message_ids)
                                    del_suk = len(message_ids)
                                    await asyncio.sleep(1)  # Tunggu sebentar untuk menghindari flood
                                else:
                                    del_suk = 0
                                    
                                del_ggl = old_purge_val - del_suk
                                total_del_suk += del_suk
                                total_del_ggl += del_ggl
                                
                                if USER_CLIENT and del_suk > 0:
                                    await USER_CLIENT.send_message(
                                        LOG_CHAT_ID,
                                        f"[HAPUS]: Berhasil hapus {del_suk} pesan lama, gagal {del_ggl} pesan di {target_chat.title}.",
                                        reply_to_message_id=x_msg.id if x_msg else None
                                    )
                        except Exception as del_err:
                            Altruix.log(f"Error saat menghapus pesan: {del_err}", level=40)
                            if USER_CLIENT:
                                await USER_CLIENT.send_message(
                                    LOG_CHAT_ID, 
                                    f"Error hapus pesan: {del_err}", 
                                    reply_to_message_id=x_msg.id if x_msg else None
                                )

                    random_delay = random.choice(delays_possible)

                    while True:
                        try:
                            # PERBAIKAN: Gunakan spam_client (userbot) untuk mengirim pesan
                            sent_msg = await spam_client.send_message(target_chat.id, msg)
                            sent_count += 1

                            react_status = "tidak ada"
                            # PERBAIKAN: Gunakan react_enabled dari config
                            current_react_enabled = TELAYSPAM_TASKS[chat_id]["config"].get("react_enabled", True)
                            current_emot_react = TELAYSPAM_TASKS[chat_id]["config"]["emot_react"]
                            
                            if current_react_enabled and current_emot_react and current_emot_react.lower() != "none":
                                try:
                                    await asyncio.sleep(2)
                                    # PERBAIKAN: Gunakan spam_client (userbot) untuk menambahkan reaction
                                    await spam_client.send_reaction(target_chat.id, sent_msg.id, current_emot_react)
                                    react_status = f"{current_emot_react} berhasil"
                                except Exception as react_err:
                                    Altruix.log(f"Error saat menambahkan reaksi: {react_err}", level=40)
                                    react_status = f"{current_emot_react} gagal"

                            remaining = count - sent_count
                            percentage = (sent_count / count) * 100 if count > 0 else 0
                            char_count = len(msg)
                            
                            if USER_CLIENT:
                                await USER_CLIENT.send_message(
                                    LOG_CHAT_ID,
                                    f"Pesan terkirim\n"
                                    f"Mode: {'Batch' if is_batch else 'Acak'}\n"
                                    f"Delay: {random_delay:.2f} detik\n"
                                    f"Sisa: {remaining} pesan\n"
                                    f"Progress: {percentage:.2f}%\n"
                                    f"Length: {char_count} karakter\n"
                                    f"React: {react_status}\n"
                                    f"Pesan: {msg[:50]}..." if len(msg) > 50 else f"Pesan: {msg}",
                                    reply_to_message_id=x_msg.id if x_msg else None
                                )

                            await asyncio.sleep(random_delay)
                            break

                        except errors.exceptions.flood_420.SlowmodeWait as swe:
                            Altruix.log(f"SlowModeWaitError: Waiting for {swe.value} seconds", level=30)
                            if USER_CLIENT:
                                await USER_CLIENT.send_message(
                                    LOG_CHAT_ID, 
                                    f"** [ #ERROR ]** __SlowModeWaitError: Waiting for {swe.value} seconds__", 
                                    reply_to_message_id=x_msg.id if x_msg else None
                                )
                            await asyncio.sleep(swe.value)

                        except FloodWait as fwe:
                            Altruix.log(f"FloodWaitError: Waiting for {fwe.value} seconds", level=30)
                            if USER_CLIENT:
                                await USER_CLIENT.send_message(
                                    LOG_CHAT_ID, 
                                    f"** [ #ERROR ]** __FloodWaitError: Waiting for {fwe.value} seconds__", 
                                    reply_to_message_id=x_msg.id if x_msg else None
                                )
                            await asyncio.sleep(fwe.value)

                        except ChatWriteForbidden as cwe:
                            Altruix.log(f"UserBot muted in chat {chat_id}: Pausing task automatically.", level=30)
                            if USER_CLIENT:
                                await USER_CLIENT.send_message(
                                    LOG_CHAT_ID, 
                                    f"** [ #ERROR ]** __UserBot muted in chat {target_chat.title}: Task paused automatically.__", 
                                    reply_to_message_id=x_msg.id if x_msg else None
                                )
                            TELAYSPAM_TASKS[chat_id]["pause_event"].clear()
                            break

                        except Exception as send_err:
                            Altruix.log(f"Error saat mengirim pesan: {send_err}", level=40)
                            if USER_CLIENT:
                                await USER_CLIENT.send_message(
                                    LOG_CHAT_ID, 
                                    f"** [ #ERROR ]** __Error saat mengirim pesan: {send_err}__", 
                                    reply_to_message_id=x_msg.id if x_msg else None
                                )
                            await asyncio.sleep(5)

        else:  # Mode acak
            for _ in range(count):
                if not TELAYSPAM_TASKS.get(chat_id, {}).get("running", False):
                    Altruix.log(f"Task dihentikan untuk chat {chat_id}", level=30)
                    if USER_CLIENT:
                        await USER_CLIENT.send_message(
                            LOG_CHAT_ID, 
                            f"__Task dihentikan untuk chat {chat_id}__"
                        )
                    break
                await TELAYSPAM_TASKS[chat_id]["pause_event"].wait()

                # Gunakan config real-time untuk old_purge
                old_purge_val = TELAYSPAM_TASKS[chat_id]["config"]["old_purge"]
                del_suk, del_ggl = 0, 0
                
                # PERBAIKAN: Pastikan hanya userbot yang menghapus pesan
                if old_purge_val > 0:
                    try:
                        messages = []
                        # Gunakan spam_client (userbot) untuk mendapatkan history
                        async for message in spam_client.get_chat_history(target_chat.id, limit=old_purge_val * 2):
                            messages.append(message)
                        
                        if messages:
                            # Hanya hapus pesan yang dikirim oleh userbot ini
                            my_messages = [msg for msg in messages if msg.from_user and msg.from_user.id == spam_client.me.id][:old_purge_val]
                            message_ids = [msg.id for msg in my_messages]
                            
                            if message_ids:
                                # PERBAIKAN: Gunakan spam_client (userbot) untuk menghapus pesan
                                await spam_client.delete_messages(target_chat.id, message_ids)
                                del_suk = len(message_ids)
                                await asyncio.sleep(1)  # Tunggu sebentar untuk menghindari flood
                            else:
                                del_suk = 0
                                
                            del_ggl = old_purge_val - del_suk
                            total_del_suk += del_suk
                            total_del_ggl += del_ggl
                            
                            if USER_CLIENT and del_suk > 0:
                                await USER_CLIENT.send_message(
                                    LOG_CHAT_ID,
                                    f"[HAPUS]: Berhasil hapus {del_suk} pesan lama, gagal {del_ggl} pesan di {target_chat.title}.",
                                    reply_to_message_id=x_msg.id if x_msg else None
                                )
                    except Exception as del_err:
                        Altruix.log(f"Error saat menghapus pesan: {del_err}", level=40)
                        if USER_CLIENT:
                            await USER_CLIENT.send_message(
                                LOG_CHAT_ID, 
                                f"Error hapus pesan: {del_err}", 
                                reply_to_message_id=x_msg.id if x_msg else None
                            )

                msg = random.choice(msg_list)
                random_delay = random.choice(delays_possible)

                while True:
                    try:
                        # PERBAIKAN: Gunakan spam_client (userbot) untuk mengirim pesan
                        sent_msg = await spam_client.send_message(target_chat.id, msg)
                        sent_count += 1

                        react_status = "tidak ada"
                        # PERBAIKAN: Gunakan react_enabled dari config
                        current_react_enabled = TELAYSPAM_TASKS[chat_id]["config"].get("react_enabled", True)
                        current_emot_react = TELAYSPAM_TASKS[chat_id]["config"]["emot_react"]
                        
                        if current_react_enabled and current_emot_react and current_emot_react.lower() != "none":
                            try:
                                await asyncio.sleep(2)
                                # PERBAIKAN: Gunakan spam_client (userbot) untuk menambahkan reaction
                                await spam_client.send_reaction(target_chat.id, sent_msg.id, current_emot_react)
                                react_status = f"{current_emot_react} berhasil"
                            except Exception as react_err:
                                Altruix.log(f"Error saat menambahkan reaksi: {react_err}", level=40)
                                react_status = f"{current_emot_react} gagal"

                        remaining = count - sent_count
                        percentage = (sent_count / count) * 100 if count > 0 else 0
                        char_count = len(msg)
                        
                        if USER_CLIENT:
                            await USER_CLIENT.send_message(
                                LOG_CHAT_ID,
                                f"Pesan terkirim\n"
                                f"Mode: {'Batch' if is_batch else 'Acak'}\n"
                                f"Delay: {random_delay:.2f} detik\n"
                                f"Sisa: {remaining} pesan\n"
                                f"Progress: {percentage:.2f}%\n"
                                f"Length: {char_count} karakter\n"
                                f"React: {react_status}\n"
                                f"Pesan: {msg[:50]}..." if len(msg) > 50 else f"Pesan: {msg}",
                                reply_to_message_id=x_msg.id if x_msg else None
                            )

                        await asyncio.sleep(random_delay)
                        break

                    except errors.exceptions.flood_420.SlowmodeWait as swe:
                        Altruix.log(f"SlowModeWaitError: Waiting for {swe.value} seconds", level=30)
                        if USER_CLIENT:
                            await USER_CLIENT.send_message(
                                LOG_CHAT_ID, 
                                f"** [ #ERROR ]** __SlowModeWaitError: Waiting for {swe.value} seconds__", 
                                reply_to_message_id=x_msg.id if x_msg else None
                            )
                        await asyncio.sleep(swe.value)

                    except FloodWait as fwe:
                        Altruix.log(f"FloodWaitError: Waiting for {fwe.value} seconds", level=30)
                        if USER_CLIENT:
                            await USER_CLIENT.send_message(
                                LOG_CHAT_ID, 
                                f"** [ #ERROR ]** __FloodWaitError: Waiting for {fwe.value} seconds__", 
                                reply_to_message_id=x_msg.id if x_msg else None
                            )
                        await asyncio.sleep(fwe.value)

                    except ChatWriteForbidden as cwe:
                        Altruix.log(f"UserBot muted in chat {chat_id}: Pausing task automatically.", level=30)
                        if USER_CLIENT:
                            await USER_CLIENT.send_message(
                                LOG_CHAT_ID, 
                                f"** [ #ERROR ]** __UserBot muted in chat {target_chat.title}: Task paused automatically.__", 
                                reply_to_message_id=x_msg.id if x_msg else None
                            )
                        TELAYSPAM_TASKS[chat_id]["pause_event"].clear()
                        break

                    except Exception as send_err:
                        Altruix.log(f"Error saat mengirim pesan: {send_err}", level=40)
                        if USER_CLIENT:
                            await USER_CLIENT.send_message(
                                LOG_CHAT_ID, 
                                f"** [ #ERROR ]** __Error saat mengirim pesan: {send_err}__", 
                                reply_to_message_id=x_msg.id if x_msg else None
                            )
                        await asyncio.sleep(5)

        if TELAYSPAM_TASKS.get(chat_id, {}).get("running", False) and USER_CLIENT:
            await USER_CLIENT.send_message(
                LOG_CHAT_ID,
                f"[SELESAI]: \n"
                f"Spam di {target_chat.title} telah selesai!\n"
                f"Terkirim {sent_count} pesan ({'batch' if is_batch else 'acak'}), delay acak [{start_delay}-{stop_delay}] dengan interval {step} detik,\n"
                f"Total sukses hapus {total_del_suk} pesan, total gagal hapus {total_del_ggl} pesan.",
                reply_to_message_id=x_msg.id if x_msg else None
            )

    except Exception as u:
        Altruix.log(f"Error in spam_loop: {u}", level=40)
        if USER_CLIENT:
            await USER_CLIENT.send_message(LOG_CHAT_ID, f"__Error in spam_loop: {u}__")
    finally:
        if chat_id in TELAYSPAM_TASKS:
            config = TELAYSPAM_TASKS[chat_id].pop('config', None)
            if config:
                COMPLETED_TASKS[chat_id] = config
        TELAYSPAM_TASKS.pop(chat_id, None)

async def start_relayspam(client: Client, destination: str, start_delay: float, stop_delay: float, 
                          step: float, count: int, old_purge: int, emot_react: str, 
                          msg_list: list, is_batch: bool, react_enabled: bool = True) -> bool:
    """
    Memulai task relayspam
    """
    try:
        # Resolusi chat/entity
        if destination.isdigit() and len(destination) >= 10:
            destination = "-100" + destination
        
        target_chat = await client.get_chat(int(destination) if destination.replace("-", "").isdigit() else destination)
        chat_id = str(target_chat.id)

        if chat_id in TELAYSPAM_TASKS:
            if USER_CLIENT:
                await USER_CLIENT.send_message(
                    LOG_CHAT_ID, 
                    f"**Error:** Task relayspam sudah berjalan di {target_chat.title}."
                )
            return False

        # PERBAIKAN: Simpan client yang digunakan untuk task ini
        TELAYSPAM_TASKS[chat_id] = {
            "running": True,
            "pause_event": asyncio.Event(),
            "client": client,  # Simpan client userbot untuk digunakan nanti
            "config": {
                "destination": destination,
                "start_delay": start_delay,
                "stop_delay": stop_delay,
                "step": step,
                "count": count,
                "old_purge": old_purge,
                "emot_react": emot_react,
                "msg_list": msg_list[:] if isinstance(msg_list, list) else msg_list,
                "is_batch": is_batch,
                "react_enabled": react_enabled  # Tambah status reaction
            }
        }
        TELAYSPAM_TASKS[chat_id]["pause_event"].set()

        clean_id = str(target_chat.id).replace("-100", "")

        notif_msg = (
            f"Notifikasi Task\n\n"
            f"Tugas spam akan segera dimulai.\n\n"
            f"✦ · · ──────✪────── · · ✦\n"
            f"Tujuan     : {target_chat.title}\n"
            f"Chat_ID    : -100{clean_id}\n"
            f"Perintah   : {HANDLER}relayspam\n"
            f"Mode       : {'Batch' if is_batch else 'Acak'}\n"
            f"Delay      : {start_delay} - {stop_delay}/step {step} detik\n"
            f"Jumlah     : {count} pesan\n"
            f"Hapus      : {old_purge} pesan {'(Aktif)' if old_purge > 0 else '(Nonaktif)'}\n"
            f"React      : {'Aktif (' + emot_react + ')' if react_enabled and emot_react else 'Tidak aktif'}\n"
            f"Pesan      : {len(msg_list)} item\n"
        )

        # Tombol inline untuk kontrol task
        # PERBAIKAN: Tambah tombol untuk reaction dan adjust purge
        tombol_baris = [
            [InlineKeyboardButton(f"-100{clean_id}", url=f"https://t.me/c/{clean_id}/99999")],
            [InlineKeyboardButton("Stop", callback_data=f"stop_{chat_id}"), 
             InlineKeyboardButton("Pause", callback_data=f"pause_{chat_id}"), 
             InlineKeyboardButton("Resume", callback_data=f"resume_{chat_id}")],
            [InlineKeyboardButton("Check Status", callback_data=f"cek_{chat_id}"), 
             InlineKeyboardButton("Recurring", callback_data=f"recurring_{chat_id}")],
            [InlineKeyboardButton("Stop All", callback_data="stopall"), 
             InlineKeyboardButton("Pause All", callback_data="pauseall"), 
             InlineKeyboardButton("Resume All", callback_data="resumeall")],
            [InlineKeyboardButton("Check All", callback_data="cekall"), 
             InlineKeyboardButton("Recur All", callback_data="recurringall")],
            [InlineKeyboardButton("Del Last 30", callback_data=f"delete_latest_{chat_id}"), 
             InlineKeyboardButton("Del Old 30", callback_data=f"delete_oldest_{chat_id}")],
            [InlineKeyboardButton("Edit Last Msg", callback_data=f"edit_last_{chat_id}"), 
             InlineKeyboardButton("Edit Msg List", callback_data=f"edit_msglist_{chat_id}")],
            [InlineKeyboardButton(f"{'Purge: ' + str(old_purge) if old_purge > 0 else 'Purge: OFF'}", callback_data=f"toggle_purge_{chat_id}"),
             InlineKeyboardButton("Adjust Purge", callback_data=f"adjust_purge_{chat_id}")],
            [InlineKeyboardButton(f"{'React: ON' if react_enabled else 'React: OFF'}", callback_data=f"toggle_react_{chat_id}"),
             InlineKeyboardButton("Pilih Emoji", callback_data=f"select_emoji_{chat_id}")]
        ]

        # PERBAIKAN: Gunakan USER_CLIENT untuk mengirim notifikasi
        if USER_CLIENT:
            x_msg = await USER_CLIENT.send_message(
                LOG_CHAT_ID,
                f"{notif_msg}",
                reply_markup=InlineKeyboardMarkup(tombol_baris)
            )

            # Simpan notif message untuk update tombol
            TELAYSPAM_TASKS[chat_id]["notif_msg"] = x_msg

            try:
                await x_msg.pin()
            except Exception as erpin:
                Altruix.log(f"#ERROR_PIN : {erpin}", level=30)
        else:
            x_msg = None

        delays_possible = []
        current = start_delay
        while current <= stop_delay:
            delays_possible.append(current)
            current += step

        if not delays_possible:
            raise ValueError("Tidak ada nilai delay yang mungkin dalam rentang yang diberikan.")

        # PERBAIKAN: Gunakan client yang disimpan (userbot) untuk spam_loop
        task = asyncio.create_task(spam_loop(client, target_chat, chat_id, msg_list, delays_possible, 
                                            count, start_delay, stop_delay, step, x_msg, emot_react, is_batch, react_enabled))
        TELAYSPAM_TASKS[chat_id]["task"] = task

        return True

    except Exception as u:
        Altruix.log(f"Error in start_relayspam: {u}", level=40)
        if USER_CLIENT:
            await USER_CLIENT.send_message(LOG_CHAT_ID, f"__Error in start_relayspam: {u}__")
        TELAYSPAM_TASKS.pop(chat_id, None)
        return False

# ==================== COMMAND HANDLERS ====================

@Altruix.register_on_cmd(
    ["relayspam"],
    cmd_help={
        "help": "Memulai spam relay dengan delay acak",
        "example": "relayspam -1001234567890 1.0 5.0 0.5 10 2 👍 [\"Pesan 1\", \"Pesan 2\"]",
        "user_args": [],
    },
)
@log_errors
async def telayspammer_cmd(c: Client, m: Message):
    """
    Handler command: relayspam
    """
    try:
        # PERBAIKAN UTAMA: Menggunakan m.user_input alih-alih Altruix.handler
        text = m.text.strip()
        
        # Menghapus prefix dan command untuk mendapatkan argumen
        cmd_pattern = re.escape(HANDLER) + r'relayspam\s+'
        args_str = re.sub(cmd_pattern, '', text, count=1)
        
        if not args_str:
            await m.handle_message(
                "INVALID_ARG_COUNT"
            )
            return
        
        # Cari list di akhir string
        msg_list_match = re.search(r'\[.*\]$', args_str, re.DOTALL)
        if not msg_list_match:
            await m.handle_message("INVALID_MSG_LIST_FORMAT")
            return

        msg_list_str = msg_list_match.group(0)
        args_str_without_msg = args_str[:msg_list_match.start()].strip()
        
        # Parsing argumen dengan shlex untuk handle quotes
        try:
            args = shlex.split(args_str_without_msg)
        except Exception:
            # Fallback ke split biasa jika shlex gagal
            args = args_str_without_msg.split()
        
        # PERBAIKAN: Sesuaikan jumlah argumen untuk perintah spesifik
        if len(args) not in [6, 7]:
            await m.handle_message(
                "INVALID_ARG_COUNT"
            )
            return

        destination = args[0]
        start_delay = float(args[1])
        stop_delay = float(args[2])
        step = float(args[3])
        count = int(args[4])
        old_purge = int(args[5])
        emot_react = args[6] if len(args) == 7 and args[6].lower() != "none" else None

        # Parse msg_list dengan aman
        try:
            msg_list = ast.literal_eval(msg_list_str)
        except (ValueError, SyntaxError) as e:
            Altruix.log(f"Error parsing msg_list: {e}", level=40)
            await m.handle_message("INVALID_MSG_LIST")
            return
            
        if not isinstance(msg_list, list) or not msg_list:
            await m.handle_message("INVALID_MSG_LIST")
            return

        # Cek apakah format batch (list of tuples) atau acak (list of strings)
        is_batch = all(isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str) and isinstance(item[1], int) for item in msg_list)
        if is_batch:
            total_batch_count = sum(b_count for _, b_count in msg_list)
            if total_batch_count != count:
                await m.handle_message("BATCH_COUNT_MISMATCH")
                return

        # Validasi nilai delay
        if start_delay <= 0 or stop_delay <= 0 or step <= 0:
            await m.handle_message("INVALID_DELAY_VALUES")
            return
        if start_delay > stop_delay:
            await m.handle_message("START_DELAY_GREATER")
            return

    except (ValueError, IndexError, SyntaxError) as err:
        Altruix.log(f"Error parsing command: {err}", level=40)
        await m.handle_message("PARSING_ERROR")
        return
    except Exception as e:
        Altruix.log(f"Error parsing command: {e}", level=40)
        await m.handle_message("ERROR_OCCURRED")
        return

    await m.handle_message("PROCESSING_TASK")
    await asyncio.sleep(2)

    # PERBAIKAN: Default react_enabled = True jika emot_react ada
    react_enabled = emot_react is not None and emot_react.lower() != "none"
    success = await start_relayspam(c, destination, start_delay, stop_delay, step, count, old_purge, emot_react, msg_list, is_batch, react_enabled)
    if success:
        await m.handle_message("TASK_STARTED_SUCCESS")
    else:
        await m.handle_message("TASK_START_FAILED")

@Altruix.register_on_cmd(
    ["srelayspam"],
    cmd_help={
        "help": "Menghentikan task relayspam",
        "example": "srelayspam -1001234567890",
        "user_args": [],
    },
)
@log_errors
async def stop_telayspam_cmd(c: Client, m: Message):
    """Stop task relayspam"""
    try:
        args = m.text.split(" ", 1)
        if len(args) < 2:
            await m.handle_message("MISSING_DESTINATION_ARG")
            return
            
        destination = args[1]
        if destination.isdigit() and len(destination) >= 10:
            destination = "-100" + destination
        target_chat = await c.get_chat(int(destination) if destination.replace("-", "").isdigit() else destination)
        chat_id = str(target_chat.id)
        if chat_id not in TELAYSPAM_TASKS:
            await m.handle_message("NO_TASK_RUNNING")
            return
        TELAYSPAM_TASKS[chat_id]["running"] = False
        TELAYSPAM_TASKS[chat_id]["pause_event"].set()
        if "task" in TELAYSPAM_TASKS[chat_id]:
            TELAYSPAM_TASKS[chat_id]["task"].cancel()
        await m.handle_message("TASK_STOPPED")
    except Exception as err:
        Altruix.log(f"Error stopping task: {err}", level=40)
        await m.handle_message("STOP_TASK_ERROR")

@Altruix.register_on_cmd(
    ["prelayspam"],
    cmd_help={
        "help": "Mempause task relayspam",
        "example": "prelayspam -1001234567890",
        "user_args": [],
    },
)
@log_errors
async def pause_telayspam_cmd(c: Client, m: Message):
    """Pause task relayspam"""
    try:
        args = m.text.split(" ", 1)
        if len(args) < 2:
            await m.handle_message("MISSING_DESTINATION_ARG")
            return
            
        destination = args[1]
        if destination.isdigit() and len(destination) >= 10:
            destination = "-100" + destination
        target_chat = await c.get_chat(int(destination) if destination.replace("-", "").isdigit() else destination)
        chat_id = str(target_chat.id)
        if chat_id not in TELAYSPAM_TASKS:
            await m.handle_message("NO_TASK_RUNNING")
            return
        TELAYSPAM_TASKS[chat_id]["pause_event"].clear()
        await m.handle_message("TASK_PAUSED")
    except Exception as err:
        Altruix.log(f"Error pausing task: {err}", level=40)
        await m.handle_message("PAUSE_TASK_ERROR")

@Altruix.register_on_cmd(
    ["rrelayspam"],
    cmd_help={
        "help": "Melanjutkan task relayspam yang dipause",
        "example": "rrelayspam -1001234567890",
        "user_args": [],
    },
)
@log_errors
async def resume_telayspam_cmd(c: Client, m: Message):
    """Resume task relayspam"""
    try:
        args = m.text.split(" ", 1)
        if len(args) < 2:
            await m.handle_message("MISSING_DESTINATION_ARG")
            return
            
        destination = args[1]
        if destination.isdigit() and len(destination) >= 10:
            destination = "-100" + destination
        target_chat = await c.get_chat(int(destination) if destination.replace("-", "").isdigit() else destination)
        chat_id = str(target_chat.id)
        if chat_id not in TELAYSPAM_TASKS:
            await m.handle_message("NO_TASK_RUNNING")
            return
        TELAYSPAM_TASKS[chat_id]["pause_event"].set()
        await m.handle_message("TASK_RESUMED")
    except Exception as err:
        Altruix.log(f"Error resuming task: {err}", level=40)
        await m.handle_message("RESUME_TASK_ERROR")

@Altruix.register_on_cmd(
    ["relayspamcek"],
    cmd_help={
        "help": "Memeriksa status task relayspam",
        "example": "relayspamcek -1001234567890",
        "user_args": [],
    },
)
@log_errors
async def check_relayspam_cmd(c: Client, m: Message):
    """Check status task relayspam"""
    try:
        args = m.text.split(" ", 1)
        if len(args) > 1:
            destination = args[1]
            if destination.isdigit() and len(destination) >= 10:
                destination = "-100" + destination
            target_chat = await c.get_chat(int(destination) if destination.replace("-", "").isdigit() else destination)
            chat_id = str(target_chat.id)
            if chat_id in TELAYSPAM_TASKS:
                status = TELAYSPAM_TASKS[chat_id]
                if status["running"]:
                    if status["pause_event"].is_set():
                        await m.handle_message("TASK_STATUS_RUNNING")
                    else:
                        await m.handle_message("TASK_STATUS_PAUSED")
                else:
                    await m.handle_message("TASK_STATUS_STOPPED")
            else:
                await m.handle_message("NO_TASK_FOR_CHAT")
        else:
            await m.handle_message("MISSING_DESTINATION_ARG")
            return
    except Exception as err:
        Altruix.log(f"Error checking status: {err}", level=40)
        await m.handle_message("CHAT_RESOLUTION_ERROR")

@Altruix.register_on_cmd(
    ["relayspamcekall"],
    cmd_help={
        "help": "Memeriksa status semua task relayspam",
        "example": "relayspamcekall",
        "user_args": [],
    },
)
@log_errors
async def check_all_relayspam_cmd(c: Client, m: Message):
    """Check semua task relayspam"""
    if not TELAYSPAM_TASKS:
        await m.handle_message("NO_ACTIVE_TASKS")
        return

    status_list = []
    for chat_id, status in TELAYSPAM_TASKS.items():
        try:
            target_chat = await c.get_chat(int(chat_id))
            chat_title = target_chat.title if hasattr(target_chat, 'title') else (target_chat.first_name or target_chat.username)
            if status["running"]:
                if status["pause_event"].is_set():
                    status_text = f"🔵 running di {chat_title} (ID: {chat_id})"
                else:
                    status_text = f"🟡 paused di {chat_title} (ID: {chat_id})"
            else:
                status_text = f"🔴 stopped di {chat_title} (ID: {chat_id})"
            status_list.append(status_text)
        except Exception as err:
            Altruix.log(f"Error resolusi chat {chat_id}: {err}", level=40)
            status_list.append(f"❓ Unknown chat (ID: {chat_id}) - Status tidak dapat diresolusi.")

    output = "Status Semua Task Relayspam:\n\n" + "\n".join(status_list)
    await m.edit(output)

# ==================== CALLBACK QUERY HANDLERS ====================

@Altruix.on_callback_query(filters.regex(r"toggle_purge_(-?\d+)"))
@log_errors
async def toggle_purge_handler(c: Client, cb):
    """Handler untuk toggle purge old messages"""
    data = cb.data
    chat_id = data.split("_")[-1]

    if chat_id not in TELAYSPAM_TASKS:
        await cb.answer("Task tidak aktif.", show_alert=True)
        return

    config = TELAYSPAM_TASKS[chat_id]["config"]
    current_purge = config["old_purge"]
    
    # Toggle: jika saat ini > 0, matikan. Jika 0, aktifkan dengan nilai default 5
    if current_purge > 0:
        new_purge = 0
        status = "NONAKTIF"
    else:
        new_purge = 5  # Default ke 5 saat di-ON
        status = "AKTIF"
    
    config["old_purge"] = new_purge

    await cb.answer(f"Purge old message: {status}", show_alert=True)
    
    if USER_CLIENT:
        await USER_CLIENT.send_message(
            LOG_CHAT_ID,
            f"PURGE TOGGLED\n"
            f"Chat: {config['destination']}\n"
            f"Status: {status}\n"
            f"Jumlah hapus: {new_purge} pesan lama"
        )

    # Update tombol di notif utama
    try:
        notif_msg = TELAYSPAM_TASKS[chat_id].get("notif_msg")
        if notif_msg:
            await update_purge_button(notif_msg, chat_id, new_purge)
    except Exception as e:
        Altruix.log(f"Gagal update tombol purge: {e}", level=40)

@Altruix.on_callback_query(filters.regex(r"adjust_purge_(-?\d+)"))
@log_errors
async def adjust_purge_handler(c: Client, cb):
    """Handler untuk menampilkan menu adjust purge"""
    data = cb.data
    chat_id = data.split("_")[-1]

    if chat_id not in TELAYSPAM_TASKS:
        await cb.answer("Task tidak aktif.", show_alert=True)
        return

    # Simpan status bahwa user sedang mengatur purge
    ADJUST_PURGE_WAITING[chat_id] = True
    
    # Buat keyboard dengan tombol +5, +10, +15, +20, +25 dan -5, -10, -15, -20, -25
    keyboard = [
        [
            InlineKeyboardButton("+5", callback_data=f"inc_purge_{chat_id}_5"),
            InlineKeyboardButton("+10", callback_data=f"inc_purge_{chat_id}_10"),
            InlineKeyboardButton("+15", callback_data=f"inc_purge_{chat_id}_15"),
            InlineKeyboardButton("+20", callback_data=f"inc_purge_{chat_id}_20"),
            InlineKeyboardButton("+25", callback_data=f"inc_purge_{chat_id}_25")
        ],
        [
            InlineKeyboardButton("-5", callback_data=f"dec_purge_{chat_id}_5"),
            InlineKeyboardButton("-10", callback_data=f"dec_purge_{chat_id}_10"),
            InlineKeyboardButton("-15", callback_data=f"dec_purge_{chat_id}_15"),
            InlineKeyboardButton("-20", callback_data=f"dec_purge_{chat_id}_20"),
            InlineKeyboardButton("-25", callback_data=f"dec_purge_{chat_id}_25")
        ],
        [
            InlineKeyboardButton("⏪ Kembali", callback_data=f"back_purge_{chat_id}"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_adjust_purge_{chat_id}")
        ]
    ]
    
    config = TELAYSPAM_TASKS[chat_id]["config"]
    current_purge = config["old_purge"]
    
    if USER_CLIENT:
        adjust_msg = await USER_CLIENT.send_message(
            LOG_CHAT_ID,
            f"📊 **Adjust Purge Settings**\n\n"
            f"**Chat:** {config['destination']}\n"
            f"**Purge saat ini:** {current_purge} pesan\n\n"
            f"Pilih tombol di bawah untuk menambah/mengurangi jumlah purge:\n"
            f"• Klik tombol + untuk menambah\n"
            f"• Klik tombol - untuk mengurangi\n"
            f"• Nilai tidak bisa kurang dari 0",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        # Simpan message adjust untuk dihapus nanti
        ADJUST_PURGE_WAITING[chat_id] = adjust_msg.id
    
    await cb.answer("Menu adjust purge ditampilkan", show_alert=False)

@Altruix.on_callback_query(filters.regex(r"inc_purge_(-?\d+)_(\d+)"))
@log_errors
async def increase_purge_handler(c: Client, cb):
    """Handler untuk menambah jumlah purge"""
    data = cb.data
    parts = data.split("_")
    chat_id = parts[2]
    inc_value = int(parts[3])

    if chat_id not in TELAYSPAM_TASKS:
        await cb.answer("Task tidak aktif.", show_alert=True)
        return

    config = TELAYSPAM_TASKS[chat_id]["config"]
    current_purge = config["old_purge"]
    new_purge = current_purge + inc_value
    
    # Pastikan nilai tidak negatif
    if new_purge < 0:
        new_purge = 0
    
    config["old_purge"] = new_purge
    
    await cb.answer(f"Purge ditambah {inc_value}. Total: {new_purge}", show_alert=True)
    
    if USER_CLIENT:
        await USER_CLIENT.send_message(
            LOG_CHAT_ID,
            f"PURGE INCREASED\n"
            f"Chat: {config['destination']}\n"
            f"Sebelum: {current_purge} pesan\n"
            f"Ditambah: +{inc_value} pesan\n"
            f"Sesudah: {new_purge} pesan"
        )

    # Update tombol di notif utama
    try:
        notif_msg = TELAYSPAM_TASKS[chat_id].get("notif_msg")
        if notif_msg:
            await update_purge_button(notif_msg, chat_id, new_purge)
    except Exception as e:
        Altruix.log(f"Gagal update tombol purge: {e}", level=40)
    
    # Hapus pesan adjust
    try:
        adjust_msg_id = ADJUST_PURGE_WAITING.get(chat_id)
        if adjust_msg_id and isinstance(adjust_msg_id, int):
            await USER_CLIENT.delete_messages(LOG_CHAT_ID, adjust_msg_id)
    except:
        pass
    
    # Hapus status waiting
    ADJUST_PURGE_WAITING.pop(chat_id, None)

@Altruix.on_callback_query(filters.regex(r"dec_purge_(-?\d+)_(\d+)"))
@log_errors
async def decrease_purge_handler(c: Client, cb):
    """Handler untuk mengurangi jumlah purge"""
    data = cb.data
    parts = data.split("_")
    chat_id = parts[2]
    dec_value = int(parts[3])

    if chat_id not in TELAYSPAM_TASKS:
        await cb.answer("Task tidak aktif.", show_alert=True)
        return

    config = TELAYSPAM_TASKS[chat_id]["config"]
    current_purge = config["old_purge"]
    new_purge = current_purge - dec_value
    
    # Pastikan nilai tidak negatif
    if new_purge < 0:
        new_purge = 0
    
    config["old_purge"] = new_purge
    
    status = "NONAKTIF" if new_purge == 0 else f"{new_purge} pesan"
    await cb.answer(f"Purge dikurangi {dec_value}. Total: {status}", show_alert=True)
    
    if USER_CLIENT:
        await USER_CLIENT.send_message(
            LOG_CHAT_ID,
            f"PURGE DECREASED\n"
            f"Chat: {config['destination']}\n"
            f"Sebelum: {current_purge} pesan\n"
            f"Dikurangi: -{dec_value} pesan\n"
            f"Sesudah: {new_purge} pesan {'(Nonaktif)' if new_purge == 0 else ''}"
        )

    # Update tombol di notif utama
    try:
        notif_msg = TELAYSPAM_TASKS[chat_id].get("notif_msg")
        if notif_msg:
            await update_purge_button(notif_msg, chat_id, new_purge)
    except Exception as e:
        Altruix.log(f"Gagal update tombol purge: {e}", level=40)
    
    # Hapus pesan adjust
    try:
        adjust_msg_id = ADJUST_PURGE_WAITING.get(chat_id)
        if adjust_msg_id and isinstance(adjust_msg_id, int):
            await USER_CLIENT.delete_messages(LOG_CHAT_ID, adjust_msg_id)
    except:
        pass
    
    # Hapus status waiting
    ADJUST_PURGE_WAITING.pop(chat_id, None)

@Altruix.on_callback_query(filters.regex(r"back_purge_(-?\d+)"))
@log_errors
async def back_purge_handler(c: Client, cb):
    """Handler untuk kembali dari menu adjust purge"""
    data = cb.data
    chat_id = data.split("_")[-1]
    
    # Hapus pesan adjust
    try:
        adjust_msg_id = ADJUST_PURGE_WAITING.get(chat_id)
        if adjust_msg_id and isinstance(adjust_msg_id, int):
            await USER_CLIENT.delete_messages(LOG_CHAT_ID, adjust_msg_id)
    except:
        pass
    
    # Hapus status waiting
    ADJUST_PURGE_WAITING.pop(chat_id, None)
    
    await cb.answer("Kembali ke menu utama", show_alert=False)

@Altruix.on_callback_query(filters.regex(r"cancel_adjust_purge_(-?\d+)"))
@log_errors
async def cancel_adjust_purge_handler(c: Client, cb):
    """Handler untuk cancel adjust purge"""
    data = cb.data
    chat_id = data.split("_")[-1]
    
    # Hapus pesan adjust
    try:
        adjust_msg_id = ADJUST_PURGE_WAITING.get(chat_id)
        if adjust_msg_id and isinstance(adjust_msg_id, int):
            await USER_CLIENT.delete_messages(LOG_CHAT_ID, adjust_msg_id)
    except:
        pass
    
    # Hapus status waiting
    ADJUST_PURGE_WAITING.pop(chat_id, None)
    
    await cb.answer("Adjust purge dibatalkan", show_alert=True)

@Altruix.on_callback_query(filters.regex(r"toggle_react_(-?\d+)"))
@log_errors
async def toggle_reaction_handler(c: Client, cb):
    """Handler untuk toggle reaction"""
    data = cb.data
    chat_id = data.split("_")[-1]

    if chat_id not in TELAYSPAM_TASKS:
        await cb.answer("Task tidak aktif.", show_alert=True)
        return

    config = TELAYSPAM_TASKS[chat_id]["config"]
    current_enabled = config.get("react_enabled", True)
    new_enabled = not current_enabled
    config["react_enabled"] = new_enabled

    status = "AKTIF" if new_enabled else "NONAKTIF"
    emoji = config["emot_react"] if config["emot_react"] and config["emot_react"].lower() != "none" else "None"
    
    await cb.answer(f"Reaction: {status} ({emoji})", show_alert=True)
    
    if USER_CLIENT:
        await USER_CLIENT.send_message(
            LOG_CHAT_ID,
            f"REACTION TOGGLED\n"
            f"Chat: {config['destination']}\n"
            f"Status: {status}\n"
            f"Emoji: {emoji}"
        )

    # Update tombol di notif utama
    try:
        notif_msg = TELAYSPAM_TASKS[chat_id].get("notif_msg")
        if notif_msg:
            await update_reaction_button(notif_msg, chat_id, new_enabled, emoji if new_enabled else None)
    except Exception as e:
        Altruix.log(f"Gagal update tombol reaction: {e}", level=40)

@Altruix.on_callback_query(filters.regex(r"select_emoji_(-?\d+)"))
@log_errors
async def select_emoji_handler(c: Client, cb):
    """Handler untuk memilih emoji reaction"""
    data = cb.data
    chat_id = data.split("_")[-1]

    if chat_id not in TELAYSPAM_TASKS:
        await cb.answer("Task tidak aktif.", show_alert=True)
        return

    # Buat keyboard dengan emoji yang valid
    keyboard = []
    row = []
    
    # Tampilkan 8 emoji per baris
    for i, emoji in enumerate(VALID_EMOJIS):
        row.append(InlineKeyboardButton(emoji, callback_data=f"set_emoji_{chat_id}_{emoji}"))
        if (i + 1) % 8 == 0:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    # Tambah tombol cancel
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_emoji_{chat_id}")])
    
    # Simpan status pemilihan emoji
    EMOJI_SELECTION_WAITING[chat_id] = True
    
    if USER_CLIENT:
        await USER_CLIENT.send_message(
            LOG_CHAT_ID,
            f"Pilih emoji reaction untuk task di chat {chat_id}:\n\n"
            f"Klik emoji di bawah untuk memilih, atau klik Cancel untuk membatalkan.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    await cb.answer("Pilih emoji dari daftar...", show_alert=False)

@Altruix.on_callback_query(filters.regex(r"set_emoji_(-?\d+)_(.+)"))
@log_errors
async def set_emoji_handler(c: Client, cb):
    """Handler untuk menyetel emoji yang dipilih"""
    data = cb.data
    parts = data.split("_")
    chat_id = parts[2]
    emoji = parts[3]

    if chat_id not in TELAYSPAM_TASKS:
        await cb.answer("Task tidak aktif.", show_alert=True)
        return

    # Validasi emoji
    if emoji not in VALID_EMOJIS:
        await cb.answer("Emoji tidak valid!", show_alert=True)
        return

    config = TELAYSPAM_TASKS[chat_id]["config"]
    old_emoji = config["emot_react"]
    config["emot_react"] = emoji
    config["react_enabled"] = True  # Otomatis enable reaction saat pilih emoji

    await cb.answer(f"Emoji reaction disetel ke: {emoji}", show_alert=True)
    
    if USER_CLIENT:
        await USER_CLIENT.send_message(
            LOG_CHAT_ID,
            f"EMOJI UPDATED\n"
            f"Chat: {config['destination']}\n"
            f"Emoji sebelumnya: {old_emoji if old_emoji else 'None'}\n"
            f"Emoji baru: {emoji}\n"
            f"Status: AKTIF"
        )

    # Update tombol di notif utama
    try:
        notif_msg = TELAYSPAM_TASKS[chat_id].get("notif_msg")
        if notif_msg:
            await update_reaction_button(notif_msg, chat_id, True, emoji)
    except Exception as e:
        Altruix.log(f"Gagal update tombol reaction: {e}", level=40)
    
    # Hapus status pemilihan emoji
    EMOJI_SELECTION_WAITING.pop(chat_id, None)
    
    # Hapus pesan pemilihan emoji
    try:
        await cb.message.delete()
    except:
        pass

@Altruix.on_callback_query(filters.regex(r"cancel_emoji_(-?\d+)"))
@log_errors
async def cancel_emoji_handler(c: Client, cb):
    """Handler untuk cancel pemilihan emoji"""
    data = cb.data
    chat_id = data.split("_")[-1]
    
    EMOJI_SELECTION_WAITING.pop(chat_id, None)
    
    await cb.answer("Pemilihan emoji dibatalkan", show_alert=True)
    
    # Hapus pesan pemilihan emoji
    try:
        await cb.message.delete()
    except:
        pass

@Altruix.on_callback_query(filters.regex(r"(stop|pause|resume|cek|recurring|delete_latest|delete_oldest|edit_last|edit_msglist|cancel_edit|cancel_editlast)_(-?\d+)"))
@log_errors
async def handle_task_control(c: Client, cb):
    """Handler untuk kontrol task via callback"""
    data = cb.data
    action, chat_id = data.rsplit("_", 1)
    
    try:
        # Resolusi chat untuk mendapatkan title
        try:
            target_chat = await c.get_chat(int(chat_id))
            chat_title = f"{target_chat.title}" if hasattr(target_chat, 'title') else (target_chat.first_name or target_chat.username or f"ID: {chat_id}")
        except Exception as err:
            chat_title = f"ID: {chat_id}"
            Altruix.log(f"Error resolusi chat untuk chat_id {chat_id}: {err}", level=40)

        if action in ["stop", "pause", "resume", "cek"]:
            if chat_id not in TELAYSPAM_TASKS:
                await cb.answer("⚫️ Task tidak aktif di chat ini.", show_alert=True)
                if USER_CLIENT:
                    await USER_CLIENT.send_message(LOG_CHAT_ID, f"⚫️ Task tidak aktif di chat ini.")
                return

        if action == "stop":
            TELAYSPAM_TASKS[chat_id]["running"] = False
            TELAYSPAM_TASKS[chat_id]["pause_event"].set()
            if "task" in TELAYSPAM_TASKS[chat_id]:
                TELAYSPAM_TASKS[chat_id]["task"].cancel()
            await cb.answer(f"🔴 Task distop di {chat_title}.", show_alert=True)
            if USER_CLIENT:
                await USER_CLIENT.send_message(LOG_CHAT_ID, f"🔴 Task distop di {chat_title}.")
        
        elif action == "pause":
            TELAYSPAM_TASKS[chat_id]["pause_event"].clear()
            await cb.answer(f"🟡 Task dipause di {chat_title}.", show_alert=True)
            if USER_CLIENT:
                await USER_CLIENT.send_message(LOG_CHAT_ID, f"🟡 Task dipause di {chat_title}.")
        
        elif action == "resume":
            TELAYSPAM_TASKS[chat_id]["pause_event"].set()
            await cb.answer(f"🟢 Task diresume di {chat_title}.", show_alert=True)
            if USER_CLIENT:
                await USER_CLIENT.send_message(LOG_CHAT_ID, f"🟢 Task diresume di {chat_title}.")
        
        elif action == "cek":
            status = TELAYSPAM_TASKS[chat_id]
            if status["running"]:
                if status["pause_event"].is_set():
                    status_text = f"🔵 Task dirunning di {chat_title} (running)."
                else:
                    status_text = f"🟡 Task dipause di {chat_title} (paused)."
            else:
                status_text = f"🔴 Task distop di {chat_title} (stopped)."
            await cb.answer(status_text, show_alert=True)
            if USER_CLIENT:
                await USER_CLIENT.send_message(LOG_CHAT_ID, f"{status_text}.")
        
        elif action == "recurring":
            # PERBAIKAN UTAMA: Gunakan client userbot dari COMPLETED_TASKS atau USER_CLIENT
            if chat_id in TELAYSPAM_TASKS:
                await cb.answer("⚠️ Task masih berjalan, hentikan dulu sebelum recurring.", show_alert=True)
                if USER_CLIENT:
                    await USER_CLIENT.send_message(LOG_CHAT_ID, f"⚠️ Task masih berjalan di {chat_title}, hentikan dulu.")
                return
            
            config = COMPLETED_TASKS.get(chat_id)
            if not config:
                await cb.answer("⚫️ Tidak ada task selesai untuk diulang di chat ini.", show_alert=True)
                if USER_CLIENT:
                    await USER_CLIENT.send_message(LOG_CHAT_ID, f"⚫️ Tidak ada task selesai untuk diulang di {chat_title}.")
                return
            
            # PERBAIKAN: Gunakan USER_CLIENT (userbot) untuk recurring, bukan client dari callback (bot)
            recurring_client = USER_CLIENT if USER_CLIENT else c
            
            success = await start_relayspam(
                recurring_client,  # PERBAIKAN: Gunakan userbot bukan bot
                config["destination"],
                config["start_delay"],
                config["stop_delay"],
                config["step"],
                config["count"],
                config["old_purge"],
                config["emot_react"],
                config["msg_list"],
                config["is_batch"],
                config.get("react_enabled", True)
            )
            
            if success:
                await cb.answer(f"🔁 Task recurring dimulai ulang di {chat_title}.", show_alert=True)
                if USER_CLIENT:
                    await USER_CLIENT.send_message(LOG_CHAT_ID, f"🔁 Task recurring dimulai ulang di {chat_title}.")
            else:
                await cb.answer(f"❌ Gagal memulai recurring di {chat_title}.", show_alert=True)
                if USER_CLIENT:
                    await USER_CLIENT.send_message(LOG_CHAT_ID, f"❌ Gagal memulai recurring di {chat_title}.")
        
        elif action == "delete_latest":
            try:
                # PERBAIKAN: Gunakan client dari task jika ada, atau USER_CLIENT untuk menghapus pesan
                delete_client = TELAYSPAM_TASKS.get(chat_id, {}).get("client", USER_CLIENT if USER_CLIENT else c)
                
                messages = []
                async for message in delete_client.get_chat_history(int(chat_id), limit=30):
                    messages.append(message)
                
                if messages:
                    # PERBAIKAN: Hanya hapus pesan yang dikirim oleh userbot ini
                    message_ids = [msg.id for msg in messages if msg.from_user and msg.from_user.id == delete_client.me.id]
                    try:
                        if message_ids:
                            # PERBAIKAN: Gunakan delete_client (userbot) untuk menghapus pesan
                            await delete_client.delete_messages(int(chat_id), message_ids)
                            del_suk = len(message_ids)
                            await asyncio.sleep(3)
                            await cb.answer(f"🗑️ Berhasil hapus {del_suk} pesan terbaru di {chat_title}.", show_alert=True)
                            if USER_CLIENT:
                                await USER_CLIENT.send_message(LOG_CHAT_ID, f"🗑️ Berhasil hapus {del_suk} pesan terbaru di {chat_title}.")
                        else:
                            await cb.answer("⚫️ Tidak ada pesan dari userbot untuk dihapus.", show_alert=True)
                            if USER_CLIENT:
                                await USER_CLIENT.send_message(LOG_CHAT_ID, f"⚫️ Tidak ada pesan dari userbot untuk dihapus di {chat_title}.")
                    except Exception as del_err:
                        Altruix.log(f"Error saat menghapus pesan terbaru: {del_err}", level=40)
                        await cb.answer(f"❌ Gagal hapus pesan terbaru: {del_err}", show_alert=True)
                        if USER_CLIENT:
                            await USER_CLIENT.send_message(LOG_CHAT_ID, f"❌ Gagal hapus pesan terbaru di {chat_title}: {del_err}")
                else:
                    await cb.answer("⚫️ Tidak ada pesan untuk dihapus.", show_alert=True)
                    if USER_CLIENT:
                        await USER_CLIENT.send_message(LOG_CHAT_ID, f"⚫️ Tidak ada pesan untuk dihapus di {chat_title}.")
            except Exception as err:
                await cb.answer(f"Error: {err}", show_alert=True)
                if USER_CLIENT:
                    await USER_CLIENT.send_message(LOG_CHAT_ID, f"⚠️ **Error :** {err}")
        
        elif action == "delete_oldest":
            try:
                # PERBAIKAN: Gunakan client dari task jika ada, atau USER_CLIENT untuk menghapus pesan
                delete_client = TELAYSPAM_TASKS.get(chat_id, {}).get("client", USER_CLIENT if USER_CLIENT else c)
                
                messages = []
                count = 0
                async for message in delete_client.get_chat_history(int(chat_id), limit=30):
                    messages.append(message)
                    count += 1
                    if count >= 30:
                        break
                
                if messages:
                    # PERBAIKAN: Hanya hapus pesan yang dikirim oleh userbot ini
                    message_ids = [msg.id for msg in messages if msg.from_user and msg.from_user.id == delete_client.me.id]
                    try:
                        if message_ids:
                            # PERBAIKAN: Gunakan delete_client (userbot) untuk menghapus pesan
                            await delete_client.delete_messages(int(chat_id), message_ids)
                            del_suk = len(message_ids)
                            await asyncio.sleep(3)
                            await cb.answer(f"🗑️ Berhasil hapus {del_suk} pesan terlama di {chat_title}.", show_alert=True)
                            if USER_CLIENT:
                                await USER_CLIENT.send_message(LOG_CHAT_ID, f"🗑️ Berhasil hapus {del_suk} pesan terlama di {chat_title}.")
                        else:
                            await cb.answer("⚫️ Tidak ada pesan dari userbot untuk dihapus.", show_alert=True)
                            if USER_CLIENT:
                                await USER_CLIENT.send_message(LOG_CHAT_ID, f"⚫️ Tidak ada pesan dari userbot untuk dihapus di {chat_title}.")
                    except Exception as del_err:
                        Altruix.log(f"Error saat menghapus pesan terlama: {del_err}", level=40)
                        await cb.answer(f"❌ Gagal hapus pesan terlama: {del_err}", show_alert=True)
                        if USER_CLIENT:
                            await USER_CLIENT.send_message(LOG_CHAT_ID, f"❌ Gagal hapus pesan terlama di {chat_title}: {del_err}")
                else:
                    await cb.answer("⚫️ Tidak ada pesan untuk dihapus.", show_alert=True)
                    if USER_CLIENT:
                        await USER_CLIENT.send_message(LOG_CHAT_ID, f"⚫️ Tidak ada pesan untuk dihapus di {chat_title}.")
            except Exception as err:
                await cb.answer(f"Error: {err}", show_alert=True)
                if USER_CLIENT:
                    await USER_CLIENT.send_message(LOG_CHAT_ID, f"⚠️ **Error :** {err}")
        
        elif action == "edit_last":
            try:
                # PERBAIKAN: Gunakan client dari task jika ada, atau USER_CLIENT untuk edit pesan
                edit_client = TELAYSPAM_TASKS.get(chat_id, {}).get("client", USER_CLIENT if USER_CLIENT else c)
                
                messages = []
                async for message in edit_client.get_chat_history(int(chat_id), limit=1):
                    messages.append(message)
                    break
                
                if messages and messages[0].from_user and messages[0].from_user.id == edit_client.me.id:
                    last_msg_id = messages[0].id
                    old_text = messages[0].text or messages[0].caption or ""
                    notif_msg = (
                        f"✏️ Edit Last Message untuk {chat_title}\n\n"
                        f"Masukkan teks baru untuk mengedit pesan terakhir.\n\n"
                        f"Balas pesan ini dengan teks baru.\n"
                        f"Contoh balasan: Edited message here\n"
                        f"Klik 'Cancel' untuk membatalkan proses edit."
                    )
                    cancel_button = [[InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_editlast_{chat_id}")]]
                    
                    if USER_CLIENT:
                        edit_notif_msg = await USER_CLIENT.send_message(
                            LOG_CHAT_ID,
                            notif_msg,
                            reply_markup=InlineKeyboardMarkup(cancel_button)
                        )
                        EDIT_LASTMSG_WAITING[chat_id] = {
                            "target_chat_id": int(chat_id),
                            "last_msg_id": last_msg_id,
                            "old_text": old_text,
                            "notif_msg_id": edit_notif_msg.id,
                            "client": edit_client  # Simpan client untuk edit
                        }
                        await cb.answer(f"📝 Silakan masukkan teks baru untuk edit last msg di {chat_title}.", show_alert=True)
                else:
                    await cb.answer("⚫️ Tidak ada pesan terakhir dari userbot untuk diedit.", show_alert=True)
                    if USER_CLIENT:
                        await USER_CLIENT.send_message(LOG_CHAT_ID, f"⚫️ Tidak ada pesan terakhir untuk diedit di {chat_title}.")
            except Exception as edit_err:
                Altruix.log(f"Error saat memulai edit last msg: {edit_err}", level=40)
                await cb.answer(f"❌ Gagal memulai edit: {edit_err}", show_alert=True)
                if USER_CLIENT:
                    await USER_CLIENT.send_message(LOG_CHAT_ID, f"❌ Gagal memulai edit last msg di {chat_title}: {edit_err}")
        
        elif action == "edit_msglist":
            config = None
            was_running = False
            task_client = None
            
            if chat_id in TELAYSPAM_TASKS:
                was_running = True
                task_client = TELAYSPAM_TASKS[chat_id].get("client")
                TELAYSPAM_TASKS[chat_id]["running"] = False
                TELAYSPAM_TASKS[chat_id]["pause_event"].set()
                if "task" in TELAYSPAM_TASKS[chat_id]:
                    TELAYSPAM_TASKS[chat_id]["task"].cancel()
                config = TELAYSPAM_TASKS[chat_id].get("config")
                TELAYSPAM_TASKS.pop(chat_id, None)
            elif chat_id in COMPLETED_TASKS:
                config = COMPLETED_TASKS.get(chat_id)
            else:
                await cb.answer("⚫️ Tidak ada task aktif atau selesai untuk mengedit msg_list.", show_alert=True)
                if USER_CLIENT:
                    await USER_CLIENT.send_message(LOG_CHAT_ID, f"⚫️ Tidak ada task untuk mengedit msg_list di {chat_title}.")
                return

            if config:
                old_msg_list = config["msg_list"]
                is_batch = config["is_batch"]
                notif_msg = (
                    f"✏️ Edit Message List untuk {chat_title}\n\n"
                    f"Masukkan pesan baru dengan format:\n"
                    f"- Untuk mode acak: [\"hello world\", \"hello dunia\", \"good morning\"]\n"
                    f"- Untuk mode batch: [(\"✅ hello world\", 50), (\"❇️ hello dunia\", 50)]\n\n"
                    f"Balas pesan ini dengan list pesan baru. Pastikan jumlah pesan atau total batch sesuai dengan count ({config['count']}).\n"
                    f"Contoh balasan: [\"hello world\", \"hello dunia\"]\n"
                    f"Klik 'Cancel' untuk membatalkan proses edit."
                )
                cancel_button = [[InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_edit_{chat_id}")]]
                
                if USER_CLIENT:
                    edit_notif_msg = await USER_CLIENT.send_message(
                        LOG_CHAT_ID,
                        notif_msg,
                        reply_markup=InlineKeyboardMarkup(cancel_button)
                    )
                    EDIT_MSGLIST_WAITING[chat_id] = {
                        "config": config,
                        "was_running": was_running,
                        "notif_msg_id": edit_notif_msg.id,
                        "client": task_client or USER_CLIENT  # Simpan client untuk restart
                    }
                    await cb.answer(f"📝 Silakan masukkan list pesan baru di {chat_title}.", show_alert=True)
            else:
                await cb.answer("⚫️ Tidak ada config untuk mengedit msg_list.", show_alert=True)
                if USER_CLIENT:
                    await USER_CLIENT.send_message(LOG_CHAT_ID, f"⚫️ Tidak ada config untuk mengedit msg_list di {chat_title}.")
        
        elif action == "cancel_edit":
            if chat_id in EDIT_MSGLIST_WAITING:
                config = EDIT_MSGLIST_WAITING[chat_id]["config"]
                was_running = EDIT_MSGLIST_WAITING[chat_id]["was_running"]
                notif_msg_id = EDIT_MSGLIST_WAITING[chat_id]["notif_msg_id"]
                task_client = EDIT_MSGLIST_WAITING[chat_id].get("client", USER_CLIENT)
                EDIT_MSGLIST_WAITING.pop(chat_id, None)
                await cb.answer(f"❌ Proses edit msg_list dibatalkan di {chat_title}.", show_alert=True)
                
                if USER_CLIENT:
                    await USER_CLIENT.send_message(
                        LOG_CHAT_ID,
                        f"❌ Proses edit msg_list dibatalkan di {chat_title}.",
                        reply_to_message_id=notif_msg_id
                    )
                
                if was_running and task_client:
                    success = await start_relayspam(
                        task_client,
                        config["destination"],
                        config["start_delay"],
                        config["stop_delay"],
                        config["step"],
                        config["count"],
                        config["old_purge"],
                        config["emot_react"],
                        config["msg_list"],
                        config["is_batch"],
                        config.get("react_enabled", True)
                    )
                    if success and USER_CLIENT:
                        await USER_CLIENT.send_message(
                            LOG_CHAT_ID,
                            f"✅ Task dikembalikan ke config default dan dimulai ulang di {chat_title}."
                        )
                    elif USER_CLIENT:
                        await USER_CLIENT.send_message(
                            LOG_CHAT_ID,
                            f"❌ Gagal memulai ulang task di {chat_title}."
                        )
            else:
                await cb.answer("⚫️ Tidak ada proses edit msg_list untuk dibatalkan.", show_alert=True)
                if USER_CLIENT:
                    await USER_CLIENT.send_message(LOG_CHAT_ID, f"⚫️ Tidak ada proses edit msg_list untuk dibatalkan di {chat_title}.")
        
        elif action == "cancel_editlast":
            if chat_id in EDIT_LASTMSG_WAITING:
                notif_msg_id = EDIT_LASTMSG_WAITING[chat_id]["notif_msg_id"]
                EDIT_LASTMSG_WAITING.pop(chat_id, None)
                await cb.answer(f"❌ Proses edit last msg dibatalkan di {chat_title}.", show_alert=True)
                
                if USER_CLIENT:
                    await USER_CLIENT.send_message(
                        LOG_CHAT_ID,
                        f"❌ Proses edit last msg dibatalkan di {chat_title}.",
                        reply_to_message_id=notif_msg_id
                    )
            else:
                await cb.answer("⚫️ Tidak ada proses edit last msg untuk dibatalkan.", show_alert=True)
                if USER_CLIENT:
                    await USER_CLIENT.send_message(LOG_CHAT_ID, f"⚫️ Tidak ada proses edit last msg untuk dibatalkan di {chat_title}.")
    
    except FloodWait as fwe:
        Altruix.log(f"FloodWaitError saat menangani aksi {action} untuk chat {chat_id}: Waiting for {fwe.value} seconds", level=30)
        await cb.answer(f"⚠️ Terlalu banyak permintaan. Tunggu {fwe.value} detik.", show_alert=True)
        if USER_CLIENT:
            await USER_CLIENT.send_message(LOG_CHAT_ID, f"⚠️ **FloodWaitError:** Tunggu {fwe.value} detik untuk aksi {action} di {chat_title}.")
    except ChatWriteForbidden as cwe:
        Altruix.log(f"ChatWriteForbiddenError saat menangani aksi {action} untuk chat {chat_id}: Bot tidak memiliki izin", level=30)
        await cb.answer(f"❌ Bot tidak memiliki izin untuk melakukan aksi ini di {chat_title}.", show_alert=True)
        if USER_CLIENT:
            await USER_CLIENT.send_message(LOG_CHAT_ID, f"❌ **ChatWriteForbiddenError:** Bot tidak memiliki izin untuk aksi {action} di {chat_title}.")
    except Exception as err:
        Altruix.log(f"Error saat menangani aksi {action} untuk chat {chat_id}: {err}", level=40)
        await cb.answer(f"Error: {err}", show_alert=True)
        if USER_CLIENT:
            await USER_CLIENT.send_message(LOG_CHAT_ID, f"⚠️ **Error :** {err}")

@Altruix.on_callback_query(filters.regex(r"(cekall|stopall|recurringall|pauseall|resumeall)"))
@log_errors
async def handle_global_controls(c: Client, cb):
    """Handler untuk kontrol global semua task"""
    data = cb.data
    
    if data == "cekall":
        if not TELAYSPAM_TASKS:
            await cb.answer("⚫️ Tidak ada task relayspam yang aktif.", show_alert=True)
            if USER_CLIENT:
                await USER_CLIENT.send_message(LOG_CHAT_ID, f"⚫️ Tidak ada task relayspam yang aktif.")
            return

        status_list = []
        for chat_id, status in TELAYSPAM_TASKS.items():
            try:
                target_chat = await c.get_chat(int(chat_id))
                chat_title = f"{target_chat.title}" if hasattr(target_chat, 'title') else (target_chat.first_name or target_chat.username or f"ID: {chat_id}")
                if status["running"]:
                    if status["pause_event"].is_set():
                        status_text = f"🔵 running di {chat_title}"
                    else:
                        status_text = f"🟡 paused di {chat_title}"
                else:
                    status_text = f"🔴 stopped di {chat_title}"
                status_list.append(status_text)
            except Exception as err:
                status_list.append(f"❓ Unknown chat (ID: {chat_id})")
                if USER_CLIENT:
                    await USER_CLIENT.send_message(LOG_CHAT_ID, f"Error: {err}")

        output = "**Status Semua Task:**\n\n" + "\n".join(status_list)
        await cb.answer(output, show_alert=True)
        if USER_CLIENT:
            await USER_CLIENT.send_message(LOG_CHAT_ID, f"{output}")
    
    elif data == "stopall":
        if not TELAYSPAM_TASKS:
            await cb.answer("⚫️ Tidak ada task aktif untuk dihentikan.", show_alert=True)
            if USER_CLIENT:
                await USER_CLIENT.send_message(LOG_CHAT_ID, "⚫️ Tidak ada task aktif untuk dihentikan.")
            return
        
        stopped_count = 0
        for chat_id in list(TELAYSPAM_TASKS.keys()):
            TELAYSPAM_TASKS[chat_id]["running"] = False
            TELAYSPAM_TASKS[chat_id]["pause_event"].set()
            if "task" in TELAYSPAM_TASKS[chat_id]:
                TELAYSPAM_TASKS[chat_id]["task"].cancel()
            stopped_count += 1
        
        await cb.answer(f"🔴 Semua {stopped_count} task dihentikan.", show_alert=True)
        if USER_CLIENT:
            await USER_CLIENT.send_message(LOG_CHAT_ID, f"🔴 Semua {stopped_count} task dihentikan.")
    
    elif data == "recurringall":
        if not COMPLETED_TASKS:
            await cb.answer("⚫️ Tidak ada task selesai untuk diulang.", show_alert=True)
            if USER_CLIENT:
                await USER_CLIENT.send_message(LOG_CHAT_ID, "⚫️ Tidak ada task selesai untuk diulang.")
            return
        
        restarted_count = 0
        for chat_id, config in list(COMPLETED_TASKS.items()):
            if chat_id in TELAYSPAM_TASKS:
                continue
            
            # PERBAIKAN: Gunakan USER_CLIENT (userbot) untuk recurring all
            recurring_client = USER_CLIENT if USER_CLIENT else c
            
            success = await start_relayspam(
                recurring_client,
                config["destination"],
                config["start_delay"],
                config["stop_delay"],
                config["step"],
                config["count"],
                config["old_purge"],
                config["emot_react"],
                config["msg_list"],
                config["is_batch"],
                config.get("react_enabled", True)
            )
            if success:
                restarted_count += 1
        
        await cb.answer(f"🔁 {restarted_count} task recurring dimulai ulang.", show_alert=True)
        if USER_CLIENT:
            await USER_CLIENT.send_message(LOG_CHAT_ID, f"🔁 {restarted_count} task recurring dimulai ulang.")
    
    elif data == "pauseall":
        if not TELAYSPAM_TASKS:
            await cb.answer("⚫️ Tidak ada task aktif untuk dipause.", show_alert=True)
            if USER_CLIENT:
                await USER_CLIENT.send_message(LOG_CHAT_ID, "⚫️ Tidak ada task aktif untuk dipause.")
            return
        
        paused_chats = []
        paused_count = 0
        for chat_id in list(TELAYSPAM_TASKS.keys()):
            if TELAYSPAM_TASKS[chat_id]["running"] and TELAYSPAM_TASKS[chat_id]["pause_event"].is_set():
                try:
                    target_chat = await c.get_chat(int(chat_id))
                    chat_title = f"{target_chat.title}" if hasattr(target_chat, 'title') else (target_chat.first_name or target_chat.username or f"ID: {chat_id}")
                    TELAYSPAM_TASKS[chat_id]["pause_event"].clear()
                    paused_count += 1
                    paused_chats.append(f"🟡 Paused di {chat_title}")
                except Exception as err:
                    Altruix.log(f"Error resolusi chat {chat_id} untuk pauseall: {err}", level=40)
                    paused_chats.append(f"❓ Paused di Unknown Chat (ID: {chat_id})")
                    TELAYSPAM_TASKS[chat_id]["pause_event"].clear()
                    paused_count += 1
        
        if paused_count == 0:
            await cb.answer("⚫️ Tidak ada task aktif yang sedang running untuk dipause.", show_alert=True)
            if USER_CLIENT:
                await USER_CLIENT.send_message(LOG_CHAT_ID, "⚫️ Tidak ada task aktif yang sedang running untuk dipause.")
        else:
            output = f"🟡 Semua {paused_count} task dipause:\n\n" + "\n".join(paused_chats)
            await cb.answer(f"🟡 Semua {paused_count} task dipause.", show_alert=True)
            if USER_CLIENT:
                await USER_CLIENT.send_message(LOG_CHAT_ID, output)
    
    elif data == "resumeall":
        if not TELAYSPAM_TASKS:
            await cb.answer("⚫️ Tidak ada task untuk diresume.", show_alert=True)
            if USER_CLIENT:
                await USER_CLIENT.send_message(LOG_CHAT_ID, "⚫️ Tidak ada task untuk diresume.")
            return
        
        resumed_chats = []
        resumed_count = 0
        for chat_id in list(TELAYSPAM_TASKS.keys()):
            if TELAYSPAM_TASKS[chat_id]["running"] and not TELAYSPAM_TASKS[chat_id]["pause_event"].is_set():
                try:
                    target_chat = await c.get_chat(int(chat_id))
                    chat_title = f"{target_chat.title}" if hasattr(target_chat, 'title') else (target_chat.first_name or target_chat.username or f"ID: {chat_id}")
                    TELAYSPAM_TASKS[chat_id]["pause_event"].set()
                    resumed_count += 1
                    resumed_chats.append(f"🟢 Resumed di {chat_title}")
                except Exception as err:
                    Altruix.log(f"Error resolusi chat {chat_id} untuk resumeall: {err}", level=40)
                    resumed_chats.append(f"❓ Resumed di Unknown Chat (ID: {chat_id})")
                    TELAYSPAM_TASKS[chat_id]["pause_event"].set()
                    resumed_count += 1
        
        if resumed_count == 0:
            await cb.answer("⚫️ Tidak ada task yang dipause untuk diresume.", show_alert=True)
            if USER_CLIENT:
                await USER_CLIENT.send_message(LOG_CHAT_ID, "⚫️ Tidak ada task yang dipause untuk diresume.")
        else:
            output = f"🟢 Semua {resumed_count} task diresume:\n\n" + "\n".join(resumed_chats)
            await cb.answer(f"🟢 Semua {resumed_count} task diresume.", show_alert=True)
            if USER_CLIENT:
                await USER_CLIENT.send_message(LOG_CHAT_ID, output)

# ==================== MESSAGE HANDLER UNTUK EDIT MSG LIST & LAST MSG ====================

@Altruix.on_message(filters.chat(LOG_CHAT_ID) & filters.incoming & filters.reply)
@log_errors
async def handle_msg_list_input(c: Client, m: Message):
    """
    Handler untuk menangani input pesan baru dari pengguna sebagai balasan 
    ke notifikasi edit msg_list atau edit last msg
    """
    if m.reply_to_message:
        reply_msg = m.reply_to_message
        reply_msg_id = reply_msg.id
        
        # Cek untuk edit msg_list
        if reply_msg_id in [waiting["notif_msg_id"] for waiting in EDIT_MSGLIST_WAITING.values()]:
            chat_id = next(cid for cid, waiting in EDIT_MSGLIST_WAITING.items() if waiting["notif_msg_id"] == reply_msg_id)
            config = EDIT_MSGLIST_WAITING[chat_id]["config"]
            was_running = EDIT_MSGLIST_WAITING[chat_id]["was_running"]
            task_client = EDIT_MSGLIST_WAITING[chat_id].get("client", USER_CLIENT)
            is_batch = config["is_batch"]
            
            # Resolusi chat_title
            try:
                target_chat = await c.get_chat(int(chat_id))
                chat_title = f"{target_chat.title}" if hasattr(target_chat, 'title') else (target_chat.first_name or target_chat.username or f"ID: {chat_id}")
            except Exception as err:
                chat_title = f"ID: {chat_id}"
                Altruix.log(f"Error resolusi entity untuk chat_id {chat_id}: {err}", level=40)
            
            try:
                # Parse input pengguna
                new_msg_list_str = m.text.strip()
                new_msg_list = ast.literal_eval(new_msg_list_str)
                if not isinstance(new_msg_list, list) or not new_msg_list:
                    raise ValueError("Input harus berupa list array yang valid.")

                # Validasi format sesuai mode
                if is_batch:
                    if not all(isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str) and isinstance(item[1], int) for item in new_msg_list):
                        raise ValueError("Format untuk mode batch harus [(pesan, jumlah), ...].")
                    total_batch_count = sum(b_count for _, b_count in new_msg_list)
                    if total_batch_count != config["count"]:
                        raise ValueError(f"Total jumlah batch ({total_batch_count}) tidak sesuai dengan count ({config['count']}).")
                else:
                    if not all(isinstance(item, str) for item in new_msg_list):
                        raise ValueError("Format untuk mode acak harus [\"pesan1\", \"pesan2\", ...].")
                    if len(new_msg_list) < 1:
                        raise ValueError("List pesan tidak boleh kosong.")

                # Update config dengan msg_list baru
                old_msg_list = config["msg_list"]
                config["msg_list"] = new_msg_list
                COMPLETED_TASKS[chat_id] = config

                # Mulai task baru dengan msg_list yang diubah
                if task_client:
                    success = await start_relayspam(
                        task_client,
                        config["destination"],
                        config["start_delay"],
                        config["stop_delay"],
                        config["step"],
                        config["count"],
                        config["old_purge"],
                        config["emot_react"],
                        config["msg_list"],
                        config["is_batch"],
                        config.get("react_enabled", True)
                    )
                    if success:
                        await m.reply(
                            f"✏️ Berhasil edit msg_list di {chat_title}:\n"
                            f"Sebelum: {old_msg_list}\n"
                            f"Sesudah: {new_msg_list}\n"
                            f"Task {'dihentikan dan ' if was_running else ''}dimulai ulang dengan msg_list baru."
                        )
                        EDIT_MSGLIST_WAITING.pop(chat_id, None)
                    else:
                        await m.reply(f"❌ Gagal memulai task dengan msg_list baru di {chat_title}.")
                else:
                    await m.reply(f"❌ Tidak ada client yang tersedia untuk memulai ulang task di {chat_title}.")
            
            except (ValueError, SyntaxError) as err:
                await m.reply(
                    f"**Error Parsing Input:** {err}\n"
                    f"Gunakan format yang benar:\n"
                    f"- Mode acak: [\"hello world\", \"hello dunia\", \"good morning\"]\n"
                    f"- Mode batch: [(\"✅ hello world\", 50), (\"❇️ hello dunia\", 50)]"
                )
            except Exception as err:
                Altruix.log(f"Error saat memproses input msg_list: {err}", level=40)
                await m.reply(f"⚠️ **Error:** {err}")
        
        # Cek untuk edit last msg
        elif reply_msg_id in [waiting["notif_msg_id"] for waiting in EDIT_LASTMSG_WAITING.values()]:
            chat_id = next(cid for cid, waiting in EDIT_LASTMSG_WAITING.items() if waiting["notif_msg_id"] == reply_msg_id)
            target_chat_id = EDIT_LASTMSG_WAITING[chat_id]["target_chat_id"]
            last_msg_id = EDIT_LASTMSG_WAITING[chat_id]["last_msg_id"]
            old_text = EDIT_LASTMSG_WAITING[chat_id]["old_text"]
            edit_client = EDIT_LASTMSG_WAITING[chat_id].get("client")
            
            # Resolusi chat_title
            try:
                target_chat = await c.get_chat(target_chat_id)
                chat_title = f"{target_chat.title}" if hasattr(target_chat, 'title') else (target_chat.first_name or target_chat.username or f"ID: {chat_id}")
            except Exception as err:
                chat_title = f"ID: {chat_id}"
                Altruix.log(f"Error resolusi entity untuk chat_id {chat_id}: {err}", level=40)
            
            try:
                new_text = m.text.strip()
                if not new_text:
                    raise ValueError("Teks baru tidak boleh kosong.")

                if edit_client:
                    await edit_client.edit_message_text(target_chat_id, last_msg_id, new_text)
                    await asyncio.sleep(1)
                    await m.reply(
                        f"✏️ Berhasil edit last msg di {chat_title}:\n"
                        f"Sebelum: {old_text}\n"
                        f"Sesudah: {new_text}"
                    )
                    EDIT_LASTMSG_WAITING.pop(chat_id, None)
                else:
                    await m.reply(f"❌ Tidak ada client yang tersedia untuk mengedit pesan di {chat_title}.")
            
            except (ValueError, SyntaxError) as err:
                await m.reply(
                    f"**Error Parsing Input:** {err}\n"
                    f"Masukkan teks biasa sebagai balasan."
                )
            except Exception as err:
                Altruix.log(f"Error saat memproses input last msg: {err}", level=40)
                await m.reply(f"⚠️ **Error:** {err}")

# Log sukses loading
try:
    Altruix.log(f"[DEBUG] Loaded → {__plugin_name__} v{PLUGIN_VERSION}", level=20)
except Exception as e:
    logger.info(f"[DEBUG] Loaded → {__plugin_name__} v{PLUGIN_VERSION}")
