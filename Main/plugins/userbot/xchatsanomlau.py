# xchatsanomlau.py
"""
Plugin Laucreate untuk Altruix Userbot
Ported from Ultroid Telethon plugin v0.0.3.14.3 [Mod by @AlphaXproject team]
Modified for Altruix Pyrogram/Kurigram ecosystem
"""

import os
import re
import asyncio
import html
import logging
import time
import tempfile
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any
import random

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


plugin_name = f"plugins/userbot/{os.path.basename(__file__)}"
__plugin_name__ = plugin_name if plugin_name else "xchatsanomlau"
PLUGIN_VERSION = "0.1.1.3.2"  # 🔥 Versi terbaru dengan smart_send dan error handling optimal
logger = logging.getLogger(f"{__plugin_name__}")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - [SET PLUGIN] - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# ==================== KONFIGURASI ====================
# Dapatkan LOG_CHAT_ID dari environment atau config Altruix
LOG_CHAT_ID = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_ID))

# 🔥 PERBAIKAN: Ambil handler dari config, bukan 'hndlr'
try:
    HANDLER = Altruix.config.HANDLERS
    if isinstance(HANDLER, list):
        HANDLER = HANDLER[0]
except AttributeError:
    HANDLER = "."


# State management untuk task laucreate
LAUCREATE_TASKS: Dict[str, Dict[str, Any]] = {}
COMPLETED_LAUCREATE_TASKS: Dict[str, Dict[str, Any]] = {}
CREATE_LOCK = asyncio.Lock()

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

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

async def download_profile_photo(client: Client) -> Optional[str]:
    """Download profile photo from source channel (message ID 4)"""
    try:
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
            # Konversi ke format yang sesuai jika perlu
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
        
        return None
    except Exception as e:
        logger.error(f"Error download foto profil: {e}")
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

def generate_group_name(pattern: str, index: int) -> str:
    """Generate group name with pattern and index"""
    now = datetime.now()
    year_last2 = str(now.year)[-2:]
    month_num = str(now.month).zfill(2)
    day_num = str(now.day).zfill(2)
    
    name = pattern\
        .replace('(tahun)', year_last2)\
        .replace('(bulan)', month_num)\
        .replace('(tanggal)', day_num)\
        .replace('(index)', str(index))
    
    return f"{name} {index}"

async def send_log_notification(bot_client: Client, text: str, reply_to_msg_id: Optional[int] = None):
    """Send notification to log channel"""
    try:
        await bot_client.send_message(
            LOG_CHAT_ID,
            text,
            reply_to_message_id=reply_to_msg_id,
            parse_mode=ParseMode.HTML
        )
        return True
    except Exception as e:
        logger.error(f"Gagal kirim notifikasi ke log: {e}")
        return False

