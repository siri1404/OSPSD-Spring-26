"""Shared public models for cloud storage operations."""

from __future__ import annotations

from collections.abc import Mapping  # noqa: TC003
from dataclasses import dataclass
from datetime import datetime  # noqa: TC003
from typing import TypedDict


@dataclass(frozen=True, slots=True)
class ObjectInfo:
    """Provider-agnostic metadata about a stored object.

    Attributes:
        object_name: Provider object key or path.
        version_id: Provider-specific object version identifier when one exists.
        data_type: MIME type or provider-reported content type.
        integrity: Checksum, ETag, or other integrity marker.
        encryption: Encryption mode or algorithm applied to the object.
        storage_tier: Storage class or access tier for the object.
        size_bytes: Object size in bytes when available.
        updated_at: Last-modified timestamp when the provider exposes one.
        metadata: Provider object metadata normalized to string key/value pairs.
    """

    object_name: str
    version_id: str | None = None
    data_type: str | None = None
    integrity: str | None = None
    encryption: str | None = None
    storage_tier: str | None = None
    size_bytes: int | None = None
    updated_at: datetime | None = None
    metadata: Mapping[str, str] | None = None


class DeleteResult(TypedDict):
    """Canonical response metadata for a delete operation.

    This type intentionally exposes only provider-neutral keys so consumers do
    not need to reason about provider-specific response shapes.
    """

    deleted: bool
    version_id: str | None
    request_charged: bool | None
