"""
Tests for the .autogp run shortcut in xauto_gpurgeme_userbot.py
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import sys

# 1. Mock external dependencies
def identity(*args, **kwargs):
    if len(args) == 1 and callable(args[0]):
        return args[0]
    return lambda f: f
mock_decorators = MagicMock()
mock_decorators.iuser_check = identity
mock_decorators.log_errors = identity
sys.modules['Main.core.decorators'] = mock_decorators

mock_filters = MagicMock()
sys.modules['pyrogram.filters'] = mock_filters

# Mock internal settings module
mock_autogp = MagicMock()
mock_autogp.ACTIVE_PURGE_TASKS = {}
mock_autogp.auto_gp_global_cycle = AsyncMock()
mock_autogp.get_auto_gp_status_text = AsyncMock(return_value="Status Text")
mock_autogp.get_auto_gp_settings = AsyncMock(return_value={"status": True})
mock_autogp.get_auto_gp_kb = MagicMock(return_value="Keyboard")
sys.modules['Main.internals.settings_handlers.auto_global_purgeme'] = mock_autogp

# 2. Setup Altruix mock
mock_altruix = MagicMock()
mock_altruix.register_on_cmd = identity
mock_altruix.on_message = identity
mock_altruix.bot_manager.get_bot_username = Mock(return_value="bot")

with patch('Main.Altruix', mock_altruix):
    import Main.plugins.userbot.xauto_gpurgeme_userbot as userbot_plugin

@pytest.mark.asyncio
async def test_autogp_run_shortcut():
    """Verify that .autogp run triggers the global cycle with force=True."""
    mock_client = AsyncMock()
    mock_client.me = Mock(id=12345)
    
    mock_message = AsyncMock()
    mock_message.user_input = "run"
    mock_message.edit = AsyncMock()
    
    # Trigger the dashboard command
    await userbot_plugin.autogp_dashboard_cmd(mock_client, mock_message)
    
    # Assertions
    mock_message.edit.assert_called_with(pytest.string_contains("Initiating quick global purge cycle"))
    mock_autogp.auto_gp_global_cycle.assert_called_once_with(mock_client, force=True)

@pytest.mark.asyncio
async def test_autogp_status_command():
    """Verify that .autogp status reports the correct status."""
    mock_client = AsyncMock()
    mock_client.me.id = 12345
    mock_message = AsyncMock()
    mock_message.user_input = "status"
    mock_message.edit = AsyncMock()
    
    # 1. Test IDLE
    mock_autogp.ACTIVE_PURGE_TASKS.clear()
    await userbot_plugin.autogp_dashboard_cmd(mock_client, mock_message)
    mock_message.edit.assert_called_with(pytest.string_contains("IDLE"))

    # 2. Test RUNNING
    mock_task = MagicMock()
    mock_task.done.return_value = False
    mock_autogp.ACTIVE_PURGE_TASKS[12345] = mock_task
    await userbot_plugin.autogp_dashboard_cmd(mock_client, mock_message)
    mock_message.edit.assert_called_with(pytest.string_contains("RUNNING"))

@pytest.mark.asyncio
async def test_autogp_stop_command():
    """Verify that .autogp stop cancels the active task."""
    mock_client = AsyncMock()
    mock_client.me.id = 12345
    mock_message = AsyncMock()
    mock_message.user_input = "stop"
    mock_message.edit = AsyncMock()
    
    mock_task = MagicMock()
    mock_task.done.return_value = False
    mock_autogp.ACTIVE_PURGE_TASKS[12345] = mock_task
    
    await userbot_plugin.autogp_dashboard_cmd(mock_client, mock_message)
    
    mock_task.cancel.assert_called_once()
    mock_message.edit.assert_called_with(pytest.string_contains("cancelled successfully"))

class PytestStringContains:
    def __init__(self, expected):
        self.expected = expected
    def __eq__(self, other):
        return self.expected in other

pytest.string_contains = PytestStringContains
