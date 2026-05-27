"""Unit tests for CloudStorageAdapter operations (upload, download, list, delete, head)."""

from __future__ import annotations

from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from cloud_storage_adapter import CloudStorageAdapter
from cloud_storage_client_api.exceptions import ObjectNotFoundError, StorageOperationError, StorageValidationError
from cloud_storage_service_api_client.models import (
    HTTPValidationError,
    ListResponse,
    ObjectInfoResponse,
    ObjectInfoResponseMetadataType0,
)
from cloud_storage_service_api_client.types import Response


def _mk_object_info_response(
    *,
    key: str = "k.txt",
    metadata: dict[str, str] | None = None,
) -> ObjectInfoResponse:
    """Create a test ObjectInfoResponse object."""
    obj_metadata = None
    if metadata is not None:
        obj_metadata = ObjectInfoResponseMetadataType0.from_dict(metadata)

    return ObjectInfoResponse(
        key=key,
        size_bytes=4,
        etag="e1",
        updated_at=datetime(2026, 3, 22, 10, 0, 0, tzinfo=UTC),
        content_type="text/plain",
        metadata=obj_metadata,
    )


@pytest.mark.unit
class TestCloudStorageAdapter:
    """Behavioral tests for generated-client adapter mapping and handling."""

    def test_upload_bytes_returns_object_info(self, monkeypatch: pytest.MonkeyPatch) -> None:
        obj = _mk_object_info_response(metadata={"owner": "team6"})
        captured_body: dict[str, object] = {}

        monkeypatch.setattr(
            "cloud_storage_adapter.adapter.upload_file_upload_post.sync_detailed",
            lambda *, client, body: (
                client,
                captured_body.update({"file": body.file, "key": body.key}),
                Response(
                    status_code=HTTPStatus.OK,
                    content=b"",
                    headers={},
                    parsed=obj,
                ),
            )[2],
        )

        adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")
        info = adapter.upload_bytes(data=b"test", key="k.txt", content_type="text/plain")

        assert captured_body["key"] == "k.txt"
        # File should be raw bytes for multipart form handling
        assert captured_body["file"] == b"test"
        assert info.key == "k.txt"
        assert info.size_bytes == 4
        assert info.etag == "e1"
        assert info.updated_at == datetime(2026, 3, 22, 10, 0, 0, tzinfo=UTC)
        assert info.content_type == "text/plain"
        assert info.metadata == {"owner": "team6"}

    def test_upload_bytes_validation_error_raises_runtime(self, monkeypatch: pytest.MonkeyPatch) -> None:
        validation_error = HTTPValidationError.from_dict(
            {"detail": [{"loc": ["body", "key"], "msg": "Field required", "type": "missing"}]}
        )
        monkeypatch.setattr(
            "cloud_storage_adapter.adapter.upload_file_upload_post.sync_detailed",
            lambda *, client, body: Response(
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                content=b"",
                headers={},
                parsed=validation_error,
            ),
        )

        adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")
        with pytest.raises(StorageValidationError, match="upload_bytes request validation failed"):
            adapter.upload_bytes(data=b"bad", key="bad.txt")

    def test_upload_file_success(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        local_file = tmp_path / "hello.txt"
        local_file.write_bytes(b"hello")
        obj = _mk_object_info_response(key="upload/hello.txt")

        monkeypatch.setattr(
            "cloud_storage_adapter.adapter.upload_file_upload_post.sync_detailed",
            lambda *, client, body: Response(
                status_code=HTTPStatus.OK,
                content=b"",
                headers={},
                parsed=obj,
            ),
        )

        adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")
        result = adapter.upload_file(local_path=str(local_file), key="upload/hello.txt", content_type="text/plain")

        assert result.key == "upload/hello.txt"

    def test_upload_file_missing_path_raises(self) -> None:
        adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")
        with pytest.raises(ObjectNotFoundError):
            adapter.upload_file(local_path="C:/does-not-exist.txt", key="missing.txt")

    def test_upload_file_unexpected_status_raises_runtime(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        local_file = tmp_path / "hello.txt"
        local_file.write_bytes(b"hello")

        monkeypatch.setattr(
            "cloud_storage_adapter.adapter.upload_file_upload_post.sync_detailed",
            lambda *, client, body: Response(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                content=b"",
                headers={},
                parsed=None,
            ),
        )

        adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")
        with pytest.raises(StorageOperationError, match="upload_file failed with status 500"):
            adapter.upload_file(local_path=str(local_file), key="upload/hello.txt")

    def test_download_200_returns_bytes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")
        monkeypatch.setattr(
            "cloud_storage_adapter.adapter.download_file_download_key_get.sync_detailed",
            lambda *, key, client: Response(
                status_code=HTTPStatus.OK,
                content=b"downloaded-content",
                headers={},
                parsed=None,
            ),
        )

        payload = adapter.download_bytes(key="folder/file.txt")
        assert payload == b"downloaded-content"

    def test_download_404_raises_file_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")
        monkeypatch.setattr(
            "cloud_storage_adapter.adapter.download_file_download_key_get.sync_detailed",
            lambda *, key, client: Response(
                status_code=HTTPStatus.NOT_FOUND,
                content=b"",
                headers={},
                parsed=None,
            ),
        )

        with pytest.raises(ObjectNotFoundError, match=r"missing\.txt"):
            adapter.download_bytes(key="missing.txt")

    def test_download_non_404_error_raises_runtime(self, monkeypatch: pytest.MonkeyPatch) -> None:
        adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")
        monkeypatch.setattr(
            "cloud_storage_adapter.adapter.download_file_download_key_get.sync_detailed",
            lambda *, key, client: Response(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                content=b"",
                headers={},
                parsed=None,
            ),
        )

        with pytest.raises(StorageOperationError, match="download_bytes failed with status 500"):
            adapter.download_bytes(key="bad.txt")

    def test_head_404_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "cloud_storage_adapter.adapter.head_object_head_key_get.sync_detailed",
            lambda *, key, client: Response(
                status_code=HTTPStatus.NOT_FOUND,
                content=b"",
                headers={},
                parsed=None,
            ),
        )

        adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")
        result = adapter.head(key="missing.txt")
        assert result is None

    def test_head_200_maps_object_info(self, monkeypatch: pytest.MonkeyPatch) -> None:
        obj = _mk_object_info_response(key="head.txt", metadata={"source": "test"})
        monkeypatch.setattr(
            "cloud_storage_adapter.adapter.head_object_head_key_get.sync_detailed",
            lambda *, key, client: Response(
                status_code=HTTPStatus.OK,
                content=b"",
                headers={},
                parsed=obj,
            ),
        )

        adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")
        result = adapter.head(key="head.txt")

        assert result is not None
        assert result.key == "head.txt"
        assert result.metadata == {"source": "test"}

    def test_head_validation_error_raises_runtime(self, monkeypatch: pytest.MonkeyPatch) -> None:
        validation_error = HTTPValidationError.from_dict(
            {"detail": [{"loc": ["path", "key"], "msg": "Invalid key", "type": "value_error"}]}
        )
        monkeypatch.setattr(
            "cloud_storage_adapter.adapter.head_object_head_key_get.sync_detailed",
            lambda *, key, client: Response(
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                content=b"",
                headers={},
                parsed=validation_error,
            ),
        )

        adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")
        with pytest.raises(StorageValidationError, match="head request validation failed"):
            adapter.head(key="bad key")

    def test_delete_404_raises_file_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "cloud_storage_adapter.adapter.delete_object_delete_key_delete.sync_detailed",
            lambda *, key, client: Response(
                status_code=HTTPStatus.NOT_FOUND,
                content=b"",
                headers={},
                parsed=None,
            ),
        )

        adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")
        with pytest.raises(ObjectNotFoundError, match=r"missing\.txt"):
            adapter.delete(key="missing.txt")

    def test_delete_204_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "cloud_storage_adapter.adapter.delete_object_delete_key_delete.sync_detailed",
            lambda *, key, client: Response(
                status_code=HTTPStatus.NO_CONTENT,
                content=b"",
                headers={},
                parsed=None,
            ),
        )

        adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")
        adapter.delete(key="delete-me.txt")

    def test_delete_validation_error_raises_runtime(self, monkeypatch: pytest.MonkeyPatch) -> None:
        validation_error = HTTPValidationError.from_dict(
            {"detail": [{"loc": ["path", "key"], "msg": "Invalid key", "type": "value_error"}]}
        )
        monkeypatch.setattr(
            "cloud_storage_adapter.adapter.delete_object_delete_key_delete.sync_detailed",
            lambda *, key, client: Response(
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                content=b"",
                headers={},
                parsed=validation_error,
            ),
        )

        adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")
        with pytest.raises(StorageValidationError, match="delete request validation failed"):
            adapter.delete(key="bad key")

    def test_list_maps_objects(self, monkeypatch: pytest.MonkeyPatch) -> None:
        a = ObjectInfoResponse(
            key="a.txt",
            size_bytes=1,
            etag="a",
            updated_at=datetime(2026, 3, 22, tzinfo=UTC),
            content_type="text/plain",
            metadata=None,
        )
        b = ObjectInfoResponse(
            key="b.txt",
            size_bytes=2,
            etag="b",
            updated_at=None,
            content_type="text/plain",
            metadata=ObjectInfoResponseMetadataType0.from_dict({"x": "1"}),
        )

        monkeypatch.setattr(
            "cloud_storage_adapter.adapter.list_objects_list_get.sync_detailed",
            lambda *, client, prefix: Response(
                status_code=HTTPStatus.OK,
                content=b"",
                headers={},
                parsed=ListResponse(objects=[a, b]),
            ),
        )

        adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")
        objects = adapter.list(prefix="")

        assert [obj.key for obj in objects] == ["a.txt", "b.txt"]
        assert objects[1].metadata == {"x": "1"}

    def test_list_validation_error_raises_runtime(self, monkeypatch: pytest.MonkeyPatch) -> None:
        validation_error = HTTPValidationError.from_dict(
            {"detail": [{"loc": ["query", "prefix"], "msg": "Invalid", "type": "value_error"}]}
        )
        monkeypatch.setattr(
            "cloud_storage_adapter.adapter.list_objects_list_get.sync_detailed",
            lambda *, client, prefix: Response(
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                content=b"",
                headers={},
                parsed=validation_error,
            ),
        )

        adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")
        with pytest.raises(StorageValidationError, match="list request validation failed"):
            adapter.list(prefix="")

    def test_to_object_info_handles_unset_fields(self) -> None:
        obj = ObjectInfoResponse(key="unset.txt")
        mapped = CloudStorageAdapter._to_object_info(obj)

        assert mapped.key == "unset.txt"
        assert mapped.size_bytes is None
        assert mapped.etag is None
        assert mapped.updated_at is None
        assert mapped.content_type is None
        assert mapped.metadata is None

    def test_raise_validation_or_runtime_generic_branch(self) -> None:
        with pytest.raises(StorageOperationError, match="list failed with status 500"):
            CloudStorageAdapter._raise_validation_or_runtime("list", object(), 500)

    def test_upload_bytes_with_non_utf8_binary_data(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Regression: binary data with invalid UTF-8 bytes must not be corrupted."""
        # Binary data that spans the full byte range
        binary_data = bytes(range(256))
        obj = _mk_object_info_response(key="binary.bin")
        captured_body: dict[str, object] = {}

        def _capture_upload(*, client: object, body: object) -> Response[ObjectInfoResponse]:
            captured_body["file"] = body.file  # type: ignore[attr-defined]
            return Response(
                status_code=HTTPStatus.OK,
                content=b"",
                headers={},
                parsed=obj,
            )

        monkeypatch.setattr(
            "cloud_storage_adapter.adapter.upload_file_upload_post.sync_detailed",
            _capture_upload,
        )

        adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")
        result = adapter.upload_bytes(data=binary_data, key="binary.bin")

        assert result.key == "binary.bin"
        assert isinstance(captured_body["file"], bytes), "file must be raw bytes, not str"
        assert captured_body["file"] == binary_data, "Binary data must survive without corruption"

    def test_upload_file_with_non_utf8_binary_data(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Regression: binary file upload must preserve non-UTF8 bytes."""
        # Create a temporary binary file with complete byte range
        binary_data = bytes(range(256))
        temp_file = tmp_path / "binary_test.dat"
        temp_file.write_bytes(binary_data)

        obj = _mk_object_info_response(key="uploaded.dat")
        captured_body: dict[str, object] = {}

        def _capture_upload(*, client: object, body: object) -> Response[ObjectInfoResponse]:
            captured_body["file"] = body.file  # type: ignore[attr-defined]
            return Response(
                status_code=HTTPStatus.OK,
                content=b"",
                headers={},
                parsed=obj,
            )

        monkeypatch.setattr(
            "cloud_storage_adapter.adapter.upload_file_upload_post.sync_detailed",
            _capture_upload,
        )

        adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")
        result = adapter.upload_file(local_path=str(temp_file), key="uploaded.dat")

        assert result.key == "uploaded.dat"
        assert isinstance(captured_body["file"], bytes), "file must be raw bytes, not str"
        assert captured_body["file"] == binary_data, "Binary file data must survive without corruption"
