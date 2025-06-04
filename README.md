# GlobeCo Order Generation Service

A high-performance portfolio optimization and rebalancing service built with FastAPI, MongoDB, and CVXPY. This service provides mathematical optimization capabilities for investment portfolio management with enterprise-grade reliability and financial precision.

## 🚀 Features

### Core Capabilities
- **Portfolio Optimization**: Mathematical optimization using CVXPY with multiple solver backends
- **Investment Model Management**: CRUD operations for investment models with positions and target allocations
- **Portfolio Rebalancing**: Automated rebalancing with transaction generation and drift analysis
- **Financial Precision**: Decimal arithmetic throughout for regulatory compliance
- **Multi-Portfolio Support**: Concurrent rebalancing of multiple portfolios

### Technical Excellence
- **Clean Architecture**: Domain-driven design with clear separation of concerns
- **High Performance**: Async/await throughout with efficient concurrent processing
- **System Resilience**: Circuit breaker pattern with automatic retry and fallback
- **Comprehensive Testing**: 731+ tests with meaningful coverage and TDD methodology
- **Production Ready**: Health checks, structured logging, and operational monitoring

### API Capabilities
- **RESTful API**: Comprehensive REST endpoints with automatic OpenAPI documentation
- **Type Safety**: Full Pydantic validation with custom financial business rules
- **Error Handling**: Structured error responses with detailed validation messages
- **Security**: CORS middleware, security headers, and input sanitization

## 📋 Prerequisites

- **Python**: 3.11 or higher
- **MongoDB**: 4.4 or higher (or MongoDB Atlas)
- **uv**: Modern Python package manager (recommended)

### Development Tools
- **Docker**: For containerized development and testing
- **Git**: Version control

## ⚡ Quick Start

### 1. Clone Repository
```bash
git clone https://github.com/kasbench/globeco-order-generation-service.git
cd globeco-order-generation-service
```

### 2. Install Dependencies
```bash
# Using uv (recommended)
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv sync

# Or using pip
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 3. Configure Environment
```bash
# Copy example environment file
cp env.example .env

# Edit .env with your MongoDB connection and other settings
# Required variables:
# - MONGODB_URL=mongodb://localhost:27017/globeco_dev
# - SECRET_KEY=your-secret-key-here
```

### 4. Start MongoDB
```bash
# Using Docker (recommended for development)
docker run -d --name mongodb -p 27017:27017 mongo:7

# Or use MongoDB Atlas cloud instance
```

### 5. Run the Service
```bash
# Development server with auto-reload
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Production server
gunicorn src.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### 6. Verify Installation
```bash
# Health check
curl http://localhost:8000/health/health

# API documentation
open http://localhost:8000/docs
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `MONGODB_URL` | MongoDB connection string | `mongodb://localhost:27017/globeco_dev` | Yes |
| `SECRET_KEY` | JWT secret key for authentication | - | Yes |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` | No |
| `CORS_ORIGINS` | Allowed CORS origins (comma-separated) | `*` | No |
| `MAX_OPTIMIZATION_TIME` | Solver timeout in seconds | `30` | No |
| `EXTERNAL_SERVICE_TIMEOUT` | External service timeout in seconds | `10` | No |

### Application Settings
The service uses Pydantic Settings for configuration management. See `src/config.py` for all available settings.

## 📚 API Documentation

### Interactive Documentation
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

### Core Endpoints

#### Investment Models
```http
# Create investment model
POST /api/v1/models
Content-Type: application/json

{
  "name": "Balanced Portfolio",
  "positions": [
    {
      "security_id": "TECH123456789012345678AB",
      "target": 60.0,
      "low_drift": 2.0,
      "high_drift": 5.0
    }
  ],
  "portfolios": ["portfolio123456789012345"]
}

# Get all models
GET /api/v1/models

# Get specific model
GET /api/v1/models/{model_id}

# Update model
PUT /api/v1/models/{model_id}

# Delete model
DELETE /api/v1/models/{model_id}
```

#### Portfolio Rebalancing
```http
# Rebalance single portfolio
POST /api/v1/rebalance/portfolio/{portfolio_id}

# Rebalance all portfolios for a model
POST /api/v1/rebalance/model/{model_id}
```

#### Health Monitoring
```http
# Liveness probe
GET /health/live

# Readiness probe
GET /health/ready

# Comprehensive health check
GET /health/health
```

### Business Rules

#### Security IDs
- Must be exactly 24 alphanumeric characters
- Example: `TECH123456789012345678AB`

#### Target Percentages
- Range: 0% to 95%
- Precision: Multiples of 0.005 (0.5 basis points)
- Sum of all targets in a model must not exceed 95%

#### Drift Bounds
- Range: 0% to 100%
- Low drift must be ≤ high drift
- Used for optimization constraint boundaries

## 🧪 Testing

### Run All Tests
```bash
# Run complete test suite
pytest

# Run with coverage
pytest --cov=src --cov-report=html --cov-report=term-missing

