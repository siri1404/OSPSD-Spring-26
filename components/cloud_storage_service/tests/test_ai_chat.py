"""Unit tests for AI chat endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from ai_client_api import AIResponse
from cloud_storage_api.exceptions import (
    AuthenticationError,
    ObjectNotFoundError,
    StorageBackendError,
)

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


@pytest.mark.unit
def test_ai_chat_returns_response(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_get_ai_client: MagicMock,
) -> None:
    """/ai/chat returns 200 with response and action_taken."""
    response = client.post(
        "/ai/chat",
        json={"prompt": "list my files"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["response"] == "AI response"
    assert data["action_taken"] == "list_files"


@pytest.mark.unit
def test_ai_chat_requires_auth(client: TestClient) -> None:
    """/ai/chat without auth header returns 401."""
    response = client.post("/ai/chat", json={"prompt": "list my files"})
    assert response.status_code == 401


@pytest.mark.unit
def test_ai_chat_with_invalid_token(client: TestClient) -> None:
    """/ai/chat with an unrecognized token returns 401."""
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
    """/ai/chat returns 500 when the AI client raises RuntimeError."""
    mock_ai_client.send_message_with_metadata.side_effect = RuntimeError("storage failed")

    response = client.post(
        "/ai/chat",
        json={"prompt": "test"},
        headers=auth_headers,
    )

    assert response.status_code == 500
    assert "storage failed" in response.json()["detail"]


@pytest.mark.unit
def test_ai_chat_with_container_passes_context(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_get_ai_client: MagicMock,
) -> None:
    """/ai/chat with X-Container header passes container in context."""
    headers = {**auth_headers, "X-Container": "my-bucket"}
    response = client.post(
        "/ai/chat",
        json={"prompt": "list files"},
        headers=headers,
    )

    assert response.status_code == 200
    mock_ai_client.send_message_with_metadata.assert_called_once()
    kwargs = mock_ai_client.send_message_with_metadata.call_args.kwargs
    assert kwargs["context"]["container"] == "my-bucket"


@pytest.mark.unit
def test_ai_chat_without_container_passes_none_context(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_get_ai_client: MagicMock,
) -> None:
    """/ai/chat without X-Container header passes context=None."""
    response = client.post(
        "/ai/chat",
        json={"prompt": "list files"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    mock_ai_client.send_message_with_metadata.assert_called_once()
    kwargs = mock_ai_client.send_message_with_metadata.call_args.kwargs
    assert kwargs["context"] is None


@pytest.mark.unit
def test_ai_chat_object_not_found_returns_404(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_get_ai_client: MagicMock,
) -> None:
    """/ai/chat returns 404 when ObjectNotFoundError is raised."""
    mock_ai_client.send_message_with_metadata.side_effect = ObjectNotFoundError("missing file")

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
    """/ai/chat returns 502 when StorageBackendError is raised."""
    mock_ai_client.send_message_with_metadata.side_effect = StorageBackendError("backend down")

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
    """/ai/chat returns 401 when AuthenticationError is raised."""
    mock_ai_client.send_message_with_metadata.side_effect = AuthenticationError("bad creds")

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
    """/ai/chat triggers the chat notifier when one is configured."""
    from cloud_storage_service import main

    mock_notifier = MagicMock()
    main.app.dependency_overrides[main.get_chat_notification] = lambda: mock_notifier
    try:
        response = client.post(
            "/ai/chat",
            json={"prompt": "list my files"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert mock_notifier.notify.called
    finally:
        del main.app.dependency_overrides[main.get_chat_notification]


@pytest.mark.unit
def test_ai_chat_notification_includes_object_name_from_tool_args(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_ai_client: MagicMock,
    mock_get_ai_client: MagicMock,
) -> None:
    """/ai/chat surfaces tool_args.object_name in the notification message."""
    from cloud_storage_service import main

    mock_ai_client.send_message_with_metadata.return_value = AIResponse(
        text="Deleted report.pdf",
        action_taken="delete_file",
        tool_calls=["delete_file"],
        tool_args={"object_name": "report.pdf", "container": "my-bucket"},
    )

    mock_notifier = MagicMock()
    main.app.dependency_overrides[main.get_chat_notification] = lambda: mock_notifier
    try:
        response = client.post(
            "/ai/chat",
            json={"prompt": "delete report.pdf"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        mock_notifier.notify.assert_called_once()
        msg = mock_notifier.notify.call_args.args[0]
        assert "delete_file" in msg
        assert "report.pdf" in msg
    finally:
        del main.app.dependency_overrides[main.get_chat_notification]


@pytest.mark.unit
def test_ai_chat_notification_failure_does_not_fail_request(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_get_ai_client: MagicMock,
) -> None:
    """If the chat notifier raises, /ai/chat still returns 200."""
    from cloud_storage_service import main

    mock_notifier = MagicMock()
    mock_notifier.notify.side_effect = RuntimeError("chat down")
    main.app.dependency_overrides[main.get_chat_notification] = lambda: mock_notifier
    try:
        response = client.post(
            "/ai/chat",
            json={"prompt": "hello"},
            headers=auth_headers,
        )
        assert response.status_code == 200
    finally:
        del main.app.dependency_overrides[main.get_chat_notification]
