# Supplemental Requirement 1

This is a correction to the original specification for how to calculate market value.  The code to be corrected is in [portfolio_accounting_client.py](../src/infrastructure/external/portfolio_accounting_client.py).

## API Endpoints

The Portfolio Accounting Service API to get balances is:

GET /api/v1/portfolios/{portfolioId}/summary

For example:
```bash
curl -X 'GET' \
  'http://globeco-portfolio-accounting-service:8087/api/v1/portfolios/683b6d88a29ee10e8b499643/summary' \
  -H 'accept: application/json'
```

The response to the curl command above looks like:

```json
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
```

## Market Value Calculation

Market value is calculated as:

- The value of "cashBalance", PLUS
- The sum of the market values of the security positions

The value of the security positions is calculated by:

1. **Get Security Ticker**: Call GET /api/v1/security/{securityId} on the GlobeCo Security Service to get the ticker. The response looks like this:
    ```json
    {
        "ticker": "string",
        "description": "string",
        "securityTypeId": "string",
        "version": 1,
        "securityId": "string",
        "securityType": {
            "securityTypeId": "string",
            "abbreviation": "string",
            "description": "string"
        }
    }
    ```

2. **Get Security Price**: Call GET /api/v1/price/{ticker} on the GlobeCo Pricing Service to get the price. The response looks like this. Price is the `close` field:
    ```json
    {
        "id": 0,
        "ticker": "string",
        "date": "2025-06-06",
        "open": 0,
        "close": 0,
        "high": 0,
        "low": 0,
        "volume": 0
    }
    ```

3. **Calculate Position Value**: Multiply `netQuantity` from the Portfolio Accounting Service response by the `close` price from the Pricing Service. Round to three decimal places.

## Data Type Handling

- **String to Decimal Conversion**: All financial values (`cashBalance`, `netQuantity`, `close` price) should be converted to Python `Decimal` objects for precise financial calculations
- **Rounding**: Final market value should be rounded to 3 decimal places using `Decimal.quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)`
- **Validation**: Validate that `close` price is positive (greater than zero). Note: `cashBalance` may be negative (overdrawn accounts) and `netQuantity` may be negative (short positions) - both are valid scenarios.

## Error Handling

### Portfolio State Scenarios (Not Errors)
- A portfolio may have cash only, securities only, or cash and securities. None of these are error conditions.
- If there is no balance record for a portfolio, treat it as a zero market value. It is not an error. It just means that the portfolio is new and it doesn't yet have any transactions to generate a balance.

### Service Failure Scenarios
- **Portfolio Accounting Service Unavailable**: Raise `ExternalServiceError` - cannot calculate market value without position data
- **Security Service Unavailable**: Raise `ExternalServiceError` - cannot determine tickers for pricing
- **Pricing Service Unavailable**: Raise `ExternalServiceError` - cannot calculate position values without prices

### Missing Data Scenarios
- **Security Not Found (404)**: Raise `ExternalServiceError` with HTTP 500 - cannot calculate accurate market value without security ticker information.
- **Price Not Available**: Raise `ExternalServiceError` with HTTP 500 - cannot calculate accurate market value without current pricing data.
- **Invalid Financial Data**: If `cashBalance`, `netQuantity`, or `close` price cannot be converted to valid numbers, raise `ExternalServiceError` with HTTP 500.

### Timeout and Retry Configuration
- **Service Timeouts**: 10 seconds for each external service call
- **Retry Logic**: 3 attempts with exponential backoff (1s, 2s, 4s delays) for HTTP 5xx errors and connection timeouts
- **No Retry**: Do not retry for HTTP 4xx errors (client errors)

## Caching Strategy

Use caching to improve performance with TTLCache from the cachetools library:

- **Securities Cache**: TTL of 10 minutes, key format: `security:{securityId}`, value: ticker string
- **Prices Cache**: TTL of 1 minute, key format: `price:{ticker}`, value: Decimal price
- **Implementation**: Use singleton cache instances per client to ensure thread safety
- **Cache Size**: Limit to 1000 entries per cache to prevent memory issues

Example cache initialization:
```python
from cachetools import TTLCache
securities_cache = TTLCache(maxsize=1000, ttl=600)  # 10 minutes
prices_cache = TTLCache(maxsize=1000, ttl=60)       # 1 minute
```

## Performance Requirements

- **Response Time**: Market value calculation should complete within 30 seconds for portfolios with up to 100 securities
- **Parallel Processing**: External service calls should be made concurrently where possible (e.g., batch security lookups)
- **Logging**: Log calculation start/end times and any skipped securities for audit purposes

## Integration Notes

- **Endpoint Migration**: This new `/portfolios/{portfolioId}/summary` endpoint replaces the existing `/portfolio/{portfolioId}/balances` endpoint in portfolio_accounting_client.py
- **Method Updates**: Update `get_portfolio_market_value()` method to use the new calculation logic
- **Backward Compatibility**: Maintain existing method signatures for minimal impact on calling code