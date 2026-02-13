"""
Unit tests for vastai/serverless/server/lib/metrics.py

Tests the Metrics class request lifecycle methods without network calls.
"""
import pytest
from unittest.mock import MagicMock, patch
import sys
import os
from pathlib import Path

# Add vast-cli to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.fixture
def mock_env():
    """Mock environment variables required by Metrics class."""
    env = {
        "CONTAINER_ID": "12345",
        "REPORT_ADDR": "https://run.vast.ai",
        "PUBLIC_IPADDR": "192.168.1.100",
        "WORKER_PORT": "8080",
        "VAST_TCP_PORT_8080": "8080",
    }
    with patch.dict(os.environ, env, clear=False):
        # Clear the cached get_url function so it picks up new env vars
        from vastai.serverless.server.lib.metrics import get_url
        get_url.cache_clear()
        yield env


@pytest.fixture
def metrics(mock_env):
    """Create Metrics instance with mocked environment."""
    from vastai.serverless.server.lib.metrics import Metrics
    return Metrics()


@pytest.fixture
def request_metrics():
    """Create a RequestMetrics object for testing."""
    from vastai.serverless.server.lib.data_types import RequestMetrics
    return RequestMetrics(
        request_idx=1,
        reqnum=100,
        workload=50.0,
        status="Created"
    )


class TestMetricsInstantiation:
    """Tests for Metrics class instantiation."""

    def test_metrics_created_with_env_defaults(self, metrics, mock_env):
        """Metrics instance should use environment variables for defaults."""
        assert metrics.id == int(mock_env["CONTAINER_ID"])
        assert mock_env["REPORT_ADDR"] in metrics.report_addr
        assert metrics.version == "0"
        assert metrics.mtoken == ""
        assert metrics.update_pending is False

    def test_metrics_url_constructed_from_env(self, metrics, mock_env):
        """URL should be constructed from PUBLIC_IPADDR and port."""
        expected_url = f"http://{mock_env['PUBLIC_IPADDR']}:{mock_env['VAST_TCP_PORT_8080']}"
        assert metrics.url == expected_url

    def test_metrics_system_metrics_initialized(self, metrics):
        """System metrics should be initialized with empty factory."""
        assert metrics.system_metrics is not None
        assert metrics.system_metrics.model_is_loaded is False

    def test_metrics_model_metrics_initialized(self, metrics):
        """Model metrics should be initialized with empty factory."""
        assert metrics.model_metrics is not None
        assert metrics.model_metrics.workload_pending == 0.0
        assert metrics.model_metrics.workload_served == 0.0


class TestMetricsRequestStart:
    """Tests for _request_start method."""

    def test_updates_status_to_started(self, metrics, request_metrics):
        """_request_start should set request status to Started."""
        metrics._request_start(request_metrics)
        assert request_metrics.status == "Started"

    def test_increments_workload_pending(self, metrics, request_metrics):
        """_request_start should increase workload_pending by request workload."""
        metrics._request_start(request_metrics)
        assert metrics.model_metrics.workload_pending == request_metrics.workload

    def test_increments_workload_received(self, metrics, request_metrics):
        """_request_start should increase workload_received by request workload."""
        metrics._request_start(request_metrics)
        assert metrics.model_metrics.workload_received == request_metrics.workload

    def test_adds_to_requests_recieved(self, metrics, request_metrics):
        """_request_start should add reqnum to requests_recieved set."""
        metrics._request_start(request_metrics)
        assert request_metrics.reqnum in metrics.model_metrics.requests_recieved

    def test_adds_to_requests_working(self, metrics, request_metrics):
        """_request_start should add request to requests_working dict."""
        metrics._request_start(request_metrics)
        assert request_metrics.reqnum in metrics.model_metrics.requests_working
        assert metrics.model_metrics.requests_working[request_metrics.reqnum] == request_metrics

    def test_sets_update_pending_true(self, metrics, request_metrics):
        """_request_start should set update_pending to True."""
        metrics._request_start(request_metrics)
        assert metrics.update_pending is True


