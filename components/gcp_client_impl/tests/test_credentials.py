"""Unit tests for GCPCloudStorageClient._build_credentials."""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest
from gcp_client_impl.client import GCPClientConfig, GCPCloudStorageClient


@pytest.mark.unit
class TestBuildCredentials:
    """Tests for GCPCloudStorageClient._build_credentials."""

    def test_returns_none_when_credentials_path_is_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GCP_SERVICE_KEY", raising=False)
        client = GCPCloudStorageClient(credentials_path="/path/key.json")
        assert client._build_credentials() is None

    def test_parses_raw_json_service_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_info = {"type": "service_account", "project_id": "proj"}
        monkeypatch.setenv("GCP_SERVICE_KEY", json.dumps(fake_info))
        monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)

        mock_creds = MagicMock()
        with patch("gcp_client_impl.client.service_account") as mock_sa:
            mock_sa.Credentials.from_service_account_info.return_value = mock_creds
            result = GCPCloudStorageClient(bucket_name="b")._build_credentials()

        assert result is mock_creds
        mock_sa.Credentials.from_service_account_info.assert_called_once_with(fake_info)

    def test_raises_for_invalid_service_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GCP_SERVICE_KEY", "not-valid-json-!!!")
        monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
        with patch("gcp_client_impl.client.service_account"), pytest.raises(RuntimeError, match="GCP_SERVICE_KEY"):
            GCPCloudStorageClient(bucket_name="b")._build_credentials()


def _make_client(
    *,
    oauth_token: str | None = None,
    service_key: str | None = None,
    credentials_path: str | None = None,
) -> GCPCloudStorageClient:
    """Create a GCPCloudStorageClient with controlled config (no env vars)."""
    client = GCPCloudStorageClient.__new__(GCPCloudStorageClient)
    client._config = GCPClientConfig(
        bucket_name="test-bucket",
        project_id="test-project",
        credentials_path=credentials_path,
        service_key=service_key,
        oauth_token=oauth_token,
    )
    client._storage_client = None
    return client


# OAuth 2.0 token tests
@pytest.mark.unit
class TestOAuthTokenCredentials:
    """Tests for OAuth 2.0 access token credential path."""

    def test_oauth_token_returns_credentials_object(self) -> None:
        """OAuth token should produce a google.oauth2.credentials.Credentials object."""
        mock_creds = MagicMock()
        mock_creds_class = MagicMock(return_value=mock_creds)

        client = _make_client(oauth_token="ya29.test-token")

        with patch("gcp_client_impl.client.oauth2_credentials") as mock_module:
            mock_module.Credentials = mock_creds_class
            result = client._build_credentials()

        mock_creds_class.assert_called_once_with(token="ya29.test-token")
        assert result is mock_creds

    def test_oauth_token_takes_priority_over_service_key(self) -> None:
        """OAuth token should be used even when a service key is also present."""
        mock_creds = MagicMock()
        mock_creds_class = MagicMock(return_value=mock_creds)

        client = _make_client(oauth_token="ya29.test-token", service_key="some-service-key")

        with patch("gcp_client_impl.client.oauth2_credentials") as mock_module:
            mock_module.Credentials = mock_creds_class
            result = client._build_credentials()

        mock_creds_class.assert_called_once_with(token="ya29.test-token")
        assert result is mock_creds

    def test_oauth_token_takes_priority_over_credentials_path(self) -> None:
        """OAuth token should be used even when credentials_path is also set."""
        mock_creds = MagicMock()
        mock_creds_class = MagicMock(return_value=mock_creds)

        client = _make_client(
            oauth_token="ya29.test-token",
            credentials_path="/some/path/creds.json",
        )

        with patch("gcp_client_impl.client.oauth2_credentials") as mock_module:
            mock_module.Credentials = mock_creds_class
            result = client._build_credentials()

        mock_creds_class.assert_called_once_with(token="ya29.test-token")
        assert result is mock_creds

    def test_missing_oauth2_credentials_module_raises(self) -> None:
        """RuntimeError should be raised if google-auth is not installed."""
        client = _make_client(oauth_token="ya29.test-token")

        with (
            patch("gcp_client_impl.client.oauth2_credentials", None),
            pytest.raises(RuntimeError, match="google-auth is not installed"),
        ):
            client._build_credentials()

    def test_empty_oauth_token_falls_through_to_service_key(self) -> None:
        """A None oauth_token should fall through to the service key path."""
        client = _make_client(oauth_token=None, service_key=None)

        with patch("gcp_client_impl.client.oauth2_credentials") as mock_module:
            mock_module.Credentials = MagicMock()
            result = client._build_credentials()

        mock_module.Credentials.assert_not_called()
        assert result is None


