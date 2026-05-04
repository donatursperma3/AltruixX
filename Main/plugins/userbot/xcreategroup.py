# xchatsanomlau.py
"""
Plugin CreateGroup untuk Altruix Userbot
Ported from Ultroid Telethon plugin v0.0.3.14.3 [Mod by @AlphaXproject team]
Modified for Altruix Pyrogram/Kurigram ecosystem
Refactored for clarity and functionality by Antigravity
"""

import os
import re
import asyncio
import html
import logging
import time
import tempfile
import json
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any
import random
import base64

from pyrogram import Client, filters
from pyrogram.errors import (
    FloodWait, PeerIdInvalid, UserNotParticipant, UsernameNotOccupied,
    UsernameInvalid, ChannelInvalid, ChannelPrivate, ChatAdminRequired,
    UserAlreadyParticipant, SlowmodeWait, RPCError, ChatWriteForbidden,
    UserIsBlocked, BadRequest, InviteHashInvalid, InviteHashExpired,
    PhotoInvalidDimensions, WebpageCurlFailed, WebpageMediaEmpty
)
from pyrogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ChatPhoto, ForceReply
)
from pyrogram.enums import ChatType, ChatMemberStatus, ParseMode, ChatAction

from Main import Altruix
from Main.core.decorators import log_errors
from Main.core.types.message import Message as AltruixMessage
# from Main.utils.helpers import run_shell_cmd
from Main.utils.helpers import ChatPrivileges
from pyrogram.types import *
from Main.core.decorators import log_errors, iuser_check
from Main.utils.essentials import Essentials


# ─── LOGGER KHUSUS PLUGIN ───────────────────────────────────────────────
import logging

plugin_name = f"{os.path.basename(__file__)}"
__plugin_name__ = plugin_name if plugin_name else "xcreategroup"
PLUGIN_VERSION = "0.2.363"  # ✅ REFACTORED: Renamed to CreateGroup, enhanced logging

logger = logging.getLogger("altruix.xcreategroup")
logger.setLevel(logging.INFO)

# ==================== KONFIGURASI ====================
# Dapatkan LOG_CHAT_ID dari config Altruix
LOG_CHAT_ID = Altruix.log_chat or Altruix.config.LOG_CHAT_ID or Altruix.config.OWNER_USERS_ID

# 🔥 PERBAIKAN: Ambil handler dari config, bukan 'hndlr'
try:
    HANDLER = Altruix.config.HANDLERS
    if isinstance(HANDLER, list):
        HANDLER = HANDLER[0]
except AttributeError:
    HANDLER = "."


# State management untuk task creategroup
CREATEGROUP_TASKS: Dict[str, Dict[str, Any]] = {}
COMPLETED_CREATEGROUP_TASKS: Dict[str, Dict[str, Any]] = {}
CREATE_LOCK = asyncio.Lock()
from Main.utils.file_helpers import get_db_path

STORAGE_FILE = get_db_path("xcreategroup_cache.json")
PENDING_CONFIRMATIONS = {}

async def save_creategroup_cache():
    try:
        # Konversi datetime dan event ke serializable
        data = {
            "tasks": {},
            "completed": {}
        }
        for tid, task in CREATEGROUP_TASKS.items():
            task_copy = task.copy()
            # Remove non-serializable objects
            keys_to_remove = ["pause_event", "status_task", "task", "task_obj", "log_progress_msg"]
            for key in keys_to_remove:
                if key in task_copy:
                    del task_copy[key]
            
            if "start_time" in task_copy and hasattr(task_copy["start_time"], "isoformat"):
                task_copy["start_time"] = task_copy["start_time"].isoformat()
            data["tasks"][tid] = task_copy
            
        for tid, comp in COMPLETED_CREATEGROUP_TASKS.items():
            comp_copy = comp.copy()
            # Remove non-serializable objects
            keys_to_remove = ["pause_event", "status_task", "task", "task_obj", "log_progress_msg"]
            for key in keys_to_remove:
                if key in comp_copy:
                    del comp_copy[key]
            
            if "end_time" in comp_copy and hasattr(comp_copy["end_time"], "isoformat"):
                comp_copy["end_time"] = comp_copy["end_time"].isoformat()
            data["completed"][tid] = comp_copy
            
        # Atomic Write: Write to temp file first, then rename
        temp_file = f"{STORAGE_FILE}.tmp"
        with open(temp_file, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(temp_file, STORAGE_FILE)
    except Exception as e:
        logger.error(f"Error saving creategroup cache: {e}")

async def load_creategroup_cache():
    global CREATEGROUP_TASKS, COMPLETED_CREATEGROUP_TASKS
    try:
        if os.path.exists(STORAGE_FILE):
            try:
                with open(STORAGE_FILE, "r") as f:
                    data = json.load(f)
            except json.JSONDecodeError as jde:
                # Corrupted JSON: Backup and start fresh
                bak_file = f"{STORAGE_FILE}.bak"
                os.replace(STORAGE_FILE, bak_file)
                logger.error(f"Corrupted creategroup cache detected! Backed up to {bak_file}. Error: {jde}")
                return
                
            for tid, task_data in data.get("tasks", {}).items():
                if "start_time" in task_data:
                    task_data["start_time"] = datetime.fromisoformat(task_data["start_time"])
                task_data["pause_event"] = asyncio.Event()
                task_data["pause_event"].set()
                # Fix: Ensure loaded tasks are NOT marked as running to prevent lock on restart
                task_data["running"] = False 
                CREATEGROUP_TASKS[tid] = task_data
                
            for tid, comp_data in data.get("completed", {}).items():
                if "end_time" in comp_data:
                    comp_data["end_time"] = datetime.fromisoformat(comp_data["end_time"])
                COMPLETED_CREATEGROUP_TASKS[tid] = comp_data
    except Exception as e:
        logger.error(f"Error loading creategroup cache: {e}")

# Load cache on startup
asyncio.ensure_future(load_creategroup_cache())

# Daftar kutipan cinta (sama seperti original)
LOVE_QUOTES = [
    "Love is not merely a feeling; it is a profound commitment to another's well-being, a choice to stand by them through life's storms and sunsets, weaving a tapestry of shared dreams and mutual sacrifice.",
    "The truest form of love is to see an imperfect person perfectly, embracing their flaws as part of their unique beauty, and choosing to cherish them in every moment of life's unpredictable journey.",
    "Love is the eternal dance of two souls, entwined in a rhythm that transcends time, where every step is a promise to nurture, protect, and uplift one another through the chaos of existence.",
    "To love deeply is to risk greatly, for it demands vulnerability and courage to open one's heart fully, trusting that the bond created will withstand the trials of life's ever-changing tides.",
    "Love is the silent language of the heart, speaking through acts of kindness, shared laughter, and quiet moments of understanding that bind two souls in an unbreakable, timeless connection.",
    "In love, we find not just a partner but a mirror, reflecting our deepest selves, challenging us to grow, and offering a sanctuary where we can be both our truest and most evolving selves.",
    "True love is a sacred fire that burns eternally, warming the hearts of those who tend it with care, forgiveness, and an unwavering commitment to each other's growth and happiness.",
    "Love is the courage to embrace another's soul, to walk beside them through life's uncertainties, and to build a shared world where both can flourish in joy and face adversity as one.",
    "The essence of love lies in its selflessness, where one finds joy in giving without expectation, creating a bond that thrives on mutual respect, trust, and the beauty of shared vulnerability.",
    "Love is not a fleeting emotion but a deliberate choice to weave two lives into one, crafting a story of shared triumphs, challenges, and an unspoken promise to face the future together."
]

LOVE_QUOTES_2 = [
    "Cinta sejati adalah perjalanan dua jiwa yang saling memilih setiap hari, membangun kebersamaan dengan keberanian, pengertian, dan pengorbanan untuk saling melengkapi di setiap langkah hidup.",
    "Cinta adalah seni merangkul ketidaksempurnaan seseorang, melihat keindahan dalam kekurangan mereka, dan memilih untuk bersama melalui liku-liku hidup dengan penuh kasih dan kesetiaan.",
    "Dalam cinta, kita menemukan makna sejati hidup, di mana dua hati bersatu untuk saling mendukung, berbagi mimpi, dan menghadapi dunia dengan keberanian yang lahir dari kasih yang mendalam.",
    "Cinta adalah ikatan suci yang mengajarkan kita untuk memberi tanpa syarat, membangun jembatan antara dua jiwa yang saling memperkaya dalam perjalanan menuju keabadian.",
    "Mencintai berarti membuka hati untuk rentan, mempercayakan jiwa kepada yang lain, dan bersama-sama menciptakan dunia di mana kasih sayang menjadi fondasi setiap langkah bersama.",
    "Cinta sejati adalah komitmen untuk saling menghormati, memahami, dan mendukung, menciptakan ruang aman di mana dua jiwa dapat tumbuh bersama dalam harmoni dan keberanian.",
    "Cinta adalah api yang menyala abadi di hati, menghangatkan jiwa dengan kelembutan, pengampunan, dan janji untuk selalu bersama dalam suka maupun duka kehidupan.",
    "Cinta adalah pemberontakan terhadap kehampaan hidup, di mana dua jiwa memilih untuk saling melengkapi, menciptakan makna baru melalui kasih, keberanian, dan pengabdian.",
    "Cinta sejati adalah ketika kita melihat seseorang dengan segala kekurangannya dan tetap memilih untuk mencintainya, membangun kebersamaan yang kokoh di tengah badai kehidupan.",
    "Cinta adalah bahasa jiwa yang berbicara melalui tindakan kecil, keberanian besar, dan kehadiran yang setia, menyatukan dua hati dalam ikatan yang tak lekang oleh waktu."
]

LOVE_QUOTES_3 = [
    "Cinta adalah kekuatan tak terlihat yang mengikat dua jiwa dalam harmoni sempurna, di mana setiap hembusan napas saling melengkapi, setiap mimpi dibagikan, dan setiap tantangan dihadapi bersama dengan keberanian yang lahir dari keyakinan mutual, menciptakan ikatan yang abadi melampaui waktu dan ruang.",
    "Cinta adalah perjalanan abadi di mana dua hati saling menemukan dalam kegelapan dunia, saling menerangi jalan dengan cahaya kasih sayang, membangun benteng kepercayaan yang tak tergoyahkan, dan bersama-sama menaklukkan badai kehidupan dengan kekuatan yang lahir dari persatuan jiwa yang mendalam dan tulus.",
    "Dalam pelukan cinta sejati, kita menemukan kedamaian yang tak tergantikan, di mana setiap detak jantung beresonansi dengan irama yang sama, setiap mimpi dibagikan dengan antusiasme, dan setiap rintangan dihadapi dengan keberanian bersama, menciptakan kisah indah yang akan dikenang sepanjang masa.",
    "Cinta adalah seni tertinggi dari kehidupan manusia, di mana kita belajar untuk memberi tanpa syarat, menerima dengan lapang dada, dan tumbuh bersama dalam harmoni, menciptakan ikatan yang tidak hanya menyatukan dua individu tetapi juga menginspirasi dunia di sekitar mereka dengan keindahan dan kekuatannya.",
    "Mencintai berarti membiarkan jiwa kita terbuka lebar terhadap kemungkinan tak terbatas, di mana kebahagiaan ditemukan dalam hal-hal kecil sehari-hari, kepercayaan dibangun melalui ujian waktu, dan komitmen menjadi pondasi yang kokoh untuk membangun masa depan yang penuh harapan dan keajaiban.",
    "Cinta sejati adalah ketika kita mampu melihat kelemahan pasangan sebagai bagian dari keunikan mereka, mendukung pertumbuhan mereka dengan sabar dan pengertian, serta bersama-sama menciptakan lingkungan di mana keduanya dapat berkembang menjadi versi terbaik dari diri mereka sendiri sepanjang hayat.",
    "Cinta adalah cahaya yang menerangi kegelapan hati, memberikan warmth dan kenyamanan di tengah dinginnya dunia, mengajarkan kita untuk memaafkan, menghargai, dan setia, sehingga setiap momen bersama menjadi kenangan berharga yang memperkaya jiwa dan memperkuat ikatan yang tak terpisahkan.",
    "Cinta adalah pemberontakan terhadap kesendirian, di mana dua jiwa yang terpisah menemukan kesatuan dalam kebersamaan, saling melengkapi kekurangan satu sama lain, dan bersama-sama menciptakan dunia baru yang penuh dengan makna, tawa, dan petualangan yang tak pernah berakhir seumur hidup.",
    "Cinta sejati muncul ketika kita berani melepaskan ego diri, memrioritaskan kebahagiaan orang yang dicintai, dan membangun hubungan berdasarkan kejujuran mutlak, sehingga ikatan tersebut menjadi sumber kekuatan yang membantu kita menghadapi segala tantangan hidup dengan optimisme dan ketabahan.",
    "Cinta adalah simfoni indah dari emosi manusia, di mana setiap nada mewakili kasih sayang, pengorbanan, dan kegembiraan, yang dimainkan bersama untuk menciptakan harmoni sempurna yang mengisi hidup dengan warna-warni kebahagiaan dan meninggalkan warisan abadi bagi generasi yang akan datang."
]

# Sumber channel untuk foto profil dan pesan
SRC_CHANNEL = "alphaxbbc"
LIST_MSG_IDS = [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17]
MSG_IMG_IDS = [25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76] # IDs 25 to 48 from alphaxbbc

# NOTE: We use Altruix.bot and Altruix.clients directly

# ==================== UTILITY FUNCTIONS ====================
def format_duration(seconds: int) -> str:
    """Format seconds to human readable duration"""
    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)
    
    if minutes > 0 and remaining_seconds > 0:
        return f"{minutes} menit {remaining_seconds} detik"
    elif minutes > 0:
        return f"{minutes} menit"
    else:
        return f"{remaining_seconds} detik"

