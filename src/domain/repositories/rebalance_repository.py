"""
Repository interface for rebalance data operations.

This module defines the abstract repository interface for storing and retrieving
rebalance results from the persistence layer.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from src.domain.entities.rebalance import Rebalance


class RebalanceRepository(ABC):
    """Abstract repository interface for rebalance data operations."""

    @abstractmethod
    async def create(self, rebalance: Rebalance) -> Rebalance:
        """
        Create a new rebalance record.

        Args:
            rebalance: The rebalance to create

        Returns:
            Rebalance: The created rebalance with updated metadata

        Raises:
            RepositoryError: If creation fails
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    async def list_all(self) -> List[Rebalance]:
        """
        Retrieve all rebalances.

        Returns:
            List[Rebalance]: All rebalances in the repository

        Raises:
            RepositoryError: If retrieval fails
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    async def count_all(self) -> int:
        """
        Get the total number of rebalances.

        Returns:
            Total count of rebalances

        Raises:
            RepositoryError: If count operation fails
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    async def get_portfolios_by_rebalance_id(
        self, rebalance_id: str
    ) -> Optional[List["PortfolioWithPositionsDTO"]]:
        """
        Get all portfolios associated with a specific rebalance.

        Args:
            rebalance_id: The unique identifier of the rebalance

        Returns:
            Optional[List[PortfolioWithPositionsDTO]]: List of portfolios with positions
                                                       if rebalance exists, None otherwise

        Raises:
            RepositoryError: If retrieval fails
        """
        pass

    @abstractmethod
    async def get_positions_by_rebalance_and_portfolio_id(
        self, rebalance_id: str, portfolio_id: str
    ) -> Optional[List["PositionDTO"]]:
        """
        Get all positions for a specific portfolio within a specific rebalance.

        Args:
            rebalance_id: The unique identifier of the rebalance
            portfolio_id: The unique identifier of the portfolio

        Returns:
            Optional[List[PositionDTO]]: List of positions if rebalance and portfolio exist,
                                        None if rebalance not found, empty list if portfolio
                                        not found in rebalance

        Raises:
            RepositoryError: If retrieval fails
        """
        pass
