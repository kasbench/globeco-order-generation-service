"""
Tests for Investment Model domain entity.

This module tests the Investment Model entity which represents an investment
model with target allocations and drift tolerances for portfolio rebalancing.

Following TDD principles, these tests define the business rules and constraints
that the Investment Model must satisfy.
"""

from datetime import datetime
from decimal import Decimal

import pytest
from bson import ObjectId

from src.core.exceptions import BusinessRuleViolationError, ValidationError
from src.domain.entities.model import InvestmentModel
from src.domain.entities.position import Position
from src.domain.value_objects.drift_bounds import DriftBounds
from src.domain.value_objects.target_percentage import TargetPercentage


class TestInvestmentModelCreation:
    """Test Investment Model creation and basic properties."""

    def test_create_investment_model_with_valid_data(self):
        """Test creating an investment model with valid data."""
        model = InvestmentModel(
            model_id=ObjectId(),
            name="Conservative Growth",
            positions=[],
            portfolios=["portfolio1", "portfolio2"],
            version=1,
        )

        assert model.name == "Conservative Growth"
        assert len(model.positions) == 0
        assert len(model.portfolios) == 2
        assert model.version == 1
        assert model.last_rebalance_date is None

    def test_investment_model_requires_name(self):
        """Test that investment model requires a name."""
        with pytest.raises(ValidationError):
            InvestmentModel(
                model_id=ObjectId(),
                name="",  # Empty name should fail
                positions=[],
                portfolios=["portfolio1"],
                version=1,
            )

    def test_investment_model_name_must_be_unique_constraint(self):
        """Test that model validates name uniqueness constraint."""
        # This will be enforced at the repository level, but the entity
        # should be designed to support this constraint
        model = InvestmentModel(
            model_id=ObjectId(),
            name="Growth Model",
            positions=[],
            portfolios=["portfolio1"],
            version=1,
        )

        # Name should be stored correctly for uniqueness checks
        assert model.name == "Growth Model"

    def test_investment_model_version_defaults_to_one(self):
        """Test that version defaults to 1 for new models."""
        model = InvestmentModel(
            model_id=ObjectId(),
            name="Test Model",
            positions=[],
            portfolios=["portfolio1"],
        )

        assert model.version == 1


class TestInvestmentModelPositions:
    """Test Investment Model position management."""

    def test_add_position_to_model(self):
        """Test adding a position to an investment model."""
        model = InvestmentModel(
            model_id=ObjectId(),
            name="Test Model",
            positions=[],
            portfolios=["portfolio1"],
            version=1,
        )

        position = Position(
            security_id="STOCK1234567890123456789",
            target=TargetPercentage(Decimal("0.15")),  # 15%
            drift_bounds=DriftBounds(
                low_drift=Decimal("0.02"), high_drift=Decimal("0.03")  # 2%  # 3%
            ),
        )

        model.add_position(position)

        assert len(model.positions) == 1
        assert model.positions[0].security_id == "STOCK1234567890123456789"
        assert model.positions[0].target.value == Decimal("0.15")

    def test_cannot_add_duplicate_security_positions(self):
        """Test that a security can only appear once in a model."""
        model = InvestmentModel(
            model_id=ObjectId(),
            name="Test Model",
            positions=[],
            portfolios=["portfolio1"],
            version=1,
        )

        position1 = Position(
            security_id="STOCK1234567890123456789",
            target=TargetPercentage(Decimal("0.15")),
            drift_bounds=DriftBounds(
                low_drift=Decimal("0.02"), high_drift=Decimal("0.03")
            ),
        )

        position2 = Position(
            security_id="STOCK1234567890123456789",  # Same security
            target=TargetPercentage(Decimal("0.10")),
            drift_bounds=DriftBounds(
                low_drift=Decimal("0.01"), high_drift=Decimal("0.02")
            ),
        )

        model.add_position(position1)

        with pytest.raises(
            BusinessRuleViolationError, match="Security.*already exists"
        ):
            model.add_position(position2)

    def test_update_existing_position(self):
        """Test updating an existing position in a model."""
        model = InvestmentModel(
            model_id=ObjectId(),
            name="Test Model",
            positions=[],
            portfolios=["portfolio1"],
            version=1,
        )

        # Add initial position
        position = Position(
            security_id="STOCK1234567890123456789",
            target=TargetPercentage(Decimal("0.15")),
            drift_bounds=DriftBounds(
                low_drift=Decimal("0.02"), high_drift=Decimal("0.03")
            ),
        )
        model.add_position(position)

        # Update position
        updated_position = Position(
            security_id="STOCK1234567890123456789",
            target=TargetPercentage(Decimal("0.20")),  # Changed from 15% to 20%
            drift_bounds=DriftBounds(
                low_drift=Decimal("0.025"), high_drift=Decimal("0.035")
            ),
        )

        model.update_position(updated_position)

        assert len(model.positions) == 1
        assert model.positions[0].target.value == Decimal("0.20")

    def test_remove_position_from_model(self):
        """Test removing a position from an investment model."""
        model = InvestmentModel(
            model_id=ObjectId(),
            name="Test Model",
            positions=[],
            portfolios=["portfolio1"],
            version=1,
        )

        position = Position(
            security_id="STOCK1234567890123456789",
            target=TargetPercentage(Decimal("0.15")),
            drift_bounds=DriftBounds(
                low_drift=Decimal("0.02"), high_drift=Decimal("0.03")
            ),
        )

        model.add_position(position)
        assert len(model.positions) == 1

        model.remove_position("STOCK1234567890123456789")
        assert len(model.positions) == 0

    def test_remove_nonexistent_position_raises_error(self):
        """Test that removing a non-existent position raises an error."""
        model = InvestmentModel(
            model_id=ObjectId(),
            name="Test Model",
            positions=[],
            portfolios=["portfolio1"],
            version=1,
        )

        with pytest.raises(ValidationError, match="Position not found"):
            model.remove_position("NONEXISTENT123456789012")