# OAuth token passed through __init__
@pytest.mark.unit
class TestOAuthTokenInit:
    """Tests for oauth_token parameter in __init__."""

    def test_oauth_token_stored_in_config(self) -> None:
        """oauth_token passed to __init__ should be stored in config."""
        with patch.dict(os.environ, {}, clear=True):
            client = GCPCloudStorageClient(oauth_token="ya29.my-token")
        assert client._config.oauth_token == "ya29.my-token"

    def test_oauth_token_defaults_to_none_when_not_set(self) -> None:
        """oauth_token should be None when not passed and env var not set."""
        with patch.dict(os.environ, {}, clear=True):
            client = GCPCloudStorageClient()
        assert client._config.oauth_token is None

    def test_oauth_token_read_from_env_var(self) -> None:
        """oauth_token should fall back to GCP_OAUTH_TOKEN env var."""
        with patch.dict(os.environ, {"GCP_OAUTH_TOKEN": "ya29.from-env"}, clear=True):
            client = GCPCloudStorageClient()
        assert client._config.oauth_token == "ya29.from-env"

    def test_explicit_oauth_token_overrides_env_var(self) -> None:
        """Explicit oauth_token parameter should take priority over env var."""
        with patch.dict(os.environ, {"GCP_OAUTH_TOKEN": "ya29.from-env"}, clear=True):
            client = GCPCloudStorageClient(oauth_token="ya29.explicit")
        assert client._config.oauth_token == "ya29.explicit"


# Storage client construction with OAuth token
@pytest.mark.unit
class TestStorageClientWithOAuthToken:
    """Tests for storage client construction when OAuth token is provided."""

    def test_storage_client_built_with_oauth_credentials(self) -> None:
        """storage.Client should be initialised with the OAuth credentials object."""
        mock_creds = MagicMock()
        mock_storage_client = MagicMock()

        client = _make_client(oauth_token="ya29.test-token")

        with (
            patch("gcp_client_impl.client.storage") as mock_storage,
            patch("gcp_client_impl.client.oauth2_credentials") as mock_oauth,
        ):
            mock_oauth.Credentials.return_value = mock_creds
            mock_storage.Client.return_value = mock_storage_client

            result = client._build_storage_client()

        mock_oauth.Credentials.assert_called_once_with(token="ya29.test-token")
        mock_storage.Client.assert_called_once_with(
            project="test-project",
            credentials=mock_creds,
        )
        assert result is mock_storage_client

    def test_storage_client_not_rebuilt_on_second_call(self) -> None:
        """_get_storage_client should cache and reuse the client instance."""
        mock_storage_client = MagicMock()
        client = _make_client(oauth_token="ya29.test-token")

        with (
            patch("gcp_client_impl.client.storage") as mock_storage,
            patch("gcp_client_impl.client.oauth2_credentials") as mock_oauth,
        ):
            mock_oauth.Credentials.return_value = MagicMock()
            mock_storage.Client.return_value = mock_storage_client

            first = client._get_storage_client()
            second = client._get_storage_client()

        mock_storage.Client.assert_called_once()
        assert first is second
