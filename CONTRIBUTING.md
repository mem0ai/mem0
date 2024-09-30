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

### 🧪 Testing

We use `pytest` to test our code. You can run the tests by running the following command:

```bash
poetry run pytest tests

# or

make test
```

Several packages have been removed from Poetry to make the package lighter. Therefore, it is recommended to run `make install_all` to install the remaining packages and ensure all tests pass. Make sure that all tests pass before submitting a pull request.

We look forward to your pull requests and can't wait to see your contributions!