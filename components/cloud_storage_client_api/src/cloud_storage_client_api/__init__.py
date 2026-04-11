"""Cloud Storage Client API package.

Public surface:
- ``CloudStorageClient``: the abstract interface every backend implements
- ``ObjectInfo``: provider-agnostic object metadata returned by operations
- ``DeleteResult``: canonical delete response metadata
- ``AuthenticationError``
- ``ContainerNotFoundError``
- ``InvalidContainerError``
- ``InvalidObjectNameError``
- ``InvalidFileObjectError``
- ``LocalFileAccessError``
- ``ObjectNotFoundError``
- ``StorageBackendError``
"""

from cloud_storage_client_api.client import CloudStorageClient as CloudStorageClient
from cloud_storage_client_api.exceptions import AuthenticationError as AuthenticationError
from cloud_storage_client_api.exceptions import ContainerNotFoundError as ContainerNotFoundError
from cloud_storage_client_api.exceptions import InvalidContainerError as InvalidContainerError
from cloud_storage_client_api.exceptions import InvalidFileObjectError as InvalidFileObjectError
from cloud_storage_client_api.exceptions import InvalidObjectNameError as InvalidObjectNameError
from cloud_storage_client_api.exceptions import LocalFileAccessError as LocalFileAccessError
from cloud_storage_client_api.exceptions import ObjectNotFoundError as ObjectNotFoundError
from cloud_storage_client_api.exceptions import StorageBackendError as StorageBackendError
from cloud_storage_client_api.models import DeleteResult as DeleteResult
from cloud_storage_client_api.models import ObjectInfo as ObjectInfo

__all__ = [
    "AuthenticationError",
    "CloudStorageClient",
    "ContainerNotFoundError",
    "DeleteResult",
    "InvalidContainerError",
    "InvalidFileObjectError",
    "InvalidObjectNameError",
    "LocalFileAccessError",
    "ObjectInfo",
    "ObjectNotFoundError",
    "StorageBackendError",
]
