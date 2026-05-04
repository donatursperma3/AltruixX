# Main/internals/settings_handlers/logger_handlers.py
import html
import os
import json
import asyncio
import logging
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton, LinkPreviewOptions
from Main.core.decorators import log_errors, iuser_check
from Main.core.client import Altruix
from Main.utils.file_helpers import get_db_path
from pyrogram.enums import ParseMode, ChatType
from pyrogram.errors import UserAlreadyParticipant, FloodWait
from Main.utils.essentials import Essentials

# States & Helpers
from .utils import edit_cb
# from .session_info import sessions_info_cb_handler

# Logger
logger = logging.getLogger(__name__)

from Main.utils.file_helpers import get_user_button_style
from .custom_alert_handlers import _get_session_user_id

@Altruix.bot.on_callback_query(filters.regex(r"^(pml|mnt|joinl|cmdl)_menu_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def logger_menu_handler(c: Client, cb: CallbackQuery):
    """General logger status menu with filter buttons if applicable."""
    log_type, index, page = cb.matches[0].group(1), int(cb.matches[0].group(2)), int(cb.matches[0].group(3))
    await cb.answer()
    
    # Resolve user_style
    user_id_key = _get_session_user_id(index)
    user_style = get_user_button_style(user_id_key)
    
    type_map = {"pml": "PM Logger", "mnt": "Mention Logger", "joinl": "Join Logger", "cmdl": "Command Logger"}
    base_key = log_type.upper()
    
    # 1. APPLY TYPE
    apply_type = await Altruix.config.get_env(f"{base_key}_LOGGER_APPLY_TYPE_{index}") or "global"
    apply_label = "Global" if apply_type == "global" else "Per-Account"
    
    # 2. STATUS
    if apply_type == "global":
        current = await Altruix.config.get_env(f"{base_key}_LOGGER_GLOBAL") or "off"
    else:
        current = await Altruix.config.get_env(f"{base_key}_LOGGER_{index}") or "off"
    status_emoji = "✅ ON" if current == "on" else "❌ OFF"
    
    # 3. REPLY BY (Only for PML and MNT)
    reply_by_txt = ""
    reply_buttons = []
    if log_type in ["pml", "mnt"]:
        if apply_type == "global":
            reply_by = await Altruix.config.get_env(f"{base_key}_REPLY_BY_GLOBAL") or "all"
        else:
            reply_by = await Altruix.config.get_env(f"{base_key}_REPLY_BY_{index}") or "all"
        
        reply_by_txt = f"• 🗣️ <b>Reply By:</b> <code>{reply_by.upper()}</code>\n"
        reply_buttons = [InlineKeyboardButton(await Essentials.get_user_button_style(user_id_key, f"🗣️ Reply: {reply_by.upper()}"), f"{log_type}_reply_{index}_{page}")]

    buttons = [
        [InlineKeyboardButton(await Essentials.get_user_button_style(user_id_key, f"Toggle {type_map[log_type]}: {status_emoji}"), f"{log_type}_toggle_{index}_{page}")],
    ]
    
    # Mode & Reply Buttons
    config_row = [InlineKeyboardButton(await Essentials.get_user_button_style(user_id_key, f"⚙️ Type: {apply_label}"), f"{log_type}_mode_{index}_{page}")]
    if reply_buttons:
        config_row.extend(reply_buttons)
    buttons.append(config_row)
    
    # Add advanced filter buttons for PM Logger and Mention Logger
    if log_type == "pml":
        buttons.append([InlineKeyboardButton(await Essentials.get_user_button_style(user_id_key, "🔍 PM Logger Filters"), f"pmlf_menu_user_{index}_{page}")])
        buttons.append([InlineKeyboardButton(await Essentials.get_user_button_style(user_id_key, "🗃️ Cache Manager"), f"pmlu_cache_menu_{user_id_key}")])
    elif log_type == "mnt":
        buttons.append([
            InlineKeyboardButton(await Essentials.get_user_button_style(user_id_key, "🔍 Mention Filters"), f"mntf_menu_{index}_{page}"),
            InlineKeyboardButton(await Essentials.get_user_button_style(user_id_key, "🔔 View Mentions"), f"view_mentions_menu_{index}_{page}")
        ])
        buttons.append([InlineKeyboardButton(await Essentials.get_user_button_style(user_id_key, "🗃️ Cache Manager"), f"mnt_cache_menu_{user_id_key}")])
        
        c_id = index
        buttons.append([InlineKeyboardButton(await Essentials.get_user_button_style(user_id_key, "🚫 Haters Detector Dashboard"), f"haters_menu_{user_id_key}")])
    
    # Add Bot Assist toggle for PML and MNT
    if log_type in ["pml", "mnt"]:
        bot_assist_enabled = False
        storage_file = get_db_path("pm_logger_bot_settings.json" if log_type == "pml" else "mentions_settings.json")
        if os.path.exists(storage_file):
            with open(storage_file, "r") as f:
                try:
                    b_data = json.load(f)
                    if log_type == "pml":
                        bot_assist_enabled = b_data.get("settings", {}).get("log_mode", "off") != "off"
                    else:
                        bot_assist_enabled = b_data.get("settings", {}).get("enabled", False)
                except: pass
        
        bot_assist_btn = "ON" if bot_assist_enabled else "OFF"
        buttons.append([InlineKeyboardButton(await Essentials.get_user_button_style(user_id_key, f"🤖 Bot Assist: {bot_assist_btn}"), f"{log_type}_botassist_{index}_{page}")])
        
    buttons.append([InlineKeyboardButton(await Essentials.get_user_button_style(user_id_key, "🔙 Back"), callback_data=f"session_info_{index}_{page}_3")]) # Fixed page return to 3 (Logs Page)
    
    await edit_cb(
        cb,
        f"<b>📊 {type_map[log_type]} Control</b>\n\n"
        f"• 🔌 <b>Status:</b> {status_emoji}\n"
        f"• ⚙️ <b>Apply Type:</b> <code>{apply_label}</code>\n"
        f"{reply_by_txt}\n"
        f"<i>Gunakan tombol di bawah untuk mengubah pengaturan.</i>",
        reply_markup=InlineKeyboardMarkup(buttons), 
        parse_mode=ParseMode.HTML
    )

@Altruix.bot.on_callback_query(filters.regex(r"^view_mnt_menu_(\d+)_(\d+)(_exec)?$"))
@iuser_check
@log_errors
async def view_mentions_menu_handler(c: Client, cb: CallbackQuery):
    """Hybrid mention search with confirmation and grid UI."""
    match = cb.matches[0]
    index, page = int(match.group(1)), int(match.group(2))
    is_exec = match.group(3) == "_exec"
    await cb.answer()

    # 1. Setup Session Client
    if index >= len(Altruix.clients): 
        Altruix.log(f"❌ [View Mentions] Index {index} out of bounds!", level=30, client=c)
        return
    session_client = Altruix.clients[index]
    
    # Get user style (emoji)
    # Note: me might not be loaded if disconnected, but we try anyway for style
    session_id = getattr(session_client.me, "id", 0) if getattr(session_client, "me", None) else 0
    user_style = get_user_button_style(session_id)

    # Fetch current limit
    limit_val = await Altruix.config.get_env(f"MENTIONS_LIMIT_{index}") or 200
    limit_val = int(limit_val)

    # 2. Confirmation Menu (if not executed yet)
    if not is_exec:
        confirm_text = (
            f"<b>🔔 View Mentions (Global Search)</b>\n\n"
            f"Account: <b>{html.escape(session_client.me.first_name if getattr(session_client, 'me', None) else 'Unknown')}</b>\n"
            f"Target Limit: <code>{limit_val}</code> dialogs\n\n"
            f"This will search for mentions across all group & channel chats. "
            f"Do you want to proceed?"
        )
        confirm_kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(await Essentials.get_user_button_style(session_id, "✅ Yes, Start Scan"), f"view_mnt_menu_{index}_{page}_exec", style=user_style),
                InlineKeyboardButton(await Essentials.get_user_button_style(session_id, "❌ No, Cancel"), f"session_info_{index}_{page}_2", style=user_style)
            ]
        ])

        return await edit_cb(cb, confirm_text, reply_markup=confirm_kb, parse_mode=ParseMode.HTML)

    # 3. Execution Phase
    Altruix.log(f"🛠 [View Mentions] Handler started for session index {index}", level=20, client=session_client)
    
    # ✅ UI Feedback
    await edit_cb(cb, "🔍 <b>Performing Health Check...</b>\n<i>Verifying session connectivity...</i>", parse_mode=ParseMode.HTML)

    Altruix.log("DEBUG: Checking connection status...", level=20, client=session_client)
    is_connected = getattr(session_client, "is_connected", False)
    Altruix.log(f"DEBUG: is_connected={is_connected}", level=20, client=session_client)
    
    # ✅ ACTIVE HEALTH CHECK: Force a ping even if connected=True
    # If the ping hangs, it's a dead session, so we force-restart it.
    try:
        Altruix.log("📡 [View Mentions] Performing Health Ping...", level=20, client=session_client)
        await asyncio.wait_for(session_client.get_me(), timeout=3)
        Altruix.log("✅ [View Mentions] Health Ping OK.", level=20, client=session_client)
    except (asyncio.TimeoutError, Exception) as e:
        Altruix.log(f"⚠️ [View Mentions] Health Ping FAILED (is_connected was {is_connected}): {e}. Forced Reworking...", level=30, client=session_client)
        try:
            # Stop safely ignoring errors
            try: await asyncio.wait_for(session_client.stop(), timeout=3)
            except: pass
            
            Altruix.log("🔌 [View Mentions] Restarting session...", level=20, client=session_client)
            await asyncio.wait_for(session_client.start(), timeout=10)
            Altruix.log("♻️ [View Mentions] Forced Restart Successful.", level=20, client=session_client)
        except Exception as re:
            Altruix.log(f"❌ [View Mentions] Forced Restart FAILED: {re}", level=40, client=session_client)
            return await cb.answer("❌ Session unreachable. Try refreshing session info.", show_alert=True)
        
    try:
        Altruix.log("⚙️ [View Mentions] Finalizing me...", level=20, client=session_client)
        me = await asyncio.wait_for(session_client.get_me(), timeout=5)
        Altruix.log(f"✅ [View Mentions] me resolved: {me.id}", level=20, client=session_client)
    except Exception as e:
        Altruix.log(f"❌ [View Mentions] Final get_me failed: {e}", level=40, client=session_client)
        return await cb.answer(f"❌ API unreachable: {str(e)}", show_alert=True)

    if me.is_bot:
        Altruix.log(f"🚫 [View Mentions] Blocked bot session usage", level=20, client=session_client)
        return await cb.answer("❌ Mentions are not logged for bot sessions.", show_alert=True)
        
    session_name = me.first_name
    session_id = me.id
    user_style = get_user_button_style(session_id)

    
    # Fetch current limit
    limit_val = await Altruix.config.get_env(f"MENTIONS_LIMIT_{index}") or 200
    limit_val = int(limit_val)
    
    await edit_cb(cb, f"🔍 <b>Searching for mentions across all chats...</b>\n<i>Limit: <code>{limit_val}</code> messages</i>", parse_mode=ParseMode.HTML)
    
    try:
        from pyrogram import enums
        mentions = []
        Altruix.log(f"📂 [View Mentions] Starting Hybrid Mention Scan (Limit: {limit_val})...", level=20, client=session_client)
        
        # 1. Fetch Dialogs (Phase 1: Quick Scan of top 10)
        await edit_cb(cb, f"🔍 <b>Starting Quick Scan...</b>\n<i>Checking top active chats...</i>", parse_mode=ParseMode.HTML)
        
        chats_to_scan = []
        scanned_dialogs = 0
        Altruix.log("📡 [View Mentions] Requesting first batch of dialogs...", level=20, client=session_client)
        
        try:
            # We use a smaller initial limit just to "wake up" the session and get progress moving
            async for dialog in session_client.get_dialogs(limit=20):
                scanned_dialogs += 1
                
                # Update UI for every dialog in Phase 1
                await edit_cb(cb, f"🔍 <b>Quick Scan in progress...</b>\n<i>Checking: {scanned_dialogs}/20</i>", parse_mode=ParseMode.HTML)
                
                # Prioritize chats
                if dialog.unread_mentions_count > 0 or scanned_dialogs <= 10:
                    if dialog.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL, ChatType.PRIVATE]:
                        chats_to_scan.append(dialog.chat.id)
                
                await asyncio.sleep(0.01) # Yield
                if len(chats_to_scan) >= 20: break

            # Phase 2: Deeper Scan if needed
            if limit_val > 20 and len(chats_to_scan) < 40:
                await edit_cb(cb, f"🔍 <b>Performing Deep Scan...</b>\n<i>Checking up to {limit_val} chats...</i>", parse_mode=ParseMode.HTML)
                async for dialog in session_client.get_dialogs(limit=limit_val):
                    # Skip already checked
                    scanned_dialogs += 1
                    if scanned_dialogs <= 20: continue
                    
                    if scanned_dialogs % 10 == 0:
                        await edit_cb(cb, f"🔍 <b>Deep Scan in progress...</b>\n<i>Processed: {scanned_dialogs}/{limit_val}</i>", parse_mode=ParseMode.HTML)
                    
                    if dialog.unread_mentions_count > 0:
                        if dialog.chat.id not in chats_to_scan:
                            chats_to_scan.append(dialog.chat.id)
                    
                    if scanned_dialogs >= limit_val: break
                    if len(chats_to_scan) >= 50: break
                    await asyncio.sleep(0.01)

        except Exception as de:
            Altruix.log(f"⚠️ [View Mentions] Dialog scan error: {de}", level=30, client=session_client)
            # If we don't have any chats to scan, we must stop
            if not chats_to_scan: raise de

        Altruix.log(f"🔍 [View Mentions] Identified {len(chats_to_scan)} chats to scan for specific mentions.", level=20, client=session_client)

        # 2. Scan identified chats
        for i, chat_id in enumerate(chats_to_scan, 1):
            # ✅ HIGH-FREQUENCY UI UPDATE: Update every chat so user knows exactly which one is being scanned.
            # Add a small delay to avoid "Edit Flood" from the bot if there are 50+ chats.
            await asyncio.sleep(0.1)
            await edit_cb(cb, f"🔍 <b>Fetching mentions...</b>\n<i>Checking chat {i}/{len(chats_to_scan)}</i>", parse_mode=ParseMode.HTML)
            
            try:
                # ✅ ADDED TIMEOUT: If search_messages hangs for more than 10s on a single chat, skip it.
                async with asyncio.timeout(10):
                    # Search inside this specific chat
                    async for m in session_client.search_messages(chat_id=chat_id, filter=enums.MessagesFilter.MENTION, limit=5):
                        mentions.append(m)
                        if len(mentions) >= 50: break # Collector limit
            except (asyncio.TimeoutError, Exception) as e:
                Altruix.log(f"⚠️ [View Mentions] Skipping chat {chat_id} due to timeout or error: {e}", level=20, client=session_client)
                continue
                
            if len(mentions) >= 50: break

        # 3. Final Sort
        mentions.sort(key=lambda x: x.date, reverse=True)
        mentions = mentions[:15] # UI Display Limit

        Altruix.log(f"🏁 [View Mentions] Finished search. Found {len(mentions)} matches.", level=20, client=session_client)
        
        if not mentions:
            Altruix.log("🔕 [View Mentions] No mentions found.", level=20, client=session_client)
            await cb.answer("🔕 No recent mentions found in your chats.", show_alert=True)
            from .session_info import get_session_info_data
            text, reply_markup = await get_session_info_data(index, page, 2)
            text = f"<b>🔕 No recent mentions found in any chat.</b>\n\n" + text
            return await edit_cb(cb, text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

        txt = f"<b>🔔 Recent Mentions (Global Search: {html.escape(session_name)})</b>\n\n"
        mention_buttons = []
        
        for i, m in enumerate(mentions, 1):
            date_str = m.date.strftime("%d/%m %H:%M")
            chat_title = m.chat.title or m.chat.first_name or "Unknown Chat"
            snippet = (m.text or m.caption or "[Media]")[:30].replace('\n', ' ')
            
            txt += f"{i}. <b>{html.escape(chat_title)}</b>\n   └ <code>{html.escape(snippet)}...</code> [<code>{date_str}</code>]\n"
            
            # Link generation
            if m.chat.username:
                link = f"https://t.me/{m.chat.username}/{m.id}"
            else:
                clean_id = str(m.chat.id).replace('-100', '')
                link = f"https://t.me/c/{clean_id}/{m.id}"
            
            mention_buttons.append(InlineKeyboardButton(await Essentials.get_user_button_style(session_id, f"Go to Mention #{i}"), url=link, style=user_style))

        # Chunk mention buttons into rows of 2
        buttons = []
        for j in range(0, len(mention_buttons), 2):
            buttons.append(mention_buttons[j:j+2])

        # Control Buttons (styled)
        buttons.append([InlineKeyboardButton(await Essentials.get_user_button_style(session_id, "⚙️ Set Limit"), f"set_scan_limit_{index}_{page}_mnt", style=user_style)])
        buttons.append([InlineKeyboardButton(await Essentials.get_user_button_style(session_id, "🔄 Refresh"), f"view_mnt_menu_{index}_{page}_exec", style=user_style)])
        buttons.append([InlineKeyboardButton(await Essentials.get_user_button_style(session_id, "🔙 Back"), f"session_info_{index}_{page}_2", style=user_style)])

        await edit_cb(cb, txt, reply_markup=InlineKeyboardMarkup(buttons))
        
    except Exception as e:
        await cb.answer(f"❌ Error: {str(e)}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^(pml|mnt|joinl|cmdl)_toggle_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def logger_toggle_handler(c: Client, cb: CallbackQuery):
    """Toggle logger status (on/off) respecting apply type"""
    log_type, index, page = cb.matches[0].group(1), int(cb.matches[0].group(2)), int(cb.matches[0].group(3))
    base_key = log_type.upper()
    
    apply_type = await Altruix.config.get_env(f"{base_key}_LOGGER_APPLY_TYPE_{index}") or "global"
    
    if apply_type == "global":
        key = f"{base_key}_LOGGER_GLOBAL"
    else:
        key = f"{base_key}_LOGGER_{index}"
        
    current = await Altruix.config.get_env(key) or "off"
    new_val = "off" if current == "on" else "on"
    
    await Altruix.config.sync_env_to_db(key, new_val, upsert=True)
    setattr(Altruix.config, key, new_val) 
    
    # ✅ SYNC TO JSON (For Userbot Loggers)
    if log_type in ["pml", "mnt", "cmdl"]:
        if log_type == "pml":
            filename = get_db_path('pm_logger_user_settings.json')
        elif log_type == "mnt":
            filename = get_db_path('mentions_settings.json')
        else:
            filename = get_db_path('cmd_logger_settings.json')

        if os.path.exists(filename):
            try:
                with open(filename, "r") as f: data = json.load(f)
                
                # PM Logger Sync
                if log_type == "pml":
                    sessions = data.get("settings", {}) or data.get("sessions", {})
                    # If global mode, sync root 'enabled'
                    if apply_type == "global":
                        data["enabled"] = (new_val == "on")
                        if "global_config" not in data: data["global_config"] = {}
                        data["global_config"]["enabled"] = (new_val == "on")
                    else:
                        me_id_str = str(Altruix.clients[index].me.id)
                        if me_id_str not in sessions: sessions[me_id_str] = {}
                        sessions[me_id_str]["enabled"] = (new_val == "on")
                        data["settings"] = sessions # Ensure back-sync
                
                # Mention Logger Sync
                elif log_type == "mnt": 
                    me_id_str = str(Altruix.clients[index].me.id)
                    if apply_type == "global":
                        if "global" not in data: data["global"] = {}
                        data["global"]["mention"] = (new_val == "on")
                    else:
                        if "settings" not in data: data["settings"] = {}
                        if me_id_str not in data["settings"]: data["settings"][me_id_str] = {}
                        # If it was a bool, convert to dict
                        if not isinstance(data["settings"][me_id_str], dict):
                             data["settings"][me_id_str] = {"mention": data["settings"][me_id_str]}
                        data["settings"][me_id_str]["mention"] = (new_val == "on")
                
                # Command Logger Sync
                elif log_type == "cmdl":
                    me_id_str = str(Altruix.clients[index].me.id)
                    if apply_type == "global":
                        if "global" not in data: data["global"] = {}
                        data["global"]["enabled"] = (new_val == "on")
                        data["enabled"] = (new_val == "on") # Legacy
                    else:
                        if "sessions" not in data: data["sessions"] = {}
                        if me_id_str not in data["sessions"]: data["sessions"][me_id_str] = {}
                        data["sessions"][me_id_str]["enabled"] = (new_val == "on")

                with open(filename, "w") as f: json.dump(data, f, indent=2)
            except Exception as e:
                logger.error(f"Failed to sync {log_type} toggle to JSON: {e}")

    await cb.answer(f"{log_type.upper()} Logger: {new_val.upper()}")
    await logger_menu_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^(pml|mnt|joinl|cmdl)_mode_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def logger_mode_handler(c: Client, cb: CallbackQuery):
    """Toggle Apply Type (Per-Account <-> Global)"""
    log_type, index, page = cb.matches[0].group(1), int(cb.matches[0].group(2)), int(cb.matches[0].group(3))
    base_key = log_type.upper()
    key = f"{base_key}_LOGGER_APPLY_TYPE_{index}"
    
    current = await Altruix.config.get_env(key) or "global"
    new_val = "global" if current == "per_account" else "per_account"
    
    await Altruix.config.sync_env_to_db(key, new_val, upsert=True)
    
    # ✅ SYNC APPLY TYPE TO JSON
    if log_type in ["pml", "mnt", "cmdl"]:
        if log_type == "pml":
            filename = get_db_path('pm_logger_user_settings.json')
        elif log_type == "mnt":
            filename = get_db_path('mentions_settings.json')
        else:
            filename = get_db_path('cmd_logger_settings.json')

        if os.path.exists(filename):
            try:
                with open(filename, "r") as f: data = json.load(f)
                if "apply_types" not in data: data["apply_types"] = {}
                me_id_str = str(Altruix.clients[index].me.id)
                data["apply_types"][me_id_str] = new_val
                with open(filename, "w") as f: json.dump(data, f, indent=2)
            except Exception as e:
                logger.error(f"Failed to sync {log_type} mode to JSON: {e}")

    await cb.answer(f"Apply Type: {new_val.upper()}")
    await logger_menu_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^(pml|mnt)_reply_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def logger_reply_handler(c: Client, cb: CallbackQuery):
    """Cycle Reply By modes: All -> Sudo -> User -> Owner"""
    log_type, index, page = cb.matches[0].group(1), int(cb.matches[0].group(2)), int(cb.matches[0].group(3))
    base_key = log_type.upper()
    
    apply_type = await Altruix.config.get_env(f"{base_key}_LOGGER_APPLY_TYPE_{index}") or "per_account"
    
    if apply_type == "global":
        key = f"{base_key}_REPLY_BY_GLOBAL"
    else:
        key = f"{base_key}_REPLY_BY_{index}"
        
    modes = ["all", "sudo", "user", "owner"]
    current = await Altruix.config.get_env(key) or "all"
    
    try:
        current_idx = modes.index(current)
        next_idx = (current_idx + 1) % len(modes)
        new_val = modes[next_idx]
    except ValueError:
        new_val = "all"
        
    await Altruix.config.sync_env_to_db(key, new_val, upsert=True)
    
    # ✅ SYNC REPLY MODE TO JSON
    if log_type in ["pml", "mnt"]:
        filename = get_db_path('pm_logger_user_settings.json' if log_type == 'pml' else 'mentions_settings.json')
        if os.path.exists(filename):
            try:
                with open(filename, "r") as f: data = json.load(f)
                # Both use 'reply_access_mode' key in root or settings
                data["reply_access_mode"] = new_val
                with open(filename, "w") as f: json.dump(data, f, indent=2)
            except Exception as e:
                logger.error(f"Failed to sync {log_type} reply mode to JSON: {e}")

    await cb.answer(f"Reply By: {new_val.upper()}")
    await logger_menu_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^(pml|mnt)_botassist_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def logger_botassist_handler(c: Client, cb: CallbackQuery):
    """Toggle Bot Assist globally from session menu"""
    log_type, index, page = cb.matches[0].group(1), int(cb.matches[0].group(2)), int(cb.matches[0].group(3))
    
    if log_type == "pml":
        bot_assist_enabled = False
        if os.path.exists(get_db_path("pm_logger_bot_settings.json")):
            with open(get_db_path("pm_logger_bot_settings.json"), "r") as f:
                b_data = json.load(f)
                bot_assist_enabled = b_data.get("settings", {}).get("log_mode", "off") != "off"
        
        new_val = "off" if bot_assist_enabled else "all"
        storage_path = get_db_path("pm_logger_bot_settings.json")
        if not os.path.exists(storage_path):
            data = {"settings": {"log_mode": new_val}}
        else:
            with open(storage_path, "r") as f: data = json.load(f)
            if "settings" not in data: data["settings"] = {}
            data["settings"]["log_mode"] = new_val
            
        with open(storage_path, "w") as f: json.dump(data, f, indent=2)
        status = "DISABLED" if new_val == "off" else "ENABLED"
    else:
        # mnt
        bot_assist_enabled = False
        storage_path = get_db_path("mentions_settings.json")
        if os.path.exists(storage_path):
            with open(storage_path, "r") as f:
                b_data = json.load(f)
                bot_assist_enabled = b_data.get("settings", {}).get("enabled", False)
        
        new_val = not bot_assist_enabled
        with open(storage_path, "r") as f: data = json.load(f)
        if "settings" not in data: data["settings"] = {}
        data["settings"]["enabled"] = new_val
        with open(storage_path, "w") as f: json.dump(data, f, indent=2)
        status = "ENABLED" if new_val else "DISABLED"
        
    await cb.answer(f"🤖 Bot Assist: {status}")
    await logger_menu_handler(c, cb)

# --- PM Logger Advanced Filters ---

@Altruix.bot.on_callback_query(filters.regex(r"^pmlf_menu_(user|bot)_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def pmlf_menu_handler(c: Client, cb: CallbackQuery):
    """PM Logger Filters Category Selection"""
    logger_type = cb.matches[0].group(1) # 'user' or 'bot'
    index = int(cb.matches[0].group(2))
    page = int(cb.matches[0].group(3))
    await cb.answer()
    
    # Resolve user_style
    user_id_key = _get_session_user_id(index)
    user_style = get_user_button_style(user_id_key)
    
    text = (
        f"<b>🔍 PM Logger Filters ({'Userbot Session'})</b>\n\n"
        "Pilih kategori di bawah untuk mengatur jenis pesan yang akan dicatat:\n\n"
        "👤 <b>User Filters:</b> Filter pesan dari pengguna (Text, Photo, Video, dll).\n"
        "🤖 <b>Bot Filters:</b> Filter pesan dari Bot (Menjaga kebersihan log group)."
    )
    buttons = [
        [
            InlineKeyboardButton(await Essentials.get_user_button_style(user_id_key, "👤 From User"), f"pmlfl_user_user_{index}_{page}"),
            InlineKeyboardButton(await Essentials.get_user_button_style(user_id_key, "🤖 From Bot"), f"pmlfl_user_bot_{index}_{page}"),
        ],
        [InlineKeyboardButton(await Essentials.get_user_button_style(user_id_key, "🔙 Back to PM Logger"), f"pml_menu_{index}_{page}")]
    ]
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

async def show_pmlf_list(c: Client, cb: CallbackQuery, logger_type: str, source: str, index: int, page: int):
    """
    Helper function to generate and display the message type filter list for PM Logger.
    Avoids ValueError by centralizing parameter handling.
    """
    filename = get_db_path("pm_logger_user_settings.json")
    user_id_str = str(Altruix.clients[index].me.id)
    source_key = f"from_{source}"
    
    filters_data = {}
    if os.path.exists(filename):
        with open(filename, "r") as f: 
            data = json.load(f)
        
        # Check apply_type to determine source of filters
        apply_type = data.get("apply_types", {}).get(user_id_str, "per_account")
        
        if apply_type == "global":
            filters_data = data.get("global_config", {}).get("filters", {}).get(source_key, {})
        else:
            sessions = data.get("sessions", {}) or data.get("settings", {})
            session_data = sessions.get(user_id_str, {})
            if isinstance(session_data, dict):
                filters_data = session_data.get("filters", {}).get(source_key, {})
    
    text = f"<b>🔍 {source.capitalize()} Filter (Session {index+1})</b>\n\nKlik untuk toggle (✅ = Log, ❌ = Ignore):"
    buttons = []
    row = []
    m_types = [
        "text", "photo", "video", "document", "audio", "voice", "sticker", "animation", 
        "video_note", "contact", "location", "venue", "game", "poll", "dice"
    ]
    # Mapping for localized keys
    type_map = {
        "text": "GP_BTN_TXT", "photo": "GP_BTN_IMG", "video": "GP_BTN_VID",
        "document": "GP_BTN_DOC", "audio": "GP_BTN_AUD", "voice": "GP_BTN_VN",
        "sticker": "GP_BTN_STK", "animation": "GP_BTN_GIF", "video_note": "GP_BTN_VNOTE",
        "contact": "GP_BTN_CONT", "location": "GP_BTN_LOC", "venue": "GP_BTN_VEN",
        "game": "GP_BTN_GAME", "poll": "GP_BTN_POLL", "dice": "GP_BTN_DICE"
    }

    # Resolve user_style
    from Main.utils.file_helpers import get_user_button_style
    user_id_key = str(Altruix.clients[index].me.id)
    user_style = get_user_button_style(int(user_id_key))

    for m_type in m_types:
        # Defaults: log everything except bot text (to avoid spam)
        default_val = False if (source == "bot" and m_type == "text") else True
        val = filters_data.get(m_type, default_val)
        status = "✅" if val else "❌"
        
        lbl_key = type_map.get(m_type)
        lbl = Altruix.get_string(lbl_key) or m_type.capitalize()
        
        row.append(InlineKeyboardButton(f"{status} {lbl}", f"pmlft_{logger_type}_{source}_{m_type}_{index}_{page}", style=user_style))
        if len(row) == 2:
            buttons.append(row)
            row = []
    
    if row: 
        buttons.append(row)
        
    buttons.append([InlineKeyboardButton(await Essentials.get_user_button_style(int(user_id_key), "🔙 Back"), f"pmlf_menu_{logger_type}_{index}_{page}")])
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlfl_(user|bot)_(user|bot)_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def pmlf_list_handler(c: Client, cb: CallbackQuery):
    """Handler for displaying the specific message type filters list."""
    logger_type = cb.matches[0].group(1)
    source = cb.matches[0].group(2)
    index = int(cb.matches[0].group(3))
    page = int(cb.matches[0].group(4))
    await cb.answer()
    await show_pmlf_list(c, cb, logger_type, source, index, page)

@Altruix.bot.on_callback_query(filters.regex(r"^pmlft_(user|bot)_(user|bot)_(.+)_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def pmlf_toggle_handler(c: Client, cb: CallbackQuery):
    """Toggle a specific filter in PM Logger"""
    logger_type, source, m_type, index, page = cb.matches[0].groups()
    index, page = int(index), int(page)
    user_id_str = str(Altruix.clients[index].me.id)
    source_key = f"from_{source}"
    filename = get_db_path("pm_logger_user_settings.json")
    
    data = {"sessions": {}}
    if os.path.exists(filename):
        with open(filename, "r") as f: data = json.load(f)
    
    # Determine apply_type
    apply_type = data.get("apply_types", {}).get(user_id_str, "per_account")
    
    if apply_type == "global":
        if "global_config" not in data: data["global_config"] = {}
        if "filters" not in data["global_config"]: data["global_config"]["filters"] = {}
        if source_key not in data["global_config"]["filters"]: data["global_config"]["filters"][source_key] = {}
        
        current = data["global_config"]["filters"][source_key].get(m_type, True)
        data["global_config"]["filters"][source_key][m_type] = not current
    else:
        if "sessions" not in data: data["sessions"] = data.pop("settings", {})
        if user_id_str not in data["sessions"]: data["sessions"][user_id_str] = {"filters": {}}
        
        # ✅ FIX: Handle legacy boolean session setting
        if not isinstance(data["sessions"][user_id_str], dict):
            data["sessions"][user_id_str] = {"enabled": bool(data["sessions"][user_id_str]), "filters": {}}

        if "filters" not in data["sessions"][user_id_str]:
            data["sessions"][user_id_str]["filters"] = {}
            
        if source_key not in data["sessions"][user_id_str]["filters"]:
            data["sessions"][user_id_str]["filters"][source_key] = {}
            
        current = data["sessions"][user_id_str]["filters"][source_key].get(m_type, True)
        data["sessions"][user_id_str]["filters"][source_key][m_type] = not current
    
    with open(filename, "w") as f: 
        json.dump(data, f, indent=2)
        
    await cb.answer(f"{m_type.capitalize()} {source}: {'ON' if not current else 'OFF'}")
    # Refresh menu using helper to avoid regex/indexing errors
    await show_pmlf_list(c, cb, logger_type, source, index, page)

# --- Mention Logger Advanced Filters ---

@Altruix.bot.on_callback_query(filters.regex(r"^mntf_menu_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def mntf_menu_handler(c: Client, cb: CallbackQuery):
    """Mention Logger Filters Category Selection"""
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    await cb.answer()
    
    # Resolve user_style
    user_id_key = _get_session_user_id(index)
    user_style = get_user_button_style(user_id_key)
    
    text = (
        f"<b>🔍 Mention Logger Filters (Sesi {index+1})</b>\n\n"
        "Pilih kategori di bawah untuk mengatur jenis pesan yang akan dicatat:\n\n"
        "👤 <b>User Filters:</b> Filter mention dari pengguna biasa.\n"
        "🤖 <b>Bot Filters:</b> Filter mention dari Bot/Robot."
    )
    buttons = [
        [
            InlineKeyboardButton(await Essentials.get_user_button_style(user_id_key, "👤 From User"), f"mntfl_user_{index}_{page}"),
            InlineKeyboardButton(await Essentials.get_user_button_style(user_id_key, "🤖 From Bot"), f"mntfl_bot_{index}_{page}"),
        ],
        [InlineKeyboardButton(await Essentials.get_user_button_style(user_id_key, "🔙 Back to Mention Logger"), f"mnt_menu_{index}_{page}")]
    ]
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

async def show_mntf_list(c: Client, cb: CallbackQuery, source: str, index: int, page: int):
    """Helper to show mention filter list for a specific source (user/bot)"""
    filename = get_db_path("mentions_settings.json")
    user_id_str = str(Altruix.clients[index].me.id)
    source_key = f"from_{source}"
    
    filters_data = {}
    if os.path.exists(filename):
        with open(filename, "r") as f: data = json.load(f)
        sessions = data.get("settings", {})
        session_data = sessions.get(user_id_str, {})
        filters_data = session_data.get("filters", {}).get(source_key, {})
    
    text = f"<b>🔍 Mention {source.capitalize()} Filter (Sesi {index+1})</b>\n\nKlik untuk toggle (✅ = Log, ❌ = Ignore):"
    buttons = []
    row = []
    m_types = [
        "text", "photo", "video", "document", "audio", "voice", "sticker", "animation", 
        "video_note", "contact", "location", "venue", "game", "poll", "dice"
    ]
    # Mapping for localized keys
    type_map = {
        "text": "GP_BTN_TXT", "photo": "GP_BTN_IMG", "video": "GP_BTN_VID",
        "document": "GP_BTN_DOC", "audio": "GP_BTN_AUD", "voice": "GP_BTN_VN",
        "sticker": "GP_BTN_STK", "animation": "GP_BTN_GIF", "video_note": "GP_BTN_VNOTE",
        "contact": "GP_BTN_CONT", "location": "GP_BTN_LOC", "venue": "GP_BTN_VEN",
        "game": "GP_BTN_GAME", "poll": "GP_BTN_POLL", "dice": "GP_BTN_DICE"
    }

    # Resolve user_style
    user_id_key = str(Altruix.clients[index].me.id)
    user_style = get_user_button_style(int(user_id_key))

    for m_type in m_types:
        # Default: log everything
        val = filters_data.get(m_type, True)
        status = "✅" if val else "❌"
        
        lbl_key = type_map.get(m_type)
        lbl = Altruix.get_string(lbl_key) or m_type.capitalize()
        
        row.append(InlineKeyboardButton(f"{status} {lbl}", f"mntft_{source}_{m_type}_{index}_{page}", style=user_style))
        if len(row) == 2:
            buttons.append(row); row = []
    if row: buttons.append(row)
    
    buttons.append([InlineKeyboardButton("🔙 Back", f"mntf_menu_{index}_{page}", style=user_style)])
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^mntfl_(user|bot)_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def mntfl_list_handler(c: Client, cb: CallbackQuery):
    """Handler for displaying the specific message type filters list for Mentions."""
    source, index, page = cb.matches[0].groups()
    await cb.answer()
    await show_mntf_list(c, cb, source, int(index), int(page))

@Altruix.bot.on_callback_query(filters.regex(r"^mntft_(user|bot)_(.+)_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def mntf_toggle_handler(c: Client, cb: CallbackQuery):
    """Toggle a specific filter in Mention Logger"""
    source, m_type, index, page = cb.matches[0].groups()
    index, page = int(index), int(page)
    user_id_str = str(Altruix.clients[index].me.id)
    source_key = f"from_{source}"
    filename = get_db_path("mentions_settings.json")
    
    data = {"settings": {}, "global": {}}
    if os.path.exists(filename):
        with open(filename, "r") as f: data = json.load(f)
    
    if "settings" not in data: data["settings"] = {}
    if user_id_str not in data["settings"]: data["settings"][user_id_str] = {}
    
    # ✅ FIX: Handle legacy boolean setting
    if not isinstance(data["settings"][user_id_str], dict):
        data["settings"][user_id_str] = {"mention": bool(data["settings"][user_id_str]), "filters": {}}

    if "filters" not in data["settings"][user_id_str]:
        data["settings"][user_id_str]["filters"] = {}
        
    if source_key not in data["settings"][user_id_str]["filters"]:
        data["settings"][user_id_str]["filters"][source_key] = {}
        
    current = data["settings"][user_id_str]["filters"][source_key].get(m_type, True)
    data["settings"][user_id_str]["filters"][source_key][m_type] = not current
    
    with open(filename, "w") as f: json.dump(data, f, indent=2)
    await cb.answer(f"MNT {source} {m_type.capitalize()} toggled")
    await show_mntf_list(c, cb, source, index, page)

# --- Join Log Group ---

@Altruix.bot.on_callback_query(filters.regex(r"^join_log_group_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def join_log_group_handler(c: Client, cb: CallbackQuery):
    """Invite session to log group and join"""
    index = int(cb.matches[0].group(1))
    # page = int(cb.matches[0].group(2)) if cb.matches[0].group(2) else 1 # Not strictly needed for logic but good for completeness if we add back button here
    await cb.answer("🔄 Processing join...", show_alert=False)
    
    if index >= len(Altruix.clients): return
    session_client = Altruix.clients[index]
    log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_USERS_ID))
    
    try:
        chat = await Altruix.bot.get_chat(log_chat_id)
        link = chat.invite_link
        if not link:
            invite = await Altruix.bot.create_chat_invite_link(log_chat_id, member_limit=1)
            link = invite.invite_link
            
        await session_client.join_chat(link)
        await cb.answer("✅ Successfully joined Log Group!", show_alert=True)
    except UserAlreadyParticipant:
        await cb.answer("ℹ️ Already in Log Group.", show_alert=True)
    except Exception as e:
        await cb.answer(f"❌ Join failed: {str(e)}", show_alert=True)

# --- Global Logger Menus (Bot Controls) ---

@Altruix.bot.on_callback_query(filters.regex(r"^(pmlb|mntlb|joinl|cbl)_menu$"))
@iuser_check
@log_errors
async def global_logger_menu_handler(c: Client, cb: CallbackQuery):
    """Global control menu for loggers from Bot Controls."""
    log_type = cb.matches[0].group(1).replace("_menu", "").replace("lb", "").replace("l", "")
    await cb.answer()
    
    type_map = {"pm": "PM Logger", "mnt": "Mention Logger", "join": "Join Logger", "cb": "Callback Logger"}
    base_key = log_type.upper()
    
    key = f"{base_key}_LOGGER_GLOBAL"
    current = await Altruix.config.get_env(key) or "off"
    
    # Resolve user_style (Global menu uses OWNER style)
    user_style = get_user_button_style(Altruix.config.OWNER_ID)
    
    # Special handling for Callback Logger (cb)
    if log_type == "cb":
        # Map old "on" to "all" for compatibility
        if current == "on": current = "all"
        
        status_text = {
            "all": "✅ ALL Users",
            "sudo": "🛡️ SUDO Only",
            "nonsudo": "👤 NON-SUDO Only",
            "off": "❌ OFF"
        }.get(current, "❌ OFF")
        
        buttons = [
            [
                InlineKeyboardButton(await Essentials.get_user_button_style(Altruix.config.OWNER_ID, f"{'✅ ' if current == 'all' else ''}All"), "global_cb_filter_all"),
                InlineKeyboardButton(await Essentials.get_user_button_style(Altruix.config.OWNER_ID, f"{'✅ ' if current == 'off' else ''}Off"), "global_cb_filter_off")
            ],
            [
                InlineKeyboardButton(await Essentials.get_user_button_style(Altruix.config.OWNER_ID, f"{'✅ ' if current == 'sudo' else ''}Sudo"), "global_cb_filter_sudo"),
                InlineKeyboardButton(await Essentials.get_user_button_style(Altruix.config.OWNER_ID, f"{'✅ ' if current == 'nonsudo' else ''}Non-Sudo"), "global_cb_filter_nonsudo")
            ],
            [InlineKeyboardButton(await Essentials.get_user_button_style(Altruix.config.OWNER_ID, "🔙 Back"), "bot_controls_menu")]
        ]
        
        await edit_cb(cb, 
            f"<b>📊 Global {type_map[log_type]} Control</b>\n\n"
            f"• 🔌 <b>Status Saat Ini:</b> {status_text}\n\n"
            f"💡 <b>Deskripsi:</b>\n"
            f"• <b>All:</b> Catat semua user.\n"
            f"• <b>Sudo:</b> Hanya catat sudo user.\n"
            f"• <b>Non-Sudo:</b> Hanya catat user biasa.\n"
            f"• <b>Off:</b> Matikan logging callback.\n",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )
        return

    status_emoji = "✅ ON" if current == "on" else "❌ OFF"
    
    buttons = [
        [InlineKeyboardButton(await Essentials.get_user_button_style(Altruix.config.OWNER_ID, f"Toggle Global {type_map[log_type]}: {status_emoji}"), f"global_{log_type}_toggle")],
        [InlineKeyboardButton(await Essentials.get_user_button_style(Altruix.config.OWNER_ID, "🔙 Back"), "bot_controls_menu")]
    ]
    
    await edit_cb(cb, 
        f"<b>📊 Global {type_map[log_type]} Control</b>\n\n"
        f"• 🔌 <b>Global Status:</b> {status_emoji}\n\n"
        f"<i>Aksi ini akan mempengaruhi semua sesi yang menggunakan mode Global.</i>",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )

@Altruix.bot.on_callback_query(filters.regex(r"^global_(pm|mnt|join|cb)_toggle$"))
@iuser_check
@log_errors
async def global_logger_toggle_handler(c: Client, cb: CallbackQuery):
    """Toggle global status for loggers."""
    log_type = cb.matches[0].group(1)
    key = f"{log_type.upper()}_LOGGER_GLOBAL"
    
    current = await Altruix.config.get_env(key) or "off"
    new_val = "off" if current == "on" else "on"
    
    await Altruix.config.sync_env_to_db(key, new_val, upsert=True)
    setattr(Altruix.config, key, new_val)
    
    # ✅ SYNC TO JSON: PM Logger Bot reads from JSON file, not DB ENV
    # Without this sync, toggling from Bot Controls has no effect on the actual bot logger
    if log_type == "pm":
        storage_path = get_db_path("pm_logger_bot_settings.json")
        try:
            if os.path.exists(storage_path):
                with open(storage_path, "r") as f: data = json.load(f)
            else:
                data = {"settings": {}}
            if "settings" not in data: data["settings"] = {}
            data["settings"]["log_mode"] = "all" if new_val == "on" else "off"
            with open(storage_path, "w") as f: json.dump(data, f, indent=2)
            logger.info(f"Global PM Toggle: Synced log_mode to JSON → {'all' if new_val == 'on' else 'off'}")
        except Exception as e:
            logger.error(f"Global PM Toggle: Failed to sync JSON: {e}")
    
    await cb.answer(f"Global {log_type.upper()} Logger: {new_val.upper()}")
    # Re-use the menu but we need a mock regex match or call it directly with adjustments
    # For simplicity, let's just create a mock with a manual type
    # ✅ FIX: Use *args in lambda to ignore implicit 'self' and return just the prefix
    cb.matches = [type('Mock', (object,), {'group': lambda *args: f"{log_type}lb"})()] 
    await global_logger_menu_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^get_log_group_link$"))
@iuser_check
@log_errors
async def get_log_group_link_handler(c: Client, cb: CallbackQuery):
    """Get or generate log group invite link."""
    await cb.answer("Generating link...")
    log_chat_id = int(os.getenv("LOG_CHAT_ID", Altruix.config.OWNER_USERS_ID))
    
    try:
        chat = await Altruix.bot.get_chat(log_chat_id)
        link = chat.invite_link
        if not link:
            invite = await Altruix.bot.create_chat_invite_link(log_chat_id)
            link = invite.invite_link
            
        user_style = get_user_button_style(Altruix.config.OWNER_ID)
        await edit_cb(cb, 
            f"<b>🔗 Log Group Link</b>\n\n<code>{link}</code>\n\n"
            f"<i>Gunakan link ini untuk memasukkan sesi lain ke Log Group secara manual atau bagikan ke Sudo user.</i>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(await Essentials.get_user_button_style(Altruix.config.OWNER_ID, "🔙 Back"), "bot_controls_menu")]]),
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        await cb.answer(f"❌ Error: {str(e)}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^global_cb_filter_(all|sudo|nonsudo|off)$"))
@iuser_check
@log_errors
async def callback_logger_filter_handler(c: Client, cb: CallbackQuery):
    """Handle filter selection for Callback Logger."""
    new_val = cb.matches[0].group(1)
    key = "CB_LOGGER_GLOBAL"
    
    await Altruix.config.sync_env_to_db(key, new_val, upsert=True)
    setattr(Altruix.config, key, new_val)
    
    await cb.answer(f"Callback Logger Filter: {new_val.upper()}")
    
    # Return to menu to update UI
    # Explicitly calling global_logger_menu_handler with mocked 'cb' match
    # Group 1 match should be "cb" as expected by global_logger_menu_handler regex (pmlb|mntlb|joinl|cbl) -> "cb"
    cb.matches = [type('Mock', (object,), {'group': lambda *args: "cbl"})()]
    await global_logger_menu_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^cb_logger_settings$"))
@iuser_check
@log_errors
async def cb_logger_settings_handler(c: Client, cb: CallbackQuery):
    """Special menu for Callback Logger."""
    # This is a bridge, for now just toggle like others
    # ✅ FIX: Use *args in lambda to ignore implicit 'self'
    cb.matches = [type('Mock', (object,), {'group': lambda *args: "cbl"})()]
    await global_logger_menu_handler(c, cb)

# --- Cache Cleaner Settings ---

@Altruix.bot.on_callback_query(filters.regex(r"^cache_cleaner_settings$"))
@iuser_check
@log_errors
async def cache_cleaner_settings_handler(c: Client, cb: CallbackQuery):
    """Display settings for Cache Cleaner log."""
    await cb.answer()
    
    # Get current status (default to False if not set)
    current_status = getattr(Altruix.config, "CACHE_LOG_ENABLED", False)
    # Handle stringified values if they exist
    if isinstance(current_status, str):
        current_status = current_status.lower() in ["on", "true", "yes"]
    
    status_emoji = "✅ ON" if current_status else "❌ OFF"
    user_style = get_user_button_style(Altruix.config.OWNER_ID)
    
    text = (
        "<b>♻️ Cache Cleaner Log Control</b>\n\n"
        f"• 🔌 <b>Status:</b> {status_emoji}\n\n"
        "💡 <b>Deskripsi:</b>\n"
        "Fitur ini mengirimkan notifikasi ke group log setiap kali bot membersihkan cache lama (Mention & PM Cache) secara otomatis.\n\n"
        "<i>Matikan jika Anda merasa pesan ini terlalu sering muncul (spammy).</i>"
    )
    
    buttons = [
        [InlineKeyboardButton(await Essentials.get_user_button_style(Altruix.config.OWNER_ID, f"Toggle Status: {status_emoji}"), "toggle_cache_cleaner_log")],
        [InlineKeyboardButton(await Essentials.get_user_button_style(Altruix.config.OWNER_ID, "🔙 Back"), "bot_controls_menu")]
    ]
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^toggle_cache_cleaner_log$"))
@iuser_check
@log_errors
async def toggle_cache_cleaner_log_handler(c: Client, cb: CallbackQuery):
    """Toggle the periodic cache cleanup log."""
    key = "CACHE_LOG_ENABLED"
    current = getattr(Altruix.config, key, False)
    
    if isinstance(current, str):
        current = current.lower() in ["on", "true", "yes"]
        
    new_val = not current
    
    # Sync to DB and Config object
    await Altruix.config.sync_env_to_db(key, new_val, upsert=True)
    setattr(Altruix.config, key, new_val)
    
    await cb.answer(f"Cache Cleaner Log: {'ENABLED' if new_val else 'DISABLED'}")
    await cache_cleaner_settings_handler(c, cb)
