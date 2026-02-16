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
        f"• <b>Page:</b> <code>{page}/{total_pages}</code>\n"
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
            buttons.append([InlineKeyboardButton(f"📌 {display_key}", f"env_view_{key}")])
    else:
        text += "\n\n<i>No environment variables found.</i>"
    
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
        InlineKeyboardButton("➕ Add", "env_add_start"),
        InlineKeyboardButton("🔍 Search", "env_search_start")
    ])
    buttons.append([
        InlineKeyboardButton("📤 Import", "env_import_start"),
        InlineKeyboardButton("🔄 Refresh", f"env_manager_list_{page}_refresh")
    ])
    buttons.append([
        InlineKeyboardButton("🔙 Back", "configs_home")
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
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 Cancel", "env_manager_list_1")
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
        [InlineKeyboardButton("✏️ Edit", f"env_edit_{key}")],
    ]
    
    if is_long:
        buttons.append([InlineKeyboardButton("📥 Export as File", f"env_export_{key}")])
    
    buttons.append([
        InlineKeyboardButton("🗑️ Delete", f"env_delete_confirm_{key}"),
        InlineKeyboardButton("🔙 Back", "env_manager_list_1")
    ])
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^env_edit_(.+)$"))
@iuser_check
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
        f"• <b>Current Value:</b> <code>{html.escape(str(display_val)[:50])}</code>\n\n"
        f"Send the new value or upload a .txt/.json file:\n\n"
        f"❌ <b>Cancel:</b> Send /cancel"
    )
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 Cancel", f"env_view_{key}")
    ]]), parse_mode=ParseMode.HTML)
    
    user_env_input_state[cb.from_user.id] = {
        'action': 'edit',
        'key': key,
        'step': 'waiting_new_value'
    }

@Altruix.bot.on_callback_query(filters.regex(r"^env_delete_confirm_(.+)$"))
@iuser_check
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
        
        await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Back to ENV Manager", "env_manager_list_1")
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
        
        await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Back to ENV Manager", "env_manager_list_1")
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
    await cb.answer()
    
    text = (
        "<b>📤 Import Environment Variables</b>\n\n"
        "Upload a file to import variables:\n\n"
        "<b>Supported formats:</b>\n"
        "• <b>.txt</b> - KEY=VALUE format (one per line)\n"
        "• <b>.json</b> - JSON object {\"KEY\": \"VALUE\"}\n\n"
        "<b>Example .txt:</b>\n"
        "<code>API_KEY=abc123\nSECRET=xyz789</code>\n\n"
        "<b>Example .json:</b>\n"
        "<code>{\"API_KEY\": \"abc123\", \"SECRET\": \"xyz789\"}</code>\n\n"
        "❌ <b>Cancel:</b> Send /cancel"
    )
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 Cancel", "env_manager_list_1")
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
        
        # Show confirmation dialog
        text = (
            f"<b>⚠️ Confirm Edit</b>\n\n"
            f"• <b>Key:</b> <code>{key}</code>\n"
            f"• <b>New Value:</b> <code>{html.escape(new_value[:100])}</code>\n\n"
            f"Are you sure you want to update this variable?"
        )
        
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Yes", f"env_edit_yes_{key}"),
                InlineKeyboardButton("❌ No", f"env_view_{key}")
            ]
        ])
        
        await m.reply(text, parse_mode=ParseMode.HTML, reply_markup=buttons)
        
        # Update state to store new value for confirmation
        user_env_input_state[m.from_user.id] = {
            'action': 'edit',
            'key': key,
            'step': 'confirming',
            'new_value': new_value
        }
    
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
        
        await m.reply(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Back to ENV Manager", "env_manager_list_1")
        ]]))
        
        # Clear state
        if m.from_user.id in user_env_input_state:
            del user_env_input_state[m.from_user.id]

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
                            await Altruix.config.sync_env_to_db(key, str(value), upsert=True)
                            setattr(Altruix.config, key, str(value))
                            if hasattr(Altruix.config, '_env_cache'):
                                Altruix.config._env_cache[key] = str(value)
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
                        await Altruix.config.sync_env_to_db(key, value, upsert=True)
                        setattr(Altruix.config, key, value)
                        if hasattr(Altruix.config, '_env_cache'):
                            Altruix.config._env_cache[key] = value
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
            
            await m.reply(result_text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back to ENV Manager", "env_manager_list_1")
            ]]))
            
        elif action == 'edit' and step == 'waiting_new_value':
            # Use file content as new value
            key = state.get('key')
            
            # Show confirmation dialog
            text = (
                f"<b>⚠️ Confirm Edit from File</b>\n\n"
                f"• <b>Key:</b> <code>{key}</code>\n"
                f"• <b>File:</b> <code>{file_name}</code>\n"
                f"• <b>Size:</b> <code>{len(content)} chars</code>\n\n"
                f"Are you sure you want to update this variable with the file content?"
            )
            
            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Yes", f"env_edit_file_yes_{key}"),
                    InlineKeyboardButton("❌ No", f"env_view_{key}")
                ]
            ])
            
            await m.reply(text, parse_mode=ParseMode.HTML, reply_markup=buttons)
            
            # Update state to store file content for confirmation
            user_env_input_state[m.from_user.id] = {
                'action': 'edit',
                'key': key,
                'step': 'confirming_file',
                'new_value': content
            }
        
        # Clear state
        if m.from_user.id in user_env_input_state:
            del user_env_input_state[m.from_user.id]
            
    except Exception as e:
        logger.error(f"Error processing ENV document: {e}")
        await m.reply(f"❌ Error processing file: {str(e)}")

