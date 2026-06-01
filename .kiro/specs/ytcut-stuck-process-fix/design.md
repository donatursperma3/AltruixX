# YTcut Stuck Process Fix - Bugfix Design

## Overview

The YTcut process becomes stuck after displaying the initial "⏳ Memulai proses YTcut..." message, leaving users without feedback about failures. This fix adds comprehensive logging at every critical stage and improved error handling with try-except blocks to identify failure points and provide clear user feedback. The approach is non-invasive: it preserves all existing logic flow, adds logging statements at strategic points, wraps risky operations in try-except blocks, and ensures users receive informative error messages when failures occur.

## Glossary

- **Bug_Condition (C)**: The condition that triggers the bug - when YTcut process gets stuck after confirmation without progressing or providing error feedback
- **Property (P)**: The desired behavior - comprehensive logging at each stage and clear error messages to users when failures occur
- **Preservation**: All existing YTcut functionality (download, concat, upload, lock mechanism, queue management, dashboard updates) must remain unchanged
- **enqueue_ytcut_run**: The function in `Main/internals/ytcut_helpers.py` (line 818) that manages task queuing and lock acquisition before processing
- **process_ytcut_task**: The function in `Main/internals/ytcut_helpers.py` (line 852) that orchestrates the three-stage YTcut workflow (download, concat, upload)
- **ytcut_confirm_yes_cb**: The callback handler in `Main/plugins/bot/xytcut_bot.py` (line 1000) that initiates the YTcut process when user confirms
- **task_id**: Unique identifier for each YTcut task, used for tracking and correlation across logs
- **ytcut_stage**: State variable tracking current processing stage (Initializing, Step 1/3, Step 2/3, Step 3/3)

## Bug Details

### Bug Condition

The bug manifests when the YTcut process encounters an error at any stage (lock acquisition, download, concat, upload) but fails to log sufficient diagnostic information or notify the user. The process appears "stuck" because exceptions may be silently caught or logged without context, and users receive no feedback about what failed or where.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type YTcutProcessExecution
  OUTPUT: boolean
  
  RETURN input.stage IN ['lock_acquisition', 'download', 'concat', 'upload']
         AND (exceptionOccurred(input) OR processHangs(input))
         AND (NOT sufficientLoggingPresent(input) OR NOT userNotified(input))
