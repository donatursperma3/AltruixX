# Dokumen Desain: Perbaikan Logic Tombol Auto Pro GCast

## Gambaran Umum

Desain ini menjelaskan solusi untuk memperbaiki bug "invalid index" dan "invalid user id" yang terjadi pada berbagai tombol di plugin Auto Pro Global Broadcast. Bug ini disebabkan oleh logic ekstraksi user ID yang salah, di mana sistem mencari numeric part dari belakang dan salah mengambil index pesan sebagai user ID.

Solusi yang diusulkan adalah menggunakan **format-aware UID extraction** yang mengenali format callback data berdasarkan action type, sehingga dapat mengekstrak UID dari posisi yang tepat.

## Arsitektur

### Komponen Utama

1. **Callback Handler** (`pgc_callback_handler`)
   - Master handler untuk semua callback dengan prefix `pgc_`
   - Melakukan parsing callback data dan routing ke handler spesifik
   - Mengekstrak UID dan parameters lain dari callback data

2. **UID Extraction Logic**
   - Logic untuk mengidentifikasi format callback data
   - Logic untuk mengekstrak UID dari posisi yang tepat
   - Validasi UID yang diekstrak

3. **Index Extraction Logic**
   - Logic untuk mengekstrak index pesan dari callback data
   - Validasi index (range check)

4. **Error Handling**
   - Catch dan handle berbagai error scenarios
   - Return error message yang jelas ke user

### Alur Data

```
User Click Button → Telegram → Callback Query → pgc_callback_handler
                                                        ↓
                                                  Parse callback data
                                                        ↓
                                                  Extract UID (format-aware)
                                                        ↓
                                                  Validate UID
                                                        ↓
                                                  Load Settings
                                                        ↓
                                                  Extract Index (if needed)
                                                        ↓
                                                  Validate Index
                                                        ↓
                                                  Execute Action
                                                        ↓
                                                  Return Response
```

## Format Callback Data

### Kategori Format

Callback data di Auto Pro GCast memiliki beberapa kategori format:

#### 1. Message Action Format (dengan type dan index)
```
pgc_{action}_{type}_{uid}_{index}
```

Contoh:
- `pgc_msgpreview_text_7844837037_0` → Preview text message index 0
- `pgc_msgpreview_media_7844837037_2` → Preview media message index 2
- `pgc_msgdelconf_text_7844837037_1` → Delete confirmation text message index 1
- `pgc_msgdel_media_7844837037_0` → Delete media message index 0
- `pgc_msgsetfixed_text_7844837037_3` → Set fixed text message index 3

**Parts breakdown:**
- parts[0] = "pgc"
- parts[1] = action ("msgpreview", "msgdelconf", "msgdel", "msgsetfixed")
- parts[2] = type ("text", "media")
- parts[3] = uid (user ID)
- parts[4] = index (message index)

**UID location:** parts[3]
**Index location:** parts[4] atau parts[-1]

#### 2. Blacklist Delete Format
```
pgc_bldel_{uid}_{index}
```

Contoh:
- `pgc_bldel_7844837037_0` → Delete blacklist item index 0
- `pgc_bldel_7844837037_5` → Delete blacklist item index 5

**Parts breakdown:**
- parts[0] = "pgc"
- parts[1] = "bldel"
- parts[2] = uid (user ID)
- parts[3] = index (blacklist index)

**UID location:** parts[2]
**Index location:** parts[3]

#### 3. Pagination Format
```
pgc_{action}_{uid}_page_{N}
```

Contoh:
- `pgc_info_7844837037_page_2` → Info page 2
- `pgc_bl_7844837037_page_1` → Blacklist page 1

**Parts breakdown:**
- parts[0] = "pgc"
- parts[1] = action ("info", "bl")
- parts[2] = uid (user ID)
- parts[3] = "page"
- parts[4] = page number

**UID location:** parts[2]

