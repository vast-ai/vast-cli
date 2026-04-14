"""Unit tests for vastai.serverless.server.lib.metrics (pyworker server metrics).

Covers get_url, Metrics request lifecycle hooks, model state helpers, HTTP session
lifecycle, both background loops, and reporting paths including retry/timeout/error
branches in __send_metrics_and_reset and __send_delete_requests_and_reset.
All HTTP and disk usage are mocked per unit-test-requirements.
"""
from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vastai.serverless.server.lib.metrics import get_url

pytestmark = pytest.mark.usefixtures("clear_get_url_cache")


class TestGetUrl:
    """Verify get_url builds worker public URL from environment."""

    def test_get_url_uses_http_when_use_ssl_false(self) -> None:
        """
        Verifies that get_url returns an http URL when USE_SSL is not true.

        This test verifies by:
        1. Clearing get_url cache and patching os.environ with port and IP keys
        2. Calling get_url()
        3. Asserting the scheme is http and host/port match PUBLIC_IPADDR and mapped TCP port

        Assumptions:
        - VAST_TCP_PORT_{WORKER_PORT} names the env key for the public port
        """
        with patch.dict(
            os.environ,
            {
                "USE_SSL": "false",
                "WORKER_PORT": "8080",
                "VAST_TCP_PORT_8080": "18080",
                "PUBLIC_IPADDR": "192.168.1.5",
            },
            clear=False,
        ):
            get_url.cache_clear()
            assert get_url() == "http://192.168.1.5:18080"

    def test_get_url_uses_https_when_use_ssl_true(self) -> None:
        """
        Verifies that get_url returns an https URL when USE_SSL is true.

        This test verifies by:
        1. Patching os.environ including USE_SSL=true
        2. Calling get_url() after cache clear
        3. Asserting scheme is https

        Assumptions:
        - Same port mapping rules as HTTP
        """
        with patch.dict(
            os.environ,
            {
                "USE_SSL": "true",
                "WORKER_PORT": "9000",
                "VAST_TCP_PORT_9000": "19000",
                "PUBLIC_IPADDR": "10.1.2.3",
            },
            clear=False,
        ):
            get_url.cache_clear()
            assert get_url() == "https://10.1.2.3:19000"


