"""Unit tests for vastai.serverless.server.lib.data_types (pyworker server types)."""
from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vastai.serverless.server.lib.data_types import (
    ApiPayload,
    AuthData,
    BenchmarkResult,
    EndpointHandler,
    JsonDataException,
    LogAction,
    ModelMetrics,
    RequestMetrics,
    Session,
    SystemMetrics,
    WorkerStatusData,
)


# ---------------------------------------------------------------------------
# Test doubles for EndpointHandler.get_data_from_request
# ---------------------------------------------------------------------------


@dataclass
class DummyPayload(ApiPayload):
    """Minimal ApiPayload for exercising deserialization in tests."""

    value: int = 0

    @classmethod
    def for_test(cls):
        return cls(value=1)

    def generate_payload_json(self):
        return {"value": self.value}

    def count_workload(self):
        return float(self.value)

    @classmethod
    def from_json_msg(cls, json_msg):
        if "value" not in json_msg:
            raise JsonDataException({"value": "missing parameter"})
        return cls(value=int(json_msg["value"]))


@dataclass
class DummyHandler(EndpointHandler):
    """Concrete handler so get_data_from_request can be called on a real class."""

    @property
    def endpoint(self) -> str:
        return "/predict"

    @property
    def healthcheck_endpoint(self):
        return None

    @classmethod
    def payload_cls(cls):
        return DummyPayload

    def make_benchmark_payload(self):
        return DummyPayload.for_test()

    async def generate_client_response(self, client_request, model_response):
        return MagicMock()

    async def call_remote_dispatch_function(self, params: dict):
        return None


@dataclass
class FalsyPayload(ApiPayload):
    """Payload whose from_json_msg returns None to exercise deserialize fallback."""

    @classmethod
    def for_test(cls):
        return cls()

    def generate_payload_json(self):
        return {}

    def count_workload(self):
        return 0.0

    @classmethod
    def from_json_msg(cls, json_msg):
        return None


@dataclass
class FalsyPayloadHandler(EndpointHandler):
    """Handler pairing with FalsyPayload for get_data_from_request edge case."""

    @property
    def endpoint(self) -> str:
        return "/x"

    @property
    def healthcheck_endpoint(self):
        return None

    @classmethod
    def payload_cls(cls):
        return FalsyPayload

    def make_benchmark_payload(self):
        return FalsyPayload.for_test()

    async def generate_client_response(self, client_request, model_response):
        return MagicMock()

    async def call_remote_dispatch_function(self, params: dict):
        return None


class TestJsonDataException:
    """JsonDataException stores structured error payloads."""

    def test_init_stores_message_dict(self) -> None:
        """
        Verifies that JsonDataException keeps the JSON error map on .message.

        This test verifies by:
        1. Constructing JsonDataException with a dict of field errors
        2. Asserting exception.message is the same dict

        Assumptions:
        - No external I/O; pure exception construction
        """
        err = {"field": "bad"}
        exc = JsonDataException(err)
        assert exc.message == err


