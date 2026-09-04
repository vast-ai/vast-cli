"""Tests for the client-side Worker view.

Startup progress, ``ensure_ready(wait=...)`` and version pinning all read worker
state through this dataclass, so the parsing and the phase mapping need to be
right — including for older workers that do not report the newer fields.
"""

from vastai.serverless.client.worker import (
    READY_STATES,
    STOPPED_STATES,
    Worker,
)


def _base(**overrides) -> dict:
    d = {
        "id": 123,
        "status": "idle",
        "cur_load": 1.0,
        "new_load": 2.0,
        "cur_load_rolling_avg": 3.0,
        "cur_perf": 4.0,
        "perf": 5.0,
        "measured_perf": 6.0,
        "dlperf": 7.0,
        "reliability": 0.9,
        "reqs_working": 2,
        "disk_usage": 8.0,
        "loaded_at": 100.0,
        "started_at": 50.0,
    }
    d.update(overrides)
    return d


class TestWorkerNewFields:
    def test_defaults_when_worker_omits_new_fields(self) -> None:
        """An older worker reports none of these; parsing must not break."""
        w = Worker.from_dict(_base())
        assert w.deployment_version_id is None
        assert w.loop_lag_max == 0.0
        assert w.warnings == []

    def test_parses_new_fields_when_present(self) -> None:
        w = Worker.from_dict(
            _base(
                deployment_version_id=3215,
                loop_lag_max=12.5,
                warnings=["event_loop_blocked"],
            )
        )
        assert w.deployment_version_id == 3215
        assert w.loop_lag_max == 12.5
        assert w.warnings == ["event_loop_blocked"]

    def test_scalar_warning_is_coerced_to_a_list(self) -> None:
        w = Worker.from_dict(_base(warnings="event_loop_blocked"))
        assert w.warnings == ["event_loop_blocked"]

    def test_version_id_is_coerced_to_int(self) -> None:
        w = Worker.from_dict(_base(deployment_version_id="42"))
        assert w.deployment_version_id == 42


class TestWorkerPhase:
    def test_ready_statuses_are_ready(self) -> None:
        for status in READY_STATES:
            assert Worker.from_dict(_base(status=status)).is_ready
            assert Worker.from_dict(_base(status=status)).phase == "ready"

    def test_startup_statuses_map_to_readable_phases(self) -> None:
        cases = {
            "creating": "renting instance",
            "created": "renting instance",
            "loading": "pulling image / installing",
            "model_loading": "loading model / benchmarking",
        }
        for status, expected in cases.items():
            w = Worker.from_dict(_base(status=status))
            assert not w.is_ready
            assert w.phase == expected

    def test_stopped_statuses_report_themselves(self) -> None:
        for status in ("stopped", "stopping", "exited"):
            w = Worker.from_dict(_base(status=status))
            assert not w.is_ready
            assert w.phase == status
            assert status in STOPPED_STATES

    def test_unknown_status_falls_back_to_the_raw_value(self) -> None:
        w = Worker.from_dict(_base(status="something_new"))
        assert w.phase == "something_new"
        assert not w.is_ready

    def test_missing_status_does_not_crash(self) -> None:
        d = _base()
        del d["status"]
        w = Worker.from_dict(d)
        assert w.status == "UNKNOWN"
        assert not w.is_ready
