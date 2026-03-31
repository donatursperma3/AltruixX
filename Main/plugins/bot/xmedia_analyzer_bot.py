# Main/plugins/bot/xmedia_analyzer_bot.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
# All rights reserved.

import re
from pyrogram import Client, filters, enums
from pyrogram.types import CallbackQuery, InlineQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
from Main import Altruix
from Main.core.decorators import log_errors, iuser_check
from Main.internals.settings_handlers.media_analyzer import (
    get_ma_settings, save_ma_settings, get_ma_status_text, 
    get_ma_kb, get_ma_submenu_kb, get_ma_filter_submenu_text,
    get_ma_filter_submenu_kb, get_ma_batch_submenu_text,
    get_ma_batch_submenu_kb, SCOPE_LIST, TYPE_LIST
)

@Altruix.bot.on_callback_query(filters.regex(r"^ma_"))
@iuser_check
@log_errors
async def ma_callback_handler(client: Client, cb: CallbackQuery):
    """Callback handler for Media Analyzer Dashboard."""
    data = cb.data
    user_id = cb.from_user.id
    
    # Auto-click loopback handler (runs BEFORE auth guard)
    # Triggered by Userbot's request_callback_answer — cb.from_user is the Userbot, not the owner
    if data.startswith("ma_progress_"):
        parts = data.split("_")
        # ma_progress_{task_id}_{user_id}
        p_task_id = parts[2] if len(parts) > 2 else None
        
        if p_task_id and hasattr(Altruix, "_MA_PROGRESS") and p_task_id in Altruix._MA_PROGRESS:
            prog = Altruix._MA_PROGRESS[p_task_id]
            try:
                await cb.edit_message_text(
                    prog["text"],
                    reply_markup=prog.get("kb")
                )
            except Exception:
                pass
        await cb.answer()
        return
    
    # Security check: Each button has the target user_id in it
    # Format: ma_action_uid_12345
    match_uid = re.search(r"_(\d+)$", data)
    if not match_uid:
        return await cb.answer("❌ Invalid callback format.")
    
    target_uid = int(match_uid.group(1))
    if user_id != target_uid:
        return await cb.answer("⚠️ Not authorized for this session.", show_alert=True)

    settings = await get_ma_settings(user_id)
    
    # 🎯 Actions
    if data.startswith("ma_refresh"):
        text = await get_ma_status_text(user_id)
        kb = get_ma_kb(user_id, settings)
        await cb.edit_message_text(text, reply_markup=kb)
        await cb.answer("Dashboard Refreshed 🔄")

    elif data.startswith("ma_cycle_scope"):
        idx = SCOPE_LIST.index(settings["scope"])
        settings["scope"] = SCOPE_LIST[(idx + 1) % len(SCOPE_LIST)]
        await save_ma_settings(user_id, settings)
        text = await get_ma_status_text(user_id)
        kb = get_ma_kb(user_id, settings)
        await cb.edit_message_text(text, reply_markup=kb)
        await cb.answer(f"Scope: {settings['scope'].capitalize()}")

    elif data.startswith("ma_filtermenu"):
        text = get_ma_filter_submenu_text(settings)
        kb = get_ma_filter_submenu_kb(user_id, settings)
        await cb.edit_message_text(text, reply_markup=kb)

    elif data.startswith("ma_filter_"):
        f_type = data.split("_")[2]
        f_list = settings.get("type", ["all"])
        
        if f_type == "all":
            f_list = ["all"]
        else:
            if "all" in f_list:
                f_list.remove("all")
            
            if f_type in f_list:
                f_list.remove(f_type)
            else:
                f_list.append(f_type)
                
            if not f_list:
                f_list = ["all"]
                
        settings["type"] = f_list
        await save_ma_settings(user_id, settings)
        
        text = get_ma_filter_submenu_text(settings)
        kb = get_ma_filter_submenu_kb(user_id, settings)
        await cb.edit_message_text(text, reply_markup=kb)

    elif data.startswith("ma_menu_dchat"):
        text = "⏱ <b>Adjust Delay per Chat</b>\nChoose a slow pace to stay safe."
        kb = get_ma_submenu_kb(user_id, settings, "dchat")
        await cb.edit_message_text(text, reply_markup=kb)

    elif data.startswith("ma_menu_dmsg"):
        text = "⏳ <b>Adjust Delay per Message</b>\nEnabling this activates Stealth Mode."
        kb = get_ma_submenu_kb(user_id, settings, "dmsg")
        await cb.edit_message_text(text, reply_markup=kb)
        
    elif data.startswith("ma_menu_batch"):
        text = get_ma_batch_submenu_text()
        kb = get_ma_batch_submenu_kb(user_id, settings)
        await cb.edit_message_text(text, reply_markup=kb)

    # 🔢 Submenu Settings
    elif data.startswith("ma_set_dchat"):
        if "_p1_" in data: settings["delay_chat"] += 1.0
        elif "_m1_" in data: settings["delay_chat"] = max(0.0, settings["delay_chat"] - 1.0)
        await save_ma_settings(user_id, settings)
        kb = get_ma_submenu_kb(user_id, settings, "dchat")
        await cb.edit_message_reply_markup(reply_markup=kb)

    elif data.startswith("ma_set_dmsg"):
        if "_p05_" in data: settings["delay_msg"] += 0.5
        elif "_m05_" in data: settings["delay_msg"] = max(0.0, settings["delay_msg"] - 0.5)
        await save_ma_settings(user_id, settings)
        kb = get_ma_submenu_kb(user_id, settings, "dmsg")
        await cb.edit_message_reply_markup(reply_markup=kb)

    elif data.startswith("ma_set_batch_"):
        if "_p5_" in data: settings["batch_size"] += 5
        elif "_m5_" in data: settings["batch_size"] = max(1, settings["batch_size"] - 5)
        await save_ma_settings(user_id, settings)
        kb = get_ma_batch_submenu_kb(user_id, settings)
        await cb.edit_message_reply_markup(reply_markup=kb)

    elif data.startswith("ma_set_bdelay_"):
        if "_p60_" in data: settings["batch_delay"] += 60.0
        elif "_m60_" in data: settings["batch_delay"] = max(0.0, settings["batch_delay"] - 60.0)
        elif "_p5_" in data: settings["batch_delay"] += 5.0
        elif "_m5_" in data: settings["batch_delay"] = max(0.0, settings["batch_delay"] - 5.0)
        await save_ma_settings(user_id, settings)
        kb = get_ma_batch_submenu_kb(user_id, settings)
        await cb.edit_message_reply_markup(reply_markup=kb)

    elif data.startswith("ma_set_bmsg_"):
        if "_p10_" in data: settings["batch_msg_size"] += 10
        elif "_m10_" in data: settings["batch_msg_size"] = max(1, settings["batch_msg_size"] - 10)
        await save_ma_settings(user_id, settings)
        kb = get_ma_batch_submenu_kb(user_id, settings)
        await cb.edit_message_reply_markup(reply_markup=kb)

    elif data.startswith("ma_set_bmdelay_"):
        if "_p60_" in data: settings["batch_msg_delay"] += 60.0
        elif "_m60_" in data: settings["batch_msg_delay"] = max(0.0, settings["batch_msg_delay"] - 60.0)
        elif "_p5_" in data: settings["batch_msg_delay"] += 5.0
        elif "_m5_" in data: settings["batch_msg_delay"] = max(0.0, settings["batch_msg_delay"] - 5.0)
        await save_ma_settings(user_id, settings)
        kb = get_ma_batch_submenu_kb(user_id, settings)
        await cb.edit_message_reply_markup(reply_markup=kb)

    elif data.startswith("ma_toggleadmin_"):
        curr = settings.get("admin_filter", "all")
        if curr == "all": settings["admin_filter"] = "admin"
        elif curr == "admin": settings["admin_filter"] = "non_admin"
        else: settings["admin_filter"] = "all"
        
        await save_ma_settings(user_id, settings)
        await cb.answer(f"👑 Admin Filter: {settings['admin_filter'].upper()}")
        
        text = await get_ma_status_text(user_id)
        kb = get_ma_kb(user_id, settings)
        await cb.edit_message_text(text, reply_markup=kb)

    elif data.startswith("ma_bl_list_") or data.startswith("ma_bl_page_"):
        page = 0
        if "page_" in data:
            page = int(data.split("_")[3])
        
        from Main.internals.settings_handlers.media_analyzer import get_ma_bl_text, get_ma_bl_kb
        text = await get_ma_bl_text(client, settings, page)
        kb = get_ma_bl_kb(user_id, settings, page)
        await cb.edit_message_text(text, reply_markup=kb, disable_web_page_preview=True)

    elif data.startswith("ma_bl_rem_"):
        parts = data.split("_")
        target_cid = int(parts[3])
        if target_cid in settings.get("blacklist", []):
            settings["blacklist"].remove(target_cid)
            await save_ma_settings(user_id, settings)
            await cb.answer(f"✅ Removed {target_cid} from blacklist.")
            
        from Main.internals.settings_handlers.media_analyzer import get_ma_bl_text, get_ma_bl_kb
        text = await get_ma_bl_text(client, settings, 0)
        kb = get_ma_bl_kb(user_id, settings, 0)
        await cb.edit_message_text(text, reply_markup=kb, disable_web_page_preview=True)

    elif data.startswith("ma_bl_addchat_"):
        # Prompt for chat ID via LOG chat or fallback to PM
        try:
            log_chat_id = await Altruix.config.get_env("LOG_CHAT_ID")
            target_chat = None
            if log_chat_id:
                try: target_chat = int(log_chat_id)
                except ValueError: pass
            
            bot = (Altruix.bot_manager.get_bot(user_id) if hasattr(Altruix, 'bot_manager') else None) or Altruix.bot
            prompt_text = (
                "<b>➕ Add Chat to Media Analyzer Blacklist</b>\n\n"
                "Reply to this message with the <b>Chat ID</b> or <b>@username</b> you want to exclude from analysis.\n\n"
                "<i>Example: -1001234567890 or @groupname</i>"
            )
            prompt_kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", f"ma_bl_canceladd_{user_id}")
            ]])
            
            sent = None
            if target_chat:
                try:
                    sent = await bot.send_message(target_chat, prompt_text, reply_markup=prompt_kb)
                except Exception:
                    pass
            
            # Fallback to PM if LOG_CHAT_ID invalid (PEER_ID_INVALID) or not configured
            if not sent:
                target_chat = cb.from_user.id
                sent = await bot.send_message(target_chat, prompt_text, reply_markup=prompt_kb)
            
            # Store state for the message handler
            if not hasattr(Altruix, "_MA_STATE"): Altruix._MA_STATE = {}
            Altruix._MA_STATE[f"addbl_{user_id}"] = {
                "prompt_id": sent.id,
                "chat_id": target_chat,
                "bot_id": bot.me.id if hasattr(bot, 'me') and bot.me else None
            }
            
            if target_chat == cb.from_user.id:
                await cb.answer("👉 Check your bot's Private Messages for the input prompt!", show_alert=True)
            else:
                await cb.answer("👉 Check your Log Group for the input prompt!", show_alert=True)
        except Exception as e:
            await cb.answer(f"❌ Error: {e}", show_alert=True)

    elif data.startswith("ma_bl_canceladd_"):
        if hasattr(Altruix, "_MA_STATE"):
            state = Altruix._MA_STATE.pop(f"addbl_{user_id}", None)
            if state:
                try:
                    bot = (Altruix.bot_manager.get_bot(user_id) if hasattr(Altruix, 'bot_manager') else None) or Altruix.bot
                    await bot.delete_messages(state["chat_id"], state["prompt_id"])
                except: pass
        await cb.answer("❌ Add chat cancelled.")

    elif data.startswith("ma_page_"):
        parts = data.split("_")
        task_id = parts[2]
        page = int(parts[3])
        
        from Main.internals.settings_handlers.media_analyzer import generate_ma_report_page
        text, kb = generate_ma_report_page(user_id, task_id, page)
        
        if kb:
            await cb.edit_message_text(text, reply_markup=kb, disable_web_page_preview=True)
        else:
            await cb.edit_message_text(text, disable_web_page_preview=True)

    elif data.startswith("ma_close"):
        await cb.message.delete()

    elif data.startswith("ma_start"):
        # Trigger Userbot scan
        await cb.answer("🚀 Scan triggered! Check your userbot chat.", show_alert=True)
        
        # Dispatch to Userbot
        # Find the correct userbot client
        u_client = None
        for cl in Altruix.clients:
            if cl.me and cl.me.id == user_id:
                u_client = cl
                break
        
        if u_client:
            from Main.plugins.userbot.xtaskmanager import register_task, generate_task_id
            from Main.plugins.userbot.xmedia_analyzer import perform_media_scan
            
            task_id = generate_task_id("MA")
            
            f_list = settings.get("type", ["all"])
            type_str = ", ".join([t.capitalize() for t in f_list])
            
            progress_cb_data = f"ma_progress_{task_id}_{user_id}"
            progress_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄", callback_data=progress_cb_data)]
            ])
            await cb.edit_message_text(
                f"🚀 <b>Scan Initiated...</b>\n\n"
                f"<b>Settings:</b> <code>{settings['scope'].capitalize()}</code> / <code>{type_str}</code>\n"
                f"<b>Task ID:</b> <code>{task_id}</code>\n\n"
                f"👉 <i>Open your <b>Log Group</b> (or Bot PM) to view the detailed tracking report!</i>\n"
                f"<i>Use <code>.canceltask {task_id}</code> anywhere to safely abort.</i>",
                reply_markup=progress_kb
            )
            
            # Dispatch as an asyncio.Task and register it
            task = asyncio.create_task(perform_media_scan(u_client, cb.message, settings, task_id, ui_msg=cb.message))
            register_task(
                task_id=task_id, 
                asyncio_task=task, 
                name=f"Media Analyzer ({settings['scope'].capitalize()})", 
                plugin="xmedia_analyzer", 
                user_id=user_id, 
                details=f"Types: {type_str}"
            )
        else:
            await cb.edit_message_text("❌ <b>Error:</b> Userbot session not found.")

