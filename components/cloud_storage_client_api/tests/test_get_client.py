"""Unit tests verifying that CloudStorageClient is an abstract base class."""

from __future__ import annotations

from typing import BinaryIO

import pytest
from cloud_storage_client_api.client import CloudStorageClient
from cloud_storage_client_api.models import DeleteResult, ObjectInfo


@pytest.mark.unit
class TestCloudStorageClientIsAbstract:
    """Verify that CloudStorageClient cannot be instantiated directly."""

    def test_cannot_instantiate_direct(self) -> None:
        """CloudStorageClient is an ABC and cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            CloudStorageClient()  # type: ignore[abstract]

    def test_requires_upload_file_implementation(self) -> None:
        """Concrete implementation must implement upload_file."""
        class IncompleteClient(CloudStorageClient):
            def upload_obj(
                self, container: str, file_obj: BinaryIO, remote_path: str
            ) -> ObjectInfo:
                raise NotImplementedError

            def download_file(
                self, container: str, object_name: str, file_name: str
            ) -> ObjectInfo:
                raise NotImplementedError

            def list_files(self, container: str, prefix: str) -> list[ObjectInfo]:
                raise NotImplementedError

            def delete_file(self, container: str, object_name: str) -> DeleteResult:
                raise NotImplementedError

            def get_file_info(self, container: str, object_name: str) -> ObjectInfo:
                raise NotImplementedError

        # Still abstract because upload_file is missing
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteClient()  # type: ignore[abstract]

    def test_concrete_implementation_can_be_instantiated(self) -> None:
        """Concrete implementation with all methods can be instantiated."""
        class ConcreteClient(CloudStorageClient):
            def upload_file(
                self, container: str, local_path: str, remote_path: str
            ) -> ObjectInfo:
                return ObjectInfo(object_name="test.txt")

            def upload_obj(
                self, container: str, file_obj: BinaryIO, remote_path: str
            ) -> ObjectInfo:
                return ObjectInfo(object_name="test.txt")

            def download_file(
                self, container: str, object_name: str, file_name: str
            ) -> ObjectInfo:
                return ObjectInfo(object_name="test.txt")

            def list_files(self, container: str, prefix: str) -> list[ObjectInfo]:
                return []

            def delete_file(self, container: str, object_name: str) -> DeleteResult:
                return {"deleted": True, "version_id": None, "request_charged": None}

            def get_file_info(self, container: str, object_name: str) -> ObjectInfo:
                return ObjectInfo(object_name="test.txt")

        # Can be instantiated since all abstract methods are implemented
        client = ConcreteClient()
        assert client is not None
