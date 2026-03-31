# Main/plugins/bot/xstories_bot.py
# Specialized Bot Assistant Plugin for Story Picker Dashboard
# This file handles Inline Queries and Callbacks for the Userbot Story plugin.

from Main import Altruix
from pyrogram import Client, filters, enums, raw
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, 
    InlineQuery, InlineQueryResultArticle, InputTextMessageContent
)
from pyrogram.handlers import InlineQueryHandler, CallbackQueryHandler
from pyrogram.errors import MessageNotModified as BotMessageNotModified
import asyncio
import re
import random
import string
import logging
import traceback
import time

# Shared state persistence logic (Imported from userbot plugin for synchronization)
from Main.plugins.userbot.xstories import get_session, save_session

STORIES_PER_PAGE = 10

# ============================================================================
# MENU BUILDERS (Shared UI logic)
# ============================================================================

def build_story_menu_text(session):
    """
    Build HTML text for Story Picker menu.
    """
    target = session.get("target") or "Target"
    target_display = session.get("target_display", "Target")
    stories = session.get("story_data", [])
    selected = session.get("selected", set())
    total = len(stories)
    page = session.get("page", 0)
    total_pages = max(1, (total + STORIES_PER_PAGE - 1) // STORIES_PER_PAGE)
    
    # Clamp page
    if page >= total_pages: page = total_pages - 1
    if page < 0: page = 0
    
    start_idx = page * STORIES_PER_PAGE
    end_idx = min(start_idx + STORIES_PER_PAGE, total)
    page_stories = stories[start_idx:end_idx]
    
    # Clickable user link logic [Standardized v1.0.609]
    target_id = session.get("target_id")
    target_orig = session.get("target_name", "Target")
    
    # If we have the raw components, build a clean robust link
    if target_id and target_orig:
        from html import escape
        clean_name = escape(str(target_orig))
        target_username = session.get("target")
        
        # Determine best clickable link
        if target_username and not str(target_username).lstrip("-").isdigit():
            link = f"https://t.me/{str(target_username).lstrip('@')}"
        elif str(target_id).startswith("-100"):
            stripped_id = str(target_id).replace("-100", "")
            link = f"https://t.me/c/{stripped_id}/1"
        else:
            # Safe fallback for typical users and chats avoiding tag stripper errors
            link = f"tg://openmessage?user_id={str(target_id).lstrip('-')}"
        
        user_link = f'<a href="{link}">{clean_name}</a> (<code>{target_id}</code>)'
    else:
        # Fallback to display string
        user_link = session.get("target_display", "Target")

    lines = [
        f"<blockquote expandable>",
        f"<b>📖 Story Picker</b>",
        f"━━━━━━━━━━━━━━━━━━",
        f"• <b>Target:</b> {user_link}",
        f"• <b>Stories:</b> {total} found",
        f"• <b>Selected:</b> {len(selected)}/{total}",
        f"• <b>Send as Album:</b> {'ON' if session.get('send_as_album') else 'OFF'}"
    ]
    
    # Progress/Status from Background Task
    status_text = session.get("status_text")
    if status_text:
        lines.append(f"━━━━━━━━━━━━━━━━━━")
        lines.append(f"⚡ <b>Status:</b> {status_text}")
    
    lines.append(f"━━━━━━━━━━━━━━━━━━")
    lines.append("")
    
    for i, (story_id, stype) in enumerate(page_stories, start_idx + 1):
        check = "✅" if story_id in selected else "⬜️"
        lines.append(f"{check} {i}. Story #{story_id} ({stype})")
    
    lines.append("")
    lines.append("<i>Tap tombol untuk memilih story, lalu tekan Download.</i>")
    lines.append("</blockquote>")
    
    return "\n".join(lines)

def build_story_menu_kb(session_id, session):
    """
    Build InlineKeyboardMarkup for Story Picker.
    """
    stories = session.get("story_data", [])
    selected = session.get("selected", set())
    client_id = session.get("client_id")
    page = session.get("page", 0)
    total = len(stories)
    total_pages = max(1, (total + STORIES_PER_PAGE - 1) // STORIES_PER_PAGE)
    
    # Clamp page
    if page >= total_pages: page = total_pages - 1
    if page < 0: page = 0
    
    start_idx = page * STORIES_PER_PAGE
    end_idx = min(start_idx + STORIES_PER_PAGE, total)
    page_stories = stories[start_idx:end_idx]
    
    # Get dynamic button style
    from Main.utils.file_helpers import get_user_button_style
    user_style = get_user_button_style(client_id) if client_id else 0
    
    rows = []
    
    menu_mode = session.get("menu_mode", "full")
    
    if menu_mode == "hide":
        # Mode hide menu: hanya 3 tombol utama
        rows.append([
            InlineKeyboardButton(f"Download Selected ({len(selected)})", callback_data=f"sdl_dlsel_{session_id}", style=user_style),
        ])
        rows.append([
            InlineKeyboardButton("Cancel", callback_data=f"sdl_cancel_{session_id}", style=user_style),
            InlineKeyboardButton("Show Menu", callback_data=f"sdl_togmenu_{session_id}", style=user_style),
        ])
        return InlineKeyboardMarkup(rows)

    # Mode full menu (Default)
    # Story toggle buttons (2 per row)
    row = []
    for i, (story_id, stype) in enumerate(page_stories, start_idx + 1):
        icon = "✅" if story_id in selected else "⬜"
        intent = 0 if story_id in selected else 1 # If checked, clicking it means intent to UNcheck
        short_type = "🎬" if "Video" in stype else "🖼"
        row.append(InlineKeyboardButton(
            f"{icon} {i}. {short_type} #{story_id}",
            callback_data=f"sdl_set_{session_id}_{story_id}_{intent}",
            style=user_style
        ))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    
    # Pagination
    if total_pages > 1:
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("«", callback_data=f"sdl_page_{session_id}_{page - 1}", style=user_style))
        else:
            nav_row.append(InlineKeyboardButton("·", callback_data=f"sdl_noop_{session_id}", style=user_style))
        
        nav_row.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data=f"sdl_noop_{session_id}", style=user_style))
        
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton("»", callback_data=f"sdl_page_{session_id}_{page + 1}", style=user_style))
        else:
            nav_row.append(InlineKeyboardButton("·", callback_data=f"sdl_noop_{session_id}", style=user_style))
        
        rows.append(nav_row)
    
    # Actions
    rows.append([
        InlineKeyboardButton("Select All", callback_data=f"sdl_selall_{session_id}", style=user_style),
        InlineKeyboardButton("Deselect All", callback_data=f"sdl_desel_{session_id}", style=user_style),
    ])
    
    wm_icon = "Watermark: ON" if session.get("watermark", True) else "Watermark: OFF"
    alb_icon = "Album: ON" if session.get("send_as_album") else "Album: OFF"
    rows.append([
        InlineKeyboardButton(wm_icon, callback_data=f"sdl_togwm_{session_id}", style=user_style),
        InlineKeyboardButton(alb_icon, callback_data=f"sdl_togalb_{session_id}", style=user_style),
    ])

    rows.append([
        InlineKeyboardButton("Refresh", callback_data=f"sdl_refresh_{session_id}", style=user_style),
        InlineKeyboardButton("Reset Status", callback_data=f"sdl_reset_{session_id}", style=user_style),
    ])

    rows.append([
        InlineKeyboardButton(f"Download Selected ({len(selected)})", callback_data=f"sdl_dlsel_{session_id}", style=user_style),
    ])
    
    rows.append([
        InlineKeyboardButton("Download All", callback_data=f"sdl_dlall_{session_id}", style=user_style),
        InlineKeyboardButton("Cancel", callback_data=f"sdl_cancel_{session_id}", style=user_style),
    ])
    
    # Toggle Menu Button
    rows.append([
        InlineKeyboardButton("Hide Menu", callback_data=f"sdl_togmenu_{session_id}", style=user_style),
    ])
    
    return InlineKeyboardMarkup(rows)

