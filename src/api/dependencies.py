"""
FastAPI dependency injection configuration.

This module provides dependency injection setup for all service layers,
connecting the API layer to the application services, domain layer, and infrastructure.
"""

from functools import lru_cache
from typing import AsyncGenerator

from fastapi import Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.config import get_settings
from src.core.mappers import ModelMapper, RebalanceMapper
from src.core.services.model_service import ModelService
from src.core.services.rebalance_service import RebalanceService
from src.domain.services.implementations.portfolio_drift_calculator import (
    PortfolioDriftCalculator,
)
from src.domain.services.implementations.portfolio_validation_service import (
    PortfolioValidationService,
)
from src.infrastructure.database.database import get_database
from src.infrastructure.database.repositories.model_repository import (
    MongoModelRepository,
)
from src.infrastructure.database.repositories.rebalance_repository import (
    MongoRebalanceRepository,
)
from src.infrastructure.external.portfolio_accounting_client import (
    PortfolioAccountingClient,
)
from src.infrastructure.external.portfolio_client import PortfolioClient
from src.infrastructure.external.pricing_client import PricingServiceClient
from src.infrastructure.external.security_client import SecurityServiceClient
from src.infrastructure.optimization.cvxpy_solver import CVXPYOptimizationEngine

# External Service Clients


@lru_cache()
def get_security_client() -> SecurityServiceClient:
    """Get Security Service client."""
    settings = get_settings()
    return SecurityServiceClient(
        base_url=settings.security_service_url,
        timeout=settings.external_service_timeout,
    )


def get_pricing_client(
    security_client: SecurityServiceClient = Depends(get_security_client),
) -> PricingServiceClient:
    """Get Pricing Service client."""
    settings = get_settings()
    return PricingServiceClient(
        base_url=settings.pricing_service_url,
        timeout=settings.external_service_timeout,
        security_client=security_client,
    )


@lru_cache()
def get_portfolio_client() -> PortfolioClient:
    """Get Portfolio Service client."""
    settings = get_settings()
    return PortfolioClient(
        base_url=settings.portfolio_service_url,
        timeout=settings.external_service_timeout,
    )


def get_portfolio_accounting_client(
    security_client: SecurityServiceClient = Depends(get_security_client),
    pricing_client: PricingServiceClient = Depends(get_pricing_client),
) -> PortfolioAccountingClient:
    """Get Portfolio Accounting Service client."""
    settings = get_settings()
    client = PortfolioAccountingClient(
        base_url=settings.portfolio_accounting_service_url,
        timeout=settings.external_service_timeout,
    )
    # Set external service clients for market value calculations
    client._set_external_clients(security_client, pricing_client)
    return client


# Domain Services


@lru_cache()
def get_optimization_engine() -> CVXPYOptimizationEngine:
    """Get optimization engine implementation."""
    settings = get_settings()
    return CVXPYOptimizationEngine(default_timeout=settings.optimization_timeout)


@lru_cache()
def get_drift_calculator() -> PortfolioDriftCalculator:
    """Get drift calculator implementation."""
    return PortfolioDriftCalculator()


@lru_cache()
def get_validation_service() -> PortfolioValidationService:
    """Get validation service implementation."""
    return PortfolioValidationService()


# Repositories


def get_model_repository(
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> MongoModelRepository:
    """Get model repository implementation."""
    return MongoModelRepository()


def get_rebalance_repository(
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> MongoRebalanceRepository:
    """Get rebalance repository implementation."""
    return MongoRebalanceRepository()


# Mappers


@lru_cache()
def get_model_mapper() -> ModelMapper:
    """Get model mapper."""
    return ModelMapper()


@lru_cache()
def get_rebalance_mapper() -> RebalanceMapper:
    """Get rebalance mapper."""
    return RebalanceMapper()


# Application Services


def get_model_service(
    model_repository: MongoModelRepository = Depends(get_model_repository),
    validation_service: PortfolioValidationService = Depends(get_validation_service),
    model_mapper: ModelMapper = Depends(get_model_mapper),
) -> ModelService:
    """Get model service."""
    return ModelService(
        model_repository=model_repository,
        validation_service=validation_service,
        model_mapper=model_mapper,
    )


def get_rebalance_service(
    model_repository: MongoModelRepository = Depends(get_model_repository),
    rebalance_repository: MongoRebalanceRepository = Depends(get_rebalance_repository),
    optimization_engine: CVXPYOptimizationEngine = Depends(get_optimization_engine),
    drift_calculator: PortfolioDriftCalculator = Depends(get_drift_calculator),
    portfolio_accounting_client: PortfolioAccountingClient = Depends(
        get_portfolio_accounting_client
    ),
    pricing_client: PricingServiceClient = Depends(get_pricing_client),
    rebalance_mapper: RebalanceMapper = Depends(get_rebalance_mapper),
) -> RebalanceService:
    """Get rebalance service."""
    settings = get_settings()
    return RebalanceService(
        model_repository=model_repository,
        rebalance_repository=rebalance_repository,
        optimization_engine=optimization_engine,
        drift_calculator=drift_calculator,
        portfolio_accounting_client=portfolio_accounting_client,
        pricing_client=pricing_client,
        rebalance_mapper=rebalance_mapper,
        max_workers=settings.rebalancing_max_workers,
    )
