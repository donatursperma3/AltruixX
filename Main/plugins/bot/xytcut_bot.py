# Copyright (C) 2026 by Altruix@Github, < https://github.com/Altruix >.
# This file is part of the Altruix project.
# All rights reserved.

PLUGIN_VERSION = "1.0.267"

import asyncio
import html
import os
import time
import traceback
import logging
from typing import Any

from pyrogram import filters, enums, errors
from pyrogram.errors import PeerIdInvalid, MessageNotModified
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InlineQuery,
    InlineQueryResultPhoto,
    InlineQueryResultArticle,
    InputTextMessageContent,
    CallbackQuery,
    ForceReply,
    Message,
)

from Main import Altruix
from Main.core.decorators import log_errors, iuser_check
from Main.utils.file_helpers import get_user_button_style
from Main.internals.ytcut_helpers import (
    ensure_ytcut_state_registry,
    get_ytcut_task_state,
    find_ytcut_state_by_prompt_message_id,
    find_ytcut_state_by_user_id,
    build_ytcut_dashboard_text,
    build_ytcut_dashboard_keyboard,
    update_ytcut_dashboard_message,
    save_ytcut_user_config,
    enqueue_ytcut_run,
    sync_ytcut_task,
    delete_ytcut_task,
    parse_ytcut_timestamp,
    format_ytcut_timestamp,
    ytcut_segments_overlap,
    get_inline_bot_results_for_client,
    merge_ytcut_segments,
    YTCUT_TEMP_DIR,
)

# ✅ VERIFICATION: Import-level check to confirm module loaded with INFO logging enabled
Altruix.log("✅ YTcut bot callbacks module loaded with INFO-level logging enabled (v1.0.267+)", level=logging.INFO)


def parse_ytcut_manual_segments(text: str):
    entries = [line.strip() for line in text.splitlines() if line.strip()]
    if not entries:
        raise ValueError("Tidak ada timestamp yang valid.")

    segments = []
    for entry in entries:
        if "-" not in entry:
            raise ValueError("Setiap baris harus berisi format start-end, misalnya 01:00-02:15.")
        start_text, end_text = entry.split("-", 1)
        start = parse_ytcut_timestamp(start_text)
        end = parse_ytcut_timestamp(end_text)
        if start >= end:
            raise ValueError("Timestamp awal harus lebih kecil dari akhir.")
        segments.append({"start": start, "end": end, "duration": end - start})
    return segments


async def _edit_ytcut_state_message(
    client: Any,
    cb: CallbackQuery,
    state: dict,
    text: str,
    reply_markup: InlineKeyboardMarkup,
):
    if cb.inline_message_id:
        state["inline_message_id"] = cb.inline_message_id

    inline_id = state.get("inline_message_id")

    async def _safe_edit(method, **kwargs):
        try:
            return await method(**kwargs)
        except errors.FloodWait as e:
            # If wait is short, we can wait and retry once.
            if e.value <= 3:
                await asyncio.sleep(e.value + 0.1)
                try:
                    return await method(**kwargs)
                except:
                    pass
            # Inform user if we can't edit right now
            try:
                await cb.answer(f"⚠️ Telegram Throttling: Mohon tunggu {e.value} detik.", show_alert=False)
            except:
                pass
            return None
        except MessageNotModified:
            return True # Consider it success as no change was needed
        except Exception:
            return None

    # 1. Try using CallbackQuery directly (safest for both inline and regular)
    if (cb.inline_message_id and cb.inline_message_id == inline_id) or \
       (cb.message and state.get("dashboard_message_id") == cb.message.id):
        
        res = await _safe_edit(cb.edit_message_caption, caption=text, parse_mode=enums.ParseMode.HTML, reply_markup=reply_markup)
        if res: return
        
        res = await _safe_edit(cb.edit_message_text, text=text, parse_mode=enums.ParseMode.HTML, reply_markup=reply_markup)
        if res: return

    # 2. Fallback to Client methods for Inline Messages
    if inline_id:
        # Prefer pyromod's edit_inline methods
        if hasattr(client, "edit_inline_caption"):
            res = await _safe_edit(client.edit_inline_caption, inline_message_id=inline_id, caption=text, parse_mode=enums.ParseMode.HTML, reply_markup=reply_markup)
        else:
            # Try positional fallback if keyword fails
            try:
                res = await client.edit_message_caption(None, None, text, inline_id, parse_mode=enums.ParseMode.HTML, reply_markup=reply_markup)
            except:
                res = await _safe_edit(client.edit_message_caption, inline_message_id=inline_id, caption=text, parse_mode=enums.ParseMode.HTML, reply_markup=reply_markup)
        
        if res: return

        if hasattr(client, "edit_inline_text"):
            res = await _safe_edit(client.edit_inline_text, inline_message_id=inline_id, text=text, parse_mode=enums.ParseMode.HTML, reply_markup=reply_markup)
        else:
            try:
                res = await client.edit_message_text(None, None, text, inline_id, parse_mode=enums.ParseMode.HTML, reply_markup=reply_markup)
            except:
                res = await _safe_edit(client.edit_message_text, inline_message_id=inline_id, text=text, parse_mode=enums.ParseMode.HTML, reply_markup=reply_markup)
        
        if res: return

    # 3. Fallback to Client methods for Regular Messages
    if state.get("dashboard_message_id"):
        chat_id = state["chat_id"]
        mid = state["dashboard_message_id"]
        
        res = await _safe_edit(client.edit_message_caption, chat_id=chat_id, message_id=mid, caption=text, parse_mode=enums.ParseMode.HTML, reply_markup=reply_markup)
        if res: return
        
        res = await _safe_edit(client.edit_message_text, chat_id=chat_id, message_id=mid, text=text, parse_mode=enums.ParseMode.HTML, reply_markup=reply_markup)
        if res: return

    # 4. Ultimate Fallback: Send as new message if editing fails completely (optional, but let's stick to edits for dashboard)
    # await client.send_message(...)

    await client.send_message(
        chat_id=cb.from_user.id,
        text=text,
        parse_mode=enums.ParseMode.HTML,
        reply_markup=reply_markup,
    )


def _clamp_int(v: int, lo: int, hi: int) -> int:
    return max(lo, min(int(v), int(hi)))

def _clamp_float(v: float, lo: float, hi: float) -> float:
    try:
        vf = float(v)
    except Exception:
        vf = 0.0
    return max(float(lo), min(vf, float(hi)))


@Altruix.bot.on_inline_query(filters.regex(r"^ytcut_menu#([\w-]+)$"))
@iuser_check
async def ytcut_inline_menu(c: Any, obj: InlineQuery, task_id: str = None):
    if not task_id:
        task_id = obj.matches[0].group(1)
    state = await get_ytcut_task_state(task_id)
    if not state:
        return await obj.answer(
            [InlineQueryResultArticle(
                title="Sesi Kedaluwarsa",
                input_message_content=InputTextMessageContent(
                    "❌ Sesi ini telah kedaluwarsa. Silakan ulang perintah .ytcut"
                ),
            )],
            cache_time=0,
            is_personal=True,
        )

    text = build_ytcut_dashboard_text(state)
    thumb_url = state.get("thumbnail")
    if thumb_url and thumb_url.startswith("//"):
        thumb_url = f"https:{thumb_url}"

    if thumb_url and thumb_url.startswith("http"):
        await obj.answer(
            results=[
                InlineQueryResultPhoto(
                    id=f"ytcut_{task_id}",
                    photo_url=thumb_url,
                    thumb_url=thumb_url,
                    title=state.get("title", "YouTube Multi-Cut"),
                    description=f"Mode: {state['mode'].upper()} | Kualitas: {state['quality']}p",
                    caption=text,
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=build_ytcut_dashboard_keyboard(state),
                )
            ],
            cache_time=0,
            is_personal=True,
        )
    else:
        await obj.answer(
            results=[
                InlineQueryResultArticle(
                    id=f"ytcut_{task_id}",
                    title=state.get("title", "YouTube Multi-Cut"),
                    description=f"Mode: {state['mode'].upper()} | Kualitas: {state['quality']}p",
                    input_message_content=InputTextMessageContent(text, parse_mode=enums.ParseMode.HTML),
                    reply_markup=build_ytcut_dashboard_keyboard(state),
                )
            ],
            cache_time=0,
            is_personal=True,
        )


