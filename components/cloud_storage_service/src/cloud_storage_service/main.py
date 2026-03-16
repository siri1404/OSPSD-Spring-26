"""FastAPI service for cloud storage operations with OAuth 2.0 authentication."""

from __future__ import annotations

import secrets
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from gcp_client_impl import GCPCloudStorageClient

# Load .env file from project root
env_path = Path(__file__).resolve().parents[4] / ".env"
if env_path.exists():
    load_dotenv(env_path)

from cloud_storage_service.auth import (
    AuthConfig,
    build_oauth_url,
    exchange_code_for_token,
    get_auth_config,
    verify_token,
)
from cloud_storage_service.models import (
    HealthResponse,
    ListResponse,
    OAuthCallbackResponse,
    OAuthLoginResponse,
    ObjectInfoResponse,
)

# Initialize FastAPI application
app = FastAPI(
    title="Cloud Storage Service API",
    description="RESTful API for cloud storage operations with OAuth 2.0 authentication",
    version="1.0.0",
)

# Store active sessions (in production, use Redis or a proper session store)
active_sessions: dict[str, str] = {}


def get_storage_client() -> GCPCloudStorageClient:
    """Get GCP Cloud Storage client instance.

    Returns:
        Configured GCPCloudStorageClient instance.
    """
    return GCPCloudStorageClient()


def object_info_to_response(obj: Any) -> ObjectInfoResponse:
    """Convert ObjectInfo to response model.

    Args:
        obj: ObjectInfo instance from gcp_client_impl.

    Returns:
        ObjectInfoResponse for API response.
    """
    return ObjectInfoResponse(
        key=obj.key,
        size_bytes=obj.size_bytes,
        etag=obj.etag,
        updated_at=obj.updated_at,
        content_type=obj.content_type,
        metadata=dict(obj.metadata) if obj.metadata else None,
    )


# ============================================================================
# Health & Status Endpoints
# ============================================================================


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """Health check endpoint to verify service status.

    Returns:
        Health status with timestamp.
    """
    return HealthResponse(
        status="healthy",
        service="cloud-storage-service",
        timestamp=datetime.now(),
    )


# ============================================================================
# OAuth 2.0 Authentication Endpoints
# ============================================================================


@app.post("/auth/login", response_model=OAuthLoginResponse, tags=["Authentication"])
async def oauth_login(config: Annotated[AuthConfig, Depends(get_auth_config)]) -> OAuthLoginResponse:
    """Initiate OAuth 2.0 login flow with Google.

    Generates an authorization URL and redirects the user to Google's OAuth consent screen.

    Returns:
        OAuth authorization URL for user redirect.
    """
    # Generate a random state for CSRF protection
    state = secrets.token_urlsafe(32)
    active_sessions[state] = "pending"

    auth_url = build_oauth_url(config, state=state)

    return OAuthLoginResponse(auth_url=auth_url)


@app.get("/auth/callback", response_model=OAuthCallbackResponse, tags=["Authentication"])
async def oauth_callback(
    code: Annotated[str, Query(description="Authorization code from Google")],
    state: Annotated[str, Query(description="State parameter for CSRF protection")],
    config: Annotated[AuthConfig, Depends(get_auth_config)],
) -> OAuthCallbackResponse:
    """Handle OAuth 2.0 callback from Google.

    Exchanges authorization code for access token.

    Args:
        code: Authorization code from Google OAuth.
        state: State parameter for CSRF validation.
        config: OAuth configuration.

    Returns:
        Access token and token metadata.

    Raises:
        HTTPException: If state is invalid or token exchange fails.
    """
    # Validate state parameter
    if state not in active_sessions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state parameter. Possible CSRF attack.",
        )

    # Exchange code for token
    try:
        token_data = await exchange_code_for_token(code, config)
        active_sessions[state] = token_data["access_token"]

        return OAuthCallbackResponse(
            access_token=token_data["access_token"],
            token_type=token_data.get("token_type", "bearer"),
            expires_in=token_data.get("expires_in"),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to exchange code for token: {exc}",
        ) from exc


# ============================================================================
# Cloud Storage Operation Endpoints
# ============================================================================


