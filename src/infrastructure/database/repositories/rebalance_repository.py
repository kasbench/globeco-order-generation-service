"""
MongoDB implementation of the Rebalance Repository using Beanie ODM.

This module provides the concrete implementation of the RebalanceRepository interface
for MongoDB persistence, using Beanie ODM for document operations.
"""

import logging
from decimal import Decimal
from typing import List, Optional

from beanie.exceptions import CollectionWasNotInitialized, DocumentNotFound
from bson import Decimal128, ObjectId
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

    def _convert_decimal128_to_decimal(self, value):
        """Convert Decimal128 to Python Decimal, or return value if already correct type."""
        if isinstance(value, Decimal128):
            return Decimal(str(value))
        return value

    def _convert_decimal128_recursively(self, obj):
        """Recursively convert all Decimal128 values to Decimal in a data structure."""
        logger.debug(
            f"_convert_decimal128_recursively(): *** ENTRY POINT *** Processing object of type {type(obj)}"
        )

        # If this is the top-level call, log some diagnostic info
        if hasattr(obj, 'portfolios'):
            logger.debug(
                f"_convert_decimal128_recursively(): Top-level document with {len(obj.portfolios)} portfolios"
            )

        if isinstance(obj, Decimal128):
            logger.debug(
                f"_convert_decimal128_recursively(): Converting Decimal128({obj}) to Decimal"
            )
            return Decimal(str(obj))
        elif isinstance(obj, dict):
            logger.debug(
                f"_convert_decimal128_recursively(): Processing dict with {len(obj)} keys"
            )
            return {
                key: self._convert_decimal128_recursively(value)
                for key, value in obj.items()
            }
        elif isinstance(obj, list):
            logger.debug(
                f"_convert_decimal128_recursively(): Processing list with {len(obj)} items"
            )
            return [self._convert_decimal128_recursively(item) for item in obj]
        elif hasattr(obj, '__dict__'):
            # Handle Beanie document objects and other objects with attributes
            logger.debug(
                f"_convert_decimal128_recursively(): Processing object with __dict__, attributes: {list(obj.__dict__.keys())}"
            )
            for attr_name, attr_value in obj.__dict__.items():
                logger.debug(
                    f"_convert_decimal128_recursively(): Processing attribute {attr_name} of type {type(attr_value)}"
                )
                if isinstance(attr_value, Decimal128):
                    logger.debug(
                        f"_convert_decimal128_recursively(): Converting Decimal128 attribute {attr_name}"
                    )
                    setattr(obj, attr_name, Decimal(str(attr_value)))
                elif isinstance(attr_value, (list, dict)) or hasattr(
                    attr_value, '__dict__'
                ):
                    logger.debug(
                        f"_convert_decimal128_recursively(): Recursing into attribute {attr_name}"
                    )
                    setattr(
                        obj, attr_name, self._convert_decimal128_recursively(attr_value)
                    )
            return obj
        else:
            # Handle objects that might have attributes but no __dict__ (like some Beanie embedded docs)
            logger.debug(
                f"_convert_decimal128_recursively(): Checking for attributes on {type(obj)}"
            )
            try:
                # Try to get all attributes using dir() and process them
                for attr_name in dir(obj):
                    if not attr_name.startswith('_') and not callable(
                        getattr(obj, attr_name, None)
                    ):
                        try:
                            attr_value = getattr(obj, attr_name)
                            logger.debug(
                                f"_convert_decimal128_recursively(): Found attribute {attr_name} = {type(attr_value)}"
                            )
                            if isinstance(attr_value, Decimal128):
                                logger.debug(
                                    f"_convert_decimal128_recursively(): Converting Decimal128 attribute {attr_name} on {type(obj)}"
                                )
                                setattr(obj, attr_name, Decimal(str(attr_value)))
                            elif (
                                isinstance(attr_value, (list, dict))
                                or hasattr(attr_value, '__dict__')
                                or (
                                    hasattr(attr_value, '__class__')
                                    and 'Embedded' in str(attr_value.__class__)
                                )
                            ):
                                logger.debug(
                                    f"_convert_decimal128_recursively(): Recursing into attribute {attr_name} on {type(obj)}"
                                )
                                setattr(
                                    obj,
                                    attr_name,
                                    self._convert_decimal128_recursively(attr_value),
                                )
                        except (AttributeError, TypeError):
                            # Skip attributes that can't be accessed or set
                            continue
            except Exception as e:
                logger.debug(
                    f"_convert_decimal128_recursively(): Could not process attributes for {type(obj)}: {e}"
                )
            return obj

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
            logger.debug(
                f"*** REPOSITORY GET_BY_ID ENTRY POINT *** rebalance_id={rebalance_id}"
            )
            logger.debug(
                f"Repository.get_by_id(): Starting retrieval for rebalance_id={rebalance_id}"
            )

            # Validate ObjectId format
            if not ObjectId.is_valid(rebalance_id):
                logger.error(
                    f"Repository.get_by_id(): Invalid ObjectId format: {rebalance_id}"
                )
                raise ValueError(f"Invalid ObjectId format: {rebalance_id}")

            logger.debug(
                f"Repository.get_by_id(): ObjectId validation passed for {rebalance_id}"
            )

            # Convert string ID to ObjectId
            object_id = ObjectId(rebalance_id)
            logger.debug(f"Repository.get_by_id(): Created ObjectId: {object_id}")

            # Find document by ID using raw MongoDB query to avoid Pydantic validation
            logger.debug(
                f"Repository.get_by_id(): Querying database for raw document..."
            )
            collection = RebalanceDocument.get_motor_collection()
            raw_document = await collection.find_one({"_id": object_id})
            logger.debug(
                f"Repository.get_by_id(): Raw database query completed, found document: {raw_document is not None}"
            )

            if raw_document is None:
                logger.info(
                    f"Repository.get_by_id(): No document found for rebalance_id={rebalance_id}"
                )
                return None

            # Convert Decimal128 values in raw document
            logger.debug(
                f"Repository.get_by_id(): Converting Decimal128 values in raw document..."
            )
            converted_doc = self._convert_decimal128_recursively(raw_document)
            logger.debug(f"Repository.get_by_id(): Decimal128 conversion completed")

            # Convert to domain model directly from dictionary
            logger.debug(
                f"Repository.get_by_id(): Converting raw document to domain object..."
            )
            domain_obj = self._convert_raw_to_domain(converted_doc)
            logger.debug(
                f"Repository.get_by_id(): Successfully converted to domain object"
            )
            return domain_obj

        except (ValueError, TypeError) as e:
            error_msg = f"Invalid rebalance ID format: {rebalance_id}"
            logger.error(f"{error_msg}. Original error: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Detailed traceback:", exc_info=True)
            raise RepositoryError(error_msg, operation="get") from e
        except CollectionWasNotInitialized as e:
            error_msg = f"Database not initialized - please ensure Beanie ODM is properly configured"
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
        except CollectionWasNotInitialized as e:
            error_msg = f"Database not initialized - please ensure Beanie ODM is properly configured"
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

    def _convert_raw_to_domain(self, doc_dict: dict) -> Rebalance:
        """Convert raw MongoDB document dictionary to domain Rebalance."""
        try:
            logger.debug(
                f"_convert_raw_to_domain(): Starting conversion from raw document"
            )
            logger.debug(
                f"_convert_raw_to_domain(): Document keys: {list(doc_dict.keys())}"
            )

            # Check a sample to verify Decimal128 conversion
            if 'portfolios' in doc_dict and len(doc_dict['portfolios']) > 0:
                sample_portfolio = doc_dict['portfolios'][0]
                if (
                    'positions' in sample_portfolio
                    and len(sample_portfolio['positions']) > 0
                ):
                    sample_position = sample_portfolio['positions'][0]
                    if 'target' in sample_position:
                        logger.debug(
                            f"_convert_raw_to_domain(): Sample position target type: {type(sample_position['target'])}"
                        )

            logger.debug(
                f"_convert_raw_to_domain(): Processing {len(doc_dict['portfolios'])} portfolios..."
            )
            portfolios = []
            for i, portfolio_dict in enumerate(doc_dict['portfolios']):
                logger.debug(
                    f"_convert_raw_to_domain(): Processing portfolio {i+1}/{len(doc_dict['portfolios'])}"
                )
                positions = []
                for j, position_dict in enumerate(portfolio_dict['positions']):
                    logger.debug(
                        f"_convert_raw_to_domain(): Processing position {j+1}/{len(portfolio_dict['positions'])} in portfolio {i+1}"
                    )
                    try:
                        position = RebalancePosition(
                            security_id=position_dict['security_id'],
                            price=position_dict['price'],
                            original_quantity=position_dict['original_quantity'],
                            adjusted_quantity=position_dict['adjusted_quantity'],
                            original_position_market_value=position_dict[
                                'original_position_market_value'
                            ],
                            adjusted_position_market_value=position_dict[
                                'adjusted_position_market_value'
                            ],
                            target=position_dict['target'],
                            high_drift=position_dict['high_drift'],
                            low_drift=position_dict['low_drift'],
                            actual=position_dict['actual'],
                            actual_drift=position_dict['actual_drift'],
                            transaction_type=position_dict['transaction_type'],
                            trade_quantity=position_dict['trade_quantity'],
                            trade_date=position_dict['trade_date'],
                        )
                        positions.append(position)
                        logger.debug(
                            f"_convert_raw_to_domain(): Successfully created position {j+1}"
                        )
                    except Exception as e:
                        logger.error(
                            f"_convert_raw_to_domain(): Error creating position {j+1} in portfolio {i+1}: {str(e)}"
                        )
                        logger.error(
                            f"_convert_raw_to_domain(): Position data types: security_id={type(position_dict['security_id'])}, price={type(position_dict['price'])}, target={type(position_dict['target'])}"
                        )
                        raise

                try:
                    portfolio = RebalancePortfolio(
                        portfolio_id=portfolio_dict['portfolio_id'],
                        market_value=portfolio_dict['market_value'],
                        cash_before_rebalance=portfolio_dict['cash_before_rebalance'],
                        cash_after_rebalance=portfolio_dict['cash_after_rebalance'],
                        positions=positions,
                    )
                    portfolios.append(portfolio)
                    logger.debug(
                        f"_convert_raw_to_domain(): Successfully created portfolio {i+1}"
                    )
                except Exception as e:
                    logger.error(
                        f"_convert_raw_to_domain(): Error creating portfolio {i+1}: {str(e)}"
                    )
                    logger.error(
                        f"_convert_raw_to_domain(): Portfolio data types: portfolio_id={type(portfolio_dict['portfolio_id'])}, market_value={type(portfolio_dict['market_value'])}"
                    )
                    raise

            logger.debug(
                f"_convert_raw_to_domain(): Creating final Rebalance object..."
            )
            rebalance = Rebalance(
                rebalance_id=doc_dict['_id'],
                model_id=doc_dict['model_id'],
                rebalance_date=doc_dict['rebalance_date'],
                model_name=doc_dict['model_name'],
                number_of_portfolios=doc_dict['number_of_portfolios'],
                portfolios=portfolios,
                version=doc_dict['version'],
                created_at=doc_dict['created_at'],
            )
            logger.debug(
                f"_convert_raw_to_domain(): Successfully created Rebalance object"
            )
            return rebalance

        except Exception as e:
            logger.error(
                f"_convert_raw_to_domain(): Failed to convert raw document to domain object: {str(e)}"
            )
            logger.error(f"_convert_raw_to_domain(): Error type: {type(e).__name__}")
            raise

    def _convert_to_domain(self, document: RebalanceDocument) -> Rebalance:
        """Convert RebalanceDocument to domain Rebalance."""
        try:
            logger.debug(
                f"_convert_to_domain(): *** ENTRY POINT *** Starting conversion"
            )
            logger.debug(f"_convert_to_domain(): Document type: {type(document)}")
            logger.debug(f"_convert_to_domain(): Trying to access document.id...")

            try:
                doc_id = document.id
                logger.debug(
                    f"_convert_to_domain(): Successfully accessed document.id: {doc_id}"
                )
            except Exception as e:
                logger.error(
                    f"_convert_to_domain(): ERROR accessing document.id: {str(e)}"
                )
                raise

            logger.debug(
                f"_convert_to_domain(): Starting conversion for document id={document.id}"
            )

            # Convert document to dictionary first for easier processing
            logger.debug(f"_convert_to_domain(): Converting document to dictionary...")
            try:
                # Convert Beanie document to dict
                if hasattr(document, 'model_dump'):
                    doc_dict = document.model_dump()
                elif hasattr(document, 'dict'):
                    doc_dict = document.dict()
                else:
                    # Fallback - try to access as dict
                    doc_dict = dict(document)

                logger.debug(
                    f"_convert_to_domain(): Successfully converted to dict with keys: {list(doc_dict.keys())}"
                )

                # Now convert all Decimal128 values in the dictionary
                logger.debug(
                    f"_convert_to_domain(): Converting Decimal128 values in dictionary..."
                )
                doc_dict = self._convert_decimal128_recursively(doc_dict)
                logger.debug(f"_convert_to_domain(): Decimal128 conversion completed")

                # Check a sample after conversion
                if 'portfolios' in doc_dict and len(doc_dict['portfolios']) > 0:
                    sample_portfolio = doc_dict['portfolios'][0]
                    if (
                        'positions' in sample_portfolio
                        and len(sample_portfolio['positions']) > 0
                    ):
                        sample_position = sample_portfolio['positions'][0]
                        if 'target' in sample_position:
                            logger.debug(
                                f"_convert_to_domain(): Sample position target type after conversion: {type(sample_position['target'])}"
                            )

            except Exception as e:
                logger.error(
                    f"_convert_to_domain(): ERROR converting document to dict: {str(e)}"
                )
                logger.error(f"_convert_to_domain(): Error type: {type(e).__name__}")
                raise

            logger.debug(
                f"_convert_to_domain(): Processing {len(doc_dict['portfolios'])} portfolios..."
            )
            portfolios = []
            for i, portfolio_dict in enumerate(doc_dict['portfolios']):
                logger.debug(
                    f"_convert_to_domain(): Processing portfolio {i+1}/{len(doc_dict['portfolios'])}"
                )
                positions = []
                for j, position_dict in enumerate(portfolio_dict['positions']):
                    logger.debug(
                        f"_convert_to_domain(): Processing position {j+1}/{len(portfolio_dict['positions'])} in portfolio {i+1}"
                    )
                    try:
                        position = RebalancePosition(
                            security_id=position_dict['security_id'],
                            price=position_dict['price'],
                            original_quantity=position_dict['original_quantity'],
                            adjusted_quantity=position_dict['adjusted_quantity'],
                            original_position_market_value=position_dict[
                                'original_position_market_value'
                            ],
                            adjusted_position_market_value=position_dict[
                                'adjusted_position_market_value'
                            ],
                            target=position_dict['target'],
                            high_drift=position_dict['high_drift'],
                            low_drift=position_dict['low_drift'],
                            actual=position_dict['actual'],
                            actual_drift=position_dict['actual_drift'],
                            transaction_type=position_dict['transaction_type'],
                            trade_quantity=position_dict['trade_quantity'],
                            trade_date=position_dict['trade_date'],
                        )
                        positions.append(position)
                        logger.debug(
                            f"_convert_to_domain(): Successfully created position {j+1}"
                        )
                    except Exception as e:
                        logger.error(
                            f"_convert_to_domain(): Error creating position {j+1} in portfolio {i+1}: {str(e)}"
                        )
                        logger.error(
                            f"_convert_to_domain(): Position data types: security_id={type(position_dict['security_id'])}, price={type(position_dict['price'])}, target={type(position_dict['target'])}"
                        )
                        raise

                try:
                    portfolio = RebalancePortfolio(
                        portfolio_id=portfolio_dict['portfolio_id'],
                        market_value=portfolio_dict['market_value'],
                        cash_before_rebalance=portfolio_dict['cash_before_rebalance'],
                        cash_after_rebalance=portfolio_dict['cash_after_rebalance'],
                        positions=positions,
                    )
                    portfolios.append(portfolio)
                    logger.debug(
                        f"_convert_to_domain(): Successfully created portfolio {i+1}"
                    )
                except Exception as e:
                    logger.error(
                        f"_convert_to_domain(): Error creating portfolio {i+1}: {str(e)}"
                    )
                    logger.error(
                        f"_convert_to_domain(): Portfolio data types: portfolio_id={type(portfolio_dict['portfolio_id'])}, market_value={type(portfolio_dict['market_value'])}"
                    )
                    raise

            logger.debug(f"_convert_to_domain(): Creating final Rebalance object...")
            rebalance = Rebalance(
                rebalance_id=doc_dict['_id'],
                model_id=doc_dict['model_id'],
                rebalance_date=doc_dict['rebalance_date'],
                model_name=doc_dict['model_name'],
                number_of_portfolios=doc_dict['number_of_portfolios'],
                portfolios=portfolios,
                version=doc_dict['version'],
                created_at=doc_dict['created_at'],
            )
            logger.debug(f"_convert_to_domain(): Successfully created Rebalance object")
            return rebalance

        except Exception as e:
            logger.error(
                f"_convert_to_domain(): Failed to convert document to domain object: {str(e)}"
            )
            logger.error(f"_convert_to_domain(): Error type: {type(e).__name__}")
            logger.error(
                f"_convert_to_domain(): Document ID: {getattr(document, 'id', 'unknown')}"
            )
            raise
