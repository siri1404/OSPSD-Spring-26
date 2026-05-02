"""GCP Cloud Storage implementation of CloudStorageClient."""

from __future__ import annotations

import base64
import binascii
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn, cast

from cloud_storage_api import CloudStorageClient, DeleteResult, ObjectInfo
from cloud_storage_api.exceptions import (
    AuthenticationError,
    ContainerNotFoundError,
    InvalidContainerError,
    InvalidFileObjectError,
    InvalidObjectNameError,
    LocalFileAccessError,
    ObjectNotFoundError,
    StorageBackendError,
)
from google.api_core import exceptions as google_exceptions
from google.cloud import storage
from google.oauth2 import credentials as oauth2_credentials
from google.oauth2 import service_account

if TYPE_CHECKING:
    from typing import BinaryIO

    from google.auth.credentials import Credentials

logger = logging.getLogger(__name__)


# ============================================================================
# Error mapping
# ============================================================================


def _raise_read_error(
    exc: google_exceptions.GoogleAPIError,
    *,
    container: str,
    object_name: str | None,
) -> NoReturn:
    """Map a provider error from a read/delete path and re-raise it.

    Read/delete paths assume the bucket exists at the start of the call;
    a 404 therefore points at the object, not the container.
    """
    if isinstance(exc, google_exceptions.Forbidden):
        msg = "Access denied by cloud provider."
        raise AuthenticationError(msg) from exc
    if isinstance(exc, google_exceptions.Unauthorized):
        msg = "Authentication failed or access denied by cloud provider."
        raise AuthenticationError(msg) from exc
    if isinstance(exc, google_exceptions.NotFound):
        if object_name is not None:
            msg = f"Object '{object_name}' not found in bucket '{container}'"
            raise ObjectNotFoundError(msg) from exc
        msg = f"Container '{container}' not found"
        raise ContainerNotFoundError(msg) from exc
    if isinstance(exc, google_exceptions.BadRequest):
        if object_name is not None:
            msg = f"Invalid object name '{object_name}'"
            raise InvalidObjectNameError(msg) from exc
        msg = f"Invalid container name '{container}'"
        raise InvalidContainerError(msg) from exc

    msg = f"Cloud storage backend operation failed: {exc}"
    raise StorageBackendError(msg) from exc


def _raise_write_error(
    exc: google_exceptions.GoogleAPIError,
    *,
    container: str,
    object_name: str | None = None,
) -> NoReturn:
    """Map a provider error from a write path and re-raise it.

    Write paths can't 404 the object (it's being created), so a 404 always
    means the bucket is missing.
    """
    if isinstance(exc, google_exceptions.Forbidden):
        msg = f"Container '{container}' not found or access denied"
        raise ContainerNotFoundError(msg) from exc
    if isinstance(exc, google_exceptions.Unauthorized):
        msg = "Authentication failed or access denied by cloud provider."
        raise AuthenticationError(msg) from exc
    if isinstance(exc, google_exceptions.NotFound):
        msg = f"Container '{container}' not found"
        raise ContainerNotFoundError(msg) from exc
    if isinstance(exc, google_exceptions.BadRequest):
        if object_name is not None:
            msg = f"Invalid object name '{object_name}'"
            raise InvalidObjectNameError(msg) from exc
        msg = f"Invalid container name '{container}'"
        raise InvalidContainerError(msg) from exc

    msg = f"Cloud storage backend operation failed: {exc}"
    raise StorageBackendError(msg) from exc


# ============================================================================
# Configuration
# ============================================================================


@dataclass(frozen=True)
class GCPClientConfig:
    """Configuration for GCP Cloud Storage client."""

    project_id: str | None
    credentials_path: str | None
    service_key: str | None
    oauth_token: str | None


# ============================================================================
# Client
# ============================================================================


