# AltruixX Changelog

All notable changes to the **AltruixX** project from version **0.0.10.0959H** to the latest.

---

## [0.0.10.2411H] - 2026-05-10

### 🏗️ CreateGroup Plugin: UI Persistence & Feature Reinstatement
- **New Feature: Persistent Dashboard Configuration**:
  - Implemented a dedicated storage system (`xcreategroup_user_configs.json`) to persist user settings across restarts and sessions.
  - **Automated Saving**: Integrated `save_user_cg_config` into all interactive handlers (Toggle, Adjust, Set Value, and Message Input).
  - **Smart Loading**: The dashboard now automatically recovers the user's last saved configuration instead of resetting to defaults.
- **New Feature: Dashboard Restore Access**:
  - Added the **"Restore Tasks"** button directly to the main dashboard for faster access to interrupted task management.
- **Restored: Quote Block Formatting**:
  - Reinstated the **Quote Block** toggle in the interactive UI, allowing users to enable/disable `<blockquote expandable>` tags for love quotes.
  - Fixed logic flow to ensure the setting is correctly passed to the background execution loop.
- **Fixed: Critical Stability & Code Integrity**:
  - Resolved missing control buttons (**Pause, Resume, Stop**, etc.) when starting tasks from the Dashboard by ensuring the control message is properly initialized with the interactive UI via the **Bot Assistant client**.
  - Resolved `KeyError` in `creategroup_loop` by standardizing on `task_key` (TID) for all dictionary accesses, preventing crashes when starting or resuming tasks.
  - Resolved `NameError: name 'CREATEGROUP_TASKS' is not defined` in the cached handler by implementing lazy imports to avoid circular dependency issues.
  - Fixed missing `import os` in the handlers file that previously caused persistence functions to fail.
  - Added "« Prev" and "Next »" navigation buttons to manage long lists of cached tasks efficiently.
- **Improved: Assistant Bot Invitation & Reliability**:
  - Implemented **Fallback Logic**: If inviting the bot fails during group creation (e.g., due to privacy settings), the system now creates the group first and logs a clear warning instead of failing.
  - Added specific error detection for **USER_PRIVACY_RESTRICTED** and other common API blocks for clearer diagnostics.
  - Ensured the `invite_bots` toggle is strictly respected across all group types (Basic, Supergroup, Channel).
- **Enhancement: Restore Tasks UI/UX**:
  - Implemented structured pagination in the format `[« Prev] [n/total] [Next »]` for the task list to prevent excessive message length.
  - Synchronized all button styles in the Restore Tasks menu with the account/session configuration (`user_style`).
  - Added interactive action buttons (**Resume**, **Ignore**, **View**) for each cached task.
  - Integrated a **Task Info Alert** popup when clicking task labels for instant progress summaries.
- **Improved: UI Consistency**:
  - Updated `HANDLER_VERSION` to **`0.3.0`** to mark the transition to a persistent configuration model.
  - Standardized button labels and emoji usage across the dashboard.

---

## [0.0.10.2410I] - 2026-05-10

---

## [0.0.10.2410H] - 2026-05-10

### 🏗️ CreateGroup Plugin: Standardized Threading & Logic Hardening
- **New Feature: Standardized Log Threading**:
  - Implemented proper message threading in the **Log Group**. All progress updates and notifications now reply to the task's **Control Message** (Dashboard), creating a clean, linear history.
  - Added `reply_to_message_id` support to `send_log_notification` and all critical log calls.
- **New Feature: Quote Block Formatting**:
  - Added **Quote Block** setting (default: **True**) to wrap love quotes in `<blockquote expandable>` tags for a premium aesthetic.
  - Integrated a new toggle in the interactive dashboard to enable/disable this formatting.
- **Improved: Chat Pin/Unpin Management**:
  - **Auto-Pin**: Processed chats are now pinned by default (`temp_pin` default changed to **True**) for better visibility during kustomization.
  - **Auto-Unpin**: Implemented automatic unpinning in the `finalize` step to keep the user's dialog list clean after completion.
- **Improved: Task Recovery & Consistency**:
  - **Naming Consistency**: Persisted `static_rand_text` in the task state, ensuring resumed tasks maintain the same name pattern after a restart.
  - **Reply Consistency**: Ensured that even resumed tasks correctly identify and reply to their recovered control messages.
- **Fixed: Logic & Parsing Errors**:
  - Resolved `TypeError: object of type 'bool' has no len()` by correctly handling `msg_img` as a boolean flag.
  - Fixed `AttributeError: 'Client' object has no attribute 'pin_chat'` by using raw API `ToggleDialogPin` as a fallback.
- **Improved: Diagnostics & Traceback**:
  - Integrated `traceback.format_exc()` into all critical error handlers across `xcreategroup.py` and `xmessage_pusher.py`.
  - Detailed stack traces are now sent to the **Log Group** inside `<blockquote expandable>` for instant debugging without needing terminal access.
