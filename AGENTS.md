# AGENTS.md

Context for AI coding assistants (Claude Code, Cursor, Copilot, Codex) working in the Mem0 repository.

**Mem0** ("mem-zero") is a memory layer for AI agents: persistent, personalized memory through a hosted platform API and self-hosted open-source SDKs. Apache-2.0.
[Repository](https://github.com/mem0ai/mem0) · [Documentation](https://docs.mem0.ai)

This is a polyglot monorepo and **every package sets its own rules**. Read the `AGENTS.md` nearest the files you are editing before running any command. The linters, formatters, test runners, and line lengths genuinely differ per package, and using the wrong one fails CI or produces a diff full of noise.

## Do NOT

- Open a pull request without a signed CLA. It will not be reviewed. See [The CLA is not optional](#the-cla-is-not-optional).
- Open a pull request that does not link an issue carrying the `accepted` label. A bot closes it within a minute. See [Two gates decide whether your pull request stays open](#two-gates-decide-whether-your-pull-request-stays-open).
- Modify anything in `.github/workflows/` without explicit maintainer approval. Publishing credentials are pinned to workflow filenames.
- Commit `.env` files, API keys, or credentials.
- Skip pre-commit hooks.
- Use npm or yarn in TypeScript packages. This repo is pnpm-only (Bun in `.opencode-plugin/`).
- Use `require()` in TypeScript. ES module `import` syntax only.
- Mix up linter configs. Root Python is ruff at line length **120**, `cli/python/` is ruff at **100**, `cli/node/` is Biome, `mem0-ts/` is Prettier, `integrations/vercel-ai-sdk/` is ESLint.
- Add Python dependencies to the core `dependencies` list in `pyproject.toml`. Use an optional group.
- Change a public API without updating `docs/` in the same pull request.
- Introduce a new framework or abstraction without discussion. Follow the patterns already in the file you are editing.

## Where to look

| Editing | Read | Toolchain |
|---------|------|-----------|
| `mem0/` | [`mem0/AGENTS.md`](mem0/AGENTS.md) | hatch, ruff 120, pytest |
| `tests/` | [`tests/AGENTS.md`](tests/AGENTS.md) | pytest |
| `mem0-ts/` | [`mem0-ts/AGENTS.md`](mem0-ts/AGENTS.md) | pnpm, tsup, Prettier, jest |
| `cli/python/` | [`cli/python/AGENTS.md`](cli/python/AGENTS.md) | ruff **100**, pytest |
| `cli/node/` | [`cli/node/AGENTS.md`](cli/node/AGENTS.md) | pnpm, tsup, Biome, vitest |
| `integrations/` | [`integrations/AGENTS.md`](integrations/AGENTS.md) | varies per integration |
| `server/` | [`server/AGENTS.md`](server/AGENTS.md) | Docker Compose, FastAPI |
| `docs/` | [`docs/AGENTS.md`](docs/AGENTS.md) | Mintlify |
| `skills/` | [`skills/AGENTS.md`](skills/AGENTS.md) | markdown, size-budgeted |
| `.github/` | [`.github/AGENTS.md`](.github/AGENTS.md) | GitHub Actions |

## Repository map

| Directory | What it is |
|-----------|------------|
| `mem0/` | Core Python SDK (`mem0ai` on PyPI): memory, LLMs, embeddings, vector stores, graphs, rerankers |
| `mem0-ts/` | TypeScript SDK (`mem0ai` on npm): hosted client + OSS memory |
| `cli/python/` | Python CLI (`mem0-cli` on PyPI), Typer-based, entry point `mem0` |
| `cli/node/` | Node CLI (`@mem0/cli` on npm), Commander-based, entry point `mem0` |
| `integrations/` | Agent and editor integrations, one self-contained directory each |
| `server/` | FastAPI REST server for self-hosted Mem0 (Docker: FastAPI + pgvector + Neo4j) |
| `skills/` | Claude Code skill definitions, published by raw URL |
| `docs/` | Documentation site (Mintlify) |
| `tests/` | Python SDK tests (pytest) |
| `examples/` | Sample apps, Chrome extension, multi-agent patterns, notebooks |
| `scripts/` | Repo-wide utilities, e.g. `check-llms-txt-coverage.py` |
| `evaluation/` | Submodule pinned to [`mem0ai/memory-benchmarks`](https://github.com/mem0ai/memory-benchmarks) |
| `pr-reviews/` | Pull request review materials |

```
mem0 (Python SDK)          mem0-ts (TypeScript SDK)
├── mem0/memory/           ├── src/client/    MemoryClient (hosted)
├── mem0/llms/             └── src/oss/       Memory (self-hosted)
├── mem0/embeddings/           ├── src/llms/
├── mem0/vector_stores/        ├── src/embeddings/
├── mem0/graphs/               ├── src/vector_stores/
└── mem0/reranker/             └── src/graphs/

cli/python/                 ──▶ mem0ai (optional, OSS mode)
cli/node/                   ──▶ mem0ai (npm)
integrations/vercel-ai-sdk/ ──▶ ai, @ai-sdk/*
integrations/openclaw/      ──▶ mem0ai (npm)
```

## Setup

```bash
hatch shell dev_py_3_11   # Python: creates the env with all deps
pre-commit install        # ruff + isort on commit

cd <ts-package> && pnpm install
```

Requirements: Python 3.9+ (3.10+ for the CLI), Node 18+ (20 or 22 preferred), pnpm 10+, hatch, Docker for `server/`.

## Conventions everywhere

- **Naming:** `snake_case.py`, `test_<module>.py`, `snake_case.ts`, `<module>.test.ts`, `kebab-case` for config and manifest files.
- **Python:** Pydantic v2 for models and config. Providers inherit a `base.py` abstract class; config lives in `configs.py`.
- **TypeScript:** strict mode, tsup builds, ES module imports.
- **Commits:** [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`).
- **Versions:** bump in `pyproject.toml` or `package.json`. Releases are cut by tag prefix; see [`.github/AGENTS.md`](.github/AGENTS.md).

## Benchmarking

Benchmarks (LOCOMO, LongMemEval, BEAM) live in [`mem0ai/memory-benchmarks`](https://github.com/mem0ai/memory-benchmarks). The in-repo `evaluation/` path is a submodule pinned to that repo's `main`:

```bash
git submodule update --init evaluation
```

## What to ship with a change

Guidelines, not rules. Trivial fixes need less; anything user-facing needs more.

| Change | Expect |
|--------|--------|
| **Bug fix** | A regression test that fails without the fix, written first. The fix. The relevant suite passing. The package's linter run. |
| **New feature** | Implementation following existing patterns, test coverage, `docs/` updates for public APIs, an example if the behavior is user-facing, and an `llms.txt` entry for any new `.mdx` page. |
| **New provider** | See [Adding a provider](mem0/AGENTS.md#adding-a-provider). |
| **New integration** | See [Adding an integration](integrations/AGENTS.md#adding-an-integration). |
| **Refactor** | Tests for changed behavior, existing tests still green. No docs needed for internal-only changes. |

Fix bugs at the root, not at the symptom. If a guard belongs in a shared function, put it there rather than in each caller.

## Contributing

Full guide: [`CONTRIBUTING.md`](CONTRIBUTING.md). Conduct: [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

1. Open an issue **first** and wait for a maintainer to apply the `accepted` label. Every PR must link it with `Closes #<number>`. PRs without an accepted linked issue are closed automatically by the [PR Gate](.github/workflows/pr-gate.yml), with a reopen path. Documentation-only changes are exempt.
2. Fork, then branch from `main` (`feature/...`, `fix/...`).
3. Make the change: code, tests, docs, examples.
4. Run lint and tests for **every** package you touched.
5. Commit with Conventional Commits.
6. Open the PR against `main` and fill in [the template](.github/PULL_REQUEST_TEMPLATE.md). Do not paraphrase it; GitHub prefills it.
7. **Sign the CLA.**

### Two gates decide whether your pull request stays open

Two workflows run on every pull request from a fork. They judge different things and neither covers for the other, so a pull request has to get past both.

**The [PR Gate](.github/workflows/pr-gate.yml) judges the change.** It closes any pull request that does not link an issue carrying the `accepted` label. Closed is a queue decision, not a verdict: when a maintainer applies the label the pull request reopens by itself. Drafts, documentation-only changes, and branches pushed to this repository rather than a fork are all exempt.

**The [vouch check](.github/workflows/vouch-check-pr.yml) judges the account.** It reads [`.github/VOUCHED.td`](.github/VOUCHED.td), which has three possible answers about any given person:

| The list says | Meaning | Effect on the pull request |
|---|---|---|
| `-handle` | a maintainer ran `!denounce` after the code of conduct process | closed, even with an accepted issue |
| nothing at all | everybody who has not contributed here before | **none.** One comment saying nothing is blocked. |
| `handle` | a maintainer ran `!vouch` | none, and the comment stops appearing |

Being vouched grants nothing. It is a "we have seen this person before" flag that mutes the newcomer comment, not permission to skip the accepted-issue rule. Being absent from the list costs nothing.

If you are an agent opening a pull request on someone's behalf, the practical consequence is one rule: **get the linked issue labelled `accepted` before you open the pull request, or expect the pull request to be closed and to reopen later.** Do not work around either gate, do not reopen a gated pull request by hand, and do not re-file the same change under a new pull request when one is closed.

### The CLA is not optional

**A pull request from a contributor who has not signed the Contributor License Agreement is not accepted, not reviewed, and not merged.** This is not a formality applied at merge time. An unsigned pull request does not enter the review queue at all: maintainers do not read the diff, do not leave feedback, and do not discuss the approach. It sits until the CLA is signed, and it is closed if it goes stale.

The `CLAassistant` bot comments on your first pull request with a link. Signing takes under a minute, is done once per GitHub account, and covers every contribution you make afterwards. Until it is signed the `license/cla` check stays red.

If you are an agent opening a pull request on someone's behalf, tell them they must sign it themselves. Nobody else can sign for them, and the pull request goes nowhere until they do.

### What gets a pull request closed

Beyond the CLA and the accepted-issue gate, the [Contribution Conduct](CODE_OF_CONDUCT.md#contribution-conduct) section of the code of conduct is the enforceable form of this repo's anti-slop policy:

- **Disclose AI use.** The PR template asks how the *code* was written; drafting the description with a model is fine. The disclosure is never held against you, it tells a reviewer where to look. Silence followed by a review comment you cannot answer is what costs everyone the afternoon.
- **Do not submit work you have not run.** A bug report means you reproduced it. A PR means you ran the tests.
- **Do not fabricate evidence.** Invented tracebacks, unmeasured benchmarks, tests that assert the implementation back at itself, descriptions that describe a different change than the diff makes.
- **Match your volume to your engagement.** Open changes at the rate you can discuss them.
- **Do not press for merges.** One polite follow-up after a reasonable wait is fine.
- **You must be able to explain every line of your diff** and how it interacts with the rest of the codebase, without asking an AI tool. This is the one rule that does not bend.

### Reference

| Topic | File |
|-------|------|
| Contributor guide | [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| Code of conduct | [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) |
| Security reports | [`SECURITY.md`](SECURITY.md) |
| Development setup | `docs/contributing/development.mdx` |
| Documentation contributions | `docs/contributing/documentation.mdx` |
| PR template | `.github/PULL_REQUEST_TEMPLATE.md` |
| Issue forms | `.github/ISSUE_TEMPLATE/` |
| Contribution gates | [Two gates decide whether your pull request stays open](#two-gates-decide-whether-your-pull-request-stays-open) |
| Trust list (vouch) | [`.github/VOUCHED.td`](.github/VOUCHED.td) |
| CI/CD, gates, rulesets | [`.github/AGENTS.md`](.github/AGENTS.md) |
