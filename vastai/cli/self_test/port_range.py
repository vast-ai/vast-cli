"""Host direct-port range discovery and mapping probes for self-test."""

from __future__ import annotations

import re
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any


HOST_PORT_RANGE_PATH = "/var/lib/vastai_kaalia/host_port_range"
MIN_PORT = 1024
MAX_PORT = 65535
# The self-test reserves these fixed mappings in addition to the configured
# range. The host offer's direct_port_count is the source of truth for the
# capacity check; it is not a fixed platform-wide limit.
FIXED_PORT_MAPPING_COUNT = 4
UDP_PROBE_RESPONSE_PREFIX = b"vast-self-test-udp-ok:"
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


def scan_mapped_port_range(
    instance_info: dict,
    public_ip: str,
    port_range: PortRange,
    timeout: float = 3.0,
    probe=probe_port,
) -> dict[str, Any]:
    """Probe every mapped TCP/UDP entry and report missing mappings too."""
    entries = _mapped_port_entries(instance_info, port_range)
    mapped_keys = {(entry["container_port"], entry["protocol"]) for entry in entries}
    missing = [
        {"container_port": port, "protocol": protocol}
        for port, protocol in sorted(expected_port_keys(port_range))
        if (port, protocol) not in mapped_keys
    ]
    results = [
        {
            **entry,
            **probe(public_ip, entry["host_port"], entry["protocol"], timeout),
        }
        for entry in entries
    ]
    failed = [result for result in results if not result.get("reachable")]
    return {
        "status": "passed" if not missing and not failed else "failed",
        "range": port_range.value,
        "expected_ports": port_range.count,
        "mapped_entries": len(entries),
        "missing_mappings": missing,
        "results": results,
        "failed": failed,
    }
