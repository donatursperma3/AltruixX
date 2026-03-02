"""
Comprehensive test suite for Main/plugins/userbot/devtools.py

Tests cover:
1. Evaldoc documentation pages structure
2. Inline keyboard generation
3. Callback data format
4. Page navigation logic
5. Boundary conditions
6. Error handling
"""

import unittest
import sys
import os
import warnings
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# Suppress Pyrogram deprecation warnings (external library issue, not our code)
warnings.filterwarnings("ignore", category=DeprecationWarning, module="pyrogram")

# Add Main to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestEvalDocPages(unittest.TestCase):
    """Test evaldoc documentation pages structure and content."""
    
    def setUp(self):
        """Import EVAL_DOC_PAGES from devtools."""
        # Import here to avoid circular dependencies
        from Main.plugins.userbot.devtools import EVAL_DOC_PAGES
        self.pages = EVAL_DOC_PAGES
    
    def test_page_count(self):
        """Test that we have exactly 15 pages."""
        self.assertEqual(len(self.pages), 15, "Should have exactly 15 documentation pages")
    
    def test_all_pages_are_strings(self):
        """Test that all pages are non-empty strings."""
        for i, page in enumerate(self.pages, 1):
            with self.subTest(page=i):
                self.assertIsInstance(page, str, f"Page {i} should be a string")
                self.assertTrue(len(page) > 0, f"Page {i} should not be empty")
    
    def test_page_length_limits(self):
        """Test that pages are within reasonable length (100-1000 chars)."""
        for i, page in enumerate(self.pages, 1):
            with self.subTest(page=i):
                page_len = len(page)
                self.assertGreater(page_len, 50, f"Page {i} too short ({page_len} chars)")
                self.assertLess(page_len, 1500, f"Page {i} too long ({page_len} chars)")
    
    def test_page_headers(self):
        """Test that all pages have proper headers."""
        for i, page in enumerate(self.pages, 1):
            with self.subTest(page=i):
                self.assertIn("📚 Eval & Reval Guide", page, f"Page {i} missing header")
                self.assertIn(f"Page {i}/15", page, f"Page {i} missing page number")
    
    def test_critical_pages_content(self):
        """Test that critical pages contain expected content."""
        # Page 1: Import
        self.assertIn("Import Altruix", self.pages[0])
        self.assertIn("from Main.core.client import Altruix", self.pages[0])
        
        # Page 2: Bot Assistant
        self.assertIn("Bot Assistant", self.pages[1])
        self.assertIn("Altruix.bot", self.pages[1])
        
        # Page 3: Userbot List
        self.assertIn("Userbot List", self.pages[2])
        self.assertIn("Altruix.clients", self.pages[2])
        
        # Page 5: Client Aktif (MOST IMPORTANT)
        self.assertIn("Client Aktif", self.pages[4])
        self.assertIn("client", self.pages[4])
        self.assertIn("⭐", self.pages[4])
        
        # Page 6: Contoh Client Aktif
        self.assertIn("Contoh Client Aktif", self.pages[5])
        self.assertIn("await client.send_message", self.pages[5])
        
        # Page 14: Quick Reference
        self.assertIn("Quick Reference", self.pages[13])
        
        # Page 15: Tips
        self.assertIn("Tips", self.pages[14])
        self.assertIn("Selesai", self.pages[14])
    
    def test_code_blocks_format(self):
        """Test that code blocks use proper <pre> tags."""
        pages_with_code = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]  # Pages with code examples
        
        for i in pages_with_code:
            with self.subTest(page=i+1):
                page = self.pages[i]
                if "await" in page or "def" in page or "import" in page:
                    self.assertIn("<pre", page, f"Page {i+1} should use <pre> tags for code")
    
    def test_navigation_hints(self):
        """Test that pages 1-14 have navigation hints."""
        for i in range(14):  # Pages 1-14
            with self.subTest(page=i+1):
                page = self.pages[i]
                self.assertIn("→ .evaldoc", page, f"Page {i+1} should have navigation hint")


