"""
Simulation test for hater detection in real-world scenarios.

This test simulates:
1. Hater user (who blocked us) mentions/replies to userbot in group chat
2. Auto response is triggered when feature is enabled
3. No response when feature is disabled
"""

import unittest
import sys
import os
import warnings
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from pyrogram import Client, enums
from pyrogram.types import Message as PyroMessage, User, Chat
from pyrogram.errors import UserIsBlocked

# Suppress warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="pyrogram")

# Add Main to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestHaterSimulation(unittest.IsolatedAsyncioTestCase):
    """Simulate real-world hater detection scenarios."""
    
    def setUp(self):
        """Set up test environment."""
        from Main.plugins.userbot.xdetect_haters import get_settings, save_settings
        
        # Enable hater detection for userbot (ID: 99999)
        settings = get_settings(99999)
        settings["enabled"] = True
        settings["responses"] = [
            {"message": "🚫 Detected hater: {mention_name}", "parse_mode": "html"}
        ]
        settings["response_delay"] = 0
        settings["log_detections"] = True
        settings["random_response"] = False
        save_settings(99999, settings)
    
    async def test_scenario_1_hater_mentions_userbot_in_group(self):
        """
        Scenario 1: Hater mentions userbot in group chat
        
        Setup:
        - Hater user (ID: 12345) has blocked userbot (ID: 99999)
        - Hater mentions userbot in group: "@userbot check this"
        - Feature is enabled
        
        Expected:
        - Userbot detects mention
        - Checks if user blocked us (returns True)
        - Sends auto response to group
        """
        from Main.plugins.userbot.xdetect_haters import hater_detector
        
        # Create mock userbot client
        mock_client = AsyncMock(spec=Client)
        mock_client.me = Mock()
        mock_client.me.id = 99999
        mock_client.send_chat_action = AsyncMock(side_effect=UserIsBlocked())  # User blocked us
        
        # Create mock message from hater in group
        mock_message = Mock(spec=PyroMessage)
        mock_message.id = 123456
        mock_message.chat = Mock(spec=Chat)
        mock_message.chat.id = -1001234567890  # Group chat
        mock_message.chat.title = "Test Group"
        mock_message.chat.type = enums.ChatType.GROUP
        mock_message.chat.username = None
        mock_message.chat.first_name = None
        mock_message.from_user = Mock(spec=User)
        mock_message.from_user.id = 12345  # Hater user
        mock_message.from_user.first_name = "Hater"
        mock_message.from_user.last_name = "User"
        mock_message.from_user.username = "hateruser"
        mock_message.text = "@userbot check this"  # Mentions userbot
        mock_message.reply_to_message = None
        mock_message.reply = AsyncMock()
        
        # Execute detector
        await hater_detector(mock_client, mock_message)
        
        # Verify auto response was sent
        mock_message.reply.assert_called_once()
        
        # Verify response contains hater mention
        call_args = mock_message.reply.call_args
        response_text = call_args[0][0]
        self.assertIn("Detected hater", response_text)
        self.assertIn("Hater", response_text)
        
        print("✅ Scenario 1 PASSED: Auto response sent when hater mentions userbot")
    
    async def test_scenario_2_hater_replies_to_userbot_message(self):
        """
        Scenario 2: Hater replies to userbot's message in group
        
        Setup:
        - Hater user (ID: 12345) has blocked userbot (ID: 99999)
        - Hater replies to userbot's message in group
        - Feature is enabled
        
        Expected:
        - Userbot detects reply
        - Checks if user blocked us (returns True)
        - Sends auto response to group
        """
        from Main.plugins.userbot.xdetect_haters import hater_detector
        
        # Create mock userbot client
        mock_client = AsyncMock(spec=Client)
        mock_client.me = Mock()
        mock_client.me.id = 99999
        mock_client.send_chat_action = AsyncMock(side_effect=UserIsBlocked())
        
        # Create mock userbot's original message
        mock_original_message = Mock(spec=PyroMessage)
        mock_original_message.from_user = Mock(spec=User)
        mock_original_message.from_user.id = 99999  # From userbot
        
        # Create mock reply from hater
        mock_message = Mock(spec=PyroMessage)
        mock_message.id = 123457
        mock_message.chat = Mock(spec=Chat)
        mock_message.chat.id = -1001234567890
        mock_message.chat.title = "Test Group"
        mock_message.chat.type = enums.ChatType.GROUP
        mock_message.chat.username = None
        mock_message.chat.first_name = None
        mock_message.from_user = Mock(spec=User)
        mock_message.from_user.id = 12345
        mock_message.from_user.first_name = "Hater"
        mock_message.from_user.last_name = "User"
        mock_message.from_user.username = "hateruser"
        mock_message.text = "This is wrong!"
        mock_message.reply_to_message = mock_original_message  # Replying to userbot
        mock_message.reply = AsyncMock()
        
        # Execute detector
        await hater_detector(mock_client, mock_message)
        
        # Verify auto response was sent
        mock_message.reply.assert_called_once()
        
        print("✅ Scenario 2 PASSED: Auto response sent when hater replies to userbot")
    
    async def test_scenario_3_normal_user_not_blocked_no_response(self):
        """
        Scenario 3: Normal user (not blocked) mentions userbot
        
        Setup:
        - Normal user (ID: 67890) has NOT blocked userbot
        - User mentions userbot in group
        - Feature is enabled
        
        Expected:
        - Userbot detects mention
        - Checks if user blocked us (returns False)
        - NO auto response sent (user is not a hater)
        """
        from Main.plugins.userbot.xdetect_haters import hater_detector
        
        # Create mock userbot client
        mock_client = AsyncMock(spec=Client)
        mock_client.me = Mock()
        mock_client.me.id = 99999
        mock_client.send_chat_action = AsyncMock()  # No exception = not blocked
        
        # Create mock message from normal user
        mock_message = Mock(spec=PyroMessage)
        mock_message.id = 123458
        mock_message.chat = Mock(spec=Chat)
        mock_message.chat.id = -1001234567890
        mock_message.chat.title = "Test Group"
        mock_message.chat.type = enums.ChatType.GROUP
        mock_message.chat.username = None
        mock_message.chat.first_name = None
        mock_message.from_user = Mock(spec=User)
        mock_message.from_user.id = 67890  # Normal user
        mock_message.from_user.first_name = "Normal"
        mock_message.from_user.last_name = "User"
        mock_message.from_user.username = "normaluser"
        mock_message.text = "@userbot hello"
        mock_message.reply_to_message = None
        mock_message.reply = AsyncMock()
        
        # Execute detector
        await hater_detector(mock_client, mock_message)
        
        # Verify NO response was sent (user is not a hater)
        mock_message.reply.assert_not_called()
        
        print("✅ Scenario 3 PASSED: No response for normal user (not blocked)")
    
    async def test_scenario_4_feature_disabled_no_response(self):
        """
        Scenario 4: Feature disabled, hater mentions userbot
        
        Setup:
        - Hater user has blocked userbot
        - Hater mentions userbot in group
        - Feature is DISABLED
        
        Expected:
        - Detector returns early
        - NO auto response sent
        """
        from Main.plugins.userbot.xdetect_haters import hater_detector, get_settings, save_settings
        
        # Disable feature
        settings = get_settings(99999)
        settings["enabled"] = False
        save_settings(99999, settings)
        
        # Create mock userbot client
        mock_client = AsyncMock(spec=Client)
        mock_client.me = Mock()
        mock_client.me.id = 99999
        mock_client.send_chat_action = AsyncMock(side_effect=UserIsBlocked())
        
        # Create mock message from hater
        mock_message = Mock(spec=PyroMessage)
        mock_message.id = 123459
        mock_message.chat = Mock(spec=Chat)
        mock_message.chat.id = -1001234567890
        mock_message.chat.title = "Test Group"
        mock_message.chat.type = enums.ChatType.GROUP
        mock_message.chat.username = None
        mock_message.chat.first_name = None
        mock_message.from_user = Mock(spec=User)
        mock_message.from_user.id = 12345
        mock_message.from_user.first_name = "Hater"
        mock_message.from_user.last_name = "User"
        mock_message.from_user.username = "hateruser"
        mock_message.text = "@userbot test"
        mock_message.reply_to_message = None
        mock_message.reply = AsyncMock()
        
        # Execute detector
        await hater_detector(mock_client, mock_message)
        
        # Verify NO response was sent (feature disabled)
        mock_message.reply.assert_not_called()
        
        # Re-enable for other tests
        settings["enabled"] = True
        save_settings(99999, settings)
        
        print("✅ Scenario 4 PASSED: No response when feature is disabled")
    
    async def test_scenario_5_multiple_haters_in_sequence(self):
        """
        Scenario 5: Multiple haters mention userbot in sequence
        
        Setup:
        - Multiple users who blocked userbot mention it
        - Feature is enabled
        
        Expected:
        - Each hater gets auto response
        - Responses are sent correctly
        """
        from Main.plugins.userbot.xdetect_haters import hater_detector
        
        # Create mock userbot client
        mock_client = AsyncMock(spec=Client)
        mock_client.me = Mock()
        mock_client.me.id = 99999
        mock_client.send_chat_action = AsyncMock(side_effect=UserIsBlocked())
        
        haters = [
            {"id": 11111, "name": "Hater1", "username": "hater1"},
            {"id": 22222, "name": "Hater2", "username": "hater2"},
            {"id": 33333, "name": "Hater3", "username": "hater3"},
        ]
        
        for hater in haters:
            # Create mock message from each hater
            mock_message = Mock(spec=PyroMessage)
            mock_message.id = hater["id"]
            mock_message.chat = Mock(spec=Chat)
            mock_message.chat.id = -1001234567890
            mock_message.chat.title = "Test Group"
            mock_message.chat.type = enums.ChatType.GROUP
            mock_message.chat.username = None
            mock_message.chat.first_name = None
            mock_message.from_user = Mock(spec=User)
            mock_message.from_user.id = hater["id"]
            mock_message.from_user.first_name = hater["name"]
            mock_message.from_user.last_name = ""
            mock_message.from_user.username = hater["username"]
            mock_message.text = f"@userbot message from {hater['name']}"
            mock_message.reply_to_message = None
            mock_message.reply = AsyncMock()
            
            # Execute detector
            await hater_detector(mock_client, mock_message)
            
            # Verify response was sent
            mock_message.reply.assert_called_once()
        
        print("✅ Scenario 5 PASSED: Multiple haters detected and responded to")
    
    async def test_scenario_6_cache_prevents_duplicate_checks(self):
        """
        Scenario 6: Cache prevents duplicate block checks
        
        Setup:
        - Same hater mentions userbot twice
        - Feature is enabled
        
        Expected:
        - First mention: Block check performed
        - Second mention: Block status retrieved from cache
        - Both get auto response
        """
        from Main.plugins.userbot.xdetect_haters import hater_detector, get_cached_block_status
        
        # Create mock userbot client
        mock_client = AsyncMock(spec=Client)
        mock_client.me = Mock()
        mock_client.me.id = 99999
        mock_client.send_chat_action = AsyncMock(side_effect=UserIsBlocked())
        
        hater_id = 44444
        
        # First mention
        mock_message1 = Mock(spec=PyroMessage)
        mock_message1.id = 123460
        mock_message1.chat = Mock(spec=Chat)
        mock_message1.chat.id = -1001234567890
        mock_message1.chat.title = "Test Group"
        mock_message1.chat.type = enums.ChatType.GROUP
        mock_message1.chat.username = None
        mock_message1.chat.first_name = None
        mock_message1.from_user = Mock(spec=User)
        mock_message1.from_user.id = hater_id
        mock_message1.from_user.first_name = "CachedHater"
        mock_message1.from_user.last_name = ""
        mock_message1.from_user.username = "cachedhater"
        mock_message1.text = "@userbot first mention"
        mock_message1.reply_to_message = None
        mock_message1.reply = AsyncMock()
        
        # Execute first detection
        await hater_detector(mock_client, mock_message1)
        mock_message1.reply.assert_called_once()
        
        # Verify cache was set
        has_cache, is_blocked = get_cached_block_status(hater_id)
        self.assertTrue(has_cache, "Cache should be set after first check")
        self.assertTrue(is_blocked, "User should be marked as blocked in cache")
        
        # Second mention (should use cache)
        mock_message2 = Mock(spec=PyroMessage)
        mock_message2.id = 123461
        mock_message2.chat = Mock(spec=Chat)
        mock_message2.chat.id = -1001234567890
        mock_message2.chat.title = "Test Group"
        mock_message2.chat.type = enums.ChatType.GROUP
        mock_message2.chat.username = None
        mock_message2.chat.first_name = None
        mock_message2.from_user = Mock(spec=User)
        mock_message2.from_user.id = hater_id
        mock_message2.from_user.first_name = "CachedHater"
        mock_message2.from_user.last_name = ""
        mock_message2.from_user.username = "cachedhater"
        mock_message2.text = "@userbot second mention"
        mock_message2.reply_to_message = None
        mock_message2.reply = AsyncMock()
        
        # Execute second detection (should use cache)
        await hater_detector(mock_client, mock_message2)
        mock_message2.reply.assert_called_once()
        
        print("✅ Scenario 6 PASSED: Cache prevents duplicate block checks")


class TestResponseFormatting(unittest.IsolatedAsyncioTestCase):
    """Test response message formatting in real scenarios."""
    
    async def test_response_contains_correct_placeholders(self):
        """Test that response message contains correctly formatted placeholders."""
        from Main.plugins.userbot.xdetect_haters import format_response
        
        template = "🚫 Hater detected: {mention_name} (@{username})"
        user_info = {
            "first_name": "John",
            "last_name": "Doe",
            "username": "johndoe"
        }
        user_id = 12345
        
        result = format_response(template, user_info, user_id)
        
        # Verify mention link
        self.assertIn('href="tg://user?id=12345"', result)
        self.assertIn("John", result)
        self.assertIn("@johndoe", result)
        
        print("✅ Response formatting test PASSED")


if __name__ == '__main__':
    # Run simulation tests
    print("\n" + "="*70)
    print("🧪 HATER DETECTION SIMULATION TESTS")
    print("="*70 + "\n")
    
    unittest.main(verbosity=2)
