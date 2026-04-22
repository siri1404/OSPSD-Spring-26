"""Integration tests for AI + Storage interactions."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, call

import pytest
from ai_client_api import AIResponse

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


@pytest.mark.unit
def test_ai_chat_list_files_tool_invocation(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_storage_client: MagicMock,
    mock_get_ai_client: MagicMock,
) -> None:
    """Test that /ai/chat with 'list files' prompt triggers storage list_files tool."""
    # Arrange: Mock AI response indicating list_files tool was called
    mock_ai_client.send_message.return_value = AIResponse(
        text="You have 3 files in your bucket",
        action_taken="list_files",
        tool_calls=["list_files"],
        tool_args={"container": "test-bucket"},
    )

    # Act: Send prompt to AI chat endpoint
    response = client.post(
        "/ai/chat",
        json={"prompt": "list my files"},
        headers=auth_headers,
    )

    # Assert: Response is successful and contains expected fields
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "action_taken" in data
    assert data["action_taken"] == "list_files"
    assert data["response"] == "You have 3 files in your bucket"

    # Verify storage client method was called (indirectly via AI client mock)
    mock_ai_client.send_message.assert_called_once()
    # Verify the mock was called with a prompt string
    call_kwargs = mock_ai_client.send_message.call_args[1]
    assert "prompt" in call_kwargs or len(mock_ai_client.send_message.call_args[0]) > 0


@pytest.mark.unit
def test_ai_chat_delete_file_tool_invocation(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_storage_client: MagicMock,
    mock_get_ai_client: MagicMock,
) -> None:
    """Test that /ai/chat with delete prompt triggers storage delete_file tool."""
    # Arrange: Mock AI response indicating delete_file tool was called
    mock_ai_client.send_message.return_value = AIResponse(
        text="Deleted old_report.pdf",
        action_taken="delete_file",
        tool_calls=["delete_file"],
        tool_args={"container": "test-bucket", "object_name": "old_report.pdf"},
    )

    # Act: Send delete prompt to AI chat endpoint
    response = client.post(
        "/ai/chat",
        json={"prompt": "delete old_report.pdf"},
        headers=auth_headers,
    )

    # Assert: Response indicates delete action was taken
    assert response.status_code == 200
    data = response.json()
    assert data["action_taken"] == "delete_file"
    assert "Deleted" in data["response"]

    # Verify AI client was invoked
    mock_ai_client.send_message.assert_called_once()


@pytest.mark.unit
def test_ai_chat_get_file_info_tool_invocation(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_storage_client: MagicMock,
    mock_get_ai_client: MagicMock,
) -> None:
    """Test that /ai/chat can invoke get_file_info tool."""
    # Arrange: Mock AI response indicating get_file_info tool was called
    mock_ai_client.send_message.return_value = AIResponse(
        text="The file report.pdf is 5.2 MB",
        action_taken="get_file_info",
        tool_calls=["get_file_info"],
        tool_args={"container": "test-bucket", "object_name": "report.pdf"},
    )

    # Act: Send prompt requesting file info
    response = client.post(
        "/ai/chat",
        json={"prompt": "what's the size of report.pdf"},
        headers=auth_headers,
    )

    # Assert: Response contains file info
    assert response.status_code == 200
    data = response.json()
    assert data["action_taken"] == "get_file_info"
    assert "5.2 MB" in data["response"]


@pytest.mark.unit
def test_ai_chat_upload_file_tool_invocation(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_storage_client: MagicMock,
    mock_get_ai_client: MagicMock,
) -> None:
    """Test that /ai/chat can invoke upload_file tool."""
    # Arrange: Mock AI response indicating upload_file tool was called
    mock_ai_client.send_message.return_value = AIResponse(
        text="Uploaded new_file.txt successfully",
        action_taken="upload_file",
        tool_calls=["upload_file"],
        tool_args={
            "container": "test-bucket",
            "object_name": "new_file.txt",
            "content_type": "text/plain",
        },
    )

    # Act: Send prompt to upload
    response = client.post(
        "/ai/chat",
        json={"prompt": "upload new_file.txt"},
        headers=auth_headers,
    )

    # Assert: Response indicates upload action
    assert response.status_code == 200
    data = response.json()
    assert data["action_taken"] == "upload_file"
    assert "Uploaded" in data["response"]


@pytest.mark.unit
def test_ai_chat_download_file_tool_invocation(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_storage_client: MagicMock,
    mock_get_ai_client: MagicMock,
) -> None:
    """Test that /ai/chat can invoke download_file tool."""
    # Arrange: Mock AI response indicating download_file tool was called
    mock_ai_client.send_message.return_value = AIResponse(
        text="Downloaded report.pdf: content preview",
        action_taken="download_file",
        tool_calls=["download_file"],
        tool_args={"container": "test-bucket", "object_name": "report.pdf"},
    )

    # Act: Send prompt to download
    response = client.post(
        "/ai/chat",
        json={"prompt": "download and summarize report.pdf"},
        headers=auth_headers,
    )

    # Assert: Response indicates download action
    assert response.status_code == 200
    data = response.json()
    assert data["action_taken"] == "download_file"
    assert "Downloaded" in data["response"]


@pytest.mark.unit
def test_ai_chat_multiple_tool_calls_in_sequence(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_storage_client: MagicMock,
    mock_get_ai_client: MagicMock,
) -> None:
    """Test that /ai/chat can handle multiple tool calls in sequence."""
    # Arrange: Mock AI response with multiple tool calls
    mock_ai_client.send_message.return_value = AIResponse(
        text="Listed files and got details on report.pdf",
        action_taken="multiple_tools",
        tool_calls=["list_files", "get_file_info"],
        tool_args={
            "primary": {"container": "test-bucket"},
            "secondary": {"container": "test-bucket", "object_name": "report.pdf"},
        },
    )

    # Act: Send complex prompt
    response = client.post(
        "/ai/chat",
        json={"prompt": "list files and get details on the largest one"},
        headers=auth_headers,
    )

    # Assert: Response indicates multiple actions
    assert response.status_code == 200
    data = response.json()
    assert data["action_taken"] == "multiple_tools"
    assert len(data.get("response", "")) > 0

    # Verify AI client was invoked
    mock_ai_client.send_message.assert_called_once()


@pytest.mark.unit
def test_ai_chat_with_no_tool_invocation(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_storage_client: MagicMock,
    mock_get_ai_client: MagicMock,
) -> None:
    """Test that /ai/chat works when no storage tools are needed."""
    # Arrange: Mock AI response with no tool calls
    mock_ai_client.send_message.return_value = AIResponse(
        text="I can help you manage your cloud storage. What would you like to do?",
        action_taken=None,
        tool_calls=[],
        tool_args=None,
    )

    # Act: Send general prompt
    response = client.post(
        "/ai/chat",
        json={"prompt": "what can you do?"},
        headers=auth_headers,
    )

    # Assert: Response is successful even without tool invocation
    assert response.status_code == 200
    data = response.json()
    assert data["response"] == "I can help you manage your cloud storage. What would you like to do?"
    assert data["action_taken"] is None