class TestAuthDataFromJsonMsg:
    """AuthData.from_json_msg validates required fields."""

    def test_from_json_msg_with_all_fields_returns_auth_data(
        self, valid_auth_data_dict
    ) -> None:
        """
        Verifies successful construction when every dataclass field is present.

        This test verifies by:
        1. Building a dict with all AuthData field names
        2. Calling AuthData.from_json_msg
        3. Asserting each attribute matches the input

        Assumptions:
        - inspect.signature(AuthData) matches dataclass fields used for validation
        """
        data = valid_auth_data_dict
        auth = AuthData.from_json_msg(data)
        assert auth.cost == data["cost"]
        assert auth.endpoint == data["endpoint"]
        assert auth.reqnum == data["reqnum"]
        assert auth.request_idx == data["request_idx"]
        assert auth.signature == data["signature"]
        assert auth.url == data["url"]

    def test_from_json_msg_missing_field_raises_json_data_exception(
        self, valid_auth_data_dict
    ) -> None:
        """
        Verifies missing required parameters produce JsonDataException with per-field errors.

        This test verifies by:
        1. Omitting one required key from the input dict
        2. Asserting JsonDataException is raised
        3. Asserting the exception message maps missing keys to 'missing parameter'

        Assumptions:
        - 'signature' is a required AuthData field
        """
        data = {**valid_auth_data_dict}
        del data["signature"]
        with pytest.raises(JsonDataException) as ctx:
            AuthData.from_json_msg(data)
        assert "signature" in ctx.value.message
        assert ctx.value.message["signature"] == "missing parameter"

    def test_from_json_msg_ignores_unknown_keys(self, valid_auth_data_dict) -> None:
        """
        Verifies extra keys in JSON do not break construction or appear on the instance.

        This test verifies by:
        1. Adding an extra key not in AuthData
        2. Calling from_json_msg
        3. Asserting the returned object has only expected attributes

        Assumptions:
        - Filtering uses inspect.signature parameters only
        """
        data = {**valid_auth_data_dict, "extra": "ignored"}
        auth = AuthData.from_json_msg(data)
        assert not hasattr(auth, "extra")


class TestEndpointHandlerGetDataFromRequest:
    """EndpointHandler.get_data_from_request parses auth, payload, and optional session_id."""

    def test_get_data_from_request_returns_auth_payload_and_none_session(
        self, valid_auth_data_dict
    ) -> None:
        """
        Verifies happy path returns auth, payload, and None session_id when omitted.

        This test verifies by:
        1. Passing valid auth_data and payload dicts
        2. Calling DummyHandler.get_data_from_request
        3. Asserting a 3-tuple (auth, payload, session_id) with session_id None

        Assumptions:
        - Backend unpacks three values (see vastai.serverless.server.lib.backend)
        """
        req = {
            "auth_data": valid_auth_data_dict,
            "payload": {"value": 7},
        }
        auth, payload, session_id = DummyHandler.get_data_from_request(req)
        assert isinstance(auth, AuthData)
        assert isinstance(payload, DummyPayload)
        assert payload.value == 7
        assert session_id is None

    def test_get_data_from_request_includes_session_id_when_present(
        self, valid_auth_data_dict
    ) -> None:
        """
        Verifies session_id from req_data is returned as the third element.

        This test verifies by:
        1. Including session_id in the request dict
        2. Calling get_data_from_request
        3. Asserting the third tuple element matches

        Assumptions:
        - session_id is optional and passed through without validation
        """
        req = {
            "auth_data": valid_auth_data_dict,
            "payload": {"value": 1},
            "session_id": "sess-abc",
        }
        _, _, session_id = DummyHandler.get_data_from_request(req)
        assert session_id == "sess-abc"

    def test_get_data_from_request_missing_auth_data_raises(self) -> None:
        """
        Verifies absent auth_data yields JsonDataException.

        This test verifies by:
        1. Omitting auth_data key
        2. Asserting JsonDataException with errors describing auth_data

        Assumptions:
        - Payload is valid so only auth errors are present
        """
        req = {"payload": {"value": 1}}
        with pytest.raises(JsonDataException) as ctx:
            DummyHandler.get_data_from_request(req)
        assert ctx.value.message["auth_data"] == "field missing"

    def test_get_data_from_request_missing_payload_raises(
        self, valid_auth_data_dict
    ) -> None:
        """
        Verifies absent payload yields JsonDataException.

        This test verifies by:
        1. Omitting payload key with valid auth_data
        2. Asserting JsonDataException mentions payload

        Assumptions:
        - auth_data alone is insufficient
        """
        req = {"auth_data": valid_auth_data_dict}
        with pytest.raises(JsonDataException) as ctx:
            DummyHandler.get_data_from_request(req)
        assert ctx.value.message["payload"] == "field missing"

    def test_get_data_from_request_invalid_auth_merges_errors(self) -> None:
        """
        Verifies AuthData validation failures appear under errors['auth_data'].

        This test verifies by:
        1. Supplying incomplete auth_data
        2. Asserting JsonDataException.message['auth_data'] is the nested error dict

        Assumptions:
        - JsonDataException from AuthData is caught and re-wrapped per field
        """
        bad_auth = {"cost": "1"}  # missing other required fields
        req = {"auth_data": bad_auth, "payload": {"value": 1}}
        with pytest.raises(JsonDataException) as ctx:
            DummyHandler.get_data_from_request(req)
        inner = ctx.value.message["auth_data"]
        assert isinstance(inner, dict)
        assert "endpoint" in inner

    def test_get_data_from_request_invalid_payload_merges_errors(
        self, valid_auth_data_dict
    ) -> None:
        """
        Verifies payload from_json_msg JsonDataException maps to errors['payload'].

        This test verifies by:
        1. Passing payload missing required 'value' for DummyPayload
        2. Asserting merged errors contain payload field errors

        Assumptions:
        - DummyPayload.from_json_msg raises JsonDataException like real payloads
        """
        req = {"auth_data": valid_auth_data_dict, "payload": {}}
        with pytest.raises(JsonDataException) as ctx:
            DummyHandler.get_data_from_request(req)
        assert "value" in ctx.value.message["payload"]

    def test_get_data_from_request_merges_auth_and_payload_errors_together(self) -> None:
        """
        Verifies invalid auth and invalid payload both appear in one JsonDataException.

        This test verifies by:
        1. Sending incomplete auth_data and empty payload in the same req_data
        2. Asserting exception.message contains both 'auth_data' and 'payload' entries

        Assumptions:
        - Each try/except block records its own JsonDataException before the combined raise
        """
        bad_auth = {"cost": "1"}
        req = {"auth_data": bad_auth, "payload": {}}
        with pytest.raises(JsonDataException) as ctx:
            DummyHandler.get_data_from_request(req)
        msg = ctx.value.message
        assert "auth_data" in msg
        assert "payload" in msg
        assert isinstance(msg["auth_data"], dict)
        assert "endpoint" in msg["auth_data"]
        assert "value" in msg["payload"]

    def test_get_data_from_request_raises_generic_exception_when_payload_falsy(
        self,
        valid_auth_data_dict,
    ) -> None:
        """
        Verifies generic Exception when no field errors but payload deserialize is falsy.

        This test verifies by:
        1. Using a payload type whose from_json_msg returns None with valid auth
        2. Asserting Exception with message 'error deserializing request data'

        Assumptions:
        - Branch at data_types.get_data_from_request when auth_data truthy but payload falsy
        """
        req = {"auth_data": valid_auth_data_dict, "payload": {"ignored": True}}
        with pytest.raises(Exception, match="error deserializing request data"):
            FalsyPayloadHandler.get_data_from_request(req)


