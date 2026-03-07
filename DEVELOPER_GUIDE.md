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

AltruixX uses a strict role-based prefix isolation:
- **Owners (Self/Outgoing):** Only respond to the User Prefix (`CMD_HANDLER`). Sudo prefixes are ignored to prevent dual responses.
- **Sudo Users:** Only respond to the Sudo Prefix (`SUDO_CMD_HANDLER`). User prefixes are ignored.

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
