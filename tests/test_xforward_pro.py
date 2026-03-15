"""
Tests for xforward_pro.py — Database CRUD & UI builders.
Uses importlib to import the plugin file directly, avoiding package path issues.
"""
import pytest
import asyncio
import os
import sys
import json
import tempfile
import types
import importlib.util
from unittest.mock import AsyncMock, MagicMock, patch

# ────────── Test DB Path ──────────
test_db_path = os.path.join(tempfile.gettempdir(), "test_forward_pro.db")

# ────────── Mock Altruix Ecosystem BEFORE importing plugin ──────────
mock_bot = MagicMock()
mock_bot.on_callback_query = MagicMock(return_value=lambda fn: fn)
mock_bot.send_message = AsyncMock()

mock_config = MagicMock()
mock_config.OWNER_ID = 12345
mock_config.OWNER_USERS_ID = [12345]
mock_config.LOG_CHAT_ID = -100999

mock_altruix = MagicMock()
mock_altruix.bot = mock_bot
mock_altruix.clients = []
mock_altruix.config = mock_config
mock_altruix.log_chat = -100999
mock_altruix.log = MagicMock()
mock_altruix.is_sudo = AsyncMock(return_value=True)
mock_altruix.register_on_cmd = MagicMock(return_value=lambda fn: fn)
mock_altruix.bot_manager = MagicMock()
mock_altruix.bot_manager.get_bot = MagicMock(return_value=mock_bot)
mock_altruix.__version__ = "0.0.10.test"

# Build mock Main package hierarchy
main_mod = types.ModuleType("Main")
main_mod.Altruix = mock_altruix
sys.modules["Main"] = main_mod

core_mod = types.ModuleType("Main.core")
sys.modules["Main.core"] = core_mod

types_mod = types.ModuleType("Main.core.types")
sys.modules["Main.core.types"] = types_mod

msg_mod = types.ModuleType("Main.core.types.message")
msg_mod.Message = MagicMock
sys.modules["Main.core.types.message"] = msg_mod

dec_mod = types.ModuleType("Main.core.decorators")
dec_mod.iuser_check = lambda fn: fn
dec_mod.log_errors = lambda fn: fn
sys.modules["Main.core.decorators"] = dec_mod

utils_mod = types.ModuleType("Main.utils")
sys.modules["Main.utils"] = utils_mod

fh_mod = types.ModuleType("Main.utils.file_helpers")
fh_mod.get_db_path = lambda name: os.path.join(tempfile.gettempdir(), f"test_{name}")
fh_mod.get_user_button_style = lambda uid: None
sys.modules["Main.utils.file_helpers"] = fh_mod

# ────────── Import Plugin via importlib ──────────
PLUGIN_PATH = os.path.join(
    os.path.dirname(__file__), "..", "Main", "plugins", "userbot", "xforward_pro.py"
)
PLUGIN_PATH = os.path.abspath(PLUGIN_PATH)

spec = importlib.util.spec_from_file_location("xforward_pro", PLUGIN_PATH)
plugin = importlib.util.module_from_spec(spec)
sys.modules["xforward_pro"] = plugin

# Pre-set DB_PATH before exec
plugin.DB_PATH = test_db_path
spec.loader.exec_module(plugin)

# Override the DB_PATH after import
plugin.DB_PATH = test_db_path
plugin._db_initialized = False


# ────────── Fixtures ──────────
@pytest.fixture(autouse=True)
async def reset_db():
    """Reset the database before each test."""
    plugin._db_initialized = False
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
    yield
    if os.path.exists(test_db_path):
        try:
            os.remove(test_db_path)
        except Exception:
            pass


