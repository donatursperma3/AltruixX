import re

# Read the file
with open(r'f:\2025\DESEMBER\altruix\AltruixX\Main\internals\settings.py', 'r', encoding='utf-8') as f:
    content = f.read()

# List of handlers that need authorization (excluding message handlers and text handlers)
# We only want callback query handlers
callback_handlers = [
    'bulk_join_menu_handler',
    'bulk_leave_menu_handler', 
    'bulk_report_menu_handler',
    'bulk_join_delay_handler',
    'bulk_leave_delay_handler',
    'bulk_report_delay_handler',
    'bulk_join_confirm_handler',
    'bulk_leave_confirm_handler',
    'bulk_report_confirm_handler',
    'bulk_report_reason_handler',
    'sessions_info_cb_handler',
    'change_name_menu_handler',
    'change_first_name_handler',
    'change_last_name_handler',
    'change_bio_handler',
    'change_username_handler',
    'change_profile_photo_handler',
    'delete_all_profile_photos_handler',
    'unlink_session_cb_handler',
    'unlink_confirm_handler',
    'export_session_cb_handler',
    'export_phone_cb_handler',
    'test_ping_cb_handler',
    'test_ping_all_confirmation_handler',
    'test_ping_all_execute_handler',
    'test_ping_all_cancel_handler',
    'export_all_sessions_confirmation_handler',
    'export_all_sessions_confirm_yes_handler',
    'export_all_sessions_cancel_handler',
    'export_all_phones_confirmation_handler',
    'export_all_phones_confirm_yes_handler',
    'export_all_phones_cancel_handler',
    'join_log_group_handler',
    'pml_menu_handler',
    'pml_toggle_handler',
    'pml_filters_menu_handler',
    'pmlf_list_handler',
    'pmlf_toggle_handler',
    'mnt_menu_handler',
    'mnt_toggle_handler',
    'mnt_filters_menu_handler',
    'mntf_list_handler',
    'mntf_toggle_handler',
    'joinl_menu_handler',
    'joinl_toggle_handler',
    'cmdl_menu_handler',
    'cmdl_toggle_handler',
    'view_mentions_menu_handler',
    'mention_count_handler',
    'cancel_mention_handler',
    'recent_messages_menu_handler',
    'recent_messages_quick_handler',
    'recent_messages_custom_handler',
    'leave_chat_input_handler',
    'leave_chat_confirm_handler',
    'send_message_input_handler',
    'send_msg_confirm_handler',
    'purge_msg_start_handler',
    'purge_mode_handler',
    'purge_amt_handler',
    'purge_exec_handler',
    'purge_del_handler',
    'dl_uphoto_start_handler',
    'dl_uphoto_exec_handler',
    'send_profile_photo_handler',
    'join_chat_input_handler',
    'join_chat_confirm_handler',
    'sys_ctrl_cb_handler',
    'sys_ctrl_1_handler',
    'sys_restart_handler',
    'sys_shutdown_handler',
    'check_limit_confirmation_handler',
    'check_limit_execute_handler',
    'laucreate_menu_handler',
    'laucreate_manual_handler',
    'laucreate_ui_handler',
    'laucreate_toggle_handler',
    'laucreate_adjust_handler',
    'laucreate_upload_photo_handler',
    'laucreate_confirm_task_handler',
    'laucreate_run_handler',
    'startup_custom_menu_handler',
    'startup_custom_input_handler',
    'toggle_startup_msg_handler',
    'phone_privacy_menu_handler',
    'set_phone_privacy_handler',
    'group_privacy_menu_handler',
    'set_group_privacy_handler',
    'refresh_session_info_cb_handler',
    'view_all_sessions_handler',
    'add_session_handler',
    'eval_session_start_handler',
    'eval_exec_confirm_handler',
    'exec_session_start_handler',
    'exec_term_handler',
    'gen_confirm_handler',
    'rpm_conf_handler',
    'rpm_exec_handler',
    'dl_content_input_handler',
    'dlstory_session_input_handler',
    'chat_stats_scan_handler',
]

# Counter for modifications
modified_count = 0

for handler_name in callback_handlers:
    # Pattern to find the handler function definition
    # Match: async def handler_name(c: Client, cb: CallbackQuery):
    #        """optional docstring"""
    #        await cb.answer() or other first line
    
    pattern = rf'(async def {handler_name}\([^)]+\):)\n(\s+"""[^"]*"""\n)?(\s+)(await cb\.answer\(\)|[^\n]+)'
    
    def replacement(match):
        global modified_count
        func_def = match.group(1)
        docstring = match.group(2) if match.group(2) else ''
        indent = match.group(3)
        first_line = match.group(4)
        
        # Check if authorization already exists
        if 'check_authorization' in first_line:
            return match.group(0)  # Already has auth check
        
        modified_count += 1
        # Add authorization check before the first line
        return f"{func_def}\n{docstring}{indent}if not await check_authorization(cb): return\n{indent}{first_line}"
    
    content = re.sub(pattern, replacement, content)

# Write back
with open(r'f:\2025\DESEMBER\altruix\AltruixX\Main\internals\settings.py', 'w', encoding='utf-8') as f:
    f.write(content)

print(f"Added authorization checks to {modified_count} handlers")
