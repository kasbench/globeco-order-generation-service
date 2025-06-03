"""
Base Repository interface.

This module defines the base repository interface that all domain repositories
should inherit from, providing common CRUD operations and patterns.
"""

from abc import ABC, abstractmethod
from typing import Generic, List, Optional, TypeVar

# Generic type for domain entities
T = TypeVar('T')


class BaseRepository(Generic[T], ABC):
    """Base repository interface for domain entities."""

    @abstractmethod
    async def create(self, entity: T) -> T:
        """
        Create a new entity.

        Args:
            entity: The domain entity to create

        Returns:
            The created entity with generated ID and metadata

        Raises:
            ValidationError: If entity data is invalid
            BusinessRuleViolationError: If creation violates business rules
        """
        pass

    @abstractmethod
    async def get_by_id(self, entity_id: str) -> Optional[T]:
        """
        Retrieve an entity by its ID.

        Args:
            entity_id: The unique identifier of the entity

        Returns:
            The entity if found, None otherwise

        Raises:
            ValidationError: If entity_id format is invalid
        """
        pass

    @abstractmethod
    async def update(self, entity: T) -> T:
        """
        Update an existing entity.

        Args:
            entity: The domain entity to update

        Returns:
            The updated entity with incremented version

        Raises:
            ValidationError: If entity not found or data is invalid
            BusinessRuleViolationError: If update violates business rules (e.g., version conflict)
        """
        pass

    @abstractmethod
    async def delete(self, entity_id: str) -> bool:
        """
        Delete an entity by its ID.

        Args:
            entity_id: The unique identifier of the entity to delete

        Returns:
            True if entity was deleted, False if not found

        Raises:
            ValidationError: If entity_id format is invalid
        """
        pass

    @abstractmethod
    async def list_all(self) -> List[T]:
        """
        Retrieve all entities.

        Returns:
            List of all entities (may be empty)
        """
        pass

    @abstractmethod
    async def exists_by_id(self, entity_id: str) -> bool:
        """
        Check if an entity exists by its ID.

        Args:
            entity_id: The unique identifier to check

        Returns:
            True if entity exists, False otherwise

        Raises:
            ValidationError: If entity_id format is invalid
        """
        pass
