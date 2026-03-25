# client.py
from .connection import _make_request
from .endpoint import Endpoint
from .worker import Worker
from .session import Session
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
        max_poll_interval: float = 5.0
    ):
        if api_key is None or api_key == "":
            raise AttributeError("API key missing. Please set VAST_API_KEY in your environment variables.")
        self.api_key = api_key

        match instance:
            case "prod":
                self.autoscaler_url = "https://run.vast.ai"
                self.vast_web_url   = "https://console.vast.ai"
            case "alpha":
                self.autoscaler_url = "https://run-alpha.vast.ai"
                self.vast_web_url   = "https://alpha.vast.ai"
            case "candidate":
                self.autoscaler_url = "https://run-candidate.vast.ai"
                self.vast_web_url   = "https://candidate.vast.ai"
            case "local":
                self.autoscaler_url = "http://localhost:8080"
                self.vast_web_url   = "https://alpha.vast.ai"
            case _:
                self.autoscaler_url = "https://run.vast.ai"
                self.vast_web_url   = "https://console.vast.ai"

        self.latencies = collections.deque(maxlen=50)
        self.debug = debug
        self.default_request_timeout = float(default_request_timeout)
        self.max_poll_interval = float(max_poll_interval)
        self.logger = logging.getLogger(self.__class__.__name__)

        if not self.logger.handlers:
            self.logger.addHandler(logging.NullHandler())

        if debug:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('[%(asctime)s] %(name)s - %(levelname)s - %(message)s')
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

    async def __aenter__(self):
        await self._get_session()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self.logger.info("Started aiohttp ClientSession")
            connector = aiohttp.TCPConnector(limit=self.connection_limit, ssl=await self.get_ssl_context())
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


    async def get_endpoint(self, name="") -> Endpoint:
        endpoints = await self.get_endpoints()
        for e in endpoints:
            if e.name == name:
                return e
        raise Exception(f"Endpoint {name} could not be found")

    async def get_endpoints(self) -> list[Endpoint]:
        try:
            result = await _make_request(
                client=self,
                url=self.vast_web_url,
                route="/api/v0/endptjobs/",
                api_key=self.api_key,
                params={"client_id": "me"}
            )
        except Exception as ex:
            raise Exception(f"Failed to get endpoints:\nReason={ex}")

        if not result.get("ok"):
            raise Exception(f"Failed to get endpoints: HTTP {result.get('status')} - {result.get('text','')[:512]}")

        response = result.get("json") or {}
        endpoints = []
        for e in response.get("results", []):
            endpoints.append(Endpoint(client=self, name=e["endpoint_name"], id=e["id"], api_key=e["api_key"]))
        self.logger.info(f"Found {len(endpoints)} endpoints")
        return endpoints

    async def get_endpoint_workers(self, endpoint: Endpoint) -> List[Worker]:
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

    async def get_endpoint_session(
        self,
        endpoint,
        session_id: int,
        session_auth: str,
        timeout: float = 10.0
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
                url=auth_data.get("url")
            )
            return session

        except asyncio.TimeoutError:
            raise
        except Exception as ex:
            error_msg = f"Failed to get session {session_id}: {ex}"
            self.logger.error(error_msg)
            raise Exception(error_msg)

    async def end_endpoint_session(
        self,
        session: Session,
        timeout: float = 10.0
    ):
        try:
            self.logger.debug(f"Attempting to end session {session.session_id} at {session.url}")
            result = await _make_request(
                client=self,
                url=session.url,
                api_key="",
                route="/session/end",
                body={"session_id": session.session_id, "session_auth": session.auth_data},
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
        endpoint: Endpoint,
        cost: int = 100,
        lifetime: float = 60,
        on_close_route: str = None,
        on_close_payload: dict = None,
        timeout: float = None
    ) -> Session:
        try:
            session_start_response = await self.queue_endpoint_request(
                endpoint=endpoint,
                worker_route="/session/create",
                worker_payload={"lifetime": lifetime, "on_close_route" : on_close_route, "on_close_payload" : on_close_payload },
                cost=cost,
                timeout=timeout,
                worker_timeout=10.0
            )
            if not session_start_response.get("ok"):
                error_msg = f"Error on /session/create: {session_start_response.get('json', {}).get('error', session_start_response.get('text', 'Unknown error'))}"
                raise Exception(error_msg)
            response = session_start_response.get("response")
            if response is None:
                raise Exception(f"No response from /session/create. Status {response.get('status')}")
            session_id = session_start_response.get("response").get("session_id")
            if session_id is None:
                raise Exception("Missing session id")
            expiration = session_start_response.get("response").get("expiration")
            url = session_start_response.get("url")
            if url is None:
                raise Exception("Missing URL")
            auth_data = session_start_response.get("auth_data")
            if auth_data is None:
                raise Exception("Missing auth data")
            return Session(endpoint=endpoint, session_id=session_id, lifetime=lifetime, expiration=expiration, url=url, auth_data=auth_data)
        except asyncio.TimeoutError:
            raise
        except Exception as ex:
            error_msg = f"Failed to create session: {ex}"
            self.logger.error(error_msg)
            raise Exception(error_msg)


    def queue_endpoint_request(
        self,
        endpoint: Endpoint,
        worker_route: str,
        worker_payload: dict,
        session: Session = None,
        serverless_request: Optional[ServerlessRequest] = None,
        cost: int = 100,
        timeout: Optional[float] = None,
        worker_timeout: Optional[float] = 600,
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
            start_time = time.time()
            try:
                while True:
                    total_attempts += 1
                    request.status = "Queued"
                    worker_url = ""
                    auth_data = {}
                    session_id = None

                    # Check total elapsed time
                    if timeout is not None and (time.time() - start_time) >= timeout:
                        raise asyncio.TimeoutError(f"Timed out after {time.time() - start_time:.1f}s waiting for worker")

                    if session is None:
                        if request_idx == 0:
                            self.logger.debug(f"Sending initial route call for request_idx {request_idx}")
                        else:
                            self.logger.debug(f"Sending retry route call for request_idx {request_idx}")

                        route = await endpoint._route(cost=cost, req_idx=request_idx, timeout=60.0)

                        request_idx = route.request_idx
                        if request_idx:
                            self.logger.debug(f"Got request index {request_idx}")
                        else:
                            self.logger.error("Did not get request_idx from initial route")

                        poll_interval = 1
                        poll_elapsed = 0
                        attempt = 0
                        while route.status != "READY":
                            request.status = "Polling"

                            # Check total elapsed time
                            if timeout is not None and (time.time() - start_time) >= timeout:
                                raise asyncio.TimeoutError(f"Timed out after {time.time() - start_time:.1f}s waiting for worker to become ready")

                            await asyncio.sleep(poll_interval)
                            poll_elapsed += poll_interval

                            route = await endpoint._route(cost=cost, req_idx=request_idx, timeout=60.0)
                            request_idx = route.request_idx or request_idx

                            attempt += 1
                            poll_interval = random.uniform(0.1, min(2 ** min(attempt, 20) + random.uniform(0, 1), self.max_poll_interval))
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
                        "payload": payload
                    }

                    self.logger.debug("Found worker machine, starting work")
                    if request.status != "Retrying":
                        request.status = "In Progress"
                        request.start_time = time.time()

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
                            stream=stream
                        )
                    except (aiohttp.ClientConnectorError, aiohttp.ServerDisconnectedError) as ex:
                        # Worker is gone
                        if session is not None:
                            # Session is bound to this worker - can't re-route
                            self.logger.error(f"Session worker unavailable ({type(ex).__name__})")
                            session.open = False
                            raise ConnectionError(f"Session worker unavailable: {ex}") from ex
                        # No session - reset request_idx to force a fresh route
                        self.logger.warning(f"Worker unavailable ({type(ex).__name__}), re-routing to new worker")
                        request.status = "Retrying"
                        continue
                    except Exception as ex:
                        self.logger.error(f"Worker request failed: {ex}")
                        request.status = "Retrying"
                        continue


                    if not result.get("ok"):
                        if retry and result.get("retryable") and (max_retries is None or total_attempts < max_retries):
                            # Check if we have time left before retrying
                            if timeout is not None and (time.time() - start_time) >= timeout:
                                raise asyncio.TimeoutError(f"Request timed out after {time.time() - start_time:.1f}s")

                            request.status = "Retrying"
                            await asyncio.sleep(min(2 ** min(total_attempts, 20) + random.uniform(0, 1), self.max_poll_interval))
                            continue

                        # Return the raw HTTP result to the caller
                        request.status = "Complete"
                        request.complete_time = time.time()
                        if request.start_time is not None:
                            self.latencies.append(request.complete_time - request.start_time)

                        response = {
                            "response": result.get("json") if result.get("json") is not None else {"error": result.get("text", "")},
                            "ok": result.get("ok"),
                            "status": result.get("status"),
                            "text" : result.get("text"),
                            "latency": (request.complete_time - request.start_time) if request.start_time else None,
                            "url": worker_url,
                            "request_idx": request_idx,
                            "auth_data": auth_data
                        }
                        request.set_result(response)
                        return

                    # Success
                    worker_response = result.get("stream") if stream else result.get("json")

                    request.status = "Complete"
                    request.complete_time = time.time()
                    self.latencies.append(request.complete_time - request.start_time)
                    self.logger.info("Endpoint request task completed")

                    response = {
                        "response": worker_response,
                        "ok" : result.get("ok"),
                        "status" : result.get("status"),
                        "text" : result.get("text"),
                        "latency": request.complete_time - request.start_time,
                        "url": worker_url,
                        "request_idx": request_idx,
                        "auth_data": auth_data
                    }
                    request.set_result(response)
                    return

            except asyncio.CancelledError:
                request.status = "Cancelled"
                return
            except Exception as ex:
                request.status = "Errored"
                self.logger.error(f"Request errored: {ex}")
                request.set_exception(ex)
                return

        bg_task = asyncio.create_task(task(serverless_request))

        def _propagate_cancel(fut: ServerlessRequest):
            if fut.cancelled():
                bg_task.cancel()

        serverless_request.add_done_callback(_propagate_cancel)
        self.logger.info("Queued endpoint request")
        return serverless_request
