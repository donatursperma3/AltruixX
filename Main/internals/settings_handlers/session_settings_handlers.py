# Main/internals/settings_handlers/session_settings_handlers.py
import logging
import html
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from Main.core.decorators import log_errors, iuser_check
from Main.core.client import Altruix
from pyrogram.enums import ParseMode
from .utils import edit_cb, check_authorization

logger = logging.getLogger(__name__)

@Altruix.bot.on_callback_query(filters.regex(r"^session_settings_menu$"))
@iuser_check
@log_errors
async def session_settings_menu_handler(c: Client, cb: CallbackQuery):
    """Dashboard for Global Session Settings."""
    if not await check_authorization(cb): return
    await cb.answer()
    
    # Fetch current startup mode
    mode = await Altruix.config.get_env("STARTUP_MODE") or "on"
    mode = str(mode).lower()
    
    user_id = cb.from_user.id
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(user_id)
    
    # Descriptions for modes
    mode_desc = {
        "on": "✅ <b>ON</b> - Mengirim startup message ke group log untuk setiap sesi.",
        "test": "🔍 <b>TEST</b> - Tidak mengirim pesan startup, hanya melakukan test session (silent)."
    }
    
    text = (
        "<b>⚙️ Global Session Settings</b>\n\n"
        f"<b>Mode Startup Message:</b>\n"
        f"{mode_desc.get(mode, mode_desc['on'])}\n\n"
        "Gunakan tombol di bawah untuk mengganti mode operasional saat bot dimulai ulang."
    )
    
    # Check if all active sessions are disabled
    all_disabled = True
    active_count = 0
    for client in Altruix.clients:
        try:
            if client.me:
                active_count += 1
                if client.me.id not in Altruix.disabled_sessions:
                    all_disabled = False
                    break
        except: continue
    
    # Show Enable All if everything is disabled, otherwise show Disable All
    if active_count > 0 and all_disabled:
        btn_text = "✅ Enable All Session"
        btn_cb = "session_enable_all_confirm"
    else:
        btn_text = "🚫 Disable All Session"
        btn_cb = "session_disable_all_confirm"

    buttons = [
        [
            InlineKeyboardButton(f"Mode Startup: {mode.upper()}", "startup_mode_toggle", style=user_style),
            InlineKeyboardButton("📱 List Settings", "session_list_settings_menu", style=user_style)
        ],
        [
            InlineKeyboardButton("💎 Profile Manager Pro", "xprof_main", style=user_style)
        ],
        [
            InlineKeyboardButton(btn_text, btn_cb, style=user_style)
        ],
        [
            InlineKeyboardButton("🔙 Back to Settings", "settings_menu", style=user_style)
        ]
    ]
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons))

@Altruix.bot.on_callback_query(filters.regex(r"^startup_mode_toggle$"))
@iuser_check
@log_errors
async def startup_mode_toggle_handler(c: Client, cb: CallbackQuery):
    """Toggle Startup Mode between ON and TEST."""
    if not await check_authorization(cb): return
    
    current = await Altruix.config.get_env("STARTUP_MODE") or "on"
    new_mode = "test" if str(current).lower() == "on" else "on"
    
    # Save to DB/Cache
    await Altruix.config.set_env("STARTUP_MODE", new_mode)
    
    await cb.answer(f"Startup Mode: {new_mode.upper()}", show_alert=False)
    await session_settings_menu_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^session_list_settings_menu$"))
@iuser_check
@log_errors
async def session_list_settings_menu_handler(c: Client, cb: CallbackQuery):
    """Sub-menu for Session List settings."""
    if not await check_authorization(cb): return
    await cb.answer()
    
    # Fetch current list mode
    mode = await Altruix.config.get_env("SESSION_LIST_MODE") or "name"
    mode = str(mode).lower()
    
    user_id = cb.from_user.id
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(user_id)
    
    # Descriptions for modes
    mode_desc = {
        "name": "👤 <b>Account Name</b> - Menampilkan nama akun pada daftar sesi.",
        "id": "🆔 <b>Account ID</b> - Menampilkan ID akun pada daftar sesi."
    }
    
    text = (
        "<b>📱 Session List Settings</b>\n\n"
        "Pilih jenis informasi yang ingin ditampilkan pada tombol di daftar sesi:\n\n"
        f"<b>Mode Tampilan:</b>\n"
        f"{mode_desc.get(mode, mode_desc['name'])}\n"
    )
    
    buttons = [
        [
            InlineKeyboardButton(f"Display: {('NAME' if mode == 'name' else 'ID')}", "session_list_mode_toggle", style=user_style)
        ],
        [
            InlineKeyboardButton("🔙 Back", "session_settings_menu", style=user_style)
        ]
    ]
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons))

