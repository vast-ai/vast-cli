from .endpoint import Endpoint
from typing import Callable, Optional
import inspect
import logging

log = logging.getLogger(__name__)


class Session:
    endpoint: Endpoint
    session_id: str
    open: bool
    url: str
    lifetime: float
    auth_data: dict
    on_close_route: str
    on_close_payload: dict

    def __init__(self, endpoint: Endpoint, session_id: str, lifetime: float, expiration: str, url: str, auth_data: dict, on_close_route: str = None, on_close_payload: dict = None):
        if endpoint is None:
            raise ValueError("Session cannot be created with empty endpoint")
        if session_id is None:
            raise ValueError("Session cannot be created with empty session_id")
        if url is None:
            raise ValueError("Session cannot be created with empty url")

        self.endpoint = endpoint
        self.session_id = session_id
        self.lifetime = lifetime
        self.expiration = expiration
        self.url = url
        self.auth_data = auth_data

        self.open = True
        self.on_close_route = on_close_route
        self.on_close_payload = on_close_payload
        self._closing = False  # guard to ensure one-time execution

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()
        return False

    async def is_open(self):
        result = await self.endpoint.session_healthcheck(self)
        self.open = result
        return result

    async def close(self):
        """
        Explicit close for non-async contexts.
        Returns an awaitable if async work is required.
        """
        if not self.open or self._closing:
            return None
        self._closing = True
        try:
            await self.endpoint.close_session(self)
        except Exception as e:
            log.warning(f"Error closing session {self.session_id}: {e}")
        finally:
            self.open = False
        return

    def request(
        self,
        route,
        payload,
        serverless_request=None,
        cost: int = 100,
        retry: bool = True,
        stream: bool = False,
    ):
        """Forward requests to the endpoint"""
        if not self.open:
            raise ValueError("Cannot make request on closed session.")

        async def _wrapped_request():
            result = await self.endpoint.request(
                route=route,
                payload=payload,
                serverless_request=serverless_request,
                cost=cost,
                retry=retry,
                stream=stream,
                session=self,
            )

            if result.get("status") == 410:
                self.open = False
                raise ValueError("Cannot make request on closed session.")

            return result

        return _wrapped_request()