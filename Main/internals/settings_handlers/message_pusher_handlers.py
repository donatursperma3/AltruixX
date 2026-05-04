# Main/internals/settings_handlers/message_pusher_handlers.py
import html
import asyncio
import logging
import traceback
from typing import Optional, List, Dict, Any
from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton,
    InlineQuery, InlineQueryResultArticle, InputTextMessageContent, ChosenInlineResult
)
from pyrogram.enums import ParseMode
from Main.core.client import Altruix, LinkPreviewOptions
from Main.core.decorators import log_errors, iuser_check
from Main.utils.file_helpers import get_user_button_style

from .states import user_messagepusher_state
 
# ─── LOGGER ───
logger = logging.getLogger("altruix.message_pusher_handlers")
logger.setLevel(logging.INFO)

DEFAULT_PUSHER_CONFIG = {
    "delay_act": 3.0,
    "batch_act": 30,
    "ba_delay": 30,
    "targets": "",
    "quote1": True,
    "quote2": True,
    "quote3": True,
    "msg_img": True,
    "anon_adm": True
}

async def edit_cb(cb: CallbackQuery, text: str, **kwargs):
    if cb.message:
        return await cb.message.edit(text, **kwargs)
    return await cb.edit_message_text(text, **kwargs)

async def delete_cb(cb: CallbackQuery):
    if cb.message:
        return await cb.message.delete()
    # For inline messages, we can't delete, so we edit to a minimal text
    return await cb.edit_message_text("🗑️ <i>Message Deleted/Closed</i>", parse_mode=ParseMode.HTML)

