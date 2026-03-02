# Evaldoc Documentation System - Requirements

## Overview
Sistem dokumentasi komprehensif untuk eval/reval commands yang menyediakan panduan lengkap tentang penggunaan client userbot dalam environment multiclient Altruix.

## User Stories

### US-1: Dokumentasi Lengkap dari DEVELOPER_GUIDE.md
**As a** developer menggunakan Altruix userbot  
**I want** semua informasi dari DEVELOPER_GUIDE.md tersedia dalam help menu plugin  
**So that** saya dapat mengakses dokumentasi lengkap tanpa membuka file eksternal

**Acceptance Criteria:**
- Semua info dari DEVELOPER_GUIDE.md harus included (tidak boleh kurang satu kata pun)
- Dokumentasi mencakup import, bot assistant, userbot list, multiple sessions
- Dokumentasi mencakup client aktif dengan contoh detail
- Format code menggunakan `<pre language="python">` untuk syntax highlighting

### US-2: Pagination untuk Mobile-Friendly
**As a** user mengakses dokumentasi via mobile  
**I want** dokumentasi dibagi dalam halaman-halaman pendek  
**So that** mudah dibaca di layar kecil

**Acceptance Criteria:**
- Limit text per page: ~200-400 karakter (mobile-friendly)
- Total 15 halaman dokumentasi
- Setiap halaman fokus pada satu topik spesifik
- Navigasi antar halaman mudah dengan tombol

### US-3: Client Aktif Documentation
**As a** developer yang bingung tentang client aktif  
**I want** penjelasan sangat jelas dengan contoh detail  
**So that** saya tahu cara menggunakan client yang sedang aktif

**Acceptance Criteria:**
- Dedicated pages (5-6) untuk client aktif
- Contoh penggunaan `client` dalam handler
- Contoh auto-detect session aktif
- Contoh praktis yang bisa langsung digunakan

### US-4: Inline Mode Dashboard
**As a** user yang ingin akses dokumentasi di chat manapun  
**I want** mode inline (via @bot) dengan tombol pagination  
**So that** bisa membuka dashboard dokumentasi di chat manapun

**Acceptance Criteria:**
- Inline mode via @bot evaldoc
- Dashboard dengan tombol inline untuk navigasi
- Tombol next/prev untuk pagination
- Bisa digunakan di chat manapun (tidak perlu bot ada di chat)

### US-5: Security Protection
**As a** bot owner  
**I want** semua tombol dilindungi dengan authorization  
**So that** hanya owner/sudo yang bisa menggunakan fitur

**Acceptance Criteria:**
- Semua tombol dilindungi fungsi @iuser_check
- Authorization checks (owner/sudo only)
- Activity logging (configurable)
- Custom alert messages untuk unauthorized users

## Functional Requirements

### FR-1: Documentation Content
- 15 halaman dokumentasi (~200-400 chars per page)
- Page 1: Import Altruix
- Page 2: Bot Assistant
- Page 3: Userbot List
- Page 4: Multiple Sessions
- Page 5-6: Client Aktif (dengan contoh detail)
- Page 7: Get Index
- Page 8: Find by User ID
- Page 9: Bot Manager
- Page 10: Plugin Example
- Page 11: Handler Best Practice
- Page 12: Prefix Handling
- Page 13: De-duplication
- Page 14: Quick Reference
- Page 15: Tips

### FR-2: Inline Keyboard
- Row 1: ◀️ Prev | 📄 Page X/15 | Next ▶️
- Row 2: ⏮️ First | ⭐ Client (jump to page 5) | Last ⏭️
- Row 3: ❌ Close
- Prev/Next disabled pada boundary pages
- Page indicator sebagai display-only button

### FR-3: Inline Mode Support
- Inline query handler dengan regex `r"^evaldoc(?:_page_)?(\d+)?"`
- Support page number dalam query
- Works in ANY chat via inline mode
- Fallback ke direct message jika inline gagal

### FR-4: Callback Handler
- Handle page navigation (prev/next/first/last/client)
- Handle close button (delete message)
- Handle noop untuk disabled buttons
- Safe error handling untuk expired callbacks

### FR-5: Security
- @iuser_check decorator pada callback handler
- @iuser_check decorator pada inline handler
- Session ID authorization untuk inline queries
- Activity logging (configurable)

## Non-Functional Requirements

### NFR-1: Performance
- Keyboard generation harus cepat (<100ms)
- Inline query response <500ms
- Callback response <200ms

### NFR-2: Reliability
- No NoneType errors
- Handle expired callbacks gracefully
- Support both regular and inline messages
- Proper error logging

### NFR-3: Usability
- Mobile-friendly page length
- Clear navigation dengan emoji
- Quick jump ke Client Aktif (page 5)
- User-friendly error messages

### NFR-4: Maintainability
- Clean code structure
- Helper functions untuk safe operations
- Comprehensive documentation
- Test coverage

## Technical Constraints

- Must use Pyrogram library
- Must integrate with Altruix ecosystem
- Must support multiclient environment
- Must follow existing plugin patterns

## Success Metrics

- All 15 pages accessible
- All 7 button types working
- Inline mode functional
- Security protection active
- No emoji corruption
- Zero NoneType errors

## Dependencies

- Pyrogram library
- Altruix core framework
- Bot manager system
- iuser_check decorator

## Out of Scope

- Multi-language support (only Indonesian)
- Custom themes
- Search functionality
- Bookmarking pages
