# Main/internals/settings_handlers/addons_handlers.py
import re
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from Main.core.decorators import log_errors, iuser_check
from Main.core.client import Altruix
from .utils import edit_cb, check_authorization

@Altruix.bot.on_callback_query(filters.regex(r"^toggle_addons_confirm_(?P<idx>\d+)_(?P<pg>\d+)$"))
@iuser_check
@log_errors
async def confirm_addons_handler(c: Client, cb: CallbackQuery):
    """Show confirmation for Altruix Addons Toggling"""
    await cb.answer()
    if not await check_authorization(cb): return
    
    idx = int(cb.matches[0].group("idx"))
    pg = int(cb.matches[0].group("pg"))
    
    current = await Altruix.config.get_env("LOAD_ULTROID_ADDONS", default="off")
    status_text = "ENABLED" if str(current).lower() in ("on", "true", "1", "yes") else "DISABLED"
    target_action = "DISABLE" if status_text == "ENABLED" else "ENABLE"
    
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)
    
    text = (
        f"<b>⚠️ CONFIRMATION</b>\n\n"
        f"Are you sure you want to <b>{target_action}</b> Altruix Addons (Ultroid Plugins)?\n\n"
        f"Current Status: <code>{status_text}</code>\n"
        f"<i>Note: Changes take effect after the next bot restart.</i>"
    )
    
    buttons = [
        [
            InlineKeyboardButton("✅ Yes", callback_data=f"toggle_addons_exec_{idx}_{pg}", style=user_style),
            InlineKeyboardButton("❌ No", callback_data=f"session_info_{idx}_{pg}_5", style=user_style)
        ],
        [
            InlineKeyboardButton("⌨️ Ultroid Prefix Settings", callback_data=f"ultroid_pfx_menu_{idx}_{pg}", style=user_style)
        ]
    ]
    
    await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Altruix.bot.on_callback_query(filters.regex(r"^toggle_addons_exec_(?P<idx>\d+)_(?P<pg>\d+)$"))
@iuser_check
@log_errors
async def toggle_addons_handler(c: Client, cb: CallbackQuery):
    """Execute Toggle Ultroid Addons Loading"""
    if not await check_authorization(cb): return
    
    idx = int(cb.matches[0].group("idx"))
    pg = int(cb.matches[0].group("pg"))
    
    current = await Altruix.config.get_env("LOAD_ULTROID_ADDONS", default="off")
    new_status = "on" if str(current).lower() in ("off", "false", "0", "no") else "off"
    
    await Altruix.config.sync_env_to_db("LOAD_ULTROID_ADDONS", new_status, upsert=True)
    
    status_text = "ENABLED" if new_status == "on" else "DISABLED"
    await cb.answer(f"Altruix Addons: {status_text}", show_alert=True)
    
    # Reload dashboard manually to avoid IndexError from Regex Group Mismatch
    from .session_info import get_session_info_data
    from pyrogram.enums import ParseMode
    from pyrogram.types import LinkPreviewOptions
    
    # We use pg (callback page) and then page 5 for button_page
    text, reply_markup = await get_session_info_data(idx, pg, 5)
    
    await cb.edit_message_text(
        text=f"╭━━━━━━━━━━━━━━━━━━━━━╮\n   <b>𝐒𝐄𝐒𝐒𝐈𝐎𝐍 𝐌𝐀𝐍𝐀𝐆𝐄𝐑</b>\n╰━━━━━━━━━━━━━━━━━━━━━╯\n\n<blockquote expandable>{text}</blockquote>",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
        link_preview_options=LinkPreviewOptions(is_disabled=True)
    )

# --- Ultroid Prefix Settings ---

