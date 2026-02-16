# Main/internals/settings_handlers/cmd_settings_handlers.py
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from Main.core.decorators import log_errors, iuser_check
from Main.core.client import Altruix
from .utils import edit_cb, check_authorization

@Altruix.bot.on_callback_query(filters.regex(r"^cmd_settings_menu(?:_(?P<idx>\d+)_(?P<pg>\d+))?$"))
@iuser_check
@log_errors
async def cmd_settings_menu_handler(c: Client, cb: CallbackQuery):
    """Main menu for command settings (Auto-Delete & Delay)"""
    if not await check_authorization(cb): return
    await cb.answer()

    match = cb.matches[0]
    idx = match.group("idx")
    pg = match.group("pg")

    if idx is not None:
        # If accessed from session info, redirect to account-specific settings directly
        return await cmd_account_settings_handler(c, cb, int(idx), int(pg))

    # Get global settings
    global_status = await Altruix.config.get_env("AUTO_DELETE_CMD_GLOBAL") or "off"
    global_delay = await Altruix.config.get_env("AUTO_DELETE_CMD_DELAY_GLOBAL") or "2"
    
    text = (
        "<b>⌨️ Command Settings (Global)</b>\n\n"
        "Configure how the userbot handles command messages after execution.\n\n"
        f"• <b>Global Auto-Delete:</b> <code>{global_status.upper()}</code>\n"
        f"• <b>Global Delay:</b> <code>{global_delay}s</code>\n\n"
        "<i>Note: Per-account settings can override global settings if configured.</i>"
    )

    buttons = [
        [
            InlineKeyboardButton(f"Auto-Delete: {global_status.upper()}", callback_data="toggle_auto_delete_global"),
        ],
        [
            InlineKeyboardButton("-2s", callback_data="adj_delay_global_m2"),
            InlineKeyboardButton(f"Delay: {global_delay}s", callback_data="none"),
            InlineKeyboardButton("+2s", callback_data="adj_delay_global_p2"),
        ],
        [
            InlineKeyboardButton("📱 Per-Account Settings", callback_data="cmd_sessions_list_1"),
        ],
        [InlineKeyboardButton("🔙 Back to Settings", callback_data="settings_menu")]
    ]
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons))

@Altruix.bot.on_callback_query(filters.regex(r"^toggle_auto_delete_global$"))
@iuser_check
@log_errors
async def toggle_auto_delete_global_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    
    current = await Altruix.config.get_env("AUTO_DELETE_CMD_GLOBAL") or "off"
    new_status = "on" if current.lower() == "off" else "off"
    
    await Altruix.config.sync_env_to_db("AUTO_DELETE_CMD_GLOBAL", new_status, upsert=True)
    await cb.answer(f"Global Auto-Delete: {new_status.upper()}", show_alert=True)
    await cmd_settings_menu_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^adj_delay_global_(?P<act>m2|p2)$"))
@iuser_check
@log_errors
async def adj_delay_global_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    
    act = cb.matches[0].group("act")
    current = int(await Altruix.config.get_env("AUTO_DELETE_CMD_DELAY_GLOBAL") or 2)
    
    if act == "m2":
        new_delay = max(0, current - 2)
    else:
        new_delay = current + 2
        
    await Altruix.config.sync_env_to_db("AUTO_DELETE_CMD_DELAY_GLOBAL", str(new_delay), upsert=True)
    await cb.answer(f"Global Delay: {new_delay}s")
    await cmd_settings_menu_handler(c, cb)

# Per-Account List
@Altruix.bot.on_callback_query(filters.regex(r"^cmd_sessions_list_(\d+)$"))
@iuser_check
@log_errors
async def cmd_sessions_list_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer()
    page = int(cb.matches[0].group(1))
    
    text = "<b>📱 Per-Account Command Settings</b>\nSelect an account to configure specific settings."
    
    buttons = []
    for i, client in enumerate(Altruix.clients):
        try:
            me = getattr(client, "myself", None) or client.me
            name = f"{me.first_name} ({i})"
            buttons.append([InlineKeyboardButton(name, callback_data=f"cmd_account_set_{i}")])
        except: continue
        
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="cmd_settings_menu")])
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons))

