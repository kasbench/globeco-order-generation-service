"""
Tests for Model Repository interface.

This module tests the Model Repository interface which defines the contract
for persisting and retrieving Investment Models.

Following TDD principles, these tests define the repository interface
that implementations must satisfy.
"""

from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, Mock

import pytest
from bson import ObjectId

from src.core.exceptions import BusinessRuleViolationError, ValidationError
from src.domain.entities.model import InvestmentModel
from src.domain.entities.position import Position
from src.domain.repositories.model_repository import ModelRepository
from src.domain.value_objects.drift_bounds import DriftBounds
from src.domain.value_objects.target_percentage import TargetPercentage


@pytest.mark.unit
class TestModelRepositoryInterface:
    """Test Model Repository interface contract."""

    @pytest.fixture
    def mock_repository(self) -> ModelRepository:
        """Create a mock repository for testing interface contract."""
        # Create a mock that implements the ModelRepository interface
        repository = Mock(spec=ModelRepository)

        # Make all methods async mocks
        repository.create = AsyncMock()
        repository.get_by_id = AsyncMock()
        repository.get_by_name = AsyncMock()
        repository.update = AsyncMock()
        repository.delete = AsyncMock()
        repository.list_all = AsyncMock()
        repository.find_by_portfolio = AsyncMock()
        repository.exists_by_name = AsyncMock()

        return repository

    @pytest.fixture
    def sample_model(self) -> InvestmentModel:
        """Create a sample investment model for testing."""
        return InvestmentModel(
            model_id=ObjectId(),
            name="Conservative Growth",
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
            portfolios=["portfolio1", "portfolio2"],
            version=1,
        )

    @pytest.mark.asyncio
    async def test_repository_has_required_methods(self, mock_repository):
        """Test that repository interface has all required methods."""
        # Verify interface methods exist
        assert hasattr(mock_repository, "create")
        assert hasattr(mock_repository, "get_by_id")
        assert hasattr(mock_repository, "get_by_name")
        assert hasattr(mock_repository, "update")
        assert hasattr(mock_repository, "delete")
        assert hasattr(mock_repository, "list_all")
        assert hasattr(mock_repository, "find_by_portfolio")
        assert hasattr(mock_repository, "exists_by_name")

        # Verify methods are callable
        assert callable(mock_repository.create)
        assert callable(mock_repository.get_by_id)
        assert callable(mock_repository.get_by_name)
        assert callable(mock_repository.update)
        assert callable(mock_repository.delete)
        assert callable(mock_repository.list_all)
        assert callable(mock_repository.find_by_portfolio)
        assert callable(mock_repository.exists_by_name)


@pytest.mark.unit
class TestModelRepositoryCreate:
    """Test Model Repository create operations."""

    @pytest.fixture
    def mock_repository(self) -> ModelRepository:
        """Create a mock repository for testing."""
        repository = Mock(spec=ModelRepository)
        repository.create = AsyncMock()
        return repository

    @pytest.fixture
    def sample_model(self) -> InvestmentModel:
        """Create a sample investment model."""
        return InvestmentModel(
            model_id=ObjectId(),
            name="Test Model",
            positions=[],
            portfolios=["portfolio1"],
            version=1,
        )

    @pytest.mark.asyncio
    async def test_create_model_success(self, mock_repository, sample_model):
        """Test successful model creation."""
        # Arrange
        mock_repository.create.return_value = sample_model

        # Act
        result = await mock_repository.create(sample_model)

        # Assert
        mock_repository.create.assert_called_once_with(sample_model)
        assert result == sample_model

    @pytest.mark.asyncio
    async def test_create_model_with_duplicate_name_raises_error(
        self, mock_repository, sample_model
    ):
        """Test that creating model with duplicate name raises error."""
        # Arrange
        mock_repository.create.side_effect = BusinessRuleViolationError(
            "Model with name 'Test Model' already exists"
        )

        # Act & Assert
        with pytest.raises(BusinessRuleViolationError, match="already exists"):
            await mock_repository.create(sample_model)

    @pytest.mark.asyncio
    async def test_create_model_validates_input(self, mock_repository):
        """Test that create method validates input."""
        # Arrange
        mock_repository.create.side_effect = ValidationError("Invalid model data")

        # Act & Assert
        with pytest.raises(ValidationError):
            await mock_repository.create(None)


