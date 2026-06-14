#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# Test script for OpenClaw + Mem0 Docker setup
# Validates everything works without needing real API keys
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PASS=0
FAIL=0
TESTS=()

pass() { PASS=$((PASS + 1)); TESTS+=("✔ $1"); echo "  ✔ $1"; }
fail() { FAIL=$((FAIL + 1)); TESTS+=("✖ $1: $2"); echo "  ✖ $1: $2"; }

echo ""
echo "═══════════════════════════════════════════════════"
echo "  OpenClaw + Mem0 Docker Setup — Test Suite"
echo "═══════════════════════════════════════════════════"

# ── Prerequisites ────────────────────────────────────────────────────────────

echo ""
echo "▸ Prerequisites"

if command -v docker &>/dev/null; then
  pass "Docker installed"
else
  fail "Docker installed" "docker not found"
fi

if docker compose version &>/dev/null; then
  pass "Docker Compose v2 available"
else
  fail "Docker Compose v2 available" "docker compose not found"
fi

if docker info &>/dev/null 2>&1; then
  pass "Docker daemon running"
else
  fail "Docker daemon running" "daemon not responding"
fi

# ── File structure ───────────────────────────────────────────────────────────

echo ""
echo "▸ File structure"

EXPECTED_FILES=(
  "setup.sh"
  "docker-compose.yml"
  "docker-compose.oss.yml"
  ".env.example"
  "config/openclaw.platform.json"
  "config/openclaw.oss.json"
  "skills/mem0-onboarding/SKILL.md"
  "README.md"
)

for f in "${EXPECTED_FILES[@]}"; do
  if [ -f "$SCRIPT_DIR/$f" ]; then
    pass "File exists: $f"
  else
    fail "File exists: $f" "missing"
  fi
done

if [ -x "$SCRIPT_DIR/setup.sh" ]; then
  pass "setup.sh is executable"
else
  fail "setup.sh is executable" "not executable"
fi

# ── Bash syntax ──────────────────────────────────────────────────────────────

echo ""
echo "▸ Script syntax"

if bash -n "$SCRIPT_DIR/setup.sh" 2>&1; then
  pass "setup.sh syntax valid"
else
  fail "setup.sh syntax valid" "syntax errors"
fi

# ── JSON validity ────────────────────────────────────────────────────────────

echo ""
echo "▸ JSON configs"

for json_file in config/openclaw.platform.json config/openclaw.oss.json; do
  if python3 -c "import json; json.load(open('$SCRIPT_DIR/$json_file'))" 2>/dev/null; then
    pass "$json_file is valid JSON"
  else
    fail "$json_file is valid JSON" "parse error"
  fi
done

# Check platform config has expected fields
if python3 -c "
import json, sys
c = json.load(open('$SCRIPT_DIR/config/openclaw.platform.json'))
p = c['plugins']['openclaw-mem0']
assert p['mode'] == 'platform', 'wrong mode'
assert p['apiKey'] == '\${MEM0_API_KEY}', 'apiKey not using env var'
assert p['userId'] == '__MEM0_USER_ID__', 'userId placeholder missing'
assert p['autoCapture'] is True
assert p['autoRecall'] is True
" 2>/dev/null; then
  pass "Platform config has correct structure"
else
  fail "Platform config has correct structure" "missing or wrong fields"
fi

# Check OSS config has Qdrant vector store
if python3 -c "
import json
c = json.load(open('$SCRIPT_DIR/config/openclaw.oss.json'))
p = c['plugins']['openclaw-mem0']
assert p['mode'] == 'open-source', 'wrong mode'
vs = p['oss']['vectorStore']
assert vs['provider'] == 'qdrant'
assert vs['config']['host'] == 'qdrant'
assert vs['config']['port'] == 6333
" 2>/dev/null; then
  pass "OSS config has Qdrant vector store"
else
  fail "OSS config has Qdrant vector store" "missing or wrong fields"
fi

# ── Docker Compose validation ────────────────────────────────────────────────

echo ""
echo "▸ Docker Compose validation"

cd "$SCRIPT_DIR"

# Create a temporary .env so compose can resolve variables
TEMP_ENV=false
if [ ! -f .env ]; then
  cat > .env <<'EOF'
MEM0_API_KEY=test-key-for-validation
OPENAI_API_KEY=test-key-for-validation
MEM0_USER_ID=testuser
OPENCLAW_PORT=18789
OPENCLAW_CONFIG_DIR=/tmp/openclaw-test
TZ=UTC
EOF
  TEMP_ENV=true
fi

if docker compose config --quiet 2>/dev/null; then
  pass "docker-compose.yml is valid"
else
  fail "docker-compose.yml is valid" "$(docker compose config 2>&1 | tail -1)"
fi

