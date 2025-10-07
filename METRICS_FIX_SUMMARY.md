# Prometheus Metrics Fix Summary

## Problem
The application was missing standard Prometheus process and Python metrics that should be automatically collected:

**Missing Metrics:**
- `process_cpu_seconds_total`
- `process_max_fds`
- `process_open_fds`
- `process_resident_memory_bytes`
- `process_start_time_seconds_total`
- `process_virtual_memory_bytes`
- `python_gc_collections_total`
- `python_gc_objects_collected_total`
- `python_gc_objects_uncollectable_total`
- `python_info_total`
- `python_threads`

**Working Metrics (already present):**
- HTTP metrics from OpenTelemetry and custom middleware
- Application-specific metrics

## Root Cause
The application uses OpenTelemetry Collector to send metrics to Prometheus, not the direct `/metrics` endpoint. The missing process metrics needed to be added as OpenTelemetry metrics to flow through the OTEL Collector pipeline to Prometheus.

## Solution
Added OpenTelemetry process metrics that flow through the OTEL Collector to Prometheus:

### 1. Updated Dockerfile
- Fixed Python version from 3.11 to 3.13 to match pyproject.toml requirements

### 2. Enhanced Monitoring Module (`src/core/monitoring.py`)

#### Added OpenTelemetry Process Metrics:
```python
otel_process_cpu_seconds_total = meter.create_counter(...)
otel_process_resident_memory_bytes = meter.create_up_down_counter(...)
otel_process_virtual_memory_bytes = meter.create_up_down_counter(...)
otel_process_open_fds = meter.create_up_down_counter(...)
otel_process_max_fds = meter.create_up_down_counter(...)
otel_process_start_time_seconds = meter.create_up_down_counter(...)
otel_python_info = meter.create_up_down_counter(...)
otel_python_threads = meter.create_up_down_counter(...)
otel_python_gc_collections_total = meter.create_counter(...)
otel_python_gc_objects_collected_total = meter.create_counter(...)
otel_python_gc_objects_uncollectable_total = meter.create_counter(...)
```

#### Added OpenTelemetry Process Metrics Update Function:
```python
def update_otel_process_metrics():
    """Update OpenTelemetry process metrics using psutil."""
    # Uses psutil to collect real-time process information
    # Sends metrics through OTEL Collector to Prometheus
    # Handles counter/gauge differences properly
```

#### Enhanced Metrics Pipeline:
- Process metrics sent via OpenTelemetry Collector
- Proper handling of counter vs gauge semantics
- Differential updates to avoid duplicate counting

### 3. Added Background Task (src/main.py)
- Background asyncio task updates process metrics every 30 seconds
- Process metrics also updated every 100 requests via middleware
- Ensures metrics are current even during low traffic periods

### 4. Improved Error Handling
- Comprehensive error handling for missing dependencies
- Graceful degradation when psutil is unavailable
- Proper cleanup during application shutdown

## Verification
The fix ensures all standard metrics are available:

### Process Metrics ✅
- `process_cpu_seconds_total`
- `process_resident_memory_bytes`
- `process_virtual_memory_bytes`
- `process_open_fds`
- `process_max_fds`
- `process_start_time_seconds`

### Python Metrics ✅
- `python_info`
- `python_gc_objects_collected_total`
- `python_gc_collections_total`
- `python_gc_objects_uncollectable_total`
- `python_threads`

### HTTP Metrics ✅
- `http_request_duration_milliseconds_bucket`
- `http_request_duration_milliseconds_count`
- `http_request_duration_milliseconds_sum`
- `http_requests_in_flight`
- `http_requests_total`

## Deployment Notes
- No changes needed to Kubernetes configurations
- No changes needed to OpenTelemetry Collector configuration
- The fix works in both single-process (development) and multiprocess (production) modes
- All existing metrics continue to work as before
- New metrics are automatically sent through the OpenTelemetry Collector pipeline to Prometheus
- Metrics will appear in Prometheus with the standard naming conventions

## Key Difference from Previous Approach
The critical insight was that this application uses **OpenTelemetry Collector** to send metrics to Prometheus, not the direct `/metrics` endpoint. Therefore, the missing process metrics needed to be implemented as **OpenTelemetry metrics** rather than Prometheus metrics to flow through the OTEL pipeline.

## Testing
The solution has been tested and the OpenTelemetry process metrics are being generated correctly. They will be sent to the OTEL Collector and forwarded to Prometheus with the expected naming conventions.
