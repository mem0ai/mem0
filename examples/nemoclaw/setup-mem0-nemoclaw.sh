#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# setup-mem0-nemoclaw.sh
#
# One-script setup for NemoClaw + Mem0 OpenClaw plugin.
# Supports Ubuntu servers (native) and macOS (via Docker container).
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/mem0ai/mem0/main/scripts/setup-mem0-nemoclaw.sh | bash
#   # or
#   chmod +x setup-mem0-nemoclaw.sh && ./setup-mem0-nemoclaw.sh
#
# Requirements:
#   - Ubuntu 22.04+ OR macOS with Docker Desktop OR Windows with WSL 2 + Docker Desktop
#   - 8 GB RAM minimum (16 GB recommended)
#   - 40 GB free disk (20 GB minimum)
#   - NVIDIA API key (from build.nvidia.com)
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

SANDBOX_NAME="${SANDBOX_NAME:-my-assistant}"
MEM0_USER_ID="${MEM0_USER_ID:-default}"
MIN_RAM_MB=6000
MIN_DISK_MB=15000
PLUGIN_PKG="@mem0/openclaw-mem0"
CONTAINER_NAME="nemoclaw-dev"

# ── Detect platform ─────────────────────────────────────────────────────────

OS_TYPE="$(uname -s)"
IS_MACOS=false
IS_LINUX=false
IS_WSL=false

case "$OS_TYPE" in
  Darwin) IS_MACOS=true ;;
  Linux)
    IS_LINUX=true
    # Detect WSL (Windows Subsystem for Linux)
    if grep -qi "microsoft\|wsl" /proc/version 2>/dev/null; then
      IS_WSL=true
    fi
    ;;
  MINGW*|MSYS*|CYGWIN*)
    error "This script cannot run in Git Bash, MSYS2, or Cygwin."
    echo ""
    echo "  NemoClaw requires a full Linux environment. On Windows, use WSL 2:"
    echo ""
    echo "  1. Open PowerShell as Administrator and run:"
    echo "     wsl --install -d Ubuntu-24.04"
    echo ""
    echo "  2. Restart your computer when prompted"
    echo ""
    echo "  3. Open 'Ubuntu' from the Start menu (this opens a WSL 2 shell)"
    echo ""
    echo "  4. Install Docker Desktop for Windows:"
    echo "     https://www.docker.com/products/docker-desktop/"
    echo "     Enable 'Use the WSL 2 based engine' in Docker Desktop settings"
    echo "     Enable 'Ubuntu-24.04' under Resources → WSL Integration"
    echo ""
    echo "  5. In the Ubuntu WSL 2 shell, re-run this script:"
    echo "     curl -fsSL https://raw.githubusercontent.com/mem0ai/mem0/main/scripts/setup-mem0-nemoclaw.sh | bash"
    echo ""
    die "Please use WSL 2 instead."
    ;;
  *)
    die "Unsupported OS: $OS_TYPE. This script supports Linux (Ubuntu), macOS, and Windows (WSL 2)."
    ;;
esac

# ── Helper functions ─────────────────────────────────────────────────────────

check_command() {
  command -v "$1" &>/dev/null
}

get_ram_mb() {
  if $IS_MACOS; then
    sysctl -n hw.memsize 2>/dev/null | awk '{printf "%.0f", $1/1024/1024}' || echo "0"
  else
    free -m 2>/dev/null | awk '/^Mem:/ {print $2}' || echo "0"
  fi
}

