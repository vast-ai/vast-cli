"""Shared pytest fixtures for vast-sdk tests.

Fixtures follow unit-test-requirements: one fixture per concept, defined in
conftest.py for reuse across test files. Pyworker ``Metrics`` helpers live in the
``# Pyworker server`` section below.

One fixture name per *kind* of resource; use factory callables for variants
(``make_request_http_mocks``, ``make_route_response_mock``, ``server_worker_config``,
``client_worker_dict``, ``make_session_mock``, ``make_client_session``, ``session_on_mock_endpoint``,
``make_mock_endpoint_for_session``, ``make_delegate_endpoint`` (only factory for ``Endpoint`` on
``mock_serverless_client``), ``make_serverless_bound_session``,
``make_test_endpoint``,
``make_backend_http_request``, ``make_mock_root_logger``, …) instead of parallel fixtures.

Pyworker: ``pyworker_backend`` (Backend with Metrics mocked), ``patch_pyworker_backend_class``,
``make_pyworker_session`` (only factory for server ``Session``), ``valid_auth_data_dict`` (AuthData-shaped JSON).

Serverless pyworker: ``serverless_backend_and_handler_default`` (default ``Backend`` + handler),
``serverless_tracked_runner_and_tcp_site`` (AppRunner/TCPSite capture bundle for ``server.lib.server``),
``run_serverless_start_server_async_patched`` (async helper applying AppRunner/TCPSite/_start_tracking patches for ``start_server_async``),
``make_patch_skip_backend_run_session_on_close`` / ``make_patch_mock_backend_close_session``,
``attach_serverless_backend_mock_aiohttp_session`` (single mock ``ClientSession`` on ``backend.session``),
``make_serverless_fetch_pubkey_client_session_return_value``, ``make_serverless_backend_session_get_steps``,
``serverless_backend_ok_json_response_chain``, ``make_serverless_mock_request_with_transport``,
``make_serverless_test_rsa_key`` (RSA key factory for signature tests).

Serverless SSL: ``serverless_ssl_self_signed_cert_pem``, ``serverless_ssl_ca_chain_without_key_cert_sign``,
``patch_serverless_ssl_cert_download`` (callable returning a ``ClientSession`` download patch).

An autouse fixture restores the ``Serverless`` logger after each test so global
logging state follows RAII and cannot leak between cases.
"""

from __future__ import annotations

import asyncio
import base64
import dataclasses
import datetime
import inspect
import json
import logging
import os
from contextlib import ExitStack, contextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientResponseError, web
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15

from vastai.serverless.client.client import Serverless, ServerlessRequest
from vastai.serverless.client.endpoint import Endpoint
from vastai.serverless.client.session import Session
from vastai.serverless.server.lib.backend import Backend
from vastai.serverless.server.lib import server as vast_serverless_server_mod
from vastai.serverless.server.lib.metrics import get_url
from vastai.serverless.server.lib.data_types import (
    RequestMetrics,
    Session as PyworkerSession,
)
from vastai.serverless.server.worker import (
    WorkerConfig,
    HandlerConfig,
    BenchmarkConfig,
    EndpointHandlerFactory,
)


def _attach_mock_aiohttp_session(sl: Serverless) -> None:
    """Put an open mocked aiohttp-backed session on ``sl._session`` (in-place)."""
    mock_sess = MagicMock()
    mock_sess.closed = False
    mock_sess.close = AsyncMock()
    sl._session = mock_sess


# ---------------------------------------------------------------------------
# Global RAII (resource cleanup after every test)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _restore_serverless_logger_state():
    """Snapshot and restore the ``Serverless`` client logger after each test.

    ``Serverless.__init__`` configures ``logging.getLogger("Serverless")``. Leaked
    handlers or ``propagate=False`` can make later tests call ``time.time()`` via
    logging and break strict clock mocks.
    """
    log = logging.getLogger("Serverless")
    old_handlers = list(log.handlers)
    old_level = log.level
    old_propagate = log.propagate
    old_disabled = log.disabled
    yield
    log.handlers.clear()
    for h in old_handlers:
        log.addHandler(h)
    log.setLevel(old_level)
    log.propagate = old_propagate
    log.disabled = old_disabled


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
        mock.headers.copy = MagicMock(return_value={})
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
# Client Worker (vastai.serverless.client.worker) — single dict factory
# ---------------------------------------------------------------------------

