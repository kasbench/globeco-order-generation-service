"""
Performance tests for the GlobeCo Order Generation Service API.

These tests validate performance characteristics and load handling capabilities
for use in CI/CD pipelines and benchmarking research.
"""

import asyncio
import statistics
import time
from decimal import Decimal
from typing import Any, Dict, List

import httpx
import pytest
from pytest_benchmark import BenchmarkFixture

# Test configuration
API_BASE_URL = "http://localhost:8080"
PERFORMANCE_TIMEOUT = 30.0  # seconds
CONCURRENT_REQUESTS = 10
LOAD_TEST_DURATION = 15  # seconds


class PerformanceMetrics:
    """Collects and analyzes performance metrics."""

    def __init__(self):
        self.response_times: List[float] = []
        self.success_count = 0
        self.error_count = 0
        self.start_time = 0.0
        self.end_time = 0.0

    def add_response(self, response_time: float, success: bool):
        """Add a response measurement."""
        self.response_times.append(response_time)
        if success:
            self.success_count += 1
        else:
            self.error_count += 1

    def start_timer(self):
        """Start the performance measurement timer."""
        self.start_time = time.time()

    def stop_timer(self):
        """Stop the performance measurement timer."""
        self.end_time = time.time()

    @property
    def total_requests(self) -> int:
        """Total number of requests made."""
        return self.success_count + self.error_count

    @property
    def success_rate(self) -> float:
        """Success rate as a percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.success_count / self.total_requests) * 100

    @property
    def duration(self) -> float:
        """Total test duration in seconds."""
        return self.end_time - self.start_time

    @property
    def requests_per_second(self) -> float:
        """Average requests per second."""
        if self.duration == 0:
            return 0.0
        return self.total_requests / self.duration

    @property
    def avg_response_time(self) -> float:
        """Average response time in milliseconds."""
        if not self.response_times:
            return 0.0
        return statistics.mean(self.response_times) * 1000

    @property
    def p95_response_time(self) -> float:
        """95th percentile response time in milliseconds."""
        if not self.response_times:
            return 0.0
        sorted_times = sorted(self.response_times)
        index = int(0.95 * len(sorted_times))
        return sorted_times[min(index, len(sorted_times) - 1)] * 1000

    @property
    def p99_response_time(self) -> float:
        """99th percentile response time in milliseconds."""
        if not self.response_times:
            return 0.0
        sorted_times = sorted(self.response_times)
        index = int(0.99 * len(sorted_times))
        return sorted_times[min(index, len(sorted_times) - 1)] * 1000

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics."""
        return {
            "total_requests": self.total_requests,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "success_rate": self.success_rate,
            "duration": self.duration,
            "requests_per_second": self.requests_per_second,
            "avg_response_time_ms": self.avg_response_time,
            "p95_response_time_ms": self.p95_response_time,
            "p99_response_time_ms": self.p99_response_time,
        }


@pytest.fixture
async def performance_client():
    """HTTP client for performance testing."""
    async with httpx.AsyncClient(
        base_url=API_BASE_URL, timeout=PERFORMANCE_TIMEOUT
    ) as client:
        # Wait for service to be ready
        max_retries = 30
        for _ in range(max_retries):
            try:
                response = await client.get("/health/ready")
                if response.status_code == 200:
                    break
            except httpx.RequestError:
                pass
            await asyncio.sleep(1)
        else:
            pytest.skip("Service not ready for performance testing")

        yield client


@pytest.fixture
def sample_model_data():
    """Sample model data for performance testing."""
    return {
        "name": "Performance Test Model",
        "positions": [
            {
                "securityId": "PERF000000000000000001",
                "target": "0.25",
                "lowDrift": "0.02",
                "highDrift": "0.03",
            },
            {
                "securityId": "PERF000000000000000002",
                "target": "0.30",
                "lowDrift": "0.02",
                "highDrift": "0.03",
            },
            {
                "securityId": "PERF000000000000000003",
                "target": "0.20",
                "lowDrift": "0.02",
                "highDrift": "0.03",
            },
        ],
        "portfolios": ["507f1f77bcf86cd799439011"],
    }


