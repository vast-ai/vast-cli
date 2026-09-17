"""Tests for deployment startup progress and the startup timeout.

A deployment's first call blocks while an instance is rented, the image pulled,
packages installed and the benchmark run. Previously the client printed nothing
and waited forever, so a slow start and a hang were indistinguishable and the
only way to see what was happening was to poll the raw endpoint-workers API by
hand.

Two things matter here beyond "it prints something":

* One poller per deployment. ``asyncio.gather`` of a large batch must not create
  one poller per call — the endpoint-workers API is rate limited.
* A bounded wait, with the last observed worker states in the error.
"""

import asyncio

import pytest

from vastai.serverless.client.worker import Worker
from vastai.serverless.remote.progress import (
    MIN_POLL_INTERVAL,
    StartupProgress,
    WorkerStartupTimeout,
)


def _worker(worker_id: int, status: str) -> Worker:
    return Worker.from_dict({"id": worker_id, "status": status})


class TestPollerIsShared:
    async def test_many_waiters_share_one_poll_task(self) -> None:
        calls = 0

        async def fetch():
            nonlocal calls
            calls += 1
            return [_worker(1, "loading")]

        p = StartupProgress("app", fetch, mode="off", poll_interval=0.01)
        for _ in range(50):
            p.acquire()
        await asyncio.sleep(0.05)
        task = p._task
        for _ in range(50):
            p.release()

        # 50 concurrent callers, still a single polling task.
        assert task is not None
        assert calls < 20, f"poller ran {calls} times; expected one shared loop"

    async def test_poller_stops_when_the_last_waiter_leaves(self) -> None:
        async def fetch():
            return []

        p = StartupProgress("app", fetch, mode="off", poll_interval=0.01)
        p.acquire()
        p.acquire()
        await asyncio.sleep(0.02)
        p.release()
        assert p._task is not None, "still one waiter, poller should live"
        p.release()
        assert p._task is None

    def test_poll_interval_is_floored_to_respect_rate_limits(self) -> None:
        p = StartupProgress("app", lambda: None, poll_interval=0.001)
        assert p._poll_interval == MIN_POLL_INTERVAL

    async def test_poll_failures_do_not_propagate(self) -> None:
        """A rate-limit response must not break the request being waited on."""

        async def fetch():
            raise RuntimeError("HTTPTooManyRequests")

        p = StartupProgress("app", fetch, mode="off", poll_interval=0.01)
        p.acquire()
        await asyncio.sleep(0.05)
        assert not p._task.done() or p._task.cancelled()
        p.release()


class TestProgressRendering:
    async def test_summary_groups_workers_by_phase(self) -> None:
        workers = [
            _worker(1, "idle"),
            _worker(2, "loading"),
            _worker(3, "loading"),
            _worker(4, "model_loading"),
        ]

        async def fetch():
            return workers

        p = StartupProgress("app", fetch, mode="off")
        p.acquire()
        await asyncio.sleep(0)
        p._workers = workers
        summary = p._summary()
        p.release()

        assert "2 pulling image / installing" in summary
        assert "1 loading model / benchmarking" in summary
        assert "1 ready" in summary

    async def test_summary_says_so_when_nothing_was_recruited(self) -> None:
        async def fetch():
            return []

        p = StartupProgress("app", fetch, mode="off")
        assert "no workers recruited yet" in p._summary()

    def test_off_mode_renders_nothing(self, capsys) -> None:
        p = StartupProgress("app", lambda: None, mode="off")
        p._workers = [_worker(1, "loading")]
        p._render()
        assert capsys.readouterr().err == ""

    def test_plain_mode_logs_instead_of_drawing(self) -> None:
        # The "vastai" logger sets propagate=False and owns its handler, so
        # caplog cannot see it; attach our own handler instead.
        import logging

        records: list[logging.LogRecord] = []

        class _Capture(logging.Handler):
            def emit(self, record):
                records.append(record)

        logger = logging.getLogger("vastai")
        handler = _Capture()
        logger.addHandler(handler)
        previous_level = logger.level
        logger.setLevel(logging.INFO)
        try:
            p = StartupProgress("app", lambda: None, mode="plain")
            p._workers = [_worker(1, "loading")]
            p._render()
        finally:
            logger.removeHandler(handler)
            logger.setLevel(previous_level)

        assert any("waiting for a worker" in r.getMessage() for r in records)
        assert any("pulling image / installing" in r.getMessage() for r in records)

    def test_elapsed_is_sane_before_acquire(self) -> None:
        """A reporter rendered before acquire() must not claim hours elapsed."""
        p = StartupProgress("app", lambda: None, mode="off")
        assert 0 <= p._elapsed() < 5


class TestWorkerStartupTimeout:
    def test_message_lists_the_last_observed_worker_states(self) -> None:
        exc = WorkerStartupTimeout(
            "my-app", 900.0, [_worker(1, "loading"), _worker(2, "model_loading")]
        )
        message = str(exc)
        assert "my-app" in message
        assert "900" in message
        assert "pulling image / installing" in message
        assert "loading model / benchmarking" in message

    def test_message_explains_an_empty_pool_differently(self) -> None:
        exc = WorkerStartupTimeout("my-app", 60.0, [])
        message = str(exc)
        # No workers at all is a search/config problem, not a slow image pull.
        assert "image.require" in message
        assert "max_workers" in message

    def test_it_is_a_timeout_error(self) -> None:
        """So existing `except TimeoutError` handlers keep working."""
        assert issubclass(WorkerStartupTimeout, TimeoutError)

    def test_workers_are_available_for_programmatic_inspection(self) -> None:
        exc = WorkerStartupTimeout("a", 1.0, [_worker(7, "stopped")])
        assert [w.id for w in exc.workers] == [7]
        assert exc.waited == 1.0
