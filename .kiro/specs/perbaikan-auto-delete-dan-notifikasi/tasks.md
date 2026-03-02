# Rencana Implementasi: Perbaikan Auto-Delete dan Notifikasi

## Gambaran Umum

Rencana implementasi ini mencakup perbaikan fungsi auto-delete command, penambahan notifikasi progres ke PM user untuk plugin xchatsanomlau, pengujian menyeluruh, dan update string lokalisasi. Implementasi menggunakan Python dengan framework Pyrogram untuk Telegram userbot.

## Tasks

- [x] 1. Perbaiki fungsi auto-delete command di Message class
  - [x] 1.1 Perbaiki logic delete_if_self() untuk membaca konfigurasi dengan benar
    - Perbaiki pembacaan AUTO_DELETE_CMD_TYPE_{index} dari database
    - Perbaiki logic untuk memilih antara global dan per-account config
    - Perbaiki konversi string "on"/"off" ke boolean
    - Perbaiki konversi delay string ke integer
    - Tambahkan error handling yang lebih baik
    - _Persyaratan: 1.1, 1.2, 1.3, 1.4, 1.6, 1.7_
  
  - [x]* 1.2 Tulis property test untuk auto-delete behavior
    - **Property 1: Auto-Delete Menghapus Self Message Ketika Enabled**
    - **Memvalidasi: Persyaratan 1.1, 1.6**
    - Gunakan hypothesis untuk generate random message dan konfigurasi
    - Minimum 100 iterasi per test
  
  - [x]* 1.3 Tulis property test untuk konfigurasi source selection
    - **Property 2: Auto-Delete Membaca Konfigurasi dari Sumber yang Benar**
    - **Memvalidasi: Persyaratan 1.2, 1.3**
    - Test dengan berbagai kombinasi AUTO_DELETE_CMD_TYPE
    - Minimum 100 iterasi per test
  
  - [x]* 1.4 Tulis property test untuk delay timing
    - **Property 3: Auto-Delete Menghormati Delay yang Dikonfigurasi**
    - **Memvalidasi: Persyaratan 1.4**
    - Verifikasi timing dengan toleransi ±1 detik
    - Minimum 100 iterasi per test
  
  - [x]* 1.5 Tulis unit test untuk edge cases auto-delete
    - Test pesan dari sudo user tidak dihapus (Persyaratan 1.5)
    - Test auto-delete disabled tidak menghapus pesan (Persyaratan 1.7)
    - Test dengan berbagai kombinasi parameter
    - _Persyaratan: 1.5, 1.7_

- [x] 2. Checkpoint - Pastikan semua test auto-delete pass
  - Pastikan semua test pass, tanyakan user jika ada pertanyaan.

- [x] 3. Tambahkan notifikasi progres ke PM user untuk plugin xchatsanomlau
  - [x] 3.1 Modifikasi fungsi send_log_notification()
    - Tambahkan parameter user_id
    - Implementasi pengiriman ke PM user (bot_client.send_message ke user_id)
    - Implementasi pengiriman ke LOG_CHAT_ID (existing)
    - Handle error untuk masing-masing pengiriman secara terpisah
    - _Persyaratan: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_
  
  - [x] 3.2 Update semua pemanggilan send_log_notification() di laucreate_loop()
    - Tambahkan parameter user_id ke semua pemanggilan
    - Pastikan user_id diambil dari task state atau initial_message
    - _Persyaratan: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_
  
  - [x]* 3.3 Tulis property test untuk notifikasi progres
    - **Property 4: Notifikasi Progres Dikirim untuk Setiap Grup**
    - **Memvalidasi: Persyaratan 2.2**
    - Generate random task dengan berbagai jumlah grup
    - Verifikasi notifikasi terkirim untuk setiap grup
    - Minimum 100 iterasi per test
  
  - [x]* 3.4 Tulis property test untuk laporan batch
    - **Property 5: Laporan Batch Dikirim Setelah Setiap Batch**
    - **Memvalidasi: Persyaratan 2.3**
    - Generate random batch size dan jumlah grup
    - Verifikasi laporan batch terkirim dengan benar
    - Minimum 100 iterasi per test
  
  - [x]* 3.5 Tulis property test untuk notifikasi error
    - **Property 6: Notifikasi Error Dikirim Ketika Error Terjadi**
    - **Memvalidasi: Persyaratan 2.5**
    - Generate random error scenarios
    - Verifikasi notifikasi error terkirim
    - Minimum 100 iterasi per test
  
  - [x]* 3.6 Tulis property test untuk penggunaan bot assistant
    - **Property 7: Semua Notifikasi Menggunakan Bot Assistant dan Dikirim ke Dua Tempat**
    - **Memvalidasi: Persyaratan 2.7**
    - Verifikasi setiap notifikasi dikirim ke PM user DAN LOG_CHAT_ID
    - Minimum 100 iterasi per test
  
  - [x]* 3.7 Tulis unit test untuk notifikasi spesifik
    - Test notifikasi awal task (Persyaratan 2.1)
    - Test notifikasi akhir task dengan file log (Persyaratan 2.4)
    - Test notifikasi pause/resume (Persyaratan 2.6)
    - _Persyaratan: 2.1, 2.4, 2.6_

