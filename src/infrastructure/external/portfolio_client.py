"""
Portfolio Service client for portfolio metadata and validation.

This module provides integration with the Portfolio Service to:
- Retrieve portfolio metadata and status
- Validate portfolio existence
- Support batch portfolio validation
"""

import logging
from typing import Dict, List

from src.config import get_settings
from src.core.exceptions import ExternalServiceError
from src.infrastructure.external.base_client import (
    BaseServiceClient,
    ExternalServiceClientProtocol,
)

logger = logging.getLogger(__name__)


class PortfolioClient(ExternalServiceClientProtocol):
    """
    Client for Portfolio Service integration.

    Provides access to portfolio metadata including:
    - Portfolio information and status
    - Portfolio validation for model associations
    - Batch portfolio operations
    """

    def __init__(self, base_url: str = None, timeout: float = None):
        """
        Initialize the Portfolio Service client.

        Args:
            base_url: Base URL of the Portfolio Service
            timeout: Request timeout in seconds
        """
        settings = get_settings()

        self.base_url = base_url or "http://globeco-portfolio-service:8000"
        self.timeout = timeout or settings.external_service_timeout

        self._base_client = BaseServiceClient(
            base_url=self.base_url,
            service_name="portfolio",
            timeout=self.timeout,
            max_retries=3,
        )

    async def get_portfolio(self, portfolio_id: str) -> Dict:
        """
        Retrieve portfolio metadata.

        Args:
            portfolio_id: The portfolio ID to get information for

        Returns:
            Dict with portfolio information: {
                "id": "portfolio-id",
                "name": "Portfolio Name",
                "type": "GROWTH|INCOME|BALANCED",
                "status": "ACTIVE|INACTIVE|CLOSED",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z"
            }

        Raises:
            ExternalServiceError: If portfolio not found or service error
        """
        try:
            logger.debug(f"Getting portfolio metadata for {portfolio_id}")

            response = await self._base_client._make_request(
                "GET", f"/api/v1/portfolio/{portfolio_id}"
            )

            logger.info(
                f"Retrieved portfolio metadata for {portfolio_id}: {response.get('name', 'Unknown')}"
            )
            return response

        except ExternalServiceError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting portfolio metadata: {str(e)}")
            raise ExternalServiceError(
                f"Failed to retrieve portfolio metadata: {str(e)}", service="portfolio"
            )

    async def validate_portfolios(
        self, portfolio_ids: List[str]
    ) -> Dict[str, List[str]]:
        """
        Validate existence and status of multiple portfolios.

        Args:
            portfolio_ids: List of portfolio IDs to validate

        Returns:
            Dict with validation results: {
                "valid": ["portfolio1", "portfolio2"],
                "invalid": ["portfolio3"],
                "inactive": ["portfolio4"]
            }

        Raises:
            ExternalServiceError: If service error occurs
        """
        try:
            logger.debug(f"Validating {len(portfolio_ids)} portfolios")

            response = await self._base_client._make_request(
                "POST",
                "/api/v1/portfolios/validate",
                json={"portfolioIds": portfolio_ids},
            )

            valid_count = len(response.get("valid", []))
            invalid_count = len(response.get("invalid", []))
            inactive_count = len(response.get("inactive", []))

            logger.info(
                f"Portfolio validation completed: {valid_count} valid, "
                f"{invalid_count} invalid, {inactive_count} inactive"
            )

            return response

        except ExternalServiceError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error validating portfolios: {str(e)}")
            raise ExternalServiceError(
                f"Failed to validate portfolios: {str(e)}", service="portfolio"
            )

    async def get_portfolio_status(self, portfolio_id: str) -> str:
        """
        Get the current status of a portfolio.

        Args:
            portfolio_id: The portfolio ID to check status for

        Returns:
            Portfolio status: "ACTIVE", "INACTIVE", or "CLOSED"

        Raises:
            ExternalServiceError: If portfolio not found or service error
        """
        try:
            portfolio_data = await self.get_portfolio(portfolio_id)
            status = portfolio_data.get("status", "UNKNOWN")

            logger.debug(f"Portfolio {portfolio_id} status: {status}")
            return status

        except Exception as e:
            logger.error(f"Error getting portfolio status: {str(e)}")
            raise ExternalServiceError(
                f"Failed to retrieve portfolio status: {str(e)}", service="portfolio"
            )

    async def is_portfolio_active(self, portfolio_id: str) -> bool:
        """
        Check if a portfolio is in active status.

        Args:
            portfolio_id: The portfolio ID to check

        Returns:
            bool: True if portfolio is active, False otherwise

        Raises:
            ExternalServiceError: If portfolio not found or service error
        """
        try:
            status = await self.get_portfolio_status(portfolio_id)
            is_active = status == "ACTIVE"

            logger.debug(f"Portfolio {portfolio_id} active status: {is_active}")
            return is_active

        except Exception as e:
            logger.error(f"Error checking portfolio active status: {str(e)}")
            raise ExternalServiceError(
                f"Failed to check portfolio active status: {str(e)}",
                service="portfolio",
            )

    async def get_portfolios_by_type(self, portfolio_type: str) -> List[Dict]:
        """
        Retrieve portfolios by type.

        Args:
            portfolio_type: Portfolio type filter ("GROWTH", "INCOME", "BALANCED")

        Returns:
            List of portfolio metadata dicts

        Raises:
            ExternalServiceError: If service error occurs
        """
        try:
            logger.debug(f"Getting portfolios by type: {portfolio_type}")

            response = await self._base_client._make_request(
                "GET", f"/api/v1/portfolios?type={portfolio_type}"
            )

            portfolios = response.get("portfolios", [])
            logger.info(
                f"Retrieved {len(portfolios)} portfolios of type {portfolio_type}"
            )

            return portfolios

        except ExternalServiceError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting portfolios by type: {str(e)}")
            raise ExternalServiceError(
                f"Failed to retrieve portfolios by type: {str(e)}", service="portfolio"
            )

    async def health_check(self) -> bool:
        """
        Check if the Portfolio Service is healthy.

        Returns:
            bool: True if service is healthy, False otherwise
        """
        return await self._base_client.health_check()

    @property
    def circuit_breaker_status(self) -> Dict:
        """Get circuit breaker status for monitoring."""
        return self._base_client.circuit_breaker_status

    async def close(self):
        """Close the HTTP client."""
        if self._base_client._client:
            await self._base_client._client.aclose()
