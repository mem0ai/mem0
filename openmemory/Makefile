.PHONY: help setup up down logs shell migrate test clean env status restart restart-ui-local

NEXT_PUBLIC_USER_ID=$(USER)
NEXT_PUBLIC_API_URL=http://localhost:8765

# Default target
help:
	@echo "Jean Memory Development Commands:"
	@echo "  make up                - Start all services in Docker"
	@echo "  make backend           - Start only backend services in Docker"
	@echo "  make ui-local          - Run UI locally for faster development"
	@echo "  make down              - Stop all services"
	@echo "  make status            - Show status of all services"
	@echo "  make restart-backend   - Restart only the backend services"
	@echo "  make restart-ui-local  - Restart only the local UI (for development)"
	@echo "  make setup             - Initial setup of the project"
	@echo "  make help              - Show this help message"

# Complete setup for first time
setup:
	@echo "Setting up Jean Memory development environment..."
	@if [ ! -f ./api/.env ]; then cp ./api/env.example ./api/.env; echo "Created api/.env"; fi
	@if [ ! -f ./ui/.env.local ]; then cp ./ui/env.example ./ui/.env.local; echo "Created ui/.env.local"; fi
	@echo "Building Docker images..."
	@docker-compose build
	@echo "Setup complete! Run 'make up' to start services or 'make backend' followed by 'make ui-local' for hybrid mode."

# Start all services in Docker
up:
	@echo "Starting all services in Docker (full Docker mode)..."
	@docker-compose --profile full up -d
	@echo "Services started. Access UI at http://localhost:3000 and API at http://localhost:8765"

# Stop all services
down:
	@echo "Stopping all services..."
	@docker-compose --profile full down
	@echo "Stopping any local UI processes..."
	@pkill -f "npm run dev" || true

# Show status of all services
status:
	@echo "Docker services status:"
	@docker-compose ps
	@echo "\nUI local development status:"
	@ps aux | grep "npm run dev" | grep -v grep || echo "UI is not running locally"

# Restart only the backend
restart-backend:
	@echo "Restarting backend services..."
	@docker-compose restart api postgres_db qdrant_db

# Restart only the local UI
restart-ui-local:
	@echo "Restarting local UI development server..."
	@chmod +x ../scripts/local-dev/restart-ui-local.sh
	@../scripts/local-dev/restart-ui-local.sh

# Show logs
logs:
	docker-compose logs -f

# Open shell in API container
shell:
	docker-compose exec api /bin/bash || docker-compose exec api /bin/sh

# Run database migrations
migrate:
	docker-compose exec api alembic upgrade head

# Run tests
test:
	docker-compose exec api pytest

# Clean up all data and containers
clean:
	@echo "Cleaning up all data and containers..."
	@docker-compose --profile full down -v
	@echo "Stopping any local UI processes..."
	@pkill -f "npm run dev" || true
	@echo "Cleanup complete."

# View only API logs
logs-api:
	docker-compose logs -f api

# Run the UI locally (outside Docker) for faster development
ui-local:
	@echo "Starting UI locally for development..."
	@chmod +x ../scripts/local-dev/local-dev-ui.sh
	@../scripts/local-dev/local-dev-ui.sh

# Run only the backend services in Docker
backend:
	@echo "Starting only backend services in Docker..."
	@docker-compose up -d api postgres_db qdrant_db
