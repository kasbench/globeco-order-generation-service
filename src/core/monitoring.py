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
from prometheus_client import Counter, Gauge, Histogram, generate_latest
from prometheus_fastapi_instrumentator import Instrumentator, metrics
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.utils import get_logger

logger = get_logger(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total number of HTTP requests',
    ['method', 'endpoint', 'status_code'],
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    buckets=[0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0],
)

ACTIVE_CONNECTIONS = Gauge('active_connections', 'Number of active connections')

OPTIMIZATION_DURATION = Histogram(
    'optimization_duration_seconds',
    'Portfolio optimization duration in seconds',
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
)

OPTIMIZATION_COUNT = Counter(
    'optimizations_total', 'Total number of optimization requests', ['status']
)

DATABASE_OPERATION_DURATION = Histogram(
    'database_operation_duration_seconds',
    'Database operation duration in seconds',
    ['operation', 'collection'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

DATABASE_OPERATION_COUNT = Counter(
    'database_operations_total',
    'Total number of database operations',
    ['operation', 'collection', 'status'],
)

EXTERNAL_SERVICE_DURATION = Histogram(
    'external_service_duration_seconds',
    'External service call duration in seconds',
    ['service', 'endpoint'],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)

EXTERNAL_SERVICE_COUNT = Counter(
    'external_service_requests_total',
    'Total number of external service requests',
    ['service', 'endpoint', 'status'],
)

ERROR_COUNT = Counter(
    'errors_total', 'Total number of errors', ['error_type', 'endpoint']
)

MEMORY_USAGE = Gauge('memory_usage_bytes', 'Current memory usage in bytes')

CPU_USAGE = Gauge('cpu_usage_percent', 'Current CPU usage percentage')


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware to collect HTTP request metrics.
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
        start_time = time.time()

        # Increment active connections
        ACTIVE_CONNECTIONS.inc()

        try:
            # Process request
            response = await call_next(request)

            # Record metrics
            duration = time.time() - start_time
            method = request.method
            endpoint = self._get_endpoint_label(request)
            status_code = str(response.status_code)

            REQUEST_COUNT.labels(
                method=method, endpoint=endpoint, status_code=status_code
            ).inc()

            REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration)

            # Log slow requests
            if duration > 1.0:
                logger.warning(
                    "Slow request detected",
                    method=method,
                    endpoint=endpoint,
                    duration=duration,
                    status_code=status_code,
                )

            return response

        except Exception as e:
            # Record error metrics
            ERROR_COUNT.labels(
                error_type=type(e).__name__, endpoint=self._get_endpoint_label(request)
            ).inc()

            logger.error(
                "Request processing error",
                error=str(e),
                method=request.method,
                endpoint=self._get_endpoint_label(request),
                exc_info=True,
            )

            raise
        finally:
            # Decrement active connections
            ACTIVE_CONNECTIONS.dec()

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
                logger.error("Optimization failed", error=str(e), exc_info=True)
                raise
            finally:
                duration = time.time() - start_time
                OPTIMIZATION_DURATION.observe(duration)
                OPTIMIZATION_COUNT.labels(status=status).inc()

                logger.info("Optimization completed", duration=duration, status=status)

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

                DATABASE_OPERATION_DURATION.labels(
                    operation=self.operation, collection=self.collection
                ).observe(duration)

                DATABASE_OPERATION_COUNT.labels(
                    operation=self.operation,
                    collection=self.collection,
                    status=self.status,
                ).inc()

                if self.status == "error":
                    logger.error(
                        "Database operation failed",
                        operation=self.operation,
                        collection=self.collection,
                        duration=duration,
                    )
                elif duration > 0.1:  # Log slow database operations
                    logger.warning(
                        "Slow database operation",
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

                EXTERNAL_SERVICE_DURATION.labels(
                    service=self.service, endpoint=self.endpoint
                ).observe(duration)

                EXTERNAL_SERVICE_COUNT.labels(
                    service=self.service, endpoint=self.endpoint, status=self.status
                ).inc()

                if self.status == "error":
                    logger.error(
                        "External service call failed",
                        service=self.service,
                        endpoint=self.endpoint,
                        duration=duration,
                    )
                elif duration > 5.0:  # Log slow external service calls
                    logger.warning(
                        "Slow external service call",
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
        should_instrument_requests_inprogress=True,
        excluded_handlers=["/metrics", "/health", "/health/live", "/health/ready"],
        inprogress_name="http_requests_inprogress",
        inprogress_labels=True,
    )

    # Add default metrics
    instrumentator.add(metrics.default())
    instrumentator.add(metrics.combined_size())
    instrumentator.add(metrics.requests())
    instrumentator.add(metrics.latency())

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
            "active_connections": ACTIVE_CONNECTIONS._value._value,
        }
    except ImportError:
        logger.warning("psutil not available for health metrics")
        return {
            "active_connections": ACTIVE_CONNECTIONS._value._value,
            "system_metrics": "unavailable",
        }
    except Exception as e:
        logger.error("Failed to get health metrics", error=str(e))
        return {"active_connections": ACTIVE_CONNECTIONS._value._value, "error": str(e)}