# ────────── Database CRUD Tests ──────────
class TestDatabaseCRUD:
    @pytest.mark.asyncio
    async def test_init_db(self):
        """Test database initialization creates tables."""
        await plugin.init_db()
        assert plugin._db_initialized is True
        assert os.path.exists(test_db_path)

    @pytest.mark.asyncio
    async def test_add_and_get_task(self):
        """Test adding and retrieving a task."""
        uid = 7844837037
        task_id = await plugin.add_task(uid, -1001111, -1002222, "live")
        assert task_id > 0
        
        tasks = await plugin.get_tasks(uid)
        assert len(tasks) == 1
        assert tasks[0]["source_id"] == -1001111
        assert tasks[0]["target_id"] == -1002222
        assert tasks[0]["mode"] == "live"
        assert tasks[0]["is_active"] == 0

    @pytest.mark.asyncio
    async def test_get_single_task(self):
        """Test getting a single task by ID."""
        uid = 7844837037
        task_id = await plugin.add_task(uid, -1003333, -1004444)
        
        task = await plugin.get_task(task_id)
        assert task is not None
        assert task["id"] == task_id
        assert task["source_id"] == -1003333

    @pytest.mark.asyncio
    async def test_update_task(self):
        """Test updating task fields."""
        uid = 7844837037
        task_id = await plugin.add_task(uid, -1005555, -1006666)
        
        result = await plugin.update_task(task_id, is_active=1, bypass_protected=1)
        assert result is True
        
        task = await plugin.get_task(task_id)
        assert task["is_active"] == 1
        assert task["bypass_protected"] == 1

    @pytest.mark.asyncio
    async def test_delete_task(self):
        """Test deleting a task."""
        uid = 7844837037
        task_id = await plugin.add_task(uid, -1007777, -1008888)
        
        result = await plugin.delete_task(task_id)
        assert result is True
        
        task = await plugin.get_task(task_id)
        assert task is None

    @pytest.mark.asyncio
    async def test_multiple_tasks_per_user(self):
        """Test multiple tasks for the same user."""
        uid = 7844837037
        await plugin.add_task(uid, -100111, -100222)
        await plugin.add_task(uid, -100333, -100444)
        await plugin.add_task(uid, -100555, -100666)
        
        tasks = await plugin.get_tasks(uid)
        assert len(tasks) == 3

    @pytest.mark.asyncio
    async def test_tasks_isolated_per_user(self):
        """Test that tasks are isolated between users."""
        uid1 = 1111
        uid2 = 2222
        await plugin.add_task(uid1, -100111, -100222)
        await plugin.add_task(uid2, -100333, -100444)
        
        tasks1 = await plugin.get_tasks(uid1)
        tasks2 = await plugin.get_tasks(uid2)
        assert len(tasks1) == 1
        assert len(tasks2) == 1
        assert tasks1[0]["source_id"] != tasks2[0]["source_id"]

    @pytest.mark.asyncio
    async def test_update_filters_json(self):
        """Test updating filters as JSON."""
        uid = 7844837037
        task_id = await plugin.add_task(uid, -100111, -100222)
        
        filt = {"photo": True, "video": False, "text": True}
        await plugin.update_task(task_id, filters=json.dumps(filt))
        
        task = await plugin.get_task(task_id)
        loaded = json.loads(task["filters"])
        assert loaded["video"] is False
        assert loaded["photo"] is True


class TestGlobalSettings:
    @pytest.mark.asyncio
    async def test_get_default_settings(self):
        """Test getting default global settings."""
        uid = 7844837037
        gs = await plugin.get_global_settings(uid)
        assert gs["default_delay"] == 1.5
        assert gs.get("log_channel", 0) == 0

    @pytest.mark.asyncio
    async def test_update_global_settings(self):
        """Test updating global settings."""
        uid = 7844837037
        await plugin.update_global_settings(uid, default_delay=3.0, log_channel=-100999)
        
        gs = await plugin.get_global_settings(uid)
        assert gs["default_delay"] == 3.0
        assert gs["log_channel"] == -100999


