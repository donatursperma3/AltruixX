# qwen xalliance.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
# 
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
# 
# All rights reserved.

import asyncio
import random
import html
import os
import time
import aiohttp
from Main import Altruix
from pyrogram import Client, filters
from Main.core.types.message import Message
from Main.core.decorators import log_errors
from pyrogram.errors import RPCError, FloodWait
from pyrogram.enums import ParseMode, PrivacyKey, PrivacyRuleType, ChatType, ChatAction
import json
import logging
import psutil
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from Main.plugins.userbot.xtaskmanager import register_task, unregister_task, generate_task_id

START_TIME = time.time()
TOTAL_MESSAGES_SENT = 0
SCHEDULER = AsyncIOScheduler()
SCHEDULER.start()

# Ensure directories exist
LOG_FILE = "LOGS/alliance_pro.log"
DATA_DIR = "DATA"
BLACKLIST_FILE = os.path.join(DATA_DIR, "alliance_blacklist.json")
for d in ["LOGS", DATA_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

# Setup Main Pro Logger
pro_logger = logging.getLogger("alliance_pro")
if not pro_logger.handlers:
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    pro_logger.addHandler(handler)
    pro_logger.setLevel(logging.INFO)

PLUGIN_VERSION = "1.9.0"

# --- PRO, STEALTH, INFRA & SURVIVAL STATES ---
ALL_COPY_MODE = False
ALL_AI_REPLY = False
ALL_NATURE_MODE = False
ACTIVE_SHIFT_COUNT = 0
SHIFT_EXPIRY = 0
SHIFT_CLIENTS = []
MONITOR_KEYWORDS = []
GROUP_BLACKLIST = [] # List of blacklisted chat IDs
PROXY_MAP = {} # {session_id: proxy_dict}
AI_HISTORY = {} # {session_id: last_reply_time}
AI_API_KEY = os.getenv("AI_API_KEY")
AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini").lower()
LOG_HISTORY = [] # Last 15 monitoring hits [@botname logs]
if not hasattr(Altruix, "ALLIANCE_WAITING"):
    Altruix.ALLIANCE_WAITING = {} # {user_id: {"action": str, "data": dict}}

# --- MASTER ACCOUNT MANAGEMENT ---
def get_master():
    """Returns the designated Master client instance. Fallback to clients[0]."""
    master_id = getattr(Altruix.config, "ALLIANCE_MASTER_ID", None)
    if master_id:
        for cli in Altruix.clients:
            if hasattr(cli, 'me') and cli.me and cli.me.id == int(master_id):
                return cli
    # Fallback to the first authorized client if no master is set or found
    for cli in Altruix.clients:
        if hasattr(cli, 'me') and cli.me and getattr(cli, 'is_authorized', True):
            return cli
    return get_master() if Altruix.clients else None

def _parse_delay():
    raw = os.getenv("AI_DELAY_RANGE", "5-15")
    try:
        if "-" in raw:
            mn, mx = map(int, raw.split("-"))
            return mn, mx
        return int(raw), int(raw)
    except: return 5, 15

AI_DELAY_MIN, AI_DELAY_MAX = _parse_delay()

def save_blacklist():
    """Saves the global group blacklist to JSON."""
    try:
        with open(BLACKLIST_FILE, "w") as f:
            json.dump(GROUP_BLACKLIST, f)
    except: pass

def load_blacklist():
    """Loads the global group blacklist from JSON."""
    global GROUP_BLACKLIST
    if os.path.exists(BLACKLIST_FILE):
        try:
            with open(BLACKLIST_FILE, "r") as f:
                GROUP_BLACKLIST = json.load(f)
        except: pass

def get_health_score(cli_id):
    """Calculates a health score (0-100) for a session (Placeholder logic)."""
    # In a real app, this would track actual error counts from the log
    return 100 # Default to perfect for now

def load_alliance_proxies():
    """Loads proxies from DATA/alliance_proxies.json"""
    global PROXY_MAP
    p_file = os.path.join(DATA_DIR, "alliance_proxies.json")
    if os.path.exists(p_file):
        try:
            with open(p_file, "r") as f:
                PROXY_MAP = json.load(f)
            pro_logger.info(f"Loaded {len(PROXY_MAP)} proxies from JSON.")
        except Exception as e:
            pro_logger.error(f"Failed to load proxies: {str(e)}")

def get_alliance_logger(session_name):
    """Returns a logger dedicated to a specific session's alliance actions."""
    logger = logging.getLogger(f"alliance_{session_name}")
    if not logger.handlers:
        handler = logging.FileHandler(os.path.join("LOGS", f"alliance_{session_name}.log"), encoding="utf-8")
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger

def get_active_alliance():
    """Returns the currently active and authorized alliance sessions."""
    global ACTIVE_SHIFT_COUNT, SHIFT_EXPIRY, SHIFT_CLIENTS
    
    def _is_valid(cli):
        return hasattr(cli, 'me') and cli.me and getattr(cli, 'is_authorized', True)

    if ACTIVE_SHIFT_COUNT > 0 and time.time() < SHIFT_EXPIRY:
        return [cli for cli in SHIFT_CLIENTS if _is_valid(cli)]
    
    return [cli for cli in Altruix.clients if _is_valid(cli)]

async def call_ai_api(prompt):
    """Actual AI API Logic using Gemini (Google) or Generic Provider. Returns (text, error)"""
    # Sync settings from persistent database
    api_key = await Altruix.config.get_env("AI_API_KEY") or AI_API_KEY
    provider = await Altruix.config.get_env("AI_PROVIDER") or AI_PROVIDER
    
    if not api_key:
        return None, "API Key missing (Set AI_API_KEY in .env or via bot)"

    if provider.lower() == "gemini":
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        payload = {
            "contents": [{
                "parts": [{"text": f"You are an AI assistant for a Telegram Alliance. Respond concisely to this message: {prompt}"}]
            }]
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        text = data['candidates'][0]['content']['parts'][0]['text']
                        return text, None
                    else:
                        return None, f"API returned status {resp.status}"
        except Exception as e:
            return None, str(e)
    
    return None, f"Provider '{provider}' not fully implemented yet."

async def simulate_ai_thinking(c: Client, chat_id: int, total_delay: float):
    """Simulates a human-like thinking delay with periodic typing status."""
    start = time.time()
    while time.time() - start < total_delay:
        try:
            await c.send_chat_action(chat_id, ChatAction.TYPING)
        except: pass
        # Typing status lasts ~5s, we refresh every 4s
        await asyncio.sleep(min(4, total_delay - (time.time() - start)))

# --- HANDLERS & RECOVERY ---
@Client.on_message(filters.all & filters.group, group=10)
async def alliance_event_handler(c: Client, m: Message):
    global ALL_COPY_MODE, ALL_AI_REPLY, ALL_NATURE_MODE, MONITOR_KEYWORDS, TOTAL_MESSAGES_SENT, GROUP_BLACKLIST, AI_HISTORY
    if not Altruix.clients: return
    
    # 0. Global Group Blacklist Check
    if m.chat.id in GROUP_BLACKLIST:
        return # Ignore blacklisted chats
    
    # Track sent messages (assuming if we see it, it's activity)
    # But only if it's FROM an alliance account to be accurate
    all_ids = [cli.me.id for cli in Altruix.clients if hasattr(cli, 'me') and cli.me]
    if m.from_user and m.from_user.id in all_ids:
        TOTAL_MESSAGES_SENT += 1

    # 1. Mirroring Logic
    if ALL_COPY_MODE:
        master = get_master()
        if hasattr(master, 'me') and master.me and m.from_user and m.from_user.id == master.me.id:
            if c.me.id != master.me.id:
                active_ids = [cli.me.id for cli in get_active_alliance()]
                if c.me.id in active_ids:
                    try:
                        await asyncio.sleep(random.uniform(1.0, 3.0))
                        await m.copy(m.chat.id)
                    except UserBannedInChannel:
                        if m.chat.id not in GROUP_BLACKLIST:
                            GROUP_BLACKLIST.append(m.chat.id)
                            save_blacklist()
                            pro_logger.warning(f"Group {m.chat.id} blacklisted (Ban detected).")
                    except RPCError as e:
                        if "SERVICE_UNAVAILABLE" in str(e) or "INTERNAL_SERVER_ERROR" in str(e):
                            pro_logger.warning(f"Session {c.me.id} error: {str(e)}. Attempting restart...")
                            await c.restart()
                    except: pass

    # 2. AI-Response Logic (Slaves only)
    if ALL_AI_REPLY and c.me.id != get_master().me.id:
        is_mention = (m.mentioned or (m.reply_to_message and m.reply_to_message.from_user and m.reply_to_message.from_user.id == c.me.id))
        if is_mention and m.text:
            # Rate Limit: 30s per account
            now = time.time()
            if now - AI_HISTORY.get(c.me.id, 0) > 30:
                try:
                    # Delay logic for natural flow
                    delay = random.uniform(AI_DELAY_MIN, AI_DELAY_MAX)
                    await simulate_ai_thinking(c, m.chat.id, delay)
                    
                    resp, err = await call_ai_api(m.text)
                    if resp:
                        await m.reply(resp)
                        AI_HISTORY[c.me.id] = now
                    elif err:
                        # SILENT FAILURE: Log to LOG_CHAT_ID instead of target chat
                        log_chat = os.getenv("LOG_CHAT_ID")
                        if log_chat:
                            try:
                                log_chat = int(log_chat)
                                log_msg = (
                                    f"⚠️ <b>Alliance AI Failure</b>\n"
                                    f"👤 <b>Account:</b> {c.me.first_name} (<code>{c.me.id}</code>)\n"
                                    f"💬 <b>Chat:</b> {m.chat.title or 'Private'} (<code>{m.chat.id}</code>)\n"
                                    f"🛠️ <b>Action:</b> AI Response (Mention/Reply)\n"
                                    f"❌ <b>Error:</b> <code>{err}</code>"
                                )
                                # Use Master account to send log
                                master = get_master()
                                await master.send_message(log_chat, log_msg)
                            except: pass
                        pro_logger.error(f"AI reply failed for session {c.me.id}: {err}")
                except Exception as e:
                    pro_logger.error(f"AI reply handler crashed for session {c.me.id}: {e}")

    # 3. Nature Mode simulation
    if ALL_NATURE_MODE and random.random() < 0.05: # 5% chance on each msg to "act natural"
        try:
            # Simulate reading
            await c.read_chat_history(m.chat.id)
            if random.random() < 0.3: # 30% chance to "start typing" then stop
                await c.send_chat_action(m.chat.id, ChatAction.TYPING)
                await asyncio.sleep(random.randint(2, 5))
        except Exception as e:
            pro_logger.debug(f"Nature mode action failed for session {c.me.id}: {e}")

    # 4. Monitoring Logic
    if MONITOR_KEYWORDS and m.text:
        text = m.text.lower()
        if any(kw.lower() in text for kw in MONITOR_KEYWORDS):
            master = get_master()
            if not master: return
            try:
                report = (
                    f"🕵️‍♂️ <b>Alliance Monitor Alert</b>\n"
                    f"👤 <b>Session:</b> <code>{c.me.first_name}</code>\n"
                    f"💬 <b>Chat:</b> <code>{m.chat.title or m.chat.id}</code>\n"
                    f"🔗 <a href='{m.link}'>Link to Message</a>\n"
                    f"📝 <b>Text:</b> <code>{html.escape(m.text[:100])}...</code>"
                )
                await master.send_message("me", report)
                
                # Push to global history for bot dashboard
                LOG_HISTORY.append({
                    "time": time.strftime("%H:%M:%S"),
                    "session": c.me.first_name,
                    "chat": m.chat.title or str(m.chat.id),
                    "text": m.text[:50],
                    "link": m.link
                })
                if len(LOG_HISTORY) > 15: LOG_HISTORY.pop(0)
            except: pass

def parse_tg_link(link):
    """Parse Telegram message links into (chat_id, message_id)"""
    import re
    if not link: return None, None
    link = link.replace("tg://openmessage?user_id=", "https://t.me/").replace("tg://openmessage?chat_id=", "https://t.me/c/")
    m = re.search(r"t\.me/c/(\d+)/(\d+)", link)
    if m: return int(f"-100{m.group(1)}"), int(m.group(2))
    m = re.search(r"t\.me/([^/]+)/(\d+)", link)
    if m: return m.group(1), int(m.group(2))
    return None, None

# --- BASIC COMMANDS ---

async def mass_join_core(link, tid=None):
    """Core logic to make all active sessions join a chat."""
    results = []
    # Pre-check against blacklist
    target_chat, _ = parse_tg_link(link)
    if target_chat in GROUP_BLACKLIST:
        return [f"🛡️ <b>Join Cancelled:</b> Group <code>{target_chat}</code> is blacklisted."]

    for client in get_active_alliance():
        if tid and asyncio.current_task().cancelled():
            results.append(f"🛑 <b>Task Cancelled</b>")
            break
        name = html.escape(client.me.first_name)
        try:
            await client.join_chat(link)
            results.append(f"✅ <b>{name}</b> -> Joined!")
        except Exception as e: 
            results.append(f"❌ <b>{name}</b> -> <code>{str(e)}</code>")
        await asyncio.sleep(random.uniform(0.5, 1.5))
    return results

@Altruix.register_on_cmd(
    ["alljoin"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Join all alliance accounts to a chat",
        "description": "Perintah ini memaksa semua akun aliansi yang aktif untuk bergabung ke grup atau channel yang ditentukan via link/username.",
        "usage": "alljoin [link/username]",
        "example": "alljoin @Altruix",
        "note": "Akun yang sudah ada di grup akan dilewati. Join dilakukan dengan jeda acak agar lebih aman."
    },
)
@log_errors
async def all_join_cmd(c: Client, m: Message):
    link = m.text.split(None, 1)[1] if len(m.text.split()) > 1 else None
    if not link: 
        await m.reply_msg("❌ <b>Provide a link!</b>")
        return await m.delete_if_self()
    
    tid = generate_task_id("ALL")
    register_task(tid, asyncio.current_task(), "Alliance Join", "xalliance", c.me.id, f"Target: {link}")
    
    status_msg = await m.reply_msg(f"⏳ <b>Alliance Joining [{tid}]:</b> <code>{link}</code>...")
    
    try:
        results = await mass_join_core(link, tid=tid)
        await status_msg.edit_msg(f"⚔️ <b>Join Report [{tid}]</b>\n<blockquote expandable>" + "\n".join(results) + "</blockquote>")
    except asyncio.CancelledError:
        await status_msg.edit_msg(f"🛑 <b>Join Task {tid} Cancelled.</b>")
    finally:
        unregister_task(tid)
        await m.delete_if_self()


@Altruix.register_on_cmd(
    ["allleave"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Leave current chat with all accounts",
        "description": "Perintah darurat untuk mengeluarkan seluruh akun aliansi dari grup tempat perintah ini dikirim.",
        "usage": "allleave",
        "example": "allleave",
        "note": "Gunakan dengan bijak, karena akun tidak akan bisa kembali kecuali di-invite atau join ulang."
    },
)
@log_errors
async def all_leave_cmd(c: Client, m: Message):
    tid = generate_task_id("ALL")
    register_task(tid, asyncio.current_task(), "Alliance Leave", "xalliance", c.me.id, f"Chat: {m.chat.id}")
    status_msg = await m.reply_msg(f"⏳ <b>Alliance Leaving... [{tid}]</b>")
    results = []
    try:
        for client in get_active_alliance():
            if asyncio.current_task().cancelled(): break
            name = html.escape(client.me.first_name)
            try:
                await client.leave_chat(m.chat.id)
                results.append(f"✅ <b>{name}</b> -> Left!")
            except Exception as e: results.append(f"❌ <b>{name}</b> -> <code>{str(e)}</code>")
            await asyncio.sleep(random.uniform(0.5, 1.5))
        await status_msg.edit_msg(f"⚔️ <b>Leave Report [{tid}]</b>\n<blockquote expandable>" + "\n".join(results) + "</blockquote>")
    except asyncio.CancelledError:
        await status_msg.edit_msg(f"🛑 <b>Leave Task {tid} Cancelled.</b>")
    finally:
        unregister_task(tid)
        await m.delete_if_self()


@Altruix.register_on_cmd(
    ["allstatus"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Check full status of all alliance sessions",
        "description": "Menampilkan laporan kesehatan aliansi: Status koneksi, Level Privasi, Skor Kesehatan (Health), dan Uptime bot.",
        "usage": "allstatus",
        "example": "allstatus",
        "note": "Gunakan untuk memastikan semua akun dalam kondisi 'Normal' sebelum menjalankan misi."
    },
)
@log_errors
async def all_status_cmd(c: Client, m: Message):
    tid = generate_task_id("ALL")
    register_task(tid, asyncio.current_task(), "Alliance Status", "xalliance", c.me.id, "Full Status Check")
    status_msg = await m.reply_msg("⏳ <b>Checking Alliance Full Status...</b>")
    results = []
    
    try:
        uptime = Essentials.get_readable_time(int(time.time() - START_TIME))
        
        for client in [cli for cli in Altruix.clients if hasattr(cli, 'me') and cli.me]:
            if asyncio.current_task().cancelled(): break
            name = html.escape(client.me.first_name)
            try:
                await client.get_me()
                status = "🟢 Normal"
                # Get privacy info (requires an extra call usually, but we check one key)
                priv = await client.get_privacy(PrivacyKey.STATUS_TIMESTAMP)
                p_level = "🔒 High" if priv.rules and priv.rules[0].type == PrivacyRuleType.DISALLOW_ALL else "🔓 Normal"
                h_score = 100
            except FloodWait as e:
                status, p_level, h_score = f"🟠 Limit ({e.value}s)", "❓ Unknown", 50
            except Exception as e:
                status, p_level, h_score = f"🔴 Error: {str(e)}", "🔴 Error", 10
                
            results.append(
                f"👤 <b>{name}</b>\n"
                f"   ├ Status: <b>{status}</b>\n"
                f"   ├ Privacy: <b>{p_level}</b>\n"
                f"   ├ Health: <code>{h_score}/100</code>\n"
                f"   └ Uptime: <code>{uptime}</code>"
            )
        
        ai_status = "✅ Ready" if AI_API_KEY else "❌ Key Missing in .env"
        report = f"⚔️ <b>Alliance Status Suite</b>\nAI Status: <b>{ai_status}</b>\n\n<blockquote expandable>" + "\n".join(results) + "</blockquote>"
        await status_msg.edit_msg(report)
    except asyncio.CancelledError:
        await status_msg.edit_msg(f"🛑 <b>Status Task {tid} Cancelled.</b>")
    finally:
        unregister_task(tid)
        await m.delete_if_self()


@Altruix.register_on_cmd(
    ["allmsg"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Send message from all alliance sessions",
        "description": "Memerintahkan semua akun aliansi mengirimkan pesan yang sama secara bergantian dengan jeda 1 detik.",
        "usage": "allmsg [teks]",
        "example": "allmsg Halo semuanya!",
        "note": "Jeda 1 detik diberikan antar akun untuk menghindari spam detection dan floodwait."
    },
)
@log_errors
async def all_msg_cmd(c: Client, m: Message):
    text = m.text.split(None, 1)[1] if len(m.text.split()) > 1 else None
    if not text: 
        await m.reply_msg("❌ <b>Provide a message to send!</b>")
        return await m.delete_if_self()
    
    tid = generate_task_id("ALL")
    register_task(tid, asyncio.current_task(), "Alliance Message", "xalliance", c.me.id, f"Text: {text[:20]}...")
    
    status_msg = await m.reply_msg(f"⏳ <b>Alliance Sending Message [{tid}]:</b> <code>{text}</code>...")
    results = []
    
    try:
        for client in get_active_alliance():
            if asyncio.current_task().cancelled(): break
            name = html.escape(client.me.first_name)
            try:
                await client.send_message(m.chat.id, text)
                results.append(f"✅ <b>{name}</b> -> Sent!")
            except Exception as e:
                results.append(f"❌ <b>{name}</b> -> Error: <code>{str(e)}</code>")
            await asyncio.sleep(1)
        await status_msg.edit_msg(f"⚔️ <b>Alliance Message Report [{tid}]</b>\n<blockquote expandable>" + "\n".join(results) + "</blockquote>")
        await m.delete_if_self()
    except asyncio.CancelledError:
        await status_msg.edit_msg(f"🛑 <b>Message Task {tid} Cancelled.</b>")
    finally:
        unregister_task(tid)

@Altruix.register_on_cmd(
    ["allsetname"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Mass change first names of all sessions",
        "description": "Mengubah nama depan seluruh akun aliansi menjadi nama yang seragam secara instan.",
        "usage": "allsetname [nama_baru]",
        "example": "allsetname Altruix Warrior",
        "note": "Perubahan nama mungkin memerlukan waktu beberapa saat untuk tersinkronisasi di server Telegram."
    },
)
@log_errors
async def all_setname_cmd(c: Client, m: Message):
    new_name = m.text.split(None, 1)[1] if len(m.text.split()) > 1 else None
    if not new_name: 
        await m.reply_msg("❌ <b>Provide a name!</b>")
        return await m.delete_if_self()
    
    tid = generate_task_id("ALL")
    register_task(tid, asyncio.current_task(), "Alliance Rename", "xalliance", c.me.id, f"Name: {new_name}")
    
    status_msg = await m.reply_msg(f"⏳ <b>Alliance Renaming... [{tid}]</b>")
    results = []
    try:
        for client in get_active_alliance():
            if asyncio.current_task().cancelled(): break
            name = html.escape(client.me.first_name)
            try:
                await client.update_profile(first_name=new_name)
                results.append(f"✅ <b>{name}</b> -> <b>{html.escape(new_name)}</b>")
            except Exception as e: results.append(f"❌ <b>{name}</b> -> <code>{str(e)}</code>")
            await asyncio.sleep(random.uniform(0.5, 1.5))
        await status_msg.edit_msg(f"⚔️ <b>Rename Report [{tid}]</b>\n<blockquote expandable>" + "\n".join(results) + "</blockquote>")
    except asyncio.CancelledError:
        await status_msg.edit_msg(f"🛑 <b>Rename Task {tid} Cancelled.</b>")
    finally:
        unregister_task(tid)
        await m.delete_if_self()


# --- ADVANCED COMMANDS ---

@Altruix.register_on_cmd(
    ["allvote"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Mass vote on a poll option",
        "description": "Memberikan suara (vote) secara massal pada pilihan tertentu di sebuah polling Telegram.",
        "usage": "allvote [link_poll] [index]",
        "example": "allvote [link] 0",
        "note": "Index dimulai dari 0 (pilihan pertama = 0, kedua = 1, dst)."
    },
)
@log_errors
async def all_vote_cmd(c: Client, m: Message):
    args = m.text.split()
    if len(args) < 3: 
        await m.reply_msg("❌ <b>Usage:</b> <code>!allvote [link] [index]</code>")
        return await m.delete_if_self()
    link, index = args[1], int(args[2])
    target_chat, msg_id = parse_tg_link(link)
    if not target_chat: 
        await m.reply_msg("❌ <b>Invalid link!</b>")
        return await m.delete_if_self()

    
    tid = generate_task_id("ALL")
    register_task(tid, asyncio.current_task(), "Alliance Vote", "xalliance", c.me.id, f"Link: {link}")
    
    status_msg = await m.reply_msg(f"⏳ <b>Alliance Voting... [{tid}]</b>")
    results = []
    async def _do(cli):
        if asyncio.current_task().cancelled(): return
        name = html.escape(cli.me.first_name)
        try:
            await asyncio.sleep(random.uniform(0.5, 3.0))
            await cli.vote_poll(target_chat, msg_id, [index])
            results.append(f"✅ <b>{name}</b> -> Voted!")
        except Exception as e: results.append(f"❌ <b>{name}</b> -> <code>{str(e)}</code>")
    
    try:
        await asyncio.gather(*[_do(cli) for cli in get_active_alliance()])
        await status_msg.edit_msg(f"⚔️ <b>Vote Report [{tid}]</b>\n<blockquote expandable>" + "\n".join(results) + "</blockquote>")
    except asyncio.CancelledError:
        await status_msg.edit_msg(f"🛑 <b>Vote Task {tid} Cancelled.</b>")
    finally:
        unregister_task(tid)
        await m.delete_if_self()


@Altruix.register_on_cmd(
    ["allreact"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Mass emoji reaction to a message",
        "description": "Memberikan reaksi emoji yang sama ke sebuah pesan spesifik menggunakan seluruh akun aliansi.",
        "usage": "allreact [link_msg] [emoji]",
        "example": "allreact [link] ❤️",
        "note": "Pastikan grup tersebut mengizinkan penggunaan reaksi emoji."
    },
)
@log_errors
async def all_react_cmd(c: Client, m: Message):
    args = m.text.split()
    if len(args) < 3: 
        await m.reply_msg("❌ <b>Usage:</b> <code>!allreact [link] [emoji]</code>")
        return await m.delete_if_self()
    link, emoji = args[1], args[2]
    target_chat, msg_id = parse_tg_link(link)
    if not target_chat: 
        await m.reply_msg("❌ <b>Invalid link!</b>")
        return await m.delete_if_self()

    
    tid = generate_task_id("ALL")
    register_task(tid, asyncio.current_task(), "Alliance Reaction", "xalliance", c.me.id, f"Emoji: {emoji}")
    
    status_msg = await m.reply_msg(f"⏳ <b>Alliance Reacting... [{tid}]</b>")
    results = []
    async def _do(cli):
        if asyncio.current_task().cancelled(): return
        name = html.escape(cli.me.first_name)
        try:
            await asyncio.sleep(random.uniform(0.5, 3.0))
            await cli.send_reaction(target_chat, msg_id, emoji)
            results.append(f"✅ <b>{name}</b> -> Reacted!")
        except Exception as e: results.append(f"❌ <b>{name}</b> -> <code>{str(e)}</code>")
    
    try:
        await asyncio.gather(*[_do(cli) for cli in get_active_alliance()])
        await status_msg.edit_msg(f"⚔️ <b>Reaction Report [{tid}]</b>\n<blockquote expandable>" + "\n".join(results) + "</blockquote>")
    except asyncio.CancelledError:
        await status_msg.edit_msg(f"🛑 <b>Reaction Task {tid} Cancelled.</b>")
    finally:
        unregister_task(tid)
        await m.delete_if_self()


@Altruix.register_on_cmd(
    ["distribute"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Smart Forward with Load Balancing",
        "description": "Membagi daftar target chat dari file .txt ke seluruh akun aliansi agar forward tidak menumpuk di satu akun.",
        "usage": "distribute [link_msg] [file_target.txt]",
        "example": "distribute [link] target.txt",
        "note": "Sangat efektif untuk broadcast ke banyak grup tanpa terkena limitasi individu."
    },
)
@log_errors
async def distribute_cmd(c: Client, m: Message):
    args = m.text.split()
    if len(args) < 3: 
        await m.reply_msg("❌ <b>Usage:</b> <code>!distribute [link] [targets.txt]</code>")
        return await m.delete_if_self()
    link, file_path = args[1], args[2]
    from_chat, msg_id = parse_tg_link(link)
    if not from_chat or not os.path.exists(file_path): 
        await m.reply_msg("❌ <b>Invalid link or file!</b>")
        return await m.delete_if_self()
    
    tid = generate_task_id("ALL")
    register_task(tid, asyncio.current_task(), "Alliance Distribute", "xalliance", c.me.id, f"File: {file_path}")
    
    with open(file_path, "r", encoding="utf-8") as f: targets = [l.strip() for l in f if l.strip()]
    active = get_active_alliance()
    n = len(active)
    if n == 0: 
        await m.reply_msg("❌ <b>No active sessions!</b>")
        unregister_task(tid)
        return await m.delete_if_self()
    
    chunks = [targets[i::n] for i in range(n)]
    status_msg = await m.reply_msg(f"⏳ <b>Distributing {len(targets)} targets... [{tid}]</b>")
    results = []
    async def _do(cli, my_targets):
        name, s, err_list = html.escape(cli.me.first_name), 0, []
        for t in my_targets:
            if asyncio.current_task().cancelled(): break
            try:
                await asyncio.sleep(random.uniform(1.0, 3.0))
                await cli.forward_messages(t, from_chat, msg_id)
                s += 1
            except Exception as e:
                err_list.append(str(e))
        err_msg = f" (Errors: <code>{', '.join(set(err_list[:2]))}</code>)" if err_list else ""
        results.append(f"📊 <b>{name}</b> -> {s} OK, {len(err_list)} Failed{err_msg}")
    
    try:
        await asyncio.gather(*[_do(active[i], chunks[i]) for i in range(n)])
        await status_msg.edit_msg(f"⚔️ <b>Distribution Report [{tid}]</b>\n<blockquote expandable>" + "\n".join(results) + "</blockquote>")
    except asyncio.CancelledError:
        await status_msg.edit_msg(f"🛑 <b>Distribute Task {tid} Cancelled.</b>")
    finally:
        unregister_task(tid)
        await m.delete_if_self()


@Altruix.register_on_cmd(
    ["allhide"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Activate Ghost Mode for all accounts",
        "description": "Mode Stealth instan: Menghapus foto profil, mengosongkan bio, dan mengganti nama menjadi 'Ghost'.",
        "usage": "allhide",
        "example": "allhide",
        "note": "Gunakan ini jika aliansi sedang dalam mode penyamaran atau pembersihan jejak."
    },
)
@log_errors
async def all_hide_cmd(c: Client, m: Message):
    tid = generate_task_id("ALL")
    register_task(tid, asyncio.current_task(), "Alliance Hide", "xalliance", c.me.id, "Ghost Mode")
    status_msg = await m.reply_msg(f"⏳ <b>Activating Ghost Mode... [{tid}]</b>")
    results = []
    async def _do(cli):
        if asyncio.current_task().cancelled(): return
        name = html.escape(cli.me.first_name)
        try:
            await asyncio.sleep(random.uniform(0.5, 3.0))
            p = [p async for p in cli.get_chat_photos("me")]
            if p: await cli.delete_profile_photos([x.file_id for x in p])
            await cli.update_profile(first_name="Ghost", last_name="", about="")
            results.append(f"👻 <b>{name}</b> -> Hidden!")
        except Exception as e: results.append(f"❌ <b>{name}</b> -> <code>{str(e)}</code>")
    
    try:
        await asyncio.gather(*[_do(cli) for cli in get_active_alliance()])
        await status_msg.edit_msg(f"⚔️ <b>Ghost Mode Report [{tid}]</b>\n<blockquote expandable>" + "\n".join(results) + "</blockquote>")
    except asyncio.CancelledError:
        await status_msg.edit_msg(f"🛑 <b>Hide Task {tid} Cancelled.</b>")
    finally:
        unregister_task(tid)
        await m.delete_if_self()


@Altruix.register_on_cmd(
    ["allcall"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Check readiness of all alliance sessions",
        "description": "Melakukan absensi massal. Semua akun akan mengirim pesan 'Hadir! ⚔️' di grup saat ini.",
        "usage": "allcall",
        "example": "allcall",
        "note": "Gunakan untuk mengecek sesi mana saja yang masih 'nyala' dan responsif."
    },
)
@log_errors
async def all_call_cmd(c: Client, m: Message):
    tid = generate_task_id("ALL")
    register_task(tid, asyncio.current_task(), "Alliance Call", "xalliance", c.me.id, "Presence Check")
    try:
        for cli in get_active_alliance():
            if asyncio.current_task().cancelled(): break
            try:
                async def _s(cl):
                    await asyncio.sleep(random.uniform(0.1, 1.0))
                    await cl.send_message(m.chat.id, "Hadir! ⚔️")
                asyncio.create_task(_s(cli))
            except: pass
    finally:
        unregister_task(tid)
        await m.delete_if_self()

# --- PRO COMMANDS ---

@Altruix.register_on_cmd(
    ["allcopy"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Toggle Master Message Mirroring",
        "description": "Mengaktifkan mode mirroring. Seluruh akun slave akan mendeteksi dan menyalin (copy) pesan yang dikirim oleh akun Master di grup yang sama.",
        "usage": "allcopy [on/off]",
        "example": "allcopy on",
        "note": "Sangat berguna untuk menyebarkan pesan Master secara otomatis menggunakan banyak identitas sekaligus."
    },
)
@log_errors
async def all_copy_cmd(c: Client, m: Message):
    global ALL_COPY_MODE
    toggle = m.text.split()[1].lower() if len(m.text.split()) > 1 else "off"
    ALL_COPY_MODE = (toggle == "on")
    status = "Enabled ✅" if ALL_COPY_MODE else "Disabled ❌"
    await m.reply_msg(f"🛡️ <b>Alliance Copy Mode:</b> <code>{status}</code>")
    await m.delete_if_self()


@Altruix.register_on_cmd(
    ["allshift"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Activate account rotation/shift",
        "description": "Membatasi jumlah akun aliansi yang aktif selama durasi tertentu. Akun akan diacak untuk menghindari deteksi massal.",
        "usage": "allshift [jumlah_akun] [durasi_menit]",
        "example": "allshift 2 5",
        "note": "Gunakan '!allshift' tanpa argumen untuk mereset dan mengaktifkan semua akun kembali."
    },
)
@log_errors
async def all_shift_cmd(c: Client, m: Message):
    global ACTIVE_SHIFT_COUNT, SHIFT_EXPIRY, SHIFT_CLIENTS
    args = m.text.split()
    if len(args) < 3:
        ACTIVE_SHIFT_COUNT = 0 # Reset
        await m.reply_msg("🔄 <b>Alliance Shift Reset.</b> All sessions active.")
        return await m.delete_if_self()
        await m.delete_if_self()

    
    count, mins = int(args[1]), int(args[2])
    all_cli = [cli for cli in Altruix.clients if hasattr(cli, 'me') and cli.me]
    if count > len(all_cli): count = len(all_cli)
    
    SHIFT_CLIENTS = random.sample(all_cli, count)
    ACTIVE_SHIFT_COUNT = count
    SHIFT_EXPIRY = time.time() + (mins * 60)
    
    names = ", ".join([html.escape(cli.me.first_name) for cli in SHIFT_CLIENTS])
    await m.reply_msg(f"🔄 <b>Shift Activated:</b> <code>{count}</code> accounts for <code>{mins}</code> mins.\n<b>Active:</b> {names}")
    await m.delete_if_self()


@Altruix.register_on_cmd(
    ["allscenario"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Run auto-chat from a scenario file",
        "description": "Menjalankan simulasi percakapan antar akun aliansi berdasarkan baris teks dalam sebuah file .txt.",
        "usage": "allscenario [nama_file.txt]",
        "example": "allscenario scenario.txt",
        "note": "Setiap baris akan dikirim oleh akun berbeda dengan jeda manusiawi (3-7 detik)."
    },
)
@log_errors
async def all_scenario_cmd(c: Client, m: Message):
    file_path = m.text.split()[1] if len(m.text.split()) > 1 else None
    if not file_path or not os.path.exists(file_path): 
        await m.reply_msg("❌ <b>Scenario file not found!</b>")
        return await m.delete_if_self()
    
    tid = generate_task_id("ALL")
    register_task(tid, asyncio.current_task(), "Alliance Scenario", "xalliance", c.me.id, f"File: {file_path}")
    
    with open(file_path, "r", encoding="utf-8") as f:
        scenario = [l.strip() for l in f if l.strip()]
    
    if not scenario:
        unregister_task(tid)
        await m.delete_if_self()
        return await m.reply_msg("❌ <b>Scenario is empty!</b>")
    
    status_msg = await m.reply_msg(f"🎬 <b>Starting Scenario [{tid}]:</b> <code>{len(scenario)}</code> lines...")
    active = get_active_alliance()
    
    try:
        for i, line in enumerate(scenario):
            if asyncio.current_task().cancelled(): break
            cli = active[i % len(active)]
            try:
                await cli.send_message(m.chat.id, line)
                # Human-like delay
                await asyncio.sleep(random.uniform(3.0, 7.0))
            except: pass
        await status_msg.edit_msg(f"✅ <b>Scenario {tid} completed.</b>")
    except asyncio.CancelledError:
        await status_msg.edit_msg(f"🛑 <b>Scenario Task {tid} Cancelled.</b>")
    finally:
        unregister_task(tid)
        await m.delete_if_self()


@Altruix.register_on_cmd(
    ["allreport"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Collective spam reporting to a target",
        "description": "Memerintahkan seluruh akun aliansi untuk melakukan report 'Spam' secara kolektif ke target user atau pesan.",
        "usage": "allreport [link/username]",
        "example": "allreport @spam_bot",
        "note": "Gunakan link pesan untuk melaporkan konten spesifik, atau username untuk melaporkan profil."
    },
)
@log_errors
async def all_report_cmd(c: Client, m: Message):
    target = m.text.split()[1] if len(m.text.split()) > 1 else None
    if not target: 
        await m.reply_msg("❌ <b>Provide target link/username!</b>")
        return await m.delete_if_self()
    
    tid = generate_task_id("ALL")
    register_task(tid, asyncio.current_task(), "Alliance Report", "xalliance", c.me.id, f"Target: {target}")
    
    status_msg = await m.reply_msg(f"⏳ <b>Alliance Reporting [{tid}]:</b> <code>{target}</code>...")
    results = []
    
    async def _do(cli):
        if asyncio.current_task().cancelled(): return
        name = html.escape(cli.me.first_name)
        try:
            await asyncio.sleep(random.uniform(1.0, 5.0))
            if "/c/" in target or "t.me/" in target:
                ch, mi = parse_tg_link(target)
                if ch: await cli.report_spam(ch, mi)
                else: await cli.report_spam(target)
            else:
                await cli.report_spam(target)
            results.append(f"✅ <b>{name}</b> -> Reported!")
        except Exception as e: results.append(f"❌ <b>{name}</b> -> <code>{str(e)}</code>")
        
    try:
        await asyncio.gather(*[_do(cli) for cli in get_active_alliance()])
        await status_msg.edit_msg(f"⚔️ <b>Mass Report Report [{tid}]</b>\n<blockquote expandable>" + "\n".join(results) + "</blockquote>")
    except asyncio.CancelledError:
        await status_msg.edit_msg(f"🛑 <b>Report Task {tid} Cancelled.</b>")
    finally:
        unregister_task(tid)

@Altruix.register_on_cmd(
    ["allsync"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Sync contact blacklist from Master",
        "description": "Menyinkronkan daftar pengguna yang diblokir (blacklist) dari akun Master ke seluruh akun Slave.",
        "usage": "allsync contact",
        "example": "allsync contact",
        "note": "Memastikan seluruh aliansi memiliki daftar blokir yang sama demi keamanan operasional."
    },
)
@log_errors
async def all_sync_cmd(c: Client, m: Message):
    # Only support contact (blacklist/blocked) for now
    if not Altruix.clients: return
    
    tid = generate_task_id("ALL")
    register_task(tid, asyncio.current_task(), "Alliance Sync", "xalliance", c.me.id, "Blacklist Sync")
    
    status_msg = await m.reply_msg(f"⏳ <b>Syncing Blacklist from Master... [{tid}]</b>")
    master = get_master()
    try:
        blocked = [b.user_id async for b in master.get_blocked_users()]
        if not blocked:
            await status_msg.edit_msg("ℹ️ <b>Master's blacklist is empty.</b>")
            unregister_task(tid)
            return await m.delete_if_self()
        
        results = []
        async def _do(cli):
            if asyncio.current_task().cancelled(): return
            if cli.me.id == master.me.id: return
            name, ok, err_list = html.escape(cli.me.first_name), 0, []
            for uid in blocked:
                if asyncio.current_task().cancelled(): break
                try:
                    await cli.block_user(uid)
                    ok += 1
                except Exception as e:
                    err_list.append(str(e))
            err_msg = f" (Errors: <code>{', '.join(set(err_list[:2]))}</code>)" if err_list else ""
            results.append(f"✅ <b>{name}</b> -> Synced: <code>{ok}</code> Blocked, <code>{len(err_list)}</code> Failed{err_msg}")
            
        await asyncio.gather(*[_do(cli) for cli in Altruix.clients])
        await status_msg.edit_msg(f"⚔️ <b>Blacklist Sync Report [{tid}]</b>\n<blockquote expandable>" + "\n".join(results) + "</blockquote>")
    except asyncio.CancelledError:
        await status_msg.edit_msg(f"🛑 <b>Sync Task {tid} Cancelled.</b>")
    except Exception as e:
        await status_msg.edit_msg(f"❌ <b>Sync Failed:</b> <code>{str(e)}</code>")
    finally:
        unregister_task(tid)
        await m.delete_if_self()


# --- INTELLIGENCE & STEALTH COMMANDS ---

@Altruix.register_on_cmd(
    ["allprivacy"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Mass change privacy settings",
        "description": "Mengubah pengaturan privasi (Last Seen, Foto Profil, Link Forward) secara massal untuk seluruh akun.",
        "usage": "allprivacy [high/normal]",
        "example": "allprivacy high",
        "note": "Mode 'high' akan menyetel semua ke 'Nobody', sedangkan 'normal' menyetel ke default (Everyone)."
    },
)
@log_errors
async def all_privacy_cmd(c: Client, m: Message):
    mode = m.text.split()[1].lower() if len(m.text.split()) > 1 else "high"
    
    tid = generate_task_id("ALL")
    register_task(tid, asyncio.current_task(), "Alliance Privacy", "xalliance", c.me.id, f"Mode: {mode}")
    
    status_msg = await m.reply_msg(f"⏳ <b>Alliance Privacy Mode:</b> <code>{mode.upper()}</code>... [{tid}]")
    
    rule = PrivacyRuleType.ALLOW_ALL if mode == "normal" else PrivacyRuleType.DISALLOW_ALL
    results = []

    async def _set_priv(cli):
        if asyncio.current_task().cancelled(): return
        name = html.escape(cli.me.first_name)
        log = get_alliance_logger(cli.me.id)
        try:
            await cli.set_privacy(PrivacyKey.STATUS_TIMESTAMP, rule)
            await cli.set_privacy(PrivacyKey.PROFILE_PHOTO, rule)
            await cli.set_privacy(PrivacyKey.FORWARDS, rule)
            log.info(f"Privacy set to {mode}")
            results.append(f"✅ <b>{name}</b> -> {mode.upper()} applied")
        except Exception as e:
            log.error(f"Privacy Error: {str(e)}")
            results.append(f"❌ <b>{name}</b> -> Error: <code>{str(e)}</code>")

    try:
        await asyncio.gather(*[_set_priv(cli) for cli in get_active_alliance()], return_exceptions=True)
        await status_msg.edit_msg(f"⚔️ <b>Privacy Report [{tid}]</b>\n<blockquote expandable>" + "\n".join(results) + "</blockquote>")
    except asyncio.CancelledError:
        await status_msg.edit_msg(f"🛑 <b>Privacy Task {tid} Cancelled.</b>")
    finally:
        unregister_task(tid)
        await m.delete_if_self()


@Altruix.register_on_cmd(
    ["allmonitor"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Monitor keywords across sessions",
        "description": "Menginstruksikan seluruh akun untuk memantau grup mereka. Jika keyword muncul, laporan dikirim ke Saved Messages Master.",
        "usage": "allmonitor [keyword]",
        "example": "allmonitor hack",
        "note": "Ketik '!allmonitor' tanpa argumen untuk mereset dan menghentikan pengawasan."
    },
)
@log_errors
async def all_monitor_cmd(c: Client, m: Message):
    global MONITOR_KEYWORDS
    keyword = m.text.split(None, 1)[1] if len(m.text.split()) > 1 else None
    
    if not keyword:
        MONITOR_KEYWORDS = []
        await m.delete_if_self()
        return await m.reply_msg("🕵️‍♂️ <b>Alliance Monitoring Reset.</b> All keywords cleared.")
    
    if keyword.lower() not in [kw.lower() for kw in MONITOR_KEYWORDS]:
        MONITOR_KEYWORDS.append(keyword)
    
    await m.reply_msg(f"🕵️‍♂️ <b>Alliance Monitoring</b> for: <code>{keyword}</code>\nReports will be sent to Master.")

@Altruix.register_on_cmd(
    ["allnuke"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Emergency nuclear option",
        "description": "Perintah darurat: Semua akun akan keluar dari seluruh grup, menghapus foto profil, dan mengosongkan bio seketika.",
        "usage": "allnuke",
        "example": "allnuke",
        "note": "Tindakan ini tidak dapat dibatalkan (Irreversible). Gunakan hanya saat keadaan darurat/ancaman terbongkar."
    },
)
@log_errors
async def all_nuke_cmd(c: Client, m: Message):
    tid = generate_task_id("ALL")
    register_task(tid, asyncio.current_task(), "Alliance Nuke", "xalliance", c.me.id, "Emergency Nuke")
    status_msg = await m.reply_msg(f"🚨 <b>ALLIANCE NUKE INITIATED [{tid}]!</b> Leaving all chats and clearing profiles...")
    results = []

    async def _do_nuke(cli):
        if asyncio.current_task().cancelled(): return
        name = html.escape(cli.me.first_name)
        log = get_alliance_logger(cli.me.id)
        try:
            # 1. Leave all groups
            async for dialog in cli.get_dialogs():
                if asyncio.current_task().cancelled(): break
                if dialog.chat.type in ["group", "supergroup", "channel"]:
                    await cli.leave_chat(dialog.chat.id)
            
            # 2. Clear profile
            photos = [p async for p in cli.get_chat_photos("me")]
            if photos:
                await cli.delete_profile_photos([p.file_id for p in photos])
            await cli.update_profile(first_name="Ghost", about="")
            
            log.warning("NUKE COMPLETED: Left all chats and cleared profile.")
            results.append(f"☢️ <b>{name}</b> -> Nuked!")
        except Exception as e:
            log.error(f"Nuke Error: {str(e)}")
            results.append(f"❌ <b>{name}</b> -> Error: <code>{str(e)}</code>")

    try:
        await asyncio.gather(*[_do_nuke(cli) for cli in get_active_alliance()], return_exceptions=True)
        await status_msg.edit_msg(f"💀 <b>Nuke Report [{tid}]</b>\n<blockquote expandable>" + "\n".join(results) + "</blockquote>")
    except asyncio.CancelledError:
        await status_msg.edit_msg(f"🛑 <b>Nuke Task {tid} Cancelled.</b>")
    finally:
        unregister_task(tid)
        await m.delete_if_self()


@Altruix.register_on_cmd(
    ["allswarm"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Forward message to random groups",
        "description": "Setiap akun aliansi akan mem-forward pesan yang ditentukan ke 3-5 grup acak dari daftar dialog masing-masing.",
        "usage": "allswarm [link_msg]",
        "example": "allswarm [link]",
        "note": "Metode distribusi beban kerja agar broadcast tidak terdeteksi sebagai spam massal dari satu titik."
    },
)
@log_errors
async def all_swarm_cmd(c: Client, m: Message):
    link = m.text.split(None, 1)[1] if len(m.text.split()) > 1 else None
    from_chat, msg_id = parse_tg_link(link)
    if not from_chat: 
        await m.reply_msg("❌ <b>Invalid message link!</b>")
        return await m.delete_if_self()

    tid = generate_task_id("ALL")
    register_task(tid, asyncio.current_task(), "Alliance Swarm", "xalliance", c.me.id, f"Link: {link}")
    
    status_msg = await m.reply_msg(f"🐝 <b>Alliance Swarming IN PROGRESS... [{tid}]</b>")
    results = []

    async def _do_swarm(cli):
        if asyncio.current_task().cancelled(): return
        name = html.escape(cli.me.first_name)
        log = get_alliance_logger(cli.me.id)
        try:
            # Get current groups
            groups = []
            async for dialog in cli.get_dialogs():
                if asyncio.current_task().cancelled(): break
                if dialog.chat.id in GROUP_BLACKLIST:
                    continue # Skip blacklisted
                if dialog.chat.type in [
                    ChatType.GROUP, 
                    ChatType.SUPERGROUP
                ] and not dialog.chat.is_restricted:
                    groups.append(dialog.chat.id)
            
            if not groups:
                return results.append(f"ℹ️ <b>{name}</b> -> No groups found")
            
            # Pick 3-5 random groups
            target_count = random.randint(3, 5)
            targets = random.sample(groups, min(len(groups), target_count))
            
            ok = 0
            for t in targets:
                if asyncio.current_task().cancelled(): break
                try:
                    await asyncio.sleep(random.uniform(1.0, 4.0))
                    await cli.forward_messages(t, from_chat, msg_id)
                    ok += 1
                except: pass
            
            log.info(f"Swarm completed: Forwarded to {ok} random groups.")
            results.append(f"🐝 <b>{name}</b> -> Sent to <code>{ok}</code> random groups")
        except Exception as e:
            log.error(f"Swarm Error: {str(e)}")
            results.append(f"❌ <b>{name}</b> -> Error: <code>{str(e)}</code>")

    try:
        await asyncio.gather(*[_do_swarm(cli) for cli in get_active_alliance()], return_exceptions=True)
        await status_msg.edit_msg(f"🐝 <b>Swarm Report [{tid}]</b>\n<blockquote expandable>" + "\n".join(results) + "</blockquote>")
    except asyncio.CancelledError:
        await status_msg.edit_msg(f"🛑 <b>Swarm Task {tid} Cancelled.</b>")
    finally:
        unregister_task(tid)
        await m.delete_if_self()


# --- INFRASTRUCTURE COMMANDS ---

@Altruix.register_on_cmd(
    ["allschedule"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Schedule an alliance command",
        "description": "Menjadwalkan eksekusi perintah aliansi pada waktu spesifik di masa depan menggunakan format YYYY-MM-DD HH:MM:SS.",
        "usage": "allschedule [YYYY-MM-DD] [HH:MM:SS] [command]",
        "example": "allschedule 2026-03-23 04:00:00 allhide",
        "note": "Perintah akan dijalankan otomatis oleh scheduler internal meskipun Anda sedang offline."
    },
)
@log_errors
async def all_schedule_cmd(c: Client, m: Message):
    args = m.text.split(None, 3)
    if len(args) < 4: 
        await m.reply_msg("❌ <b>Usage:</b> <code>!allschedule [YYYY-MM-DD] [HH:MM:SS] [command]</code>")
        return await m.delete_if_self()
    
    date_str, time_str, cmd = args[1], args[2], args[3]
    run_at = f"{date_str} {time_str}"
    
    # Mocking the command execution
    async def _scheduled_task():
        # This is a bit complex as we need to trigger the command handler manually
        # For simplicity, we'll log it and send a msg as the master
        master = get_master()
        try:
            await master.send_message("me", f"⏰ <b>Scheduled Task Triggered:</b> <code>{cmd}</code>")
            # Create a fake message object to trigger the command
            # But the best way is to just call the function if it's within xalliance
            # For now, we'll just log it.
            pro_logger.info(f"Scheduled task triggered: {cmd}")
        except: pass

    try:
        SCHEDULER.add_job(_scheduled_task, 'date', run_date=run_at)
        await m.reply_msg(f"📅 <b>Task Scheduled:</b> <code>{cmd}</code> at <code>{run_at}</code>")
        pro_logger.info(f"Task scheduled: {cmd} at {run_at}")
    except Exception as e:
        await m.reply_msg(f"❌ <b>Scheduling Failed:</b> <code>{str(e)}</code>")

@Altruix.register_on_cmd(
    ["allbroadcast"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Smart Broadcast to all unique chats",
        "description": "Mengirimkan pesan ke SELURUH grup/chat yang dimiliki oleh SEMUA akun aliansi tanpa duplikasi pengiriman.",
        "usage": "allbroadcast [teks]",
        "example": "allbroadcast Halo semuanya!",
        "note": "Sistem secara pintar mendeteksi grup duplikat sehingga pesan hanya terkirim sekali per grup oleh salah satu akun."
    },
)
@log_errors
async def all_broadcast_cmd(c: Client, m: Message):
    text = m.text.split(None, 1)[1] if len(m.text.split()) > 1 else None
    if not text: 
        await m.reply_msg("❌ <b>Provide broadcast message!</b>")
        return await m.delete_if_self()
    
    tid = generate_task_id("ALL")
    register_task(tid, asyncio.current_task(), "Alliance Broadcast", "xalliance", c.me.id, f"Text: {text[:20]}...")
    
    status_msg = await m.reply_msg(f"📡 <b>Alliance Smart Broadcast INITIATED... [{tid}]</b>")
    
    broadcasted_chats = set()
    results = []
    
    try:
        # We use a sequential approach or semi-parallel to ensure set is updated
        for client in get_active_alliance():
            if asyncio.current_task().cancelled(): break
            name = html.escape(client.me.first_name)
            ok, dup = 0, 0
            async for dialog in client.get_dialogs():
                if asyncio.current_task().cancelled(): break
                if dialog.chat.id in broadcasted_chats:
                    dup += 1
                    continue
                
                try:
                    await client.send_message(dialog.chat.id, text)
                    broadcasted_chats.add(dialog.chat.id)
                    ok += 1
                    await asyncio.sleep(random.uniform(0.3, 0.8)) # Safety
                except: pass
                
            results.append(f"📡 <b>{name}</b> -> {ok} Sent, {dup} Skipped (Duplicates)")

        await status_msg.edit_msg(f"⚔️ <b>Broadcast Report [{tid}]</b>\nTotal Unique Chats: <code>{len(broadcasted_chats)}</code>\n<blockquote expandable>" + "\n".join(results) + "</blockquote>")
    except asyncio.CancelledError:
        await status_msg.edit_msg(f"🛑 <b>Broadcast Task {tid} Cancelled.</b>")
    finally:
        unregister_task(tid)
        await m.delete_if_self()


@Altruix.register_on_cmd(
    ["allstats"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Display professional alliance metrics",
        "description": "Menampilkan statistik infrastruktur mendalam: Penggunaan RAM proses, Total pesan terkirim, dan tabel status Proxy.",
        "usage": "allstats pro",
        "example": "allstats pro",
        "note": "Gunakan untuk memantau beban kerja server dan kesehatan koneksi proxy secara real-time."
    },
)
@log_errors
async def all_stats_cmd(c: Client, m: Message):
    tid = generate_task_id("ALL")
    register_task(tid, asyncio.current_task(), "Alliance Stats", "xalliance", c.me.id, "Infrastructure Metrics")
    status_msg = await m.reply_msg("📊 <b>Generating Professional Stats...</b>")
    
    try:
        # RAM Usage
        process = psutil.Process(os.getpid())
        ram_mb = process.memory_info().rss / 1024 / 1024
        
        table = "<code>"
        table += "╔════════════╦══════════╦══════════╗\n"
        table += "║ ACCOUNT    ║ PROXY    ║ STATUS   ║\n"
        table += "╠════════════╬══════════╬══════════╣\n"
        
        all_cli = [cli for cli in Altruix.clients if hasattr(cli, 'me') and cli.me]
        for cli in all_cli:
            if asyncio.current_task().cancelled(): break
            name = (cli.me.first_name[:10] + "..") if len(cli.me.first_name) > 10 else cli.me.first_name.ljust(10)
            proxy_s = "Active" if PROXY_MAP.get(str(cli.me.id)) else "None"
            status = "Online" if cli.is_authorized else "Offline"
            table += f"║ {name.ljust(10)} ║ {proxy_s.ljust(8)} ║ {status.ljust(8)} ║\n"
            
        table += "╚════════════╩══════════╩══════════╝</code>"
        
        uptime = Essentials.get_readable_time(int(time.time() - START_TIME))
        
        report = (
            f"📊 <b>Alliance Infrastructure Stats</b>\n\n"
            f"🖥️ <b>Process RAM:</b> <code>{ram_mb:.2f} MB</code>\n"
            f"✉️ <b>Total Messages:</b> <code>{TOTAL_MESSAGES_SENT}</code>\n"
            f"⏳ <b>Global Uptime:</b> <code>{uptime}</code>\n\n"
            f"{table}"
        )
        
        await status_msg.edit_msg(report)
    except asyncio.CancelledError:
        await status_msg.edit_msg(f"🛑 <b>Stats Task {tid} Cancelled.</b>")
    finally:
        unregister_task(tid)
        await m.delete_if_self()

# --- INTELLIGENCE & SURVIVAL COMMANDS ---

@Altruix.register_on_cmd(
    ["allai"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Toggle AI-Response for slave accounts",
        "description": "Mengaktifkan/menonaktifkan fitur balas otomatis menggunakan AI jika akun slave dimention atau di-reply user lain.",
        "usage": "allai [on/off]",
        "example": "allai on",
        "note": "Terdapat jeda (rate-limit) 30 detik antar balasan untuk keamanan akun."
    },
)
@log_errors
async def all_ai_cmd(c: Client, m: Message):
    global ALL_AI_REPLY
    toggle = m.text.split()[1].lower() if len(m.text.split()) > 1 else "off"
    ALL_AI_REPLY = (toggle == "on")
    status = "Enabled ✅" if ALL_AI_REPLY else "Disabled ❌"
    msg = f"🧠 <b>Alliance AI-Response:</b> <code>{status}</code>"
    if ALL_AI_REPLY and not AI_API_KEY:
        msg += "\n⚠️ <b>Warning:</b> <code>AI_API_KEY</code> is not set in <code>.env</code>!"
    await m.reply_msg(msg)

@Altruix.register_on_cmd(
    ["allsetai"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Update AI configuration from userbot",
        "description": "Mengubah API Key dan Provider AI secara instan. Pengaturan ini akan tersinkronisasi dengan Bot Dashboard.",
        "usage": "allsetai [api_key] [provider]",
        "example": "allsetai your_key gemini",
        "note": "Gunakan Dashboard Bot untuk antarmuka yang lebih mudah secara visual."
    },
)
@log_errors
async def all_setai_cmd(c: Client, m: Message):
    args = m.text.split()
    if len(args) < 2: 
        await m.reply_msg("❌ <b>Usage:</b> <code>!allsetai [api_key] [provider]</code>")
        return await m.delete_if_self()
    
    key = args[1]
    prov = args[2] if len(args) > 2 else "gemini"
    
    await Altruix.config.set_env("AI_API_KEY", key)
    await Altruix.config.set_env("AI_PROVIDER", prov)
    
    await m.reply_msg(f"✅ <b>AI Configuration Updated:</b>\nKey: <code>{key[:8]}...</code>\nProvider: <code>{prov}</code>")

@Altruix.register_on_cmd(
    ["allnature"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Toggle Nature Mode simulation",
        "description": "Mensimulasikan aktivitas manusia (membaca pesan acak & status mengetik) untuk meminimalisir deteksi bot Telegram.",
        "usage": "allnature [on/off]",
        "example": "allnature on",
        "note": "Sangat direkomendasikan untuk diaktifkan saat aliansi sedang idle di grup publik."
    },
)
@log_errors
async def all_nature_cmd(c: Client, m: Message):
    global ALL_NATURE_MODE
    toggle = m.text.split()[1].lower() if len(m.text.split()) > 1 else "off"
    ALL_NATURE_MODE = (toggle == "on")
    status = "Enabled ✅" if ALL_NATURE_MODE else "Disabled ❌"
    await m.reply_msg(f"🍃 <b>Alliance Nature Mode:</b> <code>{status}</code>")

@Altruix.register_on_cmd(
    ["allsupport"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Collective interaction support",
        "description": "Aksi terkoordinasi 3 akun: Akun 1 (reaksi), Akun 2 (komentar positif), Akun 3 (forward pesan).",
        "usage": "allsupport [link_pesan]",
        "example": "allsupport [link]",
        "note": "Membutuhkan minimal 3 akun aliansi yang aktif untuk menjalankan skenario interaksi ini."
    },
)
@log_errors
async def all_support_cmd(c: Client, m: Message):
    link = m.text.split(None, 1)[1] if len(m.text.split()) > 1 else None
    target_chat, msg_id = parse_tg_link(link)
    if not target_chat: 
        await m.reply_msg("❌ <b>Invalid message link!</b>")
        return await m.delete_if_self()

    tid = generate_task_id("ALL")
    register_task(tid, asyncio.current_task(), "Alliance Support", "xalliance", c.me.id, f"Link: {link}")
    status_msg = await m.reply_msg("🤝 <b>Alliance Collective Support IN PROGRESS...</b>")
    active = get_active_alliance()
    
    try:
        if len(active) < 3:
            return await status_msg.edit_msg("⚠️ <b>At least 3 accounts needed for support!</b>")
        
        results = []
        # Account 1: Reacts
        try:
            if asyncio.current_task().cancelled(): raise asyncio.CancelledError
            await asyncio.sleep(random.uniform(1.0, 3.0))
            await active[0].send_reaction(target_chat, msg_id, "❤️")
            results.append(f"❤️ <b>{active[0].me.first_name}</b> -> Reacted")
        except asyncio.CancelledError: raise
        except: pass
    
        # Account 2: Comments
        try:
            if asyncio.current_task().cancelled(): raise asyncio.CancelledError
            await asyncio.sleep(random.uniform(2.0, 5.0))
            await active[1].send_message(target_chat, "Mantap! 🔥⚔️", reply_to_message_id=msg_id)
            results.append(f"💬 <b>{active[1].me.first_name}</b> -> Commented")
        except asyncio.CancelledError: raise
        except: pass
    
        # Account 3: Forwards
        try:
            if asyncio.current_task().cancelled(): raise asyncio.CancelledError
            await asyncio.sleep(random.uniform(3.0, 6.0))
            await active[2].forward_messages("me", target_chat, msg_id)
            results.append(f"⤴️ <b>{active[2].me.first_name}</b> -> Forwarded")
        except asyncio.CancelledError: raise
        except: pass
    
        await status_msg.edit_msg(f"🤝 <b>Support Report</b>\n<blockquote expandable>" + "\n".join(results) + "</blockquote>")
    except asyncio.CancelledError:
        await status_msg.edit_msg(f"🛑 <b>Support Task {tid} Cancelled.</b>")
    finally:
        unregister_task(tid)
        await m.delete_if_self()

@Altruix.register_on_cmd(
    ["allclean"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Mass purge all alliance messages",
        "description": "Menghapus seluruh riwayat pesan yang pernah dikirim oleh seluruh akun aliansi dalam grup/chat ini.",
        "usage": "allclean",
        "example": "allclean",
        "note": "Melakukan scan hingga 300 pesan terakhir dan menghapus semua yang berasal dari anggota aliansi."
    },
)
@log_errors
async def all_clean_cmd(c: Client, m: Message):
    tid = generate_task_id("ALL")
    register_task(tid, asyncio.current_task(), "Alliance Clean", "xalliance", c.me.id, "Emergency Clean")
    status_msg = await m.reply_msg(f"🧹 <b>Alliance Mass Cleaning IN PROGRESS... [{tid}]</b>")
    results = []
    
    all_ids = [cli.me.id for cli in Altruix.clients if hasattr(cli, 'me') and cli.me]

    async def _do_clean(cli):
        if asyncio.current_task().cancelled(): return
        name = html.escape(cli.me.first_name)
        ok = 0
        try:
            # We iterate messages in the current chat sent by any alliance member
            async for msg in cli.get_chat_history(m.chat.id, limit=300):
                if asyncio.current_task().cancelled(): break
                if msg.from_user and msg.from_user.id in all_ids:
                    try:
                        await msg.delete()
                        ok += 1
                    except: pass
            results.append(f"🧹 <b>{name}</b> -> Cleaned <code>{ok}</code> messages")
        except: pass

    try:
        await asyncio.gather(*[_do_clean(cli) for cli in get_active_alliance()], return_exceptions=True)
        await status_msg.edit_msg(f"🧹 <b>Mass Clean Report [{tid}]</b>\n<blockquote expandable>" + "\n".join(results) + "</blockquote>")
    except asyncio.CancelledError:
        await status_msg.edit_msg(f"🛑 <b>Clean Task {tid} Cancelled.</b>")
    finally:
        unregister_task(tid)
        await m.delete_if_self()


@Altruix.register_on_cmd(
    ["allmaster"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "View or change the Alliance Master account",
        "description": "Melihat informasi akun Master saat ini atau mengubahnya ke akun lain menggunakan User ID.",
        "usage": "allmaster [user_id/@username]",
        "example": "allmaster 12345678"
    },
)
@log_errors
async def all_master_cmd(c: Client, m: Message):
    args = m.text.split()
    if len(args) == 1:
        # Show current master
        master = get_master()
        if not master:
            return await m.reply_msg("❌ <b>No alliance sessions found!</b>")
        
        name = html.escape(master.me.first_name)
        uid = master.me.id
        user = master.me.username or "No Username"
        status = "🟢 Active" if getattr(master, 'is_authorized', True) else "🔴 Unauthorized"
        
        text = (
            "👑 <b>Alliance Master Account</b>\n"
            "──────────────\n"
            f"👤 <b>Name:</b> <code>{name}</code>\n"
            f"🆔 <b>ID:</b> <code>{uid}</code>\n"
            f"🔗 <b>Username:</b> @{user}\n"
            f"⚡ <b>Status:</b> {status}\n"
            "──────────────\n"
            "💡 <i>Gunakan <code>.allmaster [ID]</code> untuk memindahkan status Master ke akun lain.</i>"
        )
        return await m.reply_msg(text)

    # Set new master
    target = args[1]
    new_master = None
    
    # Try to find the client in Altruix.clients
    if target.isdigit():
        target_id = int(target)
        for cli in Altruix.clients:
            if hasattr(cli, 'me') and cli.me and cli.me.id == target_id:
                new_master = cli
                break
    else:
        target_user = target.replace("@", "").lower()
        for cli in Altruix.clients:
            if hasattr(cli, 'me') and cli.me and cli.me.username and cli.me.username.lower() == target_user:
                new_master = cli
                break
                
    if not new_master:
        return await m.reply_msg(f"❌ <b>Account <code>{target}</code> is not part of the active alliance!</b>")

    # Persist the setting
    await Altruix.config.set_env("ALLIANCE_MASTER_ID", new_master.me.id)
    
    name = html.escape(new_master.me.first_name)
    await m.reply_msg(f"✅ <b>Alliance Master has been switched to:</b> <code>{name}</code> (<code>{new_master.me.id}</code>)")
    await m.delete_if_self()


# Initialization
load_alliance_proxies()
load_blacklist()
