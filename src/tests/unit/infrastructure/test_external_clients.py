"""
Tests for external service clients with circuit breaker pattern and resilience.

This module tests the external service integration layer, including:
- HTTP client implementations for all external services
- Circuit breaker pattern for fault tolerance
- Retry logic with exponential backoff
- Timeout handling and error classification
- Service failure simulation and recovery
"""

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient, HTTPStatusError, RequestError, TimeoutException

from src.core.exceptions import (
    ExternalServiceError,
    ServiceTimeoutError,
    ServiceUnavailableError,
)
from src.infrastructure.external.base_client import (
    BaseServiceClient,
    CircuitBreakerState,
)
from src.infrastructure.external.portfolio_accounting_client import (
    PortfolioAccountingClient,
)
from src.infrastructure.external.portfolio_client import PortfolioClient
from src.infrastructure.external.pricing_client import PricingServiceClient
from src.infrastructure.external.security_client import SecurityServiceClient


@pytest.mark.unit
class TestBaseServiceClient:
    """Test the base service client with circuit breaker and retry logic."""

    @pytest_asyncio.fixture
    async def mock_client(self):
        """Create a mock HTTP client for testing."""
        return AsyncMock(spec=AsyncClient)

    @pytest_asyncio.fixture
    async def base_client(self, mock_client):
        """Create a base service client for testing."""
        client = BaseServiceClient(
            base_url="http://test-service:8000",
            service_name="test-service",
            timeout=5.0,
            max_retries=3,
        )
        client._client = mock_client
        return client

    @pytest.mark.asyncio
    async def test_successful_request(self, base_client, mock_client):
        """Test successful HTTP request."""
        # Arrange
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value={"status": "success", "data": []})
        mock_client.get.return_value = mock_response

        # Act
        result = await base_client._make_request("GET", "/test")

        # Assert
        assert result == {"status": "success", "data": []}
        mock_client.get.assert_called_once_with("/test", timeout=5.0)

    @pytest.mark.asyncio
    async def test_request_with_retry_on_timeout(self, base_client, mock_client):
        """Test request retry on timeout exception."""
        # Arrange - First two calls timeout, third succeeds
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value={"data": "success"})

        mock_client.get.side_effect = [
            TimeoutException("Connection timeout"),
            TimeoutException("Connection timeout"),
            mock_response,
        ]

        # Act
        result = await base_client._make_request("GET", "/test")

        # Assert
        assert result == {"data": "success"}
        assert mock_client.get.call_count == 3

    @pytest.mark.asyncio
    async def test_request_with_retry_on_503_error(self, base_client, mock_client):
        """Test request retry on 503 Service Unavailable."""
        # Arrange - First call returns 503, second succeeds
        mock_error_response = AsyncMock()
        mock_error_response.status_code = 503
        error = HTTPStatusError(
            "Service Unavailable", request=AsyncMock(), response=mock_error_response
        )

        mock_success_response = AsyncMock()
        mock_success_response.status_code = 200
        mock_success_response.json = Mock(return_value={"data": "recovered"})

        mock_client.get.side_effect = [error, mock_success_response]

        # Act
        result = await base_client._make_request("GET", "/test")

        # Assert
        assert result == {"data": "recovered"}
        assert mock_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_request_exhausts_retries_and_fails(self, base_client, mock_client):
        """Test request failure after exhausting all retries."""
        # Arrange - All retries fail with timeout
        mock_client.get.side_effect = TimeoutException("Persistent timeout")

        # Act & Assert
        with pytest.raises(ServiceTimeoutError, match="after 3 attempts"):
            await base_client._make_request("GET", "/test")

        assert mock_client.get.call_count == 3

    @pytest.mark.asyncio
    async def test_request_with_400_error_no_retry(self, base_client, mock_client):
        """Test that 400 errors are not retried."""
        # Arrange
        mock_response = AsyncMock()
        mock_response.status_code = 400
        error = HTTPStatusError(
            "Bad Request", request=AsyncMock(), response=mock_response
        )
        mock_client.get.side_effect = error

        # Act & Assert
        with pytest.raises(ExternalServiceError, match="HTTP 400"):
            await base_client._make_request("GET", "/test")

        # Should only be called once (no retries for 400)
        assert mock_client.get.call_count == 1

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_on_consecutive_failures(
        self, base_client, mock_client
    ):
        """Test circuit breaker opens after consecutive failures."""
        # Arrange - All requests fail
        mock_client.get.side_effect = TimeoutException("Service down")

        # Act - Make enough failed requests to open circuit breaker
        for _ in range(5):  # failure_threshold = 5
            try:
                await base_client._make_request("GET", "/test")
            except ServiceTimeoutError:
                pass

        # Circuit breaker should now be open
        assert base_client._circuit_breaker_state == CircuitBreakerState.OPEN

        # Next request should fail immediately without HTTP call
        with pytest.raises(ServiceUnavailableError, match="Circuit breaker is OPEN"):
            await base_client._make_request("GET", "/test")

    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_recovery(self, base_client, mock_client):
        """Test circuit breaker recovery through half-open state."""
        # Arrange - Open the circuit breaker first
        base_client._circuit_breaker_state = CircuitBreakerState.OPEN
        base_client._circuit_breaker_open_time = (
            asyncio.get_event_loop().time() - 61
        )  # 1 minute ago

        # Mock successful response for recovery
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value={"status": "recovered"})
        mock_client.get.return_value = mock_response

        # Act
        result = await base_client._make_request("GET", "/test")

        # Assert
        assert result == {"status": "recovered"}
        assert base_client._circuit_breaker_state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_exponential_backoff_delay(self, base_client, mock_client):
        """Test exponential backoff between retry attempts."""
        # Arrange
        mock_client.get.side_effect = [
            TimeoutException("Timeout 1"),
            TimeoutException("Timeout 2"),
            TimeoutException("Timeout 3"),  # Add third timeout to exhaust retries
        ]

        start_time = asyncio.get_event_loop().time()

        # Act
        with pytest.raises(ServiceTimeoutError):
            await base_client._make_request("GET", "/test")

        # Assert
        end_time = asyncio.get_event_loop().time()
        # Should have taken at least: 1s (first backoff) + 2s (second backoff) = 3s
        elapsed_time = end_time - start_time
        assert (
            elapsed_time >= 3.0
        ), f"Expected at least 3s for backoff, got {elapsed_time:.2f}s"
        assert mock_client.get.call_count == 3

    @pytest.mark.asyncio
    async def test_health_check_success(self, base_client, mock_client):
        """Test successful health check."""
        # Arrange
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value={"status": "healthy"})
        mock_client.get.return_value = mock_response

        # Act
        is_healthy = await base_client.health_check()

        # Assert
        assert is_healthy is True
        mock_client.get.assert_called_once_with("/health", timeout=5.0)

    @pytest.mark.asyncio
    async def test_health_check_failure(self, base_client, mock_client):
        """Test failed health check."""
        # Arrange
        mock_client.get.side_effect = TimeoutException("Health check timeout")

        # Act
        is_healthy = await base_client.health_check()

        # Assert
        assert is_healthy is False


