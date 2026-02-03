# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.


import re
import os
import pyrogram
import hashlib
from Main import Altruix
from typing import Optional
from platform import python_version
from pyrogram import Client, filters
from Main.core.decorators import log_errors, iuser_check
from pyrogram.types import (
    InlineQuery, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    InputTextMessageContent, InlineQueryResultArticle)


# 🗂️ Callback data cache to bypass 64-byte limit
CALLBACK_DATA_CACHE = {}

def create_callback_id(data: str) -> str:
    """Create a short hash ID for callback data and cache it."""
    # Use first 12 chars of SHA256 hash for uniqueness
    hash_id = hashlib.sha256(data.encode()).hexdigest()[:12]
    CALLBACK_DATA_CACHE[hash_id] = data
    return hash_id

def get_callback_data(hash_id: str) -> str:
    """Retrieve original callback data from hash ID."""
    return CALLBACK_DATA_CACHE.get(hash_id, "")


def get_total_plugins():
    import glob
    ub_plugins = len(glob.glob("Main/plugins/userbot/*.py"))
    bot_plugins = len(glob.glob("Main/plugins/bot/*.py"))
    return ub_plugins, bot_plugins

cache_help_menu = None
multi_pages = False


def split_help_text(text: str, max_chars: int = 1500) -> list:
    """Split help text into chunks properly, avoiding tag breakage."""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    # Split by blocks starting with <b>Command :</b>
    pattern = r"(?=<b>Command :</b>)"
    blocks = re.split(pattern, text)
    
    if len(blocks) <= 1:
        # Fallback: simple split by lines if no bold command headers found
        lines = text.split('\n')
        current_chunk = ""
        for line in lines:
            if len(current_chunk) + len(line) + 1 > max_chars:
                if current_chunk: chunks.append(current_chunk.strip())
                current_chunk = line + '\n'
            else:
                current_chunk += line + '\n'
        if current_chunk:
            chunks.append(current_chunk.strip())
        return chunks

    current_chunk = blocks[0]
    for i in range(1, len(blocks)):
        block = blocks[i]
        if len(current_chunk) + len(block) > max_chars and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = block
        else:
            current_chunk += block
            
    if current_chunk:
        chunks.append(current_chunk.strip())
        
    return [c for c in chunks if c.strip()]


