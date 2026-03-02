# Dokumen Persyaratan: Perbaikan Logic Tombol Auto Pro GCast

## Pendahuluan

Spesifikasi ini mendefinisikan perbaikan untuk bug "invalid index" yang terjadi pada berbagai tombol di plugin Auto Pro Global Broadcast (xauto_pro_gcast.py). Bug ini muncul karena kesalahan logic dalam ekstraksi user ID dari callback data, yang menyebabkan sistem menggunakan index pesan sebagai user ID.

## Glosarium

- **Callback Data**: String yang dikirim ketika user menekan inline button di Telegram
- **UID (User ID)**: ID unik pengguna Telegram yang menggunakan bot
- **Message Index**: Index pesan dalam list pesan broadcast (0, 1, 2, dst)
- **Callback Handler**: Fungsi yang memproses callback dari inline button
- **Parts**: Array hasil split callback data berdasarkan underscore (_)
- **Message List**: Daftar pesan (text/media) yang akan di-broadcast
- **Preview Button**: Tombol untuk melihat preview pesan sebelum broadcast
- **Delete Button**: Tombol untuk menghapus pesan dari list
- **Fixed Message**: Pesan yang dipilih untuk selalu dikirim (tidak random)
- **Smart Purge**: Fitur untuk menghapus pesan lama sebelum broadcast
- **Blacklist**: Daftar chat yang di-skip dari broadcast

## Persyaratan

### Persyaratan 1: Ekstraksi User ID yang Benar dari Callback Data

**User Story:** Sebagai pengguna yang menekan tombol pada dashboard Auto Pro GCast, saya ingin sistem mengidentifikasi user ID saya dengan benar dari callback data, sehingga tidak terjadi error "invalid index" atau "invalid user id".

#### Kriteria Penerimaan

1.1. WHEN callback data memiliki format `pgc_msgpreview_text_{uid}_{index}`, THEN THE System SHALL extract UID dari parts[3] (bukan dari parts[4] yang merupakan index)

1.2. WHEN callback data memiliki format `pgc_msgpreview_media_{uid}_{index}`, THEN THE System SHALL extract UID dari parts[3]

1.3. WHEN callback data memiliki format `pgc_msgdelconf_text_{uid}_{index}`, THEN THE System SHALL extract UID dari parts[3]

1.4. WHEN callback data memiliki format `pgc_msgdelconf_media_{uid}_{index}`, THEN THE System SHALL extract UID dari parts[3]

1.5. WHEN callback data memiliki format `pgc_msgdel_text_{uid}_{index}`, THEN THE System SHALL extract UID dari parts[3]

1.6. WHEN callback data memiliki format `pgc_msgdel_media_{uid}_{index}`, THEN THE System SHALL extract UID dari parts[3]

1.7. WHEN callback data memiliki format `pgc_msgsetfixed_text_{uid}_{index}`, THEN THE System SHALL extract UID dari parts[3]

1.8. WHEN callback data memiliki format `pgc_msgsetfixed_media_{uid}_{index}`, THEN THE System SHALL extract UID dari parts[3]

1.9. WHEN callback data memiliki format `pgc_bldel_{uid}_{index}`, THEN THE System SHALL extract UID dari parts[2]

1.10. WHEN callback data memiliki format `pgc_action_{uid}_page_{N}`, THEN THE System SHALL extract UID dari parts[2]

1.11. WHEN callback data memiliki format `pgc_sp_action_{uid}`, THEN THE System SHALL extract UID dengan mencari last numeric part (bukan parts[2] yang mungkin "limit", "delay", dll)

1.12. WHEN callback data memiliki format standard `pgc_action_{uid}`, THEN THE System SHALL extract UID dari parts[2]

### Persyaratan 2: Validasi User ID yang Ekstrak

**User Story:** Sebagai sistem, saya ingin memvalidasi bahwa user ID yang diekstrak adalah valid dan sesuai dengan user yang menekan tombol, sehingga tidak terjadi unauthorized access atau error.

#### Kriteria Penerimaan

2.1. WHEN user ID berhasil diekstrak, THEN THE System SHALL verify bahwa UID adalah integer positif

2.2. WHEN user ID tidak dapat diekstrak atau invalid, THEN THE System SHALL return error message "Invalid user ID" dan tidak melanjutkan operasi

2.3. WHEN user ID valid, THEN THE System SHALL load settings untuk user tersebut dari database

2.4. IF settings tidak ditemukan untuk user ID, THEN THE System SHALL create default settings untuk user tersebut

### Persyaratan 3: Ekstraksi Index Pesan yang Benar

**User Story:** Sebagai pengguna yang menekan tombol preview/delete pada message list, saya ingin sistem mengidentifikasi index pesan yang benar, sehingga preview/delete dilakukan pada pesan yang tepat.

#### Kriteria Penerimaan

