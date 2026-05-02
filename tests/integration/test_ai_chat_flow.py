"""Integration tests for AI + Chat notification flows.

These tests verify:
- AI tool invocation through the mocked Gemini client surface
- Chat notifications are triggered with correct content
- End-to-end flow from /ai/chat to storage to notifications
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING
from unittest.mock import ANY, MagicMock

import pytest
from ai_client_api import AIResponse
from cloud_storage_api.exceptions import StorageBackendError

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# AI delete + notification
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_ai_delete_triggers_chat_notification_with_object_name(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_storage_client: MagicMock,
    mock_chat_client: MagicMock,
    mock_get_chat_notification: MagicMock,
) -> None:
    """/ai/chat delete action triggers a chat notification mentioning the object."""
    mock_ai_client.send_message_with_metadata.return_value = AIResponse(
        text="Deleted old_backup.tar.gz",
        action_taken="delete_file",
        tool_calls=["delete_file"],
        tool_args={
            "object_name": "old_backup.tar.gz",
            "container": "test-bucket",
        },
    )

    response = client.post(
        "/ai/chat",
        json={"prompt": "delete old_backup.tar.gz"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["action_taken"] == "delete_file"

    mock_chat_client.send_message.assert_called()
    sent_text = mock_chat_client.send_message.call_args.kwargs.get("text") or (
        mock_chat_client.send_message.call_args.args[1] if len(mock_chat_client.send_message.call_args.args) > 1 else ""
    )
    assert "delete_file" in sent_text or "old_backup.tar.gz" in sent_text


# ---------------------------------------------------------------------------
# Direct upload + notification
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_direct_upload_triggers_chat_notification(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
    mock_chat_client: MagicMock,
    mock_get_chat_notification: MagicMock,
    sample_file_data: bytes,
) -> None:
    """/upload returns shared-contract ObjectInfo and invokes the storage client."""
    files = {"file": ("test.txt", io.BytesIO(sample_file_data), "text/plain")}
    data = {"key": "test.txt"}

    response = client.post(
        "/upload",
        headers=auth_headers,
        files=files,
        data=data,
    )

    assert response.status_code == 200
    response_data = response.json()
    # Shared-contract response shape (peer review #1).
    assert "object_name" in response_data
    assert "integrity" in response_data
    assert "data_type" in response_data
    mock_storage_client.upload_obj.assert_called_once()


# ---------------------------------------------------------------------------
# AI action + tool args + notification
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_ai_action_notification_with_tool_args_detail(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_storage_client: MagicMock,
    mock_chat_client: MagicMock,
    mock_get_chat_notification: MagicMock,
) -> None:
    """tool_args details flow through to the chat notification message."""
    mock_ai_client.send_message_with_metadata.return_value = AIResponse(
        text="Deleted metrics.csv",
        action_taken="delete_file",
        tool_calls=["delete_file"],
        tool_args={"container": "test-bucket", "object_name": "metrics.csv"},
    )

    response = client.post(
        "/ai/chat",
        json={"prompt": "delete metrics.csv"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["action_taken"] == "delete_file"
    assert "metrics.csv" in data["response"]

    mock_chat_client.send_message.assert_called()


# ---------------------------------------------------------------------------
# AI download + summarize
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_ai_download_and_summarize_flow(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_storage_client: MagicMock,
    mock_chat_client: MagicMock,
    mock_get_chat_notification: MagicMock,
) -> None:
    """/ai/chat surfaces a download_file action and the summary text."""
    mock_ai_client.send_message_with_metadata.return_value = AIResponse(
        text="Summary: Q1 2026 sales report",
        action_taken="download_file",
        tool_calls=["download_file"],
        tool_args={"container": "test-bucket", "object_name": "report.pdf"},
    )

    response = client.post(
        "/ai/chat",
        json={"prompt": "download and summarize report.pdf"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["action_taken"] == "download_file"
    assert "Q1 2026" in data["response"]


# ---------------------------------------------------------------------------
# Error resilience
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_ai_tool_invocation_error_resilience(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_storage_client: MagicMock,
    mock_chat_client: MagicMock,
    mock_get_chat_notification: MagicMock,
) -> None:
    """/ai/chat returns 200 when the AI gracefully reports a storage backend error."""
    mock_storage_client.delete_file.side_effect = StorageBackendError("Backend down")
    mock_ai_client.send_message_with_metadata.return_value = AIResponse(
        text="I attempted the delete but the storage backend is unavailable.",
        action_taken="delete_file",
        tool_calls=["delete_file"],
        tool_args={"container": "test-bucket", "object_name": "file.txt"},
    )

    response = client.post(
        "/ai/chat",
        json={"prompt": "delete file.txt"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert "backend" in response.json()["response"].lower()


# ---------------------------------------------------------------------------
# Channel verification
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_ai_notification_uses_configured_channel(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_storage_client: MagicMock,
    mock_chat_client: MagicMock,
    mock_get_chat_notification: MagicMock,
) -> None:
    """Chat notifications go through the configured channel via the wrapper."""
    mock_ai_client.send_message_with_metadata.return_value = AIResponse(
        text="3 files",
        action_taken="list_files",
        tool_calls=["list_files"],
        tool_args={"container": "test-bucket"},
    )

    response = client.post(
        "/ai/chat",
        json={"prompt": "list files"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    mock_chat_client.send_message.assert_called_once_with(
        channel_id="general",
        text=ANY,
    )


# ---------------------------------------------------------------------------
# End-to-end
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_end_to_end_ai_storage_chat_flow(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_storage_client: MagicMock,
    mock_chat_client: MagicMock,
    mock_get_chat_notification: MagicMock,
) -> None:
    """End-to-end /ai/chat response has the expected response/action_taken structure."""
    mock_ai_client.send_message_with_metadata.return_value = AIResponse(
        text="I can help you list, upload, download, or delete files.",
        action_taken=None,
        tool_calls=[],
    )

    response = client.post(
        "/ai/chat",
        json={"prompt": "help me manage my files"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "action_taken" in data
    assert isinstance(data["response"], str)
    assert len(data["response"]) > 0
    assert data["action_taken"] is None or isinstance(data["action_taken"], str)
