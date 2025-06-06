"""
Security Service client for security metadata and validation.

This module provides integration with the Security Service to:
- Retrieve security metadata and information
- Validate security existence and status
- Support batch security validation
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


class SecurityServiceClient(ExternalServiceClientProtocol):
    """
    Client for Security Service integration.

    Provides access to security metadata including:
    - Security information and status
    - Security validation for model positions
    - Batch security operations
    """

    def __init__(self, base_url: str = None, timeout: float = None):
        """
        Initialize the Security Service client.

        Args:
            base_url: Base URL of the Security Service
            timeout: Request timeout in seconds
        """
        settings = get_settings()

        self.base_url = base_url or "http://globeco-security-service:8000"
        self.timeout = timeout or settings.external_service_timeout

        self._base_client = BaseServiceClient(
            base_url=self.base_url,
            service_name="security",
            timeout=self.timeout,
            max_retries=3,
        )

    async def get_security(self, security_id: str) -> Dict:
        """
        Retrieve security metadata.

        Args:
            security_id: The 24-character security ID to get information for

        Returns:
            Dict with security information: {
                "id": "STOCK1234567890123456789",
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "type": "STOCK|BOND|ETF|OPTION",
                "sector": "TECHNOLOGY",
                "status": "ACTIVE|INACTIVE|DELISTED",
                "exchange": "NASDAQ",
                "created_at": "2024-01-01T00:00:00Z"
            }

        Raises:
            ExternalServiceError: If security not found or service error
        """
        try:
            logger.debug(f"Getting security metadata for {security_id}")

            response = await self._base_client._make_request(
                "GET", f"/api/v1/security/{security_id}"
            )

            logger.info(
                f"Retrieved security metadata for {security_id}: {response.get('ticker', 'Unknown')}"
            )
            return response

        except ExternalServiceError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting security metadata: {str(e)}")
            raise ExternalServiceError(
                f"Failed to retrieve security metadata: {str(e)}", service="security"
            )

    async def validate_securities(
        self, security_ids: List[str]
    ) -> Dict[str, List[str]]:
        """
        Validate existence and status of multiple securities.

        Args:
            security_ids: List of 24-character security IDs to validate

        Returns:
            Dict with validation results: {
                "valid": ["STOCK1234567890123456789", "BOND1111111111111111111A"],
                "invalid": ["MISSING123456789012345"],
                "inactive": ["DELISTED123456789012345"]
            }

        Raises:
            ExternalServiceError: If service error occurs
        """
        try:
            logger.debug(f"Validating {len(security_ids)} securities")

            response = await self._base_client._make_request(
                "POST",
                "/api/v1/securities/validate",
                json={"securityIds": security_ids},
            )

            valid_count = len(response.get("valid", []))
            invalid_count = len(response.get("invalid", []))
            inactive_count = len(response.get("inactive", []))

            logger.info(
                f"Security validation completed: {valid_count} valid, "
                f"{invalid_count} invalid, {inactive_count} inactive"
            )

            return response

        except ExternalServiceError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error validating securities: {str(e)}")
            raise ExternalServiceError(
                f"Failed to validate securities: {str(e)}", service="security"
            )

    async def get_security_status(self, security_id: str) -> str:
        """
        Get the current status of a security.

        Args:
            security_id: The security ID to check status for

        Returns:
            Security status: "ACTIVE", "INACTIVE", or "DELISTED"

        Raises:
            ExternalServiceError: If security not found or service error
        """
        try:
            security_data = await self.get_security(security_id)
            status = security_data.get("status", "UNKNOWN")

            logger.debug(f"Security {security_id} status: {status}")
            return status

        except Exception as e:
            logger.error(f"Error getting security status: {str(e)}")
            raise ExternalServiceError(
                f"Failed to retrieve security status: {str(e)}", service="security"
            )

    async def is_security_active(self, security_id: str) -> bool:
        """
        Check if a security is in active status.

        Args:
            security_id: The security ID to check

        Returns:
            bool: True if security is active, False otherwise

        Raises:
            ExternalServiceError: If security not found or service error
        """
        try:
            status = await self.get_security_status(security_id)
            is_active = status == "ACTIVE"

            logger.debug(f"Security {security_id} active status: {is_active}")
            return is_active

        except Exception as e:
            logger.error(f"Error checking security active status: {str(e)}")
            raise ExternalServiceError(
                f"Failed to check security active status: {str(e)}", service="security"
            )

    async def get_securities_by_type(self, security_type: str) -> List[Dict]:
        """
        Retrieve securities by type.

        Args:
            security_type: Security type filter ("STOCK", "BOND", "ETF", "OPTION")

        Returns:
            List of security metadata dicts

        Raises:
            ExternalServiceError: If service error occurs
        """
        try:
            logger.debug(f"Getting securities by type: {security_type}")

            response = await self._base_client._make_request(
                "GET", f"/api/v1/securities?type={security_type}"
            )

            securities = response.get("securities", [])
            logger.info(
                f"Retrieved {len(securities)} securities of type {security_type}"
            )

            return securities

        except ExternalServiceError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting securities by type: {str(e)}")
            raise ExternalServiceError(
                f"Failed to retrieve securities by type: {str(e)}", service="security"
            )

    async def get_securities_by_sector(self, sector: str) -> List[Dict]:
        """
        Retrieve securities by sector.

        Args:
            sector: Sector filter (e.g., "TECHNOLOGY", "HEALTHCARE", "FINANCIAL")

        Returns:
            List of security metadata dicts

        Raises:
            ExternalServiceError: If service error occurs
        """
        try:
            logger.debug(f"Getting securities by sector: {sector}")

            response = await self._base_client._make_request(
                "GET", f"/api/v1/securities?sector={sector}"
            )

            securities = response.get("securities", [])
            logger.info(f"Retrieved {len(securities)} securities in sector {sector}")

            return securities

        except ExternalServiceError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting securities by sector: {str(e)}")
            raise ExternalServiceError(
                f"Failed to retrieve securities by sector: {str(e)}", service="security"
            )

    async def search_securities(self, query: str, limit: int = 50) -> List[Dict]:
        """
        Search securities by symbol or name.

        Args:
            query: Search query (symbol or name)
            limit: Maximum number of results to return

        Returns:
            List of security metadata dicts matching the search

        Raises:
            ExternalServiceError: If service error occurs
        """
        try:
            logger.debug(f"Searching securities for query: {query}")

            response = await self._base_client._make_request(
                "GET", f"/api/v1/securities/search?q={query}&limit={limit}"
            )

            securities = response.get("securities", [])
            logger.info(f"Found {len(securities)} securities for query '{query}'")

            return securities

        except ExternalServiceError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error searching securities: {str(e)}")
            raise ExternalServiceError(
                f"Failed to search securities: {str(e)}", service="security"
            )

    async def health_check(self) -> bool:
        """
        Check if the Security Service is healthy.

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
