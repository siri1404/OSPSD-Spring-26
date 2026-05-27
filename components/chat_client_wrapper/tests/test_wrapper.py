"""Unit tests for chat notification wrapper."""

from __future__ import annotations

from datetime import UTC, datetime, timezone
from unittest.mock import MagicMock

import pytest
from chat_client_api import Message
from chat_client_wrapper import ChatNotificationWrapper
from chat_client_wrapper.notifications import NotificationMessages

_FIXED_TIMESTAMP = datetime(
    2026,
    1,
    1,
    12,
    0,
    0,
    tzinfo=UTC,
)


@pytest.fixture
def mock_chat_client() -> MagicMock:
    """Create a mock ChatClient from shared chat-client-api."""
    mock = MagicMock()

    mock.send_message.return_value = Message(
        message_id="msg_123",
        channel="test-channel",
        text="Test notification",
        sender="cloud-storage-service",
        timestamp=_FIXED_TIMESTAMP,
    )

    return mock


# ---------------------------------------------------------------------------
# ChatNotificationWrapper __init__
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_chat_notification_wrapper_initialization(
    mock_chat_client: MagicMock,
) -> None:
    """ChatNotificationWrapper initializes with explicit channel_id."""
    wrapper = ChatNotificationWrapper(
        chat_client=mock_chat_client,
        channel_id="test-channel",
    )

    assert wrapper.channel_id == "test-channel"


@pytest.mark.unit
def test_chat_notification_wrapper_requires_channel_id(
    mock_chat_client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """channel_id is required (via arg or env var)."""
    monkeypatch.delenv("CHAT_CHANNEL_ID", raising=False)

    with pytest.raises(
        ValueError,
        match="channel_id must be provided",
    ):
        ChatNotificationWrapper(chat_client=mock_chat_client)


@pytest.mark.unit
def test_chat_notification_wrapper_uses_env_var(
    mock_chat_client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CHAT_CHANNEL_ID env var is used when channel_id arg is omitted."""
    monkeypatch.setenv("CHAT_CHANNEL_ID", "env-channel")

    wrapper = ChatNotificationWrapper(
        chat_client=mock_chat_client,
    )

    assert wrapper.channel_id == "env-channel"


# ---------------------------------------------------------------------------
# notify
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_notify_sends_message(
    mock_chat_client: MagicMock,
) -> None:
    """notify() sends the message via the chat client and returns metadata."""
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
def test_notify_raises_on_empty_message(
    mock_chat_client: MagicMock,
) -> None:
    """notify() rejects empty messages."""
    wrapper = ChatNotificationWrapper(
        chat_client=mock_chat_client,
        channel_id="test-channel",
    )

    with pytest.raises(
        ValueError,
        match="non-empty string",
    ):
        wrapper.notify("")


@pytest.mark.unit
def test_notify_wraps_chat_client_exception(
    mock_chat_client: MagicMock,
) -> None:
    """notify() wraps chat client exceptions in RuntimeError."""
    mock_chat_client.send_message.side_effect = RuntimeError(
        "Chat service down",
    )

    wrapper = ChatNotificationWrapper(
        chat_client=mock_chat_client,
        channel_id="test-channel",
    )

    with pytest.raises(
        RuntimeError,
        match="Failed to send notification",
    ):
        wrapper.notify("Test message")


# ---------------------------------------------------------------------------
# NotificationMessages formatters
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_notification_message_file_uploaded() -> None:
    """file_uploaded includes container, object_name, and size."""
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
    """file_uploaded omits size when not provided."""
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
    """file_deleted includes container and object_name."""
    msg = NotificationMessages.file_deleted(
        container="my-bucket",
        object_name="documents/temp.txt",
    )

    assert "🗑️" in msg
    assert "temp.txt" in msg
    assert "my-bucket" in msg


@pytest.mark.unit
def test_notification_message_ai_action_performed() -> None:
    """ai_action_performed includes action, container, and result."""
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
    """ai_action_performed includes object_name when provided."""
    msg = NotificationMessages.ai_action_performed(
        action="delete_file",
        container="my-bucket",
        object_name="temp.txt",
    )

    assert "delete_file" in msg
    assert "temp.txt" in msg


@pytest.mark.unit
def test_notification_message_error_occurred() -> None:
    """error_occurred includes error_type, message, and context."""
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
    """error_occurred omits context when not provided."""
    msg = NotificationMessages.error_occurred(
        error_type="FileNotFound",
        message="Object does not exist",
    )

    assert "⚠️" in msg
    assert "FileNotFound" in msg
    assert "does not exist" in msg


# ---------------------------------------------------------------------------
# Integration with formatters
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_notify_full_workflow(
    mock_chat_client: MagicMock,
) -> None:
    """Full notification workflow: format, send, send another."""
    wrapper = ChatNotificationWrapper(
        chat_client=mock_chat_client,
        channel_id="notifications",
    )

    upload_msg = NotificationMessages.file_uploaded(
        "data-bucket",
        "export.csv",
        1024,
    )

    result_upload = wrapper.notify(upload_msg)

    assert result_upload["message_id"] == "msg_123"
    assert mock_chat_client.send_message.call_count == 1

    delete_msg = NotificationMessages.file_deleted(
        "data-bucket",
        "export.csv",
    )

    result_delete = wrapper.notify(delete_msg)

    assert result_delete["message_id"] == "msg_123"
    assert mock_chat_client.send_message.call_count == 2

    calls = mock_chat_client.send_message.call_args_list

    assert "uploaded" in calls[0].kwargs["text"].lower()
    assert "deleted" in calls[1].kwargs["text"].lower()
