
import sys
import os
import pytest
import asyncio
import importlib.util
from unittest.mock import MagicMock, AsyncMock, patch

# --- 1. SETUP MOCKS BEFORE LOADING MODULE ---
altruix_mock = MagicMock()
altruix_mock.log = MagicMock()
altruix_mock.clients = []
altruix_mock.config = AsyncMock()


# Define helper to sanitize mocks for pytest
def sanitize_mock(mock_obj):
    mock_obj.pytest_plugins = None
    mock_obj.setUpModule = None
    mock_obj.tearDownModule = None
    mock_obj.setup_module = None
    mock_obj.teardown_module = None
    return mock_obj

# Mock the entire Main package structure
main_pkg = MagicMock()
sanitize_mock(main_pkg)
main_pkg.Altruix = altruix_mock
sys.modules["Main"] = main_pkg

sys.modules["Main.core"] = MagicMock()
sanitize_mock(sys.modules["Main.core"])

sys.modules["Main.core.decorators"] = MagicMock()
sanitize_mock(sys.modules["Main.core.decorators"])

# Mock decorators specifically to pass through functions
def mock_decorator(func):
    return func
sys.modules["Main.core.decorators"].iuser_check = mock_decorator
sys.modules["Main.core.decorators"].log_errors = mock_decorator

sys.modules["Main.internals"] = MagicMock()
sanitize_mock(sys.modules["Main.internals"])

sys.modules["Main.internals.settings_handlers"] = MagicMock()
sanitize_mock(sys.modules["Main.internals.settings_handlers"])

sys.modules["Main.internals.settings_handlers.utils"] = MagicMock()
sanitize_mock(sys.modules["Main.internals.settings_handlers.utils"])

# Mock Pyrogram dependencies if not present
if "pyrogram" not in sys.modules:
    pyrogram_mock = MagicMock()
    sys.modules["pyrogram"] = pyrogram_mock
    sys.modules["pyrogram.types"] = MagicMock()
    sys.modules["pyrogram.errors"] = MagicMock()

# Define Enums manually for the test
class ChatType:
    PRIVATE = "private"
    GROUP = "group"
    SUPERGROUP = "supergroup"
    CHANNEL = "channel"
    BOT = "bot"

sys.modules["pyrogram.enums"] = MagicMock()
sys.modules["pyrogram.enums"].ChatType = ChatType

# --- 2. LOAD MODULE FROM SOURCE ---
file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../internals/settings_handlers/auto_global_purgeme.py'))
spec = importlib.util.spec_from_file_location("Main.internals.settings_handlers.auto_global_purgeme", file_path)
auto_global_purgeme = importlib.util.module_from_spec(spec)

# CRITICAL: Set the package so relative imports (from .utils) work
spec.loader.name = "Main.internals.settings_handlers.auto_global_purgeme"
auto_global_purgeme.__package__ = "Main.internals.settings_handlers"

sys.modules["Main.internals.settings_handlers.auto_global_purgeme"] = auto_global_purgeme
spec.loader.exec_module(auto_global_purgeme)

# Extract functions for testing
auto_gp_perform_purge = auto_global_purgeme.auto_gp_perform_purge
get_auto_gp_settings = auto_global_purgeme.get_auto_gp_settings

# --- 3. TESTS ---

