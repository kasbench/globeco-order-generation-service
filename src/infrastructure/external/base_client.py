"""
Base HTTP client for external service integration with circuit breaker pattern.

This module provides a resilient HTTP client with:
- Circuit breaker pattern for fault tolerance
- Retry logic with exponential backoff
- Timeout handling and error classification
- Health checks and service monitoring
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, Optional

from httpx import AsyncClient, HTTPStatusError, RequestError, TimeoutException

from src.config import get_settings
from src.core.exceptions import (
    ExternalServiceError,
    ServiceTimeoutError,
    ServiceUnavailableError,
)

logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    """Circuit breaker states for fault tolerance."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class BaseServiceClient:
    """
    Base HTTP client with circuit breaker pattern and retry logic.

    Provides resilient external service integration with:
    - Automatic retries with exponential backoff
    - Circuit breaker for failure detection and recovery
    - Timeout handling and error classification
    - Health check capabilities
    """

    def __init__(
        self,
        base_url: str,
        service_name: str,
        timeout: float = 10.0,
        max_retries: int = 3,
        circuit_breaker_timeout: float = 60.0,
        failure_threshold: int = 5,
    ):
        """
        Initialize the base service client.

        Args:
            base_url: Base URL of the external service
            service_name: Name of the service for logging and error handling
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            circuit_breaker_timeout: Time to wait before attempting recovery (seconds)
            failure_threshold: Number of consecutive failures to open circuit breaker
        """
        self.base_url = base_url.rstrip('/')
        self.service_name = service_name
        self.timeout = timeout
        self.max_retries = max_retries
        self.circuit_breaker_timeout = circuit_breaker_timeout
        self.failure_threshold = failure_threshold

        # Circuit breaker state
        self._circuit_breaker_state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._circuit_breaker_open_time: Optional[float] = None

        # HTTP client
        self._client: Optional[AsyncClient] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self._client = AsyncClient(base_url=self.base_url)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()

    def _get_client(self) -> AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = AsyncClient(base_url=self.base_url)
        return self._client

    async def _make_request(
        self, method: str, endpoint: str, **kwargs
    ) -> Dict[str, Any]:
        """
        Make HTTP request with circuit breaker and retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint to call
            **kwargs: Additional arguments for the HTTP request

        Returns:
            Dict containing the JSON response

        Raises:
            ServiceUnavailableError: If circuit breaker is open
            ServiceTimeoutError: If request times out after retries
            ExternalServiceError: For other HTTP errors
        """
        # Check circuit breaker state
        if self._circuit_breaker_state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self._circuit_breaker_state = CircuitBreakerState.HALF_OPEN
                logger.info(
                    f"Circuit breaker for {self.service_name} moved to HALF_OPEN"
                )
            else:
                raise ServiceUnavailableError(
                    f"Circuit breaker is OPEN for {self.service_name}",
                    service=self.service_name,
                )

        # Set default timeout
        kwargs.setdefault('timeout', self.timeout)

        last_exception: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                client = self._get_client()

                # Make the actual HTTP request
                if method.upper() == "GET":
                    response = await client.get(endpoint, **kwargs)
                elif method.upper() == "POST":
                    response = await client.post(endpoint, **kwargs)
                elif method.upper() == "PUT":
                    response = await client.put(endpoint, **kwargs)
                elif method.upper() == "DELETE":
                    response = await client.delete(endpoint, **kwargs)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                # Check if response is successful
                response.raise_for_status()

                # Success - reset circuit breaker
                self._on_success()

                return response.json()

            except HTTPStatusError as e:
                last_exception = e

                # Don't retry client errors (4xx)
                if 400 <= e.response.status_code < 500:
                    self._on_failure()
                    raise ExternalServiceError(
                        f"HTTP {e.response.status_code}: {e.response.text}",
                        service=self.service_name,
                        status_code=e.response.status_code,
                    )

                # Retry server errors (5xx)
                logger.warning(
                    f"HTTP error on attempt {attempt + 1}/{self.max_retries} "
                    f"for {self.service_name}: {e.response.status_code}"
                )

            except (TimeoutException, RequestError) as e:
                last_exception = e
                logger.warning(
                    f"Request error on attempt {attempt + 1}/{self.max_retries} "
                    f"for {self.service_name}: {str(e)}"
                )

            # Wait before retry (exponential backoff)
            if attempt < self.max_retries - 1:
                wait_time = 2**attempt  # 1s, 2s, 4s, ...
                logger.debug(
                    f"Waiting {wait_time}s before retry for {self.service_name}"
                )
                await asyncio.sleep(wait_time)

        # All retries exhausted
        self._on_failure()

        if isinstance(last_exception, (TimeoutException, RequestError)):
            raise ServiceTimeoutError(
                f"Request to {self.service_name} timed out after {self.max_retries} attempts",
                service=self.service_name,
            )
        elif isinstance(last_exception, HTTPStatusError):
            raise ExternalServiceError(
                f"HTTP error for {self.service_name}: {last_exception.response.status_code}",
                service=self.service_name,
                status_code=last_exception.response.status_code,
            )
        else:
            raise ExternalServiceError(
                f"Unexpected error for {self.service_name}: {str(last_exception)}",
                service=self.service_name,
            )

    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt to reset."""
        if self._circuit_breaker_open_time is None:
            return False

        current_time = asyncio.get_event_loop().time()
        return (
            current_time - self._circuit_breaker_open_time
            >= self.circuit_breaker_timeout
        )

    def _on_success(self):
        """Handle successful request - reset circuit breaker."""
        if self._circuit_breaker_state in [
            CircuitBreakerState.HALF_OPEN,
            CircuitBreakerState.OPEN,
        ]:
            logger.info(f"Circuit breaker for {self.service_name} reset to CLOSED")

        self._circuit_breaker_state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._circuit_breaker_open_time = None

    def _on_failure(self):
        """Handle failed request - update circuit breaker state."""
        self._failure_count += 1

        if self._circuit_breaker_state == CircuitBreakerState.HALF_OPEN:
            # Failure in half-open state - reopen circuit breaker
            self._circuit_breaker_state = CircuitBreakerState.OPEN
            self._circuit_breaker_open_time = asyncio.get_event_loop().time()
            logger.warning(
                f"Circuit breaker for {self.service_name} reopened after failure in HALF_OPEN"
            )

        elif (
            self._circuit_breaker_state == CircuitBreakerState.CLOSED
            and self._failure_count >= self.failure_threshold
        ):
            # Too many failures - open circuit breaker
            self._circuit_breaker_state = CircuitBreakerState.OPEN
            self._circuit_breaker_open_time = asyncio.get_event_loop().time()
            logger.error(
                f"Circuit breaker for {self.service_name} opened after "
                f"{self._failure_count} consecutive failures"
            )

    async def health_check(self) -> bool:
        """
        Perform health check on the service.

        Returns:
            bool: True if service is healthy, False otherwise
        """
        try:
            client = self._get_client()
            response = await client.get("/health", timeout=self.timeout)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Health check failed for {self.service_name}: {str(e)}")
            return False

    @property
    def circuit_breaker_status(self) -> Dict[str, Any]:
        """Get current circuit breaker status."""
        return {
            "state": self._circuit_breaker_state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "open_time": self._circuit_breaker_open_time,
            "service": self.service_name,
        }


class ExternalServiceClientProtocol(ABC):
    """Protocol for external service clients."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the external service is healthy."""
        pass
