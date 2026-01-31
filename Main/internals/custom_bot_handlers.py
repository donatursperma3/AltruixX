

import re
import glob
import asyncio
import contextlib
from Main import Altruix
from pyrogram import Client, filters, enums
from Main.core.decorators import log_errors
from pyrogram.types import (
    Message, ForceReply, CallbackQuery, KeyboardButton, ReplyKeyboardMarkup,
    ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup)
from pyrogram.enums import ParseMode
from Main.internals.settings import (
    check_authorization, check_authorization_message, gt, send_log_notification, user_env_manager_state
)

# ====================== CUSTOM BOT MENU HANDLER ======================
@Altruix.bot.on_callback_query(filters.regex(r"^custom_bot_menu_(\d+)_(\d+)$"))
@log_errors
async def custom_bot_menu_handler(c: Client, cb: CallbackQuery):
    """Handler untuk menu custom bot per session"""
    if not await check_authorization(cb): return
    await cb.answer()
    
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    
    # Check if custom bot exists for this session
    session_client = Altruix.clients[index]
    user_id = session_client.me.id
    
    has_custom_bot = user_id in Altruix.bot_manager.custom_bots
    bot_username = "Not Set"
    
    if has_custom_bot:
        bot = Altruix.bot_manager.get_bot(user_id)
        bot_username = bot.me.username if bot and bot.me else "Unknown"
    
    txt = (
        f"{gt('custom_bot_title')}\n\n"
        f"📊 <b>Session:</b> <code>{index + 1}</code>\n"
        f"🤖 <b>Bot Username:</b> <code>@{bot_username}</code>\n"
        f"✅ <b>Status:</b> {'Active' if has_custom_bot else 'Not Configured'}\n\n"
        f"<i>Configure custom assistant bot for this session to avoid flood waits during high concurrency.</i>"
    )
    
    buttons = []
    if has_custom_bot:
        buttons.append([InlineKeyboardButton("🗑️ Remove Bot", f"custom_bot_remove_{index}_{page}")])
        buttons.append([InlineKeyboardButton(gt("bot_info"), f"custom_bot_info_{index}_{page}")])
    else:
        buttons.append([InlineKeyboardButton(gt("set_bot_token"), f"custom_bot_set_{index}_{page}")])
    
    buttons.append([InlineKeyboardButton(gt("back"), f"session_info_{index}_{page}")])
    
    await cb.message.edit(
        text=txt,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )


@Altruix.bot.on_callback_query(filters.regex(r"^custom_bot_set_(\d+)_(\d+)$"))
@log_errors
async def custom_bot_set_handler(c: Client, cb: CallbackQuery):
    """Handler untuk set bot token"""
    if not await check_authorization(cb): return
    await cb.answer()
    
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    user_id = cb.from_user.id
    
    # Set state untuk menunggu input token
    user_env_manager_state[user_id] = {
        'action': 'custom_bot_token',
        'index': index,
        'page': page
    }
    
    await cb.message.edit(
        f"🔑 <b>Set Bot Token</b>\n\n"
        f"Please send the bot token from @BotFather.\n\n"
        f"<i>Reply to this message with the token.</i>",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(gt("cancel"), f"custom_bot_menu_{index}_{page}")
        ]]),
        parse_mode=ParseMode.HTML
    )


@Altruix.bot.on_callback_query(filters.regex(r"^custom_bot_remove_(\d+)_(\d+)$"))
@log_errors
async def custom_bot_remove_handler(c: Client, cb: CallbackQuery):
    """Handler untuk remove custom bot"""
    if not await check_authorization(cb): return
    
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    
    session_client = Altruix.clients[index]
    user_id = session_client.me.id
    
    try:
        await Altruix.bot_manager.stop_custom_bot(user_id)
        await Altruix.bot_manager.delete_token(user_id)
        
        await cb.answer("✅ Custom bot removed!", show_alert=True)
        
        # Log notification
        await send_log_notification(
            c, 'remove_custom_bot', index, cb.from_user,
            True, None, {'Session': index + 1}
        )
        
        # Return to menu
        await custom_bot_menu_handler(c, cb)
    except Exception as e:
        await cb.answer(f"❌ Error: {str(e)}", show_alert=True)
        await send_log_notification(
            c, 'remove_custom_bot', index, cb.from_user,
            False, str(e), {'Session': index + 1}
        )


