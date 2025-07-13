#!/bin/bash
# Container Security Scanning Script for GlobeCo Order Generation Service
# Performs comprehensive security analysis using multiple tools

set -euo pipefail

# ===================================================================
# Configuration
# ===================================================================
DOCKER_REPO="kasbench/globeco-order-generation-service"
DEFAULT_TAG="latest"
REPORT_DIR="security-reports"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

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

# Setup report directory
setup_reports() {
    log "Setting up security reports directory..."
    mkdir -p "${REPORT_DIR}"

    # Create timestamped subdirectory
    REPORT_SUBDIR="${REPORT_DIR}/scan_${TIMESTAMP}"
    mkdir -p "${REPORT_SUBDIR}"

    success "Reports will be saved to: ${REPORT_SUBDIR}"
}

# Install security scanning tools
install_tools() {
    log "Checking and installing security scanning tools..."

    # Check if Trivy is installed
    if ! command -v trivy &> /dev/null; then
        log "Installing Trivy..."
        case "$(uname -s)" in
            Darwin)
                if command -v brew &> /dev/null; then
                    brew install trivy
                else
                    error "Trivy not installed and Homebrew not available on macOS"
                fi
                ;;
            Linux)
                # Install Trivy for Linux
                curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin
                ;;
            *)
                warning "Unknown OS, please install Trivy manually"
                ;;
        esac
    else
        log "Trivy already installed: $(trivy --version)"
    fi

    # Check if Syft is installed (for SBOM generation)
    if ! command -v syft &> /dev/null; then
        log "Installing Syft..."
        case "$(uname -s)" in
            Darwin)
                if command -v brew &> /dev/null; then
                    brew install syft
                else
                    warning "Syft not available, skipping SBOM generation"
                fi
                ;;
            Linux)
                curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sh -s -- -b /usr/local/bin
                ;;
            *)
                warning "Unknown OS, skipping Syft installation"
                ;;
        esac
    else
        log "Syft already installed: $(syft --version)"
    fi

    # Check if Grype is installed (for vulnerability scanning)
    if ! command -v grype &> /dev/null; then
        log "Installing Grype..."
        case "$(uname -s)" in
            Darwin)
                if command -v brew &> /dev/null; then
                    brew install grype
                else
                    warning "Grype not available, will use Trivy only"
                fi
                ;;
            Linux)
                curl -sSfL https://raw.githubusercontent.com/anchore/grype/main/install.sh | sh -s -- -b /usr/local/bin
                ;;
            *)
                warning "Unknown OS, skipping Grype installation"
                ;;
        esac
    else
        log "Grype already installed: $(grype --version)"
    fi
}

# Trivy vulnerability scanning
run_trivy_scan() {
    local image=$1
    log "Running Trivy vulnerability scan..."

    # Pull the image first
    docker pull "${image}" || error "Failed to pull image: ${image}"

    # Comprehensive Trivy scan with multiple output formats
    local trivy_base="${REPORT_SUBDIR}/trivy"

    # JSON format for programmatic processing
    log "Running Trivy scan (JSON format)..."
    trivy image --format json --output "${trivy_base}_vulnerabilities.json" "${image}" || warning "Trivy scan completed with issues"

    # Table format for human readability
    log "Running Trivy scan (Table format)..."
    trivy image --format table --output "${trivy_base}_vulnerabilities.txt" "${image}" || warning "Trivy scan completed with issues"

    # SARIF format for CI/CD integration
    log "Running Trivy scan (SARIF format)..."
    trivy image --format sarif --output "${trivy_base}_vulnerabilities.sarif" "${image}" || warning "Trivy scan completed with issues"

    # Critical and high vulnerabilities only
    log "Running Trivy scan (Critical/High only)..."
    trivy image --severity CRITICAL,HIGH --format table --output "${trivy_base}_critical_high.txt" "${image}" || warning "Critical/High vulnerabilities found"

    # Configuration issues scan
    log "Running Trivy configuration scan..."
    trivy image --scanners config --format json --output "${trivy_base}_config_issues.json" "${image}" || warning "Configuration issues found"

    # Secret scanning
    log "Running Trivy secret scan..."
    trivy image --scanners secret --format json --output "${trivy_base}_secrets.json" "${image}" || warning "Secrets found in image"

    success "Trivy scans completed"
}

# Syft SBOM generation
generate_sbom() {
    local image=$1

    if ! command -v syft &> /dev/null; then
        warning "Syft not available, skipping SBOM generation"
        return
    fi

    log "Generating Software Bill of Materials (SBOM)..."

    local sbom_base="${REPORT_SUBDIR}/sbom"

    # Generate SBOM in multiple formats
    syft "${image}" -o json="${sbom_base}.json" || warning "SBOM generation failed"
    syft "${image}" -o spdx-json="${sbom_base}_spdx.json" || warning "SPDX SBOM generation failed"
    syft "${image}" -o cyclonedx-json="${sbom_base}_cyclonedx.json" || warning "CycloneDX SBOM generation failed"
    syft "${image}" -o table="${sbom_base}.txt" || warning "SBOM table generation failed"

    success "SBOM generation completed"
}

# Grype vulnerability scanning
run_grype_scan() {
    local image=$1

    if ! command -v grype &> /dev/null; then
        warning "Grype not available, skipping additional vulnerability scan"
        return
    fi

    log "Running Grype vulnerability scan..."

    local grype_base="${REPORT_SUBDIR}/grype"

    # Grype scan with different output formats
    grype "${image}" -o json > "${grype_base}_vulnerabilities.json" || warning "Grype scan completed with issues"
    grype "${image}" -o table > "${grype_base}_vulnerabilities.txt" || warning "Grype scan completed with issues"
    grype "${image}" -o sarif > "${grype_base}_vulnerabilities.sarif" || warning "Grype scan completed with issues"

    success "Grype scan completed"
}

