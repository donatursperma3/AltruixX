
# Main/internals/settings_handlers/alliance_handlers.py
# Alliance Manager Dashboard - Integrated into /settings > Bot Controls
# Uses lazy imports from xalliance.py to avoid load-order dependency.

import asyncio
import random
import html
import time
import os
import logging
import psutil
from pyrogram import Client, filters, enums
from pyrogram.types import (
    CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    Message
)
from pyrogram.enums import ParseMode, ButtonStyle
from Main import Altruix
from Main.core.decorators import log_errors, iuser_check
from .utils import check_authorization, edit_cb

logger = logging.getLogger(__name__)

# ─── Shared Input State ───────────────────────────────────────────
if not hasattr(Altruix, "ALLIANCE_WAITING"):
    Altruix.ALLIANCE_WAITING = {}
WAITING = Altruix.ALLIANCE_WAITING

# ─── Lazy Import Helper ──────────────────────────────────────────
def _get_alliance_module():
    """Lazy import from xalliance.py (userbot plugin) to avoid load-order issues."""
    from Main.plugins.userbot.xalliance import (
        get_active_alliance, mass_join_core, LOG_HISTORY,
        PLUGIN_VERSION, START_TIME
    )
    return get_active_alliance, mass_join_core, LOG_HISTORY, PLUGIN_VERSION, START_TIME


def _get_user_style(user_id):
    from Main.utils.file_helpers import get_user_button_style
    return get_user_button_style(user_id)


def get_alliance_keyboard(user_id=None):
    style = _get_user_style(user_id) if user_id else ButtonStyle.DEFAULT
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📡 Status Detail", callback_data="all_dash_status", style=style),
            InlineKeyboardButton("🛠 AI Config", callback_data="all_dash_config", style=style)
        ],
        [
            InlineKeyboardButton("🚀 Smart Mass Join", callback_data="all_dash_join", style=style),
            InlineKeyboardButton("🎙️ VC Control", callback_data="all_dash_vc", style=style)
        ],
        [
            InlineKeyboardButton("📊 Stats Pro", callback_data="all_dash_stats", style=style),
            InlineKeyboardButton("❌ Close", callback_data="all_dash_close", style=style)
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="bot_controls_menu", style=style)
        ]
    ])


# ─── Entry Point (from Bot Controls menu) ─────────────────────────
@Altruix.bot.on_callback_query(filters.regex(r"^alliance_dashboard$"))
@iuser_check
@log_errors
async def alliance_dashboard_entry(c: Client, cb: CallbackQuery):
    WAITING.pop(cb.from_user.id, None)
    if not await check_authorization(cb):
        return
    
    try:
        _, _, _, PLUGIN_VERSION, _ = _get_alliance_module()
    except Exception as e:
        await cb.answer(f"⚠️ Alliance plugin not loaded: {e}", show_alert=True)
        return
    
    await edit_cb(
        cb,
        f"⚔️ <b>Alliance Manager Dashboard v{PLUGIN_VERSION}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Pusat kendali Aliansi Altroid-X.\n"
        f"Gunakan menu di bawah untuk memantau status, mengubah konfigurasi, atau memulai misi massal.\n\n"
        f"💡 <i>Tips: Gunakan <code>@{(c.me.username if c.me else 'bot')} logs</code> untuk melihat pantauan di mana saja.</i>",
        reply_markup=get_alliance_keyboard(cb.from_user.id)
    )


