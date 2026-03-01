"""Unit tests for GCPCloudStorageClient._build_storage_client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from gcp_client_impl.client import GCPCloudStorageClient


@pytest.mark.unit
class TestBuildStorageClient:
    """Tests for GCPCloudStorageClient._build_storage_client."""

    def test_uses_from_service_account_json_when_credentials_path_given(self) -> None:
        client = GCPCloudStorageClient(bucket_name="b", project_id="proj", credentials_path="/creds/key.json")
        mock_gcs = MagicMock()
        with patch("gcp_client_impl.client.storage") as mock_storage:
            mock_storage.Client.from_service_account_json.return_value = mock_gcs
            result = client._build_storage_client()

        mock_storage.Client.from_service_account_json.assert_called_once_with("/creds/key.json", project="proj")
        assert result is mock_gcs

    def test_falls_back_to_application_default_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # When no credentials are configured GCS uses Application Default Credentials.
        monkeypatch.delenv("GCP_SERVICE_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)

        client = GCPCloudStorageClient(bucket_name="b", project_id="proj")
        mock_gcs = MagicMock()
        with patch("gcp_client_impl.client.storage") as mock_storage:
            mock_storage.Client.return_value = mock_gcs
            result = client._build_storage_client()

        mock_storage.Client.assert_called_once_with(project="proj")
        assert result is mock_gcs
