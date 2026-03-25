# Vast SDK Unit Test Requirements

This document defines the requirements and best practices for writing unit tests for the Vast SDK. It is designed to guide both human developers and AI agents in creating maintainable, reliable, and properly isolated tests.

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Test Structure and Patterns](#test-structure-and-patterns)
4. [Mocks and Fixtures](#mocks-and-fixtures)
5. [Async Tests](#async-tests)
6. [Best Practices](#best-practices)
7. [Troubleshooting](#troubleshooting)

---

## Overview

### Purpose

Unit tests for the Vast SDK validate:

- **Client behavior**: VastAI and Serverless client logic
- **Import and export**: Package structure and public API surface
- **Request/response handling**: API call construction, response parsing, error handling
- **Async flows**: Serverless client async operations (endpoints, requests)
- **Edge cases**: Invalid input, missing API key, network failures, malformed responses

### CI/CD Integration

Tests run automatically in the GitHub Actions workflow (`vast-sdk-testing.yml`) on:

- Pull request open, sync, reopen, or ready for review

The workflow uses the separate test Poetry project in `tests/`. All tests must pass before merging.

### Test Environment

- **Test Framework**: pytest
- **Test Project**: `tests/` with its own `pyproject.toml` (see [TESTING.md](./TESTING.md))
- **No real API calls**: All network traffic must be mocked; tests never hit production APIs

---

## Quick Start

```bash
# From repo root
poetry install -C tests
poetry run -C tests pytest -v

# From tests/ directory
poetry install
poetry run pytest -v
```

Run with coverage (from repo root):

```bash
poetry run -C tests pytest -v --cov=vastai --cov-report=term-missing
```

---

## Test Structure and Patterns

### Basic Test Template

Every unit test should follow this structure:

```python
import pytest
from unittest.mock import patch, AsyncMock

def test_vastai_client_requires_api_key():
    """
    Verifies that VastAI raises when no API key is provided and none is set in environment.

    This test verifies by:
    1. Patching os.environ to ensure VAST_API_KEY is unset
    2. Attempting to instantiate VastAI without an api_key argument
    3. Asserting that AttributeError is raised (or the specific SDK behavior)

    Assumptions:
    - No API key file exists at the default location
    - Test runs in isolation (no environment leakage)
    """
    with patch.dict("os.environ", {"VAST_API_KEY": ""}, clear=False):
        with pytest.raises(AttributeError, match="API key"):
            from vastai import VastAI
            VastAI()
```

### Required Docstrings

**All tests must include a docstring** that documents:

1. **What the test verifies** – The behavior or functionality being tested
2. **How the test verifies it** – Steps, assertions, mocks, or methods used
3. **Assumptions** – Preconditions, mocks applied, environment expectations

```python
def test_serverless_request_builds_correct_payload():
    """
    Verifies that Serverless.request constructs the HTTP payload as expected.

    This test verifies by:
    1. Mocking the underlying _make_request or aiohttp to avoid real API calls
    2. Calling serverless.request with a known payload
    3. Asserting the mock received the expected JSON structure

    Assumptions:
    - serverless_mock fixture provides a Serverless instance with mocked HTTP
    - No real network requests are made
    """
    # Test implementation
```

### Test Naming

- Use descriptive names: `test_create_instance_with_valid_payload_returns_instance_id`
- Follow pattern: `test_<action>_<condition>_<expected_result>`
- For classes: `Test<ModuleOrFeature>` with methods like `test_<scenario>`

### Common Patterns

#### 1. Mock HTTP and API Calls

Never allow tests to hit real endpoints. Patch at the lowest practical level:

```python
from unittest.mock import patch, MagicMock

@patch("vastai.serverless.client.connection._make_request")
async def test_get_endpoints_returns_list(mock_request):
    mock_request.return_value = {"ok": True, "json": {"results": [{"id": 1, "endpoint_name": "test"}]}}

    from vastai import Serverless
    client = Serverless(api_key="test-key")
    endpoints = await client.get_endpoints()

    assert len(endpoints) == 1
    assert endpoints[0].name == "test"
```

#### 2. Test Success and Error Cases

Cover both success and failure paths:

```python
def test_serverless_raises_when_api_key_missing():
    with patch.dict("os.environ", {"VAST_API_KEY": ""}, clear=False):
        with pytest.raises(AttributeError):
            from vastai import Serverless
            Serverless()

def test_serverless_accepts_api_key_arg():
    client = Serverless(api_key="sk-test-123")
    assert client.api_key == "sk-test-123"
```

#### 3. Use Fixtures for Shared Setup

Define fixtures in `tests/conftest.py` for reusable mocks and clients:

```python
# In conftest.py
@pytest.fixture
def mock_api_key():
    return "sk-test-12345"

@pytest.fixture
def serverless_client(mock_api_key):
    from vastai import Serverless
    return Serverless(api_key=mock_api_key)
```

---

## Mocks and Fixtures

### Overview

All tests that touch network, filesystem, or external services must use mocks. Define shared fixtures in `tests/conftest.py`.

### HTTP Client Mocks

**When to use**: Any code that calls `requests`, `aiohttp`, or internal helpers like `_make_request`.

**Where to patch**: Patch at the module where the call is made (e.g. `vastai.serverless.client.connection._make_request`).

```python
@patch("vastai.serverless.client.connection._make_request", new_callable=AsyncMock)
async def test_get_endpoint_by_name(mock_make_request):
    mock_make_request.return_value = {
        "ok": True,
        "json": {
            "results": [
                {"id": 1, "endpoint_name": "my-endpoint"}
            ]
        }
    }
    # Test implementation
```

### Environment and File Mocks

```python
def test_reads_api_key_from_env():
    with patch.dict("os.environ", {"VAST_API_KEY": "sk-from-env"}):
        client = VastAI()
        assert client.api_key == "sk-from-env"

def test_reads_api_key_from_file():
    with patch("builtins.open", mock_open(read_data="sk-from-file\n")):
        # Patch APIKEY_FILE path if needed
        # Test implementation
```

### One Fixture per Concept

Keep fixtures focused. Use one fixture per logical resource (e.g. `mock_api_response`, `serverless_client`, `vastai_client`). Reuse and compose rather than duplicating.

---

## Async Tests

### pytest-asyncio

For async tests, use `pytest-asyncio` and the `@pytest.mark.asyncio` marker. Add `pytest-asyncio` to `tests/pyproject.toml` if not present:

```toml
[tool.poetry.dependencies]
pytest-asyncio = "^0.24.0"
```

Configure in `tests/pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

### Async Test Template

```python
@pytest.mark.asyncio
async def test_serverless_get_endpoints():
    """
    Verifies that get_endpoints returns a list of Endpoint objects.

    Mocks _make_request to return sample JSON. Asserts parsing and object creation.
    """
    with patch("vastai.serverless.client.client._make_request", new_callable=AsyncMock) as mock:
        mock.return_value = {"ok": True, "json": {"results": []}}
        client = Serverless(api_key="test")
        endpoints = await client.get_endpoints()
        assert endpoints == []
```

---

## Best Practices

### 1. Test Isolation

- Each test must be independent; no shared mutable state
- Use mocks; never depend on real API keys, networks, or files
- Use unique or deterministic test data

### 2. Assertions

- Be specific: assert exact values and types, not just truthiness
- Validate structure: check dict keys, list lengths, response shapes
- Test edge cases: empty lists, None, malformed JSON

```python
# Good
assert response.status_code == 200
assert "results" in data
assert isinstance(data["results"], list)

# Avoid
assert response.ok
assert data
```

### 3. Error Handling

- Test error paths: missing keys, invalid input, 4xx/5xx responses
- Assert that exceptions are raised when expected: `pytest.raises(...)`
- Validate error messages or exception types

### 4. Fixtures in conftest.py

- Put shared fixtures in `tests/conftest.py`
- Keep test-specific helpers in the test file unless they become reusable

### 5. Patch Placement

- Patch where the object is used, not where it is defined
- Prefer `@patch("module.import_path")` or `with patch(...)` for clarity
- Use `AsyncMock` for async functions

### 6. Resource Cleanup (RAII)

**Tests must clean up testing resources using RAII-style patterns.** Resource cleanup must happen automatically when scope is exited, even if the test fails or raises an exception. Prefer context managers (`with` statements) over manual `try/finally` blocks.

**Requirements**:

- **Use `with` for patches**: `with patch(...):` and `with patch.dict(...):` ensure mocks are automatically restored when the block exits.
- **Use `with` for temporary resources**: File handles, temp directories (`tempfile.TemporaryDirectory`), sockets, or any resource that must be released.
- **Prefer context-manager fixtures**: If a fixture acquires resources, use `yield` so pytest runs teardown after the test; or return a context manager and let the test use `with fixture():`.
- **Use `try/finally` when using `try/except`**: If a test uses `try/except` to handle expected exceptions, it must include a `finally` block to clean up any resources acquired in the `try` block. Cleanup must run whether the test passes, fails, or raises.

```python
# Good: RAII via context manager
def test_env_isolation():
    with patch.dict("os.environ", {"VAST_API_KEY": "sk-test"}, clear=False):
        client = Serverless(api_key="sk-test")
        assert client.api_key == "sk-test"
    # patch.dict restores original env automatically on exit (even on exception)

# Good: RAII via context manager for temp file
def test_reads_config_from_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"api_key": "sk-file"}, f)
        path = f.name
    try:
        # ... test using path ...
    finally:
        os.unlink(path)

# Better: use TemporaryDirectory for temp files
def test_reads_config_from_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = pathlib.Path(tmpdir) / "config.json"
        config_path.write_text('{"api_key": "sk-file"}')
        # ... test using config_path ...
    # Directory and contents removed automatically on block exit

# Good: fixture that yields (RAII-like teardown)
@pytest.fixture
def isolated_env():
    with patch.dict("os.environ", {"VAST_API_KEY": ""}, clear=False):
        yield
    # Original env restored when fixture scope exits

# Good: try/except with finally for cleanup
def test_handles_exception_and_cleans_up():
    resource = acquire_test_resource()
    try:
        with pytest.raises(ValueError):
            code_that_may_raise()
    finally:
        resource.cleanup()  # Runs even when pytest.raises triggers
```

**Avoid**:

- Manual `try/finally` when a context manager exists (e.g. use `with patch` instead of `try: p = patch(...); p.start(); ... finally: p.stop()`).
- Leaving patches active beyond test scope (e.g. module-level `patch.start()` without corresponding `stop()`).
- Using `try/except` without `finally` when the test acquires resources that require cleanup.

---

## Troubleshooting

### Tests fail with "API key missing"

Ensure `VAST_API_KEY` is not set in the test environment, or patch `os.environ` so tests that expect missing keys run in a clean environment.

### Async tests not running

- Confirm `pytest-asyncio` is in `tests/pyproject.toml`
- Set `asyncio_mode = "auto"` in `[tool.pytest.ini_options]`
- Use `@pytest.mark.asyncio` on async test functions

### Import errors

Tests run from the `tests/` directory with the SDK installed in editable mode. Use `from vastai import ...`; the SDK should be on the path via the test project's dependency on `vastai-sdk`.

### Mock not applied

Patch the object in the module where it is imported and used. For example, if `client.py` does `from connection import _make_request`, patch `vastai.serverless.client.client._make_request` (or the equivalent import path).