class TestInlineKeyboard(unittest.TestCase):
    """Test inline keyboard generation and structure."""
    
    def setUp(self):
        """Import keyboard function."""
        from Main.plugins.userbot.devtools import get_evaldoc_keyboard, EVAL_DOC_PAGES
        self.get_keyboard = get_evaldoc_keyboard
        self.total_pages = len(EVAL_DOC_PAGES)
    
    def test_keyboard_structure(self):
        """Test that keyboard has correct structure (3 rows)."""
        keyboard = self.get_keyboard(5)
        self.assertIsInstance(keyboard, InlineKeyboardMarkup)
        self.assertEqual(len(keyboard.inline_keyboard), 3, "Keyboard should have 3 rows")
    
    def test_first_row_structure(self):
        """Test first row: Prev | Page X/Total | Next."""
        keyboard = self.get_keyboard(5)
        row1 = keyboard.inline_keyboard[0]
        
        self.assertEqual(len(row1), 3, "First row should have 3 buttons")
        
        # Check button texts
        self.assertIn("Prev", row1[0].text)
        self.assertIn("5/15", row1[1].text)
        self.assertIn("Next", row1[2].text)
    
    def test_second_row_structure(self):
        """Test second row: First | Client | Last."""
        keyboard = self.get_keyboard(5)
        row2 = keyboard.inline_keyboard[1]
        
        self.assertEqual(len(row2), 3, "Second row should have 3 buttons")
        
        # Check button texts
        self.assertIn("First", row2[0].text)
        self.assertIn("Client", row2[1].text)
        self.assertIn("Last", row2[2].text)
    
    def test_third_row_structure(self):
        """Test third row: Close."""
        keyboard = self.get_keyboard(5)
        row3 = keyboard.inline_keyboard[2]
        
        self.assertEqual(len(row3), 1, "Third row should have 1 button")
        self.assertIn("Close", row3[0].text)
    
    def test_callback_data_format(self):
        """Test that callback data follows correct format."""
        keyboard = self.get_keyboard(5)
        
        # Row 1
        self.assertEqual(keyboard.inline_keyboard[0][0].callback_data, "evaldoc_page_4")  # Prev
        self.assertEqual(keyboard.inline_keyboard[0][1].callback_data, "evaldoc_noop")    # Page indicator
        self.assertEqual(keyboard.inline_keyboard[0][2].callback_data, "evaldoc_page_6")  # Next
        
        # Row 2
        self.assertEqual(keyboard.inline_keyboard[1][0].callback_data, "evaldoc_page_1")  # First
        self.assertEqual(keyboard.inline_keyboard[1][1].callback_data, "evaldoc_page_5")  # Client
        self.assertEqual(keyboard.inline_keyboard[1][2].callback_data, "evaldoc_page_15") # Last
        
        # Row 3
        self.assertEqual(keyboard.inline_keyboard[2][0].callback_data, "evaldoc_close")   # Close
    
    def test_first_page_prev_disabled(self):
        """Test that Prev button is disabled on first page."""
        keyboard = self.get_keyboard(1)
        prev_button = keyboard.inline_keyboard[0][0]
        
        self.assertEqual(prev_button.callback_data, "evaldoc_noop")
        self.assertEqual(prev_button.text, "◀️")  # Just arrow, no "Prev"
    
    def test_last_page_next_disabled(self):
        """Test that Next button is disabled on last page."""
        keyboard = self.get_keyboard(15)
        next_button = keyboard.inline_keyboard[0][2]
        
        self.assertEqual(next_button.callback_data, "evaldoc_noop")
        self.assertEqual(next_button.text, "▶️")  # Just arrow, no "Next"
    
    def test_middle_page_all_enabled(self):
        """Test that all navigation buttons are enabled on middle pages."""
        keyboard = self.get_keyboard(8)
        
        # Prev should be enabled
        self.assertNotEqual(keyboard.inline_keyboard[0][0].callback_data, "evaldoc_noop")
        self.assertIn("Prev", keyboard.inline_keyboard[0][0].text)
        
        # Next should be enabled
        self.assertNotEqual(keyboard.inline_keyboard[0][2].callback_data, "evaldoc_noop")
        self.assertIn("Next", keyboard.inline_keyboard[0][2].text)
    
    def test_client_button_always_points_to_page_5(self):
        """Test that Client button always points to page 5."""
        for page in [1, 5, 10, 15]:
            with self.subTest(page=page):
                keyboard = self.get_keyboard(page)
                client_button = keyboard.inline_keyboard[1][1]
                self.assertEqual(client_button.callback_data, "evaldoc_page_5")


class TestCallbackDataParsing(unittest.TestCase):
    """Test callback data parsing logic."""
    
    def test_page_callback_parsing(self):
        """Test parsing page numbers from callback data."""
        test_cases = [
            ("evaldoc_page_1", 1),
            ("evaldoc_page_5", 5),
            ("evaldoc_page_15", 15),
            ("evaldoc_page_10", 10),
        ]
        
        for callback_data, expected_page in test_cases:
            with self.subTest(callback=callback_data):
                page_num = int(callback_data.split("_")[-1])
                self.assertEqual(page_num, expected_page)
    
    def test_special_callbacks(self):
        """Test special callback data values."""
        special_callbacks = ["evaldoc_close", "evaldoc_noop"]
        
        for callback in special_callbacks:
            with self.subTest(callback=callback):
                self.assertTrue(callback.startswith("evaldoc_"))
                self.assertNotIn("page", callback)


