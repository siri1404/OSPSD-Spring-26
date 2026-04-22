"""Test configuration for tests/ directory.

This module imports shared fixtures from the component tests,
making them available to all tests in tests/ and its subdirectories.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest

# Import all fixtures from the cloud_storage_service component conftest
from components.cloud_storage_service.tests.conftest import (  # type: ignore[attr-defined]
    app,
    async_client,
    auth_headers,
    client,
    mock_ai_client,
    mock_chat_client,
    mock_get_ai_client,
    mock_get_chat_notification,
    mock_storage_client,
    sample_file_data,
    sample_object_info,
)

__all__ = [
    "app",
    "async_client",
    "auth_headers",
    "client",
    "mock_ai_client",
    "mock_chat_client",
    "mock_get_ai_client",
    "mock_get_chat_notification",
    "mock_storage_client",
    "sample_file_data",
    "sample_object_info",
]


@pytest.fixture(autouse=True)
def _apply_mocks(
    mock_get_ai_client: object,
    mock_get_chat_notification: object,
) -> None:
    """Automatically apply AI and chat mocks to all tests in tests/ directory.

    This ensures dependency overrides are active for every test.

    Args:
        mock_get_ai_client: Mocked AI client fixture.
        mock_get_chat_notification: Mocked chat notification fixture.
    """
