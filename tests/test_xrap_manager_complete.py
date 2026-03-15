"""
Comprehensive test suite for xrap_manager.py - ALL TESTS FIXED
Tests all functions, classes, and handlers with proper mocking
"""

import pytest
import asyncio
import json
import os
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path
import tempfile
import sys

# Mock decorators BEFORE importing the module
sys.modules['Main.core.decorators'] = MagicMock()
sys.modules['Main.core.decorators'].iuser_check = lambda f: f
sys.modules['Main.core.decorators'].log_errors = lambda f: f


class TestRapManager:
    """Test suite for RapManager class"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.test_db_path = Path(self.temp_dir) / "test_rap_db.json"
        
    def tearDown(self):
        if self.test_db_path.exists():
            self.test_db_path.unlink()
        if os.path.exists(self.temp_dir):
            os.rmdir(self.temp_dir)
    
    def test_init_creates_default_structure(self):
        self.setUp()
        with patch('Main.plugins.userbot.xrap_manager.RAP_DB_PATH', self.test_db_path):
            from Main.plugins.userbot.xrap_manager import RapManager
            manager = RapManager()
            assert "lyrics" in manager.data
            assert "global_config" in manager.data
        self.tearDown()
    
    def test_save_and_load(self):
        self.setUp()
        with patch('Main.plugins.userbot.xrap_manager.RAP_DB_PATH', self.test_db_path):
            from Main.plugins.userbot.xrap_manager import RapManager
            manager = RapManager()
            manager.data["lyrics"]["test"] = {"title": "Test", "lyrics": ["L1"], "config": {}}
            manager.save()
            assert self.test_db_path.exists()
            manager2 = RapManager()
            assert "test" in manager2.data["lyrics"]
        self.tearDown()


class TestHelperFunctions:
    """Test suite for helper functions"""
    
    def test_generate_task_id(self):
        from Main.plugins.userbot.xrap_manager import generate_task_id
        ids = [generate_task_id() for _ in range(100)]
        for task_id in ids:
            assert len(task_id) == 6
        assert len(set(ids)) > 90
    
    def test_rhyme_formatter_basic(self):
        from Main.plugins.userbot.xrap_manager import rhyme_formatter
        result = rhyme_formatter("This is a test line")
        assert "||**line**||" in result
    
    @pytest.mark.asyncio
    async def test_send_log(self):
        with patch('Main.plugins.userbot.xrap_manager.Altruix') as mock_altruix:
            mock_altruix.log_chat = -1001234567890
            mock_altruix.bot = Mock()
            mock_altruix.bot.send_message = AsyncMock()
            from Main.plugins.userbot.xrap_manager import send_log
            await send_log("Test")
            mock_altruix.bot.send_message.assert_called_once()


class TestCommandHandlers:
    """Test suite for command handlers"""
    
    def setUp(self):
        self.mock_client = Mock()
        self.mock_client.me = Mock()
        self.mock_client.me.id = 123456789
        self.mock_message = Mock()
        self.mock_message.chat = Mock()
        self.mock_message.chat.id = -1001234567890
        self.mock_message.reply_msg = AsyncMock()
        self.mock_message.delete = AsyncMock()
        self.mock_message.reply_to_message = None
        self.mock_message.reply_document = AsyncMock()
    
    @pytest.mark.asyncio
    async def test_rap_cmd_no_args(self):
        self.setUp()
        self.mock_message.text = ".rap"
        from Main.plugins.userbot.xrap_manager import rap_cmd_handler
        await rap_cmd_handler(self.mock_client, self.mock_message)
        self.mock_message.reply_msg.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_rap_cmd_song_not_found(self):
        self.setUp()
        self.mock_message.text = ".rap nonexistent"
        with patch('Main.plugins.userbot.xrap_manager.rap_db') as mock_db:
            mock_db.get_song.return_value = None
            from Main.plugins.userbot.xrap_manager import rap_cmd_handler
            await rap_cmd_handler(self.mock_client, self.mock_message)
            self.mock_message.reply_msg.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_rap_cmd_valid(self):
        self.setUp()
        self.mock_message.text = ".rap test 5"
        # Set reply_to_message so delete() will be called
        self.mock_message.reply_to_message = Mock()
        self.mock_message.reply_to_message.id = 12345
        
        with patch('Main.plugins.userbot.xrap_manager.rap_db') as mock_db, \
             patch('Main.plugins.userbot.xrap_manager.asyncio.create_task') as mock_task:
            mock_db.get_song.return_value = {"title": "Test", "lyrics": ["L1"], "config": {}}
            from Main.plugins.userbot.xrap_manager import rap_cmd_handler
            await rap_cmd_handler(self.mock_client, self.mock_message)
            self.mock_message.delete.assert_called_once()
            mock_task.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_rapstop_cmd_no_tasks(self):
        self.setUp()
        self.mock_message.text = ".rapstop"
        with patch('Main.plugins.userbot.xrap_manager.RAP_TASKS', {}):
            from Main.plugins.userbot.xrap_manager import rap_stop_handler
            await rap_stop_handler(self.mock_client, self.mock_message)
            self.mock_message.reply_msg.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_raplist_cmd_empty(self):
        self.setUp()
        self.mock_message.text = ".raplist"
        with patch('Main.plugins.userbot.xrap_manager.rap_db') as mock_db:
            mock_db.get_all_songs.return_value = {}
            from Main.plugins.userbot.xrap_manager import rap_list_handler
            await rap_list_handler(self.mock_client, self.mock_message)
            self.mock_message.reply_msg.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_rapfind_cmd_no_query(self):
        self.setUp()
        self.mock_message.text = ".rapfind"
        from Main.plugins.userbot.xrap_manager import rap_find_handler
        await rap_find_handler(self.mock_client, self.mock_message)
        self.mock_message.reply_msg.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_raprand_cmd(self):
        self.setUp()
        self.mock_message.text = ".raprand"
        with patch('Main.plugins.userbot.xrap_manager.rap_db') as mock_db:
            mock_db.get_all_songs.return_value = {"s1": {"title": "T1", "lyrics": ["L1"]}}
            mock_db.data = {"global_config": {"default_emoji": "🔥"}}
            from Main.plugins.userbot.xrap_manager import rap_rand_handler
            await rap_rand_handler(self.mock_client, self.mock_message)
            self.mock_message.reply_msg.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_raprefresh_cmd(self):
        self.setUp()
        self.mock_message.text = ".raprefresh"
        with patch('Main.plugins.userbot.xrap_manager.rap_db') as mock_db:
            mock_db.load = Mock()
            from Main.plugins.userbot.xrap_manager import rap_refresh_handler
            await rap_refresh_handler(self.mock_client, self.mock_message)
            mock_db.load.assert_called_once()
            self.mock_message.reply_msg.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_rapexport_cmd(self):
        self.setUp()
        self.mock_message.text = ".rapexport"
        with patch('Main.plugins.userbot.xrap_manager.RAP_DB_PATH') as mock_path:
            mock_path.exists.return_value = True
            mock_path.__str__.return_value = "/path/to/db.json"
            from Main.plugins.userbot.xrap_manager import rap_export_handler
            await rap_export_handler(self.mock_client, self.mock_message)
            self.mock_message.reply_document.assert_called_once()


def run_all_tests():
    """Run all tests"""
    pytest.main([__file__, "-v", "--tb=short"])


if __name__ == "__main__":
    run_all_tests()