@log_errors
async def get_help_menu(return_all: bool = False, user_id: int = None, chat_id: int = None, mode: str = "userbot"):
    global cache_help_menu, multi_pages
    ub_plugins, bot_plugins = get_total_plugins()
    from pyrogram.enums import ParseMode
    
    # ✅ Check for Custom Help Message
    custom_help = None
    parse_mode = ParseMode.HTML
    session_index = -1
    if user_id:
        # Find session index
        for i, cl in enumerate(Altruix.clients):
            me = getattr(cl, "me", None) or getattr(cl, "myself", None) or (await cl.get_me() if cl.is_initialized else None)
            if me and me.id == user_id:
                session_index = i
                break
        
        if session_index != -1:
            m = await Altruix.config.get_env(f"HELP_INFO_{session_index}")
            if m == "custom":
                custom_msg_type = await Altruix.config.get_env(f"HELP_INFO_TYPE_{session_index}") or "per_account"
        
                if custom_msg_type == "global":
                    custom_msg = await Altruix.config.get_env("HELP_INFO_CUSTOM_MSG_GLOBAL")
                else:
                    custom_msg = await Altruix.config.get_env(f"HELP_INFO_CUSTOM_MSG_{session_index}")
                
                if custom_msg:
                    custom_help, parse_mode = await Altruix.resolve_placeholders(custom_msg, index=session_index)

    if custom_help:
        help_msg = custom_help
    else:
        if mode == "userbot":
            title = Altruix.get_string("userbot_plugins")
        elif mode == "bot":
            title = Altruix.get_string("bot_plugins")
        else:
            title = Altruix.get_string("extra_plugins")
            
        help_msg = f"<b><u>❇️ {title}</u></b>\n\n" \
                   f"{Altruix.get_string('help_tabs_desc')}\n\n" \
                   f"<b>Userbot version :</b> <code>V{Altruix.__version__}</code>\n" \
                   f"<b>Userbot Plugins :</b> <code>{ub_plugins}</code>\n" \
                   f"<b>Bot Plugins :</b> <code>{bot_plugins}</code>\n" \
                   f"<b>Total Commands :</b> <code>{Altruix.total_commands}</code>"


    # Filter plugins based on mode
    all_plugins = sorted(list(Altruix._command_help_message_data.keys()))
    plugins = []
    for p in all_plugins:
        p_cat = Altruix.plugin_categories.get(p, "userbot")
        if mode == "userbot" and p_cat == "userbot":
            plugins.append(p)
        elif mode == "bot" and p_cat == "bot":
            plugins.append(p)
        elif mode == "extra" and p_cat in ["extra", "other"]:
            plugins.append(p)

    # 🔗 Build base callback data string
    si_str = f"?page=0&si={session_index}" if session_index != -1 else f"?page=0&si=-1"
    if chat_id:
        si_str += f"&cid={chat_id}"
    si_str += f"&mode={mode}"
    
    # 🔗 Create compressed callback data
    ikb = []
    for plugin in plugins:
        full_data = f"help#{plugin}{si_str}"
        short_id = create_callback_id(full_data)
        ikb.append(
            InlineKeyboardButton(
                plugin.replace("_", " ").title(), 
                callback_data=f"h#{short_id}"
            )
        )
    
    # 📑 Category Tabs with compressed data
    ub_label = f"• {Altruix.get_string('userbot_plugins')} •" if mode == "userbot" else Altruix.get_string('userbot_plugins')
    bot_label = f"• {Altruix.get_string('bot_plugins')} •" if mode == "bot" else Altruix.get_string('bot_plugins')
    extra_label = f"• {Altruix.get_string('extra_plugins')} •" if mode == "extra" else Altruix.get_string('extra_plugins')
    
    ub_data = f"help_tab#userbot?si={session_index}{f'&cid={chat_id}' if chat_id else ''}"
    bot_data = f"help_tab#bot?si={session_index}{f'&cid={chat_id}' if chat_id else ''}"
    extra_data = f"help_tab#extra?si={session_index}{f'&cid={chat_id}' if chat_id else ''}"
    
    tabs = [
        InlineKeyboardButton(ub_label, callback_data=f"ht#{create_callback_id(ub_data)}"),
        InlineKeyboardButton(bot_label, callback_data=f"ht#{create_callback_id(bot_data)}"),
        InlineKeyboardButton(extra_label, callback_data=f"ht#{create_callback_id(extra_data)}")
    ]

    rows = Altruix.config.HELP_MENU_ROWS
    columns = Altruix.config.HELP_MENU_COLUMNS
    buttons = [ikb[i : i + columns] for i in range(0, len(ikb), columns)]
    
    multi_pages = False
    if len(buttons) > rows:
        buttons = [buttons[i : i + rows] for i in range(0, len(buttons), rows)]
        multi_pages = True
    
    close_data = f"close_help_{session_index}" if session_index != -1 else "close_help"
    
    if multi_pages:
        for page in buttons:
            index = buttons.index(page)
            # No need to update callback_data since we're using hash IDs
            
            # Insert Tabs at the top of each page
            page.insert(0, tabs)
            
            # Page navigation buttons with compressed data
            page_buttons = []
            for i in range(len(buttons)):
                pg_data = f"help#_page?page={i}&si={session_index}{f'&cid={chat_id}' if chat_id else ''}&mode={mode}"
                page_buttons.append(
                    InlineKeyboardButton(str(i + 1), callback_data=f"h#{create_callback_id(pg_data)}")
                )
            
            for i in page_buttons:
                if i.text == str(index + 1):
                    i.text = f"> {i.text} <"
            page.append(page_buttons)
            page.append([
                InlineKeyboardButton("Settings", "settings_menu"),
                InlineKeyboardButton("Close", close_data)
            ])
    else:
        # Wrap buttons to ensure it's a list of lists if not already (for non-multipaged)
        # Actually it's already a list of lists from [ikb[i : i + columns] ...]
        buttons.insert(0, tabs)
        buttons.append([
            InlineKeyboardButton("Settings", "settings_menu"),
            InlineKeyboardButton("Close", close_data)
        ])
        
    if multi_pages and not return_all:
        return help_msg, buttons[0], parse_mode
    return help_msg, buttons, parse_mode


