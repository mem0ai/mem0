.PHONY: help setup dev dev-api dev-ui stop restart status clean studio logs migrate db-reset test configure-env validate build

# Default target
help:
	@echo "🚀 OpenMemory Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  setup       - One-time setup with API key collection"
	@echo "  build       - Complete build and environment setup"
	@echo "  configure-env - Update environment with current Supabase keys"
	@echo "  validate    - Check if environment is properly configured"
	@echo ""
	@echo "Development:"
	@echo "  dev         - Start complete development environment"
	@echo "  dev-api     - Start only the API server"
	@echo "  dev-ui      - Start only the UI server"
	@echo "  stop        - Stop all services"
	@echo "  restart     - Restart everything"
	@echo "  status      - Check what's running"
	@echo ""
	@echo "Database:"
	@echo "  migrate     - Apply database migrations"
	@echo "  db-reset    - Reset database to clean state"
	@echo "  studio      - Open Supabase Studio"
	@echo ""
	@echo "Utilities:"
	@echo "  logs        - View service logs"
	@echo "  test        - Run tests"
	@echo "  clean       - Stop and reset everything"

# One-time setup with API key collection
setup:
	@echo "🏗️  Setting up OpenMemory development environment..."
	@echo "This will collect your API keys and set up everything needed."
	@chmod +x scripts/setup-dev-environment.sh
	@./scripts/setup-dev-environment.sh

# Complete build after setup (for when user wants to rebuild)
build:
	@echo "🔨 Building OpenMemory environment..."
	@$(MAKE) -s _check-setup
	@echo "🔧 Configuring environment with latest keys..."
	@$(MAKE) -s configure-env
	@echo "📦 Installing/updating dependencies..."
	@if [ -d "ui" ] && [ -f "ui/package.json" ]; then \
		cd ui && npm install --silent; \
		echo "✅ UI dependencies updated"; \
	fi
	@if [ -d "api" ] && [ -f "api/requirements.txt" ]; then \
		cd api && pip install -r requirements.txt --quiet; \
		echo "✅ API dependencies updated"; \
	fi
	@echo "🚀 Starting services..."
	@$(MAKE) -s _ensure-supabase
	@$(MAKE) -s _ensure-qdrant
	@$(MAKE) -s validate
	@echo "✅ Build complete! Run 'make dev' to start development."

# Configure environment with current Supabase keys
configure-env:
	@echo "🔧 Configuring environment..."
	@chmod +x scripts/configure-env.sh
	@./scripts/configure-env.sh

# Validate environment configuration
validate:
	@chmod +x scripts/validate-env.sh
	@./scripts/validate-env.sh

# Start complete development environment
dev:
	@echo "🚀 Starting OpenMemory development environment..."
	@$(MAKE) -s validate
	@$(MAKE) -s _check-env
	@echo "📊 Checking service status..."
	@if ! npx supabase status >/dev/null 2>&1; then \
		echo "🗄️  Starting Supabase..."; \
		npx supabase start; \
		echo "🔧 Configuring environment with latest keys..."; \
		$(MAKE) -s configure-env; \
	else \
		echo "✅ Supabase is running"; \
	fi
	@if ! docker ps | grep -q qdrant; then \
		echo "🔍 Starting Qdrant..."; \
		docker-compose up -d qdrant_db; \
	else \
		echo "✅ Qdrant is running"; \
	fi
	@echo "🌐 Starting servers..."
	@echo "   API: http://localhost:8765"
	@echo "   UI:  http://localhost:3000"
	@echo ""
	@echo "Press Ctrl+C to stop all servers..."
	@trap 'echo "\n🛑 Stopping servers..."; $(MAKE) -s _stop-servers; exit 0' INT; \
	$(MAKE) -s _start-servers

# Start only API server
dev-api:
	@echo "🔧 Starting API server..."
	@$(MAKE) -s _check-env
	@$(MAKE) -s _ensure-supabase
	@$(MAKE) -s _ensure-qdrant
	@echo "🌐 API server starting at http://localhost:8765"
	@cd api && ../.venv/bin/python -m uvicorn main:app --reload --port 8765 --host 0.0.0.0

# Start only UI server  
dev-ui:
	@echo "🎨 Starting UI server..."
	@$(MAKE) -s _check-env
	@if [ ! -d "ui/node_modules" ]; then \
		echo "📦 Installing UI dependencies..."; \
		cd ui && npm install; \
	fi
	@echo "🌐 UI server starting at http://localhost:3000"
	@cd ui && npm run dev

# Stop all services
stop:
	@echo "🛑 Stopping all services..."
	@$(MAKE) -s _stop-servers
	@docker-compose down 2>/dev/null || true
	@npx supabase stop 2>/dev/null || true
	@echo "✅ All services stopped"

# Restart everything
restart:
	@$(MAKE) -s stop
	@sleep 2
	@$(MAKE) -s dev

