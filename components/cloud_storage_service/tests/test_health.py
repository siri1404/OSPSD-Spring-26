"""Unit tests for health check endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


@pytest.mark.unit
def test_health_endpoint_returns_200(client: TestClient) -> None:
    """Test that health endpoint returns 200 OK."""
    response = client.get("/health")
    assert response.status_code == 200


@pytest.mark.unit
def test_health_endpoint_returns_correct_structure(client: TestClient) -> None:
    """Test that health endpoint returns correct JSON structure."""
    response = client.get("/health")
    data = response.json()

    assert "status" in data
    assert "service" in data
    assert "timestamp" in data


@pytest.mark.unit
def test_health_endpoint_returns_healthy_status(client: TestClient) -> None:
    """Test that health endpoint returns 'healthy' status."""
    response = client.get("/health")
    data = response.json()

    assert data["status"] == "healthy"
    assert data["service"] == "cloud-storage-service"


@pytest.mark.unit
def test_health_endpoint_timestamp_is_valid(client: TestClient) -> None:
    """Test that health endpoint returns a valid ISO timestamp."""
    from datetime import datetime

    response = client.get("/health")
    data = response.json()

    # Verify timestamp can be parsed
    timestamp = data["timestamp"]
    parsed_time = datetime.fromisoformat(timestamp)
    assert parsed_time is not None


@pytest.mark.unit
def test_health_endpoint_no_auth_required(client: TestClient) -> None:
    """Test that health endpoint doesn't require authentication."""
    # No Authorization header provided
    response = client.get("/health")
    assert response.status_code == 200
