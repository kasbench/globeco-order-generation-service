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
accesslog = None  # Disable access logs (set to "-" to re-enable)
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

    # Create directory with proper permissions
    os.makedirs(prometheus_multiproc_dir, exist_ok=True)
    os.chmod(prometheus_multiproc_dir, 0o755)

    # Clean up any existing metrics files at startup
    import glob

    for db_file in glob.glob(os.path.join(prometheus_multiproc_dir, "*.db")):
        try:
            os.remove(db_file)
        except OSError:
            pass  # Ignore if file doesn't exist or can't be removed


def worker_init(worker):
    """
    Initialize each worker process.

    Basic worker initialization - database initialization is handled
    by the application lifespan manager.
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Worker {worker.pid} starting")

    # Ensure Prometheus multiprocess directory is accessible for this worker
    if workers > 1 and "prometheus_multiproc_dir" in os.environ:
        prometheus_dir = os.environ["prometheus_multiproc_dir"]
        if os.path.exists(prometheus_dir):
            # Verify directory is writable
            try:
                test_file = os.path.join(prometheus_dir, f"test_worker_{worker.pid}")
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
                logger.info(
                    f"Worker {worker.pid}: Prometheus multiprocess directory is accessible"
                )
            except Exception as e:
                logger.error(
                    f"Worker {worker.pid}: Prometheus multiprocess directory not writable: {e}"
                )
        else:
            logger.warning(
                f"Worker {worker.pid}: Prometheus multiprocess directory does not exist: {prometheus_dir}"
            )


def worker_exit(server, worker):
    """
    Clean up when worker process exits.
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Worker {worker.pid} shutting down")

    # Clean up Prometheus multiprocess files for this worker
    if workers > 1 and "prometheus_multiproc_dir" in os.environ:
        prometheus_dir = os.environ["prometheus_multiproc_dir"]
        if os.path.exists(prometheus_dir):
            import glob

            # Remove files specific to this worker PID
            worker_files = glob.glob(os.path.join(prometheus_dir, f"*_{worker.pid}.db"))
            for file_path in worker_files:
                try:
                    os.remove(file_path)
                    logger.debug(f"Cleaned up Prometheus file: {file_path}")
                except Exception as e:
                    logger.warning(
                        f"Failed to clean up Prometheus file {file_path}: {e}"
                    )


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
