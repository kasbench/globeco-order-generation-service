# GlobeCo Order Generation Service

[![Build Status](https://github.com/kasbench/globeco-order-generation-service/workflows/CI/badge.svg)](https://github.com/kasbench/globeco-order-generation-service/actions)
[![Docker Hub](https://img.shields.io/docker/v/kasbench/globeco-order-generation-service?label=docker)](https://hub.docker.com/r/kasbench/globeco-order-generation-service)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/release/python-3130/)

> **Portfolio Optimization & Order Generation Microservice**
> Part of the GlobeCo Suite for KASBench Kubernetes Autoscaling Benchmark

## Overview

The Order Generation Service is a sophisticated microservice that creates optimized buy and sell orders for multiple portfolios simultaneously. It uses advanced mathematical optimization algorithms to rebalance portfolios according to predefined investment models, ensuring optimal asset allocation while respecting drift constraints and market conditions.

### Key Features

🎯 **Investment Model Management**
- Create and manage investment models with target allocations
- Define drift tolerances for each security position
- Support for up to 100 positions per model with 5% minimum cash allocation

⚡ **Portfolio Optimization**
- Mathematical optimization using CVXPY for portfolio rebalancing
- Mixed-Integer Linear Programming (MILP) for precise asset allocation
- Configurable 30-second optimization timeout with fallback strategies

🔄 **Multi-Portfolio Processing**
- Parallel rebalancing of multiple portfolios within a model
- Concurrent processing with configurable thread pools
- Individual portfolio error isolation for robust operations

📊 **Real-Time Integration**
- Integration with Portfolio Accounting Service for current positions
- Real-time pricing data from Pricing Service
- Circuit breaker pattern for external service resilience

🛡️ **Production Ready**
- Clean Architecture with Domain-Driven Design patterns
- Comprehensive error handling and retry logic
- Health checks and observability for Kubernetes deployment

## Technology Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| **Python** | 3.13 | Primary language |
| **FastAPI** | >=0.115.12 | Web framework & API |
| **MongoDB** | 8.0 | Document database |
| **Beanie** | >=1.29 | MongoDB ODM |
| **CVXPY** | >=1.6.0 | Mathematical optimization |
| **NumPy** | >=1.24.0 | Numerical computing |
| **Pydantic** | >=2.0.0 | Data validation |
| **Docker** | Latest | Containerization |
| **Kubernetes** | 1.33+ | Orchestration |

## Architecture

The service follows **Clean Architecture** principles with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                    🌐 API Layer (FastAPI)                   │
│                   Routes • Middleware • Validation          │
├─────────────────────────────────────────────────────────────┤
│                 💼 Application Layer (Core)                 │
│              Services • DTOs • Orchestration                │
├─────────────────────────────────────────────────────────────┤
│                 🧠 Domain Layer (Business Logic)            │
│           Entities • Value Objects • Domain Services        │
├─────────────────────────────────────────────────────────────┤
│               🔧 Infrastructure Layer                       │
│     Database • External Services • Optimization Engine      │
└─────────────────────────────────────────────────────────────┘
```

### Key Components

- **Investment Models**: Define target allocations and drift tolerances
- **Optimization Engine**: CVXPY-powered mathematical optimization
- **External Service Clients**: Integration with Portfolio, Pricing, and Security services
- **Repository Pattern**: MongoDB data access with Beanie ODM
- **Circuit Breakers**: Resilient external service communication

## Getting Started

### Prerequisites

- Python 3.13+
- Docker & Docker Compose
- MongoDB 8.0+ (or use Docker Compose)
- Access to GlobeCo external services (Portfolio Accounting, Pricing, etc.)

### Quick Start with Docker Compose

1. **Clone the repository**
```bash
git clone https://github.com/kasbench/globeco-order-generation-service.git
cd globeco-order-generation-service
```

2. **Start the development environment**
```bash
docker-compose up -d
```

3. **Verify the service is running**
```bash
curl http://localhost:8080/health/ready
```

4. **Access the API documentation**
```
http://localhost:8080/docs
```

### Local Development Setup

1. **Install uv package manager**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. **Set up the project**
```bash
# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .

# Install development dependencies
uv pip install -e ".[dev]"
```

3. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. **Start MongoDB (if not using Docker)**
```bash
# Using Docker
docker run -d --name mongodb -p 27017:27017 mongo:8.0

# Or install locally
# See: https://docs.mongodb.com/manual/installation/
```

5. **Run the development server**
```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8080
```

## API Documentation

The service exposes a REST API with the following main endpoints:

### Investment Models

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/models` | List all investment models |
| `POST` | `/api/v1/models` | Create a new investment model |
| `GET` | `/api/v1/model/{model_id}` | Get specific model |
| `PUT` | `/api/v1/model/{model_id}` | Update existing model |

### Portfolio Rebalancing

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/model/{model_id}/rebalance` | Rebalance all portfolios in model |
| `POST` | `/api/v1/portfolio/{portfolio_id}/rebalance` | Rebalance single portfolio |

### Model Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/model/{model_id}/position` | Add position to model |
| `PUT` | `/api/v1/model/{model_id}/position` | Update model position |
| `DELETE` | `/api/v1/model/{model_id}/position` | Remove position from model |
| `POST` | `/api/v1/model/{model_id}/portfolio` | Associate portfolios with model |

### Health & Monitoring

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health/live` | Liveness probe |
| `GET` | `/health/ready` | Readiness probe |
| `GET` | `/metrics` | Prometheus metrics |
| `GET` | `/docs` | Interactive API documentation |

### Example API Usage

**Create an Investment Model:**
```bash
curl -X POST "http://localhost:8080/api/v1/models" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Conservative Growth Model",
    "positions": [
      {
        "securityId": "683b6b9620f302c879a5fef4",
        "target": 0.60,
        "highDrift": 0.05,
        "lowDrift": 0.05
      },
      {
        "securityId": "683b6b9620f302c879a5fef5",
        "target": 0.35,
        "highDrift": 0.03,
        "lowDrift": 0.03
      }
    ],
    "portfolios": ["683b6d88a29ee10e8b499643"]
  }'
```

**Rebalance a Portfolio:**
```bash
curl -X POST "http://localhost:8080/api/v1/portfolio/683b6d88a29ee10e8b499643/rebalance"
```

## Development

### Project Structure

```
globeco-order-generation-service/
├── src/                     # Source code
│   ├── api/                 # FastAPI routes and middleware
│   ├── core/                # Application services
│   ├── domain/              # Business logic and entities
│   ├── infrastructure/      # External integrations
│   ├── models/              # Database models (Beanie)
│   ├── schemas/             # Pydantic schemas
│   └── tests/               # Test suites
├── deployments/             # Kubernetes manifests
├── docs/                    # Documentation
├── scripts/                 # Utility scripts
├── docker-compose.yml       # Development environment
├── Dockerfile               # Container build
└── pyproject.toml          # Python project configuration
```

### Development Workflow

1. **Code Quality Tools**
```bash
# Format code
black src/ tests/
ruff check src/ tests/ --fix

# Type checking
mypy src/

# Run all quality checks
make lint
```

2. **Testing**
```bash
# Run unit tests
pytest src/tests/unit/

# Run integration tests
pytest src/tests/integration/

# Run all tests with coverage
pytest --cov=src --cov-report=html

# Run specific test
pytest src/tests/unit/domain/test_investment_model.py -v
```

3. **Mathematical Validation**
```bash
# Run optimization engine tests
pytest src/tests/unit/infrastructure/test_cvxpy_solver.py -v

# Run mathematical precision tests
pytest src/tests/unit/domain/test_drift_calculator.py -v
```

### Configuration

The service uses environment-based configuration with sensible defaults:

```python
# Key configuration options
DATABASE_URL="mongodb://localhost:27017"
DATABASE_NAME="order-generation"
LOG_LEVEL="INFO"
OPTIMIZATION_TIMEOUT=30
MAX_PARALLEL_REBALANCES=10

# External service URLs
PORTFOLIO_ACCOUNTING_SERVICE_URL="http://globeco-portfolio-accounting-service:8087"
PRICING_SERVICE_URL="http://globeco-pricing-service:8083"
PORTFOLIO_SERVICE_URL="http://globeco-portfolio-service:8000"
SECURITY_SERVICE_URL="http://globeco-security-service:8000"
```

## Deployment

### Docker

**Build and run locally:**
```bash
# Build the image
docker build -t globeco-order-generation-service .

# Run the container
docker run -p 8080:8080 \
  -e DATABASE_URL="mongodb://host.docker.internal:27017" \
  globeco-order-generation-service
```

### Kubernetes

**Deploy to Kubernetes:**
```bash
# Apply all manifests
kubectl apply -f deployments/

# Check deployment status
kubectl get pods -n globeco -l app=order-generation-service

# View service logs
kubectl logs -n globeco deployment/order-generation-service -f
```

**Key Kubernetes Features:**
- Horizontal Pod Autoscaler (HPA) for automatic scaling
- Resource limits and requests for optimal performance
- Health checks for liveness and readiness probes
- ConfigMaps and Secrets for configuration management
- Service mesh integration ready

### CI/CD Pipeline

The service includes GitHub Actions workflows for:

- **Continuous Integration**: Automated testing, linting, and quality checks
- **Multi-architecture Builds**: AMD64 and ARM64 container images
- **Security Scanning**: Container vulnerability assessment
- **Automated Deployment**: GitOps-based deployment to Kubernetes

## Mathematical Foundation

The service implements sophisticated portfolio optimization using:

### Optimization Problem Formulation

**Objective Function:**
```
Minimize: Σ|MV·target_i - quantity_i·price_i|
```

**Subject to constraints:**
- Market value conservation: `MV = Cash + Σ(ui × pi)`
- Integer quantities: `∀i, ui ∈ ℤ, ui ≥ 0`
- Lower bounds: `∀i, ui × pi ≥ MV × (wi - li)`
- Upper bounds: `∀i, ui × pi ≤ MV × (wi + hi)`

Where:
- `MV` = Portfolio market value
- `ui` = Quantity of security i
- `pi` = Price of security i
- `wi` = Target weight for security i
- `li`, `hi` = Low and high drift tolerances

### Key Features
- **CVXPY Integration** for robust mathematical optimization
- **Timeout Handling** with configurable 30-second limits
- **Infeasible Solution Detection** with appropriate error responses
- **Numerical Precision** using Python Decimal for financial accuracy

## Monitoring & Observability

### Metrics

The service exposes Prometheus metrics including:

- **Business Metrics**: Portfolio drift, rebalancing success rates
- **Performance Metrics**: Optimization solver performance, API response times
- **System Metrics**: Database connections, external service health
- **Mathematical Metrics**: Constraint satisfaction, optimization convergence

### Logging

Structured JSON logging with:
- Correlation IDs for request tracing
- Performance timing for optimization operations
- Audit trail for model changes and rebalancing
- Error context for troubleshooting

### Health Checks

- **Liveness Probe** (`/health/live`): Service availability
- **Readiness Probe** (`/health/ready`): Dependency health
- **Detailed Health** (`/health/detailed`): Comprehensive system status

## External Dependencies

The service integrates with these GlobeCo services:

| Service | Purpose | Port |
|---------|---------|------|
| **Portfolio Accounting Service** | Current portfolio positions | 8087 |
| **Pricing Service** | Real-time security prices | 8083 |
| **Portfolio Service** | Portfolio metadata | 8000 |
| **Security Service** | Security information | 8000 |

**Resilience Features:**
- Circuit breaker pattern for fault tolerance
- Exponential backoff retry logic (3 attempts)
- Graceful degradation when services are unavailable
- Configurable timeouts for each service

## Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

### Development Process

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Write tests first** (we follow TDD methodology)
4. **Implement your feature**
5. **Ensure all tests pass**: `pytest`
6. **Run quality checks**: `make lint`
7. **Commit your changes**: `git commit -m 'Add amazing feature'`
8. **Push to your branch**: `git push origin feature/amazing-feature`
9. **Open a Pull Request**

### Code Style

- Follow [PEP 8](https://pep8.org/) style guidelines
- Use [Black](https://black.readthedocs.io/) for code formatting
- Use [Ruff](https://docs.astral.sh/ruff/) for linting
- Include type hints for all functions and classes
- Write comprehensive docstrings following [Google style](https://google.github.io/styleguide/pyguide.html)

## Support & Documentation

- **API Documentation**: Available at `/docs` when running the service
- **Architecture Documentation**: [architecture.md](ai-generated-documentation/architecture.md)
- **Requirements Documentation**: [requirements.md](ai-generated-documentation/requirements.md)
- **Execution Plan**: [execution-plan.md](ai-generated-documentation/execution-plan.md)
- **Business Requirements**: [business-requirements.md](original-documentation/business-requirements.md)

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Project Information

- **Organization**: KASBench (kasbench.org)
- **Author**: Noah Krieger (noah@kasbench.org)
- **Repository**: [github.com/kasbench/globeco-order-generation-service](https://github.com/kasbench/globeco-order-generation-service)
- **Docker Hub**: [kasbench/globeco-order-generation-service](https://hub.docker.com/r/kasbench/globeco-order-generation-service)

---

> **Note**: This service is part of the KASBench Kubernetes autoscaling benchmark suite and is designed for benchmarking purposes. It contains no production financial data and should not be used in live trading environments.
