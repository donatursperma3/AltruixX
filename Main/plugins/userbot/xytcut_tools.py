# Copyright (C) 2026 by Altruix@Github, < https://github.com/Altruix >.
# This file is part of the Altruix project.
# All rights reserved.

import asyncio
import copy
import hashlib
import html
import json
import os
import re
import time
import traceback
from typing import Any, Dict, List, Optional, Tuple

import httpx
from pyrogram import filters, enums, errors
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    ForceReply,
    Message,
    InlineQuery,
    InlineQueryResultPhoto,
    InlineQueryResultArticle,
    InputTextMessageContent,
)

from Main import Altruix
from Main.core.decorators import log_errors
from Main.internals.ytcut_helpers import (
    extract_yt_info,
    get_inline_bot_results_for_client,
    YTCUT_DEFAULT_EXTRACT,
    YTCUT_DEFAULT_QUALITY,
    ensure_ytcut_state_registry,
    get_ytcut_user_config,
    save_ytcut_user_config,
    sync_ytcut_task,
    make_ytcut_task_id,
    build_ytcut_dashboard_text,
    build_ytcut_dashboard_keyboard,
    parse_ytcut_timestamp,
    format_ytcut_timestamp,
    ytcut_time_to_yt_format,
    normalize_ytcut_segments,
    ytcut_segments_overlap,
    build_keep_segments_from_remove,
    find_ytcut_state_by_prompt_message_id,
)
from Main.utils.essentials import Essentials
from Main.utils.file_helpers import get_db_path

# Use defaults from Main.internals.ytcut_helpers where appropriate
PLUGIN_VERSION = "0.0.20"


@Altruix.register_on_cmd([
    "ytcut",
], bot_mode_unsupported=True, requires_input=False,
    cmd_help={
        "help": (
            "Multi-Trim & Merge YouTube video dengan dashboard interaktif. "
            "Gunakan .ytcut <URL> atau balas pesan berisi link YouTube dan jalankan .ytcut. "
            "Setelah dashboard muncul, pilih tombol untuk menambah potongan, memilih mode KEEP/REMOVE, "
            "mengubah kualitas atau ekstrak audio/video, dan mulai proses penggabungan."
        ),
        "example": (
            ".ytcut https://www.youtube.com/watch?v=xxxx\n"
            "Contoh interaktif: Setelah perintah, klik ➕ Tambah Potongan lalu balas dengan timestamp seperti 01:00-02:15 atau 30-90."
        )
    }
)
@log_errors
async def ytcut_cmd(c: Any, m: Message):
    # Entry point for the .ytcut command.
    # Workflow:
    # 1. Resolve the YouTube URL from command input or replied message.
    # 2. Extract video metadata and initialize the ytcut state registry.
    # 3. Try to build an inline bot dashboard result for a compact UX.
    # 4. If inline results fail or return empty, send a regular photo/message dashboard instead.
    ensure_ytcut_state_registry()
    url = m.user_input.strip() if getattr(m, "user_input", None) else ""
    if not url and m.reply_to_message and m.reply_to_message.text:
        match = re.search(r"https?://\S+", m.reply_to_message.text)
        if match:
            url = match.group(0)
    if not url:
        return await m.reply("❌ Silakan kirim link YouTube atau balas pesan berisi link dengan perintah .ytcut")
    status = await m.reply("<b>🔍 Menganalisis video YouTube...</b>")
    try:
        info = await extract_yt_info(url)
        if info.get("type") != "video":
            return await status.edit("❌ Hanya mendukung video YouTube tunggal. Gunakan URL video, bukan playlist.")

        task_id = make_ytcut_task_id(url)
        state = {
            "task_id": task_id,
            "chat_id": m.chat.id,
            "user_id": m.from_user.id if m.from_user else None,
            "reply_to": m.reply_to_message.id if m.reply_to_message else m.id,
            "url": info.get("url") or url,
            "title": info.get("title") or "YouTube Video",
            "duration": int(info.get("duration", 0) or 0),
            "thumbnail": info.get("thumbnail"),
            "segments": [],
            "mode": "keep",
            "extract": YTCUT_DEFAULT_EXTRACT,
            "quality": YTCUT_DEFAULT_QUALITY,
            "prompt_message_id": None,
            "dashboard_message_id": None,
            "processing": False,
        }
        user_pref = get_ytcut_user_config(state["user_id"])
        state["mode"] = user_pref.get("mode", state["mode"])
        state["extract"] = user_pref.get("extract", state["extract"])
        state["quality"] = user_pref.get("quality", state["quality"])
        Altruix.YTCUT_STATE[task_id] = state

        # Ensure the task state is persisted before asking the assistant bot
        # for inline results. The assistant (bot) may be a separate process and
        # will attempt to load the task state from the local DB; without this
        # sync the bot handler may report the session as expired or return
        # empty inline results.
        try:
            await sync_ytcut_task(task_id)
        except Exception:
            # Non-fatal: we still attempt inline builder even if DB sync fails.
            pass
        thumb_url = state["thumbnail"]
        if thumb_url and thumb_url.startswith("//"):
            thumb_url = f"https:{thumb_url}"

        text = build_ytcut_dashboard_text(state)
        kb = build_ytcut_dashboard_keyboard(state)
        bot_username = Altruix.bot_manager.get_bot_username(c.me.id)
        if bot_username and bot_username != "Unknown":
            try:
                # Pre-resolve chat ID for the bot to avoid PeerIdInvalid in callbacks
                try:
                    await Altruix.bot.get_chat(m.chat.id)
                except errors.PeerIdInvalid:
                    # If PeerIdInvalid, bot really doesn't know this chat.
                    # We can try to send a message from bot first to introduce it.
                    pass
                except Exception:
                    pass

                results = await get_inline_bot_results_for_client(c, f"ytcut_menu#{task_id}")
                if not getattr(results, "results", None):
                    # Guard against empty inline result lists.
                    # This prevents a hard IndexError when Telegram returns no results.
                    raise ValueError("Inline bot results returned empty")

                # Use the first inline result from the bot response and send it to the chat.
                # If this fails, we let the exception fall through and use the fallback dashboard.
                sent = await c.send_inline_bot_result(
                    chat_id=m.chat.id,
                    query_id=results.query_id,
                    result_id=results.results[0].id,
                    reply_to_message_id=m.reply_to_message.id if m.reply_to_message else m.id,
                )
                state["dashboard_message_id"] = getattr(sent, "id", None) or getattr(sent, "message_id", None)
                await sync_ytcut_task(task_id)
                await status.delete()
                await m.delete_if_self()
                return
            except Exception as ex:
                Altruix.log(f"YTcut inline builder failed: {ex}\n{traceback.format_exc()}")

        if thumb_url:
            msg = await Altruix.bot.send_photo(
                chat_id=m.chat.id,
                photo=thumb_url,
                caption=text,
                parse_mode=enums.ParseMode.HTML,
                reply_markup=kb,
                disable_notification=True,
            )
        else:
            msg = await Altruix.bot.send_message(
                chat_id=m.chat.id,
                text=text,
                parse_mode=enums.ParseMode.HTML,
                reply_markup=kb,
                disable_web_page_preview=True,
                disable_notification=True,
            )
        state["dashboard_message_id"] = msg.id
        await sync_ytcut_task(task_id)
        await status.delete()
        await m.delete_if_self()
    except Exception as e:
        err_msg = str(e).replace('`', "'")
        Altruix.log(f"YTcut init failed: {err_msg}\n{traceback.format_exc()}")
        await status.edit(f"❌ <b>Error:</b> <code>{html.escape(err_msg)}</code>")


