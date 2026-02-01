# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.


import re
import pyrogram
from Main import Altruix
from typing import Optional
from platform import python_version
from pyrogram import Client, filters
from Main.core.decorators import log_errors, iuser_check
from pyrogram.types import (
    InlineQuery, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    InputTextMessageContent, InlineQueryResultArticle)


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
async def get_help_menu(return_all: bool = False, user_id: int = None, chat_id: int = None):
    global cache_help_menu, multi_pages
    ub_plugins, bot_plugins = get_total_plugins()
    from pyrogram.enums import ParseMode
    
    # ✅ Check for Custom Help Message
    custom_help = None
    parse_mode = ParseMode.HTML
    if user_id:
        # Find session index
        session_index = -1
        for i, cl in enumerate(Altruix.clients):
            me = getattr(cl, "me", None) or getattr(cl, "myself", None) or (await cl.get_me() if cl.is_initialized else None)
            if me and me.id == user_id:
                session_index = i
                break
        
        if session_index != -1:
            mode = await Altruix.config.get_env(f"HELP_INFO_{session_index}")
            if mode == "custom":
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
        help_msg = f"<b><u>❇️ Altruix Userbot Help Menu</u></b>\n" \
                   f"<b>Userbot version :</b> <code>V{Altruix.__version__}</code>\n" \
                   f"<b>Pyrogram version :</b> <code>V{pyrogram.__version__} </code>\n" \
                   f"<b>Python version :</b> <code>V{python_version()}</code>\n" \
                   f"<b>Userbot Plugins :</b> <code>{ub_plugins}</code>\n" \
                   f"<b>Bot Plugins :</b> <code>{bot_plugins}</code>"

    plugins = sorted(list(Altruix._command_help_message_data.keys()))
    
    # 🔗 Propagate session_index and chat_id for all plugin buttons
    si_str = f"?page=0&si={session_index}" if session_index != -1 else f"?page=0&si=-1"
    if chat_id:
        si_str += f"&cid={chat_id}"
    
    ikb = [
        InlineKeyboardButton(
            plugin.replace("_", " ").title(), callback_data=f"help#{plugin}{si_str}"
        )
        for plugin in plugins
    ]
    rows = Altruix.config.HELP_MENU_ROWS
    columns = Altruix.config.HELP_MENU_COLUMNS
    buttons = [ikb[i : i + columns] for i in range(0, len(ikb), columns)]
    if len(buttons) > rows:
        buttons = [buttons[i : i + rows] for i in range(0, len(buttons), rows)]
        multi_pages = True
    
    close_data = f"close_help_{session_index}" if session_index != -1 else "close_help"
    
    if multi_pages:
        for page in buttons:
            index = buttons.index(page)
            for i in page:
                for j in i:
                    j.callback_data = j.callback_data.replace("?page=0", f"?page={index}")
            page_buttons = [
                InlineKeyboardButton(str(i + 1), callback_data=f"help#_page?page={i}&si={session_index}{f'&cid={chat_id}' if chat_id else ''}")
                for i in range(len(buttons))
            ]
            for i in page_buttons:
                if i.text == str(index + 1):
                    i.text = f"> {i.text} <"
            page.append(page_buttons)
            page.append([InlineKeyboardButton("Close", close_data)])
    else:
        buttons.append([InlineKeyboardButton("Close", close_data)])
        
    if multi_pages and not return_all:
        return help_msg, buttons[0], parse_mode
    return help_msg, buttons, parse_mode


