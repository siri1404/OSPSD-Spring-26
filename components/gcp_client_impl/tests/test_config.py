"""Unit tests for GCPCloudStorageClient config and construction."""

from __future__ import annotations

import base64
import json
from dataclasses import fields
from unittest.mock import MagicMock, patch

import pytest
from cloud_storage_api.exceptions import (
    InvalidContainerError,
    InvalidObjectNameError,
    StorageBackendError,
)

from gcp_client_impl.client import GCPCloudStorageClient

# ============================================================================
# Config and env-var precedence
# ============================================================================


@pytest.mark.unit
def test_constructor_kwargs_take_precedence_over_env_vars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Constructor kwargs override environment variables."""
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "env-project")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/env/creds.json")
    monkeypatch.setenv("GCP_SERVICE_KEY", "env-service-key")
    monkeypatch.setenv("GCP_OAUTH_TOKEN", "env-token")

    client = GCPCloudStorageClient(
        project_id="kwarg-project",
        credentials_path="/kwarg/creds.json",
        service_key="kwarg-service-key",
        oauth_token="kwarg-token",
    )

    assert client._config.project_id == "kwarg-project"
    assert client._config.credentials_path == "/kwarg/creds.json"
    assert client._config.service_key == "kwarg-service-key"
    assert client._config.oauth_token == "kwarg-token"


@pytest.mark.unit
def test_constructor_falls_back_to_env_vars_when_kwargs_omitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Constructor falls back to environment variables when kwargs are None."""
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "env-project")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/env/key.json")
    monkeypatch.setenv("GCP_SERVICE_KEY", '{"type":"service_account"}')
    monkeypatch.setenv("GCP_OAUTH_TOKEN", "env-token")

    client = GCPCloudStorageClient()

    assert client._config.project_id == "env-project"
    assert client._config.credentials_path == "/env/key.json"
    assert client._config.service_key == '{"type":"service_account"}'
    assert client._config.oauth_token == "env-token"


@pytest.mark.unit
def test_service_key_falls_back_to_env_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Constructor falls back to GCP_SERVICE_KEY env var."""
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.delenv("GCP_OAUTH_TOKEN", raising=False)
    monkeypatch.setenv("GCP_SERVICE_KEY", "env-key-only")

    client = GCPCloudStorageClient()

    assert client._config.service_key == "env-key-only"


@pytest.mark.unit
def test_config_includes_only_expected_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GCPClientConfig includes only project_id, credentials_path, service_key, oauth_token."""
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.delenv("GCP_SERVICE_KEY", raising=False)
    monkeypatch.delenv("GCP_OAUTH_TOKEN", raising=False)

    client = GCPCloudStorageClient()

    expected_fields = {"project_id", "credentials_path", "service_key", "oauth_token"}
    actual_fields = {f.name for f in fields(client._config)}
    assert actual_fields == expected_fields


# ============================================================================
# Credential resolution
# ============================================================================


@pytest.mark.unit
def test_oauth_token_path_builds_oauth_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_build_credentials returns OAuth credentials when oauth_token is set."""
    monkeypatch.delenv("GCP_SERVICE_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)

    client = GCPCloudStorageClient(oauth_token="my-token")
    creds = client._build_credentials()

    assert creds is not None
    assert creds.token == "my-token"


@pytest.mark.unit
def test_credentials_path_returns_none_for_downstream_handling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_build_credentials returns None when only credentials_path is set."""
    monkeypatch.delenv("GCP_OAUTH_TOKEN", raising=False)
    monkeypatch.delenv("GCP_SERVICE_KEY", raising=False)

    client = GCPCloudStorageClient(credentials_path="/tmp/creds.json")

    assert client._build_credentials() is None


@pytest.mark.unit
def test_service_key_invalid_json_raises_storage_backend_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_build_credentials raises StorageBackendError for invalid JSON service_key."""
    monkeypatch.delenv("GCP_OAUTH_TOKEN", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)

    client = GCPCloudStorageClient(service_key="not valid json {]")

    with pytest.raises(StorageBackendError, match="JSON"):
        client._build_credentials()


@pytest.mark.unit
def test_service_key_base64_encoded_json_decodes_correctly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_build_credentials decodes base64-encoded JSON service_key."""
    monkeypatch.delenv("GCP_OAUTH_TOKEN", raising=False)

    valid_sa = {
        "type": "service_account",
        "project_id": "test-project",
        "private_key_id": "abc",
        "private_key": "-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----\n",
        "client_email": "sa@test.iam.gserviceaccount.com",
        "client_id": "123",
    }
    encoded = base64.b64encode(json.dumps(valid_sa).encode()).decode()

    with patch(
        "gcp_client_impl.client.service_account.Credentials.from_service_account_info"
    ) as mock_factory:
        mock_factory.return_value = MagicMock()
        client = GCPCloudStorageClient(service_key=encoded)
        client._build_credentials()

        mock_factory.assert_called_once()
        call_args = mock_factory.call_args.args[0]
        assert call_args["project_id"] == "test-project"


@pytest.mark.unit
def test_no_credentials_falls_back_to_adc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_build_credentials returns None for Application Default Credentials."""
    for var in ("GCP_OAUTH_TOKEN", "GCP_SERVICE_KEY", "GOOGLE_APPLICATION_CREDENTIALS"):
        monkeypatch.delenv(var, raising=False)

    client = GCPCloudStorageClient()

    assert client._build_credentials() is None


# ============================================================================
# Validation
# ============================================================================


@pytest.mark.unit
def test_empty_container_raises_invalid_container_error() -> None:
    """_validate_container raises InvalidContainerError for empty string."""
    with pytest.raises(InvalidContainerError, match="empty"):
        GCPCloudStorageClient._validate_container("")


@pytest.mark.unit
def test_empty_object_name_raises_invalid_object_name_error() -> None:
    """_validate_object_name raises InvalidObjectNameError for empty string."""
    with pytest.raises(InvalidObjectNameError, match="empty"):
        GCPCloudStorageClient._validate_object_name("")


@pytest.mark.unit
def test_valid_container_passes_validation() -> None:
    """_validate_container accepts non-empty string."""
    # Should not raise
    GCPCloudStorageClient._validate_container("my-bucket")


@pytest.mark.unit
def test_valid_object_name_passes_validation() -> None:
    """_validate_object_name accepts non-empty string."""
    # Should not raise
    GCPCloudStorageClient._validate_object_name("path/to/file.txt")
