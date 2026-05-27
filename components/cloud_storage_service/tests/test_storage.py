"""Unit tests for storage operation endpoints."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from cloud_storage_client_api.exceptions import ObjectNotFoundError

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


# ============================================================================
# Upload Tests
# ============================================================================


@pytest.mark.unit
def test_upload_file_success(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
    sample_file_data: bytes,
) -> None:
    """Test successful file upload."""
    files = {"file": ("test.txt", io.BytesIO(sample_file_data), "text/plain")}
    data = {"key": "uploads/test.txt", "content_type": "text/plain"}

    response = client.post("/upload", headers=auth_headers, files=files, data=data)

    assert response.status_code == 200
    response_data = response.json()

    assert "key" in response_data
    assert "size_bytes" in response_data
    assert "etag" in response_data
    assert "updated_at" in response_data

    # Verify mock was called
    mock_storage_client.upload_bytes.assert_called_once()


@pytest.mark.unit
def test_upload_file_without_auth_fails(
    client: TestClient,
    sample_file_data: bytes,
) -> None:
    """Test that upload without authentication fails."""
    files = {"file": ("test.txt", io.BytesIO(sample_file_data), "text/plain")}
    data = {"key": "uploads/test.txt"}

    response = client.post("/upload", files=files, data=data)

    assert response.status_code == 401  # Missing credentials


@pytest.mark.unit
def test_upload_file_without_key_fails(
    client: TestClient,
    auth_headers: dict[str, str],
    sample_file_data: bytes,
) -> None:
    """Test that upload without key parameter fails."""
    files = {"file": ("test.txt", io.BytesIO(sample_file_data), "text/plain")}

    response = client.post("/upload", headers=auth_headers, files=files)

    assert response.status_code == 422  # Validation error


@pytest.mark.unit
def test_upload_file_with_custom_content_type(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
) -> None:
    """Test upload with custom content type."""
    files = {"file": ("test.json", io.BytesIO(b'{"test": "data"}'), "application/json")}
    data = {"key": "data/test.json", "content_type": "application/json"}

    response = client.post("/upload", headers=auth_headers, files=files, data=data)

    assert response.status_code == 200


# ============================================================================
# Download Tests
# ============================================================================


@pytest.mark.unit
def test_download_file_success(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
) -> None:
    """Test successful file download."""
    response = client.get("/download/uploads/test.txt", headers=auth_headers)

    assert response.status_code == 200
    assert response.content == b"test content"

    # Verify mock was called
    mock_storage_client.download_bytes.assert_called_once_with(key="uploads/test.txt")


@pytest.mark.unit
def test_download_file_without_auth_fails(client: TestClient) -> None:
    """Test that download without authentication fails."""
    response = client.get("/download/uploads/test.txt")

    assert response.status_code == 401


@pytest.mark.unit
def test_download_nonexistent_file_returns_404(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
) -> None:
    """Test download of non-existent file returns 404."""
    # Mock raises domain-level not-found exception
    mock_storage_client.download_bytes.side_effect = ObjectNotFoundError("File not found")

    response = client.get("/download/uploads/missing.txt", headers=auth_headers)

    assert response.status_code == 404
    data = response.json()
    assert "detail" in data


@pytest.mark.unit
def test_download_file_with_special_characters_in_key(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
) -> None:
    """Test download with special characters in key."""
    response = client.get("/download/uploads/my%20file.txt", headers=auth_headers)

    assert response.status_code == 200


# ============================================================================
# List Tests
# ============================================================================


@pytest.mark.unit
def test_list_files_success(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
) -> None:
    """Test successful file listing."""
    response = client.get("/list", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()

    assert "objects" in data
    assert isinstance(data["objects"], list)

    # Verify mock was called
    mock_storage_client.list.assert_called_once_with(prefix="")


@pytest.mark.unit
def test_list_files_with_prefix(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
) -> None:
    """Test file listing with prefix filter."""
    response = client.get("/list?prefix=uploads/", headers=auth_headers)

    assert response.status_code == 200

    # Verify mock was called with correct prefix
    mock_storage_client.list.assert_called_once_with(prefix="uploads/")


@pytest.mark.unit
def test_list_files_without_auth_fails(client: TestClient) -> None:
    """Test that list without authentication fails."""
    response = client.get("/list")

    assert response.status_code == 401


@pytest.mark.unit
def test_list_files_returns_correct_structure(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
) -> None:
    """Test that list returns correctly structured response."""
    response = client.get("/list", headers=auth_headers)
    data = response.json()

    assert "objects" in data
    if len(data["objects"]) > 0:
        obj = data["objects"][0]
        assert "key" in obj
        assert "size_bytes" in obj
        assert "etag" in obj


# ============================================================================
# Delete Tests
# ============================================================================


@pytest.mark.unit
def test_delete_file_success(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
) -> None:
    """Test successful file deletion."""
    response = client.delete("/delete/uploads/test.txt", headers=auth_headers)

    assert response.status_code == 204

    # Verify mock was called
    mock_storage_client.delete.assert_called_once_with(key="uploads/test.txt")


@pytest.mark.unit
def test_delete_file_without_auth_fails(client: TestClient) -> None:
    """Test that delete without authentication fails."""
    response = client.delete("/delete/uploads/test.txt")

    assert response.status_code == 401


@pytest.mark.unit
def test_delete_nonexistent_file_returns_404(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
) -> None:
    """Test delete of non-existent file returns 404."""
    # Mock raises domain-level not-found exception
    mock_storage_client.delete.side_effect = ObjectNotFoundError("File not found")

    response = client.delete("/delete/uploads/missing.txt", headers=auth_headers)

    assert response.status_code == 404


@pytest.mark.unit
def test_delete_file_returns_no_content(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
) -> None:
    """Test that successful delete returns 204 No Content."""
    response = client.delete("/delete/uploads/test.txt", headers=auth_headers)

    # 204 should have no response body
    assert response.status_code == 204
    assert response.content == b""


# ============================================================================
# Head Tests
# ============================================================================


@pytest.mark.unit
def test_head_file_success(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
) -> None:
    """Test successful head operation (get metadata)."""
    response = client.get("/head/uploads/test.txt", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()

    assert "key" in data
    assert "size_bytes" in data
    assert "etag" in data
    assert "updated_at" in data

    # Verify mock was called
    mock_storage_client.head.assert_called_once_with(key="uploads/test.txt")


@pytest.mark.unit
def test_head_file_without_auth_fails(client: TestClient) -> None:
    """Test that head without authentication fails."""
    response = client.get("/head/uploads/test.txt")

    assert response.status_code == 401


@pytest.mark.unit
def test_head_nonexistent_file_returns_404(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
) -> None:
    """Test head of non-existent file returns 404."""
    # Mock returns None for non-existent file
    mock_storage_client.head.return_value = None

    response = client.get("/head/uploads/missing.txt", headers=auth_headers)

    assert response.status_code == 404


@pytest.mark.unit
def test_head_file_returns_correct_metadata(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
) -> None:
    """Test that head returns correct metadata structure."""
    response = client.get("/head/uploads/test.txt", headers=auth_headers)
    data = response.json()

    # Verify all expected fields are present
    assert "key" in data
    assert "size_bytes" in data
    assert "etag" in data
    assert "updated_at" in data
    assert "content_type" in data
    # metadata can be None
    assert "metadata" in data


# ============================================================================
# Integration-style Tests (Multiple Operations)
# ============================================================================


@pytest.mark.unit
def test_upload_then_download_workflow(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
    sample_file_data: bytes,
) -> None:
    """Test upload followed by download workflow."""
    # Upload file
    files = {"file": ("test.txt", io.BytesIO(sample_file_data), "text/plain")}
    data = {"key": "workflow/test.txt"}
    upload_response = client.post("/upload", headers=auth_headers, files=files, data=data)
    assert upload_response.status_code == 200

    # Download file
    download_response = client.get("/download/workflow/test.txt", headers=auth_headers)
    assert download_response.status_code == 200


@pytest.mark.unit
def test_upload_list_delete_workflow(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
    sample_file_data: bytes,
) -> None:
    """Test upload, list, then delete workflow."""
    # Upload file
    files = {"file": ("test.txt", io.BytesIO(sample_file_data), "text/plain")}
    data = {"key": "workflow/test.txt"}
    upload_response = client.post("/upload", headers=auth_headers, files=files, data=data)
    assert upload_response.status_code == 200

    # List files
    list_response = client.get("/list?prefix=workflow/", headers=auth_headers)
    assert list_response.status_code == 200

    # Delete file
    delete_response = client.delete("/delete/workflow/test.txt", headers=auth_headers)
    assert delete_response.status_code == 204


@pytest.mark.unit
def test_head_before_download(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
) -> None:
    """Test checking metadata before download."""
    # Get metadata
    head_response = client.get("/head/uploads/test.txt", headers=auth_headers)
    assert head_response.status_code == 200
    metadata = head_response.json()

    # Verify file exists and has size
    assert metadata["size_bytes"] > 0

    # Download file
    download_response = client.get("/download/uploads/test.txt", headers=auth_headers)
    assert download_response.status_code == 200