class TestHealthEndpointPerformance:
    """Performance tests for health endpoints."""

    @pytest.mark.asyncio
    async def test_health_endpoint_response_time(
        self, performance_client: httpx.AsyncClient
    ):
        """Test health endpoint response time under normal load."""
        metrics = PerformanceMetrics()
        metrics.start_timer()

        # Run multiple requests to get average
        for _ in range(100):
            start_time = time.time()
            try:
                response = await performance_client.get("/health/live")
                end_time = time.time()
                metrics.add_response(end_time - start_time, response.status_code == 200)
            except Exception:
                end_time = time.time()
                metrics.add_response(end_time - start_time, False)

        metrics.stop_timer()
        summary = metrics.get_summary()

        # Performance assertions
        assert (
            summary["success_rate"] >= 99.0
        ), f"Health endpoint success rate: {summary['success_rate']:.1f}%"
        assert (
            summary["avg_response_time_ms"] <= 50.0
        ), f"Average response time: {summary['avg_response_time_ms']:.1f}ms"
        assert (
            summary["p95_response_time_ms"] <= 100.0
        ), f"P95 response time: {summary['p95_response_time_ms']:.1f}ms"

        print(f"\nHealth Endpoint Performance:")
        print(f"  Success Rate: {summary['success_rate']:.1f}%")
        print(f"  Average Response Time: {summary['avg_response_time_ms']:.1f}ms")
        print(f"  P95 Response Time: {summary['p95_response_time_ms']:.1f}ms")
        print(f"  Requests/sec: {summary['requests_per_second']:.1f}")

    @pytest.mark.asyncio
    async def test_health_endpoint_concurrent_load(
        self, performance_client: httpx.AsyncClient
    ):
        """Test health endpoint under concurrent load."""
        metrics = PerformanceMetrics()

        async def make_request():
            start_time = time.time()
            try:
                response = await performance_client.get("/health/ready")
                end_time = time.time()
                metrics.add_response(end_time - start_time, response.status_code == 200)
            except Exception:
                end_time = time.time()
                metrics.add_response(end_time - start_time, False)

        metrics.start_timer()

        # Run concurrent requests
        tasks = [make_request() for _ in range(CONCURRENT_REQUESTS)]
        await asyncio.gather(*tasks)

        metrics.stop_timer()
        summary = metrics.get_summary()

        # Concurrent load assertions
        assert (
            summary["success_rate"] >= 95.0
        ), f"Concurrent success rate: {summary['success_rate']:.1f}%"
        assert (
            summary["avg_response_time_ms"] <= 200.0
        ), f"Concurrent avg response time: {summary['avg_response_time_ms']:.1f}ms"

        print(f"\nConcurrent Health Load Test:")
        print(f"  Concurrent Requests: {CONCURRENT_REQUESTS}")
        print(f"  Success Rate: {summary['success_rate']:.1f}%")
        print(f"  Average Response Time: {summary['avg_response_time_ms']:.1f}ms")


