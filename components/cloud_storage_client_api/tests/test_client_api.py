"""Unit tests for ObjectInfo (cloud_storage_client_api/models.py)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from cloud_storage_client_api.models import ObjectInfo


@pytest.mark.unit
class TestObjectInfo:
    """ObjectInfo is a frozen dataclass — verify its fields and defaults."""

    def test_required_field_object_name(self) -> None:
        """Test that object_name is the only required field."""
        info = ObjectInfo(object_name="documents/file.txt")
        assert info.object_name == "documents/file.txt"
        assert info.version_id is None
        assert info.data_type is None
        assert info.integrity is None
        assert info.encryption is None
        assert info.storage_tier is None
        assert info.size_bytes is None
        assert info.updated_at is None
        assert info.metadata is None

    def test_all_fields_are_stored(self) -> None:
        """Test that all fields are correctly stored when provided."""
        ts = datetime(2025, 6, 15, tzinfo=UTC)
        size_bytes = 2048
        info = ObjectInfo(
            object_name="docs/report.pdf",
            version_id="v123",
            data_type="application/pdf",
            integrity="etag-abc",
            encryption="AES-256",
            storage_tier="STANDARD",
            size_bytes=size_bytes,
            updated_at=ts,
            metadata={"owner": "alice", "department": "finance"},
        )
        assert info.object_name == "docs/report.pdf"
        assert info.version_id == "v123"
        assert info.data_type == "application/pdf"
        assert info.integrity == "etag-abc"
        assert info.encryption == "AES-256"
        assert info.storage_tier == "STANDARD"
        assert info.size_bytes == size_bytes
        assert info.updated_at == ts
        assert info.metadata == {"owner": "alice", "department": "finance"}

    def test_is_immutable(self) -> None:
        """Test that ObjectInfo is immutable (frozen dataclass)."""
        info = ObjectInfo(object_name="file.txt")
        with pytest.raises((AttributeError, TypeError)):
            info.object_name = "changed"  # type: ignore[misc]
