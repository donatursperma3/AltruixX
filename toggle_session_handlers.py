# Confirmation and execution handlers for toggle session status
# Location: After line 307 in session_info.py

@Altruix.bot.on_callback_query(filters.regex(r"^toggle_session_confirm_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def toggle_session_confirm_handler(c: Client, cb: CallbackQuery):
    """Show confirmation dialog for enabling/disabling a session."""
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    
    if index >= len(Altruix.clients):
        return await cb.answer("❌ Session not found", show_alert=True)
    
    client = Altruix.clients[index]
    me = getattr(client, 'myself', None)
    if not me:
        me = await client.get_me()
        client.myself = me
    
    is_disabled = Altruix.is_session_disabled(me.id)
    action_text = "Enable" if is_disabled else "Disable"
    action_emoji = "✅" if is_disabled else "🔴"
    
    text = (
        f"<b>⚠️ Confirm Action</b>\n\n"
        f"Are you sure you want to <b>{action_emoji} {action_text}</b> this session?\n\n"
        f"<b>Session:</b> <a href='tg://user?id={me.id}'>{html.escape(me.first_name)}</a>\n"
        f"<b>ID:</b> <code>{me.id}</code>\n\n"
        f"<i>{'⚠️ This will prevent the userbot from responding to any commands (from owner, sudo, or itself).' if not is_disabled else '✅ This will re-enable command responses for this session.'}</i>"
    )
    
    buttons = [
        [
            InlineKeyboardButton("✅ Yes", f"toggle_session_execute_{index}_{page}"),
            InlineKeyboardButton("❌ No", f"session_info_{index}_{page}_1")
        ]
    ]
    
    await cb.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML,
        link_preview_options=LinkPreviewOptions(is_disabled=True)
    )

@Altruix.bot.on_callback_query(filters.regex(r"^toggle_session_execute_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def toggle_session_execute_handler(c: Client, cb: CallbackQuery):
    """Execute the session enable/disable toggle."""
    index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    
    if index >= len(Altruix.clients):
        return await cb.answer("❌ Session not found", show_alert=True)
    
    client = Altruix.clients[index]
    me = getattr(client, 'myself', None)
    if not me:
        me = await client.get_me()
        client.myself = me
    
    # Toggle the session
    new_status = Altruix.toggle_session_status(me.id)
    status_text = "enabled" if new_status else "disabled"
    status_emoji = "✅" if new_status else "🔴"
    
    await cb.answer(f"{status_emoji} Session {status_text}!", show_alert=True)
    
    # Return to session info
    await sessions_info_cb_handler(c, cb, index=index, callback_page=page, button_page=1)