class TestMetricsRequestEnd:
    """Tests for _request_end method."""

    def test_decrements_workload_pending(self, metrics, request_metrics):
        """_request_end should decrease workload_pending by request workload."""
        # Start request first
        metrics._request_start(request_metrics)
        initial_pending = metrics.model_metrics.workload_pending

        metrics._request_end(request_metrics)
        assert metrics.model_metrics.workload_pending == initial_pending - request_metrics.workload

    def test_removes_from_requests_working(self, metrics, request_metrics):
        """_request_end should remove request from requests_working dict."""
        metrics._request_start(request_metrics)
        metrics._request_end(request_metrics)
        assert request_metrics.reqnum not in metrics.model_metrics.requests_working

    def test_adds_to_requests_deleting(self, metrics, request_metrics):
        """_request_end should add request to requests_deleting list."""
        metrics._request_start(request_metrics)
        metrics._request_end(request_metrics)
        assert request_metrics in metrics.model_metrics.requests_deleting

    def test_updates_last_request_served(self, metrics, request_metrics):
        """_request_end should update last_request_served timestamp."""
        metrics._request_start(request_metrics)
        metrics._request_end(request_metrics)
        assert metrics.last_request_served > 0


class TestMetricsRequestSuccess:
    """Tests for _request_success method."""

    def test_increments_workload_served(self, metrics, request_metrics):
        """_request_success should increase workload_served by request workload."""
        metrics._request_success(request_metrics)
        assert metrics.model_metrics.workload_served == request_metrics.workload

    def test_sets_status_to_success(self, metrics, request_metrics):
        """_request_success should set request status to Success."""
        metrics._request_success(request_metrics)
        assert request_metrics.status == "Success"

    def test_sets_success_flag_true(self, metrics, request_metrics):
        """_request_success should set request success flag to True."""
        metrics._request_success(request_metrics)
        assert request_metrics.success is True

    def test_sets_update_pending_true(self, metrics, request_metrics):
        """_request_success should set update_pending to True."""
        metrics._request_success(request_metrics)
        assert metrics.update_pending is True


class TestMetricsRequestErrored:
    """Tests for _request_errored method."""

    def test_increments_workload_errored(self, metrics, request_metrics):
        """_request_errored should increase workload_errored by request workload."""
        metrics._request_errored(request_metrics, "Test error")
        assert metrics.model_metrics.workload_errored == request_metrics.workload

    def test_sets_status_to_error(self, metrics, request_metrics):
        """_request_errored should set request status to Error."""
        metrics._request_errored(request_metrics, "Test error")
        assert request_metrics.status == "Error"

    def test_sets_success_flag_false(self, metrics, request_metrics):
        """_request_errored should set request success flag to False."""
        metrics._request_errored(request_metrics, "Test error")
        assert request_metrics.success is False

    def test_sets_update_pending_true(self, metrics, request_metrics):
        """_request_errored should set update_pending to True."""
        metrics._request_errored(request_metrics, "Test error")
        assert metrics.update_pending is True


class TestMetricsRequestCanceled:
    """Tests for _request_canceled method."""

    def test_increments_workload_cancelled(self, metrics, request_metrics):
        """_request_canceled should increase workload_cancelled by request workload."""
        metrics._request_canceled(request_metrics)
        assert metrics.model_metrics.workload_cancelled == request_metrics.workload

    def test_sets_status_to_cancelled(self, metrics, request_metrics):
        """_request_canceled should set request status to Cancelled."""
        metrics._request_canceled(request_metrics)
        assert request_metrics.status == "Cancelled"

    def test_sets_success_flag_true(self, metrics, request_metrics):
        """_request_canceled should set request success flag to True (cancelled = successful cleanup)."""
        metrics._request_canceled(request_metrics)
        assert request_metrics.success is True


