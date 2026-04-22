"""Unit tests for chat notification wrapper."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from chat_client_api import Message  # type: ignore[import-untyped]
from chat_client_wrapper import ChatNotificationWrapper
from chat_client_wrapper.notifications import NotificationMessages


@pytest.fixture
def mock_chat_client() -> MagicMock:
    """Create a mock ChatClient from shared chat-client-api.

    Returns:
        Mock ChatClient instance that returns Message objects.
    """
    mock = MagicMock()
    mock.send_message.return_value = Message(
        message_id="msg_123",
        channel="test-channel",
        text="Test notification",
        sender="cloud-storage-service",
        timestamp=datetime.now(),
    )
    return mock


@pytest.mark.unit
def test_chat_notification_wrapper_initialization(mock_chat_client: MagicMock) -> None:
    """Test ChatNotificationWrapper initialization."""
    wrapper = ChatNotificationWrapper(
        chat_client=mock_chat_client,
        channel_id="test-channel",
    )

    assert wrapper is not None
    assert wrapper._channel_id == "test-channel"


@pytest.mark.unit
def test_chat_notification_wrapper_requires_channel_id(
    mock_chat_client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that channel_id is required."""
    # Ensure CHAT_CHANNEL_ID env var is not set
    monkeypatch.delenv("CHAT_CHANNEL_ID", raising=False)

    with pytest.raises(ValueError, match="channel_id must be provided"):
        ChatNotificationWrapper(chat_client=mock_chat_client)


@pytest.mark.unit
def test_chat_notification_wrapper_uses_env_var(
    mock_chat_client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that CHAT_CHANNEL_ID env var is used."""
    monkeypatch.setenv("CHAT_CHANNEL_ID", "env-channel")
    wrapper = ChatNotificationWrapper(chat_client=mock_chat_client)

    assert wrapper._channel_id == "env-channel"


@pytest.mark.unit
def test_notify_sends_message(mock_chat_client: MagicMock) -> None:
    """Test notify() sends message to chat client."""
    wrapper = ChatNotificationWrapper(
        chat_client=mock_chat_client,
        channel_id="test-channel",
    )

    result = wrapper.notify("Test notification")

    mock_chat_client.send_message.assert_called_once_with(
        channel_id="test-channel",
        text="Test notification",
    )
    assert result["message_id"] == "msg_123"
    assert result["channel"] == "test-channel"


@pytest.mark.unit
def test_notify_raises_on_empty_message(mock_chat_client: MagicMock) -> None:
    """Test notify() rejects empty messages."""
    wrapper = ChatNotificationWrapper(
        chat_client=mock_chat_client,
        channel_id="test-channel",
    )

    with pytest.raises(ValueError, match="non-empty string"):
        wrapper.notify("")


@pytest.mark.unit
def test_notify_raises_on_invalid_message_type(mock_chat_client: MagicMock) -> None:
    """Test notify() rejects non-string messages."""
    wrapper = ChatNotificationWrapper(
        chat_client=mock_chat_client,
        channel_id="test-channel",
    )

    with pytest.raises(ValueError, match="non-empty string"):
        wrapper.notify(None)  # type: ignore[arg-type]


@pytest.mark.unit
def test_notify_wraps_chat_client_exception(mock_chat_client: MagicMock) -> None:
    """Test notify() wraps chat client exceptions."""
    mock_chat_client.send_message.side_effect = RuntimeError("Chat service down")

    wrapper = ChatNotificationWrapper(
        chat_client=mock_chat_client,
        channel_id="test-channel",
    )

    with pytest.raises(RuntimeError, match="Failed to send notification"):
        wrapper.notify("Test message")


@pytest.mark.unit
def test_notification_message_file_uploaded() -> None:
    """Test file uploaded message format."""
    msg = NotificationMessages.file_uploaded(
        container="my-bucket",
        object_name="documents/report.pdf",
        size_bytes=2048,
    )

    assert "📤" in msg
    assert "report.pdf" in msg
    assert "my-bucket" in msg
    assert "2048 bytes" in msg


@pytest.mark.unit
def test_notification_message_file_uploaded_without_size() -> None:
    """Test file uploaded message format without size."""
    msg = NotificationMessages.file_uploaded(
        container="my-bucket",
        object_name="documents/report.pdf",
    )

    assert "📤" in msg
    assert "report.pdf" in msg
    assert "my-bucket" in msg
    assert "bytes" not in msg


@pytest.mark.unit
def test_notification_message_file_deleted() -> None:
    """Test file deleted message format."""
    msg = NotificationMessages.file_deleted(
        container="my-bucket",
        object_name="documents/temp.txt",
    )

    assert "🗑️" in msg
    assert "temp.txt" in msg
    assert "my-bucket" in msg


@pytest.mark.unit
def test_notification_message_ai_action_performed() -> None:
    """Test AI action performed message format."""
    msg = NotificationMessages.ai_action_performed(
        action="list_files",
        container="my-bucket",
        result="Found 42 files",
    )

    assert "🤖" in msg
    assert "list_files" in msg
    assert "my-bucket" in msg
    assert "Found 42 files" in msg


@pytest.mark.unit
def test_notification_message_ai_action_with_object() -> None:
    """Test AI action message with object name."""
    msg = NotificationMessages.ai_action_performed(
        action="delete_file",
        container="my-bucket",
        object_name="temp.txt",
    )

    assert "delete_file" in msg
    assert "temp.txt" in msg


@pytest.mark.unit
def test_notification_message_error_occurred() -> None:
    """Test error occurred message format."""
    msg = NotificationMessages.error_occurred(
        error_type="AuthenticationError",
        message="Invalid credentials",
        context="Uploading file to bucket",
    )

    assert "⚠️" in msg
    assert "AuthenticationError" in msg
    assert "Invalid credentials" in msg
    assert "Uploading file to bucket" in msg


@pytest.mark.unit
def test_notification_message_error_without_context() -> None:
    """Test error message without context."""
    msg = NotificationMessages.error_occurred(
        error_type="FileNotFound",
        message="Object does not exist",
    )

    assert "⚠️" in msg
    assert "FileNotFound" in msg
    assert "does not exist" in msg


@pytest.mark.unit
def test_notify_full_workflow(mock_chat_client: MagicMock) -> None:
    """Test full notification workflow."""
    wrapper = ChatNotificationWrapper(
        chat_client=mock_chat_client,
        channel_id="notifications",
    )

    # Send upload notification
    upload_msg = NotificationMessages.file_uploaded("data-bucket", "export.csv", 1024)
    result = wrapper.notify(upload_msg)

    assert result["message_id"] == "msg_123"
    assert mock_chat_client.send_message.call_count == 1

    # Send delete notification
    delete_msg = NotificationMessages.file_deleted("data-bucket", "export.csv")
    result = wrapper.notify(delete_msg)

    assert result["message_id"] == "msg_123"
    assert mock_chat_client.send_message.call_count == 2

    # Verify both calls used correct parameter names
    calls = mock_chat_client.send_message.call_args_list
    assert calls[0][1]["text"] is not None
    assert calls[1][1]["text"] is not None
    assert "uploaded" in calls[0][1]["text"].lower()
    assert "deleted" in calls[1][1]["text"].lower()
