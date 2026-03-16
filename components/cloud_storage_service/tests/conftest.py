"""Test fixtures and configuration for cloud_storage_service tests."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator, Generator
from datetime import datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

if TYPE_CHECKING:
    from collections.abc import Generator


# Set test environment variables before importing the app
os.environ["GOOGLE_OAUTH_CLIENT_ID"] = "test-client-id.apps.googleusercontent.com"
os.environ["GOOGLE_OAUTH_CLIENT_SECRET"] = "test-client-secret"
os.environ["GOOGLE_OAUTH_REDIRECT_URI"] = "http://localhost:8000/auth/callback"
os.environ["GCS_BUCKET_NAME"] = "test-bucket"
os.environ["GOOGLE_CLOUD_PROJECT"] = "test-project"
os.environ["DEV_AUTH_TOKEN"] = "dev-token-12345"

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

    # Mock upload_bytes
    mock_object_info = MagicMock()
    mock_object_info.key = "test-key"
    mock_object_info.size_bytes = 100
    mock_object_info.etag = "test-etag"
    mock_object_info.updated_at = datetime.now()
    mock_object_info.content_type = "text/plain"
    mock_object_info.metadata = {}

    mock_client.upload_bytes.return_value = mock_object_info
    mock_client.download_bytes.return_value = b"test content"
    mock_client.head.return_value = mock_object_info
    mock_client.list.return_value = [mock_object_info]
    mock_client.delete.return_value = None

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
