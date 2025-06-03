"""
Global test configuration and fixtures for the Order Generation Service.

This module provides shared fixtures and test configuration that can be used
across all test modules. It includes database fixtures, external service mocks,
and sample test data.
"""

import asyncio
import os
from decimal import Decimal
from typing import AsyncGenerator, Dict, List
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from testcontainers.mongodb import MongoDbContainer

from src.config import Settings, get_settings
from src.main import create_app


# Test settings override
class TestSettings(Settings):
    """Test-specific settings with safe defaults."""
    
    database_name: str = "test-order-generation"
    debug: bool = True
    log_level: str = "DEBUG"
    optimization_timeout: int = 5  # Shorter timeout for tests
    external_service_timeout: int = 1  # Shorter timeout for tests
    

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def mongodb_container():
    """Start a MongoDB test container for integration tests."""
    if os.getenv("SKIP_MONGODB_TESTS"):
        pytest.skip("MongoDB tests skipped")
    
    with MongoDbContainer("mongo:8.0") as mongodb:
        yield mongodb


@pytest.fixture(scope="session")
async def test_database_url(mongodb_container):
    """Get the test database URL from the MongoDB container."""
    return mongodb_container.get_connection_url()


@pytest.fixture
async def test_settings(test_database_url):
    """Create test settings with MongoDB container URL."""
    settings = TestSettings(database_url=test_database_url)
    return settings


@pytest.fixture
async def test_db_client(test_settings: TestSettings) -> AsyncGenerator[AsyncIOMotorClient, None]:
    """Create a test database client."""
    client = AsyncIOMotorClient(test_settings.database_url)
    try:
        yield client
    finally:
        await client.close()


@pytest.fixture
async def test_database(test_db_client: AsyncIOMotorClient, test_settings: TestSettings) -> AsyncGenerator[AsyncIOMotorDatabase, None]:
    """Create a clean test database for each test."""
    database = test_db_client[test_settings.database_name]
    
    # Clean up any existing data
    collection_names = await database.list_collection_names()
    for collection_name in collection_names:
        await database[collection_name].drop()
    
    yield database
    
    # Clean up after test
    collection_names = await database.list_collection_names()
    for collection_name in collection_names:
        await database[collection_name].drop()


@pytest.fixture
def mock_external_services():
    """Mock all external service clients."""
    mocks = {
        "portfolio_accounting_client": AsyncMock(),
        "pricing_client": AsyncMock(),
        "portfolio_client": AsyncMock(),
        "security_client": AsyncMock(),
    }
    
    # Configure default return values
    mocks["portfolio_accounting_client"].get_portfolio_balances.return_value = []
    mocks["pricing_client"].get_security_prices.return_value = {}
    mocks["portfolio_client"].get_portfolio.return_value = {"id": "test", "name": "Test Portfolio"}
    mocks["security_client"].get_security.return_value = {"id": "test", "name": "Test Security"}
    
    return mocks


@pytest.fixture
def sample_portfolio_balances():
    """Sample portfolio balance data for testing."""
    return [
        {
            "securityId": "683b6b9620f302c879a5fef4",
            "quantity": 100,
            "marketValue": Decimal("10000.00"),
        },
        {
            "securityId": "683b6b9620f302c879a5fef5",
            "quantity": 50,
            "marketValue": Decimal("7500.00"),
        },
        {
            "cash": True,
            "quantity": 1,
            "marketValue": Decimal("2500.00"),
        }
    ]


@pytest.fixture
def sample_security_prices():
    """Sample security price data for testing."""
    return {
        "683b6b9620f302c879a5fef4": Decimal("100.00"),
        "683b6b9620f302c879a5fef5": Decimal("150.00"),
    }


@pytest.fixture
def sample_investment_model():
    """Sample investment model for testing."""
    return {
        "name": "Test Growth Model",
        "positions": [
            {
                "securityId": "683b6b9620f302c879a5fef4",
                "target": Decimal("0.60"),
                "highDrift": Decimal("0.05"),
                "lowDrift": Decimal("0.05"),
            },
            {
                "securityId": "683b6b9620f302c879a5fef5",
                "target": Decimal("0.35"),
                "highDrift": Decimal("0.03"),
                "lowDrift": Decimal("0.03"),
            }
        ],
        "portfolios": ["683b6d88a29ee10e8b499643"],
    }


