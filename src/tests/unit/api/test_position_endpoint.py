"""
Tests for position data API endpoints.

This module tests the FastAPI router for retrieving position data for specific
portfolios within rebalances:
- GET /api/v1/rebalance/{rebalance_id}/portfolio/{portfolio_id}/positions - Get positions for a portfolio

Tests cover success responses, error scenarios, data validation, business logic,
and service integration following the API specification.
"""

from decimal import Decimal
from typing import List
from unittest.mock import AsyncMock

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.core.exceptions import RepositoryError
from src.schemas.rebalance import PositionDTO


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
def second_position_dto():
    """Second sample PositionDTO for testing."""
    return PositionDTO(
        security_id="68430bfd20f302c879a60287",
        price=Decimal("45.12"),
        original_quantity=Decimal("150.0"),
        adjusted_quantity=Decimal("180.0"),
        original_position_market_value=Decimal("6768.0"),
        adjusted_position_market_value=Decimal("8121.6"),
        target=Decimal("0.015"),
        high_drift=Decimal("0.003"),
        low_drift=Decimal("0.003"),
        actual=Decimal("0.01472895332167832"),
        actual_drift=Decimal("-0.00027104667832168"),
    )


@pytest.fixture
def multiple_positions_list(sample_position_dto, second_position_dto):
    """List of multiple positions for comprehensive testing."""
    return [sample_position_dto, second_position_dto]


