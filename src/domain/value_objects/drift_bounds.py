"""
DriftBounds value object.

This module contains the DriftBounds value object which represents
drift tolerance bounds for securities in an investment model.

Business rules:
- Both low_drift and high_drift must be between 0 and 1 (100%)
- low_drift cannot exceed high_drift
- Immutable value object
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import ClassVar

from src.core.exceptions import ValidationError


@dataclass(frozen=True)
class DriftBounds:
    """
    Represents drift tolerance bounds for a security position.

    Drift bounds define the acceptable range around the target allocation
    before rebalancing is required.
    """

    low_drift: Decimal
    high_drift: Decimal

    # Class constants
    MIN_DRIFT: ClassVar[Decimal] = Decimal("0")
    MAX_DRIFT: ClassVar[Decimal] = Decimal("1.0")

    def __post_init__(self):
        """Validate the drift bounds after initialization."""
        self._validate_bounds()

    def _validate_bounds(self) -> None:
        """Validate that the drift bounds meet business rules."""
        if not isinstance(self.low_drift, Decimal):
            raise ValidationError("Low drift must be a Decimal")

        if not isinstance(self.high_drift, Decimal):
            raise ValidationError("High drift must be a Decimal")

        # Check range for low drift
        if not (self.MIN_DRIFT <= self.low_drift <= self.MAX_DRIFT):
            raise ValidationError(
                f"Drift bounds must be between {self.MIN_DRIFT} and {self.MAX_DRIFT}"
            )

        # Check range for high drift
        if not (self.MIN_DRIFT <= self.high_drift <= self.MAX_DRIFT):
            raise ValidationError(
                f"Drift bounds must be between {self.MIN_DRIFT} and {self.MAX_DRIFT}"
            )

        # Check that low drift doesn't exceed high drift
        if self.low_drift > self.high_drift:
            raise ValidationError("Low drift cannot exceed high drift")

    def calculate_drift_range(
        self, target_percentage: Decimal, market_value: Decimal
    ) -> tuple[Decimal, Decimal]:
        """
        Calculate the acceptable drift range for given target and market value.

        Args:
            target_percentage: The target allocation percentage (0-1)
            market_value: The total portfolio market value

        Returns:
            Tuple of (lower_bound, upper_bound) in dollar amounts
        """
        if market_value == Decimal("0"):
            raise ValidationError("Market value cannot be zero")

        target_value = market_value * target_percentage

        lower_bound = target_value - (market_value * self.low_drift)
        upper_bound = target_value + (market_value * self.high_drift)

        return lower_bound, upper_bound

    def is_within_bounds(
        self, current_value: Decimal, target_percentage: Decimal, market_value: Decimal
    ) -> bool:
        """
        Check if a current position value is within the drift bounds.

        Args:
            current_value: Current position value in dollars
            target_percentage: Target allocation percentage (0-1)
            market_value: Total portfolio market value

        Returns:
            True if within bounds, False otherwise
        """
        lower_bound, upper_bound = self.calculate_drift_range(
            target_percentage, market_value
        )
        return lower_bound <= current_value <= upper_bound

    def calculate_current_drift(
        self, current_value: Decimal, target_percentage: Decimal, market_value: Decimal
    ) -> Decimal:
        """
        Calculate the current drift from target as a percentage.

        Args:
            current_value: Current position value in dollars
            target_percentage: Target allocation percentage (0-1)
            market_value: Total portfolio market value

        Returns:
            Current drift as a percentage (positive = above target, negative = below target)
        """
        target_value = market_value * target_percentage
        drift_value = current_value - target_value

        # Convert to percentage of market value
        return drift_value / market_value

    def get_low_drift_as_percentage(self) -> str:
        """Get the low drift as a percentage string."""
        percentage = self.low_drift * 100

        # Format with minimal decimal places but at least one
        formatted = f"{percentage:.2f}".rstrip('0').rstrip('.')
        if '.' not in formatted:
            formatted += ".0"

        return f"{formatted}%"

    def get_high_drift_as_percentage(self) -> str:
        """Get the high drift as a percentage string."""
        percentage = self.high_drift * 100

        # Format with minimal decimal places but at least one
        formatted = f"{percentage:.2f}".rstrip('0').rstrip('.')
        if '.' not in formatted:
            formatted += ".0"

        return f"{formatted}%"

    def is_symmetric(self) -> bool:
        """Check if the drift bounds are symmetric (low_drift == high_drift)."""
        return self.low_drift == self.high_drift

    def get_total_drift_tolerance(self) -> Decimal:
        """Get the total drift tolerance range (low_drift + high_drift)."""
        return self.low_drift + self.high_drift

    def __str__(self) -> str:
        """String representation."""
        return f"DriftBounds(low={self.low_drift}, high={self.high_drift})"

    def __repr__(self) -> str:
        """Detailed string representation."""
        return f"DriftBounds(low_drift={self.low_drift}, high_drift={self.high_drift})"

    def __hash__(self) -> int:
        """Hash for use in sets and dictionaries."""
        return hash((self.low_drift, self.high_drift))
