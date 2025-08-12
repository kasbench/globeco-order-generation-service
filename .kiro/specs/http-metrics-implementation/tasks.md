# Implementation Plan

- [ ] 1. Implement standardized HTTP metrics with correct naming and buckets
  - Replace existing metrics in `src/core/monitoring.py` with standardized versions
  - Use exact metric names: `http_requests_total`, `http_request_duration`, `http_requests_in_flight`
  - Configure histogram with millisecond buckets: [5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000]
  - Ensure metrics use proper types (Counter, Histogram, Gauge)
  - _Requirements: 1.1, 1.2, 2.1, 2.2, 3.1, 3.2, 3.3_

- [ ] 2. Implement enhanced HTTP metrics middleware with proper timing and in-flight tracking
  - Create `EnhancedHTTPMetricsMiddleware` class to replace existing `MetricsMiddleware`
  - Implement millisecond-precision timing using `time.perf_counter()`
  - Add in-flight request tracking with gauge increment/decrement
  - Record all three metrics for every HTTP request
  - Ensure metrics are recorded even when exceptions occur
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 5.1, 5.2, 5.3, 5.4_

- [ ] 3. Implement route pattern extraction and label formatting
  - Create `_extract_route_pattern()` method to convert URLs to route patterns
  - Handle FastAPI parameterized routes (e.g., `/api/v1/models/{model_id}`)
  - Implement proper label formatting: uppercase methods, string status codes
  - Add sanitization for sensitive data in paths
  - Create fallback handling for unmatched routes
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [ ] 4. Update middleware registration and configuration
  - Replace `MetricsMiddleware` with `EnhancedHTTPMetricsMiddleware` in `src/main.py`
  - Ensure middleware processes all HTTP requests including health checks and API endpoints
  - Verify compatibility with existing OpenTelemetry and Prometheus setup
  - Test that `/metrics` endpoint continues to work properly
  - _Requirements: 5.1, 5.2, 6.1, 6.2, 6.3_

- [ ] 5. Add error handling and logging for metrics collection
  - Implement try-catch blocks around all metric recording operations
  - Add structured logging for metrics collection failures
  - Ensure request processing continues even if metrics collection fails
  - Add debug logging for metric values during development
  - _Requirements: 5.4, 6.4_

- [ ] 6. Create comprehensive unit tests for HTTP metrics functionality
  - Write tests in `src/tests/unit/test_http_metrics.py`
  - Test metric creation and registration for all three metric types
  - Verify counter increments correctly for different request scenarios
  - Test histogram duration recording with various request durations
  - Validate gauge tracking for concurrent requests
  - Test label extraction and formatting for various endpoints
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [ ] 7. Create integration tests for end-to-end metrics collection
  - Write tests in `src/tests/integration/test_metrics_integration.py`
  - Test complete request flow with metrics collection
  - Verify `/metrics` endpoint returns properly formatted Prometheus metrics
  - Test metrics for various HTTP methods, status codes, and endpoints
  - Validate metric values match expected patterns after requests
  - Test OpenTelemetry compatibility and export format
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 6.1, 6.2_

- [ ] 8. Add performance tests to ensure minimal overhead
  - Write tests in `src/tests/performance/test_metrics_performance.py`
  - Measure metrics collection overhead per request (target < 1ms)
  - Test memory usage under load scenarios
  - Verify no significant impact on request throughput
  - Benchmark concurrent request handling with in-flight tracking
  - _Requirements: 6.4_

- [ ] 9. Update configuration and documentation
  - Add HTTP metrics configuration options to `src/config.py`
  - Update middleware registration documentation
  - Document new metric names and label structure
  - Add troubleshooting guide for metrics visibility
  - Create examples of expected metrics output format
  - _Requirements: 6.2, 6.3_
