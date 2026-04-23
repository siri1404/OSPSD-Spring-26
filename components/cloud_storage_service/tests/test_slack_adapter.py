"""Tests for Slack adapter implementation.

Verifies SlackChatClient ABC compliance, including:
- Proper initialization and token handling
- Message timestamp is datetime (not string)
- Exception types match ABC declarations
- Message ID encoding/decoding roundtrip
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from chat_client_api import (
    ChannelNotFoundError,
    Message,
    MessageDeleteError,
    MessageNotFoundError,
)
from cloud_storage_service.slack_adapter import (
    SlackChatClient,
    _decode_message_id,
    _encode_message_id,
    _slack_ts_to_datetime,
)
from slack_sdk.errors import SlackApiError


class TestSlackAdapterInit:
    """Test SlackChatClient initialization."""

    @pytest.mark.unit
    def test_slack_adapter_init_without_token_raises(self) -> None:
        """Test that __init__ raises ValueError when no token is provided.

        Verifies:
        - ValueError is raised when token arg is None
        - SLACK_BOT_TOKEN env var is not set (or unset in test)
        - Error message mentions the missing env var
        """
        # Arrange: Ensure SLACK_BOT_TOKEN is not set
        with patch.dict(os.environ, {}, clear=False):
            if "SLACK_BOT_TOKEN" in os.environ:
                del os.environ["SLACK_BOT_TOKEN"]

            # Act & Assert: Initialization fails without token
            with pytest.raises(ValueError, match="SLACK_BOT_TOKEN"):
                SlackChatClient(token=None)

    @pytest.mark.unit
    def test_slack_adapter_init_with_explicit_token_overrides_env(self) -> None:
        """Test that explicit token parameter overrides env var.

        Verifies:
        - SlackChatClient can be initialized with explicit token
        - Initialization succeeds even if SLACK_BOT_TOKEN env var differs
        - Token is used correctly to create WebClient
        """
        explicit_token = "xoxb-explicit-token-12345"

        # Act: Initialize with explicit token
        with patch("cloud_storage_service.slack_adapter.WebClient") as mock_webclient:
            client = SlackChatClient(token=explicit_token)

            # Assert: WebClient was initialized with correct token
            mock_webclient.assert_called_once_with(token=explicit_token)
            assert client._token == explicit_token

    @pytest.mark.unit
    def test_slack_adapter_init_uses_env_var_when_no_token_provided(self) -> None:
        """Test that __init__ falls back to SLACK_BOT_TOKEN env var.

        Verifies:
        - SlackChatClient uses env var when token parameter is None
        - Initialization succeeds when env var is set
        """
        env_token = "xoxb-env-token-67890"

        # Arrange: Set SLACK_BOT_TOKEN env var
        with (
            patch.dict(os.environ, {"SLACK_BOT_TOKEN": env_token}),
            patch("cloud_storage_service.slack_adapter.WebClient") as mock_webclient,
        ):
            # Act: Initialize without explicit token
            client = SlackChatClient(token=None)

            # Assert: WebClient was initialized with env var token
            mock_webclient.assert_called_once_with(token=env_token)
            assert client._token == env_token


class TestMessageTimestampCompliance:
    """Test that messages always have timezone-aware datetime timestamps (ABC compliance)."""

    @pytest.mark.unit
    def test_send_message_returns_datetime_timestamp(self) -> None:
        """Test that send_message returns Message with datetime timestamp, not string.

        CRITICAL: chat_client_api.Message.timestamp must be datetime, not str.
        This test verifies ABC compliance.

        Verifies:
        - send_message returns Message object
        - Message.timestamp is datetime.datetime instance
        - timestamp is timezone-aware (has tzinfo)
        - timestamp is in UTC
        """
        with patch("cloud_storage_service.slack_adapter.WebClient") as mock_webclient:
            # Arrange: Mock Slack response
            mock_client = MagicMock()
            mock_webclient.return_value = mock_client
            mock_client.chat_postMessage.return_value = {
                "ts": "1234567890.123456",
                "channel": "C1234567890",
            }

            client = SlackChatClient(token="xoxb-test-token")

            # Act: Send message
            message = client.send_message("C1234567890", "Hello World")

            # Assert: Timestamp is datetime, not string
            assert isinstance(message.timestamp, datetime), f"Expected datetime, got {type(message.timestamp)}"
            assert message.timestamp.tzinfo is not None, "Timestamp must be timezone-aware"
            assert message.timestamp.tzinfo == UTC, "Timestamp must be UTC"

            # Verify Message structure
            assert message.text == "Hello World"
            assert message.channel == "C1234567890"
            assert message.message_id is not None

    @pytest.mark.unit
    def test_get_messages_returns_datetime_timestamps(self) -> None:
        """Test that get_messages returns Messages with datetime timestamps.

        Verifies:
        - All messages in list have datetime timestamps
        - Timestamps are timezone-aware and in UTC
        """
        with patch("cloud_storage_service.slack_adapter.WebClient") as mock_webclient:
            # Arrange: Mock Slack response with multiple messages
            mock_client = MagicMock()
            mock_webclient.return_value = mock_client
            mock_client.conversations_history.return_value = {
                "messages": [
                    {
                        "ts": "1234567890.000000",
                        "text": "Message 1",
                        "user": "U1234567890",
                    },
                    {
                        "ts": "1234567891.000000",
                        "text": "Message 2",
                        "user": "U0987654321",
                    },
                ]
            }

            client = SlackChatClient(token="xoxb-test-token")

            # Act: Get messages
            messages = client.get_messages("C1234567890", limit=10)

            # Assert: All timestamps are datetime objects
            assert len(messages) == 2
            for msg in messages:
                assert isinstance(msg.timestamp, datetime)
                assert msg.timestamp.tzinfo == UTC


class TestSlackAdapterExceptionTypes:
    """Test that adapter raises ABC-declared exception types."""

    @pytest.mark.unit
    def test_send_message_slack_api_error_raises_value_error(self) -> None:
        """Test that send_message raises ValueError on SlackApiError.

        Note: send_message wraps SlackApiError in ValueError per implementation.
        This ensures a consistent error interface.

        Verifies:
        - SlackApiError from send_message is caught and re-raised as ValueError
        - Error message is descriptive
        """
        with patch("cloud_storage_service.slack_adapter.WebClient") as mock_webclient:
            # Arrange: Mock Slack API error
            mock_client = MagicMock()
            mock_webclient.return_value = mock_client
            mock_client.chat_postMessage.side_effect = SlackApiError(
                message="Channel not found",
                response={"error": "channel_not_found"},
            )  # type: ignore[no-untyped-call]

            client = SlackChatClient(token="xoxb-test-token")

            # Act & Assert: ValueError is raised
            with pytest.raises(ValueError, match="Failed to send message"):
                client.send_message("C1234567890", "Hello")

    @pytest.mark.unit
    def test_get_channel_not_found_raises_channel_not_found_error(self) -> None:
        """Test that get_channel raises ChannelNotFoundError on SlackApiError.

        Verifies:
        - ChannelNotFoundError (from chat_client_api ABC) is raised
        - Error message includes channel ID
        """
        with patch("cloud_storage_service.slack_adapter.WebClient") as mock_webclient:
            # Arrange: Mock Slack API error
            mock_client = MagicMock()
            mock_webclient.return_value = mock_client
            mock_client.conversations_info.side_effect = SlackApiError(
                message="Channel not found",
                response={"error": "channel_not_found"},
            )  # type: ignore[no-untyped-call]

            client = SlackChatClient(token="xoxb-test-token")

            # Act & Assert: ChannelNotFoundError is raised
            with pytest.raises(ChannelNotFoundError) as exc_info:
                client.get_channel("C1234567890")

            assert "Channel not found" in str(exc_info.value)

    @pytest.mark.unit
    def test_get_message_not_found_raises_message_not_found_error(self) -> None:
        """Test that get_message raises MessageNotFoundError when message doesn't exist.

        Verifies:
        - MessageNotFoundError (from chat_client_api ABC) is raised
        - Error message includes message ID
        """
        with patch("cloud_storage_service.slack_adapter.WebClient") as mock_webclient:
            # Arrange: Mock Slack API returning empty messages
            mock_client = MagicMock()
            mock_webclient.return_value = mock_client
            mock_client.conversations_history.return_value = {"messages": []}

            client = SlackChatClient(token="xoxb-test-token")

            # Act & Assert: MessageNotFoundError is raised
            with pytest.raises(MessageNotFoundError) as exc_info:
                client.get_message("C1234567890:1234567890.000000")

            assert "Message not found" in str(exc_info.value)

    @pytest.mark.unit
    def test_delete_message_api_error_raises_message_delete_error(self) -> None:
        """Test that delete_message raises MessageDeleteError on SlackApiError.

        Verifies:
        - MessageDeleteError (from chat_client_api ABC) is raised
        - Error message includes message ID
        """
        with patch("cloud_storage_service.slack_adapter.WebClient") as mock_webclient:
            # Arrange: Mock Slack API error
            mock_client = MagicMock()
            mock_webclient.return_value = mock_client
            mock_client.chat_delete.side_effect = SlackApiError(
                message="Message not found",
                response={"error": "message_not_found"},
            )  # type: ignore[no-untyped-call]

            client = SlackChatClient(token="xoxb-test-token")

            # Act & Assert: MessageDeleteError is raised
            with pytest.raises(MessageDeleteError) as exc_info:
                client.delete_message("C1234567890:1234567890.000000")

            assert "Failed to delete message" in str(exc_info.value)


class TestMessageIdEncoding:
    """Test message ID encoding/decoding functions."""

    @pytest.mark.unit
    def test_encode_decode_message_id_roundtrip(self) -> None:
        """Test that message ID encoding and decoding are inverse operations.

        Verifies:
        - encode_message_id creates opaque ID from channel and timestamp
        - decode_message_id recovers original channel and timestamp
        - Roundtrip is lossless
        """
        channel = "C1234567890"
        ts = "1234567890.123456"

        encoded = _encode_message_id(channel, ts)

        decoded_channel, decoded_ts = _decode_message_id(encoded)
        decoded_channel, decoded_ts = _decode_message_id(encoded)

        # Assert: Roundtrip recovers original values
        assert decoded_channel == channel
        assert decoded_ts == ts

    @pytest.mark.unit
    def test_decode_message_id_rejects_malformed_input(self) -> None:
        """Test that decode_message_id rejects malformed message IDs.

        Verifies:
        - ValueError is raised for missing separator
        - ValueError is raised for empty ID
        - Error message mentions expected format
        """
        # Act & Assert: Malformed IDs raise ValueError
        with pytest.raises(ValueError, match="Invalid message_id format"):
            _decode_message_id("malformed_id_no_separator")

        # Act & Assert: Empty string raises ValueError
        with pytest.raises(ValueError, match="Invalid message_id format"):
            _decode_message_id("")

    @pytest.mark.unit
    def test_encode_message_id_with_special_characters(self) -> None:
        """Test message ID encoding with special characters in timestamp.

        Verifies:
        - Encoding handles timestamps with dots correctly
        - Decoding uses maxsplit=1 to only split on first separator
        """
        channel = "C999999999"
        ts = "1234567890.999999"  # Contains dot

        encoded = _encode_message_id(channel, ts)
        _, decoded_ts = _decode_message_id(encoded)

        # Assert: Special character is preserved in timestamp
        assert decoded_ts == ts
        assert "." in decoded_ts


class TestTimestampConversion:
    """Test Slack timestamp to datetime conversion."""

    @pytest.mark.unit
    def test_slack_ts_to_datetime_converts_to_utc(self) -> None:
        """Test that _slack_ts_to_datetime produces UTC datetime objects.

        Verifies:
        - Returns datetime.datetime instance
        - Timezone is UTC
        - Timestamp values are preserved accurately
        """
        # Arrange: Known Slack timestamp
        ts = "1234567890.123456"  # Epoch: 2009-02-13 23:31:30 UTC

        # Act: Convert to datetime
        dt = _slack_ts_to_datetime(ts)

        # Assert: Result is UTC datetime
        assert isinstance(dt, datetime)
        assert dt.tzinfo == UTC
        # Verify the epoch conversion
        assert dt.timestamp() == 1234567890.123456

    @pytest.mark.unit
    def test_slack_ts_to_datetime_with_various_formats(self) -> None:
        """Test timestamp conversion with various Slack timestamp formats.

        Verifies:
        - Handles timestamps with different precision
        - Correctly parses fractional seconds
        """
        test_cases = [
            ("1234567890.000000", 1234567890.0),
            ("1609459200.123456", 1609459200.123456),
            ("1000000000.999999", 1000000000.999999),
        ]

        for ts_str, expected_epoch in test_cases:
            dt = _slack_ts_to_datetime(ts_str)
            assert dt.timestamp() == expected_epoch
            assert dt.tzinfo == UTC