- **Hardening: Synchronized Content**:
  - Synchronized `love_quotes` and media content between `xcreategroup.py` and `xmessage_pusher.py` for operational parity.

### 📡 Message Pusher: Parity & Client Consistency
- **Improved: Operational Parity**:
  - Synchronized all content (Quotes 1-3, Image Lists) and formatting to match the `CreateGroup` plugin.
  - Updated Quote 3 to use the **User Client** (Account) instead of Bot for a more natural interaction flow.
- **Standardization**: Updated emojis, icons, and block formatting to ensure a unified "AltruixX" brand identity across all automation modules.

---

## [0.0.10.2408H] - 2026-05-08

### 🏗️ CreateGroup Plugin: Task Recovery & Resumption
- **New Feature: Automatic Task Recovery**:
  - Implemented `check_interrupted_tasks` to scan for tasks that were interrupted by a restart.
  - Sends a recovery notification to the **Log Group** with a **"⏯ Resume Task"** button for manual continuation.
- **Improved: Resumption Logic**:
  - Modified `creategroup_loop` to accept `is_resume` parameter and start from the last saved `current_index` instead of restarting from zero.
  - Added automatic recovery of the control message (Stop/Pause/Resume buttons) for seamless re-synchronization.
- **Hardening: State Persistence**:
  - `account_name` is now persisted in `xcreategroup_cache.json` for display during recovery without extra API calls.
  - Task state (`running`) is correctly set to `True` and `task_obj` is updated when resuming.

### 📡 Message Pusher: Dashboard Sender Identity
- **New Feature: Sender Info Display**:
  - Added `• Sender:` field to the Message Pusher dashboard showing the active account name.
  - Dynamically displays "Anonymous Adm" prefix when the Anon Admin toggle is enabled.
- **Improved: Dashboard Structure**:
  - Added `Info:` header to the dashboard for better visual separation of task metadata.
- **Version Bump**:
  - **Plugin Version**: `0.1.12`

### 🛠 Power Tools: Critical `.restart` Command Fix
- **Critical Fix: Broken Decorator Chain**:
  - Identified and resolved the root cause of `.restart` and `.reload` commands silently failing.
  - **Root Cause**: Stacking two `@register_on_cmd` decorators caused the inner wrapper's `parse_` check to reject the command name (e.g., `.restart` was validated against `["reload"]` and silently dropped).
  - **Fix**: Combined both commands into a single `@register_on_cmd(["restart", "reload"], ...)` decorator call.

### 🔇 Help Menu: Error Suppression & Performance
- **Fixed: `QUERY_ID_INVALID` Error Spam**:
  - Updated `iuser_check` decorator in `decorators.py` to silently handle `QueryIdInvalid`, `MessageIdInvalid`, and `TimeoutError` — preventing noisy error logs for naturally expired queries.
  - Updated `CustomClient.invoke` in `types/client.py` to recognize `QueryIdInvalid` as a **Permanent Error**, stopping redundant 5x retry cycles.
- **Optimization: Plugin Counting**:
  - Replaced expensive `glob.glob()` disk I/O in `get_total_plugins()` with memory-cached `Altruix.plugin_categories` lookup for significantly faster help menu rendering.
- **Hardening: Inline Query Resilience**:
  - Added `SetInlineBotResults` and `AnswerInlineQuery` to the non-critical operations list, preventing crashes from failed inline responses.

---

---

## [0.0.10.2410H] - 2026-05-10

### 🏗️ CreateGroup Plugin: Task Recovery & Logic Hardening
- **Standardized Task ID (TID)**:
  - Transitioned from user-based IDs (e.g., `creategroup_123`) to a robust **TID system** (e.g., `#CGabcd`).
  - This enables multiple concurrent tasks per user and prevents "Ghost Task" overwrites in the cache.
- **Robust Task Recovery**:
  - Improved `check_interrupted_tasks` to wait for session stability before scanning for interrupted tasks.
  - Implemented automatic pruning of "Ghost Tasks" (already completed or corrupted) during startup.
- **JSON Serialization Hardening**:
  - Implemented a recursive `make_serializable` converter to handle `datetime`, `asyncio.Event`, and other non-serializable objects in `xcreategroup_cache.json`.
  - Fixed `TypeError: Object of type datetime is not JSON serializable` during cache saves.
- **Privacy & Security Enhancements**:
  - **Anonymous Mode Fix**: The owner is now promoted to **Anonymous Admin BEFORE** the assistant bot is invited, ensuring the owner's identity is never exposed in the group logs.
  - **Account Privacy**: Removed sensitive account information (`👤 Account: ...`) from both basic and supergroup welcome messages.
- **UI/UX Improvements**:
  - Added **"View Last Chat"** inline button to recovery notifications, allowing users to inspect the last group/channel created before resuming.
  - Fixed various typos and improved formatting in initialization messages.