#### 4. Smart Purge Sub-Action Format
```
pgc_sp_{subaction}_{uid}
```

Contoh:
- `pgc_sp_toggle_7844837037` → Toggle smart purge
- `pgc_sp_limit_inc_7844837037` → Increase limit
- `pgc_sp_limit_dec_7844837037` → Decrease limit
- `pgc_sp_delay_inc_7844837037` → Increase delay
- `pgc_sp_mode_7844837037` → Change mode

**Parts breakdown:**
- parts[0] = "pgc"
- parts[1] = "sp"
- parts[2] = subaction ("toggle", "limit", "delay", "mode", dll)
- parts[3] = uid (user ID) ATAU additional param (contoh: "inc", "dec")
- parts[4] = uid (jika parts[3] adalah param)

**UID location:** Last numeric part (bisa parts[3] atau parts[4])

**PROBLEM:** Untuk format seperti `pgc_sp_limit_dec_7844837037`:
- parts = ["pgc", "sp", "limit", "dec", "7844837037"]
- Old logic: Search from back → found "7844837037" at parts[4] ✅
- But for `pgc_sp_limit_7844837037`:
- parts = ["pgc", "sp", "limit", "7844837037"]
- Old logic: Search from back → found "7844837037" at parts[3] ✅

Sebenarnya untuk smart purge format, old logic sudah benar karena selalu mencari last numeric part.

#### 5. Standard Format
```
pgc_{action}_{uid}
```

Contoh:
- `pgc_backmain_7844837037` → Back to main menu
- `pgc_chatfilter_7844837037` → Toggle chat filter
- `pgc_msglist_7844837037` → Open message list
- `pgc_bl_7844837037` → Open blacklist

**Parts breakdown:**
- parts[0] = "pgc"
- parts[1] = action
- parts[2] = uid (user ID)

**UID location:** parts[2]

## Solusi: Format-Aware UID Extraction

### Algoritma

```python
def extract_uid_from_callback(data: str) -> int:
    """
    Extract user ID from callback data with format-aware logic.
    
    Args:
        data: Callback data string (e.g., "pgc_msgpreview_text_7844837037_0")
    
    Returns:
        User ID as integer
    
    Raises:
        ValueError: If UID cannot be extracted or is invalid
    """
    parts = data.split("_")
    
    # Minimum: pgc_action_uid
    if len(parts) < 3:
        raise ValueError("Invalid callback data format")
    
    action = parts[1]
    uid = None
    
    # Format detection based on action
    if action in ["msgpreview", "msgdelconf", "msgdel", "msgsetfixed"]:
        # Format: pgc_action_type_uid_index
        # Example: pgc_msgpreview_text_7844837037_0
        if len(parts) >= 5:
            uid = int(parts[3])  # UID is always at parts[3]
    
    elif action == "bldel":
        # Format: pgc_bldel_uid_index
        # Example: pgc_bldel_7844837037_0
        if len(parts) >= 4:
            uid = int(parts[2])  # UID is at parts[2]
    
    elif len(parts) >= 5 and parts[-2] == "page":
        # Format: pgc_action_uid_page_N
        # Example: pgc_info_7844837037_page_2
        uid = int(parts[2])  # UID is always at parts[2] for pagination
    
    else:
        # Standard format: pgc_action_uid or pgc_action_subaction_uid
        # Example: pgc_backmain_7844837037 or pgc_sp_toggle_7844837037
        # UID is always the last numeric part
        for i in range(len(parts) - 1, 1, -1):
            try:
                uid = int(parts[i])
                break
            except ValueError:
                continue
    
    if uid is None:
        raise ValueError("No valid user ID found")
    
    if uid <= 0:
        raise ValueError("User ID must be positive")
    
    return uid
```

### Keuntungan Solusi Ini

