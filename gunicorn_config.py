"""
Gunicorn configuration for the Order Generation Service.

This configuration ensures proper initialization of each worker process,
particularly for database connections and Beanie ODM initialization.
"""

import asyncio
import logging
import os

# Gunicorn configuration
bind = f"0.0.0.0:{os.getenv('PORT', '8088')}"
workers = int(os.getenv('WORKERS', '4'))
worker_class = "uvicorn.workers.UvicornWorker"
preload_app = True

# Logging configuration
log_level = os.getenv('LOG_LEVEL', 'INFO').lower()
access_logfile = "-"
error_logfile = "-"

# Worker configuration
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
timeout = 30
keepalive = 2

# Configure Prometheus multiprocess mode if using multiple workers
if workers > 1:
    prometheus_multiproc_dir = "/tmp/prometheus_multiproc_dir"
    os.environ["prometheus_multiproc_dir"] = prometheus_multiproc_dir
    os.makedirs(prometheus_multiproc_dir, exist_ok=True)


def worker_init(worker):
    """
    Initialize each worker process.

    Basic worker initialization - database initialization is handled
    by the application lifespan manager.
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Worker {worker.pid} starting")


def worker_exit(server, worker):
    """
    Clean up when worker process exits.
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Worker {worker.pid} shutting down")


def on_starting(server):
    """
    Called just before the master process is initialized.
    """
    logger = logging.getLogger(__name__)
    logger.info("Gunicorn master process starting")


def on_reload(server):
    """
    Called to recycle workers during a reload via SIGHUP.
    """
    logger = logging.getLogger(__name__)
    logger.info("Gunicorn reloading workers")


def when_ready(server):
    """
    Called just after the server is started.
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Gunicorn server ready with {workers} workers on {bind}")


def on_exit(server):
    """
    Called just before exiting Gunicorn.
    """
    logger = logging.getLogger(__name__)
    logger.info("Gunicorn master process exiting")
