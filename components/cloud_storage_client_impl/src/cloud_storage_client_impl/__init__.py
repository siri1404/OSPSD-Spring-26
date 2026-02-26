from cloud_storage_client_api.di import register_get_client
from cloud_storage_client_impl.client import GCPCloudStorageClient


def get_gcp_client_factory() -> GCPCloudStorageClient:
    return GCPCloudStorageClient()

register_get_client(get_gcp_client_factory, name="gcp")
register_get_client(get_gcp_client_factory)