# ============================================================================
# BOT HANDLERS
# ============================================================================

async def handle_story_inline(client: Client, query: InlineQuery):
    """
    Handle inline queries for Story Picker.
    """
    q_text = query.query
    if not q_text or not q_text.startswith("sdl_menu_sid_"):
        return
        
    # Extract session ID (6 chars)
    raw_sid = q_text.replace("sdl_menu_sid_", "")
    sid = raw_sid[:6]
    session = await get_session(sid)
    
    if not session:
        Altruix.log(f"BOT_DISPATCHER: No session for SID '{sid}'.", level=logging.DEBUG)
        try: await query.answer(results=[], cache_time=0)
        except: pass
        return
        
    try:
        text = build_story_menu_text(session)
        kb = build_story_menu_kb(sid, session)
        clean_target = re.sub(r'<[^>]+>', '', session.get('target_display', 'Target'))
        
        # Try High-level
        try:
            await query.answer(
                results=[
                    InlineQueryResultArticle(
                        title="📖 Story Picker Dashboard",
                        description=f"Select stories from {clean_target}",
                        input_message_content=InputTextMessageContent(
                            text,
                            parse_mode=enums.ParseMode.HTML,
                            disable_web_page_preview=True
                        ),
                        reply_markup=kb
                    )
                ],
                cache_time=0
            )
            Altruix.log(f"BOT_DISPATCHER: Inline answer (High-level) sent for {sid}", level=logging.DEBUG)
            return
        except Exception as high_e:
            Altruix.log(f"BOT_DISPATCHER: High-level answer failed: {high_e}. Falling back to raw API.", level=logging.DEBUG)
        
        # Raw API Fallback (Bypass PEER_ID_INVALID)
        from pyrogram.raw.types import (
            InputBotInlineResult, InputBotInlineMessageText,
            ReplyInlineMarkup, KeyboardButtonRow, KeyboardButtonCallback
        )
        
        # [v1.0.609] Parse HTML to entities for Raw API
        try:
            parsed = client.parser.parse(text, enums.ParseMode.HTML)
            if isinstance(parsed, dict):
                entities = parsed.get("entities")
                message_text = parsed.get("message")
            else:
                message_text, entities = parsed
        except Exception:
            entities = None
            message_text = re.sub(r'<[^>]+>', '', text)  # Strip HTML tags for plain fallback

        raw_rows = []
        for btn_row in kb.inline_keyboard:
            raw_buttons = []
            for btn in btn_row:
                raw_buttons.append(KeyboardButtonCallback(
                    text=btn.text,
                    data=btn.callback_data.encode() if btn.callback_data else b""
                ))
            raw_rows.append(KeyboardButtonRow(buttons=raw_buttons))
        
        raw_markup = ReplyInlineMarkup(rows=raw_rows)
        result_id = f"st_dash_{sid}_{random.randint(100, 999)}"
        
        raw_result = InputBotInlineResult(
            id=result_id,
            type="article",
            title="📖 Story Picker Dashboard",
            description=f"Select stories from {clean_target}",
            send_message=InputBotInlineMessageText(
                message=message_text,
                entities=entities,
                reply_markup=raw_markup,
                no_webpage=True
            )
        )
        
        await client.invoke(
            raw.functions.messages.SetInlineBotResults(
                query_id=int(query.id),
                results=[raw_result],
                cache_time=0,
                gallery=False,
                private=True
            )
        )
        Altruix.log(f"BOT_DISPATCHER: Inline answer (Raw) sent for {sid}", level=logging.DEBUG)
        
    except Exception as e:
        Altruix.log(f"BOT_DISPATCHER: FATAL ERROR in handle_story_inline: {repr(e)}\n{traceback.format_exc()}", level=logging.ERROR)

