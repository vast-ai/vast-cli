from .connection import _make_request
from .endpoint import Endpoint
from .worker import Worker
import asyncio
import aiohttp
import ssl
import os
import tempfile
import logging
import random
import time
import collections
from typing import Any, Awaitable, Callable, Deque, Dict, Optional, Union, List

class ServerlessRequest(asyncio.Future):
    """A request to a Serverless endpoint managed by the client"""
    def __init__(self):
        super().__init__()
        self.status = "New"
        self.create_time = time.time()
        self.start_time = None
        self.complete_time = None
        self.req_idx = 0

    def then(self, callback) -> "ServerlessRequest":
        def _done(fut):
            if fut.exception() is not None:
                print(fut.exception())
                return
            callback(fut.result())
        self.add_done_callback(_done)
        return self

class Serverless:
    SSL_CERT_URL        = "https://console.vast.ai/static/jvastai_root.cer"
    VAST_WEB_URL        = "https://console.vast.ai"
    VAST_SERVERLESS_URL = "https://run.vast.ai"

    def __init__(
        self,
        api_key: Optional[str] = os.environ.get("VAST_API_KEY", None),
        *,
        debug: bool = False,
        instance: str = "prod",
        connection_limit: int = 500,
        default_request_timeout: float = 600.0,
        max_poll_interval: float = 15.0
    ):
        if api_key is None or api_key == "":
            raise AttributeError("API key missing. Please set VAST_API_KEY in your environment variables.")
        self.api_key = api_key

        match instance:
            case "prod":
                self.autoscaler_url = "https://run.vast.ai"
            case "alpha":
                self.autoscaler_url = "https://run-alpha.vast.ai"
            case "local":
                self.autoscaler_url = "http://localhost:8080"
            case _:
                self.autoscaler_url = "https://run.vast.ai"

        self.latencies = collections.deque(maxlen=50)
        self.debug = debug
        self.default_request_timeout = float(default_request_timeout)
        self.max_poll_interval = float(max_poll_interval)
        self.logger = logging.getLogger(self.__class__.__name__)

        if self.debug:
            # Only set up logging if debug is True
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '[%(asctime)s] %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.DEBUG)
        else:
            # If debug is False, disable logging
            self.logger.addHandler(logging.NullHandler())
        self.logger.propagate = False

        self.connection_limit = connection_limit
        self._session: aiohttp.ClientSession | None = None
        self._ssl_context: ssl.SSLContext | None = None

    async def __aenter__(self):
        await self._get_session()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self.logger.info("Started aiohttp ClientSession")
            connector = aiohttp.TCPConnector(limit=self.connection_limit, ssl= await self.get_ssl_context())
            self._session = aiohttp.ClientSession(connector=connector)
        return self._session
    
    def is_open(self):
        return self._session is not None and not self._session.closed

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
            self.logger.info("Closed aiohttp ClientSession")

    async def get_ssl_context(self) -> ssl.SSLContext:
        """Download Vast.ai root cert and build SSL context (cached)."""
        if self._ssl_context is None:
            # Download the Vast root cert
            async with aiohttp.ClientSession() as s:
                async with s.get(self.SSL_CERT_URL) as resp:
                    if resp.status != 200:
                        raise Exception(f"Failed to fetch SSL cert: {resp.status}")
                    cert_bytes = await resp.read()

            # Write to a temporary PEM file
            tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix=".cer")
            tmpfile.write(cert_bytes)
            tmpfile.close()

            try:
                # Start with system defaults
                ctx = ssl.create_default_context()
                ctx.load_verify_locations(cafile=tmpfile.name)
                self.logger.info("Loaded Vast.ai SSL certificate")
                self._ssl_context = ctx
            finally:
                os.unlink(tmpfile.name)

        return self._ssl_context

    def get_avg_request_time(self) -> float:
        """
        Rolling estimate for routing timeout. A small safety margin is added.
        Currently unused. default to 60.0
        """
        return 60.0
        if len(self.latencies) < 10:
            return 30.0  # conservative default until we have data
        avg = sum(self.latencies) / len(self.latencies)
        # Clamp to reasonable bounds
        return float(max(5.0, min(avg + 2.0, 600.0)))

    async def get_endpoint(self, name="") -> Endpoint:
        endpoints = await self.get_endpoints()
        for e in endpoints:
            if e.name == name:
                return e
        raise Exception(f"Endpoint {name} could not be found")

    async def get_endpoints(self) -> list[Endpoint]:
        try:
            response = await _make_request(
                client=self,
                url=self.VAST_WEB_URL,
                route="/api/v0/endptjobs/",
                api_key=self.api_key,
                params={"client_id": "me"}
            )
        except Exception as ex:
            raise Exception(
                f"Failed to get endpoints:\nReason={ex}"
            )
        endpoints = []
        for e in response["results"]:
            endpoints.append(Endpoint(client=self, name=e["endpoint_name"], id=e["id"], api_key=e["api_key"]))
        self.logger.info(f"Found {len(endpoints)} endpoints")
        return endpoints
    
    async def get_endpoint_workers(self, endpoint: Endpoint) -> List[Worker]:
        """
        Equivalent to:
          curl -X POST https://run.vast.ai/get_endpoint_workers/ \
               -H "Content-Type: application/json" \
               -d '{"id": <endpoint_id>, "api_key": "<VAST_API_KEY>"}'
        """
        if not isinstance(endpoint, Endpoint):
            raise ValueError("endpoint must be an Endpoint")

        url = f"{self.autoscaler_url}/get_endpoint_workers/"
        payload = {"id": endpoint.id, "api_key": self.api_key}

        async with self._session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"get_endpoint_workers failed: HTTP {resp.status} - {text}")

            data = await resp.json(content_type=None)

            # If error message from authenticate_endpoint_apikey_by_id occurs, there is a possibility that
            # the endpoint's worker instances are not ready to be queried. If an error message occurs,
            # return an empty list and print the error message to the user. The endpoint get_endpoint_workers
            # should normally return a list of dictionaries containing worker instance information.
            if isinstance(data,dict):
                if 'error_msg' in data.keys():
                    self.logger.warning(f"Received the following error from get_endpoint_workers:{data['error_msg']}.\nEndpoint may not be ready for query. Check credentials or wait a few minutes and try again.")
                    return []

            
            if not isinstance(data, list):
                raise RuntimeError(f"Unexpected response type (wanted list): {type(data)}")

            return [Worker.from_dict(item) for item in data]

    def queue_endpoint_request(
        self,
        endpoint: Endpoint,
        worker_route: str,
        worker_payload: dict,
        serverless_request: Optional[ServerlessRequest] = None,
        cost: int = 100,
        max_wait_time: Optional[float] = None,
        retry: bool = True,
        max_retries: int = None,
        stream: bool = False
    ) -> ServerlessRequest:
        """Return a Future that will resolve once the request completes."""
        if serverless_request is None:
            serverless_request = ServerlessRequest()

        async def task(request: ServerlessRequest):
            request_idx: int = 0
            total_attempts = 0
            try:
                while True:
                    total_attempts += 1
                    request.status = "Queued"
                    self.logger.debug("Sending initial route call")

                    route = await endpoint._route(cost=cost, req_idx=request_idx, timeout=self.get_avg_request_time())
                    request_idx = route.request_idx
                    if (request_idx):
                        self.logger.debug(f"Got initial request index {request_idx}")
                    else:
                        self.logger.error("Did not get request_idx from initial route")

                    poll_interval = 1
                    elapsed_time = 0
                    attempt = 0
                    while route.status != "READY":
                        request.status = "Polling"
                        if max_wait_time is not None and elapsed_time >= max_wait_time:
                            raise asyncio.TimeoutError("Timed out waiting for worker to become ready")

                        await asyncio.sleep(poll_interval)
                        elapsed_time += poll_interval

                        route = await endpoint._route(cost=cost, req_idx=request_idx, timeout=self.get_avg_request_time())
                        request_idx = route.request_idx or request_idx

                        # exponential backoff + jitter (cap)
                        attempt += 1
                        poll_interval = min((2 ** attempt) + random.uniform(0, 1), self.max_poll_interval)
                        self.logger.debug("Polling route...")

                    # Now, route is ready for sending request to worker
                    worker_url = route.get_url()
                    auth_data = route.body
                    payload = worker_payload
                    worker_request_body = {
                                            "auth_data" : auth_data,
                                            "payload" : payload
                                        }
                    
                    try:
                        self.logger.debug("Found worker machine, starting work")
                        if request.status != "Retrying":
                            request.status = "In Progress"
                            request.start_time = time.time()
                        worker_response = await _make_request(
                            client=self,
                            url=worker_url,
                            route=worker_route,
                            api_key=endpoint.api_key,
                            body=worker_request_body,
                            method="POST",
                            retries=1,
                            timeout=600,
                            stream=stream
                        )
                    except Exception as ex:
                        if retry and (max_retries is None or total_attempts < max_retries):
                            request.status = "Retrying"
                            await asyncio.sleep(min((2 ** total_attempts) + random.uniform(0, 1), self.max_poll_interval))
                            continue
                        raise

                    # Resolve future, task complete 
                    request.status = "Complete"
                    request.complete_time = time.time()
                    self.latencies.append(request.complete_time - request.start_time)
                    self.logger.info("Endpoint request task completed")

                    response = {
                        "response" : worker_response,
                        "latency" : request.complete_time - request.start_time,
                        "url" : worker_url,
                        "request_idx" : request_idx
                    }
                    request.set_result(response)
                    return

            except asyncio.CancelledError:
                request.status = "Cancelled"
                request.set_exception(asyncio.CancelledError())
                return
            except Exception as ex:
                request.status = "Errored"
                # Fail the future so awaiters / then().catch() are notified
                request.set_exception(ex)
                self.logger.error(f"Request errored: {ex}")
                return

        # Create asyncio task for request lifetime management
        bg_task = asyncio.create_task(task(serverless_request))

        def _propagate_cancel(fut: ServerlessRequest):
            if fut.cancelled():
                bg_task.cancel()

        serverless_request.add_done_callback(_propagate_cancel)
        self.logger.info("Queued endpoint request")
        return serverless_request