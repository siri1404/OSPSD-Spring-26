"""OAuth 2.0 authentication handlers for Google Cloud Platform."""

from __future__ import annotations

import os
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# Security scheme for bearer token authentication
security = HTTPBearer()


class AuthConfig:
    """Configuration for OAuth 2.0 authentication."""

    def __init__(self) -> None:
        """Initialize auth configuration from environment variables."""
        self.client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
        self.client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
        self.redirect_uri = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8000/auth/callback")
        self.scopes = [
            "https://www.googleapis.com/auth/devstorage.read_write",
            "https://www.googleapis.com/auth/cloud-platform",
        ]

    def validate(self) -> None:
        """Validate that required OAuth credentials are configured."""
        if not self.client_id or not self.client_secret:
            msg = "OAuth credentials not configured. Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET."
            raise RuntimeError(msg)


def get_auth_config() -> AuthConfig:
    """Get and validate auth configuration."""
    config = AuthConfig()
    config.validate()
    return config


def build_oauth_url(config: AuthConfig, state: str | None = None) -> str:
    """Build Google OAuth 2.0 authorization URL.

    Args:
        config: OAuth configuration.
        state: Optional state parameter for CSRF protection.

    Returns:
        Authorization URL for user redirect.
    """
    from urllib.parse import urlencode

    params = {
        "client_id": config.client_id,
        "redirect_uri": config.redirect_uri,
        "response_type": "code",
        "scope": " ".join(config.scopes),
        "access_type": "offline",
        "prompt": "consent",
    }

    if state:
        params["state"] = state

    base_url = "https://accounts.google.com/o/oauth2/v2/auth"
    return f"{base_url}?{urlencode(params)}"


async def exchange_code_for_token(code: str, config: AuthConfig) -> dict[str, Any]:
    """Exchange authorization code for access token.

    Args:
        code: Authorization code from OAuth callback.
        config: OAuth configuration.

    Returns:
        Token response containing access_token, refresh_token, etc.
    """
    import httpx

    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": config.client_id,
        "client_secret": config.client_secret,
        "redirect_uri": config.redirect_uri,
        "grant_type": "authorization_code",
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(token_url, data=data)
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]


async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Verify bearer token and return the provider access token.

    Token can be a service-owned opaque session token or a dev token.

    Args:
        credentials: HTTP bearer token from request.

    Returns:
        Provider access token (resolved from session or dev token).

    Raises:
        HTTPException: If token is invalid or expired.
    """
    from cloud_storage_service.sessions import active_sessions

    token = credentials.credentials

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if this is a dev token (only in development/test)
    environment = os.getenv("ENVIRONMENT", "production")
    dev_token = os.getenv("DEV_AUTH_TOKEN")
    if environment in ("development", "test") and dev_token and token == dev_token:
        return token

    # Resolve opaque session token → provider access token
    provider_token = active_sessions.get(token)
    if provider_token:
        return provider_token

    # Token not recognized - could be invalid or expired
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired session token",
        headers={"WWW-Authenticate": "Bearer"},
    )
