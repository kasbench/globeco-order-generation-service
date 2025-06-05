#!/bin/bash

# GlobeCo Order Generation Service - Kubernetes Deployment Script
# This script deploys the Order Generation Service to Kubernetes with comprehensive validation

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DEPLOYMENTS_DIR="$PROJECT_ROOT/deployments"
NAMESPACE="globeco"
SERVICE_NAME="globeco-order-generation-service"
IMAGE_TAG="${IMAGE_TAG:-latest}"
TIMEOUT="${TIMEOUT:-300}"
DRY_RUN="${DRY_RUN:-false}"
ENVIRONMENT="${ENVIRONMENT:-production}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Print usage information
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Deploy GlobeCo Order Generation Service to Kubernetes

OPTIONS:
    -h, --help              Show this help message
    -n, --namespace         Kubernetes namespace (default: globeco)
    -t, --tag               Docker image tag (default: latest)
    -e, --environment       Environment (default: production)
    -d, --dry-run          Perform a dry run without applying changes
    -w, --wait             Wait timeout in seconds (default: 300)
    --skip-validation      Skip pre-deployment validation
    --force                Force deployment even with warnings

EXAMPLES:
    $0                                          # Deploy with defaults
    $0 -t v1.2.3 -e staging                   # Deploy specific version to staging
    $0 --dry-run                               # Dry run deployment
    $0 --namespace test-env --tag latest       # Deploy to test environment

EOF
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                usage
                exit 0
                ;;
            -n|--namespace)
                NAMESPACE="$2"
                shift 2
                ;;
            -t|--tag)
                IMAGE_TAG="$2"
                shift 2
                ;;
            -e|--environment)
                ENVIRONMENT="$2"
                shift 2
                ;;
            -d|--dry-run)
                DRY_RUN="true"
                shift
                ;;
            -w|--wait)
                TIMEOUT="$2"
                shift 2
                ;;
            --skip-validation)
                SKIP_VALIDATION="true"
                shift
                ;;
            --force)
                FORCE="true"
                shift
                ;;
            *)
                log_error "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check if kubectl is installed and configured
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed or not in PATH"
        exit 1
    fi

    # Check kubectl connection
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi

    # Check if kustomize is available
    if ! command -v kustomize &> /dev/null; then
        log_warning "kustomize not found, using kubectl kustomize"
    fi

    # Check if namespace exists
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_info "Creating namespace: $NAMESPACE"
        if [[ "$DRY_RUN" == "false" ]]; then
            kubectl create namespace "$NAMESPACE"
        fi
    fi

    log_success "Prerequisites check completed"
}

# Validate deployment files
validate_deployment() {
    if [[ "${SKIP_VALIDATION:-false}" == "true" ]]; then
        log_info "Skipping validation as requested"
        return 0
    fi

    log_info "Validating Kubernetes manifests..."

    cd "$DEPLOYMENTS_DIR"

    # Validate YAML syntax
    for file in *.yaml; do
        if ! kubectl apply --dry-run=client -f "$file" &> /dev/null; then
            log_error "Invalid YAML in $file"
            return 1
        fi
    done

    # Validate with kustomize
    if command -v kustomize &> /dev/null; then
        if ! kustomize build . | kubectl apply --dry-run=client -f - &> /dev/null; then
            log_error "Kustomize validation failed"
            return 1
        fi
    fi

    log_success "Manifest validation completed"
}

# Check if image exists
check_image() {
    log_info "Checking if Docker image exists: kasbench/$SERVICE_NAME:$IMAGE_TAG"

    # For public images, we can try to pull the manifest
    # This is a basic check - in production you might want more sophisticated checks
    if docker manifest inspect "kasbench/$SERVICE_NAME:$IMAGE_TAG" &> /dev/null; then
        log_success "Docker image found"
    else
        log_warning "Cannot verify Docker image existence. Proceeding anyway..."
    fi
}

# Deploy application
deploy_application() {
    log_info "Deploying $SERVICE_NAME to namespace $NAMESPACE..."

    cd "$DEPLOYMENTS_DIR"

    # Set image tag in kustomization
    if command -v kustomize &> /dev/null; then
        kustomize edit set image "kasbench/$SERVICE_NAME:$IMAGE_TAG"
    fi

    # Apply manifests
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "DRY RUN: Would apply the following manifests:"
        if command -v kustomize &> /dev/null; then
            kustomize build . | kubectl apply --dry-run=client -f -
        else
            kubectl apply --dry-run=client -f .
        fi
    else
        if command -v kustomize &> /dev/null; then
            kustomize build . | kubectl apply -f -
        else
            kubectl apply -f .
        fi
    fi

    log_success "Manifests applied"
}

