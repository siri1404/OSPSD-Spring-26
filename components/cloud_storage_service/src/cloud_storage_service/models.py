"""Pydantic models for request/response validation."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ObjectInfoResponse(BaseModel):
    """Response model for object metadata."""

    key: str
    size_bytes: int | None = None
    etag: str | None = None
    updated_at: datetime | None = None
    content_type: str | None = None
    metadata: dict[str, str] | None = None


class UploadRequest(BaseModel):
    """Request model for uploading bytes."""

    key: str = Field(..., description="Object key/path in storage")
    content_type: str | None = Field(None, description="MIME type of the content")
    metadata: dict[str, str] | None = Field(None, description="Custom metadata")


class ListRequest(BaseModel):
    """Request model for listing objects."""

    prefix: str = Field("", description="Prefix filter for object keys")


class ListResponse(BaseModel):
    """Response model for listing objects."""

    objects: list[ObjectInfoResponse]


class DeleteRequest(BaseModel):
    """Request model for deleting an object."""

    key: str = Field(..., description="Object key/path to delete")


class HealthResponse(BaseModel):
    """Response model for health check."""

    status: str
    service: str
    timestamp: datetime


class ErrorResponse(BaseModel):
    """Response model for errors."""

    error: str
    detail: str | None = None


class OAuthLoginResponse(BaseModel):
    """Response model for OAuth login."""

    auth_url: str = Field(..., description="URL to redirect user for OAuth authorization")


class OAuthCallbackResponse(BaseModel):
    """Response model for OAuth callback."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int | None = None
