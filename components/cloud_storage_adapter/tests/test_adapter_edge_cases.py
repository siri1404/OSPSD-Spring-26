"""Edge case unit tests for CloudStorageAdapter.

Tests boundary conditions, error handling, and metadata edge cases.
"""

from __future__ import annotations

from datetime import UTC, datetime
from http import HTTPStatus
from io import BytesIO
from unittest.mock import MagicMock

import pytest
from cloud_storage_adapter import CloudStorageAdapter
from cloud_storage_service_api_client.models import ObjectInfoResponse

pytestmark = pytest.mark.unit


def test_to_object_info_with_all_unset_fields() -> None:
    """Test ObjectInfo conversion when all optional fields are UNSET."""
    from cloud_storage_service_api_client.types import UNSET

    response = ObjectInfoResponse(
        object_name="file.txt",
        size_bytes=UNSET,
        integrity=UNSET,
        updated_at=UNSET,
        data_type=UNSET,
        metadata=UNSET,
    )

    result = CloudStorageAdapter._to_object_info(response)

    assert result.object_name == "file.txt"
    assert result.size_bytes is None
    assert result.integrity is None
    assert result.updated_at is None
    assert result.data_type is None
    assert result.metadata is None


def test_to_object_info_with_none_metadata() -> None:
    """Test ObjectInfo conversion when metadata is explicitly None."""
    response = ObjectInfoResponse(
        object_name="file.txt",
        size_bytes=100,
        integrity="abc",
        updated_at=datetime(2026, 3, 23, tzinfo=UTC),
        data_type="text/plain",
        metadata=None,
    )

    result = CloudStorageAdapter._to_object_info(response)

    assert result.metadata is None


def test_to_object_info_with_special_chars_in_metadata() -> None:
    """Test metadata values with special characters."""
    from cloud_storage_service_api_client.models.object_info_response_metadata_type_0 import (
        ObjectInfoResponseMetadataType0,
    )

    response = ObjectInfoResponse(
        object_name="file.txt",
        size_bytes=100,
        metadata=ObjectInfoResponseMetadataType0.from_dict(
            {
                "author": "José García",
                "tags": "a,b,c",
                "path": "folder/subfolder/file.txt",
            }
        ),
    )

    result = CloudStorageAdapter._to_object_info(response)

    assert result.metadata == {
        "author": "José García",
        "tags": "a,b,c",
        "path": "folder/subfolder/file.txt",
    }


def test_to_object_info_with_empty_metadata_dict() -> None:
    """Test metadata conversion with empty metadata."""
    from cloud_storage_service_api_client.models.object_info_response_metadata_type_0 import (
        ObjectInfoResponseMetadataType0,
    )

    response = ObjectInfoResponse(
        object_name="file.txt",
        size_bytes=100,
        metadata=ObjectInfoResponseMetadataType0.from_dict({}),
    )

    result = CloudStorageAdapter._to_object_info(response)

    assert result.metadata == {}


def test_list_with_empty_result(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test listing when no objects match."""
    from cloud_storage_service_api_client.models.list_response import ListResponse

    adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="test-token")

    list_response = ListResponse(objects=[])

    monkeypatch.setattr(
        "cloud_storage_adapter.adapter.list_objects_list_get.sync_detailed",
        lambda **_: MagicMock(
            status_code=HTTPStatus.OK,
            parsed=list_response,
        ),
    )

    result = adapter.list_files(container="container", prefix="nonexistent/")

    assert result == []


def test_delete_succeeds_repeatedly(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test delete is callable repeatedly; assert underlying client called twice."""
    adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="test-token")

    mock_response = MagicMock()
    mock_response.status_code = HTTPStatus.NO_CONTENT

    mock_fn = MagicMock(return_value=mock_response)

    monkeypatch.setattr(
        "cloud_storage_adapter.adapter.delete_object_delete_key_delete.sync_detailed",
        mock_fn,
    )

    adapter.delete_file(container="container", object_name="file.txt")
    adapter.delete_file(container="container", object_name="file.txt")

    assert mock_fn.call_count == 2


def test_upload_bytes_with_empty_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test uploading empty bytes."""
    from cloud_storage_service_api_client.models.object_info_response import ObjectInfoResponse

    adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="test-token")

    obj_response = ObjectInfoResponse(object_name="empty.txt", size_bytes=0)

    monkeypatch.setattr(
        "cloud_storage_adapter.adapter.upload_file_upload_post.sync_detailed",
        lambda **_: MagicMock(
            status_code=HTTPStatus.OK,
            parsed=obj_response,
        ),
    )

    result = adapter.upload_obj(
        container="container",
        file_obj=BytesIO(b""),
        remote_path="empty.txt",
    )

    assert result.object_name == "empty.txt"
    assert result.size_bytes == 0
