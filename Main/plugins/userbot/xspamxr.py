# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altruix/Altruix/blob/main/LICENSE >
#
# All rights reserved.

"""
✘ Commands Available -

• `{i}relayspam <chat/destination> <start_delay> <stop_delay> <step> <count> <delete/purge> <emot_react/optional> ["msg_1", "msg_2", ...]` 
   Atau `[("msg_1", batch_count1), ("msg_2", batch_count2), ...]`
   Spam ke chat tujuan dengan delay acak berinterval dan pesan acak dari list.

• `{i}srelayspam <chat/destination>` - Stop task
• `{i}prelayspam <chat/destination>` - Pause task  
• `{i}rrelayspam <chat/destination>` - Resume task
• `{i}relayspamcek <chat/destination>` - Check status
• `{i}relayspamcekall` - Check all tasks

**CHANGELOG:**
- ADDED: Tombol toggle untuk enable/disable purge old message secara real-time.
- ADDED: Update konfigurasi old_purge tanpa restart task.
- ADDED: Log perubahan status purge.
- FIXED: Purge kini menggunakan config real-time dari memory.
- ADDED: Opsi input pesan baru untuk Edit Last Msg dan Edit Msg List.
"""

import re
import os
import asyncio
import random
import shlex
import ast
import time
import logging

from Main import Altruix
from pyrogram import Client
from pyrogram.raw.functions import Ping
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram import errors
from pyrogram.errors import FloodWait, ChatWriteForbidden

from Main.core.types.message import Message
from Main.utils.essentials import Essentials
from Main.core.decorators import inline_check

# ─── LOGGER KHUSUS PLUGIN ───────────────────────────────────────────────
plugin_name = f"plugins/userbot/{os.path.basename(__file__)}"
__plugin_name__ = plugin_name if plugin_name else "xspamxr"
PLUGIN_VERSION = "v0.1.11.8:"

logger = logging.getLogger(f"{__plugin_name__}")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - [SET PLUGIN] - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# Dictionary global untuk menyimpan status task relayspam per chat
TELAYSPAM_TASKS = {}

# Dictionary untuk konfigurasi task yang telah selesai (untuk recurring)
COMPLETED_TASKS = {}

# Dictionary untuk menyimpan status edit msg_list yang sedang menunggu input pengguna
EDIT_MSGLIST_WAITING = {}

# Dictionary untuk menyimpan status edit last msg yang sedang menunggu input pengguna
EDIT_LASTMSG_WAITING = {}

# Referensi ke client utama Altruix
USER_CLIENT = Altruix.bot if hasattr(Altruix, 'bot') else Altruix.userbot

# --- Fungsi untuk update tombol purge secara dinamis ---
async def update_purge_button(message: Message, chat_id: str, purge_enabled: bool):
    """
    Update tombol purge di pesan notifikasi
    """
    try:
        clean_id = str(chat_id).replace("-100", "") if str(chat_id).startswith("-100") else str(chat_id)
        purge_text = "Purge: ON" if purge_enabled else "Purge: OFF"
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

