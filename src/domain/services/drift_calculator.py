"""
Drift Calculator interface.

This module defines the drift calculator interface for computing
portfolio drift metrics and position deviations from targets.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal

from src.domain.entities.model import InvestmentModel


@dataclass(frozen=True)
class DriftInfo:
    """Information about position drift from target allocation."""

    security_id: str
    current_value: Decimal  # Current market value of position
    target_value: Decimal  # Target market value based on model
    current_percentage: Decimal  # Current percentage of portfolio
    target_percentage: Decimal  # Target percentage from model
    drift_amount: Decimal  # Actual drift (current - target percentage)
    is_within_bounds: bool  # Whether drift is within acceptable bounds

    def __post_init__(self):
        """Validate drift info data."""
        if len(self.security_id) != 24:
            raise ValueError("Security ID must be exactly 24 characters")

        if self.current_value < 0:
            raise ValueError("Current value cannot be negative")

        if self.target_value < 0:
            raise ValueError("Target value cannot be negative")

        if not (0 <= self.current_percentage <= 1):
            raise ValueError("Current percentage must be between 0 and 1")

        if not (0 <= self.target_percentage <= 1):
            raise ValueError("Target percentage must be between 0 and 1")


class DriftCalculator(ABC):
    """Interface for calculating portfolio drift metrics."""

    @abstractmethod
    async def calculate_portfolio_drift(
        self,
        positions: dict[str, int],
        prices: dict[str, Decimal],
        market_value: Decimal,
        model: InvestmentModel,
    ) -> list[DriftInfo]:
        """
        Calculate drift information for all positions in a portfolio.

        Args:
            positions: Current security quantities {security_id: quantity}
            prices: Current market prices {security_id: price}
            market_value: Total portfolio market value including cash
            model: Investment model with target allocations

        Returns:
            List of DriftInfo objects for each position in the model
        """
        pass

    @abstractmethod
    async def calculate_position_drift(
        self, current_value: Decimal, target_percentage: Decimal, market_value: Decimal
    ) -> Decimal:
        """
        Calculate drift for a single position.

        Drift = (current_value / market_value) - target_percentage

        Args:
            current_value: Current market value of the position
            target_percentage: Target percentage allocation
            market_value: Total portfolio market value

        Returns:
            Drift amount (positive = above target, negative = below target)
        """
        pass

    @abstractmethod
    async def calculate_total_drift(self, drift_infos: list[DriftInfo]) -> Decimal:
        """
        Calculate total portfolio drift as sum of absolute individual drifts.

        Total Drift = Σ|drift_amount_i|

        Args:
            drift_infos: List of individual position drift information

        Returns:
            Total absolute drift for the portfolio
        """
        pass

    @abstractmethod
    async def get_positions_outside_bounds(
        self, drift_infos: list[DriftInfo]
    ) -> list[DriftInfo]:
        """
        Get positions that are outside their acceptable drift bounds.

        Args:
            drift_infos: List of position drift information

        Returns:
            List of DriftInfo for positions outside bounds
        """
        pass

    @abstractmethod
    async def calculate_required_trades(
        self, current_positions: dict[str, int], target_positions: dict[str, int]
    ) -> dict[str, int]:
        """
        Calculate required trades to move from current to target positions.

        Args:
            current_positions: Current security quantities
            target_positions: Target security quantities

        Returns:
            Required trades {security_id: quantity_change}
            Positive = buy, negative = sell, zero = no change
        """
        pass

    @abstractmethod
    async def estimate_trade_costs(
        self,
        trades: dict[str, int],
        prices: dict[str, Decimal],
        commission_rate: Decimal = Decimal("0.001"),  # 0.1% default
    ) -> Decimal:
        """
        Estimate total cost of executing trades.

        Args:
            trades: Required trades {security_id: quantity_change}
            prices: Current market prices
            commission_rate: Commission rate as decimal (e.g., 0.001 = 0.1%)

        Returns:
            Estimated total cost including commissions
        """
        pass
