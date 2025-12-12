# xspamxr.py
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
from pyrogram.errors import FloodWait, ChatWriteForbidden, SlowmodeWait, ChannelInvalid, ChannelPrivate, PeerIdInvalid, UsernameInvalid
from Main.core.types.message import Message
from Main.utils.essentials import Essentials
from Main.core.decorators import inline_check
from pyrogram.errors import RPCError
from Main.core.decorators import log_errors
from Main.utils.compatibility import smart_send

# ─── LOGGER KHUSUS PLUGIN ───────────────────────────────────────────────
import logging

plugin_name = f"plugins/userbot/{os.path.basename(__file__)}"
__plugin_name__ = plugin_name if plugin_name else "xspamxr"
PLUGIN_VERSION = "0.3.0.22"  # 🔥 FIXED: CHANNEL_INVALID + unpacking error + button freeze
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

**CHANGELOG {PLUGIN_VERSION}:**
- 🔥 FIXED: Error 'too many values to unpack (expected 2)' di confirm_start_handler
- 🔥 FIXED: Error 'CHANNEL_INVALID' saat resolve chat → gunakan get_chat_safe()
- ✅ FIXED: Tombol tidak berfungsi setelah lama dipause → hapus task jika chat tidak valid
- ✅ IMPROVED: Semua akses chat menggunakan get_chat_safe() untuk hindari crash
- ✅ IMPROVED: Validasi chat sebelum mulai task, sebelum callback, sebelum command
- 🧹 CLEANUP: Hapus task otomatis jika chat tidak valid di semua handler
- 📦 MAINTENANCE: Kode utuh tanpa potongan, siap pakai
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
# 🔥 TAMBAHAN: Dictionary untuk menyimpan konfigurasi sementara sebelum konfirmasi
PENDING_CONFIRMATIONS = {}

# Daftar emoji reaction yang valid sesuai API Telegram
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

# ==================== CLIENT SETUP ====================
try:
    if hasattr(Altruix, 'userbot'):
        USER_CLIENT = Altruix.userbot
    else:
        USER_CLIENT = Altruix
    BOT_CLIENT = Altruix.bot if hasattr(Altruix, 'bot') else None
except AttributeError:
    USER_CLIENT = Altruix
    BOT_CLIENT = None

# ============= HANDLER & LOG CHAT ====================
try:
    HANDLER = Altruix.config.HANDLERS[0] if isinstance(Altruix.config.HANDLERS, list) else Altruix.config.HANDLERS
except AttributeError:
    HANDLER = "."

try:
    LOG_CHAT_ID = Altruix.config.LOG_CHAT_ID
except AttributeError:
    try:
        LOG_CHAT_ID = Altruix.config.OWNER_ID
    except AttributeError:
        LOG_CHAT_ID = None
if not LOG_CHAT_ID:
    LOG_CHAT_ID = "me"

# ==================== SAFE CHAT RESOLVER ====================
async def get_chat_safe(client: Client, identifier):
    """Mengembalikan objek chat jika valid, atau None jika tidak valid."""
    try:
        return await client.get_chat(identifier)
    except (ChannelInvalid, ChannelPrivate, PeerIdInvalid, UsernameInvalid, ValueError, TypeError) as e:
        Altruix.log(f"[CHAT_ERROR] Gagal resolve chat {identifier}: {e}", level=40)
        return None
    except Exception as e:
        Altruix.log(f"[CHAT_ERROR] Error tak terduga saat resolve {identifier}: {e}", level=40)
        return None

# ==================== LOG MESSAGE HELPER ====================
async def send_log_message(text, reply_to_message_id=None, reply_markup=None, client=None):
    try:
        if BOT_CLIENT:
            try:
                return await smart_send(
                    client=BOT_CLIENT,
                    method_name="send_message",
                    chat_id=LOG_CHAT_ID,
                    text=text,
                    reply_to_message_id=reply_to_message_id,
                    reply_markup=reply_markup
                )
            except Exception as e:
                Altruix.log(f"Error menggunakan BOT_CLIENT: {e}", level=40)
        if USER_CLIENT:
            try:
                return await smart_send(
                    client=USER_CLIENT,
                    method_name="send_message",
                    chat_id=LOG_CHAT_ID,
                    text=text,
                    reply_to_message_id=reply_to_message_id,
                    reply_markup=reply_markup
                )
            except Exception as e:
                Altruix.log(f"Error menggunakan USER_CLIENT: {e}", level=40)
        Altruix.log(f"Tidak ada client yang dapat mengirim pesan log: {text}", level=40)
        return None
    except Exception as e:
        Altruix.log(f"Error kritis di send_log_message: {e}", level=50)
        return None

# ==================== VALIDATE CHAT (KONSISTEN RETURN 2 NILAI) ====================
async def validate_chat(client: Client, destination: str) -> tuple:
    try:
        if destination.isdigit() and len(destination) >= 10:
            destination = "-100" + destination
        if destination.startswith("@"):
            try:
                target_chat = await client.join_chat(destination)
                return True, (str(target_chat.id), target_chat)
            except (errors.UserAlreadyParticipant, errors.PeerIdInvalid):
                target_chat = await get_chat_safe(client, destination)
                if target_chat:
                    return True, (str(target_chat.id), target_chat)
                else:
                    return False, f"Tidak dapat mengakses chat {destination}"
            except Exception as e:
                return False, f"Tidak dapat join ke chat {destination}: {str(e)}"
        try:
            chat_id = int(destination) if destination.replace("-", "").isdigit() else None
        except ValueError:
            chat_id = None
        if chat_id:
            target_chat = await get_chat_safe(client, chat_id)
            if target_chat:
                return True, (str(target_chat.id), target_chat)
            else:
                return False, "Channel tidak valid atau userbot tidak memiliki akses."
        target_chat = await get_chat_safe(client, destination)
        if target_chat:
            return True, (str(target_chat.id), target_chat)
        else:
            return False, "Tidak dapat mengakses chat tersebut."
    except Exception as e:
        return False, f"Error saat memvalidasi chat {destination}: {str(e)}"

# ==================== DYNAMIC BUTTON UPDATERS ====================
async def update_purge_button(message: Message, chat_id: str, purge_value: int):
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

async def update_reaction_button(message: Message, chat_id: str, reaction_enabled: bool, emoji: str = None):
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

# ==================== MSG LIST PREVIEW ====================
async def show_msg_list_preview(c: Client, m: Message, msg_list: list, is_batch: bool):
    try:
        preview_lines = []
        total_items = len(msg_list)
        total_chars = 0
        if is_batch:
            for i, (msg, count) in enumerate(msg_list, 1):
                char_len = len(msg)
                total_chars += char_len * count
                preview_lines.append(f"{i}. [{count}x] {msg[:30]}{'...' if len(msg) > 30 else ''} ({char_len} chars)")
        else:
            for i, msg in enumerate(msg_list, 1):
                char_len = len(msg)
                total_chars += char_len
                preview_lines.append(f"{i}. {msg[:30]}{'...' if len(msg) > 30 else ''} ({char_len} chars)")
        preview_text = (
            f"👁️ **Message List Preview**\n"
            f"Total items: {total_items}\n"
            f"Total chars: {total_chars}\n"
            f"{'='*30}\n" +
            "\n".join(preview_lines)
        )
        await m.reply(preview_text)
    except Exception as e:
        Altruix.log(f"Error showing msg list preview: {e}", level=40)
        await m.reply("❌ Gagal menampilkan preview list pesan.")

