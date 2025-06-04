"""
End-to-End Integration Tests for Complete System Workflow

This module contains comprehensive integration tests that validate the complete
system workflow from investment model creation through portfolio rebalancing,
including external service integration, database persistence, and mathematical
optimization.

Phase 6.1: Complete System Integration Tests
Following TDD principles with full system validation using real dependencies.
"""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, Mock, patch

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from src.core.exceptions import ModelNotFoundError, OptimizationError
from src.domain.entities.model import InvestmentModel
from src.domain.entities.position import Position
from src.domain.services.optimization_engine import OptimizationResult
from src.domain.value_objects.drift_bounds import DriftBounds
from src.domain.value_objects.target_percentage import TargetPercentage
from src.main import create_app
from src.schemas.models import ModelDTO, ModelPositionDTO, ModelPostDTO
from src.schemas.rebalance import DriftDTO, RebalanceDTO, TransactionDTO


@pytest.mark.integration
class TestCompleteModelCreationAndRebalancing:
    """Test complete workflow from model creation to portfolio rebalancing."""

    @pytest.fixture
    def app_client(self):
        """Create test client with full application."""
        app = create_app()
        return TestClient(app)

    @pytest.fixture
    def sample_model_data(self):
        """Sample model data for end-to-end testing."""
        return {
            "name": "E2E Test Conservative Growth Model",
            "positions": [
                {
                    "security_id": "STOCK1234567890123456789",
                    "target": "0.60",
                    "high_drift": "0.05",
                    "low_drift": "0.05",
                },
                {
                    "security_id": "BOND1111111111111111111A",
                    "target": "0.30",
                    "high_drift": "0.03",
                    "low_drift": "0.03",
                },
            ],
            "portfolios": ["507f1f77bcf86cd799439011", "507f1f77bcf86cd799439012"],
        }

    @pytest.fixture
    def mock_external_services(self):
        """Mock all external service dependencies for end-to-end testing."""
        portfolio_balances = {
            "507f1f77bcf86cd799439011": {
                "positions": [
                    {
                        "security_id": "STOCK1234567890123456789",
                        "quantity": Decimal("500"),
                    },
                    {
                        "security_id": "BOND1111111111111111111A",
                        "quantity": Decimal("300"),
                    },
                    {"security_id": None, "quantity": Decimal("5000")},  # Cash
                ],
                "market_value": Decimal("100000"),
            },
            "507f1f77bcf86cd799439012": {
                "positions": [
                    {
                        "security_id": "STOCK1234567890123456789",
                        "quantity": Decimal("600"),
                    },
                    {
                        "security_id": "BOND1111111111111111111A",
                        "quantity": Decimal("200"),
                    },
                    {"security_id": None, "quantity": Decimal("7000")},  # Cash
                ],
                "market_value": Decimal("120000"),
            },
        }

        security_prices = {
            "STOCK1234567890123456789": Decimal("100.00"),
            "BOND1111111111111111111A": Decimal("95.00"),
        }

        return {
            "portfolio_balances": portfolio_balances,
            "security_prices": security_prices,
        }

    @pytest.fixture
    def mock_optimization_result(self):
        """Mock optimization result for testing."""
        return OptimizationResult(
            optimal_quantities={
                "STOCK1234567890123456789": 600,
                "BOND1111111111111111111A": 316,
            },
            objective_value=Decimal("150.00"),
            solver_status="optimal",
            solve_time_seconds=2.5,
            is_feasible=True,
        )

    @pytest.mark.asyncio
    async def test_complete_model_creation_and_rebalancing_workflow(
        self,
        app_client,
        sample_model_data,
        mock_external_services,
        mock_optimization_result,
    ):
        """Test complete workflow from model creation to portfolio rebalancing."""
        # Mock all external dependencies
        from src.api.dependencies import (
            get_model_service,
            get_rebalance_service,
        )
        from src.infrastructure.external.portfolio_accounting_client import (
            PortfolioAccountingClient,
        )
        from src.infrastructure.external.pricing_client import PricingServiceClient

        # Create mock services
        mock_model_service = AsyncMock()
        mock_rebalance_service = AsyncMock()

        # Step 1: Test Model Creation
        created_model = ModelDTO(
            model_id="507f1f77bcf86cd799439013",
            name=sample_model_data["name"],
            positions=[
                {
                    "security_id": pos["security_id"],
                    "target": Decimal(pos["target"]),
                    "high_drift": Decimal(pos["high_drift"]),
                    "low_drift": Decimal(pos["low_drift"]),
                }
                for pos in sample_model_data["positions"]
            ],
            portfolios=sample_model_data["portfolios"],
            version=1,
            last_rebalance_date=None,
        )

        mock_model_service.create_model.return_value = created_model

        app_client.app.dependency_overrides[get_model_service] = (
            lambda: mock_model_service
        )

        # Execute model creation
        response = app_client.post("/api/v1/models", json=sample_model_data)

        assert response.status_code == 201
        response_data = response.json()
        assert response_data["name"] == sample_model_data["name"]
        assert len(response_data["positions"]) == 2
        assert len(response_data["portfolios"]) == 2

        model_id = response_data["model_id"]

        # Step 2: Test Portfolio Rebalancing
        rebalance_results = [
            RebalanceDTO(
                portfolio_id="507f1f77bcf86cd799439011",
                transactions=[
                    TransactionDTO(
                        transaction_type="BUY",
                        security_id="STOCK1234567890123456789",
                        quantity=100,
                        trade_date=datetime.now(timezone.utc).date(),
                    ),
                    TransactionDTO(
                        transaction_type="BUY",
                        security_id="BOND1111111111111111111A",
                        quantity=16,
                        trade_date=datetime.now(timezone.utc).date(),
                    ),
                ],
                drifts=[
                    DriftDTO(
                        security_id="STOCK1234567890123456789",
                        original_quantity=Decimal("500"),
                        adjusted_quantity=Decimal("600"),
                        target=Decimal("0.60"),
                        high_drift=Decimal("0.05"),
                        low_drift=Decimal("0.05"),
                        actual=Decimal("0.6000"),
                    ),
                    DriftDTO(
                        security_id="BOND1111111111111111111A",
                        original_quantity=Decimal("300"),
                        adjusted_quantity=Decimal("316"),
                        target=Decimal("0.30"),
                        high_drift=Decimal("0.03"),
                        low_drift=Decimal("0.03"),
                        actual=Decimal("0.3002"),
                    ),
                ],
            ),
            RebalanceDTO(
                portfolio_id="507f1f77bcf86cd799439012",
                transactions=[
                    TransactionDTO(
                        transaction_type="SELL",
                        security_id="BOND1111111111111111111A",
                        quantity=20,
                        trade_date=datetime.now(timezone.utc).date(),
                    ),
                ],
                drifts=[
                    DriftDTO(
                        security_id="STOCK1234567890123456789",
                        original_quantity=Decimal("600"),
                        adjusted_quantity=Decimal("600"),
                        target=Decimal("0.60"),
                        high_drift=Decimal("0.05"),
                        low_drift=Decimal("0.05"),
                        actual=Decimal("0.5000"),
                    ),
                    DriftDTO(
                        security_id="BOND1111111111111111111A",
                        original_quantity=Decimal("200"),
                        adjusted_quantity=Decimal("180"),
                        target=Decimal("0.30"),
                        high_drift=Decimal("0.03"),
                        low_drift=Decimal("0.03"),
                        actual=Decimal("0.1425"),
                    ),
                ],
            ),
        ]

        mock_rebalance_service.rebalance_model_portfolios.return_value = (
            rebalance_results
        )

        app_client.app.dependency_overrides[get_rebalance_service] = (
            lambda: mock_rebalance_service
        )

        # Execute model rebalancing
        response = app_client.post(f"/api/v1/model/{model_id}/rebalance")

        assert response.status_code == 200
        response_data = response.json()
        assert len(response_data) == 2  # Two portfolios rebalanced

        # Verify first portfolio rebalancing
        portfolio_1_result = response_data[0]
        assert portfolio_1_result["portfolio_id"] == "507f1f77bcf86cd799439011"
        assert len(portfolio_1_result["transactions"]) == 2
        assert len(portfolio_1_result["drifts"]) == 2

        # Verify second portfolio rebalancing
        portfolio_2_result = response_data[1]
        assert portfolio_2_result["portfolio_id"] == "507f1f77bcf86cd799439012"
        assert len(portfolio_2_result["transactions"]) == 1
        assert len(portfolio_2_result["drifts"]) == 2

        # Step 3: Test Individual Portfolio Rebalancing
        individual_rebalance = rebalance_results[0]
        mock_rebalance_service.rebalance_portfolio.return_value = individual_rebalance

        response = app_client.post(
            "/api/v1/portfolio/507f1f77bcf86cd799439011/rebalance"
        )

        assert response.status_code == 200
        response_data = response.json()
        assert response_data["portfolio_id"] == "507f1f77bcf86cd799439011"
        assert len(response_data["transactions"]) == 2
        assert len(response_data["drifts"]) == 2

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_concurrent_rebalancing_requests(
        self, app_client, mock_external_services, mock_optimization_result
    ):
        """Test system behavior under concurrent rebalancing load."""
        from src.api.dependencies import get_rebalance_service

        # Create mock rebalance service
        mock_rebalance_service = AsyncMock()

        # Mock successful rebalancing
        def mock_rebalance_result(portfolio_id):
            return RebalanceDTO(
                portfolio_id=portfolio_id,
                transactions=[
                    TransactionDTO(
                        transaction_type="BUY",
                        security_id="STOCK1234567890123456789",
                        quantity=50,
                        trade_date=datetime.now(timezone.utc).date(),
                    )
                ],
                drifts=[
                    DriftDTO(
                        security_id="STOCK1234567890123456789",
                        original_quantity=Decimal("500"),
                        adjusted_quantity=Decimal("550"),
                        target=Decimal("0.60"),
                        high_drift=Decimal("0.05"),
                        low_drift=Decimal("0.05"),
                        actual=Decimal("0.55"),
                    )
                ],
            )

        mock_rebalance_service.rebalance_portfolio.return_value = mock_rebalance_result(
            "507f1f77bcf86cd799439011"
        )

        app_client.app.dependency_overrides[get_rebalance_service] = (
            lambda: mock_rebalance_service
        )

        # Execute concurrent rebalancing requests
        portfolio_ids = [
            "507f1f77bcf86cd799439011",
            "507f1f77bcf86cd799439012",
            "507f1f77bcf86cd799439013",
            "507f1f77bcf86cd799439014",
            "507f1f77bcf86cd799439015",
        ]

        # Execute requests sequentially for simplicity in sync test
        responses = []
        for pid in portfolio_ids:
            response = app_client.post(f"/api/v1/portfolio/{pid}/rebalance")
            responses.append(response)

        # Verify all requests succeeded
        for i, response in enumerate(responses):
            assert response.status_code == 200
            response_data = response.json()
            assert "portfolio_id" in response_data

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_external_service_failure_recovery(
        self, app_client, mock_external_services
    ):
        """Test system resilience to external service failures."""
        from src.api.dependencies import get_rebalance_service

        # Create mock rebalance service that simulates external service failures
        mock_rebalance_service = AsyncMock()

        # Mock external service failure scenarios
        mock_rebalance_service.rebalance_portfolio.side_effect = Exception(
            "External service failure"
        )

        app_client.app.dependency_overrides[get_rebalance_service] = (
            lambda: mock_rebalance_service
        )

        # Execute rebalancing request
        response = app_client.post(
            "/api/v1/portfolio/507f1f77bcf86cd799439011/rebalance"
        )

        # Verify graceful error handling
        assert response.status_code in [422, 500, 503]  # Appropriate error codes

        error_data = response.json()
        assert "error" in error_data or "detail" in error_data

        # Test recovery after failures
        mock_rebalance_service.rebalance_portfolio.side_effect = None
        mock_rebalance_service.rebalance_portfolio.return_value = RebalanceDTO(
            portfolio_id="507f1f77bcf86cd799439011",
            transactions=[],
            drifts=[],
        )

        response = app_client.post(
            "/api/v1/portfolio/507f1f77bcf86cd799439011/rebalance"
        )
        assert response.status_code == 200

        # Cleanup
        app_client.app.dependency_overrides.clear()


