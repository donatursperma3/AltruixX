# AltruixX Changelog

All notable changes to the **AltruixX** project from version **0.0.10.0959H** to the latest.

---

## [0.0.10.2318H] - 2026-05-03 (Current)

### 🎨 Premium Logging: Full-Boot Refinement
- **Restored functional colors**: Re-implemented `start.bat` color variables (`CYAN`, `YELLOW`, etc.) that were missing, ensuring text is as vibrant as before.
- **100% Timestamp Coverage**: Every single boot line, including banners and indented environment info, now features consistent timestamping.
- **Branded Consistency**: Applied unified `[Altroid-X]` tags across all launch phases for a premium, synchronized feel.

### 📊 System Reporting: Version Visibility
- **Statistics Update**: Added the current system version to the `📊 SISTEM STATISTIK` message in both Telegram and Console reports.

### 🛠 Power Controls: Debugging Hardening
- **Enhanced Logging**: Integrated detailed `Altruix.log` entries into `power_tools.py` for real-time tracking of restart/reload sequences.

### 🧹 Auto Global Purgeme: Logic Fixes
- **Resolved NameError**: Fixed variable `m` to `message` in the input handler.
- **Fixed missing emojis**: Corrected a crash in global cycle reports due to undefined `type_emoji`.

## [0.0.10.2316H] - 2026-05-02

### 🔄 Restart System: Stability & Windows Optimization
- **Critical Fix: Restart Command Reliability**:
  - Resolved issues where the `restart` and `reload` commands would fail to execute or stall after confirmation.
- **Improved: Windows Process Management**:
  - Refactored "Hard Restart" (Process Swap) to use `subprocess.CREATE_NEW_CONSOLE` and detached process handling on Windows.
  - Ensures the new instance successfully launches and survives the parent's termination.
- **Fixed: Namespace Collisions**:
  - Renamed duplicate callback handlers in `power_tools.py` to prevent function overwriting and improve registration reliability.
- **Enhanced: Restart Completion Logic**:
  - Hardened the internal `_restart` engine in `client.py` to use explicit message IDs and the active bot instance for final confirmation.
  - Fixes "stale object" errors that previously prevented the "Altruix has been restarted!" message from appearing.
- **UI/UX Polishing**:
  - Fixed redundant nested `<blockquote>` tags in confirmation menus for a cleaner look.
  - Corrected typo in the confirmation result ("mesage" -> "message").

## [0.0.10.2315H] - 2026-05-02

### 🔘 Callback Logger: Precise Inline Attribution
- **New Feature: Real-Time Inline Resolution**:
  - Implemented high-reliability `inline_message_id` decoding using Pyrogram's `unpack_inline_message_id`.
  - The system now identifies the **Real Chat Name** and **Chat ID** (Source Group/Channel) for callbacks triggered via inline interfaces, replacing the generic "Inline Interface" label.
- **Improved: Chat ID Identification**:
  - Added support for resolving `owner_id` from decoded inline IDs across all 10+ connected sessions.
  - Corrected a bug where `chat_id` was reported as "N/A" for regular message callbacks.
- **Enhanced: Multi-Tier Fallback System**:
  - Optimized the resolution flow: `Decoding` -> `DB Cache` -> `Callback Data Regex` -> `Live API Resolution`.
  - Ensures metadata consistency even when database caches are missing or expired.

### 🚀 Bootstrapping & Process Transparency
- **New Feature: Early Bootstrapping System**:
  - Implemented a lightweight milestone tracker that starts immediately upon execution, providing visibility into the "behind-the-scenes" process before the main logger is ready.
- **New Feature: High-Resolution Import Tracking**:
  - Added granular logs to track the loading of heavy libraries (Pyrogram, Httpx, Core Modules) to identify and debug slow startup bottlenecks.
- **Improved: Boot Aesthetics & Consistency**:
  - Early boot logs are now styled with premium ANSI colors and the `: »` prefix to perfectly match the existing system aesthetic.
- **Improved: Debug-Only Transparency**:
  - Bootstrapping milestones are intelligently filtered to only appear when `DEBUG=True`, ensuring a clean terminal for standard users while providing deep insights for developers.
- **Improved: Dependency Installation Progress**:
  - Updated `start.bat` and `start.sh` to remove the "black box" period by showing real-time `pip` installation progress instead of a silent wait.

