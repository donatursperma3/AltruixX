# Main/internals/settings_handlers/main_bot_manager.py
import html
import os
import asyncio
import logging
import time
import sys
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode

from Main.core.decorators import log_errors, iuser_check
from Main.core.client import Altruix

# Utils & States
from .utils import edit_cb, check_authorization, send_log_notification
from .states import user_mainbot_token_state, user_mainbot_confirm_delete_state, user_mainbot_confirm_stop_state

logger = logging.getLogger(__name__)

# ====================== MAIN BOT MANAGER ======================
@Altruix.bot.on_callback_query(filters.regex(r"^main_bot_manager$"))
@iuser_check
@log_errors
async def main_bot_manager_cb(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer()
    
    user_id = cb.from_user.id
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(user_id)
    
    # Clear any previous states
    user_mainbot_token_state.pop(user_id, None)
    user_mainbot_confirm_delete_state.pop(user_id, None)
    user_mainbot_confirm_stop_state.pop(user_id, None)
    
    try:
        me = getattr(Altruix.bot, "me", None) or await Altruix.bot.get_me()
    except Exception as e:
        logger.error(f"Could not fetch main bot me: {e}")
        me = None
        
    if not me:
        await cb.answer("Failed to fetch Bot Information", show_alert=True)
        return
    
    bot_name = me.first_name or "Bot Assistant"
    bot_username = f"@{me.username}" if me.username else "No Username"
    bot_id = me.id
    
    text = (
        "<b>🤖 Main Bot Manager</b>\n\n"
        f"<b>Name:</b> {html.escape(bot_name)}\n"
        f"<b>Username:</b> {bot_username}\n"
        f"<b>ID:</b> <code>{bot_id}</code>\n"
        "<b>Status:</b> 🟢 Running\n\n"
        "<i>Select an action below to manage your Bot Assistant:</i>"
    )
    
    buttons = [
        [
            InlineKeyboardButton("🏓 Test Connection", callback_data="mbm_test_connection", style=user_style),
            InlineKeyboardButton("🔑 Update Token", callback_data="mbm_update_token", style=user_style)
        ],
        [
            InlineKeyboardButton("🛑 Stop Bot", callback_data="mbm_stop_confirm", style=user_style),
            InlineKeyboardButton("🗑️ Delete Bot", callback_data="mbm_delete_confirm", style=user_style)
        ],
        [
            InlineKeyboardButton("🔙 Back to Bot Controls", callback_data="bot_controls_menu", style=user_style)
        ]
    ]
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons))

@Altruix.bot.on_callback_query(filters.regex(r"^mbm_test_connection$"))
@iuser_check
@log_errors
async def mbm_test_connection_cb(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    start_time = time.time()
    
    try:
        # Ping check
        await Altruix.bot.get_me()
        ping = round((time.time() - start_time) * 1000, 2)
        await cb.answer(f"✅ Connection OK! Ping: {ping}ms", show_alert=True)
    except Exception as e:
        await cb.answer(f"❌ Error pinging: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^mbm_update_token$"))
@iuser_check
@log_errors
async def mbm_update_token_cb(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer()
    
    user_id = cb.from_user.id
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(user_id)
    
    user_mainbot_token_state[user_id] = True
    
    text = (
        "<b>🔑 Update Bot Token</b>\n\n"
        "Please send the new Telegram Bot Token provided by @BotFather.\n"
        "Wait for the confirmation message.\n\n"
        "<i>Type /cancel to abort.</i>"
    )
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Cancel", callback_data="main_bot_manager", style=user_style)]
    ]))

# Message handler for Token Input
@Altruix.bot.on_message(filters.private & ~filters.me & ~filters.bot, group=-1)
async def process_mainbot_token_input(c: Client, m: Message):
    user_id = m.from_user.id
    if user_id not in user_mainbot_token_state:
        return m.continue_propagation()
        
    text = m.text.strip() if m.text else ""
    if text == "/cancel":
        del user_mainbot_token_state[user_id]
        await m.reply("❌ Update Token cancelled.")
        return m.continue_propagation()
        
    # Validasi basic token format (usually ID:Hash)
    if ":" not in text or len(text) < 30:
        await m.reply("❌ Invalid token format. Please send a valid Token.")
        return m.stop_propagation()
        
    del user_mainbot_token_state[user_id]
    
    msg = await m.reply("🔄 Wait... Checking and saving token config...")
    try:
        # Menulis perubahan langsung ke file .env
        import pathlib, re
        env_path = pathlib.Path().cwd().joinpath(".env")
        if env_path.exists():
            with open(env_path, "r") as f:
                raw_data = f.read()
            if re.search(r"BOT_TOKEN=(?:[^\r\n\t\f\v]+)?", raw_data):
                new_data = re.sub(r"BOT_TOKEN=(?:[^\r\n\t\f\v]+)?", f"BOT_TOKEN={text}", raw_data)
            else:
                new_data = f"{raw_data}\nBOT_TOKEN={text}"
            with open(env_path, "w") as f:
                f.write(new_data)
                
        # Menghapus dari database agar tidak menimpa nilai .env saat restart
        if hasattr(Altruix, "config"):
            await Altruix.config.del_env_from_db("BOT_TOKEN")
        if hasattr(Altruix, "local_db") and hasattr(Altruix.local_db, "env_col"):
            await Altruix.local_db.env_col.find_one_and_delete({"_id": "BOT_TOKEN"})
            
        await msg.edit_text("✅ Token has been successfully updated!\n\n<i>To apply changes, the bot requires a restart.</i>\nRestarting now...")
        await asyncio.sleep(2)
        os.execl(sys.executable, sys.executable, "-m", "Main")
    except Exception as e:
        await msg.edit_text(f"❌ Failed to update token: {e}")
        logger.error(f"Error updating BOT_TOKEN: {e}")
    m.stop_propagation()

