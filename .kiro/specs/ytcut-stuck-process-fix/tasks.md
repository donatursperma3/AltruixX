# Implementation Plan

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - YTcut Process Stuck Without Diagnostic Logging
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate insufficient logging and poor error feedback
  - **Scoped PBT Approach**: Test concrete failure scenarios (invalid URL, network error, disk space, permission error) to ensure reproducibility
  - Test that when YTcut process encounters errors, the system logs comprehensive context (task_id, user_id, chat_id, stage, traceback) and sends clear error messages to users
  - The test assertions should match the Expected Behavior Properties from design (Requirements 2.1-2.8)
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves insufficient logging exists)
  - Document counterexamples found:
    - Errors occur but logs lack task_id, user_id, chat_id, or stage context
    - Users receive generic error messages or no error messages at all
    - Impossible to trace which task failed or at which stage from logs alone
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Successful YTcut Executions Unchanged
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code for successful YTcut operations:
    - Successful downloads produce expected output files
    - Queue management and lock synchronization work correctly
    - Dashboard updates occur at expected stages
    - Temporary file cleanup executes properly
  - Write property-based tests capturing observed behavior patterns from Preservation Requirements (Requirements 3.1-3.9)
  - Property-based testing generates many test cases for stronger guarantees across various URLs, segment configurations, and modes
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9_

