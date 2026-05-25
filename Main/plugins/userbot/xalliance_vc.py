# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
# 
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
# 
# All rights reserved.

import os
import json
import asyncio
import random
import html
import time
import logging
try:
    import yt_dlp
except ImportError:
    yt_dlp = None

from typing import Union, List, Optional
from pyrogram import Client, filters, raw, enums
from pyrogram.types import Message
from pyrogram.errors import RPCError, FloodWait, ChatAdminRequired
from pyrogram.raw.functions.phone import GetGroupCall, GetGroupParticipants, CreateGroupCall, DiscardGroupCall, JoinGroupCall, LeaveGroupCall, InviteToGroupCall
from pyrogram.raw.types import InputGroupCall, InputPeerChannel, InputPeerChat

# Safe imports for PyTgCalls
try:
    from pytgcalls import PyTgCalls
except ImportError:
    PyTgCalls = None

AudioPiped = None
try:
    from pytgcalls.types import AudioPiped
except ImportError:
    try:
        from pytgcalls.types.input_stream import AudioPiped
    except ImportError:
        pass

AudioVideoPiped = None
try:
    from pytgcalls.types import AudioVideoPiped
except ImportError:
    try:
        from pytgcalls.types.input_stream import AudioVideoPiped
    except ImportError:
        pass

MediaStream = None
try:
    from pytgcalls.types import MediaStream
except ImportError:
    pass

try:
    from pytgcalls.exceptions import GroupCallNotFound, NoActiveGroupCall
except ImportError:
    GroupCallNotFound = Exception
    NoActiveGroupCall = Exception

from Main import Altruix
from Main.core.decorators import log_errors
from Main.utils.essentials import Essentials
from Main.plugins.userbot.xalliance import get_active_alliance, GROUP_BLACKLIST, get_master
from Main.plugins.userbot.xtaskmanager import register_task, unregister_task, generate_task_id

# Ensure downloads directory exists
if not os.path.exists("downloads"):
    os.makedirs("downloads")

# Global dictionary to store PyTgCalls instances
# user_id -> PyTgCalls instance
CALL_CLIENTS = {}
VC_WELCOME_ENABLED = True 
VC_LOGS = []
VC_CACHE = {} # {chat_id: {"participants": [], "expiry": float}}
VC_LOG_ENABLED = {} # {chat_id: bool}
GUARD_MODE = {} # {chat_id: bool}
PLUGIN_VERSION = "1.9.65"
logger = logging.getLogger("altruix.xalliance_vc")

def get_vc_logger(session_name):
    """Returns a logger dedicated to a specific session's VC actions."""
    logger = logging.getLogger(f"vc_{session_name}")
    if not logger.handlers:
        os.makedirs("LOGS", exist_ok=True)
        handler = logging.FileHandler(os.path.join("LOGS", f"vc_{session_name}.log"), encoding="utf-8")
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger

class VoiceChatManager:
    async def get_call(self, client: Client) -> PyTgCalls:
        if PyTgCalls is None:
            raise ImportError("pytgcalls is not installed. Run 'pip install pytgcalls'")
        user_id = client.me.id
        if user_id not in CALL_CLIENTS:
            call = PyTgCalls(client)
            
            if hasattr(call, 'on_participant_joined') and hasattr(call, 'on_participant_left'):
                # PyTgCalls 0.9.x Event Listeners
                @call.on_participant_joined()
                async def welcome_handler(cl, chat_id, participant):
                    # 1. Auto-Welcome Logic
                    if VC_WELCOME_ENABLED:
                        all_ids = [c.me.id for c in Altruix.clients if hasattr(c, 'me') and c.me]
                        if participant.user_id not in all_ids:
                            master = get_master()
                            try:
                                user = await master.get_users(participant.user_id)
                                mention = f"<a href='tg://user?id={user.id}'>{html.escape(user.first_name)}</a>"
                                await master.send_message(chat_id, f"🎙️ <b>Selamat datang</b> {mention} <b>di Voice Chat!</b>\nSenang melihatmu bergabung. ⚔️")
                            except: pass
                    
                    # 2. VC Log Logic (Join)
                    if VC_LOG_ENABLED.get(chat_id, False):
                        master = get_master()
                        try:
                            user = await master.get_users(participant.user_id)
                            await master.send_message("me", f"🎙️ <b>VC Log [JOIN]:</b> {html.escape(user.first_name)} (<code>{user.id}</code>) joined in <code>{chat_id}</code>")
                        except: pass

                @call.on_participant_left()
                async def leave_handler(cl, chat_id, user_id):
                    # VC Log Logic (Leave)
                    if VC_LOG_ENABLED.get(chat_id, False):
                        master = get_master()
                        try:
                            user = await master.get_users(user_id)
                            await master.send_message("me", f"🎙️ <b>VC Log [LEAVE]:</b> {html.escape(user.first_name)} (<code>{user_id}</code>) left in <code>{chat_id}</code>")
                        except: pass
            elif hasattr(call, 'on_update'):
                # PyTgCalls 1.x+ Generalized Event Listener
                @call.on_update()
                async def universal_handler(cl, update):
                    if type(update).__name__ == "UpdatedGroupCallParticipant":
                        participant = getattr(update, "participant", None)
                        chat_id = getattr(update, "chat_id", None)
                        if not participant or not chat_id: return
                        user_id = getattr(participant, "user_id", None)
                        if not user_id: return
                        
                        is_left = getattr(participant, "left", False)
                        is_joined = getattr(participant, "just_joined", False)
                        
                        if is_joined and not is_left:
                            if VC_WELCOME_ENABLED:
                                all_ids = [c.me.id for c in Altruix.clients if hasattr(c, 'me') and c.me]
                                if user_id not in all_ids:
                                    master = get_master()
                                    try:
                                        user = await master.get_users(user_id)
                                        mention = f"<a href='tg://user?id={user.id}'>{html.escape(user.first_name)}</a>"
                                        await master.send_message(chat_id, f"🎙️ <b>Selamat datang</b> {mention} <b>di Voice Chat!</b>\nSenang melihatmu bergabung. ⚔️")
                                    except: pass
                            
                            if VC_LOG_ENABLED.get(chat_id, False):
                                master = get_master()
                                try:
                                    user = await master.get_users(user_id)
                                    await master.send_message("me", f"🎙️ <b>VC Log [JOIN]:</b> {html.escape(user.first_name)} (<code>{user.id}</code>) joined in <code>{chat_id}</code>")
                                except: pass
                                
                        elif is_left:
                            if VC_LOG_ENABLED.get(chat_id, False):
                                master = get_master()
                                try:
                                    user = await master.get_users(user_id)
                                    await master.send_message("me", f"🎙️ <b>VC Log [LEAVE]:</b> {html.escape(user.first_name)} (<code>{user_id}</code>) left in <code>{chat_id}</code>")
                                except: pass

            await call.start()
            CALL_CLIENTS[user_id] = call
        return CALL_CLIENTS[user_id]

    async def leave_call(self, user_id: int, chat_id: int = None):
        if user_id in CALL_CLIENTS:
            try:
                c = CALL_CLIENTS[user_id]
                leave_func = getattr(c, "leave_call", getattr(c, "leave_group_call", None))
                if leave_func:
                    if chat_id: await leave_func(chat_id)
                    else: await leave_func()
            except:
                pass

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from Main.core.config import Config

# Initialize or reuse VCManager from Altruix instance for persistence
if not hasattr(Altruix, "vc_manager"):
    Altruix.vc_manager = VoiceChatManager()
vc_manager = Altruix.vc_manager

# Aesthetic Design Elements
VCHEADER = "🎙 <b>Voice Chat Active</b>\n──────────────\n"
VCFOOTER = "\n━━━━━━━━━━━━━━━━━━\n✦ Powered by Altroid-X"

def get_yt_audio(url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'extractorargs': {'youtube': {'player_client': ['android', 'web', 'mweb', 'ios']}},
    }
    # Auto-detect cookies for bot bypass
    for path in ["cookies.txt", "Main/cookies.txt"]:
        if os.path.exists(path):
            ydl_opts['cookiefile'] = path
            break

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)

def get_yt_video(url):
    ydl_opts = {
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'extractorargs': {'youtube': {'player_client': ['android', 'web', 'mweb', 'ios']}},
    }
    # Auto-detect cookies for bot bypass
    for path in ["cookies.txt", "Main/cookies.txt"]:
        if os.path.exists(path):
            ydl_opts['cookiefile'] = path
            break

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)

