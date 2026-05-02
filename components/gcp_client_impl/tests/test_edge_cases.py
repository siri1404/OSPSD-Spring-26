"""Edge case unit tests for GCPCloudStorageClient using shared API contract."""

from __future__ import annotations

from io import BytesIO
from unittest.mock import MagicMock

import pytest
from cloud_storage_api.exceptions import (
    InvalidContainerError,
    InvalidFileObjectError,
    InvalidObjectNameError,
    ObjectNotFoundError,
)
from google.api_core import exceptions as google_exceptions

from gcp_client_impl.client import GCPCloudStorageClient

TEST_CONTAINER = "test-bucket"


# ============================================================================
# Fixtures and helpers
# ============================================================================


@pytest.fixture
def client_with_clean_env(
    monkeypatch: pytest.MonkeyPatch,
) -> GCPCloudStorageClient:
    """Construct a GCP client with all credential env vars cleared.

    Tests inject a mocked storage client via client._storage_client = ... after
    construction, so credential resolution never runs.
    """
    for var in (
        "GOOGLE_CLOUD_PROJECT",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "GCP_SERVICE_KEY",
        "GCP_OAUTH_TOKEN",
    ):
        monkeypatch.delenv(var, raising=False)
    return GCPCloudStorageClient()


def _mk_blob(
    name: str,
    *,
    size: int = 0,
    metadata: dict[str, str] | None = None,
) -> MagicMock:
    """Build a mock GCS Blob with deterministic defaults."""
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


def _mk_storage_with_blob(blob: MagicMock) -> tuple[MagicMock, MagicMock]:
    """Build a (storage_client, bucket) pair where bucket.blob() -> blob."""
    bucket = MagicMock()
    bucket.blob.return_value = blob
    storage_client = MagicMock()
    storage_client.bucket.return_value = bucket
    return storage_client, bucket


def _mk_storage_with_blobs(blobs: list[MagicMock]) -> tuple[MagicMock, MagicMock]:
    """Build a (storage_client, bucket) pair where list_blobs() -> blobs."""
    bucket = MagicMock()
    bucket.list_blobs.return_value = blobs
    storage_client = MagicMock()
    storage_client.bucket.return_value = bucket
    return storage_client, bucket


# ============================================================================
# upload_obj
# ============================================================================


@pytest.mark.unit
def test_upload_obj_with_empty_bytes_succeeds(
    client_with_clean_env: GCPCloudStorageClient,
) -> None:
    """upload_obj accepts empty bytes and returns matching ObjectInfo."""
    blob = _mk_blob("empty.txt", size=0)
    storage_client, bucket = _mk_storage_with_blob(blob)
    client_with_clean_env._storage_client = storage_client

    payload = BytesIO(b"")
    result = client_with_clean_env.upload_obj(
        container=TEST_CONTAINER,
        file_obj=payload,
        remote_path="empty.txt",
    )

    bucket.blob.assert_called_once_with("empty.txt")
    blob.upload_from_file.assert_called_once()
    blob.reload.assert_called_once()
    assert result.object_name == "empty.txt"
    assert result.size_bytes == 0


@pytest.mark.unit
def test_upload_obj_with_special_characters_in_key_preserves_path(
    client_with_clean_env: GCPCloudStorageClient,
) -> None:
    """upload_obj preserves special characters in the remote path."""
    remote_path = "folder/file (1) [copy].txt"
    blob = _mk_blob(remote_path, size=42)
    storage_client, bucket = _mk_storage_with_blob(blob)
    client_with_clean_env._storage_client = storage_client

    result = client_with_clean_env.upload_obj(
        container=TEST_CONTAINER,
        file_obj=BytesIO(b"test"),
        remote_path=remote_path,
    )

    bucket.blob.assert_called_once_with(remote_path)
    assert result.object_name == remote_path