async def get_entity(client: Client, identifier: str) -> Any:
    """Get entity (user/chat) from identifier"""
    try:
        if identifier.startswith('@'):
            return await client.get_users(identifier)
        elif identifier.isdigit():
            return await client.get_users(int(identifier))
        elif identifier.startswith('+'):
            return await client.get_users(identifier)
        else:
            return await client.get_users(f"@{identifier}")
    except Exception as e:
        try:
            if identifier.startswith('-100'):
                return await client.get_chat(int(identifier))
            elif identifier.isdigit():
                return await client.get_chat(int(identifier))
        except:
            pass
        raise Exception(f"Gagal mendapatkan entity {identifier}: {str(e)}")

async def download_profile_photo(client: Client, file_id: Optional[str] = None) -> Optional[str]:
    """Download profile photo from source channel or custom file_id"""
    file_path = None
    try:
        if file_id:
            # Download dari custom file_id
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
                file_path = tmp_file.name
            
            downloaded_path = await client.download_media(file_id, file_name=file_path)
        else:
            # Coba download dari SRC_CHANNEL message ID 4
            message = await client.get_messages(SRC_CHANNEL, 4)
            
            if not message or not (message.photo or (message.document and message.document.mime_type.startswith('image/'))):
                logger.warning("Message ID 4 tidak mengandung foto yang valid")
                return None
            
            # Download media ke file sementara
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
                file_path = tmp_file.name
            
            # Download media
            downloaded_path = await client.download_media(
                message,
                file_name=file_path
            )
        
        if downloaded_path and os.path.exists(downloaded_path):
            try:
                # Cek ukuran file (max 10MB untuk foto profil)
                file_size = os.path.getsize(downloaded_path)
                if file_size > 10 * 1024 * 1024:  # 10MB
                    # Resize jika terlalu besar
                    from PIL import Image
                    img = Image.open(downloaded_path)
                    img.thumbnail((640, 640))  # Resize maksimal 640x640
                    img.save(downloaded_path, "JPEG", quality=85)
                    logger.info(f"Foto profil di-resize: {file_size} -> {os.path.getsize(downloaded_path)} bytes")
                
                return downloaded_path
            except Exception as conv_err:
                logger.error(f"Error konversi foto: {conv_err}")
                # Tetap return file asli jika konversi gagal
                return downloaded_path
        
        # Cleanup if downloaded_path is None or doesn't exist but file_path was created
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        return None
    except Exception as e:
        logger.error(f"Error download foto profil: {e}")
        if file_path and os.path.exists(file_path):
            try: os.remove(file_path)
            except: pass
        return None

async def send_reaction_with_fallback(client: Client, chat_id: int, message_id: int, emoji: str = "❤️") -> bool:
    """Send reaction to message with fallback for older Pyrogram versions"""
    try:
        # Coba method send_reaction (Pyrogram 2.0+)
        if hasattr(client, 'send_reaction'):
            await client.send_reaction(
                chat_id=chat_id,
                message_id=message_id,
                emoji=emoji
            )
            return True
        else:
            # Fallback: send message dengan emoji
            await client.send_message(
                chat_id=chat_id,
                text=f"{emoji} ✅",
                reply_to_message_id=message_id
            )
            return True
    except Exception as e:
        logger.error(f"Gagal kirim reaction: {e}")
        return False

def generate_group_name(pattern: str, index: int, rand_len: int = 0, rand_lower: bool = False, rand_upper: bool = False, predefined_rand: str = None) -> str:
    """Generate group name with pattern and index"""
    now = datetime.now()
    year_last2 = str(now.year)[-2:]
    month_num = str(now.month).zfill(2)
    day_num = str(now.day).zfill(2)
    
    # Check if (index) is explicitly used
    has_index_placeholder = '(index)' in pattern
    
    name = pattern\
        .replace('(tahun)', year_last2)\
        .replace('(bulan)', month_num)\
        .replace('(tanggal)', day_num)
        
    if predefined_rand is not None:
        rand_text = predefined_rand
        if rand_text:
            if has_index_placeholder:
                name = name.replace('(index)', f"{rand_text} (index)")
            else:
                name = f"{name} {rand_text}"
    elif rand_len > 0 and (rand_lower or rand_upper):
        import string
        chars = ""
        if rand_lower: chars += string.ascii_lowercase
        if rand_upper: chars += string.ascii_uppercase
        rand_text = "".join(random.choices(chars, k=rand_len))
        if has_index_placeholder:
            name = name.replace('(index)', f"{rand_text} (index)")
        else:
            name = f"{name} {rand_text}"

    name = name.replace('(index)', str(index))
    
    if has_index_placeholder:
        return name
    return f"{name} {index}"

async def send_log_notification(
    bot_client: Client,
    text: str,
    user_id: int,
    reply_to_msg_id: Optional[int] = None,
    disable_web_page_preview: bool = True
) -> Optional[Message]:
    """Send notification to PM user and log channel, return the log channel message object"""
    log_msg = None

    # Check if bot_client is available
    if not bot_client:
        logger.error("Bot assistant tidak tersedia, tidak dapat mengirim notifikasi")
        return None

    # Send to PM user
    try:
        await bot_client.send_message(
            user_id,
            text,
            disable_web_page_preview=disable_web_page_preview,
            parse_mode=ParseMode.HTML
        )
        logger.info(f"Notifikasi berhasil dikirim ke PM user {user_id}")
    except UserIsBlocked:
        logger.warning(f"User {user_id} telah memblokir bot assistant")
    except PeerIdInvalid:
        logger.warning(f"User ID {user_id} tidak valid atau bot belum pernah berinteraksi dengan user")
    except ChatWriteForbidden:
        logger.error(f"Bot tidak memiliki permission untuk mengirim pesan ke user {user_id}")
    except FloodWait as e:
        logger.warning(f"FloodWait {e.value} detik saat mengirim ke PM user {user_id}")
    except BadRequest as e:
        logger.error(f"BadRequest saat mengirim ke PM user {user_id}: {e}")
    except Exception as e:
        logger.error(f"Gagal kirim notifikasi ke PM user {user_id}: {e}")

    # Send to LOG_CHAT_ID
    try:
        log_msg = await bot_client.send_message(
            LOG_CHAT_ID,
            text,
            reply_to_message_id=reply_to_msg_id,
            disable_web_page_preview=disable_web_page_preview,
            parse_mode=ParseMode.HTML
        )
        logger.info(f"Notifikasi berhasil dikirim ke LOG_CHAT_ID")
    except ChatWriteForbidden:
        logger.error(f"Bot tidak memiliki permission untuk mengirim pesan ke LOG_CHAT_ID {LOG_CHAT_ID}")
    except PeerIdInvalid:
        logger.error(f"LOG_CHAT_ID {LOG_CHAT_ID} tidak valid")
    except ChannelPrivate:
        logger.error(f"LOG_CHAT_ID {LOG_CHAT_ID} adalah channel private dan bot tidak memiliki akses")
    except FloodWait as e:
        logger.warning(f"FloodWait {e.value} detik saat mengirim ke LOG_CHAT_ID")
    except BadRequest as e:
        logger.error(f"BadRequest saat mengirim ke LOG_CHAT_ID: {e}")
    except Exception as e:
        logger.error(f"Gagal kirim notifikasi ke LOG_CHAT_ID: {e}")

    return log_msg


