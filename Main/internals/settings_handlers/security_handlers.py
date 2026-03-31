# Main/internals/settings_handlers/security_handlers.py
import html
import os
import asyncio
import logging
import io
from datetime import datetime
from pyrogram import Client, filters, raw
from pyrogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from Main.core.decorators import log_errors, iuser_check
from Main.core.client import Altruix
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait, RPCError

# States & Helpers
from .states import (
    user_privacy_state, user_confirmation_state,
    user_exec_state, user_eval_state
)
from .utils import edit_cb, check_authorization
# from .session_info import sessions_info_cb_handler

# Logger
logger = logging.getLogger(__name__)

# Privacy and 2FA Info moved to privacy_handlers.py

# --- Session Exports ---

from Main.utils.file_helpers import get_user_button_style
from .custom_alert_handlers import _get_session_user_id

@Altruix.bot.on_callback_query(filters.regex(r"^export_session_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def export_session_menu_handler(c: Client, cb: CallbackQuery):
    """Entry menu for choosing export method: File or Message"""
    index, page = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    await cb.answer()
    
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)
    
    text = (
        f"<blockquote expandable><b>📤 Export Session Option</b>\n\n"
        f"Choose how you want to export the session session for:\n"
        f"• <b>Account:</b> {Altruix.clients[index].me.first_name}\n"
        f"• <b>Index:</b> {index+1}\n\n"
        f"<i>Select an option below:</i></blockquote>"
    )
    
    buttons = [
        [
            InlineKeyboardButton("📂 Export as File", f"exs_file_{index}_{page}", style=user_style),
            InlineKeyboardButton("💬 View Message", f"exs_msg_{index}_{page}", style=user_style)
        ],
        [InlineKeyboardButton("🔙 Back to Session Info", f"session_info_{index}_{page}_4", style=user_style)]
    ]
    
    await edit_cb(cb, text=text, reply_markup=InlineKeyboardMarkup(buttons))

@Altruix.bot.on_callback_query(filters.regex(r"^exs_file_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def export_session_file_handler(c: Client, cb: CallbackQuery):
    """Export the .session file of current session to user's PM"""
    index, page = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    await cb.answer("📤 Exporting as file...", show_alert=False)
    
    from Main.utils.file_helpers import get_user_button_style
    # Resolve user_style
    if index < len(Altruix.clients):
        user_style = get_user_button_style(Altruix.clients[index].me.id)
    else:
        user_style = get_user_button_style(cb.from_user.id)
    
    file_name = Altruix.config.SESSION_NAMES[index] if index < len(Altruix.config.SESSION_NAMES) else None
    if not file_name:
        await cb.edit_message_text("<blockquote expandable>❌ Session file name not found.</blockquote>")
        return
        
    session_path = os.path.join("cache", f"{file_name}.session")
    
    # Back button for choice menu
    back_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"export_session_{index}_{page}", style=user_style)]])

    if os.path.exists(session_path):
        await c.send_document(
            chat_id=cb.from_user.id,
            document=session_path,
            caption=f"📄 <b>Session File</b>\n• User: {Altruix.clients[index].me.first_name}\n• Index: {index+1}",
            parse_mode=ParseMode.HTML
        )
        await cb.edit_message_text("<blockquote expandable>✅ Session file has been sent to your PM.</blockquote>", reply_markup=back_markup)
    else:
        # ✅ FALLBACK: Export as Session String if file not found
        try:
            import io
            target_client = Altruix.clients[index]
            session_str = await target_client.export_session_string()
            
            # Create a bytes stream for the string text
            file_stream = io.BytesIO(session_str.encode())
            file_stream.name = f"{file_name}_string.txt"
            
            await c.send_document(
                chat_id=cb.from_user.id,
                document=file_stream,
                caption=f"<blockquote expandable>📝 <b>Session String (Fallback)</b>\n"
                        f"• User: <b>{html.escape(target_client.me.first_name or 'Unknown')}</b>\n"
                        f"• Index: {index+1}\n\n"
                        f"<i>The physical .session file was not found in cache, so the session string has been exported instead.</i></blockquote>",
                parse_mode=ParseMode.HTML
            )
            await cb.edit_message_text("<blockquote expandable>✅ Session string has been sent to your PM (Fallback).</blockquote>", 
                                     reply_markup=back_markup)
        except Exception as e:
            await cb.edit_message_text(f"<blockquote expandable>❌ Session file not found, and fallback string export failed: <code>{html.escape(str(e))}</code></blockquote>", parse_mode=ParseMode.HTML, reply_markup=back_markup)