# Run specific test categories
pytest -m unit        # Unit tests only
pytest -m integration # Integration tests only
```

### Test Categories
- **Unit Tests** (431 tests): Domain logic, services, and component testing
- **Integration Tests** (284 tests): Database integration, external services, API endpoints
- **Mathematical Tests** (16 tests): Optimization correctness and edge cases

### Performance Testing
```bash
# Run performance benchmarks
pytest src/tests/integration/test_mathematical_validation_edge_cases.py::TestOptimizationPerformanceComplexity --benchmark-only
```

## 🏗️ Development

### Project Structure
```
src/
├── main.py                 # FastAPI application entry point
├── config.py              # Configuration management
├── api/                   # API layer
│   └── routers/          # API route handlers
├── core/                 # Application services
│   ├── services/         # Business logic services
│   ├── mappers.py        # DTO-Domain mapping
│   ├── exceptions.py     # Custom exceptions
│   └── utils.py          # Utility functions
├── domain/               # Domain layer (business logic)
│   ├── entities/         # Domain entities
│   ├── value_objects/    # Value objects
│   ├── repositories/     # Repository interfaces
│   └── services/         # Domain services
├── infrastructure/       # Infrastructure layer
│   ├── database/         # Database implementation
│   ├── external/         # External service clients
│   └── optimization/     # Mathematical optimization
├── schemas/              # Pydantic schemas (DTOs)
└── tests/                # Test suites
    ├── unit/            # Unit tests
    ├── integration/     # Integration tests
    └── fixtures/        # Test fixtures
```

### Code Quality Tools
```bash
# Format code
black src tests

# Sort imports
isort src tests

# Lint code
ruff check src tests

# Type checking
mypy src

# Run all quality checks
pre-commit run --all-files
```

### Adding New Features

1. **Domain First**: Start with domain entities and business rules
2. **Test-Driven**: Write tests before implementation
3. **Clean Architecture**: Maintain clear layer boundaries
4. **Financial Precision**: Use Decimal for all financial calculations

## 🐳 Docker Deployment

### Build Image
```bash
# Build production image
docker build -t globeco-order-generation-service .

# Build with specific tag
docker build -t globeco-order-generation-service:v1.0.0 .
```

### Run Container
```bash
# Run with environment variables
docker run -d \
  --name globeco-service \
  -p 8000:8000 \
  -e MONGODB_URL=mongodb://host.docker.internal:27017/globeco_prod \
  -e SECRET_KEY=your-production-secret \
  globeco-order-generation-service
```

### Docker Compose
```bash
# Start complete stack (app + MongoDB)
docker-compose up -d

# Stop stack
docker-compose down

# View logs
docker-compose logs -f
```

## ☸️ Kubernetes Deployment

### Apply Manifests
```bash
# Deploy to Kubernetes
kubectl apply -f deployments/

# Check deployment status
kubectl get pods -l app=globeco-order-generation-service

# View logs
kubectl logs -f deployment/globeco-order-generation-service
```

### Scaling
```bash
# Manual scaling
kubectl scale deployment globeco-order-generation-service --replicas=3

# Auto-scaling is configured via HPA manifests
```

## 📊 Monitoring & Observability

### Health Endpoints
- **Liveness**: `/health/live` - Basic application health
- **Readiness**: `/health/ready` - Ready to serve traffic
- **Health**: `/health/health` - Comprehensive health with dependencies

### Logging
- **Structured JSON logs** with correlation IDs
- **Request tracing** across service boundaries
- **Sensitive data masking** for compliance

### Metrics
Integration points for Prometheus metrics:
- Request duration and counts
- Optimization performance
- External service health
- Business KPIs (portfolios rebalanced, optimization success rate)

## 🔒 Security

### API Security
- **Input validation** with Pydantic
- **Security headers** middleware
- **CORS configuration** for cross-origin requests
- **Request size limits** and timeout protection

### Data Security
- **No sensitive data in logs** (automatically masked)
- **Decimal precision** prevents calculation errors
- **Optimistic locking** prevents concurrent modification issues

## 🚨 Troubleshooting

### Common Issues

#### MongoDB Connection Issues
```bash
# Check MongoDB connectivity
mongosh $MONGODB_URL

# Verify environment variables
echo $MONGODB_URL
```

#### Optimization Failures
```bash
# Check solver availability
python -c "import cvxpy; print(cvxpy.installed_solvers())"

# Test optimization health
curl http://localhost:8000/health/health
```

#### Performance Issues
```bash
# Check resource usage
docker stats globeco-service

# Monitor logs for slow operations
kubectl logs -f deployment/globeco-order-generation-service | grep duration
```

### Debug Mode
```bash
# Run with debug logging
LOG_LEVEL=DEBUG uvicorn src.main:app --reload
```

## 🤝 Contributing

### Development Workflow
1. **Fork** the repository
2. **Create feature branch**: `git checkout -b feature/amazing-feature`
3. **Write tests** for new functionality
4. **Implement** the feature following Clean Architecture
5. **Run tests**: `pytest`
6. **Run quality checks**: `pre-commit run --all-files`
7. **Commit changes**: `git commit -m "Add amazing feature"`
8. **Push branch**: `git push origin feature/amazing-feature`
9. **Create Pull Request**

### Code Standards
- **TDD**: Tests before implementation
- **Clean Architecture**: Maintain layer boundaries
- **Type Hints**: Full type annotation
- **Documentation**: Comprehensive docstrings
- **Financial Precision**: Use Decimal for calculations

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📞 Support

### Documentation
- **API Docs**: http://localhost:8000/docs
- **Architecture Decision Records**: [ADRs](ai-generated-documentation/architecture-decision-records.md)
- **Execution Plan**: [Development Plan](ai-generated-documentation/execution-plan.md)

### Issue Reporting
Please use GitHub Issues for bug reports and feature requests.

### Performance
- **Optimization Speed**: Sub-second for portfolios up to 100 positions
- **Concurrent Requests**: Supports 100+ concurrent rebalancing operations
- **Response Times**: <200ms for read operations, <30s for optimization

---

**GlobeCo Order Generation Service** - Powering institutional portfolio optimization with mathematical precision and enterprise reliability.