class GCPCloudStorageClient(CloudStorageClient):
    """Cloud storage client backed by Google Cloud Storage (GCS).

    Manages upload, download, deletion, and listing of objects in GCS buckets.
    Supports authentication via OAuth bearer token, service account JSON key,
    service account file path, or application-default credentials.
    """

    def __init__(
        self,
        *,
        project_id: str | None = None,
        credentials_path: str | None = None,
        service_key: str | None = None,
        oauth_token: str | None = None,
    ) -> None:
        """Initialize the GCP Cloud Storage client.

        Args:
            project_id: GCP project ID. Falls back to GOOGLE_CLOUD_PROJECT.
            credentials_path: Path to a service-account JSON file. Falls back to
                GOOGLE_APPLICATION_CREDENTIALS.
            service_key: Inline service-account JSON, optionally base64-encoded.
                Falls back to GCP_SERVICE_KEY.
            oauth_token: OAuth 2.0 access token (bearer token only — caller is
                responsible for token freshness). Falls back to GCP_OAUTH_TOKEN.
                Takes priority over service-account credentials.
        """
        self._config = GCPClientConfig(
            project_id=project_id or os.getenv("GOOGLE_CLOUD_PROJECT"),
            credentials_path=(credentials_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")),
            service_key=service_key or os.getenv("GCP_SERVICE_KEY"),
            oauth_token=oauth_token or os.getenv("GCP_OAUTH_TOKEN"),
        )
        self._storage_client: storage.Client | None = None

    # ========================================================================
    # Credential plumbing
    # ========================================================================

    def _build_credentials(self) -> Credentials | None:
        """Build GCP credentials from configured sources, or None for ADC."""
        if self._config.oauth_token:
            # Bearer token only — caller is responsible for token freshness.
            return cast(
                "Credentials",
                oauth2_credentials.Credentials(token=self._config.oauth_token),  # type: ignore[no-untyped-call]
            )

        if self._config.credentials_path:
            # Handled by storage.Client.from_service_account_json downstream.
            return None

        service_key = self._config.service_key
        if not service_key:
            return None

        try:
            decoded = base64.b64decode(service_key, validate=True).decode("utf-8")
            payload = decoded
        except (binascii.Error, UnicodeDecodeError):
            payload = service_key

        try:
            info = json.loads(payload)
        except json.JSONDecodeError as exc:
            msg = (
                "GCP_SERVICE_KEY must be a valid JSON string or "
                "base64-encoded JSON service account key."
            )
            raise StorageBackendError(msg) from exc

        return cast(
            "Credentials",
            service_account.Credentials.from_service_account_info(info),  # type: ignore[no-untyped-call]
        )

    def _build_storage_client(self) -> storage.Client:
        """Build and return a GCS client with configured credentials."""
        credentials = self._build_credentials()
        if credentials is not None:
            return storage.Client(
                project=self._config.project_id,
                credentials=credentials,
            )

        if self._config.credentials_path:
            return storage.Client.from_service_account_json(
                self._config.credentials_path,
                project=self._config.project_id,
            )

        return storage.Client(project=self._config.project_id)

    def _get_storage_client(self) -> storage.Client:
        """Return the lazily-initialized storage client."""
        if self._storage_client is None:
            self._storage_client = self._build_storage_client()
        return self._storage_client

    def _get_bucket(self, container: str) -> storage.Bucket:
        """Get a bucket reference (does not perform an existence check)."""
        return self._get_storage_client().bucket(container)

    # ========================================================================
    # Validation
    # ========================================================================

    @staticmethod
    def _validate_container(container: str) -> None:
        """Validate container name is not empty."""
        if not container:
            msg = "Container name cannot be empty."
            raise InvalidContainerError(msg)

    @staticmethod
    def _validate_object_name(object_name: str) -> None:
        """Validate object name is not empty."""
        if not object_name:
            msg = "Object name cannot be empty."
            raise InvalidObjectNameError(msg)

    # ========================================================================
    # Mapping helpers
    # ========================================================================

    @staticmethod
    def _blob_to_object_info(blob: storage.Blob) -> ObjectInfo:
        """Convert a GCS Blob to a shared ObjectInfo."""
        return ObjectInfo(
            object_name=blob.name,
            version_id=str(blob.generation) if blob.generation is not None else None,
            data_type=blob.content_type,
            integrity=blob.etag,
            encryption=blob.kms_key_name or None,
            storage_tier=blob.storage_class,
            size_bytes=blob.size,
            updated_at=blob.updated,
            metadata=blob.metadata or {},
        )

    # ========================================================================
    # Public API
    # ========================================================================

    def upload_file(
        self,
        container: str,
        local_path: str,
        remote_path: str,
    ) -> ObjectInfo:
        """Upload a local file to cloud storage.

        Args:
            container: GCS bucket name.
            local_path: Path to the local file to upload.
            remote_path: Destination object key/path in cloud storage.

        Returns:
            ObjectInfo with metadata about the uploaded object.

        Raises:
            InvalidContainerError: If container is empty.
            InvalidObjectNameError: If remote_path is empty.
            LocalFileAccessError: If local_path cannot be read.
            ContainerNotFoundError: If the bucket does not exist.
            AuthenticationError: If credentials are invalid or denied.
            StorageBackendError: For other backend failures.
        """
        self._validate_container(container)
        self._validate_object_name(remote_path)

        try:
            data = Path(local_path).read_bytes()
        except OSError as exc:
            msg = f"Cannot read local file '{local_path}'"
            raise LocalFileAccessError(msg) from exc

        logger.debug(
            "gcs.upload_file",
            extra={
                "container": container,
                "remote_path": remote_path,
                "size_bytes": len(data),
            },
        )

        bucket = self._get_bucket(container)
        blob = bucket.blob(remote_path)
        try:
            blob.upload_from_string(data)
            blob.reload()
        except google_exceptions.GoogleAPIError as exc:
            _raise_write_error(exc, container=container, object_name=remote_path)

        return self._blob_to_object_info(blob)

    def upload_obj(
        self,
        container: str,
        file_obj: BinaryIO,
        remote_path: str,
        content_type: str | None = None,
    ) -> ObjectInfo:
        """Upload a binary file-like object to cloud storage.

        Args:
            container: GCS bucket name.
            file_obj: Binary readable file-like object.
            remote_path: Destination object key.
            content_type: Optional MIME type. Pass explicitly to override the
                SDK's automatic content-type detection.

        Returns:
            ObjectInfo with metadata about the uploaded object.

        Raises:
            InvalidContainerError: If container is empty.
            InvalidObjectNameError: If remote_path is empty.
            InvalidFileObjectError: If file_obj is not readable.
            ContainerNotFoundError: If the bucket does not exist.
            AuthenticationError: If credentials are invalid or denied.
            StorageBackendError: For other backend failures.
        """
        self._validate_container(container)
        self._validate_object_name(remote_path)

        if not hasattr(file_obj, "read") or not callable(file_obj.read):
            msg = "file_obj must be a file-like object with a read() method."
            raise InvalidFileObjectError(msg)

        logger.debug(
            "gcs.upload_obj",
            extra={
                "container": container,
                "remote_path": remote_path,
                "content_type": content_type,
            },
        )

        bucket = self._get_bucket(container)
        blob = bucket.blob(remote_path)
        try:
            blob.upload_from_file(file_obj, content_type=content_type)
            blob.reload()
        except (OSError, TypeError) as exc:
            msg = f"Failed to upload from file object: {exc}"
            raise InvalidFileObjectError(msg) from exc
        except google_exceptions.GoogleAPIError as exc:
            _raise_write_error(exc, container=container, object_name=remote_path)

        return self._blob_to_object_info(blob)

    def download_file(
        self,
        container: str,
        object_name: str,
        file_name: str,
    ) -> ObjectInfo:
        """Download an object to a local file.

        Args:
            container: GCS bucket name.
            object_name: Key of the object to download.
            file_name: Local filesystem path to write the downloaded file to.

        Returns:
            ObjectInfo with metadata about the downloaded object.

        Raises:
            InvalidContainerError: If container is empty.
            InvalidObjectNameError: If object_name is empty.
            LocalFileAccessError: If file_name cannot be written.
            ObjectNotFoundError: If the object does not exist.
            ContainerNotFoundError: If the bucket does not exist.
            StorageBackendError: For other backend failures.
        """
        self._validate_container(container)
        self._validate_object_name(object_name)

        logger.debug(
            "gcs.download_file",
            extra={
                "container": container,
                "object_name": object_name,
                "file_name": file_name,
            },
        )

        bucket = self._get_bucket(container)
        blob = bucket.blob(object_name)

        # Single round-trip: try the download directly and let GCS surface
        # a NotFound, which we then translate. Avoids the exists()->op race
        # and saves a HEAD request.
        try:
            blob.download_to_filename(file_name)
            blob.reload()
        except OSError as exc:
            msg = f"Cannot write to file '{file_name}': {exc}"
            raise LocalFileAccessError(msg) from exc
        except google_exceptions.GoogleAPIError as exc:
            _raise_read_error(exc, container=container, object_name=object_name)

        return self._blob_to_object_info(blob)

    def list_files(self, container: str, prefix: str) -> list[ObjectInfo]:
        """List objects in a container, filtered by prefix.

        Args:
            container: GCS bucket name.
            prefix: Prefix used to filter listed objects.

        Returns:
            ObjectInfo entries sorted ascending by object_name.

        Raises:
            InvalidContainerError: If container is empty.
            ContainerNotFoundError: If the bucket does not exist.
            StorageBackendError: For other backend failures.
        """
        self._validate_container(container)

        logger.debug(
            "gcs.list_files",
            extra={"container": container, "prefix": prefix},
        )

        bucket = self._get_bucket(container)
        try:
            blobs = bucket.list_blobs(prefix=prefix)
            objects = [self._blob_to_object_info(blob) for blob in blobs]
        except google_exceptions.GoogleAPIError as exc:
            _raise_read_error(exc, container=container, object_name=None)

        return sorted(objects, key=lambda info: info.object_name)

    def delete_file(self, container: str, object_name: str) -> DeleteResult:
        """Delete an object from cloud storage.

        Args:
            container: GCS bucket name.
            object_name: Key of the object to delete.

        Returns:
            DeleteResult with deletion metadata.

        Raises:
            InvalidContainerError: If container is empty.
            InvalidObjectNameError: If object_name is empty.
            ObjectNotFoundError: If the object does not exist.
            ContainerNotFoundError: If the bucket does not exist.
            StorageBackendError: For other backend failures.
        """
        self._validate_container(container)
        self._validate_object_name(object_name)

        logger.debug(
            "gcs.delete_file",
            extra={"container": container, "object_name": object_name},
        )

        bucket = self._get_bucket(container)
        blob = bucket.blob(object_name)

        # reload() before delete to capture generation; lets the SDK 404
        # surface naturally instead of doing an exists() pre-check.
        try:
            blob.reload()
        except google_exceptions.GoogleAPIError as exc:
            _raise_read_error(exc, container=container, object_name=object_name)

        generation = blob.generation
        try:
            blob.delete()
        except google_exceptions.GoogleAPIError as exc:
            _raise_read_error(exc, container=container, object_name=object_name)

        return {
            "deleted": True,
            "version_id": str(generation) if generation is not None else None,
            "request_charged": False,
        }

    def get_file_info(self, container: str, object_name: str) -> ObjectInfo:
        """Return metadata for a single stored object.

        Args:
            container: GCS bucket name.
            object_name: Key of the object to inspect.

        Returns:
            ObjectInfo with metadata about the object.

        Raises:
            InvalidContainerError: If container is empty.
            InvalidObjectNameError: If object_name is empty.
            ObjectNotFoundError: If the object does not exist.
            ContainerNotFoundError: If the bucket does not exist.
            StorageBackendError: For other backend failures.
        """
        self._validate_container(container)
        self._validate_object_name(object_name)

        logger.debug(
            "gcs.get_file_info",
            extra={"container": container, "object_name": object_name},
        )

        bucket = self._get_bucket(container)
        blob = bucket.blob(object_name)

        try:
            blob.reload()
        except google_exceptions.GoogleAPIError as exc:
            _raise_read_error(exc, container=container, object_name=object_name)

        return self._blob_to_object_info(blob)
