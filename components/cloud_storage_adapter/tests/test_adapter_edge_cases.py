"""Edge case unit tests for CloudStorageAdapter.

Tests boundary conditions, error handling, and metadata edge cases.
"""

from __future__ import annotations

from datetime import UTC, datetime, timezone
from http import HTTPStatus
from io import BytesIO
from unittest.mock import MagicMock

import pytest
from cloud_storage_adapter import CloudStorageAdapter
from cloud_storage_service_api_client.models import ObjectInfoResponse


@pytest.mark.unit
class TestAdapterMetadataEdgeCases:
    """Edge case tests for metadata handling in adapter."""

    def test_to_object_info_with_all_unset_fields(self) -> None:
        """Test ObjectInfo conversion when all optional fields are UNSET."""
        from cloud_storage_service_api_client.types import UNSET

        response = ObjectInfoResponse(
            key="file.txt",
            size_bytes=UNSET,
            etag=UNSET,
            updated_at=UNSET,
            content_type=UNSET,
            metadata=UNSET,
        )

        result = CloudStorageAdapter._to_object_info(response)

        assert result.object_name == "file.txt"
        assert result.size_bytes is None
        assert result.integrity is None
        assert result.updated_at is None
        assert result.data_type is None
        assert result.metadata is None

    def test_to_object_info_with_none_metadata(self) -> None:
        """Test ObjectInfo conversion when metadata is explicitly None."""
        response = ObjectInfoResponse(
            key="file.txt",
            size_bytes=100,
            etag="abc",
            updated_at=datetime(2026, 3, 23, tzinfo=UTC),
            content_type="text/plain",
            metadata=None,
        )

        result = CloudStorageAdapter._to_object_info(response)

        assert result.metadata is None

    def test_to_object_info_with_special_chars_in_metadata(self) -> None:
        """Test metadata values with special characters."""
        from cloud_storage_service_api_client.models.object_info_response_metadata_type_0 import (
            ObjectInfoResponseMetadataType0,
        )

        response = ObjectInfoResponse(
            key="file.txt",
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

    def test_to_object_info_with_empty_metadata_dict(self) -> None:
        """Test metadata conversion with empty metadata."""
        from cloud_storage_service_api_client.models.object_info_response_metadata_type_0 import (
            ObjectInfoResponseMetadataType0,
        )

        response = ObjectInfoResponse(
            key="file.txt",
            size_bytes=100,
            metadata=ObjectInfoResponseMetadataType0.from_dict({}),
        )

        result = CloudStorageAdapter._to_object_info(response)

        assert result.metadata == {}


@pytest.mark.unit
class TestAdapterStatusCodeEdgeCases:
    """Edge case tests for various HTTP status codes."""

    def test_list_with_empty_result(self, monkeypatch: pytest.MonkeyPatch) -> None:
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

    def test_delete_idempotent_behavior(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that deleting same key twice works (delete is idempotent)."""
        adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="test-token")

        mock_response = MagicMock()
        mock_response.status_code = HTTPStatus.NO_CONTENT

        monkeypatch.setattr(
            "cloud_storage_adapter.adapter.delete_object_delete_key_delete.sync_detailed",
            lambda **_: mock_response,
        )

        # First delete should succeed
        adapter.delete_file(container="container", object_name="file.txt")

        # Second delete should also succeed (idempotent)
        adapter.delete_file(container="container", object_name="file.txt")

    def test_upload_bytes_with_empty_bytes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test uploading empty bytes."""
        from cloud_storage_service_api_client.models.object_info_response import ObjectInfoResponse

        adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="test-token")

        obj_response = ObjectInfoResponse(key="empty.txt", size_bytes=0)

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