# ====================== SAFE DESTRUCT CONFIRMATIONS ======================

@Altruix.bot.on_callback_query(filters.regex(r"^mbm_stop_confirm$"))
@iuser_check
@log_errors
async def mbm_stop_confirm_cb(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer()
    
    user_id = cb.from_user.id
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(user_id)
    
    text = (
        "<b>🛑 Stop System Services</b>\n\n"
        "Are you sure you want to stop the Bot Assistant and all services? "
        "You will no longer be able to use Sudo/Bot features until you manually start it in your console."
    )
    
    buttons = [
        [
            InlineKeyboardButton("✅ Yes", callback_data="mbm_stop_execute", style=user_style),
            InlineKeyboardButton("❌ Cancel", callback_data="main_bot_manager", style=user_style)
        ]
    ]
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons))

@Altruix.bot.on_callback_query(filters.regex(r"^mbm_stop_execute$"))
@iuser_check
@log_errors
async def mbm_stop_execute_cb(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await edit_cb(cb, "🛑 Stopping Bot Assistant...")
    # Delay allows callback answer to be sent
    await asyncio.sleep(1)
    
    try:
        await Altruix.bot.stop()
    except Exception as e:
        logger.error(f"Error stopping bot client: {e}")
        
    logger.info("Bot stopped by User via Main Bot Manager. Exiting.")
    sys.exit(0)

@Altruix.bot.on_callback_query(filters.regex(r"^mbm_delete_confirm$"))
@iuser_check
@log_errors
async def mbm_delete_confirm_cb(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer()
    
    user_id = cb.from_user.id
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(user_id)
    
    text = (
        "<b>🗑️ Delete Bot Assistant!</b>\n\n"
        "⚠️ <b>WARNING:</b> This will completely delete the <code>BOT_TOKEN</code> from your environment configuration and shutdown the program.\n\n"
        "You will need to manually configure the bot token again from the console. Are you absolutely certain?"
    )
    
    buttons = [
        [
            InlineKeyboardButton("✅ Yes, Delete & Shutdown", callback_data="mbm_delete_execute", style=user_style),
            InlineKeyboardButton("❌ Cancel", callback_data="main_bot_manager", style=user_style)
        ]
    ]
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons))

@Altruix.bot.on_callback_query(filters.regex(r"^mbm_delete_execute$"))
@iuser_check
@log_errors
async def mbm_delete_execute_cb(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await edit_cb(cb, "🗑️ Deleting BOT_TOKEN from configurations and shutting down...")
    
    try:
        # Menulis perubahan langsung ke file .env untuk mengosongkannya
        import pathlib, re
        env_path = pathlib.Path().cwd().joinpath(".env")
        if env_path.exists():
            with open(env_path, "r") as f:
                raw_data = f.read()
            if re.search(r"BOT_TOKEN=(?:[^\r\n\t\f\v]+)?", raw_data):
                new_data = re.sub(r"BOT_TOKEN=(?:[^\r\n\t\f\v]+)?", "BOT_TOKEN=", raw_data)
                with open(env_path, "w") as f:
                    f.write(new_data)
                    
        # Menghapus env dari MongoDB
        if hasattr(Altruix, 'config'):
            await Altruix.config.del_env_from_db("BOT_TOKEN")
        # Menghapus env dari lokalisasi (json)
        if hasattr(Altruix, 'local_db') and hasattr(Altruix.local_db, "env_col"):
            await Altruix.local_db.env_col.find_one_and_delete({"_id": "BOT_TOKEN"})
        
        # Hapus juga dari os.environ jika ada
        if "BOT_TOKEN" in os.environ:
            del os.environ["BOT_TOKEN"]
            
    except Exception as e:
        logger.error(f"Error removing bot token: {e}")
        
    await asyncio.sleep(2)
    logger.info("BOT_TOKEN deleted by User. Shutting down system.")
    sys.exit(0)
