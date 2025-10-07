"""
Monitoring and observability module for the Order Generation Service.

This module provides comprehensive monitoring capabilities including:
- Prometheus metrics collection
- Performance monitoring
- Health check instrumentation
- Request/response tracking
- Error monitoring
"""

import os
import time
from typing import Any, Callable, Dict

from fastapi import Request, Response

# OpenTelemetry metrics imports
from opentelemetry import metrics as otel_metrics
from opentelemetry.metrics import get_meter
from prometheus_client import (
    GC_COLLECTOR,
    PLATFORM_COLLECTOR,
    PROCESS_COLLECTOR,
    REGISTRY,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    multiprocess,
    start_http_server,
)
from prometheus_fastapi_instrumentator import Instrumentator, metrics
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.utils import get_logger

logger = get_logger(__name__)

# Configure Prometheus for multiprocess mode if running with multiple workers
prometheus_multiproc_dir = os.environ.get('prometheus_multiproc_dir')
if prometheus_multiproc_dir:
    try:
        # Verify the directory exists and is writable
        if not os.path.exists(prometheus_multiproc_dir):
            os.makedirs(prometheus_multiproc_dir, exist_ok=True)
            logger.info(
                f"Created Prometheus multiprocess directory: {prometheus_multiproc_dir}"
            )

        # Test write access
        test_file = os.path.join(prometheus_multiproc_dir, "test_access")
        try:
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
        except Exception as e:
            logger.error(f"Prometheus multiprocess directory not writable: {e}")
            raise

        # Create a custom registry that combines multiprocess and process metrics
        registry = CollectorRegistry()

        # Add multiprocess collector for application metrics
        multiprocess.MultiProcessCollector(registry)

        # For multiprocess mode, we need to ensure process metrics are collected
        # The issue might be that the default collectors don't work in multiprocess mode
        # Let's create our own process metrics using psutil
        logger.info("Setting up process metrics for multiprocess mode")

        # We'll rely on our custom process metrics and the default collectors
        # The MultiProcessCollector should handle the application metrics
        # and we'll add process metrics through our health metrics system

        logger.info(
            f"Prometheus multiprocess mode enabled with directory: {prometheus_multiproc_dir}"
        )
        logger.info("Multiprocess and process collectors configured")
    except Exception as e:
        logger.error(f"Failed to initialize Prometheus multiprocess mode: {e}")
        logger.info("Falling back to single process mode")
        registry = REGISTRY
else:
    # Use default registry for single process (includes default collectors automatically)
    registry = REGISTRY
    logger.info("Prometheus single process mode")

# Get OpenTelemetry meter for creating metrics
meter = get_meter(__name__)

# OpenTelemetry HTTP metrics (sent to OTEL Collector)
otel_http_requests_total = meter.create_counter(
    name="http_requests_total", description="Total number of HTTP requests", unit="1"
)

otel_http_request_duration = meter.create_histogram(
    name="http_request_duration_milliseconds",
    description="HTTP request duration in milliseconds",
    unit="ms",
)

otel_http_requests_in_flight = meter.create_up_down_counter(
    name="http_requests_in_flight",
    description="Number of HTTP requests currently being processed",
    unit="1",
)

# OpenTelemetry Process metrics (sent to OTEL Collector)
otel_process_cpu_seconds_total = meter.create_counter(
    name="process_cpu_seconds_total",
    description="Total user and system CPU time spent in seconds",
    unit="s",
)

otel_process_resident_memory_bytes = meter.create_up_down_counter(
    name="process_resident_memory_bytes",
    description="Resident memory size in bytes",
    unit="By",
)

otel_process_virtual_memory_bytes = meter.create_up_down_counter(
    name="process_virtual_memory_bytes",
    description="Virtual memory size in bytes",
    unit="By",
)

otel_process_open_fds = meter.create_up_down_counter(
    name="process_open_fds",
    description="Number of open file descriptors",
    unit="1",
)

