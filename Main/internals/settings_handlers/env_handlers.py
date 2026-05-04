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
from datetime import datetime

from .utils import edit_cb, check_authorization

# Logger
logger = logging.getLogger(__name__)

# State for ENV input
user_env_input_state = {}

# ====================== ENV MANAGER HANDLERS ======================

@Altruix.bot.on_callback_query(filters.regex(r"^env_manager_list_(\d+)(?:_refresh)?$"))
@iuser_check
@log_errors
async def env_manager_list_handler(c: Client, cb: CallbackQuery):
    """Display list of environment variables with pagination"""
    if not await check_authorization(cb): return
    
    # Show "Refreshing..." toast if refreshing
    if "_refresh" in cb.data:
        await cb.answer("🔄 Refreshing list...", show_alert=False)
    else:
        await cb.answer()
    
    page = int(cb.matches[0].group(1))
    
    # Clear any pending input state (user pressed back)
    if cb.from_user.id in user_env_input_state:
        del user_env_input_state[cb.from_user.id]

    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)
    
    # Get all ENV variables and sort them alphabetically
    all_envs = {}
    if hasattr(Altruix.config, '_env_cache'):
        # Sort keys A-Z
        sorted_keys = sorted(Altruix.config._env_cache.keys())
        all_envs = {k: Altruix.config._env_cache[k] for k in sorted_keys}
    
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
        f"• <b>Page:</b> <code>{page}/{total_pages}</code>\n"
        f"• <b>Sort Mode:</b> <code>Alphabetical (A-Z)</code>\n"
    )
    
    # Add timestamp if refreshed to force update
    if "_refresh" in cb.data:
        current_time = datetime.now().strftime("%H:%M:%S")
        text += f"• <b>Last Updated:</b> <code>{current_time}</code>\n\n"
    else:
        text += "\n"
        
    text += "<i>Click on a variable to view/edit/delete</i>"
    
    # Buttons
    buttons = []
    
    # Variable buttons (show keys)
    if env_items:
        for key, value in env_items:
            # Truncate long keys for button display
            display_key = key[:25] + "..." if len(key) > 25 else key
            buttons.append([InlineKeyboardButton(f"📌 {display_key}", f"env_view_{key}", style=user_style)])
    else:
        text += "\n\n<i>No environment variables found.</i>"
    
    # Pagination buttons
    nav_buttons = []
    
    # Prev button
    prev_text = "«" if page > 1 else "🚫"
    prev_cb = f"env_manager_list_{page-1}" if page > 1 else f"env_manager_list_{page}"
    nav_buttons.append(InlineKeyboardButton(prev_text, prev_cb, style=user_style))
        
    # N/N indicator (merangkap refresh)
    nav_buttons.append(InlineKeyboardButton(f"{page}/{total_pages}", f"env_manager_list_{page}_refresh", style=user_style))
        
    # Next button
    next_text = "»" if page < total_pages else "🚫"
    next_cb = f"env_manager_list_{page+1}" if page < total_pages else f"env_manager_list_{page}"
    nav_buttons.append(InlineKeyboardButton(next_text, next_cb, style=user_style))
    
    buttons.append(nav_buttons)
        
    first_last_buttons = []
    if total_pages > 1:
        first_text = "First" if page > 1 else "🚫"
        first_cb = "env_manager_list_1" if page > 1 else f"env_manager_list_{page}"
        first_last_buttons.append(InlineKeyboardButton(first_text, first_cb, style=user_style))
        
        last_text = "Last" if page < total_pages else "🚫"
        last_cb = f"env_manager_list_{total_pages}" if page < total_pages else f"env_manager_list_{page}"
        first_last_buttons.append(InlineKeyboardButton(last_text, last_cb, style=user_style))
        
        buttons.append(first_last_buttons)
    
    # Action buttons
    buttons.append([
        InlineKeyboardButton("➕ Add", "env_add_start", style=user_style),
        InlineKeyboardButton("🔍 Search", "env_search_start", style=user_style)
    ])
    buttons.append([
        InlineKeyboardButton("📤 Import", "env_import_start", style=user_style),
        InlineKeyboardButton("🔄 Refresh", f"env_manager_list_{page}_refresh", style=user_style)
    ])
    buttons.append([
        InlineKeyboardButton("🔙 Back", "configs_home", style=user_style)
    ])
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^env_add_start$"))
@iuser_check
@log_errors
async def env_add_start_handler(c: Client, cb: CallbackQuery):
    """Start process to add new ENV variable"""
    if not await check_authorization(cb): return
    await cb.answer()
    
    text = (
        "<b>➕ Add Environment Variable</b>\n\n"
        "Please send the variable in this format:\n"
        "<code>KEY=VALUE</code>\n\n"
        "<b>Examples:</b>\n"
        "• <b>Text:</b> <code>MY_VAR=hello world</code>\n"
        "• <b>List:</b> <code>SUDO_USERS_ID=[123, 456, 789]</code>\n\n"
        "❌ <b>Cancel:</b> Send /cancel"
    )
    
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)

    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 Cancel", "env_manager_list_1", style=user_style)
    ]]), parse_mode=ParseMode.HTML)
    
    # Set state
    user_env_input_state[cb.from_user.id] = {
        'action': 'add',
        'step': 'waiting_key_value'
    }

