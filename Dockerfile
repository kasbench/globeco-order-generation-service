# Multi-stage, multi-architecture Dockerfile for GlobeCo Order Generation Service
# Supports AMD64 and ARM64 architectures with production optimization

# ===================================================================
# Base Stage: Common dependencies and system setup
# ===================================================================
FROM python:3.11-slim-bookworm AS base

# Set build arguments for multi-architecture support
ARG TARGETPLATFORM
ARG BUILDPLATFORM
ARG TARGETARCH

# Set environment variables for Python optimization
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/src \
    PORT=8088 \
    HOST=0.0.0.0 \
    CORS_ORIGINS="*" \
    LOG_LEVEL=DEBUG

# Install system dependencies required for both architectures
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Build dependencies
    build-essential \
    pkg-config \
    git \
    # Mathematical libraries (architecture-specific optimizations)
    libopenblas-dev \
    liblapack-dev \
    gfortran \
    # Network and security
    ca-certificates \
    curl \
    # Process management
    tini \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

# Set working directory
WORKDIR /app

# ===================================================================
# Dependencies Stage: Install Python dependencies
# ===================================================================
FROM base AS dependencies

# Install uv for fast dependency management
RUN pip install uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install production dependencies in virtual environment using system Python
RUN python3 -m venv /app/.venv && \
    uv pip install --python /app/.venv/bin/python --no-cache -r pyproject.toml

# ===================================================================
# Development Stage: Full development environment
# ===================================================================
FROM dependencies AS development

# Copy source code
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

# Expose development port
EXPOSE 8088

# Health check for development
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8088/health/live || exit 1

# Development command with auto-reload (uses environment PORT or defaults to 8088)
CMD /app/.venv/bin/uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8088} --reload

# ===================================================================
# Testing Stage: Run tests and security scanning
# ===================================================================
FROM development AS testing

# Switch back to root for test execution
USER root

# Run comprehensive test suite
RUN /app/.venv/bin/python -m pytest src/tests/ -v --tb=short

# Run security scanning (if bandit is available)
RUN /app/.venv/bin/python -m bandit -r src/ -f json -o security-report.json || true

# Run dependency vulnerability check
RUN /app/.venv/bin/python -m safety check --json --output vulnerability-report.json || true

# ===================================================================
# Production Build Stage: Compile and optimize
# ===================================================================
FROM dependencies AS builder

# Copy source code
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser pyproject.toml ./

# Pre-compile Python bytecode for faster startup
RUN /app/.venv/bin/python -m compileall -b src/

# Create optimized application directory
RUN mkdir -p /app/dist && \
    cp -r src/ /app/dist/ && \
    cp pyproject.toml /app/dist/

# ===================================================================
# Production Stage: Minimal runtime image
# ===================================================================
FROM base AS production

# Install only runtime dependencies (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Runtime mathematical libraries only
    libopenblas0 \
    liblapack3 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from dependencies stage
COPY --from=dependencies --chown=appuser:appuser /app/.venv /app/.venv

# Fix permissions on virtual environment binaries (handle symlinks properly)
RUN find /app/.venv/bin -type f -executable -exec chmod +x {} \; && \
    chown -R appuser:appuser /app/.venv

# Copy optimized application from builder
COPY --from=builder --chown=appuser:appuser /app/dist /app

# Copy startup script
COPY --chown=appuser:appuser scripts/start-production.sh /app/
RUN chmod +x /app/start-production.sh

# Create required directories
RUN mkdir -p /app/logs /app/data && \
    chown -R appuser:appuser /app/logs /app/data

# Switch to non-root user
USER appuser

# Expose production port
EXPOSE 8088

# Configure health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD /app/.venv/bin/python -c "import requests; requests.get('http://localhost:8088/health/live', timeout=5)" || exit 1

# Production entrypoint with proper signal handling
ENTRYPOINT ["tini", "--"]

# Production command with startup script that handles LOG_LEVEL properly
CMD ["/app/start-production.sh"]

# Metadata labels for multi-architecture support
LABEL org.opencontainers.image.title="GlobeCo Order Generation Service" \
      org.opencontainers.image.description="Portfolio optimization and rebalancing service" \
      org.opencontainers.image.vendor="KasBench" \
      org.opencontainers.image.source="https://github.com/kasbench/globeco-order-generation-service" \
      org.opencontainers.image.documentation="https://github.com/kasbench/globeco-order-generation-service/blob/main/README.md" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.architecture="${TARGETARCH}"
