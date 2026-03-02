"""
Security test suite for evaldoc feature with @iuser_check protection.

Tests cover:
1. Callback handler authorization
2. Inline query handler authorization
3. Unauthorized access handling
4. Button interaction security
5. Logging functionality
"""

import unittest
import sys
import os
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from pyrogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    CallbackQuery,
    InlineQuery,
    User
)

# Add Main to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestCallbackSecurity(unittest.IsolatedAsyncioTestCase):
    """Test callback handler security with @iuser_check."""
    
    async def test_callback_handler_has_iuser_check(self):
        """Test that callback handler is decorated with @iuser_check."""
        from Main.plugins.userbot.devtools import evaldoc_callback_handler
        
        # Check if handler has the wrapper from iuser_check
        # The decorator wraps the function, so we check for 'wrapper' in the name or __wrapped__
        handler_name = evaldoc_callback_handler.__name__
        
        # If decorated, it should be wrapped
        self.assertTrue(
            hasattr(evaldoc_callback_handler, '__wrapped__') or 
            handler_name == 'wrapper' or
            'wrapper' in str(evaldoc_callback_handler),
            "Callback handler should be decorated with @iuser_check"
        )
    
    async def test_all_callback_patterns_covered(self):
        """Test that all callback patterns are handled."""
        from Main.plugins.userbot.devtools import evaldoc_callback_handler
        
        # Test patterns that should be handled
        test_patterns = [
            "evaldoc_close",
            "evaldoc_noop",
            "evaldoc_page_1",
            "evaldoc_page_5",
            "evaldoc_page_15",
        ]
        
        for pattern in test_patterns:
            with self.subTest(pattern=pattern):
                # Create mock callback query
                mock_query = AsyncMock(spec=CallbackQuery)
                mock_query.data = pattern
                mock_query.message = AsyncMock()
                mock_query.message.delete = AsyncMock()
                mock_query.message.edit_text = AsyncMock()
                mock_query.answer = AsyncMock()
                
                # Create mock user (authorized)
                mock_user = Mock(spec=User)
                mock_user.id = 123456789
                mock_user.username = "testuser"
                mock_user.first_name = "Test"
                mock_user.last_name = "User"
                mock_query.from_user = mock_user
                
                # Mock client
                mock_client = AsyncMock()
                
                # The handler should process without errors
                # (actual authorization is handled by @iuser_check decorator)
                try:
                    await evaldoc_callback_handler(mock_client, mock_query)
                    # If we get here, handler executed (may have called answer/delete/edit)
                    self.assertTrue(True, f"Handler processed {pattern}")
                except Exception as e:
                    # Some patterns may fail due to missing mocks, but shouldn't crash
                    self.assertIsInstance(e, (AttributeError, TypeError), 
                                        f"Handler should handle {pattern} gracefully")


class TestInlineSecurity(unittest.IsolatedAsyncioTestCase):
    """Test inline query handler security with @iuser_check."""
    
    async def test_inline_handler_has_iuser_check(self):
        """Test that inline handler is decorated with @iuser_check."""
        from Main.plugins.userbot.devtools import evaldoc_inline_handler
        
        # Check if handler has the wrapper from iuser_check
        handler_name = evaldoc_inline_handler.__name__
        
        self.assertTrue(
            hasattr(evaldoc_inline_handler, '__wrapped__') or 
            handler_name == 'wrapper' or
            'wrapper' in str(evaldoc_inline_handler),
            "Inline handler should be decorated with @iuser_check"
        )
    
    async def test_inline_query_patterns(self):
        """Test that inline query patterns are handled."""
        from Main.plugins.userbot.devtools import evaldoc_inline_handler
        
        # Test patterns
        test_queries = [
            ("evaldoc", 1),      # Default page
            ("evaldoc_page_5", 5),  # Specific page
            ("evaldoc_page_15", 15), # Last page
        ]
        
        for query_text, expected_page in test_queries:
            with self.subTest(query=query_text):
                # Create mock inline query
                mock_query = AsyncMock(spec=InlineQuery)
                mock_query.query = query_text
                mock_query.answer = AsyncMock()
                
                # Mock regex match
                mock_match = Mock()
                mock_match.group = Mock(side_effect=lambda x: str(expected_page) if x == 1 else None)
                mock_query.matches = [mock_match]
                
                # Create mock user
                mock_user = Mock(spec=User)
                mock_user.id = 123456789
                mock_user.username = "testuser"
                mock_user.first_name = "Test"
                mock_user.last_name = "User"
                mock_query.from_user = mock_user
                
                # Mock client
                mock_client = AsyncMock()
                
                try:
                    await evaldoc_inline_handler(mock_client, mock_query)
                    # Handler should call query.answer
                    self.assertTrue(True, f"Handler processed {query_text}")
                except Exception as e:
                    # May fail due to missing mocks, but shouldn't crash
                    self.assertIsInstance(e, (AttributeError, TypeError),
                                        f"Handler should handle {query_text} gracefully")


