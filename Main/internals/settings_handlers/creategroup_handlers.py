# Main/internals/settings_handlers/creategroup_handlers.py
import html
import asyncio
from typing import Optional
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from Main.core.decorators import log_errors, iuser_check
from Main.core.client import Altruix
from pyrogram.enums import ParseMode

from .states import user_creategroup_state

# Default Configuration
DEFAULT_CREATEGROUP_CONFIG = {
    "delay": 333, "count": 2, "batch_delay": 10, "batch_size": 2, "action_delay": 3.0,
    "pattern": "Group (index)", "username": None, "description": "Powered by @AlphaXProject",
    "bots": "@MissRose_bot @simixbot @Spillgame_bot @truthordaresbot @truthordares_bot @truthordarerp_bot @truthordarerln_bot @truthordares18_bot",
    "invite_bots": False, "anon_mode": True, "copy_messages": True,
    "photo_source": "source", "custom_photo_id": None
}

from Main.utils.file_helpers import get_user_button_style

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_menu_(\d+)(?:_(\d+))?$"))
@iuser_check
@log_errors
async def creategroup_menu_handler(c: Client, cb: CallbackQuery):
    """
    Entry point for the CreateGroup settings menu. 
    Allows users to choose between manual command input or an interactive UI configuration.
    """
    await cb.answer()
    
    session_index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2)) if cb.matches[0].group(2) else 1
    
    # Resolve user_style for the session owner
    from Main.internals.settings_handlers.custom_alert_handlers import _get_session_user_id
    session_user_id = _get_session_user_id(session_index)
    user_style = get_user_button_style(session_user_id)
    
    text = (
        "<b>🚀 Create Group</b>\n\n"
        "Pilih metode input konfigurasi:\n"
        "• <b>Manual Input:</b> Ketik perintah lengkap\n"
        "• <b>Interactive UI:</b> Gunakan tombol menu"
    )
    
    buttons = [
        [InlineKeyboardButton("⌨️ Manual Input", callback_data=f"creategroup_manual_{session_index}_{page}", style=user_style)],
        [InlineKeyboardButton("🎛️ Interactive UI", callback_data=f"creategroup_ui_{session_index}_{page}", style=user_style)],
        [InlineKeyboardButton("🔙 Back to Session", callback_data=f"session_info_{session_index}_{page}", style=user_style)]
    ]
    
    if cb.message:
        await cb.message.edit(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
    else:
        await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_manual_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_manual_handler(c: Client, cb: CallbackQuery):
    await cb.answer()
    session_index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    
    # Resolve user_style
    from Main.internals.settings_handlers.custom_alert_handlers import _get_session_user_id
    session_user_id = _get_session_user_id(session_index)
    user_style = get_user_button_style(session_user_id)
    
    user_creategroup_state[cb.from_user.id] = {
        "step": "input_manual",
        "session_index": session_index,
        "page": page
    }
    
    text = (
        "<b>⌨️ Create Group - Manual Input</b>\n\n"
        "Format: <code>&lt;delay&gt; &lt;count&gt; &lt;batch_delay&gt; &lt;batch_size&gt; &lt;type&gt; &lt;pattern&gt; ; &lt;username&gt; &lt;bots&gt;</code>\n\n"
        "<b>Placeholders Pattern:</b>\n"
        "• <code>(index)</code> : Urutan\n"
        "• <code>(tahun)</code> : 2 digit tahun\n"
        "• <code>(bulan)</code> : Bulan (angka)\n"
        "• <code>(tanggal)</code>: Tanggal\n\n"
        "Ketik /cancel untuk kembali."
    )
    if cb.message:
        await cb.message.edit(text, parse_mode=ParseMode.HTML, 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"creategroup_menu_{session_index}_{page}", style=user_style)]]))
    else:
        await cb.edit_message_text(text, parse_mode=ParseMode.HTML, 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"creategroup_menu_{session_index}_{page}", style=user_style)]]))

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_ui_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_ui_handler(c: Client, cb: CallbackQuery):
    """
    Interactive UI configuration for CreateGroup.
    Loads existing configuration or defaults and renders the adjustment menu.
    Handles task state checking to prevent multiple overlapping tasks.
    """
    await cb.answer()
    session_index = int(cb.matches[0].group(1))
    page = int(cb.matches[0].group(2))
    await show_creategroup_ui(c, cb, session_index, page)

