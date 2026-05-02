"""Unit tests for Gemini client tools.

All tests in this file mock the CloudStorageClient and verify the dispatch
layer's tool functions, error handling, arg validation, and temp-file lifecycle.

Per peer-review feedback (HW-3), every test name ends with _mock to make the
mocked nature explicit.
"""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from cloud_storage_api.exceptions import (
    ContainerNotFoundError,
    LocalFileAccessError,
    ObjectNotFoundError,
)

from gemini_ai_client_impl.tools import dispatch_tool_call

# ============================================================================
# Fixtures
# ============================================================================

FIXED_TIMESTAMP = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def mock_storage_client() -> MagicMock:
    """A mock CloudStorageClient with deterministic ObjectInfo defaults."""
    mock = MagicMock()
    mock_info = MagicMock()
    mock_info.object_name = "test.txt"
    mock_info.size_bytes = 1024
    mock_info.data_type = "text/plain"
    mock_info.updated_at = FIXED_TIMESTAMP
    mock.get_file_info.return_value = mock_info
    mock.list_files.return_value = [mock_info]
    return mock


# ============================================================================
# list_files
# ============================================================================


@pytest.mark.unit
def test_list_files_calls_storage_and_returns_json_mock(
    mock_storage_client: MagicMock,
) -> None:
    """list_files calls storage and returns a JSON-encoded list."""
    result = dispatch_tool_call(
        "list_files",
        {"container": "test-bucket", "prefix": "docs/"},
        mock_storage_client,
    )

    mock_storage_client.list_files.assert_called_once_with("test-bucket", "docs/")
    assert isinstance(result, str)
    parsed = json.loads(result)
    assert isinstance(parsed, list)
    assert parsed[0]["object_name"] == "test.txt"
    assert parsed[0]["updated_at"] == FIXED_TIMESTAMP.isoformat()


@pytest.mark.unit
def test_list_files_with_default_prefix_mock(
    mock_storage_client: MagicMock,
) -> None:
    """list_files defaults prefix to empty string when not supplied."""
    result = dispatch_tool_call(
        "list_files",
        {"container": "test-bucket"},
        mock_storage_client,
    )

    mock_storage_client.list_files.assert_called_once_with("test-bucket", "")
    assert isinstance(result, str)


@pytest.mark.unit
def test_list_files_container_not_found_returns_error_string_mock(
    mock_storage_client: MagicMock,
) -> None:
    """list_files returns an error string when the container doesn't exist."""
    mock_storage_client.list_files.side_effect = ContainerNotFoundError("nope")

    result = dispatch_tool_call(
        "list_files",
        {"container": "missing-bucket"},
        mock_storage_client,
    )

    assert isinstance(result, str)
    assert "Error" in result
    assert "missing-bucket" in result


# ============================================================================
# get_file_info
# ============================================================================


@pytest.mark.unit
def test_get_file_info_returns_serialized_object_info_mock(
    mock_storage_client: MagicMock,
) -> None:
    """get_file_info returns a JSON-serialized ObjectInfo."""
    result = dispatch_tool_call(
        "get_file_info",
        {"container": "test-bucket", "object_name": "file.txt"},
        mock_storage_client,
    )

    mock_storage_client.get_file_info.assert_called_once_with(
        "test-bucket",
        "file.txt",
    )
    parsed = json.loads(result)
    assert parsed["object_name"] == "test.txt"
    assert parsed["size_bytes"] == 1024
    assert parsed["updated_at"] == FIXED_TIMESTAMP.isoformat()


@pytest.mark.unit
def test_get_file_info_not_found_returns_error_string_mock(
    mock_storage_client: MagicMock,
) -> None:
    """get_file_info returns a recoverable error string when not found."""
    mock_storage_client.get_file_info.side_effect = ObjectNotFoundError("not found")

    result = dispatch_tool_call(
        "get_file_info",
        {"container": "test-bucket", "object_name": "missing.txt"},
        mock_storage_client,
    )

    assert isinstance(result, str)
    assert "Error" in result
    assert "missing.txt" in result


# ============================================================================
# delete_file
# ============================================================================


@pytest.mark.unit
def test_delete_file_returns_confirmation_mock(
    mock_storage_client: MagicMock,
) -> None:
    """delete_file returns a confirmation string mentioning the object/bucket."""
    result = dispatch_tool_call(
        "delete_file",
        {"container": "test-bucket", "object_name": "file.txt"},
        mock_storage_client,
    )

    mock_storage_client.delete_file.assert_called_once_with(
        "test-bucket",
        "file.txt",
    )
    assert "Deleted" in result
    assert "file.txt" in result
    assert "test-bucket" in result


@pytest.mark.unit
def test_delete_file_not_found_returns_error_string_mock(
    mock_storage_client: MagicMock,
) -> None:
    """delete_file returns an error string when the object doesn't exist."""
    mock_storage_client.delete_file.side_effect = ObjectNotFoundError("not found")

    result = dispatch_tool_call(
        "delete_file",
        {"container": "test-bucket", "object_name": "missing.txt"},
        mock_storage_client,
    )

    assert isinstance(result, str)
    assert "Error" in result


