# Vast SDK Tests

## Configuration

### API Key

Tests that hit the Vast API require an API key. Resolved in order:

1. `VAST_API_KEY` environment variable
2. `$XDG_CONFIG_HOME/vastai/vast_api_key` (typically `~/.config/vastai/vast_api_key`)
3. `~/.vast_api_key` (legacy)

### Server

By default, tests run against `https://console.vast.ai`. Override with:

```
VAST_SERVER=https://alpha.vast.ai pytest tests/
```

### Serverless Instance

Serverless tests target the `prod` autoscaler by default. Override with:

```
VAST_SERVERLESS_INSTANCE=alpha pytest tests/
```

### Template Hash

Serverless integration tests use the vLLM template by default
(`490c0ed717a7da3bc5e2677a80f9c4c2`). Override with:

```
VAST_TEST_TEMPLATE_HASH=<hash> pytest tests/
```

## Running Tests

```bash
# All tests
pytest tests/

# Only unit tests (no API calls)
pytest tests/test_data_objects.py

# Only integration tests
pytest tests/ -m integration

# Serverless tests (creates real resources — costs money)
pytest tests/ -m serverless
```

## Test Files

### `test_data_objects.py` — Unit tests for data objects

Pure unit tests with no API calls. Tests Query, Column, EndpointConfig,
WorkergroupConfig, DeploymentConfig, Offer, and their serialization.

**Setup/teardown:** None.

### `test_search.py` — Search API integration tests

Tests SyncClient.search() and AsyncClient.search() against the live API.
Read-only — no resources created or modified.

**Setup/teardown:** None.

### `test_serverless_lifecycle.py` — Serverless endpoint lifecycle tests

Tests the full serverless flow: create endpoint, add workergroup, send
request, delete workergroup, delete endpoint. Uses the vLLM template.

**Setup/teardown:**
- **Setup:** Creates an endpoint (`POST /api/v0/endptjobs/`) and a
  workergroup (`POST /api/v0/workergroups/`) with the configured template
  hash. These are created once per test session as a session-scoped fixture.
- **Teardown:** Deletes the workergroup (`DELETE /api/v0/workergroups/{id}/`)
  and endpoint (`DELETE /api/v0/endptjobs/{id}/`) in `finally` blocks.
  If teardown fails, resource IDs are printed for manual cleanup.

**Cost note:** Creating a workergroup provisions GPU instances via the
autoscaler. Tests in this file will incur real costs.

### `conftest.py` — Shared fixtures

Provides:
- `api_key` — resolved API key
- `vast_server` — target server URL
- `serverless_instance` — autoscaler instance name
- `template_hash` — template hash for serverless tests
- `sync_client` — `SyncClient` instance
- `async_client` — `AsyncClient` instance (session-scoped, closed after tests)
- `serverless_client` — `CoroutineServerless` instance (session-scoped)
- `managed_endpoint` — session-scoped `ManagedEndpoint` with a workergroup
  attached, torn down after the test session