class TestModelAPIPerformance:
    """Performance tests for model management APIs."""

    @pytest.mark.asyncio
    async def test_model_list_performance(self, performance_client: httpx.AsyncClient):
        """Test model listing API performance."""
        metrics = PerformanceMetrics()
        metrics.start_timer()

        # Test multiple requests to list models
        for _ in range(50):
            start_time = time.time()
            try:
                response = await performance_client.get("/api/v1/models")
                end_time = time.time()
                metrics.add_response(end_time - start_time, response.status_code == 200)
            except Exception:
                end_time = time.time()
                metrics.add_response(end_time - start_time, False)

        metrics.stop_timer()
        summary = metrics.get_summary()

        # Performance assertions for read operations
        assert (
            summary["success_rate"] >= 95.0
        ), f"Model list success rate: {summary['success_rate']:.1f}%"
        assert (
            summary["avg_response_time_ms"] <= 200.0
        ), f"Model list avg response time: {summary['avg_response_time_ms']:.1f}ms"

        print(f"\nModel List Performance:")
        print(f"  Success Rate: {summary['success_rate']:.1f}%")
        print(f"  Average Response Time: {summary['avg_response_time_ms']:.1f}ms")
        print(f"  P95 Response Time: {summary['p95_response_time_ms']:.1f}ms")

    @pytest.mark.asyncio
    async def test_model_creation_performance(
        self, performance_client: httpx.AsyncClient, sample_model_data: dict
    ):
        """Test model creation API performance."""
        metrics = PerformanceMetrics()
        created_models = []

        try:
            metrics.start_timer()

            # Create multiple models to test performance
            for i in range(10):
                model_data = sample_model_data.copy()
                model_data["name"] = f"Performance Test Model {i}"
                # Ensure unique security IDs
                for j, position in enumerate(model_data["positions"]):
                    position["securityId"] = f"PERF{i:04d}{j:04d}0000000000000"

                start_time = time.time()
                try:
                    response = await performance_client.post(
                        "/api/v1/models", json=model_data
                    )
                    end_time = time.time()
                    success = response.status_code == 201
                    metrics.add_response(end_time - start_time, success)

                    if success:
                        created_models.append(response.json()["id"])
                except Exception:
                    end_time = time.time()
                    metrics.add_response(end_time - start_time, False)

            metrics.stop_timer()
            summary = metrics.get_summary()

            # Performance assertions for write operations
            assert (
                summary["success_rate"] >= 90.0
            ), f"Model creation success rate: {summary['success_rate']:.1f}%"
            assert (
                summary["avg_response_time_ms"] <= 500.0
            ), f"Model creation avg response time: {summary['avg_response_time_ms']:.1f}ms"

            print(f"\nModel Creation Performance:")
            print(f"  Success Rate: {summary['success_rate']:.1f}%")
            print(f"  Average Response Time: {summary['avg_response_time_ms']:.1f}ms")
            print(f"  P95 Response Time: {summary['p95_response_time_ms']:.1f}ms")

        finally:
            # Cleanup created models
            for model_id in created_models:
                try:
                    await performance_client.delete(f"/api/v1/models/{model_id}")
                except Exception:
                    pass  # Ignore cleanup errors


class TestRebalancePerformance:
    """Performance tests for portfolio rebalancing operations."""

    @pytest.mark.asyncio
    async def test_rebalance_calculation_performance(
        self, performance_client: httpx.AsyncClient, sample_model_data: dict
    ):
        """Test rebalancing calculation performance."""
        # Create a test model first
        response = await performance_client.post(
            "/api/v1/models", json=sample_model_data
        )
        if response.status_code != 201:
            pytest.skip("Could not create test model for rebalancing performance test")

        model_id = response.json()["id"]

        try:
            metrics = PerformanceMetrics()
            metrics.start_timer()

            # Test rebalancing performance
            rebalance_data = {
                "portfolioId": "507f1f77bcf86cd799439011",
                "positions": [
                    {
                        "securityId": "PERF000000000000000001",
                        "currentShares": 1000,
                        "currentPrice": "25.50",
                    },
                    {
                        "securityId": "PERF000000000000000002",
                        "currentShares": 800,
                        "currentPrice": "35.75",
                    },
                    {
                        "securityId": "PERF000000000000000003",
                        "currentShares": 600,
                        "currentPrice": "45.25",
                    },
                ],
            }

            # Run multiple rebalancing calculations
            for _ in range(5):  # Fewer iterations for complex operations
                start_time = time.time()
                try:
                    response = await performance_client.post(
                        f"/api/v1/models/{model_id}/rebalance", json=rebalance_data
                    )
                    end_time = time.time()
                    metrics.add_response(
                        end_time - start_time, response.status_code == 200
                    )
                except Exception:
                    end_time = time.time()
                    metrics.add_response(end_time - start_time, False)

                # Add delay between complex operations
                await asyncio.sleep(0.5)

            metrics.stop_timer()
            summary = metrics.get_summary()

            # Performance assertions for complex operations
            assert (
                summary["success_rate"] >= 80.0
            ), f"Rebalance success rate: {summary['success_rate']:.1f}%"
            assert (
                summary["avg_response_time_ms"] <= 5000.0
            ), f"Rebalance avg response time: {summary['avg_response_time_ms']:.1f}ms"

            print(f"\nRebalance Performance:")
            print(f"  Success Rate: {summary['success_rate']:.1f}%")
            print(f"  Average Response Time: {summary['avg_response_time_ms']:.1f}ms")
            print(f"  P95 Response Time: {summary['p95_response_time_ms']:.1f}ms")

        finally:
            # Cleanup test model
            try:
                await performance_client.delete(f"/api/v1/models/{model_id}")
            except Exception:
                pass


