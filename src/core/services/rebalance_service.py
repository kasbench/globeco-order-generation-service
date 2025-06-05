"""
Portfolio rebalancing service implementation.

This module provides the application service layer for portfolio rebalancing operations,
coordinating between optimization engine, external services, and domain logic.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List

import structlog

from src.core.exceptions import (
    ExternalServiceError,
    ModelNotFoundError,
    OptimizationError,
    PortfolioNotFoundError,
)
from src.core.mappers import RebalanceMapper
from src.domain.repositories.model_repository import ModelRepository
from src.domain.services.implementations.portfolio_drift_calculator import (
    PortfolioDriftCalculator,
)
from src.infrastructure.external.portfolio_accounting_client import (
    PortfolioAccountingClient,
)
from src.infrastructure.external.pricing_client import PricingServiceClient
from src.infrastructure.optimization.cvxpy_solver import CVXPYOptimizationEngine
from src.schemas.rebalance import DriftDTO, RebalanceDTO
from src.schemas.transactions import TransactionDTO, TransactionType

logger = structlog.get_logger(__name__)


class RebalanceService:
    """Service for portfolio rebalancing operations."""

    def __init__(
        self,
        model_repository: ModelRepository,
        optimization_engine: CVXPYOptimizationEngine,
        drift_calculator: PortfolioDriftCalculator,
        portfolio_accounting_client: PortfolioAccountingClient,
        pricing_client: PricingServiceClient,
        rebalance_mapper: RebalanceMapper,
        max_workers: int = 4,
    ):
        """Initialize the rebalance service.

        Args:
            model_repository: Repository for accessing investment models
            optimization_engine: Mathematical optimization engine
            drift_calculator: Portfolio drift calculation service
            portfolio_accounting_client: Client for portfolio position data
            pricing_client: Client for security pricing data
            rebalance_mapper: Mapper for rebalancing DTOs
            max_workers: Maximum parallel workers for multi-portfolio rebalancing
        """
        self._model_repository = model_repository
        self._optimization_engine = optimization_engine
        self._drift_calculator = drift_calculator
        self._portfolio_accounting_client = portfolio_accounting_client
        self._pricing_client = pricing_client
        self._rebalance_mapper = rebalance_mapper
        self._thread_pool = ThreadPoolExecutor(max_workers=max_workers)

    async def rebalance_portfolio(self, portfolio_id: str) -> RebalanceDTO:
        """Rebalance a single portfolio using its associated investment model.

        Args:
            portfolio_id: Portfolio identifier

        Returns:
            RebalanceDTO with transactions and drift information

        Raises:
            PortfolioNotFoundError: If portfolio doesn't exist
            ModelNotFoundError: If portfolio's model doesn't exist
            OptimizationError: If optimization fails
            ExternalServiceError: If external services are unavailable
        """
        logger.info("Starting portfolio rebalancing", portfolio_id=portfolio_id)

        try:
            # Get portfolio's associated model
            model = await self._get_portfolio_model(portfolio_id)

            # Get current portfolio positions
            current_positions = await self._get_current_positions(portfolio_id)

            # Get security prices
            security_ids = list(current_positions.keys()) + [
                pos.security_id for pos in model.positions
            ]
            prices = await self._get_security_prices(security_ids)

            # Calculate current market value
            market_value = self._calculate_market_value(current_positions, prices)

            # Perform optimization
            optimization_result = await self._optimize_portfolio(
                current_positions, model, prices, market_value
            )

            # Generate transactions
            transactions = self._generate_transactions(
                current_positions, optimization_result.optimal_quantities, portfolio_id
            )

            # Calculate drift information
            drifts = self._calculate_drifts(
                current_positions,
                optimization_result.optimal_quantities,
                model,
                prices,
                market_value,
            )

            # Update model's last rebalance date
            await self._update_last_rebalance_date(model)

            rebalance_dto = RebalanceDTO(
                portfolio_id=portfolio_id, transactions=transactions, drifts=drifts
            )

            logger.info(
                "Portfolio rebalancing completed",
                portfolio_id=portfolio_id,
                transaction_count=len(transactions),
                drift_count=len(drifts),
            )

            return rebalance_dto

        except (
            PortfolioNotFoundError,
            ModelNotFoundError,
            OptimizationError,
            ExternalServiceError,
        ):
            raise
        except Exception as e:
            logger.error(
                "Portfolio rebalancing failed", portfolio_id=portfolio_id, error=str(e)
            )
            raise

    async def rebalance_model_portfolios(self, model_id: str) -> List[RebalanceDTO]:
        """Rebalance all portfolios associated with an investment model.

        Args:
            model_id: Investment model identifier

        Returns:
            List of RebalanceDTO objects for each portfolio

        Raises:
            ModelNotFoundError: If model doesn't exist
            OptimizationError: If optimization fails for any portfolio
            ExternalServiceError: If external services are unavailable
        """
        logger.info("Starting model portfolio rebalancing", model_id=model_id)

        try:
            # Get investment model
            model = await self._model_repository.get_by_id(model_id)
            if not model:
                logger.warning("Model not found for rebalancing", model_id=model_id)
                raise ModelNotFoundError(f"Model {model_id} not found")

            if not model.portfolios:
                logger.info("No portfolios associated with model", model_id=model_id)
                return []

            # Rebalance portfolios in parallel
            logger.info(
                "Rebalancing portfolios in parallel",
                model_id=model_id,
                portfolio_count=len(model.portfolios),
            )

            rebalance_tasks = [
                self.rebalance_portfolio(portfolio_id)
                for portfolio_id in model.portfolios
            ]

            # Execute rebalancing with error isolation
            results = []
            completed_tasks = await asyncio.gather(
                *rebalance_tasks, return_exceptions=True
            )

            for i, result in enumerate(completed_tasks):
                portfolio_id = model.portfolios[i]

                if isinstance(result, Exception):
                    logger.warning(
                        "Portfolio rebalancing failed",
                        portfolio_id=portfolio_id,
                        error=str(result),
                    )

                    # Create empty rebalance result for failed portfolio
                    results.append(
                        RebalanceDTO(
                            portfolio_id=portfolio_id, transactions=[], drifts=[]
                        )
                    )
                else:
                    results.append(result)

            logger.info(
                "Model portfolio rebalancing completed",
                model_id=model_id,
                successful_portfolios=len([r for r in results if r.transactions]),
                total_portfolios=len(results),
            )

            return results

        except ModelNotFoundError:
            raise
        except Exception as e:
            logger.error(
                "Model portfolio rebalancing failed", model_id=model_id, error=str(e)
            )
            raise

    async def _get_portfolio_model(self, portfolio_id: str):
        """Get the investment model associated with a portfolio."""
        try:
            # Find model that contains this portfolio
            models = await self._model_repository.list_all()

            for model in models:
                if portfolio_id in model.portfolios:
                    logger.debug(
                        "Found model for portfolio",
                        portfolio_id=portfolio_id,
                        model_id=str(model.model_id),
                    )
                    return model

            logger.warning("No model found for portfolio", portfolio_id=portfolio_id)
            raise PortfolioNotFoundError(
                f"Portfolio {portfolio_id} not found in any model"
            )

        except Exception as e:
            logger.error(
                "Failed to find portfolio model",
                portfolio_id=portfolio_id,
                error=str(e),
            )
            raise

    async def _get_current_positions(self, portfolio_id: str) -> Dict[str, int]:
        """Get current positions for a portfolio."""
        try:
            logger.debug("Fetching current positions", portfolio_id=portfolio_id)

            balances = await self._portfolio_accounting_client.get_portfolio_balances(
                portfolio_id
            )

            # Convert balances to position quantities
            positions = {}
            for balance in balances:
                if (
                    balance.quantity > 0
                ):  # Only include positions with positive quantities
                    positions[balance.security_id] = balance.quantity

            logger.debug(
                "Retrieved current positions",
                portfolio_id=portfolio_id,
                position_count=len(positions),
            )

            return positions

        except Exception as e:
            logger.error(
                "Failed to get current positions",
                portfolio_id=portfolio_id,
                error=str(e),
            )
            raise ExternalServiceError(
                f"Failed to retrieve positions for portfolio {portfolio_id}"
            )

    async def _get_security_prices(self, security_ids: List[str]) -> Dict[str, Decimal]:
        """Get current prices for securities."""
        try:
            logger.debug("Fetching security prices", security_count=len(security_ids))

            prices = await self._pricing_client.get_security_prices(security_ids)

            logger.debug("Retrieved security prices", security_count=len(prices))

            return prices

        except Exception as e:
            logger.error(
                "Failed to get security prices",
                security_count=len(security_ids),
                error=str(e),
            )
            raise ExternalServiceError("Failed to retrieve security prices")

    def _calculate_market_value(
        self, positions: Dict[str, int], prices: Dict[str, Decimal]
    ) -> Decimal:
        """Calculate total market value of portfolio."""
        market_value = Decimal('0')

        for security_id, quantity in positions.items():
            if security_id in prices:
                market_value += Decimal(quantity) * prices[security_id]

        logger.debug("Calculated market value", market_value=float(market_value))
        return market_value

    async def _optimize_portfolio(
        self,
        current_positions: Dict[str, int],
        model,
        prices: Dict[str, Decimal],
        market_value: Decimal,
    ):
        """Perform mathematical optimization for portfolio rebalancing."""
        try:
            logger.debug("Starting portfolio optimization")

            optimization_result = await self._optimization_engine.optimize_portfolio(
                current_positions=current_positions,
                target_model=model,
                prices=prices,
                market_value=market_value,
            )

            logger.debug(
                "Portfolio optimization completed",
                status=optimization_result.solver_status,
            )

            return optimization_result

        except Exception as e:
            logger.error("Portfolio optimization failed", error=str(e))
            raise OptimizationError(f"Optimization failed: {str(e)}")

    def _generate_transactions(
        self,
        current_positions: Dict[str, int],
        optimal_quantities: Dict[str, int],
        portfolio_id: str,
    ) -> List[TransactionDTO]:
        """Generate buy/sell transactions based on optimization results."""
        transactions = []
        trade_date = date.today()

        # Get all securities (current + optimal)
        all_securities = set(current_positions.keys()) | set(optimal_quantities.keys())

        for security_id in all_securities:
            current_qty = current_positions.get(security_id, 0)
            optimal_qty = optimal_quantities.get(security_id, 0)

            quantity_delta = optimal_qty - current_qty

            if quantity_delta != 0:
                transaction_type = (
                    TransactionType.BUY if quantity_delta > 0 else TransactionType.SELL
                )
                quantity = abs(quantity_delta)

                transaction = TransactionDTO(
                    transaction_type=transaction_type,
                    security_id=security_id,
                    quantity=quantity,
                    trade_date=trade_date,
                )

                transactions.append(transaction)

        logger.debug(
            "Generated transactions",
            portfolio_id=portfolio_id,
            transaction_count=len(transactions),
        )

        return transactions

    def _calculate_drifts(
        self,
        current_positions: Dict[str, int],
        optimal_quantities: Dict[str, int],
        model,
        prices: Dict[str, Decimal],
        market_value: Decimal,
    ) -> List[DriftDTO]:
        """Calculate drift information for each position."""
        drifts = []

        for position in model.positions:
            security_id = position.security_id

            # Get quantities
            original_qty = Decimal(current_positions.get(security_id, 0))
            adjusted_qty = Decimal(optimal_quantities.get(security_id, 0))

            # Calculate actual percentage
            if market_value > 0:
                current_value = original_qty * prices.get(security_id, Decimal('0'))
                actual_percentage = current_value / market_value
            else:
                actual_percentage = Decimal('0')

            drift_dto = DriftDTO(
                security_id=security_id,
                original_quantity=original_qty,
                adjusted_quantity=adjusted_qty,
                target=position.target.value,
                high_drift=position.drift_bounds.high_drift,
                low_drift=position.drift_bounds.low_drift,
                actual=actual_percentage,
            )

            drifts.append(drift_dto)

        return drifts

    async def _update_last_rebalance_date(self, model) -> None:
        """Update the model's last rebalance date."""
        try:
            model.last_rebalance_date = datetime.utcnow()
            await self._model_repository.update(model)

            logger.debug("Updated last rebalance date", model_id=str(model.model_id))

        except Exception as e:
            # Log but don't fail the rebalancing operation
            logger.warning(
                "Failed to update last rebalance date",
                model_id=str(model.model_id),
                error=str(e),
            )

    def __del__(self):
        """Cleanup thread pool on service destruction."""
        if hasattr(self, '_thread_pool'):
            self._thread_pool.shutdown(wait=False)
