"""
FastAPI router for rebalance data retrieval operations.

This module provides REST API endpoints for retrieving stored rebalance results
with pagination and filtering capabilities.
"""

import logging
from typing import List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from src.core.exceptions import ConcurrencyError, NotFoundError, RepositoryError
from src.core.mappers import RebalanceMapper
from src.domain.repositories.rebalance_repository import RebalanceRepository
from src.infrastructure.database.repositories.rebalance_repository import (
    MongoRebalanceRepository,
)
from src.schemas.rebalance import (
    PortfolioWithPositionsDTO,
    PositionDTO,
    RebalanceResultDTO,
    RebalancesByPortfoliosRequestDTO,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["rebalances"])


class PortfolioErrorResponse(BaseModel):
    """Custom error response model for portfolio endpoint."""

    error: str
    message: str
    status_code: int


def get_rebalance_repository() -> RebalanceRepository:
    """Dependency to get rebalance repository instance."""
    return MongoRebalanceRepository()


@router.get("/rebalances", response_model=List[RebalanceResultDTO])
async def get_rebalances(
    offset: Optional[int] = Query(
        None, ge=0, description="Number of rebalances to skip"
    ),
    limit: Optional[int] = Query(
        None, ge=1, le=100, description="Maximum number of rebalances to return"
    ),
    repository: RebalanceRepository = Depends(get_rebalance_repository),
) -> List[RebalanceResultDTO]:
    """
    Get all rebalances with pagination.

    Args:
        offset: Number of rebalances to skip (default: 0)
        limit: Maximum number of rebalances to return (default: 10, max: 100)
        repository: Rebalance repository dependency

    Returns:
        List[RebalanceResultDTO]: Paginated list of rebalances

    Raises:
        HTTPException: If retrieval fails or parameters are invalid
    """
    try:
        logger.debug(f"Retrieving rebalances with offset={offset}, limit={limit}")

        # Get rebalances with pagination
        rebalances = await repository.list_with_pagination(offset=offset, limit=limit)

        # Convert to DTOs using mapper
        result = []
        for rebalance in rebalances:
            dto = RebalanceMapper.from_rebalance_entity(rebalance)
            result.append(dto)

        logger.debug(f"Retrieved {len(result)} rebalances")
        return result

    except ValueError as e:
        logger.error(f"Invalid pagination parameters: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid pagination parameters: {str(e)}",
        )
    except RepositoryError as e:
        logger.error(f"Repository error retrieving rebalances: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve rebalances",
        )


@router.get("/rebalance/{rebalance_id}", response_model=RebalanceResultDTO)
async def get_rebalance_by_id(
    rebalance_id: str,
    repository: RebalanceRepository = Depends(get_rebalance_repository),
) -> RebalanceResultDTO:
    """
    Get a specific rebalance by ID.

    Args:
        rebalance_id: The rebalance ID to retrieve
        repository: Rebalance repository dependency

    Returns:
        RebalanceResultDTO: The rebalance data

    Raises:
        HTTPException: If rebalance not found or retrieval fails
    """
    try:
        logger.debug(f"Retrieving rebalance {rebalance_id}")

        # Validate ObjectId format
        logger.debug(f"API: Validating ObjectId format for rebalance_id={rebalance_id}")
        is_valid = ObjectId.is_valid(rebalance_id)
        logger.debug(f"API: ObjectId.is_valid({rebalance_id}) = {is_valid}")

        if not is_valid:
            logger.error(f"API: ObjectId validation failed for {rebalance_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid rebalance ID format",
            )

        # Get rebalance
        logger.debug(f"API: Calling repository.get_by_id({rebalance_id})")
        rebalance = await repository.get_by_id(rebalance_id)
        logger.debug(f"API: Repository returned: {rebalance is not None}")

        if rebalance is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Rebalance {rebalance_id} not found",
            )

        # Convert to DTO using mapper
        dto = RebalanceMapper.from_rebalance_entity(rebalance)

        logger.debug(f"Retrieved rebalance {rebalance_id}")
        return dto

    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except RepositoryError as e:
        logger.error(f"Repository error retrieving rebalance {rebalance_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve rebalance",
        )


