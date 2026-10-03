"""Deploy-mode client behaviour: call metadata, waiting, and warnings.

Covers the client half of three fixes:

* ``f.submit(...)`` returns a handle carrying the worker that served the call.
  Previously the worker URL was on the transport response and thrown away, so
  the only way to attribute a call was to return ``CONTAINER_ID`` from inside
  your own payload.
* ``ensure_ready(wait=...)`` blocks until workers are actually serving this
  deployment's code version.
* A worker-reported warning (e.g. a blocked event loop) reaches the caller.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from vastai.serverless.client.worker import Worker
from vastai.serverless.remote import deploy as deploy_mode
from vastai.serverless.remote.progress import WorkerStartupTimeout


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("VAST_API_KEY", "test-key")
    return deploy_mode.Deployment(name="client-test", progress="off")


def _wire(app, response: dict) -> None:
    """Point the deployment at a fake endpoint returning ``response``."""
    endpoint = SimpleNamespace(request=AsyncMock(return_value=response))
    app._inner = deploy_mode._FullDeployment(
        root_module="deploy", deployment=SimpleNamespace(endpoint=endpoint)
    )


def _ok(result, meta: dict | None = None, **extra) -> dict:
    """A worker response in the real wire format.

    serve mode returns ``{"result": serialize_ok(value), "meta": {...}}``, and
    ``serialize_ok`` wraps the value as ``{"ok": <serialized>}``.
    """
    body = {"result": {"ok": result}}
    if meta is not None:
        body["meta"] = meta
    return {"response": body, "status": 200, "text": "", **extra}


def _worker(worker_id: int, status: str, version: int | None = None) -> Worker:
    return Worker.from_dict(
        {"id": worker_id, "status": status, "deployment_version_id": version}
    )


class TestPlainCallIsUnchanged:
    async def test_await_returns_the_result_directly(self, app) -> None:
        @app.remote(benchmark_dataset=[{"x": 1}])
        async def double(x):
            return x * 2

        _wire(app, _ok(42))
        assert await double(21) == 42

    def test_decorator_preserves_function_identity(self, app) -> None:
        @app.remote(benchmark_dataset=[{"x": 1}])
        async def documented(x):
            """A docstring worth keeping."""
            return x

        assert documented.__name__ == "documented"
        assert documented.__doc__ == "A docstring worth keeping."


class TestSubmitHandle:
    async def test_submit_result_matches_a_plain_call(self, app) -> None:
        @app.remote(benchmark_dataset=[{"x": 1}])
        async def double(x):
            return x * 2

        _wire(app, _ok(42))
        call = double.submit(21)
        assert await call == 42

    async def test_submit_exposes_the_serving_worker(self, app) -> None:
        @app.remote(benchmark_dataset=[{"x": 1}])
        async def double(x):
            return x * 2

        _wire(
            app,
            _ok(
                42,
                meta={
                    "worker_id": 48601969,
                    "gpu": "RTX 5090",
                    "duration_ms": 712.5,
                    "deployment_version_id": 3215,
                },
                url="https://1.2.3.4:30001",
                latency=0.9,
            ),
        )
        call = double.submit(21)
        await call

        assert call.worker_id == 48601969
        assert call.gpu == "RTX 5090"
        assert call.duration_ms == 712.5
        assert call.deployment_version_id == 3215
        assert call.worker_url == "https://1.2.3.4:30001"
        assert call.latency == 0.9

    async def test_attribution_across_a_gathered_batch(self, app) -> None:
        """The reason this exists: proving whether a batch really fanned out."""
        import collections

        @app.remote(benchmark_dataset=[{"x": 1}])
        async def work(x):
            return x

        _wire(app, _ok(1, meta={"worker_id": 7}))
        calls = [work.submit(i) for i in range(5)]
        await asyncio.gather(*calls)

        assert collections.Counter(c.worker_id for c in calls) == {7: 5}

    async def test_missing_meta_leaves_fields_none(self, app) -> None:
        """Older workers do not send meta; this must not raise."""

        @app.remote(benchmark_dataset=[{"x": 1}])
        async def double(x):
            return x * 2

        _wire(app, _ok(42))
        call = double.submit(21)
        assert await call == 42
        assert call.worker_id is None
        assert call.gpu is None

    def test_awaiting_an_undispatched_call_is_an_error(self) -> None:
        call = deploy_mode.RemoteCall()
        with pytest.raises(RuntimeError):
            call.__await__()


class TestWorkerWarningsReachTheCaller:
    async def test_blocked_loop_warning_is_surfaced_once(self, app) -> None:
        import logging

        records = []

        class _Capture(logging.Handler):
            def emit(self, record):
                records.append(record.getMessage())

        @app.remote(benchmark_dataset=[{"x": 1}])
        async def work(x):
            return x

        _wire(
            app,
            _ok(1, meta={"worker_id": 99, "warnings": ["event_loop_blocked"]}),
        )

        deploy_mode._WARNED.clear()
        logger = logging.getLogger("vastai")
        handler = _Capture()
        logger.addHandler(handler)
        level = logger.level
        logger.setLevel(logging.WARNING)
        try:
            await work.submit(1)
            await work.submit(2)  # same worker: must not warn twice
        finally:
            logger.removeHandler(handler)
            logger.setLevel(level)

        blocked = [m for m in records if "event loop was blocked" in m.lower()]
        assert len(blocked) == 1, records
        assert "asyncio.to_thread" in blocked[0]


class TestWaitForWorkers:
    async def test_returns_once_enough_workers_are_ready(self, app) -> None:
        app._version_id = 3215
        app.workers = AsyncMock(
            return_value=[
                _worker(1, "idle", 3215),
                _worker(2, "idle", 3215),
                _worker(3, "loading", 3215),
            ]
        )
        ready = await app._wait_for_workers(2, timeout=5)
        assert {w.id for w in ready} == {1, 2}

    async def test_ignores_workers_on_a_superseded_version(self, app) -> None:
        """The stale-rollout case: ready, but running the previous code."""
        app._version_id = 3216
        app.workers = AsyncMock(
            return_value=[_worker(1, "idle", 3215), _worker(2, "idle", 3215)]
        )
        with pytest.raises(WorkerStartupTimeout):
            await app._wait_for_workers(1, timeout=0.1)

    async def test_accepts_workers_that_do_not_report_a_version(self, app) -> None:
        """Backwards compatibility with workers predating the field."""
        app._version_id = 3216
        app.workers = AsyncMock(return_value=[_worker(1, "idle", None)])
        ready = await app._wait_for_workers(1, timeout=5)
        assert [w.id for w in ready] == [1]

    async def test_timeout_reports_the_observed_states(self, app) -> None:
        app._version_id = None
        app.workers = AsyncMock(return_value=[_worker(1, "model_loading")])
        with pytest.raises(WorkerStartupTimeout) as exc:
            await app._wait_for_workers(1, timeout=0.1)
        assert "loading model / benchmarking" in str(exc.value)

    async def test_poll_errors_do_not_abort_the_wait(self, app) -> None:
        app._version_id = None
        calls = {"n": 0}

        async def flaky():
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("rate limited")
            return [_worker(1, "idle")]

        app.workers = flaky
        ready = await app._wait_for_workers(1, timeout=30)
        assert [w.id for w in ready] == [1]
        assert calls["n"] >= 2
