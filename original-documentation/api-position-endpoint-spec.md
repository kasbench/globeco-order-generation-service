# Position Endpoint API Specification

## Overview
This document specifies the API endpoint required for the GlobeCo Portfolio Management Portal's rebalance results feature. The endpoint provides position-level data for a specific portfolio within a rebalance when users expand portfolio rows in the UI.

## Endpoint Details

### GET /api/v1/rebalance/{rebalance_id}/portfolio/{portfolio_id}/positions

**Purpose**: Retrieve all positions within a specific portfolio for a specific rebalance, used for lazy-loading when users expand portfolio rows.

**URL Pattern**: `http://localhost:8088/api/v1/rebalance/{rebalance_id}/portfolio/{portfolio_id}/positions`

**Method**: `GET`

**Parameters**:
- `rebalance_id` (path parameter, required): The unique identifier of the rebalance
  - Type: `string` (MongoDB ObjectId format)
  - Example: `"68470f3eb7cf58482e2949ce"`
- `portfolio_id` (path parameter, required): The unique identifier of the portfolio
  - Type: `string` (MongoDB ObjectId format)  
  - Example: `"68430c1bdbfc81436950873f"`

**Query Parameters**: None currently required, but could add pagination if needed for portfolios with 100+ positions.

## Response Format

**Content-Type**: `application/json`

**Success Response (200 OK)**:

```json
[
  {
    "security_id": "68430bfd20f302c879a60286",
    "price": 62.85,
    "original_quantity": 0.0,
    "adjusted_quantity": 220.0,
    "original_position_market_value": 0.0,
    "adjusted_position_market_value": 13827.0,
    "target": 0.02,
    "high_drift": 0.005,
    "low_drift": 0.005,
    "actual": 0.01995926445051035,
    "actual_drift": 0.0020367774744825414
  },
  {
    "security_id": "68430bfd20f302c879a60287",
    "price": 45.12,
    "original_quantity": 150.0,
    "adjusted_quantity": 180.0,
    "original_position_market_value": 6768.0,
    "adjusted_position_market_value": 8121.6,
    "target": 0.015,
    "high_drift": 0.003,
    "low_drift": 0.003,
    "actual": 0.01472895332167832,
    "actual_drift": -0.00027104667832168"
  }
]
```

## Data Structure Specification

### Position Object
| Field | Type | Description | Required | Format/Constraints |
|-------|------|-------------|----------|-------------------|
| `security_id` | string | Unique identifier for the security | Yes | MongoDB ObjectId (24 hex chars) |
| `price` | number | Current price per share/unit | Yes | Positive number, 2+ decimal precision |
| `original_quantity` | number | Quantity held before rebalancing | Yes | Can be 0, 2+ decimal precision |
| `adjusted_quantity` | number | Quantity held after rebalancing | Yes | Can be 0, 2+ decimal precision |
| `original_position_market_value` | number | Market value before rebalancing | Yes | Can be 0, 2 decimal precision |
| `adjusted_position_market_value` | number | Market value after rebalancing | Yes | Can be 0, 2 decimal precision |
| `target` | number | Target allocation percentage (as decimal) | Yes | 0.0 to 1.0, 3+ decimal precision |
| `high_drift` | number | High drift threshold (as decimal) | Yes | 0.0 to 1.0, 3+ decimal precision |
| `low_drift` | number | Low drift threshold (as decimal) | Yes | 0.0 to 1.0, 3+ decimal precision |
| `actual` | number | Actual allocation percentage (as decimal) | Yes | 0.0 to 1.0, 3+ decimal precision |
| `actual_drift` | number | Actual drift from target (as decimal) | Yes | Can be negative/positive, 3+ decimal precision |

## Error Responses

### 404 Not Found - Rebalance
**When**: Rebalance ID does not exist

```json
{
  "error": "Rebalance not found",
  "message": "No rebalance found with ID: {rebalance_id}",
  "status_code": 404
}
```

### 404 Not Found - Portfolio
**When**: Portfolio ID does not exist or doesn't belong to the specified rebalance

```json
{
  "error": "Portfolio not found",
  "message": "No portfolio found with ID: {portfolio_id} in rebalance: {rebalance_id}",
  "status_code": 404
}
```

### 400 Bad Request - Invalid IDs
**When**: Invalid rebalance or portfolio ID format

```json
{
  "error": "Invalid ID format",
  "message": "Rebalance ID and Portfolio ID must be valid MongoDB ObjectIds",
  "status_code": 400
}
```

### 500 Internal Server Error
**When**: Database or server error

