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
	@echo "  make setup               - Create .env files (add your API keys after this)"
	@echo "  make build               - Build everything after adding API keys"
	@echo "  make backend             - Start backend services in Docker"
	@echo "  make ui-local            - Run UI locally (recommended for development)"
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
	@echo "  make clean               - Clean up containers and temp files"
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
	@# Validate API key format
	@if [ -f openmemory/api/.env ]; then \
		OPENAI_KEY=$$(grep "OPENAI_API_KEY=" openmemory/api/.env | cut -d= -f2 | tr -d '"' | tr -d "'" | xargs); \
		if [ ! -z "$$OPENAI_KEY" ] && [ "$$OPENAI_KEY" != "your_openai_api_key_here" ]; then \
			if [[ ! "$$OPENAI_KEY" =~ ^sk-[a-zA-Z0-9-_]{48,}$$ ]]; then \
				echo "⚠️ OPENAI_API_KEY format looks incorrect"; \
				echo "   Expected format: sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"; \
				echo "   Current: $$OPENAI_KEY"; \
				echo "   Double-check your key from: https://platform.openai.com/api-keys"; \
			fi; \
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
	@echo "🚨 RUNNING COMPREHENSIVE SETUP 🚨"
	@echo ""
	@echo "This will:"
	@echo "  • Create environment files"
	@echo "  • Install all dependencies" 
	@echo "  • Start Supabase and configure it automatically"
	@echo "  • Start Qdrant vector database"
	@echo "  • Prompt you for API keys"
	@echo ""
	@echo "You'll only need to provide:"
	@echo "  • OPENAI_API_KEY (required)"
	@echo "  • GEMINI_API_KEY (optional)"
	@echo ""
	@echo "📍 Python 3.12.x will be automatically installed if needed (faster setup!)"
	@echo "   (macOS: via Homebrew, Linux: via package manager)"
	@echo ""
	@read -p "Continue with full setup? (Y/n): " -n 1 -r; \
	echo; \
	if [[ ! $$REPLY =~ ^[Nn]$$ ]]; then \
		echo "🔧 Running setup..."; \
		if cd openmemory && make setup; then \
			echo ""; \
			echo "✅ Setup completed successfully!"; \
			echo ""; \
			echo "📝 Next steps:"; \
			echo "   1. Edit openmemory/api/.env and add your OPENAI_API_KEY"; \
			echo "   2. Run 'make build' to complete the installation"; \
			echo "   3. Run 'make backend' and 'make ui-local' to start development"; \
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
	@echo "🧹 Resetting to clean state (like fresh git clone)..."
	@echo "Stopping and removing all services..."
	@cd openmemory && make clean 2>/dev/null || true
	@echo "Cleaning root-level dependencies..."
	@rm -rf node_modules .pnpm-store 2>/dev/null || true
	@echo "✅ Clean complete! Ready for 'make setup' to start fresh"

# Run tests
test:
	@echo "🧪 Running tests..."
	@cd openmemory && make test
