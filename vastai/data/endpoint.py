import dataclasses
from dataclasses import dataclass
from typing import Optional


@dataclass
class EndpointConfig:
    """Configuration for creating or updating an endpoint job.

    Only endpoint_name is required. All other fields default to None,
    meaning the server will use its own defaults.
    """
    endpoint_name: str
    cold_workers: Optional[int] = None
    max_workers: Optional[int] = None
    min_load: Optional[float] = None
    min_cold_load: Optional[float] = None
    target_util: Optional[float] = None
    cold_mult: Optional[float] = None
    max_queue_time: Optional[float] = None
    target_queue_time: Optional[float] = None
    autoscaler_instance: Optional[str] = None
    endpoint_state: Optional[str] = None
    inactivity_timeout: Optional[float] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in dataclasses.asdict(self).items() if v is not None}


@dataclass
class EndpointData:
    """Full endpoint entity as returned by the API."""
    id: int
    config: EndpointConfig
    api_key: str
    user_id: int
    created_at: float
    auto_delete_in_seconds: Optional[float]
    auto_delete_due_24h: bool

    @classmethod
    def from_dict(cls, d: dict) -> "EndpointData":
        config = EndpointConfig(
            endpoint_name=d["endpoint_name"],
            cold_workers=d.get("cold_workers"),
            max_workers=d.get("max_workers"),
            min_load=d.get("min_load"),
            min_cold_load=d.get("min_cold_load"),
            target_util=d.get("target_util"),
            cold_mult=d.get("cold_mult"),
            max_queue_time=d.get("max_queue_time"),
            target_queue_time=d.get("target_queue_time"),
            endpoint_state=d.get("endpoint_state"),
            inactivity_timeout=d.get("inactivity_timeout"),
        )
        return cls(
            id=d["id"],
            config=config,
            api_key=d["api_key"],
            user_id=d["user_id"],
            created_at=d["created_at"],
            auto_delete_in_seconds=d.get("auto_delete_in_seconds"),
            auto_delete_due_24h=d.get("auto_delete_due_24h", False),
        )
