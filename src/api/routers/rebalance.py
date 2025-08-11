"""
Portfolio rebalancing API endpoints.

This module provides REST API endpoints for portfolio rebalancing operations,
including model-based and individual portfolio rebalancing.
"""

from typing import List

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, status

from src.api.dependencies import get_rebalance_service
from src.core.exceptions import (
    ExternalServiceError,
    ModelNotFoundError,
    OptimizationError,
    PortfolioNotFoundError,
)
from src.core.services.rebalance_service import RebalanceService
from src.schemas.rebalance import RebalanceDTO

logger = structlog.get_logger(__name__)
router = APIRouter()


def validate_model_id(model_id: str) -> str:
    """Validate model ID format."""
    if not model_id or len(model_id) != 24:
        raise ValueError("Invalid model ID format")
    return model_id


def validate_portfolio_id(portfolio_id: str) -> str:
    """Validate portfolio ID format."""
    if not portfolio_id or len(portfolio_id) != 24:
        raise ValueError("Invalid portfolio ID format")
    return portfolio_id


@router.post(
    "/model/{model_id}/rebalance",
    response_model=List[RebalanceDTO],
    status_code=status.HTTP_200_OK,
)
async def rebalance_model_portfolios(
    model_id: str = Path(..., description="Model ID"),
    rebalance_service: RebalanceService = Depends(get_rebalance_service),
) -> List[RebalanceDTO]:
    """Rebalance all portfolios associated with an investment model.

    Returns a list containing a single RebalanceDTO that aggregates all transactions
    and drifts from all portfolios in the model. The portfolio_id in the response
    will be the model_id to indicate this is a model-level rebalance operation.
    """
    try:
        validate_model_id(model_id)
        return await rebalance_service.rebalance_model_portfolios(model_id)
    except ModelNotFoundError:
        logger.warning("Model not found for rebalancing", model_id=model_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Model {model_id} not found"
        )
    except OptimizationError as e:
        logger.warning("Optimization failed", model_id=model_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        )
    except ExternalServiceError as e:
        logger.error("External service error", model_id=model_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="External service unavailable",
        )
    except ValueError:
        logger.warning("Invalid model ID format", model_id=model_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid model ID format"
        )
    except Exception as e:
        logger.error("Model rebalancing failed", model_id=model_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post(
    "/portfolio/{portfolio_id}/rebalance",
    response_model=RebalanceDTO,
    status_code=status.HTTP_200_OK,
)
async def rebalance_portfolio(
    portfolio_id: str = Path(..., description="Portfolio ID"),
    rebalance_service: RebalanceService = Depends(get_rebalance_service),
) -> RebalanceDTO:
    """Rebalance a single portfolio using its associated investment model."""
    try:
        validate_portfolio_id(portfolio_id)
        return await rebalance_service.rebalance_portfolio(portfolio_id)
    except PortfolioNotFoundError:
        logger.warning("Portfolio not found for rebalancing", portfolio_id=portfolio_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Portfolio {portfolio_id} not found",
        )
    except OptimizationError as e:
        logger.warning("Optimization failed", portfolio_id=portfolio_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        )
    except ExternalServiceError as e:
        logger.error("External service error", portfolio_id=portfolio_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="External service unavailable",
        )
    except ValueError:
        logger.warning("Invalid portfolio ID format", portfolio_id=portfolio_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid portfolio ID format",
        )
    except Exception as e:
        logger.error(
            "Portfolio rebalancing failed", portfolio_id=portfolio_id, error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
