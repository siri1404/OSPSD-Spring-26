"""GCP Cloud Storage implementation of CloudStorageClient."""

from __future__ import annotations

import base64
import binascii
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

from cloud_storage_client_api import CloudStorageClient, ObjectInfo

try:
    from google.cloud import storage
    from google.oauth2 import service_account
except ImportError:  # pragma: no cover - handled by runtime guard
    storage = None
    service_account = None  # type: ignore[assignment]


@dataclass(frozen=True)
class GCPClientConfig:
    """Configuration for GCP Cloud Storage client."""

    bucket_name: str | None
    project_id: str | None
    credentials_path: str | None
    service_key: str | None


class GCPCloudStorageClient(CloudStorageClient):
    """Cloud storage client implementation using Google Cloud Storage (GCS).

    Manages upload, download, deletion, and listing of objects in GCS buckets.
    Supports authentication via service account credentials or default credentials.
    """

    def __init__(
        self,
        *,
        bucket_name: str | None = None,
        project_id: str | None = None,
        credentials_path: str | None = None,
    ) -> None:
        """Initialize the GCP Cloud Storage client.

        Args:
            bucket_name: GCS bucket name (defaults to GCS_BUCKET_NAME env var).
            project_id: GCP project ID (defaults to GOOGLE_CLOUD_PROJECT env var).
            credentials_path: Path to service account key file (defaults to GOOGLE_APPLICATION_CREDENTIALS env var).
        """
        self._config = GCPClientConfig(
            bucket_name=bucket_name or os.getenv("GCS_BUCKET_NAME"),
            project_id=project_id or os.getenv("GOOGLE_CLOUD_PROJECT"),
            credentials_path=credentials_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
            service_key=os.getenv("GCP_SERVICE_KEY"),
        )
        self._storage_client: Any | None = None

    def _require_google_cloud_storage(self) -> None:
        if storage is None:
            msg = "google-cloud-storage is not installed. Install dependencies first (for example: `uv sync`)."
            raise RuntimeError(msg)

    def _build_credentials(self) -> Any | None:
        if self._config.credentials_path:
            return None

        service_key = self._config.service_key
        if not service_key:
            return None

        if service_account is None:
            msg = "google-auth is not installed, so service-account credentials cannot be built."
            raise RuntimeError(msg)

        try:
            decoded = base64.b64decode(service_key, validate=True).decode("utf-8")
            payload = decoded
        except (binascii.Error, UnicodeDecodeError):
            payload = service_key

        try:
            info = json.loads(payload)
        except json.JSONDecodeError as exc:
            msg = "GCP_SERVICE_KEY must be a valid JSON string or base64-encoded JSON service account key."
            raise RuntimeError(msg) from exc

        return service_account.Credentials.from_service_account_info(info)  # type: ignore[no-untyped-call]

    def _build_storage_client(self) -> Any:
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
        if self._storage_client is None:
            self._storage_client = self._build_storage_client()
        return self._storage_client

    def _get_bucket_name(self) -> str:
        if not self._config.bucket_name:
            msg = "GCS bucket is not configured. Set `GCS_BUCKET_NAME` or pass `bucket_name` to GCPCloudStorageClient."
            raise RuntimeError(msg)
        return self._config.bucket_name

    def _get_bucket(self) -> Any:
        return self._get_storage_client().bucket(self._get_bucket_name())

    def _blob_to_object_info(self, blob: Any) -> ObjectInfo:
        """Convert GCS blob to ObjectInfo."""
        return ObjectInfo(
            key=blob.name,
            size_bytes=blob.size,
            etag=blob.etag,
            updated_at=blob.updated,
            content_type=blob.content_type,
            metadata=blob.metadata or {},
        )

    def upload_file(self, *, local_path: str, key: str, content_type: str | None = None) -> ObjectInfo:
        """Upload a file to cloud storage.

        Args:
            local_path: Path to the local file to upload.
            key: Destination key/path in cloud storage.
            content_type: Optional MIME type for the object.

        Returns:
            ObjectInfo with metadata about the uploaded object.
        """
        try:
            data = Path(local_path).read_bytes()
        except OSError as exc:
            msg = f"Cannot read local file '{local_path}'"
            raise FileNotFoundError(msg) from exc

        return self.upload_bytes(data=data, key=key, content_type=content_type)

    def upload_bytes(
        self,
        *,
        data: bytes,
        key: str,
        content_type: str | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> ObjectInfo:
        """Upload bytes to cloud storage.

        Args:
            data: Raw bytes to upload.
            key: Destination key/path in cloud storage.
            content_type: Optional MIME type for the object.
            metadata: Optional custom metadata dictionary.

        Returns:
            ObjectInfo with metadata about the uploaded object.
        """
        bucket = self._get_bucket()
        blob = bucket.blob(key)

        # Set content type if provided
        if content_type:
            blob.content_type = content_type

        # Set custom metadata if provided
        if metadata:
            blob.metadata = dict(metadata)

        # Upload the data
        blob.upload_from_string(data, content_type=content_type)

        # Reload to get updated metadata
        blob.reload()

        return self._blob_to_object_info(blob)

    def download_bytes(self, *, key: str) -> bytes:
        """Download bytes from cloud storage.

        Args:
            key: Key/path of the object to download.

        Returns:
            Raw bytes of the downloaded object.

        Raises:
            FileNotFoundError: If the object does not exist.
        """
        bucket = self._get_bucket()
        blob = bucket.blob(key)

        if not blob.exists():
            msg = f"Object '{key}' not found in bucket '{self._get_bucket_name()}'"
            raise FileNotFoundError(msg)

        return blob.download_as_bytes()  # type: ignore[no-any-return]

    def list(self, *, prefix: str) -> list[ObjectInfo]:
        """List objects in cloud storage with optional prefix filter.

        Args:
            prefix: Filter objects by key prefix.

        Returns:
            List of ObjectInfo for matching objects.
        """
        bucket = self._get_bucket()
        blobs = bucket.list_blobs(prefix=prefix)

        return [self._blob_to_object_info(blob) for blob in blobs]

    def delete(self, *, key: str) -> None:
        """Delete an object from cloud storage.

        Args:
            key: Key/path of the object to delete.

        Raises:
            FileNotFoundError: If the object does not exist.
        """
        bucket = self._get_bucket()
        blob = bucket.blob(key)

        if not blob.exists():
            msg = f"Object '{key}' not found in bucket '{self._get_bucket_name()}'"
            raise FileNotFoundError(msg)

        blob.delete()

    def head(self, *, key: str) -> ObjectInfo | None:
        """Get metadata for an object without downloading its contents.

        Args:
            key: Key/path of the object to query.

        Returns:
            ObjectInfo with metadata if object exists, None otherwise.
        """
        bucket = self._get_bucket()
        blob = bucket.blob(key)

        if not blob.exists():
            return None

        # Reload to get fresh metadata
        blob.reload()

        return self._blob_to_object_info(blob)