class TestMetricsRequestReject:
    """Tests for _request_reject method."""

    def test_increments_workload_rejected(self, metrics, request_metrics):
        """_request_reject should increase workload_rejected by request workload."""
        metrics._request_reject(request_metrics)
        assert metrics.model_metrics.workload_rejected == request_metrics.workload

    def test_sets_status_to_rejected(self, metrics, request_metrics):
        """_request_reject should set request status to Rejected."""
        metrics._request_reject(request_metrics)
        assert request_metrics.status == "Rejected"

    def test_sets_success_flag_false(self, metrics, request_metrics):
        """_request_reject should set request success flag to False."""
        metrics._request_reject(request_metrics)
        assert request_metrics.success is False

    def test_adds_to_requests_recieved(self, metrics, request_metrics):
        """_request_reject should add reqnum to requests_recieved set."""
        metrics._request_reject(request_metrics)
        assert request_metrics.reqnum in metrics.model_metrics.requests_recieved

    def test_adds_to_requests_deleting(self, metrics, request_metrics):
        """_request_reject should add request to requests_deleting list."""
        metrics._request_reject(request_metrics)
        assert request_metrics in metrics.model_metrics.requests_deleting

    def test_sets_update_pending_true(self, metrics, request_metrics):
        """_request_reject should set update_pending to True."""
        metrics._request_reject(request_metrics)
        assert metrics.update_pending is True


class TestMetricsModelLoaded:
    """Tests for _model_loaded method."""

    def test_sets_model_is_loaded_true(self, metrics):
        """_model_loaded should set system_metrics.model_is_loaded to True."""
        metrics._model_loaded(max_throughput=100.0)
        assert metrics.system_metrics.model_is_loaded is True

    def test_sets_max_throughput(self, metrics):
        """_model_loaded should set model_metrics.max_throughput."""
        metrics._model_loaded(max_throughput=150.5)
        assert metrics.model_metrics.max_throughput == 150.5

    def test_calculates_loading_time(self, metrics):
        """_model_loaded should calculate model_loading_time from start time."""
        metrics._model_loaded(max_throughput=100.0)
        # Loading time should be >= 0 (time since model_loading_start)
        assert metrics.system_metrics.model_loading_time >= 0


class TestMetricsModelErrored:
    """Tests for _model_errored method."""

    def test_sets_error_msg(self, metrics):
        """_model_errored should set model_metrics.error_msg."""
        metrics._model_errored("Model failed to load")
        assert metrics.model_metrics.error_msg == "Model failed to load"

    def test_sets_model_is_loaded_true(self, metrics):
        """_model_errored should set system_metrics.model_is_loaded to True."""
        metrics._model_errored("Model failed to load")
        assert metrics.system_metrics.model_is_loaded is True


class TestMetricsSetters:
    """Tests for simple setter methods."""

    def test_set_version(self, metrics):
        """_set_version should update version field."""
        metrics._set_version("2.0.1")
        assert metrics.version == "2.0.1"

    def test_set_mtoken(self, metrics):
        """_set_mtoken should update mtoken field."""
        metrics._set_mtoken("secret-token-123")
        assert metrics.mtoken == "secret-token-123"


class TestMetricsUrlWithSSL:
    """Tests for URL construction with SSL enabled."""

    def test_url_with_ssl_enabled(self):
        """URL should use https when USE_SSL=true."""
        env = {
            "CONTAINER_ID": "12345",
            "REPORT_ADDR": "https://run.vast.ai",
            "PUBLIC_IPADDR": "192.168.1.100",
            "WORKER_PORT": "8080",
            "VAST_TCP_PORT_8080": "8080",
            "USE_SSL": "true",
        }
        with patch.dict(os.environ, env, clear=False):
            from vastai.serverless.server.lib.metrics import get_url, Metrics
            get_url.cache_clear()
            metrics = Metrics()
            assert metrics.url.startswith("https://")


class TestMetricsMultipleRequests:
    """Tests for handling multiple concurrent requests."""

    def test_multiple_requests_tracked_independently(self, metrics):
        """Multiple requests should be tracked independently."""
        from vastai.serverless.server.lib.data_types import RequestMetrics

        req1 = RequestMetrics(request_idx=1, reqnum=100, workload=50.0, status="Created")
        req2 = RequestMetrics(request_idx=2, reqnum=101, workload=75.0, status="Created")

        metrics._request_start(req1)
        metrics._request_start(req2)

        # Both should be tracked
        assert len(metrics.model_metrics.requests_working) == 2
        assert metrics.model_metrics.workload_pending == 125.0  # 50 + 75

        # End one request
        metrics._request_success(req1)
        metrics._request_end(req1)

        # Only one should remain
        assert len(metrics.model_metrics.requests_working) == 1
        assert req2.reqnum in metrics.model_metrics.requests_working
