"""
Infrastructure test to verify testing setup is working correctly.

This test module validates that the testing infrastructure, fixtures,
and utilities are properly configured and functional.
"""

from decimal import Decimal

import pytest

from src.config import get_settings
from src.tests.utils.assertions import assert_decimal_equal, assert_optimization_valid
from src.tests.utils.generators import (
    generate_security_prices,
    generate_test_securities,
)


class TestTestingInfrastructure:
    """Test the testing infrastructure itself."""

    def test_configuration_loads(self):
        """Test that configuration can be loaded successfully."""
        settings = get_settings()
        assert settings.service_name == "GlobeCo Order Generation Service"
        assert settings.port == 8080
        assert settings.database_name == "order-generation"

    def test_decimal_assertion_utility(self):
        """Test the decimal assertion utility function."""
        # Test equal decimals
        assert_decimal_equal(Decimal("1.0000"), Decimal("1.0000"))
        assert_decimal_equal(Decimal("123.4567"), Decimal("123.4567"))

        # Test nearly equal decimals (within tolerance)
        assert_decimal_equal(Decimal("1.0001"), Decimal("1.0000"), places=3)

        # Test assertion failure
        with pytest.raises(AssertionError):
            assert_decimal_equal(Decimal("1.1"), Decimal("1.0"), places=4)

    def test_test_data_generators(self):
        """Test that test data generators work correctly."""
        # Test security generation
        securities = generate_test_securities(5)
        assert len(securities) == 5

        for security in securities:
            assert "securityId" in security
            assert "symbol" in security
            assert "name" in security
            assert len(security["securityId"]) == 24  # 24-character hex ID

        # Test price generation
        security_ids = [s["securityId"] for s in securities]
        prices = generate_security_prices(security_ids)

        assert len(prices) == len(security_ids)
        for security_id in security_ids:
            assert security_id in prices
            assert isinstance(prices[security_id], Decimal)
            assert prices[security_id] > 0

    def test_optimization_assertion_utility(self):
        """Test the optimization constraint validation utility."""
        # Valid optimization result that satisfies constraints
        quantities = [120, 175, 0]  # Values that fit within drift bounds
        prices = [Decimal("50"), Decimal("100"), Decimal("25")]
        target_percentages = [Decimal("0.25"), Decimal("0.70"), Decimal("0.00")]
        market_value = Decimal("25000")  # 120*50 + 175*100 = 23500, cash = 1500
        low_drifts = [Decimal("0.05"), Decimal("0.05"), Decimal("0.05")]
        high_drifts = [Decimal("0.05"), Decimal("0.05"), Decimal("0.05")]

        # This should not raise an exception
        assert_optimization_valid(
            quantities,
            prices,
            target_percentages,
            market_value,
            low_drifts,
            high_drifts,
            tolerance=Decimal("1000"),  # Large tolerance for this test
        )

        # Test constraint violation with clearly invalid quantities
        invalid_quantities = [
            500,
            200,
            0,
        ]  # First position way too large (500*50 = 25000 = 100% of portfolio)
        with pytest.raises(AssertionError):
            assert_optimization_valid(
                invalid_quantities,
                prices,
                target_percentages,
                market_value,
                low_drifts,
                high_drifts,
                tolerance=Decimal("0.01"),
            )


@pytest.mark.unit
class TestPytestMarkers:
    """Test that pytest markers are working correctly."""

    def test_unit_marker_applied(self, request):
        """Test that unit marker is automatically applied."""
        # Check if the unit marker was applied
        markers = [marker.name for marker in request.node.iter_markers()]
        assert "unit" in markers


@pytest.mark.mathematical
class TestMathematicalFixtures:
    """Test mathematical validation fixtures."""

    def test_simple_optimization_problem_fixture(self, simple_optimization_problem):
        """Test the simple optimization problem fixture."""
        problem = simple_optimization_problem

        # Validate fixture structure
        required_keys = [
            "current_quantities",
            "target_percentages",
            "prices",
            "market_value",
            "low_drifts",
            "high_drifts",
        ]
        for key in required_keys:
            assert key in problem

        # Validate data types and constraints
        assert len(problem["current_quantities"]) == 2
        assert len(problem["target_percentages"]) == 2
        assert len(problem["prices"]) == 2
        assert problem["market_value"] == 20000.0

        # Target percentages should be reasonable
        target_sum = sum(problem["target_percentages"])
        assert 0 < target_sum <= 1.0

    def test_complex_optimization_problem_fixture(self, complex_optimization_problem):
        """Test the complex optimization problem fixture."""
        problem = complex_optimization_problem

        # Validate fixture structure
        assert len(problem["current_quantities"]) == 20
        assert len(problem["target_percentages"]) == 20
        assert len(problem["prices"]) == 20
        assert problem["market_value"] == 100000.0

        # All positions should have same target (4%)
        for target in problem["target_percentages"]:
            assert target == 0.04

        # Target sum should be 80% (20 * 4%)
        target_sum = sum(problem["target_percentages"])
        assert target_sum == 0.8


class TestSampleData:
    """Test sample data fixtures."""

    def test_sample_investment_model_fixture(self, sample_investment_model):
        """Test the sample investment model fixture."""
        model = sample_investment_model

        # Validate structure
        assert "name" in model
        assert "positions" in model
        assert "portfolios" in model

        # Validate positions
        assert len(model["positions"]) == 2
        for position in model["positions"]:
            assert "securityId" in position
            assert "target" in position
            assert "highDrift" in position
            assert "lowDrift" in position

            # Validate constraints
            assert 0 <= position["target"] <= 1
            assert 0 <= position["lowDrift"] <= 1
            assert 0 <= position["highDrift"] <= 1
            assert position["lowDrift"] <= position["highDrift"]

        # Target sum should be <= 0.95
        target_sum = sum(pos["target"] for pos in model["positions"])
        assert target_sum <= Decimal("0.95")

    def test_sample_portfolio_balances_fixture(self, sample_portfolio_balances):
        """Test the sample portfolio balances fixture."""
        balances = sample_portfolio_balances

        # Should have 3 positions (2 securities + cash)
        assert len(balances) == 3

        # Check securities
        securities = [b for b in balances if not b.get("cash", False)]
        assert len(securities) == 2

        # Check cash
        cash_positions = [b for b in balances if b.get("cash", False)]
        assert len(cash_positions) == 1

        # Validate structure
        for balance in balances:
            assert "quantity" in balance
            assert "marketValue" in balance
            assert balance["quantity"] > 0
            assert balance["marketValue"] > 0

    def test_sample_security_prices_fixture(self, sample_security_prices):
        """Test the sample security prices fixture."""
        prices = sample_security_prices

        # Should have 2 securities
        assert len(prices) == 2

        # Check specific securities
        assert "683b6b9620f302c879a5fef4" in prices
        assert "683b6b9620f302c879a5fef5" in prices

        # Validate prices
        for security_id, price in prices.items():
            assert isinstance(price, Decimal)
            assert price > 0