async def spam_loop(client: Client, target_chat, chat_id: str, msg_list, delays_possible, 
                    count: int, start_delay: float, stop_delay: float, step: float, 
                    x_msg: Message, emot_react: str, is_batch: bool):
    """
    Loop utama untuk mengirim spam messages
    """
    try:
        sent_count = 0
        total_del_suk = 0
        total_del_ggl = 0
        
        if is_batch:
            for msg, b_count in msg_list:
                for _ in range(b_count):
                    if not TELAYSPAM_TASKS.get(chat_id, {}).get("running", False):
                        Altruix.log(f"Task dihentikan untuk chat {chat_id}")
                        await USER_CLIENT.send_message(
                            Altruix.config.LOG_CHAT_ID, 
                            f"__Task dihentikan untuk chat {chat_id}__"
                        )
                        break
                    await TELAYSPAM_TASKS[chat_id]["pause_event"].wait()

                    # Gunakan config real-time untuk old_purge
                    old_purge_val = TELAYSPAM_TASKS[chat_id]["config"]["old_purge"]
                    del_suk, del_ggl = 0, 0
                    if old_purge_val > 0:
                        try:
                            messages = []
                            async for message in client.get_chat_history(target_chat.id, limit=old_purge_val * 2):
                                messages.append(message)
                            
                            if messages:
                                my_messages = [msg for msg in messages if msg.from_user and msg.from_user.id == client.me.id][:old_purge_val]
                                message_ids = [msg.id for msg in my_messages]
                                
                                if message_ids:
                                    await client.delete_messages(target_chat.id, message_ids)
                                    del_suk = len(message_ids)
                                    await asyncio.sleep(3)
                                else:
                                    del_suk = 0
                                    
                                del_ggl = old_purge_val - del_suk
                                total_del_suk += del_suk
                                total_del_ggl += del_ggl
                                
                                await USER_CLIENT.send_message(
                                    Altruix.config.LOG_CHAT_ID,
                                    f"[HAPUS]: Berhasil hapus <code>{del_suk}</code> pesan lama, gagal <code>{del_ggl}</code> pesan.",
                                    reply_to_message_id=x_msg.id,
                                    parse_mode="html"
                                )
                        except Exception as del_err:
                            Altruix.log(f"Error saat menghapus pesan: {del_err}", level=40)
                            await USER_CLIENT.send_message(
                                Altruix.config.LOG_CHAT_ID, 
                                f"Error hapus pesan: {del_err}", 
                                reply_to_message_id=x_msg.id
                            )

                    random_delay = random.choice(delays_possible)

                    while True:
                        try:
                            sent_msg = await client.send_message(target_chat.id, msg)
                            sent_count += 1

                            react_status = "tidak ada"
                            if emot_react and emot_react.lower() != "none":
                                try:
                                    await asyncio.sleep(3)
                                    await client.send_reaction(target_chat.id, sent_msg.id, emot_react)
                                    react_status = f"{emot_react} berhasil"
                                except Exception as react_err:
                                    Altruix.log(f"Error saat menambahkan reaksi: {react_err}", level=40)
                                    react_status = f"{emot_react} gagal"

                            remaining = count - sent_count
                            percentage = (sent_count / count) * 100 if count > 0 else 0
                            char_count = len(msg)
                            
                            clean_chat_id = str(target_chat.id).replace("-100", "")
                            
                            await USER_CLIENT.send_message(
                                Altruix.config.LOG_CHAT_ID,
                                f"<b>Pesan terkirim</b>\n"
                                f"Mode     : <code>{'Batch' if is_batch else 'Acak'}</code>\n"
                                f"Delay    : <code>{random_delay:.2f}</code> detik\n"
                                f"Sisa      : <code>{remaining}</code> pesan\n"
                                f"Progress : <code>{percentage:.2f}%</code>\n"
                                f"Length   : <code>{char_count}</code> karakter\n"
                                f"React   : <code>{react_status}</code> <b><a href=\"https://t.me/c/{clean_chat_id}/{sent_msg.id}\">here</a></b>\n"
                                f"Pesan    : <code>{msg}</code>",
                                reply_to_message_id=x_msg.id,
                                parse_mode="html"
                            )

                            await asyncio.sleep(random_delay)
                            break

                        except errors.exceptions.flood_420.SlowmodeWait as swe:
                            Altruix.log(f"SlowModeWaitError: Waiting for {swe.value} seconds", level=30)
                            await USER_CLIENT.send_message(
                                Altruix.config.LOG_CHAT_ID, 
                                f"** [ #ERROR ]** __SlowModeWaitError: Waiting for {swe.value} seconds__", 
                                reply_to_message_id=x_msg.id
                            )
                            await asyncio.sleep(swe.value)

                        except FloodWait as fwe:
                            Altruix.log(f"FloodWaitError: Waiting for {fwe.value} seconds", level=30)
                            await USER_CLIENT.send_message(
                                Altruix.config.LOG_CHAT_ID, 
                                f"** [ #ERROR ]** __FloodWaitError: Waiting for {fwe.value} seconds__", 
                                reply_to_message_id=x_msg.id
                            )
                            await asyncio.sleep(fwe.value)

                        except ChatWriteForbidden as cwe:
                            Altruix.log(f"Bot muted in chat {chat_id}: Pausing task automatically.", level=30)
                            await USER_CLIENT.send_message(
                                Altruix.config.LOG_CHAT_ID, 
                                f"** [ #ERROR ]** __UserBot muted in chat {target_chat.title}: Task paused automatically.__", 
                                reply_to_message_id=x_msg.id
                            )
                            TELAYSPAM_TASKS[chat_id]["pause_event"].clear()
                            break

                        except Exception as send_err:
                            Altruix.log(f"Error saat mengirim pesan: {send_err}", level=40)
                            await USER_CLIENT.send_message(
                                Altruix.config.LOG_CHAT_ID, 
                                f"** [ #ERROR ]** __Error saat mengirim pesan: {send_err}__", 
                                reply_to_message_id=x_msg.id
                            )
                            await asyncio.sleep(5)

        else:  # Mode acak
            for _ in range(count):
                if not TELAYSPAM_TASKS.get(chat_id, {}).get("running", False):
                    Altruix.log(f"Task dihentikan untuk chat {chat_id}")
                    await USER_CLIENT.send_message(
                        Altruix.config.LOG_CHAT_ID, 
                        f"__Task dihentikan untuk chat {chat_id}__"
                    )
                    break
                await TELAYSPAM_TASKS[chat_id]["pause_event"].wait()

                # Gunakan config real-time untuk old_purge
                old_purge_val = TELAYSPAM_TASKS[chat_id]["config"]["old_purge"]
                del_suk, del_ggl = 0, 0
                if old_purge_val > 0:
                    try:
                        messages = []
                        async for message in client.get_chat_history(target_chat.id, limit=old_purge_val * 2):
                            messages.append(message)
                        
                        if messages:
                            my_messages = [msg for msg in messages if msg.from_user and msg.from_user.id == client.me.id][:old_purge_val]
                            message_ids = [msg.id for msg in my_messages]
                            
                            if message_ids:
                                await client.delete_messages(target_chat.id, message_ids)
                                del_suk = len(message_ids)
                                await asyncio.sleep(3)
                            else:
                                del_suk = 0
                                
                            del_ggl = old_purge_val - del_suk
                            total_del_suk += del_suk
                            total_del_ggl += del_ggl
                            
                            await USER_CLIENT.send_message(
                                Altruix.config.LOG_CHAT_ID,
                                f"[HAPUS]: Berhasil hapus <code>{del_suk}</code> pesan lama, gagal <code>{del_ggl}</code> pesan.",
                                reply_to_message_id=x_msg.id,
                                parse_mode="html"
                            )
                    except Exception as del_err:
                        Altruix.log(f"Error saat menghapus pesan: {del_err}", level=40)
                        await USER_CLIENT.send_message(
                            Altruix.config.LOG_CHAT_ID, 
                            f"Error hapus pesan: {del_err}", 
                            reply_to_message_id=x_msg.id
                        )

                msg = random.choice(msg_list)
                random_delay = random.choice(delays_possible)

                while True:
                    try:
                        sent_msg = await client.send_message(target_chat.id, msg)
                        sent_count += 1

                        react_status = "tidak ada"
                        if emot_react and emot_react.lower() != "none":
                            try:
                                await asyncio.sleep(3)
                                await client.send_reaction(target_chat.id, sent_msg.id, emot_react)
                                react_status = f"{emot_react} berhasil"
                            except Exception as react_err:
                                Altruix.log(f"Error saat menambahkan reaksi: {react_err}", level=40)
                                react_status = f"{emot_react} gagal"

                        remaining = count - sent_count
                        percentage = (sent_count / count) * 100 if count > 0 else 0
                        char_count = len(msg)
                        
                        clean_chat_id = str(target_chat.id).replace("-100", "")
                        
                        await USER_CLIENT.send_message(
                            Altruix.config.LOG_CHAT_ID,
                            f"<b>Pesan terkirim</b>\n"
                            f"Mode     : <code>{'Batch' if is_batch else 'Acak'}</code>\n"
                            f"Delay    : <code>{random_delay:.2f}</code> detik\n"
                            f"Sisa      : <code>{remaining}</code> pesan\n"
                            f"Progress : <code>{percentage:.2f}%</code>\n"
                            f"Length   : <code>{char_count}</code> karakter\n"
                            f"React   : <code>{react_status}</code> <b><a href=\"https://t.me/c/{clean_chat_id}/{sent_msg.id}\">here</a></b>\n"
                            f"Pesan    : <code>{msg}</code>",
                            reply_to_message_id=x_msg.id,
                            parse_mode="html"
                        )

                        await asyncio.sleep(random_delay)
                        break

                    except errors.exceptions.flood_420.SlowmodeWait as swe:
                        Altruix.log(f"SlowModeWaitError: Waiting for {swe.value} seconds", level=30)
                        await USER_CLIENT.send_message(
                            Altruix.config.LOG_CHAT_ID, 
                            f"** [ #ERROR ]** __SlowModeWaitError: Waiting for {swe.value} seconds__", 
                            reply_to_message_id=x_msg.id
                        )
                        await asyncio.sleep(swe.value)

                    except FloodWait as fwe:
                        Altruix.log(f"FloodWaitError: Waiting for {fwe.value} seconds", level=30)
                        await USER_CLIENT.send_message(
                            Altruix.config.LOG_CHAT_ID, 
                            f"** [ #ERROR ]** __FloodWaitError: Waiting for {fwe.value} seconds__", 
                            reply_to_message_id=x_msg.id
                        )
                        await asyncio.sleep(fwe.value)

                    except ChatWriteForbidden as cwe:
                        Altruix.log(f"Bot muted in chat {chat_id}: Pausing task automatically.", level=30)
                        await USER_CLIENT.send_message(
                            Altruix.config.LOG_CHAT_ID, 
                            f"** [ #ERROR ]** __UserBot muted in chat {target_chat.title}: Task paused automatically.__", 
                            reply_to_message_id=x_msg.id
                        )
                        TELAYSPAM_TASKS[chat_id]["pause_event"].clear()
                        break

                    except Exception as send_err:
                        Altruix.log(f"Error saat mengirim pesan: {send_err}", level=40)
                        await USER_CLIENT.send_message(
                            Altruix.config.LOG_CHAT_ID, 
                            f"** [ #ERROR ]** __Error saat mengirim pesan: {send_err}__", 
                            reply_to_message_id=x_msg.id
                        )
                        await asyncio.sleep(5)

        if TELAYSPAM_TASKS.get(chat_id, {}).get("running", False):
            await USER_CLIENT.send_message(
                Altruix.config.LOG_CHAT_ID,
                f"<b>[SELESAI]</b>: \n"
                f"Spam di <b>{target_chat.title}</b> telah selesai!\n"
                f"Terkirim <code>{sent_count}</code> pesan ({'batch' if is_batch else 'acak'}), delay acak [{start_delay}-{stop_delay}] dengan interval {step} detik,\n"
                f"Total sukses hapus <code>{total_del_suk}</code> pesan, total gagal hapus <code>{total_del_ggl}</code> pesan.",
                reply_to_message_id=x_msg.id,
                parse_mode="html"
            )

    except Exception as u:
        Altruix.log(f"Error in spam_loop: {u}", level=40)
        await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, f"__Error in spam_loop: {u}__")
    finally:
        if chat_id in TELAYSPAM_TASKS:
            config = TELAYSPAM_TASKS[chat_id].pop('config', None)
            if config:
                COMPLETED_TASKS[chat_id] = config
        TELAYSPAM_TASKS.pop(chat_id, None)

