"""
Tests for portfolio data API endpoints.

This module tests the FastAPI router for retrieving portfolio data associated
with specific rebalances:
- GET /api/v1/rebalance/{rebalance_id}/portfolios - Get portfolios for a rebalance

Tests cover success responses, error scenarios, data validation, business logic,
and service integration following the API specification.
"""

from decimal import Decimal
from typing import List
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.core.exceptions import RepositoryError
from src.schemas.rebalance import PortfolioWithPositionsDTO, PositionDTO


@pytest.fixture
def app_client():
    """Create a test client with the full app for dependency injection."""
    from src.main import create_app

    app = create_app()
    return TestClient(app)


@pytest.fixture
def sample_position_dto():
    """Sample PositionDTO for testing."""
    return PositionDTO(
        security_id="68430bfd20f302c879a60286",
        price=Decimal("62.85"),
        original_quantity=Decimal("0.0"),
        adjusted_quantity=Decimal("220.0"),
        original_position_market_value=Decimal("0.0"),
        adjusted_position_market_value=Decimal("13827.0"),
        target=Decimal("0.02"),
        high_drift=Decimal("0.005"),
        low_drift=Decimal("0.005"),
        actual=Decimal("0.01995926445051035"),
        actual_drift=Decimal("0.0020367774744825414"),
    )


@pytest.fixture
def sample_portfolio_dto(sample_position_dto):
    """Sample PortfolioWithPositionsDTO for testing."""
    return PortfolioWithPositionsDTO(
        portfolio_id="68430c0edbfc814369506be3",
        market_value=Decimal("692761.0"),
        cash_before_rebalance=Decimal("35426.93"),
        cash_after_rebalance=Decimal("52583.07"),
        positions=[sample_position_dto],
    )


@pytest.fixture
def multiple_positions_portfolio_dto():
    """Portfolio with multiple positions for comprehensive testing."""
    positions = [
        PositionDTO(
            security_id="68430bfd20f302c879a60286",
            price=Decimal("62.85"),
            original_quantity=Decimal("100.0"),
            adjusted_quantity=Decimal("120.0"),
            original_position_market_value=Decimal("6285.0"),
            adjusted_position_market_value=Decimal("7542.0"),
            target=Decimal("0.15"),
            high_drift=Decimal("0.02"),
            low_drift=Decimal("0.02"),
            actual=Decimal("0.1542"),
            actual_drift=Decimal("0.0042"),
        ),
        PositionDTO(
            security_id="68430bfd20f302c879a60287",
            price=Decimal("45.20"),
            original_quantity=Decimal("200.0"),
            adjusted_quantity=Decimal("150.0"),
            original_position_market_value=Decimal("9040.0"),
            adjusted_position_market_value=Decimal("6780.0"),
            target=Decimal("0.18"),
            high_drift=Decimal("0.03"),
            low_drift=Decimal("0.03"),
            actual=Decimal("0.1680"),
            actual_drift=Decimal("-0.012"),
        ),
    ]

    return PortfolioWithPositionsDTO(
        portfolio_id="68430c0edbfc814369506be4",
        market_value=Decimal("500000.0"),
        cash_before_rebalance=Decimal("25000.0"),
        cash_after_rebalance=Decimal("30000.0"),
        positions=positions,
    )


