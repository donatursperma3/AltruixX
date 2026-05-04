# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.

import html
from Main import Altruix
from pyrogram import Client, enums, filters
from pyrogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    CallbackQuery, 
    InlineQuery, 
    InlineQueryResultArticle, 
    InputTextMessageContent
)
from Main.core.types.message import Message
from Main.core.decorators import log_errors, iuser_check
from Main.utils.file_helpers import get_user_button_style
from Main.utils.essentials import Essentials


# ==================== EVAL/REVAL DOCUMENTATION (24 PAGES) ====================

EVAL_DOC_PAGES = [
    # Page 1: Import
    """<b>📚 Eval & Reval Guide</b>
<b>Page 1/26: Import Altruix</b>

<b>Import Core:</b>
<pre language="python">from Main.core.client import Altruix</pre>

Ini memberikan akses ke semua client (userbot & bot).

<i>→ .evaldoc 2</i>""",

    # Page 2: Bot Assistant
    """<b>📚 Eval & Reval Guide</b>
<b>Page 2/26: Bot Assistant</b>

<b>Altruix.bot</b> = Bot utama dari .env

<b>Contoh:</b>
<pre language="python"># Kirim pesan via bot
await Altruix.bot.send_message(
    12345678,
    "Halo!"
)</pre>

<i>→ .evaldoc 3</i>""",

    # Page 3: Userbot List
    """<b>📚 Eval & Reval Guide</b>
<b>Page 3/26: Userbot List</b>

<b>Altruix.clients</b> = List semua userbot

<b>Contoh:</b>
<pre language="python"># Userbot pertama
c = Altruix.clients[0]
await c.send_message(
    12345678,
    "Halo!"
)</pre>

<i>→ .evaldoc 4</i>""",

    # Page 4: Multiple Sessions
    """<b>📚 Eval & Reval Guide</b>
<b>Page 4/26: Multiple Sessions</b>

<b>Akses session lain:</b>
<pre language="python"># Session kedua
if len(Altruix.clients) > 1:
    c2 = Altruix.clients[1]
    await c2.send_message(
        12345678,
        "Dari session 2!"
    )</pre>

<i>→ .evaldoc 5</i>""",

    # Page 5: Client Aktif (PENTING!)
    """<b>📚 Eval & Reval Guide</b>
<b>Page 5/26: Client Aktif ⭐</b>

<b>CARA TERMUDAH:</b>
Gunakan <code>client</code> dari handler!

<b>Contoh di eval:</b>
<pre language="python"># 'client' = session aktif
await client.send_message(
    "me",
    "Dari session yang aktif!"
)</pre>

Client otomatis terdeteksi!

<i>→ .evaldoc 6</i>""",

    # Page 6: Contoh Client Aktif Detail
    """<b>📚 Eval & Reval Guide</b>
<b>Page 6/26: Contoh Client Aktif</b>

<b>Dalam eval/reval:</b>
<pre language="python"># Kirim ke diri sendiri
await client.send_message(
    "me", "Test"
)

# Kirim ke chat lain
await client.send_message(
    -1001234567890,
    "Test ke grup"
)

# Info session
me = await client.get_me()
print(f"Nama: {me.first_name}")
print(f"ID: {me.id}")</pre>

<i>→ .evaldoc 7</i>""",

    # Page 7: Get Index
    """<b>📚 Eval & Reval Guide</b>
<b>Page 7/26: Deteksi Index</b>

<b>Cari tahu session ke berapa:</b>
<pre language="python"># Dapatkan index
idx = Altruix.clients.index(client)

# Tampilkan (mulai dari 1)
print(f"Session ke-{idx + 1}")</pre>

<i>→ .evaldoc 8</i>""",

    # Page 8: Find by User ID
    """<b>📚 Eval & Reval Guide</b>
<b>Page 8/26: Cari by User ID</b>

<b>Cari client berdasarkan ID:</b>
<pre language="python">def get_client(uid):
    for c in Altruix.clients:
        if c.me.id == uid:
            return c
    return None

# Gunakan
c = get_client(987654321)
if c:
    await c.send_message(
        "me", "Found!"
    )</pre>

<i>→ .evaldoc 9</i>""",

    # Page 9: Bot Manager
    """<b>📚 Eval & Reval Guide</b>
<b>Page 9/26: Bot Manager</b>

<b>Support Custom Bot:</b>
<pre language="python"># Auto pilih bot
uid = client.me.id
bot = Altruix.bot_manager.get_bot(uid)

await bot.send_message(
    12345678,
    "Dari bot (custom/default)"
)</pre>

<i>→ .evaldoc 10</i>""",

    # Page 10: Plugin Example
    """<b>📚 Eval & Reval Guide</b>
<b>Page 10/26: Plugin Example</b>

<pre language="python">@Altruix.on_message(
    filters.command("test", ".")
)
async def test(client, message):
    # Balas via userbot
    await message.reply("OK!")
    
    # Log via bot
    await Altruix.bot.send_message(
        Altruix.config.OWNER_ID,
        f"User {message.from_user.id}"
    )</pre>

<i>→ .evaldoc 11</i>""",

    # Page 11: Handler Best Practice
    """<b>📚 Eval & Reval Guide</b>
<b>Page 11/26: Best Practice</b>

<b>Dalam handler:</b>
<pre language="python">async def handler(client, message):
    # ✅ BENAR: Gunakan client
    await client.send_message(
        message.chat.id, "OK"
    )
    
    # ✅ ATAU via message
    await message.reply("OK")
    
    # ❌ JANGAN hardcode index
    # await Altruix.clients[0]...</pre>

<i>→ .evaldoc 12</i>""",

    # Page 12: Prefix Handling
    """<b>📚 Eval & Reval Guide</b>
<b>Page 12/26: Prefix Handling</b>

<b>Owner:</b> Hanya respond ke CMD_HANDLER
<b>Sudo:</b> Hanya respond ke SUDO_CMD_HANDLER

Ini mencegah dual response jika owner juga ditambahkan sebagai sudo user.

<i>→ .evaldoc 13</i>""",

    # Page 13: Environment Prefixes
    """<b>📚 Eval & Reval Guide</b>
<b>Page 13/26: Environment Prefixes ⭐</b>

<b>Konfigurasi di .env:</b>
• <code>PREFIX_OWNER_USER=.</code>
• <code>PREFIX_SUDO_USERS=!</code>

<b>Per-Session Prefix:</b>
Jika menggunakan multiple session, Anda bisa mengatur prefix unik per account:
• <code>PREFIX_OWNER_USER_1=.</code>
• <code>PREFIX_OWNER_USER_2=,</code>

Ini guna memisahkan perintah antar account.

<i>→ .evaldoc 14</i>""",

    # Page 14: Addons & Ultroid Prefixes
    """<b>📚 Eval & Reval Guide</b>
<b>Page 14/26: Addons & Ultroid Prefixes ⭐</b>

<b>Khusus Addons (Ported Ultroid):</b>
Beberapa plugin yang di-port dari Ultroid menggunakan prefix berbeda agar tidak bentrok dengan core:
• <b>Owner:</b> <code>ULTROID_PREFIX_OWNER</code> (Default: <code>,</code>)
• <b>Sudo:</b> <code>ULTROID_PREFIX_SUDO</code> (Default: <code>?</code>)

<b>Apply Mode:</b>
Variabel <code>ULTROID_PREFIX_APPLY_TYPE</code> menentukan apakah prefix ini berlaku <b>global</b> atau <b>per_account</b> (per session).

<b>Dashboard:</b>
Atur di <b>Settings > Privacy > Prefix Settings</b> atau langsung via .env untuk isolasi perintah Addons.

<i>→ .evaldoc 15</i>""",

    # Page 15: Handler Groups & Priority
    """<b>📚 Eval & Reval Guide</b>
<b>Page 15/26: Handler Groups & Priority ⭐</b>

<b>Prioritas Group:</b>
• <b>Group &lt; 0</b>: INTERCEPTOR (High Priority)
  Contoh: <code>group=-2</code> untuk interactive input.
• <b>Group 1</b>: COMMAND (Default)
  Digunakan oleh hampir semua plugin.
• <b>Group 3+</b>: BACKGROUND (Low Priority)
  Untuk logger &amp; tracker pasif.

<b>PENTING:</b> Gunakan <code>allow_commands=True</code> jika ingin menangkap input yang diawali prefix (. atau /).

<i>→ .evaldoc 16</i>""",

    # Page 16: De-duplication
    """<b>📚 Eval & Reval Guide</b>
<b>Page 16/26: De-duplication</b>
Hanya satu session yang akan memproses pesan jika multiple session aktif di grup yang sama.
Ini otomatis ditangani oleh <code>xpm_logger_user</code>.

<i>→ .evaldoc 17</i>""",

    # Page 17: Config & LOG_CHAT_ID
    """<b>📚 Eval & Reval Guide</b>
<b>Page 17/26: Config & Log ID</b>

<b>Cara akses config & LOG_CHAT_ID:</b>
<pre language="python">from Main import Altruix

# Akses Config
conf = Altruix.config

# Dapatkan LOG_CHAT_ID
log_id = conf.LOG_CHAT_ID
print(f"Log Chat: {log_id}")</pre>

<b>Akses via ENV (Asynchronous):</b>
<pre language="python">env = await Altruix.db.env_col.find_one(
    {"_id": "ENV"}
)
token = env.get("BOT_TOKEN")</pre>

<i>→ .evaldoc 18</i>""",

    # Page 18: Database Persistence
    """<b>📚 Eval & Reval Guide</b>
<b>Page 18/26: Database Persistence</b>

<b>Simpan data permanen:</b>
<pre language="python">from Main import Altruix

# Gunakan DATA collection
await Altruix.db.data_col.find_one_and_update(
    {"_id": "MY_KEY"},
    {"$set": {"val": 123}},
    upsert=True
)

# Ambil data
res = await Altruix.db.data_col.find_one(
    {"_id": "MY_KEY"}
)
print(res.get("val"))</pre>

<i>→ .evaldoc 19</i>""",

    # Page 19: Additional Examples - Delay & Delete
    """<b>📚 Eval & Reval Guide</b>
<b>Page 19/26: Delay & Hapus Pesan</b>

<b>Delay (Tidur/Jeda):</b>
<pre language="python">import asyncio

await message.reply("Tunggu 3 detik...")
# HARUS pakai asyncio, jangan time.sleep()
await asyncio.sleep(3) 
await message.reply("Selesai!")</pre>

<b>Hapus Pesan:</b>
<pre language="python"># Hapus pesan pengguna
try:
    await message.delete()
except Exception: pass

# Hapus banyak pesan
await client.delete_messages(
    chat_id=message.chat.id,
    message_ids=[msg1.id, msg2.id]
)</pre>

<i>→ .evaldoc 20</i>""",

    # Page 20: Format HTML & Markdown
    """<b>📚 Eval & Reval Guide</b>
<b>Page 20/26: Markdown & HTML</b>

<b>Format Standar Telegram (HTML):</b>
<pre language="python">text = (
    "&lt;b&gt;Tebal&lt;/b&gt;\\n"
    "&lt;i&gt;Miring&lt;/i&gt;\\n"
    "&lt;u&gt;Garis bawah&lt;/u&gt;\\n"
    "&lt;s&gt;Coret&lt;/s&gt;\\n"
    "&lt;code&gt;Monospace&lt;/code&gt;\\n"
    "&lt;pre&gt;Blok Kode&lt;/pre&gt;\\n"
    "&lt;a href='t.me/'&gt;Link&lt;/a&gt;\\n"
    "&lt;tg-spoiler&gt;Rahasia&lt;/tg-spoiler&gt;"
)
await message.reply(text, parse_mode=enums.ParseMode.HTML)</pre>

<b>Markdown V2 (Butuh escape karakter khusus!):</b>
<pre language="python">text = "*Tebal* _Miring_ ~Coret~ ||Rahasia||"
await message.reply(text, parse_mode=enums.ParseMode.MARKDOWN)</pre>

<i>→ .evaldoc 21</i>""",

    # Page 21: Inline Buttons (Bot)
    """<b>📚 Eval & Reval Guide</b>
<b>Page 21/26: Inline Buttons</b>

<b>HANYA Bot Assistant yang bisa kirim tombol:</b>
<pre language="python">from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton
)

# Buat Layout Tombol
kb = InlineKeyboardMarkup([
    [InlineKeyboardButton("Pilihan 1", callback_data="cb_1")],
    [InlineKeyboardButton("Link", url="t.me/")]
])

# Kirim menggunakan bot
await Altruix.bot.send_message(
    chat_id=message.chat.id,
    text="Silakan klik:",
    reply_markup=kb
)</pre>

<i>→ .evaldoc 22</i>""",

    # Page 22: Inline Builder (Tag via@bot)
    """<b>📚 Eval & Reval Guide</b>
<b>Page 22/26: Mengirim Pesan (via@bot)</b>

<b>Fitur Builder (Ekosistem Altruix):</b>
<pre language="python"># 1. Dapatkan nama bot kamu
bot_usr = Altruix.bot_manager.get_bot_username(client.me.id)

# 2. Panggil Inline Query dari bot kamu
# (Harus ada handler @bot.on_inline_query di pluginnya)
query_str = f"my_menu_{client.me.id}"
res = await client.get_inline_bot_results(bot_usr, query_str)

# 3. Userbot "menekan" hasil inline & kirim ke chat
if res.results:
    await client.send_inline_bot_result(
        chat_id=message.chat.id,
        query_id=res.query_id,
        result_id=res.results[0].id,
        reply_to_message_id=message.id
    )</pre>

<i>→ .evaldoc 23</i>""",

    # Page 23: Quick Reference
    """<b>📚 Eval & Reval Guide</b>
<b>Page 23/26: Quick Reference</b>

<code>Altruix.bot</code>
→ Bot utama

<code>Altruix.clients</code>
→ List userbot

<code>Altruix.clients[0]</code>
→ Userbot pertama

<code>client</code> (dalam handler)
→ Session aktif ⭐

<code>Altruix.bot_manager.get_bot(uid)</code>
→ Bot (custom/default)

<i>→ .evaldoc 24</i>""",

    # Page 24: Tips
    """<b>📚 Eval & Reval Guide</b>
<b>Page 24/26: Tips Eval/Reval</b>

<b>💡 Tips:</b>

1. Gunakan <code>client</code> dari handler
   (auto-detect session aktif)

2. Untuk userbot utama:
   <code>Altruix.clients[0]</code>

3. Untuk bot assistant:
   <code>Altruix.bot</code>

4. Check jumlah session:
   <code>len(Altruix.clients)</code>

5. Info session aktif:
   <code>await client.get_me()</code>

<i>→ .evaldoc 25</i>""",

    # Page 25: Alliance Voice Chat API
    """<b>📚 Eval & Reval Guide</b>
<b>Page 25/26: Alliance Voice Chat API ⭐</b>

<b>VoiceChatManager:</b>
<pre language="python">from Main.plugins.userbot.xalliance_vc import vc_manager

# Mendapatkan instance pytgcalls
call = await vc_manager.get_call(client)

# Join & Play Audio
from pytgcalls.types import AudioPiped
await call.join_group_call(
    "chat_username", 
    AudioPiped("audio.mp3")
)</pre>

Mendukung Automasi & Eval!

<i>→ .evaldoc 26</i>""",

    # Page 26: Configuration Priority ⭐
    """<b>📚 Eval & Reval Guide</b>
<b>Page 26/28: Konfigurasi & Prioritas ⭐</b>

<b>Prioritas Sistem Config:</b>
1. <b>Cache</b> (Memory - Paling cepat)
2. <b>Database</b> (MongoDB - Dinamis)
3. <b>.env File</b> (Lokal - Fallback)

<b>PENTING:</b> Variable di Database akan <b>MENGUBAH / OVERWRITE</b> nilai di .env. Jika Anda mengubah <code>BOT_TOKEN</code> di .env tapi tidak berubah, itu karena nilai lama masih ada di Database!

<i>→ .evaldoc 27</i>""",

    # Page 27: Syncing .env to Database
    """<b>📚 Eval & Reval Guide</b>
<b>Page 27/28: Sinkronisasi .env 🛠️</b>

<b>Gunakan command .syncenv:</b>
Untuk memaksa Database menggunakan nilai terbaru dari file <code>.env</code> Anda.

<b>Command:</b>
• <code>.syncenv</code> : Cek perbedaan.
• <code>.syncenv all</code> : Sinkronkan SEMUA ke DB.
• <code>.syncenv BOT_TOKEN</code> : Sinkronkan key tertentu.

<i>→ Gunakan ini jika BOT_TOKEN di .env tidak update!</i>

<i>→ .evaldoc 28</i>""",

    # Page 28: Penutup
    """<b>📚 Eval & Reval Guide</b>
<b>Page 28/28: Penutup</b>

Semua dokumentasi ini tersedia juga di file <code>DEVELOPER_GUIDE.md</code> di repo utama.

Gunakan standar ekosistem Altruix untuk memastikan module Anda bebas bug dan aman diletakkan dalam Loop asyncio!

<b>Selesai!</b> Gunakan <code>.evaldoc 1</code> untuk kembali ke awal."""
]


