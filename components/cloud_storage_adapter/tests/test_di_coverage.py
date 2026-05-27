"""Small test to exercise cloud_storage_client_api.di registration paths to improve coverage."""

from __future__ import annotations

from collections.abc import Callable, Mapping

import pytest
from cloud_storage_client_api import di
from cloud_storage_client_api.client import CloudStorageClient, ObjectInfo


class _DummyClient(CloudStorageClient):
    def upload_file(self, *, local_path: str, key: str, content_type: str | None = None) -> ObjectInfo:
        return ObjectInfo(key=key)

    def upload_bytes(
        self, *, data: bytes, key: str, content_type: str | None = None, metadata: Mapping[str, str] | None = None
    ) -> ObjectInfo:
        return ObjectInfo(key=key)

    def download_bytes(self, *, key: str) -> bytes:
        return b""

    def list(self, *, prefix: str) -> list[ObjectInfo]:
        return []

    def delete(self, *, key: str) -> None:
        return None

    def head(self, *, key: str) -> ObjectInfo | None:
        return None


def test_di_register_and_override_paths() -> None:
    # Ensure registry errors when missing
    with pytest.raises(RuntimeError):
        di.get_client("__does_not_exist__")

    # Register default provider and get it
    di.register_get_client(lambda: _DummyClient())
    client = di.get_client()
    assert isinstance(client, _DummyClient)

    # Override within context
    def _other() -> CloudStorageClient:
        return _DummyClient()

    with di.override_get_client(_other):
        c = di.get_client()
        assert isinstance(c, _DummyClient)

    # Unregister and ensure error raised again
    di.unregister_get_client()
    with pytest.raises(RuntimeError):
        di.get_client()