@pytest.mark.unit
class TestPortfolioAccountingClient:
    """Test the Portfolio Accounting Service client."""

    @pytest_asyncio.fixture
    async def mock_base_client(self):
        """Create a mock base client for testing."""
        return AsyncMock(spec=BaseServiceClient)

    @pytest_asyncio.fixture
    async def mock_security_client(self):
        """Create a mock security client for testing."""
        mock = AsyncMock()
        mock.get_security.return_value = {"ticker": "AAPL"}
        return mock

    @pytest_asyncio.fixture
    async def mock_pricing_client(self):
        """Create a mock pricing client for testing."""
        mock = AsyncMock()
        mock._base_client = AsyncMock()
        mock._base_client._make_request.return_value = {"close": 150.0}
        return mock

    @pytest_asyncio.fixture
    async def portfolio_accounting_client(
        self, mock_base_client, mock_security_client, mock_pricing_client
    ):
        """Create a portfolio accounting client for testing."""
        client = PortfolioAccountingClient(
            base_url="http://portfolio-accounting:8087",
            timeout=10.0,
            security_client=mock_security_client,
            pricing_client=mock_pricing_client,
        )
        client._base_client = mock_base_client
        return client

    @pytest.mark.asyncio
    async def test_get_portfolio_summary_success(
        self, portfolio_accounting_client, mock_base_client
    ):
        """Test successful portfolio summary retrieval."""
        # Arrange
        portfolio_id = "683b6d88a29ee10e8b499643"
        mock_response = {
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
                    "lastUpdated": "2025-06-06T12:16:50.080869Z",
                }
            ],
        }
        mock_base_client._make_request.return_value = mock_response

        # Act
        result = await portfolio_accounting_client.get_portfolio_summary(portfolio_id)

        # Assert
        assert result["portfolioId"] == "683b6d88a29ee10e8b499643"
        assert result["cashBalance"] == "3356336"
        assert result["securityCount"] == 1
        assert len(result["securities"]) == 1
        assert result["securities"][0]["securityId"] == "683b69d420f302c879a5fef0"
        assert result["securities"][0]["netQuantity"] == "100"

        mock_base_client._make_request.assert_called_once_with(
            "GET", f"/api/v1/portfolios/{portfolio_id}/summary"
        )

    @pytest.mark.asyncio
    async def test_get_portfolio_summary_not_found(
        self, portfolio_accounting_client, mock_base_client
    ):
        """Test portfolio summary retrieval for non-existent portfolio."""
        # Arrange
        portfolio_id = "non-existent-portfolio"
        mock_base_client._make_request.side_effect = ExternalServiceError(
            "Portfolio not found", service="portfolio-accounting", status_code=404
        )

        # Act & Assert
        with pytest.raises(ExternalServiceError, match="Portfolio not found"):
            await portfolio_accounting_client.get_portfolio_summary(portfolio_id)

    @pytest.mark.asyncio
    async def test_get_portfolio_market_value_success(
        self,
        portfolio_accounting_client,
        mock_base_client,
        mock_security_client,
        mock_pricing_client,
    ):
        """Test successful portfolio market value calculation using new method."""
        # Arrange
        portfolio_id = "683b6d88a29ee10e8b499643"
        mock_summary = {
            "portfolioId": "683b6d88a29ee10e8b499643",
            "cashBalance": "5000",
            "securityCount": 1,
            "securities": [
                {"securityId": "683b69d420f302c879a5fef0", "netQuantity": "100"}
            ],
        }
        mock_base_client._make_request.return_value = mock_summary

        # Act
        result = await portfolio_accounting_client.get_portfolio_market_value(
            portfolio_id
        )

        # Assert - Cash (5000) + Securities (100 * 150.0) = 20000.000
        assert result == Decimal("20000.000")

        # Verify external service calls
        mock_security_client.get_security.assert_called_once_with(
            "683b69d420f302c879a5fef0"
        )
        mock_pricing_client._base_client._make_request.assert_called_once_with(
            "GET", "/api/v1/price/AAPL"
        )

    @pytest.mark.asyncio
    async def test_get_portfolio_market_value_cash_only(
        self, portfolio_accounting_client, mock_base_client
    ):
        """Test market value calculation for cash-only portfolio."""
        # Arrange
        portfolio_id = "683b6d88a29ee10e8b499643"
        mock_summary = {
            "portfolioId": "683b6d88a29ee10e8b499643",
            "cashBalance": "15000",
            "securityCount": 0,
            "securities": [],
        }
        mock_base_client._make_request.return_value = mock_summary

        # Act
        result = await portfolio_accounting_client.get_portfolio_market_value(
            portfolio_id
        )

        # Assert - Only cash balance
        assert result == Decimal("15000.000")

    @pytest.mark.asyncio
    async def test_get_portfolio_market_value_empty_portfolio(
        self, portfolio_accounting_client, mock_base_client
    ):
        """Test market value calculation for empty portfolio."""
        # Arrange
        portfolio_id = "683b6d88a29ee10e8b499643"
        mock_base_client._make_request.return_value = None  # No balance record

        # Act
        result = await portfolio_accounting_client.get_portfolio_market_value(
            portfolio_id
        )

        # Assert - Zero for empty portfolio
        assert result == Decimal("0.000")

    @pytest.mark.asyncio
    async def test_get_portfolio_market_value_negative_cash(
        self, portfolio_accounting_client, mock_base_client
    ):
        """Test market value calculation with negative cash (overdrawn account)."""
        # Arrange
        portfolio_id = "683b6d88a29ee10e8b499643"
        mock_summary = {
            "portfolioId": "683b6d88a29ee10e8b499643",
            "cashBalance": "-1000",  # Overdrawn account
            "securityCount": 1,
            "securities": [
                {"securityId": "683b69d420f302c879a5fef0", "netQuantity": "50"}
            ],
        }
        mock_base_client._make_request.return_value = mock_summary

        # Act
        result = await portfolio_accounting_client.get_portfolio_market_value(
            portfolio_id
        )

        # Assert - Negative cash (-1000) + Securities (50 * 150.0) = 6500.000
        assert result == Decimal("6500.000")

    @pytest.mark.asyncio
    async def test_get_portfolio_market_value_short_position(
        self, portfolio_accounting_client, mock_base_client
    ):
        """Test market value calculation with short position (negative quantity)."""
        # Arrange
        portfolio_id = "683b6d88a29ee10e8b499643"
        mock_summary = {
            "portfolioId": "683b6d88a29ee10e8b499643",
            "cashBalance": "10000",
            "securityCount": 1,
            "securities": [
                {
                    "securityId": "683b69d420f302c879a5fef0",
                    "netQuantity": "-20",  # Short position
                }
            ],
        }
        mock_base_client._make_request.return_value = mock_summary

        # Act
        result = await portfolio_accounting_client.get_portfolio_market_value(
            portfolio_id
        )

        # Assert - Cash (10000) + Securities (-20 * 150.0) = 7000.000
        assert result == Decimal("7000.000")

    @pytest.mark.asyncio
    async def test_get_portfolio_market_value_security_not_found(
        self, portfolio_accounting_client, mock_base_client, mock_security_client
    ):
        """Test market value calculation when security is not found."""
        # Arrange
        # Clear cache to ensure fresh calls
        portfolio_accounting_client._securities_cache.clear()
        portfolio_accounting_client._prices_cache.clear()

        portfolio_id = "683b6d88a29ee10e8b499643"
        mock_summary = {
            "portfolioId": "683b6d88a29ee10e8b499643",
            "cashBalance": "5000",
            "securityCount": 1,
            "securities": [
                {"securityId": "683b69d420f302c879a5fef0", "netQuantity": "100"}
            ],
        }
        mock_base_client._make_request.return_value = mock_summary

        # Reset the mock to clear any previous configuration
        mock_security_client.reset_mock()
        mock_security_client.get_security.side_effect = ExternalServiceError(
            "Security not found", service="security", status_code=404
        )

        # Act & Assert - Should raise ExternalServiceError per requirement
        with pytest.raises(ExternalServiceError, match="Security not found"):
            await portfolio_accounting_client.get_portfolio_market_value(portfolio_id)

    @pytest.mark.asyncio
    async def test_get_portfolio_market_value_price_not_available(
        self, portfolio_accounting_client, mock_base_client, mock_pricing_client
    ):
        """Test market value calculation when price is not available."""
        # Arrange
        # Clear cache to ensure fresh calls
        portfolio_accounting_client._securities_cache.clear()
        portfolio_accounting_client._prices_cache.clear()

        portfolio_id = "683b6d88a29ee10e8b499643"
        mock_summary = {
            "portfolioId": "683b6d88a29ee10e8b499643",
            "cashBalance": "5000",
            "securityCount": 1,
            "securities": [
                {"securityId": "683b69d420f302c879a5fef0", "netQuantity": "100"}
            ],
        }
        mock_base_client._make_request.return_value = mock_summary

        # Reset pricing client mock to clear any previous configuration
        mock_pricing_client.reset_mock()
        mock_pricing_client._base_client.reset_mock()
        mock_pricing_client._base_client._make_request.return_value = {"close": None}

        # Act & Assert - Should raise ExternalServiceError per requirement
        with pytest.raises(ExternalServiceError, match="No price available"):
            await portfolio_accounting_client.get_portfolio_market_value(portfolio_id)

    @pytest.mark.asyncio
    async def test_get_portfolio_positions_success(
        self, portfolio_accounting_client, mock_base_client
    ):
        """Test successful portfolio positions retrieval."""
        # Arrange
        portfolio_id = "683b6d88a29ee10e8b499643"
        mock_summary = {
            "portfolioId": "683b6d88a29ee10e8b499643",
            "cashBalance": "5000",
            "securityCount": 2,
            "securities": [
                {"securityId": "SEC1", "netQuantity": "100"},
                {"securityId": "SEC2", "netQuantity": "-50"},  # Short position
                {"securityId": "SEC3", "netQuantity": "0"},  # Zero position
            ],
        }
        mock_base_client._make_request.return_value = mock_summary

        # Act
        result = await portfolio_accounting_client.get_portfolio_positions(portfolio_id)

        # Assert - Should include all positions including negative and zero
        assert result == {"SEC1": 100, "SEC2": -50, "SEC3": 0}

    @pytest.mark.asyncio
    async def test_get_cash_position_success(
        self, portfolio_accounting_client, mock_base_client
    ):
        """Test successful cash position retrieval."""
        # Arrange
        portfolio_id = "683b6d88a29ee10e8b499643"
        mock_summary = {
            "portfolioId": "683b6d88a29ee10e8b499643",
            "cashBalance": "7500.50",
            "securityCount": 0,
            "securities": [],
        }
        mock_base_client._make_request.return_value = mock_summary

        # Act
        result = await portfolio_accounting_client.get_cash_position(portfolio_id)

        # Assert
        assert result == Decimal("7500.50")

    @pytest.mark.asyncio
    async def test_get_portfolio_balances_legacy_method(
        self,
        portfolio_accounting_client,
        mock_base_client,
        mock_security_client,
        mock_pricing_client,
    ):
        """Test the legacy get_portfolio_balances method for backward compatibility."""
        # Arrange
        portfolio_id = "683b6d88a29ee10e8b499643"
        mock_summary = {
            "portfolioId": "683b6d88a29ee10e8b499643",
            "cashBalance": "2500",
            "securityCount": 1,
            "securities": [
                {"securityId": "683b69d420f302c879a5fef0", "netQuantity": "100"}
            ],
        }
        mock_base_client._make_request.return_value = mock_summary

        # Act
        result = await portfolio_accounting_client.get_portfolio_balances(portfolio_id)

        # Assert - Should convert to legacy format
        assert len(result) == 2  # Cash + 1 security

        # Check cash entry
        cash_entry = next(entry for entry in result if entry.get("cash", False))
        assert cash_entry["marketValue"] == Decimal("2500")

        # Check security entry
        security_entry = next(entry for entry in result if "securityId" in entry)
        assert security_entry["securityId"] == "683b69d420f302c879a5fef0"
        assert security_entry["quantity"] == 100
        assert security_entry["marketValue"] == Decimal("15000")  # 100 * 150.0

    @pytest.mark.asyncio
    async def test_caching_functionality(
        self, portfolio_accounting_client, mock_security_client, mock_pricing_client
    ):
        """Test that caching works for securities and prices."""
        # Clear any existing cache
        portfolio_accounting_client._securities_cache.clear()
        portfolio_accounting_client._prices_cache.clear()

        # Test security caching
        security_id = "683b69d420f302c879a5fef0"

        # First call - should hit service
        ticker1 = await portfolio_accounting_client._get_security_ticker(security_id)
        assert ticker1 == "AAPL"
        mock_security_client.get_security.assert_called_once_with(security_id)

        # Second call - should hit cache
        mock_security_client.reset_mock()
        ticker2 = await portfolio_accounting_client._get_security_ticker(security_id)
        assert ticker2 == "AAPL"
        mock_security_client.get_security.assert_not_called()

        # Test price caching
        ticker = "AAPL"

        # First call - should hit service
        price1 = await portfolio_accounting_client._get_price_by_ticker(ticker)
        assert price1 == Decimal("150.0")
        mock_pricing_client._base_client._make_request.assert_called_once_with(
            "GET", "/api/v1/price/AAPL"
        )

        # Second call - should hit cache
        mock_pricing_client._base_client.reset_mock()
        price2 = await portfolio_accounting_client._get_price_by_ticker(ticker)
        assert price2 == Decimal("150.0")
        mock_pricing_client._base_client._make_request.assert_not_called()