class TestMetricsRequestLifecycle:
    """Verify Metrics hooks update ModelMetrics and flags correctly."""

    def test_request_start_updates_pending_and_workload_for_plain_request(
        self, make_pyworker_metrics, make_pyworker_request_metrics
    ) -> None:
        """
        Verifies that _request_start records workload and sets update_pending.

        This test verifies by:
        1. Creating Metrics and a plain RequestMetrics (no session)
        2. Calling _request_start
        3. Asserting pending/received, requests_working, and update_pending

        Assumptions:
        - Plain requests use reqnum as dict key in requests_working
        """
        m = make_pyworker_metrics()
        req = make_pyworker_request_metrics(
            request_idx=1,
            reqnum=7,
            workload=2.5,
            status="",
        )
        m._request_start(req)
        assert m.model_metrics.workload_pending == 2.5
        assert m.model_metrics.workload_received == 2.5
        assert 7 in m.model_metrics.requests_recieved
        assert m.model_metrics.requests_working[7] is req
        assert req.status == "Started"
        assert m.update_pending is True

    def test_request_end_removes_working_and_updates_last_request_served(
        self, make_pyworker_metrics, make_pyworker_request_metrics
    ) -> None:
        """
        Verifies that _request_end decreases pending and queues delete for plain requests.

        This test verifies by:
        1. Starting then ending a plain request
        2. Asserting workload_pending returned to 0, request removed from working, appended to deleting

        Assumptions:
        - last_request_served is set via time.time (patched for determinism)
        """
        m = make_pyworker_metrics()
        req = make_pyworker_request_metrics(request_idx=2, reqnum=3, workload=1.0, status="Started")
        m._request_start(req)
        with patch("vastai.serverless.server.lib.metrics.time") as mock_time:
            mock_time.time.return_value = 12345.0
            m._request_end(req)
            assert mock_time.time.called
        assert m.model_metrics.workload_pending == 0.0
        assert 3 not in m.model_metrics.requests_working
        assert m.model_metrics.requests_deleting == [req]
        assert m.last_request_served == 12345.0

    def test_request_success_increments_served_and_marks_status(
        self, make_pyworker_metrics, make_pyworker_request_metrics
    ) -> None:
        """
        Verifies that _request_success updates workload_served and request flags.

        This test verifies by:
        1. Calling _request_success on a request
        2. Asserting workload_served, status, success, update_pending

        Assumptions:
        - Success path does not require _request_start first for this unit
        """
        m = make_pyworker_metrics()
        req = make_pyworker_request_metrics(request_idx=1, reqnum=1, workload=4.0, status="Started")
        m._request_success(req)
        assert m.model_metrics.workload_served == 4.0
        assert req.status == "Success"
        assert req.success is True
        assert m.update_pending is True

    def test_request_errored_increments_errored_and_sets_status(
        self, make_pyworker_metrics, make_pyworker_request_metrics
    ) -> None:
        """
        Verifies that _request_errored records error workload and status.

        This test verifies by:
        1. Calling _request_errored with a message
        2. Asserting workload_errored, status, success=False, update_pending

        Assumptions:
        - Logging side effects are not asserted
        """
        m = make_pyworker_metrics()
        req = make_pyworker_request_metrics(request_idx=5, reqnum=5, workload=1.0, status="Started")
        m._request_errored(req, "boom")
        assert m.model_metrics.workload_errored == 1.0
        assert req.status == "Error"
        assert req.success is False
        assert m.update_pending is True

    def test_request_canceled_increments_cancelled(
        self, make_pyworker_metrics, make_pyworker_request_metrics
    ) -> None:
        """
        Verifies that _request_canceled updates cancelled workload and status.

        This test verifies by:
        1. Calling _request_canceled
        2. Asserting workload_cancelled and status Cancelled

        Assumptions:
        - Implementation sets success True for canceled (per pyworker semantics)
        """
        m = make_pyworker_metrics()
        req = make_pyworker_request_metrics(request_idx=9, reqnum=9, workload=0.5, status="Started")
        m._request_canceled(req)
        assert m.model_metrics.workload_cancelled == 0.5
        assert req.status == "Cancelled"
        assert req.success is True

    def test_request_reject_updates_rejected_and_queues_delete(
        self, make_pyworker_metrics, make_pyworker_request_metrics
    ) -> None:
        """
        Verifies that _request_reject records rejection for plain requests.

        This test verifies by:
        1. Calling _request_reject on a non-session request
        2. Asserting workload_rejected, requests_deleting, status Rejected

        Assumptions:
        - Plain reject adds reqnum to requests_recieved and requests_deleting
        """
        m = make_pyworker_metrics()
        req = make_pyworker_request_metrics(request_idx=11, reqnum=11, workload=3.0, status="")
        m._request_reject(req)
        assert m.model_metrics.workload_rejected == 3.0
        assert 11 in m.model_metrics.requests_recieved
        assert req in m.model_metrics.requests_deleting
        assert req.status == "Rejected"
        assert req.success is False
        assert m.update_pending is True

    def test_request_start_skips_recieved_dict_when_request_has_session(
        self, make_pyworker_metrics, make_pyworker_session, make_pyworker_request_metrics
    ) -> None:
        """
        Verifies that _request_start does not register requests that carry a Session reference.

        This test verifies by:
        1. Building RequestMetrics with session set (in-session request)
        2. Calling _request_start
        3. Asserting workload counters update but requests_recieved / requests_working skip

        Assumptions:
        - Implementation uses `if not request.session` to gate registration
        """
        m = make_pyworker_metrics()
        sess = make_pyworker_session()
        req = make_pyworker_request_metrics(
            request_idx=100,
            reqnum=0,
            workload=1.0,
            status="",
            session=sess,
            session_reqnum=1,
        )
        m._request_start(req)
        assert m.model_metrics.workload_received == 1.0
        assert len(m.model_metrics.requests_recieved) == 0
        assert len(m.model_metrics.requests_working) == 0

    def test_request_end_skips_working_and_delete_when_request_has_session(
        self, make_pyworker_metrics, make_pyworker_session, make_pyworker_request_metrics
    ) -> None:
        """
        Verifies _request_end still updates pending and last_request_served but skips
        requests_working / requests_deleting when the request is tied to a Session.

        Assumptions:
        - `if not request.session` gates pop/append; session-scoped traffic uses session lifecycle elsewhere
        """
        m = make_pyworker_metrics()
        sess = make_pyworker_session()
        req = make_pyworker_request_metrics(
            request_idx=10,
            reqnum=0,
            workload=2.0,
            status="Started",
            session=sess,
            session_reqnum=1,
        )
        m._request_start(req)
        with patch("vastai.serverless.server.lib.metrics.time") as mock_time:
            mock_time.time.return_value = 99.0
            m._request_end(req)
        assert m.model_metrics.workload_pending == 0.0
        assert m.model_metrics.requests_deleting == []
        assert m.last_request_served == 99.0

    def test_request_reject_skips_recieved_and_deleting_when_request_has_session(
        self, make_pyworker_metrics, make_pyworker_session, make_pyworker_request_metrics
    ) -> None:
        """
        Verifies _request_reject increments rejected workload but does not touch
        requests_recieved / requests_deleting for in-session requests.

        Assumptions:
        - Same `if not request.session` gate as _request_start / _request_end
        """
        m = make_pyworker_metrics()
        sess = make_pyworker_session(session_id="s2", request_idx=2)
        req = make_pyworker_request_metrics(
            request_idx=20,
            reqnum=0,
            workload=1.5,
            status="",
            session=sess,
            session_reqnum=1,
        )
        m._request_reject(req)
        assert m.model_metrics.workload_rejected == 1.5
        assert len(m.model_metrics.requests_recieved) == 0
        assert m.model_metrics.requests_deleting == []
        assert req.status == "Rejected"


