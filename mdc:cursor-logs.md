- Updated .pre-commit-config.yaml: Modified the check-yaml hook's exclude pattern to also skip all files in the k8s directory, suppressing YAML syntax errors in k8s/*.yaml during pre-commit hooks, as requested by the user.

---

## [Instrumentation] OpenTelemetry Metrics & Tracing (2024-06-10)

**Prompt:** Instrument this microservice to send metrics and traces to the opentelemetry collector. Please follow the guidance in @PYTHON_OTEL_INSTRUMENTATION_GUIDE.md for consistency with other microservices in the GlobeCo suite. Please refer to @OTEL_CONFIGURATION_GUIDE.md for URLs and ports. The name of this service is "globeco-order-generation-service".

**Actions Taken:**
- Added all required OpenTelemetry dependencies to `pyproject.toml`:
  - `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-instrumentation`, `opentelemetry-exporter-otlp`, `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-httpx`, `opentelemetry-instrumentation-logging` (all at GlobeCo standard versions).
- Installed dependencies with `uv pip install`.
- Instrumented FastAPI app in `src/main.py`:
  - Initialized OpenTelemetry resource with `service.name = "globeco-order-generation-service"`.
  - Configured both gRPC and HTTP OTLP exporters for traces and metrics, using endpoints from @OTEL_CONFIGURATION_GUIDE.md.
  - Instrumented FastAPI, HTTPX, and logging for tracing and metrics.
  - Mounted Prometheus `/metrics` endpoint using `prometheus_client.make_asgi_app()` (OpenTelemetry/Prometheus standard).
- Removed the custom `/metrics` endpoint from `setup_monitoring` in `src/core/monitoring.py` to avoid duplicate endpoints and ensure compatibility.
- Retained all other Prometheus and business metrics logic for backward compatibility.

**References:**
- [PYTHON_OTEL_INSTRUMENTATION_GUIDE.md]
- [OTEL_CONFIGURATION_GUIDE.md]

**Service Name Used:** `globeco-order-generation-service`

**Result:**
- The service now emits traces and metrics to the OpenTelemetry Collector as per GlobeCo standards. The `/metrics` endpoint is Prometheus-compatible and OpenTelemetry-compliant. No duplicate metrics endpoints. All business and system metrics remain available.