class TestApiPayloadAbstract:
    """ApiPayload remains abstract; concrete subclasses supply behavior."""

    def test_api_payload_cannot_be_instantiated_without_concrete_methods(self) -> None:
        """
        Verifies direct instantiation of ApiPayload raises TypeError (abstract methods).

        This test verifies by:
        1. Calling ApiPayload() with no subclass
        2. Asserting TypeError from ABC machinery

        Assumptions:
        - Python ABC prevents instantiating incomplete implementations
        """
        with pytest.raises(TypeError):
            ApiPayload()


class TestEndpointHandlerAbstract:
    """EndpointHandler concrete instance exposes defaults and implemented API."""

    def test_endpoint_handler_cannot_be_instantiated_without_concrete_methods(
        self,
    ) -> None:
        """
        Verifies EndpointHandler is abstract until all methods are implemented.

        This test verifies by:
        1. Attempting EndpointHandler()
        2. Asserting TypeError

        Assumptions:
        - ABC enforces endpoint, payload_cls, async hooks, etc.
        """
        with pytest.raises(TypeError):
            EndpointHandler()

    @pytest.mark.asyncio
    async def test_dummy_handler_exposes_endpoint_and_async_hooks(self) -> None:
        """
        Verifies DummyHandler implements the abstract server contract for callers.

        This test verifies by:
        1. Instantiating DummyHandler and reading endpoint and healthcheck_endpoint
        2. Awaiting generate_client_response and call_remote_dispatch_function

        Assumptions:
        - aiohttp objects are mocked; no real server or HTTP
        """
        h = DummyHandler()
        assert h.endpoint == "/predict"
        assert h.healthcheck_endpoint is None
        assert isinstance(h.make_benchmark_payload(), DummyPayload)
        resp = await h.generate_client_response(MagicMock(), MagicMock())
        assert resp is not None
        assert await h.call_remote_dispatch_function({}) is None


