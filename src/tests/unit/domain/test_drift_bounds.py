"""
Tests for DriftBounds value object.

This module tests the DriftBounds value object which represents
drift tolerance bounds for securities in an investment model.

Following TDD principles, these tests define the business rules and constraints
that the DriftBounds must satisfy.
"""

from decimal import Decimal

import pytest

from src.core.exceptions import ValidationError
from src.domain.value_objects.drift_bounds import DriftBounds


class TestDriftBoundsCreation:
    """Test DriftBounds creation and validation."""

    def test_create_drift_bounds_with_valid_values(self):
        """Test creating drift bounds with valid values."""
        valid_combinations = [
            (Decimal("0"), Decimal("0")),  # No drift allowed
            (Decimal("0.01"), Decimal("0.01")),  # Equal low and high drift
            (Decimal("0.01"), Decimal("0.02")),  # Low < High
            (Decimal("0"), Decimal("0.05")),  # Zero low drift
            (Decimal("0.02"), Decimal("0.10")),  # Larger drift tolerance
            (Decimal("0.5"), Decimal("1.0")),  # Large drift bounds
            (Decimal("1.0"), Decimal("1.0")),  # Maximum drift bounds
        ]

        for low_drift, high_drift in valid_combinations:
            bounds = DriftBounds(low_drift=low_drift, high_drift=high_drift)
            assert bounds.low_drift == low_drift
            assert bounds.high_drift == high_drift

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
            Decimal("-0.1"),  # More negative
            Decimal("1.001"),  # Above 100%
            Decimal("2.0"),  # 200%
            Decimal("10.0"),  # 1000%
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
            (Decimal("0"), Decimal("0")),  # Both zero
            (Decimal("0.5"), Decimal("1.0")),  # Large difference
        ]

        for low_drift, high_drift in valid_combinations:
            # Should not raise an error
            bounds = DriftBounds(low_drift=low_drift, high_drift=high_drift)
            assert bounds.low_drift == low_drift
            assert bounds.high_drift == high_drift

        # Invalid combinations (low > high)
        invalid_combinations = [
            (Decimal("0.03"), Decimal("0.02")),  # Low > High
            (Decimal("0.10"), Decimal("0.05")),  # Much larger low drift
            (Decimal("0.01"), Decimal("0")),  # Low drift but no high drift
            (Decimal("1.0"), Decimal("0.5")),  # Large low, smaller high
        ]

        for low_drift, high_drift in invalid_combinations:
            with pytest.raises(
                ValidationError, match="Low drift cannot exceed high drift"
            ):
                DriftBounds(low_drift=low_drift, high_drift=high_drift)

    def test_drift_bounds_must_be_decimal_type(self):
        """Test that drift bounds require Decimal type."""
        # Valid Decimal input
        bounds = DriftBounds(low_drift=Decimal("0.02"), high_drift=Decimal("0.03"))
        assert bounds.low_drift == Decimal("0.02")
        assert bounds.high_drift == Decimal("0.03")

        # Invalid input types should be handled by type system
        with pytest.raises((TypeError, ValidationError)):
            DriftBounds(low_drift=0.02, high_drift=0.03)  # float

        with pytest.raises((TypeError, ValidationError)):
            DriftBounds(low_drift="0.02", high_drift="0.03")  # string

        with pytest.raises((TypeError, ValidationError)):
            DriftBounds(low_drift=2, high_drift=3)  # int


