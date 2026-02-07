

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
    check_authorization, check_authorization_message, gt, send_log_notification
)

# ====================== CUSTOM BOT MENU HANDLER ======================
@Altruix.bot.on_callback_query(filters.regex(r"^custom_bot_menu_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def custom_bot_menu_handler(c: Client, cb: CallbackQuery):
    """Handler untuk menu custom bot per session"""
    if not await check_authorization(cb): return
    await cb.answer()
    
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
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
        buttons.append([InlineKeyboardButton("🗑️ Remove Bot", f"custom_bot_remove_{index}_{page}_{button_page}")])
        buttons.append([InlineKeyboardButton(gt("bot_info"), f"custom_bot_info_{index}_{page}_{button_page}")])
    else:
        buttons.append([InlineKeyboardButton(gt("set_bot_token"), f"custom_bot_set_{index}_{page}_{button_page}")])
    
    buttons.append([InlineKeyboardButton(gt("back"), f"session_info_{index}_{page}_{button_page}")])
    
    await cb.message.edit(
        text=txt,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )


@Altruix.bot.on_callback_query(filters.regex(r"^custom_bot_set_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def custom_bot_set_handler(c: Client, cb: CallbackQuery):
    """Handler untuk set bot token"""
    if not await check_authorization(cb): return
    await cb.answer()
    
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    user_id = cb.from_user.id
    
    # Set state untuk menunggu input token
    Altruix.user_env_manager_state[user_id] = {
        'action': 'custom_bot_token',
        'index': index,
        'page': page,
        'button_page': button_page
    }
    Altruix.log(f"DEBUG: Set custom_bot_token state for {user_id}. Keys in Altruix.state: {list(Altruix.user_env_manager_state.keys())}", level=20)
    
    await cb.message.edit(
        f"🔑 <b>Set Bot Token</b>\n\n"
        f"Please send the bot token from @BotFather.\n\n"
        f"<i>Reply to this message with the token.</i>",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(gt("cancel"), f"custom_bot_menu_{index}_{page}_{button_page}")
        ]]),
        parse_mode=ParseMode.HTML
    )


@Altruix.bot.on_callback_query(filters.regex(r"^custom_bot_remove_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def custom_bot_remove_handler(c: Client, cb: CallbackQuery):
    """Handler untuk remove custom bot"""
    if not await check_authorization(cb): return
    
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
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


@Altruix.bot.on_callback_query(filters.regex(r"^custom_bot_remove_confirm_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def custom_bot_remove_confirm_handler(c: Client, cb: CallbackQuery):
    """Handler untuk execute remove custom bot setelah konfirmasi"""
    if not await check_authorization(cb): return
    
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
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


@Altruix.bot.on_callback_query(filters.regex(r"^custom_bot_info_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def custom_bot_info_handler(c: Client, cb: CallbackQuery):
    """Handler untuk info custom bot"""
    if not await check_authorization(cb): return
    await cb.answer()
    
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
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
            InlineKeyboardButton(gt("back"), f"custom_bot_menu_{index}_{page}_{button_page}")
        ]]),
        parse_mode=ParseMode.HTML
    )


# ====================== CACHE LOG MENU HANDLER ======================
@Altruix.bot.on_callback_query(filters.regex(r"^cache_log_menu_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def cache_log_menu_handler(c: Client, cb: CallbackQuery):
    """Handler untuk menu cache log notification"""
    if not await check_authorization(cb): return
    await cb.answer()
    
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
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
        [InlineKeyboardButton(toggle_text, f"cache_log_toggle_{index}_{page}_{button_page}")],
        [InlineKeyboardButton(gt("back"), f"session_info_{index}_{page}_{button_page}")]
    ]
    
    await cb.message.edit(
        text=txt,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )


@Altruix.bot.on_callback_query(filters.regex(r"^cache_log_toggle_(\d+)_(\d+)(?:_(\d+))?$"))
@log_errors
async def cache_log_toggle_handler(c: Client, cb: CallbackQuery):
    """Handler untuk toggle cache log notification"""
    if not await check_authorization(cb): return
    
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
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
@Altruix.bot.on_message(~filters.bot & (filters.private | filters.group), group=-1)
@log_errors
async def handle_custom_bot_token_input(c: Client, m: Message):
    """Handle user input for custom bot token"""
    if not m.from_user:
        return
        
    user_id = m.from_user.id
    
    # Use State from Altruix client to ensure consistency
    state_dict = Altruix.user_env_manager_state
    
    Altruix.log(f"DEBUG: Message from {user_id}. State keys: {list(state_dict.keys())}", level=20)

    if user_id not in state_dict:
        return
    
    state = state_dict[user_id]
    Altruix.log(f"DEBUG: User {user_id} in state. Action: {state.get('action')}, Message attributes: text={bool(m.text)}, caption={bool(m.caption)}, media={m.media}", level=20)
    
    if state.get('action') != 'custom_bot_token':
        return
    
    # Correct way to stop propagation in Pyrogram
    from pyrogram import StopPropagation
    
    try:
        if not m.text and not m.caption:
            Altruix.log(f"DEBUG: Returning because no text or caption from {user_id}", level=20)
            return

        # Use caption if text is missing (e.g. if token sent with a photo)
        input_text = m.text or m.caption
        
        # Debug log
        Altruix.log(f"Handling potential bot token from {user_id}. input_text: {input_text[:10]}...", level=20)

        # Optional cancel
        if input_text.lower().strip() in ["/cancel", "cancel", "batal"]:
            if user_id in Altruix.user_env_manager_state:
                del Altruix.user_env_manager_state[user_id]
            await m.reply("❌ Input token dibatalkan.")
            raise StopPropagation

        # In groups, we MUST require a reply to our "Set Bot Token" message to avoid spam
        if m.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
            if not m.reply_to_message or "Set Bot Token" not in m.reply_to_message.text:
                # Just ignore if not a reply in groups, to avoid interfering with normal conversation
                m.continue_propagation()
                return # This return is fine as it's within the try block and allows propagation to continue if not handled here.
        # In PM, we should be more proactive but still check if it's likely a token
        else:
            # If it's a PM but not a reply, we check if it looks like a token
            if not m.reply_to_message or "Set Bot Token" not in m.reply_to_message.text:
                Altruix.log(f"DEBUG: PM logic - Not a reply or trigger text missing", level=20)
                if ":" not in input_text:
                    Altruix.log(f"DEBUG: PM logic - No ':' in text, returning error", level=20)
                    await m.reply("❌ Format token tidak valid. Token harus berisi karakter ':'.\nKetik `/cancel` untuk membatalkan.")
                    raise StopPropagation

        Altruix.log(f"DEBUG: Reached authorization check for {user_id}", level=20)
        # Check authorization
        if not await check_authorization_message(m):
            Altruix.log(f"DEBUG: Authorization failed for {user_id}", level=20)
            await m.reply("❌ Unauthorized")
            raise StopPropagation
        
        Altruix.log(f"DEBUG: Authorized. Preparing to start bot for index {state.get('index')}", level=20)
        index = state['index']
        page = state['page']
        button_page = state.get('button_page', 1)
        token = input_text.strip()
        
        # Validate token format (basic)
        if ":" not in token:
            Altruix.log(f"DEBUG: Final token validation failed (no ':') for {user_id}", level=20)
            await m.reply("❌ Invalid token format. Please send a valid bot token from @BotFather.")
            raise StopPropagation
        
        Altruix.log(f"DEBUG: Attempting to send 'Starting' message for {user_id}", level=20)
        status_msg = await m.reply("⏳ Starting custom bot...")
        Altruix.log(f"DEBUG: 'Starting' message sent for {user_id}. Status msg ID: {status_msg.id}", level=20)
        
        try:
            session_client = Altruix.clients[index]
            user_id_session = session_client.me.id
            Altruix.log(f"DEBUG: Session found for {user_id_session}. Starting custom bot manager...", level=20)
            
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
            Altruix.log(f"DEBUG: Error starting custom bot for {user_id}: {e}", level=40)
            await status_msg.edit(f"❌ <b>Error:</b> {str(e)}", parse_mode=ParseMode.HTML)
            await send_log_notification(
                c, 'set_custom_bot', index, m.from_user,
                False, str(e), {'Session': index + 1}
            )
        
        # Cleanup state from shared dict
        if user_id in Altruix.user_env_manager_state:
            del Altruix.user_env_manager_state[user_id]

        # Always raise stop propagation for our messages
        raise StopPropagation

    except StopPropagation:
        raise
    except Exception as e:
        Altruix.log(f"DEBUG: Unexpected error in bot token handler for {user_id}: {e}", level=40)
        # Don't re-raise, let it pass
