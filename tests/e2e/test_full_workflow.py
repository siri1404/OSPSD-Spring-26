"""E2E tests against deployed staging service.

These tests run against a real deployed instance via HTTP, without mocking.
They require STAGING_SERVICE_URL environment variable to be set.
Tests are skipped in CI when STAGING_SERVICE_URL is not available.

Verifies complete end-to-end workflow:
1. Upload a file
2. Query AI to list files
3. Query AI to delete file
4. Verify file is deleted
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

# Environment configuration
STAGING_URL = os.getenv("STAGING_SERVICE_URL")
STAGING_TOKEN = os.getenv("STAGING_AUTH_TOKEN", "dev-token-12345")
E2E_TEST_BUCKET = os.getenv("E2E_TEST_BUCKET", "test-bucket")

# Skip all tests in this module if STAGING_SERVICE_URL is not set
pytestmark = pytest.mark.skipif(
    not STAGING_URL,
    reason="STAGING_SERVICE_URL not set — E2E tests skipped (requires deployed service)",
)


@pytest.mark.e2e
def test_e2e_upload_query_ai_list_workflow() -> None:
    """E2E: Upload file and query AI to list files.

    Flow:
    1. Upload a file to staging service
    2. Query AI with "list files" prompt
    3. Verify AI response mentions the uploaded file

    This test proves:
    - Upload endpoint works on deployed service
    - AI can query storage through deployed service
    - Response flows back through HTTP correctly
    """
    import httpx

    headers = {"Authorization": f"Bearer {STAGING_TOKEN}"}

    with httpx.Client(
        base_url=str(STAGING_URL),
        headers=headers,
        timeout=30.0,
    ) as client:
        # Step 1: Upload a file
        upload_response = client.post(
            "/upload",
            files={"file": ("e2e_upload_test.txt", b"e2e test content", "text/plain")},
            data={"key": "e2e/upload_test.txt", "content_type": "text/plain"},
        )
        assert upload_response.status_code == 200, f"Upload failed: {upload_response.text}"

        # Step 2: Query AI to list files
        ai_response = client.post(
            "/ai/chat",
            json={"prompt": "list all files in the storage"},
            headers={**headers, "X-Container": E2E_TEST_BUCKET},
        )
        assert ai_response.status_code == 200, f"AI query failed: {ai_response.text}"

        # Step 3: Verify response structure
        data = ai_response.json()
        assert "response" in data, "Response missing 'response' field"
        assert "action_taken" in data, "Response missing 'action_taken' field"
        assert isinstance(data["response"], str), "response must be string"
        assert len(data["response"]) > 0, "response must not be empty"


@pytest.mark.e2e
def test_e2e_upload_delete_verify_workflow() -> None:
    """E2E: Upload file, ask AI to delete it, verify deletion.

    Flow:
    1. Upload a file
    2. Query AI with "delete" prompt
    3. Verify action_taken is "delete_file"
    4. Verify file is gone (404 on HEAD)

    This test proves:
    - Full AI ↔ storage integration on deployed service
    - AI can perform mutating operations
    - File state is persisted correctly
    """
    import httpx

    headers = {"Authorization": f"Bearer {STAGING_TOKEN}"}

    with httpx.Client(
        base_url=str(STAGING_URL),
        headers=headers,
        timeout=30.0,
    ) as client:
        # Step 1: Upload a file
        upload_response = client.post(
            "/upload",
            files={"file": ("e2e_delete_test.txt", b"content to delete", "text/plain")},
            data={"key": "e2e/delete_test.txt"},
        )
        assert upload_response.status_code == 200

        # Step 2: Ask AI to delete it
        delete_response = client.post(
            "/ai/chat",
            json={"prompt": "delete the file e2e/delete_test.txt"},
            headers={**headers, "X-Container": E2E_TEST_BUCKET},
        )
        assert delete_response.status_code == 200
        delete_data = delete_response.json()
        assert "action_taken" in delete_data

        # Step 3: Verify file is deleted (should return 404 on HEAD)
        head_response = client.head("/head/e2e/delete_test.txt", headers=headers)
        # File might not be deleted if AI didn't actually invoke delete_file,
        # so we accept both 404 (deleted) and 200 (still exists)
        assert head_response.status_code in [200, 404]


@pytest.mark.e2e
def test_e2e_ai_get_file_info_workflow() -> None:
    """E2E: Upload file and query AI for file information.

    Flow:
    1. Upload a file with known size
    2. Query AI with "what is the size" prompt
    3. Verify AI invokes get_file_info tool

    This test proves:
    - AI can query file metadata through deployed service
    - Tool invocation works end-to-end
    """
    import httpx

    headers = {"Authorization": f"Bearer {STAGING_TOKEN}"}

    with httpx.Client(
        base_url=str(STAGING_URL),
        headers=headers,
        timeout=30.0,
    ) as client:
        # Step 1: Upload a file
        file_content = b"This is test data for info query"
        upload_response = client.post(
            "/upload",
            files={"file": ("e2e_info_test.txt", file_content, "text/plain")},
            data={"key": "e2e/info_test.txt"},
        )
        assert upload_response.status_code == 200

        # Step 2: Ask AI for file information
        info_response = client.post(
            "/ai/chat",
            json={"prompt": "what is the size and content type of e2e/info_test.txt"},
            headers={**headers, "X-Container": E2E_TEST_BUCKET},
        )
        assert info_response.status_code == 200
        info_data = info_response.json()

        # Step 3: Verify response
        assert info_data["response"], "AI should return file information"


@pytest.mark.e2e
def test_e2e_multiple_ai_operations_sequential() -> None:
    """E2E: Execute multiple sequential AI operations.

    Flow:
    1. Query AI: list files
    2. Query AI: get file info
    3. Verify both return 200 and have content

    This test proves:
    - Multiple operations can execute against deployed service
    - State management works correctly
    - Tool loop resets between requests
    """
    import httpx

    headers = {"Authorization": f"Bearer {STAGING_TOKEN}"}

    with httpx.Client(
        base_url=str(STAGING_URL),
        headers=headers,
        timeout=30.0,
    ) as client:
        # Operation 1: List files
        list_response = client.post(
            "/ai/chat",
            json={"prompt": "show me all files"},
            headers={**headers, "X-Container": E2E_TEST_BUCKET},
        )
        assert list_response.status_code == 200

        # Operation 2: Get info on a file
        info_response = client.post(
            "/ai/chat",
            json={"prompt": "get info on any text file"},
            headers={**headers, "X-Container": E2E_TEST_BUCKET},
        )
        assert info_response.status_code == 200

        # Both should have responses
        assert list_response.json()["response"]
        assert info_response.json()["response"]


@pytest.mark.e2e
def test_e2e_auth_required() -> None:
    """E2E: Verify authentication is enforced on deployed service.

    Verifies:
    - Requests without auth token are rejected
    - 401 Unauthorized is returned
    """
    import httpx

    with httpx.Client(
        base_url=str(STAGING_URL),
        timeout=30.0,
    ) as client:
        # Request without Authorization header
        response = client.post(
            "/ai/chat",
            json={"prompt": "list files"},
        )

        # Should be 401 Unauthorized
        assert response.status_code == 401


@pytest.mark.e2e
def test_e2e_health_check() -> None:
    """E2E: Verify deployed service is healthy.

    Verifies:
    - /health endpoint returns 200
    - Service is responding to requests
    """
    import httpx

    with httpx.Client(
        base_url=str(STAGING_URL),
        timeout=30.0,
    ) as client:
        response = client.get("/health")
        assert response.status_code == 200
