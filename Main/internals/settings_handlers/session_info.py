# Main/internals/settings_handlers/session_info.py
import html
import os
import asyncio
import logging
import re
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton, 
    LinkPreviewOptions, InlineQuery, InlineQueryResultArticle, InputTextMessageContent
)
from Main.core.decorators import log_errors, iuser_check
from Main.core.client import Altruix
from pyrogram.enums import ParseMode, ChatType
from pyrogram.errors import FloodWait

# Logger
logger = logging.getLogger(__name__)

# State Dictionaries (Centralized)
from .states import (
    user_text_confirmation_state, user_profile_edit_state, user_edit_confirmation_state,
    user_confirmation_state, user_dlphoto_state, user_purge_state,
    user_recent_messages_state, user_mentions_state, user_privacy_state,
    user_eval_state, user_exec_state, user_creategroup_state
)

# Import all sub-handlers to register them with the bot
import Main.internals.settings_handlers.profile_handlers
import Main.internals.settings_handlers.media_handlers
import Main.internals.settings_handlers.logger_handlers
import Main.internals.settings_handlers.security_handlers
import Main.internals.settings_handlers.message_handlers
import Main.internals.settings_handlers.generic_confirm
import Main.internals.settings_handlers.stats_handlers
import Main.internals.settings_handlers.privacy_handlers
import Main.internals.settings_handlers.startup_handlers
import Main.internals.settings_handlers.creategroup_handlers
import Main.internals.settings_handlers.bulk_handlers
import Main.internals.settings_handlers.system_handlers
import Main.internals.settings_handlers.env_handlers
import Main.internals.settings_handlers.toggle_session_handlers
import Main.internals.settings_handlers.sessions_list
import Main.internals.settings_handlers.export_handlers

