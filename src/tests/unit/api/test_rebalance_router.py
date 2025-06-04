"""
Tests for rebalancing API router endpoints.

This module tests the FastAPI router for portfolio rebalancing operations:
- POST /model/{model_id}/rebalance - Rebalance all portfolios in a model
- POST /portfolio/{portfolio_id}/rebalance - Rebalance single portfolio

Tests cover status codes, request/response validation, error scenarios,
optimization failures, and service integration.
"""

from datetime import date
from decimal import Decimal
from typing import List
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.core.exceptions import (
    ExternalServiceError,
    ModelNotFoundError,
    OptimizationError,
    PortfolioNotFoundError,
)
from src.schemas.rebalance import DriftDTO, RebalanceDTO
from src.schemas.transactions import TransactionDTO, TransactionType


@pytest.fixture
def app_client():
    """Create a test client with the full app for dependency injection."""
    from src.main import create_app

    app = create_app()
    return TestClient(app)


@pytest.fixture
def sample_transaction_dto():
    """Sample TransactionDTO for testing."""
    return TransactionDTO(
        transaction_type=TransactionType.BUY,
        security_id="STOCK1234567890123456789",
        quantity=100,
        trade_date=date(2024, 12, 19),
    )


@pytest.fixture
def sample_drift_dto():
    """Sample DriftDTO for testing."""
    return DriftDTO(
        security_id="STOCK1234567890123456789",
        original_quantity=Decimal("500"),
        adjusted_quantity=Decimal("600"),
        target=Decimal("0.25"),
        high_drift=Decimal("0.05"),
        low_drift=Decimal("0.03"),
        actual=Decimal("0.2750"),
    )


@pytest.fixture
def sample_rebalance_dto(sample_transaction_dto, sample_drift_dto):
    """Sample RebalanceDTO for testing."""
    return RebalanceDTO(
        portfolio_id="683b6d88a29ee10e8b499643",
        transactions=[sample_transaction_dto],
        drifts=[sample_drift_dto],
    )


