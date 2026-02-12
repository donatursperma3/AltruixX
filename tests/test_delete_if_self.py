# Copyright (C) 2021-present by Altruix@Github, < https://github.com/Altruix >.
#
# This file is part of < https://github.com/Altruix/Altruix > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/Altriux/Altruix/blob/main/LICENSE >
#
# All rights reserved.

"""
Unit tests for Message.delete_if_self() method.

Tests verify that the auto-delete functionality works correctly with various
configurations including global/per-account settings, delays, and error handling.

NOTE: These tests are designed to be run in isolation without requiring
the full Altruix application to be initialized.
"""

import asyncio
import sys
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch, Mock

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestDeleteIfSelf(unittest.TestCase):
    """Test suite for Message.delete_if_self() method."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock message object
        self.message = MagicMock()
        self.message.from_user = MagicMock()
        self.message.from_user.is_self = True
        self.message.outgoing = False
        self.message._client = MagicMock()
        self.message._client.me = MagicMock()
        self.message._client.me.id = 12345
        self.message.delete = AsyncMock(return_value=self.message)
        
        # Mock Altruix
        self.altruix_patcher = patch('Main.Altruix')
        self.mock_altruix = self.altruix_patcher.start()
        self.mock_altruix.clients = []
        self.mock_altruix.config = MagicMock()
        self.mock_altruix.log = MagicMock()

    def tearDown(self):
        """Clean up after tests."""
        self.altruix_patcher.stop()

    async def _run_delete_if_self(self):
        """Helper to run delete_if_self with proper async context."""
        # Import the actual Message class
        from Main.core.types.message import Message
        return await Message.delete_if_self(self.message)

    def test_not_self_message_returns_without_deleting(self):
        """Test that messages not from self are not deleted."""
        self.message.from_user.is_self = False
        self.message.outgoing = False
        
        result = asyncio.run(self._run_delete_if_self())
        
        self.assertEqual(result, self.message)
        self.message.delete.assert_not_called()

    def test_auto_delete_disabled_returns_without_deleting(self):
        """Test that when auto-delete is disabled, message is not deleted."""
        # Setup: client found, auto-delete disabled
        mock_client = MagicMock()
        mock_client.me = MagicMock()
        mock_client.me.id = 12345
        self.mock_altruix.clients = [mock_client]
        
        async def mock_get_env(key):
            if key == "AUTO_DELETE_CMD_TYPE_0":
                return "per_account"
            if key == "AUTO_DELETE_CMD_STATUS_0":
                return "off"
            return None
        
        self.mock_altruix.config.get_env = AsyncMock(side_effect=mock_get_env)
        
        result = asyncio.run(self._run_delete_if_self())
        
        self.assertEqual(result, self.message)
        self.message.delete.assert_not_called()

    def test_auto_delete_enabled_deletes_message(self):
        """Test that when auto-delete is enabled, message is deleted."""
        # Setup: client found, auto-delete enabled
        mock_client = MagicMock()
        mock_client.me = MagicMock()
        mock_client.me.id = 12345
        self.mock_altruix.clients = [mock_client]
        
        async def mock_get_env(key):
            if key == "AUTO_DELETE_CMD_TYPE_0":
                return "per_account"
            if key == "AUTO_DELETE_CMD_STATUS_0":
                return "on"
            if key == "AUTO_DELETE_CMD_DELAY_0":
                return "0"
            return None
        
        self.mock_altruix.config.get_env = AsyncMock(side_effect=mock_get_env)
        
        result = asyncio.run(self._run_delete_if_self())
        
        self.message.delete.assert_called_once()

    def test_global_config_reads_global_settings(self):
        """Test that global config type reads from global settings."""
        # Setup: client found, global config
        mock_client = MagicMock()
        mock_client.me = MagicMock()
        mock_client.me.id = 12345
        self.mock_altruix.clients = [mock_client]
        
        async def mock_get_env(key):
            if key == "AUTO_DELETE_CMD_TYPE_0":
                return "global"
            if key == "AUTO_DELETE_CMD_GLOBAL":
                return "on"
            if key == "AUTO_DELETE_CMD_DELAY_GLOBAL":
                return "0"
            return None
        
        self.mock_altruix.config.get_env = AsyncMock(side_effect=mock_get_env)
        
        result = asyncio.run(self._run_delete_if_self())
        
        self.message.delete.assert_called_once()

    def test_delay_is_respected(self):
        """Test that delay configuration is respected."""
        # Setup: client found, auto-delete enabled with delay
        mock_client = MagicMock()
        mock_client.me = MagicMock()
        mock_client.me.id = 12345
        self.mock_altruix.clients = [mock_client]
        
        async def mock_get_env(key):
            if key == "AUTO_DELETE_CMD_TYPE_0":
                return "per_account"
            if key == "AUTO_DELETE_CMD_STATUS_0":
                return "on"
            if key == "AUTO_DELETE_CMD_DELAY_0":
                return "2"
            return None
        
        self.mock_altruix.config.get_env = AsyncMock(side_effect=mock_get_env)
        
        import time
        start = time.time()
        result = asyncio.run(self._run_delete_if_self())
        elapsed = time.time() - start
        
        # Verify delay was applied (with tolerance)
        self.assertGreaterEqual(elapsed, 1.9)
        self.message.delete.assert_called_once()

    def test_invalid_delay_uses_zero(self):
        """Test that invalid delay values default to 0."""
        # Setup: client found, auto-delete enabled with invalid delay
        mock_client = MagicMock()
        mock_client.me = MagicMock()
        mock_client.me.id = 12345
        self.mock_altruix.clients = [mock_client]
        
        async def mock_get_env(key):
            if key == "AUTO_DELETE_CMD_TYPE_0":
                return "per_account"
            if key == "AUTO_DELETE_CMD_STATUS_0":
                return "on"
            if key == "AUTO_DELETE_CMD_DELAY_0":
                return "invalid"
            return None
        
        self.mock_altruix.config.get_env = AsyncMock(side_effect=mock_get_env)
        
        result = asyncio.run(self._run_delete_if_self())
        
        # Should still delete, just with 0 delay
        self.message.delete.assert_called_once()

    def test_negative_delay_uses_zero(self):
        """Test that negative delay values default to 0."""
        # Setup: client found, auto-delete enabled with negative delay
        mock_client = MagicMock()
        mock_client.me = MagicMock()
        mock_client.me.id = 12345
        self.mock_altruix.clients = [mock_client]
        
        async def mock_get_env(key):
            if key == "AUTO_DELETE_CMD_TYPE_0":
                return "per_account"
            if key == "AUTO_DELETE_CMD_STATUS_0":
                return "on"
            if key == "AUTO_DELETE_CMD_DELAY_0":
                return "-5"
            return None
        
        self.mock_altruix.config.get_env = AsyncMock(side_effect=mock_get_env)
        
        result = asyncio.run(self._run_delete_if_self())
        
        # Should still delete, just with 0 delay
        self.message.delete.assert_called_once()

    def test_client_not_found_returns_without_deleting(self):
        """Test that if client is not found in Altruix.clients, message is not deleted."""
        # Setup: empty clients list
        self.mock_altruix.clients = []
        
        result = asyncio.run(self._run_delete_if_self())
        
        self.assertEqual(result, self.message)
        self.message.delete.assert_not_called()

    def test_exception_during_delete_returns_self(self):
        """Test that exceptions during delete are handled gracefully."""
        # Setup: client found, auto-delete enabled, but delete fails
        mock_client = MagicMock()
        mock_client.me = MagicMock()
        mock_client.me.id = 12345
        self.mock_altruix.clients = [mock_client]
        
        async def mock_get_env(key):
            if key == "AUTO_DELETE_CMD_TYPE_0":
                return "per_account"
            if key == "AUTO_DELETE_CMD_STATUS_0":
                return "on"
            if key == "AUTO_DELETE_CMD_DELAY_0":
                return "0"
            return None
        
        self.mock_altruix.config.get_env = AsyncMock(side_effect=mock_get_env)
        self.message.delete = AsyncMock(side_effect=Exception("Delete failed"))
        
        result = asyncio.run(self._run_delete_if_self())
        
        # Should return self even if delete fails
        self.assertEqual(result, self.message)

    def test_various_enabled_values(self):
        """Test that various enabled values are correctly interpreted."""
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
        
        for enabled_value, should_delete in test_cases:
            with self.subTest(enabled_value=enabled_value):
                # Reset mock
                self.message.delete.reset_mock()
                
                # Setup
                mock_client = MagicMock()
                mock_client.me = MagicMock()
                mock_client.me.id = 12345
                self.mock_altruix.clients = [mock_client]
                
                async def mock_get_env(key):
                    if key == "AUTO_DELETE_CMD_TYPE_0":
                        return "per_account"
                    if key == "AUTO_DELETE_CMD_STATUS_0":
                        return enabled_value
                    if key == "AUTO_DELETE_CMD_DELAY_0":
                        return "0"
                    return None
                
                self.mock_altruix.config.get_env = AsyncMock(side_effect=mock_get_env)
                
                result = asyncio.run(self._run_delete_if_self())
                
                if should_delete:
                    self.message.delete.assert_called_once()
                else:
                    self.message.delete.assert_not_called()


if __name__ == "__main__":
    unittest.main()