class TestMetricsRequestIdFormatting:
    """Verify _request_id string formatting for logs."""

    def test_request_id_plain_request(self, make_pyworker_metrics, make_pyworker_request_metrics) -> None:
        """
        Verifies _request_id for a non-session request.

        This test verifies by:
        1. Creating RequestMetrics without session
        2. Asserting formatted string contains request_idx

        Assumptions:
        - is_session is False
        """
        m = make_pyworker_metrics()
        req = make_pyworker_request_metrics(request_idx=3, reqnum=3, workload=1.0, status="")
        assert m._request_id(req) == "Request 3"

    def test_request_id_session_scope(self, make_pyworker_metrics, make_pyworker_request_metrics) -> None:
        """
        Verifies _request_id for session-scoped metrics.

        This test verifies by:
        1. Setting is_session True
        2. Asserting output uses Session prefix

        Assumptions:
        - request_idx identifies the session in this branch
        """
        m = make_pyworker_metrics()
        req = make_pyworker_request_metrics(
            request_idx=42,
            reqnum=0,
            workload=1.0,
            status="",
            is_session=True,
        )
        assert m._request_id(req) == "Session 42"

    def test_request_id_in_session_request(
        self, make_pyworker_metrics, make_pyworker_session, make_pyworker_request_metrics
    ) -> None:
        """
        Verifies _request_id for a request belonging to a Session.

        This test verifies by:
        1. Attaching a Session with request_idx to RequestMetrics
        2. Setting session_reqnum
        3. Asserting composite label

        Assumptions:
        - session.request_idx is the session identifier
        """
        m = make_pyworker_metrics()
        sess = make_pyworker_session(request_idx=7)
        req = make_pyworker_request_metrics(
            request_idx=10,
            reqnum=1,
            workload=2.0,
            status="",
            session=sess,
            session_reqnum=3,
        )
        assert m._request_id(req) == "Request 3 in Session 7"


class TestMetricsModelState:
    """Verify model loaded/errored and metadata setters."""

    def test_model_loaded_sets_timing_and_throughput(self, make_pyworker_metrics) -> None:
        """
        Verifies _model_loaded records load duration and max_throughput.

        This test verifies by:
        1. Patching time.time to return controlled values around load
        2. Calling _model_loaded
        3. Asserting model_is_loaded, model_loading_time, max_throughput

        Assumptions:
        - model_loading_start was set when SystemMetrics.empty() was created (patched time)
        """
        with patch("vastai.serverless.server.lib.data_types.time") as dt_time:
            dt_time.time.return_value = 1000.0
            m = make_pyworker_metrics()
        assert m.system_metrics.model_loading_start == 1000.0
        with patch("vastai.serverless.server.lib.metrics.time") as m_time:
            m_time.time.return_value = 1005.0
            m._model_loaded(max_throughput=128.0)
        assert m.system_metrics.model_is_loaded is True
        assert m.system_metrics.model_loading_time == 5.0
        assert m.model_metrics.max_throughput == 128.0

    def test_model_errored_sets_error_and_marks_loaded(self, make_pyworker_metrics) -> None:
        """
        Verifies _model_errored delegates to ModelMetrics.set_errored and sets loaded flag.

        This test verifies by:
        1. Calling _model_errored with a message
        2. Asserting error_msg and model_is_loaded

        Assumptions:
        - set_errored resets counters and stores message per ModelMetrics implementation
        """
        m = make_pyworker_metrics()
        m.model_metrics.workload_received = 10.0
        m._model_errored("failed to load")
        assert m.model_metrics.error_msg == "failed to load"
        assert m.system_metrics.model_is_loaded is True
        assert m.model_metrics.workload_received == 0.0

    def test_set_version_and_mtoken(self, make_pyworker_metrics) -> None:
        """
        Verifies _set_version and _set_mtoken update fields used in worker_status payload.

        This test verifies by:
        1. Calling _set_version and _set_mtoken
        2. Asserting attribute values

        Assumptions:
        - No side effects beyond assignment
        """
        m = make_pyworker_metrics()
        m._set_version("v2")
        m._set_mtoken("secret-token")
        assert m.version == "v2"
        assert m.mtoken == "secret-token"


