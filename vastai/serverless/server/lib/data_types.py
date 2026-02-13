import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
from typing import Dict, Any, Union, Tuple, Optional, Set, TypeVar, Generic, Type, Callable, Awaitable
from aiohttp import web, ClientResponse
import inspect
import random
import json
import psutil
import os

"""
type variable representing an incoming payload to pyworker that will used to calculate load and will then
be forwarded to the model
"""

log = logging.getLogger(__file__)


class JsonDataException(Exception):
    def __init__(self, json_msg: Dict[str, Any]):
        self.message = json_msg


ApiPayload_T = TypeVar("ApiPayload_T", bound="ApiPayload")


@dataclass
class ApiPayload(ABC):

    @classmethod
    @abstractmethod
    def for_test(cls: Type[ApiPayload_T]) -> ApiPayload_T:
        """defines how to create a payload for load testing"""
        pass

    @abstractmethod
    def generate_payload_json(self) -> Dict[str, Any]:
        """defines how to convert an ApiPayload to JSON that will be sent to model API"""
        pass

    @abstractmethod
    def count_workload(self) -> float:
        """defines how to calculate workload for a payload"""
        pass

    @classmethod
    @abstractmethod
    def from_json_msg(
        cls: Type[ApiPayload_T], json_msg: Dict[str, Any]
    ) -> ApiPayload_T:
        """
        defines how to create an API payload from a JSON message,
        it should throw an JsonDataException if there are issues with some fields
        or they are missing in the format of
        {
            "field": "error msg"
        }
        """
        pass


@dataclass
class AuthData:
    """data used to authenticate requester"""

    cost: str
    endpoint: str
    reqnum: int
    request_idx: int
    signature: str
    url: str

    @classmethod
    def from_json_msg(cls, json_msg: Dict[str, Any]):
        errors = {}
        for param in inspect.signature(cls).parameters:
            if param not in json_msg:
                errors[param] = "missing parameter"
        if errors:
            raise JsonDataException(errors)
        return cls(
            **{
                k: v
                for k, v in json_msg.items()
                if k in inspect.signature(cls).parameters
            }
        )


@dataclass
class EndpointHandler(ABC, Generic[ApiPayload_T]):
    """
    Each model endpoint will have a handler responsible for counting workload from the incoming ApiPayload
    and converting it to json to be forwarded to model API
    """

    has_benchmark: bool = True
    concurrency: int = 10
    benchmark_runs: int = 8
    allow_parallel_requests: bool = False
    max_queue_time: float = 30.0

    @property
    @abstractmethod
    def endpoint(self) -> str:
        """the endpoint on the model API"""
        pass

    @property
    @abstractmethod
    def healthcheck_endpoint(self) -> Optional[str]:
        """the endpoint on the model API that is used for healthchecks"""
        pass

    @classmethod
    @abstractmethod
    def payload_cls(cls) -> Type[ApiPayload_T]:
        """ApiPayload class"""
        pass

    @abstractmethod
    def make_benchmark_payload(self) -> ApiPayload_T:
        """defines how to create an ApiPayload for benchmarking."""
        pass

    @abstractmethod
    async def generate_client_response(
        self, client_request: web.Request, model_response: ClientResponse
    ) -> Union[web.Response, web.StreamResponse]:
        """
        defines how to convert a model API response to a response to PyWorker client
        """
        pass

    @classmethod
    def get_data_from_request(
        cls, req_data: Dict[str, Any]
    ) -> Tuple[AuthData, ApiPayload_T]:
        errors = {}
        auth_data: Optional[AuthData] = None
        payload: Optional[ApiPayload_T] = None
        try:
            if "auth_data" in req_data:
                auth_data = AuthData.from_json_msg(req_data["auth_data"])
            else:
                errors["auth_data"] = "field missing"
        except JsonDataException as e:
            errors["auth_data"] = e.message
        try:
            if "payload" in req_data:
                payload_cls = cls.payload_cls()
                payload = payload_cls.from_json_msg(req_data["payload"])
            else:
                errors["payload"] = "field missing"
        except JsonDataException as e:
            errors["payload"] = e.message
        if errors:
            raise JsonDataException(errors)
        if auth_data and payload:
            return (auth_data, payload)
        else:
            raise Exception("error deserializing request data")


