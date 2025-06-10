"""
FastAPI router for rebalance data retrieval operations.

This module provides REST API endpoints for retrieving stored rebalance results
with pagination and filtering capabilities.
"""

import logging
from typing import List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.core.exceptions import ConcurrencyError, NotFoundError, RepositoryError
from src.core.mappers import RebalanceMapper
from src.domain.repositories.rebalance_repository import RebalanceRepository
from src.infrastructure.database.repositories.rebalance_repository import (
    MongoRebalanceRepository,
)
from src.schemas.rebalance import RebalanceResultDTO, RebalancesByPortfoliosRequestDTO

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["rebalances"])


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
        logger.info(f"Retrieving rebalances with offset={offset}, limit={limit}")

        # Get rebalances with pagination
        rebalances = await repository.list_with_pagination(offset=offset, limit=limit)

        # Convert to DTOs using mapper
        result = []
        for rebalance in rebalances:
            dto = RebalanceMapper.from_rebalance_entity(rebalance)
            result.append(dto)

        logger.info(f"Retrieved {len(result)} rebalances")
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
        logger.info(f"Retrieving rebalance {rebalance_id}")

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

        logger.info(f"Retrieved rebalance {rebalance_id}")
        return dto

    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except RepositoryError as e:
        logger.error(f"Repository error retrieving rebalance {rebalance_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve rebalance",
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
        logger.info(
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

        logger.info(f"Retrieved {len(result)} rebalances for portfolios")
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

        logger.info(f"Deleted rebalance {rebalance_id}")
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
