# Prometheus Multiprocess Directory Permissions

## The Problem

When running in Kubernetes/Docker with a non-root user, permission errors can occur:

```
chmod: changing permissions of '/tmp/prometheus_multiproc_dir': Operation not permitted
```

## Root Cause

The issue occurs when:
1. Directory is created as `root` in Dockerfile
2. Application runs as `appuser` (non-root)
3. Startup script tries to `chmod` the directory
4. Permission denied because `appuser` doesn't own the directory

## Solution

### 1. Dockerfile Setup (Build Time)

```dockerfile
# Create directory as root with proper ownership
RUN mkdir -p /tmp/prometheus_multiproc_dir && \
    chmod 777 /tmp/prometheus_multiproc_dir && \
    chown -R appuser:appuser /tmp/prometheus_multiproc_dir

# Then switch to non-root user
USER appuser
```

**Key points:**
- Create directory as root (has permission to create in /tmp)
- Set 777 permissions (allows all workers to read/write)
- Transfer ownership to appuser (allows appuser to manage it)
- Switch to appuser AFTER setting up the directory

### 2. Startup Script (Runtime)

```bash
# Don't try to chmod - directory already has correct permissions
# Just clean up old .db files
rm -f "$prometheus_multiproc_dir"/*.db 2>/dev/null || true

# Verify it's accessible
if [ -d "$prometheus_multiproc_dir" ] && [ -w "$prometheus_multiproc_dir" ]; then
    echo "Prometheus multiprocess directory ready"
fi
```

**Key points:**
- Don't attempt chmod (would fail as non-root)
- Only clean up .db files (appuser owns the directory)
- Verify directory is writable before proceeding

### 3. Gunicorn Config (Runtime)

```python
# Directory should already exist from Dockerfile
# Just ensure it exists (for non-Docker environments)
try:
    os.makedirs(prometheus_multiproc_dir, mode=0o777, exist_ok=True)
except OSError as e:
    logging.warning(f"Could not create directory: {e}")
```

**Key points:**
- Use `exist_ok=True` to avoid errors if directory exists
- Catch OSError gracefully (might not have permission)
- Don't try to chmod existing directory

## Why This Works

### Permission Hierarchy

```
/tmp/prometheus_multiproc_dir/
├── Owner: appuser
├── Group: appuser
├── Permissions: 777 (rwxrwxrwx)
└── Created by: root (in Dockerfile)
    Transferred to: appuser (via chown)
```

### Worker Process Permissions

```
Master Process (gunicorn)
├── User: appuser
├── Can read/write to directory ✅
└── Worker Processes
    ├── User: appuser (inherited)
    ├── Can create .db files ✅
    └── Can read other workers' .db files ✅
```

## Common Issues and Solutions

### Issue 1: "Operation not permitted" on chmod

**Symptom:**
```
chmod: changing permissions of '/tmp/prometheus_multiproc_dir': Operation not permitted
```

**Cause:** Trying to chmod a directory owned by root while running as appuser

**Solution:** Remove chmod from startup script (directory already has correct permissions from Dockerfile)

### Issue 2: "Permission denied" creating .db files

**Symptom:**
```
FileNotFoundError: [Errno 13] Permission denied: '/tmp/prometheus_multiproc_dir/counter_12345.db'
```

**Cause:** Directory not owned by appuser or wrong permissions

**Solution:** Ensure Dockerfile includes `chown -R appuser:appuser /tmp/prometheus_multiproc_dir`

### Issue 3: Directory doesn't exist

**Symptom:**
```
FileNotFoundError: [Errno 2] No such file or directory: '/tmp/prometheus_multiproc_dir'
```

**Cause:** Directory not created in Dockerfile or was deleted

**Solution:**
1. Verify Dockerfile creates the directory
2. Check if something is cleaning /tmp on startup
3. Ensure directory creation happens before USER directive

### Issue 4: Workers can't read each other's files

**Symptom:**
```
PermissionError: [Errno 13] Permission denied: '/tmp/prometheus_multiproc_dir/counter_12345.db'
```

**Cause:** Directory has 755 permissions instead of 777

**Solution:** Use 777 permissions to allow all workers (same user) to read/write all files

## Verification Steps

### 1. Check Directory Ownership

```bash
# In container
ls -la /tmp/ | grep prometheus_multiproc_dir

# Should show:
drwxrwxrwx 2 appuser appuser 4096 Dec  3 10:00 prometheus_multiproc_dir
```

