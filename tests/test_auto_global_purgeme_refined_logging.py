import pytest
import asyncio
import html
import sys
import os
from unittest.mock import Mock, AsyncMock, patch, MagicMock

# Ensure local 'Main' can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock external dependencies
mock_decorators = MagicMock()
mock_decorators.iuser_check = lambda f: f
mock_decorators.log_errors = lambda f: f
sys.modules['Main.core.decorators'] = mock_decorators

mock_filters = MagicMock()
sys.modules['pyrogram.filters'] = mock_filters

mock_utils = MagicMock()
mock_utils.send_log_notification = AsyncMock()
sys.modules['Main.internals.settings_handlers.utils'] = mock_utils

mock_altruix = MagicMock()
mock_altruix.bot_manager = MagicMock()
mock_altruix.bot = AsyncMock()
mock_altruix.log_chat = -100999

# Import the module under test
with patch('Main.Altruix', mock_altruix):
    import Main.internals.settings_handlers.auto_global_purgeme as autogp

from pyrogram import enums

@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.me = Mock(id=12345)
    return client

@pytest.mark.asyncio
async def test_global_cycle_refined_logging(mock_client):
    """Test that global cycle produces the correct live-updating log output."""
    user_id = 12345
    chats = [
        {"id": -1001, "name": "Chat A"},
        {"id": -1002, "name": "Chat B"},
        {"id": -1003, "name": "Chat C"}
    ]
    
    # Mock settings
    settings = {
        "status": True,
        "blacklist": [],
        "targets": chats,
        "batch_size": 20,
        "batch_delay": 0,
        "batch_msg_size": 100,
        "batch_msg_delay": 0,
        "delay": 0
    }
    
    # Mock behavior
    mock_chat_info = AsyncMock()
    mock_chat_info.title = "Mock Chat Name"
    mock_client.get_chat.return_value = mock_chat_info
    
    # Mock individual purge results
    with patch.object(autogp, 'get_auto_gp_settings', AsyncMock(return_value=settings)), \
         patch.object(autogp, 'auto_gp_perform_purge', AsyncMock(side_effect=[10, 5, 0])), \
         patch.object(autogp, 'get_chat_lock', lambda uid, cid: AsyncMock()):
        
        # Mock Custom Bot
        mock_custom_bot = AsyncMock()
        mock_custom_bot.send_message.return_value = AsyncMock(id=555, chat=Mock(id=-100999))
        mock_altruix.bot_manager.get_bot.return_value = mock_custom_bot
        
        # Run Global Cycle
        await autogp.auto_gp_global_cycle(mock_client, user_id, force=True)
        
        # Verify custom bot was used
        mock_altruix.bot_manager.get_bot.assert_called_with(user_id)
        
        # Capture the final log message content
        # It should have updated 3 times (once per chat) + initial
        edit_calls = mock_custom_bot.edit_message_text.call_args_list
        final_call_args = edit_calls[-1]
        final_text = final_call_args[0][2] # (chat_id, msg_id, text, ...)
        
        print("\n--- FINAL LOG OUTPUT EXAMPLE ---")
        print(final_text)
        print("--------------------------------\n")
        
        # Basic assertions on the output format
        assert "📋 Batch Log — Auto Global Purgeme" in final_text
        assert "📊 3/3 │ ✅ 15 msgs" in final_text
        assert "✅ (<code>-1001</code>) : <a href='https://t.me/c/1/1'>Mock Chat Name</a> | <code>10</code> msgs" in final_text
        assert "✅ (<code>-1002</code>) : <a href='https://t.me/c/2/1'>Mock Chat Name</a> | <code>5</code> msgs" in final_text
        assert "⏭ (<code>-1003</code>) : <a href='https://t.me/c/3/1'>Mock Chat Name</a> | <code>0</code> msgs" in final_text
        assert "🏁 <b>Completed</b>" in final_text

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-s"])