class TestSystemMetrics:
    """SystemMetrics.empty, disk usage helpers, and reset behavior."""

    def test_empty_sets_loading_start_and_disk_from_helpers(self) -> None:
        """
        Verifies empty() uses time.time and get_disk_usage_GB for initial fields.

        This test verifies by:
        1. Patching time.time and SystemMetrics.get_disk_usage_GB to fixed values
        2. Calling SystemMetrics.empty()
        3. Asserting model_loading_start, last_disk_usage, and defaults

        Assumptions:
        - Patches restore automatically via context managers (RAII)
        """
        with patch(
            "vastai.serverless.server.lib.data_types.time.time", return_value=12345.0
        ):
            with patch.object(
                SystemMetrics, "get_disk_usage_GB", return_value=99.5
            ) as mock_disk:
                m = SystemMetrics.empty()
        mock_disk.assert_called()
        assert m.model_loading_start == 12345.0
        assert m.model_loading_time is None
        assert m.last_disk_usage == 99.5
        assert m.additional_disk_usage == 0.0
        assert m.model_is_loaded is False

    def test_update_disk_usage_sets_additional_and_last(self) -> None:
        """
        Verifies update_disk_usage computes delta from last_disk_usage.

        This test verifies by:
        1. Constructing SystemMetrics with known last_disk_usage
        2. Patching get_disk_usage_GB to a larger value
        3. Calling update_disk_usage and asserting additional_disk_usage and last

        Assumptions:
        - get_disk_usage_GB is the source of current usage (mocked, no real psutil)
        """
        m = SystemMetrics(
            model_loading_start=0.0,
            model_loading_time=None,
            last_disk_usage=10.0,
            additional_disk_usage=0.0,
            model_is_loaded=False,
        )
        with patch.object(SystemMetrics, "get_disk_usage_GB", return_value=13.0):
            m.update_disk_usage()
        assert m.last_disk_usage == 13.0
        assert m.additional_disk_usage == 3.0

    def test_reset_clears_model_loading_time_when_matches_expected(self) -> None:
        """
        Verifies reset(None) clears model_loading_time when it is already None.

        This test verifies by:
        1. Building metrics with model_loading_time None
        2. Calling reset(None)
        3. Asserting model_loading_time stays None

        Assumptions:
        - Condition is equality check against expected argument
        """
        m = SystemMetrics(
            model_loading_start=0.0,
            model_loading_time=None,
            last_disk_usage=0.0,
            additional_disk_usage=0.0,
            model_is_loaded=True,
        )
        m.reset(None)
        assert m.model_loading_time is None

    def test_reset_clears_model_loading_time_when_equal_to_expected(self) -> None:
        """
        Verifies reset(expected) sets model_loading_time to None when it equals expected.

        This test verifies by:
        1. Setting model_loading_time to a known float
        2. Calling reset with that same float
        3. Asserting model_loading_time becomes None

        Assumptions:
        - Autoscaler one-shot semantics per data_types docstring
        """
        m = SystemMetrics(
            model_loading_start=0.0,
            model_loading_time=42.0,
            last_disk_usage=0.0,
            additional_disk_usage=0.0,
            model_is_loaded=True,
        )
        m.reset(42.0)
        assert m.model_loading_time is None

    def test_reset_leaves_model_loading_time_when_expected_mismatch(self) -> None:
        """
        Verifies reset does not clear model_loading_time when value differs from expected.

        This test verifies by:
        1. Setting model_loading_time to 10.0
        2. Calling reset(99.0)
        3. Asserting model_loading_time remains 10.0

        Assumptions:
        - Inequality means no reset of loading time
        """
        m = SystemMetrics(
            model_loading_start=0.0,
            model_loading_time=10.0,
            last_disk_usage=0.0,
            additional_disk_usage=0.0,
            model_is_loaded=True,
        )
        m.reset(99.0)
        assert m.model_loading_time == 10.0

    def test_get_disk_usage_gb_converts_psutil_used_bytes_to_gb(self) -> None:
        """
        Verifies get_disk_usage_GB reads root mount usage and converts to gigabytes.

        This test verifies by:
        1. Patching psutil.disk_usage to return a mock with .used in bytes
        2. Calling SystemMetrics.get_disk_usage_GB()
        3. Asserting disk_usage was called with '/' and the ratio used / 2**30

        Assumptions:
        - Real psutil is never invoked; patch target is data_types.psutil.disk_usage
        """
        mock_usage = MagicMock()
        mock_usage.used = 5 * (2**30)
        with patch(
            "vastai.serverless.server.lib.data_types.psutil.disk_usage",
            return_value=mock_usage,
        ) as mock_du:
            gb = SystemMetrics.get_disk_usage_GB()
        mock_du.assert_called_once_with("/")
        assert gb == 5.0


