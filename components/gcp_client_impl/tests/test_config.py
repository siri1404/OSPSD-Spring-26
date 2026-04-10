"""Unit tests for GCPCloudStorageClient config and construction."""

from __future__ import annotations

import pytest
from gcp_client_impl.client import GCPCloudStorageClient


@pytest.mark.unit
class TestGCPClientConfig:
    """Tests for constructor argument/env-var precedence."""

    def test_kwargs_take_precedence_over_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "env-project")
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/env/creds.json")
        monkeypatch.setenv("GCP_OAUTH_TOKEN", "env-token")

        client = GCPCloudStorageClient(
            project_id="kwarg-project",
            credentials_path="/kwarg/creds.json",
            oauth_token="kwarg-token",
        )

        assert client._config.project_id == "kwarg-project"
        assert client._config.credentials_path == "/kwarg/creds.json"
        assert client._config.oauth_token == "kwarg-token"

    def test_env_vars_used_as_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "env-project")
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/env/key.json")
        monkeypatch.setenv("GCP_SERVICE_KEY", '{"type":"service_account"}')
        monkeypatch.setenv("GCP_OAUTH_TOKEN", "env-token")

        client = GCPCloudStorageClient()

        assert client._config.project_id == "env-project"
        assert client._config.credentials_path == "/env/key.json"
        assert client._config.service_key == '{"type":"service_account"}'
        assert client._config.oauth_token == "env-token"

    def test_no_bucket_in_config_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
        monkeypatch.delenv("GCP_SERVICE_KEY", raising=False)
        monkeypatch.delenv("GCP_OAUTH_TOKEN", raising=False)

        client = GCPCloudStorageClient()

        assert not hasattr(client._config, "bucket_name")
        assert client._config.project_id is None
