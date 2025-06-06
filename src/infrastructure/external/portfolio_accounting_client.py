"""
Portfolio Accounting Service client for retrieving portfolio balance data.

This module provides integration with the Portfolio Accounting Service to:
- Retrieve current portfolio positions and balances
- Calculate portfolio market values using real-time pricing
- Access cash position information
"""

import logging
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Optional

from cachetools import TTLCache

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
    - Portfolio summary with cash and security positions
    - Market value calculation using real-time pricing
    - Integration with Security and Pricing services
    """

    # Class-level cache instances for thread safety
    _securities_cache = TTLCache(maxsize=1000, ttl=600)  # 10 minutes
    _prices_cache = TTLCache(maxsize=1000, ttl=60)  # 1 minute

    def __init__(
        self,
        base_url: str = None,
        timeout: float = None,
        security_client=None,
        pricing_client=None,
    ):
        """
        Initialize the Portfolio Accounting Service client.

        Args:
            base_url: Base URL of the Portfolio Accounting Service
            timeout: Request timeout in seconds
            security_client: Security service client for ticker lookups
            pricing_client: Pricing service client for price lookups
        """
        settings = get_settings()

        self.base_url = base_url or "http://globeco-portfolio-accounting-service:8087"
        self.timeout = timeout or 10.0  # 10 second timeout per requirement

        self._base_client = BaseServiceClient(
            base_url=self.base_url,
            service_name="portfolio-accounting",
            timeout=self.timeout,
            max_retries=3,
        )

        # Inject external service clients
        self._security_client = security_client
        self._pricing_client = pricing_client

    def _set_external_clients(self, security_client, pricing_client):
        """Set external service clients (used by dependency injection)."""
        self._security_client = security_client
        self._pricing_client = pricing_client

    async def get_portfolio_summary(self, portfolio_id: str) -> Dict:
        """
        Retrieve current portfolio summary data.

        Args:
            portfolio_id: The portfolio ID to get summary for

        Returns:
            Dict with portfolio summary structure:
            {
                "portfolioId": "683b6d88a29ee10e8b499643",
                "cashBalance": "3356336",
                "securityCount": 1,
                "lastUpdated": "2025-06-06T12:17:03.072131386Z",
                "securities": [
                    {
                        "securityId": "683b69d420f302c879a5fef0",
                        "quantityLong": "100",
                        "quantityShort": "0",
                        "netQuantity": "100",
                        "lastUpdated": "2025-06-06T12:16:50.080869Z"
                    }
                ]
            }

        Raises:
            ExternalServiceError: If portfolio not found or service error
        """
        try:
            logger.debug(f"Getting portfolio summary for {portfolio_id}")

            response = await self._base_client._make_request(
                "GET", f"/api/v1/portfolios/{portfolio_id}/summary"
            )

            # Handle empty response (no balance record)
            if response is None:
                logger.info(f"No balance record found for portfolio {portfolio_id}")
                return None

            logger.info(
                f"Retrieved portfolio summary for {portfolio_id}: "
                f"{response.get('securityCount', 0)} securities, "
                f"cash balance: {response.get('cashBalance', '0')}"
            )
            return response

        except ExternalServiceError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting portfolio summary: {str(e)}")
            raise ExternalServiceError(
                f"Failed to retrieve portfolio summary: {str(e)}",
                service="portfolio-accounting",
            )

    async def _get_security_ticker(self, security_id: str) -> str:
        """
        Get ticker for a security with caching.

        Args:
            security_id: 24-character security ID

        Returns:
            Security ticker

        Raises:
            ExternalServiceError: If security not found or service error
        """
        # Check cache first
        cache_key = f"security:{security_id}"
        if cache_key in self._securities_cache:
            logger.debug(f"Cache hit for security {security_id}")
            return self._securities_cache[cache_key]

        try:
            logger.debug(f"Getting ticker for security {security_id}")

            if not self._security_client:
                raise ExternalServiceError(
                    "Security client not available", service="security"
                )

            security_data = await self._security_client.get_security(security_id)
            ticker = security_data.get("ticker")

            if not ticker:
                raise ExternalServiceError(
                    f"No ticker found for security {security_id}",
                    service="security",
                    status_code=500,
                )

            # Cache the ticker
            self._securities_cache[cache_key] = ticker
            logger.debug(f"Cached ticker {ticker} for security {security_id}")

            return ticker

        except ExternalServiceError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting security ticker: {str(e)}")
            raise ExternalServiceError(
                f"Failed to retrieve security ticker: {str(e)}",
                service="security",
                status_code=500,
            )

    async def _get_price_by_ticker(self, ticker: str) -> Decimal:
        """
        Get price for a ticker with caching.

        Args:
            ticker: Security ticker

        Returns:
            Security price as Decimal

        Raises:
            ExternalServiceError: If price not found or service error
        """
        # Check cache first
        cache_key = f"price:{ticker}"
        if cache_key in self._prices_cache:
            logger.debug(f"Cache hit for price {ticker}")
            return self._prices_cache[cache_key]

        try:
            logger.debug(f"Getting price for ticker {ticker}")

            if not self._pricing_client:
                raise ExternalServiceError(
                    "Pricing client not available", service="pricing"
                )

            response = await self._pricing_client._base_client._make_request(
                "GET", f"/api/v1/price/{ticker}"
            )

            close_price = response.get("close")
            if close_price is None:
                raise ExternalServiceError(
                    f"No price available for ticker {ticker}",
                    service="pricing",
                    status_code=500,
                )

            # Convert to Decimal and validate positive
            price = Decimal(str(close_price))
            if price <= 0:
                raise ExternalServiceError(
                    f"Invalid price for ticker {ticker}: {price}",
                    service="pricing",
                    status_code=500,
                )

            # Cache the price
            self._prices_cache[cache_key] = price
            logger.debug(f"Cached price {price} for ticker {ticker}")

            return price

        except ExternalServiceError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting price: {str(e)}")
            raise ExternalServiceError(
                f"Failed to retrieve price for {ticker}: {str(e)}",
                service="pricing",
                status_code=500,
            )

    async def get_portfolio_market_value(self, portfolio_id: str) -> Decimal:
        """
        Calculate total market value for a portfolio using real-time pricing.

        Market value = cashBalance + sum(netQuantity * currentPrice)

        Args:
            portfolio_id: The portfolio ID to calculate value for

        Returns:
            Total market value as Decimal (rounded to 3 decimal places)

        Raises:
            ExternalServiceError: If portfolio not found, missing data, or service error
        """
        try:
            logger.info(f"Calculating market value for portfolio {portfolio_id}")
            start_time = logger._get_time() if hasattr(logger, '_get_time') else None

            # Get portfolio summary
            summary = await self.get_portfolio_summary(portfolio_id)

            # Handle empty portfolio (no balance record)
            if not summary:
                logger.info(
                    f"No balance record for portfolio {portfolio_id}, returning zero"
                )
                return Decimal("0.000")

            # Extract and validate cash balance
            cash_balance_str = summary.get("cashBalance", "0")
            try:
                cash_balance = Decimal(str(cash_balance_str))
            except (ValueError, TypeError) as e:
                raise ExternalServiceError(
                    f"Invalid cash balance for portfolio {portfolio_id}: {cash_balance_str}",
                    service="portfolio-accounting",
                    status_code=500,
                )

            logger.debug(f"Portfolio {portfolio_id} cash balance: {cash_balance}")

            # Calculate security positions value
            securities_value = Decimal("0")
            securities = summary.get("securities", [])

            if securities:
                logger.debug(f"Calculating value for {len(securities)} securities")

                for security in securities:
                    security_id = security.get("securityId")
                    net_quantity_str = security.get("netQuantity", "0")

                    if not security_id:
                        logger.warning(
                            f"Security missing ID in portfolio {portfolio_id}"
                        )
                        continue

                    try:
                        net_quantity = Decimal(str(net_quantity_str))
                    except (ValueError, TypeError) as e:
                        raise ExternalServiceError(
                            f"Invalid net quantity for security {security_id}: {net_quantity_str}",
                            service="portfolio-accounting",
                            status_code=500,
                        )

                    # Skip securities with zero quantity
                    if net_quantity == 0:
                        logger.debug(
                            f"Skipping security {security_id} with zero quantity"
                        )
                        continue

                    # Get ticker for security
                    ticker = await self._get_security_ticker(security_id)

                    # Get current price
                    price = await self._get_price_by_ticker(ticker)

                    # Calculate position value
                    position_value = net_quantity * price
                    securities_value += position_value

                    logger.debug(
                        f"Security {security_id} ({ticker}): "
                        f"{net_quantity} * {price} = {position_value}"
                    )

            # Calculate total market value
            total_market_value = cash_balance + securities_value

            # Round to 3 decimal places
            rounded_value = total_market_value.quantize(
                Decimal('0.001'), rounding=ROUND_HALF_UP
            )

            if start_time:
                elapsed = logger._get_time() - start_time
                logger.info(
                    f"Portfolio {portfolio_id} market value calculation completed: "
                    f"{rounded_value} (cash: {cash_balance}, securities: {securities_value}) "
                    f"in {elapsed:.2f}s"
                )
            else:
                logger.info(
                    f"Portfolio {portfolio_id} market value: {rounded_value} "
                    f"(cash: {cash_balance}, securities: {securities_value})"
                )

            return rounded_value

        except ExternalServiceError:
            raise
        except Exception as e:
            logger.error(f"Error calculating portfolio market value: {str(e)}")
            raise ExternalServiceError(
                f"Failed to calculate portfolio market value: {str(e)}",
                service="portfolio-accounting",
                status_code=500,
            )

    async def get_portfolio_positions(self, portfolio_id: str) -> Dict[str, int]:
        """
        Get security positions (excluding cash) as quantity mapping.

        Args:
            portfolio_id: The portfolio ID to get positions for

        Returns:
            Dict mapping security IDs to net quantities: {"SEC123...": 100, ...}
            Note: Includes negative quantities for short positions

        Raises:
            ExternalServiceError: If portfolio not found or service error
        """
        try:
            logger.debug(f"Getting positions for portfolio {portfolio_id}")

            summary = await self.get_portfolio_summary(portfolio_id)

            if not summary:
                logger.debug(f"No summary data for portfolio {portfolio_id}")
                return {}

            positions = {}
            securities = summary.get("securities", [])

            for security in securities:
                security_id = security.get("securityId")
                net_quantity_str = security.get("netQuantity", "0")

                if not security_id:
                    continue

                try:
                    net_quantity = int(Decimal(str(net_quantity_str)))
                except (ValueError, TypeError):
                    logger.warning(
                        f"Invalid net quantity for security {security_id}: {net_quantity_str}"
                    )
                    continue

                # Include all positions (positive, negative, or zero)
                positions[security_id] = net_quantity

            logger.debug(
                f"Retrieved {len(positions)} security positions for portfolio {portfolio_id}"
            )
            return positions

        except ExternalServiceError:
            raise
        except Exception as e:
            logger.error(f"Error getting portfolio positions: {str(e)}")
            raise ExternalServiceError(
                f"Failed to retrieve portfolio positions: {str(e)}",
                service="portfolio-accounting",
            )

    async def get_cash_position(self, portfolio_id: str) -> Decimal:
        """
        Get cash position for a portfolio.

        Args:
            portfolio_id: The portfolio ID to get cash position for

        Returns:
            Cash balance as Decimal (may be negative for overdrawn accounts)

        Raises:
            ExternalServiceError: If portfolio not found or service error
        """
        try:
            logger.debug(f"Getting cash position for portfolio {portfolio_id}")

            summary = await self.get_portfolio_summary(portfolio_id)

            if not summary:
                logger.debug(f"No summary data for portfolio {portfolio_id}")
                return Decimal("0")

            cash_balance_str = summary.get("cashBalance", "0")
            try:
                cash_balance = Decimal(str(cash_balance_str))
            except (ValueError, TypeError) as e:
                raise ExternalServiceError(
                    f"Invalid cash balance for portfolio {portfolio_id}: {cash_balance_str}",
                    service="portfolio-accounting",
                    status_code=500,
                )

            logger.debug(f"Portfolio {portfolio_id} cash position: {cash_balance}")
            return cash_balance

        except ExternalServiceError:
            raise
        except Exception as e:
            logger.error(f"Error getting cash position: {str(e)}")
            raise ExternalServiceError(
                f"Failed to retrieve cash position: {str(e)}",
                service="portfolio-accounting",
            )

    # Legacy method for backward compatibility
    async def get_portfolio_balances(self, portfolio_id: str) -> List[Dict]:
        """
        Legacy method for backward compatibility.

        Converts new summary format to old balances format.
        """
        logger.warning(
            f"get_portfolio_balances is deprecated, use get_portfolio_summary instead"
        )

        summary = await self.get_portfolio_summary(portfolio_id)
        if not summary:
            return []

        balances = []

        # Add cash balance
        cash_balance_str = summary.get("cashBalance", "0")
        try:
            cash_balance = Decimal(str(cash_balance_str))
            balances.append({"cash": True, "quantity": 1, "marketValue": cash_balance})
        except (ValueError, TypeError):
            pass

        # Add security positions with calculated market values
        securities = summary.get("securities", [])
        for security in securities:
            security_id = security.get("securityId")
            net_quantity_str = security.get("netQuantity", "0")

            if not security_id:
                continue

            try:
                net_quantity = int(Decimal(str(net_quantity_str)))
                if net_quantity == 0:
                    continue

                # Calculate market value (this will use caching)
                ticker = await self._get_security_ticker(security_id)
                price = await self._get_price_by_ticker(ticker)
                market_value = Decimal(str(net_quantity)) * price

                balances.append(
                    {
                        "securityId": security_id,
                        "quantity": net_quantity,
                        "marketValue": market_value,
                    }
                )
            except Exception as e:
                logger.warning(f"Error processing security {security_id}: {e}")
                continue

        return balances

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
