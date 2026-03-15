import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

mock_altruix = MagicMock()
mock_altruix.bot.on_message = lambda *a, **k: lambda f: f
mock_altruix.bot.on_callback_query = lambda *a, **k: lambda f: f
mock_altruix.config.OWNER_USERS_ID = [123]
mock_altruix.config.SUDO_USERS_ID = []
mock_altruix.get_string = lambda k: k

def identity(f): return f

with patch('Main.Altruix', mock_altruix), \
     patch('Main.core.decorators.iuser_check', side_effect=identity), \
     patch('Main.core.decorators.log_errors', side_effect=identity), \
     patch('Main.utils.file_helpers.get_db_path', return_value="/tmp/test.db"), \
     patch('Main.utils.access_control.is_authorized_user', return_value=True):
    import Main.plugins.userbot.xauto_pro_gcast as gcast

@pytest.fixture
def base_settings():
    return {
        "text_list": [{"content": "GCast Text 1"}],
        "reply_text_list": [{"content": "Reply Text 1"}],
        "auto_reply": True,
        "reply_delay": 1,
        "self_destruct": True,
        "self_destruct_delay": 2,
        "chat_filter": "all",
        "admin_filter": "all",
        "delay_per_chat": 2,
        "recurring": False,
        "random_text": True,
        "blacklist": [],
        "smart_purge": False,
    }

@pytest.mark.asyncio
class TestAdvancedSelfDestruct:
    
    @patch('Main.plugins.userbot.xauto_pro_gcast.get_settings')
    @patch('Main.plugins.userbot.xauto_pro_gcast.get_target_chats', return_value=[(100, "Test Group")])
    @patch('Main.plugins.userbot.xauto_pro_gcast.send_log', new_callable=AsyncMock)
    @patch('Main.plugins.userbot.xauto_pro_gcast.asyncio.sleep', new_callable=AsyncMock)
    async def test_sd_target_both_trigger_after_gcast(self, mock_sleep, mock_send_log, mock_targets, mock_get_settings, base_settings):
        base_settings.update({"sd_target": "both", "sd_trigger": "after_gcast"})
        mock_get_settings.return_value = base_settings
        
        client = MagicMock()
        client.send_message = AsyncMock(return_value=MagicMock(id=999)) # Sent gcast
        client.delete_messages = AsyncMock()
        
        # Test the inner function logic directly
        # Simulating: handle_post_send(c, cid, gcast_mid, s, t_state)
        reply_msg = MagicMock(id=666)
        client.send_message.return_value = reply_msg
        
        pass

@pytest.mark.asyncio
class TestBroadcastControlsUI:
    
    @patch('Main.plugins.userbot.xauto_pro_gcast.get_settings')
    @patch('Main.plugins.userbot.xauto_pro_gcast.save_settings')
    @patch('Main.plugins.userbot.xauto_pro_gcast.safe_edit_message', new_callable=AsyncMock)
    @patch('Main.plugins.userbot.xauto_pro_gcast.safe_cb_answer', new_callable=AsyncMock)
    @patch('Main.plugins.userbot.xauto_pro_gcast.get_user_button_style', return_value=1)
    async def test_pause_resume_stop(self, mock_style, mock_answer, mock_edit, mock_save, mock_get, base_settings):
        uid = 123
        task_id = "#GABCD"
        gcast.GCAST_TASKS[uid] = {
            "task_id": task_id,
            "running": True,
            "pause_event": asyncio.Event(),
            "sent_count": 5,
            "total_chats": 10,
            "errors": 0
        }
        gcast.GCAST_TASKS[uid]["pause_event"].set()
        
        cb = MagicMock()
        cb.data = f"pgc_pause_{uid}_{task_id}"
        await gcast.pgc_callback_handler(AsyncMock(), cb)
        assert not gcast.GCAST_TASKS[uid]["pause_event"].is_set()
        
        cb.data = f"pgc_resume_{uid}_{task_id}"
        await gcast.pgc_callback_handler(AsyncMock(), cb)
        assert gcast.GCAST_TASKS[uid]["pause_event"].is_set()
        
        cb.data = f"pgc_stop_{uid}_{task_id}"
        await gcast.pgc_callback_handler(AsyncMock(), cb)
        assert not gcast.GCAST_TASKS[uid]["running"]
        
        cb.data = f"pgc_status_{uid}_{task_id}"
        await gcast.pgc_callback_handler(AsyncMock(), cb)
        assert mock_answer.called
        assert "Progress: 5/10" in mock_answer.call_args[0][1]

    @patch('Main.plugins.userbot.xauto_pro_gcast.get_settings')
    @patch('Main.plugins.userbot.xauto_pro_gcast.save_settings')
    @patch('Main.plugins.userbot.xauto_pro_gcast.safe_edit_message', new_callable=AsyncMock)
    @patch('Main.plugins.userbot.xauto_pro_gcast.safe_cb_answer', new_callable=AsyncMock)
    @patch('Main.plugins.userbot.xauto_pro_gcast.get_user_button_style', return_value=1)
    async def test_sd_ui_toggles(self, mock_style, mock_answer, mock_edit, mock_save, mock_get, base_settings):
        uid = 123
        mock_get.return_value = base_settings
        
        cb = MagicMock()
        cb.data = f"pgc_sdtarget_{uid}"
        await gcast.pgc_callback_handler(AsyncMock(), cb)
        assert mock_save.called
        assert mock_save.call_args[0][1]["sd_target"] == "reply"
        
        cb.data = f"pgc_sdtrigger_{uid}"
        await gcast.pgc_callback_handler(AsyncMock(), cb)
        assert mock_save.call_args[0][1]["sd_trigger"] == "after_reply"

@pytest.mark.asyncio
class TestBugFixesAndSafeties:
    
    @patch('Main.plugins.userbot.xauto_pro_gcast.get_settings')
    @patch('Main.plugins.userbot.xauto_pro_gcast.send_log', new_callable=AsyncMock)
    @patch('Main.plugins.userbot.xauto_pro_gcast.safe_cb_answer', new_callable=AsyncMock)
    @patch('Main.plugins.userbot.xauto_pro_gcast.get_user_button_style', return_value=1)
    async def test_inline_dashboard_nonetype_addtext(self, mock_style, mock_answer, mock_send_log, mock_get, base_settings):
        uid = 123
        mock_get.return_value = base_settings
        
        # Simulate an inline callback query where cb.message is missing entirely
        # (This simulates the context where the user reported `NoneType object has no attribute 'chat'`)
        cb = MagicMock()
        cb.data = f"pgc_repmsgaddtext_{uid}_p0"
        cb.message = None  # Crucial for the inline dashboard simulation!
        
        # Ensure it doesn't crash with AttributeError
        await gcast.pgc_callback_handler(AsyncMock(), cb)
        
        # State should be updated safely using fallback logic: chat_id=uid, msg_id=0
        state = gcast.GCAST_REPLY_TEXT_INPUT_STATE.get(uid)
        assert state is not None
        assert state["chat_id"] == uid
        assert state["msg_id"] == 0
        assert mock_send_log.called
