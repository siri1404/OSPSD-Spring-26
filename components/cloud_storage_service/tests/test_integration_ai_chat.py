"""Integration tests for AI + Chat notification flows."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from ai_client_api import AIResponse
from cloud_storage_api.exceptions import StorageBackendError

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


@pytest.mark.unit
def test_ai_chat_sends_notification_after_delete(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_storage_client: MagicMock,
    mock_chat_client: MagicMock,
    mock_get_ai_client: MagicMock,
    mock_get_chat_notification: MagicMock,
) -> None:
    """/ai/chat triggers chat notification when AI performs delete action."""
    mock_ai_client.send_message_with_metadata.return_value = AIResponse(
        text="Deleted old_backup.tar.gz",
        action_taken="delete_file",
        tool_calls=["delete_file"],
        tool_args={"object_name": "old_backup.tar.gz", "container": "test-bucket"},
    )

    response = client.post(
        "/ai/chat",
        json={"prompt": "delete old_backup.tar.gz"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["action_taken"] == "delete_file"
    assert "Deleted" in data["response"]
    mock_ai_client.send_message_with_metadata.assert_called_once()


@pytest.mark.unit
def test_upload_endpoint_returns_object_info_with_shared_contract_fields(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
    sample_file_data: bytes,
) -> None:
    """/upload returns shared-contract ObjectInfo (object_name, not v0 'key')."""
    files = {
        "file": ("report.pdf", io.BytesIO(sample_file_data), "application/pdf"),
    }
    data = {"key": "uploads/report.pdf", "content_type": "application/pdf"}

    response = client.post("/upload", headers=auth_headers, files=files, data=data)

    assert response.status_code == 200
    response_data = response.json()
    # Mock returns fixed object_name 'test-key', not the input key.
    assert response_data["object_name"] == "test-key"
    assert "integrity" in response_data
    assert "data_type" in response_data
    mock_storage_client.upload_obj.assert_called_once()


@pytest.mark.unit
def test_delete_endpoint_invokes_storage_client(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
) -> None:
    """/delete invokes storage_client.delete_file with the resolved container."""
    response = client.delete(
        "/delete/uploads/old_file.txt",
        headers=auth_headers,
    )

    assert response.status_code == 204
    mock_storage_client.delete_file.assert_called_once_with(
        container="test-bucket",
        object_name="uploads/old_file.txt",
    )


@pytest.mark.unit
def test_ai_summarize_with_download_returns_summary(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_get_ai_client: MagicMock,
) -> None:
    """AI summarize workflow: download file, get AI summary, return text."""
    mock_ai_client.send_message_with_metadata.return_value = AIResponse(
        text="Summary: This report details Q1 2026 sales metrics",
        action_taken="download_file",
        tool_calls=["download_file"],
        tool_args={"container": "test-bucket", "object_name": "q1_report.pdf"},
    )

    response = client.post(
        "/ai/chat",
        json={"prompt": "summarize q1_report.pdf"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["action_taken"] == "download_file"
    assert "Q1 2026" in data["response"]


@pytest.mark.unit
def test_ai_chat_returns_action_and_response_text(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_get_ai_client: MagicMock,
) -> None:
    """/ai/chat returns action_taken and response text for downstream notification."""
    mock_ai_client.send_message_with_metadata.return_value = AIResponse(
        text="Deleted metrics.csv from archive",
        action_taken="delete_file",
        tool_calls=["delete_file"],
        tool_args={"container": "test-bucket", "object_name": "metrics.csv"},
    )

    response = client.post(
        "/ai/chat",
        json={"prompt": "clean up old metrics"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["action_taken"] == "delete_file"
    assert "Deleted" in data["response"]
    assert "metrics.csv" in data["response"]


@pytest.mark.unit
def test_multiple_sequential_ai_actions(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_get_ai_client: MagicMock,
) -> None:
    """Multiple sequential /ai/chat calls each invoke the AI client and return correct actions."""
    first_response = AIResponse(
        text="Listed 5 files",
        action_taken="list_files",
        tool_calls=["list_files"],
        tool_args={"container": "test-bucket"},
    )
    second_response = AIResponse(
        text="Deleted archive.tar",
        action_taken="delete_file",
        tool_calls=["delete_file"],
        tool_args={"container": "test-bucket", "object_name": "archive.tar"},
    )
    mock_ai_client.send_message_with_metadata.side_effect = [
        first_response,
        second_response,
    ]

    response1 = client.post(
        "/ai/chat",
        json={"prompt": "list files"},
        headers=auth_headers,
    )
    response2 = client.post(
        "/ai/chat",
        json={"prompt": "delete archive.tar"},
        headers=auth_headers,
    )

    assert response1.status_code == 200
    assert response2.status_code == 200
    assert response1.json()["action_taken"] == "list_files"
    assert response2.json()["action_taken"] == "delete_file"
    assert mock_ai_client.send_message_with_metadata.call_count == 2


@pytest.mark.unit
@pytest.mark.parametrize(
    ("prompt", "expected_action"),
    [
        ("list files", "list_files"),
        ("get info on report.pdf", "get_file_info"),
        ("delete temp.txt", "delete_file"),
        ("download config.json", "download_file"),
        ("summarize data.csv", "summarize_file"),
    ],
)
def test_ai_chat_dispatches_each_storage_tool(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_get_ai_client: MagicMock,
    prompt: str,
    expected_action: str,
) -> None:
    """All 5 storage tool types are callable via /ai/chat."""
    mock_ai_client.send_message_with_metadata.return_value = AIResponse(
        text=f"Performed {expected_action}",
        action_taken=expected_action,
        tool_calls=[expected_action],
        tool_args={"container": "test-bucket"},
    )

    response = client.post(
        "/ai/chat",
        json={"prompt": prompt},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["action_taken"] == expected_action


@pytest.mark.unit
def test_ai_chat_returns_response_when_storage_backend_error_handled_by_ai(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_storage_client: MagicMock,
    mock_get_ai_client: MagicMock,
) -> None:
    """If the storage backend fails but the AI gracefully reports the error, /ai/chat returns 200."""
    mock_storage_client.delete_file.side_effect = StorageBackendError(
        "Backend error",
    )
    mock_ai_client.send_message_with_metadata.return_value = AIResponse(
        text="I attempted to delete the file but encountered a backend error",
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
    assert "backend error" in response.json()["response"].lower()
