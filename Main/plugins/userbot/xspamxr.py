# for altruix
# Copyright (C) 2025-present by @AlphaXproject team
# Ported from Ultroid (xspamxr.txt) for Altruix UserBot
# GNU v3.0 License Agreement

import asyncio
import html
import re
import os
import logging
import ast
import shlex
from datetime import datetime
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, LinkPreviewOptions
from pyrogram.errors import (
    FloodWait, PeerIdInvalid, ChatWriteForbidden, MessageIdInvalid,
    MessageNotModified, MessageEmpty, SlowmodeWait, UserIdInvalid, 
    UserNotParticipant, MessageTooLong, ReactionInvalid
)
from Main import Altruix
from Main.core.decorators import log_errors
from Main.core.types.message import Message

# =============================================================================
# LOGGER KHUSUS PLUGIN
# =============================================================================
plugin_name = f"plugins/userbot/{os.path.basename(__file__)}"
__plugin_name__ = plugin_name if plugin_name else "xspamxr"
PLUGIN_VERSION = "v0.1.11.7.34.3:"

logger = logging.getLogger(f"{__plugin_name__}")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - [SET PLUGIN] - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# ─── LOGGER KHUSUS PLUGIN ───────────────────────────────────────────────
logger = logging.getLogger("xspam")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - [XSPAM] - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

logger.info("XSpam Plugin loaded successfully.")


# ─── GLOBAL STATE ───────────────────────────────────────────────────────
RELAY_SPAM_TASKS = {}  # {chat_id: task_data}
COMPLETED_TASKS = {}   # {chat_id: config}
PURGE_CONFIG = {}      # {chat_id: old_purge_value}
REACT_CONFIG = {}      # {chat_id: emo_react}
EDIT_MSGLIST_WAITING = {}  # {chat_id: data}
EDIT_LASTMSG_WAITING = {}  # {chat_id: data}
LOG_CHAT_ID = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))


# ─── FUNGSI UTILITAS ────────────────────────────────────────────────────
def parse_message_list(input_text: str):
    """Parse input seperti ["msg1", "msg2", ...] atau [("msg", 5), ...]"""
    try:
        input_text = input_text.replace("'", '"')
        parsed = ast.literal_eval(input_text)
        if isinstance(parsed, list):
            return parsed
    except (ValueError, SyntaxError):
        pass
    return [input_text]


async def get_target_chat(client, identifier: str):
    """Ambil chat object dari username atau ID."""
    try:
        if identifier.isdigit() or (identifier.startswith("-") and identifier[1:].isdigit()):
            chat_id = int(identifier)
        else:
            chat_id = identifier
        return await client.get_chat(chat_id)
    except PeerIdInvalid:
        return None


async def bulk_delete_messages(client, chat_id: int, message_ids: list):
    """Hapus banyak pesan sekaligus."""
    try:
        await client.delete_messages(chat_id=chat_id, message_ids=message_ids)
    except Exception as e:
        logger.warning(f"Failed to delete messages: {e}")


async def update_purge_button(notif_msg: Message, chat_id: int, purge_enabled: bool):
    """Update tombol purge di notifikasi."""
    try:
        clean_id = str(chat_id).replace("-100", "") if str(chat_id).startswith("-100") else str(chat_id)
        purge_text = "Purge: ON" if purge_enabled else "Purge: OFF"
        purge_data = f"toggle_purge_{chat_id}"
        
        buttons = []
        for row in notif_msg.reply_markup.inline_keyboard:
            new_row = []
            for btn in row:
                if btn.callback_data and "toggle_purge" in btn.callback_data:
                    new_row.append(InlineKeyboardButton(purge_text, callback_data=purge_data))
                else:
                    new_row.append(btn)
            buttons.append(new_row)
        
        await notif_msg.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        logger.error(f"Gagal update tombol purge: {e}")


