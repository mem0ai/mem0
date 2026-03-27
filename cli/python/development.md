# Development

## Prerequisites

- Python **3.10+**

## Setup

All commands below should be run from the `python/` directory:

```bash
cd python
```

## Install local (editable) + run

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip

# Install in editable mode
pip install -e .

# Run
mem0 --help
mem0 version
```

> **After moving to the monorepo structure:** If you previously had the CLI installed from the old repo root, you need to re-run `pip install -e .` from inside the `python/` directory to pick up the new location.

## Run without installing globally

This still installs the package into your active virtualenv (editable), but you can invoke it via module execution:

```bash
source .venv/bin/activate
pip install -e .
python -m mem0_cli --help
```

## Optional extras

### OSS integration extras

```bash
pip install -e ".[oss]"
```

### Dev tools (tests/lint)

```bash
pip install -e ".[dev]"
```

## Run tests

```bash
pip install -e ".[dev]"

# Run all tests
pytest

# Run a specific test file
pytest tests/test_cli_integration.py

# Run a single test
pytest -k test_help
```

## Lint

```bash
ruff check .
ruff format .
```
