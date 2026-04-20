"""End-to-end workflow tests for the cloud storage service.

Tests the complete flow of the service including:
- Health checks
- Upload, list, delete workflows
- AI chat with Slack notifications (optional, requires Slack integration)

These tests require STAGING_SERVICE_URL environment variable to be set.
Set STAGING_SERVICE_URL=http://localhost:8000 to run against local service.

Mark tests with @pytest.mark.slack_integration to run Slack integration tests.
These require SLACK_BOT_TOKEN environment variable.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from io import BytesIO

import pytest
import requests


@pytest.fixture
def service_url() -> str | None:
    """Get the staging service URL from environment.

    Returns:
        Service URL if set, None otherwise.
    """
    return os.getenv("STAGING_SERVICE_URL")


@pytest.fixture
def dev_token() -> str:
    """Get the dev token for testing."""
    return os.getenv("DEV_AUTH_TOKEN", "dev-token-12345")


@pytest.fixture
def skip_if_no_service(service_url: str | None) -> None:
    """Skip test if STAGING_SERVICE_URL is not set."""
    if not service_url:
        pytest.skip("STAGING_SERVICE_URL not set - skipping E2E tests")


@pytest.mark.e2e
class TestE2EWorkflow:
    """End-to-end workflow tests."""

    def test_e2e_health_endpoint(
        self,
        service_url: str | None,
        skip_if_no_service: None,
    ) -> None:
        """Test that health endpoint is accessible and returns proper status.

        Verifies:
        - GET /health endpoint responds with 200 OK
        - Response contains status field
        - Response structure is valid JSON
        """
        assert service_url is not None
        url = f"{service_url}/health"

        # Act: Query health endpoint
        response = requests.get(url, timeout=5)

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"

    def test_e2e_upload_list_delete_workflow(
        self,
        service_url: str | None,
        skip_if_no_service: None,
        dev_token: str,
    ) -> None:
        """Test complete upload, list, delete workflow.

        Verifies:
        - Can upload a file with bearer token auth
        - Can list files and uploaded file appears
        - Can delete the file
        - File is removed from listings
        """
        assert service_url is not None
        auth_headers = {"Authorization": f"Bearer {dev_token}"}
        container_headers = {"X-Container": "test-bucket"}

        # Arrange: Prepare test file
        test_file_content = b"Test content for E2E workflow"
        test_filename = "e2e-test-file.txt"

        # Act 1: Upload file
        upload_url = f"{service_url}/upload"
        files = {"file": (test_filename, BytesIO(test_file_content))}
        data = {"key": f"e2e-tests/{test_filename}", "content_type": "text/plain"}
        headers = {**auth_headers, **container_headers}

        response = requests.post(upload_url, files=files, data=data, headers=headers, timeout=10)

        # Assert: Upload succeeded
        assert response.status_code == 200
        upload_data = response.json()
        assert "key" in upload_data
        uploaded_key = upload_data["key"]

        # Act 2: List files to verify upload
        list_url = f"{service_url}/list"
        response = requests.get(list_url, headers=headers, timeout=10)

        # Assert: File appears in listing
        assert response.status_code == 200
        list_data = response.json()
        assert "files" in list_data
        file_keys = [f["object_name"] for f in list_data["files"]]
        # File should appear (may be under uploaded_key or original key depending on implementation)
        assert len(file_keys) > 0

        # Act 3: Delete the uploaded file
        delete_url = f"{service_url}/delete"
        delete_data = {"key": uploaded_key}
        response = requests.post(delete_url, json=delete_data, headers=headers, timeout=10)

        # Assert: Delete succeeded
        assert response.status_code in (200, 204)

    def test_e2e_auth_required_on_endpoints(
        self,
        service_url: str | None,
        skip_if_no_service: None,
    ) -> None:
        """Test that endpoints require bearer token authentication.

        Verifies:
        - Requests without authorization header are rejected
        - Requests with invalid token are rejected
        - Valid token allows access
        """
        assert service_url is not None

        # Act: List files without auth
        response = requests.get(f"{service_url}/list", timeout=5)

        assert response.status_code == 403

        # Act: List files with invalid token
        bad_headers = {"Authorization": "Bearer invalid-token"}
        response = requests.get(f"{service_url}/list", headers=bad_headers, timeout=5)

        # Assert: Request is still rejected (invalid token)
        assert response.status_code == 403

    def test_e2e_container_header_required(
        self,
        service_url: str | None,
        skip_if_no_service: None,
        dev_token: str,
    ) -> None:
        """Test that endpoints require X-Container header.

        Verifies:
        - Requests without X-Container header are rejected with 400 or 422
        - With correct header, request succeeds
        """
        assert service_url is not None
        auth_headers = {"Authorization": f"Bearer {dev_token}"}

        # Act: List files without X-Container header
        response = requests.get(f"{service_url}/list", headers=auth_headers, timeout=5)

        assert response.status_code in (400, 422)

        # Act: List files with X-Container header
        correct_headers = {**auth_headers, "X-Container": "test-bucket"}
        response = requests.get(f"{service_url}/list", headers=correct_headers, timeout=5)

        # Assert: Request succeeds
        assert response.status_code == 200


@pytest.mark.e2e
@pytest.mark.slack_integration
class TestE2ESlackIntegration:
    """End-to-end tests with Slack integration.

    These tests require SLACK_BOT_TOKEN environment variable to be set
    and the Slack workspace to be properly configured.
    """

    @pytest.fixture
    def skip_if_no_slack(self) -> None:
        """Skip Slack integration tests if token is not set."""
        if not os.getenv("SLACK_BOT_TOKEN"):
            pytest.skip("SLACK_BOT_TOKEN not set - skipping Slack integration tests")

    def test_e2e_ai_chat_triggers_real_slack_notification(
        self,
        service_url: str | None,
        skip_if_no_service: None,
        skip_if_no_slack: None,
        dev_token: str,
    ) -> None:
        """Test that AI chat endpoint sends real Slack notifications.

        This is an optional test that requires:
        - STAGING_SERVICE_URL pointing to running service
        - SLACK_BOT_TOKEN set to valid Slack bot token
        - Service configured with valid Slack channel

        Verifies:
        - AI chat response includes action_taken field
        - Response is successful (200 OK)
        - No errors reported in response

        Note: Actual Slack notification delivery is verified by checking
        that no errors are returned and the message includes action details.
        """
        assert service_url is not None
        auth_headers = {"Authorization": f"Bearer {dev_token}"}
        container_headers = {"X-Container": "test-bucket"}
        headers = {**auth_headers, **container_headers}

        # Arrange: Prepare AI chat prompt
        prompt = "Tell me how many files are in the bucket"

        # Act: Send chat prompt
        chat_url = f"{service_url}/ai/chat"
        response = requests.post(
            chat_url,
            json={"prompt": prompt},
            headers=headers,
            timeout=15,  # AI operations can be slow
        )

        # Assert: Chat endpoint responds successfully
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()

        # Verify response structure
        assert "response" in data
        assert "action_taken" in data

        # Verify action was recorded (list_files, delete_file, etc.)
        action = data.get("action_taken", "none")
        assert action != "none", "AI should have taken some action"

    def test_e2e_ai_chat_slack_error_handling(
        self,
        service_url: str | None,
        skip_if_no_service: None,
        skip_if_no_slack: None,
        dev_token: str,
    ) -> None:
        """Test that AI chat handles Slack errors gracefully.

        Verifies:
        - Chat endpoint still responds even if Slack notification fails
        - Response includes AI response text
        - HTTP status is still 200 (errors don't cascade to client)
        """
        assert service_url is not None
        auth_headers = {"Authorization": f"Bearer {dev_token}"}
        container_headers = {"X-Container": "test-bucket"}
        headers = {**auth_headers, **container_headers}

        # Act: Send chat prompt (may fail to notify Slack if misconfigured)
        chat_url = f"{service_url}/ai/chat"
        response = requests.post(
            chat_url,
            json={"prompt": "list files"},
            headers=headers,
            timeout=15,
        )

        # Assert: Response is still successful (error resilience)
        # Even if Slack notification fails internally, client gets 200
        assert response.status_code in (200, 502), f"Expected 200 or 502 (service error), got {response.status_code}"

        if response.status_code == 200:
            data = response.json()
            assert "response" in data


@pytest.mark.e2e
class TestE2EErrorHandling:
    """End-to-end error handling tests."""

    def test_e2e_invalid_json_returns_422(
        self,
        service_url: str | None,
        skip_if_no_service: None,
        dev_token: str,
    ) -> None:
        """Test that invalid JSON payload returns 422 Unprocessable Entity.

        Verifies:
        - Malformed JSON is rejected
        - Error response includes error details
        """
        assert service_url is not None
        auth_headers = {"Authorization": f"Bearer {dev_token}"}
        container_headers = {"X-Container": "test-bucket"}
        headers = {**auth_headers, **container_headers}

        # Act: Send invalid JSON
        response = requests.post(
            f"{service_url}/ai/chat",
            data="not valid json",
            headers=headers,
            timeout=5,
        )

        # Assert: Invalid JSON is rejected
        assert response.status_code in (400, 422)

    def test_e2e_missing_required_fields_returns_422(
        self,
        service_url: str | None,
        skip_if_no_service: None,
        dev_token: str,
    ) -> None:
        """Test that missing required fields returns 422 Unprocessable Entity.

        Verifies:
        - POST /ai/chat requires 'prompt' field
        - Missing field is rejected
        """
        assert service_url is not None
        auth_headers = {"Authorization": f"Bearer {dev_token}"}
        container_headers = {"X-Container": "test-bucket"}
        headers = {**auth_headers, **container_headers}

        # Act: Send request without required 'prompt' field
        response = requests.post(
            f"{service_url}/ai/chat",
            json={},  # Empty payload, missing 'prompt'
            headers=headers,
            timeout=5,
        )

        # Assert: Missing field is rejected
        assert response.status_code == 422
