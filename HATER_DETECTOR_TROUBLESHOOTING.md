# Hater Detector Troubleshooting Guide

## Masalah yang Dilaporkan

1. ✅ **Di Group LOG**: User hater reply → muncul "AUTH_FEATURE_DENIED" 
   - **Status**: FIXED (xpm_logger_user.py sudah diperbaiki)
   
2. ❌ **Di Group BIASA**: User hater reply/mention userbot → TIDAK ADA RESPONSE
   - **Status**: PERLU DEBUGGING

---

## Root Cause Analysis

### Masalah 1: AUTH_FEATURE_DENIED di Group Log (FIXED)

**Penyebab:**
- Handler `handle_pmlu_send_message_input` di `xpm_logger_user.py` menggunakan `@iuser_check`
- Handler ini menangkap SEMUA reply di log chat, termasuk dari user hater
- Karena user hater bukan sudo, `@iuser_check` menolak dengan "AUTH_FEATURE_DENIED"

**Solusi:**
- Pindahkan authorization check ke dalam function
- Early return jika bukan reply ke "Send Message to User"
- Hanya check authorization untuk request yang valid

**File yang diubah:**
- `Main/plugins/userbot/xpm_logger_user.py` (line 1484-1500)

---

### Masalah 2: Hater Detector Tidak Bekerja di Group Biasa

**Kemungkinan Penyebab:**

#### A. Feature Disabled
```bash
# Cek status
.haterstatus

# Jika disabled, enable dengan:
.hateron
```

#### B. User Belum Block Userbot
Hater detector **HANYA** bekerja jika user benar-benar sudah block userbot.

**Cara test:**
```bash
# Test kirim pesan ke user hater
.send <user_id> test

# Jika error "UserIsBlocked" atau "PeerIdInvalid" → user sudah block
# Jika terkirim → user BELUM block
```

#### C. Response Tidak Dikonfigurasi
```bash
# Cek responses
.haterresponses

# Jika kosong, tambahkan:
.hateraddresponse {mention_name} blocked me but still mentions? 🤔
```

#### D. Handler Tidak Terpicu

**Cek log untuk melihat apakah handler terpicu:**

```python
# Log yang harus muncul jika handler terpicu:
[Hater Detector] hater_detector triggered for message <msg_id> from <user_id>
[Hater Detector] Processing message from <user_id> in chat <chat_id>
[Hater Detector] Message from <user_id> is relevant (mention=True/False, reply=True/False)
```

**Jika log tidak muncul**, kemungkinan:
1. Filter `filters.mentioned` tidak menangkap mention
2. Filter `filters.reply` tidak menangkap reply
3. Message dari bot (`~filters.bot` memfilter)
4. Message adalah service message (`~filters.service` memfilter)

---

## Debugging Steps

### Step 1: Cek Status Feature

```bash
.haterstatus
```

**Expected output:**
```
🚫 Haters Detector Status
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Status: 🟢 ENABLED
Response Delay: 0s
Log Detections: ON
Random Response: ON
Total Responses: 1
Detected Haters: 0
```

**Jika Status: 🔴 DISABLED:**
```bash
.hateron
```

---

### Step 2: Cek Responses

```bash
.haterresponses
```

**Expected output:**
```
📝 Custom Responses
Total: 1
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. [HTML] 🚫 <b>{mention_name}</b> blocked me but still mentions me? Interesting...
```

**Jika kosong:**
```bash
.hateraddresponse {mention_name} blocked me but still mentions? 🤔
```

---

### Step 3: Verify User Blocked Userbot

```bash
# Test send message to hater user
.send <hater_user_id> test
```

**Expected result jika user sudah block:**
```
❌ Failed to send message
Error: UserIsBlocked
```

**Jika message terkirim:**
- User BELUM block userbot
- Hater detector tidak akan bekerja

---

### Step 4: Test di Group dengan Logging

1. **Enable logging:**
```bash
.haterlog  # pastikan ON
```

2. **Minta user hater untuk:**
   - Mention userbot: `@userbotname test`
   - Reply ke message userbot

3. **Cek log chat untuk melihat:**
   - Detection log: "🚫 Hater Detected!"
   - Response sent confirmation

4. **Cek console log untuk:**
```
[Hater Detector] hater_detector triggered for message <id>
[Hater Detector] Processing message from <user_id>
[Hater Detector] User <user_id> blocked status: True
[Hater Detector] Sending response to <user_id>...
[Hater Detector] ✅ Response sent successfully! Message ID: <msg_id>
```

---

### Step 5: Manual Test dengan Python

Jika masih tidak bekerja, test manual:

```python
# Di console Python
from Main.plugins.userbot.xdetect_haters import check_if_blocked
from Main import Altruix

# Test check block status
client = Altruix.clients[0]  # userbot pertama
hater_id = 8214021089  # user ID hater

is_blocked = await check_if_blocked(client, hater_id)
print(f"User {hater_id} blocked: {is_blocked}")
```

**Expected output jika user sudah block:**
```
User 8214021089 blocked: True
```

---

## Common Issues & Solutions

### Issue 1: "Feature disabled for user"

**Cause:** Hater detector disabled

**Solution:**
```bash
.hateron
```

---

### Issue 2: "No responses configured"

**Cause:** Tidak ada response template

**Solution:**
```bash
.hateraddresponse {mention_name} blocked me but still mentions? 🤔
```

---

### Issue 3: User belum block userbot

**Cause:** User hanya mute/archive, tidak block

**Solution:**
- Minta user untuk benar-benar block userbot
- Test dengan `.send <user_id> test` untuk verify

---

### Issue 4: Handler tidak terpicu

**Possible causes:**
1. Message dari bot account (bukan user)
2. Message adalah service message (join/leave/etc)
3. Filter tidak match

**Solution:**
- Cek console log untuk "[Hater Detector]" entries
- Pastikan message dari user biasa (bukan bot)
- Pastikan bukan service message

---

### Issue 5: Response tidak muncul di group

**Possible causes:**
1. Userbot tidak punya permission untuk send message
2. Group settings restrict userbot
3. Error saat send (cek log)

**Solution:**
- Cek console log untuk error
- Test send message manual di group
- Cek group permissions

---

## Testing Checklist

- [ ] Feature enabled (`.haterstatus` shows 🟢 ENABLED)
- [ ] Response configured (`.haterresponses` shows at least 1)
- [ ] User actually blocked userbot (`.send <user_id> test` fails)
- [ ] Message is mention/reply to userbot
- [ ] Not in log chat
- [ ] Not from self
- [ ] Console log shows "[Hater Detector]" entries
- [ ] Detection log appears in log chat
- [ ] Response appears in group chat

---

## Log Examples

### Successful Detection:

**Console log:**
```
[Hater Detector] hater_reply_detector triggered for message 12345 from 8214021089
[Hater Detector] Processing message from 8214021089 in chat -1001234567890 (mention=False, reply=True)
[Hater Detector] Message from 8214021089 is relevant (mention=False, reply=True)
[Hater Detector] Reply to us detected from 8214021089
[Hater Detector] Checking if 8214021089 has blocked us (API call)...
[Hater Detector] User 8214021089 blocked status: True (cached)
[Hater Detector] Selected response template: 🚫 <b>{mention_name}</b> blocked me but still...
[Hater Detector] Sending response to 8214021089 in chat -1001234567890...
[Hater Detector] Response text: 🚫 <a href="tg://user?id=8214021089">N1</a> blocked me but still...
[Hater Detector] ✅ Response sent successfully! Message ID: 12346
```

**Log chat:**
```
🚫 Hater Detected!

User: N1 (8214021089)
Username: @None
Chat: Test Group
Detection Count: 1
Message: test reply
```

**Group chat:**
```
🚫 N1 blocked me but still mentions? 🤔
```

---

### Failed Detection (User not blocked):

**Console log:**
```
[Hater Detector] hater_reply_detector triggered for message 12345 from 8214021089
[Hater Detector] Processing message from 8214021089 in chat -1001234567890 (mention=False, reply=True)
[Hater Detector] Message from 8214021089 is relevant (mention=False, reply=True)
[Hater Detector] Reply to us detected from 8214021089
[Hater Detector] Checking if 8214021089 has blocked us (API call)...
[Hater Detector] User 8214021089 blocked status: False (cached)
```

**No response sent** (user tidak block)

---

### Failed Detection (Feature disabled):

**Console log:**
```
[Hater Detector] hater_reply_detector triggered for message 12345 from 8214021089
[Hater Detector] Processing message from 8214021089 in chat -1001234567890 (mention=False, reply=True)
[Hater Detector] Message from 8214021089 is relevant (mention=False, reply=True)
[Hater Detector] Feature disabled for user 123456789, skipping
```

**No response sent** (feature disabled)

---

## Next Steps

1. Jalankan semua debugging steps di atas
2. Share console log lengkap dengan "[Hater Detector]" prefix
3. Share screenshot dari:
   - `.haterstatus`
   - `.haterresponses`
   - Test `.send <user_id> test`
4. Confirm apakah user benar-benar sudah block userbot

Dengan informasi ini, kita bisa identify masalah yang sebenarnya.
