"""Unit tests for GCPCloudStorageClient._build_storage_client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gcp_client_impl.client import GCPCloudStorageClient


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear all GCP credential env vars before constructing the client."""
    for var in (
        "GOOGLE_CLOUD_PROJECT",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "GCP_SERVICE_KEY",
        "GCP_OAUTH_TOKEN",
    ):
        monkeypatch.delenv(var, raising=False)


@pytest.mark.unit
def test_build_storage_client_uses_from_service_account_json_when_credentials_path_given(
    clean_env: None,  # noqa: ARG001 — fixture for env-var clearing
) -> None:
    """_build_storage_client routes credentials_path through from_service_account_json."""
    client = GCPCloudStorageClient(project_id="proj", credentials_path="/creds/key.json")

    mock_gcs = MagicMock()
    with patch("gcp_client_impl.client.storage.Client.from_service_account_json") as mock_factory:
        mock_factory.return_value = mock_gcs
        result = client._build_storage_client()

    mock_factory.assert_called_once_with("/creds/key.json", project="proj")
    assert result is mock_gcs


@pytest.mark.unit
def test_build_storage_client_uses_credentials_when_oauth_token_set(
    clean_env: None,  # noqa: ARG001
) -> None:
    """_build_storage_client constructs storage.Client with explicit credentials."""
    client = GCPCloudStorageClient(project_id="proj", oauth_token="ya29.test-token")

    mock_gcs = MagicMock()
    with patch("gcp_client_impl.client.storage.Client") as mock_client_class:
        mock_client_class.return_value = mock_gcs
        result = client._build_storage_client()

    mock_client_class.assert_called_once()
    _, kwargs = mock_client_class.call_args
    assert kwargs["project"] == "proj"
    assert kwargs["credentials"] is not None
    assert result is mock_gcs


@pytest.mark.unit
def test_build_storage_client_falls_back_to_application_default_credentials(
    clean_env: None,  # noqa: ARG001
) -> None:
    """_build_storage_client falls back to ADC when no explicit credentials."""
    client = GCPCloudStorageClient(project_id="proj")

    mock_gcs = MagicMock()
    with patch("gcp_client_impl.client.storage.Client") as mock_client_class:
        mock_client_class.return_value = mock_gcs
        result = client._build_storage_client()

    mock_client_class.assert_called_once_with(project="proj")
    assert result is mock_gcs


@pytest.mark.unit
def test_get_storage_client_caches_result(
    clean_env: None,  # noqa: ARG001
) -> None:
    """_get_storage_client builds the client lazily and caches it."""
    client = GCPCloudStorageClient(project_id="proj")

    mock_gcs = MagicMock()
    with patch("gcp_client_impl.client.storage.Client") as mock_client_class:
        mock_client_class.return_value = mock_gcs

        first = client._get_storage_client()
        second = client._get_storage_client()

    assert first is second  # Should only build once despite two calls.
    mock_client_class.assert_called_once()
