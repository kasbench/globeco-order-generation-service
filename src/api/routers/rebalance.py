"""
FastAPI router for portfolio rebalancing endpoints.

This module provides HTTP endpoints for portfolio rebalancing operations:
- POST /model/{model_id}/rebalance - Rebalance all portfolios in a model
- POST /portfolio/{portfolio_id}/rebalance - Rebalance single portfolio

All endpoints include proper error handling, validation, and status codes.
"""

import re
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path, status

from src.core.exceptions import (
    ExternalServiceError,
    ModelNotFoundError,
    OptimizationError,
    PortfolioNotFoundError,
)
from src.core.services.rebalance_service import RebalanceService
from src.schemas.rebalance import RebalanceDTO

router = APIRouter(prefix="", tags=["rebalancing"])


def get_rebalance_service() -> RebalanceService:
    """Dependency to get rebalance service instance."""
    # This will be implemented when we create the actual service
    # For now, return a mock for testing
    from unittest.mock import AsyncMock

    return AsyncMock()


def validate_object_id(object_id: str, object_type: str = "ID") -> str:
    """Validate ObjectId format."""
    if not re.match(r'^[a-fA-F0-9]{24}$', object_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {object_type} format. Must be 24-character hexadecimal string.",
        )
    return object_id


@router.post("/model/{model_id}/rebalance", response_model=List[RebalanceDTO])
async def rebalance_model_portfolios(
    model_id: str = Path(..., description="24-character model ID"),
    rebalance_service: RebalanceService = Depends(get_rebalance_service),
) -> List[RebalanceDTO]:
    """
    Rebalance all portfolios associated with an investment model.

    Args:
        model_id: 24-character hexadecimal model ID

    Returns:
        List of rebalancing results for each portfolio in the model.

    Raises:
        400: Invalid model ID format
        404: Model not found
        422: Optimization failed (no feasible solution, solver timeout)
        503: External service unavailable
        500: Internal server error
    """
    # Validate model ID format
    validate_object_id(model_id, "model ID")

    try:
        results = await rebalance_service.rebalance_model_portfolios(model_id)
        return results
    except ModelNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model with ID {model_id} not found",
        )
    except OptimizationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Optimization failed: {str(e)}",
        )
    except ExternalServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"External service unavailable: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rebalance model portfolios: {str(e)}",
        )


@router.post("/portfolio/{portfolio_id}/rebalance", response_model=RebalanceDTO)
async def rebalance_portfolio(
    portfolio_id: str = Path(..., description="24-character portfolio ID"),
    rebalance_service: RebalanceService = Depends(get_rebalance_service),
) -> RebalanceDTO:
    """
    Rebalance a single portfolio.

    Args:
        portfolio_id: 24-character hexadecimal portfolio ID

    Returns:
        Rebalancing results for the portfolio.

    Raises:
        400: Invalid portfolio ID format
        404: Portfolio not found
        422: Optimization failed (no feasible solution, solver timeout)
        503: External service unavailable
        500: Internal server error
    """
    # Validate portfolio ID format
    validate_object_id(portfolio_id, "portfolio ID")

    try:
        result = await rebalance_service.rebalance_portfolio(portfolio_id)
        return result
    except PortfolioNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Portfolio with ID {portfolio_id} not found",
        )
    except OptimizationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Optimization failed: {str(e)}",
        )
    except ExternalServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"External service unavailable: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rebalance portfolio: {str(e)}",
        )
