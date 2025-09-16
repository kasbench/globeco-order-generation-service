#!/bin/bash
set -e

# Convert LOG_LEVEL to lowercase for uvicorn
UVICORN_LOG_LEVEL=$(echo "${LOG_LEVEL:-INFO}" | tr '[:upper:]' '[:lower:]')

echo "Starting GlobeCo Order Generation Service..."
echo "Port: ${PORT:-8088}"
echo "Log Level: $UVICORN_LOG_LEVEL"

# Start uvicorn directly (single process for consistent metrics)
# exec /app/.venv/bin/uvicorn src.main:app \
#      --host 0.0.0.0 \
#      --port ${PORT:-8088} \
#      --log-level "$UVICORN_LOG_LEVEL" \
#      --access-log \
#      --no-use-colors

exec /app/.venv/bin/gunicorn \
     -w 4 \
     -k uvicorn.workers.UvicornWorker \
     -b 0.0.0.0:8088 \
     --threads 1 \
     --log-level "$UVICORN_LOG_LEVEL" \
     --access-logfile - \
     --error-logfile - \
     src.main:app
