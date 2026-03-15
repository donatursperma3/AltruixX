import pytest
import os
import json
from unittest.mock import MagicMock, patch, AsyncMock
from Main.plugins.userbot import xmessage_sender as plugin

@pytest.fixture
def mock_client():
    c = MagicMock()
    c.me.id = 123456789
    c.me.first_name = "TestBot"
    c.me.mention = "@TestBot"
    c.send_message = AsyncMock()
    c.get_messages = AsyncMock()
    c.download_media = AsyncMock(return_value="/tmp/test.jpg")
    return c

@pytest.fixture
def mock_msg():
    m = MagicMock()
    m.groups = []
    m.reply_msg = AsyncMock()
    m.handle_message = AsyncMock(return_value=AsyncMock(edit_msg=AsyncMock()))
    return m

@pytest.mark.asyncio
async def test_sendto_success(mock_client, mock_msg):
    mock_msg.groups = ["987654321", "none", "Hello"]
    with patch("Main.plugins.userbot.xmessage_sender.get_user_settings", return_value={"notify_logs": False}):
        await plugin.sendto_cmd(mock_client, mock_msg)
        mock_client.send_message.assert_called_once()
        # Verify target chat
        args, kwargs = mock_client.send_message.call_args
        assert args[0] == 987654321
        assert args[1] == "Hello"

@pytest.mark.asyncio
async def test_sendto_with_reply(mock_client, mock_msg):
    mock_msg.groups = ["987654321", "123", "Hello"]
    with patch("Main.plugins.userbot.xmessage_sender.get_user_settings", return_value={"notify_logs": False}):
        await plugin.sendto_cmd(mock_client, mock_msg)
        args, kwargs = mock_client.send_message.call_args
        assert kwargs["reply_parameters"].message_id == 123

@pytest.mark.asyncio
async def test_sendtofrom_protected(mock_client, mock_msg):
    mock_msg.groups = ["target", "none", "source", "42"]
    
    source_msg = MagicMock()
    source_msg.empty = False
    source_msg.media = True
    source_msg.photo = True
    source_msg.has_protected_content = True
    source_msg.caption = "Source Caption"
    
    mock_client.get_messages.return_value = source_msg
    mock_client.send_photo = AsyncMock()
    
    with patch("Main.plugins.userbot.xmessage_sender.get_user_settings", return_value={"notify_logs": False}), \
         patch("os.path.exists", return_value=True), \
         patch("os.remove"):
        await plugin.sendtofrom_cmd(mock_client, mock_msg)
        
        # Should have downloaded
        mock_client.download_media.assert_called_with(source_msg)
        # Should have sent photo
        mock_client.send_photo.assert_called_once()
        args, kwargs = mock_client.send_photo.call_args
        assert kwargs["caption"] == "Source Caption"

@pytest.mark.asyncio
async def test_sendto_link(mock_client, mock_msg):
    # .sendto https://t.me/c/2819883800/26958 none Hello
    mock_msg.groups = ["https://t.me/c/2819883800/26958", "none", "Hello"]
    with patch("Main.plugins.userbot.xmessage_sender.get_user_settings", return_value={"notify_logs": False}):
        await plugin.sendto_cmd(mock_client, mock_msg)
        args, kwargs = mock_client.send_message.call_args
        assert args[0] == -1002819883800
        assert args[1] == "Hello"
        assert kwargs["reply_parameters"].message_id == 26958

@pytest.mark.asyncio
async def test_sendtofrom_links(mock_client, mock_msg):
    # .sendtofrom target_link source_link
    mock_msg.groups = ["https://t.me/c/111/222", "https://t.me/username/333"]
    
    source_msg = MagicMock()
    source_msg.empty = False
    source_msg.media = False
    source_msg.text = "Cloned Text"
    
    mock_client.get_messages.return_value = source_msg
    
    with patch("Main.plugins.userbot.xmessage_sender.get_user_settings", return_value={"notify_logs": False}):
        await plugin.sendtofrom_cmd(mock_client, mock_msg)
        
        # Verify get_messages called on source
        mock_client.get_messages.assert_called_with("username", 333)
        # Verify send_message called on target with reply to its link msg id
        args, kwargs = mock_client.send_message.call_args
        assert args[0] == -100111
        assert kwargs["reply_parameters"].message_id == 222
