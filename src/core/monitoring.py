"""
Monitoring and observability module for the Order Generation Service.

This module provides comprehensive monitoring capabilities including:
- Prometheus metrics collection
- Performance monitoring
- Health check instrumentation
- Request/response tracking
- Error monitoring
"""

import time
from typing import Any, Callable, Dict

from fastapi import Request, Response

# OpenTelemetry metrics imports
from opentelemetry import metrics as otel_metrics
from opentelemetry.metrics import get_meter
from prometheus_client import Counter, Gauge, Histogram, generate_latest
from prometheus_fastapi_instrumentator import Instrumentator, metrics
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.utils import get_logger

logger = get_logger(__name__)

# Get OpenTelemetry meter for creating metrics
meter = get_meter(__name__)

# OpenTelemetry HTTP metrics (sent to OTEL Collector)
otel_http_requests_total = meter.create_counter(
    name="http_requests_total", description="Total number of HTTP requests", unit="1"
)

otel_http_request_duration = meter.create_histogram(
    name="http_request_duration",
    description="HTTP request duration in milliseconds",
    unit="ms",
)

otel_http_requests_in_flight = meter.create_up_down_counter(
    name="http_requests_in_flight",
    description="Number of HTTP requests currently being processed",
    unit="1",
)

# Global metrics registry to prevent duplicate registration
_METRICS_REGISTRY = {}


def _get_or_create_metric(
    metric_class, name, description, labels=None, registry_key=None, **kwargs
):
    """Get or create a metric, preventing duplicate registration."""
    if registry_key is None:
        registry_key = name

    # Check if metric already exists in our registry
    if registry_key in _METRICS_REGISTRY:
        logger.debug(f"Reusing existing metric: {name}")
        return _METRICS_REGISTRY[registry_key]

    try:
        if labels:
            metric = metric_class(name, description, labels, **kwargs)
        else:
            metric = metric_class(name, description, **kwargs)

        _METRICS_REGISTRY[registry_key] = metric
        logger.debug(f"Created new metric: {name}")
        return metric

    except ValueError as e:
        if "Duplicated timeseries" in str(e):
            logger.warning(
                f"Metric {name} already registered in Prometheus, but not in our registry. This indicates a module reload issue."
            )

            # Create a dummy metric that won't interfere
            class DummyMetric:
                def labels(self, **kwargs):
                    return self

                def inc(self, amount=1):
                    pass

                def observe(self, amount):
                    pass

                def set(self, value):
                    pass

                def collect(self):
                    return []

            dummy = DummyMetric()
            _METRICS_REGISTRY[registry_key] = dummy
            logger.warning(f"Created dummy metric for {name} to prevent errors")
            return dummy
        else:
            logger.error(f"Failed to create metric {name}: {e}")
            raise


# Keep Prometheus metrics for backward compatibility (exposed via /metrics endpoint)
HTTP_REQUESTS_TOTAL = _get_or_create_metric(
    Counter,
    'http_requests_total',
    'Total number of HTTP requests',
    ['method', 'path', 'status'],
)

HTTP_REQUEST_DURATION = _get_or_create_metric(
    Histogram,
    'http_request_duration',
    'HTTP request duration in milliseconds',
    ['method', 'path', 'status'],
    buckets=[5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000],
)

HTTP_REQUESTS_IN_FLIGHT = _get_or_create_metric(
    Gauge,
    'http_requests_in_flight',
    'Number of HTTP requests currently being processed',
)

OPTIMIZATION_DURATION = _get_or_create_metric(
    Histogram,
    'optimization_duration_seconds',
    'Portfolio optimization duration in seconds',
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
)

OPTIMIZATION_COUNT = _get_or_create_metric(
    Counter, 'optimizations_total', 'Total number of optimization requests', ['status']
)

