"""Unit tests for vastai.serverless.server.lib.data_types module.

Tests cover:
- JsonDataException: message storage
- AuthData: from_json_msg with valid/missing/extra fields
- SystemMetrics: empty() factory, update_disk_usage(), reset()
- RequestMetrics: dataclass instantiation
- BenchmarkResult: is_successful property
- ModelMetrics: empty() factory, properties, set_errored(), reset()
- WorkerStatusData: dataclass instantiation
- LogAction enum: value validation
"""
import pytest
from unittest.mock import MagicMock, patch
import sys
import time
from pathlib import Path

# Add vast-cli to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from vastai.serverless.server.lib.data_types import (
    JsonDataException,
    AuthData,
    SystemMetrics,
    RequestMetrics,
    BenchmarkResult,
    ModelMetrics,
    WorkerStatusData,
    LogAction,
)


class TestJsonDataException:
    """Tests for JsonDataException class."""

    def test_stores_message_dict(self):
        """JsonDataException stores the error message dict."""
        error_msg = {"field": "missing parameter"}
        exc = JsonDataException(error_msg)
        assert exc.message == {"field": "missing parameter"}

    def test_multiple_fields_in_message(self):
        """JsonDataException can store multiple field errors."""
        error_msg = {"cost": "missing parameter", "endpoint": "invalid format"}
        exc = JsonDataException(error_msg)
        assert exc.message == error_msg
        assert "cost" in exc.message
        assert "endpoint" in exc.message

    def test_is_exception(self):
        """JsonDataException is a proper Exception subclass."""
        exc = JsonDataException({"error": "test"})
        assert isinstance(exc, Exception)


class TestAuthData:
    """Tests for AuthData dataclass."""

    def test_from_json_msg_valid(self):
        """AuthData.from_json_msg creates instance with valid data."""
        json_msg = {
            "cost": "0.10",
            "endpoint": "/api/test",
            "reqnum": 1,
            "request_idx": 0,
            "signature": "abc123",
            "url": "https://example.com",
        }
        auth = AuthData.from_json_msg(json_msg)
        assert auth.cost == "0.10"
        assert auth.endpoint == "/api/test"
        assert auth.reqnum == 1
        assert auth.request_idx == 0
        assert auth.signature == "abc123"
        assert auth.url == "https://example.com"

    def test_from_json_msg_missing_field_raises(self):
        """AuthData.from_json_msg raises JsonDataException for missing fields."""
        json_msg = {
            "cost": "0.10",
            "endpoint": "/api/test",
            # missing reqnum, request_idx, signature, url
        }
        with pytest.raises(JsonDataException) as exc_info:
            AuthData.from_json_msg(json_msg)
        assert "reqnum" in exc_info.value.message
        assert "request_idx" in exc_info.value.message
        assert "signature" in exc_info.value.message
        assert "url" in exc_info.value.message

    def test_from_json_msg_single_missing_field(self):
        """AuthData.from_json_msg reports single missing field."""
        json_msg = {
            "cost": "0.10",
            "endpoint": "/api/test",
            "reqnum": 1,
            "request_idx": 0,
            "signature": "abc123",
            # missing url
        }
        with pytest.raises(JsonDataException) as exc_info:
            AuthData.from_json_msg(json_msg)
        assert "url" in exc_info.value.message
        assert exc_info.value.message["url"] == "missing parameter"

    def test_from_json_msg_extra_fields_ignored(self):
        """AuthData.from_json_msg ignores extra fields."""
        json_msg = {
            "cost": "0.10",
            "endpoint": "/api/test",
            "reqnum": 1,
            "request_idx": 0,
            "signature": "abc123",
            "url": "https://example.com",
            "extra_field": "should be ignored",
            "another_extra": 12345,
        }
        auth = AuthData.from_json_msg(json_msg)
        assert auth.cost == "0.10"
        assert not hasattr(auth, "extra_field")
        assert not hasattr(auth, "another_extra")


