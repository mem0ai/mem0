.PHONY: format sort lint

# Variables
RUFF_OPTIONS = --line-length 120
ISORT_OPTIONS = --profile black

# Default target
all: format sort lint

# Format code with ruff
format:
	poetry run ruff check . --fix $(RUFF_OPTIONS)

# Sort imports with isort
sort:
	poetry run isort . $(ISORT_OPTIONS)

# Lint code with ruff
lint:
	poetry run ruff check . $(RUFF_OPTIONS)

docs:
	cd docs && mintlify dev

build:
	poetry build

publish:
	poetry publish

clean:
	poetry run rm -rf dist
