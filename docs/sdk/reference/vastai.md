# VastAI API Reference

This page documents all public methods on the `VastAI` class.

The VastAI class provides programmatic access to the Vast.ai GPU cloud platform.
Each CLI command is available as a method on this class.

## Class Overview

```python
from vastai import VastAI

client = VastAI(
    api_key: str | None = None,      # API key (reads from file if not provided)
    server_url: str | None = None,   # Override API server URL
    retry: int = 3,                  # Max retry attempts for transient failures
    raw: bool = True,                # Return JSON instead of printing (SDK default)
    explain: bool = False,           # Print API endpoint info for debugging
    quiet: bool = False,             # Suppress non-essential output
    curl: bool = False,              # Print equivalent curl commands
)
```

The SDK provides **130+ methods** corresponding to CLI commands. All methods return either:

- `dict[str, Any]` - Single object responses
- `list[dict[str, Any]]` - Collection responses

Most responses include a `success` boolean and `msg` string for error details.

## Common Patterns

### Error Handling

```python
from vastai import VastAI

client = VastAI(api_key="your-key")

result = client.create_instance(id=12345, image="pytorch/pytorch")

if result.get("success"):
    instance_id = result["new_contract"]
    print(f"Created instance: {instance_id}")
else:
    print(f"Error: {result.get('msg', 'Unknown error')}")
```

### Filtering Results

```python
# Use query parameter for server-side filtering
offers = client.search_offers(
    query="num_gpus >= 4 gpu_ram >= 24 dph_total < 2.0",
    order="dph_total",
    limit=10
)
```

### Debug Mode

```python
# See API calls being made
client = VastAI(api_key="key", explain=True)
client.search_offers(limit=1)
# Prints: GET https://console.vast.ai/api/v0/bundles?...
```

## Return Types

All methods return one of:

- `dict[str, Any]` - Single object responses
- `list[dict[str, Any]]` - Collection responses

Most responses include a `success` boolean and `msg` string for error details.

## See Also

- [Quick Start Guide](../quickstart.md) - Working examples
- [CLI Command Reference](../../cli/commands.md) - Full CLI documentation
- [Migration Guide](../../guides/migration.md) - Upgrading from old SDK
