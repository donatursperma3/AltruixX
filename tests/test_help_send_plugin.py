"""
Comprehensive test suite for Main/plugins/bot/help.py - Send Plugin functionality

Tests cover:
1. Coroutine handling (await get_callback_data)
2. Client selection logic (userbot vs bot)
3. Target chat selection
4. Error handling
5. Fallback mechanisms
"""

import unittest
import sys
import os
import warnings
from unittest.mock import Mock, AsyncMock, MagicMock, patch, call
from pyrogram import Client
from pyrogram.types import CallbackQuery, Chat, User, Message
from pyrogram import enums

# Suppress Pyrogram deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="pyrogram")

# Add Main to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestSendPluginCompressed(unittest.IsolatedAsyncioTestCase):
    """Test send_plugin_execute_compressed function."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock Altruix
        import Main.plugins.bot.help as help_module
        self.help_module = help_module
        
        # Mock Altruix.clients
        self.mock_client1 = AsyncMock(spec=Client)
        self.mock_client1.me = Mock()
        self.mock_client1.me.id = 12345
        self.mock_client1.send_document = AsyncMock()
        
        self.mock_client2 = AsyncMock(spec=Client)
        self.mock_client2.me = Mock()
        self.mock_client2.me.id = 67890
        self.mock_client2.send_document = AsyncMock()
        
        # Mock bot
        self.mock_bot = AsyncMock(spec=Client)
        self.mock_bot.send_document = AsyncMock()
        
        # Create mock CallbackQuery
        self.mock_cb = AsyncMock(spec=CallbackQuery)
        self.mock_cb.answer = AsyncMock()
        self.mock_cb.edit_message_text = AsyncMock()
        self.mock_cb.from_user = Mock(spec=User)
        self.mock_cb.from_user.id = 12345
        
        # Mock message and chat
        self.mock_cb.message = Mock(spec=Message)
        self.mock_cb.message.chat = Mock(spec=Chat)
        self.mock_cb.message.chat.id = -1001234567890  # Group chat
        
        # Mock matches
        self.mock_cb.matches = [Mock()]
        self.mock_cb.matches[0].group = Mock(side_effect=lambda x: {
            1: "abc123def456"  # hash_id
        }.get(x))
    
    @patch('Main.plugins.bot.help.get_callback_data')
    @patch('Main.plugins.bot.help.get_plugin_data')
    @patch('Main.plugins.bot.help.Altruix')
    @patch('os.path.exists')
    async def test_await_get_callback_data(self, mock_exists, mock_altruix, mock_get_plugin, mock_get_callback):
        """Test that get_callback_data is properly awaited."""
        # Setup
        mock_get_callback.return_value = "conf_send_pl#test_plugin#yes?page=0&si=0&cid=-1001234567890&mode=userbot"
        mock_exists.return_value = True
        mock_altruix.clients = [self.mock_client1]
        mock_altruix.bot = self.mock_bot
        mock_altruix.log = Mock()
        mock_get_plugin.return_value = ("<b>Test</b>", Mock())
        
        # Import function
        from Main.plugins.bot.help import send_plugin_execute_compressed
        
        # Execute
        await send_plugin_execute_compressed(self.mock_bot, self.mock_cb)
        
        # Verify get_callback_data was called (it should be awaited in the function)
        mock_get_callback.assert_called_once_with("abc123def456")
        
        # Verify no coroutine error occurred (function completed successfully)
        self.mock_cb.answer.assert_called()
    
    @patch('Main.plugins.bot.help.get_callback_data')
    @patch('Main.plugins.bot.help.get_plugin_data')
    @patch('Main.plugins.bot.help.Altruix')
    @patch('os.path.exists')
    async def test_userbot_selected_by_session_index(self, mock_exists, mock_altruix, mock_get_plugin, mock_get_callback):
        """Test that userbot is selected based on session_index (si)."""
        # Setup - si=1 should select second userbot
        mock_get_callback.return_value = "conf_send_pl#test_plugin#yes?page=0&si=1&cid=-1001234567890&mode=userbot"
        mock_exists.return_value = True
        mock_altruix.clients = [self.mock_client1, self.mock_client2]
        mock_altruix.bot = self.mock_bot
        mock_altruix.log = Mock()
        mock_get_plugin.return_value = ("<b>Test</b>", Mock())
        
        # Import function
        from Main.plugins.bot.help import send_plugin_execute_compressed
        
        # Execute
        await send_plugin_execute_compressed(self.mock_bot, self.mock_cb)
        
        # Verify second userbot (index 1) was used
        self.mock_client2.send_document.assert_called_once()
        self.mock_client1.send_document.assert_not_called()
        self.mock_bot.send_document.assert_not_called()
    
    @patch('Main.plugins.bot.help.get_callback_data')
    @patch('Main.plugins.bot.help.get_plugin_data')
    @patch('Main.plugins.bot.help.Altruix')
    @patch('os.path.exists')
    async def test_userbot_not_bot_sends_plugin(self, mock_exists, mock_altruix, mock_get_plugin, mock_get_callback):
        """Test that userbot sends plugin, not bot assistant."""
        # Setup
        mock_get_callback.return_value = "conf_send_pl#test_plugin#yes?page=0&si=0&cid=-1001234567890&mode=userbot"
        mock_exists.return_value = True
        mock_altruix.clients = [self.mock_client1]
        mock_altruix.bot = self.mock_bot
        mock_altruix.log = Mock()
        mock_get_plugin.return_value = ("<b>Test</b>", Mock())
        
        # Import function
        from Main.plugins.bot.help import send_plugin_execute_compressed
        
        # Execute
        await send_plugin_execute_compressed(self.mock_bot, self.mock_cb)
        
        # Verify userbot was used, NOT bot
        self.mock_client1.send_document.assert_called_once()
        self.mock_bot.send_document.assert_not_called()
    
    @patch('Main.plugins.bot.help.get_callback_data')
    @patch('Main.plugins.bot.help.get_plugin_data')
    @patch('Main.plugins.bot.help.Altruix')
    @patch('os.path.exists')
    async def test_target_chat_from_callback_message(self, mock_exists, mock_altruix, mock_get_plugin, mock_get_callback):
        """Test that target chat is taken from cb.message.chat.id (where button was pressed)."""
        # Setup
        mock_get_callback.return_value = "conf_send_pl#test_plugin#yes?page=0&si=0&cid=-1001111111111&mode=userbot"
        mock_exists.return_value = True
        mock_altruix.clients = [self.mock_client1]
        mock_altruix.bot = self.mock_bot
        mock_altruix.log = Mock()
        mock_get_plugin.return_value = ("<b>Test</b>", Mock())
        
        # Set different chat IDs
        self.mock_cb.message.chat.id = -1001234567890  # Where button was pressed
        # cid in callback data is -1001111111111 (different)
        
        # Import function
        from Main.plugins.bot.help import send_plugin_execute_compressed
        
        # Execute
        await send_plugin_execute_compressed(self.mock_bot, self.mock_cb)
        
        # Verify send_document was called with cb.message.chat.id (priority 1)
        call_args = self.mock_client1.send_document.call_args
        self.assertEqual(call_args[1]['chat_id'], -1001234567890)
    
    @patch('Main.plugins.bot.help.get_callback_data')
    @patch('Main.plugins.bot.help.get_plugin_data')
    @patch('Main.plugins.bot.help.Altruix')
    @patch('os.path.exists')
    async def test_fallback_to_first_userbot(self, mock_exists, mock_altruix, mock_get_plugin, mock_get_callback):
        """Test fallback to first userbot when si is invalid."""
        # Setup - si=-1 means no specific session
        mock_get_callback.return_value = "conf_send_pl#test_plugin#yes?page=0&si=-1&cid=-1001234567890&mode=userbot"
        mock_exists.return_value = True
        mock_altruix.clients = [self.mock_client1, self.mock_client2]
        mock_altruix.bot = self.mock_bot
        mock_altruix.log = Mock()
        mock_get_plugin.return_value = ("<b>Test</b>", Mock())
        
        # User ID doesn't match any client
        self.mock_cb.from_user.id = 99999
        
        # Import function
        from Main.plugins.bot.help import send_plugin_execute_compressed
        
        # Execute
        await send_plugin_execute_compressed(self.mock_bot, self.mock_cb)
        
        # Verify first userbot was used as fallback
        self.mock_client1.send_document.assert_called_once()
        self.mock_bot.send_document.assert_not_called()
    
    @patch('Main.plugins.bot.help.get_callback_data')
    @patch('Main.plugins.bot.help.get_plugin_data')
    @patch('Main.plugins.bot.help.Altruix')
    @patch('os.path.exists')
    async def test_bot_fallback_when_no_userbot(self, mock_exists, mock_altruix, mock_get_plugin, mock_get_callback):
        """Test bot assistant is used only when no userbot available."""
        # Setup
        mock_get_callback.return_value = "conf_send_pl#test_plugin#yes?page=0&si=0&cid=-1001234567890&mode=userbot"
        mock_exists.return_value = True
        mock_altruix.clients = []  # No userbots available
        mock_altruix.bot = self.mock_bot
        mock_altruix.log = Mock()
        mock_get_plugin.return_value = ("<b>Test</b>", Mock())
        
        # Import function
        from Main.plugins.bot.help import send_plugin_execute_compressed
        
        # Execute
        await send_plugin_execute_compressed(self.mock_bot, self.mock_cb)
        
        # Verify bot was used as last resort
        self.mock_bot.send_document.assert_called_once()
        
        # Verify warning log was called
        mock_altruix.log.assert_any_call(
            unittest.mock.ANY,  # Message contains "WARNING"
            level=30
        )
    
    @patch('Main.plugins.bot.help.get_callback_data')
    async def test_expired_session_handling(self, mock_get_callback):
        """Test handling of expired session (no callback data)."""
        # Setup - get_callback_data returns None (expired)
        mock_get_callback.return_value = None
        
        # Import function
        from Main.plugins.bot.help import send_plugin_execute_compressed
        
        # Execute
        await send_plugin_execute_compressed(self.mock_bot, self.mock_cb)
        
        # Verify error message was shown
        self.mock_cb.answer.assert_called_with("⚠️ Session expired, please refresh.", show_alert=True)
    
    @patch('Main.plugins.bot.help.get_callback_data')
    @patch('Main.plugins.bot.help.get_plugin_data')
    @patch('Main.plugins.bot.help.Altruix')
    @patch('os.path.exists')
    async def test_plugin_not_found_error(self, mock_exists, mock_altruix, mock_get_plugin, mock_get_callback):
        """Test error handling when plugin file not found."""
        # Setup
        mock_get_callback.return_value = "conf_send_pl#nonexistent_plugin#yes?page=0&si=0&cid=-1001234567890&mode=userbot"
        mock_exists.return_value = False  # Plugin file doesn't exist
        mock_altruix.clients = [self.mock_client1]
        mock_altruix.bot = self.mock_bot
        mock_altruix.log = Mock()
        mock_altruix.find_plugin_file = Mock(return_value=None)
        
        # Import function
        from Main.plugins.bot.help import send_plugin_execute_compressed
        
        # Execute
        await send_plugin_execute_compressed(self.mock_bot, self.mock_cb)
        
        # Verify error message was shown
        self.mock_cb.answer.assert_any_call(
            unittest.mock.ANY,  # Message contains "not found"
            show_alert=True
        )
    
    @patch('Main.plugins.bot.help.get_callback_data')
    @patch('Main.plugins.bot.help.get_plugin_data')
    @patch('Main.plugins.bot.help.Altruix')
    @patch('os.path.exists')
    async def test_answer_no_returns_to_help(self, mock_exists, mock_altruix, mock_get_plugin, mock_get_callback):
        """Test that answering 'no' returns to plugin help page."""
        # Setup - answer is 'no'
        mock_get_callback.return_value = "conf_send_pl#test_plugin#no?page=0&si=0&cid=-1001234567890&mode=userbot"
        mock_exists.return_value = True
        mock_altruix.clients = [self.mock_client1]
        mock_altruix.bot = self.mock_bot
        mock_altruix.log = Mock()
        mock_get_plugin.return_value = ("<b>Test Plugin Help</b>", Mock())
        
        # Import function
        from Main.plugins.bot.help import send_plugin_execute_compressed
        
        # Execute
        await send_plugin_execute_compressed(self.mock_bot, self.mock_cb)
        
        # Verify no document was sent
        self.mock_client1.send_document.assert_not_called()
        
        # Verify returned to help page
        self.mock_cb.edit_message_text.assert_called_once()
        call_args = self.mock_cb.edit_message_text.call_args
        self.assertIn("Test Plugin Help", call_args[0][0])


class TestCallbackDataParsing(unittest.IsolatedAsyncioTestCase):
    """Test callback data parsing logic."""
    
    async def test_parse_valid_callback_data(self):
        """Test parsing valid callback data."""
        import re
        
        callback_data = "conf_send_pl#test_plugin#yes?page=0&si=1&cid=-1001234567890&mode=userbot"
        pattern = r"conf_send_pl#([\w_ ]+)#(yes|no)\?page=(\d+)(?:&si=(-?\d+))?(?:&cid=(-?\d+))?(?:&mode=(\w+))?"
        
        match = re.match(pattern, callback_data)
        
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "test_plugin")
        self.assertEqual(match.group(2), "yes")
        self.assertEqual(match.group(3), "0")
        self.assertEqual(match.group(4), "1")
        self.assertEqual(match.group(5), "-1001234567890")
        self.assertEqual(match.group(6), "userbot")
    
    async def test_parse_callback_data_with_spaces(self):
        """Test parsing callback data with plugin names containing spaces."""
        import re
        
        callback_data = "conf_send_pl#test plugin name#yes?page=0&si=0&mode=userbot"
        pattern = r"conf_send_pl#([\w_ ]+)#(yes|no)\?page=(\d+)(?:&si=(-?\d+))?(?:&cid=(-?\d+))?(?:&mode=(\w+))?"
        
        match = re.match(pattern, callback_data)
        
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "test plugin name")


class TestIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration tests for complete workflow."""
    
    @patch('Main.plugins.bot.help.get_callback_data')
    @patch('Main.plugins.bot.help.get_plugin_data')
    @patch('Main.plugins.bot.help.Altruix')
    @patch('os.path.exists')
    async def test_complete_send_plugin_flow(self, mock_exists, mock_altruix, mock_get_plugin, mock_get_callback):
        """Test complete flow: button click → userbot sends → return to help."""
        # Setup
        mock_get_callback.return_value = "conf_send_pl#devtools#yes?page=0&si=0&cid=-1001234567890&mode=userbot"
        mock_exists.return_value = True
        
        mock_client = AsyncMock(spec=Client)
        mock_client.me = Mock()
        mock_client.me.id = 12345
        mock_client.send_document = AsyncMock()
        
        mock_altruix.clients = [mock_client]
        mock_altruix.bot = AsyncMock(spec=Client)
        mock_altruix.log = Mock()
        mock_get_plugin.return_value = ("<b>Devtools Help</b>", Mock())
        
        mock_cb = AsyncMock(spec=CallbackQuery)
        mock_cb.answer = AsyncMock()
        mock_cb.edit_message_text = AsyncMock()
        mock_cb.from_user = Mock(spec=User)
        mock_cb.from_user.id = 12345
        mock_cb.message = Mock(spec=Message)
        mock_cb.message.chat = Mock(spec=Chat)
        mock_cb.message.chat.id = -1001234567890
        mock_cb.matches = [Mock()]
        mock_cb.matches[0].group = Mock(return_value="abc123def456")
        
        # Import function
        from Main.plugins.bot.help import send_plugin_execute_compressed
        
        # Execute
        await send_plugin_execute_compressed(mock_altruix.bot, mock_cb)
        
        # Verify complete flow
        mock_get_callback.assert_called_once()  # 1. Get callback data
        mock_client.send_document.assert_called_once()  # 2. Send document via userbot
        mock_get_plugin.assert_called_once()  # 3. Get plugin help data
        mock_cb.edit_message_text.assert_called_once()  # 4. Return to help page
        
        # Verify userbot was used, not bot
        mock_altruix.bot.send_document.assert_not_called()


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