@pytest.mark.unit
class TestPricingServiceClient:
    """Test the Pricing Service client."""

    @pytest_asyncio.fixture
    async def mock_base_client(self):
        """Create a mock base client for testing."""
        return AsyncMock(spec=BaseServiceClient)

    @pytest_asyncio.fixture
    async def mock_security_client(self):
        """Create a mock security client for testing."""
        from src.infrastructure.external.security_client import SecurityServiceClient

        return AsyncMock(spec=SecurityServiceClient)

    @pytest_asyncio.fixture
    async def pricing_client(self, mock_base_client, mock_security_client):
        """Create a pricing service client for testing."""
        client = PricingServiceClient(
            base_url="http://pricing-service:8083",
            timeout=10.0,
            security_client=mock_security_client,
        )
        client._base_client = mock_base_client
        client._test_mode = True  # Enable test mode for backwards compatibility
        return client

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="Test expects future batch pricing API (POST /api/v1/prices/batch) that doesn't exist yet"
    )
    async def test_get_security_prices_success(self, pricing_client, mock_base_client):
        """Test successful security price retrieval."""
        # Arrange
        security_ids = ["STOCK1234567890123456789", "BOND1111111111111111111A"]
        mock_response = {
            "prices": {
                "STOCK1234567890123456789": "100.50",
                "BOND1111111111111111111A": "150.75",
            }
        }
        mock_base_client._make_request.return_value = mock_response

        # Act
        result = await pricing_client.get_security_prices(security_ids)

        # Assert
        assert len(result) == 2
        assert result["STOCK1234567890123456789"] == Decimal("100.50")
        assert result["BOND1111111111111111111A"] == Decimal("150.75")

        mock_base_client._make_request.assert_called_once_with(
            "POST", "/api/v1/prices/batch", json={"securityIds": security_ids}
        )

    @pytest.mark.asyncio
    async def test_get_security_prices_partial_data(
        self, pricing_client, mock_base_client
    ):
        """Test price retrieval with some missing securities."""
        # Arrange
        security_ids = ["STOCK1234567890123456789", "MISSING123456789012345"]
        mock_response = {
            "prices": {
                "STOCK1234567890123456789": "100.50"
                # Missing security not included
            }
        }
        mock_base_client._make_request.return_value = mock_response

        # Act
        result = await pricing_client.get_security_prices(security_ids)

        # Assert
        assert len(result) == 1
        assert "STOCK1234567890123456789" in result
        assert "MISSING123456789012345" not in result

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="Test expects future security price API (GET /api/v1/security/{id}/price) that doesn't exist yet"
    )
    async def test_get_single_security_price_success(
        self, pricing_client, mock_base_client
    ):
        """Test successful single security price retrieval."""
        # Arrange
        security_id = "STOCK1234567890123456789"
        mock_response = {"price": "125.75"}
        mock_base_client._make_request.return_value = mock_response

        # Act
        result = await pricing_client.get_security_price(security_id)

        # Assert
        assert result == Decimal("125.75")

        mock_base_client._make_request.assert_called_once_with(
            "GET", f"/api/v1/security/{security_id}/price"
        )


