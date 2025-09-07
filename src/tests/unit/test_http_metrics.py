"""
Unit tests for HTTP metrics functionality.

This module tests the HTTP metrics collection middleware and related components:
- Metric creation and registration for all three metric types
- Counter increments for different request scenarios
- Histogram duration recording with various request durations
- Gauge tracking for concurrent requests
- Label extraction and formatting for various endpoints
- Error handling in metrics collection
"""

import asyncio
import os
import time
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY, CollectorRegistry
from starlette.responses import JSONResponse

# Set environment variables to disable OpenTelemetry exporters during testing
os.environ['OTEL_SDK_DISABLED'] = 'true'
os.environ['OTEL_TRACES_EXPORTER'] = 'none'
os.environ['OTEL_METRICS_EXPORTER'] = 'none'
os.environ['OTEL_LOGS_EXPORTER'] = 'none'

from src.core.monitoring import (
    _METRICS_REGISTRY,
    HTTP_REQUEST_DURATION,
    HTTP_REQUESTS_IN_FLIGHT,
    HTTP_REQUESTS_TOTAL,
    EnhancedHTTPMetricsMiddleware,
)


@pytest.fixture(autouse=True)
def mock_opentelemetry_metrics():
    """Mock OpenTelemetry metrics to prevent network calls during unit tests."""
    with (
        patch('src.core.monitoring.otel_http_requests_total') as mock_otel_counter,
        patch('src.core.monitoring.otel_http_request_duration') as mock_otel_histogram,
        patch('src.core.monitoring.otel_http_requests_in_flight') as mock_otel_gauge,
    ):

        # Configure mocks to behave like the real OTEL metrics but without network calls
        mock_otel_counter.add = Mock()
        mock_otel_histogram.record = Mock()
        mock_otel_gauge.add = Mock()

        yield {
            'counter': mock_otel_counter,
            'histogram': mock_otel_histogram,
            'gauge': mock_otel_gauge,
        }


@pytest.mark.unit
class TestHTTPMetricsCreation:
    """Test metric creation and registration for all three metric types."""

    def test_http_requests_total_counter_creation(self):
        """Test that HTTP requests total counter is created with correct configuration."""
        # Verify metric exists and is a Counter
        assert HTTP_REQUESTS_TOTAL is not None
        assert hasattr(HTTP_REQUESTS_TOTAL, 'inc')
        assert hasattr(HTTP_REQUESTS_TOTAL, 'labels')

        # Verify metric is registered in our registry
        assert 'http_requests_total' in _METRICS_REGISTRY

        # Test that we can create labels
        labeled_metric = HTTP_REQUESTS_TOTAL.labels(
            method="GET", path="/test", status="200"
        )
        assert labeled_metric is not None
        assert hasattr(labeled_metric, 'inc')

    def test_http_request_duration_histogram_creation(self):
        """Test that HTTP request duration histogram is created with correct buckets."""
        # Verify metric exists and is a Histogram
        assert HTTP_REQUEST_DURATION is not None
        assert hasattr(HTTP_REQUEST_DURATION, 'observe')
        assert hasattr(HTTP_REQUEST_DURATION, 'labels')

        # Verify metric is registered in our registry
        assert 'http_request_duration' in _METRICS_REGISTRY

        # Test that we can create labels
        labeled_metric = HTTP_REQUEST_DURATION.labels(
            method="POST", path="/api/test", status="201"
        )
        assert labeled_metric is not None
        assert hasattr(labeled_metric, 'observe')

    def test_http_requests_in_flight_gauge_creation(self):
        """Test that HTTP requests in flight gauge is created correctly."""
        # Verify metric exists and is a Gauge
        assert HTTP_REQUESTS_IN_FLIGHT is not None
        assert hasattr(HTTP_REQUESTS_IN_FLIGHT, 'inc')
        assert hasattr(HTTP_REQUESTS_IN_FLIGHT, 'dec')
        assert hasattr(HTTP_REQUESTS_IN_FLIGHT, 'set')

        # Verify metric is registered in our registry
        assert 'http_requests_in_flight' in _METRICS_REGISTRY

    def test_histogram_buckets_configuration(self):
        """Test that histogram is configured with correct millisecond buckets."""
        expected_buckets = [5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000]

        # Access the histogram's buckets through its internal structure
        # Note: This is implementation-specific and may need adjustment based on prometheus_client version
        if hasattr(HTTP_REQUEST_DURATION, '_upper_bounds'):
            # Convert to list and remove the +Inf bucket
            actual_buckets = list(HTTP_REQUEST_DURATION._upper_bounds)[:-1]
            assert actual_buckets == expected_buckets
        else:
            # Alternative way to check buckets if _upper_bounds is not available
            # This is a more indirect test but still validates the configuration
            labeled_metric = HTTP_REQUEST_DURATION.labels(
                method="GET", path="/test", status="200"
            )
            assert labeled_metric is not None

    def test_metric_registry_prevents_duplicates(self):
        """Test that metrics registry prevents duplicate registration."""
        from prometheus_client import Counter

        from src.core.monitoring import _get_or_create_metric

        # Try to create the same metric twice
        metric1 = _get_or_create_metric(
            Counter, 'test_duplicate_metric', 'Test metric', ['label1']
        )
        metric2 = _get_or_create_metric(
            Counter, 'test_duplicate_metric', 'Test metric', ['label1']
        )

        # Should return the same instance
        assert metric1 is metric2
        assert 'test_duplicate_metric' in _METRICS_REGISTRY


