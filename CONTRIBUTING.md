# Contributing to Mem0

First off, thank you for taking the time to contribute! 🎉 Mem0 is a
community-driven project and we welcome contributions of all kinds — bug fixes,
new features, documentation, examples, and integrations.

Mem0 is a polyglot monorepo, and this guide covers contributing to both the
**Python SDK** and the **TypeScript SDK** (and the rest of the repository).

By participating you agree to our [Code of Conduct](./CODE_OF_CONDUCT.md). Its
**Contribution Conduct** section is the enforceable form of the rules on this
page: disclose AI use, don't submit work you haven't run, don't fabricate
reproductions or benchmarks, keep your volume matched to your engagement, and
don't press for merges.

## Before You Start

### 1. Open an Issue First

**Always open an issue before opening a pull request.** This lets us discuss the
change, avoid duplicate effort, and agree on the approach before you invest time
in code.

- Search [existing issues](https://github.com/mem0ai/mem0/issues) first to see if
  your bug or idea already exists.
- If it doesn't, open a
  [bug report](https://github.com/mem0ai/mem0/issues/new?template=bug_report.yml) or
  [feature request](https://github.com/mem0ai/mem0/issues/new?template=feature_request.yml).
- For anything beyond a trivial fix, wait for a maintainer to confirm the approach
  before starting significant work.

A bug report needs a reproduction we can run, the version you are on, and the
real output or traceback you saw. Reports without those cannot be acted on and
get closed. A feature request needs the problem you hit and the workaround you
are living with, not just the API you would like.

Every pull request must link to an issue using `Closes #<issue-number>`, and that
issue must carry the `accepted` label. A maintainer applies `accepted` once we
agree the change is one we want.

Pull requests that don't link an accepted issue are closed automatically by the
[PR Gate](./.github/workflows/pr-gate.yml). **Closed does not mean rejected.** It
means the change isn't in the queue yet. Once a maintainer labels the issue the
pull request reopens itself, and you don't have to do anything. Documentation-only
changes skip the gate entirely.

A second check looks at who opened the pull request rather than what it changes.
If you are not yet in this repo's contributor list
([`.github/VOUCHED.td`](./.github/VOUCHED.td)) you get one comment saying so.
**Nothing is blocked and there is nothing you need to do.** A maintainer can add
you by commenting `!vouch @you` on any issue, which only stops that comment from
appearing again. Being on the list is not permission to skip the accepted-issue
rule, and being absent from it costs you nothing.

The list has a negative side too. A maintainer can `!denounce` an account that
has been through the
[code of conduct](./CODE_OF_CONDUCT.md#contribution-conduct) enforcement process,
and pull requests from that account are closed whether or not they link an
accepted issue. This is rare, it is never where anyone starts, and it is
reversible.

Security fixes are the one exception, and they don't go through public pull
requests at all. Follow the [Security Policy](./SECURITY.md) instead, which uses
a private advisory and a private fork so the vulnerability isn't disclosed before
the fix ships.

### 2. Understand Your Code

**You must be able to explain what your changes do and how they interact with
the rest of the codebase without the help of an AI tool.** This is the one rule
we will not bend on.

Using AI to write code is fine. Most of us do. You can build real understanding
by interrogating an agent about this codebase until you grasp the edge cases and
the blast radius of your change. What is not fine is opening a pull request for
a diff you cannot defend in review.

Disclose it in the pull request template and say what you checked yourself.
We ask about the code, not the write-up: using AI to draft the pull request
description is fine. We ask because it tells reviewers where to look, not
because it counts against you. An honest "an agent wrote this, here is what I
verified" is welcome. Silence, followed by a review comment you cannot answer,
is what wastes everyone's time.

Signs your pull request will be closed:

- Invented APIs, config keys, or providers that don't exist in this repo.
- Tests that assert the implementation back at itself rather than the behaviour.
- A description that describes a different change than the diff makes.
- Sweeping unrelated reformatting bundled with a small fix.
- You cannot answer a direct question about your own diff.

### 3. Sign the Contributor License Agreement (CLA)

**We cannot accept or merge any pull request until you have signed our Contributor
License Agreement (CLA).**

When you open your first PR, the CLA bot will automatically comment with a link to
sign. Signing takes less than a minute and only needs to be done once. Pull
requests from contributors who have not signed the CLA will be blocked from
merging.

## First Contribution Fast Path

Fixing a typo or a small docs issue? You don't need the full workflow below.

1. **Pick something small.** Look for issues labeled `documentation` or `good first issue`, or a typo/broken link you noticed while reading the docs.
2. **Branch from `main`** with a name that says what you're fixing, e.g. `docs/fix-quickstart-typo` or `fix/broken-crewai-link`.
3. **Make the change, then run only what applies:**
   - Docs-only change (`docs/**`): preview with `make docs`. If you added or removed an `.mdx` page, run `python scripts/check-llms-txt-coverage.py --write` so `docs/llms.txt` stays in sync.
   - Code change: run the linter and tests for the package you touched, see [Development Workflow](#development-workflow) below.
4. **Open a PR** against `main` with `Closes #<issue-number>` and a one-line description of what you fixed.

For anything larger than a docs fix or a small bug, follow the full workflow below.

## Repository Layout

The two most common contribution targets are the SDKs:

| Package               | Path       | Language     | Package manager |
| --------------------- | ---------- | ------------ | --------------- |
| Python SDK (`mem0ai`) | `mem0/`    | Python 3.9+  | `hatch`         |
| TypeScript SDK (`mem0ai`) | `mem0-ts/` | TypeScript | `pnpm`        |

Other packages include the CLIs (`cli/python/`, `cli/node/`), integrations
(`integrations/`), the self-hosted `server/`, and the docs site
(`docs/`). See [AGENTS.md](./AGENTS.md) for a full map of the repository.

## Development Workflow

1. **Fork** the repository and **clone** your fork.
2. Create a **feature branch** from `main` (e.g. `feature/my-new-feature` or
   `fix/issue-1234`).
3. Make your changes — add **tests**, **documentation**, and **examples** as
   appropriate.
4. Run **linting and tests** for every package you touched (see below).
5. Commit using [Conventional Commits](https://www.conventionalcommits.org/)
   (e.g. `feat:`, `fix:`, `docs:`, `refactor:`, `test:`).
6. Push and open a **pull request** against `main`, linking the issue with
   `Closes #<number>` and filling out the
   [PR template](./.github/PULL_REQUEST_TEMPLATE.md).

### Contributing to the Python SDK (`mem0/`)

We use [`hatch`](https://hatch.pypa.io/latest/install/) to manage environments.
**Do not use `pip` or `conda` for dependency management.**

```bash
# Activate a dev environment (3.9 / 3.10 / 3.11 / 3.12)
hatch shell dev_py_3_11

# Install pre-commit hooks (runs ruff + isort on commit)
pre-commit install

# Lint, format, and sort imports
make lint
make format
make sort

# Run the test suite (run `make install_all` first if deps are missing)
make test
```

- **Linter / formatter:** Ruff (line length **120**)
- **Import sorting:** isort (`profile = "black"`)
- **Tests:** pytest (in `tests/`)

See the full [Development guide](https://docs.mem0.ai/contributing/development) for
environment details.

### Contributing to the TypeScript SDK (`mem0-ts/`)

We use [`pnpm`](https://pnpm.io/) (v10+) for all TypeScript packages. **Do not use
`npm` or `yarn`.**

```bash
cd mem0-ts
pnpm install

pnpm run build        # tsup (CJS + ESM)
pnpm run test         # jest (all tests)
pnpm run test:unit    # unit tests with coverage
```

- **Build:** tsup
- **Formatter:** Prettier
- **Tests:** jest
- Always run type checking after changes: `pnpm run typecheck` (or `tsc --noEmit`).
- Use ES module `import` syntax — never `require()`.

## Good Contribution Practices

- **Keep PRs small and focused.** One logical change per PR is easier to review and
  merge.
- **Follow existing patterns.** Match the style, structure, and conventions of the
  code around you. Don't introduce new frameworks or abstractions without
  discussion.
- **Write tests** that would fail without your change — regression tests for bugs,
  coverage for new features.
- **Update documentation** in `docs/` for any user-facing change. New `.mdx` pages
  must be added to `docs/llms.txt` (run
  `python scripts/check-llms-txt-coverage.py --write` to scaffold entries).
- **Add examples** when introducing new user-facing behavior.
- **Run linters and tests locally** before pushing — CI re-runs them on every PR
  via the CI Gate.
- **Never commit secrets** — no `.env` files, API keys, or credentials.
- **Don't add core dependencies lightly.** New Python dependencies belong in an
  optional group in `pyproject.toml`, not the core `dependencies` list.
- **Be responsive** to review feedback and keep your branch up to date with `main`.

## Pull Request Checklist

Before requesting review, make sure:

- [ ] An issue exists and is linked with `Closes #<number>`
- [ ] You have signed the CLA
- [ ] Your code follows the project's style guidelines (lint passes)
- [ ] You performed a self-review of your changes
- [ ] Tests are added/updated and pass locally
- [ ] Documentation is updated if needed

## Reporting Security Issues

**Do not report security vulnerabilities through public issues or pull requests.**
Please follow our [Security Policy](./SECURITY.md) to report them privately.

## Releasing

All packages are published automatically via GitHub Actions when a GitHub Release
is created with the correct tag prefix.

### Tag Prefixes

| Package | Registry | Tag Prefix | Example |
|---------|----------|------------|---------|
| `mem0ai` (Python SDK) | PyPI | `v*` | `v0.1.31` |
| `mem0-cli` (Python CLI) | PyPI | `cli-v*` | `cli-v0.2.1` |
| `mem0ai` (TypeScript SDK) | npm | `ts-v*` | `ts-v2.4.6` |
| `@mem0/cli` (Node CLI) | npm | `cli-node-v*` | `cli-node-v0.1.2` |
| `@mem0/vercel-ai-provider` | npm | `vercel-ai-v*` | `vercel-ai-v2.0.6` |
| `@mem0/openclaw-mem0` | npm | `openclaw-v*` | `openclaw-v1.0.1` |

### How to Release

1. Bump the version in `pyproject.toml` (Python) or `package.json` (Node)
2. Create a [GitHub Release](https://github.com/mem0ai/mem0/releases/new) with the matching tag prefix
3. The correct workflow will trigger automatically — verify in the [Actions tab](https://github.com/mem0ai/mem0/actions)

### Publishing Details

- **PyPI packages** use OIDC trusted publishing via `pypa/gh-action-pypi-publish`
- **npm packages** use OIDC trusted publishing via npm CLI (>= 11.5.1) — no tokens or secrets required
- All workflows require `permissions: id-token: write` for OIDC authentication
- First publish of a new npm package must be done manually; OIDC works for subsequent versions

We look forward to your pull requests and can't wait to see your contributions!
