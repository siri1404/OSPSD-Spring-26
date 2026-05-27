"""Integration tests for CloudStorageAdapter against a live local service.

These tests assume the cloud storage service is running at http://localhost:8000
and make real HTTP calls to the adapter to test end-to-end workflows.

Mark: @pytest.mark.integration
Skip condition: Service not reachable at configured URL
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from collections.abc import Generator
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from cloud_storage_adapter import CloudStorageAdapter
from cloud_storage_api.exceptions import ObjectNotFoundError

SERVICE_URL = os.getenv("CLOUD_STORAGE_SERVICE_URL", "http://localhost:8000")
DEV_TOKEN = os.getenv("DEV_AUTH_TOKEN", "")
TEST_CONTAINER = os.getenv("CLOUD_STORAGE_TEST_CONTAINER", "integration-test-container")


def service_available() -> bool:
    """Check if the local service is reachable and healthy.

    Only catch network-related errors so other problems bubble up.
    """
    try:
        response = httpx.get(f"{SERVICE_URL}/health", timeout=2)
        return response.status_code == 200
    except httpx.RequestError:
        return False


if not DEV_TOKEN:
    pytest.skip("DEV_AUTH_TOKEN not set; skipping integration tests", allow_module_level=True)


pytestmark = pytest.mark.skipif(
    not service_available(),
    reason=f"Local service not running at {SERVICE_URL}",
)


@pytest.fixture
def cleanup_keys() -> Generator[list[str], None, None]:
    """Track uploaded keys and delete them after each test.

    This is best-effort cleanup; failures are ignored so tests don't mask
    primary failures.
    """
    keys: list[str] = []
    yield keys
    adapter = CloudStorageAdapter(base_url=SERVICE_URL, token=DEV_TOKEN)
    for key in keys:
        with contextlib.suppress(Exception):
            adapter.delete_file(container=TEST_CONTAINER, object_name=key)


def _get_adapter() -> CloudStorageAdapter:
    return CloudStorageAdapter(base_url=SERVICE_URL, token=DEV_TOKEN)


@pytest.mark.integration
def test_upload_and_list_objects(cleanup_keys: list[str]) -> None:
    """Test uploading a file and listing objects."""
    adapter = _get_adapter()

    # Upload a test file
    test_key = "integration_test/hello.txt"
    test_data = b"Hello, Integration Test!"

    result = adapter.upload_obj(
        container=TEST_CONTAINER,
        file_obj=BytesIO(test_data),
        remote_path=test_key,
    )

    cleanup_keys.append(test_key)

    # Verify upload returned object info
    assert result.object_name == test_key
    assert result.size_bytes == len(test_data)

    # List objects and verify upload is present
    objects = adapter.list_files(container=TEST_CONTAINER, prefix="integration_test/")
    assert any(obj.object_name == test_key for obj in objects)


@pytest.mark.integration
def test_head_returns_metadata(cleanup_keys: list[str]) -> None:
    """Test head operation returns correct metadata."""
    adapter = _get_adapter()
    test_key = "integration_test/metadata_test.txt"

    # Upload file first
    adapter.upload_obj(
        container=TEST_CONTAINER,
        file_obj=BytesIO(b"metadata content"),
        remote_path=test_key,
    )
    cleanup_keys.append(test_key)

    # Head the object and verify metadata
    obj_info = adapter.get_file_info(container=TEST_CONTAINER, object_name=test_key)

    assert obj_info.object_name == test_key
    assert obj_info.size_bytes == len(b"metadata content")
    # Should have timestamp and etag
    assert obj_info.updated_at is not None
    assert obj_info.integrity is not None


@pytest.mark.integration
def test_download_bytes_returns_content(cleanup_keys: list[str]) -> None:
    """Test downloading file returns correct content."""
    adapter = _get_adapter()
    test_key = "integration_test/download_test.txt"
    test_content = b"Download test content"

    # Upload file
    adapter.upload_obj(
        container=TEST_CONTAINER,
        file_obj=BytesIO(test_content),
        remote_path=test_key,
    )
    cleanup_keys.append(test_key)

    # Download to a temp file and verify content
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
        tmp_path = tmp.name

    try:
        adapter.download_file(
            container=TEST_CONTAINER,
            object_name=test_key,
            file_name=tmp_path,
        )
        downloaded = Path(tmp_path).read_bytes()
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    assert downloaded == test_content


@pytest.mark.integration
def test_delete_removes_object() -> None:
    """Test delete operation removes object from storage."""
    adapter = _get_adapter()
    test_key = "integration_test/delete_test.txt"

    # Upload file
    adapter.upload_obj(
        container=TEST_CONTAINER,
        file_obj=BytesIO(b"to be deleted"),
        remote_path=test_key,
    )

    # Verify it exists (will raise if not)
    adapter.get_file_info(container=TEST_CONTAINER, object_name=test_key)

    # Delete the object
    adapter.delete_file(container=TEST_CONTAINER, object_name=test_key)

    # Verify it's gone
    with pytest.raises(ObjectNotFoundError):
        adapter.get_file_info(container=TEST_CONTAINER, object_name=test_key)


@pytest.mark.integration
def test_upload_returns_normalized_data_type_field(cleanup_keys: list[str]) -> None:
    """Test upload response exposes normalized data_type field."""
    adapter = _get_adapter()
    test_key = "integration_test/custom_type.json"
    test_data = b'{"key": "value"}'

    result = adapter.upload_obj(
        container=TEST_CONTAINER,
        file_obj=BytesIO(test_data),
        remote_path=test_key,
    )
    cleanup_keys.append(test_key)

    assert result.data_type is not None


@pytest.mark.integration
def test_list_with_prefix_filtering(cleanup_keys: list[str]) -> None:
    """Test that list prefix correctly filters results."""
    adapter = _get_adapter()

    # Upload files with different prefixes
    keys = [
        "prefix_a/file1.txt",
        "prefix_a/file2.txt",
        "prefix_b/file3.txt",
    ]
    for i, key in enumerate(keys):
        adapter.upload_obj(container=TEST_CONTAINER, file_obj=BytesIO(f"content{i}".encode()), remote_path=key)
        cleanup_keys.append(key)

    # List with prefix_a - should only get 2 files
    prefix_a_objects = adapter.list_files(container=TEST_CONTAINER, prefix="prefix_a/")
    prefix_a_keys = [obj.object_name for obj in prefix_a_objects]

    assert "prefix_a/file1.txt" in prefix_a_keys
    assert "prefix_a/file2.txt" in prefix_a_keys
    # Should not include prefix_b files
    assert not any(key.startswith("prefix_b/") for key in prefix_a_keys)


@pytest.mark.integration
def test_upload_file_from_path(cleanup_keys: list[str]) -> None:
    """Test uploading file from filesystem path."""
    adapter = _get_adapter()
    test_key = "integration_test/file_from_path.txt"

    # Create a temporary file
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as tmp:
        tmp.write("Content from file path")
        tmp_path = tmp.name

    try:
        # Upload from path
        result = adapter.upload_file(
            container=TEST_CONTAINER,
            local_path=tmp_path,
            remote_path=test_key,
        )
        cleanup_keys.append(test_key)

        assert result.object_name == test_key
        assert result.size_bytes == len("Content from file path")

        # Download and verify
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as dl_tmp:
            dl_path = dl_tmp.name
        try:
            adapter.download_file(
                container=TEST_CONTAINER,
                object_name=test_key,
                file_name=dl_path,
            )
            assert Path(dl_path).read_bytes() == b"Content from file path"
        finally:
            Path(dl_path).unlink(missing_ok=True)
    finally:
        # Cleanup
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.integration
def test_download_to_file_path(cleanup_keys: list[str]) -> None:
    """Test downloading file to filesystem path."""
    adapter = _get_adapter()
    test_key = "integration_test/download_to_file.txt"
    test_content = b"Downloaded file content"

    # Upload file
    adapter.upload_obj(
        container=TEST_CONTAINER,
        file_obj=BytesIO(test_content),
        remote_path=test_key,
    )
    cleanup_keys.append(test_key)

    # Download to temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
        tmp_path = tmp.name

    try:
        info = adapter.download_file(
            container=TEST_CONTAINER,
            object_name=test_key,
            file_name=tmp_path,
        )

        # Verify file was written correctly
        assert Path(tmp_path).read_bytes() == test_content
        assert info.object_name == test_key
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.integration
def test_upload_empty_file(cleanup_keys: list[str]) -> None:
    """Test uploading an empty file."""
    adapter = _get_adapter()
    test_key = "integration_test/empty.txt"

    result = adapter.upload_obj(
        container=TEST_CONTAINER,
        file_obj=BytesIO(b""),
        remote_path=test_key,
    )
    cleanup_keys.append(test_key)

    assert result.size_bytes == 0

    # Verify we can download it
    with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as tmp:
        tmp_path = tmp.name
    try:
        adapter.download_file(
            container=TEST_CONTAINER,
            object_name=test_key,
            file_name=tmp_path,
        )
        assert Path(tmp_path).read_bytes() == b""
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.integration
def test_upload_large_file(cleanup_keys: list[str]) -> None:
    """Test uploading a larger file (tests streaming/chunking if applicable)."""
    adapter = _get_adapter()
    test_key = "integration_test/large_file.bin"

    # Create 5MB of test data
    large_data = b"x" * (5 * 1024 * 1024)

    result = adapter.upload_obj(
        container=TEST_CONTAINER,
        file_obj=BytesIO(large_data),
        remote_path=test_key,
    )
    cleanup_keys.append(test_key)

    assert result.size_bytes == len(large_data)

    # Download and verify size
    with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as tmp:
        tmp_path = tmp.name
    try:
        adapter.download_file(
            container=TEST_CONTAINER,
            object_name=test_key,
            file_name=tmp_path,
        )
        assert len(Path(tmp_path).read_bytes()) == len(large_data)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.integration
def test_upload_with_special_characters_in_key(cleanup_keys: list[str]) -> None:
    """Test uploading with special characters in key."""
    adapter = _get_adapter()
    test_key = "integration_test/file with spaces (v1) [beta].txt"

    result = adapter.upload_obj(
        container=TEST_CONTAINER,
        file_obj=BytesIO(b"content"),
        remote_path=test_key,
    )
    cleanup_keys.append(test_key)

    assert result.object_name == test_key

    # Verify we can download it
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
        tmp_path = tmp.name
    try:
        adapter.download_file(
            container=TEST_CONTAINER,
            object_name=test_key,
            file_name=tmp_path,
        )
        assert Path(tmp_path).read_bytes() == b"content"
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.integration
def test_concurrent_uploads(cleanup_keys: list[str]) -> None:
    """Test multiple concurrent operations (sequential simulation)."""
    adapter = _get_adapter()

    keys = [
        "integration_test/concurrent_1.txt",
        "integration_test/concurrent_2.txt",
        "integration_test/concurrent_3.txt",
    ]

    # Upload multiple files
    for i, key in enumerate(keys):
        adapter.upload_obj(
            container=TEST_CONTAINER,
            file_obj=BytesIO(f"content_{i}".encode()),
            remote_path=key,
        )
        cleanup_keys.append(key)

    # List and verify all are present
    objects = adapter.list_files(container=TEST_CONTAINER, prefix="integration_test/concurrent_")
    uploaded_keys = [obj.object_name for obj in objects]

    for key in keys:
        assert key in uploaded_keys


@pytest.mark.integration
def test_workflow_upload_head_download_delete(cleanup_keys: list[str]) -> None:
    """Test complete workflow: upload -> head -> download -> delete."""
    adapter = _get_adapter()
    test_key = "integration_test/workflow_test.txt"
    test_content = b"Complete workflow test"

    # 1. Upload
    adapter.upload_obj(
        container=TEST_CONTAINER,
        file_obj=BytesIO(test_content),
        remote_path=test_key,
    )
    cleanup_keys.append(test_key)

    # 2. Head
    head_result = adapter.get_file_info(container=TEST_CONTAINER, object_name=test_key)
    assert head_result.object_name == test_key

    # 3. Download
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
        tmp_path = tmp.name
    try:
        adapter.download_file(
            container=TEST_CONTAINER,
            object_name=test_key,
            file_name=tmp_path,
        )
        assert Path(tmp_path).read_bytes() == test_content
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    # 4. Delete
    adapter.delete_file(container=TEST_CONTAINER, object_name=test_key)

    # 5. Verify deleted
    with pytest.raises(ObjectNotFoundError):
        adapter.get_file_info(container=TEST_CONTAINER, object_name=test_key)