# ─── Callback Handlers ────────────────────────────────────────────
@Altruix.bot.on_callback_query(filters.regex(r"^all_dash_"))
@iuser_check
@log_errors
async def alliance_callback_handler(c: Client, cb: CallbackQuery):
    WAITING.pop(cb.from_user.id, None)
    if not await check_authorization(cb):
        return

    data = cb.data.replace("all_dash_", "")
    style = _get_user_style(cb.from_user.id)

    if data == "status":
        try:
            get_active_alliance, _, _, _, _ = _get_alliance_module()
        except Exception as e:
            await cb.answer(f"⚠️ Alliance plugin error: {e}", show_alert=True)
            return
        
        status_text = "⏳ <b>Fetching Alliance Status...</b>"
        await edit_cb(cb, status_text)
        
        active = get_active_alliance()
        all_sessions = [cli for cli in Altruix.clients if hasattr(cli, 'me') and cli.me]
        
        results = []
        for cli in all_sessions:
            name = html.escape(cli.me.first_name)
            status = "🟢 Online" if cli.is_connected else "🔴 Offline"
            results.append(f"• <b>{name}</b>: {status}")
        
        await edit_cb(
            cb,
            f"📡 <b>Alliance Session Status</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            + "\n".join(results) + 
            f"\n\n🏆 <b>Total Active:</b> <code>{len(active)}/{len(all_sessions)}</code>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Dashboard", callback_data="alliance_dashboard", style=style)]])
        )

    elif data == "main":
        # Redirect back to dashboard entry
        await alliance_dashboard_entry(c, cb)

    elif data == "config":
        api_key = await Altruix.config.get_env("AI_API_KEY") or "<i>Not Set</i>"
        provider = await Altruix.config.get_env("AI_PROVIDER") or "gemini"
        delay = await Altruix.config.get_env("AI_DELAY_RANGE") or "5-15"
        
        # Mask API key for display
        display_key = f"{api_key[:8]}..." if isinstance(api_key, str) and len(api_key) > 8 else api_key
        
        await edit_cb(
            cb,
            f"🛠 <b>AI Configuration Manager</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Provider:</b> <code>{provider}</code>\n"
            f"• <b>API Key:</b> <code>{display_key}</code>\n"
            f"• <b>Delay Range:</b> <code>{delay}s</code>\n\n"
            f"Pilih aspek yang ingin diubah:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔑 Update API Key", callback_data="all_dash_set_key", style=style)],
                [InlineKeyboardButton("⏳ Adjust Delay", callback_data="all_dash_set_delay", style=style)],
                [InlineKeyboardButton("🔙 Back", callback_data="alliance_dashboard", style=style)]
            ])
        )

    elif data == "set_key":
        WAITING[cb.from_user.id] = {"action": "set_key", "msg_id": cb.inline_message_id or (cb.message.id if cb.message else None)}
        await edit_cb(
            cb,
            "🔑 <b>Update AI API Key</b>\n\n"
            "Silakan kirimkan API Key Gemini terbaru melalui chat ini sekarang.\n"
            "<i>(Format: Teks murni tanpa spasi)</i>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="all_dash_config", style=style)]])
        )

    elif data == "set_delay":
        WAITING[cb.from_user.id] = {"action": "set_delay", "msg_id": cb.inline_message_id or (cb.message.id if cb.message else None)}
        await edit_cb(
            cb,
            "⏳ <b>Adjust AI Delay Range</b>\n\n"
            "Kirimkan rentang jeda baru dalam detik.\n"
            "<b>Format:</b> <code>min-max</code> (Contoh: <code>10-20</code>)",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="all_dash_config", style=style)]])
        )

    elif data == "join":
        WAITING[cb.from_user.id] = {"action": "mass_join", "msg_id": cb.inline_message_id or (cb.message.id if cb.message else None)}
        await edit_cb(
            cb,
            "🚀 <b>Smart Mass Join</b>\n\n"
            "Kirimkan <b>Link Grup</b> atau <b>Username</b> grup yang ingin dimasuki seluruh aliansi.\n"
            "Contoh: <code>@AltruixX</code> atau <code>https://t.me/AltruixX</code>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="alliance_dashboard", style=style)]])
        )

    elif data == "vc":
        try:
            from Main.plugins.userbot.xalliance_vc import PLUGIN_VERSION as VC_VERSION
        except: VC_VERSION = "N/A"
        await edit_cb(
            cb,
            f"🎙️ <b>Alliance Voice Chat Controller v{VC_VERSION}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Kontrol utama untuk Voice Chat Aliansi:\n\n"
            f"• <b>Join:</b> Masukkan semua akun ke VC.\n"
            f"• <b>Leave:</b> Keluarkan semua akun.\n"
            f"• <b>Welcome:</b> Toggle Auto-Welcome user baru.\n"
            f"• <b>Raise:</b> Perintahkan mass Raise Hand.\n"
            f"• <b>Guard:</b> Toggle mode pengamanan aliansi.",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Mass Join", callback_data="all_dash_vc_join", style=style),
                    InlineKeyboardButton("🛑 Mass Leave", callback_data="all_dash_vc_leave", style=style)
                ],
                [
                    InlineKeyboardButton("✋ Mass Raise", callback_data="all_dash_vc_raise", style=style),
                    InlineKeyboardButton("👋 Welcome", callback_data="all_dash_vc_welcome", style=style)
                ],
                [
                    InlineKeyboardButton("👥 Partisipan", callback_data="all_dash_vc_list", style=style),
                    InlineKeyboardButton("📂 Ambil Daftar", callback_data="all_dash_vc_export", style=style)
                ],
                [
                    InlineKeyboardButton("🛡️ Guard Mode", callback_data="all_dash_vc_guard", style=style),
                    InlineKeyboardButton("📝 VC Logs", callback_data="all_dash_vc_log", style=style)
                ],
                [InlineKeyboardButton("🔙 Back to Dashboard", callback_data="alliance_dashboard", style=style)]
            ])
        )

    elif data == "vc_join":
        WAITING[cb.from_user.id] = {"action": "vc_join", "msg_id": cb.inline_message_id or (cb.message.id if cb.message else None)}
        await edit_cb(
            cb,
            "🎙️ <b>Mass Join Voice Chat</b>\n\n"
            "Kirimkan <b>Target Chat ID</b> atau <b>Username</b> grup VC.\n"
            "Contoh: <code>@AltruixX</code>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="all_dash_vc", style=style)]])
        )

    elif data == "vc_leave":
        WAITING[cb.from_user.id] = {"action": "vc_leave", "msg_id": cb.inline_message_id or (cb.message.id if cb.message else None)}
        await edit_cb(
            cb,
            "🎙️ <b>Mass Leave Voice Chat</b>\n\n"
            "Kirimkan <b>Target Chat ID</b> atau <b>Username</b> grup VC.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="all_dash_vc", style=style)]])
        )

    elif data == "vc_welcome":
        try:
            from Main.plugins.userbot.xalliance_vc import VC_WELCOME_ENABLED
            import Main.plugins.userbot.xalliance_vc as xvc
            xvc.VC_WELCOME_ENABLED = not xvc.VC_WELCOME_ENABLED
            status_env = "Aktif ✅" if xvc.VC_WELCOME_ENABLED else "Nonaktif ❌"
            await cb.answer(f"Auto-Welcome VC: {status_env}", show_alert=True)
            await edit_cb(
                cb,
                f"🎙️ <b>Alliance Voice Chat Controller</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"Status Auto-Welcome: <b>{status_env}</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="all_dash_vc", style=style)]])
            )
        except Exception as e:
            await cb.answer(f"❌ Error: {e}", show_alert=True)

    elif data == "vc_stats":
        WAITING[cb.from_user.id] = {"action": "vc_stats", "msg_id": cb.inline_message_id or (cb.message.id if cb.message else None)}
        await edit_cb(
            cb,
            "📊 <b>VC Real-time Stats</b>\n\n"
            "Kirimkan <b>Username/ID Chat</b> untuk melihat jumlah partisipan VC tanpa join.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="all_dash_vc", style=style)]])
        )
    
    elif data == "vc_raise":
        WAITING[cb.from_user.id] = {"action": "vc_raise", "msg_id": cb.inline_message_id or (cb.message.id if cb.message else None)}
        await edit_cb(
            cb,
            "✋ <b>Mass Raise Hand</b>\n\n"
            "Kirimkan <b>Username/ID Chat</b> untuk memerintahkan aliansi angkat tangan di VC tersebut.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="all_dash_vc", style=style)]])
        )

    elif data == "vc_list":
        WAITING[cb.from_user.id] = {"action": "vc_list", "msg_id": cb.inline_message_id or (cb.message.id if cb.message else None)}
        await edit_cb(
            cb,
            "👥 <b>Lihat Partisipan VC</b>\n\n"
            "Kirimkan <b>Username/ID Chat</b> untuk menarik daftar partisipan saat ini.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="all_dash_vc", style=style)]])
        )

    elif data == "vc_export":
        WAITING[cb.from_user.id] = {"action": "vc_export", "msg_id": cb.inline_message_id or (cb.message.id if cb.message else None)}
        await edit_cb(
            cb,
            "📂 <b>Ambil Daftar User (.txt)</b>\n\n"
            "Kirimkan <b>Username/ID Chat</b> untuk mengekspor seluruh partisipan VC ke file teks.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="all_dash_vc", style=style)]])
        )

    elif data == "vc_guard":
        WAITING[cb.from_user.id] = {"action": "vc_guard", "msg_id": cb.inline_message_id or (cb.message.id if cb.message else None)}
        await edit_cb(
            cb,
            "🛡️ <b>Toggle Guard Mode</b>\n\n"
            "Kirimkan <b>Username/ID Chat</b> untuk mengaktifkan perlindungan di VC tersebut.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="all_dash_vc", style=style)]])
        )

    elif data == "vc_log":
        WAITING[cb.from_user.id] = {"action": "vc_log", "msg_id": cb.inline_message_id or (cb.message.id if cb.message else None)}
        await edit_cb(
            cb,
            "📝 <b>Toggle VC Logs</b>\n\n"
            "Kirimkan <b>Username/ID Chat</b> untuk mengaktifkan pencatatan event join/leave di VC tersebut.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="all_dash_vc", style=style)]])
        )

    elif data == "stats":
        try:
            _, _, _, PLUGIN_VERSION, START_TIME = _get_alliance_module()
            from Main.utils.essentials import Essentials
            uptime = Essentials.get_readable_time(int(time.time() - START_TIME))
        except Exception:
            uptime = "N/A"
            PLUGIN_VERSION = "?"
        
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        
        await edit_cb(
            cb,
            f"📊 <b>Alliance Pro Statistics</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Uptime:</b> <code>{uptime}</code>\n"
            f"• <b>CPU Load:</b> <code>{cpu}%</code>\n"
            f"• <b>RAM Usage:</b> <code>{ram}%</code>\n"
            f"• <b>Client Count:</b> <code>{len(Altruix.clients)} Sessions</code>\n"
            f"• <b>Dashboard Version:</b> <code>{PLUGIN_VERSION}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="alliance_dashboard", style=style)]])
        )

    elif data == "close":
        try:
            await cb.message.delete()
        except Exception:
            pass
        await cb.answer("Dashboard ditutup.", show_alert=False)


