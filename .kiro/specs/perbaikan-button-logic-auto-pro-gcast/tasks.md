# Rencana Implementasi: Perbaikan Logic Tombol Auto Pro GCast

## Gambaran Umum

Rencana implementasi ini mencakup perbaikan bug "invalid index" dan "invalid user id" pada plugin Auto Pro Global Broadcast dengan mengimplementasikan format-aware UID extraction logic. Implementasi menggunakan Python dengan framework Pyrogram untuk Telegram userbot.

## Tasks

- [ ] 1. Analisis dan Dokumentasi Format Callback
  - [ ] 1.1 Identifikasi semua format callback data yang digunakan
    - Review kode untuk menemukan semua callback data format
    - Dokumentasikan format untuk setiap action type
    - Buat mapping action → format → UID position
    - _Persyaratan: 4.1-4.6_
  
  - [ ] 1.2 Buat test cases untuk setiap format
    - Buat list semua callback data yang perlu di-test
    - Include edge cases (short UID, long UID, index 0, large index)
    - Dokumentasikan expected UID dan index untuk setiap test case
    - _Persyaratan: 6.1, 6.5, 6.6_

- [ ] 2. Implementasi Format-Aware UID Extraction
  - [ ] 2.1 Refactor UID extraction logic di pgc_callback_handler
    - Implement format detection based on action type
    - Implement explicit UID extraction untuk setiap format
    - Keep fallback logic untuk standard format
    - Add validation untuk UID (must be positive integer)
    - _Persyaratan: 1.1-1.12, 2.1_
  
  - [ ] 2.2 Add error handling untuk UID extraction
    - Catch ValueError untuk invalid format
    - Catch ValueError untuk non-numeric UID
    - Return clear error message via safe_cb_answer
    - Log error untuk debugging
    - _Persyaratan: 2.2, 5.1, 5.2, 5.5, 5.6_
  
  - [ ] 2.3 Test UID extraction dengan semua format
    - Test dengan callback data dari task 1.2
    - Verify tidak ada error "invalid user id"
    - Verify UID yang diekstrak benar untuk setiap format
    - _Persyaratan: 1.1-1.12, 6.4_

- [ ] 3. Checkpoint - Verify UID Extraction Works
  - Pastikan semua test UID extraction pass
  - Verify tidak ada error "invalid user id" untuk semua tombol
  - Tanyakan user jika ada pertanyaan

- [ ] 4. Implementasi Index Extraction dan Validasi
  - [ ] 4.1 Implement index extraction logic
    - Extract index based on action type
    - Handle different index positions untuk different formats
    - Validate index is non-negative integer
    - _Persyaratan: 3.1-3.4_
  
  - [ ] 4.2 Implement index validation logic
    - Validate index is within range of list (text_list or media_list)
    - Return False if index out of range
    - Handle empty list case
    - _Persyaratan: 3.5-3.6_
  
  - [ ] 4.3 Add error handling untuk index extraction
    - Catch ValueError untuk invalid index
    - Catch IndexError untuk out of range
    - Return clear error message via safe_cb_answer
    - Log error untuk debugging
    - _Persyaratan: 5.3, 5.5, 5.6_
  
  - [ ] 4.4 Test index extraction dan validation
    - Test dengan berbagai index values (0, 1, 10, 100)
    - Test dengan empty list
    - Test dengan out of range index
    - Verify error message untuk invalid index
    - _Persyaratan: 3.1-3.6, 6.6, 6.7_

- [ ] 5. Checkpoint - Verify Index Extraction Works
  - Pastikan semua test index extraction pass
  - Verify tidak ada error "invalid index" untuk semua tombol
  - Tanyakan user jika ada pertanyaan

- [ ] 6. Update Semua Handler yang Menggunakan Index
  - [ ] 6.1 Update message preview handlers (text dan media)
    - Use new index extraction logic
    - Add index validation before accessing list
    - Handle error gracefully
    - _Persyaratan: 1.1, 1.2, 3.1-3.6_
  
  - [ ] 6.2 Update message delete confirmation handlers (text dan media)
    - Use new index extraction logic
    - Add index validation before accessing list
    - Handle error gracefully
    - _Persyaratan: 1.3, 1.4, 3.1-3.6_
  
  - [ ] 6.3 Update message delete handlers (text dan media)
    - Use new index extraction logic
    - Add index validation before accessing list
    - Handle error gracefully
    - _Persyaratan: 1.5, 1.6, 3.1-3.6_
  
  - [ ] 6.4 Update message set fixed handlers (text dan media)
    - Use new index extraction logic
    - Add index validation before accessing list
    - Handle error gracefully
    - _Persyaratan: 1.7, 1.8, 3.1-3.6_
  
  - [ ] 6.5 Update blacklist delete handler
    - Use new index extraction logic
    - Add index validation before accessing blacklist
    - Handle error gracefully
    - _Persyaratan: 1.9, 3.2-3.6_

- [ ] 7. Checkpoint - Verify All Handlers Work
  - Test setiap handler dengan berbagai input
  - Verify tidak ada error untuk semua tombol
  - Tanyakan user jika ada pertanyaan

