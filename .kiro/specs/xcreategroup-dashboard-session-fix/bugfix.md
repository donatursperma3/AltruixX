# Bugfix Requirements Document

## Introduction

Bug terjadi pada tombol dashboard '🎛 Auto Create Configuration' di `xcreategroup.py` atau `creategroup_handlers.py`. Setelah program di-restart, menekan tombol tersebut menghasilkan error "session expired" karena state dictionary (`user_creategroup_state`) yang disimpan di memory hilang saat restart.

Bug ini mencegah pengguna mengakses dashboard konfigurasi setelah restart program, memaksa mereka untuk menjalankan ulang command dari awal.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN program di-restart dan user menekan tombol dashboard '🎛 Auto Create Configuration' THEN sistem menampilkan error "Session expired" dan tidak membuka dashboard

1.2 WHEN callback handler `creategroup_ui_handler` dipanggil dengan callback data `creategroup_ui_{session_index}_{page}` dan `user_id` tidak ada di `user_creategroup_state` dictionary THEN sistem langsung return dengan error message tanpa mencoba reinisialisasi state

1.3 WHEN inline query handler membuat dashboard button dengan callback data yang valid THEN button tersebut menjadi tidak berfungsi setelah program restart karena dependency pada in-memory state

### Expected Behavior (Correct)

2.1 WHEN program di-restart dan user menekan tombol dashboard '🎛 Auto Create Configuration' THEN sistem SHALL otomatis reinisialisasi state dan membuka dashboard konfigurasi dengan setting default atau tersimpan

2.2 WHEN callback handler `creategroup_ui_handler` dipanggil dan `user_id` tidak ada di `user_creategroup_state` dictionary THEN sistem SHALL membuat state baru dengan memanggil fungsi yang sama seperti di `show_creategroup_ui()` yang sudah handle missing state

2.3 WHEN state dictionary kosong atau tidak ada entry untuk user THEN sistem SHALL load konfigurasi user dari persistent storage (`load_user_cg_config`) dan membuat state entry baru dengan session_index dan page dari callback data

### Unchanged Behavior (Regression Prevention)

3.1 WHEN user menekan tombol dashboard dan state sudah ada di memory THEN sistem SHALL CONTINUE TO langsung render dashboard tanpa reinisialisasi

3.2 WHEN user menggunakan tombol adjustment lain (delay, count, batch_size, dll) yang juga check state THEN sistem SHALL CONTINUE TO berfungsi normal dengan state yang ada

3.3 WHEN program berjalan tanpa restart dan user berinteraksi dengan dashboard THEN sistem SHALL CONTINUE TO menggunakan state yang sudah ada di memory untuk performa optimal

3.4 WHEN konfigurasi user disimpan ke persistent storage THEN sistem SHALL CONTINUE TO menyimpan dengan format dan lokasi yang sama (`xcreategroup_user_configs.json`)

3.5 WHEN callback handler lain seperti `creategroup_cached_handler`, `creategroup_manual_handler` dipanggil THEN sistem SHALL CONTINUE TO berfungsi dengan logic yang sama