DATABASE_OPERATION_DURATION = _get_or_create_metric(
    Histogram,
    'database_operation_duration_seconds',
    'Database operation duration in seconds',
    ['operation', 'collection'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

DATABASE_OPERATION_COUNT = _get_or_create_metric(
    Counter,
    'database_operations_total',
    'Total number of database operations',
    ['operation', 'collection', 'status'],
)

EXTERNAL_SERVICE_DURATION = _get_or_create_metric(
    Histogram,
    'external_service_duration_seconds',
    'External service call duration in seconds',
    ['service', 'endpoint'],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)

EXTERNAL_SERVICE_COUNT = _get_or_create_metric(
    Counter,
    'external_service_requests_total',
    'Total number of external service requests',
    ['service', 'endpoint', 'status'],
)

ERROR_COUNT = _get_or_create_metric(
    Counter, 'errors_total', 'Total number of errors', ['error_type', 'endpoint']
)

MEMORY_USAGE = _get_or_create_metric(
    Gauge, 'memory_usage_bytes', 'Current memory usage in bytes'
)

CPU_USAGE = _get_or_create_metric(
    Gauge, 'cpu_usage_percent', 'Current CPU usage percentage'
)


class EnhancedHTTPMetricsMiddleware(BaseHTTPMiddleware):
    """
    Enhanced middleware to collect standardized HTTP request metrics.

    This middleware implements the standardized HTTP metrics with proper timing,
    in-flight tracking, and comprehensive error handling as specified in the
    HTTP metrics implementation requirements.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and collect all three standardized HTTP metrics.

        Args:
            request: The incoming request
            call_next: The next middleware/endpoint to call

        Returns:
            Response with metrics recorded
        """
        # Start high-precision timing using perf_counter for millisecond precision
        start_time = time.perf_counter()

        # Increment in-flight requests gauge (both OTEL and Prometheus)
        in_flight_incremented = False
        try:
            HTTP_REQUESTS_IN_FLIGHT.inc()
            in_flight_incremented = True
            logger.debug("Successfully incremented Prometheus in-flight requests gauge")
        except Exception as e:
            logger.error(
                "Failed to increment Prometheus in-flight requests gauge",
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )

        try:
            otel_http_requests_in_flight.add(1)
            logger.debug(
                "Successfully incremented OpenTelemetry in-flight requests gauge"
            )
        except Exception as e:
            logger.error(
                "Failed to increment OpenTelemetry in-flight requests gauge",
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration in milliseconds with high precision
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Extract labels for metrics
            method = self._get_method_label(request.method)
            path = self._extract_route_pattern(request)
            status = self._format_status_code(response.status_code)

            # Record all three metrics with proper error handling
            self._record_metrics(method, path, status, duration_ms)

            # Log slow requests (> 1000ms)
            if duration_ms > 1000:
                logger.warning(
                    "Slow request detected",
                    method=method,
                    path=path,
                    duration_ms=duration_ms,
                    status=status,
                )

            return response

        except Exception as e:
            # Calculate duration even for exceptions
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Extract labels for error metrics
            method = self._get_method_label(request.method)
            path = self._extract_route_pattern(request)
            status = "500"  # All exceptions result in 500 status for metrics

            # Record metrics even when exceptions occur
            self._record_metrics(method, path, status, duration_ms)

            # Record additional error metrics with proper error handling
            try:
                ERROR_COUNT.labels(error_type=type(e).__name__, endpoint=path).inc()
                logger.debug(
                    "Successfully recorded error metrics",
                    error_type=type(e).__name__,
                    endpoint=path,
                )
            except Exception as metric_error:
                logger.error(
                    "Failed to record error metrics",
                    error=str(metric_error),
                    error_type=type(metric_error).__name__,
                    original_error=str(e),
                    original_error_type=type(e).__name__,
                    endpoint=path,
                    exc_info=True,
                )

            logger.error(
                "Request processing error - metrics collection attempted",
                error=str(e),
                error_type=type(e).__name__,
                method=method,
                path=path,
                duration_ms=duration_ms,
                exc_info=True,
            )

            raise
        finally:
            # Always decrement in-flight requests gauge (both OTEL and Prometheus)
            # Only decrement if we successfully incremented to avoid negative values
            if in_flight_incremented:
                try:
                    HTTP_REQUESTS_IN_FLIGHT.dec()
                    logger.debug(
                        "Successfully decremented Prometheus in-flight requests gauge"
                    )
                except Exception as e:
                    logger.error(
                        "Failed to decrement Prometheus in-flight requests gauge",
                        error=str(e),
                        error_type=type(e).__name__,
                        exc_info=True,
                    )

            try:
                otel_http_requests_in_flight.add(-1)
                logger.debug(
                    "Successfully decremented OpenTelemetry in-flight requests gauge"
                )
            except Exception as e:
                logger.error(
                    "Failed to decrement OpenTelemetry in-flight requests gauge",
                    error=str(e),
                    error_type=type(e).__name__,
                    exc_info=True,
                )

    def _record_metrics(
        self, method: str, path: str, status: str, duration_ms: float
    ) -> None:
        """
        Record all three HTTP metrics with comprehensive error handling.
        Records to both OpenTelemetry (sent to OTEL Collector) and Prometheus (exposed via /metrics).

        Args:
            method: HTTP method (uppercase)
            path: Route pattern
            status: Status code as string
            duration_ms: Request duration in milliseconds
        """
        # Prepare attributes for OpenTelemetry metrics
        attributes = {"method": method, "path": path, "status": status}

        # Debug logging for metric values during development
        logger.debug(
            "Recording HTTP metrics",
            method=method,
            path=path,
            status=status,
            duration_ms=duration_ms,
            attributes=attributes,
        )

        # Record counter metrics with individual error handling
        try:
            HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status=status).inc()
            logger.debug(
                "Successfully recorded Prometheus HTTP requests total counter",
                method=method,
                path=path,
                status=status,
            )
        except Exception as e:
            logger.error(
                "Failed to record Prometheus HTTP requests total counter",
                error=str(e),
                error_type=type(e).__name__,
                method=method,
                path=path,
                status=status,
                exc_info=True,
            )

        try:
            otel_http_requests_total.add(1, attributes)
            logger.debug(
                "Successfully recorded OpenTelemetry HTTP requests total counter",
                attributes=attributes,
            )
        except Exception as e:
            logger.error(
                "Failed to record OpenTelemetry HTTP requests total counter",
                error=str(e),
                error_type=type(e).__name__,
                attributes=attributes,
                exc_info=True,
            )

        # Record histogram metrics with individual error handling
        try:
            HTTP_REQUEST_DURATION.labels(
                method=method, path=path, status=status
            ).observe(duration_ms)
            logger.debug(
                "Successfully recorded Prometheus HTTP request duration histogram",
                method=method,
                path=path,
                status=status,
                duration_ms=duration_ms,
            )
        except Exception as e:
            logger.error(
                "Failed to record Prometheus HTTP request duration histogram",
                error=str(e),
                error_type=type(e).__name__,
                method=method,
                path=path,
                status=status,
                duration_ms=duration_ms,
                exc_info=True,
            )

        try:
            otel_http_request_duration.record(duration_ms, attributes)
            logger.debug(
                "Successfully recorded OpenTelemetry HTTP request duration histogram",
                attributes=attributes,
                duration_ms=duration_ms,
            )
        except Exception as e:
            logger.error(
                "Failed to record OpenTelemetry HTTP request duration histogram",
                error=str(e),
                error_type=type(e).__name__,
                attributes=attributes,
                duration_ms=duration_ms,
                exc_info=True,
            )

    def _extract_route_pattern(self, request: Request) -> str:
        """
        Extract route pattern from request URL to prevent high cardinality metrics.

        Converts URLs with parameters to route patterns (e.g., /api/v1/models/123 -> /api/v1/models/{model_id})
        Handles FastAPI parameterized routes and sanitizes sensitive data from paths.

        Args:
            request: The HTTP request

        Returns:
            Route pattern string with parameters replaced by placeholders
        """
        try:
            path = request.url.path.rstrip(
                '/'
            )  # Remove trailing slash for consistent matching

            # Handle empty path
            if not path:
                return "/"

            # Sanitize sensitive data from paths (remove query parameters and fragments)
            path = self._sanitize_path(path)

            # Handle API v1 models endpoints
            if path.startswith("/api/v1/models"):
                return self._extract_models_route_pattern(path)

            # Handle API v1 model endpoints (singular)
            if path.startswith("/api/v1/model"):
                return self._extract_model_route_pattern(path)

            # Handle API v1 rebalance endpoints (plural - from rebalances.py)
            if path.startswith("/api/v1/rebalances"):
                return self._extract_rebalances_route_pattern(path)

            # Handle API v1 portfolio endpoints
            if path.startswith("/api/v1/portfolio"):
                return self._extract_portfolio_route_pattern(path)

            # Handle API v1 rebalance endpoints (singular - from rebalance.py)
            if path.startswith("/api/v1/rebalance"):
                return self._extract_rebalance_route_pattern(path)

            # Handle health check endpoints
            if path.startswith("/health"):
                return self._extract_health_route_pattern(path)

            # Handle docs endpoints
            if (
                path.startswith("/docs")
                or path.startswith("/redoc")
                or path.startswith("/openapi.json")
            ):
                return path

            # Handle metrics endpoint
            if path == "/metrics":
                return "/metrics"

            # Handle root endpoint
            if path == "/":
                return "/"

            # Fallback for unmatched routes - sanitize but preserve structure
            return self._sanitize_unmatched_route(path)

        except Exception as e:
            logger.error(
                "Failed to extract route pattern",
                error=str(e),
                error_type=type(e).__name__,
                path=getattr(request.url, 'path', 'unknown'),
                request_method=getattr(request, 'method', 'unknown'),
                exc_info=True,
            )
            # Return sanitized path as fallback, with additional error handling
            try:
                return self._sanitize_path(request.url.path)
            except Exception as sanitize_error:
                logger.error(
                    "Failed to sanitize path as fallback",
                    error=str(sanitize_error),
                    error_type=type(sanitize_error).__name__,
                    original_error=str(e),
                    exc_info=True,
                )
                return "/unknown"

    def _sanitize_path(self, path: str) -> str:
        """
        Sanitize sensitive data from paths.

        Args:
            path: Original path string

        Returns:
            Sanitized path string
        """
        try:
            # Remove query parameters and fragments
            if '?' in path:
                path = path.split('?')[0]
            if '#' in path:
                path = path.split('#')[0]

            # Remove trailing slash for consistency
            path = path.rstrip('/')

            # Handle empty path after sanitization
            if not path:
                return "/"

            return path
        except Exception as e:
            logger.error(
                "Failed to sanitize path",
                error=str(e),
                error_type=type(e).__name__,
                path=path,
                exc_info=True,
            )
            return "/"

    def _extract_models_route_pattern(self, path: str) -> str:
        """Extract route pattern for /api/v1/models endpoints."""
        if path == "/api/v1/models":
            return "/api/v1/models"

        # This shouldn't happen based on current routes, but handle gracefully
        parts = path.split("/")
        if len(parts) > 4:
            # Unexpected sub-path under models
            return "/api/v1/models/{unknown}"

        return "/api/v1/models"

    def _extract_model_route_pattern(self, path: str) -> str:
        """Extract route pattern for /api/v1/model endpoints (singular)."""
        parts = path.split("/")

        if len(parts) < 5:
            # /api/v1/model (shouldn't exist but handle gracefully)
            return "/api/v1/model"

        # /api/v1/model/{model_id}
        if len(parts) == 5:
            return "/api/v1/model/{model_id}"

        # /api/v1/model/{model_id}/position
        if len(parts) == 6 and parts[5] == "position":
            return "/api/v1/model/{model_id}/position"

        # /api/v1/model/{model_id}/portfolio
        if len(parts) == 6 and parts[5] == "portfolio":
            return "/api/v1/model/{model_id}/portfolio"

        # Fallback for unexpected sub-resources
        if len(parts) > 6:
            return f"/api/v1/model/{{model_id}}/{'/'.join(parts[5:])}"

        return f"/api/v1/model/{{model_id}}/{parts[5]}"

    def _extract_rebalances_route_pattern(self, path: str) -> str:
        """Extract route pattern for /api/v1/rebalances endpoints (plural)."""
        parts = path.split("/")

        if len(parts) == 4:  # /api/v1/rebalances
            return "/api/v1/rebalances"

        # /api/v1/rebalances/portfolios (POST endpoint)
        if len(parts) == 5 and parts[4] == "portfolios":
            return "/api/v1/rebalances/portfolios"

        # Fallback for other rebalances sub-paths
        return f"/api/v1/rebalances/{'/'.join(parts[4:])}"

    def _extract_portfolio_route_pattern(self, path: str) -> str:
        """Extract route pattern for /api/v1/portfolio endpoints."""
        parts = path.split("/")

        if len(parts) < 5:
            return "/api/v1/portfolio"

        # /api/v1/portfolio/{portfolio_id}/rebalance
        if len(parts) == 6 and parts[5] == "rebalance":
            return "/api/v1/portfolio/{portfolio_id}/rebalance"

        # /api/v1/portfolio/{portfolio_id}
        if len(parts) == 5:
            return "/api/v1/portfolio/{portfolio_id}"

        # Fallback for other portfolio sub-paths
        return f"/api/v1/portfolio/{{portfolio_id}}/{'/'.join(parts[5:])}"

    def _extract_rebalance_route_pattern(self, path: str) -> str:
        """Extract route pattern for /api/v1/rebalance endpoints (singular)."""
        parts = path.split("/")

        if len(parts) == 4:  # /api/v1/rebalance
            return "/api/v1/rebalance"

        # /api/v1/rebalance/{rebalance_id}
        if len(parts) == 5:
            return "/api/v1/rebalance/{rebalance_id}"

        # /api/v1/rebalance/{rebalance_id}/portfolios
        if len(parts) == 6 and parts[5] == "portfolios":
            return "/api/v1/rebalance/{rebalance_id}/portfolios"

        # /api/v1/rebalance/{rebalance_id}/portfolio/{portfolio_id}/positions
        if len(parts) == 8 and parts[5] == "portfolio" and parts[7] == "positions":
            return "/api/v1/rebalance/{rebalance_id}/portfolio/{portfolio_id}/positions"

        # Fallback for other rebalance sub-paths
        return f"/api/v1/rebalance/{'/'.join(parts[4:])}"

    def _extract_health_route_pattern(self, path: str) -> str:
        """Extract route pattern for /health endpoints."""
        parts = path.split("/")

        if len(parts) == 2:  # /health
            return "/health"

        # /health/{check_type} (e.g., /health/live, /health/ready)
        if len(parts) == 3:
            return "/health/{check_type}"

        # Fallback for deeper health paths
        return f"/health/{'/'.join(parts[2:])}"

    def _sanitize_unmatched_route(self, path: str) -> str:
        """
        Sanitize unmatched routes to prevent high cardinality while preserving structure.

        Args:
            path: The unmatched path

        Returns:
            Sanitized route pattern
        """
        try:
            parts = path.split("/")
            sanitized_parts = []

            for i, part in enumerate(parts):
                if not part:  # Empty part (leading slash)
                    sanitized_parts.append(part)
                    continue

                # Check if part looks like an ID (24 char hex, UUID, or numeric)
                if self._looks_like_id(part):
                    sanitized_parts.append("{id}")
                else:
                    # Keep the original part but limit length to prevent abuse
                    sanitized_part = part[:50] if len(part) > 50 else part
                    sanitized_parts.append(sanitized_part)

            result = "/".join(sanitized_parts)

            # Ensure we don't create overly long patterns
            if len(result) > 200:
                return "/unknown"

            return result

        except Exception as e:
            logger.error(
                "Failed to sanitize unmatched route",
                error=str(e),
                error_type=type(e).__name__,
                path=path,
                exc_info=True,
            )
            return "/unknown"

    def _looks_like_id(self, part: str) -> bool:
        """
        Check if a path part looks like an ID that should be parameterized.

        Args:
            part: Path part to check

        Returns:
            True if the part looks like an ID
        """
        try:
            # MongoDB ObjectId (24 character hex)
            if len(part) == 24 and all(c in '0123456789abcdefABCDEF' for c in part):
                return True

            # UUID format (with or without hyphens)
            if len(part) == 36 and part.count('-') == 4:
                return True
            if len(part) == 32 and all(c in '0123456789abcdefABCDEF' for c in part):
                return True

            # Numeric ID (including shorter ones like "123")
            if part.isdigit() and len(part) >= 1:
                return True

            # Alphanumeric ID that looks like an identifier
            if len(part) > 8 and part.replace('-', '').replace('_', '').isalnum():
                return True

            return False

        except Exception:
            return False

    def _format_status_code(self, status_code: int) -> str:
        """
        Format HTTP status code as string for consistent labeling.

        Converts numeric HTTP status codes to strings as required by the metrics specification.

        Args:
            status_code: Numeric HTTP status code

        Returns:
            Status code as string (e.g., "200", "404", "500")
        """
        try:
            # Ensure we have a valid status code
            if not isinstance(status_code, int):
                logger.warning(
                    "Invalid status code type",
                    status_code=status_code,
                    status_code_type=type(status_code).__name__,
                )
                return "unknown"

            # Validate status code range (100-599 are valid HTTP status codes)
            if status_code < 100 or status_code > 599:
                logger.warning(
                    "Status code out of valid range", status_code=status_code
                )
                return "unknown"

            return str(status_code)

        except Exception as e:
            logger.error(
                "Failed to format status code",
                error=str(e),
                status_code=status_code,
                exc_info=True,
            )
            return "unknown"

    def _get_method_label(self, method: str) -> str:
        """
        Get uppercase HTTP method name for consistent labeling.

        Converts HTTP method to uppercase as required by the metrics specification.

        Args:
            method: HTTP method string

        Returns:
            Uppercase HTTP method string (e.g., "GET", "POST", "PUT", "DELETE")
        """
        try:
            # Ensure we have a valid method string
            if not isinstance(method, str):
                logger.warning(
                    "Invalid method type",
                    method=method,
                    method_type=type(method).__name__,
                )
                return "UNKNOWN"

            # Strip whitespace and convert to uppercase
            method_upper = method.strip().upper()

            # Validate that it's a known HTTP method
            valid_methods = {
                "GET",
                "POST",
                "PUT",
                "DELETE",
                "PATCH",
                "HEAD",
                "OPTIONS",
                "TRACE",
                "CONNECT",
            }

            if method_upper not in valid_methods:
                logger.warning(
                    "Unknown HTTP method", method=method, method_upper=method_upper
                )
                # Still return the uppercase version for consistency
                return method_upper if method_upper else "UNKNOWN"

            return method_upper

        except Exception as e:
            logger.error(
                "Failed to format method label",
                error=str(e),
                error_type=type(e).__name__,
                method=method,
                exc_info=True,
            )
            return "UNKNOWN"

    def _handle_metrics_collection_failure(
        self, operation: str, error: Exception, **context
    ) -> None:
        """
        Handle metrics collection failures with structured logging.

        This method provides centralized error handling for metrics collection failures,
        ensuring that request processing continues even when metrics collection fails.

        Args:
            operation: The metrics operation that failed (e.g., "record_counter", "record_histogram")
            error: The exception that occurred
            **context: Additional context information for logging
        """
        try:
            logger.error(
                f"Metrics collection failure: {operation}",
                error=str(error),
                error_type=type(error).__name__,
                operation=operation,
                **context,
                exc_info=True,
            )

            # Optionally, record a metric about metrics collection failures
            # This helps monitor the health of the metrics system itself
            try:
                ERROR_COUNT.labels(
                    error_type="metrics_collection_failure", endpoint="internal"
                ).inc()
            except Exception as meta_error:
                # If we can't even record the metrics failure metric, just log it
                logger.critical(
                    "Failed to record metrics collection failure metric",
                    error=str(meta_error),
                    error_type=type(meta_error).__name__,
                    original_operation=operation,
                    original_error=str(error),
                    exc_info=True,
                )

        except Exception as logging_error:
            # Last resort: if even logging fails, try to print to stderr
            try:
                import sys

                print(
                    f"CRITICAL: Failed to handle metrics collection failure: {logging_error}",
                    file=sys.stderr,
                )
                print(
                    f"Original metrics operation: {operation}, error: {error}",
                    file=sys.stderr,
                )
            except Exception:
                # If even stderr printing fails, there's nothing more we can do
                pass


# Keep the original MetricsMiddleware for backward compatibility during transition
class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Legacy middleware to collect HTTP request metrics.

    This class is kept for backward compatibility. Use EnhancedHTTPMetricsMiddleware instead.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and collect metrics.

        Args:
            request: The incoming request
            call_next: The next middleware/endpoint to call

        Returns:
            Response with metrics recorded
        """
        start_time = time.perf_counter()

        # Increment in-flight requests with error handling
        in_flight_incremented = False
        try:
            HTTP_REQUESTS_IN_FLIGHT.inc()
            in_flight_incremented = True
            logger.debug(
                "Successfully incremented in-flight requests gauge (legacy middleware)"
            )
        except Exception as e:
            logger.error(
                "Failed to increment in-flight requests gauge (legacy middleware)",
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )

        try:
            # Process request
            response = await call_next(request)

            # Record metrics
            duration_ms = (
                time.perf_counter() - start_time
            ) * 1000  # Convert to milliseconds
            method = request.method.upper()  # Ensure uppercase method
            path = self._get_endpoint_label(request)
            status = str(response.status_code)

            # Record metrics with error handling
            try:
                HTTP_REQUESTS_TOTAL.labels(
                    method=method, path=path, status=status
                ).inc()
                logger.debug(
                    "Successfully recorded HTTP requests total (legacy middleware)",
                    method=method,
                    path=path,
                    status=status,
                )
            except Exception as e:
                logger.error(
                    "Failed to record HTTP requests total (legacy middleware)",
                    error=str(e),
                    error_type=type(e).__name__,
                    method=method,
                    path=path,
                    status=status,
                    exc_info=True,
                )

            try:
                HTTP_REQUEST_DURATION.labels(
                    method=method, path=path, status=status
                ).observe(duration_ms)
                logger.debug(
                    "Successfully recorded HTTP request duration (legacy middleware)",
                    method=method,
                    path=path,
                    status=status,
                    duration_ms=duration_ms,
                )
            except Exception as e:
                logger.error(
                    "Failed to record HTTP request duration (legacy middleware)",
                    error=str(e),
                    error_type=type(e).__name__,
                    method=method,
                    path=path,
                    status=status,
                    duration_ms=duration_ms,
                    exc_info=True,
                )

            # Log slow requests (> 1000ms)
            if duration_ms > 1000:
                logger.warning(
                    "Slow request detected",
                    method=method,
                    path=path,
                    duration_ms=duration_ms,
                    status=status,
                )

            return response

        except Exception as e:
            # Record error metrics with 500 status for exceptions
            duration_ms = (time.perf_counter() - start_time) * 1000
            method = request.method.upper()
            path = self._get_endpoint_label(request)
            status = "500"

            # Record metrics with error handling
            try:
                HTTP_REQUESTS_TOTAL.labels(
                    method=method, path=path, status=status
                ).inc()
                logger.debug(
                    "Successfully recorded HTTP requests total for error (legacy middleware)",
                    method=method,
                    path=path,
                    status=status,
                )
            except Exception as metric_error:
                logger.error(
                    "Failed to record HTTP requests total for error (legacy middleware)",
                    error=str(metric_error),
                    error_type=type(metric_error).__name__,
                    method=method,
                    path=path,
                    status=status,
                    original_error=str(e),
                    exc_info=True,
                )

            try:
                HTTP_REQUEST_DURATION.labels(
                    method=method, path=path, status=status
                ).observe(duration_ms)
                logger.debug(
                    "Successfully recorded HTTP request duration for error (legacy middleware)",
                    method=method,
                    path=path,
                    status=status,
                    duration_ms=duration_ms,
                )
            except Exception as metric_error:
                logger.error(
                    "Failed to record HTTP request duration for error (legacy middleware)",
                    error=str(metric_error),
                    error_type=type(metric_error).__name__,
                    method=method,
                    path=path,
                    status=status,
                    duration_ms=duration_ms,
                    original_error=str(e),
                    exc_info=True,
                )

            # Record error metrics with error handling
            try:
                ERROR_COUNT.labels(error_type=type(e).__name__, endpoint=path).inc()
                logger.debug(
                    "Successfully recorded error count (legacy middleware)",
                    error_type=type(e).__name__,
                    endpoint=path,
                )
            except Exception as metric_error:
                logger.error(
                    "Failed to record error count (legacy middleware)",
                    error=str(metric_error),
                    error_type=type(metric_error).__name__,
                    original_error=str(e),
                    original_error_type=type(e).__name__,
                    endpoint=path,
                    exc_info=True,
                )

            logger.error(
                "Request processing error - metrics collection attempted (legacy middleware)",
                error=str(e),
                error_type=type(e).__name__,
                method=method,
                path=path,
                duration_ms=duration_ms,
                exc_info=True,
            )

            raise
        finally:
            # Decrement in-flight requests with error handling
            # Only decrement if we successfully incremented to avoid negative values
            if in_flight_incremented:
                try:
                    HTTP_REQUESTS_IN_FLIGHT.dec()
                    logger.debug(
                        "Successfully decremented in-flight requests gauge (legacy middleware)"
                    )
                except Exception as e:
                    logger.error(
                        "Failed to decrement in-flight requests gauge (legacy middleware)",
                        error=str(e),
                        error_type=type(e).__name__,
                        exc_info=True,
                    )

    def _get_endpoint_label(self, request: Request) -> str:
        """
        Get a clean endpoint label for metrics.

        Args:
            request: The HTTP request

        Returns:
            Clean endpoint label
        """
        path = request.url.path

        # Replace dynamic path parameters with placeholders
        # This prevents high cardinality metrics
        if path.startswith("/api/v1/models/"):
            if path.count("/") > 3:  # /api/v1/models/{id}/something
                parts = path.split("/")
                if len(parts) >= 5:
                    return f"/api/v1/models/{{id}}/{'/'.join(parts[5:])}"
                return "/api/v1/models/{id}"
            return "/api/v1/models"

        if path.startswith("/api/v1/rebalance/"):
            return "/api/v1/rebalance/{portfolio_id}"

        return path


class PerformanceMonitor:
    """
    Performance monitoring utilities.
    """

    @staticmethod
    def track_optimization(func: Callable) -> Callable:
        """
        Decorator to track optimization performance.

        Args:
            func: Function to track

        Returns:
            Decorated function
        """

        def wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"

            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                logger.error(
                    "Optimization failed",
                    error=str(e),
                    error_type=type(e).__name__,
                    exc_info=True,
                )
                raise
            finally:
                duration = time.time() - start_time

                # Record metrics with error handling
                try:
                    OPTIMIZATION_DURATION.observe(duration)
                    logger.debug(
                        "Successfully recorded optimization duration",
                        duration=duration,
                        status=status,
                    )
                except Exception as metric_error:
                    logger.error(
                        "Failed to record optimization duration metric",
                        error=str(metric_error),
                        error_type=type(metric_error).__name__,
                        duration=duration,
                        status=status,
                        exc_info=True,
                    )

                try:
                    OPTIMIZATION_COUNT.labels(status=status).inc()
                    logger.debug(
                        "Successfully recorded optimization count",
                        status=status,
                    )
                except Exception as metric_error:
                    logger.error(
                        "Failed to record optimization count metric",
                        error=str(metric_error),
                        error_type=type(metric_error).__name__,
                        status=status,
                        exc_info=True,
                    )

                logger.info(
                    "Optimization completed - metrics collection attempted",
                    duration=duration,
                    status=status,
                )

        return wrapper

    @staticmethod
    def track_database_operation(operation: str, collection: str):
        """
        Context manager to track database operations.

        Args:
            operation: Type of database operation (create, read, update, delete)
            collection: Database collection name

        Returns:
            Context manager
        """

        class DatabaseTracker:
            def __init__(self, op: str, coll: str):
                self.operation = op
                self.collection = coll
                self.start_time = None
                self.status = "success"

            def __enter__(self):
                self.start_time = time.time()
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                if exc_type is not None:
                    self.status = "error"

                duration = time.time() - self.start_time

                # Record database operation duration with error handling
                try:
                    DATABASE_OPERATION_DURATION.labels(
                        operation=self.operation, collection=self.collection
                    ).observe(duration)
                    logger.debug(
                        "Successfully recorded database operation duration",
                        operation=self.operation,
                        collection=self.collection,
                        duration=duration,
                        status=self.status,
                    )
                except Exception as e:
                    logger.error(
                        "Failed to record database operation duration metric",
                        error=str(e),
                        error_type=type(e).__name__,
                        operation=self.operation,
                        collection=self.collection,
                        duration=duration,
                        status=self.status,
                        exc_info=True,
                    )

                # Record database operation count with error handling
                try:
                    DATABASE_OPERATION_COUNT.labels(
                        operation=self.operation,
                        collection=self.collection,
                        status=self.status,
                    ).inc()
                    logger.debug(
                        "Successfully recorded database operation count",
                        operation=self.operation,
                        collection=self.collection,
                        status=self.status,
                    )
                except Exception as e:
                    logger.error(
                        "Failed to record database operation count metric",
                        error=str(e),
                        error_type=type(e).__name__,
                        operation=self.operation,
                        collection=self.collection,
                        status=self.status,
                        exc_info=True,
                    )

                if self.status == "error":
                    logger.error(
                        "Database operation failed - metrics collection attempted",
                        operation=self.operation,
                        collection=self.collection,
                        duration=duration,
                    )
                elif duration > 0.1:  # Log slow database operations
                    logger.warning(
                        "Slow database operation detected - metrics collection attempted",
                        operation=self.operation,
                        collection=self.collection,
                        duration=duration,
                    )

        return DatabaseTracker(operation, collection)

    @staticmethod
    def track_external_service(service: str, endpoint: str):
        """
        Context manager to track external service calls.

        Args:
            service: Service name
            endpoint: Endpoint path

        Returns:
            Context manager
        """

        class ExternalServiceTracker:
            def __init__(self, svc: str, ep: str):
                self.service = svc
                self.endpoint = ep
                self.start_time = None
                self.status = "success"

            def __enter__(self):
                self.start_time = time.time()
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                if exc_type is not None:
                    self.status = "error"

                duration = time.time() - self.start_time

                # Record external service duration with error handling
                try:
                    EXTERNAL_SERVICE_DURATION.labels(
                        service=self.service, endpoint=self.endpoint
                    ).observe(duration)
                    logger.debug(
                        "Successfully recorded external service duration",
                        service=self.service,
                        endpoint=self.endpoint,
                        duration=duration,
                        status=self.status,
                    )
                except Exception as e:
                    logger.error(
                        "Failed to record external service duration metric",
                        error=str(e),
                        error_type=type(e).__name__,
                        service=self.service,
                        endpoint=self.endpoint,
                        duration=duration,
                        status=self.status,
                        exc_info=True,
                    )

                # Record external service count with error handling
                try:
                    EXTERNAL_SERVICE_COUNT.labels(
                        service=self.service, endpoint=self.endpoint, status=self.status
                    ).inc()
                    logger.debug(
                        "Successfully recorded external service count",
                        service=self.service,
                        endpoint=self.endpoint,
                        status=self.status,
                    )
                except Exception as e:
                    logger.error(
                        "Failed to record external service count metric",
                        error=str(e),
                        error_type=type(e).__name__,
                        service=self.service,
                        endpoint=self.endpoint,
                        status=self.status,
                        exc_info=True,
                    )

                if self.status == "error":
                    logger.error(
                        "External service call failed - metrics collection attempted",
                        service=self.service,
                        endpoint=self.endpoint,
                        duration=duration,
                    )
                elif duration > 5.0:  # Log slow external service calls
                    logger.warning(
                        "Slow external service call detected - metrics collection attempted",
                        service=self.service,
                        endpoint=self.endpoint,
                        duration=duration,
                    )

        return ExternalServiceTracker(service, endpoint)


class SystemMonitor:
    """
    System resource monitoring.
    """

    @staticmethod
    def update_system_metrics():
        """
        Update system resource metrics.
        """
        try:
            import psutil

            # Memory usage
            memory = psutil.virtual_memory()
            MEMORY_USAGE.set(memory.used)

            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            CPU_USAGE.set(cpu_percent)

            logger.debug(
                "System metrics updated",
                memory_used_mb=memory.used / 1024 / 1024,
                memory_percent=memory.percent,
                cpu_percent=cpu_percent,
            )

        except ImportError:
            logger.warning("psutil not available, system metrics disabled")
        except Exception as e:
            logger.error("Failed to update system metrics", error=str(e))


def setup_monitoring(app) -> Instrumentator:
    """
    Setup monitoring and observability for the FastAPI application.

    Args:
        app: FastAPI application instance

    Returns:
        Configured Instrumentator instance
    """
    from src.config import get_settings

    settings = get_settings()

    # Check if metrics are enabled
    if not settings.enable_metrics:
        logger.info("Metrics disabled, skipping monitoring setup")
        return None

    # Create instrumentator
    instrumentator = Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        should_respect_env_var=False,  # Use settings instead of env var
        should_instrument_requests_inprogress=False,  # We use our own in-flight tracking
        excluded_handlers=[
            "/metrics"
        ],  # Only exclude metrics endpoint, let our middleware handle health
        inprogress_name="http_requests_inprogress",
        inprogress_labels=True,
    )

    # Add only non-conflicting metrics
    # Note: We use our custom EnhancedHTTPMetricsMiddleware for HTTP request metrics
    # Only add metrics that don't conflict with our custom implementation
    instrumentator.add(metrics.combined_size())  # Request/response size metrics

    # Remove custom /metrics endpoint registration here
    # /metrics is now mounted globally in main.py via prometheus_client.make_asgi_app()

    # Instrument the app
    instrumentator.instrument(app)

    logger.info("Monitoring and observability setup complete")

    return instrumentator


def get_health_metrics() -> Dict[str, Any]:
    """
    Get current health and performance metrics.

    Returns:
        Dictionary containing current metrics
    """
    try:
        import psutil

        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=0.1)

        return {
            "memory": {
                "used_bytes": memory.used,
                "available_bytes": memory.available,
                "percent": memory.percent,
            },
            "cpu": {"percent": cpu_percent},
            "http_requests_in_flight": HTTP_REQUESTS_IN_FLIGHT._value._value,
        }
    except ImportError:
        logger.warning("psutil not available for health metrics")
        return {
            "http_requests_in_flight": HTTP_REQUESTS_IN_FLIGHT._value._value,
            "system_metrics": "unavailable",
        }
    except Exception as e:
        logger.error("Failed to get health metrics", error=str(e))
        return {
            "http_requests_in_flight": HTTP_REQUESTS_IN_FLIGHT._value._value,
            "error": str(e),
        }
