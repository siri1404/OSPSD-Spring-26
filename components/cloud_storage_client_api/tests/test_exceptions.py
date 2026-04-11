"""Unit tests for domain exception hierarchy."""

from __future__ import annotations

import pytest
from cloud_storage_client_api.exceptions import (
    AuthenticationError,
    ContainerNotFoundError,
    InvalidContainerError,
    InvalidFileObjectError,
    InvalidObjectNameError,
    LocalFileAccessError,
    ObjectNotFoundError,
    StorageBackendError,
)


@pytest.mark.unit
class TestExceptionHierarchy:
    """Test exception hierarchy with Python standard inheritance."""

    def test_authentication_error_is_permission_error(self) -> None:
        assert issubclass(AuthenticationError, PermissionError)

    def test_container_not_found_is_file_not_found(self) -> None:
        assert issubclass(ContainerNotFoundError, FileNotFoundError)

    def test_object_not_found_is_file_not_found(self) -> None:
        assert issubclass(ObjectNotFoundError, FileNotFoundError)

    def test_invalid_container_is_value_error(self) -> None:
        assert issubclass(InvalidContainerError, ValueError)

    def test_invalid_object_name_is_value_error(self) -> None:
        assert issubclass(InvalidObjectNameError, ValueError)

    def test_invalid_file_object_is_value_error(self) -> None:
        assert issubclass(InvalidFileObjectError, ValueError)

    def test_local_file_access_error_is_os_error(self) -> None:
        assert issubclass(LocalFileAccessError, OSError)

    def test_storage_backend_error_is_exception(self) -> None:
        assert issubclass(StorageBackendError, Exception)

    def test_message_preserved(self) -> None:
        exc = ObjectNotFoundError("Object not found: test.txt")
        assert str(exc) == "Object not found: test.txt"

    def test_all_8_exceptions_defined(self) -> None:
        exceptions = [
            AuthenticationError,
            ContainerNotFoundError,
            InvalidContainerError,
            InvalidObjectNameError,
            InvalidFileObjectError,
            LocalFileAccessError,
            ObjectNotFoundError,
            StorageBackendError,
        ]
        assert len(exceptions) == 8