async def show_creategroup_ui(c: Client, cb: CallbackQuery, session_index: int, page: int):
    user_id = cb.from_user.id
    
    # Check if task is already running
    from Main.plugins.userbot.xcreategroup import CREATEGROUP_TASKS
    task = CREATEGROUP_TASKS.get(f"creategroup_{user_id}")
    if task and task.get("running"):
        await render_creategroup_running_ui(cb, task, session_index, page)
        return

    if user_id not in user_creategroup_state or user_creategroup_state[user_id].get("step") != "ui_config":
        if user_id in user_creategroup_state and user_creategroup_state[user_id].get("prompt_msg_id"):
            try:
                if cb.message:
                    await c.delete_messages(cb.message.chat.id, user_creategroup_state[user_id]["prompt_msg_id"])
            except: pass
            
        user_creategroup_state[user_id] = {
            "step": "ui_config",
            "session_index": session_index,
            "page": page,
            "config": DEFAULT_CREATEGROUP_CONFIG.copy(),
            "input_mode": None,
            "ui_msg_id": cb.message.id if cb.message else None,
            "prompt_msg_id": None
        }
    else:
        user_creategroup_state[user_id]["step"] = "ui_config"
        user_creategroup_state[user_id]["input_mode"] = None
        if user_creategroup_state[user_id].get("prompt_msg_id"):
            try:
                if cb.message:
                    await c.delete_messages(cb.message.chat.id, user_creategroup_state[user_id]["prompt_msg_id"])
            except: pass
            user_creategroup_state[user_id]["prompt_msg_id"] = None
    
    await render_creategroup_ui(cb, user_creategroup_state[user_id])

