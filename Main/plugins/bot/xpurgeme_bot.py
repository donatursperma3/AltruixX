
"""
Purgeme Bot Plugin
Handles the interactive UI for the Userbot Purgeme command.
"""

import re
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.errors import MessageNotModified
from pyrogram.types import (
    InlineQuery, InlineQueryResultArticle, InputTextMessageContent,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)
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

    # Common Header for active states
    header = f"{title}\n" \
             f"<b>Mode:</b> {mode.capitalize()} | <b>Type:</b> {types[0].upper() if types else 'ALL'}\n" \
             f"<b>Target:</b> {count} messages\n" \
             f"<b>Chat:</b> {chat_name}\n" \
             f"<b>Account:</b> {account_name}"
        
    if status == "collecting":
        status_line = f"🔎 <b>Collecting...</b>\nFound: {processed}/{count}\nScanned: {scanned}"
        return f"{header}\n\n{status_line}"

    elif status == "running":
        status_line = f"🗑 <b>Deleting...</b>\nDeleted: {processed}/{count}"
        if delay > 0: status_line += f"\nDelay: {delay}s"
        return f"{header}\n\n{status_line}"

    elif status == "paused":
        status_line = f"⏸ <b>PAUSED</b>\nDeleted: {processed}/{count}"
        return f"{header}\n\n{status_line}"

    elif status == "finished":
        start_time = state.get("start_time", 0)
        duration = time.time() - start_time if start_time > 0 else 0
        return f"{title}\n\n✅ <b>Finished!</b>\nDeleted: {processed} messages\nTime: {round(duration, 2)}s\nChat: {chat_name}\nAccount: {account_name}"

    elif status == "cancelled":
        lbl = loc("purgeme_cancelled") or "❌ Cancelled"
        return f"{title}\n\n{lbl}"
        
    return title

