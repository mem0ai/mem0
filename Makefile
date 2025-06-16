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

# Check prerequisites
check-prereqs:
	@echo "Checking prerequisites..."
	@if command -v docker >/dev/null 2>&1 ; then \
		echo "✅ Docker is installed"; \
	else \
		echo "❌ Docker is required but not installed"; \
		exit 1; \
	fi
	@if command -v node >/dev/null 2>&1 ; then \
		echo "✅ Node.js is installed"; \
	else \
		echo "❌ Node.js is required but not installed"; \
		exit 1; \
	fi
	@if command -v pnpm >/dev/null 2>&1 ; then \
		echo "✅ pnpm is installed"; \
	else \
		echo "❌ pnpm is required but not installed. Run: brew install pnpm"; \
		exit 1; \
	fi
	@echo "✅ Prerequisites check completed."

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

# Validate that required API keys are set
validate-env:
	@echo "🔍 Validating environment configuration..."
	@if [ ! -f openmemory/api/.env ]; then \
		echo "❌ openmemory/api/.env not found. Run 'make env' first."; \
		exit 1; \
	fi
	@if grep -q "your_openai_api_key_here" openmemory/api/.env; then \
		echo "❌ OPENAI_API_KEY not set in openmemory/api/.env"; \
		echo "   Edit the file and replace 'your_openai_api_key_here' with your actual key"; \
		echo "   Get your key from: https://platform.openai.com/api-keys"; \
		exit 1; \
	fi
	@if grep -q "auto-generated-by-setup" openmemory/.env.local 2>/dev/null; then \
		echo "❌ Supabase keys not configured. Run 'cd openmemory && make setup' first."; \
		exit 1; \
	fi
	@if [ ! -d ".venv" ]; then \
		echo "❌ Python virtual environment not found. Run 'make setup' to create it."; \
		exit 1; \
	fi
	@echo "✅ Environment validation passed!"

# Complete setup for new users - delegate to the proper setup script
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
	@echo "📍 Python 3.12.x will be automatically installed if needed"
	@echo "   (macOS: via Homebrew, Linux: via package manager)"
	@echo ""
	@read -p "Continue with full setup? (Y/n): " -n 1 -r; \
	echo; \
	if [[ ! $$REPLY =~ ^[Nn]$$ ]]; then \
		cd openmemory && make setup; \
	else \
		echo "Setup cancelled. Run 'make env' to create basic environment files."; \
	fi

# Build and install after environment is configured
build: validate-env
	@echo "🏗️ Building Jean Memory development environment..."
	@echo "Installing UI dependencies..."
	@cd openmemory/ui && pnpm install --no-frozen-lockfile
	@echo "Building Docker images..."
	@cd openmemory && $(DOCKER_COMPOSE) build
	@echo ""
	@echo "✅ Build complete! Ready to develop:"
	@echo "  • Run 'make backend' to start backend services"
	@echo "  • Run 'make ui-local' to start UI development server"

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