@log_errors
async def get_plugin_data(plugin: str, number: int = 0, sub_page: int = 0, user_id: int = None, chat_id: int = None):
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
    
    buttons = []
    nav_buttons = []
    if len(pages) > 1:
        if sub_page > 0:
            nav_buttons.append(InlineKeyboardButton(Altruix.get_string("prev"), callback_data=f"help#{plugin}?page={number}&sub={sub_page-1}{si_suffix}"))
        if sub_page < len(pages) - 1:
            nav_buttons.append(InlineKeyboardButton(Altruix.get_string("next"), callback_data=f"help#{plugin}?page={number}&sub={sub_page+1}{si_suffix}"))
    
    if nav_buttons:
        buttons.append(nav_buttons)
        
    back_data = f"help#_page?page={number}{si_suffix}"
    buttons.append([InlineKeyboardButton(Altruix.get_string("back"), callback_data=back_data)])
    buttons.append([InlineKeyboardButton("📤 Send Plugin", callback_data=f"send_plugin#{plugin}?page={number}{si_suffix}")])
    
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
    plugin: Optional[str] = iq.matches[0].group(2)
    
    cid = int(chat_id) if chat_id else None
    
    if not plugin:
        help_msg, buttons, parse_mode = await get_help_menu(user_id=iq.from_user.id, chat_id=cid)
        await iq.answer(
            results=[
                InlineQueryResultArticle(
                    title="Help Menu",
                    input_message_content=InputTextMessageContent(help_msg, parse_mode=parse_mode),
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
            ]
        )
    elif plugin.strip() in Altruix._command_help_message_data:
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
            ]
        )
    else:
        await iq.answer(
            results=[
                InlineQueryResultArticle(
                    title="Plugin not found!",
                    input_message_content=InputTextMessageContent(
                        f"Help for {plugin} is not found!"
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


@Altruix.bot.on_callback_query(filters.regex(r"^help(?:#(\w+)\?page=(\d+)(?:&sub=(\d+))?(?:&si=(-?\d+))?(?:&cid=(-?\d+))?)?$"))
@log_errors
@iuser_check
async def help_callback(_: Client, cq: CallbackQuery):
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
    
    # Determine the correct user_id based on session_index (si)
    user_id = cq.from_user.id
    if si_from_data and int(si_from_data) != -1:
        idx = int(si_from_data)
        if 0 <= idx < len(Altruix.clients):
            cl = Altruix.clients[idx]
            me = getattr(cl, "me", None) or getattr(cl, "myself", None) or await cl.get_me()
            user_id = me.id

    if not get_group(1):
        help_msg, buttons, parse_mode = await get_help_menu(user_id=user_id, chat_id=cid)
        return await cq.edit_message_text(
            help_msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=parse_mode
        )
    
    text_type = get_group(1)
    number = int(get_group(2)) if get_group(2) else 0
    sub_page = int(get_group(3)) if get_group(3) else 0

    if text_type == "_page":
        help_msg, buttons, parse_mode = await get_help_menu(return_all=True, user_id=user_id, chat_id=cid)
        return await cq.edit_message_text(
            help_msg, reply_markup=InlineKeyboardMarkup(buttons[number]), parse_mode=parse_mode
        )

    text, buttons = await get_plugin_data(text_type, number, sub_page, user_id=user_id, chat_id=cid)
    await cq.edit_message_text(text, reply_markup=buttons)


@Altruix.bot.on_message(filters.command("bothelp", ["/"]))
@log_errors
async def bot_help_handler(c: Client, m: pyrogram.types.Message):
    """Handler for bot help command"""
    text, markup, parse_mode = await get_help_menu(return_all=False, user_id=m.from_user.id, chat_id=m.chat.id)
    await m.reply(text, reply_markup=InlineKeyboardMarkup(markup), parse_mode=parse_mode)


@Altruix.bot.on_callback_query(filters.regex(r"^send_plugin#([\w_ ]+)\?page=(\d+)(?:&si=(-?\d+))?(?:&cid=(-?\d+))?"))
@log_errors
@iuser_check
async def send_plugin_confirm(c: Client, cb: CallbackQuery):
    plugin = cb.matches[0].group(1)
    page = cb.matches[0].group(2)
    si = cb.matches[0].group(3)
    cid = cb.matches[0].group(4)
    
    si_str = f"&si={si}" if si else ""
    cid_str = f"&cid={cid}" if cid else ""
    
    # Confirmation menu
    text = (
        f"<b>📤 Konfirmasi Kirim Plugin</b>\n\n"
        f"Apakah Anda yakin ingin mengirim file kode sumber untuk plugin <code>{plugin}</code>?\n\n"
        f"<i>File ini dapat mengandung kode yang sensitif atau penting.</i>"
    )
    
    buttons = [
        [
            InlineKeyboardButton("✅ Ya, Kirim", callback_data=f"conf_send_pl#{plugin}#yes?page={page}{si_str}{cid_str}"),
            InlineKeyboardButton("❌ Tidak", callback_data=f"conf_send_pl#{plugin}#no?page={page}{si_str}{cid_str}"),
        ]
    ]
    
    await cb.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))


@Altruix.bot.on_callback_query(filters.regex(r"^conf_send_pl#([\w_ ]+)#(yes|no)\?page=(\d+)(?:&si=(-?\d+))?(?:&cid=(-?\d+))?"))
@log_errors
@iuser_check
async def send_plugin_execute(c: Client, cb: CallbackQuery):
    plugin = cb.matches[0].group(1)
    answer = cb.matches[0].group(2)
    page = int(cb.matches[0].group(3))
    si = cb.matches[0].group(4)
    cid = cb.matches[0].group(5)
    
    if answer == "no":
        # Return to plugin help with user_id persistence
        text, buttons = await get_plugin_data(plugin, page, user_id=cb.from_user.id, chat_id=cid)
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
        text, buttons = await get_plugin_data(plugin, page, user_id=cb.from_user.id, chat_id=cid)
        await cb.edit_message_text(text, reply_markup=buttons)
        
    except Exception as e:
        Altruix.log(f"Failed to send plugin {plugin}: {e}", level=40)
        await cb.answer(f"❌ Gagal mengirim plugin: {str(e)[:100]}", show_alert=True)