# Docker image analysis
analyze_image() {
    local image=$1
    log "Analyzing Docker image properties..."

    local analysis_file="${REPORT_SUBDIR}/image_analysis.json"

    # Get image information
    {
        echo "{"
        echo "  \"timestamp\": \"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\","
        echo "  \"image\": \"${image}\","
        echo "  \"inspection\": $(docker inspect "${image}" 2>/dev/null || echo "null"),"
        echo "  \"history\": $(docker history --format json "${image}" 2>/dev/null | jq -s '.' || echo "null"),"
        echo "  \"layers\": $(docker image inspect "${image}" --format '{{json .RootFS.Layers}}' 2>/dev/null || echo "null")"
        echo "}"
    } > "${analysis_file}"

    # Image size analysis
    log "Image size: $(docker images "${image}" --format "{{.Size}}")"

    success "Image analysis completed"
}

# Generate security summary report
generate_summary() {
    log "Generating security summary report..."

    local summary_file="${REPORT_SUBDIR}/security_summary.md"

    cat > "${summary_file}" << EOF
# Security Scan Summary

**Scan Date:** $(date -u +"%Y-%m-%d %H:%M:%S UTC")
**Image:** ${IMAGE_TAG}
**Scan ID:** ${TIMESTAMP}

## Summary

This report contains comprehensive security analysis of the GlobeCo Order Generation Service container image.

## Files Generated

### Vulnerability Scans
- \`trivy_vulnerabilities.json\` - Trivy vulnerability scan (JSON)
- \`trivy_vulnerabilities.txt\` - Trivy vulnerability scan (human-readable)
- \`trivy_vulnerabilities.sarif\` - Trivy vulnerability scan (SARIF)
- \`trivy_critical_high.txt\` - Critical and high vulnerabilities only
- \`grype_vulnerabilities.json\` - Grype vulnerability scan (JSON)
- \`grype_vulnerabilities.txt\` - Grype vulnerability scan (human-readable)

### Configuration Analysis
- \`trivy_config_issues.json\` - Configuration security issues
- \`trivy_secrets.json\` - Secret scanning results

### Software Bill of Materials (SBOM)
- \`sbom.json\` - Software components (Syft format)
- \`sbom_spdx.json\` - SBOM in SPDX format
- \`sbom_cyclonedx.json\` - SBOM in CycloneDX format
- \`sbom.txt\` - SBOM summary table

### Image Analysis
- \`image_analysis.json\` - Docker image metadata and layer analysis

## Recommendations

1. Review all CRITICAL and HIGH severity vulnerabilities
2. Update base image and dependencies regularly
3. Remove any unnecessary packages from the image
4. Implement container runtime security controls
5. Monitor for new vulnerabilities in production

## Next Steps

1. Address critical vulnerabilities immediately
2. Create remediation plan for high-severity issues
3. Integrate security scanning into CI/CD pipeline
4. Set up automated vulnerability monitoring

EOF

    success "Security summary generated: ${summary_file}"
}

# Main scanning function
run_security_scan() {
    local image=$1

    log "Starting comprehensive security scan for: ${image}"

    # Setup
    setup_reports
    install_tools

    # Run scans
    run_trivy_scan "${image}"
    generate_sbom "${image}"
    run_grype_scan "${image}"
    analyze_image "${image}"

    # Generate summary
    generate_summary

    # Final report
    success "Security scanning completed!"
    log "Reports generated in: ${REPORT_SUBDIR}"
    log ""
    log "Key files to review:"
    log "  - ${REPORT_SUBDIR}/security_summary.md"
    log "  - ${REPORT_SUBDIR}/trivy_critical_high.txt"
    log "  - ${REPORT_SUBDIR}/trivy_config_issues.json"
    log "  - ${REPORT_SUBDIR}/trivy_secrets.json"
}

# Help function
show_help() {
    cat << EOF
Container Security Scanning Script for GlobeCo Order Generation Service

Usage: $0 [OPTIONS] [IMAGE_TAG]

OPTIONS:
    -h, --help          Show this help message
    -r, --reports-dir   Set custom reports directory (default: security-reports)

ARGUMENTS:
    IMAGE_TAG          Docker image to scan (default: ${DOCKER_REPO}:${DEFAULT_TAG})

EXAMPLES:
    # Scan latest production image
    $0

    # Scan specific version
    $0 kasbench/globeco-order-generation-service:v1.2.3

    # Scan development image
    $0 kasbench/globeco-order-generation-service:latest-dev

    # Custom reports directory
    $0 --reports-dir /tmp/security-reports

TOOLS USED:
    - Trivy: Vulnerability scanning, configuration issues, secrets
    - Syft: Software Bill of Materials (SBOM) generation
    - Grype: Additional vulnerability scanning
    - Docker: Image analysis and inspection

OUTPUTS:
    - JSON reports for programmatic processing
    - Human-readable text reports
    - SARIF reports for CI/CD integration
    - Software Bill of Materials in multiple formats
    - Security summary with recommendations

EOF
}

# Parse command line arguments
IMAGE_TAG="${DOCKER_REPO}:${DEFAULT_TAG}"

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -r|--reports-dir)
            REPORT_DIR="$2"
            shift 2
            ;;
        -*)
            error "Unknown option: $1. Use --help for usage information."
            ;;
        *)
            IMAGE_TAG="$1"
            shift
            ;;
    esac
done

# Run the security scan
run_security_scan "${IMAGE_TAG}"