@pytest.mark.asyncio
class TestSendMetricsAndReset:
    """Verify __send_metrics_and_reset HTTP reporting and reset behavior."""

    async def test_send_metrics_posts_worker_status_and_resets_on_success(
        self, make_pyworker_metrics, make_metrics_aiohttp_post, metrics_worker_status_context
    ) -> None:
        """
        Verifies successful POST to report_addr resets model metrics and update_pending.

        This test verifies by:
        1. Mocking Metrics.http and session.post context manager with 200
        2. Patching SystemMetrics.get_disk_usage_GB to avoid psutil
        3. Awaiting __send_metrics_and_reset
        4. Asserting post URL, JSON payload keys, and reset state

        Assumptions:
        - Private name mangling: _Metrics__send_metrics_and_reset on the class
        """
        m = make_pyworker_metrics()
        m.mtoken = "tok"
        m.version = "1"
        m.model_metrics.workload_served = 2.0
        m.model_metrics.workload_received = 5.0
        m.update_pending = True

        mock_session, _ = make_metrics_aiohttp_post.session_ok()

        with metrics_worker_status_context(m, mock_session, disk_gb=10.0):
            await m._Metrics__send_metrics_and_reset()

        mock_session.post.assert_called_once()
        call_kw = mock_session.post.call_args
        assert call_kw[0][0] == "http://report.test/worker_status/"
        body = call_kw[1]["json"]
        assert body["id"] == 1
        assert body["mtoken"] == "tok"
        assert body["version"] == "1"
        assert body["cur_perf"] == 2.0
        assert body["url"] == "http://worker.test:9000"
        assert m.update_pending is False
        assert m.model_metrics.workload_served == 0.0

    async def test_send_metrics_does_not_reset_when_all_posts_fail(
        self, make_pyworker_metrics, make_metrics_aiohttp_post, metrics_worker_status_context
    ) -> None:
        """
        Verifies metrics are not reset when every report address fails.

        This test verifies by:
        1. Configuring post to raise ClientResponseError
        2. Patching asyncio.sleep to avoid delay
        3. Asserting workload counters and update_pending unchanged

        Assumptions:
        - aiohttp.ClientResponseError is raised from raise_for_status path
        """
        m = make_pyworker_metrics(report_addr=["http://a.test", "http://b.test"])
        m.model_metrics.workload_served = 9.0
        m.update_pending = True

        mock_session = MagicMock()
        mock_session.post = MagicMock(
            return_value=make_metrics_aiohttp_post.context_client_error(),
        )

        with metrics_worker_status_context(m, mock_session, disk_gb=1.0, mock_asyncio_sleep=True):
            await m._Metrics__send_metrics_and_reset()

        assert m.model_metrics.workload_served == 9.0
        assert m.update_pending is True

    async def test_send_metrics_retries_after_timeout_then_succeeds(
        self, make_pyworker_metrics, make_metrics_aiohttp_post, metrics_worker_status_context
    ) -> None:
        """
        Verifies worker_status POST retries when async context raises TimeoutError.

        This test verifies by:
        1. Making the first session.post context __aenter__ raise asyncio.TimeoutError
        2. Making the second attempt succeed
        3. Patching asyncio.sleep in metrics to avoid delay
        4. Asserting post was called twice and metrics reset

        Assumptions:
        - aiohttp-style post returns a synchronous async context manager
        """
        m = make_pyworker_metrics()
        m.update_pending = True
        ctx_fail = make_metrics_aiohttp_post.context_timeout()
        ctx_ok, _ = make_metrics_aiohttp_post.context_ok()
        mock_session = MagicMock()
        mock_session.post = MagicMock(side_effect=[ctx_fail, ctx_ok])

        with metrics_worker_status_context(m, mock_session, disk_gb=1.0, mock_asyncio_sleep=True):
            await m._Metrics__send_metrics_and_reset()

        assert mock_session.post.call_count == 2
        assert m.update_pending is False

    async def test_send_metrics_with_none_mtoken_obfuscates_log_field_to_empty(
        self, make_pyworker_metrics, make_metrics_aiohttp_post, metrics_worker_status_context
    ) -> None:
        """
        Verifies send_data obfuscate() handles None mtoken for debug logging.

        This test verifies by:
        1. Assigning mtoken None on Metrics (runtime value despite type hint)
        2. Running __send_metrics_and_reset with mocked HTTP
        3. Asserting completion without error and successful reset

        Assumptions:
        - asdict includes mtoken key with None; obfuscate returns empty string
        """
        m = make_pyworker_metrics()
        m.mtoken = None  # type: ignore[assignment]
        m.update_pending = True
        mock_session, _ = make_metrics_aiohttp_post.session_ok()

        with metrics_worker_status_context(m, mock_session, disk_gb=1.0):
            await m._Metrics__send_metrics_and_reset()

        body = mock_session.post.call_args[1]["json"]
        assert body["mtoken"] is None
        assert m.update_pending is False

    async def test_send_metrics_succeeds_on_second_report_after_first_exhausts_retries(
        self,
        make_pyworker_metrics,
        make_metrics_aiohttp_post,
        metrics_worker_status_context,
    ) -> None:
        """
        Verifies __send_metrics_and_reset tries each report_addr in order: if the first
        host fails all retry attempts, the second successful host resets metrics.

        Assumptions:
        - Outer loop breaks on first send_data() that returns True
        """
        m = make_pyworker_metrics(
            report_addr=["http://primary.test", "http://backup.test"],
        )
        m.model_metrics.workload_served = 3.0
        m.update_pending = True

        aio = make_metrics_aiohttp_post
        ctx_ok, _ = aio.context_ok()
        mock_session = MagicMock()
        mock_session.post = MagicMock(
            side_effect=[
                aio.context_client_error(),
                aio.context_client_error(),
                aio.context_client_error(),
                ctx_ok,
            ],
        )

        with metrics_worker_status_context(m, mock_session, disk_gb=1.0, mock_asyncio_sleep=True):
            await m._Metrics__send_metrics_and_reset()

        assert mock_session.post.call_count == 4
        assert mock_session.post.call_args_list[3][0][0] == "http://backup.test/worker_status/"
        assert m.model_metrics.workload_served == 0.0
        assert m.update_pending is False

    async def test_send_metrics_debug_log_obfuscates_long_mtoken(
        self,
        make_pyworker_metrics,
        make_metrics_aiohttp_post,
        metrics_worker_status_context,
    ) -> None:
        """
        Verifies send_data's obfuscate() truncates secrets longer than 12 chars in debug logs.

        Assumptions:
        - log.debug receives a string containing the masked mtoken form
        """
        m = make_pyworker_metrics()
        m.mtoken = "abcdefghijklmno"
        m.update_pending = True
        mock_session, _ = make_metrics_aiohttp_post.session_ok()
        captured: list[str] = []

        with patch("vastai.serverless.server.lib.metrics.log") as mock_log:
            mock_log.debug = MagicMock(side_effect=lambda msg, *a, **k: captured.append(msg))
            with metrics_worker_status_context(m, mock_session, disk_gb=1.0):
                await m._Metrics__send_metrics_and_reset()

        joined = "\n".join(captured)
        assert "abcdefg..." in joined
        assert mock_session.post.call_args[1]["json"]["mtoken"] == "abcdefghijklmno"

    async def test_send_metrics_debug_log_obfuscates_short_mtoken_with_stars(
        self,
        make_pyworker_metrics,
        make_metrics_aiohttp_post,
        metrics_worker_status_context,
    ) -> None:
        """Verifies obfuscate() uses asterisks for mtoken length <= 12."""
        m = make_pyworker_metrics()
        m.mtoken = "short"
        m.update_pending = True
        mock_session, _ = make_metrics_aiohttp_post.session_ok()
        captured: list[str] = []

        with patch("vastai.serverless.server.lib.metrics.log") as mock_log:
            mock_log.debug = MagicMock(side_effect=lambda msg, *a, **k: captured.append(msg))
            with metrics_worker_status_context(m, mock_session, disk_gb=1.0):
                await m._Metrics__send_metrics_and_reset()

        joined = "\n".join(captured)
        assert "*****" in joined