# ==================== MAIN CREATION FUNCTIONS ====================
async def creategroup_loop(
    user_client: Client,
    bot_client: Client,
    initial_message: Message,
    delay: int,
    count: int,
    extra_delay_minutes: int,
    batch_size: int,
    group_type: str,
    name_pattern: str,
    username_prefix: Optional[str],
    bot_identifiers: List[str],
    control_message: Message,
    action_delay: float = 3.0,
    invite_bots: bool = True,
    anon_mode: bool = True,
    copy_messages: bool = True,
    description: str = "Powered by @AlphaXproject",
    photo_source: str = "source",
    custom_photo_id: Optional[str] = None,
    log_destination: str = "log_group",
    log_format: str = "zip",
    pin_first_msg: bool = True,
    msg_img: bool = True,
    rand_len: int = 0,
    rand_lower: bool = False,
    rand_upper: bool = False,
    rand_static: bool = False,
    batch_action: int = 30,
    ba_delay: int = 30,
    user_id: Optional[int] = None,
    task_id: str = None
):
    """Main loop untuk membuat grup"""
    effective_user_id = user_id or (initial_message.from_user.id if initial_message.from_user else None)
    if not effective_user_id:
        logger.error("Cannot determine user_id for creategroup task")
        return
        
    task_id = f'creategroup_{effective_user_id}'
    
    # Task Registration for .tasklist / .taskstatus
    from Main.plugins.userbot.xtaskmanager import register_task, unregister_task, generate_task_id
    tid = generate_task_id("CG")
    
    created_groups = []
    batch_groups = [] # Buffer for current batch
    last_log_msg = None
    photo_path = None  # Cache untuk foto profil
    
    # Determine dynamic labels
    is_channel = group_type == "c"
    type_label = "Channel" if is_channel else "Group" # Capitalized for Titles
    unit_label = "channel" if is_channel else "grup"  # lowercase for counts
    type_name = "Channel" if is_channel else "Grup"   # Capitalized for messages
    
    try:
        # Initialize task state
        CREATEGROUP_TASKS[task_id] = {
            "running": True,
            "paused": False,
            "paused_by_user": False,
            "pause_event": asyncio.Event(),
            "current_index": 1,
            "created_groups": [],
            "start_time": datetime.now(),
            "control_message_id": control_message.id,
            "user_id": user_id or (initial_message.from_user.id if initial_message.from_user else None),
            "params": {
                "delay": delay,
                "count": count,
                "extra_delay_minutes": extra_delay_minutes,
                "batch_size": batch_size,
                "group_type": group_type,
                "name_pattern": name_pattern,
                "username_prefix": username_prefix,
                "bot_identifiers": bot_identifiers,
                "action_delay": action_delay,
                "invite_bots": invite_bots,
                "anon_mode": anon_mode,
                "copy_messages": copy_messages,
                "msg_img": msg_img,
                "description": description,
                "photo_source": photo_source,
                "custom_photo_id": custom_photo_id,
                "pin_first_msg": pin_first_msg,
                "batch_action": batch_action,
                "ba_delay": ba_delay
            },
            "task_obj": asyncio.current_task()
        }
        CREATEGROUP_TASKS[task_id]["pause_event"].set()
        await save_creategroup_cache()
        
        # Dapatkan info user
        user_info = await user_client.get_me()
        account_name_raw = f"{user_info.first_name or ''} {user_info.last_name or ''}".strip()
        
        # Update task state with account name
        CREATEGROUP_TASKS[task_id]["account_name"] = account_name_raw
        
        # Register task with account name
        register_task(tid, asyncio.current_task(), "Create Group", "xcreategroup", effective_user_id, f"Count: {count}", user_name=account_name_raw)
        
        # Dapatkan entity bot asisten
        try:
            assistant = await bot_client.get_me()
            await send_log_notification(
                bot_client,
                f"<blockquote expandable>"
                f"🚀 <b>Task Create {type_label} Started</b>\n"
                f"• Task ID: <code>{tid}</code>\n"
                f"• Account: <b>{html.escape(f'{user_info.first_name or ''} {user_info.last_name or ''}'.strip() or 'Unknown')}</b>\n"
                f"• Account ID: <code>{user_info.id}</code>\n"
                f"• Count: <code>{count}</code> {unit_label}\n"
                f"• Delay Per-Action: <code>{action_delay}</code> detik\n"
                f"• Delay Per-{type_label}: <code>{delay}</code> detik\n"
                f"• Type: {group_type}\n"
                f"• Batch: <code>{batch_size}</code> {unit_label}, delay <code>{extra_delay_minutes}</code> menit\n"
                f"• Batch Act: <code>{batch_action}</code> act, delay <code>{ba_delay}</code> detik"
                f"</blockquote>",
                CREATEGROUP_TASKS[task_id]["user_id"],
                control_message.id
            )
        except Exception as e:
            await send_log_notification(
                bot_client,
                f"❌ Gagal mendapatkan info bot asisten: {str(e)}",
                CREATEGROUP_TASKS[task_id]["user_id"],
                control_message.id
            )
            return
        
        # Parse bot entities jika type 'i' atau invite_bots=True
        should_invite_bots = invite_bots or group_type == "i"
        bot_entities = []
        if should_invite_bots and bot_identifiers:
            for bot_id in bot_identifiers:
                try:
                    if bot_id.startswith('@'):
                        bot_entity = await user_client.get_users(bot_id)
                    elif bot_id.isdigit():
                        bot_entity = await user_client.get_users(int(bot_id))
                    else:
                        bot_entity = await user_client.get_users(f"@{bot_id}")
                    bot_entities.append(bot_entity)
                except Exception as e:
                    await send_log_notification(
                        bot_client,
                        f"⚠️ Gagal mendapatkan bot {bot_id}: {str(e)}",
                        CREATEGROUP_TASKS[task_id]["user_id"],
                        control_message.id
                    )
        
        # Download foto profil sekali saja (cache)
        if group_type in ["a", "i"]:
            try:
                if photo_source == "custom" and custom_photo_id:
                    photo_path = await download_profile_photo(user_client, file_id=custom_photo_id)
                    source_label = "kustom"
                else:
                    photo_path = await download_profile_photo(user_client)
                    source_label = "source account"
                
                if photo_path:
                    await send_log_notification(
                        bot_client,
                        f"✅ Foto profil ({source_label}) berhasil di-download ({os.path.getsize(photo_path)} bytes)\n"
                        f"💡 Use <code>.taskstatus {tid}</code> for details.",
                        CREATEGROUP_TASKS[task_id]["user_id"],
                        control_message.id
                    )
                else:
                    await send_log_notification(
                        bot_client,
                        f"⚠️ Foto profil tidak tersedia atau gagal di-download",
                        CREATEGROUP_TASKS[task_id]["user_id"],
                        control_message.id
                    )
            except Exception as e:
                await send_log_notification(
                    bot_client,
                    f"⚠️ Error download foto profil: {str(e)}",
                    CREATEGROUP_TASKS[task_id]["user_id"],
                    control_message.id
                )
        
        # Generate static random text once if enabled
        static_rand_text = None
        if rand_static and rand_len > 0 and (rand_lower or rand_upper):
            import string
            chars = ""
            if rand_lower: chars += string.ascii_lowercase
            if rand_upper: chars += string.ascii_uppercase
            static_rand_text = "".join(random.choices(chars, k=rand_len))

        # Inisialisasi progress message di log group jika command bukan dari log group
        if str(control_message.chat.id) != str(LOG_CHAT_ID):
            try:
                log_progress_msg = await bot_client.send_message(
                    LOG_CHAT_ID,
                    "📊 <b>Memulai Tracker Progress...</b>",
                    parse_mode=ParseMode.HTML
                )
                CREATEGROUP_TASKS[task_id]["log_progress_msg"] = log_progress_msg
            except Exception as e:
                logger.error(f"Gagal kirim log progress awal: {e}")

        i = 1
        while i <= count:
            # Check if task is running
            if not CREATEGROUP_TASKS.get(task_id, {}).get("running", True):
                account_name = f"{user_info.first_name or ''} {user_info.last_name or ''}".strip()
                await send_log_notification(
                    bot_client,
                    f"🛑 Task Create {type_label} dihentikan oleh user pada {unit_label} ke-{i}\n• Account: {html.escape(account_name)}",
                    CREATEGROUP_TASKS[task_id]["user_id"],
                    control_message.id
                )
                break
            
            # Check if paused by user
            if CREATEGROUP_TASKS[task_id].get("paused", False):
                CREATEGROUP_TASKS[task_id]["paused_by_user"] = True
                account_name = f"{user_info.first_name or ''} {user_info.last_name or ''}".strip()
                await send_log_notification(
                    bot_client,
                    f"⏸️ Task Create {type_label} dipause pada {unit_label} ke-{i}\n• Account: {html.escape(account_name)}",
                    CREATEGROUP_TASKS[task_id]["user_id"],
                    control_message.id
                )
                await CREATEGROUP_TASKS[task_id]["pause_event"].wait()
                CREATEGROUP_TASKS[task_id]["paused_by_user"] = False
                account_name = f"{user_info.first_name or ''} {user_info.last_name or ''}".strip()
                await send_log_notification(
                    bot_client,
                    f"▶️ Task Create {type_label} di-resume pada {unit_label} ke-{i}\n• Account: {html.escape(account_name)}",
                    CREATEGROUP_TASKS[task_id]["user_id"],
                    control_message.id
                )
            
            group_start_time = datetime.now()
            current_group_name = generate_group_name(name_pattern, i, rand_len, rand_lower, rand_upper, static_rand_text)
            current_username = f"{username_prefix}{i}" if username_prefix else None
            
            # Message buffer for consolidated logs area
            # Update: Name is now a hyperlink if username/link available, otherwise code. 
            # We don't have link yet at start, so we update it later or use placeholder?
            # Actually, we can update the header later. For now, let's keep it simple and update line 554/559.
            
            type_name = "Channel" if group_type == "c" else "Grup"
            current_log_header = f"🏗 <b>Memproses {type_name} {i}/{count}</b>\n"
            current_log_text = (
                f"<blockquote expandable>"
                f"{current_log_header}"
                f"• Task ID: <code>{tid}</code>\n"
                f"• Nama: <code>{html.escape(current_group_name)}</code>\n"
                f"• Account: {html.escape(account_name_raw)}\n"
                f"</blockquote>"
            )
            
            # ─── INITIAL LOG MESSAGES ───
            current_log_msgs = []
            
            # 1. Log Group (Bot)
            if log_destination in ["log_group", "both"]:
                msg = await send_log_notification(bot_client, current_log_text, CREATEGROUP_TASKS[task_id]["user_id"], reply_to_msg_id=None)
                if msg: current_log_msgs.append(("bot", msg))
            
            # 2. Saved Messages (User)
            if log_destination in ["saved_messages", "both"]:
                try:
                    msg = await user_client.send_message("me", current_log_text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
                    if msg: current_log_msgs.append(("user", msg))
                except Exception as e:
                    logger.error(f"Gagal kirim log awal ke Saved Messages: {e}")
            
            total_push_msg = 0 # Counter for push messages

            async def update_group_log(new_line: str, update_header_name: str = None, name_link: str = None):
                nonlocal current_log_text, current_log_msgs
                
                lines = current_log_text.split("\n")
                
                if update_header_name and name_link:
                    # Search and replace the 'Nama' line
                    for idx, line in enumerate(lines):
                        if "• Nama:" in line:
                            lines[idx] = f"• Nama: <a href='{name_link}'>{html.escape(update_header_name)}</a>"
                            break
                
                current_log_text = "\n".join(lines)
                
                if new_line:
                    # Insert before the closing blockquote tag
                    if lines and lines[-1] == "</blockquote>":
                        lines.insert(-1, new_line)
                    else:
                        lines.append(new_line)
                    current_log_text = "\n".join(lines)
                
                for client_type, msg in current_log_msgs:
                    try:
                        await msg.edit_text(current_log_text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
                    except Exception as e:
                        logger.warning(f"Gagal edit log message ({client_type}): {e}")

            async def wait_with_countdown(total_seconds, reply_msg=None):
                if total_seconds <= 0: return
                interval = 10
                countdown_msg = None
                
                while total_seconds > 0:
                    text = f"<i>Proses akan dilanjutkan dalam</i> <code>{format_duration(total_seconds)}</code>"
                    
                    if not countdown_msg:
                        if reply_msg:
                            try:
                                countdown_msg = await bot_client.send_message(
                                    chat_id=reply_msg.chat.id,
                                    text=text,
                                    reply_to_message_id=reply_msg.id,
                                    parse_mode=ParseMode.HTML
                                )
                            except Exception as e:
                                logger.error(f"Gagal kirim countdown msg: {e}")
                    else:
                        try:
                            await countdown_msg.edit_text(text, parse_mode=ParseMode.HTML)
                        except Exception as e:
                            logger.debug(f"Gagal update countdown msg: {e}")
                    
                    # Check pause/stop
                    if not CREATEGROUP_TASKS.get(task_id, {}).get("running"):
                        break
                    
                    # Wait for pause event if paused
                    if CREATEGROUP_TASKS.get(task_id, {}).get("paused"):
                        await CREATEGROUP_TASKS[task_id]["pause_event"].wait()
                    
                    sleep_time = min(interval, total_seconds)
                    await asyncio.sleep(sleep_time)
                    total_seconds -= sleep_time
                
                if countdown_msg:
                    try: await countdown_msg.delete()
                    except: pass

            action_count = 0
            async def handle_action_delay():
                nonlocal action_count
                await asyncio.sleep(action_delay)
                action_count += 1
                if action_count >= batch_action:
                    action_count = 0
                    # Ambil log_msg terakhir untuk reply
                    current_log_msg = None
                    if current_log_msgs:
                        current_log_msg = current_log_msgs[0][1] # Ambil bot client log msg
                    
                    await wait_with_countdown(ba_delay, current_log_msg)
                    await update_group_log(f"✅ BA Delay berhasil: <code>{ba_delay}</code>s")


            logger.info(f"Membuat {type_name} {i}/{count}: {current_group_name}")
            
            try:
                # ===== BAGIAN PEMBUATAN GRUP =====
                if group_type == "b":
                    # Basic group
                    try:
                        chat = await user_client.create_group(
                            title=current_group_name,
                            users=[assistant.id]
                        )
                        created_chat_id = chat.id
                        invite_link = await user_client.export_chat_invite_link(created_chat_id)
                        
                        created_groups.append({
                            'name': current_group_name,
                            'link': invite_link,
                            'id': created_chat_id,
                            'time': datetime.now().strftime('%H:%M:%S'),
                            'type': 'basic'
                        })
                        
                        await update_group_log(f"✅ Grup dasar dibuat: <code>{created_chat_id}</code>")
                        
                    except Exception as e:
                        await update_group_log(f"❌ Gagal membuat grup dasar: {str(e)}")
                        i += 1
                        continue
                
                elif group_type in ["g", "c", "a", "i"]:
                    # Supergroup atau channel
                    is_supergroup = group_type in ["g", "a", "i"]
                    
                    try:
                        if is_supergroup:
                            chat = await user_client.create_supergroup(
                                title=current_group_name,
                                description=description
                            )
                        else:
                            chat = await user_client.create_channel(
                                title=current_group_name,
                                description=description
                            )
                        
                        created_chat_id = chat.id
                        type_label_full = "Channel" if group_type == "c" else "Supergroup"
                        await update_group_log(f"✅ {type_label_full} dibuat: <code>{created_chat_id}</code>")
                        await update_group_log(f"✅ Description di-set: <i>{html.escape(description[:30])}...</i>")
                        
                        # Set username jika ada
                        if current_username:
                            try:
                                await user_client.set_chat_username(
                                    created_chat_id,
                                    current_username
                                )
                                invite_link = f"https://t.me/{current_username}"
                                await update_group_log(f"✅ Username di-set: @{current_username}", current_group_name, invite_link)
                            except Exception as e:
                                await update_group_log(f"⚠️ Gagal set username @{current_username}: {str(e)}")
                                invite_link = await user_client.export_chat_invite_link(created_chat_id)
                                await update_group_log(None, current_group_name, invite_link)
                        else:
                            invite_link = await user_client.export_chat_invite_link(created_chat_id)
                            await update_group_log(None, current_group_name, invite_link)
                        
                        # ===== KONFIGURASI LANJUTAN =====
                        should_anon = anon_mode or group_type in ["a", "i"]
                        should_copy = copy_messages or group_type in ["a", "i"]
                        
                        if is_supergroup: # Apply anon/features primarily to supergroups for now
                            # 1. Set anonymous admin
                            if should_anon:
                                try:
                                    privileges = ChatPrivileges(
                                        can_manage_chat=True,
                                        can_delete_messages=True,
                                        can_manage_video_chats=True,
                                        can_restrict_members=True,
                                        can_promote_members=True,
                                        can_change_info=True,
                                        can_post_messages=True,
                                        can_edit_messages=True,
                                        can_invite_users=True,
                                        can_pin_messages=True,
                                        can_manage_topics=True,
                                        can_post_stories=True,
                                        can_edit_stories=True,
                                        can_delete_stories=True,
                                        is_anonymous=True
                                    )
                                    
                                    await user_client.promote_chat_member(
                                        created_chat_id,
                                        user_info.id,
                                        privileges=privileges
                                    )
                                    await handle_action_delay()
                                    await update_group_log(f"✅ Anonymous admin di-set untuk <code>{created_chat_id}</code>")
                                except Exception as e:
                                    await update_group_log(f"❌ Gagal set anonymous admin: {str(e)}")
                            
                            # 2. Set profile photo dari cache
                            if photo_path and os.path.exists(photo_path):
                                try:
                                    await user_client.set_chat_photo(
                                        chat_id=created_chat_id,
                                        photo=photo_path
                                    )
                                    await handle_action_delay()
                                    await update_group_log(f"✅ Foto profil di-set untuk <code>{created_chat_id}</code>")
                                except PhotoInvalidDimensions:
                                    await update_group_log(f"❌ Foto profil invalid dimensions untuk <code>{created_chat_id}</code>")
                                except Exception as e:
                                    await update_group_log(f"❌ Gagal set foto profil: {str(e)}")
                            
                            # 3. Send time message
                            try:
                                from datetime import timezone, timedelta
                                tz = timezone(timedelta(hours=7))  # WIB
                                indonesia_time = datetime.now(tz).strftime('%Y-%m-%d | %H:%M:%S %Z')
                                
                                time_msg = await user_client.send_message(
                                    created_chat_id,
                                    f"**📅 {indonesia_time}**",
                                    parse_mode=ParseMode.MARKDOWN
                                )
                                first_msg_id = time_msg.id
                                
                                # Pin first message if enabled
                                if pin_first_msg:
                                    try:
                                        await user_client.pin_chat_message(
                                            chat_id=created_chat_id,
                                            message_id=first_msg_id,
                                            disable_notification=True
                                        )
                                        await update_group_log(f"📌 First msg berhasil di-pin <code>{created_chat_id}</code>")
                                    except Exception as epin:
                                        await update_group_log(f"⚠️ Gagal pin first msg: {str(epin)}")
                                
                                await handle_action_delay()
                            except Exception as e:
                                await update_group_log(f"❌ Gagal kirim pesan waktu: {str(e)}")
                                first_msg_id = None
                            
                            # 4. Forward messages from source channel (Copy mode)
                            if should_copy:
                                for msg_id in LIST_MSG_IDS:
                                    try:
                                        await user_client.copy_message(
                                            chat_id=created_chat_id,
                                            from_chat_id=SRC_CHANNEL,
                                            message_id=msg_id
                                        )
                                        await handle_action_delay()
                                    except FloodWait as fw:
                                        wait_time = fw.value + 10
                                        await send_log_notification(
                                            bot_client,
                                            f"⏳ FloodWait {fw.value}s, delay {wait_time}s untuk pesan {msg_id}",
                                            CREATEGROUP_TASKS[task_id]["user_id"],
                                            control_message.id
                                        )
                                        await asyncio.sleep(wait_time)
                                        continue
                                    except Exception as e:
                                        await send_log_notification(
                                            bot_client,
                                            f"⚠️ Gagal forward pesan {msg_id}: {str(e)}",
                                            CREATEGROUP_TASKS[task_id]["user_id"],
                                            control_message.id
                                        )
                                        continue
                            
                            # 5. Send LOVE_QUOTES
                            if should_copy:
                                for quote_idx, quote in enumerate(LOVE_QUOTES, 1):
                                    try:
                                        await user_client.send_message(
                                            created_chat_id,
                                            f"<i>💙 {quote}</i>",
                                            parse_mode=ParseMode.HTML
                                        )
                                        await handle_action_delay()
                                    except FloodWait as fw:
                                        await asyncio.sleep(fw.value + 10)
                                        continue
                                    except Exception as e:
                                        await send_log_notification(
                                            bot_client,
                                            f"⚠️ Gagal kirim quote {quote_idx}: {str(e)}",
                                            CREATEGROUP_TASKS[task_id]["user_id"],
                                            control_message.id
                                        )
                                        continue
                                await update_group_log(f"✅ Quote 1 berhasil dikirim total: <code>{len(LOVE_QUOTES)}</code> msg")
                            
                            # 6. Send LOVE_QUOTES_2
                            if should_copy:
                                for quote_idx, quote in enumerate(LOVE_QUOTES_2, 1):
                                    try:
                                        await user_client.send_message(
                                            created_chat_id,
                                            f"<i>💖 {quote}</i>",
                                            parse_mode=ParseMode.HTML
                                        )
                                        await handle_action_delay()
                                    except FloodWait as fw:
                                        await asyncio.sleep(fw.value + 10)
                                        continue
                                    except Exception as e:
                                        await send_log_notification(
                                            bot_client,
                                            f"⚠️ Gagal kirim quote 2-{quote_idx}: {str(e)}",
                                            CREATEGROUP_TASKS[task_id]["user_id"],
                                            control_message.id
                                        )
                                        continue
                                await update_group_log(f"✅ Quote 2 berhasil dikirim total: <code>{len(LOVE_QUOTES_2)}</code> msg")
                            
                            # 7. Invite bots
                            if should_invite_bots and bot_entities:
                                success_bots = []
                                failed_bots = []
                                
                                for bot_idx, bot in enumerate(bot_entities, 1):
                                    try:
                                        await user_client.add_chat_members(
                                            created_chat_id,
                                            bot.id
                                        )
                                        await handle_action_delay()
                                        success_bots.append(bot.username or str(bot.id))
                                        
                                        # Send /help and /id
                                        for cmd in ["/help", "/id"]:
                                            try:
                                                await user_client.send_message(
                                                    created_chat_id,
                                                    cmd
                                                )
                                                await handle_action_delay()
                                            except Exception as e:
                                                await send_log_notification(
                                                    bot_client,
                                                    f"⚠️ Gagal kirim {cmd} ke bot {bot.username}: {str(e)}",
                                                    CREATEGROUP_TASKS[task_id]["user_id"],
                                                    control_message.id
                                                )
                                    except Exception as e:
                                        failed_bots.append(f"{bot.username or bot.id}: {str(e)}")
                                        await handle_action_delay()
                                
                                # Report hasil invite
                                if success_bots:
                                    report = f"✅ Berhasil invite {len(success_bots)} bot ke <code>{created_chat_id}</code>"
                                    await user_client.send_message(
                                        created_chat_id,
                                        f"__{report}__"
                                    )
                                    await update_group_log(report)
                                
                                if failed_bots:
                                    await update_group_log(f"❌ Gagal invite {len(failed_bots)} bot")
                            
                            # 7.5. Send Image Messages (Msg Img) if enabled
                            if msg_img:
                                for img_id in MSG_IMG_IDS:
                                    try:
                                        await user_client.copy_message(
                                            chat_id=created_chat_id,
                                            from_chat_id=SRC_CHANNEL,
                                            message_id=img_id
                                        )
                                        await handle_action_delay()
                                    except FloodWait as fw:
                                        await asyncio.sleep(fw.value + 10)
                                        continue
                                    except Exception as e:
                                        await send_log_notification(
                                            bot_client,
                                            f"⚠️ Gagal kirim image {img_id}: {str(e)}",
                                            CREATEGROUP_TASKS[task_id]["user_id"],
                                            control_message.id
                                        )
                                        continue
                                await update_group_log(f"✅ Image Messages berhasil dikirim total: <code>{len(MSG_IMG_IDS)}</code> msg")
                            
                            # 8. Invite assistant dan kirim welcome message
                            try:
                                await user_client.add_chat_members(
                                    created_chat_id,
                                    assistant.id
                                )
                                await handle_action_delay()
                                
                                # Welcome message dengan inline buttons
                                welcome_buttons = InlineKeyboardMarkup([
                                    [
                                        InlineKeyboardButton(await Essentials.get_user_button_style(user_info.id, "Channel 1"), url="https://t.me/alphaxproject"),
                                        InlineKeyboardButton(await Essentials.get_user_button_style(user_info.id, "Channel 2"), url="https://t.me/tgreceh")
                                    ],
                                    [
                                        InlineKeyboardButton(await Essentials.get_user_button_style(user_info.id, "Channel 3"), url="https://t.me/kutipaninsecure"),
                                        InlineKeyboardButton(await Essentials.get_user_button_style(user_info.id, "Channel 4"), url="https://t.me/caritemanlink")
                                    ]
                                ])
                                
                                welcome_msg = await bot_client.send_message(
                                    created_chat_id,
                                    "<b>❇️ Welcome to our Aliansi AlphaX:</b>",
                                    reply_markup=welcome_buttons,
                                    parse_mode=ParseMode.HTML
                                )
                                
                                await update_group_log(f"✅ Assistant @{assistant.username} invited dan welcome message dikirim")
                            except Exception as e:
                                await update_group_log(f"❌ Gagal invite assistant: {str(e)}")
                            
                            # 9. Send LOVE_QUOTES_3 via assistant
                            if should_copy:
                                for quote_idx, quote in enumerate(LOVE_QUOTES_3, 1):
                                    try:
                                        await bot_client.send_message(
                                            created_chat_id,
                                            f"<i>💗 {quote}</i>",
                                            parse_mode=ParseMode.HTML
                                        )
                                        await handle_action_delay()
                                    except FloodWait as fw:
                                        await asyncio.sleep(fw.value + 10)
                                        continue
                                    except Exception as e:
                                        await send_log_notification(
                                            bot_client,
                                            f"⚠️ Gagal kirim quote 3-{quote_idx}: {str(e)}",
                                            CREATEGROUP_TASKS[task_id]["user_id"],
                                            control_message.id
                                        )
                                        continue
                                await update_group_log(f"✅ Quote 3 berhasil dikirim total: <code>{len(LOVE_QUOTES_3)}</code> msg")
                            
                            # 10. Get approximate message count (Push Message Total)
                            try:
                                # Get recent messages count from history scan
                                messages = []
                                async for msg in user_client.get_chat_history(created_chat_id, limit=150):
                                    messages.append(msg)
                                
                                total_push_msg = len(messages)
                                await update_group_log(f"✅ Push message berhasil total: <code>{total_push_msg}</code> msg")
                                
                                count_msg = await bot_client.send_message(
                                    created_chat_id,
                                    f"<i>Total pesan dalam grup ini: {len(messages)}+</i>",
                                    parse_mode=ParseMode.HTML
                                )
                                await handle_action_delay()
                            except Exception as e:
                                await send_log_notification(
                                    bot_client,
                                    f"⚠️ Gagal hitung pesan: {str(e)}",
                                    CREATEGROUP_TASKS[task_id]["user_id"],
                                    control_message.id
                                )
                            
                            # 11. Link ke pesan pertama
                            if first_msg_id:
                                try:
                                    link_msg = f"<i>➟ ke pesan pertama:</i> <b><a href='t.me/c/{str(created_chat_id).replace("-100", "").lstrip("-")}/{first_msg_id}'>» di sini</a></b>"
                                    await user_client.send_message(
                                        created_chat_id,
                                        link_msg,
                                        parse_mode=ParseMode.HTML
                                    )
                                    await handle_action_delay()
                                except Exception as e:
                                    await send_log_notification(
                                        bot_client,
                                        f"⚠️ Gagal kirim link pesan pertama: {str(e)}",
                                        CREATEGROUP_TASKS[task_id]["user_id"],
                                        control_message.id
                                    )
                            
                            # 12. Completion message
                            group_end_time = datetime.now()
                            group_duration = (group_end_time - group_start_time).total_seconds()
                            
                            completion_msg = await bot_client.send_message(
                                created_chat_id,
                                f"<i>✅ grup <code>{created_chat_id}</code> selesai dikustomisasi dalam {format_duration(group_duration)}!</i>",
                                parse_mode=ParseMode.HTML
                            )
                            
                            # 13. Send reaction to completion message
                            if completion_msg:
                                try:
                                    await send_reaction_with_fallback(
                                        bot_client,
                                        created_chat_id,
                                        completion_msg.id,
                                        "❤️"
                                    )
                                    await handle_action_delay()
                                except Exception as e:
                                    await send_log_notification(
                                        bot_client,
                                        f"⚠️ Gagal kirim reaction: {str(e)}",
                                        CREATEGROUP_TASKS[task_id]["user_id"],
                                        control_message.id
                                    )
                        
                        # Simpan grup yang berhasil dibuat
                        created_groups.append({
                            'name': current_group_name,
                            'link': invite_link,
                            'id': created_chat_id,
                            'time': datetime.now().strftime('%H:%M:%S'),
                            'type': group_type
                        })
                        
                        CREATEGROUP_TASKS[task_id]["created_groups"] = created_groups
                        CREATEGROUP_TASKS[task_id]["current_index"] = i
                        await save_creategroup_cache() # Save cache after group creation

                        # 14. Auto Mark All Mentions as Read
                        try:
                             # Use read_chat_history to mark everything as read
                             await user_client.read_chat_history(created_chat_id)
                        except Exception as e:
                             logger.warning(f"Gagal mark read: {e}")
                        
                        # Kirim update progress
                        # hlgroup = f"<a href='{invite_link}'>{current_group_name}</a> "
                        account_name = f"{user_info.first_name or ''} {user_info.last_name or ''}".strip()
                        progress_msg = (
                            f"<blockquote expandable>"
                            f"✅ Group {i}/{count} successfully created\n"
                            f"• Name: {current_group_name}\n"
                            f"• Account: {html.escape(account_name)}\n"
                            f"• Duration: {format_duration((datetime.now() - group_start_time).total_seconds())}\n"
                            f"• Delay: {format_duration(delay)}"
                            f"</blockquote>"
                        )
                        
                        last_log_msg = await send_log_notification(
                            bot_client,
                            progress_msg,
                            CREATEGROUP_TASKS[task_id]["user_id"],
                            control_message.id
                        )
                        
                    except FloodWait as fw:
                        account_name = f"{user_info.first_name or ''} {user_info.last_name or ''}".strip()
                        wait_msg = (
                            f"<blockquote expandable>"
                            f"⏳ FloodWait {fw.value}s untuk {unit_label} {current_group_name}\n"
                            f"• Account: {html.escape(account_name)}"
                            f"</blockquote>"
                        )
                        await send_log_notification(bot_client, wait_msg, CREATEGROUP_TASKS[task_id]["user_id"], control_message.id)
                        await asyncio.sleep(fw.value + 10)
                        continue  # Coba lagi grup/channel yang sama
                    except Exception as e:
                        account_name = f"{user_info.first_name or ''} {user_info.last_name or ''}".strip()
                        error_msg = (
                            f"<blockquote expandable>"
                            f"❌ Error membuat {unit_label} {current_group_name}: {str(e)}\n"
                            f"• Account: {html.escape(account_name)}"
                            f"</blockquote>"
                        )
                        await send_log_notification(bot_client, error_msg, CREATEGROUP_TASKS[task_id]["user_id"], control_message.id)
                        i += 1
                        continue
                
                # Update control message
                progress_text = (
                    f"<blockquote expandable>"
                    f"📊 <b>Progress CreateGroup</b>\n\n"
                    f"• Task: <code>{task_id}</code>\n"
                    f"• Account: {html.escape(account_name)}\n"
                    f"• Created: {i}/{count}\n"
                    f"• Berhasil: {len(created_groups)}\n"
                    f"• Current: {current_group_name}\n"
                    f"• Status: {'⏸️ Paused' if CREATEGROUP_TASKS[task_id].get('paused') else '▶️ Running'}"
                    f"</blockquote>"
                )
                
                try:
                    control_buttons = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("🛑 Stop", callback_data="stop_creategroup"),
                            InlineKeyboardButton("⏸️ Pause", callback_data="pause_creategroup"),
                            InlineKeyboardButton("▶️ Resume", callback_data="resume_creategroup")
                        ],
                        [
                            InlineKeyboardButton("📊 Status Detail", callback_data="status_creategroup"),
                            InlineKeyboardButton("📋 List Grup", callback_data="list_creategroup")
                        ],
                        [
                            InlineKeyboardButton("🔁 Recurring", callback_data="recurring_creategroup"),
                            InlineKeyboardButton("✏️ Edit Terakhir", callback_data="edit_last_creategroup")
                        ]
                    ])
                    
                    await control_message.edit_text(
                        progress_text,
                        reply_markup=control_buttons,
                        parse_mode=ParseMode.HTML
                    )
                    
                    if str(control_message.chat.id) != str(LOG_CHAT_ID) and "log_progress_msg" in CREATEGROUP_TASKS[task_id]:
                        try:
                            await CREATEGROUP_TASKS[task_id]["log_progress_msg"].edit_text(
                                progress_text,
                                reply_markup=control_buttons,
                                parse_mode=ParseMode.HTML
                            )
                        except Exception as el:
                            logger.error(f"Gagal update log progress message di log group: {el}")
                            
                except Exception as e:
                    logger.error(f"Gagal update control message: {e}")
                
                # Tambahkan ke batch buffer
                batch_groups.append({
                     'name': current_group_name,
                     'link': invite_link,
                     'id': created_chat_id
                })

                # Delay antar grup
                if i < count:
                    await wait_with_countdown(delay, last_log_msg)
                
                # Report Batch dan Extra Delay
                if (i % batch_size == 0) or (i == count):
                    # Kirim report batch
                    if batch_groups:
                        batch_num = (i - 1) // batch_size + 1
                        account_name = f"{user_info.first_name or ''} {user_info.last_name or ''}".strip()
                        batch_report = f"<blockquote expandable>"
                        batch_report += f"#LOG Waktu Pembuatan: {datetime.now().strftime('%Y-%m-%d')}\n"
                        batch_report += f"✅ Berhasil membuat {len(batch_groups)} {unit_label} (batch {batch_num})\n"
                        batch_report += f"• Account: {html.escape(account_name)}\n\n"
                        
                        for idx, bg in enumerate(batch_groups, 1):
                            batch_report += f"{idx}. <a href='{bg['link']}'>{bg['name']} </a> [ <code>{bg['id']}</code> ]\n"
                        
                        batch_report += f"\nmodule by: @AlphaXproject team"
                        batch_report += f"</blockquote>"
                        
                        await send_log_notification(bot_client, batch_report, CREATEGROUP_TASKS[task_id]["user_id"], control_message.id, disable_web_page_preview=True)
                        batch_groups = [] # Reset buffer

                    # Handle extra delay only if NOT the last group and batch limit reached
                    if i % batch_size == 0 and i < count:
                        extra_delay = extra_delay_minutes * 60
                        account_name = f"{user_info.first_name or ''} {user_info.last_name or ''}".strip()
                        batch_msg_obj = await send_log_notification(bot_client, batch_msg, CREATEGROUP_TASKS[task_id]["user_id"], control_message.id)
                        await wait_with_countdown(extra_delay, batch_msg_obj or last_log_msg)
                
                i += 1
                
            except Exception as e:
                logger.error(f"Error dalam loop pembuatan {unit_label}: {e}")
                await send_log_notification(
                    bot_client,
                    f"❌ Error dalam loop untuk {unit_label} {i}: {str(e)}",
                    CREATEGROUP_TASKS[task_id]["user_id"],
                    control_message.id
                )
                i += 1
                continue
        
        # ===== TASK COMPLETED =====
        if CREATEGROUP_TASKS.get(task_id, {}).get("running", False):
            end_time = datetime.now()
            total_duration = (end_time - CREATEGROUP_TASKS[task_id]["start_time"]).total_seconds()
            
            # Simpan konfigurasi task yang selesai
            COMPLETED_CREATEGROUP_TASKS[task_id] = {
                "delay": delay,
                "count": count,
                "extra_delay_minutes": extra_delay_minutes,
                "batch_size": batch_size,
                "group_type": group_type,
                "name_pattern": name_pattern,
                "username_prefix": username_prefix,
                "bot_identifiers": bot_identifiers,
                "action_delay": action_delay,
                "invite_bots": invite_bots,
                "anon_mode": anon_mode,
                "copy_messages": copy_messages,
                "description": description,
                "photo_source": photo_source,
                "custom_photo_id": custom_photo_id,
                "log_destination": log_destination,
                "log_format": log_format,
                "pin_first_msg": pin_first_msg,
                "msg_img": msg_img,
                "rand_len": rand_len,
                "rand_lower": rand_lower,
                "rand_upper": rand_upper,
                "rand_static": rand_static,
                "batch_action": batch_action,
                "ba_delay": ba_delay,
                "created_groups": created_groups,
                "total_duration": total_duration,
                "user_id": effective_user_id,
                "client_id": user_info.id,
                "start_time": CREATEGROUP_TASKS[task_id]["start_time"].strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # Kirim laporan akhir
            await send_completion_report(
                bot_client,
                created_groups,
                count,
                total_duration,
                user_info,
                control_message,
                user_client,
                initial_message,
                log_destination,
                group_type,
                log_format,
                batch_action,
                ba_delay
            )
        else:
            # Task dihentikan
            await send_log_notification(
                bot_client,
                f"<blockquote expandable>"
                f"🛑 Task Create {type_label} dihentikan\n"
                f"• {type_name} dibuat: {len(created_groups)}/{count}\n"
                f"• User: {user_info.first_name}"
                f"</blockquote>",
                CREATEGROUP_TASKS[task_id]["user_id"],
                control_message.id
            )
    
    except Exception as e:
        logger.error(f"Critical error in creategroup_loop: {e}", exc_info=True)
        
        # Simpan partial state agar bisa diakses
        COMPLETED_CREATEGROUP_TASKS[task_id] = {
            "delay": delay,
            "count": count,
            "created_groups": created_groups,
            "total_duration": (datetime.now() - CREATEGROUP_TASKS[task_id]["start_time"]).total_seconds(),
            "user_id": user_info.id,
            "status": "failed",
            "error": str(e)
        }
        
        # Update control message
        try:
             await control_message.edit_text(
                  f"❌ <b>Task CreateGroup Gagal</b>\n\n"
                  f"• Error: {html.escape(str(e))}\n"
                  f"• Berhasil: {len(created_groups)}/{count}\n"
                  f"• User: {user_info.first_name}",
                  reply_markup=InlineKeyboardMarkup([
                       [InlineKeyboardButton("📋 List Partial", callback_data="list_groups_creategroup")]
                  ]),
                  parse_mode=ParseMode.HTML
             )
        except Exception as ex:
             logger.warning(f"Gagal update control message saat error: {ex}")

        await send_log_notification(
            bot_client,
            f"<blockquote expandable>"
            f"❌ Critical error in creategroup_loop: {html.escape(str(e))}"
            f"</blockquote>",
            CREATEGROUP_TASKS[task_id]["user_id"],
            control_message.id
        )
    finally:
        if 'tid' in locals():
            unregister_task(tid)
        # Cleanup foto profil
        if photo_path and os.path.exists(photo_path):
            try:
                os.remove(photo_path)
                logger.info(f"Cache foto profil dihapus: {photo_path}")
            except Exception as e:
                logger.error(f"Gagal hapus cache foto profil: {e}")
        
        # Cleanup task state
        CREATEGROUP_TASKS.pop(task_id, None)

async def send_completion_report(
    bot_client: Client,
    created_groups: List[Dict],
    requested_count: int,
    total_duration: float,
    user_info: Any,
    control_message: Message,
    user_client: Client,
    initial_message: Message,
    log_destination: str = "log_group",
    group_type: str = "a",
    log_format: str = "zip",
    batch_action: int = 30,
    ba_delay: int = 3
):
    """Kirim laporan penyelesaian task"""
    try:
        success_count = len(created_groups)
        
        # Determine log info text
        if log_destination == "both":
            log_info = "Log Group & Saved Messages"
        elif log_destination == "log_group":
            log_info = "Log Group"
        else:
            log_info = "Saved Messages"
            
        # Determine labels
        is_channel = group_type == "c"
        type_label = "Channel" if is_channel else "Group"
        unit_label = "channel" if is_channel else "grup"
        type_name = "Channel" if is_channel else "Grup"
        
        # Buat log file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_filename = f"create{unit_label}_log_{timestamp}.txt"
        
        with open(log_filename, 'w', encoding='utf-8') as f:
            f.write(f"#LOG Create {type_label} - {timestamp}\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"AKUN PEMBUAT:\n")
            f.write(f"• Nama: {user_info.first_name or 'N/A'} {user_info.last_name or ''}\n")
            f.write(f"• ID: {user_info.id}\n")
            f.write(f"• Username: @{user_info.username if user_info.username else 'N/A'}\n\n")
            
            type_unit_stat = "channel" if group_type == "c" else "grup"
            f.write(f"STATISTIK:\n")
            f.write(f"• Diminta: {requested_count} {type_unit_stat}\n")
            f.write(f"• Berhasil: {success_count} {type_unit_stat}\n")
            f.write(f"• Gagal: {requested_count - success_count} {type_unit_stat}\n")
            f.write(f"• Durasi: {format_duration(total_duration)}\n")
            f.write(f"• Batch Act: {batch_action} act / {ba_delay}s\n\n")

            
            f.write(f"DETAIL {type_name.upper()}:\n")
            f.write("=" * 60 + "\n\n")
            
            for idx, group in enumerate(created_groups, 1):
                f.write(f"{idx}. {group['name']}\n")
                f.write(f"   • ID: -100{group['id']}\n")
                f.write(f"   • Tipe: {group['type']}\n")
                f.write(f"   • Waktu: {group['time']}\n")
                f.write(f"   • Link: {group['link']}\n\n")
        
        # Handle ZIP format
        if log_format == "zip":
            import zipfile
            zip_filename = log_filename.replace('.txt', '.zip')
            with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(log_filename)
            try:
                os.remove(log_filename)
            except Exception as e:
                logger.warning(f"Could not remove original txt log: {e}")
            log_filename = zip_filename

        # Kirim file log
        # Determine targets
        targets = []
        if log_destination == "both":
            targets = [
                (LOG_CHAT_ID, bot_client),
                ("me", user_client)
            ]
        elif log_destination == "log_group":
            targets = [(LOG_CHAT_ID, bot_client)]
        else: # saved_messages
            targets = [("me", user_client)]

        log_msg = None
        for target_chat, sender_client in targets:
            try:
                msg = await sender_client.send_document(
                    target_chat,
                    document=log_filename,
                    caption=(
                        f"<blockquote expandable>"
                        f"📊 <b>Laporan Create {type_label} Selesai</b>\n\n"
                        f"• ✅ Berhasil: {success_count}/{requested_count} {unit_label}\n"
                        f"• Durasi: {format_duration(total_duration)}\n"
                        f"• Batch: {batch_action} act / {ba_delay}s\n\n"
                        f"• Account: {html.escape(f'{user_info.first_name or ''} {user_info.last_name or ''}'.strip() or 'N/A')}\n"
                        f"• Account ID: <code>{user_info.id}</code>\n\n"
                        f"<i>Module by @AlphaXproject team</i>"
                        f"</blockquote>"
                    ),
                    parse_mode=ParseMode.HTML
                )
                if not log_msg:
                    log_msg = msg
            except Exception as e:
                logger.error(f"Gagal kirim log ke {target_chat}: {e}")
        
        # Jika destination adalah log_group, kirim juga salinan ke Saved Messages sebagai backup
        if log_destination == "log_group":
            try:
                await user_client.send_document(
                    "me",
                    document=log_filename,
                    caption=f"📊 **Create {type_label} Log (Backup)**\n{timestamp}",
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.warning(f"Gagal kirim log backup ke Saved Messages: {e}")
        else:
             # Jika destination adalah Saved Messages, kirim juga notifikasi ringkas ke log group
             try:
                 await bot_client.send_message(
                     LOG_CHAT_ID,
                     f"<blockquote expandable>"
                     f"📊 <b>Laporan Create {type_label} Selesai</b>\n"
                     f"• User: {user_info.first_name}\n"
                     f"• Detail: Berhasil {success_count}/{requested_count} {unit_label}\n"
                     f"• 📁 Log: Terkirim ke {log_info}."
                     f"</blockquote>",
                     parse_mode=ParseMode.HTML
                 )
             except: pass

        # Reply ke pesan Command awal
        if initial_message:
            try:
                # Construct link manually if username empty (private group)
                # Handle -100 prefix: plain str(id) keeps it, need to slice 4 chars
                chat_id_str = str(log_msg.chat.id)
                clean_chat_id = chat_id_str.replace("-100", "").lstrip("-") if chat_id_str.startswith("-100") else chat_id_str
                
                log_link = log_msg.link if log_msg.chat.username else f"https://t.me/c/{clean_chat_id}/{log_msg.id}"
                
                await initial_message.reply(
                    f"<blockquote expandable>"
                    f"✅ <b>Berhasil membuat {success_count} dari {requested_count} {unit_label}</b>\n"
                    f"Cek log untuk detail:\n"
                    f"• [Lihat Log]({log_link})"
                    f"</blockquote>",
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
            except Exception as e:
                logger.warning(f"Gagal reply command awal: {e}")

        # Hapus file lokal
        os.remove(log_filename)
        
        # Determine labels based on type
        is_channel = group_type == "c"
        type_label = "Channel" if is_channel else "Group"
        unit_label = "channel" if is_channel else "grup"

        # Update control message dengan tombol baru
        final_buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📥 Download Log", callback_data="download_log_creategroup"),
                InlineKeyboardButton("🔁 Recurring", callback_data="recurring_creategroup")
            ],
            [
                InlineKeyboardButton(f"📋 List {type_label}", callback_data="list_groups_creategroup"),
                InlineKeyboardButton("🗑️ Hapus Task", callback_data="delete_task_creategroup")
            ]
        ])

        # Generate buttons for created groups
        group_buttons = []
        if created_groups:
             # Limit buttons to avoid hitting limits (max 100 buttons usually safe, but let's be reasonable)
             # Structure: [[Grup 1], [Grup 2]]
             buttons_list = []
             for idx, grp in enumerate(created_groups[:90], 1): # Limit to 90 for safety
                  buttons_list.append(InlineKeyboardButton(f"{type_label} {idx}", url=grp['link']))
             
             # Arrange buttons, 3 per row
             from Main.utils.helpers import arrange_buttons
             from Main.core.decorators import log_errors, iuser_check
             group_buttons = arrange_buttons(buttons_list, 3)
             
             # Append control buttons to the group buttons (or vice versa? usually group buttons below)
             # Let's keep final_buttons separate or merge. 
             # Merging:
             final_buttons.inline_keyboard = group_buttons + final_buttons.inline_keyboard

        account_name = f"{user_info.first_name or ''} {user_info.last_name or ''}".strip()
        await control_message.edit_text(
            f"<blockquote expandable>"
            f"📊 <b>Laporan Create {type_label} Selesai</b>\n\n"
            f"• <b>User:</b> {html.escape(account_name)}\n"
            f"• <b>Detail:</b> Berhasil {success_count}/{requested_count} {unit_label}\n"
            f"• <b>Durasi:</b> {format_duration(total_duration)}\n"
            f"• <b>Log:</b> {log_info}"
            f"</blockquote>",
            reply_markup=final_buttons,
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"Error sending completion report: {e}")
        await send_log_notification(
            bot_client,
            f"❌ Error dalam completion report: {str(e)}",
            user_info.id,
            control_message.id
        )

# ==================== COMMAND HANDLER ====================

@Altruix.register_on_cmd(
    ["creategroup", "cgroup", "cg"],
    cmd_help={
        "help": "Advanced automated group and channel creation suite.",
        "example": ".creategroup <delay in seconds> <count> <batch_delay in minutes> <batch_size> <type> <pattern> ; <username/optional> <bots>\n\n.creategroup 333 2 10 2 a 🔰 X(tahun)-B(bulan) ; username/optional @bot1 @bot2\n",
        "user_args": {
            "delay": "Delay between each group creation (seconds).",
            "count": "Total number of groups/channels to create.",
            "batch_delay": "Extra delay between batches (minutes).",
            "batch_size": "Number of groups per batch.",
            "type": "Creation type (b: basic, g: mega, c: channel, a: anonymous, i: invite bots).",
            "pattern": "Name pattern (supports (tahun), (bulan), (tanggal), (index)).",
            "; username": "Optional username prefix for the groups.",
            "bots": "Optional bot list to invite (for type 'i' only).",
            "version": f"{PLUGIN_VERSION}"
        },
        "detail": (
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🏗️ <b>CREATEGROUP AUTOMATION</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "• <b>Custom Patterns:</b> Automate naming with time and index tags.\n"
            "• <b>Random Text:</b> Inject random alphabetic strings into group names.\n"
            "• <b>Full Setup (a/i):</b> Auto-set profile photos, bio, anonymous admin, and forward content.\n"
            "• <b>Bot Integration:</b> Auto-invite bots and execute setup commands (/help, /id).\n"
            "• <b>Interactive UI:</b> Configure Granular Settings (Action Delay, Toggles) via Settings -> Create Group.\n"
            "• <b>Batching:</b> Safe creation with distributed delays to avoid Telegram limits.\n"
            "• <b>Monitoring & Logs:</b> Real-time progress in the log group and exportable ZIP/TXT reports."
        )
    },
    group_only=False,
)
@log_errors
async def creategroup_command_handler(client: Client, message: AltruixMessage):
    """Handler untuk command .creategroup"""
    
    # Cek jika ada task yang sedang berjalan
    user_id = client.me.id
    task_id = f'creategroup_{user_id}'
    if task_id in CREATEGROUP_TASKS and CREATEGROUP_TASKS[task_id].get('running', False):
        # Cek apakah task benar-benar berjalan atau zombie
        status_btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔍 Cek Status", callback_data="status_creategroup")]])
        await message.reply("⚠️ Ada task CreateGroup yang sedang berjalan. Gunakan tombol kontrol untuk mengatur.", reply_markup=status_btn)
        return
    
    async with CREATE_LOCK:
        try:
            # Parse command
            args = message.text.split()
            
            if len(args) < 7:
                await message.reply(
                    "**❌ Format Salah!**\n\n"
                    "**Penggunaan:** `.creategroup <delay_detik> <jumlah> <delay_batch_menit> <ukuran_batch> <tipe> <pola_nama> ; <username> <bot_list>`\n\n"
                    "**Contoh:** `.creategroup 333 2 15 5 a \"🔰 X(tahun)-B(bulan)-T(tanggal)A\" ; myusername`\n\n"
                    "**Tipe:**\n"
                    "• b = basic group\n"
                    "• g = mega group\n"
                    "• c = channel\n"
                    "• a = anonymous group (full setup)\n"
                    "• i = invite bots group (full setup + invite bots)\n\n"
                    "**Pola:** Gunakan (tahun), (bulan), (tanggal) sebagai placeholder\n"
                    "**Bots:** Hanya untuk tipe 'i', pisahkan dengan spasi (@bot1 @bot2)"
                )
                return
            
            # Parse parameter
            try:
                delay = int(args[1])
                count = int(args[2])
                batch_delay_min = int(args[3])
                batch_size = int(args[4])
                group_type = args[5].lower()
            except ValueError:
                await message.reply("❌ Parameter angka tidak valid! Pastikan delay, jumlah, delay_batch, dan ukuran_batch adalah angka.")
                return
            
            # Validasi tipe grup
            if group_type not in ["b", "g", "c", "a", "i"]:
                await message.reply("❌ Tipe grup tidak valid! Gunakan: b, g, c, a, atau i")
                return
            
            # Parse pola nama dan parameter opsional
            full_args = " ".join(args[6:])
            name_pattern = ""
            username_prefix = None
            bot_identifiers = []
            
            if " ; " in full_args:
                pattern_part, extra_part = full_args.split(" ; ", 1)
                name_pattern = pattern_part.strip('"\'')
                
                extra_parts = extra_part.strip().split()
                if extra_parts:
                    # Cek apakah bagian pertama adalah username (bukan bot)
                    first_extra = extra_parts[0]
                    if not (first_extra.startswith('@') or first_extra.isdigit()):
                        username_prefix = first_extra
                        bot_identifiers = extra_parts[1:] if group_type == "i" else []
                    else:
                        bot_identifiers = extra_parts if group_type == "i" else []
            else:
                name_pattern = full_args.strip('"\'')
            
            # Validasi untuk tipe 'i'
            if group_type == "i" and not bot_identifiers:
                await message.reply("❌ Tipe 'i' membutuhkan minimal satu bot (@username atau ID)")
                return
            
            # Validasi jumlah
            if count <= 0:
                await message.reply("❌ Jumlah grup harus lebih dari 0")
                return
            elif count > 100:
                await message.reply("⚠️ Jumlah maksimal 100 grup per task. Mengurangi ke 100.")
                count = 100
            
            if batch_size <= 0:
                await message.reply("⚠️ Ukuran batch tidak valid, mengatur ke 5")
                batch_size = 5
            elif batch_size > count:
                # Jika batch lebih besar dari count, set batch = count (satu kali jalan)
                batch_size = count
            
            # Load user configuration to get granular settings (like action_delay, pin_first_msg, etc)
            from Main.internals.settings_handlers.creategroup_handlers import DEFAULT_CREATEGROUP_CONFIG
            config = await Altruix.config.get_user_config(message.from_user.id, "creategroup", DEFAULT_CREATEGROUP_CONFIG)
            
            # Konfirmasi sebelum memulai
            # Generate unique ID untuk callback data (hindari limit 64 bytes)
            confirm_id = f"{int(time.time())}_{message.from_user.id}"
            
            # Simpan data konfirmasi di memory
            PENDING_CONFIRMATIONS[confirm_id] = {
                "delay": delay,
                "count": count,
                "batch_delay_min": batch_delay_min,
                "batch_size": batch_size,
                "group_type": group_type,
                "name_pattern": name_pattern,
                "username_prefix": username_prefix,
                "bot_identifiers": bot_identifiers,
                "description": config.get("description", "Powered by @AlphaXproject"),
                "user_id": message.from_user.id,
                "chat_id": message.chat.id,
                "client_id": client.me.id,  # Store the ID of the client executing the command
                # Granular settings from config
                "action_delay": config.get("action_delay", 3.0),
                "invite_bots": config.get("invite_bots", True),
                "anon_mode": config.get("anon_mode", True),
                "copy_messages": config.get("copy_messages", True),
                "msg_img": config.get("msg_img", True),
                "photo_source": config.get("photo_source", "source"),
                "custom_photo_id": config.get("custom_photo_id"),
                "log_destination": config.get("log_destination", "both"),
                "log_format": config.get("log_format", "zip"),
                "pin_first_msg": config.get("pin_first_msg", True),
                "rand_len": config.get("rand_len", 0),
                "rand_lower": config.get("rand_lower", False),
                "rand_upper": config.get("rand_upper", False),
                "rand_static": config.get("rand_static", False)
            }

            confirm_buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(await Essentials.get_user_button_style(client.me.id, "✅ Ya, Mulai"), callback_data=f"confirm_creategroup:{confirm_id}"),
                    InlineKeyboardButton(await Essentials.get_user_button_style(client.me.id, "❌ Batal"), callback_data=f"cancel_creategroup:{confirm_id}")
                ]
            ])
            
            # Kirim konfirmasi ke Log Group menggunakan Bot Assistant
            try:
                bot = Altruix.bot_manager.get_bot(client.me.id)
                log_confirm = await bot.send_message(
                    LOG_CHAT_ID,
                    f"<b>🔐 Konfirmasi Task CreateGroup</b>\n\n"
                    f"• User: {message.from_user.mention}\n"
                    f"• Jumlah: <code>{count}</code> grup\n"
                    f"• Delay: <code>{delay}</code> detik per grup\n"
                    f"• Per-Batch: <code>{batch_size}</code> grup, delay <code>{batch_delay_min}</code> menit perbatch\n"
                    f"• Tipe: <code>{group_type}</code>\n"
                    f"• Pola: <code>{name_pattern}</code>\n"
                    f"• Username: <code>{username_prefix or 'Tidak ada'}</code>\n"
                    f"• Bots: <code>{len(bot_identifiers) if group_type == 'i' else 0}</code>\n\n"
                    f"<i>Task ini akan berjalan di background. Lanjutkan?</i>",
                    reply_markup=confirm_buttons,
                    parse_mode=ParseMode.HTML
                )
                
                # Beritahu user untuk cek log group
                await message.reply(
                    f"✅ **Permintaan Konfirmasi Dikirim!**\n\n"
                    f"Silakan buka Log Group untuk mengonfirmasi task ini.\n"
                    f"Output akan dikirim ke sana untuk menghindari spam di sini.",
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                await message.reply(f"❌ Gagal mengirim konfirmasi ke Log Group. Pastikan bot admin di sana.\nError: {e}")
            
        except Exception as e:
            logger.error(f"Error in creategroup_command_handler: {e}", exc_info=True)
            await message.reply(f"❌ Error: {str(e)}")


@Altruix.register_on_cmd(
    ["creategroupui", "cgui"], 
    cmd_help={"help": "Tampilkan Interactive Dashboard 'Create Group' (Full Buttons Setup)", "example": "creategroupui"},
    bot_mode_unsupported=True
)
@log_errors
async def creategroup_ui_cmd_handler(c: Client, m: AltruixMessage):
    """
    Handler untuk command .creategroupui pada userbot.
    Mengambil hasil inline dari Bot Asisten untuk menampilkan menu dengan tombol interaktif.
    """
    chat = m.chat.id
    me = c.me
    
    # 1. Identifikasi index session
    index = None
    for i, client in enumerate(Altruix.clients):
        if client.me.id == me.id:
            index = i
            break
            
    if index is None:
        await m.reply("❌ Session tidak ditemukan dalam daftar clients.")
        return
        
    # 2. Ambil username bot asisten (bisa custom bot atau main bot)
    bot_username = Altruix.bot_manager.get_bot_username(me.id)
    
    try:
        # Encode chat title for query safety
        chat_obj = m.chat
        chat_title = chat_obj.title or chat_obj.first_name or "Chat"
        encoded_title = base64.b64encode(chat_title.encode('utf-8')).decode('utf-8')
        
        # 3. Ambil hasil inline bot untuk query 'creategroup_{index}'
        # Menambahkan metadata ke query
        query_str = f"creategroup_{index} cid={chat} ctit={encoded_title}"
        results = await c.get_inline_bot_results(bot_username, query_str)
        
        if results and results.results:
            # 4. Kirim hasil inline ke chat
            await c.send_inline_bot_result(
                chat_id=chat,
                query_id=results.query_id,
                result_id=results.results[0].id,
                reply_to_message_id=m.id,
            )
            # 5. Hapus pesan perintah
            await m.delete_if_self()
        else:
            await m.reply("❌ Bot Asisten gagal memberikan Dashboard Create Group.")
            
    except Exception as e:
        logger.error(f"Error in .creategroupui userbot handler: {e}")
        await m.reply(f"❌ Error: {str(e)}")

# ==================== CALLBACK QUERY HANDLER ====================
@Altruix.bot.on_callback_query(filters.regex(r"^confirm_creategroup:"))
@log_errors
@iuser_check
async def confirm_creategroup_handler(client: Client, callback_query: CallbackQuery):
    """Handler untuk konfirmasi mulai task"""
    
    try:
        data_parts = callback_query.data.split(":")
        if len(data_parts) < 2:
            await callback_query.answer("Data tidak valid", show_alert=True)
            return
        
        confirm_id = data_parts[1]
        
        # Ambil data dari memory
        task_data = PENDING_CONFIRMATIONS.get(confirm_id)
        if not task_data:
            await callback_query.answer("❌ Data konfirmasi kadaluarsa atau tidak ditemukan.", show_alert=True)
            await callback_query.message.edit_text("❌ Konfirmasi kadaluarsa.")
            return

        # Hapus dari pending agar tidak bisa diklik dua kali
        PENDING_CONFIRMATIONS.pop(confirm_id, None)

        delay = task_data["delay"]
        count = task_data["count"]
        batch_delay_min = task_data["batch_delay_min"]
        batch_size = task_data["batch_size"]
        group_type = task_data["group_type"]
        name_pattern = task_data["name_pattern"]
        username_prefix = task_data["username_prefix"]
        bot_identifiers = task_data["bot_identifiers"]
        description = task_data.get("description", "Powered by @AlphaXproject")
        
        # Hapus pesan konfirmasi
        await callback_query.message.delete()
        
        # Buat control message dengan tombol lengkap
        control_buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(await Essentials.get_user_button_style(client.me.id, "🛑 Stop"), callback_data="stop_creategroup"),
                InlineKeyboardButton(await Essentials.get_user_button_style(client.me.id, "⏸️ Pause"), callback_data="pause_creategroup"),
                InlineKeyboardButton(await Essentials.get_user_button_style(client.me.id, "▶️ Resume"), callback_data="resume_creategroup")
            ],
            [
                InlineKeyboardButton(await Essentials.get_user_button_style(client.me.id, "📊 Status"), callback_data="status_creategroup"),
                InlineKeyboardButton(await Essentials.get_user_button_style(client.me.id, "📋 List"), callback_data="list_creategroup"),
                InlineKeyboardButton(await Essentials.get_user_button_style(client.me.id, "🔁 Recurring"), callback_data="recurring_creategroup")
            ],
            [
                 InlineKeyboardButton(await Essentials.get_user_button_style(client.me.id, "✏️ Edit Name"), callback_data="edit_last_creategroup"), 
                 InlineKeyboardButton(await Essentials.get_user_button_style(client.me.id, "✅ Check Created"), callback_data="list_groups_creategroup")
            ]
        ])
        
        control_msg = await client.send_message(
            LOG_CHAT_ID,
            f"🚀 <b>Task CreateGroup Dimulai</b>\n\n"
            f"• User: <b>{callback_query.from_user.mention}</b>\n"
            f"• Jumlah: <code>{count}</code> grup\n"
            f"• Delay Aksi: <code>{delay}</code> detik\n"
            f"• Tipe: {group_type}\n"
            f"• Pola: {name_pattern}\n"
            f"• Batch: <code>{batch_size}</code> grup, delay <code>{batch_delay_min}</code> menit\n\n"
            f"<i>Klik tombol di bawah untuk kontrol</i>",
            reply_markup=control_buttons,
            parse_mode=ParseMode.HTML
        )
        
        if not Altruix.clients:
            await callback_query.answer("❌ Tidak ada userbot aktif!")
            return

        # Find the correct client that initiated the request
        target_client_id = task_data.get("client_id")
        user_param = next((c for c in Altruix.clients if c.me.id == target_client_id), None)
        
        if not user_param:
             # Fallback if specific client not found (e.g. restart), default to first but warn
             user_param = Altruix.clients[0]
             logger.warning(f"Client {target_client_id} not found, defaulting to {user_param.me.id}")

        # Pin control message
        try:
            await control_msg.pin()
        except:
            pass
        
        # Load user configuration to get granular settings
        from Main.internals.settings_handlers.creategroup_handlers import DEFAULT_CREATEGROUP_CONFIG
        config = await Altruix.config.get_user_config(callback_query.from_user.id, "creategroup", DEFAULT_CREATEGROUP_CONFIG)
        
        # Start task
        asyncio.create_task(
            creategroup_loop(
                user_client=user_param,
                bot_client=Altruix.bot,
                initial_message=callback_query.message,
                delay=delay,
                count=count,
                extra_delay_minutes=batch_delay_min,
                batch_size=batch_size,
                group_type=group_type,
                name_pattern=name_pattern,
                username_prefix=username_prefix,
                bot_identifiers=bot_identifiers,
                control_message=control_msg,
                description=description,
                action_delay=config.get("action_delay", 3.0),
                invite_bots=config.get("invite_bots", True),
                anon_mode=config.get("anon_mode", True),
                copy_messages=config.get("copy_messages", True),
                msg_img=config.get("msg_img", True),
                photo_source=config.get("photo_source", "source"),
                custom_photo_id=config.get("custom_photo_id"),
                log_destination=config.get("log_destination", "both"),
                log_format=config.get("log_format", "zip"),
                pin_first_msg=config.get("pin_first_msg", True),
                rand_len=config.get("rand_len", 0),
                rand_lower=config.get("rand_lower", False),
                rand_upper=config.get("rand_upper", False),
                rand_static=config.get("rand_static", False),
                user_id=callback_query.from_user.id
            )
        )
        
        await callback_query.answer("Task dimulai!")
        # Reply konfirmasi ke Log Group (optional)
        # await callback_query.message.reply("✅ Task Started")
        
    except Exception as e:
        logger.error(f"Error in confirm_creategroup_handler: {e}")
        await callback_query.answer(f"Error: {str(e)}")

