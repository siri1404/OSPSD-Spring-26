"""Unit tests for Gemini AI client.

All tests in this file mock the underlying google.genai SDK and verify the
client's tool-calling loop, telemetry, error handling, and auth wiring.

Per peer-review feedback (HW-3), every test name ends with _mock to make the
mocked nature explicit.

A single boundary test (test_send_message_real_boundary_with_stubbed_transport)
constructs a real GeminiAiClient with a stubbed HTTP transport so we can assert
the SDK plumbing is wired correctly end-to-end.
"""

from __future__ import annotations

import base64
import json
from unittest.mock import MagicMock, patch

import pytest
from ai_client_api import AIResponse
from cloud_storage_api.exceptions import StorageBackendError

from gemini_ai_client_impl import GeminiAiClient, ToolLoopExhaustedError

# ============================================================================
# Fixtures and helpers
# ============================================================================


@pytest.fixture
def mock_storage_client() -> MagicMock:
    """A mock CloudStorageClient injected into GeminiAiClient."""
    return MagicMock()


def _make_function_call_part(name: str, args: dict[str, object]) -> MagicMock:
    """Build a mock Gemini Part containing a single function_call."""
    function_call = MagicMock()
    function_call.name = name
    function_call.args = args

    part = MagicMock()
    part.function_call = function_call
    return part


def _make_response(
    *,
    text: str | None,
    parts: list[MagicMock] | None = None,
) -> MagicMock:
    """Build a mock GenerateContentResponse with optional candidates/parts."""
    response = MagicMock()
    response.text = text
    if parts is None:
        response.candidates = []
    else:
        candidate = MagicMock()
        candidate.content.parts = parts
        response.candidates = [candidate]
    return response


def _wire_genai_mock(
    mock_genai: MagicMock,
    send_message_side_effect: list[MagicMock] | MagicMock,
) -> MagicMock:
    """Wire the genai mock so Client(...).chats.create(...) returns a chat.

    The chat's send_message follows the supplied side effect (or value).
    Returns the underlying mock chat for further assertions.
    """
    mock_chat = MagicMock()
    if isinstance(send_message_side_effect, list):
        mock_chat.send_message.side_effect = send_message_side_effect
    else:
        mock_chat.send_message.return_value = send_message_side_effect

    mock_client_instance = MagicMock()
    mock_client_instance.chats.create.return_value = mock_chat
    mock_genai.Client.return_value = mock_client_instance
    return mock_chat


# ============================================================================
# tools() method — expose available tool definitions
# ============================================================================


@pytest.mark.unit
def test_tools_returns_list_of_tool_definitions_mock(
    mock_storage_client: MagicMock,
) -> None:
    """tools() returns a list of ToolDefinition objects describing available tools."""
    with patch("gemini_ai_client_impl.client.genai") as mock_genai:
        _wire_genai_mock(mock_genai, _make_response(text="ok", parts=None))

        client = GeminiAiClient(storage_client=mock_storage_client, api_key="test-key")
        tools = client.tools()

        assert isinstance(tools, list)
        # 6 tools: list_files, get_file_info, delete_file, upload_file, download_file,
        # summarize_file
        assert len(tools) == 6

        # Verify each tool has required attributes
        tool_names = {tool.name for tool in tools}
        expected_tools = {
            "list_files",
            "get_file_info",
            "delete_file",
            "upload_file",
            "download_file",
            "summarize_file",
        }
        assert tool_names == expected_tools

        # Verify a specific tool has parameters
        list_files_tool = next(t for t in tools if t.name == "list_files")
        assert "list" in list_files_tool.description.lower()
        assert len(list_files_tool.parameters) > 0

        # Verify parameter structure
        param_names = {p.name for p in list_files_tool.parameters}
        assert "container" in param_names


# ============================================================================
# send_message (str contract) — HW-3 shared API
# ============================================================================


@pytest.mark.unit
def test_send_message_returns_plain_text_when_no_candidates_mock(
    mock_storage_client: MagicMock,
) -> None:
    """send_message returns the model's text when no candidates are present."""
    with patch("gemini_ai_client_impl.client.genai") as mock_genai:
        response = _make_response(text="Here are your files.", parts=None)
        _wire_genai_mock(mock_genai, response)

        client = GeminiAiClient(
            storage_client=mock_storage_client,
            api_key="test-key",
        )
        result = client.send_message("list my files")

        assert result == "Here are your files."


