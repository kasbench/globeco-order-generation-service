"""
Model management service implementation.

This module provides the application service layer for investment model operations,
coordinating between the API layer, domain logic, and infrastructure layer.
"""

from typing import List, Optional

import structlog

from src.core.exceptions import (
    BusinessRuleViolationError,
    NotFoundError,
    OptimisticLockingError,
    ServiceException,
    ValidationError,
)
from src.core.mappers import ModelMapper
from src.domain.entities.model import InvestmentModel
from src.domain.repositories.model_repository import ModelRepository
from src.domain.services.implementations.portfolio_validation_service import (
    PortfolioValidationService,
)
from src.schemas.models import (
    ModelDTO,
    ModelPortfolioDTO,
    ModelPositionDTO,
    ModelPostDTO,
    ModelPutDTO,
)

logger = structlog.get_logger(__name__)


class ModelService:
    """Service for managing investment models."""

    def __init__(
        self,
        model_repository: ModelRepository,
        validation_service: PortfolioValidationService,
        model_mapper: ModelMapper,
    ):
        """Initialize the model service.

        Args:
            model_repository: Repository for model persistence
            validation_service: Service for business rule validation
            model_mapper: Mapper for domain-DTO conversion
        """
        self._model_repository = model_repository
        self._validation_service = validation_service
        self._model_mapper = model_mapper

    async def get_all_models(self) -> List[ModelDTO]:
        """
        Retrieve all investment models.

        Returns:
            List[ModelDTO]: List of all models as DTOs

        Raises:
            ServiceException: If retrieval fails
        """
        try:
            logger.info("Retrieving all investment models")
            models = await self._model_repository.list_all()
            return [self._model_mapper.to_dto(model) for model in models]
        except Exception as e:
            logger.error(f"Failed to retrieve models: {str(e)}")
            raise ServiceException(f"Failed to retrieve models: {str(e)}") from e

    async def get_model_by_id(self, model_id: str) -> ModelDTO:
        """Retrieve a specific model by ID.

        Args:
            model_id: The model identifier

        Returns:
            ModelDTO object

        Raises:
            NotFoundError: If model doesn't exist
        """
        logger.info("Retrieving model by ID", model_id=model_id)

        try:
            model = await self._model_repository.get_by_id(model_id)
            if not model:
                logger.warning("Model not found", model_id=model_id)
                raise NotFoundError(f"Model {model_id} not found")

            logger.info(
                "Model retrieved successfully", model_id=model_id, name=model.name
            )
            return self._model_mapper.to_dto(model)

        except NotFoundError:
            raise
        except Exception as e:
            logger.error("Failed to retrieve model", model_id=model_id, error=str(e))
            raise

    async def create_model(self, create_dto: ModelPostDTO) -> ModelDTO:
        """Create a new investment model.

        Args:
            create_dto: Model creation data

        Returns:
            Created ModelDTO

        Raises:
            ValidationError: If model data is invalid
        """
        logger.info("Creating new model", name=create_dto.name)

        try:
            # Convert DTO to domain entity
            model = self._model_mapper.from_post_dto(create_dto)

            # Validate business rules
            await self._validation_service.validate_model(model)

            # Persist model
            created_model = await self._model_repository.create(model)

            logger.info(
                "Model created successfully",
                model_id=str(created_model.model_id),
                name=created_model.name,
            )

            return self._model_mapper.to_dto(created_model)

        except ValidationError:
            logger.warning("Model validation failed", name=create_dto.name)
            raise
        except Exception as e:
            logger.error("Failed to create model", name=create_dto.name, error=str(e))
            raise

    async def update_model(self, model_id: str, update_dto: ModelPutDTO) -> ModelDTO:
        """Update an existing investment model.

        Args:
            model_id: The model identifier
            update_dto: Model update data

        Returns:
            Updated ModelDTO

        Raises:
            NotFoundError: If model doesn't exist
            OptimisticLockingError: If version conflict occurs
            ValidationError: If updated data is invalid
        """
        logger.info("Updating model", model_id=model_id, name=update_dto.name)

        try:
            # Check if model exists
            existing_model = await self._model_repository.get_by_id(model_id)
            if not existing_model:
                logger.warning("Model not found for update", model_id=model_id)
                raise NotFoundError(f"Model {model_id} not found")

            # Check version for optimistic locking
            if existing_model.version != update_dto.version:
                logger.warning(
                    "Version conflict during update",
                    model_id=model_id,
                    expected_version=update_dto.version,
                    current_version=existing_model.version,
                )
                raise OptimisticLockingError(
                    "Model has been modified by another process"
                )

            # Convert DTO to domain entity with updated data
            updated_model = self._model_mapper.from_put_dto(model_id, update_dto)

            # Validate business rules
            await self._validation_service.validate_model(updated_model)

            # Persist updated model
            saved_model = await self._model_repository.update(updated_model)

            logger.info(
                "Model updated successfully",
                model_id=model_id,
                name=saved_model.name,
                new_version=saved_model.version,
            )

            return self._model_mapper.to_dto(saved_model)

        except (NotFoundError, OptimisticLockingError, ValidationError):
            raise
        except Exception as e:
            logger.error("Failed to update model", model_id=model_id, error=str(e))
            raise

    async def add_position(
        self, model_id: str, position_dto: ModelPositionDTO
    ) -> ModelDTO:
        """Add a position to an investment model.

        Args:
            model_id: The model identifier
            position_dto: Position to add

        Returns:
            Updated ModelDTO

        Raises:
            NotFoundError: If model doesn't exist
            ValidationError: If position data is invalid
        """
        logger.info(
            "Adding position to model",
            model_id=model_id,
            security_id=position_dto.security_id,
        )

        try:
            # Get existing model
            model = await self._model_repository.get_by_id(model_id)
            if not model:
                logger.warning(
                    "Model not found for position addition", model_id=model_id
                )
                raise NotFoundError(f"Model {model_id} not found")

            # Convert position DTO to domain object
            position = self._model_mapper.position_from_dto(position_dto)

            # Add position to model (domain logic handles validation)
            model.add_position(position)

            # Validate updated model
            await self._validation_service.validate_model(model)

            # Persist updated model
            updated_model = await self._model_repository.update(model)

            logger.info(
                "Position added successfully",
                model_id=model_id,
                security_id=position_dto.security_id,
            )

            return self._model_mapper.to_dto(updated_model)

        except (NotFoundError, ValidationError):
            raise
        except Exception as e:
            logger.error(
                "Failed to add position",
                model_id=model_id,
                security_id=position_dto.security_id,
                error=str(e),
            )
            raise

    async def update_position(
        self, model_id: str, position_dto: ModelPositionDTO
    ) -> ModelDTO:
        """Update a position in an investment model.

        Args:
            model_id: The model identifier
            position_dto: Updated position data

        Returns:
            Updated ModelDTO

        Raises:
            NotFoundError: If model doesn't exist
            ValidationError: If position data is invalid
        """
        logger.info(
            "Updating position in model",
            model_id=model_id,
            security_id=position_dto.security_id,
        )

        try:
            # Get existing model
            model = await self._model_repository.get_by_id(model_id)
            if not model:
                logger.warning("Model not found for position update", model_id=model_id)
                raise NotFoundError(f"Model {model_id} not found")

            # Convert position DTO to domain object
            position = self._model_mapper.position_from_dto(position_dto)

            # Update position in model (domain logic handles validation)
            model.update_position(position)

            # Validate updated model
            await self._validation_service.validate_model(model)

            # Persist updated model
            updated_model = await self._model_repository.update(model)

            logger.info(
                "Position updated successfully",
                model_id=model_id,
                security_id=position_dto.security_id,
            )

            return self._model_mapper.to_dto(updated_model)

        except (NotFoundError, ValidationError):
            raise
        except Exception as e:
            logger.error(
                "Failed to update position",
                model_id=model_id,
                security_id=position_dto.security_id,
                error=str(e),
            )
            raise

    async def remove_position(
        self, model_id: str, position_dto: ModelPositionDTO
    ) -> ModelDTO:
        """Remove a position from an investment model.

        Args:
            model_id: The model identifier
            position_dto: Position to remove (identified by security_id)

        Returns:
            Updated ModelDTO

        Raises:
            NotFoundError: If model doesn't exist
            ValidationError: If removal would violate business rules
        """
        logger.info(
            "Removing position from model",
            model_id=model_id,
            security_id=position_dto.security_id,
        )

        try:
            # Get existing model
            model = await self._model_repository.get_by_id(model_id)
            if not model:
                logger.warning(
                    "Model not found for position removal", model_id=model_id
                )
                raise NotFoundError(f"Model {model_id} not found")

            # Remove position from model (domain logic handles validation)
            model.remove_position(position_dto.security_id)

            # Validate updated model
            await self._validation_service.validate_model(model)

            # Persist updated model
            updated_model = await self._model_repository.update(model)

            logger.info(
                "Position removed successfully",
                model_id=model_id,
                security_id=position_dto.security_id,
            )

            return self._model_mapper.to_dto(updated_model)

        except (NotFoundError, ValidationError):
            raise
        except Exception as e:
            logger.error(
                "Failed to remove position",
                model_id=model_id,
                security_id=position_dto.security_id,
                error=str(e),
            )
            raise

    async def add_portfolios(
        self, model_id: str, portfolio_dto: ModelPortfolioDTO
    ) -> ModelDTO:
        """Add portfolios to an investment model.

        Args:
            model_id: The model identifier
            portfolio_dto: Portfolio IDs to add

        Returns:
            Updated ModelDTO

        Raises:
            NotFoundError: If model doesn't exist
            ValidationError: If portfolio data is invalid
        """
        logger.info(
            "Adding portfolios to model",
            model_id=model_id,
            portfolio_count=len(portfolio_dto.portfolios),
        )

        try:
            # Get existing model
            model = await self._model_repository.get_by_id(model_id)
            if not model:
                logger.warning(
                    "Model not found for portfolio addition", model_id=model_id
                )
                raise NotFoundError(f"Model {model_id} not found")

            # Add portfolios to model (domain logic handles validation)
            for portfolio_id in portfolio_dto.portfolios:
                model.add_portfolio(portfolio_id)

            # Validate updated model
            await self._validation_service.validate_model(model)

            # Persist updated model
            updated_model = await self._model_repository.update(model)

            logger.info(
                "Portfolios added successfully",
                model_id=model_id,
                portfolio_count=len(portfolio_dto.portfolios),
            )

            return self._model_mapper.to_dto(updated_model)

        except (NotFoundError, ValidationError):
            raise
        except Exception as e:
            logger.error("Failed to add portfolios", model_id=model_id, error=str(e))
            raise

    async def remove_portfolios(
        self, model_id: str, portfolio_dto: ModelPortfolioDTO
    ) -> ModelDTO:
        """Remove portfolios from an investment model.

        Args:
            model_id: The model identifier
            portfolio_dto: Portfolio IDs to remove

        Returns:
            Updated ModelDTO

        Raises:
            NotFoundError: If model doesn't exist
            ValidationError: If removal would violate business rules
        """
        logger.info(
            "Removing portfolios from model",
            model_id=model_id,
            portfolio_count=len(portfolio_dto.portfolios),
        )

        try:
            # Get existing model
            model = await self._model_repository.get_by_id(model_id)
            if not model:
                logger.warning(
                    "Model not found for portfolio removal", model_id=model_id
                )
                raise NotFoundError(f"Model {model_id} not found")

            # Remove portfolios from model (domain logic handles validation)
            for portfolio_id in portfolio_dto.portfolios:
                model.remove_portfolio(portfolio_id)

            # Validate updated model
            await self._validation_service.validate_model(model)

            # Persist updated model
            updated_model = await self._model_repository.update(model)

            logger.info(
                "Portfolios removed successfully",
                model_id=model_id,
                portfolio_count=len(portfolio_dto.portfolios),
            )

            return self._model_mapper.to_dto(updated_model)

        except (NotFoundError, ValidationError):
            raise
        except Exception as e:
            logger.error("Failed to remove portfolios", model_id=model_id, error=str(e))
            raise
