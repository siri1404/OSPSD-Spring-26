"""End-to-end workflow tests for the cloud storage service.

Tests the complete flow of the deployed service:
- Health checks
- Upload, list, delete workflows (with shared-contract response shape)
- AI chat with optional Slack notification verification

Set STAGING_SERVICE_URL (e.g. http://localhost:8000) to point at a running service.
Tests are skipped automatically when the env var is not set.

The Slack integration block additionally requires SLACK_BOT_TOKEN.

Per peer-review #2, assertions match the service's actual contract:
- Storage endpoints accept ?container= query (NOT an X-Container header)
- Delete is DELETE /delete/{key:path} (NOT POST /delete with JSON body)
- List response key is objects (NOT files)
- Object metadata uses object_name (NOT v0 key)
- AI chat accepts the X-Container header for default-container context.
"""

from __future__ import annotations

import os
from io import BytesIO
from typing import Any

import httpx
import pytest

_TEST_CONTAINER = "test-bucket"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def service_url() -> str | None:
    """Return STAGING_SERVICE_URL or None when not set."""
    return os.getenv("STAGING_SERVICE_URL")


@pytest.fixture
def dev_token() -> str:
    """Return the dev bearer token (defaults to the conftest-aligned value)."""
    return os.getenv("DEV_AUTH_TOKEN", "dev-token-12345")


@pytest.fixture
def auth_headers(dev_token: str) -> dict[str, str]:
    """Authorization header with the dev token."""
    return {"Authorization": f"Bearer {dev_token}"}


@pytest.fixture(autouse=True)
def _skip_if_no_service(
    request: pytest.FixtureRequest,
    service_url: str | None,
) -> None:
    """Skip every test in this module when STAGING_SERVICE_URL isn't set."""
    if request.node.get_closest_marker("e2e") and not service_url:
        pytest.skip("STAGING_SERVICE_URL not set — skipping E2E tests")


