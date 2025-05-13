.PHONY: help up down logs shell migrate test test-clean env ui-install ui-start ui-dev

NEXT_PUBLIC_USER_ID=$(USER)
NEXT_PUBLIC_API_URL=http://localhost:8765

# Default target
help:
	@echo "Available commands:"
	@echo "  make env       - Copy .env.example to .env"
	@echo "  make up        - Start the containers"
	@echo "  make down      - Stop the containers"
	@echo "  make logs      - Show container logs"
	@echo "  make shell     - Open a shell in the api container"
	@echo "  make migrate   - Run database migrations"
	@echo "  make test      - Run tests in a new container"
	@echo "  make test-clean - Run tests and clean up volumes"
	@echo "  make ui-install - Install frontend dependencies"
	@echo "  make ui-start  - Start the frontend development server"
	@echo "  make ui    - Install dependencies and start the frontend"

env:
	cd api && cp .env.example .env

build:
	cd api && docker-compose build

up:
	cd api && docker-compose up

down:
	cd api && docker-compose down -v
	rm -f api/openmemory.db

logs:
	cd api && docker-compose logs -f

shell:
	cd api && docker-compose exec api bash

upgrade:
	cd api && docker-compose exec api alembic upgrade head

migrate:
	cd api && docker-compose exec api alembic upgrade head

downgrade:
	cd api && docker-compose exec api alembic downgrade -1

test:
	cd api && docker-compose run --rm api pytest tests/ -v

test-clean:
	cd api && docker-compose run --rm api pytest tests/ -v && docker-compose down -v

# Frontend commands
ui-install:
	cd ui && pnpm install

ui-build:
	cd ui && pnpm build

ui-start:
	cd ui && NEXT_PUBLIC_USER_ID=$(USER) NEXT_PUBLIC_API_URL=$(NEXT_PUBLIC_API_URL) pnpm start

ui-dev-start:
	cd ui && NEXT_PUBLIC_USER_ID=$(USER) NEXT_PUBLIC_API_URL=$(NEXT_PUBLIC_API_URL) && pnpm dev

ui-dev: ui-install ui-dev-start

ui: ui-install ui-build ui-start