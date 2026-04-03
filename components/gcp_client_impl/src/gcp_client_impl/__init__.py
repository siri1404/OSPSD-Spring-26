"""GCP Cloud Storage Client implementation."""

from cloud_storage_client_api.client import CloudStorageClient
from cloud_storage_client_api.di import register_get_client

from gcp_client_impl.client import GCPCloudStorageClient


def _make_gcp_client() -> CloudStorageClient:
    """Factory that creates and returns a GCPCloudStorageClient."""
    return GCPCloudStorageClient()


register_get_client(_make_gcp_client, name="gcp")
register_get_client(_make_gcp_client)
