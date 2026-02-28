"""Cloud Storage Client API - Abstract client interface and DI utilities."""

from cloud_storage_client_api.client import CloudStorageClient as CloudStorageClient
from cloud_storage_client_api.client import ObjectInfo as ObjectInfo
from cloud_storage_client_api.di import get_client as get_client
from cloud_storage_client_api.di import register_get_client as register_get_client