async def get_pusher_ui_data(uid: int, session_index: int, page: int) -> tuple:
    state_key = f"{uid}_{session_index}"
    if state_key not in user_messagepusher_state:
        user_messagepusher_state[state_key] = {
            "session_index": session_index,
            "page": page,
            "config": DEFAULT_PUSHER_CONFIG.copy(),
            "step": "idle",
            "sub_menu": None
        }
    
    state = user_messagepusher_state[state_key]
    config = state["config"]
    sub_menu = state.get("sub_menu")
    user_style = get_user_button_style(uid)

    text = (
        f"<blockquote expandable>"
        "<b>🚀 Message Pusher Dashboard</b>\n\n"
        f"• <b>Delay Act:</b> <code>{config['delay_act']}</code>s\n"
        f"• <b>Batch Act:</b> <code>{config['batch_act']}</code>\n"
        f"• <b>BA Delay:</b> <code>{config['ba_delay']}</code>s\n"
        f"• <b>Targets:</b> <code>{len(config['targets'].split()) if config['targets'] else 0}</code> chats\n\n"
        "<b>Options:</b>\n"
        f"• LQ1: {'Yes' if config['quote1'] else 'No'} | "
        f"LQ2: {'Yes' if config['quote2'] else 'No'}\n"
        f"• LQ3: {'Yes' if config['quote3'] else 'No'} | "
        f"IMG: {'Yes' if config['msg_img'] else 'No'}\n"
        f"• ANON ADM: {'Yes' if config['anon_adm'] else 'No'}"
        f"</blockquote>"
    )

    if not sub_menu:
        buttons = [
            [
                InlineKeyboardButton(f"Act Delay: {config['delay_act']}s", callback_data=f"mp_submenu_delay_act_{session_index}", style=user_style),
                InlineKeyboardButton(f"Batch Act: {config['batch_act']}", callback_data=f"mp_submenu_batch_act_{session_index}", style=user_style)
            ],
            [
                InlineKeyboardButton(f"BA Delay: {config['ba_delay']}s", callback_data=f"mp_submenu_ba_delay_{session_index}", style=user_style),
                InlineKeyboardButton("Set Targets", callback_data=f"mp_set_targets_{session_index}", style=user_style)
            ],
            [
                InlineKeyboardButton("View Targets", callback_data=f"mp_submenu_view_targets_{session_index}", style=user_style)
            ],
            [
                InlineKeyboardButton(f"LQ1: {'Yes' if config['quote1'] else 'No'}", callback_data=f"mp_toggle_quote1_{session_index}", style=user_style),
                InlineKeyboardButton(f"LQ2: {'Yes' if config['quote2'] else 'No'}", callback_data=f"mp_toggle_quote2_{session_index}", style=user_style)
            ],
            [
                InlineKeyboardButton(f"LQ3: {'Yes' if config['quote3'] else 'No'}", callback_data=f"mp_toggle_quote3_{session_index}", style=user_style),
                InlineKeyboardButton(f"IMG: {'Yes' if config['msg_img'] else 'No'}", callback_data=f"mp_toggle_msg_img_{session_index}", style=user_style)
            ],
            [
                InlineKeyboardButton(f"Anon Adm: {'Yes' if config['anon_adm'] else 'No'}", callback_data=f"mp_toggle_anon_adm_{session_index}", style=user_style),
            ],
            [
                InlineKeyboardButton("SEND MSG", callback_data=f"mp_run_{session_index}", style=user_style),
                InlineKeyboardButton("Close", callback_data=f"mp_cancel_{session_index}", style=user_style)
            ]
        ]
    elif sub_menu == "delay_act":
        buttons = [
            [InlineKeyboardButton("━━ Adjust Act Delay ━━", callback_data="mp_ignore", style=user_style)],
            [
                InlineKeyboardButton("-1s", callback_data=f"mp_adj_delay_act_dec_{session_index}", style=user_style),
                InlineKeyboardButton(f"Delay: {config['delay_act']}s", callback_data="mp_ignore", style=user_style),
                InlineKeyboardButton("+1s", callback_data=f"mp_adj_delay_act_inc_{session_index}", style=user_style)
            ],
            [
                InlineKeyboardButton("-0.1s", callback_data=f"mp_adj_delay_act_dec_small_{session_index}", style=user_style),
                InlineKeyboardButton("+0.1s", callback_data=f"mp_adj_delay_act_inc_small_{session_index}", style=user_style)
            ],
            [InlineKeyboardButton("Back", callback_data=f"mp_back_{session_index}", style=user_style)]
        ]
    elif sub_menu == "batch_act":
        buttons = [
            [InlineKeyboardButton("━━ Adjust Batch Size ━━", callback_data="mp_ignore", style=user_style)],
            [
                InlineKeyboardButton("-5", callback_data=f"mp_adj_batch_act_dec_{session_index}", style=user_style),
                InlineKeyboardButton(f"Batch: {config['batch_act']}", callback_data="mp_ignore", style=user_style),
                InlineKeyboardButton("+5", callback_data=f"mp_adj_batch_act_inc_{session_index}", style=user_style)
            ],
            [
                InlineKeyboardButton("-1", callback_data=f"mp_adj_batch_act_dec_small_{session_index}", style=user_style),
                InlineKeyboardButton("+1", callback_data=f"mp_adj_batch_act_inc_small_{session_index}", style=user_style)
            ],
            [InlineKeyboardButton("Back", callback_data=f"mp_back_{session_index}", style=user_style)]
        ]
    elif sub_menu == "ba_delay":
        buttons = [
            [InlineKeyboardButton("━━ Adjust BA Delay ━━", callback_data="mp_ignore", style=user_style)],
            [
                InlineKeyboardButton("-30s", callback_data=f"mp_adj_ba_delay_dec_{session_index}", style=user_style),
                InlineKeyboardButton(f"BA Delay: {config['ba_delay']}s", callback_data="mp_ignore", style=user_style),
                InlineKeyboardButton("+30s", callback_data=f"mp_adj_ba_delay_inc_{session_index}", style=user_style)
            ],
            [
                InlineKeyboardButton("-5s", callback_data=f"mp_adj_ba_delay_dec_small_{session_index}", style=user_style),
                InlineKeyboardButton("+5s", callback_data=f"mp_adj_ba_delay_inc_small_{session_index}", style=user_style)
            ],
            [InlineKeyboardButton("Back", callback_data=f"mp_back_{session_index}", style=user_style)]
        ]
    elif sub_menu == "view_targets":
        targets = config["targets"].split()
        target_list = "\n".join([f"{i+1}. <code>{t}</code>" for i, t in enumerate(targets)]) if targets else "Empty"
        
        text = (
            "<b>🎯 Target List</b>\n\n"
            f"{target_list}\n\n"
            "<i>Klik tombol di bawah untuk kembali.</i>"
        )
        buttons = [
            [InlineKeyboardButton("Clear All", callback_data=f"mp_clear_targets_{session_index}", style=user_style)],
            [InlineKeyboardButton("Back", callback_data=f"mp_back_{session_index}", style=user_style)]
        ]
    return text, InlineKeyboardMarkup(buttons)

