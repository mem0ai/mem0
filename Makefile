.PHONY: format sort lint

# Variables
ISORT_OPTIONS = --profile black
PROJECT_NAME := mem0ai

# Default target
all: format sort lint

install:
	poetry install

install_all:
	poetry install
	poetry run pip install groq together boto3 litellm ollama chromadb sentence_transformers vertexai \
	                        google-generativeai

# Format code with ruff
format:
	poetry run ruff format mem0/

# Sort imports with isort
sort:
	poetry run isort mem0/

# Lint code with ruff
lint:
	poetry run ruff check mem0/

docs:
	cd docs && mintlify dev

build:
	poetry build

publish:
	poetry publish

clean:
	poetry run rm -rf dist

test:
	poetry run pytest tests
