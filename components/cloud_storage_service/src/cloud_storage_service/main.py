"""FastAPI service for cloud storage operations with OAuth 2.0 authentication."""

from __future__ import annotations

import logging
import os
import secrets
import tempfile
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import anyio
import httpx
from ai_client_api import AiClientApi, AIResponse
from chat_client_wrapper import ChatNotificationWrapper
from chat_client_wrapper.notifications import NotificationMessages
from cloud_storage_api import CloudStorageClient, ObjectInfo  # noqa: TC002
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
from fastapi import (
    Body,
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import PlainTextResponse, Response
from fastapi.security import HTTPAuthorizationCredentials  # noqa: TC002
from gcp_client_impl import GCPCloudStorageClient
from gemini_ai_client_impl import GeminiAiClient, ToolLoopExhaustedError
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from .auth import (
    AuthConfig,
    build_oauth_url,
    exchange_code_for_token,
    get_auth_config,
    security,
    verify_token,
)
from .middleware.telemetry import (
    PrometheusMiddleware,
    ai_tool_calls_total,
)
from .models import (
    HealthResponse,
    ListResponse,
    OAuthCallbackResponse,
    OAuthLoginResponse,
    ObjectInfoResponse,
)
from .sessions import (
    active_sessions,
    pending_oauth_states,
)

if TYPE_CHECKING:
    from chat_client_api import ChatClient


# ---------------------------------------------------------------------------
# Optional .env loading (development convenience only)
# ---------------------------------------------------------------------------


def load_dev_env() -> None:
    """Load .env in development. In production, env vars come from the platform."""
    if os.getenv("ENVIRONMENT", "production") not in ("development", "test"):
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    env_path = Path(__file__).resolve().parents[4] / ".env"
    if env_path.exists():
        load_dotenv(env_path)


load_dev_env()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Required configuration
# ---------------------------------------------------------------------------

GCS_BUCKET = os.getenv("GCS_BUCKET_NAME")
if not GCS_BUCKET:
    msg = "GCS_BUCKET_NAME environment variable must be set."
    raise RuntimeError(msg)

# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Cloud Storage Service API",
    description=(
        "RESTful API for cloud storage operations with OAuth 2.0 "
        "authentication. Returns the shared cross-team ObjectInfo contract."
    ),
    version="1.0.0",
)
app.add_middleware(PrometheusMiddleware)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def resolve_container(container: str | None) -> str:
    """Return the request container or the configured default bucket."""
    return container or GCS_BUCKET  # type: ignore[return-value]
    # GCS_BUCKET is non-None — the startup check above guarantees it.


class UploadStream(BytesIO):
    """BytesIO carrying optional MIME type metadata for provider uploads."""

    content_type: str | None = None


def object_info_to_response(obj: ObjectInfo) -> ObjectInfoResponse:
    """Convert the shared-API ObjectInfo to the response model.

    Per peer-review #1, the response shape now mirrors the shared cross-team
    ObjectInfo contract (object_name, integrity, data_type, ...) instead of
    the legacy v0 shape (key, etag, content_type).
    """
    return ObjectInfoResponse(
        object_name=obj.object_name,
        size_bytes=obj.size_bytes,
        integrity=obj.integrity,
        data_type=obj.data_type,
        updated_at=obj.updated_at,
        version_id=obj.version_id,
        encryption=obj.encryption,
        storage_tier=obj.storage_tier,
        metadata=dict(obj.metadata) if obj.metadata else None,
    )


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_storage_client(
    token: Annotated[str | None, Depends(verify_token)],
) -> CloudStorageClient:
    """Build a GCP storage client.

    When verify_token returns None (dev path), fall back to ADC.
    Otherwise use the resolved provider OAuth token.
    """
    if token is None:
        return GCPCloudStorageClient()
    return GCPCloudStorageClient(oauth_token=token)


def get_ai_client(
    storage_client: Annotated[CloudStorageClient, Depends(get_storage_client)],
) -> AiClientApi:
    """Build a Gemini AI client with the storage client injected."""
    return GeminiAiClient(storage_client=storage_client)


# Singleton chat client, initialized lazily and clearable by tests.
_chat_client_singleton: ChatClient | None = None
_chat_client_initialized: bool = False


