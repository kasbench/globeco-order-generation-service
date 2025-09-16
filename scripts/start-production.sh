#!/bin/bash
set -e

# Convert LOG_LEVEL to lowercase for uvicorn
UVICORN_LOG_LEVEL=$(echo "${LOG_LEVEL:-INFO}" | tr '[:upper:]' '[:lower:]')

echo "Starting GlobeCo Order Generation Service..."
echo "Port: ${PORT:-8088}"
echo "Log Level: $UVICORN_LOG_LEVEL"

# Determine number of workers (default to 1 for consistent metrics)
# Force to 1 worker to avoid metrics duplication until multiprocess is properly configured
WORKERS=4

# Configure Prometheus multiprocess mode if using multiple workers
if [ "$WORKERS" -gt 1 ]; then
    echo "Configuring Prometheus multiprocess mode for $WORKERS workers"
    export prometheus_multiproc_dir="/tmp/prometheus_multiproc_dir"
    mkdir -p "$prometheus_multiproc_dir"
    # Clean up any existing metrics files
    rm -rf "$prometheus_multiproc_dir"/*
else
    echo "Using single worker mode - no multiprocess configuration needed"
fi

# Start with Gunicorn
exec /app/.venv/bin/gunicorn \
     -w "$WORKERS" \
     -k uvicorn.workers.UvicornWorker \
     -b 0.0.0.0:${PORT:-8088} \
     --log-level "$UVICORN_LOG_LEVEL" \
     --access-logfile - \
     --error-logfile - \
     --preload \
     src.main:app
