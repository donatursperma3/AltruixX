# Main/internals/settings_handlers/privacy_handlers.py
import html
import os
import asyncio
import logging
from pyrogram import Client, filters, raw
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from Main.core.decorators import log_errors, iuser_check
from Main.core.client import Altruix
from pyrogram.enums import ParseMode

from .utils import edit_cb, check_authorization, gt
# from .session_info import sessions_info_cb_handler

# Logger
logger = logging.getLogger(__name__)

# ====================== PRIVACY & SECURITY MENU ======================
@Altruix.bot.on_callback_query(filters.regex(r"^privacy_menu_(\d+)_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def privacy_menu_handler(c: Client, cb: CallbackQuery):
    """Privacy & Security Menu with sudo, prefix, and 2FA info."""
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)

    buttons = [
        [
            InlineKeyboardButton("👑 Sudo Users", f"sudo_menu_{index}_{page}_{button_page}", style=user_style),
            InlineKeyboardButton("⚙️ Prefix Settings", f"prefix_menu_{index}_{page}_{button_page}", style=user_style)
        ],
        [
            InlineKeyboardButton("🛡️ Two-Step Verification", f"gen_conf_2fa_info_{index}_{page}_{button_page}", style=user_style),
            InlineKeyboardButton("🔒 Privacy Settings", f"native_privacy_menu_{index}_{page}_{button_page}", style=user_style)
        ],
        [
            InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}_{button_page}", style=user_style)
        ]
    ]
    await edit_cb(cb, 
        text="<b>🔒 Privacy & Security</b>\n\nManage security settings for this session:", 
        reply_markup=InlineKeyboardMarkup(buttons), 
        parse_mode=ParseMode.HTML
    )

@Altruix.bot.on_callback_query(filters.regex(r"^native_privacy_menu_(\d+)_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def native_privacy_menu_handler(c: Client, cb: CallbackQuery):
    """Stub for Native Telegram Privacy Settings"""
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    await cb.answer()
    
    text = (
        "<b>🔒 Privacy Settings (Native)</b>\n\n"
        "Configurable privacy options (Coming Soon):\n"
        "• Phone Number\n"
        "• Last Seen & Online\n"
        "• Profile Photos\n"
        "• Forwarded Messages\n"
        "• Calls\n"
        "• Groups & Channels\n\n"
        "<i>Currently read-only / placeholder.</i>"
    )
    
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)
    
    buttons = [
        [InlineKeyboardButton("🔙 Back", f"privacy_menu_{index}_{page}_{button_page}", style=user_style)]
    ]
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

# ====================== CUSTOM BOT MANAGER ======================
@Altruix.bot.on_callback_query(filters.regex(r"^custom_bot_manager$"))
@iuser_check
@log_errors
async def custom_bot_manager_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer()
    
    # List Custom Bots
    custom_bots = Altruix.bot_manager.custom_bots if hasattr(Altruix, 'bot_manager') else {}
    
    text = (
        f"<b>🤖 Custom Bot Manager (v1.5.5.9b)</b>\n\n"
        f"Total Custom Bots: <code>{len(custom_bots)}</code>\n\n"
        f"Select a bot to manage:"
    )
    
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)
    
    buttons = []
    if custom_bots:
        for bot_id, bot_client in custom_bots.items():
            name = f"Bot {bot_id}"
            try:
                me = bot_client.myself if hasattr(bot_client, "myself") else None
                if me:
                    name = f"{me.first_name} (@{me.username})"
            except: pass
            
            buttons.append([InlineKeyboardButton(name, f"manage_custom_bot_{bot_id}", style=user_style)])
    else:
        text += f"\n\n<i>{gt('no_custom_bots') or 'No custom bots found.'}</i>"

    buttons.append([InlineKeyboardButton(gt("back"), "bot_controls_menu", style=user_style)])
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons))

