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
from .states import (
    user_mainbot_token_state,
    user_mainbot_confirm_delete_state,
    user_mainbot_confirm_stop_state,
    user_add_backup_bot_token_state
)

logger = logging.getLogger(__name__)

# ====================== MAIN BOT MANAGER ======================

@Altruix.bot.on_callback_query(filters.regex(r"^main_bot_manager$"))
@iuser_check
@log_errors
async def main_bot_manager_cb(c: Client, cb: CallbackQuery):
    """
    Callback handler to render the Main Bot Manager dashboard.
    Clears active states and displays the primary bot assistant's information, status,
    and action control buttons (Test Connection, Update Token, Backup Bots, Stop/Delete).
    """
    if not await check_authorization(cb): 
        return
    await cb.answer()
    
    user_id = cb.from_user.id
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(user_id)
    
    # Clear any previous active states for this user to prevent state overlapping
    user_mainbot_token_state.pop(user_id, None)
    user_mainbot_confirm_delete_state.pop(user_id, None)
    user_mainbot_confirm_stop_state.pop(user_id, None)
    user_add_backup_bot_token_state.pop(user_id, None)
    
    try:
        # Attempt to get cached bot profile info or fetch it live
        me = getattr(Altruix.bot, "me", None) or await Altruix.bot.get_me()
    except Exception as e:
        logger.error(f"Could not fetch main bot info: {e}")
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
            # Live connection testing and updating bot token
            InlineKeyboardButton("🏓 Test Connection", callback_data="mbm_test_connection", style=user_style),
            InlineKeyboardButton("🔑 Update Token", callback_data="mbm_update_token", style=user_style)
        ],
        [
            # Navigation shortcut to the backup bot management submenu (Main Bot 2, 3, etc.)
            InlineKeyboardButton("🤖 Backup Bots (Main Bot 2, 3, ...)", callback_data="mbm_backup_bots_menu", style=user_style)
        ],
        [
            # Hard stop and absolute deletion controls
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
    """
    Callback handler to test connection latency of the primary Main Bot.
    Performs a fast get_me() call and displays response time in milliseconds via Telegram popup.
    """
    if not await check_authorization(cb): 
        return
    start_time = time.time()
    
    try:
        # Perform connection ping check
        await Altruix.bot.get_me()
        ping = round((time.time() - start_time) * 1000, 2)
        await cb.answer(f"✅ Connection OK! Ping: {ping}ms", show_alert=True)
    except Exception as e:
        await cb.answer(f"❌ Error pinging: {e}", show_alert=True)


@Altruix.bot.on_callback_query(filters.regex(r"^mbm_update_token$"))
@iuser_check
@log_errors
async def mbm_update_token_cb(c: Client, cb: CallbackQuery):
    """
    Callback handler that triggers the token update flow.
    Sets the user_mainbot_token_state flag and prompts the user to send the new bot token.
    """
    if not await check_authorization(cb): 
        return
    await cb.answer()
    
    user_id = cb.from_user.id
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(user_id)
    
    # Put user in token input state
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
@Altruix.bot.on_message(filters.private & ~filters.me & ~filters.bot, group=-100)
async def process_mainbot_token_input(c: Client, m: Message):
    """
    Message handler operating in high-priority group -100.
    Captures raw private messages for bot token inputs (for both primary main bot token update
    and backup main bot token registration). Handles cancellation, format validation,
    database clearing, dynamic client boot, and fallback continuation of propagation.
    """
    user_id = m.from_user.id
    
    # 1. Process Main Bot Token updates
    if user_id in user_mainbot_token_state:
        text = m.text.strip() if m.text else ""
        if text == "/cancel":
            del user_mainbot_token_state[user_id]
            await m.reply("❌ Update Token cancelled.")
            return await m.continue_propagation()
            
        # Validasi basic token format (usually ID:Hash)
        if ":" not in text or len(text) < 30:
            await m.reply("❌ Invalid token format. Please send a valid Token.")
            return m.stop_propagation()
            
        del user_mainbot_token_state[user_id]
        
        msg = await m.reply("🔄 Wait... Checking and saving token config...")
        try:
            # Write token directly to local env file
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
                    
            # Wipe token from databases so restart picks up the local .env value
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
        return

    # 2. Process Fallback Backup Bot Token additions
    elif user_id in user_add_backup_bot_token_state:
        text = m.text.strip() if m.text else ""
        if text == "/cancel":
            del user_add_backup_bot_token_state[user_id]
            await m.reply("❌ Add Backup Bot cancelled.")
            return await m.continue_propagation()
            
        if ":" not in text or len(text) < 30:
            await m.reply("❌ Invalid token format. Please send a valid Token.")
            return m.stop_propagation()
            
        del user_add_backup_bot_token_state[user_id]
        
        msg = await m.reply("🔄 Verifying and starting backup bot...")
        try:
            # Dynamically verify and register the fallback bot in memory and DB
            sec_client = await Altruix.add_secondary_bot(text)
            await msg.edit_text(f"✅ Backup Bot <b>@{sec_client.me.username}</b> successfully added and started!")
        except Exception as e:
            await msg.edit_text(f"❌ Failed to add backup bot: {e}")
            logger.error(f"Error adding backup bot token: {e}")
        m.stop_propagation()
        return

    # SANGAT PENTING: Lanjutkan ke handler berikutnya jika tidak memproses token
    return await m.continue_propagation()


# ====================== SAFE DESTRUCT CONFIRMATIONS ======================

@Altruix.bot.on_callback_query(filters.regex(r"^mbm_stop_confirm$"))
@iuser_check
@log_errors
async def mbm_stop_confirm_cb(c: Client, cb: CallbackQuery):
    """
    Callback handler displaying the confirmation menu for stopping system services.
    Alerts the user of the consequences and renders Yes/Cancel controls.
    """
    if not await check_authorization(cb): 
        return
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
    """
    Callback handler that stops the primary bot client and terminates the system execution.
    """
    if not await check_authorization(cb): 
        return
    await edit_cb(cb, "🛑 Stopping Bot Assistant...")
    # Delay allows the edit transaction and callback answer to clear
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
    """
    Callback handler displaying the confirmation menu for deleting the primary bot token.
    Warns the user that the BOT_TOKEN will be completely wiped from the config and database.
    """
    if not await check_authorization(cb): 
        return
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
    """
    Callback handler executing the absolute wipe of BOT_TOKEN from .env, MongoDB, LocalDB,
    and memory, followed by a complete system exit.
    """
    if not await check_authorization(cb): 
        return
    await edit_cb(cb, "🗑️ Deleting BOT_TOKEN from configurations and shutting down...")
    
    try:
        # Write to .env file directly to blank out the token
        import pathlib, re
        env_path = pathlib.Path().cwd().joinpath(".env")
        if env_path.exists():
            with open(env_path, "r") as f:
                raw_data = f.read()
            if re.search(r"BOT_TOKEN=(?:[^\r\n\t\f\v]+)?", raw_data):
                new_data = re.sub(r"BOT_TOKEN=(?:[^\r\n\t\f\v]+)?", "BOT_TOKEN=", raw_data)
                with open(env_path, "w") as f:
                    f.write(new_data)
                    
        # Wiping env settings from MongoDB
        if hasattr(Altruix, 'config'):
            await Altruix.config.del_env_from_db("BOT_TOKEN")
        # Wiping env settings from local JSON DB
        if hasattr(Altruix, 'local_db') and hasattr(Altruix.local_db, "env_col"):
            await Altruix.local_db.env_col.find_one_and_delete({"_id": "BOT_TOKEN"})
        
        # Erase from system process env
        if "BOT_TOKEN" in os.environ:
            del os.environ["BOT_TOKEN"]
            
    except Exception as e:
        logger.error(f"Error removing bot token: {e}")
        
    await asyncio.sleep(2)
    logger.info("BOT_TOKEN deleted by User. Shutting down system.")
    sys.exit(0)


# ====================== BACKUP BOT SUBMENU HANDLERS ======================

@Altruix.bot.on_callback_query(filters.regex(r"^mbm_backup_bots_menu$"))
@iuser_check
@log_errors
async def mbm_backup_bots_menu_cb(c: Client, cb: CallbackQuery):
    """
    Callback handler displaying the Backup Bots Manager (Main Bot 2, 3, etc.) submenu.
    Renders a list of all registered backup bots, showing their online/offline states,
    and displays action buttons for connection pings, deletion, and addition of backup bots.
    """
    import traceback
    try:
        if not await check_authorization(cb): 
            return
        await cb.answer()
        
        user_id = cb.from_user.id
        from Main.utils.file_helpers import get_user_button_style
        user_style = get_user_button_style(user_id)
        
        # Clear backup bot token input state on opening the menu
        user_add_backup_bot_token_state.pop(user_id, None)
        
        # Retrieve all registered backup bots from the collection
        col = Altruix.db.make_collection("secondary_main_bots")
        backup_docs = []
        try:
            async for doc in col.find({}):
                backup_docs.append(doc)
        except Exception as e:
            tb = traceback.format_exc()
            logger.error(f"Error fetching secondary bots: {e}\n{tb}")
            
        text = (
            "<b>🤖 Secondary Bot Manager (Backup Bots)</b>\n\n"
            "Here you can manage fallback bot assistants (Main Bot 2, 3, etc.).\n"
            "If the primary bot hits a <b>FloodWait</b> error, the system will automatically "
            "switch to backup bots to ensure logs are sent safely.\n\n"
            "<b>Current Status:</b>\n"
            f"• <b>Primary Bot:</b> 🟢 Active (@{Altruix.bot_info.username if Altruix.bot_info else 'Unknown'})\n"
        )
        
        if backup_docs:
            text += "• <b>Backup Bots:</b>\n"
            for i, doc in enumerate(backup_docs, 2):
                bot_id = doc["_id"]
                username = doc.get("username", "Unknown")
                first_name = doc.get("first_name", "Backup Bot")
                
                # Verify active connection status of the secondary bot in running memory
                is_active = False
                for b in getattr(Altruix, "secondary_bots", []):
                    if b.me and b.me.id == bot_id and b.is_connected:
                        is_active = True
                        break
                
                status_indicator = "🟢 Running" if is_active else "🔴 Inactive"
                text += f"  {i}. <b>{html.escape(first_name)}</b> (@{username}) | <code>{bot_id}</code> - {status_indicator}\n"
        else:
            text += "• <b>Backup Bots:</b> <i>No backup bots added yet.</i>\n"
            
        text += "\n<i>Select an action below:</i>"
        
        buttons = []
        
        # Generate operational buttons for each registered backup bot
        for doc in backup_docs:
            bot_id = doc["_id"]
            username = doc.get("username", "bot")
            buttons.append([
                InlineKeyboardButton(f"🏓 Ping @{username}", callback_data=f"mbm_ping_sec_{bot_id}", style=user_style),
                InlineKeyboardButton(f"🗑️ Delete", callback_data=f"mbm_delete_sec_{bot_id}", style=user_style)
            ])
            
        # Navigation and controls buttons
        buttons.append([
            InlineKeyboardButton("➕ Add Backup Bot", callback_data="mbm_add_backup_bot", style=user_style)
        ])
        buttons.append([
            InlineKeyboardButton("🔙 Back to Main Bot", callback_data="main_bot_manager", style=user_style)
        ])
        
        await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"Critical error in mbm_backup_bots_menu_cb: {e}\n{tb}")
        await cb.answer(f"❌ Error loading menu: {e}", show_alert=True)