@Altruix.bot.on_callback_query(filters.regex(r"^env_search_start$"))
@iuser_check
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
    
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)

    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 Cancel", "env_manager_list_1", style=user_style)
    ]]), parse_mode=ParseMode.HTML)
    
    user_env_input_state[cb.from_user.id] = {
        'action': 'search',
        'step': 'waiting_search_term'
    }

@Altruix.bot.on_callback_query(filters.regex(r"^env_view_(.+)$"))
@iuser_check
@log_errors
async def env_view_handler(c: Client, cb: CallbackQuery):
    """View ENV variable details with options"""
    if not await check_authorization(cb): return
    await cb.answer()
    
    # Clear any pending input state (user pressed back)
    if cb.from_user.id in user_env_input_state:
        del user_env_input_state[cb.from_user.id]
    
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)

    key = cb.matches[0].group(1)
    current_value = await Altruix.config.get_env(key) or "Not Set"
    
    # Mask sensitive values for display
    display_val = current_value
    is_sensitive = any(x in key.upper() for x in ['TOKEN', 'KEY', 'SECRET', 'PASSWORD', 'API'])
    if is_sensitive:
        display_val = "***HIDDEN***"
    
    # Check if value is long
    is_long = len(str(current_value)) > 100
    
    text = (
        f"<b>📌 Environment Variable</b>\n\n"
        f"• <b>Key:</b> <code>{key}</code>\n"
        f"• <b>Value:</b> <code>{html.escape(str(display_val)[:100])}</code>"
    )
    
    if is_long:
        text += "...\n\n<i>Value is too long. Use Export to view full content.</i>"
    else:
        text += "\n"
    
    buttons = [
        [
            InlineKeyboardButton(Altruix.get_string("ENV_EDIT_VALUE_BTN"), f"env_edit_val_{key}", style=user_style),
            InlineKeyboardButton(Altruix.get_string("ENV_RENAME_KEY_BTN"), f"env_rename_{key}", style=user_style)
        ],
    ]
    
    if is_long:
        buttons.append([InlineKeyboardButton("📥 Export as File", f"env_export_{key}", style=user_style)])
    
    buttons.append([
        InlineKeyboardButton("🗑️ Delete", f"env_delete_confirm_{key}", style=user_style),
        InlineKeyboardButton(Altruix.get_string("back"), "env_manager_list_1", style=user_style)
    ])
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^env_edit_val_(.+)$"))
@iuser_check
@log_errors
async def env_edit_handler(c: Client, cb: CallbackQuery):
    """Edit existing ENV variable"""
    if not await check_authorization(cb): return
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)
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
        f"• <b>Current Value:</b> <code>{html.escape(str(display_val)[:50])}</code>\n\n"
        f"Send the new value or upload a .txt/.json file:\n\n"
        f"❌ <b>Cancel:</b> Send /cancel"
    )
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 Cancel", f"env_view_{key}", style=user_style)
    ]]), parse_mode=ParseMode.HTML)
    
    user_env_input_state[cb.from_user.id] = {
        'action': 'edit',
        'key': key,
        'step': 'waiting_new_value'
    }

