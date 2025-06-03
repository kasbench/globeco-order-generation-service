"""
Position domain entity.

This module contains the Position entity which represents a security position
within an investment model, including target allocation and drift tolerances.

Business rules:
- Security ID must be exactly 24 alphanumeric characters
- Target percentage must follow TargetPercentage rules
- Drift bounds must follow DriftBounds rules
- Positions are equal if they have the same security ID
"""

import re
from dataclasses import dataclass
from decimal import Decimal

from src.core.exceptions import ValidationError
from src.domain.value_objects.drift_bounds import DriftBounds
from src.domain.value_objects.target_percentage import TargetPercentage


@dataclass(frozen=True)
class Position:
    """
    Represents a security position within an investment model.

    A position defines the target allocation and drift tolerances
    for a specific security within a portfolio model.
    """

    security_id: str
    target: TargetPercentage
    drift_bounds: DriftBounds

    def __post_init__(self):
        """Validate the position after initialization."""
        self._validate_security_id()

    def _validate_security_id(self) -> None:
        """Validate that the security ID meets business rules."""
        if not isinstance(self.security_id, str):
            raise ValidationError("Security ID must be a string")

        # Check length
        if len(self.security_id) != 24:
            raise ValidationError("Security ID must be exactly 24 characters")

        # Check alphanumeric
        if not re.match(r'^[A-Za-z0-9]+$', self.security_id):
            raise ValidationError(
                "Security ID must contain only alphanumeric characters"
            )

    def is_zero_target(self) -> bool:
        """Check if this position has a zero target allocation."""
        return self.target.is_zero()

    def calculate_acceptable_range(
        self, market_value: Decimal
    ) -> tuple[Decimal, Decimal]:
        """
        Calculate the acceptable value range for this position given market value.

        Args:
            market_value: Total portfolio market value

        Returns:
            Tuple of (lower_bound, upper_bound) in dollar amounts
        """
        return self.drift_bounds.calculate_drift_range(self.target.value, market_value)

    def is_within_drift_bounds(
        self, current_value: Decimal, market_value: Decimal
    ) -> bool:
        """
        Check if a current position value is within this position's drift bounds.

        Args:
            current_value: Current position value in dollars
            market_value: Total portfolio market value

        Returns:
            True if within bounds, False otherwise
        """
        return self.drift_bounds.is_within_bounds(
            current_value, self.target.value, market_value
        )

    def calculate_current_drift(
        self, current_value: Decimal, market_value: Decimal
    ) -> Decimal:
        """
        Calculate the current drift from target for this position.

        Args:
            current_value: Current position value in dollars
            market_value: Total portfolio market value

        Returns:
            Current drift as a percentage
        """
        return self.drift_bounds.calculate_current_drift(
            current_value, self.target.value, market_value
        )

    def get_target_value(self, market_value: Decimal) -> Decimal:
        """Calculate the target value for this position given market value."""
        return self.target.calculate_target_value(market_value)

    def __str__(self) -> str:
        """String representation."""
        return f"Position({self.security_id}, target={self.target.value})"

    def __repr__(self) -> str:
        """Detailed string representation."""
        return (
            f"Position(security_id='{self.security_id}', "
            f"target={self.target}, drift_bounds={self.drift_bounds})"
        )

    def __eq__(self, other) -> bool:
        """
        Equality based on security ID only.

        Two positions are considered equal if they have the same security ID,
        regardless of their target allocation or drift bounds.
        """
        if not isinstance(other, Position):
            return False
        return self.security_id == other.security_id

    def __hash__(self) -> int:
        """Hash based on security ID only for use in sets and dictionaries."""
        return hash(self.security_id)
