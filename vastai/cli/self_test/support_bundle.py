"""Support bundle helpers for host self-test failures."""

from __future__ import annotations

import json
import io
import os
import re
import subprocess
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vastai.cli.self_test.runtime_diagnostics import redact_secret_text


DEFAULT_BUNDLE_DIR = "/tmp"
MAX_TEXT_BYTES = 256 * 1024
MAX_LOG_BYTES = 256 * 1024
MAX_COMMAND_SECONDS = 10
SENSITIVE_KEY_RE = re.compile(
    r"(api[_-]?key|token|secret|password|passwd|authorization|jupyter_token|instance_api_key|host_port_range)",
    re.IGNORECASE,
)
SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(api[_-]?key|token|secret|password|passwd|authorization|jupyter_token|instance_api_key|host_port_range)"
    r"\b\s*[:=]\s*([^\s,;]+)"
)
DMESG_KEYWORDS_RE = re.compile(r"\b(warn|warning|err|error|fail|fault|crit|panic|oops|bug)\b", re.IGNORECASE)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def support_bundles_enabled() -> bool:
    value = os.environ.get("VAST_SELF_TEST_SUPPORT_BUNDLE", "")
    return value.strip().lower() not in ("0", "false", "no", "off")


def _safe_machine_id(machine_id: object) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(machine_id or "unknown"))[:80]


def _redact_text(text: object, secrets: list[str] | None = None) -> str:
    redacted = redact_secret_text("" if text is None else str(text)) or ""
    for secret in secrets or []:
        if secret:
            redacted = redacted.replace(str(secret), "REDACTED")
    return SENSITIVE_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}=REDACTED", redacted)


def _redact_json(value: Any, secrets: list[str] | None = None) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "REDACTED" if SENSITIVE_KEY_RE.search(str(key)) else _redact_json(item, secrets)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_json(item, secrets) for item in value]
    if isinstance(value, str):
        return _redact_text(value, secrets)
    return value


def _truncate_text(text: str, max_bytes: int) -> str:
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= max_bytes:
        return text
    tail = encoded[-max_bytes:].decode("utf-8", errors="replace")
    return f"[truncated to last {max_bytes} bytes]\n{tail}"


