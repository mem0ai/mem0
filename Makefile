.PHONY: format sort lint zvec-integration-setup zvec-integration-test zvec-integration-clean zvec-local-e2e-setup zvec-local-e2e-test e2e-zvec

# Variables
ISORT_OPTIONS = --profile black
PROJECT_NAME := mem0ai
ZVEC_PYTHON := 3.12
ZVEC_VENV := .venv-zvec
ZVEC_LOCAL_MODEL ?= /Users/dgordon/models/bge-large-en-v1.5

# Default target
all: format sort lint

install:
	hatch env create

install_all:
	pip install ruff==0.6.9 groq together boto3 litellm ollama chromadb weaviate weaviate-client sentence_transformers vertexai \
	            google-generativeai elasticsearch opensearch-py vecs "pinecone<7.0.0" pinecone-text faiss-cpu langchain-community \
							upstash-vector azure-search-documents langchain-memgraph langchain-neo4j langchain-aws rank-bm25 pymochow pymongo psycopg kuzu databricks-sdk valkey

# Format code with ruff
format:
	hatch run format

# Sort imports with isort
sort:
	hatch run isort mem0/

# Lint code with ruff
lint:
	hatch run lint

docs:
	cd docs && mintlify dev

build:
	hatch build

publish:
	hatch publish

clean:
	rm -rf dist

test:
	hatch run test

test-py-3.9:
	hatch run dev_py_3_9:test

test-py-3.10:
	hatch run dev_py_3_10:test

test-py-3.11:
	hatch run dev_py_3_11:test

test-py-3.12:
	hatch run dev_py_3_12:test

zvec-integration-setup:
	UV_PROJECT_ENVIRONMENT=$(ZVEC_VENV) uv sync --python $(ZVEC_PYTHON) --extra test
	UV_PROJECT_ENVIRONMENT=$(ZVEC_VENV) uv pip install --python $(ZVEC_VENV)/bin/python "zvec>=0.2.0"

zvec-integration-test:
	UV_PROJECT_ENVIRONMENT=$(ZVEC_VENV) uv run --python $(ZVEC_PYTHON) pytest tests/vector_stores/test_zvec_integration.py -q

zvec-integration-clean:
	rm -rf $(ZVEC_VENV)

zvec-local-e2e-setup: zvec-integration-setup
	UV_PROJECT_ENVIRONMENT=$(ZVEC_VENV) uv pip install --python $(ZVEC_VENV)/bin/python "sentence-transformers>=5.0.0"

zvec-local-e2e-test:
	MEM0_ZVEC_LOCAL_E2E=1 MEM0_ZVEC_LOCAL_MODEL=$(ZVEC_LOCAL_MODEL) UV_PROJECT_ENVIRONMENT=$(ZVEC_VENV) uv run --python $(ZVEC_PYTHON) pytest tests/vector_stores/test_zvec_local_e2e.py -q

e2e-zvec: zvec-local-e2e-setup
	MEM0_ZVEC_LOCAL_E2E=1 MEM0_ZVEC_LOCAL_MODEL=$(ZVEC_LOCAL_MODEL) UV_PROJECT_ENVIRONMENT=$(ZVEC_VENV) uv run --python $(ZVEC_PYTHON) pytest tests/vector_stores/test_zvec.py tests/vector_stores/test_zvec_integration.py tests/vector_stores/test_zvec_local_e2e.py -q
