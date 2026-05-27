"""Unit tests for authentication endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
from cloud_storage_service.auth import (
    AuthConfig,
    exchange_code_for_token,
    get_auth_config,
    verify_token,
)
from fastapi.security import HTTPAuthorizationCredentials
from httpx import ASGITransport, AsyncClient

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# /auth/login
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_login_endpoint_returns_auth_url_with_required_params(
    client: TestClient,
) -> None:
    """/auth/login returns a Google authorization URL with all OAuth params."""
    response = client.post("/auth/login")

    assert response.status_code == 200
    auth_url = response.json()["auth_url"]
    assert auth_url.startswith("https://accounts.google.com/o/oauth2/v2/auth")
    for required in (
        "client_id=",
        "redirect_uri=",
        "response_type=code",
        "scope=",
        "state=",
    ):
        assert required in auth_url


@pytest.mark.unit
def test_login_endpoint_includes_storage_scopes(client: TestClient) -> None:
    """/auth/login includes GCS storage scopes."""
    response = client.post("/auth/login")
    auth_url = response.json()["auth_url"]
    assert "devstorage.read_write" in auth_url or "cloud-platform" in auth_url


# ---------------------------------------------------------------------------
# /auth/callback
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_callback_with_valid_code_returns_opaque_session_token() -> None:
    """/auth/callback exchanges code for token and returns an opaque session ID."""
    from cloud_storage_service.main import app

    mock_token_data = {
        "access_token": "test-provider-token",
        "token_type": "bearer",
        "expires_in": 3600,
    }

    with patch(
        "cloud_storage_service.main.exchange_code_for_token",
        new=AsyncMock(return_value=mock_token_data),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as async_client:
            login_response = await async_client.post("/auth/login")
            auth_url = login_response.json()["auth_url"]

            params = parse_qs(urlparse(auth_url).query)
            state = params["state"][0]

            callback_response = await async_client.get(f"/auth/callback?code=test-code&state={state}")

            assert callback_response.status_code == 200
            data = callback_response.json()
            # Opaque session ID, NOT the provider token.
            assert data["access_token"] != "test-provider-token"
            assert len(data["access_token"]) >= 32
            assert data["token_type"] == "bearer"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_callback_with_invalid_state_returns_400() -> None:
    """/auth/callback rejects callbacks with an unknown state (CSRF protection)."""
    from cloud_storage_service.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as async_client:
        response = await async_client.get("/auth/callback?code=test-code&state=invalid-state")

        assert response.status_code == 400
        detail = response.json()["detail"].lower()
        assert "state" in detail or "csrf" in detail


# ---------------------------------------------------------------------------
# AuthConfig and OAuth helpers
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_auth_config_returns_config_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """get_auth_config builds AuthConfig from environment variables."""
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "client-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("GOOGLE_OAUTH_REDIRECT_URI", "https://example.com/callback")

    config = get_auth_config()

    assert config.client_id == "client-id"
    assert config.client_secret == "client-secret"
    assert config.redirect_uri == "https://example.com/callback"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_exchange_code_for_token_returns_token_payload() -> None:
    """exchange_code_for_token POSTs to Google and returns the parsed JSON."""
    config = AuthConfig(
        client_id="client-id",
        client_secret="client-secret",
        redirect_uri="https://example.com/callback",
        scopes=("https://www.googleapis.com/auth/devstorage.read_write",),
    )
    token_data = {"access_token": "provider-token", "expires_in": 3600}

    captured: dict[str, Any] = {}

    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = MagicMock(return_value=token_data)

    async def fake_post(url: str, data: dict[str, str]) -> MagicMock:
        captured["url"] = url
        captured["data"] = data
        return response

    fake_client = AsyncMock()
    fake_client.post = AsyncMock(side_effect=fake_post)
    fake_client.__aenter__.return_value = fake_client
    fake_client.__aexit__.return_value = False

    with patch("httpx.AsyncClient", return_value=fake_client):
        result = await exchange_code_for_token("auth-code", config)

    assert result == token_data
    assert captured["url"] == "https://oauth2.googleapis.com/token"
    assert captured["data"]["code"] == "auth-code"


# ---------------------------------------------------------------------------
# verify_token
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_token_resolves_session_token_to_provider_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A session token in active_sessions is resolved to its provider token."""
    from cloud_storage_service.sessions import active_sessions

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("DEV_AUTH_TOKEN", raising=False)
    active_sessions["session-token"] = "provider-token"

    token = await verify_token(HTTPAuthorizationCredentials(scheme="Bearer", credentials="session-token"))

    assert token == "provider-token"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_token_dev_path_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dev token in development/test environment returns None (ADC fallback)."""
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DEV_AUTH_TOKEN", "dev-token-12345")

    token = await verify_token(HTTPAuthorizationCredentials(scheme="Bearer", credentials="dev-token-12345"))

    assert token is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_token_rejects_empty_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty bearer token raises 401 with 'Missing authentication token'."""
    from fastapi import HTTPException

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("DEV_AUTH_TOKEN", raising=False)

    with pytest.raises(HTTPException, match="Missing authentication token"):
        await verify_token(HTTPAuthorizationCredentials(scheme="Bearer", credentials=""))


# ---------------------------------------------------------------------------
# Auth integration via the /list endpoint
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_dev_token_authorizes_protected_endpoint(client: TestClient, mock_storage_client: MagicMock) -> None:
    """Dev token authorizes a request to a protected endpoint."""
    headers = {"Authorization": "Bearer dev-token-12345"}
    response = client.get("/list", headers=headers)

    assert response.status_code == 200
    mock_storage_client.list_files.assert_called_once_with(container="test-bucket", prefix="")


@pytest.mark.unit
def test_missing_token_returns_401(client: TestClient) -> None:
    """A request without a bearer token is rejected with 401."""
    response = client.get("/list")
    assert response.status_code == 401


@pytest.mark.unit
def test_invalid_token_returns_401(client: TestClient) -> None:
    """An unrecognized bearer token is rejected with 401."""
    headers = {"Authorization": "Bearer invalid-token-xyz"}
    response = client.get("/list", headers=headers)

    assert response.status_code == 401
    assert "detail" in response.json()
