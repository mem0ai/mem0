.PHONY: install dev lint format test build clean publish publish-test

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

lint:
	ruff check .
	ruff format --check .

format:
	ruff check --fix .
	ruff format .

test:
	pytest

build: clean
	hatch build

clean:
	rm -rf dist/

publish: build
	hatch publish

publish-test: build
	hatch publish --repo test
