"""Cloud Storage Client API - Abstract client interface."""

from cloud_storage_client_api.client import CloudStorageClient as CloudStorageClient
from cloud_storage_client_api.client import ObjectInfo as ObjectInfo
from cloud_storage_client_api.di import get_client as get_client
from cloud_storage_client_api.di import override_get_client as override_get_client
from cloud_storage_client_api.di import unregister_get_client as unregister_get_client