# ==================== START RELAYSPAM ====================
async def start_relayspam(client: Client, destination: str, start_delay: float, stop_delay: float,
                          step: float, count: int, old_purge: int, emot_react: str,
                          msg_list: list, is_batch: bool, react_enabled: bool = True) -> bool:
    chat_id = None
    try:
        validation_success, validation_result = await validate_chat(client, destination)
        if not validation_success:
            await send_log_message(
                f"❌ **VALIDATION FAILED**\n"
                f"Tujuan: {destination}\n"
                f"Error: {validation_result}\n"
                f"💡 **Solusi:**\n"
                f"- Pastikan userbot sudah join ke grup/channel\n"
                f"- Untuk channel private, pastikan userbot adalah admin atau sudah diundang\n"
                f"- Periksa kembali ID chat atau username",
                client=client
            )
            return False

        chat_id, target_chat = validation_result

        if chat_id in TELAYSPAM_TASKS:
            await send_log_message(f"**Error:** Task relayspam sudah berjalan di {target_chat.title}.", client=client)
            return False

        TELAYSPAM_TASKS[chat_id] = {
            "running": True,
            "pause_event": asyncio.Event(),
            "client": client,
            "config": {
                "destination": destination,
                "start_delay": start_delay,
                "stop_delay": stop_delay,
                "step": step,
                "count": count,
                "old_purge": old_purge,
                "emot_react": emot_react,
                "msg_list": msg_list[:],
                "is_batch": is_batch,
                "react_enabled": react_enabled
            }
        }
        TELAYSPAM_TASKS[chat_id]["pause_event"].set()
        clean_id = str(target_chat.id).replace("-100", "")
        userbot_info = "👤 **Unknown Userbot**"
        try:
            me = await client.get_me()
            userbot_info = f"👤 **[Akun Aktif: {me.first_name}](tg://user?id={me.id})**"
        except:
            pass
        notif_msg = (
            f"Notifikasi Task\n"
            f"Tugas spam akan segera dimulai.\n"
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
            f"{userbot_info}\n"
        )
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
             InlineKeyboardButton("Pilih Emoji", callback_data=f"select_emoji_{chat_id}")],
            [InlineKeyboardButton("👁️ See Msg List", callback_data=f"see_msglist_{chat_id}")]
        ]
        x_msg = await send_log_message(
            f"{notif_msg}",
            reply_markup=InlineKeyboardMarkup(tombol_baris),
            client=client
        )
        if x_msg:
            TELAYSPAM_TASKS[chat_id]["notif_msg"] = x_msg
            try:
                await x_msg.pin()
            except Exception as erpin:
                Altruix.log(f"#ERROR_PIN : {erpin}", level=30)
        else:
            Altruix.log("Gagal mengirim notifikasi task", level=30)

        delays_possible = []
        current = start_delay
        while current <= stop_delay:
            delays_possible.append(current)
            current += step
        if not delays_possible:
            raise ValueError("Tidak ada nilai delay yang mungkin dalam rentang yang diberikan.")

        task = asyncio.create_task(spam_loop(client, target_chat, chat_id, msg_list, delays_possible,
                                            count, start_delay, stop_delay, step, x_msg, emot_react, is_batch, react_enabled))
        TELAYSPAM_TASKS[chat_id]["task"] = task
        return True
    except Exception as u:
        Altruix.log(f"[CRITICAL] Error in start_relayspam: {u}", level=50)
        await send_log_message(f"__Error in start_relayspam: {u}__", client=client)
        if chat_id in TELAYSPAM_TASKS:
            TELAYSPAM_TASKS.pop(chat_id, None)
        return False

