"""Unit tests for the dependency injection module (cloud_storage_client_api/di.py)."""

from __future__ import annotations

from collections.abc import Generator
from typing import Mapping

import pytest

from cloud_storage_client_api.client import CloudStorageClient, ObjectInfo
from cloud_storage_client_api.di import (
    get_client,
    override_get_client,
    register_get_client,
    unregister_get_client,
)


# We can't instantiate the ABC directly, so we make a minimal concrete subclass.
class _FakeClient(CloudStorageClient):
    def upload_file(
        self, *, local_path: str, key: str, content_type: str | None = None
    ) -> ObjectInfo:
        raise NotImplementedError

    def upload_bytes(
        self,
        *,
        data: bytes,
        key: str,
        content_type: str | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> ObjectInfo:
        raise NotImplementedError

    def download_bytes(self, *, key: str) -> bytes:
        raise NotImplementedError

    def list(self, *, prefix: str) -> list[ObjectInfo]:
        raise NotImplementedError

    def delete(self, *, key: str) -> None:
        raise NotImplementedError

    def head(self, *, key: str) -> ObjectInfo | None:
        raise NotImplementedError


@pytest.fixture(autouse=True)
def clean_registry() -> Generator[None, None, None]:
    # Wipe the default slot before and after every test so they don't bleed.
    unregister_get_client()
    yield
    unregister_get_client()


@pytest.mark.unit
class TestRegistry:
    """Basic register / get / unregister behaviour."""

    def test_raises_when_nothing_registered(self) -> None:
        with pytest.raises(RuntimeError, match="default"):
            get_client()

    def test_returns_instance_after_registration(self) -> None:
        fake = _FakeClient()
        register_get_client(lambda: fake)
        assert get_client() is fake

    def test_unregister_makes_get_client_raise_again(self) -> None:
        register_get_client(lambda: _FakeClient())
        unregister_get_client()
        with pytest.raises(RuntimeError):
            get_client()

    def test_second_registration_overwrites_first(self) -> None:
        # Last writer wins.
        first, second = _FakeClient(), _FakeClient()
        register_get_client(lambda: first)
        register_get_client(lambda: second)
        assert get_client() is second

    def test_named_provider_works_independently(self) -> None:
        client_a = _FakeClient()
        client_b = _FakeClient()
        register_get_client(lambda: client_a, name="gcp")
        register_get_client(lambda: client_b, name="s3")
        assert get_client(name="gcp") is client_a
        assert get_client(name="s3") is client_b

    def test_override_works_without_registered_default(self) -> None:
        temp = _FakeClient()
        with override_get_client(lambda: temp):
            assert get_client() is temp
        with pytest.raises(RuntimeError):
            get_client()


@pytest.mark.unit
class TestOverride:
    """The override_get_client() context manager swaps the factory temporarily."""

    def test_override_is_active_inside_context(self) -> None:
        real = _FakeClient()
        temp = _FakeClient()
        register_get_client(lambda: real)

        with override_get_client(lambda: temp):
            assert get_client() is temp

    def test_original_is_restored_after_context_exits(self) -> None:
        real = _FakeClient()
        register_get_client(lambda: real)

        with override_get_client(lambda: _FakeClient()):
            pass  # just enter and exit

        assert get_client() is real