END FUNCTION
```

### Examples

- **Lock Acquisition Failure**: User confirms YTcut, `enqueue_ytcut_run` is called, but lock acquisition hangs or fails without logging task_id, user_id, chat_id, or queue state
- **Download Stage Failure**: yt-dlp process fails (network error, invalid URL, format unavailable) but only generic error is logged without task_id context or stage information
- **Concat Stage Failure**: FFmpeg concat fails (codec incompatibility, disk space) but error is caught in generic exception handler without detailed logging of which files were being processed
- **Upload Stage Failure**: Telegram upload fails (file too large, peer invalid) but user receives no clear message about what went wrong or how to recover

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Lock mechanism using `Altruix.YTCUT_LOCK` must continue to prevent concurrent processing
- Queue management using `Altruix.YTCUT_QUEUE` must continue to handle task ordering
- Task state management using `state["processing"]` flag must continue to track processing status
- Dashboard updates via `edit_ytcut_dashboard_status` must continue to show current stage
- xtaskmanager integration must continue to register/unregister tasks
- Error notification to group log via `notify_ytcut_error_to_group_log` must continue to work
- Temporary file cleanup in finally blocks must continue to execute
- All existing success paths (download → concat → upload) must continue to work identically

**Scope:**
All inputs that do NOT involve error conditions should be completely unaffected by this fix. This includes:
- Successful YTcut executions from start to finish
- User interactions with YTcut dashboard (add segment, edit segment, change mode)
- Cancellation and revision workflows
- Queue position notifications

## Hypothesized Root Cause

Based on the bug description and code analysis, the most likely issues are:

1. **Insufficient Logging Context**: Existing log statements lack critical context (task_id, user_id, chat_id, stage) making it impossible to trace which task failed and where
   - `enqueue_ytcut_run` has no entry logging with task_id and queue state
   - Lock acquisition waiting has no logging to show task is waiting
   - Stage transitions in `process_ytcut_task` have minimal logging

2. **Generic Exception Handling**: The broad `except Exception as e:` blocks catch all errors but don't log enough detail
   - Missing full traceback in some error paths
   - Missing stage context when exception occurs
   - Missing task_id correlation in error logs

3. **Silent Failures in Subprocess Calls**: yt-dlp and FFmpeg subprocess failures may not be logged with sufficient context
   - `run_ytcut_download` logs stdout/stderr but may not log initial command or task_id
   - `run_ytcut_ffmpeg_concat` has heartbeat logging but may not log errors with task context

4. **User Notification Gaps**: When errors occur, user may not receive clear feedback
   - Some error paths may fail to send user notification
   - Error messages may be too technical or lack actionable information

## Correctness Properties

Property 1: Bug Condition - Comprehensive Logging and Error Feedback

_For any_ YTcut process execution where an error occurs at any stage (lock acquisition, download, concat, upload), the fixed system SHALL log the error with full context (task_id, user_id, chat_id, stage, traceback) and send a clear error message to the user describing what failed.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8**

Property 2: Preservation - Existing Functionality Unchanged

_For any_ YTcut process execution that does NOT encounter errors, the fixed system SHALL produce exactly the same behavior as the original system, preserving all existing functionality for successful downloads, queue management, lock synchronization, and dashboard updates.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9**

## Fix Implementation

### Changes Required

All changes are additive (logging and error handling) without modifying existing logic flow.

**File**: `Main/plugins/bot/xytcut_bot.py`

**Function**: `ytcut_confirm_yes_cb` (line ~1000)

**Specific Changes**:
1. **Add Entry Logging**: Log callback invocation with task_id, user_id, chat_id before any processing
   ```python
   # After: state = await get_ytcut_task_state(task_id)
   # Add:
   Altruix.log(
       f"YTcut callback confirm: task_id={task_id} user_id={cb.from_user.id if cb.from_user else 'unknown'} "
       f"chat_id={state.get('chat_id')} url={state.get('url')}"
   )
   ```

2. **Wrap enqueue_ytcut_run Call**: Add try-except around task creation to catch immediate failures
   ```python
   # Wrap existing: task = asyncio.create_task(enqueue_ytcut_run(task_id, c))
   try:
       task = asyncio.create_task(enqueue_ytcut_run(task_id, c))
       Altruix.log(f"YTcut task enqueued: task_id={task_id} user_id={cb.from_user.id if cb.from_user else 'unknown'}")
   except Exception as e:
       Altruix.log(f"YTcut enqueue failed: task_id={task_id} user_id={cb.from_user.id if cb.from_user else 'unknown'} error={e}\n{traceback.format_exc()}")
       await cb.edit_message_caption(
           caption=f"❌ <b>Gagal memulai proses YTcut:</b> <code>{html.escape(str(e))}</code>",
           parse_mode=enums.ParseMode.HTML
       )
       return
   ```

**File**: `Main/internals/ytcut_helpers.py`

**Function**: `enqueue_ytcut_run` (line 818)

**Specific Changes**:
1. **Add Entry Logging**: Log function entry with task_id, lock state, queue state
   ```python
   # At function start, after: state = Altruix.YTCUT_STATE.get(task_id)
   # Add:
   Altruix.log(
       f"YTcut enqueue_ytcut_run entry: task_id={task_id} user_id={state.get('user_id')} "
       f"chat_id={state.get('chat_id')} lock_locked={Altruix.YTCUT_LOCK.locked()} "
       f"queue_length={len(Altruix.YTCUT_QUEUE)}"
   )
   ```

2. **Add Lock Wait Logging**: Log when task is waiting for lock
   ```python
   # Before: if task_id in Altruix.YTCUT_QUEUE:
   # Add:
   if task_id in Altruix.YTCUT_QUEUE:
       Altruix.log(f"YTcut waiting for lock: task_id={task_id} queue_position={Altruix.YTCUT_QUEUE.index(task_id) + 1}")
       await Altruix.YTCUT_LOCK.acquire()
   ```

3. **Add Lock Acquired Logging**: Log when lock is successfully acquired
   ```python
   # After lock acquisition (both paths)
   # Add:
   Altruix.log(f"YTcut lock acquired: task_id={task_id} user_id={state.get('user_id')} chat_id={state.get('chat_id')}")
   ```

4. **Wrap process_ytcut_task Call**: Add try-except with detailed logging
   ```python
   # Replace existing try block:
   try:
       await process_ytcut_task(state, client)
   except Exception as e:
       Altruix.log(
           f"YTcut enqueue_ytcut_run exception: task_id={task_id} user_id={state.get('user_id')} "
           f"chat_id={state.get('chat_id')} error={e}\n{traceback.format_exc()}"
       )
       # Re-raise to let process_ytcut_task's error handling take over
       raise
   finally:
       # existing finally block
   ```

5. **Add Exit Logging**: Log function exit with success/failure status
   ```python
   # In finally block, before state["processing"] = False
   # Add:
   Altruix.log(
       f"YTcut enqueue_ytcut_run exit: task_id={task_id} processing={state.get('processing')} "
       f"lock_locked={Altruix.YTCUT_LOCK.locked()}"
   )
   ```

**Function**: `process_ytcut_task` (line 852)

**Specific Changes**:
1. **Add Entry Logging**: Log function entry with all task details
   ```python
   # At function start, after: task_id = state.get("task_id")
   # Add:
   Altruix.log(
       f"YTcut process_ytcut_task entry: task_id={task_id} user_id={state.get('user_id')} "
       f"chat_id={state.get('chat_id')} url={state.get('url')} mode={state.get('mode')} "
       f"extract={state.get('extract')} segments_count={len(state.get('segments', []))}"
   )
   ```

2. **Add Stage Transition Logging**: Log each stage transition with timestamp
   ```python
   # Before each stage assignment (current_stage = "Step X/3: ...")
   # Add:
   Altruix.log(
       f"YTcut stage transition: task_id={task_id} user_id={state.get('user_id')} "
       f"chat_id={state.get('chat_id')} stage='{current_stage}'"
   )
   ```

3. **Wrap download_ytcut_thumbnail Call**: Add try-except for thumbnail download
   ```python
   # Wrap: await download_ytcut_thumbnail(state.get("thumbnail", ""), thumb_path)
   try:
       await download_ytcut_thumbnail(state.get("thumbnail", ""), thumb_path)
       Altruix.log(f"YTcut thumbnail downloaded: task_id={task_id} thumb_path={thumb_path}")
   except Exception as thumb_err:
       Altruix.log(
           f"YTcut thumbnail download failed (non-critical): task_id={task_id} "
           f"error={thumb_err}\n{traceback.format_exc()}"
       )
       # Continue without thumbnail - this is non-critical
   ```

4. **Wrap run_ytcut_download Call**: Add try-except with stage context
   ```python
   # Wrap: downloaded_parts = await run_ytcut_download(state, temp_dir, client)
   try:
       downloaded_parts = await run_ytcut_download(state, temp_dir, client)
       Altruix.log(
           f"YTcut download completed: task_id={task_id} parts_count={len(downloaded_parts)} "
           f"parts={[os.path.basename(p) for p in downloaded_parts]}"
       )
   except Exception as dl_err:
       Altruix.log(
           f"YTcut download failed: task_id={task_id} user_id={state.get('user_id')} "
           f"chat_id={state.get('chat_id')} stage='{current_stage}' error={dl_err}\n{traceback.format_exc()}"
       )
       raise  # Re-raise to be caught by outer exception handler
   ```

5. **Wrap run_ytcut_ffmpeg_concat Call**: Add try-except with stage context
   ```python
   # Wrap: await run_ytcut_ffmpeg_concat(...)
   try:
       await run_ytcut_ffmpeg_concat(downloaded_parts, output_file, state["extract"], client, state, thumb_path if os.path.exists(thumb_path) else None)
       Altruix.log(
           f"YTcut concat completed: task_id={task_id} output_file={output_file} "
           f"file_size={os.path.getsize(output_file) if os.path.exists(output_file) else 0}"
       )
   except Exception as concat_err:
       Altruix.log(
           f"YTcut concat failed: task_id={task_id} user_id={state.get('user_id')} "
           f"chat_id={state.get('chat_id')} stage='{current_stage}' error={concat_err}\n{traceback.format_exc()}"
       )
       raise  # Re-raise to be caught by outer exception handler
   ```

6. **Enhance Upload Logging**: Add more detailed logging around send_video/send_audio
   ```python
   # Before: if state["extract"] == "video":
   # Add:
   Altruix.log(
       f"YTcut upload starting: task_id={task_id} chat_id={state.get('chat_id')} "
       f"user_id={state.get('user_id')} extract={state['extract']} "
       f"output_file={output_file} file_size={os.path.getsize(output_file)}"
   )
   
   # After successful send (after both send_video and send_audio)
   # Add:
   Altruix.log(
       f"YTcut upload completed: task_id={task_id} chat_id={state.get('chat_id')} "
       f"user_id={state.get('user_id')}"
   )
   ```

7. **Enhance Exception Handler**: Improve error logging and user notification
   ```python
   # In existing: except Exception as e:
   # Replace: Altruix.log(f"YTcut process failed: {e}\n{tb_text}")
   # With:
   Altruix.log(
       f"YTcut process_ytcut_task exception: task_id={task_id} user_id={state.get('user_id')} "
       f"chat_id={state.get('chat_id')} stage='{current_stage}' error={e}\n{tb_text}"
   )
   
   # Enhance user error message to include stage
   # Replace: text=f"❌ <b>Gagal memproses YTcut:</b> <code>{html.escape(err_text)}</code>"
   # With:
   text=(
       f"❌ <b>Gagal memproses YTcut</b>\n"
       f"<b>Stage:</b> {html.escape(current_stage)}\n"
       f"<b>Error:</b> <code>{html.escape(err_text[:200])}</code>"
   )
   ```

8. **Add Exit Logging**: Log function exit in finally block
   ```python
   # In finally block, before cleanup_ytcut_temp
   # Add:
   Altruix.log(
       f"YTcut process_ytcut_task exit: task_id={task_id} user_id={state.get('user_id')} "
       f"chat_id={state.get('chat_id')} final_stage='{current_stage}'"
   )
   ```

**Function**: `run_ytcut_download` (line 431)

**Specific Changes**:
1. **Enhance Entry Logging**: Already exists, ensure it includes all relevant context
   - Current logging at line ~475 is good, ensure task_id is included

2. **Add Subprocess Start Logging**: Log when subprocess is created
   ```python
   # After: process = await asyncio.create_subprocess_exec(...)
   # Add:
   Altruix.log(
       f"YTcut download subprocess started: task_id={state.get('task_id')} pid={process.pid}"
   )
   ```

3. **Add Subprocess Exit Logging**: Log when subprocess completes
   ```python
   # After: await process.wait()
   # Add:
   Altruix.log(
       f"YTcut download subprocess completed: task_id={state.get('task_id')} "
       f"returncode={ret} stdout_lines={len(full_stdout)} stderr_lines={len(stderr_lines)}"
   )
   ```

4. **Enhance Error Logging**: Add task_id to error raise
   ```python
   # Replace: raise RuntimeError(f"YT-DLP Error:\n{err or out or 'Unknown error'}")
   # With:
   raise RuntimeError(
       f"YT-DLP Error (task_id={state.get('task_id')}): {err or out or 'Unknown error'}"
   )
   ```

**Function**: `run_ytcut_ffmpeg_concat` (line 580)

**Specific Changes**:
1. **Add Entry Logging**: Log function entry with file details
   ```python
   # At function start
   # Add:
   Altruix.log(
       f"YTcut concat entry: task_id={state.get('task_id')} parts_count={len(parts)} "
       f"output_path={output_path} extract={extract}"
   )
   ```

2. **Add Concat File Creation Logging**: Log when concat list file is created
   ```python
   # After: with open(concat_file, "w", encoding="utf-8") as handle: ...
   # Add:
   Altruix.log(
       f"YTcut concat list created: task_id={state.get('task_id')} concat_file={concat_file} "
       f"parts_count={len(parts)}"
   )
   ```

3. **Add FFmpeg Command Logging**: Log FFmpeg command before execution
   ```python
   # Before: ret, out, err = await run_subprocess(cmd)
   # Add:
   Altruix.log(
       f"YTcut concat ffmpeg starting: task_id={state.get('task_id')} cmd={' '.join(cmd)}"
   )
   ```

4. **Add FFmpeg Retry Logging**: Log when fallback encoding is attempted
   ```python
   # In: if ret != 0: (first retry)
   # Add:
   Altruix.log(
       f"YTcut concat copy failed, retrying with re-encode: task_id={state.get('task_id')} "
       f"extract={extract}"
   )
   ```

5. **Enhance Error Logging**: Add task_id to error raise
   ```python
   # Replace: raise RuntimeError(f"FFmpeg concat error:\n{err or out or 'Unknown error'}")
   # With:
   raise RuntimeError(
       f"FFmpeg concat error (task_id={state.get('task_id')}): {err or out or 'Unknown error'}"
   )
   ```

6. **Add Thumbnail Embed Logging**: Log thumbnail embedding attempts
   ```python
   # Before: ret, out, err = await run_subprocess(embed_cmd)
   # Add:
   Altruix.log(
       f"YTcut thumbnail embed starting: task_id={state.get('task_id')} thumb_path={thumb_path}"
   )
   
   # After: if ret == 0:
   # Add:
   Altruix.log(
       f"YTcut thumbnail embed success: task_id={state.get('task_id')}"
   )
   ```

### Logging Format Standard

All new logging statements will follow this consistent format:

```python
Altruix.log(
    f"YTcut {function_name} {event}: task_id={task_id} user_id={user_id} "
    f"chat_id={chat_id} [additional_context]"
)
```

**Components:**
- **Prefix**: Always start with "YTcut" for easy filtering
- **Function Name**: Abbreviated function name (e.g., "enqueue", "process", "download", "concat")
- **Event**: Action being logged (e.g., "entry", "exit", "stage transition", "exception", "completed")
- **task_id**: Always include for correlation
- **user_id**: Include when available from state
- **chat_id**: Include when available from state
- **Additional Context**: Stage, error details, file paths, counts, etc.

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bug on unfixed code (lack of logging and poor error feedback), then verify the fix provides comprehensive logging and clear error messages while preserving existing functionality.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE implementing the fix. Confirm that errors occur without sufficient logging or user feedback.

**Test Plan**: Simulate various failure scenarios (network errors, invalid URLs, disk space issues, permission errors) and observe that the unfixed code either provides no logging context or fails to notify users clearly. Run these tests on the UNFIXED code to observe the lack of diagnostic information.

**Test Cases**:
1. **Invalid URL Test**: Submit YTcut request with invalid YouTube URL (will fail on unfixed code with minimal logging)
2. **Network Failure Test**: Simulate network interruption during download (will fail on unfixed code without stage context)
3. **Disk Space Test**: Fill disk to trigger FFmpeg concat failure (will fail on unfixed code without clear user notification)
4. **Permission Error Test**: Make temp directory read-only to trigger write failure (will fail on unfixed code without detailed error logging)

**Expected Counterexamples**:
- Errors occur but logs lack task_id, user_id, chat_id, or stage context
- Users receive generic error messages or no error messages at all
- Impossible to trace which task failed or at which stage from logs alone

### Fix Checking

**Goal**: Verify that for all inputs where errors occur, the fixed system logs comprehensive context and sends clear error messages to users.

**Pseudocode:**
```
FOR ALL input WHERE errorOccurs(input) DO
  result := process_ytcut_task_fixed(input)
  ASSERT logContainsTaskId(result.logs)
  ASSERT logContainsUserId(result.logs)
  ASSERT logContainsChatId(result.logs)
  ASSERT logContainsStage(result.logs)
  ASSERT logContainsTraceback(result.logs)
  ASSERT userReceivedErrorMessage(result)
  ASSERT errorMessageIsInformative(result.userMessage)
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where NO errors occur, the fixed system produces the same result as the original system.

