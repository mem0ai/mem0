# Contributing to Mem0

First off, thank you for taking the time to contribute! 🎉 Mem0 is a
community-driven project and we welcome contributions of all kinds — bug fixes,
new features, documentation, examples, and integrations.

Mem0 is a polyglot monorepo, and this guide covers contributing to both the
**Python SDK** and the **TypeScript SDK** (and the rest of the repository).

## Before You Start

### 1. Open an Issue First

**For non-security changes, always open an issue before opening a pull request.**
This lets us discuss the change, avoid duplicate effort, and agree on the
approach before you invest time in code.

Exception: do not open a public issue or pull request for security
vulnerabilities, unsafe examples, or secret exposure. Follow
[SECURITY.md](./SECURITY.md) and report those privately.

- Search [existing issues](https://github.com/mem0ai/mem0/issues) first to see if
  your bug or idea already exists.
- If it doesn't, open a
  [bug report](https://github.com/mem0ai/mem0/issues/new?template=bug_report.yml) or
  [feature request](https://github.com/mem0ai/mem0/issues/new?template=feature_request.yml).
- For anything beyond a trivial fix, wait for a maintainer to confirm the approach
  before starting significant work.

Every non-security pull request must link to an issue using `Closes #<issue-number>`.

### 2. Sign the Contributor License Agreement (CLA)

**We cannot accept or merge any pull request until you have signed our Contributor
License Agreement (CLA).**

When you open your first PR, the CLA bot will automatically comment with a link to
sign. Signing takes less than a minute and only needs to be done once. Pull
requests from contributors who have not signed the CLA will be blocked from
merging.

## First Contribution Fast Path

If you are making a typo fix, copy edit, or factual correction to an existing
docs page, `README.md`, or `CONTRIBUTING.md`, you do not need to set up every
package in the monorepo. The CLA, the rule to never commit secrets, and the PR
template still apply. Keep the change narrow and follow this shorter path:

1. Good first candidates are existing issues about docs or `README.md`, typo
   fixes, or small factual corrections.
2. Search existing issues first. If the change relates to a security
   vulnerability, unsafe example, or secret exposure, do not open a public issue
   or pull request; follow [SECURITY.md](./SECURITY.md) and report it privately.
   Otherwise, if no issue exists, open a
   [documentation issue](https://github.com/mem0ai/mem0/issues/new?template=documentation_issue.yml)
   before the PR so the change still has an issue to link.
   For typo fixes and small factual corrections, you can open the docs issue and
   proceed immediately unless the scope expands.
3. Create a focused branch from `main`, such as `docs/fix-cli-example` or
   `docs/typo-platform-quickstart`.
4. Change only the relevant documentation files. Avoid drive-by wording changes
   in unrelated pages.
5. Run only the checks that match the files you touched:
   - For root markdown changes like `README.md` or `CONTRIBUTING.md`, review the
     rendered diff and run `git diff --check`.
   - For small edits to existing `docs/**/*.mdx` pages, check the rendered diff
     and any links you changed. If your edit adds, removes, or moves a docs page,
     update `docs/docs.json` and `docs/llms.txt`, then run `mintlify dev` from
     `docs/` to preview.
   - In addition, for links, commands, or code examples in any Markdown file,
     validate the exact content you changed: open changed links, run changed
     commands when safe, and verify code snippets against the system they
     document. For runnable examples, use the smallest relevant verification for
     that system. If an example cannot be run locally, explain that clearly in
     the PR. Use placeholders or redacted values only; never paste real API keys,
     internal URLs, customer IDs, or secrets into docs examples or screenshots.
6. For non-security docs changes, open a PR against `main`, link the issue with
   `Closes #<number>`, and clearly state which checks you ran.

For code changes, dependency changes, public API changes, or behavior changes,
use the full package-specific setup and verification workflow below.

## Repository Layout

The two most common contribution targets are the SDKs:

| Package               | Path       | Language     | Package manager |
| --------------------- | ---------- | ------------ | --------------- |
| Python SDK (`mem0ai`) | `mem0/`    | Python 3.9+  | `hatch`         |
| TypeScript SDK (`mem0ai`) | `mem0-ts/` | TypeScript | `pnpm`        |

Other packages include the CLIs (`cli/python/`, `cli/node/`), integrations
(`integrations/`), the self-hosted `server/`, `openmemory/`, and the docs site
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
6. For non-security changes, push and open a **pull request** against `main`,
   linking the issue with `Closes #<number>` and filling out the
   [PR template](./.github/PULL_REQUEST_TEMPLATE.md). Security reports and fixes
   should follow [SECURITY.md](./SECURITY.md) and maintainer instructions instead
   of the public issue/PR flow.

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

- [ ] For non-security changes, an issue exists and is linked with `Closes #<number>`
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
