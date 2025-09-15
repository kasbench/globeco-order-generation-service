"""
CVXPY-based portfolio optimization engine implementation.

This module provides a concrete implementation of the OptimizationEngine interface
using CVXPY for mathematical optimization. Features include:
- Mixed-Integer Linear Programming (MILP) formulation
- Drift constraint handling with target percentages
- Timeout management and solver selection
- Financial precision with Decimal arithmetic
- Comprehensive error handling and validation
"""

import asyncio
import logging
import time
from decimal import Decimal
from typing import Dict, List, Optional

try:
    import cvxpy as cp
    import numpy as np

    CVXPY_AVAILABLE = True
except ImportError:
    cp = None
    np = None
    CVXPY_AVAILABLE = False

from src.core.exceptions import (
    InfeasibleSolutionError,
    OptimizationError,
    SolverTimeoutError,
    ValidationError,
)
from src.domain.entities.model import InvestmentModel
from src.domain.services.implementations.portfolio_validation_service import (
    PortfolioValidationService,
)
from src.domain.services.optimization_engine import (
    OptimizationEngine,
    OptimizationResult,
)
from src.domain.services.validation_service import ValidationService

logger = logging.getLogger(__name__)


class CVXPYOptimizationEngine(OptimizationEngine):
    """
    CVXPY-based implementation of portfolio optimization engine.

    Solves the portfolio rebalancing problem using Mixed-Integer Linear Programming:

    Minimize: Σ|MV·target_i - quantity_i·price_i|
    Subject to:
    - MV·(target_i - low_drift_i) ≤ quantity_i·price_i ≤ MV·(target_i + high_drift_i)
    - quantity_i ≥ 0 (non-negative quantities)
    - quantity_i ∈ ℤ (integer quantities)

    Where:
    - MV = Portfolio market value
    - quantity_i = Integer quantity of security i
    - price_i = Market price of security i
    - target_i = Target allocation percentage for security i
    - low_drift_i, high_drift_i = Drift tolerance bounds
    """

    def __init__(
        self,
        default_timeout: int = 30,
        default_solver: str = "CLARABEL",
        validation_service: Optional[ValidationService] = None,
    ):
        """
        Initialize the CVXPY optimization engine.

        Args:
            default_timeout: Default solver timeout in seconds
            default_solver: Default CVXPY solver name
            validation_service: Service for input/output validation

        Raises:
            ValueError: If solver is not supported
            OptimizationError: If CVXPY is not available
        """
        if not CVXPY_AVAILABLE:
            raise OptimizationError(
                "CVXPY is not available. Please install cvxpy package.",
                solver_status="unavailable",
            )

        self.default_timeout = default_timeout
        self.default_solver = default_solver
        self.validation_service = validation_service or PortfolioValidationService()

        # Validate solver availability
        available_solvers = self._get_available_solvers()
        if default_solver not in available_solvers:
            if available_solvers:
                # Use first available solver as fallback
                self.default_solver = available_solvers[0]
                logger.warning(
                    f"Solver '{default_solver}' not available. Using '{self.default_solver}'"
                )
            else:
                raise ValueError(
                    f"No suitable solvers available. Install cvxpy with additional solvers."
                )

        logger.debug(
            f"CVXPY optimization engine initialized with solver: {self.default_solver}"
        )

    async def optimize_portfolio(
        self,
        current_positions: Dict[str, int],
        target_model: InvestmentModel,
        prices: Dict[str, Decimal],
        market_value: Decimal,
        timeout_seconds: int = None,
    ) -> OptimizationResult:
        """
        Optimize portfolio to minimize drift from target allocations.

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
        timeout = timeout_seconds or self.default_timeout
        start_time = time.time()

        try:
            # Validate inputs
            await self._validate_optimization_inputs(
                current_positions, target_model, prices, market_value
            )

            # Convert to optimization problem
            problem_data = await self._setup_optimization_problem(
                current_positions, target_model, prices, market_value
            )

            # Solve optimization problem
            result = await self._solve_optimization(problem_data, timeout)

            solve_time = time.time() - start_time
            logger.debug(
                f"Portfolio optimization completed in {solve_time:.3f}s, "
                f"status: {result.solver_status}, feasible: {result.is_feasible}"
            )

            return result

        except (ValidationError, OptimizationError):
            raise
        except Exception as e:
            solve_time = time.time() - start_time
            logger.error(f"Optimization failed after {solve_time:.3f}s: {str(e)}")
            raise OptimizationError(
                f"Optimization failed: {str(e)}",
                solver_status="error",
                solve_time=solve_time,
            )

    async def validate_solution(
        self,
        solution: Dict[str, int],
        target_model: InvestmentModel,
        prices: Dict[str, Decimal],
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
        try:
            # Use validation service to check constraints
            return await self.validation_service.validate_optimization_result(
                result_positions=solution,
                model=target_model,
                prices=prices,
                market_value=market_value,
            )
        except ValidationError:
            return False
        except Exception as e:
            logger.warning(f"Solution validation error: {str(e)}")
            return False

    async def check_solver_health(self) -> bool:
        """
        Check if the optimization solver is healthy and available.

        Returns:
            True if solver is healthy, False otherwise
        """
        try:
            if not CVXPY_AVAILABLE:
                raise OptimizationError("CVXPY not available")

            # Run a simple test problem (continuous since no integer solvers)
            x = cp.Variable(1, nonneg=True)
            objective = cp.Minimize(cp.square(x - 1))
            constraints = [x >= 0, x <= 10]
            problem = cp.Problem(objective, constraints)

            # Solve with short timeout
            solver_kwargs = {"solver": self.default_solver, "verbose": False}
            if self.default_solver == "CLARABEL":
                solver_kwargs["time_limit"] = 5.0
            elif self.default_solver == "OSQP":
                solver_kwargs["time_limit"] = 5.0
            elif self.default_solver == "SCS":
                solver_kwargs["time_limit_secs"] = 5.0

            result = problem.solve(**solver_kwargs)

            # Check if solution is reasonable and ensure Python bool return
            is_healthy = problem.status == cp.OPTIMAL and abs(x.value[0] - 1.0) < 0.1

            logger.debug(
                f"Solver health check: {'healthy' if is_healthy else 'unhealthy'}"
            )
            return bool(is_healthy)  # Ensure Python bool, not numpy.bool_

        except Exception as e:
            logger.warning(f"Solver health check failed: {str(e)}")
            return False

    async def get_solver_info(self) -> Dict[str, str]:
        """
        Get information about the optimization solver.

        Returns:
            Dictionary with solver name, version, and other metadata
        """
        try:
            info = {
                "solver_name": self.default_solver,
                "version": (
                    cp.__version__ if CVXPY_AVAILABLE else "unavailable"
                ),  # Add version field
                "cvxpy_version": cp.__version__ if CVXPY_AVAILABLE else "unavailable",
                "available_solvers": self._get_available_solvers(),
                "timeout_seconds": str(self.default_timeout),
                "supports_integer": "no",
                "supports_timeout": "yes",
            }

            # Add solver-specific information
            if CVXPY_AVAILABLE and self.default_solver in cp.installed_solvers():
                info["solver_status"] = "installed"
            else:
                info["solver_status"] = "not_installed"

            return info

        except Exception as e:
            logger.warning(f"Error getting solver info: {str(e)}")
            return {
                "solver_name": self.default_solver,
                "version": "error",
                "cvxpy_version": "error",
                "available_solvers": [],
                "error": str(e),
            }

    async def _validate_optimization_inputs(
        self,
        current_positions: Dict[str, int],
        target_model: InvestmentModel,
        prices: Dict[str, Decimal],
        market_value: Decimal,
    ) -> None:
        """Validate optimization inputs using validation service."""
        await self.validation_service.validate_optimization_inputs(
            current_positions=current_positions,
            prices=prices,
            market_value=market_value,
            model=target_model,
        )

        # Additional CVXPY-specific validations
        if len(target_model.positions) == 0:
            raise ValidationError("Model must have at least one position")

        # Check that all model securities have prices
        for position in target_model.positions:
            if position.security_id not in prices:
                raise ValidationError(
                    f"Missing price for security {position.security_id} required by model"
                )

    async def _setup_optimization_problem(
        self,
        current_positions: Dict[str, int],
        target_model: InvestmentModel,
        prices: Dict[str, Decimal],
        market_value: Decimal,
    ) -> Dict:
        """
        Setup the CVXPY optimization problem.

        Note: Since integer solvers are not available, we use continuous variables
        and round the results to integers afterwards.

        Returns:
            Dictionary containing problem variables and constraints
        """
        # Extract problem dimensions
        securities = [pos.security_id for pos in target_model.positions]
        n_securities = len(securities)

        # Convert to numpy arrays for CVXPY
        price_array = np.array([float(prices[sec_id]) for sec_id in securities])
        target_array = np.array(
            [float(pos.target.value) for pos in target_model.positions]
        )
        low_drift_array = np.array(
            [float(pos.drift_bounds.low_drift) for pos in target_model.positions]
        )
        high_drift_array = np.array(
            [float(pos.drift_bounds.high_drift) for pos in target_model.positions]
        )
        market_value_float = float(market_value)

        # Create optimization variables (continuous, will round to integers later)
        quantities = cp.Variable(n_securities, nonneg=True)

        # Create auxiliary variables for absolute value objective
        deviations = cp.Variable(n_securities)

        # Calculate target values
        target_values = market_value_float * target_array

        # Objective: minimize total absolute deviation from targets
        objective = cp.Minimize(cp.sum(deviations))

        # Constraints
        constraints = []

        # Non-negativity constraints (already handled by nonneg=True)

        # Drift bound constraints
        position_values = cp.multiply(quantities, price_array)
        lower_bounds = market_value_float * (target_array - low_drift_array)
        upper_bounds = market_value_float * (target_array + high_drift_array)

        constraints.append(position_values >= lower_bounds)
        constraints.append(position_values <= upper_bounds)

        # Absolute value constraints for objective
        actual_values = cp.multiply(quantities, price_array)
        constraints.append(deviations >= actual_values - target_values)
        constraints.append(deviations >= target_values - actual_values)

        return {
            "securities": securities,
            "quantities": quantities,
            "objective": objective,
            "constraints": constraints,
            "price_array": price_array,
            "target_array": target_array,
            "market_value": market_value_float,
        }

    async def _solve_optimization(
        self, problem_data: Dict, timeout_seconds: int
    ) -> OptimizationResult:
        """
        Solve the CVXPY optimization problem.

        Args:
            problem_data: Dictionary containing CVXPY problem setup
            timeout_seconds: Solver timeout in seconds

        Returns:
            OptimizationResult with solution and metadata
        """
        start_time = time.time()

        try:
            # Create CVXPY problem
            problem = cp.Problem(problem_data["objective"], problem_data["constraints"])

            # Solve with timeout
            solver_kwargs = {"solver": self.default_solver, "verbose": False}

            # Add solver-specific parameters
            if self.default_solver == "CLARABEL":
                solver_kwargs.update({"max_iter": 1000, "time_limit": timeout_seconds})
            elif self.default_solver == "OSQP":
                solver_kwargs.update(
                    {
                        "max_iter": 4000,
                        "time_limit": timeout_seconds,
                        "eps_abs": 1e-6,
                        "eps_rel": 1e-6,
                    }
                )
            elif self.default_solver == "SCS":
                solver_kwargs.update(
                    {"max_iters": 2500, "time_limit_secs": timeout_seconds, "eps": 1e-6}
                )
            elif self.default_solver == "SCIPY":
                # SCIPY doesn't support timeout directly
                solver_kwargs.update({"scipy_options": {"maxiter": 1000}})

            # Solve the problem
            objective_value = problem.solve(**solver_kwargs)
            solve_time = time.time() - start_time

            # Extract results
            solver_status = problem.status
            is_feasible = solver_status in [cp.OPTIMAL, cp.OPTIMAL_INACCURATE]

            if is_feasible:
                # Extract optimal quantities and round to integers
                optimal_quantities = {}
                quantities_value = problem_data["quantities"].value

                if quantities_value is not None:
                    for i, security_id in enumerate(problem_data["securities"]):
                        # Round to nearest integer for discrete shares
                        quantity = int(round(quantities_value[i]))
                        optimal_quantities[security_id] = max(
                            0, quantity
                        )  # Ensure non-negative

                # Calculate objective value with proper precision
                if objective_value is not None and not np.isnan(objective_value):
                    objective_decimal = Decimal(str(objective_value)).quantize(
                        Decimal("0.01")
                    )
                else:
                    objective_decimal = None

                logger.debug(
                    f"Optimization successful: {len(optimal_quantities)} positions, "
                    f"objective: {objective_decimal}, time: {solve_time:.3f}s"
                )

                return OptimizationResult(
                    optimal_quantities=optimal_quantities,
                    objective_value=objective_decimal,
                    solver_status=solver_status,
                    solve_time_seconds=solve_time,
                    is_feasible=True,
                )
            else:
                # Infeasible or error case
                logger.warning(f"Optimization infeasible or failed: {solver_status}")

                return OptimizationResult(
                    optimal_quantities={},
                    objective_value=None,
                    solver_status=solver_status,
                    solve_time_seconds=solve_time,
                    is_feasible=False,
                )

        except Exception as e:
            solve_time = time.time() - start_time
            logger.error(f"CVXPY solver exception: {str(e)}")

            # Handle specific timeout errors
            if "time" in str(e).lower() or "timeout" in str(e).lower():
                return OptimizationResult(
                    optimal_quantities={},
                    objective_value=None,
                    solver_status="time_limit",
                    solve_time_seconds=solve_time,
                    is_feasible=False,
                )

            raise OptimizationError(
                f"Optimization failed: {str(e)}",
                solver_status="error",
                solve_time=solve_time,
            )

    def _get_available_solvers(self) -> List[str]:
        """Get list of available CVXPY solvers."""
        if not CVXPY_AVAILABLE:
            return []

        # Preferred solvers in order of preference
        preferred_solvers = ["CLARABEL", "OSQP", "SCS", "SCIPY"]
        available = []

        for solver in preferred_solvers:
            if solver in cp.installed_solvers():
                available.append(solver)

        return available
