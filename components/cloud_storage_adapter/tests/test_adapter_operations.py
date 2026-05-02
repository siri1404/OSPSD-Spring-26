"""Unit tests for CloudStorageAdapter operations on the shared API contract."""

from __future__ import annotations

import io
from collections.abc import Callable
from datetime import UTC, datetime
from http import HTTPStatus
from io import BytesIO
from pathlib import Path
from typing import Any, cast

import pytest
from cloud_storage_adapter import CloudStorageAdapter
from cloud_storage_api import ObjectInfo
from cloud_storage_api.exceptions import (
    AuthenticationError,
    ContainerNotFoundError,
    InvalidFileObjectError,
    InvalidObjectNameError,
    LocalFileAccessError,
    ObjectNotFoundError,
    StorageBackendError,
)
from cloud_storage_service_api_client.models import (
    BodyUploadFileUploadPost,
    HTTPValidationError,
    ListResponse,
    ObjectInfoResponse,
    ObjectInfoResponseMetadataType0,
)
from cloud_storage_service_api_client.types import UNSET, Response

TEST_CONTAINER = "test-container"


def _fake_upload_response(obj: ObjectInfoResponse) -> Callable[..., Response[ObjectInfoResponse]]:
    def _impl(*, client: Any, body: BodyUploadFileUploadPost, container: Any) -> Response[ObjectInfoResponse]:
        return Response(status_code=HTTPStatus.OK, content=b"", headers={}, parsed=obj)

    return _impl


def _fake_key_response(status: HTTPStatus, content: bytes = b"", parsed: object | None = None) -> Callable[..., Response[object]]:
    def _impl(*, key: str, client: Any, container: Any) -> Response[object]:
        return Response(status_code=status, content=content, headers={}, parsed=parsed)

    return _impl


def _fake_list_response(parsed: ListResponse) -> Callable[..., Response[ListResponse]]:
    def _impl(*, client: Any, prefix: str, container: Any) -> Response[ListResponse]:
        return Response(status_code=HTTPStatus.OK, content=b"", headers={}, parsed=parsed)

    return _impl


def _fake_upload_status_response(status: HTTPStatus, parsed: object | None = None) -> Callable[..., Response[object]]:
    def _impl(*, client: Any, body: BodyUploadFileUploadPost, container: Any) -> Response[object]:
        return Response(status_code=status, content=b"", headers={}, parsed=parsed)

    return _impl


def _make_capture_upload(
    captured_body: dict[str, object],
    captured_container: dict[str, object],
    expected_key: str,
    parsed_obj: ObjectInfoResponse | None = None,
) -> Callable[..., Response[ObjectInfoResponse]]:
    def _impl(*, client: Any, body: BodyUploadFileUploadPost, container: Any) -> Response[ObjectInfoResponse]:
        captured_container.update({"container": container})
        captured_body.update({"file": body.file, "key": body.key})
        assert body.key == expected_key
        parsed = parsed_obj if parsed_obj is not None else _mk_object_info_response(key=expected_key)
        return Response(status_code=HTTPStatus.OK, content=b"", headers={}, parsed=parsed)

    return _impl


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
        object_name=key,
        size_bytes=4,
        integrity="e1",
        updated_at=datetime(2026, 3, 22, 10, 0, 0, tzinfo=UTC),
        data_type="text/plain",
        metadata=obj_metadata,
    )


@pytest.mark.unit
def test_upload_obj_returns_object_info(monkeypatch: pytest.MonkeyPatch) -> None:
    obj = _mk_object_info_response(metadata={"owner": "team6"})
    captured_body: dict[str, object] = {}
    captured_container: dict[str, object] = {}

    monkeypatch.setattr(
        "cloud_storage_adapter.adapter.upload_file_upload_post.sync_detailed",
        _make_capture_upload(
            captured_body=captured_body,
            captured_container=captured_container,
            expected_key="k.txt",
            parsed_obj=obj,
        ),
    )

    adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")
    info = adapter.upload_obj(
        container=TEST_CONTAINER,
        file_obj=BytesIO(b"test"),
        remote_path="k.txt",
    )

    assert captured_body["key"] == "k.txt"
    assert captured_container["container"] == TEST_CONTAINER
    assert info.object_name == "k.txt"
    assert info.size_bytes == 4
    assert info.integrity == "e1"
    assert info.updated_at == datetime(2026, 3, 22, 10, 0, 0, tzinfo=UTC)
    assert info.data_type == "text/plain"
    assert info.metadata == {"owner": "team6"}


