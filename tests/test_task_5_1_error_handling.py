"""
Test for Task 5.1: Error handling in delete_if_self()

This test verifies that delete_if_self() properly handles:
- Database connection errors
- Permission errors
- Invalid config values
- Proper error logging
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from Main.core.types.message import Message


class TestDeleteIfSelfErrorHandling:
    """Test error handling in delete_if_self() method"""
    
    @pytest.mark.asyncio
    async def test_database_connection_error_fallback(self):
        """Test that database connection errors fall back to default (disabled)"""
        # Create mock message
        msg = Mock(spec=Message)
        msg.from_user = Mock(is_self=True)
        msg.outgoing = True
        msg._client = Mock()
        msg._client.me = Mock(id=12345)
        
        # Mock Altruix
        with patch('Main.core.types.message.Altruix') as mock_altruix:
            mock_altruix.clients = [msg._client]
            
            # Simulate database connection error
            mock_altruix.config.get_env = AsyncMock(side_effect=Exception("Database connection failed"))
            mock_altruix.log = Mock()
            
            # Call delete_if_self
            result = await Message.delete_if_self(msg)
            
            # Should return self without deleting (fallback to disabled)
            assert result == msg
            
            # Should log the database error
            log_calls = [str(call) for call in mock_altruix.log.call_args_list]
            assert any("Database error" in str(call) for call in log_calls)
    
    @pytest.mark.asyncio
    async def test_permission_error_graceful_skip(self):
        """Test that permission errors are handled gracefully"""
        # Create mock message
        msg = Mock(spec=Message)
        msg.from_user = Mock(is_self=True)
        msg.outgoing = True
        msg._client = Mock()
        msg._client.me = Mock(id=12345)
        msg.delete = AsyncMock(side_effect=Exception("Permission denied"))
        
        # Mock Altruix
        with patch('Main.core.types.message.Altruix') as mock_altruix:
            mock_altruix.clients = [msg._client]
            mock_altruix.config.get_env = AsyncMock(side_effect=[
                "per_account",  # AUTO_DELETE_CMD_TYPE
                "on",           # AUTO_DELETE_CMD_STATUS
                "0"             # AUTO_DELETE_CMD_DELAY
            ])
            mock_altruix.log = Mock()
            
            # Call delete_if_self
            result = await Message.delete_if_self(msg)
            
            # Should return self without crashing
            assert result == msg
            
            # Should log permission error at INFO level (20)
            log_calls = mock_altruix.log.call_args_list
            permission_logs = [call for call in log_calls if "Permission denied" in str(call)]
            assert len(permission_logs) > 0
    
    @pytest.mark.asyncio
    async def test_invalid_config_type_uses_default(self):
        """Test that invalid AUTO_DELETE_CMD_TYPE uses default 'per_account'"""
        # Create mock message
        msg = Mock(spec=Message)
        msg.from_user = Mock(is_self=True)
        msg.outgoing = True
        msg._client = Mock()
        msg._client.me = Mock(id=12345)
        
        # Mock Altruix
        with patch('Main.core.types.message.Altruix') as mock_altruix:
            mock_altruix.clients = [msg._client]
            
            # Return invalid type value
            call_count = 0
            async def mock_get_env(key):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return "invalid_type"  # Invalid type
                elif call_count == 2:
                    return "off"  # Status
                return None
            
            mock_altruix.config.get_env = mock_get_env
            mock_altruix.log = Mock()
            
            # Call delete_if_self
            result = await Message.delete_if_self(msg)
            
            # Should return self (auto-delete disabled)
            assert result == msg
            
            # Should log invalid config warning
            log_calls = [str(call) for call in mock_altruix.log.call_args_list]
            assert any("Invalid AUTO_DELETE_CMD_TYPE" in str(call) for call in log_calls)
    
    @pytest.mark.asyncio
    async def test_invalid_enabled_value_uses_default(self):
        """Test that invalid enabled value defaults to disabled"""
        # Create mock message
        msg = Mock(spec=Message)
        msg.from_user = Mock(is_self=True)
        msg.outgoing = True
        msg._client = Mock()
        msg._client.me = Mock(id=12345)
        
        # Mock Altruix
        with patch('Main.core.types.message.Altruix') as mock_altruix:
            mock_altruix.clients = [msg._client]
            mock_altruix.config.get_env = AsyncMock(side_effect=[
                "per_account",      # AUTO_DELETE_CMD_TYPE
                "invalid_value",    # AUTO_DELETE_CMD_STATUS (invalid)
                "0"                 # AUTO_DELETE_CMD_DELAY
            ])
            mock_altruix.log = Mock()
            
            # Call delete_if_self
            result = await Message.delete_if_self(msg)
            
            # Should return self (treated as disabled)
            assert result == msg
            
            # Should log invalid enabled value warning
            log_calls = [str(call) for call in mock_altruix.log.call_args_list]
            assert any("Invalid enabled value" in str(call) for call in log_calls)
    
    @pytest.mark.asyncio
    async def test_invalid_delay_value_uses_default(self):
        """Test that invalid delay value defaults to 0"""
        # Create mock message
        msg = Mock(spec=Message)
        msg.from_user = Mock(is_self=True)
        msg.outgoing = True
        msg._client = Mock()
        msg._client.me = Mock(id=12345)
        msg.delete = AsyncMock(return_value=msg)
        
        # Mock Altruix
        with patch('Main.core.types.message.Altruix') as mock_altruix:
            mock_altruix.clients = [msg._client]
            mock_altruix.config.get_env = AsyncMock(side_effect=[
                "per_account",      # AUTO_DELETE_CMD_TYPE
                "on",               # AUTO_DELETE_CMD_STATUS
                "not_a_number"      # AUTO_DELETE_CMD_DELAY (invalid)
            ])
            mock_altruix.log = Mock()
            
            # Call delete_if_self
            result = await Message.delete_if_self(msg)
            
            # Should still delete (with 0 delay)
            msg.delete.assert_called_once()
            
            # Should log failed to parse delay warning
            log_calls = [str(call) for call in mock_altruix.log.call_args_list]
            assert any("Failed to parse delay" in str(call) for call in log_calls)
    
    @pytest.mark.asyncio
    async def test_negative_delay_uses_zero(self):
        """Test that negative delay value is clamped to 0"""
        # Create mock message
        msg = Mock(spec=Message)
        msg.from_user = Mock(is_self=True)
        msg.outgoing = True
        msg._client = Mock()
        msg._client.me = Mock(id=12345)
        msg.delete = AsyncMock(return_value=msg)
        
        # Mock Altruix
        with patch('Main.core.types.message.Altruix') as mock_altruix:
            mock_altruix.clients = [msg._client]
            mock_altruix.config.get_env = AsyncMock(side_effect=[
                "per_account",  # AUTO_DELETE_CMD_TYPE
                "on",           # AUTO_DELETE_CMD_STATUS
                "-5"            # AUTO_DELETE_CMD_DELAY (negative)
            ])
            mock_altruix.log = Mock()
            
            # Call delete_if_self
            result = await Message.delete_if_self(msg)
            
            # Should still delete (with 0 delay)
            msg.delete.assert_called_once()
            
            # Should log invalid delay warning
            log_calls = [str(call) for call in mock_altruix.log.call_args_list]
            assert any("Invalid delay value" in str(call) and "negative" in str(call) for call in log_calls)
    
    @pytest.mark.asyncio
    async def test_error_logging_levels(self):
        """Test that errors are logged with appropriate levels"""
        # Create mock message
        msg = Mock(spec=Message)
        msg.from_user = Mock(is_self=True)
        msg.outgoing = True
        msg._client = Mock()
        msg._client.me = Mock(id=12345)
        
        # Mock Altruix
        with patch('Main.core.types.message.Altruix') as mock_altruix:
            mock_altruix.clients = [msg._client]
            mock_altruix.config.get_env = AsyncMock(side_effect=Exception("DB Error"))
            mock_altruix.log = Mock()
            
            # Call delete_if_self
            await Message.delete_if_self(msg)
            
            # Check that database error is logged at WARNING level (30)
            log_calls = mock_altruix.log.call_args_list
            db_error_logs = [call for call in log_calls if "Database error" in str(call)]
            assert len(db_error_logs) > 0
            
            # Verify level 30 (WARNING) is used
            for call in db_error_logs:
                if "level" in str(call):
                    assert "level=30" in str(call)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