# ─── FUNGSI UTAMA SPAM ──────────────────────────────────────────────────
async def spam_loop(client, target_chat, chat_id, msg_list, delays_possible, count, start_delay, stop_delay, step, x_msg, emot_react, is_batch, notif_msg_id=None):
    """Loop utama untuk mengirim spam messages."""
    try:
        sent_count = 0
        total_del_suk = 0
        total_del_ggl = 0
        
        for i in range(count):
            if not RELAY_SPAM_TASKS.get(chat_id, {}).get("running", False):
                logger.info(f"Task dihentikan untuk chat {chat_id}")
                await Altruix.bot.send_message(LOG_CHAT_ID, f"__Task dihentikan untuk chat {chat_id}__")
                break
                
            if RELAY_SPAM_TASKS[chat_id].get("paused", False):
                RELAY_SPAM_TASKS[chat_id]["pause_event"].clear()
                await RELAY_SPAM_TASKS[chat_id]["pause_event"].wait()
                
            # Purge old messages
            old_purge_val = RELAY_SPAM_TASKS[chat_id]["config"]["old_purge"]
            del_suk, del_ggl = 0, 0
            if old_purge_val > 0:
                try:
                    messages = await client.get_messages(target_chat, limit=old_purge_val * 2)
                    if messages:
                        my_messages = [msg for msg in messages if msg.from_user and msg.from_user.id == client.me.id][:old_purge_val]
                        message_ids = [msg.id for msg in my_messages]
                        if message_ids:
                            await client.delete_messages(target_chat, message_ids)
                            del_suk = len(message_ids)
                            await asyncio.sleep(3)
                        else:
                            del_suk = 0
                        del_ggl = old_purge_val - del_suk
                        total_del_suk += del_suk
                        total_del_ggl += del_ggl
                        await Altruix.bot.send_message(
                            LOG_CHAT_ID,
                            f"[HAPUS]: Berhasil hapus <code>{del_suk}</code> pesan lama, gagal <code>{del_ggl}</code> pesan.",
                            reply_to_message_id=x_msg.id if x_msg else None,
                            parse_mode="html"
                        )
                except Exception as del_err:
                    logger.error(f"Error saat menghapus pesan: {del_err}")
                    await Altruix.bot.send_message(LOG_CHAT_ID, f"Error hapus pesan: {del_err}", reply_to_message_id=x_msg.id if x_msg else None)
            
            if is_batch:
                for msg, b_count in msg_list:
                    for _ in range(b_count):
                        if not RELAY_SPAM_TASKS.get(chat_id, {}).get("running", False):
                            break
                            
                        random_delay = random.choice(delays_possible)
                        while True:
                            try:
                                sent_msg = await client.send_message(target_chat, msg)
                                sent_count += 1
                                react_status = "tidak ada"
                                
                                if emot_react and emot_react.lower() != "none":
                                    try:
                                        await asyncio.sleep(3)
                                        await sent_msg.react(emot_react)
                                        react_status = f"{emot_react} berhasil"
                                    except Exception as react_err:
                                        logger.error(f"Error saat menambahkan reaksi: {react_err}")
                                        react_status = f"{emot_react} gagal"
                                
                                remaining = count - sent_count
                                percentage = (sent_count / count) * 100 if count > 0 else 0
                                char_count = len(msg)
                                clean_chat_id = str(target_chat.id).replace("-100", "")
                                
                                progress_msg = (
                                    f"<b>Pesan terkirim</b>\n"
                                    f"Mode     : <code>{'Batch' if is_batch else 'Acak'}</code>\n"
                                    f"Delay    : <code>{random_delay:.2f}</code> detik\n"
                                    f"Sisa      : <code>{remaining}</code> pesan\n"
                                    f"Progress : <code>{percentage:.2f}%</code>\n"
                                    f"Length   : <code>{char_count}</code> karakter\n"
                                    f"React   : <code>{react_status}</code> <b><a href=\"https://t.me/c/{clean_chat_id}/{sent_msg.id}\">here</a></b>\n"
                                    f"Pesan    : <code>{msg}</code>"
                                )
                                
                                await Altruix.bot.send_message(
                                    LOG_CHAT_ID,
                                    progress_msg,
                                    reply_to_message_id=x_msg.id if x_msg else None,
                                    parse_mode="html",
                                    link_preview_options=LinkPreviewOptions(is_disabled=True)
                                )
                                
                                await asyncio.sleep(random_delay)
                                break
                            except SlowmodeWait as swe:
                                logger.warning(f"SlowModeWaitError: Waiting for {swe.value} seconds")
                                await Altruix.bot.send_message(LOG_CHAT_ID, f"** [ #ERROR ]** __SlowModeWaitError: Waiting for {swe.value} seconds__", reply_to_message_id=x_msg.id if x_msg else None)
                                await asyncio.sleep(swe.value)
                            except FloodWait as fwe:
                                logger.warning(f"FloodWaitError: Waiting for {fwe.value} seconds")
                                await Altruix.bot.send_message(LOG_CHAT_ID, f"** [ #ERROR ]** __FloodWaitError: Waiting for {fwe.value} seconds__", reply_to_message_id=x_msg.id if x_msg else None)
                                await asyncio.sleep(fwe.value)
                            except ChatWriteForbidden as cwe:
                                logger.warning(f"Bot muted in chat {chat_id}: Pausing task automatically.")
                                await Altruix.bot.send_message(LOG_CHAT_ID, f"** [ #ERROR ]** __UserBot muted in chat {target_chat.title}: Task paused automatically.__", reply_to_message_id=x_msg.id if x_msg else None)
                                RELAY_SPAM_TASKS[chat_id]["pause_event"].clear()
                                break
                            except Exception as send_err:
                                logger.error(f"Error saat mengirim pesan: {send_err}")
                                await Altruix.bot.send_message(LOG_CHAT_ID, f"** [ #ERROR ]** __Error saat mengirim pesan: {send_err}__", reply_to_message_id=x_msg.id if x_msg else None)
                                await asyncio.sleep(5)
            else:
                msg = random.choice(msg_list)
                random_delay = random.choice(delays_possible)
                while True:
                    try:
                        sent_msg = await client.send_message(target_chat, msg)
                        sent_count += 1
                        react_status = "tidak ada"
                        
                        if emot_react and emot_react.lower() != "none":
                            try:
                                await asyncio.sleep(3)
                                await sent_msg.react(emot_react)
                                react_status = f"{emot_react} berhasil"
                            except Exception as react_err:
                                logger.error(f"Error saat menambahkan reaksi: {react_err}")
                                react_status = f"{emot_react} gagal"
                        
                        remaining = count - sent_count
                        percentage = (sent_count / count) * 100 if count > 0 else 0
                        char_count = len(msg)
                        clean_chat_id = str(target_chat.id).replace("-100", "")
                        
                        progress_msg = (
                            f"<b>Pesan terkirim</b>\n"
                            f"Mode     : <code>{'Batch' if is_batch else 'Acak'}</code>\n"
                            f"Delay    : <code>{random_delay:.2f}</code> detik\n"
                            f"Sisa      : <code>{remaining}</code> pesan\n"
                            f"Progress : <code>{percentage:.2f}%</code>\n"
                            f"Length   : <code>{char_count}</code> karakter\n"
                            f"React   : <code>{react_status}</code> <b><a href=\"https://t.me/c/{clean_chat_id}/{sent_msg.id}\">here</a></b>\n"
                            f"Pesan    : <code>{msg}</code>"
                        )
                        
                        await Altruix.bot.send_message(
                            LOG_CHAT_ID,
                            progress_msg,
                            reply_to_message_id=x_msg.id if x_msg else None,
                            parse_mode="html",
                            link_preview_options=LinkPreviewOptions(is_disabled=True)
                        )
                        
                        await asyncio.sleep(random_delay)
                        break
                    except SlowmodeWait as swe:
                        logger.warning(f"SlowModeWaitError: Waiting for {swe.value} seconds")
                        await Altruix.bot.send_message(LOG_CHAT_ID, f"** [ #ERROR ]** __SlowModeWaitError: Waiting for {swe.value} seconds__", reply_to_message_id=x_msg.id if x_msg else None)
                        await asyncio.sleep(swe.value)
                    except FloodWait as fwe:
                        logger.warning(f"FloodWaitError: Waiting for {fwe.value} seconds")
                        await Altruix.bot.send_message(LOG_CHAT_ID, f"** [ #ERROR ]** __FloodWaitError: Waiting for {fwe.value} seconds__", reply_to_message_id=x_msg.id if x_msg else None)
                        await asyncio.sleep(fwe.value)
                    except ChatWriteForbidden as cwe:
                        logger.warning(f"Bot muted in chat {chat_id}: Pausing task automatically.")
                        await Altruix.bot.send_message(LOG_CHAT_ID, f"** [ #ERROR ]** __UserBot muted in chat {target_chat.title}: Task paused automatically.__", reply_to_message_id=x_msg.id if x_msg else None)
                        RELAY_SPAM_TASKS[chat_id]["pause_event"].clear()
                        break
                    except Exception as send_err:
                        logger.error(f"Error saat mengirim pesan: {send_err}")
                        await Altruix.bot.send_message(LOG_CHAT_ID, f"** [ #ERROR ]** __Error saat mengirim pesan: {send_err}__", reply_to_message_id=x_msg.id if x_msg else None)
                        await asyncio.sleep(5)
        
        if RELAY_SPAM_TASKS.get(chat_id, {}).get("running", False):
            completion_msg = (
                f"<b>[SELESAI]</b>: \n"
                f"Spam di <b>{target_chat.title}</b> telah selesai!\n"
                f"Terkirim <code>{sent_count}</code> pesan ({'batch' if is_batch else 'acak'}), delay acak [{start_delay}-{stop_delay}] dengan interval {step} detik,\n"
                f"Total sukses hapus <code>{total_del_suk}</code> pesan, total gagal hapus <code>{total_del_ggl}</code> pesan."
            )
            await Altruix.bot.send_message(
                LOG_CHAT_ID,
                completion_msg,
                reply_to_message_id=x_msg.id if x_msg else None,
                parse_mode="html",
                link_preview_options=LinkPreviewOptions(is_disabled=True)
            )
    except Exception as u:
        logger.error(f"Error in spam_loop: {u}")
        await Altruix.bot.send_message(LOG_CHAT_ID, f"__Error in spam_loop: {u}__")
    finally:
        if chat_id in RELAY_SPAM_TASKS:
            task_data = RELAY_SPAM_TASKS.pop(chat_id, None)
            if task_data and "config" in task_data:
                config = task_data["config"]
                COMPLETED_TASKS[chat_id] = config