@pytest.mark.unit
class TestModelRepositoryRead:
    """Test Model Repository read operations."""

    @pytest.fixture
    def mock_repository(self) -> ModelRepository:
        """Create a mock repository for testing."""
        repository = Mock(spec=ModelRepository)
        repository.get_by_id = AsyncMock()
        repository.get_by_name = AsyncMock()
        repository.list_all = AsyncMock()
        repository.find_by_portfolio = AsyncMock()
        repository.exists_by_name = AsyncMock()
        return repository

    @pytest.fixture
    def sample_model(self) -> InvestmentModel:
        """Create a sample investment model."""
        return InvestmentModel(
            model_id=ObjectId("507f1f77bcf86cd799439011"),
            name="Growth Model",
            positions=[],
            portfolios=["portfolio1"],
            version=1,
        )

    @pytest.mark.asyncio
    async def test_get_by_id_success(self, mock_repository, sample_model):
        """Test successful model retrieval by ID."""
        # Arrange
        model_id = "507f1f77bcf86cd799439011"
        mock_repository.get_by_id.return_value = sample_model

        # Act
        result = await mock_repository.get_by_id(model_id)

        # Assert
        mock_repository.get_by_id.assert_called_once_with(model_id)
        assert result == sample_model

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, mock_repository):
        """Test model retrieval by ID when not found."""
        # Arrange
        model_id = "507f1f77bcf86cd799439012"
        mock_repository.get_by_id.return_value = None

        # Act
        result = await mock_repository.get_by_id(model_id)

        # Assert
        mock_repository.get_by_id.assert_called_once_with(model_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_id_invalid_id_format(self, mock_repository):
        """Test model retrieval with invalid ID format."""
        # Arrange
        invalid_id = "invalid-id"
        mock_repository.get_by_id.side_effect = ValidationError(
            "Invalid ObjectId format"
        )

        # Act & Assert
        with pytest.raises(ValidationError, match="Invalid ObjectId"):
            await mock_repository.get_by_id(invalid_id)

    @pytest.mark.asyncio
    async def test_get_by_name_success(self, mock_repository, sample_model):
        """Test successful model retrieval by name."""
        # Arrange
        model_name = "Growth Model"
        mock_repository.get_by_name.return_value = sample_model

        # Act
        result = await mock_repository.get_by_name(model_name)

        # Assert
        mock_repository.get_by_name.assert_called_once_with(model_name)
        assert result == sample_model

    @pytest.mark.asyncio
    async def test_get_by_name_not_found(self, mock_repository):
        """Test model retrieval by name when not found."""
        # Arrange
        model_name = "Nonexistent Model"
        mock_repository.get_by_name.return_value = None

        # Act
        result = await mock_repository.get_by_name(model_name)

        # Assert
        mock_repository.get_by_name.assert_called_once_with(model_name)
        assert result is None

    @pytest.mark.asyncio
    async def test_list_all_models(self, mock_repository, sample_model):
        """Test listing all models."""
        # Arrange
        models = [sample_model]
        mock_repository.list_all.return_value = models

        # Act
        result = await mock_repository.list_all()

        # Assert
        mock_repository.list_all.assert_called_once()
        assert result == models

    @pytest.mark.asyncio
    async def test_list_all_empty(self, mock_repository):
        """Test listing all models when none exist."""
        # Arrange
        mock_repository.list_all.return_value = []

        # Act
        result = await mock_repository.list_all()

        # Assert
        mock_repository.list_all.assert_called_once()
        assert result == []

    @pytest.mark.asyncio
    async def test_find_by_portfolio(self, mock_repository, sample_model):
        """Test finding models by portfolio ID."""
        # Arrange
        portfolio_id = "portfolio1"
        models = [sample_model]
        mock_repository.find_by_portfolio.return_value = models

        # Act
        result = await mock_repository.find_by_portfolio(portfolio_id)

        # Assert
        mock_repository.find_by_portfolio.assert_called_once_with(portfolio_id)
        assert result == models

    @pytest.mark.asyncio
    async def test_find_by_portfolio_not_found(self, mock_repository):
        """Test finding models by portfolio when none exist."""
        # Arrange
        portfolio_id = "nonexistent-portfolio"
        mock_repository.find_by_portfolio.return_value = []

        # Act
        result = await mock_repository.find_by_portfolio(portfolio_id)

        # Assert
        mock_repository.find_by_portfolio.assert_called_once_with(portfolio_id)
        assert result == []

    @pytest.mark.asyncio
    async def test_exists_by_name_true(self, mock_repository):
        """Test checking if model exists by name (exists)."""
        # Arrange
        model_name = "Existing Model"
        mock_repository.exists_by_name.return_value = True

        # Act
        result = await mock_repository.exists_by_name(model_name)

        # Assert
        mock_repository.exists_by_name.assert_called_once_with(model_name)
        assert result is True

    @pytest.mark.asyncio
    async def test_exists_by_name_false(self, mock_repository):
        """Test checking if model exists by name (doesn't exist)."""
        # Arrange
        model_name = "Nonexistent Model"
        mock_repository.exists_by_name.return_value = False

        # Act
        result = await mock_repository.exists_by_name(model_name)

        # Assert
        mock_repository.exists_by_name.assert_called_once_with(model_name)
        assert result is False


@pytest.mark.unit
class TestModelRepositoryUpdate:
    """Test Model Repository update operations."""

    @pytest.fixture
    def mock_repository(self) -> ModelRepository:
        """Create a mock repository for testing."""
        repository = Mock(spec=ModelRepository)
        repository.update = AsyncMock()
        return repository

    @pytest.fixture
    def sample_model(self) -> InvestmentModel:
        """Create a sample investment model."""
        return InvestmentModel(
            model_id=ObjectId("507f1f77bcf86cd799439011"),
            name="Updated Model",
            positions=[],
            portfolios=["portfolio1"],
            version=2,  # Version incremented for update
        )

    @pytest.mark.asyncio
    async def test_update_model_success(self, mock_repository, sample_model):
        """Test successful model update."""
        # Arrange
        mock_repository.update.return_value = sample_model

        # Act
        result = await mock_repository.update(sample_model)

        # Assert
        mock_repository.update.assert_called_once_with(sample_model)
        assert result == sample_model

    @pytest.mark.asyncio
    async def test_update_model_not_found(self, mock_repository, sample_model):
        """Test update when model not found."""
        # Arrange
        mock_repository.update.side_effect = ValidationError("Model not found")

        # Act & Assert
        with pytest.raises(ValidationError, match="not found"):
            await mock_repository.update(sample_model)

    @pytest.mark.asyncio
    async def test_update_model_version_conflict(self, mock_repository, sample_model):
        """Test update with version conflict (optimistic locking)."""
        # Arrange
        mock_repository.update.side_effect = BusinessRuleViolationError(
            "Version conflict: model was updated by another process"
        )

        # Act & Assert
        with pytest.raises(BusinessRuleViolationError, match="Version conflict"):
            await mock_repository.update(sample_model)

    @pytest.mark.asyncio
    async def test_update_model_with_duplicate_name(
        self, mock_repository, sample_model
    ):
        """Test update that would create duplicate name."""
        # Arrange
        mock_repository.update.side_effect = BusinessRuleViolationError(
            "Model with name 'Updated Model' already exists"
        )

        # Act & Assert
        with pytest.raises(BusinessRuleViolationError, match="already exists"):
            await mock_repository.update(sample_model)


@pytest.mark.unit
class TestModelRepositoryDelete:
    """Test Model Repository delete operations."""

    @pytest.fixture
    def mock_repository(self) -> ModelRepository:
        """Create a mock repository for testing."""
        repository = Mock(spec=ModelRepository)
        repository.delete = AsyncMock()
        return repository

    @pytest.mark.asyncio
    async def test_delete_model_success(self, mock_repository):
        """Test successful model deletion."""
        # Arrange
        model_id = "507f1f77bcf86cd799439011"
        mock_repository.delete.return_value = True

        # Act
        result = await mock_repository.delete(model_id)

        # Assert
        mock_repository.delete.assert_called_once_with(model_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_model_not_found(self, mock_repository):
        """Test deletion when model not found."""
        # Arrange
        model_id = "507f1f77bcf86cd799439012"
        mock_repository.delete.return_value = False

        # Act
        result = await mock_repository.delete(model_id)

        # Assert
        mock_repository.delete.assert_called_once_with(model_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_model_invalid_id(self, mock_repository):
        """Test deletion with invalid ID format."""
        # Arrange
        invalid_id = "invalid-id"
        mock_repository.delete.side_effect = ValidationError("Invalid ObjectId format")

        # Act & Assert
        with pytest.raises(ValidationError, match="Invalid ObjectId"):
            await mock_repository.delete(invalid_id)


@pytest.mark.unit
class TestModelRepositoryQueryFiltering:
    """Test Model Repository query filtering operations."""

    @pytest.fixture
    def mock_repository(self) -> ModelRepository:
        """Create a mock repository for testing."""
        repository = Mock(spec=ModelRepository)
        repository.find_by_portfolio = AsyncMock()
        repository.find_by_last_rebalance_date = AsyncMock()
        repository.find_models_needing_rebalance = AsyncMock()
        return repository

    @pytest.mark.asyncio
    async def test_find_by_portfolio_filters_correctly(self, mock_repository):
        """Test that portfolio filtering works correctly."""
        # Arrange
        portfolio_id = "portfolio123"
        expected_models = [
            InvestmentModel(
                model_id=ObjectId(),
                name="Model 1",
                positions=[],
                portfolios=["portfolio123", "portfolio456"],
                version=1,
            )
        ]
        mock_repository.find_by_portfolio.return_value = expected_models

        # Act
        result = await mock_repository.find_by_portfolio(portfolio_id)

        # Assert
        mock_repository.find_by_portfolio.assert_called_once_with(portfolio_id)
        assert result == expected_models

    @pytest.mark.asyncio
    async def test_find_by_last_rebalance_date(self, mock_repository):
        """Test filtering by last rebalance date."""
        # Arrange
        cutoff_date = datetime.utcnow()
        expected_models = []
        mock_repository.find_by_last_rebalance_date.return_value = expected_models

        # Act
        result = await mock_repository.find_by_last_rebalance_date(cutoff_date)

        # Assert
        mock_repository.find_by_last_rebalance_date.assert_called_once_with(cutoff_date)
        assert result == expected_models

    @pytest.mark.asyncio
    async def test_find_models_needing_rebalance(self, mock_repository):
        """Test finding models that need rebalancing."""
        # Arrange
        expected_models = []
        mock_repository.find_models_needing_rebalance.return_value = expected_models

        # Act
        result = await mock_repository.find_models_needing_rebalance()

        # Assert
        mock_repository.find_models_needing_rebalance.assert_called_once()
        assert result == expected_models


@pytest.mark.unit
class TestModelRepositoryOptimisticLocking:
    """Test Model Repository optimistic locking behavior."""

    @pytest.fixture
    def mock_repository(self) -> ModelRepository:
        """Create a mock repository for testing."""
        repository = Mock(spec=ModelRepository)
        repository.update = AsyncMock()
        repository.get_by_id = AsyncMock()
        return repository

    @pytest.mark.asyncio
    async def test_optimistic_locking_version_check(self, mock_repository):
        """Test that optimistic locking checks version."""
        # Arrange
        model = InvestmentModel(
            model_id=ObjectId("507f1f77bcf86cd799439011"),
            name="Test Model",
            positions=[],
            portfolios=["portfolio1"],
            version=1,
        )

        # Simulate version conflict
        mock_repository.update.side_effect = BusinessRuleViolationError(
            "Version conflict: expected version 1, but found version 2"
        )

        # Act & Assert
        with pytest.raises(BusinessRuleViolationError, match="Version conflict"):
            await mock_repository.update(model)

    @pytest.mark.asyncio
    async def test_optimistic_locking_success_increments_version(self, mock_repository):
        """Test that successful update increments version."""
        # Arrange
        original_model = InvestmentModel(
            model_id=ObjectId("507f1f77bcf86cd799439011"),
            name="Test Model",
            positions=[],
            portfolios=["portfolio1"],
            version=1,
        )

        updated_model = InvestmentModel(
            model_id=ObjectId("507f1f77bcf86cd799439011"),
            name="Test Model",
            positions=[],
            portfolios=["portfolio1"],
            version=2,  # Version incremented
        )

        mock_repository.update.return_value = updated_model

        # Act
        result = await mock_repository.update(original_model)

        # Assert
        assert result.version == 2
        assert result.version > original_model.version