@pytest.mark.unit
def test_upload_obj_with_explicit_content_type_forwards_to_sdk(
    client_with_clean_env: GCPCloudStorageClient,
) -> None:
    """upload_obj passes content_type through to blob.upload_from_file."""
    blob = _mk_blob("doc.json", size=10)
    storage_client, _ = _mk_storage_with_blob(blob)
    client_with_clean_env._storage_client = storage_client

    client_with_clean_env.upload_obj(
        container=TEST_CONTAINER,
        file_obj=BytesIO(b'{"k":1}'),
        remote_path="doc.json",
        content_type="application/json",
    )

    _, kwargs = blob.upload_from_file.call_args
    assert kwargs["content_type"] == "application/json"


@pytest.mark.unit
def test_upload_obj_with_non_readable_object_raises(
    client_with_clean_env: GCPCloudStorageClient,
) -> None:
    """upload_obj rejects objects that don't have a callable read()."""
    blob = _mk_blob("x.txt")
    storage_client, _ = _mk_storage_with_blob(blob)
    client_with_clean_env._storage_client = storage_client

    not_a_file = object()  # No read() method.

    with pytest.raises(InvalidFileObjectError, match="read"):
        client_with_clean_env.upload_obj(
            container=TEST_CONTAINER,
            file_obj=not_a_file,  # type: ignore[arg-type]
            remote_path="x.txt",
        )


# ============================================================================
# list_files
# ============================================================================


@pytest.mark.unit
def test_list_files_with_empty_prefix_returns_all(
    client_with_clean_env: GCPCloudStorageClient,
) -> None:
    """list_files with empty prefix forwards prefix='' to the SDK."""
    blob1 = _mk_blob("file1.txt", size=1)
    blob2 = _mk_blob("file2.txt", size=2)
    storage_client, bucket = _mk_storage_with_blobs([blob1, blob2])
    client_with_clean_env._storage_client = storage_client

    results = client_with_clean_env.list_files(container=TEST_CONTAINER, prefix="")

    bucket.list_blobs.assert_called_once_with(prefix="")
    assert [r.object_name for r in results] == ["file1.txt", "file2.txt"]


@pytest.mark.unit
def test_list_files_with_no_results_returns_empty_list(
    client_with_clean_env: GCPCloudStorageClient,
) -> None:
    """list_files returns [] when the bucket is empty (or prefix matches nothing)."""
    storage_client, _ = _mk_storage_with_blobs([])
    client_with_clean_env._storage_client = storage_client

    results = client_with_clean_env.list_files(container=TEST_CONTAINER, prefix="nonexistent/")

    assert results == []


@pytest.mark.unit
def test_list_files_sorts_results_by_object_name(
    client_with_clean_env: GCPCloudStorageClient,
) -> None:
    """list_files returns results sorted ascending by object_name."""
    blobs = [
        _mk_blob("zebra.txt"),
        _mk_blob("alpha.txt"),
        _mk_blob("mango.txt"),
    ]
    storage_client, _ = _mk_storage_with_blobs(blobs)
    client_with_clean_env._storage_client = storage_client

    results = client_with_clean_env.list_files(container=TEST_CONTAINER, prefix="")

    assert [r.object_name for r in results] == [
        "alpha.txt",
        "mango.txt",
        "zebra.txt",
    ]


# ============================================================================
# get_file_info
# ============================================================================


@pytest.mark.unit
def test_get_file_info_with_special_characters_in_key_succeeds(
    client_with_clean_env: GCPCloudStorageClient,
) -> None:
    """get_file_info accepts and preserves special characters in the key."""
    object_name = "folder/file (1) [copy].txt"
    blob = _mk_blob(object_name, size=100)
    storage_client, bucket = _mk_storage_with_blob(blob)
    client_with_clean_env._storage_client = storage_client

    result = client_with_clean_env.get_file_info(container=TEST_CONTAINER, object_name=object_name)

    bucket.blob.assert_called_once_with(object_name)
    blob.reload.assert_called_once()
    assert result.object_name == object_name
    assert result.integrity == "etag-1"


