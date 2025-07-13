#!/bin/bash
set -e

# Convert LOG_LEVEL to lowercase for gunicorn
GUNICORN_LOG_LEVEL=$(echo "${LOG_LEVEL:-INFO}" | tr '[:upper:]' '[:lower:]')

# Start gunicorn with proper log level
exec /app/.venv/bin/gunicorn src.main:app \
     --worker-class uvicorn.workers.UvicornWorker \
     --workers 4 \
     --bind 0.0.0.0:${PORT:-8088} \
     --access-logfile - \
     --error-logfile - \
     --log-level "$GUNICORN_LOG_LEVEL" \
     --timeout 30 \
     --keep-alive 2 \
     --max-requests 1000 \
     --max-requests-jitter 100