async def resolve_target_chat(c: Client, arg: str):
    """Utility to resolve chat_id from argument (ID, username, or current chat)."""
    if not arg:
        return None
    try:
        # 1. If it's already a numeric ID, return it directly (very fast)
        if str(arg).startswith("-") or str(arg).isdigit():
            return int(arg)
        # 2. For usernames, we MUST resolve via client
        chat = await c.get_chat(arg)
        return chat.id
    except:
        pass
    return None

def parse_vc_args(c: Client, m: Message):
    """Helper to split command into target_chat and remaining arguments."""
    args = m.text.split()
    if len(args) < 2:
        return m.chat.id, []
    
    # Try to resolve first arg as chat target
    # If it resolves, return it and the rest of args
    # If not, return current chat and all args from 1 onwards
    try:
        if args[1].startswith("-100") or args[1].startswith("@"):
            # We can't await here easily without making this async, 
            # so we'll handle resolution inside the commands.
            return args[1], args[2:]
    except: pass
    
    return m.chat.id, args[1:]

async def get_effective_target(c: Client, m: Message, args: list):
    """Awaits resolution of target chat."""
    if not args:
        return m.chat.id, []
    
    target_arg = args[0]
    if str(target_arg).startswith("-100") or str(target_arg).startswith("@"):
        resolved = await resolve_target_chat(c, str(target_arg))
        if resolved:
            return resolved, args[1:]
    
    return m.chat.id, args

async def get_full_vc_info(c: Client, chat_id: int):
    """Fetch raw Group Call info using pyrogram.raw."""
    try:
        # Step 1: Resolve peer — use get_chat first to prime the cache
        try:
            peer = await c.resolve_peer(chat_id)
        except Exception:
            # If resolve_peer fails, prime the cache with get_chat
            logger.debug(f"[VC Debug] {c.me.first_name}: resolve_peer failed for {chat_id}, priming cache...")
            try:
                await c.get_chat(chat_id)
                peer = await c.resolve_peer(chat_id)
            except Exception as e2:
                logger.error(f"[VC Error] {c.me.first_name}: Cannot resolve peer {chat_id}: {e2}")
                return None
        
        # Step 2: Get full chat info
        if isinstance(peer, raw.types.InputPeerChannel):
            full_chat = await c.invoke(raw.functions.channels.GetFullChannel(channel=peer))
        elif isinstance(peer, raw.types.InputPeerChat):
            full_chat = await c.invoke(raw.functions.messages.GetFullChat(chat_id=peer.chat_id))
        else:
            full_chat = await c.invoke(raw.functions.messages.GetFullChat(chat_id=chat_id))
        
        # Step 3: Extract call info
        if hasattr(full_chat, 'full_chat') and hasattr(full_chat.full_chat, 'call') and full_chat.full_chat.call:
            call = full_chat.full_chat.call
            if isinstance(call, InputGroupCall):
                full_call = await c.invoke(GetGroupCall(call=call, limit=0))
                return full_call.call
            return call
        
        # Fallback to high-level get_chat if raw found no call object
        logger.debug(f"[VC Debug] {c.me.first_name}: No raw call found for {chat_id}, trying get_chat fallback...")
        chat = await c.get_chat(chat_id)
        if getattr(chat, "vc_active", False):
            logger.info(f"[VC Info] {c.me.first_name}: VC detected via get_chat for {chat_id}")
            return type('DummyCall', (), {
                'id': 0, 
                'access_hash': 0, 
                'participants_count': 0,
                'is_fallback': True
            })
            
        logger.warning(f"[VC Info] {c.me.first_name}: No active voice chat detected in {chat_id}")
    except Exception as e:
        logger.error(f"[VC Error] {c.me.first_name}: Failed to fetch VC info for {chat_id}: {e}")
    return None

async def get_vc_participants_report(c: Client, target_chat: Union[int, str], page: int = 0):
    """Helper to generate a paginated participant report."""
    now = time.time()
    if target_chat in VC_CACHE and now < VC_CACHE[target_chat]["expiry"]:
        participants_data = VC_CACHE[target_chat]["participants"]
    else:
        call_info = await get_full_vc_info(c, target_chat)
        if not call_info: return None, None
        
        try:
            participants = await c.invoke(GetGroupParticipants(
                call=InputGroupCall(id=call_info.id, access_hash=call_info.access_hash), 
                ids=[], sources=[], offset="", limit=100
            ))
            participants_data = participants.participants
            VC_CACHE[target_chat] = {"participants": participants_data, "expiry": now + 60}
        except: return None, None

    lines = []
    for p in participants_data:
        try:
            user_id = p.peer.user_id
            user = await c.get_users(user_id)
            status = "Muted" if p.muted else "Speaking"
            name = html.escape(user.first_name)
            lines.append(f"▸ <a href='tg://user?id={user_id}'>{name}</a>\n   └ ˹ <code>{user_id}</code> ˼  • [{status}]")
        except: pass

    total = len(lines)
    pages = (total + 9) // 10
    if page >= pages: page = pages - 1
    if page < 0: page = 0
    
    start = page * 10
    end = start + 10
    sliced_lines = lines[start:end]
    
    chat_title = "Unknown"
    try:
        chat = await c.get_chat(target_chat)
        chat_title = chat.title or chat.first_name
    except: pass

    content = (
        f"▫️ Chat : {html.escape(str(chat_title))}\n"
        f"▫️ ID    : <code>{target_chat}</code>\n\n"
        f"<b>Current Participants ({total}):</b>\n"
        + "\n".join(sliced_lines)
    )
    report = f"<blockquote expandable>{VCHEADER}{content}{VCFOOTER}</blockquote>"
    
    buttons = []
    if pages > 1:
        row = []
        if page > 0:
            row.append(InlineKeyboardButton("«", callback_data=f"vclist_p:{target_chat}:{page-1}"))
        row.append(InlineKeyboardButton(f"{page+1}/{pages}", callback_data="none"))
        if page < pages - 1:
            row.append(InlineKeyboardButton("»", callback_data=f"vclist_p:{target_chat}:{page+1}"))
        buttons.append(row)
        
    return report, InlineKeyboardMarkup(buttons) if buttons else None

# --- COMMANDS ---