### 🧹 Purgeme Tool: V6 Optimization & Absolute Targeting
- **New Feature: Account Message Counter**:
  - The dashboard now displays the total number of messages from the account available in the target chat.
  - Integrated into both the configuration menu and the active progress header for better visibility.
- **New Feature: Advanced Filters**:
  - **ID Range**: Added ability to filter messages within specific Message ID bounds (Min/Max ID).
  - **Date Range (Age in Days)**: Filter messages based on their age (e.g., delete messages older than 7 days but newer than 30 days).
- **Critical Fix: Absolute Oldest Logic Flow**:
  - Refactored the collection engine to use intelligent **Search Offsets** based on total user message count.
  - **Correct Targeting**: "Oldest" mode now correctly finds and targets the very first messages sent in chat history, rather than just reversing the newest ones.
  - **Sequential Processing**: Optimized the deletion sequence to ensure messages are processed in true chronological or reverse-chronological order based on the selected mode.
- **Bug Fixes & Stability**:
  - Fixed a critical `acc_link` undefined variable crash in `xpurgeme_bot.py`.
  - Resolved the `400 BOT_RESPONSE_TIMEOUT` error caused by inline query handler crashes.
  - Updated localization files (`en.yml`, `id.yml`) with consistent labels for new indicators.
- **Version Bump**:
  - **Bot Plugin**: `0.0.31`
  - **Userbot Plugin**: `0.0.442`

### 🏗️ CreateGroup Plugin: Reporting Transparency
- **Improved: Log Destination Reporting**:
  - The final completion report now dynamically detects and displays the correct **Log Destination** (`Log Group`, `Saved Messages`, or `Both`) as configured in settings.
  - Replaced hardcoded "Saved Messages" label with dynamic `log_info` logic to prevent misleading reports.

## [0.0.10.2005H] - 2026-05-01

### ⚙️ Program Controls: Database Management Pro
- **New Feature: Atomic Database Restore & Append**: 
  - Integrated high-performance ZIP-based backup/restore system within the Program Controls dashboard.
  - **Restore**: Overwrites system database with atomic locking to prevent data corruption.
  - **Append**: Intelligent JSON deep-merging that combines settings/sessions from backups into the current state without losing existing data.
- **Improved: Multi-Session Synchronization**:
  - Implemented automated **Soft Reboot** logic that triggers after critical database updates, ensuring all 10+ sessions stay perfectly in sync.
  - Added `Altruix.local_db.lock` awareness to prevent background saves during manual database operations.
- **Enhanced: Security & Validation**:
  - Added ZIP content validation to ensure integrity before extraction.
  - Hardened multi-client isolation to prevent cross-session configuration leakage.

### 🎥 YTDL Manager: Stability & Premium UX
- **Critical Fix: WEBPAGE_MEDIA_EMPTY Error**: 
  - Migrated the YTDL Dashboard from `InlineQueryResultPhoto` to `InlineQueryResultArticle`.
  - Resolves the persistent "400 WEBPAGE_MEDIA_EMPTY" crash caused by invalid/unreachable YouTube thumbnail URLs.
- **Improved: Responsive Dashboard UI**:
  - Implemented "Smart Edit" logic for all dashboard interactions.
  - Refactored callback handlers and regex patterns to support complex Task IDs.
- **Enhanced: Premium Media Processing (v0.0.238)**:
  - **MP3 Cover Embedding**: Thumbnails are now physically embedded as album art into downloaded MP3 files via `ffmpeg` metadata injection.
  - **Optimized Thumbnail Scaling**: Improved image processing with aspect-ratio awareness (max 320px) for perfect Telegram compatibility.
  - **Reliable Thumbnails**: Switched to an `httpx`-first download approach with protocol validation.
- **Robustness**: Added detailed error tracing (Traceback) for JSON parsing and database cleanup tasks.
- **Improved: Diagnostic & Error Tracking**:
  - Integrated `traceback` logging across all YTDL modules (`xyt_tools_bot.py` and `ytdl_core.py`).
  - Full stack traces are now logged for extraction failures, encoding errors, and database sync issues for easier maintenance.
- **Version Bump**:
  - **Plugin Version**: `1.0.166`
  - **YTDL Core Version**: `0.0.238`

## [0.0.10.1805H] - 2026-04-30

### 📊 Performance Logging & Logic Refinement
- **New: High-Resolution Debug Logs**:
  - Added explicit terminal logs for the selected `STAGGER_METHOD` during startup and restart.
  - Implemented the `: »` prefix logic when `DEBUG=True` for better diagnostic transparency.
