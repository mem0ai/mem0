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
	@if [ ! -f openmemory/api/.env ]; then \
		cp openmemory/api/.env.example openmemory/api/.env; \
		echo "✅ Created openmemory/api/.env from example"; \
	else \
		echo "⚠️ openmemory/api/.env already exists, skipping"; \
	fi
	@if [ ! -f openmemory/ui/.env.local ]; then \
		cp openmemory/ui/.env.example openmemory/ui/.env.local; \
		echo "✅ Created openmemory/ui/.env.local from example"; \
	else \
		echo "⚠️ openmemory/ui/.env.local already exists, skipping"; \
	fi

# Validate that required API keys are set
validate-env:
	@echo "🔍 Validating environment configuration..."
	@if [ ! -f openmemory/api/.env ]; then \
		echo "❌ openmemory/api/.env not found. Run 'make env' first."; \
		exit 1; \
	fi
	@if grep -q "your-openai-api-key-here" openmemory/api/.env; then \
		echo "❌ OPENAI_API_KEY not set in openmemory/api/.env"; \
		echo "   Edit the file and replace 'your-openai-api-key-here' with your actual key"; \
		echo "   Get your key from: https://platform.openai.com/api-keys"; \
		exit 1; \
	fi
	@if grep -q "your-gemini-api-key-here" openmemory/api/.env; then \
		echo "❌ GEMINI_API_KEY not set in openmemory/api/.env"; \
		echo "   Edit the file and replace 'your-gemini-api-key-here' with your actual key"; \
		echo "   Get your key from: https://makersuite.google.com/app/apikey"; \
		exit 1; \
	fi
	@echo "✅ Environment validation passed!"

# Complete setup for new users  
setup: check-prereqs env
	@echo ""
	@echo "🚨 SETUP REQUIRES YOUR API KEYS 🚨"
	@echo ""
	@echo "Before continuing, you need to edit openmemory/api/.env and add:"
	@echo "  • OPENAI_API_KEY (get from: https://platform.openai.com/api-keys)"
	@echo "  • GEMINI_API_KEY (get from: https://makersuite.google.com/app/apikey)"
	@echo ""
	@echo "After adding your keys, run 'make build' to continue setup."
	@echo ""
	@echo "💡 TIP: Everything else is auto-configured for local development!"

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
# Start backend services in Docker
backend:
	@echo "🐳 Starting backend services in Docker..."
	@cd openmemory && docker-compose up -d api postgres_db qdrant_db
	@echo "✅ Backend services started. API available at http://localhost:8765"

# Run UI locally for faster development
ui-local:
	@echo "🚀 Starting UI locally for development..."
	@chmod +x scripts/local-dev/local-dev-ui.sh
	@scripts/local-dev/local-dev-ui.sh

# Show status of all services
status:
	@echo "📊 Docker services status:"
	@cd openmemory && docker-compose ps
	@echo ""
	@echo "🖥️ UI local development status:"
	@ps aux | grep "pnpm dev\|npm run dev" | grep -v grep || echo "UI is not running locally"

# Restart only the backend
restart-backend:
	@echo "🔄 Restarting backend services..."
	@cd openmemory && docker-compose restart api postgres_db qdrant_db
	@echo "✅ Backend services restarted"

# Restart only the local UI
restart-ui-local:
	@echo "🔄 Restarting local UI development server..."
	@chmod +x scripts/local-dev/restart-ui-local.sh
	@scripts/local-dev/restart-ui-local.sh

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
	@echo "Stopping and removing all Docker containers..."
	@cd openmemory && $(DOCKER_COMPOSE) down -v --remove-orphans 2>/dev/null || true
	@echo "Removing Docker images..."
	@cd openmemory && docker-compose down --rmi all 2>/dev/null || true
	@echo "Cleaning UI dependencies and build files..."
	@cd openmemory/ui && rm -rf node_modules .next .pnpm-store pnpm-lock.yaml 2>/dev/null || true
	@echo "Removing environment files..."
	@rm -f openmemory/api/.env openmemory/ui/.env.local 2>/dev/null || true
	@echo "Cleaning Docker build cache..."
	@docker builder prune -f 2>/dev/null || true
	@echo "✅ Clean complete! Ready for 'make setup' to start fresh"

# Run tests
test:
	@echo "🧪 Running tests..."
	@cd openmemory && $(DOCKER_COMPOSE) exec -T api python -m pytest || echo "❌ Failed to run tests"