1. **Format-Aware**: Mengenali format berdasarkan action type
2. **Explicit**: Jelas di mana UID berada untuk setiap format
3. **Fallback**: Masih ada fallback ke "last numeric part" untuk format standard
4. **Maintainable**: Mudah menambahkan format baru
5. **Testable**: Mudah di-test dengan berbagai input

### Perbandingan dengan Old Logic

**Old Logic (WRONG):**
```python
# Always search from back for last numeric part
for i in range(len(parts) - 1, 1, -1):
    try:
        uid = int(parts[i])
        break
    except ValueError:
        continue
```

**Problem:**
- Untuk `pgc_msgpreview_text_7844837037_0`:
  - parts = ["pgc", "msgpreview", "text", "7844837037", "0"]
  - Search from back: parts[4] = "0" → uid = 0 ❌ (WRONG!)
  - Should be: parts[3] = "7844837037" → uid = 7844837037 ✅

**New Logic (CORRECT):**
```python
# Format-aware extraction
if action in ["msgpreview", "msgdelconf", "msgdel", "msgsetfixed"]:
    uid = int(parts[3])  # Explicit position for this format
```

**Result:**
- Untuk `pgc_msgpreview_text_7844837037_0`:
  - parts = ["pgc", "msgpreview", "text", "7844837037", "0"]
  - uid = int(parts[3]) = 7844837037 ✅ (CORRECT!)

## Index Extraction Logic

### Algoritma

```python
def extract_index_from_callback(data: str, action: str) -> int:
    """
    Extract message/item index from callback data.
    
    Args:
        data: Callback data string
        action: Action type (for format detection)
    
    Returns:
        Index as integer
    
    Raises:
        ValueError: If index cannot be extracted or is invalid
    """
    parts = data.split("_")
    index = None
    
    if action in ["msgpreview", "msgdelconf", "msgdel", "msgsetfixed"]:
        # Format: pgc_action_type_uid_index
        # Index is at parts[4] or parts[-1]
        if len(parts) >= 5:
            index = int(parts[-1])  # Last part is always index
    
    elif action == "bldel":
        # Format: pgc_bldel_uid_index
        # Index is at parts[3]
        if len(parts) >= 4:
            index = int(parts[3])
    
    if index is None:
        raise ValueError("No valid index found")
    
    if index < 0:
        raise ValueError("Index must be non-negative")
    
    return index
```

### Validasi Index

Setelah ekstraksi, index harus divalidasi terhadap list yang sesuai:

```python
def validate_index(index: int, list_type: str, settings: dict) -> bool:
    """
    Validate that index is within range of the list.
    
    Args:
        index: Index to validate
        list_type: "text" or "media"
        settings: User settings containing message lists
    
    Returns:
        True if valid, False otherwise
    """
    if list_type == "text":
        text_list = settings.get("text_list", [])
        return 0 <= index < len(text_list)
    elif list_type == "media":
        media_list = settings.get("media_list", [])
        return 0 <= index < len(media_list)
    else:
        return False
```

## Error Handling

### Error Scenarios dan Response

| Error Scenario | Error Message | Show Alert | Action |
|----------------|---------------|------------|--------|
| Callback data kurang dari 3 parts | "Invalid callback data." | True | Return early |
| UID tidak dapat diekstrak | "Invalid user ID." | True | Return early |
| UID bukan integer | "Invalid user ID." | True | Return early |
| UID <= 0 | "Invalid user ID." | True | Return early |
| Index tidak dapat diekstrak | "Invalid index." | True | Return early |
| Index bukan integer | "Invalid index." | True | Return early |
| Index < 0 | "Invalid index." | True | Return early |
| Index out of range | "Invalid index." | True | Return early |
| Settings tidak ditemukan | Create default settings | False | Continue |
| Exception dalam handler | "An error occurred." | True | Log error, return |

### Error Handling Pattern