@Altruix.register_on_cmd(
    ["creategroupstatus", "cgstatus"],
    cmd_help={
        "help": "Check status of active CreateGroup task.",
        "usage": ".creategroupstatus",
        "example": ".creategroupstatus"
    },
    group_only=False
)
@log_errors
async def creategroup_status_cmd(client: Client, message: AltruixMessage):
    """Command to check creategroup status"""
    user_id = client.me.id
    task_id = f'creategroup_{user_id}'
    
    if task_id not in CREATEGROUP_TASKS:
        await message.reply("💤 Tidak ada task CreateGroup yang aktif saat ini.")
        return
        
    task = CREATEGROUP_TASKS[task_id]
    is_running = task.get("running", False)
    is_paused = task.get("paused", False)
    current_idx = task.get("current_index", 0)
    count = task.get("params", {}).get("count", 0)
    
    status_text = (
        f"📊 **Status CreateGroup**\n\n"
        f"• Status: {'▶️ Running' if is_running and not is_paused else '⏸️ Paused' if is_running else '⏹️ Stopped'}\n"
        f"• Progress: {current_idx}/{count}\n"
        f"• Start: {task.get('start_time').strftime('%H:%M:%S') if isinstance(task.get('start_time'), datetime) else 'N/A'}\n"
    )
    
    buttons = [
        [
             InlineKeyboardButton(await Essentials.get_user_button_style(client.me.id, "⏸️ Pause"), callback_data="pause_creategroup"),
             InlineKeyboardButton(await Essentials.get_user_button_style(client.me.id, "▶️ Resume"), callback_data="resume_creategroup")
        ],
        [
             InlineKeyboardButton(await Essentials.get_user_button_style(client.me.id, "⏹️ Stop (Graceful)"), callback_data="stop_creategroup"),
             InlineKeyboardButton(await Essentials.get_user_button_style(client.me.id, "🛑 Force Stop"), callback_data="force_stop_creategroup")
        ],
        [InlineKeyboardButton(await Essentials.get_user_button_style(client.me.id, "🔄 Refresh Status"), callback_data="status_creategroup")]
    ]
    
    await message.reply(status_text, reply_markup=InlineKeyboardMarkup(buttons))