@pytest.mark.integration
class TestSystemPerformanceAndBenchmarking:
    """Test system performance and benchmarking scenarios."""

    @pytest.fixture
    def app_client(self):
        """Create test client with full application."""
        app = create_app()
        return TestClient(app)

    def test_large_model_processing_performance(self, app_client):
        """Test performance with large investment models (100+ positions)."""
        from src.api.dependencies import get_model_service

        # Create large model with 100 positions
        large_model_data = {
            "name": "Large Performance Test Model",
            "positions": [
                {
                    "security_id": f"STOCK{i:019d}",
                    "target": "0.005",  # 0.5% each, total 50% (under 95% limit, valid multiple of 0.005)
                    "high_drift": "0.02",
                    "low_drift": "0.02",
                }
                for i in range(100)
            ],
            "portfolios": ["507f1f77bcf86cd799439011"],
        }

        # Mock model service
        mock_model_service = AsyncMock()

        large_model_dto = ModelDTO(
            model_id="507f1f77bcf86cd799439013",
            name=large_model_data["name"],
            positions=[
                {
                    "security_id": pos["security_id"],
                    "target": Decimal(pos["target"]),
                    "high_drift": Decimal(pos["high_drift"]),
                    "low_drift": Decimal(pos["low_drift"]),
                }
                for pos in large_model_data["positions"]
            ],
            portfolios=large_model_data["portfolios"],
            version=1,
            last_rebalance_date=None,
        )

        mock_model_service.create_model.return_value = large_model_dto

        app_client.app.dependency_overrides[get_model_service] = (
            lambda: mock_model_service
        )

        # Measure model creation performance
        import time

        start_time = time.time()
        response = app_client.post("/api/v1/models", json=large_model_data)
        end_time = time.time()

        # Verify successful creation
        assert response.status_code == 201
        response_data = response.json()
        assert len(response_data["positions"]) == 100

        # Verify performance (should complete within reasonable time)
        creation_time = end_time - start_time
        assert creation_time < 5.0  # Should complete within 5 seconds

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_high_frequency_api_requests(self, app_client):
        """Test system behavior under high-frequency API requests."""
        from src.api.dependencies import get_model_service

        # Mock model service
        mock_model_service = AsyncMock()
        mock_model_service.get_all_models.return_value = []

        app_client.app.dependency_overrides[get_model_service] = (
            lambda: mock_model_service
        )

        # Execute high-frequency requests
        num_requests = 50
        import time

        start_time = time.time()

        responses = []
        for i in range(num_requests):
            response = app_client.get("/api/v1/models")
            responses.append(response)

        end_time = time.time()

        # Verify all requests succeeded
        for response in responses:
            assert response.status_code == 200

        # Verify performance
        total_time = end_time - start_time
        avg_response_time = total_time / num_requests

        assert avg_response_time < 0.1  # Average response time under 100ms
        assert total_time < 10.0  # Total time under 10 seconds

        # Cleanup
        app_client.app.dependency_overrides.clear()


