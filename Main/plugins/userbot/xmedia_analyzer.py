# Main/plugins/userbot/xmedia_analyzer.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
# All rights reserved.

PLUGIN_VERSION = "0.0.454"

import time
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import FloodWait

from Main import Altruix
from Main.core.decorators import log_errors, iuser_check
from Main.internals.settings_handlers.media_analyzer import (
    get_ma_settings, get_ma_status_text, get_ma_kb
)

# Logic Mapping
SCOPE_MAPPING = {
    "all": None,
    "groups": [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP],
    "users": [enums.ChatType.PRIVATE],
    "channels": [enums.ChatType.CHANNEL],
    "bots": [enums.ChatType.PRIVATE],
}

TYPE_MAPPING = {
    "all": None,
    "photo": enums.MessagesFilter.PHOTO,
    "video": enums.MessagesFilter.VIDEO,
    "document": enums.MessagesFilter.DOCUMENT,
    "gif": enums.MessagesFilter.ANIMATION,
    "audio": enums.MessagesFilter.AUDIO,
    "voice": enums.MessagesFilter.VOICE_NOTE,
}

@Altruix.register_on_cmd(
    ["countmedia", "mediacount", "mc"],
    cmd_help={
        "help": "Open Interactive Media Analyzer Dashboard.",
        "usage": "!countmedia",
        "detail": "Opens a premium dashboard with toggles for scope, type, and delays."
    },
)
@iuser_check
@log_errors
async def media_analyzer_dashboard_cmd(client: Client, m: Message):
    """Opens the Media Analyzer dashboard via Bot Assistant."""
    user_id = client.me.id
    bot_username = Altruix.bot_manager.get_bot_username(user_id)
    
    if not bot_username:
        # Fallback to direct text if no bot assistant
        text = await get_ma_status_text(user_id)
        return await m.handle_message(f"⚠️ <b>Bot Assistant not found.</b>\n\n{text}")

    # Try Inline Mode for seamless UI
    try:
        # Note: In Altruix, bot assistants often handle 'ma_menu' via inline query or direct msg
        # Here we simulate the Purgeme pattern: open via inline query
        results = await client.get_inline_bot_results(bot_username, f"ma_menu_uid_{user_id}")
        if results.results:
            await client.send_inline_bot_result(
                m.chat.id, results.query_id, results.results[0].id,
                reply_to_message_id=m.reply_to_message.id if m.reply_to_message else m.id
            )
            await m.delete_if_self()
            return
    except Exception:
        pass

    # Fallback: Send directly via Bot
    bot = Altruix.bot_manager.get_bot(user_id)
    if bot:
        settings = await get_ma_settings(user_id)
        text = await get_ma_status_text(user_id)
        kb = get_ma_kb(user_id, settings)
        await bot.send_message(m.chat.id, text, reply_markup=kb)
        await m.delete_if_self()
    else:
        await m.handle_message("❌ <b>Error:</b> Bot assistant connection failed.")

