"""Unit tests for GCPCloudStorageClient credential construction."""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest
from cloud_storage_api.exceptions import StorageBackendError
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
            result = GCPCloudStorageClient()._build_credentials()

        assert result is mock_creds
        mock_sa.Credentials.from_service_account_info.assert_called_once_with(fake_info)

    def test_raises_for_invalid_service_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GCP_SERVICE_KEY", "not-valid-json-!!!")
        monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
        with patch("gcp_client_impl.client.service_account"), pytest.raises(StorageBackendError, match="GCP_SERVICE_KEY"):
            GCPCloudStorageClient()._build_credentials()


def _make_client(
    *,
    oauth_token: str | None = None,
    service_key: str | None = None,
    credentials_path: str | None = None,
) -> GCPCloudStorageClient:
    """Create a client with explicit config and without env lookups."""
    client = GCPCloudStorageClient.__new__(GCPCloudStorageClient)
    client._config = GCPClientConfig(
        project_id="test-project",
        credentials_path=credentials_path,
        service_key=service_key,
        oauth_token=oauth_token,
    )
    client._storage_client = None
    return client


@pytest.mark.unit
class TestOAuthTokenCredentials:
    """Tests for OAuth token credential path."""

    def test_oauth_token_returns_credentials_object(self) -> None:
        mock_creds = MagicMock()
        mock_creds_class = MagicMock(return_value=mock_creds)

        client = _make_client(oauth_token="ya29.test-token")

        with patch("gcp_client_impl.client.oauth2_credentials") as mock_module:
            mock_module.Credentials = mock_creds_class
            result = client._build_credentials()

        mock_creds_class.assert_called_once_with(token="ya29.test-token")
        assert result is mock_creds

    def test_oauth_token_takes_priority_over_service_key(self) -> None:
        mock_creds = MagicMock()
        mock_creds_class = MagicMock(return_value=mock_creds)

        client = _make_client(oauth_token="ya29.test-token", service_key="service-key")

        with patch("gcp_client_impl.client.oauth2_credentials") as mock_module:
            mock_module.Credentials = mock_creds_class
            result = client._build_credentials()

        mock_creds_class.assert_called_once_with(token="ya29.test-token")
        assert result is mock_creds

    def test_missing_oauth2_credentials_module_raises(self) -> None:
        client = _make_client(oauth_token="ya29.test-token")

        with (
            patch("gcp_client_impl.client.oauth2_credentials", None),
            pytest.raises(StorageBackendError, match="google-auth is not installed"),
        ):
            client._build_credentials()


@pytest.mark.unit
class TestOAuthTokenInit:
    """Tests for oauth_token handling in __init__."""

    def test_oauth_token_stored_in_config(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            client = GCPCloudStorageClient(oauth_token="ya29.my-token")
        assert client._config.oauth_token == "ya29.my-token"

    def test_oauth_token_defaults_to_none_when_not_set(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            client = GCPCloudStorageClient()
        assert client._config.oauth_token is None

    def test_oauth_token_read_from_env_var(self) -> None:
        with patch.dict(os.environ, {"GCP_OAUTH_TOKEN": "ya29.from-env"}, clear=True):
            client = GCPCloudStorageClient()
        assert client._config.oauth_token == "ya29.from-env"

    def test_explicit_oauth_token_overrides_env_var(self) -> None:
        with patch.dict(os.environ, {"GCP_OAUTH_TOKEN": "ya29.from-env"}, clear=True):
            client = GCPCloudStorageClient(oauth_token="ya29.explicit")
        assert client._config.oauth_token == "ya29.explicit"
