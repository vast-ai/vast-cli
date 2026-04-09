# vastai-sdk

This package is a thin compatibility wrapper around the [`vastai`](https://pypi.org/project/vastai/) package.

All code now lives in the `vastai` package. This wrapper allows existing code that does `import vastai_sdk` or `from vastai_sdk import ...` to continue working without changes.

## Installation

```bash
pip install vastai-sdk
```

This will automatically install the `vastai` package as a dependency.

## Usage

```python
# Both of these work identically:
from vastai import VastAI
from vastai_sdk import VastAI

# Submodule imports also work:
from vastai_sdk.serverless.client.client import Serverless
```

## Migration

If you are starting a new project, use `vastai` directly:

```bash
pip install vastai
```
