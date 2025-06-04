"""
Pricing Service client for retrieving real-time security price data.

This module provides integration with the Pricing Service to:
- Retrieve current security prices
- Support batch price requests for optimization
- Handle missing price data gracefully
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional

from src.config import get_settings
from src.core.exceptions import ExternalServiceError
from src.infrastructure.external.base_client import (
    BaseServiceClient,
    ExternalServiceClientProtocol,
)

logger = logging.getLogger(__name__)


class PricingServiceClient(ExternalServiceClientProtocol):
    """
    Client for Pricing Service integration.

    Provides access to real-time security pricing data including:
    - Individual security price lookups
    - Batch price requests for optimization
    - Decimal precision for financial calculations
    """

    def __init__(self, base_url: str = None, timeout: float = None):
        """
        Initialize the Pricing Service client.

        Args:
            base_url: Base URL of the Pricing Service
            timeout: Request timeout in seconds
        """
        settings = get_settings()

        self.base_url = base_url or "http://globeco-pricing-service:8083"
        self.timeout = timeout or settings.external_service_timeout

        self._base_client = BaseServiceClient(
            base_url=self.base_url,
            service_name="pricing",
            timeout=self.timeout,
            max_retries=3,
        )

    async def get_security_prices(self, security_ids: List[str]) -> Dict[str, Decimal]:
        """
        Retrieve current prices for a list of securities.

        Args:
            security_ids: List of 24-character security IDs

        Returns:
            Dict mapping security IDs to prices: {"SEC123...": Decimal("100.50"), ...}
            Note: Only securities with available prices are included

        Raises:
            ExternalServiceError: If service error occurs
        """
        try:
            logger.debug(f"Getting prices for {len(security_ids)} securities")

            response = await self._base_client._make_request(
                "POST", "/api/v1/prices/batch", json={"securityIds": security_ids}
            )

            prices_data = response.get("prices", {})

            # Convert to Decimal for financial precision
            prices = {}
            for security_id, price_str in prices_data.items():
                try:
                    prices[security_id] = Decimal(str(price_str))
                except (ValueError, TypeError) as e:
                    logger.warning(
                        f"Invalid price for {security_id}: {price_str} - {e}"
                    )
                    continue

            logger.info(
                f"Retrieved prices for {len(prices)}/{len(security_ids)} securities"
            )

            # Log any missing prices
            missing_prices = set(security_ids) - set(prices.keys())
            if missing_prices:
                logger.warning(
                    f"Missing prices for {len(missing_prices)} securities: {list(missing_prices)[:5]}..."
                )

            return prices

        except ExternalServiceError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting security prices: {str(e)}")
            raise ExternalServiceError(
                f"Failed to retrieve security prices: {str(e)}", service="pricing"
            )

    async def get_security_price(self, security_id: str) -> Optional[Decimal]:
        """
        Retrieve current price for a single security.

        Args:
            security_id: 24-character security ID

        Returns:
            Current price as Decimal, or None if not available

        Raises:
            ExternalServiceError: If service error occurs
        """
        try:
            logger.debug(f"Getting price for security {security_id}")

            response = await self._base_client._make_request(
                "GET", f"/api/v1/security/{security_id}/price"
            )

            price_str = response.get("price")
            if price_str is None:
                logger.warning(f"No price available for security {security_id}")
                return None

            price = Decimal(str(price_str))
            logger.debug(f"Price for {security_id}: {price}")
            return price

        except ExternalServiceError as e:
            # If security not found (404), return None instead of raising
            if hasattr(e, 'status_code') and e.status_code == 404:
                logger.warning(f"Security {security_id} not found in pricing service")
                return None
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting security price: {str(e)}")
            raise ExternalServiceError(
                f"Failed to retrieve security price: {str(e)}", service="pricing"
            )

    async def validate_security_prices(
        self, security_ids: List[str]
    ) -> Dict[str, bool]:
        """
        Check which securities have available price data.

        Args:
            security_ids: List of security IDs to validate

        Returns:
            Dict mapping security IDs to availability: {"SEC123...": True, ...}

        Raises:
            ExternalServiceError: If service error occurs
        """
        try:
            logger.debug(f"Validating prices for {len(security_ids)} securities")

            response = await self._base_client._make_request(
                "POST", "/api/v1/prices/validate", json={"securityIds": security_ids}
            )

            availability = response.get("availability", {})

            logger.info(
                f"Price validation completed for {len(availability)} securities"
            )
            return availability

        except ExternalServiceError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error validating security prices: {str(e)}")
            raise ExternalServiceError(
                f"Failed to validate security prices: {str(e)}", service="pricing"
            )

    async def get_market_status(self) -> Dict[str, str]:
        """
        Get current market status information.

        Returns:
            Dict with market status information: {
                "status": "OPEN|CLOSED|PRE_MARKET|AFTER_MARKET",
                "timestamp": "2024-12-19T10:30:00Z",
                "next_open": "2024-12-19T14:30:00Z",
                "next_close": "2024-12-19T21:00:00Z"
            }

        Raises:
            ExternalServiceError: If service error occurs
        """
        try:
            logger.debug("Getting market status")

            response = await self._base_client._make_request(
                "GET", "/api/v1/market/status"
            )

            logger.debug(f"Market status: {response.get('status', 'UNKNOWN')}")
            return response

        except ExternalServiceError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting market status: {str(e)}")
            raise ExternalServiceError(
                f"Failed to retrieve market status: {str(e)}", service="pricing"
            )

    async def health_check(self) -> bool:
        """
        Check if the Pricing Service is healthy.

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
