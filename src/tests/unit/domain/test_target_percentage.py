"""
Tests for TargetPercentage value object.

This module tests the TargetPercentage value object which represents
a target allocation percentage for securities in an investment model.

Following TDD principles, these tests define the business rules and constraints
that the TargetPercentage must satisfy.
"""

from decimal import Decimal

import pytest

from src.core.exceptions import ValidationError
from src.domain.value_objects.target_percentage import TargetPercentage


class TestTargetPercentageCreation:
    """Test TargetPercentage creation and validation."""

    def test_create_target_percentage_with_valid_values(self):
        """Test creating target percentage with valid values."""
        valid_values = [
            Decimal("0"),  # 0%
            Decimal("0.005"),  # 0.5%
            Decimal("0.010"),  # 1.0%
            Decimal("0.050"),  # 5.0%
            Decimal("0.150"),  # 15.0%
            Decimal("0.500"),  # 50.0%
            Decimal("0.950"),  # 95.0% (maximum)
        ]

        for value in valid_values:
            target = TargetPercentage(value)
            assert target.value == value

    def test_target_percentage_must_be_between_0_and_95_percent(self):
        """Test that target percentage must be between 0 and 0.95."""
        # Test boundary values
        boundary_valid = [
            Decimal("0"),  # Minimum
            Decimal("0.950"),  # Maximum
        ]

        for value in boundary_valid:
            target = TargetPercentage(value)
            assert target.value == value

        # Test invalid values
        invalid_values = [
            Decimal("-0.001"),  # Negative
            Decimal("-0.1"),  # More negative
            Decimal("0.951"),  # Just above 95%
            Decimal("1.0"),  # 100%
            Decimal("1.5"),  # 150%
            Decimal("10.0"),  # 1000%
        ]

        for value in invalid_values:
            with pytest.raises(
                ValidationError, match="Target percentage must be between 0 and 0.95"
            ):
                TargetPercentage(value)

    def test_target_percentage_must_be_multiple_of_0_005(self):
        """Test that target percentage must be 0 or multiple of 0.005."""
        # Valid multiples of 0.005
        valid_multiples = [
            Decimal("0"),  # 0 × 0.005
            Decimal("0.005"),  # 1 × 0.005
            Decimal("0.010"),  # 2 × 0.005
            Decimal("0.015"),  # 3 × 0.005
            Decimal("0.020"),  # 4 × 0.005
            Decimal("0.050"),  # 10 × 0.005
            Decimal("0.100"),  # 20 × 0.005
            Decimal("0.125"),  # 25 × 0.005
            Decimal("0.250"),  # 50 × 0.005
            Decimal("0.500"),  # 100 × 0.005
            Decimal("0.950"),  # 190 × 0.005
        ]

        for value in valid_multiples:
            target = TargetPercentage(value)
            assert target.value == value

        # Invalid values (not multiples of 0.005)
        invalid_multiples = [
            Decimal("0.001"),  # Too small
            Decimal("0.002"),  # Too small
            Decimal("0.003"),  # Between 0 and 0.005
            Decimal("0.004"),  # Between 0 and 0.005
            Decimal("0.006"),  # Between 0.005 and 0.010
            Decimal("0.007"),  # Between 0.005 and 0.010
            Decimal("0.008"),  # Between 0.005 and 0.010
            Decimal("0.009"),  # Between 0.005 and 0.010
            Decimal("0.012"),  # Between 0.010 and 0.015
            Decimal("0.123"),  # Random non-multiple
            Decimal("0.127"),  # Close to 0.125 but not exact
            Decimal("0.333"),  # 1/3, not a multiple of 0.005
        ]

        for value in invalid_multiples:
            with pytest.raises(ValidationError, match="must be.*multiple.*0.005"):
                TargetPercentage(value)

    def test_target_percentage_precision_handling(self):
        """Test that target percentage handles decimal precision correctly."""
        # Test values with different decimal precision
        precision_tests = [
            (Decimal("0.005"), Decimal("0.005")),
            (Decimal("0.0050"), Decimal("0.005")),  # Trailing zero
            (Decimal("0.05"), Decimal("0.05")),
            (Decimal("0.050"), Decimal("0.05")),  # Trailing zero
            (Decimal("0.5"), Decimal("0.5")),
            (Decimal("0.500"), Decimal("0.5")),  # Trailing zeros
        ]

        for input_value, expected_value in precision_tests:
            target = TargetPercentage(input_value)
            assert target.value == expected_value

    def test_target_percentage_must_be_decimal_type(self):
        """Test that target percentage requires Decimal type."""
        # Valid Decimal input
        target = TargetPercentage(Decimal("0.15"))
        assert target.value == Decimal("0.15")

        # Invalid input types should be handled by type system
        # (This would be caught by static type checking)
        # But we can test behavior if non-Decimal is passed
        with pytest.raises((TypeError, ValidationError)):
            TargetPercentage(0.15)  # float

        with pytest.raises((TypeError, ValidationError)):
            TargetPercentage("0.15")  # string

        with pytest.raises((TypeError, ValidationError)):
            TargetPercentage(15)  # int