- [x] 4. Checkpoint - Pastikan semua test notifikasi pass
  - Pastikan semua test pass, tanyakan user jika ada pertanyaan.

- [x] 5. Implementasi pengujian menyeluruh dan error handling
  - [x] 5.1 Tambahkan error handling di delete_if_self()
    - Handle database connection error dengan fallback ke default
    - Handle permission error dengan graceful skip
    - Handle invalid config value dengan default value
    - Log error dengan level yang sesuai (DEBUG, INFO, WARNING, ERROR)
    - _Persyaratan: 3.5, 3.6_
  
  - [x] 5.2 Tambahkan error handling di send_log_notification()
    - Handle bot assistant not available
    - Handle permission error
    - Log error dengan level yang sesuai
    - _Persyaratan: 3.5_
  
  - [x]* 5.3 Tulis property test untuk konfigurasi round-trip
    - **Property 8: Konfigurasi Round-Trip Consistency**
    - **Memvalidasi: Persyaratan 3.3**
    - Generate random konfigurasi, write ke database, read kembali
    - Verifikasi nilai sama setelah round-trip
    - Minimum 100 iterasi per test
  
  - [x]* 5.4 Tulis property test untuk exception handling
    - **Property 9: Exception Handling Tidak Menyebabkan Crash**
    - **Memvalidasi: Persyaratan 3.5**
    - Generate random exception dalam delete_if_self() dan send_log_notification()
    - Verifikasi sistem tidak crash dan log error dengan benar
    - Minimum 100 iterasi per test
  
  - [x]* 5.5 Tulis property test untuk input validation
    - **Property 10: Input Validation Menolak Invalid Input**
    - **Memvalidasi: Persyaratan 3.6**
    - Generate random invalid input (delay bukan angka, status bukan "on"/"off")
    - Verifikasi sistem handle dengan benar (gunakan default atau skip)
    - Minimum 100 iterasi per test
  
  - [x]* 5.6 Tulis unit test untuk error scenarios
    - Test database connection error
    - Test permission error saat delete message
    - Test bot assistant not available
    - Test invalid configuration value
    - _Persyaratan: 3.5, 3.6_

- [x] 6. Checkpoint - Pastikan semua test error handling pass
  - Pastikan semua test pass, tanyakan user jika ada pertanyaan.

- [x] 7. Verifikasi backward compatibility
  - [x] 7.1 Verifikasi semua method existing di Message class masih berfungsi
    - Test edit_msg(), reply_msg(), handle_message()
    - Test dengan berbagai parameter dan kombinasi
    - Verifikasi signature dan return value tidak berubah
    - _Persyaratan: 4.1, 4.6_
  
  - [x] 7.2 Verifikasi semua handler existing di cmd_settings_handlers.py masih berfungsi
    - Test cmd_settings_menu_handler dengan berbagai callback query
    - Test toggle handlers untuk berbagai settings
    - Test adjustment handlers untuk delay dan parameter lain
    - Verifikasi tidak ada breaking changes
    - _Persyaratan: 4.2, 4.6_
  
  - [x] 7.3 Verifikasi semua fungsi existing di plugin xchatsanomlau masih berfungsi
    - Test laucreate_loop dengan berbagai parameter (jumlah grup, batch size, delay)
    - Test control handlers (pause, resume, stop) dengan berbagai state
    - Verifikasi backward compatibility dengan kode existing
    - _Persyaratan: 4.3, 4.6_
  
  - [x]* 7.4 Tulis property test untuk backward compatibility
    - **Property 11: Backward Compatibility Preserved**
    - **Memvalidasi: Persyaratan 4.1, 4.2, 4.3, 4.6**
    - Test semua method, handler, dan fungsi existing dengan berbagai input
    - Verifikasi signature dan behavior tetap sama
    - Minimum 100 iterasi per test

