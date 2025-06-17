.PHONY: help env check-prereqs setup build validate-env backend ui-local status restart-backend restart-ui-local up down logs clean test

# Default user ID
USER_ID ?= default_user
NEXT_PUBLIC_API_URL ?= http://localhost:8765

# Docker commands
DOCKER_COMPOSE = docker compose
DOCKER_CMD = docker

# Default target
help:
	@echo "🧠 Jean Memory - Development Commands"
	@echo ""
	@echo "📋 Prerequisites:"
	@echo "  Docker Desktop, Node.js, pnpm"
	@echo "  Python 3.12.x (auto-installed if missing)"
	@echo ""
	@echo "🚀 Quick Start:"
	@echo "  make setup               - Complete setup with API key collection"
	@echo "  make build               - Build environment (run after setup)"
	@echo "  make backend             - Start backend services (Terminal 1)"
	@echo "  make ui-local            - Start UI locally (Terminal 2)"
	@echo ""
	@echo "📊 Monitoring:"
	@echo "  make status              - Show status of all services"
	@echo "  make logs                - Show Docker logs"
	@echo ""
	@echo "🔄 Restart Commands:"
	@echo "  make restart-backend     - Restart backend services"
	@echo "  make restart-ui-local    - Restart local UI server"
	@echo ""
	@echo "🐳 Full Docker Mode (Alternative):"
	@echo "  make up                  - Start all services in Docker"
	@echo "  make down                - Stop all Docker services"
	@echo ""
	@echo "🧹 Maintenance:"
	@echo "  make clean               - Reset to fresh state (removes all data)"
	@echo "  make test                - Run tests"
	@echo "  make check-prereqs       - Check if prerequisites are installed"

# Enhanced prerequisites check with essential validation
check-prereqs:
	@echo "🔍 Checking prerequisites..."
	@# Check Docker
	@if ! command -v docker >/dev/null 2>&1; then \
		echo "❌ Docker is required but not installed"; \
		echo "   Install from: https://docker.com/get-started"; \
		exit 1; \
	fi
	@if ! docker info >/dev/null 2>&1; then \
		echo "❌ Docker is installed but not running"; \
		echo "   Start Docker Desktop and try again"; \
		exit 1; \
	fi
	@echo "✅ Docker is installed and running"
	@# Check Node.js version (need 18+)
	@if ! command -v node >/dev/null 2>&1; then \
		echo "❌ Node.js is required but not installed"; \
		echo "   Install from: https://nodejs.org"; \
		exit 1; \
	fi
	@NODE_VERSION=$$(node --version | sed 's/v//'); \
	NODE_MAJOR=$$(echo $$NODE_VERSION | cut -d. -f1); \
	if [ $$NODE_MAJOR -lt 18 ]; then \
		echo "❌ Node.js $$NODE_VERSION found, but 18+ required"; \
		echo "   Update from: https://nodejs.org"; \
		exit 1; \
	fi
	@echo "✅ Node.js is installed ($(shell node --version))"
	@# Check pnpm
	@if ! command -v pnpm >/dev/null 2>&1; then \
		echo "❌ pnpm is required but not installed"; \
		echo "   Install with: npm install -g pnpm"; \
		exit 1; \
	fi
	@echo "✅ pnpm is installed ($(shell pnpm --version))"
	@# Check critical ports availability
	@if lsof -i :3000 >/dev/null 2>&1; then \
		echo "⚠️ Port 3000 is in use (needed for UI)"; \
		echo "   Stop the service using port 3000 or it will conflict"; \
	fi
	@if lsof -i :8765 >/dev/null 2>&1; then \
		echo "⚠️ Port 8765 is in use (needed for API)"; \
		echo "   Stop the service using port 8765 or it will conflict"; \
	fi
	@if lsof -i :54322 >/dev/null 2>&1 || lsof -i :54323 >/dev/null 2>&1; then \
		echo "⚠️ Supabase ports (54322/54323) in use"; \
		echo "   This may cause database connection issues"; \
	fi
	@# Check basic resource requirements
	@if command -v df >/dev/null 2>&1; then \
		AVAILABLE_GB=$$(df -BG . 2>/dev/null | awk 'NR==2 {print $$4}' | sed 's/G//' 2>/dev/null || echo "10"); \
		if [ $$AVAILABLE_GB -lt 5 ] 2>/dev/null; then \
			echo "⚠️ Low disk space: $${AVAILABLE_GB}GB available"; \
			echo "   Need at least 5GB for Docker images and dependencies"; \
		fi; \
	fi
	@# Check Docker permissions (Linux-specific)
	@if [[ "$$OSTYPE" == "linux-gnu"* ]] && ! groups | grep -q docker 2>/dev/null; then \
		echo "⚠️ Docker permission may be required on Linux"; \
		echo "   If setup fails, run: sudo usermod -aG docker $$USER && newgrp docker"; \
	fi
	@echo "✅ All prerequisites satisfied"

