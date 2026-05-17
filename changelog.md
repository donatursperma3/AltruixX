# AltruixX Changelog

All notable changes to the **AltruixX** project from version **0.0.10.0959H** to the latest.

---

## [0.0.10.2441I] - 2026-05-17

### 🏓 Auto Ping All: Detailed Log Reports
- **Enhanced: Auto Ping Report Logs**:
  - Integrated real-time **Ping Mode** (e.g. `🔍 Test + Online`, `📡 Test + Message`, `🔍 Test Only`) and **Interval** (e.g. `1h 11m`, `5m`) settings directly into the mass-latency report sent to the log group chat.
  - Formats raw database/cache interval seconds into elegant human-readable durations.

## [1.0.182] - 2026-05-18

### 📦 YTDL Manager: Premium YouTube Chapter Splitter
- **New Feature: Premium YouTube Chapter Splitter & Slicer**:
  - Added a dynamic `📦 Split Chapters: {status}` control button directly to the YTDL main dashboard.
  - Implemented the `📦 Pengaturan Pembagian Bab (Split Chapters)` sub-menu dynamically listing all detected video chapters with clean start/end times and descriptions.
  - Symmetrically incorporates the chapter split selection into the single confirmation download screens (e.g. `[Split Chapters: 5 bab]`).
- **Enhanced: Local Slicing & Sequence Upload Pipeline**:
  - Downloads the raw video from YouTube only once, then processes local slicing locally via FFmpeg, saving massive amounts of network bandwidth.
  - Applies all user-selected custom speed, volume, and watermark parameters to each individual chapter slice.
  - Implemented sequentially automated slicing, ID3v2 metadata embedding (titles, artists, albums, thumbnail cover art), backup logging, and uploads with real-time status bars showing sequence progress (`Uploading 1/5`, `Uploading 2/5`).
- **Version Bumps**:
  - **Assistant Bot Plugin**: `1.0.175`
  - **YTDL Core Engine**: `0.0.263`

---

## [1.0.181] - 2026-05-18

### 🎥 YTDL Manager: Premium Volume & Decibel Booster Sub-Menu
- **New Feature: Premium Volume Booster & Decibel Adjuster**:
  - Integrated a premium `🔊 Volume: {volume}` control button on the YTDL main dashboard, grouped symmetrically with the `⚡️ Speed` button.
  - Implemented the `🔊 Pengaturan Volume & Boost (Desibel)` sub-menu containing 13 widely varied, versatile volume options: **10% (-20 dB), 25% (-12 dB), 50% (-6 dB), 75% (-2.5 dB), Original, 125% (+2 dB), 150% (+3.5 dB), 175% (+5 dB), 200% (+6 dB), 250% (+8 dB), 300% (+9.5 dB), 400% (+12 dB),** and **500% (+14 dB)**.
  - Automatically incorporates custom volume adjustments into the single and double-confirmation download screens (e.g. `[Volume: 200% (+6 dB)]`).
  - Logs custom volume settings directly in the final uploaded media file captions for complete traceability.
- **Enhanced: FFmpeg Unified Speed & Volume Audio Filter Chaining**:
  - Dynamically constructs a parser helper `parse_volume_to_ffmpeg` that cleanly maps descriptive desibel/percentage strings into precise FFmpeg volume factor floats.
  - Combines the volume settings filter (`volume=X.XX`) and chained tempo scaling filters (`atempo=X.XX`) into a single, unified `-af` filter chain separated by commas, preventing FFmpeg from crashing or dropping filter pipelines.
  - Automatically enforces high-quality audio re-encoding (`-c:a aac` for video and `-acodec libmp3lame` for raw MP3 files) and disables standard stream copying (`-c:a copy`) when custom volume adjustment is engaged.
- **Hardened: Comprehensive Exception Safety & Traceback Logging**:
  - Wrapped all 4 newly introduced callback handlers (`ytdl_speed_menu_cb`, `ytdl_set_speed_cb`, `ytdl_volume_menu_cb`, `ytdl_set_volume_cb`) and core speed/volume parsing utilities inside thorough `try-except Exception as ex` blocks.
  - Ensures any runtime failures are fully logged alongside granular tracebacks (`Altruix.log(...)` and `traceback.format_exc()`), and elegantly dispatches high-visibility user-facing callback alert notifications (`show_alert=True`) to prevent the inline button interface from freezing.
