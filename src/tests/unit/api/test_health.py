"""
Tests for health check endpoints.

This module tests the health check functionality including liveness,
readiness, and comprehensive health endpoints.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest

from src.main import create_app


@pytest.fixture
def health_client():
    """Create a test client for health endpoint testing."""
    app = create_app()
    return TestClient(app)


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_liveness_probe_healthy(self, health_client):
        """Test liveness probe returns healthy status."""
        response = health_client.get("/health/live")

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "status" in data
        assert "timestamp" in data
        assert "service" in data
        assert "version" in data
        assert "correlation_id" in data
        assert "checks" in data

        # Check service information
        assert data["service"] == "GlobeCo Order Generation Service"
        assert data["version"] == "0.1.0"

        # Check that optimization engine is checked for liveness
        assert "optimization_engine" in data["checks"]

        # External services should not be checked for liveness
        assert "external_services" not in data["checks"]

    def test_readiness_probe_healthy(self, health_client):
        """Test readiness probe returns healthy status."""
        response = health_client.get("/health/ready")

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "status" in data
        assert "checks" in data

        # Check that all components are checked for readiness
        assert "database" in data["checks"]
        assert "external_services" in data["checks"]
        assert "optimization_engine" in data["checks"]

    def test_general_health_endpoint(self, health_client):
        """Test general health endpoint with all checks."""
        response = health_client.get("/health/health")

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "status" in data
        assert "checks" in data
        assert "uptime_seconds" in data

        # Check uptime is positive
        assert data["uptime_seconds"] >= 0

    def test_health_endpoint_with_parameters(self, health_client):
        """Test health endpoint with query parameters."""
        # Test without external services
        response = health_client.get("/health/health?include_external=false")
        assert response.status_code == 200
        data = response.json()
        assert "external_services" not in data["checks"]

        # Test without optimization engine
        response = health_client.get("/health/health?include_optimization=false")
        assert response.status_code == 200
        data = response.json()
        assert "optimization_engine" not in data["checks"]

    def test_correlation_id_in_health_response(self, health_client):
        """Test that health responses include correlation IDs."""
        response = health_client.get("/health/live")

        assert response.status_code == 200
        data = response.json()

        # Check correlation ID is present and valid
        assert "correlation_id" in data
        assert len(data["correlation_id"]) == 36  # UUID format

        # Check correlation ID is also in headers
        assert "X-Correlation-ID" in response.headers

    @patch("src.api.routers.health.health_check.check_optimization_engine")
    def test_liveness_probe_unhealthy_optimization(self, mock_check, health_client):
        """Test liveness probe when optimization engine is unhealthy."""
        # Mock optimization engine failure
        mock_check.return_value = {
            "status": "unhealthy",
            "message": "CVXPY solver not available",
            "solver_status": None,
        }

        response = health_client.get("/health/live")

        # Should return 503 for unhealthy optimization engine
        assert response.status_code == 503
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "SERVICE_UNAVAILABLE"

    def test_security_headers_in_health_response(self, health_client):
        """Test that security headers are added to health responses."""
        response = health_client.get("/health/live")

        # Check security headers
        assert "X-Content-Type-Options" in response.headers
        assert "X-Frame-Options" in response.headers
        assert "X-XSS-Protection" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"


@pytest.mark.mathematical
class TestOptimizationEngineHealthCheck:
    """Test optimization engine health checks specifically."""

    def test_optimization_engine_test_problem(self, health_client):
        """Test that optimization engine health check uses a test problem."""
        response = health_client.get("/health/health")

        assert response.status_code == 200
        data = response.json()

        # Check optimization engine status
        opt_check = data["checks"]["optimization_engine"]
        assert "status" in opt_check
        assert "solver_status" in opt_check

        # Should be healthy with optimal status
        assert opt_check["status"] == "healthy"
        assert opt_check["solver_status"] == "optimal"