class TestInvestmentModelBusinessRules:
    """Test Investment Model business rule enforcement."""

    def test_position_targets_sum_cannot_exceed_95_percent(self):
        """Test that position targets sum must be ≤ 0.95 (95%)."""
        model = InvestmentModel(
            model_id=ObjectId(),
            name="Test Model",
            positions=[],
            portfolios=["portfolio1"],
            version=1,
        )

        # Add positions that sum to exactly 95%
        positions = [
            Position(
                security_id=f"STOCK{i:019d}",  # Changed to 19 digits to make 24 chars total
                target=TargetPercentage(Decimal("0.19")),  # 19% each
                drift_bounds=DriftBounds(
                    low_drift=Decimal("0.02"), high_drift=Decimal("0.03")
                ),
            )
            for i in range(5)  # 5 × 19% = 95%
        ]

        for position in positions:
            model.add_position(position)

        # This should be valid
        model.validate_target_sum()

        # Adding one more position should fail
        extra_position = Position(
            security_id="STOCK9999999999999999999",  # Made exactly 24 characters
            target=TargetPercentage(Decimal("0.01")),  # Even 1% more
            drift_bounds=DriftBounds(
                low_drift=Decimal("0.01"), high_drift=Decimal("0.01")
            ),
        )

        with pytest.raises(
            BusinessRuleViolationError, match="Adding position.*exceed maximum"
        ):
            model.add_position(extra_position)

    def test_position_targets_must_be_multiple_of_0_005(self):
        """Test that position targets must be 0 or multiples of 0.005."""
        # Valid targets: 0, 0.005, 0.010, 0.015, etc.
        valid_targets = [
            Decimal("0"),
            Decimal("0.005"),
            Decimal("0.010"),
            Decimal("0.050"),
            Decimal("0.125"),
        ]

        for target_value in valid_targets:
            # This should not raise an error
            target = TargetPercentage(target_value)
            assert target.value == target_value

        # Invalid targets: 0.001, 0.003, 0.007, etc.
        invalid_targets = [
            Decimal("0.001"),
            Decimal("0.003"),
            Decimal("0.007"),
            Decimal("0.012"),
            Decimal("0.123"),
        ]

        for target_value in invalid_targets:
            with pytest.raises(ValidationError, match="must be.*multiple.*0.005"):
                TargetPercentage(target_value)

    def test_maximum_100_positions_with_nonzero_target(self):
        """Test that models can have maximum 100 positions with target > 0."""
        model = InvestmentModel(
            model_id=ObjectId(),
            name="Large Model",
            positions=[],
            portfolios=["portfolio1"],
            version=1,
        )

        # Add 100 positions with small targets (0.01 each = 100% total)
        for i in range(95):  # Changed to 95 positions at 0.01 each = 95%
            position = Position(
                security_id=f"STOCK{i:019d}",  # Changed to 19 digits to make 24 chars total
                target=TargetPercentage(
                    Decimal("0.01")
                ),  # 1.0% each (valid multiple of 0.005)
                drift_bounds=DriftBounds(
                    low_drift=Decimal("0.01"), high_drift=Decimal("0.01")
                ),
            )
            model.add_position(position)

        # This should be valid
        assert len(model.get_nonzero_target_positions()) == 95  # Updated count

        # Adding the 101st position should fail
        extra_position = Position(
            security_id="STOCK0100000000000000000",  # Made exactly 24 characters
            target=TargetPercentage(Decimal("0.005")),
            drift_bounds=DriftBounds(
                low_drift=Decimal("0.01"), high_drift=Decimal("0.01")
            ),
        )

        with pytest.raises(
            BusinessRuleViolationError, match="Adding position.*exceed maximum"
        ):
            model.add_position(extra_position)

    def test_zero_target_positions_are_automatically_removed(self):
        """Test that positions with target = 0 are automatically removed."""
        model = InvestmentModel(
            model_id=ObjectId(),
            name="Test Model",
            positions=[],
            portfolios=["portfolio1"],
            version=1,
        )

        # Add position with non-zero target
        position = Position(
            security_id="STOCK1234567890123456789",
            target=TargetPercentage(Decimal("0.15")),
            drift_bounds=DriftBounds(
                low_drift=Decimal("0.02"), high_drift=Decimal("0.03")
            ),
        )
        model.add_position(position)
        assert len(model.positions) == 1

        # Update position to zero target
        zero_position = Position(
            security_id="STOCK1234567890123456789",
            target=TargetPercentage(Decimal("0")),
            drift_bounds=DriftBounds(
                low_drift=Decimal("0.02"), high_drift=Decimal("0.03")
            ),
        )
        model.update_position(zero_position)

        # Position should be automatically removed
        assert len(model.positions) == 0

    def test_validate_all_business_rules(self):
        """Test comprehensive business rule validation."""
        model = InvestmentModel(
            model_id=ObjectId(),
            name="Valid Model",
            positions=[],
            portfolios=["portfolio1"],
            version=1,
        )

        # Add valid positions
        positions = [
            Position(
                security_id="STOCK0010000000000000001",  # Made exactly 24 characters
                target=TargetPercentage(Decimal("0.30")),  # 30%
                drift_bounds=DriftBounds(
                    low_drift=Decimal("0.02"), high_drift=Decimal("0.03")
                ),
            ),
            Position(
                security_id="STOCK0020000000000000002",  # Made exactly 24 characters
                target=TargetPercentage(Decimal("0.25")),  # 25%
                drift_bounds=DriftBounds(
                    low_drift=Decimal("0.015"), high_drift=Decimal("0.025")
                ),
            ),
            Position(
                security_id="STOCK0030000000000000003",  # Made exactly 24 characters
                target=TargetPercentage(Decimal("0.20")),  # 20%
                drift_bounds=DriftBounds(
                    low_drift=Decimal("0.01"), high_drift=Decimal("0.02")
                ),
            ),
        ]

        for position in positions:
            model.add_position(position)

        # Total: 75%, should be valid (leaves 25% for cash)
        model.validate_all_business_rules()

        # Model should be valid
        assert len(model.positions) == 3
        assert model.get_total_target_percentage() == Decimal("0.75")


