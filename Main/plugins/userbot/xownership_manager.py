# Main/plugins/userbot/xownership_manager.py
# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
# All rights reserved.

PLUGIN_VERSION = "1.0.14"

import os
import time
import json
import csv
import html
import asyncio
from datetime import datetime
from pyrogram import Client, filters, enums
from pyrogram.types import Message
from pyrogram.errors import FloodWait

from Main import Altruix
from Main.core.decorators import log_errors, iuser_check

# --------------------------------------------------------------------------------
# UTILS & HELPERS
# --------------------------------------------------------------------------------

async def route_log_msg(client: Client, text: str, task_id: str = None):
    """
    [FUNCTION]: route_log_msg
    Mengarahkan pengiriman log berdasarkan prioritas Altroid-X:
    Log Group > Bot Helper PM > Main Bot PM > Saved Messages.
    
    Args:
        client: Instance userbot yang sedang aktif.
        text: Teks yang akan dikirim (HTML Format).
        task_id: ID unik untuk pelacakan proses di log server.
    """
    Altruix.log(f"[OwnershipManager] Menentukan rute log untuk Task: {task_id or 'N/A'}")
    
    # 🔍 Ambil Chat ID tujuan log dari konfigurasi environment
    log_chat_id = await Altruix.config.get_env("LOG_CHAT_ID")
    target_chat = None
    if log_chat_id:
        try: 
            target_chat = int(log_chat_id)
            Altruix.log(f"[OwnershipManager] Log Chat ID detected: {target_chat}")
        except ValueError: 
            Altruix.log(f"[OwnershipManager] Invalid Log Chat ID: {log_chat_id}")
            pass
        
    # 🤖 Identifikasi Bot Assistant (Custom Bot milik user atau Bot Utama sistem)
    custom_bot = Altruix.bot_manager.get_bot(client.me.id) if hasattr(Altruix, 'bot_manager') else None
    main_bot = Altruix.bot
    
    boot_text = text
    status_msg = None
    successful_sender = None
    
    # [PRIORITAS 1 & 2]: Kirim ke Log Group via Bot
    # Menggunakan bot lebih stabil daripada userbot untuk logging grup.
    for bot in [custom_bot, main_bot]:
        if not status_msg and bot and target_chat:
            try: 
                status_msg = await bot.send_message(target_chat, boot_text, parse_mode=enums.ParseMode.HTML)
                successful_sender = bot
                Altruix.log(f"[OwnershipManager] Log terkirim ke Group {target_chat} via {bot.me.username}")
            except Exception as e: 
                Altruix.log(f"[OwnershipManager] Main/Custom Bot to Group failed: {e}")
                pass
        
    # [PRIORITAS 3 & 4]: Kirim ke PM Bot (Jika Bot tidak ada di grup log)
    for bot in [custom_bot, main_bot]:
        if not status_msg and bot:
            try:
                status_msg = await bot.send_message(client.me.id, boot_text, parse_mode=enums.ParseMode.HTML)
                successful_sender = bot
                Altruix.log(f"[OwnershipManager] Log terkirim ke PM via {bot.me.username}")
            except Exception as e: 
                Altruix.log(f"[OwnershipManager] Main/Custom Bot PM failed: {e}")
                pass
            
    # [PRIORITAS 5]: Fallback ke Saved Messages Userbot sendiri
    if not status_msg:
        try:
            status_msg = await client.send_message("me", boot_text, parse_mode=enums.ParseMode.HTML)
            successful_sender = client
            Altruix.log(f"[OwnershipManager] Log sent via Userbot Saved Messages")
        except Exception as e:
            Altruix.log(f"[OwnershipManager] All routing failed, including Userbot: {e}")
        
    return status_msg, successful_sender, target_chat

