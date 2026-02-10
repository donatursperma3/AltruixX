# Main/internals/settings_handlers/env_handlers.py
import html
import os
import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from Main.core.decorators import log_errors, iuser_check
from Main.core.client import Altruix
from pyrogram.enums import ParseMode

from .utils import edit_cb, check_authorization

# Logger
logger = logging.getLogger(__name__)

# State for ENV input
user_env_input_state = {}

# ====================== ENV MANAGER HANDLERS ======================

@Altruix.bot.on_callback_query(filters.regex(r"^env_manager_list_(\d+)$"))
@log_errors
async def env_manager_list_handler(c: Client, cb: CallbackQuery):
    """Display list of environment variables with pagination"""
    if not await check_authorization(cb): return
    await cb.answer()
    
    page = int(cb.matches[0].group(1))
    
    # Get all ENV variables
    all_envs = {}
    if hasattr(Altruix.config, '_env_cache'):
        all_envs = Altruix.config._env_cache
    
    # Pagination
    items_per_page = 10
    total_envs = len(all_envs)
    total_pages = (total_envs + items_per_page - 1) // items_per_page if total_envs > 0 else 1
    
    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    
    env_items = list(all_envs.items())[start_idx:end_idx]
    
    text = (
        f"<b>🔧 Environment Manager (v1.5.5.9b)</b>\n\n"
        f"• <b>Total Variables:</b> <code>{total_envs}</code>\n"
        f"• <b>Page:</b> <code>{page}/{total_pages}</code>\n\n"
    )
    
    if env_items:
        text += "<b>Variables:</b>\n"
        for key, value in env_items:
            # Mask sensitive values
            display_val = value[:20] + "..." if len(str(value)) > 20 else value
            if any(x in key.upper() for x in ['TOKEN', 'KEY', 'SECRET', 'PASSWORD', 'API']):
                display_val = "***HIDDEN***"
            text += f"• <code>{key}</code>: <code>{html.escape(str(display_val))}</code>\n"
    else:
        text += "<i>No environment variables found.</i>\n"
    
    # Buttons
    buttons = []
    
    # Pagination buttons
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ Prev", f"env_manager_list_{page-1}"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("Next ➡️", f"env_manager_list_{page+1}"))
    if nav_buttons:
        buttons.append(nav_buttons)
    
    # Action buttons
    buttons.append([
        InlineKeyboardButton("➕ Add Variable", "env_add_start"),
        InlineKeyboardButton("🔍 Search", "env_search_start")
    ])
    buttons.append([
        InlineKeyboardButton("🔄 Refresh", f"env_manager_list_{page}"),
        InlineKeyboardButton("🔙 Back", "session_info_0_1_4")
    ])
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^env_add_start$"))
@log_errors
async def env_add_start_handler(c: Client, cb: CallbackQuery):
    """Start process to add new ENV variable"""
    if not await check_authorization(cb): return
    await cb.answer()
    
    text = (
        "<b>➕ Add Environment Variable</b>\n\n"
        "Please send the variable in this format:\n"
        "<code>KEY=VALUE</code>\n\n"
        "<b>Example:</b>\n"
        "<code>MY_API_KEY=abc123xyz</code>\n\n"
        "❌ <b>Cancel:</b> Send /cancel"
    )
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 Cancel", "env_manager_list_1")
    ]]), parse_mode=ParseMode.HTML)
    
    # Set state
    user_env_input_state[cb.from_user.id] = {
        'action': 'add',
        'step': 'waiting_key_value'
    }

@Altruix.bot.on_callback_query(filters.regex(r"^env_search_start$"))
@log_errors
async def env_search_start_handler(c: Client, cb: CallbackQuery):
    """Start ENV search process"""
    if not await check_authorization(cb): return
    await cb.answer()
    
    text = (
        "<b>🔍 Search Environment Variables</b>\n\n"
        "Send the search term (key name):\n\n"
        "❌ <b>Cancel:</b> Send /cancel"
    )
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 Cancel", "env_manager_list_1")
    ]]), parse_mode=ParseMode.HTML)
    
    user_env_input_state[cb.from_user.id] = {
        'action': 'search',
        'step': 'waiting_search_term'
    }

@Altruix.bot.on_callback_query(filters.regex(r"^env_edit_(.+)$"))
@log_errors
async def env_edit_handler(c: Client, cb: CallbackQuery):
    """Edit existing ENV variable"""
    if not await check_authorization(cb): return
    await cb.answer()
    
    key = cb.matches[0].group(1)
    current_value = await Altruix.config.get_env(key) or "Not Set"
    
    # Mask sensitive values
    display_val = current_value
    if any(x in key.upper() for x in ['TOKEN', 'KEY', 'SECRET', 'PASSWORD', 'API']):
        display_val = "***HIDDEN***"
    
    text = (
        f"<b>✏️ Edit Environment Variable</b>\n\n"
        f"• <b>Key:</b> <code>{key}</code>\n"
        f"• <b>Current Value:</b> <code>{html.escape(str(display_val))}</code>\n\n"
        f"Send the new value:\n\n"
        f"❌ <b>Cancel:</b> Send /cancel"
    )
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("🗑️ Delete", f"env_delete_confirm_{key}"),
        InlineKeyboardButton("🔙 Cancel", "env_manager_list_1")
    ]]), parse_mode=ParseMode.HTML)
    
    user_env_input_state[cb.from_user.id] = {
        'action': 'edit',
        'key': key,
        'step': 'waiting_new_value'
    }

