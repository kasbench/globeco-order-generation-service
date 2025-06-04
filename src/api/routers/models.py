"""
FastAPI router for investment model management endpoints.

This module provides HTTP endpoints for CRUD operations on investment models:
- GET /models - List all models
- GET /model/{model_id} - Get specific model
- POST /models - Create new model
- PUT /model/{model_id} - Update existing model
- POST /model/{model_id}/position - Add position to model
- PUT /model/{model_id}/position - Update model position
- DELETE /model/{model_id}/position - Remove position from model
- POST /model/{model_id}/portfolio - Add portfolios to model
- DELETE /model/{model_id}/portfolio - Remove portfolios from model

All endpoints include proper error handling, validation, and status codes.
"""

import re
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import ValidationError

from src.core.exceptions import ModelNotFoundError, OptimisticLockingError
from src.core.exceptions import ValidationError as DomainValidationError
from src.core.services.model_service import ModelService
from src.schemas.models import (
    ModelDTO,
    ModelPortfolioDTO,
    ModelPositionDTO,
    ModelPostDTO,
    ModelPutDTO,
)

router = APIRouter(prefix="", tags=["models"])


def get_model_service() -> ModelService:
    """Dependency to get model service instance."""
    # This will be implemented when we create the actual service
    # For now, return a mock for testing
    from unittest.mock import AsyncMock

    return AsyncMock()


def validate_model_id(
    model_id: str = Path(..., description="24-character model ID")
) -> str:
    """Validate model ID format."""
    if not re.match(r'^[a-fA-F0-9]{24}$', model_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid model ID format. Must be 24-character hexadecimal string.",
        )
    return model_id


@router.get("/models", response_model=List[ModelDTO])
async def get_models(
    model_service: ModelService = Depends(get_model_service),
) -> List[ModelDTO]:
    """
    Get all investment models.

    Returns:
        List of all investment models in the system.

    Raises:
        500: Internal server error
    """
    try:
        models = await model_service.get_all_models()
        return models
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve models: {str(e)}",
        )


@router.get("/model/{model_id}", response_model=ModelDTO)
async def get_model_by_id(
    model_id: str = Depends(validate_model_id),
    model_service: ModelService = Depends(get_model_service),
) -> ModelDTO:
    """
    Get investment model by ID.

    Args:
        model_id: 24-character hexadecimal model ID

    Returns:
        Investment model details.

    Raises:
        400: Invalid model ID format
        404: Model not found
        500: Internal server error
    """
    try:
        model = await model_service.get_model_by_id(model_id)
        return model
    except ModelNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model with ID {model_id} not found",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve model: {str(e)}",
        )


@router.post("/models", response_model=ModelDTO, status_code=status.HTTP_201_CREATED)
async def create_model(
    model_data: ModelPostDTO, model_service: ModelService = Depends(get_model_service)
) -> ModelDTO:
    """
    Create a new investment model.

    Args:
        model_data: Model creation data

    Returns:
        Created investment model.

    Raises:
        400: Validation error or business rule violation
        500: Internal server error
    """
    try:
        model = await model_service.create_model(model_data)
        return model
    except (ValidationError, DomainValidationError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create model: {str(e)}",
        )


@router.put("/model/{model_id}", response_model=ModelDTO)
async def update_model(
    model_data: ModelPutDTO,
    model_id: str = Depends(validate_model_id),
    model_service: ModelService = Depends(get_model_service),
) -> ModelDTO:
    """
    Update an existing investment model.

    Args:
        model_id: 24-character hexadecimal model ID
        model_data: Model update data

    Returns:
        Updated investment model.

    Raises:
        400: Invalid model ID format or validation error
        404: Model not found
        409: Optimistic locking conflict
        500: Internal server error
    """
    try:
        model = await model_service.update_model(model_id, model_data)
        return model
    except ModelNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model with ID {model_id} not found",
        )
    except OptimisticLockingError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Model was modified by another process. Please refresh and try again.",
        )
    except (ValidationError, DomainValidationError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update model: {str(e)}",
        )