_FULL_CLIENT_WORKER_DICT = {
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


@pytest.fixture
def client_worker_dict():
    """Single factory for API worker payload dicts (``minimal`` / ``full`` + overrides)."""

    def _make(kind: str = "minimal", **overrides: object) -> dict:
        if kind == "minimal":
            d = {"id": 1}
        elif kind == "full":
            d = dict(_FULL_CLIENT_WORKER_DICT)
        else:
            raise ValueError(f"unknown kind {kind!r}, use 'minimal' or 'full'")
        d.update(overrides)
        return d

    return _make


# ---------------------------------------------------------------------------
# Server Worker (vastai.serverless.server.worker) — single WorkerConfig factory
# ---------------------------------------------------------------------------


@pytest.fixture
def server_worker_config():
    """Single factory for :class:`WorkerConfig` (minimal / handler / from_handlers)."""

    def _make(
        kind: str,
        *,
        route: str = "/predict",
        dataset: list | None = None,
        extra_handlers: list[HandlerConfig] | None = None,
        handlers: list[HandlerConfig] | None = None,
    ) -> WorkerConfig:
        if kind == "minimal":
            return WorkerConfig(
                model_server_url="http://localhost",
                model_server_port=8000,
            )
        if kind == "handler":
            if dataset is None:
                dataset = [{"input": "test"}]
            hs = [
                HandlerConfig(
                    route=route,
                    benchmark_config=BenchmarkConfig(dataset=dataset),
                ),
            ]
            if extra_handlers:
                hs.extend(extra_handlers)
            return WorkerConfig(
                model_server_url="http://localhost",
                model_server_port=8000,
                handlers=hs,
            )
        if kind == "from_handlers":
            if handlers is None:
                raise ValueError("from_handlers requires handlers=")
            return WorkerConfig(
                model_server_url="http://localhost",
                model_server_port=8000,
                handlers=handlers,
            )
        raise ValueError(f"unknown kind {kind!r}")

    return _make


# ---------------------------------------------------------------------------
# Pyworker Backend / Worker (server.lib.backend, server.worker) — single mocks
# ---------------------------------------------------------------------------


@pytest.fixture
def patch_pyworker_backend_class():
    """Patch :class:`Backend` in ``server.lib.backend`` with ``MagicMock`` (constructor)."""
    from vastai.serverless.server.lib import backend as backend_mod

    with patch.object(backend_mod, "Backend", MagicMock()) as mock_cls:
        yield mock_cls


@pytest.fixture
def make_mock_root_logger():
    """Factory: mock root logger for :class:`Worker` ``__init__`` logging branches.

    Returns ``(root_mock, handler_mock_or_none)`` — ``handler_mock_or_none`` is the
    first handler when ``with_handlers=True``, else ``None``.
    """

    def _make(*, with_handlers: bool):
        mock_root = MagicMock()
        mock_root.setLevel = MagicMock()
        if with_handlers:
            h = MagicMock()
            mock_root.handlers = [h]
            mock_root.addHandler = MagicMock()
            return mock_root, h
        mock_root.handlers = []
        mock_root.addHandler = MagicMock()
        return mock_root, None

    return _make


@pytest.fixture
def pyworker_backend():
    """Single :class:`Backend` test instance; ``Metrics`` is mocked (no ``CONTAINER_ID`` env)."""
    from vastai.serverless.server.lib.backend import Backend
    from vastai.serverless.server.lib.data_types import LogAction

    with patch(
        "vastai.serverless.server.lib.backend.Metrics",
        return_value=MagicMock(),
    ):
        return Backend(
            model_server_url="http://localhost:8000",
            model_log_file="/tmp/model.log",
            benchmark_handler=MagicMock(),
            log_actions=[(LogAction.Info, "ready")],
        )


@pytest.fixture
def make_backend_http_request():
    """Factory: mock ``aiohttp.web.Request`` with ``.json`` async for Backend handler tests."""

    def _make(
        *,
        json_data=None,
        json_side_effect=None,
    ):
        req = MagicMock()
        if json_side_effect is not None:
            req.json = AsyncMock(side_effect=json_side_effect)
        else:
            req.json = AsyncMock(
                return_value=json_data if json_data is not None else {}
            )
        return req

    return _make


@pytest.fixture
def web_json_body():
    """Callable: parse JSON dict from ``web.json_response`` result ``.body`` bytes."""

    def _parse(resp):
        import json

        return json.loads(resp.body.decode())

    return _parse


@pytest.fixture
def valid_auth_data_dict():
    """Valid ``auth_data`` payload for :class:`AuthData` / ``get_data_from_request`` tests."""
    return {
        "cost": "1",
        "endpoint": "/predict",
        "reqnum": 1,
        "request_idx": 0,
        "signature": "sig",
        "url": "http://example.com",
    }


# ---------------------------------------------------------------------------
# Serverless pyworker (Backend, server.lib.server) fixtures
# ---------------------------------------------------------------------------

# Metrics() reads container/network env at Backend init; use with patch.dict in factories.
SERVERLESS_METRICS_TEST_ENV = {
    "CONTAINER_ID": "1",
    "REPORT_ADDR": "https://run.vast.ai",
    "WORKER_PORT": "8080",
    "PUBLIC_IPADDR": "127.0.0.1",
    "VAST_TCP_PORT_8080": "8080",
}


@pytest.fixture
def serverless_metrics_test_env() -> dict:
    """Copy of env vars required to construct Metrics inside Backend for unit tests."""
    return dict(SERVERLESS_METRICS_TEST_ENV)


def _serverless_worker_config_one_handler(
    route: str = "/predict",
    *,
    allow_parallel: bool = True,
    max_queue_time: float | None = None,
) -> WorkerConfig:
    return WorkerConfig(
        model_server_url="http://localhost",
        model_server_port=8000,
        model_log_file="/tmp/nonexistent-model.log",
        handlers=[
            HandlerConfig(
                route=route,
                benchmark_config=BenchmarkConfig(dataset=[{"input": {}}]),
                allow_parallel_requests=allow_parallel,
                max_queue_time=max_queue_time,
            ),
        ],
        max_sessions=None,
    )


@pytest.fixture
def make_serverless_backend_and_handler():
    """Factory: build Backend + generic EndpointHandler for /predict (see EndpointHandlerFactory).

    ``WorkerConfig.max_sessions`` of ``None`` is mapped to ``Backend(max_sessions=0)`` because
    ``session_create_handler`` treats ``0`` and ``None`` as unlimited (no cap).
    """

    def _make(
        *,
        unsecured: bool = True,
        max_sessions: int | None = None,
        allow_parallel: bool = True,
        max_queue_time: float | None = None,
        remote_function=None,
    ) -> tuple[Backend, object]:
        config = _serverless_worker_config_one_handler(
            allow_parallel=allow_parallel,
            max_queue_time=max_queue_time,
        )
        if remote_function is not None:
            config.handlers[0] = dataclasses.replace(
                config.handlers[0], remote_function=remote_function
            )
        if max_sessions is not None:
            config = WorkerConfig(
                model_server_url=config.model_server_url,
                model_server_port=config.model_server_port,
                model_log_file=config.model_log_file,
                handlers=config.handlers,
                max_sessions=max_sessions,
            )
        factory = EndpointHandlerFactory(config)
        benchmark = factory.get_benchmark_handler()
        handler = factory.get_handler("/predict")
        assert handler is not None
        effective_max = (
            max_sessions if max_sessions is not None else config.max_sessions
        )
        if effective_max is None:
            effective_max = 0
        with patch.dict(os.environ, SERVERLESS_METRICS_TEST_ENV, clear=False):
            get_url.cache_clear()
            backend = Backend(
                model_server_url="http://localhost:8000",
                model_log_file=config.model_log_file,
                benchmark_handler=benchmark,
                log_actions=[],
                max_sessions=effective_max,
                unsecured=unsecured,
            )
            get_url.cache_clear()
        return backend, handler

    return _make


@pytest.fixture
def parse_serverless_aiohttp_json():
    """Factory: decode JSON body from aiohttp web.Response in synchronous tests.

    When ``resp.body`` is ``None``, returns ``{}`` (same as empty JSON object) so
    status-only tests need not branch; use explicit ``resp.body`` checks if you
    must distinguish missing body from ``{}``.
    """

    def _parse(resp: web.StreamResponse) -> dict | list:
        raw = resp.body
        if raw is None:
            return {}
        return json.loads(raw.decode())

    return _parse


@pytest.fixture
def make_serverless_json_http_request():
    """Factory: mock aiohttp Request; pass str body to simulate JSON decode errors."""

    def _make(data: dict | str) -> MagicMock:
        req = MagicMock(spec=web.Request)
        if isinstance(data, str):
            req.json = AsyncMock(side_effect=json.JSONDecodeError("err", data, 0))
        else:
            req.json = AsyncMock(return_value=data)
        return req

    return _make


@pytest.fixture
def make_serverless_auth_payload():
    """Factory: minimal valid auth_data + payload dict for generic pyworker handler tests."""

    def _make(
        *,
        url: str = "http://example.com/predict",
        signature: str = "unused-in-unsecured",
        reqnum: int = 1,
    ) -> dict:
        return {
            "auth_data": {
                "cost": "1",
                "endpoint": "/predict",
                "reqnum": reqnum,
                "request_idx": 42,
                "signature": signature,
                "url": url,
            },
            "payload": {"input": {}},
        }

    return _make


@pytest.fixture
def make_serverless_signed_auth_payload(make_serverless_auth_payload):
    """Factory: auth payload with PKCS1-v1.5 signature matching Backend.__check_signature."""

    def _signed(url: str, rsa_key) -> dict:
        message = json.dumps({"url": url}, indent=4, sort_keys=True)
        h = SHA256.new(message.encode())
        sig = pkcs1_15.new(rsa_key).sign(h)
        return make_serverless_auth_payload(
            url=url,
            signature=base64.b64encode(sig).decode("ascii"),
            reqnum=7,
        )

    return _signed


@pytest.fixture
def serverless_backend_testkit(
    make_serverless_backend_and_handler,
    parse_serverless_aiohttp_json,
    make_serverless_json_http_request,
    make_serverless_auth_payload,
    make_serverless_signed_auth_payload,
):
    """Bundle common pyworker Backend test helpers (single parameter for test methods)."""
    return SimpleNamespace(
        make_backend=make_serverless_backend_and_handler,
        response_json=parse_serverless_aiohttp_json,
        json_request=make_serverless_json_http_request,
        auth_payload=make_serverless_auth_payload,
        signed_auth=make_serverless_signed_auth_payload,
    )


@pytest.fixture
def serverless_backend_and_handler_default(make_serverless_backend_and_handler):
    """Fresh ``(Backend, handler)`` with defaults for pyworker serverless unit tests."""
    return make_serverless_backend_and_handler()


@pytest.fixture
def serverless_tracked_runner_and_tcp_site(
    make_serverless_tracked_app_runner,
    make_serverless_tracked_tcp_site,
):
    """Tracked ``AppRunner`` + ``TCPSite`` side effects for ``server.lib.server`` tests."""
    apps_seen, app_runner = make_serverless_tracked_app_runner()
    tcp_calls, tcp_site = make_serverless_tracked_tcp_site()
    return SimpleNamespace(
        apps_seen=apps_seen,
        app_runner=app_runner,
        tcp_calls=tcp_calls,
        tcp_site=tcp_site,
    )


@pytest.fixture
def make_serverless_tracked_app_runner():
    """Factory: returns (captured_apps_list, AppRunner side_effect) for patching web.AppRunner."""

    def _make():
        captured: list = []

        def app_runner(app: web.Application, **kwargs):
            captured.append(app)
            m = MagicMock()
            m.setup = AsyncMock()
            return m

        return captured, app_runner

    return _make


@pytest.fixture
def make_serverless_tracked_tcp_site():
    """Factory: returns (captured_kwargs_per_call, TCPSite side_effect) for patching web.TCPSite."""

    def _make():
        captured: list = []

        def tcp_site(*args, **kwargs):
            captured.append(kwargs)
            m = MagicMock()
            m.start = AsyncMock()
            return m

        return captured, tcp_site

    return _make


@pytest.fixture
def serverless_gather_await_all():
    """Async gather replacement that awaits each awaitable (for mocked ``site.start()``).

    If an early awaitable raises :class:`Exception`, remaining awaitables are cleaned up:
    :class:`asyncio.Task` / :class:`asyncio.Future` are cancelled; bare coroutines are
    closed via ``.close()``; other awaitables get ``.close()`` when present (same idea as
    ``serverless_gather_raise_bind_failed``). Uses ``Exception`` (not ``BaseException``)
    so ``KeyboardInterrupt`` / ``SystemExit`` propagate for local debugging.

    ``**kwargs`` are accepted for call-shape parity with :func:`asyncio.gather` but ignored
    (this stub does not implement ``return_exceptions`` etc.).
    """

    async def _gather(*aws, **kwargs):
        pending = list(aws)
        idx = -1
        try:
            for idx in range(len(pending)):
                await pending[idx]
            return None
        except Exception:
            for j in range(idx + 1, len(pending)):
                aw = pending[j]
                if isinstance(aw, asyncio.Task):
                    aw.cancel()
                elif isinstance(aw, asyncio.Future):
                    aw.cancel()
                elif inspect.iscoroutine(aw):
                    aw.close()
                elif inspect.isawaitable(aw):
                    closer = getattr(aw, "close", None)
                    if callable(closer):
                        closer()
            raise

    return _gather


@pytest.fixture
def serverless_gather_raise_bind_failed():
    """Simulate gather() failing without leaking un-awaited coroutine objects.

    ``start_server_async`` does ``await gather(site.start(), http_site.start(),
    backend._start_tracking())``. Those three call expressions run before ``gather``;
    if the patched ``gather`` raises without consuming them, CPython warns on GC.
    This replacement closes each awaitable then raises like a failed bind.
    """

    async def _gather(*aws, **kwargs):
        for aw in aws:
            if inspect.isawaitable(aw):
                if isinstance(aw, asyncio.Task):
                    aw.cancel()
                else:
                    closer = getattr(aw, "close", None)
                    if callable(closer):
                        closer()
        raise RuntimeError("bind failed")

    return _gather


@pytest.fixture
def serverless_error_beacon_mocks():
    """Patches Metrics + sleep so server error beacon runs then exits on second sleep.

    Yields the MagicMock for Metrics._model_errored.
    """
    sm = vast_serverless_server_mod
    with patch.object(
        sm.Metrics, "_Metrics__send_metrics_and_reset", new_callable=AsyncMock
    ):
        with patch.object(sm.Metrics, "_model_errored") as mock_model_errored:
            with patch.object(sm.Metrics, "aclose", new_callable=AsyncMock):
                sleep_mock = AsyncMock(side_effect=[None, RuntimeError("stop-beacon")])
                with patch.object(sm.asyncio, "sleep", sleep_mock):
                    yield mock_model_errored


@pytest.fixture
def serverless_aiohttp_route_path_tuples():
    """Factory: list (method, path_string) for each route on an aiohttp Application."""

    def _paths(app: web.Application) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        for r in app.router.routes():
            resource = getattr(r, "resource", None)
            canonical = getattr(resource, "canonical", None) if resource else None
            path = str(canonical) if canonical is not None else str(r)
            out.append((r.method, path))
        return out

    return _paths


def _serverless_aiohttp_async_enter_context(
    enter_result: Any | None = None,
    *,
    enter_side_effect: BaseException | None = None,
) -> MagicMock:
    """``async with`` context manager mock (``__aenter__`` / ``__aexit__``)."""
    cm = MagicMock()
    if enter_side_effect is not None:
        cm.__aenter__ = AsyncMock(side_effect=enter_side_effect)
    else:
        cm.__aenter__ = AsyncMock(return_value=enter_result)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _attach_serverless_backend_mock_aiohttp_session(
    backend: Backend,
    *,
    spy_only: bool = False,
    post_side_effect: BaseException | None = None,
    response_text: str = "ok",
    response_status: int = 200,
    get_context_return: MagicMock | None = None,
    get_side_effect=None,
) -> MagicMock:
    """Attach one mock aiohttp session to ``backend.session`` (GET + POST)."""
    mock_sess = MagicMock()
    if get_side_effect is not None:
        mock_sess.get = MagicMock(side_effect=get_side_effect)
    elif get_context_return is not None:
        mock_sess.get = MagicMock(return_value=get_context_return)
    else:
        mock_sess.get = MagicMock()

    if spy_only:
        mock_sess.post = MagicMock()
    elif post_side_effect is not None:
        mock_sess.post = MagicMock(side_effect=post_side_effect)
    else:
        mock_resp = MagicMock()
        mock_resp.status = response_status
        mock_resp.text = AsyncMock(return_value=response_text)
        mock_sess.post = MagicMock(
            return_value=_serverless_aiohttp_async_enter_context(mock_resp)
        )

    object.__setattr__(backend, "session", mock_sess)
    return mock_sess


@pytest.fixture
def attach_serverless_backend_mock_aiohttp_session():
    """Attach a single mock aiohttp ``ClientSession`` on ``backend.session`` (GET + POST).

    Call before any code path reads ``backend.session`` so the real ``cached_property``
    is never evaluated (avoids opening a real ``TCPConnector`` / ``ClientSession``).

    Post: default successful JSON/text response; ``spy_only`` / ``post_side_effect`` for variants.
    Get: ``get_context_return`` (static async CM from ``make_serverless_aiohttp_get_context_manager``)
    or ``get_side_effect`` (e.g. from ``make_serverless_backend_session_get_steps``).
    """
    return _attach_serverless_backend_mock_aiohttp_session


@pytest.fixture
def make_serverless_aiohttp_get_context_manager():
    """Factory: build an async context manager for one aiohttp response object."""
    return _serverless_aiohttp_async_enter_context


@pytest.fixture
def make_serverless_fetch_pubkey_client_session_return_value():
    """Return value for ``patch(..., ClientSession, return_value=...)`` in ``Backend._fetch_pubkey`` tests."""

    def _make(
        *,
        pem_text: str | None = None,
        session_enter_error: BaseException | None = None,
    ) -> MagicMock:
        if session_enter_error is not None:
            return _serverless_aiohttp_async_enter_context(
                enter_side_effect=session_enter_error
            )
        if pem_text is None:
            raise ValueError("pem_text is required when session_enter_error is None")
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.text = AsyncMock(return_value=pem_text)
        mock_client = MagicMock()
        mock_client.get = MagicMock(
            return_value=_serverless_aiohttp_async_enter_context(mock_resp)
        )
        return _serverless_aiohttp_async_enter_context(mock_client)

    return _make


@pytest.fixture
def make_serverless_sleep_cancel_on_nth_call():
    """Async ``sleep`` replacement that raises ``CancelledError`` starting at the *n*-th invocation."""

    def _make(n: int):
        count = [0]

        async def _sleep(_delay: float) -> None:
            count[0] += 1
            if count[0] >= n:
                raise asyncio.CancelledError()

        return _sleep

    return _make


@pytest.fixture
def make_serverless_backend_healthcheck_attrs():
    """Set ``healthcheck_url`` / ``_Backend__start_healthcheck`` / ``_Backend__healthcheck_succeeded``."""

    def _apply(
        backend: Backend,
        *,
        url: str,
        start: bool = True,
        succeeded: bool = False,
    ) -> None:
        object.__setattr__(backend, "healthcheck_url", url)
        object.__setattr__(backend, "_Backend__start_healthcheck", start)
        object.__setattr__(backend, "_Backend__healthcheck_succeeded", succeeded)

    return _apply


@pytest.fixture
def make_serverless_backend_session_get_steps():
    """Build ``session.get`` side_effect: each call returns a CM for a response mock or raises."""

    def _make(steps: list[Any]):
        seq = iter(steps)

        def _get(*_a, **_k):
            step = next(seq)
            if isinstance(step, BaseException):
                raise step
            return _serverless_aiohttp_async_enter_context(step)

        return _get

    return _make


@pytest.fixture
def make_serverless_mock_request_with_transport():
    """Build ``(mock_request, mock_transport)`` for ``Session.requests`` transport tests."""

    def _make(*, close_side_effect: BaseException | None = None):
        mock_tr = MagicMock()
        mock_tr.is_closing.return_value = False
        if close_side_effect is not None:
            mock_tr.close.side_effect = close_side_effect
        mock_req = MagicMock()
        mock_req.transport = mock_tr
        return mock_req, mock_tr

    return _make


@pytest.fixture
def serverless_backend_ok_json_response_chain():
    """Shared ``MagicMock`` model + async stubs for successful ``__call_backend`` / ``generate_client_response``."""
    mock_model = MagicMock()

    async def call_backend(**kwargs):
        return mock_model

    async def gen_client_response(_client_request, _model_response):
        return web.json_response({"ok": True})

    return SimpleNamespace(
        mock_model=mock_model,
        call_backend=call_backend,
        gen_client_response=gen_client_response,
    )


@pytest.fixture
def make_patch_skip_backend_run_session_on_close():
    """Return ``patch.object(backend, _Backend__run_session_on_close, AsyncMock)`` context manager."""

    def _patch(backend: Backend):
        return patch.object(
            backend, "_Backend__run_session_on_close", new_callable=AsyncMock
        )

    return _patch


@pytest.fixture
def make_patch_mock_backend_close_session():
    """Return ``patch.object(backend, _Backend__close_session, AsyncMock)`` context manager."""

    def _patch(backend: Backend):
        return patch.object(backend, "_Backend__close_session", new_callable=AsyncMock)

    return _patch


@pytest.fixture
def make_serverless_test_rsa_key():
    """Factory: small RSA key for Backend signature tests (not for production crypto)."""

    def _make(bits: int = 1024):
        return RSA.generate(bits)

    return _make


@pytest.fixture
def run_serverless_start_server_async_patched(serverless_tracked_runner_and_tcp_site):
    """Async callable: apply env + AppRunner + TCPSite + _start_tracking patches, then ``start_server_async``.

    Returns the ``_start_tracking`` AsyncMock.
    """

    async def _run(
        backend: Backend,
        routes: list,
        env: dict,
        *,
        ssl_create_default_context_patch=None,
    ) -> MagicMock:
        sm = vast_serverless_server_mod
        st = serverless_tracked_runner_and_tcp_site
        app_runner, tcp_site = st.app_runner, st.tcp_site
        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, env, clear=False))
            if ssl_create_default_context_patch is not None:
                stack.enter_context(ssl_create_default_context_patch)
            stack.enter_context(
                patch.object(sm.web, "AppRunner", side_effect=app_runner)
            )
            stack.enter_context(patch.object(sm.web, "TCPSite", side_effect=tcp_site))
            mock_track = stack.enter_context(
                patch.object(backend, "_start_tracking", new_callable=AsyncMock)
            )
            await sm.start_server_async(backend, routes)
        return mock_track

    return _run


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
def make_request_http_mocks():
    """Single factory for ``(mock_session, mock_client)`` used by ``_make_request`` tests.

    Returns a callable ``(mock_session, mock_client)`` configured for _make_request.

    - ``make_request_http_mocks(mock_resp)`` — ``session.get`` returns ``mock_resp``.
    - ``make_request_http_mocks(get_side_effect=...)`` — ``session.get`` uses
      ``AsyncMock(side_effect=...)`` (exception, list of responses, etc.).
    - ``make_request_http_mocks(post_return=resp)`` — ``session.post`` returns
      ``resp``; ``session.get`` is a bare ``AsyncMock()`` (unused).
    Pass ``mock_resp=None`` and omit the kwargs to configure ``get``/``post`` manually
    on the returned ``mock_session``.
    """

    def _make(mock_resp=None, *, get_side_effect=None, post_return=None):
        mock_session = MagicMock()
        if get_side_effect is not None:
            mock_session.get = AsyncMock(side_effect=get_side_effect)
        elif post_return is not None:
            mock_session.get = AsyncMock()
        else:
            mock_session.get = AsyncMock(return_value=mock_resp)

        if post_return is not None:
            mock_session.post = AsyncMock(return_value=post_return)
        else:
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
    with patch("vastai.serverless.client.connection._build_kwargs") as mock_build:
        mock_build.return_value = {
            "headers": {},
            "params": {},
            "timeout": MagicMock(),
        }
        yield mock_build


