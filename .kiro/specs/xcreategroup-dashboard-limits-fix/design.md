# xcreategroup-dashboard-limits-fix Bugfix Design

## Overview

Terdapat 3 bug validasi limit pada dashboard Interactive UI plugin `xcreategroup` di file
`Main/internals/settings_handlers/creategroup_handlers.py`. Bug-bug ini mencegah pengguna
mengatur nilai yang seharusnya valid:

- **BUG 1** — `account_delay` tidak bisa di-set ke `0` (minimum salah: `0.1`)
- **BUG 2** — `batch_account` tidak bisa di-set lebih dari `100` (maksimum salah: `100`, seharusnya `1000`)
- **BUG 3** — `ba_account_delay` tidak bisa di-set ke `0` (minimum salah: `5`)

Ketiga bug ini berdampak pada **tiga titik kode** yang saling terkait:
1. Dict `limits` di `creategroup_adjust_handler` — menentukan batas clamp nilai
2. List `adj_steps` di `get_creategroup_ui_data` — menentukan tombol keypad sub-menu
3. Branch `elif field in [...]` di `process_CG` — menentukan field mana yang diproses saat manual input

Fix bersifat minimal dan targeted: hanya mengubah nilai batas dan menambahkan field ke branch
yang sudah ada, tanpa mengubah arsitektur atau alur logika yang ada.

---

## Glossary

- **Bug_Condition (C)**: Kondisi yang memicu bug — ketika nilai yang seharusnya valid ditolak
  oleh sistem validasi
- **Property (P)**: Perilaku yang diharapkan setelah fix — nilai valid diterima dan disimpan
  dengan benar
- **Preservation**: Perilaku yang tidak boleh berubah — validasi field lain, format penyimpanan,
  dan semua fitur dashboard lainnya tetap identik
- **`creategroup_adjust_handler`**: Handler callback di `creategroup_handlers.py` yang memproses
  tombol `+`/`-` pada keypad sub-menu; menggunakan dict `limits` untuk clamp nilai
- **`get_creategroup_ui_data`**: Fungsi yang membangun teks dan markup keyboard dashboard;
  menggunakan `adj_steps` untuk menentukan tombol keypad per field
- **`process_CG`**: Message handler yang memproses input teks manual dari pengguna saat
  `state["step"] == "awaiting_input"`; menggunakan branch `elif field in [...]` untuk
  menentukan field mana yang diproses
- **`limits` dict**: Dict `{"field": (min, max)}` di `creategroup_adjust_handler` yang
  digunakan untuk clamp nilai setelah operasi `+`/`-`
- **`adj_steps`**: List step yang digunakan untuk membangun tombol keypad `+`/`-` di sub-menu
- **`applyLimit`**: Operasi clamp `max(min_v, min(val, max_v))` yang diterapkan di
  `creategroup_adjust_handler`

---

## Bug Details

### Bug Condition

Bug terjadi ketika pengguna mencoba mengatur nilai `account_delay` ke `0`, `ba_account_delay`
ke `0`, atau `batch_account` ke nilai antara `101`–`1000`. Sistem menolak nilai-nilai ini
karena batas yang salah di tiga titik kode.

**Formal Specification:**

```
FUNCTION isBugCondition(field, value)
  INPUT: field of type string, value of type number
  OUTPUT: boolean

  RETURN (field = "account_delay"    AND value = 0)
      OR (field = "ba_account_delay" AND value = 0)
      OR (field = "batch_account"    AND value > 100 AND value <= 1000)
END FUNCTION
```

### Examples

**BUG 1 — `account_delay`:**
- Input: tekan `-0.25` saat nilai `0.25` → Expected: `0`, Actual: `0.1` (di-clamp oleh `limits`)
- Input: ketik `0` manual untuk `account_delay` → Expected: disimpan sebagai `0`, Actual:
  diterima oleh branch `elif field in ["delay", ..., "account_delay"]` tapi kemudian
  di-clamp ke `0.1` jika diubah via keypad setelahnya (inkonsistensi)

