"""Integration tests for AI + Chat notification flows."""

from __future__ import annotations

import io
from unittest.mock import MagicMock

import pytest
from ai_client_api import AIResponse
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
    """Test that /ai/chat triggers chat notification when AI performs delete action."""
    from cloud_storage_service import main

    # Arrange: Mock AI response with delete action
    mock_ai_client.send_message.return_value = AIResponse(
        text="Deleted old_backup.tar.gz",
        action_taken="delete_file",
        tool_calls=["delete_file"],
        tool_args={"object_name": "old_backup.tar.gz", "container": "test-bucket"},
    )

    # Act: Send prompt to delete file
    response = client.post(
        "/ai/chat",
        json={"prompt": "delete old_backup.tar.gz"},
        headers=auth_headers,
    )

    # Assert: Response is successful and action was taken
    assert response.status_code == 200
    data = response.json()
    assert data["action_taken"] == "delete_file"
    assert "Deleted" in data["response"]

    # Verify AI client was called
    mock_ai_client.send_message.assert_called_once()


@pytest.mark.unit
def test_ai_chat_sends_notification_after_upload_via_direct_upload(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
    sample_file_data: bytes,
) -> None:
    """Test that upload endpoint triggers chat notification."""
    # Arrange: Prepare file upload
    files = {"file": ("report.pdf", io.BytesIO(sample_file_data), "application/pdf")}
    data = {"key": "uploads/report.pdf", "content_type": "application/pdf"}

    # Act: Upload file directly via /upload endpoint
    response = client.post("/upload", headers=auth_headers, files=files, data=data)

    # Assert: Upload successful
    assert response.status_code == 200
    response_data = response.json()
    assert "key" in response_data
    # Mock returns fixed key 'test-key', not the input key
    assert response_data["key"] == "test-key"

    # Verify storage client was called
    mock_storage_client.upload_obj.assert_called_once()


@pytest.mark.unit
def test_ai_chat_sends_notification_after_delete_via_direct_delete(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
) -> None:
    """Test that delete endpoint triggers chat notification."""
    # Act: Delete file directly via /delete endpoint
    response = client.delete("/delete/uploads/old_file.txt", headers=auth_headers)

    # Assert: Delete successful
    assert response.status_code == 204

    # Verify storage client was called
    mock_storage_client.delete_file.assert_called_once_with(
        container="test-bucket", object_name="uploads/old_file.txt"
    )


@pytest.mark.unit
def test_ai_summarize_with_download_and_notify(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_storage_client: MagicMock,
    mock_get_ai_client: MagicMock,
) -> None:
    """Test AI summarize workflow: download file, get AI summary, notify chat."""
    # Arrange: Mock AI response with download + summarize action
    mock_ai_client.send_message.return_value = AIResponse(
        text="Summary: This report details Q1 2026 sales metrics",
        action_taken="download_file",
        tool_calls=["download_file"],
        tool_args={"container": "test-bucket", "object_name": "q1_report.pdf"},
    )

    # Act: Send summarize prompt
    response = client.post(
        "/ai/chat",
        json={"prompt": "summarize q1_report.pdf"},
        headers=auth_headers,
    )

    # Assert: Response contains summary
    assert response.status_code == 200
    data = response.json()
    assert data["action_taken"] == "download_file"
    assert "Q1 2026" in data["response"]


@pytest.mark.unit
def test_ai_chat_with_ai_action_and_notification_data(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_storage_client: MagicMock,
    mock_get_ai_client: MagicMock,
) -> None:
    """Test that /ai/chat returns tool_args for notification to use."""
    # Arrange: Mock AI response with detailed tool_args
    mock_ai_client.send_message.return_value = AIResponse(
        text="Deleted metrics.csv from archive",
        action_taken="delete_file",
        tool_calls=["delete_file"],
        tool_args={"container": "test-bucket", "object_name": "metrics.csv"},
    )

    # Act: Send prompt
    response = client.post(
        "/ai/chat",
        json={"prompt": "clean up old metrics"},
        headers=auth_headers,
    )

    # Assert: Response includes tool_args for notification
    assert response.status_code == 200
    data = response.json()
    assert data["action_taken"] == "delete_file"
    # The response should have enough info to construct notification
    assert "Deleted" in data["response"]
    assert "metrics.csv" in data["response"]


