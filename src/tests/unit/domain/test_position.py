"""
Tests for Position domain entity.

This module tests the Position entity which represents a security position
within an investment model, including target allocation and drift tolerances.

Following TDD principles, these tests define the business rules and constraints
that the Position entity must satisfy.
"""

from decimal import Decimal

import pytest

from src.core.exceptions import ValidationError
from src.domain.entities.position import Position
from src.domain.value_objects.drift_bounds import DriftBounds
from src.domain.value_objects.target_percentage import TargetPercentage


class TestPositionCreation:
    """Test Position creation and basic properties."""

    def test_create_position_with_valid_data(self):
        """Test creating a position with valid data."""
        position = Position(
            security_id="STOCK1234567890123456789",
            target=TargetPercentage(Decimal("0.15")),  # 15%
            drift_bounds=DriftBounds(
                low_drift=Decimal("0.02"), high_drift=Decimal("0.03")  # 2%  # 3%
            ),
        )

        assert position.security_id == "STOCK1234567890123456789"
        assert position.target.value == Decimal("0.15")
        assert position.drift_bounds.low_drift == Decimal("0.02")
        assert position.drift_bounds.high_drift == Decimal("0.03")

    def test_position_requires_24_character_security_id(self):
        """Test that position requires exactly 24-character security ID."""
        # Valid 24-character security ID
        valid_security_id = "STOCK1234567890123456789"
        assert len(valid_security_id) == 24

        position = Position(
            security_id=valid_security_id,
            target=TargetPercentage(Decimal("0.15")),
            drift_bounds=DriftBounds(
                low_drift=Decimal("0.02"), high_drift=Decimal("0.03")
            ),
        )
        assert position.security_id == valid_security_id

        # Invalid security IDs (wrong length)
        invalid_security_ids = [
            "",  # Empty
            "SHORT",  # Too short
            "STOCK123456789012345",  # 23 characters
            "STOCK12345678901234567899",  # 25 characters
        ]

        for invalid_id in invalid_security_ids:
            with pytest.raises(
                ValidationError, match="Security ID must be exactly 24 characters"
            ):
                Position(
                    security_id=invalid_id,
                    target=TargetPercentage(Decimal("0.15")),
                    drift_bounds=DriftBounds(
                        low_drift=Decimal("0.02"), high_drift=Decimal("0.03")
                    ),
                )

    def test_position_security_id_must_be_alphanumeric(self):
        """Test that security ID must contain only alphanumeric characters."""
        valid_security_ids = [
            "STOCK1234567890123456789",
            "ABCD1234567890123456789A",  # Made exactly 24 characters
            "123456789012345678901234",
        ]

        for valid_id in valid_security_ids:
            # Should not raise an error
            position = Position(
                security_id=valid_id,
                target=TargetPercentage(Decimal("0.15")),
                drift_bounds=DriftBounds(
                    low_drift=Decimal("0.02"), high_drift=Decimal("0.03")
                ),
            )
            assert position.security_id == valid_id

        invalid_security_ids = [
            "STOCK12345678901234567-8",  # Contains hyphen, exactly 24 chars
            "STOCK12345678901234567 8",  # Contains space, exactly 24 chars
            "STOCK12345678901234567@8",  # Contains special character, exactly 24 chars
            "STOCK12345678901234567.8",  # Contains period, exactly 24 chars
        ]

        for invalid_id in invalid_security_ids:
            with pytest.raises(
                ValidationError,
                match="Security ID must contain only alphanumeric characters",
            ):
                Position(
                    security_id=invalid_id,
                    target=TargetPercentage(Decimal("0.15")),
                    drift_bounds=DriftBounds(
                        low_drift=Decimal("0.02"), high_drift=Decimal("0.03")
                    ),
                )


