"""Shared pytest fixtures for vast-sdk tests.

Fixtures follow unit-test-requirements: one fixture per concept, defined in
conftest.py for reuse across test files.
"""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vastai.serverless.server.worker import (
    WorkerConfig,
    HandlerConfig,
    BenchmarkConfig,
)


# ---------------------------------------------------------------------------
# CLI fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def cli_parser():
    """Import all command modules and return the fully-populated parser."""
    from vastai.cli.main import parser
    from vastai.cli.commands import (  # noqa: F401
        instances, offers, machines, teams, keys, endpoints,
        billing, storage, clusters, auth, misc, deployments,
    )
    from vastai.cli.util import server_url_default, api_key_guard
    parser.add_argument("--url", help="Server REST API URL", default=server_url_default)
    parser.add_argument("--retry", help="Retry limit", default=3)
    parser.add_argument("--explain", action="store_true", help="Verbose")
    parser.add_argument("--raw", action="store_true", help="Raw json")
    parser.add_argument("--full", action="store_true", help="Full output")
    parser.add_argument("--curl", action="store_true", help="Curl equiv")
    parser.add_argument("--api-key", help="API Key", type=str, required=False, default=api_key_guard)
    parser.add_argument("--no-color", action="store_true", help="Disable color")
    return parser


@pytest.fixture
def parse_argv(cli_parser):
    """Return a callable that parses an argv list into an args namespace."""
    def _parse(argv):
        args = cli_parser.parse_args(argv)
        # Resolve api_key_guard to None for tests
        from vastai.cli.util import api_key_guard
        if args.api_key is api_key_guard:
            args.api_key = "test-api-key"
        if not hasattr(args, 'url'):
            args.url = "https://console.vast.ai"
        if not hasattr(args, 'retry'):
            args.retry = 3
        if not hasattr(args, 'explain'):
            args.explain = False
        if not hasattr(args, 'raw'):
            args.raw = False
        if not hasattr(args, 'full'):
            args.full = False
        if not hasattr(args, 'curl'):
            args.curl = False
        if not hasattr(args, 'no_color'):
            args.no_color = False
        if not hasattr(args, 'quiet'):
            args.quiet = False
        return args
    return _parse


# ---------------------------------------------------------------------------
# Mock HTTP response factory (CLI tests)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_response():
    """Factory for mock requests.Response objects."""
    def _make(status_code=200, json_data=None, headers=None):
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = json_data if json_data is not None else {}
        resp.headers = headers or {"Content-Type": "application/json"}
        if 400 <= status_code < 600:
            from requests.exceptions import HTTPError
            resp.raise_for_status.side_effect = HTTPError(response=resp)
        else:
            resp.raise_for_status.return_value = None
        return resp
    return _make


# ---------------------------------------------------------------------------
# Server Worker test helpers (mocks for generate_client_response etc.)
# ---------------------------------------------------------------------------


@pytest.fixture
def make_mock_web_request():
    """Factory: create a mock object for aiohttp web.Request in handler tests."""
    def _make(spec_request: bool = False):
        if spec_request:
            from aiohttp import web
            return MagicMock(spec=web.Request)
        return MagicMock()
    return _make


@pytest.fixture
def make_mock_model_response():
    """Factory: create a mock model response for generate_client_response tests.

    Returns a callable that accepts content_type, body, status, and optional
    stream_chunks. If stream_chunks is provided, content.iter_any is an async
    generator yielding those chunks; otherwise read() returns body.
    """
    def _make(
        content_type: str = "application/json",
        body: bytes | None = None,
        status: int = 200,
        stream_chunks: list[bytes] | None = None,
    ):
        mock = MagicMock()
        mock.content_type = content_type
        mock.status = status
        mock.headers = MagicMock()
        mock.headers.get = MagicMock(return_value=None)
        if stream_chunks is not None:
            async def _iter():
                for c in stream_chunks:
                    yield c
            mock.content.iter_any = _iter
        else:
            mock.read = AsyncMock(return_value=body or b"")
        return mock
    return _make


