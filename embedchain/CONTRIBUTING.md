# Contributing to embedchain

Let us make contribution easy, collaborative and fun.

## Submit your Contribution through PR

To make a contribution, follow these steps:

1. Fork and clone this repository
2. Do the changes on your fork with dedicated feature branch `feature/f1`
3. If you modified the code (new feature or bug-fix), please add tests for it
4. Include proper documentation / docstring and examples to run the feature
5. Check the linting
6. Ensure that all tests pass
7. Submit a pull request

For more details about pull requests, please read [GitHub's guides](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request).


### 📦 Package manager

We use `poetry` as our package manager. You can install poetry by following the instructions [here](https://python-poetry.org/docs/#installation).

Please DO NOT use pip or conda to install the dependencies. Instead, use poetry:

```bash
make install_all

#activate

poetry shell
```

### 📌 Pre-commit

To ensure our standards, make sure to install pre-commit before starting to contribute.

```bash
pre-commit install
```

### 🧹 Linting

We use `ruff` to lint our code. You can run the linter by running the following command:

```bash
make lint
```

Make sure that the linter does not report any errors or warnings before submitting a pull request.

### Code Formatting with `black`

We use `black` to reformat the code by running the following command:

```bash
make format
```

### 🧪 Testing

We use `pytest` to test our code. You can run the tests by running the following command:

```bash
poetry run pytest
```


Several packages have been removed from Poetry to make the package lighter. Therefore, it is recommended to run `make install_all` to install the remaining packages and ensure all tests pass.


Make sure that all tests pass before submitting a pull request.

## 🚀 Release Process

At the moment, the release process is manual. We try to make frequent releases. Usually, we release a new version when we have a new feature or bugfix. A developer with admin rights to the repository will create a new release on GitHub, and then publish the new version to PyPI.