**BUG 2 — `batch_account`:**
- Input: tekan `+10` saat nilai `100` → Expected: `110`, Actual: `100` (di-clamp oleh `limits`)
- Input: ketik `500` manual untuk `batch_account` → Expected: disimpan sebagai `500`, Actual:
  jatuh ke branch `else` (unrecognized field) karena `batch_account` tidak ada di list field
  yang diproses manual input handler

**BUG 3 — `ba_account_delay`:**
- Input: tekan `-5` saat nilai `5` → Expected: `0`, Actual: `5` (di-clamp oleh `limits`)
- Input: ketik `0` manual untuk `ba_account_delay` → Expected: disimpan sebagai `0`, Actual:
  jatuh ke branch `else` (unrecognized field) karena `ba_account_delay` tidak ada di list
  field yang diproses manual input handler

---

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Validasi field `delay`, `count`, `batch_delay`, `batch_size`, `action_delay`, `batch_action`,
  `ba_delay`, `rand_len` harus tetap menggunakan limit yang sama tanpa perubahan
- Field `action_delay` tetap memiliki minimum `0.1` (field ini tidak termasuk bugfix)
- Format penyimpanan ke `xcreategroup_user_configs.json` tetap menggunakan atomic write via
  `.tmp` file tanpa perubahan struktur JSON
- Semua fitur dashboard lain (toggle, session select, task management, creation reports,
  restore tasks) tetap berfungsi tanpa perubahan
- Tombol keypad `+`/`-` untuk field yang tidak diubah tetap menghasilkan step yang sama
- Nilai `batch_account` antara `1`–`100` tetap diterima dan disimpan dengan benar
- Nilai `account_delay` positif (misalnya `0.5`, `1.0`, `3.0`) tetap diterima dan disimpan
  dengan benar
- Nilai `ba_account_delay` positif (misalnya `10`, `30`, `60`) tetap diterima dan disimpan
  dengan benar

**Scope:**
Semua input yang TIDAK memenuhi `isBugCondition` harus sepenuhnya tidak terpengaruh oleh fix
ini. Fix hanya mengubah nilai batas dan menambahkan field ke branch yang sudah ada.

---

## Hypothesized Root Cause

Berdasarkan analisis kode, penyebab bug adalah:

1. **Nilai batas salah di `limits` dict** (titik utama):
   - `"account_delay": (0.1, 30.0)` — minimum `0.1` seharusnya `0`
   - `"batch_account": (1, 100)` — maksimum `100` seharusnya `1000`
   - `"ba_account_delay": (5, 3600)` — minimum `5` seharusnya `0`
   - Ini menyebabkan operasi clamp `max(min_v, min(val, max_v))` menolak nilai yang valid

2. **`adj_steps` tidak mencakup step yang bisa mencapai 0** (titik kedua):
   - `account_delay` menggunakan `adj_steps = [0.25, 0.5, 1, 3, 5]` — step terkecil `0.25`
     dari nilai `0.25` menghasilkan `0`, tapi ini di-clamp ke `0.1` oleh `limits`
     (setelah fix `limits`, ini sudah cukup untuk mencapai `0`)
   - `ba_account_delay` menggunakan `adj_steps = [5, 10, 30, 60, 120, 300]` — step terkecil
     `5` dari nilai `5` menghasilkan `0`, tapi ini di-clamp ke `5` oleh `limits`
     (setelah fix `limits`, ini sudah cukup untuk mencapai `0`)
   - Tidak perlu mengubah `adj_steps` setelah `limits` diperbaiki, karena step yang ada
     sudah bisa mencapai `0` secara matematis

3. **Field `batch_account` dan `ba_account_delay` tidak ada di branch manual input handler**
   (titik ketiga):
   - Branch `elif field in ["delay", "count", "batch_delay", "batch_size", "action_delay", "account_delay"]`
     tidak mencakup `batch_account` dan `ba_account_delay`
   - Input untuk field-field ini jatuh ke branch `else` dan diabaikan dengan log error
   - Perlu menambahkan kedua field ini ke branch yang sesuai

---

