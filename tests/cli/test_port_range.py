import argparse
import math
import threading
import time
from types import SimpleNamespace

import pytest
import requests

from vastai.cli.self_test.port_range import (
    DEFAULT_SCAN_DEADLINE_SECONDS,
    DEFAULT_SCAN_WORKERS,
    PortRange,
    fixed_port_docker_args,
    parse_port_range,
    port_range_docker_args,
    positive_finite_seconds,
    read_host_port_range,
    required_direct_port_count,
    resolve_port_range,
    scan_mapped_port_range,
    wait_for_port_responder_readiness,
)


def test_parse_port_range_accepts_whitespace_and_rejects_invalid_values():
    assert parse_port_range(" 40000 - 40002\n") == PortRange(40000, 40002)
    assert parse_port_range("1024-65535") == PortRange(1024, 65535)
    assert parse_port_range("1023-40000") is None
    assert parse_port_range("40000-65536") is None
    assert parse_port_range("40002-40000") is None
    assert parse_port_range("40000") is None


def test_read_and_resolve_port_range(tmp_path):
    path = tmp_path / "host_port_range"
    path.write_text("41000-41003\n", encoding="utf-8")

    assert read_host_port_range(str(path)) == PortRange(41000, 41003)
    port_range, source = resolve_port_range(host_path=str(path))
    assert port_range == PortRange(41000, 41003)
    assert source == "host_port_range"


def test_resolve_port_range_falls_back_to_instance_metadata(tmp_path):
    port_range, source = resolve_port_range(
        {"direct_port_start": 42000, "direct_port_end": 42002},
        host_path=str(tmp_path / "missing"),
    )
    assert port_range == PortRange(42000, 42002)
    assert source == "instance_metadata"


def test_docker_args_request_tcp_and_udp_range():
    assert port_range_docker_args(PortRange(40000, 40002)) == (
        "-p 40000-40002:40000-40002/tcp "
        "-p 40000-40002:40000-40002/udp"
    )


def test_fixed_docker_args_and_capacity_dedupe_range_overlaps():
    port_range = PortRange(5000, 5001)

    assert fixed_port_docker_args(port_range) == ""
    assert required_direct_port_count(port_range) == 3
    assert fixed_port_docker_args(PortRange(5000, 5000)) == "-p 5001:5001/udp"
    assert required_direct_port_count(PortRange(5000, 5000)) == 3
    assert fixed_port_docker_args(PortRange(5001, 5001)) == "-p 5000:5000"
    assert required_direct_port_count(PortRange(5001, 5001)) == 3
    assert fixed_port_docker_args(PortRange(40000, 40002)) == (
        "-p 5000:5000 -p 5001:5001/udp"
    )
    assert required_direct_port_count(PortRange(40000, 40002)) == 6


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf", "-inf", "nope"])
def test_timeout_validator_rejects_non_positive_or_non_finite_values(value):
    with pytest.raises(argparse.ArgumentTypeError):
        positive_finite_seconds(value)


def test_timeout_validator_accepts_positive_finite_value():
    assert positive_finite_seconds("0.25") == 0.25


def test_scan_reports_missing_and_unreachable_mappings():
    instance = {
        "ports": {
            "40000/tcp": [{"HostPort": "50000"}, {"HostPort": "50000"}],
            "40000/udp": [{"HostPort": "50001"}],
            "40001/tcp": [{"HostPort": "50002"}],
        }
    }

    def fake_probe(public_ip, host_port, protocol, timeout):
        return {
            "public_ip": public_ip,
            "host_port": host_port,
            "protocol": protocol,
            "reachable": host_port != 50002,
            "error": "connection refused" if host_port == 50002 else None,
        }

    result = scan_mapped_port_range(
        instance,
        "203.0.113.10",
        PortRange(40000, 40001),
        probe=fake_probe,
        max_attempts=1,
    )

    assert result["status"] == "failed"
    assert result["mapped_entries"] == 3
    assert result["missing_mappings"] == [{"container_port": 40001, "protocol": "udp"}]
    assert result["failed"][0]["host_port"] == 50002


def _mapped_instance(start, end):
    ports = {}
    host_port = 50000
    for container_port in range(start, end + 1):
        for protocol in ("tcp", "udp"):
            ports[f"{container_port}/{protocol}"] = [
                {"HostPort": str(host_port)}
            ]
            host_port += 1
    return {"ports": ports}


def test_scan_retries_transient_probe_failures():
    attempts = {}

    def flaky_probe(public_ip, host_port, protocol, timeout):
        key = (host_port, protocol)
        attempts[key] = attempts.get(key, 0) + 1
        return {
            "public_ip": public_ip,
            "host_port": host_port,
            "protocol": protocol,
            "reachable": attempts[key] >= 2,
            "error": None if attempts[key] >= 2 else "not ready",
        }

    result = scan_mapped_port_range(
        _mapped_instance(40000, 40001),
        "203.0.113.10",
        PortRange(40000, 40001),
        probe=flaky_probe,
        max_attempts=2,
        retry_interval=0.001,
    )

    assert result["status"] == "passed"
    assert {item["attempts"] for item in result["results"]} == {2}