@Altruix.bot.on_callback_query(filters.regex(r"^custom_bot_remove_confirm_(\d+)_(\d+)$"))
@log_errors
async def custom_bot_remove_confirm_handler(c: Client, cb: CallbackQuery):
    """Handler untuk execute remove custom bot setelah konfirmasi"""
    if not await check_authorization(cb): return
    
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    
    session_client = Altruix.clients[index]
    user_id = session_client.me.id
    
    try:
        await Altruix.bot_manager.stop_custom_bot(user_id)
        await Altruix.bot_manager.delete_token(user_id)
        
        await cb.answer("✅ Custom bot removed!", show_alert=True)
        
        # Log notification
        await send_log_notification(
            c, 'remove_custom_bot', index, cb.from_user,
            True, None, {'Session': index + 1}
        )
        
        # Return to menu
        await custom_bot_menu_handler(c, cb)
    except Exception as e:
        await cb.answer(f"❌ Error: {str(e)}", show_alert=True)
        await send_log_notification(
            c, 'remove_custom_bot', index, cb.from_user,
            False, str(e), {'Session': index + 1}
        )


@Altruix.bot.on_callback_query(filters.regex(r"^custom_bot_info_(\d+)_(\d+)$"))
@log_errors
async def custom_bot_info_handler(c: Client, cb: CallbackQuery):
    """Handler untuk info custom bot"""
    if not await check_authorization(cb): return
    await cb.answer()
    
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    
    session_client = Altruix.clients[index]
    user_id = session_client.me.id
    
    bot = Altruix.bot_manager.get_bot(user_id)
    
    if bot and bot.me:
        txt = (
            f"ℹ️ <b>Custom Bot Info</b>\n\n"
            f"🤖 <b>Username:</b> @{bot.me.username}\n"
            f"🆔 <b>Bot ID:</b> <code>{bot.me.id}</code>\n"
            f"📝 <b>First Name:</b> {bot.me.first_name}\n"
            f"✅ <b>Status:</b> Active"
        )
    else:
        txt = "❌ Bot info not available"
    
    await cb.message.edit(
        text=txt,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(gt("back"), f"custom_bot_menu_{index}_{page}")
        ]]),
        parse_mode=ParseMode.HTML
    )


# ====================== CACHE LOG MENU HANDLER ======================
@Altruix.bot.on_callback_query(filters.regex(r"^cache_log_menu_(\d+)_(\d+)$"))
@log_errors
async def cache_log_menu_handler(c: Client, cb: CallbackQuery):
    """Handler untuk menu cache log notification"""
    if not await check_authorization(cb): return
    await cb.answer()
    
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    
    # Get current status
    cache_log_enabled = getattr(Altruix.config, "CACHE_LOG_ENABLED", True)
    status = "✅ Enabled" if cache_log_enabled else "❌ Disabled"
    
    txt = (
        f"{gt('cache_log_title')}\n\n"
        f"📊 <b>Current Status:</b> {status}\n\n"
        f"{gt('cache_log_desc')}\n\n"
        f"<i>Toggle this setting to enable/disable cache cleaning notifications.</i>"
    )
    
    toggle_text = "❌ Disable" if cache_log_enabled else "✅ Enable"
    
    buttons = [
        [InlineKeyboardButton(toggle_text, f"cache_log_toggle_{index}_{page}")],
        [InlineKeyboardButton(gt("back"), f"session_info_{index}_{page}")]
    ]
    
    await cb.message.edit(
        text=txt,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )


