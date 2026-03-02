# Dokumen Persyaratan: Format Startup Log dengan Blockquote Expandable

## Pendahuluan

Spesifikasi ini mendefinisikan perubahan format pesan startup log dari format plain text menjadi format blockquote expandable (spoiler) agar tampilan lebih rapi, ringkas, dan mudah dibaca di Telegram.

## Glosarium

- **Startup Log**: Pesan log yang dikirim saat userbot selesai melakukan startup/initialization
- **Blockquote Expandable**: Format pesan Telegram yang menggunakan tag `<blockquote expandable>` untuk membuat konten yang dapat di-expand/collapse
- **LOG_CHAT_ID**: ID chat untuk mengirim notifikasi dan log
- **Client Statistics**: Informasi tentang jumlah session yang berhasil/gagal startup
- **System Statistics**: Informasi tentang penggunaan CPU, RAM, uptime, dll
- **Resource Warning**: Peringatan ketika resource sistem (CPU/RAM) mencapai threshold tertentu

## Persyaratan

### Persyaratan 1: Format Blockquote Expandable untuk Startup Log

**User Story:** Sebagai pengguna userbot, saya ingin pesan startup log ditampilkan dalam format blockquote expandable, sehingga tampilan lebih rapi dan tidak memenuhi chat dengan teks panjang.

#### Kriteria Penerimaan

1.1. WHEN startup log dikirim, THEN THE System SHALL menggunakan format `<blockquote expandable>` untuk membungkus konten log

1.2. THE System SHALL menampilkan header singkat di luar blockquote sebagai preview

1.3. THE System SHALL menempatkan detail lengkap (statistics, warnings) di dalam blockquote expandable

1.4. THE System SHALL menggunakan HTML formatting untuk mempertahankan struktur dan emoji

1.5. THE System SHALL memastikan blockquote dapat di-expand/collapse oleh user

### Persyaratan 2: Struktur Pesan yang Jelas

**User Story:** Sebagai pengguna, saya ingin pesan startup log memiliki struktur yang jelas dengan section yang terorganisir, sehingga mudah dibaca dan dipahami.

#### Kriteria Penerimaan

2.1. THE System SHALL menampilkan ringkasan startup di header (di luar blockquote)

2.2. THE System SHALL mengelompokkan informasi ke dalam section yang jelas:
   - Client Statistics (Total session, success, failed)
   - System Information (Owner ID, Branch, Database, Version, Time)
   - System Statistics (CPU, RAM, Process, Uptime, Platform)
   - Resource Warnings (jika ada)

2.3. THE System SHALL menggunakan separator atau spacing yang konsisten antar section

2.4. THE System SHALL menggunakan emoji yang konsisten untuk setiap jenis informasi

2.5. THE System SHALL mempertahankan semua informasi yang ada di format lama

### Persyaratan 3: Kompatibilitas dengan Telegram HTML

**User Story:** Sebagai sistem, saya ingin memastikan format HTML yang digunakan kompatibel dengan Telegram API, sehingga pesan dapat dikirim tanpa error.

#### Kriteria Penerimaan

3.1. THE System SHALL menggunakan tag HTML yang didukung oleh Telegram:
   - `<blockquote expandable>` untuk expandable section
   - `<b>` untuk bold text
   - `<code>` untuk monospace text
   - `<pre>` untuk preformatted text (jika diperlukan)

3.2. THE System SHALL escape special HTML characters (&, <, >) jika ada dalam data

3.3. THE System SHALL menggunakan `parse_mode="html"` saat mengirim pesan

3.4. THE System SHALL handle error jika format tidak didukung dan fallback ke format plain text

### Persyaratan 4: Conditional Resource Warning Display

**User Story:** Sebagai pengguna, saya ingin resource warning hanya ditampilkan jika ada masalah, sehingga tidak menampilkan warning yang tidak perlu.

#### Kriteria Penerimaan

4.1. WHEN CPU usage >= threshold (misal 80%), THEN THE System SHALL menampilkan CPU warning

4.2. WHEN RAM usage >= threshold (misal 80%), THEN THE System SHALL menampilkan RAM warning

4.3. WHEN tidak ada warning, THEN THE System SHALL NOT menampilkan section resource warning