@pytest.mark.unit
class TestRebalanceModelEndpoint:
    """Test POST /model/{model_id}/rebalance endpoint."""

    def test_rebalance_model_success(self, app_client, sample_rebalance_dto):
        """Test successful rebalancing of all portfolios in a model."""
        # Setup
        mock_service = AsyncMock()
        mock_service.rebalance_model_portfolios.return_value = [sample_rebalance_dto]

        # Override the dependency
        from src.api.routers.rebalance import get_rebalance_service

        app_client.app.dependency_overrides[get_rebalance_service] = (
            lambda: mock_service
        )

        # Execute
        response = app_client.post("/api/v1/model/507f1f77bcf86cd799439011/rebalance")

        # Verify
        assert response.status_code == status.HTTP_200_OK

        response_data = response.json()
        assert len(response_data) == 1
        assert response_data[0]["portfolio_id"] == "683b6d88a29ee10e8b499643"
        assert len(response_data[0]["transactions"]) == 1
        assert len(response_data[0]["drifts"]) == 1

        mock_service.rebalance_model_portfolios.assert_called_once_with(
            "507f1f77bcf86cd799439011"
        )

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_rebalance_model_multiple_portfolios(
        self, app_client, sample_rebalance_dto
    ):
        """Test rebalancing of model with multiple portfolios."""
        # Setup - Multiple portfolios
        rebalance_dto_2 = RebalanceDTO(
            portfolio_id="683b6d88a29ee10e8b499644", transactions=[], drifts=[]
        )

        mock_service = AsyncMock()
        mock_service.rebalance_model_portfolios.return_value = [
            sample_rebalance_dto,
            rebalance_dto_2,
        ]

        # Override the dependency
        from src.api.routers.rebalance import get_rebalance_service

        app_client.app.dependency_overrides[get_rebalance_service] = (
            lambda: mock_service
        )

        # Execute
        response = app_client.post("/api/v1/model/507f1f77bcf86cd799439011/rebalance")

        # Verify
        assert response.status_code == status.HTTP_200_OK

        response_data = response.json()
        assert len(response_data) == 2
        assert response_data[0]["portfolio_id"] == "683b6d88a29ee10e8b499643"
        assert response_data[1]["portfolio_id"] == "683b6d88a29ee10e8b499644"

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_rebalance_model_not_found(self, app_client):
        """Test rebalancing with non-existent model."""
        # Setup
        mock_service = AsyncMock()
        mock_service.rebalance_model_portfolios.side_effect = ModelNotFoundError(
            "Model not found"
        )

        # Override the dependency
        from src.api.routers.rebalance import get_rebalance_service

        app_client.app.dependency_overrides[get_rebalance_service] = (
            lambda: mock_service
        )

        # Execute
        response = app_client.post("/api/v1/model/507f1f77bcf86cd799439011/rebalance")

        # Verify
        assert response.status_code == status.HTTP_404_NOT_FOUND

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_rebalance_model_no_portfolios(self, app_client):
        """Test rebalancing model with no associated portfolios."""
        # Setup
        mock_service = AsyncMock()
        mock_service.rebalance_model_portfolios.return_value = []

        # Override the dependency
        from src.api.routers.rebalance import get_rebalance_service

        app_client.app.dependency_overrides[get_rebalance_service] = (
            lambda: mock_service
        )

        # Execute
        response = app_client.post("/api/v1/model/507f1f77bcf86cd799439011/rebalance")

        # Verify
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_rebalance_model_optimization_error(self, app_client):
        """Test handling of optimization errors during model rebalancing."""
        # Setup
        mock_service = AsyncMock()
        mock_service.rebalance_model_portfolios.side_effect = OptimizationError(
            "No feasible solution exists"
        )

        # Override the dependency
        from src.api.routers.rebalance import get_rebalance_service

        app_client.app.dependency_overrides[get_rebalance_service] = (
            lambda: mock_service
        )

        # Execute
        response = app_client.post("/api/v1/model/507f1f77bcf86cd799439011/rebalance")

        # Verify
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_rebalance_model_external_service_error(self, app_client):
        """Test handling of external service errors during rebalancing."""
        # Setup
        mock_service = AsyncMock()
        mock_service.rebalance_model_portfolios.side_effect = ExternalServiceError(
            "Portfolio Accounting Service unavailable"
        )

        # Override the dependency
        from src.api.routers.rebalance import get_rebalance_service

        app_client.app.dependency_overrides[get_rebalance_service] = (
            lambda: mock_service
        )

        # Execute
        response = app_client.post("/api/v1/model/507f1f77bcf86cd799439011/rebalance")

        # Verify
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_rebalance_model_invalid_id_format(self, app_client):
        """Test rebalancing with invalid model ID format."""
        # Execute
        response = app_client.post("/api/v1/model/invalid_id/rebalance")

        # Verify
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_rebalance_model_partial_success(self, app_client, sample_rebalance_dto):
        """Test partial success scenario where some portfolios fail rebalancing."""
        # Setup - Mixed success/failure results
        rebalance_dto_2 = RebalanceDTO(
            portfolio_id="683b6d88a29ee10e8b499644", transactions=[], drifts=[]
        )

        mock_service = AsyncMock()
        mock_service.rebalance_model_portfolios.return_value = [
            sample_rebalance_dto,
            rebalance_dto_2,
        ]

        # Override the dependency
        from src.api.routers.rebalance import get_rebalance_service

        app_client.app.dependency_overrides[get_rebalance_service] = (
            lambda: mock_service
        )

        # Execute
        response = app_client.post("/api/v1/model/507f1f77bcf86cd799439011/rebalance")

        # Verify
        assert response.status_code == status.HTTP_200_OK

        response_data = response.json()
        assert len(response_data) == 2

        # First portfolio has transactions, second doesn't (partial failure)
        assert len(response_data[0]["transactions"]) == 1
        assert len(response_data[1]["transactions"]) == 0

        # Cleanup
        app_client.app.dependency_overrides.clear()