class TestModelMetrics:
    """ModelMetrics factories, derived properties, and reset/set_errored."""

    def test_empty_initializes_counters_and_collections(self) -> None:
        """
        Verifies ModelMetrics.empty sets workload fields and optional state.

        This test verifies by:
        1. Calling ModelMetrics.empty()
        2. Asserting numeric counters, error_msg, max_throughput, and empty sets/dicts

        Assumptions:
        - Field defaults apply for requests_recieved and requests_working
        """
        mm = ModelMetrics.empty()
        assert mm.workload_pending == 0.0
        assert mm.workload_served == 0.0
        assert mm.workload_received == 0.0
        assert mm.workload_cancelled == 0.0
        assert mm.workload_errored == 0.0
        assert mm.workload_rejected == 0.0
        assert mm.error_msg is None
        assert mm.max_throughput == 0.0
        assert mm.requests_recieved == set()
        assert mm.requests_working == {}

    def test_workload_processing_is_non_negative_difference(self) -> None:
        """
        Verifies workload_processing is max(received - cancelled, 0).

        This test verifies by:
        1. Setting workload_received and workload_cancelled
        2. Asserting property matches formula for normal and over-cancelled cases

        Assumptions:
        - Uses max(..., 0.0) when cancelled exceeds received
        """
        mm = ModelMetrics.empty()
        mm.workload_received = 10.0
        mm.workload_cancelled = 3.0
        assert mm.workload_processing == 7.0
        mm.workload_cancelled = 15.0
        assert mm.workload_processing == 0.0

    def test_wait_time_zero_when_no_active_requests(self) -> None:
        """
        Verifies wait_time is 0.0 when requests_working is empty.

        This test verifies by:
        1. Using ModelMetrics.empty() (empty requests_working)
        2. Asserting wait_time == 0.0

        Assumptions:
        - Early return on len(requests_working) == 0
        """
        mm = ModelMetrics.empty()
        assert mm.wait_time == 0.0

    def test_wait_time_uses_minimum_divisor_when_max_throughput_is_zero(self) -> None:
        """
        Verifies wait_time divides by max(max_throughput, 0.00001) when throughput is zero.

        This test verifies by:
        1. Setting max_throughput to 0.0 with one non-session request workload
        2. Asserting wait_time equals workload / 0.00001

        Assumptions:
        - Avoids division by zero per data_types implementation
        """
        mm = ModelMetrics.empty()
        mm.max_throughput = 0.0
        mm.requests_working[1] = RequestMetrics(
            request_idx=1,
            reqnum=1,
            workload=3.0,
            status="x",
            is_session=False,
        )
        assert mm.wait_time == 3.0 / 0.00001

    def test_wait_time_mixed_session_and_non_session_only_counts_non_session(self) -> None:
        """
        Verifies wait_time numerator includes only non-session workloads when both exist.

        This test verifies by:
        1. Adding one session and one non-session request to requests_working
        2. Asserting wait_time uses only the non-session workload in the sum

        Assumptions:
        - cur_load would include both; wait_time filters by is_session
        """
        mm = ModelMetrics.empty()
        mm.max_throughput = 5.0
        mm.requests_working[1] = RequestMetrics(
            request_idx=1,
            reqnum=1,
            workload=100.0,
            status="x",
            is_session=True,
        )
        mm.requests_working[2] = RequestMetrics(
            request_idx=2,
            reqnum=2,
            workload=10.0,
            status="x",
            is_session=False,
        )
        assert mm.wait_time == 2.0
        assert mm.cur_load == 110.0

    def test_working_request_idxs_empty_when_no_active_requests(self) -> None:
        """
        Verifies working_request_idxs is empty when requests_working is empty.

        This test verifies by:
        1. Using ModelMetrics.empty()
        2. Asserting working_request_idxs == []

        Assumptions:
        - List comprehension over empty dict values yields []
        """
        mm = ModelMetrics.empty()
        assert mm.working_request_idxs == []

    def test_wait_time_averages_non_session_workloads_over_throughput(self) -> None:
        """
        Verifies wait_time sums non-session workloads divided by max_throughput floor.

        This test verifies by:
        1. Adding two RequestMetrics with is_session False and known workloads
        2. Setting max_throughput to 10.0
        3. Asserting wait_time == (w1 + w2) / 10.0

        Assumptions:
        - Session requests are excluded from the numerator
        """
        mm = ModelMetrics.empty()
        mm.max_throughput = 10.0
        mm.requests_working[1] = RequestMetrics(
            request_idx=1,
            reqnum=1,
            workload=4.0,
            status="x",
            is_session=False,
        )
        mm.requests_working[2] = RequestMetrics(
            request_idx=2,
            reqnum=2,
            workload=6.0,
            status="x",
            is_session=False,
        )
        assert mm.wait_time == 1.0

    def test_wait_time_excludes_session_requests_from_numerator(self) -> None:
        """
        Verifies session-flagged requests do not contribute to wait_time sum.

        This test verifies by:
        1. Placing only is_session=True metrics in requests_working
        2. Asserting wait_time is 0.0 despite positive workloads

        Assumptions:
        - Filter is `if not request.is_session`
        """
        mm = ModelMetrics.empty()
        mm.max_throughput = 100.0
        mm.requests_working[1] = RequestMetrics(
            request_idx=1,
            reqnum=1,
            workload=50.0,
            status="x",
            is_session=True,
        )
        assert mm.wait_time == 0.0

    def test_cur_load_sums_request_workloads(self) -> None:
        """
        Verifies cur_load is the sum of workloads in requests_working.

        This test verifies by:
        1. Adding multiple RequestMetrics with distinct workloads
        2. Asserting cur_load equals the sum

        Assumptions:
        - All entries in requests_working contribute regardless of is_session
        """
        mm = ModelMetrics.empty()
        mm.requests_working[0] = RequestMetrics(
            request_idx=0, reqnum=0, workload=2.5, status="a"
        )
        mm.requests_working[1] = RequestMetrics(
            request_idx=1, reqnum=1, workload=3.5, status="b"
        )
        assert mm.cur_load == 6.0

    def test_working_request_idxs_lists_indices(self) -> None:
        """
        Verifies working_request_idxs collects request_idx from values.

        This test verifies by:
        1. Populating requests_working with known request_idx values
        2. Asserting property returns list of those indices (order follows .values())

        Assumptions:
        - Dict iteration order is insertion order (Python 3.7+)
        """
        mm = ModelMetrics.empty()
        mm.requests_working[10] = RequestMetrics(
            request_idx=10, reqnum=1, workload=1.0, status="x"
        )
        mm.requests_working[20] = RequestMetrics(
            request_idx=20, reqnum=2, workload=2.0, status="x"
        )
        assert mm.working_request_idxs == [10, 20]

    def test_reset_zeros_transient_workload_fields_and_updates_last_update(self) -> None:
        """
        Verifies reset clears counters that autoscaler consumes and refreshes last_update.

        This test verifies by:
        1. Setting non-zero workload_served, workload_received, etc.
        2. Patching time.time for deterministic last_update
        3. Calling reset() and asserting zeros and new last_update

        Assumptions:
        - reset does not clear error_msg or long-lived fields beyond listed counters
        """
        mm = ModelMetrics.empty()
        mm.workload_served = 1.0
        mm.workload_received = 2.0
        mm.workload_cancelled = 3.0
        mm.workload_errored = 4.0
        mm.workload_rejected = 5.0
        mm.last_update = 0.0
        with patch(
            "vastai.serverless.server.lib.data_types.time.time", return_value=777.0
        ):
            mm.reset()
        assert mm.workload_served == 0
        assert mm.workload_received == 0
        assert mm.workload_cancelled == 0
        assert mm.workload_errored == 0
        assert mm.workload_rejected == 0
        assert mm.last_update == 777.0

    def test_set_errored_calls_reset_and_sets_error_msg(self) -> None:
        """
        Verifies set_errored resets counters and stores the error string.

        This test verifies by:
        1. Setting non-zero workload_served
        2. Calling set_errored('boom')
        3. Asserting counters cleared and error_msg set

        Assumptions:
        - set_errored delegates to reset() first
        """
        mm = ModelMetrics.empty()
        mm.workload_served = 5.0
        mm.set_errored("boom")
        assert mm.workload_served == 0
        assert mm.error_msg == "boom"


