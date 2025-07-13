#!/bin/bash

# GlobeCo Order Generation Service - Universal Deployment Script
# This script handles deployments to Kubernetes with comprehensive validation and rollback

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DEPLOYMENTS_DIR="$PROJECT_ROOT/deployments"
IMAGE_NAME="kasbench/globeco-order-generation-service"
DEFAULT_TIMEOUT="600"

# Default values
ENVIRONMENT=""
IMAGE_TAG=""
NAMESPACE=""
DRY_RUN="false"
TIMEOUT="$DEFAULT_TIMEOUT"
VALIDATE_ONLY="false"
ROLLBACK="false"
FORCE="false"
VERBOSE="false"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
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

log_debug() {
    if [[ "$VERBOSE" == "true" ]]; then
        echo -e "${PURPLE}[DEBUG]${NC} $1"
    fi
}

# Print usage information
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Deploy GlobeCo Order Generation Service to Kubernetes

REQUIRED OPTIONS:
    -e, --environment       Environment (staging|production)
    -t, --tag              Docker image tag

OPTIONAL:
    -n, --namespace        Kubernetes namespace (auto-detected from environment)
    -d, --dry-run         Perform a dry run without applying changes
    -w, --timeout         Wait timeout in seconds (default: $DEFAULT_TIMEOUT)
    -v, --validate-only   Only validate manifests, don't deploy
    -r, --rollback        Rollback to previous deployment
    -f, --force           Force deployment even with warnings
    --verbose             Enable verbose output
    -h, --help            Show this help message

EXAMPLES:
    $0 -e staging -t latest                    # Deploy latest to staging
    $0 -e production -t v1.2.3                # Deploy version to production
    $0 -e staging -t latest --dry-run         # Dry run deployment
    $0 -e production --rollback               # Rollback production
    $0 --validate-only                        # Validate manifests only

ENVIRONMENT SETUP:
    For CI/CD: Set KUBECONFIG or configure kubectl context
    For local: Ensure kubectl is configured for target cluster

EOF
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -e|--environment)
                ENVIRONMENT="$2"
                shift 2
                ;;
            -t|--tag)
                IMAGE_TAG="$2"
                shift 2
                ;;
            -n|--namespace)
                NAMESPACE="$2"
                shift 2
                ;;
            -d|--dry-run)
                DRY_RUN="true"
                shift
                ;;
            -w|--timeout)
                TIMEOUT="$2"
                shift 2
                ;;
            -v|--validate-only)
                VALIDATE_ONLY="true"
                shift
                ;;
            -r|--rollback)
                ROLLBACK="true"
                shift
                ;;
            -f|--force)
                FORCE="true"
                shift
                ;;
            --verbose)
                VERBOSE="true"
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done
}