@pytest.mark.unit
class TestRebalancePortfolioEndpoint:
    """Test POST /portfolio/{portfolio_id}/rebalance endpoint."""

    def test_rebalance_portfolio_success(self, app_client, sample_rebalance_dto):
        """Test successful rebalancing of a single portfolio."""
        # Setup
        mock_service = AsyncMock()
        mock_service.rebalance_portfolio.return_value = sample_rebalance_dto

        # Override the dependency
        from src.api.routers.rebalance import get_rebalance_service

        app_client.app.dependency_overrides[get_rebalance_service] = (
            lambda: mock_service
        )

        # Execute
        response = app_client.post(
            "/api/v1/portfolio/683b6d88a29ee10e8b499643/rebalance"
        )

        # Verify
        assert response.status_code == status.HTTP_200_OK

        response_data = response.json()
        assert response_data["portfolio_id"] == "683b6d88a29ee10e8b499643"
        assert len(response_data["transactions"]) == 1
        assert len(response_data["drifts"]) == 1

        mock_service.rebalance_portfolio.assert_called_once_with(
            "683b6d88a29ee10e8b499643"
        )

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_rebalance_portfolio_no_changes_needed(self, app_client):
        """Test portfolio rebalancing when no changes are needed."""
        # Setup
        no_change_rebalance = RebalanceDTO(
            portfolio_id="683b6d88a29ee10e8b499643",
            transactions=[],  # No transactions needed
            drifts=[],  # No drift adjustments needed
        )

        mock_service = AsyncMock()
        mock_service.rebalance_portfolio.return_value = no_change_rebalance

        # Override the dependency
        from src.api.routers.rebalance import get_rebalance_service

        app_client.app.dependency_overrides[get_rebalance_service] = (
            lambda: mock_service
        )

        # Execute
        response = app_client.post(
            "/api/v1/portfolio/683b6d88a29ee10e8b499643/rebalance"
        )

        # Verify
        assert response.status_code == status.HTTP_200_OK

        response_data = response.json()
        assert response_data["portfolio_id"] == "683b6d88a29ee10e8b499643"
        assert response_data["transactions"] == []
        assert response_data["drifts"] == []

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_rebalance_portfolio_not_found(self, app_client):
        """Test rebalancing with non-existent portfolio."""
        # Setup
        mock_service = AsyncMock()
        mock_service.rebalance_portfolio.side_effect = PortfolioNotFoundError(
            "Portfolio not found"
        )

        # Override the dependency
        from src.api.routers.rebalance import get_rebalance_service

        app_client.app.dependency_overrides[get_rebalance_service] = (
            lambda: mock_service
        )

        # Execute
        response = app_client.post(
            "/api/v1/portfolio/683b6d88a29ee10e8b499643/rebalance"
        )

        # Verify
        assert response.status_code == status.HTTP_404_NOT_FOUND

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_rebalance_portfolio_optimization_error(self, app_client):
        """Test handling of optimization errors during portfolio rebalancing."""
        # Setup
        mock_service = AsyncMock()
        mock_service.rebalance_portfolio.side_effect = OptimizationError(
            "No feasible solution exists"
        )

        # Override the dependency
        from src.api.routers.rebalance import get_rebalance_service

        app_client.app.dependency_overrides[get_rebalance_service] = (
            lambda: mock_service
        )

        # Execute
        response = app_client.post(
            "/api/v1/portfolio/683b6d88a29ee10e8b499643/rebalance"
        )

        # Verify
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_rebalance_portfolio_invalid_id_format(self, app_client):
        """Test rebalancing with invalid portfolio ID format."""
        # Execute
        response = app_client.post("/api/v1/portfolio/invalid_id/rebalance")

        # Verify
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_rebalance_portfolio_complex_transactions(self, app_client):
        """Test portfolio rebalancing with multiple transaction types."""
        # Setup - Complex rebalancing with multiple buy/sell transactions
        complex_transactions = [
            TransactionDTO(
                transaction_type=TransactionType.SELL,
                security_id="STOCK1234567890123456789",
                quantity=50,
                trade_date=date(2024, 12, 19),
            ),
            TransactionDTO(
                transaction_type=TransactionType.BUY,
                security_id="BOND1111111111111111111A",
                quantity=75,
                trade_date=date(2024, 12, 19),
            ),
        ]

        complex_drifts = [
            DriftDTO(
                security_id="STOCK1234567890123456789",
                original_quantity=Decimal("100"),
                adjusted_quantity=Decimal("50"),
                target=Decimal("0.20"),
                high_drift=Decimal("0.05"),
                low_drift=Decimal("0.03"),
                actual=Decimal("0.1750"),
            ),
            DriftDTO(
                security_id="BOND1111111111111111111A",
                original_quantity=Decimal("0"),
                adjusted_quantity=Decimal("75"),
                target=Decimal("0.30"),
                high_drift=Decimal("0.02"),
                low_drift=Decimal("0.02"),
                actual=Decimal("0.3000"),
            ),
        ]

        complex_rebalance = RebalanceDTO(
            portfolio_id="683b6d88a29ee10e8b499643",
            transactions=complex_transactions,
            drifts=complex_drifts,
        )

        mock_service = AsyncMock()
        mock_service.rebalance_portfolio.return_value = complex_rebalance

        # Override the dependency
        from src.api.routers.rebalance import get_rebalance_service

        app_client.app.dependency_overrides[get_rebalance_service] = (
            lambda: mock_service
        )

        # Execute
        response = app_client.post(
            "/api/v1/portfolio/683b6d88a29ee10e8b499643/rebalance"
        )

        # Verify
        assert response.status_code == status.HTTP_200_OK

        response_data = response.json()
        assert len(response_data["transactions"]) == 2
        assert len(response_data["drifts"]) == 2

        # Verify transaction types
        assert response_data["transactions"][0]["transaction_type"] == "SELL"
        assert response_data["transactions"][1]["transaction_type"] == "BUY"

        # Cleanup
        app_client.app.dependency_overrides.clear()


