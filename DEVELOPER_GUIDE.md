# Altruix Developer Guide: Penggunaan Client

Dokumentasi ini menjelaskan cara menggunakan berbagai client (Userbot & Bot Assistant) dalam framework Altruix, termasuk cara import dan pemilihan index client.

## 1. Import Altruix Core

Untuk mengakses client, Anda harus mengimpor instance global `Altruix` dari core client.

```python
from Main.core.client import Altruix
```

## 2. Bot Assistant (Main Bot)
`Altruix.bot` adalah instance utama dari bot assistant (bot token dari `.env`). Ini digunakan untuk fitur-fitur seperti logger, pemberitahuan, dan perintah control bot.


## Handling Prefixes

AltruixX uses a modular prefix system to separate authorization levels and prevent command collisions.

### 1. Global Prefixes
The default prefixes are defined in your `.env` file or database:
- **`PREFIX_OWNER_USER`** (Alias: `CMD_HANDLER`): Used by the account owner. Default is `.`.
- **`PREFIX_SUDO_USERS`** (Alias: `SUDO_CMD_HANDLER`): Used by authorized sudo users. Default is `!`.

### 2. Role-Based Isolation
The system enforces strict isolation to prevent dual responses:
- **Owners (Self/Outgoing):** Only respond to `PREFIX_OWNER_USER`. Sudo prefixes are ignored.
- **Sudo Users:** Only respond to `PREFIX_SUDO_USERS`. User prefixes are ignored.

### 3. Per-Session Overrides (Addons/Multiple Accounts)
If you are running multiple userbot sessions, you can define unique prefixes for each session using suffixes:
- `PREFIX_OWNER_USER_1`, `PREFIX_OWNER_USER_2`, etc.
- `PREFIX_SUDO_USERS_1`, `PREFIX_SUDO_USERS_2`, etc.

This is particularly useful for "Addons" or specialized sessions that need to avoid triggering commands on other accounts active in the same chat.

### 4. Ultroid Addon Prefixes
For plugins ported from the Ultroid ecosystem, separate prefixes are used to prevent collisions with core Altruix commands:
- **`ULTROID_PREFIX_OWNER`**: Default is `,` (Comma).
- **`ULTROID_PREFIX_SUDO`**: Default is `?` (Question Mark).

Like core prefixes, these also support per-session overrides:
- `ULTROID_PREFIX_OWNER_1`, `ULTROID_PREFIX_OWNER_2`, etc.
- `ULTROID_PREFIX_SUDO_1`, `ULTROID_PREFIX_SUDO_2`, etc.

## Multi-Session De-duplication

To prevent multiple active sessions from responding to the same command:
- **Self-Messages:** For incoming messages from `me` (sent from other devices), only the first active session (`clients[0]`) responds.
- **Sudo Commands:** Only the first active session that is authorized for the sender will execute the command.
- **Generic Handlers:** De-duplication logic is applied in decorators to ensure loggers and other non-command handlers don't trigger multiple times across sessions.

```python
# Mengirim pesan menggunakan Bot Assistant
await Altruix.bot.send_message(chat_id=12345678, text="Halo dari Bot Assistant!")
```

## 3. Userbot Client (Multiple Sessions)

`Altruix.clients` adalah sebuah **List** yang berisi semua session userbot yang aktif. Anda bisa mengaksesnya berdasarkan index.

### Mengakses Client Utama (Index 0)
```python
# Mengirim pesan dengan userbot pertama (index ke-0)
client = Altruix.clients[0]
await client.send_message(chat_id=12345678, text="Halo dari Userbot Utama!")
```

### Mengakses Client Berdasarkan Index
Jika Anda memiliki lebih dari satu session, Anda bisa menggunakan index yang sesuai:
```python
# Mengirim pesan dengan userbot kedua (index ke-1)
if len(Altruix.clients) > 1:
    client_2 = Altruix.clients[1]
    await client_2.send_message(chat_id=12345678, text="Halo dari Userbot Kedua!")
```

## 4. Deteksi Index Client Secara Otomatis

