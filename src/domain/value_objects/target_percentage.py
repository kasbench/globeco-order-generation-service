"""
TargetPercentage value object.

This module contains the TargetPercentage value object which represents
a target allocation percentage for securities in an investment model.

Business rules:
- Must be between 0 and 0.95 (95%)
- Must be 0 or a multiple of 0.005 (0.5%)
- Immutable value object
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import ClassVar

from src.core.exceptions import ValidationError


@dataclass(frozen=True)
class TargetPercentage:
    """
    Represents a target allocation percentage for a security.

    Target percentages must be between 0 and 0.95 (95%) and must be
    either 0 or a multiple of 0.005 (0.5%).
    """

    value: Decimal

    # Class constants
    MIN_VALUE: ClassVar[Decimal] = Decimal("0")
    MAX_VALUE: ClassVar[Decimal] = Decimal("0.95")
    INCREMENT: ClassVar[Decimal] = Decimal("0.005")

    def __post_init__(self):
        """Validate the target percentage value after initialization."""
        self._validate_value()

    def _validate_value(self) -> None:
        """Validate that the target percentage meets business rules."""
        if not isinstance(self.value, Decimal):
            raise ValidationError("Target percentage must be a Decimal")

        # Check range
        if not (self.MIN_VALUE <= self.value <= self.MAX_VALUE):
            raise ValidationError(
                f"Target percentage must be between {self.MIN_VALUE} and {self.MAX_VALUE}"
            )

        # Check if it's a multiple of 0.005 (unless it's zero)
        if self.value != Decimal("0"):
            remainder = self.value % self.INCREMENT
            if remainder != Decimal("0"):
                raise ValidationError(
                    f"Target percentage must be 0 or a multiple of {self.INCREMENT}"
                )

    def is_zero(self) -> bool:
        """Check if the target percentage is zero."""
        return self.value == Decimal("0")

    def to_percentage_string(self) -> str:
        """Convert to percentage string representation."""
        percentage = self.value * 100

        # Handle special case for zero
        if percentage == 0:
            return "0.0%"

        # Format with minimal decimal places but at least one
        # Remove trailing zeros but keep at least one decimal place
        formatted = f"{percentage:.3f}".rstrip('0').rstrip('.')
        if '.' not in formatted:
            formatted += ".0"

        return f"{formatted}%"

    def calculate_target_value(self, market_value: Decimal) -> Decimal:
        """Calculate the target value given a market value."""
        return market_value * self.value

    @classmethod
    def calculate_percentage_of_value(
        cls, value: Decimal, market_value: Decimal
    ) -> Decimal:
        """Calculate what percentage a value represents of market value."""
        if market_value == Decimal("0"):
            raise ValidationError("Market value cannot be zero")
        return value / market_value

    def add(self, other: 'TargetPercentage') -> Decimal:
        """Add this target percentage to another and return the result."""
        return self.value + other.value

    def subtract(self, other: 'TargetPercentage') -> Decimal:
        """Subtract another target percentage from this one and return the result."""
        return self.value - other.value

    def __str__(self) -> str:
        """String representation."""
        return f"TargetPercentage({self.value})"

    def __repr__(self) -> str:
        """Detailed string representation."""
        return f"TargetPercentage(value={self.value})"

    def __lt__(self, other: 'TargetPercentage') -> bool:
        """Less than comparison."""
        return self.value < other.value

    def __le__(self, other: 'TargetPercentage') -> bool:
        """Less than or equal comparison."""
        return self.value <= other.value

    def __gt__(self, other: 'TargetPercentage') -> bool:
        """Greater than comparison."""
        return self.value > other.value

    def __ge__(self, other: 'TargetPercentage') -> bool:
        """Greater than or equal comparison."""
        return self.value >= other.value

    def __hash__(self) -> int:
        """Hash for use in sets and dictionaries."""
        return hash(self.value)