## Correctness Properties

Property 1: Bug Condition — Zero-floor Valid for account_delay and ba_account_delay

_For any_ input di mana `isBugCondition_ZeroFloor(field, value)` bernilai `True` (yaitu
`field = "account_delay"` atau `field = "ba_account_delay"` dengan `value = 0`), fungsi
`creategroup_adjust_handler` yang sudah diperbaiki SHALL menyimpan nilai `0` ke config
tanpa di-clamp ke nilai minimum yang lebih tinggi.

**Validates: Requirements 2.1, 2.2, 2.3, 2.6, 2.7, 2.8**

Property 2: Bug Condition — Upper Bound 1000 Valid for batch_account

_For any_ input di mana `isBugCondition_UpperBound(field, value)` bernilai `True` (yaitu
`field = "batch_account"` dengan `value > 100` dan `value <= 1000`), fungsi
`creategroup_adjust_handler` yang sudah diperbaiki SHALL menyimpan nilai tersebut ke config
tanpa di-clamp ke `100`.

**Validates: Requirements 2.4, 2.5**

Property 3: Preservation — Non-buggy Inputs Unchanged

_For any_ input di mana `isBugCondition` bernilai `False` (semua field dan nilai lain yang
tidak termasuk kondisi bug), fungsi `creategroup_adjust_handler` dan `process_CG` yang sudah
diperbaiki SHALL menghasilkan hasil yang identik dengan versi aslinya, mempertahankan semua
perilaku validasi yang sudah ada.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7**

---

## Fix Implementation

### Changes Required

#### Change 1: Fix `limits` dict di `creategroup_adjust_handler`

**File**: `Main/internals/settings_handlers/creategroup_handlers.py`

**Function**: `creategroup_adjust_handler`

**Location**: ~line 1027 (dict `limits` di dalam fungsi)

**Before:**
```python
limits = {
    "delay": (1, 3600), "count": (1, 1000), "batch_delay": (0, 300),
    "batch_size": (1, 100), "action_delay": (0.1, 30.0),
    "account_delay": (0.1, 30.0),   # ← BUG: min 0.1, seharusnya 0
    "rand_len": (0, 64), "batch_action": (1, 500), "ba_delay": (10, 3600),
    "batch_account": (1, 100),       # ← BUG: max 100, seharusnya 1000
    "ba_account_delay": (5, 3600)    # ← BUG: min 5, seharusnya 0
}
```

**After:**
```python
limits = {
    "delay": (1, 3600), "count": (1, 1000), "batch_delay": (0, 300),
    "batch_size": (1, 100), "action_delay": (0.1, 30.0),
    "account_delay": (0, 30.0),      # ✅ FIX: min 0 (no delay allowed)
    "rand_len": (0, 64), "batch_action": (1, 500), "ba_delay": (10, 3600),
    "batch_account": (1, 1000),      # ✅ FIX: max 1000
    "ba_account_delay": (0, 3600)    # ✅ FIX: min 0 (no delay allowed)
}
```

**Catatan**: Perubahan ini otomatis memperbaiki perilaku keypad `+`/`-` karena operasi clamp
`max(min_v, min(val, max_v))` akan menggunakan batas yang benar. Tidak perlu mengubah
`adj_steps` karena step yang ada sudah bisa mencapai `0` secara matematis setelah batas
diperbaiki.

---

#### Change 2: Fix branch manual input handler di `process_CG`

**File**: `Main/internals/settings_handlers/creategroup_handlers.py`

**Function**: `process_CG` (message handler)

**Location**: ~line 2054 (branch `elif field in [...]`)

**Before:**
```python
elif field in ["delay", "count", "batch_delay", "batch_size", "action_delay", "account_delay"]:
    is_float_field = field in ["action_delay", "account_delay"]
    if text.isdigit() or (is_float_field and text.replace(".", "", 1).isdigit()):
         val = float(text) if is_float_field else int(text)
         state["config"][field] = val
         dl.info(f"[DEBUG-CG] Field '{field}' successfully updated to integer/float {val}.")
    else:
         dl.warning(f"[DEBUG-CG] Input for '{field}' was rejected due to non-digit: '{text}'")
         await m.reply("❌ Input harus angka!")
         return
else:
     dl.error(f"[DEBUG-CG] WARNING: Unrecognized field mode: '{field}'")
```

