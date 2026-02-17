PLUGIN_VERSION = "0.0.21"

"""
Purgeme Bot Plugin
Handles the interactive UI for the Userbot Purgeme command.
"""

import re
import time
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.errors import MessageNotModified
from pyrogram.types import (
    InlineQuery, InlineQueryResultArticle, InputTextMessageContent,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)
from Main.core.decorators import log_errors, iuser_check
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
    
    title = Altruix.get_string("purgeme_title") or "🗑 <b>Altruix Purgeme</b>"
    
    def loc(key): return Altruix.get_string(key)
    
    if status == "config":
        menu_title = loc("purgeme_menu_title") or "<b>⚙️ Purgeme Configuration</b>"
        chat_name = state.get("chat_name", "Unknown")
        chat_id = state.get("chat_id", "Unknown")
        chat_link = state.get("chat_link")
        
        display_name = f"<a href='{chat_link}'>{chat_name}</a>" if chat_link else f"<b>{chat_name}</b>"
        
        return (
            f"{title}\n\n"
            f"<b>Chat:</b> {display_name}\n"
            f"<b>Chat_ID:</b> <code>{chat_id}</code>\n\n"
            f"{menu_title}\n"
            f"Please select options:"
        )

    chat_name = state.get("chat_name", "Unknown")
    account_name = state.get("account_name", "Unknown")

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

    header = f"{title}\n" \
             f"<b>Mode:</b> {mode.capitalize()} | <b>Type:</b> {type_display}\n" \
             f"<b>Target:</b> {count} messages | <b>Offset:</b> {offset}\n" \
             f"<b>Batch:</b> {batch_size} | <b>DelayBc:</b> {int(batch_delay/60)}m\n" \
             f"<b>Chat:</b> {chat_name}\n" \
             f"<b>Account:</b> {account_name}"
        
    if status == "collecting":
        status_line = (loc("purgeme_collecting_detailed") or "🔎 <b>Collecting...</b>\nFound: {processed}/{count}\nScanned: {scanned}").format(
            processed=processed, count=count, scanned=scanned
        )
        return f"{header}\n\n{status_line}"

    elif status == "running":
        status_line = (loc("purgeme_deleting_detailed") or "🗑 <b>Deleting...</b>\nDeleted: {processed}/{count}").format(
            processed=processed, count=count
        )
        if delay > 0: status_line += f"\nDelay: {delay}s"
        return f"{header}\n\n{status_line}"

    elif status == "paused":
        status_line = (loc("purgeme_paused_detailed") or "⏸ <b>PAUSED</b>\nDeleted: {processed}/{count}").format(
            processed=processed, count=count
        )
        return f"{header}\n\n{status_line}"

    elif status == "finished":
        start_time = state.get("start_time", 0)
        duration = round(time.time() - start_time, 2) if start_time > 0 else 0
        
        chat_link = state.get("chat_link")
        chat_display = f"<a href='{chat_link}'>{chat_name}</a>" if chat_link else f"<b>{chat_name}</b>"
        
        fin_text = (loc("purgeme_finished_detailed") or "✅ <b>Finished!</b>\nDeleted: {processed} messages\nTime: {duration}s\nChat: {chat}\nAccount: {account}").format(
            processed=processed, duration=duration, chat=chat_display, account=account_name
        )
        return f"{title}\n\n{fin_text}"

    elif status == "info":
        info_text = loc("purgeme_info_text") or "ℹ️ Info Text Not Found"
        return f"{title}\n\n{info_text}"
        
    elif status == "cancelled":
        lbl = loc("purgeme_cancelled_short") or "❌ <b>Cancelled</b>"
        return f"{title}\n\n{lbl}"
        
    return title