- **Version Bumps**:
  - **Assistant Bot Plugin**: `1.0.174`
  - **YTDL Core Engine**: `0.0.262`

---

## [1.0.180] - 2026-05-17

### 🎥 YTDL Manager: Speed Multiplier, Custom Video Bitrate & Audio Language Fixes
- **New Feature: Premium Video & Audio Speed Multiplier**:
  - Added a dynamic `⚡️ Speed: {speed_val}` control button directly to the YTDL main dashboard, grouped cleanly with the `Sender` selection button.
  - Implemented the `⚡️ Pilih Kecepatan Media` sub-menu containing comprehensive, versatile multiplier options: **0.25x, 0.50x, 0.75x, 1.00x, 1.25x, 1.50x, 1.75x,** and **2.00x**.
  - Dynamically recalculates and formats the estimated output duration in the Telegram caption to reflect the adjusted media length (`duration = int(duration / speed_float)`).
  - Automatically incorporates the chosen speed setting into the single and double-confirmation screens, as well as the final uploaded media file caption.
- **Enhanced: FFmpeg Audio & Video Speed Scaling Pipeline**:
  - Leverages hardware-efficient `-vf "setpts=(1/S)*PTS"` filters to smoothly scale video speed.
  - Dynamically constructs a chained series of `atempo` filters for audio track speed adjustments (since a single `atempo` only accepts ranges within `[0.5, 2.0]`). Correctly handles extreme values such as `0.25x` (constructs `atempo=0.5,atempo=0.5`) and others seamlessly.
  - Automatically disables stream copy mode (`-c:a copy`) when custom speed is selected, dynamically engaging safe high-quality audio re-encoding (`-c:a aac` for video containers and `-acodec libmp3lame` for raw MP3 files).
- **New Feature: Video Bitrate Selection Dashboard**:
  - Dynamically swaps between `Audio Name` / `Artist` settings (for audio format) and a new `Video Bitrate` button (for video format) to maintain a highly streamlined and context-aware UI.
  - Implemented the `📺 Pilih Bitrate Video` sub-menu with premium options: **Original, 8 Mbps, 5 Mbps, 3 Mbps, 1.5 Mbps,** and **700 Kbps**.
  - Displays the selected bitrate on both the single and double-confirmation screens, and logs it in the final uploaded media caption.
- **Improved: ffmpeg Processing Pipeline**:
  - Seamlessly maps selected bitrate options to actual ffmpeg `-b:v` parameters (e.g. `8M`, `3M`, `700k`).
  - Automatically forces and performs video re-encoding (displaying `Mengompresi Video...` status) to achieve the target file compression if a custom bitrate is specified.
- **Fixed: Audio Language Selection**:
  - Fixed a callback query regex mismatch in `xyt_tools_bot.py` by converting `[\w-]+` to `(.+)`, allowing the bot to correctly match and capture audio language tracks with spaces and parentheses (e.g. `"en (Original)"`).
  - Wrapped cleaned language tokens in single quotes (e.g. `[language*='clean_lang']` and `[language_note*='clean_lang']`) in `ytdl_core.py` to prevent any yt-dlp selector string parsing syntax failures.
  - **dubbed multi-audio tracks extraction & download**: Integrated `--extractor-args "youtube:player_client=all"` into all metadata queries and media download commands in `ytdl_core.py`. This forces YouTube to serve all regional, dubbed, and alternative audio track streams that were previously hidden from default/basic player clients.
- **Enhanced: Help & Guide Version Menu**:
  - Integrated dynamic, real-time query detection for system binary CLI dependencies on Page 2 of the guide menu.
  - Asynchronously reads and displays the exact installed version of **FFmpeg** and detects whether **yt-dlp** or **youtube-dl** is the active CLI downloader engine, outputting their precise versions alongside plugin and core version information.
- **Fixed: yt-dlp Subprocess Exit Race Condition**:
  - Added explicit `await process.wait()` in `run_yt_dlp_with_progress` to guarantee the subprocess has fully exited and `process.returncode` is populated, avoiding blank errors due to exit code races.
  - Created a robust fallback error parser in `_ytdl_single_unit` that automatically scans the `stdout` history for any `ERROR:` statements if `stderr` is empty, presenting the exact error description cleanly.
- **Version Bumps**:
  - **Userbot Plugin**: `1.0.126`
  - **Assistant Bot Plugin**: `1.0.173`
  - **YTDL Core Engine**: `0.0.245`

## [1.0.179] - 2026-05-17

