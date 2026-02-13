# Serverless Framework

The Vast.ai serverless framework provides async client/server components for distributed GPU workloads.

## Overview

The serverless framework consists of two main components:

- **Client** (`Serverless`): Sends requests to workers and handles responses
- **Server** (`Worker`): Runs on GPU instances, processes requests

```
+-------------+     HTTP/WebSocket     +-------------+
|   Client    | ---------------------> |   Worker    |
| (Serverless)| <--------------------- | (GPU Node)  |
+-------------+                        +-------------+
```

## Installation

The serverless components require additional dependencies:

```bash
pip install "vastai[serverless]"
```

This installs:

- `aiohttp` - Async HTTP client/server
- `anyio` - Async runtime abstraction
- `psutil` - System monitoring
- `pycryptodome` - Encryption

## Quick Start

### Client Side

```python
import asyncio
from vastai import Serverless

async def main():
    # Create client with async context manager
    async with Serverless(
        api_key="your-api-key",
        debug=False,
        connection_limit=500,
        default_request_timeout=600.0
    ) as client:
        # Send request to autoscaler endpoint
        response = await client.request(
            endpoint_id="your-endpoint-id",
            payload={"prompt": "Hello, world!", "max_tokens": 100}
        )
        print(response)

asyncio.run(main())
```

### Server Side (Worker)

```python
from vastai import Worker, WorkerConfig, HandlerConfig

# Define request handler
config = WorkerConfig(
    model_server_url="http://localhost:8000",
    model_server_port=8000,
    handlers=[
        HandlerConfig(
            route="/generate",
            allow_parallel_requests=False,
            max_queue_time=30.0
        )
    ]
)

# Start the worker
worker = Worker(config)
worker.run()
```

## Key Classes

### Serverless (Client)

The main client class for sending requests to workers via the Vast.ai autoscaler.

```python
from vastai import Serverless

client = Serverless(
    api_key="your-api-key",     # Required: API key
    debug=False,                 # Enable debug logging
    instance="prod",             # Instance: prod, alpha, or local
    connection_limit=500,        # Max concurrent connections
    default_request_timeout=600.0,  # Request timeout in seconds
    max_poll_interval=15.0       # Max polling interval
)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | `str` | `VAST_API_KEY` env | Your Vast.ai API key |
| `debug` | `bool` | `False` | Enable debug logging |
| `instance` | `str` | `"prod"` | Autoscaler instance (prod/alpha/local) |
| `connection_limit` | `int` | `500` | Max concurrent HTTP connections |
| `default_request_timeout` | `float` | `600.0` | Request timeout in seconds |
| `max_poll_interval` | `float` | `15.0` | Maximum polling interval |

### Worker (Server)

The server component that runs on GPU instances.

```python
from vastai import Worker, WorkerConfig

config = WorkerConfig(
    model_server_url="http://localhost:8000",
    handlers=[...]
)
worker = Worker(config)
worker.run()
```

### Configuration Classes

| Class | Purpose |
|-------|---------|
| `WorkerConfig` | Main worker configuration |
| `HandlerConfig` | Request handler settings |
| `LogActionConfig` | Logging configuration |
| `BenchmarkConfig` | Performance benchmarking |
| `ServerlessRequest` | Request future with status tracking |

### WorkerConfig

```python
from vastai import WorkerConfig

config = WorkerConfig(
    model_server_url="http://localhost:8000",  # Backend model server URL
    model_server_port=8000,                    # Backend port
    model_log_file="/var/log/model.log",       # Log file path
    model_healthcheck_url="/health",           # Health check endpoint
    handlers=[...],                            # List of HandlerConfig
    log_action_config=LogActionConfig()        # Logging configuration
)
```

### HandlerConfig

```python
from vastai import HandlerConfig, BenchmarkConfig

handler = HandlerConfig(
    route="/generate",              # Route path
    allow_parallel_requests=False,  # Allow parallel request processing
    max_queue_time=30.0,            # Max time request can wait in queue
    benchmark_config=BenchmarkConfig(),  # Optional benchmarking
    handler_class=None,             # Custom handler class
    payload_class=None,             # Custom payload class
    request_parser=None,            # Custom request parser function
    response_generator=None,        # Custom response generator function
    workload_calculator=None        # Custom workload calculator
)
```

### BenchmarkConfig

```python
from vastai import BenchmarkConfig

benchmark = BenchmarkConfig(
    dataset=[{"prompt": "test"}],  # Test dataset
    generator=None,                 # Optional sample factory function
    runs=8,                         # Number of benchmark runs
    concurrency=10                  # Concurrent requests during benchmark
)
```

## Lazy Loading

The serverless classes are lazily imported to avoid requiring `aiohttp` for users who only need the basic SDK:

```python
# This works without aiohttp installed
from vastai import VastAI
client = VastAI(api_key="key")

# This requires aiohttp (lazy import triggers here)
from vastai import Serverless  # Imports aiohttp on first access
```

This design means users who only need CLI/SDK functionality don't need to install the heavier async dependencies.

## Use Cases

### Inference Server

Run a model inference server on a rented GPU:

```python
from vastai import Worker, WorkerConfig, HandlerConfig

config = WorkerConfig(
    model_server_url="http://localhost:8000",
    handlers=[
        HandlerConfig(
            route="/v1/completions",
            allow_parallel_requests=True,
            max_queue_time=60.0
        )
    ]
)

worker = Worker(config)
worker.run()
```

### Batch Processing

Process multiple requests in parallel:

```python
from vastai import Serverless
import asyncio

async def batch_process(api_key: str, endpoint_id: str, requests: list):
    async with Serverless(api_key=api_key) as client:
        tasks = [
            client.request(endpoint_id=endpoint_id, payload=req)
            for req in requests
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results
```

### Custom Handler

Create a custom endpoint handler:

```python
from vastai import WorkerConfig, HandlerConfig

def parse_request(data: dict) -> dict:
    """Custom request parser."""
    return {"processed": data.get("input", "")}

def calculate_workload(data: dict) -> float:
    """Estimate workload for queue prioritization."""
    return len(data.get("input", "")) / 1000.0

config = WorkerConfig(
    handlers=[
        HandlerConfig(
            route="/custom",
            request_parser=parse_request,
            workload_calculator=calculate_workload
        )
    ]
)
```

## Error Handling

```python
from vastai import Serverless

async def robust_request(api_key: str, endpoint_id: str, data: dict):
    try:
        async with Serverless(api_key=api_key) as client:
            response = await client.request(
                endpoint_id=endpoint_id,
                payload=data
            )
            if response.get("success"):
                return response.get("result")
            else:
                print(f"Error: {response.get('error')}")
                return None
    except Exception as e:
        print(f"Request failed: {e}")
        return None
```

## Next Steps

- [SDK Overview](../sdk/index.md) - Basic SDK usage
- [CLI Reference](../cli/commands.md) - Command-line tools
- [Installation](../installation.md) - Full installation options