@log_errors
async def get_plugin_data(plugin: str, number: int = 0, sub_page: int = 0, user_id: int = None, chat_id: int = None, mode: str = "userbot"):
    full_text = Altruix._command_help_message_data[plugin.lower()].strip()
    pages = split_help_text(full_text)
    
    # Ensure sub_page is within bounds
    if sub_page >= len(pages):
        sub_page = 0
    elif sub_page < 0:
        sub_page = len(pages) - 1
        
    text = f"<b>Help for</b> <code>{plugin}</code>"
    if len(pages) > 1:
        text += f" [Page {sub_page + 1}/{len(pages)}]"
    text += f"\n\n{pages[sub_page]}"
    
    session_index = -1
    if user_id:
        for i, cl in enumerate(Altruix.clients):
            me = getattr(cl, "me", None) or getattr(cl, "myself", None) or (await cl.get_me() if not cl.me else cl.me)
            if me and me.id == user_id:
                session_index = i
                break
                
    si_suffix = f"&si={session_index}" if session_index != -1 else "&si=-1"
    if chat_id:
        si_suffix += f"&cid={chat_id}"
    si_suffix += f"&mode={mode}"
    
    buttons = []
    
    # 📤 Relocate Send Plugin button to be above navigation/back buttons
    send_data = f"send_plugin#{plugin}?page={number}{si_suffix}"
    buttons.append([InlineKeyboardButton("📤 Send Plugin", callback_data=f"sp#{create_callback_id(send_data)}")])

    nav_buttons = []
    if len(pages) > 1:
        if sub_page > 0:
            prev_data = f"help#{plugin}?page={number}&sub={sub_page-1}{si_suffix}"
            nav_buttons.append(InlineKeyboardButton(Altruix.get_string("prev"), callback_data=f"h#{create_callback_id(prev_data)}"))
        if sub_page < len(pages) - 1:
            next_data = f"help#{plugin}?page={number}&sub={sub_page+1}{si_suffix}"
            nav_buttons.append(InlineKeyboardButton(Altruix.get_string("next"), callback_data=f"h#{create_callback_id(next_data)}"))
    
    if nav_buttons:
        buttons.append(nav_buttons)
        
    back_data = f"help#_page?page={number}{si_suffix}"
    buttons.append([InlineKeyboardButton(Altruix.get_string("back"), callback_data=f"h#{create_callback_id(back_data)}")])
    
    return text, InlineKeyboardMarkup(buttons)


@Altruix.bot.on_callback_query(filters.regex(r"^close_help(?:_(-?\d+))?"))
@log_errors
@iuser_check
async def close_help(c: Client, cq: CallbackQuery):
    session_index = cq.matches[0].group(1)
    re_open_data = f"re_open_{session_index}" if session_index else "re_open"
    await cq.edit_message_text(
        "<b>Help Menu Closed 🔐</b>",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("Re-Open", re_open_data)]]
        ),
    )


@Altruix.bot.on_inline_query(filters.regex("^change_lang", flags=re.IGNORECASE))
@log_errors
@iuser_check
async def reload_language(c: Client, iq: InlineQuery):
    bttns = [
        [
            InlineKeyboardButton(
                Altruix.all_lang_strings[lang].get("def").title() or lang.title(),
                f"reload_lang_{lang}",
            )
        ]
        for lang in Altruix.all_lang_strings.keys()
    ]
    await iq.answer(
        results=[
            InlineQueryResultArticle(
                title="Change Altruix default language",
                input_message_content=InputTextMessageContent(
                    "<b>Altruix Language Set-up Wizard</b> \n<b>Click a language available below to change Altruix's default langauge</b>"
                ),
                reply_markup=InlineKeyboardMarkup(bttns),
            )
        ]
    )


@Altruix.bot.on_callback_query(filters.regex("^reload_lang_(.*)"))
@log_errors
@iuser_check
async def change_lang(c: Client, cb: CallbackQuery):
    lang = cb.matches[0].group(1)
    if lang not in Altruix.all_lang_strings.keys():
        return await cb.answer(
            Altruix.get_string("INVALID_LANG_SELECTED"), cache_time=0, show_alert=True
        )
    if lang == Altruix.selected_lang:
        return await cb.answer(Altruix.get_string("LANG_IN_USE"))
    Altruix.selected_lang = lang
    await Altruix.config.add_env_to_db("UB_LANG", lang)
    return await cb.answer(Altruix.get_string("LANG_SELECTED"))


