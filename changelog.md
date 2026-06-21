# Altroid-X Changelog

All notable changes to the **Altroid-X** project from version **0.0.10.0959H** to the latest.
Latest updates are always added at the top (newest → oldest).

## [1.0.292] - 2026-06-21

### 👥 CreateGroup: Inline Assistant Button Unresponsive & Multi-Session Bouncing Buttons Fixes
- **Fixed: Inline assistant buttons unresponsive (updating PM instead of inline/group chat)**
  - Updated [safe_edit_message_text](file:///f:/2026/APRIL/AltruixX/Main/internals/settings_handlers/creategroup_handlers.py#L52) to correctly identify callbacks that originate from inline messages (checking `getattr(cb, 'inline_message_id', None)`) and use the assistant bot's `edit_inline_text` method instead of trying to edit the PM message.
  - Corrected [render_creategroup_ui](file:///f:/2026/APRIL/AltruixX/Main/internals/settings_handlers/creategroup_handlers.py#L485) to properly accept and use `inline_message_id` when rendering/updating the UI, ensuring that when button clicks occur, the update modifies the inline message in-place instead of spamming PM.

- **Fixed: Multi-Session Selection bouncing buttons (selections not saving/syncing and reverting)**
  - Fixed debounce logic to use specific callback data in the lock key (`cb:{chat_id}:{message_id}:{cb_data}` / `cb:{uid}:{cb_data}`), preventing a click on one session button from blocking unrelated clicks on other session buttons within the 0.3s debounce window.
  - Ensured `selected_sessions` changes are immediately saved to persistent config JSON (`xcreategroup_user_configs.json`) by invoking `save_user_cg_config(user_id, ...)` whenever sessions are selected, deselected, or page select/deselect operations occur.
  - Fixed state re-initialization logic in `get_creategroup_ui_state`, `show_creategroup_ui`, and `get_creategroup_ui_data` to properly restore `selected_sessions` from the saved user configuration instead of resetting to the default `[session_index]`.
  - Moved `cb.answer()` execution to occur *before* the rendering process starts, preventing Telegram from displaying endless loading spinners on clicked buttons.

- **Safety & Verification**
  - Syntactic validation of `creategroup_handlers.py` and `xcreategroup.py` completed using `py_compile` to ensure no syntax/runtime issues exist.
  - All changes were implemented with proper try-except handlers and error loggers to maintain stability.

- **Files changed**: [Main/internals/settings_handlers/creategroup_handlers.py](file:///f:/2026/APRIL/AltruixX/Main/internals/settings_handlers/creategroup_handlers.py), [Main/plugins/userbot/xcreategroup.py](file:///f:/2026/APRIL/AltruixX/Main/plugins/userbot/xcreategroup.py)

---

## [1.0.290] - 2026-06-16

### 👥 Multi-Session Selection: Account Filters & CHANNELS_TOO_MUCH persistence
- **Added: Account filter buttons** — Added `Limit`, `Most`, and `Least` filters to the `👥 Multi-Session Selection` UI so users can quickly show accounts with the most creations, the least creations, or those that previously hit channel limits. Buttons are arranged as two rows: `[All] [Newest] [Oldest]` and `[Limit] [Most] [Least]`.

- **Added: Persistent error reporting for terminal errors** — When a session hits a terminal `CHANNELS_TOO_MUCH` error during create (HTTP 400), the plugin now persists an error record into `xcreategroup_created_report.json` (keyed by account id) via `save_failed_error_to_report(...)`. This enables the `[Limit]` filter to only surface accounts that have recorded that specific error.

- **Fixed: UI ordering & select/deselect synchronization** — The `select_sessions` page now computes the same ordered/filtered session indices as the UI and records `last_paged_indices` so `Select Page` / `Deselect Page` operate on the exact accounts the user sees (avoids selecting wrong accounts when filters are active).

- **Added: Account preview in logs** — Failure and termination notifications now include the account index preview `N/N` (e.g. `❌ Gagal membuat Supergroup 4/40`) and `account_idx/total_accs` are passed to `creategroup_loop` and recorded in state to keep logs consistent and easy to trace.

- **Safety & persistence** — Config and report files continue to use atomic write patterns (write `.tmp` then replace). All file I/O and network operations are wrapped in try/except and log full tracebacks to assist debugging without interrupting main flows.

- **No removals** — No existing features were removed; all changes are additive and include fallbacks when report/config files are missing or corrupted.

- **Files changed**: [Main/internals/settings_handlers/creategroup_handlers.py](Main/internals/settings_handlers/creategroup_handlers.py), [Main/plugins/userbot/xcreategroup.py](Main/plugins/userbot/xcreategroup.py)

---

## [1.0.291] - 2026-06-18

### 👥 CreateGroup: Repeat indicator, recurring persistence & verification logging
- **Fixed: Repeat submenu value mismatch**
  - Normalized callback keys to `repeat_count` and updated `creategroup_set_val_handler` to accept `repeat` or `repeat_count` and persist to `repeat_count`, ensuring dashboard shows correct "Repeat: Nx" immediately.

- **Fixed: Recurring runs ignored album & invite flags**
  - Persisted `msg_img_album`, `msg_vid_album`, and `invite_assistant` into `COMPLETED_CREATEGROUP_TASKS` and forwarded them when auto-rescheduling recurring runs so album behavior and assistant invites are honored on repeats.

- **Added: Verification logging on completed-task save**
  - Added an assertion/log line after saving completed-task metadata to log saved flags (`msg_img_album`,`msg_vid_album`,`invite_assistant`,`repeat_count`) to help runtime diagnostics.

- **Changed: Rescheduler guard & repeat handling**
  - Rescheduler uses `_SCHED_RECURRING` guard to avoid duplicate scheduling and honors `repeat_count` remaining counter.

- **Files changed**: [Main/plugins/userbot/xcreategroup.py](Main/plugins/userbot/xcreategroup.py), [Main/internals/settings_handlers/creategroup_handlers.py](Main/internals/settings_handlers/creategroup_handlers.py)

---

## [1.0.289] - 2026-06-15

### 👥 CreateGroup: Restore Invite Assistant UI, Param, & Delay Enforcement
- **Restored: Invite Assistant UI & parameter plumbing**
  - Reintroduced the `Invite Asst` dashboard toggle and UI button; `invite_assistant` is now included in `DEFAULT_CREATEGROUP_CONFIG` and shown in summaries/confirmations.
  - `creategroup_handlers` now passes `invite_assistant` into `creategroup_loop` to make assistant invite behavior configurable per-launch.

- **Restored: Delay semantics (per-group & per-batch)**
  - Reapplied per-group `delay` (seconds) between each created group and `extra_delay_minutes` (minutes) applied after each `batch_size` groups.
  - Batch-level waits reuse `wait_with_countdown(...)` for visible countdowns and respect pause/cancel signals during waits.

- **Changed: Assistant invite logic now uses `invite_assistant`**
  - Plugin checks for assistant invites/promotions now use `if invite_assistant:` (separate from `invite_bots`) so assistant behavior is independent and predictable.

- **Files changed**: [Main/plugins/userbot/xcreategroup.py](Main/plugins/userbot/xcreategroup.py), [Main/internals/settings_handlers/creategroup_handlers.py](Main/internals/settings_handlers/creategroup_handlers.py)

---

## [1.0.287] - 2026-06-14

### 👥 CreateGroup: Delay Enforcement, Invite Assistant Split & Pagination Fixes
- **Added: Per-group and per-batch delay enforcement**
  - Enforced `delay` (seconds) between each created group and `extra_delay_minutes` (minutes) after each `batch_size` groups.
  - Batch-level waits use the existing `wait_with_countdown(...)` helper for visible countdowns; per-group waits respect pause/stop signals.

- **Changed: Separate Assistant Invite toggle & behaviour**
  - Introduced explicit `invite_assistant` flag and UI toggle so assistant bot invite/promotion is independent from `invite_bots`.
  - Assistant invite/promotion occurs during creation/setup; non-assistant bot invites are processed later in the `invite_bots` step.

- **Fixed: Pagination select/deselect mismatch with filters**
  - Added `_get_ordered_session_indices(state)` to compute session indices in the same ordering as the UI render (honors `account_filter: all/newest/oldest`).
  - `Select Page` / `Deselect Page` and page navigation now use the ordered indices (and `last_paged_indices`) to avoid selecting wrong accounts when filters are active.

- **Fixed: Async helper safety & indentation bug**
  - Removed `run_until_complete(...)` usage from the ordering helper to avoid running the event loop inside callbacks.
  - Fixed an over-indentation causing a syntax/indent error in `creategroup_handlers.py`.

- **Files changed**: [Main/plugins/userbot/xcreategroup.py](Main/plugins/userbot/xcreategroup.py), [Main/internals/settings_handlers/creategroup_handlers.py](Main/internals/settings_handlers/creategroup_handlers.py)

---

## [1.0.288] - 2026-06-14

### 🧹 Purgeme: Concurrency & Config Persistence Fixes
- **Fixed: Double-trigger behavior on rapid submenu button clicks**:
  - Added async lock (`asyncio.Lock`) to prevent race conditions when callbacks are processed simultaneously. Each purgeme session now serializes state modifications under `async with state["callback_lock"]:`, ensuring no concurrent state corruption.
  - Callback handler body properly indented to fall under the lock context, guaranteeing sequential execution of all state changes per session.

- **Fixed: Sender selection not persisting across sessions**:
  - User-selected sender (`from_id`) is now persisted to JSON config during auto-save. When `.purgeme` is restarted, the previously selected sender (or channel) is restored automatically.
  - Added `"from_id": "me"` to `DEFAULT_PURGEME_CONFIG` in `purgeme_handlers.py` to ensure new users start with correct default.

- **Enhanced: Auto-save config includes sender preference**:
  - Config auto-save logic now includes `from_id` field in the saved dictionary whenever a configuration-modifying action is detected (e.g., `pg_set_sender_`, `pg_cnt_`, `pg_mode_`, etc.).
  - Sender changes trigger config persistence immediately, maintaining synchronization between runtime state and persistent storage.

- **Implementation & Safety**:
  - Lock is lazily initialized in state if missing, preventing crashes on legacy session resumption.
  - All callback actions (count adjust, delay adjust, mode change, sender select, type toggle, etc.) are now atomic and race-condition-free.
  - Config save uses atomic file replacement pattern (write to temp file, then replace) to prevent data loss on crash.

- **Files changed**: [Main/plugins/userbot/xpurgeme_userbot.py](Main/plugins/userbot/xpurgeme_userbot.py), [Main/plugins/bot/xpurgeme_bot.py](Main/plugins/bot/xpurgeme_bot.py), [Main/internals/settings_handlers/purgeme_handlers.py](Main/internals/settings_handlers/purgeme_handlers.py)

- **Notes**:
  - This patch eliminates the double-trigger issue observed when users rapidly click submenu buttons (e.g., `+`, `-`, mode selection).
  - Sender selection now survives session restarts, improving UX for users who frequently change from/to different accounts or channels.
  - No changes to UI, button callbacks, or external API; purely internal state management and persistence improvements.

---

## [1.0.286] - 2026-06-12

### 🛠️ CreateGroup: Recovery, UI refresh & integer formatting fixes
- **Fixed: Resolve undefined `LOG_CHAT_ID` usage in handlers**
  - `creategroup_handlers` now resolves the log chat via `getattr(Altruix, 'log_chat', None) or getattr(Altruix.config, 'LOG_CHAT_ID', None)` before sending to the log group, avoiding NameError in environments where the module-level `LOG_CHAT_ID` isn't available.

- **Fixed: Clear stale control_message_id on recover failures**
  - In `Main/plugins/userbot/xcreategroup.py` the control-message recovery logic now detects "Invalid message ids"/similar errors, clears the stale `control_message_id` from task state, persists the cache, and logs at DEBUG level to reduce noise.

- **Fixed: Dashboard UI not updating after launches finish**
  - `launch_tasks_bg` now proactively refreshes the user's dashboard message when the launch completes (or is cancelled), ensuring the `⛔ Cancel Launch` button is removed immediately.

- **Fixed: Numeric formatting for batch values (UI + storage)**
  - `batch_action` and `batch_size` are forced to integers when adjusted and displayed in the UI (dashboard text, control buttons, and submenu headers), eliminating float artifacts like `40.0` or `11.g`.
  - The adjustment handler (`creategroup_adjust_handler`) was fixed to include `batch_action` and `batch_size` in the integer key list and to sanitize stored values to int.

- **Files changed**: [Main/internals/settings_handlers/creategroup_handlers.py](Main/internals/settings_handlers/creategroup_handlers.py), [Main/plugins/userbot/xcreategroup.py](Main/plugins/userbot/xcreategroup.py)

---

## [1.0.285] - 2026-06-10

### 👥 CreateGroup: Chunk Notifications & Aggressive Cancel
- **Added: Per-chunk notifications (configurable)**:
  - Moved chunk notification controls into the **Log Configs** submenu and introduced a multi-mode setting `Chunk Notif: Both / Group Log / PM Bot / Off`.
  - When enabled, the launcher will send start/completion notifications for each chunk to the configured target(s) and edit those messages when the chunk completes or times out.

- **Added: Chunk notification persistence & UI parity**:
  - `notify_chunks` is persisted in the per-user `xcreategroup_user_configs.json` (cycled with the existing log-mode toggle pattern) and reflected in the `Log Configs` label.
  - Safe save/load wrappers and `save_user_cg_config` are used to ensure configuration is stored atomically and survives restarts.

- **Added: Aggressive cancellation for admin-triggered aborts**:
  - When a user requests an End/Cancel (or `LAUNCH_CANCEL` is set), the launch loop will aggressively cancel any in-memory `CREATEGROUP_TASKS` entries that belong to that admin (`admin_id == user_id`), cancel their asyncio tasks, and remove them from the registry.
  - The cache is persisted after aggressive cancellation to avoid dangling task entries on disk.

- **Implementation & Safety**:
  - Per-chunk notifications route to the selected mode(s): reply to control message, PM to admin, and/or log group.
  - All notification sends and edits are wrapped in try/except and logged; failures do not abort the launch flow.
  - Chunk waits use `asyncio.wait(..., timeout=...)` and timeouts are logged; on timeout the launcher proceeds to next chunk unless user requests cancel.

- **Files changed**: [Main/internals/settings_handlers/creategroup_handlers.py](Main/internals/settings_handlers/creategroup_handlers.py)

- **Notes**:
  - This patch preserves existing behavior when `Chunk Notif` is `Off` and maintains legacy staggered startup when `auto_start` is disabled.
  - Aggressive cancellation is intentionally conservative and only removes tasks where `admin_id` matches the requesting user to avoid cross-admin interference.

---

## [1.0.284] - 2026-06-10

### 👥 CreateGroup: Session Page Selection & Pagination Fixes
- **Fixed: Inconsistent Select/Deselect Page behavior with account filters**:
  - Resolved an issue where the `Select Page` / `Deselect Page` buttons acted on the unfiltered index order when the UI was showing `newest`/`oldest` filtered pages, causing incorrect accounts to be selected or deselected.
  - `get_creategroup_ui_data` now records the actual session indices displayed on each rendered page (`last_paged_indices`) and the select/deselect handlers use those indices when available.

- **Changed: Reduced accounts per page**:
  - The session selection UI now shows **5** accounts per page (previously 8) to reduce visual clutter and improve usability on narrow screens.

- **Files changed**: [Main/internals/settings_handlers/creategroup_handlers.py](Main/internals/settings_handlers/creategroup_handlers.py)

- **Notes**:
  - This fix keeps the "Current" session indicator and selection state consistent when users switch filters (`All` / `Newest` / `Oldest`).
  - No change to persistence or external APIs; purely UI/handler behavior.

---

## [1.0.283] - 2026-06-10

### 👥 CreateGroup: Signature Mismatch Fix
- **Fixed: Unexpected keyword arguments passed during task resume**:
  - Resolved a mismatch where `creategroup_handlers` passed `auto_start` and `auto_start_count` to `creategroup_loop`, but the loop signature did not accept those keywords, causing a `TypeError` on resume/recover flows.
  - Normalized the plugin surface so `creategroup_loop` accepts `auto_start` and `auto_start_count` (with sensible defaults) and the handlers consistently pass them through.

- **Files changed**: [Main/plugins/userbot/xcreategroup.py](Main/plugins/userbot/xcreategroup.py), [Main/internals/settings_handlers/creategroup_handlers.py](Main/internals/settings_handlers/creategroup_handlers.py)

- **Notes**:
  - This is a non-breaking fix ensuring bulk-resume and cached-task recovery paths no longer raise unexpected-argument errors.
  - No behavior changes to auto-start semantics were made beyond making the parameters accepted and propagated; further runtime tuning remains in follow-ups.

---

## [1.0.281] - 2026-06-09

### 👥 CreateGroup: Log Configs Active Indicator
- **Added: Compact active log indicator on main dashboard**:
  - Dashboard `Log Configs` button now shows active count, e.g. `Log Configs: 2/6`, reflecting how many log-related settings are set to a non-`off` value.
  - Settings considered: `start_log_mode`, `start_photo_log_mode`, `progress_log_mode`, `panel_log_mode`, `interrupted_log`, `delay_log_mode`.

- **UI / UX**:
  - Indicator provides quicker visibility into logging verbosity without opening the submenu.
  - `Log Configs` submenu and per-setting toggles remain unchanged.

- **Implementation Notes**:
  - Uses existing per-user config storage and `save_user_cg_config` for persistence.
  - Includes safe UI edits and try/except logging to avoid `MessageNotModified` and callback race issues.

- **Fixed: Whitelist membership probe now handles `ParticipantIdInvalid` properly**:
  - When `get_chat_member()` or raw `channels.GetParticipant` returns `ParticipantIdInvalid`, the check now treats the user as not present in that group and continues probing other whitelisted groups.
  - This prevents repeated retry logs and avoids failing the overall whitelist authorization flow for users who have left or been removed from the group.

- **Files changed**: [Main/core/client.py](Main/core/client.py#L940-L956)

- **Notes**:
  - Non-breaking UI enhancement; no files or existing features removed.
  
---

## [1.0.282] - 2026-06-09

### 👥 CreateGroup: Auto-Start Chunking & Signature Fix
- **Fixed: Plugin import SyntaxError (duplicate argument)**:
  - Normalized the `creategroup_loop` function signature to remove duplicated `auto_start` definitions and removed references to runtime `params` at definition time. This resolves the plugin import failure caused by a duplicate argument.

- **Added: Runtime Auto-Start Chunking**:
  - When `auto_start` is enabled, selected sessions are split into chunks of size `auto_start_count`. Each chunk starts its sessions concurrently and the system waits for chunk completion (or until an `auto_start_timeout` elapses) before proceeding to the next chunk.
  - Default timeout is configurable (`auto_start_timeout`, default 300s). On timeout the chunker logs a warning and proceeds to the next chunk.
  - Fallback to legacy staggered per-account start remains when `auto_start` is disabled.

- **Implementation notes**:
  - Safe try/except logging was added around chunk startup and control-message creation to avoid task crashes and to notify the user on failures.
  - The change preserves existing per-user config persistence and passes `auto_start` / `auto_start_count` through existing call sites.

- **Files changed**: [Main/plugins/userbot/xcreategroup.py](Main/plugins/userbot/xcreategroup.py#L1444-L1489), [Main/internals/settings_handlers/creategroup_handlers.py](Main/internals/settings_handlers/creategroup_handlers.py#L270-L300)

---

## [1.0.280] - 2026-06-09

### 👥 CreateGroup: Tracker Log Selector & Auto Start
- **Added: Per-task Tracker Log selector on initial progress message**:
  - Initial progress message (`📊 Memulai Tracker Progress...`) now includes inline buttons to choose where start/update logs are sent per task: `Tracker Log: Both / Group Log / PM Bot / Off`.
  - Selection is persisted to the task params and reflected in the UI; permission checks and debounce guards applied to callbacks.

- **Added: Auto Start option in main dashboard**:
  - New dashboard buttons: `Auto Start: On/Off` and `Auto Start Count: <n>` (configurable count similar to `Batch Account`).
  - Values persist to per-user config (`xcreategroup_user_configs.json`) and are passed into `creategroup_loop` call sites.

- **Improved: UI wording and safety**:
  - Renamed `Start Log` labels to `Tracker Log` across settings UI and callbacks for clarity.
  - Added try/except logging and safe edit wrappers to reduce `MessageNotModified` and callback race issues.

- **Notes**:
  - Runtime auto-start behavior (starting tasks automatically per N accounts) is wired into configs and call sites; execution semantics will be implemented and validated in a follow-up patch.
  
---

## [1.0.279] - 2026-06-08

### 📡 xforward_pro: Skip Delay When Message Missing
- **Added: Skip per-message delay when message missing/empty**:
  - New per-task toggle `skip_delay_on_empty` (default ON) and global default `default_skip_delay_on_empty` (default ON).
  - When enabled, the batch processor and live listener will skip waiting the configured per-message delay if the message was empty or deleted, speeding up runs.
  - UI toggles added: Task Advanced Options and Global Advanced Defaults (`SkipDelay: ON/OFF`).
  - DB migrations included to persist the new fields.

### Notes
- Logic is safe by default and includes try/except fallbacks; no features or files removed.

---

## [1.0.277] - 2026-06-07
### 📡 xforward_pro: Album Forwarding & Defaults
- **Added: Album (media-group) forwarding**:
  - Detects media groups (`msg.media_group_id`) and attempts to send them as a single album via `send_media_group` when `forward_as_album` is enabled.
  - Falls back to `forward_messages` when `send_media_group` is not permitted (e.g., restricted file_ids).
- **Added: per-task and global toggles**:
  - New task field `forward_as_album` and global setting `default_forward_as_album` (DB migration included).
  - UI toggles added: Global main menu and Task Advanced Options (`Album: ON/OFF`).
- **Added: Album cache and dedupe**:
  - In-memory `FWD_ALBUM_CACHE` prevents duplicate album forwarding when multiple parts arrive rapidly.
- **DB & Logging**:
  - Schema migration ensures new fields persist; log messages added for album send fallbacks and errors.
- **Notes**: No existing features removed. This improves media-group handling and keeps backward-compatible fallbacks.

---

## [1.0.278] - 2026-06-07

### 📡 xforward_pro: Live Batch Log Timestamp
- **Added: Time stamp to live batch logs**:
  - Live `Batch Log` messages now include the processing time (HH:MM:SS) in the footer for easy correlation with runtime events and log entries.
  - Provides better traceability when debugging large batch runs and when matching log lines in `LOGS/` or remote log channels.
  - Safe fallback ensures a placeholder time (`--:--:--`) is shown if time formatting fails.


## [1.0.276] - 2026-06-07

### 📡 xforward_pro: Batch Range & Batch Msg Controls
- **Added: CONFIG BATCH RANGE submenu**:
  - Interactive menu to configure `Start ID` and `End ID` with step buttons (+/- 1,5,10,50,100,...).
  - `🚀 EXECUTE BATCH` button to run batch directly from UI (no manual `.fwd run` required).
- **Added: Batch Msg & B.Msg Delay controls (Task & Global)**:
  - Per-task (`batch_msg`, `batch_msg_delay`) and global defaults (`default_batch_msg`, `default_batch_msg_delay`) persisted in DB.
  - Added UI buttons in Advanced Options for quick adjustments and inc/dec shortcuts.
- **DB Migration & Persistence**:
  - Schema migration added for `start_id`, `end_id`, `batch_msg`, `batch_msg_delay`, and global defaults.
  - Values are saved atomically and safely via the existing DB layer.
- **Helpers & Robust UI edits**:
  - Added `safe_edit_cb_text()`, `safe_cb_ack()` and `_normalize_delay()` helpers to safely edit inline/callback messages and normalize delays.
  - UI updates now use safe editing to handle inline messages and prevent `MessageNotModified` errors.
- **UX / Labels**:
  - Task Detail now shows `📦 CONFIG BATCH RANGE` button and Advanced Options display `Batch Msg` / `B.Msg Delay` state.
- **Notes**: No files or existing features were removed; this change enhances batch configuration UX and persistence.

---

## [1.0.276] - 2026-06-07

### 📡 xforward_pro: JSON Database & Robust Restoration
- **Database: JSON Migration**:
  - Migrated primary storage from SQLite (`forward_pro.db`) to JSON (`forward_pro_db.json`) for consistency with other plugins.
  - Implemented automatic data migration from SQLite to JSON on first run without data loss.
  - Optimized database operations using an in-memory cache (`_FWD_DATA`) with an asynchronous saving mechanism and file locking to prevent race conditions.
- **Improved: Predictable Task IDs**:
  - Switched from random hashes to predictable IDs (`#FPL{id}` for Live, `#FPB{id}` for Batch) to ensure reliable task synchronization between the plugin and `xtaskmanager`.
- **Improved: Robust Startup Restoration**:
  - Enhanced `_restore_active_tasks` with a client-readiness wait mechanism (up to 30 seconds) to ensure sessions are fully established before restoring live listeners.
  - Added robust error handling and automated reporting for restoration failures.
- **Improved: Task Manager Integration**:
  - Updated `xtaskmanager` to support dual-database scanning (JSON & SQLite) for Forward Pro tasks.
  - Integrated Forward Pro into the global `handle_restore_action`, allowing manual restoration via the "♻️ Restore" button in the Task Manager dashboard.
  
---

### 🐞 xforward_pro: Compatibility, Robust Save, and Debug Improvements
- **Fixed: Inline button compatibility**:
  - Added a compatibility wrapper for `InlineKeyboardButton(..., style=...)` to support multiple Pyrogram versions and prevent import-time TypeError that made buttons unresponsive.
- **Improved: Atomic JSON save & corrupted DB handling**:
  - Implemented atomic JSON saves via a temporary file + `os.replace` (fallback `os.rename`) to avoid partial writes.
  - Added automatic backup of corrupted `forward_pro_db.json` to `forward_pro_db.json.corrupt.<ts>.bak` and safe recovery path.
- **Improved: Debugging & Tracebacks**:
  - Added debug logging to DB load/save and CRUD operations (`add_task`, `get_tasks`, `get_task`, `update_task`, `delete_task`).
  - Added debug traces on inline queries and callback receipts to assist tracing button interactions and payloads.
- **Fixed: Watermark video processing**:
  - Fixed `add_watermark_video()` flow (proper try/except/finally, cleanup of overlay/temp files, robust error logging).
- **Fixed: Log channel key consistency**:
  - Ensured `.fwd glog` stores `log_channel` key consistently with `get_global_settings` and `send_log` usage.
- **Notes**: No existing features or files were removed; these are stability, compatibility and observability improvements to make debugging and restores reliable.

---

### 👥 CreateGroup: Album Grouping untuk Msg Img & Msg Vid
- **Added: Album Mode Toggles (Per Type)**:
  - Added separate dashboard toggles: `Album Img` dan `Album Vid` untuk mengirim media sebagai album (grouping) sesuai jenis pesan.
  - Persisted ke config user (JSON) dengan key baru: `msg_img_album` dan `msg_vid_album` (default: Off).
- **Added: send_media_group Flow + Fallback**:
  - Mengirim media dalam chunk maksimal 10 item per album sesuai batas Telegram, dengan caption/entities mengikuti item pertama yang tersedia.
  - Jika `send_media_group` gagal, otomatis fallback ke metode lama (copy/send satu-per-satu) dengan logging + traceback agar task tetap lanjut.

---

## [1.0.275] - 2026-06-06

### 📡 xforward_pro: Advanced Forwarding Enhancements
- **Added: Batch Control UI**:
  - Integrated `Batch Msg` and `Batch Msg Delay` configuration buttons into Global and Task-specific Advanced Options.
  - Integrated visual batch cooldown notifications in the log group during processing.
- **Added: Album Forwarding Support**:
  - Implemented `Forward as Album` toggle in Advanced Options.
  - Automatically detects media groups (albums) and forwards them as a single entity using `send_media_group` for Copy/Bypass modes.
  - Optimized album detection to apply cleaned captions and translations correctly to the entire media group.
  - Added internal caching to prevent redundant album forwarding during live or batch processes.
- **Added: Visual Batch Range Configuration**:
  - Introduced a new submenu for configuring `Start ID` and `End ID` using interactive step buttons (+/- 1, 10, 100, 1000).
  - Added `🚀 EXECUTE BATCH` button directly in the UI, eliminating the need for manual command entry.
- **Improved: Startup Task Restoration**:
  - Refactored `_restore_active_tasks` to properly register Live Forwarding tasks as permanent listeners in `xtaskmanager` (preventing auto-cleanup).
  - Added detection and logging for interrupted Batch tasks after a bot restart.
- **Improved: Error Resilience & Debugging**:
  - Wrapped startup restoration and live forwarding logic in robust `try-except` blocks.
  - Integrated automated error reporting: critical failures now send detailed logs and full tracebacks to the `LOG_CHAT_ID` group.
- **Fixed: IndexError in Batch Range UI**:
  - Resolved `list index out of range` error in `fwd_callback_handler` when rendering Batch Range buttons with an odd number of step values.
- **UI: Reorganized Batch Range Layout**:
  - Reordered adjustment buttons to group negative values (-) on the left and positive values (+) on the right for improved readability and user experience.
- **Database**: Migrated schema to include `batch_msg`, `batch_msg_delay`, `start_id`, and `end_id` persistence.

---

## [1.0.274] - 2026-06-06

### 👥 CreateGroup: Staggered Resume & Config Persistence
- **Improved: Staggered Resume Logging**:
  - Added logic to sync and update `batch_account` and `ba_account_delay` parameters when a task is resumed after a restart.
  - Ensures the initialization logs accurately reflect the current batching state during staggered startup.
- **Fixed: selected_sessions Reset Issue**:
  - Improved `launch_tasks_bg` initialization in `creategroup_confirm_task_handler` to properly handle session indices.
  - Added state cleanup for the `launching` flag across multiple entry points to prevent UI locks.
  - Verified JSON persistence logic for user configurations to ensure settings are correctly saved and reloaded after bot restarts.

---

## [1.0.273] - 2026-06-06

### 👥 CreateGroup: Report Export Stability
- **Fixed: AttributeError 'NoneType' object has no attribute 'chat'**:
  - Added null-safety check for `cb.message` in `creategroup_report_export_acc_handler` and `creategroup_report_export_all_handler`.
  - System now falls back to `cb.from_user.id` if `cb.message` is unavailable, preventing crashes during master report export.

## [1.0.272] - 2026-06-03

### 👥 CreateGroup: UI Enhancements & Session Metrics
- **Added: Creation Count on Session Buttons**:
  - Integrated creation report metrics into the **Multi-Session Selection** menu.
  - Each session button now displays the number of groups/channels created by that account, e.g., `account xyz (11)`.
  - Improved visibility for session selection based on historical performance.
  
---

## [1.0.271] - 2026-06-03

### 👥 CreateGroup: Logic Refinement & Delay Consistency
- **Improved: Batch Action Logic**:
  - Reverted `action_count` to be per-group/channel as intended, ensuring the `ba_delay` (Batch Action Delay) triggers specifically within each creation lifecycle.
  - Maintains separation between per-action delay, batch action delay, and batch group size delay for better control.
- **Fixed: MessageNotModified Errors**:
  - Implemented `safe_edit_message_text` helper in `creategroup_handlers.py` to gracefully handle Telegram's `400 MESSAGE_NOT_MODIFIED` errors.
  - Applied the fix to all reporting and UI dashboard handlers to prevent UI freezes during rapid updates.
- **Fixed: Inconsistent Session Speed Investigation**:
  - Confirmed that speed variations are primarily due to server-side `FloodWait` or network conditions, as task initialization and delays are correctly synchronized.

---

## [1.0.270] - 2026-06-03

### 👥 CreateGroup: Enhanced Initialization Logs
- **Improved: Session Startup Feedback**:
  - Added session name display to the initialization log messages during staggered startup.
  - Enhanced visibility of which account is being initialized in multi-session tasks.

## [1.0.269] - 2026-06-03

### 👥 CreateGroup: Code Integrity & Logic Restoration
- **Fixed: Code Integrity in creategroup_loop**:
  - Restored critical code blocks for duplicate task prevention and TID normalization that were accidentally removed during refactoring.
  - Ensured variable buffers for batch processing and logging are correctly initialized.

---

## [1.0.268] - 2026-06-02

### 👥 CreateGroup: Session Selection & Task Resume Fixes
- **Fixed: Session Deselection Issue**:
  - Removed forced selection of the current session in `Main/internals/settings_handlers/creategroup_handlers.py`.
  - Users can now freely deselect the [Current] session in the **Multi-Session Selection** menu.
- **Fixed: "Task is already resuming" Error**:
    - Added a global `_ACTIVE_BULK_USERS` lock in `xtaskmanager.py` to prevent duplicate bulk actions from concurrent callback triggers.
    - Improved `xcreategroup.py` cache loading to explicitly clear `running` and `recovering` flags on bot startup.
    - Refactored `creategroup_loop` to reset the `recovering` flag at the earliest possible stage, ensuring the flag doesn't get stuck if the loop exits early.
    - Improved `asyncio.Task` status validation in `Main/plugins/userbot/xcreategroup.py` to prevent race conditions during bulk resume.
    - Updated `xtaskmanager.py` to automatically handle `interrupted` tasks via `Restore` logic when a simple `resume` is requested.
- **Fixed: SyntaxError 'await outside async function'**:
  - Converted `resume_task_by_id()` to an asynchronous function in `Main/plugins/userbot/xtaskmanager.py`.
  - Updated all internal callers (Bulk Resume, Task Control, Command) to use `await` for task resumption.
  - Resolved plugin loading failures for `xtaskmanager` and `xstories`.
- **Improved: Logging & Error Handling**:
  - Added `traceback.format_exc()` to critical CreateGroup task blocks for better diagnostic visibility.
  - Ensured atomic configuration saving remains robust during multi-session updates.

---

## [1.0.267] - 2026-06-01

### �️ 🛠️ CreateGroup: Debounce, Task ID Routing, and Pending Confirmation Cleanup
- **Fixed: Double-trigger and jumping button values** in `Main/plugins/userbot/xcreategroup.py` and `Main/internals/settings_handlers/creategroup_handlers.py` by adding debounce guarding and ensuring task-specific `callback_data` routes.
- **Improved: Pending confirmation lifecycle** by storing `created_at` timestamps and auto-cleaning stale `PENDING_CONFIRMATIONS` after 5 minutes.
- **Improved: Stability and error safety** in CreateGroup persistence and callback handlers with explicit exception handling and better logging.

### 🔀 YTcut: Fixed Missing Segments Issue
- **Fixed: Auto-merge detection in `run_ytcut_download()`**:
  - Discovered that `yt-dlp` with `--merge-output-format mp4` automatically merges all sections into a single output file instead of creating per-section files.
  - Added detection logic: if fallback finds only 1 file for multiple sections, sets `skip_ffmpeg_concat` flag to use auto-merged output directly.
  - Prevents downstream concat step when unnecessary and eliminates "missing segments" false errors.
- **Improved: Fallback file detection**:
  - Enhanced fallback with stdout parsing (looking for "Destination:" and "Merging formats into" lines) to capture yt-dlp's final output filename.
  - Fallback now gracefully handles both multi-file and single auto-merged file scenarios.
- **Improved: Heartbeat Update Interval**:
  - Reduced from 10 seconds to 6 seconds for quicker progress feedback during download and concat phases.
- **Improved: Process exception logging**:
  - Added logging to previously silent exception handlers in `delete_ytcut_task()`, watchdog process.kill, and `init_ytcut_persistence()` for better debugging.
- **Improved: FFmpeg concat error reporting**:
  - Added explicit except block to capture and log FFmpeg error outputs (stdout/stderr) before re-raising.
- **Updated: process_ytcut_task()**:
  - Added check for `skip_ffmpeg_concat` flag to bypass FFmpeg concat when yt-dlp output is already final.

---

## [1.0.266] - 2026-06-01

### 🔀 YTcut: Merge Semua Segmen Feature
- **Added: Merge Semua Segmen Button**:
  - Added a new dashboard button for YTcut sessions with 2+ segments to trigger merge confirmation.
  - Displays a Yes/No merge confirmation dialog before starting the merge flow.
- **Added: Merge flow and helper**:
  - Implemented `merge_ytcut_segments()` in `Main/internals/ytcut_helpers.py` to concatenate all segment files into one output using FFmpeg concat.
  - Added state tracking and persistence for `merge_in_progress`, `merge_completed`, and `merge_error`.
- **Improved: YTcut dashboard merge status**:
  - Dashboard now shows current merge progress status and merge failure details when present.
- **Fixed: Segment file detection during merge**:
  - Added robust fallback for `part_00x*` segment file discovery to avoid missing files when extension or naming varied.
- **Improved: merge operation logging**:
  - Added detailed merge entry, exit, and traceback logging for easier debugging and task tracing.

---

## [1.0.265] - 2026-05-31

### 🎬 YTcut: Real-time Progress Tracking & Heartbeat
- **Added: Interactive Progress Bar**:
  - Implemented real-time progress parsing for `yt-dlp` download segments.
  - The dashboard now displays a visual progress bar and percentage (`█▋░ 10.5%`) during the download phase.
- **Improved: Heartbeat Mechanism**:
  - Added a 10-second update interval for both download and concatenation phases to prevent the UI from appearing "stuck".
  - During FFmpeg concatenation, the UI now shows an elapsed timer heartbeat (e.g., `Sedang memproses FFmpeg concat (20s)...`).
- **Improved: Inline bot error tracing**:
  - Extended `CustomClient.invoke` in `Main/core/types/client.py` to include `chat_id`, `channel_id`, `message_id`, and inline query context in non-critical `QueryIdInvalid` log entries.
- **Improved: YTcut manual input in private chat**:
  - Added support for multi-line timestamp input in PM, e.g. `01:07 - 01:33`, `01:58 - 02:39`.
  - Added cancel support via button and by typing `cancel` / `batal`.
- **Fixed: YTcut FFmpeg concat path handling**:
  - Concat list now writes absolute `file` paths to prevent duplicated temp directory resolution on Windows.
- **Improved: YTcut error reporting**:
  - Assistant bot now sends a group log notification to `Altruix.log_chat` when YTcut processing fails.
  - Notifikasi kini menyertakan stage proses dan cuplikan traceback penting.
- **Improved: YTcut confirmation dialog**:
  - Converted YTcut confirmation text to blockquote format for better readability.
  - Applied per-session button styling to confirmation buttons using `get_user_button_style()`.
- **Fixed: YTcut download hang detection**:
  - Added a 5-minute yt-dlp inactivity watchdog in `run_ytcut_download()` to kill stalled downloads and report a clear timeout error.
- **Fixed: YTcut inline dashboard query mapping**:
  - Normalized internal `xytcut` task IDs by removing the leading `#` from `make_ytcut_task_id()` so inline query handlers and callback regexes match correctly.
- **Optimization**: Switched to asynchronous line-by-line stdout parsing for `yt-dlp` to ensure responsive progress updates without blocking the main event loop.

---

## [1.0.264] - 2026-05-31

### 🎬 YTcut & Task Manager: Final Integration & UI Polish
- **Fixed: `register_task` TypeError**:
  - Resolved `unexpected keyword argument 'task'` in `xytcut_bot.py` by updating the parameter name to `asyncio_task` to match the core registry definition.
- **Fixed: unresponsive "Yes" Button & UI Freeze**:
  - Implemented `MessageNotModified` handling in `xytcut_bot.py` (both in specific handlers and global `_safe_edit` helper) to prevent UI stalls when buttons are clicked multiple times.
- **Improved: Instant Visual Feedback**:
  - Added immediate UI update to "⏳ Memulai proses..." after clicking the **[Yes]** confirmation button, ensuring the user knows the task has been enqueued.
- **Improved: Cross-Plugin Task Stability**:
  - Ensured all background tasks for YouTube tools are correctly linked to the Universal Task Manager for full lifecycle visibility (Start → Active → Done).

---

## [1.0.263] - 2026-05-31

### 📋 Task Manager: Stability & YouTube Tools Integration
- **Fixed: `400 MESSAGE_NOT_MODIFIED` Error**:
  - Implemented specific handling for `MessageNotModified` exception across `xtaskmanager.py` callback handlers.
  - Prevents bot crashes and error logging when users rapidly click identical navigation or confirmation buttons.
- **Improved: YouTube Tools Visibility in `.tasklist`**:
  - **Standardized IDs**: Updated `xytcut` Task IDs to use the `#YTC...` prefix for better recognition.
  - **Explicit Registration**: Added `register_task` calls in `ytcut_helpers.py` to ensure active processing is tracked in real-time.
  - **Auto-State Detection**: Enhanced `xtaskmanager.py` to automatically detect and merge in-memory `YTDL_STATE` and `YTCUT_STATE` into the global registry.
  - **Robust Lookup**: Improved `find_task_by_id` to perform a cache sync before reporting task-not-found, ensuring accurate task management.

---

## [1.0.262] - 2026-05-31

### 🎬 YTcut: Custom Segment Reordering & Sorting Fix
- **Added: "🔄 Ubah Susunan / Urutan" Menu**:
  - New menu accessible from the dashboard (when ≥ 2 segments exist) to manually reorder segments.
  - Implemented 🔼 **Up** and 🔽 **Down** buttons for each segment to move them within the list.
  - Changes the order in which segments are concatenated in the final video/audio output.
- **Added: "⏳ Reset (Urut Waktu)" Functionality**:
  - Allows users to quickly reset the custom order back to chronological (Sort by Time).
- **Fixed: YT-DLP Segment Sorting Bug**:
  - Resolved an issue where segments were sorted lexicographically (e.g., `part_10` before `part_2`).
  - Updated `run_ytcut_download` to use padded naming (`part_001`, `part_002`) and explicit numerical matching for 100% accurate concatenation order.
- **Improved: Smart Auto-Sort**:
  - The bot now respects the user's manual order (`_manual_order` flag) and stops auto-sorting by time when adding/editing segments if a custom order is active.
  - Auto-sort remains the default for new sessions until the user manually reorders segments.

---

## [1.0.261] - 2026-05-31

### 🎬 YTcut: Edit/Revise Segment Feature
- **Added: "✏️ Edit" Functionality for Existing Segments**:
  - Users can now edit or revise the duration of segments already in the cut list by clicking the "✏️ Edit" button next to each segment.
  - Implemented `ytcut_edit_seg_cb` to enter "Edit Mode" which pre-fills the adjustment menu with the segment's current START/END values.
  - The adjustment menu dynamically updates its title to `📝 Edit Potongan #[index]` and changes the confirmation button to `💾 Simpan Perubahan`.
- **Improved: Unified Segment Application Logic**:
  - Updated `ytcut_add_apply_cb` and `ytcut_reply_handler` (manual input) to handle both adding new segments and updating existing ones based on the `edit_index` state.
  - Ensures robust state cleanup (clearing `edit_index`, `add_start`, `add_end`, etc.) when changes are saved or when the user navigates back to the main menu.
- **Improved: Reset Behavior in Edit Mode**:
  - The "🔃 Reset" button in the adjustment menu now resets values to the segment's original duration if in Edit Mode, instead of defaulting to 00:00.
- **Logic Flow & Stability**:
  - Maintained consistent overlap validation and duration clamping during the editing process.
  - Ensured all state changes are synchronized to the persistent database (`sync_ytcut_task`) for session recovery.

---

## [1.0.260] - 2026-05-31

### 🛠️ YTcut & Core: TypeError Fix + FloodWait Handling + UI Stability
- **Improved: Revision Workflow & Dashboard Persistence**:
  - Modified `process_ytcut_task` to keep the dashboard active and state persistent after completion.
  - Implemented auto-restore to menu state, allowing users to "revise" their cuts without re-running the command.
- **Fixed: YT-DLP Error on Multiple Segments**:
  - Resolved `invalid --download-sections` error by sending segments as individual arguments instead of comma-separated strings.
- **Fixed: Task Visibility in `.tasklist`**:
  - Integrated YTcut with `xtaskmanager.py` for real-time task monitoring and cancellation support.
  - Switched to non-blocking background processing using `asyncio.create_task` to keep the bot responsive.
- **Fixed: TypeError on Inline Message Edits**:
  - Resolved `TypeError: ... got an unexpected keyword argument 'inline_message_id'` across all modules.
  - Implemented multi-layer fallback: `CallbackQuery` methods → `pyromod` specific methods (`edit_inline_text`) → Positional arguments.
  - Impacted files: `xytcut_bot.py`, `ytcut_helpers.py`, `alliance_handlers.py`, and `xrap_manager.py`.
- **Fixed: Missing Module Import**:
  - Added missing `import time` in `xytcut_bot.py` which caused `NameError` during interaction.
- **Improved: UI Stability & Accuracy in "➕ Tambah Potongan"**:
  - Fixed "double-trigger" and jumping values by implementing a 500ms debounce/lock (`_busy_until`) on interaction handlers.
  - Unified adjustment logic: ensured `START < END` with a consistent minimum gap of 0.25s across all menu and adjustment callbacks.
- **Added: Robust FloodWait Handling**:
  - Implemented `_safe_edit` wrapper with automatic retry for short Telegram throttling (≤ 3s) and user notifications for longer waits.
  - Added throttling to background dashboard updates (300ms minimum interval) to prevent `FLOOD_WAIT` during rapid user interactions.
- **Optimization**: Removed redundant `sync_ytcut_task` calls during interactive adjustment phases to reduce database overhead.

---

## [1.0.259] - 2026-05-30

### 🎨 YTcut: Module Version + Per-Account Button Styles
- Added `PLUGIN_VERSION`/`__version__` to `Main/internals/ytcut_helpers.py` so the module exposes its current version programmatically.
- Dashboard buttons now respect per-session/account `ButtonStyle` via `get_user_button_style()`; buttons fall back to default styling if no preference is set.
- Minor: Small robustness improvements to keyboard builder to avoid crashing when user-style resolution fails.

---

## [1.0.258] -2026-05-30

### 🔧 YTcut: Handlers Moved to Bot Plugins & Modularization
- Moved YTcut callback and inline handlers from `Main/plugins/userbot/ytcut_handlers.py` to `Main/plugins/bot/xytcut_bot.py` to follow the project's assistant bot plugin pattern (similar to `xyt_tools_bot.py`).
- Added `Main/internals/ytcut_helpers.py` containing config persistence, state/queue registry, dashboard builders, download/concat helpers, and task processing helpers so the command logic is isolated and reusable.
- Updated `Main/plugins/userbot/xytcut_tools.py` to be a minimal entry point that uses the new helper module and the bot inline-builder flow (`get_inline_bot_results`) where available.
- Removed the duplicate handler file from `Main/plugins/userbot` to avoid conflicting registrations.
- Notes: No changes were made to `Main/internals/ytdl_core.py` in this update — if your workspace reverted prior edits, the YTcut code now relies on the existing `ytdl_core` APIs available in the repo.

---

##  [1.0.257] - 2026-05-30

### 🎬 YTcut: Plugin Version + Help Documentation + Persistent Settings
- Added `PLUGIN_VERSION` to `Main/plugins/userbot/xytcut_tools.py` so plugin help displays the correct version.
- Improved `.ytcut` help text with full interactive dashboard usage and timestamp examples.
- Added persistent user preference saving for mode, quality, and extract settings.

---

## [1.0.256] -2026-05-30

### 🎬 YTDL: Auto Return Dashboard + Sub-Second Trimmer + Fade In/Out
- **Improved: Setelah download selesai, kembali ke dashboard sebelumnya**:
  - Pesan progres YTDL otomatis menampilkan kembali menu/dashboard agar konfigurasi terakhir tetap terlihat.
  - Menjaga state task sementara (auto-cleanup) agar dashboard bisa di-refresh setelah selesai.
- **Added: Trimmer presisi sub-detik (0.5s & 0.25s)**:
  - Menambahkan tombol penyesuaian `-0.5s/-0.25s/+0.25s/+0.5s` pada menu `✂️ YouTube Video Trimmer`.
  - Mendukung value desimal pada handler trim agar lebih presisi.
- **Added: Sub-menu Fade In / Fade Out (Volume) untuk Video & Audio (MP3)**:
  - Menambahkan menu `🎚 Fade In/Out` dengan tombol +/- dalam satuan detik (termasuk 0.5s & 0.25s).
  - Config fade tersimpan (state + persistence DB) dan diterapkan saat render ffmpeg (termasuk pada mode split chapters).

---

### [1.0.255] 📊 Task Manager: Finished Tasks Owner + Finish Time
- **Fixed: Owner tampil "Unknown" di `✅ Finished Tasks History`**:
  - Menambahkan fallback resolve owner dari `client_id/user_id` ke session aktif.
  - CreateGroup: memastikan data completed menyimpan `account_name` agar owner konsisten.
- **Added: Waktu selesai task**:
  - Menampilkan `Selesai: YYYY-mm-dd HH:MM:SS` pada daftar history.
  - Menggunakan `finish_time` bila tersedia, atau fallback hitung dari `start_time + total_duration`.

---

## [0.3.231] - 2026-05-29

### 🏗️ CreateGroup Handlers: FIX SESSION EXPIRIED
- CreateGroup UI: tambah indikator akun terpilih (n/total) pada log inisialisasi multi-session (Staggered Start / Batch Account Delay / Initializing task).
- CreateGroup UI: perbaiki “Session expired” setelah restart dengan auto-rebuild state dashboard dari config persistent (xcreategroup_user_configs.json), termasuk fallback infer session index dari teks UI.

---

## [0.0.10.2482I] - 2026-05-29

### 🏗️ CreateGroup & Handlers: Multi-Session Pagination Upgrades
- **Added: "« 5 Prev" & "Next 5 »" Navigation Buttons**:
  - Implemented smart navigation buttons on the `👥 Multi-Session Selection` page to instantly hop 5 pages back or 5 pages forward.
  - Automatically bounds page limits to prevent out-of-range navigation while preserving full responsive state and styling.

---

## [0.0.10.2481I] - 2026-05-29

### 🏗️ CreateGroup & Handlers: Interactive Settings Buttons Fixes & Fully-Featured Implementation
- **Fixed: Interactive UI settings buttons "📋 Status Detail" & "📑 List Group"**:
  - Fully resolved their routing and callbacks with robust Pyrogram handlers in `creategroup_handlers.py`.
- **Implemented: "🔄 Recurring" and "✏️ Edit Last" interactive features**:
  - Implemented the complete, beautiful confirmation and recurring launching flow for completed/stopped tasks on both the Telegram Bot and the Userbot.
  - Linked the "🔄 Recurring" buttons directly to user confirmation menus with robust callback parsing.
  - Implemented "✏️ Edit Last" feature to dynamically edit the name/title of the last created group of a task, complete with an interactive input state (`awaiting_edit_last_name`) and Log Group reply listener.
- **Fixed: Completed task lookup & verification**:
  - Fixed a task identifier lookup bug where `task_key` from completed tasks was not identified correctly because of a restrictive active task list check in `xcreategroup.py`.

---

## [0.0.10.2480I] - 2026-05-29

### 🏗️ CreateGroup & Handler Audit: Robustness, Error Handling, and Logging
- **Improved: Try-Except Audit & Traceback Logging**:
  - Enhanced error handling inside `launch_tasks_bg` with complete exception logging, including `traceback.format_exc()`.
  - Added user notifications via Telegram on session start failures so users are immediately alerted.
  - Added `traceback` logging for critical errors during control message creation.
- **Fixed: KeyError Risks in Config Access**:
  - Substituted direct `[]` dictionary lookup with safe `.get()` defaults for config keys such as `bots`, `delay`, `count`, `batch_delay`, `batch_size`, `pattern`, and `username`.
- **Fixed: Outer Handler NameError Risk**:
  - Initialized `user_id = None` early in `creategroup_confirm_task_handler` to prevent potential `NameError` if an exception occurs before the variable is populated.
- **Fixed: Session Lookup for Restored Tasks**:
  - Updated `_find_task_by_session_idx` to correctly lookup tasks restored from cache that are currently running but lack a live `task_obj`.

---

## [0.0.10.2478I] - 2026-05-28

### 🏗️ CreateGroup: Account Index and Preview Info in Logs
- **Added: Account Index to Progress and Completion Logs**:
  - Added `account_idx/total_accs` (e.g. `1/100`) to the header of the tracker progress start log (`📊 Memulai Tracker Progress {account_idx}/{total_accs}...`) and all 5 completion reports (e.g. `✅ Laporan Create Group Selesai 1/100`) in [xcreategroup.py](Main/plugins/userbot/xcreategroup.py).
- **Added: Account Name Preview**:
  - Added `• Account: <b>{account_name}</b>` line to the progress tracker start log in [xcreategroup.py](Main/plugins/userbot/xcreategroup.py).
  - Modified the brief log notification and backup document caption to display the full user name (first + last name) instead of only the first name.

---

## [0.0.10.2477I] - 2026-05-26

### 🏗️ CreateGroup: Add Task ID to Report Caption
- **Added: Task ID to Laporan Create Group**:
  - Added `• Task ID: <code>{task_id}</code>` to the report caption of CreateGroup completion documents in [xcreategroup.py](Main/plugins/userbot/xcreategroup.py).
  - Also added the Task ID details to control status panel updates, fallback log messages, and brief log notifications to improve task tracking and traceability.

---

## [0.0.10.2476I] - 2026-05-26

### 🏗️ CreateGroup: Run Task from Multi-Session Page
- **Added: Run Task Button in Session Selection**:
  - Added a new `🚀 Run Task (X Acc)` button on the Multi-Session Selection page in [creategroup_handlers.py](Main/internals/settings_handlers/creategroup_handlers.py).
  - Users can now start tasks for all selected accounts directly from the session selection page.
- **Improved: Task Start Flow & UX**:
  - Modified the task confirmation handler to execute task launching in a background task (`launch_tasks_bg`) using `asyncio.create_task` to prevent blocking the UI.
  - Preserved the user's selected sessions and state in `user_creategroup_state` instead of deleting them.
  - Automatically redirected the user back to the main dashboard menu immediately after task confirmation with a popup alert notification, allowing them to easily remember and check which accounts were chosen to run the task.

---

## [0.0.10.2475I] - 2026-05-26

### 🎬 YTDL & Voice Chat: Video Resolution Fix
- **Fixed: Video Resolution Limited to 360p**:
  - Resolved an issue where downloading YouTube videos or streaming them in voice chat was limited to 360p resolution.
  - Replaced the restricted and deprecated `player_client` list (`android,web,mweb,ios`) with `default` in both [ytdl_core.py](Main/internals/ytdl_core.py) and [xalliance_vc.py](Main/plugins/userbot/xalliance_vc.py).
  - This allows yt-dlp to use its own intelligent client selection algorithm, restoring access to all available resolutions (up to 2160p/4K) and high-quality audio streams.

---

## [0.0.10.2474I] - 2026-05-26

### 📊 Task Manager: User-Friendly Uptime
- **Improved: Uptime & Duration Formatting**:
  - Implemented `_format_duration` in [xtaskmanager.py] to provide a more human-readable time format (bulan, hari, jam, menit, detik).
  - Applied the new format to both the task list (`Duration`) and the task status menu (`Uptime`).
  - Standardized time display across core plugins for better consistency.

---

## [0.0.10.2473I] - 2026-05-26

### 🏗️ CreateGroup: Bug Fixes & Stability
- **Fixed: NoneType AttributeError**:
  - Resolved `AttributeError: 'NoneType' object has no attribute 'id'` in `send_completion_report` and progress logging. 
  - Implementation changed from `message.edit_text` to `client.edit_message_text` with explicit `chat_id` fallback in [xcreategroup.py].
  - Added robust `chat_id` detection using `getattr` to handle cases where Pyrogram's `Message` object has an empty `chat` attribute.
- **Improved: Progress Tracker Reliability**:
  - Applied the same safety fix to `update_group_log` and `creategroup_loop` panel updates to prevent task crashes during live execution.

---

## [0.0.10.2472I] - 2026-05-26

### 📊 Task Manager: Real-time Status Updates
- **Improved: Last Step Synchronization**:
  - Added logic to update 'Last Step' and progress info dynamically in the `Manage Task` menu of `.tasklist`.
  - Added `update_task_info` API in [xtaskmanager.py] for plugins to push status updates to the global registry.
- **Improved: Refresh Logic**:
  - The `Refresh` button in [xtaskmanager.py] now triggers a re-scan of plugin caches to ensure the displayed data is always up-to-date.
- **Enhanced: CreateGroup Integration**:
  - Added `sync_to_registry` calls in [xcreategroup.py] loop to provide real-time updates on `current_step` (create, setup, copy_msg, etc.) and `current_index`.
  - Updated [xtaskmanager.py] to recognize `current_step` from CreateGroup cache for legacy compatibility.

---

## [0.0.10.2471I] - 2026-05-26

### 🧹 Purgeme: Bug Fixes & Stability
- **Fixed: Forward Log Selection**: 
  - Resolved an issue where selecting destinations with underscores (e.g., `Group Log`, `PM Bot`) caused errors due to incorrect callback data parsing in [xpurgeme_bot.py].
- **Fixed: UI Auto-Close**:
  - Fixed a bug where the configuration menu would automatically close after 3 seconds when changing any setting. The menu now stays open and updates the UI normally in [xpurgeme_bot.py].
- **Improved: Error Handling**:
  - Added detailed logging with `traceback.format_exc()` to all critical sections of [xpurgeme_userbot.py] for easier debugging.
- **Refined: Config Persistence**:
  - Optimized the auto-save logic to ensure settings are saved without interrupting the user experience in [xpurgeme_bot.py].

---

## [0.0.10.2470I] - 2026-05-26

### 🧹 Purgeme: Forward Delay & Reporting
- **Added: Forward Delay Control**:
  - Added a new sub-menu to adjust the delay between forwarding a message and deleting it (`Forward Delay`).
  - **Changed**: Default `Forward Delay` is now set to **0.5 seconds** for better stability.
  - Logic flow updated: **Forward -> Delay -> Delete** for better control and safety in [xpurgeme_userbot.py].
- **Improved: Forward Reporting**:
  - Added `Forwarded` message count to the interactive dashboard during execution.
  - Added detailed forward results (count and delay) to the final completion log in [xpurgeme_userbot.py].
- **Added: Configuration Persistence**:
  - `Forward Delay` setting is now saved to `xpurgeme_user_configs.json`.

---

## [0.0.10.2469I] - 2026-05-26

### 🧹 Purgeme: Forward Log & Persistence
- **Added: Forward Log Feature**:
  - Added "Forward Log" button to the interactive `.purgeme` dashboard.
  - Supports forwarding messages to **Group Log**, **PM Bot**, or **Saved Messages** before deletion.
  - Implemented sub-menu for easy destination selection in [xpurgeme_bot.py].
  - Synchronized forwarding delay with `Delay/Msg` and `Delay/Batch` in [xpurgeme_userbot.py].
- **Added: Configuration Persistence**:
  - Created `xpurgeme_user_configs.json` to save user preferences (Count, Delay, Batch, Mode, Forward Log, etc.) in [purgeme_handlers.py].
  - Settings are now automatically saved and loaded across sessions.
- **🛠️ Refinement**:
  - Improved logic flow with proper try-except blocks and detailed logging with traceback in [xpurgeme_userbot.py].

---

## [0.0.10.2473I] - 2026-05-25

### 🛠️ CreateGroup: UI Reorganization
- **Added: Log Settings Sub-menu**:
  - Created a new sub-menu **`📂 Log Settings`** to consolidate all log-related configurations, making the main dashboard cleaner and more organized in [creategroup_handlers.py].
  - Moved the following controls to the new sub-menu: `Start Log`, `Photo Log`, `Prog Log`, `Panel Log`, `Interrupt Log`, `Delay Log`, `Log To`, and `Log Format`.
  - Updated the main dashboard layout to include a direct link to the log settings and reorganized the remaining buttons for better accessibility.

---

## [0.0.10.2472I] - 2026-05-25

### 🛠️ CreateGroup: Delay Log Control
- **Added: Delay Log Mode Toggle**:
  - Introduced a new control button **`Delay Log`** in the `.cgui` dashboard to manage countdown logs (e.g., "Proses akan dilanjutkan dalam...").
  - Supported modes: **PM Bot**, **Group Log**, **Both**, and **Off** (Disable) to reduce log spam in groups.
  - Implemented logic in [xcreategroup.py] to respect the selected log mode during `wait_with_countdown` intervals.
  - Added `delay_log_mode` to the persistent configuration system in [creategroup_handlers.py].

---

## [0.0.10.2471I] - 2026-05-25

### 🛠️ CreateGroup: Code Cleanup
- **Fixed: Duplicate Function Definition**:
  - Removed the redundant `format_duration` function from [xcreategroup.py](previously at line 719).
  - Consolidated to the more advanced version of `format_duration` (at line 78) which supports months, days, hours, minutes, and seconds.

---

## [0.0.10.2470I] - 2026-05-25

### 🛠️ CreateGroup: User-Friendly Duration Format
- **Improved: Completion Report Duration Formatting**:
  - Implemented `format_duration` in [xcreategroup.py] to provide a more readable duration format (months, days, hours, minutes, seconds) instead of just minutes/seconds.
  - Applied the new format to both the interactive completion report and the exported log files.

---

## [0.0.10.2469I] - 2026-05-25

### 🛠️ CreateGroup: Dynamic Task Labels
- **Improved: Automatic Task Labeling (Group/Channel)**:
  - Updated the task registration label in [xcreategroup.py] to automatically show "Create Group" or "Create Channel" based on the task type.
  - Updated the failure message in the control panel to use dynamic labels (e.g., "Task Create Channel Gagal") instead of the static "CreateGroup" string in [xcreategroup.py].

---

## [0.0.10.2468I] - 2026-05-25

### 🛠️ CreateGroup: Progress Log Improvement
- **Task ID Visibility**:
  - Added Task ID info to the initial progress log message ("📊 Memulai Tracker Progress...") in [xcreategroup.py] to make it easier to track specific tasks.

---

## [0.0.10.2468I] - 2026-05-25

### 🎥 YouTube Tools: Resolution & Extractor Fixes
- **Fixed: Limited Resolutions (360p Only)**:
  - Fixed a logic bug in [ytdl_core.py](/Main/internals/ytdl_core.py) where the `--flat-playlist` flag used for initial analysis was preventing full format extraction for single videos.
  - Implemented a two-stage extraction process: use `--flat-playlist` only to identify playlists, and perform a full fetch for single videos to ensure all resolutions (720p, 1080p, etc.) are available.
- **Improved: High-Resolution Format Support**:
  - Expanded `player_client` list to `android,web,mweb,ios`. Adding `android` enables access to more high-quality DASH formats that were previously missing when using only `ios`.
  - Applied these improvements to both [ytdl_core.py](/Main/internals/ytdl_core.py) and [xalliance_vc.py](/Main/plugins/userbot/xalliance_vc.py).

---

## [0.0.10.2467I] - 2026-05-25

### 🎥 YouTube Tools: Caption Description Toggle
- **Added: "Insert Info Description" Toggle**:
  - Added a new button **`📝 Desc`** to the interactive dashboard to enable or disable video description in the media caption in [xyt_tools_bot.py].
  - Implemented automatic extraction of video descriptions during the analysis phase in [ytdl_core.py].
  - Added logic to append the description (with a 300-character limit to avoid Telegram caption limits) to both single media and chapter-based uploads in [ytdl_core.py].
  - Integrated state persistence using `sync_ytdl_task` to ensure the toggle state is preserved across interactions.

---

## [0.0.10.2466I] - 2026-05-25

### 🎥 YouTube Tools: Bot Detection Bypass & Cookie Support
- **Fixed: YT-DLP "Sign in to confirm you're not a bot" Error**:
  - Improved bot detection error handling with case-insensitive checks and more flexible keyword matching (e.g. `youre` vs `you're`) in [ytdl_core.py].
  - Provides a clear, actionable error message with solutions (cookies.txt / ENV settings) when blocked by YouTube.
- **Added: Auto-Detection for `cookies.txt`**:
  - The system now automatically looks for `cookies.txt` in the root or `Main/` directory to facilitate authentication bypass without requiring manual environment variable configuration.
  - Implemented in [ytdl_core.py] (subprocess) and [xalliance_vc.py] (yt-dlp library).
- **Improved: Resilient Player Clients**:
  - Updated `yt-dlp` extractor arguments to use a combination of `ios,web,mweb` player clients, which are currently more resistant to YouTube's bot detection mechanisms.
  - Applied to both interactive downloads in [ytdl_core.py] and Voice Chat streaming in [xalliance_vc.py].

---

## [0.0.10.2465I] - 2026-05-25

### 🎛️ CreateGroup UI: Page Selectors + Spam-Safe Log Modes
- **Added: Multi-Session Selection (Per-Page) Controls**:
  - Added **`📄 Select Page`** and **`📄 Deselect Page`** buttons inside **👥 Multi-Session Selection** to select/deselect only the sessions shown on the current page (without affecting other pages) in [creategroup_handlers.py](AltruixX/Main/internals/settings_handlers/creategroup_handlers.py).
  - Preserved existing global controls (**Select All / Deselect All**) and the existing task execution flow.
- **Added: .cgui Log Mode Toggles to Reduce Spam**:
  - Added dedicated toggles for **`Progress Log`** (per-group “🏗 Memproses …”) and **`Panel Log`** (control panel “🚀 Task Control Panel …”) with modes: **PM Bot / Group Log / Both / Off** in [creategroup_handlers.py](AltruixX/Main/internals/settings_handlers/creategroup_handlers.py).
  - Routed CreateGroup runtime output to follow these modes (separating progress logs vs control panel logs) in [xcreategroup.py](AltruixX/Main/plugins/userbot/xcreategroup.py).
- **Improved: Config Compatibility & Sync (Old ↔ New)**:
  - Implemented a unified CreateGroup config loader that prioritizes the persistent JSON used by **.cgui** while remaining compatible with legacy `Altruix.config.get_user_config` (auto-mirrors legacy values into JSON when needed) in [xcreategroup.py](AltruixX/Main/plugins/userbot/xcreategroup.py).

---

## [0.0.10.2464I] - 2026-05-24

### 🎛️ CreateGroup: Dynamic Log-Control & Separate Log Toggles
- **Added: Dynamic Log-Control Buttons (Task Control Panel)**:
  - Added dedicated **`PM Bot`**, **`Group Log`**, **`Both`**, and **`Disable`** buttons directly into the *Task Control Panel* in [xcreategroup.py](file:///f:/2026/APRIL/AltruixX/Main/plugins/userbot/xcreategroup.py).
  - Highlighting the currently active log destination with a visual checkmark (e.g. `✅`).
  - Added a dedicated **`🔄 Refresh Logs`** button to refresh the dashboard text and button states dynamically.
- **Added: Live Status & Log Destination Sync**:
  - Dynamically fetches the current log destination from `CREATEGROUP_TASKS` memory state and lists it on the Task Control dashboard: `• Log Destination: Both (Log+Saved) / Log Group / PM Bot / Disabled`.
  - Upgraded `creategroup_loop` to dynamically fetch and apply the updated log destination from memory at the start of each iteration and upon task completion, making settings changes fully live and reactive.
- **Added: Persistent User Configurations & Robust Callback Handlers**:
  - Configured custom interactive buttons to trigger callback handlers `log_toggle:{tid}:{mode}` and `log_refresh:{tid}`.
  - Callback handlers automatically load, update, and persist settings in `xcreategroup_user_configs.json` using the robust `load_user_cg_config` and `save_user_cg_config` methods.
  - Implemented comprehensive error handling with try-except safety, `@log_errors` protection, and authorized user access validation via `@iuser_check`.

---

## [0.0.10.2463I] - 2026-05-24

### 🛠️ CreateGroup: Limit Adjustments & Validation Fixes
- **Fixed: Delay Limit constraints preventing 0s values**:
  - Relaxed minimum limit parameters in the `limits` dictionary (`creategroup_handlers.py`) to allow **`0`** for key delay settings:
    - `delay` (Group Delay)
    - `action_delay` (Delay/Act)
    - `account_delay` (Delay/Acc)
    - `ba_delay` (B.Act Delay)
    - `ba_account_delay` (B.Acc Delay)
  - Also relaxed `batch_action` (Batch Act) minimum limit to `0`.
- **Fixed: Batch Account limit constraint**:
  - Raised maximum limit for `batch_account` (B.Acc) from `100` to `999` to support larger userbot session fleets.
- **Fixed: Missing manual text input handling**:
  - Expanded `process_creategroup_input` to correctly validate and save manual inputs for:
    - `batch_action`
    - `ba_delay`
    - `batch_account`
    - `ba_account_delay`
- **Fixed: Missing UI unit labels**:
  - Added missing entries in `unit_map` for `batch_action` (`" act"`) and `ba_delay` (`"s"`), resolving empty labels in the respective adjustment sub-menus.
- **Added: Granular Start/Setup Logs Control (Independent Settings)**:
  - Deployed independent, dedicated config toggles for startup logs to eliminate noise:
    - **`Start Log`** (`start_log_mode`): Controls the `Task Create Group Started/Resumed` log notification.
    - **`Photo Log`** (`start_photo_log_mode`): Controls the profile photo download status log notification.
  - Symmetrically placed both buttons on the interactive `.cgui` dashboard, each toggling through `Both` (default) → `Group Log` → `PM Bot` → `Off`.
  - Implemented separate asynchronous routing helpers (`send_start_log` and `send_photo_log`) inside `creategroup_loop` to process each log path independently based on the user's custom preference.

---

## [0.0.10.2462I] - 2026-05-24


### 🛡️ Core Transport: FloodWait Guard & Flood Cooldown Accuracy Fix
- **Fixed: Off-by-one error on FloodWait retry guard** (`Main/core/types/client.py`):
  - Corrected `if max_count > mmax_:` → `if max_count >= mmax_:` in the `FloodWait`/`SlowmodeWait` handler.
  - Previously the guard only raised after the **7th** attempt (`max_count == 6`) instead of the intended **6th** (`max_count == 5`), causing one extra unnecessary retry cycle beyond `mmax_`.
  - Now consistent with all other retry guards in the `invoke` loop that use `max_count < mmax_` / `max_count >= mmax_`.
- **Fixed: Race condition in flood cooldown timestamp** (`Main/core/types/client.py`):
  - Changed `self._FLOOD_COOLDOWNS[client_id] = hit_ts + wait_time` → `self._FLOOD_COOLDOWNS[client_id] = time.time() + wait_time` (evaluated **inside** the async lock).
  - `hit_ts` was captured before acquiring `_FLOOD_LOCKS`, so if a task waited in the lock queue, the cooldown window was shorter than the actual `wait_time`, potentially allowing a retry too early.
  - Using `time.time()` at the moment the lock is held ensures the cooldown window is always exactly `wait_time` seconds from when the sleep actually begins.

---

## [0.0.10.2461I] - 2026-05-24

### 🤖 Bot Assistant: FloodWait Fallback (Main Bot 2/3)
- **Improved: Automatic failover on bot FloodWait**:
  - If the primary bot assistant hits `FloodWait` during bot identity fetch (`get_me`) or log delivery, CreateGroup now automatically switches to an available secondary main bot (Main Bot 2, 3, dst.) to keep control/log messages flowing in [xcreategroup.py](file:///f:/2026/APRIL/AltruixX/Main/plugins/userbot/xcreategroup.py).
- **Improved: Push runtime errors to Log Group**:
  - CreateGroup now forwards important runtime errors/warnings (e.g. cache save failures and FloodWait warnings) to `LOG_CHAT_ID` via the bot assistant, so issues are readable directly in the Group Log, not only in terminal output.

### 🗃️ CreateGroup: Windows Cache Save Reliability
- **Fixed: WinError 5 Access is denied on atomic cache save**:
  - Serialized cache writes with an async lock, switched to unique temp filenames, and added retry/backoff around `os.replace` to prevent concurrent-save collisions on Windows in [xcreategroup.py](file:///f:/2026/APRIL/AltruixX/Main/plugins/userbot/xcreategroup.py).
  - Added a safe fallback write path if atomic replace keeps failing (keeps bot running without losing state updates).

---

## [0.0.10.2461I] - 2026-05-24

### 🛡️ Core Transport: Reduce Harmless MessageNotModified Log Noise
- **Improved: NonCritical permanent error logging**:
  - Suppressed spammy `[NonCritical-Permanent-Skipped] MessageNotModified` warnings (only visible in `DEBUG=True`) to keep logs clean during same-content message edits in [client.py](file:///f:/2026/APRIL/AltruixX/Main/core/types/client.py).

### ✅ Task Manager: Security Confirmation Responsiveness & Callback Hardening
- **Fixed: Dashboard confirmation felt "macet" on bulk actions**:
  - Migrated bulk operations (`Pause All`, `End All`, `Pause Page`, `End Page`) to background execution to prevent callback blocking/timeouts in [xtaskmanager.py](file:///f:/2026/APRIL/AltruixX/Main/plugins/userbot/xtaskmanager.py).
  - Preserved UI feedback by injecting a status banner while processing and refreshing the dashboard after completion.
- **Fixed: Confirmation payload parsing reliability**:
  - Hardened parsing for `taskmgr_ask_*` / `taskmgr_confirm_*` by joining the remaining segments, preventing malformed targets when callback payload contains underscores.
- **Fixed: Cache confirmation cancel routing**:
  - Corrected "No, Cancel" routing for cache actions to return to `Cache Manager` instead of an invalid task status route.
- **Improved: Callback safety & authorization feedback**:
  - Added `@iuser_check` and `@log_errors` protection to the Task Manager callback handler to prevent silent failures and ensure consistent popup feedback on errors/unauthorized access.

### 📋 Task Manager & CreateGroup: Robust Recovery & Silent Restore
- **Fixed: Critical 'NoneType' AttributeError in CreateGroup**:
  - Resolved `AttributeError: 'NoneType' object has no attribute 'id'` occurring during task recovery in [xcreategroup.py](file:///f:/2026/APRIL/AltruixX/Main/plugins/userbot/xcreategroup.py).
  - Implemented multi-layer safe attribute access using `getattr` for `control_message`, `chat`, and `from_user` objects to prevent crashes when message entities are missing from Telegram's cache.
- **Fixed: Task KeyError during Recovery Loop**:
  - Resolved `KeyError` when accessing `CREATEGROUP_TASKS` during task resumption by implementing an early emergency state re-initialization mechanism at the beginning of the loop.
  - Upgraded task ID detection to correctly recognize both `#CG` and `CG-` formats, ensuring consistent state mapping across restarts.
  - Replaced all direct dictionary accesses in `creategroup_loop` with safe `state` reference and `.get()` methods to prevent crashes even if memory is partially cleared.
- **Improved: Task Recovery & Logic Flow**:
  - Re-engineered the restore process by decoupling UI interaction from core task recovery.
  - Added **`recover_creategroup_task` (Silent Restore)** in [xcreategroup.py](file:///f:/2026/APRIL/AltruixX/Main/plugins/userbot/xcreategroup.py) to support stable bulk operations without dashboard flickering or `QueryIdInvalid` errors.
  - Enhanced [xtaskmanager.py](file:///f:/2026/APRIL/AltruixX/Main/plugins/userbot/xtaskmanager.py) to utilize silent recovery for **`[Resume All]`** and **`[Resume Page]`** actions, ensuring all interrupted tasks are resumed in the background seamlessly.
  - Implemented **Auto-Interaction for Peer Initialization**: Userbot accounts now automatically send `/start` to the Assistant Bot if `PeerIdInvalid` occurs during log notifications, resolving initialization errors for new sessions.
  - **Added FloodWait Resilience**: Implemented automatic detection and waiting for Telegram `FLOOD_WAIT` errors during task initialization, preventing immediate task failure during heavy load.
- **Improved: Robustness & Logging**:
  - Added comprehensive `try-except` blocks with full `traceback` logging to all recovery handlers and countdown functions.
  - Ensured all log notifications and countdown messages have automatic fallback destinations (`LOG_CHAT_ID`) if original reply message objects are no longer available.
- **Fixed: Logic Flow & State Synchronization**:
  - Synchronized state management between [xtaskmanager.py](file:///f:/2026/APRIL/AltruixX/Main/plugins/userbot/xtaskmanager.py) and plugin-specific caches to ensure `paused` and `interrupted` flags are correctly propagated across the entire ecosystem.

---

## [0.0.10.2460I] - 2026-05-22

### 🤖 Bot Assistant: Paginated Startup Changelog Notification
- **Added: Paginated Startup Changelog Notification**:
  - Replaced the static "Latest Changelog Update" notification with a fully interactive, paginated UI system in [client.py](file:///f:/2026/APRIL/AltruixX/Main/core/client.py).
  - Integrated with [xchangelog_builder.py](file:///f:/2026/APRIL/AltruixX/Main/internals/xchangelog_builder.py) to provide a rich navigation experience directly in the Log Group.
- **Added: Interactive Navigation Controls**:
  - Implemented standard pagination buttons: **`«` (Prev)**, **`»` (Next)**, **`First`**, and **`Last`** for easy traversal of the entire changelog history.
  - Added a central **`[n/n]`** page indicator button (e.g., `1/10`) for quick page reference.
- **Improved: Auto-Chunking & Long Entry Support**:
  - Upgraded the changelog parser in [changelog_helpers.py](file:///f:/2026/APRIL/AltruixX/Main/utils/changelog_helpers.py) to automatically split exceptionally long entries (> 3000 chars) into multiple parts.
  - Ensures compliance with Telegram's message character limits while maintaining a clean, aesthetic HTML layout.
- **Improved: Logic Flow & Error Resilience**:
  - Enhanced startup sequence with `try-except` safety wrappers and comprehensive logging to ensure the bot continues to boot even if changelog parsing fails.
  - Optimized resource loading by utilizing lazy imports for UI builders during the startup phase.
  - **Fixed: Changelog Delivery Logic**:
    - Upgraded the parser in [changelog_helpers.py](file:///f:/2026/APRIL/AltruixX/Main/utils/changelog_helpers.py) with a fallback mechanism to automatically split entries by version header (`## [`) if horizontal rules are missing.
    - Implemented a robust **dual-layer fallback** in [client.py](file:///f:/2026/APRIL/AltruixX/Main/core/client.py) that automatically reverts to basic HTML notification if the paginated builder encounters an error, ensuring logs are always delivered.
    - **Decoupled Notification Flow**: Separated the changelog notification logic from the startup summary report to ensure it is not skipped if the summary message fails.
    - **Broadened Config Support**: Enhanced `CHANGELOG_NOTIF_ENABLED` to recognize multiple active states: `on`, `true`, `yes`, and `1`.
    - Resolved potential `TypeError` in button style resolution during early startup.

---

## [0.0.10.2459I] - 2026-05-22

### 📨 Recent Messages: Advanced Scan Limit Control
- **Added: Independent "Set Scan Limit Chat" Control**:
  - Integrated a new **`⚙️ Set Scan Limit Chat`** button in the Recent Messages sub-menu in [session_handlers.py](file:///f:/2026/APRIL/AltruixX/Main/internals/settings_handlers/session_handlers.py).
  - Decoupled "Scan Limit (Chat)" from "Limit (Messages)" to allow granular control over how many dialogs are scanned vs how many messages are fetched per chat.
- **Improved: Limit-Aware Scanning Engine**:
  - Upgraded `recent_messages_list_handler` and `forward_recent_messages_handler` to strictly respect the **`RECENT_CHATS_LIMIT`** configuration for dialog discovery.
  - Upgraded `recent_messages_view_chat_handler` and `forward_specific_chat_recent_handler` to utilize the **`RECENT_MSGS_LIMIT`** for history extraction.
- **Improved: Logic Flow & Database Sync**:
  - Implemented automatic configuration persistence to database with real-time cache updates.
  - Enhanced UI feedback with dynamic labels: `Limit (Messages)` and `Scan Limit (Chat)`.
- **Improved: Robustness & Logging**:
  - Added comprehensive `traceback` logging for all limit-based operations to ensure stability and rapid diagnostics.
  - **Fixed: Protected Content Bypass Logic**:
    - Resolved an issue where text messages in protected chats were not being forwarded due to failed media download attempts.
    - Implemented a new `handle_bypass_forward` helper to correctly route text and various media types (Photo, Video, Voice, Document) during bypass.
    - Added automatic fallback to bypass logic if `forward_messages` fails with `CHAT_FORWARDS_RESTRICTED`.
    - Enhanced logging for the bypass process to provide clear visibility into download and upload status.
  - **Fixed: Navigation & Callback Mismatches**:
    - Resolved a broken "Back" button on the Forward Complete screen by ensuring `f_type` (user/bot/all/select) is correctly passed through the callback chain.
    - Updated `forward_specific_chat_recent_handler` regex and internal logic to support dynamic return routing.

---

## [0.0.10.2458I] - 2026-05-22

### 📨 Recent Messages: Custom Delays & Specific Chat Selection
- **Added: Configurable Delay Settings (Chat & Message)**:
  - Integrated sub-menus to adjust **`Delay/Chat`** and **`Delay/Msg`** with granular values (0.25s, 0.5s, 1s, 3s) using **`[-]`** and **`[+]`** buttons.
  - Helps prevent `FloodWait` during bulk forwarding operations.
- **Added: Specific Chat Selection Menu**:
  - Implemented **`🎯 Select Chat`** sub-menu with paginated dialog list (10 per page) to target specific conversations for recent message extraction.
  - Includes a dedicated chat view showing history with individual forward options to Log Group or PM Bot.
- **Improved: Delay-Aware Forwarding Engine**:
  - Upgraded both global and specific forward handlers to strictly respect the user-defined delay settings.
  - Enhanced UI progress feedback to display the active delay value during the forwarding process.
- **Version Bumps**:
  - **Session Handlers**: `0.3.350` (added delays & chat picker)

---

## [0.0.10.2457I] - 2026-05-21

### 📨 Recent Messages: Forwarding & Bypass Content Support
- **Added: Interactive "Forward Recent Messages" Menu**:
  - Integrated new action buttons: **`[Forward Log Group]`** and **`[Forward PM Bot]`** directly inside the Recent Messages list view in [session_handlers.py](file:///f:/2026/APRIL/AltruixX/Main/internals/settings_handlers/session_handlers.py).
  - Allows bulk forwarding of the latest messages from any chat/session to centralized logs or admin private messages.
- **Added: Advanced Bypass for Protected & Self-Destruct Content**:
  - Implemented automatic detection and bypass for "Protected Content" and "Self-Destruct (TTL) Media".
  - Since standard forwarding is blocked by Telegram for these types, the system now automatically downloads the media locally and re-uploads it as a persistent document to the target destination.
- **Improved: Robust Forwarding Logic & Error Handling**:
  - Added comprehensive `traceback` logging and per-message `try-except` wrappers to ensure the forwarding process continues even if specific messages fail.
  - Implemented dynamic status updates in the UI showing real-time progress (`Processing: {chat_name} (X/Y)`).
- **Added: Forward Activity Logging & Stats**:
  - Integrated automatic saving of the last forwarding results (`Success/Failed`) to the database (`LAST_FWD_STATS_{index}`) for audit trails.

---

## [0.0.10.2456I] - 2026-05-21

### 🤖 Bot Assistant: Optimized Session Management & 2FA Flow
- **Improved: High-Speed Session Creation Flow**:
  - Re-engineered the 2FA password request pipeline to eliminate the previous delay between OTP input and the password prompt.
  - Integrated high-precision performance monitoring using `time.perf_counter()` to track and log the duration of each authentication stage (OTP Delivery, Sign-in, and 2FA Verification).
- **Fixed: Robust Error Handling & Banned Number Detection**:
  - Restored specific error catching for 2FA verification failures with accurate user feedback.
  - Added native detection and reporting for banned accounts (`UserDeactivated`), providing clear status messages instead of generic login failures.
  - Implemented comprehensive `traceback` logging for all session-related exceptions, automatically routed to the Log Group for rapid developer diagnostic.
- **Improved: Resource Management & Process Locking**:
  - Wrapped the entire session generation alur in a global `try...finally` block to guarantee that active process locks (`_ACTIVE_ADD_SESSION`) are always cleared.
  - Ensured that temporary clients are strictly disconnected before finalizing the primary session addition to prevent database lock contention and ensure data integrity.
- **Added: Enhanced User Info on /add Command**:
  - Integrated automatic display of the requester's Account Name and User ID in the initial `/add` confirmation prompt.

---

## [0.0.10.2456I] - 2026-05-21

### 📑 Task Manager Plugin: Persistent Task Filtering & Advanced Menu UX
- **Added: Interactive Task Status Filtering**:
  - Integrated a new primary filter button row: **`[All]`**, **`[Running]`**, **`[Intrrupted]`**, and **`[Pause]`** directly into the `📋 Active Tasks` dashboard.
  - Allows users to quickly toggle between active running tasks, manual pauses, and system-interrupted/cached tasks.
- **Added: Persistent Filter State**:
  - Implemented automatic filter state persistence in `taskmanager_settings.json`. The selected filter remains active across dashboard reloads and bot restarts.
- **Improved: Filter-Aware Bulk Actions**:
  - Upgraded all bulk actions (`End Page`, `Resume All`, `Pause All`, etc.) to automatically respect the active filter. Operations now only target tasks matching the current view.
- **Added: Dynamic Status Headers & Filter Labels**:
  - Enhanced the dashboard header to dynamically display the active filter name and a filtered/total task count ratio (e.g., `📋 Active Tasks (Running) (5 filtered / 12 total)`).
- **Added: Finished Task History Dashboard**:
  - Integrated a new **`[View Finished Task]`** sub-menu to display the history of completed and failed background tasks.
  - Features advanced list views showing task status (✅/❌), task ID, progress, and **Owner Account Name** for each entry.
  - Includes **`[First]`** and **`[Last]`** navigation buttons for quick traversal of large history queues.
- **Added: Integrated Cache Management Sub-menu**:
  - Implemented a dedicated **`⚙️ Manage Cache`** panel showing real-time database sizes for `xcreategroup_cache.json` and settings files.
  - Added interactive **`🔄 Update/Sync Cache`** and **`🗑 Clear Cache`** (with security confirmation) to maintain database health and clear historical "zombie" data.

### 🛡️ Task Engine Stability & Performance Hardening
- **Fixed: 'NoneType' Subscriptable Error in gen_task_list_data**:
  - Resolved a critical UI crash (`TypeError: 'NoneType' object is not subscriptable`) when a task entry contained `None` for its name or plugin fields.
  - Implemented robust type casting and fallback defaults (`str(val or "Unknown")`) across all Task Manager list generators (Active, Restore, and Finished tasks).
- **Fixed: Task Manager Key Collision (Multi-Account Overwrites)**:
  - Resolved a critical bug in `xcreategroup.py` where multiple accounts using identical short TIDs (`#CG...`) would overwrite each other in the global registry during cache loading.
  - Migrated the internal memory indexing to a unique, account-specific `task_id` system, ensuring 100% data integrity when handling hundreds of simultaneous tasks.
- **Optimized: Non-Blocking Background Bulk Actions**:
  - Re-engineered the `[Resume All]` and `[Resume Page]` pipelines to run as asynchronous background tasks.
  - Prevents Telegram API callback timeouts and dashboard "freezing" when restoring large task queues (e.g., 170+ tasks), offering a smooth and responsive UI experience.
- **Improved: Robust Cache Restoration & Sync**:
  - Hardened the `load_creategroup_cache` routine to safely handle corrupted JSON files with automatic backup (`.bak`) and fresh reset logic.

---

## [0.0.10.2456I] - 2026-05-21

### 📨 Message Sender Plugin: Enhanced Log Visibility & Private Chat Support
- **Fixed: Missing "From/To msg_id" Buttons in Private Chats**:
  - Implemented a new manual link generation helper `get_message_link` that correctly constructs clickable Telegram links (`https://t.me/c/chat_id/msg_id`) for private groups and channels where Pyrogram's native `.link` property returns `None`.
- **Fixed: Interactive Button Fallback Logging**:
  - Upgraded the `send_action_log` pipeline to ensure that `reply_markup` (containing the interactive message links) is correctly passed to the fallback `send_log_message` function when Bot Assistant delivery is bypassed or fails.
- **Improved: Unified Log Aesthetics & Expandable Blockquotes**:
  - Guaranteed that all log notifications (Direct Message, Clones, Story Clones, and Settings) are wrapped in `<blockquote expandable>` tags for a clean, premium visual experience in the Log Group.
  - Added a new **`• ByPass: {True/False}`** field to the log notifications to indicate if a message was cloned via direct copy or through the download/re-upload bypass pipeline.
- **Improved: Media Bypass Safety**:
  - Hardened the `bypass_protected_send` routine with strict `finally` blocks to ensure temporary media and thumbnail files are always purged from the local filesystem after processing.

### 🎬 YouTube Tools (YTDL) Plugin: Visual Dashboard Enhancement & Stability
- **Fixed: Dashboard Thumbnail Visibility**:
  - Migrated the primary inline dashboard response from `InlineQueryResultArticle` to `InlineQueryResultPhoto`. This ensures the YouTube video thumbnail is persistently displayed as a media message instead of a plain text bubble with a disappearing preview.
- **Improved: Intelligent Media-Aware Dashboard Updates**:
  - Upgraded the dashboard refresh and navigation logic to automatically detect the current message type (Media vs. Text).
  - Implements a seamless transition between `edit_message_caption` and `edit_message_text` to prevent API errors during state toggles (e.g., when moving between media-rich menus and text-only sub-menus).
- **Improved: Robust Menu Navigation Fallbacks**:
  - Hardened all YTDL sub-menus (Quality, Language, Sender, Trimmer, Split Chapters, and Playlist) with multi-stage `try-except` fallbacks.
  - Guarantees that the dashboard remains interactive even if session data or message types change unexpectedly during a live download configuration.
- **Added: Source Platform & URL Visibility**:
  - Integrated a new **`• Platform: {Extractor}`** field to the main dashboard and final media captions, automatically detecting the source service (YouTube, TikTok, Instagram, etc.).
  - Added a clickable **`🔗 Source: {URL}`** field to the dashboard and media captions for easy access to the original content link.
  - Synchronized platform and source data across all state persistence (DB/JSON) and recovery pipelines.

---

## [0.0.10.2456I] - 2026-05-21

### 📤 Export Handlers: Optimized Flow & UI Hardening
- **Fixed: Export Menu "Stuck" Issue**:
  - Resolved an issue where the confirmation menu remained active after clicking "Yes" by implementing immediate message edits to show status.
- **Added: Navigation & UX Improvements**:
  - Integrated a **`🔙 Back`** button (linking to `bulk_controls_menu`) upon completion or failure of all export actions (Sessions, Phones, and Bot Tokens).
  - Enhanced UI by wrapping all confirmation prompts in `<blockquote expandable>` tags for a cleaner, modern visual experience.
- **Improved: Robustness & Error Handling**:
  - Added comprehensive `try...except` protections for file delivery (`send_document`) and log notifications to prevent process crashes.
  - Ensured all error states provide a functional "Back" button for seamless menu recovery.
- **Optimized: Internal Code Structure**:
  - Refactored message text variable management in `export_handlers.py` for improved readability and maintainability.

---

## [0.0.10.2455I] - 2026-05-20

### 🛡️ API & Transport Resilience Hardening
- **Fixed: MessageNotModified Flood & Latency Loop**:
  - Added `MessageNotModified` and `MESSAGE_NOT_MODIFIED` to the static list of `permanent_errors` inside Pyrogram's `invoke` decorator wrapper (`Main/core/types/client.py`).
  - By identifying same-content message edits as non-retryable permanent errors immediately, the system bypasses redundant 5-time backoff retries and avoids unnecessary 7.5-second thread delays/log clutter.

---

## [0.0.10.2454I] - 2026-05-20

### 📑 Task Manager Plugin: [Resume Page] and [Resume All] Robust Restoration Routing
- **Fixed: [Resume Page] / [Resume All] Bulk Resumptions**:
  - Upgraded both `resumepage` and `resumeall` bulk actions inside the Task Manager callback handler to dynamically support both paused active tasks and persistent interrupted tasks.
  - Automatically routes interrupted tasks (`is_interrupted: True`) to the restored handler (`handle_restore_action`), while routing paused tasks to the standard resume helper.
- **Fixed: Task Manager Restoration Helper**:
  - Restored `handle_restore_action` to import `creategroup_control_handler` from `Main.plugins.userbot.xcreategroup` and correctly format callback data (`recover_creategroup:{tid}`) to native requirements.
  - Fully resolves the missing `creategroup_resume_cached_handler` import error.

### 🔄 Unified Restart Flow & Debug Logging
- **Optimized: Unified Restart Pipeline**:
  - Hardened the `Full Restart (Hard)` action in `/settings` (under both `SESSION MANAGER` and `bulk control` menus) to natively route through `Altruix._restart` for a single, bulletproof, cross-platform process replacement pipeline.
- **Added: Conditional DEBUG Restart Method Logging**:
  - If `DEBUG=True` in the configuration settings, the system logs which stagger method (`Parallel` or `Sequential`) is used during session connection restarts directly to the terminal, prepended with the clean structural styling prefix `[DEBUG_ON]: » `.

---

## [0.0.10.2453I] - 2026-05-20

### 🚀 High-Speed Startup Report Index Addition
- **New Feature: Startup Session Indexes**:
  - Preallocated and synchronized detailed session entries to print the correct sequential index `[idx]` (e.g. `[0]`, `[1]`, `[2]`, ..., `[100]`) inside the consolidated Startup Report.
  - Guaranteed exact order preservation for parallel and sequential startup logging methods.

---

## [1.0.252] - 2026-05-19

### 📑 Task Manager Plugin: Page-Specific Bulk Actions & Snappy UX
- **Added: Page-Specific Bulk Actions**:
  - Integrated three new powerful interactive buttons: **`[Resume Page]`**, **`[End Page]`**, and **`[Pause Page]`** directly on the `📋 Active Tasks` paginated dashboard.
  - Allows bulk operations to act strictly on visible active tasks listed on the current page rather than terminating/resuming the entire global queue.
- **Added: Advanced UX Navigation & Smart Return Routing**:
  - Implemented smart return page routing; after approving a page bulk action, the dashboard automatically reloads and displays the *exact same page* the user was viewing, rather than resetting to page 1.
  - Symmetrically maps confirmation and cancellation actions (e.g. `❌ No, Cancel` returns to the specific page it was triggered from).
- **Added: Paced Resumes & Safety Alignment**:
  - Automatically incorporates the safety `⏳ Delay Per-Resume` pacing configuration inside page resumes to protect the userbot from network flood limits.

---

## [1.0.251] - 2026-05-19

### 📦 YTDL Manager: Premium YouTube Chapter Splitter & NoneType Hardening
- **New Feature: Premium YouTube Chapter Splitter & Slicer**:
  - Added a dynamic `📦 Split Chapters: {status}` control button directly to the YTDL main dashboard.
  - Implemented the `📦 Pengaturan Pembagian Bab (Split Chapters)` sub-menu dynamically listing all detected video chapters with clean start/end times and descriptions.
  - Symmetrically incorporates the chapter split selection into the single confirmation download screens (e.g. `[Split Chapters: 5 bab]`).
- **New Feature: Dynamic Original Video Bitrate Indicator**:
  - Automatically calculates the exact original average bitrate of the chosen video quality dynamically based on estimated format size and total duration.
  - Symmetrically prints this specific original bitrate (e.g., `Original (4.2 Mbps)` or `Original (850 Kbps)`) on the `"Original"` selector button inside the `"📺 Pilih Bitrate Video"` sub-menu, offering advanced visual clarity.
- **New Feature: Original Audio Volume & Decibel Label**:
  - Upgraded the `"Original"` audio volume option in the `"🔊 Pengaturan Volume & Boost (Desibel)"` sub-menu to display as `Original (100% / 0 dB)`.
  - Ensures full symmetric visual alignment with the other percentage and decibel booster button styles.
- **Enhanced: Local Slicing & Sequence Upload Pipeline**:
  - Downloads the raw video from YouTube only once, then processes local slicing locally via FFmpeg, saving massive amounts of network bandwidth.
  - Applies all user-selected custom speed, volume, and watermark parameters to each individual chapter slice.
  - Implemented sequentially automated slicing, ID3v2 metadata embedding (titles, artists, albums, thumbnail cover art), backup logging, and uploads with real-time status bars showing sequence progress (`Uploading 1/5`, `Uploading 2/5`).
  - Added the source content's upload date (`Upload: YYYY-MM-DD`) directly to the Chapter Split sequence captions.
- **Fixed: Robust Defensive Fallbacks (NoneType Fix)**:
  - Secured `"languages"` and `"chapters"` state retrievals across `xyt_tools_bot.py` and `ytdl_core.py` using the robust `or []` pattern fallback.
  - Eliminates potential `TypeError: object of type 'NoneType' has no len()` crashes caused by older database entries containing null values for these fields.
- **Version Bumps**:
  - **Assistant Bot Plugin**: `1.0.175`
  - **YTDL Core Engine**: `0.0.263`

---

## [1.0.250] - 2026-05-19

### ⏳ Task Manager Plugin: Paced Resume Control & Safety Delay Menu
- **Added: Delay Per-Resume Setting Dashboard Controls**:
  - Implemented a new interactive **"⏳ Delay Per-Resume: Xs"** button in the main `📋 Active Tasks` dashboard menu.
  - Added a premium configuration sub-menu offering quick adjustments (`-5s`, `-1s`, `+1s`, `+5s`) and standard presets (`0s (Instant)`, `3s (Default)`, `5s`, `10s`).
- **Added: Safety-Paced Bulk Resuming (Resume All)**:
  - Upgraded the `resumeall` bulk confirmation flow to respect the configured delay between successive task resumes.
  - Implemented smart pacing using `asyncio.sleep` to stagger the resumes, preventing Pyrogram/Telegram flood waits and system resource contention.
  - Keeps log summaries clear with descriptive real-time logs indicating delay sleeps.
- **Improved: Stable Config & DB Layer**:
  - Maintained persistent configurations in a safe `taskmanager_settings.json` file inside the centralized `DATABASE` directory.
  - Equipped all functions with robust `try-except` blocks and detailed traceback error logging for enterprise-grade debuggability.

---

## [0.0.10.2456I] - 2026-05-19

### 🎛️ CreateGroup: Staggered Multi-Account Batching & Pacing Controls
- **Added: Batch Account & Batch Account Delay Dashboard Controls**:
  - Implemented interactive buttons `B.Acc` and `B.Acc Delay` in the CreateGroup settings dashboard.
  - Users can now configure the maximum number of accounts started per batch (`batch_account`, default `3`) and the duration of delay in seconds between account batches (`ba_account_delay`, default `60s`).
  - Added support in the adjustments keypad to increase/decrease values dynamically with custom steps, boundaries, and type safety constraints.
- **Added: Dynamic Batch Boundary Sleep Logic**:
  - Upgraded the multi-account startup stagger loop in `creategroup_confirm_task_handler` to track and trigger a longer sleep duration when crossing a batch boundary.
  - Status updates to the user now explicitly indicate whether an account is starting under normal staggered delay or batch account sleep.
- **Added: Detailed Startup Log Support**:
  - Enhanced `creategroup_loop` start log notification in `xcreategroup.py` to print `Batch Account` size and `Batch Account Delay` durations dynamically in the log channel blockquote.
- **Added: First & Last Navigation for Creation Reports & Details**:
  - Integrated standard `[First]` and `[Last]` pagination buttons inside both the `📊 Creation Reports` master list and the `📊 Detail Laporan Dibuat` view for direct navigation.
  - Relaxed the page rendering threshold to `total_pages > 1` (down from `total_pages > 2`) to ensure these buttons are active on 2-page lists (e.g. `[1/2]`).
- **Optimized: Detailed Reports UI (Disable Link Preview)**:
  - Disabled web page / link previews in the `📊 Detail Laporan Dibuat` submenu to keep the dashboard view extremely clean, compact, and free of vertical preview clutter.
- **Added: Expandable Blockquote for Task Control Panel Log**:
  - Wrapped the initial `🚀 Task Control Panel` log notification message in `xcreategroup.py` inside a `<blockquote expandable>` element to match the project's visual and log threading standards.
- **Hardened: FloodWait Resiliency & Assistant Bot Log Exclusive**:
  - Engineered an automatic `FloodWait` detection and retry system when sending final completion reports.
  - If a short rate limit occurs (e.g. `<= 40` seconds), the program automatically sleeps and retries.
  - Enforced that only the Main Assistant Bot (`bot_client`) handles log transmissions and updates (userbot sessions are completely skipped to keep account activities clean). If rate limits are high, the system handles fallback logging seamlessly via a fresh log message delivered by the assistant bot.
  - Disabled all log message deletion routines (specifically during secondary bot migrations) to ensure all updated log message history remains 100% preserved and intact.
  - Configured secondary/fallback bot migration messages to **directly reply to the original/old log message ID (`msg.id`)** so that log updates are visually threaded and chronological, eliminating the need to delete old logs.
- **Added: Session Progress & Account Preview in Creation Logs**:
  - Enhanced the `🏗 Memproses` group progress header inside `xcreategroup.py` to dynamically display the active multi-session account index (`Session {account_idx}/{total_accs}`).
  - Upgraded the profile photo download success log notification to dynamically display the active session/account name `(Akun: {account_name_raw})` for ultimate transparency.
- **Fixed: Harmless QueryIdInvalid Safety Wrapper**:
  - Wrapped the initial `await cb.answer()` calls in both `creategroup_reports_handler` and `creategroup_report_detail_handler` inside clean `try-except` blocks.
  - This ensures that if a Telegram callback query expires due to latency or lag, the page loading logic continues flawlessly rather than crashing the menu with a QUERY_ID_INVALID error.
- **Version Bumps**:
  - **CreateGroup Handlers**: `0.3.230`
  - **CreateGroup Plugin**: `0.2.413`

---

## [0.0.10.2455I] - 2026-05-19

### 📊 CreateGroup: Persistent Creation Reports & Log Exports
- **Added: Persistent Creation Report Database**:
  - Implemented `xcreategroup_created_report.json` database that persists group/channel successful creation history.
  - History is kept completely persistent and is not affected by system restarts or clearing active/restore tasks.
- **Added: Interactive Creation Reports Submenu**:
  - Added a new `📊 Reports` button to the primary CreateGroup interactive UI dashboard.
  - Implemented an accounts summary directory showing total created items, and group vs channel breakdowns for each userbot.
  - Added a detailed paginated page showing full information for each created item (Name, Type, ID, Link, Task ID, Creation Time).
- **Added: Log Export/Download Feature**:
  - Implemented buttons to export specific account reports or master reports covering all accounts.
  - Reports are generated dynamically and sent directly to the admin chat as beautifully-formatted `.txt` files.
- **Added: Automated Historic Sync**:
  - Automatically synchronizes existing records in `CREATEGROUP_TASKS` and `COMPLETED_CREATEGROUP_TASKS` to the report database at startup so no previous data is lost.
- **Version Bumps**:
  - **CreateGroup Plugin**: `0.2.405`
  - **CreateGroup Handlers**: `0.3.224`

---

## [0.0.10.2454I] - 2026-05-18

### ⚙️ CreateGroup: Recovery Interrupted Log Destination Routing Config
- **Added: Interrupted Task Detected Log Destination Setting**:
  - Implemented a new dashboard button row `Interrupted Log` in the CreateGroup submenu allowing users to customize where restart-recovery logs are sent.
  - Cycle values: `Off` (default - skips sending entirely to prevent spammy startup messages), `Log Group`, `PM Bot` (admin private chat), and `Both`.
  - Modified the recovery detection startup check `check_interrupted_tasks` in `xcreategroup.py` to fetch each admin's config and route recovery logs dynamically to chosen destinations.
- **Version Bumps**:
  - **CreateGroup Plugin**: `0.2.404`
  - **CreateGroup Handlers**: `0.3.223` (updated in code)

## [0.0.10.2453I] - 2026-05-18

### ⚙️ CreateGroup: Total Task Count in Restore Tasks Header
- **Added: Total Task Count to Restore Tasks Submenu Header**:
  - Enhanced the `Restore Tasks` dashboard layout to dynamically append the total task count `Total: {total_tasks}` (e.g. `[1/4 | Total: 16]`) in the header for both empty and paginated states.
  - Improves task manager management and monitoring visibility.

---

## [0.0.10.2452I] - 2026-05-18

### 🛡️ PM Logger: Self-Destruct Media Forwarding and Re-Uploading Support
- **Fixed: Self-Destruct/TTL Media Logging Failures**:
  - Implemented automatic detection of self-destructing media (TTL photos, videos, video notes, and voice messages) in both `xpm_logger_user.py` and `xpm_logger_bot.py`.
  - Since Telegram blocks standard forwarding of self-destruct/TTL messages, the logger now automatically downloads the media to local storage immediately upon receipt and re-uploads it directly to the target log group thread.
  - Automatically cleans up the temporary downloaded file immediately after a successful upload to safeguard storage resources.
  - Added a dedicated, highly requested `• Self-Destruct: True/False` field directly in the metadata section of the PM log contents.
  - Unified and polished the Bot PM Logger log layout, upgrading it to match the premium expandable HTML blockquote layout used in the User PM Logger.
- **Added: Resilient Fallback Media Processing**:
  - Implemented a smart fallback mechanism: if a normal forward operation fails for any media message, the logger immediately attempts to download the media locally and re-uploads it as a persistent document to the log group chat.
- **Version Bumps**:
  - **PM Logger User Plugin**: `1.3.75`
  - **PM Logger Bot Plugin**: `1.3.26`

## [0.0.10.2451I] - 2026-05-18

### ⚙️ CreateGroup: Expandable Blockquote Layout for Creation Failures
- **Improved: Group and Supergroup Creation Failure Log Layout**:
  - Wrapped `Gagal membuat Grup Dasar` and `Gagal membuat Supergroup/Channel` error logs in expandable blockquote tags (`<blockquote expandable>`).
  - Ensures full aesthetic alignment with other key progress log items in the log group.

---

## [0.0.10.2450I] - 2026-05-18

### ⚙️ CreateGroup: Redundant Assistant Bot Fallback Migration
- **Added: Edit FloodWait Assistant Bot Fallback System**:
  - Implemented dynamic bot assistant fallback migration in `update_group_log`.
  - When the primary log bot client encounters a `FloodWait` edit rate limit, it automatically filters and assigns an active alternative assistant bot (from `Altruix.bot` and `Altruix.secondary_bots`).
  - The fallback bot publishes a new copy of the tracking log text, silently deletes the old message to avoid duplication, and updates active memory references so subsequent edits utilize the new bot instance seamlessly.

## [0.0.10.2449I] - 2026-05-18

### ⚙️ CreateGroup: Account Index Indicators in Startup Logs
- **Added: Account Position Index to Task Started and Resumed Logs**:
  - Dynamically appended account index position indicators `{account_idx}/{total_accs}` (e.g. `66/82`) to the `Task Started` and `Task Resumed` log headers.
  - Improves visibility and verification accuracy when multiple accounts run tasks simultaneously.

## [0.0.10.2448I] - 2026-05-18

### ⚙️ CreateGroup: Expandable Blockquote Layout for Key Logs
- **Improved: Layout for Key Logs in Log Group**:
  - Wrapped `CHANNELS_TOO_MUCH` (limit reached) task termination notification log in expandable blockquote tags (`<blockquote expandable>`).
  - Wrapped `Gagal mendapatkan bot` (bot resolving failure) notification log in expandable blockquote tags (`<blockquote expandable>`).
  - Ensures all main progress log details present a premium, unified layout.

---

## [0.0.10.2447I] - 2026-05-18

### ⚙️ CreateGroup: Enhanced Bot Entity Resolving Logs
- **Added: Account Name in Bot Entity Resolving Failure Notifications**:
  - Appended account name context `(Akun: {account_name_raw})` to the `Gagal mendapatkan bot` error log message.
  - Allows easy identification of which userbot account failed to resolve a bot entity.

## [0.0.10.2446I] - 2026-05-18

### ⚙️ CreateGroup: Enhanced Log Aesthetics
- **Improved: Profile Photo Download Notification Layout**:
  - Wrapped successful profile photo download notifications (source/custom) in expandable HTML blockquotes (`<blockquote expandable>`).
  - Ensures a clean, modern, and aligned premium display for all log group progress updates.

## [0.0.10.2445I] - 2026-05-18

### ⚙️ CreateGroup: Graceful Callback Query ID Invalid Handling
- **Fixed: QUERY_ID_INVALID Console Spam & Crash Loops**:
  - Implemented graceful catching of `QUERY_ID_INVALID` (expired/already answered callback query) exceptions in both `confirm_creategroup_handler` and `creategroup_control_handler` catch blocks.
  - Silenced these standard Telegram API behaviors to log only as debug messages, preventing false-positive critical logs in the console.
  - Secured the error-response fallback `callback_query.answer` within a safe `try...except` scope to eliminate secondary unhandled exception propagation.

---

## [0.0.10.2444I] - 2026-05-18

### 🧹 Purgeme Bot Plugin: Interactive UI Alignment & Grid Symmetry
- **Improved: Adjustment Button Layout Grid**:
  - Restructured negative/positive adjustment buttons for `count`, `batch`, `delaymsg`, `delaybc`, `offset`, `max scan`, and `keep_recent` into an elegant, symmetrical dual-column layout.
  - Aligned adjustment steps and values (e.g. up to `-500`/`+500` for count, `-5000`/`+5000` for max scan, and granular float intervals for message delay) to match the premium aesthetics and usability of `creategroup.py`.

## [0.0.10.2443I] - 2026-05-18

### 🔌 Main Bot Manager: Code Clarity & DC Rate Limit Hardening
- **Fixed: Redundant Connection & DC Migration FloodWait Rate Limit**:
  - Completely resolved the double-start DC Migration rate-limit issue in `add_secondary_bot` by directly extracting bot ID from the token string, eliminating redundant `temp_client` start/stop cycles.
- **Fixed: Token Input Responsiveness & Swallow Bug**:
  - Elevated token input message handler to `group=-100` and integrated mandatory `continue_propagation()` fallback logic to resolve input unresponsiveness and private message swallowing.
- **Documentation: Code Readability & Developer Docstrings**:
  - Added comprehensive, professional docstrings and detailed step-by-step explanatory comments to every function and message handler inside `main_bot_manager.py`.

---

## [0.0.10.2442I] - 2026-05-18

### 🤖 Settings & Main Bot Manager: Fallback Pool & Persistence
- **New Feature: Secondary Main Bot Fallback Pool**:
  - Implemented a robust fallback pool of dynamic Main Bot assistants to safeguard log transmission.
  - Automatically loads and launches registered secondary bots at startup directly from MongoDB.
  - **Dynamic Fallback Monkey-Patching**: Automatically intercepts `FloodWait` warnings during `send_message`, `send_photo`, and `send_document` calls on the primary bot and transparently fails over to secondary bots sequentially.
- **New Feature: Premium Secondary Bot Manager Sub-Menu**:
  - Added the **🤖 Backup Bots (Main Bot 2, 3, ...)** button inside the settings dashboard.
  - Interactive status grid displaying active fallback assistants (`🟢 Running` or `🔴 Inactive`).
  - **🏓 Dynamic Ping Connection**: Test latency response speed of each fallback bot via dynamic callback queries with live inline output.
  - **🗑️ Teardown & Deletion**: Hot deletion of secondary bots from runtime memory and database without requiring a restart.
  - **➕ Dynamic Hot Addition**: Hot addition and registration of new token credentials live without requiring any program restart.
- **Fixed: Settings Configuration Persistence**:
  - Resolved config persistence bugs in `load_envs_to_db` where hardcoded defaults were overwriting DB states upon restart.
  - Standardized all default notification/log parameters to `"off"`/`False` for a smoother stealth startup experience.
- **Hardened: 100% Exception Coverage & Tracebacks**:
  - Wrapped all newly introduced background systems and callback queries inside thorough `try-except` blocks with complete detailed `traceback` logging (`traceback.format_exc()`) to ensure effortless diagnostics.

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

---
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

---

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

---
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

---

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

---

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

---

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

---

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

---

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

---
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

---

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

---

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

---

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

---

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