# ---------------------------------------------------------------------------
# Mock VastClient (CLI tests)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_client(mock_response):
    """A MagicMock VastClient whose get/post/put/delete return 200 by default."""
    client = MagicMock()
    default_resp = mock_response(200, {})
    client.get.return_value = default_resp
    client.post.return_value = default_resp
    client.put.return_value = default_resp
    client.delete.return_value = default_resp
    client.api_key = "test-api-key"
    client.server_url = "https://console.vast.ai"
    client.retry = 3
    client.explain = False
    client.curl = False
    return client


# ---------------------------------------------------------------------------
# Patch get_client across all CLI command modules
# ---------------------------------------------------------------------------

COMMAND_MODULES = [
    "vastai.cli.commands.billing",
    "vastai.cli.commands.auth",
    "vastai.cli.commands.offers",
    "vastai.cli.commands.instances",
    "vastai.cli.commands.machines",
    "vastai.cli.commands.keys",
    "vastai.cli.commands.endpoints",
    "vastai.cli.commands.storage",
    "vastai.cli.commands.teams",
    "vastai.cli.commands.clusters",
    "vastai.cli.commands.misc",
    "vastai.cli.commands.deployments",
]


@pytest.fixture
def patch_get_client(mock_client):
    """Patch get_client in all command modules to return mock_client."""
    patches = []
    for mod in COMMAND_MODULES:
        p = patch(f"{mod}.get_client", return_value=mock_client)
        patches.append(p)
        p.start()
    yield mock_client
    for p in patches:
        p.stop()


# ---------------------------------------------------------------------------
# Live test fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def api_key():
    """Read VAST_API_KEY from environment; skip if missing."""
    key = os.environ.get("VAST_API_KEY")
    if not key:
        pytest.skip("VAST_API_KEY not set")
    return key


@pytest.fixture(scope="session")
def live_client(api_key):
    """Real VastClient for live tests."""
    from vastai.api.client import VastClient
    return VastClient(api_key=api_key)


# ---------------------------------------------------------------------------
# Client Worker (vastai.serverless.client.worker) fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def minimal_client_worker_dict() -> dict:
    """Minimal dict with only required id field for client Worker.from_dict tests."""
    return {"id": 1}


@pytest.fixture
def full_client_worker_dict() -> dict:
    """Complete dict with all Worker fields for client Worker.from_dict tests.

    Returns a dict that exercises every field. Tests may override specific
    keys to test edge cases.
    """
    return {
        "id": 42,
        "status": "RUNNING",
        "cur_load": 0.5,
        "new_load": 0.6,
        "cur_load_rolling_avg": 0.55,
        "cur_perf": 1.2,
        "perf": 1.1,
        "measured_perf": 1.0,
        "dlperf": 0.9,
        "reliability": 0.95,
        "reqs_working": 3,
        "disk_usage": 0.4,
        "loaded_at": 1700000000.0,
        "started_at": 1699999000.0,
    }


# ---------------------------------------------------------------------------
# Server Worker (vastai.serverless.server.worker) fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def minimal_worker_config() -> WorkerConfig:
    """WorkerConfig with minimal required fields for EndpointHandlerFactory.

    Use when tests need a valid config without custom handlers.
    """
    return WorkerConfig(
        model_server_url="http://localhost",
        model_server_port=8000,
    )


@pytest.fixture
def worker_config_with_handler():
    """Factory fixture: build WorkerConfig with HandlerConfig(s) and BenchmarkConfig.

    Returns a callable that accepts route, dataset, and optional extra handlers.
    Use to avoid repeating WorkerConfig + HandlerConfig + BenchmarkConfig setup.
    """

    def _make(
        route: str = "/predict",
        dataset: list | None = None,
        extra_handlers: list[HandlerConfig] | None = None,
    ) -> WorkerConfig:
        if dataset is None:
            dataset = [{"input": "test"}]
        handlers = [
            HandlerConfig(
                route=route,
                benchmark_config=BenchmarkConfig(dataset=dataset),
            ),
        ]
        if extra_handlers:
            handlers.extend(extra_handlers)
        return WorkerConfig(
            model_server_url="http://localhost",
            model_server_port=8000,
            handlers=handlers,
        )

    return _make