def fmt_member_count(count):
    """
    [HELPER]: fmt_member_count
    Mempercantik tampilan jumlah angka (Misal: 1500 -> 1.5K, 2000000 -> 2.0M).
    """
    if not count: return "0"
    if count >= 1000000:
        return f"{count/1000000:.1f}M"
    elif count >= 1000:
        return f"{count/1000:.1f}K"
    return str(count)

# --------------------------------------------------------------------------------
# SCANNING ENGINE
# --------------------------------------------------------------------------------

async def perform_ownership_scan(client: Client, status_msg: Message, flags: dict):
    """
    [ENGINE]: perform_ownership_scan
    Mesin pemintai dialog yang akan menelusuri seluruh chat milik user
    dan memfilter chat mana saja yang memiliki status 'OWNER' (Pemilik).
    """
    owned_assets = []
    chats_scanned = 0
    start_time = time.time()
    task_id = flags.get("task_id", "OWN")
    
    # Ekstraksi filter dari perintah user
    public_only = flags.get("pb", False)
    private_only = flags.get("pv", False)
    
    Altruix.log(f"[OwnershipManager] Starting scan task {task_id} (pb={public_only}, pv={private_only})")
    
    # Progress Pacing: Agar tidak terlalu banyak edit yang menyebabkan FloodWait
    last_update = 0
    UPDATE_COOLDOWN = 3.0
    
    async def _update_progress(force=False):
        nonlocal last_update
        if not status_msg: return
        now = time.time()
        if not force and (now - last_update) < UPDATE_COOLDOWN:
            return
        last_update = now
        took = round(now - start_time, 1)
        try:
            await status_msg.edit(
                f"🔎 <b>Ownership Scan in Progress...</b>\n\n"
                f"• <b>Scanned:</b> <code>{chats_scanned}</code> dialogs\n"
                f"• <b>Found:</b> <code>{len(owned_assets)}</code> owned assets\n"
                f"• <b>Time:</b> <code>{took}s</code>\n\n"
                f"<i>Processing... please wait.</i>",
                parse_mode=enums.ParseMode.HTML
            )
        except Exception: pass

    try:
        # [LOOP]: Berjalan di seluruh dialog user secara asinkron
        async for dialog in client.get_dialogs():
            chats_scanned += 1
            chat = dialog.chat
            await asyncio.sleep(0.01) # Mencegah lag pada event loop
            
            # 🛡️ Filter hanya tipe Group dan Channel
            if chat.type not in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP, enums.ChatType.CHANNEL]:
                continue
                
            # Filter pb (publik) / pv (privat)
            if public_only and not chat.username:
                continue
            if private_only and chat.username:
                continue
            
            # --- CEK STATUS OWNER ---
            try:
                # Ambil status member 'me' (diri sendiri)
                me = await chat.get_member("me")
                if me.status == enums.ChatMemberStatus.OWNER:
                    owned_assets.append({
                        "id": chat.id,
                        "title": chat.title,
                        "username": chat.username,
                        "type": chat.type,
                        "members": chat.members_count or 0
                    })
            except FloodWait as fw:
                Altruix.log(f"[OwnershipManager] FloodWait terdeteksi: {fw.value} detik", level=30)
                await asyncio.sleep(fw.value + 3)
                # Retry sekali lagi setelah sleep
                try:
                    me = await chat.get_member("me")
                    if me.status == enums.ChatMemberStatus.OWNER:
                        owned_assets.append({
                            "id": chat.id, "title": chat.title, "username": chat.username,
                            "type": chat.type, "members": chat.members_count or 0
                        })
                except Exception: pass
            except Exception:
                # Abaikan chat yang tidak bisa diakses
                pass
                
            await _update_progress()
            
        await _update_progress(force=True)
        Altruix.log(f"[OwnershipManager] Scan Selesai. Total {len(owned_assets)} ditemukan.")
        return owned_assets, time.time() - start_time
    except Exception as e:
        Altruix.log(f"[OwnershipManager] Critical Scan Error: {e}")
        if status_msg:
            try: await status_msg.edit(f"❌ <b>Scan interrupted:</b> <code>{e}</code>", parse_mode=enums.ParseMode.HTML)
            except Exception: pass
        return None, 0