@Altruix.bot.on_inline_query(filters.regex(r"^help(?:_(-?\d+))? ?(.+)?", flags=re.IGNORECASE))
@log_errors
@iuser_check
async def help(_: Client, iq: InlineQuery):
    chat_id = iq.matches[0].group(1)
    plugin_or_tab: Optional[str] = iq.matches[0].group(2)
    
    cid = int(chat_id) if chat_id else None
    
    # Determine the mode (userbot or bot) from query if needed, default to userbot
    default_mode = "userbot"
    if plugin_or_tab and plugin_or_tab.startswith("tab_"):
         default_mode = plugin_or_tab.replace("tab_", "")
         plugin_or_tab = None

    if not plugin_or_tab:
        help_msg, buttons, parse_mode = await get_help_menu(user_id=iq.from_user.id, chat_id=cid, mode=default_mode)
        await iq.answer(
            results=[
                InlineQueryResultArticle(
                    title=f"Userbot Help - {default_mode.title()}",
                    input_message_content=InputTextMessageContent(help_msg, parse_mode=parse_mode),
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
            ],
            cache_time=0
        )
    elif plugin_or_tab.strip() in Altruix._command_help_message_data:
        plugin = plugin_or_tab.strip()
        # Find session index for the user triggering the inline query
        session_index = -1
        for i, cl in enumerate(Altruix.clients):
            me = getattr(cl, "me", None) or getattr(cl, "myself", None) or (await cl.get_me() if cl.is_initialized else None)
            if me and me.id == iq.from_user.id:
                session_index = i
                break
                
        text, markup = await get_plugin_data(plugin.lower(), chat_id=cid, user_id=iq.from_user.id)
        
        si_str = f"?page=0&si={session_index}" if session_index != -1 else "&si=-1"
        cid_str = f"&cid={cid}" if cid else ""
        
        await iq.answer(
            results=[
                InlineQueryResultArticle(
                    title=f"Help Module for {plugin}",
                    input_message_content=InputTextMessageContent(text),
                    reply_markup=markup if markup else InlineKeyboardMarkup(
                        [[InlineKeyboardButton("Goto help menu", f"help#_page{si_str}{cid_str}")]]
                    ),
                )
            ],
            cache_time=0
        )
    else:
        await iq.answer(
            results=[
                InlineQueryResultArticle(
                    title="Plugin not found!",
                    input_message_content=InputTextMessageContent(
                        f"Help for {plugin_or_tab} is not found!"
                    ),
                )
            ]
        )


@Altruix.bot.on_callback_query(filters.regex(r"^re_open(?:_(-?\d+))?"))
@log_errors
@iuser_check
async def re_help(c: Client, cq: CallbackQuery):
    session_idx = cq.matches[0].group(1)
    user_id = cq.from_user.id
    
    if session_idx and int(session_idx) != -1:
        idx = int(session_idx)
        if idx < len(Altruix.clients):
            cl = Altruix.clients[idx]
            me = getattr(cl, "myself", None) or await cl.get_me()
            user_id = me.id

    help_msg, buttons, parse_mode = await get_help_menu(user_id=user_id)
    await cq.edit_message_text(help_msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=parse_mode)


@Altruix.bot.on_callback_query(filters.regex(r"^ht#([a-f0-9]{12})$"))
@log_errors
@iuser_check
async def help_tab_compressed(_: Client, cq: CallbackQuery):
    """Handle compressed help tab callbacks."""
    await cq.answer()  # Instant feedback
    
    hash_id = cq.matches[0].group(1)
    original_data = get_callback_data(hash_id)
    
    if not original_data:
        return await cq.answer("⚠️ Session expired, please refresh.", show_alert=True)
    
    # Parse: help_tab#(userbot|bot)?si=X&cid=Y
    match = re.match(r"help_tab#(userbot|bot|extra)\?si=(-?\d+)(?:&cid=(-?\d+))?", original_data)
    if not match:
        return await cq.answer("⚠️ Invalid data.", show_alert=True)
    
    mode = match.group(1)
    session_idx = match.group(2)
    cid = int(match.group(3)) if match.group(3) else None
    
    user_id = cq.from_user.id
    if session_idx and int(session_idx) != -1:
        idx = int(session_idx)
        if 0 <= idx < len(Altruix.clients):
            cl = Altruix.clients[idx]
            me = getattr(cl, "myself", None) or await cl.get_me()
            user_id = me.id

    help_msg, buttons, parse_mode = await get_help_menu(user_id=user_id, chat_id=cid, mode=mode)
    await cq.edit_message_text(help_msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=parse_mode)


@Altruix.bot.on_callback_query(filters.regex(r"^h#([a-f0-9]{12})$"))
@log_errors
@iuser_check
async def help_compressed(_: Client, cq: CallbackQuery):
    """Handle compressed help callbacks."""
    await cq.answer()  # Instant feedback
    
    hash_id = cq.matches[0].group(1)
    original_data = get_callback_data(hash_id)
    
    if not original_data:
        return await cq.answer("⚠️ Session expired, please refresh.", show_alert=True)
    
    # Parse: help#plugin?page=X&sub=Y&si=Z&cid=W&mode=M OR help#_page?page=X&si=Z&cid=W&mode=M
    match = re.match(r"help#([\w_]+)\?page=(\d+)(?:&sub=(\d+))?(?:&si=(-?\d+))?(?:&cid=(-?\d+))?(?:&mode=(\w+))?", original_data)
    if not match:
        return await cq.answer("⚠️ Invalid data.", show_alert=True)
    
    text_type = match.group(1)
    number = int(match.group(2)) if match.group(2) else 0
    sub_page = int(match.group(3)) if match.group(3) else 0
    si_from_data = match.group(4)
    cid = int(match.group(5)) if match.group(5) else None
    mode = match.group(6) or "userbot"
    
    # Determine the correct user_id based on session_index (si)
    user_id = cq.from_user.id
    if si_from_data and int(si_from_data) != -1:
        idx = int(si_from_data)
        if 0 <= idx < len(Altruix.clients):
            cl = Altruix.clients[idx]
            me = getattr(cl, "me", None) or getattr(cl, "myself", None) or await cl.get_me()
            user_id = me.id

    if text_type == "_page":
        help_msg, buttons, parse_mode = await get_help_menu(return_all=True, user_id=user_id, chat_id=cid, mode=mode)
        # Handle both multi-page (list of pages) and single-page (single page) structures
        if isinstance(buttons, list) and len(buttons) > 0:
            # Check if it's multi-page structure (list of lists of lists)
            if isinstance(buttons[0], list) and len(buttons[0]) > 0 and isinstance(buttons[0][0], list):
                # Multi-page: buttons is [[page1_rows], [page2_rows], ...]
                button_markup = buttons[number] if number < len(buttons) else buttons[0]
            else:
                # Single-page: buttons is [row1, row2, ...]
                button_markup = buttons
        else:
            button_markup = buttons
            
        return await cq.edit_message_text(
            help_msg, reply_markup=InlineKeyboardMarkup(button_markup), parse_mode=parse_mode
        )

    text, buttons = await get_plugin_data(text_type, number, sub_page, user_id=user_id, chat_id=cid, mode=mode)
    await cq.edit_message_text(text, reply_markup=buttons)


@Altruix.bot.on_callback_query(filters.regex(r"^help_tab#(userbot|bot|extra)\?si=(-?\d+)(?:&cid=(-?\d+))?"))
@log_errors
@iuser_check
async def help_tab_callback(_: Client, cq: CallbackQuery):
    """Legacy handler for uncompressed tab callbacks."""
    await cq.answer()  # Instant feedback
    
    mode = cq.matches[0].group(1)
    session_idx = cq.matches[0].group(2)
    cid = int(cq.matches[0].group(3)) if cq.matches[0].group(3) else None
    
    user_id = cq.from_user.id
    if session_idx and int(session_idx) != -1:
        idx = int(session_idx)
        if 0 <= idx < len(Altruix.clients):
            cl = Altruix.clients[idx]
            me = getattr(cl, "myself", None) or await cl.get_me()
            user_id = me.id

    help_msg, buttons, parse_mode = await get_help_menu(user_id=user_id, chat_id=cid, mode=mode)
    await cq.edit_message_text(help_msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=parse_mode)


@Altruix.bot.on_callback_query(filters.regex(r"^help(?:#(\w+)\?page=(\d+)(?:&sub=(\d+))?(?:&si=(-?\d+))?(?:&cid=(-?\d+))?(?:&mode=(\w+))?)?$"))
@log_errors
@iuser_check
async def help_callback(_: Client, cq: CallbackQuery):
    """Legacy handler for uncompressed help callbacks."""
    await cq.answer()  # Instant feedback
    
    data = cq.matches[0]
    num_groups = len(data.groups())
    
    # 🕵️ Safe group access helper
    def get_group(idx):
        try:
            return data.group(idx) if num_groups >= idx else None
        except IndexError:
            return None

    si_from_data = get_group(4)
    cid = int(get_group(5)) if get_group(5) else None
    mode = get_group(6) or "userbot"
    
    # Determine the correct user_id based on session_index (si)
    user_id = cq.from_user.id
    if si_from_data and int(si_from_data) != -1:
        idx = int(si_from_data)
        if 0 <= idx < len(Altruix.clients):
            cl = Altruix.clients[idx]
            me = getattr(cl, "me", None) or getattr(cl, "myself", None) or await cl.get_me()
            user_id = me.id

    if not get_group(1):
        help_msg, buttons, parse_mode = await get_help_menu(user_id=user_id, chat_id=cid, mode=mode)
        return await cq.edit_message_text(
            help_msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=parse_mode
        )
    
    text_type = get_group(1)
    number = int(get_group(2)) if get_group(2) else 0
    sub_page = int(get_group(3)) if get_group(3) else 0

    if text_type == "_page":
        help_msg, buttons, parse_mode = await get_help_menu(return_all=True, user_id=user_id, chat_id=cid, mode=mode)
        # Handle both multi-page (list of pages) and single-page (single page) structures
        if isinstance(buttons, list) and len(buttons) > 0:
            # Check if it's multi-page structure (list of lists of lists)
            if isinstance(buttons[0], list) and len(buttons[0]) > 0 and isinstance(buttons[0][0], list):
                # Multi-page: buttons is [[page1_rows], [page2_rows], ...]
                button_markup = buttons[number] if number < len(buttons) else buttons[0]
            else:
                # Single-page: buttons is [row1, row2, ...]
                button_markup = buttons
        else:
            button_markup = buttons
            
        return await cq.edit_message_text(
            help_msg, reply_markup=InlineKeyboardMarkup(button_markup), parse_mode=parse_mode
        )

    text, buttons = await get_plugin_data(text_type, number, sub_page, user_id=user_id, chat_id=cid, mode=mode)
    await cq.edit_message_text(text, reply_markup=buttons)


@Altruix.bot.on_message(filters.command("help", Altruix.bot_handler))
@log_errors
@iuser_check
async def bot_help_handler(c: Client, m: pyrogram.types.Message):
    """Handler for bot help command (/help or .help)"""
    help_msg, buttons, parse_mode = await get_help_menu(user_id=m.from_user.id, chat_id=m.chat.id, mode="userbot")
    await m.reply(help_msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=parse_mode)


@Altruix.bot.on_callback_query(filters.regex(r"^sp#([a-f0-9]{12})$"))
@log_errors
@iuser_check
async def send_plugin_compressed(c: Client, cb: CallbackQuery):
    """Handle compressed send plugin callbacks."""
    await cb.answer()  # Instant feedback
    
    hash_id = cb.matches[0].group(1)
    original_data = get_callback_data(hash_id)
    
    if not original_data:
        return await cb.answer("⚠️ Session expired, please refresh.", show_alert=True)
    
    # Parse: send_plugin#plugin?page=X&si=Y&cid=Z&mode=W
    match = re.match(r"send_plugin#([\w_ ]+)\?page=(\d+)(?:&si=(-?\d+))?(?:&cid=(-?\d+))?(?:&mode=(\w+))?", original_data)
    if not match:
        return await cb.answer("⚠️ Invalid data.", show_alert=True)
    
    plugin = match.group(1)
    page = match.group(2)
    si = match.group(3)
    cid = match.group(4)
    mode = match.group(5) or "userbot"
    
    si_str = f"&si={si}" if si else ""
    cid_str = f"&cid={cid}" if cid else ""
    mode_str = f"&mode={mode}"
    
    # Confirmation menu
    text = (
        f"<b>📤 Konfirmasi Kirim Plugin</b>\n\n"
        f"Apakah Anda yakin ingin mengirim file kode sumber untuk plugin <code>{plugin}</code>?\n\n"
        f"<i>File ini dapat mengandung kode yang sensitif atau penting.</i>"
    )
    
    # Create compressed callback for confirmation
    yes_data = f"conf_send_pl#{plugin}#yes?page={page}{si_str}{cid_str}{mode_str}"
    no_data = f"conf_send_pl#{plugin}#no?page={page}{si_str}{cid_str}{mode_str}"
    
    buttons = [
        [
            InlineKeyboardButton("✅ Ya, Kirim", callback_data=f"csp#{create_callback_id(yes_data)}"),
            InlineKeyboardButton("❌ Tidak", callback_data=f"csp#{create_callback_id(no_data)}"),
        ]
    ]
    
    await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))


