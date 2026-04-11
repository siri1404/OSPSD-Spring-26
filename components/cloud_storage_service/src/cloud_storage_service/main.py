"""FastAPI service for cloud storage operations with OAuth 2.0 authentication."""

from __future__ import annotations

import os
import secrets
import tempfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Annotated, Any

import anyio
from cloud_storage_api import CloudStorageClient
from cloud_storage_api.exceptions import (
    AuthenticationError,
    ContainerNotFoundError,
    InvalidContainerError,
    InvalidFileObjectError,
    InvalidObjectNameError,
    LocalFileAccessError,
    ObjectNotFoundError,
    StorageBackendError,
)
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials
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
    security,
    verify_token,
)
from cloud_storage_service.models import (
    HealthResponse,
    ListResponse,
    OAuthCallbackResponse,
    OAuthLoginResponse,
    ObjectInfoResponse,
)
from cloud_storage_service.sessions import active_sessions

# Initialize FastAPI application
app = FastAPI(
    title="Cloud Storage Service API",
    description="RESTful API for cloud storage operations with OAuth 2.0 authentication",
    version="1.0.0",
)

# Container used by storage operations.
GCS_BUCKET = os.getenv("GCS_BUCKET_NAME", "")


def _resolve_container(container: str | None) -> str:
    """Return the request container or the configured default bucket."""
    return container or GCS_BUCKET


class _UploadStream(BytesIO):
    """BytesIO carrying optional MIME type metadata for provider uploads."""

    content_type: str | None = None


def get_storage_client(token: Annotated[str, Depends(verify_token)]) -> CloudStorageClient:
    """Get GCP Cloud Storage client instance using verified provider token.

    The token passed here is already verified and resolved to a provider access token
    (either from session mapping, dev token, or direct provider token).

    Args:
        token: Verified provider access token (from verify_token dependency).

    Returns:
        Configured CloudStorageClient instance.
    """
    environment = os.getenv("ENVIRONMENT", "production")
    dev_token = os.getenv("DEV_AUTH_TOKEN")
    # If this is the dev token (already passed through verify_token), use default credentials
    if environment in ("development", "test") and dev_token and token == dev_token:
        return GCPCloudStorageClient()
    # Otherwise use the provided OAuth token (from session mapping or direct provider token)
    return GCPCloudStorageClient(oauth_token=token)


def object_info_to_response(obj: Any) -> ObjectInfoResponse:
    """Convert ObjectInfo to response model.

    Args:
        obj: ObjectInfo instance from gcp_client_impl.

    Returns:
        ObjectInfoResponse for API response.
    """
    return ObjectInfoResponse(
        key=obj.object_name,
        size_bytes=obj.size_bytes,
        etag=obj.integrity,
        updated_at=obj.updated_at,
        content_type=obj.data_type,
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


@app.get("/", tags=["Health"])
def root() -> dict[str, str]:
    """Return a root status message."""
    return {"message": "Client Storage Service is running"}


# ============================================================================
# OAuth 2.0 Authentication Endpoints
# ============================================================================


@app.post("/auth/login", response_model=OAuthLoginResponse, tags=["Authentication"])
async def oauth_login(config: Annotated[AuthConfig, Depends(get_auth_config)]) -> OAuthLoginResponse:
    """Initiate OAuth 2.0 login flow with Google.

    Generates an authorization URL for Google's OAuth consent screen.

    Returns:
        Response containing the authorization URL.
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

    Exchanges authorization code for provider access token and creates a service-owned session.

    Args:
        code: Authorization code from Google OAuth.
        state: State parameter for CSRF validation.
        config: OAuth configuration.

    Returns:
        Service-owned session token (opaque, not the provider token).

    Raises:
        HTTPException: If state is invalid or token exchange fails.
    """
    # Validate state parameter for CSRF protection
    if state not in active_sessions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state parameter. Possible CSRF attack.",
        )

    # Exchange code for provider access token
    try:
        token_data = await exchange_code_for_token(code, config)
        provider_token = token_data["access_token"]

        # Generate opaque service-owned session token
        opaque_session_id = secrets.token_urlsafe(32)

        # Store mapping: opaque_session_id -> provider_token
        active_sessions[opaque_session_id] = provider_token

        # Clean up state-based session (no longer needed)
        del active_sessions[state]

        return OAuthCallbackResponse(
            access_token=opaque_session_id,  # Return opaque token, not provider token
            token_type="bearer",  # noqa: S106 - Standard OAuth2 token type, not a password
            expires_in=token_data.get("expires_in"),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to exchange code for token: {exc}",
        ) from exc