```python
try:
    # Extract UID
    uid = extract_uid_from_callback(data)
except ValueError as e:
    await safe_cb_answer(cb, "Invalid user ID.", show_alert=True)
    return

try:
    # Extract index (if needed)
    index = extract_index_from_callback(data, action)
except ValueError as e:
    await safe_cb_answer(cb, "Invalid index.", show_alert=True)
    return

# Validate index range
if not validate_index(index, msg_type, settings):
    await safe_cb_answer(cb, "Invalid index.", show_alert=True)
    return

# Execute action
try:
    # ... action logic ...
except Exception as e:
    logger.error(f"Error in {action} handler: {e}")
    await safe_cb_answer(cb, "An error occurred.", show_alert=True)
    return
```

## Testing Strategy

### Unit Tests

Test setiap format callback data dengan berbagai input:

```python
def test_extract_uid_msgpreview_text():
    """Test UID extraction for message preview text format."""
    data = "pgc_msgpreview_text_7844837037_0"
    uid = extract_uid_from_callback(data)
    assert uid == 7844837037

def test_extract_uid_msgpreview_media():
    """Test UID extraction for message preview media format."""
    data = "pgc_msgpreview_media_123456789_5"
    uid = extract_uid_from_callback(data)
    assert uid == 123456789

def test_extract_uid_bldel():
    """Test UID extraction for blacklist delete format."""
    data = "pgc_bldel_7844837037_0"
    uid = extract_uid_from_callback(data)
    assert uid == 7844837037

def test_extract_uid_pagination():
    """Test UID extraction for pagination format."""
    data = "pgc_info_7844837037_page_2"
    uid = extract_uid_from_callback(data)
    assert uid == 7844837037

def test_extract_uid_standard():
    """Test UID extraction for standard format."""
    data = "pgc_backmain_7844837037"
    uid = extract_uid_from_callback(data)
    assert uid == 7844837037

def test_extract_uid_invalid_format():
    """Test UID extraction with invalid format."""
    data = "pgc_action"
    with pytest.raises(ValueError):
        extract_uid_from_callback(data)

def test_extract_index_msgpreview():
    """Test index extraction for message preview format."""
    data = "pgc_msgpreview_text_7844837037_0"
    index = extract_index_from_callback(data, "msgpreview")
    assert index == 0

def test_extract_index_bldel():
    """Test index extraction for blacklist delete format."""
    data = "pgc_bldel_7844837037_5"
    index = extract_index_from_callback(data, "bldel")
    assert index == 5

def test_validate_index_in_range():
    """Test index validation within range."""
    settings = {"text_list": ["msg1", "msg2", "msg3"]}
    assert validate_index(0, "text", settings) == True
    assert validate_index(2, "text", settings) == True

def test_validate_index_out_of_range():
    """Test index validation out of range."""
    settings = {"text_list": ["msg1", "msg2"]}
    assert validate_index(5, "text", settings) == False
    assert validate_index(-1, "text", settings) == False
```

### Property-Based Tests

Test dengan berbagai kombinasi input menggunakan hypothesis:

```python
from hypothesis import given, strategies as st

@given(
    uid=st.integers(min_value=1, max_value=9999999999),
    index=st.integers(min_value=0, max_value=100)
)
def test_property_msgpreview_format(uid, index):
    """Property: UID extraction for msgpreview format always returns correct UID."""
    data = f"pgc_msgpreview_text_{uid}_{index}"
    extracted_uid = extract_uid_from_callback(data)
    assert extracted_uid == uid

@given(
    uid=st.integers(min_value=1, max_value=9999999999),
    index=st.integers(min_value=0, max_value=100)
)
def test_property_index_extraction(uid, index):
    """Property: Index extraction for msgpreview format always returns correct index."""
    data = f"pgc_msgpreview_text_{uid}_{index}"
    extracted_index = extract_index_from_callback(data, "msgpreview")
    assert extracted_index == index

@given(
    list_size=st.integers(min_value=0, max_value=100),
    index=st.integers(min_value=0, max_value=100)
)
def test_property_index_validation(list_size, index):
    """Property: Index validation correctly identifies in-range vs out-of-range."""
    settings = {"text_list": ["msg"] * list_size}
    result = validate_index(index, "text", settings)
    expected = 0 <= index < list_size
    assert result == expected
```

