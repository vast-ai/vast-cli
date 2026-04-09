import dataclasses
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class InstanceConfig:
    """Configuration for creating an instance from an offer.

    image is required. All other fields are optional.
    """
    image: str
    disk: Optional[float] = None
    label: Optional[str] = None
    onstart: Optional[str] = None
    env: Optional[dict[str, str]] = None
    image_login: Optional[str] = None
    runtype: Optional[str] = None
    args: Optional[list] = None
    args_str: Optional[str] = None
    python_utf8: Optional[bool] = None
    lang_utf8: Optional[bool] = None
    use_jupyter_lab: Optional[bool] = None
    jupyter_dir: Optional[str] = None
    template_hash_id: Optional[str] = None
    template_id: Optional[int] = None
    extra: Optional[str] = None
    target_state: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in dataclasses.asdict(self).items() if v is not None}


@dataclass
class CreateInstanceResponse:
    """Response from PUT /api/v0/asks/{id}/ on success."""
    success: bool
    new_contract: int
    instance_api_key: Optional[str] = None
    ask_id: Optional[int] = None

    @classmethod
    def from_dict(cls, d: dict) -> "CreateInstanceResponse":
        return cls(
            success=d["success"],
            new_contract=d["new_contract"],
            instance_api_key=d.get("instance_api_key"),
            ask_id=d.get("ask_id"),
        )


@dataclass
class Instance:
    """Instance entity as returned by GET /api/v0/instances/."""
    id: int
    machine_id: Optional[int]
    actual_status: Optional[str]
    cur_state: Optional[str]
    next_state: Optional[str]
    intended_status: Optional[str]
    image_uuid: Optional[str]
    image_args: Optional[str]
    image_runtype: Optional[str]
    label: Optional[str]
    num_gpus: Optional[int]
    gpu_name: Optional[str]
    gpu_util: Optional[float]
    gpu_arch: Optional[str]
    gpu_temp: Optional[float]
    cuda_max_good: Optional[str]
    driver_version: Optional[str]
    cpu_cores_effective: Optional[float]
    cpu_util: Optional[float]
    cpu_ram: Optional[int]
    disk_space: Optional[float]
    disk_util: Optional[float]
    disk_usage: Optional[float]
    mem_usage: Optional[float]
    mem_limit: Optional[float]
    vmem_usage: Optional[float]
    inet_up: Optional[float]
    inet_down: Optional[float]
    ssh_host: Optional[str]
    ssh_port: Optional[int]
    ssh_idx: Optional[str]
    public_ipaddr: Optional[str]
    local_ipaddrs: Optional[list]
    direct_port_start: Optional[int]
    direct_port_end: Optional[int]
    status_msg: Optional[str]
    jupyter_token: Optional[str]
    extra_env: Optional[list]
    onstart: Optional[str]
    uptime_mins: Optional[float]
    start_date: Optional[float]
    end_date: Optional[float]
    reliability2: Optional[float]
    dph_total: Optional[float]
    host_id: Optional[int]
    template_id: Optional[int]
    template_hash_id: Optional[str]
    template_name: Optional[str]
    ports: Optional[str]

    @classmethod
    def from_dict(cls, d: dict) -> "Instance":
        """Construct an Instance from an API response dict, ignoring unknown keys."""
        known = {f.name: f for f in dataclasses.fields(cls)}
        kwargs = {}
        for name, field in known.items():
            if name in d:
                kwargs[name] = d[name]
            elif field.default is not dataclasses.MISSING:
                pass
            elif field.default_factory is not dataclasses.MISSING:
                pass
            else:
                kwargs[name] = None
        return cls(**kwargs)