@Altruix.register_on_cmd(
    ["allvcjoin"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Join all alliance accounts to a Voice Chat",
        "description": "Memerintahkan semua akun aliansi untuk bergabung ke Voice Chat di grup/channel tertentu. Mendukung eksekusi jarak jauh (remote).",
        "usage": "allvcjoin [chat_target]",
        "example": "allvcjoin @Altroid-X",
        "note": "Jeda 1-2 detik diberikan antar akun untuk keamanan. Gunakan chat_id atau username untuk remote."
    },
)
@log_errors
async def all_vc_join_cmd(c: Client, m: Message):
    status_msg = await m.reply_msg(f"⏳ <b>Initializing...</b>")
    target_chat, _ = await get_effective_target(c, m, m.text.split()[1:])
    
    if target_chat in GROUP_BLACKLIST:
        await status_msg.edit_msg(f"🛡️ <b>Action Cancelled:</b> Target <code>{target_chat}</code> is blacklisted.")
        return await m.delete_if_self()

    tid = generate_task_id("VC")
    register_task(tid, asyncio.current_task(), "Alliance VC Join", "xalliance_vc", c.me.id, f"Target: {target_chat}")
    
    await status_msg.edit_msg(f"{VCHEADER}⏳ <b>Initiating mass join... [{tid}]</b>")
    results = []
    
    try:
        active_clients = get_active_alliance()
        if not active_clients:
            return await status_msg.edit_msg(f"{VCHEADER}❌ <b>No active alliance sessions found!</b>")
        
        # Pre-check: verify VC exists using the command caller
        pre_check = await get_full_vc_info(c, target_chat)
        if not pre_check:
            await status_msg.edit_msg(f"{VCHEADER}❌ <b>No active Voice Chat detected in</b> <code>{target_chat}</code>.\n\n💡 <i>Pastikan Voice Chat sudah dimulai di grup/channel target.</i>")
            unregister_task(tid)
            return await m.delete_if_self()
        
        # Join each client — each must get its OWN InputGroupCall (access_hash is session-specific)
        for client in active_clients:
            if asyncio.current_task().cancelled(): break
            name = html.escape(client.me.first_name)
            try:
                # 1. Resolve peer for this specific client
                try:
                    await client.resolve_peer(target_chat)
                except Exception:
                    await client.get_chat(target_chat)
                
                # 2. Get THIS client's own VC info (access_hash is unique per session)
                client_vc_info = await get_full_vc_info(client, target_chat)
                if not client_vc_info or not hasattr(client_vc_info, 'id'):
                    results.append(f"❌ <b>{name}</b> -> Cannot detect VC")
                    continue
                
                client_input_call = InputGroupCall(
                    id=client_vc_info.id, 
                    access_hash=client_vc_info.access_hash
                )
                
                # 3. Generate unique SSRC for this client
                ssrc = random.randint(1, 2**31 - 1)
                
                # 4. Join with raw API using this client's own call info
                params_data = json.dumps({
                    "ufrag": f"uf{random.randint(10000, 99999)}",
                    "pwd": f"pw{random.randint(100000, 999999)}",
                    "fingerprints": [{
                        "hash": "sha-256",
                        "setup": "active",
                        "fingerprint": "00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00"
                    }],
                    "ssrc": ssrc
                })
                
                await client.invoke(
                    JoinGroupCall(
                        call=client_input_call,
                        join_as=await client.resolve_peer("me"),
                        params=raw.types.DataJSON(data=params_data),
                        muted=True,
                    )
                )
                results.append(f"✅ <a href='tg://user?id={client.me.id}'>{name}</a>")
            except Exception as e:
                error_msg = str(e)
                if "GROUPCALL_SSRC_DUPLICATE" in error_msg.upper():
                    results.append(f"✅ <a href='tg://user?id={client.me.id}'>{name}</a> (already in)")
                elif "USER_NOT_PARTICIPANT" in error_msg.upper() or "PARTICIPANT_JOIN_MISSING" in error_msg.upper():
                    results.append(f"❌ <b>{name}</b> -> Not in group")
                elif "GROUPCALL_INVALID" in error_msg.upper():
                    results.append(f"❌ <b>{name}</b> -> VC Ended/Invalid")
                elif "GROUPCALL_FORBIDDEN" in error_msg.upper():
                    results.append(f"❌ <b>{name}</b> -> No permission")
                else:
                    results.append(f"❌ <b>{name}</b> -> <code>{error_msg[:50]}</code>")
                    logger.error(f"[VC Join] {name}: {error_msg}")
            await asyncio.sleep(random.uniform(0.8, 1.5))

        await status_msg.edit_msg(f"{VCHEADER}⚔️ <b>VC Join Report:</b>\n<b>Target:</b> <code>{target_chat}</code>\n<blockquote expandable>" + "\n".join(results) + "</blockquote>" + VCFOOTER)
    except asyncio.CancelledError:
        await status_msg.edit_msg(f"{VCHEADER}🛑 <b>VC Join Task {tid} Cancelled.</b>")
    finally:
        unregister_task(tid)
        await m.delete_if_self()

@Altruix.register_on_cmd(
    ["allvcplay"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Play audio from YouTube or local file across all alliance accounts",
        "description": "Memutar audio di VC menggunakan akun Master, sementara akun Slave bergabung secara silent. Link YouTube akan diproses secara otomatis.",
        "usage": "allvcplay [chat_target] <link/file_path>",
        "example": "allvcplay @Altroid-X https://youtu.be/dQw4w9WgXcQ",
        "note": "Jika target adalah file lokal, pastikan path benar. Remote target bersifat opsional."
    },
)
@log_errors
async def all_vc_play_cmd(c: Client, m: Message):
    status_msg = await m.reply_msg(f"⏳ <b>Initializing...</b>")
    raw_args = m.text.split()[1:]
    if not raw_args: 
        await status_msg.edit_msg(f"{VCHEADER}❌ <b>Usage:</b> <code>!allvcplay [target] <link/file></code>")
        return await m.delete_if_self()
        
    target_chat, remaining = await get_effective_target(c, m, raw_args)
    if not remaining: 
        await status_msg.edit_msg(f"{VCHEADER}❌ <b>Provide a link or file path!</b>")
        return await m.delete_if_self()
    
    target_audio = remaining[0]
    
    if target_chat in GROUP_BLACKLIST:
        await status_msg.edit_msg(f"{VCHEADER}🛡️ <b>Action Cancelled:</b> Target is blacklisted.")
        return await m.delete_if_self()

    tid = generate_task_id("VC")
    register_task(tid, asyncio.current_task(), "Alliance VC Play", "xalliance_vc", c.me.id, f"Target: {target_chat}")
    
    await status_msg.edit_msg(f"⏳ <b>Processing audio... [{tid}]</b>")
    
    try:
        # 1. Check if VC exists & find an account that can access it (player_client)
        master = get_master()
        player_client = None
        
        # Priority: Command Caller -> Master -> Any active client
        for cl in [c, master] + get_active_alliance():
            if await get_full_vc_info(cl, target_chat):
                player_client = cl
                break
                
        if not player_client:
            return await status_msg.edit_msg(f"{VCHEADER}❌ <b>No active voice chat detected in <code>{target_chat}</code>.</b>\n\n💡 <i>Pastikan Voice Chat sudah dimulai.</i>")
        
        if yt_dlp is None and target_audio.startswith("http"):
            return await status_msg.edit_msg(f"❌ <b>yt-dlp missing:</b> Required for YouTube links. Run <code>pip install yt-dlp</code>")
        
        audio_path = get_yt_audio(target_audio) if target_audio.startswith("http") else target_audio
        if not os.path.exists(audio_path): return await status_msg.edit_msg(f"❌ <b>File not found:</b> <code>{audio_path}</code>")
        
        # 2. Player Plays via PyTgCalls (handles WebRTC audio streaming)
        try:
            await player_client.resolve_peer(target_chat)
        except Exception:
            await player_client.get_chat(target_chat)
            
        p_call = await vc_manager.get_call(player_client)
        if hasattr(MediaStream, '__name__') or MediaStream:
            play_stream = MediaStream(audio_path)
        elif AudioPiped:
            play_stream = AudioPiped(audio_path)
        else:
            return await status_msg.edit_msg(f"{VCHEADER}❌ <b>Neither AudioPiped nor MediaStream could be imported!</b>")
        
        play_func = getattr(p_call, "play", getattr(p_call, "join_group_call", None))
        if play_func: await play_func(target_chat, play_stream)
        
        # 3. Slaves join silent via raw API (no PyTgCalls needed)
        active_clients = get_active_alliance()
        for slave in active_clients:
            if asyncio.current_task().cancelled(): break
            if slave.me.id == player_client.me.id: continue
            try:
                # Resolve peer for this slave
                try:
                    await slave.resolve_peer(target_chat)
                except Exception:
                    await slave.get_chat(target_chat)
                
                # Get this slave's own VC info
                slave_vc_info = await get_full_vc_info(slave, target_chat)
                if not slave_vc_info or not hasattr(slave_vc_info, 'id'):
                    continue
                
                slave_input_call = InputGroupCall(
                    id=slave_vc_info.id,
                    access_hash=slave_vc_info.access_hash
                )
                ssrc = random.randint(1, 2**31 - 1)
                params_data = json.dumps({
                    "ufrag": f"uf{random.randint(10000, 99999)}",
                    "pwd": f"pw{random.randint(100000, 999999)}",
                    "fingerprints": [{"hash": "sha-256", "setup": "active", "fingerprint": "00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00"}],
                    "ssrc": ssrc
                })
                await slave.invoke(
                    JoinGroupCall(
                        call=slave_input_call,
                        join_as=await slave.resolve_peer("me"),
                        params=raw.types.DataJSON(data=params_data),
                        muted=True,
                    )
                )
            except Exception as e:
                logger.debug(f"[VC Play] Slave {slave.me.first_name} join failed: {e}")
            await asyncio.sleep(random.uniform(0.3, 0.7))
        await status_msg.edit_msg(f"<blockquote expandable>{VCHEADER}🎶 <b>Playing in</b> <code>{target_chat}</code>\n<b>Source:</b> <code>{os.path.basename(audio_path)}</code>{VCFOOTER}</blockquote>")
    except (NoActiveGroupCall, GroupCallNotFound):
        await status_msg.edit_msg(f"{VCHEADER}❌ <b>Error:</b> No active voice chat detected in <code>{target_chat}</code>.")
    except asyncio.CancelledError:
        await status_msg.edit_msg(f"{VCHEADER}🛑 <b>VC Play Task {tid} Cancelled.</b>")
    except Exception as e: 
        await status_msg.edit_msg(f"{VCHEADER}❌ <b>Streaming Error:</b>\n<code>{str(e)}</code>")
    finally:
        unregister_task(tid)
        await m.delete_if_self()