- [x] 8. Checkpoint - Pastikan semua test backward compatibility pass
  - Pastikan semua test pass, tanyakan user jika ada pertanyaan.

- [x] 9. Update string lokalisasi
  - [x] 9.1 Tambahkan string untuk auto-delete command di en.yml
    - Tambahkan auto_delete_cmd: "Auto-Delete Command"
    - Tambahkan auto_delete_cmd_desc: "Automatically delete command messages after execution"
    - Tambahkan auto_delete_enabled: "Auto-Delete: ENABLED"
    - Tambahkan auto_delete_disabled: "Auto-Delete: DISABLED"
    - Tambahkan auto_delete_delay: "Delay: {}s"
    - _Persyaratan: 5.1_
  
  - [x] 9.2 Tambahkan string untuk auto-delete command di id.yml
    - Terjemahkan auto_delete_cmd: "Hapus Otomatis Command"
    - Terjemahkan auto_delete_cmd_desc: "Hapus pesan command secara otomatis setelah eksekusi"
    - Terjemahkan auto_delete_enabled: "Hapus Otomatis: AKTIF"
    - Terjemahkan auto_delete_disabled: "Hapus Otomatis: NONAKTIF"
    - Terjemahkan auto_delete_delay: "Delay: {}d"
    - _Persyaratan: 5.1, 5.6_
  
  - [x] 9.3 Tambahkan string untuk notifikasi xchatsanomlau di en.yml
    - Tambahkan laucreate_started: "🚀 Laucreate Task Started"
    - Tambahkan laucreate_progress: "✅ Group {}/{} created successfully"
    - Tambahkan laucreate_batch_report: "✅ Batch {} completed: {} groups"
    - Tambahkan laucreate_completed: "✅ Laucreate Task Completed"
    - Tambahkan laucreate_error: "❌ Error creating group: {}"
    - Tambahkan laucreate_paused: "⏸️ Task paused"
    - Tambahkan laucreate_resumed: "▶️ Task resumed"
    - _Persyaratan: 5.2_
  
  - [x] 9.4 Tambahkan string untuk notifikasi xchatsanomlau di id.yml
    - Terjemahkan laucreate_started: "🚀 Task Laucreate Dimulai"
    - Terjemahkan laucreate_progress: "✅ Grup {}/{} berhasil dibuat"
    - Terjemahkan laucreate_batch_report: "✅ Batch {} selesai: {} grup"
    - Terjemahkan laucreate_completed: "✅ Task Laucreate Selesai"
    - Terjemahkan laucreate_error: "❌ Error membuat grup: {}"
    - Terjemahkan laucreate_paused: "⏸️ Task dijeda"
    - Terjemahkan laucreate_resumed: "▶️ Task dilanjutkan"
    - _Persyaratan: 5.2, 5.6_
  
  - [x]* 9.5 Tulis property test untuk kelengkapan lokalisasi
    - **Property 12: Kelengkapan String Lokalisasi**
    - **Memvalidasi: Persyaratan 5.1, 5.2, 5.6**
    - Verifikasi setiap key di en.yml ada di id.yml dan sebaliknya
    - Verifikasi tidak ada string hardcoded di kode
    - Minimum 100 iterasi per test
  
  - [x]* 9.6 Tulis property test untuk konsistensi format
    - **Property 13: Konsistensi Format String Lokalisasi**
    - **Memvalidasi: Persyaratan 5.3**
    - Verifikasi semua placeholder menggunakan format {} yang konsisten
    - Verifikasi jumlah placeholder sama di en.yml dan id.yml untuk key yang sama
    - Minimum 100 iterasi per test

- [x] 10. Checkpoint Final - Pastikan semua test pass dan tidak ada regresi
  - Jalankan semua test (unit + property) dengan pytest
  - Verifikasi tidak ada error atau warning
  - Verifikasi coverage mencakup semua fungsi yang dimodifikasi
  - Tanyakan user jika ada pertanyaan atau perlu review tambahan

## Catatan

- Task yang ditandai dengan `*` adalah optional dan dapat di-skip untuk MVP lebih cepat
- Setiap task mereferensikan persyaratan spesifik untuk traceability
- Checkpoint memastikan validasi incremental
- Property test menggunakan hypothesis library dengan minimum 100 iterasi
- Property test memvalidasi properti kebenaran universal
- Unit test memvalidasi contoh spesifik dan edge case
- Semua test menggunakan pytest sebagai test runner
- Tag format untuk property test: `Feature: perbaikan-auto-delete-dan-notifikasi, Property {number}: {property_text}`