```json
{
  "error": "Internal server error",
  "message": "An error occurred while retrieving position data",
  "status_code": 500
}
```

## Performance Considerations

### Response Size
- **Expected**: 50-500 positions per portfolio
- **Typical Position Record**: ~200-300 bytes
- **Estimated Response Size**: 10KB-150KB per portfolio
- **Recommendation**: Consider pagination if portfolios exceed 1000 positions

### Database Query Optimization
- Composite index on `(rebalance_id, portfolio_id)` in positions collection
- Index on `security_id` for joins with securities reference data
- Consider pre-aggregated position summaries for performance

## Business Logic Requirements

### Data Consistency
1. **Position Market Values**: `adjusted_position_market_value = adjusted_quantity * price`
2. **Original Market Values**: `original_position_market_value = original_quantity * price`  
3. **Drift Calculations**: `actual_drift = actual - target`
4. **Allocation Totals**: All `actual` values should sum to approximately 1.0 per portfolio (allowing for rounding)
5. **Portfolio Relationship**: All positions must belong to the specified portfolio and rebalance

### Data Validation
1. All position records must belong to the specified portfolio and rebalance
2. All monetary values and quantities must be non-negative
3. Target percentages should be between 0.0 and 1.0
4. Security IDs must exist in the securities reference data
5. Price values must be greater than 0

## Frontend Usage Context

### When This API Is Called
1. User expands a portfolio row in the rebalance results table
2. Frontend calls `useRebalancePortfolioPositions(rebalanceId, portfolioId, enabled=true)`
3. API fetches position data for that specific portfolio
4. Data populates the Position Table component within the expanded portfolio section

### Frontend Data Processing
1. **Currency Formatting**: 2 decimal places for prices and market values
2. **Quantity Formatting**: 2 decimal places for share quantities  
3. **Percentage Display**: 3 decimal places for target, actual, and drift percentages
4. **Quantity Change Calculation**: `adjusted_quantity - original_quantity`
5. **Visual Indicators**: Color coding based on drift direction (positive/negative)

## Security Considerations
- **Authentication**: Ensure user has access to view rebalance and portfolio data
- **Authorization**: Verify user role permissions (Admin, Internal, Partner - no Customer access)
- **Data Isolation**: Ensure positions returned belong only to the specified portfolio
- **Rate Limiting**: Protect against excessive API calls from rapid expand/collapse actions
- **Input Validation**: Sanitize both rebalance_id and portfolio_id parameters

## Future Enhancements
1. **Pagination**: Add `limit` and `offset` query parameters for large position lists
2. **Filtering**: Add filters for:
   - `drift_threshold` (show only positions exceeding threshold)
   - `position_status` (new, modified, closed positions)
   - `security_type` (equity, bond, etc.)
3. **Sorting**: Add `sort_by` parameter with options:
   - `market_value` (default descending)
   - `drift` (absolute value, descending)
   - `security_id` (alphabetical)
4. **Aggregation**: Add summary statistics in response headers
5. **Caching**: Implement Redis caching for frequently accessed portfolios
6. **Security Details**: Option to include security name, symbol, and sector information

## Example Implementation Notes

### Database Query (MongoDB)
```javascript
// Direct query example
db.positions.find({
  rebalance_id: ObjectId(rebalance_id),
  portfolio_id: ObjectId(portfolio_id)
}).sort({ adjusted_position_market_value: -1 })

// With security lookup (if needed)
db.positions.aggregate([
  { $match: { 
      rebalance_id: ObjectId(rebalance_id),
      portfolio_id: ObjectId(portfolio_id)
  }},
  { $lookup: {
      from: "securities",
      localField: "security_id",
      foreignField: "_id", 
      as: "security_info"
  }},
  { $sort: { adjusted_position_market_value: -1 }}
])
```

### Response Headers
```
Content-Type: application/json
X-Total-Positions: 245
X-Portfolio-Market-Value: 692761.00
X-Response-Time: 0.025s
X-Cache-Status: MISS
```

### Example cURL Request
```bash
curl -X GET \
  "http://globeco-order-generation-service:8088/api/v1/rebalance/68470f3eb7cf58482e2949ce/portfolio/68430c1bdbfc81436950873f/positions" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json"
```

## Performance Benchmarks
- **Target Response Time**: < 100ms for typical portfolios (< 500 positions)
- **Maximum Response Time**: < 500ms for large portfolios (500+ positions)
- **Throughput**: Support 50+ concurrent requests per second
- **Memory Usage**: < 10MB per request for largest expected portfolios

This API endpoint is critical for the drill-down functionality in the rebalance results table and should maintain consistent response times for optimal user experience when users explore position-level details. 