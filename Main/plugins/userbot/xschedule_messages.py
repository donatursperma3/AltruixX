# Main/plugins/userbot/xschedule_messages.py
# ============================================================================
# ROLE: Senior Expert Python Developer (Telegram Userbot Specialist)
# FRAMEWORK: Pyrogram / Kurigram (Altroid-X Style)
# TASK: Auto Repeat Scheduler Message
# DESCRIPTION: 
#   Plugin to schedule messages with automatic repetition using Telegram's
#   cloud scheduling feature. Supports multi-client independent tracking.
#   Includes Inline Builder integration for interactive management.
# ============================================================================

import asyncio
import time
from datetime import datetime, timedelta
import re
import logging
from typing import Union

from Main import Altruix
from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, RPCError

from Main.core.decorators import log_errors, iuser_check
from Main.internals.xschedule_builder import build_cloud_category_menu

# ============================================================================
# SETTINGS & DATABASE HELPERS
# ============================================================================
PLUGIN_VERSION = "1.2.241"
logger = logging.getLogger("altruix.xschedule")

# Constants for Bulk Scheduling
MAX_TELEGRAM_SCHEDULE = 100  # Telegram hard limit per chat
BUFFER_SIZE = 20             # Pre-schedule buffer for infinite/long tasks
SCHED_DELAY = 0.5            # Delay between bulk API calls to avoid FloodWait

def get_db():
    """Returns the synchronized database collection for scheduled messages."""
    db_instance = getattr(Altruix, "db", Altruix.local_db)
    col = db_instance.make_collection("SCHEDULED_MESSAGES")
    return col

def parse_interval(interval_str: str) -> Union[int, None]:
    """
    Parses interval string like '10m', '1h', '1d' or '10menit', '1jam', '1hari' into seconds.
    If no suffix, assumes minutes.
    """
    match = re.match(r"^(\d+)\s*([a-z]*)$", interval_str.lower())
    if not match:
        return None
    
    value = int(match.group(1))
    unit = match.group(2)
    
    if unit in ('s', 'detik', 'second'):
        return value
    elif unit in ('m', 'menit', ''):
        return value * 60
    elif unit in ('h', 'j', 'jam', 'hour'):
        return value * 3600
    elif unit in ('d', 'hari', 'day'):
        return value * 86400
    return None

def get_readable_interval(seconds: int) -> str:
    """Converts seconds into a readable string."""
    if seconds >= 86400:
        return f"{seconds // 86400} Hari"
    elif seconds >= 3600:
        return f"{seconds // 3600} Jam"
    elif seconds >= 60:
        return f"{seconds // 60} Menit"
    return f"{seconds} Detik"

# ============================================================================
# SELF-RESCHEDULING LOGIC
# ============================================================================

