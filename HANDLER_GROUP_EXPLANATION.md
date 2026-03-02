# Handler Group Priority Explanation

## Apa itu `group` Parameter?

Parameter `group` dalam `@Altruix.on_message()` menentukan **prioritas eksekusi handler**.

### Cara Kerja

```python
@Altruix.on_message(filters.mentioned, group=1)  # Prioritas tinggi
async def handler_a():
    pass

@Altruix.on_message(filters.mentioned, group=3)  # Prioritas rendah
async def handler_b():
    pass
```

**Urutan eksekusi:**
1. Handler dengan `group=1` dijalankan **PERTAMA**
2. Handler dengan `group=3` dijalankan **SETELAHNYA**

### StopPropagation

Jika handler dengan prioritas lebih tinggi menggunakan `raise StopPropagation`, maka handler dengan prioritas lebih rendah **TIDAK AKAN DIJALANKAN**.

```python
@Altruix.on_message(filters.mentioned, group=1)
async def handler_a():
    # Do something
    raise StopPropagation  # STOP! Handler lain tidak dijalankan

@Altruix.on_message(filters.mentioned, group=3)
async def handler_b():
    # TIDAK AKAN PERNAH DIJALANKAN jika handler_a raise StopPropagation
    pass
```

---

## Masalah di Hater Detector

### Sebelum Fix

```python
# Mention Logger (xmention_logger_user.py)
@Altruix.on_message(filters.mentioned & filters.group)  # group=1 (default)
async def send_mention_log_handler():
    # Process mention
    # Tidak ada StopPropagation
    pass

# Hater Detector (xdetect_haters.py)
@Altruix.on_message(filters.mentioned & filters.group, group=3)  # group=3
async def hater_detector():
    # BISA DIJALANKAN karena mention logger tidak StopPropagation
    pass
```

**Masalah potensial:**
- Jika ada plugin lain dengan `group=1` atau `group=2` yang menggunakan `StopPropagation`
- Hater detector dengan `group=3` tidak akan pernah terpicu

### Setelah Fix

```python
# Mention Logger (xmention_logger_user.py)
@Altruix.on_message(filters.mentioned & filters.group)  # group=1 (default)
async def send_mention_log_handler():
    pass

# Hater Detector (xdetect_haters.py)
@Altruix.on_message(filters.mentioned & filters.group, group=4)  # group=4
async def hater_detector():
    # Dijalankan SETELAH mention logger
    # Lebih aman dari interference plugin lain
    pass
```

**Keuntungan:**
- Hater detector dijalankan setelah mention logger
- Tidak bentrok dengan plugin lain yang mungkin ada di group=1-3
- Lebih predictable execution order

---

## Group Priority Best Practices

### Recommended Group Numbers

```
group=0  - Critical handlers (command logger, security)
group=1  - Core functionality (mention logger, PM logger)
group=2  - Secondary features
group=3  - Tertiary features
group=4+ - Optional features (hater detector, analytics)
```

### Checking Existing Handlers

Untuk melihat handler apa saja yang ada di group tertentu:

```bash
# Search for handlers with specific group
grep -r "group=1" Main/plugins/
grep -r "group=2" Main/plugins/
grep -r "group=3" Main/plugins/
```

---

## Filters Verification

### filters.mentioned

**Apa yang ditangkap:**
- Message yang mention userbot dengan `@username`
- Message yang mention userbot dengan text mention

**Contoh:**
```
@userbotname hello     ✅ Ditangkap
Hey @userbotname       ✅ Ditangkap
Hello world            ❌ Tidak ditangkap
```

### filters.reply

**Apa yang ditangkap:**
- Message yang reply ke message lain

**Contoh:**
```
User A: Hello
User B: Hi (reply to User A)  ✅ Ditangkap

User A: Hello
User B: Hi (not reply)        ❌ Tidak ditangkap
```

### filters.group

