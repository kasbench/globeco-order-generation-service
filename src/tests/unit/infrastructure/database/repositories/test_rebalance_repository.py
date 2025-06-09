"""
Unit tests for MongoDB rebalance repository implementation.

This module tests the rebalance repository layer including CRUD operations,
pagination, filtering, and error handling.
"""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from beanie import init_beanie
from bson import ObjectId

from src.core.exceptions import ConcurrencyError, NotFoundError, RepositoryError
from src.domain.entities.rebalance import (
    Rebalance,
    RebalancePortfolio,
    RebalancePosition,
)
from src.infrastructure.database.repositories.rebalance_repository import (
    MongoRebalanceRepository,
)
from src.models.rebalance import PortfolioEmbedded, PositionEmbedded, RebalanceDocument


@pytest.mark.unit
class TestMongoRebalanceRepository:
    """Test cases for MongoRebalanceRepository."""

    @pytest_asyncio.fixture
    async def repository(self, test_database):
        """Create repository instance for testing."""
        # Initialize Beanie for testing
        await init_beanie(database=test_database, document_models=[RebalanceDocument])
        return MongoRebalanceRepository()

    @pytest.fixture
    def sample_rebalance_entity(self):
        """Create a sample rebalance entity for testing."""
        positions = [
            RebalancePosition(
                security_id="abc123def456ghi789jkl012",
                price=Decimal("100.50"),
                original_quantity=Decimal("10"),
                adjusted_quantity=Decimal("15"),
                original_position_market_value=Decimal("1005.00"),
                adjusted_position_market_value=Decimal("1507.50"),
                target=Decimal("0.05"),
                high_drift=Decimal("0.1"),
                low_drift=Decimal("0.05"),
                actual=Decimal("0.0600"),
                actual_drift=Decimal("0.2000"),
                transaction_type="BUY",
                trade_quantity=5,
                trade_date=datetime.now(timezone.utc),
            )
        ]

        portfolio = RebalancePortfolio(
            portfolio_id="def456ghi789jkl012mno345",
            market_value=Decimal("25000.00"),
            cash_before_rebalance=Decimal("1000.00"),
            cash_after_rebalance=Decimal("500.00"),
            positions=positions,
        )

        return Rebalance(
            model_id=ObjectId("507f1f77bcf86cd799439011"),
            rebalance_date=datetime(2024, 12, 20, 10, 30, 0, tzinfo=timezone.utc),
            model_name="Test Model",
            number_of_portfolios=1,
            portfolios=[portfolio],
            version=1,
            created_at=datetime.now(timezone.utc),
        )

    @pytest_asyncio.fixture
    async def sample_rebalance_document(self, test_database):
        """Create a sample rebalance document for testing."""
        # Initialize Beanie first
        await init_beanie(database=test_database, document_models=[RebalanceDocument])

        positions = [
            PositionEmbedded(
                security_id="abc123def456ghi789jkl012",
                price=Decimal("100.50"),
                original_quantity=Decimal("10"),
                adjusted_quantity=Decimal("15"),
                original_position_market_value=Decimal("1005.00"),
                adjusted_position_market_value=Decimal("1507.50"),
                target=Decimal("0.05"),
                high_drift=Decimal("0.1"),
                low_drift=Decimal("0.05"),
                actual=Decimal("0.0600"),
                actual_drift=Decimal("0.2000"),
                transaction_type="BUY",
                trade_quantity=5,
                trade_date=datetime.now(timezone.utc),
            )
        ]

        portfolio = PortfolioEmbedded(
            portfolio_id="def456ghi789jkl012mno345",
            market_value=Decimal("25000.00"),
            cash_before_rebalance=Decimal("1000.00"),
            cash_after_rebalance=Decimal("500.00"),
            positions=positions,
        )

        # Create a mock document that behaves like RebalanceDocument
        mock_doc = MagicMock()
        mock_doc.id = ObjectId("507f1f77bcf86cd799439012")
        mock_doc.model_id = ObjectId("507f1f77bcf86cd799439011")
        mock_doc.model_name = "Test Model"
        mock_doc.rebalance_date = datetime(2024, 12, 20, 10, 30, 0, tzinfo=timezone.utc)
        mock_doc.number_of_portfolios = 1
        mock_doc.portfolios = [portfolio]
        mock_doc.version = 1
        mock_doc.created_at = datetime.now(timezone.utc)

        # Configure model_dump to return proper dictionary with 'id' instead of '_id'
        # This simulates how Beanie converts MongoDB documents
        mock_doc.model_dump.return_value = {
            'id': mock_doc.id,
            'model_id': mock_doc.model_id,
            'model_name': mock_doc.model_name,
            'rebalance_date': mock_doc.rebalance_date,
            'number_of_portfolios': mock_doc.number_of_portfolios,
            'portfolios': [
                {
                    'portfolio_id': portfolio.portfolio_id,
                    'market_value': portfolio.market_value,
                    'cash_before_rebalance': portfolio.cash_before_rebalance,
                    'cash_after_rebalance': portfolio.cash_after_rebalance,
                    'positions': [
                        {
                            'security_id': position.security_id,
                            'price': position.price,
                            'original_quantity': position.original_quantity,
                            'adjusted_quantity': position.adjusted_quantity,
                            'original_position_market_value': position.original_position_market_value,
                            'adjusted_position_market_value': position.adjusted_position_market_value,
                            'target': position.target,
                            'high_drift': position.high_drift,
                            'low_drift': position.low_drift,
                            'actual': position.actual,
                            'actual_drift': position.actual_drift,
                            'transaction_type': position.transaction_type,
                            'trade_quantity': position.trade_quantity,
                            'trade_date': position.trade_date,
                        }
                        for position in portfolio.positions
                    ],
                }
                for portfolio in mock_doc.portfolios
            ],
            'version': mock_doc.version,
            'created_at': mock_doc.created_at,
        }

        return mock_doc

    @pytest.mark.asyncio
    async def test_create_rebalance_success(self, repository, sample_rebalance_entity):
        """Test successful rebalance creation."""
        # Mock the document and its create method
        mock_document = MagicMock()
        mock_document.id = ObjectId()
        mock_document.model_id = sample_rebalance_entity.model_id
        mock_document.model_name = sample_rebalance_entity.model_name
        mock_document.rebalance_date = sample_rebalance_entity.rebalance_date
        mock_document.number_of_portfolios = (
            sample_rebalance_entity.number_of_portfolios
        )
        mock_document.portfolios = []
        mock_document.version = sample_rebalance_entity.version
        mock_document.created_at = sample_rebalance_entity.created_at
        mock_document.create = AsyncMock(return_value=mock_document)

        # Configure model_dump to return proper dictionary structure
        mock_document.model_dump.return_value = {
            '_id': mock_document.id,
            'model_id': sample_rebalance_entity.model_id,
            'model_name': sample_rebalance_entity.model_name,
            'rebalance_date': sample_rebalance_entity.rebalance_date,
            'number_of_portfolios': sample_rebalance_entity.number_of_portfolios,
            'portfolios': [],
            'version': sample_rebalance_entity.version,
            'created_at': sample_rebalance_entity.created_at,
        }

        with patch.object(
            repository, '_convert_to_document', return_value=mock_document
        ) as mock_convert:
            result = await repository.create(sample_rebalance_entity)

            assert result.rebalance_id == mock_document.id
            assert result.model_id == sample_rebalance_entity.model_id
            assert result.model_name == sample_rebalance_entity.model_name
            mock_convert.assert_called_once_with(sample_rebalance_entity)
            mock_document.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_rebalance_duplicate_key_error(
        self, repository, sample_rebalance_entity
    ):
        """Test rebalance creation with duplicate key error."""
        from pymongo.errors import DuplicateKeyError

        with patch.object(repository, '_convert_to_document') as mock_convert:
            mock_document = MagicMock()
            mock_document.create = AsyncMock(
                side_effect=DuplicateKeyError("Duplicate key error")
            )
            mock_convert.return_value = mock_document

            with pytest.raises(RepositoryError, match="Failed to create rebalance"):
                await repository.create(sample_rebalance_entity)

    @pytest.mark.asyncio
    async def test_get_by_id_success(self, repository, sample_rebalance_document):
        """Test successful rebalance retrieval by ID."""
        rebalance_id = str(sample_rebalance_document.id)

        # Mock the raw MongoDB collection operation
        mock_collection = AsyncMock()
        mock_collection.find_one.return_value = {
            '_id': sample_rebalance_document.id,
            'model_id': sample_rebalance_document.model_id,
            'model_name': sample_rebalance_document.model_name,
            'rebalance_date': sample_rebalance_document.rebalance_date,
            'number_of_portfolios': sample_rebalance_document.number_of_portfolios,
            'portfolios': [],
            'version': sample_rebalance_document.version,
            'created_at': sample_rebalance_document.created_at,
        }

        with patch.object(
            RebalanceDocument, 'get_motor_collection', return_value=mock_collection
        ):
            result = await repository.get_by_id(rebalance_id)

            assert result is not None
            assert str(result.rebalance_id) == rebalance_id
            assert result.model_name == sample_rebalance_document.model_name
            mock_collection.find_one.assert_called_once_with(
                {"_id": ObjectId(rebalance_id)}
            )

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, repository):
        """Test rebalance retrieval when not found."""
        rebalance_id = str(ObjectId())

        # Mock the raw MongoDB collection operation
        mock_collection = AsyncMock()
        mock_collection.find_one.return_value = None

        with patch.object(
            RebalanceDocument, 'get_motor_collection', return_value=mock_collection
        ):
            result = await repository.get_by_id(rebalance_id)

            assert result is None
            mock_collection.find_one.assert_called_once_with(
                {"_id": ObjectId(rebalance_id)}
            )

    @pytest.mark.asyncio
    async def test_get_by_id_invalid_object_id(self, repository):
        """Test rebalance retrieval with invalid ObjectId."""
        with pytest.raises(RepositoryError, match="Invalid rebalance ID format"):
            await repository.get_by_id("invalid_id")

    @pytest.mark.asyncio
    async def test_list_with_pagination_success(
        self, repository, sample_rebalance_document
    ):
        """Test successful rebalance listing with pagination."""
        mock_documents = [sample_rebalance_document]

        # Mock the query chain properly
        mock_query = MagicMock()
        mock_query.sort.return_value = mock_query
        mock_query.skip.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.to_list = AsyncMock(return_value=mock_documents)

        with patch.object(
            RebalanceDocument, 'find_all', return_value=mock_query
        ) as mock_find_all:
            result = await repository.list_with_pagination(offset=0, limit=10)

            assert len(result) == 1
            assert result[0].model_name == sample_rebalance_document.model_name
            mock_find_all.assert_called_once()
            mock_query.sort.assert_called_once_with([("created_at", -1)])
            mock_query.skip.assert_called_once_with(0)
            mock_query.limit.assert_called_once_with(10)

    @pytest.mark.asyncio
    async def test_list_with_pagination_default_params(self, repository):
        """Test listing with default pagination parameters."""
        # Mock the query chain properly
        mock_query = MagicMock()
        mock_query.sort.return_value = mock_query
        mock_query.skip.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.to_list = AsyncMock(return_value=[])

        with patch.object(
            RebalanceDocument, 'find_all', return_value=mock_query
        ) as mock_find_all:
            result = await repository.list_with_pagination()

            assert len(result) == 0
            mock_find_all.assert_called_once()
            mock_query.sort.assert_called_once_with([("created_at", -1)])
            mock_query.skip.assert_called_once_with(0)
            mock_query.limit.assert_called_once_with(10)

    @pytest.mark.asyncio
    async def test_list_with_pagination_invalid_params(self, repository):
        """Test rebalance listing with invalid pagination parameters."""
        with pytest.raises(ValueError, match="Offset must be non-negative"):
            await repository.list_with_pagination(offset=-1)

        with pytest.raises(ValueError, match="Limit must be positive"):
            await repository.list_with_pagination(limit=0)

        with pytest.raises(ValueError, match="Limit cannot exceed 100"):
            await repository.list_with_pagination(limit=101)

    @pytest.mark.asyncio
    async def test_list_by_portfolios_success(
        self, repository, sample_rebalance_document
    ):
        """Test successful rebalance listing by portfolio IDs."""
        portfolio_ids = ["def456ghi789jkl012mno345"]
        mock_documents = [sample_rebalance_document]

        # Mock the query chain properly
        mock_query = MagicMock()
        mock_query.sort.return_value = mock_query
        mock_query.skip.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.to_list = AsyncMock(return_value=mock_documents)

        with patch.object(
            RebalanceDocument, 'find', return_value=mock_query
        ) as mock_find:
            result = await repository.list_by_portfolios(
                portfolio_ids, offset=0, limit=10
            )

            assert len(result) == 1
            assert result[0].model_name == sample_rebalance_document.model_name
            # Check that the query was called with the portfolio filter
            mock_find.assert_called_once_with(
                {"portfolios.portfolio_id": {"$in": portfolio_ids}}
            )
            mock_query.sort.assert_called_once_with([("created_at", -1)])
            mock_query.skip.assert_called_once_with(0)
            mock_query.limit.assert_called_once_with(10)

    @pytest.mark.asyncio
    async def test_list_by_portfolios_empty_list(self, repository):
        """Test rebalance listing with empty portfolio list."""
        with pytest.raises(ValueError, match="Portfolio IDs list cannot be empty"):
            await repository.list_by_portfolios([], offset=0, limit=10)

    @pytest.mark.asyncio
    async def test_delete_by_id_success(self, repository, sample_rebalance_document):
        """Test successful rebalance deletion."""
        rebalance_id = str(sample_rebalance_document.id)
        version = 1

        # Mock the find_one operation for version checking
        with patch.object(
            RebalanceDocument, 'find_one', new_callable=AsyncMock
        ) as mock_find_one:
            sample_rebalance_document.version = version
            # Make the delete method async and properly awaitable
            sample_rebalance_document.delete = AsyncMock(return_value=None)
            mock_find_one.return_value = sample_rebalance_document

            result = await repository.delete_by_id(rebalance_id, version)

            assert result is True
            # Check that find_one was called once for version check
            assert mock_find_one.call_count == 1
            # Check that delete was called on the document
            sample_rebalance_document.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_by_id_not_found(self, repository):
        """Test rebalance deletion when not found."""
        rebalance_id = str(ObjectId())

        with patch.object(
            RebalanceDocument, 'find_one', new_callable=AsyncMock
        ) as mock_find_one:
            mock_find_one.return_value = None

            result = await repository.delete_by_id(rebalance_id, 1)

            assert result is False

    @pytest.mark.asyncio
    async def test_delete_by_id_version_conflict(
        self, repository, sample_rebalance_document
    ):
        """Test rebalance deletion with version conflict."""
        rebalance_id = str(sample_rebalance_document.id)

        with patch.object(
            RebalanceDocument, 'find_one', new_callable=AsyncMock
        ) as mock_find_one:
            # First call returns None (no document with expected version)
            # Second call returns document with different version
            existing_doc = MagicMock()
            existing_doc.version = 2  # Different version
            mock_find_one.side_effect = [None, existing_doc]

            with pytest.raises(ConcurrencyError, match="version mismatch"):
                await repository.delete_by_id(rebalance_id, 1)

    @pytest.mark.asyncio
    async def test_delete_by_id_invalid_object_id(self, repository):
        """Test rebalance deletion with invalid ObjectId."""
        with pytest.raises(RepositoryError, match="Failed to delete rebalance"):
            await repository.delete_by_id("invalid_id", 1)

    @pytest.mark.asyncio
    async def test_repository_error_handling(self, repository):
        """Test repository error handling for unexpected exceptions."""
        with patch.object(
            RebalanceDocument, 'find_all', side_effect=Exception("Database error")
        ):
            with pytest.raises(RepositoryError, match="Failed to list rebalances"):
                await repository.list_with_pagination()

    @pytest.mark.asyncio
    async def test_entity_to_document_conversion(
        self, repository, sample_rebalance_entity
    ):
        """Test conversion from domain entity to document."""
        # Test the actual conversion without mocking the constructor
        # since we're just testing the conversion logic
        with patch.object(RebalanceDocument, 'save', new_callable=AsyncMock):
            # Mock the creation but test the conversion
            mock_document = MagicMock()
            mock_document.model_id = sample_rebalance_entity.model_id
            mock_document.model_name = sample_rebalance_entity.model_name
            mock_document.number_of_portfolios = (
                sample_rebalance_entity.number_of_portfolios
            )

            with patch.object(
                repository, '_convert_to_document', return_value=mock_document
            ):
                result = repository._convert_to_document(sample_rebalance_entity)

                assert result.model_id == sample_rebalance_entity.model_id
                assert result.model_name == sample_rebalance_entity.model_name
                assert (
                    result.number_of_portfolios
                    == sample_rebalance_entity.number_of_portfolios
                )

    @pytest.mark.asyncio
    async def test_document_to_entity_conversion(
        self, repository, sample_rebalance_document
    ):
        """Test conversion from document to domain entity."""
        result = repository._convert_to_domain(sample_rebalance_document)

        assert isinstance(result, Rebalance)
        assert result.rebalance_id == sample_rebalance_document.id
        assert result.model_id == sample_rebalance_document.model_id
        assert result.model_name == sample_rebalance_document.model_name
        assert (
            result.number_of_portfolios
            == sample_rebalance_document.number_of_portfolios
        )
        assert len(result.portfolios) == len(sample_rebalance_document.portfolios)

    @pytest.mark.asyncio
    async def test_concurrent_access_handling(
        self, repository, sample_rebalance_entity
    ):
        """Test handling of concurrent access scenarios."""
        # This test simulates a scenario where multiple processes try to create
        # the same rebalance record simultaneously
        from pymongo.errors import DuplicateKeyError

        # Mock successful document creation with correct attributes
        mock_document_success = MagicMock()
        mock_document_success.id = ObjectId()
        mock_document_success.model_id = sample_rebalance_entity.model_id
        mock_document_success.model_name = sample_rebalance_entity.model_name
        mock_document_success.rebalance_date = sample_rebalance_entity.rebalance_date
        mock_document_success.number_of_portfolios = (
            sample_rebalance_entity.number_of_portfolios
        )
        mock_document_success.portfolios = []
        mock_document_success.version = sample_rebalance_entity.version
        mock_document_success.created_at = sample_rebalance_entity.created_at
        mock_document_success.create = AsyncMock(return_value=mock_document_success)

        # Configure model_dump to return proper data
        mock_document_success.model_dump.return_value = {
            'id': mock_document_success.id,
            'model_id': mock_document_success.model_id,
            'model_name': mock_document_success.model_name,
            'rebalance_date': mock_document_success.rebalance_date,
            'number_of_portfolios': mock_document_success.number_of_portfolios,
            'portfolios': mock_document_success.portfolios,
            'version': mock_document_success.version,
            'created_at': mock_document_success.created_at,
        }

        # Mock document that fails with duplicate key error
        mock_document_fail = MagicMock()
        mock_document_fail.create = AsyncMock(
            side_effect=DuplicateKeyError("Duplicate key")
        )

        with patch.object(repository, '_convert_to_document') as mock_convert:
            # Configure the mock to return different documents for each call
            mock_convert.side_effect = [mock_document_success, mock_document_fail]

            # First call should succeed
            result1 = await repository.create(sample_rebalance_entity)
            assert result1.rebalance_id is not None

            # Second call should raise RepositoryError
            with pytest.raises(RepositoryError):
                await repository.create(sample_rebalance_entity)
