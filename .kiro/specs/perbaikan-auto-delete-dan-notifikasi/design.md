# Dokumen Desain

## Gambaran Umum

Desain ini menjelaskan implementasi perbaikan fungsi auto-delete command, penambahan notifikasi progres untuk plugin xchatsanomlau, dan update string lokalisasi untuk Telegram userbot berbasis Pyrogram.

Sistem akan memperbaiki logic di `delete_if_self()` method untuk memastikan auto-delete berfungsi dengan benar ketika diaktifkan, menambahkan notifikasi progres yang dikirim ke LOG_CHAT_ID melalui bot assistant, dan memastikan semua string teks tersedia dalam file lokalisasi.

## Arsitektur

### Komponen Utama

1. **Message Type Extension** (`Main/core/types/message.py`)
   - Method `delete_if_self()` yang diperbaiki
   - Logic untuk membaca konfigurasi auto-delete dari database
   - Logic untuk menghapus pesan dengan delay

2. **Settings Handler** (`Main/internals/settings_handlers/cmd_settings_handlers.py`)
   - Handler untuk mengatur auto-delete melalui callback query
   - Sudah ada dan berfungsi dengan baik, tidak perlu perubahan

3. **Plugin xchatsanomlau** (`Main/plugins/userbot/xchatsanomlau.py`)
   - Fungsi `send_log_notification()` untuk mengirim notifikasi
   - Sudah ada dan berfungsi dengan baik
   - Notifikasi sudah terintegrasi di berbagai titik dalam `laucreate_loop()`

4. **Localization Files** (`Main/localization/en.yml`, `Main/localization/id.yml`)
   - String untuk UI auto-delete command
   - String untuk notifikasi plugin xchatsanomlau

### Alur Data

```
User Command → Message.delete_if_self() → Check Config → Delete with Delay
                                              ↓
                                        Database (ENV)
```

```
Laucreate Task → laucreate_loop() → send_log_notification() → Bot Assistant → LOG_CHAT_ID
```

## Komponen dan Interface

### 1. Message.delete_if_self()

**Lokasi:** `Main/core/types/message.py`

**Signature:**
```python
async def delete_if_self(self, **kwargs) -> Message
```

**Deskripsi:** Method untuk menghapus pesan jika pengirim adalah userbot sendiri (bukan sudo user), dengan mempertimbangkan pengaturan auto-delete.

**Logic Flow:**
1. Cek apakah pengirim adalah self (userbot) atau outgoing message
2. Jika ya, ambil client ID dari `self._client`
3. Cari index sesi dari `Altruix.clients`
4. Baca konfigurasi `AUTO_DELETE_CMD_TYPE_{index}` dari database
5. Jika type adalah "global", baca `AUTO_DELETE_CMD_GLOBAL` dan `AUTO_DELETE_CMD_DELAY_GLOBAL`
6. Jika type adalah "per_account", baca `AUTO_DELETE_CMD_STATUS_{index}` dan `AUTO_DELETE_CMD_DELAY_{index}`
7. Konversi status ke boolean (string "on" = True, lainnya = False)
8. Jika enabled = False, return self tanpa menghapus
9. Jika enabled = True, tunggu delay (jika ada), lalu hapus pesan
10. Handle exception dengan logging

**Perbaikan yang Diperlukan:**
- Pastikan logic untuk membaca konfigurasi benar
- Pastikan konversi string "on"/"off" ke boolean benar
- Pastikan delay dikonversi ke integer dengan benar
- Tambahkan error handling yang lebih baik

### 2. send_log_notification()

**Lokasi:** `Main/plugins/userbot/xchatsanomlau.py`

**Signature:**
```python
async def send_log_notification(
    bot_client: Client, 
    text: str, 
    user_id: int,
    reply_to_msg_id: Optional[int] = None, 
    disable_web_page_preview: bool = True
) -> Optional[Message]
```

**Deskripsi:** Fungsi helper untuk mengirim notifikasi ke PM user DAN LOG_CHAT_ID melalui bot assistant.

