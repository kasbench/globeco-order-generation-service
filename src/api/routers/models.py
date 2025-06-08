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
from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import ValidationError

from src.api.dependencies import get_model_service
from src.core.exceptions import (
    ModelNotFoundError,
    NotFoundError,
    OptimisticLockingError,
)
from src.core.exceptions import ValidationError as DomainValidationError
from src.core.services.model_service import ModelService
from src.schemas.models import (
    ModelDTO,
    ModelPortfolioDTO,
    ModelPositionDTO,
    ModelPostDTO,
    ModelPutDTO,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="", tags=["models"])


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


@router.get("/models", response_model=List[ModelDTO], status_code=status.HTTP_200_OK)
async def get_all_models(
    model_service: ModelService = Depends(get_model_service),
    offset: Optional[int] = Query(
        None, description="Number of models to skip (0-based)"
    ),
    limit: Optional[int] = Query(
        None, description="Maximum number of models to return"
    ),
    sort_by: Optional[str] = Query(
        None,
        description="Comma-separated list of fields to sort by (model_id, name, last_rebalance_date)",
    ),
) -> List[ModelDTO]:
    """Get all investment models with optional pagination and sorting."""
    try:
        # Parse sort_by parameter
        sort_fields = None
        if sort_by:
            sort_fields = [
                field.strip() for field in sort_by.split(",") if field.strip()
            ]

        # Validate offset and limit logic according to requirements
        if offset is not None and offset < 0:
            logger.warning("Invalid offset parameter", offset=offset)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Offset must be a non-negative integer",
            )

        if limit is not None and limit < 0:
            logger.warning("Invalid limit parameter", limit=limit)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Limit must be a non-negative integer",
            )

        # If neither parameter is specified, use original method
        if offset is None and limit is None and sort_fields is None:
            return await model_service.get_all_models()

        # Use pagination method
        return await model_service.get_models_with_pagination(
            offset=offset, limit=limit, sort_by=sort_fields
        )
    except HTTPException:
        # Re-raise HTTPExceptions without modification
        raise
    except DomainValidationError as e:
        logger.warning("Validation error in get models", error=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Failed to retrieve all models", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get(
    "/model/{model_id}", response_model=ModelDTO, status_code=status.HTTP_200_OK
)
async def get_model_by_id(
    model_id: str = Path(..., description="Model ID"),
    model_service: ModelService = Depends(get_model_service),
) -> ModelDTO:
    """Get investment model by ID."""
    try:
        validate_model_id(model_id)
        return await model_service.get_model_by_id(model_id)
    except HTTPException:
        # Re-raise HTTPExceptions from validate_model_id without changing them
        raise
    except ModelNotFoundError:
        logger.warning("Model not found", model_id=model_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Model {model_id} not found"
        )
    except NotFoundError:
        logger.warning("Model not found", model_id=model_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Model {model_id} not found"
        )
    except ValueError:
        logger.warning("Invalid model ID format", model_id=model_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid model ID format"
        )
    except Exception as e:
        logger.error("Failed to retrieve model", model_id=model_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/models", response_model=ModelDTO, status_code=status.HTTP_201_CREATED)
async def create_model(
    model_data: ModelPostDTO, model_service: ModelService = Depends(get_model_service)
) -> ModelDTO:
    """Create a new investment model."""
    try:
        return await model_service.create_model(model_data)
    except DomainValidationError as e:
        logger.warning("Model validation failed", name=model_data.name, error=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Failed to create model", name=model_data.name, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.put(
    "/model/{model_id}", response_model=ModelDTO, status_code=status.HTTP_200_OK
)
async def update_model(
    model_data: ModelPutDTO,
    model_id: str = Path(..., description="Model ID"),
    model_service: ModelService = Depends(get_model_service),
) -> ModelDTO:
    """Update an existing investment model."""
    try:
        validate_model_id(model_id)
        return await model_service.update_model(model_id, model_data)
    except ModelNotFoundError:
        logger.warning("Model not found for update", model_id=model_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Model {model_id} not found"
        )
    except NotFoundError:
        logger.warning("Model not found for update", model_id=model_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Model {model_id} not found"
        )
    except OptimisticLockingError:
        logger.warning("Optimistic locking conflict", model_id=model_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Model has been modified by another process",
        )
    except DomainValidationError as e:
        logger.warning("Model validation failed", model_id=model_id, error=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ValueError:
        logger.warning("Invalid model ID format", model_id=model_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid model ID format"
        )
    except Exception as e:
        logger.error("Failed to update model", model_id=model_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post(
    "/model/{model_id}/position",
    response_model=ModelDTO,
    status_code=status.HTTP_200_OK,
)
async def add_position(
    position_data: ModelPositionDTO,
    model_id: str = Path(..., description="Model ID"),
    model_service: ModelService = Depends(get_model_service),
) -> ModelDTO:
    """Add a position to an investment model."""
    try:
        validate_model_id(model_id)
        return await model_service.add_position(model_id, position_data)
    except NotFoundError:
        logger.warning("Model not found for position addition", model_id=model_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Model {model_id} not found"
        )
    except DomainValidationError as e:
        logger.warning("Position validation failed", model_id=model_id, error=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ValueError:
        logger.warning("Invalid model ID format", model_id=model_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid model ID format"
        )
    except Exception as e:
        logger.error("Failed to add position", model_id=model_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.put(
    "/model/{model_id}/position",
    response_model=ModelDTO,
    status_code=status.HTTP_200_OK,
)
async def update_position(
    position_data: ModelPositionDTO,
    model_id: str = Path(..., description="Model ID"),
    model_service: ModelService = Depends(get_model_service),
) -> ModelDTO:
    """Update a position in an investment model."""
    try:
        validate_model_id(model_id)
        return await model_service.update_position(model_id, position_data)
    except NotFoundError:
        logger.warning("Model not found for position update", model_id=model_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Model {model_id} not found"
        )
    except DomainValidationError as e:
        logger.warning("Position validation failed", model_id=model_id, error=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ValueError:
        logger.warning("Invalid model ID format", model_id=model_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid model ID format"
        )
    except Exception as e:
        logger.error("Failed to update position", model_id=model_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.delete(
    "/model/{model_id}/position",
    response_model=ModelDTO,
    status_code=status.HTTP_200_OK,
)
async def remove_position(
    position_data: ModelPositionDTO,
    model_id: str = Path(..., description="Model ID"),
    model_service: ModelService = Depends(get_model_service),
) -> ModelDTO:
    """Remove a position from an investment model."""
    try:
        validate_model_id(model_id)
        return await model_service.remove_position(model_id, position_data)
    except NotFoundError:
        logger.warning("Model not found for position removal", model_id=model_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Model {model_id} not found"
        )
    except DomainValidationError as e:
        logger.warning("Position validation failed", model_id=model_id, error=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ValueError:
        logger.warning("Invalid model ID format", model_id=model_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid model ID format"
        )
    except Exception as e:
        logger.error("Failed to remove position", model_id=model_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post(
    "/model/{model_id}/portfolio",
    response_model=ModelDTO,
    status_code=status.HTTP_200_OK,
)
async def add_portfolios(
    portfolio_data: ModelPortfolioDTO,
    model_id: str = Path(..., description="Model ID"),
    model_service: ModelService = Depends(get_model_service),
) -> ModelDTO:
    """Add portfolios to an investment model."""
    try:
        validate_model_id(model_id)
        return await model_service.add_portfolios(model_id, portfolio_data)
    except NotFoundError:
        logger.warning("Model not found for portfolio addition", model_id=model_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Model {model_id} not found"
        )
    except DomainValidationError as e:
        logger.warning("Portfolio validation failed", model_id=model_id, error=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ValueError:
        logger.warning("Invalid model ID format", model_id=model_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid model ID format"
        )
    except Exception as e:
        logger.error("Failed to add portfolios", model_id=model_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.delete(
    "/model/{model_id}/portfolio",
    response_model=ModelDTO,
    status_code=status.HTTP_200_OK,
)
async def remove_portfolios(
    portfolio_data: ModelPortfolioDTO,
    model_id: str = Path(..., description="Model ID"),
    model_service: ModelService = Depends(get_model_service),
) -> ModelDTO:
    """Remove portfolios from an investment model."""
    try:
        validate_model_id(model_id)
        return await model_service.remove_portfolios(model_id, portfolio_data)
    except NotFoundError:
        logger.warning("Model not found for portfolio removal", model_id=model_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Model {model_id} not found"
        )
    except DomainValidationError as e:
        logger.warning("Portfolio validation failed", model_id=model_id, error=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ValueError:
        logger.warning("Invalid model ID format", model_id=model_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid model ID format"
        )
    except Exception as e:
        logger.error("Failed to remove portfolios", model_id=model_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
