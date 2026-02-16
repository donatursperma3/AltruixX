import asyncio
import sys
import os
from unittest.mock import MagicMock, AsyncMock

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# ✅ MOCK Altruix BEFORE importing anything else
import Main
mock_altruix = MagicMock()
mock_altruix.clients = []
mock_altruix.plugin_categories = {}
mock_altruix.config = MagicMock()
mock_altruix.get_string = MagicMock(return_value="MockedString")
mock_altruix.bot = MagicMock()

# Inject mock into Main.core.client and Main.core
import Main.core.client
Main.core.client.Altruix = mock_altruix
import Main.core
Main.core.Altruix = mock_altruix

# Now we can import the handlers
import Main.internals.settings_handlers.session_info as session_info

async def test_auto_delete_enhancements():
    # Setup mock data for the test
    mock_me = MagicMock()
    mock_me.id = 12345
    mock_me.first_name = "CoolKid"
    mock_me.last_name = "369"
    mock_me.username = "coolkid369"
    mock_me.is_premium = True
    
    mock_client = AsyncMock()
    mock_client.me = mock_me
    mock_client.get_me = AsyncMock(return_value=mock_me)
    mock_client.get_chat = AsyncMock(return_value=MagicMock(bio="Verified Bio"))
    
    mock_altruix.clients = [mock_client]
    mock_altruix.plugin_categories = {"p1": "userbot", "p2": "bot", "p3": "other"}
    mock_altruix.is_session_disabled = MagicMock(return_value=False)
    
    # Mock config
    mock_altruix.config.get_env = AsyncMock(side_effect=lambda k: {
        "PREFIX_APPLY_TYPE": "global",
        "CMD_HANDLER": ".",
        "SUDO_CMD_HANDLER": ",",
        "SUDO_APPLY_TYPE": "global",
        "SUDO_ENABLED_GLOBAL": "true",
        "AUTO_DELETE_CMD_TYPE_0": "per_account",
        "AUTO_DELETE_CMD_STATUS_0": "on",
        "AUTO_DELETE_CMD_DELAY_0": "10"
    }.get(k))
    
    # Mock localization
    mock_altruix.get_string = MagicMock(side_effect=lambda k: {
        "auto_delete_cmd": "Auto-Delete Input",
        "refresh_info": "Refresh",
        "unlink_session": "Unlink",
        "next": "Next",
        "back": "Back"
    }.get(k, k))

    print("Testing get_session_info_data with index 0...")
    text, markup = await session_info.get_session_info_data(0, 1, 1)
    
    print("\n[INFO] Generated Text Output:")
    print("-" * 50)
    print(text)
    print("-" * 50)
    
    # Verify auto delete info is present
    assert "Auto-Delete Input" in text
    assert "✅ ON" in text
    assert "PER ACCOUNT" in text
    assert "10s" in text
    print("✅ Auto-delete info verified in dashboard text.")
    
    # Verify buttons
    print("\n[INFO] Generated Markup Output (Page 1):")
    for row in markup.inline_keyboard:
        for btn in row:
            print(f"[{btn.text}] -> {btn.callback_data if hasattr(btn, 'callback_data') else btn.url}")
    
    assert len(markup.inline_keyboard) > 0
    print("✅ Markup buttons verified.")

    print("\n[SUCCESS] Verification complete! Logic is valid and UI is correctly generated.")

if __name__ == "__main__":
    asyncio.run(test_auto_delete_enhancements())

if __name__ == "__main__":
    asyncio.run(test_auto_delete_enhancements())
