"""
Optimization Engine interface.

This module defines the optimization engine interface for portfolio
rebalancing using mathematical optimization algorithms.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal

from src.domain.entities.model import InvestmentModel


@dataclass(frozen=True)
class OptimizationResult:
    """Result of portfolio optimization."""

    optimal_quantities: dict[str, int]  # Security ID -> optimal quantity
    objective_value: Decimal | None  # Objective function value (if feasible)
    solver_status: str  # OPTIMAL, INFEASIBLE, TIMEOUT, etc.
    solve_time_seconds: float  # Time taken to solve
    is_feasible: bool  # Whether a feasible solution was found

    def __post_init__(self):
        """Validate optimization result data."""
        if self.is_feasible and self.objective_value is None:
            raise ValueError("Feasible solution must have objective value")

        if not self.is_feasible and self.optimal_quantities:
            raise ValueError("Infeasible solution should not have optimal quantities")

        if self.solve_time_seconds < 0:
            raise ValueError("Solve time cannot be negative")


class OptimizationEngine(ABC):
    """Interface for portfolio optimization engine."""

    @abstractmethod
    async def optimize_portfolio(
        self,
        current_positions: dict[str, int],
        target_model: InvestmentModel,
        prices: dict[str, Decimal],
        market_value: Decimal,
        timeout_seconds: int = 30,
    ) -> OptimizationResult:
        """
        Optimize portfolio to minimize drift from target allocations.

        Solves the following optimization problem:
        Minimize: Σ|MV·target_i - quantity_i·price_i|
        Subject to:
        - MV·(target_i - low_drift_i) ≤ quantity_i·price_i ≤ MV·(target_i + high_drift_i)
        - quantity_i ≥ 0 (non-negative quantities)
        - quantity_i ∈ ℤ (integer quantities)

        Args:
            current_positions: Current security quantities {security_id: quantity}
            target_model: Investment model with target allocations and drift bounds
            prices: Current market prices {security_id: price}
            market_value: Total portfolio market value including cash
            timeout_seconds: Maximum time allowed for optimization

        Returns:
            OptimizationResult with optimal quantities and metadata

        Raises:
            ValidationError: If inputs are invalid
            OptimizationError: If optimization fails unexpectedly
        """
        pass

    @abstractmethod
    async def validate_solution(
        self,
        solution: dict[str, int],
        target_model: InvestmentModel,
        prices: dict[str, Decimal],
        market_value: Decimal,
    ) -> bool:
        """
        Validate that a solution satisfies all constraints.

        Args:
            solution: Proposed security quantities {security_id: quantity}
            target_model: Investment model with constraints
            prices: Current market prices
            market_value: Total portfolio market value

        Returns:
            True if solution is valid, False otherwise
        """
        pass

    @abstractmethod
    async def check_solver_health(self) -> bool:
        """
        Check if the optimization solver is healthy and available.

        Returns:
            True if solver is healthy, False otherwise
        """
        pass

    @abstractmethod
    async def get_solver_info(self) -> dict[str, str]:
        """
        Get information about the optimization solver.

        Returns:
            Dictionary with solver name, version, and other metadata
        """
        pass