# Setup environment files
env:
	@echo "🔧 Setting up environment files..."
	@if [ ! -f openmemory/.env.local ]; then \
		cp openmemory/env.local.example openmemory/.env.local; \
		echo "✅ Created openmemory/.env.local from example"; \
	else \
		echo "⚠️ openmemory/.env.local already exists, skipping"; \
	fi
	@if [ ! -f openmemory/api/.env ]; then \
		cp openmemory/env.example openmemory/api/.env; \
		echo "✅ Created openmemory/api/.env from example"; \
	else \
		echo "⚠️ openmemory/api/.env already exists, skipping"; \
	fi

# Enhanced validation with helpful error messages
validate-env:
	@echo "🔍 Validating environment configuration..."
	@# Check environment files exist
	@if [ ! -f openmemory/api/.env ]; then \
		echo "❌ openmemory/api/.env not found. Run 'make env' first."; \
		exit 1; \
	fi
	@if [ ! -f openmemory/.env.local ]; then \
		echo "❌ openmemory/.env.local not found. Run 'make env' first."; \
		exit 1; \
	fi
	@# Check API keys are configured
	@if grep -q "your_openai_api_key_here" openmemory/api/.env 2>/dev/null; then \
		echo "❌ OPENAI_API_KEY not configured in openmemory/api/.env"; \
		echo "   1. Get your API key from: https://platform.openai.com/api-keys"; \
		echo "   2. Edit openmemory/api/.env and replace 'your_openai_api_key_here'"; \
		exit 1; \
	fi
	@# Check API key is not empty
	@if [ -f openmemory/api/.env ]; then \
		OPENAI_KEY=$$(grep "OPENAI_API_KEY=" openmemory/api/.env | cut -d= -f2 | tr -d '"' | tr -d "'" | xargs); \
		if [ -z "$$OPENAI_KEY" ]; then \
			echo "❌ OPENAI_API_KEY is empty in openmemory/api/.env"; \
			echo "   Get your API key from: https://platform.openai.com/api-keys"; \
			exit 1; \
		fi; \
	fi
	@# Check Python virtual environment
	@if [ ! -d ".venv" ]; then \
		echo "❌ Python virtual environment not found. Run 'make setup' to create it."; \
		exit 1; \
	fi
	@# Quick Python environment validation
	@if [ -f ".venv/bin/python" ]; then \
		VENV_VERSION=$$(.venv/bin/python --version 2>&1); \
		if [[ "$$VENV_VERSION" != *"3.12."* ]]; then \
			echo "⚠️ Virtual environment uses $$VENV_VERSION (expected Python 3.12.x)"; \
			echo "   Run 'make clean && make setup' to recreate with correct Python version"; \
		fi; \
	fi
	@echo "✅ Environment validation passed"

# Complete setup for new users with better error handling
setup: check-prereqs
	@echo ""
	@echo "🚨 RUNNING COMPLETE SETUP 🚨"
	@echo ""
	@echo "This will:"
	@echo "  • Create environment files"
	@echo "  • Install Python 3.12.x and dependencies"
	@echo "  • Start and configure Supabase database"
	@echo "  • Start Qdrant vector database"
	@echo "  • Collect your API keys interactively"
	@echo ""
	@echo "You'll be prompted for:"
	@echo "  • OPENAI_API_KEY (required)"
	@echo "  • GEMINI_API_KEY (optional)"
	@echo ""
	@echo "📍 Python 3.12.x will be automatically installed if needed"
	@echo "   (macOS: via Homebrew, Linux: via package manager)"
	@echo ""
	@read -p "Continue with complete setup? (Y/n): " -n 1 -r; \
	echo; \
	if [[ ! $$REPLY =~ ^[Nn]$$ ]]; then \
		echo "🔧 Running setup..."; \
		if cd openmemory && make setup; then \
			echo ""; \
			echo "✅ Setup completed successfully!"; \
			echo ""; \
			echo "🎯 Next step: Run 'make build' to complete installation"; \
		else \
			echo ""; \
			echo "❌ Setup failed. Common issues:"; \
			echo "   • Docker not running: Start Docker Desktop"; \
			echo "   • Python installation failed: Install Python 3.12.x manually"; \
			echo "   • Network issues: Check internet connection"; \
			exit 1; \
		fi; \
	else \
		echo "Setup cancelled. Run 'make env' to create basic environment files."; \
	fi

