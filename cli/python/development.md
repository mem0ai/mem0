# Development

## Prerequisites

- Python **3.10+**
- `make` (optional — you can use plain Python commands instead)

All commands below should be run from the `python/` directory:

```bash
cd python
```

## Setup

### Using Make (recommended)

All `make` targets automatically create a virtual environment (`.venv/`) and install the required dependencies — no manual setup needed.

```bash
# Install the CLI in editable mode
make install

# Install with dev tools (tests + linting)
make dev
```

### Using Python directly

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip

# Install in editable mode
pip install -e .

# With dev tools
pip install -e ".[dev]"
```

## Make targets

| Target              | Description                                      |
| ------------------- | ------------------------------------------------ |
| `make install`      | Create venv and install the CLI (editable mode)  |
| `make dev`          | Create venv and install CLI + dev dependencies   |
| `make test`         | Run all tests (installs dev deps if needed)      |
| `make lint`         | Run linter and format check                      |
| `make format`       | Auto-fix lint issues and format code             |
| `make build`        | Build distribution packages                      |
| `make clean`        | Remove `dist/`                                   |
| `make publish`      | Build and publish to PyPI                        |
| `make publish-test` | Build and publish to Test PyPI                   |
| `make shell`        | Open a new shell with the venv activated         |

## Run tests

```bash
# Using Make
make test

# Using Python directly
pytest

# Run a specific test file
pytest tests/test_cli_integration.py

# Run a single test
pytest -k test_help
```

## Run the CLI

```bash
# Using Make — drop into an activated shell
make shell
mem0 --help

# Using Python directly (with venv activated)
source .venv/bin/activate
mem0 --help
mem0 version

# Or run without activating
.venv/bin/mem0 --help
```

## Lint

```bash
# Using Make
make lint      # check only
make format    # auto-fix

# Using Python directly (with venv activated)
ruff check .
ruff format .
```

## Optional extras

### OSS integration

```bash
pip install -e ".[oss]"
```
