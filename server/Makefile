.PHONY: up down clean logs seed health build run_local

up:
	docker compose up -d --build

down:
	docker compose down

clean:
	docker compose down -v

logs:
	docker compose logs -f

seed:
	./scripts/seed.sh

health:
	@echo "API:       $$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8888/docs)"
	@echo "Dashboard: $$(curl -s -o /dev/null -w '%{http_code}' http://localhost:3000/api/health)"
	@echo "Postgres:  $$(docker compose exec -T postgres pg_isready -q && echo 'ok' || echo 'down')"

build:
	docker build -t mem0-api-server .

run_local:
	docker run -p 8000:8000 -v $(shell pwd):/app mem0-api-server --env-file .env
