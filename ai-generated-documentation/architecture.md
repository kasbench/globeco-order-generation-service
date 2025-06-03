# GlobeCo Order Generation Service - Technical Architecture

## Architecture Overview

The Order Generation Service follows **Clean Architecture** principles with **Domain-Driven Design (DDD)** patterns. The service is designed as a microservice with clear separation of concerns, ensuring maintainability, testability, and scalability for portfolio rebalancing and investment model management.

### Architecture Principles

1. **Dependency Inversion** - High-level modules don't depend on low-level modules
2. **Single Responsibility** - Each layer has a single, well-defined purpose
3. **Interface Segregation** - Clean contracts between layers
4. **Domain-Centric Design** - Business logic isolated from infrastructure concerns
5. **Idempotency** - Safe to retry operations without side effects
6. **Mathematical Precision** - Accurate financial calculations and optimization

## Project Structure

```
globeco-order-generation-service/
├── src/
│   ├── main.py              # FastAPI application entry point
│   ├── config.py            # Configuration settings
│   ├── api/                 # Presentation layer - HTTP endpoints
│   │   ├── routers/         # API route definitions
│   │   │   ├── models.py    # Model management endpoints
│   │   │   ├── rebalance.py # Rebalancing endpoints
│   │   │   └── health.py    # Health check endpoints
│   │   ├── dependencies.py  # FastAPI dependencies
│   │   ├── middleware.py    # HTTP middleware
│   │   └── __init__.py
│   ├── schemas/             # Pydantic models for API contracts
│   │   ├── models.py        # Model DTOs
│   │   ├── transactions.py  # Transaction DTOs
│   │   ├── rebalance.py     # Rebalance DTOs
│   │   └── __init__.py
│   ├── core/                # Application layer
│   │   ├── services/        # Application services
│   │   │   ├── model_service.py      # Model management
│   │   │   ├── rebalance_service.py  # Rebalancing orchestration
│   │   │   └── portfolio_service.py  # Portfolio operations
│   │   ├── exceptions.py    # Custom exceptions
│   │   ├── security.py      # Security utilities
│   │   ├── utils.py         # Utility functions
│   │   └── __init__.py
│   ├── domain/              # Domain layer - business logic
│   │   ├── entities/        # Domain entities
│   │   │   ├── model.py     # Investment model entity
│   │   │   ├── position.py  # Position entity
│   │   │   └── portfolio.py # Portfolio entity
│   │   ├── services/        # Domain services
│   │   │   ├── optimization_engine.py  # Mathematical optimization
│   │   │   ├── drift_calculator.py     # Drift calculations
│   │   │   └── validation_service.py   # Business rule validation
│   │   ├── repositories/    # Repository interfaces
│   │   │   ├── model_repository.py
│   │   │   └── base_repository.py
│   │   ├── value_objects/   # Value objects
│   │   │   ├── target_percentage.py
│   │   │   ├── drift_bounds.py
│   │   │   └── market_value.py
│   │   └── __init__.py
│   ├── infrastructure/      # Infrastructure layer
│   │   ├── database/        # MongoDB implementation
│   │   │   ├── database.py  # Database connection
│   │   │   ├── repositories/ # Concrete repository implementations
│   │   │   └── __init__.py
│   │   ├── external/        # External service clients
│   │   │   ├── portfolio_accounting_client.py
│   │   │   ├── portfolio_client.py
│   │   │   ├── pricing_client.py
│   │   │   ├── security_client.py
│   │   │   ├── base_client.py
│   │   │   └── __init__.py
│   │   ├── optimization/    # Optimization implementation
│   │   │   ├── cvxpy_solver.py
│   │   │   └── __init__.py
│   │   └── __init__.py
│   ├── models/              # Database models (Beanie ODM)
│   │   ├── model.py         # MongoDB model document
│   │   └── __init__.py
│   └── tests/               # Tests
│       ├── unit/            # Unit tests
│       ├── integration/     # Integration tests
│       └── __init__.py
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

## Layer Architecture

### 1. Presentation Layer (`src/api`)

**Responsibility:** Handle HTTP requests, routing, and response formatting

#### Components:
- **Routers** - FastAPI route definitions and handlers
- **Dependencies** - Dependency injection for services
- **Middleware** - Cross-cutting concerns (logging, CORS, metrics)
- **Schemas** - Pydantic models for request/response validation

#### Key Technologies:
- FastAPI for HTTP routing and OpenAPI generation
- Pydantic for data validation and serialization
- Custom middleware for observability

```python
# Example router structure
@router.post("/models/{model_id}/rebalance", response_model=List[schemas.RebalanceDTO])
async def rebalance_model_portfolios(
    model_id: str,
    rebalance_service: RebalanceService = Depends(get_rebalance_service)
) -> List[schemas.RebalanceDTO]:
    """Triggers rebalancing for all portfolios in the specified model."""
    return await rebalance_service.rebalance_model_portfolios(model_id)
