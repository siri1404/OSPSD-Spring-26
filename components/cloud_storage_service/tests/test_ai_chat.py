"""Unit tests for AI chat endpoint."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from ai_client_api import AIResponse
from cloud_storage_api.exceptions import (
    AuthenticationError,
    ObjectNotFoundError,
    StorageBackendError,
)
from fastapi.testclient import TestClient  # noqa: TC002


@pytest.mark.unit
def test_ai_chat_returns_response(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_get_ai_client: MagicMock,
) -> None:
    """Test /ai/chat returns 200 with response and action_taken."""
    response = client.post(
        "/ai/chat",
        json={"prompt": "list my files"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert data["response"] == "AI response"
    assert "action_taken" in data
    assert data["action_taken"] == "list_files"


@pytest.mark.unit
def test_ai_chat_requires_auth(client: TestClient) -> None:
    """Test /ai/chat without auth header returns 401."""
    response = client.post(
        "/ai/chat",
        json={"prompt": "list my files"},
    )

    assert response.status_code == 401


@pytest.mark.unit
def test_ai_chat_with_invalid_token(client: TestClient) -> None:
    """Test /ai/chat with invalid token returns 401."""
    response = client.post(
        "/ai/chat",
        json={"prompt": "list my files"},
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401


@pytest.mark.unit
def test_ai_chat_propagates_runtime_error_as_500(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_get_ai_client: MagicMock,
) -> None:
    """Test /ai/chat returns 500 when send_message raises RuntimeError."""
    mock_ai_client.send_message.side_effect = RuntimeError("storage failed")

    response = client.post(
        "/ai/chat",
        json={"prompt": "test"},
        headers=auth_headers,
    )

    assert response.status_code == 500
    data = response.json()
    assert "storage failed" in data["detail"]


@pytest.mark.unit
def test_ai_chat_with_container_passes_context(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_get_ai_client: MagicMock,
) -> None:
    """Test /ai/chat with container passes context to send_message."""
    headers = {**auth_headers, "X-Container": "my-bucket"}
    response = client.post(
        "/ai/chat",
        json={"prompt": "list files"},
        headers=headers,
    )

    assert response.status_code == 200
    mock_ai_client.send_message.assert_called_once()
    call_args = mock_ai_client.send_message.call_args
    assert call_args[1]["context"]["container"] == "my-bucket"


@pytest.mark.unit
def test_ai_chat_without_container_passes_empty_context(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_get_ai_client: MagicMock,
) -> None:
    """Test /ai/chat without container (no X-Container header) passes None context."""
    response = client.post(
        "/ai/chat",
        json={"prompt": "list files"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    mock_ai_client.send_message.assert_called_once()
    call_args = mock_ai_client.send_message.call_args
    # Context should be None when empty (no X-Container header)
    context = call_args[1]["context"]
    assert context is None


@pytest.mark.unit
def test_ai_chat_object_not_found_returns_404(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_get_ai_client: MagicMock,
) -> None:
    """Test /ai/chat returns 404 when ObjectNotFoundError is raised."""
    mock_ai_client.send_message.side_effect = ObjectNotFoundError("missing file")

    response = client.post(
        "/ai/chat",
        json={"prompt": "test"},
        headers=auth_headers,
    )

    assert response.status_code == 404


@pytest.mark.unit
def test_ai_chat_storage_backend_error_returns_502(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_get_ai_client: MagicMock,
) -> None:
    """Test /ai/chat returns 502 when StorageBackendError is raised."""
    mock_ai_client.send_message.side_effect = StorageBackendError("backend down")

    response = client.post(
        "/ai/chat",
        json={"prompt": "test"},
        headers=auth_headers,
    )

    assert response.status_code == 502


@pytest.mark.unit
def test_ai_chat_auth_error_returns_401(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_get_ai_client: MagicMock,
) -> None:
    """Test /ai/chat returns 401 when AuthenticationError is raised."""
    mock_ai_client.send_message.side_effect = AuthenticationError("bad creds")

    response = client.post(
        "/ai/chat",
        json={"prompt": "test"},
        headers=auth_headers,
    )

    assert response.status_code == 401


@pytest.mark.unit
def test_ai_chat_triggers_notification(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_get_ai_client: MagicMock,
) -> None:
    """Test that /ai/chat triggers chat notification when available."""
    from cloud_storage_service import main

    mock_notifier = MagicMock()

    def _override() -> MagicMock:
        return mock_notifier

    # Override dependency for this test
    main.app.dependency_overrides[main.get_chat_notification] = _override
    try:
        response = client.post(
            "/ai/chat",
            json={"prompt": "list my files"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        # Ensure notify was called with a message string
        assert mock_notifier.notify.called
    finally:
        del main.app.dependency_overrides[main.get_chat_notification]


@pytest.mark.unit
def test_ai_chat_triggers_notification_with_object_name(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_get_ai_client: MagicMock,
) -> None:
    """Test that /ai/chat includes object_name in notification when tool_args provided."""
    from cloud_storage_service import main

    # Arrange: mock AI response with populated tool_args
    mock_ai_client.send_message.return_value = AIResponse(
        text="Deleted report.pdf",
        action_taken="delete_file",
        tool_calls=["delete_file"],
        tool_args={"object_name": "report.pdf", "container": "my-bucket"},
    )

    mock_notifier = MagicMock()

    def _override() -> MagicMock:
        return mock_notifier

    main.app.dependency_overrides[main.get_chat_notification] = _override
    try:
        response = client.post(
            "/ai/chat",
            json={"prompt": "delete report.pdf"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        mock_notifier.notify.assert_called_once()
        msg = mock_notifier.notify.call_args[0][0]
        # Verify the notification contains the action and object name
        assert "delete_file" in msg
        assert "report.pdf" in msg  # Proves tool_args.object_name flowed through
    finally:
        del main.app.dependency_overrides[main.get_chat_notification]