class TestLoadTest:
    """Load testing scenarios."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_mixed_load_scenario(self, performance_client: httpx.AsyncClient):
        """Test mixed load scenario with various API endpoints."""
        metrics = PerformanceMetrics()

        async def health_check():
            start_time = time.time()
            try:
                response = await performance_client.get("/health/live")
                end_time = time.time()
                metrics.add_response(end_time - start_time, response.status_code == 200)
            except Exception:
                end_time = time.time()
                metrics.add_response(end_time - start_time, False)

        async def list_models():
            start_time = time.time()
            try:
                response = await performance_client.get("/api/v1/models")
                end_time = time.time()
                metrics.add_response(end_time - start_time, response.status_code == 200)
            except Exception:
                end_time = time.time()
                metrics.add_response(end_time - start_time, False)

        async def get_openapi():
            start_time = time.time()
            try:
                response = await performance_client.get("/openapi.json")
                end_time = time.time()
                metrics.add_response(end_time - start_time, response.status_code == 200)
            except Exception:
                end_time = time.time()
                metrics.add_response(end_time - start_time, False)

        # Run mixed load for duration
        metrics.start_timer()
        end_time = time.time() + LOAD_TEST_DURATION

        tasks = []
        while time.time() < end_time:
            # Create a mix of different requests
            tasks.extend(
                [
                    health_check(),
                    health_check(),  # Health checks are more frequent
                    list_models(),
                    get_openapi(),
                ]
            )

            # Execute batch and wait briefly
            if len(tasks) >= 20:
                await asyncio.gather(*tasks, return_exceptions=True)
                tasks = []
                await asyncio.sleep(0.1)

        # Execute remaining tasks
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        metrics.stop_timer()
        summary = metrics.get_summary()

        # Load test assertions
        assert (
            summary["success_rate"] >= 90.0
        ), f"Load test success rate: {summary['success_rate']:.1f}%"
        assert (
            summary["requests_per_second"] >= 10.0
        ), f"Load test throughput: {summary['requests_per_second']:.1f} req/s"

        print(f"\nMixed Load Test Results:")
        print(f"  Duration: {summary['duration']:.1f}s")
        print(f"  Total Requests: {summary['total_requests']}")
        print(f"  Success Rate: {summary['success_rate']:.1f}%")
        print(f"  Throughput: {summary['requests_per_second']:.1f} req/s")
        print(f"  Average Response Time: {summary['avg_response_time_ms']:.1f}ms")
        print(f"  P95 Response Time: {summary['p95_response_time_ms']:.1f}ms")
        print(f"  P99 Response Time: {summary['p99_response_time_ms']:.1f}ms")


# Benchmark tests using pytest-benchmark
def test_health_check_benchmark(benchmark: BenchmarkFixture):
    """Benchmark health check endpoint using pytest-benchmark."""
    import requests

    def health_check():
        response = requests.get(f"{API_BASE_URL}/health/live", timeout=5)
        return response.status_code == 200

    # Only run if service is available
    try:
        requests.get(f"{API_BASE_URL}/health/live", timeout=5)
    except requests.RequestException:
        pytest.skip("Service not available for benchmarking")

    result = benchmark(health_check)
    assert result is True


def test_openapi_benchmark(benchmark: BenchmarkFixture):
    """Benchmark OpenAPI schema endpoint."""
    import requests

    def get_openapi():
        response = requests.get(f"{API_BASE_URL}/openapi.json", timeout=10)
        return len(response.json())

    # Only run if service is available
    try:
        requests.get(f"{API_BASE_URL}/health/live", timeout=5)
    except requests.RequestException:
        pytest.skip("Service not available for benchmarking")

    result = benchmark(get_openapi)
    assert result > 0  # Should return non-empty OpenAPI spec
