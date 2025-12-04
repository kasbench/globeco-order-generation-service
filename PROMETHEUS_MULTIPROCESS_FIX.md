# Prometheus Multiprocess Mode Fix

## Problem
The application was experiencing errors when running with multiple Gunicorn workers:

1. **FileNotFoundError**: `/tmp/prometheus_multiproc_dir/*.db` files not found
2. **TypeError**: `'NoneType' object does not support item assignment` when trying to write to mmap files

## Root Causes

1. **Insufficient Directory Permissions**: Directory was created with 755 permissions instead of 777
2. **Race Conditions**: Workers trying to access files before they were created
3. **Stale File Issues**: Old mmap files persisting between restarts
4. **Missing Directory in Container**: The `/tmp/prometheus_multiproc_dir` wasn't pre-created in the Docker image

## Solution

### 1. Dockerfile Changes
- Pre-create `/tmp/prometheus_multiproc_dir` with 777 permissions in the production image
- Ensures the directory exists before any workers start

### 2. Startup Script Changes (`scripts/start-production.sh`)
- Completely remove old directory before creating new one
- Create directory with 777 permissions (not 755)
- Add verification that directory is writable
- Fallback to single worker mode if directory creation fails

### 3. Gunicorn Config Changes (`gunicorn_config.py`)
- Use `mode=0o777` when creating directory
- Force permissions even if directory already exists
- Better error handling for permission issues

### 4. Monitoring Module Changes (`src/core/monitoring.py`)
- Add PID-specific test files to avoid conflicts during initialization
- Better error handling for multiprocess mode failures
- Graceful fallback to single process mode if multiprocess fails
- Add null checks before accessing metric objects
- Wrap metric operations in try-except blocks to prevent crashes

## How Prometheus Multiprocess Mode Works

When running with multiple Gunicorn workers, each worker process needs to write metrics to shared memory-mapped files in `/tmp/prometheus_multiproc_dir/`. The files are named with patterns like:
- `counter_<PID>.db`
- `histogram_<PID>.db`
- `gauge_<PID>.db`
- `summary_<PID>.db`

The `MultiProcessCollector` aggregates metrics from all these files when the `/metrics` endpoint is scraped.

## Testing

To verify the fix:

1. **Build the new image**:
   ```bash
   docker build -t order-generation-service .
   ```

2. **Run with multiple workers**:
   ```bash
   docker run -e WORKERS=4 -p 8088:8088 order-generation-service
   ```

3. **Check logs for success messages**:
   ```
   Prometheus multiprocess directory configured at: /tmp/prometheus_multiproc_dir
   Prometheus multiprocess mode enabled with directory: /tmp/prometheus_multiproc_dir
   ```

4. **Verify metrics endpoint**:
   ```bash
   curl http://localhost:8088/metrics
   ```

5. **Check for errors**:
   - No `FileNotFoundError` in logs
   - No `TypeError: 'NoneType' object does not support item assignment`
   - Metrics are being collected successfully

## Fallback Behavior

If multiprocess mode fails to initialize:
- The application logs a warning
- Falls back to single process mode
- Continues to operate (metrics may be incomplete but service remains functional)
- In startup script: automatically reduces WORKERS to 1 if directory creation fails

## Permissions Explanation

Why 777 permissions?
- Multiple worker processes (running as `appuser`) need to create and write to files
- Each worker creates its own PID-specific `.db` files
- Workers need to read other workers' files for aggregation
- 777 ensures all workers have full read/write access
- This is safe because `/tmp` is container-local and not exposed

## Related Files Modified

1. `Dockerfile` - Added directory creation
2. `scripts/start-production.sh` - Improved directory setup and verification
3. `gunicorn_config.py` - Better permissions and error handling
4. `src/core/monitoring.py` - Robust error handling and fallback logic