@Altruix.bot.on_callback_query(filters.regex(r"^env_rename_(.+)$"))
@iuser_check
@log_errors
async def env_rename_handler(c: Client, cb: CallbackQuery):
    """Initiate rename of ENV variable"""
    if not await check_authorization(cb): return
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)
    await cb.answer()
    
    key = cb.matches[0].group(1)
    
    text = Altruix.get_string("ENV_RENAME_PROMPT").format(key)
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton(Altruix.get_string("cancel"), f"env_view_{key}", style=user_style)
    ]]), parse_mode=ParseMode.HTML)
    
    user_env_input_state[cb.from_user.id] = {
        'action': 'rename',
        'old_key': key,
        'step': 'waiting_new_key'
    }

@Altruix.bot.on_callback_query(filters.regex(r"^env_delete_confirm_(.+)$"))
@iuser_check
@log_errors
async def env_delete_confirm_handler(c: Client, cb: CallbackQuery):
    """Confirm deletion of ENV variable"""
    if not await check_authorization(cb): return
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)
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
            InlineKeyboardButton("✅ Yes, Delete", f"env_delete_exec_{key}", style=user_style),
            InlineKeyboardButton("❌ Cancel", "env_manager_list_1", style=user_style)
        ]
    ]
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^env_delete_exec_(.+)$"))
@iuser_check
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

@Altruix.bot.on_callback_query(filters.regex(r"^env_edit_yes_(.+)$"))
@iuser_check
@log_errors
async def env_edit_yes_handler(c: Client, cb: CallbackQuery):
    """Confirm and execute ENV variable edit"""
    if not await check_authorization(cb): return
    
    key = cb.matches[0].group(1)
    user_id = cb.from_user.id
    
    # Get stored new value from state
    if user_id not in user_env_input_state:
        await cb.answer("❌ Session expired. Please try again.", show_alert=True)
        return
    
    state = user_env_input_state[user_id]
    if state.get('step') != 'confirming' or state.get('key') != key:
        await cb.answer("❌ Invalid state. Please try again.", show_alert=True)
        return
    
    new_value = state.get('new_value')
    
    try:
        # Update database
        await Altruix.config.sync_env_to_db(key, new_value, upsert=True)
        
        # Update config object
        setattr(Altruix.config, key, new_value)
        
        # Update cache
        if hasattr(Altruix.config, '_env_cache'):
            Altruix.config._env_cache[key] = new_value
        
        await cb.answer("✅ Variable updated successfully!", show_alert=True)
        
        # Clear state
        if user_id in user_env_input_state:
            del user_env_input_state[user_id]
        
        # Show success message and return to list
        text = (
            f"<b>✅ Update Complete</b>\n\n"
            f"• <b>Key:</b> <code>{key}</code>\n"
            f"• <b>Status:</b> Successfully updated"
        )
        
        from Main.utils.file_helpers import get_user_button_style
        user_style = get_user_button_style(user_id)
        
        await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Back to ENV Manager", "env_manager_list_1", style=user_style)
        ]]), parse_mode=ParseMode.HTML)
        
    except Exception as e:
        logger.error(f"Error updating ENV {key}: {e}")
        await cb.answer(f"❌ Error: {str(e)}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^env_edit_file_yes_(.+)$"))