Seringkali Anda menerima object `client` dalam sebuah handler dan ingin tahu ini adalah session ke-berapa (index berapa).

### Menggunakan `.index()`
Cara tercepat untuk mendapatkan index dari object `client` yang sedang aktif:
```python
@Altruix.on_message(filters.command("myindex", prefixes="."))
async def index_handler(client, message):
    # Mendapatkan index (0-based)
    idx = Altruix.clients.index(client)
    
    # Biasanya untuk tampilan ke user ditambahkan +1 agar mulai dari 1
    await message.reply(f"Saya adalah Userbot session ke-{idx + 1}")
```

### Mencari Client Berdasarkan User ID
Jika Anda hanya memiliki `user_id` dan ingin mencari client mana yang memilikinya:
```python
def get_client_by_id(user_id):
    for c in Altruix.clients:
        if c.me.id == user_id:
            return c
    return None

# Contoh penggunaan
target_client = get_client_by_id(987654321)
if target_client:
    await target_client.send_message("me", "Ditemukan!")
```

## 5. Bot Manager & Custom Bot

Altruix mendukung **Custom Bot** per-session. Jika sebuah session userbot memiliki custom bot sendiri, Anda dapat mengambilnya melalui `BotManager`. Jika tidak ada custom bot, sistem akan otomatis mengembalikan `Altruix.bot` sebagai fallback.

```python
# Mengambil bot assistant yang sesuai untuk session tertentu
# user_id adalah ID dari session userbot yang sedang berjalan
user_id = client.me.id
bot = Altruix.bot_manager.get_bot(user_id)

await bot.send_message(chat_id=12345678, text="Halo dari Bot (Default atau Custom)!")
```

## 5. Contoh Implementasi dalam Plugin

Berikut adalah contoh bagaimana biasanya client digunakan dalam sebuah plugin:

```python
from Main.core.client import Altruix
from pyrogram import filters

@Altruix.on_message(filters.command("hello", prefixes="."))
async def hello_handler(client, message):
    # client di sini adalah instance session yang menerima pesan (Userbot)
    
    # Membalas pesan menggunakan Userbot
    await message.reply("Halo dari Userbot!")
    
    # Mengirim log ke owner menggunakan Bot Assistant
    await Altruix.bot.send_message(
        Altruix.config.OWNER_ID, 
        f"User {message.from_user.id} menjalankan perintah hello"
    )
    
    # Mengambil bot yang tepat untuk session ini (siapa tahu pakai Custom Bot)
    bot = Altruix.bot_manager.get_bot(client.me.id)
    await bot.send_message(message.chat.id, "Halo juga dari Bot Assistant!")
```

## 6. Menggunakan Client yang Sedang Aktif

Cara termudah dan paling umum untuk mengirim pesan adalah menggunakan object `client` yang secara otomatis diberikan oleh decorator handler Altruix. Object ini mewakili session userbot yang **sedang menerima/memproses** pesan tersebut.

### Di Dalam Handler
Anda tidak perlu mencari index jika berada di dalam fungsi handler, cukup gunakan argumen `client`:

```python
@Altruix.on_message(filters.command("ping", prefixes="."))
async def ping_handler(client, message):
    # 'client' di sini adalah session yang sedang aktif digunakan
    # Anda bisa langsung menggunakan metode Pyrogram seperti send_message, edit_message, dll.
    await client.send_message(message.chat.id, "Pong!")
    
    # Atau lebih mudah lagi, gunakan object 'message' yang sudah terikat ke client tersebut
    await message.reply("Pong dari session yang aktif!")
```

### Keuntungan Argumen `client`:
1. **Otomatis:** Altruix memastikan session yang benar yang menjalankan fungsi tersebut.
2. **Dynamic:** Tidak peduli session ini ada di index 0, 1, atau 10, kode Anda akan tetap bekerja.
3. **Scope:** Menjamin balasan dikirim dari akun yang sama dengan akun yang menerima perintah.

## 7. Referensi Ekosistem (Delay, Hapus, & Markdown)