get_disk_mb() {
  if $IS_MACOS; then
    df -m / 2>/dev/null | awk 'NR==2 {print $4}' || echo "0"
  else
    df -m / 2>/dev/null | awk 'NR==2 {print $4}' || echo "0"
  fi
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

wait_for_sandbox() {
  local name="$1"
  local timeout=120
  local elapsed=0
  while (( elapsed < timeout )); do
    local phase
    phase=$($RUN_CMD openshell sandbox get "$name" 2>/dev/null | grep -i "phase" | awk '{print $NF}' || true)
    if [[ "$phase" == "Ready" ]]; then
      return 0
    fi
    sleep 5
    elapsed=$((elapsed + 5))
  done
  return 1
}

# ── macOS: run command inside the container ──────────────────────────────────
# On macOS, NemoClaw runs inside a Docker container. All nemoclaw/openshell
# commands must be exec'd into the container. On Linux, they run natively.

setup_run_cmd() {
  if $IS_MACOS; then
    RUN_CMD="docker exec $CONTAINER_NAME bash -c 'export NVM_DIR=/root/.nvm && source /root/.nvm/nvm.sh && "
    RUN_CMD_SUFFIX="'"
    RUN_CMD_IT="docker exec -it $CONTAINER_NAME bash -c 'export NVM_DIR=/root/.nvm && source /root/.nvm/nvm.sh && "
    RUN_CMD_IT_SUFFIX="'"
  else
    RUN_CMD=""
    RUN_CMD_SUFFIX=""
    RUN_CMD_IT=""
    RUN_CMD_IT_SUFFIX=""
  fi
}

# Wrapper to run a command natively (Linux) or in the container (macOS)
run_cmd() {
  if $IS_MACOS; then
    docker exec "$CONTAINER_NAME" bash -c "export NVM_DIR=/root/.nvm && source /root/.nvm/nvm.sh && $*"
  else
    eval "$@"
  fi
}

run_cmd_it() {
  if $IS_MACOS; then
    docker exec -it "$CONTAINER_NAME" bash -c "export NVM_DIR=/root/.nvm && source /root/.nvm/nvm.sh && $*"
  else
    eval "$@"
  fi
}

# ── Banner ───────────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║         Mem0 Plugin Setup for NemoClaw                       ║${NC}"
echo -e "${BOLD}${CYAN}║         Long-term memory for your OpenClaw agent             ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

if $IS_MACOS; then
  info "Platform: macOS (will use Docker container)"
elif $IS_WSL; then
  info "Platform: Windows (WSL 2)"
else
  info "Platform: Linux"
fi

# ═════════════════════════════════════════════════════════════════════════════
# PHASE 1: Prerequisites
# ═════════════════════════════════════════════════════════════════════════════

step "Phase 1: Checking prerequisites"

# ── OS check ─────────────────────────────────────────────────────────────────

if $IS_LINUX; then
  if [[ -f /etc/os-release ]]; then
    source /etc/os-release
    if [[ "$ID" != "ubuntu" ]]; then
      warn "Detected OS: $PRETTY_NAME (not Ubuntu). This script is tested on Ubuntu 22.04+."
      ask "Continue anyway? [y/N]: "
      read -r cont
      [[ "$cont" =~ ^[Yy]$ ]] || exit 0
    else
      success "OS: $PRETTY_NAME"
    fi
  else
    warn "Cannot detect Linux distribution. Proceeding anyway."
  fi
elif $IS_MACOS; then
  MACOS_VERSION=$(sw_vers -productVersion 2>/dev/null || echo "unknown")
  success "OS: macOS $MACOS_VERSION"
fi

# ── RAM check ────────────────────────────────────────────────────────────────

RAM_MB=$(get_ram_mb)
if (( RAM_MB < MIN_RAM_MB )); then
  error "Insufficient RAM: ${RAM_MB} MB available, ${MIN_RAM_MB} MB required."
  echo ""
  echo "  NemoClaw needs at least 8 GB RAM (16 GB recommended)."
  if $IS_WSL; then
    echo ""
    echo "  WSL 2 may have limited memory. Increase it:"
    echo "    1. Create/edit %USERPROFILE%\\.wslconfig in Windows"
    echo "    2. Add:"
    echo "       [wsl2]"
    echo "       memory=8GB"
    echo "    3. Restart WSL:  wsl --shutdown  (from PowerShell)"
  elif $IS_LINUX; then
    echo ""
    echo "  If running on AWS EC2:"
    echo "    1. Stop the instance"
    echo "    2. Change instance type to t3.large (8 GB) or t3.xlarge (16 GB)"
    echo "    3. Start the instance and re-run this script"
  fi
  echo ""
  die "Aborting due to insufficient RAM."
else
  success "RAM: ${RAM_MB} MB available"
fi

# ── Disk check ───────────────────────────────────────────────────────────────

DISK_MB=$(get_disk_mb)
if (( DISK_MB < MIN_DISK_MB )); then
  error "Insufficient disk space: ${DISK_MB} MB available, ${MIN_DISK_MB} MB required."
  echo ""
  echo "  NemoClaw needs at least 20 GB free disk (40 GB recommended)."
  echo ""
  echo "  Quick fix:"
  echo "    docker system prune -a -f    # Remove unused Docker data"
  if $IS_LINUX; then
    echo ""
    echo "  If running on AWS EC2, expand the EBS volume:"
    echo "    1. Go to AWS Console → EC2 → Volumes"
    echo "    2. Select the volume, Actions → Modify Volume → increase size"
    echo "    3. Then run:"
    echo "       sudo growpart /dev/xvda 1"
    echo "       sudo resize2fs /dev/xvda1"
  fi
  echo ""
  die "Aborting due to insufficient disk space."
else
  success "Disk: ${DISK_MB} MB available"
fi

# ── Docker check ─────────────────────────────────────────────────────────────

if ! check_command docker; then
  if $IS_MACOS; then
    error "Docker not found."
    echo ""
    echo "  Install Docker Desktop for macOS:"
    echo "    https://www.docker.com/products/docker-desktop/"
    echo ""
    echo "  After installing, start Docker Desktop and re-run this script."
    echo ""
    die "Docker Desktop is required on macOS."
  elif $IS_WSL; then
    error "Docker not found inside WSL."
    echo ""
    echo "  Docker Desktop must be installed on Windows with WSL 2 integration enabled:"
    echo ""
    echo "  1. Install Docker Desktop for Windows:"
    echo "     https://www.docker.com/products/docker-desktop/"
    echo ""
    echo "  2. Open Docker Desktop → Settings → General:"
    echo "     ✓ Enable 'Use the WSL 2 based engine'"
    echo ""
    echo "  3. Open Docker Desktop → Settings → Resources → WSL Integration:"
    echo "     ✓ Enable integration with your Ubuntu distribution"
    echo ""
    echo "  4. Click 'Apply & restart', then re-run this script in WSL."
    echo ""
    die "Docker Desktop WSL 2 integration is required."
  else
    info "Docker not found. Installing Docker..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq docker.io >/dev/null 2>&1
    sudo systemctl enable --now docker
    sudo usermod -aG docker "$USER"
    success "Docker installed"
  fi
fi

if $IS_LINUX; then
  # Ensure Docker daemon is running
  if ! sudo docker info &>/dev/null; then
    info "Starting Docker daemon..."
    sudo systemctl start docker
    sleep 2
  fi

  # Handle Docker group permissions
  if ! docker info &>/dev/null; then
    if id -nG "$USER" | grep -qw docker || grep -q "^docker:.*\b${USER}\b" /etc/group; then
      info "Activating docker group for current session..."
      exec sg docker -c "$0 $*"
    else
      info "Adding $USER to docker group..."
      sudo usermod -aG docker "$USER"
      info "Activating docker group for current session..."
      exec sg docker -c "$0 $*"
    fi
  fi
else
  # macOS: just verify Docker is responding
  if ! docker info &>/dev/null; then
    error "Docker is not running."
    echo ""
    echo "  Start Docker Desktop and wait for it to be ready, then re-run this script."
    echo ""
    die "Docker Desktop is not running."
  fi
fi

success "Docker: running ($(docker --version | awk '{print $3}' | tr -d ','))"

# ── Linux-only: cgroup v2 fix for Ubuntu 24.04 ──────────────────────────────

if $IS_LINUX && [[ "${VERSION_ID:-}" == "24.04" ]]; then
  DAEMON_JSON="/etc/docker/daemon.json"
  NEEDS_CGROUP_FIX=false

  if [[ ! -f "$DAEMON_JSON" ]]; then
    NEEDS_CGROUP_FIX=true
  elif ! grep -q '"default-cgroupns-mode"' "$DAEMON_JSON" 2>/dev/null; then
    NEEDS_CGROUP_FIX=true
  fi

  if $NEEDS_CGROUP_FIX; then
    warn "Ubuntu 24.04 detected — applying cgroup v2 fix for Docker."
    warn "This prevents 'K8s namespace not ready' errors during onboarding."
    sudo python3 -c "
import json, os
p = '$DAEMON_JSON'
c = json.load(open(p)) if os.path.exists(p) else {}
c['default-cgroupns-mode'] = 'host'
json.dump(c, open(p, 'w'), indent=2)
"
    sudo systemctl restart docker
    success "Docker cgroup v2 fix applied"
  else
    success "Docker cgroup v2: already configured"
  fi
fi

# ── Linux-only: Swap check ──────────────────────────────────────────────────

if $IS_LINUX; then
  SWAP_MB=$(free -m 2>/dev/null | awk '/^Swap:/ {print $2}' || echo "0")
  if (( RAM_MB < 12000 && SWAP_MB < 2000 )); then
    warn "Low RAM (${RAM_MB} MB) and low swap. Adding 4 GB swap to prevent OOM kills."
    if [[ ! -f /swapfile ]]; then
      sudo fallocate -l 4G /swapfile
      sudo chmod 600 /swapfile
      sudo mkswap /swapfile >/dev/null
      sudo swapon /swapfile
      success "4 GB swap enabled"
    else
      success "Swap file already exists"
    fi
  fi
fi

# ── macOS-only: Create Docker container ──────────────────────────────────────

if $IS_MACOS; then
  step "Phase 1b: Setting up NemoClaw Docker container"

  if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    success "Container '$CONTAINER_NAME' is already running"
  elif docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    info "Starting existing container '$CONTAINER_NAME'..."
    docker start "$CONTAINER_NAME"
    success "Container started"
  else
    info "Creating Ubuntu container '$CONTAINER_NAME' for NemoClaw..."
    echo -e "  ${DIM}This container runs NemoClaw with --network host and Docker socket access.${NC}"

    docker run -d \
      --name "$CONTAINER_NAME" \
      --privileged \
      --network host \
      -v /var/run/docker.sock:/var/run/docker.sock \
      ubuntu:24.04 sleep infinity

    success "Container '$CONTAINER_NAME' created"

    info "Installing dependencies inside container..."
    docker exec "$CONTAINER_NAME" bash -c "apt-get update -qq && apt-get install -y -qq curl git docker.io >/dev/null 2>&1"
    success "Dependencies installed"
  fi

  # Check if NemoClaw is installed in the container
  NEMO_IN_CONTAINER=$(docker exec "$CONTAINER_NAME" bash -c "export NVM_DIR=/root/.nvm && source /root/.nvm/nvm.sh 2>/dev/null && command -v nemoclaw" 2>/dev/null || true)
  if [[ -z "$NEMO_IN_CONTAINER" ]]; then
    info "Installing NemoClaw inside container (this takes a few minutes)..."
    # The NVIDIA installer triggers npm tar race conditions. Workaround: clone
    # and install with --maxsockets=1 to serialize downloads.
    docker exec -it "$CONTAINER_NAME" bash -c "
      export NVM_DIR=/root/.nvm &&
      if [ ! -s \"\$NVM_DIR/nvm.sh\" ]; then
        curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash &&
        source \"\$NVM_DIR/nvm.sh\" &&
        nvm install 22
      else
        source \"\$NVM_DIR/nvm.sh\"
      fi &&
      git clone --depth 1 https://github.com/NVIDIA/NemoClaw.git /root/.nemoclaw-src &&
      cd /root/.nemoclaw-src &&
      npm install --maxsockets=1 &&
      npm link
    "
    success "NemoClaw installed in container"
  else
    success "NemoClaw already installed in container"
  fi
fi

# ═════════════════════════════════════════════════════════════════════════════
# PHASE 2: Install NemoClaw (Linux-only, macOS handled above)
# ═════════════════════════════════════════════════════════════════════════════

if $IS_LINUX; then
  step "Phase 2: Installing NemoClaw"

  ensure_nvm
  ensure_path

  if check_command nemoclaw; then
    success "NemoClaw already installed: $(nemoclaw --version 2>/dev/null || echo 'found')"
  else
    info "Installing NemoClaw (this takes a few minutes)..."

    # Install Node.js via nvm if not available
    if ! check_command node; then
      info "Node.js not found — installing via nvm..."
      export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
      curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
      source "$NVM_DIR/nvm.sh"
      nvm install 22
      ensure_nvm
      ensure_path
    fi

    # The NVIDIA installer (curl | bash) triggers npm tar race conditions
    # causing ENOENT errors on deeply nested packages. Workaround: clone the
    # repo and install with --maxsockets=1 to serialize downloads.
    NEMOCLAW_DIR="$HOME/.nemoclaw-src"
    rm -rf "$NEMOCLAW_DIR"
    info "Cloning NemoClaw from GitHub..."
    git clone --depth 1 https://github.com/NVIDIA/NemoClaw.git "$NEMOCLAW_DIR"
    cd "$NEMOCLAW_DIR"
    info "Installing dependencies (serialized to avoid tar race)..."
    npm install --maxsockets=1
    npm link
    cd - >/dev/null

    ensure_nvm
    ensure_path
    source "$HOME/.bashrc" 2>/dev/null || true
    hash -r 2>/dev/null || true

    if ! check_command nemoclaw; then
      # npm link may place the binary outside the current PATH; find and add it
      NEMOCLAW_BIN=$(find "$HOME/.nvm" -name nemoclaw \( -type f -o -type l \) -path "*/bin/*" 2>/dev/null | head -1)
      if [[ -n "$NEMOCLAW_BIN" ]]; then
        export PATH="$(dirname "$NEMOCLAW_BIN"):$PATH"
      fi
    fi

    if ! check_command nemoclaw; then
      die "NemoClaw installation failed. Try: source ~/.bashrc && nemoclaw --help"
    fi

    success "NemoClaw installed"
  fi

  ensure_path
  if ! check_command openshell; then
    warn "openshell not on PATH yet — it will be installed during onboarding."
  fi
fi

# ═════════════════════════════════════════════════════════════════════════════
# PHASE 3: NemoClaw Onboarding
# ═════════════════════════════════════════════════════════════════════════════

step "Phase 3: NemoClaw Onboarding"

# Check if a sandbox already exists
EXISTING_SANDBOX=""
if $IS_MACOS; then
  EXISTING_SANDBOX=$(run_cmd "openshell sandbox list 2>/dev/null" | awk 'NR>1 && $1!="" {print $1; exit}' || true)
else
  ensure_path
  if check_command openshell; then
    EXISTING_SANDBOX=$(openshell sandbox list 2>/dev/null | awk 'NR>1 && $1!="" {print $1; exit}' || true)
  fi
fi

if [[ -n "$EXISTING_SANDBOX" ]]; then
  success "Sandbox already exists: $EXISTING_SANDBOX"
  SANDBOX_NAME="$EXISTING_SANDBOX"
  ask "Use existing sandbox '$SANDBOX_NAME'? [Y/n]: "
  read -r use_existing
  if [[ "$use_existing" =~ ^[Nn]$ ]]; then
    ask "Enter sandbox name [my-assistant]: "
    read -r custom_name
    SANDBOX_NAME="${custom_name:-my-assistant}"
    info "Running NemoClaw onboarding..."
    echo -e "  ${DIM}You'll need your NVIDIA API key (nvapi-...) from build.nvidia.com${NC}"
    echo ""
    run_cmd_it "nemoclaw onboard"
    if $IS_LINUX; then ensure_path; fi
  fi
else
  info "No existing sandbox found. Running NemoClaw onboarding..."
  echo ""
  echo -e "  ${DIM}The onboarding wizard will guide you through 7 steps:${NC}"
  echo -e "  ${DIM}  1. Preflight checks (automatic)${NC}"
  echo -e "  ${DIM}  2. Start gateway (automatic, takes 1-2 min)${NC}"
  echo -e "  ${DIM}  3. Sandbox name — enter a name (e.g. my-assistant)${NC}"
  echo -e "  ${DIM}  4. NVIDIA API key — paste your nvapi-... key${NC}"
  echo -e "  ${DIM}  5. Inference provider (automatic)${NC}"
  echo -e "  ${DIM}  6. OpenClaw setup (automatic)${NC}"
  echo -e "  ${DIM}  7. Policy presets — type Y to apply pypi and npm${NC}"
  echo ""
  ask "Press Enter to start onboarding..."
  read -r

  run_cmd_it "nemoclaw onboard"

  if $IS_LINUX; then
    ensure_nvm
    ensure_path
  fi

  # Detect sandbox name
  SANDBOX_NAME=$(run_cmd "openshell sandbox list 2>/dev/null" | awk 'NR>1 && $1!="" {print $1; exit}' || echo "$SANDBOX_NAME")
fi

# Verify sandbox exists
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

success "Sandbox '$SANDBOX_NAME' is ready"

# ═════════════════════════════════════════════════════════════════════════════
# PHASE 4: Install Mem0 Plugin
# ═════════════════════════════════════════════════════════════════════════════

step "Phase 4: Installing Mem0 plugin ($PLUGIN_PKG)"

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

# Check if plugin is already installed by trying to download a known file from the sandbox.
# We avoid sandbox_exec for the check because piped stdin to openshell sandbox connect
# produces shell prompt noise that causes false positives with grep.
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
# PHASE 5: Update Network Policy
# ═════════════════════════════════════════════════════════════════════════════

step "Phase 5: Updating network policy to allow api.mem0.ai and telemetry"

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

# Create custom policy with mem0_api + telemetry — use node for reliable cross-platform YAML editing
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
# PHASE 6: Configure Plugin
# ═════════════════════════════════════════════════════════════════════════════

step "Phase 6: Configuring Mem0 plugin"

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
# PHASE 7: Verify & Test
# ═════════════════════════════════════════════════════════════════════════════

step "Phase 7: Verification"

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