@iuser_check
@log_errors
async def env_edit_file_yes_handler(c: Client, cb: CallbackQuery):
    """Confirm and execute ENV variable edit from file"""
    if not await check_authorization(cb): return
    
    key = cb.matches[0].group(1)
    user_id = cb.from_user.id
    
    # Get stored new value from state
    if user_id not in user_env_input_state:
        await cb.answer("❌ Session expired. Please try again.", show_alert=True)
        return
    
    state = user_env_input_state[user_id]
    if state.get('step') != 'confirming_file' or state.get('key') != key:
        await cb.answer("❌ Invalid state. Please try again.", show_alert=True)
        return
    
    new_value = state.get('new_value')
    
    try:
        # Update database
        await Altruix.config.sync_env_to_db(key, new_value, upsert=True)
        
        # Update config object
        setattr(Altruix.config, key, new_value)
        
        # Update cache
        if hasattr(Altruix.config, '_env_cache'):
            Altruix.config._env_cache[key] = new_value
        
        await cb.answer("✅ Variable updated successfully!", show_alert=True)
        
        # Clear state
        if user_id in user_env_input_state:
            del user_env_input_state[user_id]
        
        # Show success message and return to list
        text = (
            f"<b>✅ Update Complete (File)</b>\n\n"
            f"• <b>Key:</b> <code>{key}</code>\n"
            f"• <b>Status:</b> Successfully updated from file"
        )
        
        from Main.utils.file_helpers import get_user_button_style
        user_style = get_user_button_style(user_id)
        
        await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Back to ENV Manager", "env_manager_list_1", style=user_style)
        ]]), parse_mode=ParseMode.HTML)
        
    except Exception as e:
        logger.error(f"Error updating ENV {key}: {e}")
        await cb.answer(f"❌ Error: {str(e)}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^env_export_(.+)$"))
@iuser_check
@log_errors
async def env_export_handler(c: Client, cb: CallbackQuery):
    """Export ENV variable value as file"""
    if not await check_authorization(cb): return
    await cb.answer("📥 Exporting...")
    
    key = cb.matches[0].group(1)
    value = await Altruix.config.get_env(key)
    
    if not value:
        await cb.answer("❌ Variable not found!", show_alert=True)
        return
    
    try:
        # Create temporary file
        import tempfile
        import json
        
        # Determine if value is JSON
        is_json = False
        try:
            json.loads(str(value))
            is_json = True
        except:
            pass
        
        file_ext = "json" if is_json else "txt"
        filename = f"{key}.{file_ext}"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix=f'.{file_ext}', delete=False, encoding='utf-8') as f:
            if is_json:
                json.dump(json.loads(str(value)), f, indent=2)
            else:
                f.write(str(value))
            temp_path = f.name
        
        # Send file
        caption = f"<b>📥 ENV Export</b>\n\n• <b>Key:</b> <code>{key}</code>\n• <b>Size:</b> <code>{len(str(value))} chars</code>"
        
        await c.send_document(
            cb.message.chat.id,
            temp_path,
            caption=caption,
            file_name=filename,
            parse_mode=ParseMode.HTML
        )
        
        # Cleanup
        import os
        os.unlink(temp_path)
        
        await cb.answer("✅ Exported successfully!")
    except Exception as e:
        logger.error(f"Error exporting ENV {key}: {e}")
        await cb.answer(f"❌ Export failed: {str(e)}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^env_import_start$"))
