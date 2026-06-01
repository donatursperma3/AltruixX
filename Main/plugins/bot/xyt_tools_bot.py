# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.

PLUGIN_VERSION = "1.0.174"

import asyncio
import httpx
import os
import traceback
from typing import Union
from Main.utils.file_helpers import get_user_button_style
from pyrogram import Client, filters, enums
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, 
    CallbackQuery, InlineQuery, InputTextMessageContent, 
    InlineQueryResultArticle, InlineQueryResultPhoto
)
from Main import Altruix
from Main.utils.essentials import Essentials
from Main.core.decorators import iuser_check
from Main.internals.ytdl_core import ytdl_engine, sync_ytdl_task, format_count, format_yt_date, YTDL_CORE_VERSION

LOGO_PATH = "Main/assets/images/logo.jpg"

def _ytdl_fmt_time(seconds) -> str:
    try:
        sec = float(seconds or 0)
    except Exception:
        sec = 0.0
    if sec < 0:
        sec = 0.0
    whole = int(sec)
    frac = round(sec - whole, 2)
    base = Essentials.get_readable_time(whole) or "0s"
    if abs(frac) < 0.005:
        return base
    if "," in base:
        left, right = base.split(", ", 1)
        base = right
        prefix = f"{left}, "
    else:
        prefix = ""
    parts = base.split(":")
    last = parts[-1]
    if not last.endswith("s"):
        return prefix + base
    try:
        last_num = int(last[:-1] or "0")
    except Exception:
        last_num = 0
    new_val = last_num + frac
    new_txt = f"{new_val:.2f}".rstrip("0").rstrip(".")
    parts[-1] = f"{new_txt}s"
    return prefix + ":".join(parts)

async def get_logo_url():
    """Auto-uploads local logo asset to Telegraph and caches the URL."""
    if hasattr(Altruix, "_YTDL_LOGO_URL") and Altruix._YTDL_LOGO_URL:
        return Altruix._YTDL_LOGO_URL
    
    if not os.path.exists(LOGO_PATH):
        # Global fallback if file doesn't exist
        return "https://telegra.ph/file/0c6f5a3e1445790c9b0e2.jpg"

    try:
        async with httpx.AsyncClient() as client:
            files = {'file': ('logo.jpg', open(LOGO_PATH, 'rb'), 'image/jpeg')}
            r = await client.post("https://telegra.ph/upload", files=files)
            res = r.json()
            if isinstance(res, list) and len(res) > 0:
                Altruix._YTDL_LOGO_URL = f"https://telegra.ph{res[0]['src']}"
                return Altruix._YTDL_LOGO_URL
    except Exception as e:
        Altruix.log(f"Logo Auto-Upload Error: {e}")
    
    return "https://telegra.ph/file/0c6f5a3e1445790c9b0e2.jpg"