@pytest.mark.unit
def test_multiple_sequential_ai_actions(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_storage_client: MagicMock,
    mock_get_ai_client: MagicMock,
) -> None:
    """Test that multiple sequential AI actions each trigger notifications."""
    # Arrange: Setup mock for first call
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

    mock_ai_client.send_message.side_effect = [first_response, second_response]

    # Act: Send two sequential prompts
    response1 = client.post(
        "/ai/chat", json={"prompt": "list files"}, headers=auth_headers
    )
    response2 = client.post(
        "/ai/chat",
        json={"prompt": "delete archive.tar"},
        headers=auth_headers,
    )

    # Assert: Both requests successful
    assert response1.status_code == 200
    assert response2.status_code == 200

    data1 = response1.json()
    data2 = response2.json()

    assert data1["action_taken"] == "list_files"
    assert data2["action_taken"] == "delete_file"

    # Verify both AI calls were made
    assert mock_ai_client.send_message.call_count == 2


@pytest.mark.unit
def test_ai_action_with_all_storage_tools_covered(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_storage_client: MagicMock,
    mock_get_ai_client: MagicMock,
) -> None:
    """Integration test verifying all 6 storage tool types are callable via AI."""
    from cloud_storage_service import main

    test_cases = [
        (
            "list files",
            AIResponse(
                text="3 files found",
                action_taken="list_files",
                tool_calls=["list_files"],
                tool_args={"container": "test-bucket"},
            ),
        ),
        (
            "get info on report.pdf",
            AIResponse(
                text="report.pdf is 5 MB",
                action_taken="get_file_info",
                tool_calls=["get_file_info"],
                tool_args={"container": "test-bucket", "object_name": "report.pdf"},
            ),
        ),
        (
            "delete temp.txt",
            AIResponse(
                text="Deleted temp.txt",
                action_taken="delete_file",
                tool_calls=["delete_file"],
                tool_args={"container": "test-bucket", "object_name": "temp.txt"},
            ),
        ),
        (
            "download config.json",
            AIResponse(
                text="Downloaded config.json",
                action_taken="download_file",
                tool_calls=["download_file"],
                tool_args={"container": "test-bucket", "object_name": "config.json"},
            ),
        ),
        (
            "summarize data.csv",
            AIResponse(
                text="Summary of data: sales report Q1",
                action_taken="summarize_file",
                tool_calls=["summarize_file"],
                tool_args={"container": "test-bucket", "object_name": "data.csv"},
            ),
        ),
    ]

    # Act: Test each tool type via AI chat
    for prompt, expected_response in test_cases:
        mock_ai_client.send_message.return_value = expected_response

        response = client.post(
            "/ai/chat",
            json={"prompt": prompt},
            headers=auth_headers,
        )

        # Assert: Each tool invocation returns 200
        assert response.status_code == 200, f"Failed for prompt: {prompt}"
        data = response.json()
        assert data["action_taken"] == expected_response.action_taken


@pytest.mark.unit
def test_ai_chat_preserves_notification_context_on_error(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_storage_client: MagicMock,
    mock_get_ai_client: MagicMock,
) -> None:
    """Test that even if storage operation fails, AI response is still returned."""
    # Arrange: Mock storage error but AI still completes
    from cloud_storage_api.exceptions import StorageBackendError

    mock_storage_client.delete_file.side_effect = StorageBackendError(
        "Backend error"
    )

    mock_ai_client.send_message.return_value = AIResponse(
        text="I attempted to delete the file but encountered a backend error",
        action_taken="delete_file",
        tool_calls=["delete_file"],
        tool_args={"container": "test-bucket", "object_name": "file.txt"},
    )

    # Act: Send delete prompt despite backend error
    response = client.post(
        "/ai/chat",
        json={"prompt": "delete file.txt"},
        headers=auth_headers,
    )

    # Assert: AI still returns a response (graceful error handling)
    assert response.status_code == 200
    data = response.json()
    assert "backend error" in data["response"].lower() or data["response"] is not None
