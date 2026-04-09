# endpoint.py
import asyncio
from dataclasses import dataclass
import os

import time
from .connection import _make_request
from typing import Awaitable, Generic, Optional, TypeVar, Union, TYPE_CHECKING
import logging

from vastai.data.endpoint import EndpointData

logger = logging.getLogger("vastai")

if TYPE_CHECKING:
    from .client import _ServerlessBase, ServerlessRequest
    from .request_status import RequestStatus
    from .session import Session

R = TypeVar("R", bound=Awaitable)


@dataclass
class EndpointDataPartial:
    name: str
    id: int
    api_key: str


class Endpoint_(Generic[R]):
    client: "_ServerlessBase[R]"

    def __repr__(self):
        return f"<Endpoint {self.name} (id={self.data.id})>"

    def __init__(
        self,
        client: "_ServerlessBase[R]",
        name: Optional[str] = None,
        id: Optional[int] = None,
        api_key: Optional[str] = None,
        data: Optional[EndpointData] = None,
        soft_refresh_threshold=3 * 24 * 3600,
        hard_refresh_threshold=6 * 24 * 3600,
    ):
        if client is None:
            raise ValueError("client is required")
        self.client = client
        if isinstance(data, EndpointData):
            self.data: "EndpointData | EndpointDataPartial" = data
        elif isinstance(name, str) and isinstance(id, int) and isinstance(api_key, str):
            self.data: "EndpointData | EndpointDataPartial" = EndpointDataPartial(
                name, id, api_key
            )
        else:
            raise ValueError(
                "Either data or all of name, id, and api_key are required!"
            )
        self.refresh_task: Optional[asyncio.Task[EndpointData]] = None
        self.last_refresh = time.time()
        self.soft_refresh_threshold = soft_refresh_threshold
        self.hard_refresh_threshold = hard_refresh_threshold

    @property
    def name(self):
        return (
            self.data.config.endpoint_name
            if isinstance(self.data, EndpointData)
            else self.data.name
        )

    @property
    def id(self):
        return self.data.id

    @property
    def api_key(self):
        return self.data.api_key

    async def refresh(self, block=False):
        logger.debug("refresh")
        if self.refresh_task is not None:
            if block:
                try:
                    self.data = await self.refresh_task
                finally:
                    self.refresh_task = None
            else:
                try:
                    self.data = self.refresh_task.result()
                    self.refresh_task = None
                except asyncio.InvalidStateError:
                    pass
                except Exception as e:  # refresh task errored, reset it.
                    self.refresh_task = None
                    raise e
        else:
            if block:
                self.data = await self.client.fetch_endpoint(self.data.id)
            else:
                self.refresh_task = asyncio.create_task(
                    self.client.fetch_endpoint(self.data.id)
                )

    def request(
        self,
        route,
        payload,
        serverless_request: Optional[
            Union["ServerlessRequest", "RequestStatus"]
        ] = None,
        cost: int = 100,
        retry: bool = True,
        stream: bool = False,
        timeout: Optional[float] = None,
        session: Optional["Session"] = None,
    ) -> R:
        return self.client.queue_endpoint_request(
            endpoint=self,
            worker_route=route,
            worker_payload=payload,
            serverless_request=serverless_request,
            cost=cost,
            retry=retry,
            stream=stream,
            timeout=timeout,
            session=session,
        )

    def close_session(self, session: "Session"):
        return self.client.end_endpoint_session(session=session)

    async def session_healthcheck(self, session: "Session"):
        result = await self.client.get_endpoint_session(
            endpoint=self, session_id=session.session_id, session_auth=session.auth_data
        )
        return result is not None

    def get_session(self, session_id: int, session_auth: dict, timeout: float = 10):
        return self.client.get_endpoint_session(
            endpoint=self,
            session_id=session_id,
            session_auth=session_auth,
            timeout=timeout,
        )

    def session(
        self,
        cost: int = 100,
        lifetime: float = 60,
        on_close_route: str = None,
        on_close_payload: dict = None,
        timeout: float = None,
    ) -> "Session":
        return self.client.start_endpoint_session(
            endpoint=self,
            cost=cost,
            lifetime=lifetime,
            on_close_route=on_close_route,
            on_close_payload=on_close_payload,
            timeout=timeout,
        )

    def get_workers(self):
        return self.client.get_endpoint_workers(self)

    async def _route(
        self, cost: float = 0.0, req_idx: int = 0, timeout: float = 60.0
    ) -> "RouteResponse":
        VAST_DEBUG_WORKER_URL = os.environ.get("VAST_DEBUG_WORKER_URL")
        if VAST_DEBUG_WORKER_URL:
            return RouteResponse({"request_idx": 1, "url": VAST_DEBUG_WORKER_URL})
        await self.client._get_session()
        if time.time() > self.last_refresh + self.soft_refresh_threshold:
            await self.refresh(
                block=time.time() > self.last_refresh + self.hard_refresh_threshold
            )
        try:
            result = await _make_request(
                client=self.client,
                url=self.client.autoscaler_url,
                route="/route/",
                api_key=self.data.api_key,
                body={
                    "endpoint": self.name,
                    "api_key": self.data.api_key,
                    "cost": cost,
                    "request_idx": req_idx,
                    "replay_timeout": timeout,
                },
                method="POST",
                timeout=10.0,
                retries=1,
                stream=False,
            )
        except Exception as ex:
            raise RuntimeError(f"Failed to route endpoint: {ex}") from ex

        if not result.get("ok"):
            raise RuntimeError(
                f"Failed to route endpoint: HTTP {result.get('status')} - {result.get('text', '')[:512]}"
            )

        return RouteResponse(result.get("json") or {})


class RouteResponse:
    status: str
    body: dict
    request_idx: int

    def __repr__(self):
        return f"<RouteResponse status={self.status}>"

    def __init__(self, body: dict):
        if "request_idx" in body.keys():
            self.request_idx = body.get("request_idx")
        else:
            self.request_idx = 0
        if "url" in body.keys():
            self.status = "READY"
            self.body = body
        else:
            self.status = "WAITING"
            self.body = body

    def get_url(self):
        return self.body.get("url")


# Backward-compatible alias — works for instantiation at runtime.
# Static analysis infers the R parameter from the client argument to __init__.
Endpoint = Endpoint_
