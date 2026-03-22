#!/bin/bash
# Security Check Pre-Commit Hook for OpenMemory
# Run before merging upstream changes to detect backdoors and data exfiltration

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$(dirname "${SCRIPT_DIR}")")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[SECURITY]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[SECURITY ALERT]${NC} $1" >&2; }
critical() { echo -e "${RED}[CRITICAL]${NC} $1" >&2; exit 1; }

ISSUES_FOUND=0
WARNINGS_FOUND=0

cd "${REPO_ROOT}"

log "Starting security scan..."
log "Repository: ${REPO_ROOT}"

# =============================================================================
# 1. Check for suspicious network endpoints
# =============================================================================
log "Checking for suspicious network endpoints..."

SUSPICIOUS_DOMAINS=(
    "pastebin.com"
    "hastebin.com"
    "transfer.sh"
    "file.io"
    "0x0.st"
    "ngrok.io"
    "webhook.site"
    "requestbin"
    "pipedream"
    "beeceptor"
)

for domain in "${SUSPICIOUS_DOMAINS[@]}"; do
    if grep -r --include="*.py" --include="*.js" --include="*.ts" "${domain}" . 2>/dev/null | grep -v "deploy-fly-io/hooks"; then
        error "Suspicious domain found: ${domain}"
        ((ISSUES_FOUND++))
    fi
done

# Check for hardcoded IPs (potential C2)
if grep -rE --include="*.py" --include="*.js" --include="*.ts" \
    "([0-9]{1,3}\.){3}[0-9]{1,3}(:[0-9]+)?" . 2>/dev/null | \
    grep -v "127.0.0.1" | grep -v "0.0.0.0" | grep -v "localhost" | \
    grep -v "192.168" | grep -v "10.0.0" | grep -v "172.16" | \
    grep -v "deploy-fly-io/hooks" | grep -v ".git"; then
    warn "Hardcoded external IP addresses found - review manually"
    ((WARNINGS_FOUND++))
fi

# =============================================================================
# 2. Check for data exfiltration patterns
# =============================================================================
log "Checking for data exfiltration patterns..."

# Base64 encoding of secrets
EXFIL_PATTERNS=(
    "base64.*api.*key"
    "base64.*password"
    "base64.*secret"
    "base64.*token"
    "encode.*credentials"
    "btoa.*password"
    "btoa.*secret"
)

for pattern in "${EXFIL_PATTERNS[@]}"; do
    if grep -riE --include="*.py" --include="*.js" --include="*.ts" "${pattern}" . 2>/dev/null | grep -v "deploy-fly-io/hooks"; then
        error "Potential credential encoding found: ${pattern}"
        ((ISSUES_FOUND++))
    fi
done

# HTTP requests with sensitive data
if grep -rE --include="*.py" "requests\.(post|put).*\b(password|secret|api_key|token)\b" . 2>/dev/null | grep -v "deploy-fly-io/hooks"; then
    warn "HTTP request with potential sensitive data - review manually"
    ((WARNINGS_FOUND++))
fi

# =============================================================================
# 3. Check for backdoor patterns
# =============================================================================
log "Checking for backdoor patterns..."

BACKDOOR_PATTERNS=(
    "exec\s*\(\s*input"
    "eval\s*\(\s*input"
    "os\.system\s*\(\s*input"
    "subprocess\..*shell=True.*input"
    "__import__.*exec"
    "compile.*exec"
    "pickle\.loads.*input"
    "yaml\.load.*input"
    "marshal\.loads"
)

for pattern in "${BACKDOOR_PATTERNS[@]}"; do
    if grep -rE --include="*.py" "${pattern}" . 2>/dev/null | grep -v "deploy-fly-io/hooks"; then
        error "Potential backdoor pattern found: ${pattern}"
        ((ISSUES_FOUND++))
    fi
done

# =============================================================================
# 4. Check for suspicious environment variable access
# =============================================================================
log "Checking for suspicious environment variable access..."

# Look for env vars being sent externally
if grep -rE --include="*.py" "os\.environ.*requests\.|http.*os\.environ|urllib.*os\.environ" . 2>/dev/null | grep -v "deploy-fly-io/hooks"; then
    error "Environment variables potentially being exfiltrated"
    ((ISSUES_FOUND++))
fi

# Check for suspicious env var names
SUSPICIOUS_ENVS=(
    "CALLBACK_URL"
    "WEBHOOK_URL"
    "EXFIL"
    "C2_"
    "BEACON"
    "IMPLANT"
)

for env_name in "${SUSPICIOUS_ENVS[@]}"; do
    if grep -rE --include="*.py" --include="*.js" "os\.environ.*${env_name}|process\.env.*${env_name}" . 2>/dev/null | grep -v "deploy-fly-io/hooks"; then
        error "Suspicious environment variable: ${env_name}"
        ((ISSUES_FOUND++))
    fi
done

# =============================================================================
# 5. Check for vendor lock-in patterns
# =============================================================================
log "Checking for vendor lock-in patterns..."

# Look for mem0.ai specific endpoints that bypass local storage
if grep -rE --include="*.py" "api\.mem0\.ai|platform\.mem0\.ai" . 2>/dev/null | \
   grep -v "docs\|README\|\.md\|deploy-fly-io/hooks"; then
    warn "Found mem0.ai API endpoints - ensure they can be disabled for self-hosted"
    ((WARNINGS_FOUND++))
fi

# Check for telemetry that can't be disabled
TELEMETRY_PATTERNS=(
    "telemetry"
    "analytics"
    "tracking"
    "beacon"
    "metrics.*send"
    "posthog"
    "mixpanel"
    "segment"
    "amplitude"
)