@Altruix.bot.on_callback_query(filters.regex(r"^exs_msg_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def export_session_msg_handler(c: Client, cb: CallbackQuery):
    """Export the session string as a clickable message in PM"""
    index, page = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    await cb.answer("💬 Sending session string...", show_alert=False)
    
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(cb.from_user.id)
    back_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"export_session_{index}_{page}", style=user_style)]])

    try:
        target_client = Altruix.clients[index]
        session_str = await target_client.export_session_string()
        
        msg_text = (
            f"<blockquote expandable>📝 <b>Session String Information</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>User:</b> {html.escape(target_client.me.first_name or 'Unknown')}\n"
            f"🆔 <b>ID:</b> <code>{target_client.me.id}</code>\n"
            f"🔢 <b>Index:</b> {index+1}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<b>👇 Click below to copy:</b>\n"
            f"<code>{session_str}</code>\n\n"
            f"⚠️ <b>WARNING:</b> Keep this string safe and never share it!</blockquote>"
        )
        
        await c.send_message(
            chat_id=cb.from_user.id,
            text=msg_text,
            parse_mode=ParseMode.HTML
        )
        await edit_cb(cb, text="<blockquote expandable>✅ Session string has been sent to your PM as a message.</blockquote>", reply_markup=back_markup)
    except Exception as e:
        await edit_cb(cb, text=f"<blockquote expandable>❌ Failed to fetch session string: <code>{html.escape(str(e))}</code></blockquote>", reply_markup=back_markup)

