# Main/internals/settings_handlers/button_style_handlers.py
import html
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode

from Main.core.client import Altruix
from Main.core.decorators import iuser_check, log_errors
from Main.utils.file_helpers import get_button_style_data, save_button_style_data

# Style cycle order
STYLE_CYCLE = ["DEFAULT", "PRIMARY", "DANGER", "SUCCESS"]

# Display info for each style
STYLE_DISPLAY = {
    "DEFAULT": {"icon": "⬜", "label": "Default", "desc": "Abu-abu (Telegram Default)"},
    "PRIMARY": {"icon": "🔵", "label": "Primary", "desc": "Dark Blue"},
    "DANGER":  {"icon": "🔴", "label": "Danger", "desc": "Red"},
    "SUCCESS": {"icon": "🟢", "label": "Success", "desc": "Green"},
}

def _get_session_user_id(index: int) -> int:
    """Get the USERBOT session owner's user ID by session index."""
    try:
        client = Altruix.clients[index]
        if hasattr(client, 'myself') and client.myself:
            return client.myself.id
        if hasattr(client, 'me') and client.me:
            return client.me.id
    except (IndexError, AttributeError):
        pass
    if Altruix.clients:
        first = Altruix.clients[0]
        if hasattr(first, 'me') and first.me:
            return first.me.id
    return Altruix.config.OWNER_ID


@Altruix.bot.on_callback_query(filters.regex(r"^btn_style_menu_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def btn_style_menu_cb(c: Client, cb: CallbackQuery):
    """Main menu for Button Style settings."""
    if not await Altruix.is_sudo(cb.from_user.id): return
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    user_id = _get_session_user_id(index)
    
    data = get_button_style_data()
    apply_type = data.get("apply_types", {}).get(str(user_id), "global")
    
    if apply_type == "global":
        current_style = data["global"].get("style", "DEFAULT")
        scope = "🌍 Global"
    else:
        if str(user_id) not in data.get("sessions", {}):
            data.setdefault("sessions", {})[str(user_id)] = {"style": "DEFAULT"}
            save_button_style_data(data)
        current_style = data["sessions"][str(user_id)].get("style", "DEFAULT")
        scope = "👤 Per-Account"
    
    style_info = STYLE_DISPLAY.get(current_style, STYLE_DISPLAY["DEFAULT"])
    
    # Build preview of all styles
    preview_lines = []
    for key, info in STYLE_DISPLAY.items():
        marker = "  ◀️" if key == current_style else ""
        preview_lines.append(f"  {info['icon']} <code>{info['label']}</code> — {info['desc']}{marker}")
    preview_text = "\n".join(preview_lines)
    
    text = (
        f"<b>🎨 Pengaturan Button Style</b>\n\n"
        f"Ubah warna/style semua tombol inline di akun ini.\n\n"
        f"<b>Scope:</b> <code>{scope}</code>\n"
        f"<b>Style Saat Ini:</b> {style_info['icon']} <code>{style_info['label']}</code>\n\n"
        f"<b>Pilihan Style:</b>\n"
        f"{preview_text}\n\n"
        f"<i>Style akan diterapkan ke semua tombol di Session Info dashboard.</i>"
    )
    
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(user_id)
    
    buttons = [
        [
            InlineKeyboardButton(
                f"🎨 Style: {style_info['icon']} {style_info['label']}", 
                callback_data=f"toggle_btn_style_{index}_{page}",
                style=user_style
            ),
            InlineKeyboardButton(
                f"🌐 Scope: {apply_type.title().replace('_', ' ')}", 
                callback_data=f"toggle_btn_style_type_{index}_{page}",
                style=user_style
            )
        ],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data=f"session_info_{index}_{page}_5", style=user_style)]
    ]
    
    await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)


@Altruix.bot.on_callback_query(filters.regex(r"^toggle_btn_style_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def toggle_btn_style_cb(c: Client, cb: CallbackQuery):
    """Cycle button style: DEFAULT → PRIMARY → DANGER → SUCCESS → DEFAULT"""
    if not await Altruix.is_sudo(cb.from_user.id): return
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    user_id = _get_session_user_id(index)
    
    data = get_button_style_data()
    apply_type = data.get("apply_types", {}).get(str(user_id), "global")
    
    if apply_type == "global":
        current = data["global"].get("style", "DEFAULT")
        next_idx = (STYLE_CYCLE.index(current) + 1) % len(STYLE_CYCLE)
        data["global"]["style"] = STYLE_CYCLE[next_idx]
    else:
        if str(user_id) not in data.get("sessions", {}):
            data.setdefault("sessions", {})[str(user_id)] = {"style": "DEFAULT"}
        current = data["sessions"][str(user_id)].get("style", "DEFAULT")
        next_idx = (STYLE_CYCLE.index(current) + 1) % len(STYLE_CYCLE)
        data["sessions"][str(user_id)]["style"] = STYLE_CYCLE[next_idx]
    
    save_button_style_data(data)
    new_style = STYLE_CYCLE[next_idx]
    new_info = STYLE_DISPLAY.get(new_style, STYLE_DISPLAY["DEFAULT"])
    await cb.answer(f"✅ Style → {new_info['icon']} {new_info['label']}", show_alert=True)
    
    # Refresh menu
    cb.matches = [type('obj', (object,), {'group': lambda self, i: str(index) if i==1 else str(page)})()]
    await btn_style_menu_cb(c, cb)


@Altruix.bot.on_callback_query(filters.regex(r"^toggle_btn_style_type_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def toggle_btn_style_type_cb(c: Client, cb: CallbackQuery):
    """Toggle apply type: Global ↔ Per-Account"""
    if not await Altruix.is_sudo(cb.from_user.id): return
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    user_id = _get_session_user_id(index)
    
    data = get_button_style_data()
    current_type = data.setdefault("apply_types", {}).get(str(user_id), "global")
    new_type = "per_account" if current_type == "global" else "global"
    data["apply_types"][str(user_id)] = new_type
    
    if new_type == "per_account" and str(user_id) not in data.get("sessions", {}):
        data.setdefault("sessions", {})[str(user_id)] = {"style": "DEFAULT"}
    
    save_button_style_data(data)
    await cb.answer(f"✅ Scope → {new_type.replace('_', ' ').title()}", show_alert=True)
    
    # Refresh menu
    cb.matches = [type('obj', (object,), {'group': lambda self, i: str(index) if i==1 else str(page)})()]
    await btn_style_menu_cb(c, cb)
