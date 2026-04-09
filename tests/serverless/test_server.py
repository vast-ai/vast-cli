"""Unit tests for vastai.serverless.server.lib.server start/stop wiring.

Exercises route registration, SSL branch wiring, and failure beacon behavior with
everything that would bind ports or loop forever heavily mocked.
"""
from __future__ import annotations

import asyncio
import inspect
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vastai.serverless.server.lib import server as server_mod
from vastai.serverless.server.lib.server import start_server, start_server_async


@pytest.mark.asyncio
async def test_start_server_async_registers_session_routes_and_starts_sites(
    serverless_backend_and_handler_default,
    serverless_metrics_test_env,
    serverless_tracked_runner_and_tcp_site,
    serverless_aiohttp_route_path_tuples,
    run_serverless_start_server_async_patched,
) -> None:
    """
    Verifies start_server_async builds apps with session endpoints and starts TCPSites.

    This test verifies by:
    1. Patching AppRunner, TCPSite, and _start_tracking so nothing listens on real ports
    2. Capturing Application instances passed to AppRunner
    3. Asserting main app includes POST /session/create, /session/end, /session/get, /session/health
    4. Asserting HTTP app includes POST /session/end

    Assumptions:
    - backend._start_tracking is mocked; WORKER_PORT and related env are set
    """
    backend, _ = serverless_backend_and_handler_default
    routes: list = []
    st = serverless_tracked_runner_and_tcp_site
    apps_seen = st.apps_seen
    route_paths = serverless_aiohttp_route_path_tuples

    env = {**serverless_metrics_test_env, "WORKER_PORT": "9100", "WORKER_HTTP_PORT": "9101"}
    mock_track = await run_serverless_start_server_async_patched(
        backend,
        routes,
        env,
    )

    mock_track.assert_awaited_once()
    assert len(apps_seen) >= 2
    main_app = apps_seen[0]
    http_app = apps_seen[1]
    paths = route_paths(main_app)
    for suffix in ("/session/create", "/session/end", "/session/get", "/session/health"):
        assert any(suffix in p for _, p in paths)
    http_paths = route_paths(http_app)
    assert any("/session/end" in p for _, p in http_paths)


@pytest.mark.asyncio
async def test_start_server_async_defaults_http_port_to_worker_plus_one(
    serverless_backend_and_handler_default,
    serverless_metrics_test_env,
    serverless_tracked_runner_and_tcp_site,
    run_serverless_start_server_async_patched,
) -> None:
    """
    Verifies WORKER_HTTP_PORT defaults to int(WORKER_PORT) + 1 when unset.

    This test verifies by:
    1. Removing WORKER_HTTP_PORT from the environment for the duration of the call
    2. Capturing TCPSite kwargs for the HTTP-only app
    3. Asserting its port is WORKER_PORT + 1 while the TLS/plain worker uses WORKER_PORT

    Assumptions:
    - Same patched runner/_start_tracking path as other start_server_async tests
    """
    backend, _ = serverless_backend_and_handler_default
    routes: list = []
    st = serverless_tracked_runner_and_tcp_site
    tcp_calls = st.tcp_calls

    env = {**serverless_metrics_test_env, "WORKER_PORT": "7122"}
    old_http = os.environ.pop("WORKER_HTTP_PORT", None)
    try:
        await run_serverless_start_server_async_patched(
            backend,
            routes,
            env,
        )
    finally:
        if old_http is not None:
            os.environ["WORKER_HTTP_PORT"] = old_http
    assert tcp_calls[0]["port"] == 7122
    assert tcp_calls[1]["port"] == 7123