### Delay dan Jeda Waktu
**Penting:** Selalu gunakan `asyncio.sleep` (bukan `time.sleep`) agar tidak memblokir event loop.
```python
import asyncio

# Contoh delay 3 detik
await message.reply("Memproses...")
await asyncio.sleep(3)
await message.reply("Selesai!")
```

### Menghapus Pesan
Gunakan metode object jika tersedia, atau panggil fungsi client.
```python
# Hapus pesan 
try:
    await message.delete()
except Exception: 
    pass

# Hapus banyak pesan sekaligus
await client.delete_messages(
    chat_id=message.chat.id,
    message_ids=[msg1.id, msg2.id]
)
```

### Format Text (HTML vs Markdown)
Altruix sangat menyarankan penggunaan **HTML** ketimbang MarkdownV2 karena lebih minim error *escape character*.

```python
# Format HTML (Disarankan)
text = (
    "<b>Tebal</b>\n"
    "<i>Miring</i>\n"
    "<code>Monospace</code>\n"
    "<a href='t.me/AltruiX_Chat'>Link</a>"
)
await message.reply(text, parse_mode=enums.ParseMode.HTML)

# Format Markdown V2 (Harus escape karakter spesial)
text_md = "*Tebal* _Miring_ ||Spoiler||"
await message.reply(text_md, parse_mode=enums.ParseMode.MARKDOWN)
```

## 8. Mengirim Pesan Inline (Tombol)

**Hanya Bot Assistant** yang diizinkan oleh Telegram untuk mengirim *Inline Keyboard*. Userbot biasa tidak bisa mengirim tombol.

### Contoh Tombol Biasa (Via Bot Async)
```python
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

kb = InlineKeyboardMarkup([
    [InlineKeyboardButton("Pilihan 1", callback_data="cb_1")],
    [InlineKeyboardButton("Link", url="t.me/AltruiX_Chat")]
])

await Altruix.bot.send_message(
    chat_id=message.chat.id,
    text="Silakan klik:",
    reply_markup=kb
)
```

### Contoh Builder Inline (Tag `via @bot`)
Untuk membuat userbot merender pesan dengan tombol seolah-olah mengetik `@bot_username`, gunakan metode pengiriman hasil sebaris (*Inline Bot Results*).

```python
# 1. Dapatkan username dari bot asisten
bot_usr = Altruix.bot_manager.get_bot_username(client.me.id)

# 2. Panggil data inline milik bot (Pastikan bot punya @on_inline_query handler)
query_str = f"my_menu_{client.me.id}"
res = await client.get_inline_bot_results(bot_usr, query_str)

# 3. Minta userbot untuk 'memilih' hasil pertama dan mengirimnya
if res.results:
    await client.send_inline_bot_result(
        chat_id=message.chat.id,
        query_id=res.query_id,
        result_id=res.results[0].id,
        reply_to_message_id=message.id
    )
```

## Ringkasan Cepat

| Kebutuhan | Kode |
|-----------|------|
| **Main Bot Assistant** | `Altruix.bot` |
| **Daftar Semua Userbot** | `Altruix.clients` |
| **Userbot Utama (Session 1)** | `Altruix.clients[0]` |
| **Userbot Session ke-N** | `Altruix.clients[n-1]` |
| **Bot Assistant (Support Custom)** | `Altruix.bot_manager.get_bot(user_id)` |
| **Info Bot Assistant** | `Altruix.bot_info` |
| **ID Owner** | `Altruix.config.OWNER_ID` |

## 9. Alliance Voice Chat Management

AltruixX mendukung pengelolaan Voice Chat secara programmatic menggunakan `VoiceChatManager`. Anda dapat mengakses instance `PyTgCalls` untuk setiap client untuk melakukan streaming audio atau monitoring partisipan.

### Mengakses VoiceChatManager
Import manager dari module `xalliance_vc`:

```python
from Main.plugins.userbot.xalliance_vc import vc_manager
```

### Melakukan Streaming Audio (Pytgcalls)
Gunakan client yang aktif untuk mendapatkan instance `call` dan memutar audio menggunakan library `pytgcalls`:

```python
from pytgcalls.types import AudioPiped

# Dapatkan instance ptygcalls untuk client ini
call = await vc_manager.get_call(client)

# Join & Play (Master) ke Voice Chat target
await call.join_group_call(
    chat_id="-1001234567890", 
    stream=AudioPiped("downloads/audio.mp3")
)
```

### Mengambil Statistik VC (Raw API)
Gunakan fungsi `get_full_vc_info` untuk melihat status VC secara real-time tanpa harus join:

```python
from Main.plugins.userbot.xalliance_vc import get_full_vc_info

# Mengambil info call (participants_count, call_id, etc)
call_info = await get_full_vc_info(client, "target_chat_username")
if call_info:
    print(f"Total Partisipan: {call_info.participants_count}")
```

### Fitur Lanjutan (Alliance Framework)
- **Multi-Client Sync**: Gunakan `get_active_alliance()` untuk mendapatkan list client yang sedang authorized.
- **Remote Execution**: Gunakan `resolve_target_chat()` untuk konversi username/ID secara otomatis.

## 10. Auto-Delete Command Settings

AltruixX menyediakan fitur penghapusan pesan perintah (command) secara otomatis untuk menjaga kebersihan chat. Fitur ini dihubungkan dengan metode `delete_if_self()`.

### Menggunakan delete_if_self()
Panggil metode ini di akhir handler Anda (terutama untuk perintah yang dijalankan oleh diri sendiri/self):

```python
@Altruix.on_message(filters.command("mycmd", "."))
async def my_handler(client, message):
    await message.reply("Sedang memproses...")
    # ... logika Anda ...
    await message.delete_if_self()
```

### Konfigurasi Database (Toggles)
Sistem ini membaca konfigurasi dari database (MongoDB) dengan prefix `AUTO_DELETE_CMD`.

1. **Global Mode**:
   - `AUTO_DELETE_CMD_GLOBAL`: "on" / "off"
   - `AUTO_DELETE_CMD_DELAY_GLOBAL`: Detik (contoh: "5")

2. **Per-Account Mode**:
   - `AUTO_DELETE_CMD_TYPE_{index}`: "global" atau "per_account"
   - `AUTO_DELETE_CMD_STATUS_{index}`: "on" / "off"
   - `AUTO_DELETE_CMD_DELAY_{index}`: Detik

### Cara Kerja
- Jika `on`, pesan akan dihapus setelah melewati durasi `delay`.
- Hanya pesan yang dikirim oleh `self` (outgoing) yang akan diproses. Pesan dari Sudo Users tidak akan dihapus otomatis oleh metode ini.

## 11. Handler Priority & Groups

Altruix menggunakan sistem **Groups** untuk mengatur urutan eksekusi handler pesan. Semakin kecil angka group, semakin cepat handler tersebut diproses.

### Prioritas Group:

| Group | Nama/Tujuan | Penjelasan |
|-------|-------------|------------|
| **< 0** | **High Priority** | Contoh: `-1`, `-2`. Digunakan untuk **Interactive Input** (seperti fitur "Add Task") atau filter global yang harus berjalan **SESEBELUM** perintah biasa. |
| **1** | **Standard** | Prioritas default untuk semua perintah (`register_on_cmd`). Hampir semua fitur standar berada di sini. |
| **0** | **Default** | Default Pyrogram. Jarang digunakan secara manual kecuali untuk filter sistem. |
| **3+** | **Background** | Contoh: `3`, `10`. Digunakan untuk logger, tracker statistik, atau fitur pasif yang berjalan **SETELAH** perintah utama selesai diproses. |

### Case Study: Interactive Input
Jika Anda membuat fitur yang meminta input user (misal: "Kirim ID Chat"), gunakan `group=-2`.

```python
@Altruix.on_message(filters.private & filters.text, group=-2, allow_commands=True)
async def input_handler(client, message):
    if user_id in WAITING_INPUT:
        # Proses input...
        return # Selesaikan tanpa mengganggu perintah lain
```