# ==================== SPAM LOOP ====================
async def spam_loop(client: Client, target_chat, chat_id: str, msg_list, delays_possible,
                    count: int, start_delay: float, stop_delay: float, step: float,
                    x_msg: Message, emot_react: str, is_batch: bool, react_enabled: bool = True):
    try:
        sent_count = 0
        total_del_suk = 0
        total_del_ggl = 0
        spam_client = client

        # Validasi ulang akses chat
        if not await get_chat_safe(client, target_chat.id):
            error_msg = "❌ **TASK DIBATALKAN**\nUserbot kehilangan akses ke channel/grup."
            Altruix.log(f"[SPAM_LOOP_ERROR] {error_msg}", level=40)
            await send_log_message(error_msg, client=client)
            if chat_id in TELAYSPAM_TASKS:
                TELAYSPAM_TASKS.pop(chat_id, None)
            return

        if is_batch:
            for msg, b_count in msg_list:
                for _ in range(b_count):
                    if not TELAYSPAM_TASKS.get(chat_id, {}).get("running", False):
                        Altruix.log(f"Task dihentikan untuk chat {chat_id}", level=30)
                        await send_log_message(f"__Task dihentikan untuk chat {chat_id}__", client=client)
                        break
                    await TELAYSPAM_TASKS[chat_id]["pause_event"].wait()
                    old_purge_val = TELAYSPAM_TASKS[chat_id]["config"]["old_purge"]
                    del_suk, del_ggl = 0, 0
                    if old_purge_val > 0:
                        try:
                            messages = []
                            async for message in spam_client.get_chat_history(target_chat.id, limit=old_purge_val * 2):
                                messages.append(message)
                            if messages:
                                my_messages = [msg for msg in messages if msg.from_user and msg.from_user.id == spam_client.me.id][:old_purge_val]
                                message_ids = [msg.id for msg in my_messages]
                                if message_ids:
                                    await spam_client.delete_messages(target_chat.id, message_ids)
                                    del_suk = len(message_ids)
                                    await asyncio.sleep(1)
                                else:
                                    del_suk = 0
                                del_ggl = old_purge_val - del_suk
                                total_del_suk += del_suk
                                total_del_ggl += del_ggl
                                if del_suk > 0:
                                    await send_log_message(
                                        f"[HAPUS]: Berhasil hapus {del_suk} pesan lama, gagal {del_ggl} pesan di {target_chat.title}.",
                                        reply_to_message_id=x_msg.id if x_msg else None,
                                        client=client
                                    )
                        except Exception as del_err:
                            if "CHANNEL_INVALID" in str(del_err) or "CHANNEL_PRIVATE" in str(del_err):
                                error_msg = f"❌ **AKSES DITOLAK**\nUserbot kehilangan akses ke {target_chat.title}.\nTask dihentikan secara otomatis."
                                Altruix.log(f"[SPAM_LOOP_ERROR] {error_msg} - Detail: {str(del_err)}", level=40)
                                await send_log_message(error_msg, client=client)
                                if chat_id in TELAYSPAM_TASKS:
                                    TELAYSPAM_TASKS.pop(chat_id, None)
                                return
                            else:
                                Altruix.log(f"Error saat menghapus pesan: {del_err}", level=40)
                                await send_log_message(f"Error hapus pesan: {del_err}", reply_to_message_id=x_msg.id if x_msg else None, client=client)
                    random_delay = random.choice(delays_possible)
                    while True:
                        try:
                            sent_msg = await spam_client.send_message(target_chat.id, msg)
                            sent_count += 1
                            react_status = "tidak ada"
                            current_react_enabled = TELAYSPAM_TASKS[chat_id]["config"].get("react_enabled", True)
                            current_emot_react = TELAYSPAM_TASKS[chat_id]["config"]["emot_react"]
                            if current_react_enabled and current_emot_react and current_emot_react.lower() != "none":
                                try:
                                    await asyncio.sleep(2)
                                    await spam_client.send_reaction(target_chat.id, sent_msg.id, current_emot_react)
                                    react_status = f"{current_emot_react} berhasil"
                                except Exception as react_err:
                                    Altruix.log(f"Error saat menambahkan reaksi: {react_err}", level=40)
                                    react_status = f"{current_emot_react} gagal"
                            remaining = count - sent_count
                            percentage = (sent_count / count) * 100 if count > 0 else 0
                            char_count = len(msg)
                            await send_log_message(
                                f"Pesan terkirim\n"
                                f"Mode: {'Batch' if is_batch else 'Acak'}\n"
                                f"Delay: {random_delay:.2f} detik\n"
                                f"Sisa: {remaining} pesan\n"
                                f"Progress: {percentage:.2f}%\n"
                                f"Length: {char_count} karakter\n"
                                f"React: {react_status}\n"
                                f"Pesan: {msg[:50]}..." if len(msg) > 50 else f"Pesan: {msg}",
                                reply_to_message_id=x_msg.id if x_msg else None,
                                client=client
                            )
                            await asyncio.sleep(random_delay)
                            break
                        except SlowmodeWait as swe:
                            Altruix.log(f"SlowModeWaitError: Waiting for {swe.value} seconds", level=30)
                            await send_log_message(f"** [ #ERROR ]** __SlowModeWaitError: Waiting for {swe.value} seconds__", reply_to_message_id=x_msg.id if x_msg else None, client=client)
                            await asyncio.sleep(swe.value)
                        except FloodWait as fwe:
                            Altruix.log(f"FloodWaitError: Waiting for {fwe.value} seconds", level=30)
                            await send_log_message(f"** [ #ERROR ]** __FloodWaitError: Waiting for {fwe.value} seconds__", reply_to_message_id=x_msg.id if x_msg else None, client=client)
                            await asyncio.sleep(fwe.value)
                        except ChatWriteForbidden as cwe:
                            Altruix.log(f"UserBot muted in chat {chat_id}: Pausing task automatically.", level=30)
                            await send_log_message(f"** [ #ERROR ]** __UserBot muted in chat {target_chat.title}: Task paused automatically.__", reply_to_message_id=x_msg.id if x_msg else None, client=client)
                            TELAYSPAM_TASKS[chat_id]["pause_event"].clear()
                            break
                        except (errors.ChannelInvalid, errors.ChannelPrivate) as e:
                            error_msg = f"❌ **TUGAS DIBATALKAN**\nUserbot kehilangan akses ke {target_chat.title}.\nTask dihentikan secara otomatis."
                            Altruix.log(f"[SPAM_LOOP_ERROR] {error_msg} - Detail: {str(e)}", level=40)
                            await send_log_message(error_msg, client=client)
                            if chat_id in TELAYSPAM_TASKS:
                                TELAYSPAM_TASKS.pop(chat_id, None)
                            return
                        except Exception as send_err:
                            Altruix.log(f"Error saat mengirim pesan: {send_err}", level=40)
                            await send_log_message(f"** [ #ERROR ]** __Error saat mengirim pesan: {send_err}__", reply_to_message_id=x_msg.id if x_msg else None, client=client)
                            await asyncio.sleep(5)
        else:
            for _ in range(count):
                if not TELAYSPAM_TASKS.get(chat_id, {}).get("running", False):
                    Altruix.log(f"Task dihentikan untuk chat {chat_id}", level=30)
                    await send_log_message(f"__Task dihentikan untuk chat {chat_id}__", client=client)
                    break
                await TELAYSPAM_TASKS[chat_id]["pause_event"].wait()
                old_purge_val = TELAYSPAM_TASKS[chat_id]["config"]["old_purge"]
                del_suk, del_ggl = 0, 0
                if old_purge_val > 0:
                    try:
                        messages = []
                        async for message in spam_client.get_chat_history(target_chat.id, limit=old_purge_val * 2):
                            messages.append(message)
                        if messages:
                            my_messages = [msg for msg in messages if msg.from_user and msg.from_user.id == spam_client.me.id][:old_purge_val]
                            message_ids = [msg.id for msg in my_messages]
                            if message_ids:
                                await spam_client.delete_messages(target_chat.id, message_ids)
                                del_suk = len(message_ids)
                                await asyncio.sleep(1)
                            else:
                                del_suk = 0
                            del_ggl = old_purge_val - del_suk
                            total_del_suk += del_suk
                            total_del_ggl += del_ggl
                            if del_suk > 0:
                                await send_log_message(
                                    f"[HAPUS]: Berhasil hapus {del_suk} pesan lama, gagal {del_ggl} pesan di {target_chat.title}.",
                                    reply_to_message_id=x_msg.id if x_msg else None,
                                    client=client
                                )
                    except Exception as del_err:
                        if "CHANNEL_INVALID" in str(del_err) or "CHANNEL_PRIVATE" in str(del_err):
                            error_msg = f"❌ **AKSES DITOLAK**\nUserbot kehilangan akses ke {target_chat.title}.\nTask dihentikan secara otomatis."
                            Altruix.log(f"[SPAM_LOOP_ERROR] {error_msg} - Detail: {str(del_err)}", level=40)
                            await send_log_message(error_msg, client=client)
                            if chat_id in TELAYSPAM_TASKS:
                                TELAYSPAM_TASKS.pop(chat_id, None)
                            return
                        else:
                            Altruix.log(f"Error saat menghapus pesan: {del_err}", level=40)
                            await send_log_message(f"Error hapus pesan: {del_err}", reply_to_message_id=x_msg.id if x_msg else None, client=client)
                msg = random.choice(msg_list)
                random_delay = random.choice(delays_possible)
                while True:
                    try:
                        sent_msg = await spam_client.send_message(target_chat.id, msg)
                        sent_count += 1
                        react_status = "tidak ada"
                        current_react_enabled = TELAYSPAM_TASKS[chat_id]["config"].get("react_enabled", True)
                        current_emot_react = TELAYSPAM_TASKS[chat_id]["config"]["emot_react"]
                        if current_react_enabled and current_emot_react and current_emot_react.lower() != "none":
                            try:
                                await asyncio.sleep(2)
                                await spam_client.send_reaction(target_chat.id, sent_msg.id, current_emot_react)
                                react_status = f"{current_emot_react} berhasil"
                            except Exception as react_err:
                                Altruix.log(f"Error saat menambahkan reaksi: {react_err}", level=40)
                                react_status = f"{current_emot_react} gagal"
                        remaining = count - sent_count
                        percentage = (sent_count / count) * 100 if count > 0 else 0
                        char_count = len(msg)
                        await send_log_message(
                            f"Pesan terkirim\n"
                            f"Mode: {'Batch' if is_batch else 'Acak'}\n"
                            f"Delay: {random_delay:.2f} detik\n"
                            f"Sisa: {remaining} pesan\n"
                            f"Progress: {percentage:.2f}%\n"
                            f"Length: {char_count} karakter\n"
                            f"React: {react_status}\n"
                            f"Pesan: {msg[:50]}..." if len(msg) > 50 else f"Pesan: {msg}",
                            reply_to_message_id=x_msg.id if x_msg else None,
                            client=client
                        )
                        await asyncio.sleep(random_delay)
                        break
                    except SlowmodeWait as swe:
                        Altruix.log(f"SlowModeWaitError: Waiting for {swe.value} seconds", level=30)
                        await send_log_message(f"** [ #ERROR ]** __SlowModeWaitError: Waiting for {swe.value} seconds__", reply_to_message_id=x_msg.id if x_msg else None, client=client)
                        await asyncio.sleep(swe.value)
                    except FloodWait as fwe:
                        Altruix.log(f"FloodWaitError: Waiting for {fwe.value} seconds", level=30)
                        await send_log_message(f"** [ #ERROR ]** __FloodWaitError: Waiting for {fwe.value} seconds__", reply_to_message_id=x_msg.id if x_msg else None, client=client)
                        await asyncio.sleep(fwe.value)
                    except ChatWriteForbidden as cwe:
                        Altruix.log(f"UserBot muted in chat {chat_id}: Pausing task automatically.", level=30)
                        await send_log_message(f"** [ #ERROR ]** __UserBot muted in chat {target_chat.title}: Task paused automatically.__", reply_to_message_id=x_msg.id if x_msg else None, client=client)
                        TELAYSPAM_TASKS[chat_id]["pause_event"].clear()
                        break
                    except (errors.ChannelInvalid, errors.ChannelPrivate) as e:
                        error_msg = f"❌ **TUGAS DIBATALKAN**\nUserbot kehilangan akses ke {target_chat.title}.\nTask dihentikan secara otomatis."
                        Altruix.log(f"[SPAM_LOOP_ERROR] {error_msg} - Detail: {str(e)}", level=40)
                        await send_log_message(error_msg, client=client)
                        if chat_id in TELAYSPAM_TASKS:
                            TELAYSPAM_TASKS.pop(chat_id, None)
                        return
                    except Exception as send_err:
                        Altruix.log(f"Error saat mengirim pesan: {send_err}", level=40)
                        await send_log_message(f"** [ #ERROR ]** __Error saat mengirim pesan: {send_err}__", reply_to_message_id=x_msg.id if x_msg else None, client=client)
                        await asyncio.sleep(5)
        if TELAYSPAM_TASKS.get(chat_id, {}).get("running", False):
            await send_log_message(
                f"[SELESAI]:\n"
                f"Spam di {target_chat.title} telah selesai!\n"
                f"Terkirim {sent_count} pesan ({'batch' if is_batch else 'acak'}), delay acak [{start_delay}-{stop_delay}] dengan interval {step} detik,\n"
                f"Total sukses hapus {total_del_suk} pesan, total gagal hapus {total_del_ggl} pesan.",
                reply_to_message_id=x_msg.id if x_msg else None,
                client=client
            )
    except Exception as u:
        Altruix.log(f"[CRITICAL] Error in spam_loop: {u}", level=50)
        await send_log_message(f"__Error in spam_loop: {u}__", client=client)
    finally:
        if chat_id in TELAYSPAM_TASKS:
            config = TELAYSPAM_TASKS[chat_id].pop('config', None)
            if config:
                COMPLETED_TASKS[chat_id] = config
        TELAYSPAM_TASKS.pop(chat_id, None)

