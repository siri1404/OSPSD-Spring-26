"""Unit tests for Gemini client tools."""

from __future__ import annotations

import base64
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from cloud_storage_api.exceptions import LocalFileAccessError, ObjectNotFoundError
from gemini_ai_client_impl.tools import dispatch_tool_call


@pytest.fixture
def mock_storage_client() -> MagicMock:
    """Create a mock CloudStorageClient."""
    mock = MagicMock()
    mock_info = MagicMock()
    mock_info.object_name = "test.txt"
    mock_info.size_bytes = 1024
    mock_info.data_type = "text/plain"
    mock_info.updated_at = datetime.now()
    mock.get_file_info.return_value = mock_info
    mock.list_files.return_value = [mock_info]
    return mock


@pytest.mark.unit
def test_list_files_calls_storage_and_returns_json(mock_storage_client: MagicMock) -> None:
    """Test list_files calls storage and returns JSON."""
    result = dispatch_tool_call("list_files", {"container": "test-bucket", "prefix": "docs/"}, mock_storage_client)

    mock_storage_client.list_files.assert_called_once_with("test-bucket", "docs/")
    assert isinstance(result, str)
    parsed = json.loads(result)
    assert isinstance(parsed, list)
    assert parsed[0]["object_name"] == "test.txt"


@pytest.mark.unit
def test_list_files_with_default_prefix(mock_storage_client: MagicMock) -> None:
    """Test list_files defaults prefix to empty string."""
    result = dispatch_tool_call("list_files", {"container": "test-bucket"}, mock_storage_client)

    mock_storage_client.list_files.assert_called_once_with("test-bucket", "")
    assert isinstance(result, str)


@pytest.mark.unit
def test_get_file_info_returns_serialized_object_info(mock_storage_client: MagicMock) -> None:
    """Test get_file_info returns serialized ObjectInfo."""
    result = dispatch_tool_call(
        "get_file_info",
        {"container": "test-bucket", "object_name": "file.txt"},
        mock_storage_client,
    )

    mock_storage_client.get_file_info.assert_called_once_with("test-bucket", "file.txt")
    parsed = json.loads(result)
    assert parsed["object_name"] == "test.txt"
    assert parsed["size_bytes"] == 1024


@pytest.mark.unit
def test_get_file_info_not_found_returns_error_string(mock_storage_client: MagicMock) -> None:
    """Test get_file_info returns error string when not found."""
    mock_storage_client.get_file_info.side_effect = ObjectNotFoundError("not found")

    result = dispatch_tool_call(
        "get_file_info",
        {"container": "test-bucket", "object_name": "missing.txt"},
        mock_storage_client,
    )

    assert isinstance(result, str)
    assert "Error" in result
    assert "missing.txt" in result


@pytest.mark.unit
def test_delete_file_returns_confirmation(mock_storage_client: MagicMock) -> None:
    """Test delete_file returns confirmation string."""
    result = dispatch_tool_call(
        "delete_file",
        {"container": "test-bucket", "object_name": "file.txt"},
        mock_storage_client,
    )

    mock_storage_client.delete_file.assert_called_once_with("test-bucket", "file.txt")
    assert "Deleted" in result
    assert "file.txt" in result
    assert "test-bucket" in result


@pytest.mark.unit
def test_delete_file_not_found_returns_error_string(mock_storage_client: MagicMock) -> None:
    """Test delete_file returns error string when not found."""
    mock_storage_client.delete_file.side_effect = ObjectNotFoundError("not found")

    result = dispatch_tool_call(
        "delete_file",
        {"container": "test-bucket", "object_name": "missing.txt"},
        mock_storage_client,
    )

    assert isinstance(result, str)
    assert "Error" in result


@pytest.mark.unit
def test_upload_file_returns_confirmation(mock_storage_client: MagicMock) -> None:
    """Test upload_file returns confirmation string."""
    mock_info = MagicMock()
    mock_info.object_name = "uploaded.txt"
    mock_info.size_bytes = 512
    mock_storage_client.upload_file.return_value = mock_info

    result = dispatch_tool_call(
        "upload_file",
        {"container": "test-bucket", "local_path": "/tmp/file.txt", "remote_path": "uploaded.txt"},
        mock_storage_client,
    )

    mock_storage_client.upload_file.assert_called_once()
    assert "Uploaded" in result
    assert "uploaded.txt" in result


@pytest.mark.unit
def test_upload_file_local_access_error_returns_error_string(mock_storage_client: MagicMock) -> None:
    """Test upload_file returns error string on local file access error."""
    mock_storage_client.upload_file.side_effect = LocalFileAccessError("file not found")

    result = dispatch_tool_call(
        "upload_file",
        {"container": "test-bucket", "local_path": "/tmp/missing.txt", "remote_path": "file.txt"},
        mock_storage_client,
    )

    assert isinstance(result, str)
    assert "Error" in result


