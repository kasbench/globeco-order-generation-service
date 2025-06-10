"""
Unit tests for rebalance Beanie document models.

This module tests the MongoDB document models using Beanie ODM,
focusing on Decimal128 conversion and validation.
"""

from datetime import datetime
from decimal import Decimal

import pytest
from bson import Decimal128

from src.models.rebalance import PortfolioEmbedded, PositionEmbedded, RebalanceDocument


class TestPositionEmbedded:
    """Test PositionEmbedded Beanie model."""

    def test_decimal128_conversion_in_position(self):
        """Test that PositionEmbedded properly converts Decimal128 to Decimal."""
        position_data = {
            'security_id': 'STOCK1234567890123456789',
            'price': Decimal128('100.50'),
            'original_quantity': Decimal128('500'),
            'adjusted_quantity': Decimal128('600'),
            'original_position_market_value': Decimal128('50250.00'),
            'adjusted_position_market_value': Decimal128('60300.00'),
            'target': Decimal128('0.25'),
            'high_drift': Decimal128('0.05'),
            'low_drift': Decimal128('0.03'),
            'actual': Decimal128('0.2515'),
            'actual_drift': Decimal128('0.006'),
            'transaction_type': 'BUY',
            'trade_quantity': 100,
            'trade_date': datetime.now(),
        }

        # Should not raise validation errors
        position = PositionEmbedded(**position_data)

        # Verify all Decimal128 values are converted to Decimal
        assert isinstance(position.price, Decimal)
        assert isinstance(position.original_quantity, Decimal)
        assert isinstance(position.adjusted_quantity, Decimal)
        assert isinstance(position.original_position_market_value, Decimal)
        assert isinstance(position.adjusted_position_market_value, Decimal)
        assert isinstance(position.target, Decimal)
        assert isinstance(position.high_drift, Decimal)
        assert isinstance(position.low_drift, Decimal)
        assert isinstance(position.actual, Decimal)
        assert isinstance(position.actual_drift, Decimal)

        # Verify values are preserved correctly
        assert position.price == Decimal('100.50')
        assert position.original_quantity == Decimal('500')
        assert position.target == Decimal('0.25')
        assert position.actual_drift == Decimal('0.006')

    def test_regular_decimal_passthrough_in_position(self):
        """Test that regular Decimal values are passed through unchanged."""
        position_data = {
            'security_id': 'STOCK1234567890123456789',
            'price': Decimal('100.50'),
            'original_quantity': Decimal('500'),
            'adjusted_quantity': Decimal('600'),
            'original_position_market_value': Decimal('50250.00'),
            'adjusted_position_market_value': Decimal('60300.00'),
            'target': Decimal('0.25'),
            'high_drift': Decimal('0.05'),
            'low_drift': Decimal('0.03'),
            'actual': Decimal('0.2515'),
            'actual_drift': Decimal('0.006'),
            'transaction_type': 'BUY',
            'trade_quantity': 100,
            'trade_date': datetime.now(),
        }

        position = PositionEmbedded(**position_data)

        # Values should be identical
        assert position.price == Decimal('100.50')
        assert position.target == Decimal('0.25')
        assert isinstance(position.price, Decimal)


class TestPortfolioEmbedded:
    """Test PortfolioEmbedded Beanie model."""

    def test_decimal128_conversion_in_portfolio(self):
        """Test that PortfolioEmbedded properly converts Decimal128 to Decimal."""
        portfolio_data = {
            'portfolio_id': '683b6d88a29ee10e8b499643',
            'market_value': Decimal128('240000.00'),
            'cash_before_rebalance': Decimal128('10000.00'),
            'cash_after_rebalance': Decimal128('9950.00'),
            'positions': [],
        }

        # Should not raise validation errors
        portfolio = PortfolioEmbedded(**portfolio_data)

        # Verify all Decimal128 values are converted to Decimal
        assert isinstance(portfolio.market_value, Decimal)
        assert isinstance(portfolio.cash_before_rebalance, Decimal)
        assert isinstance(portfolio.cash_after_rebalance, Decimal)

        # Verify values are preserved correctly
        assert portfolio.market_value == Decimal('240000.00')
        assert portfolio.cash_before_rebalance == Decimal('10000.00')
        assert portfolio.cash_after_rebalance == Decimal('9950.00')

    def test_portfolio_with_decimal128_positions(self):
        """Test portfolio with positions that have Decimal128 values."""
        position = PositionEmbedded(
            security_id='STOCK1234567890123456789',
            price=Decimal128('100.50'),
            original_quantity=Decimal128('500'),
            adjusted_quantity=Decimal128('600'),
            original_position_market_value=Decimal128('50250.00'),
            adjusted_position_market_value=Decimal128('60300.00'),
            target=Decimal128('0.25'),
            high_drift=Decimal128('0.05'),
            low_drift=Decimal128('0.03'),
            actual=Decimal128('0.2515'),
            actual_drift=Decimal128('0.006'),
            transaction_type='BUY',
            trade_quantity=100,
            trade_date=datetime.now(),
        )

        portfolio_data = {
            'portfolio_id': '683b6d88a29ee10e8b499643',
            'market_value': Decimal128('240000.00'),
            'cash_before_rebalance': Decimal128('10000.00'),
            'cash_after_rebalance': Decimal128('9950.00'),
            'positions': [position],
        }

        # Should work without validation errors
        portfolio = PortfolioEmbedded(**portfolio_data)

        assert len(portfolio.positions) == 1
        assert isinstance(portfolio.positions[0].price, Decimal)
        assert portfolio.positions[0].price == Decimal('100.50')


