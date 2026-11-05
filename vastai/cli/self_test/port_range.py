"""Host direct-port range discovery and mapping probes for self-test."""

from __future__ import annotations

import argparse
import json
import math
import re
import socket
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import requests


HOST_PORT_RANGE_PATH = "/var/lib/vastai_kaalia/host_port_range"
MIN_PORT = 1024
MAX_PORT = 65535
# The self-test reserves progress TCP, fixed UDP, and direct SSH mappings in
# addition to the configured range. NCCL now uses loopback-only dynamic ports,
# so it no longer consumes an externally mapped port.
FIXED_PORT_MAPPING_COUNT = 3
UDP_PROBE_RESPONSE_PREFIX = b"vast-self-test-udp-ok:"
DEFAULT_PROBE_TIMEOUT_SECONDS = 3.0
DEFAULT_SCAN_DEADLINE_SECONDS = 120.0
DEFAULT_RESPONDER_READY_TIMEOUT_SECONDS = 60.0
DEFAULT_SCAN_WORKERS = 64
DEFAULT_PROBE_ATTEMPTS = 3
DEFAULT_PROBE_RETRY_INTERVAL_SECONDS = 0.5
PROGRESS_CONTAINER_PORT = 5000
FIXED_UDP_CONTAINER_PORT = 5001
DIRECT_SSH_MAPPING_COUNT = 1
_PORT_RANGE_RE = re.compile(r"^\s*(\d+)\s*-\s*(\d+)\s*$")
_PORT_KEY_RE = re.compile(r"^(\d+)/(tcp|udp)$", re.IGNORECASE)


@dataclass(frozen=True)
class PortRange:
    start: int
    end: int

    @property
    def count(self) -> int:
        return self.end - self.start + 1

    @property
    def value(self) -> str:
        return f"{self.start}-{self.end}"

    def contains(self, port: int) -> bool:
        return self.start <= port <= self.end


def positive_finite_seconds(value: Any) -> float:
    """Argparse validator for finite, strictly positive timeout values."""
    try:
        seconds = float(value)
    except (TypeError, ValueError) as error:
        raise argparse.ArgumentTypeError("timeout must be a number") from error
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError("timeout must be finite and greater than zero")
    return seconds


def parse_port_range(value: Any) -> PortRange | None:
    """Parse a ``start-end`` value and reject unsafe or reversed ranges."""
    if isinstance(value, PortRange):
        return value
    if isinstance(value, (tuple, list)) and len(value) == 2:
        value = f"{value[0]}-{value[1]}"
    if not isinstance(value, str):
        return None
    match = _PORT_RANGE_RE.fullmatch(value)
    if not match:
        return None
    start, end = (int(part) for part in match.groups())
    if not (MIN_PORT <= start <= end <= MAX_PORT):
        return None
    return PortRange(start, end)


def read_host_port_range(path: str = HOST_PORT_RANGE_PATH) -> PortRange | None:
    """Read the installer/kaalia range without invoking sudo or a shell."""
    try:
        value = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    return parse_port_range(value)


def instance_port_range(instance_info: dict | None) -> PortRange | None:
    """Read the API's direct-port range from a running test instance."""
    if not isinstance(instance_info, dict):
        return None
    start = instance_info.get("direct_port_start")
    end = instance_info.get("direct_port_end")
    if start is None or end is None:
        return None
    return parse_port_range(f"{start}-{end}")


def resolve_port_range(
    instance_info: dict | None = None,
    host_path: str = HOST_PORT_RANGE_PATH,
) -> tuple[PortRange | None, str | None]:
    """Return the configured range and its source."""
    local_range = read_host_port_range(host_path)
    if local_range is not None:
        return local_range, "host_port_range"
    api_range = instance_port_range(instance_info)
    if api_range is not None:
        return api_range, "instance_metadata"
    return None, None


def port_range_docker_args(port_range: PortRange) -> str:
    """Return TCP and UDP Docker mappings for a configured range."""
    value = port_range.value
    return f"-p {value}:{value}/tcp -p {value}:{value}/udp"