**Penting:** Selalu gunakan `allow_commands=True` pada handler prioritas tinggi jika Anda ingin menangkap input yang mungkin diawali karakter prefix (seperti `-` atau `/`). Tanpa ini, core client akan menyaring pesan tersebut sebelum sampai ke handler Anda.

## 10. Button Style Synchronization

AltruixX mendukung sinkronisasi warna tombol (**Button Style**) berdasarkan preferensi tiap akun (Primary, Success, Danger, Default). Anda sangat disarankan menggunakan helper ini pada setiap menu interaktif agar UI tetap konsisten di seluruh ekosistem.

### Cara Penggunaan:

1. **Import Helper**:
```python
from Main.utils.file_helpers import get_user_button_style
```

2. **Dapatkan Style & Terapkan**:
Gunakan `user_id` dari session yang sedang aktif untuk menentukan warna tombol. Masukkan hasil helper ke dalam argumen `style` pada `InlineKeyboardButton`.

```python
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

@Altruix.bot.on_callback_query(filters.regex("my_plugin_menu"))
async def my_handler(c, cb):
    # Ambil user_id dari user yang berinteraksi (atau dari context session)
    user_id = cb.from_user.id
    user_style = get_user_button_style(user_id)

    buttons = [
        [InlineKeyboardButton("✅ Confirm", callback_data="conf", style=user_style)],
        [InlineKeyboardButton("❌ Cancel", callback_data="canc", style=user_style)]
    ]
    
    await cb.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
```

### Keuntungan:
- **Konsistensi UI**: Jika user mengatur style akunnya ke "Success" (Hijau) melalui `/settings`, maka seluruh tombol di plugin Anda akan otomatis berwarna hijau.
- **Premium Look**: Memberikan pengalaman visual yang lebih dinamis dibandingkan tombol default yang statis.

## 12. Debugging Mendalam dengan Handler Prioritas Tinggi

Saat menghadapi masalah di mana pesan atau interaksi seolah-olah "hilang" atau tidak merespon, Anda dapat menggunakan teknik **Diagnostic Catch-All** menggunakan group prioritas yang sangat tinggi (angka negatif besar) untuk melacak alur update di Pyrogram.

### 1. Menggunakan RawUpdateHandler
`RawUpdateHandler` menangkap **semua** jenis update dari Telegram (pesan, status ketik, edit, dll) sebelum diproses oleh filter apa pun. Ini sangat berguna untuk memastikan apakah server bot sebenarnya menerima data tersebut atau tidak.

```python
from pyrogram.handlers import RawUpdateHandler

async def diagnostic_raw_update_handler(c: Client, update, users, chats):
    # Log tipe update yang masuk (misal: UpdateShortMessage, UpdateNewMessage)
    Altruix.log(f"🕵️ [DEBUG-RAW] Received update: {type(update).__name__}", level=20)

# Gunakan group -2 atau lebih rendah agar diproses paling awal
Altruix.bot.add_handler(RawUpdateHandler(diagnostic_raw_update_handler), group=-2)
```

### 2. High-Priority Message Tracker
Gunakan group ekstrim seperti `-100` untuk menangkap pesan sebelum di-intercept oleh plugin lain. Pastikan selalu memanggil `continue_propagation()` agar fitur lain tetap berfungsi.

```python
@Altruix.bot.on_message(group=-100)
async def diagnostic_message_handler(c: Client, m: Message):
    if m.from_user:
        Altruix.log(f"🚨 [DEBUG-MSG] Group -100 saw message from {m.from_user.id}: {m.text[:20]}", level=20)
    
    # SANGAT PENTING: Lanjutkan ke handler berikutnya
    await m.continue_propagation()
```

### 3. Kapan Menggunakan Ini?
- Ketika tombol menu tidak merespon saat diklik.
- Ketika input teks (seperti Token atau Password) dikirim tapi bot diam saja.
- Untuk mendeteksi apakah ada plugin lain yang tidak sengaja melakukan `stop_propagation()` sehingga memutus alur pesan.

---
*Altruix Developer Documentation*