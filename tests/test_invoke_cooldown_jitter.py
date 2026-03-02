import asyncio
import sys
import os
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import the module to ensure monkeypatch is applied
import Main.core.types.client as client_mod
import Main

async def async_noop_sleep(_):
    return None

class DummyClient:
    """
    Docstring:
    Dummy client untuk menguji invoke():
    - Memiliki atribut 'me' dengan id/username
    - Memiliki '__send_custom__' yang selalu melempar TimeoutError
    """
    def __init__(self):
        self.me = SimpleNamespace(id=12345, first_name="Tester", username="tester")
    
    async def __send_custom__(self, *args, **kwargs):
        # Default behavior: simulate a critical sync timeout
        raise asyncio.TimeoutError(self.error_msg)

def main():
    """
    Docstring:
    Menjalankan uji cepat untuk memastikan:
    - invoke() mengembalikan None pada timeout non-kritis
    - invoke() melempar Exception pada timeout kritis (updates.*)
    - cooldown per operasi diset
    """
    # Mock Altruix minimal
    Main.Altruix = MagicMock()
    Main.Altruix.clients = [MagicMock()]
    Main.Altruix.log = MagicMock()
    Main.Altruix._TIMEOUT_COOLDOWNS = {}
    
    dummy = DummyClient()
    
    async def run():
        with patch("asyncio.sleep", side_effect=async_noop_sleep), \
             patch("Main.core.types.client.Altruix") as MockAltruix:
            
            MockAltruix.clients = [MagicMock()]
            MockAltruix.log = MagicMock()
            MockAltruix._TIMEOUT_COOLDOWNS = {}

            # 1. TEST CRITICAL: updates.GetChannelDifference (Must Raise)
            dummy.error_msg = 'Failed to invoke "updates.GetChannelDifference"'
            try:
                await client_mod.CustomClientMethods.invoke(dummy, None)
                assert False, "CRITICAL: invoke() harus melempar exception untuk updates.*"
            except asyncio.TimeoutError:
                print("✓ Critical operation correctly raised exception")
            except Exception as e:
                assert False, f"Unexpected exception: {type(e).__name__}"

            # 2. TEST NON-CRITICAL: channels.GetMessages (Must return None)
            dummy.error_msg = 'Failed to invoke "channels.GetMessages"'
            result = await client_mod.CustomClientMethods.invoke(dummy, None)
            assert result is None, "NON-CRITICAL: invoke() harus mengembalikan None"
            print("✓ Non-critical operation correctly returned None")

            # 3. TEST COOLDOWN (Non-Critical)
            key = (dummy.me.id, "NoneType")
            assert key in MockAltruix._TIMEOUT_COOLDOWNS, f"Cooldown tidak terset untuk {key}. Current cooldowns: {MockAltruix._TIMEOUT_COOLDOWNS}"
            assert MockAltruix._TIMEOUT_COOLDOWNS[key] > time.time(), "Nilai cooldown bukan timestamp masa depan"
            print("✓ Cooldown correctly set")
    
    asyncio.run(run())
    print("✓ All stabilization tests passed")

if __name__ == "__main__":
    main()