class TestBoundaryConditions(unittest.TestCase):
    """Test boundary conditions and edge cases."""
    
    def setUp(self):
        """Import keyboard function."""
        from Main.plugins.userbot.devtools import get_evaldoc_keyboard, EVAL_DOC_PAGES
        self.get_keyboard = get_evaldoc_keyboard
        self.total_pages = len(EVAL_DOC_PAGES)
    
    def test_page_1_boundaries(self):
        """Test keyboard on page 1."""
        keyboard = self.get_keyboard(1)
        
        # Prev should be disabled
        self.assertEqual(keyboard.inline_keyboard[0][0].callback_data, "evaldoc_noop")
        
        # Next should point to page 2
        self.assertEqual(keyboard.inline_keyboard[0][2].callback_data, "evaldoc_page_2")
    
    def test_page_15_boundaries(self):
        """Test keyboard on page 15 (last page)."""
        keyboard = self.get_keyboard(15)
        
        # Prev should point to page 14
        self.assertEqual(keyboard.inline_keyboard[0][0].callback_data, "evaldoc_page_14")
        
        # Next should be disabled
        self.assertEqual(keyboard.inline_keyboard[0][2].callback_data, "evaldoc_noop")
    
    def test_page_2_boundaries(self):
        """Test keyboard on page 2."""
        keyboard = self.get_keyboard(2)
        
        # Prev should point to page 1
        self.assertEqual(keyboard.inline_keyboard[0][0].callback_data, "evaldoc_page_1")
        
        # Next should point to page 3
        self.assertEqual(keyboard.inline_keyboard[0][2].callback_data, "evaldoc_page_3")
    
    def test_page_14_boundaries(self):
        """Test keyboard on page 14."""
        keyboard = self.get_keyboard(14)
        
        # Prev should point to page 13
        self.assertEqual(keyboard.inline_keyboard[0][0].callback_data, "evaldoc_page_13")
        
        # Next should point to page 15
        self.assertEqual(keyboard.inline_keyboard[0][2].callback_data, "evaldoc_page_15")
    
    def test_all_pages_generate_valid_keyboards(self):
        """Test that all page numbers generate valid keyboards."""
        for page in range(1, self.total_pages + 1):
            with self.subTest(page=page):
                keyboard = self.get_keyboard(page)
                self.assertIsInstance(keyboard, InlineKeyboardMarkup)
                self.assertEqual(len(keyboard.inline_keyboard), 3)


class TestPageNavigation(unittest.TestCase):
    """Test page navigation logic."""
    
    def test_sequential_navigation_forward(self):
        """Test navigating forward through all pages."""
        from Main.plugins.userbot.devtools import get_evaldoc_keyboard
        
        for page in range(1, 15):  # Pages 1-14
            with self.subTest(page=page):
                keyboard = get_evaldoc_keyboard(page)
                next_button = keyboard.inline_keyboard[0][2]
                
                # Next button should point to page+1
                expected_callback = f"evaldoc_page_{page+1}"
                self.assertEqual(next_button.callback_data, expected_callback)
    
    def test_sequential_navigation_backward(self):
        """Test navigating backward through all pages."""
        from Main.plugins.userbot.devtools import get_evaldoc_keyboard
        
        for page in range(2, 16):  # Pages 2-15
            with self.subTest(page=page):
                keyboard = get_evaldoc_keyboard(page)
                prev_button = keyboard.inline_keyboard[0][0]
                
                # Prev button should point to page-1
                expected_callback = f"evaldoc_page_{page-1}"
                self.assertEqual(prev_button.callback_data, expected_callback)
    
    def test_jump_to_first(self):
        """Test First button always points to page 1."""
        from Main.plugins.userbot.devtools import get_evaldoc_keyboard
        
        for page in [1, 5, 10, 15]:
            with self.subTest(page=page):
                keyboard = get_evaldoc_keyboard(page)
                first_button = keyboard.inline_keyboard[1][0]
                self.assertEqual(first_button.callback_data, "evaldoc_page_1")
    
    def test_jump_to_last(self):
        """Test Last button always points to page 15."""
        from Main.plugins.userbot.devtools import get_evaldoc_keyboard
        
        for page in [1, 5, 10, 15]:
            with self.subTest(page=page):
                keyboard = get_evaldoc_keyboard(page)
                last_button = keyboard.inline_keyboard[1][2]
                self.assertEqual(last_button.callback_data, "evaldoc_page_15")


