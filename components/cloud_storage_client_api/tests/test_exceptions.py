"""Unit tests for domain exception hierarchy."""

from __future__ import annotations

import pytest
from cloud_storage_client_api.exceptions import (
    CloudStorageError,
    ObjectNotFoundError,
    StorageOperationError,
    StorageValidationError,
)


@pytest.mark.unit
class TestExceptionHierarchy:
    """Test custom exception hierarchy and inheritance."""

    def test_object_not_found_is_cloud_storage_error(self) -> None:
        assert issubclass(ObjectNotFoundError, CloudStorageError)

    def test_storage_operation_error_is_cloud_storage_error(self) -> None:
        assert issubclass(StorageOperationError, CloudStorageError)

    def test_storage_validation_error_is_cloud_storage_error(self) -> None:
        assert issubclass(StorageValidationError, CloudStorageError)

    def test_all_catchable_as_base(self) -> None:
        test_msg = "test"
        for exc_class in (ObjectNotFoundError, StorageOperationError, StorageValidationError):
            with pytest.raises(CloudStorageError):
                raise exc_class(test_msg)

    def test_message_preserved(self) -> None:
        exc = ObjectNotFoundError("Object not found: test.txt")
        assert str(exc) == "Object not found: test.txt"
