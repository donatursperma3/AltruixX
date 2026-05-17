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
import traceback
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any
import random
import base64

from pyrogram import Client, filters, raw
from pyrogram.errors import (
    FloodWait, PeerIdInvalid, UserNotParticipant, UsernameNotOccupied,
    UsernameInvalid, ChannelInvalid, ChannelPrivate, ChatAdminRequired,
    UserAlreadyParticipant, SlowmodeWait, RPCError, ChatWriteForbidden,
    UserIsBlocked, BadRequest, InviteHashInvalid, InviteHashExpired,
    PhotoInvalidDimensions, WebpageCurlFailed, WebpageMediaEmpty,
    MessageTooLong
)
from pyrogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ChatPhoto, ForceReply
)
from pyrogram.enums import ChatType, ChatMemberStatus, ParseMode, ChatAction

from Main import Altruix
from Main.core.decorators import log_errors
from Main.core.types.message import Message as AltruixMessage
from Main.utils.helpers import ChatPrivileges
from Main.core.decorators import log_errors, iuser_check
from Main.utils.essentials import Essentials
# from Main.utils.helpers import run_shell_cmd
import logging

plugin_name = f"{os.path.basename(__file__)}"
__plugin_name__ = plugin_name if plugin_name else "xcreategroup"
PLUGIN_VERSION = "0.2.396"  # ✅ ADDED: Smart Recovery Indexing for Indicators

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
RECOVERY_NOTIFIED = set() # ✅ Anti-Duplicate Guard
CREATE_LOCK = asyncio.Lock()
from Main.utils.file_helpers import get_db_path

STORAGE_FILE = get_db_path("xcreategroup_cache.json")
PENDING_CONFIRMATIONS = {}