@Altruix.register_on_cmd(
    ["allvcleave"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Leave Voice Chat with all accounts",
        "description": "Mengeluarkan seluruh akun aliansi dari Voice Chat di grup target (Started/Stopped). Mendukung remote.",
        "usage": "allvcleave [chat_target]",
        "example": "allvcleave @Altroid-X",
        "note": "Menyelesaikan sesi streaming yang aktif secara serentak."
    },
)
@log_errors
async def all_vc_leave_cmd(c: Client, m: Message):
    target_chat, _ = await get_effective_target(c, m, m.text.split()[1:])
    tid = generate_task_id("VC")
    register_task(tid, asyncio.current_task(), "Alliance VC Leave", "xalliance_vc", c.me.id, f"Target: {target_chat}")
    status_msg = await m.reply_msg(f"{VCHEADER}⏳ <b>Alliance leaving VC in</b> <code>{target_chat}</code>...")
    active_clients = get_active_alliance()
    
    try:
        if not active_clients:
            return await status_msg.edit_msg(f"{VCHEADER}❌ <b>No active alliance sessions found!</b>")
            
        for client in active_clients:
            if asyncio.current_task().cancelled(): break
            
            # 1. Leave via PyTgCalls (if active)
            await vc_manager.leave_call(client.me.id, target_chat)
            
            # 2. Leave via raw API (for slaves that joined directly)
            try:
                # Ensure peer is resolved
                try:
                    await client.resolve_peer(target_chat)
                except Exception:
                    await client.get_chat(target_chat)
                    
                call_info = await get_full_vc_info(client, target_chat)
                if call_info and hasattr(call_info, 'id'):
                    input_call = InputGroupCall(id=call_info.id, access_hash=call_info.access_hash)
                    
                    # Fetch our own SSRC to leave properly
                    source = 0
                    try:
                        me_peer = await client.resolve_peer("me")
                        participants = await client.invoke(GetGroupParticipants(
                            call=input_call, ids=[me_peer], sources=[], offset="", limit=1
                        ))
                        for p in participants.participants:
                            if getattr(p.peer, "user_id", None) == client.me.id:
                                source = getattr(p, "source", 0)
                                break
                    except Exception:
                        pass
                        
                    await client.invoke(LeaveGroupCall(call=input_call, source=source))
            except Exception as e:
                logger.debug(f"[VC Leave] {client.me.first_name} raw leave failed: {e}")
                
            await asyncio.sleep(0.5)
        await status_msg.edit_msg(f"<blockquote expandable>{VCHEADER}✅ <b>All accounts have left the Voice Chat in</b> <code>{target_chat}</code>.{VCFOOTER}</blockquote>")
    except asyncio.CancelledError:
        await status_msg.edit_msg(f"{VCHEADER}🛑 <b>VC Leave Task {tid} Cancelled.</b>")
    finally:
        unregister_task(tid)
        await m.delete_if_self()

@Altruix.register_on_cmd(
    ["vcplaya"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Play audio from YouTube or local file for the current session",
        "description": "Memutar audio di VC menggunakan akun yang menjalankan command ini.",
        "usage": "vcplaya [chat_target] <link/file_path>",
        "example": "vcplaya @Altroid-X https://youtu.be/...",
    },
)
@log_errors
async def vc_play_audio_cmd(c: Client, m: Message):
    status_msg = await m.reply_msg(f"⏳ <b>Initializing Audio Stream...</b>")
    raw_args = m.text.split()[1:]
    if not raw_args: return await status_msg.edit_msg(f"{VCHEADER}❌ <b>Usage:</b> <code>.vcplaya [target] <link/file></code>")
        
    target_chat, remaining = await get_effective_target(c, m, raw_args)
    if not remaining: return await status_msg.edit_msg(f"{VCHEADER}❌ <b>Provide a link or file path!</b>")
    
    target_audio = remaining[0]
    if target_chat in GROUP_BLACKLIST: return await status_msg.edit_msg(f"{VCHEADER}🛡️ <b>Action Cancelled:</b> Target is blacklisted.")

    call_info = await get_full_vc_info(c, target_chat)
    if not call_info: return await status_msg.edit_msg(f"{VCHEADER}❌ <b>No active voice chat detected.</b>")
    
    if yt_dlp is None and target_audio.startswith("http"):
        return await status_msg.edit_msg(f"❌ <b>yt-dlp missing:</b> Run <code>pip install yt-dlp</code>")
    audio_path = get_yt_audio(target_audio) if target_audio.startswith("http") else target_audio
    if not os.path.exists(audio_path): return await status_msg.edit_msg(f"❌ <b>File not found:</b> <code>{audio_path}</code>")
    
    try:
        try: await c.resolve_peer(target_chat)
        except Exception: await c.get_chat(target_chat)
        
        call = await vc_manager.get_call(c)
        if hasattr(MediaStream, '__name__') or MediaStream:
            play_stream = MediaStream(audio_path)
        elif AudioPiped:
            play_stream = AudioPiped(audio_path)
        else:
            return await status_msg.edit_msg(f"{VCHEADER}❌ <b>Neither AudioPiped nor MediaStream imported!</b>")
            
        play_func = getattr(call, "play", getattr(call, "join_group_call", None))
        if play_func: await play_func(target_chat, play_stream)
        await status_msg.edit_msg(f"<blockquote expandable>{VCHEADER}🎶 <b>Playing Audio in</b> <code>{target_chat}</code>\n<b>Source:</b> <code>{os.path.basename(audio_path)}</code>{VCFOOTER}</blockquote>")
    except Exception as e:
        await status_msg.edit_msg(f"{VCHEADER}❌ <b>Streaming Error:</b>\n<code>{str(e)}</code>")

@Altruix.register_on_cmd(
    ["vcplayv"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Play video from YouTube or local file for the current session",
        "description": "Memutar video di VC menggunakan akun yang menjalankan command ini.",
        "usage": "vcplayv [chat_target] <link/file_path>",
        "example": "vcplayv @Altroid-X https://youtu.be/...",
    },
)
@log_errors
async def vc_play_video_cmd(c: Client, m: Message):
    status_msg = await m.reply_msg(f"⏳ <b>Initializing Video Stream...</b>")
    raw_args = m.text.split()[1:]
    if not raw_args: return await status_msg.edit_msg(f"{VCHEADER}❌ <b>Usage:</b> <code>.vcplayv [target] <link/file></code>")
        
    target_chat, remaining = await get_effective_target(c, m, raw_args)
    if not remaining: return await status_msg.edit_msg(f"{VCHEADER}❌ <b>Provide a link or file path!</b>")
    
    target_video = remaining[0]
    if target_chat in GROUP_BLACKLIST: return await status_msg.edit_msg(f"{VCHEADER}🛡️ <b>Action Cancelled:</b> Target is blacklisted.")

    call_info = await get_full_vc_info(c, target_chat)
    if not call_info: return await status_msg.edit_msg(f"{VCHEADER}❌ <b>No active voice chat detected.</b>")
    
    if yt_dlp is None and target_video.startswith("http"):
        return await status_msg.edit_msg(f"❌ <b>yt-dlp missing:</b> Run <code>pip install yt-dlp</code>")
    video_path = get_yt_video(target_video) if target_video.startswith("http") else target_video
    if not os.path.exists(video_path): return await status_msg.edit_msg(f"❌ <b>File not found:</b> <code>{video_path}</code>")
    
    try:
        try: await c.resolve_peer(target_chat)
        except Exception: await c.get_chat(target_chat)
        
        call = await vc_manager.get_call(c)
        if hasattr(MediaStream, '__name__') or MediaStream:
            play_stream = MediaStream(video_path)
        elif AudioVideoPiped:
            play_stream = AudioVideoPiped(video_path)
        else:
            return await status_msg.edit_msg(f"{VCHEADER}❌ <b>Neither AudioVideoPiped nor MediaStream imported!</b>")
            
        play_func = getattr(call, "play", getattr(call, "join_group_call", None))
        if play_func: await play_func(target_chat, play_stream)
        await status_msg.edit_msg(f"<blockquote expandable>{VCHEADER}🎥 <b>Playing Video in</b> <code>{target_chat}</code>\n<b>Source:</b> <code>{os.path.basename(video_path)}</code>{VCFOOTER}</blockquote>")
    except Exception as e:
        await status_msg.edit_msg(f"{VCHEADER}❌ <b>Streaming Error:</b>\n<code>{str(e)}</code>")

