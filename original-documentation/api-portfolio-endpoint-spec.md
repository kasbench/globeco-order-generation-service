# Portfolio Endpoint API Specification

## Overview
This document specifies the API endpoint required for the GlobeCo Portfolio Management Portal's rebalance results feature. The endpoint provides portfolio-level data for a specific rebalance when users expand rebalance rows in the UI.

## Endpoint Details

### GET /api/v1/rebalance/{rebalance_id}/portfolios

**Purpose**: Retrieve all portfolios associated with a specific rebalance for lazy-loading when users expand rebalance rows.

**URL Pattern**: `http://localhost:8088/api/v1/rebalance/{rebalance_id}/portfolios`

**Method**: `GET`

**Parameters**:
- `rebalance_id` (path parameter, required): The unique identifier of the rebalance
  - Type: `string` (MongoDB ObjectId format)
  - Example: `"68470f3eb7cf58482e2949ce"`

**Query Parameters**: None currently required, but could add pagination if needed in the future.

## Response Format

**Content-Type**: `application/json`

**Success Response (200 OK)**:

```json
[
  {
    "portfolio_id": "68430c0edbfc814369506be3",
    "market_value": 692761.0,
    "cash_before_rebalance": 35426.93,
    "cash_after_rebalance": 52583.07,
    "positions": [
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
      }
    ]
  }
]
```

## Data Structure Specification

### Portfolio Object
| Field | Type | Description | Required | Format/Constraints |
|-------|------|-------------|----------|-------------------|
| `portfolio_id` | string | Unique identifier for the portfolio | Yes | MongoDB ObjectId (24 hex chars) |
| `market_value` | number | Total market value of the portfolio | Yes | Positive number, 2 decimal precision for currency |
| `cash_before_rebalance` | number | Cash amount before rebalancing | Yes | Can be 0 or positive, 2 decimal precision |
| `cash_after_rebalance` | number | Cash amount after rebalancing | Yes | Can be 0 or positive, 2 decimal precision |
| `positions` | array | Array of position objects in this portfolio | Yes | Can be empty array |

### Position Object (nested within Portfolio)
| Field | Type | Description | Required | Format/Constraints |
|-------|------|-------------|----------|-------------------|
| `security_id` | string | Unique identifier for the security | Yes | MongoDB ObjectId (24 hex chars) |
| `price` | number | Current price per share/unit | Yes | Positive number, 2+ decimal precision |
| `original_quantity` | number | Quantity before rebalancing | Yes | Can be 0, 2+ decimal precision |
| `adjusted_quantity` | number | Quantity after rebalancing | Yes | Can be 0, 2+ decimal precision |
| `original_position_market_value` | number | Market value before rebalancing | Yes | Can be 0, 2 decimal precision |
| `adjusted_position_market_value` | number | Market value after rebalancing | Yes | Can be 0, 2 decimal precision |
| `target` | number | Target allocation percentage (as decimal) | Yes | 0.0 to 1.0, 3+ decimal precision |
| `high_drift` | number | High drift threshold (as decimal) | Yes | 0.0 to 1.0, 3+ decimal precision |
| `low_drift` | number | Low drift threshold (as decimal) | Yes | 0.0 to 1.0, 3+ decimal precision |
| `actual` | number | Actual allocation percentage (as decimal) | Yes | 0.0 to 1.0, 3+ decimal precision |
| `actual_drift` | number | Actual drift from target (as decimal) | Yes | Can be negative/positive, 3+ decimal precision |

## Error Responses

### 404 Not Found
**When**: Rebalance ID does not exist

```json
{
  "error": "Rebalance not found",
  "message": "No rebalance found with ID: {rebalance_id}",
  "status_code": 404
}
```

### 400 Bad Request
**When**: Invalid rebalance ID format

```json
{
  "error": "Invalid rebalance ID",
  "message": "Rebalance ID must be a valid MongoDB ObjectId",
  "status_code": 400
}
```

### 500 Internal Server Error
**When**: Database or server error

```json
{
  "error": "Internal server error",
  "message": "An error occurred while retrieving portfolio data",
  "status_code": 500
}
```

## Performance Considerations

### Response Size
- **Expected**: 10-100 portfolios per rebalance
- **Each Portfolio**: ~50-500 positions
- **Estimated Response Size**: 1-50MB depending on portfolio count and positions
- **Recommendation**: Consider pagination if responses exceed 10MB

### Database Query Optimization
- Index on `rebalance_id` in portfolios collection
- Consider aggregation pipeline for efficiency
- Pre-calculate market values and drift percentages if possible

## Business Logic Requirements

### Data Consistency
1. **Portfolio Market Value**: Should equal sum of all adjusted_position_market_values
2. **Drift Calculations**: `actual_drift = actual - target`
3. **Cash Changes**: `cash_after_rebalance - cash_before_rebalance` should reflect rebalancing impact
4. **Position Values**: `adjusted_position_market_value = adjusted_quantity * price`

### Data Validation
1. All portfolio_ids must belong to the specified rebalance
2. All monetary values must be non-negative
3. Target percentages should sum to approximately 1.0 per portfolio (allowing for rounding)
4. Security IDs must exist in the securities reference data

## Frontend Usage Context

### When This API Is Called
1. User clicks expand button on a rebalance row
2. Frontend calls `useRebalancePortfolios(rebalanceId, enabled=true)`
3. API fetches portfolio data for that specific rebalance
4. Data populates the Portfolio Table component

### Frontend Data Processing
1. **Currency Formatting**: 2 decimal places for all monetary values
2. **Percentage Display**: 3 decimal places for drift and allocation percentages
3. **Cash Change Calculation**: `(cash_after - cash_before) / cash_before * 100`
4. **Visual Indicators**: Green/red arrows based on cash change direction

## Security Considerations
- **Authentication**: Ensure user has access to view rebalance data
- **Authorization**: Verify user role permissions (Admin, Internal, Partner)
- **Rate Limiting**: Protect against excessive API calls
- **Input Validation**: Sanitize rebalance_id parameter

## Future Enhancements
1. **Pagination**: Add `limit` and `offset` query parameters
2. **Filtering**: Add `portfolio_status` or `drift_threshold` filters  
3. **Sorting**: Add `sort_by` parameter for portfolio ordering
4. **Aggregation**: Add summary statistics in response header
5. **Caching**: Implement Redis caching for frequently accessed rebalances

## Example Implementation Notes

### Database Query (MongoDB)
```javascript
// Aggregation pipeline example
db.portfolios.aggregate([
  { $match: { rebalance_id: ObjectId(rebalance_id) } },
  { $lookup: {
      from: "positions",
      localField: "portfolio_id", 
      foreignField: "portfolio_id",
      as: "positions"
  }},
  { $project: {
      portfolio_id: 1,
      market_value: 1,
      cash_before_rebalance: 1,
      cash_after_rebalance: 1,
      positions: 1
  }}
])
```

### Response Headers
```
Content-Type: application/json
X-Total-Portfolios: 28
X-Total-Positions: 245
X-Response-Time: 0.045s
```

This API endpoint is critical for the lazy-loading functionality in the rebalance results table and should maintain consistent response times under 200ms for optimal user experience. 