@pytest.mark.asyncio
class TestSendDeleteRequestsAndReset:
    """Verify __send_delete_requests_and_reset behavior."""

    async def test_delete_requests_skips_cloud_vast_and_sends_to_next(
        self, make_pyworker_metrics, make_metrics_aiohttp_post, metrics_delete_send_context, make_pyworker_request_metrics
    ) -> None:
        """
        Verifies REPORT_ADDR entries for cloud.vast.ai are skipped.

        This test verifies by:
        1. Using report_addr list with cloud URL then a real test URL
        2. Mocking successful POST
        3. Asserting post called only for the second host

        Assumptions:
        - First address matches the hardcoded skip in metrics.py
        """
        m = make_pyworker_metrics(
            report_addr=[
                "https://cloud.vast.ai/api/v0",
                "http://internal.report",
            ]
        )
        req_ok = make_pyworker_request_metrics(
            request_idx=1,
            reqnum=1,
            workload=1.0,
            status="Success",
            success=True,
        )
        m.model_metrics.requests_deleting = [req_ok]

        mock_session, _ = make_metrics_aiohttp_post.session_ok()

        with metrics_delete_send_context(m, mock_session):
            await m._Metrics__send_delete_requests_and_reset()

        assert mock_session.post.call_count == 1
        assert mock_session.post.call_args[0][0] == "http://internal.report/delete_requests/"
        sent = mock_session.post.call_args[1]["json"]
        assert len(sent["requests"]) == 1
        assert sent["requests"][0]["request_idx"] == 1
        assert sent["requests"][0]["success"] is True
        assert m.model_metrics.requests_deleting == []

    async def test_delete_requests_noop_when_queue_empty(self, make_pyworker_metrics) -> None:
        """
        Verifies early return when requests_deleting is empty.

        This test verifies by:
        1. Leaving requests_deleting empty
        2. Awaiting __send_delete_requests_and_reset
        3. Asserting http() was never used to post

        Assumptions:
        - Empty success/failed idx lists short-circuit before HTTP
        """
        m = make_pyworker_metrics()
        m.model_metrics.requests_deleting = []
        mock_http = AsyncMock()
        with patch.object(m, "http", mock_http):
            await m._Metrics__send_delete_requests_and_reset()
        mock_http.assert_not_awaited()

    async def test_delete_requests_posts_only_failed_batch_when_no_successes(
        self, make_pyworker_metrics, make_metrics_aiohttp_post, metrics_delete_send_context, make_pyworker_request_metrics
    ) -> None:
        """
        Verifies failed-only snapshot triggers POST with per-request success=false.

        This test verifies by:
        1. Queuing only RequestMetrics with success False
        2. Mocking HTTP success
        3. Asserting a single POST with the request's success flag set to False

        Assumptions:
        - A single POST is made containing all requests with their individual success flags
        """
        m = make_pyworker_metrics()
        req_bad = make_pyworker_request_metrics(
            request_idx=9,
            reqnum=9,
            workload=1.0,
            status="Error",
            success=False,
        )
        m.model_metrics.requests_deleting = [req_bad]
        mock_session, _ = make_metrics_aiohttp_post.session_ok()

        with metrics_delete_send_context(m, mock_session):
            await m._Metrics__send_delete_requests_and_reset()

        assert mock_session.post.call_count == 1
        sent = mock_session.post.call_args[1]["json"]
        assert len(sent["requests"]) == 1
        assert sent["requests"][0]["request_idx"] == 9
        assert sent["requests"][0]["success"] is False
        assert m.model_metrics.requests_deleting == []

    async def test_delete_requests_posts_success_and_failure_in_single_batch(
        self, make_pyworker_metrics, make_metrics_aiohttp_post, metrics_delete_send_context, make_pyworker_request_metrics
    ) -> None:
        """
        Verifies mixed success/failure snapshot results in a single POST with per-request success flags.

        This test verifies by:
        1. Queuing one succeeded and one failed request
        2. Asserting a single POST with both requests and their individual success flags

        Assumptions:
        - All requests are sent in one batch with per-request success/status fields
        """
        m = make_pyworker_metrics()
        req_ok = make_pyworker_request_metrics(
            request_idx=1,
            reqnum=1,
            workload=1.0,
            status="Success",
            success=True,
        )
        req_bad = make_pyworker_request_metrics(
            request_idx=2,
            reqnum=2,
            workload=1.0,
            status="Error",
            success=False,
        )
        m.model_metrics.requests_deleting = [req_ok, req_bad]
        mock_session, _ = make_metrics_aiohttp_post.session_ok()

        with metrics_delete_send_context(m, mock_session):
            await m._Metrics__send_delete_requests_and_reset()

        assert mock_session.post.call_count == 1
        sent = mock_session.post.call_args[1]["json"]
        assert len(sent["requests"]) == 2
        by_idx = {r["request_idx"]: r for r in sent["requests"]}
        assert by_idx[1]["success"] is True
        assert by_idx[2]["success"] is False
        assert m.model_metrics.requests_deleting == []

    async def test_delete_requests_retries_after_timeout_then_succeeds(
        self, make_pyworker_metrics, make_metrics_aiohttp_post, metrics_delete_send_context, make_pyworker_request_metrics
    ) -> None:
        """
        Verifies delete_requests inner POST retries on TimeoutError then returns True.

        This test verifies by:
        1. First post context raising TimeoutError, second succeeding
        2. Patching asyncio.sleep between attempts
        3. Asserting queue cleared after success

        Assumptions:
        - Same retry loop structure as worker_status (3 attempts max)
        """
        m = make_pyworker_metrics()
        req = make_pyworker_request_metrics(
            request_idx=5,
            reqnum=5,
            workload=1.0,
            status="Success",
            success=True,
        )
        m.model_metrics.requests_deleting = [req]
        aio = make_metrics_aiohttp_post
        ctx_fail = aio.context_timeout()
        ctx_ok, _ = aio.context_ok()
        mock_session = MagicMock()
        mock_session.post = MagicMock(side_effect=[ctx_fail, ctx_ok])

        with metrics_delete_send_context(m, mock_session):
            await m._Metrics__send_delete_requests_and_reset()

        assert mock_session.post.call_count == 2
        assert m.model_metrics.requests_deleting == []

    async def test_delete_requests_retries_after_generic_exception_then_succeeds(
        self, make_pyworker_metrics, make_metrics_aiohttp_post, metrics_delete_send_context, make_pyworker_request_metrics
    ) -> None:
        """
        Verifies delete_requests catches non-timeout exceptions and retries.

        This test verifies by:
        1. First __aenter__ raising ValueError, second succeeding
        2. Patching asyncio.sleep
        3. Asserting two post calls and cleared queue

        Assumptions:
        - ClientResponseError and Exception share the same handler branch
        """
        m = make_pyworker_metrics()
        req = make_pyworker_request_metrics(
            request_idx=3,
            reqnum=3,
            workload=1.0,
            status="Success",
            success=True,
        )
        m.model_metrics.requests_deleting = [req]
        aio = make_metrics_aiohttp_post
        ctx_fail = aio.context_enter_raises(ValueError("boom"))
        ctx_ok, _ = aio.context_ok()
        mock_session = MagicMock()
        mock_session.post = MagicMock(side_effect=[ctx_fail, ctx_ok])

        with metrics_delete_send_context(m, mock_session):
            await m._Metrics__send_delete_requests_and_reset()

        assert mock_session.post.call_count == 2
        assert m.model_metrics.requests_deleting == []

    async def test_delete_requests_retains_queue_when_all_post_attempts_fail(
        self, make_pyworker_metrics, make_metrics_aiohttp_post, metrics_delete_send_context, make_pyworker_request_metrics
    ) -> None:
        """
        Verifies requests_deleting is unchanged when every HTTP attempt fails.

        This test verifies by:
        1. Making each async context __aenter__ raise ValueError (all 3 attempts)
        2. Patching asyncio.sleep
        3. Asserting the original request remains in the queue

        Assumptions:
        - Inner post() returns False so sent_success is False and queue is not pruned
        """
        m = make_pyworker_metrics()
        req = make_pyworker_request_metrics(
            request_idx=7,
            reqnum=7,
            workload=1.0,
            status="Success",
            success=True,
        )
        m.model_metrics.requests_deleting = [req]
        ctx_fail = make_metrics_aiohttp_post.context_enter_raises(ValueError("always fail"))
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=ctx_fail)

        with metrics_delete_send_context(m, mock_session):
            await m._Metrics__send_delete_requests_and_reset()

        assert mock_session.post.call_count == 3
        assert m.model_metrics.requests_deleting == [req]


