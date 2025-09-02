# Repository Guidelines

## Project Structure & Module Organization
- `mem0/`: Python core library (packaged via Hatch).
- `server/`: FastAPI REST API (Docker-ready). OpenAPI at `/docs`.
- `mem0-ts/`: TypeScript/Node SDK (pnpm + Jest).
- `tests/`: Python tests (pytest).
- `docs/`, `examples/`, `cookbooks/`: Usage and reference materials.

## Build, Test, and Development Commands
- Python setup: `make install` (creates Hatch env). Optional: `pip install -e .[dev]`.
- Format/Lint: `make format` (ruff fmt), `make sort` (isort), `make lint` (ruff check).
- Test (Python): `make test` or `make test-py-3.11` (per-version).
- Build (Python pkg): `make build`.
- API server: `cd server && make build && make run_local` (Docker) or `uvicorn server.main:app --reload`.
- TypeScript SDK: `cd mem0-ts && pnpm i && pnpm build && pnpm test` (Node ≥18).

## Coding Style & Naming Conventions
- Python: 4-space indent, type hints; Ruff line length 120; isort `--profile black`.
  - Naming: `snake_case` for modules/functions, `PascalCase` for classes, `UPPER_SNAKE` for constants.
- TypeScript: Prettier enforced by `pnpm build`; favor `camelCase` for functions/vars and `PascalCase` for types/classes.

## Testing Guidelines
- Python: pytest in `tests/` with `test_*.py` naming. Cover new public functions and critical paths; add regression tests for bug fixes.
- TypeScript: Jest in `mem0-ts/tests`. Use focused unit tests; mock network calls.
- Run tests locally before opening a PR: `make test` and `pnpm -C mem0-ts test`.

## Commit & Pull Request Guidelines
- Commits: use conventional prefixes (e.g., `feat:`, `fix:`, `docs:`, `refactor:`). Example: `docs: add branching strategy`.
- Branching: create topic branches from `custom` (e.g., `feature/<short-topic>`). Do not commit directly to `main`.
- PRs: target `custom`. Include a clear summary, motivation, and testing notes; link related issues; add screenshots for UI-related changes (if any).
- CI/readiness: code formatted and lint-clean; tests pass.

## Branching & Upstream Sync
- `main`: mirror of `upstream/main` (fast-forward only).
- `custom`: long-lived branch carrying our private patches; default PR target.
- Topic branches: `feature/<short-topic>` from `custom`.
- Sync flow: `git fetch upstream && git checkout main && git pull --ff-only upstream main && git push origin main` then `git checkout custom && git rebase main` (or `git merge --no-ff main`). Force-push to `custom` after rebase.
- Full policy: see `docs/branching-strategy.md`.

## Security & Configuration Tips
- Do not commit secrets. Use environment variables; see `server/.env.example`.
- For local server, set `OPENAI_API_KEY` and backing store credentials (Postgres/Neo4j) via `.env`.
