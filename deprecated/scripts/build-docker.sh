#!/bin/bash
# Multi-architecture Docker build script for GlobeCo Order Generation Service
# Builds and pushes to kasbench/globeco-order-generation-service on Docker Hub

set -euo pipefail

# ===================================================================
# Configuration
# ===================================================================
DOCKER_REPO="kasbench/globeco-order-generation-service"
PLATFORMS="linux/amd64,linux/arm64"
BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
VCS_REF=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
VERSION=${VERSION:-$(git describe --tags --always 2>/dev/null || echo "dev")}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ===================================================================
# Functions
# ===================================================================
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}" >&2
    exit 1
}

warning() {
    echo -e "${YELLOW}[WARNING] $1${NC}" >&2
}

success() {
    echo -e "${GREEN}[SUCCESS] $1${NC}"
}

# Check if required tools are installed
check_requirements() {
    log "Checking requirements..."

    if ! command -v docker &> /dev/null; then
        error "Docker is not installed or not in PATH"
    fi

    if ! docker buildx version &> /dev/null; then
        error "Docker Buildx is not available"
    fi

    if ! docker buildx ls | grep -q "docker-container"; then
        log "Creating buildx builder for multi-architecture builds..."
        docker buildx create --name multiarch-builder --driver docker-container --use
        docker buildx inspect --bootstrap
    else
        log "Using existing buildx builder"
        docker buildx use multiarch-builder 2>/dev/null || docker buildx create --name multiarch-builder --driver docker-container --use
    fi

    success "Requirements check passed"
}

# Build and push multi-architecture images
build_and_push() {
    local target=$1
    local tag_suffix=$2
    local push_flag=${3:-"--push"}

    local full_tag="${DOCKER_REPO}:${VERSION}${tag_suffix}"
    local latest_tag="${DOCKER_REPO}:latest${tag_suffix}"

    log "Building multi-architecture image for target: ${target}"
    log "Platforms: ${PLATFORMS}"
    log "Tags: ${full_tag}, ${latest_tag}"

    # Build arguments
    local build_args=(
        --platform "${PLATFORMS}"
        --target "${target}"
        --build-arg "BUILD_DATE=${BUILD_DATE}"
        --build-arg "VCS_REF=${VCS_REF}"
        --build-arg "VERSION=${VERSION}"
        --tag "${full_tag}"
        --tag "${latest_tag}"
        "${push_flag}"
        .
    )

    if ! docker buildx build "${build_args[@]}"; then
        error "Failed to build ${target} image"
    fi

    success "Successfully built and pushed ${target} image"
}

# Run security scan on built image
security_scan() {
    local image=$1
    log "Running security scan on ${image}..."

    # Pull image for scanning (amd64 only for scanning)
    docker pull --platform linux/amd64 "${image}" || warning "Could not pull image for scanning"

    # Run Trivy security scan if available
    if command -v trivy &> /dev/null; then
        log "Running Trivy security scan..."
        trivy image --exit-code 0 --severity HIGH,CRITICAL "${image}" || warning "Security scan found issues"
    else
        warning "Trivy not installed, skipping security scan"
    fi
}

# Test the built image
test_image() {
    local image=$1
    log "Testing image: ${image}"

    # Test basic functionality
    log "Testing basic container functionality..."
    local container_id
    container_id=$(docker run -d --platform linux/amd64 "${image}" sleep 30)

    # Wait for container to be ready
    sleep 5

    # Check if container is running
    if ! docker ps --filter "id=${container_id}" --format "table {{.ID}}" | grep -q "${container_id}"; then
        docker logs "${container_id}"
        docker rm -f "${container_id}" 2>/dev/null
        error "Container failed to start"
    fi

    # Cleanup
    docker rm -f "${container_id}" 2>/dev/null
    success "Image test passed"
}

# Main build function
main() {
    log "Starting multi-architecture build for GlobeCo Order Generation Service"
    log "Repository: ${DOCKER_REPO}"
    log "Version: ${VERSION}"
    log "VCS Ref: ${VCS_REF}"
    log "Build Date: ${BUILD_DATE}"

    # Check requirements
    check_requirements

    # Ensure we're in the project root
    if [[ ! -f "Dockerfile" ]]; then
        error "Dockerfile not found. Please run this script from the project root."
    fi

    # Login to Docker Hub if credentials are available
    if [[ -n "${DOCKER_USERNAME:-}" && -n "${DOCKER_PASSWORD:-}" ]]; then
        log "Logging in to Docker Hub..."
        echo "${DOCKER_PASSWORD}" | docker login -u "${DOCKER_USERNAME}" --password-stdin
    elif [[ -n "${DOCKER_TOKEN:-}" ]]; then
        log "Logging in to Docker Hub with token..."
        echo "${DOCKER_TOKEN}" | docker login -u "${DOCKER_USERNAME:-kasbench}" --password-stdin
    else
        warning "No Docker Hub credentials provided. Assuming already logged in."
    fi

    # Build development image
    log "Building development image..."
    build_and_push "development" "-dev"

    # Build production image
    log "Building production image..."
    build_and_push "production" ""

    # Build testing image (no push, local only)
    log "Building testing image (local only)..."
    build_and_push "testing" "-test" "--load"

    # Test the production image
    test_image "${DOCKER_REPO}:${VERSION}"

    # Security scan
    security_scan "${DOCKER_REPO}:${VERSION}"

    # Summary
    success "Multi-architecture build completed successfully!"
    log "Images built and pushed:"
    log "  - ${DOCKER_REPO}:${VERSION} (production)"
    log "  - ${DOCKER_REPO}:latest (production)"
    log "  - ${DOCKER_REPO}:${VERSION}-dev (development)"
    log "  - ${DOCKER_REPO}:latest-dev (development)"
    log "  - ${DOCKER_REPO}:${VERSION}-test (testing, local only)"

    # Image size information
    log "Checking image sizes..."
    docker images "${DOCKER_REPO}" --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"
}

# Help function
show_help() {
    cat << EOF
Multi-architecture Docker build script for GlobeCo Order Generation Service

Usage: $0 [OPTIONS]

OPTIONS:
    -h, --help          Show this help message
    -v, --version VER   Set version tag (default: git describe)
    --no-push          Build locally without pushing to registry
    --dry-run          Show what would be built without actually building

ENVIRONMENT VARIABLES:
    VERSION             Version tag to use
    DOCKER_USERNAME     Docker Hub username
    DOCKER_PASSWORD     Docker Hub password
    DOCKER_TOKEN        Docker Hub access token

EXAMPLES:
    # Build and push with auto-detected version
    $0

    # Build specific version
    $0 --version v1.2.3

    # Build locally without pushing
    $0 --no-push

    # Dry run to see what would be built
    $0 --dry-run

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -v|--version)
            VERSION="$2"
            shift 2
            ;;
        --no-push)
            # Override build_and_push function to use --load instead of --push
            build_and_push() {
                local target=$1
                local tag_suffix=$2
                build_and_push_impl "$target" "$tag_suffix" "--load"
            }
            shift
            ;;
        --dry-run)
            log "DRY RUN: Would build the following:"
            log "  - Target: development, Tag: ${DOCKER_REPO}:${VERSION}-dev"
            log "  - Target: production, Tag: ${DOCKER_REPO}:${VERSION}"
            log "  - Target: testing, Tag: ${DOCKER_REPO}:${VERSION}-test"
            log "  - Platforms: ${PLATFORMS}"
            exit 0
            ;;
        *)
            error "Unknown option: $1. Use --help for usage information."
            ;;
    esac
done

# Run main function
main "$@"