async def render_creategroup_ui(cb: Optional[CallbackQuery], state: dict, message: Optional[Message] = None):
    """
    Renders the configuration menu with inline adjustment buttons.
    Displays current settings including delays, counts, batching, and bot lists.
    """
    config = state["config"]
    idx = state["session_index"]
    pg = state["page"]
    
    # Resolve user_style
    from Main.internals.settings_handlers.custom_alert_handlers import _get_session_user_id
    session_user_id = _get_session_user_id(idx)
    user_style = get_user_button_style(session_user_id)
    
    session_client = Altruix.clients[idx]
    session_user = getattr(session_client, 'myself', None)
    if not session_user:
        try: session_user = await session_client.get_me()
        except Exception: session_user = None

    session_text = ""
    if session_user:
        session_text = f"👤 <b>Account:</b> <a href='tg://user?id={session_user.id}'>{html.escape(session_user.first_name)}</a> (<code><spoiler>{session_user.id}</spoiler></code>)\n"

    photo_status = f"Source Account" if config.get('photo_source') == "source" else "Custom Photo"
    if config.get('photo_source') == "custom":
        photo_status += " ✅" if config.get('custom_photo_id') else " ❌ (No photo)"

    text = (
        "<b>🎛️ Create Group Configuration</b>\n\n"
        f"{session_text}"
        f"• <b>Action Delay:</b> {config['action_delay']}s\n"
        f"• <b>Delay:</b> {config['delay']}s\n"
        f"• <b>Count:</b> {config['count']} groups\n"
        f"• <b>Batch Delay:</b> {config['batch_delay']}m\n"
        f"• <b>Batch Size:</b> {config['batch_size']} groups\n"
        f"• <b>Name:</b> {html.escape(config['pattern'])}\n"
        f"• <b>Username:</b> {config['username'] or 'None'}\n"
        f"• <b>Description:</b> {html.escape(config['description'])}\n"
        f"• <b>Photo:</b> {photo_status}\n"
        f"• <b>Anon Admin:</b> {'Yes' if config['anon_mode'] else 'No'} | <b>Copy Msg:</b> {'Yes' if config['copy_messages'] else 'No'}\n"
        f"• <b>Invite Bots:</b> {'Yes' if config['invite_bots'] else 'No'}\n"
        f"• <b>Bot List:</b> {len(config['bots'].split() if config['bots'] else [])} bots (Default)"
    )
    
    def adj_row(label, key, unit):
        return [
            InlineKeyboardButton(f"➖", callback_data=f"creategroup_adj_{idx}_{pg}_{key}_sub", style=user_style),
            InlineKeyboardButton(f"{label}", callback_data="noop", style=user_style),
            InlineKeyboardButton(f"➕", callback_data=f"creategroup_adj_{idx}_{pg}_{key}_add", style=user_style),
            InlineKeyboardButton(f"✏️", callback_data=f"creategroup_in_{idx}_{pg}_{key}", style=user_style)
        ]

    buttons = [
        adj_row(f"Act Dly ({config['action_delay']}s)", "action_delay", "s"),
        adj_row(f"Delay ({config['delay']}s)", "delay", "s"),
        adj_row(f"Count ({config['count']})", "count", ""),
        adj_row(f"Batch ({config['batch_delay']}m)", "batch_delay", "m"),
        adj_row(f"B.Size ({config['batch_size']})", "batch_size", ""),
        [
            InlineKeyboardButton(f"Name: {config['pattern'][:15]}...", callback_data="noop", style=user_style),
            InlineKeyboardButton("✏️ Input", callback_data=f"creategroup_in_{idx}_{pg}_pattern", style=user_style)
        ],
        [
            InlineKeyboardButton(f"Username: {config['username'] or 'None'}", callback_data="noop", style=user_style),
            InlineKeyboardButton("✏️ Input", callback_data=f"creategroup_in_{idx}_{pg}_username", style=user_style)
        ],
        [
            InlineKeyboardButton(f"Desc: {config['description'][:15]}...", callback_data="noop", style=user_style),
            InlineKeyboardButton("✏️ Input", callback_data=f"creategroup_in_{idx}_{pg}_description", style=user_style)
        ],
        [
            InlineKeyboardButton(f"Photo: {'👤 Source' if config.get('photo_source') == 'source' else '🖼 Custom'}", callback_data=f"creategroup_toggle_{idx}_{pg}_photo_source", style=user_style),
            InlineKeyboardButton("📸 Upload Photo" if config.get('photo_source') == 'custom' else "➖", 
                                 callback_data=f"creategroup_upload_photo_{idx}_{pg}" if config.get('photo_source') == 'custom' else "noop", style=user_style)
        ],
        [
            InlineKeyboardButton(f"Anon Admin: {'✅ Yes' if config['anon_mode'] else '❌ No'}", callback_data=f"creategroup_toggle_{idx}_{pg}_anon_mode", style=user_style),
            InlineKeyboardButton(f"Copy Msg: {'✅ Yes' if config['copy_messages'] else '❌ No'}", callback_data=f"creategroup_toggle_{idx}_{pg}_copy_messages", style=user_style)
        ],
        [
            InlineKeyboardButton(f"Invite Bots: {'✅ Yes' if config['invite_bots'] else '❌ No'}", callback_data=f"creategroup_toggle_{idx}_{pg}_invite_bots", style=user_style)
        ],
        [
            InlineKeyboardButton(f"Bots: {len(config['bots'].split() if config['bots'] else [])} usernames", callback_data="noop", style=user_style),
            InlineKeyboardButton("✏️ Bot List", callback_data=f"creategroup_in_{idx}_{pg}_bots", style=user_style)
        ],
        [
            InlineKeyboardButton("✅ RUN TASK", callback_data=f"creategroup_run_{idx}_{pg}", style=user_style),
            InlineKeyboardButton("🔙 Back", callback_data=f"creategroup_menu_{idx}_{pg}", style=user_style)
        ]
    ]
    
    try:
        if cb:
            if cb.message:
                await cb.message.edit(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
            else:
                await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
        elif message: await message.edit(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
    except Exception: pass

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_adj_(\d+)_(\d+)_(\w+)_(\w+)$"))
@iuser_check
@log_errors
async def creategroup_adjust_handler(c: Client, cb: CallbackQuery):
    idx, pg, key, action = int(cb.matches[0].group(1)), int(cb.matches[0].group(2)), cb.matches[0].group(3), cb.matches[0].group(4)
    user_id = cb.from_user.id
    if user_id not in user_creategroup_state:
         await cb.answer("Session expired", show_alert=True)
         return
    conf = user_creategroup_state[user_id]["config"]
    steps = {"delay": 1, "count": 1, "batch_delay": 1, "batch_size": 1, "action_delay": 1}
    limits = {"delay": (1, 300), "count": (1, 1000), "batch_delay": (0, 300), "batch_size": (1, 100), "action_delay": (0, 300)}
    val = conf.get(key, 0)
    step = steps.get(key, 1)
    val = val + step if action == "add" else val - step
    min_v, max_v = limits.get(key, (0, 100))
    conf[key] = max(min_v, min(val, max_v))
    await render_creategroup_ui(cb, user_creategroup_state[user_id])
    await cb.answer()

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_in_(\d+)_(\d+)_(\w+)$"))
@iuser_check
@log_errors
async def creategroup_input_request(c: Client, cb: CallbackQuery):
    await cb.answer()
    idx, pg, field = int(cb.matches[0].group(1)), int(cb.matches[0].group(2)), cb.matches[0].group(3)
    user_id = cb.from_user.id
    if user_id not in user_creategroup_state: return
    
    from Main.internals.settings_handlers.custom_alert_handlers import _get_session_user_id
    session_user_id = _get_session_user_id(idx)
    user_style = get_user_button_style(session_user_id)
    
    user_creategroup_state[user_id].update({"input_mode": field, "step": "awaiting_input", "ui_msg_id": cb.message.id if cb.message else None})
    field_name = {"pattern": "Group Name Pattern", "username": "Username Prefix", "bots": "Bot Usernames List", "description": "Group Description"}.get(field, field.replace("_", " ").title())
    text = f"<b>📝 Awaiting Input: {field_name}...</b>\n\nSilakan lihat instruksi pada pesan di bawah."
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data=f"creategroup_ui_{idx}_{pg}", style=user_style)]])
    
    if cb.message:
        await cb.message.edit(text, reply_markup=kb)
        chat_id = cb.message.chat.id
    else:
        await cb.edit_message_text(text, reply_markup=kb)
        chat_id = cb.from_user.id
        
    prompt_text = f"<b>✏️ Input {field_name}</b>\n\n{'Current Bots: ' + user_creategroup_state[user_id]['config']['bots'] if field == 'bots' else ''}\n\nSilakan kirim bot yang diinginkan untuk di add ke group.\nKetik /cancel untuk membatalkan."
    try:
        prompt_msg = await c.send_message(chat_id, prompt_text, parse_mode=ParseMode.HTML)
        user_creategroup_state[user_id]["prompt_msg_id"] = prompt_msg.id
    except Exception as e:
        logger.error(f"Failed to send prompt in creategroup: {e}")

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_toggle_(\d+)_(\d+)_(\w+)$"))
@iuser_check
@log_errors
async def creategroup_toggle_handler(c: Client, cb: CallbackQuery):
    idx, pg, key = int(cb.matches[0].group(1)), int(cb.matches[0].group(2)), cb.matches[0].group(3)
    user_id = cb.from_user.id
    if user_id in user_creategroup_state:
        if user_creategroup_state[user_id].get("prompt_msg_id"):
            try:
                if cb.message:
                    await c.delete_messages(cb.message.chat.id, user_creategroup_state[user_id]["prompt_msg_id"])
            except: pass
            user_creategroup_state[user_id]["prompt_msg_id"] = None
        conf = user_creategroup_state[user_id]["config"]
        if key == "photo_source": conf["photo_source"] = "custom" if conf.get("photo_source") == "source" else "source"
        elif key in conf: conf[key] = not conf[key]
        await render_creategroup_ui(cb, user_creategroup_state[user_id])
    await cb.answer()

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_upload_photo_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_upload_photo_handler(c: Client, cb: CallbackQuery):
    idx, pg, user_id = int(cb.matches[0].group(1)), int(cb.matches[0].group(2)), cb.from_user.id
    if user_id not in user_creategroup_state:
        await cb.answer("State expired", show_alert=True)
        return
        
    from Main.internals.settings_handlers.custom_alert_handlers import _get_session_user_id
    session_user_id = _get_session_user_id(idx)
    user_style = get_user_button_style(session_user_id)
    
    user_creategroup_state[user_id].update({"step": "awaiting_photo", "input_mode": "custom_photo", "ui_msg_id": cb.message.id if cb.message else None})
    text = "<b>📸 Awaiting Photo Upload...</b>\n\nSilakan lihat instruksi pada pesan di bawah."
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data=f"creategroup_ui_{idx}_{pg}", style=user_style)]])
    
    if cb.message:
        await cb.message.edit(text, reply_markup=kb)
        chat_id = cb.message.chat.id
    else:
        await cb.edit_message_text(text, reply_markup=kb)
        chat_id = cb.from_user.id
        
    try:
        prompt_msg = await c.send_message(chat_id, "<b>📸 Upload Custom Photo</b>\n\nSilakan kirim atau reply pesan ini dengan foto yang ingin dijadikan profil grup.\nKetik /cancel untuk membatalkan.", parse_mode=ParseMode.HTML)
        user_creategroup_state[user_id]["prompt_msg_id"] = prompt_msg.id
    except Exception as e:
        logger.error(f"Failed to send photo prompt in creategroup: {e}")

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_run_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_run_handler(c: Client, cb: CallbackQuery):
    idx, pg, user_id = int(cb.matches[0].group(1)), int(cb.matches[0].group(2)), cb.from_user.id
    if user_id not in user_creategroup_state or "config" not in user_creategroup_state[user_id]:
        await cb.answer("Error: Invalid state", show_alert=True)
        return
        
    from Main.internals.settings_handlers.custom_alert_handlers import _get_session_user_id
    session_user_id = _get_session_user_id(idx)
    user_style = get_user_button_style(session_user_id)
    
    conf = user_creategroup_state[user_id]["config"]
    photo_text = ("👤 Source Account" if conf.get('photo_source') == 'source' else "🖼 Custom Photo") + (" ✅" if conf.get('photo_source') == 'custom' and conf.get('custom_photo_id') else "")
    text = (
        "<b>⚠️ Konfirmasi Task CreateGroup</b>\n\n"
        f"• <b>Pattern:</b> {html.escape(conf['pattern'])}\n"
        f"• <b>Jumlah:</b> {conf['count']} grup\n"
        f"• <b>Anon Admin:</b> {'Yes' if conf['anon_mode'] else 'No'}\n"
        f"• <b>Photo Source:</b> {photo_text}\n"
        f"• <b>Description:</b> {html.escape(conf.get('description', ''))}\n"
        f"• <b>Invite Bots:</b> {'Yes' if conf['invite_bots'] else 'No'} ({len(conf['bots'].split() if conf['bots'] else [])})\n\n"
        "Apakah Anda yakin ingin menjalankan task ini?"
    )
    buttons = [[InlineKeyboardButton("❌ Batal", callback_data=f"creategroup_ui_{idx}_{pg}", style=user_style), InlineKeyboardButton("✅ Ya, Jalankan", callback_data=f"creategroup_confirm_task_{idx}", style=user_style)]]
    if cb.message:
        await cb.message.edit(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
    else:
        await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_confirm_task_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_confirm_task_handler(c: Client, cb: CallbackQuery):
    idx, user_id = int(cb.matches[0].group(1)), cb.from_user.id
    if user_id not in user_creategroup_state or "config" not in user_creategroup_state[user_id]:
        await cb.answer("Error: Invalid state", show_alert=True)
        return
    conf = user_creategroup_state[user_id]["config"]
    del user_creategroup_state[user_id]
    if cb.message:
        await cb.message.edit("🚀 Memulai CreateGroup Task...")
    else:
        await cb.edit_message_text("🚀 Memulai CreateGroup Task...")
        
    try:
        from Main.plugins.userbot.xcreategroup import creategroup_loop
        if cb.message:
            control_msg = await cb.message.reply("🔄 Initializing task...")
        else:
            control_msg = await c.send_message(cb.from_user.id, "🔄 Initializing task...")
            
        executor = Altruix.clients[idx]
        bots = conf["bots"].split() if conf["bots"] else []
        asyncio.create_task(creategroup_loop(user_client=executor, bot_client=Altruix.bot, initial_message=cb.message, delay=conf["delay"], count=conf["count"], extra_delay_minutes=conf["batch_delay"], batch_size=conf["batch_size"], group_type="a", name_pattern=conf["pattern"], username_prefix=conf["username"], bot_identifiers=bots, control_message=control_msg, action_delay=conf.get("action_delay", 3.0), invite_bots=conf.get("invite_bots", False), anon_mode=conf.get("anon_mode", True), copy_messages=conf.get("copy_messages", True), description=conf.get("description", "Powered by @AlphaXProject"), photo_source=conf.get("photo_source", "source"), custom_photo_id=conf.get("custom_photo_id"), user_id=user_id))
        await cb.answer("Task started!", show_alert=True)
    except Exception as e:
        if cb.message:
            await cb.message.reply(f"❌ Error: {e}")
        else:
            await c.send_message(cb.from_user.id, f"❌ Error: {e}")

async def render_creategroup_running_ui(cb: CallbackQuery, task: dict, idx: int, pg: int):
    status = "▶️ Running"
    if task.get("paused"): status = "⏸️ Paused"
    
    # Calculate created count
    created_count = len(task.get("created_groups", []))
    total_count = task["params"]["count"]
    
    # Helper for current group name
    from Main.plugins.userbot.xcreategroup import generate_group_name
    current_name = generate_group_name(task["params"]["name_pattern"], task["current_index"])
    
    # Resolve user_style
    from Main.internals.settings_handlers.custom_alert_handlers import _get_session_user_id
    session_user_id = _get_session_user_id(idx)
    user_style = get_user_button_style(session_user_id)
    
    text = (
        "<b>📊 Progress Create Group</b>\n\n"
        f"• <b>Created:</b> {created_count}/{total_count}\n"
        f"• <b>Berhasil:</b> {created_count}\n"
        f"• <b>Current:</b> {html.escape(current_name)}\n"
        f"• <b>Status:</b> {status}"
    )
    
    buttons = [
        [
            InlineKeyboardButton("🛑 Stop", callback_data=f"creategroup_control_stop_{idx}_{pg}", style=user_style),
            InlineKeyboardButton("⏸️ Pause", callback_data=f"creategroup_control_pause_{idx}_{pg}", style=user_style),
            InlineKeyboardButton("▶️ Resume", callback_data=f"creategroup_control_resume_{idx}_{pg}", style=user_style)
        ],
        [
            InlineKeyboardButton("📋 Status Detail", callback_data=f"creategroup_status_detail_{idx}_{pg}", style=user_style),
            InlineKeyboardButton("📑 List Group", callback_data=f"creategroup_list_group_{idx}_{pg}", style=user_style)
        ],
        [
            InlineKeyboardButton("🔄 Recurring", callback_data="noop", style=user_style), # Placeholder
            InlineKeyboardButton("✏️ Edit Terakhir", callback_data="noop", style=user_style) # Placeholder
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data=f"creategroup_menu_{idx}_{pg}", style=user_style)
        ]
    ]
    
    if cb.message:
        await cb.message.edit(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
    else:
        await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_control_(stop|pause|resume)_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_control_handler(c: Client, cb: CallbackQuery):
    action, idx, pg = cb.matches[0].group(1), int(cb.matches[0].group(2)), int(cb.matches[0].group(3))
    from Main.plugins.userbot.xcreategroup import CREATEGROUP_TASKS
    task = CREATEGROUP_TASKS.get(f"creategroup_{cb.from_user.id}")
    
    # Redirect to main menu if task finished
    if not task or not task.get("running"):
        await cb.answer("Task not running", show_alert=True)
        await creategroup_ui_handler(c, cb) 
        return

    if action == "stop":
        # We need to signal the task to stop. The task checks CREATEGROUP_TASKS entry.
        task["running"] = False
        # Also wake up if paused
        if task.get("pause_event"): task["pause_event"].set()
        await cb.answer("Stopping task...")
        await asyncio.sleep(1) # Give it a moment
        await show_creategroup_ui(c, cb, idx, pg)
        
    elif action == "pause":
        if not task.get("paused"):
            task["paused"] = True
            if task.get("pause_event"): task["pause_event"].clear()
            await cb.answer("Paused!")
            await render_creategroup_running_ui(cb, task, idx, pg)
        else: await cb.answer("Already paused")
            
    elif action == "resume":
        if task.get("paused"):
            task["paused"] = False
            if task.get("pause_event"): task["pause_event"].set()
            await cb.answer("Resumed!")
            await render_creategroup_running_ui(cb, task, idx, pg)
        else: await cb.answer("Already running")

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_status_detail_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_status_detail_handler(c: Client, cb: CallbackQuery):
    idx, pg = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    from Main.plugins.userbot.xcreategroup import CREATEGROUP_TASKS
    task = CREATEGROUP_TASKS.get(f"creategroup_{cb.from_user.id}")
    
    if not task: return await cb.answer("No task running", show_alert=True)
    
    # Detailed status logic
    p = task["params"]
    text = (
        "<b>📝 Status Detail</b>\n\n"
        f"• <b>Start Time:</b> {task['start_time'].strftime('%H:%M:%S')}\n"
        f"• <b>Delay:</b> {p['delay']}s\n"
        f"• <b>Batch:</b> {p['batch_size']} groups (Delay {p['extra_delay_minutes']}m)\n"
        f"• <b>Bots:</b> {len(p['bot_identifiers'])} bots\n"
        f"• <b>Username:</b> {p['username_prefix'] or 'None'}\n"
    )
    # Resolve user_style
    from Main.internals.settings_handlers.custom_alert_handlers import _get_session_user_id
    session_user_id = _get_session_user_id(idx)
    user_style = get_user_button_style(session_user_id)
    
    await cb.answer("Full details shown", show_alert=True)
    buttons = [[InlineKeyboardButton("🔙 Back", callback_data=f"creategroup_ui_{idx}_{pg}", style=user_style)]]
    if cb.message:
        await cb.message.edit(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
    else:
        await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

@Altruix.bot.on_callback_query(filters.regex(r"^creategroup_list_group_(\d+)_(\d+)$"))
@iuser_check
@log_errors
async def creategroup_list_group_handler(c: Client, cb: CallbackQuery):
    idx, pg = int(cb.matches[0].group(1)), int(cb.matches[0].group(2))
    from Main.plugins.userbot.xcreategroup import CREATEGROUP_TASKS
    task = CREATEGROUP_TASKS.get(f"creategroup_{cb.from_user.id}")
    
    if not task: return await cb.answer("No task running", show_alert=True)
    
    groups = task.get("created_groups", [])
    if not groups:
        await cb.answer("No groups created yet", show_alert=True)
        return
        
    text = "<b>📑 List Created Groups</b>\n\n"
    for g in groups[-10:]: # Show last 10
        text += f"• {html.escape(g['name'])} (<code>{g['id']}</code>)\n"
    
    if len(groups) > 10: text += f"\n...and {len(groups)-10} more."
    
    # Resolve user_style
    from Main.internals.settings_handlers.custom_alert_handlers import _get_session_user_id
    session_user_id = _get_session_user_id(idx)
    user_style = get_user_button_style(session_user_id)
    
    buttons = [[InlineKeyboardButton("🔙 Back", callback_data=f"creategroup_ui_{idx}_{pg}", style=user_style)]]
    if cb.message:
        await cb.message.edit(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
    else:
        await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

async def process_creategroup_input(c: Client, m: Message, text: str = None):
    user_id = m.from_user.id
    state = user_creategroup_state.get(user_id)
    if not state: return
    if state["step"] == "awaiting_photo":
        if state.get("prompt_msg_id"):
            try: await c.delete_messages(m.chat.id, state["prompt_msg_id"])
            except: pass
            state["prompt_msg_id"] = None
        if m.photo:
            state["config"]["custom_photo_id"] = m.photo.file_id
            state["step"], state["input_mode"] = "ui_config", None
            if state.get("ui_msg_id"):
                try: 
                    target_msg = await c.get_messages(m.chat.id, state["ui_msg_id"])
                    await render_creategroup_ui(None, state, message=target_msg)
                except: await render_creategroup_ui(None, state)
            return
        elif text and text.lower() == "/cancel":
            state["step"], state["input_mode"] = "ui_config", None
            if state.get("ui_msg_id"):
                try:
                    target_msg = await c.get_messages(m.chat.id, state["ui_msg_id"])
                    await render_creategroup_ui(None, state, message=target_msg)
                except: await render_creategroup_ui(None, state)
            return
        else: return
    elif state["step"] == "input_manual":
        # Process manual command-like input string
        try:
            args = text.split()
            if len(args) < 6:
                await m.reply("❌ Format salah! Minimal 6 parameter.")
                return
            config = {"delay": int(args[0]), "count": int(args[1]), "batch_delay": int(args[2]), "batch_size": int(args[3]), "type": args[4].lower(), "bots": [], "username": None, "pattern": ""}
            full_args = " ".join(args[5:])
            if " ; " in full_args:
                p, e = full_args.split(" ; ", 1)
                config["pattern"] = p.strip('"\'')
                ex = e.strip().split()
                if ex:
                    if not (ex[0].startswith('@') or ex[0].isdigit()):
                         config["username"] = ex[0]
                         config["bots"] = ex[1:]
                    else: config["bots"] = ex
            else: config["pattern"] = full_args.strip('"\'')
            state["config"], state["step"] = config, "confirm_manual"
            buttons = [[InlineKeyboardButton("✅ Run", f"creategroup_run_{state['session_index']}_{state['page']}")]]
            await m.reply(f"Confirm Manual Run?\n{config}", reply_markup=InlineKeyboardMarkup(buttons))
        except Exception as e: await m.reply(f"Error: {e}")
    elif state["step"] == "awaiting_input":
        field = state["input_mode"]
        if field == "pattern": state["config"]["pattern"] = text
        elif field == "username": state["config"]["username"] = text
        elif field == "description": state["config"]["description"] = text
        elif field == "bots":
             bots = text.replace(",", " ").split()
             clean_bots = []
             for b in bots: clean_bots.append(b if (b.startswith("@") or b.isdigit()) else f"@{b}")
             state["config"]["bots"] = " ".join(clean_bots)
        elif field in ["delay", "count", "batch_delay", "batch_size", "action_delay"]:
            if text.isdigit() or (field == "action_delay" and text.replace(".", "", 1).isdigit()):
                 val = float(text) if field == "action_delay" else int(text)
                 state["config"][field] = val
            else:
                 await m.reply("❌ Input harus angka!")
                 return
        state["step"], state["input_mode"] = "ui_config", None
        if state.get("prompt_msg_id"):
            try: await c.delete_messages(m.chat.id, state["prompt_msg_id"])
            except: pass
            state["prompt_msg_id"] = None
        if state.get("ui_msg_id"):
            try:
                target_msg = await c.get_messages(m.chat.id, state["ui_msg_id"])
                await render_creategroup_ui(None, state, message=target_msg)
            except: pass
        return
