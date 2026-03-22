#!/bin/bash
# OpenMemory Rollback Script for Fly.io
# Rolls back to a previous release

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[ROLLBACK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1" >&2; exit 1; }

ENVIRONMENT="${1:-production}"
VERSION="${2:-}"

if [ "${ENVIRONMENT}" = "test" ]; then
    APP_NAME="openmemory-test"
else
    APP_NAME="openmemory-prod"
fi

list_releases() {
    log "Recent releases for ${APP_NAME}:"
    flyctl releases list -a "${APP_NAME}" | head -20
}

if [ -z "${VERSION}" ]; then
    echo "OpenMemory Rollback"
    echo ""
    echo "Usage: $0 <environment> <version>"
    echo ""
    echo "Environments: test, production"
    echo ""
    list_releases
    exit 1
fi

log "Rolling back ${APP_NAME} to version ${VERSION}..."

# Get current version for safety
CURRENT_VERSION=$(flyctl releases list -a "${APP_NAME}" | head -2 | tail -1 | awk '{print $1}')
log "Current version: ${CURRENT_VERSION}"

# Confirm rollback
echo -e "${YELLOW}WARNING: This will roll back to version ${VERSION}${NC}"
read -p "Continue? (yes/no): " CONFIRM
if [ "${CONFIRM}" != "yes" ]; then
    log "Rollback cancelled"
    exit 0
fi

# Perform rollback
flyctl deploy --image "registry.fly.io/${APP_NAME}:${VERSION}" -a "${APP_NAME}"

# Verify health
log "Verifying health after rollback..."
sleep 10

if curl -sf "https://${APP_NAME}.fly.dev/health" > /dev/null; then
    log "Rollback successful! Now running version ${VERSION}"
else
    error "Health check failed after rollback!"
fi

# Show current status
flyctl status -a "${APP_NAME}"