@Altruix.bot.on_callback_query(filters.regex(r"^send_plugin#([\w_ ]+)\?page=(\d+)(?:&si=(-?\d+))?(?:&cid=(-?\d+))?(?:&mode=(\w+))?"))
@log_errors
@iuser_check
async def send_plugin_confirm(c: Client, cb: CallbackQuery):
    """Legacy handler for uncompressed send plugin callbacks."""
    await cb.answer()  # Instant feedback
    
    plugin = cb.matches[0].group(1)
    page = cb.matches[0].group(2)
    si = cb.matches[0].group(3)
    cid = cb.matches[0].group(4)
    mode = cb.matches[0].group(5) or "userbot"
    
    si_str = f"&si={si}" if si else ""
    cid_str = f"&cid={cid}" if cid else ""
    mode_str = f"&mode={mode}"
    
    # Confirmation menu
    text = (
        f"<b>📤 Konfirmasi Kirim Plugin</b>\n\n"
        f"Apakah Anda yakin ingin mengirim file kode sumber untuk plugin <code>{plugin}</code>?\n\n"
        f"<i>File ini dapat mengandung kode yang sensitif atau penting.</i>"
    )
    
    buttons = [
        [
            InlineKeyboardButton("✅ Ya, Kirim", callback_data=f"conf_send_pl#{plugin}#yes?page={page}{si_str}{cid_str}{mode_str}"),
            InlineKeyboardButton("❌ Tidak", callback_data=f"conf_send_pl#{plugin}#no?page={page}{si_str}{cid_str}{mode_str}"),
        ]
    ]
    
    await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))


