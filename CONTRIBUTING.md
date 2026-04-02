# Contributing to mem0

Let us make contribution easy, collaborative and fun.

## Submit your Contribution through PR

To make a contribution, follow these steps:

1. Fork and clone this repository
2. Do the changes on your fork with dedicated feature branch `feature/f1`
3. If you modified the code (new feature or bug-fix), please add tests for it
4. Include proper documentation / docstring and examples to run the feature
5. Ensure that all tests pass
6. Submit a pull request

For more details about pull requests, please read [GitHub's guides](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request).


### 📦 Development Environment

We use `hatch` for managing development environments. To set up:

```bash
# Activate environment for specific Python version:
hatch shell dev_py_3_9   # Python 3.9
hatch shell dev_py_3_10  # Python 3.10  
hatch shell dev_py_3_11  # Python 3.11
hatch shell dev_py_3_12  # Python 3.12

# The environment will automatically install all dev dependencies
# Run tests within the activated shell:
make test
```

### 📌 Pre-commit

To ensure our standards, make sure to install pre-commit before starting to contribute.

```bash
pre-commit install
```

### 🧪 Testing

We use `pytest` to test our code across multiple Python versions. You can run tests using:

```bash
# Run tests with default Python version
make test

# Test specific Python versions:
make test-py-3.9   # Python 3.9 environment
make test-py-3.10  # Python 3.10 environment
make test-py-3.11  # Python 3.11 environment
make test-py-3.12  # Python 3.12 environment

# When using hatch shells, run tests with:
make test  # After activating a shell with hatch shell test_XX
```

Make sure that all tests pass across all supported Python versions before submitting a pull request.

We look forward to your pull requests and can't wait to see your contributions!

### 🚀 Releasing

All packages are published automatically via GitHub Actions when a GitHub Release is created with the correct tag prefix.

#### Tag Prefixes

| Package | Registry | Tag Prefix | Example |
|---------|----------|------------|---------|
| `mem0ai` (Python SDK) | PyPI | `v*` | `v0.1.31` |
| `mem0-cli` (Python CLI) | PyPI | `cli-v*` | `cli-v0.2.1` |
| `mem0ai` (TypeScript SDK) | npm | `ts-v*` | `ts-v2.4.6` |
| `@mem0/cli` (Node CLI) | npm | `cli-node-v*` | `cli-node-v0.1.2` |
| `@mem0/vercel-ai-provider` | npm | `vercel-ai-v*` | `vercel-ai-v2.0.6` |
| `@mem0/openclaw-mem0` | npm | `openclaw-v*` | `openclaw-v1.0.1` |

#### How to Release

1. Bump the version in `pyproject.toml` (Python) or `package.json` (Node)
2. Create a [GitHub Release](https://github.com/mem0ai/mem0/releases/new) with the matching tag prefix
3. The correct workflow will trigger automatically — verify in the [Actions tab](https://github.com/mem0ai/mem0/actions)

#### Publishing Details

- **PyPI packages** use OIDC trusted publishing via `pypa/gh-action-pypi-publish`
- **npm packages** use OIDC trusted publishing via npm CLI (>= 11.5.1) — no tokens or secrets required
- All workflows require `permissions: id-token: write` for OIDC authentication
- First publish of a new npm package must be done manually; OIDC works for subsequent versions