@app.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT, tags=["Authentication"])
async def logout(credentials: HTTPAuthorizationCredentials = Depends(security)) -> None:
    """Logout by invalidating the session token.

    Removes the service-owned session token, effectively revoking access.

    Args:
        credentials: HTTP bearer credentials containing the raw token.

    Returns:
        204 No Content on success.
    """
    # Verify token first (raises 401 if invalid).
    await verify_token(credentials)

    # Remove by raw bearer token so opaque session IDs are actually invalidated.
    raw_token = credentials.credentials
    if raw_token in active_sessions:
        del active_sessions[raw_token]
    # If it's not a session token (e.g., dev token), logout is a no-op


# ============================================================================
# Cloud Storage Operation Endpoints
# ============================================================================


@app.post("/upload", response_model=ObjectInfoResponse, tags=["Storage"])
async def upload_file(  # noqa: PLR0913
    file: Annotated[UploadFile, File(description="File to upload")],
    key: Annotated[str, Form(description="Object key/path in storage")],
    content_type: Annotated[str | None, Form(description="MIME type of the content")] = None,
    token: str = Depends(verify_token),
    client: CloudStorageClient = Depends(get_storage_client),
    container: Annotated[str | None, Query(description="Storage container or bucket name")] = None,
) -> ObjectInfoResponse:
    """Upload a file to cloud storage.

    Requires authentication via Bearer token.

    Args:
        file: File to upload (multipart/form-data).
        key: Destination key/path in cloud storage.
        content_type: Optional MIME type.
        token: Validated access token.
        client: GCP storage client.
        container: Optional storage container or bucket override.

    Returns:
        Object metadata after successful upload.

    Raises:
        HTTPException: If upload fails.
    """
    try:
        # Read file contents
        file_contents = await file.read()
        effective_container = _resolve_container(container)

        # Upload to GCS
        upload_stream = _UploadStream(file_contents)
        upload_stream.content_type = content_type or file.content_type
        object_info = client.upload_obj(
            container=effective_container,
            file_obj=upload_stream,
            remote_path=key,
        )

        return object_info_to_response(object_info)
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed") from exc
    except ContainerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Container not found") from exc
    except InvalidContainerError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[{"loc": ["query", "container"], "msg": "Invalid container", "type": "value_error"}],
        ) from exc
    except InvalidObjectNameError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[{"loc": ["body", "key"], "msg": "Invalid object name", "type": "value_error"}],
        ) from exc
    except InvalidFileObjectError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[{"loc": ["body", "file"], "msg": "Invalid file object", "type": "value_error"}],
        ) from exc
    except StorageBackendError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Storage backend error: {exc}") from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {exc}",
        ) from exc


