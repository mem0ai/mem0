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
