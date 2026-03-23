"""Cloud storage adapter package."""

import os

from cloud_storage_client_api import CloudStorageClient
from cloud_storage_client_api.di import register_get_client

from cloud_storage_adapter.adapter import CloudStorageAdapter

__all__ = ["CloudStorageAdapter"]


def _make_cloud_storage_adapter() -> CloudStorageClient:
    """Factory that creates and returns a CloudStorageAdapter."""
    return CloudStorageAdapter(
        base_url=os.getenv("CLOUD_STORAGE_SERVICE_URL", "http://localhost:8000"),
        token=os.getenv("DEV_AUTH_TOKEN", "dev-token-12345"),
    )


register_get_client(_make_cloud_storage_adapter, name="service")