@Altruix.bot.on_callback_query(filters.regex(r"^ultroid_pfx_menu_(?P<idx>\d+)_(?P<pg>\d+)$"))
@iuser_check
@log_errors
async def ultroid_prefix_menu_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    await cb.answer()
    
    idx = int(cb.matches[0].group("idx"))
    pg = int(cb.matches[0].group("pg"))
    
    # Get Settings
    apply_type = await Altruix.config.get_env("PREFIX_APPLY_TYPE") or "global"
    
    if apply_type == "global":
        u_p = await Altruix.config.get_env("ULTROID_PREFIX_OWNER") or ","
        s_p = await Altruix.config.get_env("ULTROID_PREFIX_SUDO") or "?"
        mode_text = "GLOBAL"
    else:
        client = Altruix.clients[idx]
        tid = client.me.id
        u_p = await Altruix.config.get_env(f"ULTROID_PREFIX_OWNER_{tid}") or ","
        s_p = await Altruix.config.get_env(f"ULTROID_PREFIX_SUDO_{tid}") or "?"
        mode_text = f"PER-ACCOUNT ({idx})"

    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)

    text = (
        f"<b>⌨️ Ultroid Prefix Settings ({mode_text})</b>\n\n"
        f"Configure triggers for Ultroid Addon commands.\n\n"
        f"• <b>Owner Prefix:</b> <code>{u_p}</code>\n"
        f"• <b>Sudo Prefix:</b> <code>{s_p}</code>\n\n"
        f"<i>Current Apply Type: {apply_type.upper()}</i>\n"
        f"Use the buttons below to change prefixes."
    )
    
    buttons = [
        [
            InlineKeyboardButton("Set Owner Prefix", callback_data=f"ultroid_set_pfx_u_{idx}_{pg}", style=user_style),
            InlineKeyboardButton("Set Sudo Prefix", callback_data=f"ultroid_set_pfx_s_{idx}_{pg}", style=user_style)
        ],
        [
            InlineKeyboardButton("🌿 Branches", callback_data=f"upm_branch_menu_{idx}_{pg}", style=user_style),
            InlineKeyboardButton("📂 Manage Files", callback_data=f"upm_files_menu_{idx}_{pg}_0", style=user_style)
        ],
        [InlineKeyboardButton("🔄 Sync All Addons", callback_data=f"update_addons_exec_{idx}_{pg}", style=user_style)],
        [InlineKeyboardButton("🔙 Back to Addons", callback_data=f"toggle_addons_confirm_{idx}_{pg}", style=user_style)]
    ]
    await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Altruix.bot.on_callback_query(filters.regex(r"^ultroid_set_pfx_(?P<type>u|s)_(?P<idx>\d+)_(?P<pg>\d+)$"))
@iuser_check
@log_errors
async def ultroid_set_pfx_prompt_handler(c: Client, cb: CallbackQuery):
    await cb.answer()
    if not await check_authorization(cb): return
    p_type = cb.matches[0].group("type")
    idx = int(cb.matches[0].group("idx"))
    pg = int(cb.matches[0].group("pg"))
    
    label = "Owner" if p_type == "u" else "Sudo"
    
    text = (
        f"<b>✏️ Set Ultroid {label} Prefix</b>\n\n"
        f"Please send the NEW prefix character you want to use for {label} Ultroid commands.\n"
        f"Example: <code>.</code> or <code>,</code> or <code>!</code>\n\n"
        f"<i>Send <code>/cancel</code> to abort.</i>"
    )
    
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)
    await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data=f"ultroid_pfx_menu_{idx}_{pg}", style=user_style)]]))
    
    from Main.internals.settings_handlers.states import WAIT_ULTROID_PREFIX, user_privacy_state
    user_privacy_state[cb.from_user.id] = {
        "step": f"{WAIT_ULTROID_PREFIX}_{p_type}",
        "session_index": idx,
        "page": pg
    }

# --- Manual Update Handler ---

@Altruix.bot.on_callback_query(filters.regex(r"^update_addons_exec_(?P<idx>\d+)_(?P<pg>\d+)$"))
@iuser_check
@log_errors
async def update_addons_exec_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    
    idx = int(cb.matches[0].group("idx"))
    pg = int(cb.matches[0].group("pg"))
    
    await cb.answer("⏳ Syncing addons from GitHub...", show_alert=False)
    await cb.edit_message_text(f"<b>⏳ SINKRONISASI SEDANG BERJALAN</b>\n\nSedang mengupdate addons dari GitHub repo. Harap tunggu sebentar...")
    
    success = await Altruix.upm.sync_addons()
    
    if success:
        text = (
            "<b>✅ SINKRONISASI BERHASIL!</b>\n\n"
            "Addons Ultroid telah berhasil diperbarui ke versi terbaru dari GitHub.\n\n"
            "<i>Catatan: Modul baru akan terdeteksi setelah Bot di RESTART.</i>"
        )
    else:
        text = (
            "<b>❌ SINKRONISASI GAGAL!</b>\n\n"
            "Gagal mengupdate addons. Periksa koneksi internet atau log terminal untuk detail error."
        )
        
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)
    buttons = [[InlineKeyboardButton("🔙 Back", callback_data=f"ultroid_pfx_menu_{idx}_{pg}", style=user_style)]]
    await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))


