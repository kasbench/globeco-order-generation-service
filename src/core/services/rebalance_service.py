"""
Portfolio rebalancing service implementation.

This module provides the application service layer for portfolio rebalancing operations,
coordinating between optimization engine, external services, and domain logic.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Dict, List

import structlog
from bson import ObjectId

from src.core.exceptions import (
    ExternalServiceError,
    ModelNotFoundError,
    OptimizationError,
    PortfolioNotFoundError,
)
from src.core.mappers import RebalanceMapper
from src.domain.entities.rebalance import (
    Rebalance,
    RebalancePortfolio,
    RebalancePosition,
)
from src.domain.repositories.model_repository import ModelRepository
from src.domain.repositories.rebalance_repository import RebalanceRepository
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
        rebalance_repository: RebalanceRepository,
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
            rebalance_repository: Repository for storing rebalance results
            optimization_engine: Mathematical optimization engine
            drift_calculator: Portfolio drift calculation service
            portfolio_accounting_client: Client for portfolio position data
            pricing_client: Client for security pricing data
            rebalance_mapper: Mapper for rebalancing DTOs
            max_workers: Maximum parallel workers for multi-portfolio rebalancing
        """
        self._model_repository = model_repository
        self._rebalance_repository = rebalance_repository
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

            # Calculate current market value (securities + cash)
            market_value = await self._calculate_market_value(
                current_positions, prices, portfolio_id
            )

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

            # Create and persist rebalance record
            rebalance_record = await self._create_rebalance_record(
                model,
                [portfolio_id],
                {
                    portfolio_id: {
                        'current_positions': current_positions,
                        'optimal_quantities': optimization_result.optimal_quantities,
                        'prices': prices,
                        'market_value': market_value,
                        'transactions': transactions,
                        'drifts': drifts,
                    }
                },
            )

            rebalance_dto = RebalanceDTO(
                portfolio_id=portfolio_id,
                rebalance_id=str(rebalance_record.rebalance_id),
                transactions=transactions,
                drifts=drifts,
            )

            logger.info(
                "Portfolio rebalancing completed",
                portfolio_id=portfolio_id,
                rebalance_id=str(rebalance_record.rebalance_id),
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

            # Rebalance portfolios in parallel and collect data for persistence
            logger.info(
                "Rebalancing portfolios in parallel",
                model_id=model_id,
                portfolio_count=len(model.portfolios),
            )

            # Create tasks for individual portfolio rebalancing (without persistence)
            rebalance_tasks = [
                self._rebalance_portfolio_internal(portfolio_id, model)
                for portfolio_id in model.portfolios
            ]

            # Execute rebalancing with error isolation
            portfolio_data = {}
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
                            portfolio_id=portfolio_id,
                            rebalance_id="",  # Will be set after persistence
                            transactions=[],
                            drifts=[],
                        )
                    )
                    portfolio_data[portfolio_id] = None
                else:
                    results.append(result['dto'])
                    portfolio_data[portfolio_id] = result['data']

            # Update model's last rebalance date
            await self._update_last_rebalance_date(model)

            # Create and persist single rebalance record for all portfolios
            rebalance_record = await self._create_rebalance_record(
                model, model.portfolios, portfolio_data
            )

            # Update all DTOs with the rebalance ID
            for dto in results:
                dto.rebalance_id = str(rebalance_record.rebalance_id)

            logger.info(
                "Model portfolio rebalancing completed",
                model_id=model_id,
                rebalance_id=str(rebalance_record.rebalance_id),
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

            # Use the new get_portfolio_positions method which returns Dict[str, int] directly
            positions = await self._portfolio_accounting_client.get_portfolio_positions(
                portfolio_id
            )

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

    async def _calculate_market_value(
        self, positions: Dict[str, int], prices: Dict[str, Decimal], portfolio_id: str
    ) -> Decimal:
        """Calculate total market value of portfolio (securities + cash)."""
        securities_value = Decimal('0')
        matched_securities = 0
        missing_prices = []

        logger.debug(
            "Calculating market value",
            portfolio_id=portfolio_id,
            position_keys=list(positions.keys())[:5],  # Show first 5
            price_keys=list(prices.keys())[:5],  # Show first 5
            total_positions=len(positions),
            total_prices=len(prices),
        )

        # Calculate securities value
        for security_id, quantity in positions.items():
            if security_id in prices:
                position_value = Decimal(quantity) * prices[security_id]
                securities_value += position_value
                matched_securities += 1
                logger.debug(
                    "Security matched",
                    security_id=security_id,
                    quantity=quantity,
                    price=float(prices[security_id]),
                    value=float(position_value),
                )
            else:
                missing_prices.append(security_id)

        if missing_prices:
            logger.warning(
                "Missing prices for securities",
                missing_count=len(missing_prices),
                missing_securities=missing_prices[:5],  # Show first 5
            )

        # Get cash balance
        try:
            cash_balance = await self._portfolio_accounting_client.get_cash_position(
                portfolio_id
            )
            logger.debug(
                "Cash position retrieved",
                portfolio_id=portfolio_id,
                cash_balance=float(cash_balance),
            )
        except Exception as e:
            logger.warning(
                "Failed to get cash position, assuming zero",
                portfolio_id=portfolio_id,
                error=str(e),
            )
            cash_balance = Decimal('0')

        # Total market value = securities + cash
        total_market_value = securities_value + cash_balance

        logger.info(
            "Market value calculation complete",
            portfolio_id=portfolio_id,
            securities_value=float(securities_value),
            cash_balance=float(cash_balance),
            total_market_value=float(total_market_value),
            matched_securities=matched_securities,
            total_positions=len(positions),
            missing_prices_count=len(missing_prices),
        )

        return total_market_value

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

    async def _rebalance_portfolio_internal(self, portfolio_id: str, model):
        """Internal method to rebalance a portfolio without persistence.

        Returns both the DTO and the raw data needed for persistence.
        """
        logger.info(
            "Starting internal portfolio rebalancing", portfolio_id=portfolio_id
        )

        # Get current portfolio positions
        current_positions = await self._get_current_positions(portfolio_id)

        # Get security prices
        security_ids = list(current_positions.keys()) + [
            pos.security_id for pos in model.positions
        ]
        prices = await self._get_security_prices(security_ids)

        # Calculate current market value (securities + cash)
        market_value = await self._calculate_market_value(
            current_positions, prices, portfolio_id
        )

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

        # Create DTO
        dto = RebalanceDTO(
            portfolio_id=portfolio_id,
            rebalance_id="",  # Will be set later
            transactions=transactions,
            drifts=drifts,
        )

        # Collect data for persistence
        data = {
            'current_positions': current_positions,
            'optimal_quantities': optimization_result.optimal_quantities,
            'prices': prices,
            'market_value': market_value,
            'transactions': transactions,
            'drifts': drifts,
        }

        logger.info(
            "Internal portfolio rebalancing completed",
            portfolio_id=portfolio_id,
            transaction_count=len(transactions),
            drift_count=len(drifts),
        )

        return {'dto': dto, 'data': data}

    async def _create_rebalance_record(
        self, model, portfolio_ids: List[str], portfolio_data: Dict
    ) -> Rebalance:
        """Create and persist a rebalance record."""
        logger.info(
            "Creating rebalance record",
            model_id=str(model.model_id),
            portfolio_count=len(portfolio_ids),
        )

        # Get cash positions for all portfolios
        cash_positions = {}
        for portfolio_id in portfolio_ids:
            if portfolio_data.get(portfolio_id):
                try:
                    cash_before = (
                        await self._portfolio_accounting_client.get_cash_position(
                            portfolio_id
                        )
                    )
                    # Calculate cash after rebalancing (simplified - would need actual transaction processing)
                    cash_after = (
                        cash_before  # For now, assume cash doesn't change significantly
                    )
                    cash_positions[portfolio_id] = {
                        'before': cash_before,
                        'after': cash_after,
                    }
                except Exception as e:
                    logger.warning(
                        f"Failed to get cash position for {portfolio_id}: {e}"
                    )
                    cash_positions[portfolio_id] = {
                        'before': Decimal('0'),
                        'after': Decimal('0'),
                    }

        # Create rebalance portfolios
        rebalance_portfolios = []
        for portfolio_id in portfolio_ids:
            data = portfolio_data.get(portfolio_id)
            if not data:
                continue  # Skip failed portfolios

            # Create positions for this portfolio
            positions = []

            # Get union of all securities (current + model)
            all_securities = set(data['current_positions'].keys())
            for pos in model.positions:
                all_securities.add(pos.security_id)

            for security_id in all_securities:
                original_qty = Decimal(data['current_positions'].get(security_id, 0))
                adjusted_qty = Decimal(data['optimal_quantities'].get(security_id, 0))
                price = data['prices'].get(security_id, Decimal('0'))

                # Find model position for this security
                model_position = None
                for pos in model.positions:
                    if pos.security_id == security_id:
                        model_position = pos
                        break

                target = model_position.target.value if model_position else Decimal('0')
                high_drift = (
                    model_position.drift_bounds.high_drift
                    if model_position
                    else Decimal('0')
                )
                low_drift = (
                    model_position.drift_bounds.low_drift
                    if model_position
                    else Decimal('0')
                )

                # Calculate actual allocation
                actual = (
                    (adjusted_qty * price) / data['market_value']
                    if data['market_value'] > 0
                    else Decimal('0')
                )
                actual_drift = (1 - (actual / target)) if target > 0 else Decimal('0')

                # Determine transaction info
                qty_delta = int(adjusted_qty - original_qty)
                transaction_type = None
                trade_quantity = None
                trade_date = None

                if qty_delta > 0:
                    transaction_type = "BUY"
                    trade_quantity = qty_delta
                    trade_date = datetime.now(timezone.utc)
                elif qty_delta < 0:
                    transaction_type = "SELL"
                    trade_quantity = abs(qty_delta)
                    trade_date = datetime.now(timezone.utc)

                position = RebalancePosition(
                    security_id=security_id,
                    price=price,
                    original_quantity=original_qty,
                    adjusted_quantity=adjusted_qty,
                    original_position_market_value=original_qty * price,
                    adjusted_position_market_value=adjusted_qty * price,
                    target=target,
                    high_drift=high_drift,
                    low_drift=low_drift,
                    actual=actual,
                    actual_drift=actual_drift,
                    transaction_type=transaction_type,
                    trade_quantity=trade_quantity,
                    trade_date=trade_date,
                )
                positions.append(position)

            # Create portfolio
            cash_info = cash_positions.get(
                portfolio_id, {'before': Decimal('0'), 'after': Decimal('0')}
            )
            portfolio = RebalancePortfolio(
                portfolio_id=portfolio_id,
                market_value=data['market_value'],
                cash_before_rebalance=cash_info['before'],
                cash_after_rebalance=cash_info['after'],
                positions=positions,
            )
            rebalance_portfolios.append(portfolio)

        # Create rebalance record
        rebalance = Rebalance(
            model_id=model.model_id,
            rebalance_date=datetime.now(timezone.utc),
            model_name=model.name,
            number_of_portfolios=len(rebalance_portfolios),
            portfolios=rebalance_portfolios,
            version=1,
            created_at=datetime.now(timezone.utc),
        )

        # Persist to database
        saved_rebalance = await self._rebalance_repository.create(rebalance)

        logger.info(
            "Rebalance record created", rebalance_id=str(saved_rebalance.rebalance_id)
        )
        return saved_rebalance

    def __del__(self):
        """Cleanup thread pool on service destruction."""
        if hasattr(self, '_thread_pool'):
            self._thread_pool.shutdown(wait=False)