class TestDummyPayloadBehavior:
    """Concrete ApiPayload used by tests implements JSON and workload helpers."""

    def test_for_test_generate_payload_json_and_count_workload(self) -> None:
        """
        Verifies DummyPayload helpers used by benchmarks and forwarding paths.

        This test verifies by:
        1. Calling for_test(), generate_payload_json(), and count_workload()
        2. Asserting JSON shape and workload match the instance

        Assumptions:
        - Mirrors expectations for real server payload implementations
        """
        p = DummyPayload.for_test()
        assert p.generate_payload_json() == {"value": 1}
        assert p.count_workload() == 1.0
        p2 = DummyPayload.from_json_msg({"value": 42})
        assert p2.value == 42
        assert p2.count_workload() == 42.0


class TestBenchmarkResult:
    """BenchmarkResult.is_successful reflects response status."""

    def test_is_successful_true_when_response_status_200(self) -> None:
        """
        Verifies is_successful is True when response exists and status is 200.

        This test verifies by:
        1. Building BenchmarkResult with a mock ClientResponse (status 200)
        2. Asserting is_successful is True

        Assumptions:
        - No real HTTP; MagicMock only
        """
        resp = MagicMock()
        resp.status = 200
        br = BenchmarkResult(request_idx=0, workload=1.0, task=AsyncMock(), response=resp)
        assert br.is_successful is True

    def test_is_successful_false_when_response_none(self) -> None:
        """
        Verifies is_successful is False when response was never set.

        This test verifies by:
        1. Using default response=None
        2. Asserting is_successful is False

        Assumptions:
        - Property checks `response is not None`
        """
        br = BenchmarkResult(request_idx=0, workload=1.0, task=AsyncMock())
        assert br.is_successful is False

    def test_is_successful_false_when_status_not_200(self) -> None:
        """
        Verifies non-200 HTTP status yields is_successful False.

        This test verifies by:
        1. Mocking response.status to 500
        2. Asserting is_successful is False

        Assumptions:
        - Strict equality with 200
        """
        resp = MagicMock()
        resp.status = 500
        br = BenchmarkResult(request_idx=0, workload=1.0, task=AsyncMock(), response=resp)
        assert br.is_successful is False

    def test_is_successful_false_when_response_status_not_equal_200(self) -> None:
        """
        Verifies is_successful is False when response.status is present but not 200.

        This test verifies by:
        1. Using SimpleNamespace(status=None) so the comparison to 200 fails
        2. Asserting is_successful is False

        Assumptions:
        - Property requires both a non-None response and status == 200
        """
        resp = SimpleNamespace(status=None)
        br = BenchmarkResult(request_idx=0, workload=1.0, task=AsyncMock(), response=resp)
        assert br.is_successful is False