# Check status of all services
status:
	@echo "📊 Service Status:"
	@echo ""
	@echo "🗄️  Supabase:"
	@if npx supabase status >/dev/null 2>&1; then \
		echo "   ✅ Running"; \
		npx supabase status | grep -E "(API URL|Studio URL)"; \
	else \
		echo "   ❌ Not running"; \
	fi
	@echo ""
	@echo "🔍 Qdrant:"
	@if docker ps | grep -q qdrant; then \
		echo "   ✅ Running at http://localhost:6333"; \
	else \
		echo "   ❌ Not running"; \
	fi
	@echo ""
	@echo "🔧 API Server:"
	@if curl -s http://localhost:8765/health >/dev/null 2>&1; then \
		echo "   ✅ Running at http://localhost:8765"; \
	else \
		echo "   ❌ Not running"; \
	fi
	@echo ""
	@echo "🎨 UI Server:"
	@if curl -s http://localhost:3000 >/dev/null 2>&1; then \
		echo "   ✅ Running at http://localhost:3000"; \
	else \
		echo "   ❌ Not running"; \
	fi

# Apply database migrations
migrate:
	@echo "🗄️  Applying database migrations..."
	@$(MAKE) -s _ensure-supabase
	@npx supabase db reset
	@echo "✅ Migrations applied"

# Reset database
db-reset:
	@echo "🗄️  Resetting database..."
	@$(MAKE) -s _ensure-supabase
	@npx supabase db reset
	@echo "✅ Database reset complete"

# Open Supabase Studio
studio:
	@echo "🎛️  Opening Supabase Studio..."
	@$(MAKE) -s _ensure-supabase
	@open http://localhost:54323 || echo "Visit: http://localhost:54323"

# View logs
logs:
	@echo "📄 Service logs:"
	@echo ""
	@echo "🗄️  Supabase logs:"
	@npx supabase logs 2>/dev/null || echo "Supabase not running"
	@echo ""
	@echo "🔍 Qdrant logs:"
	@docker-compose logs qdrant_db 2>/dev/null || echo "Qdrant not running"

# Run tests
test:
	@echo "🧪 Running tests..."
	@if [ -d "api" ]; then \
		cd api && ../.venv/bin/python -m pytest tests/ -v; \
	fi
	@if [ -d "ui" ]; then \
		cd ui && npm test; \
	fi

# Clean everything (nuclear option)
clean:
	@echo "🧹 Cleaning everything..."
	@echo "⚠️  This will remove all local data!"
	@printf "Are you sure? (y/N): "; \
	read confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		echo "🛑 Stopping all services..."; \
		$(MAKE) -s stop; \
		echo "🗑️  Removing Docker volumes and containers..."; \
		docker-compose down -v 2>/dev/null || true; \
		echo "🗑️  Stopping Supabase..."; \
		npx supabase stop 2>/dev/null || true; \
		echo "🗑️  Cleaning Docker system..."; \
		docker system prune -f 2>/dev/null || true; \
		echo "✅ Clean complete"; \
	else \
		echo "❌ Clean cancelled"; \
	fi

# Internal helper targets (prefixed with _)
_check-env:
	@if [ ! -f ".env.local" ]; then \
		echo "❌ Environment not configured. Run 'make setup' first."; \
		exit 1; \
	fi

_check-setup:
	@if [ ! -f ".env.local" ] || [ ! -f "api/.env" ] || [ ! -f "ui/.env.local" ]; then \
		echo "❌ Setup not complete. Run 'make setup' first to collect API keys and configure environment."; \
		exit 1; \
	fi

_ensure-supabase:
	@if ! npx supabase status >/dev/null 2>&1; then \
		echo "🗄️  Starting Supabase..."; \
		npx supabase start; \
	fi

_ensure-qdrant:
	@if ! docker ps | grep -q qdrant; then \
		echo "🔍 Starting Qdrant..."; \
		docker-compose up -d qdrant_db; \
		sleep 3; \
	fi

_start-servers:
	@{ \
		cd api && python -m uvicorn main:app --reload --port 8765 --host 0.0.0.0 & \
		API_PID=$$!; \
		echo $$API_PID > .api.pid; \
		cd ui && npm run dev & \
		UI_PID=$$!; \
		echo $$UI_PID > .ui.pid; \
		wait; \
	}

_stop-servers:
	@if [ -f ".api.pid" ]; then \
		kill `cat .api.pid` 2>/dev/null || true; \
		rm -f .api.pid; \
	fi
	@if [ -f ".ui.pid" ]; then \
		kill `cat .ui.pid` 2>/dev/null || true; \
		rm -f .ui.pid; \
	fi
	@pkill -f "uvicorn main:app" 2>/dev/null || true
	@pkill -f "next-server" 2>/dev/null || true