if docker compose -f docker-compose.yml -f docker-compose.oss.yml config --quiet 2>/dev/null; then
  pass "docker-compose.oss.yml override is valid"
else
  fail "docker-compose.oss.yml override is valid" "$(docker compose -f docker-compose.yml -f docker-compose.oss.yml config 2>&1 | tail -1)"
fi

# Verify services are correctly defined
PLATFORM_SERVICES=$(docker compose config --services 2>/dev/null)
if echo "$PLATFORM_SERVICES" | grep -q "openclaw"; then
  pass "Platform mode defines 'openclaw' service"
else
  fail "Platform mode defines 'openclaw' service" "service not found"
fi

OSS_SERVICES=$(docker compose -f docker-compose.yml -f docker-compose.oss.yml config --services 2>/dev/null)
if echo "$OSS_SERVICES" | grep -q "qdrant"; then
  pass "OSS mode adds 'qdrant' service"
else
  fail "OSS mode adds 'qdrant' service" "service not found"
fi

# Verify port binding is localhost-only
PORT_CONFIG=$(docker compose config 2>/dev/null | grep -A5 "published" | head -10)
if docker compose config 2>/dev/null | grep -q "127.0.0.1"; then
  pass "Port is bound to 127.0.0.1 (localhost only)"
else
  fail "Port is bound to 127.0.0.1 (localhost only)" "binding not found"
fi

# Verify healthcheck is defined
if docker compose config 2>/dev/null | grep -q "healthz"; then
  pass "Healthcheck is configured"
else
  fail "Healthcheck is configured" "healthcheck not found"
fi

# ── Docker image pull test ───────────────────────────────────────────────────

echo ""
echo "▸ Docker image availability"

# Just check if the image reference is parseable (don't actually pull — too slow for a test)
IMAGE=$(docker compose config 2>/dev/null | grep "image:" | head -1 | awk '{print $2}')
if [ -n "$IMAGE" ]; then
  pass "OpenClaw image reference: $IMAGE"
else
  fail "OpenClaw image reference" "could not extract image name"
fi

QDRANT_IMAGE=$(docker compose -f docker-compose.yml -f docker-compose.oss.yml config 2>/dev/null | grep "image:" | grep qdrant | awk '{print $2}')
if [ -n "$QDRANT_IMAGE" ]; then
  pass "Qdrant image reference: $QDRANT_IMAGE"
else
  fail "Qdrant image reference" "could not extract image name"
fi

# ── setup.sh simulation ─────────────────────────────────────────────────────

echo ""
echo "▸ setup.sh config generation simulation"

# Test the sed substitution that setup.sh does
TEST_CONFIG_DIR=$(mktemp -d)
sed "s/__MEM0_USER_ID__/testuser/g" "$SCRIPT_DIR/config/openclaw.platform.json" > "$TEST_CONFIG_DIR/openclaw.json"

if python3 -c "
import json
c = json.load(open('$TEST_CONFIG_DIR/openclaw.json'))
p = c['plugins']['openclaw-mem0']
assert p['userId'] == 'testuser', f'expected testuser, got {p[\"userId\"]}'
assert p['apiKey'] == '\${MEM0_API_KEY}', 'apiKey should remain as env var template'
" 2>/dev/null; then
  pass "sed substitution works correctly (userId baked, apiKey templated)"
else
  fail "sed substitution" "userId not replaced or apiKey was wrongly replaced"
fi

rm -rf "$TEST_CONFIG_DIR"

# OSS config substitution
TEST_CONFIG_DIR=$(mktemp -d)
sed "s/__MEM0_USER_ID__/testuser/g" "$SCRIPT_DIR/config/openclaw.oss.json" > "$TEST_CONFIG_DIR/openclaw.json"

if python3 -c "
import json
c = json.load(open('$TEST_CONFIG_DIR/openclaw.json'))
p = c['plugins']['openclaw-mem0']
assert p['userId'] == 'testuser'
assert p['oss']['vectorStore']['config']['host'] == 'qdrant'
" 2>/dev/null; then
  pass "OSS config sed substitution works correctly"
else
  fail "OSS config sed substitution" "fields incorrect after substitution"
fi

rm -rf "$TEST_CONFIG_DIR"

# ── Cleanup ──────────────────────────────────────────────────────────────────

if [ "$TEMP_ENV" = true ]; then
  rm -f "$SCRIPT_DIR/.env"
fi

# ── Summary ──────────────────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════"
TOTAL=$((PASS + FAIL))
if [ $FAIL -eq 0 ]; then
  echo "  All $TOTAL tests passed ✔"
else
  echo "  $PASS/$TOTAL passed, $FAIL failed"
  echo ""
  for t in "${TESTS[@]}"; do
    if [[ "$t" == "✖"* ]]; then
      echo "  $t"
    fi
  done
fi
echo "═══════════════════════════════════════════════════"
echo ""

exit $FAIL
