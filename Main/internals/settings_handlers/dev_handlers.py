# Main/internals/settings_handlers/dev_handlers.py
import html
import os
import asyncio
import logging
import traceback
import sys
import io
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from Main.core.decorators import log_errors, iuser_check
from Main.core.client import Altruix
from pyrogram.enums import ParseMode

# Shared State
from .states import user_profile_edit_state

logger = logging.getLogger(__name__)

async def aexec(code, c, m):
    exec(
        f"async def __aexec(c, m): "
        + "".join(f"\n {l}" for l in code.split("\n"))
    )
    return await locals()["__aexec"](c, m)

async def process_dev_input(c: Client, m: Message, state: dict):
    """Router for developer tools (eval, terminal)"""
    action = state['action']
    index = state['session_index']
    text = m.text.strip()
    user_id = m.from_user.id
    
    session_client = Altruix.clients[index]
    
    try:
        if action == 'eval_python':
            status_msg = await m.reply("🐍 Evaluating...")
            old_stderr, old_stdout = sys.stderr, sys.stdout
            redirected_output = sys.stdout = io.StringIO()
            redirected_error = sys.stderr = io.StringIO()
            stdout, stderr, exc = None, None, None
            try:
                await aexec(text, session_client, m)
            except Exception:
                exc = traceback.format_exc()
            stdout, stderr = redirected_output.getvalue(), redirected_error.getvalue()
            sys.stdout, sys.stderr = old_stdout, old_stderr
            evaluation = exc or stderr or stdout or "Success"
            await status_msg.edit(f"🐍 <b>Output:</b>\n\n<code>{html.escape(evaluation)}</code>")
            
        elif action == 'exec_terminal':
            status_msg = await m.reply("💻 Executing...")
            process = await asyncio.create_subprocess_shell(
                text,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            result = (stdout.decode().strip() or stderr.decode().strip()) or "No output"
            await status_msg.edit(f"💻 <b>Output:</b>\n\n<code>{result}</code>")
            
    except Exception as e:
        await m.reply(f"❌ <b>Error:</b> {str(e)}")
        
    del user_profile_edit_state[user_id]
    await asyncio.sleep(2)
    await m.reply("🔄 Kembali ke menu...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"session_info_{index}_{state.get('page', 1)}")]]) )