@pytest.mark.asyncio
async def test_start_server_async_ssl_branch_loads_cert_chain(
    serverless_backend_and_handler_default,
    serverless_metrics_test_env,
    serverless_tracked_runner_and_tcp_site,
    run_serverless_start_server_async_patched,
) -> None:
    """
    Verifies USE_SSL=true passes an ssl.SSLContext into TCPSite for the main listener.

    This test verifies by:
    1. Enabling USE_SSL and patching ssl.create_default_context to return a mock context
    2. Recording kwargs passed to TCPSite for the first site (HTTPS worker)

    Assumptions:
    - Certificate load succeeds under patch; second TCPSite remains plain HTTP
    """
    backend, _ = serverless_backend_and_handler_default
    routes: list = []
    st = serverless_tracked_runner_and_tcp_site
    tcp_calls = st.tcp_calls

    mock_ctx = MagicMock()
    mock_ctx.load_cert_chain = MagicMock()

    env = {
        **serverless_metrics_test_env,
        "WORKER_PORT": "9200",
        "USE_SSL": "true",
    }
    await run_serverless_start_server_async_patched(
        backend,
        routes,
        env,
        ssl_create_default_context_patch=patch.object(
            server_mod.ssl, "create_default_context", return_value=mock_ctx
        ),
    )

    mock_ctx.load_cert_chain.assert_called_once_with(
        certfile="/etc/instance.crt",
        keyfile="/etc/instance.key",
    )
    assert tcp_calls[0].get("ssl_context") is mock_ctx
    assert tcp_calls[1].get("ssl_context") is None


@pytest.mark.asyncio
async def test_start_server_async_ssl_cert_load_failure_enters_error_beacon(
    serverless_backend_and_handler_default,
    serverless_metrics_test_env,
    serverless_error_beacon_mocks,
) -> None:
    """
    Verifies SSL certificate load errors are caught like other launch failures and enter the beacon.

    This test verifies by:
    1. Enabling USE_SSL with load_cert_chain raising OSError
    2. Patching Metrics send/sleep like other beacon tests
    3. Asserting _model_errored mentions SSL certificate failure

    Assumptions:
    - Outer try/except wraps all startup failures; beacon runs for any Exception
    """
    mock_err = serverless_error_beacon_mocks
    backend, _ = serverless_backend_and_handler_default
    routes: list = []
    mock_ctx = MagicMock()
    mock_ctx.load_cert_chain = MagicMock(side_effect=OSError("no cert file"))

    env = {
        **serverless_metrics_test_env,
        "WORKER_PORT": "9201",
        "VAST_TCP_PORT_9201": "9201",
        "USE_SSL": "true",
    }
    with patch.dict(os.environ, env, clear=False):
        with patch.object(server_mod.ssl, "create_default_context", return_value=mock_ctx):
            with pytest.raises(RuntimeError, match="stop-beacon"):
                await start_server_async(backend, routes)

    mock_err.assert_called()
    for c in mock_err.call_args_list:
        assert "SSL Certificate" in c[0][0]


@pytest.mark.asyncio
async def test_start_server_async_gather_failure_runs_beacon_until_sleep_stops(
    serverless_backend_and_handler_default,
    serverless_metrics_test_env,
    serverless_tracked_runner_and_tcp_site,
    serverless_error_beacon_mocks,
) -> None:
    """
    Verifies launch failure enters the metrics beacon loop (error reporting path).

    This test verifies by:
    1. Patching Backend._start_tracking to raise after mocked TCPSite starts (same stage as
       a real failure once the listener stack is built)
    2. Patching asyncio.sleep in the server module so the second iteration raises
    3. Asserting _model_errored was invoked with the launch error message

    Assumptions:
    - Metrics in beacon needs CONTAINER_ID etc.; send_metrics_reset is mocked to avoid I/O
    """
    mock_err = serverless_error_beacon_mocks
    backend, _ = serverless_backend_and_handler_default
    routes: list = []
    st = serverless_tracked_runner_and_tcp_site
    app_runner, tcp_site = st.app_runner, st.tcp_site

    env = {
        **serverless_metrics_test_env,
        "WORKER_PORT": "9300",
        "VAST_TCP_PORT_9300": "9300",
    }
    with patch.dict(os.environ, env, clear=False):
        with patch.object(server_mod.web, "AppRunner", side_effect=app_runner):
            with patch.object(server_mod.web, "TCPSite", side_effect=tcp_site):
                with patch.object(
                    backend,
                    "_start_tracking",
                    AsyncMock(side_effect=RuntimeError("bind failed")),
                ):
                    with pytest.raises(RuntimeError, match="stop-beacon"):
                        await start_server_async(backend, routes)

    mock_err.assert_called()
    for c in mock_err.call_args_list:
        assert "bind failed" in c[0][0]