def _decode_bytes(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def _read_file_tail(path: Path, max_bytes: int) -> str:
    size = path.stat().st_size
    with path.open("rb") as handle:
        if size > max_bytes:
            handle.seek(-max_bytes, os.SEEK_END)
        data = handle.read()
    text = _decode_bytes(data)
    if size > max_bytes:
        return f"[truncated from {size} bytes to last {max_bytes} bytes]\n{text}"
    return text


def _run_command(args: list[str], *, timeout: int = MAX_COMMAND_SECONDS) -> tuple[str, str | None]:
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    except FileNotFoundError:
        return "", f"command not found: {args[0]}"
    except subprocess.TimeoutExpired:
        return "", f"command timed out after {timeout}s: {' '.join(args)}"
    output = proc.stdout or ""
    if proc.stderr:
        output = f"{output}\n[stderr]\n{proc.stderr}".strip()
    error = None
    if proc.returncode != 0:
        error = f"command exited {proc.returncode}: {' '.join(args)}"
    return output, error


def _summarize_ss_output(text: str) -> str:
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    summarized = []
    for idx, line in enumerate(lines):
        parts = line.split()
        if idx == 0 and parts:
            summarized.append(" ".join(parts[:5]))
            continue
        if len(parts) >= 5:
            summarized.append(" ".join(parts[:5]))
        else:
            summarized.append(line)
    return "\n".join(summarized)


def _collect_host_artifacts(secrets: list[str] | None = None) -> tuple[dict[str, str], list[dict[str, str]]]:
    files: dict[str, str] = {}
    errors: list[dict[str, str]] = []

    for path in sorted(Path("/var/lib/vastai_kaalia").glob("kaalia.log*")):
        if not path.is_file():
            continue
        archive_name = f"host/kaalia/{path.name}"
        try:
            files[archive_name] = _redact_text(_read_file_tail(path, MAX_LOG_BYTES), secrets)
        except Exception as exc:
            errors.append({"artifact": archive_name, "error": _redact_text(exc, secrets)})

    daemon_json = Path("/etc/docker/daemon.json")
    if daemon_json.exists():
        try:
            files["host/etc-docker-daemon.json"] = _redact_text(_read_file_tail(daemon_json, MAX_TEXT_BYTES), secrets)
        except Exception as exc:
            errors.append({"artifact": "host/etc-docker-daemon.json", "error": _redact_text(exc, secrets)})
    else:
        errors.append({"artifact": "host/etc-docker-daemon.json", "error": "file not found"})

    command_specs = [
        ("host/dmesg-filtered.log", ["dmesg", "-T"], "dmesg"),
        (
            "host/journalctl-docker-vastai_kaalia.log",
            ["journalctl", "-b", "-p", "err..alert", "-u", "docker", "-u", "vastai_kaalia", "--since", "-24h", "--no-pager"],
            "journalctl",
        ),
        ("host/nvidia-smi.txt", ["nvidia-smi"], "nvidia-smi"),
        ("host/nvidia-smi-L.txt", ["nvidia-smi", "-L"], "nvidia-smi -L"),
        ("host/docker-info.txt", ["docker", "info"], "docker info"),
        ("host/ip-addr.txt", ["ip", "addr"], "ip addr"),
        ("host/ss-tlnp-summary.txt", ["ss", "-tlnp"], "ss -tlnp summary"),
    ]

    for archive_name, command, label in command_specs:
        output, error = _run_command(command)
        if archive_name == "host/dmesg-filtered.log":
            output = "\n".join(line for line in output.splitlines() if DMESG_KEYWORDS_RE.search(line))
        elif archive_name == "host/ss-tlnp-summary.txt":
            output = _summarize_ss_output(output)
        files[archive_name] = _truncate_text(_redact_text(output, secrets), MAX_TEXT_BYTES)
        if error:
            errors.append({"artifact": label, "error": _redact_text(error, secrets)})

    mounts = Path("/proc/mounts")
    if mounts.exists():
        try:
            mount_lines = [
                line for line in _read_file_tail(mounts, MAX_TEXT_BYTES).splitlines()
                if "/var/lib/docker" in line
            ]
            files["host/docker-mounts.txt"] = _redact_text("\n".join(mount_lines), secrets)
        except Exception as exc:
            errors.append({"artifact": "host/docker-mounts.txt", "error": _redact_text(exc, secrets)})
    else:
        errors.append({"artifact": "host/docker-mounts.txt", "error": "/proc/mounts not found"})

    return files, errors


def create_support_bundle(
    *,
    machine_id: object,
    output_dir: str | None = None,
    result: dict[str, Any] | None = None,
    cli_output: list[str] | None = None,
    extra_files: dict[str, str] | None = None,
    run_started_at: str | None = None,
    command: list[str] | None = None,
    secrets: list[str] | None = None,
    include_host_logs: bool = True,
) -> dict[str, Any]:
    """Create a redacted host/self-test support tarball and return metadata."""

    created_at = utc_timestamp()
    safe_id = _safe_machine_id(machine_id)
    bundle_dir = Path(output_dir or DEFAULT_BUNDLE_DIR).expanduser()
    bundle_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = bundle_dir / f"vast_selftest_{safe_id}_{created_at}.tar.gz"

    files: dict[str, str] = {}
    errors: list[dict[str, str]] = []
    if cli_output:
        files["self-test-output.log"] = _redact_text("\n".join(cli_output), secrets)
    if result is not None:
        files["self-test-result.json"] = json.dumps(_redact_json(result, secrets), indent=2, sort_keys=True)
    if extra_files:
        for name, content in extra_files.items():
            files[name] = _redact_text(content, secrets)
    if include_host_logs:
        host_files, host_errors = _collect_host_artifacts(secrets)
        files.update(host_files)
        errors.extend(host_errors)

    manifest = {
        "bundle_version": 1,
        "machine_id": str(machine_id),
        "created_at_utc": created_at,
        "run_started_at_utc": run_started_at,
        "command": _redact_json(command or [], secrets),
        "max_text_bytes_per_artifact": MAX_TEXT_BYTES,
        "max_log_bytes_per_artifact": MAX_LOG_BYTES,
        "files": sorted(files.keys()) + ["manifest.json", "collection-errors.json"],
        "collection_errors": errors,
        "note": "Review contents before sharing with Vast support.",
    }
    files["manifest.json"] = json.dumps(manifest, indent=2, sort_keys=True)
    files["collection-errors.json"] = json.dumps(errors, indent=2, sort_keys=True)

    with tarfile.open(bundle_path, "w:gz") as tar:
        for name, content in sorted(files.items()):
            safe_name = re.sub(r"(^/|\\.\\.|\\\\)", "_", name)
            data = _truncate_text(content, MAX_LOG_BYTES).encode("utf-8", errors="replace")
            info = tarfile.TarInfo(safe_name)
            info.size = len(data)
            info.mtime = int(time.time())
            tar.addfile(info, fileobj=io.BytesIO(data))

    size_bytes = bundle_path.stat().st_size
    return {
        "path": str(bundle_path),
        "created_at_utc": created_at,
        "size_bytes": size_bytes,
        "files": sorted(files.keys()),
        "collection_errors": errors,
    }


def format_bundle_summary(bundle: dict[str, Any]) -> list[str]:
    lines = [
        "Self-test diagnostic bundle saved to:",
        f"  {bundle.get('path')}",
        "Bundle contents:",
    ]
    for name in bundle.get("files", []):
        lines.append(f"  - {name}")
    errors = bundle.get("collection_errors") or []
    if errors:
        lines.append("Some host artifacts could not be collected:")
        for item in errors[:10]:
            lines.append(f"  - {item.get('artifact')}: {item.get('error')}")
        if len(errors) > 10:
            lines.append(f"  - ... {len(errors) - 10} more")
    lines.append("Review this tarball before sharing it with support.")
    return lines