@Altruix.bot.on_callback_query(filters.regex(r"^manage_custom_bot_(\d+)$"))
@iuser_check
@log_errors
async def manage_custom_bot_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer()
    bot_id = int(cb.matches[0].group(1))
    
    custom_bots = Altruix.bot_manager.custom_bots if hasattr(Altruix, 'bot_manager') else {}
    bot_client = custom_bots.get(bot_id)
    
    if not bot_client:
        await cb.answer("Bot not found!", show_alert=True)
        return await custom_bot_manager_handler(c, cb)
        
    me = bot_client.myself if hasattr(bot_client, "myself") else None
    is_connected = getattr(bot_client, 'is_connected', False)
    
    name = me.first_name if me else f"Bot {bot_id}"
    username = f"@{me.username}" if me and me.username else "No Username"
    dc_id = getattr(me, 'dc_id', "N/A") if me else "N/A"
    status_text = "✅ Running" if is_connected else "❌ Stopped"
    
    text = (
        f"<b>⚙️ Manage Custom Bot</b>\n\n"
        f"• <b>Name:</b> {html.escape(name)}\n"
        f"• <b>Username:</b> {username}\n"
        f"• <b>ID:</b> <code>{bot_id}</code>\n"
        f"• <b>DC:</b> <code>{dc_id}</code>\n"
        f"• <b>Status:</b> {status_text}\n"
    )
    
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)

    buttons = [
        [
            InlineKeyboardButton("🛑 Stop Bot", f"action_custom_bot_stop_{bot_id}", style=user_style),
            InlineKeyboardButton("🗑️ Delete", f"action_custom_bot_delete_{bot_id}", style=user_style)
        ],
        [InlineKeyboardButton(gt("back"), "custom_bot_manager", style=user_style)]
    ]
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

# ====================== SUDO SETTINGS HANDLERS ======================
@Altruix.bot.on_callback_query(filters.regex(r"^sudo_menu_(\d+)_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def sudo_menu_handler(c: Client, cb: CallbackQuery):
    """Handler for sudo settings menu"""
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    # ✅ FIX: Clear privacy state when returning to menu to stop input capturing (Tambah Sudo fix)
    from .states import user_privacy_state
    if cb.from_user.id in user_privacy_state:
        del user_privacy_state[cb.from_user.id]

    apply_type = await Altruix.config.get_env("SUDO_APPLY_TYPE") or "global"
    apply_label = "Global" if apply_type == "global" else "Per-Account"
    
    target_id = Altruix.clients[index].me.id
    key = "SUDO_ENABLED_GLOBAL" if apply_type == "global" else f"SUDO_ENABLED_{target_id}"
    sudo_enabled_raw = await Altruix.config.get_env(key)
    sudo_enabled = sudo_enabled_raw != "false" if sudo_enabled_raw else True
    
    status_icon = "✅ Aktif" if sudo_enabled else "❌ Nonaktif"
    
    text = (
        f"<b>👑 Sudo Settings (v1.6.0)</b>\n\n"
        f"• <b>Status Sudo:</b> <code>{status_icon}</code>\n"
        f"• <b>Mode Apply:</b> <code>{apply_label}</code>\n"
        f"<i>Atur apakah status sudo berlaku global atau per akun.</i>"
    )
    
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)

    buttons = [
        [
            InlineKeyboardButton("➕ Tambah Sudo", f"sudo_add_start_{index}_{page}_{button_page}", style=user_style),
            InlineKeyboardButton("➖ Hapus Sudo", f"sudo_remove_start_{index}_{page}_{button_page}", style=user_style)
        ],
        [InlineKeyboardButton(f"🔄 Toggle Status: {status_icon}", f"sudo_toggle_{index}_{page}_{button_page}", style=user_style)],
        [InlineKeyboardButton(f"⚙️ Mode: {apply_label}", f"sudo_mode_{index}_{page}_{button_page}", style=user_style)],
        [InlineKeyboardButton("🔙 Back", f"privacy_menu_{index}_{page}_{button_page}", style=user_style)]
    ]
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^sudo_(add|remove)_start_(\d+)_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def sudo_add_remove_start_handler(c: Client, cb: CallbackQuery):
    """Entry point for adding or removing sudo users"""
    action_type = cb.matches[0].group(1) # 'add' or 'remove'
    index = int(cb.matches[0].group(2))
    page = int(cb.matches[0].group(3))
    button_page = int(cb.matches[0].group(4)) if len(cb.matches[0].groups()) >= 4 and cb.matches[0].group(4) else 1
    await cb.answer()
    
    from .states import user_privacy_state
    user_privacy_state[cb.from_user.id] = {
        'action': f'sudo_{action_type}',
        'session_index': index,
        'page': page,
        'button_page': button_page,
        'step': 'waiting_sudo_uid'
    }
    
    label = "Tambah" if action_type == "add" else "Hapus"
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)
    await cb.edit_message_text(
        text=f"👑 <b>{label} Sudo User</b>\n\n"
             f"Silakan kirim <b>User ID</b> yang ingin di{label.lower()}.\n\n"
             f"❌ <b>Cancel:</b> /cancel",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"sudo_menu_{index}_{page}_{button_page}", style=user_style)]])
    )