class TestTargetPercentageOperations:
    """Test TargetPercentage operations and methods."""

    def test_target_percentage_equality(self):
        """Test that target percentages can be compared for equality."""
        target1 = TargetPercentage(Decimal("0.15"))
        target2 = TargetPercentage(Decimal("0.15"))
        target3 = TargetPercentage(Decimal("0.20"))

        assert target1 == target2
        assert target1 != target3
        assert target2 != target3

    def test_target_percentage_comparison(self):
        """Test that target percentages can be compared for ordering."""
        target_small = TargetPercentage(Decimal("0.10"))
        target_medium = TargetPercentage(Decimal("0.15"))
        target_large = TargetPercentage(Decimal("0.20"))

        assert target_small < target_medium
        assert target_medium < target_large
        assert target_small < target_large

        assert target_large > target_medium
        assert target_medium > target_small
        assert target_large > target_small

        assert target_small <= target_medium
        assert target_medium <= target_large
        assert target_small <= target_large

        assert target_large >= target_medium
        assert target_medium >= target_small
        assert target_large >= target_small

        # Test equal values
        target_equal = TargetPercentage(Decimal("0.15"))
        assert target_medium <= target_equal
        assert target_medium >= target_equal

    def test_target_percentage_hash(self):
        """Test that target percentages can be hashed for use in sets/dicts."""
        target1 = TargetPercentage(Decimal("0.15"))
        target2 = TargetPercentage(Decimal("0.15"))
        target3 = TargetPercentage(Decimal("0.20"))

        # Equal targets should have same hash
        assert hash(target1) == hash(target2)

        # Different targets should have different hash (usually)
        assert hash(target1) != hash(target3)

        # Should be usable in set
        target_set = {target1, target2, target3}
        assert len(target_set) == 2  # target1 and target2 are equal

    def test_target_percentage_string_representation(self):
        """Test target percentage string representation."""
        target = TargetPercentage(Decimal("0.15"))

        str_repr = str(target)
        assert "0.15" in str_repr or "15" in str_repr

        repr_str = repr(target)
        assert "TargetPercentage" in repr_str
        assert "0.15" in repr_str