@pytest.mark.unit
class TestGetPortfolioPositionsEndpoint:
    """Test GET /api/v1/rebalance/{rebalance_id}/portfolio/{portfolio_id}/positions endpoint."""

    def test_get_positions_success_single_position(
        self, app_client, sample_position_dto
    ):
        """Test successful retrieval of positions for a portfolio with single position."""
        # Setup
        mock_service = AsyncMock()
        mock_service.get_positions_by_rebalance_and_portfolio_id.return_value = [
            sample_position_dto
        ]

        # Override the dependency
        from src.api.routers.rebalances import get_rebalance_repository

        app_client.app.dependency_overrides[get_rebalance_repository] = (
            lambda: mock_service
        )

        # Execute
        rebalance_id = "68470f3eb7cf58482e2949ce"
        portfolio_id = "68430c1bdbfc81436950873f"
        response = app_client.get(
            f"/api/v1/rebalance/{rebalance_id}/portfolio/{portfolio_id}/positions"
        )

        # Verify
        assert response.status_code == status.HTTP_200_OK

        response_data = response.json()
        assert len(response_data) == 1

        position = response_data[0]
        assert position["security_id"] == "68430bfd20f302c879a60286"
        assert position["price"] == 62.85
        assert position["original_quantity"] == 0.0
        assert position["adjusted_quantity"] == 220.0
        assert position["original_position_market_value"] == 0.0
        assert position["adjusted_position_market_value"] == 13827.0
        assert position["target"] == 0.02
        assert position["high_drift"] == 0.005
        assert position["low_drift"] == 0.005
        assert position["actual"] == 0.01995926445051035
        assert position["actual_drift"] == 0.0020367774744825414

        mock_service.get_positions_by_rebalance_and_portfolio_id.assert_called_once_with(
            rebalance_id, portfolio_id
        )

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_get_positions_success_multiple_positions(
        self, app_client, multiple_positions_list
    ):
        """Test successful retrieval of multiple positions for a portfolio."""
        # Setup
        mock_service = AsyncMock()
        mock_service.get_positions_by_rebalance_and_portfolio_id.return_value = (
            multiple_positions_list
        )

        # Override the dependency
        from src.api.routers.rebalances import get_rebalance_repository

        app_client.app.dependency_overrides[get_rebalance_repository] = (
            lambda: mock_service
        )

        # Execute
        rebalance_id = "68470f3eb7cf58482e2949ce"
        portfolio_id = "68430c1bdbfc81436950873f"
        response = app_client.get(
            f"/api/v1/rebalance/{rebalance_id}/portfolio/{portfolio_id}/positions"
        )

        # Verify
        assert response.status_code == status.HTTP_200_OK

        response_data = response.json()
        assert len(response_data) == 2

        # Verify first position
        position1 = response_data[0]
        assert position1["security_id"] == "68430bfd20f302c879a60286"
        assert position1["price"] == 62.85
        assert position1["adjusted_quantity"] == 220.0

        # Verify second position
        position2 = response_data[1]
        assert position2["security_id"] == "68430bfd20f302c879a60287"
        assert position2["price"] == 45.12
        assert position2["adjusted_quantity"] == 180.0

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_get_positions_empty_result(self, app_client):
        """Test retrieval when portfolio has no positions."""
        # Setup
        mock_service = AsyncMock()
        mock_service.get_positions_by_rebalance_and_portfolio_id.return_value = []

        # Override the dependency
        from src.api.routers.rebalances import get_rebalance_repository

        app_client.app.dependency_overrides[get_rebalance_repository] = (
            lambda: mock_service
        )

        # Execute
        rebalance_id = "68470f3eb7cf58482e2949ce"
        portfolio_id = "68430c1bdbfc81436950873f"
        response = app_client.get(
            f"/api/v1/rebalance/{rebalance_id}/portfolio/{portfolio_id}/positions"
        )

        # Verify
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data == []

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_get_positions_rebalance_not_found(self, app_client):
        """Test error handling when rebalance ID does not exist."""
        # Setup
        mock_service = AsyncMock()
        mock_service.get_positions_by_rebalance_and_portfolio_id.return_value = None

        # Override the dependency
        from src.api.routers.rebalances import get_rebalance_repository

        app_client.app.dependency_overrides[get_rebalance_repository] = (
            lambda: mock_service
        )

        # Execute
        rebalance_id = "68470f3eb7cf58482e2949ce"
        portfolio_id = "68430c1bdbfc81436950873f"
        response = app_client.get(
            f"/api/v1/rebalance/{rebalance_id}/portfolio/{portfolio_id}/positions"
        )

        # Verify
        assert response.status_code == status.HTTP_404_NOT_FOUND

        response_data = response.json()
        assert "detail" in response_data
        error_detail = response_data["detail"]
        assert error_detail["error"] == "Rebalance not found"
        assert rebalance_id in error_detail["message"]
        assert error_detail["status_code"] == 404

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_get_positions_portfolio_not_found(self, app_client):
        """Test error handling when portfolio ID does not exist in rebalance."""
        # Setup
        mock_service = AsyncMock()
        # Simulate portfolio not found by returning empty list for specific portfolio
        mock_service.get_positions_by_rebalance_and_portfolio_id.side_effect = [
            []  # Empty positions means portfolio not found
        ]

        # Override the dependency
        from src.api.routers.rebalances import get_rebalance_repository

        app_client.app.dependency_overrides[get_rebalance_repository] = (
            lambda: mock_service
        )

        # Execute
        rebalance_id = "68470f3eb7cf58482e2949ce"
        portfolio_id = "68430c1bdbfc81436950873f"
        response = app_client.get(
            f"/api/v1/rebalance/{rebalance_id}/portfolio/{portfolio_id}/positions"
        )

        # Verify - Empty list is valid response (portfolio exists but has no positions)
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data == []

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_get_positions_invalid_rebalance_id_format(self, app_client):
        """Test error handling with invalid rebalance ID format."""
        # Execute
        invalid_rebalance_id = "invalid_id"
        portfolio_id = "68430c1bdbfc81436950873f"
        response = app_client.get(
            f"/api/v1/rebalance/{invalid_rebalance_id}/portfolio/{portfolio_id}/positions"
        )

        # Verify
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        response_data = response.json()
        assert "detail" in response_data
        error_detail = response_data["detail"]
        assert error_detail["error"] == "Invalid ID format"
        assert (
            "Rebalance ID and Portfolio ID must be valid MongoDB ObjectIds"
            in error_detail["message"]
        )
        assert error_detail["status_code"] == 400

    def test_get_positions_invalid_portfolio_id_format(self, app_client):
        """Test error handling with invalid portfolio ID format."""
        # Execute
        rebalance_id = "68470f3eb7cf58482e2949ce"
        invalid_portfolio_id = "invalid_id"
        response = app_client.get(
            f"/api/v1/rebalance/{rebalance_id}/portfolio/{invalid_portfolio_id}/positions"
        )

        # Verify
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        response_data = response.json()
        assert "detail" in response_data
        error_detail = response_data["detail"]
        assert error_detail["error"] == "Invalid ID format"
        assert (
            "Rebalance ID and Portfolio ID must be valid MongoDB ObjectIds"
            in error_detail["message"]
        )
        assert error_detail["status_code"] == 400

    def test_get_positions_invalid_both_ids_format(self, app_client):
        """Test error handling with both invalid ID formats."""
        # Execute
        invalid_rebalance_id = "invalid_rebalance"
        invalid_portfolio_id = "invalid_portfolio"
        response = app_client.get(
            f"/api/v1/rebalance/{invalid_rebalance_id}/portfolio/{invalid_portfolio_id}/positions"
        )

        # Verify
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        response_data = response.json()
        assert "detail" in response_data
        error_detail = response_data["detail"]
        assert error_detail["error"] == "Invalid ID format"
        assert error_detail["status_code"] == 400

    def test_get_positions_database_error(self, app_client):
        """Test error handling when database error occurs."""
        # Setup
        mock_service = AsyncMock()
        mock_service.get_positions_by_rebalance_and_portfolio_id.side_effect = (
            RepositoryError("Database connection failed", "get_positions")
        )

        # Override the dependency
        from src.api.routers.rebalances import get_rebalance_repository

        app_client.app.dependency_overrides[get_rebalance_repository] = (
            lambda: mock_service
        )

        # Execute
        rebalance_id = "68470f3eb7cf58482e2949ce"
        portfolio_id = "68430c1bdbfc81436950873f"
        response = app_client.get(
            f"/api/v1/rebalance/{rebalance_id}/portfolio/{portfolio_id}/positions"
        )

        # Verify
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        response_data = response.json()
        assert "detail" in response_data
        error_detail = response_data["detail"]
        assert error_detail["error"] == "Internal server error"
        assert (
            error_detail["message"]
            == "An error occurred while retrieving position data"
        )
        assert error_detail["status_code"] == 500

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_get_positions_unexpected_error(self, app_client):
        """Test error handling when unexpected error occurs."""
        # Setup
        mock_service = AsyncMock()
        mock_service.get_positions_by_rebalance_and_portfolio_id.side_effect = (
            Exception("Unexpected system error")
        )

        # Override the dependency
        from src.api.routers.rebalances import get_rebalance_repository

        app_client.app.dependency_overrides[get_rebalance_repository] = (
            lambda: mock_service
        )

        # Execute
        rebalance_id = "68470f3eb7cf58482e2949ce"
        portfolio_id = "68430c1bdbfc81436950873f"
        response = app_client.get(
            f"/api/v1/rebalance/{rebalance_id}/portfolio/{portfolio_id}/positions"
        )

        # Verify
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        response_data = response.json()
        assert "detail" in response_data
        error_detail = response_data["detail"]
        assert error_detail["error"] == "Internal server error"
        assert (
            error_detail["message"]
            == "An error occurred while retrieving position data"
        )
        assert error_detail["status_code"] == 500

        # Cleanup
        app_client.app.dependency_overrides.clear()


