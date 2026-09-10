# Python CLI (`cli/python/`)

The `mem0-cli` package on PyPI. Typer-based, entry point `mem0`.

## Commands

```bash
pip install -e ".[dev]"   # dev install: ruff + pytest
ruff check .              # lint
ruff format .             # format
pytest                    # test
hatch build               # build
```

## Conventions

> **Line length is 100 here, not 120.** The root Python SDK uses 120. Running the root
> `make format` over this directory reformats every file and fails CI. Use the local
> `ruff` invocations above.

- **Python 3.10+.** Not 3.9, unlike the root SDK.
- **Ruff** with an extended rule set: `E`, `F`, `I`, `W`, `UP`, `B`, `SIM`, `RUF`.
  Ignores `E501` (formatter handles it), `B008` (required by Typer's argument defaults),
  and `SIM108`.
- **Ruff format:** double quotes, space indent, `docstring-code-format = true`.
- **isort** first-party is `mem0_cli` only.
- **pytest** for tests.
- Target version pinned to `py310`.

## Layout

```
cli/python/
├── src/mem0_cli/     package source (src layout)
└── tests/
```

Entry point: `mem0 = "mem0_cli.app:main"`.

## Dependencies

Typer + Rich + httpx. `mem0ai` is **optional**, exposed through the `[oss]` extra for OSS mode. Do not promote it to a required dependency.

## CI and release

- CI: `cli-python-ci.yml`, ruff + pytest + `hatch build` on Python 3.10, 3.11, 3.12.
- Release: tag prefix `cli-v*` dispatches `cli-python-cd.yml`, publishing to PyPI over OIDC.