def _get_cached_chat_client() -> ChatClient | None:
    """Return a cached SlackChatClient, or None if not configured."""
    global _chat_client_singleton, _chat_client_initialized  # noqa: PLW0603
    if _chat_client_initialized:
        return _chat_client_singleton

    _chat_client_initialized = True
    try:
        from .slack_adapter import SlackChatClient

        _chat_client_singleton = SlackChatClient()
    except (ValueError, RuntimeError) as exc:
        logger.warning("Could not initialize Slack chat client: %s", exc)
        _chat_client_singleton = None
    return _chat_client_singleton


def get_chat_notification() -> ChatNotificationWrapper | None:
    """Build a chat notifier, or None if Slack isn't configured."""
    channel_id = os.getenv("CHAT_CHANNEL_ID")
    if not channel_id:
        return None

    chat_client = _get_cached_chat_client()
    if not chat_client:
        return None

    try:
        return ChatNotificationWrapper(
            chat_client=chat_client,
            channel_id=channel_id,
        )
    except (ValueError, RuntimeError) as exc:
        logger.warning("Could not initialize chat notifications: %s", exc)
        return None


def safe_notify(
    chat_notification: ChatNotificationWrapper | None,
    msg: str,
) -> None:
    """Send a chat notification, swallowing transport errors."""
    if chat_notification is None:
        return
    try:
        chat_notification.notify(msg)
    except (httpx.HTTPError, ValueError, RuntimeError) as exc:
        logger.warning("Failed to send chat notification: %s", exc)


# ---------------------------------------------------------------------------
# Health & root
# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """Health check with timestamp."""
    return HealthResponse(
        status="healthy",
        service="cloud-storage-service",
        timestamp=datetime.now(tz=UTC),
    )


@app.get("/", tags=["Health"])
async def root() -> dict[str, str]:
    """Root status message."""
    return {"message": "Cloud Storage Service is running"}


# ---------------------------------------------------------------------------
# OAuth 2.0 endpoints
# ---------------------------------------------------------------------------


@app.post("/auth/login", response_model=OAuthLoginResponse, tags=["Authentication"])
async def oauth_login(
    config: Annotated[AuthConfig, Depends(get_auth_config)],
) -> OAuthLoginResponse:
    """Initiate the OAuth 2.0 login flow with Google."""
    auth_url, state = build_oauth_url(config)
    pending_oauth_states.add(state)
    return OAuthLoginResponse(auth_url=auth_url)


@app.get("/auth/callback", response_model=OAuthCallbackResponse, tags=["Authentication"])
async def oauth_callback(
    code: Annotated[str, Query(description="Authorization code from Google")],
    state: Annotated[str, Query(description="State parameter for CSRF protection")],
    config: Annotated[AuthConfig, Depends(get_auth_config)],
) -> OAuthCallbackResponse:
    """Handle Google's OAuth 2.0 callback and issue an opaque session token."""
    if state not in pending_oauth_states:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state parameter. Possible CSRF attack.",
        )

    try:
        token_data = await exchange_code_for_token(code, config)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to exchange code for token: {exc}",
        ) from exc

    provider_token = token_data["access_token"]

    # Pending state has served its CSRF-validation purpose.
    pending_oauth_states.discard(state)

    # Issue an opaque session ID; never expose the provider token to the client.
    opaque_session_id = secrets.token_urlsafe(32)
    active_sessions[opaque_session_id] = provider_token

    return OAuthCallbackResponse(
        access_token=opaque_session_id,
        token_type="bearer",  # noqa: S106 - OAuth2 token type, not a credential
        expires_in=token_data.get("expires_in"),
    )


@app.post(
    "/auth/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Authentication"],
)
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> None:
    """Invalidate the current session token."""
    await verify_token(credentials)

    raw_token = credentials.credentials
    if raw_token in active_sessions:
        del active_sessions[raw_token]


# ---------------------------------------------------------------------------
# Storage endpoints
# ---------------------------------------------------------------------------