**Logic Flow:**
1. Kirim pesan ke PM user (user_id) menggunakan bot_client
2. Kirim pesan ke LOG_CHAT_ID menggunakan bot_client
3. Gunakan reply_to_message_id jika disediakan (untuk LOG_CHAT_ID)
4. Set disable_web_page_preview sesuai parameter
5. Parse mode HTML
6. Return message object jika berhasil
7. Return None jika gagal, dengan logging error

**Perubahan yang Diperlukan:**
- Tambahkan parameter user_id
- Kirim notifikasi ke dua tempat: PM user dan LOG_CHAT_ID
- Handle error untuk masing-masing pengiriman secara terpisah

### 3. Localization Strings

**Lokasi:** `Main/localization/en.yml`, `Main/localization/id.yml`

**String yang Perlu Ditambahkan/Diverifikasi:**

Untuk auto-delete command:
- `auto_delete_cmd`: "Auto-Delete Command"
- `auto_delete_cmd_desc`: "Automatically delete command messages after execution"
- `auto_delete_enabled`: "Auto-Delete: ENABLED"
- `auto_delete_disabled`: "Auto-Delete: DISABLED"
- `auto_delete_delay`: "Delay: {}s"

Untuk plugin xchatsanomlau:
- `laucreate_started`: "🚀 Laucreate Task Started"
- `laucreate_progress`: "✅ Group {}/{} created successfully"
- `laucreate_batch_report`: "✅ Batch {} completed: {} groups"
- `laucreate_completed`: "✅ Laucreate Task Completed"
- `laucreate_error`: "❌ Error creating group: {}"
- `laucreate_paused`: "⏸️ Task paused"
- `laucreate_resumed`: "▶️ Task resumed"

## Model Data

### Konfigurasi Auto-Delete (Database ENV)

```python
# Per-account settings
AUTO_DELETE_CMD_TYPE_{index}: str  # "global" atau "per_account"
AUTO_DELETE_CMD_STATUS_{index}: str  # "on" atau "off"
AUTO_DELETE_CMD_DELAY_{index}: str  # angka dalam string, contoh: "2"

# Global settings
AUTO_DELETE_CMD_GLOBAL: str  # "on" atau "off"
AUTO_DELETE_CMD_DELAY_GLOBAL: str  # angka dalam string, contoh: "2"
```

### State Laucreate Task

```python
LAUCREATE_TASKS = {
    "laucreate_main": {
        "running": bool,
        "paused": bool,
        "pause_event": asyncio.Event,
        "current_index": int,
        "created_groups": List[Dict],
        "start_time": datetime,
        "control_message_id": int,
        "user_id": int,
        "params": Dict[str, Any]
    }
}
```

## Properti Kebenaran

*Properti adalah karakteristik atau perilaku yang harus berlaku untuk semua eksekusi sistem yang valid - pada dasarnya, pernyataan formal tentang apa yang harus dilakukan sistem. Properti berfungsi sebagai jembatan antara spesifikasi yang dapat dibaca manusia dan jaminan kebenaran yang dapat diverifikasi mesin.*


### Refleksi Properti

Setelah menganalisis semua kriteria penerimaan, beberapa properti dapat digabungkan untuk menghindari redundansi:

- Property 1.2 dan 1.3 dapat digabungkan menjadi satu properti yang menguji bahwa sistem membaca konfigurasi dari sumber yang benar berdasarkan type
- Property 4.1, 4.2, 4.3, dan 4.6 dapat digabungkan menjadi satu properti tentang backward compatibility
- Property 5.1 dan 5.2 dapat digabungkan menjadi satu properti tentang kelengkapan string lokalisasi
- Property 5.4 dan 5.5 redundant dengan 5.1 dan 5.2, akan dihapus

### Properti 1: Auto-Delete Menghapus Self Message Ketika Enabled

*Untuk setiap* pesan yang berasal dari userbot sendiri (self message), ketika auto-delete status diset ke "on", pesan tersebut harus dihapus setelah eksekusi.

**Memvalidasi: Persyaratan 1.1, 1.6**

### Properti 2: Auto-Delete Membaca Konfigurasi dari Sumber yang Benar