def fixed_port_docker_args(port_range: PortRange | None = None) -> str:
    """Return only fixed mappings not already supplied by ``port_range``."""
    args = []
    if port_range is None or not port_range.contains(PROGRESS_CONTAINER_PORT):
        args.append(f"-p {PROGRESS_CONTAINER_PORT}:{PROGRESS_CONTAINER_PORT}")
    if port_range is None or not port_range.contains(FIXED_UDP_CONTAINER_PORT):
        args.append(
            f"-p {FIXED_UDP_CONTAINER_PORT}:{FIXED_UDP_CONTAINER_PORT}/udp"
        )
    return " ".join(args)


def required_direct_port_count(port_range: PortRange) -> int:
    """Count unique direct ports needed by the range, fixed endpoints, and SSH."""
    missing_fixed_mappings = sum(
        not port_range.contains(port)
        for port in (PROGRESS_CONTAINER_PORT, FIXED_UDP_CONTAINER_PORT)
    )
    return port_range.count + DIRECT_SSH_MAPPING_COUNT + missing_fixed_mappings


def _mapped_port_entries(
    instance_info: dict,
    port_range: PortRange,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    seen: set[tuple[int, str, int]] = set()
    for container_key, mappings in (instance_info.get("ports") or {}).items():
        match = _PORT_KEY_RE.fullmatch(str(container_key))
        if not match or not isinstance(mappings, list):
            continue
        container_port, protocol = int(match.group(1)), match.group(2).lower()
        if not port_range.start <= container_port <= port_range.end:
            continue
        for mapping in mappings:
            if not isinstance(mapping, dict):
                continue
            host_port = mapping.get("HostPort")
            if host_port is None:
                continue
            try:
                host_port = int(host_port)
            except (TypeError, ValueError):
                continue
            key = (container_port, protocol, host_port)
            if key in seen:
                continue
            seen.add(key)
            entries.append({
                "container_port": container_port,
                "protocol": protocol,
                "host_port": host_port,
                "host_ip": mapping.get("HostIp"),
            })
    return sorted(entries, key=lambda item: (item["container_port"], item["protocol"], item["host_port"]))


def expected_port_keys(port_range: PortRange) -> set[tuple[int, str]]:
    return {
        (port, protocol)
        for port in range(port_range.start, port_range.end + 1)
        for protocol in ("tcp", "udp")
    }


def probe_port(
    public_ip: str,
    host_port: int,
    protocol: str,
    timeout: float = 3.0,
) -> dict[str, Any]:
    """Probe one externally mapped TCP or UDP port."""
    result: dict[str, Any] = {
        "public_ip": public_ip,
        "host_port": host_port,
        "protocol": protocol,
        "reachable": False,
    }
    try:
        if protocol == "tcp":
            with socket.create_connection((public_ip, host_port), timeout=timeout):
                result["reachable"] = True
        elif protocol == "udp":
            payload = b"vast-self-test-port-scan"
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.settimeout(timeout)
                sock.sendto(payload, (public_ip, host_port))
                response, _address = sock.recvfrom(4096)
            result["reachable"] = response.startswith(UDP_PROBE_RESPONSE_PREFIX)
            if not result["reachable"]:
                result["error"] = "unexpected UDP response"
        else:
            result["error"] = f"unsupported protocol: {protocol}"
    except OSError as error:
        result["error"] = f"{type(error).__name__}: {error}"
    return result


def _entry_key(entry: dict[str, Any]) -> tuple[int, str, int]:
    return entry["container_port"], entry["protocol"], entry["host_port"]


def _probe_entries_concurrently(
    entries: list[dict[str, Any]],
    public_ip: str,
    timeout: float,
    deadline: float,
    max_workers: int,
    probe: Callable[..., dict[str, Any]],
    clock: Callable[[], float],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """Probe entries with bounded concurrency without waiting past ``deadline``."""
    if not entries:
        return [], [], []

    executor = ThreadPoolExecutor(max_workers=max_workers)
    entry_iter = iter(entries)
    in_flight: dict[Any, dict[str, Any]] = {}
    completed: list[dict[str, Any]] = []

    def submit_next() -> bool:
        remaining = deadline - clock()
        if remaining <= 0:
            return False
        try:
            entry = next(entry_iter)
        except StopIteration:
            return False
        future = executor.submit(
            probe,
            public_ip,
            entry["host_port"],
            entry["protocol"],
            min(timeout, remaining),
        )
        in_flight[future] = entry
        return True

    try:
        for _ in range(min(max_workers, len(entries))):
            if not submit_next():
                break

        while in_flight:
            remaining = deadline - clock()
            if remaining <= 0:
                break
            done, _pending = wait(
                tuple(in_flight),
                timeout=remaining,
                return_when=FIRST_COMPLETED,
            )
            if not done:
                break
            for future in done:
                entry = in_flight.pop(future)
                try:
                    probe_result = future.result()
                except Exception as error:
                    probe_result = {
                        "public_ip": public_ip,
                        "host_port": entry["host_port"],
                        "protocol": entry["protocol"],
                        "reachable": False,
                        "error": f"{type(error).__name__}: {error}",
                    }
                if not isinstance(probe_result, dict):
                    probe_result = {
                        "public_ip": public_ip,
                        "host_port": entry["host_port"],
                        "protocol": entry["protocol"],
                        "reachable": False,
                        "error": "probe returned an invalid result",
                    }
                completed.append({
                    **entry,
                    **probe_result,
                    "probe_started": True,
                })
                submit_next()

        in_flight_at_deadline = list(in_flight.values())
        unsubmitted = list(entry_iter)
        for future in in_flight:
            future.cancel()
        return completed, in_flight_at_deadline, unsubmitted
    finally:
        # Running socket calls received a timeout no larger than the remaining
        # total budget. Do not let executor shutdown extend the caller's hard
        # deadline while those bounded calls unwind.
        executor.shutdown(wait=False, cancel_futures=True)


def wait_for_port_responder_readiness(
    instance_info: dict,
    public_ip: str,
    timeout: float = DEFAULT_RESPONDER_READY_TIMEOUT_SECONDS,
    request_timeout: float = DEFAULT_PROBE_TIMEOUT_SECONDS,
    poll_interval: float = 1.0,
    request_get: Callable[..., Any] = requests.get,
    sleeper: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Wait until the image reports its configured-port responders ready."""
    timeout = positive_finite_seconds(timeout)
    request_timeout = positive_finite_seconds(request_timeout)
    poll_interval = positive_finite_seconds(poll_interval)

    mappings = (instance_info.get("ports") or {}).get(
        f"{PROGRESS_CONTAINER_PORT}/tcp",
        [],
    )
    host_port = mappings[0].get("HostPort") if mappings else None
    if not host_port:
        return {
            "ready": False,
            "reason": "Progress port 5000/tcp is not mapped.",
            "attempts": 0,
        }

    url = f"https://{public_ip}:{host_port}/summary.json"
    deadline = clock() + timeout
    attempts = 0
    last_error = None
    last_status_code = None
    last_stage = None

    while True:
        remaining = deadline - clock()
        if remaining <= 0:
            break
        attempts += 1
        try:
            response = request_get(
                url,
                verify=False,
                timeout=min(request_timeout, remaining),
            )
            last_status_code = getattr(response, "status_code", None)
            if last_status_code == 200:
                try:
                    payload = response.json()
                except (AttributeError, TypeError, ValueError):
                    payload = json.loads(getattr(response, "text", "") or "{}")
                last_stage = (
                    (payload.get("stages") or {}).get("port_range_responder")
                    if isinstance(payload, dict)
                    else None
                )
                stage_status = (
                    last_stage.get("status")
                    if isinstance(last_stage, dict)
                    else None
                )
                if stage_status == "passed":
                    return {
                        "ready": True,
                        "url": url,
                        "attempts": attempts,
                        "stage": last_stage,
                    }
                if stage_status in ("failed", "error"):
                    return {
                        "ready": False,
                        "url": url,
                        "attempts": attempts,
                        "stage": last_stage,
                        "reason": (
                            last_stage.get("message")
                            or "The self-test image reported a port responder failure."
                        ),
                    }
            last_error = None
        except (requests.exceptions.RequestException, OSError, ValueError) as error:
            last_error = f"{type(error).__name__}: {error}"

        remaining = deadline - clock()
        if remaining <= 0:
            break
        sleeper(min(poll_interval, remaining))

    return {
        "ready": False,
        "url": url,
        "attempts": attempts,
        "last_status_code": last_status_code,
        "last_error": last_error,
        "last_stage": last_stage,
        "reason": (
            "Timed out waiting for the self-test image to report "
            "configured-port responder readiness."
        ),
    }


def scan_mapped_port_range(
    instance_info: dict,
    public_ip: str,
    port_range: PortRange,
    timeout: float = DEFAULT_PROBE_TIMEOUT_SECONDS,
    total_timeout: float = DEFAULT_SCAN_DEADLINE_SECONDS,
    max_workers: int = DEFAULT_SCAN_WORKERS,
    max_attempts: int = DEFAULT_PROBE_ATTEMPTS,
    retry_interval: float = DEFAULT_PROBE_RETRY_INTERVAL_SECONDS,
    probe=probe_port,
    sleeper: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Probe every mapping concurrently within one hard total deadline."""
    timeout = positive_finite_seconds(timeout)
    total_timeout = positive_finite_seconds(total_timeout)
    retry_interval = positive_finite_seconds(retry_interval)
    if not isinstance(max_workers, int) or max_workers <= 0:
        raise ValueError("max_workers must be a positive integer")
    if not isinstance(max_attempts, int) or max_attempts <= 0:
        raise ValueError("max_attempts must be a positive integer")

    deadline = clock() + total_timeout
    entries = _mapped_port_entries(instance_info, port_range)
    mapped_keys = {(entry["container_port"], entry["protocol"]) for entry in entries}
    missing = [
        {"container_port": port, "protocol": protocol}
        for port, protocol in sorted(expected_port_keys(port_range))
        if (port, protocol) not in mapped_keys
    ]

    results_by_key: dict[tuple[int, str, int], dict[str, Any]] = {}
    pending = list(entries)
    deadline_exceeded = False

    for attempt in range(1, max_attempts + 1):
        if not pending:
            break
        completed, timed_out, unsubmitted = _probe_entries_concurrently(
            pending,
            public_ip,
            timeout,
            deadline,
            max_workers,
            probe,
            clock,
        )
        for result in completed:
            result["attempts"] = attempt
            results_by_key[_entry_key(result)] = result

        if timed_out or unsubmitted:
            deadline_exceeded = True
            for entry in timed_out:
                results_by_key[_entry_key(entry)] = {
                    **entry,
                    "public_ip": public_ip,
                    "reachable": False,
                    "attempts": attempt,
                    "error": "total scan deadline exceeded",
                    "probe_started": True,
                }
            for entry in unsubmitted:
                results_by_key[_entry_key(entry)] = {
                    **entry,
                    "public_ip": public_ip,
                    "reachable": False,
                    "attempts": 0,
                    "error": "not probed before total scan deadline",
                    "probe_started": False,
                }
            break

        pending = [
            entry
            for entry in pending
            if not results_by_key.get(_entry_key(entry), {}).get("reachable")
        ]
        if not pending or attempt == max_attempts:
            break
        remaining = deadline - clock()
        if remaining <= 0:
            deadline_exceeded = True
            break
        sleeper(min(retry_interval, remaining))

    results = [
        results_by_key.get(
            _entry_key(entry),
            {
                **entry,
                "public_ip": public_ip,
                "reachable": False,
                "attempts": 0,
                "error": "probe did not run",
            },
        )
        for entry in entries
    ]
    failed = [result for result in results if not result.get("reachable")]
    unprobed = [
        result
        for result in results
        if result.get("probe_started") is False
    ]
    return {
        "status": "passed" if not missing and not failed else "failed",
        "range": port_range.value,
        "expected_ports": port_range.count,
        "mapped_entries": len(entries),
        "missing_mappings": missing,
        "results": results,
        "failed": failed,
        "deadline_seconds": total_timeout,
        "deadline_exceeded": deadline_exceeded,
        "unprobed_count": len(unprobed),
        "unprobed": unprobed,
        "max_workers": max_workers,
        "max_attempts": max_attempts,
    }
