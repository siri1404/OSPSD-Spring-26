"""Integration tests for AI tool calling with chat notifications.

Tests that AI endpoints properly respond with actions and handle errors.
Also includes real GeminiAiClient integration tests that exercise the tool loop.
"""

from __future__ import annotations

from datetime import UTC, datetime, timezone
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from ai_client_api import AIResponse
from cloud_storage_api.exceptions import StorageBackendError
from gemini_ai_client_impl.client import GeminiAiClient

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


@pytest.mark.unit
@pytest.mark.integration
def test_ai_chat_endpoint_returns_ai_response(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_storage_client: MagicMock,
    mock_chat_client: MagicMock,
    mock_get_ai_client: MagicMock,
    mock_get_chat_notification: MagicMock,
) -> None:
    """/ai/chat returns an AI response with action_taken and response text."""
    mock_ai_client.send_message_with_metadata.return_value = AIResponse(
        text="Found 3 files in bucket",
        action_taken="list_files",
        tool_calls=["list_files"],
        tool_args={"container": "test-bucket"},
    )

    response = client.post(
        "/ai/chat",
        json={"prompt": "list all files in the bucket"},
        headers={**auth_headers, "X-Container": "test-bucket"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["response"] == "Found 3 files in bucket"
    assert data["action_taken"] == "list_files"
    mock_ai_client.send_message_with_metadata.assert_called_once()


@pytest.mark.unit
@pytest.mark.integration
def test_ai_delete_file_response_includes_action(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_storage_client: MagicMock,
    mock_get_ai_client: MagicMock,
) -> None:
    """/ai/chat surfaces delete_file action and the deleted filename in the response."""
    deleted_file = "archive_2024.tar.gz"
    mock_ai_client.send_message_with_metadata.return_value = AIResponse(
        text=f"Successfully deleted {deleted_file}",
        action_taken="delete_file",
        tool_calls=["delete_file"],
        tool_args={"object_name": deleted_file, "container": "test-bucket"},
    )

    response = client.post(
        "/ai/chat",
        json={"prompt": f"delete {deleted_file}"},
        headers={**auth_headers, "X-Container": "test-bucket"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["action_taken"] == "delete_file"
    assert deleted_file in data["response"]


@pytest.mark.unit
@pytest.mark.integration
def test_ai_chat_endpoint_response_structure(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_chat_client: MagicMock,
    mock_get_ai_client: MagicMock,
    mock_get_chat_notification: MagicMock,
) -> None:
    """/ai/chat response always exposes 'response' and 'action_taken' fields."""
    mock_ai_client.send_message_with_metadata.return_value = AIResponse(
        text="Operation complete",
        action_taken="list_files",
        tool_calls=["list_files"],
        tool_args={"container": "test-bucket"},
    )

    response = client.post(
        "/ai/chat",
        json={"prompt": "list files"},
        headers={**auth_headers, "X-Container": "test-bucket"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "action_taken" in data
    assert data["response"] == "Operation complete"
    assert data["action_taken"] == "list_files"


@pytest.mark.unit
@pytest.mark.integration
@pytest.mark.parametrize(
    ("action", "response_text"),
    [
        ("list_files", "Files listed successfully"),
        ("delete_file", "File deleted successfully"),
        ("upload_file", "File uploaded successfully"),
    ],
)
def test_ai_chat_with_various_actions(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_get_ai_client: MagicMock,
    action: str,
    response_text: str,
) -> None:
    """/ai/chat returns the AI's action_taken and response text for each tool type."""
    mock_ai_client.send_message_with_metadata.return_value = AIResponse(
        text=response_text,
        action_taken=action,
        tool_calls=[action],
        tool_args={"container": "test-bucket"},
    )

    response = client.post(
        "/ai/chat",
        json={"prompt": f"perform {action}"},
        headers={**auth_headers, "X-Container": "test-bucket"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["action_taken"] == action
    assert data["response"] == response_text


@pytest.mark.unit
@pytest.mark.integration
def test_ai_chat_requires_auth_token(client: TestClient) -> None:
    """/ai/chat rejects requests without an authorization header or with an invalid token."""
    no_auth = client.post(
        "/ai/chat",
        json={"prompt": "list files"},
        headers={"X-Container": "test-bucket"},
    )
    assert no_auth.status_code in (401, 403)

    invalid_auth = client.post(
        "/ai/chat",
        json={"prompt": "list files"},
        headers={
            "Authorization": "Bearer invalid-token",
            "X-Container": "test-bucket",
        },
    )
    assert invalid_auth.status_code in (401, 403)


@pytest.mark.unit
@pytest.mark.integration
def test_ai_chat_accepts_container_header(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_get_ai_client: MagicMock,
) -> None:
    """/ai/chat processes requests that supply the X-Container header."""
    mock_ai_client.send_message_with_metadata.return_value = AIResponse(
        text="Success",
        action_taken="list_files",
        tool_calls=[],
    )

    response = client.post(
        "/ai/chat",
        json={"prompt": "list files"},
        headers={**auth_headers, "X-Container": "test-bucket"},
    )

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Real-tool-loop integration (mocked genai.Client + storage client)
# ---------------------------------------------------------------------------


def _make_function_call_part(name: str, args: dict[str, object]) -> MagicMock:
    """Build a mock Gemini Part containing a single function_call."""
    function_call = MagicMock()
    function_call.name = name
    function_call.args = args

    part = MagicMock()
    part.function_call = function_call
    return part


def _make_response_with_parts(parts: list[MagicMock]) -> MagicMock:
    """Build a mock GenerateContentResponse with the given parts."""
    response = MagicMock()
    response.text = None
    candidate = MagicMock()
    candidate.content.parts = parts
    response.candidates = [candidate]
    return response


def _make_final_response(text: str) -> MagicMock:
    """Build a mock terminal GenerateContentResponse carrying only text."""
    final_part = MagicMock()
    final_part.function_call = None
    final_part.text = text

    response = MagicMock()
    candidate = MagicMock()
    candidate.content.parts = [final_part]
    response.candidates = [candidate]
    response.text = text
    return response


@pytest.mark.integration
def test_gemini_tool_loop_list_files_dispatches_storage_client() -> None:
    """Real GeminiAiClient list_files tool loop dispatches to the storage client."""
    mock_storage = MagicMock()
    mock_info = MagicMock()
    mock_info.object_name = "test-file.txt"
    mock_info.size_bytes = 100
    mock_info.data_type = "text/plain"
    mock_info.updated_at = datetime.now(tz=UTC)
    mock_storage.list_files.return_value = [mock_info]

    with patch("gemini_ai_client_impl.client.genai.Client") as mock_genai_cls:
        mock_chat = MagicMock()
        mock_genai_cls.return_value.chats.create.return_value = mock_chat
        mock_chat.send_message.side_effect = [
            _make_response_with_parts([_make_function_call_part("list_files", {"container": "test-bucket"})]),
            _make_final_response("Found 1 file in the bucket."),
        ]

        client = GeminiAiClient(
            storage_client=mock_storage,
            api_key="fake-key-test",
        )
        result = client.send_message_with_metadata(
            "list files",
            context={"container": "test-bucket"},
        )

        assert isinstance(result, AIResponse)
        assert result.action_taken == "list_files"
        assert "list_files" in result.tool_calls
        assert result.text == "Found 1 file in the bucket."
        mock_storage.list_files.assert_called_once()


@pytest.mark.integration
def test_gemini_tool_loop_delete_file_with_object_name() -> None:
    """Real GeminiAiClient delete_file tool loop dispatches with the right object name."""
    mock_storage = MagicMock()
    mock_storage.delete_file.return_value = {
        "deleted": True,
        "version_id": None,
        "request_charged": False,
    }
    deleted_file = "archive_2024.tar.gz"

    with patch("gemini_ai_client_impl.client.genai.Client") as mock_genai_cls:
        mock_chat = MagicMock()
        mock_genai_cls.return_value.chats.create.return_value = mock_chat
        mock_chat.send_message.side_effect = [
            _make_response_with_parts(
                [
                    _make_function_call_part(
                        "delete_file",
                        {
                            "container": "test-bucket",
                            "object_name": deleted_file,
                        },
                    )
                ]
            ),
            _make_final_response(f"Successfully deleted {deleted_file}"),
        ]

        client = GeminiAiClient(
            storage_client=mock_storage,
            api_key="fake-key-test",
        )
        result = client.send_message_with_metadata(
            f"delete {deleted_file}",
            context={"container": "test-bucket"},
        )

        assert isinstance(result, AIResponse)
        assert result.action_taken == "delete_file"
        assert deleted_file in result.text
        mock_storage.delete_file.assert_called_once()
        assert deleted_file in str(mock_storage.delete_file.call_args)


@pytest.mark.integration
def test_gemini_tool_loop_get_file_info() -> None:
    """Real GeminiAiClient get_file_info tool loop dispatches to the storage client."""
    mock_storage = MagicMock()
    mock_file_info = MagicMock()
    mock_file_info.object_name = "document.pdf"
    mock_file_info.size_bytes = 2048
    mock_file_info.data_type = "application/pdf"
    mock_file_info.updated_at = datetime.now(tz=UTC)
    mock_storage.get_file_info.return_value = mock_file_info

    with patch("gemini_ai_client_impl.client.genai.Client") as mock_genai_cls:
        mock_chat = MagicMock()
        mock_genai_cls.return_value.chats.create.return_value = mock_chat
        mock_chat.send_message.side_effect = [
            _make_response_with_parts(
                [
                    _make_function_call_part(
                        "get_file_info",
                        {
                            "container": "test-bucket",
                            "object_name": "document.pdf",
                        },
                    )
                ]
            ),
            _make_final_response("Document size: 2048 bytes, type: application/pdf"),
        ]

        client = GeminiAiClient(
            storage_client=mock_storage,
            api_key="fake-key-test",
        )
        result = client.send_message_with_metadata(
            "get info on document.pdf",
            context={"container": "test-bucket"},
        )

        assert isinstance(result, AIResponse)
        assert result.action_taken == "get_file_info"
        assert "2048" in result.text
        mock_storage.get_file_info.assert_called_once()


@pytest.mark.integration
def test_gemini_tool_loop_upload_file_triggers_dispatch() -> None:
    """Real GeminiAiClient upload_file tool loop dispatches to the storage client."""
    mock_storage = MagicMock()
    mock_file_info = MagicMock()
    mock_file_info.object_name = "new-file.txt"
    mock_file_info.size_bytes = 50
    mock_file_info.data_type = "text/plain"
    mock_file_info.updated_at = datetime.now(tz=UTC)
    mock_storage.upload_file.return_value = mock_file_info

    with patch("gemini_ai_client_impl.client.genai.Client") as mock_genai_cls:
        mock_chat = MagicMock()
        mock_genai_cls.return_value.chats.create.return_value = mock_chat
        mock_chat.send_message.side_effect = [
            _make_response_with_parts(
                [
                    _make_function_call_part(
                        "upload_file",
                        {
                            "container": "test-bucket",
                            "remote_path": "uploads/new-file.txt",
                            "local_path": "/tmp/test.txt",
                        },
                    )
                ]
            ),
            _make_final_response("File uploaded successfully"),
        ]

        client = GeminiAiClient(
            storage_client=mock_storage,
            api_key="fake-key-test",
        )
        result = client.send_message_with_metadata(
            "upload new-file.txt",
            context={"container": "test-bucket"},
        )

        assert isinstance(result, AIResponse)
        assert result.action_taken == "upload_file"
        assert "upload_file" in result.tool_calls
        mock_storage.upload_file.assert_called_once()


@pytest.mark.integration
def test_gemini_tool_loop_with_error_handling() -> None:
    """Real GeminiAiClient re-raises fatal storage errors as RuntimeError."""
    mock_storage = MagicMock()
    mock_storage.delete_file.side_effect = StorageBackendError(
        "Backend connection failed",
    )

    with patch("gemini_ai_client_impl.client.genai.Client") as mock_genai_cls:
        mock_chat = MagicMock()
        mock_genai_cls.return_value.chats.create.return_value = mock_chat
        mock_chat.send_message.return_value = _make_response_with_parts(
            [
                _make_function_call_part(
                    "delete_file",
                    {
                        "container": "test-bucket",
                        "object_name": "missing-file.txt",
                    },
                )
            ]
        )

        client = GeminiAiClient(
            storage_client=mock_storage,
            api_key="fake-key-test",
        )
        with pytest.raises(RuntimeError, match="Storage operation failed"):
            client.send_message_with_metadata(
                "delete missing-file.txt",
                context={"container": "test-bucket"},
            )

        mock_storage.delete_file.assert_called_once()


@pytest.mark.integration
def test_gemini_tool_loop_multiple_turns_with_context_injection() -> None:
    """Real GeminiAiClient injects the context container into tool args when missing."""
    mock_storage = MagicMock()
    mock_info = MagicMock()
    mock_info.object_name = "test.txt"
    mock_info.size_bytes = 100
    mock_info.data_type = "text/plain"
    mock_info.updated_at = datetime.now(tz=UTC)
    mock_storage.list_files.return_value = [mock_info]

    with patch("gemini_ai_client_impl.client.genai.Client") as mock_genai_cls:
        mock_chat = MagicMock()
        mock_genai_cls.return_value.chats.create.return_value = mock_chat
        mock_chat.send_message.side_effect = [
            # Tool call without container — client must inject from context.
            _make_response_with_parts([_make_function_call_part("list_files", {"prefix": ""})]),
            _make_final_response("Listed files successfully"),
        ]

        client = GeminiAiClient(
            storage_client=mock_storage,
            api_key="fake-key-test",
        )
        result = client.send_message_with_metadata(
            "list files",
            context={"container": "injected-bucket"},
        )

        assert isinstance(result, AIResponse)
        assert result.action_taken == "list_files"
        mock_storage.list_files.assert_called_once()
        assert "injected-bucket" in str(mock_storage.list_files.call_args)
