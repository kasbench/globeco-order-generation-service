"""
MongoDB implementation of the Rebalance Repository using Beanie ODM.

This module provides the concrete implementation of the RebalanceRepository interface
for MongoDB persistence, using Beanie ODM for document operations.
"""

import logging
from typing import List, Optional

from beanie.exceptions import DocumentNotFound
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from src.core.exceptions import (
    ConcurrencyError,
    NotFoundError,
    RepositoryError,
)
from src.domain.entities.rebalance import (
    Rebalance,
    RebalancePortfolio,
    RebalancePosition,
)
from src.domain.repositories.rebalance_repository import RebalanceRepository
from src.models.rebalance import PortfolioEmbedded, PositionEmbedded, RebalanceDocument

logger = logging.getLogger(__name__)


class MongoRebalanceRepository(RebalanceRepository):
    """MongoDB implementation of the Rebalance Repository using Beanie ODM."""

    async def create(self, rebalance: Rebalance) -> Rebalance:
        """
        Create a new rebalance record in MongoDB.

        Args:
            rebalance: The rebalance to create

        Returns:
            Rebalance: The created rebalance with updated metadata

        Raises:
            RepositoryError: If creation fails
        """
        try:
            # Convert domain model to document
            document = self._convert_to_document(rebalance)

            # Save to database
            saved_document = await document.create()

            logger.info(
                f"Created rebalance for model '{rebalance.model_name}' with ID {saved_document.id}"
            )

            # Convert back to domain model
            return self._convert_to_domain(saved_document)

        except Exception as e:
            error_msg = f"Failed to create rebalance for model '{rebalance.model_name}': {str(e)}"
            logger.error(error_msg)
            raise RepositoryError(error_msg, operation="create") from e

    async def get_by_id(self, rebalance_id: str) -> Optional[Rebalance]:
        """
        Retrieve a rebalance by its ID.

        Args:
            rebalance_id: The rebalance ID to search for

        Returns:
            Optional[Rebalance]: The rebalance if found, None otherwise

        Raises:
            RepositoryError: If retrieval fails due to invalid ID format
        """
        try:
            # Convert string ID to ObjectId
            object_id = ObjectId(rebalance_id)

            # Find document by ID
            document = await RebalanceDocument.get(object_id)

            if document is None:
                return None

            # Convert to domain model
            return self._convert_to_domain(document)

        except (ValueError, TypeError) as e:
            error_msg = f"Invalid rebalance ID format: {rebalance_id}"
            logger.error(error_msg)
            raise RepositoryError(error_msg, operation="get") from e
        except Exception as e:
            error_msg = f"Failed to retrieve rebalance by ID {rebalance_id}: {str(e)}"
            logger.error(error_msg)
            raise RepositoryError(error_msg, operation="get") from e

    async def list_all(self) -> List[Rebalance]:
        """
        Retrieve all rebalances.

        Returns:
            List[Rebalance]: All rebalances in the repository

        Raises:
            RepositoryError: If retrieval fails
        """
        try:
            # Find all documents, sorted by creation date (newest first)
            documents = (
                await RebalanceDocument.find_all().sort([("created_at", -1)]).to_list()
            )

            # Convert to domain models
            return [self._convert_to_domain(doc) for doc in documents]

        except Exception as e:
            error_msg = f"Failed to retrieve all rebalances: {str(e)}"
            logger.error(error_msg)
            raise RepositoryError(error_msg, operation="list_all") from e

    async def list_with_pagination(
        self,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[Rebalance]:
        """
        Retrieve rebalances with pagination.

        Args:
            offset: Number of rebalances to skip (default: 0)
            limit: Maximum number of rebalances to return (default: 10, max: 100)

        Returns:
            List[Rebalance]: Paginated list of rebalances

        Raises:
            RepositoryError: If retrieval fails
            ValueError: If pagination parameters are invalid
        """
        try:
            # Validate and set defaults for pagination parameters
            offset = offset if offset is not None else 0
            limit = limit if limit is not None else 10

            # Validate pagination parameters
            if offset < 0:
                raise ValueError("Offset must be non-negative")
            if limit <= 0:
                raise ValueError("Limit must be positive")
            if limit > 100:
                raise ValueError("Limit cannot exceed 100")

            # Build query with pagination
            query = RebalanceDocument.find_all()

            # Sort by creation date (newest first)
            query = query.sort([("created_at", -1)])

            # Apply pagination
            query = query.skip(offset).limit(limit)

            # Execute query
            documents = await query.to_list()

            # Convert to domain models
            return [self._convert_to_domain(doc) for doc in documents]

        except ValueError:
            raise  # Re-raise validation errors
        except Exception as e:
            error_msg = f"Failed to list rebalances with pagination: {str(e)}"
            logger.error(error_msg)
            raise RepositoryError(error_msg, operation="list_with_pagination") from e

    async def list_by_portfolios(
        self,
        portfolio_ids: List[str],
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[Rebalance]:
        """
        Retrieve rebalances for specific portfolios with pagination.

        Args:
            portfolio_ids: List of portfolio IDs to filter by
            offset: Number of rebalances to skip (default: 0)
            limit: Maximum number of rebalances to return (default: 10, max: 100)

        Returns:
            List[Rebalance]: Filtered and paginated list of rebalances

        Raises:
            RepositoryError: If retrieval fails
            ValueError: If parameters are invalid
        """
        try:
            # Validate parameters
            if not portfolio_ids:
                raise ValueError("Portfolio IDs list cannot be empty")

            # Validate and set defaults for pagination parameters
            offset = offset if offset is not None else 0
            limit = limit if limit is not None else 10

            if offset < 0:
                raise ValueError("Offset must be non-negative")
            if limit <= 0:
                raise ValueError("Limit must be positive")
            if limit > 100:
                raise ValueError("Limit cannot exceed 100")

            # Build query to find rebalances containing any of the specified portfolios
            query = RebalanceDocument.find(
                {"portfolios.portfolio_id": {"$in": portfolio_ids}}
            )

            # Sort by creation date (newest first)
            query = query.sort([("created_at", -1)])

            # Apply pagination
            query = query.skip(offset).limit(limit)

            # Execute query
            documents = await query.to_list()

            # Convert to domain models
            return [self._convert_to_domain(doc) for doc in documents]

        except ValueError:
            raise  # Re-raise validation errors
        except Exception as e:
            error_msg = f"Failed to list rebalances by portfolios: {str(e)}"
            logger.error(error_msg)
            raise RepositoryError(error_msg, operation="list_by_portfolios") from e

    async def delete_by_id(self, rebalance_id: str, version: int) -> bool:
        """
        Delete a rebalance by its ID with optimistic locking.

        Args:
            rebalance_id: The rebalance ID to delete
            version: Expected version for optimistic locking

        Returns:
            bool: True if deleted, False if not found

        Raises:
            RepositoryError: If deletion fails
            ConcurrencyError: If version mismatch occurs
            ValueError: If ID format is invalid
        """
        try:
            # Convert string ID to ObjectId
            object_id = ObjectId(rebalance_id)

            # Find document with specific version for optimistic locking
            document = await RebalanceDocument.find_one(
                {"_id": object_id, "version": version}
            )

            if document is None:
                # Check if document exists with different version
                existing = await RebalanceDocument.find_one({"_id": object_id})
                if existing is not None:
                    raise ConcurrencyError(
                        f"Rebalance version mismatch: expected {version}, got {existing.version}"
                    )
                return False

            # Delete the document
            await document.delete()

            logger.info(f"Deleted rebalance {rebalance_id} with version {version}")
            return True

        except ConcurrencyError:
            raise  # Re-raise concurrency errors
        except (ValueError, TypeError) as e:
            error_msg = f"Invalid rebalance ID format: {rebalance_id}"
            logger.error(error_msg)
            raise RepositoryError(error_msg, operation="delete") from e
        except Exception as e:
            error_msg = f"Failed to delete rebalance {rebalance_id}: {str(e)}"
            logger.error(error_msg)
            raise RepositoryError(error_msg, operation="delete") from e

    async def count_all(self) -> int:
        """
        Get the total number of rebalances.

        Returns:
            Total count of rebalances

        Raises:
            RepositoryError: If count operation fails
        """
        try:
            return await RebalanceDocument.count()
        except Exception as e:
            error_msg = f"Failed to count rebalances: {str(e)}"
            logger.error(error_msg)
            raise RepositoryError(error_msg, operation="count_all") from e

    async def exists_by_id(self, rebalance_id: str) -> bool:
        """
        Check if a rebalance exists by its ID.

        Args:
            rebalance_id: The rebalance ID to check

        Returns:
            bool: True if rebalance exists, False otherwise

        Raises:
            RepositoryError: If check operation fails
        """
        try:
            # Validate ObjectId format
            if not ObjectId.is_valid(rebalance_id):
                raise ValueError(f"Invalid ObjectId format: {rebalance_id}")

            # Check if document exists
            doc = await RebalanceDocument.find_one({"_id": ObjectId(rebalance_id)})
            exists = doc is not None

            logger.debug(f"Checked existence for rebalance {rebalance_id}: {exists}")
            return exists

        except Exception as e:
            logger.error(f"Error checking rebalance existence {rebalance_id}: {e}")
            raise RepositoryError(
                f"Failed to check rebalance existence: {e}", operation="exists_by_id"
            )

    def _convert_to_document(self, rebalance: Rebalance) -> RebalanceDocument:
        """Convert domain Rebalance to RebalanceDocument."""
        portfolios_embedded = []
        for portfolio in rebalance.portfolios:
            positions_embedded = []
            for position in portfolio.positions:
                position_embedded = PositionEmbedded(
                    security_id=position.security_id,
                    price=position.price,
                    original_quantity=position.original_quantity,
                    adjusted_quantity=position.adjusted_quantity,
                    original_position_market_value=position.original_position_market_value,
                    adjusted_position_market_value=position.adjusted_position_market_value,
                    target=position.target,
                    high_drift=position.high_drift,
                    low_drift=position.low_drift,
                    actual=position.actual,
                    actual_drift=position.actual_drift,
                    transaction_type=position.transaction_type,
                    trade_quantity=position.trade_quantity,
                    trade_date=position.trade_date,
                )
                positions_embedded.append(position_embedded)

            portfolio_embedded = PortfolioEmbedded(
                portfolio_id=portfolio.portfolio_id,
                market_value=portfolio.market_value,
                cash_before_rebalance=portfolio.cash_before_rebalance,
                cash_after_rebalance=portfolio.cash_after_rebalance,
                positions=positions_embedded,
            )
            portfolios_embedded.append(portfolio_embedded)

        return RebalanceDocument(
            id=rebalance.rebalance_id,
            model_id=rebalance.model_id,
            rebalance_date=rebalance.rebalance_date,
            model_name=rebalance.model_name,
            number_of_portfolios=rebalance.number_of_portfolios,
            portfolios=portfolios_embedded,
            version=rebalance.version,
            created_at=rebalance.created_at,
        )

    def _convert_to_domain(self, document: RebalanceDocument) -> Rebalance:
        """Convert RebalanceDocument to domain Rebalance."""
        portfolios = []
        for portfolio_doc in document.portfolios:
            positions = []
            for position_doc in portfolio_doc.positions:
                position = RebalancePosition(
                    security_id=position_doc.security_id,
                    price=position_doc.price,
                    original_quantity=position_doc.original_quantity,
                    adjusted_quantity=position_doc.adjusted_quantity,
                    original_position_market_value=position_doc.original_position_market_value,
                    adjusted_position_market_value=position_doc.adjusted_position_market_value,
                    target=position_doc.target,
                    high_drift=position_doc.high_drift,
                    low_drift=position_doc.low_drift,
                    actual=position_doc.actual,
                    actual_drift=position_doc.actual_drift,
                    transaction_type=position_doc.transaction_type,
                    trade_quantity=position_doc.trade_quantity,
                    trade_date=position_doc.trade_date,
                )
                positions.append(position)

            portfolio = RebalancePortfolio(
                portfolio_id=portfolio_doc.portfolio_id,
                market_value=portfolio_doc.market_value,
                cash_before_rebalance=portfolio_doc.cash_before_rebalance,
                cash_after_rebalance=portfolio_doc.cash_after_rebalance,
                positions=positions,
            )
            portfolios.append(portfolio)

        return Rebalance(
            rebalance_id=document.id,
            model_id=document.model_id,
            rebalance_date=document.rebalance_date,
            model_name=document.model_name,
            number_of_portfolios=document.number_of_portfolios,
            portfolios=portfolios,
            version=document.version,
            created_at=document.created_at,
        )
