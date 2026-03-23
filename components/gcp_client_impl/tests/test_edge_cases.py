"""Edge case unit tests for GCPCloudStorageClient.

Tests boundary conditions, error paths, and configuration edge cases.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from gcp_client_impl.client import GCPCloudStorageClient


@pytest.mark.unit
class TestUploadBytesEdgeCases:
    """Edge case tests for upload_bytes."""

    def test_upload_empty_bytes(self) -> None:
        """Test uploading empty bytes (0 bytes)."""
        blob = MagicMock()
        blob.name = "empty.txt"
        blob.size = 0
        bucket = MagicMock()
        bucket.blob.return_value = blob
        storage_client = MagicMock()
        storage_client.bucket.return_value = bucket

        client = GCPCloudStorageClient(bucket_name="test-bucket")
        client._storage_client = storage_client

        result = client.upload_bytes(data=b"", key="empty.txt")

        assert result.key == "empty.txt"
        assert result.size_bytes == 0
        blob.upload_from_string.assert_called_once_with(b"", content_type=None)

    def test_upload_with_special_characters_in_key(self) -> None:
        """Test uploading with special characters in object key."""
        blob = MagicMock()
        blob.name = "folder/file (1) [copy].txt"
        blob.size = 42
        bucket = MagicMock()
        bucket.blob.return_value = blob
        storage_client = MagicMock()
        storage_client.bucket.return_value = bucket

        client = GCPCloudStorageClient(bucket_name="test-bucket")
        client._storage_client = storage_client

        result = client.upload_bytes(data=b"test", key="folder/file (1) [copy].txt")

        assert result.key == "folder/file (1) [copy].txt"

    def test_upload_with_none_content_type(self) -> None:
        """Test uploading without specifying content type."""
        blob = MagicMock()
        blob.name = "file.bin"
        bucket = MagicMock()
        bucket.blob.return_value = blob
        storage_client = MagicMock()
        storage_client.bucket.return_value = bucket

        client = GCPCloudStorageClient(bucket_name="test-bucket")
        client._storage_client = storage_client

        result = client.upload_bytes(data=b"binary", key="file.bin", content_type=None)

        blob.upload_from_string.assert_called_once_with(b"binary", content_type=None)
        assert result.key == "file.bin"

    def test_upload_with_none_metadata(self) -> None:
        """Test uploading without metadata."""
        blob = MagicMock()
        blob.name = "file.txt"
        blob.metadata = {}  # Default empty metadata
        bucket = MagicMock()
        bucket.blob.return_value = blob
        storage_client = MagicMock()
        storage_client.bucket.return_value = bucket

        client = GCPCloudStorageClient(bucket_name="test-bucket")
        client._storage_client = storage_client

        result = client.upload_bytes(data=b"test", key="file.txt", metadata=None)

        # Metadata should not be set when None is passed
        assert result.key == "file.txt"

    def test_upload_with_empty_metadata_dict(self) -> None:
        """Test uploading with empty metadata dictionary."""
        blob = MagicMock()
        blob.name = "file.txt"
        bucket = MagicMock()
        bucket.blob.return_value = blob
        storage_client = MagicMock()
        storage_client.bucket.return_value = bucket

        client = GCPCloudStorageClient(bucket_name="test-bucket")
        client._storage_client = storage_client

        result = client.upload_bytes(data=b"test", key="file.txt", metadata={})

        assert result.key == "file.txt"

    def test_upload_very_large_bytes(self) -> None:
        """Test uploading very large file (100 MB simulation)."""
        blob = MagicMock()
        blob.name = "large_file.zip"
        blob.size = 100_000_000  # 100 MB
        bucket = MagicMock()
        bucket.blob.return_value = blob
        storage_client = MagicMock()
        storage_client.bucket.return_value = bucket

        client = GCPCloudStorageClient(bucket_name="test-bucket")
        client._storage_client = storage_client

        large_data = b"x" * 1_000_000  # 1 MB for test
        result = client.upload_bytes(data=large_data, key="large_file.zip")

        assert result.size_bytes == 100_000_000


@pytest.mark.unit
class TestListEdgeCases:
    """Edge case tests for list operation."""

    def test_list_with_empty_prefix(self) -> None:
        """Test listing with empty prefix (list all)."""
        blobs = [
            MagicMock(name="file1.txt"),
            MagicMock(name="file2.txt"),
        ]
        bucket = MagicMock()
        bucket.list_blobs.return_value = blobs
        storage_client = MagicMock()
        storage_client.bucket.return_value = bucket

        client = GCPCloudStorageClient(bucket_name="test-bucket")
        client._storage_client = storage_client

        results = client.list(prefix="")

        bucket.list_blobs.assert_called_with(prefix="")
        assert len(results) == 2

    def test_list_with_nested_prefix(self) -> None:
        """Test listing with deeply nested prefix."""
        blob = MagicMock()
        blob.name = "a/b/c/d/e/file.txt"
        blob.size = 100
        blob.etag = "etag"
        blob.updated = None
        blob.content_type = "text/plain"
        blob.metadata = {}
        blobs = [blob]
        bucket = MagicMock()
        bucket.list_blobs.return_value = blobs
        storage_client = MagicMock()
        storage_client.bucket.return_value = bucket

        client = GCPCloudStorageClient(bucket_name="test-bucket")
        client._storage_client = storage_client

        results = client.list(prefix="a/b/c/d/e/")

        assert len(results) == 1
        assert results[0].key == "a/b/c/d/e/file.txt"

    def test_list_with_no_results(self) -> None:
        """Test listing when no objects match prefix."""
        bucket = MagicMock()
        bucket.list_blobs.return_value = []
        storage_client = MagicMock()
        storage_client.bucket.return_value = bucket

        client = GCPCloudStorageClient(bucket_name="test-bucket")
        client._storage_client = storage_client

        results = client.list(prefix="nonexistent/")

        assert results == []


@pytest.mark.unit
class TestConfigurationEdgeCases:
    """Edge case tests for configuration handling."""

    def test_kwargs_override_all_env_vars(self) -> None:
        """Test that kwargs completely override environment variables."""
        with patch.dict(
            "os.environ",
            {
                "GCS_BUCKET_NAME": "env-bucket",
                "GOOGLE_CLOUD_PROJECT": "env-project",
                "GOOGLE_APPLICATION_CREDENTIALS": "/env/path",
            },
        ):
            client = GCPCloudStorageClient(
                bucket_name="kwargs-bucket",
                project_id="kwargs-project",
                credentials_path="/kwargs/path",
            )

            assert client._config.bucket_name == "kwargs-bucket"
            assert client._config.project_id == "kwargs-project"
            assert client._config.credentials_path == "/kwargs/path"

    def test_partial_env_vars_with_kwargs(self) -> None:
        """Test mixing kwargs and env vars (precedence test)."""
        with patch.dict(
            "os.environ",
            {
                "GCS_BUCKET_NAME": "env-bucket",
                "GOOGLE_CLOUD_PROJECT": "env-project",
            },
            clear=False,
        ):
            client = GCPCloudStorageClient(bucket_name="kwargs-bucket")

            assert client._config.bucket_name == "kwargs-bucket"  # kwargs win
            assert client._config.project_id == "env-project"  # falls back to env


@pytest.mark.unit
class TestBlobMetadataEdgeCases:
    """Edge case tests for blob metadata handling."""

    def test_blob_with_null_metadata(self) -> None:
        """Test blob.metadata when it's None from GCS."""
        blob = MagicMock()
        blob.name = "file.txt"
        blob.size = 100
        blob.metadata = None  # GCS returns None, not empty dict
        bucket = MagicMock()
        bucket.blob.return_value = blob
        storage_client = MagicMock()
        storage_client.bucket.return_value = bucket

        client = GCPCloudStorageClient(bucket_name="test-bucket")
        client._storage_client = storage_client

        result = client.upload_bytes(data=b"test", key="file.txt")

        # Should convert None to empty dict
        assert result.metadata == {}

    def test_blob_metadata_with_special_characters(self) -> None:
        """Test metadata values containing special characters."""
        blob = MagicMock()
        blob.name = "file.txt"
        blob.metadata = {"author": "José García", "key": "value-with-dash_underscore"}
        bucket = MagicMock()
        bucket.blob.return_value = blob
        storage_client = MagicMock()
        storage_client.bucket.return_value = bucket

        client = GCPCloudStorageClient(bucket_name="test-bucket")
        client._storage_client = storage_client

        result = client.upload_bytes(data=b"test", key="file.txt")

        assert result.metadata == {"author": "José García", "key": "value-with-dash_underscore"}


@pytest.mark.unit
class TestHeadEdgeCases:
    """Edge case tests for head operation."""

    def test_head_with_special_characters_in_key(self) -> None:
        """Test head with special characters in key."""
        blob = MagicMock()
        blob.name = "folder/file (1) [copy].txt"
        blob.exists.return_value = True
        bucket = MagicMock()
        bucket.blob.return_value = blob
        storage_client = MagicMock()
        storage_client.bucket.return_value = bucket

        client = GCPCloudStorageClient(bucket_name="test-bucket")
        client._storage_client = storage_client

        result = client.head(key="folder/file (1) [copy].txt")

        assert result is not None
        assert result.key == "folder/file (1) [copy].txt"

    def test_head_refreshes_metadata(self) -> None:
        """Test that head reloads metadata from GCS."""
        blob = MagicMock()
        blob.name = "file.txt"
        blob.exists.return_value = True
        bucket = MagicMock()
        bucket.blob.return_value = blob
        storage_client = MagicMock()
        storage_client.bucket.return_value = bucket

        client = GCPCloudStorageClient(bucket_name="test-bucket")
        client._storage_client = storage_client

        client.head(key="file.txt")

        blob.reload.assert_called_once()