@Altruix.bot.on_callback_query(filters.regex(r"^global_purgeme_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def global_purgeme_cb_handler(c: Client, cb: CallbackQuery):
    idx, pg = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    from Main.internals.settings_handlers.global_purgeme import open_global_purgeme_ui
    await open_global_purgeme_ui(c, cb, idx, pg)

@Altruix.bot.on_callback_query(filters.regex(r"^dl_content_menu_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def dl_content_menu_handler(c: Client, cb: CallbackQuery):
    """Handler for DL Content Menu (placeholder or actual menu if needed)"""
    index, page = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    # ... logic ...
    # For now, just ensure any back button uses 'page' variable
    await cb.answer("Menu Placeholder", show_alert=True)
    # real implementation might be different, but key is:
    # InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}_2")

async def get_session_info_data(index: int, callback_page: int, button_page: int = 1):
    """
    Helper function to generate text and buttons for session info dashboard.
    Shared between callback handler and inline query handler.
    """
    if index >= len(Altruix.clients):
        return "❌ Sesi tidak ditemukan.", None

    client = Altruix.clients[index]
    me = getattr(client, 'myself', None)
    if not me:
        try:
            me = await client.get_me()
            client.myself = me
        except Exception:
            return "❌ Gagal mengambil informasi akun.", None

    # Menu text with account info and total button count
    try:
        chat_info = await client.get_chat(me.id)
        bio = chat_info.bio or "-"
    except Exception:
        bio = "-"

    # Calculate Stats
    ub_mod = len([x for x in Altruix.plugin_categories.values() if x == 'userbot'])
    bot_mod = len([x for x in Altruix.plugin_categories.values() if x == 'bot'])
    xtra_mod = len([x for x in Altruix.plugin_categories.values() if x == 'other'])
    total_mod = len(Altruix.plugin_categories)
    
    # Custom Bot Info
    custom_bot_username = "None"
    custom_bot_id = None
    if hasattr(Altruix, 'bot_manager'):
        custom_bot_username = Altruix.bot_manager.get_bot_username(me.id) or "None"
        if custom_bot_username != "None":
            # Find the bot ID from custom_bots dict
            for bot_id, bot_client in Altruix.bot_manager.custom_bots.items():
                if bot_client.me and bot_client.me.username == custom_bot_username:
                    custom_bot_id = bot_id
                    break
    
    # Advanced Stats: Count active loggers/features
    xtra_count = 0
    feat_keys = [
        f"PM_LOGGER_STATUS_{index}", f"MENTION_LOGGER_STATUS_{index}", 
        f"JOIN_LOGGER_STATUS_{index}", f"CMDL_LOGGER_{index}",
        f"GPURGEME_STATUS_{index}", f"AUTO_DELETE_CMD_STATUS_{index}"
    ]
    for k in feat_keys:
        if (await Altruix.config.get_env(k)) == "on":
            xtra_count += 1

    # Check session status
    is_disabled = Altruix.is_session_disabled(me.id)
    status_icon = "DISABLED" if is_disabled else "ACTIVE"
    status_emoji = "🔴" if is_disabled else "🟢"
    
    # Prefix Handling
    prefix_apply_type = await Altruix.config.get_env("PREFIX_APPLY_TYPE") or "global"
    u_key = "PREFIX_OWNER_USER" if prefix_apply_type == "global" else f"PREFIX_OWNER_USER_{me.id}"
    s_key = "PREFIX_SUDO_USERS" if prefix_apply_type == "global" else f"PREFIX_SUDO_USERS_{me.id}"
    
    u_prefix = await Altruix.config.get_env(u_key) or "."
    s_prefix = await Altruix.config.get_env(s_key) or ","

    # Sudo Status
    sudo_apply_type = await Altruix.config.get_env("SUDO_APPLY_TYPE") or "global"
    if sudo_apply_type == "global":
        sudo_enabled_raw = await Altruix.config.get_env("SUDO_ENABLED_GLOBAL")
        sudo_enabled = (sudo_enabled_raw != "false") if sudo_enabled_raw else True
    else:
        sudo_enabled_raw = await Altruix.config.get_env(f"SUDO_ENABLED_{me.id}")
        sudo_enabled = (sudo_enabled_raw != "false") if sudo_enabled_raw else True
    
    sudo_status_icon = "✅ ON" if sudo_enabled else "❌ OFF"

    # Total Active Bots
    total_active_bots = 1 # Main Bot Assistant
    if hasattr(Altruix, 'bot_manager'):
         total_active_bots += len(Altruix.bot_manager.custom_bots)

    # Logger Status Check (Optimized logic - Sync with Database/Config)
    pm_logger_status = "❌ OFF"
    try:
        # Resolve Apply Type for current session
        pml_apply_type = await Altruix.config.get_env(f"PML_LOGGER_APPLY_TYPE_{index}") or "global"
        
        # Check based on apply_type
        if pml_apply_type == "global":
            pml_current = await Altruix.config.get_env("PML_LOGGER_GLOBAL") or "off"
        else:
            pml_current = await Altruix.config.get_env(f"PML_LOGGER_{index}") or "off"
            
        if pml_current == "on":
            pm_logger_status = "✅ ON"
            
        # Fallback check for JSON-only sessions if DB key is missing but JSON says enabled
        # This covers cases where JSON was modified manually or by legacy code
        if pm_logger_status == "❌ OFF":
            from Main.utils.file_helpers import get_db_path as _get_db_path
            import json as _json
            _pm_settings_path = _get_db_path("pm_logger_user_settings.json")
            if os.path.exists(_pm_settings_path):
                with open(_pm_settings_path, "r", encoding="utf-8") as _f:
                    _pm_data = _json.load(_f)
                    _pm_sessions = _pm_data.get("settings", {}) or _pm_data.get("sessions", {})
                    _settings_data = _pm_sessions.get(str(me.id))
                    if isinstance(_settings_data, dict) and _settings_data.get("enabled"):
                        pm_logger_status = "✅ ON"
                    elif isinstance(_settings_data, bool) and _settings_data:
                        pm_logger_status = "✅ ON"
    except Exception: pass
    
    mention_logger_status = "❌ OFF"
    try:
        mnt_apply_type = await Altruix.config.get_env(f"MNT_LOGGER_APPLY_TYPE_{index}") or "global"
        
        if mnt_apply_type == "global":
            mnt_current = await Altruix.config.get_env("MNT_LOGGER_GLOBAL") or "off"
        else:
            mnt_current = await Altruix.config.get_env(f"MNT_LOGGER_{index}") or "off"
            
        if mnt_current == "on":
            mention_logger_status = "✅ ON"
            
        # Fallback to JSON
        if mention_logger_status == "❌ OFF":
            _mention_settings_path = _get_db_path("mentions_settings.json")
            if os.path.exists(_mention_settings_path):
                with open(_mention_settings_path, "r", encoding="utf-8") as _f:
                    _m_data = _json.load(_f)
                    _m_sessions = _m_data.get("settings", {})
                    _m_per_account = _m_sessions.get(str(me.id), {})
                    if isinstance(_m_per_account, dict) and _m_per_account.get("mention", True):
                         # If it's a dict and explicitly enabled/missing (default true)
                        mention_logger_status = "✅ ON"
    except Exception: pass

    # Auto Delete Command Status
    auto_delete_mode = await Altruix.config.get_env(f"AUTO_DELETE_CMD_TYPE_{index}") or "per_account"
    auto_delete_status = await Altruix.config.get_env(f"AUTO_DELETE_CMD_STATUS_{index}") or "off"
    auto_delete_delay = await Altruix.config.get_env(f"AUTO_DELETE_CMD_DELAY_{index}") or "2"
    auto_delete_status_icon = "✅ ON" if auto_delete_status == "on" else "❌ OFF"
    auto_delete_mode_display = auto_delete_mode.upper().replace('_', ' ')

    text = (
        f"<b>👤 Session Info</b>\n\n"
        f"<b>Name:</b> <b><a href='tg://user?id={me.id}'>{html.escape(me.first_name)} {html.escape(me.last_name or '')}</a></b> \n"
        f"<b>ID:</b> <spoiler>{me.id}</spoiler>\n"
        f"<b>Username:</b> <spoiler>@{me.username or 'None'}</spoiler>\n"
        f"<b>Premium:</b> {'✅ YES' if me.is_premium else '❌ NO'}\n"
        f"<b>Bio:</b> {html.escape(bio)}\n"
        f"<b>Status:</b> {status_emoji} {status_icon}\n"
        f"<b>Prefix:</b> Userbot ( <code>{u_prefix}</code> ) | Sudo ( <code>{s_prefix}</code> )\n"
        f"<b>👑 Sudo Status:</b> {sudo_status_icon}\n\n"
        f"<b>📋 Logger Status:</b>\n"
        f"• <b>PM Logger:</b> {pm_logger_status}\n"
        f"• <b>Mention Logger:</b> {mention_logger_status}\n\n"
        f"<b>📱 {Altruix.get_string('auto_delete_cmd')}:</b> {auto_delete_status_icon} \n • Mode: <code>{auto_delete_mode_display}</code> | • Delay: <code>{auto_delete_delay}s</code>\n\n"
        f"<b>🤖 Bot Assistant:</b> <spoiler>{f'<a href=\"tg://user?id={custom_bot_id}\">{custom_bot_username}</a>' if custom_bot_id else (f'{custom_bot_username}' if custom_bot_username != 'None' else 'None')}</spoiler> (Active Bots: {total_active_bots})\n"
        f"<b>⚙️ Xtra-Features:</b> {xtra_count} Aktif\n"
        f"<b>🔘 Total Modul:</b> {total_mod} (UB {ub_mod}, Bot {bot_mod}, Xtra {xtra_mod})\n\n"
        f"<b>📊 Total Buttons:</b> 56 | <b>Page:</b> {button_page}/5\n"
        f"<b>Manage this session:</b>"
    )

    def btn(idx, key, data):
        return InlineKeyboardButton(f"[{idx}] {Altruix.get_string(key)}", data)

    buttons = []
    if button_page == 1:
        buttons = [
            [btn(1, "refresh_info", f"session_info_{index}_{callback_page}_1"), btn(2, "unlink_session", f"unlink_session_{index}")],
            [btn(3, "change_name", f"change_name_menu_{index}_{callback_page}"), btn(4, "change_bio", f"gen_conf_change_bio_{index}_{callback_page}")],
            [btn(5, "change_username", f"gen_conf_change_username_{index}_{callback_page}"), btn(6, "change_profile_photo", f"gen_conf_change_profile_photo_{index}_{callback_page}")],
            [btn(7, "upload_photo", f"gen_conf_send_profile_photo_{index}_{callback_page}"), btn(8, "delete_all_photos", f"gen_conf_delete_all_profile_photos_{index}_{callback_page}")],
            [btn(9, "backup_profile", f"gen_conf_backup_profile_{index}_{callback_page}"), btn(10, "check_limit", f"check_limit_confirm_{index}_{callback_page}")],
            [btn(11, "view_sessions", f"gen_conf_view_all_sessions_{index}_{callback_page}"), btn(12, "join_log_group", f"join_log_group_{index}_{callback_page}")],
            [btn(13, "toggle_session_status", f"toggle_session_confirm_{index}_{callback_page}")],
            [InlineKeyboardButton(Altruix.get_string("next"), f"session_info_{index}_{callback_page}_2")]
        ]
    elif button_page == 2:
        buttons = [
            [btn(14, "download_story", f"gen_conf_dlstory_session_input_{index}_{callback_page}"), btn(15, "download_content", f"gen_conf_dl_content_input_{index}_{callback_page}")],
            [btn(16, "download_user_photo", f"gen_conf_dl_uphoto_start_{index}_{callback_page}"), btn(17, "purge_my_msg", f"purge_msg_start_{index}_{callback_page}")],
            [btn(18, "send_message", f"gen_conf_send_message_input_{index}_{callback_page}"), btn(19, "join_group", f"gen_conf_join_chat_input_{index}_{callback_page}")],
            [btn(20, "leave_group", f"gen_conf_leave_chat_input_{index}_{callback_page}"), btn(21, "track_profile", f"gen_conf_track_profile_{index}_{callback_page}")],
            [btn(22, "chat_stats", f"gen_conf_chat_stats_scan_{index}_{callback_page}"), btn(23, "creategroup_menu", f"creategroup_menu_{index}_{callback_page}")],
            [btn(24, "recent_messages", f"gen_conf_recent_messages_menu_{index}_{callback_page}"), btn(25, "view_mentions", f"gen_conf_view_mentions_menu_{index}_{callback_page}")],
            [InlineKeyboardButton(Altruix.get_string("prev"), f"session_info_{index}_{callback_page}_1"), InlineKeyboardButton(Altruix.get_string("next"), f"session_info_{index}_{callback_page}_3")]
        ]
    elif button_page == 3:
        buttons = [
            [btn(26, "pm_logger_control", f"pml_menu_{index}_{callback_page}"), btn(27, "mention_control", f"mnt_menu_{index}_{callback_page}")],
            [btn(28, "join_logger_control", f"joinl_menu_{index}_{callback_page}"), btn(29, "cmd_logger_control", f"cmdl_menu_{index}_{callback_page}")],
            [btn(30, "privacy_security", f"privacy_menu_{index}_{callback_page}"), btn(31, "startup_settings_title", f"startup_menu_{index}_{callback_page}")],
            [btn(32, "cmd_settings", f"cmd_settings_menu_{index}_{callback_page}"), btn(33, "sudo_settings", f"sudo_menu_{index}_{callback_page}")],
            [btn(34, "prefix_settings", f"prefix_menu_{index}_{callback_page}"), btn(35, "2fa_info", f"gen_conf_2fa_info_{index}_{callback_page}")],
            [btn(36, "prefix_info", f"prefix_info_{index}_{callback_page}"), btn(37, "feature_status", f"feature_status_{index}_{callback_page}")],
            [InlineKeyboardButton(Altruix.get_string("prev"), f"session_info_{index}_{callback_page}_2"), InlineKeyboardButton(Altruix.get_string("next"), f"session_info_{index}_{callback_page}_4")]
        ]
    elif button_page == 4:
        buttons = [
            [btn(38, "export_session", f"gen_conf_export_session_{index}_{callback_page}"), btn(39, "export_phone", f"gen_conf_export_phone_{index}_{callback_page}")],
            [btn(40, "export_all_sessions", f"gen_conf_export_all_sessions_{index}_{callback_page}"), btn(41, "export_all_phones", f"gen_conf_export_all_phones_{index}_{callback_page}")],
            [btn(42, "eval_python", f"gen_conf_eval_exec_{index}_{callback_page}"), btn(43, "exec_terminal", f"gen_conf_exec_term_{index}_{callback_page}")],
            [btn(44, "global_stats", f"gen_conf_global_stats_{index}_{callback_page}"), btn(45, "env_manager", f"env_manager_list_1")],
            [btn(46, "change_login_email", f"change_login_email_{index}_{callback_page}"), btn(47, "custom_bot", f"custom_bot_manager")],
            [btn(48, "btn_stats", f"sessions_stats"), btn(49, "refresh", f"session_info_{index}_{callback_page}_4")],
            [
                InlineKeyboardButton(f"[50] {Altruix.get_string('btn_gcast_user')}", callback_data=f"gcast_user_{index}_{callback_page}"),
                InlineKeyboardButton(f"[51] {Altruix.get_string('global_purgeme')}", callback_data=f"global_purgeme_{index}_{callback_page}")
            ],
            [InlineKeyboardButton(Altruix.get_string("prev"), f"session_info_{index}_{callback_page}_3"), InlineKeyboardButton(Altruix.get_string("next"), f"session_info_{index}_{callback_page}_5")]
        ]
    elif button_page == 5:
        buttons = [
            [InlineKeyboardButton(f"[52] {Altruix.get_string('bulk_join_menu')}", f"bulk_join_menu"), InlineKeyboardButton(f"[53] {Altruix.get_string('bulk_leave_menu')}", f"bulk_leave_menu")],
            [InlineKeyboardButton(f"[54] {Altruix.get_string('bulk_report_menu')}", f"bulk_report_menu"), InlineKeyboardButton(f"[55] {Altruix.get_string('sys_ctrl_restart')}", f"sys_ctrl_restart")],
            [InlineKeyboardButton(f"[56] {Altruix.get_string('sys_ctrl_shutdown')}", f"sys_ctrl_shutdown")],
            [InlineKeyboardButton(f"{Altruix.get_string('prev')} (4/5)", f"session_info_{index}_{callback_page}_4")]
        ]
    
    buttons.append([InlineKeyboardButton(Altruix.get_string("back"), callback_data=f"sessions_list_{callback_page}")])
    return text, InlineKeyboardMarkup(buttons)

@Altruix.bot.on_callback_query(filters.regex(r"session_info_(\d+)_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def sessions_info_cb_handler(c: Client, cb: CallbackQuery):
    """Callback-based session info dashboard."""
    index = int(cb.matches[0].group(1))
    callback_page = int(cb.matches[0].group(2))
    button_page = int(cb.matches[0].group(3)) if cb.matches[0].group(3) else 1
    
    await cb.answer()
    text, reply_markup = await get_session_info_data(index, callback_page, button_page)
    
    try:
        await cb.edit_message_text(
            text=f"<b>ℹ️ SESSION MANAGER</b>\n\n<blockquote expandable>{text}</blockquote>",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML,
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
    except Exception as e:
        logger.error(f"Failed to edit message in session_info callback: {e}")
        await cb.answer(f"❌ Error: {e}", show_alert=True)

@Altruix.bot.on_inline_query(filters.regex(r"^session_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def session_info_inline_handler(c: Client, iq: InlineQuery):
    """Inline-based session info Dashboard, used by .mysess command."""
    # AUTHORIZATION CHECK
    if not await Altruix.is_sudo(iq.from_user.id):
        return
    
    index = int(iq.matches[0].group(1))
    button_page = int(iq.matches[0].group(2)) if iq.matches[0].group(2) else 1
    
    # Generate data
    text, reply_markup = await get_session_info_data(index, 1, button_page)
    
    # Answer inline query
    results = [
        InlineQueryResultArticle(
            title=f"Session Info #{index}",
            description="Open full management dashboard with 56+ buttons",
            input_message_content=InputTextMessageContent(
                message_text=f"<b>ℹ️ SESSION MANAGER</b>\n\n<blockquote expandable>{text}</blockquote>",
                parse_mode=ParseMode.HTML,
                link_preview_options=LinkPreviewOptions(is_disabled=True)
            ),
            reply_markup=reply_markup,
            thumb_url="https://telegra.ph/file/0c6f5a3e1445790c9b0e2.jpg" # Optional thumb
        )
    ]
    await iq.answer(results=results, cache_time=0, is_personal=True)

# ============================================================================
# ⌨️ CENTRAL MESSAGE HANDLER FOR INPUTS
# ============================================================================

@Altruix.bot.on_message(filters.private & Altruix.is_sudo_filter & ~filters.command(["start", "settings", "help", "add"]))
@iuser_check
@log_errors
async def sessions_info_msg_handler(c: Client, m: Message):
    """Central handler for capturing text inputs like bio, username, purge count, join links, etc."""
    user_id = m.from_user.id
    text = m.text.strip() if m.text else ""

    if text.lower() == "/cancel":
        # Clear all states
        from .env_handlers import user_env_input_state
        for state_dict in [user_profile_edit_state, user_dlphoto_state, user_purge_state,
                           user_join_state, user_leave_state, user_send_msg_state, user_privacy_state,
                           user_bulk_join_state, user_bulk_leave_state, user_bulk_report_state, 
                           user_env_input_state, user_creategroup_state, user_edit_confirmation_state,
                           user_text_confirmation_state]:
            if user_id in state_dict: del state_dict[user_id]
        await m.reply("❌ Input dibatalkan.")
        return

    # 0. Global Confirmation (Text based)
    if user_id in user_edit_confirmation_state and text.lower() in ["ya", "tidak"]:
        if text.lower() == "tidak":
            del user_edit_confirmation_state[user_id]
            await m.reply("❌ Aksi dibatalkan.")
            return
        # If "ya", we simulate the inline button "yes"
        # Since we already have edit_confirm_handler, we can refactor it or handle it here.
        # But for profile edits, it usually goes to process_profile_edit_input or similar.
        # However, the userbot version of Altruix often uses manual "ya" for confirmations.
        pass

    # 0.5 Security Verification for Exports
    if user_id in user_text_confirmation_state and text.lower() == "ok":
        state = user_text_confirmation_state[user_id]
        action = state.get("action")
        if action == "export_all_sessions":
            from .export_handlers import execute_export_all_sessions
            await execute_export_all_sessions(c, m)
        elif action == "export_all_phones":
            from .export_handlers import execute_export_all_phones
            await execute_export_all_phones(c, m)
        
        del user_text_confirmation_state[user_id]
        if user_id in user_confirmation_state: del user_confirmation_state[user_id]
        return

    # 1. Profile Edits
    from .states import user_profile_edit_state
    if user_id in user_profile_edit_state:
        state = user_profile_edit_state[user_id]
        if m.photo and state.get('action') == 'change_profile_photo':
            # Handle photo upload directly
            index = state['session_index']
            page = state['page']
            await m.reply("📸 <b>Uploading profile photo...</b>", parse_mode=ParseMode.HTML)
            try:
                photo_path = await m.download()
                session_client = Altruix.clients[index]
                await session_client.set_profile_photo(photo=photo_path)
                await m.reply("✅ <b>Profile photo updated!</b>", 
                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", f"session_info_{index}_{page}")]]),
                            parse_mode=ParseMode.HTML)
                from .utils import send_log_notification
                await send_log_notification(c, 'change_profile_photo', index, m.from_user, True)
                if os.path.exists(photo_path): os.remove(photo_path)
                del user_profile_edit_state[user_id]
            except Exception as e:
                await m.reply(f"❌ <b>Error:</b> {str(e)}", parse_mode=ParseMode.HTML)
            return

        # Route media-related actions
        if state.get('action') in ['download_story', 'download_content']:
            from .media_handlers import process_media_input
            await process_media_input(c, m, state)
            return
            
        # Route misc profile actions (stats, tracking, etc.)
        if state.get('action') in ['download_user_photo', 'track_profile', 'chat_stats', 'recent_messages']:
            from .message_handlers import process_misc_profile_input
            await process_misc_profile_input(c, m, state)
            return

        # Route dev tools (Legacy check, can be removed if strictly using separate states)
        if state.get('action') in ['eval_python', 'exec_terminal']:
            from .dev_handlers import process_dev_input
            await process_dev_input(c, m, state)
            del user_profile_edit_state[user_id]
            return

        from .profile_handlers import process_profile_edit_input
        await process_profile_edit_input(c, m)
        return
        
    # 1.5 Dev Tools (Eval / Exec)
    if user_id in user_eval_state:
        from .dev_handlers import process_dev_input
        await process_dev_input(c, m, user_eval_state[user_id])
        del user_eval_state[user_id]
        return
        
    if user_id in user_exec_state:
        from .dev_handlers import process_dev_input
        await process_dev_input(c, m, user_exec_state[user_id])
        del user_exec_state[user_id]
        return

    # 2. Join / Leave / Send Message
    from .states import user_join_state, user_leave_state, user_send_msg_state
    if user_id in user_join_state:
        from .message_handlers import process_join_chat
        await process_join_chat(c, m, user_join_state[user_id])
        return
    if user_id in user_leave_state:
        from .message_handlers import process_leave_chat
        await process_leave_chat(c, m, user_leave_state[user_id])
        return
    if user_id in user_send_msg_state:
        from .message_handlers import process_send_message, process_send_message_content
        state = user_send_msg_state[user_id]
        if state['step'] == 'waiting_target':
            await process_send_message(c, m, state)
        elif state['step'] == 'waiting_content':
            await process_send_message_content(c, m, state)
        return

    # 3. Startup Msg & Prefix Edits
    from .states import user_privacy_state
    if user_id in user_privacy_state:
        state = user_privacy_state[user_id]
        step = state.get('step')
        if step == 'waiting_startup_custom_msg':
            from .startup_handlers import process_startup_msg_input
            await process_startup_msg_input(c, m, state)
            return
        elif step == 'waiting_prefix_input':
            from .privacy_handlers import process_prefix_input
            await process_prefix_input(c, m, state)
            return
        elif step == 'waiting_gcast_msg':
            from .bulk_handlers import process_gcast_input
            await process_gcast_input(c, m, state)
            return
        elif step == 'waiting_sudo_uid':
            from .privacy_handlers import process_sudo_input
            await process_sudo_input(c, m, state)
            return
        elif step == 'waiting_gpurgeme_limit':
            from .bulk_handlers import process_gpurgeme_custom
            await process_gpurgeme_custom(c, m, state)
            return
        elif step == 'waiting_help_custom_msg':
            # Moved from settings.py
            index = state['session_index']
            page = state['page']
            apply_type = await Altruix.config.get_env(f"HELP_INFO_TYPE_{index}") or "per_account"
            key = "HELP_INFO_CUSTOM_MSG_GLOBAL" if apply_type == "global" else f"HELP_INFO_CUSTOM_MSG_{index}"
            await Altruix.config.sync_env_to_db(key, text, upsert=True)
            setattr(Altruix.config, key, text)
            del user_privacy_state[user_id]
            from .utils import gt
            await m.reply(
                f"{gt('help_info_msg_updated')}\n\n<code>{html.escape(text)}</code>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(gt("back"), callback_data=f"help_info_custom_menu_{index}_{page}")]])
            )
            return

    # 4. Download / Tracker Input
    from .states import user_dlphoto_state
    if user_id in user_dlphoto_state:
        # Re-implement or call specific handler
        await m.reply(f"🔍 Memproses target: <code>{html.escape(text)}</code>...")
        del user_dlphoto_state[user_id]
        return

    # 5. Purge Chat Selection
    from .states import user_purge_state
    if user_id in user_purge_state:
        # Simple handler if only waiting for chat
        await m.reply(f"🧹 Purge chat: <code>{html.escape(text)}</code>")
        del user_purge_state[user_id]
        return

    # 6. Bulk Actions Input
    from .states import user_bulk_join_state, user_bulk_leave_state, user_bulk_report_state
    if user_id in user_bulk_join_state:
        from .bulk_handlers import process_bulk_join_input
        await process_bulk_join_input(c, m, user_bulk_join_state[user_id])
        return
    if user_id in user_bulk_leave_state:
        from .bulk_handlers import process_bulk_leave_input
        await process_bulk_leave_input(c, m, user_bulk_leave_state[user_id])
        return
    if user_id in user_bulk_report_state:
        from .bulk_handlers import process_bulk_report_input
        await process_bulk_report_input(c, m, user_bulk_report_state[user_id])
        return

    # 7. CreateGroup Inputs
    from .creategroup_handlers import process_creategroup_input
    if user_id in user_creategroup_state:
        await process_creategroup_input(c, m, text)
        return

    # 8. ENV Manager Inputs
    from .env_handlers import user_env_input_state, process_env_input, process_env_document
    if user_id in user_env_input_state:
        state = user_env_input_state[user_id]
        # Check if it's a document upload
        if m.document:
            await process_env_document(c, m, state)
        else:
            await process_env_input(c, m, state)
        return

    # 9. Custom Link Tracker
    if user_id in Altruix.user_track_state:
        state = Altruix.user_track_state[user_id]
        step = state.get("step", "")
        # Note: logic requires access to get_custom_link_data and save_custom_link_data
        # For now, let's just use it since it's in the same process/scope or import it if needed.
        from Main.internals.settings import get_custom_link_data, save_custom_link_data
        
        if step.startswith("edit_cl_"):
            target = step.replace("edit_cl_", "")
            data = get_custom_link_data()
            apply_type = data.get("apply_types", {}).get(str(user_id), "global")
            
            if target == "link" and not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", text):
                from .utils import gt
                await m.reply(gt("invalid_link"))
                return
            
            if apply_type == "global":
                data["global"][target] = text
            else:
                data.setdefault("sessions", {}).setdefault(str(user_id), {})[target] = text
                if target == "text" and "link" not in data["sessions"][str(user_id)]:
                    data["sessions"][str(user_id)]["link"] = data["global"]["link"]
                elif target == "link" and "text" not in data["sessions"][str(user_id)]:
                    data["sessions"][str(user_id)]["text"] = data["global"]["text"]
            
            save_custom_link_data(data)
            del Altruix.user_track_state[user_id]
            from .utils import gt
            await m.reply(gt("btn_updated").format(target.capitalize()))
            await m.reply(gt("custom_link_title"), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(gt("back"), callback_data="custom_link_settings")]]))
            return

@Altruix.bot.on_callback_query(filters.regex(r"^edit_confirm_(yes|no)_(\d+)"))
@iuser_check
@log_errors
async def edit_confirm_handler(c: Client, cb: CallbackQuery):
    """Handler global for Yes/No confirmations from Inline Buttons"""
    choice = cb.matches[0].group(1)
    user_id = int(cb.matches[0].group(2))
    
    if choice == "no":
        user_edit_confirmation_state.pop(user_id, None)
        await cb.answer("Dibatalkan.", show_alert=True)
        await Altruix.edit_cb(cb, "❌ Aksi dibatalkan oleh pengguna.")
        return

    if user_id not in user_edit_confirmation_state:
        await cb.answer("❌ Data tidak ditemukan.", show_alert=True)
        return
        
    state = user_edit_confirmation_state[user_id]
    action = state['action']
    index = state['session_index']
    page = state.get('page', 1)
    
    await cb.answer("Memproses...", show_alert=False)
    
    if action == 'delete_all_profile_photos':
        from .profile_handlers import delete_all_profile_photos_process
        await delete_all_profile_photos_process(c, cb.message, index, page, state.get('delay', 2))
        if user_id in user_edit_confirmation_state: del user_edit_confirmation_state[user_id]
    
    # Handle other confirmation actions here if needed
    