class TestPositionTargetPercentage:
    """Test Position target percentage validation."""

    def test_target_percentage_valid_values(self):
        """Test that target percentage accepts valid values."""
        valid_targets = [
            Decimal("0"),  # 0%
            Decimal("0.005"),  # 0.5%
            Decimal("0.010"),  # 1.0%
            Decimal("0.050"),  # 5.0%
            Decimal("0.150"),  # 15.0%
            Decimal("0.500"),  # 50.0%
            Decimal("0.950"),  # 95.0% (maximum)
        ]

        for target_value in valid_targets:
            position = Position(
                security_id="STOCK1234567890123456789",
                target=TargetPercentage(target_value),
                drift_bounds=DriftBounds(
                    low_drift=Decimal("0.02"), high_drift=Decimal("0.03")
                ),
            )
            assert position.target.value == target_value

    def test_target_percentage_must_be_between_0_and_95_percent(self):
        """Test that target percentage must be between 0 and 0.95."""
        # Valid boundary values
        boundary_values = [
            Decimal("0"),  # Minimum
            Decimal("0.950"),  # Maximum
        ]

        for target_value in boundary_values:
            # Should not raise an error
            TargetPercentage(target_value)

        # Invalid values (outside range)
        invalid_values = [
            Decimal("-0.001"),  # Negative
            Decimal("0.951"),  # Above 95%
            Decimal("1.0"),  # 100%
            Decimal("1.5"),  # 150%
        ]

        for target_value in invalid_values:
            with pytest.raises(
                ValidationError, match="Target percentage must be between 0 and 0.95"
            ):
                TargetPercentage(target_value)

    def test_target_percentage_must_be_multiple_of_0_005(self):
        """Test that target percentage must be 0 or multiple of 0.005."""
        # Valid multiples of 0.005
        valid_multiples = [
            Decimal("0"),  # 0 × 0.005
            Decimal("0.005"),  # 1 × 0.005
            Decimal("0.010"),  # 2 × 0.005
            Decimal("0.015"),  # 3 × 0.005
            Decimal("0.050"),  # 10 × 0.005
            Decimal("0.125"),  # 25 × 0.005
            Decimal("0.250"),  # 50 × 0.005
        ]

        for target_value in valid_multiples:
            # Should not raise an error
            target = TargetPercentage(target_value)
            assert target.value == target_value

        # Invalid values (not multiples of 0.005)
        invalid_multiples = [
            Decimal("0.001"),  # Too small
            Decimal("0.003"),  # Between 0 and 0.005
            Decimal("0.007"),  # Between 0.005 and 0.010
            Decimal("0.012"),  # Between 0.010 and 0.015
            Decimal("0.123"),  # Random non-multiple
            Decimal("0.127"),  # Close to 0.125 but not exact
        ]

        for target_value in invalid_multiples:
            with pytest.raises(ValidationError, match="must be.*multiple.*0.005"):
                TargetPercentage(target_value)

    def test_zero_target_is_valid(self):
        """Test that zero target percentage is valid."""
        position = Position(
            security_id="STOCK1234567890123456789",
            target=TargetPercentage(Decimal("0")),
            drift_bounds=DriftBounds(
                low_drift=Decimal("0.02"), high_drift=Decimal("0.03")
            ),
        )

        assert position.target.value == Decimal("0")
        assert position.is_zero_target()

    def test_position_can_detect_zero_target(self):
        """Test that position can identify when target is zero."""
        zero_position = Position(
            security_id="STOCK1234567890123456789",
            target=TargetPercentage(Decimal("0")),
            drift_bounds=DriftBounds(
                low_drift=Decimal("0.02"), high_drift=Decimal("0.03")
            ),
        )

        nonzero_position = Position(
            security_id="STOCK1234567890123456789",
            target=TargetPercentage(Decimal("0.15")),
            drift_bounds=DriftBounds(
                low_drift=Decimal("0.02"), high_drift=Decimal("0.03")
            ),
        )

        assert zero_position.is_zero_target() is True
        assert nonzero_position.is_zero_target() is False


