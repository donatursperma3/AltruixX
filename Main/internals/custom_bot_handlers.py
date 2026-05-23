import html
import asyncio
import logging
import traceback
from Main.core.client import Altruix
from pyrogram import Client, filters, enums
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from pyrogram.enums import ParseMode
from Main.core.decorators import log_errors, iuser_check
from Main.internals.settings_handlers.utils import (
    check_authorization, check_authorization_message, gt, send_log_notification, edit_cb
)
from Main.utils.file_helpers import get_user_button_style

# ====================== GLOBAL CUSTOM BOT MANAGER ======================
Altruix.log("🛠️ [CustomBot] Module custom_bot_handlers.py loaded.", level=logging.DEBUG)
@Altruix.bot.on_callback_query(filters.regex(r"^custom_bot_manager$"))
@iuser_check
@log_errors
async def custom_bot_manager_handler(c: Client, cb: CallbackQuery):
    """Global manager for all custom bots."""
    if not await check_authorization(cb): return
    await cb.answer()
    
    try:
        custom_bots = Altruix.bot_manager.custom_bots if hasattr(Altruix, 'bot_manager') else {}
        
        text = (
            f"<b>🤖 {gt('custom_bot_manager_title') or 'Custom Bot Manager'} (v1.6.0)</b>\n\n"
            f"Total Custom Bots: <code>{len(custom_bots)}</code>\n\n"
            f"Select a bot to manage locally or go to Sessions list for per-account setup:"
        )
        
        user_style = get_user_button_style(cb.from_user.id)
        
        buttons = []
        if custom_bots:
            for bot_id, bot_client in custom_bots.items():
                session_index = -1
                for idx, client in enumerate(Altruix.clients):
                    if getattr(client, "me", None) and client.me.id == bot_id:
                        session_index = idx
                        break
                
                name = f"Bot {bot_id}"
                try:
                    me = bot_client.me if hasattr(bot_client, "me") else None
                    if me:
                        name = f"Sess {session_index + 1 if session_index != -1 else '?'} | @{me.username}"
                except: pass
                
                if session_index != -1:
                    callback = f"custom_bot_menu_{session_index}_1_1"
                else:
                    callback = f"manage_custom_bot_{bot_id}" # Fallback
                    
                buttons.append([InlineKeyboardButton(name, callback, style=user_style)])
        else:
            text += f"\n\n<i>{gt('no_custom_bots') or 'No custom bots found.'}</i>"

        buttons.append([InlineKeyboardButton(gt("back"), "bot_controls_menu", style=user_style)])
        
        await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        Altruix.log(f"❌ [CustomBot] manager_handler error: {e}\n{traceback.format_exc()}", level=logging.ERROR)
        try: await cb.answer(f"❌ {str(e)[:100]}", show_alert=True)
        except: pass

@Altruix.bot.on_callback_query(filters.regex(r"^manage_custom_bot_(\d+)$"))
@iuser_check
@log_errors
async def manage_custom_bot_fallback_handler(c: Client, cb: CallbackQuery):
    """Fallback handler for bots not directly mapped to an active session list."""
    if not await check_authorization(cb): return
    await cb.answer()
    
    try:
        bot_id = int(cb.matches[0].group(1))
        
        custom_bots = Altruix.bot_manager.custom_bots if hasattr(Altruix, 'bot_manager') else {}
        bot_client = custom_bots.get(bot_id)
        
        if not bot_client:
            await cb.answer("Bot not found!", show_alert=True)
            return await custom_bot_manager_handler(c, cb)
            
        me = bot_client.me if hasattr(bot_client, "me") else None
        is_connected = getattr(bot_client, 'is_connected', False)
        
        name = me.first_name if me else f"Bot {bot_id}"
        username = f"@{me.username}" if me and me.username else "No Username"
        dc_id = getattr(me, 'dc_id', "N/A") if me else "N/A"
        status_text = "✅ Running" if is_connected else "❌ Stopped"
        
        text = (
            f"<b>⚙️ Manage Custom Bot (Standalone)</b>\n\n"
            f"• <b>Name:</b> {html.escape(name)}\n"
            f"• <b>Username:</b> {username}\n"
            f"• <b>ID:</b> <code>{bot_id}</code>\n"
            f"• <b>DC:</b> <code>{dc_id}</code>\n"
            f"• <b>Status:</b> {status_text}\n"
        )
        
        user_style = get_user_button_style(cb.from_user.id)

        buttons = [
            [
                InlineKeyboardButton("🛑 Stop Bot", f"action_custom_bot_stop_{bot_id}", style=user_style),
                InlineKeyboardButton(gt("delete_bot"), f"action_custom_bot_delete_{bot_id}", style=user_style)
            ],
            [InlineKeyboardButton(gt("back"), "custom_bot_manager", style=user_style)]
        ]
        
        await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
    except Exception as e:
        Altruix.log(f"❌ [CustomBot] fallback_handler error: {e}\n{traceback.format_exc()}", level=logging.ERROR)
        try: await cb.answer(f"❌ {str(e)[:100]}", show_alert=True)
        except: pass

