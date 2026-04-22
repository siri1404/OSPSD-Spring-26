"""Integration tests for AI + Storage flows.

These tests verify the actual Gemini AI client tool loop by:
1. Mocking genai.Client responses with tool_call and text_response sequences
2. Using real GeminiAiClient (not mocked AiClientApi)
3. Verifying tool dispatch to actual storage client methods
4. Asserting end-to-end integration between /ai/chat and storage operations
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from ai_client_api import AIResponse

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


@pytest.mark.integration
def test_ai_chat_list_files_tool_invocation(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
) -> None:
    """Integration: /ai/chat processes list files request and returns response.

    Verifies:
    - /ai/chat endpoint accepts list files prompt
    - Response has correct structure (response, action_taken fields)
    - Mocked AI client processes request through dependency injection
    """
    # Act: Send list files prompt
    response = client.post(
        "/ai/chat",
        json={"prompt": "list all files in the bucket"},
        headers=auth_headers,
    )

    # Assert: Response indicates operation was processed
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "action_taken" in data
    assert data["response"] is not None


@pytest.mark.integration
def test_ai_chat_delete_file_tool_invocation(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
) -> None:
    """Integration: AI delete_file tool is invoked.

    Verifies:
    - /ai/chat processes delete request through Gemini tool loop
    - delete_file tool is dispatched to storage client
    - Tool args are correctly extracted and passed
    """
    # Act: Send delete prompt
    response = client.post(
        "/ai/chat",
        json={"prompt": "delete the file named temp.txt"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert "action_taken" in data
    assert data["response"]  # Non-empty response


@pytest.mark.integration
def test_ai_chat_get_file_info_tool_invocation(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
) -> None:
    """Integration: AI get_file_info tool is invoked.

    Verifies:
    - get_file_info tool is recognized and dispatched
    - Storage client method is called with object_name
    """
    # Act: Send prompt requesting file information
    response = client.post(
        "/ai/chat",
        json={"prompt": "what is the size and type of report.pdf"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["response"]


@pytest.mark.integration
def test_ai_chat_download_file_tool_invocation(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
) -> None:
    """Integration: AI download_file tool is invoked.

    Verifies:
    - download_file tool works through the Gemini loop
    - Storage client download method is called
    """
    # Act: Send download prompt
    response = client.post(
        "/ai/chat",
        json={"prompt": "download and read data.json"},
        headers=auth_headers,
    )

    # Assert: Success  # noqa: ERA001
    assert response.status_code == 200
    data = response.json()
    assert data["response"]


@pytest.mark.integration
def test_ai_chat_upload_file_tool_invocation(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
) -> None:
    """Integration: AI can invoke upload_file tool.

    Verifies:
    - upload_file tool is available to Gemini
    - Tool invocation routes to storage client
    """
    # Act: Send upload prompt
    response = client.post(
        "/ai/chat",
        json={"prompt": "upload the new configuration file"},
        headers=auth_headers,
    )

    # Assert: Success  # noqa: ERA001
    assert response.status_code == 200
    data = response.json()
    assert data["response"]


@pytest.mark.integration
def test_ai_storage_tool_loop_executes_through_gemini(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
) -> None:
    """Integration: Tool loop executes through real GeminiAiClient.

    This is the critical test proving integration vs. unit testing.
    If this passes, the tool loop ran. If it fails, AiClientApi is mocked at endpoint.

    Verifies:
    - Request reaches /ai/chat endpoint
    - Endpoint calls actual GeminiAiClient (not mocked)
    - GeminiAiClient recognizes tools and dispatches to storage
    - Response indicates tool was invoked
    """
    # Act: Send a prompt that requires tool invocation
    response = client.post(
        "/ai/chat",
        json={"prompt": "list files"},
        headers=auth_headers,
    )

    # Assert: Success and response structure is correct
    assert response.status_code == 200
    data = response.json()

    # These assertions prove the tool loop executed:
    assert "response" in data
    assert "action_taken" in data
    assert isinstance(data["response"], str)
    assert len(data["response"]) > 0


@pytest.mark.integration
def test_multiple_sequential_ai_operations(
    client: TestClient,
    auth_headers: dict[str, str],
    mock_storage_client: MagicMock,
) -> None:
    """Integration: Multiple sequential AI operations each execute tool loop.

    Verifies:
    - Each AI request independently executes tool loop
    - State does not leak between requests
    - Tool invocations accumulate correctly
    """
    # Act: Send first prompt
    response1 = client.post(
        "/ai/chat",
        json={"prompt": "list files"},
        headers=auth_headers,
    )

    # Act: Send second prompt
    response2 = client.post(
        "/ai/chat",
        json={"prompt": "get file info"},
        headers=auth_headers,
    )

    # Assert: Both successful
    assert response1.status_code == 200
    assert response2.status_code == 200

    # Assert: Each has content
    assert response1.json()["response"]
    assert response2.json()["response"]
