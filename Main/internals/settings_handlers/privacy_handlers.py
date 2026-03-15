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
    
    session_id = Altruix.clients[index].me.id if index < len(Altruix.clients) and hasattr(Altruix.clients[index], 'me') and Altruix.clients[index].me else cb.from_user.id
    user_style = get_user_button_style(session_id)

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
async def native_privacy_menu_handler(c: Client, cb: CallbackQuery, index: int = None, page: int = None, button_page: int = None):
    """Dynamic Native Telegram Privacy Settings Menu using Raw Functions"""
    if index is None:
        index = int(cb.matches[0].group(1))
        page = int(cb.matches[0].group(2))
        button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    await cb.answer("Fetching privacy settings...", show_alert=False)
    
    session_client = Altruix.clients[index]
    
    async def get_raw_status(p_key):
        try:
            res = await session_client.invoke(raw.functions.account.GetPrivacy(key=p_key))
            rules = res.rules
            if not rules: return "Unknown"
            
            # Check for primary permissive/restrictive rules
            for rule in rules:
                if isinstance(rule, raw.types.PrivacyValueAllowAll): return "Everybody ✅"
                if isinstance(rule, raw.types.PrivacyValueAllowContacts): return "My Contacts 👥"
                if isinstance(rule, raw.types.PrivacyValueDisallowAll): return "Nobody 🔒"
            return "Custom 🛠️"
        except Exception as e:
            logger.error(f"Failed to fetch privacy for {p_key}: {e}")
            return "Error ⚠️"

    status_phone = await get_raw_status(raw.types.InputPrivacyKeyPhoneNumber())
    status_seen = await get_raw_status(raw.types.InputPrivacyKeyStatusTimestamp())
    status_photo = await get_raw_status(raw.types.InputPrivacyKeyProfilePhoto())
    status_fwd = await get_raw_status(raw.types.InputPrivacyKeyForwards())
    status_calls = await get_raw_status(raw.types.InputPrivacyKeyPhoneCall())
    status_groups = await get_raw_status(raw.types.InputPrivacyKeyChatInvite())

    text = (
        f"<b>🔒 Privacy Settings (Native)</b>\n"
        f"Session: {session_client.me.mention}\n\n"
        f"Atur siapa yang dapat melihat atau melakukan hal berikut:\n\n"
        f"• <b>Phone Number:</b> {status_phone}\n"
        f"• <b>Last Seen & Online:</b> {status_seen}\n"
        f"• <b>Profile Photos:</b> {status_photo}\n"
        f"• <b>Forwarded Messages:</b> {status_fwd}\n"
        f"• <b>Calls:</b> {status_calls}\n"
        f"• <b>Groups & Channels:</b> {status_groups}\n\n"
        f"<i>Klik kategori di bawah untuk mengubah status.</i>"
    )
    
    from Main.utils.file_helpers import get_user_button_style
    session_id = session_client.me.id
    user_style = get_user_button_style(session_id)
    
    buttons = [
        [
            InlineKeyboardButton("📱 Phone Number", f"np_sub_phone_{index}_{page}_{button_page}", style=user_style),
            InlineKeyboardButton("🕒 Last Seen", f"np_sub_lastseen_{index}_{page}_{button_page}", style=user_style)
        ],
        [
            InlineKeyboardButton("🖼️ Profile Photo", f"np_sub_photo_{index}_{page}_{button_page}", style=user_style),
            InlineKeyboardButton("⏩ Forwards", f"np_sub_fwd_{index}_{page}_{button_page}", style=user_style)
        ],
        [
            InlineKeyboardButton("📞 Calls", f"np_sub_calls_{index}_{page}_{button_page}", style=user_style),
            InlineKeyboardButton("👥 Groups", f"np_sub_groups_{index}_{page}_{button_page}", style=user_style)
        ],
        [InlineKeyboardButton("🔙 Back", f"privacy_menu_{index}_{page}_{button_page}", style=user_style)]
    ]
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^np_sub_(phone|lastseen|photo|fwd|calls|groups)_(\d+)_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def native_privacy_submenu_handler(c: Client, cb: CallbackQuery):
    """Submenu for specific privacy category"""
    category = cb.matches[0].group(1)
    index = int(cb.matches[0].group(2))
    page = int(cb.matches[0].group(3))
    button_page = int(cb.matches[0].group(4))
    
    cat_labels = {
        "phone": "Phone Number",
        "lastseen": "Last Seen & Online",
        "photo": "Profile Photos",
        "fwd": "Forwarded Messages",
        "calls": "Calls",
        "groups": "Groups & Channels"
    }
    
    p_label = cat_labels[category]
    await cb.answer()
    
    from Main.utils.file_helpers import get_user_button_style
    session_id = Altruix.clients[index].me.id
    user_style = get_user_button_style(session_id)
    
    text = f"<b>🔒 Edit Privacy: {p_label}</b>\n\nSiapa yang dapat melihat {p_label.lower()} Anda?"
    
    buttons = [
        [InlineKeyboardButton("Everybody 🌍", f"np_set_{category}_all_{index}_{page}_{button_page}", style=user_style)],
        [InlineKeyboardButton("My Contacts 👥", f"np_set_{category}_contacts_{index}_{page}_{button_page}", style=user_style)],
        [InlineKeyboardButton("Nobody 🔒", f"np_set_{category}_none_{index}_{page}_{button_page}", style=user_style)],
        [InlineKeyboardButton("🔙 Back", f"native_privacy_menu_{index}_{page}_{button_page}", style=user_style)]
    ]
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^np_set_(phone|lastseen|photo|fwd|calls|groups)_(all|contacts|none)_(\d+)_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def native_privacy_set_handler(c: Client, cb: CallbackQuery):
    """Handler to apply privacy changes using raw.functions.account.SetPrivacy"""
    category = cb.matches[0].group(1)
    rule_key = cb.matches[0].group(2)
    index = int(cb.matches[0].group(3))
    page = int(cb.matches[0].group(4))
    button_page = int(cb.matches[0].group(5))
    
    cat_map = {
        "phone": (raw.types.InputPrivacyKeyPhoneNumber(), "Phone Number"),
        "lastseen": (raw.types.InputPrivacyKeyStatusTimestamp(), "Last Seen & Online"),
        "photo": (raw.types.InputPrivacyKeyProfilePhoto(), "Profile Photos"),
        "fwd": (raw.types.InputPrivacyKeyForwards(), "Forwarded Messages"),
        "calls": (raw.types.InputPrivacyKeyPhoneCall(), "Calls"),
        "groups": (raw.types.InputPrivacyKeyChatInvite(), "Groups & Channels")
    }
    
    rule_map = {
        "all": ([raw.types.InputPrivacyValueAllowAll()], "Everybody"),
        "contacts": ([raw.types.InputPrivacyValueAllowContacts()], "My Contacts"),
        "none": ([raw.types.InputPrivacyValueDisallowAll()], "Nobody")
    }
    
    p_key, p_label = cat_map[category]
    p_rules, r_label = rule_map[rule_key]
    
    session_client = Altruix.clients[index]
    await cb.answer(f"Updating {p_label} to {r_label}...", show_alert=False)
    
    try:
        await session_client.invoke(raw.functions.account.SetPrivacy(key=p_key, rules=p_rules))
        
        # Log to Group Log
        from .utils import send_log_notification
        await send_log_notification(
            c, f"privacy_change_{category}", index, cb.from_user, True, 
            additional_info={"Type": p_label, "New Value": r_label}
        )
        
        await cb.answer(f"✅ {p_label} updated to {r_label}!", show_alert=True)
        await native_privacy_menu_handler(c, cb, index=index, page=page, button_page=button_page)
        
    except Exception as e:
        logger.error(f"Failed to set privacy for {category}: {e}")
        await cb.answer(f"❌ Failed: {str(e)[:100]}", show_alert=True)

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
    session_id = Altruix.clients[index].me.id if index < len(Altruix.clients) and hasattr(Altruix.clients[index], 'me') and Altruix.clients[index].me else cb.from_user.id
    user_style = get_user_button_style(session_id)

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
    session_id = Altruix.clients[index].me.id if index < len(Altruix.clients) and hasattr(Altruix.clients[index], 'me') and Altruix.clients[index].me else cb.from_user.id
    user_style = get_user_button_style(session_id)
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
    session_id = Altruix.clients[index].me.id if index < len(Altruix.clients) and hasattr(Altruix.clients[index], 'me') and Altruix.clients[index].me else cb.from_user.id
    user_style = get_user_button_style(session_id)

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
    session_id = Altruix.clients[index].me.id if index < len(Altruix.clients) and hasattr(Altruix.clients[index], 'me') and Altruix.clients[index].me else cb.from_user.id
    user_style = get_user_button_style(session_id)
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
    session_id = Altruix.clients[index].me.id if index < len(Altruix.clients) and hasattr(Altruix.clients[index], 'me') and Altruix.clients[index].me else cb.from_user.id
    user_style = get_user_button_style(session_id)
    
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
        session_id = Altruix.clients[index].me.id if index < len(Altruix.clients) and hasattr(Altruix.clients[index], 'me') and Altruix.clients[index].me else cb.from_user.id
        user_style = get_user_button_style(session_id)
        
        await edit_cb(cb, txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"privacy_menu_{index}_{page}", style=user_style)]]) )
    except Exception as e:
        from Main.utils.file_helpers import get_user_button_style
        session_id = Altruix.clients[index].me.id if index < len(Altruix.clients) and hasattr(Altruix.clients[index], 'me') and Altruix.clients[index].me else cb.from_user.id
        user_style = get_user_button_style(session_id)
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
    session_id = Altruix.clients[index].me.id if index < len(Altruix.clients) and hasattr(Altruix.clients[index], 'me') and Altruix.clients[index].me else cb.from_user.id
    user_style = get_user_button_style(session_id)
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
    user_style = get_user_button_style(cb.from_user.id) # This one is actually for the interacting user in Bot Controls
    label = "Teks" if target == "text" else "Link"
    await cb.edit_message_text(
        f"📝 <b>Edit Custom {label}</b>\n\n"
        f"Silakan kirim {label.lower()} baru untuk tombol dashboard.\n\n"
        f"❌ <b>Batal:</b> Kirim /cancel",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Batal", "custom_link_settings", style=user_style)]])
    )