async def start_relayspam(client: Client, destination: str, start_delay: float, stop_delay: float, 
                          step: float, count: int, old_purge: int, emot_react: str, 
                          msg_list: list, is_batch: bool) -> bool:
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
            await USER_CLIENT.send_message(
                Altruix.config.LOG_CHAT_ID, 
                f"**Error:** Task relayspam sudah berjalan di {target_chat.title}."
            )
            return False

        TELAYSPAM_TASKS[chat_id] = {
            "running": True,
            "pause_event": asyncio.Event(),
            "config": {
                "destination": destination,
                "start_delay": start_delay,
                "stop_delay": stop_delay,
                "step": step,
                "count": count,
                "old_purge": old_purge,
                "emot_react": emot_react,
                "msg_list": msg_list[:] if isinstance(msg_list, list) else msg_list,
                "is_batch": is_batch
            }
        }
        TELAYSPAM_TASKS[chat_id]["pause_event"].set()

        clean_id = str(target_chat.id).replace("-100", "")

        notif_msg = (
            f"<b>Notifikasi Task</b>\n\n"
            f"Tugas spam akan segera dimulai.\n\n"
            f"✦ · · ──────✪────── · · ✦\n"
            f"<blockquote>\n"
            f"Tujuan     : <b><a href=\"https://t.me/c/{clean_id}/99999\">{target_chat.title}</a></b>\n"
            f"Chat_ID    : <code>-100{clean_id}</code>\n"
            f"Perintah   : <code>{Altruix.handler}relayspam</code>\n"
            f"Mode       : <code>{'Batch' if is_batch else 'Acak'}</code>\n"
            f"Delay      : <code>{start_delay}</code> - <code>{stop_delay}</code>/step <code>{step}</code> detik\n"
            f"Jumlah     : <code>{count}</code> pesan\n"
            f"Hapus      : <code>{old_purge}</code> pesan\n"
            f"React      : <code>{emot_react if emot_react else 'tidak ada'}</code>\n"
            f"Pesan      : <code>{msg_list}</code>\n"
            f"</blockquote>"
        )

        # Tombol inline untuk kontrol task
        tombol_baris = [
            [InlineKeyboardButton(f"-100{chat_id}", url=f"https://t.me/c/{clean_id}/99999")],
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
            [InlineKeyboardButton(f"{'Purge: ON' if old_purge > 0 else 'Purge: OFF'}", callback_data=f"toggle_purge_{chat_id}")]
        ]

        x_msg = await USER_CLIENT.send_message(
            Altruix.config.LOG_CHAT_ID,
            f"{notif_msg}",
            reply_markup=InlineKeyboardMarkup(tombol_baris),
            parse_mode="html"
        )

        # Simpan notif message untuk update tombol
        TELAYSPAM_TASKS[chat_id]["notif_msg"] = x_msg

        try:
            await x_msg.pin()
        except Exception as erpin:
            Altruix.log(f"#ERROR_PIN : {erpin}", level=30)

        delays_possible = []
        current = start_delay
        while current <= stop_delay:
            delays_possible.append(current)
            current += step

        if not delays_possible:
            raise ValueError("Tidak ada nilai delay yang mungkin dalam rentang yang diberikan.")

        task = asyncio.create_task(spam_loop(client, target_chat, chat_id, msg_list, delays_possible, 
                                            count, start_delay, stop_delay, step, x_msg, emot_react, is_batch))
        TELAYSPAM_TASKS[chat_id]["task"] = task

        return True

    except Exception as u:
        Altruix.log(f"Error in start_relayspam: {u}", level=40)
        await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, f"__Error in start_relayspam: {u}__")
        TELAYSPAM_TASKS.pop(chat_id, None)
        return False