async def show_pusher_ui(c: Client, cb: Optional[CallbackQuery], session_index: int, page: int, user_id: int = None, message: Message = None):
    uid = user_id or (cb.from_user.id if cb else None)
    if not uid: return

    text, markup = await get_pusher_ui_data(uid, session_index, page)
    
    try:
        if cb:
            await edit_cb(cb, text, reply_markup=markup, parse_mode=ParseMode.HTML)
        elif message:
            await message.edit(text, reply_markup=markup, parse_mode=ParseMode.HTML)
    except Exception as e:
        error_tb = traceback.format_exc()
        logger.error(f"Error in show_pusher_ui: {e}\n{error_tb}")
        if cb: await cb.answer(f"❌ Error: {e}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^mp_submenu_(\w+)_(\d+)$"))
@iuser_check
@log_errors
async def mp_submenu_handler(c: Client, cb: CallbackQuery):
    key, session_index = cb.matches[0].group(1), int(cb.matches[0].group(2))
    uid = cb.from_user.id
    state_key = f"{uid}_{session_index}"
    if state_key not in user_messagepusher_state: return await cb.answer("Expired", show_alert=True)
    
    user_messagepusher_state[state_key]["sub_menu"] = key
    await show_pusher_ui(c, cb, session_index, 1)
    await cb.answer(f"Opening {key}")