@Altruix.bot.on_callback_query(filters.regex(r"^mbm_ping_sec_(?P<bot_id>\d+)$"))
@iuser_check
@log_errors
async def mbm_ping_sec_cb(c: Client, cb: CallbackQuery):
    """
    Callback handler to test connection latency (ping test) of a secondary backup bot.
    Flashes the connection response time in milliseconds to the user via Telegram alert.
    """
    import traceback
    try:
        if not await check_authorization(cb): 
            return
        bot_id = int(cb.matches[0].group("bot_id"))
        
        # Locate the targeted secondary bot instance in active memory
        sec_bot = None
        for b in getattr(Altruix, "secondary_bots", []):
            if b.me and b.me.id == bot_id:
                sec_bot = b
                break
                
        if not sec_bot or not sec_bot.is_connected:
            await cb.answer("❌ This backup bot is not currently connected/active.", show_alert=True)
            return
            
        start_time = time.time()
        try:
            # Issue connection ping request
            await sec_bot.get_me()
            ping = round((time.time() - start_time) * 1000, 2)
            await cb.answer(f"✅ @{sec_bot.me.username} Connection OK! Ping: {ping}ms", show_alert=True)
        except Exception as e:
            tb = traceback.format_exc()
            logger.error(f"Error pinging secondary bot: {e}\n{tb}")
            await cb.answer(f"❌ Error pinging: {e}", show_alert=True)
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"Critical error in mbm_ping_sec_cb: {e}\n{tb}")
        await cb.answer(f"❌ Critical error during ping check: {e}", show_alert=True)