@Altruix.bot.on_callback_query(filters.regex(r"^gen_conf_export_phone_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def export_phone_cb_handler(c: Client, cb: CallbackQuery):
    """Export phone number linked to the session"""
    index, page = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    await cb.answer()
    client = Altruix.clients[index]
    me = await client.get_me()
    phone = me.phone_number if me.phone_number else "Hidden/N/A"
    
    # Resolve user_style
    from Main.utils.file_helpers import get_user_button_style
    if index < len(Altruix.clients):
        user_style = get_user_button_style(Altruix.clients[index].me.id)
    else:
        user_style = get_user_button_style(cb.from_user.id)

    await cb.edit_message_text(
        f"📱 <b>Phone Number Information</b>\n\n• Session: {index+1}\n• User: {me.first_name}\n• Phone: <code>+{phone}</code>",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}", style=user_style)]]),
        parse_mode=ParseMode.HTML
    )

# --- Tracking & Administrative ---

@Altruix.bot.on_callback_query(filters.regex(r"^gen_conf_track_profile_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def track_profile_handler(c: Client, cb: CallbackQuery):
    """Start SangMata-style profile tracking logic"""
    index, page = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    await cb.answer()
    
    # Simple state transition (logic matches old_settings on_message)
    # We use a global state to wait for target ID in on_message
    from .states import user_dlphoto_state # Reusing wait logic if compatible or define new
    user_id = cb.from_user.id
    
    # Resolve user_style
    from Main.utils.file_helpers import get_user_button_style
    if index < len(Altruix.clients):
        user_style = get_user_button_style(Altruix.clients[index].me.id)
    else:
        user_style = get_user_button_style(user_id)
    
    await cb.edit_message_text(
        "🔍 <b>Profile Tracker</b>\n\n"
        "Fitur ini akan mengecek history perubahan nama user melalui @SangMata_beta_bot.\n"
        "Silakan kirim <b>Target ID</b> atau <b>Username</b> user yang ingin dilacak.\n\n"
        "❌ <b>Cancel:</b> Kirim /cancel",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}", style=user_style)]])
    )

# --- Advanced Execution (Internal Use Only) ---

@Altruix.bot.on_callback_query(filters.regex(r"^gen_conf_exec_term_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def exec_term_start_handler(c: Client, cb: CallbackQuery):
    """Admin tool to run terminal commands via bot"""
    index, page = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    await cb.answer()
    user_exec_state[cb.from_user.id] = {'session_index': index, 'page': page, 'step': 'waiting_command', 'action': 'exec_terminal'}
    
    # Resolve user_style
    from Main.utils.file_helpers import get_user_button_style
    if index < len(Altruix.clients):
        user_style = get_user_button_style(Altruix.clients[index].me.id)
    else:
        user_style = get_user_button_style(cb.from_user.id)

    await cb.edit_message_text(
        "🖥️ <b>Terminal Execution</b>\n\n"
        "Silakan kirim perintah terminal yang ingin dijalankan.\n"
        "⚠️ <b>Gunakan dengan hati-hati.</b>\n\n"
        "❌ <b>Cancel:</b> /cancel",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}", style=user_style)]])
    )

@Altruix.bot.on_callback_query(filters.regex(r"^gen_conf_eval_exec_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def eval_exec_start_handler(c: Client, cb: CallbackQuery):
    """Admin tool to evaluate Python code via bot"""
    index, page = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    await cb.answer()
    user_eval_state[cb.from_user.id] = {'session_index': index, 'page': page, 'step': 'waiting_code', 'action': 'eval_python'}
    
    # Resolve user_style
    from Main.utils.file_helpers import get_user_button_style
    if index < len(Altruix.clients):
        user_style = get_user_button_style(Altruix.clients[index].me.id)
    else:
        user_style = get_user_button_style(cb.from_user.id)

    await cb.edit_message_text(
        "🐍 <b>Python Eval</b>\n\n"
        "Silakan kirim kode Python yang ingin dievaluasi.\n\n"
        "❌ <b>Cancel:</b> /cancel",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}", style=user_style)]])
    )
@Altruix.bot.on_callback_query(filters.regex(r"^check_limit_confirm_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def check_limit_confirm_handler(c: Client, cb: CallbackQuery):
    """Bridge to check account limits via @SpamBot"""
    index, page = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    await cb.answer("⏳ Checking limits...", show_alert=False)
    session_client = Altruix.clients[index]
    
    # Resolve user_style
    from Main.utils.file_helpers import get_user_button_style
    if index < len(Altruix.clients):
        user_style = get_user_button_style(Altruix.clients[index].me.id)
    else:
        user_style = get_user_button_style(cb.from_user.id)

    try:
        # Send message to SpamBot
        await session_client.send_message("SpamBot", "/start")
        await asyncio.sleep(1) # Wait for response
        
        # Get last message from SpamBot
        async for message in session_client.get_chat_history("SpamBot", limit=1):
            if message.text:
                await cb.edit_message_text(
                    f"<b>🚫 Limit Information (Session {index+1})</b>\n\n"
                    f"<code>{html.escape(message.text)}</code>",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}", style=user_style)]])
                )
                from Main.internals.settings_handlers.utils import send_log_notification
                await send_log_notification(c, 'check_limit', index, cb.from_user, True)
                return
        await cb.edit_message_text("❌ No response from @SpamBot.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}", style=user_style)]]))
    except Exception as e:
        await cb.edit_message_text(f"❌ Error checking limit: {str(e)}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}", style=user_style)]]))

# Duplicate 2FA check moved to privacy_handlers.py

# --- Email Management ---