# ====================== PER-SESSION CUSTOM BOT MENU ======================
@Altruix.bot.on_callback_query(filters.regex(r"^custom_bot_menu_(\d+)_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def custom_bot_menu_handler(c: Client, cb: CallbackQuery):
    """Handler for per-session custom bot menu with enhanced UI."""
    await cb.answer()
    
    try:
        index = int(cb.matches[0].group(1))
        page = int(cb.matches[0].group(2))
        button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
        
        if index >= len(Altruix.clients):
            await cb.answer(f"❌ Session {index+1} not found.", show_alert=True)
            return
        
        session_client = Altruix.clients[index]
        me = getattr(session_client, "myself", None) or getattr(session_client, "me", None)
        if not me:
            try:
                me = await session_client.get_me()
            except Exception:
                await cb.answer("❌ Session offline.", show_alert=True)
                return
        user_id = me.id
        
        has_custom_bot = user_id in Altruix.bot_manager.custom_bots
        bot_username = "None"
        status_text = gt("custom_bot_stopped")
        health_check = "N/A"
        
        if has_custom_bot:
            is_alive = await Altruix.bot_manager.is_bot_alive(user_id)
            bot = Altruix.bot_manager.get_bot(user_id)
            bot_username = f"@{bot.me.username}" if bot and bot.me else "Unknown"
            status_text = gt("custom_bot_running") if is_alive else gt("custom_bot_status_fail")
            health_check = gt("custom_bot_status_ok") if is_alive else gt("custom_bot_status_fail")

        txt = (
            f"{gt('custom_bot_list_title')}\n\n"
            f"👤 <b>Session:</b> <code>{index + 1}</code> ({html.escape(me.first_name or 'N/A')})\n"
            f"🤖 <b>Bot:</b> <code>{bot_username}</code>\n"
            f"⚡ <b>Status:</b> {status_text}\n"
            f"{gt('custom_bot_health_check').format(health_check)}\n\n"
            f"<blockquote expandable>{gt('custom_bot_help')}</blockquote>"
        )
        
        user_style = get_user_button_style(user_id)
        
        buttons = []
        if has_custom_bot:
            is_alive = await Altruix.bot_manager.is_bot_alive(user_id)
            if is_alive:
                buttons.append([InlineKeyboardButton("🛑 Stop Bot", f"custom_bot_stop_{index}_{page}_{button_page}", style=user_style)])
            else:
                buttons.append([InlineKeyboardButton("🚀 Start Bot", f"custom_bot_start_{index}_{page}_{button_page}", style=user_style)])
                
            buttons.append([
                InlineKeyboardButton(gt("custom_bot_test_conn"), f"custom_bot_test_{index}_{page}_{button_page}", style=user_style),
                InlineKeyboardButton(gt("custom_bot_update_token"), f"custom_bot_set_{index}_{page}_{button_page}", style=user_style)
            ])
            buttons.append([
                InlineKeyboardButton("ℹ️ Info", f"custom_bot_info_{index}_{page}_{button_page}", style=user_style),
                InlineKeyboardButton(gt("delete_bot"), f"custom_bot_remove_confirm_{index}_{page}_{button_page}", style=user_style)
            ])
        else:
            buttons.append([InlineKeyboardButton(gt("set_bot_token"), f"custom_bot_set_{index}_{page}_{button_page}", style=user_style)])
        
        buttons.append([InlineKeyboardButton(gt("back"), f"session_info_{index}_{page}_{button_page}", style=user_style)])
        
        await edit_cb(cb, txt, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
    except Exception as e:
        Altruix.log(f"❌ [CustomBot] custom_bot_menu_handler error: {e}\n{traceback.format_exc()}", level=logging.ERROR)
        try:
            await cb.answer(f"❌ Error: {str(e)[:100]}", show_alert=True)
        except: pass

@Altruix.bot.on_callback_query(filters.regex(r"^custom_bot_test_(\d+)_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def custom_bot_test_handler(c: Client, cb: CallbackQuery):
    """Test the connection of a custom bot with 'genius' feedback."""
    try:
        index = int(cb.matches[0].group(1))
        session_client = Altruix.clients[index]
        owner_id = session_client.me.id
        
        is_alive = await Altruix.bot_manager.is_bot_alive(owner_id)
        bot = Altruix.bot_manager.get_bot(owner_id)
        
        test_results = []
        success_all = True
        
        if is_alive and bot:
            try:
                me = bot.me or await bot.get_me()
                test_results.append(f"✅ <b>API Connection:</b> Active (@{me.username})")
            except Exception as e:
                test_results.append(f"❌ <b>API Connection:</b> Failed ({str(e)})")
                success_all = False

            try:
                await bot.send_message(
                    cb.from_user.id,
                    f"👋 <b>Connection Test Successful!</b>\n\n"
                    f"I am your <b>Custom Assistant</b> for Session <code>{index+1}</code>.\n"
                    f"I will handle distributed tasks to keep your main bot safe from flood limits."
                )
                test_results.append("✅ <b>Direct Message:</b> Sent successfully")
            except Exception as e:
                test_results.append(f"❌ <b>Direct Message:</b> Failed (User might need to start bot)")
                success_all = False

            if Altruix.log_chat:
                try:
                    await bot.send_message(
                        Altruix.log_chat,
                        f"📡 <b>Custom Bot Connection Test</b>\n"
                        f"• <b>Session:</b> <code>{index+1}</code>\n"
                        f"• <b>Bot:</b> @{me.username}\n"
                        f"• <b>Status:</b> Fully Functional ✅"
                    )
                    test_results.append("✅ <b>Log Notification:</b> Logged successfully")
                except Exception as e:
                    test_results.append(f"❌ <b>Log Notification:</b> Failed (Check permissions)")
                    success_all = False
            else:
                test_results.append("⚠️ <b>Log Notification:</b> Skipped (No Log Chat)")

            status_title = "<b>CONNECTION SUCCESSFUL</b> ✅" if success_all else "<b>CONNECTION PARTIAL</b> ⚠️"
            summary = "\n".join(test_results)
            
            await cb.answer(
                f"{status_title}\n\n{summary.replace('<b>', '').replace('</b>', '').replace('<code>', '').replace('</code>', '')}",
                show_alert=True
            )
        else:
            await cb.answer(
                "❌ CONNECTION FAILED\n\n"
                "• Bot is offline or token is invalid.\n"
                "• Please ensure you have pressed 'Start Bot' first.",
                show_alert=True
            )
        
        await custom_bot_menu_handler(c, cb)
    except Exception as e:
        Altruix.log(f"❌ [CustomBot] test_handler error: {e}\n{traceback.format_exc()}", level=logging.ERROR)
        try:
            await cb.answer(f"❌ Error: {str(e)[:100]}", show_alert=True)
        except: pass

@Altruix.bot.on_callback_query(filters.regex(r"^custom_bot_set_(\d+)_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def custom_bot_set_handler(c: Client, cb: CallbackQuery):
    """Set or update bot token."""
    await cb.answer()
    
    try:
        index = int(cb.matches[0].group(1))
        page = int(cb.matches[0].group(2))
        button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
        user_id = cb.from_user.id
        
        if index >= len(Altruix.clients):
            await cb.answer("❌ Session not found.", show_alert=True)
            return

        session_client = Altruix.clients[index]
        target_me = getattr(session_client, "me", None) or getattr(session_client, "myself", None)
        if not target_me:
            try:
                target_me = await session_client.get_me()
            except:
                target_me = None
                
        target_id = target_me.id if target_me else 0
        
        Altruix.user_env_manager_state[user_id] = {
            'action': 'custom_bot_token',
            'index': index,
            'page': page,
            'button_page': button_page
        }
        
        Altruix.log(f"✅ [CustomBot] State SET for user {user_id}: custom_bot_token for session {index+1}", level=20)
        
        user_style = get_user_button_style(target_id) if target_id else enums.ButtonStyle.PRIMARY
        
        await edit_cb(
            cb,
            f"<b>{gt('custom_bot_update_token')}</b>\n\n"
            f"Please send your Bot Token from @BotFather.\n\n"
            f"💡 <i>Tip: Make sure to turn off Privacy Mode in @BotFather if you want the bot to read all messages.</i>\n\n"
            f"<b>{gt('cancel')}:</b> Send <code>/cancel</code>",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(gt("cancel"), f"custom_bot_menu_{index}_{page}_{button_page}", style=user_style)
            ]]),
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        Altruix.log(f"❌ [CustomBot] set_handler error: {e}\n{traceback.format_exc()}", level=logging.ERROR)
        try:
            await cb.answer(f"❌ Error: {str(e)[:100]}", show_alert=True)
        except: pass

@Altruix.bot.on_callback_query(filters.regex(r"^custom_bot_stop_(\d+)_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def custom_bot_stop_handler(c: Client, cb: CallbackQuery):
    """Stop a running custom bot."""
    try:
        index = int(cb.matches[0].group(1))
        session_client = Altruix.clients[index]
        user_id = session_client.me.id
        
        await Altruix.bot_manager.stop_custom_bot(user_id)
        await send_log_notification(c, 'stop_custom_bot', index, cb.from_user, True, None, {'Session': index + 1})
        await cb.answer("✅ Bot stopped successfully!", show_alert=True)
        await custom_bot_menu_handler(c, cb)
    except Exception as e:
        Altruix.log(f"❌ [CustomBot] stop_handler error: {e}\n{traceback.format_exc()}", level=logging.ERROR)
        try: await cb.answer(f"❌ {str(e)[:100]}", show_alert=True)
        except: pass

@Altruix.bot.on_callback_query(filters.regex(r"^custom_bot_start_(\d+)_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def custom_bot_start_handler(c: Client, cb: CallbackQuery):
    """Start a stopped custom bot."""
    try:
        index = int(cb.matches[0].group(1))
        session_client = Altruix.clients[index]
        user_id = session_client.me.id
        # Get token from DB
        col = Altruix.db.make_collection("custom_bots")
        doc = await col.find_one({"_id": user_id})
        token = doc.get("token") if doc else None
        
        if not token:
            await cb.answer("❌ No token found! Please set bot token first.", show_alert=True)
            return
        
        success = await Altruix.bot_manager.start_custom_bot(user_id, token)
        
        if success:
            await send_log_notification(c, 'start_custom_bot', index, cb.from_user, True, None, {'Session': index + 1})
            await cb.answer("✅ Bot started successfully!", show_alert=True)
        else:
            await send_log_notification(c, 'start_custom_bot', index, cb.from_user, False, "Failed to start bot", {'Session': index + 1})
            await cb.answer("❌ Failed to start bot! Check your token.", show_alert=True)
        
        await custom_bot_menu_handler(c, cb)
    except Exception as e:
        Altruix.log(f"❌ [CustomBot] start_handler error: {e}\n{traceback.format_exc()}", level=logging.ERROR)
        try: await cb.answer(f"❌ {str(e)[:100]}", show_alert=True)
        except: pass

@Altruix.bot.on_callback_query(filters.regex(r"^custom_bot_remove_confirm_(\d+)_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def custom_bot_remove_confirm_handler(c: Client, cb: CallbackQuery):
    """Confirmation for removing bot."""
    await cb.answer()
    
    try:
        index = int(cb.matches[0].group(1))
        page = int(cb.matches[0].group(2))
        button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
        
        user_style = get_user_button_style(Altruix.clients[index].me.id)
        
        await edit_cb(
            cb,
            f"⚠️ <b>{gt('confirm_action')}</b>\n\n"
            f"Are you sure you want to remove the custom bot for <b>Session {index+1}</b>?\n"
            f"This will stop the bot and delete its token from the database.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(gt("yes"), f"custom_bot_remove_exec_{index}_{page}_{button_page}", style=user_style)],
                [InlineKeyboardButton(gt("no"), f"custom_bot_menu_{index}_{page}_{button_page}", style=user_style)]
            ]),
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        Altruix.log(f"❌ [CustomBot] remove_confirm_handler error: {e}\n{traceback.format_exc()}", level=logging.ERROR)
        try: await cb.answer(f"❌ {str(e)[:100]}", show_alert=True)
        except: pass

@Altruix.bot.on_callback_query(filters.regex(r"^custom_bot_remove_exec_(\d+)_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def custom_bot_remove_exec_handler(c: Client, cb: CallbackQuery):
    """Execute removal of custom bot."""
    
    index = int(cb.matches[0].group(1))
    session_client = Altruix.clients[index]
    user_id = session_client.me.id
    
    try:
        await Altruix.bot_manager.stop_custom_bot(user_id)
        await Altruix.bot_manager.delete_token(user_id)
        
        await cb.answer("✅ Custom bot removed successfully!", show_alert=True)
        await send_log_notification(c, 'remove_custom_bot', index, cb.from_user, True, None, {'Session': index + 1})
        await custom_bot_menu_handler(c, cb)
    except Exception as e:
        Altruix.log(f"❌ [CustomBot] remove_exec_handler error: {e}\n{traceback.format_exc()}", level=logging.ERROR)
        try: await cb.answer(f"❌ {str(e)[:100]}", show_alert=True)
        except: pass

@Altruix.bot.on_callback_query(filters.regex(r"^custom_bot_info_(\d+)_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def custom_bot_info_handler(c: Client, cb: CallbackQuery):
    """Handler for detailed bot info."""
    await cb.answer()
    
    try:
        index = int(cb.matches[0].group(1))
        page = int(cb.matches[0].group(2))
        button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
        
        session_client = Altruix.clients[index]
        user_id = session_client.me.id
        bot = Altruix.bot_manager.get_bot(user_id)
        
        if bot and bot.me:
            dc_id = getattr(bot.me, 'dc_id', "N/A")
            txt = (
                f"ℹ️ <b>Custom Bot Info</b>\n\n"
                f"🤖 <b>Username:</b> @{bot.me.username}\n"
                f"🆔 <b>Bot ID:</b> <code>{bot.me.id}</code>\n"
                f"🌐 <b>DC ID:</b> <code>{dc_id}</code>\n"
                f"📝 <b>First Name:</b> {html.escape(bot.me.first_name or 'N/A')}\n"
                f"✅ <b>Status:</b> Active"
            )
        else:
            txt = "❌ Bot info not available"
            
        user_style = get_user_button_style(Altruix.clients[index].me.id)
        
        await edit_cb(cb, txt, reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(gt("back"), f"custom_bot_menu_{index}_{page}_{button_page}", style=user_style)
            ]]), parse_mode=ParseMode.HTML)
    except Exception as e:
        Altruix.log(f"❌ [CustomBot] info_handler error: {e}\n{traceback.format_exc()}", level=logging.ERROR)
        try: await cb.answer(f"❌ {str(e)[:100]}", show_alert=True)
        except: pass

@Altruix.bot.on_callback_query(filters.regex(r"^action_custom_bot_stop_(\d+)$"))
@iuser_check
@log_errors
async def action_custom_bot_stop_handler(c: Client, cb: CallbackQuery):
    """Standalone stop handler for global manager."""
    try:
        bot_id = int(cb.matches[0].group(1))
        await Altruix.bot_manager.stop_custom_bot(bot_id)
        await cb.answer("✅ Bot stopped!", show_alert=True)
        await custom_bot_manager_handler(c, cb)
    except Exception as e:
        Altruix.log(f"❌ [CustomBot] action_stop error: {e}\n{traceback.format_exc()}", level=logging.ERROR)
        try: await cb.answer(f"❌ {str(e)[:100]}", show_alert=True)
        except: pass

@Altruix.bot.on_callback_query(filters.regex(r"^action_custom_bot_delete_(\d+)$"))
@iuser_check
@log_errors
async def action_custom_bot_delete_handler(c: Client, cb: CallbackQuery):
    """Standalone delete handler for global manager."""
    try:
        bot_id = int(cb.matches[0].group(1))
        await Altruix.bot_manager.stop_custom_bot(bot_id)
        await Altruix.bot_manager.delete_token(bot_id)
        await cb.answer("✅ Bot deleted!", show_alert=True)
        await custom_bot_manager_handler(c, cb)
    except Exception as e:
        Altruix.log(f"❌ [CustomBot] action_delete error: {e}\n{traceback.format_exc()}", level=logging.ERROR)
        try: await cb.answer(f"❌ {str(e)[:100]}", show_alert=True)
        except: pass

# ====================== CACHE LOG MENU HANDLER ======================
@Altruix.bot.on_callback_query(filters.regex(r"^cache_log_menu_(\d+)_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def cache_log_menu_handler(c: Client, cb: CallbackQuery):
    """Handler for cache log settings."""
    await cb.answer()
    
    try:
        index = int(cb.matches[0].group(1))
        page = int(cb.matches[0].group(2))
        button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
        
        cache_log_enabled = getattr(Altruix.config, "CACHE_LOG_ENABLED", True)
        status = "✅ Enabled" if cache_log_enabled else "❌ Disabled"
        
        txt = (
            f"<b>{gt('cache_log_menu')}</b>\n\n"
            f"📊 <b>Current Status:</b> {status}\n\n"
            f"<i>Toggle this setting to enable/disable cache cleaning notifications in the group log.</i>"
        )
        
        user_style = get_user_button_style(cb.from_user.id)
        
        toggle_text = "❌ Disable" if cache_log_enabled else "✅ Enable"
        
        buttons = [
            [InlineKeyboardButton(toggle_text, f"cache_log_toggle_{index}_{page}_{button_page}", style=user_style)],
            [InlineKeyboardButton(gt("back"), f"session_info_{index}_{page}_{button_page}", style=user_style)]
        ]
        
        await edit_cb(cb, txt, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
    except Exception as e:
        Altruix.log(f"❌ [CustomBot] cache_log_menu_handler error: {e}\n{traceback.format_exc()}", level=logging.ERROR)
        try: await cb.answer(f"❌ {str(e)[:100]}", show_alert=True)
        except: pass

@Altruix.bot.on_callback_query(filters.regex(r"^cache_log_toggle_(\d+)_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def cache_log_toggle_handler(c: Client, cb: CallbackQuery):
    """Handler for toggling cache log settings."""
    
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    try:
        current_status = getattr(Altruix.config, "CACHE_LOG_ENABLED", True)
        new_status = not current_status
        
        await Altruix.config.sync_env_to_db("CACHE_LOG_ENABLED", str(new_status), upsert=True)
        Altruix.config.CACHE_LOG_ENABLED = new_status
        
        status_text = "enabled" if new_status else "disabled"
        await cb.answer(f"✅ Cache log {status_text}!", show_alert=True)
        await cache_log_menu_handler(c, cb)
    except Exception as e:
        Altruix.log(f"❌ [CustomBot] cache_log_toggle_handler error: {e}\n{traceback.format_exc()}", level=logging.ERROR)
        try: await cb.answer(f"❌ {str(e)[:100]}", show_alert=True)
        except: pass

# ====================== HANDLE CUSTOM BOT TOKEN INPUT ======================
@Altruix.bot.on_message(filters.private, group=-100)
@log_errors
async def handle_custom_bot_token_input(c: Client, m: Message):
    """Robust handler for custom bot token input."""
    if not m.from_user:
        return await m.continue_propagation()
        
    user_id = m.from_user.id
    state = Altruix.user_env_manager_state.get(user_id)
    
    Altruix.log(f"🔎 [CustomBot] Group -1 Handler triggered for user {user_id}. State found: {bool(state)}", level=20)
    
    if not state or state.get('action') != 'custom_bot_token':
        return await m.continue_propagation()
        
    input_text = (m.text or m.caption or "").strip()
    Altruix.log(f"🔑 [CUSTOM-BOT] Received token input from {user_id} for session index {state.get('index')}", level=20)
    
    if input_text.lower() in ["/cancel", "cancel", "batal"]:
        del Altruix.user_env_manager_state[user_id]
        await m.reply(f"❌ {gt('operation_cancelled')}")
        return
    
    # Basic token validation
    if ":" not in input_text or len(input_text) < 20:
        await m.reply(gt('custom_bot_invalid_token'))
        return

    index = state['index']
    page = state['page']
    button_page = state.get('button_page', 1)
    
    if index >= len(Altruix.clients):
        await m.reply("❌ Session index out of range.")
        del Altruix.user_env_manager_state[user_id]
        return
        
    session_client = Altruix.clients[index]
    
    # Ensure me is available
    if not getattr(session_client, "me", None):
        try:
            Altruix.log(f"⏳ [CustomBot] Fetching identity for Session {index+1}...", level=20)
            session_client.me = await asyncio.wait_for(session_client.get_me(), timeout=10)
        except asyncio.TimeoutError:
            await m.reply("❌ Timeout fetching session info. Is the session connected?")
            return
        except Exception as e:
            await m.reply(f"❌ Failed to fetch session info: {str(e)}")
            return
            
    session_user_id = session_client.me.id
    
    status_msg = await m.reply(f"⏳ <code>Starting bot for Session {index+1}...</code>")
    
    try:
        # Start and save
        success = await Altruix.bot_manager.start_custom_bot(session_user_id, input_text)
        if success:
            await Altruix.bot_manager.save_token(session_user_id, input_text)
            bot_username = Altruix.bot_manager.get_bot_username(session_user_id)
            
            await status_msg.edit(
                f"<b>{gt('custom_bot_token_updated')}</b>\n\n"
                f"🤖 <b>Bot:</b> @{bot_username}\n"
                f"👤 <b>Session:</b> <code>{index+1}</code>",
                parse_mode=ParseMode.HTML
            )
            await send_log_notification(c, 'set_custom_bot', index, m.from_user, True, None, {'Bot': bot_username})
            del Altruix.user_env_manager_state[user_id]
        else:
            await status_msg.edit(gt('custom_bot_start_fail').format("Invalid token or API error."))
    except Exception as e:
        Altruix.log(f"❌ [CustomBot] token_input error: {e}\n{traceback.format_exc()}", level=logging.ERROR)
        try:
            await status_msg.edit(gt('custom_bot_start_fail').format(str(e)))
        except: pass
