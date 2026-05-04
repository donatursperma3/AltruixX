# xalliance_bot.py (Alliance Dashboard)

import asyncio
import html
import random
import time
import os
import psutil
from pyrogram import Client, filters, enums
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, 
    CallbackQuery, InlineQuery, InlineQueryResultArticle, 
    InputTextMessageContent
)
from Main import Altruix
from Main.core.decorators import log_errors
# ✅ LAZY IMPORTS: These are imported inside each handler function
# to avoid load-order dependency (bot plugins load before userbot plugins).
# from Main.plugins.userbot.xalliance import (...)
# from Main.plugins.userbot.xtaskmanager import (...)

PLUGIN_VERSION_FALLBACK = "1.9.100"

def _get_alliance():
    """Lazy import helper for xalliance module."""
    from Main.plugins.userbot.xalliance import (
        get_active_alliance, mass_join_core, LOG_HISTORY,
        PLUGIN_VERSION, START_TIME
    )
    return get_active_alliance, mass_join_core, LOG_HISTORY, PLUGIN_VERSION, START_TIME

# Shared Input State initialized in xalliance.py
if not hasattr(Altruix, "ALLIANCE_WAITING"):
    Altruix.ALLIANCE_WAITING = {}
WAITING = Altruix.ALLIANCE_WAITING

def get_main_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📡 Status Detail", callback_data="all_dash_status"),
            InlineKeyboardButton("🛠 AI Config", callback_data="all_dash_config")
        ],
        [
            InlineKeyboardButton("🚀 Smart Mass Join", callback_data="all_dash_join"),
            InlineKeyboardButton("🎙️ VC Control", callback_data="all_dash_vc")
        ],
        [
            InlineKeyboardButton("📊 Stats Pro", callback_data="all_dash_stats"),
            InlineKeyboardButton("❌ Close Dashboard", callback_data="all_dash_close")
        ]
    ])

@Altruix.register_on_cmd(
    ["alldash"],
    cmd_help={
        "help": "Open Alliance Dashboard",
        "usage": "/alldash",
        "example": "/alldash",
    },
    pm_only=True, # Restrict to private chat for security
)
@log_errors
async def alliance_start_handler(c: Client, m: Message):
    WAITING.pop(m.from_user.id, None)
    if m.from_user.id not in Altruix.config.OWNER_USERS_ID:
        return await m.reply("⛔ <b>Access Denied.</b>\nOnly the Master can access the Alliance Dashboard.")
    
    try:
        _, _, _, PLUGIN_VERSION, _ = _get_alliance()
    except Exception as e:
        return await m.reply(f"⚠️ Alliance plugin not loaded: <code>{e}</code>", parse_mode=enums.ParseMode.HTML)
    
    await m.reply(
        f"⚔️ <b>Alliance Manager Dashboard v{PLUGIN_VERSION}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Selamat datang di pusat kendali Aliansi Altroid-X. "
        f"Gunakan menu di bawah untuk memantau status, mengubah konfigurasi, atau memulai misi massal secara instan.\n\n"
        f"💡 <i>Tips: Gunakan <code>@{c.me.username} logs</code> untuk melihat pantauan terakhir di mana saja.</i>",
        parse_mode=enums.ParseMode.HTML,
        reply_markup=get_main_keyboard()
    )

