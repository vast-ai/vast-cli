# Vast SDK Testing Infrastructure

This document describes the design and usage of the testing infrastructure for the Vast SDK. For requirements and best practices when writing unit tests, see [unit-test-requirements.md](./unit-test-requirements.md).

## Design Overview

The test suite uses a **separate Poetry project** from the main SDK. This separation provides:

- **Independent dependency tracking**: Test-only dependencies (e.g. pytest, coverage, mocks) live in `tests/pyproject.toml` and do not pollute the main SDK’s dependency tree.
- **Clear boundaries**: The main SDK `pyproject.toml` stays focused on runtime dependencies.
- **Isolated environments**: You can install and run tests without pulling in the main project’s dev tools, and vice versa.

## Layout

```
vast-sdk/
├── pyproject.toml          # Main SDK (vastai-sdk) – runtime dependencies only
├── vastai/
├── vastai_sdk/
├── tests/
│   ├── pyproject.toml      # Test project (vast-sdk-tests) – pytest + SDK
│   ├── __init__.py
│   └── test_*.py
└── .github/workflows/
    └── vast-sdk-testing.yml
```

## Test Project (`tests/pyproject.toml`)

The test project:

- Defines `vast-sdk-tests` as a Poetry project with `package-mode = false` (dependency management only, no package to build).
- Depends on `vastai-sdk` via a path dependency: `vastai-sdk = { path = "..", develop = true }`.
- Declares pytest and related test tools.
- Configures pytest via `[tool.pytest.ini_options]`.

The `develop = true` dependency makes the SDK install in editable mode so test runs use the current source.

## Running Tests

### Locally

```bash
# Install test dependencies (installs SDK from parent + pytest)
poetry install -C tests

# Run all tests
poetry run -C tests pytest -v

# Run with extra options (e.g. coverage)
poetry run -C tests pytest -v --cov=vastai
```

### In CI (GitHub Actions)

`.github/workflows/vast-sdk-testing.yml`:

1. Checks out the repo.
2. Sets up Python.
3. Installs Poetry and `poetry-dynamic-versioning` (needed to build the main SDK).
4. Runs `poetry install -C tests` in the test project.
5. Runs `poetry run -C tests pytest -v`.

## Adding Test Dependencies

Add dependencies to `tests/pyproject.toml` under `[tool.poetry.dependencies]`:

```toml
[tool.poetry.dependencies]
python = ">=3.9"
pytest = "^8.0.0"
pytest-cov = "^4.0.0"   # example
vastai-sdk = { path = "..", develop = true }
```

Then run `poetry install -C tests` (or `poetry lock -C tests` if lockfile changes are needed).

## Test Discovery

By default, pytest:

- Runs from the `tests/` directory.
- Collects modules matching `test_*.py`.
- Collects functions and methods matching `test_*`.

Adjust `[tool.pytest.ini_options]` in `tests/pyproject.toml` if you change layouts or naming.
