# Main/internals/settings_handlers/backup_handlers.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
# All rights reserved.

import os
import asyncio
import json
import shutil
import logging
import html
import zipfile
from Main import Altruix
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
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
        [
            InlineKeyboardButton("📥 Restore DB", callback_data="backup_restore", style=user_style),
            InlineKeyboardButton("➕ Append DB", callback_data="backup_append", style=user_style)
        ],
        [InlineKeyboardButton("♻️ Restart System", callback_data="backup_restart_confirm", style=user_style)],
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

# =========================================================================
# RESTORE & APPEND DATABASE HANDLERS
# =========================================================================
import shutil
import zipfile
import json
from Main.utils.file_helpers import get_db_path
from .states import user_backup_restore_state

@Altruix.bot.on_callback_query(filters.regex(r"^backup_(restore|append)$"))
@iuser_check
@log_errors
async def backup_restore_append_cb(c: Client, cb: CallbackQuery):
    action = cb.matches[0].group(1) # "restore" or "append"
    await cb.answer()
    
    user_id = cb.from_user.id
    user_backup_restore_state[user_id] = {'action': action}
    
    if action == "restore":
        text = "📥 **Restore Database**\n\nSilakan kirim file `.zip` backup database Anda.\n⚠️ **PERINGATAN:** Semua data yang ada di database saat ini akan ditimpa (overwrite) oleh data dari backup!\n\nKetik `/cancel` untuk membatalkan."
    else:
        text = "➕ **Append Database**\n\nSilakan kirim file `.zip` backup database Anda.\nData JSON akan digabungkan, dan file yang belum ada akan ditambahkan tanpa menghapus data Anda saat ini.\n\nKetik `/cancel` untuk membatalkan."
    
    from pyrogram.enums import ParseMode
    await cb.message.reply(text, parse_mode=ParseMode.MARKDOWN)

# =========================================================================
# SYSTEM RESTART CONFIRMATION
# Note: The "Yes" button triggers "sys_ctrl_restart" which is handled in 
# Main/internals/settings_handlers/system_handlers.py to avoid code duplication.
# =========================================================================
@Altruix.bot.on_callback_query(filters.regex(r"^backup_restart_confirm$"))
@iuser_check
@log_errors
async def backup_restart_confirm_cb(c: Client, cb: CallbackQuery):
    from Main.utils.file_helpers import get_user_button_style
    from pyrogram.enums import ParseMode
    user_style = get_user_button_style(cb.from_user.id)
    
    text = "⚠️ **Konfirmasi Restart System**\n\nApakah Anda yakin ingin melakukan System Restart sekarang?\nHal ini akan me-refresh seluruh cache memori ke database."
    
    buttons = [
        [
            InlineKeyboardButton("✅ Yes", callback_data="sys_ctrl_restart", style=user_style),
            InlineKeyboardButton("❌ No", callback_data="backup_manager", style=user_style)
        ]
    ]
    
    await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.MARKDOWN)

async def _merge_json(target_path, source_path):
    """
    Deep merge two JSON files. target_path is modified in-place.
    """
    def deep_merge(target, source):
        if isinstance(target, dict) and isinstance(source, dict):
            for key, value in source.items():
                if key in target:
                    target[key] = deep_merge(target[key], value)
                else:
                    target[key] = value
        elif isinstance(target, list) and isinstance(source, list):
            # For lists, we append new unique items
            for item in source:
                if item not in target:
                    target.append(item)
        else:
            # Different types or non-containers, source overwrites
            return source
        return target

    # Read target
    if os.path.exists(target_path):
        try:
            with open(target_path, 'r', encoding='utf-8') as f:
                target_data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to read target DB {target_path}: {e}")
            return False # Don't overwrite with empty if we can't read it!
    else:
        target_data = {}
        
    # Read source
    try:
        with open(source_path, 'r', encoding='utf-8') as f:
            source_data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to read source DB {source_path}: {e}")
        return False
        
    # LOG: specifically track custom_bots if present
    if "custom_bots" in target_data:
        logger.info(f"Merging DB: Found {len(target_data['custom_bots'])} custom bots in current database.")
    if "custom_bots" in source_data:
        logger.info(f"Merging DB: Found {len(source_data['custom_bots'])} custom bots in source backup.")

    merged_data = deep_merge(target_data, source_data)
    
    if "custom_bots" in merged_data:
        logger.info(f"Merging DB: Total custom bots after merge: {len(merged_data['custom_bots'])}")
        
    with open(target_path, 'w', encoding='utf-8') as f:
        json.dump(merged_data, f, indent=4)
    return True