@router.get(
    "/rebalance/{rebalance_id}/portfolios",
    response_model=List[PortfolioWithPositionsDTO],
)
async def get_portfolios_by_rebalance_id(
    rebalance_id: str,
    repository: RebalanceRepository = Depends(get_rebalance_repository),
) -> List[PortfolioWithPositionsDTO]:
    """
    Get all portfolios associated with a specific rebalance for lazy-loading.

    This endpoint provides portfolio-level data for a specific rebalance when
    users expand rebalance rows in the UI.

    Args:
        rebalance_id: The unique identifier of the rebalance (MongoDB ObjectId format)
        repository: Rebalance repository dependency

    Returns:
        List[PortfolioWithPositionsDTO]: List of portfolios with their positions

    Raises:
        HTTPException: If rebalance not found, invalid ID format, or retrieval fails
    """
    try:
        logger.debug(f"Retrieving portfolios for rebalance {rebalance_id}")

        # Validate ObjectId format
        logger.debug(f"API: Validating ObjectId format for rebalance_id={rebalance_id}")
        if not ObjectId.is_valid(rebalance_id):
            logger.error(f"API: ObjectId validation failed for {rebalance_id}")
            error_response = PortfolioErrorResponse(
                error="Invalid rebalance ID",
                message="Rebalance ID must be a valid MongoDB ObjectId",
                status_code=400,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_response.model_dump(),
            )

        # Get portfolios for the rebalance
        logger.debug(
            f"API: Calling repository.get_portfolios_by_rebalance_id({rebalance_id})"
        )
        portfolios = await repository.get_portfolios_by_rebalance_id(rebalance_id)
        logger.debug(f"API: Repository returned: {portfolios is not None}")

        if portfolios is None:
            logger.warning(f"Rebalance {rebalance_id} not found")
            error_response = PortfolioErrorResponse(
                error="Rebalance not found",
                message=f"No rebalance found with ID: {rebalance_id}",
                status_code=404,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_response.model_dump(),
            )

        logger.debug(
            f"Retrieved {len(portfolios)} portfolios for rebalance {rebalance_id}"
        )
        return portfolios

    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except RepositoryError as e:
        logger.error(
            f"Repository error retrieving portfolios for rebalance {rebalance_id}: {e}"
        )
        error_response = PortfolioErrorResponse(
            error="Internal server error",
            message="An error occurred while retrieving portfolio data",
            status_code=500,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response.model_dump(),
        )
    except Exception as e:
        logger.error(
            f"Unexpected error retrieving portfolios for rebalance {rebalance_id}: {e}"
        )
        error_response = PortfolioErrorResponse(
            error="Internal server error",
            message="An error occurred while retrieving portfolio data",
            status_code=500,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response.model_dump(),
        )


@router.get(
    "/rebalance/{rebalance_id}/portfolio/{portfolio_id}/positions",
    response_model=List[PositionDTO],
)
async def get_portfolio_positions(
    rebalance_id: str,
    portfolio_id: str,
    repository: RebalanceRepository = Depends(get_rebalance_repository),
) -> List[PositionDTO]:
    """
    Get all positions for a specific portfolio within a specific rebalance.

    This endpoint provides position-level data for a specific portfolio when
    users expand portfolio rows in the rebalance results UI for lazy-loading.

    Args:
        rebalance_id: The unique identifier of the rebalance (MongoDB ObjectId format)
        portfolio_id: The unique identifier of the portfolio (MongoDB ObjectId format)
        repository: Rebalance repository dependency

    Returns:
        List[PositionDTO]: List of positions for the specified portfolio

    Raises:
        HTTPException: If rebalance or portfolio not found, invalid ID format, or retrieval fails
    """
    try:
        logger.debug(
            f"Retrieving positions for portfolio {portfolio_id} in rebalance {rebalance_id}"
        )

        # Validate ObjectId formats
        if not ObjectId.is_valid(rebalance_id):
            logger.error(f"API: Invalid rebalance ObjectId format: {rebalance_id}")
            error_response = PortfolioErrorResponse(
                error="Invalid ID format",
                message="Rebalance ID and Portfolio ID must be valid MongoDB ObjectIds",
                status_code=400,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_response.model_dump(),
            )

        if not ObjectId.is_valid(portfolio_id):
            logger.error(f"API: Invalid portfolio ObjectId format: {portfolio_id}")
            error_response = PortfolioErrorResponse(
                error="Invalid ID format",
                message="Rebalance ID and Portfolio ID must be valid MongoDB ObjectIds",
                status_code=400,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_response.model_dump(),
            )

        # Get positions for the portfolio in the rebalance
        logger.debug(
            f"API: Calling repository.get_positions_by_rebalance_and_portfolio_id({rebalance_id}, {portfolio_id})"
        )
        positions = await repository.get_positions_by_rebalance_and_portfolio_id(
            rebalance_id, portfolio_id
        )
        logger.debug(f"API: Repository returned: {positions is not None}")

        if positions is None:
            logger.warning(f"Rebalance {rebalance_id} not found")
            error_response = PortfolioErrorResponse(
                error="Rebalance not found",
                message=f"No rebalance found with ID: {rebalance_id}",
                status_code=404,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_response.model_dump(),
            )

        logger.debug(
            f"Retrieved {len(positions)} positions for portfolio {portfolio_id} in rebalance {rebalance_id}"
        )
        return positions

    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except RepositoryError as e:
        # Check if this is a portfolio not found error
        if hasattr(e, 'operation') and e.operation == "portfolio_not_found":
            logger.warning(
                f"Portfolio {portfolio_id} not found in rebalance {rebalance_id}"
            )
            error_response = PortfolioErrorResponse(
                error="Portfolio not found",
                message=f"No portfolio found with ID: {portfolio_id} in rebalance: {rebalance_id}",
                status_code=404,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_response.model_dump(),
            )
        logger.error(
            f"Repository error retrieving positions for portfolio {portfolio_id} in rebalance {rebalance_id}: {e}"
        )
        error_response = PortfolioErrorResponse(
            error="Internal server error",
            message="An error occurred while retrieving position data",
            status_code=500,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response.model_dump(),
        )
    except Exception as e:
        logger.error(
            f"Unexpected error retrieving positions for portfolio {portfolio_id} in rebalance {rebalance_id}: {e}"
        )
        error_response = PortfolioErrorResponse(
            error="Internal server error",
            message="An error occurred while retrieving position data",
            status_code=500,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response.model_dump(),
        )


