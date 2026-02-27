# cloud_storage_client_api/di.py
from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from contextvars import ContextVar
from threading import RLock

from cloud_storage_client_api.client import CloudStorageClient

GetClient = Callable[[], CloudStorageClient]

_DEFAULT_PROVIDER = "default"
_registry: dict[str, GetClient] = {}
_registry_lock = RLock()

# Per-context overrides (great for tests / parallel execution isolation)
_overrides: ContextVar[dict[str, GetClient]] = ContextVar("_overrides", default={})


def register_get_client(fn: GetClient, name: str = _DEFAULT_PROVIDER) -> None:
    with _registry_lock:
        _registry[name] = fn


def unregister_get_client(name: str = _DEFAULT_PROVIDER) -> None:
    with _registry_lock:
        _registry.pop(name, None)


def get_client(name: str = _DEFAULT_PROVIDER) -> CloudStorageClient:
    overrides = _overrides.get()
    if name in overrides:
        return overrides[name]()

    with _registry_lock:
        fn = _registry.get(name)

    if fn is None:
        available = ", ".join(sorted(_registry.keys())) or "(none)"
        raise RuntimeError(
            f"No CloudStorageClient implementation injected for provider '{name}'. "
            f"Available providers: {available}"
        )
    return fn()


@contextmanager
def override_get_client(fn: GetClient, name: str = _DEFAULT_PROVIDER):
    current = _overrides.get()
    token = _overrides.set({**current, name: fn})
    try:
        yield
    finally:
        _overrides.reset(token)
