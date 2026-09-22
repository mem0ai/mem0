# ============================================================================
# Agentic Memory Skills — OpenClaw Plugin Installer
# ============================================================================
#
# Usage:
#   make install                          # Interactive — prompts for API key
#   make install MEM0_API_KEY=m0-xxx      # Non-interactive
#   make uninstall                        # Revert to stock plugin
#   make restart                          # Rebuild + restart gateway
#   make status                           # Check everything is working
#   make logs                             # Tail gateway logs filtered to mem0
#   make clean                            # Full teardown
#
# ============================================================================

SHELL := /bin/bash
.PHONY: install uninstall restart status logs clean build check-deps configure help

# Defaults
MEM0_API_KEY ?=
MEM0_USER_ID ?= $(shell whoami)
OPENCLAW_CONFIG := $(HOME)/.openclaw/openclaw.json
PLUGIN_DIR := $(shell pwd)

help: ## Show this help
	@echo ""
	@echo "  Agentic Memory Skills — OpenClaw Plugin"
	@echo "  ========================================"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ============================================================================
# Dependency checks
# ============================================================================

check-deps:
	@echo "Checking dependencies..."
	@command -v node >/dev/null 2>&1 || { echo "Error: Node.js is required. Install from https://nodejs.org"; exit 1; }
	@NODE_MAJOR=$$(node -v | sed 's/v//' | cut -d. -f1); \
		if [ "$$NODE_MAJOR" -lt 18 ]; then echo "Error: Node.js >= 18 required (found $$(node -v))"; exit 1; fi
	@command -v npm >/dev/null 2>&1 || { echo "Error: npm is required"; exit 1; }
	@if ! command -v openclaw >/dev/null 2>&1; then \
		echo "OpenClaw not found. Installing..."; \
		npm install -g openclaw || { echo "Error: Failed to install OpenClaw. Try: sudo npm install -g openclaw"; exit 1; }; \
		echo "OpenClaw installed: $$(openclaw --version)"; \
	else \
		echo "OpenClaw: $$(openclaw --version 2>/dev/null || echo 'installed')"; \
	fi
	@echo "Node.js: $$(node -v)"
	@echo "All dependencies OK."

# ============================================================================
# Build
# ============================================================================

build: ## Build the plugin from source
	@echo "Installing npm dependencies..."
	@npm install --silent 2>/dev/null
	@echo "Building plugin..."
	@npm run build --silent 2>/dev/null
	@echo "Build OK: $$(ls -lh dist/index.js | awk '{print $$5}') ESM bundle"

# ============================================================================
# Install
# ============================================================================

install: check-deps build ## Full install — build, link, configure, restart
	@# Remove existing plugin (suppress errors if not installed)
	@echo "Removing existing openclaw-mem0 plugin (if any)..."
	@echo "y" | openclaw plugins uninstall openclaw-mem0 >/dev/null 2>&1 || true
	@# Link local build
	@echo "Linking local plugin build..."
	@openclaw plugins install "$(PLUGIN_DIR)" --link 2>&1 | grep -v "plugins.allow"
	@# Configure AFTER link (link may overwrite config)
	@$(MAKE) --no-print-directory configure
	@# Restart gateway
	@echo "Restarting gateway..."
	@kill -9 $$(lsof -ti:18789) 2>/dev/null || true
	@sleep 2
	@openclaw gateway >/dev/null 2>&1 &
	@sleep 4
	@echo ""
	@echo "============================================"
	@echo "  Installation complete!"
	@echo "============================================"
	@echo ""
	@echo "  Plugin: openclaw-mem0 (skills mode)"
	@echo "  User:   $(MEM0_USER_ID)"
	@echo "  Web UI: http://127.0.0.1:18789"
	@echo ""
	@echo "  Verify with: make status"
	@echo "  View logs:   make logs"
	@echo ""

# ============================================================================
# Configure — patch openclaw.json with required settings
# ============================================================================

configure:
	@if [ -z "$(MEM0_API_KEY)" ]; then \
		echo ""; \
		echo "  Enter your Mem0 API key (from https://app.mem0.ai/dashboard/api-keys):"; \
		echo -n "  > "; \
		read -r key; \
		if [ -z "$$key" ]; then echo "Error: API key is required."; exit 1; fi; \
		MEM0_API_KEY="$$key" MEM0_USER_ID="$(MEM0_USER_ID)" python3 scripts/configure.py; \
	else \
		MEM0_API_KEY="$(MEM0_API_KEY)" MEM0_USER_ID="$(MEM0_USER_ID)" python3 scripts/configure.py; \
	fi

# ============================================================================
# Status & Logs
# ============================================================================

status: ## Check plugin health and skills registration
	@echo "Plugin health:"
	@openclaw plugins doctor 2>&1 | grep -v "plugins.allow"
	@echo ""
	@echo "Skills:"
	@openclaw skills list 2>&1 | grep -E "memory|Status|---" | head -10
	@echo ""
	@echo "Last gateway registration:"
	@tail -50 /tmp/openclaw/openclaw-$$(date +%Y-%m-%d).log 2>/dev/null | grep "openclaw-mem0: registered" | tail -1 | grep -o '"1":"[^"]*"' || echo "  No gateway log found. Is the gateway running?"

logs: ## Tail gateway logs (mem0 activity only)
	@tail -f /tmp/openclaw/openclaw-$$(date +%Y-%m-%d).log 2>/dev/null | grep --line-buffered -o '"1":"[^"]*"' | grep --line-buffered -i "mem0\|skills-mode\|stored\|inject\|recall"

# ============================================================================
# Restart
# ============================================================================

restart: build ## Rebuild plugin and restart gateway
	@echo "Restarting gateway..."
	@kill -9 $$(lsof -ti:18789) 2>/dev/null || true
	@sleep 2
	@openclaw gateway >/dev/null 2>&1 &
	@sleep 4
	@echo "Gateway restarted. Verify: make status"

# ============================================================================
# Uninstall — revert to stock plugin
# ============================================================================

uninstall: ## Revert to stock openclaw-mem0 from npm
	@echo "Uninstalling local plugin..."
	@echo "y" | openclaw plugins uninstall openclaw-mem0 >/dev/null 2>&1 || true
	@echo "Installing stock plugin from npm..."
	@openclaw plugins install @mem0/openclaw-mem0 2>&1 | grep -v "plugins.allow"
	@# Restore config backup if it exists
	@if [ -f "$(OPENCLAW_CONFIG).pre-skills-backup" ]; then \
		cp "$(OPENCLAW_CONFIG).pre-skills-backup" "$(OPENCLAW_CONFIG)"; \
		echo "Restored config from backup."; \
	else \
		echo "Note: No config backup found. You may need to manually revert openclaw.json changes."; \
	fi
	@echo "Restarting gateway..."
	@kill -9 $$(lsof -ti:18789) 2>/dev/null || true
	@sleep 2
	@openclaw gateway >/dev/null 2>&1 &
	@sleep 4
	@echo "Reverted to stock openclaw-mem0."

# ============================================================================
# Clean
# ============================================================================

clean: ## Full teardown — stop gateway, remove plugin, clean build
	@echo "Stopping gateway..."
	@kill -9 $$(lsof -ti:18789) 2>/dev/null || true
	@echo "Removing plugin..."
	@echo "y" | openclaw plugins uninstall openclaw-mem0 >/dev/null 2>&1 || true
	@echo "Cleaning build artifacts..."
	@rm -rf dist/ node_modules/
	@echo "Clean complete."
