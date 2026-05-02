"""OAuth 2.0 authentication handlers for Google Cloud Platform.

Auth flow:
    1. User visits /auth/login → redirected to Google's consent screen.
    2. Google redirects back to /auth/callback with an authorization code.
    3. Service exchanges the code for an access + refresh token via
       exchange_code_for_token.
    4. Service stores the provider tokens in active_sessions keyed by an opaque
       session token returned to the client.
    5. Subsequent requests pass the session token as a bearer credential;
       verify_token resolves it back to the provider access token.

Note:
    active_sessions is in-memory; sessions don't survive restarts or shared
    deployments. Replace with Redis or signed JWTs for true multi-instance
    production use.
"""

from __future__ import annotations

import logging
import os
import secrets as secrets_module
from dataclasses import dataclass
from typing import TypedDict, cast
from urllib.parse import urlencode

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from cloud_storage_service.sessions import active_sessions

logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

_DEFAULT_SCOPES: tuple[str, ...] = (
    "https://www.googleapis.com/auth/devstorage.read_write",
    "https://www.googleapis.com/auth/cloud-platform",
)

# Security scheme for bearer token authentication.
security = HTTPBearer()


# ============================================================================
# Configuration
# ============================================================================


@dataclass(frozen=True)
class AuthConfig:
    """OAuth 2.0 configuration loaded once at startup."""

    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: tuple[str, ...]

    @classmethod
    def from_env(cls) -> AuthConfig:
        """Build an AuthConfig from environment variables.

        Raises:
            ValueError: If required environment variables are missing.
        """
        client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
        redirect_uri = os.getenv("GOOGLE_OAUTH_REDIRECT_URI")

        missing: list[str] = []
        if not client_id:
            missing.append("GOOGLE_OAUTH_CLIENT_ID")
        if not client_secret:
            missing.append("GOOGLE_OAUTH_CLIENT_SECRET")
        if not redirect_uri:
            missing.append("GOOGLE_OAUTH_REDIRECT_URI")

        if missing:
            msg = f"OAuth credentials not configured. Missing environment variables: {', '.join(missing)}."
            raise ValueError(msg)

        # Narrowing: missing == [] proves these are all non-None strings.
        assert client_id is not None  # noqa: S101 — narrowing for type-checker
        assert client_secret is not None  # noqa: S101
        assert redirect_uri is not None  # noqa: S101

        return cls(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scopes=_DEFAULT_SCOPES,
        )


def get_auth_config() -> AuthConfig:
    """Get and validate auth configuration from environment.

    Raises:
        ValueError: If required environment variables are missing.
    """
    return AuthConfig.from_env()


# ============================================================================
# OAuth response model
# ============================================================================


class OAuthTokenResponse(TypedDict, total=False):
    """Shape of Google's OAuth 2.0 token endpoint response.

    All fields except access_token and token_type are optional in practice
    (e.g., refresh_token is only returned on first consent).
    """

    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str
    scope: str
    id_token: str


# ============================================================================
# OAuth flow helpers
# ============================================================================


def build_oauth_url(config: AuthConfig, state: str | None = None) -> tuple[str, str]:
    """Build the Google OAuth 2.0 authorization URL.

    Args:
        config: OAuth configuration.
        state: Optional state parameter for CSRF protection. If not supplied,
            a cryptographically random state is generated.

    Returns:
        (url, state) — caller must store the state to verify it on callback.
    """
    resolved_state = state if state is not None else secrets_module.token_urlsafe(32)

    params: dict[str, str] = {
        "client_id": config.client_id,
        "redirect_uri": config.redirect_uri,
        "response_type": "code",
        "scope": " ".join(config.scopes),
        "access_type": "offline",
        "prompt": "consent",
        "state": resolved_state,
    }

    return f"{_GOOGLE_AUTH_URL}?{urlencode(params)}", resolved_state


async def exchange_code_for_token(
    code: str,
    config: AuthConfig,
) -> OAuthTokenResponse:
    """Exchange an authorization code for an access token.

    Args:
        code: Authorization code returned by Google's OAuth callback.
        config: OAuth configuration.

    Returns:
        Parsed token response containing the access token and (optionally)
        a refresh token.

    Raises:
        httpx.HTTPStatusError: If the exchange fails.
    """
    data = {
        "code": code,
        "client_id": config.client_id,
        "client_secret": config.client_secret,
        "redirect_uri": config.redirect_uri,
        "grant_type": "authorization_code",
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(_GOOGLE_TOKEN_URL, data=data)
        response.raise_for_status()
        return cast("OAuthTokenResponse", response.json())


# ============================================================================
# Bearer-token verification
# ============================================================================


def _matches_dev_token(presented: str, expected: str) -> bool:
    """Constant-time comparison of dev tokens to avoid timing leaks."""
    return secrets_module.compare_digest(presented, expected)


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str | None:
    """Verify a bearer token from the request.

    Two paths are supported:

    * **Session path** — the bearer is an opaque session token issued by
      /auth/callback. We resolve it to the stored provider access token.
    * **Dev path** — in ENVIRONMENT=development|test, a configured DEV_AUTH_TOKEN
      is accepted and None is returned to signal the caller should fall back to
      Application Default Credentials (ADC).

    Args:
        credentials: HTTP bearer token from request (FastAPI dependency).

    Returns:
        The provider access token string for session-authenticated requests,
        or None for dev-token requests (caller should use ADC).

    Raises:
        HTTPException: If the token is missing or unrecognized.
    """
    token = credentials.credentials
    if not token:
        logger.warning("auth.verify.missing_token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Dev/test bypass: accept a configured dev token and signal ADC fallback.
    environment = os.getenv("ENVIRONMENT", "production")
    dev_token = os.getenv("DEV_AUTH_TOKEN")
    if environment in ("development", "test") and dev_token and _matches_dev_token(token, dev_token):
        logger.info("auth.verify.success", extra={"path": "dev"})
        return None

    # Production path: opaque session token → provider access token.
    provider_token = active_sessions.get(token)
    if provider_token:
        logger.info("auth.verify.success", extra={"path": "session"})
        return provider_token

    logger.warning("auth.verify.invalid_token")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired session token",
        headers={"WWW-Authenticate": "Bearer"},
    )


# ============================================================================
# Public API
# ============================================================================

from collections.abc import Sequence

__all__: Sequence[str] = (
    "AuthConfig",
    "OAuthTokenResponse",
    "build_oauth_url",
    "exchange_code_for_token",
    "get_auth_config",
    "security",
    "verify_token",
)
