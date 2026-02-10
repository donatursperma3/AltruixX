# PowerShell script to fix id.yml localization
$filePath = "f:\2025\DESEMBER\altruix\AltruixX\Main\localization\id.yml"

# Read the file
$content = Get-Content $filePath -Raw -Encoding UTF8

# Define the Indonesian replacement text
$indonesianText = @"
  # Global Purgeme
  GPURGEME_TITLE: "🚮 <b>DASHBOARD GLOBAL PURGEME</b>"
  GP_ACCOUNT_INFO: "👤 <b>Akun:</b> {}"
  GP_TARGET: "🎯 <b>Target:</b> {}"
  GP_LIMIT: "🔢 <b>Batas:</b> {}"
  GP_DELAY: "⏱ <b>Jeda:</b> {}d"
  GP_MODE: "🔄 <b>Mode:</b> {}"
  GP_OFFSET: "⏩ <b>Offset:</b> {}"
  GP_FILTERS: "🔍 <b>Filter:</b> {}"
  GP_IGNORE_ADMIN: "👑 <b>Abaikan Admin:</b> {}"
  GP_NOTIF: "🔔 <b>Notif:</b> {}"
  
  GP_STATUS_IDLE: "💤 <b>Status:</b> <code>Diam / Siap</code>"
  GP_STATUS_RUNNING: "🚀 <b>Status:</b> <code>Berjalan ({}/{})</code>"
  GP_STATUS_PAUSED: "⏸ <b>Status:</b> <code>Dijeda</code>"
  GP_STATUS_COMPLETED: "✅ <b>Status:</b> <code>Selesai</code>"
  
  GP_BTN_TARGET_ALL: "Semua"
  GP_BTN_TARGET_GROUPS: "Grup"
  GP_BTN_TARGET_PERSONAL: "Pribadi"
  GP_BTN_MODE_NEWEST: "Terbaru"
  GP_BTN_MODE_OLDEST: "Terlama"
  GP_BTN_RESET: "Reset"
  GP_BTN_NOTIF_ON: "Notif: ON"
  GP_BTN_NOTIF_OFF: "Notif: OFF"
  
  GP_BTN_ALL: "Semua"
  GP_BTN_IMG: "Gbr"
  GP_BTN_VID: "Vid"
  GP_BTN_TXT: "Teks"
  GP_BTN_AUD: "Aud"
  GP_BTN_STK: "Stk"
  GP_BTN_GIF: "Gif"
  GP_BTN_FILE: "File"
  GP_BTN_VN: "VN"
  
  GP_BTN_IGNORE_ADMIN: "Abaikan Admin"
  GP_BTN_LIST_CHATS: "📋 Daftar Chat"
  GP_BTN_START: "🚀 Mulai GPurgeme"
  GP_BTN_INFO: "ℹ️ Info"
  GP_BTN_PAUSE: "⏸ Jeda"
  GP_BTN_STOP: "🛑 Stop"
  GP_BTN_RESUME: "▶️ Lanjut"
  GP_BTN_BACK: "🔙 Kembali"
  
  GP_INFO_TEXT: "<b>Info Global Purgeme</b>\n\nAlat ini memungkinkan Anda menghapus pesan secara massal di banyak obrolan.\n\n• <b>Batas:</b> Pesan yang dihapus per obrolan.\n• <b>Jeda:</b> Waktu tunggu antar obrolan.\n• <b>Target:</b> Jenis obrolan yang dipindai.\n• <b>Filter:</b> Jenis pesan yang dihapus."
  GP_COMPLETED_MSG: "✅ <b>Global Purgeme Selesai!</b>\n\n<b>Chat Diproses:</b> {}\n<b>Pesan Dihapus:</b> {}\n<b>Waktu:</b> {}d\n\n<b>Detail:</b>\n<pre>{}</pre>"
  GP_LIST_CHATS_HEADER: "<b>Target Chat:</b>\n<i>(Total: {} | Diabaikan: {})</i>\n\n{}"

  # Session Info Buttons
  btn_gcast_user: "Gcast User"
  global_purgeme: "Global Purgeme"
"@

# Replace the English section with Indonesian
$pattern = '(?s)  # Global Purgeme.*?global_purgeme: "Global Purgeme"'
$content = $content -replace $pattern, $indonesianText

# Write back to file
$content | Set-Content $filePath -Encoding UTF8 -NoNewline

Write-Host "✅ id.yml has been fixed with Indonesian translations!" -ForegroundColor Green
