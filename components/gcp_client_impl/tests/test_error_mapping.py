"""Unit tests for GCP error-mapping helpers.

Exercises _raise_read_error and _raise_write_error directly with each
GoogleAPIError subclass, verifying the mapped shared exception type and that
the original SDK exception is preserved as __cause__ (via raise X from exc).
"""

from __future__ import annotations

import pytest
from cloud_storage_api.exceptions import (
    AuthenticationError,
    ContainerNotFoundError,
    InvalidContainerError,
    InvalidObjectNameError,
    ObjectNotFoundError,
    StorageBackendError,
)
from google.api_core import exceptions as google_exceptions

from gcp_client_impl.client import _raise_read_error, _raise_write_error

_CONTAINER = "test-bucket"
_OBJECT = "folder/file.txt"


# ============================================================================
# _raise_read_error — read/delete paths (404 means object missing)
# ============================================================================


@pytest.mark.unit
def test_read_error_maps_forbidden_to_authentication_error() -> None:
    """Forbidden → AuthenticationError on read paths."""
    src = google_exceptions.Forbidden("denied")  # type: ignore[no-untyped-call]

    with pytest.raises(AuthenticationError, match="Access denied") as exc_info:
        _raise_read_error(src, container=_CONTAINER, object_name=_OBJECT)

    assert exc_info.value.__cause__ is src


@pytest.mark.unit
def test_read_error_maps_unauthorized_to_authentication_error() -> None:
    """Unauthorized → AuthenticationError on read paths."""
    src = google_exceptions.Unauthorized("bad token")  # type: ignore[no-untyped-call]

    with pytest.raises(AuthenticationError, match="Authentication failed") as exc_info:
        _raise_read_error(src, container=_CONTAINER, object_name=_OBJECT)

    assert exc_info.value.__cause__ is src


@pytest.mark.unit
def test_read_error_with_object_name_maps_not_found_to_object_not_found() -> None:
    """NotFound + object_name → ObjectNotFoundError on read paths."""
    src = google_exceptions.NotFound("missing")  # type: ignore[no-untyped-call]

    with pytest.raises(ObjectNotFoundError, match=_OBJECT) as exc_info:
        _raise_read_error(src, container=_CONTAINER, object_name=_OBJECT)

    assert exc_info.value.__cause__ is src


@pytest.mark.unit
def test_read_error_without_object_name_maps_not_found_to_container_not_found() -> None:
    """NotFound without object_name → ContainerNotFoundError (e.g., list_files)."""
    src = google_exceptions.NotFound("missing bucket")  # type: ignore[no-untyped-call]

    with pytest.raises(ContainerNotFoundError, match=_CONTAINER) as exc_info:
        _raise_read_error(src, container=_CONTAINER, object_name=None)

    assert exc_info.value.__cause__ is src


@pytest.mark.unit
def test_read_error_with_object_name_maps_bad_request_to_invalid_object_name() -> None:
    """BadRequest + object_name → InvalidObjectNameError."""
    src = google_exceptions.BadRequest("bad name")  # type: ignore[no-untyped-call]

    with pytest.raises(InvalidObjectNameError, match=_OBJECT) as exc_info:
        _raise_read_error(src, container=_CONTAINER, object_name=_OBJECT)

    assert exc_info.value.__cause__ is src


@pytest.mark.unit
def test_read_error_without_object_name_maps_bad_request_to_invalid_container() -> None:
    """BadRequest without object_name → InvalidContainerError."""
    src = google_exceptions.BadRequest("bad bucket name")  # type: ignore[no-untyped-call]

    with pytest.raises(InvalidContainerError, match=_CONTAINER) as exc_info:
        _raise_read_error(src, container=_CONTAINER, object_name=None)

    assert exc_info.value.__cause__ is src


@pytest.mark.unit
def test_read_error_falls_back_to_storage_backend_error_for_unmapped_api_error() -> None:
    """Unmapped GoogleAPIError → StorageBackendError fallback."""
    src = google_exceptions.GoogleAPIError("unknown failure")

    with pytest.raises(StorageBackendError, match="backend operation failed") as exc_info:
        _raise_read_error(src, container=_CONTAINER, object_name=_OBJECT)

    assert exc_info.value.__cause__ is src


# ============================================================================
# _raise_write_error — write paths (404 always means bucket missing)
# ============================================================================


@pytest.mark.unit
def test_write_error_maps_forbidden_to_container_not_found() -> None:
    """Forbidden on write → ContainerNotFoundError (often masks a missing bucket)."""
    src = google_exceptions.Forbidden("denied")  # type: ignore[no-untyped-call]

    with pytest.raises(ContainerNotFoundError, match=_CONTAINER) as exc_info:
        _raise_write_error(src, container=_CONTAINER, object_name=_OBJECT)

    assert exc_info.value.__cause__ is src


@pytest.mark.unit
def test_write_error_maps_unauthorized_to_authentication_error() -> None:
    """Unauthorized → AuthenticationError on write paths."""
    src = google_exceptions.Unauthorized("bad token")  # type: ignore[no-untyped-call]

    with pytest.raises(AuthenticationError, match="Authentication failed") as exc_info:
        _raise_write_error(src, container=_CONTAINER, object_name=_OBJECT)

    assert exc_info.value.__cause__ is src


@pytest.mark.unit
def test_write_error_maps_not_found_to_container_not_found() -> None:
    """NotFound on write → ContainerNotFoundError (bucket is the only thing that can 404)."""
    src = google_exceptions.NotFound("missing bucket")  # type: ignore[no-untyped-call]

    with pytest.raises(ContainerNotFoundError, match=_CONTAINER) as exc_info:
        _raise_write_error(src, container=_CONTAINER, object_name=_OBJECT)

    assert exc_info.value.__cause__ is src


@pytest.mark.unit
def test_write_error_with_object_name_maps_bad_request_to_invalid_object_name() -> None:
    """BadRequest + object_name → InvalidObjectNameError on write paths."""
    src = google_exceptions.BadRequest("bad name")  # type: ignore[no-untyped-call]

    with pytest.raises(InvalidObjectNameError, match=_OBJECT) as exc_info:
        _raise_write_error(src, container=_CONTAINER, object_name=_OBJECT)

    assert exc_info.value.__cause__ is src


@pytest.mark.unit
def test_write_error_without_object_name_maps_bad_request_to_invalid_container() -> None:
    """BadRequest without object_name → InvalidContainerError."""
    src = google_exceptions.BadRequest("bad bucket name")  # type: ignore[no-untyped-call]

    with pytest.raises(InvalidContainerError, match=_CONTAINER) as exc_info:
        _raise_write_error(src, container=_CONTAINER, object_name=None)

    assert exc_info.value.__cause__ is src


@pytest.mark.unit
def test_write_error_falls_back_to_storage_backend_error_for_unmapped_api_error() -> None:
    """Unmapped GoogleAPIError → StorageBackendError fallback on write paths."""
    src = google_exceptions.GoogleAPIError("unknown failure")

    with pytest.raises(StorageBackendError, match="backend operation failed") as exc_info:
        _raise_write_error(src, container=_CONTAINER, object_name=_OBJECT)

    assert exc_info.value.__cause__ is src
