"""Cloud Storage Service - FastAPI service for cloud storage operations."""

# Use relative import so packaging works regardless of PYTHONPATH configuration.
from .main import app

__all__ = ["app"]