@pytest.mark.unit
def test_get_file_info_missing_raises_not_found(
    client_with_clean_env: GCPCloudStorageClient,
) -> None:
    """get_file_info translates SDK NotFound into ObjectNotFoundError."""
    blob = _mk_blob("missing.txt")
    blob.reload.side_effect = google_exceptions.NotFound("not found")  # type: ignore[no-untyped-call]
    storage_client, _ = _mk_storage_with_blob(blob)
    client_with_clean_env._storage_client = storage_client

    with pytest.raises(ObjectNotFoundError, match=r"missing\.txt"):
        client_with_clean_env.get_file_info(container=TEST_CONTAINER, object_name="missing.txt")


@pytest.mark.unit
def test_get_file_info_handles_sparse_metadata(
    client_with_clean_env: GCPCloudStorageClient,
) -> None:
    """get_file_info coerces None metadata into an empty dict."""
    blob = _mk_blob("doc.txt", size=10, metadata=None)
    blob.metadata = None  # Override the helper's default of {}.
    storage_client, _ = _mk_storage_with_blob(blob)
    client_with_clean_env._storage_client = storage_client

    result = client_with_clean_env.get_file_info(container=TEST_CONTAINER, object_name="doc.txt")

    assert result.metadata == {}


# ============================================================================
# delete_file
# ============================================================================


@pytest.mark.unit
def test_delete_file_missing_raises_not_found(
    client_with_clean_env: GCPCloudStorageClient,
) -> None:
    """delete_file translates SDK NotFound into ObjectNotFoundError."""
    blob = _mk_blob("missing.txt")
    blob.reload.side_effect = google_exceptions.NotFound("not found")  # type: ignore[no-untyped-call]
    storage_client, _ = _mk_storage_with_blob(blob)
    client_with_clean_env._storage_client = storage_client

    with pytest.raises(ObjectNotFoundError, match=r"missing\.txt"):
        client_with_clean_env.delete_file(container=TEST_CONTAINER, object_name="missing.txt")

    blob.delete.assert_not_called()


@pytest.mark.unit
def test_delete_file_returns_delete_result_with_generation(
    client_with_clean_env: GCPCloudStorageClient,
) -> None:
    """delete_file returns a DeleteResult populated from blob.generation."""
    blob = _mk_blob("kept.txt", size=10)
    blob.generation = "12345"
    storage_client, _ = _mk_storage_with_blob(blob)
    client_with_clean_env._storage_client = storage_client

    result = client_with_clean_env.delete_file(container=TEST_CONTAINER, object_name="kept.txt")

    blob.delete.assert_called_once()
    assert result["deleted"] is True
    assert result["version_id"] == "12345"
    assert result["request_charged"] is False


# ============================================================================
# Validation paths
# ============================================================================


@pytest.mark.unit
def test_empty_container_on_upload_obj_raises_invalid_container_error(
    client_with_clean_env: GCPCloudStorageClient,
) -> None:
    """upload_obj rejects empty container before touching the SDK."""
    storage_client = MagicMock()
    client_with_clean_env._storage_client = storage_client

    with pytest.raises(InvalidContainerError, match="empty"):
        client_with_clean_env.upload_obj(
            container="",
            file_obj=BytesIO(b"x"),
            remote_path="foo.txt",
        )

    storage_client.bucket.assert_not_called()


@pytest.mark.unit
def test_empty_object_name_on_get_file_info_raises_invalid_object_name_error(
    client_with_clean_env: GCPCloudStorageClient,
) -> None:
    """get_file_info rejects empty object_name before touching the SDK."""
    storage_client = MagicMock()
    client_with_clean_env._storage_client = storage_client

    with pytest.raises(InvalidObjectNameError, match="empty"):
        client_with_clean_env.get_file_info(container=TEST_CONTAINER, object_name="")

    storage_client.bucket.assert_not_called()
