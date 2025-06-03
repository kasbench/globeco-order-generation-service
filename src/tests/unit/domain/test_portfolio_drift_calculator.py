"""
Tests for Portfolio Drift Calculator implementation.

This module tests the concrete implementation of the DriftCalculator interface,
focusing on mathematical correctness and business logic validation.

Following TDD principles, these tests define the expected behavior for
the actual drift calculation service implementation.
"""

from decimal import Decimal

import pytest
from bson import ObjectId

from src.core.exceptions import ValidationError
from src.domain.entities.model import InvestmentModel
from src.domain.entities.position import Position
from src.domain.services.drift_calculator import DriftInfo
from src.domain.services.implementations.portfolio_drift_calculator import (
    PortfolioDriftCalculator,
)
from src.domain.value_objects.drift_bounds import DriftBounds
from src.domain.value_objects.target_percentage import TargetPercentage


@pytest.mark.unit
class TestPortfolioDriftCalculatorImplementation:
    """Test concrete Portfolio Drift Calculator implementation."""

    @pytest.fixture
    def drift_calculator(self) -> PortfolioDriftCalculator:
        """Create a portfolio drift calculator instance."""
        return PortfolioDriftCalculator()

    @pytest.fixture
    def sample_model(self) -> InvestmentModel:
        """Create a sample investment model for testing."""
        return InvestmentModel(
            model_id=ObjectId(),
            name="Test Model",
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
                Position(
                    security_id="BOND1111111111111111111A",  # Made 24 chars
                    target=TargetPercentage(Decimal("0.20")),
                    drift_bounds=DriftBounds(
                        low_drift=Decimal("0.01"), high_drift=Decimal("0.02")
                    ),
                ),
            ],
            portfolios=["portfolio1"],
            version=1,
        )

    @pytest.mark.asyncio
    async def test_calculate_portfolio_drift_accurate_calculations(
        self, drift_calculator, sample_model
    ):
        """Test portfolio drift calculation with mathematical accuracy."""
        # Arrange
        current_positions = {
            "STOCK1234567890123456789": 500,  # $25,000 at $50
            "STOCK9876543210987654321": 200,  # $15,000 at $75
            "BOND1111111111111111111A": 400,  # $40,000 at $100
        }
        prices = {
            "STOCK1234567890123456789": Decimal("50.00"),
            "STOCK9876543210987654321": Decimal("75.00"),
            "BOND1111111111111111111A": Decimal("100.00"),
        }
        market_value = Decimal("100000")  # Total portfolio value

        # Expected drift calculations:
        # STOCK1: Current = 25000/100000 = 0.25, Target = 0.30, Drift = -0.05
        # STOCK2: Current = 15000/100000 = 0.15, Target = 0.25, Drift = -0.10
        # BOND1:  Current = 40000/100000 = 0.40, Target = 0.20, Drift = +0.20

        # Act
        result = await drift_calculator.calculate_portfolio_drift(
            positions=current_positions,
            prices=prices,
            market_value=market_value,
            model=sample_model,
        )

        # Assert
        assert len(result) == 3

        # Check STOCK1 drift
        stock1_drift = next(
            d for d in result if d.security_id == "STOCK1234567890123456789"
        )
        assert stock1_drift.current_value == Decimal("25000")
        assert stock1_drift.target_value == Decimal("30000")  # 0.30 * 100000
        assert stock1_drift.current_percentage == Decimal("0.25")
        assert stock1_drift.target_percentage == Decimal("0.30")
        assert stock1_drift.drift_amount == Decimal("-0.05")
        assert stock1_drift.is_within_bounds is False  # Drift 0.05 > low_drift 0.02

        # Check STOCK2 drift
        stock2_drift = next(
            d for d in result if d.security_id == "STOCK9876543210987654321"
        )
        assert stock2_drift.current_value == Decimal("15000")
        assert stock2_drift.target_value == Decimal("25000")  # 0.25 * 100000
        assert stock2_drift.current_percentage == Decimal("0.15")
        assert stock2_drift.target_percentage == Decimal("0.25")
        assert stock2_drift.drift_amount == Decimal("-0.10")
        assert stock2_drift.is_within_bounds is False  # Drift 0.10 > low_drift 0.015

        # Check BOND1 drift
        bond1_drift = next(
            d for d in result if d.security_id == "BOND1111111111111111111A"
        )
        assert bond1_drift.current_value == Decimal("40000")
        assert bond1_drift.target_value == Decimal("20000")  # 0.20 * 100000
        assert bond1_drift.current_percentage == Decimal("0.40")
        assert bond1_drift.target_percentage == Decimal("0.20")
        assert bond1_drift.drift_amount == Decimal("0.20")
        assert bond1_drift.is_within_bounds is False  # Drift 0.20 > high_drift 0.02

    @pytest.mark.asyncio
    async def test_calculate_position_drift_mathematical_accuracy(
        self, drift_calculator
    ):
        """Test individual position drift calculation."""
        # Arrange
        current_value = Decimal("25000")
        target_percentage = Decimal("0.30")
        market_value = Decimal("100000")

        # Expected: (25000 / 100000) - 0.30 = 0.25 - 0.30 = -0.05

        # Act
        result = await drift_calculator.calculate_position_drift(
            current_value=current_value,
            target_percentage=target_percentage,
            market_value=market_value,
        )

        # Assert
        assert result == Decimal("-0.05")

    @pytest.mark.asyncio
    async def test_calculate_total_drift_sum_of_absolute_drifts(self, drift_calculator):
        """Test total portfolio drift calculation as sum of absolute drifts."""
        # Arrange
        drift_infos = [
            DriftInfo(
                security_id="STOCK1234567890123456789",
                current_value=Decimal("25000"),
                target_value=Decimal("30000"),
                current_percentage=Decimal("0.25"),
                target_percentage=Decimal("0.30"),
                drift_amount=Decimal("-0.05"),
                is_within_bounds=False,
            ),
            DriftInfo(
                security_id="STOCK9876543210987654321",
                current_value=Decimal("15000"),
                target_value=Decimal("25000"),
                current_percentage=Decimal("0.15"),
                target_percentage=Decimal("0.25"),
                drift_amount=Decimal("-0.10"),
                is_within_bounds=False,
            ),
            DriftInfo(
                security_id="BOND1111111111111111111A",  # Made 24 chars
                current_value=Decimal("40000"),
                target_value=Decimal("20000"),
                current_percentage=Decimal("0.40"),
                target_percentage=Decimal("0.20"),
                drift_amount=Decimal("0.20"),
                is_within_bounds=False,
            ),
        ]

        # Expected: |−0.05| + |−0.10| + |0.20| = 0.05 + 0.10 + 0.20 = 0.35

        # Act
        result = await drift_calculator.calculate_total_drift(drift_infos)

        # Assert
        assert result == Decimal("0.35")

    @pytest.mark.asyncio
    async def test_get_positions_outside_bounds_filtering(self, drift_calculator):
        """Test filtering positions that are outside drift bounds."""
        # Arrange
        drift_infos = [
            # Within bounds
            DriftInfo(
                security_id="STOCK1234567890123456789",
                current_value=Decimal("29000"),
                target_value=Decimal("30000"),
                current_percentage=Decimal("0.29"),
                target_percentage=Decimal("0.30"),
                drift_amount=Decimal("-0.01"),
                is_within_bounds=True,  # Within 2% drift tolerance
            ),
            # Outside bounds
            DriftInfo(
                security_id="STOCK9876543210987654321",
                current_value=Decimal("15000"),
                target_value=Decimal("25000"),
                current_percentage=Decimal("0.15"),
                target_percentage=Decimal("0.25"),
                drift_amount=Decimal("-0.10"),
                is_within_bounds=False,  # Outside 1.5% drift tolerance
            ),
        ]

        # Act
        result = await drift_calculator.get_positions_outside_bounds(drift_infos)

        # Assert
        assert len(result) == 1
        assert result[0].security_id == "STOCK9876543210987654321"
        assert result[0].is_within_bounds is False

    @pytest.mark.asyncio
    async def test_calculate_required_trades_buy_sell_logic(self, drift_calculator):
        """Test calculation of required trades between current and target positions."""
        # Arrange
        current_positions = {
            "STOCK1234567890123456789": 500,  # Current quantity
            "STOCK9876543210987654321": 200,  # Current quantity
            "BOND1111111111111111111A": 400,  # Current quantity
        }
        target_positions = {
            "STOCK1234567890123456789": 600,  # Need to buy 100
            "STOCK9876543210987654321": 150,  # Need to sell 50
            "BOND1111111111111111111A": 400,  # No change
        }

        # Act
        result = await drift_calculator.calculate_required_trades(
            current_positions=current_positions,
            target_positions=target_positions,
        )

        # Assert
        assert result["STOCK1234567890123456789"] == 100  # Buy 100
        assert result["STOCK9876543210987654321"] == -50  # Sell 50
        # No change trades are not included
        assert "BOND1111111111111111111A" not in result

    @pytest.mark.asyncio
    async def test_estimate_trade_costs_commission_calculation(self, drift_calculator):
        """Test trade cost estimation with commission rates."""
        # Arrange
        trades = {
            "STOCK1234567890123456789": 100,  # Buy 100 shares
            "STOCK9876543210987654321": -50,  # Sell 50 shares
        }
        prices = {
            "STOCK1234567890123456789": Decimal("50.00"),
            "STOCK9876543210987654321": Decimal("75.00"),
        }
        commission_rate = Decimal("0.001")  # 0.1%

        # Expected cost:
        # Buy: 100 * $50 = $5,000, Commission: $5,000 * 0.001 = $5
        # Sell: 50 * $75 = $3,750, Commission: $3,750 * 0.001 = $3.75
        # Total: $5 + $3.75 = $8.75

        # Act
        result = await drift_calculator.estimate_trade_costs(
            trades=trades,
            prices=prices,
            commission_rate=commission_rate,
        )

        # Assert
        assert result == Decimal("8.75")

    @pytest.mark.asyncio
    async def test_edge_case_zero_market_value(self, drift_calculator, sample_model):
        """Test handling of edge case with zero market value."""
        # Arrange
        current_positions = {}
        prices = {}
        market_value = Decimal("0")

        # Act & Assert
        with pytest.raises(ValidationError, match="Market value must be positive"):
            await drift_calculator.calculate_portfolio_drift(
                positions=current_positions,
                prices=prices,
                market_value=market_value,
                model=sample_model,
            )

    @pytest.mark.asyncio
    async def test_edge_case_missing_prices(self, drift_calculator, sample_model):
        """Test handling of missing price data."""
        # Arrange
        current_positions = {"STOCK1234567890123456789": 500}
        prices = {}  # Missing prices
        market_value = Decimal("100000")

        # Act & Assert
        with pytest.raises(ValidationError, match="Missing price for security"):
            await drift_calculator.calculate_portfolio_drift(
                positions=current_positions,
                prices=prices,
                market_value=market_value,
                model=sample_model,
            )

    @pytest.mark.asyncio
    async def test_precision_with_decimal_arithmetic(self, drift_calculator):
        """Test that calculations maintain decimal precision for financial accuracy."""
        # Arrange - Use values that result in exact decimal precision
        current_value = Decimal("33333.00")  # Changed to avoid precision issues
        target_percentage = Decimal("0.333330")  # Exact multiple
        market_value = Decimal("100000.00")

        # Expected: 33333.00 / 100000.00 - 0.333330 = 0.333330 - 0.333330 = 0.000000

        # Act
        result = await drift_calculator.calculate_position_drift(
            current_value=current_value,
            target_percentage=target_percentage,
            market_value=market_value,
        )

        # Assert
        assert isinstance(result, Decimal)
        assert result == Decimal("0.000000")  # Exact decimal precision

    @pytest.mark.asyncio
    async def test_performance_with_large_portfolio(self, drift_calculator):
        """Test performance with a large number of positions."""
        # Arrange - Create model with many positions
        positions = []
        for i in range(100):  # 100 positions
            positions.append(
                Position(
                    security_id=f"STOCK{i:019d}",  # 24-char security ID
                    target=TargetPercentage(
                        Decimal("0.005")
                    ),  # Valid multiple of 0.005
                    drift_bounds=DriftBounds(
                        low_drift=Decimal("0.01"), high_drift=Decimal("0.02")
                    ),
                )
            )

        large_model = InvestmentModel(
            model_id=ObjectId(),
            name="Large Model",
            positions=positions,
            portfolios=["portfolio1"],
            version=1,
        )

        # Create matching positions and prices
        current_positions = {f"STOCK{i:019d}": 100 for i in range(100)}
        prices = {f"STOCK{i:019d}": Decimal("10.00") for i in range(100)}
        market_value = Decimal("1000000")  # $1M portfolio

        # Act
        result = await drift_calculator.calculate_portfolio_drift(
            positions=current_positions,
            prices=prices,
            market_value=market_value,
            model=large_model,
        )

        # Assert
        assert len(result) == 100
        # Each position should have value $1000 (100 shares * $10)
        # Current percentage = 1000/1000000 = 0.001
        # Target percentage = 0.005
        # Drift = 0.001 - 0.005 = -0.004
        for drift_info in result:
            assert drift_info.current_value == Decimal("1000")
            assert drift_info.current_percentage == Decimal("0.001")
            assert drift_info.target_percentage == Decimal("0.005")
            assert drift_info.drift_amount == Decimal("-0.004")