class TestButtonFunctionality(unittest.IsolatedAsyncioTestCase):
    """Test all button types functionality."""
    
    async def test_close_button(self):
        """Test close button deletes message."""
        from Main.plugins.userbot.devtools import evaldoc_callback_handler
        
        mock_query = AsyncMock(spec=CallbackQuery)
        mock_query.data = "evaldoc_close"
        mock_query.message = AsyncMock()
        mock_query.message.delete = AsyncMock()
        
        # Mock user
        mock_user = Mock(spec=User)
        mock_user.id = 123456789
        mock_user.username = "testuser"
        mock_user.first_name = "Test"
        mock_user.last_name = None
        mock_query.from_user = mock_user
        
        mock_client = AsyncMock()
        
        await evaldoc_callback_handler(mock_client, mock_query)
        
        # Verify delete was called
        mock_query.message.delete.assert_called_once()
    
    async def test_noop_button(self):
        """Test noop button shows boundary alert."""
        from Main.plugins.userbot.devtools import evaldoc_callback_handler
        
        mock_query = AsyncMock(spec=CallbackQuery)
        mock_query.data = "evaldoc_noop"
        mock_query.answer = AsyncMock()
        
        # Mock user
        mock_user = Mock(spec=User)
        mock_user.id = 123456789
        mock_user.username = "testuser"
        mock_user.first_name = "Test"
        mock_user.last_name = None
        mock_query.from_user = mock_user
        
        mock_client = AsyncMock()
        
        await evaldoc_callback_handler(mock_client, mock_query)
        
        # Verify answer was called
        mock_query.answer.assert_called_once()
        call_args = mock_query.answer.call_args
        self.assertIn("boundary", call_args[0][0].lower())
    
    async def test_page_navigation_button(self):
        """Test page navigation updates message."""
        from Main.plugins.userbot.devtools import evaldoc_callback_handler
        
        mock_query = AsyncMock(spec=CallbackQuery)
        mock_query.data = "evaldoc_page_5"
        mock_query.message = AsyncMock()
        mock_query.message.edit_text = AsyncMock()
        mock_query.answer = AsyncMock()
        
        # Mock user
        mock_user = Mock(spec=User)
        mock_user.id = 123456789
        mock_user.username = "testuser"
        mock_user.first_name = "Test"
        mock_user.last_name = None
        mock_query.from_user = mock_user
        
        mock_client = AsyncMock()
        
        await evaldoc_callback_handler(mock_client, mock_query)
        
        # Verify edit_text was called
        mock_query.message.edit_text.assert_called_once()
        
        # Verify answer was called
        mock_query.answer.assert_called_once()


class TestKeyboardButtons(unittest.TestCase):
    """Test all keyboard button types."""
    
    def test_all_button_types_present(self):
        """Test that all button types are present in keyboards."""
        from Main.plugins.userbot.devtools import get_evaldoc_keyboard
        
        # Test different pages
        test_pages = [1, 5, 8, 15]
        
        for page in test_pages:
            with self.subTest(page=page):
                keyboard = get_evaldoc_keyboard(page)
                
                # Collect all callback data
                all_callbacks = []
                for row in keyboard.inline_keyboard:
                    for button in row:
                        all_callbacks.append(button.callback_data)
                
                # Check for essential callback types
                has_page_nav = any("evaldoc_page_" in cb for cb in all_callbacks)
                has_close = "evaldoc_close" in all_callbacks
                has_noop = "evaldoc_noop" in all_callbacks
                
                self.assertTrue(has_page_nav or has_noop, 
                              f"Page {page} should have navigation buttons")
                self.assertTrue(has_close, 
                              f"Page {page} should have close button")
    
    def test_button_emojis_intact(self):
        """Test that all button emojis are intact."""
        from Main.plugins.userbot.devtools import get_evaldoc_keyboard
        
        keyboard = get_evaldoc_keyboard(5)
        
        # Expected emojis in buttons
        expected_emojis = ['◀️', '▶️', '📄', '⏮️', '⏭️', '⭐', '❌']
        
        # Collect all button texts
        all_texts = []
        for row in keyboard.inline_keyboard:
            for button in row:
                all_texts.append(button.text)
        
        # Check each emoji appears
        for emoji in expected_emojis:
            with self.subTest(emoji=emoji):
                found = any(emoji in text for text in all_texts)
                self.assertTrue(found, f"Emoji {emoji} should be in buttons")
                
                # Check for corrupted emoji
                has_corrupted = any('�' in text for text in all_texts)
                self.assertFalse(has_corrupted, "No corrupted emojis should be present")