class TestDriftBoundsEquality:
    """Test DriftBounds equality and comparison."""

    def test_drift_bounds_equality(self):
        """Test that drift bounds can be compared for equality."""
        bounds1 = DriftBounds(low_drift=Decimal("0.02"), high_drift=Decimal("0.03"))
        bounds2 = DriftBounds(low_drift=Decimal("0.02"), high_drift=Decimal("0.03"))
        bounds3 = DriftBounds(low_drift=Decimal("0.01"), high_drift=Decimal("0.02"))

        assert bounds1 == bounds2
        assert bounds1 != bounds3
        assert bounds2 != bounds3

    def test_drift_bounds_hash(self):
        """Test that drift bounds can be hashed for use in sets/dicts."""
        bounds1 = DriftBounds(low_drift=Decimal("0.02"), high_drift=Decimal("0.03"))
        bounds2 = DriftBounds(low_drift=Decimal("0.02"), high_drift=Decimal("0.03"))
        bounds3 = DriftBounds(low_drift=Decimal("0.01"), high_drift=Decimal("0.02"))

        # Equal bounds should have same hash
        assert hash(bounds1) == hash(bounds2)

        # Different bounds should have different hash (usually)
        assert hash(bounds1) != hash(bounds3)

        # Should be usable in set
        bounds_set = {bounds1, bounds2, bounds3}
        assert len(bounds_set) == 2  # bounds1 and bounds2 are equal

    def test_drift_bounds_string_representation(self):
        """Test drift bounds string representation."""
        bounds = DriftBounds(low_drift=Decimal("0.02"), high_drift=Decimal("0.03"))

        str_repr = str(bounds)
        assert "0.02" in str_repr
        assert "0.03" in str_repr

        repr_str = repr(bounds)
        assert "DriftBounds" in repr_str
        assert "0.02" in repr_str
        assert "0.03" in repr_str


