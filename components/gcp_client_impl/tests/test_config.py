"""Unit tests for GCPCloudStorageClient construction and config reading."""

from __future__ import annotations

import pytest
from gcp_client_impl.client import GCPCloudStorageClient


@pytest.mark.unit
class TestGCPClientConfig:
    """Tests for GCPCloudStorageClient config and construction."""

    def test_kwargs_take_precedence_over_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GCS_BUCKET_NAME", "env-bucket")
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "env-project")

        client = GCPCloudStorageClient(bucket_name="kwarg-bucket", project_id="kwarg-project")

        assert client._config.bucket_name == "kwarg-bucket"
        assert client._config.project_id == "kwarg-project"

    def test_env_vars_used_as_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GCS_BUCKET_NAME", "env-bucket")
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "env-project")
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/creds/key.json")

        client = GCPCloudStorageClient()

        assert client._config.bucket_name == "env-bucket"
        assert client._config.credentials_path == "/creds/key.json"

    def test_get_bucket_name_raises_when_not_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GCS_BUCKET_NAME", raising=False)
        client = GCPCloudStorageClient()
        with pytest.raises(RuntimeError, match="GCS_BUCKET_NAME"):
            client._get_bucket_name()