@Altruix.bot.on_callback_query(filters.regex(r"^mp_clear_targets_(\d+)$"))
@iuser_check
@log_errors
async def mp_clear_targets_handler(c: Client, cb: CallbackQuery):
    session_index = int(cb.matches[0].group(1))
    uid = cb.from_user.id
    state_key = f"{uid}_{session_index}"
    if state_key not in user_messagepusher_state: return await cb.answer("Expired", show_alert=True)
    
    user_messagepusher_state[state_key]["config"]["targets"] = ""
    await show_pusher_ui(c, cb, session_index, 1)
    await cb.answer("Targets cleared", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^mp_adj_(delay_act|batch_act|ba_delay)_(inc|dec)(_small)?_(\d+)$"))
@iuser_check
@log_errors
async def mp_adjust_handler(c: Client, cb: CallbackQuery):
    key, action, is_small, session_index = cb.matches[0].group(1), cb.matches[0].group(2), cb.matches[0].group(3), int(cb.matches[0].group(4))
    uid = cb.from_user.id
    state_key = f"{uid}_{session_index}"
    if state_key not in user_messagepusher_state: return await cb.answer("Expired", show_alert=True)
    
    config = user_messagepusher_state[state_key]["config"]
    
    # Logic for step size
    if key == "delay_act":
        step = 0.1 if is_small else 1.0
    elif key == "batch_act":
        step = 1 if is_small else 5
    elif key == "ba_delay":
        step = 5 if is_small else 30
    else:
        step = 1
        
    if action == "inc" or action == "add":
        config[key] = round(config[key] + step, 1)
    else:
        config[key] = max(0.1 if key == "delay_act" else 1, round(config[key] - step, 1))
        
    await show_pusher_ui(c, cb, session_index, 1)
    await cb.answer(f"{key}: {config[key]}")

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_adj_(delay_act|batch_act|ba_delay)_(inc|dec|add|sub)(_small)?_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_adj_compatibility_handler(c: Client, cb: CallbackQuery):
    # This acts as a bridge because we used 'creategroup_adj_' in the message pusher UI builder
    key, action, is_small, session_index = cb.matches[0].group(1), cb.matches[0].group(2), cb.matches[0].group(3), int(cb.matches[0].group(4))
    uid = cb.from_user.id
    state_key = f"{uid}_{session_index}"
    if state_key not in user_messagepusher_state: return await cb.answer("Expired", show_alert=True)
    
    config = user_messagepusher_state[state_key]["config"]
    
    if key == "delay_act": step = 0.1 if is_small else 1.0
    elif key == "batch_act": step = 1 if is_small else 5
    elif key == "ba_delay": step = 5 if is_small else 30
    else: step = 1
        
    if action in ["inc", "add"]:
        config[key] = round(config[key] + step, 1)
    else:
        config[key] = max(0.1 if key == "delay_act" else 1, round(config[key] - step, 1))
        
    await show_pusher_ui(c, cb, session_index, 1)
    await cb.answer(f"{key}: {config[key]}")

@Altruix.bot.on_callback_query(filters.regex(r"^mp_ignore$") | filters.regex(r"^noop$"))
async def mp_ignore_handler(c: Client, cb: CallbackQuery):
    await cb.answer("Info: Nilai ini diatur melalui tombol di sampingnya.", show_alert=False)

@Altruix.bot.on_callback_query(filters.regex(r"^mp_toggle_(\w+)_(\d+)$"))
@iuser_check
@log_errors
async def mp_toggle_handler(c: Client, cb: CallbackQuery):
    key, session_index = cb.matches[0].group(1), int(cb.matches[0].group(2))
    uid = cb.from_user.id
    state_key = f"{uid}_{session_index}"
    if state_key not in user_messagepusher_state: return await cb.answer("Expired", show_alert=True)
    
    user_messagepusher_state[state_key]["config"][key] = not user_messagepusher_state[state_key]["config"][key]
    await show_pusher_ui(c, cb, session_index, 1)
    await cb.answer("Toggled")

@Altruix.bot.on_callback_query(filters.regex(r"^mp_set_targets_(\d+)$"))
@iuser_check
@log_errors
async def mp_set_targets_handler(c: Client, cb: CallbackQuery):
    session_index = int(cb.matches[0].group(1))
    uid = cb.from_user.id
    state_key = f"{uid}_{session_index}"
    user_messagepusher_state[state_key]["step"] = "awaiting_targets"
    user_style = get_user_button_style(uid)
    
    buttons = [[InlineKeyboardButton("Back", callback_data=f"mp_back_{session_index}", style=user_style)]]
    
    await edit_cb(cb, 
        "<b>🎯 Set Targets</b>\n\n"
        "Kirim daftar Chat ID atau Username (pisahkan dengan spasi).\n"
        "Contoh: <code>@chat1 -100123456789 @chat2</code>\n\n"
        "<i>Atau klik tombol di bawah untuk batal.</i>", 
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )
    await cb.answer()

@Altruix.bot.on_callback_query(filters.regex(r"^mp_run_(\d+)$"))
@iuser_check
@log_errors
async def mp_run_handler(c: Client, cb: CallbackQuery):
    session_index = int(cb.matches[0].group(1))
    uid = cb.from_user.id
    state_key = f"{uid}_{session_index}"
    if state_key not in user_messagepusher_state: return await cb.answer("Expired", show_alert=True)
    config = user_messagepusher_state[state_key]["config"]
    
    targets = config["targets"].replace(",", " ").replace(";", " ").split()
    if not targets:
        return await cb.answer("❌ Harap tentukan target terlebih dahulu!", show_alert=True)
    
    user_style = get_user_button_style(uid)
    buttons = [
        [
            InlineKeyboardButton("✅ Yes, Start", callback_data=f"mp_confirm_run_{session_index}", style=user_style),
            InlineKeyboardButton("❌ No, Back", callback_data=f"mp_back_{session_index}", style=user_style)
        ]
    ]
    
    await edit_cb(cb,
        f"⚠️ <b>Confirmation</b>\n\n"
        f"Anda akan mengirim pesan ke <b>{len(targets)}</b> target.\n"
        f"Pastikan pengaturan sudah benar.\n\n"
        f"Apakah Anda yakin ingin memulai?",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )
    await cb.answer()

@Altruix.bot.on_callback_query(filters.regex(r"^mp_confirm_run_(\d+)$"))
@iuser_check
@log_errors
async def mp_confirm_run_handler(c: Client, cb: CallbackQuery):
    session_index = int(cb.matches[0].group(1))
    uid = cb.from_user.id
    state_key = f"{uid}_{session_index}"
    if state_key not in user_messagepusher_state: return await cb.answer("Expired", show_alert=True)
    config = user_messagepusher_state[state_key]["config"]
    targets = config["targets"].replace(",", " ").replace(";", " ").split()

    await edit_cb(cb, "<b>🚀 Task Started!</b>\n\nCek progress di Log Group.", parse_mode=ParseMode.HTML)
    
    from Main.plugins.userbot.xmessage_pusher import messagepusher_loop
    user_client = Altruix.clients[session_index]
    
    asyncio.create_task(messagepusher_loop(
        user_client, c, targets, config["delay_act"], config["batch_act"], config["ba_delay"],
        {
            "quote1": config["quote1"], 
            "quote2": config["quote2"], 
            "quote3": config["quote3"], 
            "msg_img": config["msg_img"],
            "anon_adm": config["anon_adm"]
        },
        cb.message, uid
    ))
    await cb.answer("Task started")

@Altruix.bot.on_callback_query(filters.regex(r"^mp_back_(\d+)$"))
@iuser_check
@log_errors
async def mp_back_handler(c: Client, cb: CallbackQuery):
    session_index = int(cb.matches[0].group(1))
    uid = cb.from_user.id
    state_key = f"{uid}_{session_index}"
    if state_key in user_messagepusher_state:
        user_messagepusher_state[state_key]["sub_menu"] = None
        user_messagepusher_state[state_key]["step"] = "idle"
    await show_pusher_ui(c, cb, session_index, 1)
    await cb.answer("Back to dashboard")

@Altruix.bot.on_callback_query(filters.regex(r"^mp_cancel_(\d+)$"))
@iuser_check
@log_errors
async def mp_cancel_handler(c: Client, cb: CallbackQuery):
    session_index = int(cb.matches[0].group(1))
    from Main.plugins.userbot.xmessage_pusher import MESSAGEPUSHER_TASKS
    try:
        user_client = Altruix.clients[session_index]
        user_info = await user_client.get_me()
        userbot_id = user_info.id
        task_id = f"messagepusher_{userbot_id}"
    except:
        task_id = None

    if task_id and task_id in MESSAGEPUSHER_TASKS:
        MESSAGEPUSHER_TASKS[task_id]["running"] = False
        await cb.answer("Task stopping...", show_alert=True)
    else:
        await cb.answer("No active task for this session", show_alert=True)
    await delete_cb(cb)

# Handler for input targets
@Altruix.bot.on_message(filters.private & filters.text & ~filters.command(["cancel"]))
async def mp_input_handler(c: Client, m: Message):
    if not m.from_user:
        return await m.continue_propagation()  # Safety: let others handle if no from_user
    uid = m.from_user.id
    # Find active state for this user that is awaiting targets
    active_key = None
    for key, state in user_messagepusher_state.items():
        if key.startswith(f"{uid}_") and state.get("step") == "awaiting_targets":
            active_key = key
            break
            
    if active_key:
        state = user_messagepusher_state[active_key]
        state["config"]["targets"] = m.text
        state["step"] = "idle"
        await m.reply("✅ Targets updated.")
        await show_pusher_ui(c, None, state["session_index"], 1, user_id=uid, message=m)
    else:
        # ✅ CRITICAL FIX: Continue propagation so other handlers (like security verification) can receive this input.
        await m.continue_propagation()

# ==================== INLINE HANDLERS ====================
@Altruix.bot.on_inline_query(filters.regex(r"^pushmsg_(\d+)(?:_(\d+))?"))
@iuser_check
@log_errors
async def pusher_inline_handler(c: Client, iq: InlineQuery):
    index = int(iq.matches[0].group(1))
    page = int(iq.matches[0].group(2)) if iq.matches[0].group(2) else 1
    
    text, markup = await get_pusher_ui_data(iq.from_user.id, index, page)
    
    results = [
        InlineQueryResultArticle(
            id=f"mp_{index}",
            title="Message Pusher Dashboard",
            description="Manage message pushing tasks",
            input_message_content=InputTextMessageContent(
                message_text=text,
                parse_mode=ParseMode.HTML,
                link_preview_options=LinkPreviewOptions(is_disabled=True)
            ),
            reply_markup=markup
        )
    ]
    await iq.answer(results=results, cache_time=0, is_personal=True)

@Altruix.bot.on_chosen_inline_result(filters.regex(r"^mp_(\d+)"))
async def pusher_chosen_handler(c: Client, cir: ChosenInlineResult):
    uid = cir.from_user.id
    index = int(cir.matches[0].group(1))
    state_key = f"{uid}_{index}"
    if state_key in user_messagepusher_state:
        user_messagepusher_state[state_key]["inline_message_id"] = cir.inline_message_id