async def get_evaldoc_keyboard(page: int, user_id: int) -> InlineKeyboardMarkup:
    """Generate inline keyboard for evaldoc pagination."""
    total_pages = len(EVAL_DOC_PAGES)
    btn_style = get_user_button_style(user_id)
    
    # Row 1: Prev | Page X/Total | Next
    row1 = []
    if page > 1:
        row1.append(InlineKeyboardButton(await Essentials.get_user_button_style(user_id, "«"), callback_data=f"evaldoc_page_{page-1}", style=btn_style))
    else:
        row1.append(InlineKeyboardButton(await Essentials.get_user_button_style(user_id, "«"), callback_data="evaldoc_noop", style=btn_style))
    
    row1.append(InlineKeyboardButton(await Essentials.get_user_button_style(user_id, f"{page}/{total_pages}"), callback_data="evaldoc_noop", style=btn_style))
    
    if page < total_pages:
        row1.append(InlineKeyboardButton(await Essentials.get_user_button_style(user_id, "»"), callback_data=f"evaldoc_page_{page+1}", style=btn_style))
    else:
        row1.append(InlineKeyboardButton(await Essentials.get_user_button_style(user_id, "»"), callback_data="evaldoc_noop", style=btn_style))
    
    # Row 2: First | Client (jump to page 5) | Last
    row2 = [
        InlineKeyboardButton(await Essentials.get_user_button_style(user_id, "First"), callback_data="evaldoc_page_1", style=btn_style),
        InlineKeyboardButton(await Essentials.get_user_button_style(user_id, "⭐ Client"), callback_data="evaldoc_page_5", style=btn_style),
        InlineKeyboardButton(await Essentials.get_user_button_style(user_id, "Last"), callback_data=f"evaldoc_page_{total_pages}", style=btn_style)
    ]
    
    # Row 3: Close
    row3 = [InlineKeyboardButton(await Essentials.get_user_button_style(user_id, "Close"), callback_data="evaldoc_close", style=btn_style)]
    
    return InlineKeyboardMarkup([row1, row2, row3])