@app.post("/upload", response_model=ObjectInfoResponse, tags=["Storage"])
async def upload_file(  # noqa: PLR0913 - FastAPI DI forces wide signature
    file: Annotated[UploadFile, File(description="File to upload")],
    key: Annotated[str, Form(description="Object key/path in storage")],
    client: Annotated[CloudStorageClient, Depends(get_storage_client)],
    content_type: Annotated[str | None, Form(description="MIME type of the content")] = None,
    container: Annotated[str | None, Query(description="Storage container or bucket name")] = None,
    chat_notification: Annotated[ChatNotificationWrapper | None, Depends(get_chat_notification)] = None,
) -> ObjectInfoResponse:
    """Upload a file to cloud storage."""
    file_contents = await file.read()
    effective_container = resolve_container(container)

    upload_stream = UploadStream(file_contents)
    upload_stream.content_type = content_type or file.content_type

    try:
        object_info = client.upload_obj(
            container=effective_container,
            file_obj=upload_stream,
            remote_path=key,
        )
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
        ) from exc
    except ContainerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Container not found",
        ) from exc
    except InvalidContainerError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid container",
        ) from exc
    except InvalidObjectNameError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid object name",
        ) from exc
    except InvalidFileObjectError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid file object",
        ) from exc
    except StorageBackendError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Storage backend error: {exc}",
        ) from exc

    safe_notify(
        chat_notification,
        NotificationMessages.file_uploaded(
            container=effective_container,
            object_name=key,
            size_bytes=object_info.size_bytes,
        ),
    )

    return object_info_to_response(object_info)


@app.get("/download/{key:path}", tags=["Storage"])
async def download_file(
    key: str,
    client: Annotated[CloudStorageClient, Depends(get_storage_client)],
    container: Annotated[str | None, Query(description="Storage container or bucket name")] = None,
) -> Response:
    """Download a file from cloud storage."""
    effective_container = resolve_container(container)

    try:
        obj_info = client.get_file_info(
            container=effective_container,
            object_name=key,
        )
    except ObjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {key}",
        ) from exc
    except ContainerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Container not found",
        ) from exc
    except (InvalidContainerError, InvalidObjectNameError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
        ) from exc
    except StorageBackendError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Storage backend error: {exc}",
        ) from exc

    content_type = obj_info.data_type or "application/octet-stream"

    # mkstemp avoids the open-then-reopen race that NamedTemporaryFile
    # causes on Windows.
    fd, tmp_path = tempfile.mkstemp()
    os.close(fd)
    try:
        try:
            client.download_file(
                container=effective_container,
                object_name=key,
                file_name=tmp_path,
            )
        except ObjectNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found: {key}",
            ) from exc
        except LocalFileAccessError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Local file access error: {exc}",
            ) from exc
        except StorageBackendError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Storage backend error: {exc}",
            ) from exc

        file_bytes = await anyio.Path(tmp_path).read_bytes()
    finally:
        await anyio.Path(tmp_path).unlink(missing_ok=True)

    filename = key.rsplit("/", maxsplit=1)[-1]
    return Response(
        content=file_bytes,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/list", response_model=ListResponse, tags=["Storage"])
async def list_objects(
    client: Annotated[CloudStorageClient, Depends(get_storage_client)],
    prefix: Annotated[str, Query(description="Prefix filter for object keys")] = "",
    container: Annotated[str | None, Query(description="Storage container or bucket name")] = None,
) -> ListResponse:
    """List objects in cloud storage with an optional prefix filter."""
    effective_container = resolve_container(container)

    try:
        objects = client.list_files(
            container=effective_container,
            prefix=prefix,
        )
    except ContainerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Container not found",
        ) from exc
    except InvalidContainerError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid container",
        ) from exc
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
        ) from exc
    except StorageBackendError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Storage backend error: {exc}",
        ) from exc

    return ListResponse(
        objects=[object_info_to_response(obj) for obj in objects],
    )