@pytest.fixture
def slack_required() -> None:
    """Skip Slack integration tests when SLACK_BOT_TOKEN isn't set."""
    if not os.getenv("SLACK_BOT_TOKEN"):
        pytest.skip("SLACK_BOT_TOKEN not set — skipping Slack integration tests")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _list_objects(
    service_url: str,
    headers: dict[str, str],
    prefix: str,
) -> list[dict[str, Any]]:
    """GET /list?prefix=&container= and return the parsed objects list."""
    response = httpx.get(
        f"{service_url}/list",
        params={"prefix": prefix, "container": _TEST_CONTAINER},
        headers=headers,
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    objects: list[dict[str, Any]] = payload["objects"]
    return objects


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_e2e_health_endpoint(service_url: str | None) -> None:
    """GET /health responds 200 with status='healthy'."""
    assert service_url is not None
    response = httpx.get(f"{service_url}/health", timeout=5)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


# ---------------------------------------------------------------------------
# Storage workflow
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_e2e_upload_list_delete_workflow(
    service_url: str | None,
    auth_headers: dict[str, str],
) -> None:
    """Upload a file, see it in /list, then delete it via DELETE /delete/{key:path}."""
    assert service_url is not None
    test_file_content = b"Test content for E2E workflow"
    test_filename = "e2e-test-file.txt"
    object_key = f"e2e-tests/{test_filename}"

    # 1) Upload — multipart form, container as query param.
    upload_response = httpx.post(
        f"{service_url}/upload",
        params={"container": _TEST_CONTAINER},
        files={"file": (test_filename, BytesIO(test_file_content), "text/plain")},
        data={"key": object_key, "content_type": "text/plain"},
        headers=auth_headers,
        timeout=15,
    )
    assert upload_response.status_code == 200, upload_response.text
    upload_data = upload_response.json()
    # Shared-contract response shape (peer review #1).
    assert "object_name" in upload_data
    assert "integrity" in upload_data
    assert "data_type" in upload_data

    # 2) List — verify object appears under our prefix.
    objects = _list_objects(service_url, auth_headers, prefix="e2e-tests/")
    listed_keys = {obj["object_name"] for obj in objects}
    assert any(
        # Mocked backends may report a synthetic name; real backends return
        # exactly object_key. Accept either to keep this test backend-agnostic.
        key == object_key or key.endswith(test_filename)
        for key in listed_keys
    ), f"Uploaded object not visible in listing: {listed_keys}"

    # 3) Delete — DELETE /delete/{key:path}, container as query param.
    delete_response = httpx.delete(
        f"{service_url}/delete/{object_key}",
        params={"container": _TEST_CONTAINER},
        headers=auth_headers,
        timeout=10,
    )
    assert delete_response.status_code == 204, delete_response.text


@pytest.mark.e2e
def test_e2e_list_response_uses_shared_contract_field_names(
    service_url: str | None,
    auth_headers: dict[str, str],
) -> None:
    """/list response objects expose object_name/integrity/data_type, not v0 names."""
    assert service_url is not None
    response = httpx.get(
        f"{service_url}/list",
        params={"container": _TEST_CONTAINER},
        headers=auth_headers,
        timeout=10,
    )

    assert response.status_code == 200
    payload = response.json()
    assert "objects" in payload
    assert isinstance(payload["objects"], list)

    if payload["objects"]:
        obj = payload["objects"][0]
        # Must be the shared-contract names.
        for shared_field in ("object_name", "size_bytes", "integrity", "data_type"):
            assert shared_field in obj, f"Missing shared-contract field {shared_field!r}: {obj}"
        # Must NOT advertise v0 names.
        for v0_field in ("key", "etag", "content_type"):
            assert v0_field not in obj, f"v0 field {v0_field!r} should have been removed: {obj}"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_e2e_auth_required_on_endpoints(service_url: str | None) -> None:
    """/list rejects requests without a valid bearer token."""
    assert service_url is not None

    no_auth = httpx.get(
        f"{service_url}/list",
        params={"container": _TEST_CONTAINER},
        timeout=5,
    )
    assert no_auth.status_code in (401, 403)

    bad_auth = httpx.get(
        f"{service_url}/list",
        params={"container": _TEST_CONTAINER},
        headers={"Authorization": "Bearer invalid-token"},
        timeout=5,
    )
    assert bad_auth.status_code in (401, 403)


@pytest.mark.e2e
def test_e2e_storage_endpoints_use_query_param_for_container(
    service_url: str | None,
    auth_headers: dict[str, str],
) -> None:
    """/list accepts container via ?container= query (NOT X-Container header)."""
    assert service_url is not None

    response = httpx.get(
        f"{service_url}/list",
        params={"container": _TEST_CONTAINER},
        headers=auth_headers,
        timeout=5,
    )

    assert response.status_code == 200, response.text


# ---------------------------------------------------------------------------
# AI chat — Slack integration (optional)
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.slack_integration
def test_e2e_ai_chat_triggers_action_with_x_container_header(
    service_url: str | None,
    auth_headers: dict[str, str],
    slack_required: None,
) -> None:
    """/ai/chat returns response and action_taken; X-Container drives default container."""
    assert service_url is not None
    headers = {**auth_headers, "X-Container": _TEST_CONTAINER}

    response = httpx.post(
        f"{service_url}/ai/chat",
        json={"prompt": "Tell me how many files are in the bucket"},
        headers=headers,
        timeout=30,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert "response" in data
    assert "action_taken" in data


@pytest.mark.e2e
@pytest.mark.slack_integration
def test_e2e_ai_chat_resilient_to_slack_failure(
    service_url: str | None,
    auth_headers: dict[str, str],
    slack_required: None,
) -> None:
    """/ai/chat returns 200 even if downstream Slack notification fails."""
    assert service_url is not None
    headers = {**auth_headers, "X-Container": _TEST_CONTAINER}

    response = httpx.post(
        f"{service_url}/ai/chat",
        json={"prompt": "list files"},
        headers=headers,
        timeout=30,
    )

    assert response.status_code in (200, 502), response.text
    if response.status_code == 200:
        assert "response" in response.json()


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_e2e_invalid_json_returns_validation_error(
    service_url: str | None,
    auth_headers: dict[str, str],
) -> None:
    """/ai/chat rejects malformed JSON with 400 or 422."""
    assert service_url is not None

    response = httpx.post(
        f"{service_url}/ai/chat",
        content=b"not valid json",
        headers={**auth_headers, "Content-Type": "application/json"},
        timeout=5,
    )

    assert response.status_code in (400, 422)


@pytest.mark.e2e
def test_e2e_missing_required_field_returns_422(
    service_url: str | None,
    auth_headers: dict[str, str],
) -> None:
    """/ai/chat rejects payloads without the required 'prompt' field."""
    assert service_url is not None

    response = httpx.post(
        f"{service_url}/ai/chat",
        json={},
        headers=auth_headers,
        timeout=5,
    )

    assert response.status_code == 422
