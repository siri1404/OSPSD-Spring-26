"""Unit tests for Gemini AI client."""

from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch

import pytest
from cloud_storage_api.exceptions import (
    AuthenticationError,
    ObjectNotFoundError,
    StorageBackendError,
)
from gemini_ai_client_impl import GeminiAiClient


@pytest.fixture
def mock_storage_client() -> MagicMock:
    """Create a mock CloudStorageClient."""
    return MagicMock()


@pytest.mark.unit
def test_send_message_returns_text_when_no_tool_call(mock_storage_client: MagicMock) -> None:
    """Test send_message returns plain text when no tool calls."""
    with patch("gemini_ai_client_impl.client.genai") as mock_genai:
        # Mock response with no function calls
        mock_response = MagicMock()
        mock_response.text = "Here are your files."
        mock_response.candidates = []

        mock_chat = MagicMock()
        mock_chat.send_message.return_value = mock_response

        mock_client_instance = MagicMock()
        mock_client_instance.chats.create.return_value = mock_chat
        mock_genai.Client.return_value = mock_client_instance

        client = GeminiAiClient(storage_client=mock_storage_client, api_key="test-key")
        result = client.send_message("list my files")

        assert result == "Here are your files."


@pytest.mark.unit
def test_send_message_executes_list_files_tool_call(mock_storage_client: MagicMock) -> None:
    """Test send_message executes list_files tool call."""
    with patch("gemini_ai_client_impl.client.genai") as mock_genai:
        # Mock first response with function call
        mock_function_call = MagicMock()
        mock_function_call.name = "list_files"
        mock_function_call.args = {"container": "my-bucket"}

        mock_part_with_call = MagicMock()
        mock_part_with_call.function_call = mock_function_call

        mock_candidate = MagicMock()
        mock_candidate.content.parts = [mock_part_with_call]

        mock_response1 = MagicMock()
        mock_response1.candidates = [mock_candidate]
        mock_response1.text = None

        mock_response2 = MagicMock()
        mock_response2.text = "Found 3 files"
        mock_response2.candidates = []

        mock_chat = MagicMock()
        mock_chat.send_message.side_effect = [mock_response1, mock_response2]

        mock_client_instance = MagicMock()
        mock_client_instance.chats.create.return_value = mock_chat
        mock_genai.Client.return_value = mock_client_instance

        with patch("gemini_ai_client_impl.client.dispatch_tool_call", return_value="[]"):
            client = GeminiAiClient(storage_client=mock_storage_client, api_key="test-key")
            result = client.send_message("list my files")

        assert "Found 3 files" in result


@pytest.mark.unit
def test_send_message_injects_context_container(mock_storage_client: MagicMock) -> None:
    """Test send_message injects context container when not provided."""
    with patch("gemini_ai_client_impl.client.genai") as mock_genai:
        mock_function_call = MagicMock()
        mock_function_call.name = "list_files"
        mock_function_call.args = {"prefix": ""}  # No container

        mock_part_with_call = MagicMock()
        mock_part_with_call.function_call = mock_function_call

        mock_candidate = MagicMock()
        mock_candidate.content.parts = [mock_part_with_call]

        mock_response1 = MagicMock()
        mock_response1.candidates = [mock_candidate]
        mock_response1.text = None

        mock_response2 = MagicMock()
        mock_response2.text = "Listed files"
        mock_response2.candidates = []

        mock_chat = MagicMock()
        mock_chat.send_message.side_effect = [mock_response1, mock_response2]

        mock_client_instance = MagicMock()
        mock_client_instance.chats.create.return_value = mock_chat
        mock_genai.Client.return_value = mock_client_instance

        with patch("gemini_ai_client_impl.client.dispatch_tool_call", return_value="[]") as mock_dispatch:
            client = GeminiAiClient(storage_client=mock_storage_client, api_key="test-key")
            client.send_message("list files", context={"container": "my-bucket"})

            # Check that dispatch_tool_call was called with injected container
            mock_dispatch.assert_called_once()
            args = mock_dispatch.call_args
            assert args[0][1]["container"] == "my-bucket"


@pytest.mark.unit
def test_send_message_caps_at_max_iterations(mock_storage_client: MagicMock) -> None:
    """Test send_message caps at max iterations."""
    with patch("gemini_ai_client_impl.client.genai") as mock_genai:
        # Always return function calls
        mock_function_call = MagicMock()
        mock_function_call.name = "list_files"
        mock_function_call.args = {"container": "test"}

        mock_part_with_call = MagicMock()
        mock_part_with_call.function_call = mock_function_call

        mock_candidate = MagicMock()
        mock_candidate.content.parts = [mock_part_with_call]

        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]
        mock_response.text = None

        mock_chat = MagicMock()
        mock_chat.send_message.return_value = mock_response

        mock_client_instance = MagicMock()
        mock_client_instance.chats.create.return_value = mock_chat
        mock_genai.Client.return_value = mock_client_instance

        with patch("gemini_ai_client_impl.client.dispatch_tool_call", return_value="result"):
            client = GeminiAiClient(storage_client=mock_storage_client, api_key="test-key")
            result = client.send_message("test")

        assert "maximum tool call iterations" in result


