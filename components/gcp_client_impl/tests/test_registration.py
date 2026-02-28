"""Unit tests for gcp_client_impl automatic DI registration.

When gcp_client_impl is imported, it must automatically register
GCPCloudStorageClient as the factory for both the 'default' and 'gcp' slots.
"""

from __future__ import annotations

import importlib
from collections.abc import Generator

import pytest
from cloud_storage_client_api.di import get_client, unregister_get_client
from gcp_client_impl.client import GCPCloudStorageClient


@pytest.fixture(autouse=True)
def clean_registry() -> Generator[None, None, None]:
    unregister_get_client()
    unregister_get_client(name="gcp")
    yield
    unregister_get_client()
    unregister_get_client(name="gcp")


@pytest.mark.unit
class TestRegistration:
    """Tests for gcp_client_impl DI registration."""

    def test_importing_impl_registers_default_provider(self) -> None:
        importlib.reload(importlib.import_module("gcp_client_impl"))
        assert isinstance(get_client(), GCPCloudStorageClient)

    def test_importing_impl_registers_gcp_named_provider(self) -> None:
        importlib.reload(importlib.import_module("gcp_client_impl"))
        assert isinstance(get_client(name="gcp"), GCPCloudStorageClient)
