"""
Unit tests for rebalance domain entities.

This module tests the business logic and validation rules for rebalance-related
domain entities including positions, portfolios, and rebalance operations.
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from bson import ObjectId

from src.domain.entities.rebalance import (
    Rebalance,
    RebalancePortfolio,
    RebalancePosition,
)


class TestRebalancePosition:
    """Test cases for RebalancePosition domain entity."""

    def test_create_position_valid_data(self):
        """Test creating a position with valid data."""
        position = RebalancePosition(
            security_id="abc123def456ghi789jkl012",
            price=Decimal("100.50"),
            original_quantity=Decimal("10"),
            adjusted_quantity=Decimal("15"),
            original_position_market_value=Decimal("1005.00"),
            adjusted_position_market_value=Decimal("1507.50"),
            target=Decimal("0.05"),
            high_drift=Decimal("0.1"),
            low_drift=Decimal("0.05"),
            actual=Decimal("0.0600"),
            actual_drift=Decimal("0.2000"),
            transaction_type="BUY",
            trade_quantity=5,
            trade_date=datetime.now(timezone.utc),
        )

        assert position.security_id == "abc123def456ghi789jkl012"
        assert position.price == Decimal("100.50")
        assert position.original_quantity == Decimal("10")
        assert position.adjusted_quantity == Decimal("15")
        assert position.has_transaction()
        assert position.calculate_transaction_delta() == 5

    def test_create_position_no_transaction(self):
        """Test creating a position with no transaction."""
        position = RebalancePosition(
            security_id="abc123def456ghi789jkl012",
            price=Decimal("100.50"),
            original_quantity=Decimal("10"),
            adjusted_quantity=Decimal("10"),
            original_position_market_value=Decimal("1005.00"),
            adjusted_position_market_value=Decimal("1005.00"),
            target=Decimal("0.05"),
            high_drift=Decimal("0.1"),
            low_drift=Decimal("0.05"),
            actual=Decimal("0.0500"),
            actual_drift=Decimal("0.0000"),
        )

        assert not position.has_transaction()
        assert position.calculate_transaction_delta() == 0
        assert position.transaction_type is None
        assert position.trade_quantity is None

    def test_invalid_security_id_format(self):
        """Test validation of security ID format."""
        with pytest.raises(
            ValueError, match="Security ID must be exactly 24 alphanumeric characters"
        ):
            RebalancePosition(
                security_id="invalid",  # Too short
                price=Decimal("100.50"),
                original_quantity=Decimal("10"),
                adjusted_quantity=Decimal("15"),
                original_position_market_value=Decimal("1005.00"),
                adjusted_position_market_value=Decimal("1507.50"),
                target=Decimal("0.05"),
                high_drift=Decimal("0.1"),
                low_drift=Decimal("0.05"),
                actual=Decimal("0.0600"),
                actual_drift=Decimal("0.2000"),
            )

    def test_invalid_transaction_type(self):
        """Test validation of transaction type."""
        with pytest.raises(
            ValueError, match="Transaction type must be 'BUY' or 'SELL'"
        ):
            RebalancePosition(
                security_id="abc123def456ghi789jkl012",
                price=Decimal("100.50"),
                original_quantity=Decimal("10"),
                adjusted_quantity=Decimal("15"),
                original_position_market_value=Decimal("1005.00"),
                adjusted_position_market_value=Decimal("1507.50"),
                target=Decimal("0.05"),
                high_drift=Decimal("0.1"),
                low_drift=Decimal("0.05"),
                actual=Decimal("0.0600"),
                actual_drift=Decimal("0.2000"),
                transaction_type="INVALID",  # Invalid type
                trade_quantity=5,
            )

    def test_invalid_trade_quantity(self):
        """Test validation of trade quantity."""
        with pytest.raises(ValueError, match="Trade quantity must be positive"):
            RebalancePosition(
                security_id="abc123def456ghi789jkl012",
                price=Decimal("100.50"),
                original_quantity=Decimal("10"),
                adjusted_quantity=Decimal("15"),
                original_position_market_value=Decimal("1005.00"),
                adjusted_position_market_value=Decimal("1507.50"),
                target=Decimal("0.05"),
                high_drift=Decimal("0.1"),
                low_drift=Decimal("0.05"),
                actual=Decimal("0.0600"),
                actual_drift=Decimal("0.2000"),
                transaction_type="BUY",
                trade_quantity=0,  # Invalid quantity
            )


class TestRebalancePortfolio:
    """Test cases for RebalancePortfolio domain entity."""

    def test_create_portfolio_valid_data(self):
        """Test creating a portfolio with valid data."""
        positions = [
            RebalancePosition(
                security_id="abc123def456ghi789jkl012",
                price=Decimal("100.50"),
                original_quantity=Decimal("10"),
                adjusted_quantity=Decimal("15"),
                original_position_market_value=Decimal("1005.00"),
                adjusted_position_market_value=Decimal("1507.50"),
                target=Decimal("0.05"),
                high_drift=Decimal("0.1"),
                low_drift=Decimal("0.05"),
                actual=Decimal("0.0600"),
                actual_drift=Decimal("0.2000"),
                transaction_type="BUY",
                trade_quantity=5,
                trade_date=datetime.now(timezone.utc),
            )
        ]

        portfolio = RebalancePortfolio(
            portfolio_id="def456ghi789jkl012mno345",
            market_value=Decimal("25000.00"),
            cash_before_rebalance=Decimal("1000.00"),
            cash_after_rebalance=Decimal("500.00"),
            positions=positions,
        )

        assert portfolio.portfolio_id == "def456ghi789jkl012mno345"
        assert portfolio.market_value == Decimal("25000.00")
        assert len(portfolio.positions) == 1
        assert portfolio.get_transaction_count() == 1
        assert (
            portfolio.get_position_by_security("abc123def456ghi789jkl012") is not None
        )
        assert portfolio.get_position_by_security("nonexistent") is None

    def test_portfolio_calculations(self):
        """Test portfolio calculation methods."""
        positions = [
            RebalancePosition(
                security_id="abc123def456ghi789jkl012",
                price=Decimal("100.00"),
                original_quantity=Decimal("10"),
                adjusted_quantity=Decimal("15"),
                original_position_market_value=Decimal("1000.00"),
                adjusted_position_market_value=Decimal("1500.00"),
                target=Decimal("0.05"),
                high_drift=Decimal("0.1"),
                low_drift=Decimal("0.05"),
                actual=Decimal("0.0600"),
                actual_drift=Decimal("0.2000"),
            ),
            RebalancePosition(
                security_id="def456ghi789jkl012mno345",
                price=Decimal("50.00"),
                original_quantity=Decimal("20"),
                adjusted_quantity=Decimal("30"),
                original_position_market_value=Decimal("1000.00"),
                adjusted_position_market_value=Decimal("1500.00"),
                target=Decimal("0.06"),
                high_drift=Decimal("0.1"),
                low_drift=Decimal("0.05"),
                actual=Decimal("0.0600"),
                actual_drift=Decimal("0.0000"),
            ),
        ]

        portfolio = RebalancePortfolio(
            portfolio_id="def456ghi789jkl012mno345",
            market_value=Decimal("25000.00"),
            cash_before_rebalance=Decimal("1000.00"),
            cash_after_rebalance=Decimal("500.00"),
            positions=positions,
        )

        assert portfolio.calculate_total_original_market_value() == Decimal("2000.00")
        assert portfolio.calculate_total_adjusted_market_value() == Decimal("3000.00")

    def test_invalid_portfolio_id_format(self):
        """Test validation of portfolio ID format."""
        with pytest.raises(
            ValueError, match="Portfolio ID must be exactly 24 characters"
        ):
            RebalancePortfolio(
                portfolio_id="short",  # Too short
                market_value=Decimal("25000.00"),
                cash_before_rebalance=Decimal("1000.00"),
                cash_after_rebalance=Decimal("500.00"),
            )

    def test_negative_monetary_values(self):
        """Test validation of non-negative monetary values."""
        with pytest.raises(ValueError, match="Monetary values must be non-negative"):
            RebalancePortfolio(
                portfolio_id="def456ghi789jkl012mno345",
                market_value=Decimal("-1000.00"),  # Negative value
                cash_before_rebalance=Decimal("1000.00"),
                cash_after_rebalance=Decimal("500.00"),
            )

    def test_duplicate_securities_in_positions(self):
        """Test validation of unique securities in positions."""
        positions = [
            RebalancePosition(
                security_id="abc123def456ghi789jkl012",  # Duplicate
                price=Decimal("100.00"),
                original_quantity=Decimal("10"),
                adjusted_quantity=Decimal("15"),
                original_position_market_value=Decimal("1000.00"),
                adjusted_position_market_value=Decimal("1500.00"),
                target=Decimal("0.05"),
                high_drift=Decimal("0.1"),
                low_drift=Decimal("0.05"),
                actual=Decimal("0.0600"),
                actual_drift=Decimal("0.2000"),
            ),
            RebalancePosition(
                security_id="abc123def456ghi789jkl012",  # Duplicate
                price=Decimal("100.00"),
                original_quantity=Decimal("5"),
                adjusted_quantity=Decimal("10"),
                original_position_market_value=Decimal("500.00"),
                adjusted_position_market_value=Decimal("1000.00"),
                target=Decimal("0.04"),
                high_drift=Decimal("0.1"),
                low_drift=Decimal("0.05"),
                actual=Decimal("0.0400"),
                actual_drift=Decimal("0.0000"),
            ),
        ]

        with pytest.raises(
            ValueError, match="Duplicate securities not allowed in portfolio positions"
        ):
            RebalancePortfolio(
                portfolio_id="def456ghi789jkl012mno345",
                market_value=Decimal("25000.00"),
                cash_before_rebalance=Decimal("1000.00"),
                cash_after_rebalance=Decimal("500.00"),
                positions=positions,
            )


class TestRebalance:
    """Test cases for Rebalance domain entity."""

    def test_create_rebalance_valid_data(self):
        """Test creating a rebalance with valid data."""
        portfolio = RebalancePortfolio(
            portfolio_id="def456ghi789jkl012mno345",
            market_value=Decimal("25000.00"),
            cash_before_rebalance=Decimal("1000.00"),
            cash_after_rebalance=Decimal("500.00"),
            positions=[],
        )

        rebalance = Rebalance(
            model_id=ObjectId(),
            rebalance_date=datetime.now(timezone.utc),
            model_name="Test Model",
            number_of_portfolios=1,
            portfolios=[portfolio],
            version=1,
            created_at=datetime.now(timezone.utc),
        )

        assert rebalance.model_name == "Test Model"
        assert rebalance.number_of_portfolios == 1
        assert len(rebalance.portfolios) == 1
        assert rebalance.version == 1

        # Test derived methods
        rebalance.validate_portfolio_count_consistency()  # Should not raise
        assert rebalance.get_total_transaction_count() == 0
        assert rebalance.get_portfolio_ids() == ["def456ghi789jkl012mno345"]
        assert rebalance.calculate_total_market_value() == Decimal("25000.00")

    def test_rebalance_with_multiple_portfolios(self):
        """Test creating a rebalance with multiple portfolios."""
        portfolios = [
            RebalancePortfolio(
                portfolio_id="def456ghi789jkl012mno345",
                market_value=Decimal("25000.00"),
                cash_before_rebalance=Decimal("1000.00"),
                cash_after_rebalance=Decimal("500.00"),
                positions=[],
            ),
            RebalancePortfolio(
                portfolio_id="ghi789jkl012mno345pqr678",
                market_value=Decimal("30000.00"),
                cash_before_rebalance=Decimal("2000.00"),
                cash_after_rebalance=Decimal("1500.00"),
                positions=[],
            ),
        ]

        rebalance = Rebalance(
            model_id=ObjectId(),
            rebalance_date=datetime.now(timezone.utc),
            model_name="Multi-Portfolio Model",
            number_of_portfolios=2,
            portfolios=portfolios,
        )

        assert rebalance.number_of_portfolios == 2
        assert len(rebalance.portfolios) == 2
        assert rebalance.calculate_total_market_value() == Decimal("55000.00")
        assert set(rebalance.get_portfolio_ids()) == {
            "def456ghi789jkl012mno345",
            "ghi789jkl012mno345pqr678",
        }

    def test_invalid_model_name(self):
        """Test validation of model name."""
        with pytest.raises(ValueError, match="Model name cannot be empty"):
            Rebalance(
                model_id=ObjectId(),
                rebalance_date=datetime.now(timezone.utc),
                model_name="   ",  # Empty/whitespace
                number_of_portfolios=1,
                portfolios=[],
            )

    def test_invalid_number_of_portfolios(self):
        """Test validation of number of portfolios."""
        with pytest.raises(ValueError, match="Number of portfolios must be positive"):
            Rebalance(
                model_id=ObjectId(),
                rebalance_date=datetime.now(timezone.utc),
                model_name="Test Model",
                number_of_portfolios=0,  # Invalid
                portfolios=[],
            )

    def test_invalid_version(self):
        """Test validation of version."""
        with pytest.raises(ValueError, match="Version must be positive"):
            Rebalance(
                model_id=ObjectId(),
                rebalance_date=datetime.now(timezone.utc),
                model_name="Test Model",
                number_of_portfolios=1,
                portfolios=[],
                version=0,  # Invalid
            )

    def test_duplicate_portfolios(self):
        """Test validation of unique portfolios."""
        portfolios = [
            RebalancePortfolio(
                portfolio_id="def456ghi789jkl012mno345",  # Duplicate
                market_value=Decimal("25000.00"),
                cash_before_rebalance=Decimal("1000.00"),
                cash_after_rebalance=Decimal("500.00"),
                positions=[],
            ),
            RebalancePortfolio(
                portfolio_id="def456ghi789jkl012mno345",  # Duplicate
                market_value=Decimal("30000.00"),
                cash_before_rebalance=Decimal("2000.00"),
                cash_after_rebalance=Decimal("1500.00"),
                positions=[],
            ),
        ]

        with pytest.raises(
            ValueError, match="Duplicate portfolios not allowed in rebalance"
        ):
            Rebalance(
                model_id=ObjectId(),
                rebalance_date=datetime.now(timezone.utc),
                model_name="Test Model",
                number_of_portfolios=2,
                portfolios=portfolios,
            )

    def test_portfolio_count_mismatch(self):
        """Test validation of portfolio count consistency."""
        portfolio = RebalancePortfolio(
            portfolio_id="def456ghi789jkl012mno345",
            market_value=Decimal("25000.00"),
            cash_before_rebalance=Decimal("1000.00"),
            cash_after_rebalance=Decimal("500.00"),
            positions=[],
        )

        rebalance = Rebalance(
            model_id=ObjectId(),
            rebalance_date=datetime.now(timezone.utc),
            model_name="Test Model",
            number_of_portfolios=2,  # Mismatch: says 2 but only 1 portfolio
            portfolios=[portfolio],
        )

        with pytest.raises(
            ValueError, match="Portfolio count mismatch: expected 2, got 1"
        ):
            rebalance.validate_portfolio_count_consistency()

    def test_get_portfolio_by_id(self):
        """Test getting portfolio by ID."""
        portfolio = RebalancePortfolio(
            portfolio_id="def456ghi789jkl012mno345",
            market_value=Decimal("25000.00"),
            cash_before_rebalance=Decimal("1000.00"),
            cash_after_rebalance=Decimal("500.00"),
            positions=[],
        )

        rebalance = Rebalance(
            model_id=ObjectId(),
            rebalance_date=datetime.now(timezone.utc),
            model_name="Test Model",
            number_of_portfolios=1,
            portfolios=[portfolio],
        )

        found_portfolio = rebalance.get_portfolio_by_id("def456ghi789jkl012mno345")
        assert found_portfolio is not None
        assert found_portfolio.portfolio_id == "def456ghi789jkl012mno345"

        not_found = rebalance.get_portfolio_by_id("nonexistent")
        assert not_found is None