@pytest.fixture
def worker_config_from_handlers():
    """Factory fixture: build WorkerConfig from an explicit list of HandlerConfigs.

    Returns a callable that accepts a list of HandlerConfig and returns WorkerConfig
    with standard model_server_url and model_server_port. Use when tests need custom
    handler options (request_parser, response_generator, payload_class, etc.).
    """

    def _make(handlers: list[HandlerConfig]) -> WorkerConfig:
        return WorkerConfig(
            model_server_url="http://localhost",
            model_server_port=8000,
            handlers=handlers,
        )

    return _make


# ---------------------------------------------------------------------------
# Connection (vastai.serverless.client.connection) fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def make_sse_response():
    """Factory: create mock aiohttp response with SSE/JSONL stream content.

    Returns a callable that accepts an iterable of bytes chunks and returns
    a mock response whose content.iter_any yields those chunks.

    Use for _iter_sse_json tests.
    """

    def _make(chunks):
        async def mock_iter():
            for c in chunks:
                yield c

        mock_resp = MagicMock()
        mock_resp.content.iter_any = mock_iter
        return mock_resp

    return _make


@pytest.fixture
def make_mock_http_response():
    """Factory: create mock aiohttp response for async with session.get/post.

    Returns a callable that accepts status, text, json, json_side_effect
    and returns a mock response configured for use in 'async with' context.
    Use for _make_request tests.
    """

    def _make(
        status: int = 200,
        text: str = "",
        json_data=None,
        json_side_effect=None,
    ):
        mock_resp = MagicMock()
        mock_resp.status = status
        mock_resp.headers = {}
        mock_resp.text = AsyncMock(return_value=text)
        mock_resp.json = AsyncMock(
            return_value=json_data,
            side_effect=json_side_effect,
        )
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=None)
        return mock_resp

    return _make


@pytest.fixture
def make_mock_make_request_client():
    """Factory: create mock session and client for _make_request.

    Returns a callable that accepts a mock response and returns
    (mock_session, mock_client) configured for _make_request.
    """

    def _make(mock_resp):
        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=mock_resp)
        mock_session.post = AsyncMock()

        mock_client = MagicMock()
        mock_client._get_session = AsyncMock(return_value=mock_session)
        mock_client.get_ssl_context = AsyncMock(return_value=None)

        return mock_session, mock_client

    return _make


@pytest.fixture
def patch_build_kwargs():
    """Patch _build_kwargs for _make_request tests.

    Yields the mock; tests run with _build_kwargs patched to return
    standard kwargs (headers, params, timeout).
    """
    with patch(
        "vastai.serverless.client.connection._build_kwargs"
    ) as mock_build:
        mock_build.return_value = {
            "headers": {},
            "params": {},
            "timeout": MagicMock(),
        }
        yield mock_build


@pytest.fixture
def make_mock_session():
    """Factory: create mock aiohttp session for _open_once tests.

    Returns a callable that accepts get_returns and post_returns (optional)
    and returns a mock session with get/post configured.
    """

    def _make(get_returns=None, post_returns=None):
        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=get_returns or MagicMock())
        mock_session.post = AsyncMock(return_value=post_returns or MagicMock())
        return mock_session

    return _make


@pytest.fixture
def build_kwargs_defaults():
    """Default kwargs for _build_kwargs tests.

    Returns a dict of common defaults; tests can override as needed.
    """
    return {
        "headers": {},
        "params": {},
        "ssl_context": None,
        "timeout": 30.0,
        "body": None,
        "method": "GET",
        "stream": False,
    }