def test_upload_obj_validation_error_raises_invalid_name(monkeypatch: pytest.MonkeyPatch) -> None:
    validation_error = HTTPValidationError.from_dict(
        {"detail": [{"loc": ["body", "key"], "msg": "Field required", "type": "missing"}]}
    )
    monkeypatch.setattr(
        "cloud_storage_adapter.adapter.upload_file_upload_post.sync_detailed",
        _fake_upload_status_response(HTTPStatus.UNPROCESSABLE_ENTITY, parsed=validation_error),
    )

    adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")
    with pytest.raises(InvalidObjectNameError, match="invalid object name"):
        adapter.upload_obj(container=TEST_CONTAINER, file_obj=BytesIO(b"bad"), remote_path="bad.txt")


def test_upload_obj_invalid_file_object_raises_domain_error() -> None:
    adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")

    with pytest.raises(InvalidFileObjectError, match="File object must be opened in binary mode"):
        adapter.upload_obj(container=TEST_CONTAINER, file_obj=cast("Any", object()), remote_path="bad.txt")


def test_upload_file_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    local_file = tmp_path / "hello.txt"
    local_file.write_bytes(b"hello")
    obj = _mk_object_info_response(key="upload/hello.txt")

    monkeypatch.setattr(
        "cloud_storage_adapter.adapter.upload_file_upload_post.sync_detailed",
        _fake_upload_response(obj),
    )

    adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")
    result = adapter.upload_file(
        container=TEST_CONTAINER,
        local_path=str(local_file),
        remote_path="upload/hello.txt",
    )

    assert result.object_name == "upload/hello.txt"


def test_upload_file_missing_path_raises_local_access_error() -> None:
    adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")
    with pytest.raises(LocalFileAccessError):
        adapter.upload_file(
            container=TEST_CONTAINER,
            local_path="C:/does-not-exist.txt",
            remote_path="missing.txt",
        )


def test_upload_file_unexpected_status_raises_runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    local_file = tmp_path / "hello.txt"
    local_file.write_bytes(b"hello")

    monkeypatch.setattr(
        "cloud_storage_adapter.adapter.upload_file_upload_post.sync_detailed",
        _fake_upload_status_response(HTTPStatus.INTERNAL_SERVER_ERROR, parsed=None),
    )

    adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")
    with pytest.raises(StorageBackendError, match="upload_file failed with status 500"):
        adapter.upload_file(
            container=TEST_CONTAINER,
            local_path=str(local_file),
            remote_path="upload/hello.txt",
        )