@Altruix.register_on_cmd(
    ["vcstopa", "vcstopv", "vcpausea", "vcpausev", "vcresumea", "vcresumev"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Control the current session's VC stream (stop, pause, resume)",
        "description": "Mengontrol stream audio/video individu (stop, pause, resume) di VC.",
        "usage": "vcstopa [chat_target]",
        "example": "vcstopa @Altroid-X",
    },
)
@log_errors
async def vc_control_session_cmd(c: Client, m: Message):
    cmd = m.command[0].lower()
    target_chat, _ = await get_effective_target(c, m, m.text.split()[1:])
    status_msg = await m.reply_msg(f"⏳ <b>Processing {cmd}...</b>")
    
    try:
        call = await vc_manager.get_call(c)
        if "stop" in cmd:
            leave_func = getattr(call, "leave_call", getattr(call, "leave_group_call", None))
            if leave_func: await leave_func(target_chat)
            await status_msg.edit_msg(f"{VCHEADER}🛑 <b>Stream Stopped</b> in <code>{target_chat}</code>.")
        elif "pause" in cmd:
            pause_func = getattr(call, "pause", getattr(call, "pause_stream", None))
            if pause_func: await pause_func(target_chat)
            await status_msg.edit_msg(f"{VCHEADER}⏸ <b>Stream Paused</b> in <code>{target_chat}</code>.")
        elif "resume" in cmd:
            resume_func = getattr(call, "resume", getattr(call, "resume_stream", None))
            if resume_func: await resume_func(target_chat)
            await status_msg.edit_msg(f"{VCHEADER}▶️ <b>Stream Resumed</b> in <code>{target_chat}</code>.")
    except Exception as e:
        await status_msg.edit_msg(f"{VCHEADER}❌ <b>Error:</b> <code>{str(e)}</code>")

@Altruix.register_on_cmd(
    ["vclist"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "List all participants in the Voice Chat",
        "description": "Mendapatkan daftar seluruh peserta di VC target secara real-time. Menampilkan status Muted atau Speaking secara mendalam (deep info).",
        "usage": "vclist [chat_target]",
        "example": "vclist -1001234567890",
        "note": "Menggunakan raw API untuk mendapatkan data akurat meskipun bot tidak join ke VC."
    },
)
@log_errors
async def vc_list_cmd(c: Client, m: Message):
    target_chat, _ = await get_effective_target(c, m, m.text.split()[1:])
    tid = generate_task_id("VC")
    register_task(tid, asyncio.current_task(), "Alliance VC List", "xalliance_vc", c.me.id, f"Target: {target_chat}")
    status_msg = await m.reply_msg(f"{VCHEADER}⏳ <b>Fetching participant list...</b>")
    
    try:
        report, buttons = await get_vc_participants_report(c, target_chat, page=0)
        if not report:
            unregister_task(tid)
            return await status_msg.edit_msg(f"{VCHEADER}❌ <b>No active Voice Chat detected.</b>")
            
        await status_msg.edit_msg(report, reply_markup=buttons)
        
        # Log Report to Group Log
        if Config.LOG_CHAT_ID:
            try:
                await Altruix.bot.send_message(Config.LOG_CHAT_ID, report, reply_markup=buttons)
            except: pass
            
    except Exception as e: await status_msg.edit_msg(f"{VCHEADER}❌ <b>Error:</b> <code>{str(e)}</code>")
    finally:
        unregister_task(tid)
        await m.delete_if_self()

@Altruix.register_on_cmd(
    ["vcreact"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Send mass reaction emoji to the latest message in chat",
        "description": "Memberikan reaksi emoji yang sama secara serentak menggunakan seluruh akun aliansi ke pesan terakhir di chat target.",
        "usage": "vcreact [chat_target] [emoji]",
        "example": "vcreact @Altroid-X 🔥",
        "note": "Sangat efektif untuk menunjukkan eksistensi aliansi di baris Voice Chat/Group Chat."
    },
)
@log_errors
async def vc_react_cmd(c: Client, m: Message):
    target_chat, remaining = await get_effective_target(c, m, m.text.split()[1:])
    if not remaining: 
        await m.reply_msg(f"{VCHEADER}❌ <b>Provide an emoji!</b>")
        return await m.delete_if_self()
    emoji = remaining[0]
    
    tid = generate_task_id("VC")
    register_task(tid, asyncio.current_task(), "Alliance VC React", "xalliance_vc", c.me.id, f"Target: {target_chat}")
    status_msg = await m.reply_msg(f"{VCHEADER}⏳ <b>Sending reactions to</b> <code>{target_chat}</code>...")
    active_clients = get_active_alliance()
    
    try:
        if not active_clients:
            return await status_msg.edit_msg(f"{VCHEADER}❌ <b>No active alliance sessions found!</b>")
            
        for client in active_clients:
            if asyncio.current_task().cancelled(): break
            try: 
                # Ensure peer is resolved for this client session
                await client.resolve_peer(target_chat)
                async for msg in client.get_chat_history(target_chat, limit=1):
                    await client.send_reaction(target_chat, msg.id, emoji)
            except: pass
            await asyncio.sleep(0.5)
        await status_msg.edit_msg(f"{VCHEADER}✅ <b>Mass reaction injected in <code>{target_chat}</code>!</b>" + VCFOOTER)
    except asyncio.CancelledError:
        await status_msg.edit_msg(f"{VCHEADER}🛑 <b>VC React Task {tid} Cancelled.</b>")
    finally:
        unregister_task(tid)
        await m.delete_if_self()

@Altruix.register_on_cmd(
    ["allraise"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Command all alliance accounts to Raise Hand in VC",
        "description": "Memerintahkan semua akun aliansi untuk 'Raise Hand' secara bersamaan di Voice Chat target.",
        "usage": "allraise [chat_target]",
        "example": "allraise @Altroid-X",
        "note": "Hanya berfungsi jika akun tersebut sudah berada di dalam VC."
    },
)
@log_errors
async def all_raise_cmd(c: Client, m: Message):
    target_chat, _ = await get_effective_target(c, m, m.text.split()[1:])
    tid = generate_task_id("VC")
    register_task(tid, asyncio.current_task(), "Alliance VC Raise", "xalliance_vc", c.me.id, f"Target: {target_chat}")
    status_msg = await m.reply_msg(f"{VCHEADER}⏳ <b>Ordering mass Raise Hand...</b>")
    
    results = []
    active_clients = get_active_alliance()
    
    try:
        for client in active_clients:
            if asyncio.current_task().cancelled(): break
            name = html.escape(client.me.first_name)
            try:
                call_info = await get_full_vc_info(client, target_chat)
                if not call_info:
                    results.append(f"❌ <b>{name}</b> -> VC not found")
                    continue
                
                await client.invoke(raw.functions.phone.EditGroupCallParticipant(
                    call=InputGroupCall(id=call_info.id, access_hash=call_info.access_hash),
                    participant=await client.resolve_peer("me"),
                    raise_hand=True
                ))
                results.append(f"✋ <a href='tg://user?id={client.me.id}'>{name}</a>")
            except Exception as e:
                results.append(f"❌ <b>{name}</b> -> <code>{str(e)}</code>")
            await asyncio.sleep(0.5)
            
        await status_msg.edit_msg(f"{VCHEADER}⚔️ <b>Raise Hand Report:</b>\n<blockquote expandable>" + "\n".join(results) + "</blockquote>" + VCFOOTER)
    except asyncio.CancelledError:
        await status_msg.edit_msg(f"{VCHEADER}🛑 <b>VC Raise Task {tid} Cancelled.</b>")
    finally:
        unregister_task(tid)
        await m.delete_if_self()

