"""Unit tests for WS2: healthcheck-gated readiness (``readiness='healthcheck'``).

Mode 'healthcheck' marks the model loaded on the first successful /health probe,
independent of any log 'model loaded' string; the benchmark runs AFTER health
confirms the server is up. Log mode ('logs', the default) is unchanged.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vastai.serverless.server.worker import WorkerConfig
from vastai.serverless.server.lib.backend import Backend

pytestmark = pytest.mark.usefixtures("clear_get_url_cache")


class _StopLoop(Exception):
    """Sentinel to break the __healthcheck while-loop after exactly one probe."""


async def _run_one_healthcheck(
    backend, attach_session, make_get_cm, *, status=None, exc=None, model_loaded
):
    """Drive exactly one iteration of Backend.__healthcheck and return the
    backend_errored mock. Uses the shared session-mock fixtures
    (attach_serverless_backend_mock_aiohttp_session + make_serverless_aiohttp_get_context_manager,
    per tests/conftest.py) to stub backend.session.get. The loop's trailing
    `await sleep(10)` (outside the try) raises _StopLoop, ending the loop after one
    probe+gate."""
    backend.healthcheck_url = "http://localhost:8000/health"  # else __healthcheck returns early
    if exc is not None:
        attach_session(backend, get_side_effect=exc)
    else:
        resp = MagicMock()
        resp.status = status
        attach_session(backend, get_context_return=make_get_cm(resp))
    backend._Backend__start_healthcheck.set()
    backend._Backend__healthcheck_succeeded = True  # past first-success (old gate)
    backend._Backend__model_loaded = model_loaded   # the NEW gate under test
    backend.backend_errored = MagicMock()
    with patch("vastai.serverless.server.lib.backend.sleep", side_effect=_StopLoop):
        with pytest.raises(_StopLoop):
            await backend._Backend__healthcheck()
    return backend.backend_errored


def test_worker_config_readiness_defaults_to_logs():
    c = WorkerConfig()
    assert c.readiness == "logs"
    assert c.readiness_timeout == 300.0


def test_worker_config_readiness_healthcheck_opt_in():
    c = WorkerConfig(readiness="healthcheck", readiness_timeout=45.0)
    assert c.readiness == "healthcheck"
    assert c.readiness_timeout == 45.0


def test_backend_threads_readiness_defaults(serverless_backend_testkit):
    backend, _ = serverless_backend_testkit.make_backend()
    assert backend.readiness == "logs"
    assert backend.readiness_timeout == 300.0


@pytest.mark.asyncio
async def test_healthcheck_readiness_marks_loaded_after_first_health(
    serverless_backend_testkit,
):
    """First /health 200 → benchmark → _model_loaded, with no log line involved."""
    backend, _ = serverless_backend_testkit.make_backend(unsecured=True)
    backend.readiness = "healthcheck"
    backend.healthcheck_url = "http://localhost:8000/health"
    backend._Backend__run_benchmark = AsyncMock(return_value=42.0)
    backend.metrics._model_loaded = MagicMock()

    backend._Backend__healthcheck_ready.set()  # simulate the first successful /health probe
    task = asyncio.create_task(backend._Backend__healthcheck_readiness())
    try:
        for _ in range(500):
            if backend.metrics._model_loaded.called:
                break
            await asyncio.sleep(0.001)
    finally:
        task.cancel()  # the coroutine stays alive (asyncio.Event().wait()) after loading
        with pytest.raises(asyncio.CancelledError):
            await task

    assert backend.metrics._model_loaded.called
    assert backend.metrics._model_loaded.call_args.kwargs["max_throughput"] == 42.0
    assert backend._Backend__start_healthcheck.is_set()  # it armed the healthcheck loop
    backend._Backend__run_benchmark.assert_awaited_once()  # benchmark ran (after health)


@pytest.mark.asyncio
async def test_healthcheck_readiness_failed_benchmark_does_not_mark_loaded(
    serverless_backend_testkit,
):
    """The round-2 fix: __run_benchmark calls backend_errored and returns 0.0 WITHOUT
    raising on 'no successful responses'. A readiness path must NOT then mark the model
    loaded (which would emit a contradictory loaded+errored, max_perf 0 status). Drives
    the REAL swallow via a benchmark that errors-then-returns, and asserts _model_loaded
    is never called and __model_loaded stays False."""
    backend, _ = serverless_backend_testkit.make_backend(unsecured=True)
    backend.readiness = "healthcheck"
    backend.healthcheck_url = "http://localhost:8000/health"
    backend.metrics._model_loaded = MagicMock()

    async def _failing_benchmark():
        backend.backend_errored("No successful responses from benchmark")  # latches __errored
        return 0.0  # ...and returns WITHOUT raising, exactly like the real swallow

    backend._Backend__run_benchmark = _failing_benchmark

    backend._Backend__healthcheck_ready.set()  # first /health 200 arrived
    task = asyncio.create_task(backend._Backend__healthcheck_readiness())
    for _ in range(200):
        if not backend._Backend__run_benchmark:  # never; loop just yields
            break
        await asyncio.sleep(0.001)
        if backend._Backend__errored:
            break
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert backend._Backend__errored is True
    assert backend.metrics._model_loaded.called is False, "must not mark loaded after error"
    assert backend._Backend__model_loaded is False


@pytest.mark.asyncio
async def test_mark_loaded_helper_skips_when_errored(serverless_backend_testkit):
    """_mark_loaded is the single choke point for the invariant: errored => not loaded.
    It RETURNS whether it marked, so callers gate their 'marked loaded' logging on it
    (else a skip-due-to-errored still logs 'marked loaded' — the live-test finding)."""
    backend, _ = serverless_backend_testkit.make_backend(unsecured=True)
    backend.metrics._model_loaded = MagicMock()
    backend.metrics._model_errored = MagicMock()  # don't need real metric mutation
    # clean path: marks loaded AND returns True
    assert backend._mark_loaded(12.0) is True
    assert backend.metrics._model_loaded.called and backend._Backend__model_loaded is True
    # after errored: subsequent _mark_loaded is a no-op AND returns False
    backend.metrics._model_loaded.reset_mock()
    backend._Backend__model_loaded = False
    backend.backend_errored("boom")
    assert backend._mark_loaded(99.0) is False
    assert not backend.metrics._model_loaded.called
    assert backend._Backend__model_loaded is False


@pytest.mark.asyncio
async def test_healthcheck_readiness_times_out_to_errored(serverless_backend_testkit):
    """No health 200 within readiness_timeout → backend_errored, benchmark never runs."""
    backend, _ = serverless_backend_testkit.make_backend(unsecured=True)
    backend.readiness = "healthcheck"
    backend.healthcheck_url = "http://localhost:8000/health"
    backend.readiness_timeout = 0.01
    backend.backend_errored = MagicMock()
    backend._Backend__run_benchmark = AsyncMock(return_value=1.0)

    await backend._Backend__healthcheck_readiness()  # __healthcheck_ready never set → times out

    assert backend.backend_errored.called
    assert "Timed out" in backend.backend_errored.call_args[0][0]
    backend._Backend__run_benchmark.assert_not_awaited()  # health never confirmed → no benchmark


@pytest.mark.asyncio
async def test_healthcheck_readiness_requires_a_healthcheck_url(serverless_backend_testkit):
    backend, _ = serverless_backend_testkit.make_backend(unsecured=True)
    backend.readiness = "healthcheck"
    backend.healthcheck_url = ""  # not configured
    backend.backend_errored = MagicMock()

    await backend._Backend__healthcheck_readiness()

    assert backend.backend_errored.called
    assert "healthcheck" in backend.backend_errored.call_args[0][0].lower()


# --- the race fix: health regressions are gated on __model_loaded, not first-200 ---


@pytest.mark.asyncio
async def test_health_failure_before_loaded_does_not_error(
    serverless_backend_testkit,
    attach_serverless_backend_mock_aiohttp_session,
    make_serverless_aiohttp_get_context_manager,
):
    """The core race fix: a 503 health probe BEFORE the model is loaded (e.g. during
    the benchmark, or a backend still loading) must NOT call backend_errored — else a
    transient blip marks the worker errored-and-loaded. Verified live: SGLang/llama.cpp
    both 503 during load, so mid-load failures are expected, not regressions."""
    backend, _ = serverless_backend_testkit.make_backend(unsecured=True)
    errored = await _run_one_healthcheck(
        backend,
        attach_serverless_backend_mock_aiohttp_session,
        make_serverless_aiohttp_get_context_manager,
        status=503,
        model_loaded=False,
    )
    assert not errored.called


@pytest.mark.asyncio
async def test_health_failure_after_loaded_errors(
    serverless_backend_testkit,
    attach_serverless_backend_mock_aiohttp_session,
    make_serverless_aiohttp_get_context_manager,
):
    """Once the model IS loaded, a 503 health probe is a real regression → backend_errored."""
    backend, _ = serverless_backend_testkit.make_backend(unsecured=True)
    errored = await _run_one_healthcheck(
        backend,
        attach_serverless_backend_mock_aiohttp_session,
        make_serverless_aiohttp_get_context_manager,
        status=503,
        model_loaded=True,
    )
    assert errored.called
    assert "503" in errored.call_args[0][0]


@pytest.mark.asyncio
async def test_health_connection_error_before_loaded_does_not_error(
    serverless_backend_testkit,
    attach_serverless_backend_mock_aiohttp_session,
    make_serverless_aiohttp_get_context_manager,
):
    """A connection error (server not up yet — the 000/conn-refused startup phase seen
    live on llama.cpp) before loaded must NOT error, only retry."""
    backend, _ = serverless_backend_testkit.make_backend(unsecured=True)
    errored = await _run_one_healthcheck(
        backend,
        attach_serverless_backend_mock_aiohttp_session,
        make_serverless_aiohttp_get_context_manager,
        exc=ConnectionError("refused"),
        model_loaded=False,
    )
    assert not errored.called


@pytest.mark.asyncio
async def test_health_connection_error_after_loaded_errors(
    serverless_backend_testkit,
    attach_serverless_backend_mock_aiohttp_session,
    make_serverless_aiohttp_get_context_manager,
):
    backend, _ = serverless_backend_testkit.make_backend(unsecured=True)
    errored = await _run_one_healthcheck(
        backend,
        attach_serverless_backend_mock_aiohttp_session,
        make_serverless_aiohttp_get_context_manager,
        exc=ConnectionError("refused"),
        model_loaded=True,
    )
    assert errored.called


# --- mode-string validation + configurable probe timeout ---


def test_invalid_readiness_mode_rejected():
    with pytest.raises(ValueError, match="invalid readiness"):
        Backend(
            model_server_url="http://localhost:8000",
            model_log_file="/tmp/x.log",
            benchmark_handler=MagicMock(),
            log_actions=[],
            readiness="healthchek",  # typo → must not silently fall through to log mode
        )


def test_healthcheck_probe_timeout_defaults_and_threads():
    c = WorkerConfig()
    assert c.healthcheck_probe_timeout == 10.0
    c2 = WorkerConfig(healthcheck_probe_timeout=25.0)
    assert c2.healthcheck_probe_timeout == 25.0
