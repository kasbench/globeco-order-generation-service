# Worker Configuration Guide for Benchmark Applications

## Overview

This guide explains the worker configuration strategy for the Order Generation Service, specifically optimized for benchmark scenarios where the service typically runs with a single replica.

## Current Configuration

```python
workers = 3                    # Number of worker processes
max_requests = 1000           # Restart worker after N requests
max_requests_jitter = 200     # Random jitter to prevent simultaneous restarts
timeout = 30                  # Request timeout in seconds
worker_connections = 1000     # Max concurrent connections per worker
```

## Why 3 Workers?

### Advantages

1. **High Availability During Restarts**
   - When one worker restarts, 2 remain active (66% capacity maintained)
   - No service interruption during worker recycling
   - Critical for single-replica deployments

2. **Optimal Resource Utilization**
   - Good balance for 2-4 CPU cores (typical pod allocation)
   - Not too many workers competing for resources
   - Efficient memory usage per worker

3. **Benchmark Consistency**
   - Provides stable, predictable performance
   - Reduces variance in benchmark results
   - Handles concurrent requests well

4. **Memory Leak Protection**
   - Workers restart after 800-1200 requests (with jitter)
   - Prevents long-running memory accumulation
   - Maintains consistent performance over time

### Comparison with Other Options

| Workers | Pros | Cons | Best For |
|---------|------|------|----------|
| 1 | Simple, no multiprocess complexity | Zero availability during restart, single point of failure | Development only |
| 2 | Minimal resources | Only 50% capacity during restart | Light workloads |
| **3** | **Good availability (66%), balanced resources** | **Slightly more memory** | **Single replica production** |
| 4+ | Maximum throughput | Higher memory, more complex | Multi-replica deployments |

## Max Requests and Jitter Explained

### The Problem

Without jitter, all workers restart at the same request count, causing:
- Complete service outage (all workers down simultaneously)
- Request failures during restart window
- Poor user experience

### The Solution: Jitter

**max_requests_jitter = 200** means each worker restarts at a random point:

```
Worker 1: 800-1200 requests (random)
Worker 2: 800-1200 requests (random)
Worker 3: 800-1200 requests (random)
```

### Why 200 is the Right Value

With 3 workers and a 400-request spread (1000 ± 200):

**Probability of simultaneous restart:**
- Window size: 400 requests
- Per-worker restart window: ~1 request
- Probability all 3 restart together: ~0.0006% (negligible)

**Practical outcome:**
- Workers restart at different times
- Always 2-3 workers available
- Smooth, rolling restarts
- No service interruption

### Why 50 Was Too Low

With `max_requests_jitter = 50`:
- Window size: 100 requests (950-1050)
- Much higher chance of overlap
- Risk of 2+ workers restarting simultaneously
- Potential service degradation

## Calculation Guide

### Formula for Safe Jitter

```
min_jitter = (max_requests / workers) * safety_factor

For 3 workers:
min_jitter = (1000 / 3) * 0.5 = 167

Recommended: 200 (adds extra safety margin)
```

### General Rules

1. **More workers = less jitter needed** (but still use generous jitter)
2. **Fewer workers = more jitter needed** (critical for availability)
3. **Single replica = maximize jitter** (no other pods to handle load)
4. **Multi-replica = can use less jitter** (other pods available)

## Configuration for Different Scenarios

### Single Replica (Current - Benchmark)
```python
workers = 3
max_requests = 1000
max_requests_jitter = 200
```
**Rationale**: Maximum availability, no other replicas to fall back on

### Multi-Replica Production (2+ replicas)
```python
workers = 2
max_requests = 1000
max_requests_jitter = 100
```
**Rationale**: Other replicas handle load during restarts, fewer workers per pod

### High-Traffic Production (3+ replicas)
```python
workers = 4
max_requests = 2000
max_requests_jitter = 300
```
**Rationale**: More throughput per pod, longer worker lifetime

### Development/Testing
```python
workers = 1
max_requests = 0  # Disable auto-restart
max_requests_jitter = 0
```
**Rationale**: Simplicity, easier debugging, no multiprocess complexity

## Monitoring Worker Health

### Key Metrics to Watch