# --- UPM Branch Management ---

@Altruix.bot.on_callback_query(filters.regex(r"^upm_branch_menu_(?P<idx>\d+)_(?P<pg>\d+)$"))
@iuser_check
@log_errors
async def upm_branch_menu_handler(c: Client, cb: CallbackQuery):
    await cb.answer()
    if not await check_authorization(cb): return
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)
    idx = int(cb.matches[0].group("idx"))
    pg = int(cb.matches[0].group("pg"))
    
    current_branch = await Altruix.config.get_env("ULTROID_ADDONS_BRANCH", default="main")
    
    text = (
        f"<b>🌿 UPM Branch Management</b>\n\n"
        f"Current Branch: <code>{current_branch}</code>\n\n"
        f"Select a branch to switch to. Bot will perform <code>checkout</code> and <code>reset --hard</code>."
    )
    
    branches = ["main", "master", "dev"] # Custom list for now, could be dynamic
    buttons = []
    for br in branches:
        label = f"✅ {br}" if br == current_branch else br
        buttons.append([InlineKeyboardButton(label, callback_data=f"upm_set_branch_{br}_{idx}_{pg}", style=user_style)])
    
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"ultroid_pfx_menu_{idx}_{pg}", style=user_style)])
    await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Altruix.bot.on_callback_query(filters.regex(r"^upm_set_branch_(?P<br>\w+)_(?P<idx>\d+)_(?P<pg>\d+)$"))
@iuser_check
@log_errors
async def upm_set_branch_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    br = cb.matches[0].group("br")
    idx = int(cb.matches[0].group("idx"))
    pg = int(cb.matches[0].group("pg"))
    
    await cb.answer(f"Switching to {br}...", show_alert=False)
    success, msg = await Altruix.upm.switch_branch(br)
    
    await cb.answer(msg, show_alert=True)
    await upm_branch_menu_handler(c, cb)


# --- UPM File Management ---

@Altruix.bot.on_callback_query(filters.regex(r"^upm_files_menu_(?P<idx>\d+)_(?P<pg>\d+)_(?P<spg>\d+)$"))
@iuser_check
@log_errors
async def upm_manage_files_handler(c: Client, cb: CallbackQuery):
    await cb.answer()
    if not await check_authorization(cb): return
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)
    idx = int(cb.matches[0].group("idx"))
    pg = int(cb.matches[0].group("pg"))
    spg = int(cb.matches[0].group("spg"))
    
    addons = Altruix.upm.list_addons()
    text = f"<b>📂 UPM File Management ({len(addons)})</b>\n\nManage individual plugin files in <code>plugins/addons</code>."
    
    # Pagination for files (8 per page)
    CHUNK_SIZE = 8
    start = spg * CHUNK_SIZE
    end = start + CHUNK_SIZE
    current_addons = addons[start:end]
    
    buttons = []
    for addon in current_addons:
        buttons.append([
            InlineKeyboardButton(f"📄 {addon}", callback_data="none", style=user_style),
            InlineKeyboardButton("🗑️", callback_data=f"upm_del_file_{addon}_{idx}_{pg}_{spg}", style=user_style)
        ])
    
    # Nav buttons
    nav = []
    if spg > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"upm_files_menu_{idx}_{pg}_{spg-1}", style=user_style))
    if end < len(addons):
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"upm_files_menu_{idx}_{pg}_{spg+1}", style=user_style))
    if nav: buttons.append(nav)
    
    buttons.append([InlineKeyboardButton("➕ Install from URL", callback_data=f"upm_inst_prompt_{idx}_{pg}", style=user_style)])
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"ultroid_pfx_menu_{idx}_{pg}", style=user_style)])
    
    await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Altruix.bot.on_callback_query(filters.regex(r"^upm_del_file_(?P<name>.+)_(?P<idx>\d+)_(?P<pg>\d+)_(?P<spg>\d+)$"))
