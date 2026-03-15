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
    
    text = (
        "<b>⚙️ Custom Help Settings</b>\n\n"
        f"Customize the message shown when running <code>.help</code>.\n\n"
        f"• <b>Status:</b> {status_icon} {'Custom' if status == 'custom' else 'Default'}\n"
        f"• <b>Apply Type:</b> {type_icon} {apply_type.replace('_', ' ').title()}\n"
        f"• <b>Current Custom Message:</b>\n<blockquote>{html.escape(custom_msg)}</blockquote>\n\n"
        "<i>Global mode applies one setting to all accounts. Per-Account allows different settings for each session.</i>"
    )
    
    buttons = [
        [
            InlineKeyboardButton(f"Status: {'Custom' if status == 'custom' else 'Default'}", callback_data=f"toggle_help_status_{idx}_{pg}", style=user_style),
            InlineKeyboardButton(f"Type: {apply_type.title()}", callback_data=f"toggle_help_type_{idx}_{pg}", style=user_style)
        ],
        [
            InlineKeyboardButton("📝 Edit Custom Message", callback_data=f"edit_help_msg_{idx}_{pg}", style=user_style)
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
    await cb.answer(f"Status set to {new_status.title()}")
    await help_settings_menu_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^toggle_help_type_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def toggle_help_apply_type_handler(c: Client, cb: CallbackQuery):
    idx, pg = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    current = await Altruix.config.get_env("HELP_INFO_APPLY_TYPE", default="global")
    new_type = "per_account" if current == "global" else "global"
    await Altruix.config.set_env("HELP_INFO_APPLY_TYPE", new_type)
    await cb.answer(f"Apply type set to {new_type.replace('_', ' ').title()}")
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
