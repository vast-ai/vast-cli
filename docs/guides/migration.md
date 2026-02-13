# Migration Guide

This guide helps users migrate from the old `vastai_sdk` package to the unified `vastai` package.

## Overview

The Vast.ai CLI and SDK have been merged into a single package. The SDK now imports from the live CLI module instead of a frozen copy, ensuring feature parity and eliminating code drift.

**Key benefits of the merger:**

- Single source of truth for all Vast.ai functionality
- Automatic feature parity between CLI and SDK
- Better error handling and retry logic
- Full type hints for IDE support
- Comprehensive docstrings

## Import Path Changes

### Old Import (Deprecated)

```python
# Old way - still works but shows deprecation warning
from vastai_sdk import VastAI
```

### New Import (Recommended)

```python
# New way - use this going forward
from vastai import VastAI
```

The old import path (`vastai_sdk`) remains functional for backwards compatibility but will emit a `DeprecationWarning`. Update your imports when convenient.

## Breaking Changes

### None for v1.0

The merger was designed to be backwards compatible. Existing code should work without changes, though you may see deprecation warnings.

## Deprecated Patterns

### Import Paths

| Old | New | Status |
|-----|-----|--------|
| `from vastai_sdk import VastAI` | `from vastai import VastAI` | Deprecated, still works |
| `from vastai_sdk import ...` | `from vastai import ...` | Deprecated, still works |

### Method Names

| Old Method | New Method | Status |
|------------|------------|--------|
| `client.autogroup_*()` | `client.workergroup_*()` | Aliased, both work |
| `client.autoscaler_*()` | `client.workergroup_*()` | Aliased, both work |

The old method names (`autogroup_*`, `autoscaler_*`) remain as aliases. New code should use `workergroup_*`.

## New Features

The unified package includes several improvements:

### Type Hints

All SDK methods now have type annotations:

```python
def search_offers(
    self,
    query: str | None = None,
    limit: int | None = None,
    order: str | None = None,
    **kwargs
) -> list[dict[str, Any]]:
    ...
```

### Docstrings

All methods have Google-style docstrings for IDE support:

```python
from vastai import VastAI
client = VastAI(api_key="key")
help(client.search_offers)  # Shows full documentation
```

### Better Error Handling

- Specific exception types instead of bare `except:`
- Thread-safe stdout capture
- `sys.exit()` calls converted to return values
- Proper exception chaining

### Retry Logic

Automatic retry with exponential backoff for:

- HTTP 429 (rate limit)
- HTTP 502, 503, 504 (server errors)
- Connection errors and timeouts

Non-retryable errors (like 500) are raised immediately.

### Timeouts

All HTTP requests have configurable timeouts:

- Default: 30 seconds
- File operations: 120 seconds

## Serverless Framework

The serverless client/server framework is now part of the main package:

```python
# Old (separate package)
from vast_serverless import Serverless, Worker

# New (lazy import from main package)
from vastai import Serverless, Worker
```

Install serverless dependencies:

```bash
pip install "vastai[serverless]"
```

The serverless classes are lazily imported, so users who don't need them won't have to install the extra dependencies.

## Configuration

### API Key Storage

No changes - keys are still stored in:

- `~/.config/vastai/vast_api_key` (XDG spec, preferred)
- `~/.vast_api_key` (legacy, still supported)

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `VAST_API_KEY` | Override file-based API key |
| `VAST_URL` | Override server URL |
| `LOGLEVEL` | Set logging level |

### Constructor Parameters

The `VastAI` class accepts these parameters:

```python
client = VastAI(
    api_key="your-key",         # API key (or from env/file)
    raw=False,                   # Return raw JSON responses
    retry=3,                     # Max retry attempts
    server_url=None,             # Override API server URL
    explain=False,               # Print API calls for debugging
    quiet=False                  # Suppress non-essential output
)
```

## Testing Your Migration

### Step 1: Update Imports

```python
# Change this:
from vastai_sdk import VastAI

# To this:
from vastai import VastAI
```

### Step 2: Suppress Warnings (Optional)

If you can't update imports immediately:

```python
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="vastai_sdk")
```

### Step 3: Verify Functionality

```python
from vastai import VastAI

client = VastAI(api_key="your-key")

# Test basic operations
offers = client.search_offers(limit=1)
print(f"Found {len(offers)} offers")

instances = client.show_instances()
print(f"You have {len(instances)} instances")
```

### Step 4: Check for Deprecation Warnings

Run your code with warnings enabled:

```bash
python -W default your_script.py
```

This will show any deprecated method or import usage.

## Troubleshooting

### DeprecationWarning on Import

**Problem:** You see warnings like `DeprecationWarning: vastai_sdk is deprecated`

**Solution:** Update your imports from `vastai_sdk` to `vastai`.

### Missing Serverless Classes

**Problem:** `ImportError: cannot import name 'Serverless'`

**Solution:** Install serverless extras:

```bash
pip install "vastai[serverless]"
```

### Different Return Types

**Problem:** Code that worked before returns different data

**Solution:** Some methods now return different types. If you were depending on specific return shapes, check the [API Reference](../sdk/reference/vastai.md) for current signatures.

Most changes:
- Methods return `dict` or `list[dict]` consistently
- Error cases return error information instead of raising

### Method Not Found

**Problem:** A method worked before but is now missing

**Solution:** Check:

1. Spelling (some were renamed for consistency)
2. Aliased names (`autogroup_*` -> `workergroup_*`)
3. [API Reference](../sdk/reference/vastai.md) for current methods

### Authentication Errors

**Problem:** API key not being found

**Solution:** Check these locations in order:

1. Constructor parameter: `VastAI(api_key="...")`
2. Environment variable: `VAST_API_KEY`
3. Config file: `~/.config/vastai/vast_api_key`
4. Legacy file: `~/.vast_api_key`

## Common Migration Patterns

### From SDK-only to Unified

```python
# Before
from vastai_sdk import VastAI
client = VastAI()
client.search_offers()

# After (identical API)
from vastai import VastAI
client = VastAI()
client.search_offers()
```

### From CLI Scripts to SDK

```python
# Before: subprocess calls
import subprocess
result = subprocess.run(["vastai", "search", "offers"], capture_output=True)

# After: direct SDK usage
from vastai import VastAI
client = VastAI()
offers = client.search_offers()
```

### Adding Type Checking

```python
from vastai import VastAI
from typing import Any

client = VastAI(api_key="key")

# Now with proper types
offers: list[dict[str, Any]] = client.search_offers(limit=10)
instance: dict[str, Any] = client.show_instance(id=12345)
```

## Getting Help

- [Changelog](../changelog.md) - Full list of changes
- [GitHub Issues](https://github.com/vast-ai/vast-cli/issues) - Report bugs
- [SDK Reference](../sdk/reference/vastai.md) - Current API documentation
- [Serverless Overview](../serverless/index.md) - Async client/server framework
