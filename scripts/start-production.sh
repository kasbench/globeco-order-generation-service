#!/bin/bash
set -e

# Convert LOG_LEVEL to lowercase for uvicorn
UVICORN_LOG_LEVEL=$(echo "${LOG_LEVEL:-INFO}" | tr '[:upper:]' '[:lower:]')

echo "Starting GlobeCo Order Generation Service..."
echo "Port: ${PORT:-8088}"
echo "Log Level: $UVICORN_LOG_LEVEL"

# Determine number of workers (default to 3)
WORKERS=${WORKERS:-3}
echo "Workers: $WORKERS"

# Configure Prometheus multiprocess mode if using multiple workers
if [ "$WORKERS" -gt 1 ]; then
    echo "Configuring Prometheus multiprocess mode for $WORKERS workers"
    export prometheus_multiproc_dir="/tmp/prometheus_multiproc_dir"

    # Clean up any old .db files (but keep the directory)
    # The directory is pre-created in Dockerfile with proper ownership
    rm -f "$prometheus_multiproc_dir"/*.db 2>/dev/null || true

    # Verify directory exists and is writable
    if [ -d "$prometheus_multiproc_dir" ] && [ -w "$prometheus_multiproc_dir" ]; then
        echo "Prometheus multiprocess directory ready at: $prometheus_multiproc_dir"
        ls -la "$prometheus_multiproc_dir" || true
    else
        echo "WARNING: Prometheus multiprocess directory not accessible, attempting to create..."
        # Try to create it if it doesn't exist (shouldn't happen in Docker)
        mkdir -p "$prometheus_multiproc_dir" 2>/dev/null || true

        # Check again
        if [ -d "$prometheus_multiproc_dir" ] && [ -w "$prometheus_multiproc_dir" ]; then
            echo "Prometheus multiprocess directory created successfully"
        else
            echo "ERROR: Failed to access Prometheus multiprocess directory"
            echo "Falling back to single worker mode"
            WORKERS=1
            unset prometheus_multiproc_dir
        fi
    fi
else
    echo "Using single worker mode - no multiprocess configuration needed"
    # Ensure the environment variable is not set for single worker mode
    unset prometheus_multiproc_dir
fi

# Start with Gunicorn using inline configuration
# Note: Access logs disabled (no --access-logfile) to reduce noise.
exec /app/.venv/bin/gunicorn \
     -w "$WORKERS" \
     -k uvicorn.workers.UvicornWorker \
     -b 0.0.0.0:${PORT:-8088} \
     --log-level "$UVICORN_LOG_LEVEL" \
     --error-logfile - \
     --preload \
     --timeout 30 \
     --max-requests 1000 \
     --max-requests-jitter 200 \
     src.main:app
