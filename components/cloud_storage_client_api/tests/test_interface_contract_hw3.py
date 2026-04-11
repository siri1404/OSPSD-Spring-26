"""Tests validating hw-3 alignment with ospsd-cloud-storage shared API contract.

This test module verifies that the OSPSD Spring '26 Cloud Storage vertical
(Teams 2, 6, 10) has correctly refactored to implement the stable v1.0.0
shared interface defined in the ospsd-cloud-storage reference repository.

Reference: https://github.com/2SpaceMasterRace/ospsd-cloud-storage
"""

from __future__ import annotations

import inspect
from dataclasses import fields
from datetime import UTC, datetime
from typing import BinaryIO, get_type_hints

import pytest
from cloud_storage_client_api import (
    AuthenticationError,
    CloudStorageClient,
    ContainerNotFoundError,
    DeleteResult,
    InvalidContainerError,
    InvalidFileObjectError,
    InvalidObjectNameError,
    LocalFileAccessError,
    ObjectInfo,
    ObjectNotFoundError,
    StorageBackendError,
)


class StubClient(CloudStorageClient):
    """Minimal concrete client for testing the abstract contract."""

    def upload_file(
        self,
        container: str,
        local_path: str,
        remote_path: str,
    ) -> ObjectInfo:
        return ObjectInfo(object_name=remote_path, data_type="application/octet-stream")

    def upload_obj(
        self,
        container: str,
        file_obj: BinaryIO,
        remote_path: str,
    ) -> ObjectInfo:
        return ObjectInfo(object_name=remote_path, data_type="application/octet-stream")

    def download_file(
        self,
        container: str,
        object_name: str,
        file_name: str,
    ) -> ObjectInfo:
        return ObjectInfo(object_name=object_name, integrity="etag-123")

    def list_files(self, container: str, prefix: str) -> list[ObjectInfo]:
        return [ObjectInfo(object_name=f"{prefix}report.csv", storage_tier="STANDARD")]

    def delete_file(self, container: str, object_name: str) -> DeleteResult:
        return {
            "deleted": True,
            "version_id": "v1",
            "request_charged": False,
        }

    def get_file_info(self, container: str, object_name: str) -> ObjectInfo:
        return ObjectInfo(
            object_name=object_name,
            version_id="v1",
            encryption="AES256",
            size_bytes=128,
            updated_at=datetime(2026, 4, 9, tzinfo=UTC),
            metadata={"source": "test"},
        )


def test_public_api_exports_match_shared_contract() -> None:
    """Verify all public symbols match the shared contract."""
    expected_exports = {
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
    }

    # Import cloud_storage_api and check __all__
    import cloud_storage_client_api

    actual_exports = set(cloud_storage_client_api.__all__)
    assert actual_exports == expected_exports, f"Exports mismatch. Got {actual_exports}, expected {expected_exports}"


def test_cloud_storage_client_has_required_methods() -> None:
    """Verify CloudStorageClient ABC defines the exact required methods."""
    expected_methods = {
        "upload_file",
        "upload_obj",
        "download_file",
        "list_files",
        "delete_file",
        "get_file_info",
    }

    actual_methods = {
        name
        for name, method in inspect.getmembers(CloudStorageClient, predicate=inspect.isfunction)
        if not name.startswith("_")
    }

    assert actual_methods == expected_methods, f"Methods mismatch. Got {actual_methods}, expected {expected_methods}"


def test_upload_file_signature() -> None:
    """Verify upload_file has the correct signature."""
    sig = inspect.signature(CloudStorageClient.upload_file)
    params = tuple(sig.parameters.keys())

    assert params == ("self", "container", "local_path", "remote_path")
    assert get_type_hints(CloudStorageClient.upload_file)["return"] is ObjectInfo


def test_upload_obj_signature() -> None:
    """Verify upload_obj has the correct signature."""
    sig = inspect.signature(CloudStorageClient.upload_obj)
    params = tuple(sig.parameters.keys())

    assert params == ("self", "container", "file_obj", "remote_path")
    hints = get_type_hints(CloudStorageClient.upload_obj)
    assert hints["file_obj"] is BinaryIO
    assert hints["return"] is ObjectInfo


def test_download_file_signature() -> None:
    """Verify download_file has the correct signature."""
    sig = inspect.signature(CloudStorageClient.download_file)
    params = tuple(sig.parameters.keys())

    assert params == ("self", "container", "object_name", "file_name")
    assert get_type_hints(CloudStorageClient.download_file)["return"] is ObjectInfo