@app.post("/upload", response_model=ObjectInfoResponse, tags=["Storage"])
async def upload_file(
    file: Annotated[UploadFile, File(description="File to upload")],
    key: Annotated[str, Form(description="Object key/path in storage")],
    content_type: Annotated[str | None, Form(description="MIME type of the content")] = None,
    token: str = Depends(verify_token),
    client: GCPCloudStorageClient = Depends(get_storage_client),
) -> ObjectInfoResponse:
    """Upload a file to cloud storage.

    Requires authentication via Bearer token.

    Args:
        file: File to upload (multipart/form-data).
        key: Destination key/path in cloud storage.
        content_type: Optional MIME type.
        token: Validated access token.
        client: GCP storage client.

    Returns:
        Object metadata after successful upload.

    Raises:
        HTTPException: If upload fails.
    """
    try:
        # Read file contents
        file_contents = await file.read()

        # Use content_type from form if provided, otherwise use file's content_type
        final_content_type = content_type or file.content_type

        # Upload to GCS
        object_info = client.upload_bytes(
            data=file_contents,
            key=key,
            content_type=final_content_type,
        )

        return object_info_to_response(object_info)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {exc}",
        ) from exc


@app.get("/download/{key:path}", tags=["Storage"])
async def download_file(
    key: str,
    token: Annotated[str, Depends(verify_token)],
    client: Annotated[GCPCloudStorageClient, Depends(get_storage_client)],
) -> Response:
    """Download a file from cloud storage.

    Requires authentication via Bearer token.

    Args:
        key: Object key/path to download.
        token: Validated access token.
        client: GCP storage client.

    Returns:
        File contents as streaming response.

    Raises:
        HTTPException: If file not found or download fails.
    """
    try:
        # Download file bytes
        file_bytes = client.download_bytes(key=key)

        # Get object info for content type
        obj_info = client.head(key=key)
        content_type = obj_info.content_type if obj_info else "application/octet-stream"

        return Response(
            content=file_bytes,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{key.rsplit("/", maxsplit=1)[-1]}"',
            },
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {key}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download file: {exc}",
        ) from exc


@app.get("/list", response_model=ListResponse, tags=["Storage"])
async def list_objects(
    prefix: Annotated[str, Query(description="Prefix filter for object keys")] = "",
    token: str = Depends(verify_token),
    client: GCPCloudStorageClient = Depends(get_storage_client),
) -> ListResponse:
    """List objects in cloud storage with optional prefix filter.

    Requires authentication via Bearer token.

    Args:
        prefix: Filter objects by key prefix.
        token: Validated access token.
        client: GCP storage client.

    Returns:
        List of objects matching the prefix.

    Raises:
        HTTPException: If listing fails.
    """
    try:
        objects = client.list(prefix=prefix)
        return ListResponse(
            objects=[object_info_to_response(obj) for obj in objects],
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list objects: {exc}",
        ) from exc


@app.delete("/delete/{key:path}", status_code=status.HTTP_204_NO_CONTENT, tags=["Storage"])
async def delete_object(
    key: str,
    token: Annotated[str, Depends(verify_token)],
    client: Annotated[GCPCloudStorageClient, Depends(get_storage_client)],
) -> None:
    """Delete an object from cloud storage.

    Requires authentication via Bearer token.

    Args:
        key: Object key/path to delete.
        token: Validated access token.
        client: GCP storage client.

    Raises:
        HTTPException: If file not found or deletion fails.
    """
    try:
        client.delete(key=key)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {key}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete file: {exc}",
        ) from exc


@app.get("/head/{key:path}", response_model=ObjectInfoResponse, tags=["Storage"])
async def head_object(
    key: str,
    token: Annotated[str, Depends(verify_token)],
    client: Annotated[GCPCloudStorageClient, Depends(get_storage_client)],
) -> ObjectInfoResponse:
    """Get metadata for an object without downloading its contents.

    Requires authentication via Bearer token.

    Args:
        key: Object key/path to query.
        token: Validated access token.
        client: GCP storage client.

    Returns:
        Object metadata.

    Raises:
        HTTPException: If object not found or query fails.
    """
    try:
        obj_info = client.head(key=key)
        if obj_info is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Object not found: {key}",
            )
        return object_info_to_response(obj_info)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get object metadata: {exc}",
        ) from exc


# ============================================================================
# Error Handlers
# ============================================================================


@app.exception_handler(404)
async def not_found_handler(request: Any, exc: Any) -> Response:
    """Handle 404 errors."""
    return Response(
        status_code=404,
        content='{"error": "Not Found", "detail": "The requested resource was not found"}',
        media_type="application/json",
    )


@app.exception_handler(500)
async def internal_error_handler(request: Any, exc: Any) -> Response:
    """Handle 500 errors."""
    return Response(
        status_code=500,
        content='{"error": "Internal Server Error", "detail": "An unexpected error occurred"}',
        media_type="application/json",
    )
