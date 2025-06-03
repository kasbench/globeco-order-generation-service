# GlobeCo Order Generation Service - Requirements

## Service Overview

**Service Name:** Order Generation Service
**Host:** globeco-order-generation-service
**Port:** 8080
**Author:** Noah Krieger (noah@kasbench.org)
**Organization:** KASBench (kasbench.org)

### Purpose
This microservice creates orders to buy and sell securities for multiple portfolios through mathematical optimization. It maintains investment models, performs portfolio rebalancing using advanced optimization algorithms, and serves as part of the GlobeCo suite of applications for benchmarking Kubernetes autoscaling.

## Technology Stack

### Core Technologies
| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.13 | Primary language |
| MongoDB | 8.0 | Primary database |
| FastAPI | >=0.115.12 | Web framework |
| Beanie | >=1.29 | MongoDB ODM |
| CVXPY | >=1.6.0 | Mathematical optimization |

### Python Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| fastapi | >=0.115.12 | HTTP API framework |
| beanie | >=1.29 | MongoDB ODM |
| motor | >=3.0.0 | Async MongoDB driver |
| pydantic | >=2.0.0 | Data validation |
| cvxpy | >=1.6.0 | Mathematical optimization |
| numpy | >=1.24.0 | Numerical computing |
| scipy | >=1.11.0 | Scientific computing |
| httpx | >=0.25.0 | HTTP client |
| tenacity | >=8.2.0 | Retry logic |
| pytest | >=8.35 | Testing framework |
| pytest-asyncio | >=0.26.0 | Async testing |
| pytest-mongo | >=3.2.0 | MongoDB testing |
| uvicorn | >=0.24.0 | ASGI server |
| gunicorn | >=23.0.0 | Production server |

### Infrastructure Components
| Component | Host | Port | Docker Image |
|-----------|------|------|--------------|
| Database | globeco-order-generation-service-mongodb | 27017 | mongo:8.0 |

## Data Model

### Models Collection
| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| _id | ObjectId | PRIMARY KEY | Unique MongoDB identifier |
| name | String | NOT NULL, UNIQUE | Model name |
| positions | Array[Position] | NOT NULL | List of security positions |
| portfolios | Array[String] | NOT NULL | Associated portfolio IDs |
| lastRebalanceDate | Date | NULL | Last rebalancing timestamp |
| version | Int32 | NOT NULL, DEFAULT 1 | Optimistic locking version |

### Position Embedded Document
| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| securityId | String | NOT NULL | 24-character security ID |
| target | Decimal128 | NOT NULL, 0-0.95 | Target allocation percentage |
| highDrift | Decimal128 | NOT NULL, 0-1 | Upper drift tolerance |
| lowDrift | Decimal128 | NOT NULL, 0-1 | Lower drift tolerance |

### Indexes
- `models.name` - UNIQUE
- `models.portfolios` - MULTIKEY
- `models.positions.securityId` - SPARSE

### Business Rules

#### Model Validation Rules
| Rule | Description |
|------|-------------|
| Target Sum | Sum of all position targets ≤ 0.95 (5% minimum cash) |
| Target Precision | Targets must be 0 or multiples of 0.005 |
| Position Limit | Maximum 100 positions with target > 0 |
| Security Uniqueness | Each security appears only once per model |
| Zero Target Cleanup | Positions with target = 0 are automatically removed |

#### Drift Validation Rules
| Rule | Description |
|------|-------------|
| Drift Range | High/low drift values between 0 and 1 |
| Drift Logic | Low drift ≤ high drift for each position |

#### Optimization Constraints
| Constraint | Mathematical Expression |
|------------|------------------------|
| Market Value Conservation | MV = Cash + Σ(ui × pi) |
| Integer Quantities | ∀i, ui ∈ ℤ, ui ≥ 0 |
| Lower Bound | ∀i, ui × pi ≥ MV × (wi - li) |
| Upper Bound | ∀i, ui × pi ≤ MV × (wi + hi) |

## API Specification

### Base Path
`/api/v1`

### Model Management Endpoints
| Method | Path | Parameters | Request | Response | Description |
|--------|------|------------|---------|----------|-------------|
| GET | /models | - | - | ModelDTO[] | Get all models |
| GET | /model/{modelId} | - | - | ModelDTO | Get model by ID |
| POST | /models | - | ModelPostDTO | ModelDTO | Create new model |
| PUT | /model/{modelId} | - | ModelPutDTO | ModelDTO | Update existing model |

### Position Management Endpoints
| Method | Path | Parameters | Request | Response | Description |
|--------|------|------------|---------|----------|-------------|
| POST | /model/{modelId}/position | - | ModelPositionDTO | ModelDTO | Add position to model |
| PUT | /model/{modelId}/position | - | ModelPositionDTO | ModelDTO | Update model position |
| DELETE | /model/{modelId}/position | - | ModelPositionDTO | ModelDTO | Remove position from model |

