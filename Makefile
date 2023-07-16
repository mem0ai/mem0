# Variables
PYTHON := python3
PIP := $(PYTHON) -m pip
PROJECT_NAME := embedchain

# Targets
.PHONY: install format lint clean test ci_lint ci_test

install:
	$(PIP) install --upgrade pip
	$(PIP) install -e .[dev]

format:
	$(PYTHON) -m black .
	$(PYTHON) -m isort .

lint:
	$(PYTHON) -m ruff .

clean:
	rm -rf dist build *.egg-info

test:
	$(PYTHON) -m pytest

ci_lint:
	poetry run ruff .

ci_test:
	poetry run pytest
