"""Abstract base class for cloud storage clients.

This module defines the provider-agnostic public interface contract. Consumers
depend only on this ABC and the shared result types; they never import an SDK,
transport layer, or concrete implementation package.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import BinaryIO

from cloud_storage_client_api.models import (  # noqa: TC001
    DeleteResult,
    ObjectInfo,
)


class CloudStorageClient(ABC):
    """Abstract base class defining the contract for a cloud storage client."""

    @abstractmethod
    def upload_file(
        self,
        container: str,
        local_path: str,
        remote_path: str,
    ) -> ObjectInfo:
        """Upload a file to cloud storage.

        Args:
            container: Name of the container / bucket to upload to.
            local_path: Path to the local file.
            remote_path: The destination object key / path within the bucket.

        Returns:
            Provider-agnostic metadata describing the uploaded object.

        Raises:
            AuthenticationError: If the provider rejects the caller's credentials.
            ContainerNotFoundError: If container does not exist.
            InvalidContainerError: If container is empty or otherwise invalid.
            InvalidObjectNameError: If remote_path is empty or otherwise invalid.
            LocalFileAccessError: If local_path cannot be read.
            StorageBackendError: If the backing storage provider fails.
        """
        raise NotImplementedError

    @abstractmethod
    def upload_obj(
        self,
        container: str,
        file_obj: BinaryIO,
        remote_path: str,
    ) -> ObjectInfo:
        """Upload a binary file-like object to cloud storage.

        Args:
            container: Name of the container / bucket to upload to.
            file_obj: A file-like object opened in binary mode.
            remote_path: Destination object key / path within the bucket.

        Returns:
            Provider-agnostic metadata describing the uploaded object.

        Raises:
            AuthenticationError: If the provider rejects the caller's credentials.
            ContainerNotFoundError: If container does not exist.
            InvalidContainerError: If container is empty or otherwise invalid.
            InvalidObjectNameError: If remote_path is empty or otherwise invalid.
            InvalidFileObjectError: If file_obj is invalid.
            StorageBackendError: If the backing storage provider fails.
        """
        raise NotImplementedError

    @abstractmethod
    def download_file(
        self,
        container: str,
        object_name: str,
        file_name: str,
    ) -> ObjectInfo:
        """Download a file from cloud storage.

        Args:
            container: Name of the container / bucket to download from.
            object_name: Key of the object to download.
            file_name: Local filesystem path to write the downloaded file to.

        Returns:
            Provider-agnostic metadata describing the downloaded object.

        Raises:
            AuthenticationError: If the provider rejects the caller's credentials.
            ContainerNotFoundError: If container does not exist.
            InvalidContainerError: If container is empty or otherwise invalid.
            InvalidObjectNameError: If object_name is empty or otherwise invalid.
            LocalFileAccessError: If file_name cannot be written locally.
            ObjectNotFoundError: If the requested object does not exist.
            StorageBackendError: If the backing storage provider fails.
        """
        raise NotImplementedError

    @abstractmethod
    def list_files(self, container: str, prefix: str) -> list[ObjectInfo]:
        """List files in cloud storage.

        Args:
            container: Name of the container / bucket to list from.
            prefix: Prefix used to filter listed objects.

        Returns:
            Metadata for the objects matching the prefix, sorted in ascending
            lexicographic order by ``object_name``.

        Raises:
            AuthenticationError: If the provider rejects the caller's credentials.
            ContainerNotFoundError: If container does not exist.
            InvalidContainerError: If container is empty or otherwise invalid.
            StorageBackendError: If the backing storage provider fails.
        """
        raise NotImplementedError

    @abstractmethod
    def delete_file(
        self,
        container: str,
        object_name: str,
    ) -> DeleteResult:
        """Delete a file from cloud storage.

        Args:
            container: Name of the container / bucket containing the object.
            object_name: Key of the object to delete.

        Returns:
            Provider-agnostic deletion metadata. Implementations must provide
            the normalized keys ``deleted``, ``version_id``, and
            ``request_charged``.

        Raises:
            AuthenticationError: If the provider rejects the caller's credentials.
            ContainerNotFoundError: If container does not exist.
            InvalidContainerError: If container is empty or otherwise invalid.
            InvalidObjectNameError: If object_name is empty or otherwise invalid.
            ObjectNotFoundError: If the requested object does not exist.
            StorageBackendError: If the backing storage provider fails.
        """
        raise NotImplementedError

    @abstractmethod
    def get_file_info(self, container: str, object_name: str) -> ObjectInfo:
        """Return metadata for a single stored object.

        Args:
            container: Name of the container / bucket containing the object.
            object_name: Key of the object to inspect.

        Returns:
            Provider-agnostic metadata describing the object.

        Raises:
            AuthenticationError: If the provider rejects the caller's credentials.
            ContainerNotFoundError: If container does not exist.
            InvalidContainerError: If container is empty or otherwise invalid.
            InvalidObjectNameError: If object_name is empty or otherwise invalid.
            ObjectNotFoundError: If the requested object does not exist.
            StorageBackendError: If the backing storage provider fails.
        """
        raise NotImplementedError