@Altruix.bot.on_callback_query(filters.regex(r"^csp#([a-f0-9]{12})$"))
@log_errors
@iuser_check
async def send_plugin_execute_compressed(c: Client, cb: CallbackQuery):
    """Handle compressed confirmation send plugin callbacks."""
    await cb.answer()  # Instant feedback
    
    hash_id = cb.matches[0].group(1)
    original_data = get_callback_data(hash_id)
    
    if not original_data:
        return await cb.answer("⚠️ Session expired, please refresh.", show_alert=True)
    
    # Parse: conf_send_pl#plugin#(yes|no)?page=X&si=Y&cid=Z&mode=W
    match = re.match(r"conf_send_pl#([\w_ ]+)#(yes|no)\?page=(\d+)(?:&si=(-?\d+))?(?:&cid=(-?\d+))?(?:&mode=(\w+))?", original_data)
    if not match:
        return await cb.answer("⚠️ Invalid data.", show_alert=True)
    
    plugin = match.group(1)
    answer = match.group(2)
    page = int(match.group(3))
    si = match.group(4)
    cid = match.group(5)
    mode = match.group(6) or "userbot"
    
    if answer == "no":
        # Return to plugin help with user_id persistence
        text, buttons = await get_plugin_data(plugin, page, user_id=cb.from_user.id, chat_id=cid, mode=mode)
        return await cb.edit_message_text(text, reply_markup=buttons)
    
    # Continue with existing send logic...
    await cb.answer("🔍 Mencari file plugin...", show_alert=False)
    
    # Find plugin file
    plugin_file = None
    for base_path in ["Main/plugins/userbot", "Main/plugins/bot"]:
        potential_path = f"{base_path}/{plugin}.py"
        if os.path.exists(potential_path):
            plugin_file = potential_path
            break
    
    if not plugin_file:
        return await cb.answer("❌ Plugin file not found!", show_alert=True)
    
    try:
        # Send to user's PM
        caption = f"📦 <b>Plugin:</b> <code>{plugin}</code>\n📁 <b>Path:</b> <code>{plugin_file}</code>"
        
        try:
            await c.send_document(
                cb.from_user.id,
                plugin_file,
                caption=caption
            )
            await cb.answer("✅ Plugin sent to your PM!", show_alert=True)
        except Exception as send_err:
            # Fallback: send to current chat if PM fails
            try:
                await cb.message.reply_document(
                    plugin_file,
                    caption=caption
                )
                await cb.answer("✅ Plugin sent!", show_alert=True)
            except Exception as fallback_err:
                raise send_err
        
        # Return to plugin help with user_id persistence
        text, buttons = await get_plugin_data(plugin, page, user_id=cb.from_user.id, chat_id=cid, mode=mode)
        await cb.edit_message_text(text, reply_markup=buttons)
        
    except Exception as e:
        await cb.answer(f"❌ Error: {str(e)[:100]}", show_alert=True)


