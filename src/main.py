"""
GlobeCo Order Generation Service - Main Application Entry Point

This module contains the FastAPI application factory and main entry point for the
Order Generation Service. It sets up the application with all necessary middleware,
routers, and configuration.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config import get_settings


logger = logging.getLogger(__name__)


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
    logger.info(f"Starting {settings.service_name} v{settings.version}")
    
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


def create_app() -> FastAPI:
    """
    Application factory function to create and configure the FastAPI app.
    
    Returns:
        FastAPI: Configured FastAPI application instance
    """
    settings = get_settings()
    
    app = FastAPI(
        title=settings.service_name,
        description="Portfolio optimization and order generation microservice",
        version=settings.version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins for benchmarking
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add routers
    # TODO: Add API routers
    # app.include_router(health_router, prefix="/health", tags=["health"])
    # app.include_router(models_router, prefix="/api/v1", tags=["models"])
    # app.include_router(rebalance_router, prefix="/api/v1", tags=["rebalance"])
    
    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        logger.error(f"Global exception handler caught: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred",
                    "timestamp": "2024-01-01T00:00:00Z",  # TODO: Use actual timestamp
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