"""Unit tests for GCPCloudStorageClient._blob_to_object_info."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from gcp_client_impl.client import GCPCloudStorageClient


def _make_blob(  # noqa: PLR0913
    *,
    name: str = "file.txt",
    size: int = 10,
    etag: str = "etag-x",
    updated: datetime | None = None,
    content_type: str = "text/plain",
    metadata: dict[str, str] | None = None,
) -> MagicMock:
    blob = MagicMock()
    blob.name = name
    blob.size = size
    blob.etag = etag
    blob.updated = updated or datetime(2025, 1, 1, tzinfo=UTC)
    blob.content_type = content_type
    blob.metadata = metadata
    return blob


@pytest.mark.unit
class TestBlobToObjectInfo:
    """Tests for GCPCloudStorageClient._blob_to_object_info."""

    def setup_method(self) -> None:
        self.client = GCPCloudStorageClient(bucket_name="test-bucket")

    def test_all_fields_are_mapped_correctly(self) -> None:
        ts = datetime(2025, 3, 10, tzinfo=UTC)
        blob = _make_blob(
            name="reports/q1.xlsx",
            size=4096,
            etag="etag-q1",
            updated=ts,
            content_type="application/vnd.ms-excel",
            metadata={"quarter": "Q1"},
        )
        info = self.client._blob_to_object_info(blob)
        assert info.key == "reports/q1.xlsx"
        assert info.size_bytes == 4096
        assert info.etag == "etag-q1"
        assert info.updated_at == ts
        assert info.content_type == "application/vnd.ms-excel"
        assert info.metadata == {"quarter": "Q1"}
