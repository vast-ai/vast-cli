"""Platform-wide GPU market metrics (available to admins and hosts)."""
from typing import Optional

from vastai.api.client import VastClient


def gpu_current(client: VastClient, verified: str = "all", hosting_type: str = "all",
                num_gpus: str = "all") -> dict:
    """Current snapshot of GPU supply/demand, pricing, and perf per GPU type.

    Args:
        client: VastClient instance.
        verified: "yes", "no", or "all".
        hosting_type: "all", "secure_cloud", or "community".
        num_gpus: "all" for cross-bucket population, or a numeric bucket
            ("1", "2", "4", "8", ...) to narrow to one rig configuration.

    Returns:
        Parsed JSON response. Shape: {"success": True, "gpus": [...]} or
        {"success": True, "gpus": [], "needs_machine": True} for hosts with no machines.
    """
    r = client.get("/metrics/gpu/current/", query_args={
        "verified": verified, "hosting_type": hosting_type, "num_gpus": num_gpus,
    })
    r.raise_for_status()
    return r.json()


def gpu_history(client: VastClient, gpu_name: str, verified: str = "all", hosting_type: str = "all",
                num_gpus: str = "all",
                start: Optional[int] = None, end: Optional[int] = None, step: Optional[int] = None) -> dict:
    """Time-series supply/demand, pricing, and stats per GPU type.

    Args:
        client: VastClient instance.
        gpu_name: GPU name, comma-separated list, or "all".
        verified: "yes", "no", or "all".
        hosting_type: "all", "secure_cloud", or "community".
        num_gpus: "all" for cross-bucket population, or a numeric bucket
            ("1", "2", "4", "8", ...) to narrow to one rig configuration.
        start: Start unix timestamp (defaults to end - 1 day server-side).
        end: End unix timestamp (defaults to now server-side).
        step: Step in seconds between data points.

    Returns:
        Parsed JSON response. Shape: {"success": True, "gpus": {gpu_name: {supply_demand, pricing, stats}}}
        or {"success": True, "gpus": {}, "needs_machine": True}.
    """
    params = {
        "gpu_name": gpu_name, "verified": verified,
        "hosting_type": hosting_type, "num_gpus": num_gpus,
    }
    if start is not None:
        params["start"] = str(start)
    if end is not None:
        params["end"] = str(end)
    if step is not None:
        params["step"] = str(step)
    r = client.get("/metrics/gpu/history/", query_args=params)
    r.raise_for_status()
    return r.json()


def gpu_locations(client: VastClient) -> dict:
    """Geographic locations of all GPUs on the platform.

    Returns:
        Parsed JSON response. Shape: {"success": True, "locations": [...]}
        or {"success": True, "locations": [], "needs_machine": True}.
    """
    r = client.get("/metrics/gpu/locations/")
    r.raise_for_status()
    return r.json()