@Altruix.bot.on_callback_query(filters.regex(r"^env_delete_confirm_(.+)$"))
@log_errors
async def env_delete_confirm_handler(c: Client, cb: CallbackQuery):
    """Confirm deletion of ENV variable"""
    if not await check_authorization(cb): return
    await cb.answer()
    
    key = cb.matches[0].group(1)
    
    text = (
        f"<b>⚠️ Confirm Deletion</b>\n\n"
        f"Are you sure you want to delete:\n"
        f"<code>{key}</code>\n\n"
        f"<b>This action cannot be undone!</b>"
    )
    
    buttons = [
        [
            InlineKeyboardButton("✅ Yes, Delete", f"env_delete_exec_{key}"),
            InlineKeyboardButton("❌ Cancel", "env_manager_list_1")
        ]
    ]
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^env_delete_exec_(.+)$"))
@log_errors
async def env_delete_exec_handler(c: Client, cb: CallbackQuery):
    """Execute deletion of ENV variable"""
    if not await check_authorization(cb): return
    
    key = cb.matches[0].group(1)
    
    try:
        # Delete from database
        await Altruix.config.sync_env_to_db(key, None, delete=True)
        
        # Delete from config object
        if hasattr(Altruix.config, key):
            delattr(Altruix.config, key)
        
        # Delete from cache
        if hasattr(Altruix.config, '_env_cache') and key in Altruix.config._env_cache:
            del Altruix.config._env_cache[key]
        
        await cb.answer(f"✅ Deleted: {key}", show_alert=True)
    except Exception as e:
        logger.error(f"Error deleting ENV {key}: {e}")
        await cb.answer(f"❌ Error: {str(e)}", show_alert=True)
    
    # Return to list
    await env_manager_list_handler(c, cb)

# ====================== INPUT PROCESSING ======================

async def process_env_input(c: Client, m: Message, state: dict):
    """Process ENV manager text inputs"""
    action = state.get('action')
    step = state.get('step')
    
    if action == 'add' and step == 'waiting_key_value':
        # Parse KEY=VALUE format
        text = m.text.strip()
        if '=' not in text:
            await m.reply("❌ Invalid format! Use: <code>KEY=VALUE</code>", parse_mode=ParseMode.HTML)
            return
        
        key, value = text.split('=', 1)
        key = key.strip()
        value = value.strip()
        
        if not key:
            await m.reply("❌ Key cannot be empty!")
            return
        
        try:
            # Save to database
            await Altruix.config.sync_env_to_db(key, value, upsert=True)
            
            # Update config object
            setattr(Altruix.config, key, value)
            
            # Update cache
            if hasattr(Altruix.config, '_env_cache'):
                Altruix.config._env_cache[key] = value
            
            await m.reply(f"✅ Added: <code>{key}</code>", parse_mode=ParseMode.HTML)
            
            # Clear state
            if m.from_user.id in user_env_input_state:
                del user_env_input_state[m.from_user.id]
            
            # Show menu
            await m.reply("🔄 Returning to ENV Manager...", reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back to ENV Manager", "env_manager_list_1")
            ]]))
        except Exception as e:
            logger.error(f"Error adding ENV: {e}")
            await m.reply(f"❌ Error: {str(e)}")
    
    elif action == 'edit' and step == 'waiting_new_value':
        key = state.get('key')
        new_value = m.text.strip()
        
        try:
            # Update database
            await Altruix.config.sync_env_to_db(key, new_value, upsert=True)
            
            # Update config object
            setattr(Altruix.config, key, new_value)
            
            # Update cache
            if hasattr(Altruix.config, '_env_cache'):
                Altruix.config._env_cache[key] = new_value
            
            await m.reply(f"✅ Updated: <code>{key}</code>", parse_mode=ParseMode.HTML)
            
            # Clear state
            if m.from_user.id in user_env_input_state:
                del user_env_input_state[m.from_user.id]
            
            # Show menu
            await m.reply("🔄 Returning to ENV Manager...", reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back to ENV Manager", "env_manager_list_1")
            ]]))
        except Exception as e:
            logger.error(f"Error updating ENV: {e}")
            await m.reply(f"❌ Error: {str(e)}")
    
    elif action == 'search' and step == 'waiting_search_term':
        search_term = m.text.strip().upper()
        
        # Search in ENV cache
        results = {}
        if hasattr(Altruix.config, '_env_cache'):
            for key, value in Altruix.config._env_cache.items():
                if search_term in key.upper():
                    results[key] = value
        
        text = f"<b>🔍 Search Results for: {html.escape(search_term)}</b>\n\n"
        
        if results:
            text += f"Found <code>{len(results)}</code> matches:\n\n"
            for key, value in list(results.items())[:10]:  # Limit to 10 results
                display_val = value[:20] + "..." if len(str(value)) > 20 else value
                if any(x in key.upper() for x in ['TOKEN', 'KEY', 'SECRET', 'PASSWORD', 'API']):
                    display_val = "***HIDDEN***"
                text += f"• <code>{key}</code>: <code>{html.escape(str(display_val))}</code>\n"
        else:
            text += "<i>No matches found.</i>"
        
        await m.reply(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Back to ENV Manager", "env_manager_list_1")
        ]]))
        
        # Clear state
        if m.from_user.id in user_env_input_state:
            del user_env_input_state[m.from_user.id]
