"""Test fixtures and configuration for cloud_storage_service tests."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator, Generator
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from ai_client_api import AIResponse
from fastapi.testclient import TestClient
from httpx import AsyncClient

# Set test environment variables before importing the app
os.environ["GOOGLE_OAUTH_CLIENT_ID"] = "test-client-id.apps.googleusercontent.com"
os.environ["GOOGLE_OAUTH_CLIENT_SECRET"] = "test-client-secret"
os.environ["GOOGLE_OAUTH_REDIRECT_URI"] = "http://localhost:8000/auth/callback"
os.environ["GCS_BUCKET_NAME"] = "test-bucket"
os.environ["GOOGLE_CLOUD_PROJECT"] = "test-project"
os.environ["DEV_AUTH_TOKEN"] = "dev-token-12345"
os.environ["ENVIRONMENT"] = "test"

# Import after setting env vars
from cloud_storage_service.main import app

# Development token for testing
DEV_TOKEN = "dev-token-12345"


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Create a test client for the FastAPI app.

    Yields:
        TestClient for making synchronous requests.
    """
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client for the FastAPI app.

    Yields:
        AsyncClient for making asynchronous requests.
    """
    from httpx import ASGITransport

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Get authorization headers with dev token.

    Returns:
        Dictionary with Authorization header.
    """
    return {"Authorization": f"Bearer {DEV_TOKEN}"}


@pytest.fixture
def mock_storage_client() -> Generator[MagicMock, None, None]:
    """Mock GCPCloudStorageClient for testing.

    Yields:
        Mocked GCPCloudStorageClient instance.
    """
    from cloud_storage_service import main

    mock_client = MagicMock()

    # Mock shared CloudStorageClient methods
    mock_object_info = MagicMock()
    mock_object_info.object_name = "test-key"
    mock_object_info.size_bytes = 100
    mock_object_info.integrity = "test-etag"
    mock_object_info.updated_at = datetime.now()
    mock_object_info.data_type = "text/plain"
    mock_object_info.metadata = {}

    def _mock_download_file(container: str, object_name: str, file_name: str) -> MagicMock:
        """Simulate provider download by writing bytes to requested local path."""
        _ = (container, object_name)
        Path(file_name).write_bytes(b"test content")
        return mock_object_info

    mock_client.upload_obj.return_value = mock_object_info
    mock_client.download_file.side_effect = _mock_download_file
    mock_client.get_file_info.return_value = mock_object_info
    mock_client.list_files.return_value = [mock_object_info]
    mock_client.delete_file.return_value = {"deleted": True, "version_id": None, "request_charged": None}

    # Override FastAPI dependency
    def mock_get_storage_client() -> MagicMock:
        return mock_client

    app.dependency_overrides[main.get_storage_client] = mock_get_storage_client

    yield mock_client

    # Clean up
    app.dependency_overrides.clear()


@pytest.fixture
def sample_file_data() -> bytes:
    """Sample file data for testing uploads.

    Returns:
        Sample file content as bytes.
    """
    return b"Hello, Cloud Storage! This is a test file."


@pytest.fixture
def sample_object_info() -> dict[str, str | int | None]:
    """Sample object info for testing responses.

    Returns:
        Dictionary representing object metadata.
    """
    return {
        "key": "test-uploads/sample.txt",
        "size_bytes": 42,
        "etag": "abc123def456",
        "updated_at": "2026-03-15T00:00:00Z",
        "content_type": "text/plain",
        "metadata": None,
    }


@pytest.fixture
def mock_ai_client() -> MagicMock:
    """Mock AiClientApi for testing.

    Returns:
        Mocked AiClientApi instance that returns AIResponse.
    """
    mock = MagicMock()
    mock.send_message.return_value = AIResponse(
        text="AI response",
        action_taken="list_files",
        tool_calls=["list_files"],
    )
    return mock


@pytest.fixture
def mock_get_ai_client(mock_ai_client: MagicMock) -> Generator[MagicMock, None, None]:
    """Override get_ai_client dependency with mock.

    Args:
        mock_ai_client: Mocked AiClientApi instance.

    Yields:
        Mocked AiClientApi instance.
    """
    from cloud_storage_service import main

    def _override() -> MagicMock:
        return mock_ai_client

    app.dependency_overrides[main.get_ai_client] = _override
    yield mock_ai_client
    del app.dependency_overrides[main.get_ai_client]


@pytest.fixture
def mock_chat_client() -> MagicMock:
    """Mock ChatClient from shared chat-client-api for testing.

    Returns:
        Mocked ChatClient instance that returns Message objects.
    """
    from chat_client_api import Message

    mock = MagicMock()
    # Mock send_message to return a Message dataclass
    mock.send_message.return_value = Message(
        message_id="msg_123",
        channel="general",
        text="Test notification",
        sender="cloud-storage-service",
        timestamp=datetime.now(),
    )
    return mock


@pytest.fixture
def mock_get_chat_notification(mock_chat_client: MagicMock) -> Generator[MagicMock, None, None]:
    """Override get_chat_notification dependency with mock.

    Args:
        mock_chat_client: Mocked ChatClient instance.

    Yields:
        Mocked ChatClient instance.
    """
    from chat_client_wrapper import ChatNotificationWrapper
    from cloud_storage_service import main

    def _override() -> ChatNotificationWrapper | None:
        try:
            return ChatNotificationWrapper(
                chat_client=mock_chat_client,
                channel_id="general",
            )
        except Exception:
            return None

    app.dependency_overrides[main.get_chat_notification] = _override
    yield mock_chat_client
    del app.dependency_overrides[main.get_chat_notification]