@pytest.mark.unit
class TestGetRebalancePortfoliosEndpoint:
    """Test GET /api/v1/rebalance/{rebalance_id}/portfolios endpoint."""

    def test_get_portfolios_success_single_portfolio(
        self, app_client, sample_portfolio_dto
    ):
        """Test successful retrieval of portfolios for a rebalance with single portfolio."""
        # Setup
        mock_service = AsyncMock()
        mock_service.get_portfolios_by_rebalance_id.return_value = [
            sample_portfolio_dto
        ]

        # Override the dependency
        from src.api.routers.rebalances import get_rebalance_repository

        app_client.app.dependency_overrides[get_rebalance_repository] = (
            lambda: mock_service
        )

        # Execute
        rebalance_id = "68470f3eb7cf58482e2949ce"
        response = app_client.get(f"/api/v1/rebalance/{rebalance_id}/portfolios")

        # Verify
        assert response.status_code == status.HTTP_200_OK

        response_data = response.json()
        assert len(response_data) == 1

        portfolio = response_data[0]
        assert portfolio["portfolio_id"] == "68430c0edbfc814369506be3"
        assert portfolio["market_value"] == 692761.0
        assert portfolio["cash_before_rebalance"] == 35426.93
        assert portfolio["cash_after_rebalance"] == 52583.07
        assert len(portfolio["positions"]) == 1

        position = portfolio["positions"][0]
        assert position["security_id"] == "68430bfd20f302c879a60286"
        assert position["price"] == 62.85
        assert position["original_quantity"] == 0.0
        assert position["adjusted_quantity"] == 220.0

        mock_service.get_portfolios_by_rebalance_id.assert_called_once_with(
            rebalance_id
        )

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_get_portfolios_success_multiple_portfolios(
        self, app_client, sample_portfolio_dto, multiple_positions_portfolio_dto
    ):
        """Test successful retrieval of multiple portfolios for a rebalance."""
        # Setup
        mock_service = AsyncMock()
        mock_service.get_portfolios_by_rebalance_id.return_value = [
            sample_portfolio_dto,
            multiple_positions_portfolio_dto,
        ]

        # Override the dependency
        from src.api.routers.rebalances import get_rebalance_repository

        app_client.app.dependency_overrides[get_rebalance_repository] = (
            lambda: mock_service
        )

        # Execute
        rebalance_id = "68470f3eb7cf58482e2949ce"
        response = app_client.get(f"/api/v1/rebalance/{rebalance_id}/portfolios")

        # Verify
        assert response.status_code == status.HTTP_200_OK

        response_data = response.json()
        assert len(response_data) == 2

        # Verify first portfolio
        assert response_data[0]["portfolio_id"] == "68430c0edbfc814369506be3"
        assert len(response_data[0]["positions"]) == 1

        # Verify second portfolio
        assert response_data[1]["portfolio_id"] == "68430c0edbfc814369506be4"
        assert len(response_data[1]["positions"]) == 2

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_get_portfolios_empty_result(self, app_client):
        """Test retrieval when rebalance has no portfolios."""
        # Setup
        mock_service = AsyncMock()
        mock_service.get_portfolios_by_rebalance_id.return_value = []

        # Override the dependency
        from src.api.routers.rebalances import get_rebalance_repository

        app_client.app.dependency_overrides[get_rebalance_repository] = (
            lambda: mock_service
        )

        # Execute
        rebalance_id = "68470f3eb7cf58482e2949ce"
        response = app_client.get(f"/api/v1/rebalance/{rebalance_id}/portfolios")

        # Verify
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_get_portfolios_rebalance_not_found(self, app_client):
        """Test retrieval with non-existent rebalance ID."""
        # Setup
        mock_service = AsyncMock()
        mock_service.get_portfolios_by_rebalance_id.return_value = None

        # Override the dependency
        from src.api.routers.rebalances import get_rebalance_repository

        app_client.app.dependency_overrides[get_rebalance_repository] = (
            lambda: mock_service
        )

        # Execute
        rebalance_id = "68470f3eb7cf58482e2949ce"
        response = app_client.get(f"/api/v1/rebalance/{rebalance_id}/portfolios")

        # Verify
        assert response.status_code == status.HTTP_404_NOT_FOUND

        error_data = response.json()
        # Error is nested in detail field per FastAPI structure
        detail = error_data["detail"]
        assert "error" in detail
        assert "Rebalance not found" in detail["error"]
        assert detail["status_code"] == 404

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_get_portfolios_invalid_rebalance_id_format(self, app_client):
        """Test retrieval with invalid rebalance ID format."""
        # Setup - need to override dependencies even for validation errors
        mock_service = AsyncMock()

        # Override the dependency
        from src.api.routers.rebalances import get_rebalance_repository

        app_client.app.dependency_overrides[get_rebalance_repository] = (
            lambda: mock_service
        )

        # Execute with invalid ID
        response = app_client.get("/api/v1/rebalance/invalid_id/portfolios")

        # Verify
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        error_data = response.json()
        # Error is nested in detail field per FastAPI structure
        detail = error_data["detail"]
        assert "error" in detail
        assert "Invalid rebalance ID" in detail["error"]
        assert detail["status_code"] == 400

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_get_portfolios_invalid_rebalance_id_too_short(self, app_client):
        """Test retrieval with rebalance ID that's too short."""
        # Setup
        mock_service = AsyncMock()

        # Override the dependency
        from src.api.routers.rebalances import get_rebalance_repository

        app_client.app.dependency_overrides[get_rebalance_repository] = (
            lambda: mock_service
        )

        # Execute with too short ID
        response = app_client.get("/api/v1/rebalance/123/portfolios")

        # Verify
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_get_portfolios_invalid_rebalance_id_too_long(self, app_client):
        """Test retrieval with rebalance ID that's too long."""
        # Setup
        mock_service = AsyncMock()

        # Override the dependency
        from src.api.routers.rebalances import get_rebalance_repository

        app_client.app.dependency_overrides[get_rebalance_repository] = (
            lambda: mock_service
        )

        # Execute with too long ID
        response = app_client.get(
            "/api/v1/rebalance/68470f3eb7cf58482e2949ce123/portfolios"
        )

        # Verify
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_get_portfolios_database_error(self, app_client):
        """Test handling of database errors."""
        # Setup
        mock_service = AsyncMock()
        mock_service.get_portfolios_by_rebalance_id.side_effect = RepositoryError(
            "Database connection failed", "get_portfolios_by_rebalance_id"
        )

        # Override the dependency
        from src.api.routers.rebalances import get_rebalance_repository

        app_client.app.dependency_overrides[get_rebalance_repository] = (
            lambda: mock_service
        )

        # Execute
        rebalance_id = "68470f3eb7cf58482e2949ce"
        response = app_client.get(f"/api/v1/rebalance/{rebalance_id}/portfolios")

        # Verify
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        error_data = response.json()
        # Error is nested in detail field per FastAPI structure
        detail = error_data["detail"]
        assert "error" in detail
        assert "Internal server error" in detail["error"]
        assert detail["status_code"] == 500

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_get_portfolios_unexpected_error(self, app_client):
        """Test handling of unexpected errors."""
        # Setup
        mock_service = AsyncMock()
        mock_service.get_portfolios_by_rebalance_id.side_effect = Exception(
            "Unexpected error"
        )

        # Override the dependency
        from src.api.routers.rebalances import get_rebalance_repository

        app_client.app.dependency_overrides[get_rebalance_repository] = (
            lambda: mock_service
        )

        # Execute
        rebalance_id = "68470f3eb7cf58482e2949ce"
        response = app_client.get(f"/api/v1/rebalance/{rebalance_id}/portfolios")

        # Verify
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        # Cleanup
        app_client.app.dependency_overrides.clear()


