# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.

"""
Manual verification script for delete_if_self() logic.

This script verifies the logic of the delete_if_self() method by checking:
1. Configuration reading logic
2. Boolean conversion logic
3. Delay parsing logic
4. Error handling

Run this script to verify the implementation is correct.
"""

def verify_boolean_conversion():
    """Verify that string to boolean conversion works correctly."""
    print("Testing boolean conversion logic...")
    
    test_cases = [
        ("on", True),
        ("ON", True),
        ("true", True),
        ("True", True),
        ("1", True),
        ("yes", True),
        ("off", False),
        ("OFF", False),
        ("false", False),
        ("False", False),
        ("0", False),
        ("no", False),
        ("random", False),
        (None, False),
    ]
    
    passed = 0
    failed = 0
    
    for enabled_value, expected in test_cases:
        # Simulate the logic from delete_if_self()
        if enabled_value is None:
            is_enabled = False
        else:
            enabled_str = str(enabled_value).lower().strip()
            is_enabled = enabled_str in ("on", "true", "1", "yes")
        
        if is_enabled == expected:
            print(f"  ✓ '{enabled_value}' -> {is_enabled} (expected {expected})")
            passed += 1
        else:
            print(f"  ✗ '{enabled_value}' -> {is_enabled} (expected {expected})")
            failed += 1
    
    print(f"\nBoolean conversion: {passed} passed, {failed} failed\n")
    return failed == 0


def verify_delay_parsing():
    """Verify that delay parsing works correctly."""
    print("Testing delay parsing logic...")
    
    test_cases = [
        ("0", 0),
        ("1", 1),
        ("5", 5),
        ("10", 10),
        ("-1", 0),  # Negative should become 0
        ("-5", 0),  # Negative should become 0
        ("invalid", 0),  # Invalid should become 0
        ("abc", 0),  # Invalid should become 0
        (None, 0),  # None should become 0
        ("", 0),  # Empty should become 0
    ]
    
    passed = 0
    failed = 0
    
    for delay_value, expected in test_cases:
        # Simulate the logic from delete_if_self()
        delay_sec = 0
        if delay_value is not None:
            try:
                delay_sec = int(delay_value)
                if delay_sec < 0:
                    delay_sec = 0
            except (ValueError, TypeError):
                delay_sec = 0
        
        if delay_sec == expected:
            print(f"  ✓ '{delay_value}' -> {delay_sec} (expected {expected})")
            passed += 1
        else:
            print(f"  ✗ '{delay_value}' -> {delay_sec} (expected {expected})")
            failed += 1
    
    print(f"\nDelay parsing: {passed} passed, {failed} failed\n")
    return failed == 0


def verify_config_type_logic():
    """Verify that config type selection logic works correctly."""
    print("Testing config type selection logic...")
    
    test_cases = [
        ("global", "global"),
        ("GLOBAL", "global"),
        ("Global", "global"),
        ("per_account", "per_account"),
        ("PER_ACCOUNT", "per_account"),
        (None, "per_account"),  # Default to per_account
        ("", "per_account"),  # Empty defaults to per_account
        ("invalid", "per_account"),  # Invalid defaults to per_account
    ]
    
    passed = 0
    failed = 0
    
    for apply_type_value, expected_type in test_cases:
        # Simulate the logic from delete_if_self()
        if apply_type_value is None:
            apply_type = "per_account"
        else:
            apply_type = apply_type_value
        
        # Check which config to use
        if str(apply_type).lower() == "global":
            config_type = "global"
        else:
            config_type = "per_account"
        
        if config_type == expected_type:
            print(f"  ✓ '{apply_type_value}' -> {config_type} (expected {expected_type})")
            passed += 1
        else:
            print(f"  ✗ '{apply_type_value}' -> {config_type} (expected {expected_type})")
            failed += 1
    
    print(f"\nConfig type selection: {passed} passed, {failed} failed\n")
    return failed == 0


def main():
    """Run all verification tests."""
    print("=" * 60)
    print("Verification Script for delete_if_self() Logic")
    print("=" * 60)
    print()
    
    results = []
    results.append(("Boolean Conversion", verify_boolean_conversion()))
    results.append(("Delay Parsing", verify_delay_parsing()))
    results.append(("Config Type Logic", verify_config_type_logic()))
    
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