- **Bug Fixes**:
  - Resolved `TypeError: 'module' object is not callable` by removing dangerous glob imports (`from pyrogram.types import *`) that shadowed the built-in `list` function.
  - Fixed missing initialization checks and indentation errors in the main execution loop.

---

## [0.0.10.2407H] - 2026-05-10


### 🚀 Smart Install: Detailed Progress & Transparency
- **New Feature: Real-Time Download Progress**:
  - Implemented manual download logic for URL-based dependencies using `urllib`.
  - Displays real-time file size (MB) and percentage progress in the terminal.
- **Improved: Installation Transparency**:
  - Unlocked `pip` output for non-cached installations, allowing users to see "Collecting" and "Downloading" details.
  - Integrated filtered `pip` output directly into the Altruix log style for a seamless diagnostic experience.
  - **Optimized Transparency**: Switched to an opt-out filter that shows all `pip` activity (including file writing and setup scripts) while suppressing only noisy progress bars, ensuring the installation never appears "stuck".

## [0.0.10.2406H] - 2026-05-06

### 📊 Diagnostic Ecosystem: Loading Progress & Log Standardization
- **New Feature: Session Loading Progress [N/N]**:
  - Added real-time progress indicators (e.g., `[1/5]`) to connection logs.
  - Uses `contextvars` to ensure accurate tracking even during high-speed **Parallel** loading.
- **Improved: Log Aesthetic & Anti-Noise**:
  - **ANSI Stripping**: Implemented automatic ANSI color stripping for `altruix.log` to ensure clean, readable file logs while maintaining vibrant terminal output.
  - **Anti-Double-Tagging**: Added logic to prevent redundant prefixing of messages that already contain the `[Altroid-X]` tag.
  - **Redundancy Cleanup**: Removed the `[_run_once]` function prefix as it's now covered by the `[📍 module.function]` anchor at the end of each line.
- **Hardening: Git Security & Privacy**:
  - Updated `.gitignore` to include high-risk local folders: `DATABASE/`, `DATA/`, `temp/`.
  - Added specific ignores for sensitive binaries (`deno.exe`) and general `*.exe` rules to prevent accidental leakage to GitHub.
- **Optimization: Resource Management**:
  - Removed the `system_watcher` background thread to eliminate noisy "System Health" logs and reduce background CPU/RAM overhead.

## [0.0.10.2405H] - 2026-05-05 (Current)

### 🧹 Purgeme Tool: Sender Identity & UI Synchronization
- **New Feature: Sender Identity Selection ("From")**:
  - Implemented the ability to choose which identity to target for deletion: **Me** (Main Account) or any **Administered Channel/Group**.
  - **Comprehensive Detection**: Uses dual-method detection (`GetSendAs` + `GetAdminedPublicChannels`) to ensure all valid sender options are available.
- **New Feature: Notification Identity Sync ("Notif")**:
  - **Renamed Stealth to Notif**: Rebranded the silent mode to a clearer "Notif" toggle.
  - **Identity Synchronization**: When a channel is selected as the sender, completion notifications are now sent **AS that channel** using `SaveDefaultSendAs` logic.
  - **Default State**: Changed default Notification state to **OFF** to ensure a non-spammy experience in groups.
- **Improved: UI Layout & Transparency**:
  - **Row-Based Layout**: Optimized the Purgeme menu with a clean, row-based button arrangement for better mobile usability.
  - **Live Preview**: The "Notif" and "From" buttons now feature a live preview of the selected identity (e.g., `Notif: OFF (as @channel)`).
- **Hardening: Debugging & Stability**:
  - **Detailed Tracebacks**: Integrated full stack-trace logging for Inline Query, Callback, and Command execution errors to identify root causes instantly.
  - **Namespace Fix**: Corrected `GetSendAs` API path to `pyrogram.raw.functions.channels.GetSendAs` for compatibility with the latest Telegram API.
- **Documentation & Localization**:
  - Fully updated the `Info` sub-menu and `.purgeme help` documentation in both English and Indonesian.
  - Synchronized localization keys for all new UI elements.
- **New Feature: Keep Recent (Safety Buffer)**:
  - Added a dedicated "Keep Recent" setting to skip the most recent `N` messages in the chat.
  - Ensures active conversations are protected from deletion regardless of the search mode (Oldest/Newest).
  - Integrated into the UI with a new sub-menu for granular adjustment.
- **Improved: Send As Capability Detection**:
  - Automatically identifies if the current group supports sending as a channel.
  - Displays a real-time status indicator (`Supported` vs `Limited`) in the dashboard header.
- **Version Bump**:
  - **Bot Plugin**: `0.0.322`
  - **Userbot Plugin**: `0.0.444` (Stability & Features)

## [0.0.10.2318H] - 2026-05-03

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
