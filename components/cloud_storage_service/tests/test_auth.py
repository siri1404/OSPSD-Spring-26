"""Unit tests for authentication endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


@pytest.mark.unit
def test_login_endpoint_returns_200(client: TestClient) -> None:
    """Test that login endpoint returns 200 OK."""
    response = client.post("/auth/login")
    assert response.status_code == 200


@pytest.mark.unit
def test_login_endpoint_returns_auth_url(client: TestClient) -> None:
    """Test that login endpoint returns OAuth authorization URL."""
    response = client.post("/auth/login")
    data = response.json()

    assert "auth_url" in data
    assert isinstance(data["auth_url"], str)
    assert data["auth_url"].startswith("https://accounts.google.com/o/oauth2/v2/auth")


@pytest.mark.unit
def test_login_endpoint_auth_url_contains_required_params(client: TestClient) -> None:
    """Test that auth URL contains required OAuth parameters."""
    response = client.post("/auth/login")
    data = response.json()
    auth_url = data["auth_url"]

    # Check for required OAuth parameters
    assert "client_id=" in auth_url
    assert "redirect_uri=" in auth_url
    assert "response_type=code" in auth_url
    assert "scope=" in auth_url
    assert "state=" in auth_url


@pytest.mark.unit
def test_login_endpoint_includes_storage_scopes(client: TestClient) -> None:
    """Test that auth URL includes GCS storage scopes."""
    response = client.post("/auth/login")
    data = response.json()
    auth_url = data["auth_url"]

    # Check for storage scopes
    assert "devstorage.read_write" in auth_url or "cloud-platform" in auth_url


@pytest.mark.unit
@pytest.mark.asyncio
async def test_callback_endpoint_with_valid_code() -> None:
    """Test OAuth callback with valid authorization code."""
    from cloud_storage_service.main import app
    from httpx import ASGITransport, AsyncClient

    # Mock the token exchange
    mock_token_data = {
        "access_token": "test-access-token",
        "token_type": "bearer",
        "expires_in": 3600,
    }

    with patch("cloud_storage_service.main.exchange_code_for_token", new=AsyncMock(return_value=mock_token_data)):
        # First, get a state parameter from login
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            login_response = await ac.post("/auth/login")
            auth_url = login_response.json()["auth_url"]

            # Extract state from auth_url
            import urllib.parse

            parsed = urllib.parse.urlparse(auth_url)
            params = urllib.parse.parse_qs(parsed.query)
            state = params["state"][0]

            # Now test callback
            callback_response = await ac.get(f"/auth/callback?code=test-code&state={state}")

            assert callback_response.status_code == 200
            callback_data = callback_response.json()

            assert "access_token" in callback_data
            assert callback_data["access_token"] == "test-access-token"
            assert callback_data["token_type"] == "bearer"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_callback_endpoint_with_invalid_state() -> None:
    """Test OAuth callback with invalid state parameter."""
    from cloud_storage_service.main import app
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Try callback with invalid state
        response = await ac.get("/auth/callback?code=test-code&state=invalid-state")

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "state" in data["detail"].lower() or "CSRF" in data["detail"]


@pytest.mark.unit
def test_dev_token_authentication(client: TestClient) -> None:
    """Test that dev token works for authentication."""
    # Try accessing a protected endpoint with dev token
    headers = {"Authorization": "Bearer dev-token-12345"}
    response = client.get("/list", headers=headers)

    # Should not return 401 Unauthorized
    assert response.status_code != 401


@pytest.mark.unit
def test_missing_token_returns_401(client: TestClient) -> None:
    """Test that missing token returns 401 Unauthorized."""
    # Try accessing protected endpoint without token
    response = client.get("/list")

    assert response.status_code == 401  # Returns 401 for missing auth


@pytest.mark.unit
def test_invalid_token_returns_401(client: TestClient) -> None:
    """Test that invalid token returns 401 Unauthorized."""
    headers = {"Authorization": "Bearer invalid-token-xyz"}
    response = client.get("/list", headers=headers)

    assert response.status_code == 401
    data = response.json()
    assert "detail" in data