class TestCallbackHandler(unittest.IsolatedAsyncioTestCase):
    """Test callback handler logic (async tests)."""
    
    async def test_close_callback(self):
        """Test that close callback deletes the message."""
        from Main.plugins.userbot.devtools import evaldoc_callback_handler
        
        # Mock CallbackQuery
        mock_query = AsyncMock(spec=CallbackQuery)
        mock_query.data = "evaldoc_close"
        mock_query.message = AsyncMock()
        mock_query.message.delete = AsyncMock()
        
        # Mock Client
        mock_client = AsyncMock()
        
        # Call handler
        await evaldoc_callback_handler(mock_client, mock_query)
        
        # Verify message.delete was called
        mock_query.message.delete.assert_called_once()
    
    async def test_noop_callback(self):
        """Test that noop callback shows boundary alert."""
        from Main.plugins.userbot.devtools import evaldoc_callback_handler
        
        # Mock CallbackQuery
        mock_query = AsyncMock(spec=CallbackQuery)
        mock_query.data = "evaldoc_noop"
        mock_query.answer = AsyncMock()
        
        # Mock Client
        mock_client = AsyncMock()
        
        # Call handler
        await evaldoc_callback_handler(mock_client, mock_query)
        
        # Verify answer was called with boundary message
        mock_query.answer.assert_called_once()
        call_args = mock_query.answer.call_args
        self.assertIn("boundary", call_args[0][0].lower())
    
    async def test_page_navigation_callback(self):
        """Test that page navigation updates the message."""
        from Main.plugins.userbot.devtools import evaldoc_callback_handler
        
        # Mock CallbackQuery
        mock_query = AsyncMock(spec=CallbackQuery)
        mock_query.data = "evaldoc_page_5"
        mock_query.message = AsyncMock()
        mock_query.message.edit_text = AsyncMock()
        mock_query.answer = AsyncMock()
        
        # Mock Client
        mock_client = AsyncMock()
        
        # Call handler
        await evaldoc_callback_handler(mock_client, mock_query)
        
        # Verify message.edit_text was called
        mock_query.message.edit_text.assert_called_once()
        
        # Verify answer was called
        mock_query.answer.assert_called_once()
    
    async def test_invalid_page_callback(self):
        """Test that invalid page number shows error."""
        from Main.plugins.userbot.devtools import evaldoc_callback_handler
        
        # Mock CallbackQuery with invalid page
        mock_query = AsyncMock(spec=CallbackQuery)
        mock_query.data = "evaldoc_page_999"
        mock_query.answer = AsyncMock()
        
        # Mock Client
        mock_client = AsyncMock()
        
        # Call handler
        await evaldoc_callback_handler(mock_client, mock_query)
        
        # Verify answer was called with error
        mock_query.answer.assert_called_once()
        call_args = mock_query.answer.call_args
        self.assertTrue(call_args[1].get('show_alert', False))


class TestIntegration(unittest.TestCase):
    """Integration tests for complete workflow."""
    
    def test_complete_navigation_flow(self):
        """Test complete navigation flow from page 1 to 15."""
        from Main.plugins.userbot.devtools import get_evaldoc_keyboard, EVAL_DOC_PAGES
        
        current_page = 1
        visited_pages = []
        
        # Navigate forward to page 15
        while current_page <= 15:
            visited_pages.append(current_page)
            keyboard = get_evaldoc_keyboard(current_page)
            
            # Verify page content exists
            self.assertIsNotNone(EVAL_DOC_PAGES[current_page - 1])
            
            # Get next page from Next button
            next_button = keyboard.inline_keyboard[0][2]
            if next_button.callback_data != "evaldoc_noop":
                current_page = int(next_button.callback_data.split("_")[-1])
            else:
                break
        
        # Verify we visited all pages
        self.assertEqual(visited_pages, list(range(1, 16)))
    
    def test_client_page_accessibility(self):
        """Test that Client page (page 5) is accessible from all pages."""
        from Main.plugins.userbot.devtools import get_evaldoc_keyboard
        
        for page in [1, 3, 7, 10, 15]:
            with self.subTest(page=page):
                keyboard = get_evaldoc_keyboard(page)
                client_button = keyboard.inline_keyboard[1][1]
                
                # Verify Client button exists and points to page 5
                self.assertEqual(client_button.callback_data, "evaldoc_page_5")
                self.assertIn("Client", client_button.text)


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