3.1. WHEN callback data memiliki format dengan index di akhir (contoh: `pgc_msgpreview_text_{uid}_{index}`), THEN THE System SHALL extract index dari parts[-1] (last part)

3.2. WHEN callback data memiliki format `pgc_bldel_{uid}_{index}`, THEN THE System SHALL extract index dari parts[3]

3.3. WHEN index berhasil diekstrak, THEN THE System SHALL verify bahwa index adalah integer non-negative (>= 0)

3.4. WHEN index tidak dapat diekstrak atau invalid, THEN THE System SHALL return error message "Invalid index" dan tidak melanjutkan operasi

3.5. WHEN index valid, THEN THE System SHALL verify bahwa index berada dalam range list yang sesuai (text_list atau media_list)

3.6. IF index out of range, THEN THE System SHALL return error message "Invalid index" dan tidak melanjutkan operasi

### Persyaratan 4: Konsistensi Format Callback Data

**User Story:** Sebagai developer, saya ingin format callback data konsisten di seluruh aplikasi, sehingga mudah di-maintain dan tidak terjadi bug karena format yang berbeda-beda.

#### Kriteria Penerimaan

4.1. THE System SHALL use consistent format untuk semua callback data: `pgc_{action}_{params}`

4.2. WHEN action membutuhkan type (text/media), THEN format SHALL be `pgc_{action}_{type}_{uid}_{index}`

4.3. WHEN action membutuhkan pagination, THEN format SHALL be `pgc_{action}_{uid}_page_{N}`

4.4. WHEN action adalah smart purge sub-action, THEN format SHALL be `pgc_sp_{subaction}_{uid}`

4.5. WHEN action adalah blacklist delete, THEN format SHALL be `pgc_bldel_{uid}_{index}`

4.6. THE System SHALL document all callback formats in code comments untuk reference

### Persyaratan 5: Error Handling yang Robust

**User Story:** Sebagai pengguna, saya ingin sistem memberikan error message yang jelas ketika terjadi error, sehingga saya tahu apa yang salah dan bagaimana memperbaikinya.

#### Kriteria Penerimaan

5.1. WHEN callback data invalid (kurang dari minimum parts), THEN THE System SHALL return error "Invalid callback data"

5.2. WHEN user ID tidak dapat diekstrak, THEN THE System SHALL return error "Invalid user ID"

5.3. WHEN index tidak dapat diekstrak atau out of range, THEN THE System SHALL return error "Invalid index"

5.4. WHEN permission error terjadi (user bukan pemilik button), THEN THE System SHALL return error "Unauthorized"

5.5. WHEN exception terjadi dalam handler, THEN THE System SHALL catch exception, log error, dan return generic error message

5.6. ALL error messages SHALL be sent via safe_cb_answer() dengan show_alert=True

### Persyaratan 6: Testing dan Validasi

**User Story:** Sebagai developer, saya ingin semua tombol di-test dengan berbagai skenario, sehingga tidak ada bug yang terlewat dan sistem berjalan dengan stabil.

#### Kriteria Penerimaan

6.1. THE System SHALL have unit tests untuk setiap format callback data

6.2. THE System SHALL have property tests untuk ekstraksi UID dan index dengan berbagai input

6.3. THE System SHALL have integration tests untuk setiap tombol di dashboard

6.4. THE System SHALL verify bahwa tidak ada tombol yang menghasilkan error "invalid index" atau "invalid user id"

6.5. THE System SHALL test dengan berbagai user ID (short, long, numeric patterns)

6.6. THE System SHALL test dengan berbagai index (0, 1, 10, 100, dst)

6.7. THE System SHALL test edge cases (empty list, single item, max items)

## Batasan dan Asumsi

### Batasan

1. Callback data Telegram memiliki limit 64 bytes, sehingga format harus efisien
2. User ID Telegram adalah integer positif (tidak ada negative atau zero)
3. Index pesan dimulai dari 0 (zero-based indexing)
4. Callback handler harus response dalam 30 detik atau Telegram akan timeout

### Asumsi

1. User yang menekan tombol adalah user yang authorized (sudah di-check oleh @iuser_check decorator)
2. Settings database selalu available dan tidak corrupt
3. Callback data tidak di-tamper oleh user (Telegram ensures integrity)
4. List pesan (text_list, media_list) tidak berubah selama user melihat dashboard

## Prioritas

1. **P0 (Critical)**: Persyaratan 1 (Ekstraksi UID yang benar) - tanpa ini semua tombol error
2. **P0 (Critical)**: Persyaratan 3 (Ekstraksi index yang benar) - tanpa ini preview/delete error
3. **P1 (High)**: Persyaratan 2 (Validasi UID) - untuk security dan stability
4. **P1 (High)**: Persyaratan 5 (Error handling) - untuk user experience
5. **P2 (Medium)**: Persyaratan 4 (Konsistensi format) - untuk maintainability
6. **P2 (Medium)**: Persyaratan 6 (Testing) - untuk quality assurance
