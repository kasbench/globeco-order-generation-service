"""
Tests for rebalance and transaction schema DTOs.

This module tests the data transfer objects used for portfolio rebalancing:
- TransactionDTO for buy/sell orders
- DriftDTO for position drift analysis
- RebalanceDTO for complete rebalancing results
- Validation and serialization of financial data
- Edge cases and error handling
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import List, Optional

import pytest
from pydantic import ValidationError


@pytest.mark.unit
class TestTransactionDTO:
    """Test TransactionDTO for buy/sell order representation."""

    def test_valid_transaction_dto_creation(self):
        """Test creation of valid transaction DTO."""
        from src.schemas.transactions import TransactionDTO, TransactionType

        transaction_data = {
            "transaction_type": TransactionType.BUY,
            "security_id": "STOCK1234567890123456789",
            "quantity": 100,
            "trade_date": date(2024, 12, 19),
        }

        transaction_dto = TransactionDTO(**transaction_data)

        assert transaction_dto.transaction_type == TransactionType.BUY
        assert transaction_dto.security_id == "STOCK1234567890123456789"
        assert transaction_dto.quantity == 100
        assert transaction_dto.trade_date == date(2024, 12, 19)

    def test_transaction_type_enum_validation(self):
        """Test transaction type enum validation."""
        from src.schemas.transactions import TransactionType

        # Test enum values
        assert TransactionType.BUY.value == "BUY"
        assert TransactionType.SELL.value == "SELL"

        # Test case insensitive parsing
        from src.schemas.transactions import TransactionDTO

        transaction_dto = TransactionDTO(
            transaction_type="buy",  # lowercase
            security_id="STOCK1234567890123456789",
            quantity=100,
            trade_date=date(2024, 12, 19),
        )

        assert transaction_dto.transaction_type == TransactionType.BUY

    def test_transaction_dto_security_id_validation(self):
        """Test security ID validation in transactions."""
        from src.schemas.transactions import TransactionDTO, TransactionType

        # Test invalid security ID length
        with pytest.raises(ValidationError, match="at least 24 characters"):
            TransactionDTO(
                transaction_type=TransactionType.BUY,
                security_id="SHORT",  # Too short
                quantity=100,
                trade_date=date(2024, 12, 19),
            )

        # Test invalid characters (24 chars but with special characters)
        with pytest.raises(ValidationError, match="exactly 24.*alphanumeric"):
            TransactionDTO(
                transaction_type=TransactionType.BUY,
                security_id="STOCK1234567890123456_!",  # 24 chars with special chars
                quantity=100,
                trade_date=date(2024, 12, 19),
            )

    def test_transaction_dto_quantity_validation(self):
        """Test quantity validation in transactions."""
        from src.schemas.transactions import TransactionDTO, TransactionType

        # Test negative quantity
        with pytest.raises(ValidationError, match="greater than 0"):
            TransactionDTO(
                transaction_type=TransactionType.BUY,
                security_id="STOCK1234567890123456789",
                quantity=-50,  # Negative quantity
                trade_date=date(2024, 12, 19),
            )

        # Test zero quantity
        with pytest.raises(ValidationError, match="positive"):
            TransactionDTO(
                transaction_type=TransactionType.BUY,
                security_id="STOCK1234567890123456789",
                quantity=0,  # Zero quantity
                trade_date=date(2024, 12, 19),
            )

    def test_transaction_dto_trade_date_validation(self):
        """Test trade date validation."""
        from src.schemas.transactions import TransactionDTO, TransactionType

        # Test future date (should be allowed for trade scheduling)
        future_transaction = TransactionDTO(
            transaction_type=TransactionType.BUY,
            security_id="STOCK1234567890123456789",
            quantity=100,
            trade_date=date(2025, 1, 1),  # Future date
        )

        assert future_transaction.trade_date == date(2025, 1, 1)

    def test_sell_transaction_creation(self):
        """Test creation of SELL transaction."""
        from src.schemas.transactions import TransactionDTO, TransactionType

        sell_transaction = TransactionDTO(
            transaction_type=TransactionType.SELL,
            security_id="BOND1111111111111111111A",
            quantity=250,
            trade_date=date(2024, 12, 20),
        )

        assert sell_transaction.transaction_type == TransactionType.SELL
        assert sell_transaction.quantity == 250


@pytest.mark.unit
class TestDriftDTO:
    """Test DriftDTO for position drift analysis."""

    def test_valid_drift_dto_creation(self):
        """Test creation of valid drift DTO."""
        from src.schemas.rebalance import DriftDTO

        drift_data = {
            "security_id": "STOCK1234567890123456789",
            "original_quantity": Decimal("500"),
            "adjusted_quantity": Decimal("600"),
            "target": Decimal("0.25"),
            "high_drift": Decimal("0.05"),
            "low_drift": Decimal("0.03"),
            "actual": Decimal("0.2750"),
        }

        drift_dto = DriftDTO(**drift_data)

        assert drift_dto.security_id == "STOCK1234567890123456789"
        assert drift_dto.original_quantity == Decimal("500")
        assert drift_dto.adjusted_quantity == Decimal("600")
        assert drift_dto.target == Decimal("0.25")
        assert drift_dto.actual == Decimal("0.2750")

    def test_drift_dto_decimal_precision(self):
        """Test decimal precision in drift calculations."""
        from src.schemas.rebalance import DriftDTO

        # Test high-precision decimal values
        drift_dto = DriftDTO(
            security_id="STOCK1234567890123456789",
            original_quantity=Decimal("500.123456"),
            adjusted_quantity=Decimal("600.789012"),
            target=Decimal("0.250000"),
            high_drift=Decimal("0.050000"),
            low_drift=Decimal("0.030000"),
            actual=Decimal("0.275123"),  # 4 decimal places as specified
        )

        # Precision should be preserved
        assert drift_dto.original_quantity == Decimal("500.123456")
        assert drift_dto.actual == Decimal("0.275123")

    def test_drift_dto_target_validation(self):
        """Test target percentage validation in drift DTO."""
        from src.schemas.rebalance import DriftDTO

        # Test target > 0.95
        with pytest.raises(ValidationError, match="less than or equal to 0.95"):
            DriftDTO(
                security_id="STOCK1234567890123456789",
                original_quantity=Decimal("500"),
                adjusted_quantity=Decimal("600"),
                target=Decimal("0.96"),  # Too high
                high_drift=Decimal("0.05"),
                low_drift=Decimal("0.03"),
                actual=Decimal("0.2750"),
            )

    def test_drift_dto_bounds_validation(self):
        """Test drift bounds validation."""
        from src.schemas.rebalance import DriftDTO

        # Test low drift > high drift
        with pytest.raises(
            ValidationError, match="Low drift.*cannot exceed.*high drift"
        ):
            DriftDTO(
                security_id="STOCK1234567890123456789",
                original_quantity=Decimal("500"),
                adjusted_quantity=Decimal("600"),
                target=Decimal("0.25"),
                high_drift=Decimal("0.03"),
                low_drift=Decimal("0.05"),  # Higher than high_drift
                actual=Decimal("0.2750"),
            )

    def test_drift_dto_quantity_validation(self):
        """Test quantity validation in drift DTO."""
        from src.schemas.rebalance import DriftDTO

        # Test negative original quantity
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            DriftDTO(
                security_id="STOCK1234567890123456789",
                original_quantity=Decimal("-500"),  # Negative
                adjusted_quantity=Decimal("600"),
                target=Decimal("0.25"),
                high_drift=Decimal("0.05"),
                low_drift=Decimal("0.03"),
                actual=Decimal("0.2750"),
            )

        # Test negative adjusted quantity
        with pytest.raises(ValidationError, match="non-negative"):
            DriftDTO(
                security_id="STOCK1234567890123456789",
                original_quantity=Decimal("500"),
                adjusted_quantity=Decimal("-600"),  # Negative
                target=Decimal("0.25"),
                high_drift=Decimal("0.05"),
                low_drift=Decimal("0.03"),
                actual=Decimal("0.2750"),
            )


@pytest.mark.unit
class TestRebalanceDTO:
    """Test RebalanceDTO for complete rebalancing results."""

    def test_valid_rebalance_dto_creation(self):
        """Test creation of valid rebalance DTO."""
        from src.schemas.rebalance import DriftDTO, RebalanceDTO
        from src.schemas.transactions import TransactionDTO, TransactionType

        transaction = TransactionDTO(
            transaction_type=TransactionType.BUY,
            security_id="STOCK1234567890123456789",
            quantity=100,
            trade_date=date(2024, 12, 19),
        )

        drift = DriftDTO(
            security_id="STOCK1234567890123456789",
            original_quantity=Decimal("500"),
            adjusted_quantity=Decimal("600"),
            target=Decimal("0.25"),
            high_drift=Decimal("0.05"),
            low_drift=Decimal("0.03"),
            actual=Decimal("0.2750"),
        )

        rebalance_data = {
            "portfolio_id": "683b6d88a29ee10e8b499643",
            "transactions": [transaction],
            "drifts": [drift],
        }

        rebalance_dto = RebalanceDTO(**rebalance_data)

        assert rebalance_dto.portfolio_id == "683b6d88a29ee10e8b499643"
        assert len(rebalance_dto.transactions) == 1
        assert len(rebalance_dto.drifts) == 1
        assert rebalance_dto.transactions[0].transaction_type == TransactionType.BUY

    def test_rebalance_dto_portfolio_id_validation(self):
        """Test portfolio ID validation."""
        from src.schemas.rebalance import RebalanceDTO

        # Test invalid portfolio ID format (not 24 characters)
        with pytest.raises(ValidationError, match="at least 24 characters"):
            RebalanceDTO(
                portfolio_id="short_id", transactions=[], drifts=[]  # Too short
            )

    def test_rebalance_dto_empty_lists_allowed(self):
        """Test that empty transactions and drifts lists are allowed."""
        from src.schemas.rebalance import RebalanceDTO

        # Empty lists should be valid (no rebalancing needed)
        rebalance_dto = RebalanceDTO(
            portfolio_id="683b6d88a29ee10e8b499643",
            transactions=[],  # No transactions needed
            drifts=[],  # No positions to analyze
        )

        assert len(rebalance_dto.transactions) == 0
        assert len(rebalance_dto.drifts) == 0


@pytest.mark.unit
class TestSchemaSerialization:
    """Test JSON serialization and deserialization of rebalance schemas."""

    def test_transaction_dto_json_serialization(self):
        """Test JSON serialization of TransactionDTO."""
        from src.schemas.transactions import TransactionDTO, TransactionType

        transaction_dto = TransactionDTO(
            transaction_type=TransactionType.BUY,
            security_id="STOCK1234567890123456789",
            quantity=100,
            trade_date=date(2024, 12, 19),
        )

        json_data = transaction_dto.model_dump(mode='json')

        assert json_data["transaction_type"] == "BUY"
        assert json_data["security_id"] == "STOCK1234567890123456789"
        assert json_data["quantity"] == 100
        assert json_data["trade_date"] == "2024-12-19"

    def test_drift_dto_json_serialization(self):
        """Test JSON serialization of DriftDTO."""
        from src.schemas.rebalance import DriftDTO

        drift_dto = DriftDTO(
            security_id="STOCK1234567890123456789",
            original_quantity=Decimal("500.123"),
            adjusted_quantity=Decimal("600.456"),
            target=Decimal("0.25"),
            high_drift=Decimal("0.05"),
            low_drift=Decimal("0.03"),
            actual=Decimal("0.2750"),
        )

        json_data = drift_dto.model_dump(mode='json')

        assert json_data["security_id"] == "STOCK1234567890123456789"
        assert json_data["original_quantity"] == "500.123"  # Decimal as string
        assert json_data["adjusted_quantity"] == "600.456"
        assert json_data["target"] == "0.25"
        assert json_data["actual"] == "0.2750"