@pytest.fixture
def make_aiohttp_client_session_mock():
    """Factory: mock aiohttp ``ClientSession`` for ``_open_once`` tests."""

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


# ---------------------------------------------------------------------------
# Pyworker server (vastai.serverless.server.lib.metrics) fixtures
# ---------------------------------------------------------------------------


def _metrics_post_ok_context_and_response() -> tuple[MagicMock, MagicMock]:
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)
    return mock_ctx, mock_resp


@pytest.fixture
def clear_get_url_cache():
    """Clear functools.cache on get_url() before and after each test.

    Use via ``pytestmark = pytest.mark.usefixtures("clear_get_url_cache")`` on
    modules that patch os.environ for URL tests.
    """
    from vastai.serverless.server.lib.metrics import get_url

    get_url.cache_clear()
    yield
    get_url.cache_clear()


@pytest.fixture
def make_pyworker_metrics():
    """Factory: build Metrics with explicit id/report_addr/url (no CONTAINER_ID env)."""

    def _make(**kwargs):
        from vastai.serverless.server.lib.metrics import Metrics

        defaults = dict(
            id=1,
            report_addr=["http://report.test"],
            url="http://worker.test:9000",
        )
        defaults.update(kwargs)
        return Metrics(**defaults)

    return _make


@pytest.fixture
def make_pyworker_session():
    """Factory: server ``Session`` (pyworker data type, not aiohttp) for all serverless tests."""

    def _make(**kwargs):
        defaults = dict(
            session_id="s1",
            lifetime=0.0,
            auth_data={},
            expiration=0.0,
            on_close_route="",
            on_close_payload={},
            request_idx=1,
        )
        defaults.update(kwargs)
        return PyworkerSession(**defaults)

    return _make