@log_errors
async def perform_media_scan(client: Client, status_msg: Message, settings: dict, task_id: str = None, ui_msg=None):
    """Core scanning logic, triggered by the dashboard."""
    from Main.plugins.userbot.xcanceltask import unregister_task
    
    # 🎯 Log Group Tracking Delegation
    # Route live updates to the central Log Group via Bot Assistant.
    # Fallback to Userbot's Saved Messages if unavailable.
    try:
        log_chat_id = await Altruix.config.get_env("LOG_CHAT_ID")
        bot = Altruix.bot_manager.get_bot(client.me.id) if hasattr(Altruix, 'bot_manager') else Altruix.bot
        
        if bot and log_chat_id:
            try:
                status_msg = await bot.send_message(int(log_chat_id), f"🚀 <b>Media Analyzer Booting...</b>\n\n<i>Preparing deep scan engine. Task ID: {task_id}</i>")
            except Exception:
                status_msg = await client.send_message("me", f"🚀 <b>Media Analyzer Booting...</b>\n\n<i>Preparing deep scan engine. Task ID: {task_id}</i>")
        else:
            status_msg = await client.send_message("me", f"🚀 <b>Media Analyzer Booting...</b>\n\n<i>Preparing deep scan engine. Task ID: {task_id}</i>")
    except Exception:
        status_msg = await client.send_message("me", f"🚀 <b>Media Analyzer Booting...</b>\n\n<i>Preparing deep scan engine. Task ID: {task_id}</i>")
    
    scope_str = settings.get("scope", "all")
    types_list = settings.get("type", ["all"])
    delay_chat = settings.get("delay_chat", 0.0)
    delay_msg = settings.get("delay_msg", 0.0)
    
    batch_size = settings.get("batch_size", 20)
    batch_delay = settings.get("batch_delay", 120.0)
    batch_msg_size = settings.get("batch_msg_size", 40)
    batch_msg_delay = settings.get("batch_msg_delay", 600.0)
    
    target_types = SCOPE_MAPPING.get(scope_str)
    
    # Map all selected types to their Pyrogram Enums with labels
    active_types = types_list.copy()
    if "all" in active_types:
        active_types = ["photo", "video", "document", "gif", "audio", "voice"]
        
    msg_filters = []
    for t in active_types:
        if t in TYPE_MAPPING and TYPE_MAPPING[t] is not None:
            msg_filters.append((t.capitalize() + "s", TYPE_MAPPING[t]))
                
    mode_str = "🐢 Stealth" if delay_msg > 0 else "🚀 Bulk"
    type_str = ", ".join([t.capitalize() for t in types_list])
    
    results = []
    total_count = 0
    chats_scanned = 0
    chats_matched = 0
    batch_ch_count = 0
    batch_ms_count = 0
    start_time = time.time()
    
    def fmt_time(sec):
        m, s = divmod(int(sec), 60)
        return f"{m}m {s}s" if m and s else (f"{m}m" if m else f"{s}s")
    
    try:
        async for dialog in client.get_dialogs():
            chats_scanned += 1
            chat = dialog.chat
            await asyncio.sleep(0.01) # Yield to other tasks
            
            # Filtering
            is_match = False
            if scope_str == "all": is_match = True
            elif scope_str == "bots":
                if chat.type == enums.ChatType.BOT:
                    is_match = True
                elif chat.type == enums.ChatType.PRIVATE:
                    if (chat.username and "bot" in chat.username.lower()) or (chat.first_name and "bot" in chat.first_name.lower()):
                        is_match = True
            elif target_types and chat.type in target_types:
                is_match = True
                
            if is_match:
                chats_matched += 1
                try:
                    chat_total = 0
                    chat_details = {}
                    
                    if delay_msg > 0:
                        for m_label, m_filter in msg_filters:
                            count = 0
                            async for _ in client.search_messages(chat.id, filter=m_filter):
                                count += 1
                                batch_ms_count += 1
                                if batch_msg_size > 0 and batch_ms_count >= batch_msg_size:
                                    if batch_msg_delay > 0:
                                        try:
                                            await status_msg.edit(f"⏳ <b>Anti-Flood Pause</b>\n\nSleeping for <code>{fmt_time(batch_msg_delay)}</code> due to Batch/Msg limit ({batch_msg_size} msgs).")
                                        except Exception:
                                            pass
                                        await asyncio.sleep(batch_msg_delay)
                                    batch_ms_count = 0
                                elif delay_msg > 0: 
                                    await asyncio.sleep(delay_msg)
                            
                            if count > 0:
                                chat_details[m_label] = count
                                chat_total += count
                    else:
                        # ✅ Parallel counting for Bulk Mode
                        tasks = []
                        labels = []
                        for m_label, m_filter in msg_filters:
                            tasks.append(client.search_messages_count(chat.id, filter=m_filter))
                            labels.append(m_label)
                        
                        counts = await asyncio.gather(*tasks, return_exceptions=True)
                        for label, count in zip(labels, counts):
                            if isinstance(count, int) and count > 0:
                                chat_details[label] = count
                                chat_total += count
                    
                    if chat_total > 0:
                        safe_title = getattr(chat, "title", None) or getattr(chat, "first_name", "Private")
                        
                        # Platform-Agnostic Hyperlink Generation
                        link = "#"
                        if getattr(chat, "username", None):
                            link = f"https://t.me/{chat.username}"
                        elif chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP, enums.ChatType.CHANNEL]:
                            if str(chat.id).startswith("-100"):
                                link = f"https://t.me/c/{str(chat.id)[4:]}/1"
                            else:
                                link = f"https://t.me/c/{str(chat.id).strip('-')}/1"
                        else:
                            link = f"tg://user?id={chat.id}"
                            
                        results.append({
                            "title": safe_title,
                            "chat_id": chat.id,
                            "link": link,
                            "total_count": chat_total,
                            "details": chat_details
                        })
                        total_count += chat_total
                    
                    batch_ch_count += 1 # Only increment for MATCHED chats
                    if delay_chat > 0: await asyncio.sleep(delay_chat)
                except FloodWait as fw:
                    await asyncio.sleep(fw.value + 1)
                except Exception: pass
            
            # Progress Update
            if chats_scanned % 10 == 0:
                took = round(time.time() - start_time, 2)
                try:
                    await status_msg.edit(
                        f"🔎 <b>Media Analysis in Progress...</b>\n\n"
                        f"• <b>Mode:</b> <code>{mode_str}</code>\n"
                        f"• <b>Scanned:</b> <code>{chats_scanned}</code> chats\n"
                        f"• <b>Matched:</b> <code>{chats_matched}</code> target chats\n"
                        f"• <b>Found:</b> <code>{total_count}</code> files\n"
                        f"• <b>Time:</b> <code>{took}s</code>"
                    )
                except Exception:
                    pass
                # Store progress for the inline 🔄 refresh button (manual click)
                # NOTE: ui_msg is always None for inline bot results (cb.message=None),
                # so we store progress unconditionally and let the user click 🔄 to refresh.
                progress_cb_data = f"ma_progress_{task_id}_{client.me.id}"
                progress_kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Refresh", callback_data=progress_cb_data)]
                ])
                if not hasattr(Altruix, "_MA_PROGRESS"):
                    Altruix._MA_PROGRESS = {}
                Altruix._MA_PROGRESS[task_id] = {
                    "text": (
                        f"🚀 <b>Scan In Progress...</b>\n\n"
                        f"<b>Settings:</b> <code>{scope_str.capitalize()}</code> / <code>{type_str}</code>\n"
                        f"<b>Task ID:</b> <code>{task_id}</code>\n\n"
                        f"<b>Progress:</b> Scanned <code>{chats_scanned}</code> chats\n"
                        f"<b>Matched:</b> <code>{chats_matched}</code> | <b>Found:</b> <code>{total_count}</code> files\n"
                        f"<b>Time:</b> <code>{took}s</code>\n\n"
                        f"<i>Use <code>.canceltask {task_id}</code> to abort.</i>"
                    ),
                    "kb": progress_kb
                }
                
            # Batch Chat Delay check
            if batch_size > 0 and batch_ch_count >= batch_size:
                if batch_delay > 0:
                    try:
                        await status_msg.edit(f"⏳ <b>Anti-Flood Pause</b>\n\nSleeping for <code>{fmt_time(batch_delay)}</code> due to Batch/Chat limit ({batch_size} chats).")
                    except Exception:
                        pass
                    await asyncio.sleep(batch_delay)
                batch_ch_count = 0
                
        # Final Detailed Pagination Payload
        results.sort(key=lambda x: x["total_count"], reverse=True)
        type_str = ", ".join([t.capitalize() for t in types_list])
        duration = round(time.time() - start_time, 2)
        
        # Save to global registry
        from Main.internals.settings_handlers.media_analyzer import save_ma_report_data
        save_ma_report_data(client.me.id, task_id, {
            "results": results,
            "scope_str": scope_str.capitalize(),
            "types_str": type_str,
            "took": duration
        })
        
        from Main.internals.settings_handlers.media_analyzer import generate_ma_report_page
        text, kb = generate_ma_report_page(client.me.id, task_id, page=1)
        
        text += f"━━━━━━━━━━━━━━━━━━\n⏱ <b>Time:</b> <code>{duration}s</code>"
        
        try:
            if getattr(status_msg, "from_user", None) and status_msg.from_user.is_bot:
                if kb:
                    await status_msg.edit(text, reply_markup=kb, disable_web_page_preview=True)
                else:
                    await status_msg.edit(text, disable_web_page_preview=True)
            else:
                await status_msg.edit(text, disable_web_page_preview=True)
        except Exception:
            pass
        
    except asyncio.CancelledError:
        duration = round(time.time() - start_time, 2)
        await status_msg.edit(
            f"🛑 <b>Media Analysis Cancelled</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Scanned:</b> <code>{chats_scanned}</code> chats\n"
            f"• <b>Found:</b> <code>{total_count}</code> files\n"
            f"• <b>Time:</b> <code>{duration}s</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>Task manually aborted via .canceltask</i>"
        )
        raise  # Bubble up to natively abort the asyncio.Task
    except Exception as e:
        Altruix.log(f"Media Scan Error: {e}")
        await status_msg.edit(f"❌ <b>Scan Error:</b> <code>{e}</code>")
    finally:
        if task_id:
            unregister_task(task_id)
            if hasattr(Altruix, "_MA_PROGRESS"):
                Altruix._MA_PROGRESS.pop(task_id, None)