### 🤖 Bulk Controls: Bulk Append Bot Tokens Exception Hardening
- **New Version: [0.0.10.2441I]**:
  - Implemented 100% try-except coverage for all 6 Custom Bot Token append and parsing functions/callbacks in `bulk_handlers.py`.
  - Added traceback formatting (`traceback.format_exc()`) to ensure granular error diagnostics are fully logged upon failure.
  - Ensured safe UI fallback answers and detailed traceback error replies to prevent the dashboard from freezing during any execution exceptions.

### 🤖 Bulk Controls: Export Bot Tokens Exception Hardening
- **Version: [0.0.10.2440I]**:
  - Implemented 100% try-except coverage for all 4 Custom Bot Token export functions/callbacks in `export_handlers.py`.
  - Added traceback formatting (`traceback.format_exc()`) to ensure granular error diagnostics are fully logged upon failure.
  - Ensured safe UI fallback answers to prevent the dashboard from freezing during any execution exceptions.

### 🤖 Bulk Controls: Export & Bulk Append Custom Bot Tokens
- **Version: [0.0.10.2439I]**:
  - Implemented **Export Bot Tokens** feature under Bulk Controls Manager, querying the MongoDB `custom_bots` collection and matching active session owners to map each token to its session index/phone number, generating a secure file download sent to the PM.
  - Implemented **Bulk Append Bot Tokens** feature with stateful input processing in `session_info.py` and `bulk_handlers.py`.
  - Added support for ZIP, TXT, and raw multi-line text input, featuring a smart parser that handles multi-format tokens (`bot_id:token_hash`, `session_index:bot_id:token_hash`, and `phone:bot_id:token_hash`), mapping them intelligently to available sessions and initiating them dynamically.
  - Updated Bulk Controls dashboard layout with sleek, symmetrical design integration for both session-level and bot-level export/append controls.

### 🏓 Auto Ping All: Test + Online Mode
- **Version: [0.0.10.2438I]**:
  - Added new `'Test + Online'` mode to Auto Ping All Manager.
  - Implemented explicit Telegram presence updates using raw RPC `account.UpdateStatus(offline=False)` during the ping cycle to keep all active accounts active and prevent automated session deletion/revocation due to inactivity.
  - Updated the Auto Ping Dashboard UI with dynamic mode button cycling through all 3 modes: `Test Only` 🔍, `Test + Message` 📡, and `Test + Online` 🟢.

### 🛠️ Custom Bot: Comprehensive Exception Wrapping & Traceback Logging
- **Version: [0.0.10.2437I]**:
  - Implemented 100% try-except coverage for all 15 callback/message handlers in `custom_bot_handlers.py`.
  - Added robust traceback formatting (`traceback.format_exc()`) to ensure detailed diagnostics are instantly logged upon any runtime failures.
  - Implemented safe callback answer fallbacks to ensure user interfaces never hang when an unexpected error occurs.

### 🛠️ Custom Bot: Inline Callback Safety & Handler Priority
- **Version: [0.0.10.2436I]**:
  - Fixed `AttributeError: 'NoneType' object has no attribute 'edit'` crash on all 5 `cb.message.edit()` calls by migrating to `edit_cb()` which safely handles inline callbacks where `cb.message` is `None`.
  - Elevated token input handler priority from `group=-1` to `group=-100` to prevent other Group -1 handlers from intercepting token messages.

### 🛠️ Custom Bot: UI Polish & Stability Fixes
- **Version: [0.0.10.2435I]**:
  - Fixed "Double Icon" issue in Custom Bot Manager messages by removing redundant hardcoded emojis.
  - Cleaned up the status line (⚡) by removing redundant status emojis.
  - Resolved a critical `NameError` in `custom_bot_handlers.py` that prevented token inputs from responding.
  - Removed high-priority diagnostic handlers after verifying system stability.

### 🛠️ Custom Bot: Propagation Fix & Group -1 Hardening
- **Fixed: Custom Bot Token Unresponsiveness**:
  - Resolved a critical bug in high-priority message handlers (Group -1) where un-awaited propagation calls caused the bot to swallow private messages.
  - Ensures the dashboard correctly responds to token inputs for session customization.