class TestUIBuilders:
    @pytest.mark.asyncio
    async def test_main_menu_text(self):
        """Test main menu text builder."""
        uid = 7844837037
        text = await plugin.build_main_menu_text(uid)
        assert "Forward Pro Dashboard" in text
        assert "Total Tasks" in text

    def test_main_menu_keyboard(self):
        """Test main menu keyboard has correct buttons."""
        uid = 7844837037
        gs = {"default_delay": 1.5}
        kb = plugin.build_main_menu_kb(uid, gsettings=gs)
        assert len(kb.inline_keyboard) == 9
        assert "List Tasks" in kb.inline_keyboard[0][0].text
        assert len(kb.inline_keyboard[1]) == 2
        assert "Close" in kb.inline_keyboard[8][0].text

    @pytest.mark.asyncio
    async def test_task_list_empty(self):
        """Test task list shows empty message."""
        uid = 99999
        text = await plugin.build_task_list_text(uid)
        assert "No tasks configured" in text

    @pytest.mark.asyncio
    async def test_task_detail_text(self):
        """Test task detail text builder."""
        uid = 7844837037
        task_id = await plugin.add_task(uid, -1001234, -1005678)
        task = await plugin.get_task(task_id)
        text = await plugin.build_task_detail_text(task)
        assert f"Task #{task_id}" in text
        assert "-1001234" in text
        assert "-1005678" in text

    def test_task_detail_keyboard_inactive(self):
        """Test task detail keyboard for inactive task."""
        task = {"id": 1, "is_active": 0, "bypass_protected": 0, "mode": "live"}
        kb = plugin.build_task_detail_kb(task, 12345)
        assert len(kb.inline_keyboard) == 7
        assert "Start" in kb.inline_keyboard[0][0].text

    def test_task_detail_keyboard_active(self):
        """Test task detail keyboard for active task."""
        task = {"id": 1, "is_active": 1, "bypass_protected": 0, "mode": "live"}
        kb = plugin.build_task_detail_kb(task, 12345)
        assert len(kb.inline_keyboard) == 7
        assert "Stop" in kb.inline_keyboard[0][0].text

    def test_filter_keyboard(self):
        """Test filter keyboard has media type toggles."""
        task = {"id": 1, "filters": "{}", "user_id": 12345}
        kb = plugin.build_filter_kb(task, 12345)
        assert len(kb.inline_keyboard) >= 4

    def test_get_message_type_photo(self):
        """Test message type detection — photo."""
        msg = MagicMock()
        msg.photo = True
        msg.video = None
        msg.audio = None
        msg.document = None
        msg.sticker = None
        msg.voice = None
        msg.text = None
        assert plugin._get_message_type(msg) == "photo"

    def test_get_message_type_text(self):
        """Test message type detection — text."""
        msg = MagicMock()
        msg.photo = None
        msg.video = None
        msg.audio = None
        msg.document = None
        msg.sticker = None
        msg.voice = None
        msg.text = "hello"
        assert plugin._get_message_type(msg) == "text"


class TestPhase2Logic:
    def test_clean_caption(self):
        """Test regex cleaning of links and usernames."""
        raw = "Check this out @user123 and visit https://google.com for more info!"
        cleaned = plugin._clean_caption(raw)
        assert "@user123" not in cleaned
        assert "https://google.com" not in cleaned
        assert "Check this out" in cleaned
        assert "for more info!" in cleaned

    @pytest.mark.asyncio
    async def test_handle_fwd_filtered(self):
        """Test that handle_fwd respects filters."""
        client = AsyncMock()
        msg = MagicMock()
        msg.photo = True
        msg.caption = "test"
        
        # Filter out photos
        filters = {"photo": False}
        success, reason = await plugin._handle_fwd(client, msg, -100123, bypass=False, filters=filters)
        assert success is False
        assert reason == "Filtered"

    @pytest.mark.asyncio
    async def test_handle_fwd_standard(self):
        """Test standard forward success."""
        client = AsyncMock()
        msg = AsyncMock()
        msg.photo = None
        msg.text = "test message"
        msg.caption = None
        msg.has_protected_content = False
        
        success, reason = await plugin._handle_fwd(client, msg, -100123)
        assert success is True
        msg.forward.assert_called_with(-100123)

    @pytest.mark.asyncio
    async def test_handle_fwd_bypass_trigger(self):
        """Test that protected content triggers bypass logic."""
        client = AsyncMock()
        msg = AsyncMock()
        msg.photo = True
        msg.text = None
        msg.caption = "protected caption"
        msg.has_protected_content = True
        
        with patch("xforward_pro._copy_protected_message", new_callable=AsyncMock) as mock_copy:
            success, reason = await plugin._handle_fwd(client, msg, -100123, bypass=True)
            assert success is True
            assert "Bypass" in reason
            mock_copy.assert_called()
