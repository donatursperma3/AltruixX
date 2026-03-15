"""
Comprehensive test suite for auto_global_purgeme.py
Tests all functions, actions, and logic flows with appropriate mocks.
"""

import pytest
import asyncio
import html
import re
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import sys

# 1. Mock external dependencies BEFORE any imports
def simple_identity(f): return f
def factory_identity(*args, **kwargs): return lambda f: f

# Mock decorators
mock_decorators = MagicMock()
mock_decorators.iuser_check = simple_identity
mock_decorators.log_errors = simple_identity
sys.modules['Main.core.decorators'] = mock_decorators

# Mock pyrogram filters
mock_filters = MagicMock()
mock_filters.regex = lambda *args, **kwargs: "MOCK_FILTER"
sys.modules['pyrogram.filters'] = mock_filters

# Mock internal utils to satisfy 'from .utils import ...'
mock_utils = MagicMock()
mock_utils.get_cmd_prefixes = Mock(return_value=["."])
mock_utils.send_log_notification = AsyncMock()
sys.modules['Main.internals.settings_handlers.utils'] = mock_utils

# Mock access_control
mock_ac = MagicMock()
mock_ac.is_authorized_user = Mock(return_value=True)
sys.modules['Main.utils.access_control'] = mock_ac

# 2. Setup Altruix mock
mock_altruix = MagicMock()
mock_altruix.bot = MagicMock()
mock_altruix.bot.on_callback_query = factory_identity
mock_altruix.bot.on_inline_query = factory_identity
mock_altruix.bot.on_message = factory_identity
mock_altruix.bot.send_message = AsyncMock()

# Setup explicit config values and AsyncMocks for awaited methods
mock_altruix.config = MagicMock()
mock_altruix.config.OWNER_USERS_ID = [12345]
mock_altruix.config.SUDO_USERS_ID = [67890]
mock_altruix.config.PREFIX_OWNER_USER = "."
mock_altruix.config.PREFIX_SUDO_USERS = "!"
mock_altruix.config.get_env = AsyncMock(return_value=None)
mock_altruix.config.set_env = AsyncMock()
mock_altruix.config.sync_env_to_db = AsyncMock()

mock_altruix.clients = []
mock_altruix.is_sudo = AsyncMock(return_value=True)
mock_altruix.get_string = lambda k, *args: f"[{k}]"

# Import the module under test with Altruix patched
with patch('Main.Altruix', mock_altruix):
    import Main.internals.settings_handlers.auto_global_purgeme as autogp

from pyrogram import enums, types

# Fix loc to return string instead of MagicMock
autogp.loc = lambda key, *args: f"[{key}]"

class AsyncIter:
    """Helper to mock async iterators (like search_messages)."""
    def __init__(self, items):
        self.items = items
    def __aiter__(self):
        return self
    async def __anext__(self):
        if not self.items:
            raise StopAsyncIteration
        return self.items.pop(0)

@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.me = Mock(id=12345, first_name="TestUser")
    mock_chat = Mock()
    mock_chat.title = "Test Chat"
    mock_chat.id = -1001
    client.get_chat = AsyncMock(return_value=mock_chat)
    msg = MagicMock(spec=types.Message)
    msg.id = 1
    msg.text = "Hello"
    msg.via_bot = None
    msg.reply_to_message_id = None
    msg.photo = None
    msg.video = None
    client.search_messages = Mock(return_value=AsyncIter([msg]))
    client.get_messages = AsyncMock(return_value=Mock(id=100))
    client.delete_messages = AsyncMock(return_value=True)
    return client

@pytest.fixture
def mock_cb():
    cb = AsyncMock()
    cb.from_user = Mock(id=12345)
    cb.message = AsyncMock()
    cb.message.chat = Mock(id=-1001)
    cb.data = ""
    cb.answer = AsyncMock()
    cb.edit_message_text = AsyncMock()
    cb.matches = [MagicMock()]
    return cb

def setup_cb_match(mock_cb, data):
    mock_cb.data = data
    regex = r"^autogp_(?P<action>target|cycle|limit|delay|delaymsg|mode|off|notif|filter|filtermenu|toggleadmin|bl|refresh|close|toggle|list|info|showcmd|back|noop|respectbl|skipcmds|keep|trigmode|forceconfirm|stopcycle|switchglobal)_(?P<tail>.*)$"
    match = re.search(regex, data)
    if match:
        def mock_group(key):
            try: return match.group(key)
            except: return None
        mock_cb.matches[0].group.side_effect = mock_group
    else:
        mock_cb.matches = []