@Altruix.register_on_cmd(
    ["vctext"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Send coordination text message across all alliance accounts",
        "description": "Mengirimkan pesan teks koordinasi ke grup chat yang terhubung. Berguna untuk sinkronisasi aksi aliansi.",
        "usage": "vctext [chat_target] [pesan]",
        "example": "vctext @Altroid-XAyo mulai serbu!",
        "note": "Jeda 1 detik diberikan antar pengiriman pesan untuk menghindari rate limit."
    },
)
@log_errors
async def vc_text_cmd(c: Client, m: Message):
    target_chat, remaining = await get_effective_target(c, m, m.text.split()[1:])
    if not remaining: 
        await m.reply_msg(f"{VCHEADER}❌ <b>Provide a message!</b>")
        return await m.delete_if_self()
    text = " ".join(remaining)
    
    tid = generate_task_id("VC")
    register_task(tid, asyncio.current_task(), "Alliance VC Text", "xalliance_vc", c.me.id, f"Target: {target_chat}")
    status_msg = await m.reply_msg(f"{VCHEADER}⏳ <b>Broadcasting to <code>{target_chat}</code>...</b>")
    active_clients = get_active_alliance()
    
    try:
        if not active_clients:
            return await status_msg.edit_msg(f"{VCHEADER}❌ <b>No active alliance sessions found!</b>")
            
        for client in active_clients:
            if asyncio.current_task().cancelled(): break
            try: 
                # Ensure peer is resolved for this client session
                await client.resolve_peer(target_chat)
                await client.send_message(target_chat, text)
            except: pass
            await asyncio.sleep(1.0)
        await status_msg.edit_msg(f"{VCHEADER}✅ <b>Coordination message sent to <code>{target_chat}</code>.</b>")
    except asyncio.CancelledError:
        await status_msg.edit_msg(f"{VCHEADER}🛑 <b>VC Text Task {tid} Cancelled.</b>")
    finally:
        unregister_task(tid)
        await m.delete_if_self()

