.PHONY: install-dev run test test-unittest lint format smoke

PYTHON ?= python3
PORT ?= 8080

install-dev:
	$(PYTHON) -m pip install -e '.[dev]'

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port $(PORT)

test:
	$(PYTHON) -m pytest tests

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