class TestSystemMetrics:
    """Tests for SystemMetrics dataclass."""

    @patch("vastai.serverless.server.lib.data_types.psutil.disk_usage")
    @patch("vastai.serverless.server.lib.data_types.time.time")
    def test_empty_factory(self, mock_time, mock_disk_usage):
        """SystemMetrics.empty() creates instance with default values."""
        mock_time.return_value = 1000.0
        mock_disk_usage.return_value = MagicMock(used=10 * (2**30))  # 10 GB

        metrics = SystemMetrics.empty()

        assert metrics.model_loading_start == 1000.0
        assert metrics.model_loading_time is None
        assert metrics.last_disk_usage == 10.0  # GB
        assert metrics.additional_disk_usage == 0.0
        assert metrics.model_is_loaded is False

    @patch("vastai.serverless.server.lib.data_types.psutil.disk_usage")
    def test_update_disk_usage(self, mock_disk_usage):
        """SystemMetrics.update_disk_usage() updates disk usage stats."""
        # Initial disk usage: 10 GB
        metrics = SystemMetrics(
            model_loading_start=0.0,
            model_loading_time=None,
            last_disk_usage=10.0,
            additional_disk_usage=0.0,
            model_is_loaded=False,
        )

        # After update: 15 GB used
        mock_disk_usage.return_value = MagicMock(used=15 * (2**30))
        metrics.update_disk_usage()

        assert metrics.last_disk_usage == 15.0
        assert metrics.additional_disk_usage == 5.0  # 15 - 10

    def test_reset_clears_loading_time_when_expected(self):
        """SystemMetrics.reset() clears model_loading_time when matching expected."""
        metrics = SystemMetrics(
            model_loading_start=0.0,
            model_loading_time=5.0,
            last_disk_usage=10.0,
            additional_disk_usage=0.0,
            model_is_loaded=True,
        )

        metrics.reset(expected=5.0)
        assert metrics.model_loading_time is None

    def test_reset_preserves_loading_time_when_different(self):
        """SystemMetrics.reset() preserves model_loading_time when not matching expected."""
        metrics = SystemMetrics(
            model_loading_start=0.0,
            model_loading_time=5.0,
            last_disk_usage=10.0,
            additional_disk_usage=0.0,
            model_is_loaded=True,
        )

        metrics.reset(expected=10.0)  # Different from current value
        assert metrics.model_loading_time == 5.0  # Preserved

    def test_reset_with_none_expected(self):
        """SystemMetrics.reset() with None expected clears None loading time."""
        metrics = SystemMetrics(
            model_loading_start=0.0,
            model_loading_time=None,
            last_disk_usage=10.0,
            additional_disk_usage=0.0,
            model_is_loaded=False,
        )

        metrics.reset(expected=None)
        assert metrics.model_loading_time is None


class TestRequestMetrics:
    """Tests for RequestMetrics dataclass."""

    def test_instantiation_required_fields(self):
        """RequestMetrics can be instantiated with required fields."""
        metrics = RequestMetrics(
            request_idx=0,
            reqnum=1,
            workload=1.5,
            status="processing",
        )
        assert metrics.request_idx == 0
        assert metrics.reqnum == 1
        assert metrics.workload == 1.5
        assert metrics.status == "processing"
        assert metrics.success is False  # default

    def test_instantiation_with_success(self):
        """RequestMetrics respects success parameter."""
        metrics = RequestMetrics(
            request_idx=1,
            reqnum=2,
            workload=2.0,
            status="completed",
            success=True,
        )
        assert metrics.success is True


class TestBenchmarkResult:
    """Tests for BenchmarkResult dataclass."""

    def test_is_successful_true(self):
        """BenchmarkResult.is_successful returns True for 200 response."""
        mock_response = MagicMock()
        mock_response.status = 200

        mock_task = MagicMock()
        result = BenchmarkResult(
            request_idx=0,
            workload=1.0,
            task=mock_task,
            response=mock_response,
        )
        assert result.is_successful is True

    def test_is_successful_false_non_200(self):
        """BenchmarkResult.is_successful returns False for non-200 response."""
        mock_response = MagicMock()
        mock_response.status = 500

        mock_task = MagicMock()
        result = BenchmarkResult(
            request_idx=0,
            workload=1.0,
            task=mock_task,
            response=mock_response,
        )
        assert result.is_successful is False

    def test_is_successful_false_no_response(self):
        """BenchmarkResult.is_successful returns False when response is None."""
        mock_task = MagicMock()
        result = BenchmarkResult(
            request_idx=0,
            workload=1.0,
            task=mock_task,
            response=None,  # No response yet
        )
        assert result.is_successful is False