# ==================== HELPER FUNCTIONS FOR SAFE CALLBACK HANDLING ====================

async def safe_evaldoc_answer(cb: CallbackQuery, text: str, show_alert: bool = False):
    """Answer callback query safely, ignoring expired queries."""
    try:
        await cb.answer(text, show_alert=show_alert)
    except Exception:
        pass

async def safe_evaldoc_edit(cb: CallbackQuery, text: str, reply_markup=None):
    """
    Safely edit callback message, handling both regular and inline mode messages.
    Uses cb.edit_message_text() which automatically handles inline messages.
    """
    try:
        # Use cb.edit_message_text() - it automatically handles both regular and inline messages
        await cb.edit_message_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
        return True
    except Exception as e:
        Altruix.log(f"[evaldoc] Error editing message: {e}", level=40)
        await safe_evaldoc_answer(cb, f"❌ Error: {str(e)[:50]}", show_alert=True)
        return False

async def safe_evaldoc_delete(cb: CallbackQuery):
    """
    Safely delete callback message.
    For inline messages, uses delete_message() instead of message.delete().
    """
    try:
        # Try to delete using callback query method (works for both inline and regular)
        await cb.message.delete()
        return True
    except AttributeError:
        # If cb.message is None (inline mode), try alternative method
        try:
            # For inline messages, we can't delete, so we edit to show "closed" message
            await cb.edit_message_text(
                "❌ <b>Menu Closed</b>",
                parse_mode=enums.ParseMode.HTML
            )
            return True
        except Exception as e:
            Altruix.log(f"[evaldoc] Error closing message: {e}", level=40)
            return False
    except Exception as e:
        Altruix.log(f"[evaldoc] Error deleting message: {e}", level=40)
        return False