@Altruix.bot.on_callback_query(filters.regex(r"^conf_send_pl#([\w_ ]+)#(yes|no)\?page=(\d+)(?:&si=(-?\d+))?(?:&cid=(-?\d+))?(?:&mode=(\w+))?"))
@log_errors
@iuser_check
async def send_plugin_execute(c: Client, cb: CallbackQuery):
    """Legacy handler for uncompressed confirmation callbacks."""
    await cb.answer()  # Instant feedback
    
    plugin = cb.matches[0].group(1)
    answer = cb.matches[0].group(2)
    page = int(cb.matches[0].group(3))
    si = cb.matches[0].group(4)
    cid = cb.matches[0].group(5)
    mode = cb.matches[0].group(6) or "userbot"
    
    if answer == "no":
        # Return to plugin help with user_id persistence
        text, buttons = await get_plugin_data(plugin, page, user_id=cb.from_user.id, chat_id=cid, mode=mode)
        return await cb.edit_message_text(text, reply_markup=buttons)
        
    await cb.answer("🔍 Mencari file plugin...", show_alert=False)
    
    file_path = Altruix.find_plugin_file(plugin)
    if not file_path:
        return await cb.answer(f"❌ File plugin '{plugin}' tidak ditemukan!", show_alert=True)
        
    await cb.answer("📤 Mengirim file...", show_alert=False)
    try:
        # Determine target chat (where button was clicked or provided cid)
        target_chat = int(cid) if cid else (cb.message.chat.id if cb.message else cb.from_user.id)
        
        user_id = cb.from_user.id
        sender_client = None
        
        # 1. Prefer the userbot session associated with the user clicking the button
        for cl in Altruix.clients:
            me = getattr(cl, "me", None) or getattr(cl, "myself", None)
            if me and me.id == user_id:
                sender_client = cl
                break
        
        # 2. Fallback to first available userbot if owner/sudo is clicking
        if not sender_client and Altruix.clients:
            sender_client = Altruix.clients[0]
            
        # 3. Final fallback: The Bot Assistant itself (Most reliable for PMs)
        if not sender_client:
            sender_client = Altruix.bot
            
        Altruix.log(f"Help: Sending plugin '{plugin}' via {'Bot' if sender_client == Altruix.bot else 'Userbot'}")
            
        try:
            # Send using the selected client
            await sender_client.send_document(
                chat_id=target_chat,
                document=file_path,
                caption=f"📦 <b>Plugin File:</b> <code>{plugin}</code>\n"
                        f"🌿 <b>Path:</b> <code>{file_path}</code>\n\n"
                        f"Generated by Altruix Assistant."
            )
            await cb.answer("✅ Plugin berhasil dikirim!", show_alert=True)
        except Exception as send_err:
            Altruix.log(f"Help: Primary send failed: {send_err}. Falling back to Bot Assistant.")
            # If userbot failed (likely due to no common chat), try using the Bot itself
            if sender_client != Altruix.bot:
                await Altruix.bot.send_document(
                    chat_id=target_chat,
                    document=file_path,
                    caption=f"📦 <b>Plugin File:</b> <code>{plugin}</code>\n"
                            f"🌿 <b>Path:</b> <code>{file_path}</code>\n\n"
                            f"<i>(Sent via Bot Fallback)</i>"
                )
                await cb.answer("✅ Plugin berhasil dikirim (via Bot Assistant)!", show_alert=True)
            else:
                raise send_err
        
        # Return to plugin help with user_id persistence
        text, buttons = await get_plugin_data(plugin, page, user_id=cb.from_user.id, chat_id=cid, mode=mode)
        await cb.edit_message_text(text, reply_markup=buttons)
        
    except Exception as e:
        Altruix.log(f"Failed to send plugin {plugin}: {e}", level=40)
        await cb.answer(f"❌ Gagal mengirim plugin: {str(e)[:100]}", show_alert=True)
