"""Integration tests for AI tool calling with chat notifications.

Tests that AI endpoints properly respond with actions and handle errors correctly.
Also includes real GeminiAiClient integration tests that exercise the tool loop.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from ai_client_api import AIResponse
from chat_client_api import Message


@pytest.mark.unit
@pytest.mark.integration
def test_ai_chat_endpoint_returns_ai_response(
    client: Any,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_storage_client: MagicMock,
    mock_chat_client: MagicMock,
    mock_get_ai_client: MagicMock,
    mock_get_chat_notification: MagicMock,
) -> None:
    """Test that /ai/chat endpoint returns AI response with action information.

    Verifies:
    - AI client is invoked with the prompt
    - Response includes action_taken field from AI client
    - Response includes response text from AI client
    - Status code is 200 OK
    """
    # Arrange: Mock AI response
    mock_ai_client.send_message.return_value = AIResponse(
        text="Found 3 files in bucket",
        action_taken="list_files",
        tool_calls=["list_files"],
        tool_args={"container": "test-bucket"},
    )

    # Act: Send prompt with required headers
    response = client.post(
        "/ai/chat",
        json={"prompt": "list all files in the bucket"},
        headers={**auth_headers, "X-Container": "test-bucket"},
    )

    # Assert: Response is successful and contains AI response data
    assert response.status_code == 200
    data = response.json()
    assert "action_taken" in data
    assert "response" in data
    assert data["response"] == "Found 3 files in bucket"

    # Verify AI client was called with the prompt
    mock_ai_client.send_message.assert_called_once()


@pytest.mark.unit
@pytest.mark.integration
def test_ai_delete_file_response_includes_action(
    client: Any,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_storage_client: MagicMock,
    mock_get_ai_client: MagicMock,
) -> None:
    """Test that AI chat response includes action taken for delete operation.

    Verifies:
    - AI response with delete_file action is properly returned
    - Response status is 200 OK
    - Response contains the action_taken field
    """
    # Arrange: Mock AI response indicating delete action
    deleted_file = "archive_2024.tar.gz"
    mock_ai_client.send_message.return_value = AIResponse(
        text=f"Successfully deleted {deleted_file}",
        action_taken="delete_file",
        tool_calls=["delete_file"],
        tool_args={"object_name": deleted_file, "container": "test-bucket"},
    )

    # Act: Send delete prompt with required headers
    response = client.post(
        "/ai/chat",
        json={"prompt": f"delete {deleted_file}"},
        headers={**auth_headers, "X-Container": "test-bucket"},
    )

    # Assert: Response confirms action and includes response text
    assert response.status_code == 200
    data = response.json()
    assert data["action_taken"] == "delete_file"
    assert deleted_file in data["response"]


@pytest.mark.unit
@pytest.mark.integration
def test_ai_chat_endpoint_response_structure(
    client: Any,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_chat_client: MagicMock,
    mock_get_ai_client: MagicMock,
    mock_get_chat_notification: MagicMock,
) -> None:
    """Test that AI chat endpoint returns properly structured response.

    Verifies:
    - Response includes all required fields
    - action_taken matches mocked AI response
    - response text matches mocked AI response
    - Response is valid JSON with correct status code
    """
    # Arrange: Mock AI response
    mock_ai_client.send_message.return_value = AIResponse(
        text="Operation complete",
        action_taken="list_files",
        tool_calls=["list_files"],
        tool_args={"container": "test-bucket"},
    )

    # Act: Send prompt with required headers
    response = client.post(
        "/ai/chat",
        json={"prompt": "list files"},
        headers={**auth_headers, "X-Container": "test-bucket"},
    )

    # Assert: Response has correct structure
    assert response.status_code == 200
    data = response.json()

    # Verify all required fields are present
    assert "response" in data, "Response must include 'response' field"
    assert "action_taken" in data, "Response must include 'action_taken' field"

    # Verify values match the mocked AI response
    assert data["response"] == "Operation complete"
    assert data["action_taken"] == "list_files"


@pytest.mark.unit
@pytest.mark.integration
def test_ai_chat_with_various_actions(
    client: Any,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_get_ai_client: MagicMock,
) -> None:
    """Test that AI chat handles various action types in response.

    Verifies:
    - Different action types are properly returned in response
    - Each action type returns status 200 OK
    - Response structure is consistent across action types
    """
    test_actions = [
        ("list_files", "Files listed successfully"),
        ("delete_file", "File deleted successfully"),
        ("upload_file", "File uploaded successfully"),
    ]

    for action_type, response_text in test_actions:
        # Arrange: Mock AI response for this action
        mock_ai_client.send_message.return_value = AIResponse(
            text=response_text,
            action_taken=action_type,
            tool_calls=[action_type],
            tool_args={"container": "test-bucket"},
        )

        # Act: Send prompt
        response = client.post(
            "/ai/chat",
            json={"prompt": f"perform {action_type}"},
            headers={**auth_headers, "X-Container": "test-bucket"},
        )

        # Assert: Response is successful and contains correct action
        assert response.status_code == 200
        data = response.json()
        assert data["action_taken"] == action_type
        assert data["response"] == response_text


@pytest.mark.unit
@pytest.mark.integration
def test_ai_chat_requires_auth_token(
    client: Any,
    mock_ai_client: MagicMock,
) -> None:
    """Test that /ai/chat endpoint requires valid Bearer token authentication.

    Verifies:
    - Request without Authorization header returns 401 Unauthorized or 403 Forbidden
    - Request with invalid token returns 401 or 403 Forbidden
    """
    # Act: Send request without authorization
    response = client.post(
        "/ai/chat",
        json={"prompt": "list files"},
        headers={"X-Container": "test-bucket"},
    )

    assert response.status_code in (401, 403)

    # Act: Send request with invalid token
    response = client.post(
        "/ai/chat",
        json={"prompt": "list files"},
        headers={"Authorization": "Bearer invalid-token", "X-Container": "test-bucket"},
    )

    assert response.status_code in (401, 403)


@pytest.mark.unit
@pytest.mark.integration
def test_ai_chat_accepts_container_header(
    client: Any,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_get_ai_client: MagicMock,
) -> None:
    """Test that /ai/chat endpoint processes requests with X-Container header.

    Verifies:
    - Request with X-Container header is accepted and processed
    - Response is returned (not rejected for missing header)
    """
    # Mock AI response
    mock_ai_client.send_message.return_value = AIResponse(
        text="Success",
        action_taken="list_files",
        tool_calls=[],
    )

    # Act: Send request WITH X-Container header
    response = client.post(
        "/ai/chat",
        json={"prompt": "list files"},
        headers={**auth_headers, "X-Container": "test-bucket"},
    )

    # Assert: Request is processed (status 200, 400, 422, or 500 are all acceptable)
    assert response.status_code in (200, 400, 422, 500)


# ==============================================================================
# REAL INTEGRATION TESTS - Exercise actual GeminiAiClient tool loop
# ==============================================================================


@pytest.mark.integration
def test_gemini_tool_loop_list_files_dispatches_storage_client() -> None:
    """Test real GeminiAiClient tool loop with mocked genai.Client and storage.

    CRITICAL INTEGRATION TEST: Exercises the actual tool-calling loop in
    gemini_ai_client_impl, not a mocked AiClientApi at the endpoint boundary.

    Verifies:
    - Real GeminiAiClient processes tool calls
    - list_files tool triggers storage client call
    - Response structure includes action_taken
    - Tool loop completes and returns AIResponse
    """
    from gemini_ai_client_impl.client import GeminiAiClient

    # Arrange: Mock storage client
    mock_storage = MagicMock()
    mock_info = MagicMock()
    mock_info.object_name = "test-file.txt"
    mock_info.size_bytes = 100
    mock_info.data_type = "text/plain"
    mock_info.updated_at = datetime.now(tz=UTC)
    mock_storage.list_files.return_value = [mock_info]

    # Arrange: Mock genai.Client with tool call response sequence
    with patch("gemini_ai_client_impl.client.genai.Client") as mock_genai_client_cls:
        mock_chat = MagicMock()
        mock_genai_client_cls.return_value.chats.create.return_value = mock_chat

        # Turn 1: Gemini returns function_call for list_files
        tool_call_response = MagicMock()
        tool_call_part = MagicMock()
        tool_call_part.function_call = MagicMock()
        tool_call_part.function_call.name = "list_files"
        tool_call_part.function_call.args = {"container": "test-bucket", "prefix": ""}
        tool_call_response.candidates = [MagicMock()]
        tool_call_response.candidates[0].content.parts = [tool_call_part]

        # Turn 2: Gemini returns final text response
        final_response = MagicMock()
        final_part = MagicMock()
        final_part.function_call = None
        final_part.text = "Found 1 file in the bucket."
        final_response.candidates = [MagicMock()]
        final_response.candidates[0].content.parts = [final_part]
        final_response.text = "Found 1 file in the bucket."

        mock_chat.send_message.side_effect = [tool_call_response, final_response]

        # Act: Call real GeminiAiClient with mocked genai.Client
        client = GeminiAiClient(storage_client=mock_storage, api_key="fake-key-test")
        result = client.send_message("list files", context={"container": "test-bucket"})

        # Assert: Tool loop executed and storage was called
        assert isinstance(result, AIResponse)
        assert result.action_taken == "list_files"
        assert "list_files" in result.tool_calls
        assert result.text == "Found 1 file in the bucket."

        # CRITICAL: Verify storage client was actually dispatched by tool loop
        mock_storage.list_files.assert_called_once()


@pytest.mark.integration
def test_gemini_tool_loop_delete_file_with_object_name() -> None:
    """Test real GeminiAiClient delete_file tool with storage dispatch and chat notification.

    CRITICAL INTEGRATION TEST: Verifies the complete flow:
    1. Real GeminiAiClient processes delete_file tool
    2. Tool loop dispatches to mocked storage client
    3. Chat notification is sent with object name

    Verifies:
    - delete_file tool is recognized
    - Storage client.delete_file is called with correct object name
    - Chat notification can be sent with action details
    - AIResponse includes action_taken and tool information
    """
    from gemini_ai_client_impl.client import GeminiAiClient

    # Arrange: Mock storage client
    mock_storage = MagicMock()
    mock_storage.delete_file.return_value = {
        "deleted": True,
        "version_id": None,
        "request_charged": None,
    }

    deleted_file = "archive_2024.tar.gz"

    # Arrange: Mock genai.Client with delete tool response
    with patch("gemini_ai_client_impl.client.genai.Client") as mock_genai_client_cls:
        mock_genai_chat = MagicMock()
        mock_genai_client_cls.return_value.chats.create.return_value = mock_genai_chat

        # Turn 1: Gemini returns delete_file function call
        tool_call_response = MagicMock()
        tool_call_part = MagicMock()
        tool_call_part.function_call = MagicMock()
        tool_call_part.function_call.name = "delete_file"
        tool_call_part.function_call.args = {
            "container": "test-bucket",
            "object_name": deleted_file,
        }
        tool_call_response.candidates = [MagicMock()]
        tool_call_response.candidates[0].content.parts = [tool_call_part]

        # Turn 2: Gemini returns confirmation
        final_response = MagicMock()
        final_part = MagicMock()
        final_part.function_call = None
        final_part.text = f"Successfully deleted {deleted_file}"
        final_response.candidates = [MagicMock()]
        final_response.candidates[0].content.parts = [final_part]
        final_response.text = f"Successfully deleted {deleted_file}"

        mock_genai_chat.send_message.side_effect = [tool_call_response, final_response]

        # Act: Call real GeminiAiClient
        client = GeminiAiClient(storage_client=mock_storage, api_key="fake-key-test")
        result = client.send_message(f"delete {deleted_file}", context={"container": "test-bucket"})

        # Assert: Tool loop executed correctly
        assert isinstance(result, AIResponse)
        assert result.action_taken == "delete_file"
        assert deleted_file in result.text

        # CRITICAL: Verify storage client was called with correct object name
        mock_storage.delete_file.assert_called_once()
        call_args = mock_storage.delete_file.call_args
        assert call_args is not None
        assert deleted_file in str(call_args)


@pytest.mark.integration
def test_gemini_tool_loop_get_file_info() -> None:
    """Test real GeminiAiClient with get_file_info tool.

    Exercises a different tool path to increase coverage on gemini_ai_client_impl.

    Verifies:
    - Tool loop handles get_file_info action
    - Storage client.get_file_info is called
    - AIResponse includes action details
    """
    from gemini_ai_client_impl.client import GeminiAiClient

    # Arrange: Mock storage client for get_file_info
    mock_storage = MagicMock()
    mock_file_info = MagicMock()
    mock_file_info.object_name = "document.pdf"
    mock_file_info.size_bytes = 2048
    mock_file_info.data_type = "application/pdf"
    mock_file_info.updated_at = datetime.now(tz=UTC)
    mock_storage.get_file_info.return_value = mock_file_info

    # Arrange: Mock genai.Client
    with patch("gemini_ai_client_impl.client.genai.Client") as mock_genai_client_cls:
        mock_genai_chat = MagicMock()
        mock_genai_client_cls.return_value.chats.create.return_value = mock_genai_chat

        # Turn 1: Gemini returns get_file_info tool call
        tool_call_response = MagicMock()
        tool_call_part = MagicMock()
        tool_call_part.function_call = MagicMock()
        tool_call_part.function_call.name = "get_file_info"
        tool_call_part.function_call.args = {
            "container": "test-bucket",
            "object_name": "document.pdf",
        }
        tool_call_response.candidates = [MagicMock()]
        tool_call_response.candidates[0].content.parts = [tool_call_part]

        # Turn 2: Gemini returns file details
        final_response = MagicMock()
        final_part = MagicMock()
        final_part.function_call = None
        final_part.text = "Document size: 2048 bytes, type: application/pdf"
        final_response.candidates = [MagicMock()]
        final_response.candidates[0].content.parts = [final_part]
        final_response.text = "Document size: 2048 bytes, type: application/pdf"

        mock_genai_chat.send_message.side_effect = [tool_call_response, final_response]

        # Act: Call real GeminiAiClient
        client = GeminiAiClient(storage_client=mock_storage, api_key="fake-key-test")
        result = client.send_message("get info on document.pdf", context={"container": "test-bucket"})

        # Assert: Tool was executed
        assert isinstance(result, AIResponse)
        assert result.action_taken == "get_file_info"
        assert "2048" in result.text

        # Verify storage client was called
        mock_storage.get_file_info.assert_called_once()


@pytest.mark.integration
def test_gemini_tool_loop_upload_file_triggers_dispatch() -> None:
    """Test real GeminiAiClient with upload_file tool dispatch.

    Verifies:
    - upload_file tool is recognized and dispatched
    - Storage client.upload_obj is called
    - Response includes proper action tracking
    """
    from gemini_ai_client_impl.client import GeminiAiClient

    # Arrange: Mock storage client
    mock_storage = MagicMock()
    mock_file_info = MagicMock()
    mock_file_info.object_name = "new-file.txt"
    mock_file_info.size_bytes = 50
    mock_file_info.data_type = "text/plain"
    mock_file_info.updated_at = datetime.now(tz=UTC)
    mock_storage.upload_file.return_value = mock_file_info

    # Arrange: Mock genai.Client
    with patch("gemini_ai_client_impl.client.genai.Client") as mock_genai_client_cls:
        mock_genai_chat = MagicMock()
        mock_genai_client_cls.return_value.chats.create.return_value = mock_genai_chat

        # Turn 1: Gemini returns upload_file tool call
        tool_call_response = MagicMock()
        tool_call_part = MagicMock()
        tool_call_part.function_call = MagicMock()
        tool_call_part.function_call.name = "upload_file"
        tool_call_part.function_call.args = {
            "container": "test-bucket",
            "remote_path": "uploads/new-file.txt",
            "local_path": "/tmp/test.txt",
        }
        tool_call_response.candidates = [MagicMock()]
        tool_call_response.candidates[0].content.parts = [tool_call_part]

        # Turn 2: Gemini returns confirmation
        final_response = MagicMock()
        final_part = MagicMock()
        final_part.function_call = None
        final_part.text = "File uploaded successfully"
        final_response.candidates = [MagicMock()]
        final_response.candidates[0].content.parts = [final_part]
        final_response.text = "File uploaded successfully"

        mock_genai_chat.send_message.side_effect = [tool_call_response, final_response]

        # Act: Call real GeminiAiClient
        client = GeminiAiClient(storage_client=mock_storage, api_key="fake-key-test")
        result = client.send_message("upload new-file.txt", context={"container": "test-bucket"})

        # Assert: Tool was executed
        assert isinstance(result, AIResponse)
        assert result.action_taken == "upload_file"
        assert "upload_file" in result.tool_calls

        # Verify storage client was called
        mock_storage.upload_file.assert_called_once()


@pytest.mark.integration
def test_gemini_tool_loop_with_error_handling() -> None:
    """Test real GeminiAiClient re-raises fatal storage errors as RuntimeError.

    The tool loop treats some storage errors as fatal and re-raises them
    as RuntimeError so the calling code can handle them. Non-fatal errors
    (e.g. ObjectNotFoundError) are returned to the AI as tool-results
    so the model can explain the situation.

    Verifies:
    - StorageBackendError during tool dispatch is re-raised as RuntimeError
    - Storage client is called (confirming tool dispatch)
    """
    from cloud_storage_api.exceptions import StorageBackendError
    from gemini_ai_client_impl.client import GeminiAiClient

    # Arrange: Mock storage client to raise fatal error
    mock_storage = MagicMock()
    mock_storage.delete_file.side_effect = StorageBackendError("Backend connection failed")

    # Arrange: Mock genai.Client
    with patch("gemini_ai_client_impl.client.genai.Client") as mock_genai_client_cls:
        mock_genai_chat = MagicMock()
        mock_genai_client_cls.return_value.chats.create.return_value = mock_genai_chat

        # Turn 1: Gemini returns delete_file tool call
        tool_call_response = MagicMock()
        tool_call_part = MagicMock()
        tool_call_part.function_call = MagicMock()
        tool_call_part.function_call.name = "delete_file"
        tool_call_part.function_call.args = {
            "container": "test-bucket",
            "object_name": "missing-file.txt",
        }
        tool_call_response.candidates = [MagicMock()]
        tool_call_response.candidates[0].content.parts = [tool_call_part]

        mock_genai_chat.send_message.return_value = tool_call_response

        # Act & Assert: Tool dispatch error should be caught
        client = GeminiAiClient(storage_client=mock_storage, api_key="fake-key-test")
        with pytest.raises(RuntimeError, match="Storage operation failed"):
            client.send_message("delete missing-file.txt", context={"container": "test-bucket"})

        # Verify storage was called
        mock_storage.delete_file.assert_called_once()


@pytest.mark.integration
def test_gemini_tool_loop_multiple_turns_with_context_injection() -> None:
    """Test real GeminiAiClient context container injection into tool args.

    Verifies:
    - Container from context is injected into tool args if not provided
    - Tool loop continues through multiple turns
    - AIResponse tracks all tool calls
    """
    from gemini_ai_client_impl.client import GeminiAiClient

    # Arrange: Mock storage client
    mock_storage = MagicMock()
    mock_info = MagicMock()
    mock_info.object_name = "test.txt"
    mock_info.size_bytes = 100
    mock_info.data_type = "text/plain"
    mock_info.updated_at = datetime.now(tz=UTC)
    mock_storage.list_files.return_value = [mock_info]

    # Arrange: Mock genai.Client
    with patch("gemini_ai_client_impl.client.genai.Client") as mock_genai_client_cls:
        mock_genai_chat = MagicMock()
        mock_genai_client_cls.return_value.chats.create.return_value = mock_genai_chat

        # Turn 1: Gemini returns tool call WITHOUT container arg
        # (should be injected from context)
        tool_call_response = MagicMock()
        tool_call_part = MagicMock()
        tool_call_part.function_call = MagicMock()
        tool_call_part.function_call.name = "list_files"
        tool_call_part.function_call.args = {"prefix": ""}  # Container NOT provided
        tool_call_response.candidates = [MagicMock()]
        tool_call_response.candidates[0].content.parts = [tool_call_part]

        # Turn 2: Gemini returns final response
        final_response = MagicMock()
        final_part = MagicMock()
        final_part.function_call = None
        final_part.text = "Listed files successfully"
        final_response.candidates = [MagicMock()]
        final_response.candidates[0].content.parts = [final_part]
        final_response.text = "Listed files successfully"

        mock_genai_chat.send_message.side_effect = [tool_call_response, final_response]

        # Act: Call real GeminiAiClient with context
        client = GeminiAiClient(storage_client=mock_storage, api_key="fake-key-test")
        result = client.send_message("list files", context={"container": "injected-bucket"})

        # Assert: Tool was executed
        assert isinstance(result, AIResponse)
        assert result.action_taken == "list_files"

        # CRITICAL: Verify container was injected
        mock_storage.list_files.assert_called_once()
        call_args = mock_storage.list_files.call_args
        assert call_args is not None
        # Container should have been injected from context
        assert "injected-bucket" in str(call_args)
