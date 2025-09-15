"""
MongoDB implementation of the Model Repository using Beanie ODM.

This module provides the concrete implementation of the ModelRepository interface
for MongoDB persistence, using Beanie ODM for document operations.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from beanie.exceptions import CollectionWasNotInitialized, DocumentNotFound
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from src.core.exceptions import (
    ConcurrencyError,
    NotFoundError,
    RepositoryError,
)
from src.domain.entities.model import InvestmentModel
from src.domain.repositories.model_repository import ModelRepository
from src.models.model import ModelDocument

logger = logging.getLogger(__name__)


class MongoModelRepository(ModelRepository):
    """MongoDB implementation of the Model Repository using Beanie ODM."""

    async def create(self, model: InvestmentModel) -> InvestmentModel:
        """
        Create a new investment model in MongoDB.

        Args:
            model: The investment model to create

        Returns:
            InvestmentModel: The created model with updated metadata

        Raises:
            RepositoryError: If model name already exists or creation fails
        """
        try:
            # Convert domain model to document
            document = ModelDocument.from_domain_model(model)

            # Save to database
            saved_document = await document.create()

            logger.debug(
                f"Created investment model '{model.name}' with ID {saved_document.id}"
            )

            # Convert back to domain model
            return saved_document.to_domain_model()

        except DuplicateKeyError as e:
            error_msg = f"Model with name '{model.name}' already exists"
            logger.error(error_msg)
            raise RepositoryError(error_msg, operation="create") from e
        except Exception as e:
            error_msg = f"Failed to create model '{model.name}': {str(e)}"
            logger.error(error_msg)
            raise RepositoryError(error_msg, operation="create") from e

    async def get_by_id(self, model_id: str) -> Optional[InvestmentModel]:
        """
        Retrieve a model by its ID.

        Args:
            model_id: The model ID to search for

        Returns:
            Optional[InvestmentModel]: The model if found, None otherwise

        Raises:
            RepositoryError: If retrieval fails due to invalid ID format
        """
        try:
            logger.debug(
                f"ModelRepository.get_by_id(): Starting retrieval for model_id={model_id}"
            )

            # Validate ObjectId format
            if not ObjectId.is_valid(model_id):
                logger.error(
                    f"ModelRepository.get_by_id(): Invalid ObjectId format: {model_id}"
                )
                raise ValueError(f"Invalid ObjectId format: {model_id}")

            # Convert string ID to ObjectId
            object_id = ObjectId(model_id)
            logger.debug(f"ModelRepository.get_by_id(): Created ObjectId: {object_id}")

            # Try to find document by ID with fallback handling
            document = None
            try:
                document = await ModelDocument.get(object_id)
                logger.debug(
                    f"ModelRepository.get_by_id(): Standard Beanie method succeeded, found document: {document is not None}"
                )
            except (CollectionWasNotInitialized, AttributeError, RuntimeError) as e:
                # Check if database is still initializing before logging warning
                from src.infrastructure.database.database import db_manager

                if db_manager.is_initializing:
                    logger.debug(
                        f"ModelRepository.get_by_id(): Beanie ODM still initializing, trying direct MongoDB access"
                    )
                else:
                    logger.warning(
                        f"ModelRepository.get_by_id(): Beanie ODM not properly initialized, trying direct MongoDB access. Error: {str(e)}"
                    )

                # Try direct MongoDB access as fallback
                try:
                    from src.infrastructure.database.database import db_manager

                    if db_manager.database:
                        collection = db_manager.database[
                            "models"
                        ]  # Collection name from ModelDocument settings
                        raw_document = await collection.find_one({"_id": object_id})
                        if raw_document:
                            logger.debug(
                                f"ModelRepository.get_by_id(): Successfully retrieved document using direct MongoDB access"
                            )
                            # Convert raw document directly to domain model without creating ModelDocument
                            logger.debug(
                                f"ModelRepository.get_by_id(): Converting raw document to domain model..."
                            )
                            domain_model = self._convert_raw_to_domain_model(
                                raw_document
                            )
                            logger.debug(
                                f"ModelRepository.get_by_id(): Successfully converted raw document to domain model"
                            )
                            return domain_model
                        else:
                            logger.debug(
                                f"ModelRepository.get_by_id(): No document found for model_id={model_id}"
                            )
                            return None
                    else:
                        raise RuntimeError("Database not available")
                except Exception as direct_error:
                    logger.error(
                        f"ModelRepository.get_by_id(): Both standard and direct methods failed. Standard error: {str(e)}, Direct error: {str(direct_error)}"
                    )
                    error_msg = (
                        f"Database not properly initialized. This may indicate:\n"
                        f"1. Beanie ODM initialization failed during application startup\n"
                        f"2. Database connection was lost\n"
                        f"3. Race condition during application startup\n"
                        f"Standard method error: {str(e) or 'Unknown error'}\n"
                        f"Direct method error: {str(direct_error) or 'Unknown error'}"
                    )
                    raise RepositoryError(error_msg, operation="get") from direct_error

            if document is None:
                logger.debug(
                    f"ModelRepository.get_by_id(): No document found for model_id={model_id}"
                )
                return None

            # Convert to domain model
            logger.debug(f"ModelRepository.get_by_id(): Converting to domain model...")
            domain_model = document.to_domain_model()
            logger.debug(
                f"ModelRepository.get_by_id(): Successfully converted to domain model"
            )
            return domain_model

        except (ValueError, TypeError) as e:
            error_msg = f"Invalid model ID format: {model_id}"
            logger.error(f"{error_msg}. Original error: {str(e)}")
            raise RepositoryError(error_msg, operation="get") from e
        except Exception as e:
            error_msg = f"Failed to retrieve model by ID {model_id}: {str(e)}"
            logger.error(error_msg)
            raise RepositoryError(error_msg, operation="get") from e

    async def get_by_name(self, name: str) -> Optional[InvestmentModel]:
        """
        Retrieve a model by its name.

        Args:
            name: The model name to search for

        Returns:
            Optional[InvestmentModel]: The model if found, None otherwise
        """
        try:
            # Find document by name (uses unique index)
            document = await ModelDocument.find_one({"name": name})

            if document is None:
                return None

            # Convert to domain model
            return document.to_domain_model()

        except Exception as e:
            error_msg = f"Failed to retrieve model by name '{name}': {str(e)}"
            logger.error(error_msg)
            raise RepositoryError(error_msg, operation="get") from e

    async def update(self, model: InvestmentModel) -> InvestmentModel:
        """
        Update an existing model with optimistic locking.

        Args:
            model: The model with updated data

        Returns:
            InvestmentModel: The updated model with incremented version

        Raises:
            NotFoundError: If model doesn't exist
            ConcurrencyError: If model has been modified by another process
            RepositoryError: If update fails
        """
        try:
            # Find current document
            current_doc = await ModelDocument.get(model.model_id)

            if current_doc is None:
                error_msg = f"Model with ID {model.model_id} not found"
                raise NotFoundError(error_msg)

            # Check version for optimistic locking
            if current_doc.version != model.version:
                error_msg = (
                    f"Model {model.model_id} has been modified by another process. "
                    f"Expected version {model.version}, found {current_doc.version}"
                )
                raise ConcurrencyError(error_msg)

            # Update document from domain model
            current_doc.update_from_domain_model(model)
            current_doc.version += 1  # Increment version

            # Save changes
            await current_doc.save()

            logger.debug(
                f"Updated investment model '{model.name}' to version {current_doc.version}"
            )

            # Convert back to domain model
            return current_doc.to_domain_model()

        except (NotFoundError, ConcurrencyError):
            raise  # Re-raise domain exceptions
        except DuplicateKeyError as e:
            error_msg = f"Another model with name '{model.name}' already exists"
            logger.error(error_msg)
            raise RepositoryError(error_msg, operation="update") from e
        except Exception as e:
            error_msg = f"Failed to update model {model.model_id}: {str(e)}"
            logger.error(error_msg)
            raise RepositoryError(error_msg, operation="update") from e

    async def delete(self, model_id: str) -> bool:
        """
        Delete a model by its ID.

        Args:
            model_id: The ID of the model to delete

        Returns:
            bool: True if deleted successfully, False if not found

        Raises:
            RepositoryError: If deletion fails
        """
        try:
            # Convert string ID to ObjectId
            object_id = ObjectId(model_id)

            # Find and delete document
            document = await ModelDocument.get(object_id)

            if document is None:
                return False

            await document.delete()

            logger.debug(f"Deleted investment model with ID {model_id}")
            return True

        except (ValueError, TypeError) as e:
            error_msg = f"Invalid model ID format: {model_id}"
            logger.error(error_msg)
            raise RepositoryError(error_msg, operation="delete") from e
        except Exception as e:
            error_msg = f"Failed to delete model {model_id}: {str(e)}"
            logger.error(error_msg)
            raise RepositoryError(error_msg, operation="delete") from e

    async def list_all(self) -> List[InvestmentModel]:
        """
        List all investment models.

        Returns:
            List[InvestmentModel]: List of all models
        """
        try:
            # Find all documents, sorted by creation date (newest first)
            documents = await ModelDocument.find_all().sort("-created_at").to_list()

            # Convert to domain models
            return [doc.to_domain_model() for doc in documents]

        except Exception as e:
            error_msg = f"Failed to list all models: {str(e)}"
            logger.error(error_msg)
            raise RepositoryError(error_msg, operation="list_all") from e

    async def list_with_pagination(
        self,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        sort_by: Optional[List[str]] = None,
    ) -> List[InvestmentModel]:
        """
        List models with pagination and sorting support.

        Args:
            offset: Number of models to skip (0-based). If None, start from beginning.
            limit: Maximum number of models to return. If None, return all from offset.
            sort_by: List of fields to sort by. Valid fields: model_id, name, last_rebalance_date.
                    Fields can be prefixed with + (ascending) or - (descending). Default is ascending.
                    If None or empty, no sorting is applied.

        Returns:
            List of models matching the pagination and sorting criteria

        Raises:
            ValueError: If offset or limit are negative, or if sort_by contains invalid fields
        """
        try:
            # Validate parameters
            if offset is not None and offset < 0:
                raise ValueError("Offset must be non-negative")
            if limit is not None and limit < 0:
                raise ValueError("Limit must be non-negative")

            # Valid sort fields mapping from API field names to MongoDB field names
            valid_sort_fields = {
                "model_id": "_id",
                "name": "name",
                "last_rebalance_date": "last_rebalance_date",
            }

            # Parse sort criteria with direction support
            sort_criteria = []
            if sort_by:
                for field_spec in sort_by:
                    # Parse direction prefix
                    direction = 1  # Default to ascending
                    field_name = field_spec

                    if field_spec.startswith('+'):
                        direction = 1  # Ascending
                        field_name = field_spec[1:]
                    elif field_spec.startswith('-'):
                        direction = -1  # Descending
                        field_name = field_spec[1:]

                    # Validate field name
                    if field_name not in valid_sort_fields:
                        valid_fields_with_prefixes = []
                        for field in valid_sort_fields.keys():
                            valid_fields_with_prefixes.extend(
                                [field, f"+{field}", f"-{field}"]
                            )
                        raise ValueError(
                            f"Invalid sort field: {field_spec}. Valid fields are: {', '.join(valid_fields_with_prefixes)}"
                        )

                    # Add to sort criteria as tuple (field, direction)
                    mongo_field = valid_sort_fields[field_name]
                    sort_criteria.append((mongo_field, direction))

            # Build query
            query = ModelDocument.find_all()

            # Apply sorting if specified
            if sort_criteria:
                # MongoDB sort with multiple fields and directions
                query = query.sort(sort_criteria)

            # Apply pagination
            if offset is not None:
                query = query.skip(offset)
            if limit is not None:
                query = query.limit(limit)

            # Execute query
            documents = await query.to_list()

            # Convert to domain models
            return [doc.to_domain_model() for doc in documents]

        except ValueError:
            raise  # Re-raise validation errors
        except Exception as e:
            error_msg = f"Failed to list models with pagination: {str(e)}"
            logger.error(error_msg)
            raise RepositoryError(error_msg, operation="list_with_pagination") from e

    async def count_all(self) -> int:
        """
        Get the total number of models.

        Returns:
            Total count of models
        """
        try:
            return await ModelDocument.count()
        except Exception as e:
            error_msg = f"Failed to count models: {str(e)}"
            logger.error(error_msg)
            raise RepositoryError(error_msg, operation="count_all") from e

    async def exists_by_name(self, name: str) -> bool:
        """
        Check if a model with the given name exists.

        Args:
            name: The model name to check

        Returns:
            bool: True if model exists, False otherwise
        """
        try:
            # Use count instead of find to be more efficient
            count = await ModelDocument.find({"name": name}).count()
            return count > 0

        except Exception as e:
            error_msg = f"Failed to check if model '{name}' exists: {str(e)}"
            logger.error(error_msg)
            raise RepositoryError(error_msg, operation="exists_by_name") from e

    async def find_by_portfolio(self, portfolio_id: str) -> List[InvestmentModel]:
        """
        Find all models associated with a specific portfolio.

        Args:
            portfolio_id: The portfolio ID to search for

        Returns:
            List[InvestmentModel]: List of models containing the portfolio
        """
        try:
            # Find documents with portfolio in portfolios array (multikey index)
            documents = (
                await ModelDocument.find({"portfolios": portfolio_id})
                .sort("-created_at")
                .to_list()
            )

            # Convert to domain models
            return [doc.to_domain_model() for doc in documents]

        except Exception as e:
            error_msg = (
                f"Failed to find models for portfolio '{portfolio_id}': {str(e)}"
            )
            logger.error(error_msg)
            raise RepositoryError(error_msg, operation="find_by_portfolio") from e

    async def find_by_last_rebalance_date(
        self, cutoff_date: datetime
    ) -> List[InvestmentModel]:
        """
        Find models rebalanced on or after the cutoff date.

        Args:
            cutoff_date: The cutoff date for filtering

        Returns:
            List[InvestmentModel]: List of models with recent rebalancing
        """
        try:
            # Find documents with last_rebalance_date >= cutoff_date
            documents = (
                await ModelDocument.find({"last_rebalance_date": {"$gte": cutoff_date}})
                .sort("-last_rebalance_date")
                .to_list()
            )

            # Convert to domain models
            return [doc.to_domain_model() for doc in documents]

        except Exception as e:
            error_msg = (
                f"Failed to find models by rebalance date {cutoff_date}: {str(e)}"
            )
            logger.error(error_msg)
            raise RepositoryError(
                error_msg, operation="find_by_last_rebalance_date"
            ) from e

    async def find_models_needing_rebalance(
        self, days_threshold: int = 30
    ) -> List[InvestmentModel]:
        """
        Find models that need rebalancing based on last rebalance date.

        Args:
            days_threshold: Number of days since last rebalance to consider stale

        Returns:
            List[InvestmentModel]: List of models needing rebalancing
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_threshold)

            # Find models with no rebalance date or old rebalance date
            documents = (
                await ModelDocument.find(
                    {
                        "$or": [
                            {"last_rebalance_date": None},
                            {"last_rebalance_date": {"$lt": cutoff_date}},
                        ]
                    }
                )
                .sort("last_rebalance_date")
                .to_list()
            )

            # Convert to domain models
            return [doc.to_domain_model() for doc in documents]

        except Exception as e:
            error_msg = f"Failed to find models needing rebalance: {str(e)}"
            logger.error(error_msg)
            raise RepositoryError(
                error_msg, operation="find_models_needing_rebalance"
            ) from e

    async def get_models_by_security(self, security_id: str) -> List[InvestmentModel]:
        """
        Find all models that contain a specific security.

        Args:
            security_id: The security ID to search for

        Returns:
            List[InvestmentModel]: List of models containing the security
        """
        try:
            # Find documents with security_id in positions array
            documents = (
                await ModelDocument.find({"positions.security_id": security_id})
                .sort("-created_at")
                .to_list()
            )

            # Convert to domain models
            return [doc.to_domain_model() for doc in documents]

        except Exception as e:
            error_msg = f"Failed to find models for security '{security_id}': {str(e)}"
            logger.error(error_msg)
            raise RepositoryError(error_msg, operation="get_models_by_security") from e

    async def get_portfolio_count(self) -> int:
        """
        Get the total number of unique portfolios across all models.

        Returns:
            int: Total number of unique portfolios
        """
        try:
            # Use aggregation pipeline to get unique portfolio count
            pipeline = [
                {"$unwind": "$portfolios"},
                {"$group": {"_id": "$portfolios"}},
                {"$count": "total"},
            ]

            result = await ModelDocument.aggregate(pipeline).to_list()

            return result[0]["total"] if result else 0

        except Exception as e:
            error_msg = f"Failed to get portfolio count: {str(e)}"
            logger.error(error_msg)
            raise RepositoryError(error_msg, operation="get_portfolio_count") from e

    async def get_position_count(self) -> int:
        """
        Get the total number of positions across all models.

        Returns:
            int: Total number of positions
        """
        try:
            # Use aggregation pipeline to sum position counts
            pipeline = [
                {"$project": {"position_count": {"$size": "$positions"}}},
                {"$group": {"_id": None, "total": {"$sum": "$position_count"}}},
            ]

            result = await ModelDocument.aggregate(pipeline).to_list()

            return result[0]["total"] if result else 0

        except Exception as e:
            error_msg = f"Failed to get position count: {str(e)}"
            logger.error(error_msg)
            raise RepositoryError(error_msg, operation="get_position_count") from e

    async def exists_by_id(self, entity_id: str) -> bool:
        """
        Check if a model exists by its ID.

        Args:
            entity_id: The model ID to check

        Returns:
            True if model exists, False otherwise

        Raises:
            ValidationError: If entity_id format is invalid
        """
        try:
            # Validate ObjectId format
            if not ObjectId.is_valid(entity_id):
                raise ValueError(f"Invalid ObjectId format: {entity_id}")

            # Check if document exists
            doc = await ModelDocument.find_one({"_id": ObjectId(entity_id)})
            exists = doc is not None

            logger.debug(f"Checked existence for model {entity_id}: {exists}")
            return exists

        except Exception as e:
            logger.error(f"Error checking model existence {entity_id}: {e}")
            raise RepositoryError(
                f"Failed to check model existence: {e}", operation="exists_by_id"
            )

    async def get_portfolio_count_for_model(self, model_id: str) -> int:
        """
        Get the number of portfolios associated with a model.

        Args:
            model_id: The model ID to count portfolios for

        Returns:
            Number of portfolios associated with the model

        Raises:
            ValidationError: If model_id format is invalid
        """
        try:
            # Validate ObjectId format
            if not ObjectId.is_valid(model_id):
                raise ValueError(f"Invalid ObjectId format: {model_id}")

            # Find the model document
            doc = await ModelDocument.find_one({"_id": ObjectId(model_id)})
            if not doc:
                logger.warning(f"Model not found for portfolio count: {model_id}")
                return 0

            portfolio_count = len(doc.portfolios)
            logger.debug(f"Portfolio count for model {model_id}: {portfolio_count}")
            return portfolio_count

        except Exception as e:
            logger.error(f"Error getting portfolio count for model {model_id}: {e}")
            raise RepositoryError(
                f"Failed to get portfolio count: {e}",
                operation="get_portfolio_count_for_model",
            )

    async def get_position_count_for_model(self, model_id: str) -> int:
        """
        Get the number of positions in a model.

        Args:
            model_id: The model ID to count positions for

        Returns:
            Number of positions in the model

        Raises:
            ValidationError: If model_id format is invalid
        """
        try:
            # Validate ObjectId format
            if not ObjectId.is_valid(model_id):
                raise ValueError(f"Invalid ObjectId format: {model_id}")

            # Find the model document
            doc = await ModelDocument.find_one({"_id": ObjectId(model_id)})
            if not doc:
                logger.warning(f"Model not found for position count: {model_id}")
                return 0

            position_count = len(doc.positions)
            logger.debug(f"Position count for model {model_id}: {position_count}")
            return position_count

        except Exception as e:
            logger.error(f"Error getting position count for model {model_id}: {e}")
            raise RepositoryError(
                f"Failed to get position count: {e}",
                operation="get_position_count_for_model",
            )

    def _convert_raw_to_domain_model(self, raw_document: dict) -> InvestmentModel:
        """Convert raw MongoDB document to domain InvestmentModel without creating ModelDocument."""
        from src.domain.entities.model import InvestmentModel
        from src.models.model import PositionEmbedded

        # Convert positions
        positions = []
        for pos_data in raw_document.get('positions', []):
            # Create PositionEmbedded and convert to domain
            pos_embedded = PositionEmbedded(**pos_data)
            positions.append(pos_embedded.to_domain_position())

        # Create domain model
        return InvestmentModel(
            model_id=raw_document['_id'],
            name=raw_document['name'],
            positions=positions,
            portfolios=raw_document.get('portfolios', []).copy(),
            last_rebalance_date=raw_document.get('last_rebalance_date'),
            version=raw_document.get('version', 1),
        )
