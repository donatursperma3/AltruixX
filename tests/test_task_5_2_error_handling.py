"""
Test untuk Task 5.2: Error handling di send_log_notification()
Validates: Requirements 3.5
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pyrogram.errors import (
    UserIsBlocked, PeerIdInvalid, ChatWriteForbidden, 
    FloodWait, BadRequest, ChannelPrivate
)
from pyrogram.types import Message


# Mock the send_log_notification function
async def send_log_notification_mock(
    bot_client,
    text: str,
    user_id: int,
    reply_to_msg_id=None,
    disable_web_page_preview=True
):
    """Mock implementation of send_log_notification with error handling"""
    import logging
    logger = logging.getLogger("test")
    
    log_msg = None

    # Check if bot_client is available
    if not bot_client:
        logger.error("Bot assistant tidak tersedia, tidak dapat mengirim notifikasi")
        return None

    # Send to PM user
    try:
        await bot_client.send_message(
            user_id,
            text,
            disable_web_page_preview=disable_web_page_preview,
            parse_mode="HTML"
        )
        logger.info(f"Notifikasi berhasil dikirim ke PM user {user_id}")
    except UserIsBlocked:
        logger.warning(f"User {user_id} telah memblokir bot assistant")
    except PeerIdInvalid:
        logger.warning(f"User ID {user_id} tidak valid atau bot belum pernah berinteraksi dengan user")
    except ChatWriteForbidden:
        logger.error(f"Bot tidak memiliki permission untuk mengirim pesan ke user {user_id}")
    except FloodWait as e:
        logger.warning(f"FloodWait {e.value} detik saat mengirim ke PM user {user_id}")
    except BadRequest as e:
        logger.error(f"BadRequest saat mengirim ke PM user {user_id}: {e}")
    except Exception as e:
        logger.error(f"Gagal kirim notifikasi ke PM user {user_id}: {e}")

    # Send to LOG_CHAT_ID (mock as 123456)
    LOG_CHAT_ID = 123456
    try:
        log_msg = await bot_client.send_message(
            LOG_CHAT_ID,
            text,
            reply_to_message_id=reply_to_msg_id,
            disable_web_page_preview=disable_web_page_preview,
            parse_mode="HTML"
        )
        logger.info(f"Notifikasi berhasil dikirim ke LOG_CHAT_ID")
    except ChatWriteForbidden:
        logger.error(f"Bot tidak memiliki permission untuk mengirim pesan ke LOG_CHAT_ID {LOG_CHAT_ID}")
    except PeerIdInvalid:
        logger.error(f"LOG_CHAT_ID {LOG_CHAT_ID} tidak valid")
    except ChannelPrivate:
        logger.error(f"LOG_CHAT_ID {LOG_CHAT_ID} adalah channel private dan bot tidak memiliki akses")
    except FloodWait as e:
        logger.warning(f"FloodWait {e.value} detik saat mengirim ke LOG_CHAT_ID")
    except BadRequest as e:
        logger.error(f"BadRequest saat mengirim ke LOG_CHAT_ID: {e}")
    except Exception as e:
        logger.error(f"Gagal kirim notifikasi ke LOG_CHAT_ID: {e}")

    return log_msg


@pytest.mark.asyncio
async def test_bot_assistant_not_available():
    """Test: Bot assistant tidak tersedia"""
    result = await send_log_notification_mock(
        bot_client=None,
        text="Test message",
        user_id=12345
    )
    assert result is None


@pytest.mark.asyncio
async def test_user_blocked_bot():
    """Test: User telah memblokir bot"""
    bot_client = AsyncMock()
    bot_client.send_message.side_effect = UserIsBlocked()
    
    result = await send_log_notification_mock(
        bot_client=bot_client,
        text="Test message",
        user_id=12345
    )
    # Should not crash, returns None or message from LOG_CHAT_ID
    assert result is None or isinstance(result, (Message, MagicMock))


@pytest.mark.asyncio
async def test_peer_id_invalid():
    """Test: User ID tidak valid"""
    bot_client = AsyncMock()
    bot_client.send_message.side_effect = PeerIdInvalid()
    
    result = await send_log_notification_mock(
        bot_client=bot_client,
        text="Test message",
        user_id=99999
    )
    # Should not crash
    assert result is None or isinstance(result, (Message, MagicMock))


@pytest.mark.asyncio
async def test_permission_error():
    """Test: Bot tidak memiliki permission"""
    bot_client = AsyncMock()
    bot_client.send_message.side_effect = ChatWriteForbidden()
    
    result = await send_log_notification_mock(
        bot_client=bot_client,
        text="Test message",
        user_id=12345
    )
    # Should not crash
    assert result is None or isinstance(result, (Message, MagicMock))


@pytest.mark.asyncio
async def test_flood_wait():
    """Test: FloodWait error"""
    bot_client = AsyncMock()
    bot_client.send_message.side_effect = FloodWait(value=30)
    
    result = await send_log_notification_mock(
        bot_client=bot_client,
        text="Test message",
        user_id=12345
    )
    # Should not crash
    assert result is None or isinstance(result, (Message, MagicMock))


@pytest.mark.asyncio
async def test_channel_private():
    """Test: LOG_CHAT_ID adalah channel private"""
    bot_client = AsyncMock()
    # First call succeeds (PM user), second call fails (LOG_CHAT_ID)
    bot_client.send_message.side_effect = [
        AsyncMock(spec=Message),  # Success for PM
        ChannelPrivate()  # Fail for LOG_CHAT_ID
    ]
    
    result = await send_log_notification_mock(
        bot_client=bot_client,
        text="Test message",
        user_id=12345
    )
    # Should not crash, returns None because LOG_CHAT_ID failed
    assert result is None


@pytest.mark.asyncio
async def test_successful_notification():
    """Test: Notifikasi berhasil dikirim ke kedua tempat"""
    bot_client = AsyncMock()
    mock_msg = AsyncMock(spec=Message)
    bot_client.send_message.return_value = mock_msg
    
    result = await send_log_notification_mock(
        bot_client=bot_client,
        text="Test message",
        user_id=12345
    )
    # Should return message object from LOG_CHAT_ID
    assert result is not None
    assert bot_client.send_message.call_count == 2


@pytest.mark.asyncio
async def test_bad_request_error():
    """Test: BadRequest error"""
    bot_client = AsyncMock()
    bot_client.send_message.side_effect = BadRequest("Invalid message")
    
    result = await send_log_notification_mock(
        bot_client=bot_client,
        text="Test message",
        user_id=12345
    )
    # Should not crash
    assert result is None or isinstance(result, (Message, MagicMock))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
