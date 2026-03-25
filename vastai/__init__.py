from .sdk import VastAI

try:
    from .serverless.client.client import Serverless, ServerlessRequest
    from .serverless.client.endpoint import Endpoint
    from .serverless.server.worker import Worker
    from .serverless.server.worker import WorkerConfig, HandlerConfig, LogActionConfig, BenchmarkConfig
except ImportError:
    # Serverless dependencies (aiohttp, etc.) not installed
    Serverless = None
    ServerlessRequest = None
    Endpoint = None
    Worker = None
    WorkerConfig = None
    HandlerConfig = None
    LogActionConfig = None
    BenchmarkConfig = None

__all__ = [
    "VastAI",
    "Serverless",
    "ServerlessRequest",
    "Endpoint",
    "Worker",
    "WorkerConfig",
    "HandlerConfig",
    "LogActionConfig",
    "BenchmarkConfig"
]
