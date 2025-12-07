#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.

from Main import Altruix
from typing import List, Tuple
from pyrogram import Client, filters
from Main.core.decorators import log_errors
from Main.core.types.message import Message
from pyrogram.types import (
    CallbackQuery, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove,
    InlineKeyboardButton, InlineKeyboardMarkup,
)


settings_menu_buttons = [
    [
        InlineKeyboardButton("Sessions", callback_data="sessions_list_1"),
        InlineKeyboardButton("Configs", callback_data="configs_home"),
    ],
]


@Altruix.bot.on_callback_query(filters.regex("configs_home"))
@log_errors
async def configs_menu_cb_handler(c: Client, cb: CallbackQuery):
    await cb.answer("This feature will be added soon!", show_alert=True)


@Altruix.bot.on_callback_query(filters.regex("settings_menu"))
@log_errors
async def settings_menu_cb_handler(c: Client, cb: CallbackQuery):
    await cb.answer()  # Acknowledge the callback
    await cb.message.edit(
        text=Altruix.get_string("SETTINGS_TEXT") or "<b>Settings</b>",
        reply_markup=InlineKeyboardMarkup(settings_menu_buttons)
    )


def arrange_buttons(array: list, no=5) -> List:
    n = int(no)
    return [array[i * n : (i + 1) * n] for i in range((len(array) + n - 1) // n)]


def get_sessions_buttons(page=1) -> Tuple[List[InlineKeyboardButton], bool, int]:
    per_page = 9
    buttons = [
        InlineKeyboardButton(str(i.myself.first_name), f"session_info_{index}_{page}")
        for index, i in enumerate(Altruix.clients)
    ] + [InlineKeyboardButton("\u2795 Add a session", "add_session")]
    len_buttons = len(buttons)
    buttons = arrange_buttons(buttons, per_page)
    
    # 🔧 PERBAIKAN: Validasi page agar tidak melebihi jumlah halaman
    total_pages = len(buttons)
    if page < 1:
        page = 1
    elif page > total_pages:
        page = total_pages if total_pages > 0 else 1

    # Pastikan selalu ada halaman minimal
    current_buttons = buttons[page - 1] if total_pages > 0 else []
    has_next = page < total_pages
    return current_buttons, has_next, total_pages


@Altruix.bot.on_message(
    filters.command("settings", "/") & filters.user(Altruix.auth_users)
)
@log_errors
async def settings_command_handler(c: Client, m: Message):
    await m.reply(
        Altruix.get_string("SETTINGS_TEXT") or "<b>Settings</b>",
        reply_markup=InlineKeyboardMarkup(settings_menu_buttons),
        quote=True,
    )


@Altruix.bot.on_callback_query(filters.regex("sessions_list_(\\d+)$"))
@log_errors
async def sessions_menu_cb_handler(c: Client, cb: CallbackQuery):
    await cb.answer()
    try:
        page = int(cb.data.split("_")[-1])
    except (ValueError, IndexError):
        page = 1

    buttons, has_next, total_pages = get_sessions_buttons(page)
    buttons = arrange_buttons(buttons, 3)
    last_col = []
    if not page == 1:
        last_col.append(InlineKeyboardButton("Previous", f"sessions_list_{page - 1}"))
    last_col.append(
        InlineKeyboardButton(f"🔙 [{page}/{total_pages or 1}]", "settings_menu")
    )
    if has_next:
        last_col.append(InlineKeyboardButton("Next", f"sessions_list_{page + 1}"))
    await cb.message.edit(
        text="Sessions", reply_markup=InlineKeyboardMarkup(buttons + [last_col])
    )


@Altruix.bot.on_callback_query(filters.regex("session_info_(\\d+)_(\\d+)$"))
@log_errors
async def sessions_info_cb_handler(c: Client, cb: CallbackQuery):
    await cb.answer()
    index = int(cb.matches[0].group(1))
    callback_page = int(cb.matches[0].group(2))  # 🔧 PERBAIKAN: sebelumnya salah ambil group(1) dua kali

    # 🔧 PERBAIKAN: Pastikan index valid
    if index >= len(Altruix.clients):
        await cb.message.edit("Session not found.")
        return

    session_info = Altruix.clients[index].myself
    txt = "<b>Session info</b>\n\n<b>First name:</b> {}\n<b>Last name:</b> {}\n<b>DC ID:</b> <code>{}</code>\n<b>Username:</b> @{}\n<b>Is SCAM:</b> <code>{}</code>".format(
        session_info.first_name or "None",
        session_info.last_name or "None",
        session_info.dc_id or "Unknown",
        session_info.username or "None",
        "Yes" if session_info.is_scam else "No",
    )
    await cb.message.edit(
        text=txt,
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🔄 Refresh data", f"refresh_session_info_{index}"
                    ),
                    InlineKeyboardButton(
                        "🔗 Unlink (Remove)", f"unlink_session_{index}"
                    ),
                ],
                [
                    InlineKeyboardButton("🔙 Back", f"sessions_list_{callback_page}"),
                ],
            ]
        ),
    )


@Altruix.bot.on_callback_query(filters.regex("refresh_session_info_(\\d+)$"))
@log_errors
async def refresh_session_info_cb_handler(c: Client, cb: CallbackQuery):
    index = int(cb.matches[0].group(1))
    
    # 🔧 PERBAIKAN: Pastikan Altruix.ourselves cukup panjang sebelum assign
    while len(Altruix.ourselves) <= index:
        Altruix.ourselves.append(None)  # Tambahkan placeholder jika belum ada
    
    # Ambil data user baru
    user = await Altruix.clients[index].get_me()
    Altruix.ourselves[index] = user
    Altruix.clients[index].myself = user  # Pastikan cache di client juga diperbarui

    await cb.answer("Data refreshed!")
    # Panggil ulang handler info dengan data terbaru
    await sessions_info_cb_handler(c, cb)


@Altruix.bot.on_callback_query(filters.regex("unlink_session_(\\d+)$"))
@log_errors
async def unlink_session_cb_handler(c: Client, cb: CallbackQuery):
    index = int(cb.matches[0].group(1))
    
    # 🔧 PERBAIKAN: Validasi index sebelum hapus
    if index >= len(Altruix.clients):
        await cb.answer("Session already removed or invalid.", show_alert=True)
        return

    temp = await cb.message.reply(
        "Are you sure you want to unlink this session?",
        quote=True,
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("Yeah sure")]],
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )
    confirmation = await cb.from_user.listen(filters.text, timeout=600)
    await Altruix.bot.delete_messages(temp.chat.id, (temp.id, confirmation.id))
    temp = await temp.reply("Processing..", ReplyKeyboardRemove())
    await cb.answer("The session will be removed and restarted soon.", show_alert=True)
    await temp.delete()
    await Altruix.remove_session(index)
    # Reset ke halaman pertama setelah hapus
    cb.data = "sessions_list_1"
    await sessions_menu_cb_handler(c, cb)
