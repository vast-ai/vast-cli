# SDK Overview

The Vast.ai Python SDK provides programmatic access to all Vast.ai CLI functionality through a clean Python interface.

## Key Features

- **130+ Methods**: Every CLI command available as a Python method
- **Type Hints**: Full type annotations for IDE support and static analysis
- **Raw Mode by Default**: SDK returns parsed JSON, not CLI output
- **Automatic Retries**: Built-in retry logic for transient failures
- **Thread-Safe**: Safe to use from multiple threads

## Quick Example

```python
from vastai import VastAI

# Initialize client
client = VastAI(api_key="your-api-key")

# Search for GPU offers
offers = client.search_offers(limit=10)

# Create an instance
result = client.create_instance(
    id=offers[0]["id"],
    image="pytorch/pytorch:latest"
)

# Check your instances
instances = client.show_instances()
```

## Architecture

The SDK consists of three layers:

1. **VastAI class** (`vastai/sdk.py`): Main entry point with method dispatch
2. **VastAIBase class** (`vastai/vastai_base.py`): Method signatures and type hints
3. **vast.py module**: Actual command implementations

When you call `client.search_offers()`, the SDK:

1. Builds an argparse Namespace with your parameters
2. Captures stdout (in raw mode, returns JSON directly)
3. Calls the underlying CLI function
4. Returns the parsed result

## Return Types

Methods follow a consistent return type pattern:

| Method Pattern | Return Type | Example |
|----------------|-------------|---------|
| `search_*` | `list[dict[str, Any]]` | `search_offers()` |
| `show_*s` (plural) | `list[dict[str, Any]]` | `show_instances()` |
| `show_*` (singular) | `dict[str, Any]` | `show_instance(id=123)` |
| `create_*` | `dict[str, Any]` | `create_instance(...)` |
| `destroy_*` | `dict[str, Any]` | `destroy_instance(id=123)` |

## Error Handling

```python
from vastai import VastAI

client = VastAI(api_key="your-api-key")

try:
    result = client.show_instance(id=99999)
except Exception as e:
    print(f"Error: {e}")
```

!!! tip "Check the API response"
    Most methods return a dict with a `success` key. Always check this:
    ```python
    result = client.create_instance(...)
    if result.get("success"):
        print("Instance created!")
    else:
        print(f"Error: {result.get('msg', 'Unknown error')}")
    ```

## Configuration Options

The `VastAI` constructor accepts several configuration options:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | `str` | None | API key (reads from file if not provided) |
| `server_url` | `str` | `https://console.vast.ai` | API base URL |
| `retry` | `int` | 3 | Number of retry attempts |
| `raw` | `bool` | True | Return JSON instead of printing |
| `explain` | `bool` | False | Print API endpoint info |
| `quiet` | `bool` | False | Suppress non-essential output |
| `curl` | `bool` | False | Print equivalent curl commands |

## Next Steps

- [Quick Start Guide](quickstart.md) - Detailed walkthrough
- [API Reference](reference/vastai.md) - Full method documentation
