"""Unit tests for GCPCloudStorageClient CRUD operations.

Every test injects a mock GCS storage client so no real network calls are made.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from gcp_client_impl.client import GCPCloudStorageClient


def _make_blob(  # noqa: PLR0913
    *,
    name: str = "folder/file.txt",
    size: int = 42,
    etag: str = "etag-abc",
    updated: datetime | None = None,
    content_type: str = "text/plain",
    metadata: dict[str, str] | None = None,
) -> MagicMock:
    blob = MagicMock()
    blob.name = name
    blob.size = size
    blob.etag = etag
    blob.updated = updated or datetime(2024, 6, 1, tzinfo=UTC)
    blob.content_type = content_type
    blob.metadata = metadata if metadata is not None else {}
    return blob


def _make_bucket(blob: MagicMock | None = None) -> MagicMock:
    bucket = MagicMock()
    bucket.blob.return_value = blob or _make_blob()
    return bucket


def _make_storage_client(bucket: MagicMock | None = None) -> MagicMock:
    storage_client = MagicMock()
    storage_client.bucket.return_value = bucket or _make_bucket()
    return storage_client


@pytest.fixture
def gcp_client() -> GCPCloudStorageClient:
    return GCPCloudStorageClient(bucket_name="test-bucket")


@pytest.mark.unit
class TestUploadBytes:
    """Tests for upload_bytes."""

    def test_uploads_data_and_returns_object_info(self, gcp_client: GCPCloudStorageClient) -> None:
        blob = _make_blob(name="dir/hello.txt", size=5, etag="xyz")
        gcp_client._storage_client = _make_storage_client(_make_bucket(blob))

        result = gcp_client.upload_bytes(data=b"hello", key="dir/hello.txt")

        blob.upload_from_string.assert_called_once()
        blob.reload.assert_called_once()
        assert result.key == "dir/hello.txt"
        assert result.size_bytes == 5

    def test_sets_content_type_and_metadata(self, gcp_client: GCPCloudStorageClient) -> None:
        blob = _make_blob()
        gcp_client._storage_client = _make_storage_client(_make_bucket(blob))

        gcp_client.upload_bytes(data=b"x", key="k", content_type="image/png", metadata={"author": "alice"})

        assert blob.content_type == "image/png"
        assert blob.metadata == {"author": "alice"}


@pytest.mark.unit
class TestUploadFile:
    """Tests for upload_file."""

    def test_reads_file_and_uploads(self, gcp_client: GCPCloudStorageClient) -> None:
        blob = _make_blob(name="photo.jpg")
        gcp_client._storage_client = _make_storage_client(_make_bucket(blob))

        with patch("pathlib.Path.read_bytes", return_value=b"jpeg-bytes"):
            result = gcp_client.upload_file(
                local_path="/tmp/photo.jpg",  # noqa: S108
                key="photo.jpg",
            )

        assert result.key == "photo.jpg"

    def test_raises_when_file_missing(self, gcp_client: GCPCloudStorageClient) -> None:
        gcp_client._storage_client = _make_storage_client()
        with (
            patch("pathlib.Path.read_bytes", side_effect=FileNotFoundError("/nonexistent/file.txt")),
            pytest.raises(FileNotFoundError, match=r"/nonexistent/file\.txt"),
        ):
            gcp_client.upload_file(local_path="/nonexistent/file.txt", key="file.txt")


@pytest.mark.unit
class TestDownloadBytes:
    """Tests for download_bytes."""

    def test_returns_bytes_when_blob_exists(self, gcp_client: GCPCloudStorageClient) -> None:
        blob = _make_blob()
        blob.exists.return_value = True
        blob.download_as_bytes.return_value = b"file content"
        gcp_client._storage_client = _make_storage_client(_make_bucket(blob))

        assert gcp_client.download_bytes(key="folder/file.txt") == b"file content"

    def test_raises_when_blob_missing(self, gcp_client: GCPCloudStorageClient) -> None:
        blob = _make_blob(name="missing.txt")
        blob.exists.return_value = False
        gcp_client._storage_client = _make_storage_client(_make_bucket(blob))

        with pytest.raises(FileNotFoundError, match=r"missing\.txt"):
            gcp_client.download_bytes(key="missing.txt")


@pytest.mark.unit
class TestList:
    """Tests for list."""

    def test_returns_object_info_for_each_blob(self, gcp_client: GCPCloudStorageClient) -> None:
        blobs = [_make_blob(name="imgs/a.png"), _make_blob(name="imgs/b.png")]
        mock_bucket = MagicMock()
        mock_bucket.list_blobs.return_value = blobs
        gcp_client._storage_client = _make_storage_client(mock_bucket)

        results = gcp_client.list(prefix="imgs/")

        assert len(results) == 2
        assert results[0].key == "imgs/a.png"


@pytest.mark.unit
class TestDelete:
    """Tests for delete."""

    def test_deletes_blob_when_it_exists(self, gcp_client: GCPCloudStorageClient) -> None:
        blob = _make_blob()
        blob.exists.return_value = True
        gcp_client._storage_client = _make_storage_client(_make_bucket(blob))

        gcp_client.delete(key="folder/file.txt")

        blob.delete.assert_called_once()

    def test_raises_when_blob_missing(self, gcp_client: GCPCloudStorageClient) -> None:
        blob = _make_blob(name="gone.txt")
        blob.exists.return_value = False
        gcp_client._storage_client = _make_storage_client(_make_bucket(blob))

        with pytest.raises(FileNotFoundError, match=r"gone\.txt"):
            gcp_client.delete(key="gone.txt")


@pytest.mark.unit
class TestHead:
    """Tests for head."""

    def test_returns_object_info_when_blob_exists(self, gcp_client: GCPCloudStorageClient) -> None:
        blob = _make_blob(name="report.pdf", size=1024)
        blob.exists.return_value = True
        gcp_client._storage_client = _make_storage_client(_make_bucket(blob))

        result = gcp_client.head(key="report.pdf")

        assert result is not None
        assert result.key == "report.pdf"
        blob.reload.assert_called_once()

    def test_returns_none_when_blob_missing(self, gcp_client: GCPCloudStorageClient) -> None:
        blob = _make_blob()
        blob.exists.return_value = False
        gcp_client._storage_client = _make_storage_client(_make_bucket(blob))

        assert gcp_client.head(key="no-such-key") is None
