# Prometheus Multiprocess Mode Troubleshooting Guide

## Quick Diagnosis

If you see these errors in your logs:
```
FileNotFoundError: [Errno 2] No such file or directory: '/tmp/prometheus_multiproc_dir/counter_XXXXX.db'
TypeError: 'NoneType' object does not support item assignment
```

The Prometheus multiprocess mode is not properly configured.

## Quick Fix

### Option 1: Rebuild and Restart (Recommended)
```bash
# Rebuild the Docker image with the fix
docker build -t order-generation-service .

# Restart the service
docker-compose down
docker-compose up -d
```

### Option 2: Manual Fix in Running Container
```bash
# Enter the container
docker exec -it <container-name> bash

# Create the directory with proper permissions
mkdir -p /tmp/prometheus_multiproc_dir
chmod 777 /tmp/prometheus_multiproc_dir

# Restart the service
docker-compose restart order-generation-service
```

## Verification

Run the test script:
```bash
docker exec -it <container-name> /app/scripts/test-prometheus-multiprocess.sh
```

Or manually check:
```bash
# Check directory exists and has correct permissions
docker exec -it <container-name> ls -la /tmp/prometheus_multiproc_dir

# Check metrics endpoint
curl http://localhost:8088/metrics | grep process_cpu_seconds_total

# Check logs for errors
docker logs <container-name> 2>&1 | grep -i "prometheus\|FileNotFoundError\|NoneType"
```

## Understanding the Issue

### What is Prometheus Multiprocess Mode?

When running with multiple Gunicorn workers (WORKERS > 1), each worker process needs to write metrics independently. Prometheus uses memory-mapped files in a shared directory to aggregate metrics from all workers.

### Why Does It Fail?

1. **Missing Directory**: The directory doesn't exist when workers start
2. **Wrong Permissions**: Workers can't write to the directory (755 instead of 777)
3. **Stale Files**: Old mmap files from previous runs cause conflicts
4. **Race Conditions**: Workers try to access files before they're created

### How the Fix Works

1. **Dockerfile**: Pre-creates `/tmp/prometheus_multiproc_dir` with 777 permissions
2. **Startup Script**: Cleans old files and verifies directory is writable
3. **Gunicorn Config**: Ensures proper permissions on startup
4. **Monitoring Module**: Gracefully handles failures and falls back to single process mode

## Configuration

### Environment Variables

- `WORKERS`: Number of Gunicorn workers (default: 4)
  - Set to 1 to disable multiprocess mode
  - Set to > 1 to enable multiprocess mode

- `prometheus_multiproc_dir`: Directory for mmap files (default: `/tmp/prometheus_multiproc_dir`)
  - Automatically set by startup script when WORKERS > 1
  - Must have 777 permissions
  - Must be writable by all workers

### Single Worker Mode

If you don't need multiple workers, set:
```bash
export WORKERS=1
```

This disables multiprocess mode entirely and avoids the complexity.

### Multiple Worker Mode

For production with multiple workers:
```bash
export WORKERS=4  # or more based on CPU cores
```

The startup script will automatically configure multiprocess mode.

## Common Issues

### Issue: "Directory not writable"

**Symptom**: Logs show "Prometheus multiprocess directory not writable"

**Solution**:
```bash
chmod 777 /tmp/prometheus_multiproc_dir
```

### Issue: "FileNotFoundError" for .db files

**Symptom**: Errors about missing counter_*.db, histogram_*.db files

**Solution**:
```bash
# Clean and recreate directory
rm -rf /tmp/prometheus_multiproc_dir
mkdir -p /tmp/prometheus_multiproc_dir
chmod 777 /tmp/prometheus_multiproc_dir

# Restart service
docker-compose restart order-generation-service
```

### Issue: "NoneType object does not support item assignment"

**Symptom**: TypeError when trying to write metrics

**Solution**: This usually means the mmap file is corrupted or missing. Clean and restart:
```bash
rm -rf /tmp/prometheus_multiproc_dir/*.db
docker-compose restart order-generation-service
```

### Issue: Metrics are missing or incomplete

**Symptom**: `/metrics` endpoint doesn't show expected metrics

**Solution**:
1. Check if multiprocess mode is enabled: `echo $prometheus_multiproc_dir`
2. Check for .db files: `ls -la /tmp/prometheus_multiproc_dir/`
3. Check logs for initialization errors
4. Verify all workers are running: `ps aux | grep gunicorn`

## Monitoring Health

### Check Multiprocess Mode Status

```bash
# Check if directory exists
docker exec <container-name> test -d /tmp/prometheus_multiproc_dir && echo "Directory exists" || echo "Directory missing"

# Check permissions
docker exec <container-name> stat -c "%a" /tmp/prometheus_multiproc_dir

# Check for .db files
docker exec <container-name> ls -la /tmp/prometheus_multiproc_dir/

# Check environment variable
docker exec <container-name> printenv prometheus_multiproc_dir
```

### Check Metrics Collection

```bash
# Test metrics endpoint
curl http://localhost:8088/metrics

# Check for specific metrics
curl http://localhost:8088/metrics | grep -E "process_|http_requests_"

# Count metric types
curl -s http://localhost:8088/metrics | grep -v "^#" | wc -l
```

## Best Practices

1. **Always use the latest Docker image** with the fix included
2. **Set WORKERS based on CPU cores**: `WORKERS=$(nproc)` or `WORKERS=4`
3. **Monitor logs during startup** for Prometheus initialization messages
4. **Use the test script** after deployment to verify everything works
5. **Clean /tmp on container restart** to avoid stale files
6. **Consider single worker mode** for development/testing (WORKERS=1)

## Getting Help

If issues persist:

1. Run the test script: `/app/scripts/test-prometheus-multiprocess.sh`
2. Collect logs: `docker logs <container-name> > prometheus-debug.log`
3. Check directory state: `ls -la /tmp/prometheus_multiproc_dir/`
4. Verify fix is applied: Check `PROMETHEUS_MULTIPROCESS_FIX.md`
5. Review this guide for common issues

## Related Documentation

- `PROMETHEUS_MULTIPROCESS_FIX.md` - Technical details of the fix
- `scripts/test-prometheus-multiprocess.sh` - Automated test script
- `scripts/start-production.sh` - Startup script with multiprocess setup
- `gunicorn_config.py` - Gunicorn configuration
- `src/core/monitoring.py` - Monitoring module implementation