@Altruix.register_on_cmd(
    ["relayspam"],
    cmd_help={
        "help": "Memulai spam relay dengan delay acak",
        "example": "relayspam -1001234567890 1.0 5.0 0.5 10 2 👍 [\"Pesan 1\", \"Pesan 2\"]",
        "user_args": [],
    },
)
async def telayspammer_cmd(c: Client, m: Message):
    """
    Handler command: relayspam
    """
    try:
        text = m.text.strip()
        args_str = text[len(f"{Altruix.handler}relayspam "):]
        msg_list_match = re.search(r'\[.*\]$', args_str, re.DOTALL)
        if not msg_list_match:
            await m.handle_message("INVALID_MSG_LIST_FORMAT")
            return

        msg_list_str = msg_list_match.group(0)
        args_str_without_msg = args_str[:msg_list_match.start()].strip()
        args = shlex.split(args_str_without_msg)

        if len(args) not in [6, 7]:
            await m.handle_message(
                "INVALID_ARG_COUNT",
                string_args=(f"{Altruix.handler}relayspam <destination> <start_delay> <stop_delay> <step> <count> <purge> <emot_react/optional> [\"msg1\", \"msg2\"]\n"
                           f"Atau: {Altruix.handler}relayspam <destination> <start_delay> <stop_delay> <step> <count> <purge> <emot_react/optional> [(\"msg1\", 100), (\"msg2\", 100)]")
            )
            return

        destination = args[0]
        start_delay = float(args[1])
        stop_delay = float(args[2])
        step = float(args[3])
        count = int(args[4])
        old_purge = int(args[5])
        emot_react = args[6] if len(args) == 7 and args[6].lower() != "none" else None

        msg_list = ast.literal_eval(msg_list_str)
        if not isinstance(msg_list, list) or not msg_list:
            await m.handle_message("INVALID_MSG_LIST")
            return

        is_batch = all(isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str) and isinstance(item[1], int) for item in msg_list)
        if is_batch:
            total_batch_count = sum(b_count for _, b_count in msg_list)
            if total_batch_count != count:
                await m.handle_message("BATCH_COUNT_MISMATCH")
                return

        if start_delay <= 0 or stop_delay <= 0 or step <= 0:
            await m.handle_message("INVALID_DELAY_VALUES")
            return
        if start_delay > stop_delay:
            await m.handle_message("START_DELAY_GREATER")
            return

    except (ValueError, IndexError, SyntaxError) as err:
        await m.handle_message(
            "PARSING_ERROR",
            string_args=(str(err), f"{Altruix.handler}relayspam <destination> <start_delay> <stop_delay> <step> <count> <purge> <emot_react> [\"msg1\", \"msg2\"]")
        )
        return

    await m.handle_message("PROCESSING_TASK")
    await asyncio.sleep(2)

    success = await start_relayspam(c, destination, start_delay, stop_delay, step, count, old_purge, emot_react, msg_list, is_batch)
    if success:
        await m.handle_message("TASK_STARTED_SUCCESS", string_args=(destination,))
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
async def stop_telayspam_cmd(c: Client, m: Message):
    """Stop task relayspam"""
    try:
        destination = m.text.split(" ", 1)[1]
        if destination.isdigit() and len(destination) >= 10:
            destination = "-100" + destination
        target_chat = await c.get_chat(int(destination) if destination.replace("-", "").isdigit() else destination)
        chat_id = str(target_chat.id)
        if chat_id not in TELAYSPAM_TASKS:
            await m.handle_message("NO_TASK_RUNNING", string_args=(target_chat.title,))
            return
        TELAYSPAM_TASKS[chat_id]["running"] = False
        TELAYSPAM_TASKS[chat_id]["pause_event"].set()
        if "task" in TELAYSPAM_TASKS[chat_id]:
            TELAYSPAM_TASKS[chat_id]["task"].cancel()
        await m.handle_message("TASK_STOPPED", string_args=(target_chat.title,))
    except Exception as err:
        await m.handle_message("STOP_TASK_ERROR", string_args=(str(err),))

@Altruix.register_on_cmd(
    ["prelayspam"],
    cmd_help={
        "help": "Mempause task relayspam",
        "example": "prelayspam -1001234567890",
        "user_args": [],
    },
)
async def pause_telayspam_cmd(c: Client, m: Message):
    """Pause task relayspam"""
    try:
        destination = m.text.split(" ", 1)[1]
        if destination.isdigit() and len(destination) >= 10:
            destination = "-100" + destination
        target_chat = await c.get_chat(int(destination) if destination.replace("-", "").isdigit() else destination)
        chat_id = str(target_chat.id)
        if chat_id not in TELAYSPAM_TASKS:
            await m.handle_message("NO_TASK_RUNNING", string_args=(target_chat.title,))
            return
        TELAYSPAM_TASKS[chat_id]["pause_event"].clear()
        await m.handle_message("TASK_PAUSED", string_args=(target_chat.title,))
    except Exception as err:
        await m.handle_message("PAUSE_TASK_ERROR", string_args=(str(err),))