class TestModelMetrics:
    """Tests for ModelMetrics dataclass."""

    def test_empty_factory(self):
        """ModelMetrics.empty() creates instance with zero values."""
        metrics = ModelMetrics.empty()
        assert metrics.workload_pending == 0.0
        assert metrics.workload_served == 0.0
        assert metrics.workload_cancelled == 0.0
        assert metrics.workload_errored == 0.0
        assert metrics.workload_rejected == 0.0
        assert metrics.workload_received == 0.0
        assert metrics.error_msg is None
        assert metrics.max_throughput == 0.0

    def test_workload_processing_property(self):
        """ModelMetrics.workload_processing computes correctly."""
        metrics = ModelMetrics.empty()
        metrics.workload_received = 10.0
        metrics.workload_cancelled = 3.0
        assert metrics.workload_processing == 7.0  # 10 - 3

    def test_workload_processing_never_negative(self):
        """ModelMetrics.workload_processing is clamped to 0."""
        metrics = ModelMetrics.empty()
        metrics.workload_received = 5.0
        metrics.workload_cancelled = 10.0  # More cancelled than received
        assert metrics.workload_processing == 0.0

    def test_wait_time_empty_requests(self):
        """ModelMetrics.wait_time returns 0 when no requests working."""
        metrics = ModelMetrics.empty()
        assert metrics.wait_time == 0.0

    def test_wait_time_calculation(self):
        """ModelMetrics.wait_time computes workload/throughput."""
        metrics = ModelMetrics.empty()
        metrics.max_throughput = 10.0
        metrics.requests_working = {
            0: RequestMetrics(request_idx=0, reqnum=1, workload=5.0, status="working"),
            1: RequestMetrics(request_idx=1, reqnum=2, workload=5.0, status="working"),
        }
        # wait_time = sum(workloads) / max_throughput = 10.0 / 10.0 = 1.0
        assert metrics.wait_time == 1.0

    def test_wait_time_near_zero_throughput(self):
        """ModelMetrics.wait_time handles near-zero throughput gracefully."""
        metrics = ModelMetrics.empty()
        metrics.max_throughput = 0.0  # Will use 0.00001 denominator
        metrics.requests_working = {
            0: RequestMetrics(request_idx=0, reqnum=1, workload=1.0, status="working"),
        }
        # Should not raise ZeroDivisionError
        result = metrics.wait_time
        assert result == 1.0 / 0.00001  # Very large but finite

    def test_cur_load_property(self):
        """ModelMetrics.cur_load sums workload from working requests."""
        metrics = ModelMetrics.empty()
        metrics.requests_working = {
            0: RequestMetrics(request_idx=0, reqnum=1, workload=2.0, status="working"),
            1: RequestMetrics(request_idx=1, reqnum=2, workload=3.0, status="working"),
        }
        assert metrics.cur_load == 5.0

    def test_cur_load_empty(self):
        """ModelMetrics.cur_load returns 0 for no working requests."""
        metrics = ModelMetrics.empty()
        assert metrics.cur_load == 0.0

    def test_working_request_idxs_property(self):
        """ModelMetrics.working_request_idxs returns list of request indices."""
        metrics = ModelMetrics.empty()
        metrics.requests_working = {
            0: RequestMetrics(request_idx=0, reqnum=1, workload=1.0, status="working"),
            5: RequestMetrics(request_idx=5, reqnum=6, workload=1.0, status="working"),
        }
        idxs = metrics.working_request_idxs
        assert 0 in idxs
        assert 5 in idxs

    def test_set_errored(self):
        """ModelMetrics.set_errored resets metrics and sets error message."""
        metrics = ModelMetrics.empty()
        metrics.workload_served = 10.0
        metrics.workload_received = 20.0

        metrics.set_errored("Test error message")

        assert metrics.error_msg == "Test error message"
        assert metrics.workload_served == 0
        assert metrics.workload_received == 0

    def test_reset(self):
        """ModelMetrics.reset clears workload counters."""
        metrics = ModelMetrics.empty()
        metrics.workload_served = 10.0
        metrics.workload_received = 20.0
        metrics.workload_cancelled = 5.0
        metrics.workload_errored = 2.0
        metrics.workload_rejected = 1.0

        metrics.reset()

        assert metrics.workload_served == 0
        assert metrics.workload_received == 0
        assert metrics.workload_cancelled == 0
        assert metrics.workload_errored == 0
        assert metrics.workload_rejected == 0


class TestWorkerStatusData:
    """Tests for WorkerStatusData dataclass."""

    def test_instantiation_all_fields(self):
        """WorkerStatusData can be instantiated with all fields."""
        status = WorkerStatusData(
            id=123,
            mtoken="token-abc",
            version="1.0.0",
            loadtime=5.0,
            cur_load=2.0,
            rej_load=0.5,
            new_load=1.5,
            error_msg="",
            max_perf=10.0,
            cur_perf=8.0,
            cur_capacity=100.0,
            max_capacity=200.0,
            num_requests_working=3,
            num_requests_recieved=10,
            additional_disk_usage=1.5,
            working_request_idxs=[0, 1, 2],
            url="https://worker.example.com",
        )

        assert status.id == 123
        assert status.mtoken == "token-abc"
        assert status.version == "1.0.0"
        assert status.loadtime == 5.0
        assert status.cur_load == 2.0
        assert status.rej_load == 0.5
        assert status.new_load == 1.5
        assert status.error_msg == ""
        assert status.max_perf == 10.0
        assert status.cur_perf == 8.0
        assert status.cur_capacity == 100.0
        assert status.max_capacity == 200.0
        assert status.num_requests_working == 3
        assert status.num_requests_recieved == 10
        assert status.additional_disk_usage == 1.5
        assert status.working_request_idxs == [0, 1, 2]
        assert status.url == "https://worker.example.com"


class TestLogAction:
    """Tests for LogAction enum."""

    def test_model_loaded_value(self):
        """LogAction.ModelLoaded has value 1."""
        assert LogAction.ModelLoaded.value == 1

    def test_model_error_value(self):
        """LogAction.ModelError has value 2."""
        assert LogAction.ModelError.value == 2

    def test_info_value(self):
        """LogAction.Info has value 3."""
        assert LogAction.Info.value == 3

    def test_all_members_exist(self):
        """All expected LogAction members exist."""
        members = list(LogAction)
        assert len(members) == 3
        assert LogAction.ModelLoaded in members
        assert LogAction.ModelError in members
        assert LogAction.Info in members