@pytest.mark.asyncio
class TestSendDeleteRequestsLoop:
    """Verify _send_delete_requests_loop scheduling."""

    async def test_delete_loop_calls_send_when_queue_nonempty(
        self, make_pyworker_metrics, make_pyworker_request_metrics
    ) -> None:
        """
        Verifies the delete loop awaits __send_delete_requests_and_reset when queue has items.

        This test verifies by:
        1. Patching sleep to return immediately
        2. Patching __send_delete_requests_and_reset to raise CancelledError after one run
        3. Asserting the private send method was awaited once

        Assumptions:
        - CancelledError exits the infinite loop for test isolation
        """
        m = make_pyworker_metrics()
        m.model_metrics.requests_deleting = [
            make_pyworker_request_metrics(
                request_idx=1,
                reqnum=1,
                workload=1.0,
                status="Success",
                success=True,
            )
        ]
        mock_send = AsyncMock(side_effect=asyncio.CancelledError())
        with patch.object(
            m,
            "_Metrics__send_delete_requests_and_reset",
            mock_send,
        ):
            with patch(
                "vastai.serverless.server.lib.metrics.sleep",
                new_callable=AsyncMock,
            ):
                with pytest.raises(asyncio.CancelledError):
                    await m._send_delete_requests_loop()

        mock_send.assert_awaited_once()

    async def test_delete_loop_skips_send_when_queue_empty(self, make_pyworker_metrics) -> None:
        """
        Verifies _send_delete_requests_loop does not call __send_delete_requests_and_reset
        while requests_deleting stays empty (only sleep iterations).

        Assumptions:
        - CancelledError exits the infinite loop after two wakeups
        """
        m = make_pyworker_metrics()
        m.model_metrics.requests_deleting = []
        mock_send = AsyncMock()
        n_sleeps = {"n": 0}

        async def sleep_side_effect(*_args, **_kwargs):
            n_sleeps["n"] += 1
            if n_sleeps["n"] >= 2:
                raise asyncio.CancelledError()

        with patch.object(
            m,
            "_Metrics__send_delete_requests_and_reset",
            mock_send,
        ):
            with patch(
                "vastai.serverless.server.lib.metrics.sleep",
                AsyncMock(side_effect=sleep_side_effect),
            ):
                with pytest.raises(asyncio.CancelledError):
                    await m._send_delete_requests_loop()

        mock_send.assert_not_awaited()