async def process_backup_restore_input(c: Client, m: Message, state: dict):
    from pyrogram.enums import ParseMode
    msg = await m.reply("⏳ <b>Sedang memproses file backup...</b>", parse_mode=ParseMode.HTML)
    user_id = m.from_user.id
    
    try:
        action = state.get("action")
        
        if not m.document or not m.document.file_name.endswith(".zip"):
            await msg.edit("❌ <b>File tidak valid!</b> Silakan kirim file <code>.zip</code> backup database.")
            return

        # Download ZIP
        dl_path = await m.download()
        
        # Validation: Check ZIP contents
        is_valid = False
        try:
            with zipfile.ZipFile(dl_path, 'r') as z:
                # Check if it has any .json file
                namelist = z.namelist()
                if any(f.endswith('.json') for f in namelist):
                    is_valid = True
                
                # Special check for Restore: must have altruix_local_db.json
                if action == "restore" and "altruix_local_db.json" not in namelist:
                    # Look for it in subdirectories too
                    if not any(f.endswith("altruix_local_db.json") for f in namelist):
                        await msg.edit("⚠️ <b>Peringatan:</b> File <code>altruix_local_db.json</code> tidak ditemukan dalam ZIP.\nRestore ini mungkin tidak lengkap.")
                        await asyncio.sleep(2)
        except Exception as ze:
            await msg.edit(f"❌ <b>ZIP Rusak:</b> {ze}")
            if os.path.exists(dl_path): os.remove(dl_path)
            return

        if not is_valid:
            await msg.edit("❌ <b>ZIP tidak valid!</b> Backup harus berisi setidaknya satu file <code>.json</code>.")
            if os.path.exists(dl_path): os.remove(dl_path)
            return

        db_dir = get_db_path("")
        
        # ✅ SYNC: Ensure memory is saved to disk before we start reading it for merge/restore
        if hasattr(Altruix, 'local_db'):
            await Altruix.local_db.save_now()
            
        if not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            
        if action == "restore":
            await msg.edit("📥 <b>Restoring database...</b>\nMohon tunggu sejenak.")
            
            # Atomic Restore: Extract and reload while holding the lock
            if hasattr(Altruix, 'local_db') and hasattr(Altruix.local_db, 'safe_extract_and_reload'):
                await Altruix.local_db.safe_extract_and_reload(dl_path, db_dir)
            else:
                # Fallback if not using LocalDatabase
                await asyncio.to_thread(shutil.unpack_archive, dl_path, db_dir, 'zip')
            
            # Reload Config
            await Altruix.config.get_sudo()
            await Altruix.config.get_owners()
            
            await msg.edit("✅ <b>Database Berhasil Di-Restore!</b>\nSistem akan segera melakukan soft-restart untuk sinkronisasi seluruh session.")
            await asyncio.sleep(2)
            
            # Trigger Soft Reboot
            await Altruix.reboot(soft=False, last_msg=m)
            
        elif action == "append":
            await msg.edit("➕ <b>Appending database...</b>\nMerging JSON files.")
            
            # Extract to temp directory
            temp_dir = os.path.join(os.getcwd(), f"temp_append_{user_id}")
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            os.makedirs(temp_dir, exist_ok=True)
            
            await asyncio.to_thread(shutil.unpack_archive, dl_path, temp_dir, 'zip')
            
            merged_count = 0
            new_files = 0
            
            # Perform merging inside the DB lock to prevent background saves from overwriting
            async with Altruix.local_db.lock:
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        src = os.path.join(root, file)
                        rel_path = os.path.relpath(src, temp_dir)
                        tgt = os.path.join(db_dir, rel_path)
                        
                        if not os.path.exists(tgt):
                            os.makedirs(os.path.dirname(tgt), exist_ok=True)
                            shutil.copy2(src, tgt)
                            new_files += 1
                        else:
                            if file.endswith('.json'):
                                await _merge_json(tgt, src)
                                merged_count += 1
                
                # Reload LocalDB memory immediately after merge while still locked
                if hasattr(Altruix, 'local_db') and hasattr(Altruix.local_db, 'reload'):
                    # We don't call reload() here because it also tries to acquire the lock.
                    # Instead, we call the internal _load() or I should have made reload() not acquire lock if already held.
                    # Since reload() uses "async with self._lock", it will deadlock if we call it here.
                    # Let's use the internal _load()
                    Altruix.local_db._load()
            
            # Cleanup temp
            shutil.rmtree(temp_dir, ignore_errors=True)

            await msg.edit(
                f"✅ <b>Database Berhasil Di-Append!</b>\n"
                f"• {new_files} file baru ditambahkan.\n"
                f"• {merged_count} file JSON digabungkan.\n\n"
                "Sistem akan segera melakukan soft-restart untuk sinkronisasi."
            )
            await asyncio.sleep(2)
            await Altruix.reboot(soft=False, last_msg=m)
            
        if os.path.exists(dl_path):
            os.remove(dl_path)
            
    except Exception as e:
        import traceback
        logger.error(f"Backup operation failed: {traceback.format_exc()}")
        await msg.edit(f"❌ <b>Terjadi Kesalahan:</b>\n<code>{html.escape(str(e))}</code>", parse_mode=ParseMode.HTML)
    finally:
        if user_id in user_backup_restore_state:
            del user_backup_restore_state[user_id]