class TestSessionAndRequestMetricsDataclasses:
    """Lightweight construction checks for Session and RequestMetrics."""

    def test_session_defaults_and_fields(self) -> None:
        """
        Verifies Session stores core fields and default_factory for requests.

        This test verifies by:
        1. Constructing Session with explicit scalar fields
        2. Asserting requests list default is empty and request counters initialized

        Assumptions:
        - created_at uses time.time at construction; not asserted to a fixed value
        """
        s = Session(
            session_id="s1",
            lifetime=30.0,
            auth_data={},
            expiration=100.0,
            on_close_route="/close",
            on_close_payload={},
        )
        assert s.session_id == "s1"
        assert s.requests == []
        assert s.request_idx == 0
        assert s.session_reqnum == 0

    def test_request_metrics_optional_session_fields(self) -> None:
        """
        Verifies RequestMetrics accepts workload and status with default success False.

        This test verifies by:
        1. Instantiating RequestMetrics with required fields only
        2. Asserting success is False and session fields default as in dataclass

        Assumptions:
        - Matches server usage as optional session tracking
        """
        rm = RequestMetrics(request_idx=3, reqnum=9, workload=2.0, status="WORKING")
        assert rm.success is False
        assert rm.is_session is False
        assert rm.session is None
        assert rm.session_reqnum is None

    def test_request_metrics_with_session_reference(self) -> None:
        """
        Verifies RequestMetrics can attach session and session_reqnum for session flows.

        This test verifies by:
        1. Building a Session and RequestMetrics with is_session True
        2. Asserting session link and session_reqnum are stored

        Assumptions:
        - Server tracks long-lived session requests alongside metrics
        """
        s = Session(
            session_id="sid",
            lifetime=1.0,
            auth_data={},
            expiration=99.0,
            on_close_route="/done",
            on_close_payload={},
        )
        rm = RequestMetrics(
            request_idx=1,
            reqnum=2,
            workload=0.5,
            status="S",
            success=True,
            is_session=True,
            session=s,
            session_reqnum=3,
        )
        assert rm.session is s
        assert rm.session_reqnum == 3
        assert rm.is_session is True


