"""
Mappers for converting between domain entities and DTOs.

This module provides mapping functionality between domain entities and API DTOs:
- ModelMapper: InvestmentModel <-> ModelDTO/ModelPostDTO/ModelPutDTO conversion
- PositionMapper: Position <-> ModelPositionDTO conversion
- RebalanceMapper: OptimizationResult -> RebalanceDTO conversion

All mappers include proper error handling, validation, and preserve data precision.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List

from bson import ObjectId

from src.domain.entities.model import InvestmentModel, Position
from src.domain.services.optimization_engine import OptimizationResult
from src.domain.value_objects.drift_bounds import DriftBounds
from src.domain.value_objects.target_percentage import TargetPercentage
from src.schemas.models import ModelDTO, ModelPositionDTO, ModelPostDTO, ModelPutDTO
from src.schemas.rebalance import DriftDTO, RebalanceDTO
from src.schemas.transactions import TransactionDTO, TransactionType


class ModelMapper:
    """Mapper for InvestmentModel domain entity and DTOs."""

    @staticmethod
    def to_dto(model: InvestmentModel) -> ModelDTO:
        """Convert domain InvestmentModel to ModelDTO."""
        return ModelDTO(
            model_id=str(model.model_id),
            name=model.name,
            positions=[PositionMapper.to_dto(pos) for pos in model.positions],
            portfolios=model.portfolios,
            last_rebalance_date=model.last_rebalance_date,
            version=model.version,
        )

    @staticmethod
    def from_dto(model_dto: ModelDTO) -> InvestmentModel:
        """Convert ModelDTO to domain InvestmentModel."""
        try:
            model_id = ObjectId(model_dto.model_id)
        except Exception as e:
            raise ValueError(f"Invalid model ID format: {model_dto.model_id}") from e

        return InvestmentModel(
            model_id=model_id,
            name=model_dto.name,
            positions=[PositionMapper.from_dto(pos) for pos in model_dto.positions],
            portfolios=model_dto.portfolios,
            last_rebalance_date=model_dto.last_rebalance_date,
            version=model_dto.version,
        )

    @staticmethod
    def from_post_dto(model_post_dto: ModelPostDTO) -> InvestmentModel:
        """Convert ModelPostDTO to domain InvestmentModel for creation."""
        # Generate a new ObjectId for the model
        new_model_id = ObjectId()

        return InvestmentModel(
            model_id=new_model_id,
            name=model_post_dto.name,
            positions=[
                PositionMapper.from_dto(pos) for pos in model_post_dto.positions
            ],
            portfolios=model_post_dto.portfolios,
            version=1,  # Default version for new models
        )

    @staticmethod
    def from_put_dto(model_put_dto: ModelPutDTO, model_id: str) -> InvestmentModel:
        """Convert ModelPutDTO to domain InvestmentModel for update."""
        try:
            object_id = ObjectId(model_id)
        except Exception as e:
            raise ValueError(f"Invalid model ID format: {model_id}") from e

        return InvestmentModel(
            model_id=object_id,
            name=model_put_dto.name,
            positions=[PositionMapper.from_dto(pos) for pos in model_put_dto.positions],
            portfolios=model_put_dto.portfolios,
            last_rebalance_date=model_put_dto.last_rebalance_date,
            version=model_put_dto.version,
        )


class PositionMapper:
    """Mapper for Position domain entity and DTOs."""

    @staticmethod
    def to_dto(position: Position) -> ModelPositionDTO:
        """Convert domain Position to ModelPositionDTO."""
        return ModelPositionDTO(
            security_id=position.security_id,
            target=position.target.value,
            high_drift=position.drift_bounds.high_drift,
            low_drift=position.drift_bounds.low_drift,
        )

    @staticmethod
    def from_dto(position_dto: ModelPositionDTO) -> Position:
        """Convert ModelPositionDTO to domain Position."""
        return Position(
            security_id=position_dto.security_id,
            target=TargetPercentage(position_dto.target),
            drift_bounds=DriftBounds(
                low_drift=position_dto.low_drift, high_drift=position_dto.high_drift
            ),
        )

    @staticmethod
    def from_dto_list(position_dtos: List[ModelPositionDTO]) -> List[Position]:
        """Convert list of ModelPositionDTOs to domain Positions."""
        return [PositionMapper.from_dto(dto) for dto in position_dtos]

    @staticmethod
    def to_dto_list(positions: List[Position]) -> List[ModelPositionDTO]:
        """Convert list of domain Positions to ModelPositionDTOs."""
        return [PositionMapper.to_dto(pos) for pos in positions]


class RebalanceMapper:
    """Mapper for optimization results and rebalance DTOs."""

    @staticmethod
    def from_optimization_result(
        optimization_result: OptimizationResult,
        portfolio_id: str,
        current_positions: Dict[str, int],
        optimal_positions: Dict[str, int],
        prices: Dict[str, Decimal],
        model_positions: List[Position],
        market_value: Decimal,
    ) -> RebalanceDTO:
        """Convert OptimizationResult to RebalanceDTO."""
        # Generate transactions from position changes
        transactions = RebalanceMapper.generate_transactions(
            current_positions=current_positions, optimal_positions=optimal_positions
        )

        # Calculate drift analysis for all model positions
        drifts = []
        for position in model_positions:
            security_id = position.security_id
            original_quantity = Decimal(str(current_positions.get(security_id, 0)))
            adjusted_quantity = Decimal(str(optimal_positions.get(security_id, 0)))
            price = prices.get(security_id, Decimal("0"))

            drift_dto = RebalanceMapper.calculate_drift(
                position=position,
                original_quantity=original_quantity,
                adjusted_quantity=adjusted_quantity,
                price=price,
                market_value=market_value,
            )
            drifts.append(drift_dto)

        # Generate a unique rebalance ID
        from bson import ObjectId

        rebalance_id = str(ObjectId())

        return RebalanceDTO(
            portfolio_id=portfolio_id,
            rebalance_id=rebalance_id,
            transactions=transactions,
            drifts=drifts,
        )

    @staticmethod
    def generate_transactions(
        current_positions: Dict[str, int], optimal_positions: Dict[str, int]
    ) -> List[TransactionDTO]:
        """Generate transactions from position changes."""
        transactions = []
        today = date.today()

        # Get all security IDs from both current and optimal positions
        all_security_ids = set(current_positions.keys()) | set(optimal_positions.keys())

        for security_id in all_security_ids:
            current_qty = current_positions.get(security_id, 0)
            optimal_qty = optimal_positions.get(security_id, 0)

            quantity_change = optimal_qty - current_qty

            if quantity_change > 0:
                # Need to buy
                transactions.append(
                    TransactionDTO(
                        transaction_type=TransactionType.BUY,
                        security_id=security_id,
                        quantity=quantity_change,
                        trade_date=today,
                    )
                )
            elif quantity_change < 0:
                # Need to sell
                transactions.append(
                    TransactionDTO(
                        transaction_type=TransactionType.SELL,
                        security_id=security_id,
                        quantity=abs(quantity_change),
                        trade_date=today,
                    )
                )
            # quantity_change == 0: no transaction needed

        return transactions

    @staticmethod
    def calculate_drift(
        position: Position,
        original_quantity: Decimal,
        adjusted_quantity: Decimal,
        price: Decimal,
        market_value: Decimal,
    ) -> DriftDTO:
        """Calculate drift analysis for a position."""
        # Calculate actual percentage after adjustment
        if market_value > Decimal("0"):
            actual_value = adjusted_quantity * price
            actual_percentage = actual_value / market_value
            # Round to 4 decimal places as specified
            actual_percentage = actual_percentage.quantize(Decimal("0.0001"))
        else:
            actual_percentage = Decimal("0.0000")

        return DriftDTO(
            security_id=position.security_id,
            original_quantity=original_quantity,
            adjusted_quantity=adjusted_quantity,
            target=position.target.value,
            high_drift=position.drift_bounds.high_drift,
            low_drift=position.drift_bounds.low_drift,
            actual=actual_percentage,
        )