- [~] 3. Fix for YTcut stuck process - Add comprehensive logging and error handling

  - [x] 3.1 Add logging and error handling to ytcut_confirm_yes_cb callback
    - File: `Main/plugins/bot/xytcut_bot.py`
    - Function: `ytcut_confirm_yes_cb` (line ~1000)
    - Add entry logging after state retrieval:
      ```python
      Altruix.log(
          f"YTcut callback confirm: task_id={task_id} user_id={cb.from_user.id if cb.from_user else 'unknown'} "
          f"chat_id={state.get('chat_id')} url={state.get('url')}"
      )
      ```
    - Wrap `enqueue_ytcut_run` call with try-except:
      ```python
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
    - Ensure `traceback` and `html` modules are imported at top of file
    - _Bug_Condition: isBugCondition(input) where process gets stuck after confirmation without diagnostic logging_
    - _Expected_Behavior: Log callback invocation with task_id, user_id, chat_id; catch and log enqueue failures with full traceback; send clear error message to user_
    - _Preservation: Successful callback handling continues to work identically_
    - _Requirements: 2.1, 2.7_

  - [x] 3.2 Add comprehensive logging to enqueue_ytcut_run function
    - File: `Main/internals/ytcut_helpers.py`
    - Function: `enqueue_ytcut_run` (line 818)
    - Add entry logging after state retrieval:
      ```python
      Altruix.log(
          f"YTcut enqueue_ytcut_run entry: task_id={task_id} user_id={state.get('user_id')} "
          f"chat_id={state.get('chat_id')} lock_locked={Altruix.YTCUT_LOCK.locked()} "
          f"queue_length={len(Altruix.YTCUT_QUEUE)}"
      )
      ```
    - Add lock wait logging before lock acquisition:
      ```python
      if task_id in Altruix.YTCUT_QUEUE:
          Altruix.log(f"YTcut waiting for lock: task_id={task_id} queue_position={Altruix.YTCUT_QUEUE.index(task_id) + 1}")
          await Altruix.YTCUT_LOCK.acquire()
      ```
    - Add lock acquired logging after both lock acquisition paths:
      ```python
      Altruix.log(f"YTcut lock acquired: task_id={task_id} user_id={state.get('user_id')} chat_id={state.get('chat_id')}")
      ```
    - Wrap `process_ytcut_task` call with enhanced try-except:
      ```python
      try:
          await process_ytcut_task(state, client)
      except Exception as e:
          Altruix.log(
              f"YTcut enqueue_ytcut_run exception: task_id={task_id} user_id={state.get('user_id')} "
              f"chat_id={state.get('chat_id')} error={e}\n{traceback.format_exc()}"
          )
          raise
      ```
    - Add exit logging in finally block before `state["processing"] = False`:
      ```python
      Altruix.log(
          f"YTcut enqueue_ytcut_run exit: task_id={task_id} processing={state.get('processing')} "
          f"lock_locked={Altruix.YTCUT_LOCK.locked()}"
      )
      ```
    - Ensure `traceback` module is imported at top of file
    - _Bug_Condition: isBugCondition(input) where lock acquisition or queue management fails without sufficient logging_
    - _Expected_Behavior: Log entry with task_id, lock state, queue state; log lock waiting and acquisition; log exceptions with full context; log exit status_
    - _Preservation: Lock mechanism and queue management continue to work identically_
    - _Requirements: 2.2, 2.3, 2.6, 2.8_

  - [ ] 3.3 Add comprehensive logging to process_ytcut_task function
    - File: `Main/internals/ytcut_helpers.py`
    - Function: `process_ytcut_task` (line 852)
    - Add entry logging after task_id extraction:
      ```python
      Altruix.log(
          f"YTcut process_ytcut_task entry: task_id={task_id} user_id={state.get('user_id')} "
          f"chat_id={state.get('chat_id')} url={state.get('url')} mode={state.get('mode')} "
          f"extract={state.get('extract')} segments_count={len(state.get('segments', []))}"
      )
      ```
    - Add stage transition logging before each `current_stage` assignment:
      ```python
      Altruix.log(
          f"YTcut stage transition: task_id={task_id} user_id={state.get('user_id')} "
          f"chat_id={state.get('chat_id')} stage='{current_stage}'"
      )
      ```
    - Wrap `download_ytcut_thumbnail` call with try-except:
      ```python
      try:
          await download_ytcut_thumbnail(state.get("thumbnail", ""), thumb_path)
          Altruix.log(f"YTcut thumbnail downloaded: task_id={task_id} thumb_path={thumb_path}")
      except Exception as thumb_err:
          Altruix.log(
              f"YTcut thumbnail download failed (non-critical): task_id={task_id} "
              f"error={thumb_err}\n{traceback.format_exc()}"
          )
      ```
    - Add exit logging in finally block before `cleanup_ytcut_temp`:
      ```python
      Altruix.log(
          f"YTcut process_ytcut_task exit: task_id={task_id} user_id={state.get('user_id')} "
          f"chat_id={state.get('chat_id')} final_stage='{current_stage}'"
      )
      ```
    - _Bug_Condition: isBugCondition(input) where process fails at any stage without stage-specific logging_
    - _Expected_Behavior: Log entry with all task details; log each stage transition; log thumbnail operations; log exit with final stage_
    - _Preservation: Task state management and dashboard updates continue to work identically_
    - _Requirements: 2.4, 2.5, 2.8_

  - [ ] 3.4 Add error handling for download stage in process_ytcut_task
    - File: `Main/internals/ytcut_helpers.py`
    - Function: `process_ytcut_task` (line 852)
    - Wrap `run_ytcut_download` call with try-except:
      ```python
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
          raise
      ```
    - _Bug_Condition: isBugCondition(input) where download fails without stage context in logs_
    - _Expected_Behavior: Log download completion with parts count; log download failures with task_id, stage, and full traceback_
    - _Preservation: Download functionality continues to work identically for successful cases_
    - _Requirements: 2.5, 2.6_

  - [ ] 3.5 Add error handling for concat stage in process_ytcut_task
    - File: `Main/internals/ytcut_helpers.py`
    - Function: `process_ytcut_task` (line 852)
    - Wrap `run_ytcut_ffmpeg_concat` call with try-except:
      ```python
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
          raise
      ```
    - _Bug_Condition: isBugCondition(input) where concat fails without stage context in logs_
    - _Expected_Behavior: Log concat completion with output file size; log concat failures with task_id, stage, and full traceback_
    - _Preservation: Concat functionality continues to work identically for successful cases_
    - _Requirements: 2.5, 2.6_

  - [ ] 3.6 Add enhanced logging for upload stage in process_ytcut_task
    - File: `Main/internals/ytcut_helpers.py`
    - Function: `process_ytcut_task` (line 852)
    - Add upload start logging before `send_video`/`send_audio`:
      ```python
      Altruix.log(
          f"YTcut upload starting: task_id={task_id} chat_id={state.get('chat_id')} "
          f"user_id={state.get('user_id')} extract={state['extract']} "
          f"output_file={output_file} file_size={os.path.getsize(output_file)}"
      )
      ```
    - Add upload completion logging after successful send:
      ```python
      Altruix.log(
          f"YTcut upload completed: task_id={task_id} chat_id={state.get('chat_id')} "
          f"user_id={state.get('user_id')}"
      )
      ```
    - _Bug_Condition: isBugCondition(input) where upload fails without detailed logging_
    - _Expected_Behavior: Log upload start with file details; log upload completion_
    - _Preservation: Upload functionality continues to work identically_
    - _Requirements: 2.5_

  - [ ] 3.7 Enhance exception handler in process_ytcut_task
    - File: `Main/internals/ytcut_helpers.py`
    - Function: `process_ytcut_task` (line 852)
    - Replace existing exception logging with enhanced version:
      ```python
      Altruix.log(
          f"YTcut process_ytcut_task exception: task_id={task_id} user_id={state.get('user_id')} "
          f"chat_id={state.get('chat_id')} stage='{current_stage}' error={e}\n{tb_text}"
      )
      ```
    - Enhance user error message to include stage:
      ```python
      text=(
          f"❌ <b>Gagal memproses YTcut</b>\n"
          f"<b>Stage:</b> {html.escape(current_stage)}\n"
          f"<b>Error:</b> <code>{html.escape(err_text[:200])}</code>"
      )
      ```
    - Ensure `html` module is imported at top of file
    - _Bug_Condition: isBugCondition(input) where exceptions occur without full context or clear user notification_
    - _Expected_Behavior: Log exceptions with task_id, user_id, chat_id, stage, and full traceback; send error message to user with stage information_
    - _Preservation: Error notification to group log continues to work identically_
    - _Requirements: 2.6, 2.7_

  - [ ] 3.8 Add enhanced logging to run_ytcut_download function
    - File: `Main/internals/ytcut_helpers.py`
    - Function: `run_ytcut_download` (line 431)
    - Add subprocess start logging after process creation:
      ```python
      Altruix.log(
          f"YTcut download subprocess started: task_id={state.get('task_id')} pid={process.pid}"
      )
      ```
    - Add subprocess exit logging after process.wait():
      ```python
      Altruix.log(
          f"YTcut download subprocess completed: task_id={state.get('task_id')} "
          f"returncode={ret} stdout_lines={len(full_stdout)} stderr_lines={len(stderr_lines)}"
      )
      ```
    - Enhance error message to include task_id:
      ```python
      raise RuntimeError(
          f"YT-DLP Error (task_id={state.get('task_id')}): {err or out or 'Unknown error'}"
      )
      ```
    - _Bug_Condition: isBugCondition(input) where yt-dlp subprocess fails without subprocess-level logging_
    - _Expected_Behavior: Log subprocess start with PID; log subprocess completion with return code and output line counts; include task_id in error messages_
    - _Preservation: Download subprocess execution continues to work identically_
    - _Requirements: 2.5, 2.6_

  - [ ] 3.9 Add comprehensive logging to run_ytcut_ffmpeg_concat function
    - File: `Main/internals/ytcut_helpers.py`
    - Function: `run_ytcut_ffmpeg_concat` (line 580)
    - Add entry logging at function start:
      ```python
      Altruix.log(
          f"YTcut concat entry: task_id={state.get('task_id')} parts_count={len(parts)} "
          f"output_path={output_path} extract={extract}"
      )
      ```
    - Add concat file creation logging after file write:
      ```python
      Altruix.log(
          f"YTcut concat list created: task_id={state.get('task_id')} concat_file={concat_file} "
          f"parts_count={len(parts)}"
      )
      ```
    - Add FFmpeg command logging before subprocess execution:
      ```python
      Altruix.log(
          f"YTcut concat ffmpeg starting: task_id={state.get('task_id')} cmd={' '.join(cmd)}"
      )
      ```
    - Add FFmpeg retry logging when fallback encoding is attempted:
      ```python
      Altruix.log(
          f"YTcut concat copy failed, retrying with re-encode: task_id={state.get('task_id')} "
          f"extract={extract}"
      )
      ```
    - Enhance error message to include task_id:
      ```python
      raise RuntimeError(
          f"FFmpeg concat error (task_id={state.get('task_id')}): {err or out or 'Unknown error'}"
      )
      ```
    - Add thumbnail embed start logging:
      ```python
      Altruix.log(
          f"YTcut thumbnail embed starting: task_id={state.get('task_id')} thumb_path={thumb_path}"
      )
      ```
    - Add thumbnail embed success logging:
      ```python
      Altruix.log(
          f"YTcut thumbnail embed success: task_id={state.get('task_id')}"
      )
      ```
    - _Bug_Condition: isBugCondition(input) where FFmpeg concat fails without detailed command and retry logging_
    - _Expected_Behavior: Log entry with parts count; log concat file creation; log FFmpeg command; log retry attempts; log thumbnail operations; include task_id in error messages_
    - _Preservation: Concat subprocess execution and thumbnail embedding continue to work identically_
    - _Requirements: 2.5, 2.6_

  - [ ] 3.10 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Comprehensive Logging and Error Feedback
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 1
    - **EXPECTED OUTCOME**: Test PASSES (confirms comprehensive logging and error feedback are now present)
    - Verify that when errors occur:
      - Logs contain task_id, user_id, chat_id, stage, and full traceback
      - Users receive clear error messages with stage information
      - All critical stages have entry/exit logging
      - Subprocess operations are logged with context
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8_

  - [ ] 3.11 Verify preservation tests still pass
    - **Property 2: Preservation** - Successful YTcut Executions Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Verify that successful YTcut operations:
      - Produce identical output files before and after fix
      - Use lock mechanism and queue management identically
      - Update dashboard at the same stages with same content
      - Clean up temporary files identically
      - Integrate with xtaskmanager identically
    - Confirm all tests still pass after fix (no regressions)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9_

- [ ] 4. Checkpoint - Ensure all tests pass
  - Run all bug condition exploration tests - verify they now pass with comprehensive logging
  - Run all preservation property tests - verify no regressions in successful executions
  - Run integration tests with full YTcut flow - verify logging appears at all stages
  - Test error scenarios at each stage - verify logs contain task_id and stage, verify user receives clear error message
  - Test concurrent YTcut requests - verify queue logging shows correct positions, verify lock logging shows acquisition order
  - Review logs for consistency - verify all log statements follow the standard format (YTcut {function} {event}: task_id=... user_id=... chat_id=...)
  - If any issues arise, ask the user for guidance before proceeding