**After:**
```python
elif field in ["delay", "count", "batch_delay", "batch_size", "action_delay", "account_delay",
               "batch_account", "ba_account_delay"]:
    is_float_field = field in ["action_delay", "account_delay"]
    if text.isdigit() or (is_float_field and text.replace(".", "", 1).isdigit()):
         val = float(text) if is_float_field else int(text)
         # Apply limits validation
         limits = {
             "delay": (1, 3600), "count": (1, 1000), "batch_delay": (0, 300),
             "batch_size": (1, 100), "action_delay": (0.1, 30.0),
             "account_delay": (0, 30.0), "batch_account": (1, 1000),
             "ba_account_delay": (0, 3600)
         }
         if field in limits:
             min_v, max_v = limits[field]
             val = max(min_v, min(val, max_v))
         state["config"][field] = val
         dl.info(f"[DEBUG-CG] Field '{field}' successfully updated to integer/float {val}.")
    else:
         dl.warning(f"[DEBUG-CG] Input for '{field}' was rejected due to non-digit: '{text}'")
         await m.reply("❌ Input harus angka!")
         return
else:
     dl.error(f"[DEBUG-CG] WARNING: Unrecognized field mode: '{field}'")
```

**Catatan perubahan**:
- Menambahkan `"batch_account"` dan `"ba_account_delay"` ke list field yang diproses
- Menambahkan validasi limit inline agar nilai yang diinput manual juga di-clamp sesuai batas
  yang benar (konsisten dengan `creategroup_adjust_handler`)
- `batch_account` dan `ba_account_delay` adalah integer field (tidak ada di `is_float_field`),
  sehingga `text.isdigit()` sudah cukup untuk validasi format

---

## Testing Strategy

### Validation Approach

Strategi testing mengikuti dua fase: pertama, verifikasi bug ada di kode yang belum diperbaiki
(exploratory), kemudian verifikasi fix bekerja dan tidak merusak perilaku yang ada (fix +
preservation checking).

### Exploratory Bug Condition Checking

**Goal**: Konfirmasi bug ada sebelum fix diterapkan. Verifikasi root cause analysis.

**Test Plan**: Simulasikan operasi `+`/`-` pada keypad dan input manual untuk field yang
bermasalah, lakukan pada kode SEBELUM fix.

**Test Cases**:
1. **account_delay zero test**: Set `account_delay = 0.25`, tekan `-0.25` → Expected `0`,
   Actual `0.1` (akan gagal pada kode unfixed)
2. **batch_account upper test**: Set `batch_account = 100`, tekan `+10` → Expected `110`,
   Actual `100` (akan gagal pada kode unfixed)
3. **ba_account_delay zero test**: Set `ba_account_delay = 5`, tekan `-5` → Expected `0`,
   Actual `5` (akan gagal pada kode unfixed)
4. **Manual input batch_account test**: Set `input_mode = "batch_account"`, kirim `"500"` →
   Expected disimpan sebagai `500`, Actual jatuh ke branch `else` (akan gagal pada kode unfixed)
5. **Manual input ba_account_delay test**: Set `input_mode = "ba_account_delay"`, kirim `"0"` →
   Expected disimpan sebagai `0`, Actual jatuh ke branch `else` (akan gagal pada kode unfixed)

**Expected Counterexamples**:
- Nilai `account_delay` di-clamp ke `0.1` bukan `0`
- Nilai `batch_account` di-clamp ke `100` bukan nilai yang diinput
- Nilai `ba_account_delay` di-clamp ke `5` bukan `0`
- Field `batch_account` dan `ba_account_delay` tidak diproses di manual input handler

### Fix Checking

**Goal**: Verifikasi bahwa untuk semua input di mana bug condition berlaku, fungsi yang sudah
diperbaiki menghasilkan perilaku yang benar.