# --------------------------------------------------------------------------------
# COMMAND: .myownlist
# --------------------------------------------------------------------------------

@Altruix.register_on_cmd(
    ["myownlist", "mol"],
    cmd_help={
        "help": "Scan dan tampilkan daftar semua Group/Channel yang kamu miliki (Owner).",
        "usage": ".myownlist [-pb] [-pv]",
        "example": ".myownlist -pb",
        "detail": "Gunakan -pb untuk filter publik, -pv untuk privat."
    },
)
@iuser_check
@log_errors
async def my_own_list_cmd(client: Client, m: Message):
    """
    [COMMAND]: .myownlist
    Mencari dan menampilkan daftar aset (Group/Channel) di mana user adalah Owner.
    Mendukung output Split-Log untuk menghindari limit Telegram.
    """
    flags = {
        "pb": "-pb" in m.text,
        "pv": "-pv" in m.text,
        "task_id": f"OWN_{int(time.time())}"
    }
    
    Altruix.log(f"[OwnershipManager] Submitting MOL request (Session: {client.me.id})")
    
    # 🛫 Langkah 1: Inisialisasi proses
    init_msg = await m.handle_message("🚀 <b>Initializing Ownership Manager...</b>")
    
    # 🛫 Langkah 2: Buat pesan status log
    # route_log_msg menentukan kemana log dikirim agar tidak mengganggu grup utama.
    status_msg, log_bot, target_chat_id = await route_log_msg(client, f"🚀 <b>Ownership Scan Started</b>\nTask ID: <code>{flags['task_id']}</code>", flags["task_id"])
    if not status_msg:
        Altruix.log(f"[OwnershipManager] CRITICAL: Failed to route log message for task {flags['task_id']}")
        return await init_msg.edit("❌ <b>Gagal mengirim rute log.</b> Periksa setting Log Group.")

    # 🛫 Langkah 3: Eksekusi Scan
    assets, duration = await perform_ownership_scan(client, status_msg, flags)
    
    if assets is None:
        Altruix.log(f"[OwnershipManager] Scan failed/returned None for task {flags['task_id']}")
        return 

    if not assets:
        text = "✅ <b>Scan Selesai.</b>\nTidak ditemukan aset yang dimiliki sesuai kriteria Anda."
        await status_msg.edit(text, parse_mode=enums.ParseMode.HTML)
        await init_msg.edit(text, parse_mode=enums.ParseMode.HTML)
        Altruix.log(f"[OwnershipManager] No assets found for task {flags['task_id']}")
        return

    Altruix.log(f"[OwnershipManager] Processing {len(assets)} found assets for reporting...")

    # [STABILITAS]: Hapus pesan status progres dan ganti dengan laporan baru
    # Hal ini dilakukan untuk menghindari 'EntityBoundsInvalid' saat mengedit pesan panjang.
    try: await status_msg.delete()
    except: pass

    # 🛫 Langkah 4: Pengelompokan & Urutan (Sort)
    # Urutan: Channel > Supergroup > Group
    type_priority = {enums.ChatType.CHANNEL: 1, enums.ChatType.SUPERGROUP: 2, enums.ChatType.GROUP: 3}
    assets.sort(key=lambda x: (type_priority.get(x["type"], 99), x["title"]))

    # Hitung total per tipe dan nomor urut
    type_counts = {}
    type_counters = {}
    for a in assets:
        t = a["type"]
        type_counts[t] = type_counts.get(t, 0) + 1
        type_counters[t] = type_counters.get(t, 0) + 1
        a["seq_num"] = type_counters[t]

    # 🛫 Langkah 5: Pembagian Laporan (Split Log)
    per_part = 20 # 20 item per pesan agar aman dari limit karakter & formatting.
    total_parts = (len(assets) + per_part - 1) // per_part
    current_type = None
    
    dest_chat = target_chat_id or status_msg.chat.id
    Altruix.log(f"[OwnershipManager] Mengirim laporan dalam {total_parts} bagian (Per Part: {per_part}).")

    for p in range(total_parts):
        start = p * per_part
        end = start + per_part
        chunk = assets[start:end]
        
        chunk_lines = []
        for itm in chunk:
             # Header tipe dinamis (Misal: 💎 CHANNELS)
             if itm["type"] != current_type:
                  current_type = itm["type"]
                  type_name = str(current_type).split(".")[-1].replace("_", " ")
                  chunk_lines.append(f"\n<b>💎 {type_name}S ({type_counts[current_type]})</b>\n───────────────")
             
             title_esc = html.escape(itm["title"])
             # Logika pembuatan link yang aman (Menangani supergroup dan username)
             if itm["username"]:
                 title_link = f"<a href='https://t.me/{itm['username']}'>{title_esc}</a>"
             elif str(itm["id"]).startswith("-100"):
                 title_link = f"<a href='https://t.me/c/{str(itm['id']).replace("-100", "").lstrip("-")}/1'>{title_esc}</a>"
             else:
                 title_link = f"<b>{title_esc}</b>"
                 
             user_str = f" | @{itm['username']}" if itm['username'] else ""
             type_icon = "📣" if itm["type"] == enums.ChatType.CHANNEL else "👥"
             m_count = fmt_member_count(itm['members'])
             
             # Format baris per item
             chunk_lines.append(f"{itm['seq_num']}. {type_icon} {title_link}\n└ (<code>{itm['id']}</code>){user_str} | 👤 <code>{m_count}</code>")
        
        body = "\n".join(chunk_lines)
        footer = ""
        if p == total_parts - 1:
            footer = f"\n───────────────\n💡 <b>Tips:</b> Gunakan <code>.moe</code> untuk ekspor JSON/CSV."

        acc_name = html.escape(client.me.first_name)
        acc_id = client.me.id
        header = f"👑 <b>OWNERSHIP REPORT — Part {p+1}/{total_parts}</b>\n• Account: <a href='tg://user?id={acc_id}'>{acc_name}</a>\n━━━━━━━━━━━━━━━━━━\n"
        full_text = f"{header}{body}{footer}\n\n<i>#Task_{flags['task_id']}</i>"
        
        Altruix.log(f"[OwnershipManager] Attempting to send report part {p+1} / {total_parts} (Length: {len(full_text)})")
        
        # Kirim laporan sebagai pesan baru (Lebih stabil dari edit)
        try:
            await log_bot.send_message(dest_chat, full_text, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
            Altruix.log(f"[OwnershipManager] Berhasil mengirim Part {p+1}/{total_parts}")
        except Exception as e:
            Altruix.log(f"[OwnershipManager] Gagal kirim laporan Part {p+1}: {e}", level=30)
            # Fallback pengiriman: Hapus formatting jika tetap gagal
            try:
                plain = full_text.replace("<b>","").replace("</b>","").replace("<code>","").replace("</code>","").replace("<a href='","").replace("'>"," ").replace("</a>","")
                await log_bot.send_message(dest_chat, f"⚠️ [Format Fallback]\n{plain}")
                Altruix.log(f"[OwnershipManager] Fallback pengiriman Part {p+1} sukses.")
            except Exception as ef: 
                Altruix.log(f"[OwnershipManager] Terminal error pada Part {p+1}: {ef}")
                pass
                
        # Pacing: Jeda 3 detik untuk pesan berikutnya demi menghindari FloodWait
        if p < total_parts - 1:
            await asyncio.sleep(3)
            
    # Feedback sukses di chat asal
    await init_msg.edit(f"✅ <b>Ownership Scan Selesai!</b>\nLaporan terkirim ke Log Group: <code>{len(assets)}</code> aset ({duration:.2f}s).", parse_mode=enums.ParseMode.HTML)
    Altruix.log(f"[OwnershipManager] Task {flags['task_id']} fully completed and reported.")
    
    if m.id != init_msg.id:
        await m.delete_if_self()

# --------------------------------------------------------------------------------
# COMMAND: .myownexport
# --------------------------------------------------------------------------------

@Altruix.register_on_cmd(
    ["myownexport", "moe"],
    cmd_help={
        "help": "Ekspor data kepemilikan aset ke file JSON/CSV.",
        "usage": ".myownexport [-csv]",
        "example": ".myownexport -csv",
        "detail": "Default format adalah JSON. Gunakan -csv untuk format file tabel."
    },
)
@iuser_check
@log_errors
async def my_own_export_cmd(client: Client, m: Message):
    """
    [COMMAND]: .myownexport
    Mengonversi daftar aset milik user menjadi format file untuk backup.
    """
    is_csv = "-csv" in m.text
    ext = "csv" if is_csv else "json"
    
    Altruix.log(f"[OwnershipManager] Starting export task (Format: {ext})")
    init_msg = await m.handle_message("🚀 <b>Gathering data for export...</b>")
    
    # 🛫 Langkah 1: Ambil data terbaru lewat scan
    assets, duration = await perform_ownership_scan(client, init_msg, {"task_id": "EXPORT"})
    
    if assets is None: return
    if not assets:
        Altruix.log(f"[OwnershipManager] Export failed: No assets found.")
        return await init_msg.edit("❌ <b>Tidak ditemukan aset untuk ekspor.</b>", parse_mode=enums.ParseMode.HTML)

    # 🛫 Langkah 2: Pengolahan File
    filename = f"ownership_export_{client.me.id}_{int(time.time())}.{ext}"
    filepath = os.path.join("cache", filename)
    os.makedirs("cache", exist_ok=True)
    
    Altruix.log(f"[OwnershipManager] Writing data to {filepath}...")
    
    try:
        # Menulis data ke file berdasarkan format yang diminta
        if is_csv:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["id", "title", "username", "type", "members"])
                writer.writeheader()
                for a in assets:
                    # Pastikan tipe enum dikonversi jadi teks (String)
                    ac = a.copy(); ac["type"] = str(a["type"])
                    writer.writerow(ac)
        else:
            with open(filepath, "w", encoding="utf-8") as f:
                # Serialisasi JSON dengan konversi Enum
                json.dump([{**a, "type": str(a["type"])} for a in assets], f, indent=4)
        
        # 🛫 Langkah 3: Pengiriman File
        caption = (
            f"📦 <b>Ownership Export</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Session:</b> <code>{client.me.id}</code>\n"
            f"📊 <b>Jumlah:</b> <code>{len(assets)}</code> aset\n"
            f"⏱ <b>Took:</b> <code>{duration:.2f}s</code>"
        )
        
        await client.send_document("me", filepath, caption=caption, file_name=filename, parse_mode=enums.ParseMode.HTML)
        Altruix.log(f"[OwnershipManager] File sent to Saved Messages.")
        
        await init_msg.edit(f"✅ <b>Ekspor Berhasil!</b>\nFile telah dikirim ke Saved Messages Anda.\nTotal: <code>{len(assets)}</code>", parse_mode=enums.ParseMode.HTML)
        
        # Bersihkan cache setelah dikirim
        if m.id != init_msg.id: await m.delete_if_self()
        if os.path.exists(filepath): os.remove(filepath)
        Altruix.log(f"[OwnershipManager] Cache file {filename} cleaned up.")
            
    except Exception as e:
        Altruix.log(f"[OwnershipManager] Export File Error: {e}", level=30)
        await init_msg.edit(f"❌ <b>Gagal membuat file ekspor:</b> <code>{e}</code>", parse_mode=enums.ParseMode.HTML)