@app.delete(
    "/delete/{key:path}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Storage"],
)
async def delete_object(
    key: str,
    client: Annotated[CloudStorageClient, Depends(get_storage_client)],
    container: Annotated[str | None, Query(description="Storage container or bucket name")] = None,
    chat_notification: Annotated[ChatNotificationWrapper | None, Depends(get_chat_notification)] = None,
) -> None:
    """Delete an object from cloud storage."""
    effective_container = resolve_container(container)

    try:
        client.delete_file(container=effective_container, object_name=key)
    except ObjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {key}",
        ) from exc
    except ContainerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Container not found",
        ) from exc
    except (InvalidContainerError, InvalidObjectNameError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
        ) from exc
    except StorageBackendError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Storage backend error: {exc}",
        ) from exc

    safe_notify(
        chat_notification,
        NotificationMessages.file_deleted(
            container=effective_container,
            object_name=key,
        ),
    )


@app.get(
    "/head/{key:path}",
    response_model=ObjectInfoResponse,
    tags=["Storage"],
)
async def head_object(
    key: str,
    client: Annotated[CloudStorageClient, Depends(get_storage_client)],
    container: Annotated[str | None, Query(description="Storage container or bucket name")] = None,
) -> ObjectInfoResponse:
    """Get metadata for an object without downloading its contents."""
    effective_container = resolve_container(container)

    try:
        obj_info = client.get_file_info(
            container=effective_container,
            object_name=key,
        )
    except ObjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Object not found: {key}",
        ) from exc
    except ContainerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Container not found",
        ) from exc
    except (InvalidContainerError, InvalidObjectNameError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
        ) from exc
    except StorageBackendError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Storage backend error: {exc}",
        ) from exc

    return object_info_to_response(obj_info)


# ---------------------------------------------------------------------------
# AI chat endpoint
# ---------------------------------------------------------------------------


@app.post("/ai/chat", tags=["AI"])
async def ai_chat(
    ai_client: Annotated[AiClientApi, Depends(get_ai_client)],
    prompt: Annotated[str, Body(embed=True, description="Natural language prompt")],
    x_container: Annotated[str | None, Header(alias="X-Container")] = None,
    chat_notification: Annotated[ChatNotificationWrapper | None, Depends(get_chat_notification)] = None,
) -> dict[str, str | None]:
    """Natural-language interface to cloud storage operations.

    Accepts a plain-English prompt and returns a human-readable response.
    The AI may call appropriate storage tools to fulfill the request.
    A default container can be supplied via the X-Container header.
    """
    context: dict[str, object] | None = {"container": x_container} if x_container else None

    # Concrete clients expose send_message_with_metadata for telemetry.
    # Fall back to the slim contract if the impl only implements send_message.
    metadata_method = getattr(ai_client, "send_message_with_metadata", None)
    try:
        if callable(metadata_method):
            ai_response: AIResponse = metadata_method(prompt=prompt, context=context)
        else:
            text = ai_client.send_message(prompt=prompt, context=context)
            ai_response = AIResponse(text=text, action_taken=None, tool_calls=[])
    except ToolLoopExhaustedError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=(
                "The AI could not complete the request after exhausting its tool-calling loop. "
                "The request may be too complex or the AI got stuck in a repetitive pattern."
            ),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except ObjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    except StorageBackendError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    for tool_name in ai_response.tool_calls:
        ai_tool_calls_total.labels(tool_name=tool_name, status="success").inc()

    if chat_notification is not None:
        resolved_container = resolve_container(x_container)
        last_tool_args = ai_response.tool_args or {}
        object_name = last_tool_args.get("object_name") or last_tool_args.get("remote_path")
        max_chars = 5000
        truncated_chars = 100
        result_text = ai_response.text if len(ai_response.text) <= max_chars else ai_response.text[:truncated_chars] + "..."

        safe_notify(
            chat_notification,
            NotificationMessages.ai_action_performed(
                action=ai_response.action_taken or "request_processed",
                container=resolved_container,
                object_name=object_name,
                result=result_text,
            ),
        )

    return {
        "response": ai_response.text,
        "action_taken": ai_response.action_taken,
    }


# ---------------------------------------------------------------------------
# Metrics endpoint
# ---------------------------------------------------------------------------


@app.get(
    "/metrics",
    response_class=PlainTextResponse,
    tags=["Monitoring"],
)
async def metrics() -> PlainTextResponse:
    """Expose Prometheus metrics in text format."""
    return PlainTextResponse(
        content=generate_latest().decode("utf-8"),
        media_type=CONTENT_TYPE_LATEST,
    )
