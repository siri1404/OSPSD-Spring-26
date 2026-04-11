"""Unit tests for authentication endpoints."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cloud_storage_service.auth import AuthConfig, build_oauth_url, exchange_code_for_token, get_auth_config, verify_token
from fastapi.security import HTTPAuthorizationCredentials

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


@pytest.mark.unit
def test_login_endpoint_returns_200(client: TestClient) -> None:
    """Test that login endpoint returns auth_url payload."""
    response = client.post("/auth/login")
    assert response.status_code == 200


@pytest.mark.unit
def test_login_endpoint_returns_auth_url(client: TestClient) -> None:
    """Test that login endpoint returns OAuth authorization URL."""
    response = client.post("/auth/login")
    auth_url = response.json()["auth_url"]

    assert isinstance(auth_url, str)
    assert auth_url.startswith("https://accounts.google.com/o/oauth2/v2/auth")


@pytest.mark.unit
def test_login_endpoint_auth_url_contains_required_params(client: TestClient) -> None:
    """Test that auth URL contains required OAuth parameters."""
    response = client.post("/auth/login")
    auth_url = response.json()["auth_url"]

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
    auth_url = response.json()["auth_url"]

    # Check for storage scopes
    assert "devstorage.read_write" in auth_url or "cloud-platform" in auth_url


@pytest.mark.unit
def test_get_auth_config_returns_config_when_env_is_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the helper returns a validated config from the environment."""
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "client-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("GOOGLE_OAUTH_REDIRECT_URI", "https://example.com/callback")

    config = get_auth_config()

    assert config.client_id == "client-id"
    assert config.client_secret == "client-secret"
    assert config.redirect_uri == "https://example.com/callback"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_exchange_code_for_token_returns_token_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the OAuth code exchange helper against a mocked HTTP response."""
    config = AuthConfig()
    config.client_id = "client-id"
    config.client_secret = "client-secret"
    config.redirect_uri = "https://example.com/callback"

    token_data = {"access_token": "provider-token", "expires_in": 3600}

    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = MagicMock(return_value=token_data)

    async def _fake_post(url: str, data: object) -> object:
        assert url == "https://oauth2.googleapis.com/token"
        assert isinstance(data, dict)
        assert data["code"] == "auth-code"
        return response

    fake_client = AsyncMock()
    fake_client.post = AsyncMock(side_effect=_fake_post)
    fake_client.__aenter__.return_value = fake_client
    fake_client.__aexit__.return_value = False

    with patch("httpx.AsyncClient", return_value=fake_client):
        result = await exchange_code_for_token("auth-code", config)

    assert result == token_data


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_token_resolves_service_session_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test service-owned session tokens resolve to provider tokens."""
    from cloud_storage_service.sessions import active_sessions

    active_sessions.clear()
    active_sessions["session-token"] = "provider-token"

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("DEV_AUTH_TOKEN", raising=False)

    try:
        token = await verify_token(HTTPAuthorizationCredentials(scheme="Bearer", credentials="session-token"))
    finally:
        active_sessions.clear()

    assert token == "provider-token"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_token_rejects_empty_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that an empty bearer token is rejected by the helper."""
    from fastapi import HTTPException

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("DEV_AUTH_TOKEN", raising=False)

    with pytest.raises(HTTPException, match="Missing authentication token"):
        await verify_token(HTTPAuthorizationCredentials(scheme="Bearer", credentials=""))


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
            # Verify it's a different token than the provider token (should be opaque session token)
            assert callback_data["access_token"] != "test-access-token"
            # Verify it's a valid opaque token (not empty, reasonable length)
            assert len(callback_data["access_token"]) > 20
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
def test_dev_token_authentication(client: TestClient, mock_storage_client: MagicMock) -> None:
    """Test that dev token works for authentication."""
    # Try accessing a protected endpoint with dev token
    headers = {"Authorization": "Bearer dev-token-12345"}
    response = client.get("/list", headers=headers)

    # Dev token should authorize the request and reach the storage layer.
    assert response.status_code == 200
    mock_storage_client.list_files.assert_called_once_with(container="test-bucket", prefix="")


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
