"""Integration tests for CloudStorageAdapter DI registration and overrides."""

from __future__ import annotations

import pytest
from cloud_storage_adapter import CloudStorageAdapter
from cloud_storage_client_api.di import get_client, override_get_client


@pytest.mark.integration
class TestAdapterDIIntegration:
    """Integration tests using DI context overrides."""

    def test_override_get_client_returns_adapter_for_named_provider(self) -> None:
        adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="integration-token")
        with override_get_client(lambda: adapter, name="service"):
            resolved = get_client("service")

        assert resolved is adapter

    def test_override_get_client_is_scoped_to_context(self) -> None:
        scoped_name = "service-temp-scoped"
        adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="integration-token")

        with override_get_client(lambda: adapter, name=scoped_name):
            assert get_client(scoped_name) is adapter

        with pytest.raises(RuntimeError, match=scoped_name):
            get_client(scoped_name)