for pattern in "${TELEMETRY_PATTERNS[@]}"; do
    if grep -riE --include="*.py" "${pattern}" . 2>/dev/null | \
       grep -v "prometheus\|deploy-fly-io\|test\|\.md"; then
        warn "Telemetry/analytics code found (${pattern}) - ensure it can be disabled"
        ((WARNINGS_FOUND++))
    fi
done

# =============================================================================
# 6. Check for suspicious file operations
# =============================================================================
log "Checking for suspicious file operations..."

# Writing to system directories
if grep -rE --include="*.py" "open\(.*(/etc/|/var/|/usr/|/root/|/home/).*w" . 2>/dev/null | grep -v "deploy-fly-io/hooks"; then
    error "Writing to system directories"
    ((ISSUES_FOUND++))
fi

# SSH key access
if grep -rE --include="*.py" "\.ssh/|id_rsa|id_ed25519|authorized_keys" . 2>/dev/null | grep -v "deploy-fly-io/hooks\|test\|\.md"; then
    error "SSH key access detected"
    ((ISSUES_FOUND++))
fi

# =============================================================================
# 7. Check for new dependencies
# =============================================================================
log "Checking for suspicious new dependencies..."

# Get changes since last known good commit (main branch)
if git rev-parse --verify main >/dev/null 2>&1; then
    NEW_DEPS=$(git diff main -- "*.txt" "*requirements*" "pyproject.toml" "package.json" 2>/dev/null | grep "^\+" | grep -v "^+++" || true)
    if [ -n "${NEW_DEPS}" ]; then
        warn "New dependencies detected - review manually:"
        echo "${NEW_DEPS}"
        ((WARNINGS_FOUND++))
    fi
fi

# =============================================================================
# 8. Run bandit security scanner (if available)
# =============================================================================
if command -v bandit &> /dev/null; then
    log "Running bandit security scanner..."
    BANDIT_OUTPUT=$(bandit -r mem0/ openmemory/ -f json 2>/dev/null || true)
    HIGH_SEVERITY=$(echo "${BANDIT_OUTPUT}" | python3 -c "import json,sys; d=json.load(sys.stdin); print(len([i for i in d.get('results',[]) if i.get('issue_severity')=='HIGH']))" 2>/dev/null || echo "0")

    if [ "${HIGH_SEVERITY}" -gt 0 ]; then
        error "Bandit found ${HIGH_SEVERITY} high severity issues"
        ((ISSUES_FOUND++))
    fi
else
    warn "bandit not installed - skipping Python security scan"
fi

# =============================================================================
# 9. Check for obfuscated code
# =============================================================================
log "Checking for obfuscated code..."

# Very long single lines (potential obfuscation)
if find . -name "*.py" -exec awk 'length > 500 {print FILENAME": line "NR" has "length" chars"}' {} \; 2>/dev/null | grep -v "deploy-fly-io/hooks\|\.git\|node_modules"; then
    warn "Very long lines detected - potential obfuscation"
    ((WARNINGS_FOUND++))
fi

# Hex-encoded strings
if grep -rE --include="*.py" "\\\\x[0-9a-f]{2}" . 2>/dev/null | wc -l | xargs test 10 -lt 2>/dev/null; then
    warn "Multiple hex-encoded strings found - review for obfuscation"
    ((WARNINGS_FOUND++))
fi

# =============================================================================
# 10. Claude AI Security Review (if ANTHROPIC_API_KEY is set)
# =============================================================================
CLAUDE_REVIEW_STATUS=0

if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
    log "Running Claude AI security review..."

    if command -v python3 &> /dev/null && python3 -c "import anthropic" 2>/dev/null; then
        CLAUDE_SCRIPT="${SCRIPT_DIR}/claude_review.py"

        if [ -x "${CLAUDE_SCRIPT}" ]; then
            # Run Claude review
            python3 "${CLAUDE_SCRIPT}" --base main --target HEAD || CLAUDE_REVIEW_STATUS=$?

            if [ ${CLAUDE_REVIEW_STATUS} -eq 2 ]; then
                error "Claude flagged DANGEROUS code patterns!"
                ((ISSUES_FOUND++))
            elif [ ${CLAUDE_REVIEW_STATUS} -eq 1 ]; then
                warn "Claude flagged SUSPICIOUS code - manual review required"
                ((WARNINGS_FOUND++))
            else
                log "Claude review passed"
            fi
        else
            warn "Claude review script not found: ${CLAUDE_SCRIPT}"
        fi
    else
        warn "anthropic package not installed - run: pip install anthropic"
    fi
else
    warn "ANTHROPIC_API_KEY not set - skipping Claude AI review"
    echo "  Set with: export ANTHROPIC_API_KEY='your-key'"
fi

# =============================================================================
# 11. Summary
# =============================================================================
echo ""
echo "=========================================="
echo "       SECURITY SCAN COMPLETE"
echo "=========================================="
echo ""

if [ ${ISSUES_FOUND} -gt 0 ]; then
    error "${ISSUES_FOUND} security issue(s) found!"
    echo ""
    echo "Review the issues above before merging."
    echo "If issues are false positives, document them in:"
    echo "  deploy-fly-io/docs/SECURITY_EXCEPTIONS.md"
    exit 1
fi

if [ ${WARNINGS_FOUND} -gt 0 ]; then
    warn "${WARNINGS_FOUND} warning(s) found - manual review recommended"
fi

log "No critical security issues detected"
exit 0