def get_purgeme_keyboard(chat_id, user_id, unique_id):
    state = Altruix.PURGEME_STATE.get(unique_id)
    if not state:
        return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Session Ended", callback_data="purgeme_close")]])

    status = state["status"]
    status = state["status"]
    count = state["count"]
    delay = state["delay"]
    batch_size = state.get("batch_size", 60)
    batch_delay = state.get("batch_delay", 120)
    offset = state.get("offset", 0)
    types = state["types"]

    buttons = []
    
    def loc(key, default):
        s = Altruix.get_string(key)
        return s if s else default

    if status == "config":
        # Count Controls
        count_lbl = loc("purgeme_count", "Count: {}").format(count)
        buttons.append([
            InlineKeyboardButton(count_lbl, callback_data="noop"),
            InlineKeyboardButton("-10", callback_data=f"pg_cnt_sub_10_{unique_id}"),
            InlineKeyboardButton("+10", callback_data=f"pg_cnt_add_10_{unique_id}"),
            InlineKeyboardButton("+100", callback_data=f"pg_cnt_add_100_{unique_id}"),
        ])
        
        # Delay Controls
        delay_lbl = loc("purgeme_delay", "Delay: {}s").format(delay)
        reset_lbl = loc("purgeme_reset", "Reset")
        buttons.append([
            InlineKeyboardButton(delay_lbl, callback_data="noop"),
            InlineKeyboardButton("-0.5s", callback_data=f"pg_dly_sub_0.5_{unique_id}"),
            InlineKeyboardButton("+0.5s", callback_data=f"pg_dly_add_0.5_{unique_id}"),
            InlineKeyboardButton(reset_lbl, callback_data=f"pg_dly_reset_{unique_id}"),
        ])
        
        # Mode Selection
        curr_mode = state.get("mode", "latest")
        mode_lbl_key = "purgeme_mode_latest" if curr_mode == "latest" else "purgeme_mode_oldest"
        mode_lbl = loc(mode_lbl_key, curr_mode.capitalize())
        
        latest_btn = f"{'✅' if curr_mode == 'latest' else '☑️'} {loc('purgeme_mode_latest', 'Newest')}"
        oldest_btn = f"{'✅' if curr_mode == 'oldest' else '☑️'} {loc('purgeme_mode_oldest', 'Oldest')}"
        
        buttons.append([
            InlineKeyboardButton(f"Mode: {mode_lbl}", callback_data="noop"),
            InlineKeyboardButton(latest_btn, callback_data=f"pg_mode_latest_{unique_id}"),
            InlineKeyboardButton(oldest_btn, callback_data=f"pg_mode_oldest_{unique_id}"),
        ])
        
        # Row 4: Notification Toggle
        # Row 4: Notification Toggle
        notify_active = state.get("notify", True)
        notif_lbl = Altruix.get_string("GP_BTN_NOTIF_ON" if notify_active else "GP_BTN_NOTIF_OFF") or (f"🔔 Notif: ON" if notify_active else "🔕 Notif: OFF")
        buttons.append([
            InlineKeyboardButton(notif_lbl, callback_data=f"pg_notify_{unique_id}"),
        ])

        # Batch Controls
        batch_lbl = f"Batch: {batch_size}"
        buttons.append([
            InlineKeyboardButton(batch_lbl, callback_data="noop"),
            InlineKeyboardButton("-10", callback_data=f"pg_btc_sub_10_{unique_id}"),
            InlineKeyboardButton("+10", callback_data=f"pg_btc_add_10_{unique_id}"),
        ])

        # Batch Delay Controls
        bd_min = int(batch_delay / 60)
        bd_lbl = f"DelayBc: {bd_min}m"
        buttons.append([
            InlineKeyboardButton(bd_lbl, callback_data="noop"),
            InlineKeyboardButton("-2m", callback_data=f"pg_dbc_sub_2m_{unique_id}"),
            InlineKeyboardButton("+2m", callback_data=f"pg_dbc_add_2m_{unique_id}"),
            InlineKeyboardButton("+10m", callback_data=f"pg_dbc_add_10m_{unique_id}"),
        ])

        # Offset Controls
        off_lbl = f"Offset: {offset}"
        buttons.append([
            InlineKeyboardButton(off_lbl, callback_data="noop"),
            InlineKeyboardButton("-5", callback_data=f"pg_off_sub_5_{unique_id}"),
            InlineKeyboardButton("+5", callback_data=f"pg_off_add_5_{unique_id}"),
            InlineKeyboardButton("Reset", callback_data=f"pg_off_reset_{unique_id}"),
        ])
        
        # Row 1: Core Media
        type_row_1 = []
        all_active = "✅" if "all" in types else "☑️"
        type_row_1.append(InlineKeyboardButton(f"{all_active} {loc('GP_BTN_ALL', 'All')}", callback_data=f"pg_typ_all_{unique_id}"))
        
        photo_active = "✅" if ("photo" in types or "image" in types) else "☑️"
        type_row_1.append(InlineKeyboardButton(f"{photo_active} {loc('GP_BTN_IMG', 'Photo')}", callback_data=f"pg_typ_photo_{unique_id}"))
        
        vid_active = "✅" if "video" in types else "☑️"
        type_row_1.append(InlineKeyboardButton(f"{vid_active} {loc('GP_BTN_VID', 'Video')}", callback_data=f"pg_typ_video_{unique_id}"))
        
        buttons.append(type_row_1)

        # Row 2: Engagement
        type_row_2 = []
        txt_active = "✅" if "text" in types else "☑️"
        type_row_2.append(InlineKeyboardButton(f"{txt_active} {loc('GP_BTN_TXT', 'Text')}", callback_data=f"pg_typ_text_{unique_id}"))

        aud_active = "✅" if "audio" in types else "☑️"
        type_row_2.append(InlineKeyboardButton(f"{aud_active} {loc('GP_BTN_AUD', 'Audio')}", callback_data=f"pg_typ_audio_{unique_id}"))

        stk_active = "✅" if "sticker" in types else "☑️"
        type_row_2.append(InlineKeyboardButton(f"{stk_active} {loc('GP_BTN_STK', 'Sticker')}", callback_data=f"pg_typ_sticker_{unique_id}"))
        
        buttons.append(type_row_2)
        
        # Row 3: Rich Media
        type_row_3 = []
        anim_active = "✅" if ("animation" in types or "gif" in types) else "☑️"
        type_row_3.append(InlineKeyboardButton(f"{anim_active} {loc('GP_BTN_GIF', 'Anim')}", callback_data=f"pg_typ_animation_{unique_id}"))

        doc_active = "✅" if ("document" in types or "file" in types) else "☑️"
        type_row_3.append(InlineKeyboardButton(f"{doc_active} {loc('GP_BTN_DOC', 'Doc')}", callback_data=f"pg_typ_document_{unique_id}"))

        vnote_active = "✅" if ("video_note" in types or "vnote" in types) else "☑️"
        type_row_3.append(InlineKeyboardButton(f"{vnote_active} {loc('GP_BTN_VNOTE', 'VNote')}", callback_data=f"pg_typ_video_note_{unique_id}"))
        
        buttons.append(type_row_3)

        # Row 4: Specialized
        type_row_4 = []
        voice_active = "✅" if "voice" in types else "☑️"
        type_row_4.append(InlineKeyboardButton(f"{voice_active} {loc('GP_BTN_VN', 'Voice')}", callback_data=f"pg_typ_voice_{unique_id}"))

        contact_active = "✅" if "contact" in types else "☑️"
        type_row_4.append(InlineKeyboardButton(f"{contact_active} {loc('GP_BTN_CONT', 'Contact')}", callback_data=f"pg_typ_contact_{unique_id}"))

        loc_active = "✅" if "location" in types else "☑️"
        type_row_4.append(InlineKeyboardButton(f"{loc_active} {loc('GP_BTN_LOC', 'Loc')}", callback_data=f"pg_typ_location_{unique_id}"))
        
        buttons.append(type_row_4)

        # Row 5: Interaction
        type_row_5 = []
        venue_active = "✅" if "venue" in types else "☑️"
        type_row_5.append(InlineKeyboardButton(f"{venue_active} {loc('GP_BTN_VEN', 'Venue')}", callback_data=f"pg_typ_venue_{unique_id}"))

        game_active = "✅" if "game" in types else "☑️"
        type_row_5.append(InlineKeyboardButton(f"{game_active} {loc('GP_BTN_GAME', 'Game')}", callback_data=f"pg_typ_game_{unique_id}"))

        poll_active = "✅" if "poll" in types else "☑️"
        type_row_5.append(InlineKeyboardButton(f"{poll_active} {loc('GP_BTN_POLL', 'Poll')}", callback_data=f"pg_typ_poll_{unique_id}"))
        
        buttons.append(type_row_5)

        # Row 6: Games
        buttons.append([
            InlineKeyboardButton(f"{'✅' if 'dice' in types else '☑️'} {loc('GP_BTN_DICE', 'Dice')}", callback_data=f"pg_typ_dice_{unique_id}")
        ])
        
        # Action Buttons
        # Action Buttons
        start_lbl = loc("purgeme_start_purge", "🚀 Start Purgeme")
        cancel_lbl = loc("purgeme_cancel_purge", "❌ Cancel")
        info_lbl = loc("purgeme_info_btn", "ℹ️ Info")
        buttons.append([
            InlineKeyboardButton(start_lbl, callback_data=f"pg_start_{unique_id}"),
            InlineKeyboardButton(cancel_lbl, callback_data=f"pg_cancel_{unique_id}"),
            InlineKeyboardButton(info_lbl, callback_data=f"pg_info_{unique_id}"),
        ])
    
    elif status == "running":
        pause_lbl = loc("purgeme_pause", "⏸ Pause")
        stop_lbl = loc("purgeme_stop", "⏹ Stop")
        refresh_lbl = loc("purgeme_refresh", "🔄 Refresh")
        
        buttons.append([
            InlineKeyboardButton(pause_lbl, callback_data=f"pg_pause_{unique_id}"),
            InlineKeyboardButton(stop_lbl, callback_data=f"pg_stop_{unique_id}"),
        ])
        buttons.append([InlineKeyboardButton(refresh_lbl, callback_data=f"pg_refresh_{unique_id}")])

    elif status == "paused":
        resume_lbl = loc("purgeme_resume", "▶️ Resume")
        stop_lbl = loc("purgeme_stop", "⏹ Stop")
        refresh_lbl = loc("purgeme_refresh", "🔄 Refresh")
        
        buttons.append([
            InlineKeyboardButton(resume_lbl, callback_data=f"pg_resume_{unique_id}"),
            InlineKeyboardButton(stop_lbl, callback_data=f"pg_stop_{unique_id}"),
        ])
        buttons.append([InlineKeyboardButton(refresh_lbl, callback_data=f"pg_refresh_{unique_id}")])

    elif status == "info":
        back_lbl = loc("back", "🔙 Back")
        buttons.append([InlineKeyboardButton(back_lbl, callback_data=f"pg_back_{unique_id}")])

    elif status == "finished":
        close_lbl = loc("purgeme_close", "Close")
        buttons.append([InlineKeyboardButton(close_lbl, callback_data=f"purgeme_close_{unique_id}")])

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
                        title="🚫 Akses Ditolak",
                        input_message_content=InputTextMessageContent("⛔ Anda tidak memiliki izin untuk mengonfigurasi sesi purgeme ini.")
                    )
                ],
                cache_time=0,
                is_personal=True
             )

        # For initial inline query, we use the config state text
        if unique_id in Altruix.PURGEME_STATE:
             text = get_purgeme_text(Altruix.PURGEME_STATE[unique_id])
        else:
             text = "⚙️ Configure Purgeme"

        await query.answer(
            results=[
                InlineQueryResultArticle(
                    title="Configure Purgeme",
                    input_message_content=InputTextMessageContent(
                        text,
                        parse_mode=enums.ParseMode.HTML,
                        disable_web_page_preview=True
                    ),
                    reply_markup=get_purgeme_keyboard(chat_id, user_id, unique_id)
                )
            ],
            cache_time=0
        )
    except Exception as e:
        Altruix.log(f"Purgeme Inline Error: {e}")

