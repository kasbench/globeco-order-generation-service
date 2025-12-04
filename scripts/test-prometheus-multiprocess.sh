#!/bin/bash
# Test script to verify Prometheus multiprocess mode is working correctly

set -e

echo "=== Testing Prometheus Multiprocess Mode ==="
echo ""

# Test 1: Check if directory exists
echo "Test 1: Checking if /tmp/prometheus_multiproc_dir exists..."
if [ -d "/tmp/prometheus_multiproc_dir" ]; then
    echo "✓ Directory exists"
    ls -la /tmp/prometheus_multiproc_dir
else
    echo "✗ Directory does not exist"
    exit 1
fi
echo ""

# Test 2: Check directory permissions
echo "Test 2: Checking directory permissions..."
PERMS=$(stat -c "%a" /tmp/prometheus_multiproc_dir 2>/dev/null || stat -f "%Lp" /tmp/prometheus_multiproc_dir 2>/dev/null)
if [ "$PERMS" = "777" ]; then
    echo "✓ Directory has correct permissions (777)"
else
    echo "⚠ Directory has permissions: $PERMS (expected 777)"
fi
echo ""

# Test 3: Check if directory is writable
echo "Test 3: Testing write access..."
TEST_FILE="/tmp/prometheus_multiproc_dir/test_write_$$"
if touch "$TEST_FILE" 2>/dev/null; then
    echo "✓ Directory is writable"
    rm -f "$TEST_FILE"
else
    echo "✗ Directory is not writable"
    exit 1
fi
echo ""

# Test 4: Check for .db files (if service is running)
echo "Test 4: Checking for Prometheus .db files..."
DB_FILES=$(ls /tmp/prometheus_multiproc_dir/*.db 2>/dev/null | wc -l)
if [ "$DB_FILES" -gt 0 ]; then
    echo "✓ Found $DB_FILES .db files"
    ls -lh /tmp/prometheus_multiproc_dir/*.db
else
    echo "⚠ No .db files found (service may not be running yet)"
fi
echo ""

# Test 5: Check environment variable
echo "Test 5: Checking prometheus_multiproc_dir environment variable..."
if [ -n "$prometheus_multiproc_dir" ]; then
    echo "✓ Environment variable is set: $prometheus_multiproc_dir"
else
    echo "⚠ Environment variable is not set (may be single worker mode)"
fi
echo ""

# Test 6: Check if metrics endpoint is accessible
echo "Test 6: Testing metrics endpoint..."
if command -v curl &> /dev/null; then
    if curl -s -f http://localhost:8088/metrics > /dev/null 2>&1; then
        echo "✓ Metrics endpoint is accessible"

        # Check for process metrics
        METRICS=$(curl -s http://localhost:8088/metrics)
        if echo "$METRICS" | grep -q "process_cpu_seconds_total"; then
            echo "✓ Process metrics are present"
        else
            echo "⚠ Process metrics may be missing"
        fi

        if echo "$METRICS" | grep -q "http_requests_total"; then
            echo "✓ HTTP metrics are present"
        else
            echo "⚠ HTTP metrics may be missing"
        fi
    else
        echo "⚠ Metrics endpoint is not accessible (service may not be running)"
    fi
else
    echo "⚠ curl not available, skipping metrics endpoint test"
fi
echo ""

# Test 7: Check logs for errors
echo "Test 7: Checking for Prometheus-related errors in logs..."
if [ -f "/app/logs/app.log" ]; then
    ERROR_COUNT=$(grep -c "FileNotFoundError.*prometheus_multiproc_dir" /app/logs/app.log 2>/dev/null || echo "0")
    if [ "$ERROR_COUNT" -eq 0 ]; then
        echo "✓ No FileNotFoundError in logs"
    else
        echo "✗ Found $ERROR_COUNT FileNotFoundError entries in logs"
    fi

    NONE_ERROR_COUNT=$(grep -c "NoneType.*object does not support item assignment" /app/logs/app.log 2>/dev/null || echo "0")
    if [ "$NONE_ERROR_COUNT" -eq 0 ]; then
        echo "✓ No NoneType errors in logs"
    else
        echo "✗ Found $NONE_ERROR_COUNT NoneType error entries in logs"
    fi
else
    echo "⚠ Log file not found, skipping log check"
fi
echo ""

echo "=== Test Summary ==="
echo "All critical tests passed. Prometheus multiprocess mode should be working correctly."