@pytest.mark.asyncio
class TestSendMetricsLoop:
    """Verify _send_metrics_loop scheduling branches."""

    async def test_metrics_loop_calls_send_when_elapsed_ge_10_and_model_not_loaded(
        self, make_pyworker_metrics, patch_pyworker_metrics_loop
    ) -> None:
        """
        Verifies the loop invokes __send_metrics_and_reset when model not loaded and elapsed >= 10.

        This test verifies by:
        1. Setting last_metric_update so elapsed >= 10 under patched time.time
        2. Patching sleep to return immediately
        3. Patching __send_metrics_and_reset to raise CancelledError to exit loop
        4. Asserting the send coroutine was awaited

        Assumptions:
        - CancelledError propagates from the loop after first successful branch
        """
        m = make_pyworker_metrics()
        m.system_metrics.model_is_loaded = False
        m.last_metric_update = 0.0
        mock_send = AsyncMock(side_effect=asyncio.CancelledError())

        with patch_pyworker_metrics_loop(m, mock_send, time_return=100.0):
            with pytest.raises(asyncio.CancelledError):
                await m._send_metrics_loop()

        mock_send.assert_awaited_once()

    async def test_metrics_loop_skips_send_when_loaded_no_pending_and_elapsed_le_10(
        self,
        make_pyworker_metrics,
    ) -> None:
        """
        Verifies the metrics loop sleeps without sending when the model is loaded,
        update_pending is False, and elapsed time is at most 10 seconds.

        Assumptions:
        - Neither `if` nor `elif` body runs; loop only advances via sleep
        """
        m = make_pyworker_metrics()
        m.system_metrics.model_is_loaded = True
        m.update_pending = False
        m.last_metric_update = 1_000.0
        mock_send = AsyncMock()
        n_sleeps = {"n": 0}

        async def sleep_side_effect(*_args, **_kwargs):
            n_sleeps["n"] += 1
            if n_sleeps["n"] >= 2:
                raise asyncio.CancelledError()

        with patch("vastai.serverless.server.lib.metrics.time") as mock_time:
            mock_time.time.return_value = 1_005.0
            with patch.object(
                m,
                "_Metrics__send_metrics_and_reset",
                mock_send,
            ):
                with patch(
                    "vastai.serverless.server.lib.metrics.sleep",
                    AsyncMock(side_effect=sleep_side_effect),
                ):
                    with pytest.raises(asyncio.CancelledError):
                        await m._send_metrics_loop()

        mock_send.assert_not_awaited()

    async def test_metrics_loop_calls_send_when_update_pending(
        self, make_pyworker_metrics, patch_pyworker_metrics_loop
    ) -> None:
        """
        Verifies the loop sends when update_pending is True even if elapsed <= 10.

        This test verifies by:
        1. Setting model_is_loaded True, update_pending True, recent last_metric_update
        2. Using same sleep/send/CancelledError pattern

        Assumptions:
        - Second branch (elif update_pending or elapsed > 10) is taken
        """
        m = make_pyworker_metrics()
        m.system_metrics.model_is_loaded = True
        m.update_pending = True
        m.last_metric_update = 1_000_000.0

        mock_send = AsyncMock(side_effect=asyncio.CancelledError())

        with patch_pyworker_metrics_loop(m, mock_send, time_return=1_000_005.0):
            with pytest.raises(asyncio.CancelledError):
                await m._send_metrics_loop()

        mock_send.assert_awaited_once()

    async def test_metrics_loop_sends_when_elapsed_gt_10_without_pending_or_loading_gate(
        self,
        make_pyworker_metrics,
        patch_pyworker_metrics_loop,
    ) -> None:
        """
        Verifies metrics loop sends via elapsed>10 when model is loaded and update_pending is False.

        This test verifies by:
        1. Setting model_is_loaded True, update_pending False, last_metric_update stale
        2. Patching time.time so elapsed > 10
        3. Using sleep and CancelledError pattern to exit the loop

        Assumptions:
        - First branch (not loaded and elapsed>=10) is false; elif uses elapsed>10 alone
        """
        m = make_pyworker_metrics()
        m.system_metrics.model_is_loaded = True
        m.update_pending = False
        m.last_metric_update = 0.0
        mock_send = AsyncMock(side_effect=asyncio.CancelledError())

        with patch_pyworker_metrics_loop(m, mock_send, time_return=50.0):
            with pytest.raises(asyncio.CancelledError):
                await m._send_metrics_loop()

        mock_send.assert_awaited_once()


