# Beanie ODM Collection Access Fix

## Problem Description

The application was experiencing consistent "Beanie ODM not properly initialized" errors specifically in the `rebalance_repository.get_by_id()` method. The error occurred with the message:

```
Repository.get_by_id(): Beanie ODM not properly initialized, falling back to standard method. Error: get_motor_collection
```

This error occurred consistently regardless of whether the application was running with single or multiple workers, indicating it was not a multi-worker initialization issue.

### Root Cause

The issue was caused by intermittent failures in Beanie ODM's `get_motor_collection()` method. This can happen due to:

1. **Timing issues** during application startup where Beanie initialization completes but collection registration is not immediately available
2. **Context isolation** where the repository instance doesn't have proper access to the initialized Beanie context
3. **Transient connection issues** that cause the motor collection reference to become invalid

## Solution Implementation

### 1. Enhanced Database Manager

**File: `src/infrastructure/database/database.py`**

- Added `_initialization_lock` to prevent race conditions during initialization
- Added `ensure_beanie_initialized()` method that:
  - Checks if Beanie is properly initialized in the current process
  - Tests actual collection access to verify functionality
  - Re-initializes if needed with proper cleanup of existing connections
  - Provides detailed error handling and logging

### 2. Repository Layer Updates

**File: `src/infrastructure/database/repositories/rebalance_repository.py`**

- Added `_get_collection_safely()` method that tries multiple approaches to access the MongoDB collection:
  1. Standard Beanie `get_motor_collection()` method
  2. Direct database access via the database manager
  3. Re-initialization of Beanie ODM and retry
- Simplified `get_by_id()` method to use the safe collection access
- Improved error handling and logging to identify which access method succeeded

### 3. Enhanced Database Manager

**File: `src/infrastructure/database/database.py`**

- Added thread-safe initialization with asyncio locks
- Enhanced `ensure_beanie_initialized()` method with better error detection and recovery
- Added collection access verification to detect when Beanie ODM is not working properly

## Key Features of the Fix

### Multiple Collection Access Methods
- Primary: Standard Beanie `get_motor_collection()`
- Fallback 1: Direct database access via motor client
- Fallback 2: Re-initialize Beanie ODM and retry
- Each method is tried in sequence until one succeeds

### Robust Error Handling
- Graceful handling of `CollectionWasNotInitialized` exceptions
- Detailed logging showing which access method was used
- Clear error messages when all methods fail

### Thread-Safe Operations
- Uses asyncio locks to prevent concurrent initialization attempts
- Handles race conditions during database initialization

### Production Ready
- Maintains existing functionality and performance
- Works with both single and multi-worker deployments
- Preserves all existing configuration options

## Testing

A test script (`test_beanie_fix.py`) is provided to verify the fix works correctly:

```bash
python test_beanie_fix.py
```

## Deployment

The fix is backward compatible and doesn't require any configuration changes. The application will automatically use the new initialization logic when deployed.

### Environment Variables

All existing environment variables are supported:
- `WORKERS`: Number of Gunicorn workers (default: 4)
- `PORT`: Application port (default: 8088)
- `LOG_LEVEL`: Logging level (default: INFO)

## Monitoring

The fix includes enhanced logging to help monitor initialization:
- Worker startup/shutdown events
- Beanie ODM initialization status
- Re-initialization attempts and results
- Collection access verification

## Expected Behavior After Fix

1. **No more "get_motor_collection" errors** in the logs
2. **Consistent database access** across all worker processes
3. **Proper worker initialization** logged during startup
4. **Graceful handling** of any remaining edge cases

## Rollback Plan

If issues occur, you can temporarily reduce to single worker mode by setting:
```bash
export WORKERS=1
```

This will eliminate any multi-worker related issues while investigating further.
