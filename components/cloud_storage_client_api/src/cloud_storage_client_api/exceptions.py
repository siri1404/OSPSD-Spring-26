"""Domain exceptions for cloud storage operations."""


class CloudStorageError(Exception):
    """Base exception for all cloud storage operations."""


class ObjectNotFoundError(CloudStorageError):
    """Raised when a requested storage object does not exist."""


class StorageOperationError(CloudStorageError):
    """Raised when a storage operation fails unexpectedly."""


class StorageValidationError(CloudStorageError):
    """Raised when request validation fails at the service boundary."""