```

### 2. Application Layer (`src/core`)

**Responsibility:** Orchestrate business operations and coordinate between layers

#### Components:
- **Services** - Application-specific business logic orchestration
- **Exceptions** - Application-level exception definitions
- **Security** - Authentication and authorization logic
- **Utils** - Application utility functions

#### Key Services:
```python
class RebalanceService:
    """Orchestrates portfolio rebalancing operations."""

    async def rebalance_portfolio(
        self,
        portfolio_id: str
    ) -> schemas.RebalanceDTO:
        """Rebalances a single portfolio using its associated model."""

    async def rebalance_model_portfolios(
        self,
        model_id: str
    ) -> List[schemas.RebalanceDTO]:
        """Rebalances all portfolios associated with a model."""
```

### 3. Domain Layer (`src/domain`)

**Responsibility:** Core business logic, entities, and domain rules

#### Key Entities:
```python
class InvestmentModel:
    """Represents an investment model with target allocations."""

    model_id: ObjectId
    name: str
    positions: List[Position]
    portfolios: List[str]
    last_rebalance_date: Optional[datetime]
    version: int

    def validate_position_targets(self) -> None:
        """Ensures position targets sum to ≤ 0.95 and follow business rules."""

    def add_position(self, position: Position) -> None:
        """Adds a position with validation."""

class Position:
    """Represents a security position within a model."""

    security_id: str
    target: Decimal  # Target percentage (0-0.95)
    high_drift: Decimal  # Allowable drift above target (0-1)
    low_drift: Decimal  # Allowable drift below target (0-1)

    def validate_drifts(self) -> None:
        """Validates drift bounds are within acceptable ranges."""
```

#### Domain Services:
```python
class OptimizationEngine:
    """Handles mathematical optimization for portfolio rebalancing."""

    async def optimize_portfolio(
        self,
        current_positions: Dict[str, int],
        target_model: InvestmentModel,
        prices: Dict[str, Decimal],
        market_value: Decimal
    ) -> OptimizationResult:
        """
        Solves the portfolio optimization problem using CVXPY.

        Minimizes: Σ|MV·target_i - quantity_i·price_i|
        Subject to: drift constraints, integer quantities, non-negativity
        """

class DriftCalculator:
    """Calculates portfolio drift and target allocations."""

    def calculate_portfolio_drift(
        self,
        positions: Dict[str, int],
        prices: Dict[str, Decimal],
        market_value: Decimal,
        model: InvestmentModel
    ) -> Decimal:
        """Calculates total portfolio drift from target allocations."""
```

### 4. Infrastructure Layer (`src/infrastructure`)

**Responsibility:** External system integration and technical implementation

#### Database Layer (MongoDB with Beanie):
```python
class MongoModelRepository(ModelRepository):
    """MongoDB implementation of model repository using Beanie ODM."""

    async def create(self, model: InvestmentModel) -> InvestmentModel:
        """Creates a new investment model in MongoDB."""

    async def get_by_id(self, model_id: str) -> Optional[InvestmentModel]:
        """Retrieves model by ID with caching."""

    async def update(self, model: InvestmentModel) -> InvestmentModel:
        """Updates model with optimistic concurrency control."""
```

#### External Service Clients:
```python
class PortfolioAccountingClient:
    """Client for Portfolio Accounting Service."""

    async def get_portfolio_balances(
        self,
        portfolio_id: str
    ) -> List[BalanceDTO]:
        """Retrieves current portfolio positions."""

