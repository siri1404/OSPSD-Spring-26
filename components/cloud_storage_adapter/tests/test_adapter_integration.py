"""Integration tests for CloudStorageAdapter against a live local service.

These tests assume the cloud storage service is running at http://localhost:8000
and make real HTTP calls to the adapter to test end-to-end workflows.

Mark: @pytest.mark.integration
Skip condition: Service not reachable at configured URL
"""

from __future__ import annotations

import os
from typing import Any

import httpx
import pytest
from cloud_storage_adapter import CloudStorageAdapter

SERVICE_URL = os.getenv("CLOUD_STORAGE_SERVICE_URL", "http://localhost:8000")
DEV_TOKEN = os.getenv("DEV_AUTH_TOKEN", "")


def service_available() -> bool:
    """Check if the local service is reachable and healthy."""
    try:
        response = httpx.get(f"{SERVICE_URL}/health", timeout=2)
        return response.status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not service_available(),
    reason=f"Local service not running at {SERVICE_URL}",
)


@pytest.mark.integration
class TestAdapterIntegration:
    """Integration tests for CloudStorageAdapter with real service."""

    @staticmethod
    def get_adapter() -> CloudStorageAdapter:
        """Get a real adapter instance pointing to local service."""
        return CloudStorageAdapter(base_url=SERVICE_URL, token=DEV_TOKEN)

    def test_upload_and_list_objects(self) -> None:
        """Test uploading a file and listing objects."""
        adapter = self.get_adapter()

        # Upload a test file
        test_key = "integration_test/hello.txt"
        test_data = b"Hello, Integration Test!"

        result = adapter.upload_bytes(
            data=test_data,
            key=test_key,
            content_type="text/plain",
        )

        # Verify upload returned object info
        assert result is not None
        assert result.key == test_key
        assert result.size_bytes == len(test_data)

        # List objects and verify upload is present
        objects = adapter.list(prefix="integration_test/")
        assert len(objects) > 0
        assert any(obj.key == test_key for obj in objects)

    def test_head_returns_metadata(self) -> None:
        """Test head operation returns correct metadata."""
        adapter = self.get_adapter()
        test_key = "integration_test/metadata_test.txt"

        # Upload file first
        adapter.upload_bytes(data=b"metadata content", key=test_key)

        # Head the object and verify metadata
        obj_info = adapter.head(key=test_key)

        assert obj_info is not None
        assert obj_info.key == test_key
        assert obj_info.size_bytes == len(b"metadata content")
        # Should have timestamp and etag
        assert obj_info.updated_at is not None
        assert obj_info.etag is not None

    def test_download_bytes_returns_content(self) -> None:
        """Test downloading file returns correct content."""
        adapter = self.get_adapter()
        test_key = "integration_test/download_test.txt"
        test_content = b"Download test content"

        # Upload file
        adapter.upload_bytes(data=test_content, key=test_key)

        # Download and verify content
        downloaded = adapter.download_bytes(key=test_key)

        assert downloaded == test_content

    def test_delete_removes_object(self) -> None:
        """Test delete operation removes object from storage."""
        adapter = self.get_adapter()
        test_key = "integration_test/delete_test.txt"

        # Upload file
        adapter.upload_bytes(data=b"to be deleted", key=test_key)

        # Verify it exists
        obj_info = adapter.head(key=test_key)
        assert obj_info is not None

        # Delete the object
        adapter.delete(key=test_key)

        # Verify it's gone
        result_after_delete = adapter.head(key=test_key)
        assert result_after_delete is None

    def test_upload_with_custom_content_type(self) -> None:
        """Test uploading with custom content type."""
        adapter = self.get_adapter()
        test_key = "integration_test/custom_type.json"
        test_data = b'{"key": "value"}'

        result = adapter.upload_bytes(
            data=test_data,
            key=test_key,
            content_type="application/json",
        )

        assert result is not None
        assert result.content_type == "application/json"

    def test_list_with_prefix_filtering(self) -> None:
        """Test that list prefix correctly filters results."""
        adapter = self.get_adapter()

        # Upload files with different prefixes
        adapter.upload_bytes(data=b"content1", key="prefix_a/file1.txt")
        adapter.upload_bytes(data=b"content2", key="prefix_a/file2.txt")
        adapter.upload_bytes(data=b"content3", key="prefix_b/file3.txt")

        # List with prefix_a - should only get 2 files
        prefix_a_objects = adapter.list(prefix="prefix_a/")
        prefix_a_keys = [obj.key for obj in prefix_a_objects]

        assert "prefix_a/file1.txt" in prefix_a_keys
        assert "prefix_a/file2.txt" in prefix_a_keys
        # Should not include prefix_b files
        assert not any(key.startswith("prefix_b/") for key in prefix_a_keys)

    def test_upload_file_from_path(self) -> None:
        """Test uploading file from filesystem path."""
        import tempfile
        from pathlib import Path

        adapter = self.get_adapter()
        test_key = "integration_test/file_from_path.txt"

        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as tmp:
            tmp.write("Content from file path")
            tmp_path = tmp.name

        try:
            # Upload from path
            result = adapter.upload_file(local_path=tmp_path, key=test_key)

            assert result is not None
            assert result.key == test_key
            assert result.size_bytes == len("Content from file path")

            # Download and verify
            downloaded = adapter.download_bytes(key=test_key)
            assert downloaded == b"Content from file path"
        finally:
            # Cleanup
            Path(tmp_path).unlink()

    def test_download_to_file_path(self) -> None:
        """Test downloading file to filesystem path."""
        import tempfile
        from pathlib import Path

        adapter = self.get_adapter()
        test_key = "integration_test/download_to_file.txt"
        test_content = b"Downloaded file content"

        # Upload file
        adapter.upload_bytes(data=test_content, key=test_key)

        # Download to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
            tmp_path = tmp.name

        try:
            # Note: This test assumes download_to_file exists or we use download_bytes + write
            downloaded = adapter.download_bytes(key=test_key)
            Path(tmp_path).write_bytes(downloaded)

            # Verify file was written correctly
            assert Path(tmp_path).read_bytes() == test_content
        finally:
            Path(tmp_path).unlink()

    def test_upload_empty_file(self) -> None:
        """Test uploading an empty file."""
        adapter = self.get_adapter()
        test_key = "integration_test/empty.txt"

        result = adapter.upload_bytes(data=b"", key=test_key)

        assert result is not None
        assert result.size_bytes == 0

        # Verify we can download it
        downloaded = adapter.download_bytes(key=test_key)
        assert downloaded == b""

    def test_upload_large_file(self) -> None:
        """Test uploading a larger file (tests streaming/chunking if applicable)."""
        adapter = self.get_adapter()
        test_key = "integration_test/large_file.bin"

        # Create 5MB of test data
        large_data = b"x" * (5 * 1024 * 1024)

        result = adapter.upload_bytes(data=large_data, key=test_key)

        assert result is not None
        assert result.size_bytes == len(large_data)

        # Download and verify size
        downloaded = adapter.download_bytes(key=test_key)
        assert len(downloaded) == len(large_data)

    def test_upload_with_special_characters_in_key(self) -> None:
        """Test uploading with special characters in key."""
        adapter = self.get_adapter()
        test_key = "integration_test/file with spaces (v1) [beta].txt"

        result = adapter.upload_bytes(data=b"content", key=test_key)

        assert result is not None
        assert result.key == test_key

        # Verify we can download it
        downloaded = adapter.download_bytes(key=test_key)
        assert downloaded == b"content"

    def test_concurrent_uploads(self) -> None:
        """Test multiple concurrent operations (sequential simulation)."""
        adapter = self.get_adapter()

        keys = [
            "integration_test/concurrent_1.txt",
            "integration_test/concurrent_2.txt",
            "integration_test/concurrent_3.txt",
        ]

        # Upload multiple files
        for i, key in enumerate(keys):
            adapter.upload_bytes(data=f"content_{i}".encode(), key=key)

        # List and verify all are present
        objects = adapter.list(prefix="integration_test/concurrent_")
        uploaded_keys = [obj.key for obj in objects]

        for key in keys:
            assert key in uploaded_keys

    def test_workflow_upload_head_download_delete(self) -> None:
        """Test complete workflow: upload -> head -> download -> delete."""
        adapter = self.get_adapter()
        test_key = "integration_test/workflow_test.txt"
        test_content = b"Complete workflow test"

        # 1. Upload
        upload_result = adapter.upload_bytes(data=test_content, key=test_key)
        assert upload_result is not None

        # 2. Head
        head_result = adapter.head(key=test_key)
        assert head_result is not None
        assert head_result.key == test_key

        # 3. Download
        downloaded = adapter.download_bytes(key=test_key)
        assert downloaded == test_content

        # 4. Delete
        adapter.delete(key=test_key)

        # 5. Verify deleted
        final_head = adapter.head(key=test_key)
        assert final_head is None
