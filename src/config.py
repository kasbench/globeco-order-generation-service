"""
Configuration module for the Order Generation Service.

This module provides environment-based configuration using Pydantic Settings,
allowing for easy configuration management across different deployment environments.
"""

import logging
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and .env files.

    This class defines all configuration options for the Order Generation Service,
    with sensible defaults for development and environment variable overrides
    for production deployment.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # Service Information
    service_name: str = Field(default="GlobeCo Order Generation Service")
    version: str = Field(default="0.1.0")
    description: str = Field(
        default="Portfolio optimization and order generation microservice"
    )

    # Server Configuration
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8080, description="Server port")
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level")

    # Database Configuration
    database_url: str = Field(
        default="mongodb://localhost:27017", description="MongoDB connection URL"
    )
    database_name: str = Field(
        default="globeco_order_generation", description="Database name"
    )
    database_timeout_ms: int = Field(
        default=5000, description="Database connection timeout in milliseconds"
    )
    database_max_connections: int = Field(
        default=50, description="Maximum database connections in pool"
    )
    database_min_connections: int = Field(
        default=10, description="Minimum database connections in pool"
    )
    database_idle_timeout_ms: int = Field(
        default=300000, description="Database connection idle timeout in milliseconds"
    )

    # External Service URLs
    portfolio_accounting_service_url: str = Field(
        default="http://globeco-portfolio-accounting-service:8087",
        description="Portfolio Accounting Service URL",
    )
    pricing_service_url: str = Field(
        default="http://globeco-pricing-service:8083", description="Pricing Service URL"
    )
    portfolio_service_url: str = Field(
        default="http://globeco-portfolio-service:8000",
        description="Portfolio Service URL",
    )
    security_service_url: str = Field(
        default="http://globeco-security-service:8000",
        description="Security Service URL",
    )

    # External Service Configuration
    external_service_timeout: int = Field(
        default=10, description="External service request timeout in seconds"
    )
    external_service_retries: int = Field(
        default=3, description="Number of retry attempts for external services"
    )

    # Optimization Engine Configuration
    optimization_timeout: int = Field(
        default=30, description="Optimization solver timeout in seconds"
    )
    max_parallel_rebalances: int = Field(
        default=10, description="Maximum number of parallel rebalancing operations"
    )

    # CORS Configuration
    cors_origins: list[str] = Field(default=["*"], description="Allowed CORS origins")
    cors_allow_credentials: bool = Field(
        default=True, description="Allow CORS credentials"
    )
    cors_allow_methods: list[str] = Field(
        default=["*"], description="Allowed CORS methods"
    )
    cors_allow_headers: list[str] = Field(
        default=["*"], description="Allowed CORS headers"
    )

    # Security Configuration
    secret_key: str = Field(
        default="dev-secret-key-change-in-production",
        description="Secret key for JWT signing",
    )

    # Monitoring Configuration
    enable_metrics: bool = Field(default=True, description="Enable Prometheus metrics")
    metrics_port: int = Field(default=9090, description="Metrics endpoint port")

    def configure_logging(self) -> None:
        """
        Configure logging based on the log level setting.
        """
        logging.basicConfig(
            level=getattr(logging, self.log_level.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
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