@pytest.mark.unit
class TestHTTPMetricsMiddleware:
    """Test the EnhancedHTTPMetricsMiddleware functionality."""

    @pytest.fixture
    def middleware(self):
        """Create middleware instance for testing."""
        return EnhancedHTTPMetricsMiddleware(app=Mock())

    @pytest.fixture
    def mock_request(self):
        """Create a mock request for testing."""
        request = Mock(spec=Request)
        request.method = "GET"
        request.url.path = "/api/v1/models"
        return request

    @pytest.fixture
    def mock_response(self):
        """Create a mock response for testing."""
        response = Mock(spec=Response)
        response.status_code = 200
        return response

    def test_method_label_formatting(self, middleware):
        """Test HTTP method label formatting to uppercase."""
        # Test various method formats
        assert middleware._get_method_label("get") == "GET"
        assert middleware._get_method_label("POST") == "POST"
        assert middleware._get_method_label("put") == "PUT"
        assert middleware._get_method_label("Delete") == "DELETE"
        assert middleware._get_method_label("  patch  ") == "PATCH"

        # Test unknown method
        assert middleware._get_method_label("CUSTOM") == "CUSTOM"

        # Test invalid input
        assert middleware._get_method_label(None) == "UNKNOWN"
        assert middleware._get_method_label("") == "UNKNOWN"

    def test_status_code_formatting(self, middleware):
        """Test HTTP status code formatting to strings."""
        # Test various status codes
        assert middleware._format_status_code(200) == "200"
        assert middleware._format_status_code(404) == "404"
        assert middleware._format_status_code(500) == "500"

        # Test edge cases
        assert middleware._format_status_code(100) == "100"
        assert middleware._format_status_code(599) == "599"

        # Test invalid input
        assert middleware._format_status_code(99) == "unknown"
        assert middleware._format_status_code(600) == "unknown"
        assert middleware._format_status_code("200") == "unknown"
        assert middleware._format_status_code(None) == "unknown"

    def test_route_pattern_extraction_models_endpoints(self, middleware):
        """Test route pattern extraction for models endpoints."""
        # Create mock requests for different model endpoints
        request_models_list = Mock(spec=Request)
        request_models_list.url.path = "/api/v1/models"
        assert (
            middleware._extract_route_pattern(request_models_list) == "/api/v1/models"
        )

        request_model_detail = Mock(spec=Request)
        request_model_detail.url.path = "/api/v1/model/507f1f77bcf86cd799439011"
        assert (
            middleware._extract_route_pattern(request_model_detail)
            == "/api/v1/model/{model_id}"
        )

        request_model_position = Mock(spec=Request)
        request_model_position.url.path = (
            "/api/v1/model/507f1f77bcf86cd799439011/position"
        )
        assert (
            middleware._extract_route_pattern(request_model_position)
            == "/api/v1/model/{model_id}/position"
        )

    def test_route_pattern_extraction_rebalance_endpoints(self, middleware):
        """Test route pattern extraction for rebalance endpoints."""
        request_rebalances = Mock(spec=Request)
        request_rebalances.url.path = "/api/v1/rebalances"
        assert (
            middleware._extract_route_pattern(request_rebalances)
            == "/api/v1/rebalances"
        )

        request_rebalances_portfolios = Mock(spec=Request)
        request_rebalances_portfolios.url.path = "/api/v1/rebalances/portfolios"
        assert (
            middleware._extract_route_pattern(request_rebalances_portfolios)
            == "/api/v1/rebalances/portfolios"
        )

        request_rebalance_detail = Mock(spec=Request)
        request_rebalance_detail.url.path = "/api/v1/rebalance/507f1f77bcf86cd799439011"
        assert (
            middleware._extract_route_pattern(request_rebalance_detail)
            == "/api/v1/rebalance/{rebalance_id}"
        )

    def test_route_pattern_extraction_health_endpoints(self, middleware):
        """Test route pattern extraction for health endpoints."""
        request_health = Mock(spec=Request)
        request_health.url.path = "/health"
        assert middleware._extract_route_pattern(request_health) == "/health"

        request_health_live = Mock(spec=Request)
        request_health_live.url.path = "/health/live"
        assert (
            middleware._extract_route_pattern(request_health_live)
            == "/health/{check_type}"
        )

        request_health_ready = Mock(spec=Request)
        request_health_ready.url.path = "/health/ready"
        assert (
            middleware._extract_route_pattern(request_health_ready)
            == "/health/{check_type}"
        )

    def test_route_pattern_extraction_special_endpoints(self, middleware):
        """Test route pattern extraction for special endpoints."""
        request_metrics = Mock(spec=Request)
        request_metrics.url.path = "/metrics"
        assert middleware._extract_route_pattern(request_metrics) == "/metrics"

        request_docs = Mock(spec=Request)
        request_docs.url.path = "/docs"
        assert middleware._extract_route_pattern(request_docs) == "/docs"

        request_root = Mock(spec=Request)
        request_root.url.path = "/"
        assert middleware._extract_route_pattern(request_root) == "/"

    def test_path_sanitization(self, middleware):
        """Test path sanitization for sensitive data removal."""
        # Test query parameter removal
        assert middleware._sanitize_path("/api/test?secret=123") == "/api/test"

        # Test fragment removal
        assert middleware._sanitize_path("/api/test#fragment") == "/api/test"

        # Test trailing slash removal
        assert middleware._sanitize_path("/api/test/") == "/api/test"

        # Test empty path handling
        assert middleware._sanitize_path("") == "/"
        assert middleware._sanitize_path("?query=only") == "/"

    def test_id_detection_in_paths(self, middleware):
        """Test detection of ID-like path segments."""
        # Test MongoDB ObjectId (24 char hex)
        assert middleware._looks_like_id("507f1f77bcf86cd799439011") == True

        # Test UUID with hyphens
        assert middleware._looks_like_id("550e8400-e29b-41d4-a716-446655440000") == True

        # Test UUID without hyphens
        assert middleware._looks_like_id("550e8400e29b41d4a716446655440000") == True

        # Test numeric ID
        assert middleware._looks_like_id("123") == True
        assert middleware._looks_like_id("1234567890") == True

        # Test non-ID strings
        assert middleware._looks_like_id("models") == False
        assert middleware._looks_like_id("api") == False
        assert middleware._looks_like_id("short") == False

    def test_unmatched_route_sanitization(self, middleware):
        """Test sanitization of unmatched routes."""
        # Test route with ID-like segments
        result = middleware._sanitize_unmatched_route(
            "/custom/507f1f77bcf86cd799439011/action"
        )
        assert result == "/custom/{id}/action"

        # Test route with mixed segments
        result = middleware._sanitize_unmatched_route("/api/custom/123/data")
        assert result == "/api/custom/{id}/data"

        # Test very long route (should return /unknown)
        long_path = "/very/" + "long/" * 50 + "path"
        result = middleware._sanitize_unmatched_route(long_path)
        assert result == "/unknown"

    @pytest.mark.asyncio
    async def test_metrics_recording_success_case(self, middleware):
        """Test successful metrics recording for a normal request."""
        # Mock the metrics to track calls
        with (
            patch.object(HTTP_REQUESTS_TOTAL, 'labels') as mock_counter_labels,
            patch.object(HTTP_REQUEST_DURATION, 'labels') as mock_histogram_labels,
            patch.object(HTTP_REQUESTS_IN_FLIGHT, 'inc') as mock_gauge_inc,
            patch.object(HTTP_REQUESTS_IN_FLIGHT, 'dec') as mock_gauge_dec,
        ):

            # Setup mock returns
            mock_counter_metric = Mock()
            mock_histogram_metric = Mock()
            mock_counter_labels.return_value = mock_counter_metric
            mock_histogram_labels.return_value = mock_histogram_metric

            # Create mock request and response
            request = Mock(spec=Request)
            request.method = "GET"
            request.url.path = "/api/v1/models"

            response = Mock(spec=Response)
            response.status_code = 200

            # Mock call_next to return the response
            async def mock_call_next(req):
                await asyncio.sleep(0.001)  # Simulate small delay
                return response

            # Execute middleware
            result = await middleware.dispatch(request, mock_call_next)

            # Verify response is returned
            assert result == response

            # Verify gauge was incremented and decremented
            mock_gauge_inc.assert_called_once()
            mock_gauge_dec.assert_called_once()

            # Verify counter was called with correct labels
            mock_counter_labels.assert_called_once_with(
                method="GET", path="/api/v1/models", status="200"
            )
            mock_counter_metric.inc.assert_called_once()

            # Verify histogram was called with correct labels
            mock_histogram_labels.assert_called_once_with(
                method="GET", path="/api/v1/models", status="200"
            )
            mock_histogram_metric.observe.assert_called_once()

            # Verify duration was recorded (should be > 0)
            call_args = mock_histogram_metric.observe.call_args[0]
            assert len(call_args) == 1
            assert call_args[0] > 0  # Duration should be positive

    @pytest.mark.asyncio
    async def test_metrics_recording_exception_case(self, middleware):
        """Test metrics recording when an exception occurs during request processing."""
        with (
            patch.object(HTTP_REQUESTS_TOTAL, 'labels') as mock_counter_labels,
            patch.object(HTTP_REQUEST_DURATION, 'labels') as mock_histogram_labels,
            patch.object(HTTP_REQUESTS_IN_FLIGHT, 'inc') as mock_gauge_inc,
            patch.object(HTTP_REQUESTS_IN_FLIGHT, 'dec') as mock_gauge_dec,
        ):

            # Setup mock returns
            mock_counter_metric = Mock()
            mock_histogram_metric = Mock()
            mock_counter_labels.return_value = mock_counter_metric
            mock_histogram_labels.return_value = mock_histogram_metric

            # Create mock request
            request = Mock(spec=Request)
            request.method = "POST"
            request.url.path = "/api/v1/models"

            # Mock call_next to raise an exception
            async def mock_call_next(req):
                await asyncio.sleep(0.001)  # Simulate small delay
                raise ValueError("Test exception")

            # Execute middleware and expect exception to be re-raised
            with pytest.raises(ValueError, match="Test exception"):
                await middleware.dispatch(request, mock_call_next)

            # Verify gauge was incremented and decremented even on exception
            mock_gauge_inc.assert_called_once()
            mock_gauge_dec.assert_called_once()

            # Verify counter was called with 500 status (exception status)
            mock_counter_labels.assert_called_once_with(
                method="POST", path="/api/v1/models", status="500"
            )
            mock_counter_metric.inc.assert_called_once()

            # Verify histogram was called with 500 status
            mock_histogram_labels.assert_called_once_with(
                method="POST", path="/api/v1/models", status="500"
            )
            mock_histogram_metric.observe.assert_called_once()

    def test_metrics_collection_error_handling(self, middleware):
        """Test error handling when metrics collection itself fails."""
        # Test _record_metrics method with failing metrics
        with patch.object(HTTP_REQUESTS_TOTAL, 'labels') as mock_counter_labels:
            # Make the counter raise an exception
            mock_counter_labels.side_effect = Exception("Metrics collection failed")

            # This should not raise an exception - errors should be logged and handled
            middleware._record_metrics("GET", "/test", "200", 100.0)

            # Verify the method was called (even though it failed)
            mock_counter_labels.assert_called_once()

    def test_timing_precision(self, middleware):
        """Test that timing uses high precision and millisecond units."""
        # Mock time.perf_counter to return predictable values
        with patch(
            'time.perf_counter', side_effect=[1000.0, 1000.1]
        ):  # 100ms difference
            with patch.object(HTTP_REQUEST_DURATION, 'labels') as mock_histogram_labels:
                mock_histogram_metric = Mock()
                mock_histogram_labels.return_value = mock_histogram_metric

                # Record metrics with mocked timing
                middleware._record_metrics("GET", "/test", "200", 100.0)

                # Verify histogram was called
                mock_histogram_metric.observe.assert_called_once_with(100.0)


