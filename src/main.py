"""
GlobeCo Order Generation Service - Main Application Entry Point

This module contains the FastAPI application factory and main entry point for the
Order Generation Service. It sets up the application with all necessary middleware,
routers, and configuration.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config import get_settings
from src.core.utils import (
    configure_structured_logging,
    get_logger,
    set_correlation_id,
    create_response_metadata,
)
from src.core.security import SecurityHeaders
from src.api.routers.health import router as health_router


# Configure structured logging early
configure_structured_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
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
    # TODO: Initialize database connections

    logger.info("Setting up external service clients...")
    # TODO: Initialize external service clients

    logger.info("Application startup completed")

    yield

    # Shutdown logic
    logger.info("Shutting down application...")
    # TODO: Close database connections
    # TODO: Close external service clients
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

    # CORS middleware (first in stack)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )

    # Add custom middleware
    app.middleware("http")(correlation_middleware)
    app.middleware("http")(security_headers_middleware)

    # Add routers
    app.include_router(health_router, prefix="/health", tags=["health"])

    # TODO: Add API routers
    # app.include_router(models_router, prefix="/api/v1", tags=["models"])
    # app.include_router(rebalance_router, prefix="/api/v1", tags=["rebalance"])

    # Global exception handler
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
        OrderGenerationServiceError,
        ValidationError,
        BusinessRuleViolationError,
        OptimizationError,
        ExternalServiceError,
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
