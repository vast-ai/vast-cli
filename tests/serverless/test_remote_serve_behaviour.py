"""Serve-mode behaviour of @remote: benchmark datasets and sync offloading.

Two defects motivated these tests:

1. ``benchmark_dataset`` collapsed to a single entry. ``into_worker`` built
   ``[{"kwargs": ... for item in dataset}]`` -- a dict comprehension with the
   constant key ``"kwargs"`` inside a one-element list -- so every entry but the
   last was silently discarded. The worker then benchmarked one arbitrary sample
   while the docs promised a representative mix.

2. A synchronous remote function body ran directly on the worker's event loop.
   GPU work is almost always synchronous, and blocking the loop starves the
   worker's ``/worker_status/`` reporting badly enough that the autoscaler can
   reclaim the worker mid-batch. Plain ``def`` functions are now threaded.
"""

import asyncio
import threading

import pytest

from vastai.serverless.remote import serve as serve_mode


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("VAST_API_KEY", "test-key")
    return serve_mode.Deployment(name="serve-behaviour")


@pytest.fixture
def worker_env(monkeypatch, serverless_metrics_test_env):
    """Env needed to construct a real Worker/Backend from a deployment."""
    for key, value in serverless_metrics_test_env.items():
        monkeypatch.setenv(key, value)


class TestBenchmarkDatasetPreserved:
    """Exercise the real into_worker path, not a reimplementation of it."""

    def test_benchmark_samples_cover_every_dataset_entry(
        self, app, worker_env
    ) -> None:
        @app.remote(benchmark_dataset=[{"x": 1}, {"x": 2}, {"x": 3}])
        async def square(x):
            return x * x

        handler = app.into_worker().backend.benchmark_handler

        # for_test() samples from the dataset, so over many draws every entry
        # should appear. Before the fix only the last one ever could.
        seen = set()
        for _ in range(200):
            payload = handler.make_benchmark_payload()
            seen.add(payload.input["kwargs"]["x"])

        assert seen == {1, 2, 3}, (
            f"benchmark dataset collapsed; only saw {sorted(seen)}"
        )

    def test_single_entry_dataset_still_works(self, app, worker_env) -> None:
        @app.remote(benchmark_dataset=[{"x": 42}])
        async def square(x):
            return x * x

        handler = app.into_worker().backend.benchmark_handler
        payload = handler.make_benchmark_payload()
        assert payload.input["kwargs"]["x"] == 42

    def test_multi_key_entries_are_preserved(self, app, worker_env) -> None:
        @app.remote(benchmark_dataset=[{"frame": 0, "total": 4}, {"frame": 3, "total": 4}])
        async def render(frame, total):
            return frame

        handler = app.into_worker().backend.benchmark_handler
        seen = set()
        for _ in range(200):
            kwargs = handler.make_benchmark_payload().input["kwargs"]
            assert set(kwargs) == {"frame", "total"}
            seen.add(kwargs["frame"])
        assert seen == {0, 3}


class TestSyncFunctionOffloading:
    async def test_sync_function_runs_off_the_event_loop(self, app) -> None:
        """A plain `def` body must not execute on the loop thread."""
        loop_thread = threading.get_ident()
        seen = {}

        @app.remote(benchmark_dataset=[{"x": 1}])
        def blocking(x):
            seen["thread"] = threading.get_ident()
            return x * 2

        (entry,) = app.remote_funcs.values()
        wrapped = app._wrap_remote_func(
            app.root_module, entry.func, entry.globals
        )
        result = await wrapped(kwargs={"x": 21})

        assert result["ok"] == 42
        assert seen["thread"] != loop_thread, (
            "synchronous remote function ran on the event loop thread"
        )

    async def test_sync_function_does_not_block_the_loop(self, app) -> None:
        """Other loop tasks keep running while a sync body is in flight."""
        import time as _time

        @app.remote(benchmark_dataset=[{"x": 1}])
        def slow(x):
            _time.sleep(0.3)
            return x

        (entry,) = app.remote_funcs.values()
        wrapped = app._wrap_remote_func(app.root_module, entry.func, entry.globals)

        ticks = 0

        async def ticker():
            nonlocal ticks
            while True:
                await asyncio.sleep(0.02)
                ticks += 1

        task = asyncio.create_task(ticker())
        try:
            await wrapped(kwargs={"x": 1})
        finally:
            task.cancel()

        # If the body had blocked the loop, the ticker could not have advanced.
        assert ticks > 3, f"event loop was starved; only {ticks} ticks"

    async def test_async_function_still_runs_inline(self, app) -> None:
        """async def bodies keep their existing behaviour."""
        loop_thread = threading.get_ident()
        seen = {}

        @app.remote(benchmark_dataset=[{"x": 1}])
        async def native(x):
            seen["thread"] = threading.get_ident()
            return x + 1

        (entry,) = app.remote_funcs.values()
        wrapped = app._wrap_remote_func(app.root_module, entry.func, entry.globals)
        result = await wrapped(kwargs={"x": 1})

        assert result["ok"] == 2
        assert seen["thread"] == loop_thread

    async def test_sync_function_errors_are_serialized_not_raised(self, app) -> None:
        @app.remote(benchmark_dataset=[{"x": 1}])
        def boom(x):
            raise ValueError("nope")

        (entry,) = app.remote_funcs.values()
        wrapped = app._wrap_remote_func(app.root_module, entry.func, entry.globals)
        result = await wrapped(kwargs={"x": 1})

        assert "err" in result