- **Improved: Token Input Security & Logic**:
  - Added debug logging for token receipt and session index validation.
  - Fixed critical `NameError` bugs (missing `logging` and `enums` imports) that prevented the module from loading.
  - Implemented robust `session_client.me` fetching to prevent attribute errors during bot initialization.
  - Hardened `BotManager` persistence logic with comprehensive error handling for `save_token` and `delete_token` operations.
  - Verified and optimized dual-database support (MongoDB & Local JSON) for custom bot token storage using atomic upserts.
  - Integrated `user_env_manager_state` into the global `/cancel` logic for easy input reset.
  
### 🗄️ Database & Persistence: Append/Restore Hardening
- **Fixed: Data Loss during 'Append DB'**:
  - Resolved a race condition where unsaved memory changes (like new bot tokens) were lost when performing a database append.
  - Implemented mandatory `save_now()` sync before starting any restore or append operations.
- **Improved: JSON Merge Reliability**:
  - Hardened `_merge_json` logic to prevent silent data wipes if the primary database file is temporarily unreadable.
  - Added detailed merge logging to track collection sizes (e.g., custom bots) before and after synchronization.

### 🚀 Startup Settings: Per-Session Test Mode
- **New Feature: Per-Session 'Test' Mode**:
  - Added a new `test` state to Startup Message settings, allowing users to verify session connectivity without sending an individual "I'm alive" message to the Log Group.
  - Useful for stealth startups or multi-account pings without log clutter.
- **Improved: Startup UI & Logic**:
  - Unified `on` and legacy `default` states for clearer user configuration.
  - Updated both parallel and sequential startup engines in `client.py` to respect the `test` status while maintaining full report accuracy.
- **Enhanced: Split Log Reporting**:
  - Confirmed and validated automatic message splitting (Part N/N) for the Startup Session Report to handle thousands of accounts gracefully.

---

## [1.0.178] - 2026-05-16

### ⚙️ CreateGroup: Smart Recovery Indexing
- **New Feature: Smart Account Re-Indexing**:
  - Implemented a "Smart Recovery" logic that dynamically reconstructs account indicators (`1/N`) for interrupted tasks.
  - Groups tasks by owner and startup time (within a 5-minute window) to automatically assign the correct sequence.
  - Ensures that even tasks started before the index-storage update will now show accurate positioning in the Log Group.
- **Improved: Data Persistence**:
  - Modified the creation loop to save and sync account indicators to the task parameters whenever a task is resumed.
  - Guarantees that once a task is recovered, its positioning data remains persistent across all future restarts.

---

## [1.0.177] - 2026-05-16

### ⚙️ CreateGroup: Bulk Resume & UI Hardening
- **Fixed: Resume All for Paused Tasks**:
  - Corrected the `Resume All` logic to include tasks that were manually paused.
  - Ensures that pressing the button correctly triggers the resume event for all active background loops.
- **Improved: UI Stability**:
  - Added specific error suppression for `MESSAGE_NOT_MODIFIED` when refreshing the task dashboard.
  - Prevents the bot from logging unnecessary "Warning" alerts when the UI content hasn't changed during a refresh.
- **Enhanced: Task Registry Sync**:
  - Improved synchronization between the local task dictionary and the global system registry during bulk actions.

---

## [1.0.176] - 2026-05-16

### ⚙️ CreateGroup: Full UI Parity for Indicators
- **New Feature: Account Indicator in Recovery Alert**:
  - Extended the account indicator (e.g., `1/100`) to the **"Interrupted Task Detected"** recovery message.
  - Ensures full consistency across all task-related notifications in the Log Group.
  - Users can now identify which account in a multi-session sequence was interrupted immediately upon system restart.

---

## [1.0.175] - 2026-05-16

### ⚙️ CreateGroup: Enhanced UI & Context
- **New Feature: Account Indicator in Control Panel**:
  - Added a dynamic counter to the **Task Control Panel** header (e.g., `🚀 Task Control Panel 1/5`).
  - Provides immediate context on the account's position within a multi-session task.
  - Implemented parameter persistence, ensuring the indicator remains accurate after task resumption or system restart.

---

## [1.0.174] - 2026-05-16

### ⚙️ CreateGroup: Enhanced Error Reporting & Logic
- **New Feature: Push Error Notifications**:
  - Implemented a "Push" mechanism for creation failures. Instead of just editing the previous log entry, the bot assistant now sends a fresh, prominent message to the **Log Group** when group/channel creation fails.
  - Ensures users are immediately alerted to critical issues without needing to watch the consolidated log message.
- **Fixed: CHANNELS_TOO_MUCH Handling**:
  - Added specific detection for the "Too Many Channels" limit.
  - When this terminal error is detected, the task now stops gracefully for that account and sends a clear termination alert to the Log Group.