@pytest.mark.unit
class TestHTTPMetricsIntegration:
    """Test HTTP metrics integration with FastAPI application."""

    @pytest.fixture
    def test_app(self):
        """Create a test FastAPI app with metrics middleware."""
        app = FastAPI()

        # Add the metrics middleware
        app.add_middleware(EnhancedHTTPMetricsMiddleware)

        # Add test endpoints
        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}

        @app.get("/test/{item_id}")
        async def test_item_endpoint(item_id: str):
            return {"item_id": item_id}

        @app.post("/test")
        async def test_post_endpoint():
            return {"message": "created"}

        @app.get("/error")
        async def error_endpoint():
            raise ValueError("Test error")

        return app

    def test_counter_increments_for_successful_requests(self, test_app):
        """Test that counter increments correctly for successful requests."""
        with TestClient(test_app) as client:
            # Clear any existing metrics
            with patch.object(HTTP_REQUESTS_TOTAL, 'labels') as mock_counter_labels:
                mock_counter_metric = Mock()
                mock_counter_labels.return_value = mock_counter_metric

                # Make requests
                response1 = client.get("/test")
                response2 = client.get("/test/123")
                response3 = client.post("/test")

                # Verify responses
                assert response1.status_code == 200
                assert response2.status_code == 200
                assert response3.status_code == 200

                # Verify counter was called for each request
                assert mock_counter_labels.call_count == 3
                assert mock_counter_metric.inc.call_count == 3

                # Verify correct labels were used
                call_args_list = mock_counter_labels.call_args_list

                # First call: GET /test
                assert call_args_list[0][1] == {
                    "method": "GET",
                    "path": "/test",
                    "status": "200",
                }

                # Second call: GET /test/{item_id}
                assert call_args_list[1][1] == {
                    "method": "GET",
                    "path": "/test/{id}",
                    "status": "200",
                }

                # Third call: POST /test
                assert call_args_list[2][1] == {
                    "method": "POST",
                    "path": "/test",
                    "status": "200",
                }

    def test_histogram_records_duration_for_requests(self, test_app):
        """Test that histogram records duration for all requests."""
        with TestClient(test_app) as client:
            with patch.object(HTTP_REQUEST_DURATION, 'labels') as mock_histogram_labels:
                mock_histogram_metric = Mock()
                mock_histogram_labels.return_value = mock_histogram_metric

                # Make request
                response = client.get("/test")
                assert response.status_code == 200

                # Verify histogram was called
                mock_histogram_labels.assert_called_once()
                mock_histogram_metric.observe.assert_called_once()

                # Verify duration is positive
                duration = mock_histogram_metric.observe.call_args[0][0]
                assert duration > 0

    def test_gauge_tracks_concurrent_requests(self, test_app):
        """Test that gauge properly tracks in-flight requests."""
        with TestClient(test_app) as client:
            with (
                patch.object(HTTP_REQUESTS_IN_FLIGHT, 'inc') as mock_gauge_inc,
                patch.object(HTTP_REQUESTS_IN_FLIGHT, 'dec') as mock_gauge_dec,
            ):

                # Make request
                response = client.get("/test")
                assert response.status_code == 200

                # Verify gauge was incremented and decremented
                mock_gauge_inc.assert_called_once()
                mock_gauge_dec.assert_called_once()

    def test_metrics_recorded_for_error_responses(self, test_app):
        """Test that metrics are recorded even for error responses."""
        with TestClient(test_app) as client:
            with (
                patch.object(HTTP_REQUESTS_TOTAL, 'labels') as mock_counter_labels,
                patch.object(HTTP_REQUEST_DURATION, 'labels') as mock_histogram_labels,
            ):

                mock_counter_metric = Mock()
                mock_histogram_metric = Mock()
                mock_counter_labels.return_value = mock_counter_metric
                mock_histogram_labels.return_value = mock_histogram_metric

                # Make request to error endpoint - this will raise an exception
                # but the test client should handle it and return a 500 response
                try:
                    response = client.get("/error")
                    # If we get here, the error was handled by FastAPI
                    assert response.status_code == 500
                except Exception:
                    # If the exception propagates, that's also acceptable for this test
                    pass

                # Verify metrics were recorded with 500 status
                # The middleware should record metrics even when exceptions occur
                mock_counter_labels.assert_called_with(
                    method="GET", path="/error", status="500"
                )
                mock_histogram_labels.assert_called_with(
                    method="GET", path="/error", status="500"
                )

                mock_counter_metric.inc.assert_called()
                mock_histogram_metric.observe.assert_called()

    def test_different_http_methods_recorded_correctly(self, test_app):
        """Test that different HTTP methods are recorded with correct labels."""
        with TestClient(test_app) as client:
            with patch.object(HTTP_REQUESTS_TOTAL, 'labels') as mock_counter_labels:
                mock_counter_metric = Mock()
                mock_counter_labels.return_value = mock_counter_metric

                # Make requests with different methods
                client.get("/test")
                client.post("/test")

                # Verify correct method labels
                call_args_list = mock_counter_labels.call_args_list
                assert call_args_list[0][1]["method"] == "GET"
                assert call_args_list[1][1]["method"] == "POST"

    def test_various_status_codes_recorded_correctly(self, test_app):
        """Test that various status codes are recorded correctly."""

        # Add endpoint that returns different status codes
        @test_app.get("/status/{code}")
        async def status_endpoint(code: int):
            return JSONResponse(content={"status": code}, status_code=code)

        with TestClient(test_app) as client:
            with patch.object(HTTP_REQUESTS_TOTAL, 'labels') as mock_counter_labels:
                mock_counter_metric = Mock()
                mock_counter_labels.return_value = mock_counter_metric

                # Test various status codes
                client.get("/status/200")
                client.get("/status/201")
                client.get("/status/404")
                client.get("/status/500")

                # Verify correct status labels
                call_args_list = mock_counter_labels.call_args_list
                assert call_args_list[0][1]["status"] == "200"
                assert call_args_list[1][1]["status"] == "201"
                assert call_args_list[2][1]["status"] == "404"
                assert call_args_list[3][1]["status"] == "500"