@Altruix.bot.on_callback_query(filters.regex(r"^pg_"))
async def purgeme_callback_handler(client: Client, cb: CallbackQuery):
    data = cb.data
    parts = data.split("_")
    
    # ─── 🔐 SECURITY ENFORCEMENT ───
    # We must determine the session owner before processing ANY action.
    # Format map: pg_{action}_{params}_{unique_id}
    prefix_map = {
        "cnt_add": 4, "cnt_sub": 4, "dly_add": 4, "dly_sub": 4, "dly_reset": 3,
        "btc_add": 4, "btc_sub": 4, "dbc_add": 4, "dbc_sub": 4,
        "off_add": 4, "off_sub": 4, "off_reset": 3,
        "typ": 3, "start": 2, "cancel": 2, "stop": 2, "pause": 2,
        "resume": 2, "refresh": 2, "mode": 3, "notify": 2, "abort": 2, "info": 2, "back": 2
    }
    
    curr_prefix = None
    for p, count in prefix_map.items():
        if f"pg_{p}" in data:
            curr_prefix = count
            break
            
    if not curr_prefix:
        return await cb.answer("❌ Invalid Callback Format.", show_alert=True)
        
    unique_id = "_".join(parts[curr_prefix:])
    try:
        chat_id, user_id = unique_id.rsplit("_", 1)
        from Main.utils.access_control import is_authorized_user
        if str(cb.from_user.id) != str(user_id) and not is_authorized_user(cb.from_user.id, Altruix.config.OWNER_USERS_ID, Altruix.config.SUDO_USERS_ID):
            unauth = Altruix.get_string("ACCESS_DENIED")
            return await cb.answer(unauth, show_alert=True)
    except (ValueError, IndexError):
        return await cb.answer("❌ Invalid Session ID.", show_alert=True)

    state = Altruix.PURGEME_STATE.get(unique_id)
    if not state:
         # ─── 2. FIX: Session Not Found Friendly Handling ───
         try:
            await Altruix.edit_cb(cb, "⚠️ <b>Session Expired</b>\n\nSesi ini telah berakhir atau tidak ditemukan. Silakan mulai perintah <code>.purgeme</code> lagi.", parse_mode=enums.ParseMode.HTML)
            return
         except:
            return await cb.answer("⚠️ Session Expired.", show_alert=True)

    # Capture message details for dashboard updates and cleanup
    if cb.message:
        state["dashboard_msg_id"] = cb.message.id
        state["dashboard_chat_id"] = cb.message.chat.id

    try:
        if "cnt_add" in data:
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

        elif "mode_" in data:
            mode = parts[2]
            state["mode"] = mode

        elif "notify" in data:
            # ─── 3. FIX: Toggle Notification Logic ───
            state["notify"] = not state.get("notify", True)

        elif "typ_" in data:
            t_type = parts[2]
            if t_type == "all":
                if "all" in state["types"]:
                    state["types"] = []
                else:
                    state["types"] = ["all"]
            else:
                if "all" in state["types"]: state["types"].remove("all")
                if t_type in state["types"]:
                    state["types"].remove(t_type)
                else:
                    state["types"].append(t_type)
                if not state["types"]: state["types"] = ["all"]
        
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

        elif "info" in data:
            # ─── 1. FIX: Info Page Logic ───
            state["status"] = "info"
            
        elif "back" in data:
            state["status"] = "config"

        elif "start" in data:
            if not state["event"].is_set(): 
                state["event"].set()
                # Immediate Feedback
                title = Altruix.get_string("purgeme_title") or "🗑 <b>Userbot Purgeme</b>"
                
                # IMPORTANT: Ensure persistent message tracking for deletion later
                if cb.message:
                    state["dashboard_msg_id"] = cb.message.id
                    state["dashboard_chat_id"] = cb.message.chat.id
                    
                await Altruix.edit_cb(
                    cb,
                    f"{title}\n⏳ <i>Task is in progress...</i>",
                    parse_mode=enums.ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("🗑 Delete", callback_data=f"purgeme_close_{unique_id}"),
                            InlineKeyboardButton("❌ Cancel", callback_data=f"pg_abort_{unique_id}")
                        ]
                    ])
                )
            return # Prevent further processing

        elif "abort" in data:
            state["status"] = "cancelled"
            state["event"].set()
            state["stop_event"].set()
            await cb.answer("🛑 Proses purgeme dihentikan!", show_alert=True)
            title = Altruix.get_string("purgeme_title") or "🗑 <b>Userbot Purgeme</b>"
            await Altruix.edit_cb(cb, f"{title}\n❌ <b>Task Cancelled / Aborted</b>")
            await asyncio.sleep(3)
            await Altruix.delete_cb(cb)
            return # Prevent further processing

        elif "cancel" in data:
            state["status"] = "cancelled"
            state["event"].set()
            state["stop_event"].set()
            # Try to delete, but answer callback regardless
            try:
                await Altruix.delete_cb(cb)
            except:
                # If deletion fails (e.g., inline result), edit to show cancellation
                try:
                    title = Altruix.get_string("purgeme_title") or "🗑 <b>Userbot Purgeme</b>"
                    await Altruix.edit_cb(cb, f"{title}\n❌ <b>Cancelled</b>")
                except:
                    pass
            await cb.answer("❌ Cancelled", show_alert=False)
            return # Prevent further processing

        elif "stop" in data:
            state["stop_event"].set()
            await cb.answer("⏹ Stopped", show_alert=False)

        elif "pause" in data:
            state["status"] = "paused"
            state["pause_event"].clear()
            # No need to answer here, will be answered by general update below

        elif "resume" in data:
            state["status"] = "running"
            state["pause_event"].set()
            # No need to answer here, will be answered by general update below

        elif "refresh" in data:
            # Just trigger UI update, answer will be handled below
            pass

        # General Keyboard Update
        new_kb = get_purgeme_keyboard(chat_id, user_id, unique_id)
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
            # Content didn't change, just answer the callback to stop loading animation
            await cb.answer("Status Updated", show_alert=False)
        except Exception as inner_e:
            raise inner_e

    except Exception as e:
        Altruix.log(f"Purgeme CB Error: {e}")
        # Only alert if it's NOT MessageNotModified (which we caught above)
        if "MessageNotModified" not in str(e):
             await cb.answer("⚠️ Error updating menu", show_alert=False)

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
            await Altruix.edit_cb(cb, "🗑 <b>Purgeme Closed</b>", parse_mode=enums.ParseMode.HTML)
            await cb.answer("Message closed.", show_alert=False)
            return
        except:
            pass

    await cb.answer("Message deleted or invalid session.", show_alert=False)



