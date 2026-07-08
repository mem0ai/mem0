#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# install-mem0-plugin.sh
#
# Installs and configures the @mem0/openclaw-mem0 plugin for an existing
# NemoClaw sandbox. Assumes NemoClaw is already installed and onboarded.
#
# Usage:
#   chmod +x install-mem0-plugin.sh && ./install-mem0-plugin.sh
#
# Requirements:
#   - NemoClaw installed and onboarded (sandbox in Ready state)
#   - Mem0 API key (from app.mem0.ai)
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── Colors and formatting ────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; }
step()    { echo -e "\n${BOLD}${CYAN}── $* ──${NC}\n"; }
ask()     { echo -en "${BOLD}$*${NC}"; }

die() {
  error "$*"
  exit 1
}

# ── Defaults ─────────────────────────────────────────────────────────────────

MEM0_USER_ID="${MEM0_USER_ID:-default}"
PLUGIN_PKG="@mem0/openclaw-mem0"
CONTAINER_NAME="nemoclaw-dev"

# ── Detect platform ──────────────────────────────────────────────────────────

OS_TYPE="$(uname -s)"
IS_MACOS=false
IS_LINUX=false

case "$OS_TYPE" in
  Darwin) IS_MACOS=true ;;
  Linux)  IS_LINUX=true ;;
  *)      die "Unsupported OS: $OS_TYPE" ;;
esac

# ── Helper functions ─────────────────────────────────────────────────────────

check_command() {
  command -v "$1" &>/dev/null
}

ensure_nvm() {
  export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
  if [[ -s "$NVM_DIR/nvm.sh" ]]; then
    source "$NVM_DIR/nvm.sh"
  fi
}

ensure_path() {
  for p in "$HOME/.local/bin" "$HOME/.nvm/versions/node/"*/bin; do
    if [[ -d "$p" ]] && [[ ":$PATH:" != *":$p:"* ]]; then
      export PATH="$p:$PATH"
    fi
  done
}

# Wrapper to run a command natively (Linux) or in the container (macOS)
run_cmd() {
  if $IS_MACOS; then
    docker exec "$CONTAINER_NAME" bash -c "export NVM_DIR=/root/.nvm && source /root/.nvm/nvm.sh && $*"
  else
    eval "$@"
  fi
}

# ── Banner ───────────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║         Mem0 Plugin Installer for NemoClaw                   ║${NC}"
echo -e "${BOLD}${CYAN}║         Long-term memory for your OpenClaw agent             ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

if $IS_MACOS; then
  info "Platform: macOS (using Docker container '$CONTAINER_NAME')"
else
  info "Platform: Linux"
fi

# ═════════════════════════════════════════════════════════════════════════════
# PRE-CHECK: Verify NemoClaw is installed and sandbox is ready
# ═════════════════════════════════════════════════════════════════════════════

step "Pre-check: Verifying NemoClaw setup"

if $IS_LINUX; then
  ensure_nvm
  ensure_path
fi

# Verify nemoclaw/openshell are available
if $IS_MACOS; then
  if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    die "Docker container '$CONTAINER_NAME' is not running. Start it with: docker start $CONTAINER_NAME"
  fi
  if ! run_cmd "command -v nemoclaw" &>/dev/null; then
    die "NemoClaw is not installed in container '$CONTAINER_NAME'. Run the full setup script first."
  fi
else
  if ! check_command openshell; then
    die "openshell not found. Is NemoClaw installed and onboarded? Try: source ~/.bashrc"
  fi
fi

# Detect sandbox
SANDBOX_NAME=$(run_cmd "openshell sandbox list 2>/dev/null" | awk 'NR>1 && $1!="" {print $1; exit}' || true)

if [[ -z "$SANDBOX_NAME" ]]; then
  die "No sandbox found. Run 'nemoclaw onboard' first."
fi

# Verify sandbox is ready
SANDBOX_PHASE=$(run_cmd "openshell sandbox get '$SANDBOX_NAME' 2>/dev/null" | grep -i "phase" | awk '{print $NF}' || true)
if [[ "$SANDBOX_PHASE" != "Ready" ]]; then
  warn "Sandbox '$SANDBOX_NAME' is not in Ready state (current: ${SANDBOX_PHASE:-unknown})."
  warn "Waiting up to 2 minutes..."
  WAIT_OK=false
  for i in $(seq 1 24); do
    SANDBOX_PHASE=$(run_cmd "openshell sandbox get '$SANDBOX_NAME' 2>/dev/null" | grep -i "phase" | awk '{print $NF}' || true)
    if [[ "$SANDBOX_PHASE" == "Ready" ]]; then
      WAIT_OK=true
      break
    fi
    sleep 5
  done
  if ! $WAIT_OK; then
    die "Sandbox '$SANDBOX_NAME' did not become Ready. Run: openshell sandbox list"
  fi