@Altruix.register_on_cmd(
    ["rrelayspam"],
    cmd_help={
        "help": "Melanjutkan task relayspam yang dipause",
        "example": "rrelayspam -1001234567890",
        "user_args": [],
    },
)
async def resume_telayspam_cmd(c: Client, m: Message):
    """Resume task relayspam"""
    try:
        destination = m.text.split(" ", 1)[1]
        if destination.isdigit() and len(destination) >= 10:
            destination = "-100" + destination
        target_chat = await c.get_chat(int(destination) if destination.replace("-", "").isdigit() else destination)
        chat_id = str(target_chat.id)
        if chat_id not in TELAYSPAM_TASKS:
            await m.handle_message("NO_TASK_RUNNING", string_args=(target_chat.title,))
            return
        TELAYSPAM_TASKS[chat_id]["pause_event"].set()
        await m.handle_message("TASK_RESUMED", string_args=(target_chat.title,))
    except Exception as err:
        await m.handle_message("RESUME_TASK_ERROR", string_args=(str(err),))

@Altruix.register_on_cmd(
    ["relayspamcek"],
    cmd_help={
        "help": "Memeriksa status task relayspam",
        "example": "relayspamcek -1001234567890",
        "user_args": [],
    },
)
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
            chat_title = target_chat.title
        else:
            await m.handle_message("MISSING_DESTINATION_ARG")
            return
    except Exception as err:
        await m.handle_message("CHAT_RESOLUTION_ERROR", string_args=(str(err),))
        return

    if chat_id in TELAYSPAM_TASKS:
        status = TELAYSPAM_TASKS[chat_id]
        if status["running"]:
            if status["pause_event"].is_set():
                await m.handle_message("TASK_STATUS_RUNNING", string_args=(chat_title,))
            else:
                await m.handle_message("TASK_STATUS_PAUSED", string_args=(chat_title,))
        else:
            await m.handle_message("TASK_STATUS_STOPPED", string_args=(chat_title,))
    else:
        await m.handle_message("NO_TASK_FOR_CHAT", string_args=(chat_title,))

@Altruix.register_on_cmd(
    ["relayspamcekall"],
    cmd_help={
        "help": "Memeriksa status semua task relayspam",
        "example": "relayspamcekall",
        "user_args": [],
    },
)
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
                    status_text = f"🔵 running di {chat_title} (ID: <code>{chat_id}</code>)"
                else:
                    status_text = f"🟡 paused di {chat_title} (ID: <code>{chat_id}</code>)"
            else:
                status_text = f"🔴 stopped di {chat_title} (ID: <code>{chat_id}</code>)"
            status_list.append(status_text)
        except Exception as err:
            Altruix.log(f"Error resolusi chat {chat_id}: {err}", level=40)
            status_list.append(f"❓ Unknown chat (ID: <code>{chat_id}</code>) - Status tidak dapat diresolusi.")

    output = "<b>Status Semua Task Relayspam:</b>\n\n" + "\n".join(status_list)
    await m.edit(output, parse_mode="html")

# --- Handler untuk callback queries (tombol inline) ---
@Altruix.on_callback(filters.regex(r"toggle_purge_(-?\d+)"))
async def toggle_purge_handler(c: Client, cb):
    """Handler untuk toggle purge old messages"""
    data = cb.data
    chat_id = data.split("_")[-1]

    if chat_id not in TELAYSPAM_TASKS:
        await cb.answer("Task tidak aktif.", show_alert=True)
        return

    config = TELAYSPAM_TASKS[chat_id]["config"]
    current_purge = config["old_purge"]
    new_purge = 0 if current_purge > 0 else 5  # Default ke 5 saat di-ON
    config["old_purge"] = new_purge

    status = "AKTIF" if new_purge > 0 else "NONAKTIF"
    await cb.answer(f"Purge old message: {status}", show_alert=True)
    
    await USER_CLIENT.send_message(
        Altruix.config.LOG_CHAT_ID,
        f"<b>PURGE TOGGLED</b>\n"
        f"Chat: <code>{config['destination']}</code>\n"
        f"Status: <b>{status}</b>\n"
        f"Jumlah hapus: <code>{new_purge}</code> pesan lama",
        parse_mode="html"
    )

    # Update tombol di notif utama
    try:
        notif_msg = TELAYSPAM_TASKS[chat_id].get("notif_msg")
        if notif_msg:
            await update_purge_button(notif_msg, chat_id, new_purge > 0)
    except Exception as e:
        Altruix.log(f"Gagal update tombol: {e}", level=40)

