# Rencana Implementasi: Format Startup Log dengan Blockquote Expandable

## Gambaran Umum

Rencana implementasi ini mencakup perubahan format pesan startup log dari plain text menjadi blockquote expandable untuk tampilan yang lebih rapi dan terorganisir. Implementasi menggunakan Python dengan framework Pyrogram untuk Telegram userbot.

## Tasks

- [x] 1. Identifikasi lokasi kode startup log
  - [x] 1.1 Cari file yang mengirim startup log message
    - Search untuk string "All clients finished sending startup logs"
    - Identifikasi fungsi yang bertanggung jawab untuk format pesan
    - Dokumentasikan struktur kode existing
    - _Persyaratan: 5.1, 5.2, 5.3_
  
  - [x] 1.2 Analisis data yang dikumpulkan untuk startup log
    - Identifikasi variabel untuk client statistics
    - Identifikasi variabel untuk system information
    - Identifikasi variabel untuk system statistics
    - Identifikasi logic untuk resource warnings
    - _Persyaratan: 2.2, 2.5_

- [x] 2. Implementasi fungsi format blockquote expandable
  - [x] 2.1 Buat fungsi helper untuk format startup log
    - Buat fungsi `format_startup_log_blockquote()`
    - Accept parameters: client_stats, system_info, system_stats, warnings
    - Return formatted HTML string
    - _Persyaratan: 1.1, 1.4_
  
  - [x] 2.2 Implementasi header section (di luar blockquote)
    - Format: `<b>✅ All clients finished sending startup logs!</b>`
    - Gunakan bold untuk emphasis
    - Tambahkan newline setelah header
    - _Persyaratan: 1.2, 2.1_
  
  - [x] 2.3 Implementasi blockquote expandable wrapper
    - Gunakan tag `<blockquote expandable>`
    - Pastikan tag ditutup dengan `</blockquote>`
    - _Persyaratan: 1.1, 1.3, 1.5_
  
  - [x] 2.4 Implementasi Client Statistics section
    - Format header: `<b>📊 Client Statistics</b>`
    - Format items dengan bullet points (•)
    - Include: Total Session, Success, Failed
    - Tambahkan spacing setelah section
    - _Persyaratan: 2.2, 2.3, 2.4_
  
  - [x] 2.5 Implementasi System Information section
    - Format header: `<b>ℹ️ System Information</b>`
    - Format items dengan bullet points (•)
    - Include: Owner ID (dengan `<code>`), Branch, Database, Version, Time
    - Tambahkan spacing setelah section
    - _Persyaratan: 2.2, 2.3, 2.4_
  
  - [x] 2.6 Implementasi System Statistics section
    - Format header: `<b>📊 System Statistics</b>`
    - Format items dengan bullet points (•)
    - Include: CPU, RAM, Proses, Uptime, Platform
    - Tambahkan spacing setelah section
    - _Persyaratan: 2.2, 2.3, 2.4_
  
  - [x] 2.7 Implementasi Resource Warning section (conditional)
    - Check if warnings exist
    - Format header: `<b>⚠️ Resource Warning</b>`
    - Format warning message dengan emoji yang sesuai
    - Only add section if warnings exist
    - _Persyaratan: 2.2, 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 3. Implementasi HTML escaping dan validation
  - [x] 3.1 Add HTML escaping untuk special characters
    - Escape &, <, > dalam data dinamis
    - Gunakan `html.escape()` untuk Owner ID dan data lain
    - Pastikan tidak escape tag HTML yang valid
    - _Persyaratan: 3.2_
  
  - [x] 3.2 Validate HTML format
    - Pastikan semua tag dibuka dan ditutup dengan benar
    - Pastikan nested tags valid
    - Test dengan berbagai data input
    - _Persyaratan: 3.1, 3.3_

