"""
Integration tests for MongoDB database implementation.

This module tests the concrete MongoDB repository implementation with real database
operations, following TDD principles by defining the expected behavior for
database integration before implementing the actual repository.

Tests use MongoDB test containers for isolated testing environment.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional

import pytest
import pytest_asyncio
from beanie import init_beanie
from bson import ObjectId

from src.core.exceptions import ConcurrencyError, NotFoundError, RepositoryError
from src.domain.entities.model import InvestmentModel
from src.domain.entities.position import Position
from src.domain.value_objects.drift_bounds import DriftBounds
from src.domain.value_objects.target_percentage import TargetPercentage
from src.infrastructure.database.repositories.model_repository import (
    MongoModelRepository,
)
from src.models.model import ModelDocument


@pytest.mark.integration
class TestMongoModelRepositoryIntegration:
    """Integration tests for MongoDB model repository implementation."""

    @pytest_asyncio.fixture
    async def repository(self, test_database) -> MongoModelRepository:
        """Create a MongoDB model repository instance."""
        # Initialize Beanie for testing
        await init_beanie(database=test_database, document_models=[ModelDocument])
        return MongoModelRepository()

    @pytest_asyncio.fixture
    async def sample_model(self) -> InvestmentModel:
        """Create a sample investment model for testing."""
        return InvestmentModel(
            model_id=ObjectId(),
            name="Integration Test Model",
            positions=[
                Position(
                    security_id="STOCK1234567890123456789",
                    target=TargetPercentage(Decimal("0.40")),
                    drift_bounds=DriftBounds(
                        low_drift=Decimal("0.02"), high_drift=Decimal("0.03")
                    ),
                ),
                Position(
                    security_id="BOND1111111111111111111A",
                    target=TargetPercentage(Decimal("0.35")),
                    drift_bounds=DriftBounds(
                        low_drift=Decimal("0.015"), high_drift=Decimal("0.025")
                    ),
                ),
            ],
            portfolios=["portfolio-integration-1", "portfolio-integration-2"],
            version=1,
        )

    @pytest.mark.asyncio
    async def test_create_model_success(self, repository, sample_model):
        """Test successful model creation in MongoDB."""
        # Act
        result = await repository.create(sample_model)

        # Assert
        assert result is not None
        assert result.model_id == sample_model.model_id
        assert result.name == sample_model.name
        assert len(result.positions) == 2
        assert len(result.portfolios) == 2
        assert result.version == 1
        assert result.last_rebalance_date is None

        # Verify persistence
        retrieved = await repository.get_by_id(str(result.model_id))
        assert retrieved is not None
        assert retrieved.name == sample_model.name

    @pytest.mark.asyncio
    async def test_create_model_duplicate_name_fails(self, repository, sample_model):
        """Test that creating model with duplicate name fails."""
        # Arrange
        await repository.create(sample_model)

        # Create another model with same name
        duplicate_model = InvestmentModel(
            model_id=ObjectId(),
            name=sample_model.name,  # Same name
            positions=[
                Position(
                    security_id="DIFFERENT123456789012345",
                    target=TargetPercentage(Decimal("0.50")),
                    drift_bounds=DriftBounds(
                        low_drift=Decimal("0.01"), high_drift=Decimal("0.02")
                    ),
                )
            ],
            portfolios=["different-portfolio"],
            version=1,
        )

        # Act & Assert
        with pytest.raises(RepositoryError, match="already exists"):
            await repository.create(duplicate_model)

    @pytest.mark.asyncio
    async def test_get_by_id_success(self, repository, sample_model):
        """Test successful model retrieval by ID."""
        # Arrange
        created = await repository.create(sample_model)

        # Act
        result = await repository.get_by_id(str(created.model_id))

        # Assert
        assert result is not None
        assert result.model_id == created.model_id
        assert result.name == created.name
        assert len(result.positions) == len(created.positions)
        assert result.portfolios == created.portfolios

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, repository):
        """Test model retrieval with non-existent ID."""
        # Arrange
        non_existent_id = str(ObjectId())

        # Act
        result = await repository.get_by_id(non_existent_id)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_name_success(self, repository, sample_model):
        """Test successful model retrieval by name."""
        # Arrange
        created = await repository.create(sample_model)

        # Act
        result = await repository.get_by_name(created.name)

        # Assert
        assert result is not None
        assert result.model_id == created.model_id
        assert result.name == created.name

    @pytest.mark.asyncio
    async def test_get_by_name_not_found(self, repository):
        """Test model retrieval with non-existent name."""
        # Act
        result = await repository.get_by_name("Non-existent Model")

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_update_model_success(self, repository, sample_model):
        """Test successful model update with optimistic locking."""
        # Arrange
        created = await repository.create(sample_model)

        # Modify the model
        updated_model = InvestmentModel(
            model_id=created.model_id,
            name="Updated Integration Test Model",
            positions=created.positions,
            portfolios=created.portfolios + ["new-portfolio"],
            last_rebalance_date=datetime.now(timezone.utc),
            version=created.version,
        )

        # Act
        result = await repository.update(updated_model)

        # Assert
        assert result.name == "Updated Integration Test Model"
        assert len(result.portfolios) == 3
        assert "new-portfolio" in result.portfolios
        assert result.version == created.version + 1
        assert result.last_rebalance_date is not None

    @pytest.mark.asyncio
    async def test_update_model_concurrent_modification_fails(
        self, repository, sample_model
    ):
        """Test that concurrent model modifications fail with optimistic locking."""
        # Arrange
        created = await repository.create(sample_model)

        # Simulate concurrent modification by updating version in database
        await ModelDocument.find_one({"_id": created.model_id}).update(
            {"$inc": {"version": 1}}
        )

        # Try to update with stale version
        updated_model = InvestmentModel(
            model_id=created.model_id,
            name="Concurrent Update",
            positions=created.positions,
            portfolios=created.portfolios,
            version=created.version,  # Stale version
        )

        # Act & Assert
        with pytest.raises(ConcurrencyError, match="has been modified"):
            await repository.update(updated_model)

    @pytest.mark.asyncio
    async def test_delete_model_success(self, repository, sample_model):
        """Test successful model deletion."""
        # Arrange
        created = await repository.create(sample_model)

        # Act
        success = await repository.delete(str(created.model_id))

        # Assert
        assert success is True

        # Verify deletion
        result = await repository.get_by_id(str(created.model_id))
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_model_not_found(self, repository):
        """Test deletion of non-existent model."""
        # Arrange
        non_existent_id = str(ObjectId())

        # Act
        success = await repository.delete(non_existent_id)

        # Assert
        assert success is False

    @pytest.mark.asyncio
    async def test_list_all_models(self, repository, sample_model):
        """Test listing all models."""
        # Arrange
        model1 = await repository.create(sample_model)

        model2 = InvestmentModel(
            model_id=ObjectId(),
            name="Second Integration Model",
            positions=[
                Position(
                    security_id="STOCK9876543210987654321",
                    target=TargetPercentage(Decimal("0.60")),
                    drift_bounds=DriftBounds(
                        low_drift=Decimal("0.03"), high_drift=Decimal("0.04")
                    ),
                )
            ],
            portfolios=["portfolio-2"],
            version=1,
        )
        model2 = await repository.create(model2)

        # Act
        results = await repository.list_all()

        # Assert
        assert len(results) >= 2
        model_ids = [model.model_id for model in results]
        assert model1.model_id in model_ids
        assert model2.model_id in model_ids

    @pytest.mark.asyncio
    async def test_exists_by_name_true(self, repository, sample_model):
        """Test model existence check returns true for existing model."""
        # Arrange
        created = await repository.create(sample_model)

        # Act
        exists = await repository.exists_by_name(created.name)

        # Assert
        assert exists is True

    @pytest.mark.asyncio
    async def test_exists_by_name_false(self, repository):
        """Test model existence check returns false for non-existent model."""
        # Act
        exists = await repository.exists_by_name("Non-existent Model")

        # Assert
        assert exists is False

    @pytest.mark.asyncio
    async def test_find_by_portfolio_filtering(self, repository, sample_model):
        """Test finding models by portfolio association."""
        # Arrange
        created = await repository.create(sample_model)

        # Act
        results = await repository.find_by_portfolio("portfolio-integration-1")

        # Assert
        assert len(results) >= 1
        found_model = next((m for m in results if m.model_id == created.model_id), None)
        assert found_model is not None
        assert "portfolio-integration-1" in found_model.portfolios

    @pytest.mark.asyncio
    async def test_find_by_portfolio_no_results(self, repository):
        """Test finding models by non-existent portfolio."""
        # Act
        results = await repository.find_by_portfolio("non-existent-portfolio")

        # Assert
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_find_by_last_rebalance_date(self, repository, sample_model):
        """Test finding models by last rebalance date."""
        # Arrange - Use a fixed cutoff date to avoid precision issues
        cutoff_date = datetime(
            2024, 1, 1, 12, 0, 0
        )  # Timezone-naive to match domain entity

        # Create model with recent rebalance date
        recent_model = InvestmentModel(
            model_id=sample_model.model_id,
            name=sample_model.name,
            positions=sample_model.positions,
            portfolios=sample_model.portfolios,
            last_rebalance_date=cutoff_date,
            version=1,
        )
        created = await repository.create(recent_model)

        # Act
        results = await repository.find_by_last_rebalance_date(cutoff_date)

        # Assert
        assert len(results) >= 1
        found_model = next((m for m in results if m.model_id == created.model_id), None)
        assert found_model is not None
        # Convert both to naive datetime for comparison if needed
        found_date = found_model.last_rebalance_date
        if found_date and found_date.tzinfo is not None:
            found_date = found_date.replace(tzinfo=None)
        assert found_date >= cutoff_date

    @pytest.mark.asyncio
    async def test_get_models_by_security(self, repository, sample_model):
        """Test finding models that contain a specific security."""
        # Arrange
        created = await repository.create(sample_model)

        # Act
        results = await repository.get_models_by_security("STOCK1234567890123456789")

        # Assert
        assert len(results) >= 1
        found_model = next((m for m in results if m.model_id == created.model_id), None)
        assert found_model is not None

        # Verify the security is in the model
        security_ids = [pos.security_id for pos in found_model.positions]
        assert "STOCK1234567890123456789" in security_ids

    @pytest.mark.asyncio
    async def test_get_portfolio_count(self, repository, sample_model):
        """Test getting total portfolio count across all models."""
        # Arrange
        await repository.create(sample_model)

        # Act
        count = await repository.get_portfolio_count()

        # Assert
        assert count >= 2  # At least the portfolios from our sample model

    @pytest.mark.asyncio
    async def test_get_position_count(self, repository, sample_model):
        """Test getting total position count across all models."""
        # Arrange
        await repository.create(sample_model)

        # Act
        count = await repository.get_position_count()

        # Assert
        assert count >= 2  # At least the positions from our sample model

    @pytest.mark.asyncio
    async def test_find_models_needing_rebalance(self, repository, sample_model):
        """Test finding models that need rebalancing."""
        # Arrange - Create model without recent rebalance
        old_rebalance_model = InvestmentModel(
            model_id=sample_model.model_id,
            name=sample_model.name,
            positions=sample_model.positions,
            portfolios=sample_model.portfolios,
            last_rebalance_date=None,  # Never rebalanced
            version=1,
        )
        created = await repository.create(old_rebalance_model)

        # Act
        results = await repository.find_models_needing_rebalance(days_threshold=1)

        # Assert
        assert len(results) >= 1
        found_model = next((m for m in results if m.model_id == created.model_id), None)
        assert found_model is not None
        assert found_model.last_rebalance_date is None

    @pytest.mark.asyncio
    async def test_database_connection_error_handling(self, repository):
        """Test graceful handling of database connection errors."""
        # This test would require mocking the database connection
        # For now, we'll test that the repository handles basic error scenarios

        # Test with invalid ObjectId format
        with pytest.raises((ValueError, RepositoryError)):
            await repository.get_by_id("invalid-object-id")

    @pytest.mark.asyncio
    async def test_large_model_handling(self, repository):
        """Test handling of models with many positions."""
        # Arrange - Create model with maximum positions
        positions = []
        for i in range(100):  # Maximum allowed positions
            positions.append(
                Position(
                    security_id=f"STOCK{i:019d}",  # 24-char security ID
                    target=TargetPercentage(Decimal("0.005")),  # Small valid target
                    drift_bounds=DriftBounds(
                        low_drift=Decimal("0.01"), high_drift=Decimal("0.02")
                    ),
                )
            )

        large_model = InvestmentModel(
            model_id=ObjectId(),
            name="Large Integration Model",
            positions=positions,
            portfolios=["large-portfolio"],
            version=1,
        )

        # Act
        created = await repository.create(large_model)
        retrieved = await repository.get_by_id(str(created.model_id))

        # Assert
        assert retrieved is not None
        assert len(retrieved.positions) == 100
        assert retrieved.name == "Large Integration Model"


@pytest.mark.integration
class TestBeanieODMIntegration:
    """Integration tests for Beanie ODM document operations."""

    @pytest.mark.asyncio
    async def test_document_creation_and_validation(self, test_database):
        """Test Beanie document creation with validation."""
        # Initialize Beanie for testing
        await init_beanie(database=test_database, document_models=[ModelDocument])

        # Arrange
        doc = ModelDocument(
            name="ODM Test Model",
            positions=[
                {
                    "security_id": "STOCK1234567890123456789",
                    "target": Decimal("0.40"),
                    "high_drift": Decimal("0.03"),
                    "low_drift": Decimal("0.02"),
                }
            ],
            portfolios=["odm-portfolio"],
            version=1,
        )

        # Act
        saved_doc = await doc.create()

        # Assert
        assert saved_doc.id is not None
        assert saved_doc.name == "ODM Test Model"
        assert len(saved_doc.positions) == 1
        assert saved_doc.version == 1

    @pytest.mark.asyncio
    async def test_document_indexing(self, test_database):
        """Test that database indexes are working correctly."""
        # Initialize Beanie for testing
        await init_beanie(database=test_database, document_models=[ModelDocument])

        # Arrange - Create multiple documents
        docs = []
        for i in range(5):
            doc = ModelDocument(
                name=f"Index Test Model {i}",
                positions=[],
                portfolios=[f"portfolio-{i}"],
                version=1,
            )
            docs.append(await doc.create())

        # Act - Query by name (should use unique index)
        found_by_name = await ModelDocument.find_one({"name": "Index Test Model 2"})

        # Assert
        assert found_by_name is not None
        assert found_by_name.name == "Index Test Model 2"

        # Act - Query by portfolio (should use multikey index)
        found_by_portfolio = await ModelDocument.find(
            {"portfolios": "portfolio-3"}
        ).to_list()

        # Assert
        assert len(found_by_portfolio) == 1
        assert found_by_portfolio[0].name == "Index Test Model 3"

    @pytest.mark.asyncio
    async def test_document_aggregation_pipeline(self, test_database):
        """Test MongoDB aggregation pipeline operations."""
        # Initialize Beanie for testing
        await init_beanie(database=test_database, document_models=[ModelDocument])

        # Arrange - Create test documents
        test_docs = []
        for i in range(3):
            doc = ModelDocument(
                name=f"Aggregation Model {i}",
                positions=[
                    {
                        "security_id": f"STOCK{j:019d}",
                        "target": Decimal("0.10"),
                        "high_drift": Decimal("0.02"),
                        "low_drift": Decimal("0.01"),
                    }
                    for j in range(i + 1)  # Different number of positions
                ],
                portfolios=[f"agg-portfolio-{i}"],
                version=1,
            )
            test_docs.append(await doc.create())

        # Act - Aggregate position counts
        pipeline = [
            {"$project": {"name": 1, "position_count": {"$size": "$positions"}}},
            {"$sort": {"position_count": 1}},
        ]
        results = await ModelDocument.aggregate(pipeline).to_list()

        # Assert
        assert len(results) >= 3
        # Results should be sorted by position count
        for i in range(len(results) - 1):
            assert results[i]["position_count"] <= results[i + 1]["position_count"]