@Altruix.on_callback(filters.regex(r"(stop|pause|resume|cek|recurring|delete_latest|delete_oldest|edit_last|edit_msglist|cancel_edit|cancel_editlast)_(-?\d+)"))
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
                await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, f"⚫️ Task tidak aktif di chat ini.")
                return

        if action == "stop":
            TELAYSPAM_TASKS[chat_id]["running"] = False
            TELAYSPAM_TASKS[chat_id]["pause_event"].set()
            if "task" in TELAYSPAM_TASKS[chat_id]:
                TELAYSPAM_TASKS[chat_id]["task"].cancel()
            await cb.answer(f"🔴 Task distop di {chat_title}.", show_alert=True)
            await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, f"🔴 Task distop di {chat_title}.")
        
        elif action == "pause":
            TELAYSPAM_TASKS[chat_id]["pause_event"].clear()
            await cb.answer(f"🟡 Task dipause di {chat_title}.", show_alert=True)
            await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, f"🟡 Task dipause di {chat_title}.")
        
        elif action == "resume":
            TELAYSPAM_TASKS[chat_id]["pause_event"].set()
            await cb.answer(f"🟢 Task diresume di {chat_title}.", show_alert=True)
            await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, f"🟢 Task diresume di {chat_title}.")
        
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
            await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, f"{status_text}.")
        
        elif action == "recurring":
            if chat_id in TELAYSPAM_TASKS:
                await cb.answer("⚠️ Task masih berjalan, hentikan dulu sebelum recurring.", show_alert=True)
                await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, f"⚠️ Task masih berjalan di {chat_title}, hentikan dulu.")
                return
            
            config = COMPLETED_TASKS.get(chat_id)
            if not config:
                await cb.answer("⚫️ Tidak ada task selesai untuk diulang di chat ini.", show_alert=True)
                await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, f"⚫️ Tidak ada task selesai untuk diulang di {chat_title}.")
                return
            
            success = await start_relayspam(
                USER_CLIENT,
                config["destination"],
                config["start_delay"],
                config["stop_delay"],
                config["step"],
                config["count"],
                config["old_purge"],
                config["emot_react"],
                config["msg_list"],
                config["is_batch"]
            )
            
            if success:
                await cb.answer(f"🔁 Task recurring dimulai ulang di {chat_title}.", show_alert=True)
                await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, f"🔁 Task recurring dimulai ulang di {chat_title}.")
            else:
                await cb.answer(f"❌ Gagal memulai recurring di {chat_title}.", show_alert=True)
                await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, f"❌ Gagal memulai recurring di {chat_title}.")
        
        elif action == "delete_latest":
            try:
                messages = []
                async for message in c.get_chat_history(int(chat_id), limit=30):
                    messages.append(message)
                
                if messages:
                    message_ids = [msg.id for msg in messages if msg.from_user and msg.from_user.id == c.me.id]
                    try:
                        await c.delete_messages(int(chat_id), message_ids)
                        del_suk = len(message_ids)
                        await asyncio.sleep(3)
                        await cb.answer(f"🗑️ Berhasil hapus {del_suk} pesan terbaru di {chat_title}.", show_alert=True)
                        await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, f"🗑️ Berhasil hapus {del_suk} pesan terbaru di {chat_title}.")
                    except Exception as del_err:
                        Altruix.log(f"Error saat menghapus pesan terbaru: {del_err}", level=40)
                        await cb.answer(f"❌ Gagal hapus pesan terbaru: {del_err}", show_alert=True)
                        await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, f"❌ Gagal hapus pesan terbaru di {chat_title}: {del_err}")
                else:
                    await cb.answer("⚫️ Tidak ada pesan untuk dihapus.", show_alert=True)
                    await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, f"⚫️ Tidak ada pesan untuk dihapus di {chat_title}.")
            except Exception as err:
                await cb.answer(f"Error: {err}", show_alert=True)
                await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, f"⚠️ **Error :** {err}")
        
        elif action == "delete_oldest":
            try:
                messages = []
                count = 0
                async for message in c.get_chat_history(int(chat_id), limit=30):
                    messages.append(message)
                    count += 1
                    if count >= 30:
                        break
                
                if messages:
                    message_ids = [msg.id for msg in messages if msg.from_user and msg.from_user.id == c.me.id]
                    try:
                        await c.delete_messages(int(chat_id), message_ids)
                        del_suk = len(message_ids)
                        await asyncio.sleep(3)
                        await cb.answer(f"🗑️ Berhasil hapus {del_suk} pesan terlama di {chat_title}.", show_alert=True)
                        await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, f"🗑️ Berhasil hapus {del_suk} pesan terlama di {chat_title}.")
                    except Exception as del_err:
                        Altruix.log(f"Error saat menghapus pesan terlama: {del_err}", level=40)
                        await cb.answer(f"❌ Gagal hapus pesan terlama: {del_err}", show_alert=True)
                        await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, f"❌ Gagal hapus pesan terlama di {chat_title}: {del_err}")
                else:
                    await cb.answer("⚫️ Tidak ada pesan untuk dihapus.", show_alert=True)
                    await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, f"⚫️ Tidak ada pesan untuk dihapus di {chat_title}.")
            except Exception as err:
                await cb.answer(f"Error: {err}", show_alert=True)
                await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, f"⚠️ **Error :** {err}")
        
        elif action == "edit_last":
            try:
                messages = []
                async for message in c.get_chat_history(int(chat_id), limit=1):
                    messages.append(message)
                    break
                
                if messages and messages[0].from_user and messages[0].from_user.id == c.me.id:
                    last_msg_id = messages[0].id
                    old_text = messages[0].text or messages[0].caption or ""
                    notif_msg = (
                        f"✏️ <b>Edit Last Message untuk {chat_title}</b>\n\n"
                        f"Masukkan teks baru untuk mengedit pesan terakhir.\n\n"
                        f"Balas pesan ini dengan teks baru.\n"
                        f"Contoh balasan: <code>Edited message here</code>\n"
                        f"Klik 'Cancel' untuk membatalkan proses edit."
                    )
                    cancel_button = [[InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_editlast_{chat_id}")]]
                    edit_notif_msg = await USER_CLIENT.send_message(
                        Altruix.config.LOG_CHAT_ID,
                        notif_msg,
                        reply_markup=InlineKeyboardMarkup(cancel_button),
                        parse_mode="html"
                    )
                    EDIT_LASTMSG_WAITING[chat_id] = {
                        "target_chat_id": int(chat_id),
                        "last_msg_id": last_msg_id,
                        "old_text": old_text,
                        "notif_msg_id": edit_notif_msg.id
                    }
                    await cb.answer(f"📝 Silakan masukkan teks baru untuk edit last msg di {chat_title}.", show_alert=True)
                else:
                    await cb.answer("⚫️ Tidak ada pesan terakhir dari userbot untuk diedit.", show_alert=True)
                    await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, f"⚫️ Tidak ada pesan terakhir untuk diedit di {chat_title}.")
            except Exception as edit_err:
                Altruix.log(f"Error saat memulai edit last msg: {edit_err}", level=40)
                await cb.answer(f"❌ Gagal memulai edit: {edit_err}", show_alert=True)
                await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, f"❌ Gagal memulai edit last msg di {chat_title}: {edit_err}")
        
        elif action == "edit_msglist":
            config = None
            was_running = False
            if chat_id in TELAYSPAM_TASKS:
                was_running = True
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
                await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, f"⚫️ Tidak ada task untuk mengedit msg_list di {chat_title}.")
                return

            if config:
                old_msg_list = config["msg_list"]
                is_batch = config["is_batch"]
                notif_msg = (
                    f"✏️ <b>Edit Message List untuk {chat_title}</b>\n\n"
                    f"Masukkan pesan baru dengan format:\n"
                    f"- Untuk mode acak: <code>[\"hello world\", \"hello dunia\", \"good morning\"]</code>\n"
                    f"- Untuk mode batch: <code>[(\"✅ hello world\", 50), (\"❇️ hello dunia\", 50)]</code>\n\n"
                    f"Balas pesan ini dengan list pesan baru. Pastikan jumlah pesan atau total batch sesuai dengan count ({config['count']}).\n"
                    f"Contoh balasan: <code>[\"hello world\", \"hello dunia\"]</code>\n"
                    f"Klik 'Cancel' untuk membatalkan proses edit."
                )
                cancel_button = [[InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_edit_{chat_id}")]]
                edit_notif_msg = await USER_CLIENT.send_message(
                    Altruix.config.LOG_CHAT_ID,
                    notif_msg,
                    reply_markup=InlineKeyboardMarkup(cancel_button),
                    parse_mode="html"
                )
                EDIT_MSGLIST_WAITING[chat_id] = {
                    "config": config,
                    "was_running": was_running,
                    "notif_msg_id": edit_notif_msg.id
                }
                await cb.answer(f"📝 Silakan masukkan list pesan baru di {chat_title}.", show_alert=True)
            else:
                await cb.answer("⚫️ Tidak ada config untuk mengedit msg_list.", show_alert=True)
                await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, f"⚫️ Tidak ada config untuk mengedit msg_list di {chat_title}.")
        
        elif action == "cancel_edit":
            if chat_id in EDIT_MSGLIST_WAITING:
                config = EDIT_MSGLIST_WAITING[chat_id]["config"]
                was_running = EDIT_MSGLIST_WAITING[chat_id]["was_running"]
                notif_msg_id = EDIT_MSGLIST_WAITING[chat_id]["notif_msg_id"]
                EDIT_MSGLIST_WAITING.pop(chat_id, None)
                await cb.answer(f"❌ Proses edit msg_list dibatalkan di {chat_title}.", show_alert=True)
                await USER_CLIENT.send_message(
                    Altruix.config.LOG_CHAT_ID,
                    f"❌ Proses edit msg_list dibatalkan di {chat_title}.",
                    reply_to_message_id=notif_msg_id,
                    parse_mode="html"
                )
                if was_running:
                    success = await start_relayspam(
                        USER_CLIENT,
                        config["destination"],
                        config["start_delay"],
                        config["stop_delay"],
                        config["step"],
                        config["count"],
                        config["old_purge"],
                        config["emot_react"],
                        config["msg_list"],
                        config["is_batch"]
                    )
                    if success:
                        await USER_CLIENT.send_message(
                            Altruix.config.LOG_CHAT_ID,
                            f"✅ Task dikembalikan ke config default dan dimulai ulang di {chat_title}.",
                            parse_mode="html"
                        )
                    else:
                        await USER_CLIENT.send_message(
                            Altruix.config.LOG_CHAT_ID,
                            f"❌ Gagal memulai ulang task di {chat_title}.",
                            parse_mode="html"
                        )
            else:
                await cb.answer("⚫️ Tidak ada proses edit msg_list untuk dibatalkan.", show_alert=True)
                await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, f"⚫️ Tidak ada proses edit msg_list untuk dibatalkan di {chat_title}.")
        
        elif action == "cancel_editlast":
            if chat_id in EDIT_LASTMSG_WAITING:
                notif_msg_id = EDIT_LASTMSG_WAITING[chat_id]["notif_msg_id"]
                EDIT_LASTMSG_WAITING.pop(chat_id, None)
                await cb.answer(f"❌ Proses edit last msg dibatalkan di {chat_title}.", show_alert=True)
                await USER_CLIENT.send_message(
                    Altruix.config.LOG_CHAT_ID,
                    f"❌ Proses edit last msg dibatalkan di {chat_title}.",
                    reply_to_message_id=notif_msg_id,
                    parse_mode="html"
                )
            else:
                await cb.answer("⚫️ Tidak ada proses edit last msg untuk dibatalkan.", show_alert=True)
                await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, f"⚫️ Tidak ada proses edit last msg untuk dibatalkan di {chat_title}.")
    
    except FloodWait as fwe:
        Altruix.log(f"FloodWaitError saat menangani aksi {action} untuk chat {chat_id}: Waiting for {fwe.value} seconds", level=30)
        await cb.answer(f"⚠️ Terlalu banyak permintaan. Tunggu {fwe.value} detik.", show_alert=True)
        await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, f"⚠️ **FloodWaitError:** Tunggu {fwe.value} detik untuk aksi {action} di {chat_title}.")
    except ChatWriteForbidden as cwe:
        Altruix.log(f"ChatWriteForbiddenError saat menangani aksi {action} untuk chat {chat_id}: Bot tidak memiliki izin", level=30)
        await cb.answer(f"❌ Bot tidak memiliki izin untuk melakukan aksi ini di {chat_title}.", show_alert=True)
        await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, f"❌ **ChatWriteForbiddenError:** Bot tidak memiliki izin untuk aksi {action} di {chat_title}.")
    except Exception as err:
        Altruix.log(f"Error saat menangani aksi {action} untuk chat {chat_id}: {err}", level=40)
        await cb.answer(f"Error: {err}", show_alert=True)
        await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, f"⚠️ **Error :** {err}")