- **Improved: Diagnostic Clarity**:
  - All creation error logs now include the Account Name and the specific Telegram error code for faster troubleshooting.

---

## [1.0.533] - 2026-05-16

### 🔄 Auto Pro Gcast: Paginated Account Sync
- **New Feature: Paginated Sync List**:
  - Implemented a robust 6-item pagination system for the "Sync from Account" sub-menu.
  - Handles large numbers of active sessions gracefully without exceeding Telegram's message length limits.
- **Improved: Navigation Controls**:
  - Added a full suite of navigation buttons in a structured layout:
    - Row 1: **[ Prev ]**, **[ n/n ]** (Page Indicator), **[ Next ]**
    - Row 2: **[ First ]**, **[ Last ]**
    - Row 3: **[ Back ]**
- **Refined: Logic Flow & UX**:
  - Updated the **[ Cancel ]** button in the sync confirmation menu to return the user to the exact same page they were browsing, maintaining navigation context.
  - Bumped plugin version to `1.0.533`.

---

## [1.0.173] - 2026-05-16

### 🛠️ CreateGroup: Advanced Pacing & Multi-Account Hardening
- **New Feature: Account Delay (Staggered Startup)**:
  - Added **"Delay/Account"** adjustment parameter to stagger the activities of multiple sessions.
  - Helps avoid Telegram's rate-limiting and detection by ensuring each account starts its execution loop with a user-defined pause (Default: 0.5s).
  - Integrated into the main dashboard, adjustment sub-menus, and manual input handlers.
- **Bug Fix: Bulk Action Global Sync**:
  - Refactored **[Pause All]**, **[Resume All]**, and **[End All]** to synchronize with the global `_TASK_REGISTRY`.
  - Prevents background loops from automatically resuming when they detect local/global state mismatches.
- **Bug Fix: Dashboard Header Duplication**:
  - Fixed a Python string precedence bug that caused the dashboard header to repeat 15 times.
  - Implemented strict **TID Sanitization** to prevent decorative text from polluting the internal state.
- **Bug Fix: Cache Manager IndexError**:
  - Resolved a crash when navigating the **Restore Tasks** menu caused by incorrect regex group access.
  - Refartored parameter extraction to use robust string splitting instead of context-dependent regex matches.

---

## [0.0.10.2435I] - 2026-05-17
- **Fixed: Redundant UI Icons**:
  - Removed double icons in Custom Bot Manager templates where localization strings already provided them.
  - Cleaned up status display by removing redundant status emojis.
- **Improved: Module Loading & Stability**:
  - Resolved critical `NameError` in `custom_bot_handlers.py` that caused token input to be unresponsive.
  - Removed diagnostic handlers after successful verification of the custom bot flow.

## [0.0.10.2434I] - 2026-05-17

### ⚙️ Program Controls: Automated Startup Changelog
- **New Feature: Automated Startup Changelog**:
  - Integrated an automated system to broadcast the latest updates to the **Log Group** immediately after program restart/reload.
  - Fetches and formats the most recent entry from `changelog.md` into an aesthetic, expandable blockquote.
  - Implemented intelligent message truncation (3600 chars) and HTML sanitization to prevent Telegram API errors.
- **New Feature: Changelog Notification Toggle**:
  - Added a dedicated **"📜 Changelog Notif"** button in the **[Program Controls]** dashboard.
  - Allows users to globally enable/disable startup update notifications.
  - Default state set to **Enabled** (`CHANGELOG_NOTIF_ENABLED=on`).

---

## [1.0.246] - 2026-05-15

### 🛡️ Task Manager Plugin: Security Gating & UI Precision
- **New Feature: Security Confirmation System**:
  - Implemented a mandatory **"Yes/No"** confirmation screen for all destructive actions (`End`, `Restore`) and bulk operations (`End All`, `Resume All`, `Pause All`).
  - Protects the system from accidental task termination and bulk state changes.
- **Improved: Enriched Execution Metadata & UX**:
  - Upgraded the **"Manage Task"** sub-menu with a refined **3-row button layout** for better accessibility:
    - Row 1: Primary Controls (`Restore/Pause`, `End`)
    - Row 2: Secondary Info (`View Info`, `Recur Toggle`)
    - Row 3: Navigation & Sync (`Back`, `Refresh`)