@pytest.fixture
def make_pyworker_request_metrics():
    """Factory: ``RequestMetrics`` with defaults; override fields per test."""

    def _make(**kwargs):
        defaults = dict(
            request_idx=1,
            reqnum=1,
            workload=1.0,
            status="",
            success=False,
            is_session=False,
            session=None,
            session_reqnum=None,
        )
        defaults.update(kwargs)
        return RequestMetrics(**defaults)

    return _make


@pytest.fixture
def make_metrics_aiohttp_post():
    """Single factory for aiohttp-style ``session.post`` / async context mocks in metrics tests.

    - ``session_ok()`` → ``(mock_session, mock_response)``
    - ``context_ok()`` → ``(context_manager, response)``
    - ``context_timeout()`` → context whose ``__aenter__`` raises ``asyncio.TimeoutError``
    - ``context_client_error(status=500)`` → context; ``raise_for_status`` raises ``ClientResponseError``
    - ``context_enter_raises(exc)`` → context whose ``__aenter__`` raises ``exc``
    """

    def session_ok():
        mock_ctx, mock_resp = _metrics_post_ok_context_and_response()
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_ctx)
        return mock_session, mock_resp

    def context_ok():
        return _metrics_post_ok_context_and_response()

    def context_timeout():
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        return mock_ctx

    def context_client_error(*, status: int = 500):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock(
            side_effect=ClientResponseError(
                request_info=MagicMock(),
                history=(),
                status=status,
            )
        )
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        return mock_ctx

    def context_enter_raises(exc: BaseException):
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(side_effect=exc)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        return mock_ctx

    return SimpleNamespace(
        session_ok=session_ok,
        context_ok=context_ok,
        context_timeout=context_timeout,
        context_client_error=context_client_error,
        context_enter_raises=context_enter_raises,
    )


