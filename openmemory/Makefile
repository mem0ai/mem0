.PHONY: help setup dev stop status restart logs clean env migrate test db-reset db-logs studio

# Default target
help:
	@echo "OpenMemory Development Commands:"
	@echo "  make setup             - Complete first-time setup"
	@echo "  make dev               - Start development environment (Supabase + Qdrant + API + UI)"
	@echo "  make stop              - Stop all services"
	@echo "  make status            - Show status of all services"
	@echo "  make restart           - Restart all services"
	@echo "  make logs              - View logs from all services"
	@echo "  make clean             - Clean all data and reset to fresh state"
	@echo "  make env               - Show current environment configuration"
	@echo ""
	@echo "Database Commands:"
	@echo "  make migrate           - Apply database migrations"
	@echo "  make db-reset          - Reset database to fresh state"
	@echo "  make db-logs           - View database logs"
	@echo ""
	@echo "Development Tools:"
	@echo "  make studio            - Open Supabase Studio"
	@echo "  make test              - Run tests"

# Complete setup for first time contributors
setup:
	@echo "🚀 Setting up OpenMemory development environment..."
	@echo ""
	@echo "📦 Installing Supabase CLI..."
	@npm install
	@echo ""
	@echo "🔧 Creating environment files..."
	@if [ ! -f .env.local ]; then \
		echo "Copying environment template..."; \
		cp env.local.example .env.local; \
		echo "⚠️  Please edit .env.local with your API keys before proceeding"; \
		echo "   Required: OPENAI_API_KEY"; \
		echo "   After running 'make dev', copy Supabase keys from the output"; \
	else \
		echo "✓ .env.local already exists"; \
	fi
	@echo ""
	@echo "✅ Setup complete!"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Edit .env.local with your OPENAI_API_KEY"
	@echo "  2. Run 'make dev' to start the development environment"
	@echo "  3. Copy Supabase keys from the output to .env.local"

# Start complete development environment
dev:
	@echo "🚀 Starting OpenMemory development environment..."
	@echo ""
	@echo "📊 Starting Qdrant vector database..."
	@docker-compose up -d qdrant_db
	@echo ""
	@echo "🗄️ Starting local Supabase..."
	@npx supabase start
	@echo ""
	@echo "📋 Current Supabase configuration:"
	@npx supabase status
	@echo ""
	@echo "⚠️  Copy the above Supabase URLs and keys to your .env.local file!"
	@echo ""
	@echo "🔥 Starting API server..."
	@cd api && python -m uvicorn main:app --reload --host 0.0.0.0 --port 8765 &
	@echo ""
	@echo "🌐 Starting UI development server..."
	@cd ui && npm run dev &
	@echo ""
	@echo "✅ Development environment started!"
	@echo ""
	@echo "🌐 Services available at:"
	@echo "   UI:               http://localhost:3000"
	@echo "   API:              http://localhost:8765"
	@echo "   Supabase Studio:  http://localhost:54323"
	@echo "   Qdrant Dashboard: http://localhost:6333/dashboard"

# Stop all services
stop:
	@echo "🛑 Stopping all services..."
	@echo "Stopping UI..."
	@pkill -f "npm run dev" || true
	@echo "Stopping API..."
	@pkill -f "uvicorn main:app" || true
	@echo "Stopping Supabase..."
	@npx supabase stop
	@echo "Stopping Qdrant..."
	@docker-compose down
	@echo "✅ All services stopped"

# Show status of all services
status:
	@echo "📊 OpenMemory Service Status"
	@echo "=========================="
	@echo ""
	@echo "🗄️ Supabase Status:"
	@npx supabase status || echo "❌ Supabase not running"
	@echo ""
	@echo "🔍 Qdrant Status:"
	@docker-compose ps qdrant_db || echo "❌ Qdrant not running"
	@echo ""
	@echo "🚀 API Status:"
	@curl -s http://localhost:8765/health > /dev/null && echo "✅ API running on http://localhost:8765" || echo "❌ API not responding"
	@echo ""
	@echo "🌐 UI Status:"
	@curl -s http://localhost:3000 > /dev/null && echo "✅ UI running on http://localhost:3000" || echo "❌ UI not responding"

# Restart all services
restart:
	@echo "🔄 Restarting all services..."
	@make stop
	@sleep 2
	@make dev

# View logs from all services
logs:
	@echo "📋 Viewing logs from all services..."
	@echo "Use Ctrl+C to stop viewing logs"
	@echo ""
	@npx supabase logs &
	@docker-compose logs -f qdrant_db &
	@wait

# Reset everything to fresh state
clean:
	@echo "🧹 Cleaning all data and containers..."
	@read -p "This will delete ALL local data. Are you sure? (y/N) " -n 1 -r; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		echo ""; \
		echo "Stopping all services..."; \
		make stop; \
		echo "Removing Qdrant data..."; \
		docker-compose down -v; \
		echo "Resetting Supabase..."; \
		npx supabase db reset; \
		echo "✅ Clean complete. Run 'make dev' to restart."; \
	else \
		echo ""; \
		echo "❌ Clean cancelled."; \
	fi

# Show current environment configuration
env:
	@echo "🔧 Current Environment Configuration"
	@echo "==================================="
	@echo ""
	@if [ -f .env.local ]; then \
		echo "📄 Environment file: .env.local"; \
		echo ""; \
		grep -E '^[A-Z_]' .env.local | grep -v '_KEY' | grep -v '_SECRET' || true; \
		echo ""; \
		echo "🔐 API Keys configured:"; \
		grep -E 'API_KEY|SECRET|TOKEN' .env.local | sed 's/=.*/=***hidden***/' || echo "   No API keys found"; \
	else \
		echo "❌ No .env.local file found. Run 'make setup' first."; \
	fi

# Database operations
migrate:
	@echo "📊 Applying database migrations..."
	@npx supabase db push

db-reset:
	@echo "🗄️ Resetting database..."
	@npx supabase db reset

db-logs:
	@echo "📋 Database logs:"
	@npx supabase logs db

# Open Supabase Studio
studio:
	@echo "🎨 Opening Supabase Studio..."
	@open http://localhost:54323 || xdg-open http://localhost:54323 || echo "Open http://localhost:54323 in your browser"

# Run tests
test:
	@echo "🧪 Running tests..."
	@cd api && python -m pytest

# Quick status check
quick-status:
	@npx supabase status --output json | jq -r '.[] | select(.name == "API") | "Supabase: " + .status'
	@docker-compose ps --format "table {{.Service}}\t{{.Status}}" qdrant_db
	@curl -s http://localhost:8765/health | jq -r '"API: healthy"' || echo "API: not responding"
	@curl -s http://localhost:3000 > /dev/null && echo "UI: running" || echo "UI: not responding"
