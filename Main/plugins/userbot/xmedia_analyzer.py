# Main/plugins/userbot/xmedia_analyzer.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
# All rights reserved.

PLUGIN_VERSION = "0.0.472"

import time
import asyncio
import html
import json
from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import FloodWait, MessageNotModified

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
    from Main.plugins.userbot.xtaskmanager import unregister_task
    
    # 🎯 Log Group Tracking Delegation
    # Route live updates to the central Log Group via Bot Assistant.
    # Fallback to User's PM with Bot Assistant, then Userbot's Saved Messages if unavailable.
    try:
        log_chat_id = await Altruix.config.get_env("LOG_CHAT_ID")
        target_chat = None
        if log_chat_id:
            try: target_chat = int(log_chat_id)
            except ValueError: pass
            
        custom_bot = Altruix.bot_manager.get_bot(client.me.id) if hasattr(Altruix, 'bot_manager') else None
        main_bot = Altruix.bot
        
        status_msg = None
        successful_bot = None
        boot_text = f"🚀 <b>Media Analyzer Booting...</b>\n\n<i>Preparing deep scan engine. Task ID: {task_id}</i>"
        
        # Priority 1: Custom Bot -> Log Group
        if custom_bot and target_chat:
            try: 
                status_msg = await custom_bot.send_message(target_chat, boot_text)
                successful_bot = custom_bot
            except Exception: 
                Altruix.log(f"MA Live Log Error (Custom bot)", level=30)
                pass
            
        # Priority 2: Main Bot -> Log Group
        if not status_msg and main_bot and target_chat:
            try: 
                status_msg = await main_bot.send_message(target_chat, boot_text)
                successful_bot = main_bot
            except Exception: 
                Altruix.log(f"MA Live Log Error (Main bot)", level=30)
                pass
            
        # Priority 3: Custom Bot -> PM
        if not status_msg and custom_bot:
            try:
                status_msg = await custom_bot.send_message(client.me.id, boot_text)
                successful_bot = custom_bot
                if ui_msg:
                    try: await ui_msg.reply("⚠️ <b>Log Routing Warning:</b>\nThe Custom & Main bots are not in your Log Group. Logs routed to my PM!", quote=True)
                    except Exception: pass
            except Exception: pass
 
        # Priority 4: Main Bot -> PM
        if not status_msg and main_bot:
            try:
                status_msg = await main_bot.send_message(client.me.id, boot_text)
                successful_bot = main_bot
                if ui_msg:
                    try: 
                        await ui_msg.reply("⚠️ <b>Log Routing Warning:</b>\nThe Main Bot sent logs to my PM because Log Group is inaccessible.", quote=True)
                    except Exception: 
                        pass
            except Exception: 
                pass
                
        # Priority 5: Saved Messages
        if not status_msg:
            status_msg = await client.send_message("me", boot_text)
            successful_bot = client
    except Exception:
        status_msg = await client.send_message("me", f"🚀 <b>Media Analyzer Booting...</b>\n\n<i>Preparing deep scan engine. Task ID: {task_id}</i>")
        successful_bot = client
    
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
    
    report_mode = settings.get("report_log", "split")
    log_entries = [] # List of strings for split log
    live_log_msgs = {} # part_number -> Message object
    chats_per_part = 30
    
    def fmt_time(sec):
        m, s = divmod(int(sec), 60)
        return f"{m}m {s}s" if m and s else (f"{m}m" if m else f"{s}s")

    # Split Log Pacing
    last_log_update = 0
    LOG_UPDATE_COOLDOWN = 3.0 # Update at most every 3 seconds to avoid FloodWait

    async def _update_batch_log(is_final=False):
        nonlocal last_log_update
        if report_mode != "split" or not status_msg: return
        
        now = time.time()
        if not is_final and (now - last_log_update) < LOG_UPDATE_COOLDOWN:
            return
            
        last_log_update = now
        total_parts = max(1, (len(log_entries) + chats_per_part - 1) // chats_per_part)
        if len(log_entries) == 0: total_parts = 1

        for part in range(1, total_parts + 1):
            start_idx = (part - 1) * chats_per_part
            end_idx = start_idx + chats_per_part
            chunk_entries = log_entries[start_idx:end_idx]
            is_last_part = (part == total_parts)
            
            part_label = f" (Part {part})" if total_parts > 1 else ""
            header = (
                f"🔎 <b>Media Analysis Log — Task #{task_id}{part_label}</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"📊 <b>{chats_scanned}</b> scanned │ <b>{total_count}</b> files\n"
                f"━━━━━━━━━━━━━━━━━━\n"
            )
            
            body = "\n".join(chunk_entries) + "\n" if chunk_entries else ""
            status_line = "<b>Completed</b>" if is_final else "<i>Processing...</i>"
            if not is_last_part: status_line = "<i>Continued below...</i>"
            
            footer = f"━━━━━━━━━━━━━━━━━━\n{status_line}"
            full_text = f"<blockquote expandable>{header}{body}{footer}</blockquote>"
            
            try:
                reporting_bot = successful_bot or client
                target_chat_id = status_msg.chat.id
                
                if part in live_log_msgs and part == total_parts:
                    try: 
                        await live_log_msgs[part].edit_text(full_text, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
                    except MessageNotModified: pass
                    except FloodWait as fw:
                         # Respect FloodWait but don't stop the whole scan
                         await asyncio.sleep(fw.value + 1)
                elif part not in live_log_msgs:
                    msg = await reporting_bot.send_message(target_chat_id, full_text, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
                    live_log_msgs[part] = msg
            except Exception as e:
                Altruix.log(f"MA Live Log Error (Part {part}) [Bot: {getattr(reporting_bot, 'me', reporting_bot).id if hasattr(reporting_bot, 'me') else 'Userbot'}]: {e}", level=30)

    try:
        async for dialog in client.get_dialogs():
            chats_scanned += 1
            chat = dialog.chat
            chat_id = chat.id
            
            # 🚫 Blacklist Guard
            blacklist = settings.get("blacklist", [])
            if chat_id in blacklist:
                continue
                
            await asyncio.sleep(0.01) # Yield to other tasks
            
            # Filtering
            is_match = False
            if scope_str == "all": is_match = True
            elif scope_str == "bots":
                if chat.type == enums.ChatType.BOT:
                    is_match = True
                elif chat.type == enums.ChatType.PRIVATE:
                    # Fix: Pyrogram chat.type for bots can be BOT, but check username/name too if needed
                    if (chat.username and "bot" in chat.username.lower()) or (chat.first_name and "bot" in chat.first_name.lower()):
                        is_match = True
            elif target_types and chat.type in target_types:
                is_match = True
                
            if is_match:
                # 👑 Admin Filter Guard
                admin_filter = settings.get("admin_filter", "all")
                if admin_filter != "all" and chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP, enums.ChatType.CHANNEL]:
                    try:
                        # Pacing API calls to avoid FloodWait from Telegram
                        await asyncio.sleep(0.1)
                        me = await chat.get_member("me")
                        is_admin = me.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]
                        if admin_filter == "admin" and not is_admin: is_match = False
                        elif admin_filter == "non_admin" and is_admin: is_match = False
                    except Exception:
                        # If check fails, skip this chat if filter is 'admin' for safety
                        if admin_filter == "admin": is_match = False
            
            if is_match:
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
                                        try:
                                            await status_msg.edit(f"🔎 <b>Media Analysis Resumed...</b>\n\n<i>Processing chat:</i> <code>{getattr(chat, 'title', 'Private')}</code>")
                                        except Exception:
                                            pass
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

                    chats_matched += 1
                    if chat_total > 0:
                        results.append({
                            "title": safe_title,
                            "chat_id": chat.id,
                            "link": link,
                            "total_count": chat_total,
                            "details": chat_details,
                            "is_protected": getattr(chat, "has_protected_content", False)
                        })
                        total_count += chat_total
                    
                    # 📄 SPLIT LOG: Track results
                    if report_mode == "split":
                        icon = "✅" if chat_total > 0 else "⏭️"
                        trunc_title = safe_title[:15] + "..." if len(safe_title) > 15 else safe_title
                        log_entries.append(f"{icon} {chats_matched}. (<code>{chat.id}</code>) : <a href='{link}'>{html.escape(trunc_title)}</a> | <code>{chat_total}</code> files")
                        await _update_batch_log()

                    batch_ch_count += 1
                    if delay_chat > 0: await asyncio.sleep(delay_chat)
                except FloodWait as fw:
                    await asyncio.sleep(fw.value + 1)
                except Exception: pass
            
            # Progress Update (Standard Mode or Header Update)
            if chats_scanned % 10 == 0:
                took = round(time.time() - start_time, 2)
                if report_mode == "single":
                    try:
                        await status_msg.edit(
                            f"🔎 <b>Media Analysis in Progress...</b>\n\n"
                            f"• <b>Mode:</b> <code>{mode_str}</code>\n"
                            f"• <b>Scanned:</b> <code>{chats_scanned}</code> chats\n"
                            f"• <b>Matched:</b> <code>{chats_matched}</code> target chats\n"
                            f"• <b>Found:</b> <code>{total_count}</code> files\n"
                            f"• <b>Time:</b> <code>{took}s</code>"
                        )
                    except Exception: pass
                
                # Store progress for the inline 🔄 refresh button (manual click)
                # NOTE: ui_msg is always None for inline bot results (cb.message=None),
                # so we store progress unconditionally and let the user click 🔄 to refresh.
                progress_cb_data = f"ma_progress_{task_id}_{client.me.id}"
                progress_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh", callback_data=progress_cb_data)]])
                if not hasattr(Altruix, "_MA_PROGRESS"): Altruix._MA_PROGRESS = {}
                Altruix._MA_PROGRESS[task_id] = {
                    "text": (
                        f"🚀 <b>Scan In Progress...</b>\n\n"
                        f"<b>Settings:</b> <code>{scope_str.capitalize()}</code> / <code>{type_str}</code>\n"
                        f"<b>Task ID:</b> <code>{task_id}</code>\n\n"
                        f"<b>Progress:</b> Scanned <code>{chats_scanned}</code> chats\n"
                        f"<b>Matched:</b> <code>{chats_matched}</code> | <b>Found:</b> <code>{total_count}</code> files\n"
                        f"<b>Time:</b> <code>{took}s</code>\n\n"
                        f"<i>Use <code>.taskcancel {task_id}</code> to abort.</i>"
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
                    try:
                        await status_msg.edit(f"🔎 <b>Media Analysis Resumed...</b>\n\n<i>Moving to the next batch of chats...</i>")
                    except Exception:
                        pass
                batch_ch_count = 0
                
        # ✅ FINAL UPDATE for Split Mode
        if report_mode == "split":
            await _update_batch_log(is_final=True)
            
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
        
        # ✅ Logic: If Split/Single mode is selected, the report log group should remain static
        # The pagination UI is mainly for interactive sessions in PM/Dashboard
        if report_mode in ["split", "single"]:
             # Convert interactive text into a simple final summary for the log group
             text = (
                 f"✅ <b>Media Analysis Finished — Task #{task_id}</b>\n"
                 f"━━━━━━━━━━━━━━━━━━━━\n"
                 f"• <b>Scanned:</b> <code>{chats_scanned}</code> chats\n"
                 f"• <b>Matched:</b> <code>{chats_matched}</code> target chats\n"
                 f"• <b>Found:</b> <code>{total_count}</code> files\n"
                 f"• <b>Time:</b> <code>{duration}s</code>\n"
                 f"━━━━━━━━━━━━━━━━━━━━\n"
                 f"<i>Settings: {scope_str.capitalize()} / {type_str}</i>"
             )
             kb = None # No buttons for split/single log group message
        else:
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
            
        # ✅ FINAL UI UPDATE: Mark progress as finished on the dashboard
        if ui_msg:
            try:
                finished_ui_text = (
                    f"✅ <b>Media Analysis Finished!</b>\n\n"
                    f"<b>Task ID:</b> <code>{task_id}</code>\n"
                    f"<b>Duration:</b> <code>{duration}s</code>\n\n"
                    f"<b>Results:</b>\n"
                    f"• Scanned: <code>{chats_scanned}</code>\n"
                    f"• Matched: <code>{chats_matched}</code>\n"
                    f"• Files: <code>{total_count}</code>\n\n"
                    f"<i>Results saved. View logs in your Log Group.</i>"
                )
                await ui_msg.edit_text(finished_ui_text, reply_markup=None)
            except Exception: pass
        
    except asyncio.CancelledError:
        duration = round(time.time() - start_time, 2)
        await status_msg.edit(
            f"🛑 <b>Media Analysis Cancelled</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Scanned:</b> <code>{chats_scanned}</code> chats\n"
            f"• <b>Found:</b> <code>{total_count}</code> files\n"
            f"• <b>Time:</b> <code>{duration}s</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>Task manually aborted via .taskcancel</i>"
        )
        if ui_msg:
             try: await ui_msg.edit_text(f"🛑 <b>Scan Task #{task_id} Aborted.</b>", reply_markup=None)
             except Exception: pass
        raise  # Bubble up to natively abort the asyncio.Task
    except Exception as e:
        Altruix.log(f"Media Scan Error: {e}")
        await status_msg.edit(f"❌ <b>Scan Error:</b> <code>{e}</code>")
    finally:
        if task_id:
            unregister_task(task_id)
            if hasattr(Altruix, "_MA_PROGRESS"):
                Altruix._MA_PROGRESS.pop(task_id, None)
