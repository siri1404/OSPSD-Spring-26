from __future__ import annotations

from typing import Mapping

from cloud_storage_client_api import CloudStorageClient, ObjectInfo

class GCPCloudStorageClient(CloudStorageClient):
    def __init__(self) -> None:
        # Later: initialize google.cloud.storage.Client + bucket from env
        pass

    def upload_file(self, *, local_path: str, key: str, content_type: str | None = None) -> ObjectInfo:
        raise NotImplementedError

    def upload_bytes(self, *, data: bytes, key: str, content_type: str | None = None, metadata: Mapping[str, str] | None = None) -> ObjectInfo:
        raise NotImplementedError

    def download_bytes(self, *, key: str) -> bytes:
        raise NotImplementedError

    def list(self, *, prefix: str) -> list[ObjectInfo]:
        raise NotImplementedError

    def delete(self, *, key: str) -> None:
        raise NotImplementedError

    def head(self, *, key: str) -> ObjectInfo | None:
        raise NotImplementedError