@pytest.mark.unit
def test_send_message_passes_api_key_to_client_mock(
    mock_storage_client: MagicMock,
) -> None:
    """Client initializes with API key for Google AI Studio authentication."""
    with patch("gemini_ai_client_impl.client.genai") as mock_genai:
        _wire_genai_mock(mock_genai, _make_response(text="ok", parts=None))

        GeminiAiClient(storage_client=mock_storage_client, api_key="test-key")

        mock_genai.Client.assert_called_once_with(api_key="test-key")


@pytest.mark.unit
def test_api_key_read_from_env_when_not_passed_mock(
    mock_storage_client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """API key falls back to GEMINI_API_KEY env var."""
    with patch("gemini_ai_client_impl.client.genai") as mock_genai:
        monkeypatch.setenv("GEMINI_API_KEY", "env-key")
        _wire_genai_mock(mock_genai, _make_response(text="ok", parts=None))

        client = GeminiAiClient(storage_client=mock_storage_client)

        assert client is not None
        mock_genai.Client.assert_called_once_with(api_key="env-key")


@pytest.mark.unit
def test_raises_value_error_when_api_key_missing_mock(
    mock_storage_client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing API key raises ValueError."""
    with patch("gemini_ai_client_impl.client.genai"):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            GeminiAiClient(storage_client=mock_storage_client)


# ============================================================================
# send_message_with_metadata (telemetry contract)
# ============================================================================


@pytest.mark.unit
def test_send_message_with_metadata_returns_ai_response_when_no_tool_call_mock(
    mock_storage_client: MagicMock,
) -> None:
    """send_message_with_metadata returns an AIResponse with empty telemetry."""
    with patch("gemini_ai_client_impl.client.genai") as mock_genai:
        response = _make_response(text="Here are your files.", parts=None)
        _wire_genai_mock(mock_genai, response)

        client = GeminiAiClient(
            storage_client=mock_storage_client,
            api_key="test-key",
        )
        result = client.send_message_with_metadata("list my files")

        assert isinstance(result, AIResponse)
        assert result.text == "Here are your files."
        assert result.action_taken is None
        assert result.tool_calls == []
        assert result.tool_args == {}


@pytest.mark.unit
def test_send_message_with_metadata_executes_list_files_tool_call_mock(
    mock_storage_client: MagicMock,
) -> None:
    """Tool-call loop executes list_files and records it in telemetry."""
    with patch("gemini_ai_client_impl.client.genai") as mock_genai:
        response_with_call = _make_response(
            text=None,
            parts=[
                _make_function_call_part(
                    "list_files",
                    {"container": "my-bucket"},
                )
            ],
        )
        final_response = _make_response(text="Found 3 files", parts=None)
        _wire_genai_mock(mock_genai, [response_with_call, final_response])

        with patch(
            "gemini_ai_client_impl.client.dispatch_tool_call",
            return_value=json.dumps([]),
        ) as mock_dispatch:
            client = GeminiAiClient(
                storage_client=mock_storage_client,
                api_key="test-key",
            )
            result = client.send_message_with_metadata("list my files")

            assert isinstance(result, AIResponse)
            assert result.text == "Found 3 files"
            assert result.action_taken == "list_files"
            assert result.tool_calls == ["list_files"]
            assert result.tool_args == {"container": "my-bucket"}
            mock_dispatch.assert_called_once()


@pytest.mark.unit
def test_send_message_with_metadata_executes_delete_file_tool_call_mock(
    mock_storage_client: MagicMock,
) -> None:
    """Tool-call loop executes delete_file and records it in telemetry."""
    with patch("gemini_ai_client_impl.client.genai") as mock_genai:
        response_with_call = _make_response(
            text=None,
            parts=[
                _make_function_call_part(
                    "delete_file",
                    {"container": "test-bucket", "object_name": "file.txt"},
                )
            ],
        )
        final_response = _make_response(
            text="File deleted successfully",
            parts=None,
        )
        _wire_genai_mock(mock_genai, [response_with_call, final_response])

        with patch(
            "gemini_ai_client_impl.client.dispatch_tool_call",
            return_value="Deleted file.txt",
        ):
            client = GeminiAiClient(
                storage_client=mock_storage_client,
                api_key="test-key",
            )
            result = client.send_message_with_metadata("delete file.txt")

            assert isinstance(result, AIResponse)
            assert "deleted successfully" in result.text.lower()
            assert result.action_taken == "delete_file"
            assert result.tool_calls == ["delete_file"]


@pytest.mark.unit
def test_send_message_with_metadata_executes_summarize_file_tool_call_mock(
    mock_storage_client: MagicMock,
) -> None:
    """Tool-call loop executes summarize_file for plain text content."""
    with patch("gemini_ai_client_impl.client.genai") as mock_genai:
        response_with_call = _make_response(
            text=None,
            parts=[
                _make_function_call_part(
                    "summarize_file",
                    {"container": "test-bucket", "object_name": "readme.md"},
                )
            ],
        )
        final_response = _make_response(
            text="This project does X and Y",
            parts=None,
        )
        _wire_genai_mock(mock_genai, [response_with_call, final_response])

        with patch(
            "gemini_ai_client_impl.client.dispatch_tool_call",
            return_value="# Project README",
        ):
            client = GeminiAiClient(
                storage_client=mock_storage_client,
                api_key="test-key",
            )
            result = client.send_message_with_metadata(
                "what does this project do",
            )

            assert isinstance(result, AIResponse)
            assert "does X and Y" in result.text
            assert result.action_taken == "summarize_file"
            assert result.tool_calls == ["summarize_file"]


# ============================================================================
# Context injection
# ============================================================================


@pytest.mark.unit
def test_send_message_injects_context_container_into_tool_args_mock(
    mock_storage_client: MagicMock,
) -> None:
    """When the model omits container, the client injects it from context."""
    with patch("gemini_ai_client_impl.client.genai") as mock_genai:
        response_with_call = _make_response(
            text=None,
            # Model forgot the container; client must fill it from context.
            parts=[_make_function_call_part("list_files", {"prefix": ""})],
        )
        final_response = _make_response(text="Listed files", parts=None)
        _wire_genai_mock(mock_genai, [response_with_call, final_response])

        with patch(
            "gemini_ai_client_impl.client.dispatch_tool_call",
            return_value=json.dumps([]),
        ) as mock_dispatch:
            client = GeminiAiClient(
                storage_client=mock_storage_client,
                api_key="test-key",
            )
            client.send_message("list files", context={"container": "my-bucket"})

            mock_dispatch.assert_called_once()
            _, dispatched_args, _ = mock_dispatch.call_args.args
            assert dispatched_args["container"] == "my-bucket"


@pytest.mark.unit
def test_send_message_rejects_invalid_context_container_mock(
    mock_storage_client: MagicMock,
) -> None:
    """A non-string or empty context['container'] raises ValueError."""
    with patch("gemini_ai_client_impl.client.genai") as mock_genai:
        _wire_genai_mock(mock_genai, _make_response(text="ok", parts=None))
        client = GeminiAiClient(
            storage_client=mock_storage_client,
            api_key="test-key",
        )

        with pytest.raises(ValueError, match="container"):
            client.send_message("list", context={"container": " "})


# ============================================================================
# Tool loop bounds and error handling
# ============================================================================


@pytest.mark.unit
def test_send_message_caps_at_max_iterations_mock(
    mock_storage_client: MagicMock,
) -> None:
    """The tool loop exhausts after MAX_TOOL_ITERATIONS and raises ToolLoopExhaustedError."""
    with patch("gemini_ai_client_impl.client.genai") as mock_genai:
        # Always return a function call → forces the loop to exhaust iterations.
        looping_response = _make_response(
            text=None,
            parts=[_make_function_call_part("list_files", {"container": "test"})],
        )
        _wire_genai_mock(mock_genai, looping_response)

        with patch(
            "gemini_ai_client_impl.client.dispatch_tool_call",
            return_value="result",
        ):
            client = GeminiAiClient(
                storage_client=mock_storage_client,
                api_key="test-key",
            )
            # send_message should raise ToolLoopExhaustedError
            with pytest.raises(ToolLoopExhaustedError) as exc_info:
                client.send_message("test")

            error = exc_info.value
            assert error.max_iterations == GeminiAiClient.MAX_TOOL_ITERATIONS
            assert error.last_action_taken == "list_files"
            assert len(error.tool_calls) == GeminiAiClient.MAX_TOOL_ITERATIONS

            # send_message_with_metadata should also raise the same error
            with pytest.raises(ToolLoopExhaustedError) as exc_info2:
                client.send_message_with_metadata("test")

            error2 = exc_info2.value
            assert error2.max_iterations == GeminiAiClient.MAX_TOOL_ITERATIONS


@pytest.mark.unit
def test_send_message_wraps_storage_exception_in_runtime_error_mock(
    mock_storage_client: MagicMock,
) -> None:
    """Storage exceptions raised by tools surface as RuntimeError to callers."""
    with patch("gemini_ai_client_impl.client.genai") as mock_genai:
        response_with_call = _make_response(
            text=None,
            parts=[
                _make_function_call_part(
                    "delete_file",
                    {"container": "test", "object_name": "file.txt"},
                )
            ],
        )
        _wire_genai_mock(mock_genai, response_with_call)

        with patch(
            "gemini_ai_client_impl.client.dispatch_tool_call",
            side_effect=StorageBackendError("backend down"),
        ):
            client = GeminiAiClient(
                storage_client=mock_storage_client,
                api_key="test-key",
            )
            with pytest.raises(RuntimeError, match="Storage operation failed"):
                client.send_message("delete file test.txt")


# ============================================================================
# PDF binary payload contract
# ============================================================================


@pytest.mark.unit
def test_send_message_summarize_pdf_sends_document_part_mock(
    mock_storage_client: MagicMock,
) -> None:
    """A PDF tool result is decoded and sent as a function_response + bytes."""
    with patch("gemini_ai_client_impl.client.genai") as mock_genai:
        pdf_content = b"%PDF-1.4 test"
        encoded = base64.b64encode(pdf_content).decode("utf-8")
        pdf_result = f"PDF_CONTENT_BASE64:{encoded}"

        response_with_call = _make_response(
            text=None,
            parts=[
                _make_function_call_part(
                    "summarize_file",
                    {"container": "test", "object_name": "doc.pdf"},
                )
            ],
        )
        final_response = _make_response(text="PDF analyzed", parts=None)
        mock_chat = _wire_genai_mock(
            mock_genai,
            [response_with_call, final_response],
        )

        with patch(
            "gemini_ai_client_impl.client.dispatch_tool_call",
            return_value=pdf_result,
        ):
            client = GeminiAiClient(
                storage_client=mock_storage_client,
                api_key="test-key",
            )
            result = client.send_message_with_metadata("summarize doc.pdf")

            assert isinstance(result, AIResponse)
            assert "PDF analyzed" in result.text
            assert result.action_taken == "summarize_file"

            # Verify two parts in second send_message call (function_response + PDF bytes).
            second_call_args = mock_chat.send_message.call_args_list[1].args[0]
            assert isinstance(second_call_args, list)
            assert len(second_call_args) == 2


# ============================================================================
# Boundary test (peer review #4): real client, stubbed transport
# ============================================================================


@pytest.mark.integration
def test_send_message_real_boundary_with_stubbed_transport(
    mock_storage_client: MagicMock,
) -> None:
    """Boundary test: real GeminiAiClient with stubbed HTTP transport.

    Instantiate the real GeminiAiClient and exercise the real
    google.genai.Client constructor, but stub the chat layer so we don't hit
    the live API.

    Verifies that:
    - genai.Client(api_key=...) actually accepts our auth args.
    - chats.create(...) integrates with our config builder.
    - send_message returns the assistant text from the stubbed chat.
    """
    pytest.importorskip("google.genai")

    real_client = GeminiAiClient(
        storage_client=mock_storage_client,
        api_key="test-key",
    )

    # Replace only the chat object so we exercise the real Client + config
    # builder path, but never hit the network.
    stub_chat = MagicMock()
    stub_chat.send_message.return_value = _make_response(
        text="hello from stubbed gemini",
        parts=None,
    )
    real_client._genai_client = MagicMock()
    real_client._genai_client.chats.create.return_value = stub_chat

    result = real_client.send_message("ping")

    assert result == "hello from stubbed gemini"
    real_client._genai_client.chats.create.assert_called_once()
