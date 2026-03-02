"""
Test suite for evaldoc close button functionality.

Tests the fix for close button not working in inline mode.
"""

import unittest
import sys
import os
from unittest.mock import Mock, AsyncMock, patch
from pyrogram.types import CallbackQuery
from pyrogram import enums

# Add Main to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestEvaldocCloseButton(unittest.IsolatedAsyncioTestCase):
    """Test evaldoc close button functionality."""
    
    async def test_close_button_regular_message(self):
        """Test close button with regular message (not inline)."""
        from Main.plugins.userbot.devtools import safe_evaldoc_delete
        
        # Mock CallbackQuery with regular message
        mock_query = AsyncMock(spec=CallbackQuery)
        mock_query.message = AsyncMock()
        mock_query.message.delete = AsyncMock()
        mock_query.edit_message_text = AsyncMock()
        
        # Call delete function
        result = await safe_evaldoc_delete(mock_query)
        
        # Verify message.delete was called
        self.assertTrue(result)
        mock_query.message.delete.assert_called_once()
    
    async def test_close_button_inline_message(self):
        """Test close button with inline message (cb.message is None)."""
        from Main.plugins.userbot.devtools import safe_evaldoc_delete
        
        # Mock CallbackQuery with None message (inline mode)
        mock_query = AsyncMock(spec=CallbackQuery)
        mock_query.message = None  # Inline messages have None
        mock_query.edit_message_text = AsyncMock()
        
        # Call delete function
        result = await safe_evaldoc_delete(mock_query)
        
        # Verify edit_message_text was called (fallback for inline)
        self.assertTrue(result)
        mock_query.edit_message_text.assert_called_once()
        
        # Verify it shows "Menu Closed" message
        call_args = mock_query.edit_message_text.call_args
        self.assertIn("Menu Closed", call_args[0][0])
    
    async def test_close_button_delete_error(self):
        """Test close button when delete raises error."""
        from Main.plugins.userbot.devtools import safe_evaldoc_delete
        
        # Mock CallbackQuery that raises error on delete
        mock_query = AsyncMock(spec=CallbackQuery)
        mock_query.message = AsyncMock()
        mock_query.message.delete = AsyncMock(side_effect=Exception("Delete failed"))
        mock_query.edit_message_text = AsyncMock()
        
        # Call delete function
        result = await safe_evaldoc_delete(mock_query)
        
        # Should return False on error
        self.assertFalse(result)
    
    async def test_close_callback_handler(self):
        """Test close callback in main handler."""
        from Main.plugins.userbot.devtools import evaldoc_callback_handler
        
        # Mock CallbackQuery
        mock_query = AsyncMock(spec=CallbackQuery)
        mock_query.data = "evaldoc_close"
        mock_query.message = AsyncMock()
        mock_query.message.delete = AsyncMock()
        mock_query.answer = AsyncMock()
        
        # Mock Client
        mock_client = AsyncMock()
        
        # Call handler
        await evaldoc_callback_handler(mock_client, mock_query)
        
        # Verify message was deleted
        mock_query.message.delete.assert_called_once()
        
        # Verify answer was called
        mock_query.answer.assert_called_once()
    
    async def test_close_button_with_attribute_error(self):
        """Test close button handles AttributeError gracefully."""
        from Main.plugins.userbot.devtools import safe_evaldoc_delete
        
        # Mock CallbackQuery that raises AttributeError
        mock_query = AsyncMock(spec=CallbackQuery)
        mock_query.message = Mock()  # Not AsyncMock, will raise AttributeError
        mock_query.message.delete = Mock(side_effect=AttributeError("No delete method"))
        mock_query.edit_message_text = AsyncMock()
        
        # Call delete function
        result = await safe_evaldoc_delete(mock_query)
        
        # Should fallback to edit_message_text
        self.assertTrue(result)
        mock_query.edit_message_text.assert_called_once()


class TestEvaldocKeyboardCloseButton(unittest.TestCase):
    """Test close button in keyboard generation."""
    
    def test_close_button_in_keyboard(self):
        """Test that close button exists in all keyboards."""
        from Main.plugins.userbot.devtools import get_evaldoc_keyboard
        
        # Test all pages
        for page in range(1, 16):
            with self.subTest(page=page):
                keyboard = get_evaldoc_keyboard(page)
                
                # Get close button (row 3, button 1)
                close_button = keyboard.inline_keyboard[2][0]
                
                # Verify callback data
                self.assertEqual(close_button.callback_data, "evaldoc_close")
                
                # Verify text contains "Close"
                self.assertIn("Close", close_button.text)
    
    def test_close_button_callback_format(self):
        """Test close button callback data format."""
        from Main.plugins.userbot.devtools import get_evaldoc_keyboard
        
        keyboard = get_evaldoc_keyboard(5)
        close_button = keyboard.inline_keyboard[2][0]
        
        # Verify callback starts with evaldoc_
        self.assertTrue(close_button.callback_data.startswith("evaldoc_"))
        
        # Verify exact callback
        self.assertEqual(close_button.callback_data, "evaldoc_close")


if __name__ == '__main__':
    unittest.main(verbosity=2)