def get_default_settings():
    return {
        "status": True, "target": "all", "cycle": "global", "mode": "newest",
        "limit": 10, "delay": 3.0, "delay_msg": 1.0, "offset": 0, "filters": ["all"],
        "admin_filter": "all", "notify": True, "respect_bl": True, "skip_cmds": True,
        "blacklist": [], "keep_recent": 6, "trigger_mode": "outgoing"
    }

class TestSettings:
    """Tests for settings retrieval and saving."""
    
    @pytest.mark.asyncio
    async def test_get_settings_default(self):
        with patch('Main.internals.settings_handlers.auto_global_purgeme.Altruix.config.get_env', AsyncMock(return_value=None)):
            settings = await autogp.get_auto_gp_settings(12345)
            assert settings["status"] is False
            assert settings["target"] == "all"
            assert settings["limit"] == 10

    @pytest.mark.asyncio
    async def test_save_settings(self):
        with patch('Main.internals.settings_handlers.auto_global_purgeme.Altruix.config.sync_env_to_db', AsyncMock()):
            test_settings = get_default_settings()
            await autogp.save_auto_gp_settings(12345, test_settings)

class TestUI:
    """Tests for UI text and keyboard generation."""
    
    @pytest.mark.asyncio
    async def test_status_text_generation(self):
        with patch.object(autogp, 'get_auto_gp_settings', AsyncMock(return_value=get_default_settings())):
            text = await autogp.get_auto_gp_status_text(12345)
            assert "AUTO GLOBAL PURGEME" in text
            assert "ENABLED" in text

    def test_keyboard_generation(self):
        settings = get_default_settings()
        kb = autogp.get_auto_gp_kb(12345, settings)
        assert isinstance(kb, types.InlineKeyboardMarkup)
        btns = [b.callback_data for row in kb.inline_keyboard for b in row]
        # Check for toggle button which includes user_id
        assert any("autogp_toggle_" in b for b in btns)