### Integration Tests

Test setiap tombol dengan real callback handler:

```python
async def test_integration_msgpreview_button():
    """Integration test for message preview button."""
    # Setup
    client = MockClient()
    cb = MockCallbackQuery(data="pgc_msgpreview_text_7844837037_0")
    
    # Execute
    await pgc_callback_handler(client, cb)
    
    # Verify
    assert cb.answer_called
    assert not cb.answer_text.startswith("Invalid")

async def test_integration_all_buttons():
    """Integration test for all buttons in dashboard."""
    test_cases = [
        "pgc_msgpreview_text_7844837037_0",
        "pgc_msgpreview_media_7844837037_1",
        "pgc_msgdelconf_text_7844837037_0",
        "pgc_msgdel_media_7844837037_2",
        "pgc_msgsetfixed_text_7844837037_1",
        "pgc_bldel_7844837037_0",
        "pgc_info_7844837037_page_1",
        "pgc_sp_toggle_7844837037",
        "pgc_backmain_7844837037",
    ]
    
    for data in test_cases:
        cb = MockCallbackQuery(data=data)
        await pgc_callback_handler(client, cb)
        assert not cb.answer_text.startswith("Invalid"), f"Failed for {data}"
```

## Implementation Plan

### Phase 1: Fix UID Extraction Logic (Critical)

1. Update `pgc_callback_handler` dengan format-aware UID extraction
2. Test dengan semua format callback data
3. Verify tidak ada error "invalid user id"

### Phase 2: Fix Index Extraction Logic (Critical)

1. Implement index extraction logic
2. Implement index validation logic
3. Test dengan berbagai index values
4. Verify tidak ada error "invalid index"

### Phase 3: Improve Error Handling (High Priority)

1. Add try-except blocks untuk semua extraction logic
2. Return clear error messages
3. Log errors untuk debugging

### Phase 4: Add Tests (Medium Priority)

1. Write unit tests untuk semua format
2. Write property tests untuk extraction logic
3. Write integration tests untuk semua buttons

### Phase 5: Documentation (Low Priority)

1. Add code comments untuk setiap format
2. Update README dengan callback format documentation
3. Add examples untuk setiap format

## Properti Kebenaran

### Properti 1: UID Extraction Correctness

*Untuk setiap* callback data dengan format valid, UID yang diekstrak harus sama dengan UID yang ada di callback data.

**Memvalidasi: Persyaratan 1.1-1.12**

### Properti 2: Index Extraction Correctness

*Untuk setiap* callback data dengan format yang memiliki index, index yang diekstrak harus sama dengan index yang ada di callback data.

**Memvalidasi: Persyaratan 3.1-3.4**

### Properti 3: Index Validation Correctness

*Untuk setiap* index dan list, validasi index harus return True jika dan hanya jika index berada dalam range [0, len(list)).

**Memvalidasi: Persyaratan 3.5-3.6**

### Properti 4: Error Handling Robustness

*Untuk setiap* callback data invalid atau exception yang terjadi, sistem harus handle dengan graceful (tidak crash) dan return error message yang jelas.

**Memvalidasi: Persyaratan 5.1-5.6**

### Properti 5: Format Consistency

*Untuk setiap* action type, format callback data harus konsisten dan terdokumentasi.

**Memvalidasi: Persyaratan 4.1-4.6**

## Kesimpulan

Solusi format-aware UID extraction akan memperbaiki bug "invalid index" dan "invalid user id" dengan mengenali format callback data berdasarkan action type dan mengekstrak UID dari posisi yang tepat. Solusi ini lebih robust, maintainable, dan testable dibandingkan old logic yang selalu mencari last numeric part.
