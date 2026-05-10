"""Integration tests for AI + Storage flows.

These tests exercise the /ai/chat endpoint with the AI client mocked at the
dependency boundary (via mock_get_ai_client autoused by conftest). They verify
that the endpoint correctly:
- surfaces the AI's response and action_taken fields
- forwards prompts to send_message_with_metadata
- preserves response content across sequential calls
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from ai_client_api import AIResponse

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Individual tool invocations
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_ai_chat_list_files_tool_invocation_mock(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_storage_client: MagicMock,
) -> None:
    """/ai/chat with a list-files prompt returns list_files action_taken."""
    mock_ai_client.send_message_with_metadata.return_value = AIResponse(
        text="You have 3 files.",
        action_taken="list_files",
        tool_calls=["list_files"],
        tool_args={"container": "test-bucket"},
    )

    response = client.post(
        "/ai/chat",
        json={"prompt": "list all files in the bucket"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["response"] == "You have 3 files."
    assert data["action_taken"] == "list_files"
    mock_ai_client.send_message_with_metadata.assert_called_once()


@pytest.mark.integration
def test_ai_chat_delete_file_tool_invocation_mock(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_storage_client: MagicMock,
) -> None:
    """/ai/chat with a delete prompt returns delete_file action_taken."""
    mock_ai_client.send_message_with_metadata.return_value = AIResponse(
        text="Deleted temp.txt",
        action_taken="delete_file",
        tool_calls=["delete_file"],
        tool_args={"container": "test-bucket", "object_name": "temp.txt"},
    )

    response = client.post(
        "/ai/chat",
        json={"prompt": "delete the file named temp.txt"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["action_taken"] == "delete_file"
    assert "Deleted" in data["response"]


@pytest.mark.integration
def test_ai_chat_get_file_info_tool_invocation_mock(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_storage_client: MagicMock,
) -> None:
    """/ai/chat with a metadata prompt returns get_file_info action_taken."""
    mock_ai_client.send_message_with_metadata.return_value = AIResponse(
        text="report.pdf is 5.2 MB, application/pdf.",
        action_taken="get_file_info",
        tool_calls=["get_file_info"],
        tool_args={"container": "test-bucket", "object_name": "report.pdf"},
    )

    response = client.post(
        "/ai/chat",
        json={"prompt": "what is the size and type of report.pdf"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["action_taken"] == "get_file_info"
    assert "5.2 MB" in data["response"]


@pytest.mark.integration
def test_ai_chat_download_file_tool_invocation_mock(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_storage_client: MagicMock,
) -> None:
    """/ai/chat with a download prompt returns download_file action_taken."""
    mock_ai_client.send_message_with_metadata.return_value = AIResponse(
        text="Downloaded data.json",
        action_taken="download_file",
        tool_calls=["download_file"],
        tool_args={"container": "test-bucket", "object_name": "data.json"},
    )

    response = client.post(
        "/ai/chat",
        json={"prompt": "download and read data.json"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["action_taken"] == "download_file"
    assert "Downloaded" in data["response"]


@pytest.mark.integration
def test_ai_chat_upload_file_tool_invocation_mock(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_storage_client: MagicMock,
) -> None:
    """/ai/chat with an upload prompt returns upload_file action_taken."""
    mock_ai_client.send_message_with_metadata.return_value = AIResponse(
        text="Uploaded config.yaml",
        action_taken="upload_file",
        tool_calls=["upload_file"],
        tool_args={
            "container": "test-bucket",
            "remote_path": "config.yaml",
        },
    )

    response = client.post(
        "/ai/chat",
        json={"prompt": "upload the new configuration file"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["action_taken"] == "upload_file"
    assert "Uploaded" in data["response"]


# ---------------------------------------------------------------------------
# Prompt forwarding and sequential operations
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_ai_chat_forwards_prompt_to_ai_client_mock(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_storage_client: MagicMock,
) -> None:
    """/ai/chat forwards the user's prompt verbatim to send_message_with_metadata."""
    mock_ai_client.send_message_with_metadata.return_value = AIResponse(
        text="ok",
        action_taken="list_files",
        tool_calls=["list_files"],
    )

    response = client.post(
        "/ai/chat",
        json={"prompt": "list files"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    mock_ai_client.send_message_with_metadata.assert_called_once()
    kwargs = mock_ai_client.send_message_with_metadata.call_args.kwargs
    assert kwargs["prompt"] == "list files"


@pytest.mark.integration
def test_multiple_sequential_ai_operations_mock(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_storage_client: MagicMock,
) -> None:
    """Sequential /ai/chat calls each invoke the AI client and return distinct responses."""
    mock_ai_client.send_message_with_metadata.side_effect = [
        AIResponse(
            text="Listed 5 files",
            action_taken="list_files",
            tool_calls=["list_files"],
            tool_args={"container": "test-bucket"},
        ),
        AIResponse(
            text="report.pdf info",
            action_taken="get_file_info",
            tool_calls=["get_file_info"],
            tool_args={"container": "test-bucket", "object_name": "report.pdf"},
        ),
    ]

    response1 = client.post(
        "/ai/chat",
        json={"prompt": "list files"},
        headers=auth_headers,
    )
    response2 = client.post(
        "/ai/chat",
        json={"prompt": "get file info on report.pdf"},
        headers=auth_headers,
    )

    assert response1.status_code == 200
    assert response2.status_code == 200
    assert response1.json()["action_taken"] == "list_files"
    assert response2.json()["action_taken"] == "get_file_info"
    assert mock_ai_client.send_message_with_metadata.call_count == 2