@Altruix.on_message(filters.outgoing, group=-3)
@log_errors
async def check_for_rescheduling(c: Client, m: Message):
    """
    Handler that monitors outgoing messages. Refills the schedule buffer 
    if the number of future scheduled messages drops below the threshold.
    """
    if m.edit_date:
        return
        
    text = m.text or m.caption
    if not text:
        return

    DB = get_db()
    record = await DB.find_one({
        "owner_id": c.me.id,
        "chat_id": m.chat.id,
        "text": text,
        "is_active": True
    })

    if not record:
        return

    # To avoid hammer/duplicate triggers
    last_resched = record.get("last_resched", 0)
    if time.time() - last_resched < 5:
        return

    interval = record.get("interval_sec", 0)
    max_repeats = record.get("max_repeats", 0)
    
    # 1. Update current_repeats (how many were actually SENT)
    current_sent = record.get("current_repeats", 0) + 1
    update_data = {"current_repeats": current_sent, "last_resched": time.time()}
    
    if max_repeats > 0 and current_sent >= max_repeats:
        update_data["is_active"] = False
        await DB.update_one({"_id": record["_id"]}, {"$set": update_data})
        logger.info(f"Target reached for {m.chat.id}. Total sent: {current_sent}")
        return

    # 2. Check Buffer Status
    try:
        scheduled_msgs = await c.get_scheduled_messages(m.chat.id)
        current_in_queue = len([msg for msg in scheduled_msgs if (msg.text or msg.caption) == text])
        
        # If queue is low, refill it
        if current_in_queue < (BUFFER_SIZE // 2):
            # Calculate how many more to schedule
            to_schedule = 0
            if max_repeats == 0:
                to_schedule = BUFFER_SIZE - current_in_queue
            else:
                remaining_total = max_repeats - current_sent
                to_schedule = min(remaining_total - current_in_queue, BUFFER_SIZE - current_in_queue)
            
            if to_schedule > 0:
                # Find the furthest scheduled time to start from
                last_date = m.date
                if scheduled_msgs:
                    # Logic to find the furthest among our matching messages
                    our_future = [msg.date for msg in scheduled_msgs if (msg.text or msg.caption) == text]
                    if our_future:
                        last_date = max(our_future)
                
                # Fill the gap
                for i in range(1, to_schedule + 1):
                    next_time = last_date + timedelta(seconds=interval * i)
                    try:
                        await c.send_message(m.chat.id, text, schedule_date=next_time)
                        await asyncio.sleep(SCHED_DELAY)
                    except FloodWait as e:
                        await asyncio.sleep(e.value)
                        await c.send_message(m.chat.id, text, schedule_date=next_time)
                    except Exception as e:
                        logger.error(f"Maintenance scheduling error: {e}")
                        break
        
        await DB.update_one({"_id": record["_id"]}, {"$set": update_data})
        
    except Exception as e:
        logger.error(f"Buffer maintenance failed for {m.chat.id}: {e}")

# ============================================================================
# COMMANDS
# ============================================================================

@Altruix.register_on_cmd(
    ["schedulrepeatmsg"],
    cmd_help={
        "help": "Jadwalkan pesan berulang secara otomatis (Cloud Scheduling).",
        "usage": ".schedulrepeatmsg <chat_id/me> <interval> <teks>",
        "usage": ".schedulrepeatmsg <chat_id/me> <interval> <limit_opsional> <teks>",
        "detail": (
            "Menjadwalkan pesan agar dikirim dan diulang otomatis.\n"
            "Userbot akan otomatis menjadwalkan ulang untuk interval berikutnya.\n\n"
            "<b>Parameter:</b>\n"
            "• <code>chat_id/me</code> : ID Chat, Username, atau 'me' untuk Saved Messages.\n"
            "• <code>interval</code> : Durasi pengulangan (s/m/h/d atau detik/menit/jam/hari).\n"
            "• <code>limit</code> : (Opsional) Jumlah maksimum pesan dikirim sebelum stop.\n"
            "• <code>teks</code> : Isi pesan yang akan dikirim.\n\n"
            "<b>Contoh Interval:</b>\n"
            "• <code>30s</code> atau <code>30detik</code>\n"
            "• <code>10m</code> atau <code>10menit</code>\n"
            "• <code>2h</code> atau <code>2jam</code>\n"
            "• <code>1d</code> atau <code>1hari</code>\n\n"
            "<b>Contoh Penggunaan:</b>\n"
            "• <code>.schedulrepeatmsg me 1h 5 Halo!</code> (Berulang 5x setiap 1 jam)\n"
            "• <code>.schedulrepeatmsg me 1h Halo!</code> (Berulang tiap 1 jam selamanya)"
        )
    }
)
@iuser_check
@log_errors
async def cmd_schedule_repeat(c: Client, m: Message):
    """
    Handles the .schedulrepeatmsg command.
    Schedules a repeating message and tracks it in the database.
    """
    args = m.user_input
    if not args:
        await m.reply_msg(
            "❌ <b>Format Salah!</b>\n"
            "Gunakan: <code>.schedulrepeatmsg &lt;chat_id/me&gt; &lt;interval&gt; [limit] &lt;teks&gt;</code>\n"
            "Contoh: <code>.schedulrepeatmsg me 1h 5 Semangat Pagi!</code>"
        )
        return await m.delete_if_self()

    parts = args.split(None, 3)
    if len(parts) < 3:
        await m.reply_msg("❌ <b>Format tidak lengkap!</b> Tambahkan interval dan teks pesan.")
        return await m.delete_if_self()

    target_chat = parts[0]
    interval_raw = parts[1]
    
    limit = 0
    text = ""
    if len(parts) == 4 and parts[2].isdigit():
        limit = int(parts[2])
        text = parts[3]
    else:
        text = parts[2] if len(parts) == 3 else parts[2] + " " + parts[3]
    
    if not text.strip():
        await m.reply_msg("❌ <b>Teks pesan kosong!</b>")
        return await m.delete_if_self()

    # Resolve chat ID
    if target_chat.lower() == "me":
        chat_id = "me"
    else:
        try:
            chat_id = int(target_chat)
        except ValueError:
            # Maybe it's a username
            try:
                chat = await c.get_chat(target_chat)
                chat_id = chat.id
            except Exception:
                await m.reply_msg("❌ <b>Chat ID / Username tidak valid!</b>")
                return await m.delete_if_self()

    # Parse interval
    interval_sec = parse_interval(interval_raw)
    if not interval_sec:
        await m.reply_msg("❌ <b>Format Interval salah!</b> Gunakan s, m, h, atau d (misal: 30s, 10m, 2h).")
        return await m.delete_if_self()

    if interval_sec < 10:
        await m.reply_msg("⚠️ <b>Interval minimum adalah 10 detik.</b>")
        return await m.delete_if_self()

    DB = get_db()
    doc_id = f"{c.me.id}_{chat_id}" if chat_id != "me" else f"{c.me.id}_self"
    
    doc = {
        "_id": doc_id,
        "owner_id": c.me.id,
        "chat_id": chat_id if chat_id != "me" else c.me.id,
        "text": text,
        "interval_raw": interval_raw,
        "interval_sec": interval_sec,
        "max_repeats": limit,
        "current_repeats": 0,
        "is_active": True,
        "last_resched": 0,
        "timestamp": time.time()
    }

    # Initial bulk scheduling
    # If limit is 0 (infinite), we pre-schedule BUFFER_SIZE messages
    to_schedule_now = limit if (0 < limit <= BUFFER_SIZE) else BUFFER_SIZE
    if limit > 0 and limit > BUFFER_SIZE:
        to_schedule_now = min(limit, MAX_TELEGRAM_SCHEDULE) # Cap at 100 for safety

    try:
        status_msg = await m.reply_msg("🕒 <b>Memulai penjadwalan massal ke Telegram...</b>")
        
        scheduled_count = 0
        for i in range(1, to_schedule_now + 1):
            target_date = m.date + timedelta(seconds=interval_sec * i)
            try:
                await c.send_message(chat_id=chat_id, text=text, schedule_date=target_date)
                scheduled_count += 1
                if to_schedule_now > 5:
                    await asyncio.sleep(SCHED_DELAY)
            except FloodWait as e:
                await asyncio.sleep(e.value)
                await c.send_message(chat_id=chat_id, text=text, schedule_date=target_date)
                scheduled_count += 1
        
        # Save to database
        await DB.update_one({"_id": doc_id}, {"$set": doc}, upsert=True)
        
        target_name = "Saved Messages" if chat_id == "me" else target_chat
        limit_text = f"{limit} kali" if limit > 0 else "Terus menerus (♾️)"
        
        detail_msg = (
            f"✅ <b>Pesan Berulang Terjadwal!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 <b>Target:</b> <code>{target_name}</code>\n"
            f"🕒 <b>Interval:</b> <code>{interval_raw}</code> ({get_readable_interval(interval_sec)})\n"
            f"🎯 <b>Batas Pengulangan:</b> {limit_text}\n"
            f"📦 <b>Pre-scheduled:</b> <code>{scheduled_count}</code> pesan aktif\n"
            f"📝 <b>Teks:</b> <code>{text[:30]}...</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 <i>Semua pesan sudah masuk ke antrean Scheduled Telegram.</i>"
        )
        await status_msg.edit(detail_msg)
        
    except Exception as e:
        await m.reply_msg(f"❌ <b>Gagal Penjadwalan:</b> <code>{str(e)}</code>")
    
    return await m.delete_if_self()

@Altruix.register_on_cmd(
    ["schedulmenu", "scheduldash"],
    cmd_help={
        "help": "Tampilkan Dashboard Scheduler Utama.", 
        "usage": ".schedulmenu",
        "description": "Membuka menu pengaturan pusat untuk mengelola semua pesan terjadwal dan statistik pengulangan."
    }
)
@iuser_check
@log_errors
async def cmd_schedule_menu(c: Client, m: Message):
    """
    Triggers the Main Dashboard Inline Builder via the Bot Assistant.
    """
    bot_usr = Altruix.bot_manager.get_bot_username(c.me.id)
    if not bot_usr:
        return await m.reply_msg("❌ <b>Bot Assistant tidak ditemukan!</b>")

    query_str = f"sched_main_{c.me.id}"
    
    try:
        res = await c.get_inline_bot_results(bot_usr, query_str)
        if res.results:
            await c.send_inline_bot_result(
                chat_id=m.chat.id,
                query_id=res.query_id,
                result_id=res.results[0].id,
                reply_to_message_id=m.reply_to_message_id or m.id
            )
        else:
            await m.reply_msg("❌ <b>Gagal memuat dashboard.</b>")
    except Exception as e:
        await m.reply_msg(f"❌ <b>Error Menu:</b> <code>{str(e)}</code>")

    return await m.delete_if_self()

@Altruix.register_on_cmd(
    ["schedullist"],
    cmd_help={
        "help": "Lihat daftar pesan terjadwal via Inline Menu.", 
        "usage": ".schedullist",
        "description": "Menampilkan semua jadwal pengulangan pesan yang aktif untuk akun ini dalam bentuk menu interaktif."
    }
)
@iuser_check
@log_errors
async def cmd_schedule_list(c: Client, m: Message):
    """
    Triggers the Inline Builder via the Bot Assistant to show a rich list dashboard.
    """
    bot_usr = Altruix.bot_manager.get_bot_username(c.me.id)
    if not bot_usr:
        return await m.reply_msg("❌ <b>Bot Assistant tidak ditemukan!</b>")

    query_str = f"sched_list_{c.me.id}"
    
    try:
        # Trigger inline results from the bot
        res = await c.get_inline_bot_results(bot_usr, query_str)
        if res.results:
            await c.send_inline_bot_result(
                chat_id=m.chat.id,
                query_id=res.query_id,
                result_id=res.results[0].id,
                reply_to_message_id=m.reply_to_message_id or m.id
            )
        else:
            await m.reply_msg("📭 <b>Tidak ada pesan terjadwal yang aktif.</b>")
    except Exception as e:
        await m.reply_msg(f"❌ <b>Gagal memuat menu:</b> <code>{str(e)}</code>")

    return await m.delete_if_self()

@Altruix.register_on_cmd(
    ["schedulcancel"],
    cmd_help={
        "help": "Batalkan pesan terjadwal.",
        "usage": ".schedulcancel <chat_id/me>",
        "example": ".schedulcancel me",
        "description": "Menghentikan sistem pengulangan pesan untuk chat tertentu dan menghapus pesan yang sedang dijadwalkan di server Telegram."
    }
)
@iuser_check
@log_errors
async def cmd_schedule_cancel(c: Client, m: Message):
    """
    Handles the .schedulcancel command.
    Cancels an active repeating schedule and removes it from the database.
    """
    args = m.user_input
    if not args:
        await m.reply_msg("❌ <b>Gunakan:</b> <code>.schedulcancel &lt;chat_id/me&gt;</code>")
        return await m.delete_if_self()

    target_chat = args.strip()
    if target_chat.lower() == "me":
        real_chat_id = c.me.id
    else:
        try:
            real_chat_id = int(target_chat)
        except ValueError:
            try:
                chat = await c.get_chat(target_chat)
                real_chat_id = chat.id
            except Exception:
                await m.reply_msg("❌ <b>Chat ID tidak valid.</b>")
                return await m.delete_if_self()

    DB = get_db()
    # Mark as inactive in DB
    res = await DB.update_one(
        {"owner_id": c.me.id, "chat_id": real_chat_id},
        {"$set": {"is_active": False}}
    )

    try:
        scheduled_msgs = await c.get_scheduled_messages(real_chat_id)
        if scheduled_msgs:
            await c.delete_scheduled_messages(real_chat_id, [msg.id for msg in scheduled_msgs])
    except Exception as e:
        logger.warning(f"Could not delete scheduled messages on server for {real_chat_id}: {e}")

    if res.modified_count > 0:
        await m.reply_msg(f"✅ <b>Pengulangan untuk chat <code>{target_chat}</code> telah dibatalkan.</b>")
    else:
        await m.reply_msg(f"❓ <b>Tidak ada pengulangan aktif ditemukan untuk chat <code>{target_chat}</code>.</b>")
    
    return await m.delete_if_self()

@Altruix.register_on_cmd(
    ["schedulcloud"],
    cmd_help={
        "help": "Lihat semua pesan terjadwal di cloud Telegram secara realtime.",
        "usage": ".schedulcloud [filter]",
        "example": ".schedulcloud groups",
        "description": (
            "Mencari dan menampilkan pesan yang sedang dijadwalkan di server Telegram.\n\n"
            "<b>Filter Tersedia:</b>\n"
            "• <code>all</code> : Semua chat (Default)\n"
            "• <code>users</code> : Chat pribadi (User)\n"
            "• <code>contacts</code> : Chat dengan kontak\n"
            "• <code>noncontacts</code> : Chat dengan non-kontak\n"
            "• <code>groups</code> : Grup & Supergrup\n"
            "• <code>channels</code> : Channel\n"
            "• <code>bots</code> : Bot"
        )
    }
)
@iuser_check
@log_errors
async def cmd_schedule_cloud(c: Client, m: Message):
    """
    Shows the interactive Cloud Schedule Dashboard Level 1 (Categories).
    """
    status_msg = await m.reply_msg("🔍 <b>Membuka Dashboard Cloud...</b>")
    
    try:
        # Use Bot Assistant to show the interactive dashboard
        if hasattr(Altruix, "bot") and Altruix.bot:
            res = await Altruix.bot.get_inline_bot_results(c.me.username, f"sched_main_{c.me.id}")
            if res and res.results:
                await c.send_inline_bot_result(
                    m.chat.id, 
                    query_id=res.query_id, 
                    result_id=res.results[0].id,
                    reply_to_message_id=m.reply_to_message_id or m.id
                )
                await status_msg.delete()
            else:
                text, kb = await build_cloud_category_menu(c.me.id)
                await status_msg.edit(text, reply_markup=kb)
        else:
            text, kb = await build_cloud_category_menu(c.me.id)
            await status_msg.edit(text, reply_markup=kb)

    except Exception as e:
        await status_msg.edit(f"❌ <b>Terjadi kesalahan:</b> <code>{str(e)}</code>")
    
    return await m.delete_if_self()