def test_download_file_200_writes_file_and_returns_info(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")

    monkeypatch.setattr(
        "cloud_storage_adapter.adapter.download_file_download_key_get.sync_detailed",
        _fake_key_response(HTTPStatus.OK, content=b"downloaded-content", parsed=None),
    )

    expected_info = ObjectInfo(object_name="folder/file.txt", size_bytes=18)
    monkeypatch.setattr(adapter, "get_file_info", lambda *, container, object_name: expected_info)

    out_file = tmp_path / "downloaded.bin"
    info = adapter.download_file(
        container=TEST_CONTAINER,
        object_name="folder/file.txt",
        file_name=str(out_file),
    )

    assert out_file.read_bytes() == b"downloaded-content"
    assert info.object_name == "folder/file.txt"


def test_download_file_404_raises_file_not_found(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")
    monkeypatch.setattr(
        "cloud_storage_adapter.adapter.download_file_download_key_get.sync_detailed",
        _fake_key_response(HTTPStatus.NOT_FOUND, content=b"", parsed=None),
    )

    with pytest.raises(ObjectNotFoundError, match=r"missing\.txt"):
        adapter.download_file(
            container=TEST_CONTAINER,
            object_name="missing.txt",
            file_name=str(tmp_path / "unused.bin"),
        )


def test_download_file_404_container_not_found(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")
    monkeypatch.setattr(
        "cloud_storage_adapter.adapter.download_file_download_key_get.sync_detailed",
        _fake_key_response(HTTPStatus.NOT_FOUND, content=b'{"detail":"Container not found"}', parsed=None),
    )

    with pytest.raises(ContainerNotFoundError, match="Container not found"):
        adapter.download_file(
            container=TEST_CONTAINER,
            object_name="missing.txt",
            file_name=str(tmp_path / "unused.bin"),
        )


def test_download_file_non_404_error_raises_runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")
    monkeypatch.setattr(
        "cloud_storage_adapter.adapter.download_file_download_key_get.sync_detailed",
        _fake_key_response(HTTPStatus.INTERNAL_SERVER_ERROR, content=b"", parsed=None),
    )

    with pytest.raises(StorageBackendError, match="download_file failed with status 500"):
        adapter.download_file(
            container=TEST_CONTAINER,
            object_name="bad.txt",
            file_name=str(tmp_path / "unused.bin"),
        )


def test_get_file_info_404_raises_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "cloud_storage_adapter.adapter.head_object_head_key_get.sync_detailed",
        _fake_key_response(HTTPStatus.NOT_FOUND, content=b"", parsed=None),
    )

    adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")
    with pytest.raises(ObjectNotFoundError, match=r"missing\.txt"):
        adapter.get_file_info(container=TEST_CONTAINER, object_name="missing.txt")


def test_get_file_info_404_container_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "cloud_storage_adapter.adapter.head_object_head_key_get.sync_detailed",
        _fake_key_response(HTTPStatus.NOT_FOUND, content=b'{"detail":"Container not found"}', parsed=None),
    )

    adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")
    with pytest.raises(ContainerNotFoundError, match="Container not found"):
        adapter.get_file_info(container=TEST_CONTAINER, object_name="missing.txt")


def test_get_file_info_200_maps_object_info(monkeypatch: pytest.MonkeyPatch) -> None:
    obj = _mk_object_info_response(key="head.txt", metadata={"source": "test"})
    monkeypatch.setattr(
        "cloud_storage_adapter.adapter.head_object_head_key_get.sync_detailed",
        lambda *, key, client, container: Response(
            status_code=HTTPStatus.OK,
            content=b"",
            headers={},
            parsed=obj,
        ),
    )

    adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")
    result = adapter.get_file_info(container=TEST_CONTAINER, object_name="head.txt")

    assert result.object_name == "head.txt"
    assert result.metadata == {"source": "test"}


def test_get_file_info_validation_error_raises_invalid_name(monkeypatch: pytest.MonkeyPatch) -> None:
    validation_error = HTTPValidationError.from_dict(
        {"detail": [{"loc": ["path", "key"], "msg": "Invalid key", "type": "value_error"}]}
    )
    monkeypatch.setattr(
        "cloud_storage_adapter.adapter.head_object_head_key_get.sync_detailed",
        lambda *, key, client, container: Response(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content=b"",
            headers={},
            parsed=validation_error,
        ),
    )

    adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")
    with pytest.raises(InvalidObjectNameError, match="invalid object name"):
        adapter.get_file_info(container=TEST_CONTAINER, object_name="bad key")


def test_delete_file_404_raises_file_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "cloud_storage_adapter.adapter.delete_object_delete_key_delete.sync_detailed",
        _fake_key_response(HTTPStatus.NOT_FOUND, content=b"", parsed=None),
    )

    adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")
    with pytest.raises(ObjectNotFoundError, match=r"missing\.txt"):
        adapter.delete_file(container=TEST_CONTAINER, object_name="missing.txt")


