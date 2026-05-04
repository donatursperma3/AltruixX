# Main/internals/settings_handlers/system_handlers.py
import os
import sys
import subprocess
import logging
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from Main.core.decorators import log_errors, iuser_check
from Main.core.client import Altruix
from Main.utils.file_helpers import get_user_button_style

# Utils
from .utils import check_authorization, edit_cb

# Logger
logger = logging.getLogger(__name__)

# =========================================================================
# SYSTEM RESTART HANDLER
# This function is responsible for replacing the current process with a new 
# instance of the bot. It uses os.execv to ensure the process ID is 
# swapped natively where possible, or spawns a new process on Windows.
# =========================================================================
@Altruix.bot.on_callback_query(filters.regex("^sys_ctrl_restart$"))
@iuser_check
@log_errors
async def sys_restart_menu_handler(c: Client, cb: CallbackQuery):
    """Confirmation menu for Restart"""
    if not await check_authorization(cb): return
    await cb.answer()
    
    user_style = get_user_button_style(cb.from_user.id)
    text = (
        f"<blockquote expandable>"
        "<b>🔄 System Restart Controls</b>\n\n"
        "Pilih metode restart yang diinginkan:\n\n"
        "🚀 <b>Soft Restart (Optimized):</b> Restart koneksi semua session dan muat ulang plugin. Sangat cepat.\n"
        "⚙️ <b>Full Restart (Hard):</b> Mengganti proses sistem secara keseluruhan. Gunakan jika ada update pada file core.\n"
        "♻️ <b>Reload Plugins:</b> Hanya muat ulang file plugin tanpa memutuskan koneksi."
        f"</blockquote>"
    )
    
    buttons = [
        [
            InlineKeyboardButton("🚀 Soft Restart", callback_data="sys_ctrl_restart_soft", style=user_style),
        ],
        [
            InlineKeyboardButton("⚙️ Full Restart (Hard)", callback_data="sys_ctrl_restart_hard", style=user_style),
        ],
        [
            InlineKeyboardButton("♻️ Reload Plugins", callback_data="sys_ctrl_reload", style=user_style),
        ],
        [
            InlineKeyboardButton("🔙 Cancel", callback_data="bulk_controls_menu", style=user_style)
        ]
    ]
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons))

@Altruix.bot.on_callback_query(filters.regex("^sys_ctrl_restart_hard$"))
@iuser_check
@log_errors
async def sys_restart_hard_handler(c: Client, cb: CallbackQuery):
    """Handler for Hard Restart (Process Replacement)"""
    if not await check_authorization(cb): return
    await cb.answer("Performing Hard Restart...", show_alert=True)
    await edit_cb(cb, "<b>⚙️ Hard Restart Initiated...</b>\nReplacing process. Please wait.")
    try:
        args = [sys.executable, "-m", "Main"]
        if os.name == 'nt':
            # on windows, use subprocess. Popen to restart the process
            subprocess.Popen(args, close_fds=True)
            os._exit(0)
        else:
            # On Linux/Unix, os.execv is the standard way to replace the process.
            os.execv(sys.executable, args)
    except Exception as e:
        logger.error(f"Failed to restart: {e}")
        await cb.answer(f"Failed to restart: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex("^sys_ctrl_restart_soft$"))
@iuser_check
@log_errors
async def sys_restart_soft_handler(c: Client, cb: CallbackQuery):
    """Handler for Soft Restart (Optimized within process)"""
    if not await check_authorization(cb): return
    await cb.answer("Performing Soft Restart...", show_alert=True)
    await edit_cb(cb, "<b>🚀 Soft Restart Initiated...</b>\nRestarting sessions in parallel. Please wait.")
    await Altruix.reboot(soft=False, last_msg=cb)

@Altruix.bot.on_callback_query(filters.regex("^sys_ctrl_reload$"))
@iuser_check
@log_errors
async def sys_reload_handler(c: Client, cb: CallbackQuery):
    """Handler for Reloading Plugins Only"""
    if not await check_authorization(cb): return
    await cb.answer("Reloading Plugins...", show_alert=True)
    await edit_cb(cb, "<b>♻️ Reloading Plugins...</b>\nUpdating command registry. Please wait.")
    await Altruix.reboot(soft=True, last_msg=cb)

@Altruix.bot.on_callback_query(filters.regex("^sys_ctrl_shutdown$"))
@iuser_check
@log_errors
async def sys_shutdown_handler(c: Client, cb: CallbackQuery):
    """Handler for Force Shutdown"""
    if not await check_authorization(cb): return
    await cb.answer("Shutting down AltruixX...", show_alert=True)
    try:
        sys.exit(0)
    except:
        pass