@router.post("/model/{model_id}/position", response_model=ModelDTO)
async def add_position(
    position_data: ModelPositionDTO,
    model_id: str = Depends(validate_model_id),
    model_service: ModelService = Depends(get_model_service),
) -> ModelDTO:
    """
    Add a position to an investment model.

    Args:
        model_id: 24-character hexadecimal model ID
        position_data: Position to add

    Returns:
        Updated investment model.

    Raises:
        400: Invalid model ID format or validation error
        404: Model not found
        500: Internal server error
    """
    try:
        model = await model_service.add_position(model_id, position_data)
        return model
    except ModelNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model with ID {model_id} not found",
        )
    except (ValidationError, DomainValidationError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add position: {str(e)}",
        )


@router.put("/model/{model_id}/position", response_model=ModelDTO)
async def update_position(
    position_data: ModelPositionDTO,
    model_id: str = Depends(validate_model_id),
    model_service: ModelService = Depends(get_model_service),
) -> ModelDTO:
    """
    Update a position in an investment model.

    Args:
        model_id: 24-character hexadecimal model ID
        position_data: Position to update

    Returns:
        Updated investment model.

    Raises:
        400: Invalid model ID format or validation error
        404: Model not found
        500: Internal server error
    """
    try:
        model = await model_service.update_position(model_id, position_data)
        return model
    except ModelNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model with ID {model_id} not found",
        )
    except (ValidationError, DomainValidationError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update position: {str(e)}",
        )


@router.delete("/model/{model_id}/position", response_model=ModelDTO)
async def remove_position(
    position_data: ModelPositionDTO,
    model_id: str = Depends(validate_model_id),
    model_service: ModelService = Depends(get_model_service),
) -> ModelDTO:
    """
    Remove a position from an investment model.

    Args:
        model_id: 24-character hexadecimal model ID
        position_data: Position to remove

    Returns:
        Updated investment model.

    Raises:
        400: Invalid model ID format or validation error
        404: Model not found
        500: Internal server error
    """
    try:
        model = await model_service.remove_position(model_id, position_data)
        return model
    except ModelNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model with ID {model_id} not found",
        )
    except (ValidationError, DomainValidationError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove position: {str(e)}",
        )


@router.post("/model/{model_id}/portfolio", response_model=ModelDTO)
async def add_portfolios(
    portfolio_data: ModelPortfolioDTO,
    model_id: str = Depends(validate_model_id),
    model_service: ModelService = Depends(get_model_service),
) -> ModelDTO:
    """
    Add portfolios to an investment model.

    Args:
        model_id: 24-character hexadecimal model ID
        portfolio_data: Portfolios to add

    Returns:
        Updated investment model.

    Raises:
        400: Invalid model ID format or validation error
        404: Model not found
        500: Internal server error
    """
    try:
        model = await model_service.add_portfolios(model_id, portfolio_data)
        return model
    except ModelNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model with ID {model_id} not found",
        )
    except (ValidationError, DomainValidationError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add portfolios: {str(e)}",
        )


@router.delete("/model/{model_id}/portfolio", response_model=ModelDTO)
async def remove_portfolios(
    portfolio_data: ModelPortfolioDTO,
    model_id: str = Depends(validate_model_id),
    model_service: ModelService = Depends(get_model_service),
) -> ModelDTO:
    """
    Remove portfolios from an investment model.

    Args:
        model_id: 24-character hexadecimal model ID
        portfolio_data: Portfolios to remove

    Returns:
        Updated investment model.

    Raises:
        400: Invalid model ID format or validation error
        404: Model not found
        500: Internal server error
    """
    try:
        model = await model_service.remove_portfolios(model_id, portfolio_data)
        return model
    except ModelNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model with ID {model_id} not found",
        )
    except (ValidationError, DomainValidationError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove portfolios: {str(e)}",
        )
