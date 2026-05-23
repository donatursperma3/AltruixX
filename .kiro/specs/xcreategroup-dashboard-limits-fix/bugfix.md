# Bugfix Requirements Document

## Introduction

Terdapat 3 bug validasi limit pada dashboard Interactive UI plugin `xcreategroup` di file `creategroup_handlers.py`. Ketiga bug ini menyebabkan pengguna tidak dapat mengatur nilai tertentu yang seharusnya valid: `account_delay` dan `ba_account_delay` tidak bisa di-set ke `0` (tanpa delay), dan `batch_account` dibatasi maksimum 100 padahal seharusnya bisa lebih besar. Bug ini berdampak pada tiga titik: dict `limits` di `creategroup_adjust_handler`, list `adj_steps` di `get_creategroup_ui_data`, dan handler manual input di message handler.

---

## Bug Analysis

### Current Behavior (Defect)

**BUG 1 — `account_delay` tidak bisa di-set ke 0:**

1.1 WHEN pengguna menekan tombol `-` pada sub-menu keypad `account_delay` hingga nilai mendekati 0 THEN sistem membatasi nilai minimum ke `0.1` sehingga nilai `0` tidak dapat dicapai

1.2 WHEN pengguna menekan tombol step terkecil (`-0.25`) pada sub-menu keypad `account_delay` dari nilai `0.25` THEN sistem mengembalikan nilai `0.1` (bukan `0`) karena limit minimum adalah `0.1`

1.3 WHEN pengguna menginput nilai `0` secara manual untuk field `account_delay` THEN sistem menerima input (karena `"0".isdigit()` bernilai `True`) namun kemudian nilai di-clamp ke `0.1` oleh `creategroup_adjust_handler` — atau tidak diproses sama sekali karena field ini tidak ada di branch manual input handler

**BUG 2 — `batch_account` tidak bisa di-set lebih dari 100:**

2.1 WHEN pengguna menekan tombol `+` pada sub-menu keypad `batch_account` saat nilai sudah mencapai `100` THEN sistem membatasi nilai maksimum ke `100` sehingga nilai di atas 100 tidak dapat dicapai

2.2 WHEN pengguna menginput nilai lebih dari `100` secara manual untuk field `batch_account` THEN field ini tidak ada di branch manual input handler sehingga input jatuh ke branch `else` dan diabaikan (unrecognized field)

**BUG 3 — `ba_account_delay` tidak bisa di-set ke 0:**

3.1 WHEN pengguna menekan tombol `-` pada sub-menu keypad `ba_account_delay` hingga nilai mendekati 0 THEN sistem membatasi nilai minimum ke `5` sehingga nilai `0` tidak dapat dicapai

3.2 WHEN pengguna menekan tombol step terkecil (`-5`) pada sub-menu keypad `ba_account_delay` dari nilai `5` THEN sistem mengembalikan nilai `5` (tidak berubah) karena limit minimum adalah `5`

3.3 WHEN pengguna menginput nilai `0` secara manual untuk field `ba_account_delay` THEN field ini tidak ada di branch manual input handler sehingga input jatuh ke branch `else` dan diabaikan (unrecognized field)

---

### Expected Behavior (Correct)

**BUG 1 — `account_delay` harus bisa di-set ke 0:**

2.1 WHEN pengguna menekan tombol `-` pada sub-menu keypad `account_delay` hingga nilai mencapai `0` THEN sistem SHALL mengizinkan nilai `0` sebagai nilai minimum yang valid (artinya tidak ada delay antar akun)

2.2 WHEN pengguna menekan tombol step terkecil (`-0.25`) pada sub-menu keypad `account_delay` dari nilai `0.25` THEN sistem SHALL mengembalikan nilai `0` (bukan `0.1`)

2.3 WHEN pengguna menginput nilai `0` secara manual untuk field `account_delay` THEN sistem SHALL menerima dan menyimpan nilai `0` sebagai konfigurasi yang valid

**BUG 2 — `batch_account` harus bisa di-set hingga 1000:**

2.4 WHEN pengguna menekan tombol `+` pada sub-menu keypad `batch_account` saat nilai sudah mencapai `100` THEN sistem SHALL mengizinkan nilai di atas 100 hingga maksimum `1000`