@pytest.mark.unit
class TestRebalanceRouterErrorHandling:
    """Test error handling scenarios across rebalancing endpoints."""

    def test_internal_server_error_handling(self, app_client):
        """Test handling of unexpected internal errors."""
        # Setup
        mock_service = AsyncMock()
        mock_service.rebalance_portfolio.side_effect = Exception(
            "Unexpected database error"
        )

        # Override the dependency
        from src.api.routers.rebalance import get_rebalance_service

        app_client.app.dependency_overrides[get_rebalance_service] = (
            lambda: mock_service
        )

        # Execute
        response = app_client.post(
            "/api/v1/portfolio/683b6d88a29ee10e8b499643/rebalance"
        )

        # Verify
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_multiple_external_service_errors(self, app_client):
        """Test handling when multiple external services are down."""
        # Setup
        mock_service = AsyncMock()
        mock_service.rebalance_model_portfolios.side_effect = ExternalServiceError(
            "Multiple external services unavailable"
        )

        # Override the dependency
        from src.api.routers.rebalance import get_rebalance_service

        app_client.app.dependency_overrides[get_rebalance_service] = (
            lambda: mock_service
        )

        # Execute
        response = app_client.post("/api/v1/model/507f1f77bcf86cd799439011/rebalance")

        # Verify
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_path_parameter_validation(self, app_client):
        """Test validation of path parameters (model ID, portfolio ID)."""
        # Test invalid model ID
        response = app_client.post("/api/v1/model/invalid_model_id/rebalance")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # Test invalid portfolio ID
        response = app_client.post("/api/v1/portfolio/invalid_portfolio_id/rebalance")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
