PLUGIN_VERSION = "0.0.325"

"""
Purgeme Bot Plugin
Handles the interactive UI for the Userbot Purgeme command.
"""

import re
import time
import asyncio
import traceback
from pyrogram import Client, filters, enums
from pyrogram.errors import MessageNotModified, FloodWait
from pyrogram.types import (
    InlineQuery, InlineQueryResultArticle, InputTextMessageContent,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)
from Main.utils.file_helpers import get_user_button_style
from Main.core.decorators import log_errors, iuser_check
from Main.internals.settings_handlers.purgeme_handlers import load_user_purgeme_config, save_user_purgeme_config
from Main import Altruix


# Ensure shared state exists (redundant if loaded second, but safe)
if not hasattr(Altruix, "PURGEME_STATE"):
    Altruix.PURGEME_STATE = {}

# Helper to get formatted status text (Localization aware)
def get_purgeme_text(state):
    status = state["status"]
    count = state["count"]
    processed = state.get("processed", 0)
    scanned = state.get("scanned", 0) # Track scanned messages
    delay = state["delay"]
    batch_size = state.get("batch_size", 60)
    batch_delay = state.get("batch_delay", 120)  # stored in seconds
    offset = state.get("offset", 0)
    types = state["types"]
    start_time = state.get("start_time", 0)
    mode = state.get("mode", "latest")
    title = Altruix.get_string("purgeme_title") or "<b>Userbot Purgeme</b>"
    
    def loc(key): return Altruix.get_string(key)
    
    if status == "config":
        menu_title = loc("purgeme_menu_title") or "<b>Purgeme Configuration</b>"
        chat_name = state.get("chat_name", "Unknown")
        chat_id = state.get("chat_id", "Unknown")
        chat_link = state.get("chat_link")
        account_name = state.get("account_name", "Unknown")
        user_id = state.get("user_id")
        total_msgs = state.get("total_account_messages", 0)
        
        display_name = f"<a href='{chat_link}'>{chat_name}</a>" if chat_link else f"<b>{chat_name}</b>"
        acc_link = f"<a href='tg://user?id={user_id}'>{account_name}</a>" if user_id else f"<b>{account_name}</b>"
        acc_msgs_lbl = loc("purgeme_account_msgs") or "Acc Msgs"
        
        from_id = state.get("from_id", "me")
        sender_list = state.get("sender_list", [])
        sender_name = "Me"
        for s in sender_list:
            if s["id"] == from_id:
                sender_name = s["name"]
                break

        send_as_ok = state.get("send_as_locally_available", False)
        sa_status = "✅ Supported" if send_as_ok else "⚠️ Limited (Private/Restricted)"

        return (
            f"<blockquote expandable>{title}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Acc:</b> {acc_link}\n"
            f"• <b>From:</b> <code>{sender_name}</code>\n"
            f"• <b>Send As:</b> <code>{sa_status}</code>\n"
            f"• <b>Chat Name:</b> {display_name}\n"
            f"• <b>Chat ID:</b> <code>{chat_id}</code>\n"
            f"• <b>{acc_msgs_lbl}:</b> <code>{total_msgs}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{menu_title}\n"
            f"<i>Please select options:</i></blockquote>"
        )

    chat_name = state.get("chat_name", "Unknown")
    account_name = state.get("account_name", "Unknown")
    total_msgs = state.get("total_account_messages", 0)

    # Mapping for special types to YML keys
    TYPE_MAP = {
        "video_note": "VNOTE",
        "animation": "GIF",
        "document": "DOC",
        "location": "LOC",
        "contact": "CONT",
        "venue": "VEN"
    }

    # Common Header for active states
    if not types or "all" in types:
        type_display = loc("GP_BTN_ALL") or "ALL"
    elif len(types) > 1:
        type_display = (loc("purgeme_multiple") or "Multiple ({})").format(len(types))
    else:
        raw_type = types[0].lower()
        suffix = TYPE_MAP.get(raw_type, raw_type.upper())
        type_display = loc(f"GP_BTN_{suffix}") or suffix

    chat_link = state.get("chat_link")
    user_id = state.get("user_id")
    display_name = f"<a href='{chat_link}'>{chat_name}</a>" if chat_link else f"<b>{chat_name}</b>"
    acc_link = f"<a href='tg://user?id={user_id}'>{account_name}</a>" if user_id else f"<b>{account_name}</b>"
    
    from_id = state.get("from_id", "me")
    sender_list = state.get("sender_list", [])
    sender_name = "Me"
    for s in sender_list:
        if s["id"] == from_id:
            sender_name = s["name"]
            break

    header_content = (
        f"<b>Account:</b> {acc_link} (<code>{total_msgs}</code> msgs)\n"
        f"<b>From:</b> <code>{sender_name}</code> | <b>Chat:</b> {display_name}\n"
        f"<b>Mode:</b> <code>{mode.capitalize()}</code> | <b>Type:</b> <code>{type_display}</code>\n"
        f"<b>Target:</b> <code>{count}</code> messages | <b>Offset:</b> <code>{offset}</code>\n"
        f"<b>Batch:</b> <code>{batch_size}</code> | <b>DelayBc:</b> <code>{int(batch_delay/60)}m</code>\n"
        f"<b>Forward:</b> <code>{state.get('forward_log', 'off').replace('_', ' ').title()}</code> | <b>FwdDly:</b> <code>{state.get('fwd_delay', 0.5)}s</code>"
    )

    if status == "collecting":
        status_line = (loc("purgeme_collecting_detailed") or "<b>Collecting...</b>\nFound: <code>{processed}/{count}</code>\nScanned: <code>{scanned}</code>").format(
            processed=processed, count=count, scanned=scanned
        )
        return f"<blockquote expandable>{title}\n━━━━━━━━━━━━━━━━━━━━\n{header_content}\n━━━━━━━━━━━━━━━━━━━━\n{status_line}</blockquote>"

    elif status == "running":
        status_line = f"<b>Deleting...</b>\nDeleted: <code>{processed}/{count}</code>"
        if delay > 0: status_line += f"\nDelay: <code>{delay}s</code>"
        return f"<blockquote expandable>{title}\n━━━━━━━━━━━━━━━━━━━━\n{header_content}\n━━━━━━━━━━━━━━━━━━━━\n{status_line}</blockquote>"

    elif status == "paused":
        status_line = (loc("purgeme_paused_detailed") or "<b>PAUSED</b>\nDeleted: <code>{processed}/{count}</code>").format(
            processed=processed, count=count
        )
        return f"<blockquote expandable>{title}\n━━━━━━━━━━━━━━━━━━━━\n{header_content}\n━━━━━━━━━━━━━━━━━━━━\n{status_line}</blockquote>"

    elif status == "waiting":
        batch_delay = state.get("batch_delay", 0)
        btn_lbl = loc("purgeme_waiting_detailed") or "<b>WAITING (Batch Cooldown)</b>"
        return f"<blockquote expandable>{title}\n━━━━━━━━━━━━━━━━━━━━\n{header_content}\n━━━━━━━━━━━━━━━━━━━━\n{btn_lbl}\nNext batch in: <code>{batch_delay}s</code></blockquote>"

    elif status == "finished":
        processed = state.get("processed", 0)
        start_time = state.get("start_time", 0)
        duration = round(time.time() - start_time, 2) if start_time > 0 else 0
        failed = state.get("failed", 0)
        
        chat_link = state.get("chat_link")
        user_id = state.get("user_id")
        chat_display = f"<a href='{chat_link}'>{chat_name}</a>" if chat_link else f"<b>{chat_name}</b>"
        acc_link = f"<a href='tg://user?id={user_id}'>{account_name}</a>" if user_id else f"<b>{account_name}</b>"
        
        fin_text = (
            f"<b>Finished!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Deleted:</b> <code>{processed}</code> messages\n"
            f"• <b>Forwarded:</b> <code>{state.get('forwarded', 0)}</code> messages\n"
            f"• <b>Failed/Skip:</b> <code>{failed}</code> messages\n"
            f"• <b>Time:</b> <code>{duration}s</code>\n"
            f"• <b>Chat:</b> {chat_display}\n"
            f"• <b>Account:</b> {acc_link}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Mode:</b> <code>{mode.capitalize()}</code> | <b>Type:</b> <code>{type_display}</code>\n"
            f"• <b>Target:</b> <code>{count}</code> | <b>Offset:</b> <code>{offset}</code>\n"
            f"• <b>Batch:</b> <code>{batch_size}</code>\n"
            f"• <b>Delay/Msg:</b> <code>{delay}s</code>\n"
            f"• <b>Delay/Batch:</b> <code>{int(batch_delay/60)}m</code>\n"
            f"• <b>Delay/Forward:</b> <code>{state.get('fwd_delay', 0.5)}s</code>\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
        return f"<blockquote expandable>{title}\n\n{fin_text}</blockquote>"

    elif status == "info":
        info_text = loc("purgeme_info_text") or "Info Text Not Found"
        return f"<blockquote expandable>{title}\n\n{info_text}</blockquote>"
        
    elif status == "confirm":
        confirm_text = (
            f"<blockquote expandable>{title}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{header_content}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Konfirmasi Purgeme</b>\n"
            f"Apakah Anda yakin ingin menghapus <code>{count}</code> pesan Anda di <b>{chat_name}</b>?\n\n"
            f"<i>Tekan [Yes, Delete!] untuk melanjutkan atau [No, Cancel] untuk membatalkan.</i></blockquote>"
        )
        return confirm_text

    elif status == "cancelled":
        lbl = loc("purgeme_cancelled_short") or "<b>Cancelled</b>"
        return f"<blockquote expandable>{title}\n━━━━━━━━━━━━━━━━━━━━\n{lbl}</blockquote>"
        
    return f"<blockquote expandable>{title}</blockquote>"

async def get_purgeme_keyboard(chat_id, user_id, unique_id):
    # Ensure user_id is an integer for correct database lookup in get_user_button_style
    user_id = int(user_id)
    btn_style = get_user_button_style(user_id)
    
    state = Altruix.PURGEME_STATE.get(unique_id)
    if not state:
        return InlineKeyboardMarkup([[InlineKeyboardButton("Session Ended", callback_data="purgeme_close", style=btn_style)]])

    status = state["status"]
    count = state["count"]
    delay = state["delay"]
    batch_size = state.get("batch_size", 60)
    batch_delay = state.get("batch_delay", 120)
    offset = state.get("offset", 0)
    types = state["types"]
    min_id = state.get("min_id", 0)
    max_id = state.get("max_id", 0)
    keep_recent = state.get("keep_recent", 0)

    buttons = []
    
    def loc(key, default):
        s = Altruix.get_string(key)
        return s if s else default

    if status == "config":
        sub_menu = state.get("sub_menu")
        
        # ─── SUB-MENUS ───
        if sub_menu == "count":
            # Count Sub-Menu
            count_lbl = loc("purgeme_count", "Count: {}").format(count)
            buttons.append([InlineKeyboardButton(f"━━ {count_lbl} ━━", callback_data="noop", style=btn_style)])
            adj_steps = [1, 5, 10, 50, 100, 500]
            for s in adj_steps:
                buttons.append([
                    InlineKeyboardButton(f"-{s}", callback_data=f"pg_cnt_sub_{s}_{unique_id}", style=btn_style),
                    InlineKeyboardButton(f"+{s}", callback_data=f"pg_cnt_add_{s}_{unique_id}", style=btn_style)
                ])
            buttons.append([InlineKeyboardButton("Back", callback_data=f"pg_back_{unique_id}", style=btn_style)])
        
        elif sub_menu == "batch":
            # Batch Sub-Menu
            batch_lbl = f"Batch: {batch_size}"
            buttons.append([InlineKeyboardButton(f"━━ {batch_lbl} ━━", callback_data="noop", style=btn_style)])
            adj_steps = [5, 10, 30, 50, 100]
            for s in adj_steps:
                buttons.append([
                    InlineKeyboardButton(f"-{s}", callback_data=f"pg_btc_sub_{s}_{unique_id}", style=btn_style),
                    InlineKeyboardButton(f"+{s}", callback_data=f"pg_btc_add_{s}_{unique_id}", style=btn_style)
                ])
            buttons.append([InlineKeyboardButton("Back", callback_data=f"pg_back_{unique_id}", style=btn_style)])
        
        elif sub_menu == "keeprecent":
            # Keep Recent Sub-Menu
            kr_lbl = f"Keep Recent: {keep_recent} msg"
            buttons.append([InlineKeyboardButton(f"━━ {kr_lbl} ━━", callback_data="noop", style=btn_style)])
            adj_steps = [1, 5, 10, 50, 100]
            for s in adj_steps:
                buttons.append([
                    InlineKeyboardButton(f"-{s}", callback_data=f"pg_kr_sub_{s}_{unique_id}", style=btn_style),
                    InlineKeyboardButton(f"+{s}", callback_data=f"pg_kr_add_{s}_{unique_id}", style=btn_style)
                ])
            buttons.append([InlineKeyboardButton("Back", callback_data=f"pg_back_{unique_id}", style=btn_style)])

        elif sub_menu == "delay":
            # Delay/Msg Sub-Menu
            delay_lbl = loc("purgeme_delay", "Delay/Msg: {}s").format(delay)
            buttons.append([InlineKeyboardButton(f"━━ {delay_lbl} ━━", callback_data="noop", style=btn_style)])
            adj_steps = [0.25, 0.5, 1.0, 2.0, 5.0]
            for s in adj_steps:
                s_str = f"{s}" if s % 1 != 0 else f"{int(s)}"
                buttons.append([
                    InlineKeyboardButton(f"-{s_str}s", callback_data=f"pg_dly_sub_{s_str}_{unique_id}", style=btn_style),
                    InlineKeyboardButton(f"+{s_str}s", callback_data=f"pg_dly_add_{s_str}_{unique_id}", style=btn_style)
                ])
            buttons.append([
                InlineKeyboardButton("Reset (0s)", callback_data=f"pg_dly_reset_{unique_id}", style=btn_style),
                InlineKeyboardButton("Back", callback_data=f"pg_back_{unique_id}", style=btn_style)
            ])
        
        elif sub_menu == "bdelay":
            # Delay/Batch Sub-Menu
            bd_min = int(batch_delay / 60)
            bd_lbl = f"Delay/Batch: {bd_min}m"
            buttons.append([InlineKeyboardButton(f"━━ {bd_lbl} ━━", callback_data="noop", style=btn_style)])
            adj_steps = [1, 2, 5, 10, 30]
            for s in adj_steps:
                buttons.append([
                    InlineKeyboardButton(f"-{s}m", callback_data=f"pg_dbc_sub_{s}m_{unique_id}", style=btn_style),
                    InlineKeyboardButton(f"+{s}m", callback_data=f"pg_dbc_add_{s}m_{unique_id}", style=btn_style)
                ])
            buttons.append([
                InlineKeyboardButton("Reset (0m)", callback_data=f"pg_dbc_sub_999m_{unique_id}", style=btn_style),
                InlineKeyboardButton("Back", callback_data=f"pg_back_{unique_id}", style=btn_style)
            ])
        
        elif sub_menu == "mode":
            # Mode & Notify Sub-Menu
            curr_mode = state.get("mode", "latest")
            buttons.append([InlineKeyboardButton("━━ Mode & Notify ━━", callback_data="noop", style=btn_style)])
            latest_btn = f"{'[x]' if curr_mode == 'latest' else '[ ]'} {loc('purgeme_mode_latest', 'Newest')}"
            oldest_btn = f"{'[x]' if curr_mode == 'oldest' else '[ ]'} {loc('purgeme_mode_oldest', 'Oldest')}"
            buttons.append([
                InlineKeyboardButton(latest_btn, callback_data=f"pg_mode_latest_{unique_id}", style=btn_style),
                InlineKeyboardButton(oldest_btn, callback_data=f"pg_mode_oldest_{unique_id}", style=btn_style),
            ])
            notify_active = state.get("notify", True)
            notif_lbl = Altruix.get_string("GP_BTN_NOTIF_ON" if notify_active else "GP_BTN_NOTIF_OFF") or (f"Notif: ON" if notify_active else "Notif: OFF")
            buttons.append([InlineKeyboardButton(notif_lbl, callback_data=f"pg_notify_{unique_id}", style=btn_style)])
            buttons.append([InlineKeyboardButton("Back", callback_data=f"pg_back_{unique_id}", style=btn_style)])
        
        elif sub_menu == "offset":
            # Offset Sub-Menu
            off_lbl = f"Offset: {offset}"
            buttons.append([InlineKeyboardButton(f"━━ {off_lbl} ━━", callback_data="noop", style=btn_style)])
            adj_steps = [5, 10, 50, 100, 500]
            for s in adj_steps:
                buttons.append([
                    InlineKeyboardButton(f"-{s}", callback_data=f"pg_off_sub_{s}_{unique_id}", style=btn_style),
                    InlineKeyboardButton(f"+{s}", callback_data=f"pg_off_add_{s}_{unique_id}", style=btn_style)
                ])
            buttons.append([
                InlineKeyboardButton("Reset", callback_data=f"pg_off_reset_{unique_id}", style=btn_style),
                InlineKeyboardButton("Back", callback_data=f"pg_back_{unique_id}", style=btn_style)
            ])
        
        elif sub_menu == "bounds":
            # ID Range Sub-Menu
            buttons.append([InlineKeyboardButton(f"━━ Min ID: {min_id} ━━", callback_data="noop", style=btn_style)])
            buttons.append([
                InlineKeyboardButton("-100", callback_data=f"pg_bnd_min_sub_100_{unique_id}", style=btn_style),
                InlineKeyboardButton("-10", callback_data=f"pg_bnd_min_sub_10_{unique_id}", style=btn_style),
                InlineKeyboardButton("+10", callback_data=f"pg_bnd_min_add_10_{unique_id}", style=btn_style),
                InlineKeyboardButton("+100", callback_data=f"pg_bnd_min_add_100_{unique_id}", style=btn_style),
            ])
            buttons.append([
                InlineKeyboardButton("-1k", callback_data=f"pg_bnd_min_sub_1000_{unique_id}", style=btn_style),
                InlineKeyboardButton("+1k", callback_data=f"pg_bnd_min_add_1000_{unique_id}", style=btn_style),
                InlineKeyboardButton("-10k", callback_data=f"pg_bnd_min_sub_10000_{unique_id}", style=btn_style),
                InlineKeyboardButton("+10k", callback_data=f"pg_bnd_min_add_10000_{unique_id}", style=btn_style),
            ])
            
            buttons.append([InlineKeyboardButton(f"━━ Max ID: {max_id} ━━", callback_data="noop", style=btn_style)])
            buttons.append([
                 InlineKeyboardButton("-100", callback_data=f"pg_bnd_max_sub_100_{unique_id}", style=btn_style),
                 InlineKeyboardButton("-10", callback_data=f"pg_bnd_max_sub_10_{unique_id}", style=btn_style),
                 InlineKeyboardButton("+10", callback_data=f"pg_bnd_max_add_10_{unique_id}", style=btn_style),
                 InlineKeyboardButton("+100", callback_data=f"pg_bnd_max_add_100_{unique_id}", style=btn_style),
            ])
            buttons.append([
                InlineKeyboardButton("-1k", callback_data=f"pg_bnd_max_sub_1000_{unique_id}", style=btn_style),
                InlineKeyboardButton("+1k", callback_data=f"pg_bnd_max_add_1000_{unique_id}", style=btn_style),
                InlineKeyboardButton("-10k", callback_data=f"pg_bnd_max_sub_10000_{unique_id}", style=btn_style),
                InlineKeyboardButton("+10k", callback_data=f"pg_bnd_max_add_10000_{unique_id}", style=btn_style),
            ])
            buttons.append([
                InlineKeyboardButton("Reset Min", callback_data=f"pg_bnd_min_reset_{unique_id}", style=btn_style),
                InlineKeyboardButton("Reset Max", callback_data=f"pg_bnd_max_reset_{unique_id}", style=btn_style),
            ])
            buttons.append([InlineKeyboardButton("Back", callback_data=f"pg_back_{unique_id}", style=btn_style)])

        elif sub_menu == "dates":
            # Date Range Sub-Menu
            min_days = state.get("min_days", 0)
            max_days = state.get("max_days", 0)
            
            def format_days(d): return f"{d}d ago" if d > 0 else "None"
                
            buttons.append([InlineKeyboardButton(f"━━ Min Date: {format_days(min_days)} ━━", callback_data="noop", style=btn_style)])
            buttons.append([
                InlineKeyboardButton("-14D", callback_data=f"pg_dat_min_sub_14_{unique_id}", style=btn_style),
                InlineKeyboardButton("-1D", callback_data=f"pg_dat_min_sub_1_{unique_id}", style=btn_style),
                InlineKeyboardButton("+1D", callback_data=f"pg_dat_min_add_1_{unique_id}", style=btn_style),
                InlineKeyboardButton("+14D", callback_data=f"pg_dat_min_add_14_{unique_id}", style=btn_style),
            ])
            buttons.append([
                InlineKeyboardButton("-60D", callback_data=f"pg_dat_min_sub_60_{unique_id}", style=btn_style),
                InlineKeyboardButton("-30D", callback_data=f"pg_dat_min_sub_30_{unique_id}", style=btn_style),
                InlineKeyboardButton("+30D", callback_data=f"pg_dat_min_add_30_{unique_id}", style=btn_style),
                InlineKeyboardButton("+60D", callback_data=f"pg_dat_min_add_60_{unique_id}", style=btn_style),
            ])
            
            buttons.append([InlineKeyboardButton(f"━━ Max Date: {format_days(max_days)} ━━", callback_data="noop", style=btn_style)])
            buttons.append([
                 InlineKeyboardButton("-14D", callback_data=f"pg_dat_max_sub_14_{unique_id}", style=btn_style),
                 InlineKeyboardButton("-1D", callback_data=f"pg_dat_max_sub_1_{unique_id}", style=btn_style),
                 InlineKeyboardButton("+1D", callback_data=f"pg_dat_max_add_1_{unique_id}", style=btn_style),
                 InlineKeyboardButton("+14D", callback_data=f"pg_dat_max_add_14_{unique_id}", style=btn_style),
            ])
            buttons.append([
                InlineKeyboardButton("-60D", callback_data=f"pg_dat_max_sub_60_{unique_id}", style=btn_style),
                InlineKeyboardButton("-30D", callback_data=f"pg_dat_max_sub_30_{unique_id}", style=btn_style),
                InlineKeyboardButton("+30D", callback_data=f"pg_dat_max_add_30_{unique_id}", style=btn_style),
                InlineKeyboardButton("+60D", callback_data=f"pg_dat_max_add_60_{unique_id}", style=btn_style),
            ])
            buttons.append([
                InlineKeyboardButton("Reset Min", callback_data=f"pg_dat_min_reset_{unique_id}", style=btn_style),
                InlineKeyboardButton("Reset Max", callback_data=f"pg_dat_max_reset_{unique_id}", style=btn_style),
            ])
            buttons.append([InlineKeyboardButton("Back", callback_data=f"pg_back_{unique_id}", style=btn_style)])

        elif sub_menu == "maxscan":
            max_scan = state.get("max_scan", 500)
            buttons.append([InlineKeyboardButton(f"━━ Max Scan: {max_scan} ━━", callback_data="noop", style=btn_style)])
            adj_steps = [50, 100, 500, 1000, 5000]
            for s in adj_steps:
                buttons.append([
                    InlineKeyboardButton(f"-{s}", callback_data=f"pg_scn_sub_{s}_{unique_id}", style=btn_style),
                    InlineKeyboardButton(f"+{s}", callback_data=f"pg_scn_add_{s}_{unique_id}", style=btn_style)
                ])
            buttons.append([
                InlineKeyboardButton("Reset", callback_data=f"pg_scn_reset_{unique_id}", style=btn_style),
                InlineKeyboardButton("Back", callback_data=f"pg_back_{unique_id}", style=btn_style)
            ])

        elif sub_menu == "forwardlog":
            # Forward Log Sub-Menu
            curr_fwd = state.get("forward_log", "off")
            buttons.append([InlineKeyboardButton("━━ Forward Log To ━━", callback_data="noop", style=btn_style)])
            
            fwd_options = [
                ("off", "Off"),
                ("group_log", "Group Log"),
                ("pm_bot", "PM Bot"),
                ("saved", "Saved Messages")
            ]
            
            for f_val, f_lbl in fwd_options:
                active = "[x]" if curr_fwd == f_val else "[ ]"
                buttons.append([InlineKeyboardButton(f"{active} {f_lbl}", callback_data=f"pg_set_fwd_{f_val}_{unique_id}", style=btn_style)])
            
            buttons.append([InlineKeyboardButton("Back", callback_data=f"pg_back_{unique_id}", style=btn_style)])

        elif sub_menu == "fwddelay":
            # Forward Delay Sub-Menu
            fwd_delay = state.get("fwd_delay", 0.5)
            buttons.append([InlineKeyboardButton(f"━━ Fwd Delay: {fwd_delay}s ━━", callback_data="noop", style=btn_style)])
            adj_steps = [0.1, 0.25, 0.5, 1.0, 2.0, 5.0]
            for s in adj_steps:
                s_str = f"{s}" if s % 1 != 0 else f"{int(s)}"
                buttons.append([
                    InlineKeyboardButton(f"-{s_str}s", callback_data=f"pg_fdl_sub_{s_str}_{unique_id}", style=btn_style),
                    InlineKeyboardButton(f"+{s_str}s", callback_data=f"pg_fdl_add_{s_str}_{unique_id}", style=btn_style)
                ])
            buttons.append([
                InlineKeyboardButton("Reset (0.5s)", callback_data=f"pg_fdl_reset_{unique_id}", style=btn_style),
                InlineKeyboardButton("Back", callback_data=f"pg_back_{unique_id}", style=btn_style)
            ])


        elif sub_menu == "filter":
            # Message Type Filter Sub-Menu
            # Mapping for special types
            TYPE_MAP = {
                "video_note": "VNOTE", "animation": "GIF", "document": "DOC",
                "location": "LOC", "contact": "CONT", "venue": "VEN"
            }
            if not types or "all" in types:
                filter_display = loc("GP_BTN_ALL", "All")
            elif len(types) > 1:
                filter_display = f"Multiple ({len(types)})"
            else:
                raw = types[0].lower()
                suffix = TYPE_MAP.get(raw, raw.upper())
                filter_display = loc(f"GP_BTN_{suffix}", suffix)
            
            buttons.append([InlineKeyboardButton(f"━━ Filter: {filter_display} ━━", callback_data="noop", style=btn_style)])
            
            # Row 1
            all_active = "[x]" if "all" in types else "[ ]"
            photo_active = "[x]" if ("photo" in types or "image" in types) else "[ ]"
            vid_active = "[x]" if "video" in types else "[ ]"
            buttons.append([
                InlineKeyboardButton(f"{all_active} {loc('GP_BTN_ALL', 'All')}", callback_data=f"pg_typ_all_{unique_id}", style=btn_style),
                InlineKeyboardButton(f"{photo_active} {loc('GP_BTN_IMG', 'Photo')}", callback_data=f"pg_typ_photo_{unique_id}", style=btn_style),
                InlineKeyboardButton(f"{vid_active} {loc('GP_BTN_VID', 'Video')}", callback_data=f"pg_typ_video_{unique_id}", style=btn_style),
            ])
            # Row 2
            txt_active = "[x]" if "text" in types else "[ ]"
            aud_active = "[x]" if "audio" in types else "[ ]"
            stk_active = "[x]" if "sticker" in types else "[ ]"
            buttons.append([
                InlineKeyboardButton(f"{txt_active} {loc('GP_BTN_TXT', 'Text')}", callback_data=f"pg_typ_text_{unique_id}", style=btn_style),
                InlineKeyboardButton(f"{aud_active} {loc('GP_BTN_AUD', 'Audio')}", callback_data=f"pg_typ_audio_{unique_id}", style=btn_style),
                InlineKeyboardButton(f"{stk_active} {loc('GP_BTN_STK', 'Sticker')}", callback_data=f"pg_typ_sticker_{unique_id}", style=btn_style),
            ])
            # Row 3
            anim_active = "[x]" if ("animation" in types or "gif" in types) else "[ ]"
            doc_active = "[x]" if ("document" in types or "file" in types) else "[ ]"
            vnote_active = "[x]" if ("video_note" in types or "vnote" in types) else "[ ]"
            buttons.append([
                InlineKeyboardButton(f"{anim_active} {loc('GP_BTN_GIF', 'Anim')}", callback_data=f"pg_typ_animation_{unique_id}", style=btn_style),
                InlineKeyboardButton(f"{doc_active} {loc('GP_BTN_DOC', 'Doc')}", callback_data=f"pg_typ_document_{unique_id}", style=btn_style),
                InlineKeyboardButton(f"{vnote_active} {loc('GP_BTN_VNOTE', 'VNote')}", callback_data=f"pg_typ_video_note_{unique_id}", style=btn_style),
            ])
            # Row 4
            voice_active = "[x]" if "voice" in types else "[ ]"
            contact_active = "[x]" if "contact" in types else "[ ]"
            loc_active = "[x]" if "location" in types else "[ ]"
            buttons.append([
                InlineKeyboardButton(f"{voice_active} {loc('GP_BTN_VN', 'Voice')}", callback_data=f"pg_typ_voice_{unique_id}", style=btn_style),
                InlineKeyboardButton(f"{contact_active} {loc('GP_BTN_CONT', 'Contact')}", callback_data=f"pg_typ_contact_{unique_id}", style=btn_style),
                InlineKeyboardButton(f"{loc_active} {loc('GP_BTN_LOC', 'Loc')}", callback_data=f"pg_typ_location_{unique_id}", style=btn_style),
            ])
            # Row 5
            venue_active = "[x]" if "venue" in types else "[ ]"
            game_active = "[x]" if "game" in types else "[ ]"
            poll_active = "[x]" if "poll" in types else "[ ]"
            buttons.append([
                InlineKeyboardButton(f"{venue_active} {loc('GP_BTN_VEN', 'Venue')}", callback_data=f"pg_typ_venue_{unique_id}", style=btn_style),
                InlineKeyboardButton(f"{game_active} {loc('GP_BTN_GAME', 'Game')}", callback_data=f"pg_typ_game_{unique_id}", style=btn_style),
                InlineKeyboardButton(f"{poll_active} {loc('GP_BTN_POLL', 'Poll')}", callback_data=f"pg_typ_poll_{unique_id}", style=btn_style),
            ])
            # Row 6
            dice_active = "[x]" if "dice" in types else "[ ]"
            web_active = "[x]" if "web_page" in types else "[ ]"
            buttons.append([
                InlineKeyboardButton(f"{dice_active} {loc('GP_BTN_DICE', 'Dice')}", callback_data=f"pg_typ_dice_{unique_id}", style=btn_style),
                InlineKeyboardButton(f"{web_active} Link", callback_data=f"pg_typ_web_page_{unique_id}", style=btn_style),
            ])
            # Row 7
            story_active = "[x]" if "story" in types else "[ ]"
            svc_active = "[x]" if "service" in types else "[ ]"
            buttons.append([
                InlineKeyboardButton(f"{story_active} Story", callback_data=f"pg_typ_story_{unique_id}", style=btn_style),
                InlineKeyboardButton(f"{svc_active} Service", callback_data=f"pg_typ_service_{unique_id}", style=btn_style),
            ])
            buttons.append([InlineKeyboardButton("Back", callback_data=f"pg_back_{unique_id}", style=btn_style)])
        
        elif sub_menu == "sender":
            # Sender Selection Sub-Menu
            sender_list = state.get("sender_list", [{"id": "me", "name": "Me"}])
            curr_from = state.get("from_id", "me")
            
            buttons.append([InlineKeyboardButton("━━ Choose Sender ━━", callback_data="noop", style=btn_style)])
            
            send_as_ok = state.get("send_as_locally_available", False)
            if not send_as_ok:
                buttons.append([InlineKeyboardButton("⚠️ Send As Restricted in this chat", callback_data="noop", style=btn_style)])
            
            # List all available senders
            for sender in sender_list:
                s_id = sender["id"]
                s_name = sender["name"]
                active = "[x]" if str(s_id) == str(curr_from) else "[ ]"
                buttons.append([InlineKeyboardButton(f"{active} {s_name}", callback_data=f"pg_set_sender_{s_id}_{unique_id}", style=btn_style)])
            
            buttons.append([InlineKeyboardButton("Back", callback_data=f"pg_back_{unique_id}", style=btn_style)])

        else:
            # ─── MAIN CONFIG MENU (Compact) ───
            curr_mode = state.get("mode", "latest")
            mode_lbl = loc("purgeme_mode_oldest" if curr_mode == "oldest" else "purgeme_mode_latest", curr_mode.capitalize())
            bd_min = int(batch_delay / 60)
            max_scan = state.get("max_scan", 500)
            
            # Determine filter display text
            TYPE_MAP = {
                "video_note": "VNOTE", "animation": "GIF", "document": "DOC",
                "location": "LOC", "contact": "CONT", "venue": "VEN"
            }
            if not types or "all" in types:
                filter_display = loc("GP_BTN_ALL", "All")
            elif len(types) > 1:
                filter_display = f"Multi({len(types)})"
            else:
                raw = types[0].lower()
                suffix = TYPE_MAP.get(raw, raw.upper())
                filter_display = loc(f"GP_BTN_{suffix}", suffix)
            
            # --- Definitions for Labels ---
            notify_active = state.get("notify", True)
            from_id = state.get("from_id", "me")
            sender_list = state.get("sender_list", [])
            sender_name = "Me"
            for s in sender_list:
                if s["id"] == from_id:
                    sender_name = s["name"]
                    break
            
            stealth_status = "ON" if not notify_active else "OFF"
            stealth_lbl = f"Stealth: {stealth_status} (as {sender_name})"
            
            # Row 1: Count & Batch
            buttons.append([
                InlineKeyboardButton(f"Count: {count} msg", callback_data=f"pg_menu_count_{unique_id}", style=btn_style),
                InlineKeyboardButton(f"Batch: {batch_size} msg", callback_data=f"pg_menu_batch_{unique_id}", style=btn_style),
            ])
            # Row 2: Delay/Msg & Delay/Batch
            buttons.append([
                InlineKeyboardButton(f"Delay/Msg: {delay}s", callback_data=f"pg_menu_delay_{unique_id}", style=btn_style),
                InlineKeyboardButton(f"Delay/Bch: {bd_min}m", callback_data=f"pg_menu_bdelay_{unique_id}", style=btn_style),
            ])
            # Row 3: Mode & Offset
            buttons.append([
                InlineKeyboardButton(f"Mode: {mode_lbl}", callback_data=f"pg_menu_mode_{unique_id}", style=btn_style),
                InlineKeyboardButton(f"Offset: {offset}", callback_data=f"pg_menu_offset_{unique_id}", style=btn_style),
            ])
            notif_status = "ON" if notify_active else "OFF"
            notif_lbl = f"Notif: {notif_status} (as {sender_name})"
            
            # Row 4: Filter & Max Scan
            buttons.append([
                InlineKeyboardButton(f"Filter: {filter_display}", callback_data=f"pg_menu_filter_{unique_id}", style=btn_style),
                InlineKeyboardButton(f"Max Scan: {max_scan}", callback_data=f"pg_menu_maxscan_{unique_id}", style=btn_style),
            ])
            # Row 5: ID Range & Date Range
            buttons.append([
                InlineKeyboardButton("ID Range", callback_data=f"pg_menu_bounds_{unique_id}", style=btn_style),
                InlineKeyboardButton("Date Range", callback_data=f"pg_menu_dates_{unique_id}", style=btn_style),
            ])
            # Row 6: From 
            buttons.append([
                InlineKeyboardButton(f"From: {sender_name}", callback_data=f"pg_menu_sender_{unique_id}", style=btn_style),
            ])
            # Row 7: Keep Recent 
            buttons.append([
                InlineKeyboardButton(f"Keep Recent: {state.get('keep_recent', 0)} msg(s)", callback_data=f"pg_menu_keeprecent_{unique_id}", style=btn_style),  
            ])
            # Row 7.5: Forward Log
            buttons.append([
                InlineKeyboardButton(f"Forward (Backup) To: {state.get('forward_log', 'off').replace('_', ' ').title()}", callback_data=f"pg_menu_forwardlog_{unique_id}", style=btn_style),
            ])
            # Row 7.6: Forward Delay 
            buttons.append([
                InlineKeyboardButton(f"Forward Delay: {state.get('fwd_delay', 0.5)}s", callback_data=f"pg_menu_fwddelay_{unique_id}", style=btn_style),
            ])
            # Row 8: Notif
            buttons.append([
                InlineKeyboardButton(notif_lbl, callback_data=f"pg_notify_{unique_id}", style=btn_style),
            ])
            # Row 9: Info
            buttons.append([
                InlineKeyboardButton(loc("purgeme_info_btn", "Info"), callback_data=f"pg_info_{unique_id}", style=btn_style),
            ])
            # Row 10: Start & Cancel
            start_lbl = loc("purgeme_start_purge", "Start Purgeme")
            cancel_lbl = loc("purgeme_cancel_purge", "Cancel")
            buttons.append([
                InlineKeyboardButton(start_lbl, callback_data=f"pg_start_{unique_id}", style=btn_style),
                InlineKeyboardButton(cancel_lbl, callback_data=f"pg_cancel_{unique_id}", style=btn_style),
            ])
    
    elif status in ["running", "waiting"]:
        pause_lbl = loc("purgeme_pause", "Pause")
        stop_lbl = loc("purgeme_stop", "Stop")
        refresh_lbl = loc("purgeme_refresh", "Status")
        
        buttons.append([
            InlineKeyboardButton(pause_lbl, callback_data=f"pg_pause_{unique_id}", style=btn_style),
            InlineKeyboardButton(stop_lbl, callback_data=f"pg_stop_{unique_id}", style=btn_style),
        ])
        buttons.append([InlineKeyboardButton(refresh_lbl, callback_data=f"pg_refresh_{unique_id}", style=btn_style)])

    elif status == "paused":
        resume_lbl = loc("purgeme_resume", "Resume")
        stop_lbl = loc("purgeme_stop", "Stop")
        refresh_lbl = loc("purgeme_refresh", "Status")
        
        buttons.append([
            InlineKeyboardButton(resume_lbl, callback_data=f"pg_resume_{unique_id}", style=btn_style),
            InlineKeyboardButton(stop_lbl, callback_data=f"pg_stop_{unique_id}", style=btn_style),
        ])
        buttons.append([InlineKeyboardButton(refresh_lbl, callback_data=f"pg_refresh_{unique_id}", style=btn_style)])

    elif status == "collecting":
        stop_lbl = loc("purgeme_stop", "Stop")
        refresh_lbl = loc("purgeme_refresh", "Status")
        buttons.append([
            InlineKeyboardButton(stop_lbl, callback_data=f"pg_stop_{unique_id}", style=btn_style),
            InlineKeyboardButton(refresh_lbl, callback_data=f"pg_refresh_{unique_id}", style=btn_style)
        ])

    elif status in ["finished", "stopped"]:
        repeat_lbl = loc("purgeme_repeat", "Repeat")
        close_lbl = loc("purgeme_close", "Close")
        buttons.append([
            InlineKeyboardButton(repeat_lbl, callback_data=f"pg_repeat_{unique_id}", style=btn_style),
            InlineKeyboardButton(close_lbl, callback_data=f"purgeme_close_{unique_id}", style=btn_style)
        ])

    elif status == "confirm":
        yes_lbl = loc("purgeme_confirm_yes", "Yes, Delete!")
        no_lbl = loc("purgeme_confirm_no", "No, Cancel")
        buttons.append([
            InlineKeyboardButton(yes_lbl, callback_data=f"pg_confirmyes_{unique_id}", style=btn_style),
            InlineKeyboardButton(no_lbl, callback_data=f"pg_cancel_{unique_id}", style=btn_style),
        ])

    elif status == "info":
        back_lbl = loc("back", "Back")
        buttons.append([InlineKeyboardButton(back_lbl, callback_data=f"pg_back_{unique_id}", style=btn_style)])


    return InlineKeyboardMarkup(buttons)

@Altruix.bot.on_inline_query(filters.regex(r"^purgeme_menu_(-?\d+)_(\d+)"))
async def purgeme_inline_handler(client: Client, query: InlineQuery):
    try:
        chat_id = query.matches[0].group(1)
        user_id = query.matches[0].group(2)
        unique_id = f"{chat_id}_{user_id}"
        
        # 🔐 Security Check: Only allow owner/sudo or the session owner to see the menu
        from Main.utils.access_control import is_authorized_user
        if str(query.from_user.id) != str(user_id) and not is_authorized_user(query.from_user.id, Altruix.config.OWNER_USERS_ID, Altruix.config.SUDO_USERS_ID):
             # Return empty result or an "Unauthorized" article
             return await query.answer(
                results=[
                    InlineQueryResultArticle(
                        title="Akses Ditolak",
                        input_message_content=InputTextMessageContent("Anda tidak memiliki izin untuk mengonfigurasi sesi purgeme ini.")
                    )
                ],
                cache_time=0,
                is_personal=True
             )

        # For initial inline query, we use the config state text
        if unique_id in Altruix.PURGEME_STATE:
             text = get_purgeme_text(Altruix.PURGEME_STATE[unique_id])
        else:
             text = "Configure Purgeme"

        await query.answer(
            results=[
                InlineQueryResultArticle(
                    title="Configure Purgeme",
                    input_message_content=InputTextMessageContent(
                        text,
                        parse_mode=enums.ParseMode.HTML,
                        disable_web_page_preview=True
                    ),
                    reply_markup=await get_purgeme_keyboard(chat_id, user_id, unique_id)
                )
            ],
            cache_time=0
        )
    except Exception as e:
        Altruix.log(f"Purgeme Inline Error: {e}\n{traceback.format_exc()}", level=40)

@Altruix.bot.on_callback_query(filters.regex(r"^pg_"))
async def purgeme_callback_handler(client: Client, cb: CallbackQuery):
    data = cb.data
    parts = data.split("_")

    try:
        parts_all = data.rsplit("_", 2)
        if len(parts_all) < 3:
            raise ValueError("Too few parts")

        chat_id_str, user_id_str = parts_all[-2], parts_all[-1]
        unique_id = f"{chat_id_str}_{user_id_str}"
        chat_id = int(chat_id_str)
        user_id = int(user_id_str)

        from Main.utils.access_control import is_authorized_user
        if str(cb.from_user.id) != str(user_id_str) and not is_authorized_user(cb.from_user.id, Altruix.config.OWNER_USERS_ID, Altruix.config.SUDO_USERS_ID):
            return await cb.answer(Altruix.get_string("ACCESS_DENIED"), show_alert=True)
    except (ValueError, IndexError):
        return await cb.answer("Invalid Session ID or Format.", show_alert=True)

    state = Altruix.PURGEME_STATE.get(unique_id)
    if not state:
        try:
            await Altruix.edit_cb(
                cb,
                "<b>Session Expired</b>\n\nSesi ini telah berakhir atau tidak ditemukan. Silakan mulai perintah <code>.purgeme</code> lagi.",
                parse_mode=enums.ParseMode.HTML
            )
            return
        except:
            return await cb.answer("Session Expired.", show_alert=True)

    if "callback_lock" not in state:
        state["callback_lock"] = asyncio.Lock()

    if cb.message:
        state["dashboard_msg_id"] = cb.message.id
        state["dashboard_chat_id"] = cb.message.chat.id
    elif cb.inline_message_id:
        state["inline_message_id"] = cb.inline_message_id

    try:
        async with state["callback_lock"]:
            # Log incoming callback for debugging
            Altruix.log(f"Purgeme CB: from={getattr(cb.from_user, 'id', None)} data={data} msg_id={getattr(cb.message, 'id', None)} inline_id={cb.inline_message_id}", level=10)

            # Simple de-duplication guard: ignore repeated identical callbacks
            now = time.time()
            last_cb = state.get("_last_callback")
            cb_key = (getattr(cb.from_user, 'id', None), data, state.get("dashboard_msg_id") or state.get("inline_message_id"))
            if last_cb and last_cb.get("key") == cb_key and (now - last_cb.get("t", 0)) < 0.8:
                Altruix.log(f"Duplicate purgeme callback ignored: {cb_key}", level=10)
                try:
                    await cb.answer()
                except:
                    pass
                return
            state["_last_callback"] = {"key": cb_key, "t": now}

            cmd = "_".join(parts[1:-2]) if len(parts) > 3 else ""

            if cmd.startswith("kr_"):
                action = parts[2]
                val = int(parts[3])
                current = state.get("keep_recent", 0)
                if action == "add":
                    state["keep_recent"] = current + val
                else:
                    state["keep_recent"] = max(0, current - val)

            elif "cnt_add" in data:
                val = int(parts[3])
                state["count"] += val

            elif "cnt_sub" in data:
                val = int(parts[3])
                state["count"] = max(1, state["count"] - val)

            elif "dly_add" in data:
                val = float(parts[3])
                state["delay"] = round(state["delay"] + val, 2)

            elif "dly_sub" in data:
                val = float(parts[3])
                state["delay"] = max(0, round(state["delay"] - val, 2))

            elif "dly_reset" in data:
                state["delay"] = 0

            elif "fdl_add" in data:
                val = float(parts[3])
                state["fwd_delay"] = round(state.get("fwd_delay", 0.5) + val, 2)

            elif "fdl_sub" in data:
                val = float(parts[3])
                state["fwd_delay"] = max(0, round(state.get("fwd_delay", 0.5) - val, 2))

            elif "fdl_reset" in data:
                state["fwd_delay"] = 0.5

            elif "menu_count" in data:
                state["sub_menu"] = "count"
            elif "menu_batch" in data:
                state["sub_menu"] = "batch"
            elif "menu_keeprecent" in data:
                state["sub_menu"] = "keeprecent"
            elif "menu_delay" in data:
                state["sub_menu"] = "delay"
            elif "menu_bdelay" in data:
                state["sub_menu"] = "bdelay"
            elif "menu_mode" in data:
                state["sub_menu"] = "mode"
            elif "menu_offset" in data:
                state["sub_menu"] = "offset"
            elif "menu_bounds" in data:
                state["sub_menu"] = "bounds"
            elif "menu_dates" in data:
                state["sub_menu"] = "dates"
            elif "menu_maxscan" in data:
                state["sub_menu"] = "maxscan"
            elif "menu_forwardlog" in data:
                state["sub_menu"] = "forwardlog"
            elif "menu_fwddelay" in data:
                state["sub_menu"] = "fwddelay"
            elif "menu_filter" in data:
                state["sub_menu"] = "filter"
            elif "menu_sender" in data:
                state["sub_menu"] = "sender"

            elif "mode_" in data:
                mode = parts[2]
                state["mode"] = mode

            elif "set_fwd_" in data:
                f_val = data.replace("pg_set_fwd_", "", 1).replace(f"_{unique_id}", "", 1)
                state["forward_log"] = f_val
                await cb.answer(f"Forward Log: {f_val.replace('_', ' ').title()}")

            elif "set_sender_" in data:
                s_id_raw = data.replace("pg_set_sender_", "", 1).replace(f"_{unique_id}", "", 1)
                if s_id_raw == "me":
                    state["from_id"] = "me"
                else:
                    try:
                        state["from_id"] = int(s_id_raw)
                    except:
                        state["from_id"] = s_id_raw

                try:
                    client_ref = state.get("client")
                    chat_ref = state.get("chat_id")
                    if client_ref and chat_ref:
                        total = await client_ref.search_messages_count(chat_ref, from_user=state["from_id"])
                        state["total_account_messages"] = total
                except:
                    pass

            elif "notify" in data:
                state["notify"] = not state.get("notify", True)

            elif "typ_" in data:
                t_type = data.replace("pg_typ_", "", 1).replace(f"_{unique_id}", "", 1)
                if t_type == "all":
                    if "all" in state["types"]:
                        state["types"] = []
                    else:
                        state["types"] = ["all"]
                else:
                    if "all" in state["types"]:
                        state["types"].remove("all")
                    if t_type in state["types"]:
                        state["types"].remove(t_type)
                    else:
                        state["types"].append(t_type)
                    if not state["types"]:
                        state["types"] = ["all"]

            elif "btc_add" in data:
                val = int(parts[3])
                state["batch_size"] = state.get("batch_size", 60) + val

            elif "btc_sub" in data:
                val = int(parts[3])
                curr = state.get("batch_size", 60)
                state["batch_size"] = max(10, curr - val)

            elif "dbc_add" in data:
                val_str = parts[3].replace('m', '')
                val_min = int(val_str)
                val_sec = val_min * 60
                state["batch_delay"] = state.get("batch_delay", 120) + val_sec

            elif "dbc_sub" in data:
                val_str = parts[3].replace('m', '')
                val_min = int(val_str)
                val_sec = val_min * 60
                curr = state.get("batch_delay", 120)
                state["batch_delay"] = max(0, curr - val_sec)

            elif "off_add" in data:
                val = int(parts[3])
                state["offset"] = state.get("offset", 0) + val

            elif "off_sub" in data:
                val = int(parts[3])
                curr = state.get("offset", 0)
                state["offset"] = max(0, curr - val)

            elif "off_reset" in data:
                state["offset"] = 0

            elif "bnd_min_add" in data:
                val = int(parts[4])
                state["min_id"] = state.get("min_id", 0) + val

            elif "bnd_min_sub" in data:
                val = int(parts[4])
                state["min_id"] = max(0, state.get("min_id", 0) - val)

            elif "bnd_max_add" in data:
                val = int(parts[4])
                state["max_id"] = state.get("max_id", 0) + val

            elif "bnd_max_sub" in data:
                val = int(parts[4])
                state["max_id"] = max(0, state.get("max_id", 0) - val)

            elif "bnd_min_reset" in data:
                state["min_id"] = 0

            elif "bnd_max_reset" in data:
                state["max_id"] = 0

            elif "dat_min_add" in data:
                val = int(parts[4])
                state["min_days"] = state.get("min_days", 0) + val

            elif "dat_min_sub" in data:
                val = int(parts[4])
                state["min_days"] = max(0, state.get("min_days", 0) - val)

            elif "dat_max_add" in data:
                val = int(parts[4])
                state["max_days"] = state.get("max_days", 0) + val

            elif "dat_max_sub" in data:
                val = int(parts[4])
                state["max_days"] = max(0, state.get("max_days", 0) - val)

            elif "dat_min_reset" in data:
                state["min_days"] = 0

            elif "dat_max_reset" in data:
                state["max_days"] = 0

            elif "scn_add" in data:
                val = int(parts[3])
                state["max_scan"] = state.get("max_scan", 500) + val

            elif "scn_sub" in data:
                val = int(parts[3])
                state["max_scan"] = max(10, state.get("max_scan", 500) - val)

            elif "scn_reset" in data:
                state["max_scan"] = 500

            elif "info" in data:
                state["sub_menu"] = None
                state["status"] = "info"

            elif "back" in data:
                if state.get("sub_menu"):
                    state["sub_menu"] = None
                else:
                    state["status"] = "config"

            elif "start" in data:
                state["status"] = "confirm"

            elif "confirmyes" in data:
                if state.get("event") and not state["event"].is_set():
                    state["event"].set()
                    title = Altruix.get_string("purgeme_title") or "<b>Userbot Purgeme</b>"
                    btn_style_local = get_user_button_style(int(user_id_str))

                    chat_name = state.get("chat_name", "Unknown")
                    chat_link = state.get("chat_link")
                    display_name = f"<a href='{chat_link}'>{chat_name}</a>" if chat_link else f"<b>{chat_name}</b>"

                    if cb.message:
                        state["dashboard_msg_id"] = cb.message.id
                        state["dashboard_chat_id"] = cb.message.chat.id

                    await Altruix.edit_cb(
                        cb,
                        f"<blockquote expandable>{title}\n<i>Task is in progress...</i>\n<b>Chat:</b> {display_name}</blockquote>",
                        parse_mode=enums.ParseMode.HTML,
                        disable_web_page_preview=True,
                        reply_markup=InlineKeyboardMarkup([
                            [
                                InlineKeyboardButton("Delete MSG", callback_data=f"purgeme_close_{unique_id}", style=btn_style_local),
                                InlineKeyboardButton("Cancel", callback_data=f"pg_abort_{unique_id}", style=btn_style_local)
                            ],
                            [InlineKeyboardButton("Status", callback_data=f"pg_refresh_{unique_id}", style=btn_style_local)]
                        ])
                    )
                return

            elif "abort" in data:
                state["status"] = "cancelled"
                if state.get("event"): state["event"].set()
                if state.get("stop_event"): state["stop_event"].set()
                await cb.answer("Proses purgeme dihentikan!", show_alert=True)
                title = Altruix.get_string("purgeme_title") or "<b>Userbot Purgeme</b>"
                await Altruix.edit_cb(
                    cb,
                    f"{title}\n<b>Task Cancelled / Aborted</b>",
                    parse_mode=enums.ParseMode.HTML,
                )

            elif "cancel" in data:
                state["status"] = "cancelled"
                if state.get("event"): state["event"].set()
                if state.get("stop_event"): state["stop_event"].set()
                try:
                    await Altruix.delete_cb(cb)
                except:
                    try:
                        title = Altruix.get_string("purgeme_title") or "<b>Userbot Purgeme</b>"
                        await Altruix.edit_cb(
                            cb,
                            f"{title}\n<b>Cancelled</b>",
                            parse_mode=enums.ParseMode.HTML,
                        )
                    except:
                        pass
                await cb.answer("Cancelled", show_alert=False)
                return

            elif "stop" in data:
                if state.get("stop_event"): state["stop_event"].set()
                await cb.answer("Stopped", show_alert=False)

            elif "pause" in data:
                state["status"] = "paused"
                if state.get("pause_event"): state["pause_event"].clear()

            elif "resume" in data:
                state["status"] = "running"
                if state.get("pause_event"): state["pause_event"].set()

            elif "repeat" in data:
                state["status"] = "config"
                state["sub_menu"] = None
                state["processed"] = 0
                state["scanned"] = 0
                state["failed"] = 0
                if state.get("event"): state["event"].clear()
                if state.get("stop_event"): state["stop_event"].clear()
                if state.get("pause_event"): state["pause_event"].set()

            elif "refresh" in data:
                pass

            settings_prefixes = [
                "pg_cnt_", "pg_dly_", "pg_btc_", "pg_dbc_", "pg_mode_", "pg_off_",
                "pg_bnd_", "pg_dat_", "pg_scn_", "pg_typ_", "pg_notify",
                "pg_set_fwd_", "pg_set_sender_", "pg_kr_", "pg_fdl_"
            ]
            if any(data.startswith(pref) for pref in settings_prefixes):
                try:
                    save_user_purgeme_config(user_id, {
                        "count": state.get("count"),
                        "delay": state.get("delay"),
                        "batch_size": state.get("batch_size"),
                        "batch_delay": state.get("batch_delay"),
                        "mode": state.get("mode"),
                        "notify": state.get("notify"),
                        "forward_log": state.get("forward_log"),
                        "fwd_delay": state.get("fwd_delay", 0.5),
                        "keep_recent": state.get("keep_recent"),
                        "max_scan": state.get("max_scan"),
                        "offset": state.get("offset"),
                        "min_id": state.get("min_id"),
                        "max_id": state.get("max_id"),
                        "min_days": state.get("min_days"),
                        "max_days": state.get("max_days"),
                        "types": state.get("types"),
                        "from_id": state.get("from_id", "me")
                    })
                except Exception as save_err:
                    Altruix.log(f"Purgeme config save failed: {save_err}\n{traceback.format_exc()}", level=40)

        new_kb = await get_purgeme_keyboard(chat_id, user_id, unique_id)
        new_text = get_purgeme_text(state)

        try:
            await Altruix.edit_cb(
                cb,
                new_text,
                reply_markup=new_kb,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )
        except MessageNotModified:
            await cb.answer("Status Updated", show_alert=False)
        except FloodWait as fw:
            await asyncio.sleep(fw.value + 1)
            try:
                await Altruix.edit_cb(
                    cb,
                    new_text,
                    reply_markup=new_kb,
                    parse_mode=enums.ParseMode.HTML,
                    disable_web_page_preview=True
                )
            except:
                pass
        except Exception as inner_e:
            raise inner_e

    except Exception as e:
        Altruix.log(f"Purgeme Callback Fatal Error: {e}\n{traceback.format_exc()}", level=40)
        if "MessageNotModified" not in str(e):
            try:
                await cb.answer(f"Error: {str(e)[:50]}", show_alert=True)
            except:
                pass

@Altruix.bot.on_callback_query(filters.regex(r"^purgeme_close(_|$)"))
async def purgeme_close(client, cb: CallbackQuery):
    # Security: Verify if user is authorized
    from Main.internals.settings import check_authorization
    if not await check_authorization(cb):
        return

    data = cb.data
    unique_id = data.replace("purgeme_close_", "", 1) if "_" in data else None
    
    # 1. Primary Attempt: Standard message delete
    if await Altruix.delete_cb(cb):
        return

    # 2. Secondary Attempt: Delete via Userbot/State (For Inline Results)
    if unique_id:
        state = Altruix.PURGEME_STATE.get(unique_id)
        if state and state.get("dashboard_msg_id") and state.get("dashboard_chat_id"):
            try:
                # Use Userbot to delete its own message
                await state["client"].delete_messages(state["dashboard_chat_id"], state["dashboard_msg_id"])
                return
            except Exception as e:
                Altruix.log(f"Purgeme: Failed to delete via userbot: {e}")
    
    # 3. Final Fallback: Edit message text if it's an inline result and we can't delete
    if not cb.message:
        try:
            # Try via Bot assistant one more time with inline_message_id
            await Altruix.edit_cb(cb, "<b>Purgeme Closed</b>", parse_mode=enums.ParseMode.HTML)
            await cb.answer("Message closed.", show_alert=False)
            return
        except:
            pass

    await cb.answer("Message deleted or invalid session.", show_alert=False)



# @Altruix.register_on_cmd(
#     ["start"],
#     cmd_help={
#         "help": "Start the Purgeme Bot process.",
#         "usage": "/start purgeme_{unique_id}",
#         "example": "/start purgeme_123456789_987654321",
#         "detail": "Memulai sesi konfigurasi Purgeme via Bot Assistant. Biasanya dipanggil otomatis oleh tombol dari Userbot."
#     },
#     group_only=False,
#     requires_input=False, 
#     requires_reply=False
# )
# @iuser_check
# @log_errors
# async def purgeme_start_handler(client: Client, message):
#     from Main.utils.access_control import is_authorized_user
    
#     # 1. Fallback if no arguments provided
#     if len(message.command) <= 1:
#         if is_authorized_user(message.from_user.id, Altruix.config.OWNER_USERS_ID, Altruix.config.SUDO_USERS_ID):
#              # Only show response if authorized, otherwise ignore to prevent spam/discovery
#              await message.reply(
#                  f"👋 <b>Halo, {message.from_user.first_name}!</b>\n\n"
#                  f"Saya adalah asisten Altruix. Gunakan tombol pada Userbot untuk mengatur Purgeme.\n"
#                  f"Ketik /help untuk melihat daftar perintah yang tersedia."
#              )
#         return

#     # 2. Process arguments
#     param = message.command[1]
#     if param.startswith("purgeme_"):
#         unique_id = param.replace("purgeme_", "", 1)
        
#         try:
#             chat_id, user_id = unique_id.rsplit("_", 1)
            
#             # Security: Ensure only the session owner or sudo can access
#             if str(message.from_user.id) != str(user_id) and not is_authorized_user(message.from_user.id, Altruix.config.OWNER_USERS_ID, Altruix.config.SUDO_USERS_ID):
#                 msg = Altruix.get_string("ACCESS_DENIED")
#                 await message.reply(msg)
#                 return
            
#             state = Altruix.PURGEME_STATE.get(unique_id)
#             if not state:
#                 await message.reply("Session Expired or Invalid.")
#                 return

#             # Show Menu
#             menu_text = get_purgeme_text(state)
#             kb = await get_purgeme_keyboard(chat_id, user_id, unique_id)
            
#             await message.reply(
#                 menu_text,
#                 reply_markup=kb,
#                 parse_mode=enums.ParseMode.HTML,
#                 disable_web_page_preview=True
#             )
#         except ValueError:
#             await message.reply("Invalid Link Format.")


