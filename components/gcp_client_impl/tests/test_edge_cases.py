"""Edge case unit tests for GCPCloudStorageClient using shared API contract."""

from __future__ import annotations

from io import BytesIO
from unittest.mock import MagicMock

import pytest
from cloud_storage_api.exceptions import ObjectNotFoundError
from gcp_client_impl.client import GCPCloudStorageClient

TEST_CONTAINER = "test-bucket"


def _mk_blob(name: str, *, size: int = 0, metadata: dict[str, str] | None = None) -> MagicMock:
    blob = MagicMock()
    blob.name = name
    blob.size = size
    blob.etag = "etag-1"
    blob.content_type = "text/plain"
    blob.updated = None
    blob.generation = "g1"
    blob.kms_key_name = None
    blob.storage_class = "STANDARD"
    blob.metadata = metadata if metadata is not None else {}
    return blob


@pytest.mark.unit
class TestUploadObjEdgeCases:
    """Edge case tests for upload_obj."""

    def test_upload_empty_bytes(self) -> None:
        blob = _mk_blob("empty.txt", size=0)
        bucket = MagicMock()
        bucket.blob.return_value = blob
        storage_client = MagicMock()
        storage_client.bucket.return_value = bucket

        client = GCPCloudStorageClient()
        client._storage_client = storage_client

        result = client.upload_obj(
            container=TEST_CONTAINER,
            file_obj=BytesIO(b""),
            remote_path="empty.txt",
        )

        assert result.object_name == "empty.txt"
        assert result.size_bytes == 0

    def test_upload_with_special_characters_in_key(self) -> None:
        remote_path = "folder/file (1) [copy].txt"
        blob = _mk_blob(remote_path, size=42)
        bucket = MagicMock()
        bucket.blob.return_value = blob
        storage_client = MagicMock()
        storage_client.bucket.return_value = bucket

        client = GCPCloudStorageClient()
        client._storage_client = storage_client

        result = client.upload_obj(
            container=TEST_CONTAINER,
            file_obj=BytesIO(b"test"),
            remote_path=remote_path,
        )

        assert result.object_name == remote_path


@pytest.mark.unit
class TestListFilesEdgeCases:
    """Edge case tests for list_files."""

    def test_list_with_empty_prefix(self) -> None:
        blob1 = _mk_blob("file1.txt", size=1)
        blob2 = _mk_blob("file2.txt", size=2)
        bucket = MagicMock()
        bucket.list_blobs.return_value = [blob1, blob2]
        storage_client = MagicMock()
        storage_client.bucket.return_value = bucket

        client = GCPCloudStorageClient()
        client._storage_client = storage_client

        results = client.list_files(container=TEST_CONTAINER, prefix="")

        bucket.list_blobs.assert_called_once_with(prefix="")
        assert len(results) == 2
        assert results[0].object_name == "file1.txt"

    def test_list_with_no_results(self) -> None:
        bucket = MagicMock()
        bucket.list_blobs.return_value = []
        storage_client = MagicMock()
        storage_client.bucket.return_value = bucket

        client = GCPCloudStorageClient()
        client._storage_client = storage_client

        results = client.list_files(container=TEST_CONTAINER, prefix="nonexistent/")

        assert results == []


@pytest.mark.unit
class TestGetFileInfoEdgeCases:
    """Edge case tests for get_file_info."""

    def test_get_file_info_with_special_characters_in_key(self) -> None:
        object_name = "folder/file (1) [copy].txt"
        blob = _mk_blob(object_name, size=100)
        blob.exists.return_value = True

        bucket = MagicMock()
        bucket.blob.return_value = blob
        storage_client = MagicMock()
        storage_client.bucket.return_value = bucket

        client = GCPCloudStorageClient()
        client._storage_client = storage_client

        result = client.get_file_info(container=TEST_CONTAINER, object_name=object_name)

        assert result.object_name == object_name
        assert result.integrity == "etag-1"

    def test_get_file_info_missing_raises_not_found(self) -> None:
        blob = _mk_blob("missing.txt")
        blob.exists.return_value = False

        bucket = MagicMock()
        bucket.blob.return_value = blob
        storage_client = MagicMock()
        storage_client.bucket.return_value = bucket

        client = GCPCloudStorageClient()
        client._storage_client = storage_client

        with pytest.raises(ObjectNotFoundError):
            client.get_file_info(container=TEST_CONTAINER, object_name="missing.txt")