class TestDriftBoundsBusinessLogic:
    """Test DriftBounds business logic methods."""

    def test_calculate_drift_range(self):
        """Test calculation of drift range for given target and market value."""
        bounds = DriftBounds(low_drift=Decimal("0.02"), high_drift=Decimal("0.03"))
        target_percentage = Decimal("0.20")  # 20%
        market_value = Decimal("100000")  # $100,000

        lower_bound, upper_bound = bounds.calculate_drift_range(
            target_percentage, market_value
        )

        # Expected calculations:
        # Target value: $100,000 × 20% = $20,000
        # Lower bound: $20,000 - ($100,000 × 2%) = $20,000 - $2,000 = $18,000
        # Upper bound: $20,000 + ($100,000 × 3%) = $20,000 + $3,000 = $23,000

        expected_target_value = market_value * target_percentage
        expected_lower = expected_target_value - (market_value * bounds.low_drift)
        expected_upper = expected_target_value + (market_value * bounds.high_drift)

        assert lower_bound == expected_lower
        assert upper_bound == expected_upper

    def test_calculate_drift_range_with_zero_target(self):
        """Test drift range calculation with zero target percentage."""
        bounds = DriftBounds(low_drift=Decimal("0.02"), high_drift=Decimal("0.03"))
        target_percentage = Decimal("0")  # 0%
        market_value = Decimal("100000")  # $100,000

        lower_bound, upper_bound = bounds.calculate_drift_range(
            target_percentage, market_value
        )

        # With 0% target:
        # Target value: $0
        # Lower bound: $0 - $2,000 = -$2,000 (but should be 0 minimum)
        # Upper bound: $0 + $3,000 = $3,000

        expected_lower = Decimal("0") - (
            market_value * bounds.low_drift
        )  # Could be negative
        expected_upper = Decimal("0") + (market_value * bounds.high_drift)

        assert lower_bound == expected_lower
        assert upper_bound == expected_upper

    def test_calculate_drift_range_with_zero_drift(self):
        """Test drift range calculation with zero drift bounds."""
        bounds = DriftBounds(low_drift=Decimal("0"), high_drift=Decimal("0"))
        target_percentage = Decimal("0.20")  # 20%
        market_value = Decimal("100000")  # $100,000

        lower_bound, upper_bound = bounds.calculate_drift_range(
            target_percentage, market_value
        )

        # With 0% drift:
        # Target value: $20,000
        # Lower bound: $20,000 - $0 = $20,000
        # Upper bound: $20,000 + $0 = $20,000

        expected_target_value = market_value * target_percentage

        assert lower_bound == expected_target_value
        assert upper_bound == expected_target_value

    def test_is_within_bounds(self):
        """Test checking if a value is within drift bounds."""
        bounds = DriftBounds(low_drift=Decimal("0.02"), high_drift=Decimal("0.03"))
        target_percentage = Decimal("0.20")  # 20%
        market_value = Decimal("100000")  # $100,000

        # Calculate expected bounds: $18,000 to $23,000
        lower_bound, upper_bound = bounds.calculate_drift_range(
            target_percentage, market_value
        )

        # Values within bounds
        values_within_bounds = [
            Decimal("18000"),  # Exactly at lower bound
            Decimal("20000"),  # Exactly at target
            Decimal("21000"),  # Between target and upper bound
            Decimal("23000"),  # Exactly at upper bound
            Decimal("19500"),  # Arbitrary value within bounds
        ]

        for value in values_within_bounds:
            assert (
                bounds.is_within_bounds(value, target_percentage, market_value) is True
            )

        # Values outside bounds
        values_outside_bounds = [
            Decimal("17999"),  # Below lower bound
            Decimal("15000"),  # Well below lower bound
            Decimal("23001"),  # Above upper bound
            Decimal("25000"),  # Well above upper bound
            Decimal("0"),  # Far below
            Decimal("50000"),  # Far above
        ]

        for value in values_outside_bounds:
            assert (
                bounds.is_within_bounds(value, target_percentage, market_value) is False
            )

    def test_calculate_current_drift(self):
        """Test calculation of current drift from target."""
        bounds = DriftBounds(low_drift=Decimal("0.02"), high_drift=Decimal("0.03"))
        target_percentage = Decimal("0.20")  # 20%
        market_value = Decimal("100000")  # $100,000

        test_cases = [
            (Decimal("20000"), Decimal("0")),  # At target, no drift
            (Decimal("22000"), Decimal("0.02")),  # $2k above, 2% drift up
            (Decimal("18000"), Decimal("-0.02")),  # $2k below, 2% drift down
            (Decimal("25000"), Decimal("0.05")),  # $5k above, 5% drift up
            (Decimal("15000"), Decimal("-0.05")),  # $5k below, 5% drift down
            (Decimal("0"), Decimal("-0.20")),  # All the way down, 20% drift down
        ]

        for current_value, expected_drift in test_cases:
            calculated_drift = bounds.calculate_current_drift(
                current_value, target_percentage, market_value
            )
            assert calculated_drift == expected_drift

    def test_get_drift_tolerance_as_percentage(self):
        """Test conversion of drift bounds to percentage strings."""
        bounds = DriftBounds(low_drift=Decimal("0.02"), high_drift=Decimal("0.03"))

        low_percentage = bounds.get_low_drift_as_percentage()
        high_percentage = bounds.get_high_drift_as_percentage()

        assert low_percentage == "2.0%"
        assert high_percentage == "3.0%"

        # Test with different values
        bounds_zero = DriftBounds(low_drift=Decimal("0"), high_drift=Decimal("0"))
        assert bounds_zero.get_low_drift_as_percentage() == "0.0%"
        assert bounds_zero.get_high_drift_as_percentage() == "0.0%"

        bounds_large = DriftBounds(
            low_drift=Decimal("0.15"), high_drift=Decimal("0.25")
        )
        assert bounds_large.get_low_drift_as_percentage() == "15.0%"
        assert bounds_large.get_high_drift_as_percentage() == "25.0%"

    def test_is_symmetric(self):
        """Test checking if drift bounds are symmetric."""
        symmetric_bounds = DriftBounds(
            low_drift=Decimal("0.02"), high_drift=Decimal("0.02")
        )
        asymmetric_bounds = DriftBounds(
            low_drift=Decimal("0.02"), high_drift=Decimal("0.03")
        )

        assert symmetric_bounds.is_symmetric() is True
        assert asymmetric_bounds.is_symmetric() is False

        # Edge case: zero bounds
        zero_bounds = DriftBounds(low_drift=Decimal("0"), high_drift=Decimal("0"))
        assert zero_bounds.is_symmetric() is True

    def test_get_total_drift_tolerance(self):
        """Test calculation of total drift tolerance range."""
        bounds = DriftBounds(low_drift=Decimal("0.02"), high_drift=Decimal("0.03"))

        total_tolerance = bounds.get_total_drift_tolerance()
        expected_total = bounds.low_drift + bounds.high_drift

        assert total_tolerance == expected_total
        assert total_tolerance == Decimal("0.05")  # 2% + 3% = 5%

        # Test with equal bounds
        symmetric_bounds = DriftBounds(
            low_drift=Decimal("0.025"), high_drift=Decimal("0.025")
        )
        symmetric_total = symmetric_bounds.get_total_drift_tolerance()
        assert symmetric_total == Decimal("0.05")  # 2.5% + 2.5% = 5%