# Validate arguments and setup
validate_args() {
    # Validate environment if provided
    if [[ -n "$ENVIRONMENT" ]]; then
        if [[ "$ENVIRONMENT" != "staging" && "$ENVIRONMENT" != "production" ]]; then
            log_error "Invalid environment '$ENVIRONMENT'. Must be 'staging' or 'production'."
            exit 1
        fi

        # Set namespace based on environment if not provided
        if [[ -z "$NAMESPACE" ]]; then
            case "$ENVIRONMENT" in
                staging)
                    NAMESPACE="globeco-staging"
                    ;;
                production)
                    NAMESPACE="globeco"
                    ;;
            esac
        fi
    fi

    # Validate required arguments for deployment
    if [[ "$VALIDATE_ONLY" != "true" && "$ROLLBACK" != "true" ]]; then
        if [[ -z "$ENVIRONMENT" ]]; then
            log_error "Environment is required for deployment. Use -e staging|production"
            exit 1
        fi

        if [[ -z "$IMAGE_TAG" ]]; then
            log_error "Image tag is required for deployment. Use -t <tag>"
            exit 1
        fi
    fi

    # Validate timeout
    if ! [[ "$TIMEOUT" =~ ^[0-9]+$ ]]; then
        log_error "Timeout must be a number"
        exit 1
    fi

    log_debug "Validated arguments:"
    log_debug "  Environment: $ENVIRONMENT"
    log_debug "  Namespace: $NAMESPACE"
    log_debug "  Image Tag: $IMAGE_TAG"
    log_debug "  Dry Run: $DRY_RUN"
    log_debug "  Timeout: $TIMEOUT"
    log_debug "  Validate Only: $VALIDATE_ONLY"
    log_debug "  Rollback: $ROLLBACK"
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
        log_error "Please ensure kubectl is configured with valid credentials"
        exit 1
    fi

    # Check if kustomize is available
    if command -v kustomize &> /dev/null; then
        log_debug "Using kustomize for manifest processing"
    else
        log_debug "kustomize not found, using kubectl kustomize"
    fi

    # Check if namespace exists
    if [[ -n "$NAMESPACE" ]]; then
        if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
            log_warning "Namespace '$NAMESPACE' does not exist"
            if [[ "$DRY_RUN" == "false" && "$FORCE" == "true" ]]; then
                log_info "Creating namespace: $NAMESPACE"
                kubectl create namespace "$NAMESPACE"
            else
                log_error "Namespace '$NAMESPACE' does not exist. Use --force to create it."
                exit 1
            fi
        fi
    fi

    # Get cluster info
    CLUSTER_INFO=$(kubectl cluster-info | head -n 1 | cut -d' ' -f6- || echo "unknown")
    log_debug "Connected to cluster: $CLUSTER_INFO"

    log_success "Prerequisites check completed"
}

# Validate Docker image exists
validate_image() {
    if [[ -z "$IMAGE_TAG" ]]; then
        return 0
    fi

    log_info "Validating Docker image: $IMAGE_NAME:$IMAGE_TAG"

    # Try to inspect the image manifest
    if docker manifest inspect "$IMAGE_NAME:$IMAGE_TAG" &> /dev/null; then
        log_success "Docker image exists: $IMAGE_NAME:$IMAGE_TAG"
    else
        log_warning "Cannot verify Docker image existence: $IMAGE_NAME:$IMAGE_TAG"
        log_warning "Image may not exist or may not be accessible"
        if [[ "$FORCE" != "true" ]]; then
            log_error "Use --force to proceed anyway"
            exit 1
        fi
    fi
}

# Validate Kubernetes manifests
validate_manifests() {
    log_info "Validating Kubernetes manifests..."

    cd "$DEPLOYMENTS_DIR"

    # Validate YAML syntax first
    for file in *.yaml; do
        if [[ -f "$file" ]]; then
            log_debug "Checking syntax: $file"
            if ! kubectl apply --dry-run=client -f "$file" &> /dev/null; then
                log_error "Invalid YAML syntax in $file"
                return 1
            fi
        fi
    done

    # Validate with kustomize if available
    if command -v kustomize &> /dev/null; then
        log_debug "Validating with kustomize"
        if ! kustomize build . | kubectl apply --dry-run=client -f - &> /dev/null; then
            log_error "Kustomize validation failed"
            return 1
        fi
    fi

    log_success "Manifest validation completed"
}

# Backup current deployment
backup_deployment() {
    if [[ -z "$NAMESPACE" ]]; then
        return 0
    fi

    log_info "Creating backup of current deployment..."

    local backup_dir="$PROJECT_ROOT/.backup/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$backup_dir"

    # Backup deployment
    if kubectl get deployment globeco-order-generation-service -n "$NAMESPACE" &> /dev/null; then
        kubectl get deployment globeco-order-generation-service -n "$NAMESPACE" -o yaml > "$backup_dir/deployment.yaml"
        log_success "Deployment backed up to: $backup_dir/deployment.yaml"
    else
        log_debug "No existing deployment to backup"
    fi

    # Backup configmap
    if kubectl get configmap globeco-order-generation-service-config -n "$NAMESPACE" &> /dev/null; then
        kubectl get configmap globeco-order-generation-service-config -n "$NAMESPACE" -o yaml > "$backup_dir/configmap.yaml"
        log_debug "ConfigMap backed up"
    fi

    echo "$backup_dir" > "$PROJECT_ROOT/.backup/latest"
}

