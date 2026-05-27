from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from dateutil.parser import isoparse

from ..models.health_response_status import HealthResponseStatus

T = TypeVar("T", bound="HealthResponse")


@_attrs_define
class HealthResponse:
    """Response model for the /health endpoint.

    Attributes:
        status (HealthResponseStatus): Service health state
        service (str): Service identifier
        timestamp (datetime.datetime): Health-check timestamp (UTC)
    """

    status: HealthResponseStatus
    service: str
    timestamp: datetime.datetime

    def to_dict(self) -> dict[str, Any]:
        status = self.status.value

        service = self.service

        timestamp = self.timestamp.isoformat()

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "status": status,
                "service": service,
                "timestamp": timestamp,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        status = HealthResponseStatus(d.pop("status"))

        service = d.pop("service")

        timestamp = isoparse(d.pop("timestamp"))

        health_response = cls(
            status=status,
            service=service,
            timestamp=timestamp,
        )

        return health_response
