"""Integration tests for shared cloud_storage_api contract behavior.

The shared cloud_storage_api package intentionally exposes no di module.
"""

from __future__ import annotations

import importlib
import io
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import BinaryIO

import pytest
from cloud_storage_api import CloudStorageClient, DeleteResult, ObjectInfo
from cloud_storage_api.exceptions import ObjectNotFoundError


class _FakeClient(CloudStorageClient):
    """In-memory fake implementing the shared CloudStorageClient contract."""

    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}

    def upload_file(self, container: str, local_path: str, remote_path: str) -> ObjectInfo:
        data = Path(local_path).read_bytes()
        self._objects[remote_path] = data
        return self._build_info(remote_path, len(data))

    def upload_obj(self, container: str, file_obj: BinaryIO, remote_path: str) -> ObjectInfo:
        data = file_obj.read()
        if not isinstance(data, bytes):
            data = bytes(data)
        self._objects[remote_path] = data
        return self._build_info(remote_path, len(data))

    def download_file(self, container: str, object_name: str, file_name: str) -> ObjectInfo:
        if object_name not in self._objects:
            message = f"Object not found: {object_name}"
            raise ObjectNotFoundError(message)
        Path(file_name).write_bytes(self._objects[object_name])
        return self._build_info(object_name, len(self._objects[object_name]))

    def list_files(self, container: str, prefix: str) -> list[ObjectInfo]:
        names = sorted(name for name in self._objects if name.startswith(prefix))
        return [self._build_info(name, len(self._objects[name])) for name in names]

    def delete_file(self, container: str, object_name: str) -> DeleteResult:
        if object_name not in self._objects:
            message = f"Object not found: {object_name}"
            raise ObjectNotFoundError(message)
        del self._objects[object_name]
        return DeleteResult(deleted=True, version_id=None, request_charged=None)

    def get_file_info(self, container: str, object_name: str) -> ObjectInfo:
        if object_name not in self._objects:
            message = f"Object not found: {object_name}"
            raise ObjectNotFoundError(message)
        return self._build_info(object_name, len(self._objects[object_name]))

    @staticmethod
    def _build_info(object_name: str, size_bytes: int) -> ObjectInfo:
        return ObjectInfo(
            object_name=object_name,
            version_id=None,
            data_type="application/octet-stream",
            integrity=None,
            encryption=None,
            storage_tier=None,
            size_bytes=size_bytes,
            updated_at=datetime.now(UTC),
            metadata=None,
        )


@pytest.mark.integration
def test_package_has_no_di_module() -> None:
    """Shared cloud_storage_api intentionally does not expose a di module."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("cloud_storage_api.di")


@pytest.mark.integration
def test_fake_client_matches_shared_contract(tmp_path: Path) -> None:
    """Verify fake client methods and ObjectInfo fields follow shared API semantics."""
    client = _FakeClient()
    container = "test-container"
    remote_path = "prefix/object.txt"
    payload = b"hello contract"

    uploaded = client.upload_obj(container=container, file_obj=io.BytesIO(payload), remote_path=remote_path)
    assert uploaded.object_name == remote_path
    assert uploaded.size_bytes == len(payload)

    info = client.get_file_info(container=container, object_name=remote_path)
    assert info.object_name == remote_path
    assert info.data_type == "application/octet-stream"

    download_path = tmp_path / "downloaded.bin"
    downloaded_info = client.download_file(container=container, object_name=remote_path, file_name=str(download_path))
    assert downloaded_info.object_name == remote_path
    assert download_path.read_bytes() == payload

    listed = client.list_files(container=container, prefix="prefix/")
    assert any(obj.object_name == remote_path for obj in listed)

    result = client.delete_file(container=container, object_name=remote_path)
    assert result["deleted"] is True

    with pytest.raises(ObjectNotFoundError):
        client.get_file_info(container=container, object_name=remote_path)