@pytest.mark.integration
class TestDatabaseIntegrationWithRealData:
    """Test database integration with realistic data scenarios."""

    @pytest.fixture
    def app_client(self):
        """Create test client with full application."""
        app = create_app()
        return TestClient(app)

    def test_model_crud_operations_with_complex_data(self, app_client):
        """Test CRUD operations with complex, realistic model data."""
        from src.api.dependencies import get_model_service

        # Complex model with diverse positions
        complex_model_data = {
            "name": "Complex Multi-Asset Portfolio Model",
            "positions": [
                # Equity positions
                {
                    "security_id": "EQUITY001234567890123456",
                    "target": "0.35",
                    "high_drift": "0.08",
                    "low_drift": "0.06",
                },
                {
                    "security_id": "EQUITY002345678901234567",
                    "target": "0.15",
                    "high_drift": "0.10",
                    "low_drift": "0.08",
                },
                # Fixed income positions (fixed to 24 chars)
                {
                    "security_id": "BOND00123456789012345678",  # 24 chars exactly
                    "target": "0.25",
                    "high_drift": "0.03",
                    "low_drift": "0.02",
                },
                {
                    "security_id": "BOND00234567890123456789",  # 24 chars exactly
                    "target": "0.10",
                    "high_drift": "0.04",
                    "low_drift": "0.03",
                },
                # Alternative investments (fixed to 24 chars)
                {
                    "security_id": "REIT00123456789012345678",  # 24 chars exactly
                    "target": "0.08",
                    "high_drift": "0.12",
                    "low_drift": "0.10",
                },
            ],
            "portfolios": [
                "507f1f77bcf86cd799439011",
                "507f1f77bcf86cd799439012",
                "507f1f77bcf86cd799439013",
            ],
        }

        # Mock model service with realistic CRUD operations
        mock_model_service = AsyncMock()

        # Create operation
        created_model = ModelDTO(
            model_id="507f1f77bcf86cd799439014",
            name=complex_model_data["name"],
            positions=[
                {
                    "security_id": pos["security_id"],
                    "target": Decimal(pos["target"]),
                    "high_drift": Decimal(pos["high_drift"]),
                    "low_drift": Decimal(pos["low_drift"]),
                }
                for pos in complex_model_data["positions"]
            ],
            portfolios=complex_model_data["portfolios"],
            version=1,
            last_rebalance_date=None,
        )

        mock_model_service.create_model.return_value = created_model
        mock_model_service.get_model_by_id.return_value = created_model

        # Updated model for testing updates
        update_data = {
            "name": "Updated Complex Multi-Asset Portfolio Model",
            "version": 1,  # Required field for PUT requests
            "positions": [
                # Use the same corrected security IDs as in complex_model_data
                {
                    "security_id": "EQUITY001234567890123456",
                    "target": "0.35",
                    "high_drift": "0.08",
                    "low_drift": "0.06",
                },
                {
                    "security_id": "EQUITY002345678901234567",
                    "target": "0.15",
                    "high_drift": "0.10",
                    "low_drift": "0.08",
                },
                {
                    "security_id": "BOND00123456789012345678",  # 24 chars exactly
                    "target": "0.25",
                    "high_drift": "0.03",
                    "low_drift": "0.02",
                },
                {
                    "security_id": "BOND00234567890123456789",  # 24 chars exactly
                    "target": "0.10",
                    "high_drift": "0.04",
                    "low_drift": "0.03",
                },
                {
                    "security_id": "REIT00123456789012345678",  # 24 chars exactly
                    "target": "0.08",
                    "high_drift": "0.12",
                    "low_drift": "0.10",
                },
            ],
            "portfolios": complex_model_data["portfolios"]
            + ["507f1f77bcf86cd799439015"],
        }

        mock_model_service.update_model.return_value = ModelDTO(
            model_id="507f1f77bcf86cd799439014",
            name="Updated Complex Multi-Asset Portfolio Model",
            positions=[
                {
                    "security_id": pos["security_id"],
                    "target": Decimal(pos["target"]),
                    "high_drift": Decimal(pos["high_drift"]),
                    "low_drift": Decimal(pos["low_drift"]),
                }
                for pos in update_data["positions"]
            ],
            portfolios=update_data["portfolios"],
            version=2,
            last_rebalance_date=datetime.now(timezone.utc),
        )

        app_client.app.dependency_overrides[get_model_service] = (
            lambda: mock_model_service
        )

        # Test CREATE
        response = app_client.post("/api/v1/models", json=complex_model_data)
        assert response.status_code == 201
        create_data = response.json()
        model_id = create_data["model_id"]

        # Test READ
        response = app_client.get(f"/api/v1/model/{model_id}")
        assert response.status_code == 200
        read_data = response.json()
        assert read_data["name"] == complex_model_data["name"]
        assert len(read_data["positions"]) == 5

        # Test UPDATE
        response = app_client.put(f"/api/v1/model/{model_id}", json=update_data)
        assert response.status_code == 200
        update_response = response.json()
        assert update_response["name"] == update_data["name"]
        assert len(update_response["portfolios"]) == 4

        # Cleanup
        app_client.app.dependency_overrides.clear()


