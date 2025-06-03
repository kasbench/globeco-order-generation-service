"""
MongoDB implementation of the Model Repository using Beanie ODM.

This module provides the concrete implementation of the ModelRepository interface
for MongoDB persistence, using Beanie ODM for document operations.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from beanie.exceptions import DocumentNotFound
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

            logger.info(
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
            # Convert string ID to ObjectId
            object_id = ObjectId(model_id)

            # Find document by ID
            document = await ModelDocument.get(object_id)

            if document is None:
                return None

            # Convert to domain model
            return document.to_domain_model()

        except (ValueError, TypeError) as e:
            error_msg = f"Invalid model ID format: {model_id}"
            logger.error(error_msg)
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

            logger.info(
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

            logger.info(f"Deleted investment model with ID {model_id}")
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
            cutoff_date = datetime.utcnow() - timedelta(days=days_threshold)

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