@pytest.mark.unit
class TestPortfolioClient:
    """Test the Portfolio Service client."""

    @pytest_asyncio.fixture
    async def mock_base_client(self):
        """Create a mock base client for testing."""
        return AsyncMock(spec=BaseServiceClient)

    @pytest_asyncio.fixture
    async def portfolio_client(self, mock_base_client):
        """Create a portfolio service client for testing."""
        client = PortfolioClient(base_url="http://portfolio-service:8000", timeout=5.0)
        client._base_client = mock_base_client
        return client

    @pytest.mark.asyncio
    async def test_get_portfolio_success(self, portfolio_client, mock_base_client):
        """Test successful portfolio metadata retrieval."""
        # Arrange
        portfolio_id = "683b6d88a29ee10e8b499643"
        mock_response = {
            "id": portfolio_id,
            "name": "Growth Portfolio",
            "type": "GROWTH",
            "status": "ACTIVE",
            "created_at": "2024-01-01T00:00:00Z",
        }
        mock_base_client._make_request.return_value = mock_response

        # Act
        result = await portfolio_client.get_portfolio(portfolio_id)

        # Assert
        assert result["id"] == portfolio_id
        assert result["name"] == "Growth Portfolio"
        assert result["type"] == "GROWTH"
        assert result["status"] == "ACTIVE"

        mock_base_client._make_request.assert_called_once_with(
            "GET", f"/api/v1/portfolio/{portfolio_id}"
        )

    @pytest.mark.asyncio
    async def test_validate_portfolios_success(
        self, portfolio_client, mock_base_client
    ):
        """Test successful portfolio validation."""
        # Arrange
        portfolio_ids = ["portfolio1", "portfolio2"]
        mock_response = {"valid": ["portfolio1", "portfolio2"], "invalid": []}
        mock_base_client._make_request.return_value = mock_response

        # Act
        result = await portfolio_client.validate_portfolios(portfolio_ids)

        # Assert
        assert result["valid"] == ["portfolio1", "portfolio2"]
        assert result["invalid"] == []

        mock_base_client._make_request.assert_called_once_with(
            "POST", "/api/v1/portfolios/validate", json={"portfolioIds": portfolio_ids}
        )