- **Hardening: Advanced Debugging & Stability**:
  - Reinforced all core handlers and UI generators with `try-except` blocks and detailed `traceback` logging to the terminal.
  - Implemented a unified `handle_restore_action` helper for modular plugin-specific recovery.
- **Fixed: Task Manager Registry Sync**: Resolved a critical `TypeError` where cached tasks with ISO string timestamps (from xcreategroup) were causing the registry merge logic to fail.
- **Fixed: Task Visibility & Status Logic**: 
  - Resolved the "Shadowing" bug that prevented interrupted tasks from appearing in the dashboard.
  - Corrected the `⚫ Done` status false-positive; tasks without active processes now accurately display `⚠️ Interrupted`.
- **Improved: Defensive Timestamp Handling**: Implemented a dual-format converter in `scan_and_merge_caches` that intelligently handles both float timestamps and ISO 8601 strings.
- **Improved: Direct Restore Access**: Added a direct **"♻️ Restore"** button within the task status sub-menu for immediate recovery.
- **Hardening: UI Crash Prevention**: Added defensive float conversion to all UI status generators to ensure the dashboard remains stable even with malformed or inconsistent task metadata.
- **Improved: Interactive Feedback (UX)**:
  - Added instant "Refreshing list...", "Updating status...", and "Refreshing info..." alerts to all Refresh buttons to ensure visual feedback even when message content is unchanged.
- **Improved: Data Consistency**:
  - Standardized `gen_task_info_data` to utilize `get_all_tasks()`, ensuring that the detailed info view always reflects the latest state from physical caches.

---

## [0.0.10.2430I] - 2026-05-15

### 🏗️ Task Manager Plugin: Global Recovery & Bulk Management (v1.0.240)
- **New Feature: Global Restore Tasks (Cache)**:
  - Integrated a cross-plugin cache scanner to recover interrupted tasks from persistent storage (e.g., `creategroup_cache.json`).
  - Added dedicated Restore Menu with pagination and single-click recovery.
- **New Feature: Bulk Task Controls**:
  - Implemented `resume all`, `pause all`, and `end all` functionality to manage all active registry tasks simultaneously.
- **Improved: Advanced Dashboard Navigation**:
  - Added `first` and `last` navigation buttons for rapid access in large task lists.
  - Refined the dashboard UI into a structured 6-row grid with clean, lowercase labels for a professional look.
- **Fixed: MESSAGE_TOO_LONG Stability**:
  - Migrated task detail views from restricted popup alerts to a dedicated paginated message view.
  - Implemented automatic log chunking (1500 chars/page) to ensure UI stability with large amounts of metadata.
- **Enhanced: Debugging & Traceback**:
  - Implemented full stack-trace reporting to the Group Log (`LOG_CHAT_ID`) for every dashboard interaction error.

---

## [1.0.172] - 2026-05-15

### 🛠️ Universal Task Management: Advanced Sub-Menus & UX Hardening
- **New Feature: Multi-Layered Sub-Menu Architecture**:
  - Implemented a clean "List-to-Detail" pattern across the global Task Manager (`.tasklist`), CreateGroup Dashboard (`.cg`), and Restore Cache Manager (`.cgui`).
  - Technical controls (Resume, Pause, End, View) are now tucked away into specialized sub-menus for each task, significantly reducing UI clutter.
- **New Feature: Distinct "View" vs "Refresh" Logic**:
  - **🔍 View Info**: Now provides a static, detailed metadata snapshot (Start time, Plugin, Owner, Details) via a non-disruptive pop-up alert.
  - **🔄 Refresh**: Strictly handles re-rendering the status message with live progress and uptime data.
- **Hardening: Robust Task Status Detection**:
  - Integrated real-time process verification using `is_actually_alive` logic.
  - The system now accurately detects **"Interrupted"** tasks (where the process is missing but the flag is set) and correctly offers the **"▶️ Resume"** button instead of "Pause".
- **Hardening: Dashboard Integrity & Anti-Duplication**:
  - Implemented a **Unified Dashboard Text Generator** to ensure consistent formatting across all modules.
  - Resolved the "Header Stacking" bug by replacing cumulative text updates with clean, template-based re-renders.
- **Fixed: UI & Styling Synchronization**:
  - Corrected a `TypeError` in the CreateGroup dashboard keyboard generator.
  - Synchronized the **"🔍 View Chat"** button styling in the Restore Cache menu to match the session's aesthetic.

## [1.0.171] - 2026-05-15

