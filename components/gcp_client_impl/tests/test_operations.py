"""Unit tests for GCPCloudStorageClient operations on shared API contract."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from cloud_storage_api.exceptions import (
    AuthenticationError,
    ContainerNotFoundError,
    InvalidFileObjectError,
    LocalFileAccessError,
    ObjectNotFoundError,
    StorageBackendError,
)
from gcp_client_impl.client import GCPCloudStorageClient, _map_provider_error

try:
    from google.api_core import exceptions as google_exceptions
except ImportError:  # pragma: no cover
    google_exceptions = None  # type: ignore[assignment]

TEST_CONTAINER = "test-bucket"


def _make_blob(name: str = "folder/file.txt", size: int = 42) -> MagicMock:
    blob = MagicMock()
    blob.name = name
    blob.size = size
    blob.etag = "etag-abc"
    blob.updated = None
    blob.content_type = "text/plain"
    blob.metadata = {}
    blob.generation = "gen-1"
    blob.kms_key_name = None
    blob.storage_class = "STANDARD"
    return blob


def _make_storage_client(blob: MagicMock | None = None) -> MagicMock:
    bucket = MagicMock()
    bucket.blob.return_value = blob or _make_blob()
    storage_client = MagicMock()
    storage_client.bucket.return_value = bucket
    return storage_client


@pytest.fixture
def gcp_client() -> GCPCloudStorageClient:
    return GCPCloudStorageClient()


@pytest.mark.unit
class TestUploadObj:
    """Upload object behavior."""

    def test_uploads_file_obj_and_returns_object_info(self, gcp_client: GCPCloudStorageClient) -> None:
        blob = _make_blob(name="dir/hello.txt", size=5)
        gcp_client._storage_client = _make_storage_client(blob)

        result = gcp_client.upload_obj(
            container=TEST_CONTAINER,
            file_obj=BytesIO(b"hello"),
            remote_path="dir/hello.txt",
        )

        blob.upload_from_file.assert_called_once()
        blob.reload.assert_called_once()
        assert result.object_name == "dir/hello.txt"
        assert result.size_bytes == 5

    def test_forwards_content_type_from_file_object(self, gcp_client: GCPCloudStorageClient) -> None:
        blob = _make_blob(name="dir/hello.txt", size=5)
        gcp_client._storage_client = _make_storage_client(blob)

        stream = BytesIO(b"hello")
        stream.content_type = "text/plain"  # type: ignore[attr-defined]

        gcp_client.upload_obj(
            container=TEST_CONTAINER,
            file_obj=stream,
            remote_path="dir/hello.txt",
        )

        blob.upload_from_file.assert_called_once_with(stream, content_type="text/plain")

    def test_raises_invalid_file_object_on_upload_type_error(self, gcp_client: GCPCloudStorageClient) -> None:
        blob = _make_blob(name="dir/hello.txt", size=5)
        blob.upload_from_file.side_effect = TypeError("bad file object")
        gcp_client._storage_client = _make_storage_client(blob)

        with pytest.raises(InvalidFileObjectError, match="Failed to upload from file object"):
            gcp_client.upload_obj(
                container=TEST_CONTAINER,
                file_obj=BytesIO(b"hello"),
                remote_path="dir/hello.txt",
            )

    def test_raises_storage_backend_error_on_unknown_upload_failure(self, gcp_client: GCPCloudStorageClient) -> None:
        blob = _make_blob(name="dir/hello.txt", size=5)
        blob.upload_from_file.side_effect = RuntimeError("boom")
        gcp_client._storage_client = _make_storage_client(blob)

        with pytest.raises(StorageBackendError):
            gcp_client.upload_obj(
                container=TEST_CONTAINER,
                file_obj=BytesIO(b"hello"),
                remote_path="dir/hello.txt",
            )

    def test_maps_provider_not_found_to_container_not_found(self, gcp_client: GCPCloudStorageClient) -> None:
        if google_exceptions is None:
            pytest.skip("google.api_core.exceptions unavailable")

        blob = _make_blob(name="dir/hello.txt", size=5)
        blob.upload_from_file.side_effect = google_exceptions.NotFound("missing bucket")  # type: ignore[no-untyped-call]
        gcp_client._storage_client = _make_storage_client(blob)

        with pytest.raises(ContainerNotFoundError):
            gcp_client.upload_obj(
                container=TEST_CONTAINER,
                file_obj=BytesIO(b"hello"),
                remote_path="dir/hello.txt",
            )


@pytest.mark.unit
class TestUploadFile:
    """Upload file behavior."""

    def test_reads_local_file_and_uploads(self, gcp_client: GCPCloudStorageClient) -> None:
        blob = _make_blob(name="photo.jpg")
        gcp_client._storage_client = _make_storage_client(blob)

        with patch("pathlib.Path.read_bytes", return_value=b"jpeg-bytes"):
            result = gcp_client.upload_file(
                container=TEST_CONTAINER,
                local_path="/tmp/photo.jpg",
                remote_path="photo.jpg",
            )

        assert result.object_name == "photo.jpg"

    def test_raises_local_access_error_when_file_missing(self, gcp_client: GCPCloudStorageClient) -> None:
        gcp_client._storage_client = _make_storage_client()
        with (
            patch("pathlib.Path.read_bytes", side_effect=FileNotFoundError("/missing/file.txt")),
            pytest.raises(LocalFileAccessError, match=r"Cannot read local file"),
        ):
            gcp_client.upload_file(
                container=TEST_CONTAINER,
                local_path="/missing/file.txt",
                remote_path="file.txt",
            )

    def test_maps_provider_forbidden_to_authentication_error(self, gcp_client: GCPCloudStorageClient) -> None:
        if google_exceptions is None:
            pytest.skip("google.api_core.exceptions unavailable")

        blob = _make_blob(name="photo.jpg")
        blob.upload_from_string.side_effect = google_exceptions.Forbidden("forbidden")  # type: ignore[no-untyped-call]
        gcp_client._storage_client = _make_storage_client(blob)

        with patch("pathlib.Path.read_bytes", return_value=b"jpeg-bytes"), pytest.raises(AuthenticationError):
            gcp_client.upload_file(
                container=TEST_CONTAINER,
                local_path="/tmp/photo.jpg",
                remote_path="photo.jpg",
            )

    def test_maps_provider_not_found_to_container_not_found(self, gcp_client: GCPCloudStorageClient) -> None:
        if google_exceptions is None:
            pytest.skip("google.api_core.exceptions unavailable")

        blob = _make_blob(name="photo.jpg")
        blob.upload_from_string.side_effect = google_exceptions.NotFound("missing bucket")  # type: ignore[no-untyped-call]
        gcp_client._storage_client = _make_storage_client(blob)

        with patch("pathlib.Path.read_bytes", return_value=b"jpeg-bytes"), pytest.raises(ContainerNotFoundError):
            gcp_client.upload_file(
                container=TEST_CONTAINER,
                local_path="/tmp/photo.jpg",
                remote_path="photo.jpg",
            )


@pytest.mark.unit
class TestDownloadFile:
    """Download file behavior."""

    def test_downloads_to_filename(self, gcp_client: GCPCloudStorageClient, tmp_path: Path) -> None:
        blob = _make_blob(name="folder/file.txt")
        blob.exists.return_value = True
        gcp_client._storage_client = _make_storage_client(blob)

        out_path = tmp_path / "out.txt"
        result = gcp_client.download_file(
            container=TEST_CONTAINER,
            object_name="folder/file.txt",
            file_name=str(out_path),
        )

        blob.download_to_filename.assert_called_once_with(str(out_path))
        assert result.object_name == "folder/file.txt"

    def test_raises_not_found_for_missing_blob(self, gcp_client: GCPCloudStorageClient, tmp_path: Path) -> None:
        blob = _make_blob(name="missing.txt")
        blob.exists.return_value = False
        gcp_client._storage_client = _make_storage_client(blob)

        with pytest.raises(ObjectNotFoundError, match=r"missing\.txt"):
            gcp_client.download_file(
                container=TEST_CONTAINER,
                object_name="missing.txt",
                file_name=str(tmp_path / "out.txt"),
            )

    def test_maps_exists_failure_to_storage_backend_error(self, gcp_client: GCPCloudStorageClient, tmp_path: Path) -> None:
        blob = _make_blob(name="folder/file.txt")
        blob.exists.side_effect = RuntimeError("exists failed")
        gcp_client._storage_client = _make_storage_client(blob)

        with pytest.raises(StorageBackendError):
            gcp_client.download_file(
                container=TEST_CONTAINER,
                object_name="folder/file.txt",
                file_name=str(tmp_path / "out.txt"),
            )

    def test_maps_download_failure_to_storage_backend_error(self, gcp_client: GCPCloudStorageClient, tmp_path: Path) -> None:
        blob = _make_blob(name="folder/file.txt")
        blob.exists.return_value = True
        blob.download_to_filename.side_effect = RuntimeError("download failed")
        gcp_client._storage_client = _make_storage_client(blob)

        with pytest.raises(StorageBackendError):
            gcp_client.download_file(
                container=TEST_CONTAINER,
                object_name="folder/file.txt",
                file_name=str(tmp_path / "out.txt"),
            )

    def test_maps_reload_failure_to_storage_backend_error(self, gcp_client: GCPCloudStorageClient, tmp_path: Path) -> None:
        blob = _make_blob(name="folder/file.txt")
        blob.exists.return_value = True
        blob.reload.side_effect = RuntimeError("reload failed")
        gcp_client._storage_client = _make_storage_client(blob)

        with pytest.raises(StorageBackendError):
            gcp_client.download_file(
                container=TEST_CONTAINER,
                object_name="folder/file.txt",
                file_name=str(tmp_path / "out.txt"),
            )

    def test_maps_provider_not_found_to_container_not_found(self, gcp_client: GCPCloudStorageClient, tmp_path: Path) -> None:
        if google_exceptions is None:
            pytest.skip("google.api_core.exceptions unavailable")

        blob = _make_blob(name="folder/file.txt")
        blob.exists.side_effect = google_exceptions.NotFound("missing bucket")  # type: ignore[no-untyped-call]
        gcp_client._storage_client = _make_storage_client(blob)

        with pytest.raises(ContainerNotFoundError):
            gcp_client.download_file(
                container=TEST_CONTAINER,
                object_name="folder/file.txt",
                file_name=str(tmp_path / "out.txt"),
            )


@pytest.mark.unit
class TestListFiles:
    """List file behavior."""

    def test_returns_object_info_for_each_blob(self, gcp_client: GCPCloudStorageClient) -> None:
        blob_a = _make_blob(name="imgs/a.png")
        blob_b = _make_blob(name="imgs/b.png")
        bucket = MagicMock()
        bucket.list_blobs.return_value = [blob_a, blob_b]
        storage_client = MagicMock()
        storage_client.bucket.return_value = bucket
        gcp_client._storage_client = storage_client

        results = gcp_client.list_files(container=TEST_CONTAINER, prefix="imgs/")

        assert len(results) == 2
        assert results[0].object_name == "imgs/a.png"

    def test_maps_provider_not_found_to_container_not_found(self, gcp_client: GCPCloudStorageClient) -> None:
        if google_exceptions is None:
            pytest.skip("google.api_core.exceptions unavailable")

        bucket = MagicMock()
        bucket.list_blobs.side_effect = google_exceptions.NotFound("missing bucket")  # type: ignore[no-untyped-call]
        storage_client = MagicMock()
        storage_client.bucket.return_value = bucket
        gcp_client._storage_client = storage_client

        with pytest.raises(ContainerNotFoundError):
            gcp_client.list_files(container=TEST_CONTAINER, prefix="")


@pytest.mark.unit
class TestDeleteFile:
    """Delete file behavior."""

    def test_deletes_blob_when_exists(self, gcp_client: GCPCloudStorageClient) -> None:
        blob = _make_blob()
        blob.exists.return_value = True
        gcp_client._storage_client = _make_storage_client(blob)

        result = gcp_client.delete_file(container=TEST_CONTAINER, object_name="folder/file.txt")

        blob.delete.assert_called_once()
        assert result["deleted"] is True

    def test_raises_when_blob_missing(self, gcp_client: GCPCloudStorageClient) -> None:
        blob = _make_blob(name="gone.txt")
        blob.exists.return_value = False
        gcp_client._storage_client = _make_storage_client(blob)

        with pytest.raises(ObjectNotFoundError, match=r"gone\.txt"):
            gcp_client.delete_file(container=TEST_CONTAINER, object_name="gone.txt")

    def test_maps_exists_failure_to_storage_backend_error(self, gcp_client: GCPCloudStorageClient) -> None:
        blob = _make_blob(name="gone.txt")
        blob.exists.side_effect = RuntimeError("exists failed")
        gcp_client._storage_client = _make_storage_client(blob)

        with pytest.raises(StorageBackendError):
            gcp_client.delete_file(container=TEST_CONTAINER, object_name="gone.txt")

    def test_maps_delete_failure_to_storage_backend_error(self, gcp_client: GCPCloudStorageClient) -> None:
        blob = _make_blob(name="gone.txt")
        blob.exists.return_value = True
        blob.delete.side_effect = RuntimeError("delete failed")
        gcp_client._storage_client = _make_storage_client(blob)

        with pytest.raises(StorageBackendError):
            gcp_client.delete_file(container=TEST_CONTAINER, object_name="gone.txt")

    def test_maps_provider_not_found_to_container_not_found(self, gcp_client: GCPCloudStorageClient) -> None:
        if google_exceptions is None:
            pytest.skip("google.api_core.exceptions unavailable")

        blob = _make_blob(name="gone.txt")
        blob.exists.side_effect = google_exceptions.NotFound("missing bucket")  # type: ignore[no-untyped-call]
        gcp_client._storage_client = _make_storage_client(blob)

        with pytest.raises(ContainerNotFoundError):
            gcp_client.delete_file(container=TEST_CONTAINER, object_name="gone.txt")


@pytest.mark.unit
class TestGetFileInfo:
    """Get file info behavior."""

    def test_returns_object_info_when_blob_exists(self, gcp_client: GCPCloudStorageClient) -> None:
        blob = _make_blob(name="report.pdf", size=1024)
        blob.exists.return_value = True
        gcp_client._storage_client = _make_storage_client(blob)

        result = gcp_client.get_file_info(container=TEST_CONTAINER, object_name="report.pdf")

        assert result.object_name == "report.pdf"
        blob.reload.assert_called_once()

    def test_raises_when_blob_missing(self, gcp_client: GCPCloudStorageClient) -> None:
        blob = _make_blob(name="no-such-key")
        blob.exists.return_value = False
        gcp_client._storage_client = _make_storage_client(blob)

        with pytest.raises(ObjectNotFoundError):
            gcp_client.get_file_info(container=TEST_CONTAINER, object_name="no-such-key")

    def test_maps_exists_failure_to_storage_backend_error(self, gcp_client: GCPCloudStorageClient) -> None:
        blob = _make_blob(name="no-such-key")
        blob.exists.side_effect = RuntimeError("exists failed")
        gcp_client._storage_client = _make_storage_client(blob)

        with pytest.raises(StorageBackendError):
            gcp_client.get_file_info(container=TEST_CONTAINER, object_name="no-such-key")

    def test_maps_reload_failure_to_storage_backend_error(self, gcp_client: GCPCloudStorageClient) -> None:
        blob = _make_blob(name="report.pdf", size=1024)
        blob.exists.return_value = True
        blob.reload.side_effect = RuntimeError("reload failed")
        gcp_client._storage_client = _make_storage_client(blob)

        with pytest.raises(StorageBackendError):
            gcp_client.get_file_info(container=TEST_CONTAINER, object_name="report.pdf")

    def test_maps_provider_not_found_to_container_not_found(self, gcp_client: GCPCloudStorageClient) -> None:
        if google_exceptions is None:
            pytest.skip("google.api_core.exceptions unavailable")

        blob = _make_blob(name="report.pdf", size=1024)
        blob.exists.side_effect = google_exceptions.NotFound("missing bucket")  # type: ignore[no-untyped-call]
        gcp_client._storage_client = _make_storage_client(blob)

        with pytest.raises(ContainerNotFoundError):
            gcp_client.get_file_info(container=TEST_CONTAINER, object_name="report.pdf")


@pytest.mark.unit
def test_map_provider_error_without_google_exceptions_returns_storage_backend_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("gcp_client_impl.client.google_exceptions", None)

    mapped = _map_provider_error(RuntimeError("boom"), container=TEST_CONTAINER)

    assert isinstance(mapped, StorageBackendError)
