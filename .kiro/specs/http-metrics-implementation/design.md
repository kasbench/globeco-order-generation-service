# Design Document

## Overview

This design implements standardized HTTP request metrics for the FastAPI-based portfolio rebalancing service according to the enhanced metrics requirements. The implementation will enhance the existing monitoring infrastructure to provide OpenTelemetry-compatible metrics that can be exported to the Otel Collector.

The current system already has some monitoring capabilities through `prometheus-fastapi-instrumentator` and custom metrics in `src/core/monitoring.py`. This design will standardize and enhance these metrics to meet the exact specifications required.

## Architecture

### Current State Analysis

The application currently has:
- OpenTelemetry instrumentation configured in `main.py`
- Prometheus metrics endpoint mounted at `/metrics`
- Custom `MetricsMiddleware` in `src/core/monitoring.py`
- Various custom metrics (REQUEST_COUNT, REQUEST_DURATION, etc.)

### Target Architecture

The enhanced implementation will:
1. **Standardize Metric Names**: Align existing metrics with required naming conventions
2. **Implement Missing Metrics**: Add the `http_requests_in_flight` gauge
3. **Correct Histogram Buckets**: Use millisecond-based buckets as specified
4. **Enhance Label Consistency**: Ensure proper label formatting and route pattern extraction
5. **Maintain OpenTelemetry Compatibility**: Ensure metrics work with existing Otel setup

## Components and Interfaces

### 1. Enhanced HTTP Metrics Middleware

**Location**: `src/core/monitoring.py` (enhance existing `MetricsMiddleware`)

**Responsibilities**:
- Collect all three required HTTP metrics
- Implement proper label extraction and formatting
- Handle timing with millisecond precision
- Manage in-flight request tracking

**Key Methods**:
```python
class EnhancedHTTPMetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response
    def _extract_route_pattern(self, request: Request) -> str
    def _format_status_code(self, status_code: int) -> str
    def _get_method_label(self, method: str) -> str
```

### 2. Standardized Metrics Definitions

**Location**: `src/core/monitoring.py` (replace existing metrics)

**Metrics to Implement**:

1. **HTTP Requests Total Counter**
   - Name: `http_requests_total`
   - Labels: `method`, `path`, `status`
   - Type: Counter

2. **HTTP Request Duration Histogram**
   - Name: `http_request_duration`
   - Labels: `method`, `path`, `status`
   - Type: Histogram
   - Unit: Milliseconds
   - Buckets: `[5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000]`

3. **HTTP Requests In Flight Gauge**
   - Name: `http_requests_in_flight`
   - Labels: None
   - Type: Gauge

### 3. Route Pattern Extraction

**Location**: `src/core/monitoring.py` (enhance existing `_get_endpoint_label`)

**Functionality**:
- Extract FastAPI route patterns from requests
- Handle parameterized routes (e.g., `/api/v1/models/{model_id}`)
- Sanitize sensitive data from paths
- Provide fallback for unmatched routes

### 4. Metrics Export Integration

**Location**: `src/main.py` (enhance existing setup)

**Integration Points**:
- Ensure compatibility with existing `/metrics` endpoint
- Maintain OpenTelemetry exporter configuration
- Preserve existing Prometheus client setup

## Data Models

### Metric Label Structure

```python
@dataclass
class HTTPMetricLabels:
    method: str      # Uppercase HTTP method (GET, POST, etc.)
    path: str        # Route pattern (/api/v1/models/{id})
    status: str      # String status code ("200", "404", "500")
```

### Route Pattern Mapping

```python
ROUTE_PATTERNS = {
    r'^/api/v1/models/[^/]+/?$': '/api/v1/models/{model_id}',
    r'^/api/v1/models/[^/]+/[^/]+/?$': '/api/v1/models/{model_id}/{action}',
    r'^/api/v1/rebalance/[^/]+/?$': '/api/v1/rebalance/{portfolio_id}',
    r'^/health/[^/]+/?$': '/health/{check_type}',
}
```

## Error Handling

### Metrics Collection Failures