*Untuk setiap* sesi userbot, ketika AUTO_DELETE_CMD_TYPE_{index} diset ke "global", sistem harus membaca dari AUTO_DELETE_CMD_GLOBAL; ketika diset ke "per_account", sistem harus membaca dari AUTO_DELETE_CMD_STATUS_{index}.

**Memvalidasi: Persyaratan 1.2, 1.3**

### Properti 3: Auto-Delete Menghormati Delay yang Dikonfigurasi

*Untuk setiap* pesan yang akan dihapus, ketika delay dikonfigurasi ke N detik, waktu antara eksekusi dan penghapusan harus sekitar N detik (dengan toleransi ±1 detik).

**Memvalidasi: Persyaratan 1.4**

### Properti 4: Notifikasi Progres Dikirim untuk Setiap Grup

*Untuk setiap* grup yang berhasil dibuat dalam task laucreate, sistem harus mengirim notifikasi progres ke PM user DAN LOG_CHAT_ID melalui bot assistant.

**Memvalidasi: Persyaratan 2.2**

### Properti 5: Laporan Batch Dikirim Setelah Setiap Batch

*Untuk setiap* batch yang selesai dalam task laucreate, sistem harus mengirim laporan batch ke PM user DAN LOG_CHAT_ID dengan jumlah grup yang dibuat.

**Memvalidasi: Persyaratan 2.3**

### Properti 6: Notifikasi Error Dikirim Ketika Error Terjadi

*Untuk setiap* error yang terjadi selama pembuatan grup, sistem harus mengirim notifikasi error ke PM user DAN LOG_CHAT_ID dengan detail error.

**Memvalidasi: Persyaratan 2.5**

### Properti 7: Semua Notifikasi Menggunakan Bot Assistant dan Dikirim ke Dua Tempat

*Untuk setiap* notifikasi yang dikirim, sistem harus menggunakan bot_client (bot assistant) dan mengirim ke dua tempat: PM user dan LOG_CHAT_ID.

**Memvalidasi: Persyaratan 2.7**

### Properti 8: Konfigurasi Round-Trip Consistency

*Untuk setiap* konfigurasi auto-delete yang ditulis ke database, membaca kembali konfigurasi tersebut harus menghasilkan nilai yang sama.

**Memvalidasi: Persyaratan 3.3**

### Properti 9: Exception Handling Tidak Menyebabkan Crash

*Untuk setiap* exception yang terjadi dalam delete_if_self() atau send_log_notification(), sistem harus menangani exception dengan graceful (tidak crash) dan log error dengan level yang sesuai.

**Memvalidasi: Persyaratan 3.5**

### Properti 10: Input Validation Menolak Invalid Input

*Untuk setiap* parameter input yang invalid (misalnya delay bukan angka, status bukan "on"/"off"), sistem harus menangani dengan benar (gunakan default value atau skip operasi).

**Memvalidasi: Persyaratan 3.6**

### Properti 11: Backward Compatibility Preserved

*Untuk setiap* method, handler, dan fungsi yang ada sebelum perubahan, signature (parameter dan return type) harus tetap sama dan fungsionalitas harus tetap bekerja.

**Memvalidasi: Persyaratan 4.1, 4.2, 4.3, 4.6**

### Properti 12: Kelengkapan String Lokalisasi

*Untuk setiap* key string yang digunakan dalam kode untuk fitur auto-delete dan xchatsanomlau, key tersebut harus ada di kedua file lokalisasi (en.yml dan id.yml).

**Memvalidasi: Persyaratan 5.1, 5.2, 5.6**

### Properti 13: Konsistensi Format String Lokalisasi

*Untuk setiap* string lokalisasi yang menggunakan placeholder, format placeholder harus konsisten (menggunakan {} untuk Python string formatting).

**Memvalidasi: Persyaratan 5.3**

## Penanganan Error

### Error Scenarios

1. **Database Connection Error**
   - Jika koneksi ke database gagal saat membaca konfigurasi auto-delete
   - Fallback: Gunakan default value (auto-delete disabled)
   - Log error dengan level WARNING

