"""Middleware package for cloud storage service."""

from cloud_storage_service.middleware.telemetry import telemetry_middleware

__all__ = ["telemetry_middleware"]
