from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Worker statuses that mean "this worker can serve a request right now".
READY_STATES = frozenset({"idle", "ready", "running"})

# Statuses that mean the worker is still coming up, mapped to a short phase
# label. Used to explain *what* a deployment is waiting on during startup.
STARTUP_PHASES: Dict[str, str] = {
    "creating": "renting instance",
    "created": "renting instance",
    "loading": "pulling image / installing",
    "model_loading": "loading model / benchmarking",
    "starting": "starting",
    "rebooting": "rebooting",
}

# Statuses that mean the worker is not going to serve anything without help.
STOPPED_STATES = frozenset({"stopped", "stopping", "exited", "error", "ERROR"})


@dataclass
class Worker:
    id: int
    status: str
    cur_load: float
    new_load: float
    cur_load_rolling_avg: float
    cur_perf: float
    perf: float
    measured_perf: float
    dlperf: float
    reliability: float
    reqs_working: int
    disk_usage: float
    loaded_at: float
    started_at: float
    # Which deployment code version this worker is actually serving. Lets a
    # client tell a freshly-rolled worker from one still running the previous
    # version. None when the endpoint is not a deployment, or when the worker
    # predates this field.
    deployment_version_id: Optional[int] = None
    # Worst event-loop stall the worker observed since its last report, in
    # seconds. A large value means a remote function is blocking the loop.
    loop_lag_max: float = 0.0
    # Self-reported problems, e.g. "event_loop_blocked".
    warnings: List[str] = field(default_factory=list)

    @property
    def is_ready(self) -> bool:
        return self.status in READY_STATES

    @property
    def phase(self) -> str:
        """Human-readable description of what this worker is doing."""
        if self.is_ready:
            return "ready"
        if self.status in STOPPED_STATES:
            return self.status
        return STARTUP_PHASES.get(self.status, self.status)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Worker":
        # Be resilient to missing / extra fields
        status = d.get("status") or "UNKNOWN"

        version = d.get("deployment_version_id")

        warnings = d.get("warnings") or []
        if not isinstance(warnings, list):
            warnings = [str(warnings)]

        return Worker(
            id=int(d.get("id")),
            status=status,
            cur_load=float(d.get("cur_load", 0.0)),
            new_load=float(d.get("new_load", 0.0)),
            cur_load_rolling_avg=float(d.get("cur_load_rolling_avg", 0.0)),
            cur_perf=float(d.get("cur_perf", 0.0)),
            perf=float(d.get("perf", 0.0)),
            measured_perf=float(d.get("measured_perf", 0.0)),
            dlperf=float(d.get("dlperf", 0.0)),
            reliability=float(d.get("reliability", 0.0)),
            reqs_working=int(d.get("reqs_working", 0)),
            disk_usage=float(d.get("disk_usage", 0.0)),
            loaded_at=float(d.get("loaded_at", 0.0)),
            started_at=float(d.get("started_at", 0.0)),
            deployment_version_id=int(version) if version is not None else None,
            loop_lag_max=float(d.get("loop_lag_max", 0.0)),
            warnings=[str(w) for w in warnings],
        )