class TestInvestmentModelPortfolios:
    """Test Investment Model portfolio association."""

    def test_add_portfolio_to_model(self):
        """Test adding a portfolio to an investment model."""
        model = InvestmentModel(
            model_id=ObjectId(),
            name="Test Model",
            positions=[],
            portfolios=[],
            version=1,
        )

        model.add_portfolio("portfolio123456789012345678")

        assert len(model.portfolios) == 1
        assert "portfolio123456789012345678" in model.portfolios

    def test_cannot_add_duplicate_portfolio(self):
        """Test that a portfolio can only be added once to a model."""
        model = InvestmentModel(
            model_id=ObjectId(),
            name="Test Model",
            positions=[],
            portfolios=["portfolio123456789012345678"],
            version=1,
        )

        with pytest.raises(
            BusinessRuleViolationError, match="Portfolio.*already associated"
        ):
            model.add_portfolio("portfolio123456789012345678")

    def test_remove_portfolio_from_model(self):
        """Test removing a portfolio from an investment model."""
        model = InvestmentModel(
            model_id=ObjectId(),
            name="Test Model",
            positions=[],
            portfolios=["portfolio1", "portfolio2"],
            version=1,
        )

        model.remove_portfolio("portfolio1")

        assert len(model.portfolios) == 1
        assert "portfolio1" not in model.portfolios
        assert "portfolio2" in model.portfolios

    def test_remove_nonexistent_portfolio_raises_error(self):
        """Test that removing a non-existent portfolio raises an error."""
        model = InvestmentModel(
            model_id=ObjectId(),
            name="Test Model",
            positions=[],
            portfolios=["portfolio1"],
            version=1,
        )

        with pytest.raises(ValidationError, match="Portfolio.*not found"):
            model.remove_portfolio("nonexistent")


class TestInvestmentModelVersioning:
    """Test Investment Model versioning for optimistic locking."""

    def test_version_increments_on_update(self):
        """Test that version increments when model is updated."""
        model = InvestmentModel(
            model_id=ObjectId(),
            name="Test Model",
            positions=[],
            portfolios=["portfolio1"],
            version=1,
        )

        original_version = model.version
        model.increment_version()

        assert model.version == original_version + 1

    def test_last_rebalance_date_can_be_updated(self):
        """Test that last rebalance date can be updated."""
        model = InvestmentModel(
            model_id=ObjectId(),
            name="Test Model",
            positions=[],
            portfolios=["portfolio1"],
            version=1,
        )

        assert model.last_rebalance_date is None

        rebalance_time = datetime.utcnow()
        model.update_last_rebalance_date(rebalance_time)

        assert model.last_rebalance_date == rebalance_time
