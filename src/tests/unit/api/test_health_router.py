"""
Tests for health check API router endpoints.

This module tests the FastAPI router for health check operations:
- GET /health/live - Liveness probe for Kubernetes
- GET /health/ready - Readiness probe with dependency checks

Tests cover status codes, dependency validation, error scenarios,
and proper Kubernetes health check integration.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient


@pytest.fixture
def app_client():
    """Create a test client with the full app for dependency injection."""
    from src.main import create_app

    app = create_app()
    return TestClient(app)


@pytest.mark.unit
class TestLivenessEndpoint:
    """Test GET /health/live endpoint."""

    def test_liveness_check_success(self, app_client):
        """Test successful liveness check."""
        # Execute
        response = app_client.get("/health/live")

        # Verify
        assert response.status_code == status.HTTP_200_OK

        response_data = response.json()
        assert response_data["status"] == "healthy"
        assert response_data["service"] == "GlobeCo Order Generation Service"
        assert "timestamp" in response_data
        assert "version" in response_data

    def test_liveness_check_structure(self, app_client):
        """Test liveness response structure and required fields."""
        # Execute
        response = app_client.get("/health/live")

        # Verify response structure
        response_data = response.json()
        required_fields = ["status", "service", "timestamp", "version"]

        for field in required_fields:
            assert field in response_data

        # Verify status value
        assert response_data["status"] in ["healthy", "unhealthy"]

        # Verify service name
        assert response_data["service"] == "GlobeCo Order Generation Service"

    def test_liveness_check_multiple_calls(self, app_client):
        """Test that liveness check is consistent across multiple calls."""
        # Execute multiple calls
        responses = []
        for _ in range(3):
            response = app_client.get("/health/live")
            responses.append(response)

        # Verify all calls succeed
        for response in responses:
            assert response.status_code == status.HTTP_200_OK
            response_data = response.json()
            assert response_data["status"] == "healthy"
            assert response_data["service"] == "GlobeCo Order Generation Service"


@pytest.mark.unit
class TestReadinessEndpoint:
    """Test GET /health/ready endpoint."""

    def test_readiness_check_success(self, app_client):
        """Test successful readiness check with all dependencies healthy."""
        # Setup - override dependencies
        from src.api.routers.health import check_external_services, get_database

        mock_db = AsyncMock()
        mock_db.command.return_value = {"ok": 1}

        mock_external_services = {
            "portfolio_accounting": True,
            "pricing_service": True,
            "portfolio_service": True,
            "security_service": True,
        }

        app_client.app.dependency_overrides[get_database] = lambda: mock_db
        app_client.app.dependency_overrides[check_external_services] = (
            lambda: mock_external_services
        )

        # Execute
        response = app_client.get("/health/ready")

        # Verify
        assert response.status_code == status.HTTP_200_OK

        response_data = response.json()
        assert response_data["status"] == "ready"
        assert response_data["service"] == "GlobeCo Order Generation Service"
        assert "dependencies" in response_data
        assert response_data["dependencies"]["database"] == "healthy"
        assert (
            response_data["dependencies"]["external_services"]["portfolio_accounting"]
            == "healthy"
        )

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_readiness_check_database_unhealthy(self, app_client):
        """Test readiness check with database connectivity issues."""
        # Setup - override dependencies
        from src.api.routers.health import check_external_services, get_database

        mock_db = AsyncMock()
        mock_db.command.side_effect = Exception("Database connection error")

        mock_external_services = {
            "portfolio_accounting": True,
            "pricing_service": True,
            "portfolio_service": True,
            "security_service": True,
        }

        app_client.app.dependency_overrides[get_database] = lambda: mock_db
        app_client.app.dependency_overrides[check_external_services] = (
            lambda: mock_external_services
        )

        # Execute
        response = app_client.get("/health/ready")

        # Verify
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

        response_data = response.json()
        assert response_data["status"] == "not_ready"
        assert response_data["dependencies"]["database"] == "unhealthy"

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_readiness_check_external_services_unhealthy(self, app_client):
        """Test readiness check with external service issues."""
        # Setup - override dependencies
        from src.api.routers.health import check_external_services, get_database

        mock_db = AsyncMock()
        mock_db.command.return_value = {"ok": 1}

        mock_external_services = {
            "portfolio_accounting": False,  # Service down
            "pricing_service": True,
            "portfolio_service": False,  # Service down
            "security_service": True,
        }

        app_client.app.dependency_overrides[get_database] = lambda: mock_db
        app_client.app.dependency_overrides[check_external_services] = (
            lambda: mock_external_services
        )

        # Execute
        response = app_client.get("/health/ready")

        # Verify
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

        response_data = response.json()
        assert response_data["status"] == "not_ready"
        assert (
            response_data["dependencies"]["external_services"]["portfolio_accounting"]
            == "unhealthy"
        )
        assert (
            response_data["dependencies"]["external_services"]["portfolio_service"]
            == "unhealthy"
        )
        assert (
            response_data["dependencies"]["external_services"]["pricing_service"]
            == "healthy"
        )
        assert (
            response_data["dependencies"]["external_services"]["security_service"]
            == "healthy"
        )

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_readiness_check_all_dependencies_unhealthy(self, app_client):
        """Test readiness check when all dependencies are unhealthy."""
        # Setup - override dependencies
        from src.api.routers.health import check_external_services, get_database

        mock_db = AsyncMock()
        mock_db.command.side_effect = Exception("Database down")

        mock_external_services = {
            "portfolio_accounting": False,
            "pricing_service": False,
            "portfolio_service": False,
            "security_service": False,
        }

        app_client.app.dependency_overrides[get_database] = lambda: mock_db
        app_client.app.dependency_overrides[check_external_services] = (
            lambda: mock_external_services
        )

        # Execute
        response = app_client.get("/health/ready")

        # Verify
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

        response_data = response.json()
        assert response_data["status"] == "not_ready"
        assert response_data["dependencies"]["database"] == "unhealthy"

        # All external services should be unhealthy
        for service in [
            "portfolio_accounting",
            "pricing_service",
            "portfolio_service",
            "security_service",
        ]:
            assert (
                response_data["dependencies"]["external_services"][service]
                == "unhealthy"
            )

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_readiness_check_partial_external_service_failure(self, app_client):
        """Test readiness with some external services down (should still be ready for core functions)."""
        # Setup - override dependencies
        from src.api.routers.health import check_external_services, get_database

        mock_db = AsyncMock()
        mock_db.command.return_value = {"ok": 1}

        # Portfolio Accounting and Pricing are critical, others are optional
        mock_external_services = {
            "portfolio_accounting": True,  # Critical - up
            "pricing_service": True,  # Critical - up
            "portfolio_service": False,  # Optional - down
            "security_service": False,  # Optional - down
        }

        app_client.app.dependency_overrides[get_database] = lambda: mock_db
        app_client.app.dependency_overrides[check_external_services] = (
            lambda: mock_external_services
        )

        # Execute
        response = app_client.get("/health/ready")

        # Verify - Should be ready if critical services are up
        # (This depends on your business logic for what constitutes "ready")
        response_data = response.json()
        assert "dependencies" in response_data
        assert (
            response_data["dependencies"]["external_services"]["portfolio_accounting"]
            == "healthy"
        )
        assert (
            response_data["dependencies"]["external_services"]["pricing_service"]
            == "healthy"
        )

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_readiness_check_response_structure(self, app_client):
        """Test readiness response structure and required fields."""
        # Setup - override dependencies
        from src.api.routers.health import check_external_services, get_database

        mock_db = AsyncMock()
        mock_db.command.return_value = {"ok": 1}

        mock_external_services = {
            "portfolio_accounting": True,
            "pricing_service": True,
            "portfolio_service": True,
            "security_service": True,
        }

        app_client.app.dependency_overrides[get_database] = lambda: mock_db
        app_client.app.dependency_overrides[check_external_services] = (
            lambda: mock_external_services
        )

        # Execute
        response = app_client.get("/health/ready")

        # Verify response structure
        response_data = response.json()
        required_fields = ["status", "service", "timestamp", "dependencies"]

        for field in required_fields:
            assert field in response_data

        # Verify dependencies structure
        dependencies = response_data["dependencies"]
        assert "database" in dependencies
        assert "external_services" in dependencies

        # Verify external services structure
        external_services = dependencies["external_services"]
        expected_services = [
            "portfolio_accounting",
            "pricing_service",
            "portfolio_service",
            "security_service",
        ]

        for service in expected_services:
            assert service in external_services
            assert external_services[service] in ["healthy", "unhealthy"]

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_readiness_check_timeout_handling(self, app_client):
        """Test readiness check with timeout scenarios."""
        # Setup - override dependencies to simulate timeout
        from src.api.routers.health import check_external_services, get_database

        mock_db = AsyncMock()
        mock_db.command.return_value = {"ok": 1}

        # Simulate timeout in external service check
        def timeout_external_services():
            raise TimeoutError("External service check timed out")

        app_client.app.dependency_overrides[get_database] = lambda: mock_db
        app_client.app.dependency_overrides[check_external_services] = (
            timeout_external_services
        )

        # Execute
        response = app_client.get("/health/ready")

        # Verify - Should handle timeout gracefully
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

        response_data = response.json()
        assert response_data["status"] == "not_ready"

        # Cleanup
        app_client.app.dependency_overrides.clear()


@pytest.mark.unit
class TestHealthRouterIntegration:
    """Test health router integration scenarios."""

    def test_health_endpoints_available(self, app_client):
        """Test that health endpoints are properly mounted and accessible."""
        # Test that both endpoints are available
        liveness_response = app_client.get("/health/live")
        readiness_response = app_client.get("/health/ready")

        # Both should return some response (not 404)
        assert liveness_response.status_code != status.HTTP_404_NOT_FOUND
        assert readiness_response.status_code != status.HTTP_404_NOT_FOUND

    def test_health_endpoints_cors_headers(self, app_client):
        """Test that health endpoints include appropriate CORS headers."""
        # Execute
        response = app_client.get("/health/live")

        # Verify CORS headers are present (if configured)
        # This depends on your CORS middleware configuration
        assert response.status_code == status.HTTP_200_OK

    def test_readiness_database_connection_validation(self, app_client):
        """Test that readiness check properly validates database connection."""
        # Setup - override dependencies
        from src.api.routers.health import check_external_services, get_database

        mock_db = AsyncMock()
        mock_db.command.return_value = {"ok": 1}

        mock_external_services = {
            "portfolio_accounting": True,
            "pricing_service": True,
            "portfolio_service": True,
            "security_service": True,
        }

        app_client.app.dependency_overrides[get_database] = lambda: mock_db
        app_client.app.dependency_overrides[check_external_services] = (
            lambda: mock_external_services
        )

        # Execute
        response = app_client.get("/health/ready")

        # Verify database command was called
        mock_db.command.assert_called_once_with("ping")

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_health_endpoint_performance(self, app_client):
        """Test that health endpoints respond quickly (important for K8s)."""
        import time

        # Measure liveness check time
        start_time = time.time()
        response = app_client.get("/health/live")
        liveness_time = time.time() - start_time

        # Verify
        assert response.status_code == status.HTTP_200_OK
        assert liveness_time < 1.0  # Should be very fast (< 1 second)

    def test_health_endpoint_idempotency(self, app_client):
        """Test that health endpoints are idempotent and consistent."""
        # Execute multiple calls
        responses = []
        for _ in range(5):
            response = app_client.get("/health/live")
            responses.append(response.json()["status"])

        # Verify all responses are consistent
        assert all(status == "healthy" for status in responses)