@dataclass
class SystemMetrics:
    """General system metrics"""

    model_loading_start: float
    model_loading_time: Union[float, None]
    last_disk_usage: float
    additional_disk_usage: float
    model_is_loaded: bool

    @staticmethod
    def get_disk_usage_GB():
        return psutil.disk_usage("/").used / (2**30)  # want units of GB

    @classmethod
    def empty(cls):
        return cls(
            model_loading_start=time.time(),
            model_loading_time=None,
            last_disk_usage=SystemMetrics.get_disk_usage_GB(),
            additional_disk_usage=0.0,
            model_is_loaded=False,
        )

    def update_disk_usage(self):
        disk_usage = SystemMetrics.get_disk_usage_GB()
        self.additional_disk_usage = disk_usage - self.last_disk_usage
        self.last_disk_usage = disk_usage

    def reset(self, expected: float | None) -> None:
        # autoscaler expects model_loading_time to be populated only once, when the instance has
        # finished benchmarking and is ready to receive requests. This applies to restarted instances
        # as well: they should send model_loading_time once when they are done loading
        if self.model_loading_time == expected:
            self.model_loading_time = None


@dataclass
class RequestMetrics:
    """Tracks metrics for an active request."""
    request_idx: int
    reqnum: int
    workload: float
    status: str
    success: bool = False

@dataclass
class BenchmarkResult:
    request_idx: int
    workload: float
    task: Awaitable[ClientResponse]
    response: Optional[ClientResponse] = None

    @property
    def is_successful(self) -> bool:
        return self.response is not None and self.response.status == 200

@dataclass
class ModelMetrics:
    """Model specific metrics"""

    # these are reset after being sent to autoscaler
    workload_served: float
    workload_received: float
    workload_cancelled: float
    workload_errored: float
    workload_rejected: float
    # these are not
    workload_pending: float
    error_msg: Optional[str]
    max_throughput: float
    requests_recieved: Set[int] = field(default_factory=set)
    requests_working: dict[int, RequestMetrics] = field(default_factory=dict)
    requests_deleting: list[RequestMetrics] = field(default_factory=list)
    last_update: float = field(default_factory=time.time)

    @classmethod
    def empty(cls):
        return cls(
            workload_pending=0.0,
            workload_served=0.0,
            workload_cancelled=0.0,
            workload_errored=0.0,
            workload_rejected=0.0,
            workload_received=0.0,
            error_msg=None,
            max_throughput=0.0,
        )
    
    @property
    def workload_processing(self) -> float:
        return max(self.workload_received - self.workload_cancelled, 0.0)

    @property
    def wait_time(self) -> float:
        if (len(self.requests_working) == 0):
            return 0.0
        return sum([request.workload for request in self.requests_working.values()]) / max(self.max_throughput, 0.00001)
    
    @property
    def cur_load(self) -> float:
        return sum([request.workload for request in self.requests_working.values()])

    @property
    def working_request_idxs(self) -> list[int]:
        return [req.request_idx for req in self.requests_working.values()]

    def set_errored(self, error_msg):
        self.reset()
        self.error_msg = error_msg

    def reset(self):
        self.workload_served = 0
        self.workload_received = 0
        self.workload_cancelled = 0
        self.workload_errored = 0
        self.workload_rejected = 0
        self.last_update = time.time()


@dataclass
class WorkerStatusData:
    """Data that is reported to autoscaler's on_status endpoint"""

    id: int
    mtoken: str
    version: str
    loadtime: float
    cur_load: float
    rej_load: float
    new_load: float
    error_msg: str
    max_perf: float
    cur_perf: float
    cur_capacity: float
    max_capacity: float
    num_requests_working: int
    num_requests_recieved: int
    additional_disk_usage: float
    working_request_idxs: list[int]
    url: str


class LogAction(Enum):
    """
    These actions tell the backend what a log value means, for example:
    actions [
        # this marks the model server as loaded
        (LogAction.ModelLoaded, "Starting server"),
        # these mark the model server as errored
        (LogAction.ModelError, "Exception loading model"),
        (LogAction.ModelError, "Server failed to bind to port"),
        # this tells the backend to print any logs containing the string into its own logs
        # which are visible in the vast console instance logs
        (LogAction.Info, "Starting model download"),
    ]
    """

    ModelLoaded = 1
    ModelError = 2
    Info = 3