fi

success "NemoClaw installed"
success "Sandbox '$SANDBOX_NAME' is ready"

# ═════════════════════════════════════════════════════════════════════════════
# STEP 1: Install Mem0 Plugin
# ═════════════════════════════════════════════════════════════════════════════

step "Step 1: Installing Mem0 plugin ($PLUGIN_PKG)"

# Helper: run a command inside the sandbox non-interactively via piped stdin
sandbox_exec() {
  local cmd="$1"
  if $IS_MACOS; then
    printf '%s\nexit\n' "$cmd" | docker exec -i "$CONTAINER_NAME" bash -c \
      "export NVM_DIR=/root/.nvm && source /root/.nvm/nvm.sh && openshell sandbox connect '$SANDBOX_NAME'" 2>&1
  else
    printf '%s\nexit\n' "$cmd" | openshell sandbox connect "$SANDBOX_NAME" 2>&1
  fi
}

# Check if plugin is already installed
PLUGIN_EXISTS=false
if run_cmd "openshell sandbox download '$SANDBOX_NAME' /sandbox/.openclaw/extensions/openclaw-mem0/package.json /tmp/_mem0_plugin_check.json" &>/dev/null; then
  if [[ -f /tmp/_mem0_plugin_check.json ]] || run_cmd "test -f /tmp/_mem0_plugin_check.json" &>/dev/null; then
    PLUGIN_EXISTS=true
  fi
fi
rm -f /tmp/_mem0_plugin_check.json 2>/dev/null || true
run_cmd "rm -f /tmp/_mem0_plugin_check.json" 2>/dev/null || true

if $PLUGIN_EXISTS; then
  success "Mem0 plugin already installed in sandbox"
else
  info "Downloading $PLUGIN_PKG..."

  # Download and build outside the sandbox (on host or in container)
  run_cmd "cd /tmp && rm -rf openclaw-mem0-full mem0-openclaw-mem0-*.tgz openclaw-mem0-full.tgz"

  if ! run_cmd "cd /tmp && npm pack '$PLUGIN_PKG' 2>/dev/null"; then
    die "Failed to download $PLUGIN_PKG from npm. Check your internet connection."
  fi

  success "Downloaded plugin"

  info "Installing plugin dependencies..."
  run_cmd "mkdir -p /tmp/openclaw-mem0-full && cd /tmp/openclaw-mem0-full && tar xzf /tmp/mem0-openclaw-mem0-*.tgz --strip-components=1 && npm install --omit=dev 2>&1 | tail -3"

  success "Dependencies installed"

  info "Uploading plugin to sandbox..."
  run_cmd "cd /tmp && tar czf openclaw-mem0-full.tgz -C openclaw-mem0-full ."

  if ! run_cmd "openshell sandbox upload '$SANDBOX_NAME' /tmp/openclaw-mem0-full.tgz /sandbox/openclaw-mem0-full.tgz 2>&1"; then
    die "Failed to upload plugin to sandbox. Check: openshell sandbox list"
  fi

  success "Plugin uploaded"

  info "Extracting plugin inside sandbox..."
  sandbox_exec "mkdir -p ~/.openclaw/extensions/openclaw-mem0 && tar xzf /sandbox/openclaw-mem0-full.tgz/openclaw-mem0-full.tgz -C ~/.openclaw/extensions/openclaw-mem0 2>/dev/null || tar xzf /sandbox/openclaw-mem0-full.tgz -C ~/.openclaw/extensions/openclaw-mem0 2>/dev/null && echo EXTRACT_OK" >/dev/null 2>&1 || true

  # Verify
  VERIFY_OK=false
  if run_cmd "openshell sandbox download '$SANDBOX_NAME' /sandbox/.openclaw/extensions/openclaw-mem0/package.json /tmp/_mem0_verify.json" &>/dev/null; then
    VERIFY_OK=true
  fi
  rm -f /tmp/_mem0_verify.json 2>/dev/null || true
  run_cmd "rm -f /tmp/_mem0_verify.json" 2>/dev/null || true
  if $VERIFY_OK; then
    success "Plugin extracted inside sandbox"
  else
    warn "Could not verify plugin extraction. You may need to extract manually."
    if $IS_MACOS; then
      echo "  docker exec -it $CONTAINER_NAME bash"
      echo "  export NVM_DIR=/root/.nvm && source /root/.nvm/nvm.sh"
    fi
    echo "  nemoclaw $SANDBOX_NAME connect"
    echo "  mkdir -p ~/.openclaw/extensions/openclaw-mem0"
    echo "  tar xzf /sandbox/openclaw-mem0-full.tgz/openclaw-mem0-full.tgz -C ~/.openclaw/extensions/openclaw-mem0"
  fi

  # Clean up
  run_cmd "rm -rf /tmp/openclaw-mem0-full /tmp/mem0-openclaw-mem0-*.tgz /tmp/openclaw-mem0-full.tgz" 2>/dev/null || true
