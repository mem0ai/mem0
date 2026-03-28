VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: install dev lint format test build clean publish publish-test shell

$(VENV)/bin/activate:
	python3 -m venv $(VENV)
	$(PIP) install -U pip

install: $(VENV)/bin/activate
	$(PIP) install -e .

dev: $(VENV)/bin/activate
	$(PIP) install -e ".[dev]"

lint: dev
	$(VENV)/bin/ruff check .
	$(VENV)/bin/ruff format --check .

format: dev
	$(VENV)/bin/ruff check --fix .
	$(VENV)/bin/ruff format .

test: dev
	$(VENV)/bin/pytest

build: clean $(VENV)/bin/activate
	$(PIP) install hatch
	$(VENV)/bin/hatch build

clean:
	rm -rf dist/

publish: build
	$(VENV)/bin/hatch publish

publish-test: build
	$(VENV)/bin/hatch publish --repo test

shell: $(VENV)/bin/activate
	@echo "Spawning a new shell with the virtual environment activated..."
	@VIRTUAL_ENV=$(CURDIR)/$(VENV) PATH=$(CURDIR)/$(VENV)/bin:$$PATH exec $(SHELL)
