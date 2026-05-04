# Main/internals/settings_handlers/help_handlers.py
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from Main.core.decorators import log_errors, iuser_check
from Main.core.client import Altruix
from pyrogram.enums import ParseMode
import logging
import html

# Logger
logger = logging.getLogger(__name__)

from .utils import edit_cb, gt
from .states import user_privacy_state

@Altruix.bot.on_callback_query(filters.regex(r"^help_settings_menu_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def help_settings_menu_handler(c: Client, cb: CallbackQuery):
    """Main menu for custom help settings."""
    idx, pg = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    user_id = cb.from_user.id
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(user_id)
    
    # Sesi info
    session_client = Altruix.clients[idx]
    me = getattr(session_client, "myself", None) or await session_client.get_me()
    session_client.myself = me
    
    # Get settings from ENV/Config (Standardized Keys)
    apply_type = await Altruix.config.get_env("HELP_INFO_APPLY_TYPE", default="global")
    
    if apply_type == "global":
        status = await Altruix.config.get_env("HELP_INFO_STATUS_GLOBAL", default="default")
        custom_msg = await Altruix.config.get_env("HELP_INFO_CUSTOM_MSG_GLOBAL", default="Not set")
    else:
        status = await Altruix.config.get_env(f"HELP_INFO_STATUS_{me.id}", default="default")
        custom_msg = await Altruix.config.get_env(f"HELP_INFO_CUSTOM_MSG_{me.id}", default="Not set")
    
    # ✅ Safety check: Ensure custom_msg is not None for html.escape
    custom_msg = custom_msg or "Not set"
    
    # Resolve icons
    type_icon = "🌍" if apply_type == "global" else "👤"
    status_icon = "✅" if status == "custom" else "❌"
    
    design_apply_type = await Altruix.config.get_env("HELP_MENU_DESIGN_APPLY_TYPE", default="global") or "global"
    if design_apply_type == "global":
        help_design = await Altruix.config.get_env("HELP_MENU_DESIGN_GLOBAL", default="1") or "1"
    else:
        help_design = await Altruix.config.get_env(f"HELP_MENU_DESIGN_{me.id}", default="1") or "1"
    design_type_icon = "🌍" if design_apply_type == "global" else "👤"
    
    # Compact Text Settings
    compact_apply_type = await Altruix.config.get_env("HELP_COMPACT_APPLY_TYPE", default="global")
    if compact_apply_type == "global":
        compact_status = await Altruix.config.get_env("HELP_COMPACT_STATUS_GLOBAL", default="off")
        res_max = await Altruix.config.get_env("HELP_COMPACT_MAX_LEN_GLOBAL", default=13)
        compact_max = int(res_max if res_max is not None else 13)
    else:
        compact_status = await Altruix.config.get_env(f"HELP_COMPACT_STATUS_{me.id}", default="off")
        res_max = await Altruix.config.get_env(f"HELP_COMPACT_MAX_LEN_{me.id}", default=13)
        compact_max = int(res_max if res_max is not None else 13)

    comp_type_icon = "🌍" if compact_apply_type == "global" else "👤"
    comp_status_icon = "✅" if compact_status == "on" else "❌"

    # Page Max Chars Settings (for plugin sub-page splitting)
    page_chars_apply_type = await Altruix.config.get_env("HELP_PAGE_CHARS_APPLY_TYPE", default="global")
    if page_chars_apply_type == "global":
        res_page_max = await Altruix.config.get_env("HELP_PAGE_MAX_CHARS_GLOBAL", default=900)
    else:
        res_page_max = await Altruix.config.get_env(f"HELP_PAGE_MAX_CHARS_{me.id}", default=900)
    page_max_chars = int(res_page_max if res_page_max is not None else 900)
    page_chars_icon = "🌍" if page_chars_apply_type == "global" else "👤"

    text = (
        f"<blockquote expandable>"
        "<b>⚙️ Custom Help Settings</b>\n\n"
        f"Customize the message shown when running <code>.help</code>.\n\n"
        "──────── <b>Message & Design</b> ────────\n"
        f"• <b>Status:</b> {status_icon} {'Custom' if status == 'custom' else 'Default'}\n"
        f"• <b>Apply Type:</b> {type_icon} {apply_type.replace('_', ' ').title()}\n"
        f"• <b>Design Mode:</b> <code>Design {help_design}</code> ({design_type_icon})\n"
        f"• <b>Current Custom Message:</b>{html.escape(custom_msg)}\n\n"
        "──────── <b>Display Settings</b> ────────\n"
        f"• <b>Compact Text:</b> {comp_status_icon} {compact_status.upper()} ({comp_type_icon})\n"
        f"• <b>Max Length:</b> <code>{compact_max} chars</code>\n"
        f"• <b>Page Max Chars:</b> <code>{page_max_chars}</code> ({page_chars_icon})\n\n"
        "<i>Global mode applies one setting to all accounts. Per-Account allows different settings for each session.</i>"
        f"</blockquote>"
    )
    
    buttons = [
        [
            InlineKeyboardButton(f"Status: {'Custom' if status == 'custom' else 'Default'}", callback_data=f"toggle_help_status_{idx}_{pg}", style=user_style),
            InlineKeyboardButton(f"Type: {apply_type.title()}", callback_data=f"toggle_help_type_{idx}_{pg}", style=user_style)
        ],
        [
            InlineKeyboardButton(f"Mode: Design {help_design}", callback_data=f"toggle_help_design_{idx}_{pg}", style=user_style),
            InlineKeyboardButton(f"Scope: {design_apply_type.title()}", callback_data=f"toggle_help_design_type_{idx}_{pg}", style=user_style)
        ],
        [
            InlineKeyboardButton(f"Compact: {compact_status.upper()}", callback_data=f"toggle_help_comp_status_{idx}_{pg}", style=user_style),
            InlineKeyboardButton(f"Comp Scope: {compact_apply_type.title()}", callback_data=f"toggle_help_comp_type_{idx}_{pg}", style=user_style)
        ],
        [
            InlineKeyboardButton("-1", callback_data=f"adj_help_comp_max_{idx}_{pg}_-1", style=user_style),
            InlineKeyboardButton(f"Max Text: {compact_max}", callback_data="none", style=user_style),
            InlineKeyboardButton("+1", callback_data=f"adj_help_comp_max_{idx}_{pg}_1", style=user_style)
        ],
        [
            InlineKeyboardButton("-100", callback_data=f"adj_help_page_max_{idx}_{pg}_-100", style=user_style),
            InlineKeyboardButton(f"Max Page: {page_max_chars}", callback_data="none", style=user_style),
            InlineKeyboardButton("+100", callback_data=f"adj_help_page_max_{idx}_{pg}_100", style=user_style)
        ],
        [
            InlineKeyboardButton(f"Page Scope: {page_chars_apply_type.title()}", callback_data=f"toggle_help_page_type_{idx}_{pg}", style=user_style)
        ],
        [
            InlineKeyboardButton("🖥 Grid Settings", callback_data=f"help_grid_menu_{idx}_{pg}", style=user_style)
        ],
        [
            InlineKeyboardButton("📝 Edit Custom Help MSG", callback_data=f"edit_help_msg_{idx}_{pg}", style=user_style)
        ],
        [
            InlineKeyboardButton("ℹ️ Variables Info", callback_data=f"help_vars_info_{idx}_{pg}", style=user_style)
        ],
        [
            InlineKeyboardButton(gt("back"), callback_data=f"session_info_{idx}_{pg}_3", style=user_style)
        ]
    ]
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons))