# ==================== CALLBACK HANDLER ====================

@Altruix.bot.on_callback_query(filters.regex(r"^evaldoc_"))
@iuser_check
@log_errors
async def evaldoc_callback_handler(c: Client, q: CallbackQuery):
    """Handle evaldoc inline keyboard callbacks.
    Protected by @iuser_check for auth verification."""
    data = q.data
    
    # Handle close button
    if data == "evaldoc_close":
        success = await safe_evaldoc_delete(q)
        if success:
            await safe_evaldoc_answer(q, "Menu closed.", show_alert=False)
        return
    
    # Handle noop (disabled buttons)
    if data == "evaldoc_noop":
        await safe_evaldoc_answer(q, "⚠️ Already at boundary", show_alert=False)
        return
    
    # Handle page navigation
    if data.startswith("evaldoc_page_"):
        try:
            page_num = int(data.split("_")[-1])
        except ValueError:
            await safe_evaldoc_answer(q, "❌ Invalid page", show_alert=True)
            return
        
        # Validate page number
        if page_num < 1 or page_num > len(EVAL_DOC_PAGES):
            await safe_evaldoc_answer(q, f"❌ Page must be 1-{len(EVAL_DOC_PAGES)}", show_alert=True)
            return
        
        # Get page content and keyboard
        page_content = EVAL_DOC_PAGES[page_num - 1]
        keyboard = await get_evaldoc_keyboard(page_num, q.from_user.id)
        
        # Update message
        success = await safe_evaldoc_edit(q, page_content, reply_markup=keyboard)
        if success:
            await safe_evaldoc_answer(q, f"📄 Page {page_num}/{len(EVAL_DOC_PAGES)}", show_alert=False)