class TestDriftBoundsEdgeCases:
    """Test DriftBounds edge cases and boundary conditions."""

    def test_maximum_drift_bounds(self):
        """Test the maximum valid drift bounds (100%)."""
        max_bounds = DriftBounds(low_drift=Decimal("1.0"), high_drift=Decimal("1.0"))
        assert max_bounds.low_drift == Decimal("1.0")
        assert max_bounds.high_drift == Decimal("1.0")
        assert max_bounds.is_symmetric() is True

    def test_minimum_drift_bounds(self):
        """Test the minimum valid drift bounds (0%)."""
        min_bounds = DriftBounds(low_drift=Decimal("0"), high_drift=Decimal("0"))
        assert min_bounds.low_drift == Decimal("0")
        assert min_bounds.high_drift == Decimal("0")
        assert min_bounds.is_symmetric() is True

    def test_asymmetric_maximum_bounds(self):
        """Test asymmetric drift bounds at maximum values."""
        asymmetric_bounds = DriftBounds(
            low_drift=Decimal("0"), high_drift=Decimal("1.0")
        )
        assert asymmetric_bounds.low_drift == Decimal("0")
        assert asymmetric_bounds.high_drift == Decimal("1.0")
        assert asymmetric_bounds.is_symmetric() is False

    def test_drift_bounds_with_high_precision(self):
        """Test drift bounds with high precision decimal values."""
        high_precision_bounds = DriftBounds(
            low_drift=Decimal("0.012345678901234567890"),
            high_drift=Decimal("0.023456789012345678901"),
        )

        # Values should be preserved with high precision
        assert str(high_precision_bounds.low_drift) == "0.012345678901234567890"
        assert str(high_precision_bounds.high_drift) == "0.023456789012345678901"

    def test_drift_bounds_immutability(self):
        """Test that DriftBounds is immutable."""
        bounds = DriftBounds(low_drift=Decimal("0.02"), high_drift=Decimal("0.03"))
        original_low = bounds.low_drift
        original_high = bounds.high_drift

        # Values should not be modifiable
        with pytest.raises(AttributeError):
            bounds.low_drift = Decimal("0.05")

        with pytest.raises(AttributeError):
            bounds.high_drift = Decimal("0.05")

        # Original values should remain unchanged
        assert bounds.low_drift == original_low
        assert bounds.high_drift == original_high

    def test_drift_calculation_edge_cases(self):
        """Test drift calculation with edge case values."""
        bounds = DriftBounds(low_drift=Decimal("0.1"), high_drift=Decimal("0.2"))

        # Edge case: zero market value
        with pytest.raises(ValidationError, match="Market value cannot be zero"):
            bounds.calculate_drift_range(Decimal("0.2"), Decimal("0"))

        # Edge case: zero target with large drift
        target_zero = Decimal("0")
        market_value = Decimal("100000")

        lower_bound, upper_bound = bounds.calculate_drift_range(
            target_zero, market_value
        )

        # Should allow negative lower bound mathematically
        assert lower_bound == Decimal("-10000")  # 0 - 10% of 100k
        assert upper_bound == Decimal("20000")  # 0 + 20% of 100k
