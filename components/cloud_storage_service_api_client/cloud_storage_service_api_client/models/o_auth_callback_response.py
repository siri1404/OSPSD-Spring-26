from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="OAuthCallbackResponse")


@_attrs_define
class OAuthCallbackResponse:
    """Response model for /auth/callback.

    Attributes:
        access_token (str): Opaque service-owned session token. The provider's actual access token is never exposed to
            clients.
        token_type (Literal['bearer'] | Unset): OAuth 2.0 token type. Always 'bearer'. Default: 'bearer'.
        expires_in (int | None | Unset): Lifetime of the underlying provider token in seconds
    """

    access_token: str
    token_type: Literal["bearer"] | Unset = "bearer"
    expires_in: int | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        access_token = self.access_token

        token_type = self.token_type

        expires_in: int | None | Unset
        if isinstance(self.expires_in, Unset):
            expires_in = UNSET
        else:
            expires_in = self.expires_in

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "access_token": access_token,
            }
        )
        if token_type is not UNSET:
            field_dict["token_type"] = token_type
        if expires_in is not UNSET:
            field_dict["expires_in"] = expires_in

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        access_token = d.pop("access_token")

        token_type = cast(Literal["bearer"] | Unset, d.pop("token_type", UNSET))
        if token_type != "bearer" and not isinstance(token_type, Unset):
            raise ValueError(f"token_type must match const 'bearer', got '{token_type}'")

        def _parse_expires_in(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        expires_in = _parse_expires_in(d.pop("expires_in", UNSET))

        o_auth_callback_response = cls(
            access_token=access_token,
            token_type=token_type,
            expires_in=expires_in,
        )

        return o_auth_callback_response