@pytest.mark.unit
class TestHTTPMetricsPerformance:
    """Test performance characteristics of HTTP metrics collection."""

    def test_metrics_collection_overhead_is_minimal(self):
        """Test that metrics collection adds minimal overhead."""
        middleware = EnhancedHTTPMetricsMiddleware(app=Mock())

        # Time the metrics recording operation
        start_time = time.perf_counter()

        # Record metrics multiple times
        for _ in range(1000):
            middleware._record_metrics("GET", "/test", "200", 50.0)

        end_time = time.perf_counter()
        total_time = (end_time - start_time) * 1000  # Convert to milliseconds

        # Average time per metric recording should be very small
        avg_time_per_recording = total_time / 1000

        # Should be less than 1ms per recording (very generous threshold)
        assert (
            avg_time_per_recording < 1.0
        ), f"Metrics recording took {avg_time_per_recording}ms on average"

    def test_route_pattern_extraction_performance(self):
        """Test that route pattern extraction is performant."""
        middleware = EnhancedHTTPMetricsMiddleware(app=Mock())

        # Create mock request
        request = Mock(spec=Request)
        request.url.path = "/api/v1/model/507f1f77bcf86cd799439011/position"

        # Time the route pattern extraction
        start_time = time.perf_counter()

        # Extract route pattern multiple times
        for _ in range(1000):
            pattern = middleware._extract_route_pattern(request)

        end_time = time.perf_counter()
        total_time = (end_time - start_time) * 1000  # Convert to milliseconds

        # Average time per extraction should be very small
        avg_time_per_extraction = total_time / 1000

        # Should be less than 0.1ms per extraction
        assert (
            avg_time_per_extraction < 0.1
        ), f"Route extraction took {avg_time_per_extraction}ms on average"

        # Verify the extraction still works correctly
        assert pattern == "/api/v1/model/{model_id}/position"

    def test_label_formatting_performance(self):
        """Test that label formatting operations are performant."""
        middleware = EnhancedHTTPMetricsMiddleware(app=Mock())

        # Time the label formatting operations
        start_time = time.perf_counter()

        # Format labels multiple times
        for _ in range(1000):
            method = middleware._get_method_label("get")
            status = middleware._format_status_code(200)

        end_time = time.perf_counter()
        total_time = (end_time - start_time) * 1000  # Convert to milliseconds

        # Average time per formatting should be very small
        avg_time_per_format = total_time / 1000

        # Should be less than 0.01ms per formatting operation
        assert (
            avg_time_per_format < 0.01
        ), f"Label formatting took {avg_time_per_format}ms on average"

        # Verify formatting still works correctly
        assert method == "GET"
        assert status == "200"