@pytest.mark.unit
class TestPortfolioEndpointDataValidation:
    """Test data validation and business logic for portfolio endpoint."""

    def test_portfolio_data_structure_validation(
        self, app_client, sample_portfolio_dto
    ):
        """Test that returned portfolio data has correct structure."""
        # Setup
        mock_service = AsyncMock()
        mock_service.get_portfolios_by_rebalance_id.return_value = [
            sample_portfolio_dto
        ]

        # Override the dependency
        from src.api.routers.rebalances import get_rebalance_repository

        app_client.app.dependency_overrides[get_rebalance_repository] = (
            lambda: mock_service
        )

        # Execute
        rebalance_id = "68470f3eb7cf58482e2949ce"
        response = app_client.get(f"/api/v1/rebalance/{rebalance_id}/portfolios")

        # Verify structure
        assert response.status_code == status.HTTP_200_OK

        portfolio = response.json()[0]

        # Required portfolio fields
        required_portfolio_fields = [
            "portfolio_id",
            "market_value",
            "cash_before_rebalance",
            "cash_after_rebalance",
            "positions",
        ]
        for field in required_portfolio_fields:
            assert field in portfolio

        # Required position fields
        position = portfolio["positions"][0]
        required_position_fields = [
            "security_id",
            "price",
            "original_quantity",
            "adjusted_quantity",
            "original_position_market_value",
            "adjusted_position_market_value",
            "target",
            "high_drift",
            "low_drift",
            "actual",
            "actual_drift",
        ]
        for field in required_position_fields:
            assert field in position

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_portfolio_with_no_positions(self, app_client):
        """Test portfolio with empty positions array."""
        # Setup
        empty_portfolio = PortfolioWithPositionsDTO(
            portfolio_id="68430c0edbfc814369506be3",
            market_value=Decimal("100000.0"),
            cash_before_rebalance=Decimal("100000.0"),
            cash_after_rebalance=Decimal("100000.0"),
            positions=[],  # Empty positions
        )

        mock_service = AsyncMock()
        mock_service.get_portfolios_by_rebalance_id.return_value = [empty_portfolio]

        # Override the dependency
        from src.api.routers.rebalances import get_rebalance_repository

        app_client.app.dependency_overrides[get_rebalance_repository] = (
            lambda: mock_service
        )

        # Execute
        rebalance_id = "68470f3eb7cf58482e2949ce"
        response = app_client.get(f"/api/v1/rebalance/{rebalance_id}/portfolios")

        # Verify
        assert response.status_code == status.HTTP_200_OK

        portfolio = response.json()[0]
        assert portfolio["positions"] == []
        assert portfolio["market_value"] == 100000.0

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_decimal_precision_handling(self, app_client):
        """Test proper handling of decimal precision in financial data."""
        # Setup portfolio with high-precision decimal values
        high_precision_position = PositionDTO(
            security_id="68430bfd20f302c879a60286",
            price=Decimal("62.8547"),  # 4 decimal places
            original_quantity=Decimal("100.123456"),  # 6 decimal places
            adjusted_quantity=Decimal("120.654321"),  # 6 decimal places
            original_position_market_value=Decimal("6290.98"),
            adjusted_position_market_value=Decimal("7585.47"),
            target=Decimal("0.15000"),  # 5 decimal places
            high_drift=Decimal("0.02500"),  # 5 decimal places
            low_drift=Decimal("0.02500"),  # 5 decimal places
            actual=Decimal("0.15425698"),  # 8 decimal places
            actual_drift=Decimal("0.00425698"),  # 8 decimal places
        )

        precision_portfolio = PortfolioWithPositionsDTO(
            portfolio_id="68430c0edbfc814369506be3",
            market_value=Decimal("692761.123456"),  # 6 decimal places
            cash_before_rebalance=Decimal("35426.9387"),  # 4 decimal places
            cash_after_rebalance=Decimal("52583.0712"),  # 4 decimal places
            positions=[high_precision_position],
        )

        mock_service = AsyncMock()
        mock_service.get_portfolios_by_rebalance_id.return_value = [precision_portfolio]

        # Override the dependency
        from src.api.routers.rebalances import get_rebalance_repository

        app_client.app.dependency_overrides[get_rebalance_repository] = (
            lambda: mock_service
        )

        # Execute
        rebalance_id = "68470f3eb7cf58482e2949ce"
        response = app_client.get(f"/api/v1/rebalance/{rebalance_id}/portfolios")

        # Verify precision is maintained
        assert response.status_code == status.HTTP_200_OK

        portfolio = response.json()[0]
        position = portfolio["positions"][0]

        # Verify high precision values are preserved
        assert position["price"] == 62.8547
        assert position["actual"] == 0.15425698
        assert portfolio["market_value"] == 692761.123456

        # Cleanup
        app_client.app.dependency_overrides.clear()