@Altruix.bot.on_callback_query(filters.regex(r"^all_dash_"))
@log_errors
async def alliance_callback_handler(c: Client, cb: CallbackQuery):
    WAITING.pop(cb.from_user.id, None)
    if cb.from_user.id not in Altruix.config.OWNER_USERS_ID:
        return await cb.answer("⛔ Access Denied.", show_alert=True)

    data = cb.data.replace("all_dash_", "")

    if data == "status":
        status_text = "⏳ <b>Fetching Alliance Status...</b>"
        await cb.edit_message_text(status_text)
        
        active = []
        try:
            get_active_alliance, _, _, _, _ = _get_alliance()
            active = get_active_alliance()
        except Exception:
            pass
        all_sessions = [cli for cli in Altruix.clients if hasattr(cli, 'me') and cli.me]
        
        results = []
        for cli in all_sessions:
            name = html.escape(cli.me.first_name)
            status = "🟢 Online" if cli.is_connected else "🔴 Offline"
            results.append(f"• <b>{name}</b>: {status}")
        
        await cb.edit_message_text(
            f"📡 <b>Alliance Session Status</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            + "\n".join(results) + 
            f"\n\n🏆 <b>Total Active:</b> <code>{len(active)}/{len(all_sessions)}</code>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Main", callback_data="all_dash_main")]])
        )

    elif data == "main":
        try:
            _, _, _, PLUGIN_VERSION, _ = _get_alliance()
        except Exception:
            PLUGIN_VERSION = PLUGIN_VERSION_FALLBACK
        await cb.edit_message_text(
            f"⚔️ <b>Alliance Manager Dashboard v{PLUGIN_VERSION}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Pusat kendali Aliansi Altroid-X. Pilih menu di bawah:",
            reply_markup=get_main_keyboard()
        )

    elif data == "config":
        api_key = await Altruix.config.get_env("AI_API_KEY") or "<i>Not Set</i>"
        provider = await Altruix.config.get_env("AI_PROVIDER") or "gemini"
        delay = await Altruix.config.get_env("AI_DELAY_RANGE") or "5-15"
        
        await cb.edit_message_text(
            f"🛠 <b>AI Configuration Manager</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Provider:</b> <code>{provider}</code>\n"
            f"• <b>API Key:</b> <code>{api_key[:8]}...</code>\n"
            f"• <b>Delay Range:</b> <code>{delay}s</code>\n\n"
            f"Pilih aspek yang ingin diubah:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔑 Update API Key", callback_data="all_dash_set_key")],
                [InlineKeyboardButton("⏳ Adjust Delay", callback_data="all_dash_set_delay")],
                [InlineKeyboardButton("🔙 Back", callback_data="all_dash_main")]
            ])
        )

    elif data == "set_key":
        WAITING[cb.from_user.id] = {"action": "set_key", "msg_id": cb.message.id}
        await cb.edit_message_text(
            "🔑 <b>Update AI API Key</b>\n\n"
            "Silakan kirimkan API Key Gemini terbaru kakak melalui chat ini sekarang.\n"
            "<i>(Format: Teks murni tanpa spasi)</i>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="all_dash_config")]])
        )

    elif data == "set_delay":
        WAITING[cb.from_user.id] = {"action": "set_delay", "msg_id": cb.message.id}
        await cb.edit_message_text(
            "⏳ <b>Adjust AI Delay Range</b>\n\n"
            "Kirimkan rentang jeda baru dalam detik.\n"
            "<b>Format:</b> <code>min-max</code> (Contoh: <code>10-20</code>)",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="all_dash_config")]])
        )

    elif data == "join":
        WAITING[cb.from_user.id] = {"action": "mass_join", "msg_id": cb.message.id}
        await cb.edit_message_text(
            "🚀 <b>Smart Mass Join</b>\n\n"
            "Kirimkan <b>Link Grup</b> atau <b>Username</b> grup yang ingin dimasuki seluruh aliansi.\n"
            "Contoh: <code>@Altroid-X</code> atau <code>https://t.me/AltruixX</code>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="all_dash_main")]])
        )

    elif data == "stats":
        try:
            _, _, _, PLUGIN_VERSION, START_TIME = _get_alliance()
            from Main.utils.essentials import Essentials
            uptime = Essentials.get_readable_time(int(time.time() - START_TIME))
        except Exception:
            uptime = "N/A"
            PLUGIN_VERSION = PLUGIN_VERSION_FALLBACK
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        
        await cb.edit_message_text(
            f"📊 <b>Alliance Pro Statistics</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Uptime:</b> <code>{uptime}</code>\n"
            f"• <b>CPU Load:</b> <code>{cpu}%</code>\n"
            f"• <b>RAM Usage:</b> <code>{ram}%</code>\n"
            f"• <b>Client Count:</b> <code>{len(Altruix.clients)} Sessions</code>\n"
            f"• <b>Dashboard Version:</b> <code>{PLUGIN_VERSION}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="all_dash_main")]])
        )

    elif data == "vc":
        try:
            from Main.plugins.userbot.xalliance_vc import PLUGIN_VERSION
        except: PLUGIN_VERSION = "N/A"
        await cb.edit_message_text(
            f"🎙️ <b>Alliance Voice Chat Controller v{PLUGIN_VERSION}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Kontrol utama untuk Voice Chat Aliansi:\n\n"
            f"• <b>Join:</b> Masukkan semua akun ke VC.\n"
            f"• <b>Leave:</b> Keluarkan semua akun.\n"
            f"• <b>Welcome:</b> Toggle Auto-Welcome user baru.\n"
            f"• <b>Raise:</b> Perintahkan mass Raise Hand.\n"
            f"• <b>Guard:</b> Toggle mode pengamanan aliansi.",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Mass Join", callback_data="all_dash_vc_join"),
                    InlineKeyboardButton("🛑 Mass Leave", callback_data="all_dash_vc_leave")
                ],
                [
                    InlineKeyboardButton("✋ Mass Raise", callback_data="all_dash_vc_raise"),
                    InlineKeyboardButton("👋 Welcome", callback_data="all_dash_vc_welcome")
                ],
                [
                    InlineKeyboardButton("👥 Partisipan", callback_data="all_dash_vc_list"),
                    InlineKeyboardButton("📂 Ambil Daftar", callback_data="all_dash_vc_export")
                ],
                [
                    InlineKeyboardButton("🛡️ Guard Mode", callback_data="all_dash_vc_guard"),
                    InlineKeyboardButton("📝 VC Logs", callback_data="all_dash_vc_log")
                ],
                [InlineKeyboardButton("🔙 Back to Main", callback_data="all_dash_main")]
            ])
        )

    elif data == "vc_join":
        WAITING[cb.from_user.id] = {"action": "vc_join", "msg_id": cb.message.id}
        await cb.edit_message_text(
            "🎙️ <b>Mass Join Voice Chat</b>\n\n"
            "Kirimkan <b>Target Chat ID</b> atau <b>Username</b> grup VC.\n"
            "Contoh: <code>@Altroid-X</code>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="all_dash_vc")]])
        )

    elif data == "vc_leave":
        WAITING[cb.from_user.id] = {"action": "vc_leave", "msg_id": cb.message.id}
        await cb.edit_message_text(
            "🎙️ <b>Mass Leave Voice Chat</b>\n\n"
            "Kirimkan <b>Target Chat ID</b> atau <b>Username</b> grup VC.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="all_dash_vc")]])
        )

    elif data == "vc_welcome":
        # Toggle via userbot logic
        from Main.plugins.userbot.xalliance_vc import VC_WELCOME_ENABLED
        import Main.plugins.userbot.xalliance_vc as xvc
        xvc.VC_WELCOME_ENABLED = not xvc.VC_WELCOME_ENABLED
        status = "Aktif ✅" if xvc.VC_WELCOME_ENABLED else "Nonaktif ❌"
        await cb.answer(f"Auto-Welcome VC: {status}", show_alert=True)
        await cb.edit_message_text(
            f"🎙️ <b>Alliance Voice Chat Controller</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Status Auto-Welcome: <b>{status}</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="all_dash_vc")]])
        )
    
    elif data == "vc_stats":
        WAITING[cb.from_user.id] = {"action": "vc_stats", "msg_id": cb.message.id}
        await cb.edit_message_text(
            "📊 <b>VC Real-time Stats</b>\n\n"
            "Kirimkan <b>Username/ID Chat</b> untuk melihat jumlah partisipan VC tanpa join.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="all_dash_vc")]])
        )
    
    elif data == "vc_raise":
        WAITING[cb.from_user.id] = {"action": "vc_raise", "msg_id": cb.message.id}
        await cb.edit_message_text(
            "✋ <b>Mass Raise Hand</b>\n\n"
            "Kirimkan <b>Username/ID Chat</b> untuk memerintahkan aliansi angkat tangan di VC tersebut.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="all_dash_vc")]])
        )

    elif data == "vc_list":
        WAITING[cb.from_user.id] = {"action": "vc_list", "msg_id": cb.message.id}
        await cb.edit_message_text(
            "👥 <b>Lihat Partisipan VC</b>\n\n"
            "Kirimkan <b>Username/ID Chat</b> untuk menarik daftar partisipan saat ini.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="all_dash_vc")]])
        )

    elif data == "vc_export":
        WAITING[cb.from_user.id] = {"action": "vc_export", "msg_id": cb.message.id}
        await cb.edit_message_text(
            "📂 <b>Ambil Daftar User (.txt)</b>\n\n"
            "Kirimkan <b>Username/ID Chat</b> untuk mengekspor seluruh partisipan VC ke file teks.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="all_dash_vc")]])
        )

    elif data == "vc_guard":
        WAITING[cb.from_user.id] = {"action": "vc_guard", "msg_id": cb.message.id}
        await cb.edit_message_text(
            "🛡️ <b>Toggle Guard Mode</b>\n\n"
            "Kirimkan <b>Username/ID Chat</b> untuk mengaktifkan perlindungan di VC tersebut.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="all_dash_vc")]])
        )

    elif data == "vc_log":
        WAITING[cb.from_user.id] = {"action": "vc_log", "msg_id": cb.message.id}
        await cb.edit_message_text(
            "📝 <b>Toggle VC Logs</b>\n\n"
            "Kirimkan <b>Username/ID Chat</b> untuk mengaktifkan pencatatan event join/leave di VC tersebut.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="all_dash_vc")]])
        )

    elif data == "close":
        await cb.message.delete()
        await cb.answer("Dashboard ditutup.", show_alert=False)