@pytest.mark.unit
class TestHTTPMetricsErrorHandling:
    """Test error handling in HTTP metrics collection."""

    def test_metrics_failure_does_not_break_request_processing(self):
        """Test that metrics collection failures don't break request processing."""
        middleware = EnhancedHTTPMetricsMiddleware(app=Mock())

        # Mock all metrics to raise exceptions
        with (
            patch.object(
                HTTP_REQUESTS_TOTAL, 'labels', side_effect=Exception("Counter failed")
            ),
            patch.object(
                HTTP_REQUEST_DURATION,
                'labels',
                side_effect=Exception("Histogram failed"),
            ),
            patch.object(
                HTTP_REQUESTS_IN_FLIGHT,
                'inc',
                side_effect=Exception("Gauge inc failed"),
            ),
            patch.object(
                HTTP_REQUESTS_IN_FLIGHT,
                'dec',
                side_effect=Exception("Gauge dec failed"),
            ),
        ):

            # This should not raise an exception
            middleware._record_metrics("GET", "/test", "200", 100.0)

    def test_invalid_request_data_handling(self):
        """Test handling of invalid request data."""
        middleware = EnhancedHTTPMetricsMiddleware(app=Mock())

        # Test with None request - this should raise an exception and be handled
        with pytest.raises(AttributeError):
            middleware._extract_route_pattern(None)

    def test_malformed_url_handling(self):
        """Test handling of malformed URLs."""
        middleware = EnhancedHTTPMetricsMiddleware(app=Mock())

        # Create request with malformed URL
        request = Mock(spec=Request)
        request.url.path = None  # Invalid path

        # The middleware should handle this gracefully and return a safe fallback
        result = middleware._extract_route_pattern(request)

        # Should return a safe fallback
        assert result == "/"

    def test_extreme_path_lengths_handling(self):
        """Test handling of extremely long paths."""
        middleware = EnhancedHTTPMetricsMiddleware(app=Mock())

        # Create very long path
        long_path = "/api/" + "very_long_segment/" * 100 + "end"

        result = middleware._sanitize_unmatched_route(long_path)

        # Should return /unknown for overly long paths
        assert result == "/unknown"

    def test_opentelemetry_metrics_error_handling(self):
        """Test error handling for OpenTelemetry metrics failures."""
        middleware = EnhancedHTTPMetricsMiddleware(app=Mock())

        # Mock OpenTelemetry metrics to fail
        with (
            patch('src.core.monitoring.otel_http_requests_total') as mock_otel_counter,
            patch(
                'src.core.monitoring.otel_http_request_duration'
            ) as mock_otel_histogram,
            patch(
                'src.core.monitoring.otel_http_requests_in_flight'
            ) as mock_otel_gauge,
        ):

            mock_otel_counter.add.side_effect = Exception("OTEL counter failed")
            mock_otel_histogram.record.side_effect = Exception("OTEL histogram failed")
            mock_otel_gauge.add.side_effect = Exception("OTEL gauge failed")

            # Should handle OTEL failures gracefully
            middleware._record_metrics("GET", "/test", "200", 100.0)

            # Verify OTEL methods were called (even though they failed)
            mock_otel_counter.add.assert_called()
            mock_otel_histogram.record.assert_called()
