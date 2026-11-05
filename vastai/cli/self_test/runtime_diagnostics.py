"""Runtime diagnostic helpers for CLI self-test machine flows.

The functions in this module are intentionally pure so the CLI can use them for
raw output shaping without coupling parser/classifier behavior to live Vast API
calls or the existing self-test orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


INSTANCE_CREATE_FAILED = "instance_create_failed"
INSTANCE_CREATE_MISSING_CONTRACT = "instance_create_missing_contract"
INSTANCE_ID_HANDOFF_FAILED = "instance_id_handoff_failed"
INSTANCE_STATUS_ERROR = "instance_status_error"
INSTANCE_STATUS_POLL_FAILED = "instance_status_poll_failed"
INSTANCE_START_TIMEOUT = "instance_start_timeout"
INSTANCE_OFFLINE_BEFORE_TEST = "instance_offline_before_test"
MISSING_PUBLIC_IP = "missing_public_ip"
PROGRESS_PORT_NOT_MAPPED = "progress_port_not_mapped"
PROGRESS_ENDPOINT_UNREACHABLE = "progress_endpoint_unreachable"
PROGRESS_ENDPOINT_LOST = "progress_endpoint_lost"
PROGRESS_EMPTY_TIMEOUT = "progress_empty_timeout"
RUNTIME_TEST_TIMEOUT = "runtime_test_timeout"
LEGACY_PROGRESS_ERROR = "legacy_progress_error"
DOCKER_PULL_FAILED = "docker_pull_failed"
DAEMON_STARTUP_FAILED = "daemon_startup_failed"
NVML_FAILED = "nvml_failed"
RESNET_FAILED = "resnet_failed"
ECC_FAILED = "ecc_failed"
NCCL_FAILED = "nccl_failed"
STRESS_GPU_BURN_FAILED = "stress_gpu_burn_failed"
INTERRUPTED = "interrupted"
CLEANUP_FAILED = "cleanup_failed"
CUDA_ERROR_TOO_MANY_PEERS = "cuda_error_too_many_peers"
CUDA_ERROR_CONTAINED = "cuda_error_contained"
CUDA_OUT_OF_MEMORY = "cuda_out_of_memory"
CUDA_DEVICE_UNAVAILABLE = "cuda_device_unavailable"
CUDA_DRIVER_OR_INITIALIZATION_ERROR = "cuda_driver_or_initialization_error"
CUDA_KERNEL_INCOMPATIBLE = "cuda_kernel_incompatible"
CUDA_DEVICE_EXECUTION_FAILED = "cuda_device_execution_failed"
CUDA_RUNTIME_ERROR = "cuda_runtime_error"
PYTORCH_RUNTIME_ERROR = "pytorch_runtime_error"
RESNET_PROCESS_ERROR = "resnet_process_error"
PROGRESS_CONTAINER_PORT = "5000/tcp"


RUNTIME_FAILURE_CODES = (
    INSTANCE_CREATE_FAILED,
    INSTANCE_CREATE_MISSING_CONTRACT,
    INSTANCE_ID_HANDOFF_FAILED,
    INSTANCE_STATUS_ERROR,
    INSTANCE_STATUS_POLL_FAILED,
    INSTANCE_START_TIMEOUT,
    INSTANCE_OFFLINE_BEFORE_TEST,
    MISSING_PUBLIC_IP,
    PROGRESS_PORT_NOT_MAPPED,
    PROGRESS_ENDPOINT_UNREACHABLE,
    PROGRESS_ENDPOINT_LOST,
    PROGRESS_EMPTY_TIMEOUT,
    RUNTIME_TEST_TIMEOUT,
    LEGACY_PROGRESS_ERROR,
    DOCKER_PULL_FAILED,
    DAEMON_STARTUP_FAILED,
    NVML_FAILED,
    RESNET_FAILED,
    ECC_FAILED,
    NCCL_FAILED,
    STRESS_GPU_BURN_FAILED,
    INTERRUPTED,
    CLEANUP_FAILED,
    CUDA_ERROR_TOO_MANY_PEERS,
    CUDA_ERROR_CONTAINED,
    CUDA_OUT_OF_MEMORY,
    CUDA_DEVICE_UNAVAILABLE,
    CUDA_DRIVER_OR_INITIALIZATION_ERROR,
    CUDA_KERNEL_INCOMPATIBLE,
    CUDA_DEVICE_EXECUTION_FAILED,
    CUDA_RUNTIME_ERROR,
    PYTORCH_RUNTIME_ERROR,
    RESNET_PROCESS_ERROR,
)


@dataclass(frozen=True)
class FailureCatalogEntry:
    code: str
    summary: str
    remediation: str
    suggested_steps: tuple[str, ...]


FAILURE_CATALOG: dict[str, FailureCatalogEntry] = {
    INSTANCE_CREATE_FAILED: FailureCatalogEntry(
        INSTANCE_CREATE_FAILED,
        "Failed to create the runtime test instance.",
        "Check the offer, docker image, and instance creation response.",
        ("Retry with --debugging enabled.", "Inspect the create-instance API error."),
    ),
    INSTANCE_CREATE_MISSING_CONTRACT: FailureCatalogEntry(
        INSTANCE_CREATE_MISSING_CONTRACT,
        "Instance creation did not return a new contract id.",
        "Treat the create response as malformed or incomplete.",
        ("Inspect the raw create-instance response.", "Retry after confirming the offer is still rentable."),
    ),
    INSTANCE_ID_HANDOFF_FAILED: FailureCatalogEntry(
        INSTANCE_ID_HANDOFF_FAILED,
        "The instance was created, but the CLI could not durably publish its ID.",
        "Verify the configured instance-ID handoff path is an absolute writable file path, then retry.",
        (
            "Confirm the CLI reported that cleanup destroyed the exact created instance.",
            "Fix or remove VAST_SELF_TEST_CREATED_INSTANCE_ID_FILE before retrying.",
        ),
    ),
    INSTANCE_STATUS_ERROR: FailureCatalogEntry(
        INSTANCE_STATUS_ERROR,
        "The instance reported an error while starting.",
        "Inspect the instance status message and host/container logs.",
        ("Run show instance for the contract.", "Check docker logs on the host if available."),
    ),
    INSTANCE_STATUS_POLL_FAILED: FailureCatalogEntry(
        INSTANCE_STATUS_POLL_FAILED,
        "Failed to poll instance status.",
        "Confirm API connectivity and retry the status check.",
        ("Retry the CLI command.", "Check network/API errors from the status request."),
    ),
    INSTANCE_START_TIMEOUT: FailureCatalogEntry(
        INSTANCE_START_TIMEOUT,
        "The instance did not reach running state before timeout.",
        "Check host capacity, docker startup, and network configuration.",
        ("Inspect instance status_msg.", "Try the test again after confirming the host is healthy."),
    ),
    INSTANCE_OFFLINE_BEFORE_TEST: FailureCatalogEntry(
        INSTANCE_OFFLINE_BEFORE_TEST,
        "The instance went offline before the runtime test could run.",
        "Investigate host availability and instance lifecycle events.",
        ("Check machine status.", "Review host daemon and container logs."),
    ),
    MISSING_PUBLIC_IP: FailureCatalogEntry(
        MISSING_PUBLIC_IP,
        "The running instance did not expose a public IP address.",
        "Confirm the instance network configuration and public IP assignment.",
        ("Inspect show instance output.", "Retry on a machine with public networking available."),
    ),
    PROGRESS_PORT_NOT_MAPPED: FailureCatalogEntry(
        PROGRESS_PORT_NOT_MAPPED,
        "The runtime progress port was not mapped.",
        "Confirm port 5000/tcp is exposed and direct ports are available.",
        ("Check the available mapped ports in the diagnostic output.", "Verify the machine has enough direct ports."),
    ),
    PROGRESS_ENDPOINT_UNREACHABLE: FailureCatalogEntry(
        PROGRESS_ENDPOINT_UNREACHABLE,
        "The runtime progress endpoint was never reachable.",
        "Check TCP firewall/NAT forwarding, direct port mapping, container startup, and NAT hairpinning.",
        (
            "Confirm the mapped public TCP port forwards to the host LAN IP.",
            "Inspect docker logs to confirm the progress server bound port 5000/tcp.",
            "If testing from the same LAN as the host, retry from an outside network to rule out NAT loopback/hairpinning.",
        ),
    ),
    PROGRESS_ENDPOINT_LOST: FailureCatalogEntry(
        PROGRESS_ENDPOINT_LOST,
        "The runtime progress endpoint became unreachable after connecting.",
        "Look for container crashes, OOM, GPU errors, or host instability.",
        (
            "Inspect docker logs for a crash or missing progress server.",
            "Check dmesg for Xid, GPU reset, OOM, or host stall messages.",
            "Check for network loss between the CLI and host public endpoint.",
        ),
    ),
    PROGRESS_EMPTY_TIMEOUT: FailureCatalogEntry(
        PROGRESS_EMPTY_TIMEOUT,
        "The progress endpoint returned no new output before timeout.",
        "Check whether the runtime script stalled or stopped writing progress.",
        ("Inspect runtime logs.", "Retry with debugging enabled."),
    ),
    RUNTIME_TEST_TIMEOUT: FailureCatalogEntry(
        RUNTIME_TEST_TIMEOUT,
        "The runtime test did not complete before timeout.",
        "Investigate long-running or stalled test stages.",
        ("Check the last reported progress stage.", "Run individual tests to isolate the stall."),
    ),
    LEGACY_PROGRESS_ERROR: FailureCatalogEntry(
        LEGACY_PROGRESS_ERROR,
        "The legacy runtime progress stream reported an unclassified error.",
        "Use the raw error text and active stage to decide the next action.",
        ("Inspect the original ERROR line.", "Retry with debugging enabled if the cause is unclear."),
    ),
    DOCKER_PULL_FAILED: FailureCatalogEntry(
        DOCKER_PULL_FAILED,
        "The test image could not be pulled.",
        "Check image name, tag availability, registry access, and credentials.",
        ("Verify the docker image tag exists.", "Check for registry unauthorized or denied errors."),
    ),
    DAEMON_STARTUP_FAILED: FailureCatalogEntry(
        DAEMON_STARTUP_FAILED,
        "The container or daemon failed during startup.",
        "Inspect docker daemon, OCI runtime, and container startup logs.",
        ("Check docker logs.", "Verify NVIDIA container runtime and host daemon health."),
    ),
    NVML_FAILED: FailureCatalogEntry(
        NVML_FAILED,
        "NVML or nvidia-smi failed during system checks.",
        "Check NVIDIA driver, NVML, and GPU visibility on the host.",
        ("Run nvidia-smi on the host.", "Check driver/library mismatch or GPU reset errors."),
    ),
    RESNET_FAILED: FailureCatalogEntry(
        RESNET_FAILED,
        "The ResNet runtime test failed.",
        "Check PyTorch/CUDA health, available VRAM, and GPU compute stability.",
        ("Look for CUDA OOM, cuDNN, or torch runtime errors.", "Run a smaller isolated torch workload."),
    ),
    ECC_FAILED: FailureCatalogEntry(
        ECC_FAILED,
        "The ECC runtime test failed.",
        "Check GPU ECC counters and hardware health.",
        ("Inspect ECC error counters.", "Review dmesg and nvidia-smi health output."),
    ),
    NCCL_FAILED: FailureCatalogEntry(
        NCCL_FAILED,
        "The NCCL distributed runtime test failed.",
        "Check multi-GPU connectivity, NCCL transport, and network fabric.",
        ("Inspect NCCL error output.", "Verify peer-to-peer and multi-GPU communication."),
    ),
    STRESS_GPU_BURN_FAILED: FailureCatalogEntry(
        STRESS_GPU_BURN_FAILED,
        "The stress-ng or gpu-burn runtime test failed.",
        "Check thermals, power stability, GPU Xid errors, and host stress logs.",
        ("Inspect dmesg for Xid errors.", "Review gpu-burn and stress-ng output."),
    ),
    INTERRUPTED: FailureCatalogEntry(
        INTERRUPTED,
        "The runtime test was interrupted.",
        "Ensure cleanup completed or destroy the test instance manually.",
        ("Check whether the test instance still exists.", "Destroy leaked instances if needed."),
    ),
    CLEANUP_FAILED: FailureCatalogEntry(
        CLEANUP_FAILED,
        "Runtime test cleanup failed.",
        "Destroy the temporary test instance manually to avoid continued billing.",
        ("Run destroy instance for the temporary contract.", "Retry cleanup after checking API connectivity."),
    ),
    CUDA_ERROR_TOO_MANY_PEERS: FailureCatalogEntry(
        CUDA_ERROR_TOO_MANY_PEERS,
        "CUDA peer-mapping resources were exhausted during the all-GPU ResNet test.",
        "Do not verify the advertised all-GPU configuration; split the offer into smaller groups that pass self-test or use an NVSwitch-capable topology.",
        (
            "Inspect the retained traceback and GPU topology.",
            "Rerun self-test after changing the offered GPU grouping or topology.",
        ),
    ),
    CUDA_ERROR_CONTAINED: FailureCatalogEntry(
        CUDA_ERROR_CONTAINED,
        (
            "CUDA reported a contained device exception during the all-GPU ResNet test, "
            "commonly caused by certain invalid peer-memory accesses over NVLink or "
            "certain hardware errors; this is not CUDA out-of-memory or VRAM exhaustion."
        ),
        (
            "Terminate and relaunch the failed process/container, then diagnose the peer "
            "fabric and hardware; do not treat this as tenant VRAM exhaustion."
        ),
        (
            "Terminate and relaunch the failed self-test process/container before retrying.",
            (
                "Inspect nvidia-smi topo -m and run all-pairs P2P access/bandwidth tests "
                "for the advertised GPU group."
            ),
            "Check NVLink/NVSwitch health plus Fabric Manager/NVLSM status and logs.",
            (
                "Review NVIDIA Xid/ECC/driver logs, then repair or isolate the affected "
                "GPU or fabric path."
            ),
        ),
    ),
    CUDA_OUT_OF_MEMORY: FailureCatalogEntry(
        CUDA_OUT_OF_MEMORY,
        "CUDA memory was exhausted during the all-GPU ResNet test.",
        "Stop competing GPU workloads, confirm free VRAM on every GPU, and rerun.",
        (
            "Check active processes and free VRAM on every advertised GPU.",
            "Rerun self-test only after every GPU has sufficient free memory.",
        ),
    ),
    CUDA_DEVICE_UNAVAILABLE: FailureCatalogEntry(
        CUDA_DEVICE_UNAVAILABLE,
        "CUDA reported that one or more GPUs were busy or unavailable.",
        "Make every advertised GPU idle and healthy, then rerun self-test.",
        (
            "Check active GPU processes, compute mode, reset state, and NVIDIA Xid/driver logs.",
            "Confirm every advertised GPU accepts a CUDA workload before retrying.",
        ),
    ),
    CUDA_DRIVER_OR_INITIALIZATION_ERROR: FailureCatalogEntry(
        CUDA_DRIVER_OR_INITIALIZATION_ERROR,
        "NVIDIA driver initialization or CUDA runtime compatibility failed.",
        "Check driver health and image compatibility, repair or upgrade as needed, then rerun.",
        (
            "Confirm nvidia-smi and a small CUDA workload succeed on every GPU.",
            "Use a self-test image compatible with the host driver.",
        ),
    ),
    CUDA_KERNEL_INCOMPATIBLE: FailureCatalogEntry(
        CUDA_KERNEL_INCOMPATIBLE,
        "The selected PyTorch/CUDA kernels do not support this GPU or runtime combination.",
        "Use an image compatible with the GPUs and host driver, then rerun.",
        (
            "Verify the image contains kernels for the advertised GPU architecture.",
            "Confirm the image CUDA runtime is supported by the host driver.",
        ),
    ),
    CUDA_DEVICE_EXECUTION_FAILED: FailureCatalogEntry(
        CUDA_DEVICE_EXECUTION_FAILED,
        "CUDA failed while executing the all-GPU workload.",
        "Review NVIDIA Xid/ECC and driver logs, repair unhealthy GPUs, and rerun.",
        (
            "Check the retained traceback and NVIDIA Xid/ECC logs for the failing device.",
            "Confirm an isolated CUDA workload succeeds on every GPU before retrying.",
        ),
    ),
    CUDA_RUNTIME_ERROR: FailureCatalogEntry(
        CUDA_RUNTIME_ERROR,
        "An unclassified CUDA runtime failure stopped the all-GPU ResNet test.",
        "Review the retained traceback and NVIDIA driver logs before attributing the cause.",
        (
            "Check topology, driver compatibility, GPU health, and competing workloads.",
            "Correct the observed condition, then rerun self-test.",
        ),
    ),
    PYTORCH_RUNTIME_ERROR: FailureCatalogEntry(
        PYTORCH_RUNTIME_ERROR,
        "An unclassified PyTorch runtime failure stopped the all-GPU ResNet test.",
        "Review the retained traceback before deciding whether the image or host is at fault.",
        (
            "Reproduce with a small isolated PyTorch workload on every GPU.",
            "Correct the image or host runtime condition, then rerun self-test.",
        ),
    ),
    RESNET_PROCESS_ERROR: FailureCatalogEntry(
        RESNET_PROCESS_ERROR,
        "The all-GPU ResNet subprocess exited without a more specific diagnosis.",
        "Review the retained process output before attributing the failure, then correct it and rerun.",
        (
            "Inspect the container log for import, image, signal, or process-exit details.",
            "Confirm the image can run its ResNet entry point before retrying.",
        ),
    ),
}


STAGE_SYSTEM_REQUIREMENTS = "system_requirements"
STAGE_RESNET = "resnet"
STAGE_ECC = "ecc"
STAGE_NCCL = "nccl"
STAGE_STRESS_GPU_BURN = "stress_gpu_burn"
STAGE_STARTUP = "startup"


_STAGE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^\s*Running system requirements test\.\.\.\s*$", re.IGNORECASE), STAGE_SYSTEM_REQUIREMENTS),
    (re.compile(r"^\s*Running ResNet(?:50/ResNet18|18)(?: test(?: on all GPUs)?)?\.\.\.\s*$", re.IGNORECASE), STAGE_RESNET),
    (re.compile(r"^\s*Running ECC test(?: on all GPUs)?\.\.\.\s*$", re.IGNORECASE), STAGE_ECC),
    (re.compile(r"^\s*Running NCCL distributed test(?: with \d+ GPUs)?\.\.\.\s*$", re.IGNORECASE), STAGE_NCCL),
    (re.compile(r"^\s*Running stress-ng and gpu-burn(?: tests simultaneously for \d+ seconds)?\.\.\.\s*$", re.IGNORECASE), STAGE_STRESS_GPU_BURN),
)

_SELF_TEST_FAILURE_RE = re.compile(
    r"\bSELF_TEST_FAILURE\[([a-z0-9_]+)\]",
    re.IGNORECASE,
)
_SELF_TEST_RESNET_FAILURE_CODES = (
    CUDA_ERROR_TOO_MANY_PEERS,
    CUDA_ERROR_CONTAINED,
    CUDA_OUT_OF_MEMORY,
    CUDA_DEVICE_UNAVAILABLE,
    CUDA_DRIVER_OR_INITIALIZATION_ERROR,
    CUDA_KERNEL_INCOMPATIBLE,
    CUDA_DEVICE_EXECUTION_FAILED,
    CUDA_RUNTIME_ERROR,
    PYTORCH_RUNTIME_ERROR,
    RESNET_PROCESS_ERROR,
)
_SELF_TEST_FAILURE_STAGES = {
    code: STAGE_RESNET for code in _SELF_TEST_RESNET_FAILURE_CODES
}

_NVML_RE = re.compile(
    r"nvml|nvidia-smi|driver/library version mismatch|failed to initialize.*nvidia",
    re.IGNORECASE,
)
_CUDA_ERROR_CONTAINED_RE = re.compile(
    r"cudaerrorcontained|"
    r"invalid access (?:of|to) peer gpu memory(?: over nvlink)?|"
    r"invalid peer(?:-gpu)?[- ]memory access(?: over nvlink)?",
    re.IGNORECASE,
)
_RESNET_RE = re.compile(
    r"resnet|torch|pytorch|cuda out of memory|outofmemory|cudnn|cublas|cuda error|runtimeerror",
    re.IGNORECASE,
)
_ECC_RE = re.compile(r"\becc\b|volatile double bit|aggregate single bit", re.IGNORECASE)
_NCCL_RE = re.compile(r"\bnccl\b|unhandled system error|connection timed out|allreduce|peer access", re.IGNORECASE)
_STRESS_RE = re.compile(r"stress-ng|gpu-burn|xid|thermal|power limit|burn-in|hardware error", re.IGNORECASE)
_EXPLICIT_STRESS_RE = re.compile(r"stress-ng|gpu-burn|burn-in", re.IGNORECASE)
_EXPLICIT_RESNET_RE = re.compile(
    r"\bresnet(?:18|50)?\b|\btorch\b|\bpytorch\b|\bcudnn\b|\bcublas\b",
    re.IGNORECASE,
)

_DOCKER_PULL_RE = re.compile(
    r"pull|manifest|not found|unauthorized|denied|repository does not exist|no such image|"
    r"pull access denied|requested access to the resource is denied",
    re.IGNORECASE,
)
_STARTUP_RE = re.compile(
    r"daemon|container|startup|start container|failed to start|oci runtime|runc|nvidia-container|"
    r"docker|exited|exec format error|permission denied|mount|entrypoint",
    re.IGNORECASE,
)
_STATUS_ERROR_LINE_RE = re.compile(
    r"^\s*(?:#\d+\s+(?:\d+(?:\.\d+)?\s+)?)?"
    r"(?:(?:errors?|failed|failures?|exceptions?|tracebacks?)(?=[:\s]|$)|"
    r"unauthorized(?=:))",
    re.IGNORECASE | re.MULTILINE,
)
_STATUS_RECOVERABLE_LINE_RE = re.compile(
    r"\bfailed to fetch\b[^\r\n]{0,240}"
    r"\b(?:using cached|ignored|old (?:ones?|indexes?) used)\b",
    re.IGNORECASE,
)
_STATUS_FATAL_MARKER_RE = re.compile(
    r"\b(?:oci runtime|permission denied|pull access denied|"
    r"repository does not exist|no such image|exec format error|failed to start|"
    r"invalid reference format|manifest unknown|no matching manifest)\b|"
    r"\bmanifest\b[^\r\n]{0,160}\bnot found\b|"
    r"\brequested access\b[^\r\n]{0,160}\bdenied\b|"
    r"\brpc error(?=[:\s]|$)|"
    r"\bdocker:\s*error(?=[:\s]|$)|"
    r"(?:docker_build\(\)|docker pull|containerd|dockerd|nvidia-container(?:-cli)?)"
    r"[^\r\n]{0,160}\b(?:errors?|failed|failures?)(?=[:\s]|$)",
    re.IGNORECASE,
)

_API_KEY_RE = re.compile(r"([?&]api_key=)[^&\s]+")


def redact_secret_text(value: object) -> str | None:
    """Return a host-visible string with obvious API-key query values redacted."""
    if value is None:
        return None
    return _API_KEY_RE.sub(r"\1REDACTED", str(value))


def _mapped_port_names(mapped_ports) -> list[str]:
    if not mapped_ports:
        return []
    if isinstance(mapped_ports, dict):
        return sorted(str(key) for key in mapped_ports.keys())
    return sorted(str(port) for port in mapped_ports)


def make_progress_endpoint_diagnostic(
    *,
    url: str | None = None,
    public_ip: str | None = None,
    container_port: str = PROGRESS_CONTAINER_PORT,
    host_port: str | int | None = None,
    timeout_seconds: int | float | None = None,
    attempt_count: int = 0,
    first_connection_established: bool = False,
    last_error_type: str | None = None,
    last_error: object = None,
    last_status_code: int | None = None,
    mapped_ports=None,
) -> dict[str, object]:
    """Shape progress endpoint state for raw output and UI consumption."""
    if url is None and public_ip and host_port:
        url = f"https://{public_ip}:{host_port}/progress"
    diagnostic: dict[str, object] = {
        "url": url,
        "public_ip": public_ip,
        "container_port": container_port,
        "external_port": str(host_port) if host_port is not None else None,
        "host_port": str(host_port) if host_port is not None else None,
        "timeout_seconds": timeout_seconds,
        "attempt_count": int(attempt_count or 0),
        "first_connection_established": bool(first_connection_established),
        "last_error_type": last_error_type,
        "last_error": redact_secret_text(last_error),
        "last_status_code": last_status_code,
        "mapped_ports": _mapped_port_names(mapped_ports),
    }
    return diagnostic


def failure_catalog() -> dict[str, dict[str, object]]:
    """Return a JSON-serializable copy of the runtime failure catalog."""
    return {
        code: {
            "code": entry.code,
            "summary": entry.summary,
            "remediation": entry.remediation,
            "suggested_steps": list(entry.suggested_steps),
        }
        for code, entry in FAILURE_CATALOG.items()
    }


def get_failure_entry(code: str) -> FailureCatalogEntry:
    """Return the catalog entry for a stable runtime failure code."""
    try:
        return FAILURE_CATALOG[code]
    except KeyError as exc:
        raise ValueError(f"Unknown runtime failure code: {code}") from exc


def make_failure(
    code: str,
    *,
    stage: str | None = None,
    summary: str | None = None,
    details: str | None = None,
    error: str | None = None,
    remediation: str | None = None,
    suggested_steps: Iterable[str] | None = None,
    underlying_error: str | None = None,
    progress_endpoint: dict[str, object] | None = None,
) -> dict[str, object]:
    """Build a raw-output-friendly diagnostic dictionary."""
    entry = get_failure_entry(code)
    diagnostic: dict[str, object] = {
        "code": code,
        "stage": stage,
        "summary": summary or entry.summary,
        "remediation": remediation or entry.remediation,
        "suggested_steps": list(suggested_steps) if suggested_steps is not None else list(entry.suggested_steps),
    }
    if details:
        diagnostic["details"] = details
    if error:
        diagnostic["error"] = error
    if underlying_error:
        diagnostic["underlying_error"] = underlying_error
    if progress_endpoint:
        diagnostic["progress_endpoint"] = progress_endpoint
    return diagnostic


def stage_from_progress_line(line: str) -> str | None:
    """Return the legacy runtime stage introduced by a progress line."""
    for pattern, stage in _STAGE_PATTERNS:
        if pattern.search(line):
            return stage
    return None


def classify_legacy_error_line(line: str, stage: str | None = None) -> dict[str, object]:
    """Classify a legacy progress ``ERROR`` line into a runtime diagnostic."""
    stripped = line.strip()
    lowered_stage = stage.lower() if stage else None

    marker_match = _SELF_TEST_FAILURE_RE.search(stripped)
    marker_code = marker_match.group(1).lower() if marker_match else None
    if marker_code in _SELF_TEST_FAILURE_STAGES:
        code = marker_code
        stage = _SELF_TEST_FAILURE_STAGES.get(code, stage)
    else:
        code = LEGACY_PROGRESS_ERROR
        if _CUDA_ERROR_CONTAINED_RE.search(stripped):
            code = CUDA_ERROR_CONTAINED
            stage = STAGE_RESNET
        elif _NVML_RE.search(stripped):
            code = NVML_FAILED
        # Explicit test names beat remembered progress state. The legacy
        # endpoint can replace several stage lines between 20-second polls, so
        # that state may be stale by the time its ERROR line arrives.
        elif _NCCL_RE.search(stripped):
            code = NCCL_FAILED
            stage = STAGE_NCCL
        elif _ECC_RE.search(stripped):
            code = ECC_FAILED
            stage = STAGE_ECC
        elif _EXPLICIT_STRESS_RE.search(stripped):
            code = STRESS_GPU_BURN_FAILED
            stage = STAGE_STRESS_GPU_BURN
        elif _EXPLICIT_RESNET_RE.search(stripped):
            code = RESNET_FAILED
            stage = STAGE_RESNET
        # Use remembered stage for ambiguous text (for example, bare
        # "hardware error") before applying broad compatibility heuristics.
        elif lowered_stage == STAGE_NCCL:
            code = NCCL_FAILED
        elif lowered_stage == STAGE_ECC:
            code = ECC_FAILED
        elif lowered_stage == STAGE_STRESS_GPU_BURN:
            code = STRESS_GPU_BURN_FAILED
        elif lowered_stage == STAGE_RESNET:
            code = RESNET_FAILED
        elif _STRESS_RE.search(stripped):
            code = STRESS_GPU_BURN_FAILED
        elif _RESNET_RE.search(stripped):
            code = RESNET_FAILED

    return make_failure(
        code,
        stage=stage,
        error=stripped,
        details=f"Legacy progress stream reported: {stripped}",
        underlying_error=stripped,
    )


class LegacyProgressParser:
    """Stateful parser for the legacy runtime progress text stream."""

    def __init__(self) -> None:
        self.stage: str | None = None

    def process_line(self, line: str) -> dict[str, object] | None:
        """Update parser state and return a diagnostic for ``ERROR`` lines."""
        stage = stage_from_progress_line(line)
        if stage:
            self.stage = stage
            return None

        if line.strip().upper().startswith("ERROR"):
            return classify_legacy_error_line(line, self.stage)

        return None

    def parse(self, text: str) -> list[dict[str, object]]:
        """Parse progress text and return diagnostics for any ``ERROR`` lines."""
        diagnostics: list[dict[str, object]] = []
        for line in text.splitlines():
            diagnostic = self.process_line(line)
            if diagnostic is not None:
                diagnostics.append(diagnostic)
        return diagnostics


def parse_legacy_progress(text: str) -> list[dict[str, object]]:
    """Parse a legacy progress payload with a fresh parser instance."""
    return LegacyProgressParser().parse(text)


def status_message_is_error(status_msg: str | None) -> bool:
    """Return whether an in-progress instance status contains a fatal marker.

    ``status_msg`` also carries ordinary Docker build output while an image is
    loading. Match explicit error lines and unambiguous fatal phrases instead
    of raw substrings such as ``error``, which also occur in package names such
    as ``liberror-perl``.
    """
    if not status_msg:
        return False

    msg = status_msg.strip()
    if not msg:
        return False

    if _STATUS_FATAL_MARKER_RE.search(msg):
        return True

    return any(
        _STATUS_ERROR_LINE_RE.search(line)
        and not _STATUS_RECOVERABLE_LINE_RE.search(line)
        for line in msg.splitlines()
    )


def classify_status_msg(status_msg: str | None) -> dict[str, object] | None:
    """Classify startup/status messages reported while the instance starts."""
    if not status_msg:
        return None

    msg = status_msg.strip()
    if not msg:
        return None

    code = INSTANCE_STATUS_ERROR
    if _DOCKER_PULL_RE.search(msg):
        code = DOCKER_PULL_FAILED
    elif _STARTUP_RE.search(msg):
        code = DAEMON_STARTUP_FAILED

    return make_failure(
        code,
        stage=STAGE_STARTUP,
        error=msg,
        details=f"Instance status message reported: {msg}",
        underlying_error=msg,
    )


__all__ = [
    "CLEANUP_FAILED",
    "CUDA_DEVICE_EXECUTION_FAILED",
    "CUDA_DEVICE_UNAVAILABLE",
    "CUDA_DRIVER_OR_INITIALIZATION_ERROR",
    "CUDA_ERROR_CONTAINED",
    "CUDA_ERROR_TOO_MANY_PEERS",
    "CUDA_KERNEL_INCOMPATIBLE",
    "CUDA_OUT_OF_MEMORY",
    "CUDA_RUNTIME_ERROR",
    "DAEMON_STARTUP_FAILED",
    "DOCKER_PULL_FAILED",
    "ECC_FAILED",
    "FAILURE_CATALOG",
    "FailureCatalogEntry",
    "INSTANCE_CREATE_FAILED",
    "INSTANCE_CREATE_MISSING_CONTRACT",
    "INSTANCE_ID_HANDOFF_FAILED",
    "INSTANCE_OFFLINE_BEFORE_TEST",
    "INSTANCE_START_TIMEOUT",
    "INSTANCE_STATUS_ERROR",
    "INSTANCE_STATUS_POLL_FAILED",
    "INTERRUPTED",
    "LEGACY_PROGRESS_ERROR",
    "LegacyProgressParser",
    "MISSING_PUBLIC_IP",
    "NCCL_FAILED",
    "NVML_FAILED",
    "PROGRESS_EMPTY_TIMEOUT",
    "PYTORCH_RUNTIME_ERROR",
    "PROGRESS_CONTAINER_PORT",
    "PROGRESS_ENDPOINT_LOST",
    "PROGRESS_ENDPOINT_UNREACHABLE",
    "PROGRESS_PORT_NOT_MAPPED",
    "RESNET_FAILED",
    "RESNET_PROCESS_ERROR",
    "RUNTIME_FAILURE_CODES",
    "RUNTIME_TEST_TIMEOUT",
    "STAGE_ECC",
    "STAGE_NCCL",
    "STAGE_RESNET",
    "STAGE_STARTUP",
    "STAGE_STRESS_GPU_BURN",
    "STAGE_SYSTEM_REQUIREMENTS",
    "STRESS_GPU_BURN_FAILED",
    "classify_legacy_error_line",
    "classify_status_msg",
    "failure_catalog",
    "get_failure_entry",
    "make_failure",
    "make_progress_endpoint_diagnostic",
    "parse_legacy_progress",
    "redact_secret_text",
    "status_message_is_error",
    "stage_from_progress_line",
]