@app.get("/download/{key:path}", tags=["Storage"])
async def download_file(
    key: str,
    token: Annotated[str, Depends(verify_token)],
    client: Annotated[CloudStorageClient, Depends(get_storage_client)],
    container: Annotated[str | None, Query(description="Storage container or bucket name")] = None,
) -> Response:
    """Download a file from cloud storage.

    Requires authentication via Bearer token.

    Args:
        key: Object key/path to download.
        token: Validated access token.
        client: GCP storage client.
        container: Optional storage container or bucket override.

    Returns:
        File contents as streaming response.

    Raises:
        HTTPException: If file not found or download fails.
    """
    try:
        effective_container = _resolve_container(container)
        obj_info = client.get_file_info(container=effective_container, object_name=key)
        content_type = obj_info.data_type or "application/octet-stream"

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name

        try:
            client.download_file(container=effective_container, object_name=key, file_name=tmp_path)
            file_bytes = await anyio.Path(tmp_path).read_bytes()
        finally:
            await anyio.Path(tmp_path).unlink(missing_ok=True)

        return Response(
            content=file_bytes,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{key.rsplit("/", maxsplit=1)[-1]}"',
            },
        )
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed") from exc
    except ContainerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Container not found") from exc
    except InvalidContainerError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[{"loc": ["query", "container"], "msg": "Invalid container", "type": "value_error"}],
        ) from exc
    except InvalidObjectNameError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[{"loc": ["path", "key"], "msg": "Invalid object name", "type": "value_error"}],
        ) from exc
    except LocalFileAccessError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Local file access error: {exc}") from exc
    except StorageBackendError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Storage backend error: {exc}") from exc
    except ObjectNotFoundError as exc:
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
    client: CloudStorageClient = Depends(get_storage_client),
    container: Annotated[str | None, Query(description="Storage container or bucket name")] = None,
) -> ListResponse:
    """List objects in cloud storage with optional prefix filter.

    Requires authentication via Bearer token.

    Args:
        prefix: Filter objects by key prefix.
        token: Validated access token.
        client: GCP storage client.
        container: Optional storage container or bucket override.

    Returns:
        List of objects matching the prefix.

    Raises:
        HTTPException: If listing fails.
    """
    try:
        effective_container = _resolve_container(container)
        objects = client.list_files(container=effective_container, prefix=prefix)
        return ListResponse(
            objects=[object_info_to_response(obj) for obj in objects],
        )
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed") from exc
    except ContainerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Container not found") from exc
    except InvalidContainerError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[{"loc": ["query", "container"], "msg": "Invalid container", "type": "value_error"}],
        ) from exc
    except StorageBackendError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Storage backend error: {exc}") from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list objects: {exc}",
        ) from exc


@app.delete("/delete/{key:path}", status_code=status.HTTP_204_NO_CONTENT, tags=["Storage"])
async def delete_object(
    key: str,
    token: Annotated[str, Depends(verify_token)],
    client: Annotated[CloudStorageClient, Depends(get_storage_client)],
    container: Annotated[str | None, Query(description="Storage container or bucket name")] = None,
) -> None:
    """Delete an object from cloud storage.

    Requires authentication via Bearer token.

    Args:
        key: Object key/path to delete.
        token: Validated access token.
        client: GCP storage client.
        container: Optional storage container or bucket override.

    Raises:
        HTTPException: If file not found or deletion fails.
    """
    try:
        effective_container = _resolve_container(container)
        client.delete_file(container=effective_container, object_name=key)
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed") from exc
    except ContainerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Container not found") from exc
    except InvalidContainerError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[{"loc": ["query", "container"], "msg": "Invalid container", "type": "value_error"}],
        ) from exc
    except InvalidObjectNameError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[{"loc": ["path", "key"], "msg": "Invalid object name", "type": "value_error"}],
        ) from exc
    except ObjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {key}",
        ) from exc
    except StorageBackendError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Storage backend error: {exc}") from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete file: {exc}",
        ) from exc


@app.get("/head/{key:path}", response_model=ObjectInfoResponse, tags=["Storage"])
async def head_object(
    key: str,
    token: Annotated[str, Depends(verify_token)],
    client: Annotated[CloudStorageClient, Depends(get_storage_client)],
    container: Annotated[str | None, Query(description="Storage container or bucket name")] = None,
) -> ObjectInfoResponse:
    """Get metadata for an object without downloading its contents.

    Requires authentication via Bearer token.

    Args:
        key: Object key/path to query.
        token: Validated access token.
        client: GCP storage client.
        container: Optional storage container or bucket override.

    Returns:
        Object metadata.

    Raises:
        HTTPException: If object not found or query fails.
    """
    try:
        effective_container = _resolve_container(container)
        obj_info = client.get_file_info(container=effective_container, object_name=key)
        return object_info_to_response(obj_info)
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed") from exc
    except ContainerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Container not found") from exc
    except InvalidContainerError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[{"loc": ["query", "container"], "msg": "Invalid container", "type": "value_error"}],
        ) from exc
    except InvalidObjectNameError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[{"loc": ["path", "key"], "msg": "Invalid object name", "type": "value_error"}],
        ) from exc
    except ObjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Object not found: {key}",
        ) from exc
    except StorageBackendError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Storage backend error: {exc}") from exc
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
