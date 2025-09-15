#!/bin/bash
set -e

# Convert LOG_LEVEL to lowercase for uvicorn
UVICORN_LOG_LEVEL=$(echo "${UVICORN_LOG_LEVEL:-WARNING}" | tr '[:upper:]' '[:lower:]')

# Start uvicorn directly (single process for consistent metrics)
exec /app/.venv/bin/uvicorn src.main:app \
     --host 0.0.0.0 \
     --port ${PORT:-8088} \
     --log-level "$UVICORN_LOG_LEVEL" \
     --access-log \
     --no-use-colors