@Altruix.on_callback(filters.regex(r"(cekall|stopall|recurringall|pauseall|resumeall)"))
async def handle_global_controls(c: Client, cb):
    """Handler untuk kontrol global semua task"""
    data = cb.data
    
    if data == "cekall":
        if not TELAYSPAM_TASKS:
            await cb.answer("⚫️ Tidak ada task relayspam yang aktif.", show_alert=True)
            await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, f"⚫️ Tidak ada task relayspam yang aktif.")
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
                await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, f"Error: {err}")

        output = "**Status Semua Task:**\n\n" + "\n".join(status_list)
        await cb.answer(output, show_alert=True)
        await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, f"{output}")
    
    elif data == "stopall":
        if not TELAYSPAM_TASKS:
            await cb.answer("⚫️ Tidak ada task aktif untuk dihentikan.", show_alert=True)
            await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, "⚫️ Tidak ada task aktif untuk dihentikan.")
            return
        
        stopped_count = 0
        for chat_id in list(TELAYSPAM_TASKS.keys()):
            TELAYSPAM_TASKS[chat_id]["running"] = False
            TELAYSPAM_TASKS[chat_id]["pause_event"].set()
            if "task" in TELAYSPAM_TASKS[chat_id]:
                TELAYSPAM_TASKS[chat_id]["task"].cancel()
            stopped_count += 1
        
        await cb.answer(f"🔴 Semua {stopped_count} task dihentikan.", show_alert=True)
        await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, f"🔴 Semua {stopped_count} task dihentikan.")
    
    elif data == "recurringall":
        if not COMPLETED_TASKS:
            await cb.answer("⚫️ Tidak ada task selesai untuk diulang.", show_alert=True)
            await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, "⚫️ Tidak ada task selesai untuk diulang.")
            return
        
        restarted_count = 0
        for chat_id, config in list(COMPLETED_TASKS.items()):
            if chat_id in TELAYSPAM_TASKS:
                continue
            
            success = await start_relayspam(
                USER_CLIENT,
                config["destination"],
                config["start_delay"],
                config["stop_delay"],
                config["step"],
                config["count"],
                config["old_purge"],
                config["emot_react"],
                config["msg_list"],
                config["is_batch"]
            )
            if success:
                restarted_count += 1
        
        await cb.answer(f"🔁 {restarted_count} task recurring dimulai ulang.", show_alert=True)
        await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, f"🔁 {restarted_count} task recurring dimulai ulang.")
    
    elif data == "pauseall":
        if not TELAYSPAM_TASKS:
            await cb.answer("⚫️ Tidak ada task aktif untuk dipause.", show_alert=True)
            await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, "⚫️ Tidak ada task aktif untuk dipause.")
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
            await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, "⚫️ Tidak ada task aktif yang sedang running untuk dipause.")
        else:
            output = f"🟡 Semua {paused_count} task dipause:\n\n" + "\n".join(paused_chats)
            await cb.answer(f"🟡 Semua {paused_count} task dipause.", show_alert=True)
            await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, output, parse_mode="html")
    
    elif data == "resumeall":
        if not TELAYSPAM_TASKS:
            await cb.answer("⚫️ Tidak ada task untuk diresume.", show_alert=True)
            await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, "⚫️ Tidak ada task untuk diresume.")
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
            await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, "⚫️ Tidak ada task yang dipause untuk diresume.")
        else:
            output = f"🟢 Semua {resumed_count} task diresume:\n\n" + "\n".join(resumed_chats)
            await cb.answer(f"🟢 Semua {resumed_count} task diresume.", show_alert=True)
            await USER_CLIENT.send_message(Altruix.config.LOG_CHAT_ID, output, parse_mode="html")