class TestPositionDriftBounds:
    """Test Position drift bounds validation."""

    def test_drift_bounds_valid_values(self):
        """Test that drift bounds accept valid values."""
        valid_drift_combinations = [
            (Decimal("0"), Decimal("0")),  # No drift allowed
            (Decimal("0.01"), Decimal("0.01")),  # Equal low and high drift
            (Decimal("0.01"), Decimal("0.02")),  # Low < High
            (Decimal("0"), Decimal("0.05")),  # Zero low drift
            (Decimal("0.02"), Decimal("0.10")),  # Larger drift tolerance
        ]

        for low_drift, high_drift in valid_drift_combinations:
            position = Position(
                security_id="STOCK1234567890123456789",
                target=TargetPercentage(Decimal("0.15")),
                drift_bounds=DriftBounds(low_drift=low_drift, high_drift=high_drift),
            )

            assert position.drift_bounds.low_drift == low_drift
            assert position.drift_bounds.high_drift == high_drift

    def test_drift_bounds_must_be_between_0_and_1(self):
        """Test that drift bounds must be between 0 and 1."""
        # Valid boundary values
        valid_values = [
            Decimal("0"),  # Minimum
            Decimal("0.5"),  # Middle
            Decimal("1.0"),  # Maximum
        ]

        for drift_value in valid_values:
            # Should not raise an error
            DriftBounds(low_drift=drift_value, high_drift=drift_value)

        # Invalid values (outside range)
        invalid_values = [
            Decimal("-0.001"),  # Negative
            Decimal("1.001"),  # Above 100%
            Decimal("2.0"),  # 200%
        ]

        for drift_value in invalid_values:
            with pytest.raises(
                ValidationError, match="Drift bounds must be between 0 and 1"
            ):
                DriftBounds(low_drift=drift_value, high_drift=Decimal("0.05"))

            with pytest.raises(
                ValidationError, match="Drift bounds must be between 0 and 1"
            ):
                DriftBounds(low_drift=Decimal("0.05"), high_drift=drift_value)

    def test_low_drift_cannot_exceed_high_drift(self):
        """Test that low drift cannot be greater than high drift."""
        # Valid combinations (low <= high)
        valid_combinations = [
            (Decimal("0.01"), Decimal("0.01")),  # Equal
            (Decimal("0.01"), Decimal("0.02")),  # Low < High
            (Decimal("0"), Decimal("0.05")),  # Zero low drift
        ]

        for low_drift, high_drift in valid_combinations:
            # Should not raise an error
            DriftBounds(low_drift=low_drift, high_drift=high_drift)

        # Invalid combinations (low > high)
        invalid_combinations = [
            (Decimal("0.03"), Decimal("0.02")),  # Low > High
            (Decimal("0.10"), Decimal("0.05")),  # Much larger low drift
            (Decimal("0.01"), Decimal("0")),  # Low drift but no high drift
        ]

        for low_drift, high_drift in invalid_combinations:
            with pytest.raises(
                ValidationError, match="Low drift cannot exceed high drift"
            ):
                DriftBounds(low_drift=low_drift, high_drift=high_drift)


class TestPositionEquality:
    """Test Position equality and comparison."""

    def test_positions_with_same_security_id_are_equal(self):
        """Test that positions with same security ID are considered equal."""
        position1 = Position(
            security_id="STOCK1234567890123456789",
            target=TargetPercentage(Decimal("0.15")),
            drift_bounds=DriftBounds(
                low_drift=Decimal("0.02"), high_drift=Decimal("0.03")
            ),
        )

        position2 = Position(
            security_id="STOCK1234567890123456789",
            target=TargetPercentage(Decimal("0.20")),  # Different target
            drift_bounds=DriftBounds(
                low_drift=Decimal("0.01"),  # Different drift bounds
                high_drift=Decimal("0.02"),
            ),
        )

        # Positions are equal if they have the same security ID
        assert position1 == position2
        assert hash(position1) == hash(position2)

    def test_positions_with_different_security_id_are_not_equal(self):
        """Test that positions with different security IDs are not equal."""
        position1 = Position(
            security_id="STOCK1234567890123456789",
            target=TargetPercentage(Decimal("0.15")),
            drift_bounds=DriftBounds(
                low_drift=Decimal("0.02"), high_drift=Decimal("0.03")
            ),
        )

        position2 = Position(
            security_id="STOCK9876543210987654321",  # Made exactly 24 characters
            target=TargetPercentage(Decimal("0.15")),  # Same target
            drift_bounds=DriftBounds(
                low_drift=Decimal("0.02"),  # Same drift bounds
                high_drift=Decimal("0.03"),
            ),
        )

        assert position1 != position2
        assert hash(position1) != hash(position2)