@Altruix.register_on_cmd(
    ["start"],
    cmd_help={
        "help": "Start the Purgeme Bot process.",
        "usage": "/start purgeme_{unique_id}",
        "example": "/start purgeme_123456789_987654321",
        "detail": "Memulai sesi konfigurasi Purgeme via Bot Assistant. Biasanya dipanggil otomatis oleh tombol dari Userbot."
    },
    group_only=False,
    requires_input=False, 
    requires_reply=False
)
@log_errors
async def purgeme_start_handler(client: Client, message):
    from Main.utils.access_control import is_authorized_user
    
    # 1. Fallback if no arguments provided
    if len(message.command) <= 1:
        if is_authorized_user(message.from_user.id, Altruix.config.OWNER_USERS_ID, Altruix.config.SUDO_USERS_ID):
             # Only show response if authorized, otherwise ignore to prevent spam/discovery
             await message.reply(
                 f"👋 <b>Halo, {message.from_user.first_name}!</b>\n\n"
                 f"Saya adalah asisten Altruix. Gunakan tombol pada Userbot untuk mengatur Purgeme.\n"
                 f"Ketik /help untuk melihat daftar perintah yang tersedia."
             )
        return

    # 2. Process arguments
    param = message.command[1]
    if param.startswith("purgeme_"):
        unique_id = param.replace("purgeme_", "", 1)
        
        try:
            chat_id, user_id = unique_id.rsplit("_", 1)
            
            # Security: Ensure only the session owner or sudo can access
            if str(message.from_user.id) != str(user_id) and not is_authorized_user(message.from_user.id, Altruix.config.OWNER_USERS_ID, Altruix.config.SUDO_USERS_ID):
                msg = Altruix.get_string("ACCESS_DENIED")
                await message.reply(msg)
                return
            
            state = Altruix.PURGEME_STATE.get(unique_id)
            if not state:
                await message.reply("❌ Session Expired or Invalid.")
                return

            # Show Menu
            menu_text = get_purgeme_text(state)
            kb = get_purgeme_keyboard(chat_id, user_id, unique_id)
            
            await message.reply(
                menu_text,
                reply_markup=kb,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )
        except ValueError:
            await message.reply("❌ Invalid Link Format.")