def test_scan_preserves_full_hundred_port_range():
    result = scan_mapped_port_range(
        _mapped_instance(40000, 40099),
        "203.0.113.10",
        PortRange(40000, 40099),
        probe=lambda public_ip, host_port, protocol, timeout: {
            "public_ip": public_ip,
            "host_port": host_port,
            "protocol": protocol,
            "reachable": True,
        },
        max_workers=16,
        max_attempts=1,
    )

    assert result["status"] == "passed"
    assert result["expected_ports"] == 100
    assert result["mapped_entries"] == 200
    assert result["unprobed_count"] == 0


def test_large_full_range_fits_default_worker_deadline_model():
    start = 40000
    count = 16_383
    end = start + count - 1
    result = scan_mapped_port_range(
        _mapped_instance(start, end),
        "203.0.113.10",
        PortRange(start, end),
        probe=lambda public_ip, host_port, protocol, timeout: {
            "public_ip": public_ip,
            "host_port": host_port,
            "protocol": protocol,
            "reachable": True,
        },
        max_attempts=1,
    )
    modeled_seconds_at_50ms = (
        math.ceil(result["mapped_entries"] / DEFAULT_SCAN_WORKERS) * 0.05
    )

    assert result["status"] == "passed"
    assert result["mapped_entries"] == count * 2
    assert result["unprobed_count"] == 0
    assert modeled_seconds_at_50ms < DEFAULT_SCAN_DEADLINE_SECONDS


def test_scan_uses_bounded_concurrency():
    lock = threading.Lock()
    active = 0
    max_active = 0

    def slow_probe(public_ip, host_port, protocol, timeout):
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.04)
        with lock:
            active -= 1
        return {
            "public_ip": public_ip,
            "host_port": host_port,
            "protocol": protocol,
            "reachable": True,
        }

    result = scan_mapped_port_range(
        _mapped_instance(40000, 40003),
        "203.0.113.10",
        PortRange(40000, 40003),
        probe=slow_probe,
        max_workers=4,
        max_attempts=1,
        total_timeout=2,
    )

    assert result["status"] == "passed"
    assert max_active == 4


def test_scan_deadline_reports_entries_that_never_started():
    release_probes = threading.Event()
    probes_started = threading.Event()
    probe_finished = threading.Event()
    started_count = 0
    started_lock = threading.Lock()

    def blocking_probe(public_ip, host_port, protocol, timeout):
        nonlocal started_count
        with started_lock:
            started_count += 1
            if started_count == 2:
                probes_started.set()
        release_probes.wait(timeout=2)
        probe_finished.set()
        return {
            "public_ip": public_ip,
            "host_port": host_port,
            "protocol": protocol,
            "reachable": False,
        }

    clock_calls = 0

    def controlled_clock():
        nonlocal clock_calls
        clock_calls += 1
        if clock_calls <= 3:
            return 0.0
        assert probes_started.wait(timeout=1)
        return 1.0

    try:
        result = scan_mapped_port_range(
            _mapped_instance(40000, 40009),
            "203.0.113.10",
            PortRange(40000, 40009),
            probe=blocking_probe,
            max_workers=2,
            max_attempts=1,
            total_timeout=0.05,
            clock=controlled_clock,
        )

        assert result["status"] == "failed"
        assert result["deadline_exceeded"] is True
        assert result["unprobed_count"] == 18
        assert all(item["probe_started"] is False for item in result["unprobed"])
        assert probe_finished.is_set() is False
    finally:
        release_probes.set()


def test_readiness_retries_until_summary_stage_passes():
    responses = [
        requests.exceptions.ConnectTimeout("starting"),
        SimpleNamespace(status_code=503, text="", json=lambda: {}),
        SimpleNamespace(
            status_code=200,
            text="",
            json=lambda: {
                "stages": {
                    "port_range_responder": {
                        "status": "passed",
                        "message": "ready",
                    }
                }
            },
        ),
    ]

    def request_get(*_args, **_kwargs):
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    result = wait_for_port_responder_readiness(
        {"ports": {"5000/tcp": [{"HostPort": "45000"}]}},
        "203.0.113.10",
        timeout=1,
        poll_interval=0.001,
        request_get=request_get,
        sleeper=lambda _seconds: None,
    )

    assert result["ready"] is True
    assert result["attempts"] == 3
    assert result["stage"]["status"] == "passed"


def test_readiness_returns_image_reported_failure_without_scanning():
    result = wait_for_port_responder_readiness(
        {"ports": {"5000/tcp": [{"HostPort": "45000"}]}},
        "203.0.113.10",
        timeout=1,
        request_get=lambda *_args, **_kwargs: SimpleNamespace(
            status_code=200,
            text="",
            json=lambda: {
                "stages": {
                    "port_range_responder": {
                        "status": "failed",
                        "message": "bind failed",
                    }
                }
            },
        ),
        sleeper=lambda _seconds: None,
    )

    assert result["ready"] is False
    assert result["reason"] == "bind failed"
    assert result["attempts"] == 1