@Altruix.bot.on_callback_query(filters.regex(r"^toggle_help_status_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def toggle_help_status_handler(c: Client, cb: CallbackQuery):
    idx, pg = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    # Sesi info
    session_client = Altruix.clients[idx]
    me = getattr(session_client, "myself", None) or await session_client.get_me()
    
    apply_type = await Altruix.config.get_env("HELP_INFO_APPLY_TYPE", default="global")
    
    if apply_type == "global":
        key = "HELP_INFO_STATUS_GLOBAL"
    else:
        key = f"HELP_INFO_STATUS_{me.id}"
        
    current = await Altruix.config.get_env(key, default="default")
    new_status = "custom" if current == "default" else "default"
    await Altruix.config.set_env(key, new_status)
    await cb.answer(f"Status set to {new_status.title()}", show_alert=True)
    await help_settings_menu_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^toggle_help_type_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def toggle_help_apply_type_handler(c: Client, cb: CallbackQuery):
    idx, pg = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    current = await Altruix.config.get_env("HELP_INFO_APPLY_TYPE", default="global")
    new_type = "per_account" if current == "global" else "global"
    await Altruix.config.set_env("HELP_INFO_APPLY_TYPE", new_type)
    await cb.answer(f"Apply type set to {new_type.replace('_', ' ').title()}", show_alert=True)
    await help_settings_menu_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^toggle_help_design_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def toggle_help_design_handler(c: Client, cb: CallbackQuery):
    idx, pg = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    session_client = Altruix.clients[idx]
    me = getattr(session_client, "myself", None) or await session_client.get_me()
    
    apply_type = await Altruix.config.get_env("HELP_MENU_DESIGN_APPLY_TYPE", default="global")
    
    if apply_type == "global":
        key = "HELP_MENU_DESIGN_GLOBAL"
    else:
        key = f"HELP_MENU_DESIGN_{me.id}"
        
    current = await Altruix.config.get_env(key, default="1")
    if str(current) == "1":
        new_design = "2"
    elif str(current) == "2":
        new_design = "3"
    elif str(current) == "3":
        new_design = "4"
    else:
        new_design = "1"
        
    await Altruix.config.set_env(key, new_design)
    await cb.answer(f"Help Design set to Design {new_design}", show_alert=True)
    await help_settings_menu_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^toggle_help_design_type_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def toggle_help_design_type_handler(c: Client, cb: CallbackQuery):
    idx, pg = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    current = await Altruix.config.get_env("HELP_MENU_DESIGN_APPLY_TYPE", default="global")
    new_type = "per_account" if current == "global" else "global"
    await Altruix.config.set_env("HELP_MENU_DESIGN_APPLY_TYPE", new_type)
    await cb.answer(f"Design scope set to {new_type.replace('_', ' ').title()}", show_alert=True)
    await help_settings_menu_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^toggle_help_comp_status_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def toggle_help_compact_status_handler(c: Client, cb: CallbackQuery):
    idx, pg = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    session_client = Altruix.clients[idx]
    me = getattr(session_client, "myself", None) or await session_client.get_me()
    
    apply_type = await Altruix.config.get_env("HELP_COMPACT_APPLY_TYPE", default="global")
    key = "HELP_COMPACT_STATUS_GLOBAL" if apply_type == "global" else f"HELP_COMPACT_STATUS_{me.id}"
        
    current = await Altruix.config.get_env(key, default="off")
    new_status = "on" if current == "off" else "off"
    await Altruix.config.set_env(key, new_status)
    await cb.answer(f"Compact Text set to {new_status.upper()}", show_alert=True)
    await help_settings_menu_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^toggle_help_comp_type_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def toggle_help_compact_apply_type_handler(c: Client, cb: CallbackQuery):
    idx, pg = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    current = await Altruix.config.get_env("HELP_COMPACT_APPLY_TYPE", default="global")
    new_type = "per_account" if current == "global" else "global"
    await Altruix.config.set_env("HELP_COMPACT_APPLY_TYPE", new_type)
    await cb.answer(f"Compact Scope set to {new_type.replace('_', ' ').title()}", show_alert=True)
    await help_settings_menu_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^adj_help_comp_max_(\d+)_(\d+)_(-?\d+)$"))
@iuser_check
@log_errors
async def adjust_help_compact_max_len_handler(c: Client, cb: CallbackQuery):
    idx, pg = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    change = int(cb.matches[0].group(3))
    
    session_client = Altruix.clients[idx]
    me = getattr(session_client, "myself", None) or await session_client.get_me()
    
    apply_type = await Altruix.config.get_env("HELP_COMPACT_APPLY_TYPE", default="global")
    key = "HELP_COMPACT_MAX_LEN_GLOBAL" if apply_type == "global" else f"HELP_COMPACT_MAX_LEN_{me.id}"
        
    res_curr = await Altruix.config.get_env(key, default=13)
    current = int(res_curr if res_curr is not None else 13)
    new_val = max(1, current + change)
    await Altruix.config.set_env(key, new_val)
    await cb.answer(f"Max Text Length: {new_val}", show_alert=True)
    await help_settings_menu_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^adj_help_page_max_(\d+)_(\d+)_(-?\d+)$"))
@iuser_check
@log_errors
async def adjust_help_page_max_chars_handler(c: Client, cb: CallbackQuery):
    """Adjust the maximum character limit per plugin help sub-page."""
    idx, pg = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    change = int(cb.matches[0].group(3))
    
    session_client = Altruix.clients[idx]
    me = getattr(session_client, "myself", None) or await session_client.get_me()
    
    apply_type = await Altruix.config.get_env("HELP_PAGE_CHARS_APPLY_TYPE", default="global")
    key = "HELP_PAGE_MAX_CHARS_GLOBAL" if apply_type == "global" else f"HELP_PAGE_MAX_CHARS_{me.id}"
        
    res_curr = await Altruix.config.get_env(key, default=900)
    current = int(res_curr if res_curr is not None else 900)
    new_val = max(200, min(4000, current + change))  # Clamp between 200-4000
    await Altruix.config.set_env(key, new_val)
    await cb.answer(f"Max Page Chars: {new_val}", show_alert=True)
    await help_settings_menu_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^toggle_help_page_type_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def toggle_help_page_chars_apply_type_handler(c: Client, cb: CallbackQuery):
    """Toggle scope for page max chars between Global and Per-Account."""
    idx, pg = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    current = await Altruix.config.get_env("HELP_PAGE_CHARS_APPLY_TYPE", default="global")
    new_type = "per_account" if current == "global" else "global"
    await Altruix.config.set_env("HELP_PAGE_CHARS_APPLY_TYPE", new_type)
    await cb.answer(f"Page Chars Scope: {new_type.replace('_', ' ').title()}", show_alert=True)
    await help_settings_menu_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^help_vars_info_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def help_vars_info_handler(c: Client, cb: CallbackQuery):
    idx, pg = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)
    text = (
        "<b>ℹ️ Custom Help Documentation</b>\n\n"
        "<b>🔹 Logic Variables:</b>\n"
        "• <code>{mention_name}</code>, <code>{mention_full_name}</code>\n"
        "• <code>{mention}</code>, <code>{session_name}</code>, <code>{user_id}</code>\n"
        "• <code>{ub_version}</code>, <code>{kurigram_version}</code>, <code>{python_version}</code>\n"
        "• <code>{ub_plugins}</code>, <code>{bot_plugins}</code>, <code>{total_addons}</code>, <code>{index}</code>\n\n"
        "<b>🔹 HTML Mode (Default):</b>\n"
        "• <code>&lt;b&gt;Bold&lt;/b&gt;</code>, <code>&lt;i&gt;Italic&lt;/i&gt;</code>, <code>&lt;u&gt;Under&lt;/u&gt;</code>\n"
        "• <code>&lt;tg-spoiler&gt;Spoiler&lt;/tg-spoiler&gt;</code>, <code>&lt;code&gt;Code&lt;/code&gt;</code>\n"
        "• <code>&lt;blockquote&gt;Quote&lt;/blockquote&gt;</code>\n"
        "• <code>&lt;blockquote expandable&gt;Exp. Quote&lt;/blockquote&gt;</code>\n"
        "• <code>&lt;pre&gt;&lt;code class=\"language-py\"&gt;Code&lt;/code&gt;&lt;/pre&gt;</code>\n\n"
        "<b>🔹 MarkdownV2 Mode (Add <code>(md2)</code>):</b>\n"
        "• <code>&#42;Bold&#42;</code>, <code>&#95;Italic&#95;</code>, <code>&#95;&#95;Under&#95;&#95;</code>\n"
        "• <code>&#124;&#124;Spoiler&#124;&#124;</code>, <code>&#96;Code&#96;</code>\n"
        "• <code>&gt; Quote</code> (Start line with &gt;)\n"
        "• <code>&gt; Quote ... &#124;&#124;</code> (End with &#124;&#124; to expand)\n"
        "• <code>&#96;&#96;&#96;python\nCode\n&#96;&#96;&#96;</code>\n\n"
        "<i>Note: Reserved characters in MarkdownV2 like . - ! must be escaped with \\ if not part of a tag.</i>"
    )
    buttons = [[InlineKeyboardButton(gt("back"), callback_data=f"help_settings_menu_{idx}_{pg}", style=user_style)]]
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^edit_help_msg_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def edit_help_msg_start_handler(c: Client, cb: CallbackQuery):
    idx, pg = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    user_id = cb.from_user.id
    
    # Store state for input handling
    user_privacy_state[user_id] = {
        "action": "edit_help_msg",
        "index": idx,
        "page": pg,
        "dash_msg_id": cb.message.id if cb.message else None
    }
    
    text = (
        "<b>📝 Edit Custom Help Message</b>\n\n"
        "Please send the new custom message you want to use for <code>.help</code>.\n\n"
        "You can use HTML or Markdown tags. Include <code>(md2)</code> for markdown or <code>(html)</code> for HTML.\n"
        "Variables supported: <code>{mention}</code>, <code>{ub_version}</code>, etc.\n\n"
        "<i>Type /cancel to abort.</i>"
    )
    
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(user_id)
    
    buttons = [[InlineKeyboardButton("🔙 Cancel", callback_data=f"help_settings_menu_{idx}_{pg}", style=user_style)]]
    
    if cb.message:
        await cb.message.edit(text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def process_help_msg_input(c: Client, m: Message, state: dict):
    """Processes the custom help message input."""
    user_id = m.from_user.id
    idx = state["index"]
    pg = state["page"]
    new_msg = m.text
    
    # Save to ENV/Config
    apply_type = await Altruix.config.get_env("HELP_INFO_APPLY_TYPE", default="global")
    if apply_type == "global":
        key = "HELP_INFO_CUSTOM_MSG_GLOBAL"
    else:
        session_client = Altruix.clients[idx]
        me = getattr(session_client, "myself", None) or await session_client.get_me()
        key = f"HELP_INFO_CUSTOM_MSG_{me.id}"
        
    await Altruix.config.set_env(key, new_msg)
    
    # Notify success
    confirm_msg = await m.reply("✅ <b>Custom help message updated!</b>", parse_mode=ParseMode.HTML)
    
    # Clean up state
    if user_id in user_privacy_state:
        del user_privacy_state[user_id]
        
    # Auto-delete confirmation after 3 seconds
    async def _cleanup():
        import asyncio
        await asyncio.sleep(3)
        try: await confirm_msg.delete()
        except: pass
    Altruix.loop.create_task(_cleanup())
    
    # Try to refresh dashboard if msg_id is known
    if state.get("dash_msg_id"):
        try:
            # We need to recreate a mock callback to reuse the handler or just manually call it
            # For simplicity, we'll just let the user click back or we could try to edit the original msg
            pass
        except: pass
        
# ============================================================================
# 🖥 GRID SETTINGS HANDLERS (ROWS & COLUMNS)
# ============================================================================

@Altruix.bot.on_callback_query(filters.regex(r"^help_grid_menu_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def help_grid_settings_handler(c: Client, cb: CallbackQuery):
    """Sub-menu for configuring help rows and columns."""
    idx, pg = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    user_id = cb.from_user.id
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(user_id)
    
    # Sesi info
    session_client = Altruix.clients[idx]
    me = getattr(session_client, "myself", None) or await session_client.get_me()
    
    # Grid Apply Type
    apply_type = await Altruix.config.get_env("HELP_GRID_APPLY_TYPE", default="global")
    
    if apply_type == "global":
        rows = await Altruix.config.get_env("HELP_GRID_ROWS_GLOBAL", default=3)
        cols = await Altruix.config.get_env("HELP_GRID_COLS_GLOBAL", default=3)
    else:
        rows = await Altruix.config.get_env(f"HELP_GRID_ROWS_{me.id}", default=3)
        cols = await Altruix.config.get_env(f"HELP_GRID_COLS_{me.id}", default=3)
        
    rows = int(rows if rows is not None else 3)
    cols = int(cols if cols is not None else 3)
    
    type_icon = "🌍" if apply_type == "global" else "👤"
    
    text = (
        "<b>🖥 Help Grid Settings</b>\n\n"
        "Configure the layout of plugin buttons in the help menu.\n\n"
        f"• <b>Current Scope:</b> {type_icon} {apply_type.replace('_', ' ').title()}\n"
        f"• <b>Rows:</b> <code>{rows}</code> (Plugin rows per page)\n"
        f"• <b>Columns:</b> <code>{cols}</code> (Plugin buttons per row)\n\n"
        "<i>Note: Mode 2 & 3 are optimized for 2 columns, but you can change it here.</i>"
    )
    
    buttons = [
        [
            InlineKeyboardButton("-1", callback_data=f"adj_help_grid_rows_{idx}_{pg}_-1", style=user_style),
            InlineKeyboardButton(f"Rows: {rows}", callback_data="none", style=user_style),
            InlineKeyboardButton("+1", callback_data=f"adj_help_grid_rows_{idx}_{pg}_1", style=user_style)
        ],
        [
            InlineKeyboardButton("-1", callback_data=f"adj_help_grid_cols_{idx}_{pg}_-1", style=user_style),
            InlineKeyboardButton(f"Columns: {cols}", callback_data="none", style=user_style),
            InlineKeyboardButton("+1", callback_data=f"adj_help_grid_cols_{idx}_{pg}_1", style=user_style)
        ],
        [
            InlineKeyboardButton(f"Scope: {apply_type.title()}", callback_data=f"toggle_help_grid_type_{idx}_{pg}", style=user_style)
        ],
        [
            InlineKeyboardButton(gt("back"), callback_data=f"help_settings_menu_{idx}_{pg}", style=user_style)
        ]
    ]
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons))

@Altruix.bot.on_callback_query(filters.regex(r"^toggle_help_grid_type_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def toggle_help_grid_apply_type_handler(c: Client, cb: CallbackQuery):
    idx, pg = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    current = await Altruix.config.get_env("HELP_GRID_APPLY_TYPE", default="global")
    new_type = "per_account" if current == "global" else "global"
    await Altruix.config.set_env("HELP_GRID_APPLY_TYPE", new_type)
    await cb.answer(f"Grid Scope: {new_type.replace('_', ' ').title()}", show_alert=True)
    await help_grid_settings_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^adj_help_grid_rows_(\d+)_(\d+)_(-?\d+)$"))
@iuser_check
@log_errors
async def adjust_help_grid_rows_handler(c: Client, cb: CallbackQuery):
    idx, pg = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    change = int(cb.matches[0].group(3))
    
    session_client = Altruix.clients[idx]
    me = getattr(session_client, "myself", None) or await session_client.get_me()
    
    apply_type = await Altruix.config.get_env("HELP_GRID_APPLY_TYPE", default="global")
    key = "HELP_GRID_ROWS_GLOBAL" if apply_type == "global" else f"HELP_GRID_ROWS_{me.id}"
    
    res_curr = await Altruix.config.get_env(key, default=3)
    current = int(res_curr if res_curr is not None else 3)
    new_val = max(1, min(10, current + change))
    
    await Altruix.config.set_env(key, new_val)
    await cb.answer(f"Rows: {new_val}", show_alert=True)
    await help_grid_settings_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^adj_help_grid_cols_(\d+)_(\d+)_(-?\d+)$"))
@iuser_check
@log_errors
async def adjust_help_grid_cols_handler(c: Client, cb: CallbackQuery):
    idx, pg = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    change = int(cb.matches[0].group(3))
    
    session_client = Altruix.clients[idx]
    me = getattr(session_client, "myself", None) or await session_client.get_me()
    
    apply_type = await Altruix.config.get_env("HELP_GRID_APPLY_TYPE", default="global")
    key = "HELP_GRID_COLS_GLOBAL" if apply_type == "global" else f"HELP_GRID_COLS_{me.id}"
    
    res_curr = await Altruix.config.get_env(key, default=3)
    current = int(res_curr if res_curr is not None else 3)
    new_val = max(1, min(5, current + change))
    
    await Altruix.config.set_env(key, new_val)
    await cb.answer(f"Columns: {new_val}", show_alert=True)
    await help_grid_settings_handler(c, cb)