# ==================== INLINE HANDLER (for dashboard mode via @bot) ====================

@Altruix.bot.on_inline_query(filters.regex(r"^evaldoc(?:_page_)?(\d+)?"))
@iuser_check
@log_errors
async def evaldoc_inline_handler(client: Client, query: InlineQuery):
    """
    Responds to inline query for evaldoc (triggered by @bot evaldoc).
    Allows opening the evaldoc dashboard in ANY chat via inline mode.
    Protected by @iuser_check for auth verification.
    """
    try:
        # Extract page number from query
        match = query.matches[0]
        page_str = match.group(1)
        page_num = int(page_str) if page_str else 1
        
        # Validate page number
        if page_num < 1 or page_num > len(EVAL_DOC_PAGES):
            page_num = 1
        
        # Get page content and keyboard
        page_content = EVAL_DOC_PAGES[page_num - 1]
        keyboard = await get_evaldoc_keyboard(page_num, query.from_user.id)
        
        await query.answer(
            results=[
                InlineQueryResultArticle(
                    title=f"📚 Eval & Reval Guide - Page {page_num}/{len(EVAL_DOC_PAGES)}",
                    description=f"Comprehensive documentation for eval/reval usage",
                    input_message_content=InputTextMessageContent(
                        page_content,
                        parse_mode=enums.ParseMode.HTML,
                        disable_web_page_preview=True
                    ),
                    reply_markup=keyboard
                )
            ],
            cache_time=0
        )
    except Exception as e:
        Altruix.log(f"Evaldoc Inline Handler Error: {e}", level=40)