def get_purgeme_keyboard(chat_id, user_id, unique_id):
    state = Altruix.PURGEME_STATE.get(unique_id)
    if not state:
        return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Session Ended", callback_data="purgeme_close")]])

    status = state["status"]
    count = state["count"]
    delay = state["delay"]
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
        notify_active = state.get("notify", True)
        notif_lbl = f"Notif: {'Yes' if notify_active else 'No'}"
        buttons.append([
            InlineKeyboardButton(notif_lbl, callback_data="noop"),
            InlineKeyboardButton(f"{'✅' if notify_active else '☑️'} Yes", callback_data=f"pg_notify_yes_{unique_id}"),
            InlineKeyboardButton(f"{'✅' if not notify_active else '☑️'} No", callback_data=f"pg_notify_no_{unique_id}"),
        ])
        
        # Type Toggles
        type_row_1 = []
        all_active = "✅" if "all" in types else "☑️"
        type_row_1.append(InlineKeyboardButton(f"{all_active} All", callback_data=f"pg_typ_all_{unique_id}"))
        
        img_active = "✅" if "image" in types else "☑️"
        type_row_1.append(InlineKeyboardButton(f"{img_active} Img", callback_data=f"pg_typ_image_{unique_id}"))
        
        vid_active = "✅" if "video" in types else "☑️"
        type_row_1.append(InlineKeyboardButton(f"{vid_active} Vid", callback_data=f"pg_typ_video_{unique_id}"))
        
        buttons.append(type_row_1)

        type_row_2 = []
        txt_active = "✅" if "text" in types else "☑️"
        type_row_2.append(InlineKeyboardButton(f"{txt_active} Txt", callback_data=f"pg_typ_text_{unique_id}"))

        aud_active = "✅" if "audio" in types else "☑️"
        type_row_2.append(InlineKeyboardButton(f"{aud_active} Aud", callback_data=f"pg_typ_audio_{unique_id}"))

        stk_active = "✅" if "sticker" in types else "☑️"
        type_row_2.append(InlineKeyboardButton(f"{stk_active} Stk", callback_data=f"pg_typ_sticker_{unique_id}"))
        
        buttons.append(type_row_2)
        
        # Row 3: Gif, File, VNote
        type_row_3 = []
        gif_active = "✅" if "gif" in types else "☑️"
        type_row_3.append(InlineKeyboardButton(f"{gif_active} Gif", callback_data=f"pg_typ_gif_{unique_id}"))

        file_active = "✅" if "file" in types else "☑️"
        type_row_3.append(InlineKeyboardButton(f"{file_active} File", callback_data=f"pg_typ_file_{unique_id}"))

        vnote_active = "✅" if "vnote" in types else "☑️"
        type_row_3.append(InlineKeyboardButton(f"{vnote_active} VN", callback_data=f"pg_typ_vnote_{unique_id}"))
        
        buttons.append(type_row_3)
        
        # Action Buttons
        start_lbl = loc("purgeme_start_purge", "🚀 Start Purge")
        cancel_lbl = loc("purgeme_cancel_purge", "❌ Cancel")
        buttons.append([
            InlineKeyboardButton(start_lbl, callback_data=f"pg_start_{unique_id}"),
            InlineKeyboardButton(cancel_lbl, callback_data=f"pg_cancel_{unique_id}"),
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
        if str(query.from_user.id) != str(user_id) and not is_authorized_user(query.from_user.id, Altruix.config.OWNER_ID, Altruix.config.SUDO_USERS):
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
        "typ": 3, "start": 2, "cancel": 2, "stop": 2, "pause": 2,
        "resume": 2, "refresh": 2, "mode": 3, "notify": 3, "abort": 2
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
        if str(cb.from_user.id) != str(user_id) and not is_authorized_user(cb.from_user.id, Altruix.config.OWNER_ID, Altruix.config.SUDO_USERS):
            unauth = Altruix.get_string("access_denied") or "🚫 Access Denied"
            return await cb.answer(unauth, show_alert=True)
    except (ValueError, IndexError):
        return await cb.answer("❌ Invalid Session ID.", show_alert=True)

    state = Altruix.PURGEME_STATE.get(unique_id)
    if not state:
         return await cb.answer("⚠️ Session not found. It may have finished or timed out.", show_alert=True)

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

        elif "notify_" in data:
            option = parts[2]
            state["notify"] = (option == "yes")

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

        elif "start" in data:
            if not state["event"].is_set(): 
                state["event"].set()
                # Immediate Feedback
                title = Altruix.get_string("purgeme_title") or "🗑 <b>Userbot Purgeme</b>"
                
                # IMPORTANT: Ensure persistent message tracking for deletion later
                if cb.message:
                    state["dashboard_msg_id"] = cb.message.id
                    state["dashboard_chat_id"] = cb.message.chat.id
                    
                await cb.edit_message_text(
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
            await cb.edit_message_text(f"{title}\n❌ <b>Task Cancelled / Aborted</b>")
            await asyncio.sleep(3)
            try:
                await cb.message.delete()
            except: pass
            return # Prevent further processing

        elif "cancel" in data:
            state["status"] = "cancelled"
            state["event"].set()
            state["stop_event"].set()
            try:
                await cb.message.delete()
            except: pass
            return # Prevent further processing

        elif "stop" in data:
            state["stop_event"].set()

        elif "pause" in data:
            state["status"] = "paused"
            state["pause_event"].clear()

        elif "resume" in data:
            state["status"] = "running"
            state["pause_event"].set()

        elif "refresh" in data:
            pass

        # General Keyboard Update
        new_kb = get_purgeme_keyboard(chat_id, user_id, unique_id)
        new_text = get_purgeme_text(state)
        
        try:
            await cb.edit_message_text(
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
    if cb.message:
        try:
            await cb.message.delete()
            return
        except:
            pass

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
            await cb.edit_message_text("🗑 <b>Purgeme Closed</b>", parse_mode=enums.ParseMode.HTML)
            await cb.answer("Message close requested.", show_alert=False)
            return
        except:
            pass

    await cb.answer("Message already deleted or not found.", show_alert=True)

@Altruix.bot.on_message(filters.command("start") & filters.private & filters.regex(r"purgeme_"))
async def purgeme_start_handler(client: Client, message):
    try:
        if len(message.command) > 1:
            param = message.command[1]
            if param.startswith("purgeme_"):
                unique_id = param.replace("purgeme_", "", 1)
                
                try:
                    chat_id, user_id = unique_id.rsplit("_", 1)
                    from Main.utils.access_control import is_authorized_user
                    if str(message.from_user.id) != str(user_id) and not is_authorized_user(message.from_user.id, Altruix.config.OWNER_ID, Altruix.config.SUDO_USERS):
                        msg = Altruix.get_string("access_denied") or "🚫 Access Denied"
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
    except Exception as e:
        Altruix.log(f"Purgeme Start Error: {e}")