@router.post("/rebalances/portfolios", response_model=List[RebalanceResultDTO])
async def get_rebalances_by_portfolios(
    request: RebalancesByPortfoliosRequestDTO,
    offset: Optional[int] = Query(
        None, ge=0, description="Number of rebalances to skip"
    ),
    limit: Optional[int] = Query(
        None, ge=1, le=100, description="Maximum number of rebalances to return"
    ),
    repository: RebalanceRepository = Depends(get_rebalance_repository),
) -> List[RebalanceResultDTO]:
    """
    Get rebalances for specific portfolios with pagination.

    Args:
        request: Request containing list of portfolio IDs
        offset: Number of rebalances to skip (default: 0)
        limit: Maximum number of rebalances to return (default: 10, max: 100)
        repository: Rebalance repository dependency

    Returns:
        List[RebalanceResultDTO]: Filtered and paginated list of rebalances

    Raises:
        HTTPException: If retrieval fails or parameters are invalid
    """
    try:
        logger.debug(
            f"Retrieving rebalances for {len(request.portfolios)} portfolios with offset={offset}, limit={limit}"
        )

        # Get rebalances by portfolios with pagination
        rebalances = await repository.list_by_portfolios(
            portfolio_ids=request.portfolios, offset=offset, limit=limit
        )

        # Convert to DTOs using mapper
        result = []
        for rebalance in rebalances:
            dto = RebalanceMapper.from_rebalance_entity(rebalance)
            result.append(dto)

        logger.debug(f"Retrieved {len(result)} rebalances for portfolios")
        return result

    except ValueError as e:
        logger.error(f"Invalid request parameters: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request parameters: {str(e)}",
        )
    except RepositoryError as e:
        logger.error(f"Repository error retrieving rebalances by portfolios: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve rebalances",
        )


@router.delete("/rebalance/{rebalance_id}")
async def delete_rebalance(
    rebalance_id: str,
    version: int = Query(..., description="Expected version for optimistic locking"),
    repository: RebalanceRepository = Depends(get_rebalance_repository),
) -> dict:
    """
    Delete a specific rebalance by ID with optimistic locking.

    Args:
        rebalance_id: The rebalance ID to delete
        version: Expected version for optimistic locking
        repository: Rebalance repository dependency

    Returns:
        dict: Success message

    Raises:
        HTTPException: If rebalance not found, version mismatch, or deletion fails
    """
    try:
        logger.info(f"Deleting rebalance {rebalance_id} with version {version}")

        # Validate ObjectId format
        if not ObjectId.is_valid(rebalance_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid rebalance ID format",
            )

        # Delete rebalance
        deleted = await repository.delete_by_id(rebalance_id, version)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Rebalance {rebalance_id} not found",
            )

        logger.debug(f"Deleted rebalance {rebalance_id}")
        return {"message": f"Rebalance {rebalance_id} deleted successfully"}

    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except ConcurrencyError as e:
        logger.error(f"Concurrency error deleting rebalance {rebalance_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except RepositoryError as e:
        logger.error(f"Repository error deleting rebalance {rebalance_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete rebalance",
        )