2. **Message Delete Permission Error**
   - Jika userbot tidak memiliki permission untuk menghapus pesan
   - Fallback: Skip delete operation, log error dengan level INFO
   - Tidak crash, return self

3. **Bot Assistant Not Available**
   - Jika bot assistant tidak tersedia atau tidak bisa mengirim pesan
   - Fallback: Log error dengan level ERROR
   - Task tetap berjalan, hanya notifikasi yang gagal

4. **Invalid Configuration Value**
   - Jika nilai konfigurasi tidak valid (misalnya delay bukan angka)
   - Fallback: Gunakan default value (delay = 0)
   - Log warning

5. **Localization String Not Found**
   - Jika key string tidak ditemukan di file lokalisasi
   - Fallback: Return key string itu sendiri
   - Log warning

### Error Logging Levels

- **DEBUG**: Informasi detail untuk debugging (misalnya: "Reading config for index 0")
- **INFO**: Informasi normal (misalnya: "Auto-delete disabled, skipping")
- **WARNING**: Situasi yang tidak normal tapi tidak critical (misalnya: "Config not found, using default")
- **ERROR**: Error yang perlu perhatian (misalnya: "Failed to send notification")
- **CRITICAL**: Error yang menyebabkan sistem tidak bisa berfungsi (tidak digunakan dalam fitur ini)

## Strategi Pengujian

### Pendekatan Dual Testing

Pengujian akan menggunakan kombinasi unit test dan property-based test:

- **Unit tests**: Untuk contoh spesifik, edge case, dan kondisi error
- **Property tests**: Untuk memverifikasi properti universal di berbagai input

### Unit Testing

Unit test akan fokus pada:

1. **Edge Cases**
   - Pesan dari sudo user tidak dihapus (Persyaratan 1.5)
   - Auto-delete disabled tidak menghapus pesan (Persyaratan 1.7)
   - Notifikasi awal task laucreate (Persyaratan 2.1)
   - Notifikasi akhir task laucreate (Persyaratan 2.4)
   - Notifikasi pause/resume (Persyaratan 2.6)

2. **Integration Points**
   - Integrasi delete_if_self() dengan database
   - Integrasi send_log_notification() dengan bot assistant
   - Integrasi settings handler dengan callback query

3. **Error Conditions**
   - Database connection error
   - Permission error saat delete
   - Bot assistant tidak tersedia

### Property-Based Testing

Property test akan fokus pada:

1. **Auto-Delete Properties** (Properti 1, 2, 3)
   - Generate random message dengan berbagai konfigurasi
   - Verifikasi behavior sesuai dengan konfigurasi
   - Minimum 100 iterasi per test

2. **Notification Properties** (Properti 4, 5, 6, 7)
   - Generate random task dengan berbagai parameter
   - Verifikasi notifikasi terkirim dengan benar
   - Minimum 100 iterasi per test

3. **Configuration Properties** (Properti 8)
   - Generate random konfigurasi
   - Verifikasi round-trip consistency
   - Minimum 100 iterasi per test

4. **Error Handling Properties** (Properti 9, 10)
   - Generate random exception dan invalid input
   - Verifikasi sistem tidak crash
   - Minimum 100 iterasi per test

5. **Backward Compatibility Properties** (Properti 11)
   - Verifikasi semua method existing masih berfungsi
   - Test dengan berbagai input
   - Minimum 100 iterasi per test

6. **Localization Properties** (Properti 12, 13)
   - Verifikasi kelengkapan dan konsistensi string
   - Test dengan berbagai key
   - Minimum 100 iterasi per test

### Konfigurasi Property Test

- **Library**: `hypothesis` untuk Python
- **Iterasi minimum**: 100 per property test
- **Tag format**: `Feature: perbaikan-auto-delete-dan-notifikasi, Property {number}: {property_text}`
- **Setiap property test harus reference design document property**

### Balance Unit vs Property Tests

- Unit tests untuk edge case spesifik dan contoh konkret
- Property tests untuk coverage input yang luas
- Hindari terlalu banyak unit test yang redundant dengan property test
- Fokus unit test pada integration dan error condition