@Altruix.bot.on_inline_query(filters.regex(r"^ma_menu_uid_(\d+)$"))
@iuser_check
@log_errors
async def ma_inline_menu_handler(client: Client, iq: InlineQuery):
    """Inline query handler for opening the Media Analyzer dashboard."""
    user_id = int(iq.matches[0].group(1))
    
    # Authorized user check
    if iq.from_user.id != user_id:
        return

    settings = await get_ma_settings(user_id)
    text = await get_ma_status_text(user_id)
    kb = get_ma_kb(user_id, settings)
    
    from pyrogram.types import InlineQueryResultArticle, InputTextMessageContent
    await iq.answer([
        InlineQueryResultArticle(
            title="Open Media Analyzer Dashboard",
            input_message_content=InputTextMessageContent(text, parse_mode=enums.ParseMode.HTML),
            reply_markup=kb,
            thumb_url="https://img.icons8.com/color/96/combo-chart.png"
        )
    ], cache_time=0)

@Altruix.bot.on_message(~filters.bot & ~filters.channel, group=60)
@iuser_check
@log_errors
async def ma_bl_add_input_handler(client: Client, message: Message):
    """Processes Chat ID / Username input for Media Analyzer Blacklist."""
    if not message.from_user: return
    
    user_id = message.from_user.id
    state_key = f"addbl_{user_id}"
    
    if not hasattr(Altruix, "_MA_STATE") or state_key not in Altruix._MA_STATE:
        return
        
    state = Altruix._MA_STATE.get(state_key)
    # Validate it's a reply to our prompt
    if not message.reply_to_message or message.reply_to_message.id != state["prompt_id"]:
        return

    user_input = (message.text or "").strip()
    if not user_input: return
    
    if user_input.lower() in ["/cancel", "cancel"]:
        Altruix._MA_STATE.pop(state_key, None)
        try: await client.delete_messages(state["chat_id"], [state["prompt_id"], message.id])
        except: pass
        return

    from Main.internals.settings_handlers.media_analyzer import get_ma_settings, save_ma_settings
    settings = await get_ma_settings(user_id)
    
    # Resolve input
    resolved_id = None
    resolved_name = "Unknown"
    
    try:
        # Pacing
        await asyncio.sleep(0.1)
        # Try finding via correct userbot client for better access
        u_client = next((cl for cl in Altruix.clients if cl.me and cl.me.id == user_id), client)
        
        if user_input.lstrip("-").isdigit():
            chat = await u_client.get_chat(int(user_input))
        else:
            chat = await u_client.get_chat(user_input)
            
        resolved_id = chat.id
        resolved_name = chat.title or chat.first_name or user_input
    except Exception as e:
        # Fallback for manual ID entry if resolver fails
        if user_input.lstrip("-").isdigit():
            resolved_id = int(user_input)
            resolved_name = f"Chat {resolved_id}"
        else:
            await message.reply(f"❌ <b>Error:</b> Could not resolve <code>{user_input}</code>.\n\n<code>{e}</code>")
            return

    if resolved_id in settings.get("blacklist", []):
        await message.reply(f"⚠️ <code>{resolved_id}</code> is already in the blacklist.")
    else:
        settings["blacklist"].append(resolved_id)
        await save_ma_settings(user_id, settings)
        await message.reply(f"✅ <b>Added to Blacklist:</b>\n• {resolved_name} (<code>{resolved_id}</code>)")

    # Cleanup state
    Altruix._MA_STATE.pop(state_key, None)
    try: await client.delete_messages(state["chat_id"], [state["prompt_id"]])
    except: pass