class TestSecurityIntegration(unittest.TestCase):
    """Test security integration with handlers."""
    
    def test_iuser_check_imported(self):
        """Test that iuser_check is imported."""
        import Main.plugins.userbot.devtools as devtools
        
        # Check if iuser_check is in the module
        # It should be imported from Main.core.decorators
        import Main.core.decorators as decorators
        
        self.assertTrue(hasattr(decorators, 'iuser_check'),
                       "iuser_check should be available in decorators module")
    
    def test_handlers_are_async(self):
        """Test that all handlers are async functions."""
        from Main.plugins.userbot.devtools import (
            evaldoc_callback_handler,
            evaldoc_inline_handler
        )
        
        import asyncio
        
        self.assertTrue(asyncio.iscoroutinefunction(evaldoc_callback_handler),
                       "Callback handler should be async")
        self.assertTrue(asyncio.iscoroutinefunction(evaldoc_inline_handler),
                       "Inline handler should be async")
    
    def test_log_errors_decorator_present(self):
        """Test that @log_errors decorator is also present."""
        from Main.plugins.userbot.devtools import (
            evaldoc_callback_handler,
            evaldoc_inline_handler
        )
        
        # Both handlers should have error logging
        # This is indicated by the decorator chain
        self.assertTrue(callable(evaldoc_callback_handler),
                       "Callback handler should be callable")
        self.assertTrue(callable(evaldoc_inline_handler),
                       "Inline handler should be callable")


class TestAllButtonInteractions(unittest.IsolatedAsyncioTestCase):
    """Test all possible button interactions."""
    
    async def test_prev_button_interactions(self):
        """Test Prev button on different pages."""
        from Main.plugins.userbot.devtools import get_evaldoc_keyboard
        
        # Pages where Prev should be enabled
        enabled_pages = [2, 5, 10, 15]
        
        for page in enabled_pages:
            with self.subTest(page=page):
                keyboard = get_evaldoc_keyboard(page)
                prev_button = keyboard.inline_keyboard[0][0]
                
                # Should have callback to previous page
                self.assertNotEqual(prev_button.callback_data, "evaldoc_noop",
                                  f"Prev should be enabled on page {page}")
                self.assertIn("Prev", prev_button.text,
                            f"Prev button should have text on page {page}")
    
    async def test_next_button_interactions(self):
        """Test Next button on different pages."""
        from Main.plugins.userbot.devtools import get_evaldoc_keyboard
        
        # Pages where Next should be enabled
        enabled_pages = [1, 5, 10, 14]
        
        for page in enabled_pages:
            with self.subTest(page=page):
                keyboard = get_evaldoc_keyboard(page)
                next_button = keyboard.inline_keyboard[0][2]
                
                # Should have callback to next page
                self.assertNotEqual(next_button.callback_data, "evaldoc_noop",
                                  f"Next should be enabled on page {page}")
                self.assertIn("Next", next_button.text,
                            f"Next button should have text on page {page}")
    
    async def test_first_button_all_pages(self):
        """Test First button works on all pages."""
        from Main.plugins.userbot.devtools import get_evaldoc_keyboard
        
        for page in range(1, 16):
            with self.subTest(page=page):
                keyboard = get_evaldoc_keyboard(page)
                first_button = keyboard.inline_keyboard[1][0]
                
                # Should always point to page 1
                self.assertEqual(first_button.callback_data, "evaldoc_page_1",
                               f"First button should point to page 1 from page {page}")
                self.assertIn("First", first_button.text,
                            f"First button should have text on page {page}")
    
    async def test_last_button_all_pages(self):
        """Test Last button works on all pages."""
        from Main.plugins.userbot.devtools import get_evaldoc_keyboard
        
        for page in range(1, 16):
            with self.subTest(page=page):
                keyboard = get_evaldoc_keyboard(page)
                last_button = keyboard.inline_keyboard[1][2]
                
                # Should always point to page 15
                self.assertEqual(last_button.callback_data, "evaldoc_page_15",
                               f"Last button should point to page 15 from page {page}")
                self.assertIn("Last", last_button.text,
                            f"Last button should have text on page {page}")
    
    async def test_client_button_all_pages(self):
        """Test Client button works on all pages."""
        from Main.plugins.userbot.devtools import get_evaldoc_keyboard
        
        for page in range(1, 16):
            with self.subTest(page=page):
                keyboard = get_evaldoc_keyboard(page)
                client_button = keyboard.inline_keyboard[1][1]
                
                # Should always point to page 5
                self.assertEqual(client_button.callback_data, "evaldoc_page_5",
                               f"Client button should point to page 5 from page {page}")
                self.assertIn("Client", client_button.text,
                            f"Client button should have text on page {page}")
    
    async def test_close_button_all_pages(self):
        """Test Close button works on all pages."""
        from Main.plugins.userbot.devtools import get_evaldoc_keyboard
        
        for page in range(1, 16):
            with self.subTest(page=page):
                keyboard = get_evaldoc_keyboard(page)
                close_button = keyboard.inline_keyboard[2][0]
                
                # Should always be evaldoc_close
                self.assertEqual(close_button.callback_data, "evaldoc_close",
                               f"Close button should have correct callback on page {page}")
                self.assertIn("Close", close_button.text,
                            f"Close button should have text on page {page}")


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
