"""
GlobeCo Order Generation Service - Main Application Entry Point

This module contains the FastAPI application factory and main entry point for the
Order Generation Service. It sets up the application with all necessary middleware,
routers, and configuration.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# --- OpenTelemetry Instrumentation (GlobeCo Standard) ---
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
    OTLPMetricExporter as OTLPMetricExporterGRPC,
)
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter as OTLPSpanExporterGRPC,
)
from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
    OTLPMetricExporter as OTLPMetricExporterHTTP,
)
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter as OTLPSpanExporterHTTP,
)
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import make_asgi_app

from src.api.routers.health import router as health_router
from src.api.routers.models import router as models_router
from src.api.routers.rebalance import router as rebalance_router
from src.api.routers.rebalances import router as rebalances_router
from src.config import get_settings
from src.core.monitoring import MetricsMiddleware, setup_monitoring
from src.core.security import SecurityHeaders
from src.core.utils import (
    configure_structured_logging,
    create_response_metadata,
    get_correlation_id,
    get_logger,
    set_correlation_id,
)

# Set OpenTelemetry resource attributes
resource = Resource.create(
    {
        "service.name": "globeco-order-generation-service",
        # Optionally add version/namespace if desired
        # "service.version": "0.1.0",
        # "service.namespace": "globeco",
    }
)

# Tracing setup (gRPC and HTTP exporters)
trace.set_tracer_provider(TracerProvider(resource=resource))
tracer_provider = trace.get_tracer_provider()
tracer_provider.add_span_processor(
    BatchSpanProcessor(
        OTLPSpanExporterGRPC(
            endpoint="otel-collector-collector.monitoring.svc.cluster.local:4317",
            insecure=True,
        )
    )
)
tracer_provider.add_span_processor(
    BatchSpanProcessor(
        OTLPSpanExporterHTTP(
            endpoint="http://otel-collector-collector.monitoring.svc.cluster.local:4318/v1/traces"
        )
    )
)

# Metrics setup (gRPC and HTTP exporters)
from opentelemetry.metrics import set_meter_provider

meter_provider = MeterProvider(
    resource=resource,
    metric_readers=[
        PeriodicExportingMetricReader(
            OTLPMetricExporterGRPC(
                endpoint="otel-collector-collector.monitoring.svc.cluster.local:4317",
                insecure=True,
            )
        ),
        PeriodicExportingMetricReader(
            OTLPMetricExporterHTTP(
                endpoint="http://otel-collector-collector.monitoring.svc.cluster.local:4318/v1/metrics"
            )
        ),
    ],
)
set_meter_provider(meter_provider)

# --- End OpenTelemetry Instrumentation ---

# Configure structured logging early with settings
settings = get_settings()
configure_structured_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """
    Application lifespan manager for startup and shutdown events.

    Args:
        app: The FastAPI application instance

    Yields:
        None: Control back to the application
    """
    settings = get_settings()
    logger.info(
        "Starting application", service=settings.service_name, version=settings.version
    )

    # Startup logic
    logger.info("Initializing database connections...")
    from src.infrastructure.database.database import init_database

    await init_database()

    logger.info("Setting up external service clients...")
    # External service clients are managed through dependency injection with @lru_cache()
    # and HTTP clients that don't require explicit initialization or connection pooling.
    # Circuit breaker patterns and retry logic are handled within each client implementation.
    logger.info("External service clients configured via dependency injection")

    logger.info("Application startup completed")

    yield

    # Shutdown logic
    logger.info("Shutting down application...")
    from src.infrastructure.database.database import close_database

    await close_database()
    # External service clients are HTTP-based and don't require explicit cleanup
    # The dependency injection system handles their lifecycle automatically
    logger.info("Application shutdown completed")


async def correlation_middleware(request: Request, call_next):
    """
    Middleware to handle correlation IDs for request tracing.

    Args:
        request: The incoming request
        call_next: The next middleware/endpoint to call

    Returns:
        Response with correlation ID header
    """
    # Extract correlation ID from headers or generate new one
    correlation_id = request.headers.get("X-Correlation-ID")
    if not correlation_id:
        from src.core.utils import generate_correlation_id

        correlation_id = generate_correlation_id()

    # Set correlation ID in context
    set_correlation_id(correlation_id)

    # Log request
    logger.info(
        "Request received",
        method=request.method,
        url=str(request.url),
        client_ip=request.client.host if request.client else None,
    )

    # Process request
    response = await call_next(request)

    # Add correlation ID to response headers
    response.headers["X-Correlation-ID"] = correlation_id

    # Log response
    logger.info(
        "Request completed",
        method=request.method,
        url=str(request.url),
        status_code=response.status_code,
    )

    return response


async def security_headers_middleware(request: Request, call_next):
    """
    Middleware to add security headers to responses.

    Args:
        request: The incoming request
        call_next: The next middleware/endpoint to call

    Returns:
        Response with security headers
    """
    response = await call_next(request)

    # Add security headers
    security_headers = SecurityHeaders.get_default_headers()

    # Special CSP for Swagger UI endpoints to allow external resources
    if (
        request.url.path in ["/docs", "/redoc"]
        or request.url.path.startswith("/docs/")
        or request.url.path.startswith("/redoc/")
    ):
        security_headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com; "
            "img-src 'self' data: https:; "
            "font-src 'self' https://cdn.jsdelivr.net https://unpkg.com;"
        )

    for header_name, header_value in security_headers.items():
        response.headers[header_name] = header_value

    return response


def create_app() -> FastAPI:
    """
    Application factory function to create and configure the FastAPI app.

    Returns:
        FastAPI: Configured FastAPI application instance
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.service_name,
        description="Portfolio optimization and order generation microservice for the GlobeCo Suite",
        version=settings.version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Instrument FastAPI, HTTPX, and logging for OpenTelemetry
    FastAPIInstrumentor().instrument_app(app)
    HTTPXClientInstrumentor().instrument()
    LoggingInstrumentor().instrument(set_logging_format=True)

    # Mount Prometheus /metrics endpoint (OpenTelemetry standard)
    app.mount("/metrics", make_asgi_app())

    # CORS middleware (first in stack)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )

    # Add custom middleware
    if settings.enable_metrics:
        app.add_middleware(MetricsMiddleware)
    app.middleware("http")(correlation_middleware)
    app.middleware("http")(security_headers_middleware)

    # Setup monitoring and observability
    if settings.enable_metrics:
        instrumentator = setup_monitoring(app)
        if instrumentator is None:
            logger.warning("Monitoring setup returned None despite enable_metrics=True")

    # Add routers
    app.include_router(health_router, prefix="/health", tags=["health"])
    app.include_router(models_router, prefix="/api/v1", tags=["models"])
    app.include_router(rebalance_router, prefix="/api/v1", tags=["rebalance"])
    app.include_router(rebalances_router)

    # Global exception handler
    @app.exception_handler(TimeoutError)
    async def timeout_exception_handler(request: Request, exc: TimeoutError):
        """Handle timeout errors, especially for health check endpoints."""
        logger.warning(
            "Timeout error occurred",
            exception=str(exc),
            path=request.url.path,
            method=request.method,
        )

        # Special handling for health check endpoints
        if request.url.path.startswith("/health"):
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "service": "GlobeCo Order Generation Service",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "correlation_id": get_correlation_id(),
                    "error": {
                        "code": "TIMEOUT",
                        "message": str(exc),
                    },
                },
            )

        # For non-health endpoints, return generic service unavailable
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "SERVICE_TIMEOUT",
                    "message": "Request timed out",
                    **create_response_metadata(),
                }
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Global exception handler for unhandled exceptions."""
        logger.error(
            "Unhandled exception occurred",
            exception=str(exc),
            exception_type=type(exc).__name__,
            path=request.url.path,
            method=request.method,
            exc_info=True,
        )

        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred",
                    **create_response_metadata(),
                }
            },
        )

    # Custom exception handlers for domain-specific exceptions
    from src.core.exceptions import (
        BusinessRuleViolationError,
        ExternalServiceError,
        ModelNotFoundError,
        NotFoundError,
        OptimizationError,
        PortfolioNotFoundError,
        ValidationError,
    )

    @app.exception_handler(NotFoundError)
    async def not_found_exception_handler(request: Request, exc: NotFoundError):
        """Handle not found errors."""
        logger.warning(
            "Resource not found",
            error_code=exc.error_code,
            message=exc.message,
            details=exc.details,
        )

        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                    "details": exc.details,
                    **create_response_metadata(),
                }
            },
        )

    @app.exception_handler(ModelNotFoundError)
    async def model_not_found_exception_handler(
        request: Request, exc: ModelNotFoundError
    ):
        """Handle model not found errors."""
        logger.warning(
            "Model not found",
            error_code=exc.error_code,
            message=exc.message,
            details=exc.details,
        )

        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                    "details": exc.details,
                    **create_response_metadata(),
                }
            },
        )

    @app.exception_handler(PortfolioNotFoundError)
    async def portfolio_not_found_exception_handler(
        request: Request, exc: PortfolioNotFoundError
    ):
        """Handle portfolio not found errors."""
        logger.warning(
            "Portfolio not found",
            error_code=exc.error_code,
            message=exc.message,
            details=exc.details,
        )

        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                    "details": exc.details,
                    **create_response_metadata(),
                }
            },
        )

    @app.exception_handler(ValidationError)
    async def validation_exception_handler(request: Request, exc: ValidationError):
        """Handle validation errors."""
        logger.warning(
            "Validation error",
            error_code=exc.error_code,
            message=exc.message,
            details=exc.details,
        )

        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                    "details": exc.details,
                    **create_response_metadata(),
                }
            },
        )

    @app.exception_handler(BusinessRuleViolationError)
    async def business_rule_exception_handler(
        request: Request, exc: BusinessRuleViolationError
    ):
        """Handle business rule violations."""
        logger.warning(
            "Business rule violation",
            error_code=exc.error_code,
            message=exc.message,
            details=exc.details,
        )

        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                    "details": exc.details,
                    **create_response_metadata(),
                }
            },
        )

    @app.exception_handler(OptimizationError)
    async def optimization_exception_handler(request: Request, exc: OptimizationError):
        """Handle optimization errors."""
        logger.error(
            "Optimization error",
            error_code=exc.error_code,
            message=exc.message,
            details=exc.details,
        )

        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                    "details": exc.details,
                    **create_response_metadata(),
                }
            },
        )

    @app.exception_handler(ExternalServiceError)
    async def external_service_exception_handler(
        request: Request, exc: ExternalServiceError
    ):
        """Handle external service errors."""
        logger.error(
            "External service error",
            error_code=exc.error_code,
            message=exc.message,
            details=exc.details,
        )

        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                    "details": exc.details,
                    **create_response_metadata(),
                }
            },
        )

    return app


# Create the application instance
app = create_app()


def main() -> None:
    """
    Main entry point for running the application.

    This function is used when running the application directly or via
    the command line script defined in pyproject.toml.
    """
    import uvicorn

    settings = get_settings()

    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
