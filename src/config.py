"""
Configuration module for the Order Generation Service.

This module provides environment-based configuration using Pydantic Settings,
allowing for easy configuration management across different deployment environments.
"""

import logging
from functools import lru_cache
from typing import Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and .env files.

    This class defines all configuration options for the Order Generation Service,
    with sensible defaults for development and environment variable overrides
    for production deployment.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        # Disable automatic JSON parsing for environment variables
        env_parse_none_str="",
        json_encoders={},
    )

    # Service Information
    service_name: str = Field(default="GlobeCo Order Generation Service")
    version: str = Field(default="0.1.0")
    description: str = Field(
        default="Portfolio optimization and order generation microservice"
    )

    # Server Configuration
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8088, description="Server port")
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="DEBUG", description="Logging level")

    # Database Configuration
    database_url: str = Field(
        default="mongodb://globeco-order-generation-service-mongodb:27017",
        description="MongoDB connection URL",
    )
    database_name: str = Field(
        default="globeco_order_generation", description="Database name"
    )
    database_timeout_ms: int = Field(
        default=5000, description="Database connection timeout in milliseconds"
    )
    database_max_connections: int = Field(
        default=100, description="Maximum database connections in pool"
    )
    database_min_connections: int = Field(
        default=10, description="Minimum database connections in pool"
    )
    database_idle_timeout_ms: int = Field(
        default=300000, description="Database connection idle timeout in milliseconds"
    )

    # Redis Configuration
    redis_url: str = Field(
        default="redis://globeco-order-generation-service-redis:6379/0",
        description="Redis connection URL",
    )
    redis_timeout: int = Field(
        default=5, description="Redis connection timeout in seconds"
    )

    # External Service URLs
    portfolio_accounting_service_url: str = Field(
        default="http://globeco-portfolio-accounting-service:8087",
        description="Portfolio Accounting Service base URL",
    )

    pricing_service_url: str = Field(
        default="http://globeco-pricing-service:8083",
        description="Pricing Service base URL",
    )

    portfolio_service_url: str = Field(
        default="http://globeco-portfolio-service:8000",
        description="Portfolio Service base URL",
    )

    security_service_url: str = Field(
        default="http://globeco-security-service:8000",
        description="Security Service base URL",
    )

    order_service_url: str = Field(
        default="http://globeco-order-service:8081",
        description="Order Service base URL",
    )

    # External Service Configuration
    external_service_timeout: int = Field(
        default=10, description="Timeout for external service calls in seconds"
    )

    # Rebalancing Configuration
    rebalancing_max_workers: int = Field(
        default=4,
        description="Maximum parallel workers for multi-portfolio rebalancing",
    )

    optimization_timeout: int = Field(
        default=30, description="Optimization solver timeout in seconds"
    )

    # CORS Configuration
    cors_origins: Union[str, list[str]] = Field(
        default="*", description="Allowed CORS origins"
    )
    cors_allow_credentials: bool = Field(
        default=True, description="Allow CORS credentials"
    )
    cors_allow_methods: Union[str, list[str]] = Field(
        default="*", description="Allowed CORS methods"
    )
    cors_allow_headers: Union[str, list[str]] = Field(
        default="*", description="Allowed CORS headers"
    )

    @field_validator("cors_origins", mode="after")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, list]) -> list[str]:
        """Parse CORS origins from string or list format."""
        if isinstance(v, str):
            # Handle comma-separated values
            if v.startswith("[") and v.endswith("]"):
                # Handle JSON-like format from environment
                import json

                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    # Fallback to comma-separated
                    return [
                        origin.strip().strip('"\'')
                        for origin in v.strip("[]").split(",")
                    ]
            else:
                # Simple comma-separated format
                return [origin.strip() for origin in v.split(",")]
        return v if isinstance(v, list) else [v]

    @field_validator("cors_allow_methods", mode="after")
    @classmethod
    def parse_cors_methods(cls, v: Union[str, list]) -> list[str]:
        """Parse CORS methods from string or list format."""
        if isinstance(v, str):
            return [method.strip() for method in v.split(",")]
        return v if isinstance(v, list) else [v]

    @field_validator("cors_allow_headers", mode="after")
    @classmethod
    def parse_cors_headers(cls, v: Union[str, list]) -> list[str]:
        """Parse CORS headers from string or list format."""
        if isinstance(v, str):
            return [header.strip() for header in v.split(",")]
        return v if isinstance(v, list) else [v]

    # Security Configuration
    secret_key: str = Field(
        default="dev-secret-key-change-in-production",
        description="Secret key for JWT signing",
    )

    # Monitoring Configuration
    enable_metrics: bool = Field(default=True, description="Enable Prometheus metrics")
    metrics_port: int = Field(default=9090, description="Metrics endpoint port")

    # OpenTelemetry Configuration
    otel_collector_grpc_endpoint: str = Field(
        default="otel-collector-collector.monitoring.svc.cluster.local:4317",
        description="OpenTelemetry Collector gRPC endpoint",
    )
    otel_collector_http_endpoint: str = Field(
        default="http://otel-collector-collector.monitoring.svc.cluster.local:4318",
        description="OpenTelemetry Collector HTTP endpoint base URL",
    )
    otel_insecure: bool = Field(
        default=True, description="Use insecure connection for OpenTelemetry gRPC"
    )

    def configure_logging(self) -> None:
        """
        Configure logging based on the log level setting.
        """
        # Debug: Print the actual log level being set
        print(f"[CONFIG] Setting log level to: {self.log_level.upper()}")

        logging.basicConfig(
            level=getattr(logging, self.log_level.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # Debug: Verify the root logger level
        root_logger = logging.getLogger()
        print(
            f"[CONFIG] Root logger level set to: {logging.getLevelName(root_logger.level)}"
        )

        # Debug: Create a test debug message
        logger = logging.getLogger(__name__)
        logger.debug(
            "Debug logging is working - this message should be visible when LOG_LEVEL=DEBUG"
        )

        # Set third-party loggers to WARNING to reduce noise
        logging.getLogger("uvicorn").setLevel(logging.WARNING)
        logging.getLogger("motor").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)


@lru_cache
def get_settings() -> Settings:
    """
    Get cached application settings instance.

    This function uses lru_cache to ensure the settings are loaded only once
    and reused throughout the application lifetime.

    Returns:
        Settings: The application settings instance
    """
    settings = Settings()
    settings.configure_logging()
    return settings
