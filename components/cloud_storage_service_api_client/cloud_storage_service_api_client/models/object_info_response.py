from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from dateutil.parser import isoparse

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.object_info_response_metadata_type_0 import ObjectInfoResponseMetadataType0


T = TypeVar("T", bound="ObjectInfoResponse")


@_attrs_define
class ObjectInfoResponse:
    """Response model for object metadata.

    Attributes:
        key (str):
        size_bytes (int | None | Unset):
        etag (None | str | Unset):
        updated_at (datetime.datetime | None | Unset):
        content_type (None | str | Unset):
        metadata (None | ObjectInfoResponseMetadataType0 | Unset):
    """

    key: str
    size_bytes: int | None | Unset = UNSET
    etag: None | str | Unset = UNSET
    updated_at: datetime.datetime | None | Unset = UNSET
    content_type: None | str | Unset = UNSET
    metadata: None | ObjectInfoResponseMetadataType0 | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.object_info_response_metadata_type_0 import ObjectInfoResponseMetadataType0

        key = self.key

        size_bytes: int | None | Unset
        if isinstance(self.size_bytes, Unset):
            size_bytes = UNSET
        else:
            size_bytes = self.size_bytes

        etag: None | str | Unset
        if isinstance(self.etag, Unset):
            etag = UNSET
        else:
            etag = self.etag

        updated_at: None | str | Unset
        if isinstance(self.updated_at, Unset):
            updated_at = UNSET
        elif isinstance(self.updated_at, datetime.datetime):
            updated_at = self.updated_at.isoformat()
        else:
            updated_at = self.updated_at

        content_type: None | str | Unset
        if isinstance(self.content_type, Unset):
            content_type = UNSET
        else:
            content_type = self.content_type

        metadata: dict[str, Any] | None | Unset
        if isinstance(self.metadata, Unset):
            metadata = UNSET
        elif isinstance(self.metadata, ObjectInfoResponseMetadataType0):
            metadata = self.metadata.to_dict()
        else:
            metadata = self.metadata

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "key": key,
            }
        )
        if size_bytes is not UNSET:
            field_dict["size_bytes"] = size_bytes
        if etag is not UNSET:
            field_dict["etag"] = etag
        if updated_at is not UNSET:
            field_dict["updated_at"] = updated_at
        if content_type is not UNSET:
            field_dict["content_type"] = content_type
        if metadata is not UNSET:
            field_dict["metadata"] = metadata

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.object_info_response_metadata_type_0 import ObjectInfoResponseMetadataType0

        d = dict(src_dict)
        key = d.pop("key")

        def _parse_size_bytes(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        size_bytes = _parse_size_bytes(d.pop("size_bytes", UNSET))

        def _parse_etag(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        etag = _parse_etag(d.pop("etag", UNSET))

        def _parse_updated_at(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                updated_at_type_0 = isoparse(data)

                return updated_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        updated_at = _parse_updated_at(d.pop("updated_at", UNSET))

        def _parse_content_type(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        content_type = _parse_content_type(d.pop("content_type", UNSET))

        def _parse_metadata(data: object) -> None | ObjectInfoResponseMetadataType0 | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                metadata_type_0 = ObjectInfoResponseMetadataType0.from_dict(data)

                return metadata_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | ObjectInfoResponseMetadataType0 | Unset, data)

        metadata = _parse_metadata(d.pop("metadata", UNSET))

        object_info_response = cls(
            key=key,
            size_bytes=size_bytes,
            etag=etag,
            updated_at=updated_at,
            content_type=content_type,
            metadata=metadata,
        )

        object_info_response.additional_properties = d
        return object_info_response

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
