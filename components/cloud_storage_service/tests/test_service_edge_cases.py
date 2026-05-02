"""Edge case tests for cloud storage service auth and OAuth URL builder.

Tests boundary conditions for AuthConfig validation and build_oauth_url.
"""

from __future__ import annotations

import pytest
from cloud_storage_service.auth import AuthConfig, build_oauth_url, get_auth_config

_BASE_ENV: dict[str, str] = {
    "GOOGLE_OAUTH_CLIENT_ID": "test-client-id",
    "GOOGLE_OAUTH_CLIENT_SECRET": "test-secret",
    "GOOGLE_OAUTH_REDIRECT_URI": "http://localhost:8000/auth/callback",
}


def _make_config(
    *,
    client_id: str = "test-client-id",
    client_secret: str = "test-secret",  # noqa: S107
    redirect_uri: str = "http://localhost:8000/auth/callback",
) -> AuthConfig:
    """Construct an AuthConfig directly for OAuth URL helper tests."""
    return AuthConfig(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scopes=(
            "https://www.googleapis.com/auth/devstorage.read_write",
            "https://www.googleapis.com/auth/cloud-platform",
        ),
    )


# ---------------------------------------------------------------------------
# AuthConfig.from_env validation
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_auth_config_missing_client_id_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """from_env raises ValueError listing GOOGLE_OAUTH_CLIENT_ID as missing."""
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "secret")
    monkeypatch.setenv(
        "GOOGLE_OAUTH_REDIRECT_URI",
        "http://localhost:8000/auth/callback",
    )

    with pytest.raises(ValueError, match="GOOGLE_OAUTH_CLIENT_ID"):
        AuthConfig.from_env()


@pytest.mark.unit
def test_auth_config_missing_client_secret_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """from_env raises ValueError listing GOOGLE_OAUTH_CLIENT_SECRET as missing."""
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "id")
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_SECRET", raising=False)
    monkeypatch.setenv(
        "GOOGLE_OAUTH_REDIRECT_URI",
        "http://localhost:8000/auth/callback",
    )

    with pytest.raises(ValueError, match="GOOGLE_OAUTH_CLIENT_SECRET"):
        AuthConfig.from_env()


@pytest.mark.unit
def test_auth_config_missing_redirect_uri_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """from_env raises ValueError listing GOOGLE_OAUTH_REDIRECT_URI as missing."""
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "secret")
    monkeypatch.delenv("GOOGLE_OAUTH_REDIRECT_URI", raising=False)

    with pytest.raises(ValueError, match="GOOGLE_OAUTH_REDIRECT_URI"):
        AuthConfig.from_env()


@pytest.mark.unit
def test_auth_config_all_missing_lists_every_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """from_env raises a single ValueError listing every missing env var."""
    for var in (
        "GOOGLE_OAUTH_CLIENT_ID",
        "GOOGLE_OAUTH_CLIENT_SECRET",
        "GOOGLE_OAUTH_REDIRECT_URI",
    ):
        monkeypatch.delenv(var, raising=False)

    with pytest.raises(ValueError, match="GOOGLE_OAUTH_CLIENT_ID") as exc_info:
        AuthConfig.from_env()

    msg = str(exc_info.value)
    assert "GOOGLE_OAUTH_CLIENT_ID" in msg
    assert "GOOGLE_OAUTH_CLIENT_SECRET" in msg
    assert "GOOGLE_OAUTH_REDIRECT_URI" in msg


@pytest.mark.unit
def test_auth_config_empty_string_treated_as_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """from_env treats empty-string env vars as missing."""
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "secret")
    monkeypatch.setenv(
        "GOOGLE_OAUTH_REDIRECT_URI",
        "http://localhost:8000/auth/callback",
    )

    with pytest.raises(ValueError, match="GOOGLE_OAUTH_CLIENT_ID"):
        AuthConfig.from_env()


@pytest.mark.unit
def test_auth_config_custom_redirect_uri(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """from_env honors the configured redirect URI."""
    for var, value in _BASE_ENV.items():
        monkeypatch.setenv(var, value)
    monkeypatch.setenv(
        "GOOGLE_OAUTH_REDIRECT_URI",
        "https://example.com/callback",
    )

    config = AuthConfig.from_env()

    assert config.redirect_uri == "https://example.com/callback"


@pytest.mark.unit
def test_get_auth_config_delegates_to_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """get_auth_config returns the same AuthConfig as from_env."""
    for var, value in _BASE_ENV.items():
        monkeypatch.setenv(var, value)

    config = get_auth_config()

    assert config.client_id == "test-client-id"
    assert config.client_secret == "test-secret"
    assert config.redirect_uri == "http://localhost:8000/auth/callback"


# ---------------------------------------------------------------------------
# build_oauth_url
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_build_oauth_url_auto_generates_state_when_none() -> None:
    """build_oauth_url generates a non-empty state when none is supplied."""
    config = _make_config()

    url, state = build_oauth_url(config, state=None)

    assert state
    assert f"state={state}" in url
    assert "client_id=test-client-id" in url
    assert "response_type=code" in url
    assert "access_type=offline" in url


@pytest.mark.unit
def test_build_oauth_url_includes_explicit_state() -> None:
    """build_oauth_url echoes back an explicitly supplied state."""
    config = _make_config()
    state = "abc123xyz"

    url, returned_state = build_oauth_url(config, state=state)

    assert returned_state == state
    assert f"state={state}" in url


@pytest.mark.unit
def test_build_oauth_url_includes_all_scopes() -> None:
    """build_oauth_url includes every configured GCS scope."""
    config = _make_config()

    url, _ = build_oauth_url(config)

    assert "devstorage.read_write" in url
    assert "cloud-platform" in url


@pytest.mark.unit
def test_build_oauth_url_url_encodes_special_characters_in_state() -> None:
    """build_oauth_url URL-encodes special characters in state."""
    config = _make_config()
    state = "abc123!@#$%^&*()"

    url, _ = build_oauth_url(config, state=state)

    assert "state=" in url
    # '@' and '!' are URL-encoded by urlencode.
    assert "%40" in url or "%21" in url


@pytest.mark.unit
def test_build_oauth_url_handles_long_state() -> None:
    """build_oauth_url handles a long state value without truncation."""
    config = _make_config()
    long_state = "x" * 1000

    url, returned_state = build_oauth_url(config, state=long_state)

    assert returned_state == long_state
    assert "test-client-id" in url
    assert long_state in url