# ============================================================================
# upload_file
# ============================================================================


@pytest.mark.unit
def test_upload_file_returns_confirmation_mock(
    mock_storage_client: MagicMock,
) -> None:
    """upload_file returns a confirmation string with object name and size."""
    mock_info = MagicMock()
    mock_info.object_name = "uploaded.txt"
    mock_info.size_bytes = 512
    mock_storage_client.upload_file.return_value = mock_info

    result = dispatch_tool_call(
        "upload_file",
        {
            "container": "test-bucket",
            "local_path": "/tmp/file.txt",
            "remote_path": "uploaded.txt",
        },
        mock_storage_client,
    )

    mock_storage_client.upload_file.assert_called_once()
    assert "Uploaded" in result
    assert "uploaded.txt" in result


@pytest.mark.unit
def test_upload_file_local_access_error_returns_error_string_mock(
    mock_storage_client: MagicMock,
) -> None:
    """upload_file returns an error string when the local file is unreadable."""
    mock_storage_client.upload_file.side_effect = LocalFileAccessError("file not found")

    result = dispatch_tool_call(
        "upload_file",
        {
            "container": "test-bucket",
            "local_path": "/tmp/missing.txt",
            "remote_path": "file.txt",
        },
        mock_storage_client,
    )

    assert isinstance(result, str)
    assert "Error" in result


# ============================================================================
# download_file
# ============================================================================


@pytest.mark.unit
def test_download_file_returns_confirmation_mock(
    mock_storage_client: MagicMock,
) -> None:
    """download_file returns a confirmation string referencing both paths."""
    result = dispatch_tool_call(
        "download_file",
        {
            "container": "test-bucket",
            "object_name": "file.txt",
            "file_name": "/tmp/local.txt",
        },
        mock_storage_client,
    )

    mock_storage_client.download_file.assert_called_once()
    assert "Downloaded" in result


@pytest.mark.unit
def test_download_file_not_found_returns_error_string_mock(
    mock_storage_client: MagicMock,
) -> None:
    """download_file returns an error string when the object doesn't exist."""
    mock_storage_client.download_file.side_effect = ObjectNotFoundError("not found")

    result = dispatch_tool_call(
        "download_file",
        {
            "container": "test-bucket",
            "object_name": "missing.txt",
            "file_name": "/tmp/local.txt",
        },
        mock_storage_client,
    )

    assert isinstance(result, str)
    assert "Error" in result


# ============================================================================
# summarize_file
# ============================================================================


@pytest.mark.unit
def test_summarize_file_text_returns_content_mock(
    mock_storage_client: MagicMock,
) -> None:
    """summarize_file with a text file returns the raw content."""

    def download_mock(_container: str, _obj_name: str, file_name: str) -> None:
        Path(file_name).write_text("Q1 revenue was $1M")

    mock_storage_client.download_file.side_effect = download_mock

    result = dispatch_tool_call(
        "summarize_file",
        {"container": "test-bucket", "object_name": "report.txt"},
        mock_storage_client,
    )

    assert isinstance(result, str)
    assert "Q1 revenue" in result


@pytest.mark.unit
def test_summarize_file_returns_full_content_for_large_files_mock(
    mock_storage_client: MagicMock,
) -> None:
    """summarize_file returns the full file content without truncation."""

    def download_mock(_container: str, _obj_name: str, file_name: str) -> None:
        Path(file_name).write_text("x" * 10000)

    mock_storage_client.download_file.side_effect = download_mock

    result = dispatch_tool_call(
        "summarize_file",
        {"container": "test-bucket", "object_name": "large.txt"},
        mock_storage_client,
    )

    assert result == "x" * 10000


@pytest.mark.unit
def test_summarize_file_unsupported_type_returns_message_mock(
    mock_storage_client: MagicMock,
) -> None:
    """summarize_file rejects unsupported extensions without downloading."""
    result = dispatch_tool_call(
        "summarize_file",
        {"container": "test-bucket", "object_name": "archive.zip"},
        mock_storage_client,
    )

    assert "not supported" in result
    mock_storage_client.download_file.assert_not_called()


@pytest.mark.unit
def test_summarize_file_not_found_returns_error_string_mock(
    mock_storage_client: MagicMock,
) -> None:
    """summarize_file returns an error string when the object doesn't exist."""
    mock_storage_client.download_file.side_effect = ObjectNotFoundError("not found")

    result = dispatch_tool_call(
        "summarize_file",
        {"container": "test-bucket", "object_name": "missing.txt"},
        mock_storage_client,
    )

    assert isinstance(result, str)
    assert "Error" in result


@pytest.mark.unit
def test_summarize_file_invalid_utf8_returns_error_string_mock(
    mock_storage_client: MagicMock,
) -> None:
    """summarize_file gracefully handles non-UTF-8 text files."""

    def download_mock(_container: str, _obj_name: str, file_name: str) -> None:
        Path(file_name).write_bytes(b"\xff\xfe\x00\x00invalid utf-8")

    mock_storage_client.download_file.side_effect = download_mock

    result = dispatch_tool_call(
        "summarize_file",
        {"container": "test-bucket", "object_name": "binary.txt"},
        mock_storage_client,
    )

    assert "Could not decode" in result
    assert "binary.txt" in result


