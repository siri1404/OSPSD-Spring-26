"""Typed domain exceptions for cloud storage operations."""

from __future__ import annotations


class InvalidContainerError(ValueError):
    """Raised when a container or bucket name is invalid."""


class InvalidObjectNameError(ValueError):
    """Raised when an object key or path is invalid."""


class InvalidFileObjectError(ValueError):
    """Raised when a provided file object cannot be uploaded."""


class AuthenticationError(PermissionError):
    """Raised when the storage provider rejects credentials or access."""


class ContainerNotFoundError(FileNotFoundError):
    """Raised when a referenced container or bucket does not exist."""


class LocalFileAccessError(OSError):
    """Raised when a local filesystem path cannot be read from or written to."""


class ObjectNotFoundError(FileNotFoundError):
    """Raised when a requested object does not exist."""


class StorageBackendError(Exception):
    """Raised when the underlying storage provider fails unexpectedly."""
