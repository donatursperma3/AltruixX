# Dokumen Persyaratan

## Pendahuluan

Spesifikasi ini mendefinisikan perbaikan dan peningkatan untuk Telegram userbot Pyrogram yang mencakup perbaikan fungsi auto-delete command, penambahan notifikasi progres untuk plugin xchatsanomlau, pengujian menyeluruh kode, dan pembaruan string lokalisasi.

## Glosarium

- **Userbot**: Bot Telegram yang berjalan menggunakan akun pengguna (bukan bot account)
- **Auto_Delete_CMD**: Fitur untuk menghapus pesan command secara otomatis setelah eksekusi
- **Plugin_xchatsanomlau**: Plugin untuk membuat grup/channel secara otomatis dengan konfigurasi lengkap
- **LOG_CHAT_ID**: ID chat untuk mengirim notifikasi dan log
- **Bot_Assistant**: Bot asisten yang digunakan untuk mengirim notifikasi
- **Localization**: File YAML yang berisi string teks dalam berbagai bahasa (en.yml, id.yml)
- **Settings_Handler**: Handler untuk mengatur konfigurasi auto-delete melalui callback query
- **Message_Type**: Tipe pesan Pyrogram yang telah di-extend dengan method custom

## Persyaratan

### Persyaratan 1: Perbaikan Fungsi Auto-Delete Command

**User Story:** Sebagai pengguna userbot, saya ingin pesan command saya dihapus secara otomatis setelah eksekusi ketika fitur auto-delete diaktifkan, sehingga chat tetap bersih dan tidak penuh dengan command.

#### Kriteria Penerimaan

1. WHEN auto-delete command status diset ke "on" untuk sebuah sesi, THEN THE System SHALL menghapus pesan command dari pengguna tersebut setelah eksekusi
2. WHEN auto-delete command type diset ke "global", THEN THE System SHALL menggunakan pengaturan AUTO_DELETE_CMD_GLOBAL untuk semua sesi
3. WHEN auto-delete command type diset ke "per_account", THEN THE System SHALL menggunakan pengaturan AUTO_DELETE_CMD_STATUS_{index} untuk sesi spesifik
4. WHEN delay auto-delete dikonfigurasi, THEN THE System SHALL menunggu sejumlah detik yang ditentukan sebelum menghapus pesan
5. IF pesan berasal dari sudo user, THEN THE System SHALL NOT menghapus pesan tersebut
6. IF pesan berasal dari userbot sendiri (self message), THEN THE System SHALL menghapus pesan sesuai pengaturan auto-delete
7. WHEN pengaturan auto-delete tidak ditemukan atau bernilai "off", THEN THE System SHALL NOT menghapus pesan command

### Persyaratan 2: Notifikasi Progres Plugin xchatsanomlau

**User Story:** Sebagai pengguna yang menjalankan task laucreate, saya ingin menerima notifikasi progres di PM (Private Message) melalui bot assistant, sehingga saya dapat memantau status pembuatan grup tanpa harus membuka log group.

#### Kriteria Penerimaan

1. WHEN task laucreate dimulai, THEN THE System SHALL mengirim notifikasi awal ke PM user (via bot assistant) DAN ke LOG_CHAT_ID
2. WHEN setiap grup berhasil dibuat, THEN THE System SHALL mengirim notifikasi progres ke PM user (via bot assistant) DAN ke LOG_CHAT_ID dengan detail grup
3. WHEN batch grup selesai dibuat, THEN THE System SHALL mengirim laporan batch ke PM user (via bot assistant) DAN ke LOG_CHAT_ID
4. WHEN task laucreate selesai, THEN THE System SHALL mengirim laporan lengkap dengan file log ke PM user (via bot assistant) DAN ke LOG_CHAT_ID
5. WHEN error terjadi selama pembuatan grup, THEN THE System SHALL mengirim notifikasi error ke PM user (via bot assistant) DAN ke LOG_CHAT_ID
6. WHEN task di-pause atau di-resume, THEN THE System SHALL mengirim notifikasi status ke PM user (via bot assistant) DAN ke LOG_CHAT_ID
7. THE System SHALL menggunakan bot assistant untuk mengirim semua notifikasi ke PM user DAN LOG_CHAT_ID

### Persyaratan 3: Pengujian Menyeluruh Kode

**User Story:** Sebagai developer, saya ingin memastikan semua kode berfungsi dengan benar tanpa error dan logic yang salah, sehingga userbot dapat berjalan stabil dan reliable.

#### Kriteria Penerimaan

1. WHEN kode dijalankan, THEN THE System SHALL NOT menghasilkan syntax error
2. WHEN method delete_if_self dipanggil, THEN THE System SHALL mengeksekusi logic auto-delete dengan benar
3. WHEN settings handler dipanggil, THEN THE System SHALL membaca dan menulis konfigurasi ke database dengan benar
4. WHEN plugin xchatsanomlau dijalankan, THEN THE System SHALL mengirim notifikasi tanpa error
5. IF exception terjadi, THEN THE System SHALL menangani exception dengan graceful dan log error dengan level yang sesuai
6. THE System SHALL memvalidasi semua parameter input sebelum digunakan
7. THE System SHALL menggunakan try-except block untuk operasi yang berpotensi error

### Persyaratan 4: Preservasi Fitur Existing

**User Story:** Sebagai pengguna userbot, saya ingin semua fitur yang sudah ada tetap berfungsi setelah update, sehingga tidak ada functionality yang hilang.

#### Kriteria Penerimaan

1. THE System SHALL mempertahankan semua method existing di Message class
2. THE System SHALL mempertahankan semua handler existing di cmd_settings_handlers.py
3. THE System SHALL mempertahankan semua fungsi existing di plugin xchatsanomlau
4. THE System SHALL mempertahankan backward compatibility dengan kode yang sudah ada
5. IF perubahan diperlukan, THEN THE System SHALL menggunakan pendekatan yang tidak breaking existing functionality
6. THE System SHALL mempertahankan semua parameter dan return value dari fungsi existing

### Persyaratan 5: Update String Lokalisasi

**User Story:** Sebagai pengguna yang menggunakan bahasa Indonesia, saya ingin semua string teks sesuai dengan fitur yang ada, sehingga UI konsisten dan mudah dipahami.

#### Kriteria Penerimaan

1. THE System SHALL memiliki string lokalisasi untuk semua fitur auto-delete command di en.yml dan id.yml
2. THE System SHALL memiliki string lokalisasi untuk semua notifikasi plugin xchatsanomlau di en.yml dan id.yml
3. THE System SHALL menggunakan format yang konsisten untuk semua string lokalisasi
4. THE System SHALL menyediakan string untuk semua tombol UI yang terkait dengan fitur auto-delete
5. THE System SHALL menyediakan string untuk semua pesan notifikasi plugin xchatsanomlau
6. IF string baru ditambahkan, THEN THE System SHALL menambahkannya ke kedua file lokalisasi (en.yml dan id.yml)
7. THE System SHALL memastikan tidak ada string yang hardcoded di kode, semua harus menggunakan Altruix.get_string()
