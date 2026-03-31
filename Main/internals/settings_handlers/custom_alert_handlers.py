# Main/internals/settings_handlers/custom_alert_handlers.py
import html
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode
from pyromod.exceptions import ListenerTimeout

from Main.core.client import Altruix
from Main.core.decorators import iuser_check, log_errors
from Main.utils.file_helpers import get_custom_alert_data, save_custom_alert_data

def _get_session_user_id(index: int) -> int:
    """
    ✅ Consistently get the USERBOT session owner's user ID by session index (1-based).
    This must match the ID used in decorators.py (Altruix.clients[0].me.id for global).
    """
    try:
        client = Altruix.clients[index - 1]
        if hasattr(client, 'me') and client.me:
            return client.me.id
    except (IndexError, AttributeError):
        pass
    # Fallback: first available session
    if Altruix.clients:
        first = Altruix.clients[0]
        if hasattr(first, 'me') and first.me:
            return first.me.id
    return Altruix.config.OWNER_ID

@Altruix.bot.on_callback_query(filters.regex(r"^custom_alert_menu_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def custom_alert_menu_cb(c: Client, cb: CallbackQuery):
    await cb.answer()
    if not await Altruix.is_sudo(cb.from_user.id): return
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    # ✅ Always use the USERBOT session's user ID as the key
    user_id = _get_session_user_id(index)
    user_style = get_user_button_style(user_id)
    
    data = get_custom_alert_data()
    apply_type = data.get("apply_types", {}).get(str(user_id), "global")
    
    if apply_type == "global":
        settings = data["global"]
        scope = "🌍 Global"
    else:
        if str(user_id) not in data.get("sessions", {}):
            data.setdefault("sessions", {})[str(user_id)] = {"mode": "default", "text": "⛔️ You are not allowed to use this button."}
            save_custom_alert_data(data)
        settings = data["sessions"][str(user_id)]
        scope = "👤 Per-Account"
        
    mode = settings.get("mode", "default").title()
    current_text = settings.get("text", "⛔️ You are not allowed to use this button.")
    
    text = (
        f"<b>🚨 Custom Alert Settings</b>\n\n"
        f"Customize the popup message shown when an unauthorized user clicks a restricted bot button.\n\n"
        f"<b>Scope:</b> <code>{scope}</code>\n"
        f"<b>Mode:</b> <code>{mode}</code>\n\n"
        f"<b>Current Message:</b>\n"
        f"<blockquote>{html.escape(current_text)}</blockquote>\n\n"
        f"<i>Select an option below to configure:</i>"
    )
    
    buttons = [
        [InlineKeyboardButton(f"🔁 Mode: {mode}", callback_data=f"toggle_alert_mode_{index}_{page}", style=user_style),
         InlineKeyboardButton(f"🌐 Scope: {apply_type.title().replace('_', ' ')}", callback_data=f"toggle_alert_type_{index}_{page}", style=user_style)],
        [InlineKeyboardButton("✍️ Set Custom Text", callback_data=f"set_alert_text_{index}_{page}", style=user_style)],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data=f"session_info_{index}_{page}_5", style=user_style)]
    ]
    
    await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^toggle_alert_type_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def toggle_alert_type_cb(c: Client, cb: CallbackQuery):
    await cb.answer()
    if not await Altruix.is_sudo(cb.from_user.id): return
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    user_id = _get_session_user_id(index)
    
    data = get_custom_alert_data()
    current_type = data.setdefault("apply_types", {}).get(str(user_id), "global")
    new_type = "per_account" if current_type == "global" else "global"
    data["apply_types"][str(user_id)] = new_type
    
    if new_type == "per_account" and str(user_id) not in data.get("sessions", {}):
        data.setdefault("sessions", {})[str(user_id)] = {"mode": "default", "text": "⛔️ You are not allowed to use this button."}
        
    save_custom_alert_data(data)
    cb.matches = [type('obj', (object,), {'group': lambda self, i: str(index) if i==1 else str(page)})()]
    await custom_alert_menu_cb(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^toggle_alert_mode_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def toggle_alert_mode_cb(c: Client, cb: CallbackQuery):
    if not await Altruix.is_sudo(cb.from_user.id): return
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    user_id = _get_session_user_id(index)
    
    data = get_custom_alert_data()
    apply_type = data.get("apply_types", {}).get(str(user_id), "global")
    
    if apply_type == "global":
        current_mode = data["global"].get("mode", "default")
        data["global"]["mode"] = "custom" if current_mode == "default" else "default"
    else:
        current_mode = data["sessions"][str(user_id)].get("mode", "default")
        data["sessions"][str(user_id)]["mode"] = "custom" if current_mode == "default" else "default"
        
    save_custom_alert_data(data)
    cb.matches = [type('obj', (object,), {'group': lambda self, i: str(index) if i==1 else str(page)})()]
    await custom_alert_menu_cb(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^set_alert_text_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def set_alert_text_btn(c: Client, cb: CallbackQuery):
    if not await Altruix.is_sudo(cb.from_user.id): return
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    chat_user_id = cb.from_user.id  # For listen() - who to wait input from
    
    msg = await cb.message.reply_text(
        "<b>✍️ Sila kirim text baru untuk Custom Alert.</b>\n"
        "<i>Text ini akan muncul sebagai pop-up notifikasi bagi user yang tidak diizinkan.</i>\n\n"
        "Ketik /cancel untuk membatalkan.",
        parse_mode=ParseMode.HTML
    )
    
    try:
        response = await c.listen(chat_id=cb.message.chat.id, user_id=chat_user_id, timeout=60)
        await response.delete()
        if response.text and response.text.startswith("/cancel"):
            await msg.edit("❌ Proses dibatalkan.")
            return
            
        if not response.text:
            await msg.edit("❌ Input tidak valid (hanya mendukung teks).")
            return
            
        if len(response.text) > 150:
            await msg.edit("❌ Pesan terlalu panjang. (Maksimal 150 karakter untuk Inline Alert).")
            return
        
        # ✅ Use the USERBOT's user ID as the key (consistent with decorators.py)
        session_user_id = _get_session_user_id(index)
        data = get_custom_alert_data()
        apply_type = data.get("apply_types", {}).get(str(session_user_id), "global")
        
        if apply_type == "global":
            data["global"]["text"] = response.text
            data["global"]["mode"] = "custom"
        else:
            if str(session_user_id) not in data.get("sessions", {}):
                data.setdefault("sessions", {})[str(session_user_id)] = {}
            data["sessions"][str(session_user_id)]["text"] = response.text
            data["sessions"][str(session_user_id)]["mode"] = "custom"
            
        save_custom_alert_data(data)
        await msg.edit(f"✅ <b>Custom Alert berhasil diatur!</b>\n\n<blockquote>{html.escape(response.text)}</blockquote>", parse_mode=ParseMode.HTML)
        
        # Refresh Menu
        cb.matches = [type('obj', (object,), {'group': lambda self, i: str(index) if i==1 else str(page)})()]
        await custom_alert_menu_cb(c, cb)
        
    except ListenerTimeout:
        await msg.edit("⏳ Waktu habis. Proses dibatalkan.")