**Pseudocode:**
```
FOR ALL input WHERE NOT errorOccurs(input) DO
  ASSERT process_ytcut_task_original(input) = process_ytcut_task_fixed(input)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain (various URLs, segment configurations, modes)
- It catches edge cases that manual unit tests might miss (unusual segment patterns, boundary durations)
- It provides strong guarantees that behavior is unchanged for all successful executions

**Test Plan**: Run successful YTcut operations on UNFIXED code first to capture expected behavior (download completes, concat succeeds, upload works, dashboard updates correctly), then write property-based tests capturing that behavior and verify it continues after fix.

**Test Cases**:
1. **Successful Download Preservation**: Verify that successful downloads produce identical output files before and after fix
2. **Queue Management Preservation**: Verify that queue ordering and lock synchronization work identically before and after fix
3. **Dashboard Update Preservation**: Verify that dashboard updates occur at the same stages with the same content before and after fix
4. **Cleanup Preservation**: Verify that temporary file cleanup occurs identically before and after fix

### Unit Tests

- Test that each new logging statement is executed when its code path is triggered
- Test that try-except blocks catch expected exception types
- Test that error messages sent to users contain stage information
- Test that task_id, user_id, chat_id are included in all relevant log statements

### Property-Based Tests

- Generate random YTcut configurations (various URLs, segment patterns, modes, quality settings) and verify successful executions produce identical results before and after fix
- Generate random error scenarios (network failures, invalid inputs, resource constraints) and verify all errors are logged with full context and users receive clear messages
- Test that lock and queue behavior is preserved across many concurrent task submissions

### Integration Tests

- Test full YTcut flow with logging enabled: confirm → enqueue → download → concat → upload → cleanup
- Test error scenarios at each stage: verify logs contain task_id and stage, verify user receives error message
- Test concurrent YTcut requests: verify queue logging shows correct positions, verify lock logging shows acquisition order
- Test xtaskmanager integration: verify tasks are registered/unregistered correctly with logging
