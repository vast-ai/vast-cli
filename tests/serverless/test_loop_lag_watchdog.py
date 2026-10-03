"""Tests for the event-loop lag watchdog.

Synchronous work inside an ``async def`` remote function holds the worker's event
loop for its whole duration. Requests still succeed, so the client sees nothing
wrong, but the metrics reporter cannot run: ``/worker_status/`` POSTs time out and
the autoscaler can reclaim a worker that is in fact busy and making progress.
Observed in the wild as a four-worker pool collapsing to one over a single batch.

The watchdog measures how late its own sleep returns, which detects the condition
directly regardless of what is blocking.
"""

import asyncio
import time

import pytest

from vastai.serverless.server.lib import backend as backend_mod


@pytest.fixture
def metrics_env(monkeypatch, serverless_metrics_test_env):
    for key, value in serverless_metrics_test_env.items():
        monkeypatch.setenv(key, value)


@pytest.fixture
def backend_real_metrics(pyworker_backend, metrics_env):
    """Backend from the shared fixture, but with a real Metrics attached.

    ``pyworker_backend`` mocks Metrics, which is fine for most tests but useless
    here — the watchdog's whole job is to mutate it.
    """
    from vastai.serverless.server.lib.metrics import Metrics

    pyworker_backend.metrics = Metrics()
    return pyworker_backend


class TestMetricsLagRecording:
    def test_record_loop_lag_tracks_the_peak(self, metrics_env) -> None:
        from vastai.serverless.server.lib.metrics import Metrics

        m = Metrics()
        m.record_loop_lag(3.0)
        m.record_loop_lag(9.5)
        m.record_loop_lag(1.0)
        assert m.loop_lag_max == 9.5

    def test_record_loop_lag_sets_the_warning_flag(self, metrics_env) -> None:
        from vastai.serverless.server.lib.metrics import Metrics

        m = Metrics()
        assert "event_loop_blocked" not in m.warnings
        m.record_loop_lag(7.0)
        assert "event_loop_blocked" in m.warnings
        assert m.update_pending is True

    def test_lag_is_reported_then_cleared_but_warning_is_sticky(
        self, metrics_env
    ) -> None:
        """The peak is per-interval; the warning describes a code defect."""
        from vastai.serverless.server.lib.metrics import Metrics

        m = Metrics()
        m.record_loop_lag(6.0)

        # Simulate the post-send reset the sender performs.
        m.loop_lag_max = 0.0
        assert "event_loop_blocked" in m.warnings

    def test_worker_status_payload_carries_lag_and_warnings(
        self, metrics_env
    ) -> None:
        from vastai.serverless.server.lib.data_types import WorkerStatusData

        # The dataclass must accept the new fields with defaults so older
        # construction sites keep working.
        data = WorkerStatusData(
            id=1,
            mtoken="t",
            version="1.1.0",
            loadtime=0.0,
            cur_load=0.0,
            rej_load=0.0,
            new_load=0.0,
            error_msg="",
            max_perf=0.0,
            cur_perf=0.0,
            cur_capacity=0.0,
            max_capacity=0.0,
            num_requests_working=0,
            num_requests_recieved=0,
            additional_disk_usage=0.0,
            working_request_idxs=[],
            url="http://x",
        )
        assert data.deployment_version_id is None
        assert data.loop_lag_max == 0.0
        assert data.warnings == []


class TestWatchdogDetectsBlocking:
    async def test_watchdog_reports_a_blocked_loop(
        self, monkeypatch, backend_real_metrics
    ) -> None:
        """A synchronous stall on the loop is detected and recorded."""
        monkeypatch.setattr(backend_mod, "LOOP_LAG_PROBE_INTERVAL", 0.02)
        monkeypatch.setattr(backend_mod, "LOOP_LAG_WARN_SECONDS", 0.05)

        backend = backend_real_metrics
        watchdog = asyncio.create_task(
            backend._Backend__loop_lag_watchdog()
        )
        try:
            await asyncio.sleep(0.05)
            # Block the loop the way a synchronous remote function would.
            time.sleep(0.3)
            await asyncio.sleep(0.1)
        finally:
            watchdog.cancel()

        assert backend.metrics.loop_lag_max > 0.05
        assert "event_loop_blocked" in backend.metrics.warnings

    async def test_watchdog_stays_quiet_on_a_healthy_loop(
        self, monkeypatch, backend_real_metrics
    ) -> None:
        monkeypatch.setattr(backend_mod, "LOOP_LAG_PROBE_INTERVAL", 0.02)
        monkeypatch.setattr(backend_mod, "LOOP_LAG_WARN_SECONDS", 1.0)

        backend = backend_real_metrics
        watchdog = asyncio.create_task(backend._Backend__loop_lag_watchdog())
        try:
            await asyncio.sleep(0.2)  # cooperative sleeps only
        finally:
            watchdog.cancel()

        assert backend.metrics.loop_lag_max == 0.0
        assert "event_loop_blocked" not in backend.metrics.warnings


class TestBenchmarkRepresentativenessWarning:
    def test_warns_when_real_traffic_is_far_slower_than_the_benchmark(
        self, metrics_env
    ) -> None:
        """The silent failure that stops an endpoint from ever scaling up."""
        from vastai.serverless.server.lib.data_types import RequestMetrics
        from vastai.serverless.server.lib.metrics import Metrics

        m = Metrics()
        # Benchmarked on the cheapest sample, so it claims ~6x real throughput.
        m.model_metrics.max_throughput = 20000.0

        req = RequestMetrics(
            request_idx=1, reqnum=1, workload=26000.0, status="Started"
        )
        req.work_started_at = 100.0
        req.work_completed_at = 108.0  # ~3250 workload/s observed
        m._check_benchmark_representative(req)

        assert "benchmark_unrepresentative" in m.warnings

    def test_no_warning_when_benchmark_matches_reality(self, metrics_env) -> None:
        from vastai.serverless.server.lib.data_types import RequestMetrics
        from vastai.serverless.server.lib.metrics import Metrics

        m = Metrics()
        m.model_metrics.max_throughput = 3000.0

        req = RequestMetrics(
            request_idx=1, reqnum=1, workload=26000.0, status="Started"
        )
        req.work_started_at = 100.0
        req.work_completed_at = 108.0  # ~3250 observed, close to benchmark
        m._check_benchmark_representative(req)

        assert "benchmark_unrepresentative" not in m.warnings

    def test_no_warning_before_a_benchmark_has_run(self, metrics_env) -> None:
        from vastai.serverless.server.lib.data_types import RequestMetrics
        from vastai.serverless.server.lib.metrics import Metrics

        m = Metrics()
        m.model_metrics.max_throughput = 0.0
        req = RequestMetrics(
            request_idx=1, reqnum=1, workload=100.0, status="Started"
        )
        req.work_started_at = 100.0
        req.work_completed_at = 110.0
        m._check_benchmark_representative(req)

        assert "benchmark_unrepresentative" not in m.warnings
