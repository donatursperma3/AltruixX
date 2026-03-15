"""
Comprehensive test suite for xrap_manager.py
Tests all functions, classes, and handlers
"""

import pytest
import asyncio
import json
import os
from unittest.mock import Mock, AsyncMock, patch, MagicMock, mock_open
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
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_db_path = Path(self.temp_dir) / "test_rap_db.json"
        
    def tearDown(self):
        """Cleanup test environment"""
        if self.test_db_path.exists():
            self.test_db_path.unlink()
        if os.path.exists(self.temp_dir):
            os.rmdir(self.temp_dir)
    
    def test_init_creates_default_structure(self):
        """Test RapManager initialization creates default structure"""
        self.setUp()
        
        with patch('Main.plugins.userbot.xrap_manager.RAP_DB_PATH', self.test_db_path):
            from Main.plugins.userbot.xrap_manager import RapManager
            
            manager = RapManager()
            
            # Verify default structure
            assert "lyrics" in manager.data
            assert "global_config" in manager.data
            assert isinstance(manager.data["lyrics"], dict)
            assert isinstance(manager.data["global_config"], dict)
            
            # Verify default config
            assert manager.data["global_config"]["default_delay"] == 6
            assert manager.data["global_config"]["default_emoji"] == "🔥"
            assert manager.data["global_config"]["mode"] == "reply"
            assert manager.data["global_config"]["inline_mode"] == False
        
        self.tearDown()
        print("✅ test_init_creates_default_structure PASSED")
    
    def test_save_and_load(self):
        """Test save and load functionality"""
        self.setUp()
        
        with patch('Main.plugins.userbot.xrap_manager.RAP_DB_PATH', self.test_db_path):
            from Main.plugins.userbot.xrap_manager import RapManager
            
            manager = RapManager()
            
            # Add test data
            manager.data["lyrics"]["test-song"] = {
                "title": "Test Song",
                "lyrics": ["Line 1", "Line 2"],
                "config": {}
            }
            
            # Save
            manager.save()
            
            # Verify file exists
            assert self.test_db_path.exists()
            
            # Load in new instance
            manager2 = RapManager()
            
            # Verify data loaded
            assert "test-song" in manager2.data["lyrics"]
            assert manager2.data["lyrics"]["test-song"]["title"] == "Test Song"
            assert len(manager2.data["lyrics"]["test-song"]["lyrics"]) == 2
        
        self.tearDown()
        print("✅ test_save_and_load PASSED")

    
    def test_add_song(self):
        """Test add_song method"""
        self.setUp()
        
        with patch('Main.plugins.userbot.xrap_manager.RAP_DB_PATH', self.test_db_path):
            from Main.plugins.userbot.xrap_manager import RapManager
            
            manager = RapManager()
            
            # Add song
            manager.add_song(
                slug="em-god",
                title="Rap God",
                lyrics=["Line 1", "Line 2", "Line 3"],
                config={"delay": 5}
            )
            
            # Verify song added
            assert "em-god" in manager.data["lyrics"]
            song = manager.data["lyrics"]["em-god"]
            assert song["title"] == "Rap God"
            assert len(song["lyrics"]) == 3
            assert song["config"]["delay"] == 5
        
        self.tearDown()
        print("✅ test_add_song PASSED")
    
    def test_get_song(self):
        """Test get_song method"""
        self.setUp()
        
        with patch('Main.plugins.userbot.xrap_manager.RAP_DB_PATH', self.test_db_path):
            from Main.plugins.userbot.xrap_manager import RapManager
            
            manager = RapManager()
            manager.add_song("test", "Test", ["Line 1"])
            
            # Get existing song
            song = manager.get_song("test")
            assert song is not None
            assert song["title"] == "Test"
            
            # Get non-existing song
            song = manager.get_song("nonexistent")
            assert song is None
        
        self.tearDown()
        print("✅ test_get_song PASSED")
