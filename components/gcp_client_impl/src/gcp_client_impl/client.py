"""GCP Cloud Storage implementation of CloudStorageClient."""

from __future__ import annotations

import base64
import binascii
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

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

try:
    from google.api_core import exceptions as google_exceptions
    from google.cloud import storage
    from google.oauth2 import credentials as oauth2_credentials
    from google.oauth2 import service_account
except ImportError:  # pragma: no cover - handled by runtime guard
    google_exceptions = None  # type: ignore[assignment]
    storage = None
    service_account = None  # type: ignore[assignment]
    oauth2_credentials = None  # type: ignore[assignment]


def _map_provider_error(  # noqa: PLR0912
    exc: Exception,
    *,
    container: str,
    object_name: str | None = None,
    treat_not_found_as_container: bool = False,
) -> Exception:
    """Map provider-specific errors to shared cloud_storage_api exceptions."""
    if google_exceptions is None:
        return StorageBackendError(str(exc))

    mapped: Exception

    if isinstance(exc, google_exceptions.Forbidden):
        if treat_not_found_as_container:
            mapped = ContainerNotFoundError(f"Container '{container}' not found or access denied")
        else:
            mapped = AuthenticationError("Access denied by cloud provider.")
    elif isinstance(exc, google_exceptions.Unauthorized):
        mapped = AuthenticationError("Authentication failed or access denied by cloud provider.")
    elif isinstance(exc, google_exceptions.NotFound):
        if treat_not_found_as_container:
            mapped = ContainerNotFoundError(f"Container '{container}' not found")
        elif object_name is not None:
            mapped = ObjectNotFoundError(f"Object '{object_name}' not found in bucket '{container}'")
        else:
            mapped = ContainerNotFoundError(f"Container '{container}' not found")
    elif isinstance(exc, google_exceptions.BadRequest):
        if object_name is not None:
            mapped = InvalidObjectNameError(f"Invalid object name '{object_name}'")
        else:
            mapped = InvalidContainerError(f"Invalid container name '{container}'")
    else:
        mapped = StorageBackendError(f"Cloud storage backend operation failed: {exc}")

    return mapped


@dataclass(frozen=True)
class GCPClientConfig:
    """Configuration for GCP Cloud Storage client."""

    project_id: str | None
    credentials_path: str | None
    service_key: str | None
    oauth_token: str | None