class TestCallbacks:
    """Tests for action handlers in the dashboard."""
    
    @pytest.mark.asyncio
    async def test_toggle_status(self, mock_client, mock_cb):
        setup_cb_match(mock_cb, "autogp_toggle_12345")
        settings = get_default_settings()
        settings["status"] = False
        
        with patch.object(autogp, 'get_auto_gp_settings', AsyncMock(return_value=settings)):
            with patch.object(autogp, 'save_auto_gp_settings', AsyncMock()) as mock_save:
                # Mock get_auto_gp_status_text and get_auto_gp_kb to avoid more mocks
                with patch.object(autogp, 'get_auto_gp_status_text', AsyncMock(return_value="OK")):
                    with patch.object(autogp, 'get_auto_gp_kb', Mock(return_value=None)):
                        await autogp.auto_gp_callback_handler(mock_client, mock_cb)
                        mock_save.assert_called()
                        saved_settings = mock_save.call_args[0][1]
                        assert saved_settings["status"] is True

    @pytest.mark.asyncio
    async def test_force_confirm_prompt(self, mock_client, mock_cb):
        setup_cb_match(mock_cb, "autogp_forceconfirm_prompt_12345")
        with patch('Main.internals.settings_handlers.auto_global_purgeme.get_auto_gp_settings', AsyncMock(return_value=get_default_settings())):
            await autogp.auto_gp_callback_handler(mock_client, mock_cb)
            
            args = mock_cb.edit_message_text.call_args
            assert args is not None
            text = args[0][0]
            assert "FORCE START" in text.upper()

    @pytest.mark.asyncio
    async def test_force_confirm_yes_rerender(self, mock_client, mock_cb):
        setup_cb_match(mock_cb, "autogp_forceconfirm_yes_12345")
        mock_altruix.clients = [mock_client]
        with patch('Main.internals.settings_handlers.auto_global_purgeme.get_auto_gp_settings', AsyncMock(return_value=get_default_settings())):
            with patch('Main.internals.settings_handlers.auto_global_purgeme.auto_gp_global_cycle', AsyncMock()):
                await autogp.auto_gp_callback_handler(mock_client, mock_cb)
                edit_text = mock_cb.edit_message_text.call_args[0][0]
                assert "AUTO GLOBAL PURGEME" in edit_text

    @pytest.mark.asyncio
    async def test_keyboard_inline_switch_global(self):
        settings = get_default_settings()
        settings["cycle"] = "current_smart"
        # current_chat_id = None simulates Inline Mode
        kb = autogp.get_auto_gp_kb(12345, settings, current_chat_id=None)
        btns = [b for row in kb.inline_keyboard for b in row]
        force_btn = next((b for b in btns if "forceconfirm" in b.callback_data), None)
        assert force_btn is not None
        assert "Switch & Start" in force_btn.text
        assert "switchglobal" in force_btn.callback_data

    @pytest.mark.asyncio
    async def test_switch_global_callback(self, mock_client, mock_cb):
        setup_cb_match(mock_cb, "autogp_forceconfirm_switchglobal_12345")
        settings = get_default_settings()
        settings["cycle"] = "current_smart"
        
        with patch.object(autogp, 'get_auto_gp_settings', AsyncMock(return_value=settings)):
            with patch.object(autogp, 'save_auto_gp_settings', AsyncMock()) as mock_save:
                await autogp.auto_gp_callback_handler(mock_client, mock_cb)
                
                # Verify settings were updated to global
                mock_save.assert_called()
                saved_settings = mock_save.call_args[0][1]
                assert saved_settings["cycle"] == "global"
                
                # Verify confirmation prompt was shown
                args = mock_cb.edit_message_text.call_args
                assert args is not None
                text = args[0][0]
                assert "FORCE START" in text.upper()
                assert "Global (All Targets)" in text

    @pytest.mark.asyncio
    async def test_keyboard_with_active_task(self):
        settings = get_default_settings()
        mock_task = MagicMock(spec=asyncio.Task)
        mock_task.done.return_value = False
        
        user_id = 12345
        with patch.dict(autogp.ACTIVE_PURGE_TASKS, {user_id: mock_task}):
            kb = autogp.get_auto_gp_kb(user_id, settings)
            btns = [b for row in kb.inline_keyboard for b in row]
            stop_btn = next((b for b in btns if "stopcycle" in b.callback_data), None)
            assert stop_btn is not None
            assert "Stop Active Purge" in stop_btn.text

    @pytest.mark.asyncio
    async def test_stop_cycle_callback(self, mock_client, mock_cb):
        user_id = 12345
        setup_cb_match(mock_cb, f"autogp_stopcycle_{user_id}")
        
        mock_task = MagicMock(spec=asyncio.Task)
        mock_task.done.return_value = False
        
        with patch.dict(autogp.ACTIVE_PURGE_TASKS, {user_id: mock_task}):
            with patch.object(autogp, 'get_auto_gp_settings', AsyncMock(return_value=get_default_settings())):
                with patch.object(autogp, 'get_auto_gp_status_text', AsyncMock(return_value="OK")):
                    with patch.object(autogp, 'get_auto_gp_kb', Mock(return_value=None)):
                        await autogp.auto_gp_callback_handler(mock_client, mock_cb)
                        
                        mock_task.cancel.assert_called_once()
                        assert user_id not in autogp.ACTIVE_PURGE_TASKS
                        mock_cb.answer.assert_called_with("🛑 Purge cycle cancelled successfully.", show_alert=True)

class TestEngine:
    """Tests for the purge engine logic."""
    
    @pytest.mark.asyncio
    async def test_purge_engine_skips_when_off(self, mock_client):
        settings = get_default_settings()
        settings["status"] = False
        with patch('Main.internals.settings_handlers.auto_global_purgeme.get_auto_gp_settings', AsyncMock(return_value=settings)):
            mock_client.search_messages.reset_mock()
            await autogp.auto_gp_perform_purge(mock_client, -1001)
            mock_client.search_messages.assert_not_called()

    @pytest.mark.asyncio
    async def test_purge_engine_runs_when_forced(self, mock_client):
        settings = get_default_settings()
        settings["status"] = False
        settings["limit"] = 10
        settings["keep_recent"] = 0
        
        with patch('Main.internals.settings_handlers.auto_global_purgeme.get_auto_gp_settings', AsyncMock(return_value=settings)):
            mock_chat = Mock()
            mock_chat.title = "Test Chat"
            mock_chat.id = -1001
            mock_client.get_chat.return_value = mock_chat
            
            msg = MagicMock(spec=types.Message)
            msg.id = 999
            msg.text = "Normal message"
            msg.via_bot = None
            msg.reply_to_message_id = None
            msg.photo = None
            msg.video = None
            mock_client.search_messages.return_value = AsyncIter([msg])
            mock_client.delete_messages.reset_mock()
            
            await autogp.auto_gp_perform_purge(mock_client, -1001, force=True)
            mock_client.search_messages.assert_called()
            mock_client.delete_messages.assert_called_once()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