async def start_relayspam(client, destination, start_delay, stop_delay, step, count, old_purge, emot_react, msg_list, is_batch):
    """Mulai task relayspam dengan konfigurasi lengkap."""
    try:
        if destination.isdigit() and len(destination) >= 10:
            destination = "-100" + destination
            
        target_chat = await client.get_chat(int(destination) if destination.replace("-", "").isdigit() else destination)
        chat_id = str(target_chat.id)
        
        if chat_id in RELAY_SPAM_TASKS:
            await Altruix.bot.send_message(LOG_CHAT_ID, f"**Error:** Task relayspam sudah berjalan di {target_chat.title}.")
            return False
            
        RELAY_SPAM_TASKS[chat_id] = {
            "running": True,
            "paused": False,
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
        RELAY_SPAM_TASKS[chat_id]["pause_event"].set()
        
        clean_id = str(target_chat.id).replace("-100", "") if str(target_chat.id).startswith("-100") else str(target_chat.id)
        notif_msg = (
            f"<b>Notifikasi Task</b>\n"
            f"Tugas spam akan segera dimulai.\n"
            f"✦ · · ──────✪────── · · ✦\n"
            f"<blockquote>\n"
            f"Tujuan     : <b><a href=\"https://t.me/c/{clean_id}/99999\">{target_chat.title}</a></b>\n"
            f"Chat_ID    : <code>-100{clean_id}</code>\n"
            f"Perintah   : <code>{Altruix.config.CMD_HANDLER}relayspam</code>\n"
            f"Mode       : <code>{'Batch' if is_batch else 'Acak'}</code>\n"
            f"Delay      : <code>{start_delay}</code> - <code>{stop_delay}</code>/step <code>{step}</code> detik\n"
            f"Jumlah     : <code>{count}</code> pesan\n"
            f"Hapus      : <code>{old_purge}</code> pesan\n"
            f"React      : <code>{emot_react if emot_react else 'tidak ada'}</code>\n"
            f"Pesan      : <code>{msg_list}</code>\n"
            f"</blockquote>"
        )
        
        tombol_baris = [
            [InlineKeyboardButton(f"-100{chat_id}", url=f"https://t.me/c/{clean_id}/99999")],
            [
                InlineKeyboardButton("Stop", callback_data=f"stop_{chat_id}"),
                InlineKeyboardButton("Pause", callback_data=f"pause_{chat_id}"),
                InlineKeyboardButton("Resume", callback_data=f"resume_{chat_id}")
            ],
            [
                InlineKeyboardButton("Check Status", callback_data=f"cek_{chat_id}"),
                InlineKeyboardButton("Recurring", callback_data=f"recurring_{chat_id}")
            ],
            [
                InlineKeyboardButton("Stop All", callback_data="stopall"),
                InlineKeyboardButton("Pause All", callback_data="pauseall"),
                InlineKeyboardButton("Resume All", callback_data="resumeall")
            ],
            [
                InlineKeyboardButton("Check All", callback_data="cekall"),
                InlineKeyboardButton("Recur All", callback_data="recurringall")
            ],
            [
                InlineKeyboardButton("Del Last 30", callback_data=f"delete_latest_{chat_id}"),
                InlineKeyboardButton("Del Old 30", callback_data=f"delete_oldest_{chat_id}")
            ],
            [
                InlineKeyboardButton("Edit Last Msg", callback_data=f"edit_last_{chat_id}"),
                InlineKeyboardButton("Edit Msg List", callback_data=f"edit_msglist_{chat_id}")
            ],
            [
                InlineKeyboardButton(f"{'Purge: ON' if old_purge > 0 else 'Purge: OFF'}", callback_data=f"toggle_purge_{chat_id}")
            ]
        ]
        
        x_msg = await Altruix.bot.send_message(
            LOG_CHAT_ID,
            notif_msg,
            reply_markup=InlineKeyboardMarkup(tombol_baris),
            parse_mode="html",
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
        
        RELAY_SPAM_TASKS[chat_id]["notif_msg"] = x_msg
        
        try:
            await x_msg.pin(disable_notification=True)
        except Exception as erpin:
            logger.error(f"#ERROR_PIN : `{erpin}`")
            pass
            
        delays_possible = []
        current = start_delay
        while current <= stop_delay:
            delays_possible.append(current)
            current += step
            
        if not delays_possible:
            raise ValueError("Tidak ada nilai delay yang mungkin dalam rentang yang diberikan.")
            
        task = asyncio.create_task(
            spam_loop(client, target_chat, chat_id, msg_list, delays_possible, count, start_delay, stop_delay, step, x_msg, emot_react, is_batch)
        )
        RELAY_SPAM_TASKS[chat_id]["task"] = task
        return True
        
    except Exception as u:
        logger.error(f"Error in start_relayspam: {u}")
        await Altruix.bot.send_message(LOG_CHAT_ID, f"__Error in start_relayspam: {u}__")
        RELAY_SPAM_TASKS.pop(chat_id, None)
        return False


# ─── HANDLER CALLBACK ───────────────────────────────────────────────────
@Altruix.bot.on_callback_query(filters.regex(r"^(stop|pause|resume|cek|recurring|delete_latest|delete_oldest|edit_last|edit_msglist|cancel_edit|cancel_editlast)_(-?\d+)"))
@log_errors
async def handle_task_control(c: Client, cb: CallbackQuery):
    action = cb.matches[0].group(1)
    chat_id = cb.matches[0].group(2)
    
    try:
        if int(chat_id) > 0:
            target_chat = await c.get_users(int(chat_id))
        else:
            target_chat = await c.get_chat(int(chat_id))
        chat_title = f"{target_chat.first_name or target_chat.title} (ID: {chat_id})" if hasattr(target_chat, 'first_name') or hasattr(target_chat, 'title') else "Unknown Chat"
    except (ValueError, TypeError, UserIdInvalid, PeerIdInvalid) as err:
        chat_title = f"Unknown Chat (ID: {chat_id})"
        logger.error(f"Error resolusi entity untuk chat_id {chat_id}: {err}")
    
    try:
        if action in ["stop", "pause", "resume", "cek"]:
            if chat_id not in RELAY_SPAM_TASKS:
                await cb.answer("⚫️ Task tidak aktif di chat ini.", show_alert=True)
                await Altruix.bot.send_message(LOG_CHAT_ID, f"⚫️ Task tidak aktif di chat ini.")
                return
                
        if action == "stop":
            RELAY_SPAM_TASKS[chat_id]["running"] = False
            RELAY_SPAM_TASKS[chat_id]["pause_event"].set()
            if "task" in RELAY_SPAM_TASKS[chat_id]:
                RELAY_SPAM_TASKS[chat_id]["task"].cancel()
            await cb.answer(f"🔴 Task distop di {chat_title}.", show_alert=True)
            await Altruix.bot.send_message(LOG_CHAT_ID, f"🔴 Task distop di {chat_title}.")
            
        elif action == "pause":
            RELAY_SPAM_TASKS[chat_id]["pause_event"].clear()
            await cb.answer(f"🟡 Task dipause di {chat_title}.", show_alert=True)
            await Altruix.bot.send_message(LOG_CHAT_ID, f"🟡 Task dipause di {chat_title}.")
            
        elif action == "resume":
            RELAY_SPAM_TASKS[chat_id]["pause_event"].set()
            await cb.answer(f"🟢 Task diresume di {chat_title}.", show_alert=True)
            await Altruix.bot.send_message(LOG_CHAT_ID, f"🟢 Task diresume di {chat_title}.")
            
        elif action == "cek":
            status = RELAY_SPAM_TASKS[chat_id]
            if status["running"]:
                if status["pause_event"].is_set():
                    status_text = f"🔵 Task dirunning di {chat_title} (running)."
                else:
                    status_text = f"🟡 Task dipause di {chat_title} (paused)."
            else:
                status_text = f"🔴 Task distop di {chat_title} (stopped)."
            await cb.answer(status_text, show_alert=True)
            await Altruix.bot.send_message(LOG_CHAT_ID, f"{status_text}.")
            
        elif action == "recurring":
            if chat_id in RELAY_SPAM_TASKS:
                await cb.answer("⚠️ Task masih berjalan, hentikan dulu sebelum recurring.", show_alert=True)
                await Altruix.bot.send_message(LOG_CHAT_ID, f"⚠️ Task masih berjalan di {chat_title}, hentikan dulu.")
                return
                
            config = COMPLETED_TASKS.get(chat_id)
            if not config:
                await cb.answer("⚫️ Tidak ada task selesai untuk diulang di chat ini.", show_alert=True)
                await Altruix.bot.send_message(LOG_CHAT_ID, f"⚫️ Tidak ada task selesai untuk diulang di {chat_title}.")
                return
                
            success = await start_relayspam(
                c,  # Menggunakan client bot untuk operasi
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
                await Altruix.bot.send_message(LOG_CHAT_ID, f"🔁 Task recurring dimulai ulang di {chat_title}.")
            else:
                await cb.answer(f"❌ Gagal memulai recurring di {chat_title}.", show_alert=True)
                await Altruix.bot.send_message(LOG_CHAT_ID, f"❌ Gagal memulai recurring di {chat_title}.")
                
        elif action == "delete_latest":
            try:
                messages = await c.get_messages(target_chat.id if hasattr(target_chat, 'id') else int(chat_id), limit=30, reverse=False)
                if messages:
                    message_ids = [msg.id for msg in messages if msg.from_user and msg.from_user.id == c.me.id]
                    if message_ids:
                        await c.delete_messages(target_chat.id if hasattr(target_chat, 'id') else int(chat_id), message_ids)
                        del_suk = len(message_ids)
                        await asyncio.sleep(3)
                        await cb.answer(f"🗑️ Berhasil hapus {del_suk} pesan terbaru di {chat_title}.", show_alert=True)
                        await Altruix.bot.send_message(LOG_CHAT_ID, f"🗑️ Berhasil hapus {del_suk} pesan terbaru di {chat_title}.")
                    else:
                        await cb.answer("⚫️ Tidak ada pesan dari userbot untuk dihapus.", show_alert=True)
                        await Altruix.bot.send_message(LOG_CHAT_ID, f"⚫️ Tidak ada pesan dari userbot untuk dihapus di {chat_title}.")
                else:
                    await cb.answer("⚫️ Tidak ada pesan untuk dihapus.", show_alert=True)
                    await Altruix.bot.send_message(LOG_CHAT_ID, f"⚫️ Tidak ada pesan untuk dihapus di {chat_title}.")
            except Exception as err:
                logger.error(f"Error saat menghapus pesan terbaru: {err}")
                await cb.answer(f"❌ Gagal hapus pesan terbaru: {err}", show_alert=True)
                await Altruix.bot.send_message(LOG_CHAT_ID, f"❌ Gagal hapus pesan terbaru di {chat_title}: {err}")
                
        elif action == "delete_oldest":
            try:
                messages = await c.get_messages(target_chat.id if hasattr(target_chat, 'id') else int(chat_id), limit=30, reverse=True)
                if messages:
                    message_ids = [msg.id for msg in messages if msg.from_user and msg.from_user.id == c.me.id]
                    if message_ids:
                        await c.delete_messages(target_chat.id if hasattr(target_chat, 'id') else int(chat_id), message_ids)
                        del_suk = len(message_ids)
                        await asyncio.sleep(3)
                        await cb.answer(f"🗑️ Berhasil hapus {del_suk} pesan terlama di {chat_title}.", show_alert=True)
                        await Altruix.bot.send_message(LOG_CHAT_ID, f"🗑️ Berhasil hapus {del_suk} pesan terlama di {chat_title}.")
                    else:
                        await cb.answer("⚫️ Tidak ada pesan dari userbot untuk dihapus.", show_alert=True)
                        await Altruix.bot.send_message(LOG_CHAT_ID, f"⚫️ Tidak ada pesan dari userbot untuk dihapus di {chat_title}.")
                else:
                    await cb.answer("⚫️ Tidak ada pesan untuk dihapus.", show_alert=True)
                    await Altruix.bot.send_message(LOG_CHAT_ID, f"⚫️ Tidak ada pesan untuk dihapus di {chat_title}.")
            except Exception as err:
                logger.error(f"Error saat menghapus pesan terlama: {err}")
                await cb.answer(f"❌ Gagal hapus pesan terlama: {err}", show_alert=True)
                await Altruix.bot.send_message(LOG_CHAT_ID, f"❌ Gagal hapus pesan terlama di {chat_title}: {err}")
                
        elif action == "edit_last":
            try:
                messages = await c.get_messages(target_chat.id if hasattr(target_chat, 'id') else int(chat_id), limit=1, reverse=False)
                if messages and messages[0].from_user and messages[0].from_user.id == c.me.id:
                    last_msg_id = messages[0].id
                    old_text = messages[0].text
                    
                    notif_msg = (
                        f"✏️ <b>Edit Last Message untuk {chat_title}</b>\n"
                        f"Masukkan teks baru untuk mengedit pesan terakhir.\n"
                        f"Balas pesan ini dengan teks baru.\n"
                        f"Contoh balasan: <code>Edited message here</code>\n"
                        f"Klik 'Cancel' untuk membatalkan proses edit."
                    )
                    cancel_button = [[InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_editlast_{chat_id}")]]
                    
                    edit_notif_msg = await Altruix.bot.send_message(
                        LOG_CHAT_ID,
                        notif_msg,
                        reply_markup=InlineKeyboardMarkup(cancel_button),
                        parse_mode="html",
                        link_preview_options=LinkPreviewOptions(is_disabled=True)
                    )
                    
                    EDIT_LASTMSG_WAITING[chat_id] = {
                        "target_chat": target_chat,
                        "last_msg_id": last_msg_id,
                        "old_text": old_text,
                        "notif_msg_id": edit_notif_msg.id
                    }
                    await cb.answer(f"📝 Silakan masukkan teks baru untuk edit last msg di {chat_title}.", show_alert=True)
                else:
                    await cb.answer("⚫️ Tidak ada pesan terakhir dari userbot untuk diedit.", show_alert=True)
                    await Altruix.bot.send_message(LOG_CHAT_ID, f"⚫️ Tidak ada pesan terakhir untuk diedit di {chat_title}.")
            except Exception as edit_err:
                logger.error(f"Error saat memulai edit last msg: {edit_err}")
                await cb.answer(f"❌ Gagal memulai edit: {edit_err}", show_alert=True)
                await Altruix.bot.send_message(LOG_CHAT_ID, f"❌ Gagal memulai edit last msg di {chat_title}: {edit_err}")
                
        elif action == "edit_msglist":
            config = None
            was_running = False
            if chat_id in RELAY_SPAM_TASKS:
                was_running = True
                RELAY_SPAM_TASKS[chat_id]["running"] = False
                RELAY_SPAM_TASKS[chat_id]["pause_event"].set()
                if "task" in RELAY_SPAM_TASKS[chat_id]:
                    RELAY_SPAM_TASKS[chat_id]["task"].cancel()
                config = RELAY_SPAM_TASKS[chat_id].get("config")
                RELAY_SPAM_TASKS.pop(chat_id, None)
            elif chat_id in COMPLETED_TASKS:
                config = COMPLETED_TASKS.get(chat_id)
            else:
                await cb.answer("⚫️ Tidak ada task aktif atau selesai untuk mengedit msg_list.", show_alert=True)
                await Altruix.bot.send_message(LOG_CHAT_ID, f"⚫️ Tidak ada task untuk mengedit msg_list di {chat_title}.")
                return
                
            if config:
                old_msg_list = config["msg_list"]
                is_batch = config["is_batch"]
                notif_msg = (
                    f"✏️ <b>Edit Message List untuk {chat_title}</b>\n"
                    f"Masukkan pesan baru dengan format:\n"
                    f"- Untuk mode acak: <code>[\"hello world\", \"hello dunia\", \"good morning\"]</code>\n"
                    f"- Untuk mode batch: <code>[(\"✅ hello world\", 50), (\"❇️ hello dunia\", 50)]</code>\n"
                    f"Balas pesan ini dengan list pesan baru. Pastikan jumlah pesan atau total batch sesuai dengan count ({config['count']}).\n"
                    f"Contoh balasan: <code>[\"hello world\", \"hello dunia\"]</code>\n"
                    f"Klik 'Cancel' untuk membatalkan proses edit."
                )
                cancel_button = [[InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_edit_{chat_id}")]]
                
                edit_notif_msg = await Altruix.bot.send_message(
                    LOG_CHAT_ID,
                    notif_msg,
                    reply_markup=InlineKeyboardMarkup(cancel_button),
                    parse_mode="html",
                    link_preview_options=LinkPreviewOptions(is_disabled=True)
                )
                
                EDIT_MSGLIST_WAITING[chat_id] = {
                    "config": config,
                    "was_running": was_running,
                    "notif_msg_id": edit_notif_msg.id
                }
                await cb.answer(f"📝 Silakan masukkan list pesan baru di {chat_title}.", show_alert=True)
            else:
                await cb.answer("⚫️ Tidak ada config untuk mengedit msg_list.", show_alert=True)
                await Altruix.bot.send_message(LOG_CHAT_ID, f"⚫️ Tidak ada config untuk mengedit msg_list di {chat_title}.")
                
        elif action == "cancel_edit":
            if chat_id in EDIT_MSGLIST_WAITING:
                data = EDIT_MSGLIST_WAITING[chat_id]
                config = data["config"]
                was_running = data["was_running"]
                notif_msg_id = data["notif_msg_id"]
                
                EDIT_MSGLIST_WAITING.pop(chat_id, None)
                await cb.answer(f"❌ Proses edit msg_list dibatalkan di {chat_title}.", show_alert=True)
                await Altruix.bot.send_message(
                    LOG_CHAT_ID,
                    f"❌ Proses edit msg_list dibatalkan di {chat_title}.",
                    reply_to_message_id=notif_msg_id,
                    parse_mode="html",
                    link_preview_options=LinkPreviewOptions(is_disabled=True)
                )
                
                if was_running:
                    success = await start_relayspam(
                        c,  # Menggunakan client bot
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
                        await Altruix.bot.send_message(
                            LOG_CHAT_ID,
                            f"✅ Task dikembalikan ke config default dan dimulai ulang di {chat_title}.",
                            parse_mode="html",
                            link_preview_options=LinkPreviewOptions(is_disabled=True)
                        )
                    else:
                        await Altruix.bot.send_message(
                            LOG_CHAT_ID,
                            f"❌ Gagal memulai ulang task di {chat_title}.",
                            parse_mode="html",
                            link_preview_options=LinkPreviewOptions(is_disabled=True)
                        )
            else:
                await cb.answer("⚫️ Tidak ada proses edit msg_list untuk dibatalkan.", show_alert=True)
                await Altruix.bot.send_message(LOG_CHAT_ID, f"⚫️ Tidak ada proses edit msg_list untuk dibatalkan di {chat_title}.")
                
        elif action == "cancel_editlast":
            if chat_id in EDIT_LASTMSG_WAITING:
                data = EDIT_LASTMSG_WAITING[chat_id]
                notif_msg_id = data["notif_msg_id"]
                
                EDIT_LASTMSG_WAITING.pop(chat_id, None)
                await cb.answer(f"❌ Proses edit last msg dibatalkan di {chat_title}.", show_alert=True)
                await Altruix.bot.send_message(
                    LOG_CHAT_ID,
                    f"❌ Proses edit last msg dibatalkan di {chat_title}.",
                    reply_to_message_id=notif_msg_id,
                    parse_mode="html",
                    link_preview_options=LinkPreviewOptions(is_disabled=True)
                )
            else:
                await cb.answer("⚫️ Tidak ada proses edit last msg untuk dibatalkan.", show_alert=True)
                await Altruix.bot.send_message(LOG_CHAT_ID, f"⚫️ Tidak ada proses edit last msg untuk dibatalkan di {chat_title}.")
                
    except FloodWait as fwe:
        logger.error(f"FloodWaitError saat menangani aksi {action} untuk chat {chat_id}: Waiting for {fwe.value} seconds")
        await cb.answer(f"⚠️ Terlalu banyak permintaan. Tunggu {fwe.value} detik.", show_alert=True)
        await Altruix.bot.send_message(LOG_CHAT_ID, f"⚠️ **FloodWaitError:** Tunggu {fwe.value} detik untuk aksi {action} di {chat_title}.")
    except ChatWriteForbidden as cwe:
        logger.error(f"ChatWriteForbiddenError saat menangani aksi {action} untuk chat {chat_id}: Bot tidak memiliki izin")
        await cb.answer(f"❌ Bot tidak memiliki izin untuk melakukan aksi ini di {chat_title}.", show_alert=True)
        await Altruix.bot.send_message(LOG_CHAT_ID, f"❌ **ChatWriteForbiddenError:** Bot tidak memiliki izin untuk aksi {action} di {chat_title}.")
    except Exception as err:
        logger.error(f"Error saat menangani aksi {action} untuk chat {chat_id}: {err}")
        await cb.answer(f"Error: {err}", show_alert=True)
        await Altruix.bot.send_message(LOG_CHAT_ID, f"⚠️ **Error :** {err}")


@Altruix.bot.on_callback_query(filters.regex(r"^(cekall|stopall|recurringall|pauseall|resumeall)"))
@log_errors
async def handle_global_controls(c: Client, cb: CallbackQuery):
    data = cb.data
    
    if data == "cekall":
        if not RELAY_SPAM_TASKS:
            await cb.answer("⚫️ Tidak ada task relayspam yang aktif.", show_alert=True)
            await Altruix.bot.send_message(LOG_CHAT_ID, f"⚫️ Tidak ada task relayspam yang aktif.")
            return
            
        status_list = []
        for chat_id, status in RELAY_SPAM_TASKS.items():
            try:
                if int(chat_id) > 0:
                    target_chat = await c.get_users(int(chat_id))
                else:
                    target_chat = await c.get_chat(int(chat_id))
                chat_title = f"{target_chat.first_name or target_chat.title} (ID: {chat_id})" if hasattr(target_chat, 'first_name') or hasattr(target_chat, 'title') else "Unknown Chat"
                
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
                await Altruix.bot.send_message(LOG_CHAT_ID, f"Error: {err}")
                
        output = "**Status Semua Task:**\n" + "\n".join(status_list)
        await cb.answer(output, show_alert=True)
        await Altruix.bot.send_message(LOG_CHAT_ID, f"{output}")
        
    elif data == "stopall":
        if not RELAY_SPAM_TASKS:
            await cb.answer("⚫️ Tidak ada task aktif untuk dihentikan.", show_alert=True)
            await Altruix.bot.send_message(LOG_CHAT_ID, "⚫️ Tidak ada task aktif untuk dihentikan.")
            return
            
        stopped_count = 0
        for chat_id in list(RELAY_SPAM_TASKS.keys()):
            RELAY_SPAM_TASKS[chat_id]["running"] = False
            RELAY_SPAM_TASKS[chat_id]["pause_event"].set()
            if "task" in RELAY_SPAM_TASKS[chat_id]:
                RELAY_SPAM_TASKS[chat_id]["task"].cancel()
            stopped_count += 1
            
        await cb.answer(f"🔴 Semua {stopped_count} task dihentikan.", show_alert=True)
        await Altruix.bot.send_message(LOG_CHAT_ID, f"🔴 Semua {stopped_count} task dihentikan.")
        
    elif data == "recurringall":
        if not COMPLETED_TASKS:
            await cb.answer("⚫️ Tidak ada task selesai untuk diulang.", show_alert=True)
            await Altruix.bot.send_message(LOG_CHAT_ID, "⚫️ Tidak ada task selesai untuk diulang.")
            return
            
        restarted_count = 0
        for chat_id, config in list(COMPLETED_TASKS.items()):
            if chat_id in RELAY_SPAM_TASKS:
                continue
                
            success = await start_relayspam(
                c,  # Menggunakan client bot
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
        await Altruix.bot.send_message(LOG_CHAT_ID, f"🔁 {restarted_count} task recurring dimulai ulang.")
        
    elif data == "pauseall":
        if not RELAY_SPAM_TASKS:
            await cb.answer("⚫️ Tidak ada task aktif untuk dipause.", show_alert=True)
            await Altruix.bot.send_message(LOG_CHAT_ID, "⚫️ Tidak ada task aktif untuk dipause.")
            return
            
        paused_chats = []
        paused_count = 0
        for chat_id in list(RELAY_SPAM_TASKS.keys()):
            if RELAY_SPAM_TASKS[chat_id]["running"] and RELAY_SPAM_TASKS[chat_id]["pause_event"].is_set():
                try:
                    if int(chat_id) > 0:
                        target_chat = await c.get_users(int(chat_id))
                    else:
                        target_chat = await c.get_chat(int(chat_id))
                    chat_title = f"{target_chat.first_name or target_chat.title} (ID: {chat_id})" if hasattr(target_chat, 'first_name') or hasattr(target_chat, 'title') else "Unknown Chat"
                    
                    RELAY_SPAM_TASKS[chat_id]["pause_event"].clear()
                    paused_count += 1
                    paused_chats.append(f"🟡 Paused di {chat_title}")
                except Exception as err:
                    logger.error(f"Error resolusi chat {chat_id} untuk pauseall: {err}")
                    paused_chats.append(f"❓ Paused di Unknown Chat (ID: {chat_id})")
                    RELAY_SPAM_TASKS[chat_id]["pause_event"].clear()
                    paused_count += 1
                    
        if paused_count == 0:
            await cb.answer("⚫️ Tidak ada task aktif yang sedang running untuk dipause.", show_alert=True)
            await Altruix.bot.send_message(LOG_CHAT_ID, "⚫️ Tidak ada task aktif yang sedang running untuk dipause.")
        else:
            output = f"🟡 Semua {paused_count} task dipause:\n" + "\n".join(paused_chats)
            await cb.answer(f"🟡 Semua {paused_count} task dipause.", show_alert=True)
            await Altruix.bot.send_message(LOG_CHAT_ID, output, parse_mode="html")
            
    elif data == "resumeall":
        if not RELAY_SPAM_TASKS:
            await cb.answer("⚫️ Tidak ada task untuk diresume.", show_alert=True)
            await Altruix.bot.send_message(LOG_CHAT_ID, "⚫️ Tidak ada task untuk diresume.")
            return
            
        resumed_chats = []
        resumed_count = 0
        for chat_id in list(RELAY_SPAM_TASKS.keys()):
            if RELAY_SPAM_TASKS[chat_id]["running"] and not RELAY_SPAM_TASKS[chat_id]["pause_event"].is_set():
                try:
                    if int(chat_id) > 0:
                        target_chat = await c.get_users(int(chat_id))
                    else:
                        target_chat = await c.get_chat(int(chat_id))
                    chat_title = f"{target_chat.first_name or target_chat.title} (ID: {chat_id})" if hasattr(target_chat, 'first_name') or hasattr(target_chat, 'title') else "Unknown Chat"
                    
                    RELAY_SPAM_TASKS[chat_id]["pause_event"].set()
                    resumed_count += 1
                    resumed_chats.append(f"🟢 Resumed di {chat_title}")
                except Exception as err:
                    logger.error(f"Error resolusi chat {chat_id} untuk resumeall: {err}")
                    resumed_chats.append(f"❓ Resumed di Unknown Chat (ID: {chat_id})")
                    RELAY_SPAM_TASKS[chat_id]["pause_event"].set()
                    resumed_count += 1
                    
        if resumed_count == 0:
            await cb.answer("⚫️ Tidak ada task yang dipause untuk diresume.", show_alert=True)
            await Altruix.bot.send_message(LOG_CHAT_ID, "⚫️ Tidak ada task yang dipause untuk diresume.")
        else:
            output = f"🟢 Semua {resumed_count} task diresume:\n" + "\n".join(resumed_chats)
            await cb.answer(f"🟢 Semua {resumed_count} task diresume.", show_alert=True)
            await Altruix.bot.send_message(LOG_CHAT_ID, output, parse_mode="html")


# ─── HANDLER REPLY ──────────────────────────────────────────────────────
@Altruix.bot.on_message(filters.reply & filters.user(Altruix.auth_users) & filters.chat(LOG_CHAT_ID))
@log_errors
async def handle_msg_list_input(c: Client, m: Message):
    if not m.reply_to_message:
        return
        
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
            if int(chat_id) > 0:
                target_chat = await c.get_users(int(chat_id))
            else:
                target_chat = await c.get_chat(int(chat_id))
            chat_title = f"{target_chat.first_name or target_chat.title} (ID: {chat_id})" if hasattr(target_chat, 'first_name') or hasattr(target_chat, 'title') else "Unknown Chat"
        except (ValueError, TypeError, UserIdInvalid, PeerIdInvalid) as err:
            chat_title = f"Unknown Chat (ID: {chat_id})"
            logger.error(f"Error resolusi entity untuk chat_id {chat_id}: {err}")
            
        try:
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
                    
            old_msg_list = config["msg_list"]
            config["msg_list"] = new_msg_list
            COMPLETED_TASKS[chat_id] = config
            
            success = await start_relayspam(
                c,  # Menggunakan client bot
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
                response_msg = (
                    f"✏️ Berhasil edit msg_list di {chat_title}:\n"
                    f"Sebelum: <code>{old_msg_list}</code>\n"
                    f"Sesudah: <code>{new_msg_list}</code>\n"
                    f"Task {'dihentikan dan ' if was_running else ''}dimulai ulang dengan msg_list baru."
                )
                await m.reply(response_msg, parse_mode="html")
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
            logger.error(f"Error saat memproses input msg_list: {err}")
            await m.reply(f"⚠️ **Error:** {err}", parse_mode="html")
            
    # Cek untuk edit last msg
    elif reply_msg_id in [waiting["notif_msg_id"] for waiting in EDIT_LASTMSG_WAITING.values()]:
        chat_id = next(cid for cid, waiting in EDIT_LASTMSG_WAITING.items() if waiting["notif_msg_id"] == reply_msg_id)
        data = EDIT_LASTMSG_WAITING[chat_id]
        target_chat = data["target_chat"]
        last_msg_id = data["last_msg_id"]
        old_text = data["old_text"]
        
        try:
            chat_title = f"{target_chat.first_name or target_chat.title} (ID: {chat_id})" if hasattr(target_chat, 'first_name') or hasattr(target_chat, 'title') else "Unknown Chat"
        except Exception as err:
            chat_title = f"Unknown Chat (ID: {chat_id})"
            logger.error(f"Error resolusi entity untuk chat_id {chat_id}: {err}")
            
        try:
            new_text = m.text.strip()
            if not new_text:
                raise ValueError("Teks baru tidak boleh kosong.")
                
            await c.edit_message_text(target_chat.id if hasattr(target_chat, 'id') else int(chat_id), last_msg_id, new_text)
            await asyncio.sleep(1)
            
            response_msg = (
                f"✏️ Berhasil edit last msg di {chat_title}:\n"
                f"Sebelum: <code>{old_text}</code>\n"
                f"Sesudah: <code>{new_text}</code>"
            )
            await m.reply(response_msg, parse_mode="html")
            EDIT_LASTMSG_WAITING.pop(chat_id, None)
        except (ValueError, SyntaxError) as err:
            await m.reply(
                f"**Error Parsing Input:** {err}\n"
                f"Masukkan teks biasa sebagai balasan.",
                parse_mode="html"
            )
        except Exception as err:
            logger.error(f"Error saat memproses input last msg: {err}")
            await m.reply(f"⚠️ **Error:** {err}", parse_mode="html")


# ─── HANDLER COMMAND ────────────────────────────────────────────────────
@Altruix.register_on_cmd(
    ["relayspam", "xspam"],
    cmd_help={
        "help": "Relay spam messages to a chat with delay control.",
        "example": ".relayspam -1001234567890 1 5 1 10 5 👋 [\"Hello\", \"World\"]",
        "user_args": [
            {"arg": "chat", "help": "Target chat ID or username", "requires_input": True},
            {"arg": "start_delay", "help": "Delay before starting (seconds)", "requires_input": True},
            {"arg": "stop_delay", "help": "Delay between messages (seconds)", "requires_input": True},
            {"arg": "step", "help": "Step increment for delay", "requires_input": True},
            {"arg": "count", "help": "Number of times to repeat", "requires_input": True},
            {"arg": "purge_count", "help": "Number of old messages to delete (0 = off)", "requires_input": True},
            {"arg": "react_emoji", "help": "Emoji to react (or 'none')", "requires_input": True},
            {"arg": "messages", "help": "List of messages to spam", "requires_input": True},
        ],
    },
)
@log_errors
async def relayspam_handler(c: Client, m: Message):
    raw_input = m.raw_user_input
    
    if not raw_input:
        return await m.handle_message("INPUT_REQUIRED")
        
    try:
        # Split input
        parts = shlex.split(raw_input)
        if len(parts) < 8:
            return await m.handle_message("❌ Format salah. Gunakan: .relayspam <chat> <start> <stop> <step> <count> <purge> <react> [\"msg1\", ...]")
            
        chat_identifier = parts[0]
        start_delay = float(parts[1])
        stop_delay = float(parts[2])
        step_delay = float(parts[3])
        count = int(parts[4])
        purge_count = int(parts[5])
        react_emoji = parts[6] if parts[6].lower() != "none" else ""
        
        # Ambil msg_list dari sisa input
        msg_list_str = " ".join(parts[7:])
        messages = parse_message_list(msg_list_str)
        
        if not messages:
            return await m.handle_message("❌ Tidak ada pesan untuk di-spam.")
            
        target_chat = await get_target_chat(c, chat_identifier)
        if not target_chat:
            return await m.handle_message("❌ Chat tidak ditemukan.")
            
        chat_id = target_chat.id
        task_key = f"{m.from_user.id}_{chat_id}"
        
        if task_key in RELAY_SPAM_TASKS:
            return await m.handle_message("❌ Task sedang berjalan. Batalkan dulu.")
            
        # Cek apakah mode batch
        is_batch = all(isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str) and isinstance(item[1], int) for item in messages)
        if is_batch:
            total_batch_count = sum(b_count for _, b_count in messages)
            if total_batch_count != count:
                return await m.handle_message(f"❌ Total jumlah batch ({total_batch_count}) tidak sesuai dengan count ({count}).")
                
        # Simpan konfig ke global
        config = {
            "destination": chat_id,
            "start_delay": start_delay,
            "stop_delay": stop_delay,
            "step": step_delay,
            "count": count,
            "old_purge": purge_count,
            "emot_react": react_emoji,
            "msg_list": messages,
            "is_batch": is_batch,
        }
        
        RELAY_SPAM_TASKS[chat_id] = {
            "running": True,
            "paused": False,
            "pause_event": asyncio.Event(),
            "config": config,
        }
        PURGE_CONFIG[chat_id] = purge_count
        REACT_CONFIG[chat_id] = react_emoji
        
        # Kirim notifikasi awal ke LOG_CHAT_ID
        clean_id = str(chat_id).replace("-100", "") if str(chat_id).startswith("-100") else str(chat_id)
        notif_msg = await Altruix.bot.send_message(
            LOG_CHAT_ID,
            f"<b>🚀 RelaySpam Started</b>\n"
            f"• Chat: <a href='https://t.me/c/{clean_id}/99999'>{html.escape(target_chat.title)}</a>\n"
            f"• ID: <code>{chat_id}</code>\n"
            f"• Mode: <code>{'Batch' if is_batch else 'Random'}</code>\n"
            f"• Delay: <code>{start_delay}</code>s - <code>{stop_delay}</code>s\n"
            f"• Step: <code>{step_delay}</code>s\n"
            f"• Count: <code>{count}</code>\n"
            f"• Purge: <code>{purge_count}</code>\n"
            f"• React: <code>{react_emoji or 'off'}</code>\n"
            f"• Msgs: <code>{messages}</code>",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("⏸️ Pause", callback_data=f"pause_{chat_id}"),
                    InlineKeyboardButton("⏹️ Stop", callback_data=f"stop_{chat_id}"),
                ],
                [
                    InlineKeyboardButton(f"{'✅' if purge_count > 0 else '❌'} Purge", callback_data=f"toggle_purge_{chat_id}"),
                    InlineKeyboardButton(f"{'✅' if react_emoji else '❌'} React", callback_data=f"toggle_react_{chat_id}"),
                ],
                [
                    InlineKeyboardButton("📝 Edit Last Msg", callback_data=f"edit_last_{chat_id}"),
                    InlineKeyboardButton("📝 Edit Msg List", callback_data=f"edit_list_{chat_id}"),
                ],
            ]),
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
        
        RELAY_SPAM_TASKS[chat_id]["notif_msg"] = notif_msg
        
        # Task background
        async def spam_task():
            await spam_loop(c, target_chat, chat_id, messages, [start_delay + i*step_delay for i in range(int((stop_delay-start_delay)/step_delay)+1)], count, start_delay, stop_delay, step_delay, None, react_emoji, is_batch)
            
        task = asyncio.create_task(spam_task())
        RELAY_SPAM_TASKS[chat_id]["task"] = task
        
        await m.handle_message(f"🚀 RelaySpam dimulai di <code>{html.escape(target_chat.title)}</code>. Lihat log untuk kontrol.")
        
    except ValueError as ve:
        await m.handle_message(f"❌ Input salah: {ve}")
    except Exception as e:
        logger.error(f"RelaySpam error: {e}")
        await m.handle_message(f"❌ Gagal: {str(e)}")


@Altruix.register_on_cmd(
    ["cancelrelayspam", "xspamcancel"],
    cmd_help={
        "help": "Cancel an ongoing relay spam task.",
        "example": ".cancelrelayspam",
    },
)
@log_errors
async def cancel_relayspam_handler(c: Client, m: Message):
    found = False
    for chat_id in list(RELAY_SPAM_TASKS.keys()):
        if RELAY_SPAM_TASKS[chat_id].get("config", {}).get("user_id") == m.from_user.id:
            RELAY_SPAM_TASKS[chat_id]["running"] = False
            if "task" in RELAY_SPAM_TASKS[chat_id]:
                RELAY_SPAM_TASKS[chat_id]["task"].cancel()
            RELAY_SPAM_TASKS.pop(chat_id, None)
            PURGE_CONFIG.pop(chat_id, None)
            REACT_CONFIG.pop(chat_id, None)
            await m.handle_message(f"⏸️ Relay spam di <code>{chat_id}</code> dibatalkan.")
            await Altruix.bot.send_message(LOG_CHAT_ID, f"⏸️ RelaySpam di {chat_id} dibatalkan oleh {m.from_user.mention}.")
            found = True
            break
            
    if not found:
        await m.handle_message("❌ Tidak ada task aktif untuk Anda.")


@Altruix.register_on_cmd(
    ["relaystatus", "xspamstatus"],
    cmd_help={
        "help": "Check status of ongoing relay spam tasks.",
        "example": ".relaystatus",
    },
)
@log_errors
async def relaystatus_handler(c: Client, m: Message):
    if not RELAY_SPAM_TASKS:
        return await m.handle_message("🟢 Tidak ada task aktif.")
        
    status_lines = ["<b>Status Semua Task RelaySpam:</b>"]
    for chat_id, data in RELAY_SPAM_TASKS.items():
        try:
            chat = await c.get_chat(chat_id)
            title = html.escape(chat.title)
        except Exception:
            title = f"Chat ID <code>{chat_id}</code> (Tidak dapat diakses)"
            
        running = data.get("running", False)
        paused = data.get("paused", False)
        
        if paused:
            status = "🟡 Paused"
        elif running:
            status = "🟢 Active"
        else:
            status = "🔴 Stopped (Pending Clear)"
            
        status_lines.append(f"• {status} di <b>{title}</b>")
        
    await m.handle_message("\n".join(status_lines))

logger.info(f"[DEBUG] Loaded → {__plugin_name__} v{PLUGIN_VERSION}")