### 2. Check Directory Permissions

```bash
# In container
stat -c "%a %U:%G" /tmp/prometheus_multiproc_dir

# Should show:
777 appuser:appuser
```

### 3. Test Write Access

```bash
# In container as appuser
touch /tmp/prometheus_multiproc_dir/test_file
rm /tmp/prometheus_multiproc_dir/test_file

# Should succeed without errors
```

### 4. Check Worker Files

```bash
# After service starts
ls -la /tmp/prometheus_multiproc_dir/

# Should show .db files owned by appuser:
-rw-r--r-- 1 appuser appuser 1024 Dec  3 10:00 counter_12345.db
-rw-r--r-- 1 appuser appuser 1024 Dec  3 10:00 histogram_12345.db
```

## Best Practices

### 1. Set Up in Dockerfile

✅ **DO**: Create directory in Dockerfile before switching to non-root user
```dockerfile
RUN mkdir -p /tmp/prometheus_multiproc_dir && \
    chmod 777 /tmp/prometheus_multiproc_dir && \
    chown -R appuser:appuser /tmp/prometheus_multiproc_dir
USER appuser
```

❌ **DON'T**: Try to create directory after switching to non-root user
```dockerfile
USER appuser
RUN mkdir -p /tmp/prometheus_multiproc_dir  # May fail!
```

### 2. Don't Chmod at Runtime

✅ **DO**: Trust the Dockerfile setup
```bash
# Just verify it exists
if [ -d "$prometheus_multiproc_dir" ]; then
    echo "Directory ready"
fi
```

❌ **DON'T**: Try to chmod at runtime
```bash
chmod 777 "$prometheus_multiproc_dir"  # Will fail as non-root!
```

### 3. Use 777 Permissions

✅ **DO**: Use 777 for multiprocess directory
```bash
chmod 777 /tmp/prometheus_multiproc_dir
```

❌ **DON'T**: Use restrictive permissions
```bash
chmod 755 /tmp/prometheus_multiproc_dir  # Workers can't write!
```

**Why 777 is safe:**
- Directory is inside the container (not exposed)
- All workers run as the same user (appuser)
- No other users in the container
- /tmp is container-local, not shared with host

### 4. Clean Files, Not Directory

✅ **DO**: Clean up .db files
```bash
rm -f /tmp/prometheus_multiproc_dir/*.db
```

❌ **DON'T**: Remove and recreate directory
```bash
rm -rf /tmp/prometheus_multiproc_dir  # Loses ownership!
mkdir -p /tmp/prometheus_multiproc_dir  # Can't set permissions!
```

## Security Considerations

### Is 777 Safe?

**Yes, in this context:**

1. **Container Isolation**: Directory is inside container, not on host
2. **Single User**: All processes run as appuser
3. **No Other Users**: Container has no other users to exploit permissions
4. **Temporary Storage**: /tmp is ephemeral, cleared on restart
5. **Not Exposed**: Directory not mounted or exposed outside container

### Alternative: Use 775

If you prefer more restrictive permissions:

```dockerfile
RUN mkdir -p /tmp/prometheus_multiproc_dir && \
    chmod 775 /tmp/prometheus_multiproc_dir && \
    chown -R appuser:appuser /tmp/prometheus_multiproc_dir
```

This works because:
- Owner (appuser): rwx (7)
- Group (appuser): rwx (7)
- Others: r-x (5)

All workers run as appuser, so they have full access via owner/group permissions.

## Troubleshooting Commands

```bash
# Check who you're running as
whoami

# Check directory ownership
ls -la /tmp/ | grep prometheus

# Check directory permissions
stat /tmp/prometheus_multiproc_dir

# Test write access
touch /tmp/prometheus_multiproc_dir/test && rm /tmp/prometheus_multiproc_dir/test

# Check for .db files
ls -la /tmp/prometheus_multiproc_dir/

# Check process user
ps aux | grep gunicorn

# Check environment variable
echo $prometheus_multiproc_dir
```

## Summary

**The fix:**
1. Create directory in Dockerfile as root
2. Set 777 permissions
3. Transfer ownership to appuser
4. Switch to appuser
5. Don't try to chmod at runtime

**Result:**
- No permission errors ✅
- Workers can create and read .db files ✅
- Metrics collection works properly ✅
- Service runs as non-root (secure) ✅