@pytest.fixture
def sample_investment_models():
    """Multiple sample investment models for testing."""
    return [
        {
            "name": "Conservative Model",
            "positions": [
                {
                    "securityId": "683b6b9620f302c879a5fef4",
                    "target": Decimal("0.70"),
                    "highDrift": Decimal("0.05"),
                    "lowDrift": Decimal("0.05"),
                },
                {
                    "securityId": "683b6b9620f302c879a5fef5",
                    "target": Decimal("0.25"),
                    "highDrift": Decimal("0.03"),
                    "lowDrift": Decimal("0.03"),
                }
            ],
            "portfolios": ["683b6d88a29ee10e8b499643"],
        },
        {
            "name": "Aggressive Model", 
            "positions": [
                {
                    "securityId": "683b6b9620f302c879a5fef4",
                    "target": Decimal("0.40"),
                    "highDrift": Decimal("0.10"),
                    "lowDrift": Decimal("0.10"),
                },
                {
                    "securityId": "683b6b9620f302c879a5fef5", 
                    "target": Decimal("0.55"),
                    "highDrift": Decimal("0.08"),
                    "lowDrift": Decimal("0.08"),
                }
            ],
            "portfolios": ["683b6d88a29ee10e8b499644"],
        }
    ]


@pytest.fixture
async def test_app(test_settings: TestSettings):
    """Create a test FastAPI application."""
    # Override settings for testing
    def get_test_settings():
        return test_settings
    
    app = create_app()
    app.dependency_overrides[get_settings] = get_test_settings
    
    yield app
    
    # Clean up
    app.dependency_overrides.clear()


@pytest.fixture
async def test_client(test_app):
    """Create a test client for the FastAPI application."""
    with TestClient(test_app) as client:
        yield client


@pytest.fixture 
async def async_test_client(test_app):
    """Create an async test client for the FastAPI application."""
    async with AsyncClient(app=test_app, base_url="http://testserver") as client:
        yield client


# Mathematical test fixtures
@pytest.fixture
def simple_optimization_problem():
    """Simple optimization problem for mathematical validation."""
    return {
        "current_quantities": [100, 50],
        "target_percentages": [0.6, 0.35],
        "prices": [100.0, 150.0],
        "market_value": 20000.0,
        "low_drifts": [0.05, 0.03],
        "high_drifts": [0.05, 0.03],
    }


@pytest.fixture
def complex_optimization_problem():
    """Complex optimization problem with many positions."""
    num_positions = 20
    return {
        "current_quantities": [100] * num_positions,
        "target_percentages": [0.04] * num_positions,  # 20 positions at 4% each = 80%, 20% cash
        "prices": [50.0 + i * 10 for i in range(num_positions)],
        "market_value": 100000.0,
        "low_drifts": [0.02] * num_positions,
        "high_drifts": [0.02] * num_positions,
    }


# Pytest markers for organizing tests
@pytest.fixture(autouse=True)
def add_markers(request):
    """Automatically add markers based on test file location."""
    if "unit" in request.fspath.strpath:
        request.node.add_marker(pytest.mark.unit)
    elif "integration" in request.fspath.strpath:
        request.node.add_marker(pytest.mark.integration)


# Test utilities
class TestUtils:
    """Utility class for common test operations."""
    
    @staticmethod
    def assert_decimal_equal(actual: Decimal, expected: Decimal, places: int = 4):
        """Assert that two decimal values are equal within specified precision."""
        assert abs(actual - expected) < Decimal(f"1e-{places}"), f"Expected {expected}, got {actual}"
    
    @staticmethod
    def assert_optimization_constraints_satisfied(
        quantities: List[int], 
        prices: List[Decimal], 
        target_percentages: List[Decimal],
        market_value: Decimal,
        low_drifts: List[Decimal],
        high_drifts: List[Decimal]
    ):
        """Assert that optimization result satisfies all constraints."""
        for i, (qty, price, target, low_drift, high_drift) in enumerate(
            zip(quantities, prices, target_percentages, low_drifts, high_drifts)
        ):
            position_value = qty * price
            target_value = market_value * target
            lower_bound = market_value * (target - low_drift)
            upper_bound = market_value * (target + high_drift)
            
            assert lower_bound <= position_value <= upper_bound, (
                f"Position {i} constraint violated: "
                f"value={position_value}, bounds=[{lower_bound}, {upper_bound}]"
            )


@pytest.fixture
def test_utils():
    """Provide test utilities."""
    return TestUtils 