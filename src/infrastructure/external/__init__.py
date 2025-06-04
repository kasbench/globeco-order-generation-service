"""
External service clients for GlobeCo Order Generation Service.

This module provides HTTP clients for integrating with external services:
- Portfolio Accounting Service: Portfolio balance and position data
- Pricing Service: Real-time security pricing data
- Portfolio Service: Portfolio metadata and validation
- Security Service: Security metadata and validation

All clients include:
- Circuit breaker pattern for fault tolerance
- Retry logic with exponential backoff
- Comprehensive error handling and logging
- Health check capabilities
"""

from src.infrastructure.external.base_client import (
    BaseServiceClient,
    CircuitBreakerState,
    ExternalServiceClientProtocol,
)
from src.infrastructure.external.portfolio_accounting_client import (
    PortfolioAccountingClient,
)
from src.infrastructure.external.portfolio_client import PortfolioClient
from src.infrastructure.external.pricing_client import PricingServiceClient
from src.infrastructure.external.security_client import SecurityServiceClient

__all__ = [
    # Base client and protocols
    "BaseServiceClient",
    "CircuitBreakerState",
    "ExternalServiceClientProtocol",
    # Service clients
    "PortfolioAccountingClient",
    "PricingServiceClient",
    "PortfolioClient",
    "SecurityServiceClient",
]
