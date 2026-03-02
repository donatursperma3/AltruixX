import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock
from pyrogram import Client, enums
from pyrogram.enums import ChatAction
from pyrogram.errors import UserIsBlocked, PeerIdInvalid, RPCError

# Set up logging to see what's happening
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_block_detection")

# Mock the Altruix object if needed, but here we just test the function directly
# Copy the function logic from xdetect_haters.py for testing in isolation
async def check_if_blocked(client: Client, user_id: int) -> bool:
    """
    Check if a user has blocked us by probing with send_chat_action.
    Returns True if blocked, False otherwise.
    """
    try:
        # Probe using send_chat_action - safer for userbots to detect blocks
        await client.send_chat_action(user_id, ChatAction.TYPING)
        return False
    except UserIsBlocked:
        logger.info(f"Hater Alert: User {user_id} has blocked the bot.")
        return True
    except PeerIdInvalid:
        logger.debug(f"PeerIdInvalid for {user_id} - potential hater.")
        return True
    except RPCError as e:
        logger.debug(f"RPCInternalError checking block status for {user_id}: {e}")
        return True
    except Exception as e:
        logger.error(f"Unexpected error checking block status for {user_id}: {e}")
        return False

async def run_tests():
    mock_client = AsyncMock(spec=Client)
    
    # Test Case 1: User has NOT blocked
    mock_client.send_chat_action.return_value = True
    result = await check_if_blocked(mock_client, 12345)
    print(f"Test 1 (Not Blocked): Result={result} (Expected: False)")
    assert result is False
    
    # Test Case 2: User HAS blocked (raises UserIsBlocked)
    mock_client.send_chat_action.side_effect = UserIsBlocked
    result = await check_if_blocked(mock_client, 67890)
    print(f"Test 2 (UserIsBlocked): Result={result} (Expected: True)")
    assert result is True
    
    # Test Case 3: PeerIdInvalid (raises PeerIdInvalid)
    mock_client.send_chat_action.side_effect = PeerIdInvalid
    result = await check_if_blocked(mock_client, 11111)
    print(f"Test 3 (PeerIdInvalid): Result={result} (Expected: True)")
    assert result is True

    print("\n[SUCCESS] All automated test cases passed!")

if __name__ == "__main__":
    asyncio.run(run_tests())