@Altruix.bot.on_callback_query(filters.regex(r"^cache_log_toggle_(\d+)_(\d+)$"))
@log_errors
async def cache_log_toggle_handler(c: Client, cb: CallbackQuery):
    """Handler untuk toggle cache log notification"""
    if not await check_authorization(cb): return
    
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    
    try:
        # Get current status
        current_status = getattr(Altruix.config, "CACHE_LOG_ENABLED", True)
        new_status = not current_status
        
        # Save to database
        await Altruix.config.sync_env_to_db("CACHE_LOG_ENABLED", str(new_status), upsert=True)
        
        # Update in-memory config
        Altruix.config.CACHE_LOG_ENABLED = new_status
        
        status_text = "enabled" if new_status else "disabled"
        await cb.answer(f"✅ Cache log {status_text}!", show_alert=True)
        
        # Log notification
        await send_log_notification(
            c, 'toggle_cache_log', index, cb.from_user,
            True, None, {'Status': status_text}
        )
        
        # Return to menu
        await cache_log_menu_handler(c, cb)
    except Exception as e:
        await cb.answer(f"❌ Error: {str(e)}", show_alert=True)
        await send_log_notification(
            c, 'toggle_cache_log', index, cb.from_user,
            False, str(e), {}
        )


# ====================== HANDLE CUSTOM BOT TOKEN INPUT ======================
@Altruix.bot.on_message(~filters.bot & (filters.private | filters.group))
@log_errors
async def handle_custom_bot_token_input(c: Client, m: Message):
    """Handle user input for custom bot token"""
    if not m.from_user:
        return
        
    user_id = m.from_user.id
    
    if user_id not in user_env_manager_state:
        return
    
    state = user_env_manager_state[user_id]
    
    if state.get('action') != 'custom_bot_token':
        return

    if not m.text:
        return

    # Debug log
    Altruix.log(f"Handling potential bot token from {user_id}. Action: {state.get('action')}", level=20)

    # Optional cancel
    if m.text.lower().strip() in ["/cancel", "cancel", "batal"]:
        del user_env_manager_state[user_id]
        await m.reply("❌ Input token dibatalkan.")
        return

    # In groups, we MUST require a reply to our "Set Bot Token" message to avoid spam
    if m.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        if not m.reply_to_message or "Set Bot Token" not in m.reply_to_message.text:
            return
    # In PM, we can be more lenient but still check if it looks like a token if not a reply
    else:
        # If it's a PM but not a reply, we only process if it looks like a token (contains ':')
        if not m.reply_to_message or "Set Bot Token" not in m.reply_to_message.text:
            if ":" not in m.text:
                return # Likely not a token, maybe user just talking to bot

    # Check authorization
    if not await check_authorization_message(m):
        await m.reply("❌ Unauthorized")
        return
    
    index = state['index']
    page = state['page']
    token = m.text.strip()
    
    # Validate token format (basic)
    if ":" not in token:
        await m.reply("❌ Invalid token format. Please send a valid bot token from @BotFather.")
        return
    
    status_msg = await m.reply("⏳ Starting custom bot...")
    
    try:
        session_client = Altruix.clients[index]
        user_id_session = session_client.me.id
        
        # Start custom bot
        success = await Altruix.bot_manager.start_custom_bot(user_id_session, token)
        
        if success:
            # Save token to database
            await Altruix.bot_manager.save_token(user_id_session, token)
            
            bot_username = Altruix.bot_manager.get_bot_username(user_id_session)
            
            await status_msg.edit(
                f"✅ <b>Custom bot started successfully!</b>\n\n"
                f"🤖 <b>Bot:</b> @{bot_username}\n"
                f"📊 <b>Session:</b> <code>{index + 1}</code>",
                parse_mode=ParseMode.HTML
            )
            
            # Log notification
            await send_log_notification(
                c, 'set_custom_bot', index, m.from_user,
                True, None, {'Session': index + 1, 'Bot': bot_username}
            )
            
            # Delete instruction message
            try:
                await m.reply_to_message.delete()
            except:
                pass
        else:
            await status_msg.edit("❌ Failed to start custom bot. Please check the token and try again.")
            
    except Exception as e:
        await status_msg.edit(f"❌ <b>Error:</b> {str(e)}", parse_mode=ParseMode.HTML)
        await send_log_notification(
            c, 'set_custom_bot', index, m.from_user,
            False, str(e), {'Session': index + 1}
        )
    
    # Cleanup state
    del user_env_manager_state[user_id]
