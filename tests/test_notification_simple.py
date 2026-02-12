# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.

"""
Simple verification tests for notification functionality.

This script verifies that the send_log_notification function has the correct
signature and can be called with the expected parameters.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def test_send_log_notification_signature():
    """Test that send_log_notification has the correct signature."""
    print("Testing send_log_notification signature...")
    
    # Read the xchatsanomlau.py file
    plugin_path = os.path.join(os.path.dirname(__file__), '..', 'Main', 'plugins', 'userbot', 'xchatsanomlau.py')
    
    with open(plugin_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check that send_log_notification function exists
    if 'async def send_log_notification(' not in content:
        print("  ✗ FAILED: send_log_notification function not found")
        return False
    
    # Check that it has user_id parameter
    if 'user_id: int' not in content:
        print("  ✗ FAILED: user_id parameter not found in send_log_notification")
        return False
    
    # Check that it sends to PM user
    if 'await bot_client.send_message(\n            user_id,' in content or 'await bot_client.send_message(user_id,' in content:
        print("  ✓ PASSED: send_log_notification sends to PM user")
    else:
        print("  ✗ FAILED: send_log_notification does not send to PM user")
        print(f"    (Looking for send_message call with user_id)")
        return False
    
    # Check that it sends to LOG_CHAT_ID
    if 'LOG_CHAT_ID' in content and ('await bot_client.send_message(\n            LOG_CHAT_ID,' in content or 'await bot_client.send_message(LOG_CHAT_ID,' in content):
        print("  ✓ PASSED: send_log_notification sends to LOG_CHAT_ID")
    else:
        print("  ✗ FAILED: send_log_notification does not send to LOG_CHAT_ID")
        return False
    
    print("  ✓ ALL CHECKS PASSED")
    return True


def test_laucreate_loop_calls_with_user_id():
    """Test that laucreate_loop calls send_log_notification with user_id."""
    print("\nTesting laucreate_loop calls send_log_notification with user_id...")
    
    # Read the xchatsanomlau.py file
    plugin_path = os.path.join(os.path.dirname(__file__), '..', 'Main', 'plugins', 'userbot', 'xchatsanomlau.py')
    
    with open(plugin_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check that laucreate_loop has user_id parameter
    if 'user_id: Optional[int] = None' not in content:
        print("  ✗ FAILED: user_id parameter not found in laucreate_loop")
        return False
    
    # Check that send_log_notification is called with user_id
    # Look for patterns like: send_log_notification(bot_client, ..., LAUCREATE_TASKS[task_id]["user_id"], ...)
    if 'LAUCREATE_TASKS[task_id]["user_id"]' in content:
        print("  ✓ PASSED: laucreate_loop passes user_id to send_log_notification")
    else:
        print("  ✗ FAILED: laucreate_loop does not pass user_id to send_log_notification")
        return False
    
    print("  ✓ ALL CHECKS PASSED")
    return True


def test_task_state_stores_user_id():
    """Test that task state stores user_id."""
    print("\nTesting task state stores user_id...")
    
    # Read the xchatsanomlau.py file
    plugin_path = os.path.join(os.path.dirname(__file__), '..', 'Main', 'plugins', 'userbot', 'xchatsanomlau.py')
    
    with open(plugin_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check that task state includes user_id
    if '"user_id": user_id' in content or '"user_id": user_id or' in content:
        print("  ✓ PASSED: Task state stores user_id")
    else:
        print("  ✗ FAILED: Task state does not store user_id")
        return False
    
    print("  ✓ ALL CHECKS PASSED")
    return True


def main():
    """Run all verification tests."""
    print("=" * 60)
    print("Notification Functionality Verification Tests")
    print("=" * 60)
    print()
    
    results = []
    results.append(("send_log_notification signature", test_send_log_notification_signature()))
    results.append(("laucreate_loop calls with user_id", test_laucreate_loop_calls_with_user_id()))
    results.append(("task state stores user_id", test_task_state_stores_user_id()))
    
    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{test_name}: {status}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("✓ All verification tests passed!")
        return 0
    else:
        print("✗ Some verification tests failed!")
        return 1


if __name__ == "__main__":
    exit(main())
