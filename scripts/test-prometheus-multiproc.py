#!/usr/bin/env python3
"""
Test script to verify Prometheus multiprocess configuration.
"""

import os
import shutil
import tempfile


def test_prometheus_multiprocess():
    """Test Prometheus multiprocess functionality."""

    # Create a temporary directory for testing
    test_dir = tempfile.mkdtemp(prefix="prometheus_test_")

    try:
        print(f"Testing Prometheus multiprocess with directory: {test_dir}")

        # Set the environment variable BEFORE importing prometheus_client
        os.environ["prometheus_multiproc_dir"] = test_dir

        # Now import prometheus_client - it will detect the environment variable
        from prometheus_client import (
            CollectorRegistry,
            Counter,
            generate_latest,
            multiprocess,
        )

        # Create a registry and collector
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)

        # Create a test counter
        test_counter = Counter(
            'test_requests_total',
            'Test counter for multiprocess verification',
            ['method'],
            registry=registry,
        )

        # Increment the counter
        test_counter.labels(method='GET').inc()
        test_counter.labels(method='POST').inc(5)

        print("Successfully created and incremented counters")

        # Generate metrics
        metrics_output = generate_latest(registry)
        print("Generated metrics:")
        print(metrics_output.decode('utf-8'))

        # Check if files were created
        files = os.listdir(test_dir)
        print(f"Files created in multiprocess directory: {files}")

        if files:
            print("✅ Prometheus multiprocess test PASSED")
            return True
        else:
            print("❌ Prometheus multiprocess test FAILED - no files created")
            return False

    except Exception as e:
        print(f"❌ Prometheus multiprocess test FAILED with error: {e}")
        return False

    finally:
        # Clean up
        try:
            shutil.rmtree(test_dir)
            print(f"Cleaned up test directory: {test_dir}")
        except Exception as e:
            print(f"Warning: Failed to clean up test directory: {e}")

        # Remove environment variable
        if "prometheus_multiproc_dir" in os.environ:
            del os.environ["prometheus_multiproc_dir"]


if __name__ == "__main__":
    print("Testing Prometheus multiprocess configuration...")
    success = test_prometheus_multiprocess()
    exit(0 if success else 1)