class PricingServiceClient:
    """Client for Real-Time Pricing Service."""

    async def get_security_prices(
        self,
        security_ids: List[str]
    ) -> Dict[str, Decimal]:
        """Retrieves current security prices."""
```

#### Optimization Implementation:
```python
class CVXPYSolver:
    """CVXPY implementation of portfolio optimization."""

    async def solve_rebalancing_problem(
        self,
        current_quantities: np.ndarray,
        target_percentages: np.ndarray,
        prices: np.ndarray,
        market_value: float,
        low_drifts: np.ndarray,
        high_drifts: np.ndarray,
        timeout_seconds: int = 30
    ) -> OptimizationResult:
        """Solves MILP optimization problem with timeout."""
```

## Data Flow Architecture

### 1. Model Management Flow

```
HTTP Request → FastAPI Router → Model Service → Model Repository → MongoDB
                ↓
         Response ← Pydantic Schema ← Domain Entity ← Beanie Document
```

### 2. Portfolio Rebalancing Flow

```
HTTP Request → Rebalance Service → Get Current Positions (Portfolio Accounting)
                ↓                               ↓
         Get Model → Get Prices (Pricing Service) → Optimization Engine
                ↓                               ↓
         Calculate Drift ← Generate Transactions ← CVXPY Solver
                ↓
         Return RebalanceDTO ← Create Response
```

### 3. Multi-Portfolio Rebalancing Flow

```
Model ID → Get Model → Get Associated Portfolios → Parallel Rebalancing
                ↓                                        ↓
         Aggregate Results ← Thread Pool Executor ← Individual Portfolio Results
```

## Component Integration

### Database Integration (MongoDB + Beanie)

- **ODM Integration** - Beanie for object-document mapping
- **Connection Management** - Motor async driver with connection pooling
- **Document Validation** - Pydantic models with MongoDB validation
- **Optimistic Locking** - Version-based concurrency control
- **Indexing Strategy** - Optimized for query patterns

```python
# Example Beanie document model
class ModelDocument(Document):
    name: str
    positions: List[PositionEmbedded]
    portfolios: List[str]
    last_rebalance_date: Optional[datetime]
    version: int = 1

    class Settings:
        name = "models"
        indexes = [
            IndexModel([("name", 1)], unique=True),
            IndexModel([("portfolios", 1)])
        ]
```

### External Service Integration

- **Circuit Breaker Pattern** - Fault tolerance with exponential backoff
- **Retry Logic** - Configurable retry attempts (default: 3)
- **Timeout Management** - Configurable request timeouts
- **Service Discovery** - Kubernetes DNS-based service resolution
- **Error Handling** - Graceful degradation and error propagation

```python
class ExternalServiceClient:
    """Base class for external service integration."""

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def make_request(self, url: str, **kwargs) -> Any:
        """Makes HTTP request with retry logic and circuit breaker."""
```

### Optimization Engine Integration

- **CVXPY Integration** - Mathematical optimization solver
- **Solver Selection** - Automatic solver selection (ECOS_BB, SCIP)
- **Timeout Handling** - Configurable solver timeout (default: 30s)
- **Problem Formulation** - MILP problem setup and constraint handling
- **Result Processing** - Solution extraction and validation

### Parallel Processing

- **AsyncIO Integration** - Asynchronous portfolio processing
- **Thread Pool** - CPU-bound optimization tasks
- **Concurrency Control** - Configurable parallelization limits
- **Error Isolation** - Individual portfolio failure handling

## Security Architecture

### Authentication & Authorization
- Service-to-service authentication via API keys
- Request validation and input sanitization
- CORS configuration for all origins (benchmarking environment)

### Data Protection
- Input validation at multiple layers (Pydantic, domain)
- SQL injection prevention (not applicable for MongoDB)
- Sensitive financial data handling best practices

### Network Security
- TLS encryption for external service communications
- Internal service mesh security (Kubernetes network policies)

## Observability Architecture

### Logging
- **Structured Logging** - JSON format with correlation IDs
- **Log Levels** - Configurable verbosity (DEBUG, INFO, WARNING, ERROR)
- **Financial Audit Trail** - Model changes and rebalancing operations
- **Performance Logging** - Optimization solver performance metrics

### Metrics
- **Prometheus Integration** - Custom business and performance metrics
- **Rebalancing Metrics** - Success rates, processing times, optimization results
- **External Service Metrics** - Response times, error rates, circuit breaker status
- **Mathematical Metrics** - Portfolio drift, optimization convergence

### Health Checks
- **Liveness Probe** - Service availability (`/health/live`)
- **Readiness Probe** - Service readiness (`/health/ready`)
- **Dependency Checks** - MongoDB connectivity, external service availability

```python
@router.get("/health/ready")
async def readiness_check(
    db: AsyncIOMotorDatabase = Depends(get_database)
) -> HealthStatus:
    """Kubernetes readiness probe with dependency checks."""
    health = HealthStatus()
    health.check_database(db)
    health.check_external_services()
    return health
