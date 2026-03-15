# Main/internals/settings_handlers/backup_handlers.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
# All rights reserved.

import os
import asyncio
from Main import Altruix
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from Main.core.decorators import iuser_check, log_errors
from Main.utils.backup_helpers import upload_db_backup
from datetime import datetime

# Plugin Metadata
PLUGIN_VERSION = "1.0.0"

async def get_backup_kb(user_style=None):
    """
    Generates the inline keyboard for the backup manager.
    
    Args:
        user_style (ButtonStyle): The button style to apply.

    Returns:
        InlineKeyboardMarkup: The generated keyboard with current settings highlighted.
    """
    is_enabled = await Altruix.config.get_env("AUTO_BACKUP_ENABLED") == "true"
    interval = await Altruix.config.get_env("AUTO_BACKUP_INTERVAL") or "24h"
    
    toggle_text = "✅ Enabled" if is_enabled else "❌ Disabled"
    toggle_cb = "backup_toggle_off" if is_enabled else "backup_toggle_on"
    
    kb = [
        [InlineKeyboardButton(f"Status: {toggle_text}", callback_data=toggle_cb, style=user_style)],
        [
            InlineKeyboardButton(f"{'➡️ ' if interval == '1h' else ''}1h", callback_data="backup_set_1h", style=user_style),
            InlineKeyboardButton(f"{'➡️ ' if interval == '3h' else ''}3h", callback_data="backup_set_3h", style=user_style),
            InlineKeyboardButton(f"{'➡️ ' if interval == '6h' else ''}6h", callback_data="backup_set_6h", style=user_style),
        ],
        [
            InlineKeyboardButton(f"{'➡️ ' if interval == '12h' else ''}12h", callback_data="backup_set_12h", style=user_style),
            InlineKeyboardButton(f"{'➡️ ' if interval == '24h' else ''}24h", callback_data="backup_set_24h", style=user_style),
            InlineKeyboardButton(f"{'➡️ ' if interval == '1w' else ''}1w", callback_data="backup_set_1w", style=user_style),
        ],
        [InlineKeyboardButton("📤 Backup Now", callback_data="backup_now", style=user_style)],
        [InlineKeyboardButton("🔙 Back to Configs", callback_data="configs_home", style=user_style)]
    ]
    return InlineKeyboardMarkup(kb)

@Altruix.bot.on_callback_query(filters.regex(r"^backup_manager$"))
@iuser_check
@log_errors
async def backup_manager_handler(c: Client, cb: CallbackQuery):
    """
    Displays the main dashboard for the Database Manager (Auto-Backup).
    
    Args:
        c (Client): The bot client.
        cb (CallbackQuery): The callback query.
    """
    await cb.answer()
    
    is_enabled = await Altruix.config.get_env("AUTO_BACKUP_ENABLED") == "true"
    interval = await Altruix.config.get_env("AUTO_BACKUP_INTERVAL") or "24h"
    last_backup = await Altruix.config.get_env("LAST_BACKUP_TIME") or "<i>Never</i>"
    log_chat = Altruix.log_chat
    
    text = Altruix.get_string("backup_manager_text").format(
        "ENABLED" if is_enabled else "DISABLED",
        interval,
        f"<code>{log_chat}</code>" if log_chat else "<i>Not Set</i>",
        last_backup
    )
    
    from Main.utils.file_helpers import get_user_button_style
    from .states import user_confirmation_state
    user_style = get_user_button_style(cb.from_user.id)
    
    await cb.edit_message_text(text, reply_markup=await get_backup_kb(user_style=user_style))

@Altruix.bot.on_callback_query(filters.regex(r"^backup_toggle_(on|off)$"))
@iuser_check
@log_errors
async def toggle_backup_handler(c: Client, cb: CallbackQuery):
    """
    Toggles the auto-backup feature on or off and refreshes the UI.
    
    Args:
        c (Client): The bot client.
        cb (CallbackQuery): The callback query.
    """
    new_status = "true" if cb.matches[0].group(1) == "on" else "false"
    # ✅ Fixed: Use upsert=True to ensure key is created if missing
    await Altruix.config.add_env_to_db("AUTO_BACKUP_ENABLED", new_status, upsert=True)
    
    await cb.answer(f"Auto-Backup {'Enabled' if new_status == 'true' else 'Disabled'}")
    await backup_manager_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^backup_set_(1h|3h|6h|12h|24h|1w)$"))
@iuser_check
@log_errors
async def set_backup_interval_handler(c: Client, cb: CallbackQuery):
    """
    Sets the auto-backup interval and refreshes the UI.
    
    Args:
        c (Client): The bot client.
        cb (CallbackQuery): The callback query.
    """
    interval = cb.matches[0].group(1)
    # ✅ Fixed: Use upsert=True to ensure key is created if missing
    await Altruix.config.add_env_to_db("AUTO_BACKUP_INTERVAL", interval, upsert=True)
    
    await cb.answer(f"Backup interval set to {interval}")
    await backup_manager_handler(c, cb)
@Altruix.bot.on_callback_query(filters.regex(r"^backup_now$"))
@iuser_check
@log_errors
async def manual_backup_handler(c: Client, cb: CallbackQuery):
    """
    Triggers a manual database backup, updates the last backup time, and refreshes the UI.
    
    Args:
        c (Client): The bot client.
        cb (CallbackQuery): The callback query.
    """
    if not Altruix.log_chat:
        return await cb.answer("❌ Log Chat ID not set! Backup failed.", show_alert=True)
    
    await cb.answer("📤 Creating backup... Please wait.")
    
    success = await upload_db_backup(Altruix.bot, Altruix.log_chat)
    if success:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # ✅ Fixed: Use upsert=True to ensure key is created if missing
        await Altruix.config.add_env_to_db("LAST_BACKUP_TIME", now_str, upsert=True)
        await cb.answer("✅ Backup uploaded to log channel!", show_alert=True)
    else:
        await cb.answer("❌ Backup failed! Check logs.", show_alert=True)
    
    # Reload dashboard to show updated "Last Backup"
    await backup_manager_handler(c, cb)
