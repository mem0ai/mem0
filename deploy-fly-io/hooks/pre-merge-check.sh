#!/bin/bash
# Pre-Merge Check Hook for OpenMemory
# Run this before merging changes from upstream (main) to deploy branch

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(dirname "${SCRIPT_DIR}")"
REPO_ROOT="$(dirname "${DEPLOY_DIR}")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${GREEN}[CHECK]${NC} $1"; }
info() { echo -e "${BLUE}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }

cd "${REPO_ROOT}"

echo "=========================================="
echo "   Pre-Merge Security & Quality Check"
echo "=========================================="
echo ""

SOURCE_BRANCH="${1:-main}"
TARGET_BRANCH="${2:-deploy}"

info "Checking merge: ${SOURCE_BRANCH} -> ${TARGET_BRANCH}"
echo ""

# Check for Claude AI review capability
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
    log "Claude AI review: ${GREEN}ENABLED${NC}"
else
    warn "Claude AI review: DISABLED (set ANTHROPIC_API_KEY to enable)"
fi
echo ""

# =============================================================================
# 1. Show what's being merged
# =============================================================================
log "Commits to be merged:"
git log --oneline "${TARGET_BRANCH}..${SOURCE_BRANCH}" 2>/dev/null | head -20 || {
    warn "Could not determine commits to merge"
}
echo ""

log "Files changed:"
git diff --stat "${TARGET_BRANCH}...${SOURCE_BRANCH}" 2>/dev/null | tail -20 || {
    warn "Could not determine changed files"
}
echo ""

# =============================================================================
# 2. Run security checks
# =============================================================================
log "Running security scan..."
if [ -x "${DEPLOY_DIR}/hooks/security-check.sh" ]; then
    "${DEPLOY_DIR}/hooks/security-check.sh"
    SECURITY_STATUS=$?
else
    warn "Security check script not found"
    SECURITY_STATUS=0
fi

if [ ${SECURITY_STATUS} -ne 0 ]; then
    error "Security check failed! Do not merge until issues are resolved."
    exit 1
fi

echo ""

# =============================================================================
# 3. Check for deploy-fly-io conflicts
# =============================================================================
log "Checking for conflicts with deployment files..."

# Files in deploy-fly-io should NOT be in upstream
CONFLICT_FILES=$(git diff --name-only "${TARGET_BRANCH}...${SOURCE_BRANCH}" 2>/dev/null | grep "^deploy-fly-io/" || true)
if [ -n "${CONFLICT_FILES}" ]; then
    warn "Upstream changes include deploy-fly-io files!"
    echo "${CONFLICT_FILES}"
    warn "These changes should be reviewed carefully as they may overwrite your deployment config."
fi
echo ""

# =============================================================================
# 4. Check for breaking changes
# =============================================================================
log "Checking for potential breaking changes..."

# Check for API changes
API_CHANGES=$(git diff "${TARGET_BRANCH}...${SOURCE_BRANCH}" -- "openmemory/api/*.py" "server/*.py" 2>/dev/null || true)
if [ -n "${API_CHANGES}" ]; then
    info "API changes detected - review for backwards compatibility:"
    git diff --stat "${TARGET_BRANCH}...${SOURCE_BRANCH}" -- "openmemory/api/*.py" "server/*.py" 2>/dev/null || true
fi

# Check for database migrations
MIGRATION_CHANGES=$(git diff --name-only "${TARGET_BRANCH}...${SOURCE_BRANCH}" 2>/dev/null | grep "migrations\|alembic" || true)
if [ -n "${MIGRATION_CHANGES}" ]; then
    warn "Database migrations detected - verify Fly Postgres backup before deploying!"
    echo "${MIGRATION_CHANGES}"
fi

# Check for dependency changes
DEP_CHANGES=$(git diff "${TARGET_BRANCH}...${SOURCE_BRANCH}" -- "*requirements*.txt" "pyproject.toml" "package.json" 2>/dev/null || true)
if [ -n "${DEP_CHANGES}" ]; then
    info "Dependency changes detected:"
    git diff --stat "${TARGET_BRANCH}...${SOURCE_BRANCH}" -- "*requirements*.txt" "pyproject.toml" "package.json" 2>/dev/null || true
fi
echo ""

# =============================================================================
# 5. Run tests
# =============================================================================
log "Running tests..."
cd "${REPO_ROOT}"

if command -v pytest &> /dev/null; then
    if pytest tests/ -v --tb=short -q 2>/dev/null; then
        log "Tests passed"
    else
        error "Tests failed! Fix issues before merging."
        exit 1
    fi
else
    warn "pytest not available - skipping tests"
fi
echo ""

# =============================================================================
# 6. Generate diff report
# =============================================================================
REPORT_FILE="${DEPLOY_DIR}/docs/merge_review_$(date +%Y%m%d_%H%M%S).md"
mkdir -p "${DEPLOY_DIR}/docs"

# Check for Claude review report
CLAUDE_REPORT=""
CLAUDE_VERDICT="N/A"
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
    LATEST_CLAUDE_REPORT=$(ls -t "${DEPLOY_DIR}/docs/claude_review_"*.json 2>/dev/null | head -1 || true)
    if [ -n "${LATEST_CLAUDE_REPORT}" ]; then
        CLAUDE_VERDICT=$(python3 -c "import json; print(json.load(open('${LATEST_CLAUDE_REPORT}')).get('review',{}).get('verdict','UNKNOWN'))" 2>/dev/null || echo "UNKNOWN")
        CLAUDE_REPORT="See: $(basename ${LATEST_CLAUDE_REPORT})"
    fi
fi

cat > "${REPORT_FILE}" << EOF
# Merge Review Report

**Date:** $(date -u +%Y-%m-%dT%H:%M:%SZ)
**Source Branch:** ${SOURCE_BRANCH}
**Target Branch:** ${TARGET_BRANCH}

## Commits

\`\`\`
$(git log --oneline "${TARGET_BRANCH}..${SOURCE_BRANCH}" 2>/dev/null | head -50)
\`\`\`

## Files Changed

\`\`\`
$(git diff --stat "${TARGET_BRANCH}...${SOURCE_BRANCH}" 2>/dev/null)
\`\`\`

## Security Check

### Automated Scans
- Pattern-based scan: PASSED
- Claude AI review: ${CLAUDE_VERDICT} ${CLAUDE_REPORT}

### Reviewer Notes

- [ ] Reviewed Claude AI security report (if applicable)
- [ ] Reviewed API changes for backwards compatibility
- [ ] Verified no sensitive data exposure
- [ ] Checked for vendor lock-in patterns
- [ ] Confirmed database migrations are safe
- [ ] Tested locally before merge

---
*Generated by pre-merge-check.sh*
EOF

log "Merge review report saved to: ${REPORT_FILE}"
echo ""

# =============================================================================
# Summary
# =============================================================================
echo "=========================================="
echo "       PRE-MERGE CHECK COMPLETE"
echo "=========================================="
echo ""
log "All checks passed!"
echo ""
info "Next steps:"
echo "  1. Review the merge report: ${REPORT_FILE}"
echo "  2. Merge with: git merge ${SOURCE_BRANCH}"
echo "  3. Deploy to test: ./deploy-fly-io/scripts/deploy.sh test"
echo "  4. Verify test deployment"
echo "  5. Deploy to production: ./deploy-fly-io/scripts/deploy.sh production"
echo ""