def test_start_server_invokes_asyncio_run(
    serverless_backend_and_handler_default,
) -> None:
    """
    Verifies start_server delegates to asyncio.run(start_server_async(...)).

    This test verifies by:
    1. Patching asyncio.run in the server module
    2. Replacing start_server_async with a trivial async function
    3. Calling start_server(backend, routes, host="127.0.0.1") and asserting run received a coroutine

    Assumptions:
    - kwargs are forwarded into the coroutine factory call before run() sees it
    """
    backend, _ = serverless_backend_and_handler_default
    routes: list = []

    async def fake_start_server_async(b, r, **kwargs):
        assert kwargs.get("host") == "127.0.0.1"
        return None

    ran = []

    def _run_impl(coro):
        ran.append(coro)
        policy = asyncio.get_event_loop_policy()
        loop = policy.new_event_loop()
        try:
            loop.run_until_complete(coro)
        finally:
            loop.close()

    with patch.object(server_mod, "run", side_effect=_run_impl):
        with patch.object(server_mod, "start_server_async", fake_start_server_async):
            start_server(backend, routes, host="127.0.0.1")

    assert len(ran) == 1
    assert asyncio.iscoroutine(ran[0])


# ---------------------------------------------------------------------------
# serverless_gather_await_all (conftest stub semantics)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_serverless_gather_await_all_runs_awaitables_in_order(
    serverless_gather_await_all,
) -> None:
    g = serverless_gather_await_all
    order: list[int] = []

    async def first() -> None:
        order.append(1)

    async def second() -> None:
        order.append(2)

    await g(first(), second())
    assert order == [1, 2]


@pytest.mark.asyncio
async def test_serverless_gather_await_all_cancels_later_tasks_on_exception(
    serverless_gather_await_all,
) -> None:
    g = serverless_gather_await_all

    async def ok_coro() -> None:
        await asyncio.sleep(0)

    async def boom() -> None:
        raise ValueError("stop")

    t_late = asyncio.create_task(asyncio.sleep(999))
    with pytest.raises(ValueError, match="stop"):
        await g(ok_coro(), asyncio.create_task(boom()), t_late)
    try:
        await t_late
    except asyncio.CancelledError:
        pass
    assert t_late.cancelled()


@pytest.mark.asyncio
async def test_serverless_gather_await_all_closes_bare_coroutine_on_exception(
    serverless_gather_await_all,
) -> None:
    g = serverless_gather_await_all

    async def ok_coro() -> None:
        await asyncio.sleep(0)

    async def boom() -> None:
        raise OSError("boom")

    async def never_run() -> None:
        await asyncio.sleep(999)

    coro = never_run()
    with pytest.raises(OSError, match="boom"):
        await g(ok_coro(), boom(), coro)
    assert inspect.getcoroutinestate(coro) == inspect.CORO_CLOSED


@pytest.mark.asyncio
async def test_serverless_gather_await_all_cancels_pending_future_on_exception(
    serverless_gather_await_all,
) -> None:
    g = serverless_gather_await_all
    loop = asyncio.get_running_loop()
    fut: asyncio.Future = loop.create_future()

    async def boom() -> None:
        raise RuntimeError("fail")

    with pytest.raises(RuntimeError, match="fail"):
        await g(boom(), fut)
    assert fut.cancelled()


@pytest.mark.asyncio
async def test_serverless_gather_await_all_accepts_ignored_gather_kwargs(
    serverless_gather_await_all,
) -> None:
    g = serverless_gather_await_all

    async def ok() -> None:
        await asyncio.sleep(0)

    await g(ok(), return_exceptions=True)


def test_beacon_model_errored_assertion_requires_each_call_contains_marker() -> None:
    """Regression: substring checks must scan every call, not only the last."""
    good = [("SSL Certificate failure",), ("SSL Certificate retry",)]
    for call in good:
        assert "SSL Certificate" in call[0]

    bad = [("SSL Certificate ok",), ("unrelated noise",)]
    with pytest.raises(AssertionError):
        for msg in bad:
            assert "SSL Certificate" in msg[0]