fi

# ═════════════════════════════════════════════════════════════════════════════
# STEP 2: Update Network Policy
# ═════════════════════════════════════════════════════════════════════════════

step "Step 2: Updating network policy to allow api.mem0.ai and telemetry"

# Find baseline policy
BASELINE_POLICY=$(run_cmd "find / -path '*/nemoclaw-blueprint/policies/openclaw-sandbox.yaml' 2>/dev/null | head -1" || true)

if [[ -z "$BASELINE_POLICY" ]]; then
  die "Cannot find NemoClaw baseline policy file. Is NemoClaw installed?"
fi

info "Baseline policy: $BASELINE_POLICY"

# Check if mem0_api already exists
HAS_MEM0=$(run_cmd "grep -c mem0_api '$BASELINE_POLICY' 2>/dev/null" || echo "0")

if [[ "$HAS_MEM0" != "0" ]]; then
  success "mem0_api already in baseline policy"
else
  info "Adding api.mem0.ai to network policy..."
fi

# Create custom policy with mem0_api + telemetry
run_cmd "node -e \"
const fs = require('fs');
let c = fs.readFileSync('$BASELINE_POLICY', 'utf8');
const mem0Block = '\\n  mem0_api:\\n    name: mem0_api\\n    endpoints:\\n      - host: api.mem0.ai\\n        port: 443\\n        access: full\\n    binaries:\\n      - { path: /usr/local/bin/node }\\n      - { path: /usr/local/bin/openclaw }\\n';
const telemetryBlock = '\\n  mem0_telemetry:\\n    name: mem0_telemetry\\n    endpoints:\\n      - host: us.i.posthog.com\\n        port: 443\\n        access: full\\n    binaries:\\n      - { path: /usr/local/bin/node }\\n      - { path: /usr/local/bin/openclaw }\\n';
if (!c.includes('mem0_api')) {
  if (c.includes('# ── Messaging')) {
    c = c.replace('  # ── Messaging', mem0Block + '\\n  # ── Messaging');
  } else {
    c += mem0Block;
  }
}
if (!c.includes('mem0_telemetry')) {
  if (c.includes('mem0_api:')) {
    c = c.replace('  mem0_api:', telemetryBlock + '\\n  mem0_api:');
  } else {
    c += telemetryBlock;
  }
}
fs.writeFileSync('/tmp/nemoclaw-mem0-policy.yaml', c);
console.log('ok');
\""

success "Custom policy file created"

# Apply the policy
info "Applying network policy..."
if ! run_cmd "openshell policy set '$SANDBOX_NAME' --policy /tmp/nemoclaw-mem0-policy.yaml --wait 2>&1"; then
  error "Failed to apply network policy."
  echo ""
  echo "  If you see 'sandbox not found', re-run: nemoclaw onboard"
  echo "  Then re-run this script."
  echo ""
  die "Network policy update failed."
fi

success "Network policy applied — api.mem0.ai and telemetry allowed"

# ═════════════════════════════════════════════════════════════════════════════
# STEP 3: Configure Plugin
# ═════════════════════════════════════════════════════════════════════════════

step "Step 3: Configuring Mem0 plugin"

echo ""
echo -e "  ${DIM}Get your Mem0 API key from: https://app.mem0.ai${NC}"
echo -e "  ${DIM}The key starts with 'm0-'${NC}"
echo ""
ask "Enter your Mem0 API key: "
read -r MEM0_API_KEY

if [[ -z "$MEM0_API_KEY" ]]; then
  die "Mem0 API key is required."
fi

if [[ ! "$MEM0_API_KEY" =~ ^m0- ]]; then
  warn "Key doesn't start with 'm0-'. Make sure this is correct."
fi

echo ""
echo -e "  ${DIM}The user ID scopes all memories. Pick any unique identifier.${NC}"
echo -e "  ${DIM}Examples: alice, user_123, your-email@example.com${NC}"
echo ""
ask "Enter user ID [$MEM0_USER_ID]: "
read -r custom_user_id
MEM0_USER_ID="${custom_user_id:-$MEM0_USER_ID}"