1. **Metric Recording Errors**:
   - Log error but continue request processing
   - Use try-catch blocks around metric operations
   - Provide fallback values for label extraction

2. **Timing Accuracy**:
   - Use high-precision timing (`time.perf_counter()`)
   - Handle clock adjustments gracefully
   - Ensure timing stops even on exceptions

3. **Label Value Sanitization**:
   - Remove sensitive data from paths
   - Handle malformed URLs gracefully
   - Provide default values for missing labels

### Exception Scenarios

```python
try:
    # Metric recording logic
    REQUEST_COUNT.labels(method=method, path=path, status=status).inc()
except Exception as e:
    logger.error("Failed to record HTTP metrics", error=str(e), exc_info=True)
    # Continue processing request
```

## Testing Strategy

### Unit Tests

**Location**: `src/tests/unit/test_http_metrics.py`

**Test Coverage**:
1. **Metric Creation and Registration**
   - Verify all three metrics are properly initialized
   - Test metric type correctness (Counter, Histogram, Gauge)
   - Validate histogram bucket configuration

2. **Label Extraction**
   - Test route pattern extraction for various endpoints
   - Verify status code formatting
   - Test method name normalization

3. **Timing Accuracy**
   - Test duration measurement precision
   - Verify millisecond unit conversion
   - Test timing under exception conditions

4. **In-Flight Request Tracking**
   - Test gauge increment/decrement behavior
   - Verify concurrent request handling
   - Test cleanup on exceptions

### Integration Tests

**Location**: `src/tests/integration/test_metrics_integration.py`

**Test Scenarios**:
1. **End-to-End Metric Collection**
   - Make HTTP requests and verify metrics are recorded
   - Test various endpoints and status codes
   - Verify metric values match expected patterns

2. **Prometheus Export**
   - Test `/metrics` endpoint returns proper format
   - Verify metric names and labels in output
   - Test HELP and TYPE declarations

3. **OpenTelemetry Compatibility**
   - Verify metrics are exported to Otel Collector
   - Test metric format compatibility
   - Validate label transformation

### Performance Tests

**Location**: `src/tests/performance/test_metrics_performance.py`

**Performance Criteria**:
- Metrics collection overhead < 1ms per request
- Memory usage increase < 10MB under load
- No significant impact on request throughput

## Implementation Phases

### Phase 1: Core Metrics Implementation
1. Update metric definitions with correct names and buckets
2. Implement enhanced middleware with proper timing
3. Add in-flight request tracking

### Phase 2: Label Enhancement
1. Implement route pattern extraction
2. Add proper label formatting
3. Enhance error handling

### Phase 3: Integration and Testing
1. Update existing middleware registration
2. Implement comprehensive test suite
3. Validate OpenTelemetry compatibility

### Phase 4: Documentation and Validation
1. Update configuration documentation
2. Validate metrics in monitoring dashboards
3. Verify alerting rule compatibility

## Configuration Changes

### Settings Updates

**Location**: `src/config.py`

```python
class Settings(BaseSettings):
    # Existing metrics configuration
    enable_metrics: bool = Field(default=True, description="Enable Prometheus metrics")

    # New HTTP metrics specific settings
    http_metrics_buckets: list[float] = Field(
        default=[5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000],
        description="HTTP request duration histogram buckets in milliseconds"
    )
    http_metrics_high_cardinality_limit: int = Field(
        default=1000,
        description="Maximum number of unique path labels to prevent high cardinality"
    )
```

### Middleware Registration

**Location**: `src/main.py`

```python
# Replace existing MetricsMiddleware with enhanced version
if settings.enable_metrics:
    app.add_middleware(EnhancedHTTPMetricsMiddleware)
```

## Compatibility Considerations

### Backward Compatibility
- Maintain existing metric names where possible
- Preserve existing Prometheus endpoint functionality
- Keep OpenTelemetry configuration unchanged

### Migration Strategy
- Gradual replacement of existing metrics
- Maintain both old and new metrics during transition
- Provide configuration flags for rollback

### Monitoring Dashboard Updates
- Update Grafana dashboards to use new metric names
- Adjust alerting rules for new label structure
- Document metric name changes for operations team