- [ ] 8. Add Code Comments dan Documentation
  - [ ] 8.1 Add comments untuk setiap format callback data
    - Document format structure
    - Document UID position
    - Document index position (if applicable)
    - Add examples untuk setiap format
    - _Persyaratan: 4.6_
  
  - [ ] 8.2 Add docstrings untuk extraction functions
    - Document parameters
    - Document return values
    - Document exceptions
    - Add examples
    - _Persyaratan: 4.6_

- [ ] 9. Write Unit Tests
  - [ ]* 9.1 Write unit tests untuk UID extraction
    - Test setiap format callback data
    - Test dengan berbagai UID values
    - Test error cases (invalid format, non-numeric UID)
    - _Persyaratan: 6.1, 6.5_
  
  - [ ]* 9.2 Write unit tests untuk index extraction
    - Test setiap format dengan index
    - Test dengan berbagai index values
    - Test error cases (invalid index, out of range)
    - _Persyaratan: 6.1, 6.6_
  
  - [ ]* 9.3 Write unit tests untuk index validation
    - Test dengan berbagai list sizes
    - Test dengan berbagai index values
    - Test edge cases (empty list, index 0, max index)
    - _Persyaratan: 6.1, 6.7_

- [ ] 10. Write Property-Based Tests
  - [ ]* 10.1 Write property test untuk UID extraction correctness
    - **Property 1: UID Extraction Correctness**
    - **Memvalidasi: Persyaratan 1.1-1.12**
    - Generate random UID dan index
    - Build callback data dengan format yang berbeda
    - Verify extracted UID matches original UID
    - Minimum 100 iterasi per test
  
  - [ ]* 10.2 Write property test untuk index extraction correctness
    - **Property 2: Index Extraction Correctness**
    - **Memvalidasi: Persyaratan 3.1-3.4**
    - Generate random UID dan index
    - Build callback data dengan format yang berbeda
    - Verify extracted index matches original index
    - Minimum 100 iterasi per test
  
  - [ ]* 10.3 Write property test untuk index validation correctness
    - **Property 3: Index Validation Correctness**
    - **Memvalidasi: Persyaratan 3.5-3.6**
    - Generate random list size dan index
    - Verify validation result matches expected (in range or not)
    - Minimum 100 iterasi per test
  
  - [ ]* 10.4 Write property test untuk error handling robustness
    - **Property 4: Error Handling Robustness**
    - **Memvalidasi: Persyaratan 5.1-5.6**
    - Generate random invalid callback data
    - Generate random exceptions
    - Verify sistem tidak crash dan return error message
    - Minimum 100 iterasi per test

- [ ] 11. Write Integration Tests
  - [ ]* 11.1 Write integration test untuk setiap tombol
    - Test dengan real callback handler
    - Test dengan mock client dan callback query
    - Verify tidak ada error untuk setiap tombol
    - _Persyaratan: 6.3_
  
  - [ ]* 11.2 Write integration test untuk all buttons
    - Test semua tombol dalam satu test
    - Verify tidak ada error "invalid index" atau "invalid user id"
    - _Persyaratan: 6.4_

- [ ] 12. Checkpoint Final - Verify All Tests Pass
  - Jalankan semua tests (unit + property + integration)
  - Verify tidak ada error atau warning
  - Verify coverage mencakup semua fungsi yang dimodifikasi
  - Tanyakan user jika ada pertanyaan atau perlu review tambahan

- [ ] 13. Manual Testing dengan User
  - [ ] 13.1 Test semua tombol di dashboard utama
    - Test toggle buttons (chat filter, random, notify, etc)
    - Test navigation buttons (message list, blacklist, smart purge, etc)
    - Test info pagination
    - Verify tidak ada error
  
  - [ ] 13.2 Test semua tombol di message list
    - Test preview buttons (text dan media)
    - Test delete buttons (text dan media)
    - Test set fixed buttons (text dan media)
    - Test clear all button
    - Verify tidak ada error "invalid index"
  
  - [ ] 13.3 Test semua tombol di blacklist
    - Test add button
    - Test delete buttons
    - Test pagination
    - Verify tidak ada error
  
  - [ ] 13.4 Test semua tombol di smart purge
    - Test toggle button
    - Test limit adjustment buttons
    - Test delay adjustment buttons
    - Test mode button
    - Test offset adjustment buttons
    - Verify tidak ada error
  
  - [ ] 13.5 Test semua tombol di auto react
    - Test toggle button
    - Test delay adjustment buttons
    - Test emoji selection buttons
    - Verify tidak ada error

- [ ] 14. Final Verification
  - Verify semua tombol berfungsi dengan benar
  - Verify tidak ada error "invalid index" atau "invalid user id"
  - Verify error messages jelas dan helpful
  - Dokumentasikan semua perubahan yang dilakukan

## Catatan

- Task yang ditandai dengan `*` adalah optional (testing) dan dapat di-skip untuk MVP lebih cepat
- Setiap task mereferensikan persyaratan spesifik untuk traceability
- Checkpoint memastikan validasi incremental
- Property test menggunakan hypothesis library dengan minimum 100 iterasi
- Manual testing dengan user adalah critical untuk memastikan semua tombol bekerja
- Focus pada fixing bug dulu, testing bisa dilakukan setelah bug fixed