### Portfolio Association Endpoints
| Method | Path | Parameters | Request | Response | Description |
|--------|------|------------|---------|----------|-------------|
| POST | /model/{modelId}/portfolio | - | ModelPortfolioDTO | ModelDTO | Add portfolios to model |
| DELETE | /model/{modelId}/portfolio | - | ModelPortfolioDTO | ModelDTO | Remove portfolios from model |

### Rebalancing Endpoints
| Method | Path | Parameters | Request | Response | Description |
|--------|------|------------|---------|----------|-------------|
| POST | /model/{modelId}/rebalance | - | - | RebalanceDTO[] | Rebalance all model portfolios |
| POST | /portfolio/{portfolioId}/rebalance | - | - | RebalanceDTO | Rebalance single portfolio |

### Data Transfer Objects

#### ModelDTO
```json
{
  "modelId": "string(ObjectId)",
  "name": "string",
  "positions": "ModelPositionDTO[]",
  "portfolios": "string[]",
  "lastRebalanceDate": "datetime?",
  "version": "integer"
}
```

#### ModelPostDTO
```json
{
  "name": "string",
  "positions": "ModelPositionDTO[]",
  "portfolios": "string[]"
}
```

#### ModelPutDTO
```json
{
  "name": "string",
  "positions": "ModelPositionDTO[]",
  "portfolios": "string[]",
  "lastRebalanceDate": "datetime?",
  "version": "integer"
}
```

#### ModelPositionDTO
```json
{
  "securityId": "string(24)",
  "target": "decimal(0-0.95)",
  "highDrift": "decimal(0-1)",
  "lowDrift": "decimal(0-1)"
}
```

#### RebalanceDTO
```json
{
  "portfolioId": "string(24)",
  "transactions": "TransactionDTO[]",
  "drifts": "DriftDTO[]"
}
```

#### TransactionDTO
```json
{
  "transactionType": "string(BUY|SELL)",
  "securityId": "string(24)",
  "quantity": "integer",
  "tradeDate": "date"
}
```

#### DriftDTO
```json
{
  "securityId": "string(24)",
  "originalQuantity": "decimal",
  "adjustedQuantity": "decimal",
  "target": "decimal",
  "highDrift": "decimal",
  "lowDrift": "decimal",
  "actual": "decimal(4)"
}
```

## Processing Requirements

### Portfolio Rebalancing Algorithm
1. **Data Collection**
   - Retrieve current positions from Portfolio Accounting Service
   - Get model target allocations and drift tolerances
   - Fetch current security prices from Pricing Service
   - Calculate current market value including cash positions

2. **Optimization Setup**
   - Formulate Mixed-Integer Linear Program (MILP)
   - Set objective: minimize Σ|MV·target_i - quantity_i·price_i|
   - Apply constraints: drift bounds, integer quantities, non-negativity
   - Configure solver timeout (default: 30 seconds)

3. **Solution Processing**
   - Execute CVXPY optimization solver
   - Extract optimal quantities for each security
   - Calculate transaction deltas (new - current quantities)
   - Generate buy/sell transactions for non-zero deltas

4. **Result Generation**
   - Create TransactionDTO objects for each required trade
   - Calculate DriftDTO objects showing before/after positions
   - Compile RebalanceDTO with transactions and drift analysis
   - Return results to API caller (not sent to Order Service)

### Multi-Portfolio Rebalancing
1. **Model Retrieval** - Get investment model and associated portfolios
2. **Parallel Processing** - Rebalance portfolios concurrently using thread pool
3. **Error Isolation** - Continue processing remaining portfolios if one fails
4. **Result Aggregation** - Collect and return all rebalancing results

### Mathematical Optimization Details
- **Solver Selection**: CVXPY with automatic solver selection (ECOS_BB, SCIP)
- **Problem Type**: Mixed-Integer Linear Programming (MILP)
- **Variables**: Integer security quantities (ui)
- **Objective**: Minimize total portfolio drift
- **Timeout**: Configurable solver timeout (default: 30 seconds)
- **Precision**: Decimal arithmetic for financial calculations

## Quality Requirements

### Performance
- **Optimization Timeout**: 30-second configurable limit per portfolio
- **Parallel Processing**: Configurable thread pool for multi-portfolio operations
- **Database Connections**: Connection pooling for MongoDB operations
- **Caching**: Price and model data caching strategies

### Reliability
- **Idempotency**: Safe to retry rebalancing operations
- **External Service Resilience**: 3 retry attempts with exponential backoff
- **Circuit Breaker**: Fail-fast for degraded external services
- **Graceful Degradation**: Partial results when some portfolios fail
- **Error Classification**: Distinguish recoverable vs. fatal errors

