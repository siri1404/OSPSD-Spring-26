"""Unit tests for GCPCloudStorageClient._blob_to_object_info."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from gcp_client_impl.client import GCPCloudStorageClient


def _make_blob(
    *,
    name: str = "file.txt",
    size: int = 10,
    etag: str = "etag-x",
    updated: datetime | None = None,
    content_type: str = "text/plain",
    metadata: dict[str, str] | None = None,
    generation: str = "gen-1",
    kms_key_name: str | None = None,
    storage_class: str = "STANDARD",
) -> MagicMock:
    blob = MagicMock()
    blob.name = name
    blob.size = size
    blob.etag = etag
    blob.updated = updated or datetime(2025, 1, 1, tzinfo=UTC)
    blob.content_type = content_type
    blob.metadata = metadata
    blob.generation = generation
    blob.kms_key_name = kms_key_name
    blob.storage_class = storage_class
    return blob


@pytest.mark.unit
class TestBlobToObjectInfo:
    """Tests for GCPCloudStorageClient._blob_to_object_info."""

    def setup_method(self) -> None:
        self.client = GCPCloudStorageClient()

    def test_all_fields_are_mapped_correctly(self) -> None:
        ts = datetime(2025, 3, 10, tzinfo=UTC)
        blob = _make_blob(
            name="reports/q1.xlsx",
            size=4096,
            etag="etag-q1",
            updated=ts,
            content_type="application/vnd.ms-excel",
            metadata={"quarter": "Q1"},
            generation="gen-42",
            kms_key_name="kms/key/1",
            storage_class="COLDLINE",
        )
        info = self.client._blob_to_object_info(blob)

        assert info.object_name == "reports/q1.xlsx"
        assert info.size_bytes == 4096
        assert info.integrity == "etag-q1"
        assert info.updated_at == ts
        assert info.data_type == "application/vnd.ms-excel"
        assert info.metadata == {"quarter": "Q1"}
        assert info.version_id == "gen-42"
        assert info.encryption == "kms/key/1"
        assert info.storage_tier == "COLDLINE"