@Altruix.register_on_cmd(
    ["creategroupstop", "cgstop"],
    cmd_help={
        "help": "Stop active CreateGroup task.",
        "usage": ".creategroupstop [force]",
        "example": ".creategroupstop\n.creategroupstop force"
    },
    group_only=False
)
@log_errors
async def creategroup_stop_cmd(client: Client, message: AltruixMessage):
    """Command to stop CreateGroup task"""
    user_id = client.me.id
    task_id = f'creategroup_{user_id}'
    cmd_args = getattr(message, "command", None)
    if not cmd_args and message.text:
        cmd_args = message.text.split()
        
    force = cmd_args and len(cmd_args) > 1 and cmd_args[1].lower() == "force"
    
    if task_id not in CREATEGROUP_TASKS:
        await message.reply("💤 Tidak ada task CreateGroup yang aktif.")
        return

    if force:
        # Force stop logic
        task_data = CREATEGROUP_TASKS.get(task_id)
        if task_data and "task_obj" in task_data:
            task_obj = task_data["task_obj"]
            task_obj.cancel()
        
        CREATEGROUP_TASKS.pop(task_id, None)
        PENDING_CONFIRMATIONS.clear()
        
        await save_creategroup_cache()
        await message.reply("🛑 Task berhasil dihentikan paksa (Force Stop).")
    else:
        # Graceful stop
        CREATEGROUP_TASKS[task_id]["running"] = False
        await message.reply("⏹️ Sinyal stop dikirim. Task akan berhenti setelah proses saat ini selesai.")


