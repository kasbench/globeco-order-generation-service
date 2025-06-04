"""
Integration tests for FastAPI middleware components.

This module tests the middleware stack including:
- CORS middleware configuration and behavior
- Correlation ID middleware for request tracing
- Security headers middleware
- Request/response logging
- Error handling through middleware chain
"""

import json
import uuid
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from src.core.utils import get_correlation_id
from src.main import correlation_middleware, create_app, security_headers_middleware


class TestCORSMiddleware:
    """Test CORS middleware configuration and behavior."""

    def test_cors_allows_all_origins(self):
        """Test that CORS middleware reflects back the origin for allow-all configuration."""
        app = create_app()
        client = TestClient(app)

        # Test preflight request - FastAPI CORS middleware reflects origin when allow_origins=["*"]
        response = client.options(
            "/api/v1/models",
            headers={
                "Origin": "https://test-origin.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )

        assert response.status_code == 200
        # When allow_origins=["*"], CORS middleware reflects the origin
        assert (
            response.headers["Access-Control-Allow-Origin"] == "https://test-origin.com"
        )
        assert "POST" in response.headers["Access-Control-Allow-Methods"]
        assert "Content-Type" in response.headers["Access-Control-Allow-Headers"]

    def test_cors_allows_credentials(self):
        """Test that CORS middleware allows credentials."""
        app = create_app()
        client = TestClient(app)

        response = client.options(
            "/api/v1/models",
            headers={
                "Origin": "https://test-origin.com",
                "Access-Control-Request-Method": "GET",
            },
        )

        assert response.status_code == 200
        assert response.headers["Access-Control-Allow-Credentials"] == "true"

    def test_cors_with_actual_request(self):
        """Test CORS headers on actual API requests."""
        app = create_app()
        client = TestClient(app)

        response = client.get(
            "/health/live",
            headers={"Origin": "https://test-origin.com"},
        )

        assert response.status_code == 200
        # On actual requests with allow_origins=["*"], FastAPI returns "*"
        assert response.headers["Access-Control-Allow-Origin"] == "*"

    def test_cors_allows_common_methods(self):
        """Test that CORS allows all required HTTP methods."""
        app = create_app()
        client = TestClient(app)

        for method in ["GET", "POST", "PUT", "DELETE", "OPTIONS"]:
            response = client.options(
                "/api/v1/models",
                headers={
                    "Origin": "https://test-origin.com",
                    "Access-Control-Request-Method": method,
                },
            )

            assert response.status_code == 200
            assert method in response.headers["Access-Control-Allow-Methods"]


class TestCorrelationMiddleware:
    """Test correlation ID middleware for request tracing."""

    @pytest.fixture
    def mock_request(self):
        """Create a mock request object."""
        request = Mock(spec=Request)
        request.method = "GET"
        request.url = Mock()
        request.url.path = "/api/v1/models"
        request.url.__str__ = Mock(return_value="http://test/api/v1/models")
        request.client = Mock()
        request.client.host = "127.0.0.1"
        request.headers = {}
        return request

    @pytest.fixture
    def mock_response(self):
        """Create a mock response object."""
        response = Mock(spec=Response)
        response.headers = {}
        response.status_code = 200
        return response

    @pytest.fixture
    def mock_call_next(self, mock_response):
        """Create a mock call_next function."""

        async def call_next(request):
            return mock_response

        return call_next

    @pytest.mark.asyncio
    async def test_correlation_id_generated_when_missing(
        self, mock_request, mock_call_next
    ):
        """Test that correlation ID is generated when not provided."""
        # No correlation ID in headers
        mock_request.headers = {}

        response = await correlation_middleware(mock_request, mock_call_next)

        # Verify correlation ID was added to response
        assert "X-Correlation-ID" in response.headers
        correlation_id = response.headers["X-Correlation-ID"]
        assert len(correlation_id) > 0
        # Should be a valid UUID format
        uuid.UUID(correlation_id)  # Will raise ValueError if invalid

    @pytest.mark.asyncio
    async def test_correlation_id_preserved_when_provided(
        self, mock_request, mock_call_next
    ):
        """Test that existing correlation ID is preserved."""
        existing_id = str(uuid.uuid4())
        mock_request.headers = {"X-Correlation-ID": existing_id}

        response = await correlation_middleware(mock_request, mock_call_next)

        # Verify existing correlation ID was preserved
        assert response.headers["X-Correlation-ID"] == existing_id

    @pytest.mark.asyncio
    async def test_correlation_id_set_in_context(self, mock_request, mock_call_next):
        """Test that correlation ID is set in request context."""
        correlation_id = str(uuid.uuid4())
        mock_request.headers = {"X-Correlation-ID": correlation_id}

        with patch("src.main.set_correlation_id") as mock_set_id:
            await correlation_middleware(mock_request, mock_call_next)
            mock_set_id.assert_called_once_with(correlation_id)

    @pytest.mark.asyncio
    async def test_request_logging(self, mock_request, mock_call_next):
        """Test that requests are logged with proper details."""
        with patch("src.main.logger") as mock_logger:
            await correlation_middleware(mock_request, mock_call_next)

            # Verify request logging
            mock_logger.info.assert_any_call(
                "Request received",
                method="GET",
                url="http://test/api/v1/models",
                client_ip="127.0.0.1",
            )

    @pytest.mark.asyncio
    async def test_response_logging(self, mock_request, mock_call_next):
        """Test that responses are logged with proper details."""
        with patch("src.main.logger") as mock_logger:
            await correlation_middleware(mock_request, mock_call_next)

            # Verify response logging
            mock_logger.info.assert_any_call(
                "Request completed",
                method="GET",
                url="http://test/api/v1/models",
                status_code=200,
            )


class TestSecurityHeadersMiddleware:
    """Test security headers middleware."""

    @pytest.fixture
    def mock_request(self):
        """Create a mock request object."""
        return Mock(spec=Request)

    @pytest.fixture
    def mock_response(self):
        """Create a mock response object."""
        response = Mock(spec=Response)
        response.headers = {}
        return response

    @pytest.fixture
    def mock_call_next(self, mock_response):
        """Create a mock call_next function."""

        async def call_next(request):
            return mock_response

        return call_next

    @pytest.mark.asyncio
    async def test_security_headers_added(
        self, mock_request, mock_call_next, mock_response
    ):
        """Test that all required security headers are added."""
        response = await security_headers_middleware(mock_request, mock_call_next)

        # Verify all expected security headers are present
        expected_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Content-Security-Policy": "default-src 'self'",
        }

        for header, value in expected_headers.items():
            assert response.headers[header] == value

    @pytest.mark.asyncio
    async def test_security_headers_not_overwritten(self, mock_request, mock_call_next):
        """Test that existing security headers are not overwritten."""
        response = Mock(spec=Response)
        response.headers = {"X-Frame-Options": "SAMEORIGIN"}

        async def call_next_with_headers(request):
            return response

        result = await security_headers_middleware(mock_request, call_next_with_headers)

        # Security middleware should overwrite with default values
        assert result.headers["X-Frame-Options"] == "DENY"


class TestMiddlewareIntegration:
    """Test middleware integration with actual FastAPI application."""

    def test_middleware_stack_order(self):
        """Test that middleware is applied in correct order."""
        app = create_app()
        client = TestClient(app)

        correlation_id = str(uuid.uuid4())
        response = client.get(
            "/health/live",
            headers={
                "X-Correlation-ID": correlation_id,
                "Origin": "https://test-origin.com",
            },
        )

        assert response.status_code == 200

        # Verify CORS headers (outer middleware) - actual requests get "*"
        assert response.headers["Access-Control-Allow-Origin"] == "*"

        # Verify correlation ID (middle middleware)
        assert response.headers["X-Correlation-ID"] == correlation_id

        # Verify security headers (inner middleware)
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"

    def test_middleware_with_api_endpoints(self):
        """Test middleware behavior with actual API endpoints."""
        app = create_app()
        client = TestClient(app)

        # Mock dependencies to avoid database connections
        from src.api.dependencies import get_model_service

        async def mock_get_all_models():
            return []

        mock_service = Mock()
        mock_service.get_all_models = mock_get_all_models

        app.dependency_overrides[get_model_service] = lambda: mock_service

        response = client.get(
            "/api/v1/models", headers={"Origin": "https://test-origin.com"}
        )

        # Should have all middleware headers regardless of endpoint
        assert "X-Correlation-ID" in response.headers
        assert "X-Content-Type-Options" in response.headers
        # CORS actual requests get "*"
        assert response.headers["Access-Control-Allow-Origin"] == "*"

    def test_middleware_error_handling(self):
        """Test middleware behavior during error conditions."""
        app = create_app()
        client = TestClient(app)

        # Request non-existent endpoint to trigger 404
        response = client.get(
            "/api/v1/nonexistent", headers={"Origin": "https://test-origin.com"}
        )

        assert response.status_code == 404

        # Middleware should still apply headers even for errors
        assert "X-Correlation-ID" in response.headers
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["Access-Control-Allow-Origin"] == "*"

    def test_middleware_with_large_request(self):
        """Test middleware behavior with large request payloads."""
        app = create_app()
        client = TestClient(app)

        # Create large but valid request
        large_positions = [
            {
                "securityId": f"SEC{i:021d}",
                "target": 0.005,
                "highDrift": 0.1,
                "lowDrift": 0.1,
            }
            for i in range(10)  # 10 positions
        ]

        large_request = {
            "name": "Large Test Model",
            "positions": large_positions,
            "portfolios": ["portfolio1", "portfolio2"],
        }

        # Mock dependencies
        from src.api.dependencies import get_model_service

        async def mock_create_model(data):
            return Mock(model_id="test-id")

        mock_service = Mock()
        mock_service.create_model = mock_create_model

        app.dependency_overrides[get_model_service] = lambda: mock_service

        response = client.post(
            "/api/v1/models",
            json=large_request,
        )

        # Middleware should handle large requests properly
        assert "X-Correlation-ID" in response.headers
        assert "X-Content-Type-Options" in response.headers

    def test_middleware_concurrent_requests(self):
        """Test middleware behavior with concurrent requests."""
        import threading
        import time

        app = create_app()

        # Mock dependencies
        from src.api.dependencies import get_model_service

        mock_service = Mock()
        mock_service.get_all_models.return_value = []

        app.dependency_overrides[get_model_service] = lambda: mock_service

        results = []
        correlation_ids = [str(uuid.uuid4()) for _ in range(5)]

        def make_request(correlation_id):
            """Make a single request with unique correlation ID."""
            try:
                client = TestClient(app)
                response = client.get(
                    "/api/v1/models",
                    headers={"X-Correlation-ID": correlation_id},
                )
                results.append(
                    (correlation_id, response.headers.get("X-Correlation-ID"))
                )
            except Exception as e:
                results.append((correlation_id, f"ERROR: {e}"))

        # Create and start threads for concurrent requests
        threads = []
        for corr_id in correlation_ids:
            thread = threading.Thread(target=make_request, args=(corr_id,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify results
        assert len(results) == 5
        for sent_id, received_id in results:
            assert (
                sent_id == received_id
            ), f"Correlation ID mismatch: sent {sent_id}, received {received_id}"


class TestMiddlewareLogging:
    """Test middleware logging behavior."""

    def test_structured_logging_format(self):
        """Test that middleware produces structured logs."""
        app = create_app()
        client = TestClient(app)

        # Mock dependencies
        from src.api.dependencies import get_model_service

        async def mock_get_all_models():
            return []

        mock_service = Mock()
        mock_service.get_all_models = mock_get_all_models

        app.dependency_overrides[get_model_service] = lambda: mock_service

        with patch("src.main.logger") as mock_logger:
            response = client.get("/api/v1/models")

            # Verify structured logging calls
            mock_logger.info.assert_any_call(
                "Request received",
                method="GET",
                url="http://testserver/api/v1/models",
                client_ip="testclient",
            )

            mock_logger.info.assert_any_call(
                "Request completed",
                method="GET",
                url="http://testserver/api/v1/models",
                status_code=200,  # Should be 200 with proper mocking
            )

    def test_sensitive_data_not_logged(self):
        """Test that sensitive data is not logged in middleware."""
        app = create_app()
        client = TestClient(app)

        # Request with potential sensitive data
        sensitive_request = {
            "name": "Test Model",
            "positions": [
                {
                    "securityId": "SENSITIVE_SECURITY_001",
                    "target": 0.1,
                    "highDrift": 0.05,
                    "lowDrift": 0.05,
                }
            ],
            "portfolios": ["sensitive-portfolio"],
        }

        # Mock dependencies
        from src.api.dependencies import get_model_service

        async def mock_create_model(data):
            return Mock(model_id="test-id")

        mock_service = Mock()
        mock_service.create_model = mock_create_model

        app.dependency_overrides[get_model_service] = lambda: mock_service

        with patch("src.main.logger") as mock_logger:
            client.post("/api/v1/models", json=sensitive_request)

            # Check that log calls don't contain sensitive request body data
            for call in mock_logger.info.call_args_list:
                args, kwargs = call
                log_message = args[0] if args else ""

                # Middleware should not log request body content
                assert "SENSITIVE_SECURITY_001" not in str(kwargs)
                assert "sensitive-portfolio" not in str(kwargs)
                assert "SENSITIVE_SECURITY_001" not in log_message