# Update the eval_documentation_handler to support inline mode
@Altruix.register_on_cmd(
    ["evaldoc", "evalhelp", "evalguide"],
    cmd_help={
        "help": "Show comprehensive documentation for eval/reval usage with client access.",
        "example": "evaldoc 1",
        "user_input": {
            "required": False,
            "placeholder": f"page number (1-{len(EVAL_DOC_PAGES)})"
        }
    },
)
@log_errors
async def eval_documentation_handler_inline(c: Client, m: Message):
    """Show eval/reval documentation with inline keyboard pagination via bot assistant."""
    # Get page number from user input
    page_input = m.user_input.strip() if m.user_input else "1"
    
    try:
        page_num = int(page_input)
    except ValueError:
        return await m.reply_msg(
            "❌ <b>Invalid page number.</b>\n\n"
            f"Usage: <code>.evaldoc [1-{len(EVAL_DOC_PAGES)}]</code>\n"
            f"Example: <code>.evaldoc 1</code>"
        )
    
    # Validate page number
    if page_num < 1 or page_num > len(EVAL_DOC_PAGES):
        return await m.reply_msg(
            f"❌ <b>Page not found.</b>\n\n"
            f"Available pages: <b>1-{len(EVAL_DOC_PAGES)}</b>\n"
            f"Usage: <code>.evaldoc [page]</code>"
        )
    
    user_id = c.me.id
    
    # Get bot assistant
    bot = None
    bot_username = None
    if hasattr(Altruix, 'bot_manager'):
        bot = Altruix.bot_manager.get_bot(user_id)
        bot_username = Altruix.bot_manager.get_bot_username(user_id)
    if not bot:
        bot = Altruix.bot
        if hasattr(Altruix.bot, 'me') and Altruix.bot.me:
            bot_username = Altruix.bot.me.username
    
    if not bot:
        # No bot assistant found - fallback to direct message
        page_content = EVAL_DOC_PAGES[page_num - 1]
        keyboard = await get_evaldoc_keyboard(page_num, m.from_user.id) # Pass user_id
        await m.edit_msg(page_content, reply_markup=keyboard)
        return
    
    # Try Inline mode first (works in ANY chat, even without bot present)
    if bot_username:
        try:
            results = await c.get_inline_bot_results(bot_username, f"evaldoc_page_{page_num}")
            if results.results:
                sent = await c.send_inline_bot_result(
                    m.chat.id,
                    results.query_id,
                    results.results[0].id,
                    reply_to_message_id=m.id  # ✅ Reply to command message
                )
                if sent:
                    await m.delete_if_self()
                    Altruix.log(f"[evaldoc] Dashboard opened via inline mode (page {page_num})", level=20)
                    return
        except Exception as e:
            Altruix.log(f"[evaldoc] Inline mode failed: {e}, falling back to direct message", level=30)
    
    # Fallback to direct bot message (only works if bot is in the chat)
    try:
        page_content = EVAL_DOC_PAGES[page_num - 1]
        keyboard = await get_evaldoc_keyboard(page_num, m.from_user.id)
        await bot.send_message(
            m.chat.id, 
            page_content, 
            reply_markup=keyboard, 
            parse_mode=enums.ParseMode.HTML,
            reply_to_message_id=m.id  # ✅ Reply to command message
        )
        await m.delete_if_self()
        Altruix.log(f"[evaldoc] Dashboard opened via direct message (page {page_num})", level=20)
    except Exception as e:
        Altruix.log(f"[evaldoc] Error sending dashboard: {e}", level=40)
        # Final fallback - edit original message
        page_content = EVAL_DOC_PAGES[page_num - 1]
        keyboard = await get_evaldoc_keyboard(page_num, m.from_user.id)
        await m.edit_msg(page_content, reply_markup=keyboard)