@Altruix.bot.on_callback_query(filters.regex(r"^(stop|pause|resume|status|list|recurring|edit_last|download_log|list_groups|delete_task|cancel|force_stop|confirm_recur)_creategroup"))
@log_errors
@iuser_check
async def creategroup_control_handler(client: Client, callback_query: CallbackQuery):
    """Handler untuk tombol kontrol creategroup"""
    
    data_parts = callback_query.data.split(":")
    action = data_parts[0].replace("_creategroup", "")
    user_id = callback_query.from_user.id
    task_id = f'creategroup_{user_id}'
    
    try:
        # Handle Force Stop first (doesn't need check)
        if action == "force_stop":
            if task_id in CREATEGROUP_TASKS:
                CREATEGROUP_TASKS[task_id]["running"] = False
                CREATEGROUP_TASKS.pop(task_id, None)
            
            # Also clear pending confirmations
            PENDING_CONFIRMATIONS.clear()
            
            await save_creategroup_cache()
            await callback_query.message.edit_text("🛑 <b>Task CreateGroup Dihentikan Paksa (Force Stop)</b>\nMemory dibersihkan.", parse_mode=ParseMode.HTML)
            return

        if action == "cancel":
            if len(data_parts) > 1:
                confirm_id = data_parts[1]
                PENDING_CONFIRMATIONS.pop(confirm_id, None)
            
            await callback_query.message.delete()
            await callback_query.answer("Task dibatalkan")
            return
        
        if action == "stop":
            if task_id in CREATEGROUP_TASKS:
                CREATEGROUP_TASKS[task_id]["running"] = False
                await send_log_notification(
                    client,
                    f"🛑 Task CreateGroup dihentikan oleh {callback_query.from_user.mention}",
                    CREATEGROUP_TASKS[task_id].get("user_id"),
                    CREATEGROUP_TASKS[task_id].get("control_message_id")
                )
                await callback_query.answer("Task dihentikan")
                await callback_query.message.edit_text(
                    callback_query.message.text + "\n\n🛑 **DIHENTIKAN OLEH USER**",
                    parse_mode=ParseMode.HTML
                )
            else:
                await callback_query.answer("Tidak ada task yang berjalan")
        
        elif action == "pause":
            if task_id in CREATEGROUP_TASKS and CREATEGROUP_TASKS[task_id].get("running", False):
                CREATEGROUP_TASKS[task_id]["paused"] = True
                CREATEGROUP_TASKS[task_id]["pause_event"].clear()
                await send_log_notification(
                    client,
                    f"⏸️ Task CreateGroup dipause oleh {callback_query.from_user.mention}",
                    CREATEGROUP_TASKS[task_id].get("user_id"),
                    CREATEGROUP_TASKS[task_id].get("control_message_id")
                )
                await callback_query.answer("Task dipause")
                await callback_query.message.edit_text(
                    callback_query.message.text + "\n\n⏸️ **DIPAUSE OLEH USER**",
                    parse_mode=ParseMode.HTML
                )
            else:
                await callback_query.answer("Task tidak berjalan atau sudah dihentikan")
        
        elif action == "resume":
            if task_id in CREATEGROUP_TASKS and CREATEGROUP_TASKS[task_id].get("paused", False):
                CREATEGROUP_TASKS[task_id]["paused"] = False
                CREATEGROUP_TASKS[task_id]["pause_event"].set()
                await send_log_notification(
                    client,
                    f"▶️ Task CreateGroup di-resume oleh {callback_query.from_user.mention}",
                    CREATEGROUP_TASKS[task_id].get("user_id"),
                    CREATEGROUP_TASKS[task_id].get("control_message_id")
                )
                await callback_query.answer("Task di-resume")
                # Hapus status pause dari teks
                text = callback_query.message.text
                if "**DIPAUSE" in text:
                    text = text.replace("\n\n⏸️ **DIPAUSE OLEH USER**", "")
                await callback_query.message.edit_text(
                    text + "\n\n▶️ **DILANJUTKAN OLEH USER**",
                    parse_mode=ParseMode.HTML
                )
            else:
                await callback_query.answer("Task tidak dalam status pause")
        
        elif action == "status":
            if task_id in CREATEGROUP_TASKS:
                task_info = CREATEGROUP_TASKS[task_id]
                created = len(task_info.get("created_groups", []))
                current = task_info.get("current_index", 0)
                running = task_info.get("running", False)
                paused = task_info.get("paused", False)
                start_time = task_info.get("start_time", datetime.now())
                elapsed = (datetime.now() - start_time).total_seconds()
                
                status_text = (
                    f"📊 Status Task CreateGroup\n\n"
                    f"• Created: {created}\n"
                    f"• Current: {current}\n"
                    f"• Running: {'Ya' if running else 'Tidak'}\n"
                    f"• Paused: {'Ya' if paused else 'Tidak'}\n"
                    f"• Elapsed: {format_duration(elapsed)}\n"
                    f"• Start: {start_time.strftime('%Y-%m-%d %H:%M:%S')}"
                )
                await callback_query.answer(status_text, show_alert=True)
            elif task_id in COMPLETED_CREATEGROUP_TASKS:
                info = COMPLETED_CREATEGROUP_TASKS[task_id]
                status_str = "Gagal ❌" if info.get("status") == "failed" else "Selesai ✅"
                err_msg = f"\nError: {info.get('error')}" if info.get('status') == "failed" else ""
                
                await callback_query.answer(
                    f"Task Terakhir: {status_str}\n"
                    f"Created: {len(info.get('created_groups', []))}/{info.get('count')}"
                    f"{err_msg}",
                    show_alert=True
                )
            else:
                await callback_query.answer("Tidak ada task aktif atau riwayat task.")
        
        elif action == "list":
            if task_id in CREATEGROUP_TASKS:
                groups = CREATEGROUP_TASKS[task_id].get("created_groups", [])
                if groups:
                    list_text = "📋 Grup yang Telah Dibuat:\n\n"
                    for idx, group in enumerate(groups[-10:], 1):  # Tampilkan 10 terakhir
                        list_text += f"{idx}. {group['name']}\n   ID: {group['id']}\n\n"
                    
                    if len(groups) > 10:
                        list_text += f"... dan {len(groups) - 10} grup lainnya"
                    
                    await callback_query.answer(list_text, show_alert=True)
                else:
                    await callback_query.answer("Belum ada grup yang dibuat")
            else:
                await callback_query.answer("Tidak ada task yang berjalan")
        
        elif action == "recurring":
            if task_id in COMPLETED_CREATEGROUP_TASKS:
                if task_id in CREATEGROUP_TASKS:
                    await callback_query.answer("⚠️ Task CreateGroup masih berjalan!", show_alert=True)
                    return
                
                conf = COMPLETED_CREATEGROUP_TASKS[task_id]
                
                # Show confirmation menu
                buttons = [
                    [
                        InlineKeyboardButton("✅ Ya, Ulangi", callback_data="confirm_recur_creategroup"),
                        InlineKeyboardButton("❌ Tidak", callback_data="status_creategroup")
                    ]
                ]
                
                await callback_query.message.edit_text(
                    f"🔁 <b>Konfirmasi Recurring</b>\n\n"
                    f"Apakah Anda yakin ingin mengulang task ini?\n"
                    f"• Account: <b>{callback_query.from_user.mention}</b>\n"
                    f"• Total: <code>{conf['count']}</code> grup\n"
                    f"• Tipe: <code>{conf['group_type']}</code>\n"
                    f"• Act Delay: <code>{conf.get('action_delay', 3.0)}</code>s\n"
                    f"• GC Delay: <code>{conf['delay']}</code>s\n"
                    f"• Batch: <code>{conf['batch_size']}</code> | <code>{conf['extra_delay_minutes']}</code>m\n"
                    f"• Batch Act: <code>{conf.get('batch_action', 30)}</code> | <code>{conf.get('ba_delay', 30)}</code>s\n"
                    f"• Pattern: <code>{html.escape(conf['name_pattern'][:25])}...</code>\n"
                    f"• Bots: <code>{'Yes' if conf.get('invite_bots', True) else 'No'}</code>\n\n"
                    f"<i>Task akan menggunakan konfigurasi yang sama.</i>",
                    reply_markup=InlineKeyboardMarkup(buttons),
                    parse_mode=ParseMode.HTML
                )
            else:
                await callback_query.answer("Tidak ada task selesai untuk diulang")
        
        elif action == "confirm_recur":
            if task_id in COMPLETED_CREATEGROUP_TASKS:
                if task_id in CREATEGROUP_TASKS:
                    await callback_query.answer("⚠️ Task CreateGroup masih berjalan!", show_alert=True)
                    return
                
                conf = COMPLETED_CREATEGROUP_TASKS[task_id]
                
                # Find client
                client_id = conf.get("client_id", conf["user_id"])
                user_client = next((c for c in Altruix.clients if c.me.id == client_id), None)
                if not user_client and Altruix.clients:
                    user_client = Altruix.clients[0]
                
                if not user_client:
                    await callback_query.answer("❌ Tidak ada userbot aktif!", show_alert=True)
                    return
                
                # Start task
                await callback_query.answer("🔁 Mengulang task...")
                
                # Update control message with starting status
                await callback_query.message.edit_text(
                    f"🔄 <b>Mengulang Task CreateGroup...</b>\n\n"
                    f"• Account: {callback_query.from_user.mention}\n"
                    f"• Total: {conf['count']} grup\n"
                    f"• Tipe: {conf['group_type']}",
                    parse_mode=ParseMode.HTML
                )
                
                asyncio.create_task(
                    creategroup_loop(
                        user_client=user_client,
                        bot_client=Altruix.bot,
                        initial_message=callback_query.message,
                        delay=conf["delay"],
                        count=conf["count"],
                        extra_delay_minutes=conf["extra_delay_minutes"],
                        batch_size=conf["batch_size"],
                        group_type=conf["group_type"],
                        name_pattern=conf["name_pattern"],
                        username_prefix=conf["username_prefix"],
                        bot_identifiers=conf["bot_identifiers"],
                        control_message=callback_query.message,
                        action_delay=conf.get("action_delay", 3.0),
                        invite_bots=conf.get("invite_bots", True),
                        anon_mode=conf.get("anon_mode", True),
                        copy_messages=conf.get("copy_messages", True),
                        description=conf.get("description", "Powered by @AlphaXproject"),
                        photo_source=conf.get("photo_source", "source"),
                        custom_photo_id=conf.get("custom_photo_id"),
                        log_destination=conf.get("log_destination", "both"),
                        log_format=conf.get("log_format", "zip"),
                        pin_first_msg=conf.get("pin_first_msg", True),
                        msg_img=conf.get("msg_img", True),
                        rand_len=conf.get("rand_len", 0),
                        rand_lower=conf.get("rand_lower", False),
                        rand_upper=conf.get("rand_upper", False),
                        rand_static=conf.get("rand_static", False),
                        batch_action=conf.get("batch_action", 30),
                        ba_delay=conf.get("ba_delay", 30),
                        user_id=user_id
                    )
                )
            else:
                await callback_query.answer("Tidak ada task selesai untuk diulang.")
        
        elif action == "edit_last":
            if task_id in CREATEGROUP_TASKS:
                groups = CREATEGROUP_TASKS[task_id].get("created_groups", [])
                if groups:
                    last_group = groups[-1]
                    await callback_query.answer(f"Edit grup terakhir: {last_group['name']}")
                    # Implement edit last group
                else:
                    await callback_query.answer("Belum ada grup yang dibuat")
            else:
                await callback_query.answer("Tidak ada task yang berjalan")
        
        elif action == "download_log":
            if task_id in COMPLETED_CREATEGROUP_TASKS:
                await callback_query.answer("Log sudah dikirim ke channel")
            else:
                await callback_query.answer("Belum ada log yang tersedia")
        
        elif action == "list_groups":
            if task_id in COMPLETED_CREATEGROUP_TASKS:
                groups = COMPLETED_CREATEGROUP_TASKS[task_id].get("created_groups", [])
                if groups:
                    list_text = "📋 <b>Semua Grup yang Dibuat:</b>\n\n"
                    for idx, group in enumerate(groups, 1):
                        list_text += f"{idx}. {group['name']}\n   Link: {group['link'][:30]}...\n\n"
                    
                    await callback_query.answer(list_text, show_alert=True)
                else:
                    await callback_query.answer("Tidak ada grup dalam task ini")
            else:
                await callback_query.answer("Task belum selesai")
        
        elif action == "delete_task":
            if task_id in COMPLETED_CREATEGROUP_TASKS:
                COMPLETED_CREATEGROUP_TASKS.pop(task_id)
                await callback_query.answer("Task dihapus dari memory")
                await callback_query.message.delete()
            else:
                await callback_query.answer("Tidak ada task untuk dihapus")
    
    except Exception as e:
        logger.error(f"Error in creategroup_control_handler: {e}")
        await callback_query.answer(f"Error: {str(e)}")

# Log sukses loading
# try:
#     Altruix.log(f"[DEBUG] Loaded → {__plugin_name__} {PLUGIN_VERSION}", level=20)
# except Exception as e:
#     logger.info(f"[DEBUG] Loaded → {__plugin_name__} {PLUGIN_VERSION}")