1. **Worker Restart Frequency**
   ```bash
   # Check logs for worker restarts
   kubectl logs <pod> | grep "Worker.*shutting down"
   ```

2. **Request Distribution**
   ```bash
   # Monitor requests per worker
   curl http://localhost:8088/metrics | grep worker_requests
   ```

3. **Memory Usage Per Worker**
   ```bash
   # Check memory growth over time
   kubectl top pod <pod-name>
   ```

4. **Concurrent Requests**
   ```bash
   # Monitor in-flight requests
   curl http://localhost:8088/metrics | grep http_requests_in_flight
   ```

### Warning Signs

- **All workers restart within 60 seconds**: Jitter too low
- **Memory grows continuously**: max_requests too high
- **Frequent timeouts**: Workers overloaded, increase count
- **High CPU with low throughput**: Too many workers (context switching)

## Tuning Recommendations

### When to Increase Workers

- CPU utilization consistently > 80%
- Request queue building up
- Response times increasing
- More than 4 CPU cores available

### When to Decrease Workers

- Memory pressure (OOM kills)
- CPU utilization < 40%
- Fewer than 2 CPU cores available
- Development/testing environment

### When to Increase max_requests

- Workers restart too frequently (< 5 minutes)
- No memory leak observed
- Stable memory usage over time
- Want longer worker lifetime

### When to Decrease max_requests

- Memory leaks detected
- Memory usage grows over time
- Workers become slow after many requests
- Want more frequent recycling

## Environment Variable Override

You can override the defaults at runtime:

```bash
# Set custom worker count
export WORKERS=4

# Set custom max requests (via gunicorn args)
# Edit gunicorn_config.py or startup script

# For Kubernetes
kubectl set env deployment/order-generation-service WORKERS=4
```

## Best Practices

1. **Always use jitter in production** (never set to 0)
2. **Jitter should be at least 20% of max_requests**
3. **For single replica: jitter = max_requests / workers**
4. **Monitor worker restart patterns** after changes
5. **Test configuration under load** before production
6. **Document any custom settings** in deployment notes

## Troubleshooting

### Problem: Service becomes unavailable periodically

**Cause**: All workers restarting simultaneously

**Solution**: Increase `max_requests_jitter`

```python
max_requests_jitter = 300  # Increase from 200
```

### Problem: Memory usage grows continuously

**Cause**: Workers not restarting frequently enough

**Solution**: Decrease `max_requests`

```python
max_requests = 500  # Decrease from 1000
```

### Problem: Workers restart too frequently

**Cause**: max_requests too low for traffic volume

**Solution**: Increase `max_requests`

```python
max_requests = 2000  # Increase from 1000
```

### Problem: High CPU, low throughput

**Cause**: Too many workers causing context switching

**Solution**: Decrease workers

```python
workers = 2  # Decrease from 3
```

## Testing Your Configuration

### Load Test Script

```bash
#!/bin/bash
# Test worker restart behavior

echo "Starting load test..."

# Generate load for 5 minutes
for i in {1..5000}; do
    curl -s http://localhost:8088/api/v1/models > /dev/null &

    # Limit concurrent requests
    if [ $(jobs -r | wc -l) -gt 50 ]; then
        wait -n
    fi
done

wait

echo "Load test complete. Check logs for worker restarts:"
kubectl logs <pod> | grep "Worker.*shutting down" | tail -20
```

### Verify Jitter is Working

```bash
# Monitor worker restarts over time
kubectl logs -f <pod> | grep "Worker.*shutting down" | while read line; do
    echo "$(date): $line"
done
```

You should see restarts spread out over time, not clustered together.

## Summary

**For your benchmark application with single replica:**

✅ **3 workers** - Optimal balance of availability and resources
✅ **max_requests = 1000** - Good for memory leak prevention
✅ **max_requests_jitter = 200** - Ensures rolling restarts, no downtime

This configuration ensures:
- No service interruption during worker restarts
- Consistent benchmark performance
- Protection against memory leaks
- Efficient resource utilization

**Key Takeaway**: The jitter is more important than the worker count for single-replica deployments. Always ensure jitter is large enough to prevent simultaneous restarts.
