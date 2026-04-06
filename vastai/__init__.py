from .sdk import VastAI

try:
    from .serverless.client.client import (
        Serverless,
        CoroutineServerless,
        ServerlessRequest,
    )
    from .serverless.client.request_status import RequestStatus
    from .serverless.client.endpoint import Endpoint
    from .serverless.server.worker import Worker
    from .serverless.server.worker import WorkerConfig, HandlerConfig, LogActionConfig, BenchmarkConfig
    from .sync.client import SyncClient
    from .async_.client import AsyncClient
    from .serverless.remote import Deployment
except ImportError:
    # Serverless dependencies (aiohttp, etc.) not installed
    Deployment = None
    Serverless = None
    CoroutineServerless = None
    ServerlessRequest = None
    RequestStatus = None
    Endpoint = None
    Worker = None
    WorkerConfig = None
    HandlerConfig = None
    LogActionConfig = None
    BenchmarkConfig = None
    SyncClient = None
    AsyncClient = None

__all__ = [
    "VastAI",
    "Deployment",
    "Serverless",
    "CoroutineServerless",
    "ServerlessRequest",
    "RequestStatus",
    "Endpoint",
    "Worker",
    "WorkerConfig",
    "HandlerConfig",
    "LogActionConfig",
    "BenchmarkConfig",
    "SyncClient",
    "AsyncClient",
]