class TestWorkerStatusData:
    """WorkerStatusData is a plain report DTO."""

    def test_worker_status_data_holds_report_fields(self) -> None:
        """
        Verifies WorkerStatusData stores all fields passed to the constructor.

        This test verifies by:
        1. Building an instance with representative values
        2. Asserting each attribute matches

        Assumptions:
        - No validation logic on the dataclass
        """
        ws = WorkerStatusData(
            id=1,
            mtoken="t",
            version="v1",
            loadtime=1.0,
            cur_load=2.0,
            rej_load=3.0,
            new_load=4.0,
            error_msg="",
            max_perf=5.0,
            cur_perf=6.0,
            cur_capacity=7.0,
            max_capacity=8.0,
            num_requests_working=9,
            num_requests_recieved=10,
            additional_disk_usage=11.0,
            working_request_idxs=[1, 2],
            url="http://worker",
        )
        assert ws.id == 1
        assert ws.working_request_idxs == [1, 2]
        assert ws.url == "http://worker"


class TestLogAction:
    """LogAction enum values used for backend log routing."""

    def test_log_action_enum_values(self) -> None:
        """
        Verifies LogAction members have stable int values for API contracts.

        This test verifies by:
        1. Comparing ModelLoaded, ModelError, Info to documented integers
        2. Asserting distinct values

        Assumptions:
        - Values match vastai.serverless.server.lib.data_types definitions
        """
        assert LogAction.ModelLoaded.value == 1
        assert LogAction.ModelError.value == 2
        assert LogAction.Info.value == 3
        assert len({LogAction.ModelLoaded, LogAction.ModelError, LogAction.Info}) == 3
