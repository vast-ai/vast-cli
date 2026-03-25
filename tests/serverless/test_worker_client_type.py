"""Unit tests for vastai.serverless.client.worker.Worker dataclass and from_dict factory."""
import pytest

from vastai.serverless.client.worker import Worker


class TestWorkerFromDict:
    """Verify Worker.from_dict parses dict input into Worker instances correctly."""

    def test_from_dict_with_full_valid_dict_returns_worker_with_all_fields(
        self, full_client_worker_dict: dict
    ) -> None:
        """
        Verifies that from_dict creates a Worker with all fields when given a complete dict.

        This test verifies by:
        1. Using full_client_worker_dict fixture with all expected Worker fields
        2. Calling Worker.from_dict with that dict
        3. Asserting each field matches the input value

        Assumptions:
        - full_client_worker_dict fixture provides valid data for all fields
        """
        worker = Worker.from_dict(full_client_worker_dict)
        assert worker.id == full_client_worker_dict["id"]
        assert worker.status == full_client_worker_dict["status"]
        assert worker.cur_load == full_client_worker_dict["cur_load"]
        assert worker.new_load == full_client_worker_dict["new_load"]
        assert worker.cur_load_rolling_avg == full_client_worker_dict["cur_load_rolling_avg"]
        assert worker.cur_perf == full_client_worker_dict["cur_perf"]
        assert worker.perf == full_client_worker_dict["perf"]
        assert worker.measured_perf == full_client_worker_dict["measured_perf"]
        assert worker.dlperf == full_client_worker_dict["dlperf"]
        assert worker.reliability == full_client_worker_dict["reliability"]
        assert worker.reqs_working == full_client_worker_dict["reqs_working"]
        assert worker.disk_usage == full_client_worker_dict["disk_usage"]
        assert worker.loaded_at == full_client_worker_dict["loaded_at"]
        assert worker.started_at == full_client_worker_dict["started_at"]

    def test_from_dict_with_minimal_dict_uses_defaults_for_missing_fields(
        self, minimal_client_worker_dict: dict
    ) -> None:
        """
        Verifies that from_dict uses default values for missing optional fields.

        This test verifies by:
        1. Using minimal_client_worker_dict with only required id field
        2. Calling Worker.from_dict
        3. Asserting numeric fields default to 0.0 or 0 and status defaults to "UNKNOWN"

        Assumptions:
        - minimal_client_worker_dict provides id only
        """
        worker = Worker.from_dict(minimal_client_worker_dict)
        assert worker.id == minimal_client_worker_dict["id"]
        assert worker.status == "UNKNOWN"
        assert worker.cur_load == 0.0
        assert worker.new_load == 0.0
        assert worker.cur_load_rolling_avg == 0.0
        assert worker.cur_perf == 0.0
        assert worker.perf == 0.0
        assert worker.measured_perf == 0.0
        assert worker.dlperf == 0.0
        assert worker.reliability == 0.0
        assert worker.reqs_working == 0
        assert worker.disk_usage == 0.0
        assert worker.loaded_at == 0.0
        assert worker.started_at == 0.0

    def test_from_dict_with_status_none_uses_unknown(
        self, minimal_client_worker_dict: dict
    ) -> None:
        """
        Verifies that from_dict treats None or falsy status as "UNKNOWN".

        This test verifies by:
        1. Passing a dict with status=None
        2. Asserting worker.status == "UNKNOWN"
        3. Similarly for status=""

        Assumptions:
        - d.get("status") or "UNKNOWN" handles None and empty string
        """
        worker_none = Worker.from_dict({**minimal_client_worker_dict, "status": None})
        assert worker_none.status == "UNKNOWN"

        worker_empty = Worker.from_dict({"id": 2, "status": ""})
        assert worker_empty.status == "UNKNOWN"

    def test_from_dict_with_extra_fields_ignores_them(self) -> None:
        """
        Verifies that from_dict is resilient to extra fields in the input dict.

        This test verifies by:
        1. Passing a dict with extra keys not in the Worker schema
        2. Asserting Worker is created successfully with correct known fields
        3. Confirming no error is raised

        Assumptions:
        - Extra fields are ignored per implementation comment
        """
        data = {
            "id": 10,
            "status": "IDLE",
            "extra_field": "ignored",
            "another_unknown": 999,
        }
        worker = Worker.from_dict(data)
        assert worker.id == 10
        assert worker.status == "IDLE"

    def test_from_dict_with_string_numeric_values_coerces_to_numbers(self) -> None:
        """
        Verifies that from_dict coerces string numeric values to int/float.

        This test verifies by:
        1. Passing a dict with id, cur_load, etc. as strings
        2. Asserting Worker fields are proper int/float types with correct values

        Assumptions:
        - int() and float() handle numeric strings correctly
        """
        data = {
            "id": "100",
            "status": "RUNNING",
            "cur_load": "0.75",
            "reqs_working": "5",
        }
        worker = Worker.from_dict(data)
        assert worker.id == 100
        assert isinstance(worker.id, int)
        assert worker.cur_load == 0.75
        assert isinstance(worker.cur_load, float)
        assert worker.reqs_working == 5
        assert isinstance(worker.reqs_working, int)

    def test_from_dict_with_missing_id_raises(self) -> None:
        """
        Verifies that from_dict raises when id is missing.

        This test verifies by:
        1. Passing a dict without an id key
        2. Asserting TypeError is raised (int(None) raises TypeError)

        Assumptions:
        - id has no default; missing id causes int(d.get("id")) to fail
        """
        with pytest.raises(TypeError, match="int"):
            Worker.from_dict({"status": "RUNNING"})

    def test_from_dict_with_empty_dict_raises(self) -> None:
        """
        Verifies that from_dict raises when given an empty dict.

        This test verifies by:
        1. Passing an empty dict
        2. Asserting TypeError is raised

        Assumptions:
        - id is required and missing in empty dict
        """
        with pytest.raises(TypeError):
            Worker.from_dict({})

    def test_from_dict_with_various_status_values_preserves_status(
        self, minimal_client_worker_dict: dict
    ) -> None:
        """
        Verifies that from_dict preserves non-empty status values.

        This test verifies by:
        1. Passing status values like "RUNNING", "IDLE", "LOADING"
        2. Asserting each is stored correctly

        Assumptions:
        - status is passed through when truthy
        """
        for status in ("RUNNING", "IDLE", "LOADING", "OFFLINE"):
            worker = Worker.from_dict({**minimal_client_worker_dict, "status": status})
            assert worker.status == status

    def test_from_dict_with_id_zero_accepted(self) -> None:
        """
        Verifies that from_dict accepts id=0 as a valid worker id.

        This test verifies by:
        1. Passing a dict with id=0
        2. Asserting Worker is created with id 0

        Assumptions:
        - id 0 is a valid worker identifier
        """
        worker = Worker.from_dict({"id": 0, "status": "IDLE"})
        assert worker.id == 0

    def test_from_dict_with_invalid_id_string_raises(self) -> None:
        """
        Verifies that from_dict raises when id cannot be converted to int.

        This test verifies by:
        1. Passing a dict with id as non-numeric string
        2. Asserting ValueError is raised

        Assumptions:
        - int() raises ValueError for invalid string input
        """
        with pytest.raises((ValueError, TypeError)):
            Worker.from_dict({"id": "not_a_number", "status": "RUNNING"})

    def test_from_dict_with_invalid_float_value_raises(
        self, minimal_client_worker_dict: dict
    ) -> None:
        """
        Verifies that from_dict raises when a numeric field has invalid value.

        This test verifies by:
        1. Passing a dict with cur_load as non-numeric string (id from fixture)
        2. Asserting ValueError is raised

        Assumptions:
        - float() raises ValueError for invalid string input
        """
        with pytest.raises(ValueError):
            Worker.from_dict({**minimal_client_worker_dict, "cur_load": "not_a_number"})

    def test_from_dict_with_negative_numeric_values_accepted(
        self, minimal_client_worker_dict: dict
    ) -> None:
        """
        Verifies that from_dict accepts negative values for numeric fields.

        This test verifies by:
        1. Extending minimal_client_worker_dict with negative cur_load, cur_perf
        2. Asserting Worker is created with those values

        Assumptions:
        - Negative numbers are valid (e.g. for load metrics)
        """
        data = {
            **minimal_client_worker_dict,
            "status": "RUNNING",
            "cur_load": -0.5,
            "cur_perf": -1.0,
        }
        worker = Worker.from_dict(data)
        assert worker.cur_load == -0.5
        assert worker.cur_perf == -1.0

    def test_from_dict_with_integer_id_in_dict(self) -> None:
        """
        Verifies that from_dict handles id passed as integer (not string).

        This test verifies by:
        1. Passing id as int 42
        2. Asserting worker.id == 42 and is int type

        Assumptions:
        - int() accepts int input and returns it unchanged
        """
        worker = Worker.from_dict({"id": 42})
        assert worker.id == 42
        assert isinstance(worker.id, int)
