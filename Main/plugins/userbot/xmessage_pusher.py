# xmessage_pusher.py
"""
Plugin Message Pusher untuk Altruix Userbot
Inspired by xcreategroup.py logic
Created by Antigravity for Altruix
"""

import os
import asyncio
import logging
import json
import html
import traceback
from datetime import datetime
from typing import List, Dict, Any, Optional

from pyrogram import Client, filters
from pyrogram.errors import FloodWait, RPCError, UserIsBlocked, PeerIdInvalid, ChatWriteForbidden, BadRequest
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode

from Main import Altruix
from Main.core.decorators import log_errors, iuser_check
from Main.core.types.message import Message
from Main.utils.file_helpers import get_db_path
from Main.utils.helpers import ChatPrivileges

# ─── LOGGER ───
logger = logging.getLogger("altruix.xmessage_pusher")
logger.setLevel(logging.INFO)

plugin_name = f"{os.path.basename(__file__)}"
__plugin_name__ = plugin_name if plugin_name else "xmessage_pusher"
PLUGIN_VERSION = "0.1.15"

# ─── CONFIG ───
LOG_CHAT_ID = Altruix.log_chat or Altruix.config.LOG_CHAT_ID or Altruix.config.OWNER_USERS_ID
SRC_CHANNEL = "alphaxbbc"

# Message IDs from xcreategroup.py
LIST_MSG_IDS = [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17]
MSG_IMG_IDS = [25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76]

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
    "Cinta sejati adalah ketika kita mampu melihat kelemahan pasangan sebagai bagian dari keunikan mereka, mendukung pertumbuhan mereka dengan sabar and pengertian, serta bersama-sama menciptakan lingkungan di mana keduanya dapat berkembang menjadi versi terbaik dari diri mereka sendiri sepanjang hayat.",
    "Cinta adalah cahaya yang menerangi kegelapan hati, memberikan warmth dan kenyamanan di tengah dinginnya dunia, mengajarkan kita untuk memaafkan, menghargai, dan setia, sehingga setiap momen bersama menjadi kenangan berharga yang memperkaya jiwa dan memperkuat ikatan yang tak terpisahkan.",
    "Cinta adalah pemberontakan terhadap kesendirian, di mana dua jiwa yang terpisah menemukan kesatuan dalam kebersamaan, saling melengkapi kekurangan satu sama lain, dan bersama-sama menciptakan dunia baru yang penuh dengan makna, tawa, dan petualangan yang tak pernah berakhir seumur hidup.",
    "Cinta sejati muncul ketika kita berani melepaskan ego diri, memrioritaskan kebahagiaan orang yang dicintai, dan membangun hubungan berdasarkan kejujuran mutlak, sehingga ikatan tersebut menjadi sumber kekuatan yang membantu kita menghadapi segala tantangan hidup dengan optimisme dan ketabahan.",
    "Cinta adalah simfoni indah dari emosi manusia, di mana setiap nada mewakili kasih sayang, pengorbanan, dan kegembiraan, yang dimainkan bersama untuk menciptakan harmoni sempurna yang mengisi hidup dengan warna-warni kebahagiaan dan meninggalkan warisan abadi bagi generasi yang akan datang."
]

# Task Storage
MESSAGEPUSHER_TASKS = {}
CACHE_FILE = get_db_path("xmessage_pusher_cache.json")