@Altruix.bot.on_callback_query(filters.regex(r"change_login_email_(\d+)_(\d+)(?:_(\d+))?"))
@iuser_check
@log_errors
async def change_login_email_handler(c: Client, cb: CallbackQuery):
    """Handler awal untuk ganti login email (Review email saat ini)"""
    from .utils import gt, edit_cb
    await cb.answer()
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    
    if index >= len(Altruix.clients):
        await edit_cb(cb, "❌ Session tidak ditemukan.")
        return

    session_client = Altruix.clients[index]
    await edit_cb(cb, gt("fetching_security_info"))
    
    try:
        pwd_info = await session_client.invoke(raw.functions.account.GetPassword())
        email_pattern = getattr(pwd_info, "login_email_pattern", None)
        has_password = getattr(pwd_info, "has_password", False)
        
        email_display = f"<code>{html.escape(email_pattern)}</code>" if email_pattern else f"<i>{gt('inactive')}</i>"
        
        text = (
            f"<b>📧 Change Login Email</b>\n\n"
            f"• Current Email: {email_display}\n"
            f"• 2FA Password: <code>{'Active' if has_password else 'Inactive'}</code>\n\n"
            f"Apakah Anda ingin melanjutkan penggantian email login?\n"
            f"Kode verifikasi akan dikirim ke email baru."
        )
        
        # Resolve user_style
        from Main.utils.file_helpers import get_user_button_style
        if index < len(Altruix.clients):
            user_style = get_user_button_style(Altruix.clients[index].me.id)
        else:
            user_style = get_user_button_style(cb.from_user.id)
        
        buttons = [
            [
                InlineKeyboardButton(gt("yes_continue"), f"change_email_start_{index}_{page}_{button_page}", style=user_style),
                InlineKeyboardButton(gt("cancel"), f"session_info_{index}_{page}_{button_page}", style=user_style)
            ]
        ]
        await edit_cb(cb, text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
    except Exception as e:
        await edit_cb(cb, f"❌ Error: {str(e)}")

@Altruix.bot.on_callback_query(filters.regex(r"change_email_start_(\d+)_(\d+)(?:_(\d+))?"))
@iuser_check
@log_errors
async def change_email_start_handler(c: Client, cb: CallbackQuery):
    """Handler untuk memulai input email baru"""
    from .utils import gt, edit_cb
    await cb.answer()
    index, page = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if len(cb.matches[0].groups()) >= 3 and cb.matches[0].group(3) else 1
    user_id = cb.from_user.id
    
    await edit_cb(cb, "📧 Silakan kirim <b>Email Baru</b> Anda sekarang.\nKetik <code>/cancel</code> untuk membatalkan.")
    
    try:
        msg_email = await c.listen(filters.chat(user_id) & filters.text, timeout=120)
        new_email = msg_email.text.strip().lower()
        
        if new_email == "/cancel":
            await msg_email.reply("❌ Penggantian email dibatalkan.")
            from .session_info import sessions_info_cb_handler
            await sessions_info_cb_handler(c, cb, index=index, callback_page=page, button_page=button_page)
            return

        if "@" not in new_email or "." not in new_email:
            await msg_email.reply("❌ Format email tidak valid.")
            return

        await edit_cb(cb, f"⏳ Mengirim kode verifikasi ke <code>{html.escape(new_email)}</code>...")
        
        # Kirim kode
        purpose = raw.types.EmailVerifyPurposeLoginChange()
        await Altruix.clients[index].invoke(raw.functions.account.SendVerifyEmailCode(email=new_email, purpose=purpose))
        
        await edit_cb(cb, f"✅ Kode dikirim ke <code>{html.escape(new_email)}</code>.\nSilakan kirim kode verifikasi yang Anda terima.")
        
        msg_code = await c.listen(filters.chat(user_id) & filters.text, timeout=300)
        verify_code = msg_code.text.strip()
        
        if verify_code == "/cancel":
            await msg_code.reply("❌ Batal.")
            return

        await edit_cb(cb, "⏳ Verifikasi...")
        verification = raw.types.EmailVerificationCode(code=verify_code)
        await Altruix.clients[index].invoke(raw.functions.account.UpdateLoginEmailAddress(new_email=new_email, verification=verification))
        
        await edit_cb(cb, "✅ <b>Email login berhasil diubah!</b>")
        await send_log_notification(c, 'change_email', index, cb.from_user, True, additional_info={'Email': new_email})
        
    except asyncio.TimeoutExpired:
        await cb.edit_message_text("⏰ Waktu habis. Silakan ulangi.")
    except RPCError as e:
        await edit_cb(cb, f"❌ Error: {e.MESSAGE}")
    except Exception as e:
        await edit_cb(cb, f"❌ Error: {str(e)}")
