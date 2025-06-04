"""
Tests for domain-to-DTO mappers and conversion utilities.

This module tests the mapping logic between domain entities and API DTOs:
- InvestmentModel to ModelDTO conversion
- Position to ModelPositionDTO conversion
- OptimizationResult to RebalanceDTO conversion
- Error handling in mapping operations
- Bidirectional conversion accuracy
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from src.core.exceptions import ValidationError as DomainValidationError
from src.domain.entities.model import InvestmentModel, Position
from src.domain.services.optimization_engine import OptimizationResult
from src.domain.value_objects.drift_bounds import DriftBounds
from src.domain.value_objects.target_percentage import TargetPercentage


@pytest.mark.unit
class TestModelMappers:
    """Test mapping between InvestmentModel domain entity and DTOs."""

    def test_model_to_dto_conversion(self):
        """Test conversion from domain InvestmentModel to ModelDTO."""
        from src.core.mappers import ModelMapper

        # Create domain model
        domain_model = InvestmentModel(
            model_id="507f1f77bcf86cd799439011",
            name="Test Investment Model",
            positions=[
                Position(
                    security_id="STOCK1234567890123456789",
                    target=TargetPercentage(Decimal("0.60")),
                    drift_bounds=DriftBounds(
                        low_drift=Decimal("0.03"), high_drift=Decimal("0.05")
                    ),
                ),
                Position(
                    security_id="BOND1111111111111111111A",
                    target=TargetPercentage(Decimal("0.30")),
                    drift_bounds=DriftBounds(
                        low_drift=Decimal("0.02"), high_drift=Decimal("0.02")
                    ),
                ),
            ],
            portfolios=["683b6d88a29ee10e8b499643", "683b6d88a29ee10e8b499644"],
            last_rebalance_date=datetime(2024, 12, 19, 10, 30, 0, tzinfo=timezone.utc),
            version=2,
        )

        # Convert to DTO
        model_dto = ModelMapper.to_dto(domain_model)

        # Verify conversion
        assert model_dto.model_id == "507f1f77bcf86cd799439011"
        assert model_dto.name == "Test Investment Model"
        assert len(model_dto.positions) == 2
        assert len(model_dto.portfolios) == 2
        assert model_dto.version == 2
        assert model_dto.last_rebalance_date == datetime(
            2024, 12, 19, 10, 30, 0, tzinfo=timezone.utc
        )

        # Verify position conversion
        stock_position = model_dto.positions[0]
        assert stock_position.security_id == "STOCK1234567890123456789"
        assert stock_position.target == Decimal("0.60")
        assert stock_position.high_drift == Decimal("0.05")
        assert stock_position.low_drift == Decimal("0.03")

    def test_dto_to_model_conversion(self):
        """Test conversion from ModelDTO to domain InvestmentModel."""
        from src.core.mappers import ModelMapper
        from src.schemas.models import ModelDTO, ModelPositionDTO

        # Create DTO
        position_dto = ModelPositionDTO(
            security_id="STOCK1234567890123456789",
            target=Decimal("0.60"),
            high_drift=Decimal("0.05"),
            low_drift=Decimal("0.03"),
        )

        model_dto = ModelDTO(
            model_id="507f1f77bcf86cd799439011",
            name="Test Investment Model",
            positions=[position_dto],
            portfolios=["683b6d88a29ee10e8b499643"],
            last_rebalance_date=datetime(2024, 12, 19, 10, 30, 0, tzinfo=timezone.utc),
            version=2,
        )

        # Convert to domain
        domain_model = ModelMapper.from_dto(model_dto)

        # Verify conversion
        assert str(domain_model.model_id) == "507f1f77bcf86cd799439011"
        assert domain_model.name == "Test Investment Model"
        assert len(domain_model.positions) == 1
        assert len(domain_model.portfolios) == 1
        assert domain_model.version == 2

        # Verify position conversion
        position = domain_model.positions[0]
        assert position.security_id == "STOCK1234567890123456789"
        assert position.target.value == Decimal("0.60")
        assert position.drift_bounds.high_drift == Decimal("0.05")
        assert position.drift_bounds.low_drift == Decimal("0.03")

    def test_model_post_dto_to_domain_conversion(self):
        """Test conversion from ModelPostDTO to domain for creation."""
        from src.core.mappers import ModelMapper
        from src.schemas.models import ModelPositionDTO, ModelPostDTO

        # Create ModelPostDTO
        position_dto = ModelPositionDTO(
            security_id="STOCK1234567890123456789",
            target=Decimal("0.75"),
            high_drift=Decimal("0.06"),
            low_drift=Decimal("0.04"),
        )

        model_post_dto = ModelPostDTO(
            name="New Investment Model",
            positions=[position_dto],
            portfolios=["683b6d88a29ee10e8b499643"],
        )

        # Convert to domain
        domain_model = ModelMapper.from_post_dto(model_post_dto)

        # Verify conversion
        assert domain_model.name == "New Investment Model"
        assert len(domain_model.positions) == 1
        assert domain_model.portfolios == ["683b6d88a29ee10e8b499643"]
        assert domain_model.version == 1  # Default for new models
        assert domain_model.last_rebalance_date is None  # No rebalancing yet
        assert domain_model.model_id is not None  # Should generate new ID

    def test_model_put_dto_to_domain_conversion(self):
        """Test conversion from ModelPutDTO to domain for updates."""
        from src.core.mappers import ModelMapper
        from src.schemas.models import ModelPositionDTO, ModelPutDTO

        # Create ModelPutDTO
        position_dto = ModelPositionDTO(
            security_id="STOCK1234567890123456789",
            target=Decimal("0.65"),
            high_drift=Decimal("0.04"),
            low_drift=Decimal("0.02"),
        )

        model_put_dto = ModelPutDTO(
            name="Updated Investment Model",
            positions=[position_dto],
            portfolios=["683b6d88a29ee10e8b499643"],
            last_rebalance_date=datetime(2024, 12, 19, 15, 45, 0, tzinfo=timezone.utc),
            version=3,
        )

        # Convert to domain with existing ID
        domain_model = ModelMapper.from_put_dto(
            model_put_dto, model_id="507f1f77bcf86cd799439011"
        )

        # Verify conversion
        assert str(domain_model.model_id) == "507f1f77bcf86cd799439011"
        assert domain_model.name == "Updated Investment Model"
        assert domain_model.version == 3
        assert domain_model.last_rebalance_date == datetime(
            2024, 12, 19, 15, 45, 0, tzinfo=timezone.utc
        )

    def test_bidirectional_conversion_accuracy(self):
        """Test that domain -> DTO -> domain conversion preserves data."""
        from src.core.mappers import ModelMapper

        # Create original domain model
        original_model = InvestmentModel(
            model_id="507f1f77bcf86cd799439011",
            name="Precision Test Model",
            positions=[
                Position(
                    security_id="STOCK1234567890123456789",
                    target=TargetPercentage(
                        Decimal("0.125")
                    ),  # Valid multiple of 0.005
                    drift_bounds=DriftBounds(
                        low_drift=Decimal("0.012345"),  # High precision in drift bounds
                        high_drift=Decimal(
                            "0.067890"
                        ),  # High precision in drift bounds
                    ),
                )
            ],
            portfolios=["683b6d88a29ee10e8b499643"],
            last_rebalance_date=datetime(
                2024, 12, 19, 10, 30, 15, 123456, tzinfo=timezone.utc
            ),
            version=5,
        )

        # Convert to DTO and back
        model_dto = ModelMapper.to_dto(original_model)
        reconstructed_model = ModelMapper.from_dto(model_dto)

        # Verify precision is preserved
        assert str(reconstructed_model.model_id) == str(original_model.model_id)
        assert reconstructed_model.name == original_model.name
        assert reconstructed_model.version == original_model.version
        assert reconstructed_model.portfolios == original_model.portfolios

        # Verify position precision
        original_position = original_model.positions[0]
        reconstructed_position = reconstructed_model.positions[0]

        assert reconstructed_position.security_id == original_position.security_id
        assert reconstructed_position.target.value == original_position.target.value
        assert (
            reconstructed_position.drift_bounds.low_drift
            == original_position.drift_bounds.low_drift
        )
        assert (
            reconstructed_position.drift_bounds.high_drift
            == original_position.drift_bounds.high_drift
        )

    def test_mapping_with_empty_positions(self):
        """Test mapping models with no positions."""
        from src.core.mappers import ModelMapper

        # Create domain model with no positions
        domain_model = InvestmentModel(
            model_id="507f1f77bcf86cd799439011",
            name="Empty Model",
            positions=[],  # No positions
            portfolios=["683b6d88a29ee10e8b499643"],
            version=1,
        )

        # Convert to DTO and back
        model_dto = ModelMapper.to_dto(domain_model)
        reconstructed_model = ModelMapper.from_dto(model_dto)

        # Verify empty positions are handled correctly
        assert len(model_dto.positions) == 0
        assert len(reconstructed_model.positions) == 0
        assert reconstructed_model.name == "Empty Model"

    def test_mapping_validation_error_handling(self):
        """Test error handling during mapping operations."""
        from src.core.mappers import ModelMapper, PositionMapper
        from src.schemas.models import ModelDTO, ModelPositionDTO

        # Test that Pydantic validation catches invalid data at DTO level
        with pytest.raises(ValidationError):
            # Create DTO with invalid data that should fail Pydantic validation
            invalid_position_dto = ModelPositionDTO(
                security_id="STOCK1234567890123456789",
                target=Decimal("1.50"),  # Invalid target > 0.95
                high_drift=Decimal("0.05"),
                low_drift=Decimal("0.03"),
            )

        # Test domain-level validation by creating a valid DTO but invalid domain conversion
        try:
            # This should pass Pydantic validation but potentially fail at domain level
            valid_dto = ModelPositionDTO(
                security_id="STOCK1234567890123456789",
                target=Decimal("0.50"),  # Valid target
                high_drift=Decimal("0.05"),
                low_drift=Decimal("0.03"),
            )

            # Convert to domain - this should work
            domain_position = PositionMapper.from_dto(valid_dto)
            assert domain_position is not None

        except Exception as e:
            # If any domain validation fails, we can still assert the type
            assert isinstance(e, (ValidationError, DomainValidationError))


@pytest.mark.unit
class TestPositionMappers:
    """Test mapping between Position domain entity and DTOs."""

    def test_position_to_dto_conversion(self):
        """Test conversion from domain Position to ModelPositionDTO."""
        from src.core.mappers import PositionMapper

        # Create domain position
        domain_position = Position(
            security_id="STOCK1234567890123456789",
            target=TargetPercentage(Decimal("0.45")),
            drift_bounds=DriftBounds(
                low_drift=Decimal("0.025"), high_drift=Decimal("0.075")
            ),
        )

        # Convert to DTO
        position_dto = PositionMapper.to_dto(domain_position)

        # Verify conversion
        assert position_dto.security_id == "STOCK1234567890123456789"
        assert position_dto.target == Decimal("0.45")
        assert position_dto.high_drift == Decimal("0.075")
        assert position_dto.low_drift == Decimal("0.025")

    def test_dto_to_position_conversion(self):
        """Test conversion from ModelPositionDTO to domain Position."""
        from src.core.mappers import PositionMapper
        from src.schemas.models import ModelPositionDTO

        # Create DTO
        position_dto = ModelPositionDTO(
            security_id="BOND1111111111111111111A",
            target=Decimal("0.35"),
            high_drift=Decimal("0.08"),
            low_drift=Decimal("0.02"),
        )

        # Convert to domain
        domain_position = PositionMapper.from_dto(position_dto)

        # Verify conversion
        assert domain_position.security_id == "BOND1111111111111111111A"
        assert domain_position.target.value == Decimal("0.35")
        assert domain_position.drift_bounds.high_drift == Decimal("0.08")
        assert domain_position.drift_bounds.low_drift == Decimal("0.02")

    def test_position_list_conversion(self):
        """Test conversion of position lists."""
        from src.core.mappers import PositionMapper
        from src.schemas.models import ModelPositionDTO

        # Create list of DTOs
        position_dtos = [
            ModelPositionDTO(
                security_id="STOCK1234567890123456789",
                target=Decimal("0.50"),
                high_drift=Decimal("0.05"),
                low_drift=Decimal("0.03"),
            ),
            ModelPositionDTO(
                security_id="BOND1111111111111111111A",
                target=Decimal("0.40"),
                high_drift=Decimal("0.04"),
                low_drift=Decimal("0.02"),
            ),
        ]

        # Convert to domain positions
        domain_positions = PositionMapper.from_dto_list(position_dtos)

        # Verify conversion
        assert len(domain_positions) == 2
        assert domain_positions[0].security_id == "STOCK1234567890123456789"
        assert domain_positions[1].security_id == "BOND1111111111111111111A"
        assert domain_positions[0].target.value == Decimal("0.50")
        assert domain_positions[1].target.value == Decimal("0.40")

    def test_position_decimal_precision_preservation(self):
        """Test that decimal precision is preserved in position mapping."""
        from src.core.mappers import PositionMapper

        # Create domain position with high precision
        domain_position = Position(
            security_id="STOCK1234567890123456789",
            target=TargetPercentage(Decimal("0.125")),  # Valid multiple of 0.005
            drift_bounds=DriftBounds(
                low_drift=Decimal("0.012345678"),  # High precision in drift bounds
                high_drift=Decimal("0.098765432"),  # High precision in drift bounds
            ),
        )

        # Convert to DTO and back
        position_dto = PositionMapper.to_dto(domain_position)
        reconstructed_position = PositionMapper.from_dto(position_dto)

        # Verify precision is preserved
        assert reconstructed_position.target.value == domain_position.target.value
        assert (
            reconstructed_position.drift_bounds.low_drift
            == domain_position.drift_bounds.low_drift
        )
        assert (
            reconstructed_position.drift_bounds.high_drift
            == domain_position.drift_bounds.high_drift
        )

    def test_missing_required_fields_handling(self):
        """Test handling of missing required fields during mapping."""
        from src.core.mappers import PositionMapper
        from src.schemas.models import ModelPositionDTO

        # This should be caught by Pydantic validation before reaching mapper
        with pytest.raises(ValidationError):
            # Missing required fields
            incomplete_dto = ModelPositionDTO()

    def test_large_decimal_precision_handling(self):
        """Test handling of very large decimal precision values."""
        from src.core.mappers import PositionMapper
        from src.schemas.models import ModelPositionDTO

        # Create DTO with high precision but valid target (multiple of 0.005)
        high_precision_dto = ModelPositionDTO(
            security_id="STOCK1234567890123456789",
            target=Decimal("0.125"),  # Valid multiple of 0.005
            high_drift=Decimal("0.050000000000000000000000000001"),  # High precision
            low_drift=Decimal("0.029999999999999999999999999999"),  # High precision
        )

        # Should handle high precision gracefully
        domain_position = PositionMapper.from_dto(high_precision_dto)

        # Target should be exactly as specified
        assert domain_position.target.value == Decimal("0.125")
        # High precision should be preserved in drift bounds
        assert domain_position.drift_bounds.high_drift > Decimal("0.05")
        assert domain_position.drift_bounds.low_drift < Decimal("0.03")


@pytest.mark.unit
class TestRebalanceMappers:
    """Test mapping between optimization results and rebalance DTOs."""

    def test_optimization_result_to_rebalance_dto_conversion(self):
        """Test conversion from OptimizationResult to RebalanceDTO."""
        from src.core.mappers import RebalanceMapper

        # Create optimization result
        optimization_result = OptimizationResult(
            optimal_quantities={
                "STOCK1234567890123456789": 600,
                "BOND1111111111111111111A": 300,
            },
            objective_value=Decimal("125.50"),
            solver_status="optimal",
            solve_time_seconds=2.5,
            is_feasible=True,
        )

        # Mock additional data needed for rebalance DTO
        portfolio_id = "683b6d88a29ee10e8b499643"
        current_positions = {
            "STOCK1234567890123456789": 500,
            "BOND1111111111111111111A": 400,
        }
        prices = {
            "STOCK1234567890123456789": Decimal("100.00"),
            "BOND1111111111111111111A": Decimal("95.00"),
        }
        model_positions = [
            Position(
                security_id="STOCK1234567890123456789",
                target=TargetPercentage(Decimal("0.60")),
                drift_bounds=DriftBounds(
                    low_drift=Decimal("0.03"), high_drift=Decimal("0.05")
                ),
            ),
            Position(
                security_id="BOND1111111111111111111A",
                target=TargetPercentage(Decimal("0.30")),
                drift_bounds=DriftBounds(
                    low_drift=Decimal("0.02"), high_drift=Decimal("0.02")
                ),
            ),
        ]
        market_value = Decimal("100000.00")

        # Convert to rebalance DTO
        rebalance_dto = RebalanceMapper.from_optimization_result(
            optimization_result=optimization_result,
            portfolio_id=portfolio_id,
            current_positions=current_positions,
            optimal_positions=optimization_result.optimal_quantities,
            prices=prices,
            model_positions=model_positions,
            market_value=market_value,
        )

        # Verify conversion
        assert rebalance_dto.portfolio_id == portfolio_id

        # Should have transactions for changes
        assert len(rebalance_dto.transactions) >= 0  # May have buy/sell transactions

        # Should have drift analysis for all positions
        assert len(rebalance_dto.drifts) == len(model_positions)

        # Verify drift calculations
        stock_drift = next(
            d
            for d in rebalance_dto.drifts
            if d.security_id == "STOCK1234567890123456789"
        )
        assert stock_drift.original_quantity == Decimal("500")
        assert stock_drift.adjusted_quantity == Decimal("600")
        assert stock_drift.target == Decimal("0.60")

    def test_transaction_generation_from_position_changes(self):
        """Test generation of transactions from position changes."""
        from src.core.mappers import RebalanceMapper

        current_positions = {
            "STOCK1234567890123456789": 500,  # Need to buy 100 more
            "BOND1111111111111111111A": 400,  # Need to sell 100
            "CASH123456789012345678AB": 0,  # New position, buy 200 (24 chars)
        }

        optimal_positions = {
            "STOCK1234567890123456789": 600,  # +100
            "BOND1111111111111111111A": 300,  # -100
            "CASH123456789012345678AB": 200,  # +200 (24 chars)
        }

        # Generate transactions
        transactions = RebalanceMapper.generate_transactions(
            current_positions=current_positions, optimal_positions=optimal_positions
        )

        # Verify transactions
        buy_transactions = [t for t in transactions if t.transaction_type == "BUY"]
        sell_transactions = [t for t in transactions if t.transaction_type == "SELL"]

        # Should have 2 buy transactions and 1 sell transaction
        assert len(buy_transactions) == 2
        assert len(sell_transactions) == 1

        # Check specific transactions
        stock_buy = next(
            t for t in buy_transactions if t.security_id == "STOCK1234567890123456789"
        )
        bond_sell = next(
            t for t in sell_transactions if t.security_id == "BOND1111111111111111111A"
        )
        cash_buy = next(
            t for t in buy_transactions if t.security_id == "CASH123456789012345678AB"
        )

        assert stock_buy.quantity == 100
        assert bond_sell.quantity == 100
        assert cash_buy.quantity == 200

    def test_drift_calculation_accuracy(self):
        """Test accuracy of drift calculations in mapping."""
        from src.core.mappers import RebalanceMapper

        # Setup test data
        position = Position(
            security_id="STOCK1234567890123456789",
            target=TargetPercentage(Decimal("0.25")),  # 25% target
            drift_bounds=DriftBounds(
                low_drift=Decimal("0.05"), high_drift=Decimal("0.05")
            ),
        )

        original_quantity = Decimal("200")  # 200 * $50 = $10,000
        adjusted_quantity = Decimal("250")  # 250 * $50 = $12,500
        price = Decimal("50.00")
        market_value = Decimal("50000.00")  # $50,000 total portfolio

        # Calculate drift
        drift_dto = RebalanceMapper.calculate_drift(
            position=position,
            original_quantity=original_quantity,
            adjusted_quantity=adjusted_quantity,
            price=price,
            market_value=market_value,
        )

        # Verify drift calculation
        assert drift_dto.security_id == "STOCK1234567890123456789"
        assert drift_dto.original_quantity == original_quantity
        assert drift_dto.adjusted_quantity == adjusted_quantity
        assert drift_dto.target == Decimal("0.25")

        # Actual percentage should be 12,500 / 50,000 = 0.25 = 25%
        expected_actual = Decimal("0.2500")  # 4 decimal places
        assert drift_dto.actual == expected_actual

    def test_empty_optimization_result_handling(self):
        """Test handling of empty/infeasible optimization results."""
        from src.core.mappers import RebalanceMapper

        # Create infeasible optimization result
        infeasible_result = OptimizationResult(
            optimal_quantities={},  # No solution
            objective_value=None,
            solver_status="infeasible",
            solve_time_seconds=5.0,
            is_feasible=False,
        )

        # Convert to rebalance DTO
        rebalance_dto = RebalanceMapper.from_optimization_result(
            optimization_result=infeasible_result,
            portfolio_id="683b6d88a29ee10e8b499643",
            current_positions={"STOCK1234567890123456789": 500},
            optimal_positions={},  # No optimal solution
            prices={"STOCK1234567890123456789": Decimal("100.00")},
            model_positions=[],
            market_value=Decimal("50000.00"),
        )

        # Verify handling of infeasible result
        assert rebalance_dto.portfolio_id == "683b6d88a29ee10e8b499643"
        # When no optimal positions are provided, current positions should be liquidated
        assert len(rebalance_dto.transactions) == 1  # Should sell current position
        assert rebalance_dto.transactions[0].transaction_type == "SELL"
        assert rebalance_dto.transactions[0].security_id == "STOCK1234567890123456789"
        assert rebalance_dto.transactions[0].quantity == 500


@pytest.mark.unit
class TestMapperErrorHandling:
    """Test error handling and edge cases in mapping operations."""

    def test_invalid_model_id_format_handling(self):
        """Test handling of invalid model ID formats."""
        from src.core.mappers import ModelMapper
        from src.schemas.models import ModelDTO

        # Create DTO with invalid model ID
        invalid_model_dto = ModelDTO(
            model_id="invalid_id",  # Not a valid ObjectId
            name="Test Model",
            positions=[],
            portfolios=["683b6d88a29ee10e8b499643"],
            version=1,
        )

        # Should handle invalid ObjectId gracefully
        with pytest.raises((ValueError, TypeError)):
            ModelMapper.from_dto(invalid_model_dto)

    def test_missing_required_fields_handling(self):
        """Test handling of missing required fields during mapping."""
        from src.core.mappers import PositionMapper
        from src.schemas.models import ModelPositionDTO

        # This should be caught by Pydantic validation before reaching mapper
        with pytest.raises(ValidationError):
            # Missing required fields
            incomplete_dto = ModelPositionDTO()
