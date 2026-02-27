"""Unit tests for ObjectInfo (cloud_storage_client_api/client.py)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cloud_storage_client_api.client import CloudStorageClient, ObjectInfo


@pytest.mark.unit
class TestObjectInfo:
    """ObjectInfo is a frozen dataclass — verify its fields and defaults."""

    def test_optional_fields_default_to_none(self) -> None:
        # Only key is required; everything else should be None when omitted.
        info = ObjectInfo(key="x")
        assert info.size_bytes is None
        assert info.etag is None
        assert info.updated_at is None
        assert info.content_type is None
        assert info.metadata is None

    def test_all_fields_are_stored(self) -> None:
        ts = datetime(2025, 6, 15, tzinfo=timezone.utc)
        info = ObjectInfo(
            key="docs/report.pdf",
            size_bytes=2048,
            etag="abc-etag",
            updated_at=ts,
            content_type="application/pdf",
            metadata={"owner": "alice"},
        )
        assert info.key == "docs/report.pdf"
        assert info.size_bytes == 2048
        assert info.etag == "abc-etag"
        assert info.updated_at == ts
        assert info.content_type == "application/pdf"
        assert info.metadata == {"owner": "alice"}

    def test_is_immutable(self) -> None:
        # frozen=True on the dataclass means we can't change fields after creation.
        info = ObjectInfo(key="file.txt")
        with pytest.raises((AttributeError, TypeError)):
            info.key = "changed"  # type: ignore[misc]  # intentionally testing runtime freeze behaviour on frozen dataclass

    def test_cannot_instantiate_abstract_client(self) -> None:
        # CloudStorageClient is abstract — direct instantiation must raise.
        with pytest.raises(TypeError):
            CloudStorageClient()  # type: ignore[abstract]
