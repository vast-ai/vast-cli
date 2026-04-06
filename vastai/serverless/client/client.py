# client.py
from .connection import _make_request
from .endpoint import Endpoint, Endpoint_
from .managed import ManagedEndpoint, ManagedDeployment
from .worker import Worker
from .session import Session
from .request_status import RequestStatus
from vastai.data.endpoint import EndpointConfig, EndpointData
from vastai.data.deployment import (
    DeploymentConfig,
    DeploymentData,
    DeploymentPutResponse,
)
from vastai.data.workergroup import WorkergroupConfig
import asyncio
import aiohttp
import ssl
import os
import tempfile
import logging
import random
import time
import collections
from abc import abstractmethod
from typing import (
    Any,
    Awaitable,
    Callable,
    Coroutine,
    Deque,
    Dict,
    Generic,
    Optional,
    TypeVar,
    Union,
    List,
)

logger = logging.getLogger("vastai")

R = TypeVar("R", bound=Awaitable)


class ServerlessRequest(asyncio.Future):
    """A fire-and-observe request to a Serverless endpoint.

    Composes a RequestStatus tracker for status/timestamp tracking.
    Properties delegate to the tracker for backward compatibility.
    """

    def __init__(self, tracker: Optional[RequestStatus] = None):
        super().__init__()
        self.tracker = tracker if tracker is not None else RequestStatus()

    @property
    def status(self):
        return self.tracker.status

    @status.setter
    def status(self, value):
        self.tracker.status = value

    @property
    def create_time(self):
        return self.tracker.create_time

    @create_time.setter
    def create_time(self, value):
        self.tracker.create_time = value

    @property
    def start_time(self):
        return self.tracker.start_time

    @start_time.setter
    def start_time(self, value):
        self.tracker.start_time = value

    @property
    def complete_time(self):
        return self.tracker.complete_time

    @complete_time.setter
    def complete_time(self, value):
        self.tracker.complete_time = value

    @property
    def req_idx(self):
        return self.tracker.req_idx

    @req_idx.setter
    def req_idx(self, value):
        self.tracker.req_idx = value

    def then(self, callback) -> "ServerlessRequest":
        def _done(fut):
            if fut.exception() is not None:
                print(fut.exception())
                return
            callback(fut.result())

        self.add_done_callback(_done)
        return self