@Altruix.bot.on_callback_query(filters.regex(r"^mbm_delete_sec_(?P<bot_id>\d+)$"))
@iuser_check
@log_errors
async def mbm_delete_sec_cb(c: Client, cb: CallbackQuery):
    """
    Callback handler that stops, deletes, and unlinks a secondary backup bot dynamically
    from memory and database. Instantly refreshes the submenu afterwards.
    """
    import traceback
    try:
        if not await check_authorization(cb): 
            return
        bot_id = int(cb.matches[0].group("bot_id"))
        
        # Retrieve backup bot details from collection to format the result message
        col = Altruix.db.make_collection("secondary_main_bots")
        doc = await col.find_one({"_id": bot_id})
        username = doc.get("username", "bot") if doc else "bot"
        
        try:
            # Dynamically delete and teardown the client without requiring system restart
            await Altruix.delete_secondary_bot(bot_id)
            await cb.answer(f"🗑️ Deleted backup bot @{username} successfully!", show_alert=True)
        except Exception as e:
            tb = traceback.format_exc()
            logger.error(f"Error stopping/deleting secondary bot client: {e}\n{tb}")
            await cb.answer(f"❌ Failed to delete backup bot: {e}", show_alert=True)
            
        # Reload the backup bots management submenu with the updated list
        await mbm_backup_bots_menu_cb(c, cb)
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"Critical error in mbm_delete_sec_cb: {e}\n{tb}")
        await cb.answer(f"❌ Critical error during deletion: {e}", show_alert=True)