# Wait for deployment to be ready
wait_for_deployment() {
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "DRY RUN: Skipping deployment wait"
        return 0
    fi

    log_info "Waiting for deployment to be ready (timeout: ${TIMEOUT}s)..."

    # Wait for deployment to be ready
    if kubectl rollout status deployment/"$SERVICE_NAME" -n "$NAMESPACE" --timeout="${TIMEOUT}s"; then
        log_success "Deployment is ready"
    else
        log_error "Deployment failed to become ready within ${TIMEOUT}s"
        return 1
    fi

    # Wait for MongoDB StatefulSet
    if kubectl rollout status statefulset/"$SERVICE_NAME-mongodb" -n "$NAMESPACE" --timeout="${TIMEOUT}s"; then
        log_success "MongoDB StatefulSet is ready"
    else
        log_error "MongoDB StatefulSet failed to become ready within ${TIMEOUT}s"
        return 1
    fi
}

# Verify deployment health
verify_deployment() {
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "DRY RUN: Skipping health verification"
        return 0
    fi

    log_info "Verifying deployment health..."

    # Check if pods are running
    local ready_pods
    ready_pods=$(kubectl get pods -n "$NAMESPACE" -l app="$SERVICE_NAME" --field-selector=status.phase=Running --no-headers | wc -l)

    if [[ "$ready_pods" -eq 0 ]]; then
        log_error "No pods are running"
        return 1
    fi

    log_info "Found $ready_pods running pods"

    # Check health endpoint
    log_info "Checking health endpoint..."
    local pod_name
    pod_name=$(kubectl get pods -n "$NAMESPACE" -l app="$SERVICE_NAME" --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')

    if kubectl exec -n "$NAMESPACE" "$pod_name" -- curl -f http://localhost:8080/health/live &> /dev/null; then
        log_success "Health check passed"
    else
        log_warning "Health check failed, but deployment may still be starting up"
    fi

    log_success "Deployment verification completed"
}

# Show deployment status
show_status() {
    if [[ "$DRY_RUN" == "true" ]]; then
        return 0
    fi

    log_info "Deployment Status:"
    echo

    echo "Pods:"
    kubectl get pods -n "$NAMESPACE" -l app="$SERVICE_NAME"
    echo

    echo "Services:"
    kubectl get services -n "$NAMESPACE" -l app="$SERVICE_NAME"
    echo

    echo "Deployments:"
    kubectl get deployments -n "$NAMESPACE" -l app="$SERVICE_NAME"
    echo

    echo "StatefulSets:"
    kubectl get statefulsets -n "$NAMESPACE" -l app="$SERVICE_NAME"
    echo

    echo "HPA:"
    kubectl get hpa -n "$NAMESPACE" -l app="$SERVICE_NAME"
    echo

    echo "Ingress:"
    kubectl get ingress -n "$NAMESPACE" -l app="$SERVICE_NAME"
}

# Rollback deployment
rollback_deployment() {
    log_warning "Rolling back deployment..."

    if kubectl rollout undo deployment/"$SERVICE_NAME" -n "$NAMESPACE"; then
        log_success "Rollback initiated"

        # Wait for rollback to complete
        if kubectl rollout status deployment/"$SERVICE_NAME" -n "$NAMESPACE" --timeout="${TIMEOUT}s"; then
            log_success "Rollback completed successfully"
        else
            log_error "Rollback failed"
        fi
    else
        log_error "Failed to initiate rollback"
    fi
}

# Cleanup on exit
cleanup() {
    local exit_code=$?
    if [[ $exit_code -ne 0 ]] && [[ "$DRY_RUN" == "false" ]] && [[ "${FORCE:-false}" != "true" ]]; then
        log_warning "Deployment failed. Consider running rollback manually:"
        log_warning "kubectl rollout undo deployment/$SERVICE_NAME -n $NAMESPACE"
    fi
}

# Main deployment function
main() {
    log_info "Starting deployment of $SERVICE_NAME..."
    log_info "Environment: $ENVIRONMENT"
    log_info "Namespace: $NAMESPACE"
    log_info "Image Tag: $IMAGE_TAG"
    log_info "Dry Run: $DRY_RUN"
    echo

    # Set up cleanup trap
    trap cleanup EXIT

    # Run deployment steps
    check_prerequisites
    validate_deployment
    check_image
    deploy_application
    wait_for_deployment
    verify_deployment
    show_status

    if [[ "$DRY_RUN" == "true" ]]; then
        log_success "Dry run completed successfully"
    else
        log_success "Deployment completed successfully!"
        log_info "Service URL: https://order-generation.globeco.kasbench.org"
        log_info "Health Check: https://order-generation.globeco.kasbench.org/health/health"
        log_info "API Documentation: https://order-generation.globeco.kasbench.org/docs"
    fi
}

# Parse arguments and run main function
parse_args "$@"
main