- [x] 4. Update kode pengiriman pesan
  - [x] 4.1 Replace format lama dengan format baru
    - Call fungsi `format_startup_log_blockquote()`
    - Pass semua data yang diperlukan
    - _Persyaratan: 1.1, 5.1_
  
  - [x] 4.2 Set parse_mode ke "html"
    - Pastikan `parse_mode="html"` digunakan saat send_message
    - _Persyaratan: 3.3_
  
  - [x] 4.3 Add error handling dan fallback
    - Wrap send_message dalam try-except
    - Catch error jika HTML format tidak didukung
    - Fallback ke format plain text jika error
    - Log error untuk debugging
    - _Persyaratan: 3.4, 5.4_

- [x] 5. Testing dan validasi
  - [x] 5.1 Test dengan berbagai skenario client statistics
    - Test dengan 0 failed clients
    - Test dengan beberapa failed clients
    - Test dengan berbagai jumlah total session
    - _Persyaratan: 2.5, 5.1_
  
  - [x] 5.2 Test dengan berbagai skenario system statistics
    - Test dengan CPU usage rendah, sedang, tinggi
    - Test dengan RAM usage rendah, sedang, tinggi
    - Test dengan berbagai platform (Linux, Windows)
    - _Persyaratan: 2.5, 5.1_
  
  - [x] 5.3 Test conditional resource warning
    - Test tanpa warning (CPU < 80%, RAM < 80%)
    - Test dengan CPU warning saja
    - Test dengan RAM warning saja
    - Test dengan kedua warning
    - _Persyaratan: 4.1, 4.2, 4.3_
  
  - [x] 5.4 Test HTML escaping
    - Test dengan Owner ID yang mengandung special characters
    - Test dengan data lain yang mungkin mengandung <, >, &
    - Verify tidak ada broken HTML
    - _Persyaratan: 3.2_
  
  - [x] 5.5 Test di Telegram client
    - Test di Telegram Desktop
    - Test di Telegram Android/iOS
    - Verify blockquote dapat di-expand/collapse
    - Verify formatting tampil dengan benar
    - _Persyaratan: 1.5, 2.3, 2.4_

- [ ] 6. Checkpoint - Verify format berfungsi dengan benar
  - Pastikan pesan terkirim tanpa error
  - Pastikan blockquote expandable berfungsi
  - Pastikan semua data ditampilkan dengan benar
  - Tanyakan user jika ada pertanyaan

- [x] 7. Code cleanup dan documentation
  - [x] 7.1 Add docstring untuk fungsi baru
    - Document parameters
    - Document return value
    - Add usage examples
    - _Persyaratan: 5.2_
  
  - [x] 7.2 Add inline comments untuk logic kompleks
    - Comment HTML formatting logic
    - Comment conditional warning logic
    - _Persyaratan: 5.2_
  
  - [x] 7.3 Remove atau comment out kode lama (jika ada)
    - Keep kode lama sebagai reference (commented)
    - Add comment menjelaskan perubahan
    - _Persyaratan: 5.1_

- [x] 8. Final verification
  - [x] 8.1 Verify backward compatibility
    - Pastikan semua data yang ditampilkan di format lama masih ada
    - Pastikan logic pengumpulan statistics tidak berubah
    - Pastikan behavior pengiriman pesan tidak berubah
    - _Persyaratan: 5.1, 5.2, 5.3, 5.5_
  
  - [x] 8.2 Test error handling
    - Test dengan LOG_CHAT_ID invalid
    - Test dengan network error
    - Verify fallback ke plain text berfungsi
    - _Persyaratan: 3.4, 5.4_
  
  - [x] 8.3 Final manual test
    - Restart userbot dan verify startup log
    - Check format di Telegram client
    - Verify semua section tampil dengan benar
    - Verify expandable berfungsi

## Catatan

- Semua tasks adalah required untuk implementasi lengkap
- Setiap task mereferensikan persyaratan spesifik untuk traceability
- Checkpoint memastikan validasi incremental
- Testing di actual Telegram client sangat penting untuk verify blockquote expandable
- Fallback ke plain text penting untuk kompatibilitas dengan Telegram versi lama
- HTML escaping critical untuk mencegah broken formatting