@pytest.mark.asyncio
class TestMetricsHttpSession:
    """Verify ClientSession lifecycle on Metrics."""

    async def test_http_creates_session_once(
        self, make_pyworker_metrics, make_metrics_client_session_instance
    ) -> None:
        """
        Verifies http() lazily creates and reuses ClientSession.

        This test verifies by:
        1. Patching ClientSession in the metrics module
        2. Calling await http() twice
        3. Asserting ClientSession constructed once

        Assumptions:
        - Session is stored on _session until aclose
        """
        m = make_pyworker_metrics()
        mock_session_instance = make_metrics_client_session_instance()
        with patch(
            "vastai.serverless.server.lib.metrics.ClientSession",
            return_value=mock_session_instance,
        ) as mock_cls:
            s1 = await m.http()
            s2 = await m.http()
        assert s1 is s2 is mock_session_instance
        mock_cls.assert_called_once()

    async def test_aclose_closes_and_clears_session(
        self, make_pyworker_metrics, make_metrics_client_session_instance
    ) -> None:
        """
        Verifies aclose awaits session.close and clears _session.

        This test verifies by:
        1. Using http() then aclose()
        2. Asserting close was awaited and _session is None

        Assumptions:
        - ClientSession.close is an awaitable
        """
        m = make_pyworker_metrics()
        mock_session_instance = make_metrics_client_session_instance(close_async=True)
        with patch(
            "vastai.serverless.server.lib.metrics.ClientSession",
            return_value=mock_session_instance,
        ):
            await m.http()
            await m.aclose()
        mock_session_instance.close.assert_awaited_once()
        assert m._session is None

    async def test_aclose_when_session_never_opened_does_nothing(self, make_pyworker_metrics) -> None:
        """
        Verifies aclose is safe when http() was never called (_session is None).

        This test verifies by:
        1. Instantiating Metrics without creating a session
        2. Awaiting aclose()
        3. Asserting _session remains None and no AttributeError is raised

        Assumptions:
        - Guard on self._session is not None prevents close on missing session
        """
        m = make_pyworker_metrics()
        assert m._session is None
        await m.aclose()
        assert m._session is None