@pytest.fixture
def metrics_worker_status_context():
    """Patch ``Metrics.http``, disk usage, and optionally ``asyncio.sleep`` for ``__send_metrics_and_reset``."""

    @contextmanager
    def _cm(m, mock_session, *, disk_gb: float = 1.0, mock_asyncio_sleep: bool = False):
        with patch.object(m, "http", new_callable=AsyncMock, return_value=mock_session):
            with patch(
                "vastai.serverless.server.lib.data_types.SystemMetrics.get_disk_usage_GB",
                return_value=disk_gb,
            ):
                if mock_asyncio_sleep:
                    with patch(
                        "vastai.serverless.server.lib.metrics.asyncio.sleep",
                        new_callable=AsyncMock,
                    ):
                        yield
                else:
                    yield

    return _cm


@pytest.fixture
def metrics_delete_send_context():
    """Patch ``Metrics.http`` and ``asyncio.sleep`` for ``__send_delete_requests_and_reset``."""

    @contextmanager
    def _cm(m, mock_session):
        with patch.object(m, "http", new_callable=AsyncMock, return_value=mock_session):
            with patch(
                "vastai.serverless.server.lib.metrics.asyncio.sleep",
                new_callable=AsyncMock,
            ):
                yield

    return _cm


@pytest.fixture
def patch_pyworker_metrics_loop():
    """Patch ``time``, ``_Metrics__send_metrics_and_reset``, and ``metrics.sleep`` for ``_send_metrics_loop`` tests."""

    @contextmanager
    def _cm(m, mock_send, *, time_return: float):
        with patch("vastai.serverless.server.lib.metrics.time") as mock_time:
            mock_time.time.return_value = time_return
            with patch.object(m, "_Metrics__send_metrics_and_reset", mock_send):
                with patch(
                    "vastai.serverless.server.lib.metrics.sleep",
                    new_callable=AsyncMock,
                ):
                    yield mock_time

    return _cm