@Altruix.bot.on_inline_query(filters.regex(r"^ytdl_menu#([#\w]+)"))
@iuser_check
@Altruix.bot.on_inline_query(filters.regex(r"^ytdl_menu#([#\w]+)"))
@iuser_check
async def ytdl_inline_menu(c: Client, obj: Union[InlineQuery, CallbackQuery], task_id: str = None):
    if not task_id:
        task_id = obj.matches[0].group(1)
    state = Altruix.YTDL_STATE.get(task_id)
    
    # helper for checking query type
    is_iq = isinstance(obj, InlineQuery)
    
    if not state:
        if is_iq:
            return await obj.answer([InlineQueryResultArticle(
                title="Sesi Kedaluwarsa",
                input_message_content=InputTextMessageContent("❌ Sesi ini telah kedaluwarsa. Silakan ulang perintah .ytdl")
            )], cache_time=0)
        else:
            return await obj.answer("Sesi kedaluwarsa.", show_alert=True)
            
    # ✅ CAPTURE MESSAGE ID: Store the ID of the dashboard message for persistence recovery.
    if not is_iq and not state.get("message_id") and obj.message:
        state["message_id"] = obj.message.id
        await sync_ytdl_task(task_id)
            
    is_playlist = state.get("type") == "playlist"
    dur_str = Essentials.get_readable_time(state["duration"]) if not is_playlist else f"{state['count']} Videos"
     # ✅ AUDIO TRACK: Detect and display the selected language
    audio_langs = state.get("languages") or []
    current_lang = state.get("audio_lang", "Default").upper()
    has_multi_audio = len(audio_langs) > 1
    
    chapters = state.get("chapters") or []
    chapters_str = "" if is_playlist else f"<b>• Split Chapters:</b> <code>{'Yes' if state.get('split_chapters', False) else 'No'} ({len(chapters)} bab terdeteksi)</code>\n"
    
    platform = state.get("extractor", "YouTube").capitalize()
    source_url = state.get("url", "Unknown")

    text = (
        f"<blockquote expandable>"
        f"<b>🎬 YouTube Tools {'(Playlist)' if is_playlist else ''}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>• Judul:</b> {state['title']}\n"
        f"<b>• {'Total' if is_playlist else 'Durasi'}:</b> {dur_str}\n"
        f"<b>• Playlist:</b> {'✅ Yes' if is_playlist else '❌ No'}\n"
        f"<b>• Channel:</b> {state.get('uploader', 'Unknown')} ({format_count(state.get('subscribers'))} subs)\n"
        f"<b>• Views:</b> {format_count(state.get('views', 0))}\n"
        f"<b>• Year:</b> {format_yt_date(state.get('upload_date'))}\n"
        f"<b>• Platform:</b> <code>{platform}</code>\n"
        f"<b>• Audio Lang:</b> <code>{current_lang}</code>\n"
        f"<b>• Speed:</b> <code>{state.get('speed', '1.0x')}</code>\n"
        f"<b>• Volume:</b> <code>{state.get('volume', 'Original')}</code>\n"
        f"<b>• Fade:</b> <code>IN {_ytdl_fmt_time(state.get('fade_in', 0))} | OUT {_ytdl_fmt_time(state.get('fade_out', 0))}</code>\n"
        f"{chapters_str}"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>🔗 Source:</b> <code>{source_url}</code>\n"
        f"<b>🛠 Task ID:</b> <code>{task_id}</code>\n"
    )
    if is_playlist:
        text += f"<i>Pilih untuk mengunduh seluruh isi playlist atau pilih video tertentu.</i>"
    else:
        text += f"<i>Pilih format yang ingin diunduh atau potong video jika diperlukan.</i>"
    text += f"</blockquote>"
    
    # ✅ OPTIMIZATION: Use cached logo URL sync if available to reduce render lag
    logo_url = getattr(Altruix, "_YTDL_LOGO_URL", None)
    if not logo_url:
        logo_url = await get_logo_url()
    
    # Fix thumb URL (ensure it has protocol)
    raw_thumb = state.get("thumb")
    if raw_thumb and raw_thumb.startswith("//"):
        raw_thumb = f"https:{raw_thumb}"
    
    thumb = raw_thumb if raw_thumb and raw_thumb.startswith("http") else logo_url
    
    user_style = get_user_button_style(obj.from_user.id)
    backup_status = "Yes" if state.get("auto_backup", True) else "No"
    b_mode = state.get("backup_mode", "userbot").capitalize()
    link_status = "Yes" if state.get("show_link", True) else "No"
    desc_status = "Yes" if state.get("show_desc", False) else "No"
    wm_status = "ON" if state.get("watermark", False) else "OFF"
    
    
    s, e = state.get("start", 0), state.get("end", state["duration"])
    trim_text = f"✂️ Trimmer: {_ytdl_fmt_time(s)} - {_ytdl_fmt_time(e)}" if (not is_playlist and (s != 0 or e != state["duration"])) else "✂️ Precise Trimmer"
    
    # Audio formatting texts
    fmt_txt = "Title-Artist" if state.get("audio_name_fmt", "title_artist") == "title_artist" else "Artist-Title"
    src_val = state.get("audio_artist_src", "channel")
    src_txt = "Meta" if src_val == "meta" else "None" if src_val == "none" else "Channel"
 
    aud_row = [
        InlineKeyboardButton(f"🏷 Audio Name: {fmt_txt}", callback_data=f"ytdl_toggle_aname#{task_id}", style=user_style),
        InlineKeyboardButton(f"👤 Artist: {src_txt}", callback_data=f"ytdl_toggle_asrc#{task_id}", style=user_style)
    ]
    
    # 🔘 BUTTON GENERATION
    buttons = []
    if is_playlist:
        buttons.append([
            InlineKeyboardButton("📥 Batch Video", callback_data=f"ytdl_pl_batch_confirm#{task_id}#video", style=user_style),
            InlineKeyboardButton("🎵 Batch Audio", callback_data=f"ytdl_pl_batch_confirm#{task_id}#audio", style=user_style)
        ])
        buttons.append([
            InlineKeyboardButton("🎬 Select Video", callback_data=f"ytdl_pl_list#{task_id}#0#video", style=user_style),
            InlineKeyboardButton("🎵 Select Audio", callback_data=f"ytdl_pl_list#{task_id}#0#audio", style=user_style)
        ])
    else:
        # Show Download button if quality is already selected
        if state.get("quality"):
            q = state["quality"]
            f = state.get("format", "video").upper()
            buttons.append([InlineKeyboardButton(f"🚀 START DOWNLOAD {f} ({q}) 🚀", callback_data=f"ytdl_dl_confirm#{task_id}", style=user_style)])
            
        buttons.append([
            InlineKeyboardButton("🎬 Video", callback_data=f"ytdl_type#{task_id}#video", style=user_style),
            InlineKeyboardButton("🎵 Audio", callback_data=f"ytdl_type#{task_id}#audio", style=user_style)
        ])
        buttons.append([InlineKeyboardButton(trim_text, callback_data=f"ytdl_trim_menu#{task_id}", style=user_style)])
 
    # Common Settings for both Single and Playlist
    if state.get("format", "video") == "video":
        v_bit = state.get("video_bitrate", "Original")
        buttons.append([InlineKeyboardButton(f"📺 Video Bitrate: {v_bit}", callback_data=f"ytdl_vbit_menu#{task_id}", style=user_style)])
    else:
        buttons.append([InlineKeyboardButton(f"🏷 Audio Name: {fmt_txt}", callback_data=f"ytdl_toggle_aname#{task_id}", style=user_style)])
        buttons.append([InlineKeyboardButton(f"👤 Artist: {src_txt}", callback_data=f"ytdl_toggle_asrc#{task_id}", style=user_style)])
        
    speed_val = state.get("speed", "1.0x")
    volume_val = state.get("volume", "Original")
    buttons.append([
        InlineKeyboardButton(f"⚡️ Speed: {speed_val}", callback_data=f"ytdl_speed_menu#{task_id}", style=user_style),
        InlineKeyboardButton(f"🔊 Volume: {volume_val}", callback_data=f"ytdl_volume_menu#{task_id}", style=user_style)
    ])
    fade_in_lbl = _ytdl_fmt_time(state.get("fade_in", 0))
    fade_out_lbl = _ytdl_fmt_time(state.get("fade_out", 0))
    buttons.append([InlineKeyboardButton(f"🎚 Fade In/Out: {fade_in_lbl} | {fade_out_lbl}", callback_data=f"ytdl_fade_menu#{task_id}", style=user_style)])
    buttons.append([InlineKeyboardButton(f"👤 Sender: {state.get('sender_name', 'Default')}", callback_data=f"ytdl_sel_sender#{task_id}", style=user_style)])
 
    # 🔊 AUDIO TRACK: Only show if video has multiple audio options
    if has_multi_audio:
        buttons.append([InlineKeyboardButton(f"🔊 Audio Track (Lang): {current_lang}", callback_data=f"ytdl_audio_lang_menu#{task_id}", style=user_style)])
 
    # 📦 SPLIT CHAPTERS: Only show if single media has chapters
    if not is_playlist and chapters:
        split_lbl = f"📦 Split Chapters: {'Yes' if state.get('split_chapters', False) else 'No'}"
        buttons.append([InlineKeyboardButton(split_lbl, callback_data=f"ytdl_split_menu#{task_id}", style=user_style)])

    # Configuration Rows
    buttons.append([
        InlineKeyboardButton(f"📥 Backup: {backup_status}", callback_data=f"ytdl_toggle_backup#{task_id}", style=user_style),
        InlineKeyboardButton(f"📤 Via: {b_mode}", callback_data=f"ytdl_toggle_bmode#{task_id}", style=user_style)
    ])
    buttons.append([
        InlineKeyboardButton(f"🔗 Link: {link_status}", callback_data=f"ytdl_toggle_link#{task_id}", style=user_style),
        InlineKeyboardButton(f"📝 Desc: {desc_status}", callback_data=f"ytdl_toggle_desc#{task_id}", style=user_style)
    ])
    buttons.append([
        InlineKeyboardButton(f"💧 WM: {wm_status}", callback_data=f"ytdl_toggle_wm#{task_id}", style=user_style),
        InlineKeyboardButton("🔄 Refresh", callback_data=f"ytdl_refresh#{task_id}", style=user_style),
    ])
    buttons.append([
        InlineKeyboardButton("💡 Info", callback_data=f"ytdl_info#{task_id}", style=user_style),
        InlineKeyboardButton("❌ Cancel", callback_data=f"ytdl_cancel#{task_id}", style=user_style)
    ])
    
    # ✅ FIX: Explicitly add 'Back to Playlist' button if it's a subtask
    if not is_playlist and state.get("parent_id"):
        # Insert before Cancel (last row) to keep Cancel at the bottom
        buttons.insert(-1, [InlineKeyboardButton("« Back to Playlist »", callback_data=f"ytdl_back#{state['parent_id']}", style=user_style)])
    
    if is_iq:
        await obj.answer(
            results=[
                InlineQueryResultPhoto(
                    id=f"ytdl_{task_id.replace('#', '')}",
                    photo_url=thumb,
                    thumb_url=thumb,
                    title=state["title"],
                    description=f"Duration: {dur_str}",
                    caption=text,
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
            ],
            cache_time=0,
            is_personal=True
        )
    else:
        # It's a callback, edit current message
        try:
            # Prefer caption if it's already a media message
            if obj.message and (obj.message.photo or obj.message.video or obj.message.animation):
                await obj.edit_message_caption(
                    caption=text,
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
            else:
                await obj.edit_message_text(
                    text=text,
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
        except:
            # Fallback
            try:
                await obj.edit_message_caption(
                    caption=text,
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
            except:
                try:
                    await obj.edit_message_text(
                        text=text,
                        parse_mode=enums.ParseMode.HTML,
                        reply_markup=InlineKeyboardMarkup(buttons)
                    )
                except Exception as e:
                    Altruix.log(f"YTDL Dashboard Edit Fail: {e}\n{traceback.format_exc()}")

@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_type#([#\w]+)#(\w+)"))
@iuser_check
async def ytdl_type_cb(c: Client, cb: CallbackQuery):
    await cb.answer()
    task_id, f_type = cb.matches[0].groups()
    state = Altruix.YTDL_STATE.get(task_id)
    if not state: return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
    state["format"] = f_type
    
    if f_type == "video":
        text = "<b>🎬 Pilih Kualitas Video:</b>"
        buttons = []
        row = []
        # Get all extracted resolutions, sorted descending
        available = sorted([int(r) for r in state["resolutions"]], reverse=True)
        if not available:
            available = [720, 480, 360]
            
        user_style = get_user_button_style(cb.from_user.id)
        for res in available:
            sz_val = state.get("res_sizes", {}).get(str(res), 0)
            if not sz_val: sz_val = state.get("res_sizes", {}).get(res, 0)
            sz_str = f" [{Essentials.humanbytes(sz_val)}]" if sz_val else ""
            row.append(InlineKeyboardButton(f"{res}p{sz_str}", callback_data=f"ytdl_qual#{task_id}#{res}", style=user_style))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
    else:
        text = "<b>🎵 Pilih Kualitas Audio (MP3):</b>"
        user_style = get_user_button_style(cb.from_user.id)
        dur = state.get("duration", 0)
        def get_aud_sz(kbps):
            if not dur: return ""
            b = (kbps * 1000 * dur) // 8
            if b <= 0: return ""
            return f" [{Essentials.humanbytes(b)}]"
            
        buttons = [
            [InlineKeyboardButton(f"320kbps{get_aud_sz(320)}", callback_data=f"ytdl_qual#{task_id}#320", style=user_style), InlineKeyboardButton(f"192kbps{get_aud_sz(192)}", callback_data=f"ytdl_qual#{task_id}#192", style=user_style)], 
            [InlineKeyboardButton(f"128kbps{get_aud_sz(128)}", callback_data=f"ytdl_qual#{task_id}#128", style=user_style)]
        ]
        
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"ytdl_back#{task_id}", style=user_style)])
    try:
        await cb.edit_message_caption(caption=text, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
    except:
        await cb.edit_message_text(text=text, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_qual#([#\w]+)#(\w+)"))
@iuser_check
async def ytdl_qual_cb(c: Client, cb: CallbackQuery):
    task_id, qual = cb.matches[0].groups()
    state = Altruix.YTDL_STATE.get(task_id)
    if not state: return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
    await cb.answer(f"Quality set to {qual}")
    state["quality"] = qual
    await sync_ytdl_task(task_id) # ✅ PERSISTENCE
    await cb.answer(f"Quality set to {qual}")
    await ytdl_inline_menu(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_audio_lang_menu#([#\w]+)"))
@iuser_check
async def ytdl_audio_lang_menu_cb(c: Client, cb: CallbackQuery):
    await cb.answer()
    task_id = cb.matches[0].group(1)
    state = Altruix.YTDL_STATE.get(task_id)
    if not state: return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
    
    audio_langs = state.get("languages") or []
    if not audio_langs:
        return await cb.answer("Tidak ada opsi bahasa tambahan.", show_alert=True)
    
    text = "<b>🔊 Pilih Bahasa Audio Track:</b>\n<i>Pilihan ini akan diprioritaskan saat download.</i>"
    user_style = get_user_button_style(cb.from_user.id)
    buttons = []
    
    # Default Option
    cur = state.get("audio_lang", "Default")
    def_btn = "✅ Default" if cur == "Default" else "Default"
    buttons.append([InlineKeyboardButton(def_btn, callback_data=f"ytdl_set_audio_lang#{task_id}#Default", style=user_style)])
    
    # Language Options
    row = []
    for lang in audio_langs:
        label = f"✅ {lang.upper()}" if cur == lang else lang.upper()
        row.append(InlineKeyboardButton(label, callback_data=f"ytdl_set_audio_lang#{task_id}#{lang}", style=user_style))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
        
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"ytdl_back#{task_id}", style=user_style)])
    try:
        await cb.edit_message_caption(caption=text, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
    except:
        await cb.edit_message_text(text=text, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_set_audio_lang#([#\w]+)#(.+)"))
@iuser_check
async def ytdl_set_audio_lang_cb(c: Client, cb: CallbackQuery):
    task_id, lang = cb.matches[0].groups()
    state = Altruix.YTDL_STATE.get(task_id)
    if not state: return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
    
    state["audio_lang"] = lang
    await sync_ytdl_task(task_id)
    await cb.answer(f"Audio Track: {lang}")
    await ytdl_inline_menu(c, cb)
    state["quality_set"] = True
    await sync_ytdl_task(task_id)
    
    # Bypass sender selection because it's available on main dashboard
    c_idx = str(state.get("client_idx", 0))
    cb.matches = [type('Match', (), {'groups': lambda self: (task_id, c_idx)})()]
    return await ytdl_confirm_cb(c, cb)


@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_sel_sender#([#\w\d_-]+?)(?:#(\d+))?$"))
@iuser_check
async def ytdl_sel_sender_cb(c: Client, cb: CallbackQuery):
    await cb.answer()
    match = cb.matches[0]
    task_id = match.group(1)
    page = int(match.group(2) or 0)
    
    state = Altruix.YTDL_STATE.get(task_id)
    if not state: return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
    
    user_style = get_user_button_style(cb.from_user.id)
    all_clients = Altruix.clients
    per_page = 10
    total_clients = len(all_clients)
    total_pages = (total_clients + per_page - 1) // per_page
    if total_pages == 0: total_pages = 1 # Avoid 0/0
    
    start = page * per_page
    end = start + per_page
    paged_clients = all_clients[start:end]
    
    text = (
        f"<blockquote expandable>"
        f"<b>👤 Pilih Akun Pengunggah:</b> (Hal {page+1}/{total_pages})\n"
        f"<i>Akun ini akan digunakan untuk mengirim file hasil proses.</i>"
        f"</blockquote>"
    )
    
    buttons = []
    
    current_idx = state.get("client_idx", 0)
    
    # 🤖 Option for Assistant Bot (Only on first page)
    if page == 0:
        bot_label = "✅ Assistant Bot" if current_idx == -1 else "Assistant Bot"
        buttons.append([InlineKeyboardButton(f"[🤖] {bot_label}", callback_data=f"ytdl_client#{task_id}#-1", style=user_style)])
    
    # List Accounts for current page
    for i, client in enumerate(paged_clients):
        actual_idx = start + i
        try:
            # ✅ OPTIMIZATION: Use cached '.me' attribute to avoid redundant API calls
            me = getattr(client, "me", None)
            if not me: 
                try: me = await client.get_me()
                except: continue
            
            raw_name = me.first_name if me else f"Session {actual_idx}"
            prefix = ""
            
            # ✅ Chosen Sender Mark
            if actual_idx == current_idx:
                prefix += "✅ "
            
            # 👤 Initiator Mark (The one who ran the cmd)
            if actual_idx == state.get("runner_idx"):
                prefix += "👤 "
                
            display_name = f"{prefix}{raw_name}"
                
            buttons.append([InlineKeyboardButton(f"[{actual_idx}] {display_name}", callback_data=f"ytdl_client#{task_id}#{actual_idx}", style=user_style)])
        except: continue
        
    # 📑 Pagination Row
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("Prev", callback_data=f"ytdl_sel_sender#{task_id}#{page-1}", style=user_style))
    
    if total_pages > 1:
        nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="none", style=user_style))
        
    if end < total_clients:
        nav.append(InlineKeyboardButton("Next", callback_data=f"ytdl_sel_sender#{task_id}#{page+1}", style=user_style))
        
    if nav:
        buttons.append(nav)
        
    buttons.append([InlineKeyboardButton("Back", callback_data=f"ytdl_back#{task_id}", style=user_style)])
    
    try:
        await cb.edit_message_text(text=text, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        Altruix.log(f"YTDL Sender Sel Edit Fail: {e}\n{traceback.format_exc()}")
        try: await cb.edit_message_caption(caption=text, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        except: pass

@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_client#([#\w\d_-]+)#(-?\d+)"))
@iuser_check
async def ytdl_confirm_cb(c: Client, cb: CallbackQuery):
    task_id, c_idx = cb.matches[0].groups()
    state = Altruix.YTDL_STATE.get(task_id)
    if not state: return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
    # Build Client List
    client_idx = int(c_idx)
    if client_idx == -1:
         acc_name = "Assistant Bot"
         state["sender_name"] = "Bot"
         state["client_idx"] = -1
    else:
         client = Altruix.clients[client_idx] if client_idx < len(Altruix.clients) else Altruix.clients[0]
         try:
             me = getattr(client, "me", None) or await client.get_me()
             acc_name = f"{me.first_name} {me.last_name or ''}".strip()
             state["sender_name"] = me.first_name
         except:
             acc_name = "Unknown"
             state["sender_name"] = "Unknown"
         state["client_idx"] = client_idx
    
    await sync_ytdl_task(task_id)

    # Logic: If quality is not set, we came from Dashboard. Go back there.
    if "quality_set" not in state:
        return await ytdl_back_cb(c, cb)
        
    start_s, end_s = state['start'], state['end']
    is_trimmed = (start_s != 0 or end_s != state['duration'])
    
    v_bit = state.get("video_bitrate", "Original")
    is_video = state['format'] == 'video'
    fmt_details = f"{state['quality']}p" if is_video else f"{state['quality']}k"
    if is_video and v_bit != "Original":
        fmt_details += f" (Bitrate: {v_bit})"
    speed_val = state.get("speed", "1.0x")
    if speed_val != "1.0x":
        fmt_details += f" [Speed: {speed_val}]"
    volume_val = state.get("volume", "Original")
    if volume_val != "Original":
        fmt_details += f" [Volume: {volume_val}]"
    fade_in = state.get("fade_in", 0) or 0
    fade_out = state.get("fade_out", 0) or 0
    try:
        fade_in_f = float(fade_in)
        fade_out_f = float(fade_out)
    except Exception:
        fade_in_f = 0.0
        fade_out_f = 0.0
    if fade_in_f > 0 or fade_out_f > 0:
        fmt_details += f" [Fade: IN {_ytdl_fmt_time(fade_in_f)} | OUT {_ytdl_fmt_time(fade_out_f)}]"
    split_chapters = state.get("split_chapters", False)
    if split_chapters:
        fmt_details += f" [Split Chapters: {len(state.get('chapters', []))} bab]"

    confirm_text = (
        f"<blockquote expandable>"
        f"<b>🚀 Konfirmasi Unduhan</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>• Nama:</b> {state['title']}\n"
        f"<b>• Platform:</b> {state.get('extractor', 'YouTube').capitalize()}\n"
        f"<b>• Format:</b> {state['format'].upper()} ({fmt_details})\n"
        f"<b>• Trim:</b> {'✅ Yes' if is_trimmed else '❌ No'}\n"
        f"  └─ <code>{_ytdl_fmt_time(start_s)}</code> - <code>{_ytdl_fmt_time(end_s)}</code>\n"
        f"<b>• Akun Upload:</b> Session {c_idx} [<code>{acc_name}</code>]\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>🛠 Task ID:</b> <code>{task_id}</code>\n"
        f"<i>Klik tombol di bawah untuk memulai pemrosesan.</i>"
        f"</blockquote>"
    )
    user_style = get_user_button_style(cb.from_user.id)
    buttons = [
        [InlineKeyboardButton("✅ Start Process", callback_data=f"ytdl_start_go#{task_id}", style=user_style)],
        [InlineKeyboardButton("🔙 Back", callback_data=f"ytdl_back_type#{task_id}", style=user_style), InlineKeyboardButton("❌ Cancel", callback_data=f"ytdl_cancel#{task_id}", style=user_style)]
    ]
    try:
        await cb.edit_message_caption(caption=confirm_text, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
    except:
        await cb.edit_message_text(text=confirm_text, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_back_type#([#\w\d_-]+)"))
@iuser_check
async def ytdl_back_to_type_cb(c: Client, cb: CallbackQuery):
    task_id = cb.matches[0].group(1)
    state = Altruix.YTDL_STATE.get(task_id)
    if not state: return
    # Reuse type handler logic for format (video/audio)
    cb.matches = [type('Match', (), {'groups': lambda self: (task_id, state['format'])})()]
    await ytdl_type_cb(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_back_qual#([#\w\d_-]+)"))
@iuser_check
async def ytdl_back_to_qual_cb(c: Client, cb: CallbackQuery):
    task_id = cb.matches[0].group(1)
    state = Altruix.YTDL_STATE.get(task_id)
    if not state: return
    # Reuse quality handler logic
    cb.matches = [type('Match', (), {'groups': lambda self: (task_id, state['quality'])})()]
    await ytdl_qual_cb(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_trim_menu#([#\w\d_-]+)"))
@iuser_check
async def ytdl_trim_menu_cb(c: Client, cb: CallbackQuery):
    task_id = cb.matches[0].group(1)
    state = Altruix.YTDL_STATE.get(task_id)
    if not state: return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
    
    if "trim_target" not in state:
        state["trim_target"] = "s"
        
    s, e, total = state["start"], state["end"], state["duration"]
    target = state["trim_target"]
    
    text = (
        f"<blockquote expandable>"
        f"<b>✂️ YouTube Video Trimmer</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>⏱ Start:</b> <code>{_ytdl_fmt_time(s)}</code>\n"
        f"<b>⌛️ End:</b> <code>{_ytdl_fmt_time(e)}</code>\n"
        f"<b>📊 Total:</b> <code>{_ytdl_fmt_time(total)}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Gunakan tombol di bawah untuk menyesuaikan range potongan.</i>"
        f"</blockquote>"
    )
    user_style = get_user_button_style(cb.from_user.id)
    
    start_lbl = f"🟢 Edit START: {_ytdl_fmt_time(s)}" if target == "s" else f"⚪️ Edit START: {_ytdl_fmt_time(s)}"
    end_lbl = f"🟢 Edit END: {_ytdl_fmt_time(e)}" if target == "e" else f"⚪️ Edit END: {_ytdl_fmt_time(e)}"
    
    buttons = [
        # --- TAB SWITCHER ---
        [
            InlineKeyboardButton(start_lbl, callback_data=f"ytdl_trim_tab#{task_id}#s", style=user_style),
            InlineKeyboardButton(end_lbl, callback_data=f"ytdl_trim_tab#{task_id}#e", style=user_style)
        ],
        [InlineKeyboardButton("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", callback_data="none", style=user_style)],
        
        # --- ADJUSTMENTS ---
        [InlineKeyboardButton("⏪ -30m", callback_data=f"ytdl_trim_adj#{task_id}#{target}#-1800", style=user_style), InlineKeyboardButton("◀️ -10m", callback_data=f"ytdl_trim_adj#{task_id}#{target}#-600", style=user_style), InlineKeyboardButton("+10m ▶️", callback_data=f"ytdl_trim_adj#{task_id}#{target}#600", style=user_style), InlineKeyboardButton("+30m ⏩", callback_data=f"ytdl_trim_adj#{task_id}#{target}#1800", style=user_style)],
        [InlineKeyboardButton("⏪ -5m", callback_data=f"ytdl_trim_adj#{task_id}#{target}#-300", style=user_style), InlineKeyboardButton("◀️ -1m", callback_data=f"ytdl_trim_adj#{task_id}#{target}#-60", style=user_style), InlineKeyboardButton("+1m ▶️", callback_data=f"ytdl_trim_adj#{task_id}#{target}#60", style=user_style), InlineKeyboardButton("+5m ⏩", callback_data=f"ytdl_trim_adj#{task_id}#{target}#300", style=user_style)],
        [InlineKeyboardButton("⏪ -30s", callback_data=f"ytdl_trim_adj#{task_id}#{target}#-30", style=user_style), InlineKeyboardButton("◀️ -10s", callback_data=f"ytdl_trim_adj#{task_id}#{target}#-10", style=user_style), InlineKeyboardButton("+10s ▶️", callback_data=f"ytdl_trim_adj#{task_id}#{target}#10", style=user_style), InlineKeyboardButton("+30s ⏩", callback_data=f"ytdl_trim_adj#{task_id}#{target}#30", style=user_style)],
        [InlineKeyboardButton("⏪ -5s", callback_data=f"ytdl_trim_adj#{task_id}#{target}#-5", style=user_style), InlineKeyboardButton("◀️ -1s", callback_data=f"ytdl_trim_adj#{task_id}#{target}#-1", style=user_style), InlineKeyboardButton("+1s ▶️", callback_data=f"ytdl_trim_adj#{task_id}#{target}#1", style=user_style), InlineKeyboardButton("+5s ⏩", callback_data=f"ytdl_trim_adj#{task_id}#{target}#5", style=user_style)],
        [InlineKeyboardButton("⏪ -0.5s", callback_data=f"ytdl_trim_adj#{task_id}#{target}#-0.5", style=user_style), InlineKeyboardButton("◀️ -0.25s", callback_data=f"ytdl_trim_adj#{task_id}#{target}#-0.25", style=user_style), InlineKeyboardButton("+0.25s ▶️", callback_data=f"ytdl_trim_adj#{task_id}#{target}#0.25", style=user_style), InlineKeyboardButton("+0.5s ⏩", callback_data=f"ytdl_trim_adj#{task_id}#{target}#0.5", style=user_style)],
        
        [InlineKeyboardButton("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", callback_data="none", style=user_style)],
        
        # --- ACTIONS ---
        [InlineKeyboardButton("✅ Save Settings", callback_data=f"ytdl_back#{task_id}", style=user_style), InlineKeyboardButton("🔃 Reset All", callback_data=f"ytdl_trim_reset#{task_id}", style=user_style)],
        [InlineKeyboardButton("« Back to Menu »", callback_data=f"ytdl_back#{task_id}", style=user_style)]
    ]
    try:
        await cb.edit_message_caption(caption=text, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
    except:
        await cb.edit_message_text(text=text, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_trim_tab#([#\w]+)#([se])"))
@iuser_check
async def ytdl_trim_tab_cb(c: Client, cb: CallbackQuery):
    task_id, target = cb.matches[0].groups()
    state = Altruix.YTDL_STATE.get(task_id)
    if not state: return
    state["trim_target"] = target
    await sync_ytdl_task(task_id)
    
    cb.matches = [type('Match', (), {'group': lambda self, n: task_id})()]
    await ytdl_trim_menu_cb(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_trim_adj#([#\w]+)#(\w+)#(-?\d+(?:\.\d+)?)"))
@iuser_check
async def ytdl_trim_adj_cb(c: Client, cb: CallbackQuery):
    task_id, target, val = cb.matches[0].groups()
    state = Altruix.YTDL_STATE.get(task_id)
    if not state: return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
    try:
        delta = float(val)
    except Exception:
        delta = 0.0
    min_gap = 0.01
    start_v = float(state.get("start", 0) or 0)
    end_v = float(state.get("end", state.get("duration", 0)) or 0)
    dur_v = float(state.get("duration", 0) or 0)
    if target == "s":
        start_v = max(0.0, min(start_v + delta, end_v - min_gap))
        state["start"] = start_v
    else:
        end_v = max(start_v + min_gap, min(end_v + delta, dur_v))
        state["end"] = end_v
    await sync_ytdl_task(task_id)
    await ytdl_trim_menu_cb(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_trim_reset#([#\w\d_-]+)"))
@iuser_check
async def ytdl_trim_reset_cb(c: Client, cb: CallbackQuery):
    task_id = cb.matches[0].group(1)
    state = Altruix.YTDL_STATE.get(task_id)
    if not state: return
    state["start"], state["end"] = 0, state["duration"]
    await sync_ytdl_task(task_id)
    await ytdl_trim_menu_cb(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_back#([#\w\d_-]+)"))
@iuser_check
async def ytdl_back_cb(c: Client, cb: CallbackQuery):
    task_id = cb.matches[0].group(1)
    state = Altruix.YTDL_STATE.get(task_id)
    if not state: return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
    return await ytdl_inline_menu(c, cb, task_id)

@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_cancel#([#\w\d_-]+)"))
@iuser_check
async def ytdl_cancel_cb(c: Client, cb: CallbackQuery):
    task_id = cb.matches[0].group(1)
    Altruix.YTDL_STATE.pop(task_id, None)
    try: await cb.edit_message_text(text="<b>❌ Proses Dibatalkan.</b>", parse_mode=enums.ParseMode.HTML)
    except Exception as e:
        Altruix.log(f"YTDL Cancel Edit Fail: {e}\n{traceback.format_exc()}")
        try: await cb.edit_message_caption(caption="<b>❌ Proses Dibatalkan.</b>", parse_mode=enums.ParseMode.HTML)
        except: pass

@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_info#([#\w\d_-]+?)(?:#(\d+))?$"))
@iuser_check
async def ytdl_info_cb(c: Client, cb: CallbackQuery):
    groups = cb.matches[0].groups()
    task_id = groups[0]
    page = int(groups[1]) if groups[1] else 0
    state = Altruix.YTDL_STATE.get(task_id)
    if not state: return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
    
    if page == 0:
        text = (
            f"<blockquote expandable>"
            f"<b>💡 Panduan Tombol (1/2)</b>\n\n"
            f"• <b>Video/Audio:</b> Mulai proses download ke format terpilih.\n"
            f"• <b>Batch:</b> (Playlist) Download seluruh isi playlist secara otomatis.\n"
            f"• <b>Select:</b> (Playlist) Pilih video spesifik untuk diproses individu.\n"
            f"• <b>Precise Trimmer:</b> Memotong durasi video/audio dengan presisi.\n"
            f"• <b>Sender:</b> Memilih pengunggah (Userbot Anda atau Bot Asisten).\n"
            f"• <b>Backup:</b> Jika ON, media akan dicadangkan ke Grup Log.\n"
            f"• <b>Via:</b> Memilih dikirim via Bot atau Userbot.\n"
            f"• <b>Link:</b> Menampilkan link YouTube di caption.\n"
            f"• <b>Desc:</b> Menampilkan deskripsi video di caption.\n"
            f"</blockquote>"
        )
        nav_text = "Page 2 »"
        nav_data = f"ytdl_info#{task_id}#1"
    else:
        from Main.internals.ytdl_core import get_ffmpeg_version, get_ytdl_engine_info
        ffmpeg_v = await get_ffmpeg_version()
        engine_name, engine_v = await get_ytdl_engine_info()
        
        text = (
            f"<blockquote expandable>"
            f"<b>💡 Panduan Tombol (2/2)</b>\n\n"
            f"• <b>Audio Name:</b> Menukar urutan teks MP3 (Title-Artist vs Artist-Title).\n"
            f"• <b>Artist:</b> Asal usul metadata MP3. "
            f"(<b>Channel:</b> Akun uploader | "
            f"<b>Meta:</b> ID3 Tag Musik Original | "
            f"<b>None:</b> Mengosongkan data Artist sepenuhnya agar minimalis).\n"
            f"• <b>WM (Watermark):</b> Menyematkan Teks Visual 'Altroid-X' di atas Video, atau ID3 MP3.\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>⚙️ Version Info:</b>\n"
            f"• <b>Plugin:</b> <code>v{PLUGIN_VERSION}</code>\n"
            f"• <b>YTDL Core:</b> <code>v{YTDL_CORE_VERSION}</code>\n"
            f"• <b>FFmpeg:</b> <code>v{ffmpeg_v}</code>\n"
            f"• <b>Downloader:</b> <code>{engine_name} v{engine_v}</code>\n"
            f"</blockquote>"
        )
        nav_text = "« Page 1"
        nav_data = f"ytdl_info#{task_id}#0"

    user_style = get_user_button_style(cb.from_user.id)
    buttons = [
        [InlineKeyboardButton(nav_text, callback_data=nav_data, style=user_style)],
        [InlineKeyboardButton("« Back to Menu »", callback_data=f"ytdl_back#{task_id}", style=user_style)]
    ]
    try:
        await cb.edit_message_text(text=text, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        Altruix.log(f"YTDL Info Edit Fail: {e}\n{traceback.format_exc()}")
        try: await cb.edit_message_caption(caption=text, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        except: pass

@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_start_go#([#\w]+)"))
@iuser_check
async def ytdl_process_start_cb(c: Client, cb: CallbackQuery):
    task_id = cb.matches[0].group(1)
    try: await cb.edit_message_text(text="<b>⏳ Memulai pemrosesan... Mohon tunggu.</b>", parse_mode=enums.ParseMode.HTML)
    except Exception as e:
        Altruix.log(f"YTDL Start Edit Fail: {e}\n{traceback.format_exc()}")
        try: await cb.edit_message_caption(caption="<b>⏳ Memulai pemrosesan... Mohon tunggu.</b>", parse_mode=enums.ParseMode.HTML)
        except: pass
    asyncio.create_task(ytdl_engine(cb, task_id))

@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_split_menu#([#\w\d_-]+)"))
@iuser_check
async def ytdl_split_menu_cb(c: Client, cb: CallbackQuery):
    task_id = cb.matches[0].group(1)
    try:
        state = Altruix.YTDL_STATE.get(task_id)
        if not state: return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
        
        chapters = state.get("chapters") or []
        if not chapters:
            return await cb.answer("❌ Video ini tidak memiliki bab/chapter metadata.", show_alert=True)
            
        text = (
            f"<blockquote expandable>"
            f"<b>📦 Pengaturan Pembagian Bab (Split Chapters)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Terdapat <b>{len(chapters)} bab</b> terdeteksi pada video ini. Mengaktifkan opsi ini akan membagi video secara otomatis dan mengirim setiap bab sebagai file terpisah.\n\n"
        )
        for idx, chap in enumerate(chapters):
            c_title = chap.get("title", f"Bab {idx+1}")
            c_start = chap.get("start_time", 0.0)
            c_end = chap.get("end_time", state["duration"])
            text += f" {idx+1:02d}. <b>{c_title}</b> ({Essentials.get_readable_time(c_start)} - {Essentials.get_readable_time(c_end)})\n"
        text += f"━━━━━━━━━━━━━━━━━━━━\n"
        text += f"<i>Pilih opsi di bawah untuk mengaktifkan atau menonaktifkan pembagian bab.</i>"
        text += f"</blockquote>"
        
        user_style = get_user_button_style(cb.from_user.id)
        split_status = state.get("split_chapters", False)
        
        yes_lbl = "✅ Yes (Split)" if split_status else "Yes (Split)"
        no_lbl = "✅ No (Single File)" if not split_status else "No (Single File)"
        
        buttons = [
            [
                InlineKeyboardButton(yes_lbl, callback_data=f"ytdl_set_split#{task_id}#yes", style=user_style),
                InlineKeyboardButton(no_lbl, callback_data=f"ytdl_set_split#{task_id}#no", style=user_style)
            ],
            [
                InlineKeyboardButton("« Back to Menu »", callback_data=f"ytdl_back#{task_id}", style=user_style)
            ]
        ]
        
        try:
            await cb.edit_message_caption(caption=text, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        except:
            await cb.edit_message_text(text=text, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as ex:
        Altruix.log(f"Split Menu Error: {ex}\n{traceback.format_exc()}")
        try: await cb.answer(f"❌ Terjadi kesalahan: {ex}", show_alert=True)
        except: pass

@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_set_split#([#\w\d_-]+)#(yes|no)"))
@iuser_check
async def ytdl_set_split_cb(c: Client, cb: CallbackQuery):
    task_id, val = cb.matches[0].groups()
    try:
        state = Altruix.YTDL_STATE.get(task_id)
        if not state: return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
        
        state["split_chapters"] = (val == "yes")
        asyncio.create_task(sync_ytdl_task(task_id)) # Background Sync
        await cb.answer(f"Split Chapters: {'ON' if state['split_chapters'] else 'OFF'}")
        
        # Refresh split menu
        await ytdl_split_menu_cb(c, cb)
    except Exception as ex:
        Altruix.log(f"Set Split Error: {ex}\n{traceback.format_exc()}")
        try: await cb.answer(f"❌ Terjadi kesalahan: {ex}", show_alert=True)
        except: pass

@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_toggle_backup#([#\w\d_-]+)"))
@iuser_check
async def ytdl_toggle_backup_cb(c: Client, cb: CallbackQuery):
    task_id = cb.matches[0].group(1)
    state = Altruix.YTDL_STATE.get(task_id)
    if not state: return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
    state["auto_backup"] = not state.get("auto_backup", True) # Toggle state
    await cb.answer(f"Auto Backup: {'ON' if state['auto_backup'] else 'OFF'}")
    asyncio.create_task(sync_ytdl_task(task_id)) # ✅ Background Sync
    # Refresh dashboard
    await ytdl_inline_menu(c, cb, task_id)

@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_toggle_bmode#([#\w\d_-]+)"))
@iuser_check
async def ytdl_toggle_bmode_cb(c: Client, cb: CallbackQuery):
    task_id = cb.matches[0].group(1)
    state = Altruix.YTDL_STATE.get(task_id)
    if not state: return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
    
    current = state.get("backup_mode", "userbot")
    state["backup_mode"] = "bot" if current == "userbot" else "userbot"
    asyncio.create_task(sync_ytdl_task(task_id)) # ✅ Background Sync
    await cb.answer(f"Backup via: {state['backup_mode'].capitalize()}")
    
    # Refresh dashboard
    await ytdl_inline_menu(c, cb, task_id)

@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_toggle_link#([#\w\d_-]+)"))
@iuser_check
async def ytdl_toggle_link_cb(c: Client, cb: CallbackQuery):
    task_id = cb.matches[0].group(1)
    state = Altruix.YTDL_STATE.get(task_id)
    if not state: return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
    
    state["show_link"] = not state.get("show_link", True) # Toggle state (default True)
    asyncio.create_task(sync_ytdl_task(task_id)) # ✅ Background Sync
    await cb.answer(f"Source Link: {'ON' if state['show_link'] else 'OFF'}")
    
    # Refresh dashboard
    await ytdl_inline_menu(c, cb, task_id)

@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_toggle_desc#([#\w\d_-]+)"))
@iuser_check
async def ytdl_toggle_desc_cb(c: Client, cb: CallbackQuery):
    task_id = cb.matches[0].group(1)
    state = Altruix.YTDL_STATE.get(task_id)
    if not state: return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
    
    state["show_desc"] = not state.get("show_desc", False) # Toggle state (default False)
    asyncio.create_task(sync_ytdl_task(task_id)) # ✅ Background Sync
    await cb.answer(f"Show Description: {'ON' if state['show_desc'] else 'OFF'}")
    
    # Refresh dashboard
    await ytdl_inline_menu(c, cb, task_id)

@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_pl_list#([#\w]+)#(\d+)#(\w+)"))
@iuser_check
async def ytdl_pl_list_cb(c: Client, cb: CallbackQuery):
    task_id, page, f_type = cb.matches[0].groups()
    state = Altruix.YTDL_STATE.get(task_id)
    if not state: return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
    
    entries = state.get("entries", [])
    selected_raw = state.get("selected_indices", [])
    if isinstance(selected_raw, str): selected_raw = []
    selected = set(selected_raw)
    page = int(page)
    limit = 8
    start = page * limit
    end = start + limit
    
    current_entries = entries[start:end]
    if not current_entries:
         return await cb.answer("Tidak ada video lagi.", show_alert=True)
    
    sel_count = len(selected)
    total_pages = ((len(entries)-1)//limit) + 1
    
    text = (
        f"<blockquote expandable>"
        f"<b>📑 Select {f_type.capitalize()} from Playlist</b>\n"
        f"Page: {page + 1} / {total_pages}\n"
        f"Total: {len(entries)} Items | Selected: {sel_count}\n\n"
        f"<i>☑️ = selected | ☐ = not selected\n"
        f"Tap title to toggle, then press 'Download Selected'.</i>"
        f"</blockquote>"
    )
    
    user_style = get_user_button_style(cb.from_user.id)
    buttons = []
    for i, entry in enumerate(current_entries):
        idx = start + i
        is_sel = idx in selected
        icon = "☑️" if is_sel else "☐"
        title = entry['title'][:32]
        buttons.append([InlineKeyboardButton(
            f"{icon} {idx+1}. {title}",
            callback_data=f"ytdl_pl_tog#{task_id}#{idx}#{page}#{f_type}",
            style=user_style
        )])
    
    # Select Page / Select All row
    all_on_page = set(range(start, min(end, len(entries))))
    all_page_selected = all_on_page.issubset(selected)
    sp_text = "☑️ Deselect Page" if all_page_selected else "☐ Select Page"
    sa_text = f"☑️ All ({len(entries)})" if sel_count == len(entries) else f"☐ All ({len(entries)})"
    buttons.append([
        InlineKeyboardButton(sp_text, callback_data=f"ytdl_pl_sp#{task_id}#{page}#{f_type}", style=user_style),
        InlineKeyboardButton(sa_text, callback_data=f"ytdl_pl_sa#{task_id}#{page}#{f_type}", style=user_style)
    ])
    
    # Download Selected button (only show if items are selected)
    if sel_count > 0:
        buttons.append([InlineKeyboardButton(
            f"📥 Download Selected ({sel_count})",
            callback_data=f"ytdl_pl_dls#{task_id}#{f_type}",
            style=user_style
        )])
    
    # Navigation Row 1: [Prev] [N/N] [Next]
    last_page = total_pages - 1
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("« Prev", callback_data=f"ytdl_pl_list#{task_id}#{page-1}#{f_type}", style=user_style))
    nav.append(InlineKeyboardButton(f"[{page+1}/{total_pages}]", callback_data="noop", style=user_style))
    if end < len(entries):
        nav.append(InlineKeyboardButton("Next »", callback_data=f"ytdl_pl_list#{task_id}#{page+1}#{f_type}", style=user_style))
    buttons.append(nav)
    
    # Navigation Row 2: [First] [Last]
    fl_row = []
    if page > 0:
        fl_row.append(InlineKeyboardButton("« First", callback_data=f"ytdl_pl_list#{task_id}#0#{f_type}", style=user_style))
    if end < len(entries):
        fl_row.append(InlineKeyboardButton("Last »", callback_data=f"ytdl_pl_list#{task_id}#{last_page}#{f_type}", style=user_style))
    if fl_row: buttons.append(fl_row)
    
    # Navigation Row 3: [Back]
    buttons.append([InlineKeyboardButton("« Back to Menu »", callback_data=f"ytdl_back#{task_id}", style=user_style)])
    try:
        await cb.edit_message_text(text=text, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
    except:
        await cb.edit_message_caption(caption=text, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

# --- Multi-Select Toggle (Single Item) ---
@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_pl_tog#([#\w]+)#(\d+)#(\d+)#(\w+)"))
@iuser_check
async def ytdl_pl_toggle_cb(c: Client, cb: CallbackQuery):
    task_id, idx, page, f_type = cb.matches[0].groups()
    state = Altruix.YTDL_STATE.get(task_id)
    if not state: return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
    
    idx = int(idx)
    selected_raw = state.get("selected_indices", [])
    if isinstance(selected_raw, str): selected_raw = []
    selected = set(selected_raw)
    
    if idx in selected:
        selected.discard(idx)
        await cb.answer(f"☐ Deselected #{idx+1}")
    else:
        selected.add(idx)
        await cb.answer(f"☑️ Selected #{idx+1}")
    
    state["selected_indices"] = list(selected)
    
    # Re-render the list page
    cb.matches = [type('Match', (), {'groups': lambda self: (task_id, page, f_type)})()]
    await ytdl_pl_list_cb(c, cb)

# --- Multi-Select: Select/Deselect Current Page ---
@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_pl_sp#([#\w]+)#(\d+)#(\w+)"))
@iuser_check
async def ytdl_pl_select_page_cb(c: Client, cb: CallbackQuery):
    task_id, page, f_type = cb.matches[0].groups()
    state = Altruix.YTDL_STATE.get(task_id)
    if not state: return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
    
    page = int(page)
    limit = 8
    start = page * limit
    end = min(start + limit, len(state.get("entries", [])))
    selected_raw = state.get("selected_indices", [])
    if isinstance(selected_raw, str): selected_raw = []
    selected = set(selected_raw)
    
    page_indices = set(range(start, end))
    if page_indices.issubset(selected):
        selected -= page_indices
        await cb.answer(f"☐ Deselected page {page+1}")
    else:
        selected |= page_indices
        await cb.answer(f"☑️ Selected page {page+1}")
    
    state["selected_indices"] = list(selected)
    
    cb.matches = [type('Match', (), {'groups': lambda self: (task_id, str(page), f_type)})()]
    await ytdl_pl_list_cb(c, cb)

# --- Multi-Select: Select All / Deselect All ---
@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_pl_sa#([#\w]+)#(\d+)#(\w+)"))
@iuser_check
async def ytdl_pl_select_all_cb(c: Client, cb: CallbackQuery):
    task_id, page, f_type = cb.matches[0].groups()
    state = Altruix.YTDL_STATE.get(task_id)
    if not state: return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
    
    entries = state.get("entries", [])
    selected_raw = state.get("selected_indices", [])
    if isinstance(selected_raw, str): selected_raw = []
    selected = set(selected_raw)
    
    if len(selected) == len(entries):
        selected.clear()
        await cb.answer(f"☐ Deselected all {len(entries)} items")
    else:
        selected.update(range(len(entries)))
        await cb.answer(f"☑️ Selected all {len(entries)} items")
    
    state["selected_indices"] = list(selected)
    
    cb.matches = [type('Match', (), {'groups': lambda self: (task_id, page, f_type)})()]
    await ytdl_pl_list_cb(c, cb)

# --- Multi-Select: Download Selected (Confirmation) ---
@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_pl_dls#([#\w]+)#(\w+)"))
@iuser_check
async def ytdl_pl_dl_selected_cb(c: Client, cb: CallbackQuery):
    task_id, f_type = cb.matches[0].groups()
    state = Altruix.YTDL_STATE.get(task_id)
    if not state: return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
    
    selected_raw = state.get("selected_indices", [])
    if isinstance(selected_raw, str): selected_raw = []
    selected = set(selected_raw)
    
    if not selected:
        return await cb.answer("❌ No items selected!", show_alert=True)
    
    entries = state.get("entries", [])
    sel_count = len(selected)
    selected_entries = [entries[i] for i in sorted(selected) if i < len(entries)]
    
    user_style = get_user_button_style(cb.from_user.id)
    text = (
        f"<blockquote expandable>"
        f"<b>⚠️ Confirm Multi-Select Download</b>\n\n"
        f"Download <b>{sel_count}</b> selected items as <b>{f_type.capitalize()}</b>.\n\n"
        f"<b>Selected:</b>\n"
    )
    for i, entry in enumerate(selected_entries[:10]):
        text += f"  {i+1}. {entry['title'][:40]}\n"
    if sel_count > 10:
        text += f"  ... and {sel_count - 10} more\n"
    text += f"</blockquote>"
    
    buttons = [
        [InlineKeyboardButton(f"✅ Download {sel_count} Items", callback_data=f"ytdl_pl_q#multi#{task_id}#{f_type}", style=user_style)],
        [
            InlineKeyboardButton("🔙 Back", callback_data=f"ytdl_pl_list#{task_id}#0#{f_type}", style=user_style),
            InlineKeyboardButton("❌ Cancel", callback_data=f"ytdl_back#{task_id}", style=user_style)
        ]
    ]
    try:
        await cb.edit_message_text(text=text, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
    except:
        await cb.edit_message_caption(caption=text, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

# --- Global Quality Selection for Batch / Multi-Select ---
@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_pl_q#(multi|batch)#([#\w]+)#(\w+)"))
@iuser_check
async def ytdl_pl_qual_menu_cb(c: Client, cb: CallbackQuery):
    mode, task_id, f_type = cb.matches[0].groups()
    state = Altruix.YTDL_STATE.get(task_id)
    if not state: return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
    
    user_style = get_user_button_style(cb.from_user.id)
    sender = state.get("sender_name", "Unknown")
    
    if f_type == "video":
        text = (
            f"<blockquote expandable>"
            f"<b>⚙️ Select Global Video Quality</b>\n\n"
            f"<b>👤 Sender:</b> <code>{sender}</code>\n"
            f"Choose preferred video resolution for this process.\n"
            f"<i>If the selected quality is unavailable for a specific video, the next best quality will be used automatically.</i>"
            f"</blockquote>"
        )
        buttons = [
            [
                InlineKeyboardButton("1080p", callback_data=f"ytdl_pl_go#{mode}#{task_id}#{f_type}#1080", style=user_style),
                InlineKeyboardButton("720p", callback_data=f"ytdl_pl_go#{mode}#{task_id}#{f_type}#720", style=user_style)
            ],
            [
                InlineKeyboardButton("480p", callback_data=f"ytdl_pl_go#{mode}#{task_id}#{f_type}#480", style=user_style),
                InlineKeyboardButton("360p", callback_data=f"ytdl_pl_go#{mode}#{task_id}#{f_type}#360", style=user_style)
            ]
        ]
    else:
        text = (
            f"<blockquote expandable>"
            f"<b>⚙️ Select Global Audio Quality</b>\n\n"
            f"<b>👤 Sender:</b> <code>{sender}</code>\n"
            f"Choose preferred audio bitrate for this process.\n"
            f"<i>If unavailable, the highest original audio bitrate will be used.</i>"
            f"</blockquote>"
        )
        buttons = [
            [
                InlineKeyboardButton("320kbps", callback_data=f"ytdl_pl_go#{mode}#{task_id}#{f_type}#320", style=user_style),
                InlineKeyboardButton("256kbps", callback_data=f"ytdl_pl_go#{mode}#{task_id}#{f_type}#256", style=user_style)
            ],
            [
                InlineKeyboardButton("192kbps", callback_data=f"ytdl_pl_go#{mode}#{task_id}#{f_type}#192", style=user_style),
                InlineKeyboardButton("128kbps", callback_data=f"ytdl_pl_go#{mode}#{task_id}#{f_type}#128", style=user_style)
            ]
        ]
        
    back_data = f"ytdl_pl_list#{task_id}#0#{f_type}" if mode == "multi" else f"ytdl_back#{task_id}"
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data=back_data, style=user_style)])
    
    try:
        await cb.edit_message_text(text=text, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
    except:
        await cb.edit_message_caption(caption=text, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_pl_select#([#\w]+)#(\d+)#(\w+)"))
@iuser_check
async def ytdl_pl_select_cb(c: Client, cb: CallbackQuery):
    task_id, idx, f_type = cb.matches[0].groups()
    state = Altruix.YTDL_STATE.get(task_id)
    if not state: return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
    
    idx = int(idx)
    entry = state["entries"][idx]
    
    # Create a sub-task for this specific video
    from Main.plugins.userbot.xtaskmanager import generate_task_id
    sub_id = generate_task_id("YT")
    
    await cb.answer(f"Menganalisis: {entry['title'][:20]}...")
    
    # Extract info for this specific video
    from Main.internals.ytdl_core import extract_yt_info
    try:
        info = await extract_yt_info(entry["url"])
        if info.get("type") == "playlist":
             return await cb.answer("Nested playlist tidak didukung.", show_alert=True)
             
        Altruix.YTDL_STATE[sub_id] = {
            "type": "video",
            "title": info["title"],
            "url": entry["url"],
            "duration": info["duration"],
            "thumb": info["thumbnail"],
            "uploader": info.get("uploader"),
            "subscribers": info.get("subscribers"),
            "views": info.get("views"),
            "upload_date": info.get("upload_date"),
            "resolutions": info.get("resolutions", []),
            "res_sizes": info.get("res_sizes", {}),
            "start": 0,
            "end": info["duration"],
            "format": f_type,
            "quality": "720" if f_type == "video" else "128",
            "client_idx": state["client_idx"],
            "sender_name": state["sender_name"],
            "user_id": state["user_id"],
            "chat_id": state["chat_id"],
            "speed": state.get("speed", "1.0x"),
            "volume": state.get("volume", "Original"),
            "fade_in": state.get("fade_in", 0) or 0,
            "fade_out": state.get("fade_out", 0) or 0,
            "watermark": state.get("watermark", False),
            "video_bitrate": state.get("video_bitrate", "Original"),
            "show_desc": state.get("show_desc", False),
            "audio_lang": state.get("audio_lang", "Default"),
            "audio_name_fmt": state.get("audio_name_fmt", "title_artist"),
            "audio_artist_src": state.get("audio_artist_src", "channel"),
            "show_link": state.get("show_link", True),
            "auto_backup": state.get("auto_backup", True),
            "backup_mode": state.get("backup_mode", "bot"),
            "parent_id": task_id
        }
        await sync_ytdl_task(sub_id)
    except Exception as e:
        return await cb.answer(f"Gagal: {str(e)}", show_alert=True)

    # Open single dashboard for this subtask
    cb.matches = [type('Match', (), {'group': lambda self, n: sub_id})()]
    await ytdl_inline_menu(c, cb)

@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_pl_batch_confirm#([#\w]+)#(\w+)"))
@iuser_check
async def ytdl_pl_batch_confirm_cb(c: Client, cb: CallbackQuery):
    task_id, f_type = cb.matches[0].groups()
    user_style = get_user_button_style(cb.from_user.id)
    
    text = (
        f"<blockquote expandable>"
        f"<b>⚠️ Konfirmasi Batch Download</b>\n\n"
        f"Anda akan mengunduh seluruh isi playlist ke format <b>{f_type.capitalize()}</b>.\n"
        f"Tindakan ini mungkin membutuhkan waktu lama tergantung jumlah video.\n\n"
        f"<b>Apakah Anda yakin ingin melanjutkan?</b>"
        f"</blockquote>"
    )
    buttons = [
        [
            InlineKeyboardButton("✅ Yes, Continue", callback_data=f"ytdl_pl_q#batch#{task_id}#{f_type}", style=user_style),
            InlineKeyboardButton("❌ No, Cancel", callback_data=f"ytdl_back#{task_id}", style=user_style)
        ]
    ]
    try:
        await cb.edit_message_text(text=text, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
    except:
        await cb.edit_message_caption(caption=text, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_pl_auto#([#\w]+)"))
@iuser_check
async def ytdl_pl_auto_cb(c: Client, cb: CallbackQuery):
    task_id = cb.matches[0].group(1)
    state = Altruix.YTDL_STATE.get(task_id)
    if not state: return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
    
    text = "<b>📥 Auto-Download Playlist</b>\nPilih format utama untuk seluruh isi playlist:"
    user_style = get_user_button_style(cb.from_user.id)
    buttons = [
        [
            InlineKeyboardButton("🎬 Video (Best)", callback_data=f"ytdl_pl_batch_confirm#{task_id}#video", style=user_style),
            InlineKeyboardButton("🎵 Audio (MP3)", callback_data=f"ytdl_pl_batch_confirm#{task_id}#audio", style=user_style)
        ],
        [InlineKeyboardButton("« Back to Menu »", callback_data=f"ytdl_back#{task_id}", style=user_style)]
    ]
    try:
        await cb.edit_message_caption(caption=text, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
    except:
        await cb.edit_message_text(text=text, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

# --- Executing Batch / Multi-Select ---
@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_pl_go#(multi|batch)#([#\w]+)#(\w+)#(\d+)"))
@iuser_check
async def ytdl_pl_execute_batch_cb(c: Client, cb: CallbackQuery):
    mode, task_id, f_type, qual = cb.matches[0].groups()
    state = Altruix.YTDL_STATE.get(task_id)
    if not state: return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
    
    if mode == "multi":
        selected_raw = state.get("selected_indices", [])
        if isinstance(selected_raw, str): selected_raw = []
        selected = set(selected_raw)
        
        if not selected:
            return await cb.answer("❌ No items selected!", show_alert=True)
        
        entries = state.get("entries", [])
        state["_original_entries"] = entries
        state["entries"] = [entries[i] for i in sorted(selected) if i < len(entries)]
        state.pop("selected_indices", None)
        
    state["count"] = len(state["entries"])
    state["format"] = f_type
    state["quality"] = qual
    state["auto_batch"] = True
    state["current_index"] = 0
    state["quality_set"] = True
    
    await sync_ytdl_task(task_id)
    msg_text = f"<b>⏳ Memulai pemrosesan {mode.capitalize()} ({len(state['entries'])} items)...</b>"
    try:
        await cb.edit_message_text(text=msg_text, parse_mode=enums.ParseMode.HTML)
    except Exception as e:
        Altruix.log(f"YTDL Batch Start Edit Fail: {e}\n{traceback.format_exc()}")
        try: await cb.edit_message_caption(caption=msg_text, parse_mode=enums.ParseMode.HTML)
        except: pass
    asyncio.create_task(ytdl_engine(cb, task_id))

# --- Persistence Recovery ---
async def init_ytdl_persistence():
    """Reloads pending/running YTDL tasks from DB on startup."""
    import sys as _sys
    if hasattr(_sys, "_ytdl_persistence_initialized"):
        return
    setattr(_sys, "_ytdl_persistence_initialized", True)
    
    await asyncio.sleep(5) # Delay to allow clients to initialize
    try:
        col = Altruix.local_db.make_collection("ytdl_tasks")
        async for task_data in col.find({}):
            task_id = task_data["_id"]
            Altruix.YTDL_STATE[task_id] = task_data
            
            # If it was running, we attempt to resume it
            if task_data.get("status") == "running":
                Altruix.log(f"YTDL: [RESUME] Found running task {task_id}. Attempting recovery...")
                
                # We need a proper message/callback object to pass to the engine
                # Since we don't have the original cb, we might need to recreate a minimal one
                # or just use Altruix.bot to send status updates.
                # Actually, the engine uses 'msg' for edit_status().
                
                class DummyCB:
                    def __init__(self, task_id, chat_id, message_id):
                        self.task_id = task_id
                        self.chat_id = chat_id
                        self.message_id = message_id
                    
                    async def edit_message_text(self, text, **kwargs):
                        try: await Altruix.bot.edit_message_text(self.chat_id, self.message_id, text, **kwargs)
                        except Exception as e:
                            Altruix.log(f"YTDL DummyCB Text Edit Fail: {e}\n{traceback.format_exc()}")
                            try: await Altruix.bot.edit_message_caption(self.chat_id, self.message_id, text, **kwargs)
                            except: pass
                    
                    async def edit_message_caption(self, caption, **kwargs):
                        try: await Altruix.bot.edit_message_text(self.chat_id, self.message_id, caption, **kwargs)
                        except Exception as e:
                            Altruix.log(f"YTDL DummyCB Edit Fail: {e}\n{traceback.format_exc()}")
                            try: await Altruix.bot.edit_message_caption(self.chat_id, self.message_id, caption, **kwargs)
                            except: pass
                
                # Note: 'chat_id' and 'message_id' MUST be in the state for this to work
                # If they are missing, we just skip or log error.
                c_id = task_data.get("chat_id")
                m_id = task_data.get("message_id")
                if c_id and m_id:
                    dummy = DummyCB(task_id, c_id, m_id)
                    asyncio.create_task(ytdl_engine(dummy, task_id))
    except Exception as e:
        Altruix.log(f"YTDL Persistence Recovery Fail: {e}")

# Start background recovery
asyncio.create_task(init_ytdl_persistence())

# --- Audio Toggles ---
@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_toggle_aname#([#\w\d_-]+)"))
@iuser_check
async def ytdl_toggle_aname_cb(c: Client, cb: CallbackQuery):
    task_id = cb.matches[0].group(1)
    state = Altruix.YTDL_STATE.get(task_id)
    if not state: return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
    current = state.get("audio_name_fmt", "title_artist")
    state["audio_name_fmt"] = "artist_title" if current == "title_artist" else "title_artist"
    await cb.answer(f"Format: {state['audio_name_fmt'].replace('_', '-').title()}")
    asyncio.create_task(sync_ytdl_task(task_id)) # ✅ Background Sync
    await ytdl_inline_menu(c, cb, task_id)

@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_toggle_asrc#([#\w\d_-]+)"))
@iuser_check
async def ytdl_toggle_asrc_cb(c: Client, cb: CallbackQuery):
    task_id = cb.matches[0].group(1)
    state = Altruix.YTDL_STATE.get(task_id)
    if not state: return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
    current = state.get("audio_artist_src", "channel")
    if current == "channel": nxt = "meta"
    elif current == "meta": nxt = "none"
    else: nxt = "channel"
    state["audio_artist_src"] = nxt
    await cb.answer(f"Artist Source: {nxt.title()}")
    asyncio.create_task(sync_ytdl_task(task_id)) # ✅ Background Sync
    await ytdl_inline_menu(c, cb, task_id)

@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_toggle_wm#([#\w\d_-]+)"))
@iuser_check
async def ytdl_toggle_wm_cb(c: Client, cb: CallbackQuery):
    task_id = cb.matches[0].group(1)
    state = Altruix.YTDL_STATE.get(task_id)
    if not state: return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
    state["watermark"] = not state.get("watermark", False)
    asyncio.create_task(sync_ytdl_task(task_id)) # ✅ Background Sync
    await cb.answer(f"Watermark: {'ON' if state['watermark'] else 'OFF'}")
    await ytdl_inline_menu(c, cb, task_id)

@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_refresh#([#\w]+)"))
@iuser_check
async def ytdl_refresh_cb(c: Client, cb: CallbackQuery):
    task_id = cb.matches[0].group(1)
    state = Altruix.YTDL_STATE.get(task_id)
    if not state: return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
    
    await cb.answer("🔄 Refreshing metadata...", show_alert=False)
    
    try:
        # Re-extract info
        new_info = await extract_yt_info(state["url"])
        
        # Update relevant fields in state
        is_playlist = new_info.get("type") == "playlist"
        state.update({
            "title": new_info["title"],
            "duration": new_info.get("duration", 0),
            "thumb": new_info["thumbnail"],
            "uploader": new_info.get("uploader"),
            "subscribers": new_info.get("subscribers"),
            "views": new_info.get("views"),
            "upload_date": new_info.get("upload_date"),
            "languages": new_info.get("languages", []),
        })
        
        if not is_playlist:
             state.update({
                 "resolutions": new_info.get("resolutions", []),
                 "res_sizes": new_info.get("res_sizes", {}),
             })
             # Reset end time if it was at the end
             if state.get("end") == 0 or state.get("end") == state.get("_old_dur", 0):
                 state["end"] = new_info.get("duration", 0)
             state["_old_dur"] = new_info.get("duration", 0)
        else:
             state.update({
                 "entries": new_info.get("entries", []),
                 "count": new_info.get("count", 0)
             })
             
        from Main.internals.ytdl_core import sync_ytdl_task
        await sync_ytdl_task(task_id)
        await cb.answer("✅ Metadata updated!", show_alert=False)
        await ytdl_inline_menu(c, cb)
        
    except Exception as e:
        await cb.answer(f"❌ Refresh Error: {str(e)[:50]}", show_alert=True)

@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_dl_confirm#([#\w]+)"))
@iuser_check
async def ytdl_download_confirm_cb(c: Client, cb: CallbackQuery):
    task_id = cb.matches[0].group(1)
    state = Altruix.YTDL_STATE.get(task_id)
    if not state: return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
    
    q = state.get("quality", "Unknown")
    f = state.get("format", "video").upper()
    lang = state.get("audio_lang", "Default")
    
    v_bit = state.get("video_bitrate", "Original")
    is_video = state.get("format", "video") == "video"
    q_str = f"{q}p" if is_video else f"{q}k"
    if is_video and v_bit != "Original":
        q_str += f" (Bitrate: {v_bit})"
    
    uploader = state.get("sender_name", "Default")
    backup_status = "Enabled" if state.get("auto_backup", True) else "Disabled"
    backup_via = state.get("backup_mode", "userbot").capitalize()
    
    text = (
        f"<blockquote expandable>"
        f"<b>⚠️ DOWNLOAD CONFRIMATION</b>\n\n"
        f"<b>• Title:</b> <code>{state['title']}</code>\n"
        f"<b>• Platform:</b> <code>{state.get('extractor', 'YouTube').capitalize()}</code>\n"
        f"<b>• Format:</b> <code>{f}</code>\n"
        f"<b>• Quality:</b> <code>{q_str}</code>\n"
        f"<b>• Audio Lang:</b> <code>{lang}</code>\n"
        f"<b>• Uploader Account:</b> <code>{uploader}</code>\n"
        f"<b>• Backup Status:</b> <code>{backup_status} ({backup_via})</code>\n\n"
        f"<i>Are you sure you want to start this download?</i>"
        f"</blockquote>"
    )
    
    user_style = get_user_button_style(cb.from_user.id)
    buttons = [
        [
            InlineKeyboardButton("✅ YES, START", callback_data=f"ytdl_start_go#{task_id}", style=user_style),
            InlineKeyboardButton("❌ NO, BACK", callback_data=f"ytdl_back#{task_id}", style=user_style)
        ]
    ]
    try:
        await cb.edit_message_text(text=text, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
    except:
        await cb.edit_message_caption(caption=text, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

# --- Video Bitrate Configuration ---
@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_vbit_menu#([#\w\d_-]+)"))
@iuser_check
async def ytdl_vbit_menu_cb(c: Client, cb: CallbackQuery):
    await cb.answer()
    task_id = cb.matches[0].group(1)
    state = Altruix.YTDL_STATE.get(task_id)
    if not state: return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
    
    # Calculate original average bitrate dynamically based on selected quality size
    orig_bitrate_str = ""
    q = state.get("quality")
    if q:
        try:
            v_size = state.get("res_sizes", {}).get(int(q), 0) or state.get("res_sizes", {}).get(str(q), 0)
            dur = state.get("duration", 0)
            if v_size and dur > 0:
                bps = (v_size * 8) / dur
                kbps = bps / 1000
                if kbps >= 1000:
                    orig_bitrate_str = f" ({kbps / 1000:.1f} Mbps)"
                else:
                    orig_bitrate_str = f" ({int(kbps)} Kbps)"
        except Exception as ex:
            Altruix.log(f"Orig Bitrate Calculation Error: {ex}")
            
    text = (
        f"<blockquote expandable>"
        f"<b>📺 Pilih Bitrate Video:</b>\n"
        f"<i>Silakan pilih target bitrate untuk proses kompresi video.</i>"
        f"</blockquote>"
    )
    user_style = get_user_button_style(cb.from_user.id)
    cur = state.get("video_bitrate", "Original")
    
    options = ["Original", "8 Mbps", "5 Mbps", "3 Mbps", "1.5 Mbps", "700 Kbps"]
    buttons = []
    row = []
    for opt in options:
        display_opt = f"Original{orig_bitrate_str}" if opt == "Original" else opt
        label = f"✅ {display_opt}" if cur == opt else display_opt
        row.append(InlineKeyboardButton(label, callback_data=f"ytdl_set_vbit#{task_id}#{opt}", style=user_style))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
        
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"ytdl_back#{task_id}", style=user_style)])
    
    try:
        await cb.edit_message_text(text=text, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        Altruix.log(f"YTDL VBit Edit Fail: {e}\n{traceback.format_exc()}")
        try: await cb.edit_message_caption(caption=text, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        except: pass

@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_set_vbit#([#\w\d_-]+)#(.+)"))
@iuser_check
async def ytdl_set_vbit_cb(c: Client, cb: CallbackQuery):
    task_id, vbit = cb.matches[0].groups()
    state = Altruix.YTDL_STATE.get(task_id)
    if not state: return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
    
    state["video_bitrate"] = vbit
    await cb.answer(f"Video Bitrate set to: {vbit}")
    await sync_ytdl_task(task_id)
    await ytdl_inline_menu(c, cb, task_id)

@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_speed_menu#([#\w]+)"))
@iuser_check
async def ytdl_speed_menu_cb(c: Client, cb: CallbackQuery):
    try:
        await cb.answer()
        task_id = cb.matches[0].group(1)
        state = Altruix.YTDL_STATE.get(task_id)
        if not state: return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
        
        text = (
            f"<blockquote expandable>"
            f"<b>⚡️ Pilih Kecepatan Media (Speed):</b>\n"
            f"<i>Silakan pilih nilai pengali kecepatan untuk proses unduhan video & audio Anda.</i>"
            f"</blockquote>"
        )
        user_style = get_user_button_style(cb.from_user.id)
        cur = state.get("speed", "1.0x")
        
        options = ["0.25x", "0.50x", "0.75x", "1.00x", "1.25x", "1.50x", "1.75x", "2.00x"]
        buttons = []
        row = []
        
        # Extract actual float values for comparisons to ensure exact matching
        try: cur_float = float(cur.replace("x", ""))
        except: cur_float = 1.0
        
        for opt in options:
            try: opt_float = float(opt.replace("x", ""))
            except: opt_float = 1.0
            
            label = f"✅ {opt}" if abs(cur_float - opt_float) < 0.01 else opt
            row.append(InlineKeyboardButton(label, callback_data=f"ytdl_set_speed#{task_id}#{opt}", style=user_style))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
            
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"ytdl_back#{task_id}", style=user_style)])
        
        try:
            await cb.edit_message_text(text=text, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        except Exception as e:
            Altruix.log(f"YTDL Speed Menu Edit Fail: {e}\n{traceback.format_exc()}")
            try: await cb.edit_message_caption(caption=text, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
            except: pass
    except Exception as ex:
        Altruix.log(f"YTDL Speed Menu Error: {ex}\n{traceback.format_exc()}")
        try: await cb.answer(f"Error: {ex}", show_alert=True)
        except: pass

@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_set_speed#([#\w]+)#([\d.]+x)"))
@iuser_check
async def ytdl_set_speed_cb(c: Client, cb: CallbackQuery):
    try:
        task_id, sp = cb.matches[0].groups()
        state = Altruix.YTDL_STATE.get(task_id)
        if not state: return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
        
        if sp == "1.00x":
            sp = "1.0x"
            
        state["speed"] = sp
        await cb.answer(f"Speed set to: {sp}")
        await sync_ytdl_task(task_id)
        await ytdl_inline_menu(c, cb, task_id)
    except Exception as ex:
        Altruix.log(f"YTDL Set Speed Error: {ex}\n{traceback.format_exc()}")
        try: await cb.answer(f"Error: {ex}", show_alert=True)
        except: pass

@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_volume_menu#([#\w]+)"))
@iuser_check
async def ytdl_volume_menu_cb(c: Client, cb: CallbackQuery):
    try:
        await cb.answer()
        task_id = cb.matches[0].group(1)
        state = Altruix.YTDL_STATE.get(task_id)
        if not state: return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
        
        text = (
            f"<blockquote expandable>"
            f"<b>🔊 Pengaturan Volume & Boost (Desibel):</b>\n"
            f"<i>Silakan pilih nilai penyesuaian atau dorongan volume audio di bawah ini.</i>"
            f"</blockquote>"
        )
        user_style = get_user_button_style(cb.from_user.id)
        cur = state.get("volume", "Original")
        
        options = [
            "10% (-20 dB)", "25% (-12 dB)", "50% (-6 dB)", "75% (-2.5 dB)",
            "Original",
            "125% (+2 dB)", "150% (+3.5 dB)", "175% (+5 dB)", "200% (+6 dB)",
            "250% (+8 dB)", "300% (+9.5 dB)", "400% (+12 dB)", "500% (+14 dB)"
        ]
        buttons = []
        row = []
        
        for opt in options:
            display_opt = "Original (100% / 0 dB)" if opt == "Original" else opt
            label = f"✅ {display_opt}" if cur == opt else display_opt
            row.append(InlineKeyboardButton(label, callback_data=f"ytdl_set_volume#{task_id}#{opt}", style=user_style))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
            
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"ytdl_back#{task_id}", style=user_style)])
        
        try:
            await cb.edit_message_text(text=text, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        except Exception as e:
            Altruix.log(f"YTDL Volume Menu Edit Fail: {e}\n{traceback.format_exc()}")
            try: await cb.edit_message_caption(caption=text, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
            except: pass
    except Exception as ex:
        Altruix.log(f"YTDL Volume Menu Error: {ex}\n{traceback.format_exc()}")
        try: await cb.answer(f"Error: {ex}", show_alert=True)
        except: pass

@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_set_volume#([#\w]+)#(.+)"))
@iuser_check
async def ytdl_set_volume_cb(c: Client, cb: CallbackQuery):
    try:
        task_id, vol = cb.matches[0].groups()
        state = Altruix.YTDL_STATE.get(task_id)
        if not state: return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
        
        state["volume"] = vol
        await cb.answer(f"Volume set to: {vol}")
        await sync_ytdl_task(task_id)
        await ytdl_inline_menu(c, cb, task_id)
    except Exception as ex:
        Altruix.log(f"YTDL Set Volume Error: {ex}\n{traceback.format_exc()}")
        try: await cb.answer(f"Error: {ex}", show_alert=True)
        except: pass

@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_fade_menu#([#\w]+)"))
@iuser_check
async def ytdl_fade_menu_cb(c: Client, cb: CallbackQuery):
    try:
        await cb.answer()
        task_id = cb.matches[0].group(1)
        state = Altruix.YTDL_STATE.get(task_id)
        if not state:
            return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
        if "fade_target" not in state:
            state["fade_target"] = "in"

        try:
            start_v = float(state.get("start", 0) or 0)
            end_v = float(state.get("end", state.get("duration", 0)) or 0)
            total_v = float(state.get("duration", 0) or 0)
        except Exception:
            start_v, end_v, total_v = 0.0, 0.0, 0.0

        if end_v <= 0 and total_v > 0:
            end_v = total_v
        if start_v < 0:
            start_v = 0.0
        if end_v > total_v and total_v > 0:
            end_v = total_v
        if end_v < start_v:
            end_v = start_v

        base_dur = max(0.0, end_v - start_v)
        speed_val = state.get("speed", "1.0x")
        try:
            speed_float = float(str(speed_val).replace("x", ""))
            if speed_float <= 0:
                speed_float = 1.0
        except Exception:
            speed_float = 1.0
        out_dur = base_dur / speed_float if speed_float else base_dur

        try:
            fade_in = float(state.get("fade_in", 0) or 0)
        except Exception:
            fade_in = 0.0
        try:
            fade_out = float(state.get("fade_out", 0) or 0)
        except Exception:
            fade_out = 0.0
        if fade_in < 0:
            fade_in = 0.0
        if fade_out < 0:
            fade_out = 0.0

        target = state.get("fade_target", "in")
        in_lbl = f"🟢 Edit FADE IN: {_ytdl_fmt_time(fade_in)}" if target == "in" else f"⚪️ Edit FADE IN: {_ytdl_fmt_time(fade_in)}"
        out_lbl = f"🟢 Edit FADE OUT: {_ytdl_fmt_time(fade_out)}" if target == "out" else f"⚪️ Edit FADE OUT: {_ytdl_fmt_time(fade_out)}"

        text = (
            f"<blockquote expandable>"
            f"<b>🎚 Fade In / Fade Out (Volume)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>• Fade In:</b> <code>{_ytdl_fmt_time(fade_in)}</code>\n"
            f"<b>• Fade Out:</b> <code>{_ytdl_fmt_time(fade_out)}</code>\n"
            f"<b>• Est. Durasi Output:</b> <code>{_ytdl_fmt_time(out_dur)}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>Gunakan tombol +/- untuk mengatur durasi fade (detik).</i>"
            f"</blockquote>"
        )

        user_style = get_user_button_style(cb.from_user.id)
        buttons = [
            [
                InlineKeyboardButton(in_lbl, callback_data=f"ytdl_fade_tab#{task_id}#in", style=user_style),
                InlineKeyboardButton(out_lbl, callback_data=f"ytdl_fade_tab#{task_id}#out", style=user_style),
            ],
            [InlineKeyboardButton("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", callback_data="none", style=user_style)],
            [
                InlineKeyboardButton("⏪ -30s", callback_data=f"ytdl_fade_adj#{task_id}#{target}#-30", style=user_style),
                InlineKeyboardButton("◀️ -10s", callback_data=f"ytdl_fade_adj#{task_id}#{target}#-10", style=user_style),
                InlineKeyboardButton("+10s ▶️", callback_data=f"ytdl_fade_adj#{task_id}#{target}#10", style=user_style),
                InlineKeyboardButton("+30s ⏩", callback_data=f"ytdl_fade_adj#{task_id}#{target}#30", style=user_style),
            ],
            [
                InlineKeyboardButton("⏪ -5s", callback_data=f"ytdl_fade_adj#{task_id}#{target}#-5", style=user_style),
                InlineKeyboardButton("◀️ -1s", callback_data=f"ytdl_fade_adj#{task_id}#{target}#-1", style=user_style),
                InlineKeyboardButton("+1s ▶️", callback_data=f"ytdl_fade_adj#{task_id}#{target}#1", style=user_style),
                InlineKeyboardButton("+5s ⏩", callback_data=f"ytdl_fade_adj#{task_id}#{target}#5", style=user_style),
            ],
            [
                InlineKeyboardButton("⏪ -0.5s", callback_data=f"ytdl_fade_adj#{task_id}#{target}#-0.5", style=user_style),
                InlineKeyboardButton("◀️ -0.25s", callback_data=f"ytdl_fade_adj#{task_id}#{target}#-0.25", style=user_style),
                InlineKeyboardButton("+0.25s ▶️", callback_data=f"ytdl_fade_adj#{task_id}#{target}#0.25", style=user_style),
                InlineKeyboardButton("+0.5s ⏩", callback_data=f"ytdl_fade_adj#{task_id}#{target}#0.5", style=user_style),
            ],
            [InlineKeyboardButton("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", callback_data="none", style=user_style)],
            [
                InlineKeyboardButton("✅ Save Settings", callback_data=f"ytdl_back#{task_id}", style=user_style),
                InlineKeyboardButton("🔃 Reset Fade", callback_data=f"ytdl_fade_reset#{task_id}", style=user_style),
            ],
            [InlineKeyboardButton("« Back to Menu »", callback_data=f"ytdl_back#{task_id}", style=user_style)],
        ]

        try:
            await cb.edit_message_caption(caption=text, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
        except Exception:
            await cb.edit_message_text(text=text, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as ex:
        Altruix.log(f"YTDL Fade Menu Error: {ex}\n{traceback.format_exc()}")
        try:
            await cb.answer(f"Error: {ex}", show_alert=True)
        except:
            pass

@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_fade_tab#([#\w]+)#(in|out)$"))
@iuser_check
async def ytdl_fade_tab_cb(c: Client, cb: CallbackQuery):
    try:
        task_id, target = cb.matches[0].groups()
        state = Altruix.YTDL_STATE.get(task_id)
        if not state:
            return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
        state["fade_target"] = target
        await sync_ytdl_task(task_id)
        cb.matches = [type("Match", (), {"group": lambda self, n: task_id})()]
        await ytdl_fade_menu_cb(c, cb)
    except Exception as ex:
        Altruix.log(f"YTDL Fade Tab Error: {ex}\n{traceback.format_exc()}")
        try:
            await cb.answer(f"Error: {ex}", show_alert=True)
        except:
            pass

@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_fade_adj#([#\w]+)#(in|out)#(-?\d+(?:\.\d+)?)$"))
@iuser_check
async def ytdl_fade_adj_cb(c: Client, cb: CallbackQuery):
    try:
        task_id, target, val = cb.matches[0].groups()
        state = Altruix.YTDL_STATE.get(task_id)
        if not state:
            return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
        try:
            delta = float(val)
        except Exception:
            delta = 0.0

        try:
            start_v = float(state.get("start", 0) or 0)
            end_v = float(state.get("end", state.get("duration", 0)) or 0)
            total_v = float(state.get("duration", 0) or 0)
        except Exception:
            start_v, end_v, total_v = 0.0, 0.0, 0.0
        if end_v <= 0 and total_v > 0:
            end_v = total_v
        if start_v < 0:
            start_v = 0.0
        if end_v > total_v and total_v > 0:
            end_v = total_v
        if end_v < start_v:
            end_v = start_v
        base_dur = max(0.0, end_v - start_v)
        speed_val = state.get("speed", "1.0x")
        try:
            speed_float = float(str(speed_val).replace("x", ""))
            if speed_float <= 0:
                speed_float = 1.0
        except Exception:
            speed_float = 1.0
        out_dur = base_dur / speed_float if speed_float else base_dur

        key = "fade_in" if target == "in" else "fade_out"
        try:
            cur = float(state.get(key, 0) or 0)
        except Exception:
            cur = 0.0
        cur = max(0.0, cur + delta)
        if out_dur > 0:
            cur = min(cur, out_dur)
        state[key] = cur
        await sync_ytdl_task(task_id)
        await ytdl_fade_menu_cb(c, cb)
    except Exception as ex:
        Altruix.log(f"YTDL Fade Adj Error: {ex}\n{traceback.format_exc()}")
        try:
            await cb.answer(f"Error: {ex}", show_alert=True)
        except:
            pass

@Altruix.bot.on_callback_query(filters.regex(r"^ytdl_fade_reset#([#\w]+)$"))
@iuser_check
async def ytdl_fade_reset_cb(c: Client, cb: CallbackQuery):
    try:
        task_id = cb.matches[0].group(1)
        state = Altruix.YTDL_STATE.get(task_id)
        if not state:
            return await cb.answer("Sesi kedaluwarsa.", show_alert=True)
        state["fade_in"] = 0.0
        state["fade_out"] = 0.0
        await sync_ytdl_task(task_id)
        cb.matches = [type("Match", (), {"group": lambda self, n: task_id})()]
        await ytdl_fade_menu_cb(c, cb)
    except Exception as ex:
        Altruix.log(f"YTDL Fade Reset Error: {ex}\n{traceback.format_exc()}")
        try:
            await cb.answer(f"Error: {ex}", show_alert=True)
        except:
            pass