### 🏗️ CreateGroup Plugin: Bulk Control & Execution Precision
- **New Feature: Bulk Task Management**:
  - Implemented **"Resume All"**, **"Pause All"**, and **"End All"** buttons in the Restore Tasks menu.
  - Allows simultaneous control over all cached background tasks across multiple sessions.
- **Improved: Restore Tasks Navigation**:
  - Added **"First"**, **"Last"**, and **"Refresh List"** buttons for more efficient navigation of large task histories.
  - Implemented a dedicated **"Back to Menu"** button for a smoother UI flow.
- **Hardening: Smart Task Status Monitoring**:
  - Implemented real-time task object validation to distinguish between active (`🟢 Running`), paused (`⏸️ Paused`), interrupted (`⚠️ Interrupted`), and stopped (`🛑 Stopped`) states.
  - The UI now accurately identifies tasks that were interrupted by a system restart or crash.
- **Improved: Log Formatting & Execution Loop**:
  - Enforced strict **integer-only types** for the `Count` parameter to eliminate floating-point artifacts in progress logs (e.g., `1/2.0` → `1/2`).
  - Corrected logic flow in the Restore Tasks menu to ensure all navigation buttons are properly registered before message dispatch.
- **Hardening: Task Parameter Integrity**:
  - Refined the adjustment handler to maintain precision for float-based delays while strictly enforcing whole numbers for count-based execution settings.

## [1.0.170] - 2026-05-15

### 🏗️ CreateGroup Plugin: Multi-Account & UI Scalability
- **New Feature: Multi-Account/Session Selection**:
  - Implemented a dedicated **Account Selection Dashboard** allowing users to select multiple accounts for a single task.
  - **Individual Toggles**: Select specific accounts from the session list with ☑️/☐ status icons.
  - **Batch Selection**: Added **"Select All"** and **"Deselect All"** buttons for rapid management of large session pools.
  - **Smart Defaulting**: The account that initiates the `.cgui` command is automatically pre-selected.
- **New Feature: Parallel Multi-Tasking**:
  - The system now initiates independent background tasks for every selected account simultaneously.
  - Each session-task is assigned a unique **Task ID (TID)** and can be managed (Pause/Resume/Stop) individually via `.tasklist`.
- **Improved: Adjustment UI & Granularity**:
  - Expanded numeric adjustment buttons to include **+/- 3** and **+/- 5** increments for all parameters (Count, Delay, Batch, etc.).
  - Redesigned the adjustment interface into a clean **2-column layout** for better vertical space management.
  - Hardened regex and parsing to support **floating-point values** (e.g., `0.5s` action delays).
- **Hardening: Multi-Session Persistence & Recovery**:
  - **Advanced State Mapping**: Separated `admin_id` (task owner) from `client_id` (executor session) in the task state.
  - **Independent Recovery**: The recovery system now correctly resolves the exact userbot session for each task after a restart, preventing session cross-talk.
  - **Collision-Proof Logging**: Log filenames now include the unique **TID** to prevent overwriting when multiple sessions finish at the same time.
- **Fixed: UI & Logic Consistency**:
  - Resolved a critical session indexing mismatch (0-based vs 1-based) that caused the Bot Assistant to fail when launching the dashboard via `.cgui`.
  - Standardized all internal session lookups to use 1-based indexing for UI compatibility.
  - Added **⏮ First** and **⏭ Last** buttons to the Multi-Session selection menu for faster navigation through large account lists.
- **Improved: Diagnostic & Debugging Suite**:
  - **Centralized Log Reporting**: Integrated `send_log_message` with full **Traceback** capture for all critical handler and loop failures.
  - **Smart Log Delivery**: Implemented automatic conversion of long error logs into `.txt` files to bypass Telegram's `MessageTooLong` limit.
  - **Real-Time Notifications**: Critical internal errors are now immediately reported to the Log Group for faster troubleshooting.
- **Fixed: UI Error Handling Parity**:
  - Restored fallback logic that warns the user if the Bot Assistant cannot send a PM (e.g., blocked), while ensuring the task still proceeds in the Log Group.
  - Implemented session-level `try-except` blocks to ensure one failing account doesn't prevent others from starting.

## [1.0.169] - 2026-05-14

### 🎥 YTDL Manager: Real-Time Download Progress
- **New Feature: Live Download Progress Bar**:
  - Implemented real-time parsing of `yt-dlp` output to display a live progress bar during the downloading phase.
  - Users can now track the exact percentage of completion without the dashboard appearing stuck.