@pytest.mark.unit
class TestSecurityServiceClient:
    """Test the Security Service client."""

    @pytest_asyncio.fixture
    async def mock_base_client(self):
        """Create a mock base client for testing."""
        return AsyncMock(spec=BaseServiceClient)

    @pytest_asyncio.fixture
    async def security_client(self, mock_base_client):
        """Create a security service client for testing."""
        client = SecurityServiceClient(
            base_url="http://security-service:8000", timeout=5.0
        )
        client._base_client = mock_base_client
        return client

    @pytest.mark.asyncio
    async def test_get_security_success(self, security_client, mock_base_client):
        """Test successful security metadata retrieval."""
        # Arrange
        security_id = "STOCK1234567890123456789"
        mock_response = {
            "id": security_id,
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "type": "STOCK",
            "sector": "TECHNOLOGY",
            "status": "ACTIVE",
        }
        mock_base_client._make_request.return_value = mock_response

        # Act
        result = await security_client.get_security(security_id)

        # Assert
        assert result["id"] == security_id
        assert result["symbol"] == "AAPL"
        assert result["name"] == "Apple Inc."
        assert result["type"] == "STOCK"

        mock_base_client._make_request.assert_called_once_with(
            "GET", f"/api/v1/security/{security_id}"
        )

    @pytest.mark.asyncio
    async def test_validate_securities_success(self, security_client, mock_base_client):
        """Test successful security validation."""
        # Arrange
        security_ids = ["STOCK1234567890123456789", "BOND1111111111111111111A"]
        mock_response = {
            "valid": ["STOCK1234567890123456789", "BOND1111111111111111111A"],
            "invalid": [],
        }
        mock_base_client._make_request.return_value = mock_response

        # Act
        result = await security_client.validate_securities(security_ids)

        # Assert
        assert result["valid"] == security_ids
        assert result["invalid"] == []

        mock_base_client._make_request.assert_called_once_with(
            "POST", "/api/v1/securities/validate", json={"securityIds": security_ids}
        )

    @pytest.mark.asyncio
    async def test_validate_securities_with_invalid_ids(
        self, security_client, mock_base_client
    ):
        """Test security validation with some invalid IDs."""
        # Arrange
        security_ids = ["VALID123456789012345678", "INVALID123456789012345"]
        mock_response = {
            "valid": ["VALID123456789012345678"],
            "invalid": ["INVALID123456789012345"],
        }
        mock_base_client._make_request.return_value = mock_response

        # Act
        result = await security_client.validate_securities(security_ids)

        # Assert
        assert len(result["valid"]) == 1
        assert len(result["invalid"]) == 1
        assert "INVALID123456789012345" in result["invalid"]