# ─── Text Input Handler (for API Key, Delay, Mass Join) ───────────
@Altruix.bot.on_message(filters.private & filters.incoming, group=3)
async def alliance_input_handler(c: Client, m: Message):
    if m.from_user.id not in WAITING:
        return await m.continue_propagation()
    if not await Altruix.is_sudo(m.from_user.id):
        return await m.continue_propagation()

    state = WAITING.pop(m.from_user.id)
    action = state["action"]
    old_msg_id = state["msg_id"]
    style = _get_user_style(m.from_user.id)
    
    if not m.text:
        return await m.continue_propagation()  # ✅ FIX: Don't swallow non-text messages
        
    await m.delete()  # Cleanup user input

    async def edit_msg(text, reply_markup=None):
        try:
            if isinstance(old_msg_id, str): # inline_message_id
                if hasattr(c, "edit_inline_text"):
                    await c.edit_inline_text(
                        inline_message_id=old_msg_id,
                        text=text,
                        reply_markup=reply_markup,
                        parse_mode=ParseMode.HTML
                    )
                else:
                    try:
                        await c.edit_message_text(
                            None, None, text, old_msg_id,
                            reply_markup=reply_markup,
                            parse_mode=ParseMode.HTML
                        )
                    except:
                        await c.edit_message_text(
                            inline_message_id=old_msg_id,
                            text=text,
                            reply_markup=reply_markup,
                            parse_mode=ParseMode.HTML
                        )
            elif old_msg_id:
                await c.edit_message_text(
                    chat_id=m.chat.id,
                    message_id=old_msg_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
            else:
                await c.send_message(m.chat.id, text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"Failed to edit message {old_msg_id}: {e}", exc_info=True)
            try:
                await c.send_message(m.chat.id, text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
            except Exception as ex:
                logger.error(f"Fallback send_message failed: {ex}")

    if action == "set_key":
        new_key = m.text.strip()
        await Altruix.config.set_env("AI_API_KEY", new_key)
        await edit_msg(
            f"✅ <b>API Key Updated!</b>\n"
            f"Kunci baru telah disimpan ke database dan aktif seketika.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Config", callback_data="all_dash_config", style=style)]])
        )

    elif action == "set_delay":
        if "-" not in m.text:
            return await edit_msg(
                "❌ Format salah. Gunakan <code>min-max</code>.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Try Again", callback_data="all_dash_set_delay", style=style)]])
            )
        
        await Altruix.config.set_env("AI_DELAY_RANGE", m.text.strip())
        await edit_msg(
            f"✅ <b>Delay Range Updated!</b>\n"
            f"Jeda baru <code>{m.text.strip()}s</code> telah diterapkan.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Config", callback_data="all_dash_config", style=style)]])
        )

    elif action == "mass_join":
        try:
            _, mass_join_core, _, _, _ = _get_alliance_module()
            from Main.plugins.userbot.xtaskmanager import register_task, unregister_task, generate_task_id
        except Exception as e:
            return await edit_msg(
                f"⚠️ <b>Alliance plugin not loaded:</b> <code>{e}</code>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="alliance_dashboard", style=style)]])
            )

        link = m.text.strip()
        tid = generate_task_id("ALL")
        register_task(tid, asyncio.current_task(), "Bot Alliance Join", "alliance_handlers", m.from_user.id, f"Target: {link}")
        
        await edit_msg(f"⏳ <b>Orchestrating Mass Join [{tid}]:</b> <code>{link}</code>...")
        
        try:
            results = await mass_join_core(link, tid=tid)
            await edit_msg(
                f"🚀 <b>Mass Join Complete [{tid}]</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                + "\n".join(results),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="alliance_dashboard", style=style)]])
            )
        except asyncio.CancelledError:
            await edit_msg(
                f"🛑 <b>Mass Join Task {tid} Cancelled.</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="alliance_dashboard", style=style)]])
            )
        finally:
            unregister_task(tid)

    elif action in ["vc_join", "vc_leave", "vc_stats", "vc_raise", "vc_list", "vc_guard", "vc_log", "vc_export"]:
        raw_target = m.text.strip()
        from Main.plugins.userbot.xalliance_vc import (
            vc_manager, get_full_vc_info, get_vc_participants_report, 
            GUARD_MODE, VC_LOG_ENABLED
        )
        
        # Resolve target to ID if possible
        target = raw_target
        try:
            chat = await c.get_chat(raw_target)
            target = chat.id
        except: pass

        if action == "vc_join":
            from pytgcalls.types import AudioPiped
            status_msg = await c.send_message(m.chat.id, f"🎙️ <b>Orchestrating Mass Join:</b> <code>{raw_target}</code>...")
            results = []
            for client in Altruix.clients:
                if not hasattr(client, 'me') or not client.me: continue
                name = html.escape(client.me.first_name)
                try:
                    # Prime the client session with full VC info (critical for detection)
                    if not await get_full_vc_info(client, target):
                        results.append(f"❌ <b>{name}</b> -> No Active VC")
                        continue
                        
                    call = await vc_manager.get_call(client)
                    await call.join_group_call(target, AudioPiped("Main/assets/silent.mp3"))
                    results.append(f"✅ <b>{name}</b> -> Joined")
                except Exception as e:
                    results.append(f"❌ <b>{name}</b> -> <code>{str(e)}</code>")
                await asyncio.sleep(1.0)
            await status_msg.edit_text(f"🎙️ <b>VC Mass Join Complete</b>\nTarget: <code>{raw_target}</code>\n━━━━━━━━━━━━━━━━━━━━\n" + "\n".join(results), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="all_dash_vc", style=style)]]))

        elif action == "vc_leave":
            status_msg = await c.send_message(m.chat.id, f"🎙️ <b>Orchestrating Mass Leave:</b> <code>{raw_target}</code>...")
            results = []
            for client in Altruix.clients:
                if not hasattr(client, 'me') or not client.me: continue
                try:
                    await vc_manager.leave_call(client.me.id)
                    results.append(f"✅ <b>{html.escape(client.me.first_name)}</b> -> Left")
                except Exception: pass
                await asyncio.sleep(0.5)
            await status_msg.edit_text(f"🎙️ <b>VC Mass Leave Complete</b>\nTarget: <code>{raw_target}</code>\n━━━━━━━━━━━━━━━━━━━━\n" + "\n".join(results), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="all_dash_vc", style=style)]]))

        elif action == "vc_stats":
            master = Altruix.clients[0]
            call_info = await get_full_vc_info(master, target)
            if not call_info:
                return await c.send_message(m.chat.id, f"❌ No active VC in <code>{raw_target}</code>.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="all_dash_vc", style=style)]]))
            count = call_info.participants_count
            await c.send_message(m.chat.id, f"🎙️ <b>VC Stats for</b> <code>{raw_target}</code>\n👥 <b>Total Participants:</b> <code>{count}</code>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="all_dash_vc", style=style)]]))

        elif action == "vc_raise":
            from pyrogram import raw
            from pyrogram.raw.types import InputGroupCall
            status_msg = await c.send_message(m.chat.id, f"✋ <b>Ordering Mass Raise Hand:</b> <code>{raw_target}</code>...")
            for client in Altruix.clients:
                if not hasattr(client, 'me') or not client.me: continue
                try:
                    call_info = await get_full_vc_info(client, target)
                    if call_info:
                        await client.invoke(raw.functions.phone.EditGroupCallParticipant(
                            call=InputGroupCall(id=call_info.id, access_hash=call_info.access_hash),
                            participant=await client.resolve_peer("me"), raise_hand=True
                        ))
                except: pass
                await asyncio.sleep(0.5)
            await status_msg.edit_text(f"✅ <b>All accounts in VC have raised hands.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="all_dash_vc", style=style)]]))

        elif action == "vc_list":
            master = Altruix.clients[0]
            report, buttons = await get_vc_participants_report(master, target, page=0)
            if report: await c.send_message(m.chat.id, report, reply_markup=buttons)
            else: await c.send_message(m.chat.id, f"❌ No active VC found in <code>{raw_target}</code>.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="all_dash_vc", style=style)]]))

        elif action == "vc_guard":
            is_enabled = GUARD_MODE.get(target, False)
            GUARD_MODE[target] = not is_enabled
            status_env = "Aktif ✅" if GUARD_MODE[target] else "Nonaktif ❌"
            await c.send_message(m.chat.id, f"🛡️ <b>VC Guard Mode in <code>{raw_target}</code>:</b> <code>{status_env}</code>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="all_dash_vc", style=style)]]))

        elif action == "vc_log":
            is_enabled = VC_LOG_ENABLED.get(target, False)
            VC_LOG_ENABLED[target] = not is_enabled
            status_env = "Aktif ✅" if VC_LOG_ENABLED[target] else "Nonaktif ❌"
            await c.send_message(m.chat.id, f"📝 <b>VC Monitoring in <code>{raw_target}</code>:</b> <code>{status_env}</code>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="all_dash_vc", style=style)]]))

        elif action == "vc_export":
            from pyrogram.raw.functions.phone import GetGroupParticipants
            from pyrogram.raw.types import InputGroupCall
            master = Altruix.clients[0]
            try:
                call_info = await get_full_vc_info(master, target)
                if call_info:
                    participants = await master.invoke(GetGroupParticipants(
                        call=InputGroupCall(id=call_info.id, access_hash=call_info.access_hash), 
                        ids=[], sources=[], offset="", limit=100
                    ))
                    data = "\n".join([str(p.peer.user_id) for p in participants.participants])
                    filename = f"vc_export_{int(time.time())}.txt"
                    with open(filename, "w") as f: f.write(data)
                    await m.reply_document(filename, caption=f"📂 <b>VC Export:</b> <code>{raw_target}</code>\nTotal: <code>{len(participants.participants)}</code> users.")
                    if os.path.exists(filename): os.remove(filename)
                else: await c.send_message(m.chat.id, f"❌ <b>No Active VC</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="all_dash_vc", style=style)]]))
            except Exception as e: await c.send_message(m.chat.id, f"❌ <b>Error:</b> <code>{str(e)}</code>")