class _ServerlessBase(Generic[R]):
    SSL_CERT_URL = "https://console.vast.ai/static/jvastai_root.cer"
    VAST_WEB_URL = "https://console.vast.ai"
    VAST_SERVERLESS_URL = "https://run.vast.ai"

    def __init__(
        self,
        api_key: Optional[str] = os.environ.get("VAST_API_KEY", None),
        *,
        debug: bool = False,
        instance: str = "prod",
        autoscaler_url: Optional[str] = None,
        webserver_url: str = VAST_WEB_URL,
        connection_limit: int = 500,
        default_request_timeout: float = 600.0,
        max_poll_interval: float = 5.0,
    ):
        if api_key is None or api_key == "":
            raise AttributeError(
                "API key missing. Please set VAST_API_KEY in your environment variables."
            )
        self.api_key = api_key
        self.vast_web_url = webserver_url
        if autoscaler_url:
            self.autoscaler_url = autoscaler_url
        else:
            match instance:
                case "prod":
                    self.autoscaler_url = "https://run.vast.ai"
                case "alpha":
                    self.autoscaler_url = "https://run-alpha.vast.ai"
                case "candidate":
                    self.autoscaler_url = "https://run-candidate.vast.ai"
                case "local":
                    self.autoscaler_url = "http://localhost:8080"
                case _:
                    self.autoscaler_url = "https://run.vast.ai"

        self.latencies = collections.deque(maxlen=50)
        self.debug = debug
        self.default_request_timeout = float(default_request_timeout)
        self.max_poll_interval = float(max_poll_interval)
        self.logger = logging.getLogger(self.__class__.__name__)

        if not self.logger.handlers:
            self.logger.addHandler(logging.NullHandler())

        if debug:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "[%(asctime)s] %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            handler.setLevel(logging.DEBUG)

            self.logger.addHandler(handler)
            self.logger.setLevel(logging.DEBUG)

            # If we attach our own handler, avoid double-logging via root handlers.
            self.logger.propagate = False
        else:
            # Let the application decide if/where logs go.
            self.logger.propagate = True

        self.connection_limit = connection_limit
        self._session: aiohttp.ClientSession | None = None
        self._ssl_context: ssl.SSLContext | None = None
        self._transport_owner = (
            None  # if set, delegate _get_session/get_ssl_context and skip close
        )

    async def __aenter__(self):
        await self._get_session()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._transport_owner is not None:
            return await self._transport_owner._get_session()
        if self._session is None or self._session.closed:
            self.logger.info("Started aiohttp ClientSession")
            connector = aiohttp.TCPConnector(
                limit=self.connection_limit, ssl=await self.get_ssl_context()
            )
            self._session = aiohttp.ClientSession(connector=connector)
        return self._session

    def is_open(self):
        if self._transport_owner is not None:
            return self._transport_owner.is_open()
        return self._session is not None and not self._session.closed

    async def close(self):
        if self._transport_owner is not None:
            return  # transport owned by another client
        if self._session and not self._session.closed:
            await self._session.close()
            self.logger.info("Closed aiohttp ClientSession")

    async def get_ssl_context(self) -> ssl.SSLContext:
        """Download Vast.ai root cert and build SSL context (cached)."""
        if self._transport_owner is not None:
            return await self._transport_owner.get_ssl_context()
        if self._ssl_context is None:
            async with aiohttp.ClientSession() as s:
                async with s.get(self.SSL_CERT_URL) as resp:
                    if resp.status != 200:
                        raise Exception(f"Failed to fetch SSL cert: {resp.status}")
                    cert_bytes = await resp.read()

            tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix=".cer")
            tmpfile.write(cert_bytes)
            tmpfile.close()

            ctx = ssl.create_default_context()
            ctx.load_verify_locations(cafile=tmpfile.name)
            # The Vast.ai root CA cert has pathlen set without keyCertSign in
            # Key Usage.  OpenSSL 3.x (Python ≥3.10) rejects this by default.
            # Clearing VERIFY_X509_STRICT relaxes that single check while
            # keeping full chain-of-trust and signature verification intact.
            ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
            self.logger.info("Loaded Vast.ai SSL certificate")

            self._ssl_context = ctx
            os.unlink(tmpfile.name)

        return self._ssl_context

    async def get_endpoint(self, name="") -> Endpoint_[R]:
        endpoints = await self.get_endpoints()
        for e in endpoints:
            if e.name == name:
                return e
        raise Exception(f"Endpoint {name} could not be found")

    async def get_endpoints(self) -> list[Endpoint_[R]]:
        try:
            result = await _make_request(
                client=self,
                url=self.vast_web_url,
                route="/api/v0/endptjobs/",
                api_key=self.api_key,
                params={"client_id": "me"},
            )
        except Exception as ex:
            raise Exception(f"Failed to get endpoints:\nReason={ex}")

        if not result.get("ok"):
            raise Exception(
                f"Failed to get endpoints: HTTP {result.get('status')} - {result.get('text', '')[:512]}"
            )

        response = result.get("json") or {}
        endpoints = []
        for e in response.get("results", []):
            data = EndpointData.from_dict(e)
            endpoints.append(Endpoint(client=self, data=data))
        self.logger.info(f"Found {len(endpoints)} endpoints")
        return endpoints

    async def fetch_endpoint(self, endpoint_id: int) -> EndpointData:
        """Fetch full endpoint data by ID. Used internally by ManagedEndpoint.get()."""
        try:
            result = await _make_request(
                client=self,
                url=self.vast_web_url,
                route=f"/api/v0/endptjobs/{endpoint_id}/",
                api_key=self.api_key,
            )
        except Exception as ex:
            raise Exception(f"Failed to fetch endpoint {endpoint_id}:\nReason={ex}")

        if not result.get("ok"):
            raise Exception(
                f"Failed to fetch endpoint {endpoint_id}: HTTP {result.get('status')} - {result.get('text', '')[:512]}"
            )

        return EndpointData.from_dict(result["json"]["result"])

    async def fetch_deployment(self, deployment_id: int) -> DeploymentData:
        """Fetch full deployment data by ID. Used internally by ManagedDeployment.get()."""
        try:
            result = await _make_request(
                client=self,
                url=self.vast_web_url,
                route=f"/api/v0/deployment/{deployment_id}/",
                api_key=self.api_key,
            )
        except Exception as ex:
            raise Exception(f"Failed to fetch deployment {deployment_id}:\nReason={ex}")

        if not result.get("ok"):
            raise Exception(
                f"Failed to fetch deployment {deployment_id}: HTTP {result.get('status')} - {result.get('text', '')[:512]}"
            )

        return DeploymentData.from_dict(result["json"]["deployment"])

    async def create_endpoint(self, config: EndpointConfig) -> ManagedEndpoint[R]:
        """Create a new endpoint job. Returns a ManagedEndpoint (data fetched lazily)."""
        try:
            result = await _make_request(
                client=self,
                url=self.vast_web_url,
                route="/api/v0/endptjobs/",
                api_key=self.api_key,
                body=config.to_dict(),
                method="POST",
            )
        except Exception as ex:
            raise Exception(f"Failed to create endpoint:\nReason={ex}")

        if not result.get("ok"):
            raise Exception(
                f"Failed to create endpoint: HTTP {result.get('status')} - {result.get('text', '')[:512]}"
            )

        endpoint_id = result["json"]["result"]
        self.logger.info(f"Created endpoint {endpoint_id}")
        return ManagedEndpoint(id=endpoint_id, client=self)

    async def put_deployment(self, config: DeploymentConfig) -> ManagedDeployment[R]:
        """Create or update a deployment. Returns a ManagedDeployment (data fetched lazily)."""
        logger.debug(f"putting deployment: \n {config.to_dict()}")
        try:
            result = await _make_request(
                client=self,
                url=self.vast_web_url,
                route="/api/v0/deployments/",
                api_key=self.api_key,
                body=config.to_dict(),
                method="PUT",
            )
        except Exception as ex:
            raise Exception(f"Failed to put deployment:\nReason={ex}")

        if not result.get("ok"):
            raise Exception(
                f"Failed to put deployment: HTTP {result.get('status')} - {result.get('text', '')[:512]}"
            )

        resp = DeploymentPutResponse.from_dict(result["json"])
        self.logger.info(
            f"Deployment {resp.deployment_id} ({resp.action}), endpoint {resp.endpoint_id}"
        )
        return ManagedDeployment(
            id=resp.deployment_id,
            endpoint_id=resp.endpoint_id,
            client=self,
            put_response=resp,
        )

    async def create_workergroup(self, config: WorkergroupConfig) -> int:
        """Create a workergroup (autoscale job). Returns the workergroup ID."""
        try:
            result = await _make_request(
                client=self,
                url=self.vast_web_url,
                route="/api/v0/workergroups/",
                api_key=self.api_key,
                body=config.to_dict(),
                method="POST",
            )
        except Exception as ex:
            raise Exception(f"Failed to create workergroup:\nReason={ex}")

        if not result.get("ok"):
            raise Exception(
                f"Failed to create workergroup: HTTP {result.get('status')} - {result.get('text', '')[:512]}"
            )

        wg_id = result["json"]["id"]
        self.logger.info(f"Created workergroup {wg_id}")
        return wg_id

    async def delete_workergroup(self, workergroup_id: int) -> None:
        """Delete a workergroup (autoscale job) by ID."""
        try:
            result = await _make_request(
                client=self,
                url=self.vast_web_url,
                route=f"/api/v0/workergroups/{workergroup_id}/",
                api_key=self.api_key,
                method="DELETE",
            )
        except Exception as ex:
            raise Exception(
                f"Failed to delete workergroup {workergroup_id}:\nReason={ex}"
            )

        if not result.get("ok"):
            raise Exception(
                f"Failed to delete workergroup {workergroup_id}: HTTP {result.get('status')} - {result.get('text', '')[:512]}"
            )

        self.logger.info(f"Deleted workergroup {workergroup_id}")

    async def update_workers(self, workergroup_id: int) -> dict:
        """Trigger a rolling update for all workers in a workergroup via the autoscaler."""
        try:
            result = await _make_request(
                client=self,
                url=self.autoscaler_url,
                route="/update_workers/",
                api_key=self.api_key,
                body={"workergroup_id": workergroup_id, "api_key": self.api_key},
                method="POST",
            )
        except Exception as ex:
            raise Exception(
                f"Failed to trigger worker update for workergroup {workergroup_id}:\nReason={ex}"
            )

        if not result.get("ok"):
            raise Exception(
                f"Failed to trigger worker update for workergroup {workergroup_id}: HTTP {result.get('status')} - {result.get('text', '')[:512]}"
            )

        self.logger.info(f"Triggered rolling update for workergroup {workergroup_id}")
        return result.get("json", {})

    async def find_workergroup_for_endpoint(self, endpoint_id: int) -> Optional[int]:
        """Fetch all workergroups and return the first one matching endpoint_id, or None."""
        try:
            result = await _make_request(
                client=self,
                url=self.vast_web_url,
                route="/api/v0/workergroups/",
                api_key=self.api_key,
                method="GET",
            )
        except Exception:
            return None
        if not result.get("ok"):
            return None
        for wg in result.get("json", {}).get("results", []):
            if wg.get("endpoint_id") == endpoint_id:
                return wg["id"]
        return None

    async def delete_endpoint(self, endpoint_id: int) -> None:
        """Delete an endpoint job by ID."""
        try:
            result = await _make_request(
                client=self,
                url=self.vast_web_url,
                route=f"/api/v0/endptjobs/{endpoint_id}/",
                api_key=self.api_key,
                method="DELETE",
            )
        except Exception as ex:
            raise Exception(f"Failed to delete endpoint {endpoint_id}:\nReason={ex}")

        if not result.get("ok"):
            raise Exception(
                f"Failed to delete endpoint {endpoint_id}: HTTP {result.get('status')} - {result.get('text', '')[:512]}"
            )

        self.logger.info(f"Deleted endpoint {endpoint_id}")

    async def get_endpoint_workers(self, endpoint: Endpoint_[R]) -> List[Worker]:
        if not isinstance(endpoint, Endpoint_):
            raise ValueError("endpoint must be an Endpoint")

        url = f"{self.autoscaler_url}/get_endpoint_workers/"
        payload = {"id": endpoint.id, "api_key": self.api_key}

        async with self._session.post(
            url, json=payload, timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(
                    f"get_endpoint_workers failed: HTTP {resp.status} - {text}"
                )

            data = await resp.json(content_type=None)

            # If error message from authenticate_endpoint_apikey_by_id occurs, there is a possibility that
            # the endpoint's worker instances are not ready to be queried. If an error message occurs,
            # return an empty list and print the error message to the user. The endpoint get_endpoint_workers
            # should normally return a list of dictionaries containing worker instance information.
            if isinstance(data, dict):
                if "error_msg" in data.keys():
                    self.logger.warning(
                        f"Received the following error from get_endpoint_workers:{data['error_msg']}.\nEndpoint may not be ready for query. Check credentials or wait a few minutes and try again."
                    )
                    return []

            if not isinstance(data, list):
                raise RuntimeError(
                    f"Unexpected response type (wanted list): {type(data)}"
                )

            return [Worker.from_dict(item) for item in data]

    async def get_endpoint_session(
        self, endpoint, session_id: int, session_auth: str, timeout: float = 10.0
    ):
        try:
            result = await _make_request(
                client=self,
                url=session_auth.get("url"),
                api_key="",
                route="/session/get",
                body={"session_id": session_id, "session_auth": session_auth},
                method="POST",
                retries=1,
                timeout=timeout,
                stream=False,
            )

            if not result.get("ok"):
                error_msg = f"Error on /session/get: {result.get('json', {}).get('error', result.get('text', 'Unknown error'))}"
                raise Exception(error_msg)

            worker_response = result.get("json") or {}

            auth_data = worker_response.get("auth_data")
            if auth_data is None:
                raise Exception("Missing auth_data in response")

            session = Session(
                endpoint=endpoint,
                session_id=session_id,
                lifetime=worker_response.get("lifetime"),
                expiration=worker_response.get("expiration"),
                auth_data=auth_data,
                url=auth_data.get("url"),
            )
            return session

        except asyncio.TimeoutError:
            raise
        except Exception as ex:
            error_msg = f"Failed to get session {session_id}: {ex}"
            self.logger.error(error_msg)
            raise Exception(error_msg)

    async def end_endpoint_session(self, session: Session, timeout: float = 10.0):
        try:
            self.logger.debug(
                f"Attempting to end session {session.session_id} at {session.url}"
            )
            result = await _make_request(
                client=self,
                url=session.url,
                api_key="",
                route="/session/end",
                body={
                    "session_id": session.session_id,
                    "session_auth": session.auth_data,
                },
                method="POST",
                retries=1,
                timeout=timeout,
                stream=False,
            )

            if not result.get("ok"):
                error_msg = f"Error on /session/end: {result.get('json', {}).get('error', result.get('text', 'Unknown error'))}"
                raise Exception(error_msg)

            self.logger.debug(f"Successfully ended session {session.session_id}")
            return

        except asyncio.TimeoutError:
            raise
        except Exception as ex:
            error_msg = f"Failed to end session {session.session_id}: {ex}"
            self.logger.error(error_msg)
            raise Exception(error_msg)

    async def start_endpoint_session(
        self,
        endpoint: Endpoint_[R],
        cost: int = 100,
        lifetime: float = 60,
        on_close_route: str = None,
        on_close_payload: dict = None,
        timeout: float = None,
    ) -> Session:
        try:
            session_start_response = await self.queue_endpoint_request(
                endpoint=endpoint,
                worker_route="/session/create",
                worker_payload={
                    "lifetime": lifetime,
                    "on_close_route": on_close_route,
                    "on_close_payload": on_close_payload,
                },
                cost=cost,
                timeout=timeout,
                worker_timeout=10.0,
            )
            if not session_start_response.get("ok"):
                error_msg = f"Error on /session/create: {session_start_response.get('json', {}).get('error', session_start_response.get('text', 'Unknown error'))}"
                raise Exception(error_msg)
            response = session_start_response.get("response")
            if response is None:
                raise Exception("No response from /session/create")
            if not isinstance(response, dict):
                raise Exception(
                    "Invalid response from /session/create: expected mapping"
                )
            session_id = response.get("session_id")
            if session_id is None:
                raise Exception("Missing session id")
            expiration = response.get("expiration")
            url = session_start_response.get("url")
            if url is None:
                raise Exception("Missing URL")
            auth_data = session_start_response.get("auth_data")
            if auth_data is None:
                raise Exception("Missing auth data")
            return Session(
                endpoint=endpoint,
                session_id=session_id,
                lifetime=lifetime,
                expiration=expiration,
                url=url,
                auth_data=auth_data,
            )
        except asyncio.TimeoutError:
            raise
        except Exception as ex:
            error_msg = f"Failed to create session: {ex}"
            self.logger.error(error_msg)
            raise Exception(error_msg)

    async def _do_request(
        self,
        endpoint: Endpoint_[R],
        worker_route: str,
        worker_payload: dict,
        session: Optional[Session] = None,
        tracker: Optional[RequestStatus] = None,
        cost: int = 100,
        timeout: Optional[float] = None,
        worker_timeout: Optional[float] = 600,
        retry: bool = True,
        max_retries: Optional[int] = None,
        stream: bool = False,
    ) -> dict:
        """Core request logic: route to a worker, execute, retry on failure. Returns the response dict."""
        if tracker is None:
            tracker = RequestStatus()

        request_idx: int = 0
        total_attempts = 0
        start_time = time.time()
        try:
            while True:
                total_attempts += 1
                tracker.status = "Queued"
                worker_url = ""
                auth_data = {}
                session_id = None

                # Check total elapsed time
                if timeout is not None and (time.time() - start_time) >= timeout:
                    raise asyncio.TimeoutError(
                        f"Timed out after {time.time() - start_time:.1f}s waiting for worker"
                    )

                if session is None:
                    if request_idx == 0:
                        self.logger.debug(
                            f"Sending initial route call for request_idx {request_idx}"
                        )
                    else:
                        self.logger.debug(
                            f"Sending retry route call for request_idx {request_idx}"
                        )

                    route = await endpoint._route(
                        cost=cost, req_idx=request_idx, timeout=60.0
                    )

                    request_idx = route.request_idx
                    if request_idx:
                        self.logger.debug(f"Got request index {request_idx}")
                    else:
                        self.logger.info(  # usually non-fatal due to get_serverless_groups polling delay; we should fix that and make this an error again.
                            "Did not get request_idx from initial route"
                        )

                    poll_interval = 1
                    poll_elapsed = 0
                    attempt = 0
                    while route.status != "READY":
                        tracker.status = "Polling"

                        # Check total elapsed time
                        if (
                            timeout is not None
                            and (time.time() - start_time) >= timeout
                        ):
                            raise asyncio.TimeoutError(
                                f"Timed out after {time.time() - start_time:.1f}s waiting for worker to become ready"
                            )

                        await asyncio.sleep(poll_interval)
                        poll_elapsed += poll_interval

                        route = await endpoint._route(
                            cost=cost, req_idx=request_idx, timeout=60.0
                        )
                        request_idx = route.request_idx or request_idx

                        attempt += 1
                        poll_interval = random.uniform(
                            0.1,
                            min(
                                2 ** min(attempt, 20) + random.uniform(0, 1),
                                self.max_poll_interval,
                            ),
                        )
                        self.logger.debug(f"Polling route, attempt {attempt}")

                    worker_url = route.get_url()
                    auth_data = route.body
                else:
                    if session.url is not None:
                        worker_url = session.url
                        auth_data = session.auth_data
                        session_id = session.session_id

                payload = worker_payload
                worker_request_body = {
                    "auth_data": auth_data,
                    "session_id": session_id,
                    "payload": payload,
                }

                self.logger.debug("Found worker machine, starting work")
                if tracker.status != "Retrying":
                    tracker.status = "In Progress"
                    tracker.start_time = time.time()

                # Transport/JSON failures may raise; HTTP errors return ok=False.
                try:
                    result = await _make_request(
                        client=self,
                        url=worker_url,
                        route=worker_route,
                        api_key=endpoint.api_key,
                        body=worker_request_body,
                        method="POST",
                        retries=1,  # avoid stacking retries with the outer loop
                        timeout=worker_timeout,
                        stream=stream,
                    )
                except (
                    aiohttp.ClientConnectorError,
                    aiohttp.ServerDisconnectedError,
                ) as ex:
                    # Worker is gone
                    if session is not None:
                        # Session is bound to this worker - can't re-route
                        self.logger.error(
                            f"Session worker unavailable ({type(ex).__name__})"
                        )
                        session.open = False
                        raise ConnectionError(
                            f"Session worker unavailable: {ex}"
                        ) from ex
                    # No session - reset request_idx to force a fresh route
                    self.logger.warning(
                        f"Worker unavailable ({type(ex).__name__}), re-routing to new worker"
                    )
                    tracker.status = "Retrying"
                    continue
                except Exception as ex:
                    self.logger.error(f"Worker request failed: {ex}")
                    tracker.status = "Retrying"
                    continue

                if not result.get("ok"):
                    if (
                        retry
                        and result.get("retryable")
                        and (max_retries is None or total_attempts < max_retries)
                    ):
                        # Check if we have time left before retrying
                        if (
                            timeout is not None
                            and (time.time() - start_time) >= timeout
                        ):
                            raise asyncio.TimeoutError(
                                f"Request timed out after {time.time() - start_time:.1f}s"
                            )

                        tracker.status = "Retrying"
                        await asyncio.sleep(
                            min(
                                (2 ** min(total_attempts, 20)) + random.uniform(0, 1),
                                self.max_poll_interval,
                            )
                        )
                        continue

                    # Return the raw HTTP result to the caller
                    tracker.status = "Complete"
                    tracker.complete_time = time.time()
                    if tracker.start_time is not None:
                        self.latencies.append(
                            tracker.complete_time - tracker.start_time
                        )

                    return {
                        "response": result.get("json")
                        if result.get("json") is not None
                        else {"error": result.get("text", "")},
                        "ok": result.get("ok"),
                        "status": result.get("status"),
                        "text": result.get("text"),
                        "latency": (tracker.complete_time - tracker.start_time)
                        if tracker.start_time
                        else None,
                        "url": worker_url,
                        "request_idx": request_idx,
                        "auth_data": auth_data,
                    }

                # Success
                worker_response = result.get("stream") if stream else result.get("json")

                tracker.status = "Complete"
                tracker.complete_time = time.time()
                self.latencies.append(tracker.complete_time - tracker.start_time)
                self.logger.info("Endpoint request task completed")

                return {
                    "response": worker_response,
                    "ok": result.get("ok"),
                    "status": result.get("status"),
                    "text": result.get("text"),
                    "latency": tracker.complete_time - tracker.start_time,
                    "url": worker_url,
                    "request_idx": request_idx,
                    "auth_data": auth_data,
                }

        except asyncio.CancelledError:
            tracker.status = "Cancelled"
            raise
        except Exception as ex:
            tracker.status = "Errored"
            self.logger.error(f"Request errored: {ex}")
            raise

    @abstractmethod
    def queue_endpoint_request(
        self,
        endpoint: Endpoint_[R],
        worker_route: str,
        worker_payload: dict,
        session: Optional[Session] = None,
        serverless_request: Optional[Union[ServerlessRequest, RequestStatus]] = None,
        cost: int = 100,
        timeout: Optional[float] = None,
        worker_timeout: Optional[float] = 600,
        retry: bool = True,
        max_retries: Optional[int] = None,
        stream: bool = False,
    ) -> R:
        """Dispatch a request to a serverless endpoint. Return type depends on subclass."""
        ...


class Serverless(_ServerlessBase[ServerlessRequest]):
    """Fire-and-observe client: queue_endpoint_request returns a ServerlessRequest (Future)."""

    def queue_endpoint_request(
        self,
        endpoint: Endpoint,
        worker_route: str,
        worker_payload: dict,
        session: Optional[Session] = None,
        serverless_request: Optional[Union[ServerlessRequest, RequestStatus]] = None,
        cost: int = 100,
        timeout: Optional[float] = None,
        worker_timeout: Optional[float] = 600,
        retry: bool = True,
        max_retries: Optional[int] = None,
        stream: bool = False,
    ) -> ServerlessRequest:
        """Return a Future that will resolve once the request completes."""
        if serverless_request is None:
            serverless_request = ServerlessRequest()
        elif isinstance(serverless_request, RequestStatus):
            serverless_request = ServerlessRequest(tracker=serverless_request)

        async def task(request: ServerlessRequest):
            try:
                result = await self._do_request(
                    endpoint=endpoint,
                    worker_route=worker_route,
                    worker_payload=worker_payload,
                    session=session,
                    tracker=request.tracker,
                    cost=cost,
                    timeout=timeout,
                    worker_timeout=worker_timeout,
                    retry=retry,
                    max_retries=max_retries,
                    stream=stream,
                )
                request.set_result(result)
            except asyncio.CancelledError:
                pass  # tracker already set by _do_request
            except Exception as ex:
                request.set_exception(ex)

        bg_task = asyncio.create_task(task(serverless_request))

        def _propagate_cancel(fut: ServerlessRequest):
            if fut.cancelled():
                bg_task.cancel()

        serverless_request.add_done_callback(_propagate_cancel)
        self.logger.info("Queued endpoint request")
        return serverless_request


class CoroutineServerless(_ServerlessBase[Coroutine[Any, Any, dict]]):
    """Async/await client: queue_endpoint_request returns a coroutine."""

    def queue_endpoint_request(
        self,
        endpoint: Endpoint,
        worker_route: str,
        worker_payload: dict,
        session: Optional[Session] = None,
        serverless_request: Optional[Union[ServerlessRequest, RequestStatus]] = None,
        cost: int = 100,
        timeout: Optional[float] = None,
        worker_timeout: Optional[float] = 600,
        retry: bool = True,
        max_retries: Optional[int] = None,
        stream: bool = False,
    ) -> Coroutine[Any, Any, dict]:
        """Return a coroutine that resolves to the response dict when awaited."""
        if isinstance(serverless_request, ServerlessRequest):
            tracker = serverless_request.tracker
        elif isinstance(serverless_request, RequestStatus):
            tracker = serverless_request
        else:
            tracker = None
        return self._do_request(
            endpoint=endpoint,
            worker_route=worker_route,
            worker_payload=worker_payload,
            session=session,
            tracker=tracker,
            cost=cost,
            timeout=timeout,
            worker_timeout=worker_timeout,
            retry=retry,
            max_retries=max_retries,
            stream=stream,
        )