# --- Handler untuk input pesan (edit msg_list dan edit last msg) ---
@Altruix.on_message(filters.chat(Altruix.config.LOG_CHAT_ID) & filters.incoming & filters.reply)
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
                success = await start_relayspam(
                    USER_CLIENT,
                    config["destination"],
                    config["start_delay"],
                    config["stop_delay"],
                    config["step"],
                    config["count"],
                    config["old_purge"],
                    config["emot_react"],
                    config["msg_list"],
                    config["is_batch"]
                )
                if success:
                    await m.reply(
                        f"✏️ Berhasil edit msg_list di {chat_title}:\n"
                        f"Sebelum: <code>{old_msg_list}</code>\n"
                        f"Sesudah: <code>{new_msg_list}</code>\n"
                        f"Task {'dihentikan dan ' if was_running else ''}dimulai ulang dengan msg_list baru.",
                        parse_mode="html"
                    )
                    EDIT_MSGLIST_WAITING.pop(chat_id, None)
                else:
                    await m.reply(f"❌ Gagal memulai task dengan msg_list baru di {chat_title}.", parse_mode="html")
            
            except (ValueError, SyntaxError) as err:
                await m.reply(
                    f"**Error Parsing Input:** {err}\n"
                    f"Gunakan format yang benar:\n"
                    f"- Mode acak: <code>[\"hello world\", \"hello dunia\", \"good morning\"]</code>\n"
                    f"- Mode batch: <code>[(\"✅ hello world\", 50), (\"❇️ hello dunia\", 50)]</code>",
                    parse_mode="html"
                )
            except Exception as err:
                Altruix.log(f"Error saat memproses input msg_list: {err}", level=40)
                await m.reply(f"⚠️ **Error:** {err}", parse_mode="html")
        
        # Cek untuk edit last msg
        elif reply_msg_id in [waiting["notif_msg_id"] for waiting in EDIT_LASTMSG_WAITING.values()]:
            chat_id = next(cid for cid, waiting in EDIT_LASTMSG_WAITING.items() if waiting["notif_msg_id"] == reply_msg_id)
            target_chat_id = EDIT_LASTMSG_WAITING[chat_id]["target_chat_id"]
            last_msg_id = EDIT_LASTMSG_WAITING[chat_id]["last_msg_id"]
            old_text = EDIT_LASTMSG_WAITING[chat_id]["old_text"]
            
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

                await c.edit_message_text(target_chat_id, last_msg_id, new_text)
                await asyncio.sleep(1)
                await m.reply(
                    f"✏️ Berhasil edit last msg di {chat_title}:\n"
                    f"Sebelum: <code>{old_text}</code>\n"
                    f"Sesudah: <code>{new_text}</code>",
                    parse_mode="html"
                )
                EDIT_LASTMSG_WAITING.pop(chat_id, None)
            
            except (ValueError, SyntaxError) as err:
                await m.reply(
                    f"**Error Parsing Input:** {err}\n"
                    f"Masukkan teks biasa sebagai balasan.",
                    parse_mode="html"
                )
            except Exception as err:
                Altruix.log(f"Error saat memproses input last msg: {err}", level=40)
                await m.reply(f"⚠️ **Error:** {err}", parse_mode="html")

# Log sukses loading
Altruix.log(f"[DEBUG] Loaded → {__plugin_name__} v{PLUGIN_VERSION}", level=20)
logger.info(f"[DEBUG] Loaded → {__plugin_name__} v{PLUGIN_VERSION}")