@Altruix.bot.on_callback_query(filters.regex(r"^cmd_account_set_(?P<idx>\d+)(?:_(?P<pg>\d+))?$"))
@iuser_check
@log_errors
async def cmd_account_settings_handler(c: Client, cb: CallbackQuery, index: int = None, page: int = 1):
    if not await check_authorization(cb): return
    await cb.answer()
    
    if index is None:
        index = int(cb.matches[0].group("idx"))
    if page is None and cb.matches[0].group("pg"):
        page = int(cb.matches[0].group("pg"))
    
    # Get Per-Account Settings
    apply_type = await Altruix.config.get_env(f"AUTO_DELETE_CMD_TYPE_{index}") or "per_account"
    status = await Altruix.config.get_env(f"AUTO_DELETE_CMD_STATUS_{index}") or "off"
    delay = await Altruix.config.get_env(f"AUTO_DELETE_CMD_DELAY_{index}") or "2"
    
    client = Altruix.clients[index]
    me = getattr(client, "myself", None) or client.me
    
    # ✅ Enhanced UI with localized title and description
    title = Altruix.get_string("auto_delete_cmd_title")
    desc = Altruix.get_string("auto_delete_cmd_desc")
    text = (
        f"<b>{title} for: {me.first_name}</b>\n\n"
        f"<i>{desc}</i>\n\n"
        f"• <b>Mode:</b> <code>{apply_type.upper().replace('_', ' ')}</code>\n"
        f"• <b>Status:</b> <code>{status.upper()}</code>\n"
        f"• <b>Delay:</b> <code>{delay}s</code>\n\n"
        "If Mode is GLOBAL, this account uses Global settings."
    )

    buttons = [
        [
            InlineKeyboardButton(f"Mode: {apply_type.upper()}", callback_data=f"cmd_toggle_mode_{index}_{page}"),
        ],
        [
            InlineKeyboardButton(f"Status: {status.upper()}", callback_data=f"cmd_toggle_status_{index}_{page}"),
        ],
        [
            InlineKeyboardButton("-2s", callback_data=f"cmd_adj_delay_{index}_{page}_m2"),
            InlineKeyboardButton(f"Delay: {delay}s", callback_data="none"),
            InlineKeyboardButton("+2s", callback_data=f"cmd_adj_delay_{index}_{page}_p2"),
        ],
    ]
    
    # Back button logic
    if page > 0: # If coming from session_info
        buttons.append([InlineKeyboardButton("🔙 Back to Session Info", callback_data=f"session_info_{index}_{page}_3")])
    else:
        buttons.append([InlineKeyboardButton("🔙 Back to List", callback_data="cmd_sessions_list_1")])
        
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons))

@Altruix.bot.on_callback_query(filters.regex(r"^cmd_toggle_mode_(?P<index>\d+)_(?P<page>\d+)$"))
@iuser_check
@log_errors
async def cmd_toggle_mode_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    index = int(cb.matches[0].group("index"))
    page = int(cb.matches[0].group("page"))
    current = await Altruix.config.get_env(f"AUTO_DELETE_CMD_TYPE_{index}") or "per_account"
    new_mode = "global" if current == "per_account" else "per_account"
    await Altruix.config.sync_env_to_db(f"AUTO_DELETE_CMD_TYPE_{index}", new_mode, upsert=True)
    await cmd_account_settings_handler(c, cb, index, page)

@Altruix.bot.on_callback_query(filters.regex(r"^cmd_toggle_status_(?P<index>\d+)_(?P<page>\d+)$"))
@iuser_check
@log_errors
async def cmd_toggle_status_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    index = int(cb.matches[0].group("index"))
    page = int(cb.matches[0].group("page"))
    current = await Altruix.config.get_env(f"AUTO_DELETE_CMD_STATUS_{index}") or "off"
    new_status = "on" if current == "off" else "off"
    await Altruix.config.sync_env_to_db(f"AUTO_DELETE_CMD_STATUS_{index}", new_status, upsert=True)
    await cmd_account_settings_handler(c, cb, index, page)

@Altruix.bot.on_callback_query(filters.regex(r"^cmd_adj_delay_(?P<index>\d+)_(?P<page>\d+)_(?P<act>m2|p2)$"))
@iuser_check
@log_errors
async def cmd_adj_delay_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    index = int(cb.matches[0].group("index"))
    page = int(cb.matches[0].group("page"))
    act = cb.matches[0].group("act")
    current = int(await Altruix.config.get_env(f"AUTO_DELETE_CMD_DELAY_{index}") or 2)
    new_delay = max(0, current - 2) if act == "m2" else current + 2
    await Altruix.config.sync_env_to_db(f"AUTO_DELETE_CMD_DELAY_{index}", str(new_delay), upsert=True)
    await cmd_account_settings_handler(c, cb, index, page)