@Altruix.bot.on_message(filters.private & filters.incoming, group=2)
async def alliance_input_handler(c: Client, m: Message):
    if m.from_user.id not in WAITING:
        return await m.continue_propagation()

    state = WAITING.pop(m.from_user.id)
    action = state["action"]
    old_msg_id = state["msg_id"]
    
    if not m.text:
        return await m.continue_propagation()  # ✅ FIX: Don't swallow non-text messages

    await m.delete() # Cleanup user input

    if action == "set_key":
        new_key = m.text.strip()
        await Altruix.config.set_env("AI_API_KEY", new_key)
        await c.edit_message_text(
            m.chat.id, old_msg_id,
            f"✅ <b>API Key Updated!</b>\n"
            f"Kunci baru telah disimpan ke database dan aktif seketika.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Config", callback_data="all_dash_config")]])
        )

    elif action == "set_delay":
        if "-" not in m.text:
            return await c.edit_message_text(m.chat.id, old_msg_id, "❌ Format salah. Gunakan <code>min-max</code>.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Try Again", callback_data="all_dash_set_delay")]]))
        
        await Altruix.config.set_env("AI_DELAY_RANGE", m.text.strip())
        await c.edit_message_text(
            m.chat.id, old_msg_id,
            f"✅ <b>Delay Range Updated!</b>\n"
            f"Jeda baru <code>{m.text.strip()}s</code> telah diterapkan.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Config", callback_data="all_dash_config")]])
        )

    elif action == "mass_join":
        link = m.text.strip()
        try:
            _, mass_join_core, _, _, _ = _get_alliance()
            from Main.plugins.userbot.xtaskmanager import register_task, unregister_task, generate_task_id
        except Exception as e:
            return await c.edit_message_text(m.chat.id, old_msg_id, f"⚠️ Alliance plugin error: <code>{e}</code>")
        tid = generate_task_id("ALL")
        register_task(tid, asyncio.current_task(), "Bot Alliance Join", "xalliance_bot", m.from_user.id, f"Target: {link}")
        
        await c.edit_message_text(m.chat.id, old_msg_id, f"⏳ <b>Orchestrating Mass Join [{tid}]:</b> <code>{link}</code>...")
        
        try:
            results = await mass_join_core(link, tid=tid)
            await c.edit_message_text(
                m.chat.id, old_msg_id,
                f"🚀 <b>Mass Join Complete [{tid}]</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                + "\n".join(results),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="all_dash_main")]])
            )
        except asyncio.CancelledError:
            await c.edit_message_text(m.chat.id, old_msg_id, f"🛑 <b>Mass Join Task {tid} Cancelled.</b>", 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="all_dash_main")]]))
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
            await status_msg.edit_text(f"🎙️ <b>VC Mass Join Complete</b>\nTarget: <code>{raw_target}</code>\n━━━━━━━━━━━━━━━━━━━━\n" + "\n".join(results), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="all_dash_vc")]]))

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
            await status_msg.edit_text(f"🎙️ <b>VC Mass Leave Complete</b>\nTarget: <code>{raw_target}</code>\n━━━━━━━━━━━━━━━━━━━━\n" + "\n".join(results), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="all_dash_vc")]]))

        elif action == "vc_stats":
            master = Altruix.clients[0]
            call_info = await get_full_vc_info(master, target)
            if not call_info:
                return await c.send_message(m.chat.id, f"❌ No active VC in <code>{raw_target}</code>.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="all_dash_vc")]]))
            count = call_info.participants_count
            await c.send_message(m.chat.id, f"🎙️ <b>VC Stats for</b> <code>{raw_target}</code>\n👥 <b>Total Participants:</b> <code>{count}</code>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="all_dash_vc")]]))

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
            await status_msg.edit_text(f"✅ <b>All accounts in VC have raised hands.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="all_dash_vc")]]))

        elif action == "vc_list":
            master = Altruix.clients[0]
            report, buttons = await get_vc_participants_report(master, target, page=0)
            if report: await c.send_message(m.chat.id, report, reply_markup=buttons)
            else: await c.send_message(m.chat.id, f"❌ No active VC found in <code>{raw_target}</code>.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="all_dash_vc")]]))

        elif action == "vc_guard":
            is_enabled = GUARD_MODE.get(target, False)
            GUARD_MODE[target] = not is_enabled
            status_env = "Aktif ✅" if GUARD_MODE[target] else "Nonaktif ❌"
            await c.send_message(m.chat.id, f"🛡️ <b>VC Guard Mode in <code>{raw_target}</code>:</b> <code>{status_env}</code>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="all_dash_vc")]]))

        elif action == "vc_log":
            is_enabled = VC_LOG_ENABLED.get(target, False)
            VC_LOG_ENABLED[target] = not is_enabled
            status_env = "Aktif ✅" if VC_LOG_ENABLED[target] else "Nonaktif ❌"
            await c.send_message(m.chat.id, f"📝 <b>VC Monitoring in <code>{raw_target}</code>:</b> <code>{status_env}</code>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="all_dash_vc")]]))

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
                else: await c.send_message(m.chat.id, f"❌ <b>No Active VC</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="all_dash_vc")]]))
            except Exception as e: await c.send_message(m.chat.id, f"❌ <b>Error:</b> <code>{str(e)}</code>")


@Altruix.bot.on_inline_query(filters.regex(r"logs$"))
async def alliance_inline_logs(c: Client, q: InlineQuery):
    if q.from_user.id not in Altruix.config.OWNER_USERS_ID: return
    
    try:
        _, _, LOG_HISTORY, _, _ = _get_alliance()
    except Exception:
        return
    
    results = []
    # Show items in reverse (latest first)
    for i, log in enumerate(reversed(LOG_HISTORY)):
        results.append(
            InlineQueryResultArticle(
                title=f"Alert: {log['session']} in {log['chat']}",
                description=f"[{log['time']}] {log['text']}",
                input_message_content=InputTextMessageContent(
                    f"🕵️‍♂️ <b>Alliance Monitor Alert</b>\n"
                    f"👤 <b>Session:</b> <code>{log['session']}</code>\n"
                    f"💬 <b>Chat:</b> <code>{log['chat']}</code>\n"
                    f"🕒 <b>Time:</b> <code>{log['time']}</code>\n"
                    f"🔗 <a href='{log['link']}'>Jump to Message</a>\n"
                    f"📝 <b>Text:</b> <code>{html.escape(log['text'])}...</code>",
                    parse_mode=enums.ParseMode.HTML
                )
            )
        )
    
    if not results:
        results.append(
            InlineQueryResultArticle(
                title="No Monitoring Logs Yet",
                description="Aliansi belum mendeteksi keyword apapun.",
                input_message_content=InputTextMessageContent("Belum ada log monitor yang tersimpan.")
            )
        )
        
    await q.answer(results, cache_time=0, is_personal=True)

@Altruix.bot.on_callback_query(filters.regex(r"^vclist_p:"))
@log_errors
async def vclist_pagination_handler(c: Client, cb: CallbackQuery):
    if cb.from_user.id not in Altruix.config.OWNER_USERS_ID:
        return await cb.answer("⛔ Access Denied.", show_alert=True)
        
    try:
        _, chat_id, page = cb.data.split(":")
        page = int(page)
        # chat_id might be a negative string or a username
        if chat_id.startswith("-") and chat_id[1:].isdigit():
            chat_id = int(chat_id)
            
        from Main.plugins.userbot.xalliance_vc import get_vc_participants_report
        # We use the first client as the worker for fetching info
        master = Altruix.clients[0]
        
        report, buttons = await get_vc_participants_report(master, chat_id, page=page)
        if report:
            await cb.edit_message_text(report, reply_markup=buttons, disable_web_page_preview=True)
        else:
            await cb.answer("❌ Failed to fetch page. VC might have ended.", show_alert=True)
            
    except Exception as e:
        await cb.answer(f"❌ Error: {str(e)}", show_alert=True)