@pytest.fixture
def make_metrics_client_session_instance():
    """Factory: MagicMock standing in for ``aiohttp.ClientSession`` in metrics ``http()`` tests."""

    def _make(*, close_async: bool = False):
        inst = MagicMock()
        if close_async:
            inst.close = AsyncMock()
        return inst

    return _make


# ---------------------------------------------------------------------------
# Serverless client (Serverless, Endpoint, Session) fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> Serverless:
    """Serverless client with a fixed test API key (no aiohttp session)."""
    return Serverless(api_key="k")


@pytest.fixture
def client_with_session(client: Serverless) -> Serverless:
    """Serverless client with a mocked open aiohttp session on ``_session``."""
    _attach_mock_aiohttp_session(client)
    return client


@pytest.fixture
def serverless_master_client() -> Serverless:
    """Serverless client using api_key ``master`` (autoscaler POST payload tests)."""
    return Serverless(api_key="master")


@pytest.fixture
def make_serverless_endpoint():
    """Build an :class:`Endpoint` bound to a :class:`Serverless` client."""

    def _make(
        sl_client: Serverless,
        *,
        name: str = "myep",
        endpoint_id: int = 5,
        api_key: str = "ekey",
    ) -> Endpoint:
        return Endpoint(sl_client, name, endpoint_id, api_key)

    return _make