async def story_download_callback(client: Client, cb: CallbackQuery):
    """
    Handle callback queries for Story Picker.
    """
    from Main.internals.settings_handlers.utils import check_authorization
    if not await check_authorization(cb):
        return
    
    data = cb.data
    parts = data.split("_")
    if len(parts) < 3: return
    
    action = parts[1]
    # [v1.0.614] Fix: sid is ALWAYS parts[2] in the callback data. 
    # cb.message is None for inline results, so we avoid accessing via_bot.
    sid = parts[2]
    
    # Properly await get_session (Imported from xstories)
    session = await get_session(sid)
    
    if not session:
        await cb.answer("⏰ Session story telah kedaluwarsa atau hilang.", show_alert=True)
        return
    
    # 1. Mutex Check & Intent-based Throttling (v1.0.602)
    # Heavy actions require a mutex to prevent race conditions.
    # Light actions (toggles, pages) use a much shorter lock or no lock.
    HEAVY_ACTIONS = ["dlsel", "dlall", "confirmall", "refresh"]
    is_heavy = action in HEAVY_ACTIONS
    
    now = time.time()
    busy_until = session.get("busy_until", 0)
    
    if is_heavy and busy_until > now:
        remaining = int(busy_until - now)
        return await cb.answer(f"⚡ Sistem sedang memproses, silakan tunggu... ({remaining}s)", show_alert=False)
    
    # Set Busy for heavy actions (longer) or light actions (ultra-short stabilization)
    if action != "reset":
        session["busy_until"] = now + (30 if is_heavy else 0.5)
    await save_session(sid, session)
    
    try:
        if action == "noop":
            await cb.answer()
            return
            
        elif action == "page":
            await cb.answer()
            if len(parts) < 4: return
            session["page"] = int(parts[3])
            await save_session(sid, update_dict={"page": session["page"]})
            text = build_story_menu_text(session)
            kb = build_story_menu_kb(sid, session)
            try: await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
            except BotMessageNotModified: pass
            return
            
        elif action == "togwm":
            await cb.answer()
            session["watermark"] = not session.get("watermark", True)
            await save_session(sid, update_dict={"watermark": session["watermark"]})
            text = build_story_menu_text(session)
            kb = build_story_menu_kb(sid, session)
            try: await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
            except BotMessageNotModified: pass
            return
            
        elif action == "togalb":
            await cb.answer()
            session["send_as_album"] = not session.get("send_as_album", False)
            await save_session(sid, update_dict={"send_as_album": session["send_as_album"]})
            text = build_story_menu_text(session)
            kb = build_story_menu_kb(sid, session)
            try: await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
            except BotMessageNotModified: pass
            return

        elif action == "togmenu":
            await cb.answer()
            current_mode = session.get("menu_mode", "full")
            session["menu_mode"] = "hide" if current_mode == "full" else "full"
            await save_session(sid, update_dict={"menu_mode": session["menu_mode"]})
            text = build_story_menu_text(session)
            kb = build_story_menu_kb(sid, session)
            try: await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
            except BotMessageNotModified: pass
            return
            
        elif action == "set":
            await cb.answer()
            if len(parts) < 5: return
            story_id = int(parts[3])
            intent = int(parts[4]) # 1 = Select, 0 = Deselect
            
            # Use set() explicitly to avoid 'list' object attribute errors
            selected = set(session.get("selected", []))
            is_currently_selected = (story_id in selected)
            
            # Intent-based Check: Avoid redundant toggling if UI is outdated
            changed = False
            if intent == 1 and not is_currently_selected:
                selected.add(story_id)
                changed = True
            elif intent == 0 and is_currently_selected:
                selected.discard(story_id)
                changed = True
            
            if not changed:
                # User clicked an outdated button, but the state is already what they wanted
                Altruix.log(f"STORY_CB: SID {sid} | Story {story_id} already at intent {intent}. No-op.", level=logging.DEBUG)
                return
                
            session["selected"] = selected
            await save_session(sid, update_dict={"selected": selected})
            text = build_story_menu_text(session)
            kb = build_story_menu_kb(sid, session)
            try: await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
            except BotMessageNotModified: pass
            return
            
        elif action == "selall":
            await cb.answer()
            session["selected"] = set(s[0] for s in session.get("story_data", []))
            await save_session(sid, update_dict={"selected": session["selected"]})
            text = build_story_menu_text(session)
            kb = build_story_menu_kb(sid, session)
            try: await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
            except BotMessageNotModified: pass
            return
            
        elif action == "desel":
            await cb.answer()
            session["selected"] = set()
            await save_session(sid, update_dict={"selected": session["selected"]})
            text = build_story_menu_text(session)
            kb = build_story_menu_kb(sid, session)
            try: await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
            except BotMessageNotModified: pass
            return
            
        elif action == "dlsel":
            selected = session.get("selected", set())
            if not selected:
                return await cb.answer("❌ Belum ada story yang dipilih!", show_alert=True)
            
            await cb.answer(f"⬇️ Downloading {len(selected)} stories...")
            session["status"] = "downloading"
            await save_session(sid, update_dict={"status": "downloading"})
            
            # Start download on Userbot side (via Background Task)
            from Main.plugins.userbot.xstories import execute_story_download
            asyncio.create_task(execute_story_download(session, list(selected)))
            
        elif action == "dlall":
            total = len(session.get("story_data", []))
            client_id = session.get("client_id")
            from Main.utils.file_helpers import get_user_button_style
            user_style = get_user_button_style(client_id) if client_id else 0
            
            confirm_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"✅ Ya, Download {total} Stories", callback_data=f"sdl_confirmall_{sid}", style=user_style)],
                [InlineKeyboardButton("◀️ Kembali", callback_data=f"sdl_back_{sid}", style=user_style),
                 InlineKeyboardButton("❌ Cancel", callback_data=f"sdl_cancel_{sid}", style=user_style)]
            ])
            
            await cb.edit_message_text(
                f"<b>⚠️ Konfirmasi Download All</b>\n━━━━━━━━━━━━━━━━━━\n"
                f"• <b>User:</b> {session.get('target_display')}\n"
                f"• <b>Total:</b> {total} stories\n\n"
                f"<i>Download seluruh story sekaligus berpotensi FloodWait.\nLanjutkan?</i>",
                reply_markup=confirm_kb, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True
            )
            await cb.answer()
            
        elif action == "confirmall":
            all_ids = [s[0] for s in session.get("story_data", [])]
            await cb.answer(f"⬇️ Downloading all {len(all_ids)} stories...")
            session["status"] = "downloading"
            from Main.plugins.userbot.xstories import execute_story_download
            asyncio.create_task(execute_story_download(session, all_ids))
            
        elif action == "refresh":
            await cb.answer("🔄 Refreshing...")
            client_id = session.get("client_id")
            target = session.get("target")
            
            # Re-scan for new stories if possible with timeout (v1.0.599)
            if client_id and target:
                from Main.plugins.userbot.xstories import discover_stories
                # Try to get the userbot client
                ub_client = next((c for c in Altruix.clients if c.me and c.me.id == client_id), None)
                if ub_client:
                    try:
                        new_story_data = await asyncio.wait_for(discover_stories(ub_client, target), timeout=20.0)
                        if new_story_data:
                            session["story_data"] = new_story_data
                    except asyncio.TimeoutError:
                        await cb.answer("⚠️ Timeout: Gagal mengambil data terbaru.", show_alert=True)
                    except Exception as e:
                        Altruix.log(f"Refresh discovery error: {e}", level=logging.DEBUG)
            
            text = build_story_menu_text(session)
            kb = build_story_menu_kb(sid, session)
            try: await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
            except BotMessageNotModified: pass
            return

        elif action == "reset":
            await cb.answer("⚠️ Dashboard Reset!", show_alert=True)
            session["busy_until"] = 0
            session["status_text"] = None
            text = build_story_menu_text(session)
            kb = build_story_menu_kb(sid, session)
            try: await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
            except BotMessageNotModified: pass
            return
            
        elif action == "back":
            text = build_story_menu_text(session)
            kb = build_story_menu_kb(sid, session)
            try: await cb.edit_message_text(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
            except BotMessageNotModified: pass
            await cb.answer()
            
        elif action == "cancel":
            try: await cb.edit_message_text("<b>📖 Story Picker — Cancelled</b>\n━━━━━━━━━━━━━━━━━━", parse_mode=enums.ParseMode.HTML)
            except: pass
            await get_story_db().find_one_and_delete({"_id": sid})
            await cb.answer("Cancelled ❌")
            
    except Exception as e:
        Altruix.log(f"BOT_DISPATCHER: Story CB Error: {e}", level=logging.ERROR)
        await cb.answer(f"Error: {str(e)[:50]}", show_alert=True)
    finally:
        # Use granular update to release the mutex without overwriting other state
        if session:
            await asyncio.sleep(0.05) # 50ms stabilization
            await save_session(sid, update_dict={"busy_until": 0})

_registered_bots = set()

# Registration logic
def register_story_bot_handlers(bot_client: Client):
    """
    Register story handlers to a bot client.
    """
    if not bot_client: return
    
    # [v1.0.618] Deduplicate handlers to prevent double background tasks
    if bot_client.me and bot_client.me.id in _registered_bots:
        return
        
    try:
        # High priority group (-1)
        bot_client.add_handler(InlineQueryHandler(handle_story_inline, filters.regex(r"^sdl_menu_sid_")), group=-1)
        bot_client.add_handler(CallbackQueryHandler(story_download_callback, filters.regex(r"^sdl_")), group=-1)
        if bot_client.me:
            _registered_bots.add(bot_client.me.id)
        Altruix.log(f"✅ Bot handlers registered for @{bot_client.me.username if bot_client.me else 'Bot'}", level=logging.DEBUG)
    except Exception as e:
        Altruix.log(f"❌ Failed to register bot handlers: {e}", level=logging.DEBUG)

@Altruix.bot.on_inline_query(filters.regex(r"^sdl_menu_sid_"))
async def story_inline_handler(client, query):
    return await handle_story_inline(client, query)

@Altruix.bot.on_callback_query(filters.regex(r"^sdl_"))
async def story_callback_handler(client, cb):
    return await story_download_callback(client, cb)