info "Configuring plugin inside sandbox..."

CONFIG_SCRIPT="openclaw config set plugins.slots.memory openclaw-mem0 2>&1 | tail -1 && \
openclaw config set plugins.entries.openclaw-mem0.enabled true 2>&1 | tail -1 && \
openclaw config set plugins.entries.openclaw-mem0.config.apiKey '$MEM0_API_KEY' 2>&1 | tail -1 && \
openclaw config set plugins.entries.openclaw-mem0.config.userId '$MEM0_USER_ID' 2>&1 | tail -1 && \
echo SETUP_DONE"

CONFIG_OUTPUT=$(sandbox_exec "$CONFIG_SCRIPT" || true)

if echo "$CONFIG_OUTPUT" | grep -q "SETUP_DONE"; then
  success "Plugin configured (mode: platform, user: $MEM0_USER_ID)"
else
  warn "Could not verify config. You may need to configure manually:"
  echo ""
  if $IS_MACOS; then
    echo "  docker exec -it $CONTAINER_NAME bash"
    echo "  export NVM_DIR=/root/.nvm && source /root/.nvm/nvm.sh"
  fi
  echo "  nemoclaw $SANDBOX_NAME connect"
  echo "  openclaw config set plugins.slots.memory openclaw-mem0"
  echo "  openclaw config set plugins.entries.openclaw-mem0.enabled true"
  echo "  openclaw config set plugins.entries.openclaw-mem0.config.apiKey \"$MEM0_API_KEY\""
  echo "  openclaw config set plugins.entries.openclaw-mem0.config.userId \"$MEM0_USER_ID\""
  echo ""
fi

# ═════════════════════════════════════════════════════════════════════════════
# Done
# ═════════════════════════════════════════════════════════════════════════════

step "Verification"

echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${GREEN}║                    Setup Complete!                           ║${NC}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}Sandbox:${NC}   $SANDBOX_NAME"
echo -e "  ${BOLD}Plugin:${NC}    @mem0/openclaw-mem0 (platform mode)"
echo -e "  ${BOLD}User ID:${NC}   $MEM0_USER_ID"
if $IS_MACOS; then
  echo -e "  ${BOLD}Container:${NC} $CONTAINER_NAME"
fi
echo ""
echo -e "  ${BOLD}${CYAN}Next steps:${NC}"
echo ""

if $IS_MACOS; then
  echo -e "  1. Open a shell in the container:"
  echo ""
  echo -e "     ${DIM}docker exec -it $CONTAINER_NAME bash${NC}"
  echo -e "     ${DIM}export NVM_DIR=/root/.nvm && source /root/.nvm/nvm.sh${NC}"
  echo ""
  echo -e "  2. Connect to the sandbox and start the gateway:"
  echo ""
  echo -e "     ${DIM}nemoclaw $SANDBOX_NAME connect${NC}"
  echo -e "     ${DIM}nemoclaw-start${NC}"
else
  echo -e "  1. Connect to the sandbox and start the gateway:"
  echo ""
  echo -e "     ${DIM}source ~/.bashrc${NC}"
  echo -e "     ${DIM}nemoclaw $SANDBOX_NAME connect${NC}"
  echo -e "     ${DIM}nemoclaw-start${NC}"
fi
echo ""
echo -e "  Then verify the plugin loaded (look for 'openclaw-mem0: registered'):"
echo ""
echo -e "     ${DIM}openclaw plugins list${NC}"
echo ""
echo -e "  Test auto-capture (storing memories):"
echo ""
echo -e "     ${DIM}openclaw agent --agent main --local -m \"My name is Alice\" --session-id test1${NC}"
echo ""
echo -e "  Test auto-recall (new session, memories should appear):"
echo ""
echo -e "     ${DIM}openclaw agent --agent main --local -m \"What do you know about me?\" --session-id test2${NC}"
echo ""
echo -e "  Or use the interactive TUI:"
echo ""
echo -e "     ${DIM}openclaw tui${NC}"
echo ""
echo -e "  ${YELLOW}Note:${NC} You may see 'Telemetry event capture failed' errors."
echo -e "  These are harmless and do not affect memory functionality."
echo ""
echo -e "  ${BOLD}Documentation:${NC} https://docs.mem0.ai"
echo -e "  ${BOLD}Plugin source:${NC} https://www.npmjs.com/package/@mem0/openclaw-mem0"
echo ""