@pytest.mark.unit
def test_summarize_file_pdf_returns_base64_prefix_mock(
    mock_storage_client: MagicMock,
) -> None:
    """summarize_file with a PDF returns base64-encoded content with sentinel."""

    def download_mock(_container: str, _obj_name: str, file_name: str) -> None:
        Path(file_name).write_bytes(b"%PDF-1.4")

    mock_storage_client.download_file.side_effect = download_mock

    result = dispatch_tool_call(
        "summarize_file",
        {"container": "test-bucket", "object_name": "document.pdf"},
        mock_storage_client,
    )

    assert result.startswith("PDF_CONTENT_BASE64:")
    encoded = result[len("PDF_CONTENT_BASE64:") :]
    decoded = base64.b64decode(encoded)
    assert decoded == b"%PDF-1.4"


@pytest.mark.unit
def test_summarize_file_cleans_up_temp_file_on_error_mock(
    mock_storage_client: MagicMock,
) -> None:
    """Temp file is cleaned up even when the download fails."""
    captured_path: list[str] = []

    def download_error(_container: str, _obj_name: str, file_name: str) -> None:
        captured_path.append(file_name)
        Path(file_name).write_text("test")
        msg = "error"
        raise ObjectNotFoundError(msg)

    mock_storage_client.download_file.side_effect = download_error

    result = dispatch_tool_call(
        "summarize_file",
        {"container": "test-bucket", "object_name": "missing.txt"},
        mock_storage_client,
    )

    assert isinstance(result, str)
    assert "Error" in result
    assert len(captured_path) == 1
    assert not Path(captured_path[0]).exists()


@pytest.mark.unit
@pytest.mark.parametrize(
    ("object_name", "content"),
    [
        ("notes.txt", b"hello"),
        ("doc.pdf", b"%PDF-1.4"),
    ],
)
def test_summarize_file_cleans_up_temp_file_on_success_mock(
    mock_storage_client: MagicMock,
    object_name: str,
    content: bytes,
) -> None:
    """Temp file is cleaned up after successful text and PDF summarization."""
    captured_path: list[str] = []

    def download_mock(_container: str, _obj_name: str, file_name: str) -> None:
        captured_path.append(file_name)
        Path(file_name).write_bytes(content)

    mock_storage_client.download_file.side_effect = download_mock

    dispatch_tool_call(
        "summarize_file",
        {"container": "test-bucket", "object_name": object_name},
        mock_storage_client,
    )

    assert len(captured_path) == 1
    assert not Path(captured_path[0]).exists()


# ============================================================================
# Dispatch routing and arg validation
# ============================================================================


@pytest.mark.unit
def test_dispatch_tool_call_routes_correctly_mock(
    mock_storage_client: MagicMock,
) -> None:
    """dispatch_tool_call routes each tool name to its function."""
    dispatch_tool_call("list_files", {"container": "test-bucket"}, mock_storage_client)
    mock_storage_client.list_files.assert_called_once()

    mock_storage_client.reset_mock()

    dispatch_tool_call(
        "delete_file",
        {"container": "test-bucket", "object_name": "file.txt"},
        mock_storage_client,
    )
    mock_storage_client.delete_file.assert_called_once()


@pytest.mark.unit
def test_dispatch_tool_call_unknown_tool_raises_value_error_mock(
    mock_storage_client: MagicMock,
) -> None:
    """Unknown tool names raise ValueError (programming bug, not user error)."""
    with pytest.raises(ValueError, match="Unknown tool"):
        dispatch_tool_call("unknown_tool", {}, mock_storage_client)


@pytest.mark.unit
def test_dispatch_tool_call_missing_container_returns_error_string_mock(
    mock_storage_client: MagicMock,
) -> None:
    """Missing required arg 'container' returns a recoverable error string."""
    result = dispatch_tool_call("list_files", {}, mock_storage_client)

    assert "missing required arg" in result
    assert "container" in result
    mock_storage_client.list_files.assert_not_called()


@pytest.mark.unit
def test_dispatch_tool_call_missing_object_name_returns_error_string_mock(
    mock_storage_client: MagicMock,
) -> None:
    """Missing required arg 'object_name' returns a recoverable error string."""
    result = dispatch_tool_call(
        "delete_file",
        {"container": "test"},
        mock_storage_client,
    )

    assert "missing required arg" in result
    assert "object_name" in result
    mock_storage_client.delete_file.assert_not_called()


@pytest.mark.unit
def test_dispatch_tool_call_missing_upload_args_returns_error_string_mock(
    mock_storage_client: MagicMock,
) -> None:
    """upload_file surfaces the first missing required arg by name."""
    result = dispatch_tool_call(
        "upload_file",
        {"container": "test", "local_path": "/tmp/x"},
        mock_storage_client,
    )

    assert "missing required arg" in result
    assert "remote_path" in result
    mock_storage_client.upload_file.assert_not_called()