@iuser_check
@log_errors
async def env_import_start_handler(c: Client, cb: CallbackQuery):
    """Start ENV import from file"""
    if not await check_authorization(cb): return
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)
    await cb.answer()
    
    text = (
        "<b>📤 Import Environment Variables</b>\n\n"
        "Upload a file to import variables:\n\n"
        "<b>Supported formats:</b>\n"
        "• <b>.txt</b> - KEY=VALUE format (one per line)\n"
        "• <b>.json</b> - JSON object {\"KEY\": \"VALUE\"}\n\n"
        "<b>Example .txt:</b>\n"
        "<code>API_KEY=abc123\nSUDO_USERS_ID=[111, 222, 333]</code>\n\n"
        "<b>Example .json:</b>\n"
        "<code>{\"API_KEY\": \"abc\", \"MY_LIST\": [1, 2, 3]}</code>\n\n"
        "❌ <b>Cancel:</b> Send /cancel"
    )
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 Cancel", "env_manager_list_1", style=user_style)
    ]]), parse_mode=ParseMode.HTML)
    
    user_env_input_state[cb.from_user.id] = {
        'action': 'import',
        'step': 'waiting_file'
    }

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
            if m.from_user.id in user_env_input_state:
                del user_env_input_state[m.from_user.id]
            from Main.utils.file_helpers import get_user_button_style
            user_style = get_user_button_style(m.from_user.id)
            # Show menu
            await m.reply("🔄 Returning to ENV Manager...", reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back to ENV Manager", "env_manager_list_1", style=user_style)
            ]]))
        except Exception as e:
            logger.error(f"Error adding ENV: {e}")
            await m.reply(f"❌ Error: {str(e)}")
    
    elif action == 'edit' and step == 'waiting_new_value':
        key = state.get('key')
        new_value = m.text.strip()
        
        # ✅ List detection for manual text input
        is_list = False
        if new_value.startswith('[') and new_value.endswith(']'):
            import ast
            try:
                parsed = ast.literal_eval(new_value)
                if isinstance(parsed, list):
                    is_list = True
                    # We store it as a list in state
                    new_value = parsed
            except: pass

        # Show confirmation dialog
        format_label = Altruix.get_string("ENV_FORMAT_LIST") if is_list else Altruix.get_string("ENV_FORMAT_TEXT")
        text = (
            f"<b>⚠️ Confirm Edit</b>\n\n"
            f"• <b>Key:</b> <code>{key}</code>\n"
            f"• <b>New Value:</b> <code>{html.escape(str(new_value)[:100])}</code>\n"
            f"• <b>Format:</b> <code>{format_label}</code>\n\n"
            f"Are you sure you want to update this variable?"
        )
        
        from Main.utils.file_helpers import get_user_button_style
        user_style = get_user_button_style(m.from_user.id)

        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Yes", f"env_edit_yes_{key}", style=user_style),
                InlineKeyboardButton("❌ No", f"env_view_{key}", style=user_style)
            ]
        ])
        
        await m.reply(text, parse_mode=ParseMode.HTML, reply_markup=buttons)
        
        # Update state to store new value for confirmation
        user_env_input_state[m.from_user.id] = {
            'action': 'edit',
            'key': key,
            'step': 'confirming',
            'new_value': parsed if is_list else new_value
        }
        # DON'T DELETE STATE HERE - IT'S NEEDED FOR CONFIRMATION
    
    elif action == 'rename' and step == 'waiting_new_key':
        # ... (keeping existing rename logic)
        old_key = state.get('old_key')
        new_key = m.text.strip().upper().replace(' ', '_')
        
        if not new_key:
            await m.reply("❌ New name cannot be empty!")
            return
            
        # Check if new key already exists
        if hasattr(Altruix.config, new_key) or (hasattr(Altruix.config, '_env_cache') and new_key in Altruix.config._env_cache):
            await m.reply(f"❌ Variable <code>{new_key}</code> already exists!", parse_mode=ParseMode.HTML)
            return

        # Show confirmation dialog
        text = Altruix.get_string("ENV_RENAME_CONFIRM").format(old_key, new_key)
        
        from Main.utils.file_helpers import get_user_button_style
        user_style = get_user_button_style(m.from_user.id)
        
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(Altruix.get_string("yes"), f"env_rename_exec_{old_key}_{new_key}", style=user_style),
                InlineKeyboardButton(Altruix.get_string("no"), f"env_view_{old_key}", style=user_style)
            ]
        ])
        
        await m.reply(text, parse_mode=ParseMode.HTML, reply_markup=buttons)
        
        # Clear state
        if m.from_user.id in user_env_input_state:
            del user_env_input_state[m.from_user.id]

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
                display_val = str(value)[:20] + "..." if len(str(value)) > 20 else value
                if any(x in key.upper() for x in ['TOKEN', 'KEY', 'SECRET', 'PASSWORD', 'API']):
                    display_val = "***HIDDEN***"
                text += f"• <code>{key}</code>: <code>{html.escape(str(display_val))}</code>\n"
        else:
            text += "<i>No matches found.</i>"
        
        from Main.utils.file_helpers import get_user_button_style
        user_style = get_user_button_style(m.from_user.id)
        await m.reply(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Back to ENV Manager", "env_manager_list_1", style=user_style)
        ]]))
        
        # Clear state
        if m.from_user.id in user_env_input_state:
            del user_env_input_state[m.from_user.id]