@iuser_check
@log_errors
async def upm_delete_file_handler(c: Client, cb: CallbackQuery):
    if not await check_authorization(cb): return
    name = cb.matches[0].group("name")
    idx = int(cb.matches[0].group("idx"))
    pg = int(cb.matches[0].group("pg"))
    spg = int(cb.matches[0].group("spg"))
    
    if await Altruix.upm.uninstall_plugin(name):
        await cb.answer(f"Deleted {name}", show_alert=True)
    else:
        await cb.answer(f"Failed to delete {name}", show_alert=True)
        
    await upm_manage_files_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^upm_inst_prompt_(?P<idx>\d+)_(?P<pg>\d+)$"))
@iuser_check
@log_errors
async def upm_install_prompt_handler(c: Client, cb: CallbackQuery):
    await cb.answer()
    if not await check_authorization(cb): return
    idx = int(cb.matches[0].group("idx"))
    pg = int(cb.matches[0].group("pg"))
    
    text = (
        "<b>➕ UPM: Install from URL</b>\n\n"
        "Please send the direct raw URL of the <code>.py</code> plugin you want to install.\n"
        "Example: <code>https://raw.githubusercontent.com/.../plugin.py</code>\n\n"
        "<i>Send <code>/cancel</code> to abort.</i>"
    )
    
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)
    await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data=f"upm_files_menu_{idx}_{pg}_0", style=user_style)]]))
    
    from Main.internals.settings_handlers.states import WAIT_UPM_INSTALL, user_privacy_state
    user_privacy_state[cb.from_user.id] = {
        "step": WAIT_UPM_INSTALL,
        "session_index": idx,
        "page": pg
    }

# --- Ultroid Input Processing ---

async def process_ultroid_prefix_input(c: Client, m: Message, state: dict):
    user_id = m.from_user.id
    text = m.text.strip()
    step = state.get("step", "")
    idx = state.get("session_index")
    pg = state.get("page")
    
    # Extract type (u or s)
    p_type = step.split("_")[-1] 
    label = "Owner" if p_type == "u" else "Sudo"
    
    if len(text) != 1:
        return await m.reply("❌ Prefix harus berupa **satu** karakter spesial saja (misal: <code>,</code> atau <code>?</code>).")

    # Resolve settings
    apply_type = await Altruix.config.get_env("PREFIX_APPLY_TYPE") or "global"
    client = Altruix.clients[idx]
    tid = client.me.id
    
    if apply_type == "global":
        key = "ULTROID_PREFIX_OWNER" if p_type == "u" else "ULTROID_PREFIX_SUDO"
    else:
        key = f"ULTROID_PREFIX_OWNER_{tid}" if p_type == "u" else f"ULTROID_PREFIX_SUDO_{tid}"

    await Altruix.config.sync_env_to_db(key, text, upsert=True)
    
    # Refresh Cache
    await Altruix.refresh_sudo_cache()
    
    from Main.internals.settings_handlers.states import user_privacy_state
    if user_id in user_privacy_state: del user_privacy_state[user_id]
    
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(user_id)
    await m.reply(
        f"✅ **Berhasil!** Prefix Ultroid {label} sekarang adalah: <code>{text}</code>",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Settings", callback_data=f"ultroid_pfx_menu_{idx}_{pg}", style=user_style)]])
    )

async def process_upm_install_input(c: Client, m: Message, state: dict):
    user_id = m.from_user.id
    url = m.text.strip()
    idx = state.get("session_index")
    pg = state.get("page")
    
    if not re.match(r"^https?://", url) or not url.endswith(".py"):
        return await m.reply("❌ **URL tidak valid!** Harap kirimkan direct link mentah (raw) menuju file <code>.py</code>.\nContoh: <code>https://raw.githubusercontent.com/.../plugin.py</code>")

    status_msg = await m.reply("⏳ **Mengunduh plugin...**")
    
    success, res_msg = await Altruix.upm.install_plugin(url)
    
    from Main.internals.settings_handlers.states import user_privacy_state
    if user_id in user_privacy_state: del user_privacy_state[user_id]
    
    if success:
        text = (
            f"✅ **Instalasi Berhasil!**\n\n"
            f"Plugin telah diunduh ke <code>plugins/addons</code>.\n"
            f"<i>{res_msg}</i>\n\n"
            f"Harap RESTART bot untuk memuat modul baru."
        )
    else:
        text = f"❌ **Gagal Menginstal!**\n\n`{res_msg}`"
        
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(user_id)
    await status_msg.edit(
        text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to UPM", callback_data=f"upm_files_menu_{idx}_{pg}_0", style=user_style)]])
    )