@Altruix.bot.on_callback_query(filters.regex(r"^mbm_add_backup_bot$"))
@iuser_check
@log_errors
async def mbm_add_backup_bot_cb(c: Client, cb: CallbackQuery):
    """
    Callback handler initiating the fallback backup bot token registration process.
    Puts the user into user_add_backup_bot_token_state and prompts them for the token input.
    """
    import traceback
    try:
        if not await check_authorization(cb): 
            return
        await cb.answer()
        
        user_id = cb.from_user.id
        from Main.utils.file_helpers import get_user_button_style
        user_style = get_user_button_style(user_id)
        
        # Trigger the add secondary bot token state
        user_add_backup_bot_token_state[user_id] = True
        
        text = (
            "<b>➕ Add Backup Bot Token</b>\n\n"
            "Please send the Telegram Bot Token for your backup bot (provided by @BotFather).\n"
            "The system will verify, start, and register this bot as a fallback log sender dynamically.\n\n"
            "<i>Type /cancel to abort.</i>"
        )
        
        await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Cancel", callback_data="mbm_backup_bots_menu", style=user_style)]
        ]))
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"Critical error in mbm_add_backup_bot_cb: {e}\n{tb}")
        await cb.answer(f"❌ Error opening add bot screen: {e}", show_alert=True)