@pytest.mark.asyncio
async def test_auto_gp_basic_flow():
    """Test basic flow: Status ON, Valid Chat -> Search -> Delete."""
    client = AsyncMock()
    client.me.id = 12345
    
    chat = MagicMock()
    chat.id = 999
    chat.type = ChatType.SUPERGROUP
    client.get_chat.return_value = chat
    
    # FIX: Populate Altruix.clients so notification logic works
    altruix_mock.clients = [client]
    
    # FIX: Notify MUST BE True for cycle completion log to be printed
    mock_settings = {
        "status": True,
        "blacklist": [],
        "limit": 5,
        "offset": 0,
        "filters": ["all"],
        "target": "all",
        "admin_filter": "all",
        "notify": True,
        "delay_msg": 0
    }
    
    # Mock search results
    msg1 = MagicMock()
    msg1.id = 101
    msg1.text = "test1"
    msg2 = MagicMock()
    msg2.id = 102
    msg2.text = "test2"
    
    async def search_gen(*args, **kwargs):
        yield msg1
        yield msg2
    
    # FIX: search_messages should NOT be AsyncMock (which implies awaitable), 
    # but a helper that returns an async generator.
    client.search_messages = MagicMock(side_effect=search_gen)
    
    # Patch get_auto_gp_settings inside the LOADED MODULE
    with patch.object(auto_global_purgeme, "get_auto_gp_settings", return_value=mock_settings):
        trigger_msg = MagicMock()
        trigger_msg.chat = chat
        trigger_msg.id = 100
        
        await auto_gp_perform_purge(client, 999, message=trigger_msg)
        
    # Verify
    client.search_messages.assert_called()
    client.delete_messages.assert_called()
    call_args = client.delete_messages.call_args
    assert call_args[0][0] == 999
    deleted_ids = call_args[0][1]
    assert 101 in deleted_ids
    assert 102 in deleted_ids
    
    altruix_mock.log.assert_any_call("✅ Auto-GP | Cycle Complete for 999. Deleted: 2", level=20)

@pytest.mark.asyncio
async def test_auto_gp_blacklist():
    """Test blacklist guard."""
    client = AsyncMock()
    client.me.id = 12345
    
    mock_settings = {
        "status": True,
        "blacklist": [999], 
        "notify": False
    }
    
    with patch.object(auto_global_purgeme, "get_auto_gp_settings", return_value=mock_settings):
        await auto_gp_perform_purge(client, 999)
        
    client.search_messages.assert_not_called()
    altruix_mock.log.assert_any_call("🕵️ Auto-GP | Chat 999 is blacklisted. Skipping.", level=20)

@pytest.mark.asyncio
async def test_auto_gp_status_off():
    """Test status OFF guard."""
    client = AsyncMock()
    client.me.id = 12345
    
    mock_settings = {
        "status": False,
        "blacklist": [],
        "notify": False
    }
    
    with patch.object(auto_global_purgeme, "get_auto_gp_settings", return_value=mock_settings):
        await auto_gp_perform_purge(client, 888)
        
    client.search_messages.assert_not_called()
    altruix_mock.log.assert_any_call("💤 Auto-GP | Status is OFF for user 12345. Skipping.", level=20)

@pytest.mark.asyncio
async def test_auto_gp_global_cycle():
    """
    Test the GLOBAL iteration logic:
    - Should iterate through target chats
    - Should call perform_purge for each match
    - Should respect lock
    """
    # 1. Setup mocks
    client = MagicMock()
    client.me.id = 12345
    
    mock_settings = {
        "status": True,
        "target": "all",
        "admin_filter": "all",
        "blacklist": [],
        "delay": 0.1 # Small delay for test
    }
    
    # Mock Target Chats
    mock_chats = [
        {"id": 1001, "title": "Chat A"},
        {"id": 1002, "title": "Chat B"},
        {"id": 1003, "title": "Chat C"}
    ]
    
    # 2. Patch dependencies
    with patch("Main.internals.settings_handlers.auto_global_purgeme.get_auto_gp_settings", return_value=mock_settings), \
         patch("Main.internals.settings_handlers.auto_global_purgeme.get_auto_gp_target_chats", return_value=(mock_chats, 0)), \
         patch("Main.internals.settings_handlers.auto_global_purgeme.auto_gp_perform_purge", new_callable=AsyncMock) as mock_purge, \
         patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
         
        # 3. Run Global Cycle
        await auto_global_purgeme.auto_gp_global_cycle(client)
        
        # 4. Verifications
        assert mock_purge.call_count == 3
        # Check call args for each chat
        mock_purge.assert_any_call(client, 1001, message=None)
        mock_purge.assert_any_call(client, 1002, message=None)
        mock_purge.assert_any_call(client, 1003, message=None)
        
        # Verify delay was called (len - 1 times) = 2 times
        assert mock_sleep.call_count >= 2