- **Improved: Adaptive Restart Logic**:
  - The `.restart` and dashboard restart now dynamically follow the `STAGGER_METHOD` (Parallel/Sequential) set in settings.
  - Ensures consistency between manual reboots and system startup.

## [0.0.10.1800H] - 2026-04-30

### 🔄 Optimized Restart System & Unified Controls
- **Enhanced: Parallel Session Restart**:
  - The internal `_restart` logic (Soft Restart) now uses the same **High-Speed Parallel** engine as the startup process.
  - Multi-session accounts now reboot 10x faster without process termination.
- **Improved: Unified Restart Interface**:
  - The restart button in **Session Manager** and **Bulk Controls** now provides a refined confirmation menu.
  - Users can now choose between **Soft Restart (Optimized)**, **Hard Restart (Process Swap)**, and **Reload Plugins**.
- **Synchronized Commands**:
  - The userbot `.restart` and `.reload` commands now offer the same "Soft vs Hard" options as the dashboard, ensuring a consistent management experience.

## [0.0.10.1600H] - 2026-04-30

### 🚀 High-Speed Startup & Session Optimization
- **New Feature: Parallel Session Initialization**:
  - Implemented high-speed session loading using `asyncio.gather` and `Semaphore(10)`.
  - Dramatically reduces startup time for multi-session accounts (up to 80% faster).
- **New Feature: Startup Method Toggle**:
  - Added **Method Switch** in `[Program Controls]` to choose between **Parallel (High Speed)** and **Sequential (Legacy/Safe)**.
  - Allows users to optimize performance based on their server's network stability.
- **Optimized Startup Logging**:
  - Parallelized the "Startup Log" sending process to clear the log queue faster.
  - Added micro-staggering to prevent Telegram spam detection while maintaining high speed.

## [0.0.10.1552H] - 2026-04-30

### ⚙️ Program Controls & Authorization Fix
- **New Feature: [Program Controls] Dashboard**:
  - Centralized submenu in `/settings` for global program behavior management.
  - Added **Group Whitelist Toggle**: Instantly Enable/Disable the group-based sudo authorization system globally.
- **Critical Fix: Group Whitelist Authorization**:
  - Resolved "NOT AUTHORIZED" errors for whitelisted group members.
  - **Full Session Probe**: The system now scans ALL connected userbot sessions (previously limited to first 2) to verify group membership.
  - **Context-Aware Routing**: Commands now prioritize the receiving session for membership checks, significantly improving reliability in groups.
  - **Robust Status Handling**: Fixed case-sensitivity and type mismatch issues in the whitelist status check logic.
- **Enhanced Diagnostics**:
  - Added **Whitelist Features** section to `/start debug` command:
    - View global feature status.
    - Check the number of whitelisted groups in DB.
    - Real-time verification of your own membership status.
- **Logging & Stability**:
  - Fixed a diagnostic bug where group retrieval counts were only logged on errors.
  - Improved `is_sudo_filter` performance by correctly passing client context.

---

## [0.0.10.1550H] - 2026-04-30

### 💎 Profile Manager Pro - Avatar System V2
- **New Avatar Source: Pinterest Scraper**:
  - Implemented a robust **Pinterest Scraper** using mobile browser simulation to fetch aesthetic profile pictures without paid APIs.
  - Added support for multiple avatar sources: `XSGames`, `Pinterest`, `ThisPersonDoesNotExist`, and `RandomUser.me`.
  - Added **Manual Keyword Input** for Pinterest: You can now set custom search keywords (e.g., "Aesthetic Car", "Cyberpunk") per session.
  - Improved synchronization between avatar gender and selected persona gender for all sources.
- **Fault Tolerance & Reliability**:
  - Added robust error handling and fallback logic: If Pinterest or any API is down, the system automatically falls back to secondary sources.
  - Added dynamic "Avatar Link" labels in the preview message showing exactly which source provided the image.
- **UI/UX Enhancements**:
  - New `⚙️ Photo Source` submenu for granular control over session avatars.
  - New `🏷 Set Pin Keyword` feature using interactive `ForceReply` for easy configuration.

---

## [0.0.10.1230H] - 2026-04-30

---

