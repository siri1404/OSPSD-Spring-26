"""Unit tests for GCPCloudStorageClient._build_credentials."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from gcp_client_impl.client import GCPCloudStorageClient


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