@pytest.mark.unit
def test_download_file_returns_confirmation(mock_storage_client: MagicMock) -> None:
    """Test download_file returns confirmation string."""
    result = dispatch_tool_call(
        "download_file",
        {"container": "test-bucket", "object_name": "file.txt", "file_name": "/tmp/local.txt"},
        mock_storage_client,
    )

    mock_storage_client.download_file.assert_called_once()
    assert "Downloaded" in result


@pytest.mark.unit
def test_download_file_not_found_returns_error_string(mock_storage_client: MagicMock) -> None:
    """Test download_file returns error string when not found."""
    mock_storage_client.download_file.side_effect = ObjectNotFoundError("not found")

    result = dispatch_tool_call(
        "download_file",
        {"container": "test-bucket", "object_name": "missing.txt", "file_name": "/tmp/local.txt"},
        mock_storage_client,
    )

    assert isinstance(result, str)
    assert "Error" in result


@pytest.mark.unit
def test_summarize_file_text_returns_content(mock_storage_client: MagicMock, tmp_path: Path) -> None:
    """Test summarize_file with text file returns content."""

    def _download_mock(container: str, obj_name: str, file_name: str) -> None:
        Path(file_name).write_text("Q1 revenue was $1M")

    mock_storage_client.download_file.side_effect = _download_mock

    result = dispatch_tool_call(
        "summarize_file",
        {"container": "test-bucket", "object_name": "report.txt"},
        mock_storage_client,
    )

    assert "Q1 revenue" in result
    assert isinstance(result, str)


@pytest.mark.unit
def test_summarize_file_truncates_large_content(mock_storage_client: MagicMock) -> None:
    """Test summarize_file returns full raw content for large files without truncation."""

    def _download_mock(container: str, obj_name: str, file_name: str) -> None:
        large_content = "x" * 10000
        Path(file_name).write_text(large_content)

    mock_storage_client.download_file.side_effect = _download_mock

    result = dispatch_tool_call(
        "summarize_file",
        {"container": "test-bucket", "object_name": "large.txt"},
        mock_storage_client,
    )

    assert result == "x" * 10000


@pytest.mark.unit
def test_summarize_file_unsupported_type_returns_message(mock_storage_client: MagicMock) -> None:
    """Test summarize_file returns unsupported message for unknown types."""
    result = dispatch_tool_call(
        "summarize_file",
        {"container": "test-bucket", "object_name": "archive.zip"},
        mock_storage_client,
    )

    assert "not supported" in result
    mock_storage_client.download_file.assert_not_called()


@pytest.mark.unit
def test_summarize_file_not_found_returns_error_string(mock_storage_client: MagicMock) -> None:
    """Test summarize_file returns error string when not found."""
    mock_storage_client.download_file.side_effect = ObjectNotFoundError("not found")

    result = dispatch_tool_call(
        "summarize_file",
        {"container": "test-bucket", "object_name": "missing.txt"},
        mock_storage_client,
    )

    assert isinstance(result, str)
    assert "Error" in result


@pytest.mark.unit
def test_summarize_file_cleans_up_temp_file(mock_storage_client: MagicMock) -> None:
    """Test summarize_file cleans up temp file even on exception."""
    captured_path: list[str] = []

    def _download_error(container: str, obj_name: str, file_name: str) -> None:
        captured_path.append(file_name)
        Path(file_name).write_text("test")
        error_msg = "error"
        raise ObjectNotFoundError(error_msg)

    mock_storage_client.download_file.side_effect = _download_error

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
def test_dispatch_tool_call_routes_correctly(mock_storage_client: MagicMock) -> None:
    """Test dispatch_tool_call routes to correct function."""
    dispatch_tool_call("list_files", {"container": "test-bucket"}, mock_storage_client)
    mock_storage_client.list_files.assert_called_once()

    mock_storage_client.reset_mock()

    dispatch_tool_call("delete_file", {"container": "test-bucket", "object_name": "file.txt"}, mock_storage_client)
    mock_storage_client.delete_file.assert_called_once()


@pytest.mark.unit
def test_dispatch_tool_call_unknown_tool_returns_error_string(mock_storage_client: MagicMock) -> None:
    """Test dispatch_tool_call returns error for unknown tool."""
    result = dispatch_tool_call("unknown_tool", {}, mock_storage_client)

    assert "Error" in result
    assert "Unknown tool" in result


@pytest.mark.unit
def test_summarize_file_pdf_returns_base64_prefix(mock_storage_client: MagicMock) -> None:
    """Test summarize_file with PDF returns base64-encoded content with prefix."""

    def _download_mock(container: str, obj_name: str, file_name: str) -> None:
        Path(file_name).write_bytes(b"%PDF-1.4")

    mock_storage_client.download_file.side_effect = _download_mock

    result = dispatch_tool_call(
        "summarize_file",
        {"container": "test-bucket", "object_name": "document.pdf"},
        mock_storage_client,
    )

    assert result.startswith("PDF_CONTENT_BASE64:")
    encoded = result[len("PDF_CONTENT_BASE64:") :]
    decoded = base64.b64decode(encoded)
    assert decoded == b"%PDF-1.4"