@pytest.mark.unit
class TestPortfolioEndpointBusinessLogic:
    """Test business logic validation for portfolio endpoint."""

    def test_cash_calculation_consistency(self, app_client):
        """Test that cash changes are mathematically consistent."""
        # Setup portfolio with specific cash values
        consistent_portfolio = PortfolioWithPositionsDTO(
            portfolio_id="68430c0edbfc814369506be3",
            market_value=Decimal("500000.0"),
            cash_before_rebalance=Decimal("50000.0"),  # 10% cash
            cash_after_rebalance=Decimal("25000.0"),  # 5% cash after rebalance
            positions=[],
        )

        mock_service = AsyncMock()
        mock_service.get_portfolios_by_rebalance_id.return_value = [
            consistent_portfolio
        ]

        # Override the dependency
        from src.api.routers.rebalances import get_rebalance_repository

        app_client.app.dependency_overrides[get_rebalance_repository] = (
            lambda: mock_service
        )

        # Execute
        rebalance_id = "68470f3eb7cf58482e2949ce"
        response = app_client.get(f"/api/v1/rebalance/{rebalance_id}/portfolios")

        # Verify
        assert response.status_code == status.HTTP_200_OK

        portfolio = response.json()[0]

        # Calculate cash change
        cash_before = portfolio["cash_before_rebalance"]
        cash_after = portfolio["cash_after_rebalance"]
        cash_change = cash_after - cash_before

        assert cash_change == -25000.0  # Cash decreased by 25k (invested in securities)

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_drift_calculation_validation(self, app_client):
        """Test that drift calculations are mathematically consistent."""
        # Setup position with specific drift values
        drift_position = PositionDTO(
            security_id="68430bfd20f302c879a60286",
            price=Decimal("100.0"),
            original_quantity=Decimal("100.0"),
            adjusted_quantity=Decimal("150.0"),
            original_position_market_value=Decimal("10000.0"),
            adjusted_position_market_value=Decimal("15000.0"),
            target=Decimal("0.20"),  # 20% target
            high_drift=Decimal("0.05"),
            low_drift=Decimal("0.05"),
            actual=Decimal("0.22"),  # 22% actual
            actual_drift=Decimal("0.02"),  # 2% drift (22% - 20%)
        )

        drift_portfolio = PortfolioWithPositionsDTO(
            portfolio_id="68430c0edbfc814369506be3",
            market_value=Decimal("100000.0"),
            cash_before_rebalance=Decimal("10000.0"),
            cash_after_rebalance=Decimal("5000.0"),
            positions=[drift_position],
        )

        mock_service = AsyncMock()
        mock_service.get_portfolios_by_rebalance_id.return_value = [drift_portfolio]

        # Override the dependency
        from src.api.routers.rebalances import get_rebalance_repository

        app_client.app.dependency_overrides[get_rebalance_repository] = (
            lambda: mock_service
        )

        # Execute
        rebalance_id = "68470f3eb7cf58482e2949ce"
        response = app_client.get(f"/api/v1/rebalance/{rebalance_id}/portfolios")

        # Verify drift calculations
        assert response.status_code == status.HTTP_200_OK

        position = response.json()[0]["positions"][0]

        # Verify drift calculation: actual_drift = actual - target
        calculated_drift = position["actual"] - position["target"]
        assert (
            abs(calculated_drift - position["actual_drift"]) < 0.001
        )  # Allow for rounding

        # Cleanup
        app_client.app.dependency_overrides.clear()


