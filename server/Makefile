.PHONY: up down clean logs seed wait-api wait-dashboard bootstrap health build run_local reset-admin-password prune-logs

OUTPUT ?= text
API_URL ?= http://localhost:8888
DASHBOARD_URL ?= http://localhost:3000

up:
	@for port in 3000 8888; do \
		if lsof -iTCP:$$port -sTCP:LISTEN >/dev/null 2>&1; then \
			echo "error: port $$port is already in use."; \
			echo "find the owning process with: lsof -iTCP:$$port -sTCP:LISTEN"; \
			exit 1; \
		fi; \
	done
	docker compose up -d --build
	@$(MAKE) --no-print-directory wait-api
	@$(MAKE) --no-print-directory wait-dashboard
	@echo ""
	@echo "Stack is ready."
	@echo "  Dashboard:  $(DASHBOARD_URL)  <- open this to run the setup wizard"
	@echo "  API:        $(API_URL)"

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
	@until curl -fsS "$(API_URL)/auth/setup-status" >/dev/null 2>&1; do sleep 2; done

wait-dashboard:
	@echo "Waiting for dashboard..."
	@until curl -fsS "$(DASHBOARD_URL)/api/health" >/dev/null 2>&1; do sleep 2; done

bootstrap: up wait-api wait-dashboard seed

health:
	@echo "API:       $$(curl -s -o /dev/null -w '%{http_code}' "$(API_URL)/docs")"
	@echo "Dashboard: $$(curl -s -o /dev/null -w '%{http_code}' "$(DASHBOARD_URL)/api/health")"
	@echo "Postgres:  $$(docker compose exec -T postgres pg_isready -q && echo 'ok' || echo 'down')"

reset-admin-password:
	@test -n "$(EMAIL)" || (echo "usage: make reset-admin-password EMAIL=<email> PASSWORD=<password>" && exit 2)
	@test -n "$(PASSWORD)" || (echo "usage: make reset-admin-password EMAIL=<email> PASSWORD=<password>" && exit 2)
	@docker compose exec -T -e EMAIL="$(EMAIL)" -e PASSWORD="$(PASSWORD)" -e PYTHONPATH=/app mem0 python scripts/reset_admin_password.py

prune-logs:
	@docker compose exec -T -e REQUEST_LOG_RETENTION_DAYS="$(REQUEST_LOG_RETENTION_DAYS)" -e PYTHONPATH=/app mem0 python scripts/prune_request_logs.py

build:
	docker build -t mem0-api-server .

run_local:
	docker run -p 8000:8000 -v $(shell pwd):/app mem0-api-server --env-file .env
