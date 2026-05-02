"""Integration tests for AI + Storage interactions."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

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
    """/ai/chat with 'list files' prompt routes through the AI client and returns list_files action."""
    mock_ai_client.send_message_with_metadata.return_value = AIResponse(
        text="You have 3 files in your bucket",
        action_taken="list_files",
        tool_calls=["list_files"],
        tool_args={"container": "test-bucket"},
    )

    response = client.post(
        "/ai/chat",
        json={"prompt": "list my files"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["action_taken"] == "list_files"
    assert data["response"] == "You have 3 files in your bucket"
    mock_ai_client.send_message_with_metadata.assert_called_once()
    kwargs = mock_ai_client.send_message_with_metadata.call_args.kwargs
    assert kwargs["prompt"] == "list my files"


@pytest.mark.unit
def test_ai_chat_delete_file_tool_invocation(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_storage_client: MagicMock,
    mock_get_ai_client: MagicMock,
) -> None:
    """/ai/chat with delete prompt routes through the AI client and returns delete_file action."""
    mock_ai_client.send_message_with_metadata.return_value = AIResponse(
        text="Deleted old_report.pdf",
        action_taken="delete_file",
        tool_calls=["delete_file"],
        tool_args={"container": "test-bucket", "object_name": "old_report.pdf"},
    )

    response = client.post(
        "/ai/chat",
        json={"prompt": "delete old_report.pdf"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["action_taken"] == "delete_file"
    assert "Deleted" in data["response"]
    mock_ai_client.send_message_with_metadata.assert_called_once()


@pytest.mark.unit
def test_ai_chat_get_file_info_tool_invocation(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_storage_client: MagicMock,
    mock_get_ai_client: MagicMock,
) -> None:
    """/ai/chat invokes get_file_info via AI client and returns metadata in the response."""
    mock_ai_client.send_message_with_metadata.return_value = AIResponse(
        text="The file report.pdf is 5.2 MB",
        action_taken="get_file_info",
        tool_calls=["get_file_info"],
        tool_args={"container": "test-bucket", "object_name": "report.pdf"},
    )

    response = client.post(
        "/ai/chat",
        json={"prompt": "what's the size of report.pdf"},
        headers=auth_headers,
    )

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
    """/ai/chat invokes upload_file via AI client and returns upload confirmation."""
    mock_ai_client.send_message_with_metadata.return_value = AIResponse(
        text="Uploaded new_file.txt successfully",
        action_taken="upload_file",
        tool_calls=["upload_file"],
        tool_args={
            "container": "test-bucket",
            "object_name": "new_file.txt",
            "content_type": "text/plain",
        },
    )

    response = client.post(
        "/ai/chat",
        json={"prompt": "upload new_file.txt"},
        headers=auth_headers,
    )

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
    """/ai/chat invokes download_file via AI client and returns download confirmation."""
    mock_ai_client.send_message_with_metadata.return_value = AIResponse(
        text="Downloaded report.pdf: content preview",
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
    assert "Downloaded" in data["response"]


@pytest.mark.unit
def test_ai_chat_multiple_tool_calls_in_sequence(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_storage_client: MagicMock,
    mock_get_ai_client: MagicMock,
) -> None:
    """/ai/chat handles AI responses that report multiple tool calls in sequence."""
    mock_ai_client.send_message_with_metadata.return_value = AIResponse(
        text="Listed files and got details on report.pdf",
        action_taken="get_file_info",
        tool_calls=["list_files", "get_file_info"],
        tool_args={"container": "test-bucket", "object_name": "report.pdf"},
    )

    response = client.post(
        "/ai/chat",
        json={"prompt": "list files and get details on the largest one"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["action_taken"] == "get_file_info"
    assert len(data["response"]) > 0
    mock_ai_client.send_message_with_metadata.assert_called_once()


@pytest.mark.unit
def test_ai_chat_with_no_tool_invocation(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_storage_client: MagicMock,
    mock_get_ai_client: MagicMock,
) -> None:
    """/ai/chat returns a plain text response when no storage tools are invoked."""
    mock_ai_client.send_message_with_metadata.return_value = AIResponse(
        text="I can help you manage your cloud storage. What would you like to do?",
        action_taken=None,
        tool_calls=[],
    )

    response = client.post(
        "/ai/chat",
        json={"prompt": "what can you do?"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["response"] == "I can help you manage your cloud storage. What would you like to do?"
    assert data["action_taken"] is None
