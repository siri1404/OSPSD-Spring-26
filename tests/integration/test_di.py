"""Integration tests for dependency injection and client registration."""

import gcp_client_impl
from cloud_storage_client_api.di import get_client


def test_importing_impl_injects_factory() -> None:
    client = get_client()
    assert client.__class__.__name__ == "GCPCloudStorageClient"
