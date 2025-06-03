"""
Tests for Domain Service interfaces.

This module tests the Domain Service interfaces which define contracts
for business logic operations that don't belong to entities.

Following TDD principles, these tests define the service interfaces
that implementations must satisfy.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, Mock

import pytest
from bson import ObjectId

from src.domain.entities.model import InvestmentModel
from src.domain.entities.position import Position
from src.domain.services.drift_calculator import DriftCalculator, DriftInfo
from src.domain.services.optimization_engine import (
    OptimizationEngine,
    OptimizationResult,
)
from src.domain.services.validation_service import ValidationService
from src.domain.value_objects.drift_bounds import DriftBounds
from src.domain.value_objects.target_percentage import TargetPercentage


@pytest.mark.unit
class TestOptimizationEngineInterface:
    """Test Optimization Engine interface contract."""

    @pytest.fixture
    def mock_optimization_engine(self) -> OptimizationEngine:
        """Create a mock optimization engine for testing."""
        engine = Mock(spec=OptimizationEngine)
        engine.optimize_portfolio = AsyncMock()
        engine.validate_solution = AsyncMock()
        engine.check_solver_health = AsyncMock()
        return engine

    @pytest.fixture
    def sample_model(self) -> InvestmentModel:
        """Create a sample investment model."""
        return InvestmentModel(
            model_id=ObjectId(),
            name="Test Model",
            positions=[
                Position(
                    security_id="STOCK1234567890123456789",
                    target=TargetPercentage(Decimal("0.30")),
                    drift_bounds=DriftBounds(
                        low_drift=Decimal("0.02"), high_drift=Decimal("0.03")
                    ),
                ),
                Position(
                    security_id="STOCK9876543210987654321",
                    target=TargetPercentage(Decimal("0.25")),
                    drift_bounds=DriftBounds(
                        low_drift=Decimal("0.015"), high_drift=Decimal("0.025")
                    ),
                ),
            ],
            portfolios=["portfolio1"],
            version=1,
        )

    @pytest.mark.asyncio
    async def test_optimization_engine_has_required_methods(
        self, mock_optimization_engine
    ):
        """Test that optimization engine has all required methods."""
        # Verify interface methods exist
        assert hasattr(mock_optimization_engine, "optimize_portfolio")
        assert hasattr(mock_optimization_engine, "validate_solution")
        assert hasattr(mock_optimization_engine, "check_solver_health")

        # Verify methods are callable
        assert callable(mock_optimization_engine.optimize_portfolio)
        assert callable(mock_optimization_engine.validate_solution)
        assert callable(mock_optimization_engine.check_solver_health)

    @pytest.mark.asyncio
    async def test_optimize_portfolio_success(
        self, mock_optimization_engine, sample_model
    ):
        """Test successful portfolio optimization."""
        # Arrange
        current_positions = {
            "STOCK1234567890123456789": 100,
            "STOCK9876543210987654321": 80,
        }
        prices = {
            "STOCK1234567890123456789": Decimal("50.00"),
            "STOCK9876543210987654321": Decimal("75.00"),
        }
        market_value = Decimal("100000")

        expected_result = OptimizationResult(
            optimal_quantities={
                "STOCK1234567890123456789": 600,
                "STOCK9876543210987654321": 333,
            },
            objective_value=Decimal("150.50"),
            solver_status="OPTIMAL",
            solve_time_seconds=2.5,
            is_feasible=True,
        )

        mock_optimization_engine.optimize_portfolio.return_value = expected_result

        # Act
        result = await mock_optimization_engine.optimize_portfolio(
            current_positions=current_positions,
            target_model=sample_model,
            prices=prices,
            market_value=market_value,
        )

        # Assert
        mock_optimization_engine.optimize_portfolio.assert_called_once_with(
            current_positions=current_positions,
            target_model=sample_model,
            prices=prices,
            market_value=market_value,
        )
        assert result == expected_result

    @pytest.mark.asyncio
    async def test_optimize_portfolio_infeasible(
        self, mock_optimization_engine, sample_model
    ):
        """Test optimization with infeasible constraints."""
        # Arrange
        current_positions = {"STOCK1234567890123456789": 100}
        prices = {"STOCK1234567890123456789": Decimal("50.00")}
        market_value = Decimal("1000")  # Too small for constraints

        infeasible_result = OptimizationResult(
            optimal_quantities={},
            objective_value=None,
            solver_status="INFEASIBLE",
            solve_time_seconds=1.0,
            is_feasible=False,
        )

        mock_optimization_engine.optimize_portfolio.return_value = infeasible_result

        # Act
        result = await mock_optimization_engine.optimize_portfolio(
            current_positions=current_positions,
            target_model=sample_model,
            prices=prices,
            market_value=market_value,
        )

        # Assert
        assert result.is_feasible is False
        assert result.solver_status == "INFEASIBLE"

    @pytest.mark.asyncio
    async def test_validate_solution(self, mock_optimization_engine):
        """Test solution validation."""
        # Arrange
        solution = {"STOCK1234567890123456789": 600, "STOCK9876543210987654321": 333}
        mock_optimization_engine.validate_solution.return_value = True

        # Act
        result = await mock_optimization_engine.validate_solution(solution)

        # Assert
        mock_optimization_engine.validate_solution.assert_called_once_with(solution)
        assert result is True

    @pytest.mark.asyncio
    async def test_check_solver_health(self, mock_optimization_engine):
        """Test solver health check."""
        # Arrange
        mock_optimization_engine.check_solver_health.return_value = True

        # Act
        result = await mock_optimization_engine.check_solver_health()

        # Assert
        mock_optimization_engine.check_solver_health.assert_called_once()
        assert result is True


@pytest.mark.unit
class TestDriftCalculatorInterface:
    """Test Drift Calculator interface contract."""

    @pytest.fixture
    def mock_drift_calculator(self) -> DriftCalculator:
        """Create a mock drift calculator for testing."""
        calculator = Mock(spec=DriftCalculator)
        calculator.calculate_portfolio_drift = AsyncMock()
        calculator.calculate_position_drift = AsyncMock()
        calculator.calculate_total_drift = AsyncMock()
        calculator.get_positions_outside_bounds = AsyncMock()
        return calculator

    @pytest.fixture
    def sample_model(self) -> InvestmentModel:
        """Create a sample investment model."""
        return InvestmentModel(
            model_id=ObjectId(),
            name="Test Model",
            positions=[
                Position(
                    security_id="STOCK1234567890123456789",
                    target=TargetPercentage(Decimal("0.30")),
                    drift_bounds=DriftBounds(
                        low_drift=Decimal("0.02"), high_drift=Decimal("0.03")
                    ),
                ),
            ],
            portfolios=["portfolio1"],
            version=1,
        )

    @pytest.mark.asyncio
    async def test_drift_calculator_has_required_methods(self, mock_drift_calculator):
        """Test that drift calculator has all required methods."""
        # Verify interface methods exist
        assert hasattr(mock_drift_calculator, "calculate_portfolio_drift")
        assert hasattr(mock_drift_calculator, "calculate_position_drift")
        assert hasattr(mock_drift_calculator, "calculate_total_drift")
        assert hasattr(mock_drift_calculator, "get_positions_outside_bounds")

        # Verify methods are callable
        assert callable(mock_drift_calculator.calculate_portfolio_drift)
        assert callable(mock_drift_calculator.calculate_position_drift)
        assert callable(mock_drift_calculator.calculate_total_drift)
        assert callable(mock_drift_calculator.get_positions_outside_bounds)

    @pytest.mark.asyncio
    async def test_calculate_portfolio_drift(self, mock_drift_calculator, sample_model):
        """Test portfolio drift calculation."""
        # Arrange
        current_positions = {"STOCK1234567890123456789": 500}
        prices = {"STOCK1234567890123456789": Decimal("50.00")}
        market_value = Decimal("100000")

        expected_drift_info = DriftInfo(
            security_id="STOCK1234567890123456789",
            current_value=Decimal("25000"),
            target_value=Decimal("30000"),
            current_percentage=Decimal("0.25"),
            target_percentage=Decimal("0.30"),
            drift_amount=Decimal("-0.05"),
            is_within_bounds=False,
        )

        mock_drift_calculator.calculate_portfolio_drift.return_value = [
            expected_drift_info
        ]

        # Act
        result = await mock_drift_calculator.calculate_portfolio_drift(
            positions=current_positions,
            prices=prices,
            market_value=market_value,
            model=sample_model,
        )

        # Assert
        mock_drift_calculator.calculate_portfolio_drift.assert_called_once_with(
            positions=current_positions,
            prices=prices,
            market_value=market_value,
            model=sample_model,
        )
        assert result == [expected_drift_info]

    @pytest.mark.asyncio
    async def test_calculate_position_drift(self, mock_drift_calculator):
        """Test individual position drift calculation."""
        # Arrange
        security_id = "STOCK1234567890123456789"
        current_value = Decimal("25000")
        target_percentage = Decimal("0.30")
        market_value = Decimal("100000")

        expected_drift = Decimal("-0.05")  # (25000/100000) - 0.30 = -0.05
        mock_drift_calculator.calculate_position_drift.return_value = expected_drift

        # Act
        result = await mock_drift_calculator.calculate_position_drift(
            current_value=current_value,
            target_percentage=target_percentage,
            market_value=market_value,
        )

        # Assert
        mock_drift_calculator.calculate_position_drift.assert_called_once_with(
            current_value=current_value,
            target_percentage=target_percentage,
            market_value=market_value,
        )
        assert result == expected_drift

    @pytest.mark.asyncio
    async def test_calculate_total_drift(self, mock_drift_calculator):
        """Test total portfolio drift calculation."""
        # Arrange
        drift_infos = [
            DriftInfo(
                security_id="STOCK1234567890123456789",
                current_value=Decimal("25000"),
                target_value=Decimal("30000"),
                current_percentage=Decimal("0.25"),
                target_percentage=Decimal("0.30"),
                drift_amount=Decimal("-0.05"),
                is_within_bounds=False,
            )
        ]

        expected_total_drift = Decimal("0.05")
        mock_drift_calculator.calculate_total_drift.return_value = expected_total_drift

        # Act
        result = await mock_drift_calculator.calculate_total_drift(drift_infos)

        # Assert
        mock_drift_calculator.calculate_total_drift.assert_called_once_with(drift_infos)
        assert result == expected_total_drift

    @pytest.mark.asyncio
    async def test_get_positions_outside_bounds(self, mock_drift_calculator):
        """Test finding positions outside drift bounds."""
        # Arrange
        drift_infos = []
        expected_outside_bounds = []
        mock_drift_calculator.get_positions_outside_bounds.return_value = (
            expected_outside_bounds
        )

        # Act
        result = await mock_drift_calculator.get_positions_outside_bounds(drift_infos)

        # Assert
        mock_drift_calculator.get_positions_outside_bounds.assert_called_once_with(
            drift_infos
        )
        assert result == expected_outside_bounds


@pytest.mark.unit
class TestValidationServiceInterface:
    """Test Validation Service interface contract."""

    @pytest.fixture
    def mock_validation_service(self) -> ValidationService:
        """Create a mock validation service for testing."""
        service = Mock(spec=ValidationService)
        service.validate_model = AsyncMock()
        service.validate_optimization_inputs = AsyncMock()
        service.validate_business_rules = AsyncMock()
        service.validate_market_data = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_validation_service_has_required_methods(
        self, mock_validation_service
    ):
        """Test that validation service has all required methods."""
        # Verify interface methods exist
        assert hasattr(mock_validation_service, "validate_model")
        assert hasattr(mock_validation_service, "validate_optimization_inputs")
        assert hasattr(mock_validation_service, "validate_business_rules")
        assert hasattr(mock_validation_service, "validate_market_data")

        # Verify methods are callable
        assert callable(mock_validation_service.validate_model)
        assert callable(mock_validation_service.validate_optimization_inputs)
        assert callable(mock_validation_service.validate_business_rules)
        assert callable(mock_validation_service.validate_market_data)

    @pytest.mark.asyncio
    async def test_validate_model(self, mock_validation_service):
        """Test model validation."""
        # Arrange
        model = InvestmentModel(
            model_id=ObjectId(),
            name="Test Model",
            positions=[],
            portfolios=["portfolio1"],
            version=1,
        )

        mock_validation_service.validate_model.return_value = True

        # Act
        result = await mock_validation_service.validate_model(model)

        # Assert
        mock_validation_service.validate_model.assert_called_once_with(model)
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_optimization_inputs(self, mock_validation_service):
        """Test optimization input validation."""
        # Arrange
        current_positions = {"STOCK1": 100}
        prices = {"STOCK1": Decimal("50.00")}
        market_value = Decimal("100000")

        mock_validation_service.validate_optimization_inputs.return_value = True

        # Act
        result = await mock_validation_service.validate_optimization_inputs(
            current_positions=current_positions,
            prices=prices,
            market_value=market_value,
        )

        # Assert
        mock_validation_service.validate_optimization_inputs.assert_called_once_with(
            current_positions=current_positions,
            prices=prices,
            market_value=market_value,
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_business_rules(self, mock_validation_service):
        """Test business rule validation."""
        # Arrange
        model = InvestmentModel(
            model_id=ObjectId(),
            name="Test Model",
            positions=[],
            portfolios=["portfolio1"],
            version=1,
        )

        mock_validation_service.validate_business_rules.return_value = True

        # Act
        result = await mock_validation_service.validate_business_rules(model)

        # Assert
        mock_validation_service.validate_business_rules.assert_called_once_with(model)
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_market_data(self, mock_validation_service):
        """Test market data validation."""
        # Arrange
        prices = {"STOCK1": Decimal("50.00"), "STOCK2": Decimal("75.00")}
        mock_validation_service.validate_market_data.return_value = True

        # Act
        result = await mock_validation_service.validate_market_data(prices)

        # Assert
        mock_validation_service.validate_market_data.assert_called_once_with(prices)
        assert result is True