**Pseudocode:**
```
FOR ALL (field, value) WHERE isBugCondition(field, value) DO
  result := applyLimit_fixed(field, value)
  ASSERT result = value  // nilai tidak di-clamp ke batas yang salah
END FOR
```

### Preservation Checking

**Goal**: Verifikasi bahwa untuk semua input di mana bug condition TIDAK berlaku, fungsi yang
sudah diperbaiki menghasilkan hasil yang identik dengan fungsi asli.

**Pseudocode:**
```
FOR ALL (field, value) WHERE NOT isBugCondition(field, value) DO
  ASSERT applyLimit_original(field, value) = applyLimit_fixed(field, value)
END FOR
```

**Testing Approach**: Property-based testing direkomendasikan untuk preservation checking karena:
- Menghasilkan banyak test case secara otomatis di seluruh domain input
- Menangkap edge case yang mungkin terlewat oleh unit test manual
- Memberikan jaminan kuat bahwa perilaku tidak berubah untuk semua input non-buggy

**Test Cases**:
1. **action_delay preservation**: Verifikasi `action_delay` masih memiliki minimum `0.1`
   setelah fix (field ini tidak diubah)
2. **delay/count/batch_size preservation**: Verifikasi field-field ini masih menggunakan
   limit yang sama setelah fix
3. **batch_account 1-100 preservation**: Verifikasi nilai `1`–`100` untuk `batch_account`
   masih diterima dan disimpan dengan benar
4. **account_delay positive preservation**: Verifikasi nilai positif `account_delay` (misalnya
   `0.5`, `1.0`, `3.0`) masih diterima dan disimpan dengan benar
5. **ba_account_delay positive preservation**: Verifikasi nilai positif `ba_account_delay`
   (misalnya `10`, `30`, `60`) masih diterima dan disimpan dengan benar

### Unit Tests

- Test `creategroup_adjust_handler` dengan `account_delay = 0.25`, action `sub0.25` →
  verifikasi hasil `0`
- Test `creategroup_adjust_handler` dengan `batch_account = 100`, action `add10` →
  verifikasi hasil `110`
- Test `creategroup_adjust_handler` dengan `ba_account_delay = 5`, action `sub5` →
  verifikasi hasil `0`
- Test `process_CG` dengan `field = "batch_account"`, input `"500"` → verifikasi disimpan
  sebagai `500`
- Test `process_CG` dengan `field = "ba_account_delay"`, input `"0"` → verifikasi disimpan
  sebagai `0`
- Test `process_CG` dengan `field = "batch_account"`, input `"1500"` → verifikasi di-clamp
  ke `1000`
- Test edge case: `account_delay = 0`, action `sub0.25` → verifikasi tetap `0` (tidak negatif)

### Property-Based Tests

- Generate random `account_delay` values in `[0, 30.0]` → verifikasi semua diterima oleh
  `applyLimit_fixed` tanpa perubahan
- Generate random `batch_account` values in `[1, 1000]` → verifikasi semua diterima oleh
  `applyLimit_fixed` tanpa perubahan
- Generate random `ba_account_delay` values in `[0, 3600]` → verifikasi semua diterima oleh
  `applyLimit_fixed` tanpa perubahan
- Generate random values untuk field yang tidak diubah (`delay`, `count`, `action_delay`, dll.)
  → verifikasi `applyLimit_original(field, value) = applyLimit_fixed(field, value)`

### Integration Tests

- Test full flow: buka sub-menu `account_delay`, tekan `-` hingga `0`, verifikasi UI
  menampilkan `0` dan config tersimpan dengan benar
- Test full flow: buka sub-menu `batch_account`, tekan `+10` dari `100`, verifikasi UI
  menampilkan `110` dan config tersimpan dengan benar
- Test full flow: input manual `0` untuk `ba_account_delay`, verifikasi config tersimpan
  sebagai `0` dan UI diperbarui
- Test bahwa perubahan config tersimpan ke `xcreategroup_user_configs.json` dengan format
  yang benar setelah fix
