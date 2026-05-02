from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define

if TYPE_CHECKING:
    from ..models.object_info_response import ObjectInfoResponse


T = TypeVar("T", bound="ListResponse")


@_attrs_define
class ListResponse:
    """Response model for listing objects.

    Attributes:
        objects (list[ObjectInfoResponse]): Objects matching the prefix, sorted by object_name.
    """

    objects: list[ObjectInfoResponse]

    def to_dict(self) -> dict[str, Any]:
        objects = []
        for objects_item_data in self.objects:
            objects_item = objects_item_data.to_dict()
            objects.append(objects_item)

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "objects": objects,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.object_info_response import ObjectInfoResponse

        d = dict(src_dict)
        objects = []
        _objects = d.pop("objects")
        for objects_item_data in _objects:
            objects_item = ObjectInfoResponse.from_dict(objects_item_data)

            objects.append(objects_item)

        list_response = cls(
            objects=objects,
        )

        return list_response
