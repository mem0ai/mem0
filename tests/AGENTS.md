# Python SDK tests (`tests/`)

pytest suite for the `mem0/` package.

## Commands

```bash
make install_all    # optional deps; several tests need them
make test           # pytest tests/
make test-py-3.9    # pin a Python version (3.9 through 3.12)

pytest tests/llms/test_openai.py::test_generate_response   # single test
```

## Conventions

- Files are named `test_<module>.py`.
- Provider tests mirror the source tree: `tests/<category>/<provider_name>/`.
- pytest-mock for mocks, pytest-asyncio for the async surface.
- Ruff line length **120**, matching `mem0/`. See [`../mem0/AGENTS.md`](../mem0/AGENTS.md).
- Mock the provider SDK, never the code under test. A test that asserts the implementation back at itself is worse than no test.
- Bug fixes need a regression test that fails without the fix. Write it first and watch it fail.

Tests for other packages live with those packages: `mem0-ts/` (jest), `cli/python/tests/` (pytest), `cli/node/` (vitest), and each directory under `integrations/`.