4.4. THE System SHALL menampilkan warning dengan format yang jelas dan actionable

4.5. THE System SHALL menggunakan emoji yang sesuai untuk warning (⚠️, ‼️)

### Persyaratan 5: Backward Compatibility

**User Story:** Sebagai developer, saya ingin perubahan format tidak merusak fungsi existing, sehingga sistem tetap stabil setelah update.

#### Kriteria Penerimaan

5.1. THE System SHALL mempertahankan semua data yang ditampilkan di format lama

5.2. THE System SHALL mempertahankan logic untuk mengumpulkan statistics

5.3. THE System SHALL mempertahankan logic untuk mendeteksi resource warnings

5.4. IF blockquote expandable tidak didukung (Telegram versi lama), THEN THE System SHALL fallback ke format plain text

5.5. THE System SHALL tidak mengubah behavior pengiriman pesan (tetap ke LOG_CHAT_ID)

## Contoh Format

### Format Lama (Plain Text)
```
All clients finished sending startup logs!
Total Session: 2 user + 1 bot
Success: 3 clients
Failed: 0 clients
Owner ID: <owner_id>
Branch: antigravity_1.5.5.17 [0688960]
Database: LocalDB
Version: 0.0.10.0733H
Time: 28-02-2026 02:11:59

📊 SISTEM STATISTIK
• CPU: 18.5% (2 core/4 thread)
• RAM: 0.5GB/7.72GB (6.5%)
• Proses: N/AMB (N/A thread)
• Uptime: 3m:12s
• Platform: Linux | Python 3.12.3 | Pyrogram 2.2.19

⚠️ USERBOT RESOURCE WARNING
🖥 CPU Usage: 100.0%
‼️ Tindakan diperlukan:
Server Anda hampir mencapai kapasitas maksimal. Mohon periksa proses yang berjalan untuk menghindari crash atau restart tak terduga.
```

### Format Baru (Blockquote Expandable)
```html
<b>✅ All clients finished sending startup logs!</b>

<blockquote expandable>
<b>📊 Client Statistics</b>
• Total Session: 2 user + 1 bot
• Success: 3 clients
• Failed: 0 clients

<b>ℹ️ System Information</b>
• Owner ID: <code><owner_id></code>
• Branch: antigravity_1.5.5.17 [0688960]
• Database: LocalDB
• Version: 0.0.10.0733H
• Time: 28-02-2026 02:11:59

<b>📊 System Statistics</b>
• CPU: 18.5% (2 core/4 thread)
• RAM: 0.5GB/7.72GB (6.5%)
• Proses: N/AMB (N/A thread)
• Uptime: 3m:12s
• Platform: Linux | Python 3.12.3 | Pyrogram 2.2.19

<b>⚠️ Resource Warning</b>
🖥 CPU Usage: 100.0%
‼️ Tindakan diperlukan:
Server Anda hampir mencapai kapasitas maksimal. Mohon periksa proses yang berjalan untuk menghindai crash atau restart tak terduga.
</blockquote>
```

## Batasan dan Asumsi

### Batasan

1. Blockquote expandable hanya didukung di Telegram versi terbaru (Desktop 4.14+, Android 10.9+, iOS 10.9+)
2. HTML formatting memiliki batasan karakter (4096 untuk caption, unlimited untuk text message)
3. Tidak semua emoji ditampilkan dengan baik di semua platform

### Asumsi

1. User menggunakan Telegram versi yang mendukung blockquote expandable
2. LOG_CHAT_ID sudah dikonfigurasi dengan benar
3. Data statistics selalu tersedia saat startup log dikirim
4. Format HTML tidak akan di-sanitize oleh Telegram

## Prioritas

1. **P0 (Critical)**: Persyaratan 1 (Format blockquote expandable) - core feature
2. **P0 (Critical)**: Persyaratan 2 (Struktur pesan yang jelas) - untuk readability
3. **P1 (High)**: Persyaratan 3 (Kompatibilitas HTML) - untuk stability
4. **P2 (Medium)**: Persyaratan 4 (Conditional warning) - untuk cleaner output
5. **P2 (Medium)**: Persyaratan 5 (Backward compatibility) - untuk safety
