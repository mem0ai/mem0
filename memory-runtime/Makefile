.PHONY: install-dev run run-worker run-worker-once test test-unittest lint format smoke test-e2e pilot-smoke quality-eval reset-pilot show-last-smoke show-last-quality-eval

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

quality-eval:
	bash scripts/openclaw_quality_eval.sh

reset-pilot:
	bash scripts/openclaw_reset_pilot.sh

show-last-smoke:
	bash scripts/show_last_report.sh smoke

show-last-quality-eval:
	bash scripts/show_last_report.sh quality

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
