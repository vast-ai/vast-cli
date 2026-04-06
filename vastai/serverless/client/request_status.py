import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RequestStatus:
    """Observable status tracker for a serverless request lifecycle."""
    status: str = "New"
    create_time: float = field(default_factory=time.time)
    start_time: Optional[float] = None
    complete_time: Optional[float] = None
    req_idx: int = 0