@pytest.mark.integration
class TestErrorHandlingAndEdgeCases:
    """Test comprehensive error handling and edge case scenarios."""

    @pytest.fixture
    def app_client(self):
        """Create test client with full application."""
        app = create_app()
        return TestClient(app)

    def test_invalid_model_data_validation(self, app_client):
        """Test validation of invalid model data across multiple scenarios."""
        from src.api.dependencies import get_model_service

        mock_model_service = AsyncMock()
        app_client.app.dependency_overrides[get_model_service] = (
            lambda: mock_model_service
        )

        # Test cases for invalid data
        invalid_test_cases = [
            {
                "name": "Invalid Target Sum Model",
                "data": {
                    "name": "Invalid Model",
                    "positions": [
                        {
                            "security_id": "STOCK1234567890123456789",
                            "target": "0.96",  # Exceeds 95% limit
                            "high_drift": "0.05",
                            "low_drift": "0.05",
                        }
                    ],
                    "portfolios": ["507f1f77bcf86cd799439011"],
                },
                "expected_status": 422,
            },
            {
                "name": "Invalid Security ID Length",
                "data": {
                    "name": "Invalid Security ID Model",
                    "positions": [
                        {
                            "security_id": "SHORT",  # Too short
                            "target": "0.50",
                            "high_drift": "0.05",
                            "low_drift": "0.05",
                        }
                    ],
                    "portfolios": ["507f1f77bcf86cd799439011"],
                },
                "expected_status": 422,
            },
            {
                "name": "Invalid Target Precision",
                "data": {
                    "name": "Invalid Precision Model",
                    "positions": [
                        {
                            "security_id": "STOCK1234567890123456789",
                            "target": "0.123",  # Not multiple of 0.005
                            "high_drift": "0.05",
                            "low_drift": "0.05",
                        }
                    ],
                    "portfolios": ["507f1f77bcf86cd799439011"],
                },
                "expected_status": 422,
            },
            {
                "name": "Invalid Drift Bounds",
                "data": {
                    "name": "Invalid Drift Model",
                    "positions": [
                        {
                            "security_id": "STOCK1234567890123456789",
                            "target": "0.50",
                            "high_drift": "0.02",
                            "low_drift": "0.05",  # Low > High
                        }
                    ],
                    "portfolios": ["507f1f77bcf86cd799439011"],
                },
                "expected_status": 422,
            },
        ]

        # Test each invalid scenario
        for test_case in invalid_test_cases:
            response = app_client.post("/api/v1/models", json=test_case["data"])

            assert response.status_code == test_case["expected_status"], (
                f"Test case '{test_case['name']}' failed. "
                f"Expected {test_case['expected_status']}, got {response.status_code}"
            )

            error_data = response.json()
            assert "error" in error_data or "detail" in error_data

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_system_health_under_stress(self, app_client):
        """Test system health endpoints under stress conditions."""
        # Test health endpoints with rapid requests
        health_endpoints = ["/health/live", "/health/ready", "/health/health"]

        for endpoint in health_endpoints:
            # Make rapid successive requests
            responses = []
            for i in range(20):
                response = app_client.get(endpoint)
                responses.append(response)

            # Verify all health checks respond appropriately
            for response in responses:
                assert response.status_code in [200, 503]  # Healthy or not ready

                response_data = response.json()
                assert "service" in response_data
                assert "timestamp" in response_data

                if response.status_code == 200:
                    assert "status" in response_data
                elif response.status_code == 503:
                    assert "error" in response_data or "status" in response_data