@pytest.mark.unit
class TestCircuitBreakerStates:
    """Test circuit breaker state transitions and behavior."""

    @pytest_asyncio.fixture
    async def client_with_fast_timeout(self):
        """Create client with fast timeout for testing."""
        return BaseServiceClient(
            base_url="http://test:8000",
            service_name="test",
            timeout=0.1,  # Very short timeout
            circuit_breaker_timeout=1.0,  # Short recovery time
        )

    @pytest.mark.asyncio
    async def test_circuit_breaker_closed_to_open_transition(
        self, client_with_fast_timeout
    ):
        """Test circuit breaker transition from CLOSED to OPEN."""
        # Arrange
        assert (
            client_with_fast_timeout._circuit_breaker_state
            == CircuitBreakerState.CLOSED
        )

        # Create and inject mock client
        mock_client = AsyncMock(spec=AsyncClient)
        mock_client.get.side_effect = TimeoutException("Service timeout")
        client_with_fast_timeout._client = mock_client

        # Act - Generate failures to open circuit breaker
        for _ in range(5):  # Exceed failure threshold
            with pytest.raises(ServiceTimeoutError):
                await client_with_fast_timeout._make_request("GET", "/test")

        # Assert
        assert (
            client_with_fast_timeout._circuit_breaker_state == CircuitBreakerState.OPEN
        )

    @pytest.mark.asyncio
    async def test_circuit_breaker_open_to_half_open_transition(
        self, client_with_fast_timeout
    ):
        """Test circuit breaker transition from OPEN to HALF_OPEN."""
        # Arrange - Set circuit breaker to OPEN state
        client_with_fast_timeout._circuit_breaker_state = CircuitBreakerState.OPEN
        client_with_fast_timeout._circuit_breaker_open_time = (
            asyncio.get_event_loop().time() - 2.0
        )

        # Create and inject mock client
        mock_client = AsyncMock(spec=AsyncClient)
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value={"status": "success"})
        mock_client.get.return_value = mock_response
        client_with_fast_timeout._client = mock_client

        # Act - Try request after timeout
        result = await client_with_fast_timeout._make_request("GET", "/test")

        # Assert
        assert result == {"status": "success"}
        assert (
            client_with_fast_timeout._circuit_breaker_state
            == CircuitBreakerState.CLOSED
        )

    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_failure_reopens(
        self, client_with_fast_timeout
    ):
        """Test circuit breaker reopens on failure in HALF_OPEN state."""
        # Arrange - Set to HALF_OPEN state
        client_with_fast_timeout._circuit_breaker_state = CircuitBreakerState.HALF_OPEN

        # Create and inject mock client
        mock_client = AsyncMock(spec=AsyncClient)
        mock_client.get.side_effect = TimeoutException("Service timeout")
        client_with_fast_timeout._client = mock_client

        # Act - Fail request in HALF_OPEN state
        with pytest.raises(ServiceTimeoutError):
            await client_with_fast_timeout._make_request("GET", "/test")

        # Assert
        assert (
            client_with_fast_timeout._circuit_breaker_state == CircuitBreakerState.OPEN
        )