class TestTargetPercentageBusinessLogic:
    """Test TargetPercentage business logic methods."""

    def test_is_zero_method(self):
        """Test the is_zero method."""
        zero_target = TargetPercentage(Decimal("0"))
        nonzero_target = TargetPercentage(Decimal("0.15"))

        assert zero_target.is_zero() is True
        assert nonzero_target.is_zero() is False

    def test_to_percentage_string(self):
        """Test conversion to percentage string representation."""
        test_cases = [
            (Decimal("0"), "0.0%"),
            (Decimal("0.05"), "5.0%"),
            (Decimal("0.15"), "15.0%"),
            (Decimal("0.005"), "0.5%"),
            (Decimal("0.125"), "12.5%"),
            (Decimal("0.950"), "95.0%"),
        ]

        for value, expected_string in test_cases:
            target = TargetPercentage(value)
            assert target.to_percentage_string() == expected_string

    def test_calculate_target_value(self):
        """Test calculation of target value given market value."""
        target = TargetPercentage(Decimal("0.20"))  # 20%

        test_cases = [
            (Decimal("100000"), Decimal("20000")),  # $100k → $20k
            (Decimal("50000"), Decimal("10000")),  # $50k → $10k
            (Decimal("1000000"), Decimal("200000")),  # $1M → $200k
            (Decimal("0"), Decimal("0")),  # $0 → $0
        ]

        for market_value, expected_target_value in test_cases:
            calculated_value = target.calculate_target_value(market_value)
            assert calculated_value == expected_target_value

    def test_calculate_percentage_of_value(self):
        """Test calculation of what percentage a value represents of market value."""
        test_cases = [
            (
                Decimal("20000"),
                Decimal("100000"),
                Decimal("0.20"),
            ),  # $20k of $100k = 20%
            (
                Decimal("15000"),
                Decimal("100000"),
                Decimal("0.15"),
            ),  # $15k of $100k = 15%
            (Decimal("0"), Decimal("100000"), Decimal("0")),  # $0 of $100k = 0%
            (
                Decimal("100000"),
                Decimal("100000"),
                Decimal("1.0"),
            ),  # $100k of $100k = 100%
        ]

        for value, market_value, expected_percentage in test_cases:
            calculated_percentage = TargetPercentage.calculate_percentage_of_value(
                value, market_value
            )
            assert calculated_percentage == expected_percentage

    def test_calculate_percentage_of_value_with_zero_market_value(self):
        """Test calculation with zero market value."""
        with pytest.raises(ValidationError, match="Market value cannot be zero"):
            TargetPercentage.calculate_percentage_of_value(
                Decimal("1000"), Decimal("0")
            )

    def test_add_target_percentages(self):
        """Test adding target percentages together."""
        target1 = TargetPercentage(Decimal("0.15"))  # 15%
        target2 = TargetPercentage(Decimal("0.20"))  # 20%

        result = target1.add(target2)
        assert result == Decimal("0.35")  # 35%

        # Test with zero
        zero_target = TargetPercentage(Decimal("0"))
        result_with_zero = target1.add(zero_target)
        assert result_with_zero == Decimal("0.15")

    def test_subtract_target_percentages(self):
        """Test subtracting target percentages."""
        target1 = TargetPercentage(Decimal("0.20"))  # 20%
        target2 = TargetPercentage(Decimal("0.15"))  # 15%

        result = target1.subtract(target2)
        assert result == Decimal("0.05")  # 5%

        # Test subtracting larger from smaller (should not go negative)
        result_reverse = target2.subtract(target1)
        assert result_reverse == Decimal("-0.05")  # -5% (mathematical result)


class TestTargetPercentageEdgeCases:
    """Test TargetPercentage edge cases and boundary conditions."""

    def test_maximum_valid_target_percentage(self):
        """Test the maximum valid target percentage (95%)."""
        max_target = TargetPercentage(Decimal("0.950"))
        assert max_target.value == Decimal("0.950")
        assert max_target.to_percentage_string() == "95.0%"

    def test_minimum_valid_target_percentage(self):
        """Test the minimum valid target percentage (0%)."""
        min_target = TargetPercentage(Decimal("0"))
        assert min_target.value == Decimal("0")
        assert min_target.to_percentage_string() == "0.0%"
        assert min_target.is_zero() is True

    def test_smallest_non_zero_target_percentage(self):
        """Test the smallest valid non-zero target percentage (0.5%)."""
        smallest_target = TargetPercentage(Decimal("0.005"))
        assert smallest_target.value == Decimal("0.005")
        assert smallest_target.to_percentage_string() == "0.5%"
        assert smallest_target.is_zero() is False

    def test_target_percentage_with_many_decimal_places(self):
        """Test target percentage with high precision input."""
        # Should still validate to be a multiple of 0.005
        high_precision_valid = Decimal("0.125000000000000")
        target = TargetPercentage(high_precision_valid)
        assert target.value == Decimal("0.125")

        # High precision invalid should still fail
        high_precision_invalid = Decimal("0.123456789012345")
        with pytest.raises(ValidationError, match="must be.*multiple.*0.005"):
            TargetPercentage(high_precision_invalid)

    def test_target_percentage_immutability(self):
        """Test that TargetPercentage is immutable."""
        target = TargetPercentage(Decimal("0.15"))
        original_value = target.value

        # Value should not be modifiable
        # (This is enforced by Python's property system and dataclass frozen=True)
        with pytest.raises(AttributeError):
            target.value = Decimal("0.20")

        # Original value should remain unchanged
        assert target.value == original_value