## [0.0.10.1210H] - 2026-04-29### 🚀 Added: Profile Manager Pro Module
- **New Plugin System: `XProfile_Manager_Pro`**
  - Advanced identity management system for multi-session userbots.
  - Modular architecture: Split into **Userbot Logic** (`main.py`) and **Bot Assistant UI** (`bot_handlers.py`) for Altruix compliance.
- **Premium Interactive Dashboard**:
  - Full-featured inline dashboard with pagination for managing many sessions.
  - Added **[First]** and **[Last]** buttons for rapid session navigation.
  - Optimized layout: `[ « ] [n/n] [ » ]`, `[First] [Last]`, and `[ « Back » ]`.
- **Intelligent Identity Generation**:
  - **Auto Bio**: Generate aesthetic bios based on gender using the `Faker` library.
  - **Auto Username**: Generate unique usernames based on name patterns with random alphabets and numbers.
  - **Username Format Settings**: Choose between patterns like `nama_xy123`, `real_namax12`, or `official_nama_999`.
- **Safety & Recovery Features**:
  - **Interactive Confirmation**: Mandatory Yes/No confirmation for all profile-modifying actions to prevent accidental changes.
  - **Undo Change System**: Automatic profile backup storage before updates, allowing users to revert to the previous state with one click.
  - **Persona Lock**: Prevent specific sessions from being affected by bulk updates.
- **Visual Curations**:
  - **Direct Image Preview**: View AI-generated avatars directly in Telegram as photo messages before applying them.
  - **Integrated Caption**: Draft Name, Bio, and Username displayed as a caption for a seamless "What You See Is What You Get" experience.
  - **EXIF Stripping**: Automatic metadata removal from profile photos for enhanced privacy.

### 🏗️ Architecture: Version Centralization
- **New File: `Main/core/version.py`** — Single Source of Truth for `__version__`.
  - `config.py` (`BaseConfig.ALTRUIX_VERSION`) and `client.py` (`self.__version__`) now both import from `version.py`.
  - Eliminates version drift: update one file, all modules stay in sync.

### 🛠️ Core & Stability
- **Shared State Management**: Implemented `STATE` dictionary for real-time task status synchronization between Userbot and Bot Assistant.
- **Anti-Flood Logic**: Integrated asynchronous queues with randomized delays for safe bulk profile updates.

---

## [0.0.10.1190H] - 2026-04-28

### 🚀 Added: Message Pusher Module
- **New Plugin: `xmessage_pusher.py`**
  - Advanced message distribution system supporting multi-type content.
  - Automated sequence: `LOVE QUOTES 1`, `LOVE QUOTES 2`, `MSG IMG`, and `LOVE QUOTES 3`.
  - Content sourced directly from specified channels (e.g., `alphaxbbc`).
  - Integrated `Anon Adm` (Anonymous Admin) promotion for enhanced privacy.
  - Full task synchronization with `xtaskmanager`.
- **Interactive Dashboard: `message_pusher_handlers.py`**
  - Triggered via **Inline Results** for a seamless user experience.
  - Granular control over `Act Delay`, `Batch Act`, and `BA Delay`.
  - Target selection via interactive private message state management.
  - Toggles for individual content blocks (LQ1-3, IMG).
  - Safety confirmation menu before task execution.

### ✨ Enhanced: CreateGroup Optimization
- **Dashboard UI**: Implemented a comprehensive interactive UI for `xcreategroup.py`.
- **Randomization**: Added "Static per Task" random text injection for consistent group naming.
- **Live Preview**: Real-time name pattern preview including injected random strings.
- **Task Monitoring**: Mirroring of the Interactive Progress Dashboard to the Log Group for unified monitoring.
- **Logging**: Improved metrics reporting for batch delays and specific action timing.

### 🎨 UI & UX Refinements
- **Penambahan submenu List Settings untuk memilih antara Nama Akun atau ID Akun di Sessions Manager.**
- **Session Info Dashboard**:
  - Cleaned up aesthetics by removing redundant emojis from Status and Sudo indicators.
  - Enhanced privacy by wrapping **Account Name**, **ID**, and **Username** in spoiler tags.
  - Optimized button layout for better alignment.
- **Help Menu System**:
  - **Dynamic Headers**: Category progress (e.g., `(1/4)`) and total plugin counts are now displayed in the header for Design 2.
  - **Page Navigation**: Added support for jumping directly to specific help pages using `.help <page_number>` (e.g., `.help 3`).