- **Improved: Throttled UI Updates**:
  - Optimized the progress update interval to **10 seconds** per refresh.
  - This balance ensures continuous visual feedback while strictly preventing Telegram `FloodWait` (429) errors during long downloads.
- **Hardening: Stable Subprocess Handling**:
  - Refactored the internal download engine to use a robust stream reader for `stdout` and `stderr`.

## [0.0.10.2506H] - 2026-05-12

### 🏗️ Task Manager Plugin: Universal Dashboard & UI Synchronization
- **New Feature: Interactive Task Dashboard (v1.0.231)**:
  - Full UI overhaul with inline control buttons for each task: **Pause, Resume, Stop,** and **Recurring Toggle**.
  - Implemented a **Pagination System** (5 tasks per page) with `⬅️ Prev` and `Next ➡️` navigation for managing large task registries.
- **Improved: Inline Bot Results Integration**:
  - Migrated menu rendering to the compliant `via @bot` assistant architecture (`get_inline_bot_results`), ensuring maximum interactive stability and following developer guidelines.
- **Synchronized: Button Style & Aesthetics**:
  - **Account Styling**: Every interactive button now automatically matches the account/session's configured **Button Style** (Primary, Success, Danger, or Default).
  - **Expandable Blockquotes**: All task-related responses are now wrapped in `<blockquote expandable>` for a cleaner, professional chat experience.
- **Hardening: Robust Error Handling & Diagnostics**:
  - Wrapped all menu generators, inline handlers, and callback logic in `try/except` blocks with **full Traceback logging**.
  - Integrated `logger.exception` to ensure rapid identification of technical issues during task management.
- **Refined Command Set**:
  - Renamed `.canceltask` to `.taskcancel` for better naming consistency.
  - Added new dedicated commands: `.taskpause`, `.taskresume`, and `.taskstatus`.

---

## [0.0.10.2505H] - 2026-05-11

### 🏗️ Message Pusher Plugin: Feature Parity & Interactive Enhancements
- **New Feature: Bot & Assistant Invitation**:
  - Added support for inviting the **Bot Assistant** and a **Custom Bot List** automatically before pushing messages.
  - Implemented a dedicated sub-menu for managing the bot username list interactively.
- **New Feature: Quote Block Support**:
  - Integrated the **Quote Block** toggle to wrap quote sequences in `<blockquote expandable>` tags, matching the CreateGroup module's aesthetics.
- **Improved: Command UX & Logic**:
  - The `.pushmsg` command now defaults to the **current chat** if no arguments are provided, allowing for faster task initialization.
- **Enhanced: Task Management Integration**:
  - Fully integrated with `Xtaskmanager`, enabling users to monitor, pause, resume, and cancel background pusher tasks via `.tasklist`.
- **Plugin Version Upgraded**: Bumped `xmessage_pusher.py` to `0.1.17`.

### 🏗️ CreateGroup Plugin: UX Refinement
- **UI Improvement**: Added `.cgpanel` as an official alias for `.cgtid` and updated help documentation for better clarity on task recalling.

## [0.0.10.2411H] - 2026-05-10

### 🏗️ CreateGroup Plugin: UI Persistence & Feature Reinstatement
- **New Feature: Persistent Dashboard Configuration**:
  - Implemented a dedicated storage system (`xcreategroup_user_configs.json`) to persist user settings across restarts and sessions.
  - **Automated Saving**: Integrated `save_user_cg_config` into all interactive handlers (Toggle, Adjust, Set Value, and Message Input).
  - **Smart Loading**: The dashboard now automatically recovers the user's last saved configuration instead of resetting to defaults.
- **New Feature: Task Control Recovery**:
  - Added `.cgtid [TID]` (alias `.cgpanel`) command to recall the interactive **Task Control Panel** for any specific active task.
- **New Feature: Dashboard Restore Access**:
  - Added the **"Restore Tasks"** button directly to the main dashboard for faster access to interrupted task management.
- **Restored: Quote Block Formatting**:
  - Reinstated the **Quote Block** toggle in the interactive UI, allowing users to enable/disable `<blockquote expandable>` tags for love quotes.
  - Fixed logic flow to ensure the setting is correctly passed to the background execution loop.
- **Fixed: Critical Stability & Code Integrity**:
  - Resolved task initiation failures for users who haven't started the Bot Assistant in PM; the system now gracefully falls back to the Log Group control panel instead of crashing.
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