2.5 WHEN pengguna menginput nilai antara `101` hingga `1000` secara manual untuk field `batch_account` THEN sistem SHALL menerima dan menyimpan nilai tersebut sebagai konfigurasi yang valid

**BUG 3 — `ba_account_delay` harus bisa di-set ke 0:**

2.6 WHEN pengguna menekan tombol `-` pada sub-menu keypad `ba_account_delay` hingga nilai mencapai `0` THEN sistem SHALL mengizinkan nilai `0` sebagai nilai minimum yang valid (artinya tidak ada delay antar batch akun)

2.7 WHEN pengguna menekan tombol step terkecil pada sub-menu keypad `ba_account_delay` dari nilai yang kecil THEN sistem SHALL dapat mencapai nilai `0`

2.8 WHEN pengguna menginput nilai `0` secara manual untuk field `ba_account_delay` THEN sistem SHALL menerima dan menyimpan nilai `0` sebagai konfigurasi yang valid

---

### Unchanged Behavior (Regression Prevention)

3.1 WHEN pengguna mengatur `account_delay` ke nilai positif (misalnya `0.5`, `1`, `3`) THEN sistem SHALL CONTINUE TO menyimpan dan menerapkan nilai tersebut dengan benar

3.2 WHEN pengguna mengatur `batch_account` ke nilai antara `1` hingga `100` THEN sistem SHALL CONTINUE TO menyimpan dan menerapkan nilai tersebut dengan benar

3.3 WHEN pengguna mengatur `ba_account_delay` ke nilai positif (misalnya `10`, `30`, `60`) THEN sistem SHALL CONTINUE TO menyimpan dan menerapkan nilai tersebut dengan benar

3.4 WHEN pengguna mengatur field lain seperti `delay`, `count`, `batch_delay`, `batch_size`, `action_delay`, `batch_action`, `ba_delay`, `rand_len` THEN sistem SHALL CONTINUE TO memvalidasi dan menyimpan nilai-nilai tersebut sesuai limit yang sudah ada tanpa perubahan

3.5 WHEN konfigurasi disimpan ke `xcreategroup_user_configs.json` THEN sistem SHALL CONTINUE TO menggunakan format JSON yang sama dan atomic write (via `.tmp` file) tanpa perubahan struktur

3.6 WHEN pengguna menggunakan tombol keypad `+`/`-` untuk field `action_delay` THEN sistem SHALL CONTINUE TO membatasi nilai minimum ke `0.1` (field ini tidak termasuk dalam bugfix)

3.7 WHEN pengguna menggunakan fitur lain pada dashboard xcreategroup (toggle, session select, task management, creation reports) THEN sistem SHALL CONTINUE TO berfungsi tanpa perubahan perilaku

---

## Bug Condition Pseudocode

### BUG 1 & 3 — Zero-floor Validation

```pascal
FUNCTION isBugCondition_ZeroFloor(field, value)
  INPUT: field of type string, value of type number
  OUTPUT: boolean
  
  RETURN (field = "account_delay" AND value = 0)
      OR (field = "ba_account_delay" AND value = 0)
END FUNCTION

// Property: Fix Checking — Zero is valid for account_delay and ba_account_delay
FOR ALL (field, value) WHERE isBugCondition_ZeroFloor(field, value) DO
  result ← applyLimit'(field, value)
  ASSERT result = 0
END FOR

// Property: Preservation Checking
FOR ALL (field, value) WHERE NOT isBugCondition_ZeroFloor(field, value) DO
  ASSERT applyLimit(field, value) = applyLimit'(field, value)
END FOR
```

### BUG 2 — Upper Bound Validation

```pascal
FUNCTION isBugCondition_UpperBound(field, value)
  INPUT: field of type string, value of type number
  OUTPUT: boolean
  
  RETURN field = "batch_account" AND value > 100 AND value <= 1000
END FUNCTION

// Property: Fix Checking — Values 101–1000 are valid for batch_account
FOR ALL (field, value) WHERE isBugCondition_UpperBound(field, value) DO
  result ← applyLimit'(field, value)
  ASSERT result = value
END FOR

// Property: Preservation Checking
FOR ALL (field, value) WHERE NOT isBugCondition_UpperBound(field, value) DO
  ASSERT applyLimit(field, value) = applyLimit'(field, value)
END FOR
```
