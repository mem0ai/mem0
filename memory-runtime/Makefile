.PHONY: install-dev run run-worker run-worker-once test test-unittest lint format smoke test-e2e pilot-smoke

PYTHON ?= python3
PORT ?= 8080

install-dev:
	$(PYTHON) -m pip install -e '.[dev]'

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port $(PORT)

run-worker:
	$(PYTHON) -m app.workers.main

run-worker-once:
	$(PYTHON) -m app.workers.main --once

test:
	$(PYTHON) -m pytest tests

test-e2e:
	$(PYTHON) -m pytest tests/e2e

pilot-smoke:
	bash scripts/openclaw_pilot_smoke.sh

test-unittest:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v

lint:
	$(PYTHON) -m ruff check .

format:
	$(PYTHON) -m ruff format .

smoke:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v

migrate:
	.venv/bin/alembic upgrade head