def test_list_files_signature() -> None:
    """Verify list_files has the correct signature."""
    sig = inspect.signature(CloudStorageClient.list_files)
    params = tuple(sig.parameters.keys())

    assert params == ("self", "container", "prefix")
    assert get_type_hints(CloudStorageClient.list_files)["return"] == list[ObjectInfo]


def test_delete_file_signature_and_returns_delete_result() -> None:
    """Verify delete_file returns DeleteResult, not None or bytes."""
    sig = inspect.signature(CloudStorageClient.delete_file)
    params = tuple(sig.parameters.keys())

    assert params == ("self", "container", "object_name")
    assert get_type_hints(CloudStorageClient.delete_file)["return"] is DeleteResult


def test_get_file_info_signature() -> None:
    """Verify get_file_info has the correct signature."""
    sig = inspect.signature(CloudStorageClient.get_file_info)
    params = tuple(sig.parameters.keys())

    assert params == ("self", "container", "object_name")
    assert get_type_hints(CloudStorageClient.get_file_info)["return"] is ObjectInfo


def test_object_info_has_required_fields() -> None:
    """Verify ObjectInfo has all required fields in the correct order."""
    expected_field_names = [
        "object_name",
        "version_id",
        "data_type",
        "integrity",
        "encryption",
        "storage_tier",
        "size_bytes",
        "updated_at",
        "metadata",
    ]

    actual_field_names = [field.name for field in fields(ObjectInfo)]
    assert actual_field_names == expected_field_names


def test_object_info_is_frozen() -> None:
    """Verify ObjectInfo is immutable (frozen)."""
    info = ObjectInfo(object_name="test.txt")

    with pytest.raises((AttributeError, TypeError)):
        info.object_name = "changed"  # type: ignore[misc]


def test_delete_result_has_required_keys() -> None:
    """Verify DeleteResult TypedDict has the canonical provider-neutral keys."""
    assert DeleteResult.__required_keys__ == {"deleted", "version_id", "request_charged"}
    assert DeleteResult.__optional_keys__ == frozenset()


def test_exception_hierarchy_matches_python_standards() -> None:
    """Verify exceptions inherit from appropriate Python built-in types."""
    assert issubclass(AuthenticationError, PermissionError)
    assert issubclass(ContainerNotFoundError, FileNotFoundError)
    assert issubclass(InvalidContainerError, ValueError)
    assert issubclass(InvalidObjectNameError, ValueError)
    assert issubclass(InvalidFileObjectError, ValueError)
    assert issubclass(LocalFileAccessError, OSError)
    assert issubclass(ObjectNotFoundError, FileNotFoundError)
    assert issubclass(StorageBackendError, Exception)


def test_all_exceptions_are_distinct() -> None:
    """Verify each exception is unique."""
    exceptions = {
        AuthenticationError,
        ContainerNotFoundError,
        InvalidContainerError,
        InvalidFileObjectError,
        InvalidObjectNameError,
        LocalFileAccessError,
        ObjectNotFoundError,
        StorageBackendError,
    }
    assert len(exceptions) == 8


def test_concrete_implementation_can_be_instantiated() -> None:
    """Verify a concrete CloudStorageClient can be instantiated and used."""
    client = StubClient()

    assert isinstance(client, CloudStorageClient)


def test_methods_document_authentication_errors() -> None:
    """Verify all methods document AuthenticationError in their docstrings."""
    for method_name in (
        "upload_file",
        "upload_obj",
        "download_file",
        "list_files",
        "delete_file",
        "get_file_info",
    ):
        method = getattr(CloudStorageClient, method_name)
        docstring = inspect.getdoc(method)

        assert docstring is not None
        assert "AuthenticationError" in docstring


def test_methods_document_container_errors() -> None:
    """Verify all methods document container-related errors in their docstrings."""
    for method_name in (
        "upload_file",
        "upload_obj",
        "download_file",
        "list_files",
        "delete_file",
        "get_file_info",
    ):
        method = getattr(CloudStorageClient, method_name)
        docstring = inspect.getdoc(method)

        assert docstring is not None
        assert "ContainerNotFoundError" in docstring or "InvalidContainerError" in docstring


def test_list_files_documents_deterministic_ordering() -> None:
    """Verify list_files commits to lexicographic ordering in docstring."""
    docstring = inspect.getdoc(CloudStorageClient.list_files)

    assert docstring is not None
    assert "sorted in ascending" in docstring
    assert "lexicographic order by" in docstring
    assert "object_name" in docstring
