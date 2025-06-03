"""
InvestmentModel domain entity.

This module contains the InvestmentModel entity which represents an investment
model with target allocations and drift tolerances for portfolio rebalancing.

Business rules:
- Model name must not be empty
- Position targets must sum to ≤ 0.95 (95%)
- Maximum 100 positions with target > 0
- Each security can appear only once
- Positions with target = 0 are automatically removed
- Version-based optimistic locking
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from bson import ObjectId

from src.core.exceptions import BusinessRuleViolationError, ValidationError
from src.domain.entities.position import Position


@dataclass
class InvestmentModel:
    """
    Represents an investment model with target allocations for securities.

    An investment model defines the target allocations and drift tolerances
    for multiple securities and can be associated with multiple portfolios.
    """

    model_id: ObjectId
    name: str
    positions: list[Position] = field(default_factory=list)
    portfolios: list[str] = field(default_factory=list)
    version: int = 1
    last_rebalance_date: datetime | None = None

    # Business rule constants
    MAX_TARGET_SUM = Decimal("0.95")  # 95% maximum target allocation
    MAX_POSITIONS = 100  # Maximum positions with target > 0

    def __post_init__(self):
        """Validate the investment model after initialization."""
        self._validate_name()
        self._validate_positions()
        self._validate_portfolios()

    def _validate_name(self) -> None:
        """Validate that the model name is not empty."""
        if not self.name or not self.name.strip():
            raise ValidationError("Model name cannot be empty")

    def _validate_positions(self) -> None:
        """Validate positions business rules."""
        # Check for duplicate securities
        security_ids = [pos.security_id for pos in self.positions]
        if len(security_ids) != len(set(security_ids)):
            raise BusinessRuleViolationError("Duplicate securities found in model")

        # Validate business rules
        self.validate_all_business_rules()

    def _validate_portfolios(self) -> None:
        """Validate portfolios list."""
        # Check for duplicate portfolios
        if len(self.portfolios) != len(set(self.portfolios)):
            raise BusinessRuleViolationError("Duplicate portfolios found in model")

    def add_position(self, position: Position) -> None:
        """
        Add a position to the model.

        Args:
            position: The position to add

        Raises:
            BusinessRuleViolationError: If business rules are violated
        """
        # Check if security already exists
        if any(pos.security_id == position.security_id for pos in self.positions):
            raise BusinessRuleViolationError(
                f"Security {position.security_id} already exists in model"
            )

        # Check if adding this position would violate target sum rule
        current_sum = self.get_total_target_percentage()
        new_sum = current_sum + position.target.value
        if new_sum > self.MAX_TARGET_SUM:
            raise BusinessRuleViolationError(
                f"Adding position would cause target sum ({new_sum}) to exceed maximum ({self.MAX_TARGET_SUM})"
            )

        # Check if adding this position would violate position count rule
        if not position.is_zero_target():
            nonzero_count = len(self.get_nonzero_target_positions())
            if nonzero_count >= self.MAX_POSITIONS:
                raise BusinessRuleViolationError(
                    f"Maximum of {self.MAX_POSITIONS} positions with non-zero targets allowed"
                )

        # If position has zero target, don't add it (automatic cleanup)
        if not position.is_zero_target():
            self.positions.append(position)

    def update_position(self, updated_position: Position) -> None:
        """
        Update an existing position in the model.

        Args:
            updated_position: The updated position

        Raises:
            ValidationError: If position not found
            BusinessRuleViolationError: If business rules are violated
        """
        # Find existing position
        position_index = None
        for i, pos in enumerate(self.positions):
            if pos.security_id == updated_position.security_id:
                position_index = i
                break

        if position_index is None:
            raise ValidationError(
                f"Position not found for security {updated_position.security_id}"
            )

        # If updated position has zero target, remove it
        if updated_position.is_zero_target():
            self.positions.pop(position_index)
            return

        # Check if updating this position would violate target sum rule
        current_sum = self.get_total_target_percentage()
        old_target = self.positions[position_index].target.value
        new_sum = current_sum - old_target + updated_position.target.value

        if new_sum > self.MAX_TARGET_SUM:
            raise BusinessRuleViolationError(
                f"Updating position would cause target sum ({new_sum}) to exceed maximum ({self.MAX_TARGET_SUM})"
            )

        # Update the position
        self.positions[position_index] = updated_position

    def remove_position(self, security_id: str) -> None:
        """
        Remove a position from the model.

        Args:
            security_id: The security ID to remove

        Raises:
            ValidationError: If position not found
        """
        position_index = None
        for i, pos in enumerate(self.positions):
            if pos.security_id == security_id:
                position_index = i
                break

        if position_index is None:
            raise ValidationError(f"Position not found for security {security_id}")

        self.positions.pop(position_index)

    def add_portfolio(self, portfolio_id: str) -> None:
        """
        Add a portfolio association to the model.

        Args:
            portfolio_id: The portfolio ID to add

        Raises:
            BusinessRuleViolationError: If portfolio already associated
        """
        if portfolio_id in self.portfolios:
            raise BusinessRuleViolationError(
                f"Portfolio {portfolio_id} already associated with model"
            )

        self.portfolios.append(portfolio_id)

    def remove_portfolio(self, portfolio_id: str) -> None:
        """
        Remove a portfolio association from the model.

        Args:
            portfolio_id: The portfolio ID to remove

        Raises:
            ValidationError: If portfolio not found
        """
        if portfolio_id not in self.portfolios:
            raise ValidationError(f"Portfolio {portfolio_id} not found in model")

        self.portfolios.remove(portfolio_id)

    def get_total_target_percentage(self) -> Decimal:
        """Calculate the total target percentage across all positions."""
        return sum(pos.target.value for pos in self.positions)

    def get_nonzero_target_positions(self) -> list[Position]:
        """Get all positions with non-zero target allocations."""
        return [pos for pos in self.positions if not pos.is_zero_target()]

    def validate_target_sum(self) -> None:
        """
        Validate that position targets sum to ≤ 95%.

        Raises:
            BusinessRuleViolationError: If target sum exceeds maximum
        """
        total_target = self.get_total_target_percentage()
        if total_target > self.MAX_TARGET_SUM:
            raise BusinessRuleViolationError(
                f"Position targets sum ({total_target}) exceeds maximum ({self.MAX_TARGET_SUM})"
            )

    def validate_position_count(self) -> None:
        """
        Validate that there are ≤ 100 positions with target > 0.

        Raises:
            BusinessRuleViolationError: If too many positions
        """
        nonzero_positions = self.get_nonzero_target_positions()
        if len(nonzero_positions) > self.MAX_POSITIONS:
            raise BusinessRuleViolationError(
                f"Maximum of {self.MAX_POSITIONS} positions with non-zero targets allowed, found {len(nonzero_positions)}"
            )

    def validate_all_business_rules(self) -> None:
        """
        Validate all business rules for the model.

        Raises:
            BusinessRuleViolationError: If any business rule is violated
        """
        self.validate_target_sum()
        self.validate_position_count()

    def increment_version(self) -> None:
        """Increment the version for optimistic locking."""
        self.version += 1

    def update_last_rebalance_date(self, rebalance_date: datetime) -> None:
        """Update the last rebalance date."""
        self.last_rebalance_date = rebalance_date

    def get_position_by_security_id(self, security_id: str) -> Position | None:
        """Get a position by security ID."""
        for position in self.positions:
            if position.security_id == security_id:
                return position
        return None

    def has_position(self, security_id: str) -> bool:
        """Check if the model has a position for the given security."""
        return self.get_position_by_security_id(security_id) is not None

    def __str__(self) -> str:
        """String representation."""
        return f"InvestmentModel(name='{self.name}', positions={len(self.positions)}, portfolios={len(self.portfolios)})"

    def __repr__(self) -> str:
        """Detailed string representation."""
        return (
            f"InvestmentModel(model_id={self.model_id}, name='{self.name}', "
            f"positions={len(self.positions)}, portfolios={len(self.portfolios)}, version={self.version})"
        )
