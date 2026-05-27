"""Test fixtures and configuration for cloud_storage_service tests."""

from __future__ import annotations

import os

os.environ["GCS_BUCKET_NAME"] = "test-bucket"
from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from ai_client_api import AIResponse
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Test environment setup
# ---------------------------------------------------------------------------

# Set required env vars before importing the app (which validates them at startup)
os.environ.setdefault("GOOGLE_OAUTH_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
os.environ.setdefault("GOOGLE_OAUTH_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8000/auth/callback")
os.environ.setdefault("GCS_BUCKET_NAME", "test-bucket")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "test-project")
os.environ.setdefault("DEV_AUTH_TOKEN", "dev-token-12345")
os.environ.setdefault("ENVIRONMENT", "test")

# Import after setting env vars
from cloud_storage_service.main import app

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEV_TOKEN = "dev-token-12345"
FIXED_TIMESTAMP = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

# ---------------------------------------------------------------------------
# Session state cleanup
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clear_session_state() -> Generator[None, None, None]:
    """Ensure module-level session state doesn't leak between tests."""
    from cloud_storage_service.sessions import active_sessions, pending_oauth_states

    yield
    active_sessions.clear()
    pending_oauth_states.clear()


# ---------------------------------------------------------------------------
# HTTP clients
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Synchronous test client for the FastAPI app."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Asynchronous test client for the FastAPI app."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Authorization headers using the dev bearer token."""
    return {"Authorization": f"Bearer {DEV_TOKEN}"}


# ---------------------------------------------------------------------------
# Storage client mock
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_storage_client() -> Generator[MagicMock, None, None]:
    """Mock GCPCloudStorageClient overriding the get_storage_client dependency."""
    from cloud_storage_service import main

    mock_client = MagicMock()

    mock_object_info = MagicMock()
    mock_object_info.object_name = "test-key"
    mock_object_info.size_bytes = 100
    mock_object_info.integrity = "test-etag"
    mock_object_info.data_type = "text/plain"
    mock_object_info.updated_at = FIXED_TIMESTAMP
    mock_object_info.version_id = None
    mock_object_info.encryption = None
    mock_object_info.storage_tier = "STANDARD"
    mock_object_info.metadata = {}

    def _mock_download_file(container: str, object_name: str, file_name: str) -> MagicMock:
        """Simulate provider download by writing bytes to the requested local path."""
        _ = object_name
        _ = container
        Path(file_name).write_bytes(b"test content")
        return mock_object_info

    mock_client.upload_obj.return_value = mock_object_info
    mock_client.download_file.side_effect = _mock_download_file
    mock_client.get_file_info.return_value = mock_object_info
    mock_client.list_files.return_value = [mock_object_info]
    mock_client.delete_file.return_value = {
        "deleted": True,
        "version_id": None,
        "request_charged": False,
    }

    def override() -> MagicMock:
        return mock_client

    app.dependency_overrides[main.get_storage_client] = override
    yield mock_client
    del app.dependency_overrides[main.get_storage_client]


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_file_data() -> bytes:
    """Sample file bytes for testing uploads."""
    return b"Hello, Cloud Storage! This is a test file."


@pytest.fixture
def sample_object_info() -> dict[str, str | int | None]:
    """Sample ObjectInfoResponse payload (matches the shared cross-team contract)."""
    return {
        "object_name": "test-uploads/sample.txt",
        "size_bytes": 42,
        "integrity": "abc123def456",
        "data_type": "text/plain",
        "updated_at": "2026-03-15T00:00:00Z",
        "version_id": None,
        "encryption": None,
        "storage_tier": "STANDARD",
        "metadata": None,
    }


# ---------------------------------------------------------------------------
# AI client mock
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_ai_client() -> MagicMock:
    """Mock AiClientApi covering both send_message and send_message_with_metadata."""
    mock = MagicMock()
    mock.send_message.return_value = "AI response"
    mock.send_message_with_metadata.return_value = AIResponse(
        text="AI response",
        action_taken="list_files",
        tool_calls=["list_files"],
        tool_args={"container": "test-bucket"},
    )
    return mock


@pytest.fixture
def mock_get_ai_client(
    mock_ai_client: MagicMock,
) -> Generator[MagicMock, None, None]:
    """Override the get_ai_client dependency."""
    from cloud_storage_service import main

    def override() -> MagicMock:
        return mock_ai_client

    app.dependency_overrides[main.get_ai_client] = override
    yield mock_ai_client
    del app.dependency_overrides[main.get_ai_client]


# ---------------------------------------------------------------------------
# Chat notification mock
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_chat_client() -> MagicMock:
    """Mock ChatClient returning a deterministic Message."""
    from chat_client_api import Message

    mock = MagicMock()
    mock.send_message.return_value = Message(
        message_id="msg_123",
        channel="general",
        text="Test notification",
        sender="cloud-storage-service",
        timestamp=FIXED_TIMESTAMP,
    )
    return mock


@pytest.fixture
def mock_get_chat_notification(
    mock_chat_client: MagicMock,
) -> Generator[MagicMock, None, None]:
    """Override the get_chat_notification dependency."""
    from chat_client_wrapper import ChatNotificationWrapper
    from cloud_storage_service import main

    def override() -> ChatNotificationWrapper:
        return ChatNotificationWrapper(
            chat_client=mock_chat_client,
            channel_id="general",
        )

    app.dependency_overrides[main.get_chat_notification] = override
    yield mock_chat_client
    del app.dependency_overrides[main.get_chat_notification]
