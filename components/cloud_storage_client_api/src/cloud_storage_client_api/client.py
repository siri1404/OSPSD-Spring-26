from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Mapping


@dataclass(frozen=True)
class ObjectInfo:
    key: str
    size_bytes: int | None = None
    etag: str | None = None
    updated_at: datetime | None = None
    content_type: str | None = None
    metadata: Mapping[str, str] | None = None


class CloudStorageClient(ABC):
    @abstractmethod
    def upload_file(
        self, *, local_path: str, key: str, content_type: str | None = None
    ) -> ObjectInfo:
        raise NotImplementedError

    @abstractmethod
    def upload_bytes(
        self,
        *,
        data: bytes,
        key: str,
        content_type: str | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> ObjectInfo:
        raise NotImplementedError

    @abstractmethod
    def download_bytes(self, *, key: str) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def list(self, *, prefix: str) -> list[ObjectInfo]:
        raise NotImplementedError

    @abstractmethod
    def delete(self, *, key: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def head(self, *, key: str) -> ObjectInfo | None:
        raise NotImplementedError
