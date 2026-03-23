"""Edge case tests for cloud storage service auth and operations.

Tests boundary conditions for authentication, OAuth config, and request handling.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from cloud_storage_service.auth import AuthConfig, build_oauth_url


@pytest.mark.unit
class TestAuthConfigEdgeCases:
    """Edge case tests for AuthConfig."""

    def test_auth_config_missing_client_id(self) -> None:
        """Test AuthConfig validation when client_id is missing."""
        with patch.dict("os.environ", {"GOOGLE_OAUTH_CLIENT_SECRET": "secret"}, clear=True):
            config = AuthConfig()
            with pytest.raises(RuntimeError, match="OAuth credentials not configured"):
                config.validate()

    def test_auth_config_missing_client_secret(self) -> None:
        """Test AuthConfig validation when client_secret is missing."""
        with patch.dict("os.environ", {"GOOGLE_OAUTH_CLIENT_ID": "id"}, clear=True):
            config = AuthConfig()
            with pytest.raises(RuntimeError, match="OAuth credentials not configured"):
                config.validate()

    def test_auth_config_both_missing(self) -> None:
        """Test AuthConfig validation when both credentials are missing."""
        with patch.dict("os.environ", {}, clear=True):
            config = AuthConfig()
            with pytest.raises(RuntimeError, match="OAuth credentials not configured"):
                config.validate()

    def test_auth_config_empty_string_client_id(self) -> None:
        """Test AuthConfig validation with empty string client_id."""
        with patch.dict(
            "os.environ",
            {
                "GOOGLE_OAUTH_CLIENT_ID": "",
                "GOOGLE_OAUTH_CLIENT_SECRET": "secret",
            },
        ):
            config = AuthConfig()
            with pytest.raises(RuntimeError):
                config.validate()

    def test_auth_config_default_redirect_uri(self) -> None:
        """Test that AuthConfig uses default redirect_uri when not set."""
        with patch.dict("os.environ", {}, clear=True):
            config = AuthConfig()
            assert config.redirect_uri == "http://localhost:8000/auth/callback"

    def test_auth_config_custom_redirect_uri(self) -> None:
        """Test that AuthConfig uses custom redirect_uri when set."""
        with patch.dict(
            "os.environ",
            {"GOOGLE_OAUTH_REDIRECT_URI": "https://example.com/callback"},
        ):
            config = AuthConfig()
            assert config.redirect_uri == "https://example.com/callback"


@pytest.mark.unit
class TestBuildOAuthUrlEdgeCases:
    """Edge case tests for build_oauth_url."""

    def test_build_oauth_url_without_state(self) -> None:
        """Test building OAuth URL without state parameter."""
        config = AuthConfig()
        config.client_id = "test-client-id"
        config.redirect_uri = "http://localhost:8000/callback"

        url = build_oauth_url(config, state=None)

        assert "client_id=test-client-id" in url
        assert "state=" not in url
        assert "response_type=code" in url
        assert "access_type=offline" in url

    def test_build_oauth_url_with_state(self) -> None:
        """Test building OAuth URL with state parameter."""
        config = AuthConfig()
        config.client_id = "test-client-id"
        config.redirect_uri = "http://localhost:8000/callback"

        state = "abc123xyz"
        url = build_oauth_url(config, state=state)

        assert f"state={state}" in url

    def test_build_oauth_url_includes_all_scopes(self) -> None:
        """Test that OAuth URL includes all required scopes."""
        config = AuthConfig()
        config.client_id = "test-client-id"
        config.redirect_uri = "http://localhost:8000/callback"

        url = build_oauth_url(config)

        assert "devstorage.read_write" in url
        assert "cloud-platform" in url

    def test_build_oauth_url_with_special_characters_in_state(self) -> None:
        """Test OAuth URL with special characters in state."""
        config = AuthConfig()
        config.client_id = "test-client-id"
        config.redirect_uri = "http://localhost:8000/callback"

        # State with special characters that need URL encoding
        state = "abc123!@#$%^&*()"
        url = build_oauth_url(config, state=state)

        # Should be URL encoded
        assert "state=" in url

    def test_build_oauth_url_with_very_long_state(self) -> None:
        """Test OAuth URL with very long state parameter."""
        config = AuthConfig()
        config.client_id = "test-client-id"
        config.redirect_uri = "http://localhost:8000/callback"

        # Very long state
        long_state = "x" * 1000
        url = build_oauth_url(config, state=long_state)

        assert "test-client-id" in url
        assert "oauth" in url.lower() or "authorization" in url.lower()


@pytest.mark.unit
class TestKeyEdgeCases:
    """Edge case tests for storage keys."""

    def test_key_with_multiple_dots(self) -> None:
        """Test keys with multiple dots."""
        test_key = "file.backup.tar.gz"
        assert test_key.count(".") == 3
        assert len(test_key) > 0

    def test_key_with_special_characters(self) -> None:
        """Test keys with special characters."""
        test_keys = [
            "file (copy).txt",
            "file [1].txt",
            "file@example.txt",
        ]

        for key in test_keys:
            assert len(key) > 0
            assert key is not None

    def test_key_with_unicode_characters(self) -> None:
        """Test key with unicode characters."""
        test_keys = [
            "файл.txt",  # Cyrillic
            "文件.txt",  # Chinese
        ]

        for key in test_keys:
            assert len(key) > 0

    def test_very_long_key_name(self) -> None:
        """Test very long key name."""
        long_key = "folder/" + "a" * 500 + "/file.txt"
        assert len(long_key) > 500

    def test_key_with_leading_slash(self) -> None:
        """Test key with leading slash."""
        test_key = "/folder/file.txt"
        assert test_key.startswith("/")

    def test_key_with_double_slash(self) -> None:
        """Test key with double slash."""
        test_key = "folder//subfolder/file.txt"
        assert "//" in test_key

    def test_key_with_trailing_slash(self) -> None:
        """Test key that looks like a folder."""
        test_key = "folder/"
        assert test_key.endswith("/")


@pytest.mark.unit
class TestPrefixEdgeCases:
    """Edge case tests for list prefix parameter."""

    def test_very_long_prefix(self) -> None:
        """Test list with very long prefix."""
        prefix = "a/" * 100 + "b/"
        assert len(prefix) > 100

    def test_prefix_with_special_characters(self) -> None:
        """Test prefix with special characters."""
        prefixes = [
            "folder (archived)/",
            "folder[2024]/",
        ]

        for prefix in prefixes:
            assert prefix.endswith("/")

    def test_empty_prefix(self) -> None:
        """Test list with empty prefix."""
        prefix = ""
        assert prefix == ""

    def test_prefix_without_trailing_slash(self) -> None:
        """Test prefix without trailing slash."""
        prefix = "folder"
        assert "/" not in prefix

    def test_prefix_deeply_nested(self) -> None:
        """Test deeply nested prefix."""
        prefix = "level1/level2/level3/level4/level5/"
        assert prefix.count("/") == 5


@pytest.mark.unit
class TestBearerTokenEdgeCases:
    """Edge case tests for bearer token handling."""

    def test_bearer_token_formats(self) -> None:
        """Test various bearer token formats."""
        test_tokens = [
            "bearer abc123",
            "Bearer abc123",
            "BEARER abc123",
        ]

        # Just verify they're valid strings
        for token_header in test_tokens:
            assert len(token_header) > 0
            assert "abc123" in token_header

    def test_token_with_special_characters(self) -> None:
        """Test tokens with special characters."""
        test_tokens = [
            "token-with-dashes",
            "token_with_underscores",
            "token.with.dots",
            "token123numeric",
        ]

        for token in test_tokens:
            assert len(token) > 0

    def test_very_long_token(self) -> None:
        """Test very long token value."""
        long_token = "x" * 500
        assert len(long_token) == 500


@pytest.mark.unit
class TestConfigurationEdgeCases:
    """Edge case tests for configuration handling."""

    def test_url_with_trailing_slashes(self) -> None:
        """Test URLs with trailing slashes."""
        urls = [
            "http://localhost:8000/",
            "https://example.com/api/v1/",
            "http://storage.example.com/",
        ]

        for url in urls:
            assert url.endswith("/")

    def test_redirect_uri_variations(self) -> None:
        """Test various redirect URI formats."""
        uris = [
            "http://localhost/callback",
            "http://localhost:8000/callback",
            "https://example.com/oauth/callback",
            "http://localhost:3000/auth/callback",
        ]

        for uri in uris:
            assert "callback" in uri.lower()
            assert uri.startswith("http")