### 📡 Automated Reporting & Connectivity
- **Auto-Ping System**:
  - **Message Splitting**: Implemented automatic splitting for large session reports (80 sessions per part) to prevent hitting Telegram's character limits.
  - **Ping Indicators**: Added clear labeling to distinguish between `SYSTEM - AUTO PING` and `MANUAL - PING ALL` reports.
  - **Flood Safety**: Added rate-limiting (0.5s delay) between split message parts to avoid flood waits.

### 🛠️ Core & Stability
- **Version Bump**: Updated project core version to `0.0.10.1190H`.
- **Session Management**: Improved session status reporting and auto-restart logic after session updates.
- **Bug Fixes**:
  - Resolved `ImportError` in Pyrogram v2 by standardizing `ParseMode` imports.
  - Standardized client routing (User vs Bot) for cleaner command execution.
  - Added robust traceback and logging to all new modules for easier troubleshooting.
  - Fixed `AttributeError: 'NoneType' object has no attribute 'edit'` in Inline Dashboard mode.
  - Resolved `KeyError` in `ba_delay_dec` by optimizing regex for numeric adjustment buttons.
  - Improved Anonymous Admin support for `.pushmsg` command.
  - Added "View Targets" sub-menu with "Clear All" functionality.
  - Refined UI aesthetics by removing redundant emojis and switching to text indicators (Yes/No).
  - Implemented interactive +/- buttons with small/large step adjustments.
  - Fixed `PHONE_NOT_OCCUPIED` error by ensuring numeric Chat IDs are handled as integers.
  - Enhanced target parsing to support multiple separators (space, comma, semicolon).
  - Implemented **Full Session Isolation**: Config states and active tasks are now uniquely keyed per userbot session to prevent data leakage in multi-account management.
  - Fixed **Anonymous Admin mode**: `iuser_check` decorator now falls back to `client.me` when `from_user` is `None`, allowing `.pushmsg` to work in anon admin groups.
  - Fixed state key mismatch between `pushmsg_cmd` and dashboard handlers (migrated to composite `uid_sessionIndex` format).
  - Added dynamic **Disable/Enable All Session** toggle in Global Session Settings with intelligent status detection and safety confirmation.
  - Enhanced **Sessions Manager Dashboard**: Added real-time counters for **Enabled** and **Disabled** sessions in the main list header.
  - Optimized **Main Dashboard UI**: Relocated **Alliance Manager** to the home screen and added a global **Close** button for faster navigation.
  - Hardened **Command Security**: Implemented strict `outgoing` message validation in decorators to prevent command hijacking by other anonymous admins in shared groups.
  - Refactored session list generation to be fully asynchronous for improved performance.

---

## [0.0.10.0959H] - 2025-12-25
### 🏗️ Core Architecture & Performance
- **AltruixClient 2.0**: Completely refactored client initialization for high-concurrency multi-account management.
- **Optimized Event Loops**: Integrated `winloop` (Windows) and `uvloop` (Linux) policies for maximum I/O performance.
- **Hybrid Database**: Support for **MongoDB** (Cloud) and **LocalDatabase** (JSON-based) with automatic migration logic.
- **Smart Caching**: Implemented TTL caching for Sudo users, prefixes, and group memberships to reduce database load.
- **Global Exception Handling**: Added centralized error catching for asyncio tasks and Pyrogram dispatchers.

### 🛡️ Privacy & Security
- **PM Security**: Integrated `PM_Security.py` with automated whitelist/blacklist and anti-spam controls.
- **Group Whitelist**: New system to delegate sudo permissions based on group membership.
- **Stealth Logging**: Truncated log format to prevent sensitive data leakage and handle long tracebacks.

### 🛠️ Advanced Plugins & Features
- **Broadcasting**: `xauto_pro_gcast.py` - Pro-grade broadcast system with advanced filtering and reporting.
- **Group Management**: `xalliance.py` & `xpurgeme_userbot.py` - High-speed deletion and alliance-wide controls.
- **Activity Tracking**: `xmention_logger_user` and `xpm_logger_user` for comprehensive interaction monitoring.
- **Task Management**: Initial implementation of `xtaskmanager` for cross-session task tracking.

### 🚀 Deployment & Stability
- **Platform Detection**: Automatic detection and optimization for **Sevalla**, **Heroku**, **Windows**, **Linux**, and **Termux**.
- **Monkey-Patching**: Implemented safety patches for Pyrogram's `Message.edit` and `Message.delete` to avoid common RPC errors.