@pytest.fixture
def make_serverless_bound_session(make_serverless_endpoint):
    """Factory: :class:`Session` on a real :class:`Endpoint` (queue / Serverless client tests)."""

    def _make(
        sl_client: Serverless,
        *,
        endpoint: Endpoint | None = None,
        session_id: str = "sid",
        lifetime: float = 60.0,
        expiration: str = "e",
        url: str = "https://worker/u",
        auth_data: dict | None = None,
        **kwargs,
    ) -> Session:
        ep = endpoint if endpoint is not None else make_serverless_endpoint(sl_client)
        ad = {"token": "t"} if auth_data is None else auth_data
        return Session(ep, session_id, lifetime, expiration, url, ad, **kwargs)

    return _make


@pytest.fixture
def mock_serverless_client():
    """Minimal mock Serverless-like client for Endpoint delegation tests."""
    c = MagicMock()
    c.is_open = MagicMock(return_value=True)
    c.autoscaler_url = "https://run.vast.ai"
    c.queue_endpoint_request = MagicMock(return_value="queued")
    c.end_endpoint_session = AsyncMock(return_value=None)
    c.get_endpoint_session = AsyncMock(return_value=MagicMock())
    c.start_endpoint_session = AsyncMock(return_value="started")
    c.get_endpoint_workers = AsyncMock(return_value=[])
    c._get_session = AsyncMock(return_value=MagicMock())
    return c


@pytest.fixture
def make_delegate_endpoint(mock_serverless_client):
    """Factory: :class:`Endpoint` bound to ``mock_serverless_client`` (delegation / session tests).

    This is the single factory for a real :class:`Endpoint` instance backed by the shared
    minimal mock client. Use :func:`make_serverless_endpoint` for endpoints on a real
    :class:`Serverless` client.
    """

    def _make(
        *,
        name: str = "e",
        endpoint_id: int | None = 1,
        api_key: str = "ek",
        client: Any | None = None,
    ) -> Endpoint:
        c = mock_serverless_client if client is None else client
        return Endpoint(c, name, endpoint_id, api_key)

    return _make


@pytest.fixture
def make_mock_endpoint_for_session():
    """Factory: new MagicMock endpoint with session_healthcheck, close_session, request."""

    def _make() -> MagicMock:
        ep = MagicMock()
        ep.session_healthcheck = AsyncMock(return_value=True)
        ep.close_session = AsyncMock(return_value=None)
        ep.request = AsyncMock(return_value={"status": 200, "body": "ok"})
        return ep

    return _make


@pytest.fixture
def make_route_response_mock():
    """Single factory for autoscaler route polling mocks (WAITING / READY)."""

    def _make(
        *,
        status: str = "WAITING",
        url: str = "https://w/",
        request_idx: int = 1,
        body: dict | None = None,
    ) -> MagicMock:
        if status == "READY":
            b = {"url": url, **(body or {})}
            m = MagicMock()
            m.status = "READY"
            m.request_idx = request_idx
            m.body = b
            m.get_url = MagicMock(return_value=url)
            return m
        if status == "WAITING":
            m = MagicMock()
            m.status = "WAITING"
            m.request_idx = request_idx
            m.body = body if body is not None else {}
            return m
        raise ValueError(f"unknown status {status!r}, use WAITING or READY")

    return _make


@pytest.fixture
def make_completed_serverless_request():
    """Factory: build a resolved :class:`ServerlessRequest` (call from async tests only).

    Pass either ``result=`` for ``set_result`` or ``exception=`` for ``set_exception``.
    """

    def _make(
        *,
        result: dict | None = None,
        exception: BaseException | None = None,
    ) -> ServerlessRequest:
        if (result is None) == (exception is None):
            raise ValueError("Exactly one of result= or exception= must be given")
        req = ServerlessRequest()
        if exception is not None:
            req.set_exception(exception)
        else:
            req.set_result(result)
        return req

    return _make


@pytest.fixture
def make_session_mock():
    """Factory: ``MagicMock(spec=Session)`` stub (not a real :class:`Session` instance).

    For a real :class:`Session`, use ``make_client_session`` (mock endpoint),
    ``make_session`` / ``sample_session`` (delegate :class:`Endpoint`), or
    ``make_serverless_bound_session`` (real :class:`Serverless` client).
    """

    def _make(
        *,
        session_id: int = 1,
        url: str | None = "https://worker/u",
        auth_data: dict | None = None,
        open_: bool = True,
    ) -> MagicMock:
        m = MagicMock(spec=Session)
        m.session_id = session_id
        m.url = url
        m.auth_data = {} if auth_data is None else auth_data
        m.open = open_
        return m

    return _make


@pytest.fixture
def default_start_endpoint_session_ep(client, make_serverless_endpoint):
    """Shared :class:`Endpoint` for ``start_endpoint_session`` tests."""
    return make_serverless_endpoint(client, name="ep", endpoint_id=3, api_key="ek")


@pytest.fixture
def make_test_endpoint(client, make_serverless_endpoint):
    """Factory for test :class:`Endpoint` instances.

    Do not depend on ``client_with_session``: that fixture mutates the shared
    ``client`` in place. ``open_session=True`` uses a **new** ``Serverless`` with
    its own mock aiohttp session so ``open_session=False`` keeps ``client`` without
    ``_session`` (unless another fixture or test attaches one).
    """

    def _make(
        *,
        open_session: bool = False,
        name: str = "ep",
        endpoint_id: int = 1,
        api_key: str = "ek",
    ) -> Endpoint:
        if open_session:
            sl = Serverless(api_key="k")
            _attach_mock_aiohttp_session(sl)
        else:
            sl = client
        return make_serverless_endpoint(
            sl, name=name, endpoint_id=endpoint_id, api_key=api_key
        )

    return _make