def test_delete_file_404_container_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "cloud_storage_adapter.adapter.delete_object_delete_key_delete.sync_detailed",
        _fake_key_response(HTTPStatus.NOT_FOUND, content=b'{"detail":"Container not found"}', parsed=None),
    )

    adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")
    with pytest.raises(ContainerNotFoundError, match="Container not found"):
        adapter.delete_file(container=TEST_CONTAINER, object_name="missing.txt")


def test_delete_file_204_returns_delete_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "cloud_storage_adapter.adapter.delete_object_delete_key_delete.sync_detailed",
        _fake_key_response(HTTPStatus.NO_CONTENT, content=b"", parsed=None),
    )

    adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")
    result = adapter.delete_file(container=TEST_CONTAINER, object_name="delete-me.txt")
    assert result == {"deleted": True, "version_id": None, "request_charged": False}


def test_delete_file_validation_error_raises_invalid_name(monkeypatch: pytest.MonkeyPatch) -> None:
    validation_error = HTTPValidationError.from_dict(
        {"detail": [{"loc": ["path", "key"], "msg": "Invalid key", "type": "value_error"}]}
    )
    monkeypatch.setattr(
        "cloud_storage_adapter.adapter.delete_object_delete_key_delete.sync_detailed",
        _fake_key_response(HTTPStatus.UNPROCESSABLE_ENTITY, content=b"", parsed=validation_error),
    )

    adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")
    with pytest.raises(InvalidObjectNameError, match="invalid object name"):
        adapter.delete_file(container=TEST_CONTAINER, object_name="bad key")


def test_list_files_maps_objects(monkeypatch: pytest.MonkeyPatch) -> None:
    b_obj = ObjectInfoResponse(
        object_name="b.txt",
        size_bytes=2,
        integrity="b",
        updated_at=None,
        data_type="text/plain",
        metadata=ObjectInfoResponseMetadataType0.from_dict({"x": "1"}),
    )
    a_obj = ObjectInfoResponse(
        object_name="a.txt",
        size_bytes=1,
        integrity="a",
        updated_at=datetime(2026, 3, 22, tzinfo=UTC),
        data_type="text/plain",
        metadata=None,
    )

    monkeypatch.setattr(
        "cloud_storage_adapter.adapter.list_objects_list_get.sync_detailed",
        _fake_list_response(ListResponse(objects=[b_obj, a_obj])),
    )

    adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")
    objects = adapter.list_files(container=TEST_CONTAINER, prefix="")

    assert [obj.object_name for obj in objects] == ["a.txt", "b.txt"]
    assert objects[1].metadata == {"x": "1"}


def test_list_files_validation_error_raises_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    validation_error = HTTPValidationError.from_dict(
        {"detail": [{"loc": ["query", "prefix"], "msg": "Invalid", "type": "value_error"}]}
    )
    monkeypatch.setattr(
        "cloud_storage_adapter.adapter.list_objects_list_get.sync_detailed",
        lambda *, client, prefix, container: Response(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content=b"",
            headers={},
            parsed=validation_error,
        ),
    )

    adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")
    with pytest.raises(StorageBackendError, match="list_files request validation failed"):
        adapter.list_files(container=TEST_CONTAINER, prefix="")


def test_list_files_404_raises_container_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "cloud_storage_adapter.adapter.list_objects_list_get.sync_detailed",
        lambda *, client, prefix, container: Response(
            status_code=HTTPStatus.NOT_FOUND,
            content=b"",
            headers={},
            parsed=None,
        ),
    )

    adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")
    with pytest.raises(ContainerNotFoundError, match="container not found"):
        adapter.list_files(container=TEST_CONTAINER, prefix="")


