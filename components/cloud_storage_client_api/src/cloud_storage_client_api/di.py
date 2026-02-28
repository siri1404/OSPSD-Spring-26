"""Dependency injection module for registering and retrieving cloud storage client implementations."""

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import contextmanager
from contextvars import ContextVar
from threading import RLock
from typing import TypeAlias

from cloud_storage_client_api.client import CloudStorageClient

GetClient: TypeAlias = Callable[[], CloudStorageClient]

_DEFAULT_PROVIDER = "default"
_registry: dict[str, GetClient] = {}
_registry_lock = RLock()

# Per-context overrides (great for tests / parallel execution isolation)
_overrides: ContextVar[dict[str, GetClient] | None] = ContextVar("_overrides", default=None)


def register_get_client(fn: GetClient, name: str = _DEFAULT_PROVIDER) -> None:
    """Register a cloud storage client factory function.

    Args:
        fn: Callable that returns a CloudStorageClient instance.
        name: Name of the provider (defaults to 'default').
    """
    with _registry_lock:
        _registry[name] = fn


def unregister_get_client(name: str = _DEFAULT_PROVIDER) -> None:
    """Unregister a cloud storage client factory function.

    Args:
        name: Name of the provider (defaults to 'default').
    """
    with _registry_lock:
        _registry.pop(name, None)


def get_client(name: str = _DEFAULT_PROVIDER) -> CloudStorageClient:
    """Get a cloud storage client instance.

    Args:
        name: Name of the provider (defaults to 'default').

    Returns:
        An instance of the registered CloudStorageClient.

    Raises:
        RuntimeError: If no client factory is registered for the given name.
    """
    # Check for context-local overrides first
    overrides_dict = _overrides.get()
    if overrides_dict and name in overrides_dict:
        fn = overrides_dict[name]
        return fn()

    # Check the global registry
    with _registry_lock:
        fn_candidate = _registry.get(name)

    if fn_candidate is None:
        available = ", ".join(sorted(_registry.keys())) or "(none)"
        msg = f"No CloudStorageClient implementation injected for provider '{name}'. Available providers: {available}"
        raise RuntimeError(msg)

    return fn_candidate()


@contextmanager
def override_get_client(fn: GetClient, name: str = _DEFAULT_PROVIDER) -> Generator[None, None, None]:
    """Temporarily override a cloud storage client factory.

    Args:
        fn: Callable that returns a CloudStorageClient instance.
        name: Name of the provider (defaults to 'default').

    Yields:
        None (context manager).
    """
    current = _overrides.get() or {}
    token = _overrides.set({**current, name: fn})
    try:
        yield
    finally:
        _overrides.reset(token)