# Deploy application
deploy_application() {
    log_info "Deploying $IMAGE_NAME:$IMAGE_TAG to $ENVIRONMENT environment..."

    cd "$DEPLOYMENTS_DIR"

    # Update image tag in kustomization if using kustomize
    if command -v kustomize &> /dev/null && [[ -f "kustomization.yaml" ]]; then
        log_debug "Updating image tag in kustomization.yaml"
        kustomize edit set image "$IMAGE_NAME:$IMAGE_TAG"
    fi

    # Update namespace if staging
    if [[ "$ENVIRONMENT" == "staging" ]]; then
        log_debug "Updating namespace for staging environment"
        # Create temporary files with staging namespace
        for file in *.yaml; do
            if [[ -f "$file" ]]; then
                sed "s/namespace: globeco$/namespace: $NAMESPACE/g" "$file" > "${file}.staging"
            fi
        done
    fi

    # Apply manifests
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "DRY RUN: Would apply the following manifests:"
        if command -v kustomize &> /dev/null && [[ -f "kustomization.yaml" ]]; then
            kustomize build . | kubectl apply --dry-run=client -f -
        else
            if [[ "$ENVIRONMENT" == "staging" ]]; then
                kubectl apply --dry-run=client -f *.staging
            else
                kubectl apply --dry-run=client -f *.yaml
            fi
        fi
    else
        log_info "Applying manifests to $NAMESPACE namespace..."
        if command -v kustomize &> /dev/null && [[ -f "kustomization.yaml" ]]; then
            kustomize build . | kubectl apply -f -
        else
            if [[ "$ENVIRONMENT" == "staging" ]]; then
                kubectl apply -f *.staging
            else
                kubectl apply -f *.yaml
            fi
        fi
    fi

    # Clean up staging files
    if [[ "$ENVIRONMENT" == "staging" ]]; then
        rm -f *.staging
    fi

    log_success "Manifests applied successfully"
}

# Wait for deployment to be ready
wait_for_deployment() {
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "DRY RUN: Skipping deployment wait"
        return 0
    fi

    log_info "Waiting for deployment to be ready (timeout: ${TIMEOUT}s)..."

    # Wait for main deployment
    if kubectl rollout status deployment/globeco-order-generation-service -n "$NAMESPACE" --timeout="${TIMEOUT}s"; then
        log_success "Application deployment is ready"
    else
        log_error "Application deployment failed to become ready within ${TIMEOUT}s"
        return 1
    fi

    # Wait for MongoDB StatefulSet if it exists
    if kubectl get statefulset globeco-order-generation-service-mongodb -n "$NAMESPACE" &> /dev/null; then
        log_info "Waiting for MongoDB StatefulSet..."
        if kubectl rollout status statefulset/globeco-order-generation-service-mongodb -n "$NAMESPACE" --timeout="${TIMEOUT}s"; then
            log_success "MongoDB StatefulSet is ready"
        else
            log_warning "MongoDB StatefulSet failed to become ready within ${TIMEOUT}s"
        fi
    fi
}

# Verify deployment
verify_deployment() {
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "DRY RUN: Skipping deployment verification"
        return 0
    fi

    log_info "Verifying deployment..."

    # Check pods
    local ready_pods
    ready_pods=$(kubectl get pods -n "$NAMESPACE" -l app=globeco-order-generation-service --field-selector=status.phase=Running --no-headers | wc -l)

    if [[ "$ready_pods" -eq 0 ]]; then
        log_error "No pods are running"
        return 1
    fi

    log_success "Found $ready_pods running pods"

    # Check services
    if kubectl get service globeco-order-generation-service -n "$NAMESPACE" &> /dev/null; then
        log_success "Service is available"
    else
        log_warning "Service not found"
    fi

    # Test health endpoint if possible
    local pod_name
    if pod_name=$(kubectl get pods -n "$NAMESPACE" -l app=globeco-order-generation-service --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null); then
        log_info "Testing health endpoint..."
        if kubectl exec -n "$NAMESPACE" "$pod_name" -- curl -f http://localhost:8080/health/live &> /dev/null; then
            log_success "Health check passed"
        else
            log_warning "Health check failed (service may still be starting)"
        fi
    fi

    log_success "Deployment verification completed"
}