class TestRebalanceDocument:
    """Test RebalanceDocument Beanie model."""

    def test_rebalance_document_creation_with_decimal128_data(self):
        """Test creating RebalanceDocument with embedded Decimal128 data."""
        from bson import ObjectId

        position = PositionEmbedded(
            security_id='STOCK1234567890123456789',
            price=Decimal128('100.50'),
            original_quantity=Decimal128('500'),
            adjusted_quantity=Decimal128('600'),
            original_position_market_value=Decimal128('50250.00'),
            adjusted_position_market_value=Decimal128('60300.00'),
            target=Decimal128('0.25'),
            high_drift=Decimal128('0.05'),
            low_drift=Decimal128('0.03'),
            actual=Decimal128('0.2515'),
            actual_drift=Decimal128('0.006'),
            transaction_type='BUY',
            trade_quantity=100,
            trade_date=datetime.now(),
        )

        portfolio = PortfolioEmbedded(
            portfolio_id='683b6d88a29ee10e8b499643',
            market_value=Decimal128('240000.00'),
            cash_before_rebalance=Decimal128('10000.00'),
            cash_after_rebalance=Decimal128('9950.00'),
            positions=[position],
        )

        rebalance_data = {
            'model_id': ObjectId(),
            'rebalance_date': datetime.now(),
            'model_name': 'Test Model',
            'number_of_portfolios': 1,
            'portfolios': [portfolio],
            'version': 1,
        }

        # Should work without validation errors
        rebalance = RebalanceDocument(**rebalance_data)

        assert len(rebalance.portfolios) == 1
        assert isinstance(rebalance.portfolios[0].market_value, Decimal)
        assert isinstance(rebalance.portfolios[0].positions[0].price, Decimal)
        assert rebalance.portfolios[0].market_value == Decimal('240000.00')
        assert rebalance.portfolios[0].positions[0].price == Decimal('100.50')

    def test_decimal128_conversion_validation_sufficient(self):
        """Test that the embedded models handle Decimal128 conversion correctly.

        This test validates that our Decimal128 conversion validators work
        for the embedded models, which is sufficient since RebalanceDocument
        uses these embedded models and the conversion happens at the field level.
        """
        # Test position with all Decimal128 fields
        position = PositionEmbedded(
            security_id='STOCK1234567890123456789',
            price=Decimal128('100.50'),
            original_quantity=Decimal128('500'),
            adjusted_quantity=Decimal128('600'),
            original_position_market_value=Decimal128('50250.00'),
            adjusted_position_market_value=Decimal128('60300.00'),
            target=Decimal128('0.25'),
            high_drift=Decimal128('0.05'),
            low_drift=Decimal128('0.03'),
            actual=Decimal128('0.2515'),
            actual_drift=Decimal128('0.006'),
            transaction_type='BUY',
            trade_quantity=100,
            trade_date=datetime.now(),
        )

        # Test portfolio with Decimal128 fields and position
        portfolio = PortfolioEmbedded(
            portfolio_id='683b6d88a29ee10e8b499643',
            market_value=Decimal128('240000.00'),
            cash_before_rebalance=Decimal128('10000.00'),
            cash_after_rebalance=Decimal128('9950.00'),
            positions=[position],
        )

        # Verify all conversions worked
        assert isinstance(position.price, Decimal)
        assert isinstance(position.target, Decimal)
        assert isinstance(portfolio.market_value, Decimal)
        assert isinstance(portfolio.positions[0].actual_drift, Decimal)

        # Values preserved correctly
        assert position.price == Decimal('100.50')
        assert portfolio.market_value == Decimal('240000.00')

        # This proves the Decimal128 conversion will work in RebalanceDocument
        # since it uses these same embedded models
