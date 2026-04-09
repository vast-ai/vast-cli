import dataclasses
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class DeploymentConfig:
    """Configuration for creating or updating a deployment.

    Required: name, image, file_hash, file_size.
    Endpoint scaling params are optional and follow server defaults.
    """

    name: str
    image: str
    file_hash: str
    file_size: int
    env: Optional[str] = None
    tag: Optional[str] = None
    search_params: Optional[str] = None
    storage: Optional[float] = None
    ttl: Optional[float] = None
    version_label: Optional[str] = None
    docker_login_user: Optional[str] = None
    docker_login_pass: Optional[str] = None
    docker_login_repo: Optional[str] = None
    # Endpoint scaling params
    cold_workers: Optional[int] = None
    max_workers: Optional[int] = None
    min_load: Optional[float] = None
    min_cold_load: Optional[float] = None
    target_util: Optional[float] = None
    cold_mult: Optional[float] = None
    max_queue_time: Optional[float] = None
    target_queue_time: Optional[float] = None
    inactivity_timeout: Optional[float] = None
    autoscaler_instance: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in dataclasses.asdict(self).items() if v is not None}


@dataclass
class DeploymentPutResponse:
    """Response from PUT /api/v0/deployments/."""

    success: bool
    action: str  # "created", "soft_update", "autoscale_update", "exists"
    deployment_id: int
    endpoint_id: int
    workergroup_id: Optional[int] = None
    upload_url: Optional[str] = None
    upload_fields: Optional[dict] = None
    evicted_versions: Optional[list] = None

    @classmethod
    def from_dict(cls, d: dict) -> "DeploymentPutResponse":
        return cls(
            success=d["success"],
            action=d["action"],
            deployment_id=d["deployment_id"],
            endpoint_id=d["endpoint_id"],
            workergroup_id=d.get("workergroup_id"),
            upload_url=d.get("upload_url"),
            upload_fields=d.get("upload_fields"),
            evicted_versions=d.get("evicted_versions"),
        )


@dataclass
class DeploymentData:
    """Full deployment entity as returned by GET /api/v0/deployment/{id}/."""

    id: int
    name: str
    tag: str
    endpoint_id: Optional[int]
    endpoint_state: Optional[str]
    worker_count: Optional[int]
    s3_key: Optional[str]
    env: Optional[str]
    image: str
    storage: float
    search_params: Optional[str]
    file_hash: str
    current_version_id: int
    last_healthy_version_id: Optional[int]
    ttl: Optional[float]
    last_client_heartbeat: Optional[float]
    created_at: float
    updated_at: float

    @classmethod
    def from_dict(cls, d: dict) -> "DeploymentData":
        return cls(
            id=d["id"],
            name=d["name"],
            tag=d.get("tag", "default"),
            endpoint_id=d.get("endpoint_id"),
            endpoint_state=d.get("endpoint_state"),
            worker_count=d.get("worker_count"),
            s3_key=d.get("s3_key"),
            env=d.get("env"),
            image=d["image"],
            storage=d.get("storage", 50.0),
            search_params=d.get("search_params"),
            file_hash=d["file_hash"],
            current_version_id=d["current_version_id"],
            last_healthy_version_id=d.get("last_healthy_version_id"),
            ttl=d.get("ttl"),
            last_client_heartbeat=d.get("last_client_heartbeat"),
            created_at=d["created_at"],
            updated_at=d["updated_at"],
        )