async def save_creategroup_cache():
    def make_serializable(obj):
        import asyncio
        if isinstance(obj, dict):
            return {k: make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [make_serializable(i) for i in obj]
        elif hasattr(obj, "isoformat"):
            return obj.isoformat()
        elif isinstance(obj, asyncio.Event) or "Task" in str(type(obj)) or "Message" in str(type(obj)):
            return None # Skip non-serializable objects
        return obj

    try:
        import json
        data = {
            "tasks": {},
            "completed": {}
        }
        
        # Clean tasks
        for tid, task in CREATEGROUP_TASKS.items():
            task_copy = task.copy()
            # Explicitly remove known big objects/events
            keys_to_remove = ["pause_event", "status_task", "task", "task_obj", "log_progress_msg"]
            for key in keys_to_remove:
                task_copy.pop(key, None)
            data["tasks"][tid] = make_serializable(task_copy)
            
        # Clean completed tasks
        for tid, comp in COMPLETED_CREATEGROUP_TASKS.items():
            data["completed"][tid] = make_serializable(comp)
            
        # Atomic Write
        temp_file = f"{STORAGE_FILE}.tmp"
        with open(temp_file, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(temp_file, STORAGE_FILE)
    except Exception as e:
        import logging
        logger = logging.getLogger("altruix.xcreategroup")
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
                logger.error(f"[CreateGroup] Corrupted cache detected! Backed up to {bak_file}. Error: {jde}")
                return
                
            task_count = len(data.get("tasks", {}))
            comp_count = len(data.get("completed", {}))
            logger.info(f"[CreateGroup] Memuat cache: {task_count} task aktif, {comp_count} task selesai.")
            
            for tid, task_data in data.get("tasks", {}).items():
                if "start_time" in task_data and isinstance(task_data["start_time"], str):
                    try:
                        task_data["start_time"] = datetime.fromisoformat(task_data["start_time"])
                    except: pass
                task_data["pause_event"] = asyncio.Event()
                task_data["pause_event"].set()
                # Ensure the key is the TID (#CGabcd)
                key = task_data.get("tid", tid)
                CREATEGROUP_TASKS[key] = task_data
                
            for tid, comp_data in data.get("completed", {}).items():
                if "start_time" in comp_data and isinstance(comp_data["start_time"], str):
                    try:
                        comp_data["start_time"] = datetime.fromisoformat(comp_data["start_time"])
                    except: pass
                COMPLETED_CREATEGROUP_TASKS[tid] = comp_data
        else:
            logger.info("[CreateGroup] File cache tidak ditemukan, memulai dengan data kosong.")
    except Exception as e:
        logger.error(f"[CreateGroup] Error loading cache: {e}")

async def check_interrupted_tasks():
    """Scan for tasks that were interrupted by a restart and notify user."""
    logger.info("[CreateGroup] Memulai pemeriksaan task yang terhenti...")
    
    if not CREATEGROUP_TASKS:
        logger.info("[CreateGroup] Tidak ada task aktif di cache, skip pemeriksaan.")
        return
    
    logger.info(f"[CreateGroup] Mengevaluasi {len(CREATEGROUP_TASKS)} task potensial, menunggu bot siap...")
    
    # Tunggu bot asisten dan session siap secara dinamis
    max_wait = 120  # Maksimal 120 detik (untuk banyak session)
    waited = 0
    while waited < max_wait:
        bot_ready = Altruix.bot and Altruix.bot.is_connected
        sessions_ready = len(Altruix.clients) > 0
        if bot_ready and sessions_ready:
            logger.info(f"[CreateGroup] Bot dan Sessions siap setelah {waited}s.")
            break
        await asyncio.sleep(2)
        waited += 2
        if waited % 10 == 0:
            logger.info(f"[CreateGroup] Startup Wait: Bot={bool(bot_ready)}, Sessions={len(Altruix.clients)} ({waited}/{max_wait}s)")

    if not Altruix.bot or not Altruix.bot.is_connected:
        logger.warning(f"[CreateGroup] Bot Assistant tidak siap setelah {waited}s, pemeriksaan dibatalkan.")
        return

    # Gunakan LOG_CHAT_ID terbaru dari Altruix
    target_log_chat = Altruix.log_chat or Altruix.config.LOG_CHAT_ID
    if not target_log_chat and Altruix.config.OWNER_USERS_ID:
        target_log_chat = Altruix.config.OWNER_USERS_ID[0]

    if not target_log_chat:
        logger.error("[CreateGroup] LOG_CHAT_ID tidak ditemukan, gagal mengirim notifikasi recovery.")
        return
    
    logger.info(f"[CreateGroup] Target log chat: {target_log_chat}")
        
    interrupted_found = False
    tasks_to_clean = []  # Task yang sudah selesai tapi belum dibersihkan
    
    # Use copy to avoid 'dictionary changed size during iteration' and 'module' shadowing issues
    active_tasks = dict(CREATEGROUP_TASKS)
    # --- Smart Indexing for Recovery ---
    # Group tasks by admin_id and start_time (rounded to minute) to guess groups
    task_groups = {}
    for key_id, task_data in active_tasks.items():
        admin_id = task_data.get("admin_id", 0)
        start_time = task_data.get("start_time")
        # Round start time to nearest 5 minutes to catch tasks started in a single bulk run
        if isinstance(start_time, datetime):
            time_key = start_time.replace(second=0, microsecond=0)
            time_key = time_key.replace(minute=(time_key.minute // 5) * 5)
        else:
            time_key = "unknown"
            
        group_key = f"{admin_id}_{time_key}"
        if group_key not in task_groups:
            task_groups[group_key] = []
        task_groups[group_key].append(key_id)

    # Sort each group by actual start_time to assign indices
    smart_indices = {}
    for group_key, keys in task_groups.items():
        sorted_keys = sorted(keys, key=lambda k: active_tasks[k].get("start_time") if isinstance(active_tasks[k].get("start_time"), datetime) else datetime.min)
        total = len(sorted_keys)
        for idx, key in enumerate(sorted_keys, 1):
            smart_indices[key] = (idx, total)

    for key_id, task_data in active_tasks.items():
        # Task yang ada di CREATEGROUP_TASKS saat startup dipastikan adalah task yang terhenti
        # karena task yang selesai normal akan dihapus dari dictionary ini.
        current = task_data.get("current_index", 0)
        params = task_data.get("params", {})
        total = params.get("count", 0)
        tid_display = task_data.get("tid", key_id) # Gunakan user-friendly TID jika ada
        
        # Safety check: jika data tidak valid, abaikan
        if total == 0:
            logger.info(f"[CreateGroup] Task {key_id}: count=0, skip.")
            continue
        
        # Filter: task yang sudah benar-benar selesai
        # Jika current >= total DAN tidak ada step aktif (loop selesai)
        if current >= total and task_data.get("current_step") is None:
            logger.info(f"[CreateGroup] Task {key_id}: sudah selesai ({current}/{total}), akan dibersihkan.")
            tasks_to_clean.append(key_id)
            continue
            
        interrupted_found = True
        remaining = total - current
        step_info = task_data.get("current_step", "unknown")
        
        # Dapatkan nama akun
        account_name = task_data.get("account_name", "Unknown Account")
        client_id = task_data.get("user_id")
        
        if account_name == "Unknown Account" and client_id:
            user_client = next((c for c in Altruix.clients if c.me and c.me.id == client_id), None)
            if user_client:
                account_name = f"{user_client.me.first_name or ''} {user_client.me.last_name or ''}".strip()
        
        logger.info(f"[CreateGroup] DITEMUKAN: Task {key_id} (TID={tid_display}): {current}/{total}, step={step_info}, account={account_name}")
        
        # Prevent duplicate notifications for the same task in one session
        if key_id in RECOVERY_NOTIFIED:
            logger.info(f"[CreateGroup] Task {key_id} sudah dinotifikasi sebelumnya, skip.")
            continue
            
        # Get account indicator from params with smart fallback
        smart_idx, smart_total = smart_indices.get(key_id, (1, 1))
        acc_idx = params.get("account_idx", smart_idx)
        tot_accs = params.get("total_accs", smart_total)
        
        try:
            # Build keyboard
            keyboard = []
            
            # Row 1: Action buttons
            keyboard.append([
                InlineKeyboardButton("Resume", callback_data=f"recover_creategroup:{key_id}"),
                InlineKeyboardButton("End", callback_data=f"delete_task_creategroup:{key_id}")
            ])
            
            # Row 2: Info link (optional)
            chat_link = task_data.get("invite_link")
            if not chat_link and task_data.get("current_chat_id"):
                c_id = task_data.get("current_chat_id")
                # Format link for supergroup/channel (T.me/c/ID/1)
                if str(c_id).startswith("-100"):
                    chat_link = f"https://t.me/c/{str(c_id)[4:]}/1"
            
            if chat_link:
                keyboard.append([InlineKeyboardButton("View", url=chat_link)])
                
            buttons = InlineKeyboardMarkup(keyboard)

            await Altruix.bot.send_message(
                target_log_chat,
                f"<blockquote expandable>"
                f"⚠️ <b>Interrupted Task Detected {acc_idx}/{tot_accs}</b>\n\n"
                f"Task CreateGroup terhenti akibat restart.\n"
                f"• Account: <b>{html.escape(account_name)}</b>\n"
                f"• Task ID: <code>{tid_display}</code>\n"
                f"• Progress: {current}/{total} grup (sisa {remaining})\n"
                f"• Step terakhir: <code>{step_info}</code>\n\n"
                f"<i>Ingin melanjutkan proses yang tersisa?</i>"
                f"</blockquote>",
                reply_markup=buttons,
                parse_mode=ParseMode.HTML
            )
            RECOVERY_NOTIFIED.add(key_id)
            logger.info(f"[CreateGroup] ✅ Notifikasi recovery dikirim untuk Task {key_id}")
        except Exception as e:
            logger.error(f"[CreateGroup] ❌ Gagal kirim notifikasi recovery untuk {key_id}: {e}")
    
    # Bersihkan task yang sudah selesai dari cache
    for key_id in tasks_to_clean:
        if key_id in CREATEGROUP_TASKS:
            del CREATEGROUP_TASKS[key_id]
    if tasks_to_clean:
        await save_creategroup_cache()
        logger.info(f"[CreateGroup] Dibersihkan {len(tasks_to_clean)} task selesai dari cache.")
                
    if interrupted_found:
        logger.info("[CreateGroup] Semua task terhenti telah dinotifikasi.")
    else:
        logger.info("[CreateGroup] Tidak ada task terhenti yang perlu di-resume.")

# Load cache on startup
async def startup_initialization():
    try:
        await load_creategroup_cache()
        logger.info(f"[CreateGroup] Cache loaded. Active tasks: {len(CREATEGROUP_TASKS)}")
        # Langsung panggil, tidak perlu create_task terpisah
        await check_interrupted_tasks()
    except Exception as e:
        logger.error(f"[CreateGroup] ❌ Startup initialization GAGAL: {e}\n{traceback.format_exc()}")

# Schedule startup — wrapped dengan error handling
try:
    asyncio.ensure_future(startup_initialization())
except RuntimeError:
    # Jika belum ada event loop (misal saat import), jadwalkan nanti
    logger.warning("[CreateGroup] Event loop belum aktif saat import, startup dijadwalkan ulang.")
    import atexit
    _startup_scheduled = False
    def _schedule_startup():
        global _startup_scheduled
        if not _startup_scheduled:
            _startup_scheduled = True
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(startup_initialization())
            except: 
                pass


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
    
    # Use case-insensitive regex for placeholders
    import re
    
    # Replace date/time placeholders
    name = pattern
    name = re.sub(r'\(tahun\)', year_last2, name, flags=re.IGNORECASE)
    name = re.sub(r'\(bulan\)', month_num, name, flags=re.IGNORECASE)
    name = re.sub(r'\(tanggal\)', day_num, name, flags=re.IGNORECASE)
    
    # Check if (index) is explicitly used (case-insensitive)
    index_pattern = re.compile(r'\(index\)', re.IGNORECASE)
    has_index_placeholder = bool(index_pattern.search(name))
    
    rand_text = ""
    if predefined_rand is not None:
        rand_text = predefined_rand
    elif rand_len > 0 and (rand_lower or rand_upper):
        import string
        chars = ""
        if rand_lower: chars += string.ascii_lowercase
        if rand_upper: chars += string.ascii_uppercase
        rand_text = "".join(random.choices(chars, k=rand_len))

    if rand_text:
        if has_index_placeholder:
            # Inject rand_text before the first (index)
            name = index_pattern.sub(f"{rand_text} \\g<0>", name, count=1)
            # Subsequent (index) remain as is for now
        else:
            name = f"{name} {rand_text}"

    # Final replacement of all (index) placeholders
    name = index_pattern.sub(str(index), name)
    
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
    except MessageTooLong:
        try:
            from Main.utils.file_helpers import make_file_from_text
            import os
            file_path = await make_file_from_text(text, file_name="creategroup_log.txt")
            log_msg = await bot_client.send_document(
                LOG_CHAT_ID,
                file_path,
                caption=f"📄 <b>Log message too long</b>\n#CREATEGROUP_LOG",
                reply_to_message_id=reply_to_msg_id,
                parse_mode=ParseMode.HTML
            )
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.error(f"Gagal kirim log file ke LOG_CHAT_ID: {e}")
    except Exception as e:
        logger.error(f"Gagal kirim notifikasi ke LOG_CHAT_ID: {e}")

    return log_msg


# ==================== TASK REGISTRY SYNC HELPERS ====================
def _sync_pause_from_registry(task_key: str, tid: str):
    """Sync pause state FROM global _TASK_REGISTRY TO local CREATEGROUP_TASKS.
    
    When xtaskmanager sets paused=True in the global registry, propagate it
    to CREATEGROUP_TASKS so the loop actually pauses.
    """
    registry = getattr(Altruix, "_TASK_REGISTRY", {})
    if tid in registry and registry[tid].get("paused", False):
        if task_key in CREATEGROUP_TASKS and not CREATEGROUP_TASKS[task_key].get("paused", False):
            CREATEGROUP_TASKS[task_key]["paused"] = True
            if "pause_event" in CREATEGROUP_TASKS[task_key]:
                CREATEGROUP_TASKS[task_key]["pause_event"].clear()
            logger.info(f"[Sync] Pause propagated from _TASK_REGISTRY to CREATEGROUP_TASKS for {tid}")


def _sync_resume_from_registry(task_key: str, tid: str):
    """Sync resume state FROM global _TASK_REGISTRY TO local CREATEGROUP_TASKS.
    
    When xtaskmanager sets paused=False in the global registry, propagate it
    to CREATEGROUP_TASKS so the loop actually resumes.
    """
    registry = getattr(Altruix, "_TASK_REGISTRY", {})
    if tid in registry and not registry[tid].get("paused", False):
        if task_key in CREATEGROUP_TASKS and CREATEGROUP_TASKS[task_key].get("paused", False):
            CREATEGROUP_TASKS[task_key]["paused"] = False
            if "pause_event" in CREATEGROUP_TASKS[task_key]:
                CREATEGROUP_TASKS[task_key]["pause_event"].set()
            logger.info(f"[Sync] Resume propagated from _TASK_REGISTRY to CREATEGROUP_TASKS for {tid}")


# ==================== UI HELPERS ====================
def get_creategroup_dashboard_text(tid: str):
    """Generate a clean, standardized dashboard text for a task."""
    # Sanitize tid to prevent header duplication if it was polluted
    tid = str(tid).split('\n')[0].replace('━', '').replace('⚙️ Manage Task:', '').strip()
    
    task = CREATEGROUP_TASKS.get(tid)
    if not task:
        return f"❌ <b>Task {tid} tidak ditemukan di memori.</b>"
    
    params = task.get("params", {})
    current = task.get("current_index", 0)
    total = params.get("count", 0)
    step = task.get("current_step", "N/A")
    account = task.get("account_name", "Unknown")
    is_paused = task.get("paused", False)
    is_running = task.get("running", False)
    task_obj = task.get("task_obj")
    
    # Live status check
    is_alive = task_obj and not task_obj.done()
    if is_alive:
        status = "⏸️ Paused" if is_paused else "🟢 Running"
    else:
        status = "⚠️ Interrupted" if is_running else "🛑 Stopped"
    
    uptime = ""
    start_str = "N/A"
    if "start_time" in task:
        st = task["start_time"]
        elapsed = (datetime.now() - st).total_seconds()
        uptime = f"\n• <b>Uptime:</b> <code>{format_duration(elapsed)}</code>"
        start_str = st.strftime("%Y-%m-%d %H:%M:%S")

    created_count = len(task.get("created_groups", []))
    separator = "━" * 15
    
    text = (
        f"<blockquote expandable><b>⚙️ Manage Task:</b> <code>{tid}</code>\n"
        f"{separator}\n"
        f"• <b>Account:</b> {account}\n"
        f"• <b>Status:</b> {status}\n"
        f"• <b>Created:</b> <code>{created_count}</code> / <b>Attempt:</b> <code>{int(current)}</code> / <b>Total:</b> <code>{int(total)}</code>\n"
        f"• <b>Started:</b> <code>{start_str}</code>{uptime}\n"
        f"• <b>Last Step:</b> <code>{step}</code>\n"
        f"</blockquote>"
    )
    return text


# ==================== KEYBOARD GENERATORS ====================
async def get_creategroup_keyboard(client_id: int, tid: str, menu_type: str = "main"):
    """Generate the control keyboard for CreateGroup tasks."""
    
    if menu_type == "manage":
        # Sub-menu for Resume, End, View
        # Check current state for Pause/Resume label
        is_paused = False
        if tid in CREATEGROUP_TASKS:
            is_paused = CREATEGROUP_TASKS[tid].get("paused", False)
        
        keyboard = [
            [
                InlineKeyboardButton(await Essentials.get_user_button_style(client_id, "▶️ Resume" if is_paused else "⏸️ Pause"), 
                                     callback_data=f"{'resume' if is_paused else 'pause'}_creategroup:{tid}"),
                InlineKeyboardButton(await Essentials.get_user_button_style(client_id, "🛑 End"), 
                                     callback_data=f"stop_creategroup:{tid}"),
                InlineKeyboardButton(await Essentials.get_user_button_style(client_id, "🔄 View"), 
                                     callback_data=f"status_creategroup:{tid}")
            ],
            [
                InlineKeyboardButton(await Essentials.get_user_button_style(client_id, "🔁 Recurring"), 
                                     callback_data=f"recurring_creategroup:{tid}"),
                InlineKeyboardButton(await Essentials.get_user_button_style(client_id, "🔙 Back"), 
                                     callback_data=f"back_creategroup:{tid}")
            ]
        ]
    else:
        # Main Menu
        keyboard = [
            [
                InlineKeyboardButton(await Essentials.get_user_button_style(client_id, "⚙️ Manage Task"), 
                                     callback_data=f"manage_creategroup:{tid}"),
                InlineKeyboardButton(await Essentials.get_user_button_style(client_id, "📊 Status"), 
                                     callback_data=f"status_creategroup:{tid}")
            ],
            [
                InlineKeyboardButton(await Essentials.get_user_button_style(client_id, "📋 List Created"), 
                                     callback_data=f"list_creategroup:{tid}"),
                InlineKeyboardButton(await Essentials.get_user_button_style(client_id, "✏️ Edit Name"), 
                                     callback_data=f"edit_last_creategroup:{tid}")
            ],
            [
                InlineKeyboardButton(await Essentials.get_user_button_style(client_id, "✅ Check Created"), 
                                     callback_data=f"list_groups_creategroup:{tid}")
            ]
        ]
    
    return InlineKeyboardMarkup(keyboard)


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
    temp_pin: bool = True,
    quote_block: bool = True,
    user_id: Optional[int] = None,
    task_id: str = None,
    is_resume: bool = False,
    account_idx: int = 1,
    total_accs: int = 1
):
    """Main loop untuk membuat grup"""
    effective_user_id = user_id or (initial_message.from_user.id if initial_message.from_user else None)
    if not effective_user_id:
        logger.error("Cannot determine user_id for creategroup task")
        return

    if not task_id:
        task_id = f'creategroup_{effective_user_id}'

    # Task Registration for .tasklist / .taskstatus
    from Main.plugins.userbot.xtaskmanager import register_task, unregister_task, generate_task_id

    # Get tid from state if resuming, else generate new
    if is_resume and task_id and task_id in CREATEGROUP_TASKS:
        tid = CREATEGROUP_TASKS[task_id].get("tid")
        if not tid:
            tid = task_id # Fallback if task_id was already the tid
    else:
        # Use explicit task_id if it's already a tid format, else generate
        tid = task_id if (task_id and task_id.startswith("CG-")) else generate_task_id("CG")

    # Standardize on using tid as the main key in memory
    if tid:
        # Prevent "Dirty TID" pollution from message text extraction
        tid = str(tid).split('\n')[0].replace('━', '').replace('⚙️ Manage Task:', '').strip()
    
    task_key = tid

    created_groups = []
    batch_groups = [] # Buffer for current batch
    last_log_msg = None
    photo_path = None  # Cache untuk foto profil

    # Determine dynamic labels
    is_channel = group_type == "c"
    type_label = "Channel" if is_channel else "Group" # Capitalized for Titles
    unit_label = "channel" if is_channel else "grup"  # lowercase for counts
    type_name = "Channel" if is_channel else "Grup"   # Capitalized for messages
    
    # 🔥 Ensure integer type for count (other parameters can be floats)
    count = int(count)
    
    user_info = None
    photo_path = None

    try:
        # Initialize task state
        if task_key in CREATEGROUP_TASKS and is_resume:
            # Keep existing state but ensure it's marked as running
            CREATEGROUP_TASKS[task_key]["running"] = True
            CREATEGROUP_TASKS[task_key]["task_obj"] = asyncio.current_task()
            
            # Ensure account indicator is updated/synced on resume
            if "params" in CREATEGROUP_TASKS[task_key]:
                CREATEGROUP_TASKS[task_key]["params"]["account_idx"] = account_idx
                CREATEGROUP_TASKS[task_key]["params"]["total_accs"] = total_accs
                
            if "pause_event" not in CREATEGROUP_TASKS[task_key]:
                CREATEGROUP_TASKS[task_key]["pause_event"] = asyncio.Event()
                CREATEGROUP_TASKS[task_key]["pause_event"].set()
        else:
            CREATEGROUP_TASKS[task_key] = {
                "running": True,
                "paused": False,
                "paused_by_user": False,
                "pause_event": asyncio.Event(),
                "tid": tid,
                "current_index": 0,
                "current_step": None,
                "step_index": 0,
                "current_chat_id": None,
                "current_group_name": None,
                "invite_link": None,
                "first_msg_id": None,
                "created_groups": [],
                "start_time": datetime.now(),
                "control_message_id": control_message.id if control_message else None,
                "admin_id": user_id or (initial_message.from_user.id if initial_message and initial_message.from_user else None),
                "user_id": user_client.me.id, # The actual session account
                "account_name": (user_client.me.first_name or "") + (f" {user_client.me.last_name}" if user_client.me.last_name else ""),
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
                    "log_format": log_format,
                    "pin_first_msg": pin_first_msg,
                    "temp_pin": temp_pin,
                    "quote_block": quote_block,
                    "rand_len": rand_len,
                    "rand_lower": rand_lower,
                    "rand_upper": rand_upper,
                    "rand_static": rand_static,
                    "batch_action": batch_action,
                    "ba_delay": ba_delay,
                    "account_idx": account_idx,
                    "total_accs": total_accs
                },
                "task_obj": asyncio.current_task()
            }
            CREATEGROUP_TASKS[task_key]["pause_event"].set()
        await save_creategroup_cache()
        
        # Recovery control message if missing (for resumed tasks)
        if not control_message and "control_message_id" in CREATEGROUP_TASKS[task_key]:
             try:
                  control_message = await bot_client.get_messages(LOG_CHAT_ID, CREATEGROUP_TASKS[task_key]["control_message_id"])
             except Exception as e:
                  logger.warning(f"Gagal recover control message: {e}")

        # Dapatkan info user dasar dulu untuk nama di control message
        user_info = await user_client.get_me()
        account_name_raw = f"{user_info.first_name or ''} {user_info.last_name or ''}".strip()
        assistant = await bot_client.get_me()

        # Definisikan tombol kontrol dengan TID eksplisit agar handler tidak bingung
        control_buttons = await get_creategroup_keyboard(user_client.me.id, tid, menu_type="main")

        # Pastikan control_message ada di LOG_CHAT_ID dan dikirim oleh bot agar tombol muncul
        is_valid_control = (
            control_message and 
            str(control_message.chat.id) == str(LOG_CHAT_ID) and 
            control_message.from_user and 
            control_message.from_user.id == assistant.id
        )
        
        if not is_valid_control:
             # Jika tidak valid (misal dari User command atau PM), buat baru di log group oleh Bot
             try:
                 control_message = await bot_client.send_message(
                     LOG_CHAT_ID,
                     f"🚀 <b>Task Control Panel {account_idx}/{total_accs}</b>\n"
                     f"• TID: <code>{tid}</code>\n"
                     f"• Account: <b>{html.escape(account_name_raw)}</b>\n"
                     f"• Target: <code>{count}</code> grup\n\n"
                     f"<i>Linear Log threading aktif di bawah pesan ini.</i>",
                     reply_markup=control_buttons,
                     parse_mode=ParseMode.HTML
                 )
                 # Update ID di state agar bisa di-recover nanti
                 CREATEGROUP_TASKS[task_key]["control_message_id"] = control_message.id
                 await save_creategroup_cache()
             except Exception as e:
                 logger.warning(f"Gagal buat control msg baru di LOG_CHAT_ID: {e}")
        else:
             # Jika sudah dari bot di log, pastikan tombolnya ada (update jika perlu)
             try:
                 await control_message.edit_reply_markup(reply_markup=control_buttons)
             except Exception as e:
                 logger.debug(f"Gagal update markup control msg: {e}")

        # Determine the best message ID to reply to in the log channel
        reply_id = getattr(control_message, 'id', None)
        if initial_message and initial_message.chat and str(initial_message.chat.id) == str(LOG_CHAT_ID):
             reply_id = initial_message.id

        # Dapatkan info user
        user_info = await user_client.get_me()
        account_name_raw = f"{user_info.first_name or ''} {user_info.last_name or ''}".strip()
        
        # Update task state with account name
        CREATEGROUP_TASKS[task_key]["account_name"] = account_name_raw
        
        # Register task with account name
        register_task(tid, asyncio.current_task(), "Create Group", "xcreategroup", effective_user_id, f"Count: {count}", user_name=account_name_raw)
        
        # Dapatkan entity bot asisten
        try:
            assistant = await bot_client.get_me()
            
            if is_resume:
                resume_msg = (
                    f"<blockquote expandable>"
                    f"🔄 <b>Task Create {type_label} Resumed</b>\n"
                    f"• Task ID: <code>{tid}</code>\n"
                    f"• Account: <b>{html.escape(account_name_raw)}</b>\n"
                    f"• Melanjutkan dari {unit_label} ke-{CREATEGROUP_TASKS[task_key].get('current_index', 0) + 1}\n"
                    f"</blockquote>"
                )
                await send_log_notification(bot_client, resume_msg, CREATEGROUP_TASKS[task_key]["user_id"], reply_id)
            else:
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
                effective_user_id,
                reply_id
            )
        except Exception as e:
            await send_log_notification(
                bot_client,
                f"❌ Gagal mendapatkan info bot asisten: {str(e)}",
                effective_user_id,
                reply_id
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
                        effective_user_id,
                        reply_id
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
                        effective_user_id,
                        reply_id
                    )
                else:
                    await send_log_notification(
                        bot_client,
                        f"⚠️ Foto profil tidak tersedia atau gagal di-download",
                        effective_user_id,
                        reply_id
                    )
            except Exception as e:
                await send_log_notification(
                    bot_client,
                    f"⚠️ Error download foto profil: {str(e)}",
                    effective_user_id,
                    reply_id
                )
        
        # Define state for convenient access
        state = CREATEGROUP_TASKS[task_key]

        # Generate static random text once if enabled
        static_rand_text = state.get("static_rand_text")
        if not static_rand_text and rand_static and rand_len > 0 and (rand_lower or rand_upper):
            import string
            chars = ""
            if rand_lower: chars += string.ascii_lowercase
            if rand_upper: chars += string.ascii_uppercase
            static_rand_text = "".join(random.choices(chars, k=rand_len))
            state["static_rand_text"] = static_rand_text
            await save_creategroup_cache()

        # Inisialisasi progress message di log group jika command bukan dari log group
        if control_message and str(control_message.chat.id) != str(LOG_CHAT_ID):
            try:
                log_progress_msg = await bot_client.send_message(
                    LOG_CHAT_ID,
                    "📊 <b>Memulai Tracker Progress...</b>",
                    parse_mode=ParseMode.HTML
                )
                CREATEGROUP_TASKS[task_key]["log_progress_msg"] = log_progress_msg
            except Exception as e:
                logger.error(f"Gagal kirim log progress awal: {e}")

        # Recovery control message if missing (moved higher, removing duplicate here)
        pass

        # Determine starting index: if was in progress, resume same index, else next index
        last_index = CREATEGROUP_TASKS[task_key].get("current_index", 0)
        last_step = CREATEGROUP_TASKS[task_key].get("current_step")
        
        if is_resume and last_step is not None:
            i = last_index
        else:
            i = last_index + 1
            
        created_groups = CREATEGROUP_TASKS[task_key].get("created_groups", [])
        while i <= count:
            pinned_chat_id = None
            # Check if task is running (from either local or global registry)
            _sync_pause_from_registry(task_key, tid)
            if not CREATEGROUP_TASKS.get(task_key, {}).get("running", True):
                account_name = f"{user_info.first_name or ''} {user_info.last_name or ''}".strip()
                await send_log_notification(
                    bot_client,
                    f"🛑 Task Create {type_label} dihentikan oleh user pada {unit_label} ke-{i}\n• Account: {html.escape(account_name)}",
                    effective_user_id,
                    reply_id
                )
                break
            
            # Check if paused by user (from either CREATEGROUP_TASKS or global _TASK_REGISTRY)
            if CREATEGROUP_TASKS[task_key].get("paused", False):
                CREATEGROUP_TASKS[task_key]["paused_by_user"] = True
                account_name = f"{user_info.first_name or ''} {user_info.last_name or ''}".strip()
                await send_log_notification(
                    bot_client,
                    f"⏸️ Task Create {type_label} dipause pada {unit_label} ke-{i}\n• Account: {html.escape(account_name)}",
                    effective_user_id,
                    reply_id
                )
                # Poll-based wait: check both local pause_event AND global registry
                while CREATEGROUP_TASKS.get(task_key, {}).get("paused", False):
                    _sync_resume_from_registry(task_key, tid)
                    if not CREATEGROUP_TASKS.get(task_key, {}).get("paused", False):
                        break
                    await asyncio.sleep(1)
                CREATEGROUP_TASKS[task_key]["paused_by_user"] = False
                account_name = f"{user_info.first_name or ''} {user_info.last_name or ''}".strip()
                await send_log_notification(
                    bot_client,
                    f"▶️ Task Create {type_label} di-resume pada {unit_label} ke-{i}\n• Account: {html.escape(account_name)}",
                    effective_user_id,
                    reply_id
                )
            
            group_start_time = datetime.now()
            
            # Granular Resume Logic: Check if we were in the middle of a group
            state = CREATEGROUP_TASKS[task_key]
            resuming_this_group = is_resume and state.get("current_index") == i and state.get("current_chat_id")
            
            if resuming_this_group:
                created_chat_id = state.get("current_chat_id")
                current_group_name = state.get("current_group_name")
                invite_link = state.get("invite_link")
                first_msg_id = state.get("first_msg_id")
                current_step = state.get("current_step")
                s_idx = state.get("step_index", 0)
                logger.info(f"Resuming {type_name} {i} ({current_group_name}) at step: {current_step} [{s_idx}]")
            else:
                current_group_name = generate_group_name(pattern=name_pattern, index=i, rand_len=rand_len, rand_lower=rand_lower, rand_upper=rand_upper, predefined_rand=static_rand_text)
                created_chat_id = None
                invite_link = None
                first_msg_id = None
                current_step = "create"
                s_idx = 0
                
                # Save initial state for this group
                state["current_index"] = i
                state["current_group_name"] = current_group_name
                state["current_step"] = "create"
                state["step_index"] = 0
                await save_creategroup_cache()

            current_username = f"{username_prefix}{i}" if username_prefix else None
            
            # Message buffer for consolidated logs area
            # Update: Name is now a hyperlink if username/link available, otherwise code. 
            # We don't have link yet at start, so we update it later or use placeholder?
            # Actually, we can update the header later. For now, let's keep it simple and update line 554/559.
            
            type_name = "Channel" if group_type == "c" else "Grup"
            current_log_header = f"🏗 <b>Memproses {type_name} {i}/{int(count)}</b>\n"
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
                msg = await send_log_notification(bot_client, current_log_text, effective_user_id, reply_to_msg_id=reply_id)
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
                    
                    # Check pause/stop (sync from global registry)
                    _sync_pause_from_registry(task_key, tid)
                    if not CREATEGROUP_TASKS.get(task_key, {}).get("running"):
                        break
                    
                    # Wait for pause event if paused (poll both sources)
                    while CREATEGROUP_TASKS.get(task_key, {}).get("paused"):
                        _sync_resume_from_registry(task_key, tid)
                        if not CREATEGROUP_TASKS.get(task_key, {}).get("paused"):
                            break
                        await asyncio.sleep(1)
                    
                    sleep_time = min(interval, total_seconds)
                    await asyncio.sleep(sleep_time)
                    total_seconds -= sleep_time
                
                if countdown_msg:
                    try: await countdown_msg.edit_text("✅ <b>Waktu tunggu selesai, melanjutkan proses...</b>", parse_mode=ParseMode.HTML)
                    except: pass

            action_count = 0
            async def handle_action_delay():
                nonlocal action_count
                
                # Immediate check before action delay
                _sync_pause_from_registry(task_key, tid)
                if not CREATEGROUP_TASKS.get(task_key, {}).get("running"): return
                
                while CREATEGROUP_TASKS.get(task_key, {}).get("paused"):
                    _sync_resume_from_registry(task_key, tid)
                    if not CREATEGROUP_TASKS.get(task_key, {}).get("paused"): break
                    await asyncio.sleep(1)

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
            
            # Variabel yang dibutuhkan di semua step — definisikan di luar blok kondisional
            is_supergroup = group_type in ["g", "a", "i"]
            type_label_full = "Channel" if group_type == "c" else "Supergroup"
            
            try:
                # ===== BAGIAN PEMBUATAN GRUP =====
                if current_step == "create":
                    # Extra pause check before creation
                    _sync_pause_from_registry(task_key, tid)
                    while CREATEGROUP_TASKS.get(task_key, {}).get("paused"):
                        _sync_resume_from_registry(task_key, tid)
                        if not CREATEGROUP_TASKS.get(task_key, {}).get("paused"): break
                        await asyncio.sleep(1)
                    if not CREATEGROUP_TASKS.get(task_key, {}).get("running"): break

                    if group_type == "b":
                        # Basic group
                        try:
                            # Try with assistant if invite_bots is True
                            users_to_add = [assistant.id] if invite_bots else []
                            try:
                                chat = await user_client.create_group(
                                    title=current_group_name,
                                    users=users_to_add
                                )
                            except Exception as eg:
                                # If failed with users (maybe privacy), try without users
                                if users_to_add:
                                    logger.warning(f"Gagal buat grup dasar dengan bot: {eg}")
                                    chat = await user_client.create_group(title=current_group_name)
                                    await update_group_log(f"⚠️ Grup dasar dibuat tanpa bot (kendala privasi/limit)")
                                else:
                                    raise eg
                            
                            created_chat_id = chat.id
                            invite_link = await user_client.export_chat_invite_link(created_chat_id)
                            
                            # Welcome message for basic group
                            try:
                                await bot_client.send_message(
                                    created_chat_id, 
                                    f"🚀 <b>Group Initialized!</b>\n"                                    
                                    f"━━━━━━━━━━━━━━━━━━━━\n"
                                    f"🆔 <b>Chat ID:</b><code>{created_chat_id}</code>\n"
                                    f"📊 <b>Status:</b> Active\n\n"
                                    f"<i>Powered by Altroid-X Engine</i>",
                                    parse_mode=ParseMode.HTML
                                )
                            except Exception as ew:
                                logger.warning(f"Gagal kirim welcome msg (basic): {ew}")

                            state["current_chat_id"] = created_chat_id
                            state["invite_link"] = invite_link
                            state["current_step"] = "setup"
                            current_step = "setup"
                            await save_creategroup_cache()
                            
                            await update_group_log(f"✅ Grup dasar dibuat: <code>{created_chat_id}</code>")
                        except Exception as e:
                            err_str = str(e)
                            logger.error(f"Gagal membuat grup dasar: {e}\n{traceback.format_exc()}")
                            
                            error_msg = f"❌ <b>Gagal membuat Grup Dasar</b>\n• Account: {html.escape(account_name_raw)}\n• Error: <code>{html.escape(err_str)}</code>"
                            
                            # 1. Update the consolidated log (edit)
                            await update_group_log(f"❌ Gagal: {html.escape(err_str)}")
                            
                            # 2. Send a FRESH notification to the Log Group (push)
                            await send_log_notification(bot_client, error_msg, effective_user_id, reply_to_msg_id=reply_id)
                            
                            i += 1
                            continue
                        
                        if temp_pin:
                                try:
                                    if hasattr(user_client, "pin_chat"):
                                        await user_client.pin_chat(created_chat_id)
                                    else:
                                        await user_client.invoke(
                                            raw.functions.messages.ToggleDialogPin(
                                                peer=await user_client.resolve_peer(created_chat_id),
                                                pinned=True
                                            )
                                        )
                                    pinned_chat_id = created_chat_id
                                    await update_group_log(f"📌 {type_name} dipin sementara")
                                except Exception as epin:
                                    logger.warning(f"Gagal pin chat {created_chat_id}: {epin}")
                                    await update_group_log(f"❌ Gagal pin {type_name}: {str(epin)}")
                
                    elif group_type in ["g", "c", "a", "i"]:
                        # Supergroup atau channel
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
                            
                            # Set Anonymous Admin DULU sebelum invite bot (agar identitas owner tersembunyi)
                            should_anon = anon_mode or group_type in ["a", "i"]
                            if is_supergroup and should_anon:
                                try:
                                    privileges = ChatPrivileges(can_manage_chat=True, can_delete_messages=True, can_manage_video_chats=True, can_restrict_members=True, can_promote_members=True, can_change_info=True, can_post_messages=True, can_edit_messages=True, can_invite_users=True, can_pin_messages=True, can_manage_topics=True, can_post_stories=True, can_edit_stories=True, can_delete_stories=True, is_anonymous=True)
                                    await user_client.promote_chat_member(created_chat_id, user_info.id, privileges=privileges)
                                    await handle_action_delay()
                                    await update_group_log(f"✅ Anonymous admin di-set untuk <code>{created_chat_id}</code>")
                                except Exception as e:
                                    await update_group_log(f"❌ Gagal set anonymous admin: {str(e)}")

                            # Invite and Promote Assistant Bot for supergroups/channels
                            if invite_bots:
                                try:
                                    await user_client.add_chat_members(created_chat_id, assistant.id)
                                    await user_client.promote_chat_member(
                                        created_chat_id, 
                                        assistant.id,
                                        privileges=ChatPrivileges(
                                            can_manage_chat=False,
                                            can_post_messages=True,
                                            can_delete_messages=False,
                                            can_invite_users=False,
                                            can_pin_messages=True,
                                            can_change_info=False
                                        )
                                    )
                                    await update_group_log(f"🤖 Asisten bot diundang & di-admin")
                                    # Welcome message from bot (tanpa info akun)
                                    await bot_client.send_message(
                                        created_chat_id, 
                                        f"🚀 <b>{type_label_full} Initialized!</b>\n"                                 
                                        f"━━━━━━━━━━━━━━━━━━━━\n"
                                        f"🆔 <b>Chat ID:</b><code>{created_chat_id}</code>\n"
                                        f"📊 <b>Status:</b> Active\n\n"
                                        f"<i>Powered by Altroid-X Engine</i>",
                                        parse_mode=ParseMode.HTML
                                    )
                                except Exception as ebot:
                                    err_msg = str(ebot)
                                    if "USER_PRIVACY_RESTRICTED" in err_msg:
                                        msg = "❌ Gagal undang asisten: Privasi Bot Terbatas"
                                    elif "USER_BOT" in err_msg:
                                        msg = "❌ Gagal undang asisten: Bot tidak dapat diundang"
                                    else:
                                        msg = f"❌ Gagal undang asisten: {err_msg}"
                                    
                                    logger.warning(f"Gagal undang asisten bot ke {created_chat_id}: {ebot}")
                                    await update_group_log(msg)

                            state["current_chat_id"] = created_chat_id
                            state["current_step"] = "setup"
                            current_step = "setup"
                            await save_creategroup_cache()
                            
                            await update_group_log(f"✅ {type_label_full} dibuat: <code>{created_chat_id}</code>")
                            await update_group_log(f"✅ Description di-set: <i>{html.escape(description[:30])}...</i>")
                        except Exception as e:
                            err_str = str(e)
                            logger.error(f"Gagal membuat {type_label_full}: {e}\n{traceback.format_exc()}")
                            
                            error_msg = f"❌ <b>Gagal membuat {type_label_full}</b>\n• Account: {html.escape(account_name_raw)}\n• Error: <code>{html.escape(err_str)}</code>"
                            
                            # 1. Update the consolidated log (edit)
                            await update_group_log(f"❌ Gagal: {html.escape(err_str)}")
                            
                            # 2. Send a FRESH notification to the Log Group (push)
                            await send_log_notification(bot_client, error_msg, effective_user_id, reply_to_msg_id=reply_id)
                            
                            # 3. Special handling for "Too many channels" - this is a terminal error for this session
                            if "CHANNELS_TOO_MUCH" in err_str:
                                await update_group_log("🛑 <b>Task dihentikan:</b> Limit akun tercapai (Channels Too Much).")
                                await send_log_notification(
                                    bot_client, 
                                    f"🛑 <b>Task Create {type_label_full} Dihentikan</b>\n• Account: {html.escape(account_name_raw)}\n• Reason: <code>CHANNELS_TOO_MUCH</code> (Limit tercapai)",
                                    effective_user_id,
                                    reply_to_msg_id=reply_id
                                )
                                break # Exit the loop for this session
                                
                            i += 1
                            continue

                # Extra pause check before setup
                _sync_pause_from_registry(task_key, tid)
                while CREATEGROUP_TASKS.get(task_key, {}).get("paused"):
                    _sync_resume_from_registry(task_key, tid)
                    if not CREATEGROUP_TASKS.get(task_key, {}).get("paused"): break
                    await asyncio.sleep(1)
                if not CREATEGROUP_TASKS.get(task_key, {}).get("running"): break

                if current_step == "setup":
                    if temp_pin:
                        try:
                            if hasattr(user_client, "pin_chat"):
                                await user_client.pin_chat(created_chat_id)
                            else:
                                await user_client.invoke(
                                    raw.functions.messages.ToggleDialogPin(
                                        peer=await user_client.resolve_peer(created_chat_id),
                                        pinned=True
                                    )
                                )
                            pinned_chat_id = created_chat_id
                            await update_group_log(f"📌 {type_name} dipin sementara")
                        except Exception as epin:
                            logger.warning(f"Gagal pin chat {created_chat_id}: {epin}")
                            await update_group_log(f"❌ Gagal pin {type_name}: {str(epin)}")
                    
                    if current_username:
                        try:
                            await user_client.set_chat_username(created_chat_id, current_username)
                            invite_link = f"https://t.me/{current_username}"
                            await update_group_log(f"✅ Username di-set: @{current_username}", current_group_name, invite_link)
                        except Exception as e:
                            await update_group_log(f"❌ Gagal set username @{current_username}: {str(e)}")
                            invite_link = await user_client.export_chat_invite_link(created_chat_id)
                            await update_group_log(None, current_group_name, invite_link)
                    else:
                        invite_link = await user_client.export_chat_invite_link(created_chat_id)
                        await update_group_log(None, current_group_name, invite_link)
                    
                    state["invite_link"] = invite_link
                    
                    
                    if is_supergroup:
                        if photo_path and os.path.exists(photo_path):
                            try:
                                await user_client.set_chat_photo(chat_id=created_chat_id, photo=photo_path)
                                await handle_action_delay()
                                await update_group_log(f"✅ Foto profil di-set untuk <code>{created_chat_id}</code>")
                            except Exception as e:
                                await update_group_log(f"❌ Gagal set foto profil: {str(e)}")
                    
                    try:
                        from datetime import timezone, timedelta
                        tz = timezone(timedelta(hours=7))
                        indonesia_time = datetime.now(tz).strftime('%Y-%m-%d | %H:%M:%S %Z')
                        time_msg = await user_client.send_message(created_chat_id, f"**📅 {indonesia_time}**", parse_mode=ParseMode.MARKDOWN)
                        first_msg_id = time_msg.id
                        state["first_msg_id"] = first_msg_id
                        if pin_first_msg:
                            try:
                                await user_client.pin_chat_message(created_chat_id, first_msg_id)
                                await update_group_log(f"📌 First msg berhasil di-pin <code>{created_chat_id}</code>")
                            except Exception as epin:
                                await update_group_log(f"❌ Gagal pin first msg: {str(epin)}")
                        await handle_action_delay()
                    except Exception as e:
                        await update_group_log(f"❌ Gagal kirim pesan waktu: {str(e)}")
                    
                    state["current_step"] = "copy_msg"
                    current_step = "copy_msg"
                    state["step_index"] = 0
                    await save_creategroup_cache()

                if current_step == "copy_msg":
                    should_copy = copy_messages or group_type in ["a", "i"]
                    if should_copy:
                        for idx in range(s_idx, len(LIST_MSG_IDS)):
                            msg_id = LIST_MSG_IDS[idx]
                            try:
                                await user_client.copy_message(chat_id=created_chat_id, from_chat_id=SRC_CHANNEL, message_id=msg_id)
                                s_idx = idx + 1
                                state["step_index"] = s_idx
                                if s_idx % 5 == 0: await save_creategroup_cache()
                                await handle_action_delay()
                            except FloodWait as fw:
                                await asyncio.sleep(fw.value + 10)
                                continue
                            except Exception as e:
                                logger.warning(f"Gagal copy message {msg_id}: {e}")
                    
                    state["current_step"] = "quotes_1"
                    current_step = "quotes_1"
                    state["step_index"] = 0
                    s_idx = 0
                    await save_creategroup_cache()

                if current_step == "quotes_1":
                    for idx in range(s_idx, len(LOVE_QUOTES)):
                        quote = LOVE_QUOTES[idx]
                        try:
                            msg_text = f"<i>💙 {quote}</i>"
                            if quote_block:
                                msg_text = f"<blockquote expandable>{msg_text}</blockquote>"
                            await user_client.send_message(created_chat_id, msg_text, parse_mode=ParseMode.HTML)
                            s_idx = idx + 1
                            state["step_index"] = s_idx
                            if s_idx % 5 == 0: await save_creategroup_cache()
                            await handle_action_delay()
                        except FloodWait as fw:
                            await asyncio.sleep(fw.value + 10)
                            continue
                    await update_group_log(f"✅ Quote 1 berhasil dikirim total: <code>{len(LOVE_QUOTES)}</code> msg")
                    state["current_step"] = "quotes_2"
                    current_step = "quotes_2"
                    state["step_index"] = 0
                    s_idx = 0
                    await save_creategroup_cache()

                if current_step == "quotes_2":
                    for idx in range(s_idx, len(LOVE_QUOTES_2)):
                        quote = LOVE_QUOTES_2[idx]
                        try:
                            msg_text = f"<i>💖 {quote}</i>"
                            if quote_block:
                                msg_text = f"<blockquote expandable>{msg_text}</blockquote>"
                            await user_client.send_message(created_chat_id, msg_text, parse_mode=ParseMode.HTML)
                            s_idx = idx + 1
                            state["step_index"] = s_idx
                            if s_idx % 5 == 0: await save_creategroup_cache()
                            await handle_action_delay()
                        except FloodWait as fw:
                            await asyncio.sleep(fw.value + 10)
                            continue
                    await update_group_log(f"✅ Quote 2 berhasil dikirim total: <code>{len(LOVE_QUOTES_2)}</code> msg")
                    state["current_step"] = "invite_bots"
                    current_step = "invite_bots"
                    state["step_index"] = 0
                    s_idx = 0
                    await save_creategroup_cache()

                if current_step == "invite_bots":
                    if should_invite_bots and bot_entities:
                        success_bots = []
                        for idx in range(s_idx, len(bot_entities)):
                            bot = bot_entities[idx]
                            try:
                                await user_client.add_chat_members(created_chat_id, bot.id)
                                success_bots.append(bot.username or str(bot.id))
                                for cmd in ["/help", "/id"]:
                                    try:
                                        await user_client.send_message(created_chat_id, cmd)
                                        await handle_action_delay()
                                    except: pass
                            except: pass
                            s_idx = idx + 1
                            state["step_index"] = s_idx
                            if s_idx % 2 == 0: await save_creategroup_cache()
                        await update_group_log(f"✅ Berhasil invite {len(success_bots)} bot ke <code>{created_chat_id}</code>")
                    
                    state["current_step"] = "msg_img"
                    current_step = "msg_img"
                    state["step_index"] = 0
                    s_idx = 0
                    await save_creategroup_cache()

                if current_step == "msg_img":
                    if msg_img:
                        if isinstance(msg_img, bool):
                            # Jika msg_img adalah boolean True, gunakan daftar global MSG_IMG_IDS
                            for idx in range(s_idx, len(MSG_IMG_IDS)):
                                msg_id = MSG_IMG_IDS[idx]
                                try:
                                    await user_client.copy_message(created_chat_id, from_chat_id=SRC_CHANNEL, message_id=msg_id)
                                    s_idx = idx + 1
                                    state["step_index"] = s_idx
                                    if s_idx % 5 == 0: await save_creategroup_cache()
                                    await handle_action_delay()
                                except: pass

                        elif isinstance(msg_img, list):
                            # Jika msg_img adalah list, gunakan list tersebut
                            for idx in range(s_idx, len(msg_img)):
                                img_url = msg_img[idx]
                                try:
                                    await user_client.send_photo(created_chat_id, img_url)
                                    s_idx = idx + 1
                                    state["step_index"] = s_idx
                                    if s_idx % 5 == 0: await save_creategroup_cache()
                                    await handle_action_delay()
                                except: pass
                            await update_group_log(f"✅ Image Messages berhasil dikirim total: <code>{len(msg_img)}</code> msg")
                    state["current_step"] = "quotes_3"
                    current_step = "quotes_3"
                    state["step_index"] = 0
                    s_idx = 0
                    await save_creategroup_cache()

                if current_step == "quotes_3":
                    for idx in range(s_idx, len(LOVE_QUOTES_3)):
                        quote = LOVE_QUOTES_3[idx]
                        try:
                            msg_text = f"<i>🌹 {quote}</i>"
                            if quote_block:
                                msg_text = f"<blockquote expandable>{msg_text}</blockquote>"
                            await user_client.send_message(created_chat_id, msg_text, parse_mode=ParseMode.HTML)
                            s_idx = idx + 1
                            state["step_index"] = s_idx
                            await handle_action_delay()
                        except: pass
                    await update_group_log(f"✅ Quote 3 berhasil dikirim total: <code>{len(LOVE_QUOTES_3)}</code> msg")
                    state["current_step"] = "finalize"
                    current_step = "finalize"
                    state["step_index"] = 0
                    s_idx = 0
                    await save_creategroup_cache()

                if current_step == "finalize":
                    # 1. Count messages
                    total_push_msg = 0
                    try:
                        messages = []
                        async for msg in user_client.get_chat_history(created_chat_id, limit=150):
                            messages.append(msg)
                        total_push_msg = len(messages)
                        await update_group_log(f"✅ Push message berhasil total: <code>{total_push_msg}</code> msg")
                    except Exception as e:
                        logger.warning(f"Gagal hitung pesan: {e}")
                        await update_group_log(f"❌ Gagal hitung push message: {str(e)}")
                    
                    # 2. Bot sends summary message (independent — bot mungkin tidak ada di grup)
                    try:
                        await bot_client.send_message(created_chat_id, f"<i>Total pesan dalam grup ini: {total_push_msg}+</i>", parse_mode=ParseMode.HTML)
                    except Exception as e:
                        logger.warning(f"Bot gagal kirim summary ke {created_chat_id}: {e}")
                        await update_group_log(f"❌ Bot gagal kirim summary: {str(e)}")
                    
                    # 3. Link ke pesan pertama
                    if first_msg_id:
                        try:
                            link_msg = f"<i>➟ ke pesan pertama:</i> <b><a href='t.me/c/{str(created_chat_id).replace('-100', '').lstrip('-')}/{first_msg_id}'>» di sini</a></b>"
                            await user_client.send_message(created_chat_id, link_msg, parse_mode=ParseMode.HTML)
                        except Exception as e:
                            logger.warning(f"Gagal kirim link first msg: {e}")
                    
                    # 4. Bot sends completion message (independent)
                    try:
                        group_duration = (datetime.now() - group_start_time).total_seconds()
                        await bot_client.send_message(created_chat_id, f"<i>✅ grup <code>{created_chat_id}</code> selesai dikustomisasi dalam {format_duration(group_duration)}!</i>", parse_mode=ParseMode.HTML)
                    except Exception as e:
                        logger.warning(f"Bot gagal kirim completion msg ke {created_chat_id}: {e}")

                    # 5. Unpin chat (SELALU dijalankan, tidak bergantung pada bot)
                    if temp_pin and created_chat_id:
                        try:
                            if hasattr(user_client, "unpin_chat"):
                                await user_client.unpin_chat(created_chat_id)
                            else:
                                await user_client.invoke(
                                    raw.functions.messages.ToggleDialogPin(
                                        peer=await user_client.resolve_peer(created_chat_id),
                                        pinned=False
                                    )
                                )
                            await update_group_log(f"📍 {type_name} unpin otomatis")
                        except Exception as e:
                            logger.warning(f"Gagal unpin chat {created_chat_id}: {e}")
                            await update_group_log(f"❌ Gagal unpin {type_name}: {str(e)}")

                # Group completed, move to next
                created_groups.append({'name': current_group_name, 'link': invite_link, 'id': created_chat_id, 'time': datetime.now().strftime('%H:%M:%S'), 'type': group_type})
                state["current_index"] = i
                state["current_step"] = None
                current_step = None
                state["step_index"] = 0
                state["current_chat_id"] = None
                await save_creategroup_cache()
                i += 1
                
            except FloodWait as fw:
                account_name = f"{user_info.first_name or ''} {user_info.last_name or ''}".strip()
                wait_msg = (
                    f"<blockquote expandable>"
                    f"⏳ FloodWait {fw.value}s untuk {unit_label} {current_group_name}\n"
                    f"• Account: {html.escape(account_name)}"
                    f"</blockquote>"
                )
                await send_log_notification(bot_client, wait_msg, effective_user_id, reply_id)
                await asyncio.sleep(fw.value + 10)
                continue
            except Exception as e:
                logger.error(f"Error dalam loop pembuatan {unit_label}: {e}\n{traceback.format_exc()}")
                error_msg = (
                    f"❌ <b>Error dalam loop {unit_label} #{i}:</b>\n"
                    f"<code>{html.escape(str(e))}</code>\n\n"
                    f"📑 <b>Traceback:</b>\n"
                    f"<pre>{html.escape(traceback.format_exc())}</pre>"
                )
                await send_log_notification(
                    bot_client,
                    error_msg,
                    effective_user_id,
                    reply_id
                )
                i += 1
                continue
        
        # ===== TASK COMPLETED =====
        if CREATEGROUP_TASKS.get(task_key, {}).get("running", False):
            end_time = datetime.now()
            total_duration = (end_time - CREATEGROUP_TASKS[task_key]["start_time"]).total_seconds()
            
            # Simpan konfigurasi task yang selesai
            COMPLETED_CREATEGROUP_TASKS[task_key] = {
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
                "temp_pin": temp_pin,
                "quote_block": quote_block,
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
                "start_time": CREATEGROUP_TASKS[task_key]["start_time"].strftime('%Y-%m-%d %H:%M:%S')
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
                ba_delay,
                task_id=tid # Pass tid here
            )
        else:
            # Task dihentikan
            await send_log_notification(
                bot_client,
                f"<blockquote expandable>"
                f"🛑 Task Create {type_label} dihentikan\n"
                f"• {type_name} dibuat: {len(created_groups)}/{count}\n"
                f"• User: {user_info.first_name if user_info else 'Unknown'}"
                f"</blockquote>",
                effective_user_id,
                reply_id
            )
    
    except Exception as e:
        logger.error(f"Critical error in creategroup_loop: {e}", exc_info=True)
        
        # Simpan partial state agar bisa diakses
        COMPLETED_CREATEGROUP_TASKS[task_key] = {
            "delay": delay,
            "count": count,
            "created_groups": created_groups,
            "total_duration": (datetime.now() - CREATEGROUP_TASKS[task_key]["start_time"]).total_seconds(),
            "user_id": user_info.id if user_info else None,
            "status": "failed",
            "error": str(e)
        }
        
        # Update control message
        if control_message:
            try:
                 await control_message.edit_text(
                      f"❌ <b>Task CreateGroup Gagal</b>\n\n"
                      f"• Error: {html.escape(str(e))}\n"
                      f"• Berhasil: {len(created_groups)}/{count}\n"
                      f"• User: {user_info.first_name if user_info else 'Unknown'}",
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
            effective_user_id,
            reply_id
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
        if 'task_key' in locals():
            CREATEGROUP_TASKS.pop(task_key, None)
        else:
            CREATEGROUP_TASKS.pop(task_id, None)
        
        # Simpan cache setelah cleanup (mencegah ghost tasks)
        await save_creategroup_cache()

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
    ba_delay: int = 3,
    task_id: str = None
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
        # Use TID in filename to avoid collision in multi-session
        from Main.plugins.userbot.xtaskmanager import generate_task_id
        tid_suffix = f"_{task_id.replace('#', '')}" if task_id else ""
        log_filename = f"create{unit_label}_log_{timestamp}{tid_suffix}.txt"
        
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
                     parse_mode=ParseMode.HTML,
                     reply_to_message_id=reply_id
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
        if control_message:
            try:
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
                     buttons_list = []
                     for idx, grp in enumerate(created_groups[:90], 1): # Limit to 90 for safety
                          buttons_list.append(InlineKeyboardButton(f"{type_label} {idx}", url=grp['link']))
                     
                     # Arrange buttons, 3 per row
                     from Main.utils.helpers import arrange_buttons
                     group_buttons = arrange_buttons(buttons_list, 3)
                     
                     # Merging:
                     final_buttons.inline_keyboard = group_buttons + final_buttons.inline_keyboard

                account_name = f"{user_info.first_name or ''} {user_info.last_name or ''}".strip() if user_info else "Unknown"
                await control_message.edit_text(
                    f"<blockquote expandable>"
                    f"✅ <b>Laporan Create {type_label} Selesai</b>\n\n"
                    f"• <b>User:</b> {html.escape(account_name)}\n"
                    f"• <b>Detail:</b> Berhasil {success_count}/{requested_count} {unit_label}\n"
                    f"• <b>Durasi:</b> {format_duration(total_duration)}\n"
                    f"• <b>Log:</b> {log_info}"
                    f"</blockquote>",
                    reply_markup=final_buttons,
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Gagal update control message final: {e}\n{traceback.format_exc()}")
        
    except Exception as e:
        error_tb = traceback.format_exc()
        logger.error(f"Error sending completion report: {e}\n{error_tb}")
        await send_log_notification(
            bot_client,
            f"❌ <b>Error dalam completion report:</b> {str(e)}\n\n<blockquote expandable><code>{html.escape(error_tb)}</code></blockquote>",
            user_info.id if user_info else user_client.me.id,
            reply_id
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
                "quote_block": config.get("quote_block", True),
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
                    parse_mode=ParseMode.HTML,
                    reply_to_message_id=message.id if str(message.chat.id) == str(LOG_CHAT_ID) else None
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
            index = i + 1 # Use 1-based index for UI consistency
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
        if callback_query.message:
            await callback_query.message.delete()
        else:
            try:
                await callback_query.edit_message_text("🗑 <b>Dashboard Ditutup</b>", parse_mode=ParseMode.HTML)
            except Exception:
                pass
        
        # Generate tid early for buttons
        from Main.plugins.userbot.xtaskmanager import generate_task_id
        tid = generate_task_id("CG")
        
        # Buat control message dengan tombol lengkap (Main Menu)
        control_buttons = await get_creategroup_keyboard(client.me.id, tid, menu_type="main")
        
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
                quote_block=config.get("quote_block", True),
                rand_len=config.get("rand_len", 0),
                rand_lower=config.get("rand_lower", False),
                rand_upper=config.get("rand_upper", False),
                rand_static=config.get("rand_static", False),
                temp_pin=config.get("temp_pin", True),
                user_id=callback_query.from_user.id,
                task_id=tid
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
    """Command to check creategroup status for current session"""
    me_id = client.me.id
    # Search for running task owned by this session
    from Main.plugins.userbot.xcreategroup import CREATEGROUP_TASKS
    task_key = next((k for k, v in CREATEGROUP_TASKS.items() if v.get("user_id") == me_id and v.get("running")), None)
    
    if not task_key:
        # Fallback: check if the admin started it but assigned it to this session
        task_key = next((k for k, v in CREATEGROUP_TASKS.items() if v.get("params", {}).get("user_id") == me_id and v.get("running")), None)
        
    if not task_key:
        await message.reply("💤 Tidak ada task CreateGroup yang aktif untuk akun ini.")
        return
        
    task = CREATEGROUP_TASKS[task_key]
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
    
    # Resolve user_style
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(client.me.id)
    
    buttons = [
        [
             InlineKeyboardButton(await Essentials.get_user_button_style(client.me.id, "⏸️ Pause"), callback_data="pause_creategroup", style=user_style),
             InlineKeyboardButton(await Essentials.get_user_button_style(client.me.id, "▶️ Resume"), callback_data="resume_creategroup", style=user_style)
        ],
        [
             InlineKeyboardButton(await Essentials.get_user_button_style(client.me.id, "⏹️ Stop (Graceful)"), callback_data="stop_creategroup", style=user_style),
             InlineKeyboardButton(await Essentials.get_user_button_style(client.me.id, "🛑 Force Stop"), callback_data="force_stop_creategroup", style=user_style)
        ],
        [InlineKeyboardButton(await Essentials.get_user_button_style(client.me.id, "🔄 Refresh Status"), callback_data="status_creategroup", style=user_style)]
    ]
    
    await Altruix.bot.send_message(
        chat_id=message.chat.id,
        text=status_text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML,
        reply_to_message_id=message.id
    )

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
    # Cari task aktif milik user ini
    task_id = next((k for k, v in CREATEGROUP_TASKS.items() if v.get("user_id") == user_id and v.get("running")), None)
    
    cmd_args = getattr(message, "command", None)
    if not cmd_args and message.text:
        cmd_args = message.text.split()
        
    force = cmd_args and len(cmd_args) > 1 and cmd_args[1].lower() == "force"
    
    if not task_id or task_id not in CREATEGROUP_TASKS:
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


@Altruix.bot.on_callback_query(filters.regex(r"^(stop|pause|resume|status|list|recurring|edit_last|download_log|list_groups|delete_task|cancel|force_stop|confirm_recur|recover|manage|back)_creategroup"))
@log_errors
@iuser_check
async def creategroup_control_handler(client: Client, callback_query: CallbackQuery):
    """Handler untuk tombol kontrol creategroup"""
    
    data_parts = callback_query.data.split(":")
    action = data_parts[0].replace("_creategroup", "")
    user_id = callback_query.from_user.id
    
    # Mencari task yang relevan (baik dari tid eksplisit atau owner)
    task_key = None
    if len(data_parts) > 1 and data_parts[1] in CREATEGROUP_TASKS:
        task_key = data_parts[1]
    else:
        # Fallback: cari task aktif milik session ini (client.me.id)
        me_id = client.me.id
        task_key = next((k for k, v in CREATEGROUP_TASKS.items() if v.get("user_id") == me_id and v.get("running")), None)
        if not task_key:
            # Or if user_id is the admin (callback_query.from_user.id)
            task_key = next((k for k, v in CREATEGROUP_TASKS.items() if v.get("user_id") == user_id and v.get("running")), None)

    try:
        # Handle Menu Navigation
        if action == "manage":
            if not task_key:
                await callback_query.answer("❌ Task tidak ditemukan.", show_alert=True)
                return
            keyboard = await get_creategroup_keyboard(client.me.id, task_key, menu_type="manage")
            await callback_query.edit_message_reply_markup(reply_markup=keyboard)
            return

        if action == "back":
            if not task_key:
                await callback_query.answer("❌ Task tidak ditemukan.", show_alert=True)
                return
            keyboard = await get_creategroup_keyboard(client.me.id, task_key, menu_type="main")
            await callback_query.edit_message_reply_markup(reply_markup=keyboard)
            return
        # Handle Force Stop first (doesn't need check)
        if action == "force_stop":
            if task_key in CREATEGROUP_TASKS:
                CREATEGROUP_TASKS[task_key]["running"] = False
                CREATEGROUP_TASKS.pop(task_key, None)
            
            # Also clear pending confirmations
            PENDING_CONFIRMATIONS.clear()
            
            await save_creategroup_cache()
            try:
                await callback_query.edit_message_text("🛑 <b>Task CreateGroup Dihentikan Paksa (Force Stop)</b>\nMemory dibersihkan.", parse_mode=ParseMode.HTML)
            except Exception:
                await callback_query.answer("🛑 Task Dihentikan Paksa", show_alert=True)
            return

        if action == "recover":
            if len(data_parts) < 2:
                await callback_query.answer("Data tidak valid", show_alert=True)
                return
                
            tid = data_parts[1]
            if tid not in CREATEGROUP_TASKS:
                await callback_query.answer("❌ Task tidak ditemukan di memori.", show_alert=True)
                return
            
            task_data = CREATEGROUP_TASKS[tid]
            params = task_data.get("params", {})
            
            # Find client
            client_id = task_data.get("user_id")
            user_client = next((c for c in Altruix.clients if c.me.id == client_id), None)
            
            if not user_client:
                 if Altruix.clients:
                      user_client = Altruix.clients[0]
                 else:
                      await callback_query.answer("❌ Tidak ada userbot aktif!", show_alert=True)
                      return

            
            await callback_query.answer("Mengambil alih task...")
            msg_text = f"🔄 <b>Resuming Interrupted Task:</b> <code>{tid}</code>"
            try:
                await callback_query.edit_message_text(msg_text, parse_mode=ParseMode.HTML)
            except Exception:
                pass

            # Start loop
            asyncio.create_task(
                creategroup_loop(
                    user_client=user_client,
                    bot_client=Altruix.bot,
                    initial_message=None,
                    delay=params.get("delay"),
                    count=params.get("count"),
                    extra_delay_minutes=params.get("extra_delay_minutes"),
                    batch_size=params.get("batch_size"),
                    group_type=params.get("group_type"),
                    name_pattern=params.get("name_pattern"),
                    username_prefix=params.get("username_prefix"),
                    bot_identifiers=params.get("bot_identifiers"),
                    control_message=None, # Will be recovered by loop
                    action_delay=params.get("action_delay", 3.0),
                    invite_bots=params.get("invite_bots", True),
                    anon_mode=params.get("anon_mode", True),
                    copy_messages=params.get("copy_messages", True),
                    description=params.get("description", "Powered by @AlphaXproject"),
                    photo_source=params.get("photo_source", "source"),
                    custom_photo_id=params.get("custom_photo_id"),
                    log_destination=params.get("log_destination", "both"),
                    log_format=params.get("log_format", "zip"),
                    pin_first_msg=params.get("pin_first_msg", True),
                    temp_pin=params.get("temp_pin", True),
                    quote_block=params.get("quote_block", True),
                    msg_img=params.get("msg_img", True),
                    rand_len=params.get("rand_len", 0),
                    rand_lower=params.get("rand_lower", False),
                    rand_upper=params.get("rand_upper", False),
                    rand_static=params.get("rand_static", False),
                    batch_action=params.get("batch_action", 30),
                    ba_delay=params.get("ba_delay", 30),
                    user_id=client_id,
                    task_id=tid,
                    is_resume=True,
                    account_idx=params.get("account_idx", 1),
                    total_accs=params.get("total_accs", 1)
                )
            )
            return

        if action == "cancel":
            if len(data_parts) > 1:
                confirm_id = data_parts[1]
                PENDING_CONFIRMATIONS.pop(confirm_id, None)
            if callback_query.message:
                await callback_query.message.delete()
            else:
                try:
                    await callback_query.edit_message_text("🗑 <b>Dashboard Ditutup</b>", parse_mode=ParseMode.HTML)
                except Exception:
                    pass
            await callback_query.answer("Task dibatalkan")
            return
        
        elif action == "stop":
            if task_key in CREATEGROUP_TASKS:
                CREATEGROUP_TASKS[task_key]["running"] = False
                await send_log_notification(
                    client,
                    f"🛑 Task CreateGroup dihentikan oleh {callback_query.from_user.mention}",
                    CREATEGROUP_TASKS[task_key].get("user_id"),
                    CREATEGROUP_TASKS[task_key].get("control_message_id")
                )
                await callback_query.answer("Task dihentikan")
                try:
                    await callback_query.edit_message_text(
                        (callback_query.message.text if callback_query.message else "🚀 Task Control Panel") + "\n\n🛑 **DIHENTIKAN OLEH USER**",
                        parse_mode=ParseMode.HTML
                    )
                except Exception:
                    pass
            else:
                await callback_query.answer("Tidak ada task yang berjalan")
        
        elif action == "pause":
            if task_key in CREATEGROUP_TASKS and CREATEGROUP_TASKS[task_key].get("running", False):
                CREATEGROUP_TASKS[task_key]["paused"] = True
                CREATEGROUP_TASKS[task_key]["pause_event"].clear()
                # Sync to global _TASK_REGISTRY
                _tid = CREATEGROUP_TASKS[task_key].get("tid")
                if _tid:
                    _reg = getattr(Altruix, "_TASK_REGISTRY", {})
                    if _tid in _reg:
                        _reg[_tid]["paused"] = True
                await send_log_notification(
                    client,
                    f"⏸️ Task CreateGroup dipause oleh {callback_query.from_user.mention}",
                    CREATEGROUP_TASKS[task_key].get("user_id"),
                    CREATEGROUP_TASKS[task_key].get("control_message_id")
                )
                await callback_query.answer("Task dipause")
                try:
                    # Update text and keyboard cleanly
                    text = get_creategroup_dashboard_text(task_key)
                    keyboard = await get_creategroup_keyboard(client.me.id, task_key, menu_type="manage")
                    await callback_query.edit_message_text(
                        text,
                        reply_markup=keyboard,
                        parse_mode=ParseMode.HTML
                    )
                except Exception:
                    pass
            else:
                await callback_query.answer("Task tidak berjalan atau sudah dihentikan")
        
        elif action == "resume":
            if task_key in CREATEGROUP_TASKS and CREATEGROUP_TASKS[task_key].get("paused", False):
                CREATEGROUP_TASKS[task_key]["paused"] = False
                CREATEGROUP_TASKS[task_key]["pause_event"].set()
                # Sync to global _TASK_REGISTRY
                _tid = CREATEGROUP_TASKS[task_key].get("tid")
                if _tid:
                    _reg = getattr(Altruix, "_TASK_REGISTRY", {})
                    if _tid in _reg:
                        _reg[_tid]["paused"] = False
                await send_log_notification(
                    client,
                    f"▶️ Task CreateGroup di-resume oleh {callback_query.from_user.mention}",
                    CREATEGROUP_TASKS[task_key].get("user_id"),
                    CREATEGROUP_TASKS[task_key].get("control_message_id")
                )
                await callback_query.answer("Task di-resume")
                try:
                    # Update text and keyboard cleanly
                    text = get_creategroup_dashboard_text(task_key)
                    keyboard = await get_creategroup_keyboard(client.me.id, task_key, menu_type="manage")
                    await callback_query.edit_message_text(
                        text,
                        reply_markup=keyboard,
                        parse_mode=ParseMode.HTML
                    )
                except Exception:
                    pass
            else:
                await callback_query.answer("Task tidak dalam status pause")
        
        elif action == "status":
            if task_key in CREATEGROUP_TASKS:
                # If it's a dashboard message, refresh it. Else show popup.
                msg_text = callback_query.message.text if callback_query.message else ""
                if "Manage Task" in msg_text:
                    text = get_creategroup_dashboard_text(task_key)
                    keyboard = await get_creategroup_keyboard(client.me.id, task_key, menu_type="manage")
                    try:
                        await callback_query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
                    except Exception:
                        pass
                else:
                    # Show alert style status
                    text = get_creategroup_dashboard_text(task_key).replace("<blockquote expandable>", "").replace("</blockquote>", "")
                    await callback_query.answer(text, show_alert=True)
            elif task_key in COMPLETED_CREATEGROUP_TASKS:
                info = COMPLETED_CREATEGROUP_TASKS[task_key]
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
            if task_key in CREATEGROUP_TASKS:
                groups = CREATEGROUP_TASKS[task_key].get("created_groups", [])
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
            if task_key in COMPLETED_CREATEGROUP_TASKS:
                if task_key in CREATEGROUP_TASKS:
                    await callback_query.answer("⚠️ Task CreateGroup masih berjalan!", show_alert=True)
                    return
                
                conf = COMPLETED_CREATEGROUP_TASKS[task_key]
                
                # Show confirmation menu
                buttons = [
                    [
                        InlineKeyboardButton("✅ Ya, Ulangi", callback_data="confirm_recur_creategroup"),
                        InlineKeyboardButton("❌ Tidak", callback_data="status_creategroup")
                    ]
                ]
                
                try:
                    await callback_query.edit_message_text(
                        f"🔁 <b>Konfirmasi Recurring</b>\n\n"
                        f"Apakah Anda yakin ingin mengulang task ini?\n"
                        f"• Account: <b>{callback_query.from_user.mention}</b>\n"
                        f"• Total: <code>{conf['count']}</code> grup\n"
                        f"• Tipe: <code>{conf['group_type']}</code>\n"
                        f"• Delay/Act: <code>{conf.get('action_delay', 3.0)}</code>s\n"
                        f"• Delay/GC: <code>{conf['delay']}</code>s\n"
                        f"• Batch: <code>{conf['batch_size']}</code> | <code>{conf['extra_delay_minutes']}</code>m\n"
                        f"• Batch Act: <code>{conf.get('batch_action', 30)}</code> | <code>{conf.get('ba_delay', 30)}</code>s\n"
                        f"• Pattern: <code>{html.escape(conf['name_pattern'][:25])}...</code>\n"
                        f"• Bots: <code>{'Yes' if conf.get('invite_bots', True) else 'No'}</code>\n\n"
                        f"<i>Task akan menggunakan konfigurasi yang sama.</i>",
                        reply_markup=InlineKeyboardMarkup(buttons),
                        parse_mode=ParseMode.HTML
                    )
                except Exception:
                    pass
            else:
                await callback_query.answer("Tidak ada task selesai untuk diulang")
        
        elif action == "confirm_recur":
            if task_key in COMPLETED_CREATEGROUP_TASKS:
                if task_key in CREATEGROUP_TASKS:
                    await callback_query.answer("⚠️ Task CreateGroup masih berjalan!", show_alert=True)
                    return
                
                conf = COMPLETED_CREATEGROUP_TASKS[task_key]
                client_id = conf.get("client_id", conf.get("user_id"))
                user_client = next((c for c in Altruix.clients if c.me.id == client_id), None)
                if not user_client and Altruix.clients: user_client = Altruix.clients[0]
                if not user_client:
                    await callback_query.answer("❌ Tidak ada userbot aktif!", show_alert=True)
                    return

                await callback_query.answer("🔁 Mengulang task...")
                msg_text = "🔄 <b>Mengulang Task CreateGroup...</b>"
                try:
                    await callback_query.edit_message_text(msg_text, parse_mode=ParseMode.HTML)
                except Exception:
                    pass

                asyncio.create_task(
                    creategroup_loop(
                        user_client=user_client, bot_client=Altruix.bot, initial_message=callback_query.message,
                        delay=conf["delay"], count=conf["count"], extra_delay_minutes=conf["extra_delay_minutes"],
                        batch_size=conf["batch_size"], group_type=conf["group_type"], name_pattern=conf["name_pattern"],
                        username_prefix=conf["username_prefix"], bot_identifiers=conf["bot_identifiers"],
                        control_message=callback_query.message, action_delay=conf.get("action_delay", 3.0),
                        invite_bots=conf.get("invite_bots", True), anon_mode=conf.get("anon_mode", True),
                        copy_messages=conf.get("copy_messages", True), description=conf.get("description", "Powered by @AlphaXproject"),
                        photo_source=conf.get("photo_source", "source"), custom_photo_id=conf.get("custom_photo_id"),
                        log_destination=conf.get("log_destination", "both"), log_format=conf.get("log_format", "zip"),
                        pin_first_msg=conf.get("pin_first_msg", True), temp_pin=conf.get("temp_pin", True),
                        quote_block=conf.get("quote_block", True), msg_img=conf.get("msg_img", True),
                        rand_len=conf.get("rand_len", 0), rand_lower=conf.get("rand_lower", False),
                        rand_upper=conf.get("rand_upper", False), rand_static=conf.get("rand_static", False),
                        batch_action=conf.get("batch_action", 30), ba_delay=conf.get("ba_delay", 30), user_id=conf.get("user_id")
                    )
                )
            else:
                await callback_query.answer("Tidak ada task selesai untuk diulang.")
            
        elif action == "edit_last":
            if task_key in CREATEGROUP_TASKS:
                groups = CREATEGROUP_TASKS[task_key].get("created_groups", [])
                if groups:
                    last_group = groups[-1]
                    await callback_query.answer(f"Edit grup terakhir: {last_group['name']}")
                    # Implement edit last group
                else:
                    await callback_query.answer("Belum ada grup yang dibuat")
            else:
                await callback_query.answer("Tidak ada task yang berjalan")
        
        elif action == "download_log":
            if task_key in COMPLETED_CREATEGROUP_TASKS:
                await callback_query.answer("Log sudah dikirim ke channel")
            else:
                await callback_query.answer("Belum ada log yang tersedia")
        
        elif action == "list_groups":
            if task_key in COMPLETED_CREATEGROUP_TASKS:
                groups = COMPLETED_CREATEGROUP_TASKS[task_key].get("created_groups", [])
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
            target_tid = data_parts[1] if len(data_parts) > 1 else task_key
            if target_tid in COMPLETED_CREATEGROUP_TASKS:
                COMPLETED_CREATEGROUP_TASKS.pop(target_tid, None)
                await callback_query.answer("Task riwayat dihapus")
                try:
                    await callback_query.edit_message_text("🗑 <b>Riwayat Dihapus</b>", parse_mode=ParseMode.HTML)
                except Exception:
                    if callback_query.message: await callback_query.message.delete()
            elif target_tid in CREATEGROUP_TASKS:
                CREATEGROUP_TASKS.pop(target_tid, None)
                await callback_query.answer("Task aktif dihapus dari memori")
                try:
                    await callback_query.edit_message_text("🗑 <b>Task Dihapus</b>", parse_mode=ParseMode.HTML)
                except Exception:
                    if callback_query.message: await callback_query.message.delete()
            else:
                await callback_query.answer("Tidak ada task untuk dihapus")
                try:
                    await callback_query.edit_message_text("🗑 <b>Data Kosong</b>", parse_mode=ParseMode.HTML)
                except Exception:
                    if callback_query.message: await callback_query.message.delete()
    
    except Exception as e:
        logger.error(f"Error in creategroup_control_handler: {e}")
        await callback_query.answer(f"Error: {str(e)}")

@Altruix.register_on_cmd(
    ["cgtid", "cgpanel"],
    cmd_help={
        "help": "Tampilkan Task Control Panel untuk TID tertentu.",
        "usage": ".cgtid [TID]\n.cgpanel [TID]",
        "example": ".cgtid #CGbd5e\n.cgpanel #CGbd5e"
    },
    group_only=False
)
@log_errors
async def creategroup_panel_cmd(client: Client, message: Message):
    """Command to show the interactive control panel for a specific task"""
    if not message.user_input:
        return await message.reply_msg("❌ Masukkan Task ID (TID). Contoh: <code>.cgtid #CGbd5e</code>")
    
    tid = message.user_input.strip()
    if not tid.startswith("#"):
        tid = f"#{tid}"
    
    # Mencari task di memori
    if tid not in CREATEGROUP_TASKS:
        return await message.reply_msg(f"❌ Task <code>{tid}</code> tidak ditemukan atau sudah selesai.")
    
    task_data = CREATEGROUP_TASKS[tid]
    account_name = task_data.get("account_name", "Unknown")
    params = task_data.get("params", {})
    count = params.get("count", 0)
    group_type = params.get("group_type", "a")
    
    type_label = "Channel" if group_type == "c" else "Group"
    unit_label = "channel" if group_type == "c" else "grup"
    
    # Resolve bot username
    bot_username = Altruix.bot_manager.get_bot_username(client.me.id)
    
    try:
        # Get inline results from bot for the control panel
        results = await client.get_inline_bot_results(bot_username, f"creategroup_panel_{tid}")
        
        if results.results:
            await client.send_inline_bot_result(
                chat_id=message.chat.id,
                query_id=results.query_id,
                result_id=results.results[0].id,
                reply_to_message_id=message.id
            )
        else:
            await message.reply_msg(f"❌ Gagal mendapatkan panel kontrol dari bot asisten.")
            
    except Exception as e:
        logger.error(f"Error in creategroup_panel_cmd: {e}")
        await message.reply_msg(f"❌ Error: {str(e)}")

# Log sukses loading
# try:
#     Altruix.log(f"[DEBUG] Loaded → {__plugin_name__} {PLUGIN_VERSION}", level=20)
# except Exception as e:
#     logger.info(f"[DEBUG] Loaded → {__plugin_name__} {PLUGIN_VERSION}")