@Altruix.bot.on_callback_query(filters.regex(r"^ytcut_add_menu#([\w-]+)$"))
@iuser_check
@log_errors
async def ytcut_add_menu_cb(c: Any, cb: CallbackQuery):
    task_id = cb.matches[0].group(1)
    state = await get_ytcut_task_state(task_id)
    if not state:
        return await cb.answer("Sesi tidak ditemukan.", show_alert=True)

    # Simple debounce: If we're already processing an update for this task, ignore rapid clicks
    now = time.time()
    if state.get("_busy_until", 0) > now:
        return await cb.answer("Mohon tunggu sebentar...", show_alert=False)
    state["_busy_until"] = now + 0.5  # 500ms cooldown

    duration = float(state.get("duration", 0) or 0)
    edit_idx = state.get("edit_index") # index of segment being edited, if any

    if "add_target" not in state:
        state["add_target"] = "s"
    
    # Initialize add_start/end if not present or if we just entered edit mode
    if "add_start" not in state or "add_end" not in state:
        if edit_idx is not None and 0 <= edit_idx < len(state.get("segments", [])):
            seg = state["segments"][edit_idx]
            state["add_start"] = float(seg["start"])
            state["add_end"] = float(seg["end"])
        else:
            state["add_start"] = 0.0
            state["add_end"] = min(30.0, duration) if duration > 0 else 1.0

    s = _clamp_float(state.get("add_start", 0.0), 0.0, max(0.0, duration))
    e = _clamp_float(state.get("add_end", 1.0), 0.0, max(0.0, duration))
    
    # Consistent logic: End must be at least 0.25s after Start
    if duration > 0 and e <= s + 0.001:
        e = _clamp_float(s + 0.25, 0.0, duration)
    
    state["add_start"], state["add_end"] = s, e

    target = state.get("add_target", "s")
    user_style = None
    try:
        user_style = get_user_button_style(state.get("user_id"))
    except Exception:
        user_style = None

    def kb_btn(text: str, cb_data: str):
        if user_style is not None:
            return InlineKeyboardButton(text, callback_data=cb_data, style=user_style)
        return InlineKeyboardButton(text, callback_data=cb_data)

    start_lbl = f"🟢 Edit START: {format_ytcut_timestamp(s)}" if target == "s" else f"⚪️ Edit START: {format_ytcut_timestamp(s)}"
    end_lbl = f"🟢 Edit END: {format_ytcut_timestamp(e)}" if target == "e" else f"⚪️ Edit END: {format_ytcut_timestamp(e)}"

    menu_title = f"📝 <b>Edit Potongan #{edit_idx + 1}</b>" if edit_idx is not None else "<b>➕ Tambah Potongan</b>"
    apply_btn_lbl = "💾 Simpan Perubahan" if edit_idx is not None else "✅ Tambahkan"

    text = (
        f"<blockquote expandable>"
        f"{menu_title}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>⏱ Start:</b> <code>{format_ytcut_timestamp(s)}</code>\n"
        f"<b>⌛️ End:</b> <code>{format_ytcut_timestamp(e)}</code>\n"
        f"<b>📊 Durasi:</b> <code>{format_ytcut_timestamp(max(0, e - s))}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Pilih tab START/END, lalu pakai tombol +/- untuk mengatur waktu.</i>\n"
        f"</blockquote>"
    )

    buttons = [
        [
            kb_btn(start_lbl, f"ytcut_add_tab#{task_id}#s"),
            kb_btn(end_lbl, f"ytcut_add_tab#{task_id}#e"),
        ],
        [kb_btn("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "ytcut_noop")],
        [
            kb_btn("⏪ -30m", f"ytcut_add_adj#{task_id}#{target}#-1800"),
            kb_btn("◀️ -10m", f"ytcut_add_adj#{task_id}#{target}#-600"),
            kb_btn("+10m ▶️", f"ytcut_add_adj#{task_id}#{target}#600"),
            kb_btn("+30m ⏩", f"ytcut_add_adj#{task_id}#{target}#1800"),
        ],
        [
            kb_btn("⏪ -5m", f"ytcut_add_adj#{task_id}#{target}#-300"),
            kb_btn("◀️ -1m", f"ytcut_add_adj#{task_id}#{target}#-60"),
            kb_btn("+1m ▶️", f"ytcut_add_adj#{task_id}#{target}#60"),
            kb_btn("+5m ⏩", f"ytcut_add_adj#{task_id}#{target}#300"),
        ],
        [
            kb_btn("⏪ -30s", f"ytcut_add_adj#{task_id}#{target}#-30"),
            kb_btn("◀️ -10s", f"ytcut_add_adj#{task_id}#{target}#-10"),
            kb_btn("+10s ▶️", f"ytcut_add_adj#{task_id}#{target}#10"),
            kb_btn("+30s ⏩", f"ytcut_add_adj#{task_id}#{target}#30"),
        ],
        [
            kb_btn("⏪ -5s", f"ytcut_add_adj#{task_id}#{target}#-5"),
            kb_btn("◀️ -1s", f"ytcut_add_adj#{task_id}#{target}#-1"),
            kb_btn("+1s ▶️", f"ytcut_add_adj#{task_id}#{target}#1"),
            kb_btn("+5s ⏩", f"ytcut_add_adj#{task_id}#{target}#5"),
        ],
        [
            kb_btn("⏪ -0.5s", f"ytcut_add_adj#{task_id}#{target}#-0.5"),
            kb_btn("◀️ -0.25s", f"ytcut_add_adj#{task_id}#{target}#-0.25"),
            kb_btn("+0.25s ▶️", f"ytcut_add_adj#{task_id}#{target}#0.25"),
            kb_btn("+0.5s ⏩", f"ytcut_add_adj#{task_id}#{target}#0.5"),
        ],
        [kb_btn("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "ytcut_noop")],
        [
            kb_btn(apply_btn_lbl, f"ytcut_add_apply#{task_id}"),
            kb_btn("📝 Input Manual", f"ytcut_add#{task_id}"),
        ],
        [
            kb_btn("🔃 Reset", f"ytcut_add_reset#{task_id}"),
            kb_btn("« Back to Menu »", f"ytcut_back#{task_id}"),
        ],
    ]

    await _edit_ytcut_state_message(c, cb, state, text, InlineKeyboardMarkup(buttons))
    asyncio.create_task(sync_ytcut_task(task_id))
    await cb.answer()


@Altruix.bot.on_callback_query(filters.regex(r"^ytcut_add_tab#([\w-]+)#([se])$"))
@iuser_check
@log_errors
async def ytcut_add_tab_cb(c: Any, cb: CallbackQuery):
    task_id, target = cb.matches[0].groups()
    state = await get_ytcut_task_state(task_id)
    if not state:
        return await cb.answer("Sesi tidak ditemukan.", show_alert=True)
    
    state["add_target"] = target
    # Don't sync yet, menu_cb will do it
    cb.matches = [type("Match", (), {"group": lambda self, n: task_id})()]
    await ytcut_add_menu_cb(c, cb)


@Altruix.bot.on_callback_query(filters.regex(r"^ytcut_add_adj#([\w-]+)#([se])#(-?\d+(?:\.\d+)?)$"))
@iuser_check
@log_errors
async def ytcut_add_adj_cb(c: Any, cb: CallbackQuery):
    task_id, target, val = cb.matches[0].groups()
    state = await get_ytcut_task_state(task_id)
    if not state:
        return await cb.answer("Sesi tidak ditemukan.", show_alert=True)
    
    # Simple debounce
    now = time.time()
    if state.get("_busy_until", 0) > now:
        return await cb.answer()
    
    try:
        delta = float(val)
    except Exception:
        delta = 0.0

    duration = float(state.get("duration", 0) or 0)
    s = _clamp_float(state.get("add_start", 0.0), 0.0, max(0.0, duration))
    e = _clamp_float(state.get("add_end", 1.0), 0.0, max(0.0, duration))

    if target == "s":
        new_s = s + delta
        if new_s < 0:
            return await cb.answer("⚠️ Mencapai batas awal video (00:00).", show_alert=True)
        if duration > 0 and new_s >= duration:
            return await cb.answer("⚠️ Start tidak boleh melebihi durasi video.", show_alert=True)
        
        s = _clamp_float(new_s, 0.0, max(0.0, duration))
        if duration > 0 and e <= s + 0.001:
            e = _clamp_float(s + 0.25, 0.0, duration)
    else:
        new_e = e + delta
        if duration > 0 and new_e > duration + 0.001:
            return await cb.answer(f"⚠️ Mencapai batas akhir video ({format_ytcut_timestamp(duration)}).", show_alert=True)
        if new_e <= 0.25:
            return await cb.answer("⚠️ End tidak boleh kurang dari 0.25 detik.", show_alert=True)

        e = _clamp_float(new_e, 0.0, max(0.0, duration))
        if duration > 0 and e <= s + 0.001:
            s = _clamp_float(e - 0.25, 0.0, duration)

    state["add_target"] = target
    state["add_start"], state["add_end"] = s, e
    
    # Redundant sync removed, will be handled by menu_cb
    cb.matches = [type("Match", (), {"group": lambda self, n: task_id})()]
    await ytcut_add_menu_cb(c, cb)


@Altruix.bot.on_callback_query(filters.regex(r"^ytcut_add_reset#([\w-]+)$"))
@iuser_check
@log_errors
async def ytcut_add_reset_cb(c: Any, cb: CallbackQuery):
    task_id = cb.matches[0].group(1)
    state = await get_ytcut_task_state(task_id)
    if not state:
        return await cb.answer("Sesi tidak ditemukan.", show_alert=True)
    
    now = time.time()
    if state.get("_busy_until", 0) > now:
        return await cb.answer()
    state["_busy_until"] = now + 0.3

    duration = float(state.get("duration", 0) or 0)
    edit_idx = state.get("edit_index")
    
    state["add_target"] = "s"
    if edit_idx is not None and 0 <= edit_idx < len(state.get("segments", [])):
        seg = state["segments"][edit_idx]
        state["add_start"] = float(seg["start"])
        state["add_end"] = float(seg["end"])
    else:
        state["add_start"] = 0.0
        state["add_end"] = min(30.0, duration) if duration > 0 else 1.0
    
    cb.matches = [type("Match", (), {"group": lambda self, n: task_id})()]
    await ytcut_add_menu_cb(c, cb)


@Altruix.bot.on_callback_query(filters.regex(r"^ytcut_add_apply#([\w-]+)$"))
@iuser_check
@log_errors
async def ytcut_add_apply_cb(c: Any, cb: CallbackQuery):
    task_id = cb.matches[0].group(1)
    state = await get_ytcut_task_state(task_id)
    if not state:
        return await cb.answer("Sesi tidak ditemukan.", show_alert=True)

    now = time.time()
    if state.get("_busy_until", 0) > now:
        return await cb.answer()
    state["_busy_until"] = now + 0.5

    duration = float(state.get("duration", 0) or 0)
    s = _clamp_float(state.get("add_start", 0.0), 0.0, max(0.0, duration))
    e = _clamp_float(state.get("add_end", 1.0), 0.0, max(0.0, duration))
    if e <= s + 0.001:
        return await cb.answer("Timestamp tidak valid. Pastikan START < END.", show_alert=True)

    candidate = {"start": s, "end": e, "duration": e - s}
    segments = (state.get("segments") or []).copy()
    edit_idx = state.get("edit_index")

    if edit_idx is not None:
        if 0 <= edit_idx < len(segments):
            segments[edit_idx] = candidate
            msg = f"✅ Potongan #{edit_idx + 1} diperbarui."
        else:
            return await cb.answer("Index edit tidak valid.", show_alert=True)
    else:
        segments.append(candidate)
        msg = "✅ Potongan ditambahkan."

    if not state.get("_manual_order"):
        segments.sort(key=lambda x: x["start"])
        
    if ytcut_segments_overlap(segments):
        return await cb.answer("Potongan tumpang tindih. Ubah START/END.", show_alert=True)

    state["segments"] = segments
    # Clear edit state
    state.pop("edit_index", None)
    state.pop("add_start", None)
    state.pop("add_end", None)
    state.pop("add_target", None)

    await update_ytcut_dashboard_message(c, state)
    asyncio.create_task(sync_ytcut_task(task_id))
    await cb.answer(msg)


@Altruix.bot.on_callback_query(filters.regex(r"^ytcut_back#([\w-]+)$"))
@iuser_check
@log_errors
async def ytcut_back_cb(c: Any, cb: CallbackQuery):
    task_id = cb.matches[0].group(1)
    state = await get_ytcut_task_state(task_id)
    if not state:
        return await cb.answer("Sesi tidak ditemukan.", show_alert=True)
    
    # Clear temp add/edit states
    state.pop("edit_index", None)
    state.pop("add_start", None)
    state.pop("add_end", None)
    state.pop("add_target", None)

    await update_ytcut_dashboard_message(c, state)
    asyncio.create_task(sync_ytcut_task(task_id))
    await cb.answer()


@Altruix.bot.on_callback_query(filters.regex(r"^ytcut_edit_seg#([\w-]+)#(\d+)$"))
@iuser_check
@log_errors
async def ytcut_edit_seg_cb(c: Any, cb: CallbackQuery):
    task_id = cb.matches[0].group(1)
    idx = int(cb.matches[0].group(2))
    state = await get_ytcut_task_state(task_id)
    if not state:
        return await cb.answer("Sesi tidak ditemukan.", show_alert=True)

    now = time.time()
    if state.get("_busy_until", 0) > now:
        return await cb.answer()
    state["_busy_until"] = now + 0.5

    if idx < 0 or idx >= len(state.get("segments", [])):
        return await cb.answer("Index potongan tidak valid.", show_alert=True)

    seg = state["segments"][idx]
    state["edit_index"] = idx
    state["add_start"] = float(seg["start"])
    state["add_end"] = float(seg["end"])
    state["add_target"] = "s"

    # Forward to add_menu_cb
    cb.matches = [type("Match", (), {"group": lambda self, n: task_id})()]
    await ytcut_add_menu_cb(c, cb)


@Altruix.bot.on_callback_query(filters.regex(r"^ytcut_reorder_menu#([\w-]+)$"))
@iuser_check
@log_errors
async def ytcut_reorder_menu_cb(c: Any, cb: CallbackQuery):
    task_id = cb.matches[0].group(1)
    state = await get_ytcut_task_state(task_id)
    if not state:
        return await cb.answer("Sesi tidak ditemukan.", show_alert=True)

    now = time.time()
    if state.get("_busy_until", 0) > now:
        return await cb.answer()
    state["_busy_until"] = now + 0.5

    segments = state.get("segments", [])
    if len(segments) < 2:
        return await cb.answer("Minimal butuh 2 potongan untuk mengubah urutan.", show_alert=True)

    user_style = None
    try:
        user_style = get_user_button_style(state.get("user_id"))
    except Exception:
        user_style = None

    def kb_btn(text: str, cb_data: str):
        if user_style is not None:
            return InlineKeyboardButton(text, callback_data=cb_data, style=user_style)
        return InlineKeyboardButton(text, callback_data=cb_data)

    seg_list_text = []
    buttons = []
    for i, seg in enumerate(segments):
        ts_text = f"<code>{format_ytcut_timestamp(seg['start'])} - {format_ytcut_timestamp(seg['end'])}</code>"
        seg_list_text.append(f"{i+1}. {ts_text}")
        
        row = [kb_btn(f"Potongan {i+1}", "ytcut_noop")]
        if i > 0:
            row.append(kb_btn("🔼 Up", f"ytcut_move_seg#{task_id}#{i}#up"))
        else:
            row.append(kb_btn("➖", "ytcut_noop"))
            
        if i < len(segments) - 1:
            row.append(kb_btn("🔽 Down", f"ytcut_move_seg#{task_id}#{i}#down"))
        else:
            row.append(kb_btn("➖", "ytcut_noop"))
        
        buttons.append(row)

    buttons.append([
        kb_btn("⏳ Reset (Urut Waktu)", f"ytcut_sort_segments#{task_id}"),
        kb_btn("« Back", f"ytcut_back#{task_id}")
    ])

    text = (
        f"<blockquote expandable>"
        f"🔄 <b>Ubah Susunan Potongan</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{'\n'.join(seg_list_text)}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Gunakan tombol Panah untuk menggeser posisi potongan dalam video akhir.</i>\n"
        f"</blockquote>"
    )

    await _edit_ytcut_state_message(c, cb, state, text, InlineKeyboardMarkup(buttons))
    asyncio.create_task(sync_ytcut_task(task_id))
    await cb.answer()


@Altruix.bot.on_callback_query(filters.regex(r"^ytcut_move_seg#([\w-]+)#(\d+)#(up|down)$"))
@iuser_check
@log_errors
async def ytcut_move_seg_cb(c: Any, cb: CallbackQuery):
    task_id, idx_str, direction = cb.matches[0].groups()
    idx = int(idx_str)
    state = await get_ytcut_task_state(task_id)
    if not state:
        return await cb.answer("Sesi tidak ditemukan.", show_alert=True)

    now = time.time()
    if state.get("_busy_until", 0) > now:
        return await cb.answer()
    state["_busy_until"] = now + 0.3

    segments = state.get("segments", []).copy()
    if idx < 0 or idx >= len(segments):
        return await cb.answer("Index tidak valid.")

    new_idx = idx - 1 if direction == "up" else idx + 1
    if new_idx < 0 or new_idx >= len(segments):
        return await cb.answer("Sudah di batas.")

    # Swap
    segments[idx], segments[new_idx] = segments[new_idx], segments[idx]
    state["segments"] = segments
    state["_manual_order"] = True # Mark that we have a manual order

    # Refresh reorder menu
    cb.matches = [type("Match", (), {"group": lambda self, n: task_id})()]
    await ytcut_reorder_menu_cb(c, cb)


@Altruix.bot.on_callback_query(filters.regex(r"^ytcut_sort_segments#([\w-]+)$"))
@iuser_check
@log_errors
async def ytcut_sort_segments_cb(c: Any, cb: CallbackQuery):
    task_id = cb.matches[0].group(1)
    state = await get_ytcut_task_state(task_id)
    if not state:
        return await cb.answer("Sesi tidak ditemukan.", show_alert=True)

    now = time.time()
    if state.get("_busy_until", 0) > now:
        return await cb.answer()
    state["_busy_until"] = now + 0.5

    segments = state.get("segments", []).copy()
    segments.sort(key=lambda x: x["start"])
    state["segments"] = segments
    state.pop("_manual_order", None) # Remove manual order flag

    # Refresh reorder menu
    cb.matches = [type("Match", (), {"group": lambda self, n: task_id})()]
    await ytcut_reorder_menu_cb(c, cb)
    await cb.answer("Susunan direset ke urutan waktu (Default).")


@Altruix.bot.on_callback_query(filters.regex(r"^ytcut_noop$"))
async def ytcut_noop_cb(c: Any, cb: CallbackQuery):
    await cb.answer()


@Altruix.bot.on_callback_query(filters.regex(r"^ytcut_add#([\w-]+)$"))
@iuser_check
@log_errors
async def ytcut_add_cb(c: Any, cb: CallbackQuery):
    ensure_ytcut_state_registry()
    task_id = cb.matches[0].group(1)
    state = await get_ytcut_task_state(task_id)
    if not state:
        return await cb.answer("Sesi tidak ditemukan.", show_alert=True)
    prompt = (
        "🎬 YouTube Cut Tool\n\n"
        "Balas pesan ini dengan format timestamp.\n"
        "Contoh:\n"
        "01:07 - 01:33\n"
        "01:58 - 02:39\n"
        "03:30 - 03:58\n"
        "04:50 - 05:20\n"
        "Gunakan satu baris untuk setiap potongan.\n"
        "Gunakan format HH:MM:SS jika diperlukan."
    )
    prompt_markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("❌ Batalkan input", callback_data=f"ytcut_input_cancel#{task_id}")]]
    )
    try:
        if cb.inline_message_id:
            state["inline_message_id"] = cb.inline_message_id

        if getattr(cb, "message", None) is not None:
            prompt_msg = await cb.message.reply_text(
                prompt,
                reply_markup=prompt_markup,
                parse_mode=enums.ParseMode.HTML,
            )
        else:
            # Some callback queries may lack a message (inline contexts). Send prompt via client to chat_id.
            # Fallback to private chat if the bot is not in the group/channel.
            chat_id = state.get("chat_id")
            try:
                prompt_msg = await c.send_message(
                    chat_id=chat_id,
                    text=prompt,
                    reply_markup=prompt_markup,
                    parse_mode=enums.ParseMode.HTML,
                )
            except (PeerIdInvalid, errors.Forbidden, errors.ChatAdminRequired):
                # Fallback to private chat with the user
                prompt_msg = await c.send_message(
                    chat_id=cb.from_user.id,
                    text=f"{prompt}\n\n<i>(Pesan ini dikirim ke chat pribadi karena bot tidak berada di grup asal)</i>",
                    reply_markup=prompt_markup,
                    parse_mode=enums.ParseMode.HTML,
                )
                # Pisahkan cb.answer() dari inner try-except untuk mencegah double message
                # jika cb.answer() throws exception
                try:
                    await cb.answer("Silakan cek chat pribadi bot untuk menambah potongan.", show_alert=True)
                except Exception as cb_err:
                    Altruix.log(f"YTcut callback answer failed (non-critical): {cb_err}")
            except Exception as e:
                # Last resort: just try to send to user ID anyway
                prompt_msg = await c.send_message(
                    chat_id=cb.from_user.id,
                    text=prompt,
                    reply_markup=prompt_markup,
                    parse_mode=enums.ParseMode.HTML,
                )
        state["prompt_message_id"] = prompt_msg.id
        Altruix.log(f"YTcut manual input prompt sent: task_id={task_id}, prompt_id={prompt_msg.id}, chat_id={prompt_msg.chat.id}")
        asyncio.create_task(sync_ytcut_task(task_id))
        await cb.answer()
    except Exception as e:
        Altruix.log(f"YTcut add prompt send failed: {e}\n{traceback.format_exc()}")
        try:
            await cb.answer("Gagal membuat prompt. Coba lagi.", show_alert=True)
        except Exception:
            pass


@Altruix.bot.on_callback_query(filters.regex(r"^ytcut_toggle_mode#([\w-]+)$"))
@iuser_check
@log_errors
async def ytcut_toggle_mode_cb(c: Any, cb: CallbackQuery):
    task_id = cb.matches[0].group(1)
    state = await get_ytcut_task_state(task_id)
    if not state:
        return await cb.answer("Sesi tidak ditemukan.", show_alert=True)
    
    now = time.time()
    if state.get("_busy_until", 0) > now:
        return await cb.answer()
    state["_busy_until"] = now + 0.5

    if cb.inline_message_id:
        state["inline_message_id"] = cb.inline_message_id
    state["mode"] = "remove" if state["mode"] == "keep" else "keep"
    save_ytcut_user_config(state.get("user_id"), {"mode": state["mode"]})
    await update_ytcut_dashboard_message(c, state)
    asyncio.create_task(sync_ytcut_task(task_id))
    await cb.answer(f"Mode diubah ke {state['mode'].upper()}.")


@Altruix.bot.on_callback_query(filters.regex(r"^ytcut_toggle_extract#([\w-]+)$"))
@iuser_check
@log_errors
async def ytcut_toggle_extract_cb(c: Any, cb: CallbackQuery):
    task_id = cb.matches[0].group(1)
    state = await get_ytcut_task_state(task_id)
    if not state:
        return await cb.answer("Sesi tidak ditemukan.", show_alert=True)

    now = time.time()
    if state.get("_busy_until", 0) > now:
        return await cb.answer()
    state["_busy_until"] = now + 0.5

    if cb.inline_message_id:
        state["inline_message_id"] = cb.inline_message_id
    state["extract"] = "audio" if state["extract"] == "video" else "video"
    save_ytcut_user_config(state.get("user_id"), {"extract": state["extract"]})
    await update_ytcut_dashboard_message(c, state)
    asyncio.create_task(sync_ytcut_task(task_id))
    await cb.answer(f"Ekstrak diubah ke {state['extract'].upper()}.")


@Altruix.bot.on_callback_query(filters.regex(r"^ytcut_cycle_quality#([\w-]+)$"))
@iuser_check
@log_errors
async def ytcut_cycle_quality_cb(c: Any, cb: CallbackQuery):
    task_id = cb.matches[0].group(1)
    state = await get_ytcut_task_state(task_id)
    if not state:
        return await cb.answer("Sesi tidak ditemukan.", show_alert=True)

    now = time.time()
    if state.get("_busy_until", 0) > now:
        return await cb.answer()
    state["_busy_until"] = now + 0.5

    if cb.inline_message_id:
        state["inline_message_id"] = cb.inline_message_id
    current = state.get("quality", "720")
    try:
        idx = ["360", "480", "720", "1080"].index(current)
    except ValueError:
        idx = 0
    state["quality"] = ["360", "480", "720", "1080"][(idx + 1) % 4]
    save_ytcut_user_config(state.get("user_id"), {"quality": state["quality"]})
    await update_ytcut_dashboard_message(c, state)
    asyncio.create_task(sync_ytcut_task(task_id))
    await cb.answer(f"Kualitas diubah ke {state['quality']}p.")


@Altruix.bot.on_callback_query(filters.regex(r"^ytcut_remove#([\w-]+)#(\d+)$"))
@iuser_check
@log_errors
async def ytcut_remove_cb(c: Any, cb: CallbackQuery):
    task_id = cb.matches[0].group(1)
    idx = int(cb.matches[0].group(2))
    state = await get_ytcut_task_state(task_id)
    if not state:
        return await cb.answer("Sesi tidak ditemukan.", show_alert=True)
    
    now = time.time()
    if state.get("_busy_until", 0) > now:
        return await cb.answer()
    state["_busy_until"] = now + 0.3

    if cb.inline_message_id:
        state["inline_message_id"] = cb.inline_message_id
    if idx < 0 or idx >= len(state["segments"]):
        return await cb.answer("Index potongan tidak valid.", show_alert=True)
    state["segments"].pop(idx)
    
    if len(state["segments"]) < 2:
        state.pop("_manual_order", None)

    await update_ytcut_dashboard_message(c, state)
    asyncio.create_task(sync_ytcut_task(task_id))
    await cb.answer("Potongan dihapus.")


@Altruix.bot.on_callback_query(filters.regex(r"^ytcut_cancel#([\w-]+)$"))
@iuser_check
@log_errors
async def ytcut_cancel_cb(c: Any, cb: CallbackQuery):
    task_id = cb.matches[0].group(1)
    state = getattr(Altruix, "YTCUT_STATE", {}).pop(task_id, None)
    asyncio.create_task(delete_ytcut_task(task_id))
    if state and state.get("dashboard_message_id"):
        try:
            await c.delete_messages(chat_id=state["chat_id"], message_ids=[state["dashboard_message_id"]])
        except Exception:
            pass
    await cb.answer("Sesi YTcut dibatalkan.")


@Altruix.bot.on_callback_query(filters.regex(r"^ytcut_input_cancel#([\w-]+)$"))
@iuser_check
@log_errors
async def ytcut_input_cancel_cb(c: Any, cb: CallbackQuery):
    task_id = cb.matches[0].group(1)
    state = await get_ytcut_task_state(task_id)
    if not state:
        return await cb.answer("Sesi tidak ditemukan.", show_alert=True)
    state["prompt_message_id"] = None
    asyncio.create_task(sync_ytcut_task(task_id))
    try:
        if getattr(cb, "message", None) is not None:
            await cb.edit_message_text("❌ Input manual dibatalkan.", reply_markup=None)
    except Exception as e:
        Altruix.log(f"YTcut input cancel failed: {e}\n{traceback.format_exc()}")
    await cb.answer("Input manual dibatalkan.")


@Altruix.bot.on_callback_query(filters.regex(r"^ytcut_start#([\w-]+)$"))
@iuser_check
@log_errors
async def ytcut_start_cb(c: Any, cb: CallbackQuery):
    task_id = cb.matches[0].group(1)
    state = await get_ytcut_task_state(task_id)
    if not state:
        return await cb.answer("Sesi tidak ditemukan.", show_alert=True)
    if state["mode"] == "keep" and not state["segments"]:
        return await cb.answer("Tambahkan potongan terlebih dahulu pada mode KEEP.", show_alert=True)
    Altruix.log(
        f"YTcut start requested: task_id={task_id} user_id={cb.from_user.id if cb.from_user else 'unknown'} mode={state.get('mode')} extract={state.get('extract')} quality={state.get('quality')} segments={len(state.get('segments', []))}",
        level=logging.INFO,
    )
    # Ask for user confirmation before enqueueing the run
    try:
        user_style = get_user_button_style(state.get("user_id"))
    except Exception:
        user_style = None

    def _kb_btn(text: str, cb: str):
        if user_style is not None:
            return InlineKeyboardButton(text, callback_data=cb, style=user_style)
        return InlineKeyboardButton(text, callback_data=cb)

    confirm_kb = InlineKeyboardMarkup([[
        _kb_btn("✅ Ya, mulai", f"ytcut_confirm_yes#{task_id}"),
        _kb_btn("❌ Batal", f"ytcut_confirm_no#{task_id}"),
    ]])

    confirm_text = (
        "<blockquote expandable>"
        "❗️ <b>Konfirmasi</b>\n"
        "Apakah Anda yakin ingin memulai proses YTcut? Ini akan menempatkan tugas Anda ke antrean pemrosesan."
        "</blockquote>"
    )
    try:
        if cb.inline_message_id:
            state["inline_message_id"] = cb.inline_message_id
        
        inline_id = state.get("inline_message_id")
        # Try to edit the dashboard message if present
        if (cb.inline_message_id and cb.inline_message_id == inline_id) or \
           (cb.message and state.get("dashboard_message_id") == cb.message.id):
            try:
                await cb.edit_message_caption(
                    caption=confirm_text,
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=confirm_kb,
                )
            except Exception:
                await cb.edit_message_text(
                    text=confirm_text,
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=confirm_kb,
                )
        elif inline_id:
            try:
                if hasattr(c, "edit_inline_caption"):
                    await c.edit_inline_caption(
                        inline_message_id=inline_id,
                        caption=confirm_text,
                        parse_mode=enums.ParseMode.HTML,
                        reply_markup=confirm_kb,
                    )
                else:
                    await c.edit_message_caption(
                        inline_message_id=inline_id,
                        caption=confirm_text,
                        parse_mode=enums.ParseMode.HTML,
                        reply_markup=confirm_kb,
                    )
            except Exception:
                if hasattr(c, "edit_inline_text"):
                    await c.edit_inline_text(
                        inline_message_id=inline_id,
                        text=confirm_text,
                        parse_mode=enums.ParseMode.HTML,
                        reply_markup=confirm_kb,
                    )
                else:
                    await c.edit_message_text(
                        inline_message_id=inline_id,
                        text=confirm_text,
                        parse_mode=enums.ParseMode.HTML,
                        reply_markup=confirm_kb,
                    )
        elif state.get("dashboard_message_id"):
            try:
                await c.edit_message_caption(
                    chat_id=state["chat_id"],
                    message_id=state["dashboard_message_id"],
                    caption=confirm_text,
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=confirm_kb,
                )
            except Exception:
                await c.edit_message_text(
                    chat_id=state["chat_id"],
                    message_id=state["dashboard_message_id"],
                    text=confirm_text,
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=confirm_kb,
                )
        else:
            chat_id = state.get("chat_id")
            try:
                await c.send_message(chat_id=chat_id, text=confirm_text, parse_mode=enums.ParseMode.HTML, reply_markup=confirm_kb)
            except (PeerIdInvalid, errors.Forbidden, errors.ChatAdminRequired):
                await c.send_message(chat_id=cb.from_user.id, text=confirm_text, parse_mode=enums.ParseMode.HTML, reply_markup=confirm_kb)
                await cb.answer("Konfirmasi dikirim ke chat pribadi.", show_alert=True)
        await cb.answer()
        asyncio.create_task(sync_ytcut_task(task_id))
    except Exception as e:
        if isinstance(e, MessageNotModified):
            return await cb.answer()
        Altruix.log(f"YTcut start confirmation failed: {e}\n{traceback.format_exc()}")
        try:
            await cb.answer("Gagal menampilkan konfirmasi. Coba lagi.", show_alert=True)
        except Exception:
            pass


@Altruix.bot.on_callback_query(filters.regex(r"^ytcut_confirm_yes#([\w-]+)$"))
@iuser_check
@log_errors
async def ytcut_confirm_yes_cb(c: Any, cb: CallbackQuery):
    task_id = cb.matches[0].group(1)
    state = await get_ytcut_task_state(task_id)
    if not state:
        return await cb.answer("Sesi tidak ditemukan.", show_alert=True)
    
    # Add entry logging after state retrieval with task_id, user_id, chat_id, url
    Altruix.log(
        f"YTcut callback confirm: task_id={task_id} user_id={cb.from_user.id if cb.from_user else 'unknown'} "
        f"chat_id={state.get('chat_id')} url={state.get('url')}",
        level=logging.INFO,
    )
    
    await cb.answer("Menempatkan tugas Anda ke antrean proses...")
    
    # Update UI immediately to show it's starting
    try:
        await cb.edit_message_caption(
            caption="⏳ <b>Memulai proses YTcut...</b>\nMohon tunggu hingga proses download dimulai.",
            parse_mode=enums.ParseMode.HTML
        )
    except MessageNotModified:
        # Nothing to change; user already saw the same caption.
        try:
            return await cb.answer()
        except Exception:
            return
    except Exception as e:
        Altruix.log(f"[YTcut] Failed to edit message caption: {html.escape(str(e))}\n{traceback.format_exc()}")
        try:
            await cb.edit_message_text(
                text="⏳ <b>Memulai proses YTcut...</b>\nMohon tunggu hingga proses download dimulai.",
                parse_mode=enums.ParseMode.HTML,
            )
        except MessageNotModified:
            try:
                return await cb.answer()
            except Exception:
                return
        except Exception as inner_e:
            Altruix.log(f"[YTcut] Failed to edit message text fallback: {html.escape(str(inner_e))}\n{traceback.format_exc()}")

    # Run in background to avoid blocking the callback handler
    # And register to xtaskmanager so it's visible in .tasklist
    # Wrap enqueue_ytcut_run call with try-except
    try:
        task = asyncio.create_task(enqueue_ytcut_run(task_id, c))
        Altruix.log(
            f"YTcut task enqueued: task_id={task_id} user_id={cb.from_user.id if cb.from_user else 'unknown'}",
            level=logging.INFO,
        )
        def _ytcut_enqueue_done(t):
            if t.cancelled():
                Altruix.log(
                    f"YTcut enqueue task cancelled: task_id={task_id}",
                    level=logging.INFO,
                )
                return
            exc = t.exception()
            if exc:
                Altruix.log(
                    f"YTcut enqueue task exception: task_id={task_id} user_id={cb.from_user.id if cb.from_user else 'unknown'} error={exc}\n"
                    + "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
                    level=logging.INFO,
                )
        task.add_done_callback(_ytcut_enqueue_done)
    except Exception as e:
        Altruix.log(
            f"YTcut enqueue failed: task_id={task_id} user_id={cb.from_user.id if cb.from_user else 'unknown'} error={e}\n{traceback.format_exc()}",
            level=logging.INFO,
        )
        await cb.edit_message_caption(
            caption=f"❌ <b>Gagal memulai proses YTcut:</b> <code>{html.escape(str(e))}</code>",
            parse_mode=enums.ParseMode.HTML
        )
        return


@Altruix.bot.on_callback_query(filters.regex(r"^ytcut_merge_decision#([\w-]+)$"))
@iuser_check
@log_errors
async def ytcut_merge_decision_cb(c: Any, cb: CallbackQuery):
    """
    Handle merge decision button click. Shows Yes/No confirmation for merge.
    """
    task_id = cb.matches[0].group(1)
    state = await get_ytcut_task_state(task_id)
    if not state:
        return await cb.answer("Sesi tidak ditemukan.", show_alert=True)
    
    segments = state.get("segments", [])
    if len(segments) < 2:
        return await cb.answer("Minimal 2 segmen diperlukan untuk merge.", show_alert=True)
    
    # Check if segment files exist
    task_tmp_dir = os.path.join(YTCUT_TEMP_DIR, task_id)
    if not os.path.exists(task_tmp_dir):
        return await cb.answer(
            "File segmen tidak ditemukan. Jalankan 'MULAI PROSES' terlebih dahulu untuk membuat file segmen.",
            show_alert=True
        )
    
    try:
        part_files = [f for f in os.listdir(task_tmp_dir) if f.startswith("part_")]
    except Exception as list_err:
        return await cb.answer(
            f"Gagal mengakses file segmen: {str(list_err)[:100]}",
            show_alert=True
        )
    
    if not part_files:
        return await cb.answer(
            "File segmen tidak ditemukan. Jalankan 'MULAI PROSES' terlebih dahulu untuk membuat file segmen.",
            show_alert=True
        )
    
    Altruix.log(
        f"YTcut merge decision requested: task_id={task_id} user_id={cb.from_user.id if cb.from_user else 'unknown'} "
        f"segments_count={len(segments)} chat_id={state.get('chat_id')}"
    )
    
    try:
        user_style = get_user_button_style(state.get("user_id"))
    except Exception:
        user_style = None

    def _kb_btn(text: str, cb: str):
        if user_style is not None:
            return InlineKeyboardButton(text, callback_data=cb, style=user_style)
        return InlineKeyboardButton(text, callback_data=cb)

    merge_kb = InlineKeyboardMarkup([[
        _kb_btn("✅ Ya, Merge", f"ytcut_merge_yes#{task_id}"),
        _kb_btn("❌ Batal", f"ytcut_back#{task_id}"),
    ]])

    merge_text = (
        "<blockquote expandable>"
        f"🔀 <b>Merge Semua Segmen?</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Segmen yang akan digabung:</b> <code>{len(segments)}</code>\n"
        f"<b>Mode Saat Ini:</b> <code>{state['mode'].upper()}</code>\n"
        f"<b>Format:</b> <code>{'VIDEO' if state['extract']=='video' else 'AUDIO ONLY'}</code>\n"
        f"<b>Kualitas:</b> <code>{state['quality']}p</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Proses merge akan menggabungkan semua {len(segments)} segmen menjadi 1 video "
        f"tanpa re-encoding (hanya concat).</i>\n"
        f"</blockquote>"
    )
    
    try:
        if cb.inline_message_id:
            state["inline_message_id"] = cb.inline_message_id
        
        await _edit_ytcut_state_message(c, cb, state, merge_text, merge_kb)
        await cb.answer()
        asyncio.create_task(sync_ytcut_task(task_id))
        
        Altruix.log(
            f"YTcut merge decision confirmation shown: task_id={task_id} user_id={cb.from_user.id if cb.from_user else 'unknown'}"
        )
    except Exception as e:
        if isinstance(e, MessageNotModified):
            return await cb.answer()
        Altruix.log(f"YTcut merge decision confirmation failed: task_id={task_id} error={e}\n{traceback.format_exc()}")
        try:
            await cb.answer("Gagal menampilkan konfirmasi merge. Coba lagi.", show_alert=True)
        except Exception:
            pass


@Altruix.bot.on_callback_query(filters.regex(r"^ytcut_merge_yes#([\w-]+)$"))
@iuser_check
@log_errors
async def ytcut_merge_yes_cb(c: Any, cb: CallbackQuery):
    """
    Confirm merge decision and start merge process.
    """
    task_id = cb.matches[0].group(1)
    state = await get_ytcut_task_state(task_id)
    if not state:
        return await cb.answer("Sesi tidak ditemukan.", show_alert=True)
    
    segments = state.get("segments", [])
    if len(segments) < 2:
        return await cb.answer("Minimal 2 segmen diperlukan untuk merge.", show_alert=True)
    
    Altruix.log(
        f"YTcut merge confirmed: task_id={task_id} user_id={cb.from_user.id if cb.from_user else 'unknown'} "
        f"segments_count={len(segments)} chat_id={state.get('chat_id')}"
    )
    
    await cb.answer("Memulai proses merge segmen...")
    
    try:
        # Update state to indicate merge in progress
        state["merge_in_progress"] = True
        state["merge_start_time"] = time.time()
        await sync_ytcut_task(task_id)
        
        # Run merge in background
        async def _merge_and_send():
            try:
                # Perform merge
                merged_file = await merge_ytcut_segments(state, c)
                
                # Prepare caption for merged file
                caption = (
                    f"🎬 <b>Merge Segmen Selesai</b>\n"
                    f"<b>• Judul:</b> {html.escape(state['title'])}\n"
                    f"<b>• Mode:</b> <code>{state['mode'].upper()}</code>\n"
                    f"<b>• Ekstrak:</b> <code>{'VIDEO' if state['extract']=='video' else 'AUDIO ONLY'}</code>\n"
                    f"<b>• Segmen Digabung:</b> <code>{len(segments)}</code>\n"
                    f"<b>• Kualitas:</b> <code>{state['quality']}p</code>\n"
                    f"<b>• Source:</b> <code>{html.escape(state['url'])}</code>\n"
                )
                
                # Send merged file
                thumb_path = None
                thumb_dir = os.path.join(YTCUT_TEMP_DIR, task_id)
                if os.path.exists(os.path.join(thumb_dir, "thumb.jpg")):
                    thumb_path = os.path.join(thumb_dir, "thumb.jpg")
                
                try:
                    if state["extract"] == "video":
                        await c.send_video(
                            chat_id=state["chat_id"],
                            video=merged_file,
                            caption=caption,
                            parse_mode=enums.ParseMode.HTML,
                            supports_streaming=True,
                            thumb=thumb_path,
                            reply_to_message_id=state.get("reply_to"),
                        )
                    else:
                        await c.send_audio(
                            chat_id=state["chat_id"],
                            audio=merged_file,
                            caption=caption,
                            parse_mode=enums.ParseMode.HTML,
                            thumb=thumb_path,
                            reply_to_message_id=state.get("reply_to"),
                        )
                    
                    Altruix.log(
                        f"YTcut merge result sent: task_id={task_id} user_id={state.get('user_id')} "
                        f"chat_id={state.get('chat_id')} extract={state['extract']}"
                    )
                    
                except errors.PeerIdInvalid as erpeer:
                    Altruix.log(
                        f"YCut merge send failed (PeerIdInvalid, likely bot not in chat): task_id={task_id} user-id={state.get('user_id')} chat_id={state.get('chat_id')} error={erpeer}"
                    )
                    fallback_chat = state.get("user_id")
                    if fallback_chat:
                        if state["extract"] == "video":
                            await c.send_video(
                                chat_id=fallback_chat,
                                video=merged_file,
                                caption=caption,
                                parse_mode=enums.ParseMode.HTML,
                                supports_streaming=True,
                                thumb=thumb_path,
                            )
                        else:
                            await c.send_audio(
                                chat_id=fallback_chat,
                                audio=merged_file,
                                caption=caption,
                                parse_mode=enums.ParseMode.HTML,
                                thumb=thumb_path,
                            )
                        
                        Altruix.log(
                            f"YTcut merge result sent to fallback: task_id={task_id} "
                            f"fallback_user_id={fallback_chat}"
                        )
                
                # Update state
                state["merge_in_progress"] = False
                state["merge_completed"] = True
                state["merge_end_time"] = time.time()
                await sync_ytcut_task(task_id)
                
                Altruix.log(
                    f"YTcut merge flow complete: task_id={task_id} user_id={state.get('user_id')} "
                    f"merge_time={(state.get('merge_end_time', 0) - state.get('merge_start_time', 0)):.2f}s"
                )
                
            except Exception as merge_err:
                tb_text = traceback.format_exc()
                Altruix.log(
                    f"YTcut merge flow failed: task_id={task_id} user_id={state.get('user_id')} "
                    f"error={merge_err}\n{tb_text}"
                )
                
                state["merge_in_progress"] = False
                state["merge_error"] = str(merge_err)
                await sync_ytcut_task(task_id)
                
                try:
                    error_text = (
                        f"❌ <b>Merge gagal:</b>\n"
                        f"<code>{html.escape(str(merge_err)[:200])}</code>"
                    )
                    await c.send_message(
                        chat_id=state.get("chat_id"),
                        text=error_text,
                        parse_mode=enums.ParseMode.HTML,
                        reply_to_message_id=state.get("reply_to"),
                    )
                except Exception as send_err:
                    Altruix.log(f"YTcut merge error notification failed: {send_err}")
        
        merge_task = asyncio.create_task(_merge_and_send())
        
        try:
            from Main.plugins.userbot.xtaskmanager import register_task
            register_task(
                task_id=task_id,
                asyncio_task=merge_task,
                name=f"YTcut: {state.get('title', 'Unknown Video')[:30]}",
                plugin="xytcut",
                user_id=cb.from_user.id,
                details=f"URL: {state.get('url')}\nMode: {state.get('mode', 'keep').upper()}\nSegments: {len(state.get('segments', []))}"
            )
            Altruix.log(f"YTcut task registered to xtaskmanager: task_id={task_id}")
        except Exception as e:
            Altruix.log(f"[YTcut] Failed to register task in xtaskmanager: {e}")
    except Exception as e:
        Altruix.log(f"YTcut merge yes callback failed: task_id={task_id} error={e}\n{traceback.format_exc()}")
        try:
            await cb.answer(f"Gagal memulai merge: {str(e)[:100]}", show_alert=True)
        except Exception as e2:
            Altruix.log(f"YTcut merge yes callback answer failed: {e2}")
            pass


@Altruix.bot.on_callback_query(filters.regex(r"^ytcut_confirm_no#([\w-]+)$"))
@iuser_check
@log_errors
async def ytcut_confirm_no_cb(c: Any, cb: CallbackQuery):
    task_id = cb.matches[0].group(1)
    state = await get_ytcut_task_state(task_id)
    if not state:
        return await cb.answer("Sesi tidak ditemukan.", show_alert=True)
    if cb.inline_message_id:
        state["inline_message_id"] = cb.inline_message_id
    # Restore dashboard
    try:
        await update_ytcut_dashboard_message(c, state)
        asyncio.create_task(sync_ytcut_task(task_id))
        await cb.answer("Dibatalkan.")
    except Exception as e:
        Altruix.log(f"YTcut cancel confirmation failed: {e}\n{traceback.format_exc()}")
        try:
            await cb.answer("Gagal mengembalikan dashboard. Periksa log.", show_alert=True)
        except Exception:
            pass


@Altruix.bot.on_message(filters.text & (filters.reply | filters.private))
@log_errors
async def ytcut_reply_handler(c: Any, m: Message):
    state = None
    if m.reply_to_message:
        state = find_ytcut_state_by_prompt_message_id(m.reply_to_message.id)
    if not state and m.chat.type == enums.ChatType.PRIVATE and getattr(m.from_user, "id", None) is not None:
        state = find_ytcut_state_by_user_id(m.from_user.id)
    if not state:
        return
    try:
        text = m.text.strip()
        lowered = text.lower()
        if lowered in {"cancel", "batal"}:
            state["prompt_message_id"] = None
            asyncio.create_task(sync_ytcut_task(state.get("task_id")))
            return await m.reply_text("❌ Input manual dibatalkan.")

        new_segments = parse_ytcut_manual_segments(text)
        if not new_segments:
            raise ValueError("Tidak ada timestamp yang valid.")

        segments = state.get("segments", []).copy()
        edit_idx = state.get("edit_index")

        if edit_idx is not None and 0 <= edit_idx < len(segments):
            if len(new_segments) != 1:
                raise ValueError("Saat mengedit, masukkan hanya satu baris timestamp.")
            segments[edit_idx] = new_segments[0]
            success_msg = f"✅ Potongan #{edit_idx + 1} berhasil diperbarui."
        else:
            segments.extend(new_segments)
            if len(new_segments) == 1:
                success_msg = f"✅ Potongan berhasil ditambahkan: {format_ytcut_timestamp(new_segments[0]['start'])} - {format_ytcut_timestamp(new_segments[0]['end'])}"
            else:
                success_msg = f"✅ {len(new_segments)} potongan berhasil ditambahkan."

        if not state.get("_manual_order"):
            segments.sort(key=lambda x: x["start"])

        if any(seg["end"] > state["duration"] for seg in segments):
            raise ValueError("Timestamp akhir melebihi durasi video.")
        if ytcut_segments_overlap(segments):
            raise ValueError("Potongan tumpang tindih. Periksa input Anda.")

        state["segments"] = segments
        state["prompt_message_id"] = None
        # Clear edit state if manual input was used during edit mode
        state.pop("edit_index", None)
        state.pop("add_start", None)
        state.pop("add_end", None)
        state.pop("add_target", None)

        await update_ytcut_dashboard_message(c, state)
        asyncio.create_task(sync_ytcut_task(state.get("task_id")))
        await m.reply_text(success_msg)
    except Exception as e:
        Altruix.log(f"YTcut reply handler failed: {e}\n{traceback.format_exc()}")
        await m.reply_text(f"❌ Gagal memproses timestamp: {html.escape(str(e))}")


async def init_ytcut_persistence():
    import sys as _sys
    if hasattr(_sys, "_ytcut_persistence_initialized"):
        return
    setattr(_sys, "_ytcut_persistence_initialized", True)
    await asyncio.sleep(5)
    try:
        ensure_ytcut_state_registry()
        col = Altruix.local_db.make_collection("ytcut_tasks")
        async for task_data in col.find({}):
            task_id = task_data.get("_id")
            if not task_id:
                continue
            if isinstance(task_data, dict):
                task_data.pop("_id", None)
                Altruix.YTCUT_STATE[task_id] = task_data
    except Exception as e:
        Altruix.log(f"YTcut persistence init failed: {e}\n{traceback.format_exc()}")


asyncio.create_task(init_ytcut_persistence())


@Altruix.bot.on_callback_query(filters.regex(r"^ytcut_busy$"))
async def ytcut_busy_cb(c: Any, cb: CallbackQuery):
    await cb.answer("Tunggu proses yang sedang berjalan hingga selesai.")
