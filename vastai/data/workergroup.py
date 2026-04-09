import dataclasses
from dataclasses import dataclass
from typing import Optional


@dataclass
class WorkergroupConfig:
    """Configuration for creating a workergroup (autoscale job).

    Either endpoint_id or endpoint_name is required (endpoint_id is set
    automatically when using ManagedEndpoint.add_workergroup()).
    Either template_hash or template_id is required (template resolves image, search_query, etc.).
    search_params is always required by the server; defaults to empty dict.
    """
    search_params: str | dict = ""
    endpoint_id: Optional[int] = None
    endpoint_name: Optional[str] = None
    template_hash: Optional[str] = None
    template_id: Optional[int] = None
    launch_args: Optional[str] = None
    min_load: Optional[float] = None
    min_cold_load: Optional[float] = None
    target_util: Optional[float] = None
    cold_mult: Optional[float] = None
    cold_workers: Optional[int] = None
    max_workers: Optional[int] = None
    test_workers: Optional[int] = None
    gpu_ram: Optional[float] = None
    autoscaler_instance: Optional[str] = None
    docker_login_user: Optional[str] = None
    docker_login_pass: Optional[str] = None
    docker_login_repo: Optional[str] = None

    def to_dict(self) -> dict:
        d = {k: v for k, v in dataclasses.asdict(self).items() if v is not None}
        # search_params is always required by the server
        d.setdefault("search_params", self.search_params)
        return d