@pytest.mark.unit
class TestPortfolioEndpointPerformance:
    """Test performance considerations for portfolio endpoint."""

    def test_large_portfolio_response(self, app_client):
        """Test handling of portfolios with many positions."""
        # Setup portfolio with 50 positions (simulating large portfolio)
        large_positions = []
        for i in range(50):
            position = PositionDTO(
                security_id=f"68430bfd20f302c879a6{i:04d}",
                price=Decimal(f"{50 + i}.25"),
                original_quantity=Decimal(f"{100 + i}.0"),
                adjusted_quantity=Decimal(f"{120 + i}.0"),
                original_position_market_value=Decimal(f"{5000 + i * 100}.0"),
                adjusted_position_market_value=Decimal(f"{6000 + i * 120}.0"),
                target=Decimal("0.02"),  # 2% each
                high_drift=Decimal("0.005"),
                low_drift=Decimal("0.005"),
                actual=Decimal("0.021"),
                actual_drift=Decimal("0.001"),
            )
            large_positions.append(position)

        large_portfolio = PortfolioWithPositionsDTO(
            portfolio_id="68430c0edbfc814369506be3",
            market_value=Decimal("1000000.0"),
            cash_before_rebalance=Decimal("50000.0"),
            cash_after_rebalance=Decimal("50000.0"),
            positions=large_positions,
        )

        mock_service = AsyncMock()
        mock_service.get_portfolios_by_rebalance_id.return_value = [large_portfolio]

        # Override the dependency
        from src.api.routers.rebalances import get_rebalance_repository

        app_client.app.dependency_overrides[get_rebalance_repository] = (
            lambda: mock_service
        )

        # Execute
        rebalance_id = "68470f3eb7cf58482e2949ce"
        response = app_client.get(f"/api/v1/rebalance/{rebalance_id}/portfolios")

        # Verify
        assert response.status_code == status.HTTP_200_OK

        portfolio = response.json()[0]
        assert len(portfolio["positions"]) == 50

        # Verify all positions are properly serialized
        for i, position in enumerate(portfolio["positions"]):
            assert position["security_id"] == f"68430bfd20f302c879a6{i:04d}"

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_multiple_large_portfolios(self, app_client):
        """Test handling of multiple portfolios in single response."""
        # Setup 10 portfolios with 10 positions each
        portfolios = []
        for p in range(10):
            positions = []
            for i in range(10):
                position = PositionDTO(
                    security_id=f"68430bfd20f302c8{p:02d}{i:02d}{p:04d}",
                    price=Decimal(f"{100 + i}.00"),
                    original_quantity=Decimal(f"{50 + i}.0"),
                    adjusted_quantity=Decimal(f"{60 + i}.0"),
                    original_position_market_value=Decimal(f"{5000 + i * 100}.0"),
                    adjusted_position_market_value=Decimal(f"{6000 + i * 100}.0"),
                    target=Decimal("0.10"),
                    high_drift=Decimal("0.02"),
                    low_drift=Decimal("0.02"),
                    actual=Decimal("0.11"),
                    actual_drift=Decimal("0.01"),
                )
                positions.append(position)

            portfolio = PortfolioWithPositionsDTO(
                portfolio_id=f"68430c0edbfc8143695{p:05d}",
                market_value=Decimal(f"{100000 + p * 10000}.0"),
                cash_before_rebalance=Decimal(f"{10000 + p * 1000}.0"),
                cash_after_rebalance=Decimal(f"{10500 + p * 1000}.0"),
                positions=positions,
            )
            portfolios.append(portfolio)

        mock_service = AsyncMock()
        mock_service.get_portfolios_by_rebalance_id.return_value = portfolios

        # Override the dependency
        from src.api.routers.rebalances import get_rebalance_repository

        app_client.app.dependency_overrides[get_rebalance_repository] = (
            lambda: mock_service
        )

        # Execute
        rebalance_id = "68470f3eb7cf58482e2949ce"
        response = app_client.get(f"/api/v1/rebalance/{rebalance_id}/portfolios")

        # Verify
        assert response.status_code == status.HTTP_200_OK

        response_data = response.json()
        assert len(response_data) == 10

        # Verify each portfolio has 10 positions
        for portfolio in response_data:
            assert len(portfolio["positions"]) == 10

        # Cleanup
        app_client.app.dependency_overrides.clear()


