from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from .. import types
from ..types import UNSET, Unset

T = TypeVar("T", bound="BodyUploadFileUploadPost")


@_attrs_define
class BodyUploadFileUploadPost:
    """
    Attributes:
        file (str): File to upload
        key (str): Object key/path in storage
        content_type (None | str | Unset): MIME type of the content
    """

    file: str
    key: str
    content_type: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        file = self.file

        key = self.key

        content_type: None | str | Unset
        if isinstance(self.content_type, Unset):
            content_type = UNSET
        else:
            content_type = self.content_type

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "file": file,
                "key": key,
            }
        )
        if content_type is not UNSET:
            field_dict["content_type"] = content_type

        return field_dict

    def to_multipart(self) -> types.RequestFiles:
        files: types.RequestFiles = []

        files.append(("file", (None, str(self.file).encode(), "text/plain")))

        files.append(("key", (None, str(self.key).encode(), "text/plain")))

        if not isinstance(self.content_type, Unset):
            if isinstance(self.content_type, str):
                files.append(("content_type", (None, str(self.content_type).encode(), "text/plain")))
            else:
                files.append(("content_type", (None, str(self.content_type).encode(), "text/plain")))

        for prop_name, prop in self.additional_properties.items():
            files.append((prop_name, (None, str(prop).encode(), "text/plain")))

        return files

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        file = d.pop("file")

        key = d.pop("key")

        def _parse_content_type(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        content_type = _parse_content_type(d.pop("content_type", UNSET))

        body_upload_file_upload_post = cls(
            file=file,
            key=key,
            content_type=content_type,
        )

        body_upload_file_upload_post.additional_properties = d
        return body_upload_file_upload_post

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
