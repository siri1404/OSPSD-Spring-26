"""Pydantic models for request/response validation.

The response models mirror the shared cross-team ObjectInfo contract from
cloud_storage_api (object_name, integrity, data_type, ...) — NOT the legacy v0
shape (key, etag, content_type). External consumers should see the same field
names as first-party SDKs that import from cloud_storage_api.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    """Base for all API models.

    Forbids extra fields so contract drift surfaces as a validation error
    instead of a silent serialization gap.
    """

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Storage models
# ---------------------------------------------------------------------------


class ObjectInfoResponse(APIModel):
    """Object metadata mirroring the shared cross-team ObjectInfo contract."""

    object_name: str = Field(..., description="Object key/path in storage")
    size_bytes: int | None = Field(default=None, description="Object size in bytes")
    integrity: str | None = Field(default=None, description="ETag or content hash")
    data_type: str | None = Field(default=None, description="MIME type (e.g. 'application/json')")
    updated_at: datetime | None = Field(default=None, description="Last modified timestamp (UTC)")
    version_id: str | None = Field(default=None, description="Provider version or generation identifier")
    encryption: str | None = Field(
        default=None,
        description="KMS key name if customer-managed encryption is used",
    )
    storage_tier: str | None = Field(
        default=None,
        description="Storage class (e.g. STANDARD, NEARLINE, COLDLINE, ARCHIVE)",
    )
    metadata: dict[str, str] | None = Field(default=None, description="Custom user-defined metadata")


class ListResponse(APIModel):
    """Response model for listing objects."""

    objects: list[ObjectInfoResponse] = Field(..., description="Objects matching the prefix, sorted by object_name.")


# ---------------------------------------------------------------------------
# Health & error models
# ---------------------------------------------------------------------------


class HealthResponse(APIModel):
    """Response model for the /health endpoint."""

    status: Literal["healthy", "degraded", "unhealthy"] = Field(..., description="Service health state")
    service: str = Field(..., description="Service identifier")
    timestamp: datetime = Field(..., description="Health-check timestamp (UTC)")


# ---------------------------------------------------------------------------
# OAuth models
# ---------------------------------------------------------------------------


class OAuthLoginResponse(APIModel):
    """Response model for /auth/login."""

    auth_url: str = Field(..., description="URL to redirect the user for OAuth authorization")


class OAuthCallbackResponse(APIModel):
    """Response model for /auth/callback."""

    access_token: str = Field(
        ...,
        description=("Opaque service-owned session token. The provider's actual access token is never exposed to clients."),
    )
    token_type: Literal["bearer"] = Field(default="bearer", description="OAuth 2.0 token type. Always 'bearer'.")
    expires_in: int | None = Field(
        default=None,
        description="Lifetime of the underlying provider token in seconds",
    )
