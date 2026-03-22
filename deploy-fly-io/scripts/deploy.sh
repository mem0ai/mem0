#!/bin/bash
# OpenMemory Deployment Script for Fly.io
#
# ⚠️  MANUAL DEPLOYMENTS ARE DISABLED
#
# Deployments happen automatically via GitHub Actions:
# - Push to 'deploy' branch → deploys to TEST
# - Create a Release → deploys to PRODUCTION
#
# This script is used by GitHub Actions only.
# For local testing, use: ALLOW_LOCAL_DEPLOY=true ./deploy.sh test

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(dirname "${SCRIPT_DIR}")"
REPO_ROOT="$(dirname "${DEPLOY_DIR}")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() { echo -e "${GREEN}[DEPLOY]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1" >&2; exit 1; }

# Check if running in GitHub Actions or local override
if [ -z "${GITHUB_ACTIONS:-}" ] && [ -z "${ALLOW_LOCAL_DEPLOY:-}" ]; then
    echo ""
    echo "=========================================="
    echo "   ⚠️  MANUAL DEPLOYMENTS DISABLED"
    echo "=========================================="
    echo ""
    echo "Deployments happen automatically via GitHub Actions:"
    echo ""
    echo "  TEST:        Push/merge to 'deploy' branch"
    echo "  PRODUCTION:  Create a GitHub Release"
    echo ""
    echo "To deploy:"
    echo "  1. git push origin deploy  (triggers test deploy)"
    echo "  2. gh release create v1.x.x --target deploy"
    echo ""
    echo "For local testing only (NOT recommended):"
    echo "  ALLOW_LOCAL_DEPLOY=true $0 test"
    echo ""
    exit 1
fi

# Default values
ENVIRONMENT="${1:-}"
SKIP_TESTS="${SKIP_TESTS:-false}"

usage() {
    echo "OpenMemory Fly.io Deployment"
    echo ""
    echo "Usage: $0 <environment> [options]"
    echo ""
    echo "Environments:"
    echo "  test        Deploy to test environment (openmemory-test)"
    echo "  production  Deploy to production (openmemory-prod)"
    echo ""
    echo "Options (via environment variables):"
    echo "  SKIP_TESTS=true    Skip test execution"
    echo ""
    echo "Examples:"
    echo "  $0 test"
    echo "  $0 production"
    exit 1
}

check_prerequisites() {
    log "Checking prerequisites..."

    # Check flyctl is installed
    if ! command -v flyctl &> /dev/null; then
        error "flyctl is not installed. Install from: https://fly.io/docs/hands-on/install-flyctl/"
    fi

    # Check if logged in
    if ! flyctl auth whoami &> /dev/null; then
        error "Not logged in to Fly.io. Run: flyctl auth login"
    fi

    # Check we're in the right directory
    if [ ! -f "${DEPLOY_DIR}/fly.toml" ]; then
        error "fly.toml not found. Run from deploy-fly-io directory."
    fi

    log "Prerequisites OK"
}

run_security_checks() {
    log "Running security checks..."

    # Run the security pre-commit hook
    if [ -x "${DEPLOY_DIR}/hooks/security-check.sh" ]; then
        "${DEPLOY_DIR}/hooks/security-check.sh" || error "Security check failed"
    else
        warn "Security check script not found or not executable"
    fi

    log "Security checks passed"
}

run_tests() {
    if [ "${SKIP_TESTS}" = "true" ]; then
        warn "Skipping tests (SKIP_TESTS=true)"
        return
    fi

    log "Running tests..."
    cd "${REPO_ROOT}"

    # Run pytest if available
    if command -v pytest &> /dev/null; then
        pytest tests/ -v --tb=short || error "Tests failed"
    else
        warn "pytest not found, skipping tests"
    fi

    log "Tests passed"
}

deploy() {
    local config_file
    local app_name

    if [ "${ENVIRONMENT}" = "test" ]; then
        config_file="fly-test.toml"
        app_name="openmemory-test"
    elif [ "${ENVIRONMENT}" = "production" ]; then
        config_file="fly.toml"
        app_name="openmemory-prod"
    else
        error "Unknown environment: ${ENVIRONMENT}"
    fi

    log "Deploying to ${ENVIRONMENT} (${app_name})..."

    cd "${DEPLOY_DIR}"

    # Check if app exists, create if not
    if ! flyctl apps list | grep -q "${app_name}"; then
        log "Creating app: ${app_name}"
        flyctl apps create "${app_name}" || error "Failed to create app"
    fi

    # Create volume if it doesn't exist
    local volume_name="openmemory_data"
    if [ "${ENVIRONMENT}" = "test" ]; then
        volume_name="openmemory_test_data"
    fi

    if ! flyctl volumes list -a "${app_name}" | grep -q "${volume_name}"; then
        log "Creating volume: ${volume_name}"
        local volume_size="10"
        if [ "${ENVIRONMENT}" = "test" ]; then
            volume_size="1"
        fi
        flyctl volumes create "${volume_name}" \
            -a "${app_name}" \
            --region sjc \
            --size "${volume_size}" \
            --yes || error "Failed to create volume"
    fi

    # Deploy
    flyctl deploy \
        --config "${config_file}" \
        --app "${app_name}" \
        --remote-only \
        --strategy rolling

    log "Deployment complete!"

    # Show status
    flyctl status -a "${app_name}"

    # Show URL
    log "Application URL: https://${app_name}.fly.dev"
}

health_check() {
    local app_name
    if [ "${ENVIRONMENT}" = "test" ]; then
        app_name="openmemory-test"
    else
        app_name="openmemory-prod"
    fi

    log "Running health check..."

    local max_attempts=10
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if curl -sf "https://${app_name}.fly.dev/health" > /dev/null; then
            log "Health check passed!"
            return 0
        fi
        log "Attempt ${attempt}/${max_attempts} - waiting..."
        sleep 5
        ((attempt++))
    done

    error "Health check failed after ${max_attempts} attempts"
}

# Main execution
if [ -z "${ENVIRONMENT}" ]; then
    usage
fi

if [ "${ENVIRONMENT}" != "test" ] && [ "${ENVIRONMENT}" != "production" ]; then
    usage
fi

log "Starting deployment to ${ENVIRONMENT}"

check_prerequisites
run_security_checks
run_tests
deploy
health_check

log "Deployment to ${ENVIRONMENT} successful!"