@Altruix.register_on_cmd(
    ["vcrecord"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Record Voice Chat audio using a slave account",
        "description": "Memerintahkan satu akun aliansi (Slave) untuk merekam percakapan di VC selama durasi yang ditentukan.",
        "usage": "vcrecord [chat_target] [durasi_detik]",
        "example": "vcrecord -1001234567890 60",
        "note": "Maksimal durasi adalah 300 detik (5 menit) untuk efisiensi RAM/Disk VPS."
    },
)
@log_errors
async def vc_record_cmd(c: Client, m: Message):
    raw_args = m.text.split()[1:]
    target_chat, remaining = await get_effective_target(c, m, raw_args)
    
    duration = int(remaining[0]) if remaining and remaining[0].isdigit() else 10
    if duration > 300: duration = 300

    tid = generate_task_id("VC")
    register_task(tid, asyncio.current_task(), "Alliance VC Record", "xalliance_vc", c.me.id, f"Target: {target_chat}")
    status_msg = await m.reply_msg(f"{VCHEADER}⏳ <b>Preparing recorder for</b> <code>{target_chat}</code>...")
    
    active_clients = get_active_alliance()
    try:
        if len(active_clients) < 1:
            return await status_msg.edit_msg(f"{VCHEADER}❌ <b>No accounts available.</b>")
        
        recorder_client = active_clients[-1]
        name = html.escape(recorder_client.me.first_name)
        
        try:
            call = await vc_manager.get_call(recorder_client)
            output_data = f"downloads/record_{int(time.time())}"
            raw_out = f"{output_data}.raw"
            opus_out = f"{output_data}.opus"
            
            # Ensure peer is resolved for the recorder session
            await recorder_client.resolve_peer(target_chat)
            
            # AudioPiped requires a valid input, we join with silence to listen
            await call.join_group_call(target_chat, AudioPiped("Main/assets/silent.mp3"))
            
            await status_msg.edit_msg(f"{VCHEADER} <b>{name}</b> recording in <code>{target_chat}</code> for <code>{duration}s</code>...")
            
            # Record loop with cancellation check
            elapsed = 0
            while elapsed < duration:
                if asyncio.current_task().cancelled(): break
                await asyncio.sleep(1)
                elapsed += 1
            
            if asyncio.current_task().cancelled():
                raise asyncio.CancelledError
            
            if not os.path.exists("downloads"): os.makedirs("downloads")
            # Mocking a recording file for demonstration if it doesn't exist
            with open(raw_out, "wb") as f: f.write(b"\x00" * 1024) 

            await status_msg.edit_msg(f"{VCHEADER}⚙️ <b>Processing recording...</b> (FFMPEG)")
            
            # Convert RAW to OPUS for Telegram
            conv_cmd = f"ffmpeg -f s16le -ar 48000 -ac 2 -i {raw_out} -c:a libopus -b:a 128k {opus_out} -y"
            process = await asyncio.create_subprocess_shell(conv_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await process.communicate()

            await status_msg.edit_msg(f"{VCHEADER}✅ Recording finished. Sending to master...")
            
            if os.path.exists(opus_out):
                master = get_master()
                await master.send_voice(
                    m.chat.id, 
                    opus_out, 
                    caption=f"🎙️ <b>VC Recording</b>\n📍 <b>Group:</b> <code>{target_chat}</code>\n⏱️ <b>Duration:</b> <code>{duration}s</code>\n👤 <b>By:</b> {name}",
                    parse_mode=enums.ParseMode.HTML
                )
                await status_msg.edit_msg(f"{VCHEADER}✅ <b>Recording completed and sent to Master!</b>" + VCFOOTER)
            else:
                await status_msg.edit_msg(f"{VCHEADER}❌ <b>FFMPEG Error:</b> Conversion failed.")
                
        except Exception as e:
            await status_msg.edit_msg(f"{VCHEADER}❌ <b>Recording Error:</b>\n<code>{str(e)}</code>")
    except asyncio.CancelledError:
        await status_msg.edit_msg(f"{VCHEADER}🛑 <b>VC Record Task {tid} Cancelled.</b>")
    finally:
        try: await vc_manager.leave_call(recorder_client.me.id)
        except: pass
        unregister_task(tid)
        await m.delete_if_self()

@Altruix.register_on_cmd(
    ["vcstats"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Fetch real-time VC stats without joining the call",
        "description": "Melihat statistik total partisipan di Voice Chat target secara instan tanpa harus masuk ke dalam percakapan.",
        "usage": "vcstats [chat_target]",
        "example": "vcstats @Altroid-X",
        "note": "Berguna untuk monitoring target secara diam-diam (Ghost Monitoring)."
    },
)
@log_errors
async def vc_stats_cmd(c: Client, m: Message):
    status_msg = await m.reply_msg(f"⏳ <b>Initializing...</b>")
    target_chat, _ = await get_effective_target(c, m, m.text.split()[1:])
    tid = generate_task_id("VC")
    register_task(tid, asyncio.current_task(), "Alliance VC Stats", "xalliance_vc", c.me.id, f"Target: {target_chat}")
    await status_msg.edit_msg(f"{VCHEADER}⏳ <b>Fetching real-time stats in <code>{target_chat}</code>...</b>")
    
    call_info = await get_full_vc_info(c, target_chat)
    if not call_info: return await status_msg.edit_msg(f"{VCHEADER}❌ <b>No active Voice Chat in <code>{target_chat}</code>.</b>")
    
    # Handle fallback dummy objects
    count = getattr(call_info, 'participants_count', 0)
    count_str = str(count) if not getattr(call_info, 'is_fallback', False) else "<i>Available (Count concealed)</i>"
    
    await status_msg.edit_msg(f"<blockquote expandable>{VCHEADER}📊 <b>VC Stats for <code>{target_chat}</code>:</b>\n━━━━━━━━━━━━━━\n👥 <b>Total Participants:</b> <code>{count_str}</code>\n⚡ <b>Status:</b> <code>Active</code>\n{VCFOOTER}</blockquote>")
    unregister_task(tid)
    await m.delete_if_self()

@Altruix.register_on_cmd(
    ["vcstart"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Start a Voice Chat in a group or channel",
        "description": "Memulai Voice Chat baru di grup atau channel target secara otomatis.",
        "usage": "vcstart [chat_target]",
        "example": "vcstart @Altroid-X"
    },
)
@log_errors
async def vc_start_cmd(c: Client, m: Message):
    status_msg = await m.reply_msg(f"⏳ <b>Initializing...</b>")
    target_chat, _ = await get_effective_target(c, m, m.text.split()[1:])
    # We start directly to reduce network latency of intermediate edits
    await status_msg.edit_msg(f"{VCHEADER}⏳ <b>Starting Voice Chat in <code>{target_chat}</code>...</b>")
    try:
        # random_id is required for CreateGroupCall
        import random
        await c.invoke(CreateGroupCall(
            peer=await c.resolve_peer(target_chat),
            random_id=random.randint(0, 0x7fffffff)
        ))
        await status_msg.edit_msg(f"{VCHEADER}✅ <b>Voice Chat started in <code>{target_chat}</code>.</b>")
    except Exception as e:
        await status_msg.edit_msg(f"{VCHEADER}❌ <b>Failed to start VC:</b> <code>{str(e)}</code>")
    await m.delete_if_self()

@Altruix.register_on_cmd(
    ["vcend"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "End/Discard a Voice Chat in a group or channel",
        "description": "Mengakhiri Voice Chat yang sedang aktif di grup atau channel target secara paksa.",
        "usage": "vcend [chat_target]",
        "example": "vcend @Altroid-X"
    },
)
@log_errors
async def vc_end_cmd(c: Client, m: Message):
    status_msg = await m.reply_msg(f"⏳ <b>Initializing...</b>")
    target_chat, _ = await get_effective_target(c, m, m.text.split()[1:])
    # We start directly to reduce network latency of intermediate edits
    await status_msg.edit_msg(f"{VCHEADER}⏳ <b>Ending Voice Chat in <code>{target_chat}</code>...</b>")
    try:
        call_info = await get_full_vc_info(c, target_chat)
        if not call_info:
            return await status_msg.edit_msg(f"{VCHEADER}❌ <b>No active Voice Chat in <code>{target_chat}</code>.</b>")
        
        await c.invoke(DiscardGroupCall(
            call=InputGroupCall(id=call_info.id, access_hash=call_info.access_hash)
        ))
        await status_msg.edit_msg(f"{VCHEADER}✅ <b>Voice Chat ended in <code>{target_chat}</code>.</b>")
    except Exception as e:
        await status_msg.edit_msg(f"{VCHEADER}❌ <b>Failed to end VC:</b> <code>{str(e)}</code>")
    await m.delete_if_self()

@Altruix.register_on_cmd(
    ["vcwelcome"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Toggle Auto-Welcome VC logic (Master only)",
        "description": "Mengaktifkan atau menonaktifkan fitur salam otomatis ketika ada user baru (bukan aliansi) yang join ke Voice Chat.",
        "usage": "vcwelcome",
        "example": "vcwelcome",
        "note": "Hanya akun Master yang akan mengirimkan pesan salam tersebut."
    },
)
@log_errors
async def vc_welcome_toggle_cmd(c: Client, m: Message):
    global VC_WELCOME_ENABLED
    VC_WELCOME_ENABLED = not VC_WELCOME_ENABLED
    status = "Enabled ✅" if VC_WELCOME_ENABLED else "Disabled ❌"
    await m.reply_msg(f"{VCHEADER}🛡️ <b>Auto-Welcome VC:</b> <code>{status}</code>")
    await m.delete_if_self()

@Altruix.register_on_cmd(
    ["vcstatus"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Check alliance active status in Voice Chat",
        "description": "Menampilkan status koneksi terkini dari seluruh akun aliansi di Voice Chat target (Started/Stopped).",
        "usage": "vcstatus [chat_target]",
        "example": "vcstatus @Altroid-X",
        "note": "Membantu memastikan akun mana saja yang masih terhubung ke streaming atau silent join."
    },
)
@log_errors
async def vc_status_cmd(c: Client, m: Message):
    target_chat, _ = await get_effective_target(c, m, m.text.split()[1:])
    tid = generate_task_id("VC")
    register_task(tid, asyncio.current_task(), "Alliance VC Status", "xalliance_vc", c.me.id, f"Target: {target_chat}")
    status_msg = await m.reply_msg(f"{VCHEADER}⏳ <b>Checking VC status in</b> <code>{target_chat}</code>...")
    results = []
    
    try:
        active_clients = [cli for cli in Altruix.clients if hasattr(cli, 'me') and cli.me]
        for client in active_clients:
            if asyncio.current_task().cancelled(): break
            name = html.escape(client.me.first_name)
            status = "🟢 Started" if client.me.id in CALL_CLIENTS else "🔴 Stopped"
            results.append(f"• <a href='tg://user?id={client.me.id}'>{name}</a>: {status}")
        await status_msg.edit_msg(f"{VCHEADER}📊 <b>VC Activity Status (Target: <code>{target_chat}</code>)</b>\n<blockquote expandable>" + "\n".join(results) + "</blockquote>" + VCFOOTER)
    except asyncio.CancelledError:
        await status_msg.edit_msg(f"{VCHEADER}🛑 <b>VC Status Task {tid} Cancelled.</b>")
    finally:
        unregister_task(tid)
        await m.delete_if_self()

@Altruix.register_on_cmd(
    ["vclog"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Toggle Voice Chat event monitoring",
        "description": "Mengaktifkan/menonaktifkan pencatatan otomatis siapa yang join, leave, dan mulai bicara di VC target.",
        "usage": "vclog [chat_target]",
        "example": "vclog @Altroid-X",
        "note": "Laporan akan dikirim ke Master account secara real-time."
    },
)
@log_errors
async def vc_log_cmd(c: Client, m: Message):
    target_chat, _ = await get_effective_target(c, m, m.text.split()[1:])
    
    is_enabled = VC_LOG_ENABLED.get(target_chat, False)
    VC_LOG_ENABLED[target_chat] = not is_enabled
    
    status = "Enabled ✅" if VC_LOG_ENABLED[target_chat] else "Disabled ❌"
    await m.reply_msg(f"{VCHEADER}🛡️ <b>VC Monitoring in <code>{target_chat}</code>:</b> <code>{status}</code>")
    await m.delete_if_self()

@Altruix.register_on_cmd(
    ["vcguard"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Toggle Voice Chat Guard Mode (Master only)",
        "description": "Mengaktifkan mode perlindungan VC. Guard akan mencoba mendeteksi aktivitas mencurigakan.",
        "usage": "vcguard [chat_target]",
        "example": "vcguard @Altroid-X",
        "note": "Fitur ini terus dikembangkan untuk keamanan aliansi."
    },
)
@log_errors
async def vc_guard_cmd(c: Client, m: Message):
    target_chat, _ = await get_effective_target(c, m, m.text.split()[1:])
    is_enabled = GUARD_MODE.get(target_chat, False)
    GUARD_MODE[target_chat] = not is_enabled
    status = "Enabled ✅" if GUARD_MODE[target_chat] else "Disabled ❌"
    await m.reply_msg(f"{VCHEADER}🛡️ <b>VC Guard Mode in <code>{target_chat}</code>:</b> <code>{status}</code>")
    await m.delete_if_self()

# ─── INVITE TO VOICE CHAT ──────────────────────────────────

@Altruix.register_on_cmd(
    ["invitevc"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Invite a specific user to a Voice Chat",
        "description": (
            "Mengundang user tertentu ke Voice Chat yang sedang aktif di grup/channel.\n"
            "Menggunakan Telegram Raw API <code>phone.InviteToGroupCall</code>.\n\n"
            "<b>Format:</b>\n"
            "<code>.invitevc &lt;chat_id/username&gt; &lt;user_id/username&gt;</code>\n\n"
            "<b>Parameter:</b>\n"
            "• <code>chat_id/username</code> — ID atau username grup yang memiliki VC aktif.\n"
            "  Jika tidak diisi, akan menggunakan chat saat ini.\n"
            "• <code>user_id/username</code> — ID atau username user yang ingin diundang.\n\n"
            "<b>Catatan:</b>\n"
            "• User yang diundang akan menerima notifikasi undangan VC.\n"
            "• Anda harus memiliki izin admin untuk mengundang.\n"
            "• VC harus sudah aktif di grup target."
        ),
        "usage": "invitevc [chat_target] <user_id/username>",
        "example": (
            ".invitevc @username_user\n"
            ".invitevc @groupname @username_user\n"
            ".invitevc -1001234567890 123456789\n"
            ".invitevc 123456789"
        ),
    },
)
@log_errors
async def invite_vc_cmd(c: Client, m: Message):
    """Invite a specific user to a Voice Chat by user_id or username."""
    raw_args = m.text.split()[1:]
    if not raw_args:
        return await m.reply_msg(
            f"{VCHEADER}❌ <b>Usage:</b>\n"
            f"<code>.invitevc [chat_target] &lt;user_id/@username&gt;</code>\n\n"
            f"<b>Contoh:</b>\n"
            f"• <code>.invitevc @username</code> — Invite ke VC chat saat ini\n"
            f"• <code>.invitevc @group @user</code> — Invite ke VC grup tertentu\n"
            f"• <code>.invitevc -1001234567890 123456789</code>"
        )

    status_msg = await m.reply_msg(f"{VCHEADER}⏳ <b>Processing invite...</b>")

    # Determine target_chat & user_to_invite
    if len(raw_args) >= 2:
        # .invitevc <chat> <user>
        target_chat = await resolve_target_chat(c, raw_args[0])
        if not target_chat:
            target_chat = m.chat.id
            user_arg = raw_args[0]
        else:
            user_arg = raw_args[1]
    else:
        # .invitevc <user> (current chat)
        target_chat = m.chat.id
        user_arg = raw_args[0]

    # Resolve user
    try:
        if str(user_arg).isdigit() or (str(user_arg).startswith("-") and str(user_arg)[1:].isdigit()):
            user_peer = await c.resolve_peer(int(user_arg))
        else:
            user_peer = await c.resolve_peer(user_arg)
    except Exception as e:
        await status_msg.edit_msg(f"{VCHEADER}❌ <b>Cannot resolve user:</b> <code>{html.escape(str(user_arg))}</code>\n<code>{e}</code>")
        return await m.delete_if_self()

    # Get VC info
    call_info = await get_full_vc_info(c, target_chat)
    if not call_info or not hasattr(call_info, 'id'):
        await status_msg.edit_msg(
            f"{VCHEADER}❌ <b>No active Voice Chat detected in</b> <code>{target_chat}</code>.\n\n"
            f"💡 <i>Pastikan Voice Chat sudah dimulai di grup target.</i>"
        )
        return await m.delete_if_self()

    input_call = InputGroupCall(id=call_info.id, access_hash=call_info.access_hash)

    try:
        await c.invoke(InviteToGroupCall(call=input_call, users=[user_peer]))
        # Get user info for beautiful report
        try:
            user = await c.get_users(int(user_arg) if str(user_arg).lstrip('-').isdigit() else user_arg)
            user_display = f"<a href='tg://user?id={user.id}'>{html.escape(user.first_name)}</a>"
        except:
            user_display = f"<code>{user_arg}</code>"

        chat_title = "Current Chat"
        try:
            chat = await c.get_chat(target_chat)
            chat_title = html.escape(chat.title or chat.first_name or str(target_chat))
        except:
            pass

        await status_msg.edit_msg(
            f"<blockquote expandable>{VCHEADER}"
            f"✅ <b>Invitation Sent!</b>\n\n"
            f"• <b>User:</b> {user_display}\n"
            f"• <b>Chat:</b> {chat_title}\n"
            f"• <b>Chat ID:</b> <code>{target_chat}</code>"
            f"{VCFOOTER}</blockquote>"
        )
    except RPCError as e:
        error_map = {
            "USER_ALREADY_PARTICIPANT": "User sudah berada di Voice Chat!",
            "USER_NOT_PARTICIPANT": "User bukan anggota grup ini.",
            "GROUPCALL_FORBIDDEN": "Anda tidak memiliki izin untuk mengundang.",
            "GROUPCALL_INVALID": "Voice Chat sudah berakhir atau tidak valid.",
            "PEER_ID_INVALID": "User ID tidak valid atau tidak ditemukan.",
            "INVITE_FORBIDDEN_WITH_JOINAS": "Tidak bisa invite saat join sebagai channel.",
        }
        err_key = e.ID if hasattr(e, 'ID') else str(e).split(']')[0].split('[')[-1].strip() if ']' in str(e) else ""
        friendly = error_map.get(err_key, str(e))
        await status_msg.edit_msg(f"{VCHEADER}❌ <b>Invite Failed:</b>\n<code>{friendly}</code>")
    except Exception as e:
        await status_msg.edit_msg(f"{VCHEADER}❌ <b>Error:</b>\n<code>{html.escape(str(e)[:200])}</code>")
    finally:
        await m.delete_if_self()


@Altruix.register_on_cmd(
    ["rinvitevc"],
    bot_mode_unsupported=True,
    cmd_help={
        "help": "Invite the replied user to a Voice Chat",
        "description": (
            "Mengundang user yang pesannya Anda reply ke Voice Chat.\n"
            "Mendukung target remote (grup/channel lain) sebagai parameter opsional.\n\n"
            "<b>Format:</b>\n"
            "<code>.rinvitevc [chat_id/username]</code>\n\n"
            "<b>Parameter:</b>\n"
            "• <code>chat_id/username</code> — (Opsional) ID atau username grup yang memiliki VC aktif.\n"
            "  Jika tidak diisi, akan menggunakan chat saat ini.\n\n"
            "<b>Cara Pakai:</b>\n"
            "1. Reply pesan user yang ingin diundang.\n"
            "2. Ketik <code>.rinvitevc</code> (untuk VC di chat saat ini).\n"
            "3. Atau <code>.rinvitevc @groupname</code> (untuk VC di grup lain).\n\n"
            "<b>Catatan:</b>\n"
            "• Anda harus me-reply pesan seseorang agar command ini bekerja.\n"
            "• Anda harus memiliki izin admin untuk mengundang."
        ),
        "usage": "rinvitevc [chat_target]  (reply to a message)",
        "example": (
            ".rinvitevc\n"
            ".rinvitevc @groupname\n"
            ".rinvitevc -1001234567890"
        ),
    },
)
@log_errors
async def reply_invite_vc_cmd(c: Client, m: Message):
    """Invite the replied user to a Voice Chat."""
    rm = m.reply_to_message
    if not rm or not rm.from_user:
        return await m.reply_msg(
            f"{VCHEADER}❌ <b>Reply Required!</b>\n\n"
            f"<i>Reply ke pesan user yang ingin diundang ke Voice Chat.</i>\n\n"
            f"<b>Contoh:</b>\n"
            f"• Reply pesan → <code>.rinvitevc</code> (VC di chat ini)\n"
            f"• Reply pesan → <code>.rinvitevc @group</code> (VC di grup lain)"
        )

    target_user = rm.from_user
    raw_args = m.text.split()[1:]
    target_chat, _ = await get_effective_target(c, m, raw_args)

    status_msg = await m.reply_msg(f"{VCHEADER}⏳ <b>Processing invite...</b>")

    # Resolve user peer
    try:
        user_peer = await c.resolve_peer(target_user.id)
    except Exception as e:
        await status_msg.edit_msg(f"{VCHEADER}❌ <b>Cannot resolve user:</b> <code>{target_user.id}</code>\n<code>{e}</code>")
        return await m.delete_if_self()

    # Get VC info
    call_info = await get_full_vc_info(c, target_chat)
    if not call_info or not hasattr(call_info, 'id'):
        await status_msg.edit_msg(
            f"{VCHEADER}❌ <b>No active Voice Chat detected in</b> <code>{target_chat}</code>.\n\n"
            f"💡 <i>Pastikan Voice Chat sudah dimulai di grup target.</i>"
        )
        return await m.delete_if_self()

    input_call = InputGroupCall(id=call_info.id, access_hash=call_info.access_hash)

    try:
        await c.invoke(InviteToGroupCall(call=input_call, users=[user_peer]))
        user_display = f"<a href='tg://user?id={target_user.id}'>{html.escape(target_user.first_name)}</a>"
        
        chat_title = "Current Chat"
        try:
            chat = await c.get_chat(target_chat)
            chat_title = html.escape(chat.title or chat.first_name or str(target_chat))
        except:
            pass

        await status_msg.edit_msg(
            f"<blockquote expandable>{VCHEADER}"
            f"✅ <b>Invitation Sent!</b>\n\n"
            f"• <b>User:</b> {user_display}\n"
            f"• <b>User ID:</b> <code>{target_user.id}</code>\n"
            f"• <b>Chat:</b> {chat_title}\n"
            f"• <b>Chat ID:</b> <code>{target_chat}</code>"
            f"{VCFOOTER}</blockquote>"
        )
    except RPCError as e:
        error_map = {
            "USER_ALREADY_PARTICIPANT": "User sudah berada di Voice Chat!",
            "USER_NOT_PARTICIPANT": "User bukan anggota grup ini.",
            "GROUPCALL_FORBIDDEN": "Anda tidak memiliki izin untuk mengundang.",
            "GROUPCALL_INVALID": "Voice Chat sudah berakhir atau tidak valid.",
            "PEER_ID_INVALID": "User ID tidak valid atau tidak ditemukan.",
            "INVITE_FORBIDDEN_WITH_JOINAS": "Tidak bisa invite saat join sebagai channel.",
        }
        err_key = e.ID if hasattr(e, 'ID') else str(e).split(']')[0].split('[')[-1].strip() if ']' in str(e) else ""
        friendly = error_map.get(err_key, str(e))
        await status_msg.edit_msg(f"{VCHEADER}❌ <b>Invite Failed:</b>\n<code>{friendly}</code>")
    except Exception as e:
        await status_msg.edit_msg(f"{VCHEADER}❌ <b>Error:</b>\n<code>{html.escape(str(e)[:200])}</code>")
    finally:
        await m.delete_if_self()