class TestPositionStringRepresentation:
    """Test Position string representation."""

    def test_position_string_representation(self):
        """Test that position has meaningful string representation."""
        position = Position(
            security_id="STOCK1234567890123456789",
            target=TargetPercentage(Decimal("0.15")),
            drift_bounds=DriftBounds(
                low_drift=Decimal("0.02"), high_drift=Decimal("0.03")
            ),
        )

        str_repr = str(position)

        # String representation should include key information
        assert "STOCK1234567890123456789" in str_repr
        assert "0.15" in str_repr or "15" in str_repr  # Target percentage
        assert "Position" in str_repr

    def test_position_repr_representation(self):
        """Test that position has meaningful repr representation."""
        position = Position(
            security_id="STOCK1234567890123456789",
            target=TargetPercentage(Decimal("0.15")),
            drift_bounds=DriftBounds(
                low_drift=Decimal("0.02"), high_drift=Decimal("0.03")
            ),
        )

        repr_str = repr(position)

        # Repr should include class name and key information
        assert "Position" in repr_str
        assert "STOCK1234567890123456789" in repr_str


class TestPositionBusinessLogic:
    """Test Position business logic methods."""

    def test_position_can_calculate_drift_tolerance_range(self):
        """Test that position can calculate its drift tolerance range."""
        position = Position(
            security_id="STOCK1234567890123456789",
            target=TargetPercentage(Decimal("0.20")),  # 20%
            drift_bounds=DriftBounds(
                low_drift=Decimal("0.02"), high_drift=Decimal("0.03")  # 2%  # 3%
            ),
        )

        # Calculate acceptable range for a $100,000 portfolio
        market_value = Decimal("100000")

        lower_bound, upper_bound = position.calculate_acceptable_range(market_value)

        # Expected range:
        # Target: $20,000 (20% of $100,000)
        # Lower bound: $20,000 - $2,000 = $18,000 (20% - 2%)
        # Upper bound: $20,000 + $3,000 = $23,000 (20% + 3%)

        expected_lower = market_value * (
            position.target.value - position.drift_bounds.low_drift
        )
        expected_upper = market_value * (
            position.target.value + position.drift_bounds.high_drift
        )

        assert lower_bound == expected_lower
        assert upper_bound == expected_upper

    def test_position_can_check_if_value_within_bounds(self):
        """Test that position can check if a value is within drift bounds."""
        position = Position(
            security_id="STOCK1234567890123456789",
            target=TargetPercentage(Decimal("0.20")),  # 20%
            drift_bounds=DriftBounds(
                low_drift=Decimal("0.02"), high_drift=Decimal("0.03")  # 2%  # 3%
            ),
        )

        market_value = Decimal("100000")

        # Values within bounds (18% to 23% of $100,000)
        values_within_bounds = [
            Decimal("18000"),  # Exactly at lower bound
            Decimal("20000"),  # Exactly at target
            Decimal("21000"),  # Between target and upper bound
            Decimal("23000"),  # Exactly at upper bound
        ]

        for value in values_within_bounds:
            assert position.is_within_drift_bounds(value, market_value) is True

        # Values outside bounds
        values_outside_bounds = [
            Decimal("17999"),  # Below lower bound
            Decimal("15000"),  # Well below lower bound
            Decimal("23001"),  # Above upper bound
            Decimal("25000"),  # Well above upper bound
        ]

        for value in values_outside_bounds:
            assert position.is_within_drift_bounds(value, market_value) is False
