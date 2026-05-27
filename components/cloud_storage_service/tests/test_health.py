"""Unit tests for health check endpoint."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


@pytest.mark.unit
def test_health_endpoint_returns_200(client: TestClient) -> None:
    """Health endpoint returns 200 OK."""
    response = client.get("/health")
    assert response.status_code == 200


@pytest.mark.unit
def test_health_endpoint_returns_correct_structure(client: TestClient) -> None:
    """Health endpoint returns correct JSON structure with required fields."""
    response = client.get("/health")
    data = response.json()

    assert "status" in data
    assert "service" in data
    assert "timestamp" in data


@pytest.mark.unit
def test_health_endpoint_returns_healthy_status(client: TestClient) -> None:
    """Health endpoint returns 'healthy' status and service name."""
    response = client.get("/health")
    data = response.json()

    assert data["status"] == "healthy"
    assert data["service"] == "cloud-storage-service"


@pytest.mark.unit
def test_health_endpoint_timestamp_is_valid_iso8601(client: TestClient) -> None:
    """Health endpoint returns a valid timezone-aware ISO 8601 timestamp."""
    response = client.get("/health")
    data = response.json()

    # datetime.fromisoformat handles ISO 8601 timestamps including the
    # timezone-aware UTC value emitted by health_check().
    parsed = datetime.fromisoformat(data["timestamp"])
    assert parsed.tzinfo is not None


@pytest.mark.unit
def test_health_endpoint_no_auth_required(client: TestClient) -> None:
    """Health endpoint doesn't require authentication."""
    response = client.get("/health")
    assert response.status_code == 200
