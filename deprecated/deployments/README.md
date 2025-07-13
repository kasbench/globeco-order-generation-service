# GlobeCo Order Generation Service - Kubernetes Deployment

This directory contains all Kubernetes manifests and deployment configurations for the GlobeCo Order Generation Service.

## Overview

The Order Generation Service is deployed as a scalable microservice in Kubernetes with the following components:

- **Application Deployment**: Multi-replica FastAPI application with horizontal autoscaling
- **MongoDB StatefulSet**: Persistent database with proper initialization
- **Services**: ClusterIP and headless services for internal communication
- **Ingress**: External access with TLS termination and rate limiting
- **ConfigMaps**: Application configuration and environment-specific settings
- **Secrets**: Sensitive data like database credentials and API keys
- **HPA**: Horizontal Pod Autoscaler for automatic scaling based on CPU/memory/custom metrics
- **RBAC**: Role-based access control with service accounts and role bindings

## Prerequisites

### Required Tools

- `kubectl` (v1.25+) - Kubernetes command-line tool
- `kustomize` (v4.0+) - Configuration management (optional but recommended)
- `docker` - For building and pushing images
- Access to a Kubernetes cluster (v1.25+)

### Cluster Requirements

- **Kubernetes Version**: 1.25 or higher
- **Namespace**: `globeco` (will be created if it doesn't exist)
- **Storage Class**: `standard` (or `fast-ssd` for production)
- **Ingress Controller**: NGINX Ingress Controller
- **DNS**: Cluster DNS configured for service discovery

### Optional Components

- **Prometheus**: For custom metrics collection (HPA scaling)
- **cert-manager**: For automatic TLS certificate management
- **External DNS**: For automatic DNS management

## Quick Start

### 1. Deploy with Default Configuration

```bash
# Make deployment script executable
chmod +x ../scripts/deploy-k8s.sh

# Deploy with defaults (production environment, latest tag)
../scripts/deploy-k8s.sh
```

### 2. Deploy Specific Version

```bash
# Deploy specific version to staging
../scripts/deploy-k8s.sh -t v1.2.3 -e staging

# Deploy to custom namespace
../scripts/deploy-k8s.sh -n test-globeco -t latest
```

### 3. Dry Run Deployment

```bash
# Test deployment without applying changes
../scripts/deploy-k8s.sh --dry-run
```

## Manual Deployment

### Using Kustomize (Recommended)

```bash
# Apply all manifests with kustomize
kubectl apply -k .

# Or build and inspect first
kustomize build . | kubectl apply -f -
```

### Using Direct kubectl

```bash
# Apply manifests in order
kubectl apply -f secrets.yaml
kubectl apply -f configmap.yaml
kubectl apply -f mongodb.yaml
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f hpa.yaml
kubectl apply -f ingress.yaml
```

## Configuration

### Environment Variables

The service is configured through ConfigMaps and Secrets. Key configuration options:

| Setting | ConfigMap Key | Default | Description |
|---------|---------------|---------|-------------|
| Database Name | `database-name` | `globeco_production` | MongoDB database name |
| Log Level | `LOG_LEVEL` | `INFO` | Application log level |
| Optimization Timeout | `optimization-timeout` | `30` | CVXPY solver timeout (seconds) |
| External Service URLs | Various | See ConfigMap | URLs for external services |

### Resource Limits

Default resource configuration:

```yaml
resources:
  requests:
    cpu: 500m
    memory: 1Gi
  limits:
    cpu: 2000m
    memory: 4Gi
```

Production overrides in `patches/production-resources.yaml`:

```yaml
resources:
  requests:
    cpu: 1000m
    memory: 2Gi
  limits:
    cpu: 4000m
    memory: 8Gi
```

### Scaling Configuration

- **Min Replicas**: 3 (ensures high availability)
- **Max Replicas**: 20 (prevents resource exhaustion)
- **CPU Target**: 70% (triggers scaling)
- **Memory Target**: 80% (triggers scaling)

## Monitoring and Health Checks

### Health Endpoints

- **Liveness**: `/health/live` - Basic application health
- **Readiness**: `/health/ready` - Application ready to serve traffic
- **Health**: `/health/health` - Comprehensive health including dependencies

### Probe Configuration

```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8080
  initialDelaySeconds: 30
  periodSeconds: 30

readinessProbe:
  httpGet:
    path: /health/ready
    port: 8080
  initialDelaySeconds: 15
  periodSeconds: 10

startupProbe:
  httpGet:
    path: /health/live
    port: 8080
  initialDelaySeconds: 10
  failureThreshold: 12
```

### Metrics

Prometheus metrics are exposed at `/metrics` endpoint with annotations:

```yaml
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "8080"
  prometheus.io/path: "/metrics"
```

## Security

### RBAC

The service uses a dedicated service account with minimal required permissions:

- Read access to ConfigMaps and Secrets
- Read access to own Pod information
- Read access to Deployment information

### Pod Security

- **Non-root user**: Runs as user ID 1000
- **Read-only root filesystem**: Prevents runtime modifications
- **Dropped capabilities**: Removes all unnecessary Linux capabilities
- **Security context**: Enforced at both pod and container level

### Network Security

- **Service mesh ready**: Compatible with Istio/Linkerd
- **Network policies**: Can be restricted with Kubernetes NetworkPolicies
- **TLS**: Ingress termination with configurable certificates

## Troubleshooting

### Common Issues

#### 1. Pods Not Starting

```bash
# Check pod status
kubectl get pods -n globeco -l app=globeco-order-generation-service

# Check pod logs
kubectl logs -n globeco -l app=globeco-order-generation-service --tail=100

# Describe pod for events
kubectl describe pod -n globeco <pod-name>
```

#### 2. Database Connection Issues

```bash
# Check MongoDB pod status
kubectl get pods -n globeco -l app=globeco-order-generation-service-mongodb

# Check MongoDB logs
kubectl logs -n globeco -l app=globeco-order-generation-service-mongodb

# Test connectivity from app pod
kubectl exec -n globeco <app-pod> -- nc -zv globeco-order-generation-service-mongodb 27017
```

#### 3. Health Check Failures

```bash
# Check health endpoint directly
kubectl exec -n globeco <pod-name> -- curl -f http://localhost:8080/health/health

# Check configuration
kubectl get configmap -n globeco globeco-order-generation-service-config -o yaml
```

#### 4. HPA Not Scaling

```bash
# Check HPA status
kubectl get hpa -n globeco

# Check metrics server
kubectl top pods -n globeco

# Check HPA events
kubectl describe hpa -n globeco globeco-order-generation-service-hpa
```

### Debugging Commands

```bash
# Get all resources
kubectl get all -n globeco -l app=globeco-order-generation-service

# Check resource usage
kubectl top pods -n globeco -l app=globeco-order-generation-service

# View events
kubectl get events -n globeco --sort-by='.lastTimestamp'

# Port forward for local testing
kubectl port-forward -n globeco svc/globeco-order-generation-service 8080:8080

# Shell into application pod
kubectl exec -it -n globeco <pod-name> -- /bin/bash
```

### Log Analysis

```bash
# Stream logs from all pods
kubectl logs -n globeco -l app=globeco-order-generation-service -f

# Get logs from previous container restart
kubectl logs -n globeco <pod-name> --previous

# Filter logs by level
kubectl logs -n globeco <pod-name> | jq 'select(.level=="ERROR")'
```

## Performance Tuning

### Application Performance

1. **Optimization Timeout**: Adjust `optimization-timeout` in ConfigMap
2. **Thread Pool Size**: Modify `THREAD_POOL_MAX_WORKERS`
3. **Connection Pooling**: Tune `CONNECTION_POOL_SIZE`

### Database Performance

1. **MongoDB Resources**: Increase CPU/memory in production patches
2. **Storage Class**: Use `fast-ssd` for better I/O performance
3. **Connection Limits**: Adjust MongoDB connection limits

### Autoscaling Performance

1. **Scale-up Policy**: Faster scaling for sudden load increases
2. **Scale-down Policy**: Conservative scaling to prevent flapping
3. **Custom Metrics**: Use business metrics for better scaling decisions

## Maintenance

### Updates and Rollouts

```bash
# Update image tag
kubectl set image deployment/globeco-order-generation-service \
  order-generation-service=kasbench/globeco-order-generation-service:v1.2.3 \
  -n globeco

# Check rollout status
kubectl rollout status deployment/globeco-order-generation-service -n globeco

# Rollback if needed
kubectl rollout undo deployment/globeco-order-generation-service -n globeco
```

### Backup and Recovery

```bash
# Backup MongoDB data
kubectl exec -n globeco <mongodb-pod> -- mongodump --db globeco_production --out /backup

# Copy backup to local machine
kubectl cp globeco/<mongodb-pod>:/backup ./mongodb-backup

# Restore from backup
kubectl exec -n globeco <mongodb-pod> -- mongorestore --db globeco_production /backup/globeco_production
```

### Configuration Updates

```bash
# Update ConfigMap
kubectl patch configmap globeco-order-generation-service-config -n globeco \
  --patch '{"data":{"LOG_LEVEL":"DEBUG"}}'

# Restart deployment to pick up changes
kubectl rollout restart deployment/globeco-order-generation-service -n globeco
```

## Production Considerations

### High Availability

- **Pod Disruption Budget**: Ensures minimum 2 pods available during maintenance
- **Anti-affinity**: Spreads pods across different nodes
- **Multi-zone deployment**: Consider zone anti-affinity for critical workloads

### Disaster Recovery

- **Database backups**: Regular automated backups with point-in-time recovery
- **Configuration backups**: Version control all configuration changes
- **Cross-region replication**: For mission-critical deployments

### Monitoring and Alerting

- **Application metrics**: Business KPIs and performance metrics
- **Infrastructure metrics**: Resource utilization and capacity planning
- **Log aggregation**: Centralized logging with structured JSON format
- **Alerting rules**: Proactive alerting for critical issues

## Support

For issues or questions:

1. Check the troubleshooting section above
2. Review application logs and Kubernetes events
3. Consult the main project documentation
4. Contact the development team

## File Structure

```
deployments/
├── README.md                          # This file
├── deployment.yaml                    # Application deployment
├── service.yaml                       # Service definitions
├── configmap.yaml                     # Application configuration
├── secrets.yaml                       # Sensitive configuration
├── mongodb.yaml                       # Database deployment
├── hpa.yaml                          # Horizontal Pod Autoscaler
├── ingress.yaml                      # External access configuration
├── kustomization.yaml                # Kustomize configuration
└── patches/
    └── production-resources.yaml     # Production resource overrides
```