def test_upload_file_401_raises_authentication_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    local_file = tmp_path / "hello.txt"
    local_file.write_bytes(b"hello")

    monkeypatch.setattr(
        "cloud_storage_adapter.adapter.upload_file_upload_post.sync_detailed",
        lambda *, client, body, container: Response(
            status_code=HTTPStatus.UNAUTHORIZED,
            content=b"",
            headers={},
            parsed=None,
        ),
    )

    adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")
    with pytest.raises(AuthenticationError, match="authentication failed"):
        adapter.upload_file(
            container=TEST_CONTAINER,
            local_path=str(local_file),
            remote_path="upload/hello.txt",
        )


def test_to_object_info_handles_unset_fields() -> None:
    obj = ObjectInfoResponse(
        object_name="unset.txt",
        size_bytes=UNSET,
        integrity=UNSET,
        updated_at=UNSET,
        data_type=UNSET,
        metadata=UNSET,
    )
    mapped = CloudStorageAdapter._to_object_info(obj)

    assert mapped.object_name == "unset.txt"
    assert mapped.size_bytes is None
    assert mapped.integrity is None
    assert mapped.updated_at is None
    assert mapped.data_type is None
    assert mapped.metadata is None


def test_raise_validation_or_runtime_generic_branch() -> None:
    with pytest.raises(StorageBackendError, match="list_files failed with status 500"):
        CloudStorageAdapter._raise_validation_or_runtime("list_files", object(), 500)


def test_raise_validation_or_runtime_with_content_branch() -> None:
    """Exercise validation error branch by passing an HTTPValidationError payload."""
    validation_error = HTTPValidationError.from_dict(
        {"detail": [{"loc": ["body", "key"], "msg": "Invalid key", "type": "value_error"}]}
    )
    with pytest.raises(InvalidObjectNameError):
        CloudStorageAdapter._raise_validation_or_runtime("upload_file", validation_error, HTTPStatus.UNPROCESSABLE_ENTITY)


def test_upload_obj_with_non_utf8_binary_data(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: binary data with invalid UTF-8 bytes must not be corrupted."""
    binary_data = bytes(range(256))
    obj = _mk_object_info_response(key="binary.bin")
    captured_body: dict[str, object] = {}

    def _capture_upload(*, client: object, body: BodyUploadFileUploadPost, container: object) -> Response[ObjectInfoResponse]:
        assert body.key == "binary.bin"
        captured_body["file"] = body.file
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
    result = adapter.upload_obj(
        container=TEST_CONTAINER,
        file_obj=cast("Any", BytesIO(binary_data)),
        remote_path="binary.bin",
    )

    assert result.object_name == "binary.bin"
    assert isinstance(captured_body["file"], bytes)
    assert captured_body["file"] == binary_data


def test_upload_file_with_non_utf8_binary_data(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Regression: binary file upload must preserve non-UTF8 bytes."""
    binary_data = bytes(range(256))
    temp_file = tmp_path / "binary_test.dat"
    temp_file.write_bytes(binary_data)

    obj = _mk_object_info_response(key="uploaded.dat")
    captured_body: dict[str, object] = {}

    def _capture_upload(*, client: object, body: BodyUploadFileUploadPost, container: object) -> Response[ObjectInfoResponse]:
        assert body.key == "uploaded.dat"
        captured_body["file"] = body.file
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
    result = adapter.upload_file(
        container=TEST_CONTAINER,
        local_path=str(temp_file),
        remote_path="uploaded.dat",
    )

    assert result.object_name == "uploaded.dat"
    assert isinstance(captured_body["file"], bytes)
    assert captured_body["file"] == binary_data


def test_upload_obj_non_bytes_read_raises_invalid_file_object() -> None:
    class _TextReader:
        def read(self) -> str:
            return "not-bytes"

    adapter = CloudStorageAdapter(base_url="http://localhost:8000", token="t")
    with pytest.raises(InvalidFileObjectError, match="binary mode"):
        adapter.upload_obj(container=TEST_CONTAINER, file_obj=cast("Any", _TextReader()), remote_path="bad.txt")


def test_is_container_not_found_response_invalid_payload_returns_false() -> None:
    assert CloudStorageAdapter._is_container_not_found_response(b"not-json") is False