# Build with validation and better error handling
build: validate-env
	@echo "🏗️ Building Jean Memory development environment..."
	@echo "📋 Validating setup completion..."
	@# Verify critical dependencies before building
	@if [ -f ".venv/bin/python" ] && ! .venv/bin/python -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)" 2>/dev/null; then \
		echo "❌ Python 3.12.x required but found $$(.venv/bin/python --version 2>&1)"; \
		echo "   Run 'make clean && make setup' to recreate environment"; \
		exit 1; \
	fi
	@echo "📦 Installing UI dependencies..."
	@if ! cd openmemory/ui && pnpm install --no-frozen-lockfile; then \
		echo "❌ Failed to install UI dependencies"; \
		echo "   Try: cd openmemory/ui && rm -rf node_modules && pnpm install"; \
		exit 1; \
	fi
	@echo "🐳 Building Docker images..."
	@if ! cd openmemory && $(DOCKER_COMPOSE) build; then \
		echo "❌ Failed to build Docker images"; \
		echo "   Check Docker is running and try again"; \
		exit 1; \
	fi
	@echo ""
	@echo "✅ Build completed successfully!"
	@echo ""
	@echo "🚀 Ready to develop:"
	@echo "  • Terminal 1: make backend"
	@echo "  • Terminal 2: make ui-local"
	@echo "  • UI: http://localhost:3000"
	@echo "  • API: http://localhost:8765/docs"

# HYBRID DEVELOPMENT COMMANDS (Recommended)
# Start backend services - delegate to openmemory Makefile
backend:
	@echo "🐳 Starting backend services..."
	@cd openmemory && make dev-api

# Run UI locally for faster development
ui-local:
	@echo "🚀 Starting UI locally for development..."
	@cd openmemory && make dev-ui

# Show status of all services
status:
	@echo "📊 Development environment status:"
	@cd openmemory && make status

# Restart only the backend
restart-backend:
	@echo "🔄 Restarting backend services..."
	@cd openmemory && make restart

# Restart only the local UI
restart-ui-local:
	@echo "🔄 Restarting local UI development server..."
	@cd openmemory && make dev-ui

# FULL DOCKER MODE (Alternative)
# Start all services in Docker
up:
	@echo "🐳 Starting all services in Docker..."
	@cd openmemory && $(DOCKER_COMPOSE) up -d
	@echo "✅ All services started. UI: http://localhost:3000, API: http://localhost:8765"

# Stop Docker services
down:
	@echo "🛑 Stopping all Docker services..."
	@cd openmemory && $(DOCKER_COMPOSE) down -v

# Show Docker logs
logs:
	@cd openmemory && $(DOCKER_COMPOSE) logs -f

# Clean up everything - reset to pristine state
clean:
	@echo "🧹 Resetting to fresh state..."
	@echo ""
	@echo "⚠️  This will remove:"
	@echo "   • All Docker containers and volumes (user data)"
	@echo "   • Python virtual environment"
	@echo "   • Node.js dependencies"
	@echo "   • All services and databases"
	@echo ""
	@read -p "Are you sure? This will delete all local data! (y/N): " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		echo "🛑 Stopping all services..."; \
		cd openmemory && make clean 2>/dev/null || true; \
		echo "🗑️ Removing Docker containers and volumes..."; \
		cd openmemory && $(DOCKER_COMPOSE) down -v 2>/dev/null || true; \
		echo "🗑️ Removing Python virtual environment..."; \
		rm -rf .venv; \
		echo "🗑️ Removing Node.js dependencies..."; \
		rm -rf node_modules .pnpm-store openmemory/ui/node_modules 2>/dev/null || true; \
		echo "✅ Reset complete! Run 'make setup' to start fresh"; \
	else \
		echo "❌ Clean cancelled - no changes made"; \
	fi

# Run tests
test:
	@echo "🧪 Running tests..."
	@cd openmemory && make test