class GCPCloudStorageClient(CloudStorageClient):
    """Cloud storage client implementation using Google Cloud Storage (GCS).

    Manages upload, download, deletion, and listing of objects in GCS buckets.
    Supports authentication via service account credentials or default credentials.
    """

    def __init__(
        self,
        *,
        project_id: str | None = None,
        credentials_path: str | None = None,
        oauth_token: str | None = None,
    ) -> None:
        """Initialize the GCP Cloud Storage client.

        Args:
            project_id: GCP project ID (defaults to GOOGLE_CLOUD_PROJECT env var).
            credentials_path: Path to service account key file (defaults to GOOGLE_APPLICATION_CREDENTIALS env var).
            oauth_token: OAuth 2.0 access token for user-delegated authentication.
            Takes priority over service account credentials.
        """
        self._config = GCPClientConfig(
            project_id=project_id or os.getenv("GOOGLE_CLOUD_PROJECT"),
            credentials_path=credentials_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
            service_key=os.getenv("GCP_SERVICE_KEY"),
            oauth_token=oauth_token or os.getenv("GCP_OAUTH_TOKEN"),
        )
        self._storage_client: Any | None = None

    def _require_google_cloud_storage(self) -> None:
        """Ensure google-cloud-storage is installed."""
        if storage is None:
            msg = "google-cloud-storage is not installed. Install dependencies first (for example: `uv sync`)."
            raise StorageBackendError(msg)

    def _build_credentials(self) -> Any | None:
        """Build GCP credentials from configured sources."""
        if self._config.oauth_token:
            if oauth2_credentials is None:
                msg = "google-auth is not installed, cannot build OAuth credentials."
                raise StorageBackendError(msg)
            return oauth2_credentials.Credentials(token=self._config.oauth_token)  # type: ignore[no-untyped-call]

        if self._config.credentials_path:
            return None

        service_key = self._config.service_key
        if not service_key:
            return None

        if service_account is None:
            msg = "google-auth is not installed, so service-account credentials cannot be built."
            raise StorageBackendError(msg)

        try:
            decoded = base64.b64decode(service_key, validate=True).decode("utf-8")
            payload = decoded
        except (binascii.Error, UnicodeDecodeError):
            payload = service_key

        try:
            info = json.loads(payload)
        except json.JSONDecodeError as exc:
            msg = "GCP_SERVICE_KEY must be a valid JSON string or base64-encoded JSON service account key."
            raise StorageBackendError(msg) from exc

        return service_account.Credentials.from_service_account_info(info)  # type: ignore[no-untyped-call]

    def _build_storage_client(self) -> Any:
        """Build and return GCS client with configured credentials."""
        self._require_google_cloud_storage()

        credentials = self._build_credentials()
        if credentials is not None:
            return storage.Client(project=self._config.project_id, credentials=credentials)

        if self._config.credentials_path:
            return storage.Client.from_service_account_json(
                self._config.credentials_path,
                project=self._config.project_id,
            )

        return storage.Client(project=self._config.project_id)

    def _get_storage_client(self) -> Any:
        """Get or lazily initialize the storage client."""
        if self._storage_client is None:
            self._storage_client = self._build_storage_client()
        return self._storage_client

    def _validate_container(self, container: str) -> None:
        """Validate container name is not empty."""
        if not container:
            msg = "Container name cannot be empty."
            raise InvalidContainerError(msg)

    def _validate_object_name(self, object_name: str) -> None:
        """Validate object name is not empty."""
        if not object_name:
            msg = "Object name cannot be empty."
            raise InvalidObjectNameError(msg)

    def _get_bucket(self, container: str) -> Any:
        """Get a bucket by name."""
        return self._get_storage_client().bucket(container)

    def _blob_to_object_info(self, blob: Any) -> ObjectInfo:
        """Convert GCS blob to ObjectInfo.

        Args:
            blob: GCS blob object from google.cloud.storage.

        Returns:
            ObjectInfo with metadata extracted from the blob.
        """
        return ObjectInfo(
            object_name=blob.name,
            version_id=blob.generation,
            data_type=blob.content_type,
            integrity=blob.etag,
            encryption=blob.kms_key_name or None,
            storage_tier=blob.storage_class,
            size_bytes=blob.size,
            updated_at=blob.updated,
            metadata=blob.metadata or {},
        )

    def upload_file(
        self,
        container: str,
        local_path: str,
        remote_path: str,
    ) -> ObjectInfo:
        """Upload a file to cloud storage.

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
            StorageBackendError: If the operation fails.
        """
        self._validate_container(container)
        self._validate_object_name(remote_path)

        try:
            data = Path(local_path).read_bytes()
        except OSError as exc:
            msg = f"Cannot read local file '{local_path}'"
            raise LocalFileAccessError(msg) from exc

        bucket = self._get_bucket(container)
        blob = bucket.blob(remote_path)
        try:
            blob.upload_from_string(data)
            blob.reload()
        except Exception as exc:
            raise _map_provider_error(
                exc,
                container=container,
                object_name=None,
                treat_not_found_as_container=False,
            ) from exc

        return self._blob_to_object_info(blob)

    def upload_obj(
        self,
        container: str,
        file_obj: BinaryIO,
        remote_path: str,
    ) -> ObjectInfo:
        """Upload a binary file-like object to cloud storage.

        Args:
            container: GCS bucket name.
            file_obj: A file-like object opened in binary mode.
            remote_path: Destination object key/path in cloud storage.

        Returns:
            ObjectInfo with metadata about the uploaded object.

        Raises:
            InvalidContainerError: If container is empty.
            InvalidObjectNameError: If remote_path is empty.
            InvalidFileObjectError: If file_obj is not a valid binary readable.
            StorageBackendError: If the operation fails.
        """
        self._validate_container(container)
        self._validate_object_name(remote_path)

        if not hasattr(file_obj, "read") or not callable(file_obj.read):
            msg = "file_obj must be a file-like object with a read() method."
            raise InvalidFileObjectError(msg)

        try:
            bucket = self._get_bucket(container)
            blob = bucket.blob(remote_path)
            raw_content_type = getattr(file_obj, "content_type", None)
            detected_content_type = raw_content_type if isinstance(raw_content_type, str) else None
            blob.upload_from_file(file_obj, content_type=detected_content_type)
            blob.reload()
            return self._blob_to_object_info(blob)
        except (OSError, TypeError) as exc:
            msg = f"Failed to upload from file object: {exc}"
            raise InvalidFileObjectError(msg) from exc
        except Exception as exc:
            raise _map_provider_error(
                exc,
                container=container,
                object_name=remote_path,
                treat_not_found_as_container=True,
            ) from exc

    def download_file(
        self,
        container: str,
        object_name: str,
        file_name: str,
    ) -> ObjectInfo:
        """Download a file from cloud storage.

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
            StorageBackendError: If the operation fails.
        """
        self._validate_container(container)
        self._validate_object_name(object_name)

        bucket = self._get_bucket(container)
        blob = bucket.blob(object_name)

        try:
            exists = blob.exists()
        except Exception as exc:
            raise _map_provider_error(
                exc,
                container=container,
                object_name=object_name,
                treat_not_found_as_container=True,
            ) from exc

        if not exists:
            msg = f"Object '{object_name}' not found in bucket '{container}'"
            raise ObjectNotFoundError(msg)

        try:
            blob.download_to_filename(file_name)
        except OSError as exc:
            msg = f"Cannot write to file '{file_name}': {exc}"
            raise LocalFileAccessError(msg) from exc
        except Exception as exc:
            raise _map_provider_error(
                exc,
                container=container,
                object_name=object_name,
                treat_not_found_as_container=True,
            ) from exc

        try:
            blob.reload()
        except Exception as exc:
            raise _map_provider_error(
                exc,
                container=container,
                object_name=object_name,
                treat_not_found_as_container=True,
            ) from exc

        return self._blob_to_object_info(blob)

    def list_files(self, container: str, prefix: str) -> list[ObjectInfo]:
        """List files in cloud storage.

        Args:
            container: GCS bucket name.
            prefix: Prefix used to filter listed objects.

        Returns:
            Metadata for the objects matching the prefix, sorted in ascending
            lexicographic order by ``object_name``.

        Raises:
            InvalidContainerError: If container is empty.
            StorageBackendError: If the operation fails.
        """
        self._validate_container(container)

        bucket = self._get_bucket(container)
        try:
            blobs = bucket.list_blobs(prefix=prefix)
            objects = [self._blob_to_object_info(blob) for blob in blobs]
        except Exception as exc:
            raise _map_provider_error(exc, container=container) from exc

        return sorted(objects, key=lambda object_info: object_info.object_name)

    def delete_file(self, container: str, object_name: str) -> DeleteResult:
        """Delete a file from cloud storage.

        Args:
            container: GCS bucket name.
            object_name: Key of the object to delete.

        Returns:
            DeleteResult with deletion metadata.

        Raises:
            InvalidContainerError: If container is empty.
            InvalidObjectNameError: If object_name is empty.
            ObjectNotFoundError: If the object does not exist.
            StorageBackendError: If the operation fails.
        """
        self._validate_container(container)
        self._validate_object_name(object_name)

        bucket = self._get_bucket(container)
        blob = bucket.blob(object_name)

        try:
            exists = blob.exists()
        except Exception as exc:
            raise _map_provider_error(
                exc,
                container=container,
                object_name=object_name,
                treat_not_found_as_container=True,
            ) from exc

        if not exists:
            msg = f"Object '{object_name}' not found in bucket '{container}'"
            raise ObjectNotFoundError(msg)

        generation = blob.generation
        try:
            blob.delete()
        except Exception as exc:
            raise _map_provider_error(
                exc,
                container=container,
                object_name=object_name,
                treat_not_found_as_container=True,
            ) from exc

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
            StorageBackendError: If the operation fails.
        """
        self._validate_container(container)
        self._validate_object_name(object_name)

        bucket = self._get_bucket(container)
        blob = bucket.blob(object_name)

        try:
            exists = blob.exists()
        except Exception as exc:
            raise _map_provider_error(
                exc,
                container=container,
                object_name=object_name,
                treat_not_found_as_container=True,
            ) from exc

        if not exists:
            msg = f"Object '{object_name}' not found in bucket '{container}'"
            raise ObjectNotFoundError(msg)

        try:
            blob.reload()
        except Exception as exc:
            raise _map_provider_error(
                exc,
                container=container,
                object_name=object_name,
                treat_not_found_as_container=True,
            ) from exc

        return self._blob_to_object_info(blob)
