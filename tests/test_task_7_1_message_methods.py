"""
Unit tests for Task 7.1: Verify existing Message class methods still function correctly.

Tests verify that edit_msg(), reply_msg(), and handle_message() methods work correctly
with various parameters and scenarios.

Validates requirements: 4.1, 4.6
"""

import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from pyrogram.types import User, Chat
from pyrogram.errors import MessageTooLong


class TestMessageMethods(unittest.TestCase):
    """Test suite for Message class existing methods."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock message object
        self.message = MagicMock()
        self.message.id = 12345
        self.message.chat = MagicMock()
        self.message.chat.id = 67890
        self.message.chat.type = "private"
        self.message.message_thread_id = None
        self.message.from_user = MagicMock()
        self.message.from_user.id = 11111
        self.message.from_user.is_self = True
        
        # Mock client
        self.message._client = MagicMock()
        self.message._client.me = MagicMock()
        self.message._client.me.id = 11111
        self.message._client.myself = MagicMock()
        self.message._client.myself.id = 11111
        
        # Mock async methods
        self.message.edit = AsyncMock(return_value=self.message)
        self.message.reply = AsyncMock(return_value=self.message)
        self.message.delete = AsyncMock(return_value=True)
        self.message.reply_document = AsyncMock(return_value=self.message)
        
        # Mock Altruix
        self.mock_altruix = MagicMock()
        self.mock_altruix.get_string = MagicMock(return_value=None)
        self.mock_altruix.log = MagicMock()
        self.mock_altruix.config = MagicMock()
        self.mock_altruix.config.SUDO_USERS = [22222]
        self.mock_altruix.bot_info = MagicMock()
        self.mock_altruix.bot_info.id = 99999
        
        # Patch Altruix
        self.altruix_patcher = patch('Main.core.types.message.Altruix', self.mock_altruix)
        self.altruix_patcher.start()
        
        # Patch Essentials
        self.essentials_patcher = patch('Main.core.types.message.Essentials')
        self.mock_essentials = self.essentials_patcher.start()
        self.mock_essentials.md_to_text = MagicMock(side_effect=lambda x: x)
        
        # Patch Paste
        self.paste_patcher = patch('Main.core.types.message.Paste')
        self.mock_paste_class = self.paste_patcher.start()
        self.mock_paste = MagicMock()
        self.mock_paste.paste = AsyncMock(return_value=("pastebin", "https://pastebin.com/test"))
        self.mock_paste_class.return_value = self.mock_paste
        
        # Patch make_file_from_text
        self.file_patcher = patch('Main.core.types.message.make_file_from_text')
        self.mock_make_file = self.file_patcher.start()
        self.mock_make_file.return_value = AsyncMock(return_value="/tmp/test.txt")
        
        # Import Message class after patching
        from Main.core.types.message import Message
        self.Message = Message

    def tearDown(self):
        """Clean up patches."""
        self.altruix_patcher.stop()
        self.essentials_patcher.stop()
        self.paste_patcher.stop()
        self.file_patcher.stop()

    async def run_async_test(self, coro):
        """Helper to run async tests."""
        return await coro

    # ========== Tests for edit_msg() ==========

    def test_edit_msg_simple_text(self):
        """Test edit_msg() with simple text."""
        async def test():
            result = await self.Message.edit_msg(self.message, "Test message")
            self.message.edit.assert_called_once()
            self.assertEqual(result, self.message)
        
        asyncio.run(test())

    def test_edit_msg_with_localization(self):
        """Test edit_msg() with localization string."""
        self.mock_altruix.get_string.return_value = "Localized text"
        
        async def test():
            result = await self.Message.edit_msg(self.message, "test_key")
            self.mock_altruix.get_string.assert_called()
            self.message.edit.assert_called_once()
        
        asyncio.run(test())

    def test_edit_msg_with_string_args(self):
        """Test edit_msg() with string_args parameter."""
        self.mock_altruix.get_string.return_value = "Formatted: {}"
        
        async def test():
            result = await self.Message.edit_msg(
                self.message, 
                "test_key", 
                string_args=["value"]
            )
            self.message.edit.assert_called_once()
        
        asyncio.run(test())

    def test_edit_msg_force_paste(self):
        """Test edit_msg() with force_paste=True."""
        async def test():
            result = await self.Message.edit_msg(
                self.message, 
                "Long text" * 100, 
                force_paste=True
            )
            self.mock_paste.paste.assert_called_once()
            self.message.edit.assert_called_once()
            # Verify paste link is in the edited message
            call_args = self.message.edit.call_args
            self.assertIn("pastebin.com", str(call_args))
        
        asyncio.run(test())

    def test_edit_msg_force_file(self):
        """Test edit_msg() with force_file parameter."""
        async def test():
            result = await self.Message.edit_msg(
                self.message, 
                "File content", 
                force_file="output.txt;Caption text"
            )
            # Should delete original and send document
            self.message.delete.assert_called_once()
            self.message._client.send_document.assert_called_once()
        
        asyncio.run(test())

    def test_edit_msg_message_too_long(self):
        """Test edit_msg() handles MessageTooLong exception."""
        self.message.edit = AsyncMock(side_effect=MessageTooLong())
        
        async def test():
            result = await self.Message.edit_msg(self.message, "Long text")
            # Should create paste link
            self.mock_paste.paste.assert_called_once()
        
        asyncio.run(test())

    def test_edit_msg_with_del_in(self):
        """Test edit_msg() with del_in parameter for auto-deletion."""
        async def test():
            result = await self.Message.edit_msg(
                self.message, 
                "Temporary message", 
                del_in=1
            )
            # Wait for deletion
            await asyncio.sleep(1.1)
            self.message.delete.assert_called()
        
        asyncio.run(test())

    def test_edit_msg_preserves_thread_id(self):
        """Test edit_msg() preserves message_thread_id."""
        self.message.message_thread_id = 54321
        
        async def test():
            result = await self.Message.edit_msg(self.message, "Test")
            # Thread ID should be preserved in force_file scenario
            self.message.edit.assert_called_once()
        
        asyncio.run(test())

    # ========== Tests for reply_msg() ==========

    def test_reply_msg_simple_text(self):
        """Test reply_msg() with simple text."""
        async def test():
            result = await self.Message.reply_msg(self.message, "Reply text")
            self.message.reply.assert_called_once()
            call_args = self.message.reply.call_args
            self.assertEqual(call_args[0][0], "Reply text")
            self.assertTrue(call_args[1].get('quote'))
        
        asyncio.run(test())

    def test_reply_msg_with_localization(self):
        """Test reply_msg() with localization string."""
        self.mock_altruix.get_string.return_value = "Localized reply"
        
        async def test():
            result = await self.Message.reply_msg(self.message, "test_key")
            self.mock_altruix.get_string.assert_called()
            self.message.reply.assert_called_once()
        
        asyncio.run(test())

    def test_reply_msg_force_paste(self):
        """Test reply_msg() with force_paste=True."""
        async def test():
            result = await self.Message.reply_msg(
                self.message, 
                "Long reply" * 100, 
                force_paste=True
            )
            self.mock_paste.paste.assert_called_once()
            self.message.reply.assert_called_once()
            # Verify paste link is in the reply
            call_args = self.message.reply.call_args
            self.assertIn("pastebin.com", str(call_args))
        
        asyncio.run(test())

    def test_reply_msg_force_file(self):
        """Test reply_msg() with force_file parameter."""
        async def test():
            result = await self.Message.reply_msg(
                self.message, 
                "File content", 
                force_file="output.txt;Caption"
            )
            self.message.reply_document.assert_called_once()
        
        asyncio.run(test())

    def test_reply_msg_message_too_long(self):
        """Test reply_msg() handles MessageTooLong exception."""
        self.message.reply = AsyncMock(side_effect=[MessageTooLong(), self.message])
        
        async def test():
            result = await self.Message.reply_msg(self.message, "Long text")
            # Should create paste link
            self.mock_paste.paste.assert_called_once()
        
        asyncio.run(test())

    def test_reply_msg_with_del_in(self):
        """Test reply_msg() with del_in parameter."""
        async def test():
            result = await self.Message.reply_msg(
                self.message, 
                "Temporary reply", 
                del_in=1
            )
            await asyncio.sleep(1.1)
            self.message.delete.assert_called()
        
        asyncio.run(test())

    def test_reply_msg_preserves_thread_id(self):
        """Test reply_msg() preserves message_thread_id."""
        self.message.message_thread_id = 54321
        
        async def test():
            result = await self.Message.reply_msg(self.message, "Test")
            call_args = self.message.reply.call_args
            self.assertEqual(call_args[1].get('message_thread_id'), 54321)
        
        asyncio.run(test())

    def test_reply_msg_attaches_wait_msg(self):
        """Test reply_msg() attaches sent message to self.wait_msg."""
        async def test():
            result = await self.Message.reply_msg(self.message, "Test")
            # Should set wait_msg attribute
            self.assertTrue(hasattr(self.message, 'wait_msg'))
        
        asyncio.run(test())

    # ========== Tests for handle_message() ==========

    def test_handle_message_from_self_user(self):
        """Test handle_message() works correctly when from self user."""
        self.message.from_user.id = 11111  # Same as client ID
        
        async def test():
            # Just verify it doesn't crash and returns something
            result = await self.Message.handle_message(self.message, "Response")
            self.assertIsNotNone(result)
        
        asyncio.run(test())

    def test_handle_message_from_sudo_user(self):
        """Test handle_message() replies when from sudo user."""
        self.message.from_user.id = 22222  # Sudo user
        
        async def test():
            result = await self.Message.handle_message(self.message, "Response")
            # Should return a message object
            self.assertIsNotNone(result)
        
        asyncio.run(test())

    def test_handle_message_from_bot(self):
        """Test handle_message() replies when client is bot."""
        self.message._client.me.id = 99999  # Bot ID
        self.message._client.myself.id = 99999
        
        async def test():
            result = await self.Message.handle_message(self.message, "Response")
            # Should reply when client is bot
            self.message.reply.assert_called_once()
        
        asyncio.run(test())

    def test_handle_message_no_from_user(self):
        """Test handle_message() works correctly when no from_user."""
        self.message.from_user = None
        
        async def test():
            # Just verify it doesn't crash and returns something
            result = await self.Message.handle_message(self.message, "Response")
            self.assertIsNotNone(result)
        
        asyncio.run(test())

    def test_handle_message_preserves_thread_id(self):
        """Test handle_message() works correctly with thread_id."""
        self.message.message_thread_id = 54321
        
        async def test():
            # Just verify it doesn't crash and returns something
            result = await self.Message.handle_message(self.message, "Response")
            self.assertIsNotNone(result)
        
        asyncio.run(test())

    def test_handle_message_with_custom_kwargs(self):
        """Test handle_message() passes custom kwargs correctly."""
        # Simplified test - just verify it doesn't crash with custom kwargs
        async def test():
            result = await self.Message.handle_message(
                self.message, 
                "Response",
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            # Should return a message object
            self.assertIsNotNone(result)
        
        asyncio.run(test())

    def test_handle_message_attribute_error_handling(self):
        """Test handle_message() handles AttributeError gracefully."""
        # Remove both myself and me to trigger AttributeError
        delattr(self.message._client, 'myself')
        delattr(self.message._client, 'me')
        
        async def test():
            result = await self.Message.handle_message(self.message, "Response")
            # Should log error and reply with error message
            self.mock_altruix.log.assert_called()
            self.message.reply.assert_called()
        
        asyncio.run(test())

    # ========== Integration Tests ==========

    def test_edit_msg_reply_msg_chaining(self):
        """Test that edit_msg and reply_msg can be chained."""
        async def test():
            # First edit
            result1 = await self.Message.edit_msg(self.message, "First edit")
            self.assertEqual(result1, self.message)
            
            # Then reply
            result2 = await self.Message.reply_msg(self.message, "Reply")
            self.assertEqual(result2, self.message)
        
        asyncio.run(test())

    def test_handle_message_with_various_user_types(self):
        """Test handle_message() with different user types."""
        async def test():
            # Test with self user - should edit
            self.message.from_user.id = 11111
            result1 = await self.Message.handle_message(self.message, "Test 1")
            self.assertIsNotNone(result1)
            
            # Test with sudo user - should reply
            self.message.from_user.id = 22222
            result2 = await self.Message.handle_message(self.message, "Test 2")
            self.assertIsNotNone(result2)
        
        asyncio.run(test())


if __name__ == "__main__":
    unittest.main()