@Altruix.bot.on_callback_query(filters.regex(r"^sudo_toggle_(\d+)_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def sudo_toggle_handler(c: Client, cb: CallbackQuery):
    """Toggle sudo status for this session or globally"""
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    apply_type = await Altruix.config.get_env("SUDO_APPLY_TYPE") or "global"
    target_id = Altruix.clients[index].me.id
    key = "SUDO_ENABLED_GLOBAL" if apply_type == "global" else f"SUDO_ENABLED_{target_id}"
    
    current = await Altruix.config.get_env(key)
    new_val = "false" if current != "false" else "true"
    
    await Altruix.config.sync_env_to_db(key, new_val, upsert=True)
    setattr(Altruix.config, key, new_val)
    
    # ✅ Update high-performance cache immediately
    await Altruix.refresh_sudo_cache()
    
    await cb.answer(f"Sudo {'Aktif' if new_val == 'true' else 'Nonaktif'}", show_alert=False)
    await sudo_menu_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^sudo_mode_(\d+)_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def sudo_mode_handler(c: Client, cb: CallbackQuery):
    """Toggle Sudo Apply Type"""
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    current = await Altruix.config.get_env("SUDO_APPLY_TYPE") or "global"
    new_val = "per_account" if current == "global" else "global"
    
    await Altruix.config.sync_env_to_db("SUDO_APPLY_TYPE", new_val, upsert=True)
    # ✅ Refresh cache just in case
    await Altruix.refresh_sudo_cache()
    await cb.answer(f"Mode: {new_val.upper()}")
    await sudo_menu_handler(c, cb)

# ====================== PREFIX SETTINGS HANDLERS ======================
@Altruix.bot.on_callback_query(filters.regex(r"^prefix_menu_(\d+)_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def prefix_menu_handler(c: Client, cb: CallbackQuery):
    """Menu to configure command prefixes"""
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    await cb.answer()
    
    # ✅ FIX: Clear privacy state when returning to menu to stop input capturing (Prefix Edit fix)
    from .states import user_privacy_state
    if cb.from_user.id in user_privacy_state:
        del user_privacy_state[cb.from_user.id]

    apply_type = await Altruix.config.get_env("PREFIX_APPLY_TYPE") or "global"
    u_key = "PREFIX_OWNER_USER" if apply_type == "global" else f"PREFIX_OWNER_USER_{Altruix.clients[index].me.id}"
    s_key = "PREFIX_SUDO_USERS" if apply_type == "global" else f"PREFIX_SUDO_USERS_{Altruix.clients[index].me.id}"
    
    u_prefix = await Altruix.config.get_env(u_key) or "."
    s_prefix = await Altruix.config.get_env(s_key) or ","
    
    text = (
        f"<b>⚙️ Prefix Settings (v1.5.5.9b)</b>\n\n"
        f"• <b>Userbot Prefix:</b> <code>{u_prefix}</code>\n"
        f"• <b>Sudo Prefix:</b> <code>{s_prefix}</code>\n"
        f"• <b>Mode:</b> <code>{apply_type.title()}</code>\n\n"
        f"<i>Klik tombol di bawah untuk mengubah prefix.</i>"
    )
    
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)

    buttons = [
        [
            InlineKeyboardButton("📝 Edit User Prefix", f"prefix_edit_u_{index}_{page}_{button_page}", style=user_style),
            InlineKeyboardButton("📝 Edit Sudo Prefix", f"prefix_edit_s_{index}_{page}_{button_page}", style=user_style)
        ],
        [InlineKeyboardButton(f"🔄 Mode: {apply_type.title()}", f"prefix_toggle_mode_{index}_{page}_{button_page}", style=user_style)],
        [InlineKeyboardButton("🔙 Back", f"privacy_menu_{index}_{page}_{button_page}", style=user_style)]
    ]
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^prefix_info_(\d+)_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def prefix_info_handler(c: Client, cb: CallbackQuery):
    """Informational display about command prefixes"""
    index, page = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    await cb.answer()
    
    text = (
        "<b>⌨️ Command Prefix Information</b>\n\n"
        "Prefix adalah karakter yang digunakan di awal perintah (contoh: <code>.ping</code>).\n\n"
        "• <b>Global:</b> Berlaku untuk semua sesi.\n"
        "• <b>Per Account:</b> Setiap sesi bisa memiliki prefix unik.\n\n"
        "Anda dapat mengubahnya melalui menu <b>Privacy > Prefix Settings</b>."
    )
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}_{button_page}", style=user_style)]]), parse_mode=ParseMode.HTML)

# ====================== FEATURE STATUS HANDLER ======================
@Altruix.bot.on_callback_query(filters.regex(r"^feature_status_(\d+)_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def feature_status_handler(c: Client, cb: CallbackQuery):
    """Display ON/OFF status of major userbot features"""
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    await cb.answer()
    
    # Fetch statuses
    async def get_s(k, default="off"):
        val = await Altruix.config.get_env(f"{k}_{index}") or "off"
        return "✅ ON" if val == "on" else "❌ OFF"
        
    pml = await get_s("PML_LOGGER")
    mnt = await get_s("MNT_LOGGER")
    joinl = await get_s("JOINL_LOGGER")
    cmdl = await get_s("CMDL_LOGGER")
    
    startup = await Altruix.config.get_env(f"STARTUP_MSG_{index}") or "default"
    startup_s = "✅ ON" if startup != "off" else "❌ OFF"
    
    text = (
        f"<b>🚀 Feature Status (Session {index+1})</b>\n\n"
        f"• <b>PM Logger:</b> {pml}\n"
        f"• <b>Mention Logger:</b> {mnt}\n"
        f"• <b>Join Logger:</b> {joinl}\n"
        f"• <b>Command Logger:</b> {cmdl}\n"
        f"• <b>Startup Msg:</b> {startup_s}\n\n"
        f"<i>Status ini menunjukkan fitur mana yang aktif untuk sesi ini.</i>"
    )
    
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}_{button_page}", style=user_style)]]), parse_mode=ParseMode.HTML)

# ====================== TWO-STEP VERIFICATION HANDLER ======================
@Altruix.bot.on_callback_query(filters.regex(r"^gen_conf_2fa_info_(\d+)_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def check_2fa_info_handler(c: Client, cb: CallbackQuery):
    """Bridge to check 2FA status on the account"""
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    # button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    await cb.answer("⏳ Checking 2FA status...", show_alert=False)
    session_client = Altruix.clients[index]
    
    try:
        r = await session_client.invoke(raw.functions.account.GetPassword())
        has_2fa = r.has_recovery if hasattr(r, 'has_recovery') else False
        
        txt = (
            f"<b>🔒 2FA Security Info (Session {index+1})</b>\n\n"
            f"• <b>2FA Enabled:</b> <code>{'✅ Yes' if has_2fa else '❌ No'}</code>\n"
            f"• <b>Account Secure:</b> <code>{'✅ High' if has_2fa else '⚠️ Low'}</code>\n\n"
            f"<i>Jika 2FA belum aktif, sangat disarankan untuk mengaktifkannya di pengaturan Telegram resmi.</i>"
        )
        
        from Main.utils.file_helpers import get_user_button_style
        user_style = get_user_button_style(cb.from_user.id)
        
        await edit_cb(cb, txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"privacy_menu_{index}_{page}", style=user_style)]]) )
    except Exception as e:
        from Main.utils.file_helpers import get_user_button_style
        user_style = get_user_button_style(cb.from_user.id)
        await edit_cb(cb, f"❌ Error checking 2FA: {str(e)}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"privacy_menu_{index}_{page}", style=user_style)]]))

@Altruix.bot.on_callback_query(filters.regex(r"^prefix_toggle_mode_(\d+)_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def prefix_toggle_mode_handler(c: Client, cb: CallbackQuery):
    """Toggle between Global and Per Account prefix mode"""
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    current = await Altruix.config.get_env("PREFIX_APPLY_TYPE") or "global"
    new_val = "per_account" if current == "global" else "global"
    
    await Altruix.config.sync_env_to_db("PREFIX_APPLY_TYPE", new_val, upsert=True)
    setattr(Altruix.config, "PREFIX_APPLY_TYPE", new_val)
    
    # ✅ Update high-performance cache immediately
    await Altruix.refresh_sudo_cache()
    
    await cb.answer(f"Prefix Mode: {new_val.title()}", show_alert=False)
    await prefix_menu_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^prefix_edit_(u|s)_(\d+)_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def prefix_edit_start_handler(c: Client, cb: CallbackQuery):
    """Initiate prefix editing"""
    p_type = cb.matches[0].group(1) # 'u' for user, 's' for sudo
    index = int(cb.matches[0].group(2))
    page = int(cb.matches[0].group(3))
    button_page = int(cb.matches[0].group(4)) if len(cb.matches[0].groups()) >= 4 and cb.matches[0].group(4) else 1
    await cb.answer()
    
    label = "Userbot" if p_type == 'u' else "Sudo"
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)
    await cb.edit_message_text(
        f"📝 <b>Edit {label} Prefix</b>\n\n"
        f"Silakan kirim karakter tunggal yang ingin dijadikan prefix baru.\n"
        f"Contoh: <code>.</code> atau <code>!</code> atau <code>,</code>\n\n"
        f"❌ <b>Batal:</b> Kirim /cancel",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Batal", f"prefix_menu_{index}_{page}_{button_page}", style=user_style)]])
    )
    
    # Use state to wait for input
    from .states import user_privacy_state
    user_privacy_state[cb.from_user.id] = {
        'session_index': index,
        'page': page,
        'button_page': button_page,
        'p_type': p_type,
        'step': 'waiting_prefix_input'
    }

async def process_prefix_input(c: Client, m: Message, state: dict):
    """Save the new prefix based on mode (global/per account)"""
    new_prefix = m.text.strip()
    index = state['session_index']
    p_type = state['p_type']
    
    if len(new_prefix) != 1:
        await m.reply("❌ Prefix harus berupa **satu** karakter tunggal.")
        return
        
    apply_type = await Altruix.config.get_env("PREFIX_APPLY_TYPE") or "global"
    
    if p_type == 'u':
        key = "PREFIX_OWNER_USER" if apply_type == "global" else f"PREFIX_OWNER_USER_{Altruix.clients[index].me.id}"
    else:
        key = "PREFIX_SUDO_USERS" if apply_type == "global" else f"PREFIX_SUDO_USERS_{Altruix.clients[index].me.id}"
        
    await Altruix.config.sync_env_to_db(key, new_prefix, upsert=True)
    setattr(Altruix.config, key, new_prefix)
    
    # ✅ Update high-performance cache immediately
    await Altruix.refresh_sudo_cache()
    
    await m.reply(f"✅ Prefix berhasil diubah ke: <code>{new_prefix}</code>")
    from .states import user_privacy_state
    if m.from_user.id in user_privacy_state:
        del user_privacy_state[m.from_user.id]
        
    # Show menu again
async def process_sudo_input(c: Client, m: Message, state: dict):
    """Process adding or removing sudo users"""
    action = state['action'] # 'sudo_add' or 'sudo_remove'
    index = state['session_index']
    uid_text = m.text.strip()
    user_id = m.from_user.id
    
    if not uid_text.isdigit():
        await m.reply("❌ User ID harus berupa angka.")
        return
        
    uid = int(uid_text)
    session_client = Altruix.clients[index]
    target_id = session_client.me.id
    key = f"SUDO_USERS_{target_id}"
    current_sudo_raw = await Altruix.config.get_env(key) or ""
    
    # Handle list/string
    if isinstance(current_sudo_raw, str):
        current_sudo = current_sudo_raw.split()
    else:
        current_sudo = [str(x) for x in current_sudo_raw]
        
    if action == 'sudo_add':
        if str(uid) not in current_sudo:
            current_sudo.append(str(uid))
            await Altruix.config.sync_env_to_db(key, " ".join(current_sudo), upsert=True)
            # ✅ Refresh Cache
            await Altruix.refresh_sudo_cache()
            await m.reply(f"✅ User {uid} ditambahkan ke Sudo Session {index+1}.")
        else:
            await m.reply(f"ℹ️ User {uid} sudah ada di daftar Sudo.")
            
    elif action == 'sudo_remove':
        if str(uid) in current_sudo:
            current_sudo.remove(str(uid))
            await Altruix.config.sync_env_to_db(key, " ".join(current_sudo), upsert=True)
            # ✅ Refresh Cache
            await Altruix.refresh_sudo_cache()
            await m.reply(f"✅ User {uid} dihapus dari Sudo Session {index+1}.")
        else:
            await m.reply(f"❌ User {uid} tidak ada di daftar Sudo.")
            
    from .states import user_privacy_state
    if user_id in user_privacy_state:
        del user_privacy_state[user_id]
        
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(user_id)

    await asyncio.sleep(2)
    await m.reply("🔄 Kembali ke dashboard...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"session_info_{index}_{state.get('page', 1)}", style=user_style)]]) )

# --- Custom Link Settings (Bot Controls) ---

@Altruix.bot.on_callback_query(filters.regex(r"^custom_link_settings$"))
@iuser_check
@log_errors
async def custom_link_settings_handler(c: Client, cb: CallbackQuery):
    """Global & Per-Account configuration for Custom Dashboard Button."""
    await cb.answer()
    user_id = cb.from_user.id
    
    # We need access to get_custom_link_data from settings.py or duplicate logic
    from Main.internals.settings import get_custom_link_data, get_user_custom_link
    data = get_custom_link_data()
    apply_type = data.get("apply_types", {}).get(str(user_id), "global")
    apply_label = "Global" if apply_type == "global" else "Per-Account"
    
    custom_data = get_user_custom_link(user_id)
    text_val = custom_data.get("text", "Repo")
    link_val = custom_data.get("link", "https://t.me/AlphaXProject")
    
    text = (
        f"<b>🔗 Custom Link Settings</b>\n\n"
        f"• <b>Status:</b> <code>{apply_label}</code>\n"
        f"• <b>Button Text:</b> <code>{html.escape(text_val)}</code>\n"
        f"• <b>Button Link:</b> <code>{html.escape(link_val)}</code>\n\n"
        f"<i>Klik tombol di bawah untuk mengubah teks atau link tombol custom di dashboard utama.</i>"
    )
    
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(user_id)
    
    buttons = [
        [
            InlineKeyboardButton("📝 Edit Text", callback_data="edit_cl_text", style=user_style),
            InlineKeyboardButton("📝 Edit Link", callback_data="edit_cl_link", style=user_style),
        ],
        [InlineKeyboardButton(f"🔄 Per-Account Mode: {'✅' if apply_type == 'per_account' else '❌'}", callback_data="toggle_cl_mode", style=user_style)],
        [InlineKeyboardButton("🔙 Back", "bot_controls_menu", style=user_style)]
    ]
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^toggle_cl_mode$"))
@iuser_check
@log_errors
async def toggle_cl_mode_handler(c: Client, cb: CallbackQuery):
    """Toggle Custom Link Apply Type (Global <-> Per-Account)."""
    user_id = cb.from_user.id
    from Main.internals.settings import get_custom_link_data, save_custom_link_data
    data = get_custom_link_data()
    
    current = data.get("apply_types", {}).get(str(user_id), "global")
    new_val = "per_account" if current == "global" else "global"
    
    data.setdefault("apply_types", {})[str(user_id)] = new_val
    save_custom_link_data(data)
    
    await cb.answer(f"Mode: {new_val.upper()}")
    await custom_link_settings_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^edit_cl_(text|link)$"))
@iuser_check
@log_errors
async def edit_cl_start_handler(c: Client, cb: CallbackQuery):
    """Start process to edit custom link text or url."""
    target = cb.matches[0].group(1)
    await cb.answer()
    
    # Store state in session_info track state or privacy state
    # Actually session_info.py uses Altruix.user_track_state for this.
    Altruix.user_track_state[cb.from_user.id] = {"step": f"edit_cl_{target}"}
    
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)
    label = "Teks" if target == "text" else "Link"
    await cb.edit_message_text(
        f"📝 <b>Edit Custom {label}</b>\n\n"
        f"Silakan kirim {label.lower()} baru untuk tombol dashboard.\n\n"
        f"❌ <b>Batal:</b> Kirim /cancel",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Batal", "custom_link_settings", style=user_style)]])
    )