```

## Scalability Architecture

### Horizontal Scaling
- **Stateless Design** - No server-side session state
- **Load Balancing** - Kubernetes service load balancing
- **Auto-scaling** - HPA based on CPU/memory metrics and custom metrics

### Optimization Scaling
- **Parallel Portfolio Processing** - Concurrent rebalancing operations
- **CPU-bound Optimization** - Thread pool for CVXPY solver operations
- **Memory Management** - Efficient matrix operations for large portfolios

### Database Scaling
- **MongoDB Sharding** - Horizontal data distribution (future)
- **Read Replicas** - Read traffic distribution
- **Connection Pooling** - Efficient connection management

## Error Handling Architecture

### Error Categories
1. **Validation Errors** - Input validation failures, business rule violations
2. **Optimization Errors** - Infeasible solutions, solver timeouts
3. **External Service Errors** - Dependency failures, network issues
4. **Mathematical Errors** - Precision issues, overflow conditions

### Error Handling Strategy
- **Domain-Specific Errors** - Financial calculation errors, optimization failures
- **Circuit Breaker Pattern** - External service failure protection
- **Graceful Degradation** - Partial results when possible
- **Audit Trail** - Error logging for financial compliance

### Optimization Error Handling
```python
class OptimizationError(Exception):
    """Raised when portfolio optimization fails."""

class InfeasibleSolutionError(OptimizationError):
    """Raised when no feasible solution exists within constraints."""

class SolverTimeoutError(OptimizationError):
    """Raised when optimization solver exceeds timeout."""
```

## Performance Considerations

### Mathematical Optimization
- **Solver Performance** - CVXPY with efficient solvers (ECOS_BB, SCIP)
- **Problem Size** - Optimized for portfolios up to 100+ securities
- **Numerical Precision** - Decimal arithmetic for financial calculations
- **Caching Strategy** - Price and model data caching

### Database Optimization
- **Indexing Strategy** - Optimized for query patterns (model lookup, portfolio filtering)
- **Aggregation Pipelines** - Efficient MongoDB aggregations
- **Connection Pooling** - Configured for concurrent operations

### Concurrency Optimization
- **AsyncIO** - Non-blocking I/O for external service calls
- **Thread Pools** - CPU-bound optimization in separate threads
- **Batch Processing** - Efficient multi-portfolio operations

### Memory Management
- **NumPy Arrays** - Efficient matrix operations for optimization
- **Decimal Precision** - Python Decimal for financial accuracy
- **Garbage Collection** - Explicit cleanup for large optimization problems

## Deployment Architecture

### Containerization
- **Multi-stage Docker Build** - Optimized image size
- **Multi-architecture Support** - AMD64 and ARM64 builds
- **Base Image** - Python 3.13 slim with security updates

### Kubernetes Integration
- **Namespace** - `globeco` namespace
- **Service Mesh** - Istio integration (future enhancement)
- **Config Management** - ConfigMaps and Secrets
- **Resource Limits** - CPU/memory constraints for optimization workloads

### CI/CD Pipeline
- **GitHub Actions** - Automated build and deployment
- **Docker Hub** - Multi-architecture image registry
- **Testing Pipeline** - Unit, integration, and performance tests
- **Security Scanning** - Container vulnerability scanning