# ==================== MAIN CREATION FUNCTIONS ====================
async def laucreate_loop(
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
    control_message: Message
):
    """Main loop untuk membuat grup"""
    task_id = 'laucreate_main'
    created_groups = []
    photo_path = None  # Cache untuk foto profil
    
    try:
        # Initialize task state
        LAUCREATE_TASKS[task_id] = {
            "running": True,
            "paused": False,
            "paused_by_user": False,
            "pause_event": asyncio.Event(),
            "current_index": 1,
            "created_groups": [],
            "start_time": datetime.now(),
            "control_message_id": control_message.id,
            "user_id": initial_message.from_user.id if initial_message.from_user else None
        }
        LAUCREATE_TASKS[task_id]["pause_event"].set()
        
        # Dapatkan info user
        user_info = await user_client.get_me()
        
        # Dapatkan entity bot asisten
        try:
            assistant = await bot_client.get_me()
            await send_log_notification(
                bot_client,
                f"🚀 <b>Task Laucreate Dimulai</b>\n"
                f"• User: {user_info.first_name or 'Unknown'}\n"
                f"• Jumlah: {count} grup\n"
                f"• Delay: {delay} detik\n"
                f"• Tipe: {group_type}\n"
                f"• Batch: {batch_size} grup, delay {extra_delay_minutes} menit",
                control_message.id
            )
        except Exception as e:
            await send_log_notification(
                bot_client,
                f"❌ Gagal mendapatkan info bot asisten: {str(e)}",
                control_message.id
            )
            return
        
        # Parse bot entities jika type 'i'
        bot_entities = []
        if group_type == 'i' and bot_identifiers:
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
                        control_message.id
                    )
        
        # Download foto profil sekali saja (cache)
        if group_type in ["a", "i"]:
            try:
                photo_path = await download_profile_photo(user_client)
                if photo_path:
                    await send_log_notification(
                        bot_client,
                        f"✅ Foto profil berhasil di-download ({os.path.getsize(photo_path)} bytes)",
                        control_message.id
                    )
                else:
                    await send_log_notification(
                        bot_client,
                        f"⚠️ Foto profil tidak tersedia atau gagal di-download",
                        control_message.id
                    )
            except Exception as e:
                await send_log_notification(
                    bot_client,
                    f"⚠️ Error download foto profil: {str(e)}",
                    control_message.id
                )
        
        i = 1
        while i <= count:
            # Check if task is running
            if not LAUCREATE_TASKS.get(task_id, {}).get("running", True):
                await send_log_notification(
                    bot_client,
                    f"🛑 Task laucreate dihentikan oleh user pada grup ke-{i}",
                    control_message.id
                )
                break
            
            # Check if paused by user
            if LAUCREATE_TASKS[task_id].get("paused", False):
                LAUCREATE_TASKS[task_id]["paused_by_user"] = True
                await send_log_notification(
                    bot_client,
                    f"⏸️ Task laucreate dipause pada grup ke-{i}",
                    control_message.id
                )
                await LAUCREATE_TASKS[task_id]["pause_event"].wait()
                LAUCREATE_TASKS[task_id]["paused_by_user"] = False
                await send_log_notification(
                    bot_client,
                    f"▶️ Task laucreate di-resume pada grup ke-{i}",
                    control_message.id
                )
            
            group_start_time = datetime.now()
            current_group_name = generate_group_name(name_pattern, i)
            current_username = f"{username_prefix}{i}" if username_prefix else None
            
            logger.info(f"Membuat grup {i}/{count}: {current_group_name}")
            
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
                        
                        await send_log_notification(
                            bot_client,
                            f"✅ Grup dasar dibuat: {current_group_name}\n"
                            f"ID: <code>-100{created_chat_id}</code>\n"
                            f"Link: {invite_link}",
                            control_message.id
                        )
                        
                    except Exception as e:
                        await send_log_notification(
                            bot_client,
                            f"❌ Gagal membuat grup dasar {current_group_name}: {str(e)}",
                            control_message.id
                        )
                        i += 1
                        continue
                
                elif group_type in ["g", "c", "a", "i"]:
                    # Supergroup atau channel
                    is_supergroup = group_type in ["g", "a", "i"]
                    
                    try:
                        if is_supergroup:
                            chat = await user_client.create_supergroup(
                                title=current_group_name,
                                description="Grup dibuat oleh plugin laucreate @AlphaXproject"
                            )
                        else:
                            chat = await user_client.create_channel(
                                title=current_group_name,
                                description="Channel dibuat oleh plugin laucreate @AlphaXproject"
                            )
                        
                        created_chat_id = chat.id
                        
                        # Set username jika ada
                        if current_username:
                            try:
                                await user_client.set_chat_username(
                                    created_chat_id,
                                    current_username
                                )
                                invite_link = f"https://t.me/{current_username}"
                                await send_log_notification(
                                    bot_client,
                                    f"✅ Username di-set: @{current_username}",
                                    control_message.id
                                )
                            except Exception as e:
                                await send_log_notification(
                                    bot_client,
                                    f"⚠️ Gagal set username {current_username}: {str(e)}",
                                    control_message.id
                                )
                                invite_link = await user_client.export_chat_invite_link(created_chat_id)
                        else:
                            invite_link = await user_client.export_chat_invite_link(created_chat_id)
                        
                        # ===== KONFIGURASI LANJUTAN UNTUK TIPE 'a' DAN 'i' =====
                        if group_type in ["a", "i"]:
                            # 1. Set anonymous admin
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
                                    is_anonymous=True
                                )
                                
                                await user_client.promote_chat_member(
                                    created_chat_id,
                                    user_info.id,
                                    privileges=privileges
                                )
                                await asyncio.sleep(2)
                                await send_log_notification(
                                    bot_client,
                                    f"✅ Anonymous admin di-set untuk -100{created_chat_id}",
                                    control_message.id
                                )
                            except Exception as e:
                                await send_log_notification(
                                    bot_client,
                                    f"⚠️ Gagal set anonymous admin: {str(e)}",
                                    control_message.id
                                )
                            
                            # 2. Set profile photo dari cache
                            if photo_path and os.path.exists(photo_path):
                                try:
                                    await user_client.set_chat_photo(
                                        chat_id=created_chat_id,
                                        photo=photo_path
                                    )
                                    await asyncio.sleep(2)
                                    await send_log_notification(
                                        bot_client,
                                        f"✅ Foto profil di-set untuk -100{created_chat_id}",
                                        control_message.id
                                    )
                                except PhotoInvalidDimensions:
                                    await send_log_notification(
                                        bot_client,
                                        f"⚠️ Foto profil invalid dimensions untuk -100{created_chat_id}",
                                        control_message.id
                                    )
                                except Exception as e:
                                    await send_log_notification(
                                        bot_client,
                                        f"⚠️ Gagal set foto profil: {str(e)}",
                                        control_message.id
                                    )
                            
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
                                await asyncio.sleep(3)
                            except Exception as e:
                                await send_log_notification(
                                    bot_client,
                                    f"⚠️ Gagal kirim pesan waktu: {str(e)}",
                                    control_message.id
                                )
                                first_msg_id = None
                            
                            # 4. Forward messages from source channel
                            for msg_id in LIST_MSG_IDS:
                                try:
                                    await user_client.forward_messages(
                                        chat_id=created_chat_id,
                                        from_chat_id=SRC_CHANNEL,
                                        message_ids=msg_id
                                    )
                                    await asyncio.sleep(4)
                                except FloodWait as fw:
                                    wait_time = fw.value + 10
                                    await send_log_notification(
                                        bot_client,
                                        f"⏳ FloodWait {fw.value}s, delay {wait_time}s untuk pesan {msg_id}",
                                        control_message.id
                                    )
                                    await asyncio.sleep(wait_time)
                                    continue
                                except Exception as e:
                                    await send_log_notification(
                                        bot_client,
                                        f"⚠️ Gagal forward pesan {msg_id}: {str(e)}",
                                        control_message.id
                                    )
                                    continue
                            
                            # 5. Send LOVE_QUOTES
                            for quote_idx, quote in enumerate(LOVE_QUOTES, 1):
                                try:
                                    await user_client.send_message(
                                        created_chat_id,
                                        f"<i>💙 {quote}</i>",
                                        parse_mode=ParseMode.HTML
                                    )
                                    await asyncio.sleep(4)
                                except FloodWait as fw:
                                    await asyncio.sleep(fw.value + 10)
                                    continue
                                except Exception as e:
                                    await send_log_notification(
                                        bot_client,
                                        f"⚠️ Gagal kirim quote {quote_idx}: {str(e)}",
                                        control_message.id
                                    )
                                    continue
                            
                            # 6. Send LOVE_QUOTES_2
                            for quote_idx, quote in enumerate(LOVE_QUOTES_2, 1):
                                try:
                                    await user_client.send_message(
                                        created_chat_id,
                                        f"<i>💖 {quote}</i>",
                                        parse_mode=ParseMode.HTML
                                    )
                                    await asyncio.sleep(4)
                                except FloodWait as fw:
                                    await asyncio.sleep(fw.value + 10)
                                    continue
                                except Exception as e:
                                    await send_log_notification(
                                        bot_client,
                                        f"⚠️ Gagal kirim quote 2-{quote_idx}: {str(e)}",
                                        control_message.id
                                    )
                                    continue
                            
                            # 7. Invite bots (hanya untuk tipe 'i')
                            if group_type == "i" and bot_entities:
                                success_bots = []
                                failed_bots = []
                                
                                for bot_idx, bot in enumerate(bot_entities, 1):
                                    try:
                                        await user_client.add_chat_members(
                                            created_chat_id,
                                            bot.id
                                        )
                                        await asyncio.sleep(3)
                                        success_bots.append(bot.username or str(bot.id))
                                        
                                        # Send /help and /id
                                        for cmd in ["/help", "/id"]:
                                            try:
                                                await user_client.send_message(
                                                    created_chat_id,
                                                    cmd
                                                )
                                                await asyncio.sleep(3)
                                            except Exception as e:
                                                await send_log_notification(
                                                    bot_client,
                                                    f"⚠️ Gagal kirim {cmd} ke bot {bot.username}: {str(e)}",
                                                    control_message.id
                                                )
                                    except Exception as e:
                                        failed_bots.append(f"{bot.username or bot.id}: {str(e)}")
                                        await asyncio.sleep(3)
                                
                                # Report hasil invite
                                if success_bots:
                                    report = f"✅ Berhasil invite {len(success_bots)} bot ke -100{created_chat_id}"
                                    await user_client.send_message(
                                        created_chat_id,
                                        f"__{report}__"
                                    )
                                    await send_log_notification(
                                        bot_client,
                                        report,
                                        control_message.id
                                    )
                                
                                if failed_bots:
                                    failed_report = f"❌ Gagal invite {len(failed_bots)} bot"
                                    await send_log_notification(
                                        bot_client,
                                        failed_report,
                                        control_message.id
                                    )
                            
                            # 8. Invite assistant dan kirim welcome message
                            try:
                                await user_client.add_chat_members(
                                    created_chat_id,
                                    assistant.id
                                )
                                await asyncio.sleep(3)
                                
                                # Welcome message dengan inline buttons
                                welcome_buttons = InlineKeyboardMarkup([
                                    [
                                        InlineKeyboardButton("Channel 1", url="https://t.me/alphaxproject"),
                                        InlineKeyboardButton("Channel 2", url="https://t.me/tgreceh")
                                    ],
                                    [
                                        InlineKeyboardButton("Channel 3", url="https://t.me/kutipaninsecure"),
                                        InlineKeyboardButton("Channel 4", url="https://t.me/caritemanlink")
                                    ]
                                ])
                                
                                welcome_msg = await bot_client.send_message(
                                    created_chat_id,
                                    "<b>❇️ Welcome to our Aliansi AlphaX:</b>",
                                    reply_markup=welcome_buttons,
                                    parse_mode=ParseMode.HTML
                                )
                                
                                await send_log_notification(
                                    bot_client,
                                    f"✅ Assistant @{assistant.username} invited dan welcome message dikirim",
                                    control_message.id
                                )
                            except Exception as e:
                                await send_log_notification(
                                    bot_client,
                                    f"⚠️ Gagal invite assistant: {str(e)}",
                                    control_message.id
                                )
                            
                            # 9. Send LOVE_QUOTES_3 via assistant
                            for quote_idx, quote in enumerate(LOVE_QUOTES_3, 1):
                                try:
                                    await bot_client.send_message(
                                        created_chat_id,
                                        f"<i>💗 {quote}</i>",
                                        parse_mode=ParseMode.HTML
                                    )
                                    await asyncio.sleep(4)
                                except FloodWait as fw:
                                    await asyncio.sleep(fw.value + 10)
                                    continue
                                except Exception as e:
                                    await send_log_notification(
                                        bot_client,
                                        f"⚠️ Gagal kirim quote 3-{quote_idx}: {str(e)}",
                                        control_message.id
                                    )
                                    continue
                            
                            # 10. Get approximate message count
                            try:
                                # Get recent messages count
                                messages = []
                                async for msg in user_client.get_chat_history(created_chat_id, limit=100):
                                    messages.append(msg)
                                
                                count_msg = await bot_client.send_message(
                                    created_chat_id,
                                    f"<i>Total pesan dalam grup ini: {len(messages)}+</i>",
                                    parse_mode=ParseMode.HTML
                                )
                                await asyncio.sleep(3)
                            except Exception as e:
                                await send_log_notification(
                                    bot_client,
                                    f"⚠️ Gagal hitung pesan: {str(e)}",
                                    control_message.id
                                )
                            
                            # 11. Link ke pesan pertama
                            if first_msg_id:
                                try:
                                    link_msg = f"<i>➟ ke pesan pertama:</i> <b><a href='t.me/c/{created_chat_id}/{first_msg_id}'>» di sini</a></b>"
                                    await user_client.send_message(
                                        created_chat_id,
                                        link_msg,
                                        parse_mode=ParseMode.HTML
                                    )
                                    await asyncio.sleep(3)
                                except Exception as e:
                                    await send_log_notification(
                                        bot_client,
                                        f"⚠️ Gagal kirim link pesan pertama: {str(e)}",
                                        control_message.id
                                    )
                            
                            # 12. Completion message
                            group_end_time = datetime.now()
                            group_duration = (group_end_time - group_start_time).total_seconds()
                            
                            completion_msg = await bot_client.send_message(
                                created_chat_id,
                                f"<i>✅ grup <code>-100{created_chat_id}</code> selesai dikustomisasi dalam {format_duration(group_duration)}!</i>",
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
                                    await asyncio.sleep(3)
                                except Exception as e:
                                    await send_log_notification(
                                        bot_client,
                                        f"⚠️ Gagal kirim reaction: {str(e)}",
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
                        
                        LAUCREATE_TASKS[task_id]["created_groups"] = created_groups
                        LAUCREATE_TASKS[task_id]["current_index"] = i
                        
                        # Kirim update progress
                        progress_msg = (
                            f"✅ Grup {i}/{count} berhasil dibuat\n"
                            f"📛 Nama: {current_group_name}\n"
                            f"🔗 Link: {invite_link[:50]}...\n"
                            f"⏱️ Waktu: {format_duration((datetime.now() - group_start_time).total_seconds())}"
                        )
                        
                        await send_log_notification(
                            bot_client,
                            progress_msg,
                            control_message.id
                        )
                        
                    except FloodWait as fw:
                        wait_msg = f"⏳ FloodWait {fw.value}s untuk grup {current_group_name}"
                        await send_log_notification(bot_client, wait_msg, control_message.id)
                        await asyncio.sleep(fw.value + 10)
                        continue  # Coba lagi grup yang sama
                    except Exception as e:
                        error_msg = f"❌ Error membuat grup {current_group_name}: {str(e)}"
                        await send_log_notification(bot_client, error_msg, control_message.id)
                        i += 1
                        continue
                
                # Update control message
                progress_text = (
                    f"📊 <b>Progress Laucreate</b>\n\n"
                    f"• Created: {i}/{count}\n"
                    f"• Berhasil: {len(created_groups)}\n"
                    f"• Current: {current_group_name}\n"
                    f"• Status: {'⏸️ Paused' if LAUCREATE_TASKS[task_id].get('paused') else '▶️ Running'}"
                )
                
                try:
                    control_buttons = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("🛑 Stop", callback_data="stop_laucreate"),
                            InlineKeyboardButton("⏸️ Pause", callback_data="pause_laucreate"),
                            InlineKeyboardButton("▶️ Resume", callback_data="resume_laucreate")
                        ],
                        [
                            InlineKeyboardButton("📊 Status Detail", callback_data="status_laucreate"),
                            InlineKeyboardButton("📋 List Grup", callback_data="list_laucreate")
                        ],
                        [
                            InlineKeyboardButton("🔁 Recurring", callback_data="recurring_laucreate"),
                            InlineKeyboardButton("✏️ Edit Terakhir", callback_data="edit_last_laucreate")
                        ]
                    ])
                    
                    await control_message.edit_text(
                        progress_text,
                        reply_markup=control_buttons,
                        parse_mode=ParseMode.HTML
                    )
                except Exception as e:
                    logger.error(f"Gagal update control message: {e}")
                
                # Delay antar grup
                if i < count:
                    await asyncio.sleep(delay)
                
                # Extra delay per batch
                if i % batch_size == 0 and i < count:
                    extra_delay = extra_delay_minutes * 60
                    batch_msg = f"⏳ Extra delay {extra_delay_minutes} menit setelah batch {i//batch_size} ({batch_size} grup)"
                    await send_log_notification(bot_client, batch_msg, control_message.id)
                    await asyncio.sleep(extra_delay)
                
                i += 1
                
            except Exception as e:
                logger.error(f"Error dalam loop pembuatan grup: {e}")
                await send_log_notification(
                    bot_client,
                    f"❌ Error dalam loop untuk grup {i}: {str(e)}",
                    control_message.id
                )
                i += 1
                continue
        
        # ===== TASK COMPLETED =====
        if LAUCREATE_TASKS.get(task_id, {}).get("running", False):
            end_time = datetime.now()
            total_duration = (end_time - LAUCREATE_TASKS[task_id]["start_time"]).total_seconds()
            
            # Simpan konfigurasi task yang selesai
            COMPLETED_LAUCREATE_TASKS[task_id] = {
                "delay": delay,
                "count": count,
                "extra_delay_minutes": extra_delay_minutes,
                "batch_size": batch_size,
                "group_type": group_type,
                "name_pattern": name_pattern,
                "username_prefix": username_prefix,
                "bot_identifiers": bot_identifiers,
                "created_groups": created_groups,
                "total_duration": total_duration,
                "user_id": user_info.id,
                "start_time": LAUCREATE_TASKS[task_id]["start_time"].strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # Kirim laporan akhir
            await send_completion_report(
                bot_client,
                created_groups,
                count,
                total_duration,
                user_info,
                control_message
            )
        else:
            # Task dihentikan
            await send_log_notification(
                bot_client,
                f"🛑 Task laucreate dihentikan\n"
                f"• Grup dibuat: {len(created_groups)}/{count}\n"
                f"• User: {user_info.first_name}",
                control_message.id
            )
    
    except Exception as e:
        logger.error(f"Critical error in laucreate_loop: {e}", exc_info=True)
        await send_log_notification(
            bot_client,
            f"❌ Critical error in laucreate_loop: {html.escape(str(e))}",
            control_message.id
        )
    finally:
        # Cleanup foto profil
        if photo_path and os.path.exists(photo_path):
            try:
                os.remove(photo_path)
                logger.info(f"Foto profil dihapus: {photo_path}")
            except Exception as e:
                logger.error(f"Gagal hapus foto profil: {e}")
        
        # Cleanup task state
        LAUCREATE_TASKS.pop(task_id, None)

async def send_completion_report(
    bot_client: Client,
    created_groups: List[Dict],
    requested_count: int,
    total_duration: float,
    user_info: Any,
    control_message: Message
):
    """Kirim laporan penyelesaian task"""
    try:
        success_count = len(created_groups)
        
        # Buat log file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_filename = f"laucreate_log_{timestamp}.txt"
        
        with open(log_filename, 'w', encoding='utf-8') as f:
            f.write(f"#LOG Laucreate - {timestamp}\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"AKUN PEMBUAT:\n")
            f.write(f"• Nama: {user_info.first_name or 'N/A'} {user_info.last_name or ''}\n")
            f.write(f"• ID: {user_info.id}\n")
            f.write(f"• Username: @{user_info.username if user_info.username else 'N/A'}\n\n")
            
            f.write(f"STATISTIK:\n")
            f.write(f"• Diminta: {requested_count} grup\n")
            f.write(f"• Berhasil: {success_count} grup\n")
            f.write(f"• Gagal: {requested_count - success_count} grup\n")
            f.write(f"• Durasi: {format_duration(total_duration)}\n\n")
            
            f.write(f"DETAIL GRUP:\n")
            f.write("=" * 60 + "\n\n")
            
            for idx, group in enumerate(created_groups, 1):
                f.write(f"{idx}. {group['name']}\n")
                f.write(f"   • ID: -100{group['id']}\n")
                f.write(f"   • Tipe: {group['type']}\n")
                f.write(f"   • Waktu: {group['time']}\n")
                f.write(f"   • Link: {group['link']}\n\n")
        
        # Kirim file log
        await bot_client.send_document(
            LOG_CHAT_ID,
            document=log_filename,
            caption=(
                f"📊 <b>Laporan Laucreate Selesai</b>\n\n"
                f"• ✅ Berhasil: {success_count}/{requested_count} grup\n"
                f"• ⏱️ Durasi: {format_duration(total_duration)}\n"
                f"• 👤 User: {user_info.first_name or 'N/A'}\n"
                f"• 🆔 ID: <code>{user_info.id}</code>\n\n"
                f"<i>Module by @AlphaXproject team</i>"
            ),
            reply_to_message_id=control_message.id,
            parse_mode=ParseMode.HTML
        )
        
        # Hapus file lokal
        os.remove(log_filename)
        
        # Update control message dengan tombol baru
        final_buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📥 Download Log", callback_data="download_log_laucreate"),
                InlineKeyboardButton("🔁 Recurring", callback_data="recurring_laucreate")
            ],
            [
                InlineKeyboardButton("📋 List Grup", callback_data="list_groups_laucreate"),
                InlineKeyboardButton("🗑️ Hapus Task", callback_data="delete_task_laucreate")
            ]
        ])
        
        await control_message.edit_text(
            f"✅ <b>Task Laucreate Selesai</b>\n\n"
            f"• 📊 Berhasil membuat {success_count} dari {requested_count} grup\n"
            f"• ⏱️ Durasi: {format_duration(total_duration)}\n"
            f"• 👤 User: {user_info.first_name}\n"
            f"• 📁 Log: Terkirim ke log channel",
            reply_markup=final_buttons,
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"Error sending completion report: {e}")
        await send_log_notification(
            bot_client,
            f"❌ Error dalam completion report: {str(e)}",
            control_message.id
        )

