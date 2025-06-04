"""
Portfolio Accounting Service client for retrieving portfolio balance data.

This module provides integration with the Portfolio Accounting Service to:
- Retrieve current portfolio positions and balances
- Get portfolio market values
- Access cash position information
"""

import logging
from decimal import Decimal
from typing import Dict, List

from src.config import get_settings
from src.core.exceptions import ExternalServiceError
from src.infrastructure.external.base_client import (
    BaseServiceClient,
    ExternalServiceClientProtocol,
)

logger = logging.getLogger(__name__)


class PortfolioAccountingClient(ExternalServiceClientProtocol):
    """
    Client for Portfolio Accounting Service integration.

    Provides access to portfolio balance data including:
    - Security positions with quantities and market values
    - Cash positions
    - Total portfolio market value calculations
    """

    def __init__(self, base_url: str = None, timeout: float = None):
        """
        Initialize the Portfolio Accounting Service client.

        Args:
            base_url: Base URL of the Portfolio Accounting Service
            timeout: Request timeout in seconds
        """
        settings = get_settings()

        self.base_url = base_url or "http://globeco-portfolio-accounting-service:8087"
        self.timeout = timeout or settings.external_service_timeout

        self._base_client = BaseServiceClient(
            base_url=self.base_url,
            service_name="portfolio-accounting",
            timeout=self.timeout,
            max_retries=3,
        )

    async def get_portfolio_balances(self, portfolio_id: str) -> List[Dict]:
        """
        Retrieve current balance data for a portfolio.

        Args:
            portfolio_id: The portfolio ID to get balances for

        Returns:
            List of balance entries with structure:
            [
                {
                    "securityId": "24-char-security-id",
                    "quantity": 100,
                    "marketValue": Decimal("10000.00")
                },
                {
                    "cash": True,
                    "quantity": 1,
                    "marketValue": Decimal("2500.00")
                }
            ]

        Raises:
            ExternalServiceError: If portfolio not found or service error
        """
        try:
            logger.debug(f"Getting portfolio balances for {portfolio_id}")

            response = await self._base_client._make_request(
                "GET", f"/api/v1/portfolio/{portfolio_id}/balances"
            )

            balances = response.get("balances", [])

            # Convert market values to Decimal for financial precision
            for balance in balances:
                if "marketValue" in balance:
                    balance["marketValue"] = Decimal(str(balance["marketValue"]))

            logger.info(
                f"Retrieved {len(balances)} balance entries for portfolio {portfolio_id}"
            )
            return balances

        except ExternalServiceError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting portfolio balances: {str(e)}")
            raise ExternalServiceError(
                f"Failed to retrieve portfolio balances: {str(e)}",
                service="portfolio-accounting",
            )

    async def get_portfolio_market_value(self, portfolio_id: str) -> Decimal:
        """
        Calculate total market value for a portfolio.

        Args:
            portfolio_id: The portfolio ID to calculate value for

        Returns:
            Total market value as Decimal

        Raises:
            ExternalServiceError: If portfolio not found or service error
        """
        try:
            balances = await self.get_portfolio_balances(portfolio_id)

            total_value = Decimal("0")
            for balance in balances:
                total_value += balance.get("marketValue", Decimal("0"))

            logger.debug(
                f"Calculated portfolio {portfolio_id} market value: {total_value}"
            )
            return total_value

        except Exception as e:
            logger.error(f"Error calculating portfolio market value: {str(e)}")
            raise ExternalServiceError(
                f"Failed to calculate portfolio market value: {str(e)}",
                service="portfolio-accounting",
            )

    async def get_portfolio_positions(self, portfolio_id: str) -> Dict[str, int]:
        """
        Get security positions (excluding cash) as quantity mapping.

        Args:
            portfolio_id: The portfolio ID to get positions for

        Returns:
            Dict mapping security IDs to quantities: {"SEC123...": 100, ...}

        Raises:
            ExternalServiceError: If portfolio not found or service error
        """
        try:
            balances = await self.get_portfolio_balances(portfolio_id)

            positions = {}
            for balance in balances:
                # Skip cash positions
                if balance.get("cash", False):
                    continue

                security_id = balance.get("securityId")
                quantity = balance.get("quantity", 0)

                if security_id and quantity > 0:
                    positions[security_id] = quantity

            logger.debug(
                f"Retrieved {len(positions)} security positions for portfolio {portfolio_id}"
            )
            return positions

        except Exception as e:
            logger.error(f"Error getting portfolio positions: {str(e)}")
            raise ExternalServiceError(
                f"Failed to retrieve portfolio positions: {str(e)}",
                service="portfolio-accounting",
            )

    async def get_cash_position(self, portfolio_id: str) -> Decimal:
        """
        Get cash position market value for a portfolio.

        Args:
            portfolio_id: The portfolio ID to get cash position for

        Returns:
            Cash position market value as Decimal

        Raises:
            ExternalServiceError: If portfolio not found or service error
        """
        try:
            balances = await self.get_portfolio_balances(portfolio_id)

            cash_value = Decimal("0")
            for balance in balances:
                if balance.get("cash", False):
                    cash_value += balance.get("marketValue", Decimal("0"))

            logger.debug(f"Portfolio {portfolio_id} cash position: {cash_value}")
            return cash_value

        except Exception as e:
            logger.error(f"Error getting cash position: {str(e)}")
            raise ExternalServiceError(
                f"Failed to retrieve cash position: {str(e)}",
                service="portfolio-accounting",
            )

    async def health_check(self) -> bool:
        """
        Check if the Portfolio Accounting Service is healthy.

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
