.PHONY: help env build up down restart logs shell upgrade migrate downgrade test test-clean ui-install ui-start ui-dev ui-build ui-dev-start clean backup restore

# Default target
help:
	@echo "Available commands:"
	@echo "  make env       - Copy .env.example to .env"
	@echo "  make build      - Build the images"
	@echo "  make up         - Start the containers (foreground logs)"
	@echo "  make down       - Stop the containers (non-destructive)"
	@echo "  make restart    - Restart the containers (down + up)"
	@echo "  make logs       - Show container logs"
	@echo "  make shell      - Open a shell in the api container"
	@echo "  make upgrade    - Run database upgrades"
	@echo "  make migrate    - Run database migrations"
	@echo "  make downgrade  - Downgrade database migrations"
	@echo "  make test       - Run tests in a new container"
	@echo "  make test-clean - Run tests and clean up volumes"
	@echo "  make ui-install - Install frontend dependencies"
	@echo "  make ui-start   - Start the frontend development server"
	@echo "  make ui-dev     - Install dependencies and start frontend in dev mode"
	@echo "  make ui-build   - Build the frontend"
	@echo "  make ui-dev-start - Start frontend in dev mode"
	@echo "  make clean      - Full cleanup (containers, volumes, images)"
	@echo "  make backup     - Backup Qdrant + Postgres volumes"
	@echo "  make restore    - Restore from paired backup"

env:
	cp .env.example .env
	cp api/.env.example api/.env
	cp ui/.env.example ui/.env

build:
	docker compose build

up:
	docker compose up

down:
	docker compose down

restart: down up

logs:
	docker compose logs -f

shell:
	docker compose exec api sh

upgrade:
	docker compose exec api alembic upgrade head

migrate:
	docker compose exec api alembic upgrade head

downgrade:
	docker compose exec api alembic downgrade -1

test:
	docker compose run --rm api pytest

test-clean:
	docker compose run --rm api pytest
	docker compose down -v

ui-install:
	cd ui && pnpm install

ui-start:
	cd ui && pnpm start

ui-dev:
	cd ui && NEXT_PUBLIC_USER_ID=$(USER) pnpm install && pnpm dev

ui-build:
	cd ui && pnpm build

ui-dev-start:
	cd ui && NEXT_PUBLIC_USER_ID=$(USER) pnpm dev

clean:
	docker compose down -v
	docker volume rm openmemory openmemory_postgres || true
	docker image prune -f
	rm -f api/openmemory.db

# === Backup & Restore ===
backup:
	./backup.sh

restore:
	./restore.sh