# ==================== CALLBACK HANDLERS ====================
@Altruix.bot.on_callback_query(filters.regex(r"see_msglist_(-?\d+)"))
@log_errors
async def see_msglist_handler(c: Client, cb):
    chat_id = cb.data.split("_")[-1]
    config = None
    if chat_id in TELAYSPAM_TASKS:
        config = TELAYSPAM_TASKS[chat_id]["config"]
    elif chat_id in COMPLETED_TASKS:
        config = COMPLETED_TASKS[chat_id]
    if not config:
        await cb.answer("❌ Tidak ada data pesan untuk ditampilkan.", show_alert=True)
        return
    msg_list = config["msg_list"]
    is_batch = config["is_batch"]
    try:
        preview_lines = []
        total_items = len(msg_list)
        total_chars = 0
        if is_batch:
            for i, (msg, count) in enumerate(msg_list, 1):
                char_len = len(msg)
                total_chars += char_len * count
                preview_lines.append(f"{i}. [{count}x] {msg[:40]}{'...' if len(msg) > 40 else ''} ({char_len} chars)")
        else:
            for i, msg in enumerate(msg_list, 1):
                char_len = len(msg)
                total_chars += char_len
                preview_lines.append(f"{i}. {msg[:40]}{'...' if len(msg) > 40 else ''} ({char_len} chars)")
        preview_text = (
            f"👁️ **Message List Preview**\n"
            f"Total items: {total_items}\n"
            f"Total chars: {total_chars}\n"
            f"{'='*40}\n" +
            "\n".join(preview_lines)
        )
        if len(preview_text) > 200:
            userbot_client = TELAYSPAM_TASKS.get(chat_id, {}).get("client") or USER_CLIENT
            await send_log_message(preview_text, client=userbot_client)
            await cb.answer("ℹ️ Preview dikirim sebagai pesan.", show_alert=True)
        else:
            await cb.answer(preview_text, show_alert=True)
    except Exception as e:
        Altruix.log(f"Error in see_msglist_handler: {e}", level=40)
        await cb.answer("❌ Gagal menampilkan preview.", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^confirm_start_[^_]+?\|\|[^_]+?_(confirm|cancel)$"))
@log_errors
async def confirm_start_handler(c: Client, cb):
    try:
        full_data = cb.data
        Altruix.log(f"[DEBUG] Callback diterima: {full_data}", level=20)
        if not full_data.startswith("confirm_start_"):
            await cb.answer("Data callback tidak valid.", show_alert=True)
            return
        suffix = full_data[len("confirm_start_"):]
        last_underscore = suffix.rfind("_")
        if last_underscore == -1:
            await cb.answer("Format callback tidak valid.", show_alert=True)
            Altruix.log(f"[ERROR] Format callback tidak valid: {full_data}", level=40)
            return
        temp_id = suffix[:last_underscore]
        action = suffix[last_underscore + 1:]
        Altruix.log(f"[DEBUG] Parsed temp_id: {temp_id}, action: {action}", level=20)
        if action == "confirm":
            if temp_id not in PENDING_CONFIRMATIONS:
                Altruix.log(f"[WARN] Konfirmasi kadaluarsa atau tidak ditemukan: {temp_id}", level=30)
                await cb.answer("❌ Konfirmasi sudah kadaluarsa.", show_alert=True)
                return
            data = PENDING_CONFIRMATIONS.pop(temp_id)
            Altruix.log(f"[INFO] Memulai task dari konfirmasi: {temp_id}", level=20)

            validation_success, validation_result = await validate_chat(data["client"], data["destination"])
            if not validation_success:
                await cb.answer(f"❌ Gagal validasi chat: {validation_result}", show_alert=True)
                await send_log_message(
                    f"❌ **VALIDATION FAILED**\n"
                    f"Tujuan: {data['destination']}\n"
                    f"Error: {validation_result}\n"
                    f"💡 **Solusi:**\n"
                    f"- Pastikan userbot sudah join ke grup/channel\n"
                    f"- Untuk channel private, pastikan userbot adalah admin atau sudah diundang\n"
                    f"- Periksa kembali ID chat atau username",
                    client=data["client"]
                )
                return

            chat_id, target_chat = validation_result

            success = await start_relayspam(
                data["client"],
                data["destination"],
                data["start_delay"],
                data["stop_delay"],
                data["step"],
                data["count"],
                data["old_purge"],
                data["emot_react"],
                data["msg_list"],
                data["is_batch"],
                data["react_enabled"]
            )
            if success:
                await cb.answer("✅ Task berhasil dimulai!", show_alert=True)
                Altruix.log(f"[SUCCESS] Task dimulai dari konfirmasi: {temp_id}", level=20)
            else:
                await cb.answer("❌ Gagal memulai task.", show_alert=True)
                Altruix.log(f"[ERROR] Gagal memulai task dari konfirmasi: {temp_id}", level=40)
        elif action == "cancel":
            if temp_id in PENDING_CONFIRMATIONS:
                PENDING_CONFIRMATIONS.pop(temp_id)
                Altruix.log(f"[INFO] Konfirmasi dibatalkan: {temp_id}", level=20)
            else:
                Altruix.log(f"[WARN] Konfirmasi sudah tidak ada saat cancel: {temp_id}", level=30)
            await cb.answer("❌ Pembuatan task dibatalkan.", show_alert=True)
            try:
                await cb.message.delete()
            except Exception as e:
                Altruix.log(f"[DEBUG] Gagal hapus pesan konfirmasi: {e}", level=20)
        else:
            await cb.answer("Aksi tidak dikenali.", show_alert=True)
            Altruix.log(f"[WARN] Aksi tidak dikenali: {action}", level=30)
    except Exception as e:
        Altruix.log(f"[CRITICAL] Error di confirm_start_handler: {e}", level=50)
        await cb.answer("❌ Terjadi kesalahan internal. Silakan coba lagi.", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^preview_msglist_(.+)$"))
@log_errors
async def preview_msglist_from_confirm(c: Client, cb):
    full_data = cb.data
    Altruix.log(f"[DEBUG] Preview callback: {full_data}", level=20)
    if not full_data.startswith("preview_msglist_"):
        await cb.answer("Data tidak valid.", show_alert=True)
        return
    temp_id = full_data[len("preview_msglist_"):]
    Altruix.log(f"[DEBUG] Preview untuk temp_id: {temp_id}", level=20)
    if temp_id not in PENDING_CONFIRMATIONS:
        await cb.answer("❌ Data tidak ditemukan.", show_alert=True)
        Altruix.log(f"[WARN] Data tidak ditemukan untuk preview: {temp_id}", level=30)
        return
    data = PENDING_CONFIRMATIONS[temp_id]
    await show_msg_list_preview(c, cb.message, data["msg_list"], data["is_batch"])
    await cb.answer("ℹ️ Preview ditampilkan.", show_alert=False)

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
    try:
        text = m.text.strip()
        cmd_pattern = re.escape(HANDLER) + r'relayspam\s+'
        args_str = re.sub(cmd_pattern, '', text, count=1)
        if not args_str:
            await m.handle_message("INVALID_ARG_COUNT")
            return
        msg_list_match = re.search(r'\[.*\]$', args_str, re.DOTALL)
        if not msg_list_match:
            await m.handle_message("INVALID_MSG_LIST_FORMAT")
            return
        msg_list_str = msg_list_match.group(0)
        args_str_without_msg = args_str[:msg_list_match.start()].strip()
        try:
            args = shlex.split(args_str_without_msg)
        except Exception:
            args = args_str_without_msg.split()
        if len(args) not in [6, 7]:
            await m.handle_message("INVALID_ARG_COUNT")
            return
        destination = args[0]
        start_delay = float(args[1])
        stop_delay = float(args[2])
        step = float(args[3])
        count = int(args[4])
        old_purge = int(args[5])
        emot_react = args[6] if len(args) == 7 and args[6].lower() != "none" else None
        try:
            msg_list = ast.literal_eval(msg_list_str)
        except (ValueError, SyntaxError) as e:
            Altruix.log(f"Error parsing msg_list: {e}", level=40)
            await m.handle_message("INVALID_MSG_LIST")
            return
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
        Altruix.log(f"Error parsing command: {err}", level=40)
        await m.handle_message("PARSING_ERROR")
        return
    except Exception as e:
        Altruix.log(f"Error parsing command: {e}", level=40)
        await m.handle_message("ERROR_OCCURRED")
        return

    try:
        await m.handle_message("PROCESSING_TASK")
        await asyncio.sleep(2)
    except Exception as e:
        Altruix.log(f"Error during processing task: {e}", level=40)
        await m.handle_message("PROCESSING_TASK")
        await asyncio.sleep(2)

    react_enabled = emot_react is not None and emot_react.lower() != "none"
    temp_id = f"{m.chat.id}||{m.id}"
    PENDING_CONFIRMATIONS[temp_id] = {
        "client": c,
        "destination": destination,
        "start_delay": start_delay,
        "stop_delay": stop_delay,
        "step": step,
        "count": count,
        "old_purge": old_purge,
        "emot_react": emot_react,
        "msg_list": msg_list,
        "is_batch": is_batch,
        "react_enabled": react_enabled
    }
    confirm_buttons = [
        [InlineKeyboardButton("✅ Confirm Start", callback_data=f"confirm_start_{temp_id}_confirm")],
        [InlineKeyboardButton("❌ Cancel", callback_data=f"confirm_start_{temp_id}_cancel")],
        [InlineKeyboardButton("👁️ See Msg List", callback_data=f"preview_msglist_{temp_id}")]
    ]
    confirm_msg = (
        f"⚠️ **Konfirmasi Mulai Task**\n"
        f"Apakah Anda yakin ingin memulai task relayspam?\n"
        f"Tujuan: {destination}\n"
        f"Mode: {'Batch' if is_batch else 'Acak'}\n"
        f"Pesan: {len(msg_list)} item\n"
        f"Total: {count} pesan\n"
        f"Delay: {start_delay}–{stop_delay} detik\n"
        f"Purge: {old_purge}\n"
        f"React: {'Aktif' if react_enabled else 'Nonaktif'}"
    )
    try:
        if not BOT_CLIENT:
            await m.handle_message("BOT_NOT_AVAILABLE")
            Altruix.log("Bot client tidak tersedia.", level=40)
            PENDING_CONFIRMATIONS.pop(temp_id, None)
            return
        await BOT_CLIENT.send_message(
            chat_id=LOG_CHAT_ID,
            text=confirm_msg,
            reply_markup=InlineKeyboardMarkup(confirm_buttons)
        )
        await m.handle_message("CONFIRMATION_SENT")
        Altruix.log(f"[INFO] Konfirmasi dikirim: {temp_id}", level=20)
    except Exception as send_err:
        Altruix.log(f"Gagal mengirim konfirmasi: {send_err}", level=40)
        await m.edit(f"❌ Gagal mengirim konfirmasi: {send_err}")
        PENDING_CONFIRMATIONS.pop(temp_id, None)

# ==================== COMMAND HANDLERS ====================
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
    try:
        args = m.text.split(" ", 1)
        if len(args) < 2:
            await m.handle_message("MISSING_DESTINATION_ARG")
            return
        destination = args[1]
        if destination.isdigit() and len(destination) >= 10:
            destination = "-100" + destination
        target_chat = await get_chat_safe(c, int(destination) if destination.replace("-", "").isdigit() else destination)
        if not target_chat:
            await m.handle_message("CHAT_INVALID_OR_INACCESSIBLE")
            return
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
    try:
        args = m.text.split(" ", 1)
        if len(args) < 2:
            await m.handle_message("MISSING_DESTINATION_ARG")
            return
        destination = args[1]
        if destination.isdigit() and len(destination) >= 10:
            destination = "-100" + destination
        target_chat = await get_chat_safe(c, int(destination) if destination.replace("-", "").isdigit() else destination)
        if not target_chat:
            await m.handle_message("CHAT_INVALID_OR_INACCESSIBLE")
            return
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
    try:
        args = m.text.split(" ", 1)
        if len(args) < 2:
            await m.handle_message("MISSING_DESTINATION_ARG")
            return
        destination = args[1]
        if destination.isdigit() and len(destination) >= 10:
            destination = "-100" + destination
        target_chat = await get_chat_safe(c, int(destination) if destination.replace("-", "").isdigit() else destination)
        if not target_chat:
            await m.handle_message("CHAT_INVALID_OR_INACCESSIBLE")
            return
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
    try:
        args = m.text.split(" ", 1)
        if len(args) > 1:
            destination = args[1]
            if destination.isdigit() and len(destination) >= 10:
                destination = "-100" + destination
            target_chat = await get_chat_safe(c, int(destination) if destination.replace("-", "").isdigit() else destination)
            if not target_chat:
                await m.handle_message("CHAT_INVALID_OR_INACCESSIBLE")
                return
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
    if not TELAYSPAM_TASKS:
        await m.handle_message("NO_ACTIVE_TASKS")
        return
    status_list = []
    for chat_id, status in TELAYSPAM_TASKS.items():
        target_chat = await get_chat_safe(c, int(chat_id))
        if not target_chat:
            status_list.append(f"❓ Unknown chat (ID: {chat_id}) - Tidak valid atau tidak bisa diakses.")
            continue
        chat_title = target_chat.title if hasattr(target_chat, 'title') else (target_chat.first_name or target_chat.username)
        if status["running"]:
            if status["pause_event"].is_set():
                status_text = f"🔵 running di {chat_title} (ID: {chat_id})"
            else:
                status_text = f"🟡 paused di {chat_title} (ID: {chat_id})"
        else:
            status_text = f"🔴 stopped di {chat_title} (ID: {chat_id})"
        status_list.append(status_text)
    output = "Status Semua Task Relayspam:\n" + "\n".join(status_list)
    await m.edit(output)

# ==================== MORE CALLBACKS ====================
@Altruix.bot.on_callback_query(filters.regex(r"toggle_purge_(-?\d+)"))
@log_errors
async def toggle_purge_handler(c: Client, cb):
    data = cb.data
    chat_id = data.split("_")[-1]
    if chat_id not in TELAYSPAM_TASKS:
        await cb.answer("Task tidak aktif.", show_alert=True)
        return
    config = TELAYSPAM_TASKS[chat_id]["config"]
    current_purge = config["old_purge"]
    if current_purge > 0:
        new_purge = 0
        status = "NONAKTIF"
    else:
        new_purge = 5
        status = "AKTIF"
    config["old_purge"] = new_purge
    await cb.answer(f"Purge old message: {status}", show_alert=True)
    userbot_client = TELAYSPAM_TASKS[chat_id]["client"]
    await send_log_message(
        f"PURGE TOGGLED\n"
        f"Chat: {config['destination']}\n"
        f"Status: {status}\n"
        f"Jumlah hapus: {new_purge} pesan lama",
        client=userbot_client
    )
    try:
        notif_msg = TELAYSPAM_TASKS[chat_id].get("notif_msg")
        if notif_msg:
            await update_purge_button(notif_msg, chat_id, new_purge)
    except Exception as e:
        Altruix.log(f"Gagal update tombol purge: {e}", level=40)

@Altruix.bot.on_callback_query(filters.regex(r"toggle_react_(-?\d+)"))
@log_errors
async def toggle_reaction_handler(c: Client, cb):
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
    userbot_client = TELAYSPAM_TASKS[chat_id]["client"]
    await send_log_message(
        f"REACTION TOGGLED\n"
        f"Chat: {config['destination']}\n"
        f"Status: {status}\n"
        f"Emoji: {emoji}",
        client=userbot_client
    )
    try:
        notif_msg = TELAYSPAM_TASKS[chat_id].get("notif_msg")
        if notif_msg:
            await update_reaction_button(notif_msg, chat_id, new_enabled, emoji if new_enabled else None)
    except Exception as e:
        Altruix.log(f"Gagal update tombol reaction: {e}", level=40)

@Altruix.bot.on_callback_query(filters.regex(r"select_emoji_(-?\d+)"))
@log_errors
async def select_emoji_handler(c: Client, cb):
    data = cb.data
    chat_id = data.split("_")[-1]
    if chat_id not in TELAYSPAM_TASKS:
        await cb.answer("Task tidak aktif.", show_alert=True)
        return
    keyboard = []
    row = []
    for i, emoji in enumerate(VALID_EMOJIS):
        row.append(InlineKeyboardButton(emoji, callback_data=f"set_emoji_{chat_id}_{emoji}"))
        if (i + 1) % 8 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_emoji_{chat_id}")])
    EMOJI_SELECTION_WAITING[chat_id] = True
    userbot_client = TELAYSPAM_TASKS[chat_id]["client"]
    await send_log_message(
        f"Pilih emoji reaction untuk task di chat {chat_id}:\n"
        f"Klik emoji di bawah untuk memilih, atau klik Cancel untuk membatalkan.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        client=userbot_client
    )
    await cb.answer("Pilih emoji dari daftar...", show_alert=False)

@Altruix.bot.on_callback_query(filters.regex(r"set_emoji_(-?\d+)_(.+)"))
@log_errors
async def set_emoji_handler(c: Client, cb):
    data = cb.data
    parts = data.split("_")
    chat_id = parts[2]
    emoji = parts[3]
    if chat_id not in TELAYSPAM_TASKS:
        await cb.answer("Task tidak aktif.", show_alert=True)
        return
    if emoji not in VALID_EMOJIS:
        await cb.answer("Emoji tidak valid!", show_alert=True)
        return
    config = TELAYSPAM_TASKS[chat_id]["config"]
    old_emoji = config["emot_react"]
    config["emot_react"] = emoji
    config["react_enabled"] = True
    await cb.answer(f"Emoji reaction disetel ke: {emoji}", show_alert=True)
    userbot_client = TELAYSPAM_TASKS[chat_id]["client"]
    await send_log_message(
        f"EMOJI UPDATED\n"
        f"Chat: {config['destination']}\n"
        f"Emoji sebelumnya: {old_emoji if old_emoji else 'None'}\n"
        f"Emoji baru: {emoji}\n"
        f"Status: AKTIF",
        client=userbot_client
    )
    try:
        notif_msg = TELAYSPAM_TASKS[chat_id].get("notif_msg")
        if notif_msg:
            await update_reaction_button(notif_msg, chat_id, True, emoji)
    except Exception as e:
        Altruix.log(f"Gagal update tombol reaction: {e}", level=40)
    EMOJI_SELECTION_WAITING.pop(chat_id, None)
    try:
        await cb.message.delete()
    except:
        pass

@Altruix.bot.on_callback_query(filters.regex(r"cancel_emoji_(-?\d+)"))
@log_errors
async def cancel_emoji_handler(c: Client, cb):
    data = cb.data
    chat_id = data.split("_")[-1]
    EMOJI_SELECTION_WAITING.pop(chat_id, None)
    await cb.answer("Pemilihan emoji dibatalkan", show_alert=True)
    try:
        await cb.message.delete()
    except:
        pass

@Altruix.bot.on_callback_query(filters.regex(r"adjust_purge_(-?\d+)"))
@log_errors
async def adjust_purge_handler(c: Client, cb):
    data = cb.data
    chat_id = data.split("_")[-1]
    if chat_id not in TELAYSPAM_TASKS:
        await cb.answer("Task tidak aktif.", show_alert=True)
        return
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
    userbot_client = TELAYSPAM_TASKS[chat_id]["client"]
    adjust_msg = await send_log_message(
        f"📊 **Adjust Purge Settings**\n"
        f"**Chat:** {config['destination']}\n"
        f"**Purge saat ini:** {current_purge} pesan\n"
        f"Pilih tombol di bawah untuk menambah/mengurangi jumlah purge:\n"
        f"• Klik tombol + untuk menambah\n"
        f"• Klik tombol - untuk mengurangi\n"
        f"• Nilai tidak bisa kurang dari 0",
        reply_markup=InlineKeyboardMarkup(keyboard),
        client=userbot_client
    )
    if adjust_msg:
        ADJUST_PURGE_WAITING[chat_id] = adjust_msg.id
    await cb.answer("Menu adjust purge ditampilkan", show_alert=False)

@Altruix.bot.on_callback_query(filters.regex(r"inc_purge_(-?\d+)_(\d+)"))
@log_errors
async def increase_purge_handler(c: Client, cb):
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
    if new_purge < 0:
        new_purge = 0
    config["old_purge"] = new_purge
    await cb.answer(f"Purge ditambah {inc_value}. Total: {new_purge}", show_alert=True)
    userbot_client = TELAYSPAM_TASKS[chat_id]["client"]
    await send_log_message(
        f"PURGE INCREASED\n"
        f"Chat: {config['destination']}\n"
        f"Sebelum: {current_purge} pesan\n"
        f"Ditambah: +{inc_value} pesan\n"
        f"Sesudah: {new_purge} pesan",
        client=userbot_client
    )
    try:
        notif_msg = TELAYSPAM_TASKS[chat_id].get("notif_msg")
        if notif_msg:
            await update_purge_button(notif_msg, chat_id, new_purge)
    except Exception as e:
        Altruix.log(f"Gagal update tombol purge: {e}", level=40)
    try:
        adjust_msg_id = ADJUST_PURGE_WAITING.get(chat_id)
        if adjust_msg_id and isinstance(adjust_msg_id, int) and userbot_client:
            await userbot_client.delete_messages(LOG_CHAT_ID, adjust_msg_id)
    except:
        pass
    ADJUST_PURGE_WAITING.pop(chat_id, None)

@Altruix.bot.on_callback_query(filters.regex(r"dec_purge_(-?\d+)_(\d+)"))
@log_errors
async def decrease_purge_handler(c: Client, cb):
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
    if new_purge < 0:
        new_purge = 0
    config["old_purge"] = new_purge
    status = "NONAKTIF" if new_purge == 0 else f"{new_purge} pesan"
    await cb.answer(f"Purge dikurangi {dec_value}. Total: {status}", show_alert=True)
    userbot_client = TELAYSPAM_TASKS[chat_id]["client"]
    await send_log_message(
        f"PURGE DECREASED\n"
        f"Chat: {config['destination']}\n"
        f"Sebelum: {current_purge} pesan\n"
        f"Dikurangi: -{dec_value} pesan\n"
        f"Sesudah: {new_purge} pesan {'(Nonaktif)' if new_purge == 0 else ''}",
        client=userbot_client
    )
    try:
        notif_msg = TELAYSPAM_TASKS[chat_id].get("notif_msg")
        if notif_msg:
            await update_purge_button(notif_msg, chat_id, new_purge)
    except Exception as e:
        Altruix.log(f"Gagal update tombol purge: {e}", level=40)
    try:
        adjust_msg_id = ADJUST_PURGE_WAITING.get(chat_id)
        if adjust_msg_id and isinstance(adjust_msg_id, int) and userbot_client:
            await userbot_client.delete_messages(LOG_CHAT_ID, adjust_msg_id)
    except:
        pass
    ADJUST_PURGE_WAITING.pop(chat_id, None)

@Altruix.bot.on_callback_query(filters.regex(r"back_purge_(-?\d+)"))
@log_errors
async def back_purge_handler(c: Client, cb):
    data = cb.data
    chat_id = data.split("_")[-1]
    try:
        adjust_msg_id = ADJUST_PURGE_WAITING.get(chat_id)
        if adjust_msg_id and isinstance(adjust_msg_id, int):
            userbot_client = TELAYSPAM_TASKS.get(chat_id, {}).get("client")
            if userbot_client:
                await userbot_client.delete_messages(LOG_CHAT_ID, adjust_msg_id)
    except:
        pass
    ADJUST_PURGE_WAITING.pop(chat_id, None)
    await cb.answer("Kembali ke menu utama", show_alert=False)

@Altruix.bot.on_callback_query(filters.regex(r"cancel_adjust_purge_(-?\d+)"))
@log_errors
async def cancel_adjust_purge_handler(c: Client, cb):
    data = cb.data
    chat_id = data.split("_")[-1]
    try:
        adjust_msg_id = ADJUST_PURGE_WAITING.get(chat_id)
        if adjust_msg_id and isinstance(adjust_msg_id, int):
            userbot_client = TELAYSPAM_TASKS.get(chat_id, {}).get("client")
            if userbot_client:
                await userbot_client.delete_messages(LOG_CHAT_ID, adjust_msg_id)
    except:
        pass
    ADJUST_PURGE_WAITING.pop(chat_id, None)
    await cb.answer("Adjust purge dibatalkan", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"(stop|pause|resume|cek|recurring|delete_latest|delete_oldest|edit_last|edit_msglist|cancel_edit|cancel_editlast)_(-?\d+)"))
@log_errors
async def handle_task_control(c: Client, cb):
    data = cb.data
    action, chat_id = data.rsplit("_", 1)

    # Validasi chat terlebih dahulu
    target_chat = await get_chat_safe(c, int(chat_id))
    if not target_chat:
        if chat_id in TELAYSPAM_TASKS:
            TELAYSPAM_TASKS.pop(chat_id, None)
        if chat_id in COMPLETED_TASKS:
            COMPLETED_TASKS.pop(chat_id, None)
        await cb.answer("❌ Chat tidak valid atau userbot tidak memiliki akses. Task dihapus.", show_alert=True)
        Altruix.log(f"[CHAT_CLEANUP] Task dihapus karena chat {chat_id} tidak valid.", level=30)
        return

    chat_title = f"{target_chat.title}" if hasattr(target_chat, 'title') else (target_chat.first_name or target_chat.username or f"ID: {chat_id}")

    if action in ["stop", "pause", "resume", "cek"]:
        if chat_id not in TELAYSPAM_TASKS:
            await cb.answer("⚫️ Task tidak aktif di chat ini.", show_alert=True)
            return

    try:
        if action == "stop":
            TELAYSPAM_TASKS[chat_id]["running"] = False
            TELAYSPAM_TASKS[chat_id]["pause_event"].set()
            if "task" in TELAYSPAM_TASKS[chat_id]:
                TELAYSPAM_TASKS[chat_id]["task"].cancel()
            await cb.answer(f"🔴 Task distop di {chat_title}.", show_alert=True)
            userbot_client = TELAYSPAM_TASKS[chat_id]["client"]
            await send_log_message(f"🔴 Task distop di {chat_title}.", client=userbot_client)

        elif action == "pause":
            TELAYSPAM_TASKS[chat_id]["pause_event"].clear()
            await cb.answer(f"🟡 Task dipause di {chat_title}.", show_alert=True)
            userbot_client = TELAYSPAM_TASKS[chat_id]["client"]
            await send_log_message(f"🟡 Task dipause di {chat_title}.", client=userbot_client)

        elif action == "resume":
            TELAYSPAM_TASKS[chat_id]["pause_event"].set()
            await cb.answer(f"🟢 Task diresume di {chat_title}.", show_alert=True)
            userbot_client = TELAYSPAM_TASKS[chat_id]["client"]
            await send_log_message(f"🟢 Task diresume di {chat_title}.", client=userbot_client)

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
            userbot_client = TELAYSPAM_TASKS[chat_id]["client"]
            await send_log_message(f"{status_text}.", client=userbot_client)

        elif action == "recurring":
            if chat_id in TELAYSPAM_TASKS:
                await cb.answer("⚠️ Task masih berjalan, hentikan dulu sebelum recurring.", show_alert=True)
                return
            config = COMPLETED_TASKS.get(chat_id)
            if not config:
                await cb.answer("⚫️ Tidak ada task selesai untuk diulang di chat ini.", show_alert=True)
                return
            recurring_client = USER_CLIENT or BOT_CLIENT
            if not recurring_client:
                await cb.answer("❌ Tidak ada client yang tersedia untuk recurring.", show_alert=True)
                return
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
                await cb.answer(f"🔁 Task recurring dimulai ulang di {chat_title}.", show_alert=True)
            else:
                await cb.answer(f"❌ Gagal memulai recurring di {chat_title}.", show_alert=True)

        elif action == "delete_latest":
            try:
                delete_client = TELAYSPAM_TASKS[chat_id].get("client") if chat_id in TELAYSPAM_TASKS else USER_CLIENT
                if not delete_client:
                    await cb.answer("❌ Tidak ada client untuk menghapus pesan.", show_alert=True)
                    return
                messages = []
                async for message in delete_client.get_chat_history(int(chat_id), limit=30):
                    messages.append(message)
                if messages:
                    message_ids = [msg.id for msg in messages if msg.from_user and msg.from_user.id == delete_client.me.id]
                    if message_ids:
                        await delete_client.delete_messages(int(chat_id), message_ids)
                        del_suk = len(message_ids)
                        await asyncio.sleep(3)
                        await cb.answer(f"🗑️ Berhasil hapus {del_suk} pesan terbaru di {chat_title}.", show_alert=True)
                        await send_log_message(f"🗑️ Berhasil hapus {del_suk} pesan terbaru di {chat_title}.", client=delete_client)
                    else:
                        await cb.answer("⚫️ Tidak ada pesan dari userbot untuk dihapus.", show_alert=True)
                else:
                    await cb.answer("⚫️ Tidak ada pesan untuk dihapus.", show_alert=True)
            except Exception as err:
                await cb.answer(f"Error: {err}", show_alert=True)

        elif action == "delete_oldest":
            try:
                delete_client = TELAYSPAM_TASKS[chat_id].get("client") if chat_id in TELAYSPAM_TASKS else USER_CLIENT
                if not delete_client:
                    await cb.answer("❌ Tidak ada client untuk menghapus pesan.", show_alert=True)
                    return
                messages = []
                async for message in delete_client.get_chat_history(int(chat_id), limit=30):
                    messages.append(message)
                if messages:
                    message_ids = [msg.id for msg in messages if msg.from_user and msg.from_user.id == delete_client.me.id]
                    if message_ids:
                        await delete_client.delete_messages(int(chat_id), message_ids)
                        del_suk = len(message_ids)
                        await asyncio.sleep(3)
                        await cb.answer(f"🗑️ Berhasil hapus {del_suk} pesan terlama di {chat_title}.", show_alert=True)
                        await send_log_message(f"🗑️ Berhasil hapus {del_suk} pesan terlama di {chat_title}.", client=delete_client)
                    else:
                        await cb.answer("⚫️ Tidak ada pesan dari userbot untuk dihapus.", show_alert=True)
                else:
                    await cb.answer("⚫️ Tidak ada pesan untuk dihapus.", show_alert=True)
            except Exception as err:
                await cb.answer(f"Error: {err}", show_alert=True)

        elif action == "edit_last":
            try:
                edit_client = TELAYSPAM_TASKS[chat_id].get("client") if chat_id in TELAYSPAM_TASKS else USER_CLIENT
                if not edit_client:
                    await cb.answer("❌ Tidak ada client untuk edit pesan.", show_alert=True)
                    return
                messages = []
                async for message in edit_client.get_chat_history(int(chat_id), limit=1):
                    messages.append(message)
                    break
                if messages and messages[0].from_user and messages[0].from_user.id == edit_client.me.id:
                    last_msg_id = messages[0].id
                    old_text = messages[0].text or messages[0].caption or ""
                    notif_msg = (
                        f"✏️ Edit Last Message untuk {chat_title}\n"
                        f"Masukkan teks baru untuk mengedit pesan terakhir.\n"
                        f"Balas pesan ini dengan teks baru.\n"
                        f"Contoh balasan: Edited message here\n"
                        f"Klik 'Cancel' untuk membatalkan proses edit."
                    )
                    cancel_button = [[InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_editlast_{chat_id}")]]
                    edit_notif_msg = await send_log_message(
                        notif_msg,
                        reply_markup=InlineKeyboardMarkup(cancel_button),
                        client=edit_client
                    )
                    if edit_notif_msg:
                        EDIT_LASTMSG_WAITING[chat_id] = {
                            "target_chat_id": int(chat_id),
                            "last_msg_id": last_msg_id,
                            "old_text": old_text,
                            "notif_msg_id": edit_notif_msg.id,
                            "client": edit_client
                        }
                        await cb.answer(f"📝 Silakan masukkan teks baru untuk edit last msg di {chat_title}.", show_alert=True)
                    else:
                        await cb.answer("❌ Gagal membuat notifikasi edit.", show_alert=True)
                else:
                    await cb.answer("⚫️ Tidak ada pesan terakhir dari userbot untuk diedit.", show_alert=True)
            except Exception as edit_err:
                Altruix.log(f"Error saat memulai edit last msg: {edit_err}", level=40)
                await cb.answer(f"❌ Gagal memulai edit: {edit_err}", show_alert=True)

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
                return
            if config:
                old_msg_list = config["msg_list"]
                is_batch = config["is_batch"]
                notif_msg = (
                    f"✏️ Edit Message List untuk {chat_title}\n"
                    f"Masukkan pesan baru dengan format:\n"
                    f"- Untuk mode acak: [\"hello world\", \"hello dunia\", \"good morning\"]\n"
                    f"- Untuk mode batch: [(\"✅ hello world\", 50), (\"❇️ hello dunia\", 50)]\n"
                    f"Balas pesan ini dengan list pesan baru. Pastikan jumlah pesan atau total batch sesuai dengan count ({config['count']}).\n"
                    f"Contoh balasan: [\"hello world\", \"hello dunia\"]\n"
                    f"Klik 'Cancel' untuk membatalkan proses edit."
                )
                cancel_button = [[InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_edit_{chat_id}")]]
                send_client = task_client or USER_CLIENT or BOT_CLIENT
                if not send_client:
                    await cb.answer("❌ Tidak ada client untuk mengirim notifikasi.", show_alert=True)
                    return
                edit_notif_msg = await send_log_message(
                    notif_msg,
                    reply_markup=InlineKeyboardMarkup(cancel_button),
                    client=send_client
                )
                if edit_notif_msg:
                    EDIT_MSGLIST_WAITING[chat_id] = {
                        "config": config,
                        "was_running": was_running,
                        "notif_msg_id": edit_notif_msg.id,
                        "client": task_client
                    }
                    await cb.answer(f"📝 Silakan masukkan list pesan baru di {chat_title}.", show_alert=True)
                else:
                    await cb.answer("❌ Gagal membuat notifikasi edit.", show_alert=True)
            else:
                await cb.answer("⚫️ Tidak ada config untuk mengedit msg_list.", show_alert=True)

        elif action == "cancel_edit":
            if chat_id in EDIT_MSGLIST_WAITING:
                config = EDIT_MSGLIST_WAITING[chat_id]["config"]
                was_running = EDIT_MSGLIST_WAITING[chat_id]["was_running"]
                notif_msg_id = EDIT_MSGLIST_WAITING[chat_id]["notif_msg_id"]
                task_client = EDIT_MSGLIST_WAITING[chat_id].get("client")
                EDIT_MSGLIST_WAITING.pop(chat_id, None)
                await cb.answer(f"❌ Proses edit msg_list dibatalkan di {chat_title}.", show_alert=True)
                if task_client:
                    try:
                        await task_client.delete_messages(LOG_CHAT_ID, notif_msg_id)
                    except:
                        pass
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
                    if success:
                        await send_log_message(
                            f"✅ Task dikembalikan ke config default dan dimulai ulang di {chat_title}.",
                            client=task_client
                        )
            else:
                await cb.answer("⚫️ Tidak ada proses edit msg_list untuk dibatalkan.", show_alert=True)

        elif action == "cancel_editlast":
            if chat_id in EDIT_LASTMSG_WAITING:
                notif_msg_id = EDIT_LASTMSG_WAITING[chat_id]["notif_msg_id"]
                edit_client = EDIT_LASTMSG_WAITING[chat_id].get("client")
                EDIT_LASTMSG_WAITING.pop(chat_id, None)
                await cb.answer(f"❌ Proses edit last msg dibatalkan di {chat_title}.", show_alert=True)
                if edit_client:
                    try:
                        await edit_client.delete_messages(LOG_CHAT_ID, notif_msg_id)
                    except:
                        pass
            else:
                await cb.answer("⚫️ Tidak ada proses edit last msg untuk dibatalkan.", show_alert=True)

    except FloodWait as fwe:
        Altruix.log(f"FloodWaitError saat menangani aksi {action} untuk chat {chat_id}: Waiting for {fwe.value} seconds", level=30)
        await cb.answer(f"⚠️ Terlalu banyak permintaan. Tunggu {fwe.value} detik.", show_alert=True)
    except ChatWriteForbidden as cwe:
        Altruix.log(f"ChatWriteForbiddenError saat menangani aksi {action} untuk chat {chat_id}: Bot tidak memiliki izin", level=30)
        await cb.answer(f"❌ Bot tidak memiliki izin untuk melakukan aksi ini di {chat_title}.", show_alert=True)
    except Exception as err:
        Altruix.log(f"Error saat menangani aksi {action} untuk chat {chat_id}: {err}", level=40)
        await cb.answer(f"Error: {err}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"(cekall|stopall|recurringall|pauseall|resumeall)"))
@log_errors
async def handle_global_controls(c: Client, cb):
    data = cb.data
    if data == "cekall":
        if not TELAYSPAM_TASKS:
            await cb.answer("⚫️ Tidak ada task relayspam yang aktif.", show_alert=True)
            return
        status_list = []
        for chat_id, status in TELAYSPAM_TASKS.items():
            target_chat = await get_chat_safe(c, int(chat_id))
            if not target_chat:
                status_list.append(f"❓ Unknown chat (ID: {chat_id})")
                continue
            chat_title = f"{target_chat.title}" if hasattr(target_chat, 'title') else (target_chat.first_name or target_chat.username or f"ID: {chat_id}")
            if status["running"]:
                if status["pause_event"].is_set():
                    status_text = f"🔵 running di {chat_title}"
                else:
                    status_text = f"🟡 paused di {chat_title}"
            else:
                status_text = f"🔴 stopped di {chat_title}"
            status_list.append(status_text)
        output = "**Status Semua Task:**\n" + "\n".join(status_list)
        await cb.answer(output, show_alert=True)

    elif data == "stopall":
        if not TELAYSPAM_TASKS:
            await cb.answer("⚫️ Tidak ada task aktif untuk dihentikan.", show_alert=True)
            return
        stopped_count = 0
        for chat_id in list(TELAYSPAM_TASKS.keys()):
            TELAYSPAM_TASKS[chat_id]["running"] = False
            TELAYSPAM_TASKS[chat_id]["pause_event"].set()
            if "task" in TELAYSPAM_TASKS[chat_id]:
                TELAYSPAM_TASKS[chat_id]["task"].cancel()
            stopped_count += 1
        await cb.answer(f"🔴 Semua {stopped_count} task dihentikan.", show_alert=True)
        if TELAYSPAM_TASKS:
            first_chat_id = list(TELAYSPAM_TASKS.keys())[0]
            userbot_client = TELAYSPAM_TASKS[first_chat_id].get("client")
            if userbot_client:
                await send_log_message(f"🔴 Semua {stopped_count} task dihentikan.", client=userbot_client)

    elif data == "recurringall":
        if not COMPLETED_TASKS:
            await cb.answer("⚫️ Tidak ada task selesai untuk diulang.", show_alert=True)
            return
        restarted_count = 0
        for chat_id, config in list(COMPLETED_TASKS.items()):
            if chat_id in TELAYSPAM_TASKS:
                continue
            recurring_client = USER_CLIENT or BOT_CLIENT
            if not recurring_client:
                continue
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

    elif data == "pauseall":
        if not TELAYSPAM_TASKS:
            await cb.answer("⚫️ Tidak ada task aktif untuk dipause.", show_alert=True)
            return
        paused_count = 0
        for chat_id in list(TELAYSPAM_TASKS.keys()):
            if TELAYSPAM_TASKS[chat_id]["running"] and TELAYSPAM_TASKS[chat_id]["pause_event"].is_set():
                TELAYSPAM_TASKS[chat_id]["pause_event"].clear()
                paused_count += 1
        if paused_count == 0:
            await cb.answer("⚫️ Tidak ada task aktif yang sedang running untuk dipause.", show_alert=True)
        else:
            await cb.answer(f"🟡 Semua {paused_count} task dipause.", show_alert=True)

    elif data == "resumeall":
        if not TELAYSPAM_TASKS:
            await cb.answer("⚫️ Tidak ada task untuk diresume.", show_alert=True)
            return
        resumed_count = 0
        for chat_id in list(TELAYSPAM_TASKS.keys()):
            if TELAYSPAM_TASKS[chat_id]["running"] and not TELAYSPAM_TASKS[chat_id]["pause_event"].is_set():
                TELAYSPAM_TASKS[chat_id]["pause_event"].set()
                resumed_count += 1
        if resumed_count == 0:
            await cb.answer("⚫️ Tidak ada task yang dipause untuk diresume.", show_alert=True)
        else:
            await cb.answer(f"🟢 Semua {resumed_count} task diresume.", show_alert=True)

@Altruix.bot.on_message(filters.chat(LOG_CHAT_ID) & filters.incoming & filters.reply)
@log_errors
async def handle_msg_list_input(c: Client, m: Message):
    if m.reply_to_message:
        reply_msg = m.reply_to_message
        reply_msg_id = reply_msg.id
        if reply_msg_id in [waiting["notif_msg_id"] for waiting in EDIT_MSGLIST_WAITING.values()]:
            chat_id = next(cid for cid, waiting in EDIT_MSGLIST_WAITING.items() if waiting["notif_msg_id"] == reply_msg_id)
            config = EDIT_MSGLIST_WAITING[chat_id]["config"]
            was_running = EDIT_MSGLIST_WAITING[chat_id]["was_running"]
            task_client = EDIT_MSGLIST_WAITING[chat_id].get("client")
            is_batch = config["is_batch"]
            target_chat = await get_chat_safe(c, int(chat_id))
            chat_title = f"{target_chat.title}" if hasattr(target_chat, 'title') else (target_chat.first_name or target_chat.username or f"ID: {chat_id}")
            try:
                new_msg_list_str = m.text.strip()
                new_msg_list = ast.literal_eval(new_msg_list_str)
                if not isinstance(new_msg_list, list) or not new_msg_list:
                    raise ValueError("Input harus berupa list array yang valid.")
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
                old_msg_list = config["msg_list"]
                config["msg_list"] = new_msg_list
                COMPLETED_TASKS[chat_id] = config
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
        elif reply_msg_id in [waiting["notif_msg_id"] for waiting in EDIT_LASTMSG_WAITING.values()]:
            chat_id = next(cid for cid, waiting in EDIT_LASTMSG_WAITING.items() if waiting["notif_msg_id"] == reply_msg_id)
            target_chat_id = EDIT_LASTMSG_WAITING[chat_id]["target_chat_id"]
            last_msg_id = EDIT_LASTMSG_WAITING[chat_id]["last_msg_id"]
            old_text = EDIT_LASTMSG_WAITING[chat_id]["old_text"]
            edit_client = EDIT_LASTMSG_WAITING[chat_id].get("client")
            target_chat = await get_chat_safe(c, target_chat_id)
            chat_title = f"{target_chat.title}" if hasattr(target_chat, 'title') else (target_chat.first_name or target_chat.username or f"ID: {chat_id}")
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
    Altruix.log(f"[DEBUG] Loaded → {__plugin_name__} {PLUGIN_VERSION}", level=20)
except Exception as e:
    logger.info(f"[DEBUG] Loaded → {__plugin_name__} {PLUGIN_VERSION}")
