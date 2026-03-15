import pytest
import json
import os
from unittest.mock import MagicMock, patch, AsyncMock
from pyrogram.types import CallbackQuery
from Main.internals.settings_handlers.logger_handlers import pmlf_toggle_handler, mntf_toggle_handler

@pytest.mark.asyncio
async def test_pmlf_toggle_handler_legacy_bool_fix(tmp_path):
    # Setup mock data with legacy boolean session
    user_id = 12345
    user_id_str = str(user_id)
    db_file = tmp_path / "pm_logger_user_settings.json"
    data = {
        "sessions": {
            user_id_str: True  # Legacy bool format
        }
    }
    db_file.write_text(json.dumps(data))
    
    # Mock Altruix, Client, CallbackQuery
    mock_client = MagicMock()
    mock_client.me.id = user_id
    
    mock_cb = MagicMock(spec=CallbackQuery)
    mock_cb.matches = [MagicMock()]
    mock_cb.matches[0].groups.return_value = ("user", "user", "text", "0", "1")
    mock_cb.answer = AsyncMock()
    
    with patch("Main.internals.settings_handlers.logger_handlers.get_db_path", return_value=str(db_file)), \
         patch("Main.internals.settings_handlers.logger_handlers.Altruix") as mock_altruix, \
         patch("Main.internals.settings_handlers.logger_handlers.show_pmlf_list", new_callable=AsyncMock) as mock_show:
        
        mock_altruix.clients = [mock_client]
        
        # Execute handler
        await pmlf_toggle_handler(None, mock_cb)
        
        # Verify migration
        with open(db_file, "r") as f:
            new_data = json.load(f)
        
        assert isinstance(new_data["sessions"][user_id_str], dict)
        assert new_data["sessions"][user_id_str]["enabled"] is True
        assert "filters" in new_data["sessions"][user_id_str]
        assert new_data["sessions"][user_id_str]["filters"]["from_user"]["text"] is False # toggled from default True

@pytest.mark.asyncio
async def test_mntf_toggle_handler_legacy_bool_fix(tmp_path):
    # Setup mock data with legacy boolean session
    user_id = 12345
    user_id_str = str(user_id)
    db_file = tmp_path / "mentions_settings.json"
    data = {
        "settings": {
            user_id_str: False  # Legacy bool format
        }
    }
    db_file.write_text(json.dumps(data))
    
    # Mock Altruix, Client, CallbackQuery
    mock_client = MagicMock()
    mock_client.me.id = user_id
    
    mock_cb = MagicMock(spec=CallbackQuery)
    mock_cb.matches = [MagicMock()]
    mock_cb.matches[0].groups.return_value = ("user", "text", "0", "1")
    mock_cb.answer = AsyncMock()
    
    with patch("Main.internals.settings_handlers.logger_handlers.get_db_path", return_value=str(db_file)), \
         patch("Main.internals.settings_handlers.logger_handlers.Altruix") as mock_altruix, \
         patch("Main.internals.settings_handlers.logger_handlers.show_mntf_list", new_callable=AsyncMock) as mock_show:
        
        mock_altruix.clients = [mock_client]
        
        # Execute handler
        await mntf_toggle_handler(None, mock_cb)
        
        # Verify migration
        with open(db_file, "r") as f:
            new_data = json.load(f)
        
        assert isinstance(new_data["settings"][user_id_str], dict)
        assert new_data["settings"][user_id_str]["mention"] is False
        assert "filters" in new_data["settings"][user_id_str]
        assert new_data["settings"][user_id_str]["filters"]["from_user"]["text"] is False # toggled from default True