### Mathematical Accuracy
- **Precision**: Python Decimal arithmetic for financial calculations
- **Constraint Validation**: Strict enforcement of drift bounds
- **Optimization Validation**: Solution feasibility verification
- **Rounding**: Consistent rounding for percentage calculations (4 decimal places)

### Observability
- **Structured Logging**: JSON format with correlation IDs
- **Performance Metrics**: Optimization solver performance tracking
- **Business Metrics**: Portfolio drift, rebalancing success rates
- **Health Checks**: Database connectivity and external service status
- **Audit Trail**: Complete history of model changes and rebalancing operations

### Testing
- **Unit Tests**: High coverage for all business logic
- **Integration Tests**: External service mocking and database testing
- **Mathematical Tests**: Optimization algorithm validation
- **Performance Tests**: Load testing for concurrent rebalancing
- **TestContainers**: MongoDB integration testing

### Security
- **Input Validation**: Multi-layer validation (Pydantic, domain)
- **CORS Configuration**: All origins allowed (benchmarking environment)
- **Data Protection**: Secure handling of financial data
- **Error Information**: Sanitized error messages in responses

## External Dependencies

### Required Services
| Service | Host | Port | Purpose | Timeout |
|---------|------|------|---------|---------|
| Portfolio Accounting Service | globeco-portfolio-accounting-service | 8087 | Current positions | 10s |
| Pricing Service | globeco-pricing-service | 8083 | Security prices | 10s |
| Portfolio Service | globeco-portfolio-service | 8000 | Portfolio metadata | 10s |
| Security Service | globeco-security-service | 8000 | Security information | 10s |

### Optional Services (Phase 2)
| Service | Host | Port | Purpose |
|---------|------|------|---------|
| Portfolio Optimization Service | globeco-portfolio-optimization-service | TBD | Advanced optimization |
| Order Service | globeco-order-service | 8081 | Order submission |

### Service Integration Patterns
- **Retry Logic**: 3 attempts with exponential backoff (1s, 2s, 4s)
- **Circuit Breaker**: Fail-fast after 5 consecutive failures
- **Timeout Management**: Configurable per-service timeouts
- **Error Handling**: Graceful degradation for non-critical services

## Error Handling Requirements

### Error Categories
| Category | HTTP Status | Retry | Description |
|----------|-------------|-------|-------------|
| Validation Error | 400 | No | Invalid input data |
| Not Found | 404 | No | Model/portfolio not found |
| Conflict | 409 | No | Version conflict, business rule violation |
| Optimization Error | 422 | No | No feasible solution, solver timeout |
| External Service Error | 503 | Yes | Dependency unavailable |
| Internal Error | 500 | No | Unexpected system error |

### Specific Error Scenarios
- **Infeasible Solution**: Return HTTP 422 when optimization constraints cannot be satisfied
- **Solver Timeout**: Return HTTP 422 when optimization exceeds 30-second limit
- **External Service Failure**: Return HTTP 503 for Portfolio Accounting/Pricing Service failures
- **Concurrent Modification**: Return HTTP 409 for version conflicts during model updates

### Error Response Format
```json
{
  "error": {
    "code": "OPTIMIZATION_FAILED",
    "message": "No feasible solution exists for portfolio constraints",
    "details": {
      "portfolioId": "683b6d88a29ee10e8b499643",
      "solverStatus": "INFEASIBLE"
    },
    "timestamp": "2024-12-19T10:30:00Z",
    "traceId": "abc123"
  }
}
```

## Deployment Requirements

### Containerization
- **Multi-stage Docker Build**: Optimized Python image with minimal size
- **Multi-architecture Support**: AMD64 and ARM64 builds for Linux
- **Base Image**: python:3.13-slim with security updates
- **Health Checks**: Container-level health check endpoints

### Kubernetes Integration
- **Namespace**: `globeco` (pre-existing)
- **Service Discovery**: DNS-based service resolution
- **Config Management**: ConfigMaps for application settings
- **Secrets Management**: Kubernetes secrets for sensitive data
- **Resource Limits**: CPU/memory constraints for optimization workloads

### CI/CD Pipeline
- **GitHub Actions**: Automated build, test, and deployment
- **Docker Hub Registry**: `kasbench/globeco-order-generation-service`
- **Multi-architecture Builds**: Automated AMD64/ARM64 compilation
- **Testing Pipeline**: Unit, integration, and performance tests
- **Security Scanning**: Container vulnerability assessment

### Configuration Management
- **Environment Variables**: Database connection, external service URLs
- **Feature Flags**: Configurable parallelization limits, timeouts
- **Secrets**: Database credentials, API keys
- **Health Check Configuration**: Kubernetes liveness/readiness probes

### Monitoring & Observability
- **Prometheus Metrics**: Custom business and performance metrics
- **Health Endpoints**: `/health/live` and `/health/ready`
- **Swagger Documentation**: Auto-generated OpenAPI specification at `/docs`
- **Log Aggregation**: Centralized logging with structured JSON format