@Altruix.bot.on_callback_query(filters.regex(r"^session_list_mode_toggle$"))
@iuser_check
@log_errors
async def session_list_mode_toggle_handler(c: Client, cb: CallbackQuery):
    """Toggle Session List mode between NAME and ID."""
    if not await check_authorization(cb): return
    
    current = await Altruix.config.get_env("SESSION_LIST_MODE") or "name"
    new_mode = "id" if str(current).lower() == "name" else "name"
    
    # Save to DB/Cache
    await Altruix.config.set_env("SESSION_LIST_MODE", new_mode)
    
    await cb.answer(f"Display Mode: {new_mode.upper()}", show_alert=False)
    await session_list_settings_menu_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^session_disable_all_confirm$"))
@iuser_check
@log_errors
async def session_disable_all_confirm_handler(c: Client, cb: CallbackQuery):
    """Confirmation menu for Disable All Sessions."""
    if not await check_authorization(cb): return
    await cb.answer()
    
    user_id = cb.from_user.id
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(user_id)
    
    text = (
        "<b>⚠️ Konfirmasi Disable All Session</b>\n\n"
        "Apakah Anda yakin ingin menonaktifkan <b>SELURUH</b> sesi userbot?\n\n"
        "Setelah dinonaktifkan, semua akun tidak akan merespons perintah apapun sampai Anda mengaktifkannya kembali secara manual melalui menu Session Info."
    )
    
    buttons = [
        [
            InlineKeyboardButton("✅ Ya, Nonaktifkan Semua", "session_disable_all_execute", style=user_style),
            InlineKeyboardButton("❌ Batal", "session_settings_menu", style=user_style)
        ]
    ]
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons))

@Altruix.bot.on_callback_query(filters.regex(r"^session_disable_all_execute$"))
@iuser_check
@log_errors
async def session_disable_all_execute_handler(c: Client, cb: CallbackQuery):
    """Execute Disable All Sessions."""
    if not await check_authorization(cb): return
    
    count = 0
    # Collect all current client IDs
    for client in Altruix.clients:
        try:
            if client.me:
                Altruix.disabled_sessions.add(client.me.id)
                count += 1
        except: continue
        
    Altruix.save_disabled_sessions()
    
    await cb.answer(f"✅ {count} Sesi telah dinonaktifkan!", show_alert=True)
    await session_settings_menu_handler(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^session_enable_all_confirm$"))
@iuser_check
@log_errors
async def session_enable_all_confirm_handler(c: Client, cb: CallbackQuery):
    """Confirmation menu for Enable All Sessions."""
    if not await check_authorization(cb): return
    await cb.answer()
    
    user_id = cb.from_user.id
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(user_id)
    
    text = (
        "<b>✅ Konfirmasi Enable All Session</b>\n\n"
        "Apakah Anda yakin ingin mengaktifkan KEMBALI <b>SELURUH</b> sesi userbot?\n\n"
        "Setelah diaktifkan, semua akun akan kembali merespons perintah secara normal."
    )
    
    buttons = [
        [
            InlineKeyboardButton("✅ Ya, Aktifkan Semua", "session_enable_all_execute", style=user_style),
            InlineKeyboardButton("❌ Batal", "session_settings_menu", style=user_style)
        ]
    ]
    
    await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons))

@Altruix.bot.on_callback_query(filters.regex(r"^session_enable_all_execute$"))
@iuser_check
@log_errors
async def session_enable_all_execute_handler(c: Client, cb: CallbackQuery):
    """Execute Enable All Sessions."""
    if not await check_authorization(cb): return
    
    Altruix.disabled_sessions.clear()
    Altruix.save_disabled_sessions()
    
    await cb.answer("✅ Seluruh sesi telah diaktifkan kembali!", show_alert=True)
    await session_settings_menu_handler(c, cb)