**Apa yang ditangkap:**
- Message di group chat (GROUP, SUPERGROUP)

**Tidak ditangkap:**
- Message di private chat
- Message di channel

### ~filters.bot

**Apa yang ditangkap:**
- Message dari user biasa

**Tidak ditangkap:**
- Message dari bot account

### ~filters.service

**Apa yang ditangkap:**
- Message biasa (text, media, etc)

**Tidak ditangkap:**
- Service message (user joined, user left, etc)

---

## Combined Filters

```python
filters.mentioned & filters.group & ~filters.bot & ~filters.service
```

**Artinya:**
- ✅ Message mention userbot
- ✅ Di group chat
- ✅ Dari user biasa (bukan bot)
- ✅ Bukan service message

**Contoh yang DITANGKAP:**
```
User mention userbot di group: "@userbotname test"
```

**Contoh yang TIDAK DITANGKAP:**
```
User mention userbot di private chat     ❌ (bukan group)
Bot mention userbot di group             ❌ (dari bot)
Service message "User joined"            ❌ (service message)
Message tanpa mention di group           ❌ (tidak mention)
```

---

## Testing Handler Priority

### Test Script

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test")

@Altruix.on_message(filters.mentioned, group=1)
async def handler_group_1(c, m):
    logger.info("Handler group=1 executed")
    # Tidak ada StopPropagation

@Altruix.on_message(filters.mentioned, group=4)
async def handler_group_4(c, m):
    logger.info("Handler group=4 executed")
```

**Expected output saat ada mention:**
```
Handler group=1 executed
Handler group=4 executed
```

**Jika handler_group_1 menggunakan StopPropagation:**
```
Handler group=1 executed
(handler_group_4 TIDAK dijalankan)
```

---

## Debugging Handler Issues

### Check 1: Verify Handler Registered

```python
# Di console Python
from Main import Altruix

# List all handlers
for client in Altruix.clients:
    print(f"Client: {client.me.first_name}")
    for group_num, handlers in client.dispatcher.groups.items():
        print(f"  Group {group_num}: {len(handlers)} handlers")
```

### Check 2: Test Filter Match

```python
# Test apakah message match filter
from pyrogram import filters

# Simulate message
class MockMessage:
    def __init__(self):
        self.mentioned = True
        self.chat = MockChat()
        self.from_user = MockUser()

class MockChat:
    def __init__(self):
        self.type = "supergroup"

class MockUser:
    def __init__(self):
        self.is_bot = False

msg = MockMessage()

# Test filters
print(f"filters.mentioned: {filters.mentioned(None, msg)}")
print(f"filters.group: {filters.group(None, msg)}")
print(f"~filters.bot: {(~filters.bot)(None, msg)}")
```

### Check 3: Monitor Handler Execution

Add logging to every handler:

```python
@Altruix.on_message(filters.mentioned, group=4)
async def hater_detector(c, m):
    logger.info(f"🔔 Handler triggered: group=4, msg_id={m.id}")
    # Rest of code
```

---

## Summary

### Hater Detector Changes

**Before:**
- `group=3` - Prioritas rendah, bisa di-block oleh handler lain

**After:**
- `group=4` - Prioritas lebih rendah dari mention logger (group=1)
- Tidak bentrok dengan plugin lain
- Tetap bisa dijalankan setelah mention logger

### Why group=4?

1. **Mention logger** menggunakan `group=1` (default)
2. **Hater detector** perlu dijalankan **SETELAH** mention logger
3. `group=4` memastikan tidak ada interference dari plugin lain
4. Masih cukup tinggi untuk tidak di-block oleh plugin optional lainnya

### Verification

Untuk memverifikasi handler terpicu:

```bash
# Restart userbot
# Test mention di group
# Cek console log untuk:
[Hater Detector] 🔔 hater_detector triggered for message <id>
```

Jika log muncul → Handler terpicu ✅
Jika log tidak muncul → Ada masalah dengan filter atau priority ❌