# Rollback deployment
rollback_deployment() {
    log_info "Rolling back deployment in namespace: $NAMESPACE"

    if [[ ! -f "$PROJECT_ROOT/.backup/latest" ]]; then
        log_error "No backup found for rollback"
        exit 1
    fi

    local backup_dir
    backup_dir=$(cat "$PROJECT_ROOT/.backup/latest")

    if [[ ! -d "$backup_dir" ]]; then
        log_error "Backup directory not found: $backup_dir"
        exit 1
    fi

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "DRY RUN: Would rollback to backup: $backup_dir"
        return 0
    fi

    log_info "Rolling back to: $backup_dir"

    # Apply backup files
    for file in "$backup_dir"/*.yaml; do
        if [[ -f "$file" ]]; then
            log_debug "Applying: $(basename "$file")"
            kubectl apply -f "$file"
        fi
    done

    # Wait for rollback to complete
    log_info "Waiting for rollback to complete..."
    wait_for_deployment

    log_success "Rollback completed"
}

# Show deployment status
show_status() {
    if [[ -z "$NAMESPACE" ]]; then
        log_warning "No namespace specified, cannot show status"
        return 0
    fi

    log_info "Deployment Status for namespace: $NAMESPACE"
    echo

    echo "Pods:"
    kubectl get pods -n "$NAMESPACE" -l app=globeco-order-generation-service || echo "No pods found"
    echo

    echo "Services:"
    kubectl get services -n "$NAMESPACE" -l app=globeco-order-generation-service || echo "No services found"
    echo

    echo "Deployments:"
    kubectl get deployments -n "$NAMESPACE" -l app=globeco-order-generation-service || echo "No deployments found"
    echo

    echo "HPA:"
    kubectl get hpa -n "$NAMESPACE" -l app=globeco-order-generation-service || echo "No HPA found"
    echo

    if [[ "$ENVIRONMENT" == "production" ]]; then
        echo "Ingress:"
        kubectl get ingress -n "$NAMESPACE" -l app=globeco-order-generation-service || echo "No ingress found"
    fi
}

# Cleanup on exit
cleanup() {
    local exit_code=$?
    if [[ $exit_code -ne 0 ]] && [[ "$DRY_RUN" == "false" ]] && [[ "$FORCE" != "true" ]]; then
        log_warning "Deployment failed. Rollback may be available:"
        log_warning "$0 -e $ENVIRONMENT --rollback"
    fi
}

# Main function
main() {
    log_info "Starting deployment process..."

    if [[ "$VERBOSE" == "true" ]]; then
        log_debug "Script: $0"
        log_debug "Arguments: $*"
        log_debug "Working directory: $(pwd)"
    fi

    # Set up cleanup trap
    trap cleanup EXIT

    # Run appropriate workflow
    if [[ "$ROLLBACK" == "true" ]]; then
        check_prerequisites
        rollback_deployment
        verify_deployment
        show_status
        log_success "Rollback completed successfully!"
    elif [[ "$VALIDATE_ONLY" == "true" ]]; then
        validate_manifests
        log_success "Validation completed successfully!"
    else
        # Full deployment workflow
        check_prerequisites
        validate_image
        validate_manifests
        backup_deployment
        deploy_application
        wait_for_deployment
        verify_deployment
        show_status

        if [[ "$DRY_RUN" == "true" ]]; then
            log_success "Dry run completed successfully!"
        else
            log_success "Deployment completed successfully!"
            if [[ "$ENVIRONMENT" == "production" ]]; then
                log_info "Production URL: https://order-generation.globeco.kasbench.org"
                log_info "Health Check: https://order-generation.globeco.kasbench.org/health/health"
                log_info "API Documentation: https://order-generation.globeco.kasbench.org/docs"
            elif [[ "$ENVIRONMENT" == "staging" ]]; then
                log_info "Staging URL: https://order-generation-staging.globeco.kasbench.org"
            fi
        fi
    fi
}

# Parse arguments and run main function
parse_args "$@"
validate_args
main
