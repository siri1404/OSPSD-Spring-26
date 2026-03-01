"""Abstract base class and data models for cloud storage operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime


@dataclass(frozen=True)
class ObjectInfo:
    """Metadata and information about a cloud storage object."""

    key: str
    size_bytes: int | None = None
    etag: str | None = None
    updated_at: datetime | None = None
    content_type: str | None = None
    metadata: Mapping[str, str] | None = None


class CloudStorageClient(ABC):
    """Abstract base class for cloud storage client implementations."""

    @abstractmethod
    def upload_file(self, *, local_path: str, key: str, content_type: str | None = None) -> ObjectInfo:
        """Upload a file from the local filesystem to cloud storage."""
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
        """Upload bytes to cloud storage."""
        raise NotImplementedError

    @abstractmethod
    def download_bytes(self, *, key: str) -> bytes:
        """Download an object from cloud storage as bytes."""
        raise NotImplementedError

    @abstractmethod
    def list(self, *, prefix: str) -> list[ObjectInfo]:
        """List objects in cloud storage with the given prefix."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, *, key: str) -> None:
        """Delete an object from cloud storage."""
        raise NotImplementedError

    @abstractmethod
    def head(self, *, key: str) -> ObjectInfo | None:
        """Get metadata about an object without downloading its contents.

        Returns None if the object does not exist.
        """
        raise NotImplementedError