@pytest.mark.asyncio
async def test_cycle_mode_current_force():
    """
    Test the CURRENT FORCE mode logic:
    - Should call purge with bypass_guards=True
    - Should ignore blacklist/admin checks inside perform_purge
    """
    client = AsyncMock()
    client.me.id = 12345
    chat = MagicMock(); chat.id=999; chat.type="group"
    client.get_chat.return_value = chat
    
    mock_settings = {
        "status": True,
        "blacklist": [999], # Blacklisted
        "limit": 5,
        "offset": 0,
        "filters": ["all"],
        "target": "personal", # Mismatch
        "admin_filter": "all",
        "notify": False,
        "cycle": "current_force"
    }
    
    msg_list = [MagicMock(id=1), MagicMock(id=2)]
    async def search_gen(*args, **kwargs):
        for m in msg_list: yield m
    client.search_messages = MagicMock(side_effect=search_gen)

    with patch.object(auto_global_purgeme, "get_auto_gp_settings", return_value=mock_settings):
        # Force mode -> Bypass=True -> Should Delete
        await auto_gp_perform_purge(client, 999, message=MagicMock(chat=chat), bypass_guards=True)
        assert client.delete_messages.call_count > 0

@pytest.mark.asyncio
async def test_cycle_mode_current_smart():
    """
    Test the CURRENT SMART mode logic:
    - Should call purge with bypass_guards=False
    - Should RESPECT blacklist (skip purge)
    """
    client = AsyncMock()
    client.me.id = 12345
    chat = MagicMock(); chat.id=888; chat.type="group"
    client.get_chat.return_value = chat
    
    mock_settings = {
        "status": True,
        "blacklist": [888], # Blacklisted
        "limit": 5,
        "offset": 0,
        "filters": ["all"],
        "target": "all",
        "admin_filter": "all",
        "notify": False,
        "cycle": "current_smart"
    }
    
    with patch.object(auto_global_purgeme, "get_auto_gp_settings", return_value=mock_settings):
        # Smart mode -> Bypass=False -> Should be skipped due to blacklist
        await auto_gp_perform_purge(client, 888, message=MagicMock(chat=chat), bypass_guards=False)
        client.delete_messages.assert_not_called()

@pytest.mark.asyncio
async def test_filter_stickers_only():
    """Test filtering mechanism for stickers."""
    client = AsyncMock()
    client.me.id = 12345
    chat = MagicMock(); chat.id=777; chat.type=ChatType.GROUP
    client.get_chat.return_value = chat
    
    mock_settings = {
        "status": True,
        "blacklist": [],
        "limit": 5,
        "offset": 0,
        "filters": ["sticker"], # Only stickers
        "target": "all",
        "admin_filter": "all",
        "notify": False,
        "delay_msg": 0
    }
    
    msg_text = MagicMock(); msg_text.id = 201; msg_text.text = "Text"; msg_text.sticker = None
    msg_sticker = MagicMock(); msg_sticker.id = 202; msg_sticker.text = None; msg_sticker.sticker = True
    
    async def search_gen(*args, **kwargs):
        yield msg_text
        yield msg_sticker
        
    # FIX: search_messages should NOT be AsyncMock (which implies awaitable), 
    # but a helper that returns an async generator.
    client.search_messages = MagicMock(side_effect=search_gen)
    
    with patch.object(auto_global_purgeme, "get_auto_gp_settings", return_value=mock_settings):
        await auto_gp_perform_purge(client, 777, message=MagicMock(chat=chat))
        
    # Verify only sticker (202) is in deletion list
    call_args = client.delete_messages.call_args
    deleted_ids = call_args[0][1]
    assert 202 in deleted_ids
    assert 201 not in deleted_ids

if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))
