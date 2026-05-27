"""Cloud storage adapter implementation using generated OpenAPI client."""

from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

from cloud_storage_client_api import CloudStorageClient, ObjectInfo
from cloud_storage_client_api.exceptions import ObjectNotFoundError, StorageOperationError, StorageValidationError
from cloud_storage_service_api_client import AuthenticatedClient
from cloud_storage_service_api_client.api.storage import (
    delete_object_delete_key_delete,
    download_file_download_key_get,
    head_object_head_key_get,
    list_objects_list_get,
    upload_file_upload_post,
)
from cloud_storage_service_api_client.models.body_upload_file_upload_post import BodyUploadFileUploadPost
from cloud_storage_service_api_client.models.http_validation_error import HTTPValidationError
from cloud_storage_service_api_client.models.list_response import ListResponse
from cloud_storage_service_api_client.models.object_info_response import ObjectInfoResponse
from cloud_storage_service_api_client.types import UNSET, Unset

if TYPE_CHECKING:
    from collections.abc import Mapping


class CloudStorageAdapter(CloudStorageClient):
    """CloudStorageClient implementation backed by a remote service."""

    def __init__(self, base_url: str, token: str) -> None:
        """Initialize adapter with service base URL and bearer token."""
        self._client = AuthenticatedClient(base_url=base_url.rstrip("/"), token=token)

    def upload_file(self, *, local_path: str, key: str, content_type: str | None = None) -> ObjectInfo:
        """Upload a local file through the service-backed adapter."""
        try:
            file_bytes = Path(local_path).read_bytes()
        except OSError as exc:
            msg = f"Local file not found: {local_path}"
            raise ObjectNotFoundError(msg) from exc

        body = BodyUploadFileUploadPost(
            file=file_bytes,  # type: ignore[arg-type]  # Generated model types file as str, but multipart correctly supports bytes.
            key=key,
            content_type=content_type if content_type is not None else UNSET,
        )
        response = upload_file_upload_post.sync_detailed(client=self._client, body=body)
        parsed = response.parsed

        if response.status_code == HTTPStatus.OK and isinstance(parsed, ObjectInfoResponse):
            return self._to_object_info(parsed)

        self._raise_validation_or_runtime("upload_file", parsed, response.status_code)
        msg = "unreachable"
        raise AssertionError(msg)

    def upload_bytes(
        self,
        *,
        data: bytes,
        key: str,
        content_type: str | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> ObjectInfo:
        """Upload raw bytes through the service-backed adapter."""
        body = BodyUploadFileUploadPost(
            file=data,  # type: ignore[arg-type]  # Generated model types file as str, but multipart correctly supports bytes.
            key=key,
            content_type=content_type if content_type is not None else UNSET,
        )

        # Current upload endpoint contract does not define metadata in the request body.
        _ = metadata

        response = upload_file_upload_post.sync_detailed(client=self._client, body=body)
        parsed = response.parsed

        if response.status_code == HTTPStatus.OK and isinstance(parsed, ObjectInfoResponse):
            return self._to_object_info(parsed)

        self._raise_validation_or_runtime("upload_bytes", parsed, response.status_code)
        msg = "unreachable"
        raise AssertionError(msg)

    def download_bytes(self, *, key: str) -> bytes:
        """Download bytes for a given object key."""
        response = download_file_download_key_get.sync_detailed(key=key, client=self._client)

        if response.status_code == HTTPStatus.OK:
            return response.content  # raw bytes from HTTP response body

        if response.status_code == HTTPStatus.NOT_FOUND:
            msg = f"Object not found: {key}"
            raise ObjectNotFoundError(msg)

        # Let the shared helper raise a validation or generic operation error
        self._raise_validation_or_runtime("download_bytes", response.parsed, response.status_code)
        msg = "unreachable"
        raise AssertionError(msg)

    def list(self, *, prefix: str) -> list[ObjectInfo]:
        """List objects with the provided key prefix."""
        response = list_objects_list_get.sync_detailed(client=self._client, prefix=prefix)
        parsed = response.parsed

        if response.status_code == HTTPStatus.OK and isinstance(parsed, ListResponse):
            return [self._to_object_info(item) for item in parsed.objects]

        self._raise_validation_or_runtime("list", parsed, response.status_code)
        msg = "unreachable"
        raise AssertionError(msg)

    def delete(self, *, key: str) -> None:
        """Delete an object by key."""
        response = delete_object_delete_key_delete.sync_detailed(key=key, client=self._client)
        parsed = response.parsed

        if response.status_code == HTTPStatus.NO_CONTENT:
            return
        if response.status_code == HTTPStatus.NOT_FOUND:
            msg = f"Object not found: {key}"
            raise ObjectNotFoundError(msg)

        self._raise_validation_or_runtime("delete", parsed, response.status_code)

    def head(self, *, key: str) -> ObjectInfo | None:
        """Fetch object metadata without downloading content."""
        response = head_object_head_key_get.sync_detailed(key=key, client=self._client)
        parsed = response.parsed

        if response.status_code == HTTPStatus.NOT_FOUND:
            return None
        if response.status_code == HTTPStatus.OK and isinstance(parsed, ObjectInfoResponse):
            return self._to_object_info(parsed)

        self._raise_validation_or_runtime("head", parsed, response.status_code)
        msg = "unreachable"
        raise AssertionError(msg)

    @staticmethod
    def _to_object_info(obj: ObjectInfoResponse) -> ObjectInfo:
        size_bytes = None if isinstance(obj.size_bytes, Unset) else obj.size_bytes
        etag = None if isinstance(obj.etag, Unset) else obj.etag
        updated_at = None if isinstance(obj.updated_at, Unset) else obj.updated_at
        content_type = None if isinstance(obj.content_type, Unset) else obj.content_type

        metadata: dict[str, str] | None
        if isinstance(obj.metadata, Unset) or obj.metadata is None:
            metadata = None
        else:
            metadata = {str(k): str(v) for k, v in obj.metadata.additional_properties.items()}

        return ObjectInfo(
            key=obj.key,
            size_bytes=size_bytes,
            etag=etag,
            updated_at=updated_at,
            content_type=content_type,
            metadata=metadata,
        )

    @staticmethod
    def _raise_validation_or_runtime(operation: str, parsed: object, status_code: int) -> NoReturn:
        if isinstance(parsed, HTTPValidationError):
            msg = f"{operation} request validation failed (status {status_code})"
            raise StorageValidationError(msg)

        msg = f"{operation} failed with status {status_code}"
        raise StorageOperationError(msg)