@pytest.fixture
def patch_serverless_queue_async_stubs():
    """Patch ``asyncio.sleep`` and ``random.uniform`` on the serverless client module.

    Queue/routing tests use instant sleep and fixed jitter so they stay fast and
    deterministic. Does not apply when a test replaces ``sleep`` with a custom
    ``side_effect`` (e.g. cancellation).
    """
    with (
        patch(
            "vastai.serverless.client.client.asyncio.sleep",
            new_callable=AsyncMock,
        ),
        patch(
            "vastai.serverless.client.client.random.uniform",
            return_value=0.1,
        ),
    ):
        yield


@pytest.fixture
def make_client_session(make_mock_endpoint_for_session):
    """Factory: build Session with default mock endpoint and typical test defaults."""

    def _make(
        endpoint=None,
        *,
        session_id: str = "sess-1",
        lifetime: float = 60.0,
        expiration: str = "2099-01-01T00:00:00Z",
        url: str = "https://worker.example/session",
        auth_data: dict | None = None,
        **kwargs,
    ):
        ep = endpoint if endpoint is not None else make_mock_endpoint_for_session()
        ad = auth_data if auth_data is not None else {"token": "t"}
        return Session(
            endpoint=ep,
            session_id=session_id,
            lifetime=lifetime,
            expiration=expiration,
            url=url,
            auth_data=ad,
            **kwargs,
        )

    return _make


@pytest.fixture
def session_on_mock_endpoint(make_mock_endpoint_for_session, make_client_session):
    """Single mock endpoint and :class:`Session` bound to it (configure ``ep`` attrs in tests as needed)."""
    ep = make_mock_endpoint_for_session()
    return ep, make_client_session(endpoint=ep)


# ---------------------------------------------------------------------------
# Client Session on delegate Endpoint (test_client_session.py)
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_endpoint(make_delegate_endpoint):
    """:class:`Endpoint` on ``mock_serverless_client`` with ``test_client_session`` defaults."""
    return make_delegate_endpoint(
        name="test-endpoint", endpoint_id=1, api_key="ep-api-key"
    )


@pytest.fixture
def make_session(make_delegate_endpoint):
    """Factory: :class:`Session` bound to a delegate :class:`Endpoint` (real type, mock client)."""

    def _make(
        endpoint=None,
        session_id="sess-123",
        lifetime=60.0,
        expiration="2026-12-31T00:00:00Z",
        url="https://worker1.vast.ai",
        auth_data=None,
        on_close_route=None,
        on_close_payload=None,
    ):
        ep = (
            endpoint
            if endpoint is not None
            else make_delegate_endpoint(
                name="test-endpoint", endpoint_id=1, api_key="ep-api-key"
            )
        )
        if auth_data is None:
            auth_data = {"url": "https://worker1.vast.ai", "signature": "abc"}
        return Session(
            endpoint=ep,
            session_id=session_id,
            lifetime=lifetime,
            expiration=expiration,
            url=url,
            auth_data=auth_data,
            on_close_route=on_close_route,
            on_close_payload=on_close_payload,
        )

    return _make


@pytest.fixture
def sample_session(make_session):
    """A ready-to-use :class:`Session` on the default delegate endpoint."""
    return make_session()


# ---------------------------------------------------------------------------
# Serverless client SSL test helpers (test_client_ssl.py)
# ---------------------------------------------------------------------------


_NOW_SSL = datetime.datetime.now(datetime.UTC)


def _serverless_ssl_generate_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _serverless_ssl_dummy_cert_pem() -> bytes:
    """Self-signed PEM used only to satisfy ``load_verify_locations`` in SSL tests."""
    key = _serverless_ssl_generate_key()
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_NOW_SSL)
        .not_valid_after(_NOW_SSL + datetime.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.PEM)


def serverless_ssl_build_ca_chain_without_key_cert_sign() -> tuple[bytes, bytes, bytes]:
    """CA + leaf PEM bytes mimicking a CA without keyCertSign (see test_client_ssl docstring)."""
    ca_key = _serverless_ssl_generate_key()
    ca_name = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "Test CA (no keyCertSign)")]
    )
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_NOW_SSL)
        .not_valid_after(_NOW_SSL + datetime.timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )
    leaf_key = _serverless_ssl_generate_key()
    leaf_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    leaf_cert = (
        x509.CertificateBuilder()
        .subject_name(leaf_name)
        .issuer_name(ca_name)
        .public_key(leaf_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_NOW_SSL)
        .not_valid_after(_NOW_SSL + datetime.timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("localhost")]),
            critical=False,
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )
    ca_pem = ca_cert.public_bytes(serialization.Encoding.PEM)
    leaf_pem = leaf_cert.public_bytes(serialization.Encoding.PEM)
    leaf_key_pem = leaf_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
    return ca_pem, leaf_pem, leaf_key_pem


def patch_serverless_client_cert_download(cert_pem: bytes):
    """Patch ``aiohttp.ClientSession`` so the trust-store GET returns ``cert_pem``."""
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.read = AsyncMock(return_value=cert_pem)

    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_session = AsyncMock()
    mock_session.get = MagicMock(return_value=mock_session_ctx)

    mock_session_outer = AsyncMock()
    mock_session_outer.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_outer.__aexit__ = AsyncMock(return_value=False)

    return patch(
        "vastai.serverless.client.client.aiohttp.ClientSession",
        return_value=mock_session_outer,
    )


@pytest.fixture
def serverless_ssl_self_signed_cert_pem():
    """Dummy PEM leaf for ``get_ssl_context`` tests."""
    return _serverless_ssl_dummy_cert_pem()


@pytest.fixture
def serverless_ssl_ca_chain_without_key_cert_sign():
    """``(ca_pem, leaf_pem, leaf_key_pem)`` for OpenSSL strict-flag regression tests."""
    return serverless_ssl_build_ca_chain_without_key_cert_sign()


@pytest.fixture
def patch_serverless_ssl_cert_download():
    """Callable ``(cert_pem: bytes)`` returning an active ``patch`` for cert download."""
    return patch_serverless_client_cert_download


# ---------------------------------------------------------------------------
# CLI fixtures (vast-cli specific)
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

