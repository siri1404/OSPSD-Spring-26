"""Unit tests for storage operation endpoints."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from cloud_storage_api.exceptions import ObjectNotFoundError

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_upload_file_success(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
    sample_file_data: bytes,
) -> None:
    """Successful upload returns ObjectInfoResponse with shared-contract fields."""
    files = {"file": ("test.txt", io.BytesIO(sample_file_data), "text/plain")}
    data = {"key": "uploads/test.txt", "content_type": "text/plain"}

    response = client.post(
        "/upload",
        headers=auth_headers,
        files=files,
        data=data,
    )

    assert response.status_code == 200
    response_data = response.json()
    assert "object_name" in response_data
    assert "size_bytes" in response_data
    assert "integrity" in response_data
    assert "data_type" in response_data
    assert "updated_at" in response_data
    mock_storage_client.upload_obj.assert_called_once()


@pytest.mark.unit
def test_upload_file_without_auth_fails(
    client: TestClient,
    sample_file_data: bytes,
) -> None:
    """Upload without an Authorization header is rejected with 401."""
    files = {"file": ("test.txt", io.BytesIO(sample_file_data), "text/plain")}
    data = {"key": "uploads/test.txt"}

    response = client.post("/upload", files=files, data=data)

    assert response.status_code == 401


@pytest.mark.unit
def test_upload_file_without_key_fails(
    client: TestClient,
    auth_headers: dict[str, str],
    sample_file_data: bytes,
) -> None:
    """Upload without the key form field returns 422 (FastAPI validation)."""
    files = {"file": ("test.txt", io.BytesIO(sample_file_data), "text/plain")}

    response = client.post("/upload", headers=auth_headers, files=files)

    assert response.status_code == 422


@pytest.mark.unit
def test_upload_file_with_custom_content_type(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
) -> None:
    """Upload with an explicit content_type form field is accepted."""
    files = {
        "file": ("test.json", io.BytesIO(b'{"test": "data"}'), "application/json"),
    }
    data = {"key": "data/test.json", "content_type": "application/json"}

    response = client.post(
        "/upload",
        headers=auth_headers,
        files=files,
        data=data,
    )

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_download_file_success(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
) -> None:
    """Successful download returns the file bytes from the storage client."""
    response = client.get(
        "/download/uploads/test.txt",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.content == b"test content"
    mock_storage_client.get_file_info.assert_called_once_with(
        container="test-bucket",
        object_name="uploads/test.txt",
    )
    mock_storage_client.download_file.assert_called_once()


@pytest.mark.unit
def test_download_file_without_auth_fails(client: TestClient) -> None:
    """Download without an Authorization header is rejected with 401."""
    response = client.get("/download/uploads/test.txt")

    assert response.status_code == 401


@pytest.mark.unit
def test_download_nonexistent_file_returns_404(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
) -> None:
    """Download of a non-existent object returns 404."""
    mock_storage_client.get_file_info.side_effect = ObjectNotFoundError(
        "File not found",
    )

    response = client.get(
        "/download/uploads/missing.txt",
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert "detail" in response.json()


@pytest.mark.unit
def test_download_file_with_special_characters_in_key(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
) -> None:
    """Download accepts URL-encoded special characters in the key path."""
    response = client.get(
        "/download/uploads/my%20file.txt",
        headers=auth_headers,
    )

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_list_files_success(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
) -> None:
    """/list returns objects with the shared-contract response shape."""
    response = client.get("/list", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert "objects" in data
    assert isinstance(data["objects"], list)
    mock_storage_client.list_files.assert_called_once_with(
        container="test-bucket",
        prefix="",
    )


@pytest.mark.unit
def test_list_files_with_prefix(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
) -> None:
    """/list forwards the prefix query parameter to the storage client."""
    response = client.get("/list?prefix=uploads/", headers=auth_headers)

    assert response.status_code == 200
    mock_storage_client.list_files.assert_called_once_with(
        container="test-bucket",
        prefix="uploads/",
    )


@pytest.mark.unit
def test_list_files_with_explicit_container(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
) -> None:
    """/list forwards an explicit container query parameter."""
    response = client.get(
        "/list?prefix=uploads/&container=other-bucket",
        headers=auth_headers,
    )

    assert response.status_code == 200
    mock_storage_client.list_files.assert_called_once_with(
        container="other-bucket",
        prefix="uploads/",
    )


@pytest.mark.unit
def test_list_files_without_auth_fails(client: TestClient) -> None:
    """/list without an Authorization header is rejected with 401."""
    response = client.get("/list")

    assert response.status_code == 401


@pytest.mark.unit
def test_list_files_returns_shared_contract_object_fields(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
) -> None:
    """/list response objects expose shared-contract fields (object_name, integrity, data_type)."""
    response = client.get("/list", headers=auth_headers)
    data = response.json()

    assert "objects" in data
    assert len(data["objects"]) > 0
    obj = data["objects"][0]
    assert "object_name" in obj
    assert "size_bytes" in obj
    assert "integrity" in obj
    assert "data_type" in obj


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_delete_file_success(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
) -> None:
    """Successful delete returns 204 and invokes the storage client."""
    response = client.delete(
        "/delete/uploads/test.txt",
        headers=auth_headers,
    )

    assert response.status_code == 204
    mock_storage_client.delete_file.assert_called_once_with(
        container="test-bucket",
        object_name="uploads/test.txt",
    )


@pytest.mark.unit
def test_delete_file_without_auth_fails(client: TestClient) -> None:
    """Delete without an Authorization header is rejected with 401."""
    response = client.delete("/delete/uploads/test.txt")

    assert response.status_code == 401


@pytest.mark.unit
def test_delete_nonexistent_file_returns_404(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
) -> None:
    """Delete of a non-existent object returns 404."""
    mock_storage_client.delete_file.side_effect = ObjectNotFoundError(
        "File not found",
    )

    response = client.delete(
        "/delete/uploads/missing.txt",
        headers=auth_headers,
    )

    assert response.status_code == 404


@pytest.mark.unit
def test_delete_file_returns_no_content(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
) -> None:
    """A successful delete returns 204 with an empty response body."""
    response = client.delete(
        "/delete/uploads/test.txt",
        headers=auth_headers,
    )

    assert response.status_code == 204
    assert response.content == b""


# ---------------------------------------------------------------------------
# Head
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_head_file_success(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
) -> None:
    """/head returns ObjectInfoResponse with shared-contract field names."""
    response = client.get("/head/uploads/test.txt", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert "object_name" in data
    assert "size_bytes" in data
    assert "integrity" in data
    assert "data_type" in data
    assert "updated_at" in data
    mock_storage_client.get_file_info.assert_called_once_with(
        container="test-bucket",
        object_name="uploads/test.txt",
    )


@pytest.mark.unit
def test_head_file_without_auth_fails(client: TestClient) -> None:
    """/head without an Authorization header is rejected with 401."""
    response = client.get("/head/uploads/test.txt")

    assert response.status_code == 401


@pytest.mark.unit
def test_head_nonexistent_file_returns_404(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
) -> None:
    """/head of a non-existent object returns 404."""
    mock_storage_client.get_file_info.side_effect = ObjectNotFoundError(
        "File not found",
    )

    response = client.get(
        "/head/uploads/missing.txt",
        headers=auth_headers,
    )

    assert response.status_code == 404


@pytest.mark.unit
def test_head_file_returns_full_shared_contract_metadata(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
) -> None:
    """/head response exposes all shared-contract metadata fields."""
    response = client.get("/head/uploads/test.txt", headers=auth_headers)
    data = response.json()

    for field in (
        "object_name",
        "size_bytes",
        "integrity",
        "data_type",
        "updated_at",
        "version_id",
        "encryption",
        "storage_tier",
        "metadata",
    ):
        assert field in data


# ---------------------------------------------------------------------------
# Multi-operation workflows
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_upload_then_download_workflow(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
    sample_file_data: bytes,
) -> None:
    """Upload then download against the mocked backend both succeed."""
    files = {"file": ("test.txt", io.BytesIO(sample_file_data), "text/plain")}
    data = {"key": "workflow/test.txt"}

    upload_response = client.post(
        "/upload",
        headers=auth_headers,
        files=files,
        data=data,
    )
    assert upload_response.status_code == 200

    download_response = client.get(
        "/download/workflow/test.txt",
        headers=auth_headers,
    )
    assert download_response.status_code == 200


@pytest.mark.unit
def test_upload_list_delete_workflow(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
    sample_file_data: bytes,
) -> None:
    """Upload → list → delete workflow against the mocked backend."""
    files = {"file": ("test.txt", io.BytesIO(sample_file_data), "text/plain")}
    data = {"key": "workflow/test.txt"}

    upload_response = client.post(
        "/upload",
        headers=auth_headers,
        files=files,
        data=data,
    )
    assert upload_response.status_code == 200

    list_response = client.get("/list?prefix=workflow/", headers=auth_headers)
    assert list_response.status_code == 200

    delete_response = client.delete(
        "/delete/workflow/test.txt",
        headers=auth_headers,
    )
    assert delete_response.status_code == 204


@pytest.mark.unit
def test_head_before_download(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
) -> None:
    """Head returns metadata that callers can inspect before downloading."""
    head_response = client.get(
        "/head/uploads/test.txt",
        headers=auth_headers,
    )
    assert head_response.status_code == 200
    metadata = head_response.json()
    assert metadata["size_bytes"] > 0

    download_response = client.get(
        "/download/uploads/test.txt",
        headers=auth_headers,
    )
    assert download_response.status_code == 200


@pytest.mark.unit
def test_upload_notification_failure_does_not_fail_request(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
    sample_file_data: bytes,
) -> None:
    """A chat-notifier failure during upload does not fail the upload itself."""
    from cloud_storage_service import main

    mock_notifier = MagicMock()
    mock_notifier.notify.side_effect = RuntimeError("chat down")
    main.app.dependency_overrides[main.get_chat_notification] = lambda: mock_notifier
    try:
        files = {"file": ("test.txt", io.BytesIO(sample_file_data), "text/plain")}
        data = {"key": "test.txt"}
        response = client.post(
            "/upload",
            headers=auth_headers,
            files=files,
            data=data,
        )
        assert response.status_code == 200
    finally:
        del main.app.dependency_overrides[main.get_chat_notification]


@pytest.mark.unit
def test_delete_notification_failure_does_not_fail_request(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
) -> None:
    """A chat-notifier failure during delete does not fail the delete itself."""
    from cloud_storage_service import main

    mock_notifier = MagicMock()
    mock_notifier.notify.side_effect = RuntimeError("chat down")
    main.app.dependency_overrides[main.get_chat_notification] = lambda: mock_notifier
    try:
        response = client.delete("/delete/test.txt", headers=auth_headers)
        assert response.status_code == 204
    finally:
        del main.app.dependency_overrides[main.get_chat_notification]