@Altruix.bot.on_callback_query(filters.regex(r"^env_rename_exec_(.+)_(.+)$"))
@iuser_check
@log_errors
async def env_rename_exec_handler(c: Client, cb: CallbackQuery):
    """Execute rename of ENV variable"""
    if not await check_authorization(cb): return
    
    old_key = cb.matches[0].group(1)
    new_key = cb.matches[0].group(2)
    
    try:
        # Get current value
        value = await Altruix.config.get_env(old_key)
        
        # 1. Add new key with same value
        await Altruix.config.sync_env_to_db(new_key, value, upsert=True)
        setattr(Altruix.config, new_key, value)
        if hasattr(Altruix.config, '_env_cache'):
            Altruix.config._env_cache[new_key] = value
            
        # 2. Delete old key
        await Altruix.config.sync_env_to_db(old_key, None, delete=True)
        if hasattr(Altruix.config, old_key):
            delattr(Altruix.config, old_key)
        if hasattr(Altruix.config, '_env_cache') and old_key in Altruix.config._env_cache:
            del Altruix.config._env_cache[old_key]
            
        await cb.answer(Altruix.get_string("ENV_RENAME_SUCCESS").format(old_key, new_key), show_alert=True)
        # Return to list
        await env_manager_list_handler(c, cb)
    except Exception as e:
        logger.error(f"Error renaming ENV {old_key}: {e}")
        await cb.answer(f"❌ Error: {str(e)}", show_alert=True)

