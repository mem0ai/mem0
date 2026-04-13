.PHONY: up down clean logs seed wait-api wait-dashboard bootstrap health build run_local

EMAIL ?= admin@mem0.dev
PASSWORD ?= admin123456
NAME ?= Admin
OUTPUT ?= text
API_URL ?= http://localhost:8888
DASHBOARD_URL ?= http://localhost:3000

up:
	docker compose up -d --build

down:
	docker compose down

clean:
	docker compose down -v

logs:
	docker compose logs -f

seed:
	@API_URL="$(API_URL)" DASHBOARD_URL="$(DASHBOARD_URL)" EMAIL="$(EMAIL)" PASSWORD="$(PASSWORD)" NAME="$(NAME)" OUTPUT="$(OUTPUT)" ./scripts/seed.sh

wait-api:
	@echo "Waiting for API..."
	@until curl -fsS "$(API_URL)/auth/setup-status" >/dev/null; do sleep 2; done

wait-dashboard:
	@echo "Waiting for dashboard..."
	@until curl -fsS "$(DASHBOARD_URL)/api/health" >/dev/null; do sleep 2; done

bootstrap: up wait-api wait-dashboard seed

health:
	@echo "API:       $$(curl -s -o /dev/null -w '%{http_code}' "$(API_URL)/docs")"
	@echo "Dashboard: $$(curl -s -o /dev/null -w '%{http_code}' "$(DASHBOARD_URL)/api/health")"
	@echo "Postgres:  $$(docker compose exec -T postgres pg_isready -q && echo 'ok' || echo 'down')"

build:
	docker build -t mem0-api-server .

run_local:
	docker run -p 8000:8000 -v $(shell pwd):/app mem0-api-server --env-file .env
