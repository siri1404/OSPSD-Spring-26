from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

T = TypeVar("T", bound="OAuthLoginResponse")


@_attrs_define
class OAuthLoginResponse:
    """Response model for /auth/login.

    Attributes:
        auth_url (str): URL to redirect the user for OAuth authorization
    """

    auth_url: str

    def to_dict(self) -> dict[str, Any]:
        auth_url = self.auth_url

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "auth_url": auth_url,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        auth_url = d.pop("auth_url")

        o_auth_login_response = cls(
            auth_url=auth_url,
        )

        return o_auth_login_response
