"""
Model Repository interface.

This module defines the repository interface for Investment Model persistence,
extending the base repository with model-specific operations.
"""

from abc import abstractmethod
from datetime import datetime

from src.domain.entities.model import InvestmentModel
from src.domain.repositories.base_repository import BaseRepository


class ModelRepository(BaseRepository[InvestmentModel]):
    """Repository interface for Investment Model persistence."""

    @abstractmethod
    async def get_by_name(self, name: str) -> InvestmentModel | None:
        """
        Retrieve a model by its name.

        Args:
            name: The name of the investment model

        Returns:
            The model if found, None otherwise
        """
        pass

    @abstractmethod
    async def exists_by_name(self, name: str) -> bool:
        """
        Check if a model exists with the given name.

        Args:
            name: The name to check for uniqueness

        Returns:
            True if a model with this name exists, False otherwise
        """
        pass

    @abstractmethod
    async def find_by_portfolio(self, portfolio_id: str) -> list[InvestmentModel]:
        """
        Find all models that include the specified portfolio.

        Args:
            portfolio_id: The portfolio ID to search for

        Returns:
            List of models that include this portfolio (may be empty)
        """
        pass

    @abstractmethod
    async def find_by_last_rebalance_date(
        self, cutoff_date: datetime
    ) -> list[InvestmentModel]:
        """
        Find models that were last rebalanced before the cutoff date.

        Args:
            cutoff_date: Only return models last rebalanced before this date

        Returns:
            List of models meeting the criteria (may be empty)
        """
        pass

    @abstractmethod
    async def find_models_needing_rebalance(self) -> list[InvestmentModel]:
        """
        Find models that may need rebalancing.

        This method implements business logic to identify models that
        haven't been rebalanced recently or meet other rebalancing criteria.

        Returns:
            List of models that may need rebalancing (may be empty)
        """
        pass

    @abstractmethod
    async def get_models_by_security(self, security_id: str) -> list[InvestmentModel]:
        """
        Find all models that contain positions in the specified security.

        Args:
            security_id: The security ID to search for

        Returns:
            List of models containing this security (may be empty)
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass
