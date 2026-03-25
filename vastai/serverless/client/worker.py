from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Optional

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

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Worker":
        # Be resilient to missing / extra fields
        status = d.get("status") or "UNKNOWN"
        try:
            status = status
        except Exception:
            status = "UNKNOWN"

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
        )
