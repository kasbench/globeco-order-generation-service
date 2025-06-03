"""
Tests for Portfolio Validation Service implementation.

This module tests the concrete implementation of the ValidationService interface,
focusing on business rule validation and input validation accuracy.

Following TDD principles, these tests define the expected behavior for
the actual validation service implementation.
"""

from decimal import Decimal

import pytest
from bson import ObjectId

from src.core.exceptions import BusinessRuleViolationError, ValidationError
from src.domain.entities.model import InvestmentModel
from src.domain.entities.position import Position
from src.domain.services.implementations.portfolio_validation_service import (
    PortfolioValidationService,
)
from src.domain.value_objects.drift_bounds import DriftBounds
from src.domain.value_objects.target_percentage import TargetPercentage


@pytest.mark.unit
class TestPortfolioValidationServiceImplementation:
    """Test concrete Portfolio Validation Service implementation."""

    @pytest.fixture
    def validation_service(self) -> PortfolioValidationService:
        """Create a portfolio validation service instance."""
        return PortfolioValidationService()

    @pytest.fixture
    def valid_model(self) -> InvestmentModel:
        """Create a valid investment model for testing."""
        return InvestmentModel(
            model_id=ObjectId(),
            name="Valid Model",
            positions=[
                Position(
                    security_id="STOCK1234567890123456789",
                    target=TargetPercentage(Decimal("0.30")),
                    drift_bounds=DriftBounds(
                        low_drift=Decimal("0.02"), high_drift=Decimal("0.03")
                    ),
                ),
                Position(
                    security_id="STOCK9876543210987654321",
                    target=TargetPercentage(Decimal("0.25")),
                    drift_bounds=DriftBounds(
                        low_drift=Decimal("0.015"), high_drift=Decimal("0.025")
                    ),
                ),
            ],
            portfolios=["portfolio1", "portfolio2"],
            version=1,
        )

    @pytest.mark.asyncio
    async def test_validate_model_success(self, validation_service, valid_model):
        """Test successful model validation."""
        # Act
        result = await validation_service.validate_model(valid_model)

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_model_target_sum_exceeds_95_percent(
        self, validation_service
    ):
        """Test model validation fails when target sum exceeds 95%."""
        # This test should fail during model creation due to domain validation
        # Act & Assert
        with pytest.raises(
            BusinessRuleViolationError, match="Position targets sum.*exceeds maximum"
        ):
            InvestmentModel(
                model_id=ObjectId(),
                name="Invalid Model",
                positions=[
                    Position(
                        security_id="STOCK1234567890123456789",
                        target=TargetPercentage(Decimal("0.50")),
                        drift_bounds=DriftBounds(
                            low_drift=Decimal("0.02"), high_drift=Decimal("0.03")
                        ),
                    ),
                    Position(
                        security_id="STOCK9876543210987654321",
                        target=TargetPercentage(Decimal("0.50")),  # Total = 1.0 > 0.95
                        drift_bounds=DriftBounds(
                            low_drift=Decimal("0.015"), high_drift=Decimal("0.025")
                        ),
                    ),
                ],
                portfolios=["portfolio1"],
                version=1,
            )

    @pytest.mark.asyncio
    async def test_validate_model_too_many_positions(self, validation_service):
        """Test model validation fails with more than 100 positions."""
        # Simply test the validation logic directly without trying to create invalid models
        # Create a mock model that bypasses entity validation
        mock_model = type(
            'MockModel',
            (),
            {
                'positions': [
                    type(
                        'MockPosition',
                        (),
                        {
                            'target': type(
                                'MockTarget', (), {'value': Decimal('0.005')}
                            )()
                        },
                    )()
                    for _ in range(101)
                ]
            },
        )()

        # Act & Assert - validation service should catch this
        with pytest.raises(
            BusinessRuleViolationError,
            match="101 non-zero positions, maximum allowed is 100",
        ):
            await validation_service._validate_position_count_limit(mock_model)

    @pytest.mark.asyncio
    async def test_validate_optimization_inputs_success(
        self, validation_service, valid_model
    ):
        """Test successful optimization input validation."""
        # Arrange - make sure total position value is reasonable compared to market value
        current_positions = {
            "STOCK1234567890123456789": 500,  # 500 * $50 = $25,000
            "STOCK9876543210987654321": 200,  # 200 * $75 = $15,000
        }
        prices = {
            "STOCK1234567890123456789": Decimal("50.00"),
            "STOCK9876543210987654321": Decimal("75.00"),
        }
        market_value = Decimal(
            "44000"
        )  # Adjusted to be within 85-105% range of $40,000 position value

        # Act
        result = await validation_service.validate_optimization_inputs(
            current_positions=current_positions,
            prices=prices,
            market_value=market_value,
            model=valid_model,
        )

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_optimization_inputs_missing_prices(
        self, validation_service, valid_model
    ):
        """Test optimization input validation fails with missing prices."""
        # Arrange
        current_positions = {"STOCK1234567890123456789": 500}
        prices = {
            "STOCK1234567890123456789": Decimal(
                "50.00"
            )  # Only one price, missing the other
        }
        market_value = Decimal("100000")

        # Act & Assert - should fail because model requires price for STOCK987...
        with pytest.raises(
            ValidationError, match="Missing price for security STOCK987"
        ):
            await validation_service.validate_optimization_inputs(
                current_positions=current_positions,
                prices=prices,
                market_value=market_value,
                model=valid_model,
            )

    @pytest.mark.asyncio
    async def test_validate_optimization_inputs_negative_quantities(
        self, validation_service, valid_model
    ):
        """Test optimization input validation fails with negative quantities."""
        # Arrange
        current_positions = {
            "STOCK1234567890123456789": -100,  # Negative quantity
        }
        prices = {"STOCK1234567890123456789": Decimal("50.00")}
        market_value = Decimal("100000")

        # Act & Assert
        with pytest.raises(ValidationError, match="Quantities must be non-negative"):
            await validation_service.validate_optimization_inputs(
                current_positions=current_positions,
                prices=prices,
                market_value=market_value,
                model=valid_model,
            )

    @pytest.mark.asyncio
    async def test_validate_optimization_inputs_zero_market_value(
        self, validation_service, valid_model
    ):
        """Test optimization input validation fails with zero market value."""
        # Arrange
        current_positions = {"STOCK1234567890123456789": 500}
        prices = {"STOCK1234567890123456789": Decimal("50.00")}
        market_value = Decimal("0")  # Invalid market value

        # Act & Assert
        with pytest.raises(ValidationError, match="Market value must be positive"):
            await validation_service.validate_optimization_inputs(
                current_positions=current_positions,
                prices=prices,
                market_value=market_value,
                model=valid_model,
            )

    @pytest.mark.asyncio
    async def test_validate_market_data_success(self, validation_service):
        """Test successful market data validation."""
        # Arrange
        prices = {
            "STOCK1234567890123456789": Decimal("50.00"),
            "STOCK9876543210987654321": Decimal("75.00"),
            "BOND1111111111111111111A": Decimal("100.00"),  # Made 24 chars
        }

        # Act
        result = await validation_service.validate_market_data(prices)

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_market_data_negative_prices(self, validation_service):
        """Test market data validation fails with negative prices."""
        # Arrange
        prices = {
            "STOCK1234567890123456789": Decimal("-50.00"),  # Negative price
            "STOCK9876543210987654321": Decimal("75.00"),
        }

        # Act & Assert
        with pytest.raises(ValidationError, match="Price for.*must be positive"):
            await validation_service.validate_market_data(prices)

    @pytest.mark.asyncio
    async def test_validate_market_data_zero_prices(self, validation_service):
        """Test market data validation fails with zero prices."""
        # Arrange
        prices = {
            "STOCK1234567890123456789": Decimal("0.00"),  # Zero price
            "STOCK9876543210987654321": Decimal("75.00"),
        }

        # Act & Assert
        with pytest.raises(ValidationError, match="Price for.*must be positive"):
            await validation_service.validate_market_data(prices)

    @pytest.mark.asyncio
    async def test_validate_market_data_invalid_security_ids(self, validation_service):
        """Test market data validation fails with invalid security IDs."""
        # Arrange
        prices = {
            "INVALID_ID": Decimal("50.00"),  # Invalid security ID (not 24 chars)
            "STOCK9876543210987654321": Decimal("75.00"),
        }

        # Act & Assert
        with pytest.raises(ValidationError, match="Invalid security ID format"):
            await validation_service.validate_market_data(prices)

    @pytest.mark.asyncio
    async def test_validate_portfolio_data_success(self, validation_service):
        """Test successful portfolio data validation."""
        # Arrange
        positions = {
            "STOCK1234567890123456789": 500,
            "STOCK9876543210987654321": 200,
        }
        market_value = Decimal("100000")

        # Act
        result = await validation_service.validate_portfolio_data(
            positions=positions,
            market_value=market_value,
        )

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_portfolio_data_negative_quantities(
        self, validation_service
    ):
        """Test portfolio data validation fails with negative quantities."""
        # Arrange
        positions = {
            "STOCK1234567890123456789": -100,  # Negative quantity
            "STOCK9876543210987654321": 200,
        }
        market_value = Decimal("100000")

        # Act & Assert
        with pytest.raises(ValidationError, match="Quantities must be non-negative"):
            await validation_service.validate_portfolio_data(
                positions=positions,
                market_value=market_value,
            )

    @pytest.mark.asyncio
    async def test_validate_optimization_result_success(
        self, validation_service, valid_model
    ):
        """Test successful optimization result validation."""
        # Arrange
        result_positions = {
            "STOCK1234567890123456789": 600,
            "STOCK9876543210987654321": 333,
        }
        prices = {
            "STOCK1234567890123456789": Decimal("50.00"),
            "STOCK9876543210987654321": Decimal("75.00"),
        }
        market_value = Decimal("100000")

        # Act
        result = await validation_service.validate_optimization_result(
            result_positions=result_positions,
            model=valid_model,
            prices=prices,
            market_value=market_value,
        )

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_optimization_result_violates_drift_bounds(
        self, validation_service, valid_model
    ):
        """Test optimization result validation fails when drift bounds are violated."""
        # Arrange - Create result that violates drift bounds
        result_positions = {
            "STOCK1234567890123456789": 1000,  # Too many shares, exceeds drift bounds
            "STOCK9876543210987654321": 0,  # Too few shares, violates drift bounds
        }
        prices = {
            "STOCK1234567890123456789": Decimal("50.00"),
            "STOCK9876543210987654321": Decimal("75.00"),
        }
        market_value = Decimal("100000")

        # Act & Assert
        with pytest.raises(ValidationError, match="violates drift bounds"):
            await validation_service.validate_optimization_result(
                result_positions=result_positions,
                model=valid_model,
                prices=prices,
                market_value=market_value,
            )

    @pytest.mark.asyncio
    async def test_validate_security_ids_success(self, validation_service):
        """Test successful security ID validation."""
        # Arrange
        security_ids = [
            "STOCK1234567890123456789",
            "STOCK9876543210987654321",
            "BOND1111111111111111111A",  # Made 24 chars
        ]

        # Act
        result = await validation_service.validate_security_ids(security_ids)

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_security_ids_invalid_length(self, validation_service):
        """Test security ID validation fails with invalid length."""
        # Arrange
        security_ids = [
            "STOCK1234567890123456789",
            "SHORT",  # Too short
        ]

        # Act & Assert
        with pytest.raises(ValidationError, match="Invalid security ID format"):
            await validation_service.validate_security_ids(security_ids)

    @pytest.mark.asyncio
    async def test_validate_security_ids_non_alphanumeric(self, validation_service):
        """Test security ID validation fails with non-alphanumeric characters."""
        # Arrange
        security_ids = [
            "STOCK1234567890123456789",
            "STOCK!@#$%^&*()1234567890",  # Contains special characters
        ]

        # Act & Assert
        with pytest.raises(ValidationError, match="Invalid security ID format"):
            await validation_service.validate_security_ids(security_ids)

    @pytest.mark.asyncio
    async def test_validate_security_ids_duplicates(self, validation_service):
        """Test security ID validation fails with duplicates."""
        # Arrange
        security_ids = [
            "STOCK1234567890123456789",
            "STOCK1234567890123456789",  # Duplicate
        ]

        # Act & Assert
        with pytest.raises(ValidationError, match="Duplicate security IDs"):
            await validation_service.validate_security_ids(security_ids)

    @pytest.mark.asyncio
    async def test_validate_percentage_precision_success(self, validation_service):
        """Test successful percentage precision validation."""
        # Arrange - Valid percentages (multiples of 0.005)
        valid_percentages = [
            Decimal("0.000"),
            Decimal("0.005"),
            Decimal("0.010"),
            Decimal("0.015"),
            Decimal("0.100"),
            Decimal("0.250"),
            Decimal("0.950"),
        ]

        # Act & Assert
        for percentage in valid_percentages:
            result = await validation_service.validate_percentage_precision(percentage)
            assert result is True

    @pytest.mark.asyncio
    async def test_validate_percentage_precision_invalid(self, validation_service):
        """Test percentage precision validation fails with invalid precision."""
        # Arrange - Invalid percentages (not multiples of 0.005)
        invalid_percentages = [
            Decimal("0.001"),
            Decimal("0.003"),
            Decimal("0.007"),
            Decimal("0.012"),
            Decimal("0.133"),
        ]

        # Act & Assert
        for percentage in invalid_percentages:
            with pytest.raises(ValidationError, match="not a multiple of 0.005"):
                await validation_service.validate_percentage_precision(percentage)

    @pytest.mark.asyncio
    async def test_validate_business_rules_comprehensive(
        self, validation_service, valid_model
    ):
        """Test comprehensive business rule validation."""
        # Act
        result = await validation_service.validate_business_rules(valid_model)

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_business_rules_empty_model_name(self, validation_service):
        """Test business rule validation with empty model name."""
        # This test should fail during model creation due to domain validation
        # Act & Assert
        with pytest.raises(ValidationError, match="Model name cannot be empty"):
            InvestmentModel(
                model_id=ObjectId(),
                name="",  # Empty name
                positions=[
                    Position(
                        security_id="STOCK1234567890123456789",
                        target=TargetPercentage(Decimal("0.30")),
                        drift_bounds=DriftBounds(
                            low_drift=Decimal("0.02"), high_drift=Decimal("0.03")
                        ),
                    )
                ],
                portfolios=["portfolio1"],
                version=1,
            )

    @pytest.mark.asyncio
    async def test_validation_performance_with_large_datasets(self, validation_service):
        """Test validation performance with large datasets."""
        # Arrange - Large dataset
        large_positions = {f"STOCK{i:019d}": 100 for i in range(1000)}
        large_prices = {f"STOCK{i:019d}": Decimal("50.00") for i in range(1000)}
        market_value = Decimal("5000000")  # $5M portfolio

        # Act
        result = await validation_service.validate_portfolio_data(
            positions=large_positions,
            market_value=market_value,
        )

        # Assert
        assert result is True

        # Market data validation should also be fast
        result = await validation_service.validate_market_data(large_prices)
        assert result is True