otel_process_max_fds = meter.create_up_down_counter(
    name="process_max_fds",
    description="Maximum number of open file descriptors",
    unit="1",
)

otel_process_start_time_seconds = meter.create_up_down_counter(
    name="process_start_time_seconds",
    description="Start time of the process since unix epoch in seconds",
    unit="s",
)

# OpenTelemetry Python metrics (sent to OTEL Collector)
otel_python_info = meter.create_up_down_counter(
    name="python_info",
    description="Python platform information",
    unit="1",
)

otel_python_threads = meter.create_up_down_counter(
    name="python_threads",
    description="Number of Python threads",
    unit="1",
)

otel_python_gc_collections_total = meter.create_counter(
    name="python_gc_collections_total",
    description="Number of times this generation was collected",
    unit="1",
)

otel_python_gc_objects_collected_total = meter.create_counter(
    name="python_gc_objects_collected_total",
    description="Objects collected during gc",
    unit="1",
)

otel_python_gc_objects_uncollectable_total = meter.create_counter(
    name="python_gc_objects_uncollectable_total",
    description="Uncollectable object found during GC",
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
        # Pass the registry to the metric constructor for multiprocess support
        if labels:
            metric = metric_class(
                name, description, labels, registry=registry, **kwargs
            )
        else:
            metric = metric_class(name, description, registry=registry, **kwargs)

        _METRICS_REGISTRY[registry_key] = metric
        logger.debug(f"Created new metric: {name}")
        return metric

    except ValueError as e:
        if "Duplicated timeseries" in str(e) or "already registered" in str(e).lower():
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
    'http_request_duration_milliseconds',
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

# Custom process metrics using psutil (since default ProcessCollector may not work in multiprocess mode)
PROCESS_CPU_SECONDS_TOTAL = _get_or_create_metric(
    Counter,
    'process_cpu_seconds_total',
    'Total user and system CPU time spent in seconds',
)

PROCESS_RESIDENT_MEMORY_BYTES = _get_or_create_metric(
    Gauge, 'process_resident_memory_bytes', 'Resident memory size in bytes'
)

PROCESS_VIRTUAL_MEMORY_BYTES = _get_or_create_metric(
    Gauge, 'process_virtual_memory_bytes', 'Virtual memory size in bytes'
)

PROCESS_OPEN_FDS = _get_or_create_metric(
    Gauge, 'process_open_fds', 'Number of open file descriptors'
)

PROCESS_MAX_FDS = _get_or_create_metric(
    Gauge, 'process_max_fds', 'Maximum number of open file descriptors'
)

PROCESS_START_TIME_SECONDS = _get_or_create_metric(
    Gauge,
    'process_start_time_seconds',
    'Start time of the process since unix epoch in seconds',
)

# Python info metric (static)
PYTHON_INFO = _get_or_create_metric(
    Gauge,
    'python_info',
    'Python platform information',
    ['version', 'implementation', 'major', 'minor', 'patchlevel'],
)

# Python threads metric
PYTHON_THREADS = _get_or_create_metric(
    Gauge, 'python_threads', 'Number of Python threads'
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

        # Update process metrics periodically (every 100 requests to avoid overhead)
        if hasattr(self, '_request_count'):
            self._request_count += 1
        else:
            self._request_count = 1

        if self._request_count % 100 == 0:
            try:
                update_process_metrics()  # For Prometheus /metrics endpoint
                update_otel_process_metrics()  # For OpenTelemetry Collector
            except Exception as e:
                logger.debug(f"Failed to update process metrics: {e}")

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

    # Ensure process metrics are available in multiprocess mode
    prometheus_multiproc_dir = os.environ.get('prometheus_multiproc_dir')
    if prometheus_multiproc_dir:
        logger.info("Process metrics enabled for multiprocess mode")
    else:
        logger.info("Process metrics enabled for single process mode")

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

    # Initialize process metrics
    update_process_metrics()  # For Prometheus /metrics endpoint
    update_otel_process_metrics()  # For OpenTelemetry Collector

    # Debug registry information
    debug_registry_collectors()

    # Verify process metrics are available
    if verify_process_metrics_available():
        logger.info("Monitoring and observability setup complete with process metrics")
    else:
        logger.warning(
            "Monitoring setup complete but some process metrics may be missing"
        )

    logger.info(
        "OpenTelemetry process metrics initialized and will be sent to OTEL Collector"
    )
    return instrumentator


def cleanup_multiprocess_metrics():
    """Clean up multiprocess metrics directory on worker shutdown."""
    multiproc_dir = os.environ.get('prometheus_multiproc_dir')
    if multiproc_dir and os.path.exists(multiproc_dir):
        try:
            import shutil

            shutil.rmtree(multiproc_dir)
            logger.info("Cleaned up multiprocess metrics directory")
        except Exception as e:
            logger.error(f"Failed to clean up multiprocess metrics directory: {e}")


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


def verify_process_metrics_available() -> bool:
    """
    Verify that process metrics are available in the registry.

    Returns:
        True if process metrics are available, False otherwise
    """
    try:
        metrics_output = generate_latest(registry).decode('utf-8')

        # Check for key process and HTTP metrics
        required_metrics = [
            # Process metrics
            'process_cpu_seconds_total',
            'process_resident_memory_bytes',
            'process_virtual_memory_bytes',
            'process_open_fds',
            'process_max_fds',
            'process_start_time_seconds',
            # Python metrics
            'python_info',
            'python_gc_objects_collected_total',
            'python_gc_collections_total',
            'python_threads',
            # HTTP metrics
            'http_request_duration_milliseconds_bucket',
            'http_request_duration_milliseconds_count',
            'http_request_duration_milliseconds_sum',
            'http_requests_in_flight',
            'http_requests_total',
        ]

        available_metrics = []
        missing_metrics = []

        for metric in required_metrics:
            if metric in metrics_output:
                available_metrics.append(metric)
            else:
                missing_metrics.append(metric)

        # Log all available metrics for debugging
        all_metric_names = []
        for line in metrics_output.split('\n'):
            if line.startswith('#') or not line.strip():
                continue
            if '{' in line:
                metric_name = line.split('{')[0]
            else:
                metric_name = line.split(' ')[0] if ' ' in line else line
            if metric_name and metric_name not in all_metric_names:
                all_metric_names.append(metric_name)

        logger.debug(
            "Available metrics in registry",
            total_metrics=len(all_metric_names),
            sample_metrics=all_metric_names[:10],  # Show first 10 for debugging
        )

        if missing_metrics:
            logger.warning(
                "Some process metrics are missing",
                missing=missing_metrics,
                available=available_metrics,
                multiprocess_mode=bool(os.environ.get('prometheus_multiproc_dir')),
            )
            return False
        else:
            logger.info(
                "All process metrics are available",
                available_count=len(available_metrics),
                multiprocess_mode=bool(os.environ.get('prometheus_multiproc_dir')),
            )
            return True

    except Exception as e:
        logger.error(
            "Failed to verify process metrics",
            error=str(e),
            error_type=type(e).__name__,
        )
        return False


def update_process_metrics():
    """
    Update process metrics using psutil.
    This ensures we have process metrics even when the default ProcessCollector doesn't work.
    """
    try:
        import platform
        import sys

        import psutil

        # Get current process
        process = psutil.Process()

        # CPU metrics
        cpu_times = process.cpu_times()
        total_cpu_time = cpu_times.user + cpu_times.system
        PROCESS_CPU_SECONDS_TOTAL._value._value = total_cpu_time

        # Memory metrics
        memory_info = process.memory_info()
        PROCESS_RESIDENT_MEMORY_BYTES.set(memory_info.rss)
        PROCESS_VIRTUAL_MEMORY_BYTES.set(memory_info.vms)

        # File descriptor metrics (Unix only)
        try:
            if hasattr(process, 'num_fds'):
                PROCESS_OPEN_FDS.set(process.num_fds())

            # Get max FDs from system limits
            import resource

            max_fds = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
            if max_fds != resource.RLIM_INFINITY:
                PROCESS_MAX_FDS.set(max_fds)
        except (AttributeError, OSError):
            # Not available on this platform
            pass

        # Process start time
        PROCESS_START_TIME_SECONDS.set(process.create_time())

        # Python info (set once)
        try:
            if hasattr(PYTHON_INFO, '_value') and PYTHON_INFO._value._value == 0:
                version_info = sys.version_info
                PYTHON_INFO.labels(
                    version=platform.python_version(),
                    implementation=platform.python_implementation(),
                    major=str(version_info.major),
                    minor=str(version_info.minor),
                    patchlevel=str(version_info.micro),
                ).set(1)
        except AttributeError:
            # PYTHON_INFO is a dummy metric, skip setting it
            pass

        # Python threads count
        import threading

        PYTHON_THREADS.set(threading.active_count())

        logger.debug("Process metrics updated successfully")

    except ImportError:
        logger.warning("psutil not available for process metrics")
    except Exception as e:
        logger.error(
            "Failed to update process metrics",
            error=str(e),
            error_type=type(e).__name__,
        )


def update_otel_process_metrics():
    """
    Update OpenTelemetry process metrics using psutil.
    These metrics will be sent to the OTEL Collector and then to Prometheus.
    """
    try:
        import gc
        import platform
        import sys
        import threading

        import psutil

        # Get current process
        process = psutil.Process()

        # CPU metrics - use add() for counters to set absolute values
        cpu_times = process.cpu_times()
        total_cpu_time = cpu_times.user + cpu_times.system

        # For counters, we need to track the previous value and only add the difference
        if not hasattr(update_otel_process_metrics, '_last_cpu_time'):
            update_otel_process_metrics._last_cpu_time = 0

        cpu_diff = total_cpu_time - update_otel_process_metrics._last_cpu_time
        if cpu_diff > 0:
            otel_process_cpu_seconds_total.add(cpu_diff)
            update_otel_process_metrics._last_cpu_time = total_cpu_time

        # Memory metrics - use add() with current value for up-down counters
        memory_info = process.memory_info()

        # For up-down counters, we need to track previous values and add the difference
        if not hasattr(update_otel_process_metrics, '_last_rss'):
            update_otel_process_metrics._last_rss = 0
            update_otel_process_metrics._last_vms = 0

        rss_diff = memory_info.rss - update_otel_process_metrics._last_rss
        vms_diff = memory_info.vms - update_otel_process_metrics._last_vms

        if rss_diff != 0:
            otel_process_resident_memory_bytes.add(rss_diff)
            update_otel_process_metrics._last_rss = memory_info.rss

        if vms_diff != 0:
            otel_process_virtual_memory_bytes.add(vms_diff)
            update_otel_process_metrics._last_vms = memory_info.vms

        # File descriptor metrics (Unix only)
        try:
            if hasattr(process, 'num_fds'):
                current_fds = process.num_fds()
                if not hasattr(update_otel_process_metrics, '_last_fds'):
                    update_otel_process_metrics._last_fds = 0

                fds_diff = current_fds - update_otel_process_metrics._last_fds
                if fds_diff != 0:
                    otel_process_open_fds.add(fds_diff)
                    update_otel_process_metrics._last_fds = current_fds

            # Get max FDs from system limits
            import resource

            max_fds = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
            if max_fds != resource.RLIM_INFINITY:
                if not hasattr(update_otel_process_metrics, '_last_max_fds'):
                    update_otel_process_metrics._last_max_fds = 0

                max_fds_diff = max_fds - update_otel_process_metrics._last_max_fds
                if max_fds_diff != 0:
                    otel_process_max_fds.add(max_fds_diff)
                    update_otel_process_metrics._last_max_fds = max_fds
        except (AttributeError, OSError):
            # Not available on this platform
            pass

        # Process start time (set once)
        if not hasattr(update_otel_process_metrics, '_start_time_set'):
            start_time = process.create_time()
            otel_process_start_time_seconds.add(start_time)
            update_otel_process_metrics._start_time_set = True

        # Python info (set once)
        if not hasattr(update_otel_process_metrics, '_python_info_set'):
            version_info = sys.version_info
            attributes = {
                "version": platform.python_version(),
                "implementation": platform.python_implementation(),
                "major": str(version_info.major),
                "minor": str(version_info.minor),
                "patchlevel": str(version_info.micro),
            }
            otel_python_info.add(1, attributes)
            update_otel_process_metrics._python_info_set = True

        # Python threads count
        current_threads = threading.active_count()
        if not hasattr(update_otel_process_metrics, '_last_threads'):
            update_otel_process_metrics._last_threads = 0

        threads_diff = current_threads - update_otel_process_metrics._last_threads
        if threads_diff != 0:
            otel_python_threads.add(threads_diff)
            update_otel_process_metrics._last_threads = current_threads

        # GC metrics
        gc_stats = gc.get_stats()
        if not hasattr(update_otel_process_metrics, '_last_gc_collections'):
            update_otel_process_metrics._last_gc_collections = [0, 0, 0]
            update_otel_process_metrics._last_gc_collected = [0, 0, 0]
            update_otel_process_metrics._last_gc_uncollectable = [0, 0, 0]

        for i, stats in enumerate(gc_stats):
            # Collections
            collections = stats.get('collections', 0)
            collections_diff = (
                collections - update_otel_process_metrics._last_gc_collections[i]
            )
            if collections_diff > 0:
                otel_python_gc_collections_total.add(
                    collections_diff, {"generation": str(i)}
                )
                update_otel_process_metrics._last_gc_collections[i] = collections

            # Collected objects
            collected = stats.get('collected', 0)
            collected_diff = (
                collected - update_otel_process_metrics._last_gc_collected[i]
            )
            if collected_diff > 0:
                otel_python_gc_objects_collected_total.add(
                    collected_diff, {"generation": str(i)}
                )
                update_otel_process_metrics._last_gc_collected[i] = collected

            # Uncollectable objects
            uncollectable = stats.get('uncollectable', 0)
            uncollectable_diff = (
                uncollectable - update_otel_process_metrics._last_gc_uncollectable[i]
            )
            if uncollectable_diff > 0:
                otel_python_gc_objects_uncollectable_total.add(
                    uncollectable_diff, {"generation": str(i)}
                )
                update_otel_process_metrics._last_gc_uncollectable[i] = uncollectable

        logger.debug("OpenTelemetry process metrics updated successfully")

    except ImportError:
        logger.warning("psutil not available for OpenTelemetry process metrics")
    except Exception as e:
        logger.error(
            "Failed to update OpenTelemetry process metrics",
            error=str(e),
            error_type=type(e).__name__,
        )


def debug_registry_collectors():
    """
    Debug function to log information about registered collectors.
    """
    try:
        logger.debug(
            "Registry debug info",
            multiprocess_dir=os.environ.get('prometheus_multiproc_dir'),
            registry_type=type(registry).__name__,
        )

        # Try to get collector information
        if hasattr(registry, '_collector_to_names'):
            collectors = list(registry._collector_to_names.keys())
            collector_names = [type(c).__name__ for c in collectors]
            logger.debug(
                "Registered collectors", count=len(collectors), types=collector_names
            )

    except Exception as e:
        logger.debug("Could not debug registry collectors", error=str(e))
