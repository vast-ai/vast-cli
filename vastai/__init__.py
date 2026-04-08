import logging as _logging
import os as _os

_VAST_LOG_LEVELS = {
    "critical": _logging.CRITICAL,
    "error": _logging.ERROR,
    "warning": _logging.WARNING,
    "info": _logging.INFO,
    "debug": _logging.DEBUG,
}
_env_level = _os.environ.get("VAST_LOG_LEVEL", "").lower()
_level = (
    _VAST_LOG_LEVELS.get(_env_level, _logging.WARNING) if _env_level else _logging.INFO
)

logger = _logging.getLogger("vastai")
logger.setLevel(_level)
if not logger.handlers:
    _handler = _logging.StreamHandler()
    _handler.setFormatter(_logging.Formatter("%(levelname)s - %(message)s"))
    logger.addHandler(_handler)
    logger.propagate = False

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
