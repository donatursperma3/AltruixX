# Main/internals/settings_handlers/system_handlers.py
import os
import sys
import subprocess
import logging
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery
from Main.core.decorators import log_errors, iuser_check
from Main.core.client import Altruix

# Utils
from .utils import check_authorization

# Logger
logger = logging.getLogger(__name__)

# ====================== SYSTEM CONTROL HANDLERS ======================
@Altruix.bot.on_callback_query(filters.regex("^sys_ctrl_restart$"))
@iuser_check
@log_errors
async def sys_restart_handler(c: Client, cb: CallbackQuery):
    """Handler for Force Restart"""
    if not await check_authorization(cb): return
    await cb.answer("Restarting AltruixX...", show_alert=True)
    try:
        args = [sys.executable, "-m", "Main"]
        if os.name == 'nt':
            subprocess.Popen(args, creationflags=subprocess.CREATE_NEW_CONSOLE)
            sys.exit(0)
        else:
            os.execv(sys.executable, args)
    except Exception as e:
        logger.error(f"Failed to restart: {e}")
        await cb.answer(f"Failed to restart: {e}", show_alert=True)

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