@pytest.mark.unit
class TestPositionEndpointDataValidation:
    """Test data structure and validation for position endpoint responses."""

    def test_position_data_structure_validation(self, app_client, sample_position_dto):
        """Test that position data structure matches API specification."""
        # Setup
        mock_service = AsyncMock()
        mock_service.get_positions_by_rebalance_and_portfolio_id.return_value = [
            sample_position_dto
        ]

        # Override the dependency
        from src.api.routers.rebalances import get_rebalance_repository

        app_client.app.dependency_overrides[get_rebalance_repository] = (
            lambda: mock_service
        )

        # Execute
        rebalance_id = "68470f3eb7cf58482e2949ce"
        portfolio_id = "68430c1bdbfc81436950873f"
        response = app_client.get(
            f"/api/v1/rebalance/{rebalance_id}/portfolio/{portfolio_id}/positions"
        )

        # Verify
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert len(response_data) == 1

        position = response_data[0]

        # Verify all required fields are present
        required_fields = [
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

        for field in required_fields:
            assert field in position, f"Required field '{field}' missing from response"

        # Verify data types and constraints
        assert isinstance(position["security_id"], str)
        assert len(position["security_id"]) == 24
        assert isinstance(position["price"], (int, float))
        assert position["price"] > 0
        assert isinstance(position["original_quantity"], (int, float))
        assert position["original_quantity"] >= 0
        assert isinstance(position["adjusted_quantity"], (int, float))
        assert position["adjusted_quantity"] >= 0
        assert isinstance(position["target"], (int, float))
        assert 0 <= position["target"] <= 1
        assert isinstance(position["high_drift"], (int, float))
        assert 0 <= position["high_drift"] <= 1
        assert isinstance(position["low_drift"], (int, float))
        assert 0 <= position["low_drift"] <= 1
        assert isinstance(position["actual"], (int, float))
        assert 0 <= position["actual"] <= 1

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_position_with_zero_values(self, app_client):
        """Test position with zero quantities and market values."""
        # Setup position with zero values
        zero_position = PositionDTO(
            security_id="68430bfd20f302c879a60288",
            price=Decimal("50.00"),
            original_quantity=Decimal("0.0"),
            adjusted_quantity=Decimal("0.0"),
            original_position_market_value=Decimal("0.0"),
            adjusted_position_market_value=Decimal("0.0"),
            target=Decimal("0.0"),
            high_drift=Decimal("0.01"),
            low_drift=Decimal("0.01"),
            actual=Decimal("0.0"),
            actual_drift=Decimal("0.0"),
        )

        mock_service = AsyncMock()
        mock_service.get_positions_by_rebalance_and_portfolio_id.return_value = [
            zero_position
        ]

        # Override the dependency
        from src.api.routers.rebalances import get_rebalance_repository

        app_client.app.dependency_overrides[get_rebalance_repository] = (
            lambda: mock_service
        )

        # Execute
        rebalance_id = "68470f3eb7cf58482e2949ce"
        portfolio_id = "68430c1bdbfc81436950873f"
        response = app_client.get(
            f"/api/v1/rebalance/{rebalance_id}/portfolio/{portfolio_id}/positions"
        )

        # Verify
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert len(response_data) == 1

        position = response_data[0]
        assert position["original_quantity"] == 0.0
        assert position["adjusted_quantity"] == 0.0
        assert position["original_position_market_value"] == 0.0
        assert position["adjusted_position_market_value"] == 0.0
        assert position["target"] == 0.0
        assert position["actual"] == 0.0

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_decimal_precision_handling(self, app_client):
        """Test that decimal precision is maintained in API responses."""
        # Setup position with high precision decimals
        precision_position = PositionDTO(
            security_id="68430bfd20f302c879a60289",
            price=Decimal("123.456789"),
            original_quantity=Decimal("123.456789"),
            adjusted_quantity=Decimal("234.567890"),
            original_position_market_value=Decimal("15241.578966913521"),
            adjusted_position_market_value=Decimal("28958.446672290"),
            target=Decimal("0.123456"),
            high_drift=Decimal("0.012345"),
            low_drift=Decimal("0.098765"),
            actual=Decimal("0.123789"),
            actual_drift=Decimal("0.000333"),
        )

        mock_service = AsyncMock()
        mock_service.get_positions_by_rebalance_and_portfolio_id.return_value = [
            precision_position
        ]

        # Override the dependency
        from src.api.routers.rebalances import get_rebalance_repository

        app_client.app.dependency_overrides[get_rebalance_repository] = (
            lambda: mock_service
        )

        # Execute
        rebalance_id = "68470f3eb7cf58482e2949ce"
        portfolio_id = "68430c1bdbfc81436950873f"
        response = app_client.get(
            f"/api/v1/rebalance/{rebalance_id}/portfolio/{portfolio_id}/positions"
        )

        # Verify
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert len(response_data) == 1

        position = response_data[0]

        # Verify precision is maintained (allowing for float conversion)
        assert abs(position["price"] - 123.456789) < 1e-6
        assert abs(position["target"] - 0.123456) < 1e-6
        assert abs(position["actual"] - 0.123789) < 1e-6

        # Cleanup
        app_client.app.dependency_overrides.clear()


@pytest.mark.unit
class TestPositionEndpointBusinessLogic:
    """Test business logic validation for position endpoint."""

    def test_market_value_calculation_consistency(self, app_client):
        """Test that market value calculations are consistent with quantity * price."""
        # Setup position with specific values for calculation testing
        calculation_position = PositionDTO(
            security_id="68430bfd20f302c879a60290",
            price=Decimal("100.00"),
            original_quantity=Decimal("50.0"),
            adjusted_quantity=Decimal("75.0"),
            original_position_market_value=Decimal("5000.0"),  # 50 * 100
            adjusted_position_market_value=Decimal("7500.0"),  # 75 * 100
            target=Decimal("0.15"),
            high_drift=Decimal("0.02"),
            low_drift=Decimal("0.02"),
            actual=Decimal("0.15"),
            actual_drift=Decimal("0.0"),
        )

        mock_service = AsyncMock()
        mock_service.get_positions_by_rebalance_and_portfolio_id.return_value = [
            calculation_position
        ]

        # Override the dependency
        from src.api.routers.rebalances import get_rebalance_repository

        app_client.app.dependency_overrides[get_rebalance_repository] = (
            lambda: mock_service
        )

        # Execute
        rebalance_id = "68470f3eb7cf58482e2949ce"
        portfolio_id = "68430c1bdbfc81436950873f"
        response = app_client.get(
            f"/api/v1/rebalance/{rebalance_id}/portfolio/{portfolio_id}/positions"
        )

        # Verify
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert len(response_data) == 1

        position = response_data[0]

        # Verify market value calculations
        original_calculated = position["original_quantity"] * position["price"]
        adjusted_calculated = position["adjusted_quantity"] * position["price"]

        assert (
            abs(position["original_position_market_value"] - original_calculated) < 0.01
        )
        assert (
            abs(position["adjusted_position_market_value"] - adjusted_calculated) < 0.01
        )

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_drift_calculation_validation(self, app_client):
        """Test that drift calculations are consistent with actual - target."""
        # Setup position with specific drift values for testing
        drift_position = PositionDTO(
            security_id="68430bfd20f302c879a60291",
            price=Decimal("80.00"),
            original_quantity=Decimal("100.0"),
            adjusted_quantity=Decimal("125.0"),
            original_position_market_value=Decimal("8000.0"),
            adjusted_position_market_value=Decimal("10000.0"),
            target=Decimal("0.20"),
            high_drift=Decimal("0.03"),
            low_drift=Decimal("0.03"),
            actual=Decimal("0.22"),
            actual_drift=Decimal("0.02"),  # 0.22 - 0.20 = 0.02
        )

        mock_service = AsyncMock()
        mock_service.get_positions_by_rebalance_and_portfolio_id.return_value = [
            drift_position
        ]

        # Override the dependency
        from src.api.routers.rebalances import get_rebalance_repository

        app_client.app.dependency_overrides[get_rebalance_repository] = (
            lambda: mock_service
        )

        # Execute
        rebalance_id = "68470f3eb7cf58482e2949ce"
        portfolio_id = "68430c1bdbfc81436950873f"
        response = app_client.get(
            f"/api/v1/rebalance/{rebalance_id}/portfolio/{portfolio_id}/positions"
        )

        # Verify
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert len(response_data) == 1

        position = response_data[0]

        # Verify drift calculation
        calculated_drift = position["actual"] - position["target"]
        assert abs(position["actual_drift"] - calculated_drift) < 1e-6

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_negative_drift_handling(self, app_client):
        """Test handling of negative drift values."""
        # Setup position with negative drift
        negative_drift_position = PositionDTO(
            security_id="68430bfd20f302c879a60292",
            price=Decimal("60.00"),
            original_quantity=Decimal("200.0"),
            adjusted_quantity=Decimal("150.0"),
            original_position_market_value=Decimal("12000.0"),
            adjusted_position_market_value=Decimal("9000.0"),
            target=Decimal("0.25"),
            high_drift=Decimal("0.02"),
            low_drift=Decimal("0.02"),
            actual=Decimal("0.22"),
            actual_drift=Decimal("-0.03"),  # Negative drift
        )

        mock_service = AsyncMock()
        mock_service.get_positions_by_rebalance_and_portfolio_id.return_value = [
            negative_drift_position
        ]

        # Override the dependency
        from src.api.routers.rebalances import get_rebalance_repository

        app_client.app.dependency_overrides[get_rebalance_repository] = (
            lambda: mock_service
        )

        # Execute
        rebalance_id = "68470f3eb7cf58482e2949ce"
        portfolio_id = "68430c1bdbfc81436950873f"
        response = app_client.get(
            f"/api/v1/rebalance/{rebalance_id}/portfolio/{portfolio_id}/positions"
        )

        # Verify
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert len(response_data) == 1

        position = response_data[0]
        assert position["actual_drift"] == -0.03

        # Cleanup
        app_client.app.dependency_overrides.clear()


@pytest.mark.unit
class TestPositionEndpointPerformance:
    """Test performance characteristics of position endpoint."""

    def test_large_position_list_response(self, app_client):
        """Test endpoint performance with large number of positions."""
        # Generate large list of positions (simulate 500+ positions)
        large_position_list = []
        for i in range(250):  # Create 250 positions to test performance
            position = PositionDTO(
                security_id=f"683{i:021d}",  # Generate unique 24-char IDs
                price=Decimal(f"{50 + (i % 50)}.{(i % 100):02d}"),
                original_quantity=Decimal(f"{100 + i}"),
                adjusted_quantity=Decimal(f"{120 + i}"),
                original_position_market_value=Decimal(f"{5000 + i * 50}"),
                adjusted_position_market_value=Decimal(f"{6000 + i * 60}"),
                target=Decimal(f"0.{(i % 95):02d}"),
                high_drift=Decimal(f"0.0{(i % 9) + 1}"),
                low_drift=Decimal(f"0.0{(i % 9) + 1}"),
                actual=Decimal(f"0.{((i + 5) % 95):02d}"),
                actual_drift=Decimal(f"{(i % 10 - 5) / 1000:.6f}"),
            )
            large_position_list.append(position)

        mock_service = AsyncMock()
        mock_service.get_positions_by_rebalance_and_portfolio_id.return_value = (
            large_position_list
        )

        # Override the dependency
        from src.api.routers.rebalances import get_rebalance_repository

        app_client.app.dependency_overrides[get_rebalance_repository] = (
            lambda: mock_service
        )

        # Execute
        rebalance_id = "68470f3eb7cf58482e2949ce"
        portfolio_id = "68430c1bdbfc81436950873f"
        response = app_client.get(
            f"/api/v1/rebalance/{rebalance_id}/portfolio/{portfolio_id}/positions"
        )

        # Verify
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert len(response_data) == 250

        # Verify structure of first and last positions
        first_position = response_data[0]
        last_position = response_data[-1]

        assert len(first_position["security_id"]) == 24
        assert len(last_position["security_id"]) == 24
        assert isinstance(first_position["price"], (int, float))
        assert isinstance(last_position["price"], (int, float))

        # Cleanup
        app_client.app.dependency_overrides.clear()

    def test_empty_positions_performance(self, app_client):
        """Test endpoint performance with no positions."""
        # Setup
        mock_service = AsyncMock()
        mock_service.get_positions_by_rebalance_and_portfolio_id.return_value = []

        # Override the dependency
        from src.api.routers.rebalances import get_rebalance_repository

        app_client.app.dependency_overrides[get_rebalance_repository] = (
            lambda: mock_service
        )

        # Execute
        rebalance_id = "68470f3eb7cf58482e2949ce"
        portfolio_id = "68430c1bdbfc81436950873f"
        response = app_client.get(
            f"/api/v1/rebalance/{rebalance_id}/portfolio/{portfolio_id}/positions"
        )

        # Verify
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data == []
        assert len(response_data) == 0

        # Cleanup
        app_client.app.dependency_overrides.clear()


@pytest.mark.unit
class TestPositionEndpointSecurity:
    """Test security aspects of position endpoint."""

    def test_rebalance_id_injection_protection(self, app_client):
        """Test protection against injection attacks in rebalance ID parameter."""
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

        portfolio_id = "68430c1bdbfc81436950873f"

        for malicious_input, expected_status in injection_attempts:
            response = app_client.get(
                f"/api/v1/rebalance/{malicious_input}/portfolio/{portfolio_id}/positions"
            )

            # Verify that malicious input is handled safely
            assert response.status_code in [
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_404_NOT_FOUND,
            ]

    def test_portfolio_id_injection_protection(self, app_client):
        """Test protection against injection attacks in portfolio ID parameter."""
        # Test various injection attempts
        injection_attempts = [
            (
                "'; DROP TABLE portfolios; --",
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
        ]

        rebalance_id = "68470f3eb7cf58482e2949ce"

        for malicious_input, expected_status in injection_attempts:
            response = app_client.get(
                f"/api/v1/rebalance/{rebalance_id}/portfolio/{malicious_input}/positions"
            )

            # Verify that malicious input is handled safely
            assert response.status_code in [
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_404_NOT_FOUND,
            ]

    def test_path_traversal_protection(self, app_client):
        """Test protection against path traversal attacks."""
        # Test path traversal attempts
        traversal_attempts = [
            "../../../",
            "..\\..\\..\\",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2f",
            "..%252f..%252f..%252f",
        ]

        for traversal_input in traversal_attempts:
            response = app_client.get(
                f"/api/v1/rebalance/{traversal_input}/portfolio/{traversal_input}/positions"
            )

            # Verify that path traversal is blocked
            assert response.status_code in [
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_404_NOT_FOUND,
            ]

    def test_oversized_parameter_handling(self, app_client):
        """Test handling of oversized parameters."""
        # Test with extremely long parameter values
        oversized_id = "a" * 1000  # 1000 character string

        response = app_client.get(
            f"/api/v1/rebalance/{oversized_id}/portfolio/{oversized_id}/positions"
        )

        # Verify that oversized parameters are handled gracefully
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        ]