async def process_env_document(c: Client, m: Message, state: dict):
    """Process ENV manager document uploads"""
    action = state.get('action')
    step = state.get('step')
    
    if not m.document:
        await m.reply("❌ Please upload a document file (.txt or .json)")
        return
    
    file_name = m.document.file_name
    file_ext = file_name.split('.')[-1].lower() if '.' in file_name else ''
    
    if file_ext not in ['txt', 'json']:
        await m.reply("❌ Unsupported file type! Please upload .txt or .json file.")
        return
    
    try:
        # Download file
        file_path = await m.download()
        
        # Read content
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Cleanup downloaded file
        import os
        os.unlink(file_path)
        
        if action == 'import' and step == 'waiting_file':
            # Parse and import variables
            import json
            imported = 0
            errors = []
            
            if file_ext == 'json':
                try:
                    data = json.loads(content)
                    if not isinstance(data, dict):
                        await m.reply("❌ JSON file must contain an object with key-value pairs!")
                        return
                    
                    for key, value in data.items():
                        try:
                            # Detect list-like strings and parse them
                            val_to_save = str(value)
                            if val_to_save.startswith('[') and val_to_save.endswith(']'):
                                import ast
                                try:
                                    parsed = ast.literal_eval(val_to_save)
                                    if isinstance(parsed, list):
                                        val_to_save = parsed
                                except: pass

                            await Altruix.config.sync_env_to_db(key, val_to_save, upsert=True)
                            setattr(Altruix.config, key, val_to_save)
                            if hasattr(Altruix.config, '_env_cache'):
                                Altruix.config._env_cache[key] = val_to_save
                            imported += 1
                        except Exception as e:
                            errors.append(f"{key}: {str(e)}")
                except json.JSONDecodeError as e:
                    await m.reply(f"❌ Invalid JSON format: {str(e)}")
                    return
            else:  # txt
                lines = content.strip().split('\n')
                for line in lines:
                    line = line.strip()
                    if not line or line.startswith('#'):  # Skip empty and comments
                        continue
                    if '=' not in line:
                        errors.append(f"Invalid format: {line}")
                        continue
                    
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    if not key:
                        errors.append(f"Empty key in line: {line}")
                        continue
                    
                    try:
                        # Detect list-like strings
                        val_to_save = value
                        if val_to_save.startswith('[') and val_to_save.endswith(']'):
                            import ast
                            try:
                                parsed = ast.literal_eval(val_to_save)
                                if isinstance(parsed, list):
                                    val_to_save = parsed
                            except: pass

                        await Altruix.config.sync_env_to_db(key, val_to_save, upsert=True)
                        setattr(Altruix.config, key, val_to_save)
                        if hasattr(Altruix.config, '_env_cache'):
                            Altruix.config._env_cache[key] = val_to_save
                        imported += 1
                    except Exception as e:
                        errors.append(f"{key}: {str(e)}")
            
            # Report results
            result_text = f"<b>✅ Import Complete</b>\n\n• <b>Imported:</b> <code>{imported}</code> variables\n"
            if errors:
                result_text += f"• <b>Errors:</b> <code>{len(errors)}</code>\n\n<b>Error details:</b>\n"
                for err in errors[:5]:  # Show first 5 errors
                    result_text += f"• <code>{html.escape(err)}</code>\n"
                if len(errors) > 5:
                    result_text += f"\n<i>...and {len(errors) - 5} more errors</i>"
            
            from Main.utils.file_helpers import get_user_button_style
            user_style = get_user_button_style(m.from_user.id)
            await m.reply(result_text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back to ENV Manager", "env_manager_list_1", style=user_style)
            ]]))
        elif action == 'edit' and step == 'waiting_new_value':
            # Use file content as new value
            key = state.get('key')
            
        # ✅ IMPROVED: List detection for file content
            final_value = content.strip()
            is_list_display = False
            if final_value.startswith('[') and final_value.endswith(']'):
                import ast
                try:
                    # Validate if it's a valid list string
                    parsed = ast.literal_eval(final_value)
                    if isinstance(parsed, list):
                        is_list_display = True
                        final_value = parsed # Use actual list object
                except: pass

            # Show confirmation dialog
            format_label = Altruix.get_string("ENV_FORMAT_LIST") if is_list_display else Altruix.get_string("ENV_FORMAT_TEXT")
            text = (
                f"<b>⚠️ Confirm Edit from File</b>\n\n"
                f"• <b>Key:</b> <code>{key}</code>\n"
                f"• <b>File:</b> <code>{file_name}</code>\n"
                f"• <b>Size:</b> <code>{len(content)} chars</code>\n"
                f"• <b>Format:</b> <code>{format_label}</code>\n\n"
                f"Are you sure you want to update this variable with the file content?"
            )
            
            from Main.utils.file_helpers import get_user_button_style
            user_style = get_user_button_style(m.from_user.id)
            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Yes", f"env_edit_file_yes_{key}", style=user_style),
                    InlineKeyboardButton("❌ No", f"env_view_{key}", style=user_style)
                ]
            ])
            
            await m.reply(text, parse_mode=ParseMode.HTML, reply_markup=buttons)
            
            # Update state to store file content for confirmation
            user_env_input_state[m.from_user.id] = {
                'action': 'edit',
                'key': key,
                'step': 'confirming_file',
                'new_value': final_value
            }
        
        # Only clear state if NOT in a confirmation or multi-step action
        if action == 'import':
            if m.from_user.id in user_env_input_state:
                del user_env_input_state[m.from_user.id]
            
    except Exception as e:
        logger.error(f"Error processing ENV document: {e}")
        await m.reply(f"❌ Error processing file: {str(e)}")