@pytest.mark.unit
def test_send_message_wraps_storage_exception_in_runtime_error(mock_storage_client: MagicMock) -> None:
    """Test send_message wraps storage exceptions in RuntimeError."""
    with patch("gemini_ai_client_impl.client.genai") as mock_genai:
        mock_function_call = MagicMock()
        mock_function_call.name = "delete_file"
        mock_function_call.args = {"container": "test", "object_name": "file.txt"}

        mock_part_with_call = MagicMock()
        mock_part_with_call.function_call = mock_function_call

        mock_candidate = MagicMock()
        mock_candidate.content.parts = [mock_part_with_call]

        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]
        mock_response.text = None

        mock_chat = MagicMock()
        mock_chat.send_message.return_value = mock_response

        mock_client_instance = MagicMock()
        mock_client_instance.chats.create.return_value = mock_chat
        mock_genai.Client.return_value = mock_client_instance

        with patch("gemini_ai_client_impl.client.dispatch_tool_call") as mock_dispatch:
            mock_dispatch.side_effect = StorageBackendError("backend down")
            client = GeminiAiClient(storage_client=mock_storage_client, api_key="test-key")

            with pytest.raises(RuntimeError):
                client.send_message("delete file test.txt")


@pytest.mark.unit
def test_api_key_read_from_env_when_not_passed(mock_storage_client: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test API key is read from environment when not passed."""
    with patch("gemini_ai_client_impl.client.genai"):
        monkeypatch.setenv("GEMINI_API_KEY", "env-key")
        client = GeminiAiClient(storage_client=mock_storage_client)
        assert client is not None


@pytest.mark.unit
def test_raises_value_error_when_api_key_missing(
    mock_storage_client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test ValueError raised when API key is missing."""
    with patch("gemini_ai_client_impl.client.genai"):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            GeminiAiClient(storage_client=mock_storage_client)


@pytest.mark.unit
def test_send_message_summarize_pdf_sends_document_part(mock_storage_client: MagicMock) -> None:
    """Test send_message sends PDF content as document part."""
    with patch("gemini_ai_client_impl.client.genai") as mock_genai:
        pdf_content = b"%PDF-1.4 test"
        base64_encoded = base64.b64encode(pdf_content).decode("utf-8")
        pdf_result = f"PDF_CONTENT_BASE64:{base64_encoded}"

        mock_function_call = MagicMock()
        mock_function_call.name = "summarize_file"
        mock_function_call.args = {"container": "test", "object_name": "doc.pdf"}

        mock_part_with_call = MagicMock()
        mock_part_with_call.function_call = mock_function_call

        mock_candidate = MagicMock()
        mock_candidate.content.parts = [mock_part_with_call]

        mock_response1 = MagicMock()
        mock_response1.candidates = [mock_candidate]
        mock_response1.text = None

        mock_response2 = MagicMock()
        mock_response2.text = "PDF analyzed"
        mock_response2.candidates = []

        mock_chat = MagicMock()
        mock_chat.send_message.side_effect = [mock_response1, mock_response2]

        mock_client_instance = MagicMock()
        mock_client_instance.chats.create.return_value = mock_chat
        mock_genai.Client.return_value = mock_client_instance

        with patch("gemini_ai_client_impl.client.dispatch_tool_call", return_value=pdf_result):
            client = GeminiAiClient(storage_client=mock_storage_client, api_key="test-key")
            result = client.send_message("summarize doc.pdf")

        assert "PDF analyzed" in result
        second_call_args = mock_chat.send_message.call_args_list[1].args[0]
        assert isinstance(second_call_args, list)
        assert len(second_call_args) == 2


@pytest.mark.unit
def test_send_message_executes_delete_file_tool_call(mock_storage_client: MagicMock) -> None:
    """Test send_message executes delete_file tool call."""
    with patch("gemini_ai_client_impl.client.genai") as mock_genai:
        mock_function_call = MagicMock()
        mock_function_call.name = "delete_file"
        mock_function_call.args = {"container": "test-bucket", "object_name": "file.txt"}

        mock_part_with_call = MagicMock()
        mock_part_with_call.function_call = mock_function_call

        mock_candidate = MagicMock()
        mock_candidate.content.parts = [mock_part_with_call]

        mock_response1 = MagicMock()
        mock_response1.candidates = [mock_candidate]
        mock_response1.text = None

        mock_response2 = MagicMock()
        mock_response2.text = "File deleted successfully"
        mock_response2.candidates = []

        mock_chat = MagicMock()
        mock_chat.send_message.side_effect = [mock_response1, mock_response2]

        mock_client_instance = MagicMock()
        mock_client_instance.chats.create.return_value = mock_chat
        mock_genai.Client.return_value = mock_client_instance

        with patch("gemini_ai_client_impl.client.dispatch_tool_call", return_value="Deleted file.txt"):
            client = GeminiAiClient(storage_client=mock_storage_client, api_key="test-key")
            result = client.send_message("delete file.txt")

        assert "deleted successfully" in result.lower()


@pytest.mark.unit
def test_send_message_executes_summarize_file_tool_call(mock_storage_client: MagicMock) -> None:
    """Test send_message executes summarize_file tool call."""
    with patch("gemini_ai_client_impl.client.genai") as mock_genai:
        mock_function_call = MagicMock()
        mock_function_call.name = "summarize_file"
        mock_function_call.args = {"container": "test-bucket", "object_name": "readme.md"}

        mock_part_with_call = MagicMock()
        mock_part_with_call.function_call = mock_function_call

        mock_candidate = MagicMock()
        mock_candidate.content.parts = [mock_part_with_call]

        mock_response1 = MagicMock()
        mock_response1.candidates = [mock_candidate]
        mock_response1.text = None

        mock_response2 = MagicMock()
        mock_response2.text = "This project does X and Y"
        mock_response2.candidates = []

        mock_chat = MagicMock()
        mock_chat.send_message.side_effect = [mock_response1, mock_response2]

        mock_client_instance = MagicMock()
        mock_client_instance.chats.create.return_value = mock_chat
        mock_genai.Client.return_value = mock_client_instance

        with patch("gemini_ai_client_impl.client.dispatch_tool_call", return_value="# Project README"):
            client = GeminiAiClient(storage_client=mock_storage_client, api_key="test-key")
            result = client.send_message("what does this project do")

        assert "does X and Y" in result