@pytest.mark.unit
class TestPortfolioEndpointSecurity:
    """Test security aspects of portfolio endpoint."""

    def test_rebalance_id_injection_protection(self, app_client):
        """Test protection against injection attacks in rebalance_id parameter."""
        # Setup
        mock_service = AsyncMock()

        # Override the dependency
        from src.api.routers.rebalances import get_rebalance_repository

        app_client.app.dependency_overrides[get_rebalance_repository] = (
            lambda: mock_service
        )

        # Test various injection attempts
        injection_attempts = [
            (
                "'; DROP TABLE rebalances; --",
                status.HTTP_400_BAD_REQUEST,
            ),  # Invalid ObjectId format
            (
                "<script>alert('xss')</script>",
                status.HTTP_404_NOT_FOUND,
            ),  # Route not found
            ("../../../etc/passwd", status.HTTP_404_NOT_FOUND),  # Route not found
            (
                "%3Cscript%3Ealert%28%27xss%27%29%3C/script%3E",
                status.HTTP_404_NOT_FOUND,
            ),  # Route not found
            ("1' OR '1'='1", status.HTTP_400_BAD_REQUEST),  # Invalid ObjectId format
        ]

        for malicious_id, expected_status in injection_attempts:
            response = app_client.get(f"/api/v1/rebalance/{malicious_id}/portfolios")
            # Should return appropriate status for invalid input
            assert response.status_code == expected_status

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_path_traversal_protection(self, app_client):
        """Test protection against path traversal attacks."""
        # Setup
        mock_service = AsyncMock()

        # Override the dependency
        from src.api.routers.rebalances import get_rebalance_repository

        app_client.app.dependency_overrides[get_rebalance_repository] = (
            lambda: mock_service
        )

        # Test path traversal attempts
        traversal_attempts = [
            ("../", status.HTTP_404_NOT_FOUND),  # Route not found
            ("../../", status.HTTP_404_NOT_FOUND),  # Route not found
            ("%2e%2e%2f", status.HTTP_404_NOT_FOUND),  # Route not found
            ("..%2f", status.HTTP_404_NOT_FOUND),  # Route not found
            ("%2e%2e/", status.HTTP_404_NOT_FOUND),  # Route not found
        ]

        for traversal_id, expected_status in traversal_attempts:
            response = app_client.get(f"/api/v1/rebalance/{traversal_id}/portfolios")
            assert response.status_code == expected_status

        # Cleanup
        app_client.app.dependency_overrides.clear()
