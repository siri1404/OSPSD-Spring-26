"""Cloud storage adapter implementation using generated OpenAPI client."""

from __future__ import annotations

import json
from http import HTTPStatus
from pathlib import Path
from typing import BinaryIO, NoReturn

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


class CloudStorageAdapter(CloudStorageClient):
    """CloudStorageClient implementation backed by a remote service."""

    def __init__(self, base_url: str, token: str) -> None:
        """Initialize adapter with service base URL and bearer token."""
        self._client = AuthenticatedClient(base_url=base_url.rstrip("/"), token=token)

    def upload_file(
        self,
        container: str,
        local_path: str,
        remote_path: str,
    ) -> ObjectInfo:
        """Upload a local file to cloud storage.

        Args:
            container: Name of the container / bucket to upload to.
            local_path: Path to the local file to upload.
            remote_path: Destination object key / path within the bucket.

        Returns:
            Provider-agnostic metadata describing the uploaded object.

        Raises:
            LocalFileAccessError: If local_path cannot be read.
            ObjectNotFoundError: If container does not exist.
            StorageBackendError: If the backing storage provider fails.
        """
        try:
            file_bytes = Path(local_path).read_bytes()
        except OSError as exc:
            msg = f"Local file not found: {local_path}"
            raise LocalFileAccessError(msg) from exc

        body = BodyUploadFileUploadPost(
            file=file_bytes,  # type: ignore[arg-type]  # Generated model types file as str, but multipart correctly supports bytes.
            key=remote_path,
            content_type=UNSET,
        )
        response = upload_file_upload_post.sync_detailed(client=self._client, body=body, container=container)
        parsed = response.parsed

        if response.status_code == HTTPStatus.OK and isinstance(parsed, ObjectInfoResponse):
            return self._to_object_info(parsed)

        self._raise_validation_or_runtime("upload_file", parsed, response.status_code)
        msg = "unreachable"
        raise AssertionError(msg)

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
            InvalidFileObjectError: If file_obj is invalid.
            ObjectNotFoundError: If container does not exist.
            StorageBackendError: If the backing storage provider fails.
        """
        if not hasattr(file_obj, "read") or not callable(file_obj.read):
            msg = "File object must be opened in binary mode"
            raise InvalidFileObjectError(msg)

        data = file_obj.read()
        if not isinstance(data, bytes):
            msg = "File object must be opened in binary mode"
            raise InvalidFileObjectError(msg)

        body = BodyUploadFileUploadPost(
            file=data,  # type: ignore[arg-type]  # Generated model types file as str, but multipart correctly supports bytes.
            key=remote_path,
            content_type=UNSET,
        )
        response = upload_file_upload_post.sync_detailed(client=self._client, body=body, container=container)
        parsed = response.parsed

        if response.status_code == HTTPStatus.OK and isinstance(parsed, ObjectInfoResponse):
            return self._to_object_info(parsed)

        self._raise_validation_or_runtime("upload_obj", parsed, response.status_code)
        msg = "unreachable"
        raise AssertionError(msg)

    def download_file(
        self,
        container: str,
        object_name: str,
        file_name: str,
    ) -> ObjectInfo:
        """Download an object from cloud storage to a local file.

        Args:
            container: Name of the container / bucket to download from.
            object_name: Key of the object to download.
            file_name: Local filesystem path to write the downloaded file to.

        Returns:
            Provider-agnostic metadata describing the downloaded object.

        Raises:
            LocalFileAccessError: If file_name cannot be written locally.
            ObjectNotFoundError: If the requested object does not exist.
            StorageBackendError: If the backing storage provider fails.
        """
        # Download the file bytes
        response = download_file_download_key_get.sync_detailed(key=object_name, client=self._client, container=container)

        if response.status_code == HTTPStatus.NOT_FOUND:
            if self._is_container_not_found_response(response.content):
                msg = f"Container not found: {container}"
                raise ContainerNotFoundError(msg)
            msg = f"Object not found: {object_name}"
            raise ObjectNotFoundError(msg)

        if response.status_code == HTTPStatus.OK:
            # Write bytes to local file
            try:
                Path(file_name).write_bytes(response.content)
            except OSError as exc:
                msg = f"Cannot write to file: {file_name}"
                raise LocalFileAccessError(msg) from exc
            # Get metadata for the downloaded object
            return self.get_file_info(container=container, object_name=object_name)

        self._raise_validation_or_runtime("download_file", response.parsed, response.status_code)
        msg = "unreachable"
        raise AssertionError(msg)

    def list_files(self, container: str, prefix: str) -> list[ObjectInfo]:
        """List objects in a container with the provided prefix.

        Args:
            container: Name of the container / bucket to list.
            prefix: Prefix filter for object keys. Use "" to list all objects.

        Returns:
            List of ObjectInfo sorted in ascending lexicographic order by object_name.

        Raises:
            ObjectNotFoundError: If container does not exist.
            StorageBackendError: If the backing storage provider fails.
        """
        response = list_objects_list_get.sync_detailed(client=self._client, prefix=prefix, container=container)
        parsed = response.parsed

        if response.status_code == HTTPStatus.OK and isinstance(parsed, ListResponse):
            objects = [self._to_object_info(item) for item in parsed.objects]
            # Sort by object_name to ensure ascending lexicographic order
            return sorted(objects, key=lambda obj: obj.object_name)

        self._raise_validation_or_runtime("list_files", parsed, response.status_code)
        msg = "unreachable"
        raise AssertionError(msg)

    def delete_file(self, container: str, object_name: str) -> DeleteResult:
        """Delete an object from cloud storage.

        Args:
            container: Name of the container / bucket to delete from.
            object_name: Key of the object to delete.

        Returns:
            Canonical response metadata for the delete operation.

        Raises:
            ObjectNotFoundError: If the requested object does not exist.
            StorageBackendError: If the backing storage provider fails.
        """
        response = delete_object_delete_key_delete.sync_detailed(key=object_name, client=self._client, container=container)
        parsed = response.parsed

        if response.status_code == HTTPStatus.NO_CONTENT:
            return DeleteResult(deleted=True, version_id=None, request_charged=None)
        if response.status_code == HTTPStatus.NOT_FOUND:
            if self._is_container_not_found_response(response.content):
                msg = f"Container not found: {container}"
                raise ContainerNotFoundError(msg)
            msg = f"Object not found: {object_name}"
            raise ObjectNotFoundError(msg)

        self._raise_validation_or_runtime("delete_file", parsed, response.status_code)
        msg = "unreachable"
        raise AssertionError(msg)

    def get_file_info(self, container: str, object_name: str) -> ObjectInfo:
        """Get metadata for a single object without downloading its contents.

        Args:
            container: Name of the container / bucket.
            object_name: Key of the object to get metadata for.

        Returns:
            Provider-agnostic metadata describing the object.

        Raises:
            ObjectNotFoundError: If the requested object does not exist.
            StorageBackendError: If the backing storage provider fails.
        """
        response = head_object_head_key_get.sync_detailed(
            key=object_name,
            client=self._client,
            container=container,
        )
        parsed = response.parsed

        if response.status_code == HTTPStatus.NOT_FOUND:
            if self._is_container_not_found_response(response.content):
                msg = f"Container not found: {container}"
                raise ContainerNotFoundError(msg)
            msg = f"Object not found: {object_name}"
            raise ObjectNotFoundError(msg)
        if response.status_code == HTTPStatus.OK and isinstance(parsed, ObjectInfoResponse):
            return self._to_object_info(parsed)

        self._raise_validation_or_runtime("get_file_info", parsed, response.status_code)
        msg = "unreachable"
        raise AssertionError(msg)

    @staticmethod
    def _to_object_info(obj: ObjectInfoResponse) -> ObjectInfo:
        """Convert service ObjectInfoResponse to shared ObjectInfo model.

        Maps service response fields to the 9-field ObjectInfo contract:
        - key → object_name
        - etag → integrity
        - content_type → data_type
        - size_bytes → size_bytes
        - updated_at → updated_at
        - metadata → metadata
        - version_id, encryption, storage_tier → None (not exposed by service)
        """
        size_bytes = None if isinstance(obj.size_bytes, Unset) else obj.size_bytes
        integrity = None if isinstance(obj.etag, Unset) else obj.etag
        updated_at = None if isinstance(obj.updated_at, Unset) else obj.updated_at
        data_type = None if isinstance(obj.content_type, Unset) else obj.content_type

        metadata: dict[str, str] | None
        if isinstance(obj.metadata, Unset) or obj.metadata is None:
            metadata = None
        else:
            metadata = {str(k): str(v) for k, v in obj.metadata.additional_properties.items()}

        return ObjectInfo(
            object_name=obj.key,
            version_id=None,
            data_type=data_type,
            integrity=integrity,
            encryption=None,
            storage_tier=None,
            size_bytes=size_bytes,
            updated_at=updated_at,
            metadata=metadata,
        )

    @staticmethod
    def _raise_validation_or_runtime(operation: str, parsed: object, status_code: int) -> NoReturn:
        if status_code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
            msg = f"{operation} authentication failed (status {status_code})"
            raise AuthenticationError(msg)

        if status_code == HTTPStatus.NOT_FOUND:
            msg = f"{operation} container not found (status {status_code})"
            raise ContainerNotFoundError(msg)

        if isinstance(parsed, HTTPValidationError):
            locations: set[str] = set()
            if not isinstance(parsed.detail, Unset):
                for error in parsed.detail:
                    for token in error.loc:
                        locations.add(str(token))

            if "container" in locations:
                msg = f"{operation} invalid container (status {status_code})"
                raise InvalidContainerError(msg)

            if operation != "list_files" and ("key" in locations or "object_name" in locations):
                msg = f"{operation} invalid object name (status {status_code})"
                raise InvalidObjectNameError(msg)

            msg = f"{operation} request validation failed (status {status_code})"
            raise StorageBackendError(msg)

        if status_code in (HTTPStatus.BAD_REQUEST, HTTPStatus.UNPROCESSABLE_ENTITY):
            msg = f"{operation} request validation failed (status {status_code})"
            raise StorageBackendError(msg)

        msg = f"{operation} failed with status {status_code}"
        raise StorageBackendError(msg)

    @staticmethod
    def _is_container_not_found_response(content: bytes) -> bool:
        """Return True when a 404 body clearly indicates missing container."""
        try:
            parsed = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return False

        detail = parsed.get("detail")
        return isinstance(detail, str) and "container not found" in detail.lower()