# ==================== COMMAND HANDLER ====================

@Altruix.bot.on_message(
    filters.command("laucreate", prefixes=HANDLER) & 
    filters.user(Altruix.auth_users)
)
@log_errors
async def laucreate_command_handler(client: Client, message: Message):
    """Handler untuk command .laucreate"""
    
    # Cek jika ada task yang sedang berjalan
    if 'laucreate_main' in LAUCREATE_TASKS and LAUCREATE_TASKS['laucreate_main'].get('running', False):
        await message.reply("⚠️ Ada task laucreate yang sedang berjalan. Gunakan tombol kontrol untuk mengatur.")
        return
    
    async with CREATE_LOCK:
        try:
            # Parse command
            args = message.text.split()
            
            if len(args) < 7:
                await message.reply(
                    "**❌ Format Salah!**\n\n"
                    "**Penggunaan:** `.laucreate <delay> <jumlah> <delay_batch> <ukuran_batch> <tipe> <pola_nama> ; <username> <bot_list>`\n\n"
                    "**Contoh:** `.laucreate 5 25 30 5 a \"🔰 X(tahun)-B(bulan)-T(tanggal)A\" ; myusername`\n\n"
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
            
            if batch_size <= 0 or batch_size > count:
                await message.reply("⚠️ Ukuran batch tidak valid, mengatur ke 5")
                batch_size = 5
            
            # Konfirmasi sebelum memulai
            confirm_buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Ya, Mulai", callback_data=f"confirm_laucreate:{delay}:{count}:{batch_delay_min}:{batch_size}:{group_type}:{name_pattern}:{username_prefix or ''}:{','.join(bot_identifiers)}"),
                    InlineKeyboardButton("❌ Batal", callback_data="cancel_laucreate")
                ]
            ])
            
            await message.reply(
                f"**Konfirmasi Task Laucreate**\n\n"
                f"• Jumlah: {count} grup\n"
                f"• Delay: {delay} detik per grup\n"
                f"• Batch: {batch_size} grup, delay {batch_delay_min} menit\n"
                f"• Tipe: {group_type}\n"
                f"• Pola: {name_pattern}\n"
                f"• Username: {username_prefix or 'Tidak ada'}\n"
                f"• Bots: {len(bot_identifiers) if group_type == 'i' else 0}\n\n"
                f"Task akan berjalan di background. Lanjutkan?",
                reply_markup=confirm_buttons,
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logger.error(f"Error in laucreate_command_handler: {e}", exc_info=True)
            await message.reply(f"❌ Error: {str(e)}")

# ==================== CALLBACK QUERY HANDLER ====================
@Altruix.bot.on_callback_query(filters.regex(r"^confirm_laucreate:"))
@log_errors
async def confirm_laucreate_handler(client: Client, callback_query: CallbackQuery):
    """Handler untuk konfirmasi mulai task"""
    
    try:
        data_parts = callback_query.data.split(":")
        if len(data_parts) < 8:
            await callback_query.answer("Data tidak valid")
            return
        
        delay = int(data_parts[1])
        count = int(data_parts[2])
        batch_delay_min = int(data_parts[3])
        batch_size = int(data_parts[4])
        group_type = data_parts[5]
        name_pattern = data_parts[6]
        username_prefix = data_parts[7] if data_parts[7] else None
        bot_identifiers_str = data_parts[8] if len(data_parts) > 8 else ""
        bot_identifiers = bot_identifiers_str.split(",") if bot_identifiers_str else []
        
        # Hapus pesan konfirmasi
        await callback_query.message.delete()
        
        # Buat control message
        control_buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🛑 Stop", callback_data="stop_laucreate"),
                InlineKeyboardButton("⏸️ Pause", callback_data="pause_laucreate"),
                InlineKeyboardButton("▶️ Resume", callback_data="resume_laucreate")
            ],
            [
                InlineKeyboardButton("📊 Status Detail", callback_data="status_laucreate"),
                InlineKeyboardButton("📋 List Grup", callback_data="list_laucreate")
            ]
        ])
        
        control_msg = await client.send_message(
            LOG_CHAT_ID,
            f"🚀 <b>Task Laucreate Dimulai</b>\n\n"
            f"• User: {callback_query.from_user.mention}\n"
            f"• Jumlah: {count} grup\n"
            f"• Delay: {delay} detik\n"
            f"• Tipe: {group_type}\n"
            f"• Pola: {name_pattern}\n"
            f"• Batch: {batch_size} grup, delay {batch_delay_min} menit\n\n"
            f"<i>Klik tombol di bawah untuk kontrol</i>",
            reply_markup=control_buttons,
            parse_mode=ParseMode.HTML
        )
        
        # Start task
        asyncio.create_task(
            laucreate_loop(
                user_client=callback_query._client,
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
                control_message=control_msg
            )
        )
        
        await callback_query.answer("Task dimulai!")
        await callback_query.message.reply(
            f"✅ **Task Laucreate Dimulai**\n\n"
            f"• Akan membuat {count} grup\n"
            f"• Delay: {delay} detik per grup\n"
            f"• Monitor progress di log channel\n"
            f"• Gunakan tombol kontrol untuk manage task",
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Error in confirm_laucreate_handler: {e}")
        await callback_query.answer(f"Error: {str(e)}")

@Altruix.bot.on_callback_query(filters.regex(r"^(stop|pause|resume|status|list|recurring|edit_last|download_log|list_groups|delete_task|cancel)_laucreate$"))
@log_errors
async def laucreate_control_handler(client: Client, callback_query: CallbackQuery):
    """Handler untuk tombol kontrol laucreate"""
    
    action = callback_query.data.split("_")[0]
    task_id = 'laucreate_main'
    
    try:
        if action == "cancel":
            await callback_query.message.delete()
            await callback_query.answer("Task dibatalkan")
            return
        
        if action == "stop":
            if task_id in LAUCREATE_TASKS:
                LAUCREATE_TASKS[task_id]["running"] = False
                await send_log_notification(
                    client,
                    f"🛑 Task laucreate dihentikan oleh {callback_query.from_user.mention}",
                    LAUCREATE_TASKS[task_id].get("control_message_id")
                )
                await callback_query.answer("Task dihentikan")
                await callback_query.message.edit_text(
                    callback_query.message.text + "\n\n🛑 **DIHENTIKAN OLEH USER**",
                    parse_mode=ParseMode.HTML
                )
            else:
                await callback_query.answer("Tidak ada task yang berjalan")
        
        elif action == "pause":
            if task_id in LAUCREATE_TASKS and LAUCREATE_TASKS[task_id].get("running", False):
                LAUCREATE_TASKS[task_id]["paused"] = True
                LAUCREATE_TASKS[task_id]["pause_event"].clear()
                await send_log_notification(
                    client,
                    f"⏸️ Task laucreate dipause oleh {callback_query.from_user.mention}",
                    LAUCREATE_TASKS[task_id].get("control_message_id")
                )
                await callback_query.answer("Task dipause")
                await callback_query.message.edit_text(
                    callback_query.message.text + "\n\n⏸️ **DIPAUSE OLEH USER**",
                    parse_mode=ParseMode.HTML
                )
            else:
                await callback_query.answer("Task tidak berjalan atau sudah dihentikan")
        
        elif action == "resume":
            if task_id in LAUCREATE_TASKS and LAUCREATE_TASKS[task_id].get("paused", False):
                LAUCREATE_TASKS[task_id]["paused"] = False
                LAUCREATE_TASKS[task_id]["pause_event"].set()
                await send_log_notification(
                    client,
                    f"▶️ Task laucreate di-resume oleh {callback_query.from_user.mention}",
                    LAUCREATE_TASKS[task_id].get("control_message_id")
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
            if task_id in LAUCREATE_TASKS:
                task_info = LAUCREATE_TASKS[task_id]
                created = len(task_info.get("created_groups", []))
                current = task_info.get("current_index", 0)
                running = task_info.get("running", False)
                paused = task_info.get("paused", False)
                start_time = task_info.get("start_time", datetime.now())
                elapsed = (datetime.now() - start_time).total_seconds()
                
                status_text = (
                    f"📊 <b>Status Task Laucreate</b>\n\n"
                    f"• Created: {created}\n"
                    f"• Current: {current}\n"
                    f"• Running: {'Ya' if running else 'Tidak'}\n"
                    f"• Paused: {'Ya' if paused else 'Tidak'}\n"
                    f"• Elapsed: {format_duration(elapsed)}\n"
                    f"• Start: {start_time.strftime('%Y-%m-%d %H:%M:%S')}"
                )
                await callback_query.answer(status_text, show_alert=True)
            else:
                await callback_query.answer("Tidak ada task yang berjalan")
        
        elif action == "list":
            if task_id in LAUCREATE_TASKS:
                groups = LAUCREATE_TASKS[task_id].get("created_groups", [])
                if groups:
                    list_text = "📋 <b>Grup yang Telah Dibuat:</b>\n\n"
                    for idx, group in enumerate(groups[-10:], 1):  # Tampilkan 10 terakhir
                        list_text += f"{idx}. {group['name']}\n   ID: -100{group['id']}\n\n"
                    
                    if len(groups) > 10:
                        list_text += f"... dan {len(groups) - 10} grup lainnya"
                    
                    await callback_query.answer(list_text, show_alert=True)
                else:
                    await callback_query.answer("Belum ada grup yang dibuat")
            else:
                await callback_query.answer("Tidak ada task yang berjalan")
        
        elif action == "recurring":
            if task_id in COMPLETED_LAUCREATE_TASKS:
                config = COMPLETED_LAUCREATE_TASKS[task_id]
                # Implement recurring task
                await callback_query.answer("Fitur recurring dalam pengembangan")
            else:
                await callback_query.answer("Tidak ada task selesai untuk diulang")
        
        elif action == "edit_last":
            if task_id in LAUCREATE_TASKS:
                groups = LAUCREATE_TASKS[task_id].get("created_groups", [])
                if groups:
                    last_group = groups[-1]
                    await callback_query.answer(f"Edit grup terakhir: {last_group['name']}")
                    # Implement edit last group
                else:
                    await callback_query.answer("Belum ada grup yang dibuat")
            else:
                await callback_query.answer("Tidak ada task yang berjalan")
        
        elif action == "download_log":
            if task_id in COMPLETED_LAUCREATE_TASKS:
                await callback_query.answer("Log sudah dikirim ke channel")
            else:
                await callback_query.answer("Belum ada log yang tersedia")
        
        elif action == "list_groups":
            if task_id in COMPLETED_LAUCREATE_TASKS:
                groups = COMPLETED_LAUCREATE_TASKS[task_id].get("created_groups", [])
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
            if task_id in COMPLETED_LAUCREATE_TASKS:
                COMPLETED_LAUCREATE_TASKS.pop(task_id)
                await callback_query.answer("Task dihapus dari memory")
                await callback_query.message.delete()
            else:
                await callback_query.answer("Tidak ada task untuk dihapus")
    
    except Exception as e:
        logger.error(f"Error in laucreate_control_handler: {e}")
        await callback_query.answer(f"Error: {str(e)}")

# ==================== CLEANUP ON SHUTDOWN ====================
async def cleanup_laucreate_tasks():
    """Cleanup semua task laucreate saat shutdown"""
    for task_id in list(LAUCREATE_TASKS.keys()):
        if LAUCREATE_TASKS[task_id].get("running", False):
            LAUCREATE_TASKS[task_id]["running"] = False
            logger.info(f"Stopped laucreate task {task_id} on shutdown")

# ==================== PLUGIN INFO ====================
__plugin_name__ = "Laucreate"
__plugin_version__ = "1.0.3"
__plugin_author__ = "AlphaXproject Team (ported for Altruix)"
__plugin_description__ = "Advanced group creation tool for Telegram with full control panel"

# Register cleanup
import atexit
atexit.register(lambda: asyncio.run(cleanup_laucreate_tasks()))

# Log sukses loading
try:
    Altruix.log(f"[DEBUG] Loaded → {__plugin_name__} {PLUGIN_VERSION}", level=20)
except Exception as e:
    logger.info(f"[DEBUG] Loaded → {__plugin_name__} {PLUGIN_VERSION}")