async def save_cache():
    try:
        data = {}
        for tid, task in MESSAGEPUSHER_TASKS.items():
            task_copy = task.copy()
            # Remove non-serializable objects
            for key in ["pause_event", "task_obj"]:
                if key in task_copy: del task_copy[key]
            if "start_time" in task_copy:
                task_copy["start_time"] = task_copy["start_time"].isoformat()
            data[tid] = task_copy
        
        with open(CACHE_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save cache: {e}")

async def send_log_notification(client, text, user_id, reply_to=None):
    try:
        await client.send_message(
            LOG_CHAT_ID,
            text,
            parse_mode=ParseMode.HTML,
            reply_to_message_id=reply_to
        )
    except Exception as e:
        logger.error(f"Failed to send log: {e}")

async def messagepusher_loop(
    user_client: Client,
    bot_client: Client,
    target_chats: List[Any],
    delay_act: float,
    batch_act: int,
    ba_delay: int,
    options: Dict[str, bool],
    control_message: Message,
    user_id: int
):
    from Main.plugins.userbot.xtaskmanager import register_task, unregister_task, generate_task_id
    tid = generate_task_id("MP")
    
    try:
        user_info = await user_client.get_me()
        userbot_id = user_info.id
        task_id = f"messagepusher_{userbot_id}"
        account_name = f"{user_info.first_name or ''} {user_info.last_name or ''}".strip()
        
        MESSAGEPUSHER_TASKS[task_id] = {
            "running": True,
            "paused": False,
            "pause_event": asyncio.Event(),
            "current_index": 0,
            "start_time": datetime.now(),
            "user_id": user_id,
            "account_name": account_name,
            "task_obj": asyncio.current_task()
        }
        MESSAGEPUSHER_TASKS[task_id]["pause_event"].set()
        await save_cache()
        
        register_task(tid, asyncio.current_task(), "Message Pusher", "xmessage_pusher", user_id, f"Chats: {len(target_chats)}", user_name=account_name)
        
        await send_log_notification(
            bot_client,
            f"<blockquote expandable>🚀 <b>Task Message Pusher Started</b>\n"
            f"• Task ID: <code>{tid}</code>\n"
            f"• Account: <b>{html.escape(account_name)}</b>\n"
            f"• Targets: <code>{len(target_chats)}</code> chats\n"
            f"• Act Delay: <code>{delay_act}</code>s\n"
            f"• Batch Act: <code>{batch_act}</code> | Delay: <code>{ba_delay}</code>s\n"
            f"</blockquote>",
            user_id
        )

        action_count = 0
        async def handle_delay():
            nonlocal action_count
            await asyncio.sleep(delay_act)
            action_count += 1
            if action_count >= batch_act:
                action_count = 0
                await asyncio.sleep(ba_delay)

        for idx, chat_id in enumerate(target_chats, 1):
            # ─── PAUSE HANDLER (Xtaskmanager) ───
            while True:
                registry = getattr(Altruix, "_TASK_REGISTRY", {})
                if tid in registry and registry[tid].get("paused"):
                    await asyncio.sleep(1)
                else:
                    break

            if not MESSAGEPUSHER_TASKS.get(task_id, {}).get("running"): break
            
            # Convert to int if numeric string to avoid Pyrogram interpreting it as a phone number
            try:
                if str(chat_id).replace("-", "").isdigit():
                    chat_id = int(chat_id)
            except: pass
            
            try:
                # 0. Invite Assistant/Bots if enabled
                if options.get("invite_assistant"):
                    try:
                        bot_me = await bot_client.get_me()
                        await user_client.add_chat_members(chat_id, bot_me.id)
                        await handle_delay()
                    except Exception as e:
                        logger.warning(f"Failed to invite assistant to {chat_id}: {e}")

                if options.get("invite_bots") and options.get("bots"):
                    bots = options.get("bots").replace(",", " ").split()
                    for bot_username in bots:
                        try:
                            # Ensure @ prefix
                            if not (bot_username.startswith("@") or bot_username.isdigit()):
                                bot_username = f"@{bot_username}"
                            await user_client.add_chat_members(chat_id, bot_username)
                            await handle_delay()
                        except Exception as e:
                            logger.warning(f"Failed to invite bot {bot_username} to {chat_id}: {e}")

                # 0.1 Handle Anon Adm if enabled
                if options.get("anon_adm"):
                    try:
                        await user_client.promote_chat_member(
                            chat_id, user_info.id,
                            privileges=ChatPrivileges(
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
                        )
                        await handle_delay()
                    except Exception as e:
                        logger.warning(f"Failed to set anon adm for {chat_id}: {e}")

                # 1. LIST_MSG_IDS
                for msg_id in LIST_MSG_IDS:
                    await user_client.copy_message(chat_id, SRC_CHANNEL, msg_id)
                    await handle_delay()
                
                # 2. LOVE_QUOTES
                if options.get("quote1"):
                    for quote in LOVE_QUOTES:
                        await user_client.send_message(chat_id, f"<i>💙 {quote}</i>", parse_mode=ParseMode.HTML)
                        await handle_delay()
                
                # 3. LOVE_QUOTES_2
                if options.get("quote2"):
                    for quote in LOVE_QUOTES_2:
                        await user_client.send_message(chat_id, f"<i>💖 {quote}</i>", parse_mode=ParseMode.HTML)
                        await handle_delay()
                
                # 4. MSG_IMG_IDS
                if options.get("msg_img"):
                    for img_id in MSG_IMG_IDS:
                        await user_client.copy_message(chat_id, SRC_CHANNEL, img_id)
                        await handle_delay()
                
                # 5. LOVE_QUOTES_3
                if options.get("quote3"):
                    for quote in LOVE_QUOTES_3:
                        await user_client.send_message(chat_id, f"<i>🌹 {quote}</i>", parse_mode=ParseMode.HTML)
                        await handle_delay()

                await send_log_notification(
                    bot_client,
                    f"✅ <b>Pushed to chat {idx}/{len(target_chats)}</b>: <code>{chat_id}</code>",
                    user_id
                )
            except Exception as e:
                error_tb = traceback.format_exc()
                logger.error(f"Error pushing to {chat_id}: {e}\n{error_tb}")
                await send_log_notification(
                    bot_client, 
                    f"❌ <b>Error on {chat_id}</b>: {str(e)}\n\n<blockquote expandable><code>{html.escape(error_tb)}</code></blockquote>", 
                    user_id
                )

        await send_log_notification(bot_client, f"🏁 <b>Message Pusher Task Completed!</b>\n• Task ID: <code>{tid}</code>", user_id)

    except Exception as e:
        error_tb = traceback.format_exc()
        logger.error(f"Critical error in pusher_loop: {e}\n{error_tb}")
        await send_log_notification(
            bot_client,
            f"❌ <b>Critical Error in Message Pusher:</b> {str(e)}\n\n<blockquote expandable><code>{html.escape(error_tb)}</code></blockquote>",
            user_id
        )
    finally:
        unregister_task(tid)
        MESSAGEPUSHER_TASKS.pop(task_id, None)
        await save_cache()

# ─── COMMANDS ───
@Altruix.register_on_cmd(
    ["pushmsg"], 
    cmd_help={
        "help": "Open the interactive Message Pusher dashboard.", 
        "usage": ".pushmsg [chat_id | current]",
        "example": ".pushmsg -100123456789",
        "details": (
            "An interactive dashboard to push message sequences (Quotes, Images, etc.) to target chats.\n\n"
            "<b>Features:</b>\n"
            "• <b>Quotes (LQ1-3)</b>: Send three sets of curated love quotes.\n"
            "• <b>Images (IMG)</b>: Copy message sequences from the source channel.\n"
            "• <b>Anon Adm</b>: Automatically promote to anonymous admin before sending.\n"
            "• <b>Bot Invite</b>: Automatically invite the bot assistant or a custom list of bots to target chats.\n"
            "• <b>Task Control</b>: Use <code>.tasklist</code> to monitor, pause, resume, or cancel pusher tasks."
        )
    }
)
@iuser_check
@log_errors
async def pushmsg_cmd(c: Client, m: Message):
    user_id = m.from_user.id if m.from_user else c.me.id
    logger.info(f"Received .pushmsg command from {user_id} (Anon: {m.from_user is None})")
    
    # Handle optional target argument
    target_arg = m.user_input
    
    try:
        from Main.internals.settings_handlers.message_pusher_handlers import show_pusher_ui, user_messagepusher_state, DEFAULT_PUSHER_CONFIG
        
        # Resolve 'current' keyword
        if target_arg and target_arg.lower() == "current":
            target_arg = str(m.chat.id)

        # Find session index first (needed for composite state key)
        session_index = -1
        for i, client in enumerate(Altruix.clients):
            if client.me and client.me.id == user_id:
                session_index = i
                break
        
        if session_index == -1:
            return await m.reply_msg("❌ Session not found.")

        # Use composite state key matching all dashboard handlers
        state_key = f"{user_id}_{session_index}"

        # Initialize or update state with targets if provided
        if target_arg:
            if state_key not in user_messagepusher_state:
                user_messagepusher_state[state_key] = {
                    "step": "idle",
                    "config": DEFAULT_PUSHER_CONFIG.copy(),
                    "session_index": session_index,
                    "sub_menu": None
                }
            user_messagepusher_state[state_key]["config"]["targets"] = target_arg
            logger.info(f"Set targets to: {target_arg}")

            
        # Trigger the dashboard through inline query
        bot_username = Altruix.bot_manager.get_bot_username(c.me.id)
        logger.info(f"Triggering inline query to @{bot_username} with query: pushmsg_{session_index}")
        
        try:
            results = await c.get_inline_bot_results(bot_username, f"pushmsg_{session_index}")
            logger.info(f"Received {len(results.results)} inline results. Query ID: {results.query_id}")
            
            await c.send_inline_bot_result(
                chat_id=m.chat.id,
                query_id=results.query_id,
                result_id=results.results[0].id,
                reply_to_message_id=m.reply_to_message.id if m.reply_to_message else m.id
            )
            logger.info("Successfully sent inline bot result.")
        except Exception as inline_err:
            logger.error(f"Failed to get or send inline result: {inline_err}")
            # Fallback to direct edit if possible (though unlikely to work if inline failed)
            raise inline_err

        await m.delete_if_self()
    except Exception as e:
        error_tb = traceback.format_exc()
        logger.error(f"Error in pushmsg_cmd: {e}\n{error_tb}")
        await m.reply_msg(f"❌ <b>Error Loading Dashboard:</b>\n<code>{html.escape(str(e))}</code>\n\n<blockquote expandable><code>{html.escape(error_tb)}</code></blockquote>", parse_mode=ParseMode.HTML)

Altruix.log(f"[DEBUG] Loaded → {__plugin_name__} {PLUGIN_VERSION}", level=20)
